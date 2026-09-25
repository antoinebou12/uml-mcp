"""``uml-mcp lint``: MXCP-inspired definition and configuration checks."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from types import SimpleNamespace

from mcp_core.core import commands
from mcp_core.core.settings_file import parse_app_config
from mcp_core.quality import wire
from mcp_core.quality.lint import (
    LintIssue,
    exit_code,
    lint_config,
    lint_tools,
    run_lint,
)
from mcp_core.quality.wire import Surface


def codes(issues: list[LintIssue]) -> set[str]:
    return {i.code for i in issues}


def bare(x, y):  # no annotations, no docstring
    return x, y


def documented(code: str) -> str:
    """Render.

    Args:
        code: the diagram source
    """
    return code


def test_tool_rules_fire_on_a_poor_definition():
    issues = lint_tools({"bad": {"description": "", "function": bare}})
    assert "TOOL002" not in codes(issues)  # empty is the wire rule's job
    assert {
        "TOOL003",
        "TOOL004",
        "TOOL005",
        "TOOL006",
        "TOOL007",
        "TOOL008",
    } <= codes(issues)
    short = lint_tools({"s": {"description": "Too short"}})
    assert "TOOL002" in codes(short)


def test_well_described_tool_is_clean():
    good = {
        "description": "Render a diagram from source code and return its URL and data.",
        "annotations": {
            "title": "Render",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
        "output_schema": {"type": "object"},
        "function": documented,
        "example": "documented(code='A->B')",
    }
    assert lint_tools({"render": good}) == []


def test_config_rules():
    tools = {
        "generate_uml": {"annotations": {}},
        "validate_uml": {"annotations": {"readOnlyHint": True}},
    }
    auth = SimpleNamespace(
        enabled=True, resource_url="http://localhost/mcp", tool_permissions={}
    )
    app = parse_app_config(
        {
            "audit": {"enabled": False},
            "tools": {"disabled": ["nope", "generate_uml"]},
            "rate_limit": {"tools": {"ghost": {"requests_per_minute": 1}}},
            "admin": {"allow_local_without_auth": True},
        }
    )
    got = codes(lint_config(app, auth, tools))
    assert {
        "CFG001",
        "CFG002",
        "CFG003",
        "CFG006",
        "CFG007",
        "CFG008",
        "CFG009",
        "AUTH001",
    } <= got
    risky = parse_app_config(
        {"audit": {"enabled": True, "sinks": ["file"], "include_inputs": "full"}}
    )
    assert {"CFG004", "CFG005"} <= codes(lint_config(risky, None, tools))


def test_exit_codes():
    warn = LintIssue("warning", "X", "t", "m")
    err = LintIssue("error", "Y", "t", "m")
    assert exit_code([]) == 0 and exit_code([warn]) == 0
    assert exit_code([warn], strict=True) == 1 and exit_code([err]) == 1


def test_real_registry_is_strict_clean():
    """Guards future tools/prompts/resources: fix the lint instead of relaxing this."""
    issues = run_lint()
    blocking = [i for i in issues if i.severity in ("error", "warning")]
    assert blocking == [], blocking


GOOD_SURFACE = Surface(
    "uml_mcp",
    "1.4.0",
    tools=[
        {
            "name": "render",
            "description": "Render a diagram and return its URL.",
            "inputSchema": {
                "type": "object",
                "properties": {"code": {"type": "string", "description": "source"}},
                "required": ["code"],
            },
        }
    ],
)


def test_lint_cli(capsys, monkeypatch):
    async def fake_fetch(url=None, token=None):
        if url:
            raise ConnectionError("down")
        return GOOD_SURFACE

    monkeypatch.setattr(wire, "fetch_surface", fake_fetch)
    assert commands.main(["lint", "--strict", "--min-grade", "A"]) == 0
    out = capsys.readouterr().out
    assert "0 error(s), 0 warning(s)" in out and "Grade A" in out
    assert commands.main(["lint", "--token-budget", "10"]) == 1
    assert "over budget" in capsys.readouterr().out
    assert commands.main(["lint", "--quiet"]) == 0
    assert capsys.readouterr().out == ""
    assert commands.main(["lint", "http://127.0.0.1:9/mcp"]) == 2
    assert commands.main(["lint", "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert (
        data["grade"] == "A" and data["failures"] == [] and data["token_estimate"] > 0
    )
    monkeypatch.setattr(wire, "fetch_surface", lambda url=None, token=None: _empty())
    assert commands.main(["lint", "--min-grade", "B"]) == 1
    assert "grade F below B" in capsys.readouterr().out


async def _empty():
    return Surface()


def test_real_server_lint_gate():
    """The CI gate, end to end against the real FastMCP server."""
    env: dict[str, str] = {
        **os.environ,
        "USE_REAL_FASTMCP": "1",
        "UML_MCP_CONFIG": "none",
    }
    env.pop("MOCK_FASTMCP", None)
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "mcp_core.core.commands",
            "lint",
            "--strict",
            "--min-grade",
            "A",
            "--token-budget",
            "5500",
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Grade A" in proc.stdout
    proc = subprocess.run(
        [sys.executable, "-m", "mcp_core.core.commands", "lint", "--format", "json"],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        check=False,
    )
    server = json.loads(proc.stdout)["server"]
    assert server["name"] == "uml_mcp" and server["version"].startswith(
        "1."
    )  # not FastMCP's
