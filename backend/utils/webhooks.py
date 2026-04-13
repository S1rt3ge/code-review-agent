"""GitHub webhook signature verification.

Functions:
    verify_github_signature: Verify HMAC-SHA256 signature from GitHub webhooks.
"""

import hashlib
import hmac
import logging

logger = logging.getLogger(__name__)


def verify_github_signature(
    body: bytes,
    signature: str | None,
    secret: str,
) -> bool:
    """Verify GitHub webhook HMAC-SHA256 signature.

    GitHub sends a ``X-Hub-Signature-256`` header with each webhook request.
    This function computes the expected HMAC digest and compares it against
    the provided signature using constant-time comparison.

    Args:
        body: Raw request body bytes.
        signature: ``X-Hub-Signature-256`` header value (e.g. ``sha256=abc...``).
        secret: GitHub webhook secret configured in repository settings.

    Returns:
        True if the signature is valid, False otherwise.
    """
    if not signature or not secret:
        logger.warning("Missing signature or secret for webhook verification")
        return False

    try:
        expected = hmac.new(
            secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(f"sha256={expected}", signature)
    except Exception as e:
        logger.error(f"Signature verification failed: {e}")
        return False
