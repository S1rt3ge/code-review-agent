"""Encrypt and decrypt sensitive values (API keys) using Fernet symmetric encryption.

Functions:
    encrypt_value: Encrypt a plaintext string.
    decrypt_value: Decrypt a previously encrypted string.
"""

import logging

from cryptography.fernet import Fernet, InvalidToken

from backend.config import settings

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """Get or lazily create the Fernet cipher instance.

    Returns:
        Fernet instance initialised with the configured key.

    Raises:
        ValueError: If ``FERNET_KEY`` is not set in the environment.
    """
    global _fernet
    if _fernet is None:
        if not settings.fernet_key:
            raise ValueError("FERNET_KEY environment variable is not set")
        _fernet = Fernet(settings.fernet_key.encode())
    return _fernet


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value using Fernet symmetric encryption.

    Args:
        plaintext: Value to encrypt.

    Returns:
        Encrypted value as a URL-safe base64-encoded string.

    Raises:
        ValueError: If the Fernet key is not configured.
    """
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt an encrypted string value.

    Args:
        ciphertext: Encrypted value produced by ``encrypt_value``.

    Returns:
        Decrypted plaintext string.

    Raises:
        InvalidToken: If the ciphertext is invalid or the key does not match.
    """
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        logger.error("Failed to decrypt value -- key mismatch or corrupted data")
        raise
