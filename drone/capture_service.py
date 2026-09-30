"""
drone/capture_service.py — Dual-Mode Camera Trigger (Option C + D).

Design contracts:
  - Primary trigger: CAMERA_FEEDBACK via MAVLink (Option C).
  - Fallback trigger: Software-calculated distance based on GPS coords (Option D).
  - Triggers PiCamera2.
  - Ensures we don't trigger twice for the same physical location (debounce).
"""
import time
import math
import uuid
import json
import os
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

# Note: In real RPi env, import picamera2 here. Mocked for this prototype.
# from picamera2 import Picamera2

class CaptureService:
    def __init__(self, capture_dir: str = "/tmp/terratrace_captures", distance_interval_m: float = 10.0):
        self.capture_dir = Path(capture_dir)
        self.capture_dir.mkdir(parents=True, exist_ok=True)
        self.distance_interval_m = distance_interval_m
        
        self.last_capture_time = 0.0
        self.last_capture_lat = None
        self.last_capture_lon = None
        self.seq_counter = 1
        self.mission_id = "M_DEBUG"
        
        # Debounce (prevent Option C and Option D from double-triggering)
        self.debounce_seconds = 1.0 
        
        self.camera_ready = False
        self._init_camera()

    def _init_camera(self):
        print("Initializing PiCamera2...")
        # self.picam = Picamera2()
        # self.picam.configure(self.picam.create_preview_configuration(main={"size": (4056, 3040)}))
        # self.picam.start()
        self.camera_ready = True
        print("Camera ready.")

    def haversine(self, lat1, lon1, lat2, lon2):
        """Distance in meters between two GPS coords."""
        R = 6371000
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)

        a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c

    def trigger_capture(self, lat: float, lon: float, alt: float, trigger_source: str = "SOFTWARE"):
        """Execute a capture and save the image + sidecar."""
        now = time.time()
        if now - self.last_capture_time < self.debounce_seconds:
            print(f"Capture debounced (triggered by {trigger_source})")
            return

        if not self.camera_ready:
            print("Camera not ready.")
            return

        image_id = str(uuid.uuid4())
        ts = datetime.now(timezone.utc).isoformat()
        
        print(f"[{trigger_source}] Capturing image {self.seq_counter} at {lat}, {lon}")
        
        img_path = self.capture_dir / f"{self.mission_id}_{self.seq_counter:04d}_{image_id}.jpg"
        meta_path = self.capture_dir / f"{self.mission_id}_{self.seq_counter:04d}_{image_id}.json"

        # Mock capture
        # self.picam.capture_file(str(img_path))
        with open(img_path, "w") as f:
            f.write("mock_jpeg_data")

        # Create sidecar JSON
        sidecar = {
            "image_id": image_id,
            "mission_id": self.mission_id,
            "seq": self.seq_counter,
            "lat": lat,
            "lon": lon,
            "alt_m": alt,
            "yaw_deg": 0.0, # Mocked
            "gps_fix_type": "3D_FIX",
            "timestamp_gps": ts,
            "blur_score": 0.0, # Will be set by blur_check.py pipeline
            "quality_flag": "PENDING",
            "camera_id": "picam_v2_01"
        }
        
        with open(meta_path, "w") as f:
            json.dump(sidecar, f, indent=2)

        self.last_capture_time = now
        self.last_capture_lat = lat
        self.last_capture_lon = lon
        self.seq_counter += 1

    def handle_position_update(self, lat: float, lon: float, alt: float):
        """Option D: Software distance tracking."""
        if self.last_capture_lat is None or self.last_capture_lon is None:
            # First fix, capture immediately
            self.trigger_capture(lat, lon, alt, trigger_source="OPTION_D_FIRST_FIX")
            return

        dist = self.haversine(self.last_capture_lat, self.last_capture_lon, lat, lon)
        if dist >= self.distance_interval_m:
            self.trigger_capture(lat, lon, alt, trigger_source="OPTION_D_DISTANCE")

    def handle_camera_feedback(self, img_idx: int, lat: float, lon: float, alt: float):
        """Option C: Hardware CAMERA_FEEDBACK event."""
        self.trigger_capture(lat, lon, alt, trigger_source="OPTION_C_FEEDBACK")
