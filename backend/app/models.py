"""
backend/app/models.py — Full SQLAlchemy ORM schema for TerraTrace MVP.

Tables:
  Existing (carried forward, corrected):
    parcels, ror, mutation, registration, cases, objections

  New (Phase 1):
    users, missions, mission_images, parcel_locks,
    audit_log, parcel_versions, ror_versions,
    approvals, record_updates, field_verifications,
    discrepancy_metrics, boundary_candidates, temporal_signals

Design contracts:
  - parcel_id is internal key. ulpin is nullable external government ID.
  - No fabricated ULPIN values ever written by system code.
  - Audit log is append-only; hash chain validated by audit_service.py.
  - Record updates are typed; approval must exist before update is written.
  - Parcel lock has mandatory TTL — no indefinite locks.
  - Registration and RoR are separate tables; signals must not be collapsed.
  - STANDARD_GNSS !== RTK_FIX; positioning quality must be carried through.
"""
import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Numeric, DateTime, Text, Boolean,
    ForeignKey, Integer, Enum as SAEnum, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import JSONB
from geoalchemy2 import Geometry
from .database import Base


def utcnow():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class UserRole(str, enum.Enum):
    CUSTOMER = "CUSTOMER"
    SURVEYOR_FIELD = "SURVEYOR_FIELD"
    SURVEYOR_DRONE = "SURVEYOR_DRONE"
    SENIOR_FIELD = "SENIOR_FIELD"
    ADMIN = "ADMIN"


class AuthorityTier(int, enum.Enum):
    TIER_0 = 0   # CUSTOMER
    TIER_1 = 1   # SURVEYOR_FIELD, SURVEYOR_DRONE
    TIER_2 = 2   # SENIOR_FIELD


class MissionState(str, enum.Enum):
    DRAFT = "DRAFT"
    READY = "READY"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    ABORTED = "ABORTED"
    COMPLETED = "COMPLETED"
    QC = "QC"
    PASS = "PASS"
    RE_FLIGHT_REQUIRED = "RE_FLIGHT_REQUIRED"


class CaseStatus(str, enum.Enum):
    OPEN = "open"
    FIELD_VERIFICATION = "field_verification"
    AUTHORITY_REVIEW = "authority_review"
    CLOSED = "closed"
    REJECTED = "rejected"


class UpdateClass(str, enum.Enum):
    OWNERSHIP = "OWNERSHIP"
    CADASTRAL_GEOMETRY = "CADASTRAL_GEOMETRY"
    MUTATION = "MUTATION"
    OTHER_AUTHORIZED = "OTHER_AUTHORIZED"


class VerificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    DISPUTED = "DISPUTED"
    INCONCLUSIVE = "INCONCLUSIVE"


class MatchStatus(str, enum.Enum):
    MATCHED = "MATCHED"
    AMBIGUOUS = "AMBIGUOUS"
    UNRESOLVED = "UNRESOLVED"


# ---------------------------------------------------------------------------
# Carried-forward tables (corrected)
# ---------------------------------------------------------------------------

class Parcel(Base):
    __tablename__ = "parcels"

    # Internal identity — never the same as ULPIN.
    parcel_id = Column(String, primary_key=True)
    # Real government ULPIN, nullable. Populated only when government provides it.
    # Never auto-generated or fabricated.
    ulpin = Column(String, nullable=True, index=True)
    geom = Column(Geometry("POLYGON", srid=4326), nullable=False)
    source = Column(String, nullable=False)   # 'cadastral' | 'drone_derived'
    area_sqm = Column(Numeric, nullable=True)
    last_updated = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class RoR(Base):
    __tablename__ = "ror"

    id = Column(String, primary_key=True)
    parcel_id = Column(String, ForeignKey("parcels.parcel_id"), nullable=False, index=True)
    owner_name = Column(String, nullable=True)
    khasra_no = Column(String, nullable=True)
    area_recorded = Column(Numeric, nullable=True)
    record_date = Column(DateTime(timezone=True), nullable=True)
    # Explicit missing-representation — absent row means "not checked", status="missing"
    # means "checked and absent from records".
    status = Column(String, default="present")  # 'present' | 'missing'


class Mutation(Base):
    __tablename__ = "mutation"

    id = Column(String, primary_key=True)
    parcel_id = Column(String, ForeignKey("parcels.parcel_id"), nullable=False, index=True)
    mutation_status = Column(String, nullable=False)  # 'pending' | 'approved' | 'none'
    mutation_date = Column(DateTime(timezone=True), nullable=True)


