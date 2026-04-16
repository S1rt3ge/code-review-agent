"""Startup recovery utilities.

Handles reconciliation of review records that were left in ``analyzing``
state due to process crashes/restarts.
"""

from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.db_models import Review


async def recover_stuck_reviews(session: AsyncSession) -> int:
    """Move stale ``analyzing`` reviews to ``error`` on startup.

    Args:
        session: Open database session used during app startup.

    Returns:
        Number of rows updated.
    """
    result = await session.execute(
        update(Review)
        .where(Review.status == "analyzing")
        .values(
            status="error",
            error_message="Analysis interrupted by server restart",
            completed_at=datetime.now(timezone.utc),
        )
    )
    rowcount = result.rowcount
    if rowcount is None or rowcount < 0:
        return 0
    return int(rowcount)
