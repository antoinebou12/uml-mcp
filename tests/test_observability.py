"""MXCP-style audit trail, redaction, sinks/rotation, metrics and rate limiting."""

from __future__ import annotations

import asyncio
import io
import json
import logging

import pytest

from mcp_core.core.settings_file import (
    AppConfig,
    LimitConfig,
    RateLimitConfig,
    parse_app_config,
)
from mcp_core.observability.audit import (
    AuditLogger,
    ToolRateLimitedError,
    configure_audit,
    instrument,
)
from mcp_core.observability.context import current_context, reset_context, set_context
from mcp_core.observability.metrics import METRICS, Metrics
from mcp_core.observability.ratelimit import (
    LIMITER,
    TokenBucketLimiter,
    client_ip,
    rate_key,
    route_limit,
)
from mcp_core.observability.redaction import redact
from mcp_core.observability.sinks import StreamSink

MXCP_FIELDS = {
    "timestamp",
    "caller_type",
    "operation_type",
    "operation_name",
    "input_data",
    "duration_ms",
    "policy_decision",
    "policy_reason",
    "operation_status",
    "error",
    "user_id",
    "session_id",
}


@pytest.fixture
def memory_audit():
    app = parse_app_config({"audit": {"enabled": True, "sinks": ["memory"]}})
    logger = configure_audit(app)
    METRICS.reset()
    yield logger
    configure_audit(AppConfig())
    LIMITER.reset()


def test_record_has_all_mxcp_fields(memory_audit):
    token = set_context(
        caller_type="http",
        user_id="ada@contoso.com",
        session_id="s1",
        policy_decision="allow",
        policy_reason="write permission",
    )
    try:
        instrument(lambda code: {"ok": True}, "tool", "generate_uml")(
            code="graph TD; A-->B"
        )
    finally:
        reset_context(token)
    rec = memory_audit.memory.records[-1]
    assert MXCP_FIELDS <= set(rec)
    assert rec["caller_type"] == "http" and rec["operation_type"] == "tool"
    assert rec["operation_status"] == "success" and rec["policy_decision"] == "allow"
    assert rec["user_id"] == "ada@contoso.com" and rec["session_id"] == "s1"
    assert rec["input_data"]["code"]["chars"] == len("graph TD; A-->B")
    assert rec["timestamp"].endswith("Z") and rec["duration_ms"] >= 0


def test_errors_are_recorded_and_reraised(memory_audit):
    def boom(**_):
        raise ValueError("bad diagram")

    with pytest.raises(ValueError):
        instrument(boom, "tool", "validate_uml")(code="x")
    rec = memory_audit.memory.records[-1]
    assert rec["operation_status"] == "error" and "bad diagram" in rec["error"]
    assert current_context().policy_decision == "n/a"  # default when auth is off


def test_async_functions_are_instrumented(memory_audit):
    async def resource():
        return "ok"

    assert asyncio.run(instrument(resource, "resource", "uml://types")()) == "ok"
    assert memory_audit.memory.records[-1]["operation_type"] == "resource"


def test_redaction():
    data = {
        "access_token": "abc",
        "nested": {"client_secret": "s"},
        "note": "Bearer eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxIn0.sig",
        "code": "x" * 500,
    }
    out = redact(data)
    assert out["access_token"] == "***" and out["nested"]["client_secret"] == "***"
    assert "eyJ" not in json.dumps(out)
    assert set(out["code"]) == {"sha256", "chars", "preview"}
    assert redact(data, mode="none") is None
    assert redact({"code": "y" * 50}, mode="full", max_chars=10)["code"].endswith("…")


def test_disabled_audit_still_counts_metrics():
    logger = AuditLogger(AppConfig())
    METRICS.reset()
    assert logger.record(operation_type="tool", operation_name="t") is None
    assert METRICS.snapshot()["operations"][0]["total"] == 1


