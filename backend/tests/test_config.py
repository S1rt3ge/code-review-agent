"""Configuration safety checks."""

from backend.config import _should_reject_default_jwt_secret


def test_default_jwt_secret_rejected_for_production_env() -> None:
    assert _should_reject_default_jwt_secret(
        app_env="production",
        jwt_secret="change-me-in-production",
    )


def test_default_jwt_secret_allowed_in_test_env() -> None:
    assert not _should_reject_default_jwt_secret(
        app_env="test",
        jwt_secret="change-me-in-production",
    )


def test_custom_jwt_secret_allowed_in_production() -> None:
    assert not _should_reject_default_jwt_secret(
        app_env="production",
        jwt_secret="super-secret",
    )
