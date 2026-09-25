"""Local-only user install: register the stdio server in MCP clients.

``uml-mcp client install --client vscode|cursor|claude-desktop|claude-code``
merges a stdio entry into the client's configuration (backup first,
idempotent, ``--dry-run`` prints the result without writing).
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import sys
import time
from pathlib import Path
from typing import Any

CLIENTS = ("vscode", "cursor", "claude-desktop", "claude-code")
SERVER_NAME = "uml-mcp"


def stdio_command() -> tuple[str, list[str]]:
    """Prefer the script installed next to this interpreter, then PATH, then uvx."""
    bindir = Path(sys.executable).parent
    for name in ("uml-mcp", "uml-mcp.exe"):
        candidate = bindir / name
        if candidate.is_file():
            return str(candidate), ["--transport", "stdio"]
    exe = shutil.which("uml-mcp")
    if exe:
        return exe, ["--transport", "stdio"]
    return "uvx", ["uml-mcp", "--transport", "stdio"]


def config_path(client: str, scope: str, home: Path | None = None) -> Path | None:
    home = home or Path.home()
    system = platform.system()
    if client == "vscode":
        if scope == "workspace":
            return Path(".vscode") / "mcp.json"
        base = {
            "Darwin": home / "Library/Application Support/Code/User",
            "Windows": Path(os.environ.get("APPDATA", home / "AppData/Roaming"))
            / "Code/User",
        }.get(system, home / ".config/Code/User")
        return base / "mcp.json"
    if client == "cursor":
        return (
            Path(".cursor/mcp.json")
            if scope == "workspace"
            else home / ".cursor/mcp.json"
        )
    if client == "claude-desktop":
        base = {
            "Darwin": home / "Library/Application Support/Claude",
            "Windows": Path(os.environ.get("APPDATA", home / "AppData/Roaming"))
            / "Claude",
        }.get(system, home / ".config/Claude")
        return base / "claude_desktop_config.json"
    return None  # claude-code uses its CLI


def build_entry(client: str, env: dict[str, str] | None = None) -> dict[str, Any]:
    command, args = stdio_command()
    entry: dict[str, Any] = {"command": command, "args": args}
    if env:
        entry["env"] = env
    if client == "vscode":
        entry = {"type": "stdio", **entry}
    return entry


def merge_config(
    existing: dict[str, Any], client: str, entry: dict[str, Any]
) -> dict[str, Any]:
    root = "servers" if client == "vscode" else "mcpServers"
    merged = dict(existing)
    servers = dict(merged.get(root) or {})
    servers[SERVER_NAME] = entry
    merged[root] = servers
    return merged


def install(
    client: str,
    *,
    scope: str = "user",
    dry_run: bool = False,
    env: dict[str, str] | None = None,
    home: Path | None = None,
) -> tuple[str, Path | None]:
    """Return ``(text, path)``: the merged JSON (or CLI command) and target file."""
    if client not in CLIENTS:
        raise ValueError(
            f"unknown client {client!r}; choose one of {', '.join(CLIENTS)}"
        )
    entry = build_entry(client, env)
    if client == "claude-code":
        cmd = " ".join([entry["command"], *entry["args"]])
        flag = " --scope user" if scope == "user" else ""
        return f"claude mcp add{flag} {SERVER_NAME} -- {cmd}", None
    path = config_path(client, scope, home)
    assert path is not None
    existing: dict[str, Any] = {}
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path} is not valid JSON; fix it first ({exc})") from exc
    merged = merge_config(existing, client, entry)
    text = json.dumps(merged, indent=2) + "\n"
    if dry_run or merged == existing:
        return text, path
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        backup = path.with_suffix(path.suffix + f".bak-{int(time.time())}")
        shutil.copy2(path, backup)
    path.write_text(text, encoding="utf-8")
    return text, path


__all__ = ["CLIENTS", "build_entry", "config_path", "install", "merge_config"]
