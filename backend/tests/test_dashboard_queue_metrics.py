"""Tests for queue observability metrics surfaced in API responses."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from backend.services.analysis_queue import get_queue_metrics


@pytest.mark.asyncio
async def test_get_queue_metrics_returns_counts_and_oldest_pending_age() -> None:
    now = datetime.now(timezone.utc)
    pending_created_at = now - timedelta(seconds=120)

    scalar_values = iter(
        [
            pending_created_at,
            7,
            1,
        ]
    )

    class FakeCountsResult:
        def all(self):
            return [
                ("pending", 2),
                ("running", 1),
                ("error", 3),
                ("done", 4),
            ]

    class FakeScalarResult:
        def scalar_one_or_none(self):
            return next(scalar_values)

        def scalar_one(self):
            return next(scalar_values)

    class FakeSession:
        def __init__(self):
            self.calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, _stmt):
            self.calls += 1
            if self.calls == 1:
                return FakeCountsResult()
            return FakeScalarResult()

    with patch(
        "backend.services.analysis_queue.async_session_factory",
        return_value=FakeSession(),
    ):
        metrics = await get_queue_metrics()

    assert metrics["pending_count"] == 2
    assert metrics["running_count"] == 1
    assert metrics["error_count"] == 3
    assert metrics["done_count"] == 4
    assert metrics["retry_count"] == 7
    assert metrics["stale_running_count"] == 1
    assert metrics["oldest_pending_age_seconds"] is not None
    assert metrics["oldest_pending_age_seconds"] >= 120
