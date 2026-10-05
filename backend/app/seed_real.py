import json
import uuid
import os
import pandas as pd
from sqlalchemy import text
from app.database import engine, SessionLocal, Base
from app import models
import shapely.geometry

def seed_real_db():
    print("Dropping and recreating tables...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # 1. Users
    print("Seeding Users...")
    from app import auth
    users = [
        models.User(user_id="U_CUST_1", username="customer1", phone="9876543210", hashed_password=auth.hash_password("pass"), role=models.UserRole.CUSTOMER, authority_tier=0, owned_parcel_ids=["AP-07-GURAZALA-MADUGULA-5"]),
        models.User(user_id="U_DRONE_1", username="drone1", phone="9876543211", hashed_password=auth.hash_password("pass"), role=models.UserRole.SURVEYOR_DRONE, authority_tier=1, dgca_credential="DGCA-DR-001"),
        models.User(user_id="U_FIELD_1", username="field1", phone="9876543212", hashed_password=auth.hash_password("pass"), role=models.UserRole.SURVEYOR_FIELD, authority_tier=1, govt_id_ref="GOVT-SV-100"),
        models.User(user_id="U_SENIOR_1", username="senior1", phone="9876543213", hashed_password=auth.hash_password("pass"), role=models.UserRole.SENIOR_FIELD, authority_tier=2, govt_id_ref="GOVT-SR-01"),
    ]
    db.add_all(users)
    db.commit()

    dataset_dir = "/Users/nithishranjith/AndroidStudioProjects/ProjectIKNOS/data_extracted/iknos_dataset_1000 2/output_real"

    print("Loading cases.jsonl (limited to 500 for speed)...")
    cases = []
    parcel_ids = set()
    with open(os.path.join(dataset_dir, "cases.jsonl")) as f:
        for i, line in enumerate(f):
            if i >= 500:
                break
            c = json.loads(line)
            pid = c["parcel"]["internal_parcel_key"]
            parcel_ids.add(pid)
            
            c_status = c["status"].lower()
            if "open" in c_status or "pending" in c_status:
                status = models.CaseStatus.OPEN
            elif "closed" in c_status or "approved" in c_status or "rejected" in c_status:
                status = models.CaseStatus.CLOSED
            else:
                status = models.CaseStatus.OPEN
                
            cases.append(models.Case(
                case_id=c["case_id"],
                parcel_id=pid,
                status=status,
                confidence_score=c["priority_score"]["raw_score"] * 100,
                action="field_verification_required",
                case_data=c
            ))

    print(f"Loading parcels.geojson for {len(parcel_ids)} parcels...")
    with open(os.path.join(dataset_dir, "parcels.geojson")) as f:
        gj = json.load(f)
        
    parcels = []
    for feat in gj["features"]:
        pid = feat["properties"]["internal_parcel_key"]
        if pid in parcel_ids:
            geom = shapely.geometry.shape(feat["geometry"])
            wkt = geom.wkt
            area = feat["properties"].get("area_sqm", 1000.0)
            
            parcels.append(models.Parcel(
                parcel_id=pid,
                ulpin=feat["properties"].get("ulpin"),
                geom=text(f"ST_GeomFromText('{wkt}', 4326)"),
                source="cadastral",
                area_sqm=area
            ))
            
    print(f"Inserting {len(parcels)} parcels...")
    for p in parcels:
        db.add(p)
    db.commit()
    
    print(f"Inserting {len(cases)} cases...")
    for c in cases:
        db.add(c)
    db.commit()

    print("Loading Records...")
    # ror
    df_ror = pd.read_csv(os.path.join(dataset_dir, "ror.csv"))
    df_ror = df_ror[df_ror["internal_parcel_key"].isin(parcel_ids)]
    for _, r in df_ror.iterrows():
        db.add(models.RoR(
            id=str(uuid.uuid4()),
            parcel_id=r["internal_parcel_key"],
            owner_name=r.get("owner_name", "Unknown"),
            khasra_no=r.get("khasra_no", ""),
            status="present",
            area_recorded=r.get("area_recorded", 0)
        ))
    db.commit()

    # mutations
    df_mut = pd.read_csv(os.path.join(dataset_dir, "mutation.csv"))
    df_mut = df_mut[df_mut["internal_parcel_key"].isin(parcel_ids)]
    for _, r in df_mut.iterrows():
        db.add(models.Mutation(
            id=str(uuid.uuid4()),
            parcel_id=r["internal_parcel_key"],
            mutation_status=r.get("mutation_status", "none")
        ))
    db.commit()
    
    # registrations
    df_reg = pd.read_csv(os.path.join(dataset_dir, "registration.csv"))
    df_reg = df_reg[df_reg["internal_parcel_key"].isin(parcel_ids)]
    for _, r in df_reg.iterrows():
        db.add(models.Registration(
            id=str(uuid.uuid4()),
            parcel_id=r["internal_parcel_key"],
            status="present"
        ))
    db.commit()

    print("Done seeding real data!")
    db.close()

if __name__ == "__main__":
    seed_real_db()