def test_stream_sink_uses_stderr_for_stdio(capsys):
    StreamSink(stdio_transport=True).write({"a": 1})
    captured = capsys.readouterr()
    assert captured.out == "" and '"audit"' in captured.err
    buf = io.StringIO()
    StreamSink(buf).write({"b": 2})
    assert json.loads(buf.getvalue())["audit"] == {"b": 2}


def test_jsonl_file_rotation(tmp_path):
    path = tmp_path / "audit" / "audit.jsonl"
    app = parse_app_config(
        {
            "audit": {
                "enabled": True,
                "sinks": ["file"],
                "file": {"path": str(path), "max_bytes": 400, "backup_count": 2},
            }
        }
    )
    logger = AuditLogger(app)
    for i in range(20):
        logger.record(
            operation_type="tool", operation_name=f"t{i}", input_data={"i": i}
        )
    logger.close()
    files = sorted(p.name for p in path.parent.iterdir())
    assert files == ["audit.jsonl", "audit.jsonl.1", "audit.jsonl.2"]
    last = json.loads(path.read_text().strip().splitlines()[-1])
    assert last["operation_name"] == "t19"


def test_compressed_rotation_keeps_backup_count(tmp_path):
    import gzip

    path = tmp_path / "audit.jsonl"
    app = parse_app_config(
        {
            "audit": {
                "enabled": True,
                "sinks": ["file"],
                "file": {
                    "path": str(path),
                    "max_bytes": 300,
                    "backup_count": 3,
                    "compress": True,
                },
            }
        }
    )
    logger = AuditLogger(app)
    for i in range(40):
        logger.record(
            operation_type="tool", operation_name=f"t{i}", input_data={"i": i}
        )
    logger.close()
    files = sorted(p.name for p in tmp_path.iterdir())
    assert files == [
        "audit.jsonl",
        "audit.jsonl.1.gz",
        "audit.jsonl.2.gz",
        "audit.jsonl.3.gz",
    ]
    with gzip.open(tmp_path / "audit.jsonl.1.gz", "rt") as fh:
        assert json.loads(fh.readline())["operation_type"] == "tool"
    assert oct(path.stat().st_mode & 0o777) == "0o600"


def test_error_result_dict_is_audited_as_error(memory_audit):
    fn = instrument(lambda: {"error": "Kroki unavailable"}, "tool", "generate_uml")
    assert fn() == {"error": "Kroki unavailable"}  # result is passed through untouched
    rec = memory_audit.memory.records[-1]
    assert rec["operation_status"] == "error" and rec["error"] == "Kroki unavailable"
    assert METRICS.snapshot()["operations"][-1]["error"] == 1


def test_reconfiguring_keeps_activity_history(memory_audit):
    instrument(lambda: "ok", "tool", "generate_uml")()
    kept = parse_app_config(
        {"audit": {"enabled": True, "sinks": ["memory"], "memory_size": 50}}
    )
    logger = configure_audit(kept)
    assert logger.memory is not None
    assert [r["operation_name"] for r in logger.memory.records] == ["generate_uml"]


def test_broken_sink_never_breaks_calls(memory_audit):
    class Broken:
        def write(self, record):
            raise OSError("disk full")

        def close(self):
            return None

    memory_audit.sinks.append(Broken())
    assert instrument(lambda: 1, "tool", "t")() == 1
    assert METRICS.snapshot()["sink_errors"] == 1


def test_metrics_percentiles_and_prometheus():
    m = Metrics()
    for ms in (1, 20, 30, 400):
        m.observe(
            {
                "operation_type": "tool",
                "operation_name": "g",
                "duration_ms": ms,
                "operation_status": "success",
                "policy_decision": "allow",
            }
        )
    m.observe(
        {
            "operation_type": "tool",
            "operation_name": "g",
            "policy_decision": "deny",
            "policy_reason": "insufficient_scope",
        }
    )
    op = m.snapshot()["operations"][0]
    assert op["total"] == 5 and op["denied"] == 1 and op["p50_ms"] == 25.0
    text = m.prometheus()
    assert 'uml_mcp_operations_total{type="tool",name="g",outcome="denied"} 1' in text


