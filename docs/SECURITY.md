# SECURITY.md — Security model and known gaps

## Authentication
- JWT with HS256, 8-hour expiry for field sessions.
- Role and authority tier embedded in token, validated server-side on every request.
- Token stored in Android EncryptedSharedPreferences (AES256-GCM).
- `SECRET_KEY` must be set via `IKNOS_SECRET_KEY` env var in production.
  Default value is a placeholder — DO NOT USE IN PRODUCTION.

## Role Separation
- CUSTOMER: tier 0 — can only view their own parcels and submit objections.
- SURVEYOR_DRONE: tier 1 — mission operations only. Cannot approve cases or write records.
- SURVEYOR_FIELD: tier 1 — can review cases and submit field verification. Cannot write
  OWNERSHIP or CADASTRAL_GEOMETRY updates (requires tier 2).
- SENIOR_FIELD: tier 2 — can approve all update classes.
- Role assignment is server-side only. Clients cannot self-assign roles.

## Authority Tier Enforcement
- Tier checked on every sensitive endpoint via `require_authority_tier()` dependency.
- `check_update_class_tier()` is called inside the approval endpoint to ensure
  the approval class is within the approver's tier.
- An approval for OWNERSHIP cannot be used by a SURVEYOR_FIELD.

## Parcel-Level Access Scoping
- CUSTOMER role is scoped to `owned_parcel_ids` stored in the user record.
- Customers cannot view cases or parcels they do not own.

## Known Gaps (Production Hardening Required)
- mTLS between RPi4 and backend — not implemented in MVP.
- API rate limiting — not implemented.
- Backend is designed to run inside a private network in the field.
  It should NOT be exposed to the public internet without a reverse proxy + TLS.
- `SECRET_KEY` rotation policy — not implemented.
- Audit log off-chain mirroring (for tamper-proof guarantees) — not implemented.
