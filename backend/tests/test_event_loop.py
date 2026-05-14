"""Event loop compatibility tests."""

import asyncio
import sys

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
