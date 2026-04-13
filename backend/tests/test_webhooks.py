"""Unit tests for backend.utils.webhooks.verify_github_signature.

Tests cover valid signatures, invalid signatures, empty/missing values,
and malformed input.
"""

import hashlib
import hmac

import pytest

from backend.utils.webhooks import verify_github_signature


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_signature(body: bytes, secret: str) -> str:
    """Compute a valid GitHub-style HMAC-SHA256 signature."""
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestVerifyGithubSignature:
    """Tests for verify_github_signature."""

    def test_valid_signature(self) -> None:
        """Signature computed with correct secret should verify."""
        body = b'{"action": "opened"}'
        secret = "test-secret-123"
        signature = _make_signature(body, secret)

        assert verify_github_signature(body, signature, secret) is True

    def test_invalid_signature_wrong_secret(self) -> None:
        """Signature computed with a different secret should fail."""
        body = b'{"action": "opened"}'
        secret = "correct-secret"
        wrong_secret = "wrong-secret"
        signature = _make_signature(body, wrong_secret)

        assert verify_github_signature(body, signature, secret) is False

    def test_invalid_signature_tampered_body(self) -> None:
        """Signature for original body should fail against tampered body."""
        original = b'{"action": "opened"}'
        tampered = b'{"action": "closed"}'
        secret = "my-secret"
        signature = _make_signature(original, secret)

        assert verify_github_signature(tampered, signature, secret) is False

    def test_empty_signature(self) -> None:
        """Empty string signature should return False."""
        body = b'{"action": "opened"}'
        secret = "my-secret"

        assert verify_github_signature(body, "", secret) is False

    def test_none_signature(self) -> None:
        """None signature should return False."""
        body = b'{"action": "opened"}'
        secret = "my-secret"

        assert verify_github_signature(body, None, secret) is False

    def test_empty_secret(self) -> None:
        """Empty secret should return False regardless of signature."""
        body = b'{"action": "opened"}'
        signature = "sha256=abc123"

        assert verify_github_signature(body, signature, "") is False

    def test_empty_body(self) -> None:
        """Empty body with matching signature should verify."""
        body = b""
        secret = "secret"
        signature = _make_signature(body, secret)

        assert verify_github_signature(body, signature, secret) is True

    def test_malformed_signature_no_prefix(self) -> None:
        """Signature without 'sha256=' prefix should fail."""
        body = b'{"data": "test"}'
        secret = "secret"
        raw_digest = hmac.new(
            secret.encode("utf-8"), body, hashlib.sha256
        ).hexdigest()

        # Missing the sha256= prefix
        assert verify_github_signature(body, raw_digest, secret) is False

    def test_large_body(self) -> None:
        """Signature verification should work with large payloads."""
        body = b"x" * 100_000
        secret = "big-payload-secret"
        signature = _make_signature(body, secret)

        assert verify_github_signature(body, signature, secret) is True

    def test_unicode_secret(self) -> None:
        """Verification should handle non-ASCII characters in secret."""
        body = b'{"action": "opened"}'
        secret = "geheim-schluessel"
        signature = _make_signature(body, secret)

        assert verify_github_signature(body, signature, secret) is True
