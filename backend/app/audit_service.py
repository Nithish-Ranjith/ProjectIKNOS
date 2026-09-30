"""
backend/app/audit_service.py — Hash-chained, tamper-evident audit log.

Hash contract (canonical):
  payload = JSON.dumps({
      "audit_id": ..., "case_id": ..., "event_type": ...,
      "actor_id": ..., "actor_role": ...,
      "timestamp": ISO8601,
      "data": ...,
      "previous_hash": ...,
      "seq": ...,
  }, sort_keys=True, separators=(',', ':'))

  current_hash = SHA-256(payload.encode('utf-8')).hexdigest()

The genesis entry for a case has previous_hash = "GENESIS".

"Tamper-evident" means modifying any historical entry causes hash chain
verification to fail from that point forward. The system does NOT claim
cryptographic tamper-proof guarantees beyond this append-only chain.
"""
import hashlib
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from . import models


def _canonicalize(payload: dict) -> str:
    """Stable canonical JSON — sorted keys, no whitespace."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def append_event(
    db: Session,
    case_id: str,
    event_type: str,
    data: dict,
    actor_id: str = "SYSTEM",
    actor_role: str = "SYSTEM",
) -> models.AuditLog:
    """
    Append a new entry to the audit chain for a case.
    Retrieves the current tip hash, computes next hash, inserts the new entry.
    All in one call — caller must commit the surrounding transaction.
    """
    # Find the current chain tip for this case
    tip = (
        db.query(models.AuditLog)
        .filter(models.AuditLog.case_id == case_id)
        .order_by(models.AuditLog.seq.desc())
        .first()
    )
    previous_hash = tip.current_hash if tip else "GENESIS"
    seq = (tip.seq + 1) if tip else 0
    audit_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    canonical_payload = _canonicalize({
        "audit_id": audit_id,
        "case_id": case_id,
        "event_type": event_type,
        "actor_id": actor_id,
        "actor_role": actor_role,
        "timestamp": timestamp,
        "data": data,
        "previous_hash": previous_hash,
        "seq": seq,
    })
    current_hash = _sha256(canonical_payload)

    entry = models.AuditLog(
        audit_id=audit_id,
        case_id=case_id,
        event_type=event_type,
        actor_id=actor_id,
        actor_role=actor_role,
        timestamp=datetime.fromisoformat(timestamp),
        data=data,
        previous_hash=previous_hash,
        current_hash=current_hash,
        seq=seq,
    )
    db.add(entry)
    return entry


def verify_chain(db: Session, case_id: str) -> dict:
    """
    Verify the hash chain for a given case.
    Returns {"valid": True/False, "first_broken_seq": int|None, "entries_checked": int}.
    A broken chain means at least one historical entry was modified.
    """
    entries = (
        db.query(models.AuditLog)
        .filter(models.AuditLog.case_id == case_id)
        .order_by(models.AuditLog.seq.asc())
        .all()
    )
    if not entries:
        return {"valid": True, "first_broken_seq": None, "entries_checked": 0}

    prev_hash = "GENESIS"
    for entry in entries:
        canonical_payload = _canonicalize({
            "audit_id": entry.audit_id,
            "case_id": entry.case_id,
            "event_type": entry.event_type,
            "actor_id": entry.actor_id,
            "actor_role": entry.actor_role,
            "timestamp": (
                entry.timestamp.isoformat()
                if isinstance(entry.timestamp, datetime)
                else str(entry.timestamp)
            ),
            "data": entry.data,
            "previous_hash": entry.previous_hash,
            "seq": entry.seq,
        })
        expected_hash = _sha256(canonical_payload)

        if entry.previous_hash != prev_hash or entry.current_hash != expected_hash:
            return {
                "valid": False,
                "first_broken_seq": entry.seq,
                "entries_checked": entry.seq,
            }
        prev_hash = entry.current_hash

    return {"valid": True, "first_broken_seq": None, "entries_checked": len(entries)}


# Canonical event type constants — use these rather than raw strings
EVENT_CASE_OPENED = "CASE_OPENED"
EVENT_LOCK_ACQUIRED = "LOCK_ACQUIRED"
EVENT_LOCK_RELEASED = "LOCK_RELEASED"
EVENT_FIELD_VERIFICATION = "FIELD_VERIFICATION"
EVENT_DECISION = "DECISION"
EVENT_APPROVAL = "APPROVAL"
EVENT_RECORD_UPDATE = "RECORD_UPDATE"
EVENT_CASE_CLOSED = "CASE_CLOSED"
EVENT_CASE_REJECTED = "CASE_REJECTED"
EVENT_REFLIGHT_REQUESTED = "REFLIGHT_REQUESTED"
EVENT_MISSION_COMPLETED = "MISSION_COMPLETED"
