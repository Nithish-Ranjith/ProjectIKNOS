# TerraTrace — Application Architecture & Screen-Level Specification
**Three roles: USER · SURVEYOR · ADMIN/OFFICER**
Every module, every screen, every button — where it leads, and which layer owns it.

Table columns used throughout:
**Element** = what's on screen · **Type** = button/input/toggle/card · **On tap/submit** = what happens · **Leads to** = next screen/state · **Frontend** = route/component · **Backend** = endpoint it calls

---

## 0. ROLE MODEL — who does what

| Role | Core job | Sees | Cannot do |
|---|---|---|---|
| **USER** (landowner) | Track their own parcel(s), raise concerns | Only their own parcels, plain-language status | See raw scores, other parcels, internal evidence, decide anything |
| **SURVEYOR** | Collect evidence — drone flight + field visit | Assigned cases only, full evidence-collection tools | Cannot approve/reject a case, cannot see cases not assigned to them |
| **ADMIN/OFFICER** | Review evidence, decide, manage the system | Everything — full case queue, all surveyors, all records, system config | Nothing withheld — this is the highest-privilege role, gated by strongest auth |

---

## 1. SHARED INFRASTRUCTURE (every role passes through this)

### 1.1 App Shell
| Element | Type | On tap | Leads to | Frontend | Backend |
|---|---|---|---|---|---|
| Splash/loading screen | screen | auto, on load | checks session token | `/` root, `<AppBootstrap>` | `GET /auth/session` |
| Logo (top-left, all screens) | button | click | returns to that role's home dashboard | global `<Header>` | — |
| Role/user badge (top-right) | dropdown | click | opens account menu (Profile, Logout) | `<AccountMenu>` | — |
| Logout | button | click | clears session, redirects to Login | `<AccountMenu>` | `POST /auth/logout` |
| Notification bell | icon-button | click | opens notification panel (slide-over) | `<NotificationBell>` | `GET /notifications` |
| Global search (Admin/Officer only) | input | typed query | filters case/parcel results live | `<GlobalSearch>` | `GET /search?q=` |

### 1.2 Authentication (shared component, role resolved server-side)
| Screen | Element | Type | On submit | Leads to | Frontend | Backend |
|---|---|---|---|---|---|---|
| Login | Phone number input | input | validated on blur | enables Send OTP | `/login` `<LoginForm>` | — |
| Login | Send OTP | button | sends request | OTP screen | `/login` | `POST /auth/otp/send` |
| OTP | 6-digit input | input | auto-submits at 6 digits | verify call | `/login/otp` | — |
| OTP | Verify | button | validates code | routes by returned role | `/login/otp` | `POST /auth/otp/verify` → returns `{role, token}` |
| OTP | Resend | button (disabled during countdown) | re-sends | resets timer | `/login/otp` | `POST /auth/otp/send` |
| — | Admin/Officer only: 2FA step | input | after OTP, second factor (TOTP app code) required | Admin dashboard | `/login/2fa` | `POST /auth/2fa/verify` |

**Routing on success:** `role: user` → `/user/home` · `role: surveyor` → `/surveyor/home` · `role: admin` → `/admin/home`

---

## 2. ROLE: USER

### 2.1 Module — Dashboard (`/user/home`)
Layout: header (shared) + welcome line + parcel-card grid + empty state if none.

| Element | Type | On tap | Leads to | Frontend | Backend |
|---|---|---|---|---|---|
| Parcel card (per linked parcel) | card/button | click | opens that parcel's detail | `<ParcelCard>` → `/user/parcel/:id` | `GET /parcels/:id/summary` |
| Status pill on card (`No Issues`/`Under Review`/`Action Needed`) | badge | — (display only) | — | derived from case status, never raw score | `GET /parcels/:id/summary` |
| "Link a Parcel" | button | click | opens Link Parcel screen | `/user/link-parcel` | — |
| Empty-state illustration + CTA | button | click | same as above | `/user/link-parcel` | — |

