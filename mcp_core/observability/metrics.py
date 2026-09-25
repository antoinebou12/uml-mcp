"""In-process metrics: call counts, errors, denials, latency percentiles."""

from __future__ import annotations

import bisect
import threading
import time
from collections import defaultdict
from typing import Any

BUCKETS_MS = (5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000)
#: Distinct (type, name) series kept; the rest aggregate under name="other".
MAX_SERIES = 200


def _series_name(op_type: str, name: str) -> str:
    """Bounded metric name: HTTP paths keep method + first two segments only."""
    if op_type != "http":
        return name[:80]
    method, _, path = name.partition(" ")
    segments = [p for p in path.split("/") if p][:2]
    return f"{method} /{'/'.join(segments)}"


def _label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


class Histogram:
    def __init__(self) -> None:
        self.counts = [0] * (len(BUCKETS_MS) + 1)
        self.total = 0
        self.sum_ms = 0.0

    def observe(self, value_ms: float) -> None:
        self.counts[bisect.bisect_left(BUCKETS_MS, value_ms)] += 1
        self.total += 1
        self.sum_ms += value_ms

    def percentile(self, q: float) -> float | None:
        if not self.total:
            return None
        target = q * self.total
        seen = 0
        for i, count in enumerate(self.counts):
            seen += count
            if seen >= target:
                # the overflow bucket reports its lower bound (JSON has no inf)
                return float(BUCKETS_MS[min(i, len(BUCKETS_MS) - 1)])
        return float(BUCKETS_MS[-1])  # pragma: no cover


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.started = time.time()
        self.reset()

    def reset(self) -> None:
        self.calls: dict[tuple[str, str], dict[str, int]] = defaultdict(
            lambda: {"success": 0, "error": 0, "denied": 0}
        )
        self.latency: dict[tuple[str, str], Histogram] = defaultdict(Histogram)
        self.denial_reasons: dict[str, int] = defaultdict(int)
        self.rate_limited: dict[str, int] = defaultdict(int)
        self.sink_errors = 0

    def observe(self, record: dict[str, Any]) -> None:
        op_type = str(record.get("operation_type"))
        key = (op_type, _series_name(op_type, str(record.get("operation_name"))))
        with self._lock:
            if key not in self.calls and len(self.calls) >= MAX_SERIES:
                key = (op_type, "other")
            if record.get("policy_decision") == "deny":
                self.calls[key]["denied"] += 1
                self.denial_reasons[str(record.get("policy_reason"))] += 1
            else:
                status = (
                    "error" if record.get("operation_status") == "error" else "success"
                )
                self.calls[key][status] += 1
            if record.get("duration_ms") is not None:
                self.latency[key].observe(float(record["duration_ms"]))

    def rate_limit_hit(self, scope: str) -> None:
        with self._lock:
            self.rate_limited[scope] += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            ops = []
            for (op_type, name), counts in sorted(self.calls.items()):
                hist = self.latency.get((op_type, name))
                total = sum(counts.values())
                ops.append(
                    {
                        "operation_type": op_type,
                        "operation_name": name,
                        **counts,
                        "total": total,
                        "error_rate": round(counts["error"] / total, 4)
                        if total
                        else 0.0,
                        "p50_ms": hist.percentile(0.5) if hist else None,
                        "p95_ms": hist.percentile(0.95) if hist else None,
                    }
                )
            return {
                "uptime_seconds": round(time.time() - self.started, 1),
                "operations": ops,
                "denial_reasons": dict(self.denial_reasons),
                "rate_limited": dict(self.rate_limited),
                "sink_errors": self.sink_errors,
            }

    def prometheus(self) -> str:
        snap = self.snapshot()
        lines = [
            "# HELP uml_mcp_operations_total MCP operations by outcome",
            "# TYPE uml_mcp_operations_total counter",
        ]
        for op in snap["operations"]:
            labels = f'type="{_label(op["operation_type"])}",name="{_label(op["operation_name"])}"'
            for outcome in ("success", "error", "denied"):
                lines.append(
                    f'uml_mcp_operations_total{{{labels},outcome="{outcome}"}} {op[outcome]}'
                )
        lines += [
            "# HELP uml_mcp_rate_limited_total Requests rejected by rate limiting",
            "# TYPE uml_mcp_rate_limited_total counter",
        ]
        for scope, count in snap["rate_limited"].items():
            lines.append(
                f'uml_mcp_rate_limited_total{{scope="{_label(scope)}"}} {count}'
            )
        lines.append(f"uml_mcp_uptime_seconds {snap['uptime_seconds']}")
        return "\n".join(lines) + "\n"


METRICS = Metrics()

__all__ = ["BUCKETS_MS", "METRICS", "Histogram", "Metrics"]
