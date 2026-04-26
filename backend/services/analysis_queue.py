"""Durable background analysis queue backed by the database.

This service replaces ad-hoc in-process fire-and-forget calls with a
database-backed job table and worker loop. Jobs survive process restarts.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from sqlalchemy.dialects.postgresql import insert as pg_insert
except Exception:  # pragma: no cover - fallback for non-postgres test envs
    pg_insert = None

from backend.config import settings
from backend.models.db_models import AnalysisJob, Review
from backend.services.analyzer import run_analysis
from backend.utils.database import async_session_factory

logger = logging.getLogger(__name__)

_worker_task: asyncio.Task | None = None
_instance_id = f"{socket.gethostname()}:{uuid.uuid4().hex[:8]}"


async def enqueue_analysis(review_id: uuid.UUID, session: AsyncSession | None = None) -> None:
    """Create or reset a durable analysis job for a review."""
    if session is not None:
        await _enqueue_analysis_in_session(session, review_id)
        return

    async with async_session_factory() as owned_session:
        await _enqueue_analysis_in_session(owned_session, review_id)
        await owned_session.commit()


async def _enqueue_analysis_in_session(session: AsyncSession, review_id: uuid.UUID) -> None:
    """Create or reset an analysis job using the caller's transaction."""
    now = datetime.now(timezone.utc)

    if pg_insert is None or not callable(pg_insert):
        result = await session.execute(
            select(AnalysisJob).where(AnalysisJob.review_id == review_id)
        )
        job = result.scalar_one_or_none()
        if job is None:
            session.add(
                AnalysisJob(
                    review_id=review_id,
                    status="pending",
                    attempts=0,
                    next_run_at=now,
                )
            )
        else:
            job.status = "pending"
            job.attempts = 0
            job.next_run_at = now
            job.locked_at = None
            job.locked_by = None
            job.error_message = None
            job.completed_at = None
        return

    upsert_stmt = (
        pg_insert(AnalysisJob)
        .values(
            review_id=review_id,
            status="pending",
            attempts=0,
            next_run_at=now,
            locked_at=None,
            locked_by=None,
            error_message=None,
            completed_at=None,
        )
        .on_conflict_do_update(
            index_elements=[AnalysisJob.review_id],
            set_={
                "status": "pending",
                "attempts": 0,
                "next_run_at": now,
                "locked_at": None,
                "locked_by": None,
                "error_message": None,
                "completed_at": None,
            },
        )
    )

    await session.execute(upsert_stmt)


async def startup() -> None:
    """Start queue worker loop if not running yet."""
    global _worker_task
    if _worker_task and not _worker_task.done():
        return
    _worker_task = asyncio.create_task(_worker_loop(), name="analysis-queue-worker")
    logger.info("Analysis queue worker started (%s)", _instance_id)


async def shutdown() -> None:
    """Stop queue worker loop gracefully."""
    global _worker_task
    if _worker_task is None:
        return
    _worker_task.cancel()
    try:
        await _worker_task
    except asyncio.CancelledError:
        pass
    _worker_task = None


