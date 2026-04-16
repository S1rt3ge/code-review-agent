"""Tests for backend/utils/auth.py and backend/routers/auth.py.

Covers:
    hash_password / verify_password: bcrypt round-trip
    create_access_token / verify_token: JWT encode/decode
    verify_token: expired and invalid-sub edge cases
    get_current_user: happy path and error paths (mocked DB)
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from jose import jwt

from backend.config import settings
from backend.utils.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
    verify_token,
)


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def test_hash_password_produces_non_empty_string():
    hashed = hash_password("secret123")
    assert isinstance(hashed, str)
    assert len(hashed) > 20


def test_verify_password_correct():
    hashed = hash_password("mypassword")
    assert verify_password("mypassword", hashed) is True


def test_verify_password_wrong():
    hashed = hash_password("mypassword")
    assert verify_password("wrongpassword", hashed) is False


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------


def test_create_access_token_returns_string():
    uid = uuid.uuid4()
    token = create_access_token(uid, "user@example.com")
    assert isinstance(token, str)
    assert len(token) > 20


def test_verify_token_returns_correct_sub():
    uid = uuid.uuid4()
    token = create_access_token(uid, "user@example.com")
    payload = verify_token(token)
    assert payload["sub"] == str(uid)
    assert payload["email"] == "user@example.com"


def test_verify_token_expired_raises_401():
    uid = uuid.uuid4()
    expired_payload = {
        "sub": str(uid),
        "email": "x@x.com",
        "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        "iat": datetime.now(timezone.utc) - timedelta(minutes=5),
    }
    token = jwt.encode(
        expired_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )
    with pytest.raises(HTTPException) as exc_info:
        verify_token(token)
    assert exc_info.value.status_code == 401


def test_verify_token_invalid_signature_raises_401():
    uid = uuid.uuid4()
    token = create_access_token(uid, "user@example.com")
    tampered = token[:-4] + "XXXX"
    with pytest.raises(HTTPException) as exc_info:
        verify_token(tampered)
    assert exc_info.value.status_code == 401


def test_verify_token_missing_sub_raises_401():
    payload = {
        "email": "x@x.com",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    with pytest.raises(HTTPException) as exc_info:
        verify_token(token)
    assert exc_info.value.status_code == 401


def test_verify_password_with_malformed_hash_returns_false():
    assert verify_password("any", "not-base64") is False


# ---------------------------------------------------------------------------
# get_current_user dependency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_current_user_returns_user():
    uid = uuid.uuid4()
    token = create_access_token(uid, "found@example.com")

    mock_user = MagicMock()
    mock_user.id = uid

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_user)

    user = await get_current_user(token=token, session=mock_session)
    assert user is mock_user


@pytest.mark.asyncio
async def test_get_current_user_not_found_raises_401():
    uid = uuid.uuid4()
    token = create_access_token(uid, "gone@example.com")

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=token, session=mock_session)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_invalid_token_raises_401():
    mock_session = AsyncMock()
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token="not.a.valid.jwt", session=mock_session)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_unverified_email_raises_403():
    uid = uuid.uuid4()
    token = create_access_token(uid, "unverified@example.com")

    mock_user = MagicMock()
    mock_user.id = uid
    mock_user.email_verified = False

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_user)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=token, session=mock_session)

    assert exc_info.value.status_code == 403
