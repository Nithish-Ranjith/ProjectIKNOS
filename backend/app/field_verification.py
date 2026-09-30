"""
backend/app/field_verification.py — Structured field evidence.

Design contracts:
  - Free-text summary is permitted but not the sole evidence.
  - Requires structured photo_refs, measurement_refs, observations.
"""
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any

from sqlalchemy.orm import Session

from . import models, audit_service


def submit_verification(
    db: Session,
    case_id: str,
    surveyor_id: str,
    observations: List[Dict[str, Any]],
    photo_refs: List[str],
    measurement_refs: List[Dict[str, Any]],
    verification_status: models.VerificationStatus,
    findings_summary: str = "",
    lat: float = None,
    lon: float = None
) -> models.FieldVerification:
    """Submit structured field verification evidence."""
    
    case = db.get(models.Case, case_id)
    if not case:
        raise ValueError("Case not found")

    verification = models.FieldVerification(
        verification_id=str(uuid.uuid4()),
        case_id=case_id,
        surveyor_id=surveyor_id,
        timestamp=datetime.now(timezone.utc),
        location_lat=lat,
        location_lon=lon,
        observations=observations,
        photo_refs=photo_refs,
        measurement_refs=measurement_refs,
        findings_summary=findings_summary,
        verification_status=verification_status
    )
    db.add(verification)

    # Update case status
    if case.status == models.CaseStatus.FIELD_VERIFICATION:
        case.status = models.CaseStatus.AUTHORITY_REVIEW
        db.add(case)

    # Log to audit trail
    audit_service.append_event(
        db, case_id, audit_service.EVENT_FIELD_VERIFICATION,
        data={
            "verification_id": verification.verification_id,
            "status": verification_status.value
        },
        actor_id=surveyor_id, actor_role=models.UserRole.SURVEYOR_FIELD.value
    )

    db.commit()
    db.refresh(verification)
    return verification
