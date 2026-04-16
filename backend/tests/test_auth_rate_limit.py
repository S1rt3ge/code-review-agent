"""Rate-limiter configuration tests."""

from backend.utils.rate_limit import limiter


def test_rate_limiter_disabled_in_test_env() -> None:
    assert limiter.enabled is False
