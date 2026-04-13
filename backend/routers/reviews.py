"""Review management endpoints.

Provides CRUD operations for code reviews, analysis triggering, and
PR comment posting.

Functions:
    list_reviews: GET /reviews -- paginated review list.
    create_review: POST /reviews -- manually create a review.
    get_review: GET /reviews/{review_id} -- single review with findings.
    analyze_review: POST /reviews/{review_id}/analyze -- start analysis.
    post_comment: POST /reviews/{review_id}/post-comment -- post to GitHub PR.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models.db_models import Finding, Review
from backend.models.schemas import (
    AnalyzeResponse,
    CreateReviewRequest,
    PostCommentRequest,
    PostCommentResponse,
    ReviewListItem,
    ReviewListResponse,
    ReviewResponse,
)
from backend.utils.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reviews", tags=["reviews"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_PAGE_LIMIT = 100
DEFAULT_PAGE_LIMIT = 20

# TODO(phase-1.2): Replace with real user from JWT auth dependency.
PLACEHOLDER_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=ReviewListResponse)
async def list_reviews(
    session: AsyncSession = Depends(get_db),
    repo_id: uuid.UUID | None = Query(default=None, description="Filter by repository"),
    review_status: str | None = Query(
        default=None,
        alias="status",
        description="Filter by status (pending, analyzing, done, error)",
    ),
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> ReviewListResponse:
    """List reviews with optional filters and pagination.

    Args:
        session: Async database session.
        repo_id: Optional repository UUID filter.
        review_status: Optional status filter.
        limit: Page size (1-100, default 20).
        offset: Number of records to skip.

    Returns:
        Paginated list of review items with total count.
    """
    # Build base query
    stmt = select(Review).order_by(Review.created_at.desc())
    count_stmt = select(func.count(Review.id))

    # Apply filters
    if repo_id is not None:
        stmt = stmt.where(Review.repo_id == repo_id)
        count_stmt = count_stmt.where(Review.repo_id == repo_id)

    if review_status is not None:
        stmt = stmt.where(Review.status == review_status)
        count_stmt = count_stmt.where(Review.status == review_status)

    # Total count
    total_result = await session.execute(count_stmt)
    total = total_result.scalar_one()

    # Paginate
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    reviews = result.scalars().all()

    return ReviewListResponse(
        reviews=[ReviewListItem.model_validate(r) for r in reviews],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ReviewResponse)
async def create_review(
    payload: CreateReviewRequest,
    session: AsyncSession = Depends(get_db),
) -> ReviewResponse:
    """Create a review manually (not via webhook).

    Args:
        payload: Review creation request with repo, PR number, and agents.
        session: Async database session.

    Returns:
        The newly created review.
    """
    review = Review(
        id=uuid.uuid4(),
        user_id=PLACEHOLDER_USER_ID,
        repo_id=payload.repo_id,
        github_pr_number=payload.github_pr_number,
        status="pending",
        selected_agents=payload.selected_agents,
    )
    session.add(review)
    await session.flush()

    logger.info(f"Manually created review {review.id} for PR #{payload.github_pr_number}")

    return ReviewResponse.model_validate(review)


@router.get("/{review_id}", response_model=ReviewResponse)
async def get_review(
    review_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> ReviewResponse:
    """Get a single review with its findings and agent executions.

    Args:
        review_id: UUID of the review.
        session: Async database session.

    Returns:
        Full review including findings and agent execution details.

    Raises:
        HTTPException 404: If the review does not exist.
    """
    stmt = (
        select(Review)
        .where(Review.id == review_id)
        .options(
            selectinload(Review.findings),
            selectinload(Review.agent_executions),
        )
    )
    result = await session.execute(stmt)
    review = result.scalar_one_or_none()

    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found",
        )

    return ReviewResponse.model_validate(review)


@router.post("/{review_id}/analyze", response_model=AnalyzeResponse)
async def analyze_review(
    review_id: uuid.UUID,
    force_agents: str | None = Query(
        default=None,
        description="Comma-separated agent names to override defaults",
    ),
    session: AsyncSession = Depends(get_db),
) -> AnalyzeResponse:
    """Trigger analysis for a pending review.

    Changes the review status to ``analyzing`` and (in Phase 1.2+) queues
    the LangGraph orchestrator to process the code diff.

    Args:
        review_id: UUID of the review to analyze.
        force_agents: Optional comma-separated agent override.
        session: Async database session.

    Returns:
        Review id and new status.

    Raises:
        HTTPException 404: If the review does not exist.
        HTTPException 409: If the review is already being analyzed or is done.
    """
    review = await session.get(Review, review_id)

    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found",
        )

    if review.status not in ("pending", "error"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Review is already in status '{review.status}' and cannot be re-analyzed",
        )

    # Override agents if requested
    if force_agents:
        review.selected_agents = [a.strip() for a in force_agents.split(",") if a.strip()]

    review.status = "analyzing"
    await session.flush()

    logger.info(f"Analysis started for review {review.id}")

    # TODO(phase-1.2): Queue async LangGraph orchestrator here.

    return AnalyzeResponse(review_id=review.id, status="analyzing")


@router.post("/{review_id}/post-comment", response_model=PostCommentResponse)
async def post_comment(
    review_id: uuid.UUID,
    payload: PostCommentRequest,
    session: AsyncSession = Depends(get_db),
) -> PostCommentResponse:
    """Post review findings as a GitHub PR comment.

    Args:
        review_id: UUID of the review whose findings to post.
        payload: Comment formatting options.
        session: Async database session.

    Returns:
        GitHub comment id, URL, and timestamp.

    Raises:
        HTTPException 404: If the review does not exist.
        HTTPException 400: If the review has no findings or is not done.
    """
    stmt = (
        select(Review)
        .where(Review.id == review_id)
        .options(selectinload(Review.findings))
    )
    result = await session.execute(stmt)
    review = result.scalar_one_or_none()

    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found",
        )

    if review.status != "done":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot post comment: review status is '{review.status}', expected 'done'",
        )

    if not review.findings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Review has no findings to post",
        )

    # TODO(phase-1.2): Call GitHub API to post the actual comment.
    logger.info(f"Post-comment requested for review {review.id} (not yet implemented)")

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="GitHub comment posting will be available in Phase 1.2",
    )
