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
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models.db_models import Repository, Review, User
from backend.models.schemas import (
    AnalyzeResponse,
    CreateReviewRequest,
    PostCommentRequest,
    PostCommentResponse,
    PlaygroundDemoReviewRequest,
    PlaygroundDiffReviewRequest,
    ReviewDNACriteriaPackResponse,
    ReviewDNACriterionResponse,
    ReviewPassportGateResponse,
    ReviewPassportMarkdownResponse,
    ReviewPassportRequest,
    ReviewPassportResponse,
    ReviewListItem,
    ReviewListResponse,
    ReviewResponse,
)
from backend.services.analysis_queue import enqueue_analysis
from backend.services.github_api import get_github_client
from backend.services.playground_review import DEMO_DIFF, create_playground_review
from backend.services.pr_commenter import build_comment
from backend.services.review_dna import (
    build_review_dna_criteria_pack_for_repo,
    render_review_dna_criteria_pack,
)
from backend.services.review_passport_commenter import build_passport_markdown
from backend.services.review_passport import (
    create_or_replace_review_passport,
    delete_review_passport,
    get_review_passport,
)
from backend.services.review_passport_gate import build_passport_gate
from backend.services.review_passport_summary import build_review_passport_summary
from backend.utils.auth import create_review_ws_ticket, get_current_user
from backend.utils.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reviews", tags=["reviews"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_PAGE_LIMIT = 100
DEFAULT_PAGE_LIMIT = 20
VALID_AGENTS = {"security", "performance", "style", "logic"}
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _review_dna_pack_payload() -> tuple[
    str,
    str,
    str,
    str,
    list[ReviewDNACriterionResponse],
]:
    """Load Review DNA criteria once and return reusable API/passport payload."""
    pack = build_review_dna_criteria_pack_for_repo(PROJECT_ROOT)
    spec_source_ref = f"{pack.title} ({pack.source_profile})"
    markdown = render_review_dna_criteria_pack(pack)
    criteria = [
        ReviewDNACriterionResponse(**criterion.to_dict())
        for criterion in pack.criteria
    ]
    return pack.title, pack.source_profile, spec_source_ref, markdown, criteria


def _validate_agents(agent_names: list[str]) -> list[str]:
    """Validate and normalize selected analysis agent names."""
    normalized = [agent.strip() for agent in agent_names if agent.strip()]
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one analysis agent must be selected",
        )
    invalid = sorted(set(normalized) - VALID_AGENTS)
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown agent names: {', '.join(invalid)}",
        )
    return normalized


def _review_list_item(review: Review) -> ReviewListItem:
    return ReviewListItem(
        id=review.id,
        repo_id=review.repo_id,
        github_pr_number=review.github_pr_number,
        github_pr_title=review.github_pr_title,
        status=review.status,
        total_findings=review.total_findings,
        lm_used=review.lm_used,
        created_at=review.created_at,
        completed_at=review.completed_at,
        passport=(
            build_review_passport_summary(review.passport)
            if review.passport is not None
            else None
        ),
    )


async def _get_review_for_passport(
    session: AsyncSession,
    review_id: uuid.UUID,
    current_user: User,
) -> Review:
    """Load a review for passport operations with explicit ownership handling."""
    result = await session.execute(
        select(Review)
        .where(Review.id == review_id)
        .options(selectinload(Review.findings))
    )
    review = result.scalar_one_or_none()
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found",
        )
    if review.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Review does not belong to the current user",
        )
    return review


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/review-dna/criteria-pack",
    response_model=ReviewDNACriteriaPackResponse,
)
async def get_review_dna_criteria_pack(
    current_user: User = Depends(get_current_user),
) -> ReviewDNACriteriaPackResponse:
    """Return Review DNA criteria as Review Passport-ready form input."""
    try:
        title, source_profile, spec_source_ref, markdown, criteria = (
            _review_dna_pack_payload()
        )
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Review DNA criteria unavailable: {exc}",
        ) from exc

    return ReviewDNACriteriaPackResponse(
        title=title,
        source_profile=source_profile,
        spec_source_ref=spec_source_ref,
        markdown=markdown,
        criteria=criteria,
    )


@router.get("", response_model=ReviewListResponse)
async def list_reviews(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
    # Build base query — always scoped to the authenticated user
    stmt = (
        select(Review)
        .options(selectinload(Review.passport))
        .where(Review.user_id == current_user.id)
        .order_by(Review.created_at.desc())
    )
    count_stmt = select(func.count(Review.id)).where(Review.user_id == current_user.id)

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
        reviews=[_review_list_item(r) for r in reviews],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ReviewResponse)
