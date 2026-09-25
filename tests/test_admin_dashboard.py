"""Admin dashboard operations API (audit, metrics, limits, config, lint, tools)."""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcp_core.admin.api import build_local_admin_router, metrics_response
from mcp_core.core.settings_file import AppConfig, parse_app_config
from mcp_core.observability.audit import configure_audit, instrument
from mcp_core.observability.metrics import METRICS
from tests.fixtures_auth import build_auth_app, entra_v2_claims, mint

OPS = [
    "/admin/api/audit",
    "/admin/api/audit/export",
    "/admin/api/metrics",
    "/admin/api/rate-limits",
    "/admin/api/config",
    "/admin/api/config/download",
    "/admin/api/lint",
    "/admin/api/tools",
]


@pytest.fixture
def audit_on():
    configure_audit(parse_app_config({"audit": {"enabled": True, "sinks": ["memory"]}}))
    METRICS.reset()
    ok = instrument(lambda code: "ok", "tool", "generate_uml")
    ok(code="A->B")

    def boom():
        raise RuntimeError("kaput")

    with pytest.raises(RuntimeError):
        instrument(boom, "tool", "validate_uml")()
    yield
    configure_audit(AppConfig())


@pytest.fixture
def admin(settings_factory, mock_idp, rsa_key):
    app = build_auth_app(settings_factory(MCP_ADMIN_UI="true"), http=mock_idp.client())
    app.add_api_route("/metrics", metrics_response, methods=["GET"])
    client = TestClient(app)
    admin_tok = mint(entra_v2_claims(roles=["MCP.Admin"]), rsa_key)
    user_tok = mint(entra_v2_claims(), rsa_key)
    return (
        client,
        {"Authorization": f"Bearer {admin_tok}"},
        {"Authorization": f"Bearer {user_tok}"},
    )


@pytest.mark.parametrize("path", [*OPS, "/metrics"])
def test_ops_endpoints_require_admin(admin, path):
    client, admin_h, user_h = admin
    assert client.get(path).status_code == 401
    assert client.get(path, headers=user_h).status_code == 403
    r = client.get(path, headers=admin_h)
    assert r.status_code == 200
    if path.startswith("/admin/api"):
        assert r.headers["cache-control"] == "no-store"


def test_audit_filters_and_export(admin, audit_on):
    client, h, _ = admin
    body = client.get("/admin/api/audit", headers=h).json()
    assert body["enabled"] is True
    names = [r["operation_name"] for r in body["records"]]
    assert {"generate_uml", "validate_uml"} <= set(names)
    errors = client.get("/admin/api/audit?status=error", headers=h).json()["records"]
    assert errors and all(r["operation_status"] == "error" for r in errors)
    one = client.get(
        "/admin/api/audit?operation=generate_uml&limit=1", headers=h
    ).json()
    assert [r["operation_name"] for r in one["records"]] == ["generate_uml"]
    export = client.get("/admin/api/audit/export", headers=h)
    assert export.headers["content-type"].startswith("application/x-ndjson")
    assert "attachment" in export.headers["content-disposition"]
    lines = [json.loads(line) for line in export.text.splitlines()]
    assert any(line["operation_status"] == "error" for line in lines)
    # the bearer token never lands in the trail
    assert h["Authorization"].split()[1] not in export.text


def test_audit_disabled_hint(admin):
    configure_audit(AppConfig())
    client, h, _ = admin
    body = client.get("/admin/api/audit", headers=h).json()
    assert body["enabled"] is False and "memory" in body["hint"]


def test_metrics_limits_config_lint_tools(admin, audit_on):
    client, h, _ = admin
    m = client.get("/admin/api/metrics", headers=h).json()
    assert m["operations"]
    rl = client.get("/admin/api/rate-limits", headers=h).json()
    assert {"policy", "hot_keys", "rejected"} <= set(rl)
    cfg = client.get("/admin/api/config", headers=h).json()
    assert "auth" not in cfg["sections"]
    assert cfg["sources"]["rendering.kroki_server"]["env"] == "KROKI_SERVER"
    yaml_text = client.get("/admin/api/config/download", headers=h).text
    assert yaml_text.startswith("# Effective uml-mcp.yaml")
    assert isinstance(client.get("/admin/api/lint", headers=h).json(), list)
    tools = {t["name"]: t for t in client.get("/admin/api/tools", headers=h).json()}
    assert tools["validate_uml"]["permission"] == "read"
    assert tools["generate_uml"]["permission"] == "write"
    prom = client.get("/metrics", headers=h).text
    assert "uml_mcp_" in prom


def _local_app() -> FastAPI:
    app = FastAPI()
    app.include_router(build_local_admin_router())
    return app


def test_local_dashboard_loopback_only():
    local = TestClient(
        _local_app(), client=("127.0.0.1", 5000), base_url="http://127.0.0.1"
    )
    assert local.get("/admin").status_code == 200
    assert local.get("/admin/favicon.svg").status_code == 200
    ov = local.get("/admin/api/overview").json()
    assert ov["local"] is True and ov["mode"] == "none"
    assert local.get("/admin/api/tools").status_code == 200
    ipv6 = TestClient(_local_app(), client=("::1", 5000), base_url="http://127.0.0.1")
    assert ipv6.get("/admin/api/metrics").status_code == 200
    remote = TestClient(
        _local_app(), client=("10.1.2.3", 5000), base_url="http://127.0.0.1"
    )
    for path in ("/admin", "/admin/api/overview", "/admin/api/audit"):
        assert remote.get(path).status_code == 404
    named = TestClient(
        _local_app(), client=("testclient", 5000), base_url="http://127.0.0.1"
    )
    assert named.get("/admin/api/overview").status_code == 404
