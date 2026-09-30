import yaml
import json
import random
import os
import shutil
from pathlib import Path
from shapely.geometry import Polygon
from fastapi.testclient import TestClient

from app.main import app
from app.flight_planner import plan
from app.sim.virtual_drone import VirtualPlan, fly
from app.sim.virtual_camera import capture_image
from app.database import SessionLocal
from app import models
from app import auth

client = TestClient(app)

def run_simulation():
    config_path = Path("app/config/camera.sim.yaml")
    with open(config_path, "r") as f:
        cam_config = yaml.safe_load(f)
        
    planning_cfg = cam_config.get("planning", {})
    gsd_m = planning_cfg.get("target_gsd_m", 0.02)
    fwd = planning_cfg.get("forward_overlap", 0.8)
    side = planning_cfg.get("side_overlap", 0.7)
    
    poly = Polygon([
        (0.0, 0.0),
        (0.001, 0.0),
        (0.001, 0.001),
        (0.0, 0.001),
        (0.0, 0.0)
    ])
    
    res = plan(poly_wgs84=poly, cam=cam_config, gsd_m=gsd_m, fwd=fwd, side=side)
    
    virtual_plan = VirtualPlan(
        waypoints_utm=res["waypoints"], 
        altitude_m=res["altitude_m"],
        cam_trigg_dist_m=res["cam_trigg_dist_m"]
    )
    
    headers = {
        "X-Demo-Email": "drone@example.com",
        "X-Demo-Role": "surveyor"
    }
    
    db = SessionLocal()
    case = db.query(models.Case).first() 
    if not case:
        print("No cases in DB.")
        return
        
    scenarios = [
        {"id": "base", "name": "Baseline", "drift_m": 2.0, "blur_rate": 0.05},
        {"id": "high_wind", "name": "High Wind", "drift_m": 8.0, "blur_rate": 0.05},
        {"id": "poor_light", "name": "Poor Lighting", "drift_m": 2.0, "blur_rate": 0.20},
    ]
    
    report = []
    
    for sc in scenarios:
        mission_id = f"SIM_{sc['id'].upper()}_001"
        cam_config["mission_id"] = mission_id
        out_dir = f"/tmp/sim_images_{sc['id']}"
        if os.path.exists(out_dir):
            shutil.rmtree(out_dir)
            
        mission = db.query(models.Mission).filter(models.Mission.mission_id == mission_id).first()
        if not mission:
            mission = models.Mission(
                mission_id=mission_id,
                case_id=case.case_id,
                parcel_id=case.parcel_id,
                created_by="U_DRONE_1",
                state=models.MissionState.DRAFT
            )
            db.add(mission)
            db.commit()
            
        random.seed(42)
        total_images, injected_blur, rejected = 0, 0, 0
        
        for cap in fly(virtual_plan, drift_m=sc["drift_m"], seed=42):
            is_blurry = random.random() < sc["blur_rate"]
            if is_blurry:
                injected_blur += 1
                
            img_path, meta = capture_image(cap, out_dir, cam_config, is_blurry=is_blurry)
            total_images += 1
            
            with open(img_path, "rb") as f:
                resp = client.post(
                    f"/missions/{mission_id}/images", 
                    headers=headers,
                    data={"sidecar": json.dumps(meta)},
                    files={"file": (os.path.basename(img_path), f, "image/jpeg")}
                )
                
            if resp.status_code == 200:
                if resp.json().get("quality_flag") == "REJECT":
                    rejected += 1
                    
        res_entry = {
            "scenario": sc["name"],
            "total_images": total_images,
            "injected_blur": injected_blur,
            "rejected_by_qc": rejected,
            "qc_passed": rejected == injected_blur
        }
        report.append(res_entry)
        
    with open("sim_report.json", "w") as f:
        json.dump(report, f, indent=2)
        
    with open("sim_report.md", "w") as f:
        f.write("# Simulation Report\n\n")
        f.write("| Scenario | Total Images | Injected Blur | Rejected by QC | Passed |\n")
        f.write("|----------|--------------|---------------|----------------|--------|\n")
        for r in report:
            f.write(f"| {r['scenario']} | {r['total_images']} | {r['injected_blur']} | {r['rejected_by_qc']} | {'✅' if r['qc_passed'] else '❌'} |\n")
            
    print("Simulation complete. Wrote sim_report.json and sim_report.md")

if __name__ == "__main__":
    run_simulation()