def test_metrics_are_bounded_json_safe_and_escaped():
    import mcp_core.observability.metrics as metrics_mod

    m = Metrics()
    for run in range(5):  # per-run paths collapse into one series
        m.observe(
            {
                "operation_type": "http",
                "operation_name": f"GET /ag-ui/events/{run}",
                "operation_status": "success",
                "duration_ms": 45_000,
            }
        )
    ops = m.snapshot()["operations"]
    assert [o["operation_name"] for o in ops] == ["GET /ag-ui/events"]
    assert ops[0]["p95_ms"] == 30000.0  # overflow bucket, not inf
    json.dumps(m.snapshot(), allow_nan=False)
    for i in range(metrics_mod.MAX_SERIES + 5):  # attacker-chosen tool names
        m.observe(
            {
                "operation_type": "tool",
                "operation_name": f'x"{i}\n',
                "operation_status": "error",
            }
        )
    names = {o["operation_name"] for o in m.snapshot()["operations"]}
    assert len(names) <= metrics_mod.MAX_SERIES + 1 and "other" in names
    text = m.prometheus()
    assert 'name="x\\"0\\n"' in text and '\n"' not in text


def test_token_bucket_and_burst():
    clock = [0.0]
    lim = TokenBucketLimiter(clock=lambda: clock[0])
    cfg = LimitConfig(requests_per_minute=60, burst=2)
    assert [lim.check("s", "k", cfg).allowed for _ in range(3)] == [True, True, False]
    clock[0] += 1.0  # one token per second
    assert lim.check("s", "k", cfg).allowed
    assert lim.check("s", "other", cfg).allowed  # separate key


def test_client_ip_trusted_proxies():
    assert client_ip("10.0.0.5", "203.0.113.9", ["10.0.0.0/8"]) == "203.0.113.9"
    assert (
        client_ip("198.51.100.1", "203.0.113.9", ["10.0.0.0/8"]) == "198.51.100.1"
    )  # spoof
    assert (
        client_ip("10.0.0.5", "203.0.113.9, 10.0.0.7", ["10.0.0.0/8"]) == "203.0.113.9"
    )


def test_rate_keys_and_routes():
    cfg = RateLimitConfig(
        enabled=True,
        key="principal",
        routes={"/oauth/token": LimitConfig(requests_per_minute=5)},
    )
    assert rate_key(cfg, "1.2.3.4", None) == "ip:1.2.3.4"
    assert rate_key(cfg, "1.2.3.4", "Bearer x").startswith("tok:")
    assert route_limit(cfg, "/health") is None
    token_route = route_limit(cfg, "/oauth/token")
    default_route = route_limit(cfg, "/mcp")
    assert token_route is not None and token_route[0] == "route:/oauth/token"
    assert default_route is not None and default_route[0] == "default"


def test_tool_level_rate_limit(memory_audit):
    app = parse_app_config(
        {
            "audit": {"enabled": True},
            "rate_limit": {
                "enabled": True,
                "tools": {"generate_uml": {"requests_per_minute": 1}},
            },
        }
    )
    logger = configure_audit(app)
    fn = instrument(lambda: "ok", "tool", "generate_uml")
    assert fn() == "ok"
    with pytest.raises(ToolRateLimitedError):
        fn()
    assert logger.memory is not None
    assert logger.memory.records[-1]["policy_reason"] == "rate_limited"


