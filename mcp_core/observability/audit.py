"""MXCP-style audit trail for every tool, resource, prompt (and REST) execution.

Fields (all records): ``timestamp``, ``caller_type``, ``operation_type``,
``operation_name``, ``input_data`` (redacted), ``duration_ms``,
``policy_decision``, ``policy_reason``, ``operation_status``, ``error``,
``user_id``, ``session_id`` plus ``request_id``, ``tenant_id``, ``client_id``
and ``server_version``.
"""

from __future__ import annotations

import datetime as _dt
import functools
import inspect
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

from ..core.settings_file import AppConfig, get_app_config
from . import otel
from .context import current_context
from .metrics import METRICS
from .ratelimit import LIMITER
from .redaction import redact
from .sinks import JsonlFileSink, MemorySink, Sink, StreamSink

logger = logging.getLogger(__name__)


@dataclass
class AuditRecord:
    timestamp: str
    caller_type: str
    operation_type: str
    operation_name: str
    input_data: Any
    duration_ms: float | None
    policy_decision: str
    policy_reason: str | None
    operation_status: str
    error: str | None
    user_id: str | None
    session_id: str | None
    request_id: str | None = None
    tenant_id: str | None = None
    client_id: str | None = None
    server_version: str | None = None


def utc_now() -> str:
    return (
        _dt.datetime.now(_dt.UTC)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


class ToolRateLimitedError(RuntimeError):
    """Raised inside a tool call when its configured per-tool limit is exceeded."""


class AuditLogger:
    def __init__(self, app: AppConfig, *, stdio: bool = False):
        self.app = app
        self.stdio = stdio
        self.enabled = app.audit.enabled
        self.metrics_enabled = app.metrics.enabled
        self.memory: MemorySink | None = None
        self.sinks: list[Sink] = []
        if self.enabled:
            for name in dict.fromkeys(app.audit.sinks):
                if name == "memory":
                    self.memory = MemorySink(app.audit.memory_size)
                    self.sinks.append(self.memory)
                elif name == "stream":
                    self.sinks.append(StreamSink(stdio_transport=stdio))
                elif name == "file":
                    if app.audit.file is None:
                        raise ValueError(
                            "audit.sinks contains 'file' but audit.file is not set"
                        )
                    self.sinks.append(JsonlFileSink(app.audit.file))
        try:
            from ..core.config import MCP_SETTINGS

            self.version: str | None = MCP_SETTINGS.version
        except Exception:  # noqa: BLE001
            self.version = None
        otel.configure_otel(app.otel, version=self.version or "")

    def record(
        self,
        *,
        operation_type: str,
        operation_name: str,
        input_data: Any = None,
        duration_ms: float | None = None,
        operation_status: str = "success",
        error: str | None = None,
        policy_decision: str | None = None,
        policy_reason: str | None = None,
    ) -> dict[str, Any] | None:
        ctx = current_context()
        rec = asdict(
            AuditRecord(
                timestamp=utc_now(),
                caller_type=ctx.caller_type,
                operation_type=operation_type,
                operation_name=operation_name,
                input_data=redact(
                    input_data,
                    mode=self.app.audit.include_inputs,
                    max_chars=self.app.audit.max_input_chars,
                ),
                duration_ms=None if duration_ms is None else round(duration_ms, 2),
                policy_decision=policy_decision or ctx.policy_decision,
                policy_reason=policy_reason
                if policy_reason is not None
                else ctx.policy_reason,
                operation_status=operation_status,
                error=None if error is None else str(redact(error, max_chars=300)),
                user_id=ctx.user_id,
                session_id=ctx.session_id,
                request_id=ctx.request_id,
                tenant_id=ctx.tenant_id,
                client_id=ctx.client_id,
                server_version=self.version,
            )
        )
        if self.metrics_enabled:
            METRICS.observe(rec)
        otel.annotate_current(rec, self.app.otel.include_user)
        if not self.enabled:
            return None
        for sink in self.sinks:
            try:
                sink.write(rec)
            except Exception:
                METRICS.sink_errors += 1
                logger.exception("audit sink %s failed", type(sink).__name__)
        return rec

    def close(self) -> None:
        for sink in self.sinks:
            sink.close()


_LOCK = threading.Lock()
_LOGGER: AuditLogger | None = None


def configure_audit(
    app: AppConfig | None = None, *, stdio: bool = False
) -> AuditLogger:
    global _LOGGER
    with _LOCK:
        previous = _LOGGER.memory if _LOGGER is not None else None
        if _LOGGER is not None:
            _LOGGER.close()
        _LOGGER = AuditLogger(app or get_app_config(), stdio=stdio)
        if previous is not None and _LOGGER.memory is not None:
            # Reconfiguring (e.g. saving settings) must not wipe the Activity history.
            _LOGGER.memory.records.extend(previous.records)
        return _LOGGER


def get_audit_logger() -> AuditLogger:
    return _LOGGER or configure_audit()


def record_operation(**kwargs: Any) -> dict[str, Any] | None:
    return get_audit_logger().record(**kwargs)


def _check_tool_limit(name: str) -> None:
    app = get_audit_logger().app
    limit = app.rate_limit.tools.get(name)
    if not (app.rate_limit.enabled and limit):
        return
    ctx = current_context()
    if app.rate_limit.key == "principal" and ctx.user_id:
        key = f"user:{ctx.user_id}"  # verified identity (set after token validation)
    else:
        key = ctx.rate_key or "local"
    decision = LIMITER.check(f"tool:{name}", key, limit)
    if not decision.allowed:
        METRICS.rate_limit_hit(f"tool:{name}")
        raise ToolRateLimitedError(
            f"Rate limit exceeded for tool '{name}' "
            f"({limit.requests_per_minute}/min); retry in {decision.reset_seconds}s"
        )


def instrument(
    func: Callable[..., Any], operation_type: str, name: str
) -> Callable[..., Any]:
    """Wrap ``func`` so every call is timed, rate limited (tools) and audited."""

    def _finish(
        start: float,
        kwargs: dict[str, Any],
        exc: BaseException | None,
        result: Any = None,
    ) -> None:
        # Tools report failures as {"error": ...}; the MCP adapter turns that into
        # a ToolError after this wrapper returns, so treat it as an error here.
        failed = (
            str(result["error"])
            if isinstance(result, dict) and result.get("error")
            else None
        )
        if exc is not None:
            failed = f"{type(exc).__name__}: {exc}"
        record_operation(
            operation_type=operation_type,
            operation_name=name,
            input_data=kwargs,
            duration_ms=(time.perf_counter() - start) * 1000,
            operation_status="error" if failed else "success",
            error=failed,
            **(
                {"policy_decision": "deny", "policy_reason": "rate_limited"}
                if isinstance(exc, ToolRateLimitedError)
                else {}
            ),
        )

    span_name = f"{operation_type} {name}"
    span_attrs = {"mcp.operation.type": operation_type, "mcp.operation.name": name}

    if inspect.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            with otel.span(span_name, span_attrs):
                try:
                    if operation_type == "tool":
                        _check_tool_limit(name)
                    result = await func(*args, **kwargs)
                except BaseException as exc:
                    _finish(start, kwargs, exc)
                    raise
                _finish(start, kwargs, None, result)
                return result

        return async_wrapper

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        with otel.span(span_name, span_attrs):
            try:
                if operation_type == "tool":
                    _check_tool_limit(name)
                result = func(*args, **kwargs)
            except BaseException as exc:
                _finish(start, kwargs, exc)
                raise
            _finish(start, kwargs, None, result)
            return result

    return wrapper


__all__ = [
    "AuditLogger",
    "AuditRecord",
    "ToolRateLimitedError",
    "configure_audit",
    "get_audit_logger",
    "instrument",
    "record_operation",
    "utc_now",
]
