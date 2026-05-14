"""Authentication policy helpers."""

from __future__ import annotations

from backend.config import settings

_LOCAL_ENVS = {"development", "dev", "local", "test", "testing"}


def is_email_verification_required() -> bool:
    """Return whether login should require a verified email address."""
    configured = settings.auth_require_email_verification
    if configured is not None:
        return configured
    return settings.app_env.lower() not in _LOCAL_ENVS
