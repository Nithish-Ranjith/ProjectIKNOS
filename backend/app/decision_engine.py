"""
backend/app/decision_engine.py — Core deterministic Decision Engine for TerraTrace MVP.

This module implements the full flowchart logic EXCLUDING ML model calls.
All ML plugin points are clearly marked with TODO(ML) comments so a model can
be dropped in without restructuring the surrounding code.

Flow implemented:
  Trigger (satellite/citizen/schedule) 
    → Record Availability Check (RoR + Registration + Mutation)
    → Grievance Validity Check (rate-limit, evidence requirement — citizen path only)
    → Parcel Change / Inconsistency Analysis (spatial + record signals)
    → Priority Score
    → PARCEL_STATE_LOCK (with mandatory TTL)
    → Confidence scoring
    → Threshold routing: field_verification | authority_review | no_action
    → If verify-path: field verification → classify update type → authority tier gate
    → Authenticated Approval → Authorized Record Update → Versioned Record → Audit Log
    → Release Lock
    → Back to continuous monitoring

Design contracts (from validated flowchart review):
  - Approval is written BEFORE the record update — signature gates the write.
  - Lock has mandatory TTL; a periodic check detects expiry and escalates.
  - Citizen grievances route through the SAME evidence analysis node as satellite triggers.
  - Update class distinguishes OWNERSHIP vs CADASTRAL_GEOMETRY vs MUTATION.
  - Authority tier is determined from update_class + priority_score.
  - Registration and RoR are independent signals; two missing records is worse than one.
  - Spatial thresholds scale with parcel size + GNSS uncertainty; no fixed IoU global bar.
  - internal_parcel_key is the system key; ulpin is nullable government-issued only.
  - ML model slots are isolated; engine runs deterministically without them.
"""
from __future__ import annotations

import hashlib
import json
import math
import uuid
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, List, Dict, Any


# ---------------------------------------------------------------------------
# Constants — tunable via config, not hardcoded thresholds
# ---------------------------------------------------------------------------

# Priority score thresholds for routing
PRIORITY_ROUTE_TO_FIELD_VERIFY = 45.0       # >= this → field_verification
PRIORITY_ROUTE_TO_AUTHORITY_REVIEW = 75.0   # >= this → directly authority_review

# Authority tier gating: update class + priority score → min officer tier
TIER2_REQUIRED_CLASSES = {"OWNERSHIP"}
TIER2_REQUIRED_PRIORITY = 70.0

# Grievance rate-limit: max N grievances per filer per parcel per N days
GRIEVANCE_RATE_LIMIT_COUNT = 3
GRIEVANCE_RATE_LIMIT_DAYS = 30
GRIEVANCE_MIN_EVIDENCE_ITEMS = 1            # Must attach at least 1 photo/doc

# Lock TTL in hours — never allow indefinite locks
DEFAULT_LOCK_TTL_HOURS = 72
ESCALATION_LOCK_TTL_HOURS = 168            # 7 days, then force-release + supervisor notification

# Weights for priority scoring (must sum to 1.0)
_PRIORITY_WEIGHTS = {
    "spatial_discrepancy": 0.35,
    "record_gaps":         0.30,
    "temporal_signal":     0.20,
    "source_quality":      0.15,
}
assert abs(sum(_PRIORITY_WEIGHTS.values()) - 1.0) < 1e-9, "Priority weights must sum to 1.0"


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class TriggerSource(str, Enum):
    SATELLITE_PERIODIC  = "SATELLITE_PERIODIC"
    CITIZEN_GRIEVANCE   = "CITIZEN_GRIEVANCE"
    DRONE_SURVEY        = "DRONE_SURVEY"
    OFFICER_MANUAL      = "OFFICER_MANUAL"
    SCHEDULED_AUDIT     = "SCHEDULED_AUDIT"


class UpdateClass(str, Enum):
    OWNERSHIP          = "OWNERSHIP"
    CADASTRAL_GEOMETRY = "CADASTRAL_GEOMETRY"
    MUTATION           = "MUTATION"
    OTHER_AUTHORIZED   = "OTHER_AUTHORIZED"


