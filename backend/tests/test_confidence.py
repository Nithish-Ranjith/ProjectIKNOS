"""
backend/tests/test_confidence.py — Unit tests for the confidence scoring formula.

Tests:
  1. Weights sum to 1.0 (startup validation)
  2. All-clean parcel scores low
  3. High spatial discrepancy scores higher
  4. Registration missing adds registration_conflict weight
  5. Mutation pending adds mutation_pending weight
  6. STANDARD_GNSS penalty applies
  7. Temporal signal of 1.0 adds full temporal weight
  8. Action routing: score >= 50 → field_verification_required
  9. Reasoning trace contains all 5 rules
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import json
import math
import pytest
from backend.app.confidence import compute_confidence


def test_weights_sum_to_one():
    """Weights must sum to exactly 1.0 — validated at module import."""
    config_path = os.path.join(os.path.dirname(__file__), "../app/config/weights.json")
    with open(config_path) as f:
        cfg = json.load(f)
    total = sum(cfg["weights"].values())
    assert math.isclose(total, 1.0, abs_tol=1e-6), f"Weights sum to {total}, not 1.0"


def test_clean_parcel_scores_low():
    result = compute_confidence(
        area_diff_pct=0,
        boundary_shift_m=0,
        parcel_area_sqm=1000,
        registration_status="present",
        mutation_status="approved",
        instability_score=0.0,
        positioning_quality="RTK_FIX",
    )
    assert result["confidence_score"] < 20, f"Expected < 20, got {result['confidence_score']}"
    assert result["action"] == "no_action"


def test_high_spatial_discrepancy_scores_higher():
    result = compute_confidence(
        area_diff_pct=40,
        boundary_shift_m=10.0,
        parcel_area_sqm=100,
        registration_status="present",
        mutation_status="approved",
        instability_score=0.0,
        positioning_quality="RTK_FIX",
    )
    low = compute_confidence(
        area_diff_pct=0, boundary_shift_m=0, parcel_area_sqm=100,
        registration_status="present", mutation_status="approved",
        instability_score=0.0, positioning_quality="RTK_FIX"
    )
    assert result["confidence_score"] > low["confidence_score"]


def test_registration_missing_increases_score():
    with_reg = compute_confidence(
        area_diff_pct=0, boundary_shift_m=0, parcel_area_sqm=1000,
        registration_status="present", mutation_status="approved",
        positioning_quality="RTK_FIX"
    )
    without_reg = compute_confidence(
        area_diff_pct=0, boundary_shift_m=0, parcel_area_sqm=1000,
        registration_status="missing", mutation_status="approved",
        positioning_quality="RTK_FIX"
    )
    assert without_reg["confidence_score"] > with_reg["confidence_score"]


def test_mutation_pending_increases_score():
    approved = compute_confidence(
        area_diff_pct=0, boundary_shift_m=0, parcel_area_sqm=1000,
        registration_status="present", mutation_status="approved",
        positioning_quality="RTK_FIX"
    )
    pending = compute_confidence(
        area_diff_pct=0, boundary_shift_m=0, parcel_area_sqm=1000,
        registration_status="present", mutation_status="pending",
        positioning_quality="RTK_FIX"
    )
    assert pending["confidence_score"] > approved["confidence_score"]


def test_standard_gnss_penalty():
    rtk = compute_confidence(
        area_diff_pct=5, boundary_shift_m=2, parcel_area_sqm=100,
        registration_status="present", mutation_status="approved",
        positioning_quality="RTK_FIX"
    )
    gnss = compute_confidence(
        area_diff_pct=5, boundary_shift_m=2, parcel_area_sqm=100,
        registration_status="present", mutation_status="approved",
        positioning_quality="STANDARD_GNSS"
    )
    assert gnss["confidence_score"] > rtk["confidence_score"], (
        "STANDARD_GNSS should score HIGHER (worse) due to quality penalty"
    )


def test_high_instability_score_increases_confidence():
    no_s2 = compute_confidence(
        area_diff_pct=0, boundary_shift_m=0, parcel_area_sqm=1000,
        registration_status="present", mutation_status="approved",
        instability_score=0.0, positioning_quality="RTK_FIX"
    )
    high_s2 = compute_confidence(
        area_diff_pct=0, boundary_shift_m=0, parcel_area_sqm=1000,
        registration_status="present", mutation_status="approved",
        instability_score=1.0, positioning_quality="RTK_FIX"
    )
    assert high_s2["confidence_score"] > no_s2["confidence_score"]


def test_action_routing_threshold():
    """Scores >= 50 route to field_verification_required."""
    high = compute_confidence(
        area_diff_pct=50, boundary_shift_m=15, parcel_area_sqm=100,
        registration_status="missing", mutation_status="pending",
        instability_score=1.0, positioning_quality="STANDARD_GNSS"
    )
    assert high["action"] == "field_verification_required"
    assert high["confidence_score"] >= 50


def test_reasoning_trace_has_all_rules():
    result = compute_confidence(
        area_diff_pct=5, boundary_shift_m=2, parcel_area_sqm=500,
        registration_status="present", mutation_status="approved",
        instability_score=0.3, positioning_quality="STANDARD_GNSS"
    )
    rules = {r["rule"] for r in result["reasoning_trace"]}
    expected_rules = {
        "spatial_discrepancy_check",
        "registration_conflict_check",
        "mutation_pending_check",
        "temporal_signal_check",
        "positioning_quality_check",
    }
    assert expected_rules == rules, f"Missing rules: {expected_rules - rules}"


def test_null_temporal_signal_not_treated_as_discrepancy():
    """None instability_score should not be treated as 1.0."""
    with_none = compute_confidence(
        area_diff_pct=0, boundary_shift_m=0, parcel_area_sqm=1000,
        registration_status="present", mutation_status="approved",
        instability_score=None, positioning_quality="RTK_FIX"
    )
    with_one = compute_confidence(
        area_diff_pct=0, boundary_shift_m=0, parcel_area_sqm=1000,
        registration_status="present", mutation_status="approved",
        instability_score=1.0, positioning_quality="RTK_FIX"
    )
    assert with_none["confidence_score"] < with_one["confidence_score"]
