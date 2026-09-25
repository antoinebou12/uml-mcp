"""Admin console backend: writable settings, reset, stop, logs, time series, guards."""

from __future__ import annotations

import logging
import os
import stat

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcp_core.admin import console, guards, routes, settings_service
from mcp_core.admin.api import build_local_admin_router
from mcp_core.core.settings_file import AppConfig, reset_config_cache
from mcp_core.observability.audit import configure_audit, get_audit_logger
from tests.fixtures_auth import build_auth_app, entra_v2_claims, mint

TOKEN = "test-setup-token-0123456789"
WRITE = {"Authorization": f"Bearer {TOKEN}", "X-UML-MCP-Admin": "1"}


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    # Reloading a saved file fills unset env vars (KROKI_SERVER, ...): restore them all.
    saved_env = dict(os.environ)
    path = tmp_path / "uml-mcp.yaml"
    path.write_text(
        "version: 1\nsetup: {profile: local}\naudit: {enabled: false}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("UML_MCP_CONFIG", str(path))
    monkeypatch.setenv(guards.TOKEN_ENV, TOKEN)
    guards.reset_setup_token()
    reset_config_cache()
    yield path
    os.environ.clear()
    os.environ.update(saved_env)
    reset_config_cache()
    guards.reset_setup_token()
    configure_audit(AppConfig())


@pytest.fixture
def local(cfg):
    app = FastAPI()
    app.include_router(build_local_admin_router())
    return TestClient(app, client=("127.0.0.1", 5000), base_url="http://127.0.0.1:8765")


def test_schema_describes_every_section(local):
    data = local.get("/admin/api/settings/schema").json()
    keys = [s["key"] for s in data["sections"]]
    assert keys[:2] == ["rendering", "server"] and "plugins" in keys
    audit = next(s for s in data["sections"] if s["key"] == "audit")
    assert audit["apply"] == "live"
    assert audit["schema"]["properties"]["enabled"]["description"]
    assert {f["key"] for f in data["features"]} >= {"audit", "rate_limit"}


def test_read_needs_loopback_and_localhost_host(cfg):
    app = FastAPI()
    app.include_router(build_local_admin_router())
    remote = TestClient(app, client=("10.0.0.2", 1), base_url="http://127.0.0.1")
    assert remote.get("/admin/api/settings").status_code == 404
    rebinding = TestClient(app, client=("127.0.0.1", 1), base_url="http://evil.example")
    assert rebinding.get("/admin/api/settings").status_code == 403
    from starlette.requests import Request

    scope = {
        "type": "http",
        "client": ("::1", 1),
        "headers": [(b"host", b"[::1]:8765")],
        "method": "GET",
        "path": "/",
    }
    guards.local_read(Request(scope))  # IPv6 loopback + bracketed Host is accepted


def test_writes_need_token_and_header(local):
    body = {"data": {"audit": {"enabled": True}}}
    assert local.put("/admin/api/settings", json=body).status_code == 403
    assert (
        local.put(
            "/admin/api/settings", json=body, headers={"X-UML-MCP-Admin": "1"}
        ).status_code
        == 401
    )
    bad = {"Authorization": "Bearer nope", "X-UML-MCP-Admin": "1"}
    assert local.put("/admin/api/settings", json=body, headers=bad).status_code == 401


def test_save_writes_file_applies_live_and_reports_restart(local, cfg):
    before = local.get("/admin/api/settings").json()
    assert before["writable"] and before["mode"] == "local"
    body = {
        "data": {
            "audit": {"enabled": True, "sinks": ["memory"]},
            "rendering": {"memory_only": True},
            "rate_limit": {"enabled": True},
        }
    }
    res = local.put("/admin/api/settings", json=body, headers=WRITE)
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["backup"] and "audit.enabled" in out["changed"]
    assert out["restart_required"] == ["rendering.memory_only"]
    assert "audit" in out["applied_live"]
    saved = yaml.safe_load(cfg.read_text())
    assert saved["audit"]["enabled"] is True and saved["setup"] == {"profile": "local"}
    assert stat.S_IMODE(cfg.stat().st_mode) == 0o600
    # audit is live: the save itself is on the Activity trail
    memory = get_audit_logger().memory
    assert memory is not None
    records = memory.records
    assert records[-1]["operation_name"] == "settings.save"
    after = local.get("/admin/api/settings").json()
    assert after["effective"]["audit"]["enabled"] is True
    assert "audit" in after["features"]


def test_invalid_and_readonly(local, cfg):
    bad = local.put(
        "/admin/api/settings",
        json={"data": {"audit": {"sinks": ["syslog"]}}},
        headers=WRITE,
    )
    assert bad.status_code == 422 and "audit.sinks" in bad.json()["detail"]
    typo = local.post(
        "/admin/api/settings/validate", json={"data": {"rendering": {"kroki": "x"}}}
    )
    assert typo.status_code == 422
    assert local.post(
        "/admin/api/settings/validate", json={"data": {"metrics": {"endpoint": True}}}
    ).json() == {"valid": True}
    assert (
        local.put("/admin/api/settings", content="[1]", headers=WRITE).status_code
        == 400
    )
    cfg.chmod(0o400)
    cfg.parent.chmod(0o500)
    try:
        res = local.put("/admin/api/settings", json={"data": {}}, headers=WRITE)
        if res.status_code != 200:  # root ignores permissions
            assert res.status_code == 409 and res.json()["error"] == "read_only"
    finally:
        cfg.parent.chmod(0o700)
        cfg.chmod(0o600)


def test_auth_secrets_are_still_rejected():
    from mcp_core.auth import AuthConfigError

    with pytest.raises(AuthConfigError):
        settings_service.validate({"auth": {"mode": "none", "client_secret": "x"}})


def test_save_preserves_auth_section(local, cfg):
    cfg.write_text("version: 1\nauth: {mode: none}\n", encoding="utf-8")
    reset_config_cache()
    assert local.get("/admin/api/settings").json()["has_auth_section"]
    assert (
        local.put(
            "/admin/api/settings",
            json={"data": {"metrics": {"enabled": True}}},
            headers=WRITE,
        ).status_code
        == 200
    )
    assert yaml.safe_load(cfg.read_text())["auth"] == {"mode": "none"}


def test_reset_section_and_all(local, cfg):
    local.put(
        "/admin/api/settings",
        json={"data": {"rate_limit": {"enabled": True}, "otel": {"enabled": True}}},
        headers=WRITE,
    )
    one = local.post(
        "/admin/api/settings/reset", json={"section": "otel"}, headers=WRITE
    )
    assert one.status_code == 200
    saved = yaml.safe_load(cfg.read_text())
    assert saved["otel"]["enabled"] is False and saved["rate_limit"]["enabled"] is True
    everything = local.post(
        "/admin/api/settings/reset", json={"profile": "docker"}, headers=WRITE
    )
    assert everything.status_code == 200
    saved = yaml.safe_load(cfg.read_text())
    assert (
        saved["setup"]["profile"] == "docker"
        and saved["rendering"]["memory_only"] is True
    )
    assert (
        local.post(
            "/admin/api/settings/reset", json={"section": "warp"}, headers=WRITE
        ).status_code
        == 422
    )


def test_setup_preview_and_status(local):
    prev = local.post(
        "/admin/api/setup/preview",
        json={"profile": "enterprise", "features": ["audit", "otel"]},
    ).json()
    assert prev["data"]["otel"]["enabled"] is True and "otel:" in prev["yaml"]
    assert (
        local.post("/admin/api/setup/preview", json={"profile": "x"}).status_code == 422
    )
    status = local.get("/admin/api/setup/status").json()
    assert status["exists"] and status["setup_complete"] is False


def test_stop_is_guarded_and_scheduled(local, monkeypatch):
    calls = []
    monkeypatch.setattr(routes, "schedule_stop", lambda delay=0.5: calls.append(delay))
    assert local.post("/admin/api/server/stop").status_code == 403
    res = local.post("/admin/api/server/stop", headers=WRITE)
    assert res.status_code == 202 and calls == [0.5]


def test_logs_are_redacted_and_filterable(local):
    from mcp_core.observability.logging_setup import attach_ring

    attach_ring()
    log = logging.getLogger("uml_mcp.test")
    log.setLevel(logging.INFO)
    log.warning(
        "login with client_secret=hunter2 and eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxIn0.sig"
    )
    log.info("plain info line")
    data = local.get(
        "/admin/api/logs", params={"level": "WARNING", "q": "login with"}
    ).json()
    msg = data["records"][-1]["message"]
    assert "hunter2" not in msg and "eyJhbGci" not in msg and "client_secret=***" in msg
    assert all(r["level"] != "INFO" for r in data["records"])
    after = local.get(
        "/admin/api/logs", params={"after": data["last_seq"], "q": "login with"}
    ).json()
    assert after["records"] == []
    log.warning("streamed line")
    with local.stream(
        "GET", "/admin/api/logs/stream", params={"max_seconds": 1, "q": "streamed"}
    ) as res:
        body = "".join(res.iter_text())
    assert res.headers["content-type"].startswith("text/event-stream")
    assert ": keep-alive" in body


def test_timeseries_and_client_install(local, monkeypatch):
    points = local.get("/admin/api/metrics/timeseries", params={"minutes": 5}).json()
    assert len(points["points"]) == 5 and {"calls", "errors", "p95_ms"} <= set(
        points["points"][0]
    )
    monkeypatch.setattr(
        "mcp_core.core.client_install.install",
        lambda client, dry_run=False: (
            "{}",
            None if client == "claude-code" else "/tmp/x.json",
        ),
    )
    res = local.post("/admin/api/clients/cursor?dry_run=1", headers=WRITE)
    assert res.status_code == 200 and res.json()["dry_run"] is True
    assert local.post("/admin/api/clients/cursor").status_code == 403


def test_enterprise_writes_need_opt_in(settings_factory, mock_idp, rsa_key, cfg):
    app = build_auth_app(settings_factory(MCP_ADMIN_UI="true"), http=mock_idp.client())
    client = TestClient(app)
    admin = {
        "Authorization": f"Bearer {mint(entra_v2_claims(roles=['MCP.Admin']), rsa_key)}"
    }
    user = {"Authorization": f"Bearer {mint(entra_v2_claims(), rsa_key)}"}
    assert client.get("/admin/api/settings", headers=user).status_code == 403
    assert (
        client.get("/admin/api/settings", headers=admin).json()["mode"] == "enterprise"
    )
    body = {"data": {"metrics": {"enabled": True}}}
    denied = client.put("/admin/api/settings", json=body, headers=admin)
    assert denied.status_code == 403 and "allow_write" in denied.text
    assert client.post("/admin/api/server/stop", headers=admin).status_code == 403
    assert client.post("/admin/api/clients/cursor", headers=admin).status_code == 403
    cfg.write_text("version: 1\nadmin: {allow_write: true}\n", encoding="utf-8")
    reset_config_cache()
    ok = client.put(
        "/admin/api/settings",
        json={"data": {"admin": {"allow_write": True}, "metrics": {"enabled": True}}},
        headers=admin,
    )
    assert ok.status_code == 200, ok.text
    assert get_audit_logger() is not None


def test_console_url_and_loopback_only(monkeypatch):
    url = console.console_url("127.0.0.1", 8765, "setup", "tok")
    assert url == "http://127.0.0.1:8765/admin/#/setup?token=tok"
    assert console.console_url("::1", 1, "overview", "t").startswith("http://[::1]:1/")
    with pytest.raises(SystemExit):
        console.run_console(host="0.0.0.0", open_browser=False)
    ran, opened = [], []
    monkeypatch.setattr(console, "build_console_app", lambda: "app")
    monkeypatch.setattr("uvicorn.run", lambda app, **kw: ran.append((app, kw)))
    monkeypatch.setattr(console.webbrowser, "open", opened.append)
    monkeypatch.setenv(guards.TOKEN_ENV, "tok")
    console.run_console(port=9999, page="setup")
    assert ran == [("app", {"host": "127.0.0.1", "port": 9999, "log_level": "warning"})]
    assert opened == ["http://127.0.0.1:9999/admin/#/setup?token=tok"]