### 2.2 Module — Link a Parcel (`/user/link-parcel`)
| Element | Type | On tap/submit | Leads to | Frontend | Backend |
|---|---|---|---|---|---|
| Search by Parcel ID / Survey No. | input | submit | fetches match | preview card renders | `GET /parcels/search?q=` |
| "Scan Cadastral QR" | button | opens camera | reads QR → auto-fills search | `<QRScanner>` | — |
| Preview card (village, area shown for confirmation) | card | — | confirm before linking | `<ParcelPreview>` | — |
| "Confirm & Link" | button | click | adds to user's account | back to `/user/home`, new card appears | `POST /users/me/parcels` |
| "Not found" state | text | — | prompts re-check of number | — | — |

### 2.3 Module — Parcel / Case Detail (`/user/parcel/:id`)
| Element | Type | On tap | Leads to | Frontend | Backend |
|---|---|---|---|---|---|
| Map (cadastral boundary only, satellite base) | map widget | pan/zoom | — | `<MapView layer="cadastral-only">` | `GET /parcels/:id/geometry` |
| Plain-language status block | text card | — (display) | copy mapped from internal status enum | `<StatusSummary>` | `GET /cases?parcel_id=:id` |
| "What changed" summary (only if case approved) | expandable card | click | expands before/after in plain language | `<ChangeSummary>` | `GET /cases/:id/summary` |
| "Raise a Concern" | button | click | opens Grievance form | `/user/parcel/:id/grievance` | — |
| "View History" | button | click | opens past closed cases for this parcel | `/user/parcel/:id/history` | `GET /parcels/:id/history` |

### 2.4 Module — Grievance / Objection (`/user/parcel/:id/grievance`)
| Element | Type | On tap/submit | Leads to | Frontend | Backend |
|---|---|---|---|---|---|
| Description text field | input (required) | — | enables Submit once filled | `<GrievanceForm>` | — |
| "Attach Photo" | button | opens camera/gallery | thumbnail preview appears | `<PhotoPicker>` | — |
| Submit | button (disabled until text + ≥1 photo) | click | server runs validity check | success → confirmation screen; fail → inline reason shown | `POST /grievances` |
| Confirmation screen | screen | — | "Done" returns home | `/user/grievance/confirmed` | — |

### 2.5 Module — Notifications (`/user/notifications`)
| Element | Type | On tap | Leads to | Frontend | Backend |
|---|---|---|---|---|---|
| Notification list item | card | click | opens the related parcel/case | routes to `/user/parcel/:id` | `GET /notifications` |
| "Mark all read" | button | click | clears unread badges | — | `POST /notifications/read-all` |

### 2.6 Module — Profile & Settings (`/user/profile`)
| Element | Type | On tap | Leads to | Frontend | Backend |
|---|---|---|---|---|---|
| Name, phone (display) | text | — | — | `<ProfileCard>` | `GET /users/me` |
| Language preference | dropdown | select | updates UI language | — | `PATCH /users/me` |
| DPDP consent status | toggle (view/revoke) | click | opens consent detail | `<ConsentPanel>` | `GET/PATCH /users/me/consent` |
| Logout | button | click | see 1.1 | — | `POST /auth/logout` |

---

## 3. ROLE: SURVEYOR

### 3.1 Module — Dashboard (`/surveyor/home`)
| Element | Type | On tap | Leads to | Frontend | Backend |
|---|---|---|---|---|---|
| Assigned Missions tab | tab | click | filters list to drone-flight cases | `<AssignmentTabs>` | `GET /surveyor/assignments?type=mission` |
| Assigned Field Visits tab | tab | click | filters list to verification-only cases | `<AssignmentTabs>` | `GET /surveyor/assignments?type=field_visit` |
| Assignment card | card | click | opens that case's relevant module (3.3 or 3.4) | routes conditionally | `GET /cases/:id` |
| Sync status indicator | badge | — | shows online/offline/pending-count | `<SyncBadge>` | local queue state |

### 3.2 Module — Drone Mission (5-step flow, `/surveyor/mission/:id/*`)
*(Full detail already specified in the earlier functional spec — Steps 1–5: Parcel → Plan → Fly → Capture → Process. Mapping below is the FE/BE layer for each.)*

