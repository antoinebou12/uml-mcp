"""Protocol-level lint: what clients actually see (initialize + */list).

Implements the rule set of the MCP Playground grading methodology used by
``mcpx lint`` (tool/prop/resource/prompt/server rules, score, grade A–F and
token estimate), so ``uml-mcp lint`` gives the same verdict offline, in
process or against any URL, without calling a third-party API.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from .lint import LintIssue

POINTS = {"error": 15, "warning": 5, "info": 1}
GRADES = (("A", 90), ("B", 80), ("C", 70), ("D", 60), ("F", 0))
NAME_RE = re.compile(r"^[a-z0-9]+([_-][a-z0-9]+)*$")
TYPE_KEYS = ("type", "anyOf", "oneOf", "allOf", "$ref", "enum", "const")
MIN_DESCRIPTION, MAX_DESCRIPTION = 10, 500


@dataclass
class Surface:
    """The server as a client sees it (JSON-shaped, camelCase keys)."""

    server_name: str | None = None
    server_version: str | None = None
    tools: list[dict[str, Any]] = field(default_factory=list)
    resources: list[dict[str, Any]] = field(default_factory=list)
    resource_templates: list[dict[str, Any]] = field(default_factory=list)
    prompts: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Report:
    issues: list[LintIssue]
    score: int
    grade: str
    token_estimate: int
    counts: dict[str, int]
    server: dict[str, str | None] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "grade": self.grade,
            "score": self.score,
            "token_estimate": self.token_estimate,
            "counts": self.counts,
            "server": self.server,
            "issues": [i.as_dict() for i in self.issues],
        }


def _issue(
    severity: str, code: str, target: str, message: str, fix: str = ""
) -> LintIssue:
    return LintIssue(severity, code, target, message, fix)


def _description_issues(
    kind: str, target: str, name: str, desc: str
) -> list[LintIssue]:
    desc = (desc or "").strip()
    if not desc:
        sev = "error" if kind in ("tool", "prompt") else "warning"
        return [
            _issue(
                sev,
                f"{kind}-no-description",
                target,
                f"missing {kind} description",
                "say what it does and when to use it",
            )
        ]
    out = []
    if kind == "tool":
        if len(desc) < MIN_DESCRIPTION:
            out.append(
                _issue(
                    "warning",
                    "tool-short-description",
                    target,
                    f"description is {len(desc)} chars (< {MIN_DESCRIPTION})",
                )
            )
        if len(desc) > MAX_DESCRIPTION:
            out.append(
                _issue(
                    "warning",
                    "tool-long-description",
                    target,
                    f"description is {len(desc)} chars (> {MAX_DESCRIPTION}); "
                    "every call pays these tokens",
                    "aim for under 300 chars",
                )
            )
        if desc.lower().replace(" ", "_").strip(".") == name.lower():
            out.append(
                _issue(
                    "warning",
                    "tool-description-is-name",
                    target,
                    "description just repeats the tool name",
                )
            )
    return out


def lint_tool(tool: dict[str, Any]) -> list[LintIssue]:
    name = str(tool.get("name") or "")
    target = f"tool:{name}"
    issues = _description_issues("tool", target, name, tool.get("description") or "")
    if not NAME_RE.match(name):
        issues.append(
            _issue(
                "info",
                "tool-name-convention",
                target,
                "name is not snake_case or kebab-case",
            )
        )
    schema = tool.get("inputSchema")
    if not isinstance(schema, dict):
        issues.append(
            _issue("warning", "tool-no-schema", target, "missing inputSchema")
        )
        return issues
    if schema.get("type") != "object":
        issues.append(
            _issue(
                "info",
                "tool-schema-not-object",
                target,
                "inputSchema type is not 'object'",
            )
        )
    props = schema.get("properties") or {}
    if not props:
        issues.append(
            _issue("info", "tool-empty-schema", target, "tool accepts no arguments")
        )
    required = schema.get("required") or []
    if props and not required:
        issues.append(
            _issue(
                "info",
                "tool-no-required",
                target,
                "no required parameters",
                "mark the essential ones as required",
            )
        )
    for req in required:
        if req not in props:
            issues.append(
                _issue(
                    "error",
                    "required-not-in-properties",
                    target,
                    f"required field '{req}' is not in properties",
                )
            )
    for pname, prop in props.items():
        prop = prop if isinstance(prop, dict) else {}
        if not str(prop.get("description") or "").strip():
            issues.append(
                _issue(
                    "warning",
                    "prop-no-description",
                    f"{target}.{pname}",
                    f"parameter '{pname}' has no description",
                )
            )
        if not any(k in prop for k in TYPE_KEYS):
            issues.append(
                _issue(
                    "warning",
                    "prop-no-type",
                    f"{target}.{pname}",
                    f"parameter '{pname}' has no type",
                )
            )
    return issues


def lint_resource(res: dict[str, Any]) -> list[LintIssue]:
    ident = res.get("uri") or res.get("uriTemplate") or res.get("name") or "?"
    target = f"resource:{ident}"
    issues = []
    if not str(res.get("name") or "").strip():
        issues.append(
            _issue("warning", "resource-no-name", target, "missing resource name")
        )
    issues += _description_issues(
        "resource", target, str(res.get("name") or ""), res.get("description") or ""
    )
    if not res.get("mimeType"):
        issues.append(_issue("info", "resource-no-mimetype", target, "no MIME type"))
    return issues


def lint_prompt(prompt: dict[str, Any]) -> list[LintIssue]:
    name = str(prompt.get("name") or "")
    target = f"prompt:{name}"
    issues = _description_issues(
        "prompt", target, name, prompt.get("description") or ""
    )
    for arg in prompt.get("arguments") or []:
        if not str(arg.get("description") or "").strip():
            issues.append(
                _issue(
                    "warning",
                    "prompt-arg-no-description",
                    f"{target}.{arg.get('name')}",
                    f"argument '{arg.get('name')}' has no description",
                )
            )
    return issues


def lint_server(s: Surface) -> list[LintIssue]:
    issues = []
    if not (s.tools or s.resources or s.resource_templates or s.prompts):
        issues.append(
            _issue(
                "error",
                "server-empty",
                "server",
                "server exposes no tools, resources or prompts",
            )
        )
    if not s.server_name:
        issues.append(_issue("warning", "server-no-name", "server", "no server name"))
    if not s.server_version:
        issues.append(
            _issue("warning", "server-no-version", "server", "no server version")
        )
    names = [str(t.get("name") or "") for t in s.tools]
    for dup in sorted({n for n in names if names.count(n) > 1}):
        issues.append(
            _issue(
                "error", "server-duplicate-tools", f"tool:{dup}", "duplicate tool name"
            )
        )
    return issues


def token_estimate(s: Surface) -> int:
    """~4 characters per token over everything a client loads at connect time."""
    payload = {
        "tools": s.tools,
        "resources": s.resources,
        "resourceTemplates": s.resource_templates,
        "prompts": s.prompts,
    }
    return len(json.dumps(payload, separators=(",", ":"))) // 4


def grade_for(score: int) -> str:
    return next(g for g, floor in GRADES if score >= floor)


def lint_surface(s: Surface) -> Report:
    issues = lint_server(s)
    for tool in s.tools:
        issues += lint_tool(tool)
    for res in [*s.resources, *s.resource_templates]:
        issues += lint_resource(res)
    for prompt in s.prompts:
        issues += lint_prompt(prompt)
    score = (
        0
        if any(i.code == "server-empty" for i in issues)
        else max(0, 100 - sum(POINTS[i.severity] for i in issues))
    )
    counts = {
        "tools": len(s.tools),
        "resources": len(s.resources) + len(s.resource_templates),
        "prompts": len(s.prompts),
    }
    server = {"name": s.server_name, "version": s.server_version}
    return Report(issues, score, grade_for(score), token_estimate(s), counts, server)


def _dump(items: list[Any]) -> list[dict[str, Any]]:
    return [i.model_dump(by_alias=True, exclude_none=True, mode="json") for i in items]


async def fetch_surface(url: str | None = None, token: str | None = None) -> Surface:
    """Connect like a client: in process (default) or to a Streamable HTTP URL."""
    from fastmcp import Client

    if url:
        client = Client(url, auth=token) if token else Client(url)
    else:
        from ..core.server import get_mcp_server

        client = Client(get_mcp_server())
    async with client:
        info = client.server_info
        return Surface(
            server_name=getattr(info, "name", None),
            server_version=getattr(info, "version", None),
            tools=_dump(await client.list_tools()),
            resources=_dump(await client.list_resources()),
            resource_templates=_dump(await client.list_resource_templates()),
            prompts=_dump(await client.list_prompts()),
        )


__all__ = [
    "GRADES",
    "POINTS",
    "Report",
    "Surface",
    "fetch_surface",
    "grade_for",
    "lint_prompt",
    "lint_resource",
    "lint_server",
    "lint_surface",
    "lint_tool",
    "token_estimate",
]
