"""
backend/app/schemas.py — Pydantic models for API request/response validation.
"""
from pydantic import BaseModel
from typing import Optional, Any, List, Dict
from datetime import datetime
from .models import CaseStatus, MissionState, UpdateClass, VerificationStatus

# --- Users / Auth ---
class TokenOut(BaseModel):
    access_token: str
    token_type: str
    role: str

class LoginIn(BaseModel):
    username: str
    password: str

class UserOut(BaseModel):
    user_id: str
    username: str
    role: str
    authority_tier: int

# --- Parcels & Cases ---
class ParcelOut(BaseModel):
    parcel_id: str
    ulpin: Optional[str] = None
    source: str
    area_sqm: Optional[float] = None
    class Config:
        from_attributes = True

class CaseOut(BaseModel):
    case_id: str
    schema_version: str
    parcel_id: str
    status: CaseStatus
    confidence_score: float
    action: str
    case_data: Any
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True

# --- Decisions & Approvals ---
class DecisionIn(BaseModel):
    decision: str  # 'approve' | 'reject' | 'escalate'
    reason: Optional[str] = None

class ApprovalIn(BaseModel):
    update_class: UpdateClass
    reason: str

class RecordUpdateIn(BaseModel):
    approval_id: str
    target_record_type: str
    target_record_id: str
    changes: List[Dict[str, Any]]

# --- Objections ---
class ObjectionIn(BaseModel):
    parcel_id: str
    text: Optional[str] = None
    evidence_photo_ref: Optional[str] = None

# --- Missions ---
class ImageSidecarIn(BaseModel):
    image_id: str
    mission_id: str
    seq: int
    lat: float
    lon: float
    alt_m: float
    yaw_deg: float
    gps_fix_type: str
    timestamp_gps: str
    blur_score: float
    quality_flag: str
    camera_id: str

class MissionCreate(BaseModel):
    case_id: str
    parcel_id: str
    reflight_of_mission_id: Optional[str] = None

class MissionOut(BaseModel):
    mission_id: str
    case_id: str
    parcel_id: str
    state: MissionState
    class Config:
        from_attributes = True

class MissionStateUpdate(BaseModel):
    state: MissionState

# --- Field Verification ---
class FindingsSummary(BaseModel):
    text: str
    primary_photo_ref: Optional[str] = None
    geotag: Optional[Dict[str, float]] = None  # {"lat": float, "lon": float}
    timestamp: str

class FieldVerificationIn(BaseModel):
    observations: List[Dict[str, Any]]
    photo_refs: List[str]
    measurement_refs: List[Dict[str, Any]]
    verification_status: VerificationStatus
    findings_summary: Optional[FindingsSummary] = None
    lat: Optional[float] = None
    lon: Optional[float] = None

# --- Audit ---
class AuditOut(BaseModel):
    audit_id: str
    event_type: str
    actor_id: str
    actor_role: str
    timestamp: datetime
    data: Any
    current_hash: str
    class Config:
        from_attributes = True
