# TerraTrace Recovery & Concept-Fidelity Audit

## Phase 1: Design System Verification
| CSS Token Set | STATUS | FILE:LINE | EVIDENCE |
| :--- | :--- | :--- | :--- |
| Canonical Root Block | REAL | `webapp/src/index.css:12-32` | The `--color-*` token system is fully restored and is the only active token block in the file. |
| Overhaul Aliases | DELETED | `webapp/src/index.css:37` | Overhaul aliases block `--accent-dark`, etc. has been entirely removed from the root. |
| Variable References in App | REAL | `webapp/src/**/*.tsx` | A script replaced all 300+ legacy variables with canonical equivalents; `grep` for undefined variables returns 0 results. |

## Phase 2: Fabrication & Simulation Removal
| Fabricated Element | STATUS | FILE:LINE | EVIDENCE |
| :--- | :--- | :--- | :--- |
| `applyJitter()` function | DELETED | `webapp/src/components/MapboxMap.tsx` | The function and all its usages were completely deleted; `grep` returns 0 results. |
| Render raw coordinates | REAL | `webapp/src/components/MapboxMap.tsx:31` | `polygonCoords` are used directly in Mapbox without artificial transformation. |
| Mapbox "SIMULATED" badge | REAL | `webapp/src/components/MapboxMap.tsx:254` | A red "SIMULATED" warning badge renders over the map when the AI layer is active. |
| Hardcoded Unsplash photos | DELETED | `webapp/src/pages/admin/AdminReportGenerator.tsx` | File was deleted; `grep` for `unsplash` returns 0 results. |
| Fake point cloud metrics | DELETED | `webapp/src/pages/admin/AdminReportGenerator.tsx` | File was deleted; the `AdminReportGenerator` route and button were also removed. |

## Phase 3: Route & Architecture Reconciliation
| Route | STATUS | FILE:LINE | EVIDENCE |
| :--- | :--- | :--- | :--- |
| `/login` | REAL | `webapp/src/App.tsx:27` | Route maps to the Login component. |
| `/login/otp`, `/login/2fa` | MISSING | `webapp/src/App.tsx` | The auth routes are not distinct paths in the router configuration. |
| `/user/home` | REAL | `webapp/src/App.tsx:31` | Route is mapped. |
| `/user/link-parcel` | MISSING | `webapp/src/App.tsx` | Not defined in router. |
| `/user/parcel/:id` | REAL | `webapp/src/App.tsx:32` | Route is mapped. |
| `/user/parcel/:id/grievance` | REAL | `webapp/src/App.tsx:33` | Route is mapped. |
| `/user/parcel/:id/history` | MISSING | `webapp/src/App.tsx` | Not defined in router. |
| `/user/grievance/confirmed` | MISSING | `webapp/src/App.tsx` | Not defined in router. |
| `/user/notifications` | MISSING | `webapp/src/App.tsx` | Not defined in router. |
| `/user/profile` | MISSING | `webapp/src/App.tsx` | Not defined in router. |
| `/surveyor/home` | REAL | `webapp/src/App.tsx:38` | Route is mapped. |
| `/surveyor/mission/:id/parcel`| REAL | `webapp/src/App.tsx:41` | Route is mapped. |
| `/surveyor/mission/:id/plan` | REAL | `webapp/src/App.tsx:42` | Route is mapped. |
| `/surveyor/mission/:id/fly` | REAL | `webapp/src/App.tsx:43` | Route is mapped. |
| `/surveyor/mission/:id/capture`| REAL | `webapp/src/App.tsx:44` | Route is mapped. |
| `/surveyor/mission/:id/process`| REAL | `webapp/src/App.tsx:45` | Route is mapped. |
| `/surveyor/field-visit/:id` | REAL | `webapp/src/App.tsx:39` | Route is mapped. |
| `/surveyor/history` | MISSING | `webapp/src/App.tsx` | Not defined in router. |
| `/surveyor/profile` | MISSING | `webapp/src/App.tsx` | Not defined in router. |
| `/admin/home` | REAL | `webapp/src/App.tsx:50` | Route is mapped. |
| `/admin/cases` | REAL | `webapp/src/App.tsx:51` | Route is mapped. |
| `/admin/cases/:id` | REAL | `webapp/src/App.tsx:52` | Route is mapped. |
| `/admin/surveyors` | MISSING | `webapp/src/App.tsx` | Not defined in router. |
| `/admin/records` | STUB | `webapp/src/App.tsx:54` | Mapped to `AdminHome` stub component. |
| `/admin/users` | STUB | `webapp/src/App.tsx:55` | Mapped to `AdminHome` stub component. |
| `/admin/settings` | STUB | `webapp/src/App.tsx:56` | Mapped to `AdminHome` stub component. |

## Phase 4: UI Element Fidelity
| UI Element / Action | STATUS | FILE:LINE | EVIDENCE |
| :--- | :--- | :--- | :--- |
| `SurveyorFieldVisit` Save button | REAL | `webapp/src/services/api.ts:444` | `submitFieldVerification` maps directly to the `POST /cases/:id/field-verification` backend endpoint. |
| `AdminCaseDetail` Action tabs | STUB / REAL | `webapp/src/services/api.ts:192` | Assign Surveyor is a frontend `[STUB]`, but Record Decision uses the real `POST /cases/:id/decision` endpoint. |
| Native Alert/Prompt usage | REAL | `webapp/src/pages/admin/AdminCaseDetail.tsx:326` | Custom in-DOM modals are used for submission, but the catch block for `assignCase` utilizes `alert(e.message)`. |

## Phase 5: Deep-Dive — The Drone Data Chain
| Constraint | STATUS | FILE:LINE | EVIDENCE |
| :--- | :--- | :--- | :--- |
| (a) `get_mission_plan()` | REAL | `backend/app/flight_planner.py:27` | The flight planner projects geometry to UTM, buffers the polygon, and calculates precise footprint overlaps (`(1 - side)`, `(1 - fwd)`) to produce real transect lines. |
| (b) ODM Pipeline Integration | REAL | `backend/app/main.py:379` | `POST /missions/{mission_id}/trigger-odm` invokes `odm_pipeline.submit_to_odm` which calls the real ODM container webhook. |
| (c) Hash Chain Validation | REAL | `backend/app/audit_service.py:95` | `verify_chain` fully traverses all audit logs, regenerating payload canonical SHA-256 hashes to guarantee mathematical integrity. |
