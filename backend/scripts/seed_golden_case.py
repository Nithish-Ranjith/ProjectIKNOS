"""
Seed the deterministic golden-path boundary candidate for one case.

1. Builds candidate.geojson from the cadastral polygon using the transform documented in
   demo_artifacts/<case>/manifest.json (offline, reproducible, committed as a real GeoJSON file).
2. Ingests that stored file through boundary_repository.record_candidate — the SAME code path a
   real U-Net result takes (candidate row -> PostGIS comparison -> metrics -> evidence fusion).

The candidate is labelled SIMULATED_PRECOMPUTED and has no model confidence. Idempotent: re-running
replaces the prior simulated candidate for the case.

Usage:  python -m scripts.seed_golden_case --case-id C01
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))


def build_candidate(cadastral_geometry: dict, params: dict) -> dict:
    from pyproj import Transformer
    from shapely.affinity import translate
    from shapely.geometry import mapping, shape
    from shapely.ops import transform as shp_transform

    from app.spatial_service import utm_srid_for_lon

    poly = shape(cadastral_geometry)
    srid = utm_srid_for_lon(poly.centroid.x)
    fwd = Transformer.from_crs(4326, srid, always_xy=True).transform
    inv = Transformer.from_crs(srid, 4326, always_xy=True).transform
    p = shp_transform(fwd, poly)
    p = translate(p, xoff=params["translate_east_m"], yoff=params["translate_north_m"])
    p = p.buffer(params["buffer_m"], join_style=2)
    p = p.simplify(params["simplify_tolerance_m"], preserve_topology=True)
    return mapping(shp_transform(inv, p))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-id", required=True)
    args = ap.parse_args()

    from app import models, boundary_repository as repo
    from app.database import SessionLocal

    art_dir = BACKEND_ROOT / "demo_artifacts" / args.case_id
    manifest = json.loads((art_dir / "manifest.json").read_text())
    db = SessionLocal()
    try:
        case = db.get(models.Case, args.case_id)
        if not case:
            print(f"case {args.case_id} not found"); return 2
        cad = repo.cadastral_geometry(db, case.parcel_id)

        geometry = build_candidate(cad, manifest["transform"])
        (art_dir / manifest["candidate_file"]).write_text(json.dumps(
            {"type": "Feature", "geometry": geometry,
             "properties": {"provenance": manifest["provenance"], "case_id": args.case_id}}, indent=2))

        mission = (db.query(models.Mission).filter(models.Mission.case_id == args.case_id)
                   .order_by(models.Mission.created_at.desc()).first())
        if not mission:
            drone = db.query(models.User).filter(models.User.role == models.UserRole.SURVEYOR_DRONE).first()
            mission = models.Mission(mission_id=f"MSN-{args.case_id}", case_id=args.case_id,
                                     parcel_id=case.parcel_id, state=models.MissionState.READY,
                                     created_by=drone.user_id)
            db.add(mission); db.commit()

        db.query(models.BoundaryCandidate).filter(
            models.BoundaryCandidate.case_id == args.case_id,
            models.BoundaryCandidate.dataset_label == repo.PROVENANCE_SIMULATED,
        ).delete()
        db.commit()

        stored = json.loads((art_dir / manifest["candidate_file"]).read_text())
        res = repo.record_candidate(db, case, mission.mission_id, stored["geometry"],
                                    repo.PROVENANCE_SIMULATED, "simulated-precomputed", None)
        if res.get("status") != "SUCCESS":
            print("spatial comparison failed:", res); return 3
        fused = repo.fuse_case_evidence(db, case)
        repo.set_pipeline_status(db, case.case_id, "PRECOMPUTED",
                                 "Simulated precomputed candidate (not U-Net output)",
                                 mission_id=mission.mission_id)
        print("metrics:", {k: res[k] for k in ("area_diff_pct", "boundary_shift_m", "iou",
                                                "cadastral_area_m2", "candidate_area_m2", "topology_valid")})
        print("fused score:", fused["confidence_score"], fused["action"])
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