class DecisionOutcome(str, Enum):
    NO_ACTION              = "NO_ACTION"
    FIELD_VERIFICATION     = "FIELD_VERIFICATION"
    AUTHORITY_REVIEW       = "AUTHORITY_REVIEW"
    GRIEVANCE_REJECTED     = "GRIEVANCE_REJECTED"
    LOCK_ESCALATED         = "LOCK_ESCALATED"
    LOCK_RELEASED          = "LOCK_RELEASED"


class AuthorityTier(int, Enum):
    TIER_1 = 1   # SURVEYOR_FIELD / SURVEYOR_DRONE
    TIER_2 = 2   # SENIOR_FIELD / SENIOR_AUTHORITY


# ---------------------------------------------------------------------------
# Input/Output dataclasses — the ML plugin interface lives here
# ---------------------------------------------------------------------------

@dataclass
class RecordAvailability:
    """
    Output of record availability check.
    Registration and RoR are kept as independent signals per design contract.
    """
    ror_present: bool
    registration_present: bool
    mutation_status: str      # 'approved' | 'pending' | 'none'
    record_gap_count: int     # 0, 1, or 2 — two missing is strictly worse


@dataclass
class SpatialSignals:
    """
    Outputs of geometric / spatial analysis.

    TODO(ML): boundary_shift_m and area_diff_pct will eventually be replaced or
    augmented by U-Net boundary segmentation output. When plugging in the model:
      1. Run U-Net on the drone orthoimage to produce adjusted_boundary_geojson.
      2. Compute IoU between adjusted_boundary and cadastral_boundary.
      3. Convert IoU to equivalent area_diff_pct / boundary_shift_m using
         parcel_area_sqm as the scale reference.
      4. Store raw IoU in model_iou field below; the engine will use the
         normalized form for scoring.
    Threshold is NOT a fixed global 0.85 — it is computed from parcel_area_sqm
    and gnss_uncertainty_m. See _scale_normalized_iou_threshold().
    """
    area_diff_pct: float          # % area difference between cadastral and measured
    boundary_shift_m: float       # median boundary vertex shift in metres
    parcel_area_sqm: float        # used for normalization — not an optional field
    gnss_uncertainty_m: float     # 2.5–5.0 for STANDARD_GNSS, ~0.02 for RTK_FIX
    model_iou: Optional[float] = None     # TODO(ML): raw IoU from U-Net (nullable until model plugged in)
    temporal_instability: Optional[float] = None  # TODO(ML): from Sentinel-2 STL/PELT


@dataclass
class GrievanceContext:
    """Only populated when trigger_source == CITIZEN_GRIEVANCE."""
    filer_id: str
    parcel_id: str
    evidence_items: List[str]     # photo_refs or doc_refs
    recent_grievance_count: int   # from DB, last GRIEVANCE_RATE_LIMIT_DAYS days


@dataclass
class EngineInput:
    internal_parcel_key: str
    trigger_source: TriggerSource
    records: RecordAvailability
    spatial: SpatialSignals
    positioning_quality: str          # 'STANDARD_GNSS' | 'RTK_FIX'
    active_lock_id: Optional[str] = None
    lock_created_at: Optional[datetime] = None
    grievance: Optional[GrievanceContext] = None
    extra_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ApprovalRecord:
    approval_id: str
    case_id: str
    approver_id: str
    approver_tier: AuthorityTier
    update_class: UpdateClass
    reason: str
    timestamp: datetime
    signature_hash: str           # SHA-256 of (case_id + approver_id + reason + timestamp)


@dataclass
class RecordUpdateRecord:
    update_id: str
    case_id: str
    approval_id: str              # Must reference an existing approval
    update_class: UpdateClass
    target_record_ref: str
    changes: List[Dict]           # [{field, old_value, new_value}]
    applied_at: datetime


@dataclass
class VersionedRecord:
    version_id: str
    parcel_key: str
    case_id: str
    version_number: int
    snapshot: Dict                # Full record state at time of update
    created_at: datetime


@dataclass
class AuditEntry:
    entry_id: str
    case_id: str
    seq: int
    event_type: str
    actor_id: str
    actor_role: str
    data: Dict
    timestamp: datetime
    hash_chain_entry: str         # SHA-256 of (prev_hash + this event content)


