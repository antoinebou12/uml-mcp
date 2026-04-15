"""
Optional HTTP rate limiting and request ID propagation for FastAPI (e.g. app.py).
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from typing import Deque, Dict
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

_rate_buckets: Dict[str, Deque[float]] = defaultdict(deque)


def _rate_limited(client_ip: str, limit_per_minute: int) -> bool:
    if limit_per_minute <= 0:
        return False
    now = time.monotonic()
    q = _rate_buckets[client_ip]
    while q and now - q[0] > 60.0:
        q.popleft()
    if len(q) >= limit_per_minute:
        return True
    q.append(now)
    return False


class RequestIdAndRateLimitMiddleware(BaseHTTPMiddleware):
    """Assign X-Request-ID; optionally rate-limit selected paths (MCP_RATE_LIMIT_PER_MINUTE)."""

    async def dispatch(self, request: Request, call_next) -> Response:
        rid = request.headers.get("x-request-id") or str(uuid4())
        try:
            from .config import MCP_SETTINGS

            limit = MCP_SETTINGS.rate_limit_per_minute
        except Exception:  # noqa: BLE001
            limit = 0

        path = request.url.path
        if limit > 0 and path.startswith(
            ("/mcp", "/generate_diagram", "/kroki_encode")
        ):
            ip = request.client.host if request.client else "unknown"
            if _rate_limited(ip, limit):
                logger.warning(
                    "rate_limit exceeded request_id=%s path=%s ip=%s",
                    rid,
                    path,
                    ip,
                )
                return JSONResponse(
                    {"detail": "Rate limit exceeded. Try again later."},
                    status_code=429,
                    headers={"X-Request-ID": rid},
                )

        logger.info(
            "http_request request_id=%s method=%s path=%s",
            rid,
            request.method,
            path,
        )
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response
