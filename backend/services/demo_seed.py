"""Demo data seeding for local self-hosted product demos."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.db_models import (
    AgentExecution,
    AnalysisJob,
    Finding,
    Repository,
    Review,
)

DEMO_ALLOWED_ENVS = {"development", "dev", "local", "demo", "test", "testing"}
DEMO_REPO_OWNER = "demo-org"
DEMO_REPO_NAME = "checkout-service"
DEMO_AGENTS = ["security", "performance", "style", "logic"]


def is_demo_seed_allowed(app_env: str) -> bool:
    """Return True when demo data may be seeded in this environment."""
    return app_env.lower() in DEMO_ALLOWED_ENVS


def build_demo_seed_plan(now: datetime | None = None) -> dict[str, Any]:
    """Return the deterministic repository/review data used by demo seeding."""
    now = now or datetime.now(timezone.utc)

    return {
        "repository": {
            "owner": DEMO_REPO_OWNER,
            "name": DEMO_REPO_NAME,
            "url": f"https://github.com/{DEMO_REPO_OWNER}/{DEMO_REPO_NAME}",
        },
        "reviews": [
            {
                "github_pr_number": 128,
                "github_pr_title": "Harden OAuth callback handling",
                "head_sha": "demo-auth-hardening-head",
                "base_sha": "demo-auth-hardening-base",
                "status": "done",
                "lm_used": "ollama:qwen2.5-coder:7b",
                "created_at": now - timedelta(days=2, hours=3),
                "completed_at": now - timedelta(days=2, hours=3) + timedelta(minutes=2, seconds=18),
                "findings": [
                    {
                        "agent_name": "security",
                        "finding_type": "auth_bypass",
                        "severity": "critical",
                        "file_path": "app/api/oauth.py",
                        "line_number": 88,
                        "message": "Callback token validation accepts unsigned JWTs in the fallback path.",
                        "suggestion": "Require signature verification for all callback tokens before exchanging sessions.",
                        "code_snippet": "jwt.decode(token, options={'verify_signature': False})",
                        "category": "authentication",
                    },
                    {
                        "agent_name": "logic",
                        "finding_type": "boundary_condition",
                        "severity": "high",
                        "file_path": "app/services/retry_queue.py",
                        "line_number": 142,
                        "message": "Retry attempts are checked before incrementing, allowing one extra retry after the configured limit.",
                        "suggestion": "Increment attempts before comparing against the retry limit.",
                        "code_snippet": "if job.attempts >= max_attempts:\n    mark_failed(job)\njob.attempts += 1",
                        "category": "correctness",
                    },
                    {
                        "agent_name": "performance",
                        "finding_type": "n_plus_one_query",
                        "severity": "medium",
                        "file_path": "app/repositories/orders.py",
                        "line_number": 57,
                        "message": "Order line items are loaded one order at a time in the dashboard summary.",
                        "suggestion": "Use a joined load or aggregate query for line item counts.",
                        "code_snippet": "for order in orders:\n    order.items = await load_items(order.id)",
                        "category": "database",
                    },
                    {
                        "agent_name": "style",
                        "finding_type": "error_message",
                        "severity": "low",
                        "file_path": "app/services/github.py",
                        "line_number": 31,
                        "message": "Webhook failure logs omit repository and delivery identifiers needed for support.",
                        "suggestion": "Include owner, repo, and delivery id in the structured log context.",
                        "code_snippet": "logger.warning('Invalid signature')",
                        "category": "observability",
                    },
                ],
            },
            {
                "github_pr_number": 127,
                "github_pr_title": "Speed up repository dashboard queries",
                "head_sha": "demo-dashboard-perf-head",
                "base_sha": "demo-dashboard-perf-base",
                "status": "done",
                "lm_used": "ollama:qwen2.5-coder:7b",
                "created_at": now - timedelta(days=5, hours=6),
                "completed_at": now - timedelta(days=5, hours=6) + timedelta(minutes=1, seconds=44),
                "findings": [
                    {
                        "agent_name": "performance",
                        "finding_type": "expensive_aggregation",
                        "severity": "high",
                        "file_path": "app/dashboard/stats.py",
                        "line_number": 103,
                        "message": "Monthly token totals scan all historical reviews before applying the date filter in Python.",
                        "suggestion": "Push the month filter and sum aggregation into the database query.",
                        "code_snippet": "sum(r.tokens for r in reviews if r.created_at >= month_start)",
                        "category": "database",
                    },
                    {
                        "agent_name": "logic",
                        "finding_type": "null_handling",
                        "severity": "medium",
                        "file_path": "frontend/src/pages/ReviewDetail.jsx",
                        "line_number": 205,
                        "message": "Duration rendering assumes completed_at is present for every done review.",
                        "suggestion": "Guard duration formatting when completed_at is missing from imported historical data.",
                        "code_snippet": "formatDuration(new Date(completed_at) - new Date(created_at))",
                        "category": "correctness",
                    },
                    {
                        "agent_name": "style",
                        "finding_type": "copy_clarity",
                        "severity": "info",
                        "file_path": "frontend/src/pages/Settings.jsx",
                        "line_number": 243,
                        "message": "Provider copy does not clearly state that paid API keys are bring-your-own-key.",
                        "suggestion": "Clarify that hosted providers bill the user's own account and Ollama is the local no-cost option.",
                        "code_snippet": "Keys are encrypted at rest. You only need one provider.",
                        "category": "ux",
                    },
                ],
            },
            {
                "github_pr_number": 126,
                "github_pr_title": "Polish settings form validation",
                "head_sha": "demo-clean-settings-head",
                "base_sha": "demo-clean-settings-base",
                "status": "done",
                "lm_used": "ollama:qwen2.5-coder:7b",
                "created_at": now - timedelta(days=9, hours=2),
                "completed_at": now - timedelta(days=9, hours=2) + timedelta(minutes=1, seconds=9),
                "findings": [],
            },
        ],
    }


async def seed_demo_data(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Seed deterministic demo repository, review, finding, and queue rows."""
    plan = build_demo_seed_plan(now)
    repo_spec = plan["repository"]

    repo_result = await session.execute(
        select(Repository).where(
            Repository.user_id == user_id,
            Repository.github_repo_owner == repo_spec["owner"],
            Repository.github_repo_name == repo_spec["name"],
        )
    )
    repository = repo_result.scalar_one_or_none()
    if repository is None:
        repository = Repository(
            id=uuid.uuid4(),
            user_id=user_id,
            github_repo_owner=repo_spec["owner"],
            github_repo_name=repo_spec["name"],
            github_repo_url=repo_spec["url"],
            enabled=True,
        )
        session.add(repository)
        await session.flush()
    else:
        repository.github_repo_url = repo_spec["url"]
        repository.enabled = True

    seeded_review_ids: list[uuid.UUID] = []
    findings_created = 0
    agent_executions_created = 0
    analysis_jobs_created = 0

    for review_spec in plan["reviews"]:
        review_result = await session.execute(
            select(Review).where(
                Review.repo_id == repository.id,
                Review.head_sha == review_spec["head_sha"],
            )
        )
        review = review_result.scalar_one_or_none()
        if review is None:
            review = Review(
                id=uuid.uuid4(),
                user_id=user_id,
                repo_id=repository.id,
                github_pr_number=review_spec["github_pr_number"],
                head_sha=review_spec["head_sha"],
            )
            session.add(review)

        review.github_pr_number = review_spec["github_pr_number"]
        review.github_pr_title = review_spec["github_pr_title"]
        review.base_sha = review_spec["base_sha"]
        review.status = review_spec["status"]
        review.error_message = None
        review.selected_agents = DEMO_AGENTS
        review.lm_used = review_spec["lm_used"]
        review.pr_comment_id = None
        review.pr_comment_posted = False
        review.created_at = review_spec["created_at"]
        review.completed_at = review_spec["completed_at"]
        review.total_findings = len(review_spec["findings"])

        await session.flush()

        await session.execute(delete(Finding).where(Finding.review_id == review.id))
        await session.execute(
            delete(AgentExecution).where(AgentExecution.review_id == review.id)
        )
        await session.execute(delete(AnalysisJob).where(AnalysisJob.review_id == review.id))
        await session.flush()

        counts_by_agent = {
            agent: sum(
                1
                for finding in review_spec["findings"]
                if finding["agent_name"] == agent
            )
            for agent in DEMO_AGENTS
        }
        token_totals = _seed_agent_executions(
            session=session,
            review_id=review.id,
            review_spec=review_spec,
            counts_by_agent=counts_by_agent,
        )
        agent_executions_created += len(DEMO_AGENTS)

        for finding_spec in review_spec["findings"]:
            session.add(
                Finding(
                    id=uuid.uuid4(),
                    review_id=review.id,
                    **finding_spec,
                )
            )
            findings_created += 1

        review.tokens_input = token_totals["input"]
        review.tokens_output = token_totals["output"]
        review.estimated_cost = Decimal("0.0000")

        session.add(
            AnalysisJob(
                id=uuid.uuid4(),
                review_id=review.id,
                status="done",
                attempts=1,
                next_run_at=review_spec["created_at"],
                last_attempt_at=review_spec["created_at"],
                locked_at=None,
                locked_by=None,
                completed_at=review_spec["completed_at"],
                error_message=None,
                created_at=review_spec["created_at"],
                updated_at=review_spec["completed_at"],
            )
        )
        analysis_jobs_created += 1
        seeded_review_ids.append(review.id)

    await session.flush()

    return {
        "repository_id": repository.id,
        "review_ids": seeded_review_ids,
        "first_review_id": seeded_review_ids[0] if seeded_review_ids else None,
        "reviews_created": len(seeded_review_ids),
        "findings_created": findings_created,
        "agent_executions_created": agent_executions_created,
        "analysis_jobs_created": analysis_jobs_created,
    }


def _seed_agent_executions(
    *,
    session: AsyncSession,
    review_id: uuid.UUID,
    review_spec: dict[str, Any],
    counts_by_agent: dict[str, int],
) -> dict[str, int]:
    """Create demo agent execution rows and return aggregate token totals."""
    total_input = 0
    total_output = 0
    started_at = review_spec["created_at"] + timedelta(seconds=8)
    completed_at = review_spec["completed_at"]

    for index, agent in enumerate(DEMO_AGENTS):
        tokens_input = 1100 + (index * 175)
        tokens_output = 180 + (counts_by_agent[agent] * 90)
        session.add(
            AgentExecution(
                id=uuid.uuid4(),
                review_id=review_id,
                agent_name=agent,
                status="done",
                started_at=started_at + timedelta(seconds=index * 4),
                completed_at=completed_at - timedelta(seconds=(len(DEMO_AGENTS) - index) * 3),
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                findings_count=counts_by_agent[agent],
                error_message=None,
            )
        )
        total_input += tokens_input
        total_output += tokens_output

    return {"input": total_input, "output": total_output}