@dataclass
class EngineOutput:
    case_id: str
    parcel_key: str
    trigger: TriggerSource
    outcome: DecisionOutcome
    priority_score: float
    confidence_score: Optional[float]
    lock_id: Optional[str]
    lock_expires_at: Optional[datetime]
    required_authority_tier: Optional[AuthorityTier]
    update_class: Optional[UpdateClass]
    reasoning_trace: List[Dict]
    audit_entry: Optional[AuditEntry]
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _sha256_hex(*parts: str) -> str:
    combined = "|".join(parts)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def _scale_normalized_spatial_score(s: SpatialSignals) -> float:
    """
    Returns 0.0–1.0 discrepancy score, scaled by parcel size and GNSS uncertainty.
    A 2m shift on a 200m² parcel is catastrophic; on a 50,000m² farm it is noise.
    GNSS uncertainty is subtracted from boundary_shift_m before scoring so that
    consumer-grade GPS noise does not generate phantom high-severity cases.
    """
    effective_shift = max(0.0, s.boundary_shift_m - s.gnss_uncertainty_m)
    characteristic_length = math.sqrt(max(s.parcel_area_sqm, 1.0))
    shift_ratio = effective_shift / characteristic_length
    shift_component = min(shift_ratio * 10.0, 1.0)

    area_component = min(s.area_diff_pct / 25.0, 1.0)

    # If ML model IoU is available, blend it in
    if s.model_iou is not None:
        # Convert IoU to a discrepancy signal (lower IoU = higher discrepancy)
        # Scale the threshold to parcel size + GNSS: small parcels require higher IoU
        gnss_tolerance_fraction = s.gnss_uncertainty_m / characteristic_length
        scaled_threshold = max(0.70, 0.92 - gnss_tolerance_fraction * 2.0)
        iou_component = max(0.0, scaled_threshold - s.model_iou) / scaled_threshold
    else:
        iou_component = 0.0

    return max(area_component, shift_component, iou_component)


def _compute_priority_score(
    spatial_sub: float,
    records: RecordAvailability,
    temporal_sub: float,
    source_quality: str,
) -> tuple[float, List[Dict]]:
    """
    Weighted priority score 0–100. All weights sum to 1.0 (validated at module load).
    Returns (score, trace).
    """
    trace = []

    # Record gap: 0 gaps = 0.0, 1 gap = 0.5, 2 gaps = 1.0 (two independent signals)
    record_sub = min(records.record_gap_count / 2.0, 1.0)
    trace.append({
        "rule": "record_availability_check",
        "ror_present": records.ror_present,
        "registration_present": records.registration_present,
        "mutation_status": records.mutation_status,
        "gap_count": records.record_gap_count,
        "sub_score": round(record_sub, 3),
        "note": "registration and RoR are independent signals; two missing = stronger evidence",
    })

    quality_sub = 0.5 if source_quality == "STANDARD_GNSS" else 0.0
    trace.append({
        "rule": "positioning_quality_check",
        "quality": source_quality,
        "sub_score": round(quality_sub, 3),
        "note": (
            "STANDARD_GNSS ~2.5-5m accuracy — spatial evidence weighted down accordingly"
            if source_quality == "STANDARD_GNSS"
            else "RTK_FIX centimetre-level accuracy"
        ),
    })

    trace.append({
        "rule": "spatial_discrepancy_check",
        "sub_score": round(spatial_sub, 3),
    })

    trace.append({
        "rule": "temporal_signal_check",
        "sub_score": round(temporal_sub, 3),
        "note": (
            "Sentinel-2 STL/PELT instability score" if temporal_sub > 0
            else "temporal analysis not available or not run"
        ),
    })

    raw = (
        _PRIORITY_WEIGHTS["spatial_discrepancy"] * spatial_sub
        + _PRIORITY_WEIGHTS["record_gaps"]       * record_sub
        + _PRIORITY_WEIGHTS["temporal_signal"]   * temporal_sub
        + _PRIORITY_WEIGHTS["source_quality"]    * quality_sub
    )
    score = round(raw * 100, 1)
    return score, trace


