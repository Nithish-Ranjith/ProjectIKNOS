"""
ml/fuzzy/matcher.py — Standalone Jaro-Winkler matcher for ML pipeline use.
Delegates to backend/app/fuzzy_match.py logic (duplicated here to keep ml/ self-contained).
"""
import sys
sys.path.insert(0, "backend")

from backend.app.fuzzy_match import match_record_fields, jaro_winkler

__all__ = ["match_record_fields", "jaro_winkler"]
