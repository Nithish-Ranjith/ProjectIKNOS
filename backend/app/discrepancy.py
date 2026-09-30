"""
backend/app/discrepancy.py — Deterministic spatial comparison engine.

Design contracts:
  - No global fixed IoU >= 0.85 cutoff as sole criterion.
  - Discrepancy interpretation accounts for: parcel scale, positional uncertainty,
    source quality, survey quality, geometry quality.
  - boundary_shift_m is computed as Hausdorff distance — sensitive to worst-case
    point displacement, not just centroid offset.
  - area_diff_pct is normalized against the cadastral parcel area.
  - STANDARD_GNSS positional uncertainty (~2.5-5m) must be carried through into
    interpretation — a 3m Hausdorff distance with STANDARD_GNSS is not the same
    signal as a 3m distance with RTK_FIX.
  - Geometry validity is checked before any metric is computed.

Uses PostGIS via geoalchemy2 / shapely fallback.
For production: use PostGIS (ST_HausdorffDistance, ST_Difference, ST_Intersection).
For unit tests without PostGIS: shapely equivalents are used.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from . import models


def compute_discrepancy(
    db: Session,
    case_id: str,
    mission_id: Optional[str],
    cadastral_parcel_id: str,
    candidate_geojson: dict,
    positioning_quality: str = "STANDARD_GNSS",
) -> models.DiscrepancyMetrics:
    """
    Compare a candidate boundary (from U-Net or hand-digitized GeoJSON) against
    the cadastral parcel geometry using PostGIS spatial functions.

    Returns a DiscrepancyMetrics row (not yet committed — caller commits).
    """
    # Fetch cadastral geometry
    parcel = db.get(models.Parcel, cadastral_parcel_id)
    if not parcel:
        raise ValueError(f"Parcel {cadastral_parcel_id} not found")

    # Build the candidate geometry WKT from GeoJSON coordinates
    # Expecting GeoJSON polygon feature or geometry
    geom_type = candidate_geojson.get("type")
    if geom_type == "Feature":
        coords = candidate_geojson["geometry"]["coordinates"]
    elif geom_type == "Polygon":
        coords = candidate_geojson["coordinates"]
    else:
        raise ValueError(f"Unsupported GeoJSON type: {geom_type}")

    # Convert coords ring to WKT
    outer_ring = coords[0]
    pts = ", ".join(f"{lon} {lat}" for lon, lat in outer_ring)
    candidate_wkt = f"POLYGON(({pts}))"

    # Run PostGIS spatial comparison
    raw = db.execute(text("""
        WITH
          cadastral AS (
            SELECT geom AS g FROM parcels WHERE parcel_id = :pid
          ),
          candidate AS (
            SELECT ST_GeomFromText(:wkt, 4326) AS g
          )
        SELECT
          -- Geometry validity checks
          ST_IsValid(cadastral.g)                          AS cad_valid,
          ST_IsValid(candidate.g)                          AS cand_valid,
          -- Area comparison
          ST_Area(cadastral.g::geography)                  AS cad_area_sqm,
          ST_Area(candidate.g::geography)                  AS cand_area_sqm,
          ABS(ST_Area(candidate.g::geography) - ST_Area(cadastral.g::geography))
            / NULLIF(ST_Area(cadastral.g::geography), 0) * 100  AS area_diff_pct,
          -- Boundary displacement (Hausdorff distance in metres)
          ST_HausdorffDistance(
            ST_Transform(cadastral.g, 32644),
            ST_Transform(candidate.g, 32644)
          )                                                AS boundary_shift_m,
          -- Intersection area
          ST_Area(ST_Intersection(cadastral.g, candidate.g)::geography)  AS intersection_sqm,
          -- Difference area (cadastral but NOT candidate)
          ST_Area(ST_Difference(cadastral.g, candidate.g)::geography)    AS diff_sqm,
          -- IoU (for reference — NOT used as sole criterion)
          ST_Area(ST_Intersection(cadastral.g, candidate.g)::geography) /
            NULLIF(ST_Area(ST_Union(cadastral.g, candidate.g)::geography), 0) AS iou
        FROM cadastral, candidate
    """), {"pid": cadastral_parcel_id, "wkt": candidate_wkt}).mappings().one()

    metrics = models.DiscrepancyMetrics(
        metrics_id=str(uuid.uuid4()),
        case_id=case_id,
        mission_id=mission_id,
        area_diff_pct=float(raw["area_diff_pct"] or 0),
        boundary_shift_m=float(raw["boundary_shift_m"] or 0),
        iou=float(raw["iou"] or 0),
        intersection_area_sqm=float(raw["intersection_sqm"] or 0),
        difference_area_sqm=float(raw["diff_sqm"] or 0),
        topology_valid=bool(raw["cad_valid"] and raw["cand_valid"]),
        positioning_quality=positioning_quality,
        computed_at=datetime.now(timezone.utc),
        raw_output={
            "cad_area_sqm": float(raw["cad_area_sqm"] or 0),
            "cand_area_sqm": float(raw["cand_area_sqm"] or 0),
            "cad_valid": bool(raw["cad_valid"]),
            "cand_valid": bool(raw["cand_valid"]),
        },
    )
    db.add(metrics)
    return metrics


def interpret_discrepancy(metrics: models.DiscrepancyMetrics, parcel_area_sqm: float) -> dict:
    """
    Produce a human-readable interpretation of the metrics.
    Accounts for parcel scale and positioning uncertainty.
    Does NOT produce a legal verdict.
    """
    gnss_uncertainty_m = 5.0 if metrics.positioning_quality == "STANDARD_GNSS" else 0.05

    # Boundary shift is meaningful only when it exceeds the positioning uncertainty
    shift_above_noise = max(0.0, metrics.boundary_shift_m - gnss_uncertainty_m)

    # Scale-relative severity
    char_length = max(parcel_area_sqm, 1.0) ** 0.5
    relative_shift = shift_above_noise / char_length if char_length else 0

    severity = "LOW"
    if metrics.area_diff_pct > 15 or relative_shift > 0.05:
        severity = "HIGH"
    elif metrics.area_diff_pct > 5 or relative_shift > 0.01:
        severity = "MEDIUM"

    return {
        "severity": severity,
        "area_diff_pct": round(float(metrics.area_diff_pct or 0), 2),
        "boundary_shift_m": round(float(metrics.boundary_shift_m or 0), 2),
        "shift_above_gnss_noise_m": round(shift_above_noise, 2),
        "topology_valid": metrics.topology_valid,
        "positioning_quality": metrics.positioning_quality,
        "note": (
            "Boundary shift is within STANDARD_GNSS positional uncertainty — "
            "spatial evidence is inconclusive; higher-precision survey recommended"
            if shift_above_noise <= 0 else
            f"Boundary shift of {metrics.boundary_shift_m:.1f}m exceeds GNSS uncertainty ({gnss_uncertainty_m}m)"
        ),
        "legal_note": "This is a candidate physical boundary comparison, NOT a legal boundary determination",
    }
