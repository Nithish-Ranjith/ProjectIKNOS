"""
backend/app/boundary_repository.py — single source of truth for a case's geometry state.

Every consumer (geometry-layers API, evidence API, report PDF, U-Net job, seed
script) goes through this module so the UI, the evidence panel and the PDF can
never disagree about areas, provenance or which candidate is "current".

Provenance vocabulary (stored in BoundaryCandidate.dataset_label):
  REAL_INFERENCE        candidate produced by the ONNX U-Net on a real orthomosaic
  SIMULATED_PRECOMPUTED candidate generated offline by scripts/seed_golden_case.py
                        from a documented transform of the cadastral polygon.
                        It is NOT model output and carries no confidence value.

Candidates are always CANDIDATE PHYSICAL BOUNDARIES, never legal boundaries.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models, spatial_service

PROVENANCE_REAL = "REAL_INFERENCE"
PROVENANCE_SIMULATED = "SIMULATED_PRECOMPUTED"
PROVENANCE_SPECTRAL = "SPECTRAL_EDGE_DETECTION"

# Domain policy: below this model-output statistic a prediction is flagged
# LOW_CONFIDENCE and must be treated as unusable evidence until a human reviews it.
MIN_USABLE_MODEL_CONFIDENCE = 0.5


def provenance_of(candidate: models.BoundaryCandidate) -> str:
    if candidate.dataset_label == PROVENANCE_SIMULATED:
        return PROVENANCE_SIMULATED
    if candidate.dataset_label == PROVENANCE_SPECTRAL:
        return PROVENANCE_SPECTRAL
    return PROVENANCE_REAL


def cadastral_geometry(db: Session, parcel_id: str) -> Optional[dict]:
    """GeoJSON geometry (EPSG:4326) of the cadastral polygon, or None."""
    raw = db.execute(
        select(func.ST_AsGeoJSON(models.Parcel.geom)).where(models.Parcel.parcel_id == parcel_id)
    ).scalar()
    return json.loads(raw) if raw else None


def latest_candidate(db: Session, case_id: str) -> Optional[dict]:
    row = (
        db.query(models.BoundaryCandidate)
        .filter(models.BoundaryCandidate.case_id == case_id)
        .order_by(models.BoundaryCandidate.computed_at.desc())
        .first()
    )
    if not row:
        return None
    conf = float(row.confidence_score) if row.confidence_score is not None else None
    prov = provenance_of(row)
    return {
        "candidate_id": row.candidate_id,
        "mission_id": row.mission_id,
        "geometry": row.boundary_geojson,
        "provenance": prov,
        "model_version": row.model_version,
        "dataset_label": row.dataset_label,
        "confidence": conf,
        "low_confidence": (prov == PROVENANCE_REAL and conf is not None
                           and conf < MIN_USABLE_MODEL_CONFIDENCE),
        "computed_at": row.computed_at.isoformat() if row.computed_at else None,
    }


def latest_metrics(db: Session, case_id: str) -> Optional[dict]:
    row = (
        db.query(models.DiscrepancyMetrics)
        .filter(models.DiscrepancyMetrics.case_id == case_id)
        .order_by(models.DiscrepancyMetrics.computed_at.desc())
        .first()
    )
    if not row:
        return None
    raw = row.raw_output or {}
    f = lambda v: float(v) if v is not None else None  # noqa: E731
    return {
        "metrics_id": row.metrics_id,
        "area_diff_pct": f(row.area_diff_pct),
        "boundary_shift_m": f(row.boundary_shift_m),
        "iou": f(row.iou),
        "intersection_m2": f(row.intersection_area_sqm),
        "difference_m2": f(row.difference_area_sqm),
        "cadastral_area_m2": raw.get("cadastral_area_m2"),
        "candidate_area_m2": raw.get("candidate_area_m2"),
        "topology_valid": row.topology_valid,
        "positioning_quality": row.positioning_quality,
        "utm_srid": raw.get("utm_srid"),
        "computed_at": row.computed_at.isoformat() if row.computed_at else None,
    }


def set_pipeline_status(db: Session, case_id: str, status: str, message: str, **extra) -> None:
    """Record explicit boundary-pipeline state on the case (QUEUED/RUNNING/SUCCESS/NO_DETECTION/...)."""
    case = db.get(models.Case, case_id)
    if not case:
        return
    cd = dict(case.case_data or {})
    cd["boundary_pipeline"] = {
        "status": status,
        "message": message,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **extra,
    }
    case.case_data = cd
    db.commit()


def record_candidate(
    db: Session,
    case: models.Case,
    mission_id: str,
    geometry: dict,
    provenance: str,
    model_version: Optional[str],
    confidence: Optional[float],
) -> dict:
    """
    Store a candidate, compute PostGIS discrepancy against the cadastral polygon, and
    mirror the computed numbers into case_data so list views stay consistent.
    Returns the spatial_service result dict (status != SUCCESS means nothing is stored
    as evidence and the candidate row is rolled back).
    """
    cand = models.BoundaryCandidate(
        candidate_id=str(uuid.uuid4()),
        mission_id=mission_id,
        case_id=case.case_id,
        boundary_geojson=geometry,
        confidence_score=confidence,
        model_version=model_version,
        dataset_label=provenance if provenance in (
            PROVENANCE_SIMULATED, PROVENANCE_SPECTRAL
        ) else "TRANSFER_LEARNED_UNVALIDATED",
    )
    db.add(cand)
    db.flush()
    res = spatial_service.compute_spatial_discrepancy(
        db, case.parcel_id, {"type": "Feature", "geometry": geometry, "properties": {}},
        case_id=case.case_id, mission_id=mission_id,
    )
    if res.get("status") != "SUCCESS":
        db.delete(cand)
        db.commit()
        return res
    if not res.get("topology_valid"):
        res["status"] = "INVALID_GEOMETRY"
        res["note"] = "Candidate or cadastral geometry failed ST_IsValid; candidate rejected."
        db.delete(cand)
        db.commit()
        return res
    cd = dict(case.case_data or {})
    cd["spatial_mismatch_pct"] = res["area_diff_pct"]
    cd["boundary_shift_m"] = res["boundary_shift_m"]
    cd["spatial_source"] = "COMPUTED_POSTGIS"
    case.case_data = cd
    db.commit()
    return res


def fuse_case_evidence(db: Session, case: models.Case, positioning_quality: str = "STANDARD_GNSS") -> dict:
    """
    Re-run the deterministic evidence fusion for a case using COMPUTED spatial metrics and the
    record tables (RoR / Mutation / Registration). Updates the case score, action and reasoning
    trace, and appends an audit event. Returns the confidence result.

    Positioning quality defaults to STANDARD_GNSS per the PRD (no RTK in the MVP).
    """
    from . import audit_service
    from .confidence import compute_confidence

    metrics = latest_metrics(db, case.case_id)
    if not metrics or metrics["area_diff_pct"] is None or metrics["boundary_shift_m"] is None:
        raise ValueError("No computed spatial metrics for case; cannot fuse evidence")

    parcel = db.get(models.Parcel, case.parcel_id)
    cd = dict(case.case_data or {})

    reg = (db.query(models.Registration).filter(models.Registration.parcel_id == case.parcel_id).first())
    mut = (db.query(models.Mutation).filter(models.Mutation.parcel_id == case.parcel_id).first())
    registration_status = reg.status if reg else ("missing" if cd.get("registration_conflict") else "present")
    mutation_status = mut.mutation_status if mut else cd.get("mutation_status", "none")
    instability = (cd.get("temporal_signal") or {}).get("instability_score")

    result = compute_confidence(
        area_diff_pct=metrics["area_diff_pct"],
        boundary_shift_m=metrics["boundary_shift_m"],
        parcel_area_sqm=float(metrics["cadastral_area_m2"] or (parcel.area_sqm if parcel else 0) or 0),
        registration_status=registration_status,
        mutation_status=mutation_status,
        instability_score=instability,
        positioning_quality=positioning_quality,
    )
    cd["reasoning_trace"] = result["reasoning_trace"]
    cd["positioning_quality"] = positioning_quality
    case.case_data = cd
    case.confidence_score = result["confidence_score"]
    case.action = result["action"]
    audit_service.append_event(
        db, case.case_id, "EVIDENCE_FUSED",
        {"risk_score": result["risk_score"], "action": result["action"],
         "metrics_id": metrics["metrics_id"], "positioning_quality": positioning_quality},
    )
    db.commit()
    return result
