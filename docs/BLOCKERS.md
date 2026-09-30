# BLOCKERS.md — Known gaps requiring external input before full deployment

## BQ-01: Camera Hardware Trigger (Partially Resolved)
**Status:** Implemented as Option C+D Dual Mode.
- **Option C:** CAMERA_FEEDBACK MAVLink message triggers PiCamera2 software capture.
  Timing jitter ~100-500ms is acceptable given standard GNSS ±2.5-5m positional uncertainty.
- **Option D:** Software Haversine distance tracking triggers at configurable spacing (default 10m).
- **Action required:** If hardware GPIO wiring is preferred (Option B), specify the Pixhawk AUX pin and RPi4 GPIO pin number.

## BQ-02: DGCA RPAS Registration Format
**Status:** Stored as an opaque string (`dgca_credential` column). Validation schema unknown.
- **Action required:** Provide the DGCA RPAS credential format to implement server-side validation.

## BQ-03: Google Earth Engine Project Credentials
**Status:** `sentinel_fetch.py` returns `NOT_RUN_GEE_PROJECT_MISSING` if `GEE_PROJECT` env var is absent.
- **Impact:** Sentinel-2 temporal analysis is skipped. `instability_score` will be `null`.
  The confidence formula handles this cleanly (temporal weight goes to 0).
- **Action required:**
  1. Create a GEE project at https://console.cloud.google.com/earth-engine
  2. Generate a service account key
  3. Set `GEE_PROJECT=<project-id>` and configure `GOOGLE_APPLICATION_CREDENTIALS`

## BQ-04: Hand-Labeled Indian Parcel Dataset for U-Net
**Status:** U-Net model built. Transfer-learned weights from AI4Boundaries/Eurocrops used.
All boundary candidates labeled `TRANSFER_LEARNED_UNVALIDATED`.
- **Impact:** Boundary candidate quality on Indian agricultural/peri-urban parcels is unknown.
- **Action required:** Provide 20-50 hand-labeled GeoJSON polygons paired with drone imagery
  of Indian parcels. Format: `{image: *.jpg, label: *.geojson}` pairs.

## BQ-05: Government ULPIN Write API
**Status:** `RecordUpdate` endpoint records the intent to update. No government API is called.
- **Impact:** The system cannot actually write to government land records.
- **Action required:** Provide the government API endpoint, authentication spec, and test environment
  credentials when available.

## BQ-06: ODM Workstation
**Status:** `odm_pipeline.py` submits to WebODM REST API. ODM cannot run on RPi4.
- **Action required:** Set up a workstation with >= 8GB RAM + WebODM.
  Set `WEBODM_URL` and `WEBODM_TOKEN` environment variables.
  Recommended: Ubuntu 22.04, 16GB RAM, 8-core CPU, WebODM 2.x.