class Registration(Base):
    """
    Registration evidence — separate from RoR because these are independent
    signals. RoR missing and Registration missing are NOT the same fact.
    Collapsing them would lose information the scoring model needs.
    """
    __tablename__ = "registration"

    id = Column(String, primary_key=True)
    parcel_id = Column(String, ForeignKey("parcels.parcel_id"), nullable=False, index=True)
    status = Column(String, default="present")  # 'present' | 'missing'
    registration_date = Column(DateTime(timezone=True), nullable=True)
    deed_ref = Column(String, nullable=True)


class Case(Base):
    """
    Case is the central coordination object. case_data is JSONB holding the
    full evidence bundle, reasoning trace, and decision history. The relational
    columns (status, confidence_score, action) exist so queries can filter/sort
    without parsing JSONB. Never update case_data destructively — append to
    audit_log instead and record the delta in record_updates.
    """
    __tablename__ = "cases"

    case_id = Column(String, primary_key=True)
    schema_version = Column(String, default="1.0", nullable=False)
    parcel_id = Column(String, ForeignKey("parcels.parcel_id"), nullable=False, index=True)
    status = Column(SAEnum(CaseStatus), default=CaseStatus.OPEN, nullable=False)
    confidence_score = Column(Numeric, nullable=False)   # 0-100
    action = Column(String, nullable=False)              # 'field_verification_required' | 'no_action'
    case_data = Column(JSONB, nullable=False)            # full evidence bundle + reasoning trace
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Objection(Base):
    """
    Citizen grievance. Storing the objection here does NOT create a case or
    lock anything. A human (SURVEYOR_FIELD) reviews objections and decides
    whether to open a case through the same analysis pipeline as proactive
    cases. That gate is intentional and cannot be bypassed.
    """
    __tablename__ = "objections"

    objection_id = Column(String, primary_key=True)
    parcel_id = Column(String, ForeignKey("parcels.parcel_id"), nullable=False, index=True)
    submitted_by = Column(String, nullable=False)
    text = Column(Text, nullable=True)
    evidence_photo_refs = Column(JSONB, default=list)   # list of storage refs
    created_at = Column(DateTime(timezone=True), default=utcnow)
    reviewed = Column(Boolean, default=False)
    reviewed_by = Column(String, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    # If review results in a case, link it here — NOT created automatically.
    resulting_case_id = Column(String, ForeignKey("cases.case_id"), nullable=True)


# ---------------------------------------------------------------------------
# Users and authentication
# ---------------------------------------------------------------------------

class User(Base):
    """
    Users. Role is assigned server-side only — the client NEVER assigns its
    own role. The server is the authority.
    """
    __tablename__ = "users"

    user_id = Column(String, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(SAEnum(UserRole), nullable=False)
    authority_tier = Column(Integer, nullable=False, default=0)
    # SURVEYOR_FIELD/SENIOR_FIELD: government ID ref
    govt_id_ref = Column(String, nullable=True)
    # SURVEYOR_DRONE: DGCA credential, stored as opaque string pending format confirmation
    dgca_credential = Column(String, nullable=True)
    # CUSTOMER: phone for OTP
    phone = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    # Parcels this customer owns (for access scoping) — stored as JSON array of parcel_ids
    owned_parcel_ids = Column(JSONB, default=list)


# ---------------------------------------------------------------------------
# Mission lifecycle
# ---------------------------------------------------------------------------

class Mission(Base):
    """
    A survey mission. One Case can generate multiple Missions (initial +
    targeted re-flights). state follows the explicit state machine in
    mission_service.py — no ad-hoc boolean flags.
    """
    __tablename__ = "missions"

    mission_id = Column(String, primary_key=True)
    case_id = Column(String, ForeignKey("cases.case_id"), nullable=False, index=True)
    parcel_id = Column(String, ForeignKey("parcels.parcel_id"), nullable=False)
    state = Column(SAEnum(MissionState), default=MissionState.DRAFT, nullable=False)

    # AOI and planning
    aoi_geojson = Column(JSONB, nullable=True)           # accepted polygon
    planned_route_geojson = Column(JSONB, nullable=True) # grid lines
    target_altitude_m = Column(Numeric, nullable=True)
    camera_profile_id = Column(String, nullable=True)    # e.g. 'picam_v2_01'
    forward_overlap_pct = Column(Numeric, default=80)
    side_overlap_pct = Column(Numeric, default=70)
    capture_spacing_m = Column(Numeric, nullable=True)   # computed from FOV + altitude + overlap

    # Re-flight linkage
    reflight_of_mission_id = Column(String, ForeignKey("missions.mission_id"), nullable=True)
    reflight_sector = Column(String, nullable=True)      # e.g. 'NE-03'

    # Execution metadata
    created_by = Column(String, ForeignKey("users.user_id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # QC result (set when state transitions to PASS or RE_FLIGHT_REQUIRED)
    qc_result = Column(JSONB, nullable=True)

    # Photogrammetry artifacts (populated after ODM completes)
    orthomosaic_uri = Column(String, nullable=True)
    dsm_uri = Column(String, nullable=True)
    point_cloud_uri = Column(String, nullable=True)


class MissionImage(Base):
    """
    Relational record for each image acquired during a mission. The actual
    image.jpg and image.json sidecar live on the filesystem (or object store);
    this row links to them and holds the indexed fields for querying.
    """
    __tablename__ = "mission_images"
    __table_args__ = (
        # Idempotency contract: same mission + seq cannot create two rows.
        UniqueConstraint("mission_id", "seq", name="uq_mission_image_seq"),
    )

    image_id = Column(String, primary_key=True)
    mission_id = Column(String, ForeignKey("missions.mission_id"), nullable=False, index=True)
    seq = Column(Integer, nullable=False)
    lat = Column(Numeric, nullable=True)
    lon = Column(Numeric, nullable=True)
    alt_m = Column(Numeric, nullable=True)
    yaw_deg = Column(Numeric, nullable=True)
    gps_fix_type = Column(String, nullable=True)        # '3D_FIX' | 'NO_FIX' | etc.
    timestamp_gps = Column(DateTime(timezone=True), nullable=True)
    blur_score = Column(Numeric, nullable=True)
    quality_flag = Column(String, nullable=True)        # 'PASS' | 'BLUR'
    camera_id = Column(String, nullable=True)
    # Storage refs
    image_path = Column(String, nullable=True)          # local path or object store URI
    sidecar_path = Column(String, nullable=True)
    captured_at = Column(DateTime(timezone=True), default=utcnow)


# ---------------------------------------------------------------------------
# Parcel lock
# ---------------------------------------------------------------------------

class ParcelLock(Base):
    """
    Prevents concurrent investigations on the same parcel.
    MANDATORY TTL — no indefinite locks. When expires_at is reached,
    lock_service.py either releases the lock or escalates the case.
    """
    __tablename__ = "parcel_locks"

    lock_id = Column(String, primary_key=True)
    parcel_id = Column(String, ForeignKey("parcels.parcel_id"), nullable=False, unique=True)
    locked_by_case_id = Column(String, ForeignKey("cases.case_id"), nullable=False)
    locked_by_user = Column(String, ForeignKey("users.user_id"), nullable=True)
    lock_reason = Column(String, nullable=False)
    locked_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)   # must be set; no null
    released_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)


# ---------------------------------------------------------------------------
# Audit log (hash-chained, append-only)
# ---------------------------------------------------------------------------

class AuditLog(Base):
    """
    Tamper-evident append-only audit history.

    Hash contract:
      payload = canonical JSON of {case_id, event_type, actor_id, actor_role,
                                   timestamp, data, previous_hash}
      current_hash = SHA-256(previous_hash + payload)

    The genesis entry has previous_hash = "GENESIS".

    "Tamper-evident" means modifying any historical entry causes hash chain
    verification to fail from that point forward. Do NOT claim "tamper-proof."
    """
    __tablename__ = "audit_log"

    audit_id = Column(String, primary_key=True)
    case_id = Column(String, ForeignKey("cases.case_id"), nullable=False, index=True)
    event_type = Column(String, nullable=False)   # 'CASE_OPENED' | 'DECISION' | 'APPROVED' | 'RECORD_UPDATED' | ...
    actor_id = Column(String, nullable=True)      # user_id or 'SYSTEM'
    actor_role = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    data = Column(JSONB, nullable=False)           # event-specific payload
    previous_hash = Column(String, nullable=False) # hash of previous entry, or "GENESIS"
    current_hash = Column(String, nullable=False)  # SHA-256(previous_hash + canonicalized payload)
    seq = Column(Integer, nullable=False)          # monotonically increasing within a case


# ---------------------------------------------------------------------------
# Versioned records (append-only)
# ---------------------------------------------------------------------------

class ParcelVersion(Base):
    """
    Append-only version history for parcel geometry. Never overwrite — always
    INSERT a new version row. The parcel with the highest version_no is current.
    """
    __tablename__ = "parcel_versions"

    version_id = Column(String, primary_key=True)
    parcel_id = Column(String, ForeignKey("parcels.parcel_id"), nullable=False, index=True)
    version_no = Column(Integer, nullable=False)
    geom = Column(Geometry("POLYGON", srid=4326), nullable=False)
    source = Column(String, nullable=False)
    area_sqm = Column(Numeric, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    created_by_case_id = Column(String, ForeignKey("cases.case_id"), nullable=True)
    created_by_approval_id = Column(String, nullable=True)


class RoRVersion(Base):
    """
    Append-only version history for RoR records. Same principle as ParcelVersion.
    """
    __tablename__ = "ror_versions"

    version_id = Column(String, primary_key=True)
    ror_id = Column(String, ForeignKey("ror.id"), nullable=False, index=True)
    parcel_id = Column(String, ForeignKey("parcels.parcel_id"), nullable=False)
    version_no = Column(Integer, nullable=False)
    owner_name = Column(String, nullable=True)
    khasra_no = Column(String, nullable=True)
    area_recorded = Column(Numeric, nullable=True)
    record_date = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    created_by_case_id = Column(String, ForeignKey("cases.case_id"), nullable=True)
    created_by_approval_id = Column(String, nullable=True)


# ---------------------------------------------------------------------------
# Approval gate (must exist BEFORE any record update)
# ---------------------------------------------------------------------------

class Approval(Base):
    """
    Authenticated authorization record. MUST be created and referenced before
    any record_update row can be written. Attempting to write a record_update
    without a valid approval_id is rejected by the API layer.

    Correct order:
      Officer Review → Authenticated Approval → Record Update → Versioned Record
                                                               → Audit Entry
    """
    __tablename__ = "approvals"

    approval_id = Column(String, primary_key=True)
    case_id = Column(String, ForeignKey("cases.case_id"), nullable=False, index=True)
    approved_by = Column(String, ForeignKey("users.user_id"), nullable=False)
    approver_role = Column(SAEnum(UserRole), nullable=False)
    approver_tier = Column(Integer, nullable=False)   # snapshot of tier at time of approval
    approved_at = Column(DateTime(timezone=True), default=utcnow)
    # The update class this approval is valid for — cannot approve CADASTRAL_GEOMETRY
    # and then use the approval_id to push an OWNERSHIP update.
    update_class = Column(SAEnum(UpdateClass), nullable=False)
    reason = Column(Text, nullable=True)
    used = Column(Boolean, default=False)   # consumed when record_update references it


# ---------------------------------------------------------------------------
# Typed record updates
# ---------------------------------------------------------------------------

class RecordUpdate(Base):
    """
    A structured, typed record update. What changed, from where to where, who
    authorized it, and when. All these fields must be recoverable.

    update_class determines the minimum authority tier required.
    approval_id must reference an unused Approval of the same update_class.
    """
    __tablename__ = "record_updates"

    update_id = Column(String, primary_key=True)
    case_id = Column(String, ForeignKey("cases.case_id"), nullable=False, index=True)
    approval_id = Column(String, ForeignKey("approvals.approval_id"), nullable=False, unique=True)
    update_class = Column(SAEnum(UpdateClass), nullable=False)
    target_record_type = Column(String, nullable=False)  # 'parcel' | 'ror' | 'mutation'
    target_record_id = Column(String, nullable=False)
    changes = Column(JSONB, nullable=False)              # list of {field, old_value_ref, new_value_ref}
    authorized_by = Column(String, ForeignKey("users.user_id"), nullable=False)
    applied_at = Column(DateTime(timezone=True), default=utcnow)
    resulting_version_id = Column(String, nullable=True)  # parcel_versions or ror_versions ID


# ---------------------------------------------------------------------------
# Field verification (structured evidence)
# ---------------------------------------------------------------------------

class FieldVerification(Base):
    """
    Structured field evidence from an authorized SURVEYOR_FIELD.
    Free-text summary is permitted as an explanatory field but cannot be the
    sole evidence representation. Structured fields (photo_refs, measurement_refs,
    observations, verification_status) are required.
    """
    __tablename__ = "field_verifications"

    verification_id = Column(String, primary_key=True)
    case_id = Column(String, ForeignKey("cases.case_id"), nullable=False, index=True)
    surveyor_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), default=utcnow)
    # Location where verification was performed
    location_lat = Column(Numeric, nullable=True)
    location_lon = Column(Numeric, nullable=True)
    # Structured evidence
    observations = Column(JSONB, nullable=False, default=list)  # list of {type, description, value}
    photo_refs = Column(JSONB, nullable=False, default=list)    # list of storage refs
    measurement_refs = Column(JSONB, nullable=False, default=list)  # list of {type, value, unit}
    # Outcome
    findings_summary = Column(Text, nullable=True)              # explanatory, not sole evidence
    verification_status = Column(SAEnum(VerificationStatus), nullable=False)


# ---------------------------------------------------------------------------
# Discrepancy metrics (deterministic geometry output)
# ---------------------------------------------------------------------------

class DiscrepancyMetrics(Base):
    """
    PostGIS-derived spatial comparison between drone candidate boundary and
    cadastral boundary. Scale-normalized — a 2m shift on a 100m² parcel and
    a 2m shift on a 50,000m² parcel are treated differently.

    No global fixed IoU >= 0.85 threshold. Interpretation accounts for parcel
    scale, positional uncertainty, and source quality.
    """
    __tablename__ = "discrepancy_metrics"

    metrics_id = Column(String, primary_key=True)
    case_id = Column(String, ForeignKey("cases.case_id"), nullable=False, index=True)
    mission_id = Column(String, ForeignKey("missions.mission_id"), nullable=True)
    area_diff_pct = Column(Numeric, nullable=True)
    boundary_shift_m = Column(Numeric, nullable=True)         # Hausdorff distance
    iou = Column(Numeric, nullable=True)                      # for reference only, not sole criterion
    intersection_area_sqm = Column(Numeric, nullable=True)
    difference_area_sqm = Column(Numeric, nullable=True)
    topology_valid = Column(Boolean, nullable=True)
    positioning_quality = Column(String, default="STANDARD_GNSS")  # never confuse with RTK_FIX
    computed_at = Column(DateTime(timezone=True), default=utcnow)
    raw_output = Column(JSONB, nullable=True)                 # full PostGIS output for audit


# ---------------------------------------------------------------------------
# Boundary candidates (U-Net output)
# ---------------------------------------------------------------------------

class BoundaryCandidate(Base):
    """
    Probability-scored candidate boundary from U-Net inference.
    Explicitly labeled as a CANDIDATE physical boundary, never a legal boundary.
    Transfer-learned from AI4Boundaries/Eurocrops; fine-tuned on Indian pilot set.
    """
    __tablename__ = "boundary_candidates"

    candidate_id = Column(String, primary_key=True)
    mission_id = Column(String, ForeignKey("missions.mission_id"), nullable=False, index=True)
    case_id = Column(String, ForeignKey("cases.case_id"), nullable=True)
    # GeoJSON geometry stored as JSONB; also available via geom for PostGIS ops
    boundary_geojson = Column(JSONB, nullable=False)
    geom = Column(Geometry("POLYGON", srid=4326), nullable=True)  # populated on ingest
    confidence_score = Column(Numeric, nullable=True)   # model output probability
    model_version = Column(String, nullable=True)
    dataset_label = Column(String, nullable=False, default="TRANSFER_LEARNED_UNVALIDATED")
    computed_at = Column(DateTime(timezone=True), default=utcnow)


# ---------------------------------------------------------------------------
# Temporal signals (STL + PELT on Sentinel-2)
# ---------------------------------------------------------------------------

class TemporalSignal(Base):
    """
    Temporal anomaly result from STL decomposition + PELT changepoint detection
    on Sentinel-2 NDVI time series. This identifies a temporal signal, NOT
    a legal verdict. instability_score > 0 means the time series shows
    deviation; it does NOT mean 'illegal partition detected'.
    """
    __tablename__ = "temporal_signals"

    signal_id = Column(String, primary_key=True)
    parcel_id = Column(String, ForeignKey("parcels.parcel_id"), nullable=False, index=True)
    instability_score = Column(Numeric, nullable=True)   # 0.0 – 1.0
    onset_year = Column(Integer, nullable=True)
    analysis_quality = Column(String, nullable=True)     # 'HIGH' | 'MEDIUM' | 'LOW' | 'INSUFFICIENT_DATA'
    data_source = Column(String, default="REAL_SENTINEL2_GEE")
    n_observations = Column(Integer, nullable=True)
    raw_changepoints = Column(JSONB, nullable=True)
    computed_at = Column(DateTime(timezone=True), default=utcnow)
    gee_project = Column(String, nullable=True)          # which GEE project was used
