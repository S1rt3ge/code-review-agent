"""GitHub API client for fetching PR diffs and posting comments.

Uses GitHub App authentication (JWT → installation access token).
Tokens are cached in memory to avoid redundant API calls.

Classes:
    PullRequestFile: Single changed file in a pull request.
    GitHubApiClient: Async client for GitHub API operations.

Functions:
    get_github_client: Factory returning a configured client or None.
"""

import logging
import time
from dataclasses import dataclass

import httpx
from jose import jwt

from backend.config import settings

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
GITHUB_API_TIMEOUT = 10  # seconds per backend rules
TOKEN_EXPIRY_BUFFER = 300  # refresh 5 min before expiry


@dataclass
class PullRequestFile:
    """A single file changed in a pull request."""

    filename: str
    status: str  # added | modified | removed | renamed
    additions: int
    deletions: int
    patch: str | None = None  # unified diff; None for binary files


@dataclass
class _CachedToken:
    token: str
    expires_at: float  # unix timestamp


def _normalize_private_key(key: str) -> str:
    """Replace escaped newlines so PEM keys stored in .env work correctly."""
    return key.replace("\\n", "\n")


class GitHubApiClient:
    """Async GitHub API client that authenticates via GitHub App.

    Call ``get_pr_files`` to fetch changed files for a PR and
    ``post_pr_comment`` / ``update_pr_comment`` to manage comments.
    """

    # Shared token cache across instances (keyed by installation_id).
    _token_cache: dict[int, _CachedToken] = {}

    def __init__(self, app_id: int, private_key: str) -> None:
        self._app_id = app_id
        self._private_key = _normalize_private_key(private_key)

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _make_app_jwt(self) -> str:
        """Create a short-lived JWT signed with the GitHub App private key.

        Returns:
            Signed RS256 JWT string valid for ~9 minutes.
        """
        now = int(time.time())
        payload = {
            "iat": now - 60,   # 60s clock-skew tolerance
            "exp": now + 540,  # 9 minutes
            "iss": str(self._app_id),
        }
        return jwt.encode(payload, self._private_key, algorithm="RS256")

    async def _get_installation_token(self, installation_id: int) -> str:
        """Return a valid installation access token, refreshing if needed.

        Args:
            installation_id: GitHub App installation ID.

        Returns:
            Access token string.

        Raises:
            httpx.HTTPStatusError: If GitHub returns an error response.
        """
        now = time.time()
        cached = self._token_cache.get(installation_id)
        if cached and cached.expires_at - TOKEN_EXPIRY_BUFFER > now:
            return cached.token

        url = f"{GITHUB_API_BASE}/app/installations/{installation_id}/access_tokens"
        async with httpx.AsyncClient(timeout=GITHUB_API_TIMEOUT) as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {self._make_app_jwt()}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            resp.raise_for_status()

        token: str = resp.json()["token"]
        self._token_cache[installation_id] = _CachedToken(
            token=token, expires_at=now + 3600
        )
        logger.debug("Refreshed installation token for installation %d", installation_id)
        return token

    # ------------------------------------------------------------------
    # PR file diff
    # ------------------------------------------------------------------

    async def get_pr_files(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        installation_id: int,
    ) -> list[PullRequestFile]:
        """Fetch all files changed in a pull request (paginated).

        Args:
            owner: Repository owner login.
            repo: Repository name.
            pr_number: Pull request number.
            installation_id: GitHub App installation ID.

        Returns:
            List of PullRequestFile with patch strings where available.

        Raises:
            httpx.HTTPStatusError: On GitHub API errors.
        """
        token = await self._get_installation_token(installation_id)
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/files"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        files: list[PullRequestFile] = []
        page = 1
        async with httpx.AsyncClient(timeout=GITHUB_API_TIMEOUT) as client:
            while True:
                resp = await client.get(
                    url, headers=headers, params={"per_page": 100, "page": page}
                )
                resp.raise_for_status()
                batch: list[dict] = resp.json()
                if not batch:
                    break
                for f in batch:
                    files.append(PullRequestFile(
                        filename=f["filename"],
                        status=f["status"],
                        additions=f.get("additions", 0),
                        deletions=f.get("deletions", 0),
                        patch=f.get("patch"),
                    ))
                if len(batch) < 100:
                    break
                page += 1

        logger.info("Fetched %d files for %s/%s#%d", len(files), owner, repo, pr_number)
        return files

    # ------------------------------------------------------------------
    # PR comments
    # ------------------------------------------------------------------

    async def post_pr_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
        installation_id: int,
    ) -> dict[str, int | str]:
        """Post a new comment on a pull request.

        Args:
            owner: Repository owner login.
            repo: Repository name.
            pr_number: Pull request number.
            body: Markdown-formatted comment text.
            installation_id: GitHub App installation ID.

        Returns:
            Dict with ``id`` (int) and ``url`` (str) of the new comment.

        Raises:
            httpx.HTTPStatusError: On GitHub API errors.
        """
        token = await self._get_installation_token(installation_id)
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{pr_number}/comments"
        async with httpx.AsyncClient(timeout=GITHUB_API_TIMEOUT) as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                json={"body": body},
            )
            resp.raise_for_status()

        data: dict = resp.json()
        logger.info("Posted comment %d to %s/%s#%d", data["id"], owner, repo, pr_number)
        return {"id": data["id"], "url": data["html_url"]}

    async def update_pr_comment(
        self,
        owner: str,
        repo: str,
        comment_id: int,
        body: str,
        installation_id: int,
    ) -> None:
        """Update an existing PR comment (e.g. after re-analysis).

        Args:
            owner: Repository owner login.
            repo: Repository name.
            comment_id: GitHub comment ID to patch.
            body: New markdown-formatted comment text.
            installation_id: GitHub App installation ID.

        Raises:
            httpx.HTTPStatusError: On GitHub API errors.
        """
        token = await self._get_installation_token(installation_id)
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/comments/{comment_id}"
        async with httpx.AsyncClient(timeout=GITHUB_API_TIMEOUT) as client:
            resp = await client.patch(
                url,
                headers={
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                json={"body": body},
            )
            resp.raise_for_status()

        logger.info("Updated comment %d on %s/%s", comment_id, owner, repo)


def get_github_client() -> GitHubApiClient | None:
    """Return a configured GitHubApiClient, or None if credentials are missing.

    Returns:
        GitHubApiClient if ``GITHUB_APP_ID`` and ``GITHUB_APP_PRIVATE_KEY``
        are set, otherwise None.
    """
    if not settings.github_app_id or not settings.github_app_private_key:
        return None
    return GitHubApiClient(
        app_id=settings.github_app_id,
        private_key=settings.github_app_private_key,
    )
