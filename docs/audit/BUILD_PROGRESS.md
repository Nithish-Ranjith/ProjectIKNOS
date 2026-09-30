# TerraTrace Web App — Build Progress Tracker

> Cross-checked against: `TerraTrace_App_Architecture.md` (all sections)
> Standards: Design system (navy/terracotta/sage, Cambria/Calibri/mono), 3-state fetches, no hardcoded URLs, stubs clearly marked, ML sync contract maintained.

---

## ✅ Step 1 — Auth + Role Routing (Architecture §1.2)
| Check | Status |
|---|---|
| Supabase Auth SDK (not hand-rolled) | ✅ |
| 3 roles: `user`, `surveyor`, `admin` | ✅ |
| Route guard `AuthRoute.tsx` — redirects to `/login` if no session | ✅ |
| Role mismatch → redirect to own dashboard | ✅ |
| Design system CSS (navy/terracotta/sage, Cambria/Calibri/mono) | ✅ |
| Env-driven Supabase URL and key, never hardcoded | ✅ |

---

## ✅ Step 2 — Admin Case Queue + Case Detail (Architecture §4.1–4.4)
| Check | Status |
|---|---|
| KPI cards (open cases, SLA breaches, avg. resolution, cases this week) | ✅ |
| Filter bar (status, risk threshold) — §4.2 | ✅ |
| Case table sorted by confidence descending | ✅ |
| 3-layer EvidenceMap (cadastral / AI boundary / drone) | ✅ |
| EvidenceTabs — 3 tabs: Spatial / Temporal / Records | ✅ |
| ReasoningTrace accordion with per-rule pass/fail breakdown | ✅ |
| Decision Modal: Approve/Reject/Escalate with mandatory reason | ✅ |
| Decision Modal: **Auth step before write** — matches §4.3 flowchart | ✅ |
| All 3 fetch states (loading/error/success) per panel | ✅ |

---

## ✅ Step 3 — User Dashboard + Parcel Detail (Architecture §2.1–2.3)
| Check | Status |
|---|---|
| Parcel cards grid with plain-language status badges | ✅ |
| Status labels: "No Issues", "Under Review" (never raw scores) | ✅ |
| Cadastral-only map (Users cannot see AI boundary or raw ML layers) | ✅ |
| "What Changed" expandable — only shown on closed cases | ✅ |
| 3-state fetch enforced | ✅ |

---

## ✅ Step 4 — Surveyor Home + Field Visit (Architecture §3.1, §3.3, §3.4)
| Check | Status |
|---|---|
| Assignment Dashboard with tabs: All / Drone Missions / Field Visits | ✅ |
| History panel (lazy loaded) §3.4 | ✅ |
| Field Visit: read-only Case Evidence Summary | ✅ |
| Discrepancy toggle + Findings textarea: required | ✅ |
| Photo capture with thumbnail preview + remove | ✅ |
| Submit: 3-state (pending / error / success screen) | ✅ |

---

## ✅ Step 5 — User Grievance Form
| Check | Status |
|---|---|
| Form connected to `/user/parcel/:id/grievance` | ✅ |
| Max 5 photos with thumbnail preview | ✅ |
| Validation and 3-state submit | ✅ |

---

## ✅ Step 6 — Admin Home KPI Charts
| Check | Status |
|---|---|
| Dynamic stats grid | ✅ |
| Action Required alert panel | ✅ |
| Quick Actions routing | ✅ |

---

## ✅ Step 7 — Mapbox GL JS Integration
| Check | Status |
|---|---|
| Token loaded via `.env` | ✅ |
| `MapboxMap.tsx` component | ✅ |
| Cadastral layer rendering | ✅ |
| AI Boundary conditionally shown based on role | ✅ |
| Used in `AdminCaseDetail` and `UserParcelDetail` and `SurveyorFieldVisit` | ✅ |

---

## ✅ Step 8 — Drone Mission Module (Architecture §3.2)
| Check | Status |
|---|---|
| **5-step workflow strictly adhered to**: Parcel → Plan → Fly → Capture → Process | ✅ |
| Step 1: Target Parcel Overview with Mapbox bounding | ✅ |
| Step 2: Automated Flight Plan review | ✅ |
| Step 3: Live Telemetry mock (battery, speed, altitude) | ✅ |
| Step 4: Capture/QC Gate (refly logic & <90% coverage rejection logic built-in) | ✅ |
| Step 5: Process polling status simulating U-Net backend states (stitching, extracting, failed, done) | ✅ |

---

## 🔲 Next Steps (Refining UX & Closing System Gaps)

| Priority | Task | Description | Dependency |
|---|---|---|---|
| 1 | **Surveyor Dashboard Fixes** | Add SLA countdown/urgency signals, fix left-border accent color drift, enforce 3-color strictness (remove blue). | None |
| 2 | **Aviation-Style Flight Plan** | Mapbox overlay drawing actual numbered waypoints and connecting lines, replacing the "4 waypoints" stub text. | Mapbox integration |
| 3 | **Field Visit Confirm Gate** | Add explicit confirmation step before final submission ("Submission is final") to adhere to write-action rules. | None |
| 4 | **Forensic Exhibit-Tag Photos** | Overlay "Exhibit A/B/C", GPS, and timestamps physically onto the photo thumbnails in Field Visit. | None |
| 5 | **Dynamic Coordinates** | Make Mapbox zoom to the actual parcel bounding box data instead of hardcoding to Vijayawada default center. | Backend Data |
| 6 | **Radial Confidence Gauge** | Replace plain confidence numbers with a speedometer-style arc gauge (green/amber/terracotta) for quick risk assessment. | None |
| 7 | **Admin Escalation Stub** | Ensure the "Escalate with mandatory reason" path in the decision modal correctly routes and persists in the stub DB. | None |
| 8 | **Live Drone Telemetry Bridge** | Design the architecture hook (WebSocket or polling contract) to replace the `setTimeout` mock when the real drone connects. | Hardware integration |
| 9 | **U-Net Inference Wiring** | Replace `POST /missions/:id/process` stub with live endpoint call when ML pipeline is ready. | Real model + dataset |
| 10 | **System Evaluation Dashboard** | Build `/admin/evaluation` with live Confusion Matrix, interactive Precision-Recall curve (adjustable threshold slider), Calibration/Reliability chart, and Workload-Reduction stat block. | `validate.py` extended data |

---

## ⚠ Pending — Need From You
| Item | Needed for | Blocking? |
|---|---|---|
| **Real U-Net model + dataset** | Inference endpoint wiring | No — we build shell now, wire later |
| **Drone Hardware Feed Protocol** | Hooking real telemetry into the React Mapbox context | No — mock covers the UI path |
| **Extended `validate.py` JSON** | The Evaluation Dashboard needs the precision/recall/confusion matrix output added to `evaluation_report.json` to feed the live UI. | No — we can mock the JSON structure for the UI now |
