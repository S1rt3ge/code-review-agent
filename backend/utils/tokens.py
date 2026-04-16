"""Secure token helpers for email verification and password reset."""

import hashlib
import secrets


def generate_urlsafe_token(length_bytes: int = 32) -> str:
    """Generate a cryptographically secure URL-safe token."""
    return secrets.token_urlsafe(length_bytes)


def hash_token(token: str) -> str:
    """Hash a token for DB storage (never store raw tokens)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
