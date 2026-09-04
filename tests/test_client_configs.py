"""Validate committed MCP client config templates parse and keep expected shapes."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def test_vscode_workspace_mcp_uses_servers_key() -> None:
    data = _load_json(ROOT / ".vscode" / "mcp.json")
    assert isinstance(data, dict)
    assert "servers" in data
    assert "mcpServers" not in data
    entry = data["servers"]["uml-mcp"]
    assert entry["type"] == "http"
    assert str(entry["url"]).endswith("/mcp")


def test_cursor_workspace_mcp_uses_mcp_servers_key() -> None:
    data = _load_json(ROOT / ".cursor" / "mcp.json")
    assert "mcpServers" in data
    assert str(data["mcpServers"]["uml-mcp"]["url"]).endswith("/mcp")


def test_codex_project_toml_has_http_server() -> None:
    text = (ROOT / ".codex" / "config.toml").read_text(encoding="utf-8")
    assert "[mcp_servers.uml-mcp]" in text
    assert "https://uml-mcp.vercel.app/mcp" in text
    assert "tool_timeout_sec" in text


def test_config_json_templates_parse() -> None:
    json_files = sorted(CONFIG.glob("*.json"))
    assert json_files, "expected config/*.json templates"
    for path in json_files:
        data = _load_json(path)
        blob = json.dumps(data)
        if path.name.startswith("vscode_"):
            assert "servers" in data
            assert "mcpServers" not in data
        if path.name == "openwebui_mcp.json":
            assert isinstance(data, list)
            assert data[0]["url"].endswith("/mcp")
        if "http" in path.name or path.name in {
            "cursor_http.json",
            "claude_desktop_http.json",
            "vscode_mcp.json",
        }:
            assert "/mcp" in blob


def test_codex_and_continue_templates_exist() -> None:
    codex = (CONFIG / "codex_config.toml").read_text(encoding="utf-8")
    assert "[mcp_servers.uml-mcp]" in codex
    assert "uml-mcp.vercel.app/mcp" in codex

    continue_cfg = (CONFIG / "continue_config.yaml").read_text(encoding="utf-8")
    assert "uml-mcp.vercel.app/mcp" in continue_cfg
    assert "mcpServers" in continue_cfg

    stdio = (CONFIG / "codex_stdio.toml").read_text(encoding="utf-8")
    assert "command" in stdio
    assert "MCP_DIAGRAM_FALLBACK" in stdio
