"""
backend/app/mission_service.py — Mission lifecycle state machine.

Design contracts:
  - Explicit states (DRAFT -> READY -> ACTIVE -> PAUSED -> COMPLETED -> QC -> PASS/RE_FLIGHT_REQUIRED).
  - Invalid transitions are rejected.
  - QC is evaluated post-flight (mocked for now until QC engine is wired).
  - Mission completions log to the audit chain.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from . import models, audit_service


class InvalidTransitionError(Exception):
    pass


def create_mission(
    db: Session,
    case_id: str,
    parcel_id: str,
    created_by: str,
    reflight_of_mission_id: Optional[str] = None
) -> models.Mission:
    mission = models.Mission(
        mission_id=f"M{datetime.now().strftime('%Y%m')}-{uuid.uuid4().hex[:6]}",
        case_id=case_id,
        parcel_id=parcel_id,
        created_by=created_by,
        reflight_of_mission_id=reflight_of_mission_id
    )
    db.add(mission)
    db.commit()
    db.refresh(mission)
    return mission


def transition_state(
    db: Session,
    mission_id: str,
    new_state: models.MissionState,
    actor_id: str = "SYSTEM",
    actor_role: str = "SYSTEM"
) -> models.Mission:
    mission = db.get(models.Mission, mission_id)
    if not mission:
        raise ValueError(f"Mission {mission_id} not found")

    curr = mission.state

    # Define valid transitions
    valid = {
        models.MissionState.DRAFT: [models.MissionState.READY, models.MissionState.ABORTED],
        models.MissionState.READY: [models.MissionState.ACTIVE, models.MissionState.ABORTED, models.MissionState.DRAFT],
        models.MissionState.ACTIVE: [models.MissionState.PAUSED, models.MissionState.COMPLETED, models.MissionState.ABORTED],
        models.MissionState.PAUSED: [models.MissionState.ACTIVE, models.MissionState.ABORTED],
        models.MissionState.ABORTED: [],
        models.MissionState.COMPLETED: [models.MissionState.QC],
        models.MissionState.QC: [models.MissionState.PASS, models.MissionState.RE_FLIGHT_REQUIRED],
        models.MissionState.PASS: [],
        models.MissionState.RE_FLIGHT_REQUIRED: []
    }

    if new_state not in valid.get(curr, []):
        raise InvalidTransitionError(f"Cannot transition from {curr} to {new_state}")

    now = datetime.now(timezone.utc)
    mission.state = new_state

    if new_state == models.MissionState.ACTIVE and not mission.started_at:
        mission.started_at = now
    elif new_state == models.MissionState.COMPLETED:
        mission.completed_at = now

    db.add(mission)

    # Log completion/QC results to audit chain
    if new_state == models.MissionState.COMPLETED:
        audit_service.append_event(
            db, mission.case_id, audit_service.EVENT_MISSION_COMPLETED,
            data={"mission_id": mission_id, "status": new_state.value},
            actor_id=actor_id, actor_role=actor_role
        )
    
    # In a real app, transition to QC might automatically trigger QC engine.
    
    db.commit()
    db.refresh(mission)
    return mission
