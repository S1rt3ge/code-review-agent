"""Email notification delivery service.

Supports SMTP delivery when configured, and logs links in development/test
or when SMTP credentials are absent.
"""

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from backend.config import settings

logger = logging.getLogger(__name__)

_NON_PROD_ENVS = {"development", "dev", "local", "test", "testing"}


class EmailDeliveryError(RuntimeError):
    """Raised when email delivery is required but cannot be completed."""


def _smtp_is_configured() -> bool:
    """Return True when SMTP host is configured for real delivery."""
    return bool(settings.smtp_host)


def _email_fallback_allowed() -> bool:
    """Return True when logging-only fallback is acceptable."""
    return (
        settings.app_env.lower() in _NON_PROD_ENVS
        or not settings.smtp_required_in_production
    )


def _send_email_sync(to_email: str, subject: str, body: str) -> None:
    """Blocking SMTP send helper executed in a worker thread."""
    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    if not _smtp_is_configured():
        if _email_fallback_allowed():
            logger.info(
                "[email-fallback] to=%s subject=%s\n%s", to_email, subject, body
            )
            return
        logger.error(
            "Email delivery unavailable in %s: SMTP_HOST is not configured",
            settings.app_env,
        )
        raise EmailDeliveryError("SMTP is required in production but not configured")

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_user and settings.smtp_password:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
    except Exception as exc:
        logger.error("Email delivery failed to %s: %s", to_email, exc)
        raise EmailDeliveryError(f"Email delivery failed: {exc}") from exc


async def send_email(to_email: str, subject: str, body: str) -> None:
    """Send an email asynchronously without blocking the event loop."""
    await asyncio.to_thread(_send_email_sync, to_email, subject, body)


def build_password_reset_email(link: str) -> tuple[str, str]:
    """Build password reset email subject + body."""
    subject = "Reset your password"
    body = (
        "We received a request to reset your password.\n\n"
        f"Open this link to set a new password:\n{link}\n\n"
        "If you did not request this change, you can safely ignore this email."
    )
    return subject, body


def build_email_verification_email(link: str) -> tuple[str, str]:
    """Build email verification subject + body."""
    subject = "Verify your email"
    body = (
        "Welcome to AI Code Review Agent.\n\n"
        f"Please verify your email by opening this link:\n{link}\n\n"
        "If you did not create this account, you can ignore this email."
    )
    return subject, body
