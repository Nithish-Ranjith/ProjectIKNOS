import json
import os
from sqlalchemy import create_engine
from app.database import SessionLocal, engine, Base
from app import models, auth
from app.confidence import compute_confidence
from geoalchemy2.elements import WKTElement

def get_geom_from_geojson(geometry):
    # Convert GeoJSON polygon to WKT
    coords = geometry['coordinates'][0]
    coord_str = ", ".join([f"{c[0]} {c[1]}" for c in coords])
    wkt = f"POLYGON(({coord_str}))"
    return WKTElement(wkt, srid=4326)

def seed_db():
    print("Dropping and recreating tables...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # 1. Users
    print("Seeding Users...")
    users = [
        models.User(user_id="U_CUST_1", username="customer1", phone="9876543210", hashed_password=auth.hash_password("pass"), role=models.UserRole.CUSTOMER, authority_tier=0, owned_parcel_ids=[]),
        models.User(user_id="U_DRONE_1", username="drone1", phone="9876543211", hashed_password=auth.hash_password("pass"), role=models.UserRole.SURVEYOR_DRONE, authority_tier=1, dgca_credential="DGCA-DR-001"),
        models.User(user_id="U_FIELD_1", username="field1", phone="9876543212", hashed_password=auth.hash_password("pass"), role=models.UserRole.SURVEYOR_FIELD, authority_tier=1, govt_id_ref="GOVT-SV-100"),
        models.User(user_id="U_SENIOR_1", username="senior1", phone="9876543213", hashed_password=auth.hash_password("pass"), role=models.UserRole.SENIOR_FIELD, authority_tier=2, govt_id_ref="GOVT-SR-01"),
    ]
    db.add_all(users)
    db.commit()

    print("Loading parcels.geojson...")
    filepath = "../ml/boundary/UNET_BOUNDRYdetection/data/input/parcels.geojson"
    with open(filepath, "r") as f:
        data = json.load(f)

    parcels_to_add = []
    rors_to_add = []
    mutations_to_add = []
    registrations_to_add = []
    cases_to_add = []

    features = data.get("features", [])
    
    # We will pick the first 30 parcels for the demo to keep it snappy
    for i, feat in enumerate(features[:30]):
        props = feat["properties"]
        geom = feat["geometry"]
        pid = props.get("internal_parcel_key", f"P{i:02d}")
        
        scenario = props.get("scenario", "normal")
        
        # Default clean values
        area_diff = 0
        shift = 0.0
        reg_status = "present"
        mut_status = "approved"
        s2 = 0.0
        
        # Map scenarios to our logic
        if scenario == "missing_registration":
            reg_status = "missing"
            s2 = 0.2
        elif scenario == "old_mutation_issue":
            mut_status = "pending"
            s2 = 0.3
        elif scenario == "boundary_overlap":
            area_diff = 25
            shift = 3.5
            s2 = 0.5
        elif scenario == "complex_multi_issue":
            area_diff = 40
            shift = 8.0
            reg_status = "missing"
            mut_status = "pending"
            s2 = 0.9

        p = models.Parcel(
            parcel_id=pid,
            ulpin=f"ULPIN-{i:06d}" if i % 4 != 0 else None,
            geom=get_geom_from_geojson(geom),
            source="cadastral",
            area_sqm=props.get("area_sqm", 100.0)
        )
        parcels_to_add.append(p)
        
        ror = models.RoR(
            id=f"R{i:02d}", parcel_id=pid,
            owner_name=f"Owner of {pid}",
            khasra_no=props.get("survey_number", f"KH-{i*10}"),
            area_recorded=props.get("area_sqm", 100.0),
            status="present" if scenario != "missing_ror" else "missing"
        )
        rors_to_add.append(ror)
        
        mut = models.Mutation(id=f"M{i:02d}", parcel_id=pid, mutation_status=mut_status)
        mutations_to_add.append(mut)
        
        reg = models.Registration(id=f"RG{i:02d}", parcel_id=pid, status=reg_status)
        registrations_to_add.append(reg)
        
        conf_res = compute_confidence(
            area_diff_pct=area_diff,
            boundary_shift_m=shift,
            parcel_area_sqm=props.get("area_sqm", 100.0),
            registration_status=reg_status,
            mutation_status=mut_status,
            instability_score=s2,
            positioning_quality="RTK_FIX"
        )
        
        if conf_res["action"] == "field_verification_required" or scenario != "normal":
            case = models.Case(
                case_id=f"C{i:02d}",
                parcel_id=pid,
                status=models.CaseStatus.OPEN,
                confidence_score=conf_res["confidence_score"],
                action=conf_res["action"],
                case_data={
                    "reasoning_trace": conf_res["reasoning_trace"],
                    "spatial_mismatch_pct": area_diff,
                    "boundary_shift_m": shift,
                    "mutation_status": mut_status,
                    "registration_conflict": (reg_status == "missing"),
                    "temporal_signal": {"instability_score": s2, "onset_year": 2024},
                    "village": f"Village {props.get('village_code', '000')}",
                    "district": "Guntur",
                    "owner_name": f"Owner {i}"
                }
            )
            cases_to_add.append(case)
            
    db.add_all(parcels_to_add)
    db.commit()
    db.add_all(rors_to_add)
    db.add_all(mutations_to_add)
    db.add_all(registrations_to_add)
    db.add_all(cases_to_add)
    db.commit()

    print(f"Seeded {len(parcels_to_add)} REAL parcels from Guntur, {len(cases_to_add)} cases.")
    db.close()

if __name__ == "__main__":
    seed_db()