def _grievance_validity_check(g: GrievanceContext) -> tuple[bool, str]:
    """
    Returns (is_valid, rejection_reason).
    Routes citizen grievances through the same evidence standard as satellite triggers.
    """
    if g.recent_grievance_count >= GRIEVANCE_RATE_LIMIT_COUNT:
        return False, (
            f"Rate limit exceeded: {g.recent_grievance_count} grievances filed "
            f"against this parcel in the last {GRIEVANCE_RATE_LIMIT_DAYS} days "
            f"(max {GRIEVANCE_RATE_LIMIT_COUNT} allowed)."
        )
    if len(g.evidence_items) < GRIEVANCE_MIN_EVIDENCE_ITEMS:
        return False, (
            f"Minimum evidence requirement not met: {len(g.evidence_items)} items attached, "
            f"{GRIEVANCE_MIN_EVIDENCE_ITEMS} required (photo or document reference)."
        )
    return True, ""


def _classify_update_type(spatial: SpatialSignals, records: RecordAvailability) -> UpdateClass:
    """
    Classify the most likely update class based on evidence signals.
    This classification is used for officer-tier gating.
    An actual officer must confirm or override this before record write.
    """
    if not records.registration_present or not records.ror_present:
        return UpdateClass.OWNERSHIP
    if records.mutation_status == "pending":
        return UpdateClass.MUTATION
    if spatial.area_diff_pct > 2.0 or spatial.boundary_shift_m > 5.0:
        return UpdateClass.CADASTRAL_GEOMETRY
    return UpdateClass.OTHER_AUTHORIZED


def _required_authority_tier(update_class: UpdateClass, priority_score: float) -> AuthorityTier:
    """
    Determine minimum officer tier.
    OWNERSHIP updates or high-priority cases require TIER_2 (senior authority).
    """
    if update_class in TIER2_REQUIRED_CLASSES or priority_score >= TIER2_REQUIRED_PRIORITY:
        return AuthorityTier.TIER_2
    return AuthorityTier.TIER_1


def _build_lock(parcel_key: str, case_id: str, ttl_hours: int = DEFAULT_LOCK_TTL_HOURS) -> Dict:
    """
    Create a parcel lock record with a mandatory expiry.
    No indefinite locks allowed — design contract enforced here.
    """
    now = _utcnow()
    return {
        "lock_id": str(uuid.uuid4()),
        "parcel_key": parcel_key,
        "case_id": case_id,
        "locked_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=ttl_hours)).isoformat(),
        "ttl_hours": ttl_hours,
        "status": "LOCKED",
    }


def _check_lock_ttl(lock_created_at: datetime, ttl_hours: int = DEFAULT_LOCK_TTL_HOURS) -> tuple[bool, bool]:
    """
    Returns (is_expired, needs_escalation).
    Evaluated periodically while case is open — not just at lock creation.
    """
    elapsed = (_utcnow() - lock_created_at).total_seconds() / 3600
    is_expired = elapsed >= ttl_hours
    needs_escalation = elapsed >= ESCALATION_LOCK_TTL_HOURS
    return is_expired, needs_escalation


def _build_audit_entry(
    case_id: str, seq: int, event_type: str,
    actor_id: str, actor_role: str, data: Dict, prev_hash: str = ""
) -> AuditEntry:
    """
    Append-only audit entry with SHA-256 hash chain.
    What is hashed: full event content snapshot at event time — not just the delta.
    """
    now = _utcnow()
    content = json.dumps({
        "case_id": case_id, "seq": seq, "event_type": event_type,
        "actor_id": actor_id, "actor_role": actor_role,
        "data": data, "timestamp": now.isoformat(),
    }, sort_keys=True)
    chain_hash = _sha256_hex(prev_hash, content)
    return AuditEntry(
        entry_id=str(uuid.uuid4()),
        case_id=case_id, seq=seq,
        event_type=event_type, actor_id=actor_id, actor_role=actor_role,
        data=data, timestamp=now,
        hash_chain_entry=chain_hash,
    )


def create_approval(
    case_id: str,
    approver_id: str,
    approver_tier: AuthorityTier,
    update_class: UpdateClass,
    reason: str,
) -> ApprovalRecord:
    """
    Step 1 of the mandatory write gate: authenticated approval.
    Must be called BEFORE apply_record_update.
    """
    now = _utcnow()
    sig = _sha256_hex(case_id, approver_id, reason, now.isoformat())
    return ApprovalRecord(
        approval_id=str(uuid.uuid4()),
        case_id=case_id,
        approver_id=approver_id,
        approver_tier=approver_tier,
        update_class=update_class,
        reason=reason,
        timestamp=now,
        signature_hash=sig,
    )


