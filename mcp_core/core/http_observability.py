"""Optional HTTP rate limiting and request ID propagation for FastAPI."""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# In-memory and intentionally per process. A distributed implementation can replace
# this helper later without changing HTTP response semantics.
_rate_buckets: dict[str, deque[float]] = defaultdict(deque)


def _rate_limit_state(
    client_ip: str,
    limit_per_minute: int,
) -> tuple[bool, int, int]:
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


REST_AUDIT_PREFIXES = ("/generate_diagram", "/kroki_encode", "/ag-ui")


def _limit_response(request_id: str, limit: int, retry_after: int) -> JSONResponse:
    return JSONResponse(
        {"detail": "Rate limit exceeded. Try again later.", "error": "rate_limited"},
        status_code=429,
        headers={
            "X-Request-ID": request_id,
            "Retry-After": str(retry_after),
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": "0",
            "RateLimit-Limit": str(limit),
            "RateLimit-Remaining": "0",
            "RateLimit-Reset": str(retry_after),
        },
    )


class RequestIdAndRateLimitMiddleware(BaseHTTPMiddleware):
    """Assign X-Request-ID, set the audit context and apply rate limits.

    Rate limits come from ``rate_limit`` in ``uml-mcp.yaml`` (token bucket,
    per IP / principal / client id, route overrides, trusted proxies). The
    legacy ``MCP_RATE_LIMIT_PER_MINUTE`` sliding window still applies when the
    section is disabled. Limiters are per process; use the ingress/APIM for
    global limits.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        from ..observability.context import reset_context, set_context
        from ..observability.metrics import METRICS
        from ..observability.ratelimit import (
            AUTH_FAILURE_SCOPE,
            LIMITER,
            client_ip,
            rate_key,
            route_limit,
        )
        from .settings_file import LimitConfig, get_app_config

        request_id = (request.headers.get("x-request-id") or str(uuid4()))[:128]
        try:
            from .config import MCP_SETTINGS

            legacy_limit = MCP_SETTINGS.rate_limit_per_minute
        except Exception:  # noqa: BLE001
            legacy_limit = 0
        app_cfg = get_app_config()
        rl = app_cfg.rate_limit
        path = request.url.path
        peer = request.client.host if request.client else "unknown"
        ip = client_ip(peer, request.headers.get("x-forwarded-for"), rl.trusted_proxies)
        key = rate_key(rl, ip, request.headers.get("authorization"))
        session = request.headers.get("mcp-session-id")
        token = set_context(
            caller_type="http",
            request_id=request_id,
            session_id=session or f"req-{request_id[:12]}",
            rate_key=key,
        )
        try:
            headers: dict[str, str] = {}
            ip_key = f"ip:{ip}"
            fail_limit = LimitConfig(requests_per_minute=rl.auth_failures_per_minute)
            throttle_failures = rl.enabled and key != ip_key
            if throttle_failures and LIMITER.exhausted(
                AUTH_FAILURE_SCOPE, ip_key, fail_limit
            ):
                METRICS.rate_limit_hit(AUTH_FAILURE_SCOPE)
                logger.warning(
                    "rate_limit auth failures request_id=%s path=%s", request_id, path
                )
                return _limit_response(request_id, fail_limit.requests_per_minute, 60)
            if rl.enabled:
                target = route_limit(rl, path)
                if target is not None:
                    scope, limit = target
                    decision = LIMITER.check(scope, key, limit)
                    headers = {
                        "RateLimit-Limit": str(decision.limit),
                        "RateLimit-Remaining": str(decision.remaining),
                        "RateLimit-Reset": str(decision.reset_seconds),
                        "X-RateLimit-Limit": str(decision.limit),
                        "X-RateLimit-Remaining": str(decision.remaining),
                    }
                    if not decision.allowed:
                        METRICS.rate_limit_hit(scope)
                        logger.warning(
                            "rate_limit exceeded request_id=%s path=%s scope=%s",
                            request_id,
                            path,
                            scope,
                        )
                        return _limit_response(
                            request_id, decision.limit, max(1, decision.reset_seconds)
                        )
            elif legacy_limit > 0 and path.startswith(
                ("/mcp", "/generate_diagram", "/kroki_encode")
            ):
                limited, remaining_value, retry_after = _rate_limit_state(
                    peer, legacy_limit
                )
                if limited:
                    METRICS.rate_limit_hit("legacy")
                    logger.warning(
                        "rate_limit exceeded request_id=%s path=%s ip=%s",
                        request_id,
                        path,
                        peer,
                    )
                    return _limit_response(request_id, legacy_limit, retry_after)
                headers = {
                    "X-RateLimit-Limit": str(legacy_limit),
                    "X-RateLimit-Remaining": str(remaining_value),
                }

            logger.info(
                "http_request request_id=%s method=%s path=%s",
                request_id,
                request.method,
                path,
            )
            start = time.perf_counter()
            from ..observability import otel
            from ..observability.metrics import _series_name

            with otel.span(
                _series_name("http", f"{request.method} {path}"),
                {
                    "http.request.method": request.method,
                    "url.path": path,
                    "mcp.request_id": request_id,
                },
                carrier=dict(request.headers),
                kind="server",
            ) as http_span:
                response = await call_next(request)
                if http_span is not None:
                    http_span.set_attribute(
                        "http.response.status_code", response.status_code
                    )
            if throttle_failures and response.status_code == 401:
                LIMITER.check(AUTH_FAILURE_SCOPE, ip_key, fail_limit)
            if app_cfg.audit.include_http and path.startswith(REST_AUDIT_PREFIXES):
                from ..observability.audit import record_operation

                record_operation(
                    operation_type="http",
                    operation_name=f"{request.method} {path}",
                    duration_ms=(time.perf_counter() - start) * 1000,
                    operation_status="success"
                    if response.status_code < 400
                    else "error",
                    error=None
                    if response.status_code < 400
                    else f"HTTP {response.status_code}",
                )
            response.headers["X-Request-ID"] = request_id
            for name, value in headers.items():
                response.headers[name] = value
            return response
        finally:
            reset_context(token)
