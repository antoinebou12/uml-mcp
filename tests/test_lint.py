"""``uml-mcp lint``: MXCP-inspired definition and configuration checks."""

from __future__ import annotations

import json
from types import SimpleNamespace

from mcp_core.core import commands
from mcp_core.core.settings_file import parse_app_config
from mcp_core.quality.lint import (
    LintIssue,
    exit_code,
    lint_config,
    lint_named,
    lint_tools,
    run_lint,
)


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
    assert {
        "TOOL001",
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


def test_prompt_and_resource_descriptions():
    issues = lint_named(
        "prompt", {"p": {"description": "x"}, "q": {"description": "A" * 20}}
    )
    assert [(i.code, i.target) for i in issues] == [("PROM001", "prompt:p")]


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


def test_lint_cli(capsys):
    assert commands.main(["lint", "--strict"]) == 0
    assert "0 error(s), 0 warning(s)" in capsys.readouterr().out
    assert commands.main(["lint", "--format", "json"]) == 0
    assert isinstance(json.loads(capsys.readouterr().out), list)
