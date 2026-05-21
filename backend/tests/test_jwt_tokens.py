"""Tests for the app's minimal JWT helper."""

import base64
import json
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from backend.utils.jwt_tokens import JWTDecodeError, decode_jwt, encode_jwt


def test_encode_decode_hs256_round_trips_claims():
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    token = encode_jwt(
        {"sub": "user-1", "email": "user@example.com", "exp": expires_at},
        "secret",
        algorithm="HS256",
    )

    payload = decode_jwt(token, "secret", algorithms=["HS256"])

    assert payload["sub"] == "user-1"
    assert payload["email"] == "user@example.com"
    assert payload["exp"] == int(expires_at.timestamp())


def test_decode_hs256_rejects_tampered_signature():
    token = encode_jwt(
        {"sub": "user-1", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "secret",
        algorithm="HS256",
    )
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")

    with pytest.raises(JWTDecodeError, match="signature"):
        decode_jwt(tampered, "secret", algorithms=["HS256"])


def test_decode_hs256_rejects_expired_token():
    token = encode_jwt(
        {"sub": "user-1", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
        "secret",
        algorithm="HS256",
    )

    with pytest.raises(JWTDecodeError, match="expired"):
        decode_jwt(token, "secret", algorithms=["HS256"])


def test_decode_hs256_rejects_disallowed_algorithm():
    token = encode_jwt(
        {"sub": "user-1", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "secret",
        algorithm="HS256",
    )

    with pytest.raises(JWTDecodeError, match="algorithm"):
        decode_jwt(token, "secret", algorithms=["RS256"])


def test_encode_rs256_signs_with_private_key():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    token = encode_jwt(
        {"iss": "123", "iat": 100, "exp": 200},
        pem,
        algorithm="RS256",
    )
    header_segment, payload_segment, signature_segment = token.split(".")
    header = json.loads(_base64url_decode(header_segment))

    assert header["alg"] == "RS256"
    private_key.public_key().verify(
        _base64url_decode(signature_segment),
        f"{header_segment}.{payload_segment}".encode("ascii"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )


def _base64url_decode(segment: str) -> bytes:
    padded = segment + "=" * ((-len(segment)) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))
