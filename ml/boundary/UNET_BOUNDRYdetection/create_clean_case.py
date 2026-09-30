import json
from datetime import datetime, timezone

with open("data/output/citizen_grievance_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

case["case_id"] = "CASE-2026-CLEAN-PASS"
case["status"] = "AWAITING_SURVEY"
case["evidence"]["satellite_evidence"]["anomaly_score"] = 0.0
case["evidence"]["spatial_evidence"] = None
case["field_verification"] = None
case["update_classification"] = None
case["record_update"] = None
case["audit"] = None
case["officer_decision"] = {
    "decision": None,
    "decided_by": None,
    "decided_at": None,
    "reason": None,
    "signature_ref": None,
}
case["parcel_lock"] = {
    "locked": True,
    "locked_at": datetime.now(timezone.utc).isoformat(),
    "locked_by_case_id": "CASE-2026-CLEAN-PASS",
    "lock_ttl_hours": 168,
    "escalated": False,
}

with open("data/output/clean_test_case.json", "w", encoding="utf-8") as f:
    json.dump(case, f, indent=2)

print("Created data/output/clean_test_case.json with anomaly_score = 0.0 and active lock.")