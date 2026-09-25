"""``uml-mcp client install``: local stdio registration in MCP clients."""

from __future__ import annotations

import json

import pytest

from mcp_core.core import client_install, commands
from mcp_core.core.client_install import build_entry, config_path, install, merge_config


@pytest.fixture(autouse=True)
def fixed_command(monkeypatch, tmp_path):
    monkeypatch.setattr(
        client_install.sys, "executable", str(tmp_path / "nobin" / "python")
    )
    monkeypatch.setattr(client_install.shutil, "which", lambda _: "/usr/bin/uml-mcp")


def test_entry_shapes():
    assert build_entry("vscode") == {
        "type": "stdio",
        "command": "/usr/bin/uml-mcp",
        "args": ["--transport", "stdio"],
    }
    assert "type" not in build_entry("cursor")
    assert build_entry("cursor", {"MCP_URL_ONLY": "true"})["env"] == {
        "MCP_URL_ONLY": "true"
    }


def test_prefers_script_next_to_interpreter(monkeypatch, tmp_path):
    bindir = tmp_path / "venv" / "bin"
    bindir.mkdir(parents=True)
    (bindir / "uml-mcp").write_text("#!/bin/sh\n")
    monkeypatch.setattr(client_install.sys, "executable", str(bindir / "python"))
    assert build_entry("cursor")["command"] == str(bindir / "uml-mcp")


def test_falls_back_to_uvx(monkeypatch):
    monkeypatch.setattr(client_install.shutil, "which", lambda _: None)
    assert build_entry("cursor")["command"] == "uvx"


def test_merge_keeps_other_servers():
    merged = merge_config({"servers": {"other": {}}, "inputs": []}, "vscode", {"x": 1})
    assert merged == {"servers": {"other": {}, "uml-mcp": {"x": 1}}, "inputs": []}
    assert "mcpServers" in merge_config({}, "claude-desktop", {})


def test_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(client_install.platform, "system", lambda: "Linux")
    assert config_path("cursor", "user", tmp_path) == tmp_path / ".cursor/mcp.json"
    assert str(config_path("vscode", "workspace")) == ".vscode/mcp.json"
    assert str(config_path("vscode", "user", tmp_path)).endswith("Code/User/mcp.json")
    assert str(config_path("claude-desktop", "user", tmp_path)).endswith(
        "claude_desktop_config.json"
    )
    monkeypatch.setattr(client_install.platform, "system", lambda: "Darwin")
    assert "Library" in str(config_path("claude-desktop", "user", tmp_path))
    assert config_path("claude-code", "user", tmp_path) is None


def test_install_merges_backs_up_and_is_idempotent(tmp_path):
    target = tmp_path / ".cursor" / "mcp.json"
    target.parent.mkdir()
    target.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}))
    text, path = install("cursor", home=tmp_path)
    assert path == target
    data = json.loads(target.read_text())
    assert set(data["mcpServers"]) == {"other", "uml-mcp"}
    assert json.loads(text) == data
    backups = list(target.parent.glob("mcp.json.bak-*"))
    assert len(backups) == 1
    install("cursor", home=tmp_path)  # unchanged -> no new write/backup
    assert list(target.parent.glob("mcp.json.bak-*")) == backups


def test_dry_run_does_not_write(tmp_path):
    text, path = install("cursor", home=tmp_path, dry_run=True)
    assert path is not None and not path.exists()
    assert json.loads(text)["mcpServers"]["uml-mcp"]["args"] == ["--transport", "stdio"]


def test_invalid_existing_json_and_unknown_client(tmp_path):
    target = tmp_path / ".cursor" / "mcp.json"
    target.parent.mkdir()
    target.write_text("{not json")
    with pytest.raises(ValueError, match="not valid JSON"):
        install("cursor", home=tmp_path)
    with pytest.raises(ValueError, match="unknown client"):
        install("emacs")


def test_claude_code_prints_cli_command():
    text, path = install("claude-code")
    assert path is None
    assert (
        text
        == "claude mcp add --scope user uml-mcp -- /usr/bin/uml-mcp --transport stdio"
    )
    assert "--scope" not in install("claude-code", scope="workspace")[0]


def test_cli(capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert commands.main(["client", "install", "--client", "claude-code"]) == 0
    assert "claude mcp add" in capsys.readouterr().out
    assert (
        commands.main(
            [
                "client",
                "install",
                "--client",
                "cursor",
                "--scope",
                "workspace",
                "--dry-run",
            ]
        )
        == 0
    )
    assert "# would write" in capsys.readouterr().out
    assert (
        commands.main(
            ["client", "install", "--client", "cursor", "--scope", "workspace"]
        )
        == 0
    )
    assert (tmp_path / ".cursor" / "mcp.json").is_file()
    (tmp_path / ".cursor" / "mcp.json").write_text("{bad")
    assert (
        commands.main(
            ["client", "install", "--client", "cursor", "--scope", "workspace"]
        )
        == 1
    )
