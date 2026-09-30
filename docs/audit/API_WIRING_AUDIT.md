# TerraTrace — API Wiring Audit
**api.ts stubs vs. backend/app/main.py real routes — complete cross-reference**
*Generated: 2026-09-29*

> Legend: **WIRE NOW** = real endpoint exists, only the frontend stub needs to be swapped.
> **NEEDS BACKEND** = the backend endpoint is genuinely missing or incomplete.
> **SCHEMA GAP** = endpoint exists but the request/response shape differs from what api.ts expects.

---

## CATEGORY A — WIRE NOW (backend is real and working, frontend is still on stub)

These are your highest-leverage items. No new backend work required.

### 1. `fetchMissionProcessStatus` → `POST /missions/:id/trigger-odm` + `GET /missions/:id/odm-status`

**api.ts (line 341–347):** Returns a hardcoded `{ stage: 'stitching', progress_pct: 68 }` with `delay(500)`.

**Backend reality (`main.py` lines 340–361):**
- `POST /missions/{mission_id}/trigger-odm` — real, calls `odm_pipeline.submit_to_odm()`, gated to `SURVEYOR_DRONE`.
- `GET /missions/{mission_id}/odm-status?task_id=&project_id=` — real, calls `odm_pipeline.poll_odm_task()`.

**Fix:** Split the single stub function into two. Call `trigger-odm` on "Start Processing" button press, then poll `odm-status` every 3s. Map ODM status strings to the frontend's `stage` enum.

**Schema gap to handle:** `odm-status` requires `task_id` and `project_id` as query params. The `trigger-odm` response will need to return these so the poller can use them. Verify `odm_pipeline.submit_to_odm()` returns a `task_id`.

---

### 2. `submitFieldVerification` → `POST /cases/:id/field-verification`

**api.ts (line 374–384):** Returns `{ case_id, status: 'field_verification' }` after `delay(900)`. Explicitly comments "When FastAPI endpoint is live, uncomment."

**Backend reality (`main.py` lines 365–377):** Real endpoint exists, gated to `SURVEYOR_FIELD | SENIOR_FIELD`, calls `field_verification.submit_verification()` which writes to database.

**Schema gap:** The backend expects `schemas.FieldVerificationIn` — check that `body.findings_summary`, `body.observations`, `body.photo_refs`, `body.measurement_refs`, `body.verification_status`, `body.lat`, `body.lon` match the frontend's `FieldVerificationPayload`. The frontend currently sends `{ discrepancy_confirmed, findings, photo_uris, submitted_by }`. **These field names do not match.** Before uncommenting, align the payload shape or add a transformer.

---

### 3. `submitGrievance` → `POST /objections`

**api.ts (line 245–277):** Fake client-side case creation with local STUB_CASES mutation.

**Backend reality (`main.py` lines 258–275):** `POST /objections` — real, creates `Objection` row, parcel-access gated, returns `{ objection_id, status: 'submitted_pending_review' }`.

**Schema gap:** Frontend calls `/grievances`, backend is at `/objections`. Frontend sends `{ parcel_id, text, photo_uris, submitted_by }`. Backend expects `schemas.ObjectionIn` with `{ parcel_id, text, evidence_photo_ref }` (singular, not array). **Requires both URL change and payload restructure before wiring.**

---

### 4. `fetchCase` / `fetchCases` → `GET /cases/:id` and `GET /cases`

**api.ts (lines 64–85):** Both return from `STUB_CASES` in-memory array.

**Backend reality (`main.py` lines 161–202):** Both endpoints exist, real database queries, role-gated. `GET /cases` blocks `CUSTOMER` role (403). `GET /cases/:id` runs parcel-access assertion.

**Schema gap:** Backend returns SQLAlchemy `CaseOut` schema. Frontend `Case` type (`types/index.ts`) has fields like `spatial_mismatch_pct`, `boundary_shift_m`, `temporal_signal` etc. Verify the `CaseOut` schema in `schemas.py` exposes all these fields — they may be nested in `case_data: JSON` rather than top-level columns. **This is the most likely hidden schema gap in the whole codebase.** Check before wiring.

---

### 5. `fetchCurrentUserProfile` → `GET /users/me`

**api.ts (line 209–212):** Returns hardcoded `{ id: 'u1', name: 'Suresh Reddy', ... }`.

**Backend reality (`main.py` lines 124–126):** `GET /users/me` — real, returns `current_user` via `schemas.UserOut`, gated to authenticated user.

**Schema gap:** Frontend expects `{ id, name, phone, linked_parcels[] }`. Backend `UserOut` may expose `{ user_id, username, role, phone }`. Check `schemas.py UserOut` for the exact shape. `linked_parcels` almost certainly isn't in `UserOut` — may need a second call to `GET /my-cases` to derive it.

---

### 6. `fetchSurveyorAssignments` → `GET /surveyor/assignments`

**api.ts (lines 351–361):** Returns hardcoded assignment array filtered in-memory.

**Backend reality:** **Not found in `main.py`.** However, `GET /cases` with role filtering effectively gives the same data for an assigned surveyor. There is also `GET /my-cases` (line 174) for customers. A `/surveyor/assignments` route is **not yet implemented** — see Category B below.

---

### 7. `fetchDashboardStats` → `GET /admin/dashboard/stats`

**api.ts (line 50–60):** Derived client-side from STUB_CASES.

**Backend reality:** **Not found in `main.py`.** The backend has `GET /health` which returns `open_cases` count, but no dedicated `/admin/dashboard/stats` route with `sla_breaches`, `avg_resolution_days`, `cases_this_week`. **Genuinely missing** — see Category B.

