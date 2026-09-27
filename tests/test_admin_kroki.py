"""Kroki in the admin console and CLI: health, playground render, Docker stack."""

from __future__ import annotations

import base64
import json
import os
import subprocess

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from mcp_core.admin import guards
from mcp_core.admin.api import build_local_admin_router
from mcp_core.core.config import MCP_SETTINGS
from mcp_core.core.settings_file import AppConfig, reset_config_cache
from mcp_core.kroki import health, stack
from mcp_core.observability.audit import configure_audit
from mcp_core.quality.render_check import check_svg
from tests.fixtures_auth import build_auth_app, entra_v2_claims, mint
from tests.fixtures_real import FakeKroki

TOKEN = "kroki-setup-token-0123456789"
WRITE = {"Authorization": f"Bearer {TOKEN}", "X-UML-MCP-Admin": "1"}
HEADER = {"X-UML-MCP-Admin": "1"}


@pytest.fixture(scope="module")
def fake():
    with FakeKroki() as running:
        yield running


@pytest.fixture
def cfg(tmp_path, monkeypatch, fake):
    saved_env = dict(os.environ)
    saved_kroki = MCP_SETTINGS.kroki_server
    path = tmp_path / "uml-mcp.yaml"
    path.write_text("version: 1\naudit: {enabled: false}\n", encoding="utf-8")
    monkeypatch.setenv("UML_MCP_CONFIG", str(path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv(guards.TOKEN_ENV, TOKEN)
    monkeypatch.delenv("KROKI_SERVER", raising=False)
    monkeypatch.setenv("MCP_DIAGRAM_FALLBACK", "false")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    guards.reset_setup_token()
    reset_config_cache()
    from mcp_core.core.utils import use_kroki_server

    use_kroki_server(fake.url)
    monkeypatch.setattr(
        stack,
        "status",
        lambda: {
            "docker": True,
            "detail": "Docker test",
            "compose_file": "/x/compose.yml",
            "url": "http://127.0.0.1:8001",
            "containers": [],
            "command": "uml-mcp kroki up --use",
        },
    )
    yield path
    os.environ.clear()
    os.environ.update(saved_env)
    use_kroki_server(saved_kroki)
    reset_config_cache()
    guards.reset_setup_token()
    configure_audit(AppConfig())


@pytest.fixture
def local(cfg):
    app = FastAPI()
    app.include_router(build_local_admin_router())
    return TestClient(app, client=("127.0.0.1", 5000), base_url="http://127.0.0.1:8765")


# ------------------------------------------------------------------- health
def test_probe_reports_version_and_every_companion(fake):
    report = health.probe(fake.url, trust_env=False)
    assert report["reachable"] and report["version"] == "fake"
    assert set(report["companions"]) == {"mermaid", "blockdiag", "bpmn", "excalidraw"}
    assert all(c["ok"] for c in report["companions"].values())
    assert health.ready(report)


def test_probe_unreachable_and_wait_gives_up():
    report = health.wait_until_ready(
        "http://127.0.0.1:9", timeout=0, trust_env=False, interval=0
    )
    assert not report["reachable"] and "ConnectError" in report["error"]
    assert report["companions"]["mermaid"] == {"ok": False, "detail": "unreachable"}
    assert not health.ready(report)


def test_probe_reports_companion_errors(fake, monkeypatch):
    monkeypatch.setattr(health, "_example", lambda dtype: "SYNTAX_ERROR")
    report = health.probe(fake.url, ("mermaid",), trust_env=False)
    assert report["reachable"] and not report["companions"]["mermaid"]["ok"]
    assert "HTTP 400" in report["companions"]["mermaid"]["detail"]


# ------------------------------------------------------------------- admin API
def test_status_catalog_and_render(local, fake):
    status = local.get("/admin/api/kroki").json()
    assert status["kroki"]["url"] == fake.url and status["kroki"]["reachable"]
    assert status["mode"] == "local" and status["docker"]["detail"] == "Docker test"

    types = local.get("/admin/api/kroki/catalog").json()["types"]
    assert len(types) == len(MCP_SETTINGS.diagram_types)
    mermaid = next(t for t in types if t["name"] == "mermaid")
    assert mermaid["example"] and "svg" in mermaid["formats"]

    body = {"diagram_type": "mermaid", "code": "graph TD; Start-->Finish"}
    out = local.post("/admin/api/kroki/render", json=body, headers=HEADER).json()
    assert out["url"].startswith(fake.url) and out["playground"]
    check_svg(base64.b64decode(out["content_base64"]), ("Start", "Finish"))
    assert out["mime_type"] == "image/svg+xml"


def test_render_errors_and_guards(local, cfg):
    bad = {"diagram_type": "graphviz", "code": "digraph { a -> SYNTAX_ERROR -> }"}
    out = local.post("/admin/api/kroki/render", json=bad, headers=HEADER).json()
    assert "syntax error" in out["error"].lower()
    unknown = {"diagram_type": "nope", "code": "x"}
    assert (
        "error"
        in local.post("/admin/api/kroki/render", json=unknown, headers=HEADER).json()
    )
    # a custom header is required (CSRF), a body must be a JSON object
    assert local.post("/admin/api/kroki/render", json=bad).status_code == 403
    assert (
        local.post(
            "/admin/api/kroki/render", content=b"[1]", headers=HEADER
        ).status_code
        == 400
    )
    app = FastAPI()
    app.include_router(build_local_admin_router())
    remote = TestClient(app, client=("10.0.0.9", 1), base_url="http://127.0.0.1")
    assert remote.get("/admin/api/kroki").status_code == 404


def test_use_saves_and_switches_live(local, cfg, fake):
    assert local.post("/admin/api/kroki/use", json={"url": fake.url}).status_code == 403
    no_token = local.post(
        "/admin/api/kroki/use", json={"url": fake.url}, headers=HEADER
    )
    assert no_token.status_code == 401
    bad = local.post("/admin/api/kroki/use", json={"url": "ftp://x"}, headers=WRITE)
    assert bad.status_code == 422
    other = f"{fake.url}/"
    res = local.post("/admin/api/kroki/use", json={"url": other}, headers=WRITE)
    assert res.status_code == 200, res.text
    assert res.json()["kroki_server"] == fake.url
    saved = yaml.safe_load(cfg.read_text())
    assert saved["rendering"]["kroki_server"] == fake.url
    assert MCP_SETTINGS.kroki_server == fake.url
    assert os.environ["KROKI_SERVER"] == fake.url  # re-applied from the file
    # an operator env var always wins: the console refuses to fight it
    reset_config_cache()
    os.environ["KROKI_SERVER"] = "http://operator:8000"
    cfg.write_text("version: 1\n", encoding="utf-8")
    reset_config_cache()
    locked = local.post("/admin/api/kroki/use", json={"url": fake.url}, headers=WRITE)
    assert locked.status_code == 409 and "environment" in locked.text


def test_docker_up_down(local, cfg, fake, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        stack,
        "up",
        lambda port: (
            calls.append(f"up:{port}")
            or {"url": fake.url, "compose_file": "f", "containers": []}
        ),
    )
    monkeypatch.setattr(
        stack, "down", lambda: calls.append("down") or {"stopped": True}
    )
    assert local.post("/admin/api/kroki/docker/up", json={}).status_code == 403
    res = local.post(
        "/admin/api/kroki/docker/up", json={"port": 8123, "use": True}, headers=WRITE
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["health"]["reachable"] and body["use"]["kroki_server"] == fake.url
    assert local.post("/admin/api/kroki/docker/down", headers=WRITE).json() == {
        "stopped": True
    }
    assert calls == ["up:8123", "down"]

    def unavailable(port):
        raise stack.DockerUnavailable("docker is not installed")

    monkeypatch.setattr(stack, "up", unavailable)
    res = local.post("/admin/api/kroki/docker/up", json={}, headers=WRITE)
    assert res.status_code == 503 and "not installed" in res.json()["detail"]


def test_enterprise_reports_health_but_never_runs_docker(
    settings_factory, mock_idp, rsa_key, cfg, fake
):
    app = build_auth_app(settings_factory(MCP_ADMIN_UI="true"), http=mock_idp.client())
    client = TestClient(app)
    admin = {
        "Authorization": f"Bearer {mint(entra_v2_claims(roles=['MCP.Admin']), rsa_key)}"
    }
    status = client.get("/admin/api/kroki", headers=admin).json()
    assert status["mode"] == "enterprise" and status["docker"] is None
    assert status["kroki"]["reachable"]
    cfg.write_text("version: 1\nadmin: {allow_write: true}\n", encoding="utf-8")
    reset_config_cache()
    res = client.post("/admin/api/kroki/docker/up", json={}, headers=admin)
    assert res.status_code == 404
    user = {"Authorization": f"Bearer {mint(entra_v2_claims(), rsa_key)}"}
    assert client.get("/admin/api/kroki", headers=user).status_code == 403


# ------------------------------------------------------------------- stack
def test_compose_file_binds_loopback_with_every_companion(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    text = stack.compose_yaml(8123)
    compose = yaml.safe_load(text)
    assert set(compose["services"]) == set(stack.IMAGES)
    assert compose["services"]["kroki"]["ports"] == ["127.0.0.1:8123:8000"]
    env = compose["services"]["kroki"]["environment"]
    assert env["KROKI_MERMAID_HOST"] == "mermaid" and env["KROKI_BPMN_HOST"] == "bpmn"
    with pytest.raises(ValueError):
        stack.compose_yaml(0)
    assert stack.configured_port() is None
    path = stack.write_compose(8123)
    assert path == tmp_path / "uml-mcp" / "kroki" / "compose.yml"
    assert stack.configured_port() == 8123


class FakeRun:
    def __init__(self, outputs: dict[str, subprocess.CompletedProcess]):
        self.outputs = outputs
        self.calls: list[list[str]] = []

    def __call__(self, args, **kwargs):
        assert "shell" not in kwargs and isinstance(args, list)
        self.calls.append(args)
        for key, value in self.outputs.items():
            if key in " ".join(args):
                return value
        return subprocess.CompletedProcess(args, 0, "", "")


def _done(stdout: str = "", code: int = 0, stderr: str = ""):
    return subprocess.CompletedProcess([], code, stdout, stderr)


def test_stack_commands(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(stack.shutil, "which", lambda name: "/usr/bin/docker")
    rows = [{"Service": "kroki", "State": "running", "Status": "Up", "Image": "k"}]
    fake_run = FakeRun(
        {
            "ps --all": _done("\n".join(json.dumps(r) for r in rows)),
            "info": _done("29.0"),
            "logs": _done("kroki | started"),
        }
    )
    monkeypatch.setattr(stack.subprocess, "run", fake_run)
    assert stack.ps() == []  # no compose file yet
    result = stack.up(8123)
    assert result["url"] == "http://127.0.0.1:8123"
    assert result["containers"][0]["service"] == "kroki"
    up = fake_run.calls[0]
    assert up[:6] == [
        "/usr/bin/docker",
        "compose",
        "-p",
        "uml-mcp-kroki",
        "-f",
        str(stack.compose_path()),
    ]
    assert up[6:] == ["up", "-d", "--remove-orphans"]
    assert stack.logs(5) == "kroki | started"
    assert stack.docker_available() == (True, "Docker 29.0")
    info = stack.status()
    assert info["url"] == "http://127.0.0.1:8123" and info["containers"]
    assert stack.down() == {"stopped": True}
    # older compose prints a JSON array
    fake_run.outputs["ps --all"] = _done(json.dumps(rows))
    assert stack.ps()[0]["state"] == "running"


def test_stack_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(stack.shutil, "which", lambda name: None)
    with pytest.raises(stack.DockerUnavailable):
        stack.docker_bin()
    assert stack.status()["docker"] is False
    assert stack.down() == {"stopped": False, "detail": "no stack was created"}
    assert stack.logs() == ""
    monkeypatch.setattr(stack.shutil, "which", lambda name: "/usr/bin/docker")
    fake_run = FakeRun(
        {"up -d": _done(code=1, stderr="Cannot connect to the Docker daemon at unix")}
    )
    monkeypatch.setattr(stack.subprocess, "run", fake_run)
    with pytest.raises(stack.DockerUnavailable, match="not running"):
        stack.up(8123)
    fake_run.outputs = {"up -d": _done(code=1, stderr="port is already allocated")}
    with pytest.raises(stack.StackError, match="already allocated"):
        stack.up(8123)

    def timeout(args, **kwargs):
        raise subprocess.TimeoutExpired(args, 1)

    monkeypatch.setattr(stack.subprocess, "run", timeout)
    with pytest.raises(stack.StackError, match="timed out"):
        stack.up(8123)
    fake_run = FakeRun({"info": _done(code=1)})
    monkeypatch.setattr(stack.subprocess, "run", fake_run)
    assert stack.docker_available() == (False, "the Docker daemon is not running")


# ------------------------------------------------------------------- CLI
def test_cli_kroki_commands(cfg, fake, monkeypatch):
    from mcp_core.cli.app import app

    runner = CliRunner()
    monkeypatch.setattr(
        stack,
        "up",
        lambda port: {"url": fake.url, "compose_file": "f", "containers": []},
    )
    monkeypatch.setattr(stack, "down", lambda: {"stopped": True})
    monkeypatch.setattr(stack, "logs", lambda tail: "log line")
    res = runner.invoke(
        app, ["kroki", "up", "--port", "8123", "--use", "--timeout", "5"]
    )
    assert res.exit_code == 0, res.output
    assert "ok  mermaid" in res.output and "rendering.kroki_server" in res.output
    assert yaml.safe_load(cfg.read_text())["rendering"]["kroki_server"] == fake.url
    res = runner.invoke(app, ["kroki", "status"])
    assert res.exit_code == 0 and "Docker: Docker test" in res.output
    bad = runner.invoke(app, ["kroki", "status", "--url", "http://127.0.0.1:9"])
    assert bad.exit_code == 1 and "unreachable" in bad.output
    assert runner.invoke(app, ["kroki", "down"]).output.strip() == "Stopped."
    assert "log line" in runner.invoke(app, ["kroki", "logs"]).output

    def fail(port):
        raise stack.StackError("port is already allocated")

    monkeypatch.setattr(stack, "up", fail)
    res = runner.invoke(app, ["kroki", "up"])
    assert res.exit_code == 1 and "already allocated" in res.output


def test_cli_main_propagates_exit_codes(monkeypatch):
    from mcp_core.cli.app import main

    monkeypatch.setattr(stack, "status", lambda: {"detail": "n/a", "containers": []})
    assert main(["kroki", "status", "--url", "http://127.0.0.1:9"]) == 1


# ------------------------------------------------------------------- real Docker
@pytest.mark.docker
def test_real_docker_stack_renders_every_type(tmp_path, monkeypatch):
    """`uml-mcp kroki up` for real: five containers, then all 37 types render."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(
        stack, "PROJECT", "uml-mcp-kroki-test"
    )  # leave a dev stack alone
    port = int(os.environ.get("UML_MCP_TEST_DOCKER_PORT", "8011"))
    result = stack.up(port)
    try:
        report = health.wait_until_ready(result["url"], 300, trust_env=False)
        assert health.ready(report), report
        assert {c["service"] for c in stack.ps()} == set(stack.IMAGES)
        from mcp_core.admin.kroki_routes import catalog, render
        from mcp_core.core.utils import use_kroki_server

        saved = MCP_SETTINGS.kroki_server
        use_kroki_server(result["url"])
        try:
            failures = {}
            for item in catalog():
                out = render(item["name"], item["example"], "svg")
                if out.get("error"):
                    failures[item["name"]] = out["error"][:120]
                else:
                    check_svg(base64.b64decode(out["content_base64"]))
            assert failures == {}
        finally:
            use_kroki_server(saved)
    finally:
        stack.down()
    assert stack.ps() == []
