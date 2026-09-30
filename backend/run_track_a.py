"""
backend/run_track_a.py — The ML Plugin Wrapper / Decision Engine Trigger

This script acts as the entry point for "Track A" (Machine Learning / Computer Vision).
It wraps the core Decision Engine, providing the ML boundary where deep learning models
(U-Net for boundaries, Sentinel-2 PELT for temporal anomalies) will be plugged in.

Usage:
  python run_track_a.py --mode sweep
  python run_track_a.py --mode grievance --parcel AP-07-0103-006-00070 --desc "Unauthorized boundary clearing"
"""

import argparse
import sys
import os
import uuid
from datetime import datetime, timezone

# Adjust path so we can import backend.app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import decision_engine as de
from app.models import CaseStatus, UpdateClass

# --- ML Plugin Boundaries (Track A) ---
# These functions represent the "Hole" where the actual ML models will be added.

def run_unet_boundary_detection(parcel_id: str) -> tuple[float, float, float]:
    """
    Queries the PostGIS spatial_service which compares the latest U-Net derived 
    candidate_boundary against the cadastral parcel geometry.
    """
    print(f"  [ML] Fetching spatial discrepancy for {parcel_id}...")
    from app.database import SessionLocal
    from app import spatial_service
    import json
    
    # In a real sweep, we'd trigger U-Net here if not already run, or read the latest candidate
    # For now, we simulate a candidate boundary that overlaps 80% to exercise the DB logic
    db = SessionLocal()
    try:
        # Get cadastral bbox just to simulate a candidate
        wkt = spatial_service.parcel_bbox_wkt(db, parcel_id)
        # Using a dummy candidate if we can't find one, but spatial_service requires a GeoJSON
        # If we just want to run it, we can create a dummy GeoJSON
        dummy_geojson = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[79.0, 16.0], [79.0, 16.01], [79.01, 16.01], [79.01, 16.0], [79.0, 16.0]]]
            }
        }
        res = spatial_service.compute_spatial_discrepancy(db, parcel_id, dummy_geojson)
        if res["status"] == "SUCCESS":
            return (res["area_diff_pct"] or 0.0, res["boundary_shift_m"] or 0.0, res["iou"] or 0.0)
        return (0.0, 0.0, 0.0)
    finally:
        db.close()

from ml.temporal.gee_fetcher import analyze_parcel_temporal_anomaly

def run_sentinel_pelt_analysis(parcel_id: str) -> float:
    """
    Sentinel-2 NDVI + PELT Temporal Anomaly Detection.
    Fetches S2 imagery from GEE, computes NDVI series, applies PELT, returns instability_score (0.0-1.0).
    """
    print(f"  [ML] Running Sentinel-2 PELT temporal analysis for {parcel_id}...")
    result = analyze_parcel_temporal_anomaly(parcel_id)
    print(f"  [ML] Mode: {result['mode']} | Changepoints: {result['changepoints_detected']} | Instability: {result['instability_score']}")
    return result["instability_score"]

def get_real_records(parcel_id: str) -> de.RecordAvailability:
    """
    Retrieves RoR, Registration, and Mutation status directly from PostgreSQL.
    """
    from app.database import SessionLocal
    from app import models
    db = SessionLocal()
    try:
        ror_present = db.query(models.RoRRecord).filter_by(parcel_id=parcel_id).first() is not None
        reg_present = db.query(models.RegistrationRecord).filter_by(parcel_id=parcel_id).first() is not None
        mutation = db.query(models.MutationRecord).filter_by(parcel_id=parcel_id).order_by(models.MutationRecord.mutation_date.desc()).first()
        mutation_status = mutation.mutation_status.value if mutation else "none"
        
        return de.RecordAvailability(
            ror_present=ror_present,
            registration_present=reg_present,
            mutation_status=mutation_status,
            record_gap_count=0
        )
    finally:
        db.close()


# --- Execution Modes ---

