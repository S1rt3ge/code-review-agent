"""Tests for local demo mode seed behavior."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.models.db_models import User
from backend.routers.demo import seed_demo
from backend.services.demo_seed import build_demo_seed_plan, is_demo_seed_allowed


def test_demo_seed_allowed_only_in_non_production_envs() -> None:
    assert is_demo_seed_allowed("development") is True
    assert is_demo_seed_allowed("demo") is True
    assert is_demo_seed_allowed("test") is True
    assert is_demo_seed_allowed("production") is False
    assert is_demo_seed_allowed("staging") is False


def test_demo_seed_plan_has_realistic_data_shape() -> None:
    plan = build_demo_seed_plan(datetime(2026, 4, 27, tzinfo=timezone.utc))

    assert plan["repository"]["owner"] == "demo-org"
    assert plan["repository"]["name"] == "checkout-service"
    assert len(plan["reviews"]) == 3
    assert sum(len(review["findings"]) for review in plan["reviews"]) == 7
    assert all(review["status"] == "done" for review in plan["reviews"])
    assert all(review["lm_used"].startswith("ollama:") for review in plan["reviews"])
    assert any(len(review["findings"]) == 0 for review in plan["reviews"])


@pytest.mark.asyncio
async def test_seed_demo_endpoint_blocks_production_env() -> None:
    user = MagicMock(spec=User)
    session = AsyncMock()

    with patch("backend.routers.demo.settings.app_env", "production"):
        with pytest.raises(HTTPException) as exc_info:
            await seed_demo(session=session, current_user=user)

    assert exc_info.value.status_code == 403
    assert "local development or demo" in exc_info.value.detail
    session.execute.assert_not_called()
