"""
backend/app/confidence.py — Deterministic evidence-fusion formula.

Deliberately NOT ML. Deliberately NOT a single global IoU >= 0.85 cutoff.
Spatial discrepancy is normalized against parcel scale.
Weights are loaded from config/weights.json and validated at startup.
Every score change is explainable via the reasoning trace.
"""
import json
import math
from pathlib import Path
from typing import Optional

_CONFIG_PATH = Path(__file__).parent / "config" / "weights.json"


def _load_config():
    with open(_CONFIG_PATH) as f:
        cfg = json.load(f)
    w = cfg["weights"]
    total = sum(w.values())
    if not math.isclose(total, 1.0, abs_tol=1e-6):
        raise RuntimeError(
            f"confidence weights in {_CONFIG_PATH} sum to {total}, not 1.0 — "
            "refusing to start with an inconsistent scoring formula."
        )
    return cfg


_CONFIG = _load_config()


def normalized_spatial_score(
    area_diff_pct: float, boundary_shift_m: float, parcel_area_sqm: float
) -> float:
    """
    Returns 0-1. Scales boundary_shift_m against sqrt(parcel_area) as a proxy
    for the parcel's characteristic size, so a 2m shift on a 0.1-ha parcel
    and a 2m shift on a 5-ha parcel are not treated as equally severe.
    """
    area_component = min(area_diff_pct / 25.0, 1.0)   # 25% diff saturates at 1.0

    characteristic_length = math.sqrt(max(parcel_area_sqm, 1.0))
    shift_ratio = boundary_shift_m / characteristic_length
    shift_component = min(shift_ratio * 10.0, 1.0)     # tunable scale factor in config

    return max(area_component, shift_component)


def compute_confidence(
    *,
    area_diff_pct: float,
    boundary_shift_m: float,
    parcel_area_sqm: float,
    registration_status: str,       # 'present' | 'missing'
    mutation_status: str,           # 'pending' | 'approved' | 'none'
    instability_score: Optional[float] = None,   # 0-1, from Sentinel-2; None if not run
    positioning_quality: str = "STANDARD_GNSS",  # 'STANDARD_GNSS' | 'RTK_FIX'
) -> dict:
    """
    Deterministic weighted confidence formula. Returns a dict with:
      confidence_score  (0-100)
      action            ('field_verification_required' | 'no_action')
      reasoning_trace   (list of rule dicts — one per sub-score)
      positioning_quality (passed through for transparency)
    """
    w = _CONFIG["weights"]
    trace = []

    # 1. Spatial discrepancy (scale-normalized)
    spatial_sub = normalized_spatial_score(area_diff_pct, boundary_shift_m, parcel_area_sqm)
    trace.append({
        "rule": "spatial_discrepancy_check",
        "result": "significant" if spatial_sub > 0.3 else "within_tolerance",
        "detail": (
            f"area_diff_pct={area_diff_pct}, boundary_shift_m={boundary_shift_m}, "
            f"normalized_against_parcel_scale={round(spatial_sub, 3)}"
        ),
    })

    # 2. Registration evidence (independent from RoR — cannot collapse these signals)
    reg_sub = 1.0 if registration_status == "missing" else 0.0
    trace.append({
        "rule": "registration_conflict_check",
        "result": registration_status,
        "detail": (
            "no registration deed on file — signal present independently of RoR status"
            if registration_status == "missing"
            else "registration deed present"
        ),
    })

    # 3. Mutation pending
    mut_sub = 1.0 if mutation_status == "pending" else 0.0
    trace.append({
        "rule": "mutation_pending_check",
        "result": mutation_status,
    })

    # 4. Temporal signal (Sentinel-2 STL+PELT)
    if instability_score is not None:
        temporal_sub = instability_score
        trace.append({
            "rule": "temporal_signal_check",
            "result": "deviation_detected" if instability_score > 0.5 else "stable",
            "detail": f"instability_score={instability_score} — temporal anomaly, NOT a legal verdict",
        })
    else:
        temporal_sub = 0.0
        trace.append({
            "rule": "temporal_signal_check",
            "result": "not_run",
            "detail": "Sentinel-2 temporal analysis not available for this case",
        })

    # 5. Positioning quality penalty
    quality_sub = 0.0 if positioning_quality == "RTK_FIX" else 0.5
    trace.append({
        "rule": "positioning_quality_check",
        "result": positioning_quality,
        "detail": (
            "consumer-grade GNSS (~2.5-5m accuracy) — spatial evidence weighted down accordingly"
            if positioning_quality != "RTK_FIX"
            else "survey-grade RTK fix"
        ),
    })

    # Pattern-Library Intelligence Layer
    PATTERN_LIBRARY = [
        {
            "id": "ENCROACHMENT_HIGH_RISK",
            "description": "Significant boundary shift with missing registration or pending mutation.",
            "condition": lambda s, r, m, t: s > 0.4 and (r == "missing" or m == "pending"),
            "base_risk": 85.0
        },
        {
            "id": "ABANDONED_OR_FALLOW",
            "description": "High temporal instability with missing records, possibly abandoned.",
            "condition": lambda s, r, m, t: t > 0.6 and r == "missing",
            "base_risk": 75.0
        },
        {
            "id": "ADMINISTRATIVE_LAG",
            "description": "No significant spatial shift, but pending mutation or missing registration.",
            "condition": lambda s, r, m, t: s < 0.2 and (m == "pending" or r == "missing"),
            "base_risk": 40.0
        }
    ]

    matched_pattern = None
    for pattern in PATTERN_LIBRARY:
        if pattern["condition"](spatial_sub, registration_status, mutation_status, temporal_sub):
            matched_pattern = pattern
            break

    if matched_pattern:
        raw = matched_pattern["base_risk"] / 100.0
        trace.append({
            "rule": "pattern_library_match",
            "result": matched_pattern["id"],
            "detail": matched_pattern["description"]
        })
    else:
        # Fallback to deterministic weighted sum
        raw = (
            w["spatial_discrepancy"] * spatial_sub
            + w["registration_conflict"] * reg_sub
            + w["mutation_pending"] * mut_sub
            + w["temporal_signal"] * temporal_sub
            + w["source_quality_penalty"] * quality_sub
        )
        trace.append({
            "rule": "pattern_library_match",
            "result": "NO_PATTERN_MATCH",
            "detail": "Fell back to linear weighted sum"
        })

    risk_score = round(raw * 100, 1)

    threshold = _CONFIG["thresholds"]["confidence_score_route_to_verification"]
    action = "field_verification_required" if risk_score >= threshold else "no_action"

    return {
        "risk_score": risk_score,
        "confidence_score": risk_score, # Alias for backwards compatibility
        "action": action,
        "reasoning_trace": trace,
        "positioning_quality": positioning_quality,
    }
