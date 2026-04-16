"""Authentication endpoints and account lifecycle flows.

Functions:
    register: POST /auth/register -- create account.
    login: POST /auth/token -- email/password login returning JWT.
    me: GET /auth/me -- return current user profile.
    request_password_reset: POST /auth/password-reset/request.
    confirm_password_reset: POST /auth/password-reset/confirm.
    request_email_verification: POST /auth/email-verification/request.
    confirm_email_verification: POST /auth/email-verification/confirm.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.db_models import User
from backend.models.schemas import (
    EmailVerificationConfirmRequest,
    EmailVerificationRequest,
    MessageResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from backend.services.notifications import (
    build_email_verification_email,
    build_password_reset_email,
    send_email,
)
from backend.utils.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from backend.utils.database import get_db
from backend.utils.rate_limit import limiter
from backend.utils.tokens import generate_urlsafe_token, hash_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _frontend_link(path: str, token: str) -> str:
    """Build an absolute frontend URL for email links."""
    base = settings.frontend_base_url.rstrip("/")
    return f"{base}{path}?token={token}"


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
@limiter.limit(settings.auth_register_rate_limit)
async def register(
    request: Request,  # noqa: ARG001
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

    # Derive username from email prefix if not provided
    username = payload.username or payload.email.split("@")[0]

    # Ensure username is unique (append suffix if taken)
    base = username
    suffix = 1
    while True:
        existing_username = await session.execute(
            select(User).where(User.username == username)
        )
        if existing_username.scalar_one_or_none() is None:
            break
        username = f"{base}{suffix}"
        suffix += 1

    now = datetime.now(timezone.utc)
    verification_token = generate_urlsafe_token()

    user = User(
        id=uuid.uuid4(),
        email=payload.email,
        username=username,
        hashed_password=hash_password(payload.password),
        email_verified=False,
        email_verification_token_hash=hash_token(verification_token),
        email_verification_expires_at=(
            now + timedelta(minutes=settings.email_verification_token_expire_minutes)
        ),
        email_verification_sent_at=now,
    )
    session.add(user)
    await session.flush()

    token = create_access_token(user_id=user.id, email=user.email)

    verification_link = _frontend_link("/verify-email", verification_token)
    subject, body = build_email_verification_email(verification_link)
    try:
        await send_email(user.email, subject, body)
    except Exception as exc:  # pragma: no cover - best-effort side effect
        logger.warning("Failed to send verification email to %s: %s", user.email, exc)

    logger.info("Registered new user %s (%s)", user.username, user.email)

    return TokenResponse(
        access_token=token,
        user_id=str(user.id),
        email=user.email,
        username=user.username,
    )


@router.post("/token", response_model=TokenResponse)
@limiter.limit(settings.auth_login_rate_limit)
async def login(
    request: Request,  # noqa: ARG001
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate with email and password, returning a JWT.

    Accepts OAuth2 form-encoded body (username=email&password=...).
    Also accessible at POST /auth/login for convenience.

    Args:
        form_data: OAuth2 form with username (email) and password.
        session: Async database session.

    Returns:
        JWT access token and basic user profile.

    Raises:
        HTTPException 401: If credentials are invalid.
    """
    result = await session.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()

    invalid_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if user is None or not user.hashed_password:
        raise invalid_exc

    if not verify_password(form_data.password, user.hashed_password):
        raise invalid_exc

    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email is not verified. Check your inbox or request a new verification link.",
        )

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


@router.post("/password-reset/request", response_model=MessageResponse)
@limiter.limit(settings.auth_password_reset_rate_limit)
async def request_password_reset(
    request: Request,  # noqa: ARG001
    payload: PasswordResetRequest,
    session: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Request password reset link (enumeration-safe response)."""
    generic_message = (
        "If an account with that email exists, a password reset link has been sent."
    )

    result = await session.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if user is None or not user.hashed_password:
        return MessageResponse(message=generic_message)

    token = generate_urlsafe_token()
    user.password_reset_token_hash = hash_token(token)
    user.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.password_reset_token_expire_minutes
    )
    user.password_reset_requested_at = datetime.now(timezone.utc)
    await session.flush()

    reset_link = _frontend_link("/reset-password", token)
    subject, body = build_password_reset_email(reset_link)

    try:
        await send_email(user.email, subject, body)
    except Exception as exc:  # pragma: no cover - best-effort side effect
        logger.warning("Failed to send password reset email to %s: %s", user.email, exc)

    return MessageResponse(message=generic_message)


@router.post("/password-reset/confirm", response_model=MessageResponse)
@limiter.limit(settings.auth_password_reset_rate_limit)
async def confirm_password_reset(
    request: Request,  # noqa: ARG001
    payload: PasswordResetConfirmRequest,
    session: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Confirm password reset with one-time token and new password."""
    if len(payload.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters",
        )

    now = datetime.now(timezone.utc)
    token_hash = hash_token(payload.token)
    result = await session.execute(
        select(User).where(
            User.password_reset_token_hash == token_hash,
            User.password_reset_expires_at.is_not(None),
            User.password_reset_expires_at >= now,
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token",
        )

    user.hashed_password = hash_password(payload.new_password)
    user.password_reset_token_hash = None
    user.password_reset_expires_at = None
    user.password_reset_requested_at = None
    await session.flush()

    logger.info("Password reset completed for user %s", user.email)
    return MessageResponse(message="Password has been reset successfully.")


@router.post("/email-verification/request", response_model=MessageResponse)
@limiter.limit(settings.auth_email_verify_rate_limit)
async def request_email_verification(
    request: Request,  # noqa: ARG001
    payload: EmailVerificationRequest,
    session: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Request email verification link (enumeration-safe response)."""
    generic_message = (
        "If the account exists and is unverified, a verification link has been sent."
    )

    result = await session.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if user is None or user.email_verified:
        return MessageResponse(message=generic_message)

    token = generate_urlsafe_token()
    user.email_verification_token_hash = hash_token(token)
    user.email_verification_expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.email_verification_token_expire_minutes
    )
    user.email_verification_sent_at = datetime.now(timezone.utc)
    await session.flush()

    verification_link = _frontend_link("/verify-email", token)
    subject, body = build_email_verification_email(verification_link)

    try:
        await send_email(user.email, subject, body)
    except Exception as exc:  # pragma: no cover - best-effort side effect
        logger.warning("Failed to send verification email to %s: %s", user.email, exc)

    return MessageResponse(message=generic_message)


@router.post("/email-verification/confirm", response_model=MessageResponse)
@limiter.limit(settings.auth_email_verify_rate_limit)
async def confirm_email_verification(
    request: Request,  # noqa: ARG001
    payload: EmailVerificationConfirmRequest,
    session: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Confirm email verification token and activate email_verified flag."""
    now = datetime.now(timezone.utc)
    token_hash = hash_token(payload.token)
    result = await session.execute(
        select(User).where(
            User.email_verification_token_hash == token_hash,
            User.email_verification_expires_at.is_not(None),
            User.email_verification_expires_at >= now,
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    user.email_verified = True
    user.email_verified_at = now
    user.email_verification_token_hash = None
    user.email_verification_expires_at = None
    user.email_verification_sent_at = None
    await session.flush()

    logger.info("Email verified for user %s", user.email)
    return MessageResponse(message="Email verified successfully.")


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
