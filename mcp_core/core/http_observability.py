"""Optional HTTP rate limiting and request ID propagation for FastAPI."""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Tuple
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# In-memory and intentionally per process. A distributed implementation can replace
# this helper later without changing HTTP response semantics.
_rate_buckets: Dict[str, Deque[float]] = defaultdict(deque)


def _rate_limit_state(
    client_ip: str,
    limit_per_minute: int,
) -> Tuple[bool, int, int]:
    """Return (limited, remaining, retry_after_seconds) for one client IP."""
    if limit_per_minute <= 0:
        return False, 0, 0

    now = time.monotonic()
    queue = _rate_buckets[client_ip]
    while queue and now - queue[0] > 60.0:
        queue.popleft()

    if len(queue) >= limit_per_minute:
        retry_after = max(1, int(60.0 - (now - queue[0]) + 0.999))
        return True, 0, retry_after

    queue.append(now)
    remaining = max(0, limit_per_minute - len(queue))
    return False, remaining, 0


def _rate_limited(client_ip: str, limit_per_minute: int) -> bool:
    """Backward-compatible boolean helper used by existing tests/callers."""
    limited, _, _ = _rate_limit_state(client_ip, limit_per_minute)
    return limited


class RequestIdAndRateLimitMiddleware(BaseHTTPMiddleware):
    """Assign X-Request-ID and optionally rate-limit generation endpoints.

    The limiter is process-local. Horizontally scaled deployments should use a
    distributed limiter at the platform/edge or replace this implementation.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid4())
        try:
            from .config import MCP_SETTINGS

            limit = MCP_SETTINGS.rate_limit_per_minute
        except Exception:  # noqa: BLE001
            limit = 0

        path = request.url.path
        protected = path.startswith(("/mcp", "/generate_diagram", "/kroki_encode"))
        remaining = None
        if limit > 0 and protected:
            # Deliberately trust only the socket peer here. Forwarded headers require an
            # explicitly trusted proxy configuration and are not interpreted by this app.
            client_ip = request.client.host if request.client else "unknown"
            limited, remaining_value, retry_after = _rate_limit_state(client_ip, limit)
            remaining = remaining_value
            if limited:
                logger.warning(
                    "rate_limit exceeded request_id=%s path=%s ip=%s",
                    request_id,
                    path,
                    client_ip,
                )
                return JSONResponse(
                    {"detail": "Rate limit exceeded. Try again later."},
                    status_code=429,
                    headers={
                        "X-Request-ID": request_id,
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(limit),
                        "X-RateLimit-Remaining": "0",
                    },
                )

        logger.info(
            "http_request request_id=%s method=%s path=%s",
            request_id,
            request.method,
            path,
        )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        if limit > 0 and protected and remaining is not None:
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