async def create_review(
    payload: CreateReviewRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReviewResponse:
    """Create a review manually (not via webhook).

    Args:
        payload: Review creation request with repo, PR number, and agents.
        session: Async database session.

    Returns:
        The newly created review.
    """
    repo_stmt = select(Repository).where(
        Repository.id == payload.repo_id,
        Repository.user_id == current_user.id,
    )
    repo_result = await session.execute(repo_stmt)
    repo = repo_result.scalar_one_or_none()
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    selected_agents = _validate_agents(payload.selected_agents)

    review = Review(
        id=uuid.uuid4(),
        user_id=current_user.id,
        repo_id=repo.id,
        github_pr_number=payload.github_pr_number,
        status="pending",
        selected_agents=selected_agents,
    )
    session.add(review)
    await session.flush()

    # Re-fetch with relationships so Pydantic can serialize them
    result = await session.execute(
        select(Review)
        .where(Review.id == review.id)
        .options(selectinload(Review.findings), selectinload(Review.agent_executions))
    )
    review = result.scalar_one()

    logger.info(
        f"Manually created review {review.id} for PR #{payload.github_pr_number}"
    )

    return ReviewResponse.model_validate(review)


@router.post(
    "/playground/demo",
    status_code=status.HTTP_201_CREATED,
    response_model=ReviewResponse,
)
async def create_playground_demo_review(
    payload: PlaygroundDemoReviewRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReviewResponse:
    """Create a completed local demo review without GitHub or LLM setup."""
    selected_agents = _validate_agents(payload.selected_agents)
    review = await create_playground_review(
        session,
        current_user,
        title="Local demo review",
        code_diff=DEMO_DIFF,
        selected_agents=selected_agents,
    )
    logger.info("Created local playground demo review %s", review.id)
    return ReviewResponse.model_validate(review)


@router.post(
    "/playground/diff",
    status_code=status.HTTP_201_CREATED,
    response_model=ReviewResponse,
)
async def create_playground_diff_review(
    payload: PlaygroundDiffReviewRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReviewResponse:
    """Create a completed local review from a pasted diff."""
    selected_agents = _validate_agents(payload.selected_agents)
    try:
        review = await create_playground_review(
            session,
            current_user,
            title=payload.title or "Pasted diff review",
            code_diff=payload.code_diff,
            selected_agents=selected_agents,
        )
    except OverflowError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    logger.info("Created local playground diff review %s", review.id)
    return ReviewResponse.model_validate(review)


@router.post(
    "/{review_id}/passport",
    status_code=status.HTTP_201_CREATED,
    response_model=ReviewPassportResponse,
)
async def create_review_passport(
    review_id: uuid.UUID,
    payload: ReviewPassportRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReviewPassportResponse:
    """Create or replace an evidence-backed passport for a review."""
    review = await _get_review_for_passport(session, review_id, current_user)
    try:
        passport = await create_or_replace_review_passport(
            session,
            review=review,
            current_user=current_user,
            mode=payload.mode,
            spec_source_type=payload.spec_source_type,
            spec_source_ref=payload.spec_source_ref,
            spec_input=payload.spec_input,
            code_diff=payload.code_diff,
        )
    except OverflowError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return ReviewPassportResponse.model_validate(passport)


@router.post(
    "/{review_id}/passport/review-dna",
    status_code=status.HTTP_201_CREATED,
    response_model=ReviewPassportResponse,
)
async def create_review_passport_from_review_dna(
    review_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReviewPassportResponse:
    """Create or replace a passport using the current Review DNA Criteria Pack."""
    review = await _get_review_for_passport(session, review_id, current_user)
    try:
        _, _, spec_source_ref, markdown, _ = _review_dna_pack_payload()
        passport = await create_or_replace_review_passport(
            session,
            review=review,
            current_user=current_user,
            mode="combined",
            spec_source_type="review_dna",
            spec_source_ref=spec_source_ref,
            spec_input=markdown,
            code_diff=None,
        )
    except (ValueError, OverflowError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return ReviewPassportResponse.model_validate(passport)


@router.get("/{review_id}/passport", response_model=ReviewPassportResponse)
async def get_passport(
    review_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReviewPassportResponse:
    """Return an existing Review Passport for an owned review."""
    await _get_review_for_passport(session, review_id, current_user)
    passport = await get_review_passport(session, review_id, current_user.id)
    if passport is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review passport not found",
        )
    return ReviewPassportResponse.model_validate(passport)


@router.get(
    "/{review_id}/passport/gate",
    response_model=ReviewPassportGateResponse,
)
async def get_passport_gate(
    review_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReviewPassportGateResponse:
    """Return the merge gate state derived from an existing Review Passport."""
    await _get_review_for_passport(session, review_id, current_user)
    passport = await get_review_passport(session, review_id, current_user.id)
    if passport is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review passport not found",
        )
    return ReviewPassportGateResponse.model_validate(build_passport_gate(passport))


@router.post(
    "/{review_id}/passport/gate/publish",
    response_model=ReviewPassportGateResponse,
)
async def publish_passport_gate(
    review_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReviewPassportGateResponse:
    """Publish the Review Passport verdict as a GitHub commit status."""
    review = await _get_review_for_passport(session, review_id, current_user)
    passport = await get_review_passport(session, review_id, current_user.id)
    if passport is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review passport not found",
        )

    repo = await session.get(Repository, review.repo_id)
    if repo is None or repo.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found for this review",
        )
    if repo.github_repo_url == "local://playground":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Local playground reviews cannot publish GitHub gate statuses",
        )
    if not review.head_sha:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Review head SHA is required to publish a GitHub gate status",
        )

    github_client = get_github_client()
    if github_client is None or repo.github_installation_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub App is not configured; cannot publish passport gate",
        )

    gate = build_passport_gate(passport)
    try:
        result = await github_client.post_commit_status(
            owner=repo.github_repo_owner,
            repo=repo.github_repo_name,
            sha=review.head_sha,
            state=gate["state"],
            context=gate["context"],
            description=gate["description"],
            installation_id=repo.github_installation_id,
        )
        passport.github_gate_state = gate["state"]
        passport.github_gate_url = result.get("url")
        passport.github_gate_posted_at = datetime.now(timezone.utc)
        await session.flush()
    except Exception as exc:
        logger.error(
            "GitHub passport gate publish failed for review %s: %s",
            review.id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="GitHub API error while publishing the passport gate",
        ) from exc

    logger.info("Published passport gate %s for review %s", gate["state"], review.id)
    return ReviewPassportGateResponse.model_validate(build_passport_gate(passport))


@router.get(
    "/{review_id}/passport/markdown",
    response_model=ReviewPassportMarkdownResponse,
)
async def export_passport_markdown(
    review_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReviewPassportMarkdownResponse:
    """Return a Markdown Review Passport artifact for copying or export."""
    review = await _get_review_for_passport(session, review_id, current_user)
    passport = await get_review_passport(session, review_id, current_user.id)
    if passport is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review passport not found",
        )
    return ReviewPassportMarkdownResponse(
        body=build_passport_markdown(
            passport,
            pr_title=review.github_pr_title,
            head_sha=review.head_sha,
        )
    )


@router.post(
    "/{review_id}/passport/post-comment",
    response_model=PostCommentResponse,
)
async def post_passport_comment(
    review_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PostCommentResponse:
    """Post or update the Review Passport as a GitHub PR comment."""
    review = await _get_review_for_passport(session, review_id, current_user)
    passport = await get_review_passport(session, review_id, current_user.id)
    if passport is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review passport not found",
        )

    repo = await session.get(Repository, review.repo_id)
    if repo is None or repo.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found for this review",
        )
    if repo.github_repo_url == "local://playground":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Local playground reviews cannot be posted to GitHub; copy Markdown instead",
        )

    github_client = get_github_client()
    if github_client is None or repo.github_installation_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub App is not configured; cannot post passport comment",
        )

    body = build_passport_markdown(
        passport,
        pr_title=review.github_pr_title,
        head_sha=review.head_sha,
    )

    try:
        if passport.github_comment_id:
            await github_client.update_pr_comment(
                owner=repo.github_repo_owner,
                repo=repo.github_repo_name,
                comment_id=passport.github_comment_id,
                body=body,
                installation_id=repo.github_installation_id,
            )
            comment_id = passport.github_comment_id
            url = passport.github_comment_url or (
                f"https://github.com/{repo.github_repo_owner}/{repo.github_repo_name}"
                f"/issues/{review.github_pr_number}#issuecomment-{comment_id}"
            )
        else:
            result = await github_client.post_pr_comment(
                owner=repo.github_repo_owner,
                repo=repo.github_repo_name,
                pr_number=review.github_pr_number,
                body=body,
                installation_id=repo.github_installation_id,
            )
            comment_id = int(result["id"])
            url = str(result["url"])
            passport.github_comment_id = comment_id
            passport.github_comment_url = url

        posted_at = datetime.now(timezone.utc)
        passport.github_comment_posted_at = posted_at
        await session.flush()

    except Exception as exc:
        logger.error(
            "GitHub passport comment post failed for review %s: %s",
            review.id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="GitHub API error while posting the passport comment",
        ) from exc

    logger.info("Posted passport comment %s for review %s", comment_id, review.id)
    return PostCommentResponse(comment_id=comment_id, url=url, posted_at=posted_at)


