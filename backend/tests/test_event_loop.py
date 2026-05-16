"""Event loop compatibility tests."""

import asyncio
import sys

from backend.run import get_uvicorn_loop_factory
from backend.utils.event_loop import configure_windows_selector_event_loop_policy


def test_configure_windows_selector_event_loop_policy_noops_off_windows(monkeypatch):
    """Non-Windows platforms should keep the current event loop policy."""
    original_policy = asyncio.get_event_loop_policy()
    sentinel_policy = asyncio.DefaultEventLoopPolicy()
    asyncio.set_event_loop_policy(sentinel_policy)
    monkeypatch.setattr(sys, "platform", "linux")

    try:
        configure_windows_selector_event_loop_policy()
        assert asyncio.get_event_loop_policy() is sentinel_policy
    finally:
        asyncio.set_event_loop_policy(original_policy)


def test_backend_run_uses_selector_loop_factory_on_windows(monkeypatch):
    """Uvicorn 0.44 otherwise chooses Proactor, which async psycopg rejects."""
    monkeypatch.setattr(sys, "platform", "win32")

    loop_factory = get_uvicorn_loop_factory()
    loop = loop_factory()
    try:
        assert isinstance(loop, asyncio.SelectorEventLoop)
    finally:
        loop.close()


def test_backend_run_uses_uvicorn_auto_loop_off_windows(monkeypatch):
    """Non-Windows local runs should keep uvicorn's normal loop selection."""
    monkeypatch.setattr(sys, "platform", "linux")

    assert get_uvicorn_loop_factory() == "auto"


def test_configure_windows_selector_event_loop_policy_sets_selector_on_windows(
    monkeypatch,
):
    """Windows should use SelectorEventLoopPolicy for async psycopg compatibility."""
    selector_policy = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
    if selector_policy is None:
        return

    original_policy = asyncio.get_event_loop_policy()
    monkeypatch.setattr(sys, "platform", "win32")

    try:
        configure_windows_selector_event_loop_policy()
        assert isinstance(asyncio.get_event_loop_policy(), selector_policy)
    finally:
        asyncio.set_event_loop_policy(original_policy)
