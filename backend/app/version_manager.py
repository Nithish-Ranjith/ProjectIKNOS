"""
backend/app/version_manager.py — Append-only versioned records.

Design contracts:
  - Never overwrite a previous state. Always INSERT a new version row.
  - Each version is attributable to: source evidence, authorized decision,
    timestamp, and case.
  - The version with the highest version_no is the current state.
  - version_id, parcel_id, version_no, created_by_case_id are all required.
"""
import uuid
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from . import models


def _next_version_no(db: Session, table_cls, id_col, entity_id: str) -> int:
    """Get the next version number for an entity."""
    current_max = db.execute(
        select(func.max(id_col)).where(id_col == entity_id)
    ).scalar()
    # Note: id_col here is the FK column e.g. ParcelVersion.parcel_id
    result = db.execute(
        select(func.max(table_cls.version_no)).where(id_col == entity_id)
    ).scalar()
    return (result or 0) + 1


def create_parcel_version(
    db: Session,
    parcel: models.Parcel,
    case_id: str,
    approval_id: str,
) -> models.ParcelVersion:
    """
    Snapshot the current parcel geometry into a new version row.
    Call this AFTER the Approval has been recorded and BEFORE updating parcels.
    """
    version_no = db.execute(
        select(func.max(models.ParcelVersion.version_no)).where(
            models.ParcelVersion.parcel_id == parcel.parcel_id
        )
    ).scalar() or 0

    version = models.ParcelVersion(
        version_id=str(uuid.uuid4()),
        parcel_id=parcel.parcel_id,
        version_no=version_no + 1,
        geom=parcel.geom,
        source=parcel.source,
        area_sqm=parcel.area_sqm,
        created_by_case_id=case_id,
        created_by_approval_id=approval_id,
    )
    db.add(version)
    return version


def create_ror_version(
    db: Session,
    ror: models.RoR,
    case_id: str,
    approval_id: str,
) -> models.RoRVersion:
    """Snapshot the current RoR record into a new version row."""
    version_no = db.execute(
        select(func.max(models.RoRVersion.version_no)).where(
            models.RoRVersion.ror_id == ror.id
        )
    ).scalar() or 0

    version = models.RoRVersion(
        version_id=str(uuid.uuid4()),
        ror_id=ror.id,
        parcel_id=ror.parcel_id,
        version_no=version_no + 1,
        owner_name=ror.owner_name,
        khasra_no=ror.khasra_no,
        area_recorded=ror.area_recorded,
        record_date=ror.record_date,
        status=ror.status,
        created_by_case_id=case_id,
        created_by_approval_id=approval_id,
    )
    db.add(version)
    return version


def get_parcel_history(db: Session, parcel_id: str) -> list[models.ParcelVersion]:
    """Return all versions of a parcel in chronological order."""
    return (
        db.query(models.ParcelVersion)
        .filter(models.ParcelVersion.parcel_id == parcel_id)
        .order_by(models.ParcelVersion.version_no.asc())
        .all()
    )


def get_ror_history(db: Session, ror_id: str) -> list[models.RoRVersion]:
    """Return all versions of a RoR record in chronological order."""
    return (
        db.query(models.RoRVersion)
        .filter(models.RoRVersion.ror_id == ror_id)
        .order_by(models.RoRVersion.version_no.asc())
        .all()
    )