@router.delete("/{review_id}/passport", status_code=status.HTTP_204_NO_CONTENT)
async def delete_passport(
    review_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete an existing Review Passport for an owned review."""
    await _get_review_for_passport(session, review_id, current_user)
    deleted = await delete_review_passport(session, review_id, current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review passport not found",
        )


@router.get("/{review_id}", response_model=ReviewResponse)
async def get_review(
    review_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
        .where(Review.id == review_id, Review.user_id == current_user.id)
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
    current_user: User = Depends(get_current_user),
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

    if review is None or review.user_id != current_user.id:
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
        review.selected_agents = _validate_agents(force_agents.split(","))

    review.status = "analyzing"
    await session.flush()

    logger.info(f"Analysis started for review {review.id}")

    # Fire-and-forget background analysis scheduling.
    await enqueue_analysis(review.id, session=session)

    return AnalyzeResponse(review_id=review.id, status="analyzing")


@router.post("/{review_id}/ws-ticket", response_model=dict)
async def create_websocket_ticket(
    review_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Issue a short-lived ticket for the review progress WebSocket."""
    stmt = select(Review.id).where(
        Review.id == review_id,
        Review.user_id == current_user.id,
    )
    result = await session.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found",
        )
    return {"ticket": create_review_ws_ticket(current_user.id, review_id)}


