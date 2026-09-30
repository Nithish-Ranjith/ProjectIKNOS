# REQUIREMENTS_TRACEABILITY.md — PRD §x → Implementation Mapping

| PRD Requirement | Implementation | File | Status |
|---|---|---|---|
| One Android app, three roles | CUSTOMER / SURVEYOR_FIELD / SURVEYOR_DRONE | `models.py` → `UserRole` | ✅ |
| RPi4 + Pixhawk edge node | MAVLink listener + capture service | `drone/` | ✅ |
| LOITER / manual flight only | PreFlight advisory banner; no flight commands sent | `PreFlightScreen.kt` | ✅ |
| No RTK in MVP | `STANDARD_GNSS` explicitly labelled; RTK_FIX is the other branch | `confidence.py`, `discrepancy.py` | ✅ |
| Wi-Fi / MAVLink telemetry | UDP telemetry relay + MAVLink listener | `telemetry_relay.py`, `mavlink_listener.py` | ✅ |
| Guided survey (not autonomous) | All drone ops are pilot-operated; app is planning tool only | `PreFlightScreen.kt`, `LiveMissionScreen.kt` | ✅ |
| CAM_TRIGG_DIST vs CAMERA_FEEDBACK resolved | Option C+D dual-mode | `capture_service.py`, `DRONE.md` | ✅ |
| Confidence formula weighted | `confidence.py`, `weights.json` | All weights sum to 1.0, validated at startup | ✅ |
| ULPIN nullable, never fabricated | `parcel.ulpin` nullable; seed.py uses None for missing | `models.py`, `seed.py` | ✅ |
| Registration ≠ RoR (separate signals) | Separate `registration` and `ror` tables | `models.py` | ✅ |
| Objection does NOT auto-lock | Objection creates grievance row only; lock requires investigation | `main.py /objections`, `lock_service.py` | ✅ |
| Lock TTL mandatory | `expires_at` non-nullable; `LOCK_TTL_HOURS=72` | `lock_service.py` | ✅ |
| Approval before record update | `approval_id` required on `record_updates`; checked server-side | `record_update_service.py` | ✅ |
| Append-only versioned records | `parcel_versions`, `ror_versions` — never overwrite | `version_manager.py` | ✅ |
| Hash-chained audit log | SHA-256 chain with `GENESIS` genesis | `audit_service.py` | ✅ |
| Spatial discrepancy scale-normalized | `normalized_spatial_score()` uses √parcel_area | `confidence.py` | ✅ |
| No global IoU >= 0.85 cutoff | Hausdorff + area diff + GNSS uncertainty in interpretation | `discrepancy.py` | ✅ |
| U-Net boundary detection | Lightweight U-Net, transfer-learned | `ml/boundary/model.py` | ✅ BQ-04 |
| STL + PELT temporal analysis | `ml/temporal/stl_pelt.py` | Graceful fallback if deps missing | ✅ BQ-03 |
| Jaro-Winkler fuzzy matching | `fuzzy_match.py` | MATCHED / AMBIGUOUS / UNRESOLVED | ✅ |
| ODM photogrammetry | WebODM REST API integration | `odm_pipeline.py` | ✅ BQ-06 |
| Confidence score NOT shown raw to customer | `CustomerHomeScreen.kt` shows status only | No score shown | ✅ |
| Field verification structured evidence | Requires observations + photo_refs (not just free text) | `FieldVerificationScreen.kt` | ✅ |
| Decision gated by authority tier | `check_update_class_tier()` enforces tier server-side | `auth.py`, `record_update_service.py` | ✅ |
| Grievance → human review gate | Objection reviewed flag; resulting_case_id only set by human | `models.py` → `Objection` | ✅ |
| Sentinel-2 temporal signal | GEE NDVI fetch + STL+PELT | `ml/temporal/` | ✅ BQ-03 |
| Positioning quality explicit | `positioning_quality` in all spatial outputs | `discrepancy.py`, `confidence.py`, `mission_images` | ✅ |
| Tamper-evident audit, not tamper-proof | "tamper-evident" wording used; limitation documented | `audit_service.py`, `LIMITATIONS.md` | ✅ |