def run_sweep():
    print("\nStarting Proactive Satellite Sweep...")
    # Mock list of parcels to sweep
    parcels = ["AP-07-0103-006-00070", "AP-07-0103-006-00071"]
    
    for parcel in parcels:
        print(f"\n--- Analyzing Parcel: {parcel} ---")
        
        # 1. Run ML
        area_diff, shift_m, iou = run_unet_boundary_detection(parcel)
        temporal_instability = run_sentinel_pelt_analysis(parcel)
        
        # 2. Fetch Records
        records = get_real_records(parcel)
        
        # 3. Construct Engine Input
        spatial = de.SpatialSignals(
            area_diff_pct=area_diff,
            boundary_shift_m=shift_m,
            parcel_area_sqm=10000.0,
            gnss_uncertainty_m=3.5,
            model_iou=iou,
            temporal_instability=temporal_instability
        )
        
        inp = de.EngineInput(
            internal_parcel_key=parcel,
            trigger_source=de.TriggerSource.SATELLITE_PERIODIC,
            records=records,
            spatial=spatial,
            positioning_quality="STANDARD_GNSS",
            active_lock_id=None,
            lock_created_at=None,
            grievance=None
        )
        
        # 4. Execute Engine
        result = de.run(inp)
        
        print(f"  [Engine] Outcome: {result.outcome.value}")
        print(f"  [Engine] Priority Score: {result.priority_score}")
        if result.lock_id:
            print(f"  [Engine] Lock created: {result.lock_id} (Expires: {result.lock_expires_at})")
        if result.required_authority_tier:
            print(f"  [Engine] Required Authority: {result.required_authority_tier.value}")
        if result.audit_entry:
            print(f"  [Engine] Audit Hash: {result.audit_entry.hash_chain_entry}")


def run_grievance(parcel_id: str, desc: str):
    print(f"\nStarting Grievance Intake for {parcel_id}...")
    print(f"Description: {desc}")
    
    # 1. Construct Grievance Context (simulating photo upload)
    grievance = de.GrievanceContext(
        filer_id="CUST-10293",
        parcel_id=parcel_id,
        evidence_items=["photo_1.jpg", "boundary_complaint.txt"],
        recent_grievance_count=0
    )
    
    # 2. Run ML
    area_diff, shift_m, iou = run_unet_boundary_detection(parcel_id)
    temporal_instability = run_sentinel_pelt_analysis(parcel_id)
    
    # 3. Fetch Records
    records = get_real_records(parcel_id)
    
    # 4. Construct Engine Input
    spatial = de.SpatialSignals(
        area_diff_pct=area_diff,
        boundary_shift_m=shift_m,
        parcel_area_sqm=10000.0,
        gnss_uncertainty_m=3.5,
        model_iou=iou,
        temporal_instability=temporal_instability
    )
    
    inp = de.EngineInput(
        internal_parcel_key=parcel_id,
        trigger_source=de.TriggerSource.CITIZEN_GRIEVANCE,
        records=records,
        spatial=spatial,
        positioning_quality="STANDARD_GNSS",
        active_lock_id=None,
        lock_created_at=None,
        grievance=grievance
    )
    
    # 5. Execute Engine
    result = de.run(inp)
    
    print(f"  [Engine] Outcome: {result.outcome.value}")
    print(f"  [Engine] Priority Score: {result.priority_score}")
    if result.lock_id:
        print(f"  [Engine] Lock created: {result.lock_id} (Expires: {result.lock_expires_at})")
    if result.required_authority_tier:
        print(f"  [Engine] Required Authority: {result.required_authority_tier.value}")
    if result.audit_entry:
        print(f"  [Engine] Audit Hash: {result.audit_entry.hash_chain_entry}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Track A ML Runner / Decision Engine Wrapper")
    parser.add_argument("--mode", choices=["sweep", "grievance"], required=True, help="Mode of execution")
    parser.add_argument("--parcel", type=str, help="Parcel ID (required for grievance mode)")
    parser.add_argument("--desc", type=str, help="Grievance description (required for grievance mode)")
    
    args = parser.parse_args()
    
    if args.mode == "sweep":
        run_sweep()
    elif args.mode == "grievance":
        if not args.parcel or not args.desc:
            print("Error: --parcel and --desc are required for grievance mode.")
            sys.exit(1)
        run_grievance(args.parcel, args.desc)
