"""Unit tests for backend.utils.crypto encrypt/decrypt roundtrip.

Tests cover successful encryption and decryption, key mismatch errors,
empty strings, and long values.
"""

import os
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet, InvalidToken

# We need to set FERNET_KEY before importing the module under test,
# because it reads settings at import time.  We use a fresh Fernet
# key for each test session.
_TEST_FERNET_KEY = Fernet.generate_key().decode()


@pytest.fixture(autouse=True)
def _reset_fernet_singleton() -> None:
    """Reset the module-level Fernet singleton between tests.

    This ensures each test starts with a clean state so that patching
    settings.fernet_key takes effect.
    """
    import backend.utils.crypto as mod

    mod._fernet = None


@pytest.fixture(autouse=True)
def _patch_fernet_key() -> None:
    """Patch settings.fernet_key for all tests in this module."""
    with patch("backend.utils.crypto.settings") as mock_settings:
        mock_settings.fernet_key = _TEST_FERNET_KEY
        yield


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEncryptDecrypt:
    """Roundtrip tests for encrypt_value and decrypt_value."""

    def test_roundtrip_simple(self) -> None:
        """Encrypt then decrypt returns original value."""
        from backend.utils.crypto import decrypt_value, encrypt_value

        original = "sk-ant-secret-key-12345"
        encrypted = encrypt_value(original)
        decrypted = decrypt_value(encrypted)

        assert decrypted == original

    def test_roundtrip_empty_string(self) -> None:
        """Encrypt then decrypt an empty string."""
        from backend.utils.crypto import decrypt_value, encrypt_value

        original = ""
        encrypted = encrypt_value(original)
        decrypted = decrypt_value(encrypted)

        assert decrypted == original

    def test_roundtrip_unicode(self) -> None:
        """Encrypt then decrypt a string with non-ASCII characters."""
        from backend.utils.crypto import decrypt_value, encrypt_value

        original = "api-key-with-unicode"
        encrypted = encrypt_value(original)
        decrypted = decrypt_value(encrypted)

        assert decrypted == original

    def test_roundtrip_long_value(self) -> None:
        """Encrypt then decrypt a long string."""
        from backend.utils.crypto import decrypt_value, encrypt_value

        original = "A" * 10_000
        encrypted = encrypt_value(original)
        decrypted = decrypt_value(encrypted)

        assert decrypted == original

    def test_encrypted_differs_from_plaintext(self) -> None:
        """Encrypted value should not equal the plaintext."""
        from backend.utils.crypto import encrypt_value

        original = "my-secret-api-key"
        encrypted = encrypt_value(original)

        assert encrypted != original

    def test_different_encryptions_differ(self) -> None:
        """Two encryptions of the same value should produce different ciphertext
        (Fernet uses a random IV)."""
        from backend.utils.crypto import encrypt_value

        original = "my-secret-api-key"
        enc1 = encrypt_value(original)
        enc2 = encrypt_value(original)

        assert enc1 != enc2

    def test_decrypt_with_wrong_key_raises(self) -> None:
        """Decrypting with a different Fernet key should raise InvalidToken."""
        from backend.utils.crypto import encrypt_value

        original = "my-secret-api-key"
        encrypted = encrypt_value(original)

        # Create a different Fernet instance with a new key
        other_fernet = Fernet(Fernet.generate_key())

        with pytest.raises(InvalidToken):
            other_fernet.decrypt(encrypted.encode())

    def test_decrypt_garbage_raises(self) -> None:
        """Decrypting garbage input should raise InvalidToken."""
        from backend.utils.crypto import decrypt_value

        with pytest.raises(InvalidToken):
            decrypt_value("not-a-valid-fernet-token")


class TestFernetKeyMissing:
    """Test behaviour when FERNET_KEY is not set."""

    def test_encrypt_raises_without_key(self) -> None:
        """encrypt_value should raise ValueError when key is None."""
        with patch("backend.utils.crypto.settings") as mock_settings:
            mock_settings.fernet_key = None

            import backend.utils.crypto as mod
            mod._fernet = None

            with pytest.raises(ValueError, match="FERNET_KEY"):
                mod.encrypt_value("test")

    def test_decrypt_raises_without_key(self) -> None:
        """decrypt_value should raise ValueError when key is None."""
        with patch("backend.utils.crypto.settings") as mock_settings:
            mock_settings.fernet_key = None

            import backend.utils.crypto as mod
            mod._fernet = None

            with pytest.raises(ValueError, match="FERNET_KEY"):
                mod.decrypt_value("test")
