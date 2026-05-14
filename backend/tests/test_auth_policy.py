"""Tests for email verification policy selection."""

from backend.utils import auth_policy


def test_email_verification_required_when_explicitly_enabled(monkeypatch):
    monkeypatch.setattr(auth_policy.settings, "auth_require_email_verification", True)
    monkeypatch.setattr(auth_policy.settings, "app_env", "development")

    assert auth_policy.is_email_verification_required() is True


def test_email_verification_disabled_when_explicitly_disabled(monkeypatch):
    monkeypatch.setattr(auth_policy.settings, "auth_require_email_verification", False)
    monkeypatch.setattr(auth_policy.settings, "app_env", "production")

    assert auth_policy.is_email_verification_required() is False


def test_email_verification_defaults_off_in_local_env(monkeypatch):
    monkeypatch.setattr(auth_policy.settings, "auth_require_email_verification", None)
    monkeypatch.setattr(auth_policy.settings, "app_env", "development")

    assert auth_policy.is_email_verification_required() is False


def test_email_verification_defaults_on_in_non_dev_env(monkeypatch):
    monkeypatch.setattr(auth_policy.settings, "auth_require_email_verification", None)
    monkeypatch.setattr(auth_policy.settings, "app_env", "production")

    assert auth_policy.is_email_verification_required() is True
