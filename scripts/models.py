"""
MVP schema — deliberately scoped to what's buildable in the demo window.

NOT included (documented as roadmap, not built): hash-chained audit log,
parcel lock TTL/escalation, authority-tier gating, versioned record diffs,
mission state machine. See LIMITATIONS.md.
"""
from sqlalchemy import Column, String, Numeric, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from geoalchemy2 import Geometry
from datetime import datetime, timezone
from .database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Parcel(Base):
    __tablename__ = "parcels"

    # Internal identity is separate from ULPIN — ULPIN is nullable and only
    # populated when a real government identifier is actually available.
    parcel_id = Column(String, primary_key=True)  # internal_parcel_key
    ulpin = Column(String, nullable=True)  # real government ULPIN, nullable — never fabricated
    geom = Column(Geometry("POLYGON", srid=4326), nullable=False)
    source = Column(String, nullable=False)  # 'cadastral' | 'drone_derived'
    area_sqm = Column(Numeric, nullable=True)
    last_updated = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class RoR(Base):
    __tablename__ = "ror"

    id = Column(String, primary_key=True)
    parcel_id = Column(String, ForeignKey("parcels.parcel_id"), nullable=False)
    owner_name = Column(String, nullable=True)
    khasra_no = Column(String, nullable=True)
    area_recorded = Column(Numeric, nullable=True)
    record_date = Column(DateTime(timezone=True), nullable=True)
    # explicit "missing" representation rather than an absent row that could
    # be misread as "not checked yet"
    status = Column(String, default="present")  # 'present' | 'missing'


class Mutation(Base):
    __tablename__ = "mutation"

    id = Column(String, primary_key=True)
    parcel_id = Column(String, ForeignKey("parcels.parcel_id"), nullable=False)
    mutation_status = Column(String, nullable=False)  # 'pending' | 'approved' | 'none'
    mutation_date = Column(DateTime(timezone=True), nullable=True)


class Registration(Base):
    """
    PRD referenced `registration_id` in evidence refs but never defined a
    concrete table for it — resolving that gap here rather than silently
    inventing structure elsewhere. Kept minimal: presence/absence is the
    signal that matters for the demo, not full deed content.
    """
    __tablename__ = "registration"

    id = Column(String, primary_key=True)
    parcel_id = Column(String, ForeignKey("parcels.parcel_id"), nullable=False)
    status = Column(String, default="present")  # 'present' | 'missing'
    registration_date = Column(DateTime(timezone=True), nullable=True)
    deed_ref = Column(String, nullable=True)


class Case(Base):
    __tablename__ = "cases"

    case_id = Column(String, primary_key=True)
    parcel_id = Column(String, ForeignKey("parcels.parcel_id"), nullable=False)
    status = Column(String, default="open")  # 'open' | 'field_verification' | 'closed'
    confidence_score = Column(Numeric, nullable=False)  # 0-100
    action = Column(String, nullable=False)  # 'field_verification_required' | 'no_action'
    case_data = Column(JSONB, nullable=False)  # full case object incl. reasoning trace
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Objection(Base):
    """Citizen grievance. Deliberately does NOT write to Case or lock anything
    directly — it's a trigger that must pass through the same analysis path
    as proactive cases, per the earlier governance correction. In this MVP
    that means: stored here, and a human decides whether to open a Case."""
    __tablename__ = "objections"

    objection_id = Column(String, primary_key=True)
    parcel_id = Column(String, ForeignKey("parcels.parcel_id"), nullable=False)
    submitted_by = Column(String, nullable=False)
    text = Column(Text, nullable=True)
    evidence_photo_ref = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    reviewed = Column(Boolean, default=False)
