"""Authentication routes - PIN-based family profiles."""
import uuid
import hashlib
from datetime import datetime, timedelta
from typing import List, Tuple

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db
from app.core.auth import require_admin
from app.core.rate_limit import limiter, RATE_LIMIT_AUTH, RATE_LIMIT_DEFAULT
from app.models.database import Profile
from app.models.schemas import (
    ProfileCreate, ProfileResponse, LoginRequest, TokenResponse
)

router = APIRouter()

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24


def hash_pin(pin: str) -> str:
    """Hash a PIN using bcrypt with random salt."""
    pin_bytes = pin.encode('utf-8')
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pin_bytes, salt).decode('utf-8')


def _legacy_hash_pin(pin: str) -> str:
    """Legacy SHA256 hash for migration purposes only."""
    salted = f"pool_telemetry_{pin}_salt"
    return hashlib.sha256(salted.encode()).hexdigest()


def _is_bcrypt_hash(pin_hash: str) -> bool:
    """Check if hash is bcrypt format (starts with $2b$)."""
    return pin_hash.startswith(("$2b$", "$2a$", "$2y$"))


def verify_pin(pin: str, pin_hash: str) -> Tuple[bool, bool]:
    """
    Verify a PIN against its hash.

    Returns:
        Tuple of (is_valid, needs_upgrade)
        - is_valid: True if PIN matches
        - needs_upgrade: True if hash should be upgraded to bcrypt
    """
    if _is_bcrypt_hash(pin_hash):
        try:
            is_valid = bcrypt.checkpw(pin.encode('utf-8'), pin_hash.encode('utf-8'))
            return is_valid, False
        except Exception:
            return False, False
    else:
        # Legacy SHA256 hash - verify and flag for upgrade
        is_valid = _legacy_hash_pin(pin) == pin_hash
        return is_valid, is_valid  # Only upgrade if valid


def create_access_token(profile_id: str) -> str:
    """Create JWT access token."""
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode = {"sub": profile_id, "exp": expire}
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


@router.get("/profiles", response_model=List[ProfileResponse])
async def list_profiles(db: AsyncSession = Depends(get_db)):
    """List all family profiles (for profile selection screen)."""
    result = await db.execute(select(Profile).order_by(Profile.name))
    profiles = result.scalars().all()
    return profiles


@router.post("/profiles", response_model=ProfileResponse)
async def create_profile(
    profile_data: ProfileCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new family profile."""
    # Check if first profile (make admin)
    result = await db.execute(select(Profile))
    is_first = result.first() is None

    profile = Profile(
        id=uuid.uuid4().hex,
        name=profile_data.name,
        pin_hash=hash_pin(profile_data.pin),
        avatar=profile_data.avatar,
        is_admin=is_first,
    )

    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    return profile


@router.post("/login", response_model=TokenResponse)
@limiter.limit(RATE_LIMIT_AUTH)
async def login(
    request: Request,
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Login with profile and PIN."""
    result = await db.execute(
        select(Profile).where(Profile.id == login_data.profile_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )

    is_valid, needs_upgrade = verify_pin(login_data.pin, profile.pin_hash)

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect PIN"
        )

    # Upgrade legacy SHA256 hash to bcrypt on successful login
    if needs_upgrade:
        profile.pin_hash = hash_pin(login_data.pin)
        await db.commit()
        await db.refresh(profile)

    access_token = create_access_token(profile.id)

    return TokenResponse(
        access_token=access_token,
        profile=ProfileResponse.model_validate(profile)
    )


@router.delete("/profiles/{profile_id}")
async def delete_profile(
    profile_id: str,
    admin: Profile = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete a profile (admin only)."""
    # Prevent self-deletion
    if profile_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own profile"
        )

    result = await db.execute(
        select(Profile).where(Profile.id == profile_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )

    await db.delete(profile)
    await db.commit()

    return {"status": "deleted"}
