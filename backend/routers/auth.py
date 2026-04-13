"""Authentication endpoints: register, login, and current-user info.

Functions:
    register: POST /auth/register -- create a new user account.
    login: POST /auth/token -- email/password login returning JWT.
    me: GET /auth/me -- return the authenticated user's profile.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.db_models import User
from backend.models.schemas import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from backend.utils.auth import create_access_token, get_current_user, hash_password, verify_password
from backend.utils.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Create a new user account and return an access token.

    Args:
        payload: Email, username, and password for the new account.
        session: Async database session.

    Returns:
        JWT access token and basic user profile.

    Raises:
        HTTPException 409: If the email or username is already taken.
    """
    # Check for duplicate email
    existing_email = await session.execute(
        select(User).where(User.email == payload.email)
    )
    if existing_email.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        )

    # Check for duplicate username
    existing_username = await session.execute(
        select(User).where(User.username == payload.username)
    )
    if existing_username.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username is already taken",
        )

    user = User(
        id=uuid.uuid4(),
        email=payload.email,
        username=payload.username,
        hashed_password=hash_password(payload.password),
    )
    session.add(user)
    await session.flush()

    token = create_access_token(user_id=user.id, email=user.email)
    logger.info("Registered new user %s (%s)", user.username, user.email)

    return TokenResponse(
        access_token=token,
        user_id=str(user.id),
        email=user.email,
        username=user.username,
    )


@router.post("/token", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate with email and password, returning a JWT.

    Also accessible at POST /auth/login for convenience.

    Args:
        payload: Email and password credentials.
        session: Async database session.

    Returns:
        JWT access token and basic user profile.

    Raises:
        HTTPException 401: If credentials are invalid.
    """
    result = await session.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    invalid_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if user is None or not user.hashed_password:
        raise invalid_exc

    if not verify_password(payload.password, user.hashed_password):
        raise invalid_exc

    token = create_access_token(user_id=user.id, email=user.email)
    logger.info("User %s logged in", user.email)

    return TokenResponse(
        access_token=token,
        user_id=str(user.id),
        email=user.email,
        username=user.username,
    )


# Alias for frontend convenience
router.post("/login", response_model=TokenResponse)(login)


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Return the authenticated user's profile.

    Args:
        current_user: User injected by the JWT dependency.

    Returns:
        User profile (no sensitive fields).
    """
    return UserResponse.model_validate(current_user)
