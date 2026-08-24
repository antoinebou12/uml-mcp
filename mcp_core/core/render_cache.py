"""Small bounded in-process cache for rendered diagram results.

The cache intentionally sits behind a tiny interface so a distributed implementation
can replace it later without changing tool code. It is process-local by design.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Optional


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name, "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        return default
    return max(minimum, value)


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except ValueError:
        return default
    return max(minimum, value)


@dataclass
class _CacheEntry:
    value: dict[str, Any]
    created_at: float
    size_bytes: int


class InMemoryRenderCache:
    """Thread-safe TTL/LRU cache with entry and byte bounds."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._entries: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._bytes = 0
        self._hits = 0
        self._misses = 0

    @property
    def enabled(self) -> bool:
        # Tests default to disabled so existing mocks continue to assert render calls.
        testing = _env_bool("TESTING", False)
        return _env_bool("MCP_RENDER_CACHE_ENABLED", not testing)

    @property
    def ttl_seconds(self) -> float:
        return _env_float("MCP_RENDER_CACHE_TTL_SECONDS", 300.0)

    @property
    def max_entries(self) -> int:
        return _env_int("MCP_RENDER_CACHE_MAX_ENTRIES", 128)

    @property
    def max_bytes(self) -> int:
        return _env_int("MCP_RENDER_CACHE_MAX_BYTES", 32 * 1024 * 1024)

    @staticmethod
    def _value_size(value: dict[str, Any]) -> int:
        try:
            encoded = json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
            return len(encoded)
        except (TypeError, ValueError):
            return 0

    def _expired(self, entry: _CacheEntry, now: float) -> bool:
        ttl = self.ttl_seconds
        return ttl <= 0 or now - entry.created_at >= ttl

    def _remove(self, key: str) -> None:
        entry = self._entries.pop(key, None)
        if entry is not None:
            self._bytes = max(0, self._bytes - entry.size_bytes)

    def get(self, key: str) -> Optional[dict[str, Any]]:
        if not self.enabled:
            return None
        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._misses += 1
                return None
            if self._expired(entry, now):
                self._remove(key)
                self._misses += 1
                return None
            self._entries.move_to_end(key)
            self._hits += 1
            return copy.deepcopy(entry.value)

    def set(self, key: str, value: dict[str, Any]) -> None:
        if not self.enabled or self.max_entries <= 0 or self.max_bytes <= 0:
            return
        size = self._value_size(value)
        if size <= 0 or size > self.max_bytes:
            return
        with self._lock:
            self._remove(key)
            self._entries[key] = _CacheEntry(
                value=copy.deepcopy(value),
                created_at=time.monotonic(),
                size_bytes=size,
            )
            self._bytes += size
            while (
                len(self._entries) > self.max_entries
                or self._bytes > self.max_bytes
            ):
                oldest_key = next(iter(self._entries))
                self._remove(oldest_key)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._bytes = 0
            self._hits = 0
            self._misses = 0

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "entries": len(self._entries),
                "bytes": self._bytes,
                "hits": self._hits,
                "misses": self._misses,
            }


def build_render_cache_key(
    *,
    diagram_type: str,
    code: str,
    output_format: str,
    theme: Optional[str],
    scale: float,
    renderer_identity: str,
) -> str:
    """Return a deterministic key for all inputs that can affect render output."""
    payload = {
        "schema": 1,
        "diagram_type": diagram_type,
        "code": code.strip(),
        "output_format": output_format,
        "theme": theme or "",
        "scale": scale,
        "renderer_identity": renderer_identity,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


_RENDER_CACHE = InMemoryRenderCache()


def get_render_cache() -> InMemoryRenderCache:
    """Return the process-local render cache singleton."""
    return _RENDER_CACHE


__all__ = [
    "InMemoryRenderCache",
    "build_render_cache_key",
    "get_render_cache",
]
