"""Integration tests — full HTTP request/response cycle via ASGI transport.

Tests cover:
    Auth flow: register → token → /me
    Review lifecycle: create → analyze (mocked) → list
    Settings: update → test-llm
    Dashboard stats: requires auth, returns per-user data
    Webhook: signature verification, unsupported action ignored
"""

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert, select

from backend.main import app
from backend.models.db_models import Repository, Review, User
from backend.utils.tokens import hash_token
from backend.utils.database import async_session_factory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unique_email() -> str:
    return f"integ_{uuid.uuid4().hex[:8]}@test.com"


def _sign(payload: bytes, secret: str) -> str:
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c


@pytest_asyncio.fixture
async def auth_headers(client):
    """Register a fresh user and return Authorization headers."""
    email = _unique_email()
    password = "TestPass123!"
    username = f"user_{uuid.uuid4().hex[:6]}"

    r = await client.post(
        "/api/auth/register",
        json={"email": email, "username": username, "password": password},
    )
    assert r.status_code == 201, r.text

    # Mark verified for tests that need authenticated access.
    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        user.email_verified = True
        user.email_verified_at = datetime.now(timezone.utc)
        await session.commit()

    r = await client.post(
        "/api/auth/token",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def db_repo_id(auth_headers, client):
    """Insert a repository row directly and return its UUID.

    There is no public POST /repositories endpoint; repos are normally
    created via the GitHub App webhook. For integration tests we insert
    one directly so we can exercise the review endpoints.
    """
    # Get current user id from /me
    me = await client.get("/api/auth/me", headers=auth_headers)
    user_id = me.json()["id"]

    repo_id = uuid.uuid4()
    async with async_session_factory() as session:
        await session.execute(
            insert(Repository).values(
                id=repo_id,
                user_id=user_id,
                github_repo_owner="testorg",
                github_repo_name=f"repo_{uuid.uuid4().hex[:6]}",
                github_repo_url="https://github.com/testorg/testrepo",
                github_installation_id=None,
                enabled=True,
            )
        )
        await session.commit()
    return str(repo_id)


# ---------------------------------------------------------------------------
# Auth flow
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_register_success(client):
    r = await client.post(
        "/api/auth/register",
        json={
            "email": _unique_email(),
            "username": f"u_{uuid.uuid4().hex[:6]}",
            "password": "Secret123!",
        },
    )
    assert r.status_code == 201
    assert "verify your email" in r.json()["message"].lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_register_duplicate_email_rejected(client):
    email = _unique_email()
    payload = {
        "email": email,
        "username": f"u_{uuid.uuid4().hex[:6]}",
        "password": "Secret123!",
    }
    await client.post("/api/auth/register", json=payload)
    r = await client.post("/api/auth/register", json={**payload, "username": "other"})
    assert r.status_code == 409


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_wrong_password(client):
    email = _unique_email()
    await client.post(
        "/api/auth/register",
        json={
            "email": email,
            "username": f"u_{uuid.uuid4().hex[:6]}",
            "password": "Correct1!",
        },
    )
    r = await client.post(
        "/api/auth/token",
        data={"username": email, "password": "WrongPass!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_unverified_email_rejected(client):
    email = _unique_email()
    await client.post(
        "/api/auth/register",
        json={
            "email": email,
            "username": f"u_{uuid.uuid4().hex[:6]}",
            "password": "Correct1!",
        },
    )

    r = await client.post(
        "/api/auth/token",
        data={"username": email, "password": "Correct1!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 403
    assert "not verified" in r.json()["detail"].lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_password_reset_request_returns_generic_message(client, auth_headers):
    me = await client.get("/api/auth/me", headers=auth_headers)
    email = me.json()["email"]

    r = await client.post(
        "/api/auth/password-reset/request",
        json={"email": email},
    )
    assert r.status_code == 200
    assert "password reset link" in r.json()["message"].lower()

    me = await client.get("/api/auth/me", headers=auth_headers)
    user_id = me.json()["id"]
    async with async_session_factory() as session:
        user = await session.get(User, user_id)
        assert user is not None
        assert user.password_reset_token_hash is not None
        assert user.password_reset_expires_at is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_password_reset_confirm_with_invalid_token(client):
    r = await client.post(
        "/api/auth/password-reset/confirm",
        json={"token": "invalid-token", "new_password": "NewPass123!"},
    )
    assert r.status_code == 400


@pytest.mark.integration
@pytest.mark.asyncio
async def test_email_verification_confirm_with_invalid_token(client):
    r = await client.post(
        "/api/auth/email-verification/confirm",
        json={"token": "invalid-token"},
    )
    assert r.status_code == 400


@pytest.mark.integration
@pytest.mark.asyncio
async def test_email_verification_request_returns_generic_message(client, auth_headers):
    me = await client.get("/api/auth/me", headers=auth_headers)
    email = me.json()["email"]

    r = await client.post(
        "/api/auth/email-verification/request",
        json={"email": email},
    )
    assert r.status_code == 200
    assert "verification link" in r.json()["message"].lower()

    me = await client.get("/api/auth/me", headers=auth_headers)
    user_id = me.json()["id"]
    async with async_session_factory() as session:
        user = await session.get(User, user_id)
        assert user is not None
        assert user.email_verification_token_hash is not None
        assert user.email_verification_expires_at is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_email_verification_confirm_allows_login(client):
    email = _unique_email()
    password = "Verified1!"
    reg = await client.post(
        "/api/auth/register",
        json={
            "email": email,
            "username": f"u_{uuid.uuid4().hex[:6]}",
            "password": password,
        },
    )
    assert reg.status_code == 201

    # before verification login is blocked
    blocked = await client.post(
        "/api/auth/token",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert blocked.status_code == 403

    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        assert user.email_verification_token_hash is not None
        raw_token = "manual-token"
        user.email_verification_token_hash = hash_token(raw_token)
        user.email_verification_expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=30
        )
        await session.commit()

    verified = await client.post(
        "/api/auth/email-verification/confirm",
        json={"token": raw_token},
    )
    assert verified.status_code == 200

    allowed = await client.post(
        "/api/auth/token",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert allowed.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_password_reset_confirm_changes_password(client):
    email = _unique_email()
    old_password = "OldPass123!"
    new_password = "NewPass123!"

    reg = await client.post(
        "/api/auth/register",
        json={
            "email": email,
            "username": f"u_{uuid.uuid4().hex[:6]}",
            "password": old_password,
        },
    )
    assert reg.status_code == 201

    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        user.email_verified = True
        user.password_reset_token_hash = hash_token("reset-token")
        user.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=30
        )
        await session.commit()

    confirm = await client.post(
        "/api/auth/password-reset/confirm",
        json={"token": "reset-token", "new_password": new_password},
    )
    assert confirm.status_code == 200

    old_login = await client.post(
        "/api/auth/token",
        data={"username": email, "password": old_password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        "/api/auth/token",
        data={"username": email, "password": new_password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert new_login.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_me_returns_current_user(client, auth_headers):
    r = await client.get("/api/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert "email" in r.json()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_protected_route_rejects_no_token(client):
    r = await client.get("/api/reviews")
    assert r.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_protected_route_rejects_bad_token(client):
    r = await client.get("/api/reviews", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Review lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_review(client, auth_headers, db_repo_id):
    r = await client.post(
        "/api/reviews",
        json={
            "repo_id": db_repo_id,
            "github_pr_number": 42,
            "selected_agents": ["security"],
        },
        headers=auth_headers,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending"
    assert body["github_pr_number"] == 42


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_review_rejects_foreign_repository(client, auth_headers):
    other_user_id = uuid.uuid4()
    foreign_repo_id = uuid.uuid4()
    async with async_session_factory() as session:
        await session.execute(
            insert(User).values(
                id=other_user_id,
                email=f"foreign_{uuid.uuid4().hex[:8]}@test.com",
                username=f"foreign_{uuid.uuid4().hex[:8]}",
                hashed_password="x",
                email_verified=True,
            )
        )
        await session.execute(
            insert(Repository).values(
                id=foreign_repo_id,
                user_id=other_user_id,
                github_repo_owner="other",
                github_repo_name=f"repo_{uuid.uuid4().hex[:6]}",
                github_repo_url="https://github.com/other/repo",
                enabled=True,
            )
        )
        await session.commit()

    r = await client.post(
        "/api/reviews",
        json={"repo_id": str(foreign_repo_id), "github_pr_number": 42},
        headers=auth_headers,
    )
    assert r.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_reviews_scoped_to_user(client, auth_headers, db_repo_id):
    # Create one review
    await client.post(
        "/api/reviews",
        json={"repo_id": db_repo_id, "github_pr_number": 99},
        headers=auth_headers,
    )
    r = await client.get("/api/reviews", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "reviews" in body
    assert "total" in body
    assert body["total"] >= 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_review_detail(client, auth_headers, db_repo_id):
    r = await client.post(
        "/api/reviews",
        json={"repo_id": db_repo_id, "github_pr_number": 7},
        headers=auth_headers,
    )
    review_id = r.json()["id"]
    r = await client.get(f"/api/reviews/{review_id}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["id"] == review_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_websocket_ticket_requires_review_ownership(client, auth_headers):
    r = await client.post(
        f"/api/reviews/{uuid.uuid4()}/ws-ticket",
        headers=auth_headers,
    )
    assert r.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_review_not_found(client, auth_headers):
    r = await client.get(f"/api/reviews/{uuid.uuid4()}", headers=auth_headers)
    assert r.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_analyze_sets_status_analyzing(client, auth_headers, db_repo_id):
    r = await client.post(
        "/api/reviews",
        json={"repo_id": db_repo_id, "github_pr_number": 11},
        headers=auth_headers,
    )
    review_id = r.json()["id"]

    with patch("backend.routers.reviews.enqueue_analysis", new_callable=AsyncMock):
        r = await client.post(f"/api/reviews/{review_id}/analyze", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "analyzing"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_analyze_rejects_unknown_force_agent(client, auth_headers, db_repo_id):
    r = await client.post(
        "/api/reviews",
        json={"repo_id": db_repo_id, "github_pr_number": 12},
        headers=auth_headers,
    )
    review_id = r.json()["id"]

    with patch("backend.routers.reviews.enqueue_analysis", new_callable=AsyncMock) as enqueue:
        r = await client.post(
            f"/api/reviews/{review_id}/analyze?force_agents=security,unknown",
            headers=auth_headers,
        )

    assert r.status_code == 400
    enqueue.assert_not_called()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_analyze_conflict_when_already_analyzing(
    client, auth_headers, db_repo_id
):
    r = await client.post(
        "/api/reviews",
        json={"repo_id": db_repo_id, "github_pr_number": 22},
        headers=auth_headers,
    )
    review_id = r.json()["id"]

    with patch("backend.routers.reviews.enqueue_analysis", new_callable=AsyncMock):
        await client.post(f"/api/reviews/{review_id}/analyze", headers=auth_headers)
        r = await client.post(f"/api/reviews/{review_id}/analyze", headers=auth_headers)
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_settings_default(client, auth_headers):
    r = await client.get("/api/settings", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "ollama_enabled" in body
    assert "default_agents" in body
    assert "lm_preference" in body


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_settings_agents(client, auth_headers):
    r = await client.put(
        "/api/settings",
        json={"default_agents": ["security", "logic"], "lm_preference": "auto"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert set(body["default_agents"]) == {"security", "logic"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_settings_rejects_empty_agents(client, auth_headers):
    r = await client.put(
        "/api/settings",
        json={"default_agents": []},
        headers=auth_headers,
    )
    assert r.status_code == 400


@pytest.mark.integration
@pytest.mark.asyncio
async def test_test_llm_returns_booleans(client, auth_headers):
    r = await client.post("/api/settings/test-llm", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["claude_available"], bool)
    assert isinstance(body["gpt_available"], bool)
    assert isinstance(body["ollama_available"], bool)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dashboard_stats_requires_auth(client):
    r = await client.get("/api/dashboard/stats")
    assert r.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dashboard_stats_shape(client, auth_headers):
    r = await client.get("/api/dashboard/stats", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    for key in (
        "total_reviews",
        "reviews_today",
        "findings_by_severity",
        "findings_by_agent",
        "tokens_used_this_month",
    ):
        assert key in body, f"missing key: {key}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dashboard_stats_isolated_per_user(client):
    """Two different users should see only their own totals."""

    async def make_user_token():
        email = _unique_email()
        username = f"u_{uuid.uuid4().hex[:6]}"
        await client.post(
            "/api/auth/register",
            json={"email": email, "username": username, "password": "Pass123!"},
        )

        async with async_session_factory() as session:
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one()
            user.email_verified = True
            user.email_verified_at = datetime.now(timezone.utc)
            await session.commit()

        r = await client.post(
            "/api/auth/token",
            data={"username": email, "password": "Pass123!"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        return r.json()["access_token"]

    tok_a = await make_user_token()
    tok_b = await make_user_token()

    r_a = await client.get(
        "/api/dashboard/stats", headers={"Authorization": f"Bearer {tok_a}"}
    )
    r_b = await client.get(
        "/api/dashboard/stats", headers={"Authorization": f"Bearer {tok_b}"}
    )
    assert r_a.status_code == 200
    assert r_b.status_code == 200
    # Both fresh users have 0 reviews — isolation is enforced
    assert r_a.json()["total_reviews"] == 0
    assert r_b.json()["total_reviews"] == 0


# ---------------------------------------------------------------------------
# GitHub webhook
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_webhook_missing_signature_rejected(client):
    r = await client.post(
        "/api/github/webhook",
        content=b"{}",
        headers={"Content-Type": "application/json", "X-GitHub-Event": "pull_request"},
    )
    assert r.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_webhook_bad_signature_rejected(client):
    r = await client.post(
        "/api/github/webhook",
        content=b'{"action":"opened"}',
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": "sha256=badhash",
        },
    )
    assert r.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_webhook_unsupported_action_ignored(client):
    """A valid signature with an unknown action returns 202 + 'ignored'."""
    secret = "test-webhook-secret"
    payload = json.dumps(
        {
            "action": "closed",
            "pull_request": {
                "number": 1,
                "title": "test",
                "head": {"sha": "abc"},
                "base": {"sha": "def"},
            },
            "repository": {
                "owner": {"login": "org"},
                "name": "repo",
                "full_name": "org/repo",
            },
        }
    ).encode()

    with patch("backend.config.settings.github_webhook_secret", secret):
        r = await client.post(
            "/api/github/webhook",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": _sign(payload, secret),
            },
        )
    assert r.status_code == 202
    assert r.json()["status"] == "ignored"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_webhook_opened_queues_analysis(client):
    """A valid opened PR webhook creates pending review and queues analysis."""
    user_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    owner = f"org_{uuid.uuid4().hex[:6]}"
    name = f"repo_{uuid.uuid4().hex[:6]}"

    async with async_session_factory() as session:
        await session.execute(
            insert(User).values(
                id=user_id,
                email=f"hook_{uuid.uuid4().hex[:8]}@test.com",
                username=f"hook_{uuid.uuid4().hex[:8]}",
                hashed_password="x",
                email_verified=True,
            )
        )
        await session.execute(
            insert(Repository).values(
                id=repo_id,
                user_id=user_id,
                github_repo_owner=owner,
                github_repo_name=name,
                github_repo_url=f"https://github.com/{owner}/{name}",
                enabled=True,
            )
        )
        await session.commit()

    secret = "test-webhook-secret"
    payload = json.dumps(
        {
            "action": "opened",
            "pull_request": {
                "number": 77,
                "title": "feature: webhook queue",
                "head": {"sha": "headsha123"},
                "base": {"sha": "basesha123"},
            },
            "repository": {
                "owner": {"login": owner},
                "name": name,
                "full_name": f"{owner}/{name}",
            },
        }
    ).encode()

    with (
        patch("backend.config.settings.github_webhook_secret", secret),
        patch(
            "backend.routers.github.enqueue_analysis", new_callable=AsyncMock
        ) as enqueue,
    ):
        r = await client.post(
            "/api/github/webhook",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": _sign(payload, secret),
            },
        )

    assert r.status_code == 202
    assert r.json()["status"] == "pending"
    enqueue.assert_called_once()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_webhook_duplicate_returns_existing_without_requeue(client):
    """Duplicate webhook should return existing pending review and not requeue."""
    user_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    review_id = uuid.uuid4()
    owner = f"orgdup_{uuid.uuid4().hex[:6]}"
    name = f"repodup_{uuid.uuid4().hex[:6]}"

    async with async_session_factory() as session:
        await session.execute(
            insert(User).values(
                id=user_id,
                email=f"hookdup_{uuid.uuid4().hex[:8]}@test.com",
                username=f"hookdup_{uuid.uuid4().hex[:8]}",
                hashed_password="x",
                email_verified=True,
            )
        )
        await session.execute(
            insert(Repository).values(
                id=repo_id,
                user_id=user_id,
                github_repo_owner=owner,
                github_repo_name=name,
                github_repo_url=f"https://github.com/{owner}/{name}",
                enabled=True,
            )
        )
        await session.execute(
            insert(Review).values(
                id=review_id,
                user_id=user_id,
                repo_id=repo_id,
                github_pr_number=88,
                head_sha="dupheadsha",
                status="pending",
            )
        )
        await session.commit()

    secret = "test-webhook-secret"
    payload = json.dumps(
        {
            "action": "opened",
            "pull_request": {
                "number": 88,
                "title": "feature: duplicate",
                "head": {"sha": "dupheadsha"},
                "base": {"sha": "base"},
            },
            "repository": {
                "owner": {"login": owner},
                "name": name,
                "full_name": f"{owner}/{name}",
            },
        }
    ).encode()

    with (
        patch("backend.config.settings.github_webhook_secret", secret),
        patch(
            "backend.routers.github.enqueue_analysis", new_callable=AsyncMock
        ) as enqueue,
    ):
        r = await client.post(
            "/api/github/webhook",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": _sign(payload, secret),
            },
        )

    assert r.status_code == 202
    assert r.json()["status"] == "pending"
    assert r.json()["review_id"] == str(review_id)
    enqueue.assert_not_called()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_webhook_duplicate_completed_sha_returns_existing(client):
    """Webhook redelivery for the same PR/SHA should be idempotent after completion."""
    user_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    review_id = uuid.uuid4()
    owner = f"orgdone_{uuid.uuid4().hex[:6]}"
    name = f"repodone_{uuid.uuid4().hex[:6]}"

    async with async_session_factory() as session:
        await session.execute(
            insert(User).values(
                id=user_id,
                email=f"hookdone_{uuid.uuid4().hex[:8]}@test.com",
                username=f"hookdone_{uuid.uuid4().hex[:8]}",
                hashed_password="x",
                email_verified=True,
            )
        )
        await session.execute(
            insert(Repository).values(
                id=repo_id,
                user_id=user_id,
                github_repo_owner=owner,
                github_repo_name=name,
                github_repo_url=f"https://github.com/{owner}/{name}",
                enabled=True,
            )
        )
        await session.execute(
            insert(Review).values(
                id=review_id,
                user_id=user_id,
                repo_id=repo_id,
                github_pr_number=89,
                head_sha="doneheadsha",
                status="done",
            )
        )
        await session.commit()

    secret = "test-webhook-secret"
    payload = json.dumps(
        {
            "action": "opened",
            "pull_request": {
                "number": 89,
                "title": "feature: duplicate done",
                "head": {"sha": "doneheadsha"},
                "base": {"sha": "base"},
            },
            "repository": {
                "owner": {"login": owner},
                "name": name,
                "full_name": f"{owner}/{name}",
            },
        }
    ).encode()

    with (
        patch("backend.config.settings.github_webhook_secret", secret),
        patch("backend.routers.github.enqueue_analysis", new_callable=AsyncMock) as enqueue,
    ):
        r = await client.post(
            "/api/github/webhook",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": _sign(payload, secret),
            },
        )

    assert r.status_code == 202
    assert r.json()["status"] == "done"
    assert r.json()["review_id"] == str(review_id)
    enqueue.assert_not_called()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_analyze_endpoint_queues_analysis(client, auth_headers, db_repo_id):
    r = await client.post(
        "/api/reviews",
        json={"repo_id": db_repo_id, "github_pr_number": 501},
        headers=auth_headers,
    )
    review_id = r.json()["id"]

    with patch(
        "backend.routers.reviews.enqueue_analysis", new_callable=AsyncMock
    ) as enqueue:
        r = await client.post(f"/api/reviews/{review_id}/analyze", headers=auth_headers)

    assert r.status_code == 200
    assert r.json()["status"] == "analyzing"
    enqueue.assert_called_once()
