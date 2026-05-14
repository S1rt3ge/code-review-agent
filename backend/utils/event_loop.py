"""Event loop compatibility helpers.

The async psycopg driver cannot run on Windows' default Proactor event loop.
Configure the Selector policy as early as possible in local Python processes.
"""

from __future__ import annotations

import asyncio
import sys


def configure_windows_selector_event_loop_policy() -> None:
    """Use the Windows Selector event loop policy when available."""
    if sys.platform != "win32":
        return
    selector_policy = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
    if selector_policy is None:
        return
    asyncio.set_event_loop_policy(selector_policy())
