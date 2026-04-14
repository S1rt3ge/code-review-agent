"""Dashboard statistics endpoint.

Aggregates review, finding, and cost metrics for the frontend dashboard.

Functions:
    get_dashboard_stats: GET /dashboard/stats -- aggregate statistics.
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.db_models import Finding, Review, User
from backend.models.schemas import DashboardStatsResponse
from backend.utils.auth import get_current_user
from backend.utils.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DashboardStatsResponse:
    """Return aggregate statistics for the authenticated user's dashboard.

    Computes totals for reviews, findings grouped by severity and agent,
    top issue types, average review time, and monthly token/cost usage.
    All queries are scoped to the current user.

    Args:
        session: Async database session.
        current_user: Authenticated user from JWT.

    Returns:
        Dashboard statistics response with all aggregate values.
    """
    uid = current_user.id

    # Total reviews
    total_result = await session.execute(
        select(func.count(Review.id)).where(Review.user_id == uid)
    )
    total_reviews: int = total_result.scalar_one()

    # Reviews today (UTC)
    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_result = await session.execute(
        select(func.count(Review.id)).where(
            Review.user_id == uid,
            Review.created_at >= start_of_day,
        )
    )
    reviews_today: int = today_result.scalar_one()

    # Findings by severity (only user's reviews)
    severity_stmt = (
        select(Finding.severity, func.count(Finding.id))
        .join(Review, Finding.review_id == Review.id)
        .where(Review.user_id == uid, Finding.is_duplicate.is_(False))
        .group_by(Finding.severity)
    )
    severity_result = await session.execute(severity_stmt)
    findings_by_severity: dict[str, int] = {
        row[0]: row[1] for row in severity_result.all()
    }

    # Findings by agent
    agent_stmt = (
        select(Finding.agent_name, func.count(Finding.id))
        .join(Review, Finding.review_id == Review.id)
        .where(Review.user_id == uid, Finding.is_duplicate.is_(False))
        .group_by(Finding.agent_name)
    )
    agent_result = await session.execute(agent_stmt)
    findings_by_agent: dict[str, int] = {
        row[0]: row[1] for row in agent_result.all()
    }

    # Top issue types (top 10)
    top_stmt = (
        select(Finding.finding_type, func.count(Finding.id).label("cnt"))
        .join(Review, Finding.review_id == Review.id)
        .where(Review.user_id == uid, Finding.is_duplicate.is_(False))
        .group_by(Finding.finding_type)
        .order_by(func.count(Finding.id).desc())
        .limit(10)
    )
    top_result = await session.execute(top_stmt)
    top_issues: list[dict[str, int | str]] = [
        {"type": row[0], "count": row[1]} for row in top_result.all()
    ]

    # Average review time (seconds) for completed reviews
    avg_stmt = select(
        func.avg(
            func.extract("epoch", Review.completed_at)
            - func.extract("epoch", Review.created_at)
        )
    ).where(
        Review.user_id == uid,
        Review.status == "done",
        Review.completed_at.isnot(None),
    )
    avg_result = await session.execute(avg_stmt)
    avg_raw = avg_result.scalar_one()
    avg_review_time: float = round(float(avg_raw), 1) if avg_raw else 0.0

    # Monthly token and cost totals
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_stmt = select(
        func.coalesce(func.sum(Review.tokens_input + Review.tokens_output), 0),
        func.coalesce(func.sum(Review.estimated_cost), Decimal("0")),
    ).where(Review.user_id == uid, Review.created_at >= month_start)
    monthly_result = await session.execute(monthly_stmt)
    monthly_row = monthly_result.one()
    tokens_used: int = int(monthly_row[0])
    cost_this_month: Decimal = Decimal(str(monthly_row[1]))

    return DashboardStatsResponse(
        total_reviews=total_reviews,
        reviews_today=reviews_today,
        findings_by_severity=findings_by_severity,
        findings_by_agent=findings_by_agent,
        top_issues=top_issues,
        avg_review_time_seconds=avg_review_time,
        tokens_used_this_month=tokens_used,
        estimated_cost_this_month=cost_this_month,
    )