| Step | Key screen | Key button | Leads to | Frontend | Backend |
|---|---|---|---|---|---|
| 1 — Parcel | `/surveyor/mission/:id/parcel` | "Approve" boundary | unlocks Step 2 | `<ParcelVerify>` | `GET /parcels/:id/geometry`, `POST /missions/:id/approve-aoi` |
| 1 — Parcel (no geometry) | same route, perimeter-walk mode | "Close Polygon" | saves walked AOI | `<PerimeterWalk>` | `POST /missions/:id/aoi` |
| 2 — Plan | `/surveyor/mission/:id/plan` | "Lock Plan" | unlocks Step 3 | `<GridPlanner>` | `POST /missions/:id/plan` |
| 3 — Fly | `/surveyor/mission/:id/fly` | "Pause Guidance" / "End Mission" | stops tracking / ends flight | `<LiveGuidance>` | `WS /missions/:id/telemetry` (websocket, live) |
| 4 — Capture | `/surveyor/mission/:id/capture` | "Accept Dataset" / "Recommend Re-fly" | unlocks Step 5 / returns to Step 3 for target block | `<CoverageQC>` | `POST /missions/:id/images`, `GET /missions/:id/qc` |
| 5 — Process | `/surveyor/mission/:id/process` | "Done" | returns to dashboard | `<ProcessingStatus>` | `POST /missions/:id/process`, `GET /missions/:id/status` (polling or websocket) |

### 3.3 Module — Field Verification (`/surveyor/field-visit/:id`)
| Element | Type | On tap/submit | Leads to | Frontend | Backend |
|---|---|---|---|---|---|
| Case evidence summary (read-only) | card | — | context before visiting | `<CaseSummaryReadOnly>` | `GET /cases/:id` |
| "Capture Photo" (geotagged automatically) | button | opens camera | adds to evidence list | `<GeotaggedCamera>` | device GPS + local queue |
| Findings text field | input | — | required before Save | `<FindingsForm>` | — |
| "Confirmed Discrepancy" / "No Discrepancy" | toggle | select one | required before Save | `<FindingsForm>` | — |
| "Save & Submit" | button | click | attaches field_verification block, pushes to Admin/Officer queue | back to `/surveyor/home` | `POST /cases/:id/field-verification` |

### 3.4 Module — Mission History (`/surveyor/history`)
| Element | Type | On tap | Leads to | Frontend | Backend |
|---|---|---|---|---|---|
| Past mission/visit list | list | click item | opens read-only detail | `<HistoryList>` | `GET /surveyor/history` |

### 3.5 Module — Profile & Settings
Same pattern as 2.6, plus:
| Element | Type | On tap | Leads to | Frontend | Backend |
|---|---|---|---|---|---|
| DGCA pilot credential (display) | text | — | — | `<ProfileCard>` | `GET /users/me` |
| Device pairing status (drone-phone link) | status card | "Re-pair" button | opens pairing flow | `<DevicePairing>` | `POST /devices/pair` |

---

## 4. ROLE: ADMIN/OFFICER

### 4.1 Module — Dashboard (`/admin/home`)
| Element | Type | On tap | Leads to | Frontend | Backend |
|---|---|---|---|---|---|
| KPI cards (open cases, SLA breaches, avg. resolution time) | cards | click | drills into filtered Case Queue | `<KPICard>` | `GET /admin/dashboard/stats` |
| "Lock TTL Alerts" widget | list | click item | opens that case directly | `<TTLAlerts>` | `GET /admin/locks/expiring` |
| Trigger-source breakdown chart | chart | — | — | `<TriggerChart>` | `GET /admin/dashboard/triggers` |

### 4.2 Module — Case Queue & Review (`/admin/cases`)
| Element | Type | On tap | Leads to | Frontend | Backend |
|---|---|---|---|---|---|
| Sort/filter bar (score, status, trigger, tier-required) | controls | change | refreshes list | `<CaseFilters>` | `GET /cases?filters...` |
| Case row | row | click | opens Case Detail | `/admin/cases/:id` | `GET /cases/:id` |
| Priority/score column | text | — | visible here only (never to User) | — | — |

