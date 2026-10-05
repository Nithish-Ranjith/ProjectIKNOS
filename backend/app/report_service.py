"""
backend/app/report_service.py — builds the PDF report context from the SAME repository
functions the UI uses (boundary_repository), so the report cannot disagree with the UI.

No network images, no static-map tokens: the boundary comparison is rendered as inline SVG
directly from the stored geometries (local equirectangular projection, metres).
"""
from __future__ import annotations

import math
from typing import Optional

from sqlalchemy.orm import Session

from . import boundary_repository as repo
from . import models

SVG_WIDTH_PX = 520
SVG_HEIGHT_PX = 380
SVG_MARGIN_PX = 24
CADASTRAL_STROKE = "#b45309"
CANDIDATE_STROKE = "#0e7490"


def _rings(geometry: dict) -> list[list[tuple[float, float]]]:
    if not geometry:
        return []
    t, c = geometry.get("type"), geometry.get("coordinates")
    if t == "Polygon":
        return [[(p[0], p[1]) for p in ring] for ring in c]
    if t == "MultiPolygon":
        return [[(p[0], p[1]) for p in ring] for poly in c for ring in poly]
    return []


def render_comparison_svg(cadastral: Optional[dict], candidate: Optional[dict]) -> Optional[str]:
    """Inline SVG with both geometries in one shared metric frame. None if no cadastral geometry."""
    cad = _rings(cadastral)
    if not cad:
        return None
    cand = _rings(candidate) if candidate else []
    pts = [p for ring in cad + cand for p in ring]
    lat0 = sum(p[1] for p in pts) / len(pts)
    kx = 111_320.0 * math.cos(math.radians(lat0))
    ky = 111_320.0

    def to_m(p):
        return (p[0] * kx, p[1] * ky)

    mpts = [to_m(p) for p in pts]
    minx, maxx = min(p[0] for p in mpts), max(p[0] for p in mpts)
    miny, maxy = min(p[1] for p in mpts), max(p[1] for p in mpts)
    span_x, span_y = max(maxx - minx, 1e-6), max(maxy - miny, 1e-6)
    scale = min((SVG_WIDTH_PX - 2 * SVG_MARGIN_PX) / span_x, (SVG_HEIGHT_PX - 2 * SVG_MARGIN_PX) / span_y)
    off_x = (SVG_WIDTH_PX - span_x * scale) / 2
    off_y = (SVG_HEIGHT_PX - span_y * scale) / 2

    def to_px(p):
        mx, my = to_m(p)
        return (off_x + (mx - minx) * scale, SVG_HEIGHT_PX - (off_y + (my - miny) * scale))

    def path(rings):
        return " ".join(
            "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in map(to_px, ring)) + " Z" for ring in rings
        )

    scale_bar_m = 10 ** math.floor(math.log10(max(span_x / 3, 1)))
    bar_px = scale_bar_m * scale
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_WIDTH_PX}" height="{SVG_HEIGHT_PX}" '
        f'viewBox="0 0 {SVG_WIDTH_PX} {SVG_HEIGHT_PX}" style="background:#f8fafc;border:1px solid #cbd5e1">',
        f'<path d="{path(cad)}" fill="{CADASTRAL_STROKE}" fill-opacity="0.12" stroke="{CADASTRAL_STROKE}" '
        f'stroke-width="2" stroke-dasharray="6 3"/>',
    ]
    if cand:
        parts.append(
            f'<path d="{path(cand)}" fill="{CANDIDATE_STROKE}" fill-opacity="0.18" stroke="{CANDIDATE_STROKE}" stroke-width="2"/>'
        )
    parts.append(
        f'<line x1="{SVG_MARGIN_PX}" y1="{SVG_HEIGHT_PX - 10}" x2="{SVG_MARGIN_PX + bar_px:.1f}" '
        f'y2="{SVG_HEIGHT_PX - 10}" stroke="#334155" stroke-width="2"/>'
        f'<text x="{SVG_MARGIN_PX + bar_px + 6:.1f}" y="{SVG_HEIGHT_PX - 6}" font-size="10" '
        f'font-family="monospace" fill="#334155">{scale_bar_m:g} m</text>'
    )
    parts.append("</svg>")
    return "".join(parts)


def build_report_context(db: Session, case: models.Case) -> dict:
    parcel = db.get(models.Parcel, case.parcel_id)
    cad_geom = repo.cadastral_geometry(db, case.parcel_id)
    candidate = repo.latest_candidate(db, case.case_id)
    metrics = repo.latest_metrics(db, case.case_id)
    cd = case.case_data or {}

    ror = db.query(models.RoR).filter(models.RoR.parcel_id == case.parcel_id).first()
    mut = db.query(models.Mutation).filter(models.Mutation.parcel_id == case.parcel_id).first()
    reg = db.query(models.Registration).filter(models.Registration.parcel_id == case.parcel_id).first()

    audit_rows = (
        db.query(models.AuditLog).filter(models.AuditLog.case_id == case.case_id)
        .order_by(models.AuditLog.seq.asc()).all()
    )
    verifications = (
        db.query(models.FieldVerification).filter(models.FieldVerification.case_id == case.case_id)
        .order_by(models.FieldVerification.timestamp.asc()).all()
    )
    approvals = (
        db.query(models.Approval).filter(models.Approval.case_id == case.case_id)
        .order_by(models.Approval.approved_at.asc()).all()
    )
    updates = (
        db.query(models.RecordUpdate).filter(models.RecordUpdate.case_id == case.case_id)
        .order_by(models.RecordUpdate.applied_at.asc()).all()
    )
    temporal = cd.get("temporal_signal") or {}

    return {
        "case": case,
        "parcel": parcel,
        "candidate": candidate,
        "metrics": metrics,
        "comparison_svg": render_comparison_svg(cad_geom, candidate["geometry"] if candidate else None),
        "ror": ror, "mutation": mut, "registration": reg,
        "temporal": temporal,
        "temporal_source": cd.get("temporal_source", "SEEDED_SYNTHETIC"),
        "reasoning_trace": cd.get("reasoning_trace", []),
        "pipeline": cd.get("boundary_pipeline"),
        "verifications": verifications,
        "approvals": approvals,
        "record_updates": updates,
        "audit_rows": audit_rows,
        "audit_tip": audit_rows[-1].current_hash if audit_rows else None,
        "audit_count": len(audit_rows),
    }
