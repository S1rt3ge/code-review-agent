"""Minimal JWT helpers for the algorithms this app uses.

The project only needs HS256 for local application tokens and RS256 signing for
GitHub App authentication. Keeping this surface tiny avoids pulling vulnerable
general-purpose JWT packages into the runtime dependency set.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import time
from datetime import datetime
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


class JWTDecodeError(ValueError):
    """Raised when a JWT cannot be decoded or verified."""


def encode_jwt(payload: dict[str, Any], key: str, *, algorithm: str) -> str:
    """Encode a signed JWT for the supported algorithms."""
    header = {"alg": algorithm, "typ": "JWT"}
    normalized_payload = {
        name: _normalize_claim_value(value) for name, value in payload.items()
    }
    signing_input = b".".join(
        [
            _base64url_json(header),
            _base64url_json(normalized_payload),
        ]
    )
    signature = _sign(signing_input, key, algorithm)
    return ".".join(
        [
            signing_input.decode("ascii"),
            _base64url_encode(signature).decode("ascii"),
        ]
    )


def decode_jwt(token: str, key: str, *, algorithms: list[str]) -> dict[str, Any]:
    """Decode and verify a JWT, including expiration."""
    parts = token.split(".")
    if len(parts) != 3:
        raise JWTDecodeError("JWT must contain header, payload, and signature")

    header_segment, payload_segment, signature_segment = parts
    header = _decode_json_segment(header_segment)
    payload = _decode_json_segment(payload_segment)

    algorithm = header.get("alg")
    if not isinstance(algorithm, str) or algorithm not in algorithms:
        raise JWTDecodeError("JWT algorithm is not allowed")
    if algorithm != "HS256":
        raise JWTDecodeError("JWT verification only supports HS256")

    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    expected_signature = _sign(signing_input, key, algorithm)
    actual_signature = _base64url_decode(signature_segment)
    if not hmac.compare_digest(expected_signature, actual_signature):
        raise JWTDecodeError("JWT signature is invalid")

    exp = payload.get("exp")
    if exp is not None:
        try:
            expires_at = float(exp)
        except (TypeError, ValueError) as exc:
            raise JWTDecodeError("JWT exp claim is invalid") from exc
        if expires_at <= time.time():
            raise JWTDecodeError("JWT is expired")

    return payload


def _sign(signing_input: bytes, key: str, algorithm: str) -> bytes:
    if algorithm == "HS256":
        return hmac.new(key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    if algorithm == "RS256":
        private_key = serialization.load_pem_private_key(
            key.encode("utf-8"),
            password=None,
        )
        return private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    raise ValueError(f"Unsupported JWT algorithm: {algorithm}")


def _normalize_claim_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return int(value.timestamp())
    return value


def _base64url_json(payload: dict[str, Any]) -> bytes:
    data = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return _base64url_encode(data)


def _base64url_encode(data: bytes) -> bytes:
    return base64.urlsafe_b64encode(data).rstrip(b"=")


def _base64url_decode(data: str) -> bytes:
    padding_size = (-len(data)) % 4
    try:
        return base64.urlsafe_b64decode((data + "=" * padding_size).encode("ascii"))
    except (ValueError, binascii.Error) as exc:
        raise JWTDecodeError("JWT segment is not valid base64url") from exc


def _decode_json_segment(segment: str) -> dict[str, Any]:
    try:
        decoded = _base64url_decode(segment)
        payload = json.loads(decoded)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise JWTDecodeError("JWT segment is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise JWTDecodeError("JWT segment must decode to an object")
    return payload
