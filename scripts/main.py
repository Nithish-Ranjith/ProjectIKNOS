"""
IKNOS MVP backend.

Deliberately excluded from this file (see LIMITATIONS.md): authentication/
role enforcement, hash-chained audit log, parcel lock TTL, authority-tier
gating, versioned record diffs, actual RoR/cadastral record mutation on
approval. Decisions are recorded; the destructive "write to the government
record" step is out of scope for the demo and is stated as such rather than
faked.
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select

from .database import get_db, engine, Base
from . import models, schemas
from .confidence import compute_confidence

app = FastAPI(title="IKNOS MVP API")

# Configure CORS for dev and deployed origins
origins = [
    "http://localhost:5173", # Vite default dev server
    "http://localhost:3000",
    # Add production URL here via env var later
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path(__file__).parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


@app.get("/parcels/{parcel_id}", response_model=schemas.ParcelOut)
def get_parcel(parcel_id: str, db: Session = Depends(get_db)):
    parcel = db.get(models.Parcel, parcel_id)
    if not parcel:
        raise HTTPException(404, "parcel not found")
    return parcel


@app.get("/cases", response_model=list[schemas.CaseOut])
def list_cases(
    status: Optional[str] = None,
    min_confidence: Optional[float] = None,
    db: Session = Depends(get_db),
):
    stmt = select(models.Case).order_by(models.Case.confidence_score.desc())
    if status:
        stmt = stmt.where(models.Case.status == status)
    if min_confidence is not None:
        stmt = stmt.where(models.Case.confidence_score >= min_confidence)
    return db.execute(stmt).scalars().all()


@app.get("/cases/{case_id}", response_model=schemas.CaseOut)
def get_case(case_id: str, db: Session = Depends(get_db)):
    case = db.get(models.Case, case_id)
    if not case:
        raise HTTPException(404, "case not found")
    return case


@app.post("/cases/{case_id}/decision")
def decide_case(case_id: str, body: schemas.DecisionIn, db: Session = Depends(get_db)):
    case = db.get(models.Case, case_id)
    if not case:
        raise HTTPException(404, "case not found")

    if body.decision not in ("approve", "reject", "escalate"):
        raise HTTPException(400, "decision must be approve | reject | escalate")

    case.status = "closed" if body.decision in ("approve", "reject") else "field_verification"
    case.case_data["officer_decision"] = {
        "decision": body.decision,
        "decided_by": body.decided_by,
        "decided_at": datetime.now(timezone.utc).isoformat(),
        "reason": body.reason,
    }
    # NOTE: this deliberately stops here. It does NOT write to ror/mutation/
    # parcel tables. Actually mutating the government record on approval is
    # explicitly out of MVP scope — flagging rather than faking it.
    db.commit()
    db.refresh(case)
    return {"case_id": case_id, "status": case.status, "decision_recorded": body.decision}


@app.post("/objections")
def submit_objection(body: schemas.ObjectionIn, db: Session = Depends(get_db)):
    parcel = db.get(models.Parcel, body.parcel_id)
    if not parcel:
        raise HTTPException(404, "parcel not found")

    objection = models.Objection(
        objection_id=str(uuid.uuid4()),
        parcel_id=body.parcel_id,
        submitted_by=body.submitted_by,
        text=body.text,
        evidence_photo_ref=body.evidence_photo_ref,
    )
    db.add(objection)
    db.commit()
    # Deliberately does NOT create a Case or lock anything here. A grievance
    # is a trigger, not proof — a human reviews `objections` and decides
    # whether to open a case through the same analysis path as proactive
    # cases. That review step is manual in this MVP, not automated.
    return {"objection_id": objection.objection_id, "status": "submitted_pending_review"}


@app.post("/missions/{mission_id}/images")
async def upload_mission_image(
    mission_id: str,
    sidecar: str = Form(...),  # JSON string matching ImageSidecarIn schema
    file: UploadFile = File(...),
):
    try:
        meta = schemas.ImageSidecarIn.model_validate_json(sidecar)
    except Exception as e:
        raise HTTPException(400, f"invalid sidecar JSON: {e}")

    if meta.mission_id != mission_id:
        raise HTTPException(400, "mission_id in path and sidecar must match")

    mission_dir = UPLOAD_DIR / mission_id
    mission_dir.mkdir(exist_ok=True)

    image_path = mission_dir / f"{meta.image_id}.jpg"
    sidecar_path = mission_dir / f"{meta.image_id}.json"

    contents = await file.read()
    image_path.write_bytes(contents)
    sidecar_path.write_text(meta.model_dump_json(indent=2))

    return {"image_id": meta.image_id, "stored": True, "quality_flag": meta.quality_flag}


@app.post("/cases/{case_id}/recompute")
def recompute_confidence(
    case_id: str,
    area_diff_pct: float,
    boundary_shift_m: float,
    instability_score: Optional[float] = None,
    db: Session = Depends(get_db),
):
    """
    Manual trigger to (re)run the deterministic confidence formula against
    a case's parcel and persist the result + reasoning trace. Exists so the
    ML teammate's Sentinel-2 output can be wired in without touching the
    scoring math itself.
    """
    case = db.get(models.Case, case_id)
    if not case:
        raise HTTPException(404, "case not found")
    parcel = db.get(models.Parcel, case.parcel_id)
    ror = db.execute(
        select(models.RoR).where(models.RoR.parcel_id == case.parcel_id)
    ).scalars().first()
    mutation = db.execute(
        select(models.Mutation).where(models.Mutation.parcel_id == case.parcel_id)
    ).scalars().first()

    result = compute_confidence(
        area_diff_pct=area_diff_pct,
        boundary_shift_m=boundary_shift_m,
        parcel_area_sqm=float(parcel.area_sqm or 1.0),
        registration_status="missing",  # wire to Registration table lookup as needed
        mutation_status=mutation.mutation_status if mutation else "none",
        instability_score=instability_score,
    )

    case.confidence_score = result["confidence_score"]
    case.action = result["action"]
    case.case_data["explanation"] = {"reasoning_trace": result["reasoning_trace"]}
    case.case_data["evidence"] = case.case_data.get("evidence", {})
    case.case_data["evidence"]["spatial_evidence"] = {
        "area_diff_pct": area_diff_pct,
        "boundary_shift_m": boundary_shift_m,
        "positioning_quality": result["positioning_quality"],
    }
    db.commit()
    return {"case_id": case_id, **result}