### 4.3 Module — Case Detail & Decision (`/admin/cases/:id`)
| Element | Type | On tap | Leads to | Frontend | Backend |
|---|---|---|---|---|---|
| Map — 3 toggle layers (cadastral / AI boundary / drone coverage) | map + layer toggles | toggle | shows/hides layer | `<EvidenceMap>` | `GET /cases/:id/geometry-layers` |
| Evidence tabs (Spatial / Temporal / Records) | tabs | click | switches evidence panel | `<EvidenceTabs>` | `GET /cases/:id/evidence` |
| Reasoning trace (expandable) | accordion | click | shows per-rule pass/fail | `<ReasoningTrace>` | `GET /cases/:id/reasoning` |
| "Request Field Visit" | button (if not yet done) | click | assigns to a surveyor | opens Assign modal | `POST /cases/:id/assign` |
| "Record Decision" | button | click | opens Decision modal | `<DecisionModal>` | — |
| Decision modal: Approve/Reject/Escalate radio | radio | select | requires reason field | — | — |
| Decision modal: Reason text | input (required) | — | enables Confirm | — | — |
| Decision modal: Auth step (PIN/biometric) | input | submit | **must complete before any write fires** | — | `POST /auth/reauth` |
| "Confirm Decision" | button | click | fires record update, closes case | back to Case Queue, case removed from active list | `POST /cases/:id/decision` |

### 4.4 Module — Assignment & Workforce (`/admin/surveyors`)
| Element | Type | On tap | Leads to | Frontend | Backend |
|---|---|---|---|---|---|
| Surveyor list (with current workload count) | list | click | opens surveyor detail | `<SurveyorList>` | `GET /admin/surveyors` |
| Assign modal: surveyor picker | dropdown | select | assigns case | — | `POST /cases/:id/assign` |
| Surveyor detail: assigned cases, completion rate | card | — | — | `<SurveyorProfile>` | `GET /admin/surveyors/:id` |

### 4.5 Module — Record Management / Audit Trail (`/admin/records`)
| Element | Type | On tap | Leads to | Frontend | Backend |
|---|---|---|---|---|---|
| Record search (parcel/khasra/owner) | input | submit | shows matching RoR/mutation/registration rows | `<RecordSearch>` | `GET /records/search?q=` |
| Versioned record view (old/new state diff) | card | click parcel | shows full version history | `<VersionHistory>` | `GET /parcels/:id/versions` |
| Hash-chain viewer | table | click entry | shows hash, previous_hash, verifies chain integrity | `<AuditChainViewer>` | `GET /audit/chain?parcel_id=` |

### 4.6 Module — User & Access Management (`/admin/users`)
| Element | Type | On tap | Leads to | Frontend | Backend |
|---|---|---|---|---|---|
| User/Surveyor account list | table | click | opens edit panel | `<UserManagement>` | `GET /admin/accounts` |
| "Add Account" | button | fill form, submit | creates new Surveyor/Admin account | — | `POST /admin/accounts` |
| Role/tier assignment dropdown | dropdown | change | updates permission tier | — | `PATCH /admin/accounts/:id` |
| "Deactivate" | button | confirm | disables login for that account | — | `POST /admin/accounts/:id/deactivate` |

### 4.7 Module — System Configuration (`/admin/settings`)
| Element | Type | On tap | Leads to | Frontend | Backend |
|---|---|---|---|---|---|
| Confidence-weight sliders (per factor) | sliders | adjust, save | recalculation formula updates (must still sum to 1.0 — validated client + server side) | `<WeightConfig>` | `GET/PUT /admin/config/weights` |
| Lock TTL setting | input | save | changes system-wide lock timeout | `<LockConfig>` | `PUT /admin/config/lock-ttl` |
| Threshold-scaling formula params | input group | save | updates spatial-discrepancy sensitivity | `<ThresholdConfig>` | `PUT /admin/config/thresholds` |

### 4.8 Module — Reports & Export (`/admin/reports`)
| Element | Type | On tap | Leads to | Frontend | Backend |
|---|---|---|---|---|---|
| Date-range picker | input | select | filters report scope | `<ReportBuilder>` | — |
| "Generate Report" | button | click | builds summary (cases by status/village/officer) | shows preview | `GET /admin/reports/generate?range=` |
| "Export CSV/PDF" | button | click | downloads file | — | `GET /admin/reports/export?format=` |

