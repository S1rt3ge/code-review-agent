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
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert

from backend.main import app
from backend.models.db_models import Repository
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
        json={"email": _unique_email(), "username": f"u_{uuid.uuid4().hex[:6]}", "password": "Secret123!"},
    )
    assert r.status_code == 201
    assert "access_token" in r.json()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_register_duplicate_email_rejected(client):
    email = _unique_email()
    payload = {"email": email, "username": f"u_{uuid.uuid4().hex[:6]}", "password": "Secret123!"}
    await client.post("/api/auth/register", json=payload)
    r = await client.post("/api/auth/register", json={**payload, "username": "other"})
    assert r.status_code == 409


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_wrong_password(client):
    email = _unique_email()
    await client.post(
        "/api/auth/register",
        json={"email": email, "username": f"u_{uuid.uuid4().hex[:6]}", "password": "Correct1!"},
    )
    r = await client.post(
        "/api/auth/token",
        data={"username": email, "password": "WrongPass!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 401


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
        json={"repo_id": db_repo_id, "github_pr_number": 42, "selected_agents": ["security"]},
        headers=auth_headers,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending"
    assert body["github_pr_number"] == 42


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

    with patch("backend.routers.reviews.run_analysis", new_callable=AsyncMock):
        r = await client.post(f"/api/reviews/{review_id}/analyze", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "analyzing"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_analyze_conflict_when_already_analyzing(client, auth_headers, db_repo_id):
    r = await client.post(
        "/api/reviews",
        json={"repo_id": db_repo_id, "github_pr_number": 22},
        headers=auth_headers,
    )
    review_id = r.json()["id"]

    with patch("backend.routers.reviews.run_analysis", new_callable=AsyncMock):
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
    for key in ("total_reviews", "reviews_today", "findings_by_severity",
                "findings_by_agent", "tokens_used_this_month"):
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
        r = await client.post(
            "/api/auth/token",
            data={"username": email, "password": "Pass123!"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        return r.json()["access_token"]

    tok_a = await make_user_token()
    tok_b = await make_user_token()

    r_a = await client.get("/api/dashboard/stats", headers={"Authorization": f"Bearer {tok_a}"})
    r_b = await client.get("/api/dashboard/stats", headers={"Authorization": f"Bearer {tok_b}"})
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
    payload = json.dumps({
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
    }).encode()

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
