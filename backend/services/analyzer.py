"""Background analysis task that drives a full review cycle.

Fetches the PR diff from GitHub, extracts code chunks, runs them through
the LangGraph orchestrator, persists findings, and posts a GitHub PR comment
when analysis is complete.

Functions:
    run_analysis: Entry point for the background task.
    _build_comment_body: Format findings into a PR comment markdown string.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from backend.agents.orchestrator import run_graph
from backend.services.ws_manager import ws_manager
from backend.models.db_models import AgentExecution, Finding, Repository, Review, User
from backend.services.code_extractor import CodeChunk, extract_chunks
from backend.services.github_api import GitHubApiClient, get_github_client
from backend.services.pr_commenter import build_comment
from backend.services.result_aggregator import aggregate
from backend.utils.crypto import decrypt_value
from backend.utils.database import async_session_factory

logger = logging.getLogger(__name__)


def _try_decrypt_key(ciphertext: str | None) -> str | None:
    """Decrypt a stored API key, returning None on any failure."""
    if not ciphertext:
        return None
    try:
        return decrypt_value(ciphertext)
    except Exception:
        return None



# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def run_analysis(review_id: uuid.UUID) -> None:
    """Run a full analysis cycle for the given review in the background.

    Creates its own database session (independent of the request session)
    so it can run after the HTTP response has been sent.

    Steps:
    1. Load review + repository from DB.
    2. Fetch PR files from GitHub API.
    3. Extract code chunks from unified diffs.
    4. Run orchestrator on each chunk and collect findings.
    5. Persist findings and agent execution records.
    6. Update review status to ``done`` (or ``error`` on failure).
    7. Post PR comment if GitHub client is available.

    Args:
        review_id: UUID of the Review record to process.
    """
    async with async_session_factory() as session:
        try:
            await _run_analysis_inner(session, review_id)
            await session.commit()
        except Exception as exc:
            await session.rollback()
            logger.error(
                "Analysis failed for review %s: %s",
                review_id,
                exc,
                exc_info=True,
            )
            # Attempt to persist the error status.
            await _mark_error(review_id, str(exc))


async def _run_analysis_inner(session: AsyncSession, review_id: uuid.UUID) -> None:
    """Inner analysis logic that runs within a managed session.

    Args:
        session: Async database session.
        review_id: UUID of the review.

    Raises:
        ValueError: If review or repository is not found.
        Exception: Propagated from GitHub API or orchestrator calls.
    """
    # ── 1. Load review + repository ──────────────────────────────────────────
    stmt = (
        select(Review)
        .where(Review.id == review_id)
        .options(selectinload(Review.findings), selectinload(Review.agent_executions))
    )
    result = await session.execute(stmt)
    review = result.scalar_one_or_none()

    if review is None:
        raise ValueError(f"Review {review_id} not found")

    repo_result = await session.get(Repository, review.repo_id)
    if repo_result is None:
        raise ValueError(f"Repository {review.repo_id} not found for review {review_id}")

    logger.info(
        "Starting analysis for review %s (%s/%s #%d)",
        review_id,
        repo_result.github_repo_owner,
        repo_result.github_repo_name,
        review.github_pr_number,
    )

    # ── 2. Fetch PR files ─────────────────────────────────────────────────────
    github_client = get_github_client()
    pr_files = []

    if github_client and repo_result.github_installation_id:
        pr_files = await github_client.get_pr_files(
            owner=repo_result.github_repo_owner,
            repo=repo_result.github_repo_name,
            pr_number=review.github_pr_number,
            installation_id=repo_result.github_installation_id,
        )
    else:
        logger.warning(
            "GitHub client not configured; skipping file fetch for review %s",
            review_id,
        )

    # ── 3. Extract code chunks ─────────────────────────────────────────────────
    chunks = extract_chunks(pr_files)
    logger.info("Extracted %d chunks for review %s", len(chunks), review_id)

    # ── 4. Run orchestrator ────────────────────────────────────────────────────
    agents = review.selected_agents or ["security", "performance", "style", "logic"]

    # Resolve user API keys for LLM selection.
    user = await session.get(User, review.user_id)
    api_key_claude: str | None = None
    api_key_gpt: str | None = None
    ollama_enabled = False
    ollama_host: str | None = None

    lm_preference = "auto"
    if user:
        api_key_claude = _try_decrypt_key(user.api_key_claude)
        api_key_gpt = _try_decrypt_key(user.api_key_gpt)
        ollama_enabled = user.ollama_enabled
        ollama_host = user.ollama_host
        lm_preference = user.lm_preference or "auto"

    async def _on_progress(agent_name: str, status: str) -> None:
        await ws_manager.broadcast(
            str(review_id),
            {"agent_name": agent_name, "status": status},
        )

    all_findings, agent_results = await run_graph(
        review_id=review_id,
        chunks=chunks,
        agents=agents,
        api_key_claude=api_key_claude,
        api_key_gpt=api_key_gpt,
        ollama_enabled=ollama_enabled,
        ollama_host=ollama_host,
        llm_preference=lm_preference,
        on_progress=_on_progress,
    )

    # ── 4b. Deduplicate and rank findings ─────────────────────────────────────
    all_findings = aggregate(all_findings)

    # ── 5. Persist findings and agent execution records ────────────────────────
    now = datetime.now(timezone.utc)
    total_tokens_in = 0
    total_tokens_out = 0

    for agent_name, result in agent_results.items():
        exec_record = AgentExecution(
            id=uuid.uuid4(),
            review_id=review_id,
            agent_name=agent_name,
            status=result["status"],
            started_at=result.get("started_at"),
            completed_at=result.get("completed_at"),
            tokens_input=result.get("tokens_input", 0),
            tokens_output=result.get("tokens_output", 0),
            findings_count=result.get("findings_count", 0),
            error_message=result.get("error_message"),
        )
        session.add(exec_record)
        total_tokens_in += result.get("tokens_input", 0)
        total_tokens_out += result.get("tokens_output", 0)

    for f in all_findings:
        finding = Finding(
            id=uuid.uuid4(),
            review_id=review_id,
            agent_name=f["agent_name"],
            finding_type=f["finding_type"],
            severity=f["severity"],
            file_path=f["file_path"],
            line_number=f.get("line_number", 0),
            message=f["message"],
            suggestion=f.get("suggestion"),
            code_snippet=f.get("code_snippet"),
            category=f.get("category"),
            is_duplicate=f.get("is_duplicate", False),
        )
        session.add(finding)

    # ── 6. Update review record ────────────────────────────────────────────────
    review.status = "done"
    review.total_findings = len(all_findings)
    review.tokens_input = total_tokens_in
    review.tokens_output = total_tokens_out
    review.estimated_cost = _estimate_cost(total_tokens_in, total_tokens_out)
    review.completed_at = now

    await session.flush()
    logger.info(
        "Review %s completed: %d findings, %d tokens",
        review_id,
        len(all_findings),
        total_tokens_in + total_tokens_out,
    )

    # ── 7. Post PR comment ─────────────────────────────────────────────────────
    if github_client and repo_result.github_installation_id and all_findings:
        await _post_comment(
            github_client=github_client,
            session=session,
            review=review,
            repository=repo_result,
            findings=all_findings,
            agent_results=agent_results,
        )



# ---------------------------------------------------------------------------
# PR comment formatting
# ---------------------------------------------------------------------------


async def _post_comment(
    github_client: GitHubApiClient,
    session: AsyncSession,
    review: Review,
    repository: Repository,
    findings: list[dict],
    agent_results: dict[str, dict] | None = None,
) -> None:
    """Format findings as markdown and post (or update) a GitHub PR comment.

    Args:
        github_client: Authenticated GitHub API client.
        session: Async database session for updating review record.
        review: The review ORM object to update with comment metadata.
        repository: Repository ORM object with owner/name/installation_id.
        findings: List of finding dicts from the orchestrator.
    """
    body = build_comment(
        findings=findings,
        agent_results=agent_results,
        estimated_cost=review.estimated_cost,
        pr_title=review.github_pr_title,
        head_sha=review.head_sha,
    )

    try:
        if review.pr_comment_id:
            await github_client.update_pr_comment(
                owner=repository.github_repo_owner,
                repo=repository.github_repo_name,
                comment_id=review.pr_comment_id,
                body=body,
                installation_id=repository.github_installation_id,
            )
        else:
            result = await github_client.post_pr_comment(
                owner=repository.github_repo_owner,
                repo=repository.github_repo_name,
                pr_number=review.github_pr_number,
                body=body,
                installation_id=repository.github_installation_id,
            )
            review.pr_comment_id = result["id"]

        review.pr_comment_posted = True
        await session.flush()
        logger.info("PR comment posted/updated for review %s", review.id)

    except Exception as exc:
        logger.error(
            "Failed to post PR comment for review %s: %s",
            review.id,
            exc,
            exc_info=True,
        )



# ---------------------------------------------------------------------------
# Error recovery helper
# ---------------------------------------------------------------------------


async def _mark_error(review_id: uuid.UUID, error_message: str) -> None:
    """Update a review's status to ``error`` in a new session.

    Called from the top-level error handler so a previous session rollback
    does not prevent persisting the error state.

    Args:
        review_id: UUID of the review to update.
        error_message: Human-readable description of what went wrong.
    """
    try:
        async with async_session_factory() as session:
            review = await session.get(Review, review_id)
            if review is not None:
                review.status = "error"
                review.error_message = error_message[:2000]  # Truncate to column limit
                review.completed_at = datetime.now(timezone.utc)
                await session.commit()
    except Exception as exc:
        logger.error(
            "Could not persist error status for review %s: %s",
            review_id,
            exc,
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------


def _estimate_cost(tokens_input: int, tokens_output: int) -> Decimal:
    """Rough cost estimate in USD using Claude Opus 4.6 pricing.

    This is a best-effort approximation for dashboard display. Actual costs
    depend on the LLM used per run.

    Args:
        tokens_input: Total prompt tokens consumed.
        tokens_output: Total completion tokens consumed.

    Returns:
        Estimated cost as a Decimal rounded to 4 decimal places.
    """
    # Claude Opus 4.6 approximate: $15 / 1M input, $75 / 1M output
    cost = Decimal(tokens_input) * Decimal("0.000015") + Decimal(tokens_output) * Decimal("0.000075")
    return round(cost, 4)
