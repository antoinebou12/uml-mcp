"""Configurable token-bucket rate limiting (per IP, principal or client id)."""

from __future__ import annotations

import hashlib
import ipaddress
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from ..core.settings_file import LimitConfig, RateLimitConfig


@dataclass
class Decision:
    allowed: bool
    limit: int
    remaining: int
    reset_seconds: int


class TokenBucketLimiter:
    """Thread-safe token buckets keyed by (scope, key). Per process by design."""

    def __init__(
        self, clock: Callable[[], float] = time.monotonic, max_keys: int = 50_000
    ):
        self._clock = clock
        self._buckets: dict[tuple[str, str], tuple[float, float]] = {}
        self._lock = threading.Lock()
        self._max_keys = max_keys

    def check(self, scope: str, key: str, limit: LimitConfig) -> Decision:
        rate = limit.requests_per_minute / 60.0
        capacity = float(limit.burst or limit.requests_per_minute)
        now = self._clock()
        with self._lock:
            if len(self._buckets) > self._max_keys:
                self._buckets.clear()  # bounded memory under key-spraying
            tokens, last = self._buckets.get((scope, key), (capacity, now))
            tokens = min(capacity, tokens + (now - last) * rate)
            allowed = tokens >= 1.0
            if allowed:
                tokens -= 1.0
            self._buckets[(scope, key)] = (tokens, now)
        reset = 0 if tokens >= 1 else int((1.0 - tokens) / rate) + 1
        return Decision(allowed, int(capacity), int(tokens), reset)

    def exhausted(self, scope: str, key: str, limit: LimitConfig) -> bool:
        """True when the bucket exists and has no whole token left (no consumption)."""
        rate = limit.requests_per_minute / 60.0
        capacity = float(limit.burst or limit.requests_per_minute)
        with self._lock:
            state = self._buckets.get((scope, key))
        if state is None:
            return False
        tokens, last = state
        return min(capacity, tokens + (self._clock() - last) * rate) < 1.0

    def hot_keys(self, top: int = 10) -> list[dict[str, object]]:
        with self._lock:
            items = sorted(self._buckets.items(), key=lambda kv: kv[1][0])[:top]
        return [
            {"scope": scope, "key": _hash(key), "tokens_left": round(tokens, 2)}
            for (scope, key), (tokens, _) in items
        ]

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def client_ip(peer: str | None, forwarded_for: str | None, trusted: list[str]) -> str:
    """Honour ``X-Forwarded-For`` only when the socket peer is a trusted proxy."""
    peer = peer or "unknown"
    if not forwarded_for or not trusted:
        return peer
    try:
        peer_ip = ipaddress.ip_address(peer)
        nets = [ipaddress.ip_network(n, strict=False) for n in trusted]
    except ValueError:
        return peer
    if not any(peer_ip in n for n in nets):
        return peer
    hops = [h.strip() for h in forwarded_for.split(",") if h.strip()]
    for hop in reversed(hops):  # right-most untrusted hop is the client
        try:
            ip = ipaddress.ip_address(hop)
        except ValueError:
            return peer
        if not any(ip in n for n in nets):
            return hop
    return hops[0] if hops else peer


def rate_key(cfg: RateLimitConfig, ip: str, authorization: str | None) -> str:
    """Bucket key. ``principal`` keys on the presented bearer token (hashed).

    The token is not verified yet at this point, so callers must also apply
    :data:`AUTH_FAILURE_SCOPE` throttling per IP (see the HTTP middleware):
    otherwise random tokens would each get a fresh bucket.
    """
    if cfg.key == "principal" and authorization:
        return "tok:" + _hash(authorization)
    return f"ip:{ip}"


#: Per-IP bucket charged on every 401 when keying by principal.
AUTH_FAILURE_SCOPE = "auth-failures"


def route_limit(cfg: RateLimitConfig, path: str) -> tuple[str, LimitConfig] | None:
    if any(path.startswith(p) for p in cfg.exempt_paths):
        return None
    best = ""
    for prefix in cfg.routes:
        if (path == prefix or path.startswith(prefix.rstrip("/") + "/")) and len(
            prefix
        ) > len(best):
            best = prefix
    if best:
        return f"route:{best}", cfg.routes[best]
    return "default", cfg.default


LIMITER = TokenBucketLimiter()

__all__ = [
    "AUTH_FAILURE_SCOPE",
    "LIMITER",
    "Decision",
    "TokenBucketLimiter",
    "client_ip",
    "rate_key",
    "route_limit",
]
