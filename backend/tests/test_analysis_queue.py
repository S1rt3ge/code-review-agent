"""Unit tests for analysis queue scheduling."""

import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from backend.services import analysis_queue


@pytest.mark.asyncio
async def test_enqueue_analysis_persists_new_pending_job() -> None:
    review_id = uuid.uuid4()

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
            return FakeScalarResult(self.job)

        def add(self, obj):
            self.job = obj

        async def commit(self):
            return None

    fake = FakeSession()
    with patch(
        "backend.services.analysis_queue.async_session_factory", return_value=fake
    ):
        await analysis_queue.enqueue_analysis(review_id)

    assert fake.job is not None
    assert fake.job.review_id == review_id
    assert fake.job.status == "pending"


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

    with patch(
        "backend.services.analysis_queue.async_session_factory",
        return_value=FakeSession(),
    ):
        await analysis_queue.enqueue_analysis(review_id)

    assert existing.status == "pending"
    assert existing.attempts == 0
    assert existing.locked_at is None
    assert existing.locked_by is None
    assert existing.error_message is None


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