---

## 5. CROSS-ROLE DATA FLOW — one case, start to finish

```
[Satellite trigger OR User grievance OR Admin manual audit]
        ↓
Case created (status: OPEN) ── visible in ADMIN Case Queue (4.2)
        ↓
Admin clicks "Request Field Visit" (4.3) ── assigns SURVEYOR (4.4)
        ↓
SURVEYOR sees it in Dashboard (3.1) → runs Drone Mission (3.2) and/or Field Visit (3.3)
        ↓
SURVEYOR "Save & Submit" ── case updates, returns to ADMIN queue with new evidence
        ↓
Admin opens Case Detail (4.3), reviews evidence + reasoning trace
        ↓
Admin "Record Decision" → auth step → Confirm ── case closes
        ↓
USER's Parcel Detail (2.3) status updates automatically to reflect the closed case
```

---

## 6. MASTER BACKEND ENDPOINT LIST

```
AUTH        POST /auth/otp/send · POST /auth/otp/verify · POST /auth/2fa/verify
            POST /auth/logout · GET /auth/session · POST /auth/reauth

USER        GET /parcels/:id/summary · GET /parcels/:id/geometry · GET /parcels/:id/history
            GET /parcels/search · POST /users/me/parcels · GET /users/me · PATCH /users/me
            POST /grievances · GET /notifications · POST /notifications/read-all

SURVEYOR    GET /surveyor/assignments · GET /cases/:id
            POST /missions/:id/approve-aoi · POST /missions/:id/aoi · POST /missions/:id/plan
            WS /missions/:id/telemetry · POST /missions/:id/images · GET /missions/:id/qc
            POST /missions/:id/process · GET /missions/:id/status
            POST /cases/:id/field-verification · GET /surveyor/history · POST /devices/pair

ADMIN       GET /admin/dashboard/stats · GET /admin/locks/expiring · GET /admin/dashboard/triggers
            GET /cases · GET /cases/:id/geometry-layers · GET /cases/:id/evidence
            GET /cases/:id/reasoning · POST /cases/:id/assign · POST /cases/:id/decision
            GET /admin/surveyors · GET /admin/surveyors/:id
            GET /records/search · GET /parcels/:id/versions · GET /audit/chain
            GET /admin/accounts · POST /admin/accounts · PATCH /admin/accounts/:id
            POST /admin/accounts/:id/deactivate
            GET/PUT /admin/config/weights · PUT /admin/config/lock-ttl · PUT /admin/config/thresholds
            GET /admin/reports/generate · GET /admin/reports/export

SHARED      GET /search (admin-scoped)
```

---

## 7. MASTER FRONTEND ROUTE MAP

```
/                              → bootstrap/splash
/login  /login/otp  /login/2fa → auth

/user/home
/user/link-parcel
/user/parcel/:id
/user/parcel/:id/grievance
/user/parcel/:id/history
/user/grievance/confirmed
/user/notifications
/user/profile

/surveyor/home
/surveyor/mission/:id/parcel|plan|fly|capture|process
/surveyor/field-visit/:id
/surveyor/history
/surveyor/profile

/admin/home
/admin/cases
/admin/cases/:id
/admin/surveyors
/admin/records
/admin/users
/admin/settings
/admin/reports
```

---

## 8. WHAT TO BUILD FIRST (given everything above)

1. Auth shell + role routing (Section 1) — nothing else works without this.
2. Admin Case Queue + Case Detail (4.2, 4.3) against seeded data — proves FE↔BE works with zero ML dependency.
3. User Dashboard + Parcel Detail (2.1, 2.3) reading the same seeded cases — proves the same case renders correctly for two different roles.
4. Decision flow (4.3's modal) — closes the loop, updates User's view live.
5. Surveyor Field Visit (3.3) — simplest surveyor module, no drone/ML dependency.
6. Drone Mission module (3.2) + U-Net endpoint — most complex, build last, once everything around it already works.