@router.post("/{review_id}/post-comment", response_model=PostCommentResponse)
async def post_comment(
    review_id: uuid.UUID,
    payload: PostCommentRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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

    if review is None or review.user_id != current_user.id:
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

    # Load repository for owner / name / installation_id
    repo = await session.get(Repository, review.repo_id)
    if repo is None or repo.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found for this review",
        )

    github_client = get_github_client()
    if github_client is None or repo.github_installation_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub App is not configured; cannot post comment",
        )

    findings_dicts = [
        {
            "agent_name": f.agent_name,
            "finding_type": f.finding_type,
            "severity": f.severity,
            "file_path": f.file_path,
            "line_number": f.line_number,
            "message": f.message,
            "suggestion": f.suggestion,
            "code_snippet": f.code_snippet,
        }
        for f in review.findings
    ]

    body = build_comment(findings_dicts)

    try:
        if review.pr_comment_id:
            await github_client.update_pr_comment(
                owner=repo.github_repo_owner,
                repo=repo.github_repo_name,
                comment_id=review.pr_comment_id,
                body=body,
                installation_id=repo.github_installation_id,
            )
            comment_id = review.pr_comment_id
            url = (
                f"https://github.com/{repo.github_repo_owner}/{repo.github_repo_name}"
                f"/issues/{review.github_pr_number}#issuecomment-{comment_id}"
            )
        else:
            result = await github_client.post_pr_comment(
                owner=repo.github_repo_owner,
                repo=repo.github_repo_name,
                pr_number=review.github_pr_number,
                body=body,
                installation_id=repo.github_installation_id,
            )
            comment_id = result["id"]
            url = result["url"]
            review.pr_comment_id = comment_id

        review.pr_comment_posted = True
        await session.flush()

    except Exception as exc:
        logger.error(
            f"GitHub comment post failed for review {review.id}: {exc}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="GitHub API error while posting the PR comment",
        )

    posted_at = datetime.now(timezone.utc)
    logger.info(f"Posted comment {comment_id} for review {review.id}")
    return PostCommentResponse(comment_id=comment_id, url=url, posted_at=posted_at)
