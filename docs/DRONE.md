# DRONE.md — RPi4 Edge Node Architecture

## Hardware Stack
- Raspberry Pi 4 (4GB RAM recommended)
- Pixhawk flight controller (ArduCopter 4.x)
- Pi Camera v2 (8MP, 62.2° HFOV)
- Connection: UART (`/dev/ttyAMA0`, 57600 baud) from Pixhawk to Pi

## Camera Trigger Strategy — Option C + D Dual Mode
This resolves the `CAM_TRIGG_DIST` vs `CAMERA_FEEDBACK` ambiguity noted in the PRD.

**ArduPilot behaviour:**
- `CAM_TRIGG_DIST` tells ArduPilot to emit a shutter trigger at distance intervals.
- For Pi Camera, there is no hardware shutter — the shutter trigger cannot be directly wired.
- `CAMERA_FEEDBACK` is the MAVLink event ArduPilot emits AFTER it records that a camera
  fired. This is what `mavlink_listener.py` listens for (Option C).

**Option C (Primary):** Listen for CAMERA_FEEDBACK messages. When received, trigger
  PiCamera2 software capture. This is ~100-500ms after the intended trigger point.
  Acceptable for STANDARD_GNSS accuracy (±2.5-5m).

**Option D (Fallback):** Software Haversine distance tracking. When aircraft moves more
  than `distance_interval_m` (default: 10m) from last capture position, trigger capture.

Both modes run simultaneously. A debounce of 1 second prevents double-triggering.

## Grid Spacing Formula (Pi Camera v2 at altitude h meters)
```
HFOV = 62.2°
footprint_width = 2 * h * tan(HFOV/2)
grid_spacing = footprint_width * (1 - side_overlap_pct / 100)
```

| Altitude (m) | Footprint Width (m) | Spacing at 70% overlap |
|---|---|---|
| 30 | ~36m | ~10.8m |
| 50 | ~60m | ~18m |
| 80 | ~96m | ~29m |

## Workflow
1. `mavlink_listener.py` — connects to Pixhawk, reads GPS, armed state, CAMERA_FEEDBACK
2. `capture_service.py` — triggers PiCamera2 based on C+D dual mode
3. `blur_check.py` — scans captured images, updates sidecar JSONs with blur score
4. `telemetry_relay.py` — forwards GPS/armed/mode to Android tablet over Wi-Fi UDP

## Environment Variables
| Variable | Default | Description |
|---|---|---|
| `CAPTURE_DIR` | `/tmp/terratrace_captures` | Where images are stored |
| `DISTANCE_INTERVAL_M` | `10.0` | Option D trigger distance |
| `BLUR_THRESHOLD` | `100.0` | Laplacian variance below this → BLUR |

## ODM Note
WebODM / ODM photogrammetry **cannot run on the RPi4**. Images must be transferred to
a workstation with >= 8GB RAM. See PHOTOGRAMMETRY.md.
