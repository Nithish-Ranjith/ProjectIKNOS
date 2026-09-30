"""
backend/tests/test_mission_lifecycle.py — Mission state machine tests.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import pytest
from unittest.mock import MagicMock, patch
from backend.app.models import Mission, MissionState, Case
from backend.app.mission_service import transition_state, InvalidTransitionError


def make_mock_db(mission):
    db = MagicMock()
    db.get = MagicMock(side_effect=lambda cls, id: mission if cls == Mission else None)
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock(side_effect=lambda obj: None)
    mock_query = MagicMock()
    mock_query.filter.return_value.order_by.return_value.first.return_value = None
    db.query = MagicMock(return_value=mock_query)
    return db


def make_mission(state: MissionState) -> Mission:
    m = Mission()
    m.mission_id = "M_001"
    m.case_id = "C_001"
    m.state = state
    m.started_at = None
    m.completed_at = None
    return m


class TestMissionStateTransitions:
    def test_draft_to_ready(self):
        m = make_mission(MissionState.DRAFT)
        db = make_mock_db(m)
        result = transition_state(db, "M_001", MissionState.READY)
        assert result.state == MissionState.READY

    def test_ready_to_active(self):
        m = make_mission(MissionState.READY)
        db = make_mock_db(m)
        result = transition_state(db, "M_001", MissionState.ACTIVE)
        assert result.state == MissionState.ACTIVE
        assert result.started_at is not None

    def test_active_to_completed(self):
        m = make_mission(MissionState.ACTIVE)
        db = make_mock_db(m)
        result = transition_state(db, "M_001", MissionState.COMPLETED)
        assert result.state == MissionState.COMPLETED
        assert result.completed_at is not None

    def test_completed_to_qc(self):
        m = make_mission(MissionState.COMPLETED)
        db = make_mock_db(m)
        result = transition_state(db, "M_001", MissionState.QC)
        assert result.state == MissionState.QC

    def test_qc_to_pass(self):
        m = make_mission(MissionState.QC)
        db = make_mock_db(m)
        result = transition_state(db, "M_001", MissionState.PASS)
        assert result.state == MissionState.PASS

    def test_qc_to_reflight(self):
        m = make_mission(MissionState.QC)
        db = make_mock_db(m)
        result = transition_state(db, "M_001", MissionState.RE_FLIGHT_REQUIRED)
        assert result.state == MissionState.RE_FLIGHT_REQUIRED

    def test_invalid_transition_raises(self):
        m = make_mission(MissionState.PASS)
        db = make_mock_db(m)
        with pytest.raises(InvalidTransitionError):
            transition_state(db, "M_001", MissionState.ACTIVE)

    def test_aborted_is_terminal(self):
        m = make_mission(MissionState.ABORTED)
        db = make_mock_db(m)
        with pytest.raises(InvalidTransitionError):
            transition_state(db, "M_001", MissionState.ACTIVE)

    def test_draft_to_aborted_allowed(self):
        m = make_mission(MissionState.DRAFT)
        db = make_mock_db(m)
        result = transition_state(db, "M_001", MissionState.ABORTED)
        assert result.state == MissionState.ABORTED
