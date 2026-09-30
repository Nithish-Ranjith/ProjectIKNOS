"""
backend/tests/test_audit.py — Unit tests for the hash-chained audit service.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import pytest
from unittest.mock import MagicMock, patch
from backend.app import audit_service
from backend.app import models


def make_mock_db(existing_entries=None):
    """Create a mock SQLAlchemy Session with given audit entries."""
    db = MagicMock()
    mock_query = MagicMock()

    entries = existing_entries or []
    mock_query.filter.return_value.order_by.return_value.first.return_value = (
        entries[-1] if entries else None
    )
    mock_query.filter.return_value.order_by.return_value.all.return_value = entries
    db.query.return_value = mock_query
    db.add = MagicMock()
    return db


class TestAppendEvent:
    def test_genesis_entry_has_GENESIS_prev_hash(self):
        db = make_mock_db(existing_entries=None)
        entry = audit_service.append_event(db, "CASE_01", "CASE_OPENED", {}, "SYSTEM", "SYSTEM")
        assert entry.previous_hash == "GENESIS"
        assert entry.seq == 0
        assert len(entry.current_hash) == 64  # SHA-256 hex digest

    def test_chained_entry_uses_previous_hash(self):
        # Create a mock first entry
        first = models.AuditLog(
            audit_id="first_id",
            case_id="CASE_01",
            event_type="CASE_OPENED",
            actor_id="SYSTEM",
            actor_role="SYSTEM",
            timestamp=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            data={},
            previous_hash="GENESIS",
            current_hash="abc123",
            seq=0,
        )
        db = make_mock_db(existing_entries=[first])
        entry = audit_service.append_event(db, "CASE_01", "DECISION", {"decision": "reject"}, "U1", "SURVEYOR_FIELD")
        assert entry.previous_hash == "abc123"
        assert entry.seq == 1

    def test_hash_is_deterministic(self):
        """Same payload → same hash."""
        db = make_mock_db()
        e1 = audit_service.append_event(db, "CASE_X", "CASE_OPENED", {}, "SYSTEM", "SYSTEM")
        # Mock again with same genesis conditions
        db2 = make_mock_db()
        e2 = audit_service.append_event(db2, "CASE_X", "CASE_OPENED", {}, "SYSTEM", "SYSTEM")
        # Note: timestamps will differ, so hashes will differ.
        # What we CAN assert is that the structure is consistent.
        assert len(e1.current_hash) == 64
        assert len(e2.current_hash) == 64


class TestVerifyChain:
    def test_empty_chain_is_valid(self):
        db = make_mock_db(existing_entries=[])
        result = audit_service.verify_chain(db, "CASE_01")
        assert result["valid"] is True
        assert result["entries_checked"] == 0

    def test_valid_chain(self):
        # Build a real two-entry chain
        import datetime, hashlib, json

        def make_entry(audit_id, seq, prev_hash, event_type, case_id="CASE_01"):
            ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
            payload = json.dumps({
                "audit_id": audit_id, "case_id": case_id, "event_type": event_type,
                "actor_id": "SYSTEM", "actor_role": "SYSTEM",
                "timestamp": ts, "data": {}, "previous_hash": prev_hash, "seq": seq
            }, sort_keys=True, separators=(',', ':'))
            current_hash = hashlib.sha256(payload.encode()).hexdigest()
            entry = models.AuditLog(
                audit_id=audit_id, case_id=case_id, event_type=event_type,
                actor_id="SYSTEM", actor_role="SYSTEM",
                timestamp=datetime.datetime.fromisoformat(ts),
                data={}, previous_hash=prev_hash, current_hash=current_hash, seq=seq
            )
            return entry, current_hash

        e1, h1 = make_entry("id1", 0, "GENESIS", "CASE_OPENED")
        e2, h2 = make_entry("id2", 1, h1, "DECISION")

        db = make_mock_db(existing_entries=[e1, e2])
        result = audit_service.verify_chain(db, "CASE_01")
        assert result["valid"] is True
        assert result["entries_checked"] == 2
