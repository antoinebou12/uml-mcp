"""Per-replica ring buffer of auth decisions (never stores tokens)."""

from __future__ import annotations

import hashlib
import time
from collections import deque
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class AuditEvent:
    ts: float
    method: str
    path: str
    status: int
    reason: str
    request_id: str | None = None
    tenant_id: str | None = None
    client_id: str | None = None
    subject_hash: str | None = None
    tool: str | None = None


def subject_hash(subject: str | None) -> str | None:
    if not subject:
        return None
    return hashlib.sha256(subject.encode()).hexdigest()[:16]


class AuditLog:
    def __init__(self, maxlen: int = 200):
        self._events: deque[AuditEvent] = deque(maxlen=maxlen)
        self.counters: dict[str, int] = {}

    def record(self, event: AuditEvent) -> None:
        self._events.append(event)
        key = f"{event.status}:{event.reason}"
        self.counters[key] = self.counters.get(key, 0) + 1

    def snapshot(self) -> list[dict[str, Any]]:
        return [asdict(e) for e in reversed(self._events)]

    @staticmethod
    def now() -> float:
        return time.time()


__all__ = ["AuditEvent", "AuditLog", "subject_hash"]
