"""
backend/app/odm_pipeline.py — ODM / WebODM photogrammetry integration with U-Net Trigger.

Design contracts:
  - ODM CANNOT run on RPi4 (insufficient RAM for large point clouds).
  - WebODM endpoint is configurable via WEBODM_URL env var.
  - If WEBODM_URL is not set, pipeline is skipped and flagged in mission record.
  - Adds capability to trigger U-Net Boundary Extraction after ODM succeeds.
"""
import os
import json
import uuid
import requests
from pathlib import Path
from typing import Optional

WEBODM_URL = os.environ.get("WEBODM_URL", "http://localhost:8000")
WEBODM_TOKEN = os.environ.get("WEBODM_TOKEN", "")


def submit_to_odm(mission_id: str, image_dir: str, project_name: Optional[str] = None) -> dict:
    if not WEBODM_TOKEN:
        return {
            "status": "SKIPPED_NO_WEBODM",
            "task_id": None,
            "project_id": None,
            "webodm_url": WEBODM_URL,
            "note": "WEBODM_TOKEN not set. ODM pipeline requires a running WebODM instance."
        }
    try:
        project_name = project_name or f"IKNOS_{mission_id}"
        project_resp = requests.post(
            f"{WEBODM_URL}/api/projects/",
            headers={"Authorization": f"JWT {WEBODM_TOKEN}"},
            data={"name": project_name}
        )
        project_resp.raise_for_status()
        project_id = project_resp.json()["id"]

        images = list(Path(image_dir).glob("*.jpg")) + list(Path(image_dir).glob("*.JPG"))
        if not images:
            return {"status": "ERROR", "task_id": None, "project_id": project_id,
                    "note": "No images found to upload."}

        files = [("images", (img.name, open(img, "rb"), "image/jpeg")) for img in images]
        options = json.dumps([{"name": "dsm", "value": True}, {"name": "orthophoto-resolution", "value": 5}])
        
        task_resp = requests.post(
            f"{WEBODM_URL}/api/projects/{project_id}/tasks/",
            headers={"Authorization": f"JWT {WEBODM_TOKEN}"},
            files=files,
            data={"options": options, "name": f"Mission_{mission_id}"}
        )
        task_resp.raise_for_status()
        return {
            "status": "SUBMITTED",
            "task_id": task_resp.json()["id"],
            "project_id": project_id,
            "webodm_url": WEBODM_URL,
            "note": "Images uploaded to WebODM. Processing is asynchronous."
        }
    except Exception as e:
        return {"status": "ERROR", "task_id": None, "project_id": None, "note": str(e)}


def poll_odm_task(task_id: str, project_id: str) -> dict:
    if not WEBODM_TOKEN:
        return {"status": "SKIPPED_NO_WEBODM"}
    try:
        resp = requests.get(
            f"{WEBODM_URL}/api/projects/{project_id}/tasks/{task_id}/",
            headers={"Authorization": f"JWT {WEBODM_TOKEN}"}
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "status": data.get("status", {}).get("code", "UNKNOWN"),
            "orthomosaic_uri": f"{WEBODM_URL}/api/projects/{project_id}/tasks/{task_id}/download/orthophoto.tif",
            "dsm_uri": f"{WEBODM_URL}/api/projects/{project_id}/tasks/{task_id}/download/dsm.tif",
            "point_cloud_uri": f"{WEBODM_URL}/api/projects/{project_id}/tasks/{task_id}/download/georeferenced_model.laz",
        }
    except Exception as e:
        return {"status": "ERROR", "note": str(e)}


def trigger_unet_inference(tif_path: str, output_geojson: str, cadastral_geojson: dict) -> dict:
    """
    Runs the v2 EfficientNet-B3 ONNX inference pipeline on the
    downloaded orthomosaic, extracts the boundary polygon, and saves it.
    """
    try:
        from app.unet_service import process_orthophoto_for_parcel
        import json
        
        feature = process_orthophoto_for_parcel(tif_path, cadastral_geojson)
        if not feature:
            return {"status": "ERROR", "note": "No parcel detected or inference failed"}
            
        geojson = {
            "type": "FeatureCollection",
            "features": [feature],
            "metadata": {"n_candidates": 1}
        }
        
        with open(output_geojson, "w") as f:
            json.dump(geojson, f, indent=2)
            
        return {
            "status": "SUCCESS",
            "geojson_path": output_geojson,
            "num_candidates": 1,
            "feature": feature
        }
    except Exception as e:
        return {"status": "ERROR", "note": f"U-Net Inference failed: {e}"}
