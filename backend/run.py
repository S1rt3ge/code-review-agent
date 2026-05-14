"""Local backend runner.

Use ``python -m backend.run`` for local development, especially on Windows.
It configures the event loop before uvicorn creates one so async psycopg can
connect to PostgreSQL reliably.
"""

from __future__ import annotations

from backend.utils.event_loop import configure_windows_selector_event_loop_policy

configure_windows_selector_event_loop_policy()

import uvicorn  # noqa: E402

from backend.config import settings  # noqa: E402


def main() -> None:
    """Start the FastAPI backend with project-safe defaults."""
    uvicorn.run(
        "backend.main:app",
        host=settings.app_host,
        port=settings.app_port,
    )


if __name__ == "__main__":
    main()
