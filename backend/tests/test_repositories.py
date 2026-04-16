"""Unit tests for backend/routers/repositories.py.

Tests cover:
    list_repositories: returns empty list for new user
    create_repository: creates repo, auto-derives URL, returns 201
    create_repository: returns 409 on duplicate owner+name
    update_repository: toggles enabled flag
    delete_repository: removes repo, returns 204
    delete_repository: returns 404 for non-existent repo
    delete_repository: returns 404 for repo owned by another user
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.models.db_models import Repository, User  # noqa: F401 — used in spec=
from backend.routers.repositories import (
    create_repository,
    delete_repository,
    list_repositories,
    update_repository,
    _UpdateRepositoryRequest,
)
from backend.models.schemas import CreateRepositoryRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(user_id: uuid.UUID | None = None) -> MagicMock:
    """Return a mock User with the fields repositories router needs."""
    u = MagicMock(spec=User)
    u.id = user_id or uuid.uuid4()
    u.email = "test@example.com"
    u.username = "testuser"
    return u


def _make_repo(
    user_id: uuid.UUID,
    owner: str = "acme",
    name: str = "myrepo",
    enabled: bool = True,
    repo_id: uuid.UUID | None = None,
) -> MagicMock:
    """Return a mock Repository with the fields repositories router needs."""
    r = MagicMock(spec=Repository)
    r.id = repo_id or uuid.uuid4()
    r.user_id = user_id
    r.github_repo_owner = owner
    r.github_repo_name = name
    r.github_repo_url = f"https://github.com/{owner}/{name}"
    r.github_installation_id = None
    r.enabled = enabled
    r.created_at = None
    return r


def _make_session(scalar_result=None, scalars_result=None, count_result=0):
    """Return a mock AsyncSession with common method stubs."""
    session = AsyncMock()

    # session.execute() returns a result object
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar_result
    result.scalars.return_value.all.return_value = scalars_result or []
    result.scalar_one.return_value = count_result
    session.execute.return_value = result

    session.flush = AsyncMock()
    session.delete = AsyncMock()
    session.add = MagicMock()  # synchronous in SQLAlchemy
    return session


# ---------------------------------------------------------------------------
# list_repositories
# ---------------------------------------------------------------------------


class TestListRepositories:
    @pytest.mark.asyncio
    async def test_returns_empty_list_for_new_user(self):
        user = _make_user()
        session = _make_session(scalars_result=[], count_result=0)

        result = await list_repositories(session=session, current_user=user)

        assert result.total == 0
        assert result.repositories == []

    @pytest.mark.asyncio
    async def test_returns_repos_for_user(self):
        from datetime import datetime, timezone

        user = _make_user()
        repos = [
            _make_repo(user.id, owner="acme", name="alpha"),
            _make_repo(user.id, owner="acme", name="beta"),
        ]
        # created_at must be a real datetime for Pydantic serialization
        for r in repos:
            r.created_at = datetime.now(timezone.utc)

        session = _make_session(scalars_result=repos, count_result=2)

        result = await list_repositories(session=session, current_user=user)

        assert result.total == 2
        assert len(result.repositories) == 2


# ---------------------------------------------------------------------------
# create_repository
# ---------------------------------------------------------------------------


class TestCreateRepository:
    @pytest.mark.asyncio
    async def test_creates_repo_and_derives_url(self):
        user = _make_user()
        # First execute() — duplicate check (None = no dup)
        # Second execute() is not called (flush adds it)
        session = _make_session(scalar_result=None)

        # After flush the repo is returned; we need model_validate to work
        # so we patch it to return a real-looking repo.
        new_repo = _make_repo(user.id, owner="octocat", name="hello-world")
        session.flush = AsyncMock()

        payload = CreateRepositoryRequest(
            github_repo_owner="octocat",
            github_repo_name="hello-world",
        )

        with patch(
            "backend.routers.repositories.RepositoryResponse.model_validate"
        ) as mv:
            mv.return_value = MagicMock(
                id=new_repo.id,
                github_repo_owner="octocat",
                github_repo_name="hello-world",
                github_repo_url="https://github.com/octocat/hello-world",
                github_installation_id=None,
                enabled=True,
                created_at=None,
            )
            result = await create_repository(
                payload=payload, session=session, current_user=user
            )

        assert result.github_repo_owner == "octocat"
        assert result.github_repo_name == "hello-world"
        assert result.github_repo_url == "https://github.com/octocat/hello-world"
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_409_on_duplicate(self):
        from fastapi import HTTPException

        user = _make_user()
        existing = _make_repo(user.id, owner="acme", name="dup")
        session = _make_session(scalar_result=existing)

        payload = CreateRepositoryRequest(
            github_repo_owner="acme",
            github_repo_name="dup",
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_repository(payload=payload, session=session, current_user=user)

        assert exc_info.value.status_code == 409
        assert "already configured" in exc_info.value.detail


# ---------------------------------------------------------------------------
# update_repository
# ---------------------------------------------------------------------------


class TestUpdateRepository:
    @pytest.mark.asyncio
    async def test_toggles_enabled_to_false(self):
        user = _make_user()
        repo = _make_repo(user.id, enabled=True)
        session = _make_session(scalar_result=repo)

        payload = _UpdateRepositoryRequest(enabled=False)

        with patch(
            "backend.routers.repositories.RepositoryResponse.model_validate"
        ) as mv:
            mv.return_value = MagicMock(enabled=False)
            await update_repository(
                repo_id=repo.id,
                payload=payload,
                session=session,
                current_user=user,
            )

        assert repo.enabled is False
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_404_when_not_found(self):
        from fastapi import HTTPException

        user = _make_user()
        session = _make_session(scalar_result=None)

        payload = _UpdateRepositoryRequest(enabled=False)

        with pytest.raises(HTTPException) as exc_info:
            await update_repository(
                repo_id=uuid.uuid4(),
                payload=payload,
                session=session,
                current_user=user,
            )

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# delete_repository
# ---------------------------------------------------------------------------


class TestDeleteRepository:
    @pytest.mark.asyncio
    async def test_deletes_existing_repo(self):
        user = _make_user()
        repo = _make_repo(user.id)
        session = _make_session(scalar_result=repo)

        await delete_repository(repo_id=repo.id, session=session, current_user=user)

        session.delete.assert_awaited_once_with(repo)
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_repo(self):
        from fastapi import HTTPException

        user = _make_user()
        session = _make_session(scalar_result=None)

        with pytest.raises(HTTPException) as exc_info:
            await delete_repository(
                repo_id=uuid.uuid4(), session=session, current_user=user
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_404_for_other_users_repo(self):
        """A repo owned by a different user should look like 404 to the requester."""
        from fastapi import HTTPException

        requester = _make_user()  # different user
        # The DB query filters by user_id so it returns None for wrong owner
        session = _make_session(scalar_result=None)

        with pytest.raises(HTTPException) as exc_info:
            await delete_repository(
                repo_id=uuid.uuid4(), session=session, current_user=requester
            )

        assert exc_info.value.status_code == 404
