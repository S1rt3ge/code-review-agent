"""Tests for secure token helpers."""

from backend.utils.tokens import generate_urlsafe_token, hash_token


def test_generate_urlsafe_token_not_empty() -> None:
    token = generate_urlsafe_token()
    assert isinstance(token, str)
    assert len(token) > 20


def test_generate_urlsafe_token_unique() -> None:
    token1 = generate_urlsafe_token()
    token2 = generate_urlsafe_token()
    assert token1 != token2


def test_hash_token_is_deterministic() -> None:
    token = "abc123"
    assert hash_token(token) == hash_token(token)


def test_hash_token_not_equal_input() -> None:
    token = "abc123"
    assert hash_token(token) != token
