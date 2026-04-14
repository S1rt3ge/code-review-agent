"""Repository management endpoints.

Provides CRUD operations for GitHub repositories linked to the
authenticated user's account.

Functions:
    list_repositories: GET /repositories -- list user's repositories.
    create_repository: POST /repositories -- add a new repository.
    update_repository: PATCH /repositories/{repo_id} -- toggle enabled flag.
    delete_repository: DELETE /repositories/{repo_id} -- remove a repository.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.db_models import Repository, User
from backend.models.schemas import (
    CreateRepositoryRequest,
    RepositoryListResponse,
    RepositoryResponse,
)
from backend.utils.auth import get_current_user
from backend.utils.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/repositories", tags=["repositories"])


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class _UpdateRepositoryRequest(BaseModel):
    """Body for PATCH /repositories/{repo_id}."""

    enabled: bool


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=RepositoryListResponse)
async def list_repositories(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RepositoryListResponse:
    """List all repositories belonging to the authenticated user.

    Args:
        session: Async database session.
        current_user: Authenticated user from JWT.

    Returns:
        List of repositories with total count.
    """
    stmt = (
        select(Repository)
        .where(Repository.user_id == current_user.id)
        .order_by(Repository.created_at.desc())
    )
    count_stmt = (
        select(func.count(Repository.id))
        .where(Repository.user_id == current_user.id)
    )

    result = await session.execute(stmt)
    repositories = result.scalars().all()

    total_result = await session.execute(count_stmt)
    total = total_result.scalar_one()

    return RepositoryListResponse(
        repositories=[RepositoryResponse.model_validate(r) for r in repositories],
        total=total,
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=RepositoryResponse,
)
async def create_repository(
    payload: CreateRepositoryRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RepositoryResponse:
    """Add a new GitHub repository for the authenticated user.

    The ``github_repo_url`` is derived automatically from the owner and name.

    Args:
        payload: Owner and name of the GitHub repository.
        session: Async database session.
        current_user: Authenticated user from JWT.

    Returns:
        The newly created repository record.

    Raises:
        HTTPException 409: If the user already has this owner/name pair.
    """
    # Check for duplicate
    dup_stmt = select(Repository).where(
        Repository.user_id == current_user.id,
        Repository.github_repo_owner == payload.github_repo_owner,
        Repository.github_repo_name == payload.github_repo_name,
    )
    dup_result = await session.execute(dup_stmt)
    if dup_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Repository {payload.github_repo_owner}/{payload.github_repo_name} "
                "is already configured"
            ),
        )

    repo = Repository(
        id=uuid.uuid4(),
        user_id=current_user.id,
        github_repo_owner=payload.github_repo_owner,
        github_repo_name=payload.github_repo_name,
        github_repo_url=f"https://github.com/{payload.github_repo_owner}/{payload.github_repo_name}",
        enabled=True,
    )
    session.add(repo)
    await session.flush()

    logger.info(
        f"Created repository {repo.id} "
        f"({payload.github_repo_owner}/{payload.github_repo_name}) "
        f"for user {current_user.id}"
    )

    return RepositoryResponse.model_validate(repo)


@router.patch("/{repo_id}", response_model=RepositoryResponse)
async def update_repository(
    repo_id: uuid.UUID,
    payload: _UpdateRepositoryRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RepositoryResponse:
    """Toggle the enabled flag on a repository.

    Args:
        repo_id: UUID of the repository to update.
        payload: New enabled value.
        session: Async database session.
        current_user: Authenticated user from JWT.

    Returns:
        The updated repository record.

    Raises:
        HTTPException 404: If the repository does not exist or is not owned by user.
    """
    stmt = select(Repository).where(
        Repository.id == repo_id,
        Repository.user_id == current_user.id,
    )
    result = await session.execute(stmt)
    repo = result.scalar_one_or_none()

    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    repo.enabled = payload.enabled
    await session.flush()

    logger.info(f"Repository {repo_id} enabled={payload.enabled}")

    return RepositoryResponse.model_validate(repo)


@router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_repository(
    repo_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a repository.

    Args:
        repo_id: UUID of the repository to delete.
        session: Async database session.
        current_user: Authenticated user from JWT.

    Raises:
        HTTPException 404: If the repository does not exist or is not owned by user.
    """
    stmt = select(Repository).where(
        Repository.id == repo_id,
        Repository.user_id == current_user.id,
    )
    result = await session.execute(stmt)
    repo = result.scalar_one_or_none()

    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    await session.delete(repo)
    await session.flush()

    logger.info(f"Deleted repository {repo_id} for user {current_user.id}")
