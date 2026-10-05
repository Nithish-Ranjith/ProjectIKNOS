# IKNOS — Product Requirements Document
**One-stop land-record reconciliation application — drone survey, evidence fusion, field verification**
SIH 2026 · Team StrawHats · Hardware Category

---

## 0. What this document is

One application, three role-based login experiences, one backend, one database. The drone (Pixhawk 2.4.8 + Raspberry Pi 4, 4GB) is a data-producing edge node, not a separate product. Everything below states plainly what is **built from scratch**, what is a **pre-built module you configure**, and what is **future/optional** — so no teammate mistakes a configured tool for original engineering, and no judge mistakes a configured tool for a gap.

Legend used throughout: **✅ CORE (build this)** · **🔧 PREBUILT (configure, don't rewrite)** · **🔬 VALIDATE (real but unproven at your scale)** · **💡 FUTURE (not in MVP)**

---

## 1. The problem, restated in one paragraph

Land boundary *measurement* is a solved problem. Land boundary *adjudication* — deciding which of several disagreeing evidence sources (cadastral map, Record of Rights, mutation register, registration deed, physical ground reality) should be trusted, and routing that conflict transparently to a human — is not. IKNOS is a reconciliation layer that consumes survey data (from your drone) and existing government records, detects disagreement, scores confidence, and produces an evidence-backed case for a revenue officer to decide. It never decides ownership itself.

---

## 2. Product concept — what "one-stop app" actually means

**One Android application, three logins, three permission sets, one shared backend and database.** Nobody installs three separate apps. On login, the role determines which screens render — same codebase, same API, different views and write-permissions.

```
                        ┌─────────────────────────┐
                        │   IKNOS BACKEND     │
                        │  FastAPI + PostgreSQL/   │
                        │  PostGIS + Object Store  │
                        └───────────┬─────────────┘
                                    │  REST/JSON over HTTPS
            ┌───────────────────────┼───────────────────────┐
            ▼                       ▼                       ▼
   ┌────────────────┐     ┌──────────────────┐    ┌──────────────────────┐
   │  CUSTOMER LOGIN │     │  SURVEYOR FIELD   │    │  SURVEYOR DRONE       │
   │  (landowner)    │     │  LOGIN (tablet)   │    │  LOGIN (pilot console)│
   │  view + object  │     │  review + verify  │    │  plan + fly + capture │
   └────────────────┘     └──────────────────┘    └──────────────────────┘
                                                              │
                                                    WiFi (UDP/MAVLink)
                                                              │
                                                   ┌──────────────────────┐
                                                   │ RASPBERRY PI 4 (drone)│
                                                   │ mavlink-router        │
                                                   │ Pi Camera + capture   │
                                                   │ script + blur check   │
                                                   └──────────┬───────────┘
                                                              │ Serial/UART
                                                   ┌──────────────────────┐
                                                   │  PIXHAWK 2.4.8 / FC   │
                                                   │  ArduCopter firmware  │
                                                   │  LOITER mode +        │
                                                   │  CAM_TRIGG_DIST       │
                                                   └──────────────────────┘
```

---

## 3. The three login roles — precisely, with what changes

| | **CUSTOMER (Landowner)** | **SURVEYOR — FIELD (Tablet/Phone)** | **SURVEYOR — DRONE (Pilot Console)** |
|---|---|---|---|
| **Who** | Landowner / co-sharer | Revenue officer, clerk, back-office surveyor | DGCA-credentialed drone pilot |
| **When used** | Anytime, remote | Pre-flight planning + post-flight case review | Only during active flight, on-site |
| **Primary screens** | My Parcels, Case Status, Evidence Summary (plain language), File Objection | Case Queue (risk-sorted), Case Detail (full evidence bundle), Approve/Reject/Route, Mission History | Live Mission Screen (grid overlay + drone position dot), Trigger Distance config, Battery/GPS/Mode telemetry, Abort control |
| **Can write?** | Objection text + evidence photo upload only | Verification decision (approve/reject/escalate), field notes, geotagged photos | Mission parameters (`CAM_TRIGG_DIST`, altitude target), start/abort — **cannot** edit any record, **cannot** decide case outcome |
| **Cannot do** | Cannot see other parcels, cannot see internal confidence scores/raw ML output — only a plain-language summary | Cannot fly or control the drone | Cannot approve/reject a case, cannot view other parcels' RoR/ownership data |
| **Auth model** | Phone OTP (self-registered, DPDP consent capture on first login) | Government-issued ID + role assigned by admin | Government-issued ID + DGCA pilot credential number stored against account |

This mirrors real-world role separation (a pilot's job and a revenue officer's job are legally and practically different people in India) — worth stating exactly this way to a judge.

---

## 4. Hardware reality — what you actually have, and what each piece does

| Component | Role | Status |
|---|---|---|
| Pixhawk 2.4.8 + ArduCopter firmware | Flight control, GPS-assisted LOITER mode, `CAM_TRIGG_DIST` distance-based camera triggering | ✅ Have it |
| Raspberry Pi 4 (4GB) | Companion computer: MAVLink relay over WiFi, camera capture + geotag, onboard blur/quality check | ✅ Have it |
| Pi Camera Module (v2/HQ) or USB camera | Image capture, RPi4-attached | 🔧 Buy — ~₹1,500–3,500, no dedicated gimbal camera needed for MVP |
| WiFi (RPi4 built-in) | Telemetry bridge, RPi4 ↔ tablet | ✅ Already onboard — **replaces need for a SiK radio** |
| NEO-6M/NEO-M8N GPS | Position fix, consumer-grade (~2.5–5m) | ✅ Have it — **no RTK in MVP; documented limitation, not hidden** |
| Barometric altimeter (in FC) | Altitude hold for LOITER | ✅ Already on Pixhawk — **do not use HC-SR04 for this**, ultrasonic is unreliable above ~4m and over crop canopy |
| SIM800L GSM | Status SMS alerts only | ✅ Have it — **not for images, not for live telemetry**, 2G bandwidth is the wrong tool for both |

**Flight mode: LOITER, not AUTO.** Pilot keeps full stick authority; GPS assists position/altitude hold against drift. `CAM_TRIGG_DIST` fires the camera every N meters of travel **independently of flight mode** — this is the one ArduPilot parameter that gives you automated, distance-based capture without surrendering manual control. 🔧 Configure via Mission Planner parameter list — this is not code you write.

---

## 5. End-to-end data flow — every stage, with the actual file format

```
[1] PRE-FLIGHT
    Cadastral polygon (GeoJSON) OR perimeter-walk AOI (phone GPS breadcrumb → closed polygon)
        ↓
    Grid-plan geometry calculated from camera FOV + target altitude + desired overlap
        → displayed as reference overlay on Surveyor-Drone tablet (not uploaded as an executable mission)

[2] FLIGHT
    Pixhawk: LOITER mode, CAM_TRIGG_DIST fires camera trigger event over MAVLink
        ↓
    RPi4: pymavlink listens for CAMERA_FEEDBACK message → triggers Pi Camera → saves:
        image.jpg  (JPEG)
        + EXIF GPS tag (lat/lon/alt from the MAVLink message at that instant)
        + companion sidecar: image.json  { seq, lat, lon, alt_m, yaw_deg, gps_fix_type, timestamp_gps }
        ↓
    RPi4 onboard: OpenCV Laplacian-variance blur check per image → quality_flag: PASS/BLUR
        ↓
    RPi4 → tablet (Surveyor-Drone login) over WiFi/UDP: live GPS position, battery %, mode, image count
        → rendered as a moving dot on the pre-flight grid overlay

[3] POST-FLIGHT SYNC
    RPi4 local storage (SD card) → base laptop/backend, via WiFi transfer or physical SD removal
    All images + sidecar JSON + mission_id uploaded as one batch

[4] PHOTOGRAMMETRY  (🔧 PREBUILT — OpenDroneMap, do not build a custom stitcher)
    Input: image set + geotags
    Output: orthomosaic.tif (GeoTIFF), dsm.tif (GeoTIFF), optional point_cloud.laz

[5] BOUNDARY EXTRACTION (✅ CORE ML — see Section 6)
    Input: orthomosaic tile(s)
    Output: candidate_boundary.geojson (probability-scored polygon)

[6] SPATIAL COMPARISON (✅ CORE — deterministic, not ML)
    candidate_boundary.geojson  vs  cadastral polygon (PostGIS geometry)
        ↓ PostGIS: ST_Difference, ST_Intersection, ST_HausdorffDistance, ST_IsValid
    Output: discrepancy_metrics (JSON) — area_diff_pct, boundary_shift_m, topology_valid

[7] MULTI-SOURCE EVIDENCE FUSION (✅ CORE)
    discrepancy_metrics + RoR/mutation/registration join + temporal satellite signal (Section 6)
        ↓ weighted scoring formula
    Output: CASE OBJECT (JSON — schema in Section 7) → written to PostgreSQL, surfaced to Surveyor-Field login

[8] HUMAN VERIFICATION
    Surveyor-Field: approve / reject / escalate
        ↓
    [9] PROVENANCE-PRESERVING RECORD UPDATE (append-only, reversible under authorized override only)
```

---

## 6. ML models — exact input, output, algorithm, and status per model

| Model | Purpose | Input (exact features) | Output | Algorithm | Status |
|---|---|---|---|---|---|
| **Boundary extraction** | Trace physical field edges from orthomosaic | RGB image tile, 512×512px, 3-channel, cropped from orthomosaic.tif | Per-pixel probability mask (0–1) → vectorized to GeoJSON polygon | U-Net (or U-Net++), transfer-learned | 🔬 Pretrain on AI4Boundaries/Eurocrops (public, EU parcels) → fine-tune on 20–50 hand-digitized parcels from your own pilot flight |
| **Onboard image quality check** | Reject blurred frames before they reach photogrammetry | Single grayscale image | `blur_score` (float) + PASS/FAIL flag | Laplacian variance (classical CV, OpenCV) — **not deep learning** | ✅ Trivial to implement, runs on RPi4 in real time |
| **Temporal anomaly detection** | Flag informal partition / undeclared change before drone even flies | Per-parcel NDVI time series, N seasonal timesteps (Sentinel-2 via Google Earth Engine, masked to parcel polygon) | `instability_score` (0–1) + estimated `onset_year` | STL decomposition (seasonal-trend-residual) + PELT changepoint detection — classical time-series, **not deep learning** | 🔬 Real satellite data, un-backtested against real adjudicated cases yet |
| **Fuzzy record matching** | Link RoR/mutation/registration rows when parcel_id/ULPIN is missing or inconsistent | String pairs: owner name, khasra/khata number | Similarity score (0–1) | Jaro-Winkler / Levenshtein distance — rule-based, **not ML** | ✅ Deterministic, implement directly |
| **Confidence / risk fusion score** | Combine all evidence into one actionable number | Vector: `[area_diff_pct, boundary_shift_m, registration_conflict (bool), mutation_pending (bool), instability_score, source_quality_weight]` | `confidence_score` (0–100) + `action` (`route_to_verification` / `no_action`) | Weighted deterministic formula first (transparent, defensible); logistic regression only after real labeled outcomes exist to calibrate against | ✅ Start deterministic — 💡 ML calibration is future work |
| **OCR on legacy RoR scans** | Digitize handwritten/typed regional-script records | Scanned document image | Structured fields (owner, area, khasra no.) | Tesseract OCR + regex/NER field extraction | 🔧 Integration, not original model work |

**Explicit statement for your pitch:** discrepancy detection is deterministic geometry + database joins. ML is scoped to exactly three subtasks — boundary pixels, temporal time-series anomaly, and OCR. This is a stronger, more precise claim than "we use AI," and it's the honest one.

---

## 7. Data schemas — concrete, per data type

**Drone image metadata (sidecar JSON, per photo):**
```json
{
  "image_id": "uuid",
  "mission_id": "M2026-0091",
  "seq": 47,
  "lat": 16.5062, "lon": 80.6480, "alt_m": 62.3,
  "yaw_deg": 184.2,
  "gps_fix_type": "3D_FIX",
  "timestamp_gps": "2026-09-10T05:12:33Z",
  "blur_score": 812.4, "quality_flag": "PASS",
  "camera_id": "picam_v2_01"
}
```

**Parcel geometry (PostGIS table `parcels`):**
```sql
CREATE TABLE parcels (
  parcel_id      TEXT PRIMARY KEY,   -- ULPIN or internal key
  geom           GEOMETRY(Polygon, 4326),
  source         TEXT,               -- 'cadastral' | 'drone_derived'
  area_sqm       NUMERIC,
  last_updated   TIMESTAMPTZ
);
```

**RoR / Mutation / Registration (relational, `PostgreSQL`):**
```sql
CREATE TABLE ror (
  parcel_id TEXT REFERENCES parcels(parcel_id),
  owner_name TEXT, khasra_no TEXT, area_recorded NUMERIC,
  record_date DATE
);
CREATE TABLE mutation (
  parcel_id TEXT REFERENCES parcels(parcel_id),
  mutation_status TEXT,  -- 'pending' | 'approved' | 'none'
  mutation_date DATE
);
```

**Case object (the contract artifact — PostgreSQL JSONB, and the API response shape both apps consume):**
```json
{
  "case_id": "uuid",
  "parcel_id": "AP-GNT-114-0087",
  "spatial_mismatch_pct": 7.3,
  "boundary_shift_m": 2.4,
  "registration_conflict": true,
  "mutation_status": "pending",
  "temporal_signal": { "instability_score": 0.62, "onset_year": 2021 },
  "confidence_score": 61,
  "action": "field_verification_required",
  "evidence_refs": ["orthomosaic_uri", "cadastral_geom_id", "ror_record_id"],
  "status": "open",
  "audit_trail": []
}
```

**Photogrammetry outputs:** `orthomosaic.tif` (GeoTIFF), `dsm.tif` (GeoTIFF), optional `points.laz`.
**Boundary candidates:** `GeoJSON` in transit, cast to `PostGIS geometry` on ingest.

---

## 8. Creative/efficient solutions — fastest path to a working result per problem

| Problem | Fast, real solution |
|---|---|
| No RTK, position noise ~2.5–5m | GPS-averaging at 2–3 known corners (hold static 30–60s) as manual "poor-man's GCP"; anchor orthomosaic to these, not raw single-fix GPS |
| No labeled Indian boundary dataset | Transfer-learn from AI4Boundaries/Eurocrops (public), fine-tune on your own 20–50 hand-digitized pilot parcels in QGIS |
| Manual flight can't hold a perfect grid | Over-specify overlap (80% forward / 70% side vs. the usual 75/60) — cheap insurance against pilot drift, stated as a deliberate design choice |
| No live telemetry radio | RPi4's built-in WiFi + `mavlink-router`/pymavlink — zero extra hardware |
| No real government RoR access | Synthetic but structurally realistic records with deliberately injected inconsistencies, explicitly labeled synthetic in your docs |
| Real ground-truth for temporal model | Sentinel-2 via Google Earth Engine is free and real — your one genuinely non-synthetic data source, foreground it |
| Homogeneous crop canopy breaks feature matching | Higher overlap over uniform fields; flag low-feature zones for optional temporary ground markers |

---

## 9. MVP scope for your timeline — what ships, what's demoed as concept only

✅ **Build and demo live:** LOITER-mode manual flight, `CAM_TRIGG_DIST` capture, RPi4 geotagging + blur check, OpenDroneMap orthomosaic, U-Net boundary candidate (fine-tuned on your own pilot set), deterministic spatial comparison, weighted confidence score, three-login app with real case flow on synthetic RoR/mutation data, Sentinel-2 temporal signal on one real parcel.

💡 **State as roadmap, do not fake as built:** RTK integration, ML-calibrated confidence scoring, full-state DILRMP interoperability, IVR/low-literacy interface, dispute-prediction backtesting against real tribunal cases.

---

## 10. Prompt for Antigravity — build command

```
ROLE: You are building IKNOS, an Android + backend land-record reconciliation
system for a Smart India Hackathon prototype. Follow this PRD exactly — do not
invent scope beyond what is specified, and do not silently downgrade a specified
component to something simpler without flagging it back to me first.

BUILD, IN THIS ORDER:

1. BACKEND (FastAPI + PostgreSQL/PostGIS)
   - Implement the exact table schemas in Section 7 of the attached PRD:
     parcels (PostGIS geometry), ror, mutation, cases (JSONB).
   - Seed with synthetic-but-structurally-realistic data: 30 parcels, deliberately
     inject inconsistencies (5 with registration conflicts, 5 with pending
     mutations, 5 with spatial mismatch >5%) so the case queue has real variety.
   - Implement REST endpoints: GET /parcels/{id}, GET /cases (filterable by
     confidence_score/status), POST /cases/{id}/decision, POST /objections,
     POST /missions/{id}/images (accepts image + sidecar JSON from Section 7).
   - Implement the confidence-fusion formula from Section 6 as a plain weighted
     function over the case object fields — deterministic, not a model, and
     expose the weights as a config file, not hardcoded magic numbers.

2. DRONE-SIDE (Raspberry Pi 4, Python)
   - pymavlink listener over the RPi4 ↔ Pixhawk 2.4.8 serial link (TELEM2/UART),
     subscribed to CAMERA_FEEDBACK MAVLink messages.
   - On each CAMERA_FEEDBACK event: capture via picamera2, write image.jpg +
     sidecar image.json exactly matching the schema in Section 7.
   - OpenCV Laplacian-variance blur check on each captured frame; write
     quality_flag into the same sidecar JSON.
   - Separate lightweight service: mavlink-router (or MAVProxy) rebroadcasting
     live GLOBAL_POSITION_INT, battery, and mode over WiFi UDP for the
     Surveyor-Drone tablet to consume. Do not build a custom telemetry protocol.

3. ANDROID APP — three role-gated experiences sharing one codebase and one API client
   - Auth: role stored server-side against account; UI renders conditionally by role.
   - CUSTOMER: My Parcels list, plain-language case summary (map confidence_score
     to a human label like "Under Review" / "No Issues Found" — never show raw
     ML internals), objection submission form with photo upload.
   - SURVEYOR-FIELD: Case queue sorted by confidence_score descending, case detail
     view rendering all evidence_refs, Approve/Reject/Escalate buttons writing to
     POST /cases/{id}/decision, offline-first local SQLite cache with sync-on-
     reconnect queue.
   - SURVEYOR-DRONE: Pre-flight AOI screen (import GeoJSON polygon OR
     "perimeter-walk" mode logging a GPS breadcrumb trail into a closed polygon),
     grid-plan overlay computed from camera FOV + target altitude + overlap
     inputs (implement this formula yourself — it is small, specific geometry,
     not a prebuilt tool), live mission screen consuming the WiFi/UDP telemetry
     stream from step 2 and rendering the drone's position as a moving dot over
     the grid overlay, with drift indicator ("on-track" / "drift: X m").

4. OFFLINE PHOTOGRAMMETRY PIPELINE
   - Integrate OpenDroneMap (prebuilt, do not reimplement stitching) as a batch
     job triggered on image-set upload completion. Output orthomosaic.tif +
     dsm.tif to object storage, register the URI against the mission_id.

5. ML MODELS — implement exactly as scoped in Section 6, no more, no less
   - Boundary extraction: U-Net, transfer-learned from a public field-boundary
     dataset (AI4Boundaries or Eurocrops), fine-tuned on a small hand-labeled set
     I will provide separately. Do not attempt to train from zero.
   - Temporal anomaly: STL decomposition + PELT changepoint on Sentinel-2 NDVI
     time series pulled via Google Earth Engine, masked to the parcel polygon
     (not scene-wide classification).
   - Fuzzy matching: Jaro-Winkler on name/khasra string pairs — a rule-based
     function, not a trained model.
   - Do NOT add any ML component beyond these three plus the deterministic
     confidence formula, even if it seems like an improvement — flag any such
     idea back to me instead of implementing it unasked.

6. AT EVERY STEP: if a required piece of information (API key, dataset path,
   exact camera FOV, exact overlap target) is missing, stop and ask rather than
   substituting a placeholder value silently into a working demo path.

Deliver working code with clear module boundaries matching the three-login
structure and the backend/drone split above, plus a README mapping each folder
to the PRD section it implements.
```
