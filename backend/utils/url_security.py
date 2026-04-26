"""Server-side URL validation helpers.

Used before the backend makes HTTP requests to user-provided endpoints.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


_PRIVATE_HOSTNAMES = {"localhost"}


def validate_server_http_url(url: str, *, allow_private: bool = False) -> str:
    """Validate and normalize an HTTP URL used by backend HTTP clients.

    Args:
        url: Candidate URL.
        allow_private: Whether localhost/private/link-local targets are allowed.

    Returns:
        Normalized URL without a trailing slash.

    Raises:
        ValueError: If the URL is malformed or points at a disallowed host.
    """
    candidate = url.strip().rstrip("/")
    parsed = urlparse(candidate)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL must be an absolute http(s) URL")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL host is required")

    if allow_private:
        return candidate

    host_lower = hostname.lower().rstrip(".")
    if host_lower in _PRIVATE_HOSTNAMES:
        raise ValueError("Private or localhost hosts are not allowed")

    addresses: set[str] = set()
    try:
        ipaddress.ip_address(host_lower)
        addresses.add(host_lower)
    except ValueError:
        try:
            infos = socket.getaddrinfo(hostname, parsed.port or 443)
        except socket.gaierror as exc:
            raise ValueError("URL host could not be resolved") from exc
        addresses.update(info[4][0] for info in infos)

    for raw_address in addresses:
        try:
            address = ipaddress.ip_address(raw_address)
        except ValueError:
            raise ValueError("URL host resolved to an invalid address") from None

        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        ):
            raise ValueError("Private or localhost hosts are not allowed")

    return candidate
