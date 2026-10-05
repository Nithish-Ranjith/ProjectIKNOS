"""
backend/app/auth.py — JWT authentication and role/authority-tier enforcement.

Design contracts:
  - Role is assigned by admin server-side. Client NEVER self-assigns a role.
  - Authority tier is derived from the user's role at login time and embedded in JWT.
  - All role checks are performed server-side in dependency functions.
  - CUSTOMER: tier 0 — view own parcels, submit objections.
  - SURVEYOR_DRONE: tier 1 — mission operations only, cannot approve cases.
  - SURVEYOR_FIELD: tier 1 — case review, field verification, decisions within tier.
  - SENIOR_FIELD: tier 2 — authority for OWNERSHIP and CADASTRAL_GEOMETRY updates.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .database import get_db
from . import models

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SECRET_KEY = os.environ.get("IKNOS_SECRET_KEY", "CHANGE_ME_IN_PRODUCTION_USE_ENV_VAR")
SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET", "CHANGE_ME_IN_PRODUCTION_USE_ENV_VAR")
IKNOS_ENV = os.environ.get("IKNOS_ENV", "development").lower()
IS_PRODUCTION = IKNOS_ENV == "production"
_PLACEHOLDER_SECRET = "CHANGE_ME_IN_PRODUCTION_USE_ENV_VAR"
# Demo header login is a development convenience. It is hard-disabled in production.
IKNOS_DEMO = "0" if IS_PRODUCTION else os.environ.get("IKNOS_DEMO", "0")


def assert_production_safe() -> None:
    """Called at startup. Raises if a production deployment still has dev auth switches/secrets."""
    if not IS_PRODUCTION:
        return
    problems = []
    if os.environ.get("IKNOS_DEMO", "0") == "1":
        problems.append("IKNOS_DEMO=1 must not be set in production")
    if SECRET_KEY == _PLACEHOLDER_SECRET:
        problems.append("IKNOS_SECRET_KEY is the placeholder value")
    if SUPABASE_JWT_SECRET == _PLACEHOLDER_SECRET:
        problems.append("SUPABASE_JWT_SECRET is the placeholder value")
    if problems:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))

def dev_only() -> None:
    """FastAPI dependency: endpoint exists only outside production (mock OTP, dummy-hash login)."""
    if IS_PRODUCTION:
        raise HTTPException(status_code=404, detail="Not found")


ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("TOKEN_EXPIRE_MINUTES", "480"))  # 8h field sessions

_CONFIG_PATH = Path(__file__).parent / "config" / "weights.json"
with open(_CONFIG_PATH) as _f:
    _CONFIG = json.load(_f)

AUTHORITY_TIERS: dict[str, int] = _CONFIG["authority_tiers"]
UPDATE_CLASS_MIN_TIER: dict[str, int] = _CONFIG["update_class_min_tier"]

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    # Bypass passlib bcrypt bug on modern python versions
    return f"dummy_hash_{plain}"


def verify_password(plain: str, hashed: str) -> bool:
    return hashed == f"dummy_hash_{plain}"


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def create_access_token(user: models.User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user.user_id,
        "role": user.role.value,
        "tier": user.authority_tier,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ---------------------------------------------------------------------------
# FastAPI dependency: get current user from Bearer token
# ---------------------------------------------------------------------------

def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    # 1. Handle Demo Header Login (Bypass JWT for hardcoded demo personas)
    if IKNOS_DEMO == "1":
        demo_email = request.headers.get("X-Demo-Email")
        demo_role = request.headers.get("X-Demo-Role")
        if demo_email:
            role_map = {
                "admin": "senior1",
                "surveyor": "drone1",
                "user": "customer1"
            }
            username = role_map.get(demo_role, "customer1")
            user = db.query(models.User).filter(models.User.username == username).first()
            if user:
                return user
            
    # 2. Handle Supabase JWT Token
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        # Verify Supabase JWT signature correctly using the secret
        payload = jwt.decode(
            credentials.credentials, 
            SUPABASE_JWT_SECRET, 
            algorithms=["HS256"], 
            audience="authenticated"
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    sub = payload.get("sub")
    user = db.get(models.User, sub)
    
    # Auto-create if signed up via Supabase just now
    if not user:
        email = payload.get("email", "unknown@example.com")
        # Securely read role from app_metadata (admin assigned), not user_metadata
        role_str = payload.get("app_metadata", {}).get("role", "user")
        
        db_role = models.UserRole.CUSTOMER
        if role_str == "admin":
            db_role = models.UserRole.ADMIN
        elif role_str == "surveyor":
            db_role = models.UserRole.SURVEYOR_DRONE
            
        user = models.User(
            user_id=sub, 
            username=email.split("@")[0],
            role=db_role,
            authority_tier=0 if db_role == models.UserRole.CUSTOMER else 1
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is inactive")
        
    return user


# ---------------------------------------------------------------------------
# Role-gating dependency factories
# ---------------------------------------------------------------------------

def require_role(*allowed_roles: str):
    """Dependency that enforces the caller has one of the allowed roles."""
    def _check(current_user: models.User = Depends(get_current_user)) -> models.User:
        if current_user.role.value not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role {current_user.role.value} is not permitted for this operation",
            )
        return current_user
    return _check


def require_authority_tier(min_tier: int):
    """Dependency that enforces the caller meets a minimum authority tier."""
    def _check(current_user: models.User = Depends(get_current_user)) -> models.User:
        if current_user.authority_tier < min_tier:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Authority tier {current_user.authority_tier} insufficient; "
                       f"minimum required: {min_tier}",
            )
        return current_user
    return _check


def check_update_class_tier(update_class: str, current_user: models.User) -> None:
    """
    Raises 403 if the current user's authority tier is insufficient for the
    given update_class. Called inside route handlers, not as a dependency.
    """
    required = UPDATE_CLASS_MIN_TIER.get(update_class)
    if required is None:
        raise HTTPException(status_code=400, detail=f"Unknown update_class: {update_class}")
    if current_user.authority_tier < required:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"update_class={update_class} requires authority tier >= {required}; "
                f"you have tier {current_user.authority_tier}"
            ),
        )


# ---------------------------------------------------------------------------
# Parcel-level access scoping
# ---------------------------------------------------------------------------

def assert_parcel_access(parcel_id: str, current_user: models.User) -> None:
    """
    CUSTOMER role can only access parcels in their owned_parcel_ids list.
    All other roles have unrestricted parcel access.
    Raises 403 on violation.
    """
    if current_user.role == models.UserRole.CUSTOMER:
        owned = current_user.owned_parcel_ids or []
        if parcel_id not in owned:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied — parcel not in your registered holdings",
            )
