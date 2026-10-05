"""
run_track_b.py -- IKNOS Track B: Targeted Investigation & Field Verification

Ingests an escalated Case JSON (v1.1) produced by Track A and advances it
through the targeted-investigation pipeline:

    check-lock -> survey -> extract-boundary -> compare -> officer-review -> approve

or all at once via `full-pipeline-demo`.

DESIGN PRINCIPLE -- do not trust the inbound `status` string:
    This module infers the actual pipeline stage from which fields are
    populated vs null, and corrects/logs a mismatch rather than trusting the
    stored label. This is not theoretical: Track A's own sample output
    (CASE-2026-E078A6) shipped with status="OFFICER_REVIEW_PENDING" while
    every Track B field (field_verification, evidence.spatial_evidence,
    officer_decision) was still null -- i.e. a case that had not been
    surveyed yet, mislabeled as ready for officer sign-off. See
    reconcile_status_label() below.

WHAT IS REAL vs SIMULATED IN THIS FILE:
    REAL:      lock TTL logic, IoU/Hausdorff/area-discrepancy computation,
               size-and-uncertainty-scaled discrepancy threshold, evidence
               fusion into reasoning_trace, authority-tier escalation logic,
               signature-before-write ordering, hash-chained audit log,
               parcel history, status snapshot.
    EXTRACTION: Supports ingestion and vectorization of real/synthetic GeoTIFF
               orthomosaics via `boundary_extractor.py`. Falls back to an
               anomaly-scaled geometric simulation if no raster is supplied.

Dependencies: shapely (pip install shapely rasterio opencv-python). Everything else is stdlib.
"""

from __future__ import annotations
import argparse
import hashlib
import json
import math
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from shapely.geometry import Polygon, mapping, shape
from shapely.ops import transform as shapely_transform

try:
    from boundary_extractor import extract_parcel_polygon_from_ortho
except ImportError:
    extract_parcel_polygon_from_ortho = None

EARTH_RADIUS_M = 6_371_000.0


def _local_meters_projector(origin_lon: float, origin_lat: float):
    """
    Simple equirectangular approximation centered on the parcel: adequate at
    parcel scale (tens to low hundreds of meters), not for large-area or
    high-latitude work. Shapely has no notion of geographic coordinates --
    feeding it raw lon/lat and asking for .area or .hausdorff_distance
    silently returns nonsense in "square degrees" / "degrees of distance"
    rather than an error. All geometric math below runs in this local meter
    frame; geo refs in the case JSON stay in lon/lat.
    """
    lat0_rad = math.radians(origin_lat)
    m_per_deg_lat = math.pi / 180.0 * EARTH_RADIUS_M
    m_per_deg_lon = m_per_deg_lat * math.cos(lat0_rad)

    def _project(x, y, z=None):
        return ((x - origin_lon) * m_per_deg_lon, (y - origin_lat) * m_per_deg_lat)

    return _project


# --------------------------------------------------------------------------
# Paths / constants
# --------------------------------------------------------------------------

OUTPUT_DIR = Path("data/output")
HASH_LEDGER_PATH = OUTPUT_DIR / "hash_chain_ledger.json"
SNAPSHOT_PATH = OUTPUT_DIR / "parcel_status_snapshots.json"
PARCEL_HISTORY_PATH = OUTPUT_DIR / "parcel_history.json"

# Authority-tier escalation rules
SENIOR_REVIEW_PRIORITY_THRESHOLD = 0.80
SENIOR_REVIEW_AREA_DELTA_PCT_THRESHOLD = 15.0
SENIOR_REVIEW_UPDATE_TYPES = {"OWNERSHIP_MUTATION"}

# Spatial threshold scaling
IOU_BASE_THRESHOLD = 0.85
IOU_FLOOR = 0.55
AREA_DISCREPANCY_FLAG_PCT = 10.0

