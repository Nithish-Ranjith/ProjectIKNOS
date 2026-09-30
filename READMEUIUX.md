# TerraTrace MVP Backend — 2-day hackathon scope

## What's here (built, real, runs)
- `parcels`, `ror`, `mutation`, `registration`, `cases`, `objections` tables (PostGIS)
- Deterministic confidence-fusion formula (`app/confidence.py`) — weighted,
  config-driven (`app/config/weights.json`, weights sum to 1.0, validated at
  startup), produces a full reasoning trace. No hardcoded global IoU cutoff —
  spatial discrepancy is normalized against each parcel's own scale.
- REST API: `GET /parcels/{id}`, `GET /cases` (filter by status/confidence),
  `GET /cases/{id}`, `POST /cases/{id}/decision`, `POST /objections`,
  `POST /missions/{id}/images` (real image + sidecar JSON storage),
  `POST /cases/{id}/recompute` (for wiring in the ML teammate's Sentinel-2
  output without touching the scoring math).
- `seed.py` — 30 synthetic parcels (5 spatial mismatch, 5 registration
  missing, 5 mutation pending, 15 clean), cases generated from the real
  formula, plus one golden demo parcel for the live walkthrough.

## What's NOT here (deliberately, not accidentally)
- No auth / role enforcement — anyone can call any endpoint. Fine for a
  local demo, not fine for anything real. Roadmap item.
- No hash-chained audit log, no parcel lock/TTL, no authority-tier gating.
  These are real governance requirements for a production system and
  explicitly out of scope for a 2-day build — say so in the pitch, don't
  fake them.
- `POST /cases/{id}/decision` records the decision but does **not** write
  back to `ror`/`mutation`/`parcels`. Approval → record mutation is the one
  irreversible step in the real system and isn't safe to fake for a demo.
- U-Net boundary extraction is NOT wired in here. Feed `recompute` with
  `area_diff_pct`/`boundary_shift_m` from wherever the ML teammate's
  pipeline lands — hand-digitized GeoJSON fallback or a real model output,
  the API doesn't care which.

## Setup
```bash
pip install -r requirements.txt
# Postgres must have PostGIS enabled on the target DB:
#   CREATE EXTENSION IF NOT EXISTS postgis;
export DATABASE_URL="postgresql://user:pass@localhost:5432/terratrace"
python seed.py
uvicorn app.main:app --reload
```

## Surveyor-Field UI
`frontend/field_ui.html` — single file, no build step, no npm install.
Open it directly in a browser (or serve it on the tablet). It's a case
queue (sorted by confidence, descending) + case dossier + decision form,
talking to the FastAPI backend over plain `fetch`.

This is a **browser web app, not native Android** — a real Android build
for one role in the remaining time wasn't a good trade against getting the
reconciliation logic solid. State this plainly if asked: it runs fine on
the tablet's browser for the demo, native Android is roadmap.

Set the backend URL before opening if it's not on localhost:8000 — add a
`<script>window.API_BASE = "http://YOUR_HOST:8000";</script>` before the
main `<script>` tag, or edit the `API_BASE` constant directly.

Every field this UI reads was cross-checked against what `seed.py` and
`app/main.py` actually write into `case_data` — no guessed field names.

## Surveyor-Drone mission UI
`frontend/drone_mission_ui.html` — Plan screen (stepper step 2 of 5).
Single file, no build step. Recreates the reference mockup's visual
direction, but only what's real got built as real:

- **Grid/lawnmower plan is computed, not decorative** — block count, line
  spacing, and photo-point spacing come from actual camera FOV/altitude/
  overlap math (`CONFIG.camera`), same formula the PRD specifies. Verified
  in testing: an early version silently mismatched the SVG polygon's scale
  against the stated 4.05 ha parcel area (4x off), which fed wrong
  real-world distances into that math. Fixed by deriving meters-per-unit
  from the parcel's own stated area rather than assuming 1:1.
- **U-Net confidence (0.87) is a flagged placeholder**, not a real model
  output — labeled on-screen and in `CONFIG.boundary.confidence_source`.
  Replace with a real number once boundary extraction actually runs
  (stub or trained model), or drop the confidence badge entirely rather
  than show a fabricated one.
- **Live telemetry is simulated**, animating along the real computed
  flight path — clearly labeled on-screen. Real telemetry needs a
  WebSocket bridge in front of `mavlink-router` relaying MAVLink UDP into
  the browser; that bridge is NOT built. Say so if asked.
- **Aerial "imagery" is a procedural placeholder texture**, not a real
  orthomosaic — labeled on-screen. Swap for the real GeoTIFF render once
  ODM output exists for your golden demo parcel.
- Steps 1, 3, 4, 5 of the stepper are stubs (click shows an honest "not
  built yet" alert) — only Plan (step 2) is functional. Ask if you want
  another step built next; building all 5 blind wasn't a good trade
  against getting Plan right.

## Wiring in the Sentinel-2 signal
`ml/` contains the temporal-analysis pipeline:
- `ml/gee_ndvi.py` — pulls a cloud-masked Sentinel-2 NDVI series for one
  parcel via Google Earth Engine.
- `ml/temporal_analysis.py` — per-calendar-year seasonal amplitude vs. a
  baseline, not STL+PELT-on-trend (that version was tested against
  synthetic data first and produced INVERTED results — a stable parcel
  scored higher instability than a genuinely converted one — so it was
  replaced before shipping, not tuned blind). Verified against synthetic
  data: a parcel that loses its seasonal NDVI swing correctly scores
  higher than one that keeps cycling normally, and correctly identifies
  the onset year.
- `ml/run_temporal.py` — CLI glue: pull → analyze → POST to `/recompute`.

**Blocking requirement, not optional:** GEE needs a Cloud project
registered for Earth Engine access, plus either `earthengine authenticate`
run once locally or a service account JSON key
(`GEE_SERVICE_ACCOUNT_KEY` env var). Set `GEE_PROJECT` to the project ID.
Without this, `gee_ndvi.py` fails loudly at `ee.Initialize()` rather than
returning fake data — get this set up on day 1, not the morning of demo.

```bash
python -m ml.run_temporal \
  --case-id CASE-2026-000001 \
  --geojson parcel.geojson \
  --start 2023-01-01 --end 2026-08-31 \
  --area-diff-pct 18.1 --boundary-shift-m 2.4
```

If Sentinel-2 data is unavailable or analysis quality is `insufficient`
(too few cloud-free scenes), the script deliberately omits
`instability_score` rather than feeding in a fake number — the case scores
on spatial+record evidence alone in that case, which is the honest
fallback, not a bug.
