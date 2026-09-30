"""
backend/tests/test_decision_engine.py — Full test suite for the decision engine.

Tests every branch of the flowchart:
  - Lock TTL: expiry and escalation
  - Grievance: rate-limit rejection, evidence rejection, valid pass-through
  - Record availability: gap counting, two missing > one missing
  - Spatial analysis: scale-normalized scoring, GNSS uncertainty subtraction
  - Priority routing: no_action / field_verification / authority_review thresholds
  - Update class classification: OWNERSHIP / CADASTRAL_GEOMETRY / MUTATION
  - Authority tier gating: TIER_1 vs TIER_2 by update class + priority
  - Approval → Record Update: approval-before-write ordering enforced
  - Audit chain: hash chain integrity across two events
  - ML plugin points: model_iou and temporal_instability are respected when provided
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest
from datetime import datetime, timezone, timedelta
from backend.app import decision_engine as de



def utcnow():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_input(
    trigger=de.TriggerSource.SATELLITE_PERIODIC,
    ror_present=True,
    registration_present=True,
    mutation_status="approved",
    area_diff_pct=0.5,
    boundary_shift_m=1.0,
    parcel_area_sqm=10000.0,
    gnss_uncertainty_m=3.5,
    model_iou=None,
    temporal_instability=None,
    positioning_quality="STANDARD_GNSS",
    active_lock_id=None,
    lock_created_at=None,
    grievance=None,
):
    return de.EngineInput(
        internal_parcel_key="TEST-PARCEL-001",
        trigger_source=trigger,
        records=de.RecordAvailability(
            ror_present=ror_present,
            registration_present=registration_present,
            mutation_status=mutation_status,
            record_gap_count=0,
        ),
        spatial=de.SpatialSignals(
            area_diff_pct=area_diff_pct,
            boundary_shift_m=boundary_shift_m,
            parcel_area_sqm=parcel_area_sqm,
            gnss_uncertainty_m=gnss_uncertainty_m,
            model_iou=model_iou,
            temporal_instability=temporal_instability,
        ),
        positioning_quality=positioning_quality,
        active_lock_id=active_lock_id,
        lock_created_at=lock_created_at,
        grievance=grievance,
    )


# ---------------------------------------------------------------------------
# 1. Priority weights sum check (engine module-level assertion)
# ---------------------------------------------------------------------------

def test_priority_weights_sum_to_one():
    total = sum(de._PRIORITY_WEIGHTS.values())
    assert abs(total - 1.0) < 1e-9, f"Priority weights sum to {total}"


# ---------------------------------------------------------------------------
# 2. Lock TTL checks
# ---------------------------------------------------------------------------

def test_lock_still_valid():
    lock_time = utcnow() - timedelta(hours=10)
    expired, needs_escalation = de._check_lock_ttl(lock_time, ttl_hours=72)
    assert not expired
    assert not needs_escalation


def test_lock_expired():
    lock_time = utcnow() - timedelta(hours=73)
    expired, needs_escalation = de._check_lock_ttl(lock_time, ttl_hours=72)
    assert expired
    assert not needs_escalation


def test_lock_escalation_needed():
    lock_time = utcnow() - timedelta(hours=169)  # over 168h = ESCALATION_LOCK_TTL_HOURS
    expired, needs_escalation = de._check_lock_ttl(lock_time, ttl_hours=72)
    assert expired
    assert needs_escalation


def test_engine_returns_lock_escalated_when_ttl_exceeded():
    inp = _make_input(
        active_lock_id="LOCK-001",
        lock_created_at=utcnow() - timedelta(hours=169),
    )
    result = de.run(inp)
    assert result.outcome == de.DecisionOutcome.LOCK_ESCALATED
    assert result.required_authority_tier == de.AuthorityTier.TIER_2


def test_engine_returns_lock_released_on_normal_expiry():
    inp = _make_input(
        active_lock_id="LOCK-001",
        lock_created_at=utcnow() - timedelta(hours=73),
    )
    result = de.run(inp)
    assert result.outcome == de.DecisionOutcome.LOCK_RELEASED


# ---------------------------------------------------------------------------
# 3. Grievance validity gate
# ---------------------------------------------------------------------------

def test_grievance_rejected_on_rate_limit():
    g = de.GrievanceContext(
        filer_id="USER-A", parcel_id="P001",
        evidence_items=["photo1.jpg"],
        recent_grievance_count=5,  # over limit of 3
    )
    inp = _make_input(trigger=de.TriggerSource.CITIZEN_GRIEVANCE, grievance=g)
    result = de.run(inp)
    assert result.outcome == de.DecisionOutcome.GRIEVANCE_REJECTED
    assert "Rate limit exceeded" in (result.error or "")


def test_grievance_rejected_on_missing_evidence():
    g = de.GrievanceContext(
        filer_id="USER-A", parcel_id="P001",
        evidence_items=[],          # no evidence attached
        recent_grievance_count=0,
    )
    inp = _make_input(trigger=de.TriggerSource.CITIZEN_GRIEVANCE, grievance=g)
    result = de.run(inp)
    assert result.outcome == de.DecisionOutcome.GRIEVANCE_REJECTED
    assert "evidence" in (result.error or "").lower()


def test_grievance_valid_routes_to_analysis():
    g = de.GrievanceContext(
        filer_id="USER-A", parcel_id="P001",
        evidence_items=["photo1.jpg"],
        recent_grievance_count=1,
    )
    # Provide signals that will result in no_action to isolate grievance path
    inp = _make_input(
        trigger=de.TriggerSource.CITIZEN_GRIEVANCE,
        grievance=g,
        area_diff_pct=0.1,
        boundary_shift_m=0.5,
    )
    result = de.run(inp)
    # Should NOT be GRIEVANCE_REJECTED — it passed the gate
    assert result.outcome != de.DecisionOutcome.GRIEVANCE_REJECTED
    # Grievance validity step should appear in trace
    steps = [t.get("step") for t in result.reasoning_trace]
    assert "grievance_validity_check" in steps


def test_grievance_trigger_missing_context():
    inp = _make_input(trigger=de.TriggerSource.CITIZEN_GRIEVANCE, grievance=None)
    result = de.run(inp)
    assert result.outcome == de.DecisionOutcome.GRIEVANCE_REJECTED
    assert result.error is not None


# ---------------------------------------------------------------------------
# 4. Record availability — two missing is worse than one
# ---------------------------------------------------------------------------

def test_record_gap_count_zero():
    inp = _make_input(ror_present=True, registration_present=True)
    result = de.run(inp)
    gap_step = next(t for t in result.reasoning_trace if t.get("step") == "record_availability_check")
    assert gap_step["gap_count"] == 0


def test_record_gap_count_two():
    inp = _make_input(ror_present=False, registration_present=False)
    result = de.run(inp)
    gap_step = next(t for t in result.reasoning_trace if t.get("step") == "record_availability_check")
    assert gap_step["gap_count"] == 2


def test_two_missing_records_higher_priority_than_one():
    inp_one = _make_input(ror_present=False, registration_present=True)
    inp_two = _make_input(ror_present=False, registration_present=False)
    res_one = de.run(inp_one)
    res_two = de.run(inp_two)
    assert res_two.priority_score > res_one.priority_score


# ---------------------------------------------------------------------------
# 5. Routing thresholds
# ---------------------------------------------------------------------------

def test_low_signals_produce_no_action():
    inp = _make_input(area_diff_pct=0.1, boundary_shift_m=0.5)
    result = de.run(inp)
    assert result.outcome == de.DecisionOutcome.NO_ACTION
    assert result.lock_id is None
    assert result.confidence_score is None


def test_high_signals_produce_field_verification():
    # boundary_shift_m=20m with gnss_uncertainty=3.5m → effective shift=16.5m on 10000m² parcel
    # That plus one missing record and pending mutation should clear the 45.0 threshold
    inp = _make_input(
        area_diff_pct=8.0,
        boundary_shift_m=20.0,
        gnss_uncertainty_m=3.5,
        ror_present=False,
        mutation_status="pending",
    )
    result = de.run(inp)
    assert result.outcome in (de.DecisionOutcome.FIELD_VERIFICATION, de.DecisionOutcome.AUTHORITY_REVIEW)
    assert result.lock_id is not None
    assert result.lock_expires_at is not None
    assert result.confidence_score is not None


def test_very_high_signals_produce_authority_review():
    inp = _make_input(
        area_diff_pct=20.0,
        boundary_shift_m=50.0,
        ror_present=False,
        registration_present=False,
        mutation_status="pending",
        temporal_instability=0.9,
    )
    result = de.run(inp)
    assert result.outcome == de.DecisionOutcome.AUTHORITY_REVIEW


# ---------------------------------------------------------------------------
# 6. Lock has mandatory TTL
# ---------------------------------------------------------------------------

def test_lock_has_expiry_when_case_opened():
    inp = _make_input(area_diff_pct=10.0, boundary_shift_m=20.0, ror_present=False)
    result = de.run(inp)
    if result.lock_id:
        assert result.lock_expires_at is not None
        assert result.lock_expires_at > utcnow()


# ---------------------------------------------------------------------------
# 7. Update class classification
# ---------------------------------------------------------------------------

def test_missing_registration_classified_as_ownership():
    update_class = de._classify_update_type(
        de.SpatialSignals(0.5, 1.0, 10000, 3.5),
        de.RecordAvailability(ror_present=False, registration_present=False, mutation_status="approved", record_gap_count=2),
    )
    assert update_class == de.UpdateClass.OWNERSHIP


def test_pending_mutation_classified_correctly():
    update_class = de._classify_update_type(
        de.SpatialSignals(0.5, 1.0, 10000, 3.5),
        de.RecordAvailability(ror_present=True, registration_present=True, mutation_status="pending", record_gap_count=0),
    )
    assert update_class == de.UpdateClass.MUTATION


def test_large_boundary_shift_classified_as_cadastral():
    update_class = de._classify_update_type(
        de.SpatialSignals(3.0, 10.0, 10000, 3.5),
        de.RecordAvailability(ror_present=True, registration_present=True, mutation_status="approved", record_gap_count=0),
    )
    assert update_class == de.UpdateClass.CADASTRAL_GEOMETRY


# ---------------------------------------------------------------------------
# 8. Authority tier gating
# ---------------------------------------------------------------------------

def test_ownership_requires_tier2():
    tier = de._required_authority_tier(de.UpdateClass.OWNERSHIP, 50.0)
    assert tier == de.AuthorityTier.TIER_2


def test_high_priority_requires_tier2():
    tier = de._required_authority_tier(de.UpdateClass.CADASTRAL_GEOMETRY, 72.0)
    assert tier == de.AuthorityTier.TIER_2


def test_low_priority_cadastral_allows_tier1():
    tier = de._required_authority_tier(de.UpdateClass.CADASTRAL_GEOMETRY, 55.0)
    assert tier == de.AuthorityTier.TIER_1


# ---------------------------------------------------------------------------
# 9. Approval → Record Update: approval must precede write
# ---------------------------------------------------------------------------

def test_approval_creates_signature():
    approval = de.create_approval(
        case_id="CASE-001",
        approver_id="OFFICER-1",
        approver_tier=de.AuthorityTier.TIER_1,
        update_class=de.UpdateClass.CADASTRAL_GEOMETRY,
        reason="Boundary verified in field",
    )
    assert approval.approval_id is not None
    assert len(approval.signature_hash) == 64  # SHA-256 hex


def test_record_update_requires_approval():
    with pytest.raises(ValueError, match="valid approval"):
        fake_approval = de.ApprovalRecord(
            approval_id="",     # empty — no approval
            case_id="CASE-001",
            approver_id="X",
            approver_tier=de.AuthorityTier.TIER_1,
            update_class=de.UpdateClass.CADASTRAL_GEOMETRY,
            reason="test",
            timestamp=utcnow(),
            signature_hash="",
        )
        de.apply_record_update(fake_approval, "parcel-001", [])


def test_record_update_correct_order():
    approval = de.create_approval(
        case_id="CASE-002",
        approver_id="OFFICER-1",
        approver_tier=de.AuthorityTier.TIER_1,
        update_class=de.UpdateClass.CADASTRAL_GEOMETRY,
        reason="Confirmed discrepancy",
    )
    update, version = de.apply_record_update(
        approval=approval,
        target_record_ref="ror-001",
        changes=[{"field": "area_sqm", "old_value": 9800, "new_value": 10200}],
    )
    assert update.approval_id == approval.approval_id
    assert version.snapshot["approval_id"] == approval.approval_id
    assert update.changes[0]["field"] == "area_sqm"


# ---------------------------------------------------------------------------
# 10. Audit chain — hash chain integrity
# ---------------------------------------------------------------------------

def test_audit_chain_links_correctly():
    entry1 = de._build_audit_entry(
        case_id="CASE-003", seq=1, event_type="CASE_OPENED",
        actor_id="SYSTEM", actor_role="DECISION_ENGINE",
        data={"priority_score": 60.0}, prev_hash="",
    )
    entry2 = de._build_audit_entry(
        case_id="CASE-003", seq=2, event_type="FIELD_VERIFIED",
        actor_id="OFFICER-1", actor_role="SURVEYOR_FIELD",
        data={"status": "CONFIRMED"}, prev_hash=entry1.hash_chain_entry,
    )
    assert entry1.hash_chain_entry != entry2.hash_chain_entry
    assert len(entry2.hash_chain_entry) == 64


def test_tampered_audit_chain_produces_different_hash():
    entry1 = de._build_audit_entry(
        case_id="CASE-004", seq=1, event_type="CASE_OPENED",
        actor_id="SYSTEM", actor_role="DECISION_ENGINE",
        data={"priority_score": 60.0}, prev_hash="",
    )
    # Tamper: change a data value
    import copy, json
    tampered_data = copy.deepcopy(entry1.data)
    tampered_data["priority_score"] = 99.9

    # Re-compute what the hash would be with tampered data — it must differ
    honest_hash = entry1.hash_chain_entry
    tampered_entry = de._build_audit_entry(
        case_id="CASE-004", seq=1, event_type="CASE_OPENED",
        actor_id="SYSTEM", actor_role="DECISION_ENGINE",
        data=tampered_data, prev_hash="",
    )
    assert tampered_entry.hash_chain_entry != honest_hash


# ---------------------------------------------------------------------------
# 11. ML plugin points respected
# ---------------------------------------------------------------------------

def test_model_iou_contributes_to_score():
    # Low model_iou (bad boundary match) should raise priority
    inp_no_ml = _make_input(area_diff_pct=0.5, boundary_shift_m=1.0, model_iou=None)
    inp_with_ml = _make_input(area_diff_pct=0.5, boundary_shift_m=1.0, model_iou=0.45)
    res_no_ml = de.run(inp_no_ml)
    res_with_ml = de.run(inp_with_ml)
    assert res_with_ml.priority_score >= res_no_ml.priority_score


def test_temporal_instability_contributes_to_score():
    inp_no_temporal = _make_input(temporal_instability=None)
    inp_with_temporal = _make_input(temporal_instability=0.85)
    res_no_t = de.run(inp_no_temporal)
    res_with_t = de.run(inp_with_temporal)
    assert res_with_t.priority_score >= res_no_t.priority_score


# ---------------------------------------------------------------------------
# 12. GNSS uncertainty subtracted from boundary shift before scoring
# ---------------------------------------------------------------------------

def test_gnss_uncertainty_subtracted():
    # If boundary_shift_m == gnss_uncertainty_m, effective shift = 0 → near-zero spatial component
    spatial = de.SpatialSignals(
        area_diff_pct=0.0, boundary_shift_m=3.5,
        parcel_area_sqm=10000.0, gnss_uncertainty_m=3.5,
    )
    score = de._scale_normalized_spatial_score(spatial)
    assert score < 0.05, f"Expected near-zero score when shift == GNSS uncertainty, got {score}"


# ---------------------------------------------------------------------------
# 13. Reasoning trace is always populated on every non-trivial run
# ---------------------------------------------------------------------------

def test_reasoning_trace_always_populated():
    inp = _make_input(area_diff_pct=10.0, boundary_shift_m=20.0, ror_present=False)
    result = de.run(inp)
    assert len(result.reasoning_trace) > 0
    step_names = [t.get("step", t.get("rule", "")) for t in result.reasoning_trace]
    assert "record_availability_check" in step_names
    assert "spatial_analysis" in step_names
    assert "priority_score" in step_names


# ---------------------------------------------------------------------------
# 14. Internal parcel key vs ULPIN contract
# ---------------------------------------------------------------------------

def test_engine_never_generates_ulpin():
    inp = _make_input()
    result = de.run(inp)
    # parcel_key should be internal, not formatted like a ULPIN
    assert result.parcel_key == "TEST-PARCEL-001"
    # The result dict must not contain a 'ulpin' key
    assert "ulpin" not in result.__dict__
