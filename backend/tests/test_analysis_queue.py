"""Unit tests for analysis queue scheduling."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta, timezone

import pytest

from backend.services import analysis_queue


@pytest.mark.asyncio
async def test_enqueue_analysis_persists_new_pending_job() -> None:
    review_id = uuid.uuid4()
    captured_stmt = {"value": None}

    class FakeScalarResult:
        def __init__(self, job):
            self._job = job

        def scalar_one_or_none(self):
            return self._job

    class FakeSession:
        def __init__(self):
            self.job = None

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, _stmt):
            captured_stmt["value"] = _stmt
            return FakeScalarResult(self.job)

        def add(self, obj):
            self.job = obj

        async def commit(self):
            return None

    fake = FakeSession()
    with (
        patch(
            "backend.services.analysis_queue.async_session_factory", return_value=fake
        ),
        patch("backend.services.analysis_queue.pg_insert", new=object()),
    ):
        await analysis_queue.enqueue_analysis(review_id)

    assert captured_stmt["value"] is not None


@pytest.mark.asyncio
async def test_enqueue_analysis_resets_existing_done_job_to_pending() -> None:
    review_id = uuid.uuid4()
    existing = SimpleNamespace(
        review_id=review_id,
        status="done",
        attempts=3,
        next_run_at=None,
        locked_at="x",
        locked_by="y",
        error_message="oops",
        completed_at="z",
    )

    class FakeScalarResult:
        def scalar_one_or_none(self):
            return existing

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, _stmt):
            return FakeScalarResult()

        def add(self, _obj):
            raise AssertionError("add should not be called for existing job")

        async def commit(self):
            return None

    with (
        patch(
            "backend.services.analysis_queue.async_session_factory",
            return_value=FakeSession(),
        ),
        patch("backend.services.analysis_queue.pg_insert", new=object()),
    ):
        await analysis_queue.enqueue_analysis(review_id)

    assert existing.status == "pending"
    assert existing.attempts == 0
    assert existing.locked_at is None
    assert existing.locked_by is None
    assert existing.error_message is None
    assert existing.completed_at is None


@pytest.mark.asyncio
async def test_inflight_analyses_counts_running_jobs() -> None:
    class FakeScalarResult:
        def scalar_one(self):
            return 4

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, _stmt):
            return FakeScalarResult()

    with patch(
        "backend.services.analysis_queue.async_session_factory",
        return_value=FakeSession(),
    ):
        count = await analysis_queue.inflight_analyses()

    assert count == 4


@pytest.mark.asyncio
async def test_enqueue_analysis_fallback_when_pg_insert_unavailable() -> None:
    review_id = uuid.uuid4()
    existing = SimpleNamespace(
        review_id=review_id,
        status="done",
        attempts=3,
        next_run_at=None,
        locked_at="x",
        locked_by="y",
        error_message="oops",
        completed_at="y",
    )

    class FakeScalarResult:
        def scalar_one_or_none(self):
            return existing

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, _stmt):
            return FakeScalarResult()

        def add(self, _obj):
            raise AssertionError("add should not be called for existing job")

        async def commit(self):
            return None

    with (
        patch(
            "backend.services.analysis_queue.async_session_factory",
            return_value=FakeSession(),
        ),
        patch("backend.services.analysis_queue.pg_insert", None),
    ):
        await analysis_queue.enqueue_analysis(review_id)

    assert existing.status == "pending"
    assert existing.attempts == 0
    assert existing.locked_at is None
    assert existing.locked_by is None
    assert existing.error_message is None
    assert existing.completed_at is None


@pytest.mark.asyncio
async def test_recover_stale_running_jobs_marks_old_running_as_pending() -> None:
    stale_job = SimpleNamespace(
        status="running",
        attempts=1,
        next_run_at=None,
        locked_at=datetime.now(timezone.utc) - timedelta(hours=1),
        locked_by="worker-1",
        completed_at=None,
        error_message=None,
    )

    class FakeScalars:
        def all(self):
            return [stale_job]

    class FakeResult:
        def scalars(self):
            return FakeScalars()

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, _stmt):
            return FakeResult()

        async def commit(self):
            return None

    with patch(
        "backend.services.analysis_queue.async_session_factory",
        return_value=FakeSession(),
    ):
        recovered = await analysis_queue._recover_stale_running_jobs()  # noqa: SLF001

    assert recovered == 1
    assert stale_job.status == "pending"
    assert stale_job.attempts == 2
    assert stale_job.locked_at is None
    assert stale_job.locked_by is None


@pytest.mark.asyncio
async def test_process_job_marks_error_when_analysis_raises() -> None:
    job_id = uuid.uuid4()
    review_id = uuid.uuid4()
    job = SimpleNamespace(id=job_id, review_id=review_id)

    with (
        patch(
            "backend.services.analysis_queue.run_analysis",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ),
        patch(
            "backend.services.analysis_queue._mark_job_error",
            new=AsyncMock(),
        ) as mark_error,
        patch(
            "backend.services.analysis_queue._mark_job_done",
            new=AsyncMock(),
        ) as mark_done,
        patch(
            "backend.services.analysis_queue._heartbeat_lock",
            new=AsyncMock(),
        ),
    ):
        await analysis_queue._process_job(job)  # noqa: SLF001

    mark_error.assert_awaited_once()
    assert mark_error.await_args.args[0] == job_id
    assert "boom" in mark_error.await_args.args[1]
    mark_done.assert_not_awaited()
