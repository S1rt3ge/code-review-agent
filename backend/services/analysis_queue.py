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

try:
    from sqlalchemy.dialects.postgresql import insert as pg_insert
except Exception:  # pragma: no cover - fallback for non-postgres test envs
    pg_insert = None

from backend.config import settings
from backend.models.db_models import AnalysisJob
from backend.services.analyzer import run_analysis
from backend.utils.database import async_session_factory

logger = logging.getLogger(__name__)

_worker_task: asyncio.Task | None = None
_instance_id = f"{socket.gethostname()}:{uuid.uuid4().hex[:8]}"


async def enqueue_analysis(review_id: uuid.UUID) -> None:
    """Create or reset a durable analysis job for a review."""
    now = datetime.now(timezone.utc)

    if pg_insert is None or not callable(pg_insert):
        async with async_session_factory() as session:
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
            await session.commit()
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

    async with async_session_factory() as session:
        await session.execute(upsert_stmt)
        await session.commit()


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
            if job.attempts >= settings.analysis_queue_max_attempts:
                job.status = "error"
                job.completed_at = now
                job.error_message = (
                    "Analysis job exceeded retry limit after stale lock recovery"
                )
            else:
                job.status = "pending"
                job.next_run_at = now
                job.locked_at = None
                job.locked_by = None

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
        else:
            delay = settings.analysis_queue_base_retry_seconds * (
                2 ** (job.attempts - 1)
            )
            job.status = "pending"
            job.next_run_at = now + timedelta(seconds=delay)

        await session.commit()