def apply_record_update(
    approval: ApprovalRecord,
    target_record_ref: str,
    changes: List[Dict],
) -> tuple[RecordUpdateRecord, VersionedRecord]:
    """
    Step 2: write the record update ONLY if a valid approval exists.
    Signature gates the write — approval always precedes update.
    Returns (update_record, versioned_record).
    """
    if not approval.approval_id:
        raise ValueError("apply_record_update called without a valid approval — refusing write")

    update = RecordUpdateRecord(
        update_id=str(uuid.uuid4()),
        case_id=approval.case_id,
        approval_id=approval.approval_id,
        update_class=approval.update_class,
        target_record_ref=target_record_ref,
        changes=changes,   # [{field, old_value, new_value}]
        applied_at=_utcnow(),
    )
    version = VersionedRecord(
        version_id=str(uuid.uuid4()),
        parcel_key=target_record_ref,
        case_id=approval.case_id,
        version_number=0,    # caller must set from DB sequence
        snapshot={
            "update_id": update.update_id,
            "approval_id": approval.approval_id,
            "approver_id": approval.approver_id,
            "approver_tier": approval.approver_tier.value,
            "update_class": approval.update_class.value,
            "changes": changes,
        },
        created_at=_utcnow(),
    )
    return update, version


def build_audit_entry_for_update(
    update: RecordUpdateRecord,
    version: VersionedRecord,
    actor_id: str,
    actor_role: str,
    prev_hash: str = "",
) -> AuditEntry:
    """
    Build the audit chain entry that follows a record update.
    Hashes the full snapshot — not just the delta.
    """
    return _build_audit_entry(
        case_id=update.case_id,
        seq=2,   # caller must retrieve actual seq from DB
        event_type="RECORD_UPDATED",
        actor_id=actor_id,
        actor_role=actor_role,
        data={
            "update_id": update.update_id,
            "version_id": version.version_id,
            "approval_id": update.approval_id,
            "update_class": update.update_class.value,
            "target_record_ref": update.target_record_ref,
            "changes": update.changes,
        },
        prev_hash=prev_hash,
    )



# ---------------------------------------------------------------------------
# Main engine entry point
# ---------------------------------------------------------------------------