def test_http_middleware_config_limits_and_headers(monkeypatch):
    from starlette.applications import Starlette
    from starlette.responses import PlainTextResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient

    import mcp_core.core.settings_file as sf
    from mcp_core.core.http_observability import RequestIdAndRateLimitMiddleware

    app_cfg = parse_app_config(
        {"rate_limit": {"enabled": True, "default": {"requests_per_minute": 2}}}
    )
    monkeypatch.setattr(sf, "get_app_config", lambda: app_cfg)
    LIMITER.reset()

    async def ok(_):
        return PlainTextResponse(current_context().caller_type)

    app = Starlette(routes=[Route("/mcp", ok, methods=["POST"]), Route("/health", ok)])
    app.add_middleware(RequestIdAndRateLimitMiddleware)
    c = TestClient(app)
    first = c.post("/mcp")
    assert first.text == "http" and first.headers["RateLimit-Limit"] == "2"
    c.post("/mcp")
    limited = c.post("/mcp")
    assert limited.status_code == 429 and "Retry-After" in limited.headers
    assert c.get("/health").status_code == 200  # exempt
    LIMITER.reset()


def test_bogus_tokens_cannot_spray_fresh_buckets(monkeypatch):
    """key=principal: every 401 charges a per-IP bucket, so random tokens get throttled."""
    from starlette.applications import Starlette
    from starlette.responses import PlainTextResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient

    import mcp_core.core.settings_file as sf
    from mcp_core.core.http_observability import RequestIdAndRateLimitMiddleware

    app_cfg = parse_app_config(
        {
            "rate_limit": {
                "enabled": True,
                "key": "principal",
                "auth_failures_per_minute": 3,
                "default": {"requests_per_minute": 100},
            }
        }
    )
    monkeypatch.setattr(sf, "get_app_config", lambda: app_cfg)
    LIMITER.reset()

    async def unauthorized(request):
        ok = request.headers.get("authorization") == "Bearer good"
        return PlainTextResponse("ok" if ok else "no", status_code=200 if ok else 401)

    app = Starlette(routes=[Route("/mcp", unauthorized, methods=["POST"])])
    app.add_middleware(RequestIdAndRateLimitMiddleware)
    c = TestClient(app)
    statuses = [
        c.post("/mcp", headers={"Authorization": f"Bearer bogus{i}"}).status_code
        for i in range(5)
    ]
    assert statuses[:3] == [401, 401, 401] and statuses[3:] == [429, 429]
    # a key=ip deployment is unaffected by the extra bucket
    LIMITER.reset()
    assert c.post("/mcp", headers={"Authorization": "Bearer good"}).status_code == 200
    LIMITER.reset()


def test_tool_limit_uses_verified_user_for_principal_key(memory_audit):
    app = parse_app_config(
        {
            "audit": {"enabled": True},
            "rate_limit": {
                "enabled": True,
                "key": "principal",
                "tools": {"generate_uml": {"requests_per_minute": 1}},
            },
        }
    )
    configure_audit(app)
    fn = instrument(lambda: "ok", "tool", "generate_uml")
    for token in ("tok:a", "tok:b"):  # same user, rotated tokens -> same bucket
        ctx = set_context(user_id="ada", rate_key=token)
        try:
            if token == "tok:a":
                assert fn() == "ok"
            else:
                with pytest.raises(ToolRateLimitedError):
                    fn()
        finally:
            reset_context(ctx)


def test_logging_json_formatter(tmp_path):
    from mcp_core.core.settings_file import LoggingConfig
    from mcp_core.observability.logging_setup import configure_logging

    root = logging.getLogger()
    saved = root.handlers[:], root.level
    try:
        cfg = LoggingConfig(
            format="json",
            file={"path": str(tmp_path / "s.log")},
            loggers={"httpx": "WARNING"},
        )
        configure_logging(cfg)
        logging.getLogger("x").info("token eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxIn0.sig")
        for h in root.handlers:
            h.flush()
        line = json.loads((tmp_path / "s.log").read_text().splitlines()[-1])
        assert line["logger"] == "x" and "eyJ" not in line["message"]
        assert logging.getLogger("httpx").level == logging.WARNING
    finally:
        for h in root.handlers:
            h.close()
        root.handlers, lvl = saved
        root.setLevel(lvl)
