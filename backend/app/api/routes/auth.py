"""Authentication routes - PIN-based family profiles."""
from __future__ import annotations

import uuid
import hashlib
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db
from app.models.database import Profile
from app.models.schemas import (
    ProfileCreate, ProfileResponse, LoginRequest, TokenResponse
)

router = APIRouter()

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24


def hash_pin(pin: str) -> str:
    """Hash a PIN using SHA256 with salt (simple for family app)."""
    salted = f"pool_telemetry_{pin}_salt"
    return hashlib.sha256(salted.encode()).hexdigest()


def verify_pin(pin: str, pin_hash: str) -> bool:
    """Verify a PIN against its hash."""
    return hash_pin(pin) == pin_hash


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
async def login(
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

    if not verify_pin(login_data.pin, profile.pin_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect PIN"
        )

    access_token = create_access_token(profile.id)

    return TokenResponse(
        access_token=access_token,
        profile=ProfileResponse.model_validate(profile)
    )


@router.delete("/profiles/{profile_id}")
async def delete_profile(
    profile_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete a profile (admin only in production)."""
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
