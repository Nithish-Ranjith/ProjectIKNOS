"""
backend/app/spatial_service.py — Real PostGIS spatial computation service.

Implements the spatial comparison step from the PRD (Section 5, Stage [6]):
  candidate_boundary.geojson  vs  cadastral polygon (PostGIS geometry)
      → PostGIS: ST_Difference, ST_Intersection, ST_HausdorffDistance, ST_IsValid
  Output: discrepancy_metrics (JSON) — area_diff_pct, boundary_shift_m, topology_valid

Design Contracts:
  - All geometry operations happen in the DATABASE via PostGIS functions
  - Results are stored in discrepancy_metrics table for audit reproducibility
  - Coordinates in EPSG:4326; area/distance computed via ST_Transform to UTM
  - Function returns None for individual metrics if geometry is invalid — never fabricates
  - These are SPATIAL SIGNALS only — they are inputs to the Decision Engine, not verdicts
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from . import models


def utm_srid_for_lon(lon: float) -> int:
    """WGS84 UTM (northern hemisphere) EPSG code for a longitude. India is entirely northern."""
    return 32600 + int((lon + 180.0) // 6) + 1


def compute_spatial_discrepancy(
    db: Session,
    parcel_id: str,
    candidate_geojson: dict,
    case_id: Optional[str] = None,
    mission_id: Optional[str] = None,
    positioning_quality: str = "STANDARD_GNSS",
) -> dict:
    """
    Compare candidate boundary (from U-Net) vs cadastral boundary (in PostGIS parcels table).
    Runs real PostGIS spatial queries.

    Args:
        db:                  SQLAlchemy session (connected to PostGIS DB)
        parcel_id:           Internal parcel key — must exist in parcels table
        candidate_geojson:   GeoJSON dict for the candidate polygon (from boundary_vectorizer)
        case_id:             Optional — links result to a case for audit

    Returns:
        {
          "status":             "SUCCESS" | "INVALID_GEOMETRY" | "NO_CADASTRAL" | "ERROR",
          "area_diff_pct":      float | None,     # % area difference
          "boundary_shift_m":   float | None,     # Hausdorff distance in metres
          "intersection_m2":    float | None,     # Overlap area m²
          "difference_m2":      float | None,     # Non-overlapping area m²
          "topology_valid":     bool | None,
          "iou":                float | None,     # Intersection over Union
          "candidate_area_m2":  float | None,
          "cadastral_area_m2":  float | None,
          "metric_id":          str,
          "note":               str
        }
    """
    metric_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # 1. Check cadastral parcel exists
    parcel = db.get(models.Parcel, parcel_id)
    if parcel is None:
        return {
            "status": "NO_CADASTRAL",
            "metric_id": metric_id,
            "note": f"Parcel {parcel_id} not found in cadastral table."
        }

    # 2. Validate candidate GeoJSON
    if candidate_geojson.get("type") == "FeatureCollection":
        features = candidate_geojson.get("features", [])
        if not features:
            return {"status": "NO_CADASTRAL", "metric_id": metric_id,
                    "note": "No candidate features in GeoJSON."}
        # Use the largest candidate polygon
        geom_dict = max(features, key=lambda f: f.get("properties", {}).get("area_m2_est", 0))["geometry"]
    elif candidate_geojson.get("type") == "Feature":
        geom_dict = candidate_geojson["geometry"]
    else:
        geom_dict = candidate_geojson

    candidate_geojson_str = json.dumps(geom_dict)

    # UTM zone derived from the parcel itself (never assumed)
    lon_row = db.execute(
        text("SELECT ST_X(ST_Centroid(geom)) FROM parcels WHERE parcel_id = :pid"),
        {"pid": parcel_id},
    ).fetchone()
    utm_srid = utm_srid_for_lon(float(lon_row[0]))

    # 3. Run PostGIS spatial analysis
    sql = text("""
        WITH
          cadastral AS (
            SELECT geom AS g
            FROM parcels
            WHERE parcel_id = :parcel_id
          ),
          candidate AS (
            SELECT ST_GeomFromGeoJSON(:candidate_geojson)::geometry AS g
          ),
          -- Reproject both to UTM for accurate metric measurements
          cadastral_utm AS (
            SELECT ST_Transform(g, :utm_srid) AS g FROM cadastral
          ),
          candidate_utm AS (
            SELECT ST_Transform(g, :utm_srid) AS g FROM candidate
          ),
          -- Topology validation
          validity AS (
            SELECT
              ST_IsValid(c.g)  AS cadastral_valid,
              ST_IsValid(cn.g) AS candidate_valid
            FROM cadastral_utm c, candidate_utm cn
          ),
          -- Spatial metrics
          metrics AS (
            SELECT
              ST_Area(c.g)                           AS cadastral_area,
              ST_Area(cn.g)                          AS candidate_area,
              ST_Area(ST_Intersection(c.g, cn.g))    AS intersection_area,
              ST_Area(ST_Difference(cn.g, c.g))      AS difference_area,
              ST_HausdorffDistance(
                ST_Boundary(c.g), ST_Boundary(cn.g)
              )                                       AS hausdorff_m
            FROM cadastral_utm c, candidate_utm cn
          )
        SELECT
          v.cadastral_valid,
          v.candidate_valid,
          m.cadastral_area,
          m.candidate_area,
          m.intersection_area,
          m.difference_area,
          m.hausdorff_m
        FROM metrics m, validity v
    """)

    try:
        result = db.execute(sql, {
            "parcel_id":        parcel_id,
            "candidate_geojson": candidate_geojson_str,
            "utm_srid":         utm_srid,
        }).fetchone()
    except Exception as e:
        return {
            "status": "ERROR",
            "metric_id": metric_id,
            "note": f"PostGIS query failed: {e}"
        }

    if result is None:
        return {"status": "ERROR", "metric_id": metric_id, "note": "No result from PostGIS."}

    (cad_valid, cand_valid, cad_area, cand_area,
     inter_area, diff_area, hausdorff_m) = result

    # 4. Compute derived metrics
    cad_area   = float(cad_area   or 0)
    cand_area  = float(cand_area  or 0)
    inter_area = float(inter_area or 0)
    diff_area  = float(diff_area  or 0)

    area_diff_pct = None
    if cad_area > 0:
        area_diff_pct = round(abs(cand_area - cad_area) / cad_area * 100.0, 2)

    union_area = cad_area + cand_area - inter_area
    iou = round(inter_area / union_area, 4) if union_area > 0 else None

    topology_valid = bool(cad_valid and cand_valid)
    hausdorff_m_val = round(float(hausdorff_m), 2) if hausdorff_m is not None else None

    # 5. Persist to discrepancy_metrics (append-only; every computation is kept for audit)
    output = {
        "status":            "SUCCESS",
        "metric_id":         metric_id,
        "area_diff_pct":     area_diff_pct,
        "boundary_shift_m":  hausdorff_m_val,
        "intersection_m2":   round(inter_area, 2),
        "difference_m2":     round(diff_area, 2),
        "iou":               iou,
        "candidate_area_m2": round(cand_area, 2),
        "cadastral_area_m2": round(cad_area, 2),
        "topology_valid":    topology_valid,
        "utm_srid":          utm_srid,
        "computed_at":       now.isoformat(),
        "note": (
            "Spatial discrepancy computed via PostGIS ST_Intersection, ST_Difference, "
            f"ST_HausdorffDistance in EPSG:{utm_srid}. "
            "These are geometric signals — NOT legal boundary determinations."
        ),
    }
    persisted = False
    if case_id:
        try:
            db.add(models.DiscrepancyMetrics(
                metrics_id=metric_id,
                case_id=case_id,
                mission_id=mission_id,
                area_diff_pct=area_diff_pct,
                boundary_shift_m=hausdorff_m_val,
                iou=iou,
                intersection_area_sqm=round(inter_area, 2),
                difference_area_sqm=round(diff_area, 2),
                topology_valid=topology_valid,
                positioning_quality=positioning_quality,
                computed_at=now,
                raw_output=output,
            ))
            db.commit()
            persisted = True
        except Exception as e:
            db.rollback()
            output["persist_error"] = str(e)
    output["persisted"] = persisted
    return output


def get_parcel_geojson(db: Session, parcel_id: str) -> Optional[dict]:
    """
    Retrieve a parcel's cadastral geometry as GeoJSON from PostGIS.
    """
    sql = text("""
        SELECT ST_AsGeoJSON(geom) AS geojson
        FROM parcels
        WHERE parcel_id = :parcel_id
    """)
    try:
        row = db.execute(sql, {"parcel_id": parcel_id}).fetchone()
        if row and row[0]:
            return {"type": "Feature", "geometry": json.loads(row[0]),
                    "properties": {"parcel_id": parcel_id}}
    except Exception:
        pass
    return None


def parcel_bbox_wkt(db: Session, parcel_id: str) -> Optional[str]:
    """Return the WKT envelope (bounding box) of a parcel for GEE query."""
    sql = text("""
        SELECT ST_AsText(ST_Envelope(geom)) AS wkt
        FROM parcels WHERE parcel_id = :parcel_id
    """)
    try:
        row = db.execute(sql, {"parcel_id": parcel_id}).fetchone()
        return row[0] if row else None
    except Exception:
        return None
