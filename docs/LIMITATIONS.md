# LIMITATIONS.md — Known system limitations in MVP scope

## Positioning Accuracy
- Standard consumer GNSS is used (±2.5–5m accuracy).
- All spatial discrepancy measurements carry this uncertainty.
- Boundary shifts < 5m cannot be considered conclusive without RTK or
  independent ground-truth measurement.
- The confidence formula explicitly penalizes STANDARD_GNSS vs RTK_FIX.
- This is documented as a permanent limitation of the drone platform in MVP.
- RTK-GNSS is explicitly out of MVP scope and may be added in a future phase.

## U-Net Boundary Candidates
- The U-Net model is transfer-learned from European agricultural parcel datasets
  (AI4Boundaries, Eurocrops).
- Its performance on Indian agricultural and peri-urban parcels is unknown
  until fine-tuning on Indian data is completed (BQ-04).
- All model outputs are labeled `TRANSFER_LEARNED_UNVALIDATED`.
- Boundary candidates are CANDIDATE PHYSICAL BOUNDARIES, not legal boundaries.

## Sentinel-2 Temporal Analysis
- Temporal analysis requires Sentinel-2 data from Google Earth Engine (BQ-03).
- Without GEE credentials, `instability_score` is null. The confidence formula
  treats a null score as zero contribution, not as an absence of discrepancy.
- Cloud cover can reduce the number of usable observations. Analysis quality
  is reported as HIGH / MEDIUM / LOW / INSUFFICIENT_DATA.

## No Autonomous Flight
- This system does NOT autonomously fly the drone. The pilot operates manually in LOITER mode.
- The tablet provides planning assistance and image capture monitoring only.
- No MAVLink flight commands are sent from the tablet to the drone.

## No Government Write
- The system records authenticated update intents. No actual government API write is implemented.
- The government ULPIN system integration is out of MVP scope (BQ-05).

## ODM on RPi4
- WebODM / ODM photogrammetry processing cannot run on the Raspberry Pi 4.
- A separate workstation with >= 8GB RAM is required.

## Tamper Evidence vs Tamper Proof
- The audit log is tamper-EVIDENT, not tamper-PROOF.
- SHA-256 hash chaining detects any modification of historical entries.
- It does not prevent a database administrator with direct write access from
  deleting audit log rows. For a production deployment, the audit log should
  be mirrored to an immutable off-chain store.
