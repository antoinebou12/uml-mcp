"""Plugins v1: entry-point discovery, allow-list, tools, renderers, lint, CLI, API."""

from __future__ import annotations

import base64
import importlib.metadata as md
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from mcp_core.core.config import MCP_SETTINGS
from mcp_core.core.settings_file import reset_config_cache
from mcp_core.plugins import loader
from mcp_core.plugins.api import RENDERERS_GROUP, TOOLS_GROUP, PluginContext
from mcp_core.tools.tool_decorator import _registered_tools, register_tools_with_server

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/plugins/uml-mcp-plugin-hello/src"


def ep(name: str, value: str, group: str) -> md.EntryPoint:
    return md.EntryPoint(name=name, value=value, group=group)


EPS = {
    TOOLS_GROUP: [
        ep("hello", "uml_mcp_plugin_hello:register", TOOLS_GROUP),
        ep("broken", "uml_mcp_plugin_hello:does_not_exist", TOOLS_GROUP),
    ],
    RENDERERS_GROUP: [
        ep("ascii", "uml_mcp_plugin_hello:AsciiRenderer", RENDERERS_GROUP)
    ],
}


@pytest.fixture
def plugins(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(EXAMPLE))
    monkeypatch.setattr(loader, "entry_points", lambda group: EPS.get(group, []))
    cfg = tmp_path / "uml-mcp.yaml"

    def configure(text: str) -> None:
        cfg.write_text(text, encoding="utf-8")
        reset_config_cache()

    monkeypatch.setenv("UML_MCP_CONFIG", str(cfg))
    configure("version: 1\n")
    tools_before = set(_registered_tools)
    yield configure
    for name in set(_registered_tools) - tools_before:
        del _registered_tools[name]
    for dtype in list(loader.RENDERERS):
        MCP_SETTINGS.diagram_types.pop(dtype, None)
    loader.RENDERERS.clear()
    loader.STATUS.clear()
    sys.modules.pop("uml_mcp_plugin_hello", None)
    reset_config_cache()


def test_discovered_but_not_loaded_without_allow_list(plugins):
    status = loader.load_plugins()
    assert {s.name: s.enabled for s in status} == {
        "hello": False,
        "broken": False,
        "ascii": False,
    }
    assert not any(s.loaded for s in status) and "hello_echo" not in _registered_tools
    assert "ascii" not in MCP_SETTINGS.diagram_types


def test_enabled_plugins_register_tools_and_renderers(plugins):
    plugins(
        "plugins:\n  enabled: [hello, ascii]\n  settings: {hello: {greeting: Hi}}\n"
    )
    status = {s.name: s for s in loader.load_plugins()}
    assert status["hello"].loaded and status["hello"].tools == ["hello_echo"]
    assert status["ascii"].diagram_types == ["ascii"]
    info = _registered_tools["hello_echo"]
    assert info["annotations"]["readOnlyHint"] is True
    assert info["function"](text="world") == {"message": "Hi, world!"}
    # the tool goes through the normal registration path (instrumented, gated)
    server = MagicMock()
    server.tool.return_value = lambda f: f
    assert "hello_echo" in register_tools_with_server(server)
    assert MCP_SETTINGS.diagram_types["ascii"].backend == "plugin:ascii"


def test_plugin_renderer_runs_before_kroki(plugins):
    from mcp_core.core.utils import generate_diagram

    plugins("plugins: {enabled: [ascii]}\n")
    loader.load_plugins()
    result = generate_diagram("ascii", "+--+\n|<>|\n+--+", "svg")
    assert result["source"] == "plugin:ascii" and result["mime_type"] == "image/svg+xml"
    svg = base64.b64decode(result["content_base64"]).decode()
    assert "&lt;&gt;" in svg and result["attempts"] == [
        {"backend": "plugin:ascii", "ok": True}
    ]
    failed = generate_diagram("ascii", "x", "png")
    assert "plugin renderer ascii failed" in failed["error"]


def test_errors_are_isolated_and_linted(plugins):
    from mcp_core.core.settings_file import get_app_config
    from mcp_core.quality.lint import lint_config

    plugins("plugins: {enabled: [broken, ghost]}\n")
    status = {s.name: s for s in loader.load_plugins()}
    assert not status["broken"].loaded and "AttributeError" in (
        status["broken"].error or ""
    )
    assert status["ghost"].error == "not installed"
    codes = {i.code for i in lint_config(get_app_config(), None, {})}
    assert {"PLG001", "PLG002"} <= codes


def test_context_rejects_collisions():
    ctx = PluginContext("dup")
    ctx.tool("x", "A tool used to test collisions between plugins.")(lambda: 1)
    try:
        with pytest.raises(ValueError, match="collision"):
            ctx.tool("x", "Same name again.")
    finally:
        _registered_tools.pop("dup_x", None)


def test_builtin_types_cannot_be_overridden(plugins, monkeypatch):
    from mcp_core.plugins.api import DiagramTypeSpec, RenderOutput

    class Hijack:
        name = "evil"

        def __init__(self) -> None:
            self.diagram_types = {"class": DiagramTypeSpec("hijack")}

        def render(
            self, diagram_type: str, code: str, output_format: str
        ) -> RenderOutput:
            raise AssertionError("never called")  # pragma: no cover

    import types

    module = types.SimpleNamespace(Hijack=Hijack)
    monkeypatch.setitem(sys.modules, "hijack_mod", module)
    extra = {**EPS, RENDERERS_GROUP: [ep("evil", "hijack_mod:Hijack", RENDERERS_GROUP)]}
    monkeypatch.setattr(loader, "entry_points", lambda group: extra.get(group, []))
    plugins("plugins: {enabled: [evil]}\n")
    status = {s.name: s for s in loader.load_plugins()}
    assert "already built in" in (status["evil"].error or "")
    assert MCP_SETTINGS.diagram_types["class"].backend == "plantuml"


def test_cli_list_enable_disable(plugins):
    from mcp_core.cli.app import app

    runner = CliRunner()
    out = runner.invoke(app, ["plugins", "list"]).output
    assert "hello" in out and "available" in out
    res = runner.invoke(app, ["plugins", "enable", "hello"])
    assert res.exit_code == 0, res.output
    assert "enabled" in runner.invoke(app, ["plugins", "list"]).output
    assert runner.invoke(app, ["plugins", "disable", "hello"]).exit_code == 0
    reset_config_cache()
    from mcp_core.core.settings_file import get_app_config

    assert get_app_config().plugins.enabled == []


def test_admin_api_lists_and_toggles(plugins, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from mcp_core.admin import guards
    from mcp_core.admin.api import build_local_admin_router

    monkeypatch.setenv(guards.TOKEN_ENV, "tok")
    guards.reset_setup_token()
    app = FastAPI()
    app.include_router(build_local_admin_router())
    c = TestClient(app, client=("127.0.0.1", 1), base_url="http://127.0.0.1")
    names = {p["name"] for p in c.get("/admin/api/plugins").json()["plugins"]}
    assert {"hello", "ascii", "broken"} <= names
    res = c.post(
        "/admin/api/plugins/ascii",
        json={"enabled": True},
        headers={"Authorization": "Bearer tok", "X-UML-MCP-Admin": "1"},
    )
    assert (
        res.status_code == 200 and "plugins.enabled" in res.json()["restart_required"]
    )
    guards.reset_setup_token()
