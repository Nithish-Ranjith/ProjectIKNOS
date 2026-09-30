"""
backend/tests/test_fuzzy_match.py — Unit tests for Jaro-Winkler fuzzy matcher.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import pytest
from backend.app.fuzzy_match import jaro_winkler, match_record_fields


class TestJaroWinkler:
    def test_identical_strings(self):
        assert jaro_winkler("Ramesh Kumar", "Ramesh Kumar") == 1.0

    def test_empty_string(self):
        assert jaro_winkler("", "Ramesh") == 0.0

    def test_completely_different(self):
        score = jaro_winkler("ABCDE", "ZYXWV")
        assert score < 0.5

    def test_transposition(self):
        # Typical name spelling variation — should score high
        score = jaro_winkler("Ramesh", "Ramash")
        assert score > 0.85

    def test_prefix_boost(self):
        # Winkler prefix boost: 'MARTHA' vs 'MARHTA' example from paper
        score = jaro_winkler("MARTHA", "MARHTA")
        assert score > 0.90


class TestMatchRecordFields:
    def test_exact_name_and_id_match(self):
        result = match_record_fields("Ravi Shankar", "Ravi Shankar", "KH-1234", "KH-1234")
        assert result["status"] == "MATCHED"

    def test_id_mismatch_always_unresolved(self):
        result = match_record_fields("Ravi Shankar", "Ravi Shankar", "KH-1234", "KH-9999")
        assert result["status"] == "UNRESOLVED"

    def test_strong_name_no_ids(self):
        result = match_record_fields("Ravi Kumar", "Ravi Kumaar", None, None)
        assert result["status"] == "MATCHED"

    def test_ambiguous_name_with_one_id(self):
        result = match_record_fields("Ravi Kumar", "Ravi Kumaar", "KH-1234", None)
        assert result["status"] == "AMBIGUOUS"

    def test_weak_name_no_id(self):
        result = match_record_fields("Ravi Kumar", "Suresh Rao", None, None)
        assert result["status"] == "UNRESOLVED"

    def test_exact_id_no_names(self):
        result = match_record_fields(None, None, "KH-1234", "KH-1234")
        assert result["status"] == "MATCHED"

    def test_both_empty(self):
        result = match_record_fields(None, None, None, None)
        assert result["status"] == "UNRESOLVED"
