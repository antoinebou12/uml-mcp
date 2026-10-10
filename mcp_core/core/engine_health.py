"""A small circuit breaker for Kroki engines that can hang (Mermaid on public kroki.io).

Why: when kroki.io's Mermaid engine hangs, every Mermaid render (and, in URL-only mode,
every Mermaid link check) waits out the fail-fast timeout before falling back to
mermaid.ink, on every call.

The breaker remembers that the engine is failing, so callers can skip it for a
cooldown and use the fallback straight away, then try it again afterwards.

It tracks engine health only. A diagram the engine rejects (HTTP 400: syntax error) is
proof the engine is alive and must be recorded as a success by the caller.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

logger = logging.getLogger(__name__)

FAILURE_THRESHOLD = 2


class EngineUnavailable(Exception):
    """Raised instead of calling an engine that the breaker has marked as failing."""

    def __init__(self, engine: str, retry_in: float) -> None:
        self.engine = engine
        self.retry_in = retry_in
        super().__init__(
            f"{engine} engine marked unavailable for another {retry_in:.0f}s"
        )


class EngineHealth:
    """Thread-safe health memory for one engine.

    After ``threshold`` consecutive failures the engine is *open* (skipped) for the
    cooldown. When the cooldown ends it is tried again: one more failure re-opens it, a
    success closes it.

    ``cooldown`` is a callable so the setting can change at runtime. A value of ``0``
    (or less) disables the breaker: nothing is ever skipped or remembered.
    """

    def __init__(
        self,
        name: str,
        *,
        cooldown: Callable[[], float],
        threshold: int = FAILURE_THRESHOLD,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.name = name
        self._cooldown = cooldown
        self._threshold = threshold
        self._clock = clock
        self._lock = threading.Lock()
        self._failures = 0
        self._open_until = 0.0

    def _enabled(self) -> bool:
        return self._cooldown() > 0

    def is_open(self) -> bool:
        """True while the engine should be skipped."""
        if not self._enabled():
            return False
        with self._lock:
            return self._clock() < self._open_until

    def retry_in(self) -> float:
        """Seconds until the engine is tried again (0 when it is not open)."""
        with self._lock:
            return max(0.0, self._open_until - self._clock())

    def success(self) -> None:
        if not self._enabled():
            return
        with self._lock:
            recovered = self._open_until > 0 or self._failures >= self._threshold
            self._failures = 0
            self._open_until = 0.0
        if recovered:
            logger.info("Kroki %s engine recovered", self.name)

    def failure(self) -> None:
        """Record a failed call; open the breaker once the threshold is reached."""
        if not self._enabled():
            return
        with self._lock:
            self._failures += 1
            should_open = self._failures >= self._threshold
            if should_open:
                self._open_until = self._clock() + self._cooldown()
        if should_open:
            logger.warning(
                "Kroki %s engine is failing; skipping it for %.0fs and using the "
                "fallback",
                self.name,
                self._cooldown(),
            )

    def reset(self) -> None:
        """Forget everything (a different Kroki server was selected, or between tests)."""
        with self._lock:
            self._failures = 0
            self._open_until = 0.0
