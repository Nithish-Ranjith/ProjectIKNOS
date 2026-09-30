"""
backend/app/decision_routes.py — FastAPI endpoints that expose the decision engine.

Endpoints:
  POST /engine/run           — Run the full decision engine for a parcel trigger
  POST /engine/lock-check    — Periodic TTL check on an existing lock
  POST /engine/approve       — Step 1: create authenticated approval (gates the write)
  POST /engine/record-update — Step 2: apply record update against an approval
  GET  /engine/case/{case_id}/trace — Retrieve full reasoning trace for a case
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from . import auth, models
from .database import get_db
from . import decision_engine as de

router = APIRouter(prefix="/engine", tags=["Decision Engine"])


# ---------------------------------------------------------------------------
# Request / Response Pydantic models
# ---------------------------------------------------------------------------

class RecordAvailabilityIn(BaseModel):
    ror_present: bool
    registration_present: bool
    mutation_status: str = "none"


class SpatialSignalsIn(BaseModel):
    area_diff_pct: float
    boundary_shift_m: float
    parcel_area_sqm: float
    gnss_uncertainty_m: float = 3.5          # default: STANDARD_GNSS midpoint
    model_iou: Optional[float] = None        # TODO(ML): fill from U-Net output
    temporal_instability: Optional[float] = None  # TODO(ML): fill from Sentinel-2


class GrievanceContextIn(BaseModel):
    filer_id: str
    parcel_id: str
    evidence_items: List[str] = Field(default_factory=list)
    recent_grievance_count: int = 0


class EngineRunRequest(BaseModel):
    internal_parcel_key: str
    trigger_source: str                       # TriggerSource enum value
    records: RecordAvailabilityIn
    spatial: SpatialSignalsIn
    positioning_quality: str = "STANDARD_GNSS"
    active_lock_id: Optional[str] = None
    lock_created_at: Optional[datetime] = None
    grievance: Optional[GrievanceContextIn] = None


class LockCheckRequest(BaseModel):
    lock_id: str
    lock_created_at: datetime
    ttl_hours: int = de.DEFAULT_LOCK_TTL_HOURS


class ApprovalRequest(BaseModel):
    case_id: str
    update_class: str                        # UpdateClass enum value
    reason: str


class RecordUpdateRequest(BaseModel):
    case_id: str
    approval_id: str
    approval_signature_hash: str            # from the ApprovalRecord returned by /approve
    approver_id: str
    approver_tier: int
    update_class: str
    reason: str
    target_record_ref: str
    changes: List[Dict[str, Any]]           # [{field, old_value, new_value}]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/run")
def run_engine(
    body: EngineRunRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Run the full decision engine for a parcel trigger event.

    - Handles all trigger sources (satellite, citizen grievance, drone survey, etc.)
    - Citizen grievances routed through validity gate before analysis
    - Returns full reasoning trace, priority score, lock, update class, authority tier
    """
    try:
        trigger = de.TriggerSource(body.trigger_source)
    except ValueError:
        raise HTTPException(400, f"Invalid trigger_source: {body.trigger_source}. "
                                  f"Valid values: {[t.value for t in de.TriggerSource]}")

    records = de.RecordAvailability(
        ror_present=body.records.ror_present,
        registration_present=body.records.registration_present,
        mutation_status=body.records.mutation_status,
        record_gap_count=0,   # computed inside engine
    )
    spatial = de.SpatialSignals(
        area_diff_pct=body.spatial.area_diff_pct,
        boundary_shift_m=body.spatial.boundary_shift_m,
        parcel_area_sqm=body.spatial.parcel_area_sqm,
        gnss_uncertainty_m=body.spatial.gnss_uncertainty_m,
        model_iou=body.spatial.model_iou,
        temporal_instability=body.spatial.temporal_instability,
    )
    grievance = None
    if body.grievance:
        grievance = de.GrievanceContext(
            filer_id=body.grievance.filer_id,
            parcel_id=body.grievance.parcel_id,
            evidence_items=body.grievance.evidence_items,
            recent_grievance_count=body.grievance.recent_grievance_count,
        )

    inp = de.EngineInput(
        internal_parcel_key=body.internal_parcel_key,
        trigger_source=trigger,
        records=records,
        spatial=spatial,
        positioning_quality=body.positioning_quality,
        active_lock_id=body.active_lock_id,
        lock_created_at=body.lock_created_at,
        grievance=grievance,
    )

    result = de.run(inp)

    return {
        "case_id": result.case_id,
        "parcel_key": result.parcel_key,
        "trigger": result.trigger.value,
        "outcome": result.outcome.value,
        "priority_score": result.priority_score,
        "confidence_score": result.confidence_score,
        "lock_id": result.lock_id,
        "lock_expires_at": result.lock_expires_at.isoformat() if result.lock_expires_at else None,
        "required_authority_tier": result.required_authority_tier.value if result.required_authority_tier else None,
        "update_class": result.update_class.value if result.update_class else None,
        "reasoning_trace": result.reasoning_trace,
        "audit_entry": {
            "entry_id": result.audit_entry.entry_id,
            "event_type": result.audit_entry.event_type,
            "hash_chain_entry": result.audit_entry.hash_chain_entry,
            "timestamp": result.audit_entry.timestamp.isoformat(),
        } if result.audit_entry else None,
        "error": result.error,
    }


