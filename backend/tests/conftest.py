"""Pytest configuration for backend tests.

Forces asyncio SelectorEventLoop on Windows so psycopg async works correctly.
On Linux/macOS the default event loop is already selector-based.
"""

import asyncio
import os
import sys


os.environ.setdefault("APP_ENV", "test")


def pytest_configure(config):
    """Set the Windows event loop policy to SelectorEventLoop before any tests run.

    psycopg's async driver is incompatible with Windows' default ProactorEventLoop.
    Switching to WindowsSelectorEventLoopPolicy fixes all async DB integration tests.
    """
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
