"""
backend/tests/test_security.py — Role and authority tier enforcement tests.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


class TestAuthModule:
    """Unit tests for auth.py helpers — no DB required."""

    def test_hash_and_verify_password(self):
        from backend.app.auth import hash_password, verify_password
        plain = "mysupersecretpassword123"
        hashed = hash_password(plain)
        assert hashed != plain
        assert verify_password(plain, hashed)
        assert not verify_password("wrongpassword", hashed)

    def test_check_update_class_tier_enforces_minimum(self):
        from backend.app.auth import check_update_class_tier
        from backend.app.models import User, UserRole
        from fastapi import HTTPException

        customer = MagicMock(spec=User)
        customer.authority_tier = 0
        customer.role = UserRole.CUSTOMER

        field = MagicMock(spec=User)
        field.authority_tier = 1
        field.role = UserRole.SURVEYOR_FIELD

        senior = MagicMock(spec=User)
        senior.authority_tier = 2
        senior.role = UserRole.SENIOR_FIELD

        # CUSTOMER cannot approve anything
        with pytest.raises(HTTPException) as exc:
            check_update_class_tier("OTHER_AUTHORIZED", customer)
        assert exc.value.status_code == 403

        # SURVEYOR_FIELD can approve OTHER_AUTHORIZED and MUTATION
        check_update_class_tier("OTHER_AUTHORIZED", field)  # should not raise
        check_update_class_tier("MUTATION", field)            # should not raise

        # SURVEYOR_FIELD cannot approve OWNERSHIP or CADASTRAL_GEOMETRY
        with pytest.raises(HTTPException):
            check_update_class_tier("OWNERSHIP", field)
        with pytest.raises(HTTPException):
            check_update_class_tier("CADASTRAL_GEOMETRY", field)

        # SENIOR_FIELD can approve all classes
        check_update_class_tier("OWNERSHIP", senior)
        check_update_class_tier("CADASTRAL_GEOMETRY", senior)

    def test_parcel_access_scoping_for_customer(self):
        from backend.app.auth import assert_parcel_access
        from backend.app.models import User, UserRole
        from fastapi import HTTPException

        customer = MagicMock(spec=User)
        customer.role = UserRole.CUSTOMER
        customer.owned_parcel_ids = ["P01", "P03"]

        # Allowed parcel
        assert_parcel_access("P01", customer)  # no exception

        # Not allowed parcel
        with pytest.raises(HTTPException) as exc:
            assert_parcel_access("P99", customer)
        assert exc.value.status_code == 403

    def test_non_customer_has_unrestricted_parcel_access(self):
        from backend.app.auth import assert_parcel_access
        from backend.app.models import User, UserRole

        field = MagicMock(spec=User)
        field.role = UserRole.SURVEYOR_FIELD
        field.owned_parcel_ids = []

        # No exception for any parcel
        assert_parcel_access("P99", field)
        assert_parcel_access("ANY_PARCEL", field)
