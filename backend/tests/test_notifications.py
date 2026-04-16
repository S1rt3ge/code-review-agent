"""Tests for notification helpers."""

from backend.services.notifications import (
    build_email_verification_email,
    build_password_reset_email,
)


def test_build_password_reset_email_contains_link() -> None:
    subject, body = build_password_reset_email("https://example.com/reset?token=abc")
    assert "Reset your password" in subject
    assert "https://example.com/reset?token=abc" in body


def test_build_email_verification_email_contains_link() -> None:
    subject, body = build_email_verification_email(
        "https://example.com/verify?token=abc"
    )
    assert "Verify your email" in subject
    assert "https://example.com/verify?token=abc" in body
