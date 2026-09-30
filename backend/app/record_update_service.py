"""
backend/app/record_update_service.py — Authenticated Approval & Typed Updates.

Design contracts:
  - Correct order: Officer Review -> Authenticated Approval -> Record Update -> Versioned Record.
  - You cannot push a record update without a valid, unused approval.
  - The approval class determines the required authority tier.
"""
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any

from sqlalchemy.orm import Session

from . import models, audit_service, auth, version_manager


def create_approval(
    db: Session,
    case_id: str,
    approved_by: models.User,
    update_class: models.UpdateClass,
    reason: str
) -> models.Approval:
    """Create an authenticated approval gate."""
    # Ensure user has sufficient tier for this update_class
    auth.check_update_class_tier(update_class.value, approved_by)

    approval = models.Approval(
        approval_id=str(uuid.uuid4()),
        case_id=case_id,
        approved_by=approved_by.user_id,
        approver_role=approved_by.role,
        approver_tier=approved_by.authority_tier,
        update_class=update_class,
        reason=reason
    )
    db.add(approval)
    
    # Audit log
    audit_service.append_event(
        db, case_id, audit_service.EVENT_APPROVAL,
        data={
            "approval_id": approval.approval_id,
            "update_class": update_class.value,
            "tier": approved_by.authority_tier
        },
        actor_id=approved_by.user_id, actor_role=approved_by.role.value
    )
    
    db.commit()
    db.refresh(approval)
    return approval


def apply_record_update(
    db: Session,
    case_id: str,
    approval_id: str,
    target_record_type: str,
    target_record_id: str,
    changes: List[Dict[str, Any]],
    user: models.User
) -> models.RecordUpdate:
    """
    Apply a typed record update using a valid approval.
    """
    approval = db.get(models.Approval, approval_id)
    if not approval:
        raise ValueError("Approval not found")
    if approval.case_id != case_id:
        raise ValueError("Approval does not belong to this case")
    if approval.used:
        raise ValueError("Approval has already been used")

    # The actual mutation logic would go here in a production system.
    # For MVP, we record the intent to change and create the new version row.
    # (Leaving actual live table mutation mocked per PRD limitation).
    
    # Mark approval as used
    approval.used = True
    db.add(approval)

    update_record = models.RecordUpdate(
        update_id=str(uuid.uuid4()),
        case_id=case_id,
        approval_id=approval_id,
        update_class=approval.update_class,
        target_record_type=target_record_type,
        target_record_id=target_record_id,
        changes=changes,
        authorized_by=user.user_id
    )
    db.add(update_record)

    # Version the record
    resulting_version = None
    if target_record_type == "parcel":
        parcel = db.get(models.Parcel, target_record_id)
        if parcel:
            v = version_manager.create_parcel_version(db, parcel, case_id, approval_id)
            resulting_version = v.version_id
    elif target_record_type == "ror":
        ror = db.get(models.RoR, target_record_id)
        if ror:
            v = version_manager.create_ror_version(db, ror, case_id, approval_id)
            resulting_version = v.version_id

    update_record.resulting_version_id = resulting_version

    # Close case
    case = db.get(models.Case, case_id)
    case.status = models.CaseStatus.CLOSED
    db.add(case)

    # Audit log
    audit_service.append_event(
        db, case_id, audit_service.EVENT_RECORD_UPDATE,
        data={
            "update_id": update_record.update_id,
            "target": target_record_type,
            "class": approval.update_class.value
        },
        actor_id=user.user_id, actor_role=user.role.value
    )
    audit_service.append_event(
        db, case_id, audit_service.EVENT_CASE_CLOSED,
        data={"reason": "Record update applied"},
        actor_id=user.user_id, actor_role=user.role.value
    )

    db.commit()
    db.refresh(update_record)
    return update_record
