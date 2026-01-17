"""Authentication dependencies for route protection."""
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db
from app.models.database import Profile

# Security scheme for OpenAPI docs
security = HTTPBearer(auto_error=False)

ALGORITHM = "HS256"


async def get_current_profile_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    """
    Extract and verify profile_id from JWT token.

    Raises 401 if token is missing, invalid, or expired.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.secret_key,
            algorithms=[ALGORITHM]
        )
        profile_id: str = payload.get("sub")
        if profile_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
        return profile_id
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token validation failed",
        )


async def get_current_profile(
    profile_id: str = Depends(get_current_profile_id),
    db: AsyncSession = Depends(get_db),
) -> Profile:
    """
    Get the full Profile object for the authenticated user.

    Raises 401 if profile doesn't exist (deleted after token issued).
    """
    result = await db.execute(select(Profile).where(Profile.id == profile_id))
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Profile not found",
        )
    return profile


async def require_admin(
    profile: Profile = Depends(get_current_profile),
) -> Profile:
    """
    Require admin privileges for the endpoint.

    Raises 403 if user is not admin.
    """
    if not profile.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return profile


async def get_optional_profile_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[str]:
    """
    Get profile_id if token is valid, None otherwise.

    Use for endpoints that work with or without authentication.
    """
    if not credentials:
        return None
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.secret_key,
            algorithms=[ALGORITHM]
        )
        return payload.get("sub")
    except JWTError:
        return None


def verify_ws_token(token: str) -> Optional[str]:
    """
    Verify JWT token for WebSocket connections.

    Returns profile_id if valid, None otherwise.
    Used for WebSocket endpoints that receive token via query parameter.
    """
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None
