"""Optional OpenTelemetry tracing (``otel:`` in uml-mcp.yaml).

One span per MCP tool/resource/prompt call and per HTTP request, carrying the
same attributes as the audit trail (never inputs, never tokens). W3C
``traceparent`` from callers is honoured. Without ``uml-mcp[otel]`` installed,
or with ``otel.enabled: false``, every helper is a cheap no-op.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Iterator, Mapping
from typing import Any

from ..core.settings_file import OtelConfig

logger = logging.getLogger(__name__)
_TRACER: Any = None


def otel_available() -> bool:
    try:
        import opentelemetry.sdk.trace  # noqa: F401
    except ImportError:
        return False
    return True


def configure_otel(cfg: OtelConfig, *, version: str = "", exporter: Any = None) -> bool:
    """Install a tracer provider; returns False when disabled or unavailable."""
    global _TRACER
    _TRACER = None
    if not cfg.enabled:
        return False
    if not otel_available():
        logger.warning("otel.enabled is true but uml-mcp[otel] is not installed")
        return False
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
    from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

    resource = Resource.create(
        {
            "service.name": cfg.service_name,
            "service.version": version,
            **cfg.resource_attributes,
        }
    )
    provider = TracerProvider(
        resource=resource, sampler=ParentBased(TraceIdRatioBased(cfg.sample_ratio))
    )
    if exporter is not None:  # tests / custom exporters
        provider.add_span_processor(SimpleSpanProcessor(exporter))
    elif cfg.exporter == "console":
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter

        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    else:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        endpoint = cfg.endpoint.rstrip("/") + "/v1/traces" if cfg.endpoint else None
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
        )
    # A private tracer (not the global provider) keeps host apps' OTel setup intact.
    _TRACER = provider.get_tracer("uml-mcp", version)
    return True


def enabled() -> bool:
    return _TRACER is not None


@contextlib.contextmanager
def span(
    name: str,
    attributes: Mapping[str, Any] | None = None,
    carrier: Mapping[str, str] | None = None,
    kind: str = "internal",
) -> Iterator[Any]:
    """Start a span (child of ``carrier``'s traceparent when given)."""
    if _TRACER is None:
        yield None
        return
    from opentelemetry import propagate
    from opentelemetry.trace import SpanKind, Status, StatusCode

    ctx = propagate.extract(dict(carrier)) if carrier else None
    attrs = {k: v for k, v in (attributes or {}).items() if v is not None}
    span_kind = SpanKind.SERVER if kind == "server" else SpanKind.INTERNAL
    with _TRACER.start_as_current_span(
        name, context=ctx, kind=span_kind, attributes=attrs
    ) as current:
        try:
            yield current
        except BaseException as exc:
            current.set_status(Status(StatusCode.ERROR, type(exc).__name__))
            current.record_exception(exc)
            raise


def annotate_current(record: Mapping[str, Any], include_user: bool) -> None:
    """Copy an audit record's outcome onto the active span (no inputs, no tokens)."""
    if _TRACER is None:
        return
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode

    current = trace.get_current_span()
    if not current.is_recording():
        return
    for key in (
        "operation_status",
        "policy_decision",
        "policy_reason",
        "caller_type",
        "session_id",
        "request_id",
        "client_id",
        "tenant_id",
        "duration_ms",
    ):
        if record.get(key) is not None:
            current.set_attribute(
                f"mcp.{key}", record[key] if key == "duration_ms" else str(record[key])
            )
    if include_user and record.get("user_id"):
        current.set_attribute("enduser.id", str(record["user_id"]))
    if record.get("operation_status") == "error":
        current.set_status(
            Status(StatusCode.ERROR, str(record.get("error") or "")[:200])
        )


__all__ = ["annotate_current", "configure_otel", "enabled", "otel_available", "span"]
