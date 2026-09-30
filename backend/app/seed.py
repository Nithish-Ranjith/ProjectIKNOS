"""
backend/app/seed.py — Generates synthetic MVP data and the 'Golden Demo'.

Design contracts:
  - DO NOT construct random geometries (it breaks spatial queries in testing).
  - Use simple 10x10 squares spaced out cleanly.
  - Generates users with defined roles.
  - Seeds the 30 base parcels with permutations of discrepancies.
"""
import uuid
import random
from datetime import datetime, timezone
from .database import SessionLocal, engine, Base
from . import models, auth
from .confidence import compute_confidence
from geoalchemy2.elements import WKTElement

def get_geom_square(x_min, y_min, size=0.0001):
    # roughly 10m x 10m at equator
    x_max = x_min + size
    y_max = y_min + size
    wkt = f"POLYGON(({x_min} {y_min}, {x_max} {y_min}, {x_max} {y_max}, {x_min} {y_max}, {x_min} {y_min}))"
    return WKTElement(wkt, srid=4326)

def seed_db():
    print("Dropping and recreating tables...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # 1. Users
    print("Seeding Users...")
    users = [
        models.User(user_id="U_CUST_1", username="customer1", phone="9876543210", hashed_password=auth.hash_password("pass"), role=models.UserRole.CUSTOMER, authority_tier=0, owned_parcel_ids=["P01", "P02", "P30"]),
        models.User(user_id="U_DRONE_1", username="drone1", phone="9876543211", hashed_password=auth.hash_password("pass"), role=models.UserRole.SURVEYOR_DRONE, authority_tier=1, dgca_credential="DGCA-DR-001"),
        models.User(user_id="U_FIELD_1", username="field1", phone="9876543212", hashed_password=auth.hash_password("pass"), role=models.UserRole.SURVEYOR_FIELD, authority_tier=1, govt_id_ref="GOVT-SV-100"),
        models.User(user_id="U_SENIOR_1", username="senior1", phone="9876543213", hashed_password=auth.hash_password("pass"), role=models.UserRole.SENIOR_FIELD, authority_tier=2, govt_id_ref="GOVT-SR-01"),
    ]
    db.add_all(users)
    db.commit()

    # 2. Parcels (30 synthetic parcels)
    print("Seeding 30 Parcels...")
    parcels_to_add = []
    rors_to_add = []
    mutations_to_add = []
    registrations_to_add = []
    cases_to_add = []
    
    # 5 base variations
    scenarios = [
        {"area": 0, "shift": 0, "reg": "present", "mut": "approved", "s2": 0.0}, # Clean
        {"area": 30, "shift": 5.0, "reg": "present", "mut": "approved", "s2": 0.1}, # Spatial only
        {"area": 0, "shift": 0, "reg": "missing", "mut": "approved", "s2": 0.2}, # Registration missing
        {"area": 0, "shift": 0, "reg": "present", "mut": "pending", "s2": 0.3}, # Mutation pending
        {"area": 15, "shift": 1.0, "reg": "present", "mut": "approved", "s2": 0.8}, # Temporal anomaly
        {"area": 40, "shift": 8.0, "reg": "missing", "mut": "pending", "s2": 0.9}, # Absolute mess (Golden demo)
    ]
    
    start_x = 77.0 # longitude
    start_y = 28.0 # latitude (Delhi approx)

    for i in range(1, 31):
        pid = f"P{i:02d}"
        
        # assign scenario by modulo
        scen = scenarios[i % 6]
        
        # create geometry in a grid pattern
        x = start_x + (i % 6) * 0.0005
        y = start_y + (i // 6) * 0.0005
        
        p = models.Parcel(
            parcel_id=pid,
            ulpin=f"ULPIN-{i:06d}" if i % 4 != 0 else None, # 25% missing ULPIN
            geom=get_geom_square(x, y),
            source="cadastral",
            area_sqm=100.0
        )
        parcels_to_add.append(p)
        
        ror = models.RoR(
            id=f"R{i:02d}", parcel_id=pid,
            owner_name=f"Owner of {pid}",
            khasra_no=f"KH-{i*10}",
            area_recorded=100.0,
            status="present" if i % 5 != 0 else "missing" # 20% RoR missing entirely
        )
        rors_to_add.append(ror)
        
        mut = models.Mutation(
            id=f"M{i:02d}", parcel_id=pid,
            mutation_status=scen["mut"]
        )
        mutations_to_add.append(mut)
        
        reg = models.Registration(
            id=f"RG{i:02d}", parcel_id=pid,
            status=scen["reg"]
        )
        registrations_to_add.append(reg)
        
        # Calculate confidence score
        # Note: we use "RTK_FIX" just to let the spatial signal through cleanly for the demo
        conf_res = compute_confidence(
            area_diff_pct=scen["area"],
            boundary_shift_m=scen["shift"],
            parcel_area_sqm=100.0,
            registration_status=scen["reg"],
            mutation_status=scen["mut"],
            instability_score=scen["s2"],
            positioning_quality="RTK_FIX"
        )
        
        # Create case only if verification required, or for P30 (always case)
        if conf_res["action"] == "field_verification_required" or pid == "P30":
            case = models.Case(
                case_id=f"C{i:02d}",
                parcel_id=pid,
                status=models.CaseStatus.OPEN,
                confidence_score=conf_res["confidence_score"],
                action=conf_res["action"],
                case_data={"reasoning_trace": conf_res["reasoning_trace"]}
            )
            cases_to_add.append(case)
            
    db.add_all(parcels_to_add)
    db.commit()
    db.add_all(rors_to_add)
    db.add_all(mutations_to_add)
    db.add_all(registrations_to_add)
    db.add_all(cases_to_add)
    db.commit()

    print(f"Seeded {len(parcels_to_add)} parcels, {len(cases_to_add)} cases.")
    db.close()

if __name__ == "__main__":
    seed_db()
