"""Optional OpenTelemetry tracing: spans per MCP operation and HTTP request."""

from __future__ import annotations

import pytest

pytest.importorskip("opentelemetry.sdk.trace")

from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from mcp_core.core.settings_file import (
    AppConfig,
    OtelConfig,
    parse_app_config,
)
from mcp_core.observability import otel
from mcp_core.observability.audit import configure_audit, instrument
from mcp_core.observability.context import reset_context, set_context

TRACEPARENT = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"


@pytest.fixture
def spans():
    exporter = InMemorySpanExporter()
    app = parse_app_config({"otel": {"enabled": True, "include_user": True}})
    configure_audit(app)
    assert otel.configure_otel(app.otel, version="1.4.0", exporter=exporter)
    yield exporter
    configure_audit(AppConfig())
    assert not otel.enabled()


def test_disabled_is_noop():
    assert otel.configure_otel(OtelConfig()) is False
    with otel.span("x") as current:
        assert current is None


def test_tool_span_carries_audit_attributes(spans):
    token = set_context(
        user_id="ada@contoso.com", policy_decision="allow", session_id="s1"
    )
    try:
        instrument(lambda code: {"ok": 1}, "tool", "generate_uml")(code="secret source")
    finally:
        reset_context(token)
    (span,) = spans.get_finished_spans()
    attrs = dict(span.attributes or {})
    assert span.name == "tool generate_uml"
    assert attrs["mcp.operation.name"] == "generate_uml"
    assert (
        attrs["mcp.operation_status"] == "success"
        and attrs["mcp.policy_decision"] == "allow"
    )
    assert attrs["enduser.id"] == "ada@contoso.com" and attrs["mcp.session_id"] == "s1"
    assert "secret source" not in str(attrs)  # inputs never reach traces
    assert span.resource.attributes["service.version"] == "1.4.0"


def test_error_results_and_exceptions_mark_span_error(spans):
    from opentelemetry.trace import StatusCode

    instrument(lambda: {"error": "Kroki down"}, "tool", "generate_uml")()

    def boom():
        raise RuntimeError("kaput")

    with pytest.raises(RuntimeError):
        instrument(boom, "tool", "validate_uml")()
    statuses = [s.status.status_code for s in spans.get_finished_spans()]
    assert statuses == [StatusCode.ERROR, StatusCode.ERROR]


def test_http_span_joins_caller_trace(spans, monkeypatch):
    from starlette.applications import Starlette
    from starlette.responses import PlainTextResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient

    from mcp_core.core.http_observability import RequestIdAndRateLimitMiddleware

    async def ok(_):
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/ag-ui/events/{rid}", ok)])
    app.add_middleware(RequestIdAndRateLimitMiddleware)
    TestClient(app).get("/ag-ui/events/run-123", headers={"traceparent": TRACEPARENT})
    (span,) = spans.get_finished_spans()
    assert span.name == "GET /ag-ui/events"  # bounded span name
    assert format(span.context.trace_id, "032x") == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert span.attributes["http.response.status_code"] == 200


def test_lint_flags_missing_extra(monkeypatch):
    from mcp_core.quality.lint import lint_config

    monkeypatch.setattr(otel, "otel_available", lambda: False)
    app = parse_app_config({"otel": {"enabled": True}})
    assert "CFG010" in {i.code for i in lint_config(app, None, {})}
