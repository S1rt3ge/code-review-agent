"""Tests for backend/services/github_api.py.

Covers:
    _normalize_private_key: newline escaping
    GitHubApiClient._get_installation_token: caching + refresh
    GitHubApiClient.get_pr_files: pagination logic
    GitHubApiClient.post_pr_comment: response parsing
    GitHubApiClient.update_pr_comment: PATCH call
    get_github_client: factory None-guard
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.github_api import (
    GitHubApiClient,
    _CachedToken,
    _normalize_private_key,
    get_github_client,
)


# ---------------------------------------------------------------------------
# _normalize_private_key
# ---------------------------------------------------------------------------


def test_normalize_private_key_replaces_escaped_newlines():
    key = "-----BEGIN RSA PRIVATE KEY-----\\nABC\\nDEF\\n-----END RSA PRIVATE KEY-----"
    result = _normalize_private_key(key)
    assert "\\n" not in result
    assert "\n" in result


def test_normalize_private_key_leaves_real_newlines_intact():
    key = "-----BEGIN\\nRSA-----\nABC\n-----END-----"
    result = _normalize_private_key(key)
    # \\n replaced, real \n kept
    assert result == "-----BEGIN\nRSA-----\nABC\n-----END-----"


# ---------------------------------------------------------------------------
# Token caching
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    GitHubApiClient._token_cache.clear()
    return GitHubApiClient(app_id=123, private_key="key")


@pytest.mark.asyncio
async def test_get_installation_token_uses_cache(client):
    """Second call must not make an HTTP request when token is fresh."""
    future_expiry = time.time() + 7200  # 2 hours from now
    client._token_cache[42] = _CachedToken(
        token="cached-token", expires_at=future_expiry
    )

    with patch.object(client, "_make_app_jwt", return_value="jwt"):
        token = await client._get_installation_token(42)

    assert token == "cached-token"


@pytest.mark.asyncio
async def test_get_installation_token_refreshes_near_expiry(client):
    """Token within the 5-min buffer must be refreshed."""
    near_expiry = time.time() + 200  # less than TOKEN_EXPIRY_BUFFER (300)
    client._token_cache[42] = _CachedToken(token="old-token", expires_at=near_expiry)

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"token": "new-token"}
    mock_resp.raise_for_status = MagicMock()

    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.post = AsyncMock(return_value=mock_resp)

    with patch("backend.services.github_api.httpx.AsyncClient", return_value=mock_http):
        with patch.object(client, "_make_app_jwt", return_value="jwt"):
            token = await client._get_installation_token(42)

    assert token == "new-token"
    assert client._token_cache[42].token == "new-token"


# ---------------------------------------------------------------------------
# get_pr_files
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_pr_files_single_page(client):
    """Single page of results (< 100 files) terminates pagination."""
    raw_files = [
        {
            "filename": "app.py",
            "status": "modified",
            "additions": 5,
            "deletions": 2,
            "patch": "@@ -1,2 +1,5 @@\n line1\n+added",
        }
    ]
    mock_resp = MagicMock()
    mock_resp.json.return_value = raw_files
    mock_resp.raise_for_status = MagicMock()

    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.get = AsyncMock(return_value=mock_resp)

    with patch("backend.services.github_api.httpx.AsyncClient", return_value=mock_http):
        with patch.object(
            client, "_get_installation_token", AsyncMock(return_value="tok")
        ):
            files = await client.get_pr_files("owner", "repo", 1, 42)

    assert len(files) == 1
    assert files[0].filename == "app.py"
    assert files[0].patch is not None
    mock_http.get.assert_called_once()


@pytest.mark.asyncio
async def test_get_pr_files_paginates_when_full_page(client):
    """If the first page returns exactly 100 items, a second request is made."""
    page1 = [
        {"filename": f"f{i}.py", "status": "modified", "additions": 1, "deletions": 0}
        for i in range(100)
    ]
    page2: list = []

    mock_resp1 = MagicMock()
    mock_resp1.json.return_value = page1
    mock_resp1.raise_for_status = MagicMock()

    mock_resp2 = MagicMock()
    mock_resp2.json.return_value = page2
    mock_resp2.raise_for_status = MagicMock()

    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.get = AsyncMock(side_effect=[mock_resp1, mock_resp2])

    with patch("backend.services.github_api.httpx.AsyncClient", return_value=mock_http):
        with patch.object(
            client, "_get_installation_token", AsyncMock(return_value="tok")
        ):
            files = await client.get_pr_files("owner", "repo", 7, 42)

    assert len(files) == 100
    assert mock_http.get.call_count == 2


@pytest.mark.asyncio
async def test_get_pr_files_missing_patch_becomes_none(client):
    """Files without a 'patch' key (e.g. binary) get patch=None."""
    raw_files = [
        {"filename": "image.png", "status": "added", "additions": 0, "deletions": 0}
    ]
    mock_resp = MagicMock()
    mock_resp.json.return_value = raw_files
    mock_resp.raise_for_status = MagicMock()

    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.get = AsyncMock(return_value=mock_resp)

    with patch("backend.services.github_api.httpx.AsyncClient", return_value=mock_http):
        with patch.object(
            client, "_get_installation_token", AsyncMock(return_value="tok")
        ):
            files = await client.get_pr_files("owner", "repo", 2, 42)

    assert files[0].patch is None


# ---------------------------------------------------------------------------
# post_pr_comment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_pr_comment_returns_id_and_url(client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": 999, "html_url": "https://github.com/c/999"}
    mock_resp.raise_for_status = MagicMock()

    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.post = AsyncMock(return_value=mock_resp)

    with patch("backend.services.github_api.httpx.AsyncClient", return_value=mock_http):
        with patch.object(
            client, "_get_installation_token", AsyncMock(return_value="tok")
        ):
            result = await client.post_pr_comment("owner", "repo", 1, "body text", 42)

    assert result == {"id": 999, "url": "https://github.com/c/999"}


# ---------------------------------------------------------------------------
# update_pr_comment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_pr_comment_sends_patch(client):
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()

    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.patch = AsyncMock(return_value=mock_resp)

    with patch("backend.services.github_api.httpx.AsyncClient", return_value=mock_http):
        with patch.object(
            client, "_get_installation_token", AsyncMock(return_value="tok")
        ):
            await client.update_pr_comment("owner", "repo", 777, "new body", 42)

    mock_http.patch.assert_called_once()
    call_kwargs = mock_http.patch.call_args
    assert call_kwargs.kwargs["json"] == {"body": "new body"}


# ---------------------------------------------------------------------------
# get_github_client factory
# ---------------------------------------------------------------------------


def test_get_github_client_returns_none_when_unconfigured():
    with patch("backend.services.github_api.settings") as mock_settings:
        mock_settings.github_app_id = None
        mock_settings.github_app_private_key = None
        assert get_github_client() is None


def test_get_github_client_returns_client_when_configured():
    with patch("backend.services.github_api.settings") as mock_settings:
        mock_settings.github_app_id = 1
        mock_settings.github_app_private_key = "key"
        result = get_github_client()
        assert isinstance(result, GitHubApiClient)
