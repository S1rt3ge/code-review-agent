"""GitHub webhook endpoint.

Receives pull_request events from GitHub, verifies the HMAC-SHA256
signature, creates a review record, and returns 202 Accepted so
the caller does not block on analysis.  Also handles GitHub App
installation and installation_repositories events to store
installation IDs on repository records.

Functions:
    github_webhook: POST /github/webhook handler.
    _handle_installation_event: Process installation lifecycle events.
"""

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.db_models import Repository, Review, User
from backend.models.schemas import WebhookPayload
from backend.services.analysis_queue import enqueue_analysis
from backend.utils.database import get_db
from backend.utils.webhooks import verify_github_signature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/github", tags=["github"])

SUPPORTED_ACTIONS = {"opened", "synchronize"}


@router.post(
    "/webhook",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=dict,
)
async def github_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Receive and process a GitHub webhook event for pull requests.

    The endpoint reads the raw body, verifies the ``X-Hub-Signature-256``
    header against the configured webhook secret, parses the payload, and
    creates a new review record with ``status='pending'``.

    Args:
        request: The incoming HTTP request (used to read raw body and headers).
        session: Async database session injected by FastAPI.

    Returns:
        Dict with ``review_id`` and ``status`` keys.

    Raises:
        HTTPException 401: If the webhook signature is missing or invalid.
        HTTPException 400: If the payload is malformed or the action is unsupported.
        HTTPException 404: If the repository is not configured in the system.
    """
    content_length = request.headers.get("content-length")
    try:
        body_size = int(content_length) if content_length else 0
    except ValueError:
        body_size = 0
    if body_size > settings.webhook_max_body_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Webhook payload is too large",
        )

    # Read raw body for signature verification
    body = await request.body()
    if len(body) > settings.webhook_max_body_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Webhook payload is too large",
        )
    event_type = request.headers.get("X-GitHub-Event", "")

    # Verify HMAC-SHA256 signature
    signature = request.headers.get("X-Hub-Signature-256")
    if not verify_github_signature(body, signature, settings.github_webhook_secret):
        logger.warning("Invalid webhook signature received")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    if event_type == "ping":
        return {"review_id": "", "status": "ignored"}

    # Handle GitHub App installation events
    if event_type in ("installation", "installation_repositories"):
        return await _handle_installation_event(body, session)

    if event_type != "pull_request":
        logger.info("Ignoring unsupported webhook event type: %s", event_type)
        return {"review_id": "", "status": "ignored"}

    # Parse payload
    try:
        payload = WebhookPayload.model_validate_json(body)
    except Exception as e:
        logger.error(f"Failed to parse webhook payload: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook payload",
        )

    # Only process supported pull_request actions
    if payload.action not in SUPPORTED_ACTIONS:
        logger.info(f"Ignoring unsupported webhook action: {payload.action}")
        return {"review_id": "", "status": "ignored"}

    # Look up repository in the database
    repo_owner = payload.repository.owner.login
    repo_name = payload.repository.name

    stmt = select(Repository).where(
        Repository.github_repo_owner == repo_owner,
        Repository.github_repo_name == repo_name,
        Repository.enabled.is_(True),
    )
    result = await session.execute(stmt)
    repositories = result.scalars().all()

    if not repositories:
        logger.warning(f"Repository not configured: {repo_owner}/{repo_name}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {repo_owner}/{repo_name} is not configured",
        )

    installation_id: int | None = None
    if payload.installation and isinstance(payload.installation, dict):
        raw_installation_id = payload.installation.get("id")
        if isinstance(raw_installation_id, int):
            installation_id = raw_installation_id

    if installation_id is not None:
        exact_matches = [
            repo
            for repo in repositories
            if repo.github_installation_id == installation_id
        ]
        if not exact_matches:
            logger.warning(
                "Repository %s/%s is configured, but no enabled row matched installation_id=%s",
                repo_owner,
                repo_name,
                installation_id,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository installation is not configured",
            )
        if len(exact_matches) > 1:
            logger.warning(
                "Multiple repository rows matched owner/name/install id %s/%s/%s; using first match",
                repo_owner,
                repo_name,
                installation_id,
            )
        repository = exact_matches[0]
    elif len(repositories) != 1:
        logger.warning(
            "Multiple repository rows matched owner/name %s/%s without installation id; ignoring webhook",
            repo_owner,
            repo_name,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository installation is not configured",
        )
    else:
        repository = repositories[0]

    # Check for duplicate review (same PR, same head SHA)
    dup_stmt = select(Review).where(
        Review.repo_id == repository.id,
        Review.github_pr_number == payload.pull_request.number,
        Review.head_sha == payload.pull_request.head.sha,
    )
    dup_result = await session.execute(dup_stmt)
    existing = dup_result.scalar_one_or_none()

    if existing is not None:
        logger.info(
            f"Duplicate review for PR #{payload.pull_request.number} "
            f"(sha={payload.pull_request.head.sha}), returning existing"
        )
        return {"review_id": str(existing.id), "status": existing.status}

    user = await session.get(User, repository.user_id)
    selected_agents = (
        user.default_agents
        if user and user.default_agents
        else ["security", "performance", "style", "logic"]
    )

    # Create review record
    review = Review(
        id=uuid.uuid4(),
        user_id=repository.user_id,
        repo_id=repository.id,
        github_pr_number=payload.pull_request.number,
        github_pr_title=payload.pull_request.title,
        head_sha=payload.pull_request.head.sha,
        base_sha=payload.pull_request.base.sha,
        status="pending",
        selected_agents=selected_agents,
    )
    session.add(review)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        dup_result = await session.execute(dup_stmt)
        existing = dup_result.scalar_one_or_none()
        if existing is not None:
            logger.info(
                "Concurrent duplicate review detected for PR #%s sha=%s",
                payload.pull_request.number,
                payload.pull_request.head.sha,
            )
            return {"review_id": str(existing.id), "status": existing.status}
        raise

    logger.info(
        f"Created review {review.id} for "
        f"{repo_owner}/{repo_name} PR #{payload.pull_request.number}"
    )

    # Kick off analysis in the background; response returns immediately.
    await enqueue_analysis(review.id, session=session)

    return {"review_id": str(review.id), "status": "pending"}


# ---------------------------------------------------------------------------
# Installation event helpers
# ---------------------------------------------------------------------------


async def _handle_installation_event(
    body: bytes, session: AsyncSession
) -> dict[str, str]:
    """Process GitHub App installation and installation_repositories events.

    For ``installation`` with ``action=created``, iterates over the
    ``repositories`` list and upserts each one, setting the
    ``github_installation_id``.

    For ``installation_repositories`` with ``action=added``, does the same
    for ``repositories_added``.  With ``action=removed``, disables
    (``enabled=False``) each repository in ``repositories_removed``.

    Args:
        body: Raw request body bytes.
        session: Async database session.

    Returns:
        ``{"status": "ok"}`` regardless of outcome.
    """
    try:
        payload = json.loads(body)

        installation_id: int = payload["installation"]["id"]
        account_login: str = payload["installation"]["account"]["login"]
        action: str = payload.get("action", "")

        repos_to_upsert: list[dict] = []
        repos_to_disable: list[dict] = []

        if action == "created" and "repositories" in payload:
            repos_to_upsert = payload["repositories"] or []
        elif action == "added" and "repositories_added" in payload:
            repos_to_upsert = payload["repositories_added"] or []
        elif action == "removed" and "repositories_removed" in payload:
            repos_to_disable = payload["repositories_removed"] or []

        # Upsert repositories (set installation_id, re-enable if disabled)
        for repo_info in repos_to_upsert:
            full_name: str = repo_info.get("full_name", "")
            if "/" not in full_name:
                continue
            owner, name = full_name.split("/", 1)

            stmt = select(Repository).where(
                Repository.github_repo_owner == owner,
                Repository.github_repo_name == name,
            )
            result = await session.execute(stmt)
            repos = result.scalars().all()

            if repos:
                for repo in repos:
                    repo.github_installation_id = installation_id
                    repo.enabled = True
                logger.info(
                    "Updated installation_id=%s on %s for %d repository row(s)",
                    installation_id,
                    full_name,
                    len(repos),
                )
            else:
                logger.info(f"Skipping {full_name}: not registered by any user")

        # Disable removed repositories
        for repo_info in repos_to_disable:
            full_name = repo_info.get("full_name", "")
            if "/" not in full_name:
                continue
            owner, name = full_name.split("/", 1)

            stmt = select(Repository).where(
                Repository.github_repo_owner == owner,
                Repository.github_repo_name == name,
            )
            result = await session.execute(stmt)
            repos = result.scalars().all()

            for repo in repos:
                if repo.github_installation_id == installation_id:
                    repo.enabled = False
                    logger.info(
                        f"Disabled repository {full_name} (removed from installation)"
                    )

        await session.flush()
        logger.info(
            f"Processed installation event action={action} "
            f"account={account_login} installation_id={installation_id}"
        )

    except Exception as exc:
        logger.error(f"Failed to process installation event: {exc}", exc_info=True)

    return {"status": "ok"}
