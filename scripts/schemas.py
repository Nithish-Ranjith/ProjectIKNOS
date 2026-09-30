from pydantic import BaseModel
from typing import Optional, Any


class ParcelOut(BaseModel):
    parcel_id: str
    ulpin: Optional[str] = None
    source: str
    area_sqm: Optional[float] = None

    class Config:
        from_attributes = True


class CaseOut(BaseModel):
    case_id: str
    parcel_id: str
    status: str
    confidence_score: float
    action: str
    case_data: Any

    class Config:
        from_attributes = True


class DecisionIn(BaseModel):
    decision: str  # 'approve' | 'reject' | 'escalate'
    decided_by: str
    reason: Optional[str] = None


class ObjectionIn(BaseModel):
    parcel_id: str
    submitted_by: str
    text: Optional[str] = None
    evidence_photo_ref: Optional[str] = None


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
