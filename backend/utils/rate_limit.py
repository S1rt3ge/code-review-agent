"""Rate-limiting utilities shared across API routers.

Provides a single SlowAPI limiter instance configured with a best-effort
client IP key function that supports reverse-proxy headers.
"""

from fastapi import Request
from slowapi import Limiter

from backend.config import settings


def _client_ip_key(request: Request) -> str:
    """Return client key for rate limiting.

    Prefers ``X-Forwarded-For`` (first hop) when present so limits work
    correctly behind reverse proxies/load balancers.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()

    if request.client and request.client.host:
        return request.client.host

    return "unknown"


limiter = Limiter(
    key_func=_client_ip_key,
    enabled=settings.app_env != "test",
)