@router.post("/lock-check")
def check_lock_ttl(
    body: LockCheckRequest,
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Periodic TTL check on an open case lock.
    Called by the backend scheduler — not by the mobile client directly.
    Returns whether lock is expired or needs supervisor escalation.
    """
    expired, needs_escalation = de._check_lock_ttl(body.lock_created_at, body.ttl_hours)
    return {
        "lock_id": body.lock_id,
        "is_expired": expired,
        "needs_escalation": needs_escalation,
        "action": (
            "FORCE_RELEASE_AND_NOTIFY_SUPERVISOR" if needs_escalation
            else "RELEASE" if expired
            else "STILL_VALID"
        ),
    }


@router.post("/approve")
def create_approval(
    body: ApprovalRequest,
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Step 1 of the mandatory write gate.
    Creates an authenticated approval record with a digital signature.
    The approval_id and signature_hash returned MUST be passed to /record-update.
    Approval must precede the record write — this order is enforced by /record-update.
    """
    try:
        update_class = de.UpdateClass(body.update_class)
    except ValueError:
        raise HTTPException(400, f"Invalid update_class: {body.update_class}")

    # Tier check: ownership or high-priority update types require SENIOR_FIELD or above
    officer_tier = _resolve_officer_tier(current_user)
    if update_class in de.TIER2_REQUIRED_CLASSES:
        if officer_tier < de.AuthorityTier.TIER_2:
            raise HTTPException(
                403,
                f"Update class '{update_class.value}' requires a TIER_2 (senior) officer. "
                f"Your tier is {officer_tier.value}."
            )

    approval = de.create_approval(
        case_id=body.case_id,
        approver_id=current_user.user_id,
        approver_tier=officer_tier,
        update_class=update_class,
        reason=body.reason,
    )
    return {
        "approval_id": approval.approval_id,
        "case_id": approval.case_id,
        "approver_id": approval.approver_id,
        "approver_tier": approval.approver_tier.value,
        "update_class": approval.update_class.value,
        "signature_hash": approval.signature_hash,
        "timestamp": approval.timestamp.isoformat(),
        "note": "Pass approval_id and signature_hash to /engine/record-update to complete the write",
    }


@router.post("/record-update")
def apply_record_update(
    body: RecordUpdateRequest,
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Step 2: apply the authorized record update.
    REQUIRES a valid approval from /engine/approve.
    Signature gates the write — no approval = no write.
    Returns update_id, version_id, and the next hash-chain entry.
    """
    try:
        update_class = de.UpdateClass(body.update_class)
        approver_tier = de.AuthorityTier(body.approver_tier)
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Reconstruct minimal approval record to pass into the engine
    # (in production this would be fetched from DB by approval_id)
    from datetime import datetime as _dt, timezone as _tz
    approval = de.ApprovalRecord(
        approval_id=body.approval_id,
        case_id=body.case_id,
        approver_id=body.approver_id,
        approver_tier=approver_tier,
        update_class=update_class,
        reason=body.reason,
        timestamp=_dt.now(_tz.utc),
        signature_hash=body.approval_signature_hash,
    )

    update, version = de.apply_record_update(
        approval=approval,
        target_record_ref=body.target_record_ref,
        changes=body.changes,
    )

    # Build the next audit chain link
    audit = de.build_audit_entry_for_update(update, version, current_user.user_id, current_user.role.value)

    return {
        "update_id": update.update_id,
        "version_id": version.version_id,
        "approval_id": update.approval_id,
        "update_class": update.update_class.value,
        "changes_applied": update.changes,
        "applied_at": update.applied_at.isoformat(),
        "hash_chain_entry": audit.hash_chain_entry,
        "audit_entry_id": audit.entry_id,
    }


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _resolve_officer_tier(user: models.User) -> de.AuthorityTier:
    if user.role in (models.UserRole.SENIOR_FIELD, models.UserRole.ADMIN):
        return de.AuthorityTier.TIER_2
    return de.AuthorityTier.TIER_1
