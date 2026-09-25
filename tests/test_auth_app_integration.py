"""app.py integration: none mode unchanged, auth mode fails closed, server guards."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.fixtures_auth import API_CLIENT, TENANT

ROOT = Path(__file__).resolve().parents[1]


def run_app(env_extra: dict[str, str], code: str) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("MCP_AUTH")}
    env.update({"TESTING": "1", "MOCK_FASTMCP": "1", "PYTHONPATH": str(ROOT)})
    env.pop("VERCEL", None)
    env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_none_mode_does_not_load_auth_submodules():
    code = (
        "import sys, app\n"
        "loaded = sorted(m for m in sys.modules if m.startswith('mcp_core.auth.'))\n"
        "paths = sorted(getattr(r, 'path', '') for r in app.app.routes)\n"
        "print(loaded)\n"
        "assert not [p for p in paths if 'oauth' in p or p.startswith('/admin')], paths\n"
    )
    proc = run_app({}, code)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip().splitlines()[-1] == "[]"


def test_jwt_mode_protects_mcp():
    code = (
        "from fastapi.testclient import TestClient\n"
        "import app, json\n"
        "c = TestClient(app.app)\n"
        "r = c.post('/mcp', json={'jsonrpc':'2.0','id':1,'method':'ping'})\n"
        "print(json.dumps({'status': r.status_code, 'www': r.headers.get('www-authenticate'),\n"
        "  'prm': c.get('/.well-known/oauth-protected-resource/mcp').json(),\n"
        "  'health': c.get('/health').json(), 'root': c.get('/').status_code}))\n"
    )
    proc = run_app(
        {
            "MCP_AUTH_MODE": "jwt",
            "MCP_AUTH_RESOURCE_URL": "https://mcp.contoso.com/mcp",
            "MCP_AUTH_ENTRA_TENANT_ID": TENANT,
            "MCP_AUTH_ENTRA_CLIENT_ID": API_CLIENT,
            "MCP_AUTH_PREFLIGHT": "off",
        },
        code,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout.strip().splitlines()[-1])
    assert out["status"] == 401
    assert (
        'resource_metadata="https://mcp.contoso.com/.well-known/oauth-protected-resource/mcp"'
        in out["www"]
    )
    assert out["prm"]["resource"] == "https://mcp.contoso.com/mcp"
    assert out["health"]["auth"]["mode"] == "jwt"
    assert out["root"] == 200  # public pages stay public


def test_invalid_auth_config_fails_import():
    proc = run_app({"MCP_AUTH_MODE": "jwt"}, "import app")
    assert proc.returncode != 0
    assert "resource_url is required" in proc.stderr


def test_vercel_with_auth_is_refused():
    proc = run_app(
        {"VERCEL": "1", "MCP_AUTH_MODE": "jwt"},
        "import mcp_core.core.server",
    )
    assert proc.returncode != 0 and "not supported on Vercel" in proc.stderr


def test_http_transport_refuses_to_bypass_auth(monkeypatch):
    from mcp_core.core import server

    monkeypatch.setenv("MCP_AUTH_MODE", "jwt")
    monkeypatch.setattr(server, "get_mcp_server", lambda: object())
    with pytest.raises(SystemExit, match="uvicorn app:app"):
        server.start_server("http", "127.0.0.1", 8000)


def test_cache_scope_private_with_auth(monkeypatch):
    from mcp_core.core.server import get_mcp_cache_policy

    monkeypatch.setenv("MCP_AUTH_MODE", "jwt")
    assert get_mcp_cache_policy()["cache_scope"] == "private"


def test_resource_host_added_to_fastmcp_allowlist(monkeypatch):
    from mcp_core.core import server

    for name in ("MCP_ALLOWED_HOSTS", "MCP_ALLOWED_ORIGINS", "VERCEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("MCP_AUTH_RESOURCE_URL", "https://mcp.contoso.com/mcp")
    server._configure_fastmcp_http_security()
    assert "mcp.contoso.com" in json.loads(os.environ["FASTMCP_HTTP_ALLOWED_HOSTS"])
    monkeypatch.delenv("MCP_AUTH_RESOURCE_URL")
    server._configure_fastmcp_http_security()


def test_log_redaction_filter():
    import logging

    from mcp_core.auth.integration import QueryRedactionFilter

    rec = logging.LogRecord(
        "uvicorn.access",
        20,
        "",
        0,
        '%s "%s"',
        ("1.2.3.4", "GET /x?code=abc&state=s1&y=2"),
        None,
    )
    QueryRedactionFilter().filter(rec)
    assert "abc" not in rec.getMessage() and "s1" not in rec.getMessage()
    assert "y=2" in rec.getMessage()


def test_yaml_enables_metrics_endpoint_and_local_dashboard(tmp_path):
    cfg = tmp_path / "uml-mcp.yaml"
    cfg.write_text(
        "metrics: {enabled: true, endpoint: true}\n"
        "admin: {allow_local_without_auth: true}\n"
        "audit: {enabled: true, sinks: [memory]}\n"
        "logging: {level: WARNING, format: json}\n",
        encoding="utf-8",
    )
    code = (
        "from fastapi.testclient import TestClient\n"
        "import app\n"
        "c = TestClient(app.app, client=('127.0.0.1', 5000))\n"
        "assert c.get('/metrics').status_code == 200\n"
        "assert 'uml_mcp_' in c.get('/metrics').text\n"
        "assert c.get('/admin').status_code == 200\n"
        "assert c.get('/admin/api/overview').json()['local'] is True\n"
        "import logging\n"
        "assert logging.getLogger().level == logging.WARNING\n"
        "r = TestClient(app.app, client=('203.0.113.9', 5000))\n"
        "assert r.get('/admin/api/overview').status_code == 404\n"
        "print('ok')\n"
    )
    proc = run_app({"UML_MCP_CONFIG": str(cfg)}, code)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip().splitlines()[-1] == "ok"


def test_default_app_has_no_metrics_or_local_admin():
    code = (
        "from fastapi.testclient import TestClient\n"
        "import app\n"
        "c = TestClient(app.app, client=('127.0.0.1', 5000))\n"
        "assert c.get('/metrics').status_code == 404\n"
        "assert c.get('/admin/api/overview').status_code == 404\n"
        "print('ok')\n"
    )
    proc = run_app({"UML_MCP_CONFIG": "none"}, code)
    assert proc.returncode == 0, proc.stderr