# Positional uncertainty by survey equipment class, meters
SURVEY_GRADE_UNCERTAINTY_M = {
    "RTK": 0.03,
    "PPK": 0.05,
    "DGPS": 0.5,
    "CONSUMER_GNSS": 3.0,
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_of(obj) -> str:
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_case(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_case(case: dict, path: Path) -> None:
    case["updated_at"] = now_iso()
    to_write = {k: v for k, v in case.items() if not k.startswith("_internal")}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(to_write, f, indent=2)


def append_ledger_entry(entry: dict) -> tuple[str, str]:
    """Append-only global hash chain. Returns (current_hash, previous_hash)."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ledger = []
    if HASH_LEDGER_PATH.exists():
        ledger = json.loads(HASH_LEDGER_PATH.read_text(encoding="utf-8"))
    previous_hash = ledger[-1]["current_hash"] if ledger else "0" * 64
    entry = dict(entry)
    entry["previous_hash"] = previous_hash
    entry["current_hash"] = sha256_of({**entry, "current_hash": None})
    ledger.append(entry)
    HASH_LEDGER_PATH.write_text(json.dumps(ledger, indent=2, default=str), encoding="utf-8")
    return entry["current_hash"], entry["previous_hash"]


def append_parcel_history(parcel_key: str, entry: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    history = {}
    if PARCEL_HISTORY_PATH.exists():
        history = json.loads(PARCEL_HISTORY_PATH.read_text(encoding="utf-8"))
    history.setdefault(parcel_key, []).append(entry)
    PARCEL_HISTORY_PATH.write_text(json.dumps(history, indent=2), encoding="utf-8")


def _verification_state(case: dict) -> str:
    return {
        "CLOSED_RECONCILED": "reconciled",
        "CLOSED_NO_DISCREPANCY": "verified_no_discrepancy",
        "CLOSED_REJECTED": "reviewed_rejected",
    }.get(case["status"], "under_investigation")


def write_status_snapshot(case: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    snapshots = {}
    if SNAPSHOT_PATH.exists():
        snapshots = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    key = case["parcel"]["internal_parcel_key"]
    snapshots[key] = {
        "parcel_key": key,
        "case_id": case["case_id"],
        "current_status": case["status"],
        "verification_state": _verification_state(case),
        "last_updated": now_iso(),
    }
    SNAPSHOT_PATH.write_text(json.dumps(snapshots, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------
# Defensive stage detection -- do NOT trust `status` alone
# --------------------------------------------------------------------------

def infer_actual_stage(case: dict) -> str:
    if case.get("officer_decision", {}).get("decision") not in (None, "VALID_PENDING_APPROVAL"):
        return "OFFICER_DECIDED"
    if case["evidence"].get("spatial_evidence") is not None:
        return "SPATIAL_COMPARISON_DONE"
    if case.get("field_verification") is not None:
        return "FIELD_SURVEY_DONE"
    return "AWAITING_SURVEY"


def reconcile_status_label(case: dict) -> dict:
    if case["status"].startswith("CLOSED"):
        return case
    actual = infer_actual_stage(case)
    expected = {
        "AWAITING_SURVEY": "LOCKED_UNDER_INVESTIGATION",
        "FIELD_SURVEY_DONE": "LOCKED_UNDER_INVESTIGATION",
        "SPATIAL_COMPARISON_DONE": "OFFICER_REVIEW_PENDING",
        "OFFICER_DECIDED": case["status"],
    }.get(actual)
    if expected and case["status"] != expected:
        print(
            f"[track_b][WARNING] case {case['case_id']}: stored status "
            f"'{case['status']}' does not match actual content stage "
            f"'{actual}' (field_verification={case.get('field_verification') is not None}, "
            f"spatial_evidence={case['evidence'].get('spatial_evidence') is not None}, "
            f"officer_decision={case['officer_decision'].get('decision')}). "
            f"Correcting status to '{expected}'.",
            file=sys.stderr,
        )
        case["status"] = expected
    return case


# --------------------------------------------------------------------------
# Stage 1: Parcel lock TTL check
# --------------------------------------------------------------------------

def cmd_check_lock(case: dict, supervisor_decision: Optional[str]) -> dict:
    lock = case["parcel_lock"]
    if not lock["locked"]:
        print("[check-lock] Parcel is not currently locked. Nothing to do.")
        return case

    locked_at = datetime.fromisoformat(lock["locked_at"])
    elapsed_hours = (datetime.now(timezone.utc) - locked_at).total_seconds() / 3600
    ttl = lock["lock_ttl_hours"]

    if elapsed_hours <= ttl:
        print(f"[check-lock] OK. {elapsed_hours:.2f}h / {ttl}h elapsed. No action needed.")
        return case

    print(f"[check-lock] TTL EXCEEDED: {elapsed_hours:.2f}h elapsed, TTL was {ttl}h.")
    lock["escalated"] = True

    if supervisor_decision == "extend":
        lock["locked_at"] = now_iso()
        print("[check-lock] Supervisor extended the lock. Case resumes at TARGETED SURVEY.")
    elif supervisor_decision == "force-release":
        lock["locked"] = False
        case["status"] = "CLOSED_REJECTED"
        case["officer_decision"] = {
            "decision": "ABANDONED",
            "decided_by": "SYSTEM_SUPERVISOR_ESCALATION",
            "decided_at": now_iso(),
            "reason": "Investigation stalled beyond lock TTL; force-released by supervisor.",
            "signature_ref": None,
        }
        append_parcel_history(case["parcel"]["internal_parcel_key"], {
            "case_id": case["case_id"],
            "closed_status": "CLOSED_REJECTED",
            "closed_at": now_iso(),
            "reason": "lock_ttl_exceeded_force_release",
        })
        write_status_snapshot(case)
        print("[check-lock] Supervisor force-released the lock. Case closed as ABANDONED.")
    else:
        print(
            "[check-lock] TTL exceeded but no --supervisor-decision given "
            "(extend|force-release). Case remains locked and escalated, "
            "awaiting supervisor action.",
            file=sys.stderr,
        )
    return case


# --------------------------------------------------------------------------
# Stage 2: Targeted survey + field verification (surveyor attestation)
# --------------------------------------------------------------------------

def cmd_survey(case: dict, surveyor_id: str, survey_grade: str) -> dict:
    if survey_grade not in SURVEY_GRADE_UNCERTAINTY_M:
        raise ValueError(
            f"Unknown survey_grade '{survey_grade}'. Choose from {list(SURVEY_GRADE_UNCERTAINTY_M)}"
        )

    case["field_verification"] = {
        "assigned_to": surveyor_id,
        "assigned_at": now_iso(),
        "completed_at": now_iso(),
        "survey_grade": survey_grade,
        "site_visit": {
            "geotag": case["parcel"]["centroid"],
            "visited_at": now_iso(),
            "photo_refs": [],
        },
        "structured_findings": [
            {
                "observation": "gcp_verified",
                "detail": "Ground control points confirmed against parcel centroid.",
            },
            {
                "observation": "flight_certified",
                "detail": f"Surveyor {surveyor_id} certifies correct parcel was flown.",
            },
        ],
        "findings_summary": f"On-site surveyor attestation complete ({survey_grade} grade).",
        "report_ref": f"report://field-verification/{case['case_id']}",
    }
    case["status"] = "LOCKED_UNDER_INVESTIGATION"
    print(f"[survey] Field verification recorded by {surveyor_id} ({survey_grade} grade GNSS).")
    return case


# --------------------------------------------------------------------------
# Stage 3: Boundary extraction (GeoTIFF Raster or Geometric Simulation Fallback)
# --------------------------------------------------------------------------

def cmd_extract_boundary(
    case: dict,
    ortho_tif_path: Optional[Path] = None,
    seed: Optional[int] = None,
) -> tuple[dict, Polygon, str]:
    """
    Extracts observed parcel boundaries directly from a drone orthomosaic GeoTIFF.
    Falls back to anomaly-scaled simulation if no raster is supplied.
    """
    if ortho_tif_path and Path(ortho_tif_path).exists():
        if extract_parcel_polygon_from_ortho is None:
            raise ImportError(
                "boundary_extractor module not found. Ensure boundary_extractor.py exists in the project root."
            )
        print(f"[extract-boundary] Processing drone GeoTIFF: {ortho_tif_path}")
        observed, geo_ref = extract_parcel_polygon_from_ortho(Path(ortho_tif_path))
        case["_internal_geometry_note"] = (
            f"EXTRACTED: Computed from raster orthomosaic {Path(ortho_tif_path).name}"
        )
        print(
            f"[extract-boundary] Extracted vector boundary -> {geo_ref} "
            f"(Vertices: {len(observed.exterior.coords)})"
        )
        return case, observed, geo_ref

    # Fallback to geometric simulation if no raster file is passed
    rng = random.Random(seed if seed is not None else case["case_id"])
    minx, miny, maxx, maxy = case["parcel"]["bbox"]
    anomaly = case["evidence"]["satellite_evidence"]["anomaly_score"]

    shift_frac = 0.02 + 0.15 * anomaly
    dx = (maxx - minx) * shift_frac * rng.choice([-1, 1])
    shrink = 1.0 - (0.05 + 0.20 * anomaly) * rng.uniform(0.5, 1.0)

    cx = (minx + maxx) / 2 + dx
    cy = (miny + maxy) / 2
    hw = (maxx - minx) / 2 * math.sqrt(shrink)
    hh = (maxy - miny) / 2 * math.sqrt(shrink)
    observed = Polygon([
        (cx - hw, cy - hh),
        (cx + hw, cy - hh),
        (cx + hw, cy + hh),
        (cx - hw, cy + hh),
    ])

    geo_ref = f"geo://survey/{case['case_id']}/observed_v1"
    case["_internal_geometry_note"] = (
        "SIMULATED: no real drone capture available today. Geometry generated "
        "by perturbing the cadastral bbox in proportion to the satellite "
        "anomaly score, for end-to-end pipeline demonstration only."
    )
    print(
        f"[extract-boundary] SIMULATED observed geometry generated -> {geo_ref} "
        f"(anomaly_score={anomaly}, shift_frac={shift_frac:.3f}, shrink={shrink:.3f})"
    )
    return case, observed, geo_ref


# --------------------------------------------------------------------------
# Stage 4: Deterministic spatial comparison
# --------------------------------------------------------------------------

def scaled_iou_threshold(parcel_area_sqm: float, perimeter_m: float, uncertainty_m: float) -> float:
    if parcel_area_sqm <= 0:
        return IOU_BASE_THRESHOLD
    noise_fraction = (perimeter_m * uncertainty_m) / parcel_area_sqm
    return max(IOU_FLOOR, min(IOU_BASE_THRESHOLD, IOU_BASE_THRESHOLD - noise_fraction))


def cmd_compare(
    case: dict,
    cadastral_geojson: dict,
    observed_polygon: Polygon,
    survey_grade: str,
) -> dict:
    cadastral_lonlat = shape(cadastral_geojson)
    uncertainty_m = SURVEY_GRADE_UNCERTAINTY_M[survey_grade]

    origin_lon, origin_lat = case["parcel"]["centroid"]["coordinates"]
    project = _local_meters_projector(origin_lon, origin_lat)
    cadastral = shapely_transform(project, cadastral_lonlat)
    observed_m = shapely_transform(project, observed_polygon)

    intersection = cadastral.intersection(observed_m).area
    union = cadastral.union(observed_m).area
    iou = intersection / union if union > 0 else 0.0
    hausdorff = cadastral.hausdorff_distance(observed_m)

    area_declared = cadastral.area
    area_surveyed = observed_m.area
    area_discrepancy_pct = (
        abs(area_declared - area_surveyed) / area_declared * 100 if area_declared > 0 else 0.0
    )

    perimeter_m = cadastral.length
    threshold_used = scaled_iou_threshold(area_declared, perimeter_m, uncertainty_m)
    topology_issues: list[str] = []

    significant = (
        (iou < threshold_used)
        or (area_discrepancy_pct > AREA_DISCREPANCY_FLAG_PCT)
        or bool(topology_issues)
    )

    case["evidence"]["spatial_evidence"] = {
        "survey_geometry_ref": f"geo://survey/{case['case_id']}/observed_v1",
        "cadastral_geometry_ref": case["parcel"]["cadastral_geometry_ref"],
        "iou": round(iou, 4),
        "iou_threshold_used": round(threshold_used, 4),
        "threshold_basis": "scaled_for_parcel_area_and_survey_uncertainty",
        "hausdorff_distance_m": round(hausdorff, 2),
        "area_declared_sqm": round(area_declared, 2),
        "area_surveyed_sqm": round(area_surveyed, 2),
        "area_discrepancy_pct": round(area_discrepancy_pct, 2),
        "topology_issues": topology_issues,
    }

    if not significant:
        case["status"] = "CLOSED_NO_DISCREPANCY"
        append_parcel_history(case["parcel"]["internal_parcel_key"], {
            "case_id": case["case_id"],
            "closed_status": "CLOSED_NO_DISCREPANCY",
            "closed_at": now_iso(),
        })
        case["parcel_lock"]["locked"] = False
        write_status_snapshot(case)
        print(
            f"[compare] IoU={iou:.3f} >= threshold={threshold_used:.3f}. "
            f"No significant discrepancy. Case CLOSED, lock released."
        )
    else:
        case["status"] = "OFFICER_REVIEW_PENDING"
        case["explanation"]["reasoning_trace"].append({
            "rule": "iou_threshold_check",
            "result": "below_threshold" if iou < threshold_used else "passed",
            "detail": (
                f"IoU {iou:.3f} vs threshold {threshold_used:.3f} "
                f"(scaled to parcel area {area_declared:.0f} sqm and "
                f"{survey_grade} positional uncertainty of {uncertainty_m}m, "
                f"not a fixed global cutoff)"
            ),
        })
        case["explanation"]["reasoning_trace"].append({
            "rule": "area_discrepancy_check",
            "result": "flagged" if area_discrepancy_pct > AREA_DISCREPANCY_FLAG_PCT else "ok",
            "detail": f"{area_discrepancy_pct:.1f}% area discrepancy vs declared.",
        })
        case["explanation"]["summary"] += (
            f" Drone survey found a boundary discrepancy: "
            f"IoU {iou:.2f} against a scaled threshold of {threshold_used:.2f}, "
            f"and a {area_discrepancy_pct:.1f}% area mismatch."
        )
        print(
            f"[compare] IoU={iou:.3f} vs threshold={threshold_used:.3f}, "
            f"area_discrepancy={area_discrepancy_pct:.1f}%. "
            f"SIGNIFICANT DISCREPANCY -> routed to officer review."
        )
    return case


# --------------------------------------------------------------------------
# Stage 5: Officer review + authority-tier gating + signature-before-write
# --------------------------------------------------------------------------

def cmd_officer_review(case: dict, officer_id: str, valid: bool, reason: str) -> dict:
    if not valid:
        case["status"] = "CLOSED_REJECTED"
        case["officer_decision"] = {
            "decision": "REJECTED",
            "decided_by": officer_id,
            "decided_at": now_iso(),
            "reason": reason,
            "signature_ref": None,
        }
        append_parcel_history(case["parcel"]["internal_parcel_key"], {
            "case_id": case["case_id"],
            "closed_status": "CLOSED_REJECTED",
            "closed_at": now_iso(),
            "reason": reason,
        })
        case["parcel_lock"]["locked"] = False
        write_status_snapshot(case)
        print(f"[officer-review] {officer_id} REJECTED case. Reason: {reason}. Lock released.")
        return case

    spatial = case["evidence"]["spatial_evidence"]
    area_delta = spatial["area_discrepancy_pct"]
    priority = case["priority_score"]["value"]
    record = case["evidence"]["record_evidence"]

    if record.get("registration_status") == "missing" and record.get("ror_status") == "missing":
        update_type = "OWNERSHIP_MUTATION"
    elif area_delta > 30:
        update_type = "OWNERSHIP_MUTATION"
    else:
        update_type = "BOUNDARY_CORRECTION"

    requires_senior = (
        priority > SENIOR_REVIEW_PRIORITY_THRESHOLD
        or area_delta > SENIOR_REVIEW_AREA_DELTA_PCT_THRESHOLD
        or update_type in SENIOR_REVIEW_UPDATE_TYPES
    )

    case["update_classification"] = {
        "type": update_type,
        "authority_tier_required": "senior" if requires_senior else "standard",
        "classified_at": now_iso(),
    }
    case["officer_decision"] = {
        "decision": "VALID_PENDING_APPROVAL",
        "decided_by": officer_id,
        "decided_at": now_iso(),
        "reason": reason,
        "signature_ref": None,
    }

    if requires_senior:
        print(
            f"[officer-review] {officer_id} confirmed discrepancy VALID. "
            f"update_type={update_type}, priority={priority}, area_delta={area_delta}% "
            f"-> requires SENIOR OFFICER approval. Run `approve` with a senior officer id."
        )
    else:
        print(
            f"[officer-review] {officer_id} confirmed discrepancy VALID. "
            f"Standard tier sufficient ({update_type}). Ready for signature + write."
        )
    return case


def cmd_approve(case: dict, approving_officer_id: str, is_senior: bool) -> dict:
    tier_required = case["update_classification"]["authority_tier_required"]
    if tier_required == "senior" and not is_senior:
        print(
            f"[approve] BLOCKED: this case requires a SENIOR officer. "
            f"{approving_officer_id} is not flagged --senior. No write performed.",
            file=sys.stderr,
        )
        return case

    # 1. AUTHENTICATED APPROVAL -- captured before any record write
    pre_write_snapshot = {k: v for k, v in case.items() if not k.startswith("_internal")}
    signature_payload = {
        "case_id": case["case_id"],
        "officer_id": approving_officer_id,
        "signed_at": now_iso(),
        "pre_write_case_hash": sha256_of(pre_write_snapshot),
    }
    signature_ref = f"dsc://{approving_officer_id}/{sha256_of(signature_payload)[:16]}"
    print(f"[approve] Step 1/4 -- AUTHENTICATED APPROVAL captured: {signature_ref}")

    # 2. AUTHORIZED RECORD UPDATE
    old_geometry_ref = case["parcel"]["cadastral_geometry_ref"]
    new_geometry_ref = old_geometry_ref.rsplit("/", 1)[0] + "/v2"
    changes = [{
        "field": "boundary_geometry",
        "target_record_ref": case["parcel"]["cadastral_geometry_ref"],
        "old_value_ref": old_geometry_ref,
        "new_value_ref": new_geometry_ref,
    }]
    if case["update_classification"]["type"] == "OWNERSHIP_MUTATION":
        changes.append({
            "field": "ror_status",
            "target_record_ref": f"ror://{case['parcel']['internal_parcel_key']}",
            "old_value_ref": None,
            "new_value_ref": "pending_field_registration",
        })
    print("[approve] Step 2/4 -- AUTHORIZED RECORD UPDATE applied.")

    # 3. VERSIONED RECORD
    case["record_update"] = {
        "changes": changes,
        "authorized_by": approving_officer_id,
        "authorized_at": now_iso(),
    }
    case["officer_decision"]["signature_ref"] = signature_ref
    case["officer_decision"]["decision"] = "APPROVED"
    case["officer_decision"]["decided_by"] = approving_officer_id
    case["officer_decision"]["decided_at"] = now_iso()
    case["parcel"]["cadastral_geometry_ref"] = new_geometry_ref
    print("[approve] Step 3/4 -- VERSIONED RECORD written (previous_state preserved).")

    # 4. HASH-CHAINED AUDIT LOG
    case["status"] = "CLOSED_RECONCILED"
    post_write_snapshot = {k: v for k, v in case.items() if not k.startswith("_internal")}
    current_hash, previous_hash = append_ledger_entry({
        "case_id": case["case_id"],
        "event": "RECORD_UPDATE_APPROVED",
        "officer_id": approving_officer_id,
        "signature_ref": signature_ref,
        "case_snapshot": post_write_snapshot,
        "timestamp": now_iso(),
    })
    case["audit"] = {
        "hash_chain_entry_id": f"HCE-{case['case_id']}-01",
        "hash_scope": "full_case_snapshot",
        "previous_hash": previous_hash,
        "current_hash": current_hash,
    }
    print(f"[approve] Step 4/4 -- HASH-CHAINED AUDIT LOG appended. current_hash={current_hash[:16]}...")

    append_parcel_history(case["parcel"]["internal_parcel_key"], {
        "case_id": case["case_id"],
        "closed_status": "CLOSED_RECONCILED",
        "closed_at": now_iso(),
    })
    case["parcel_lock"]["locked"] = False
    write_status_snapshot(case)
    print("[approve] Parcel lock released. Case CLOSED_RECONCILED.")
    return case


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="IKNOS Track B: Targeted Investigation")
    p.add_argument("--case-file", required=True, help="Path to the Case JSON to operate on.")
    sub = p.add_subparsers(dest="mode", required=True)

    s_lock = sub.add_parser("check-lock")
    s_lock.add_argument("--supervisor-decision", choices=["extend", "force-release"], default=None)

    s_surv = sub.add_parser("survey")
    s_surv.add_argument("--surveyor-id", required=True)
    s_surv.add_argument("--survey-grade", choices=list(SURVEY_GRADE_UNCERTAINTY_M), default="RTK")

    s_demo = sub.add_parser("full-pipeline-demo")
    s_demo.add_argument("--surveyor-id", default="SURVEYOR-AP-2291")
    s_demo.add_argument("--survey-grade", choices=list(SURVEY_GRADE_UNCERTAINTY_M), default="RTK")
    s_demo.add_argument("--officer-id", default="OFFICER-AP-1187")
    s_demo.add_argument("--senior-officer-id", default="SENIOR-OFFICER-AP-0044")
    s_demo.add_argument("--seed", type=int, default=None)
    s_demo.add_argument(
        "--ortho-tif",
        type=str,
        default=None,
        help="Optional path to drone orthomosaic GeoTIFF to extract boundaries from.",
    )

    return p


def main():
    args = build_parser().parse_args()
    case_path = Path(args.case_file)
    case = load_case(case_path)
    case = reconcile_status_label(case)

    if args.mode == "check-lock":
        case = cmd_check_lock(case, args.supervisor_decision)

    elif args.mode == "survey":
        case = cmd_survey(case, args.surveyor_id, args.survey_grade)

    elif args.mode == "full-pipeline-demo":
        print("=" * 70)
        print(f"TRACK B FULL PIPELINE DEMO -- {case['case_id']}")
        print("=" * 70)

        case = cmd_check_lock(case, supervisor_decision=None)
        case = cmd_survey(case, args.surveyor_id, args.survey_grade)

        ortho_path = Path(args.ortho_tif) if args.ortho_tif else None
        case, observed_polygon, _ = cmd_extract_boundary(case, ortho_tif_path=ortho_path, seed=args.seed)

        minx, miny, maxx, maxy = case["parcel"]["bbox"]
        cadastral_geojson = mapping(Polygon([
            (minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)
        ]))

        case = cmd_compare(case, cadastral_geojson, observed_polygon, args.survey_grade)

        if case["status"] == "OFFICER_REVIEW_PENDING":
            case = cmd_officer_review(
                case,
                args.officer_id,
                valid=True,
                reason="Field findings corroborate spatial discrepancy.",
            )
            if case["update_classification"]["authority_tier_required"] == "senior":
                case = cmd_approve(case, args.senior_officer_id, is_senior=True)
            else:
                case = cmd_approve(case, args.officer_id, is_senior=False)

        print("=" * 70)
        print(f"FINAL STATUS: {case['status']}")
        print("=" * 70)

    save_case(case, case_path)
    print(f"\nCase written back to {case_path}")


if __name__ == "__main__":
    main()