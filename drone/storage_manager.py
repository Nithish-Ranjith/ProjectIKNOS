"""
drone/storage_manager.py — Manages local disk space on RPi4.

Design contracts:
  - MVP: simple circular buffer approach if disk gets too full (not implemented yet, just stub).
  - Syncs captured data back to the Android app when requested.
"""
import os
import shutil
from pathlib import Path

class StorageManager:
    def __init__(self, capture_dir: str = "/tmp/iknos_captures"):
        self.capture_dir = Path(capture_dir)
        self.capture_dir.mkdir(parents=True, exist_ok=True)
        
    def get_disk_usage(self):
        total, used, free = shutil.disk_usage(self.capture_dir)
        return {
            "total_gb": total / (1024**3),
            "used_gb": used / (1024**3),
            "free_gb": free / (1024**3),
            "percent_used": (used / total) * 100
        }
        
    def list_missions(self):
        """Find all unique mission IDs in the capture dir."""
        missions = set()
        for f in self.capture_dir.glob("*.json"):
            # Filename format: {mission_id}_{seq}_{uuid}.json
            parts = f.name.split('_')
            if len(parts) >= 3:
                # Need to reconstruct mission ID if it contains underscores
                mission_id = "_".join(parts[:-2])
                missions.add(mission_id)
        return list(missions)
        
    def get_mission_files(self, mission_id: str):
        """Get all images and sidecars for a mission."""
        files = []
        for f in self.capture_dir.glob(f"{mission_id}_*.json"):
            img_path = f.with_suffix('.jpg')
            if img_path.exists():
                files.append({
                    "sidecar": str(f),
                    "image": str(img_path)
                })
        return files
