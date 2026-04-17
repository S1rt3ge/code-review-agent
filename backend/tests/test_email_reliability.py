"""Tests for email delivery reliability rules."""

from unittest.mock import patch

import pytest

from backend.services.notifications import EmailDeliveryError, _send_email_sync


def test_email_fallback_allowed_in_test_env() -> None:
    with (
        patch("backend.services.notifications.settings.app_env", "test"),
        patch("backend.services.notifications.settings.smtp_host", None),
        patch("backend.services.notifications.logger.info") as info_log,
    ):
        _send_email_sync("user@example.com", "Subject", "Body")

    assert info_log.called


def test_email_raises_when_smtp_missing_in_production() -> None:
    with (
        patch("backend.services.notifications.settings.app_env", "production"),
        patch("backend.services.notifications.settings.smtp_host", None),
        patch(
            "backend.services.notifications.settings.smtp_required_in_production", True
        ),
    ):
        with pytest.raises(EmailDeliveryError):
            _send_email_sync("user@example.com", "Subject", "Body")
