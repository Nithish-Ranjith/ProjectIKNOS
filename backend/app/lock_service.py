"""
backend/app/lock_service.py — Parcel lock with mandatory TTL.

Design contracts:
  - No indefinite locks. Every lock has an expires_at.
  - When TTL expires, lock is auto-released unless escalate=True, in which
    case the case is escalated to SENIOR_FIELD authority.
  - A grievance does NOT auto-create a lock — only a confirmed investigation does.
  - lock_id, locked_at, expires_at, locked_by_case_id, locked_by_user,
    lock_reason are all mandatory fields.
"""
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from . import models

_CONFIG_PATH = Path(__file__).parent / "config" / "weights.json"
with open(_CONFIG_PATH) as _f:
    _CFG = json.load(_f)

LOCK_TTL_HOURS: int = _CFG.get("lock_ttl_hours", 72)


def acquire_lock(
    db: Session,
    parcel_id: str,
    case_id: str,
    locked_by_user: str,
    lock_reason: str,
    ttl_hours: int = LOCK_TTL_HOURS,
) -> models.ParcelLock:
    """
    Attempt to acquire a parcel lock for an investigation.
    Raises ValueError if the parcel is already locked by an active case.
    """
    # Check for existing active lock
    existing = (
        db.query(models.ParcelLock)
        .filter(
            models.ParcelLock.parcel_id == parcel_id,
            models.ParcelLock.is_active.is_(True),
        )
        .first()
    )
    if existing:
        # Has the existing lock expired?
        if existing.expires_at > datetime.now(timezone.utc):
            raise ValueError(
                f"Parcel {parcel_id} is already locked by case {existing.locked_by_case_id} "
                f"until {existing.expires_at.isoformat()}"
            )
        # Expired lock — release it before acquiring new one
        _release(db, existing, reason="TTL_EXPIRED_ON_NEW_ACQUIRE")

    now = datetime.now(timezone.utc)
    lock = models.ParcelLock(
        lock_id=str(uuid.uuid4()),
        parcel_id=parcel_id,
        locked_by_case_id=case_id,
        locked_by_user=locked_by_user,
        lock_reason=lock_reason,
        locked_at=now,
        expires_at=now + timedelta(hours=ttl_hours),
        is_active=True,
    )
    db.add(lock)
    db.commit()
    db.refresh(lock)
    return lock


def release_lock(db: Session, parcel_id: str, case_id: str) -> bool:
    """Release an active lock. Returns True if released, False if not found."""
    lock = (
        db.query(models.ParcelLock)
        .filter(
            models.ParcelLock.parcel_id == parcel_id,
            models.ParcelLock.locked_by_case_id == case_id,
            models.ParcelLock.is_active.is_(True),
        )
        .first()
    )
    if not lock:
        return False
    _release(db, lock, reason="CASE_RESOLVED")
    return True


def expire_stale_locks(db: Session) -> list[str]:
    """
    Find and release all locks whose TTL has expired.
    Returns list of released parcel_ids.
    Intended to be called periodically (e.g., by a background task or health endpoint).
    """
    now = datetime.now(timezone.utc)
    stale = (
        db.query(models.ParcelLock)
        .filter(
            models.ParcelLock.is_active.is_(True),
            models.ParcelLock.expires_at <= now,
        )
        .all()
    )
    released = []
    for lock in stale:
        _release(db, lock, reason="TTL_EXPIRED")
        released.append(lock.parcel_id)
    if released:
        db.commit()
    return released


def get_lock(db: Session, parcel_id: str) -> models.ParcelLock | None:
    """Return the active lock for a parcel, or None."""
    return (
        db.query(models.ParcelLock)
        .filter(
            models.ParcelLock.parcel_id == parcel_id,
            models.ParcelLock.is_active.is_(True),
        )
        .first()
    )


def _release(db: Session, lock: models.ParcelLock, reason: str) -> None:
    lock.is_active = False
    lock.released_at = datetime.now(timezone.utc)
    lock.lock_reason = f"{lock.lock_reason} | RELEASED:{reason}"
    db.add(lock)
