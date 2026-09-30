"""
drone/telemetry_relay.py — Forwards Pixhawk telemetry over Wi-Fi to Android.

Design contracts:
  - Reads from mavlink_listener.
  - Serves a lightweight UDP or WebSocket stream for the Android app.
"""
import socket
import json
import time
import threading

class TelemetryRelay:
    def __init__(self, bind_host: str = "0.0.0.0", bind_port: int = 5000):
        self.bind_host = bind_host
        self.bind_port = bind_port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Allows broadcast if Android IP isn't explicitly known
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.target_address = ("255.255.255.255", 5001)  # Broadcast by default
        
    def set_target_address(self, ip: str, port: int = 5001):
        self.target_address = (ip, port)
        
    def broadcast_position(self, lat: float, lon: float, alt: float, armed: bool, mode: str):
        data = {
            "type": "telemetry",
            "lat": lat,
            "lon": lon,
            "alt": alt,
            "armed": armed,
            "mode": mode,
            "ts": time.time()
        }
        try:
            self.sock.sendto(json.dumps(data).encode('utf-8'), self.target_address)
        except Exception as e:
            print(f"Relay error: {e}")

# If we were wiring this up fully, we'd hook this into the MAVLinkListener's callbacks.
