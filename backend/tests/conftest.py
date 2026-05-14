"""Pytest configuration for backend tests.

Forces asyncio SelectorEventLoop on Windows so psycopg async works correctly.
On Linux/macOS the default event loop is already selector-based.
"""

import os

from backend.utils.event_loop import configure_windows_selector_event_loop_policy


os.environ.setdefault("APP_ENV", "test")
os.environ["AUTH_REQUIRE_EMAIL_VERIFICATION"] = "true"


def pytest_configure(config):
    """Set the Windows event loop policy to SelectorEventLoop before any tests run.

    psycopg's async driver is incompatible with Windows' default ProactorEventLoop.
    Switching to WindowsSelectorEventLoopPolicy fixes all async DB integration tests.
    """
    configure_windows_selector_event_loop_policy()