async def inflight_analyses() -> int:
    """Return count of running jobs in the durable queue."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(func.count(AnalysisJob.id)).where(AnalysisJob.status == "running")
        )
        return int(result.scalar_one() or 0)


async def get_queue_metrics() -> dict[str, int | float | None]:
    """Return operational metrics for the durable analysis queue."""
    now = datetime.now(timezone.utc)

    async with async_session_factory() as session:
        counts_result = await session.execute(
            select(
                AnalysisJob.status,
                func.count(AnalysisJob.id),
            ).group_by(AnalysisJob.status)
        )
        counts = {row[0]: int(row[1]) for row in counts_result.all()}

        oldest_pending_result = await session.execute(
            select(func.min(AnalysisJob.created_at)).where(
                AnalysisJob.status == "pending"
            )
        )
        oldest_pending_created_at = oldest_pending_result.scalar_one_or_none()

        retries_result = await session.execute(
            select(func.coalesce(func.sum(AnalysisJob.attempts), 0))
        )
        retry_count = int(retries_result.scalar_one() or 0)

        stale_running_cutoff = now - timedelta(
            seconds=settings.analysis_queue_stale_lock_seconds
        )
        stale_running_result = await session.execute(
            select(func.count(AnalysisJob.id)).where(
                AnalysisJob.status == "running",
                AnalysisJob.locked_at.is_not(None),
                AnalysisJob.locked_at < stale_running_cutoff,
            )
        )
        stale_running_count = int(stale_running_result.scalar_one() or 0)

    oldest_pending_age_seconds: float | None = None
    if oldest_pending_created_at is not None:
        oldest_pending_age_seconds = max(
            0.0,
            (now - oldest_pending_created_at).total_seconds(),
        )

    return {
        "pending_count": counts.get("pending", 0),
        "running_count": counts.get("running", 0),
        "error_count": counts.get("error", 0),
        "done_count": counts.get("done", 0),
        "retry_count": retry_count,
        "stale_running_count": stale_running_count,
        "oldest_pending_age_seconds": oldest_pending_age_seconds,
    }


async def _worker_loop() -> None:
    """Poll pending jobs and process them one by one."""
    while True:
        try:
            await _recover_stale_running_jobs()
            jobs = await _claim_jobs(limit=settings.analysis_queue_batch_size)
            if not jobs:
                await asyncio.sleep(settings.analysis_queue_poll_interval_seconds)
                continue

            for job in jobs:
                await _process_job(job)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Analysis queue worker error: %s", exc, exc_info=True)
            await asyncio.sleep(settings.analysis_queue_poll_interval_seconds)


async def _claim_jobs(limit: int) -> list[AnalysisJob]:
    """Claim available jobs and mark them running."""
    now = datetime.now(timezone.utc)
    async with async_session_factory() as session:
        result = await session.execute(
            select(AnalysisJob)
            .where(
                and_(
                    AnalysisJob.status == "pending",
                    AnalysisJob.next_run_at <= now,
                )
            )
            .order_by(AnalysisJob.next_run_at.asc(), AnalysisJob.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        jobs = result.scalars().all()

        for job in jobs:
            job.status = "running"
            job.locked_at = now
            job.locked_by = _instance_id
            job.last_attempt_at = now

        await session.commit()
        return jobs


async def _process_job(job: AnalysisJob) -> None:
    """Execute one claimed analysis job and persist result."""
    heartbeat_task = asyncio.create_task(_heartbeat_lock(job.id))
    try:
        await run_analysis(job.review_id)
    except Exception as exc:
        await _mark_job_error(job.id, str(exc))
    else:
        await _mark_job_done(job.id)
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass


async def _set_review_state(
    session: AsyncSession,
    review_id: uuid.UUID,
    *,
    review_status: str,
    error_message: str | None,
    completed_at: datetime | None = None,
) -> None:
    """Best-effort sync from durable job state to review state."""
    if not hasattr(session, "get"):
        return
    review = await session.get(Review, review_id)
    if review is None:
        return
    review.status = review_status
    review.error_message = error_message
    if completed_at is not None:
        review.completed_at = completed_at


async def _heartbeat_lock(job_id: uuid.UUID) -> None:
    """Periodically refresh lock timestamp while a job is running."""
    while True:
        await asyncio.sleep(settings.analysis_queue_lock_heartbeat_seconds)
        async with async_session_factory() as session:
            result = await session.execute(
                select(AnalysisJob).where(
                    AnalysisJob.id == job_id,
                    AnalysisJob.status == "running",
                )
            )
            job = result.scalar_one_or_none()
            if job is None:
                return
            job.locked_at = datetime.now(timezone.utc)
            await session.commit()


async def _recover_stale_running_jobs() -> int:
    """Move stale running jobs back to pending for reprocessing."""
    cutoff = datetime.now(timezone.utc) - timedelta(
        seconds=settings.analysis_queue_stale_lock_seconds
    )
    async with async_session_factory() as session:
        result = await session.execute(
            select(AnalysisJob)
            .where(
                and_(
                    AnalysisJob.status == "running",
                    AnalysisJob.locked_at.is_not(None),
                    AnalysisJob.locked_at < cutoff,
                )
            )
            .with_for_update(skip_locked=True)
        )
        stale_jobs = result.scalars().all()

        if not stale_jobs:
            return 0

        now = datetime.now(timezone.utc)
        for job in stale_jobs:
            job.attempts += 1
            if job.attempts >= settings.analysis_queue_max_attempts:
                job.status = "error"
                job.completed_at = now
                job.error_message = (
                    "Analysis job exceeded retry limit after stale lock recovery"
                )
                if getattr(job, "review_id", None) is not None:
                    await _set_review_state(
                        session,
                        job.review_id,
                        review_status="error",
                        error_message=job.error_message,
                        completed_at=now,
                    )
            else:
                job.status = "pending"
                job.next_run_at = now
                job.locked_at = None
                job.locked_by = None
                if getattr(job, "review_id", None) is not None:
                    await _set_review_state(
                        session,
                        job.review_id,
                        review_status="pending",
                        error_message="Analysis job recovered after worker interruption",
                    )

        await session.commit()
        recovered = len(stale_jobs)
        logger.warning("Recovered %d stale running analysis jobs", recovered)
        return recovered


async def _mark_job_done(job_id: uuid.UUID) -> None:
    now = datetime.now(timezone.utc)
    async with async_session_factory() as session:
        result = await session.execute(
            select(AnalysisJob).where(AnalysisJob.id == job_id)
        )
        job = result.scalar_one_or_none()
        if job is None:
            return
        job.status = "done"
        job.completed_at = now
        job.locked_at = None
        job.locked_by = None
        await session.commit()


async def _mark_job_error(job_id: uuid.UUID, message: str) -> None:
    now = datetime.now(timezone.utc)
    async with async_session_factory() as session:
        result = await session.execute(
            select(AnalysisJob).where(AnalysisJob.id == job_id)
        )
        job = result.scalar_one_or_none()
        if job is None:
            return

        job.attempts += 1
        job.error_message = message[:2000]
        job.locked_at = None
        job.locked_by = None

        if job.attempts >= settings.analysis_queue_max_attempts:
            job.status = "error"
            job.completed_at = now
            await _set_review_state(
                session,
                job.review_id,
                review_status="error",
                error_message=job.error_message,
                completed_at=now,
            )
        else:
            delay = settings.analysis_queue_base_retry_seconds * (
                2 ** (job.attempts - 1)
            )
            job.status = "pending"
            job.next_run_at = now + timedelta(seconds=delay)
            await _set_review_state(
                session,
                job.review_id,
                review_status="pending",
                error_message=f"Analysis failed; retry scheduled in {delay} seconds",
            )

        await session.commit()
