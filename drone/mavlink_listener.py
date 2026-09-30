"""
drone/mavlink_listener.py — Listens to MAVLink telemetry from Pixhawk.

Design contracts:
  - MVP only requires basic telemetry (position, altitude, flight mode).
  - Pushes GPS coords to capture_service for Option D (software distance tracking).
"""
import time
import json
import threading
from typing import Optional, Callable
from pymavlink import mavutil

class MAVLinkListener:
    def __init__(self, connection_string: str = "/dev/ttyAMA0", baud: int = 57600):
        self.connection_string = connection_string
        self.baud = baud
        self.conn = None
        self.running = False
        self._thread = None
        
        # Latest telemetry state
        self.lat = 0.0
        self.lon = 0.0
        self.alt = 0.0
        self.heading = 0.0
        self.flight_mode = "UNKNOWN"
        self.armed = False
        
        self.position_callbacks = []
        self.camera_feedback_callbacks = []

    def connect(self):
        print(f"Connecting to {self.connection_string} at {self.baud} baud...")
        # For testing without hardware, we could use a UDP port
        self.conn = mavutil.mavlink_connection(self.connection_string, baud=self.baud)
        self.conn.wait_heartbeat()
        print(f"Heartbeat received from system (system {self.conn.target_system} component {self.conn.target_component})")
        
        # Request data streams
        self.conn.mav.request_data_stream_send(
            self.conn.target_system, self.conn.target_component,
            mavutil.mavlink.MAV_DATA_STREAM_POSITION, 10, 1
        )
        self.conn.mav.request_data_stream_send(
            self.conn.target_system, self.conn.target_component,
            mavutil.mavlink.MAV_DATA_STREAM_EXTRA1, 10, 1
        )

    def start(self):
        if not self.conn:
            self.connect()
        self.running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def register_position_callback(self, cb: Callable[[float, float, float], None]):
        self.position_callbacks.append(cb)

    def register_camera_feedback_callback(self, cb: Callable[[int], None]):
        self.camera_feedback_callbacks.append(cb)

    def _listen_loop(self):
        while self.running:
            msg = self.conn.recv_match(blocking=True, timeout=1.0)
            if not msg:
                continue

            msg_type = msg.get_type()
            
            if msg_type == 'HEARTBEAT':
                self.armed = (msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0
                self.flight_mode = mavutil.mode_string_v10(msg)

            elif msg_type == 'GLOBAL_POSITION_INT':
                self.lat = msg.lat / 1e7
                self.lon = msg.lon / 1e7
                self.alt = msg.relative_alt / 1000.0  # meters
                self.heading = msg.hdg / 100.0        # degrees
                
                for cb in self.position_callbacks:
                    try:
                        cb(self.lat, self.lon, self.alt)
                    except Exception as e:
                        print(f"Callback error: {e}")

            elif msg_type == 'CAMERA_FEEDBACK':
                # Option C hardware trigger event
                img_idx = getattr(msg, 'img_idx', 0)
                print(f"CAMERA_FEEDBACK received for image {img_idx}")
                for cb in self.camera_feedback_callbacks:
                    try:
                        cb(img_idx)
                    except Exception as e:
                        print(f"Callback error: {e}")

if __name__ == "__main__":
    # Test script
    listener = MAVLinkListener("udpin:localhost:14550")
    listener.register_position_callback(lambda lat, lon, alt: print(f"Pos: {lat}, {lon}, {alt}"))
    listener.register_camera_feedback_callback(lambda idx: print(f"Camera triggered: {idx}"))
    listener.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        listener.stop()