---

### 8. `fetchGeometryLayers` → `GET /cases/:id/geometry-layers`

**api.ts (lines 90–124):** Returns hardcoded GeoJSON polygon with a simulated boundary offset.

**Backend reality:** **Not found in `main.py`.** However, `GET /map/parcels` (line 821) returns all parcels as a GeoJSON FeatureCollection from the real database. The specific `/cases/:id/geometry-layers` route is **missing** — but `GET /map/parcels` can substitute for cadastral layer. For AI boundary: `POST /cases/:id/spatial-discrepancy` (line 574) **already runs real U-Net geometry comparison** — the candidate GeoJSON would need to come from the drone pipeline output. **Partially covered, route missing.**

---

### 9. `fetchReasoning` → `GET /cases/:id/reasoning`

**api.ts (lines 155–169):** Constructs reasoning trace client-side by decomposing case fields.

**Backend reality:** No dedicated `/cases/:id/reasoning` route. However, `GET /cases/:id` returns a `case_data` JSON column that **includes `reasoning_trace`** (see `main.py` line 938 — it's stored during intake). **The data is there inside the case object already.** The frontend just needs to read `case.case_data.reasoning_trace` instead of recomputing it client-side.

---

### 10. `fetchEvidence` → `GET /cases/:id/evidence`

**api.ts (lines 128–151):** Constructs evidence bundle from STUB_CASES fields.

**Backend reality:** No `/cases/:id/evidence` route. Evidence exists across multiple real endpoints:
- Photos: `GET /cases/:id/images` (line 437) — real, returns mission images with GPS metadata.
- Audit trail: `GET /cases/:id/audit` (line 381) — real, returns full audit log.
- Spatial data: Inside `GET /cases/:id` case_data + `POST /cases/:id/spatial-discrepancy`.

**The single `fetchEvidence` stub needs to be replaced with 2–3 calls aggregated client-side, or a new `/cases/:id/evidence` aggregator endpoint needs to be added on the backend.**

---

## CATEGORY B — GENUINELY NEEDS BACKEND WORK

These have no matching backend implementation and cannot be wired today without new code.

| Function | Missing Route | Notes |
|---|---|---|
| `fetchDashboardStats` | `GET /admin/dashboard/stats` | Health endpoint has `open_cases` but not SLA/avg-resolution metrics. Need SQL aggregation. |
| `fetchSurveyorAssignments` | `GET /surveyor/assignments` | No dedicated route. Could re-use `GET /cases?assigned_to=:id` if that filter exists. Check `list_cases` query for an `assigned_to` filter. |
| `assignCase` | `POST /cases/:id/assign` | Not in `main.py`. The `decision_router` may have it — check `decision_routes.py`. |
| `fetchSurveyors` | `GET /admin/surveyors` | Not in `main.py`. Needs a query over `users` table filtered by surveyor roles. |
| `fetchFlightPlan` | `GET /missions/:id/plan` | Not in `main.py`. Mission state machine (`PATCH /missions/:id/state`) exists but no plan getter. |
| `fetchGeometryLayers` | `GET /cases/:id/geometry-layers` | Not in `main.py`. Use `GET /map/parcels` as partial substitute. |

---

## CATEGORY C — DO NOT WIRE YET (auth dependency)

| Function | Reason |
|---|---|
| `submitDecision` | Already calls real API (`apiFetch`) with no stub. But backend expects `SURVEYOR_FIELD | SENIOR_FIELD` role on the decision route — verify the JWT from the demo login carries the right role before testing this live. |
| All surveyor mission steps | ODM pipeline needs a running OpenDroneMap server. In dev, the call will reach the backend but `odm_pipeline.submit_to_odm()` will fail unless ODM is configured. Keep the stub as fallback. |

---

## FLY SCREEN — Fixed-Sequence Telemetry Fix

Confirmed: `SurveyorMissionFly.tsx` uses chained `setTimeout` at fixed ms offsets. Replace with this pattern (no new backend needed — just makes the demo non-reproducible):

```typescript
// Replace the 5 hardcoded setTimeouts with this:
const interval = setInterval(() => {
  setTelemetry(prev => ({
    battery_pct:  Math.max(0, prev.battery_pct - (0.3 + Math.random() * 0.4)),
    altitude_m:   60 + (Math.random() - 0.5) * 4,
    speed_ms:     7 + (Math.random() - 0.5) * 2,
    status:       'flying',
    position:     [prev.position[0] + 0.0001 * (Math.random()-0.5),
                   prev.position[1] + 0.0001 * (Math.random()-0.5)],
  }))
}, 1200)
```

This alone makes every demo run unique and eliminates the "same sequence every time" tell.

---

## PRIORITY ORDER (highest → lowest leverage)

1. **Fix Fly telemetry** — 15-minute change, eliminates the most obvious demo tell.
2. **Wire `fetchMissionProcessStatus`** — biggest credibility win; real ODM endpoint exists.
3. **Wire `submitFieldVerification`** — resolve the payload field name mismatch, then it's one line.
4. **Audit `CaseOut` schema** — before wiring `fetchCase`/`fetchCases`, confirm `case_data` vs. top-level columns, or you'll get runtime nulls.
5. **Wire `GET /users/me`** — straightforward, minor schema diff to resolve.
6. **Wire `POST /objections`** — rename URL + reshape payload.
7. **Add `GET /admin/dashboard/stats`** — short SQL aggregation in backend, then the frontend stub is a one-liner swap.
8. **Add `GET /surveyor/assignments`** — check if `decision_routes.py` already has assignment logic before writing from scratch.
