"""Tests for health status degradation logic."""

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch

from backend.main import app


class _HealthySession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, _stmt):
        return None


@pytest.mark.asyncio
async def test_health_is_degraded_when_queue_has_stale_jobs() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        with (
            patch(
                "backend.main.analysis_queue.get_queue_metrics",
                new=AsyncMock(
                    return_value={
                        "pending_count": 0,
                        "running_count": 0,
                        "error_count": 0,
                        "done_count": 0,
                        "retry_count": 0,
                        "stale_running_count": 1,
                        "oldest_pending_age_seconds": 0,
                    }
                ),
            ),
            patch("backend.main.async_session_factory", return_value=_HealthySession()),
        ):
            response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"


@pytest.mark.asyncio
async def test_health_is_ok_when_db_connected_and_queue_within_threshold() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        with (
            patch(
                "backend.main.analysis_queue.get_queue_metrics",
                new=AsyncMock(
                    return_value={
                        "pending_count": 1,
                        "running_count": 1,
                        "error_count": 0,
                        "done_count": 3,
                        "retry_count": 1,
                        "stale_running_count": 0,
                        "oldest_pending_age_seconds": 120,
                    }
                ),
            ),
            patch("backend.main.async_session_factory", return_value=_HealthySession()),
        ):
            response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