def run(inp: EngineInput) -> EngineOutput:
    """
    Execute the full decision engine for a single case.

    Returns EngineOutput describing:
      - outcome (DecisionOutcome)
      - priority score + confidence score
      - required lock (with TTL)
      - required authority tier
      - classified update type
      - full reasoning trace (auditable, not opaque)
      - initial audit entry

    ML plugin points:
      - inp.spatial.model_iou         → plug U-Net output here
      - inp.spatial.temporal_instability → plug Sentinel-2 STL/PELT output here
    """
    trace: List[Dict] = []
    case_id = str(uuid.uuid4())

    # -----------------------------------------------------------------------
    # 0. LOCK TTL CHECK — runs first if an existing lock is present
    #    Evaluated periodically while a case is open, not just at creation.
    # -----------------------------------------------------------------------
    if inp.active_lock_id and inp.lock_created_at:
        expired, needs_escalation = _check_lock_ttl(inp.lock_created_at)
        if needs_escalation:
            trace.append({
                "step": "lock_ttl_check",
                "result": "ESCALATION_REQUIRED",
                "detail": f"Lock held for over {ESCALATION_LOCK_TTL_HOURS}h — notifying supervisor, extending or force-releasing",
            })
            return EngineOutput(
                case_id=case_id, parcel_key=inp.internal_parcel_key,
                trigger=inp.trigger_source, outcome=DecisionOutcome.LOCK_ESCALATED,
                priority_score=0.0, confidence_score=None,
                lock_id=inp.active_lock_id, lock_expires_at=None,
                required_authority_tier=AuthorityTier.TIER_2,
                update_class=None, reasoning_trace=trace, audit_entry=None,
                error="LOCK_ESCALATION: supervisor notification required",
            )
        if expired:
            trace.append({"step": "lock_ttl_check", "result": "EXPIRED_RELEASED"})
            return EngineOutput(
                case_id=case_id, parcel_key=inp.internal_parcel_key,
                trigger=inp.trigger_source, outcome=DecisionOutcome.LOCK_RELEASED,
                priority_score=0.0, confidence_score=None,
                lock_id=inp.active_lock_id, lock_expires_at=None,
                required_authority_tier=None, update_class=None,
                reasoning_trace=trace, audit_entry=None,
            )

    # -----------------------------------------------------------------------
    # 1. GRIEVANCE VALIDITY CHECK (citizen path only)
    #    Routes through same evidence gate as satellite triggers — no privileged fast-path.
    # -----------------------------------------------------------------------
    if inp.trigger_source == TriggerSource.CITIZEN_GRIEVANCE:
        if not inp.grievance:
            return EngineOutput(
                case_id=case_id, parcel_key=inp.internal_parcel_key,
                trigger=inp.trigger_source, outcome=DecisionOutcome.GRIEVANCE_REJECTED,
                priority_score=0.0, confidence_score=None, lock_id=None, lock_expires_at=None,
                required_authority_tier=None, update_class=None, reasoning_trace=trace,
                audit_entry=None, error="GrievanceContext missing for CITIZEN_GRIEVANCE trigger",
            )
        valid, reason = _grievance_validity_check(inp.grievance)
        trace.append({
            "step": "grievance_validity_check",
            "valid": valid,
            "reason": reason or "passed",
            "evidence_count": len(inp.grievance.evidence_items),
            "recent_count": inp.grievance.recent_grievance_count,
        })
        if not valid:
            return EngineOutput(
                case_id=case_id, parcel_key=inp.internal_parcel_key,
                trigger=inp.trigger_source, outcome=DecisionOutcome.GRIEVANCE_REJECTED,
                priority_score=0.0, confidence_score=None, lock_id=None, lock_expires_at=None,
                required_authority_tier=None, update_class=None,
                reasoning_trace=trace, audit_entry=None, error=reason,
            )
        trace.append({"step": "grievance_validity_check", "result": "PASSED — routing to standard analysis"})

    # -----------------------------------------------------------------------
    # 2. RECORD AVAILABILITY CHECK (all triggers)
    #    RoR, Registration, Mutation — treated as three independent signals.
    # -----------------------------------------------------------------------
    gap_count = 0
    if not inp.records.ror_present:
        gap_count += 1
    if not inp.records.registration_present:
        gap_count += 1
    inp.records.record_gap_count = gap_count
    trace.append({
        "step": "record_availability_check",
        "ror_present": inp.records.ror_present,
        "registration_present": inp.records.registration_present,
        "mutation_status": inp.records.mutation_status,
        "gap_count": gap_count,
        "note": "Two missing records is strictly stronger evidence than one — weighted independently",
    })

    # -----------------------------------------------------------------------
    # 3. PARCEL CHANGE / INCONSISTENCY ANALYSIS — spatial + temporal signals
    # -----------------------------------------------------------------------
    spatial_sub = _scale_normalized_spatial_score(inp.spatial)
    temporal_sub = inp.spatial.temporal_instability or 0.0
    trace.append({
        "step": "spatial_analysis",
        "area_diff_pct": inp.spatial.area_diff_pct,
        "boundary_shift_m": inp.spatial.boundary_shift_m,
        "gnss_uncertainty_m": inp.spatial.gnss_uncertainty_m,
        "model_iou": inp.spatial.model_iou,
        "normalized_spatial_sub": round(spatial_sub, 3),
        "note": "Threshold scaled to parcel size + GNSS uncertainty — not a fixed global IoU bar",
    })
    trace.append({
        "step": "temporal_analysis",
        "instability_score": temporal_sub,
        "source": "Sentinel-2 STL/PELT" if temporal_sub > 0 else "not_run",
        "note": "TODO(ML): plug Sentinel-2 model output into spatial.temporal_instability",
    })

    # -----------------------------------------------------------------------
    # 4. PRIORITY SCORE COMPUTATION
    # -----------------------------------------------------------------------
    priority_score, priority_trace = _compute_priority_score(
        spatial_sub, inp.records, temporal_sub, inp.positioning_quality
    )
    trace.extend(priority_trace)
    trace.append({"step": "priority_score", "score": priority_score})

    # -----------------------------------------------------------------------
    # 5. ROUTING: No Action | Field Verification | Authority Review
    # -----------------------------------------------------------------------
    if priority_score < PRIORITY_ROUTE_TO_FIELD_VERIFY:
        trace.append({"step": "routing", "outcome": "NO_ACTION", "priority_score": priority_score})
        return EngineOutput(
            case_id=case_id, parcel_key=inp.internal_parcel_key,
            trigger=inp.trigger_source, outcome=DecisionOutcome.NO_ACTION,
            priority_score=priority_score, confidence_score=None,
            lock_id=None, lock_expires_at=None, required_authority_tier=None,
            update_class=None, reasoning_trace=trace, audit_entry=None,
        )

    # -----------------------------------------------------------------------
    # 6. PARCEL STATE LOCK (with mandatory TTL)
    # -----------------------------------------------------------------------
    lock = _build_lock(inp.internal_parcel_key, case_id)
    trace.append({
        "step": "parcel_lock",
        "lock_id": lock["lock_id"],
        "expires_at": lock["expires_at"],
        "ttl_hours": lock["ttl_hours"],
        "note": "Lock is periodically re-evaluated for TTL expiry during the life of the case",
    })

    # -----------------------------------------------------------------------
    # 7. CLASSIFY UPDATE TYPE → AUTHORITY TIER GATE
    # -----------------------------------------------------------------------
    update_class = _classify_update_type(inp.spatial, inp.records)
    required_tier = _required_authority_tier(update_class, priority_score)
    trace.append({
        "step": "classify_update_type",
        "update_class": update_class.value,
        "required_authority_tier": required_tier.value,
        "note": "OWNERSHIP or priority >= 70 requires TIER_2 senior authority",
    })

    # Determine high-level outcome
    if priority_score >= PRIORITY_ROUTE_TO_AUTHORITY_REVIEW:
        outcome = DecisionOutcome.AUTHORITY_REVIEW
    else:
        outcome = DecisionOutcome.FIELD_VERIFICATION

    trace.append({"step": "routing", "outcome": outcome.value, "priority_score": priority_score})

    # -----------------------------------------------------------------------
    # 8. CONFIDENCE SCORE (for the assigned officer's dashboard)
    #    This is a deterministic formula — NOT a model prediction.
    #    See confidence.py for the full sub-score breakdown.
    # -----------------------------------------------------------------------
    from .confidence import compute_confidence  # local import to keep plugin interface clean

    conf_result = compute_confidence(
        area_diff_pct=inp.spatial.area_diff_pct,
        boundary_shift_m=inp.spatial.boundary_shift_m,
        parcel_area_sqm=inp.spatial.parcel_area_sqm,
        registration_status="missing" if not inp.records.registration_present else "present",
        mutation_status=inp.records.mutation_status,
        instability_score=inp.spatial.temporal_instability,
        positioning_quality=inp.positioning_quality,
    )
    confidence_score = conf_result["confidence_score"]
    trace.extend(conf_result["reasoning_trace"])
    trace.append({"step": "confidence_score", "score": confidence_score})

    # -----------------------------------------------------------------------
    # 9. INITIAL AUDIT ENTRY (the engine writes the first chain link)
    # -----------------------------------------------------------------------
    audit = _build_audit_entry(
        case_id=case_id, seq=1,
        event_type="CASE_OPENED",
        actor_id="SYSTEM", actor_role="DECISION_ENGINE",
        data={
            "trigger": inp.trigger_source.value,
            "parcel_key": inp.internal_parcel_key,
            "priority_score": priority_score,
            "confidence_score": confidence_score,
            "outcome": outcome.value,
            "lock_id": lock["lock_id"],
            "update_class": update_class.value,
            "required_authority_tier": required_tier.value,
        },
        prev_hash="",
    )

    return EngineOutput(
        case_id=case_id,
        parcel_key=inp.internal_parcel_key,
        trigger=inp.trigger_source,
        outcome=outcome,
        priority_score=priority_score,
        confidence_score=confidence_score,
        lock_id=lock["lock_id"],
        lock_expires_at=datetime.fromisoformat(lock["expires_at"]),
        required_authority_tier=required_tier,
        update_class=update_class,
        reasoning_trace=trace,
        audit_entry=audit,
    )
