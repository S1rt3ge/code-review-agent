"""JWT authentication utilities and FastAPI dependency for current user.

Functions:
    hash_password: Hash a plaintext password with bcrypt.
    verify_password: Check a plaintext password against a bcrypt hash.
    create_access_token: Issue a signed JWT for a user.
    verify_token: Decode and validate a JWT, returning its claims.
    get_current_user: FastAPI dependency that extracts and validates the
        Bearer token and returns the authenticated User ORM object.
"""

import base64
import hashlib
import hmac
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.utils.database import get_db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALGORITHM = settings.jwt_algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

# PBKDF2-SHA256 parameters (OWASP recommended minimum).
_HASH_ALG = "sha256"
_ITERATIONS = 260_000
_SALT_BYTES = 32


# ---------------------------------------------------------------------------
# Password hashing (PBKDF2-SHA256, stdlib only)
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    """Hash a plaintext password using PBKDF2-SHA256.

    The salt is prepended to the derived key and the whole thing is
    base64-encoded for compact storage.

    Args:
        plain: The user's plaintext password.

    Returns:
        Base64-encoded ``salt + key`` string suitable for storage.
    """
    salt = os.urandom(_SALT_BYTES)
    key = hashlib.pbkdf2_hmac(_HASH_ALG, plain.encode(), salt, _ITERATIONS)
    return base64.b64encode(salt + key).decode()


def verify_password(plain: str, stored: str) -> bool:
    """Verify a plaintext password against a PBKDF2-SHA256 hash.

    Args:
        plain: Plaintext password from the login form.
        stored: Stored value produced by ``hash_password``.

    Returns:
        True if the password matches, False otherwise.
    """
    try:
        decoded = base64.b64decode(stored.encode())
    except Exception:
        return False
    salt = decoded[:_SALT_BYTES]
    expected_key = decoded[_SALT_BYTES:]
    actual_key = hashlib.pbkdf2_hmac(_HASH_ALG, plain.encode(), salt, _ITERATIONS)
    return hmac.compare_digest(expected_key, actual_key)


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------


def create_access_token(user_id: uuid.UUID, email: str) -> str:
    """Create a signed JWT access token for the given user.

    Args:
        user_id: The user's UUID (stored as ``sub`` claim).
        email: The user's email (stored as ``email`` claim).

    Returns:
        Signed JWT string.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def verify_token(token: str) -> dict:
    """Decode and validate a JWT token.

    Args:
        token: Encoded JWT string.

    Returns:
        Decoded payload dict with at minimum ``sub`` and ``email`` keys.

    Raises:
        HTTPException 401: If the token is expired, malformed, or missing
            required claims.
    """
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except JWTError as exc:
        logger.debug("JWT decode failed: %s", exc)
        raise credentials_exc

    if payload.get("sub") is None:
        raise credentials_exc

    return payload


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


async def get_current_user(
    token: str = Depends(_oauth2_scheme),
    session: AsyncSession = Depends(get_db),
):
    """FastAPI dependency: extract the Bearer token and return the User row.

    Args:
        token: JWT from the Authorization header (injected by OAuth2PasswordBearer).
        session: Async database session.

    Returns:
        User ORM object for the authenticated user.

    Raises:
        HTTPException 401: If the token is invalid or the user no longer exists.
    """
    # Import here to avoid circular imports at module load time.
    from backend.models.db_models import User  # noqa: PLC0415

    payload = verify_token(token)
    user_id_str: str = payload["sub"]

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
