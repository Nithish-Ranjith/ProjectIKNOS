# API Reference — TerraTrace MVP

**Base URL:** `http://<backend-host>:8000`

All protected endpoints require `Authorization: Bearer <JWT>`.

---

## Auth

### `POST /auth/login`
**Body:** `{"username": "...", "password": "..."}`
**Response:** `{"access_token": "...", "token_type": "bearer", "role": "CUSTOMER"}`
**Roles:** Public

---

## Users

### `GET /users/me`
Returns the currently authenticated user's profile.
**Roles:** All authenticated

---

## Parcels

### `GET /parcels/{parcel_id}`
Returns parcel metadata. CUSTOMER role scoped to owned parcels.
**Roles:** All authenticated

---

## Cases

### `GET /cases`
List all cases. Filterable by `?status=open|field_verification|closed`.
CUSTOMER role forbidden.
**Roles:** SURVEYOR_FIELD, SURVEYOR_DRONE, SENIOR_FIELD

### `GET /cases/{case_id}`
Get a single case with full evidence bundle.
**Roles:** All authenticated (CUSTOMER scoped to owned parcels)

### `POST /cases/{case_id}/decision`
Submit a case decision (reject or escalate). Not for approval.
**Body:** `{"decision": "reject"|"escalate", "reason": "..."}`
**Roles:** SURVEYOR_FIELD, SENIOR_FIELD

### `POST /cases/{case_id}/approve`
Create an authenticated approval gate.
**Body:** `{"update_class": "MUTATION"|"OWNERSHIP"|..., "reason": "..."}`
Authority tier enforced server-side.
**Roles:** SURVEYOR_FIELD (tier 1), SENIOR_FIELD (tier 2)

### `POST /cases/{case_id}/record-update`
Apply a typed record update using a valid approval.
**Body:** `{"approval_id": "...", "target_record_type": "parcel"|"ror", "target_record_id": "...", "changes": [...]}`
**Roles:** SURVEYOR_FIELD, SENIOR_FIELD

### `GET /cases/{case_id}/audit`
Get the full hash-chained audit log for a case.
**Roles:** All authenticated (CUSTOMER scoped)

### `GET /audit/verify/{case_id}`
Verify audit chain integrity. Returns `{"valid": true/false, "first_broken_seq": int|null}`.
**Roles:** All authenticated

---

## Objections

### `POST /objections`
Submit a citizen grievance. Does NOT lock parcel or open a case automatically.
**Body:** `{"parcel_id": "...", "text": "..."}`
**Roles:** CUSTOMER

---

## Field Verification

### `POST /cases/{case_id}/field-verification`
Submit structured field evidence.
**Body:** `{"observations": [...], "photo_refs": [...], "measurement_refs": [...], "verification_status": "CONFIRMED"|"DISPUTED"|"INCONCLUSIVE", "findings_summary": "..."}`
**Roles:** SURVEYOR_FIELD, SENIOR_FIELD

---

## Missions

### `POST /missions`
Create a new mission in DRAFT state.
**Body:** `{"case_id": "...", "parcel_id": "..."}`
**Roles:** SURVEYOR_DRONE

### `PATCH /missions/{mission_id}/state`
Advance mission state machine.
**Body:** `{"state": "READY"|"ACTIVE"|"PAUSED"|"COMPLETED"|...}`
Invalid transitions return 400.
**Roles:** SURVEYOR_DRONE

### `POST /missions/{mission_id}/images`
Upload a captured image + sidecar JSON (multipart/form-data).
Idempotent — duplicate seq numbers are silently ignored.
**Roles:** SURVEYOR_DRONE
