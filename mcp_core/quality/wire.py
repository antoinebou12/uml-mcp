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
from urllib.parse import urlsplit

from .lint import LintIssue

POINTS = {"error": 15, "warning": 5, "info": 1}
GRADES = (("A", 90), ("B", 80), ("C", 70), ("D", 60), ("F", 0))
NAME_RE = re.compile(r"^[a-z0-9]+([_-][a-z0-9]+)*$")
TYPE_KEYS = ("type", "anyOf", "oneOf", "allOf", "$ref", "enum", "const")
HINTS = ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint")
#: A single tool definition above this many tokens is expensive for every client.
MAX_TOOL_TOKENS = 1500
#: Rules beyond the mcpx set (MCP spec SEP-986, MCP annotations/structured output,
#: FastMCP server instructions). They score the same way.
EXTENDED_RULES = (
    "tool-name-invalid",
    "tool-no-title",
    "tool-missing-hints",
    "tool-no-output-schema",
    "output-schema-not-object",
    "tool-schema-open",
    "tool-too-large",
    "server-no-instructions",
    "server-duplicate-prompts",
    "server-duplicate-resources",
    "server-duplicate-skills",
    "skill-no-uri",
    "skill-no-name",
    "skill-no-description",
    "server-metadata-incomplete",
    "tool-invocation-metadata-missing",
    "tool-inline-image-unbounded",
    "view-domain-invalid",
    "view-mimetype-invalid",
    "view-domains-inconsistent",
)
MIN_DESCRIPTION, MAX_DESCRIPTION = 10, 500


@dataclass
class Surface:
    """The server as a client sees it (JSON-shaped, camelCase keys)."""

    server_name: str | None = None
    server_version: str | None = None
    server_info: dict[str, Any] = field(default_factory=dict)
    tools: list[dict[str, Any]] = field(default_factory=list)
    resources: list[dict[str, Any]] = field(default_factory=list)
    resource_templates: list[dict[str, Any]] = field(default_factory=list)
    prompts: list[dict[str, Any]] = field(default_factory=list)
    #: ``skills/list`` entries (URI, frontmatter, resource digests). Empty when the
    #: server does not advertise the Skills extension.
    skills: list[dict[str, Any]] = field(default_factory=list)
    instructions: str | None = None
    #: Documented suppressions: {target: {rule: reason}} (e.g. from ``mcp_tool(lint_ignore=)``)
    ignores: dict[str, dict[str, str]] = field(default_factory=dict)


@dataclass
class Report:
    issues: list[LintIssue]
    score: int
    grade: str
    token_estimate: int
    counts: dict[str, int]
    server: dict[str, str | None] = field(default_factory=dict)
    suppressed: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "grade": self.grade,
            "score": self.score,
            "token_estimate": self.token_estimate,
            "counts": self.counts,
            "server": self.server,
            "suppressed": self.suppressed,
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
    meta = tool.get("_meta") or {}
    if (meta.get("ui") or {}).get("resourceUri"):
        labels = meta.get("openai/toolInvocation") or {}
        if any(
            not isinstance(labels.get(k), str) or not labels[k].strip()
            for k in ("invoking", "invoked")
        ):
            issues.append(
                _issue(
                    "warning",
                    "tool-invocation-metadata-missing",
                    target,
                    "UI tools need invoking and invoked labels in openai/toolInvocation",
                )
            )
        if _unbounded_inline(tool.get("outputSchema") or {}):
            issues.append(
                _issue(
                    "error",
                    "tool-inline-image-unbounded",
                    target,
                    "content_base64 needs a finite maxLength of at most 48000; verify total runtime result size separately",
                )
            )
    if not NAME_RE.match(name):
        issues.append(
            _issue(
                "info",
                "tool-name-convention",
                target,
                "name is not snake_case or kebab-case",
            )
        )
    from mcp.shared.tool_name_validation import validate_tool_name

    check = validate_tool_name(name)
    if name and not check.is_valid:
        issues.append(
            _issue(
                "warning",
                "tool-name-invalid",
                target,
                "; ".join(check.warnings) or "invalid tool name",
                "use 1-128 chars of A-Z a-z 0-9 _ - . (MCP SEP-986)",
            )
        )
    annotations = tool.get("annotations") or {}
    if not (tool.get("title") or annotations.get("title")):
        issues.append(
            _issue(
                "info",
                "tool-no-title",
                target,
                "no human-readable title",
                "set annotations.title",
            )
        )
    missing = [h for h in HINTS if h not in annotations]
    if missing:
        issues.append(
            _issue(
                "warning",
                "tool-missing-hints",
                target,
                f"missing annotations: {', '.join(missing)}",
                "declare side effects so clients can ask before risky calls",
            )
        )
    output = tool.get("outputSchema")
    if output is None:
        issues.append(
            _issue(
                "info",
                "tool-no-output-schema",
                target,
                "no outputSchema (no structured results)",
            )
        )
    elif not isinstance(output, dict) or output.get("type") != "object":
        issues.append(
            _issue(
                "error",
                "output-schema-not-object",
                target,
                "outputSchema must be a JSON Schema of type 'object'",
            )
        )
    size = len(json.dumps(tool, separators=(",", ":"))) // 4
    if size > MAX_TOOL_TOKENS:
        issues.append(
            _issue(
                "warning",
                "tool-too-large",
                target,
                f"definition is ~{size} tokens (> {MAX_TOOL_TOKENS})",
                "shorten descriptions or simplify the schemas",
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
    if props and schema.get("additionalProperties") is not False:
        issues.append(
            _issue(
                "info",
                "tool-schema-open",
                target,
                "inputSchema allows unknown arguments",
                "set additionalProperties: false so typos fail fast",
            )
        )
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


def _unbounded_inline(schema: Any) -> bool:
    if isinstance(schema, list):
        return any(_unbounded_inline(s) for s in schema)
    if not isinstance(schema, dict):
        return False
    prop = (schema.get("properties") or {}).get("content_base64")
    if isinstance(prop, dict):
        variants = [prop, *prop.get("anyOf", []), *prop.get("oneOf", [])]
        if not any(
            isinstance(v.get("maxLength"), int) and 0 < v["maxLength"] <= 48000
            for v in variants
        ):
            return True
    return any(_unbounded_inline(v) for v in schema.values())


def _https_origin(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        p = urlsplit(value)
        return bool(
            p.scheme == "https"
            and p.hostname
            and p.username is None
            and p.password is None
            and p.path in ("", "/")
            and not p.query
            and not p.fragment
            and p.port != 0
        )
    except ValueError:
        return False


def lint_resource(res: dict[str, Any]) -> list[LintIssue]:
    ident = res.get("uri") or res.get("uriTemplate") or res.get("name") or "?"
    target = f"resource:{ident}"
    issues = []
    if str(ident).startswith("ui://"):
        ui = (res.get("_meta") or {}).get("ui") or {}
        if not _https_origin(ui.get("domain")):
            issues.append(
                _issue(
                    "error",
                    "view-domain-invalid",
                    target,
                    "UI resources need one exact HTTPS origin in _meta.ui.domain",
                )
            )
        if res.get("mimeType") != "text/html;profile=mcp-app":
            issues.append(
                _issue(
                    "error",
                    "view-mimetype-invalid",
                    target,
                    "UI resources require text/html;profile=mcp-app",
                )
            )
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


def lint_skill(skill: dict[str, Any]) -> list[LintIssue]:
    uri = str(skill.get("uri") or "")
    target = f"skill:{uri or '?'}"
    front = skill.get("frontmatter")
    front = front if isinstance(front, dict) else {}
    name = str(front.get("name") or "")
    issues: list[LintIssue] = []
    if not uri:
        issues.append(_issue("error", "skill-no-uri", target, "skill has no URI"))
    if not name.strip():
        issues.append(
            _issue(
                "warning",
                "skill-no-name",
                target,
                "skill frontmatter has no name",
            )
        )
    issues += _description_issues(
        "skill", target, name, str(front.get("description") or "")
    )
    return issues


def lint_server(s: Surface) -> list[LintIssue]:
    issues = []
    if s.server_info:
        for key in ("title", "description", "websiteUrl", "icons"):
            if not s.server_info.get(key):
                issues.append(
                    _issue(
                        "warning",
                        "server-metadata-incomplete",
                        "server",
                        f"initialize serverInfo is missing {key}",
                    )
                )
    domains = {
        (r.get("_meta", {}).get("ui", {}).get("domain") or "").rstrip("/")
        for r in s.resources
        if str(r.get("uri", "")).startswith("ui://")
    }
    if len(domains) > 1:
        issues.append(
            _issue(
                "error",
                "view-domains-inconsistent",
                "server",
                "All UI resources must use the same HTTPS origin",
            )
        )
    if not (s.tools or s.resources or s.resource_templates or s.prompts or s.skills):
        issues.append(
            _issue(
                "error",
                "server-empty",
                "server",
                "server exposes no tools, resources, prompts or skills",
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
    if (s.tools or s.prompts) and not (s.instructions or "").strip():
        issues.append(
            _issue(
                "warning",
                "server-no-instructions",
                "server",
                "initialize returns no instructions",
                "tell agents how to use the server (workflow, key tools)",
            )
        )
    prompts = [str(p.get("name") or "") for p in s.prompts]
    for dup in sorted({n for n in prompts if prompts.count(n) > 1}):
        issues.append(
            _issue(
                "error",
                "server-duplicate-prompts",
                f"prompt:{dup}",
                "duplicate prompt name",
            )
        )
    uris = [
        str(r.get("uri") or r.get("uriTemplate") or "")
        for r in [*s.resources, *s.resource_templates]
    ]
    for dup in sorted({u for u in uris if u and uris.count(u) > 1}):
        issues.append(
            _issue(
                "error",
                "server-duplicate-resources",
                f"resource:{dup}",
                "duplicate resource URI",
            )
        )
    skill_uris = [str(sk.get("uri") or "") for sk in s.skills]
    for dup in sorted({n for n in skill_uris if n and skill_uris.count(n) > 1}):
        issues.append(
            _issue(
                "error",
                "server-duplicate-skills",
                f"skill:{dup}",
                "duplicate skill URI",
            )
        )
    return issues


def token_estimate(s: Surface) -> int:
    """~4 characters per token for the model-visible discovery surface."""
    payload = {
        "tools": [
            t
            for t in s.tools
            if t.get("_meta", {}).get("ui", {}).get("visibility") != ["app"]
        ],
        "resources": s.resources,
        "resourceTemplates": s.resource_templates,
        "prompts": s.prompts,
        "skills": s.skills,
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
    for skill in s.skills:
        issues += lint_skill(skill)
    issues, suppressed = apply_ignores(issues, s.ignores)
    score = (
        0
        if any(i.code == "server-empty" for i in issues)
        else max(0, 100 - sum(POINTS[i.severity] for i in issues))
    )
    counts = {
        "tools": len(s.tools),
        "resources": len(s.resources) + len(s.resource_templates),
        "prompts": len(s.prompts),
        "skills": len(s.skills),
    }
    server = {"name": s.server_name, "version": s.server_version}
    return Report(
        issues, score, grade_for(score), token_estimate(s), counts, server, suppressed
    )


def apply_ignores(
    issues: list[LintIssue], ignores: dict[str, dict[str, str]]
) -> tuple[list[LintIssue], list[dict[str, str]]]:
    """Split issues into kept and documented-suppressed (``rule`` at ``target``).

    A target also covers its parameters (``tool:x`` covers ``tool:x.param``);
    ``*`` matches every target. Suppressions need a reason and are reported.
    """
    kept: list[LintIssue] = []
    suppressed: list[dict[str, str]] = []
    for issue in issues:
        base = issue.target.split(".", 1)[0]
        reason = None
        for target in (issue.target, base, "*"):
            reason = (ignores.get(target) or {}).get(issue.code)
            if reason:
                break
        if reason:
            suppressed.append({**issue.as_dict(), "reason": reason})
        else:
            kept.append(issue)
    return kept, suppressed


def parse_ignore(spec: str) -> tuple[str, str]:
    """``rule`` or ``rule@target`` (CLI ``--ignore``) -> (target, rule)."""
    rule, _, target = spec.partition("@")
    return (target or "*"), rule


def _dump(items: list[Any]) -> list[dict[str, Any]]:
    return [i.model_dump(by_alias=True, exclude_none=True, mode="json") for i in items]


def _skills_method_missing(exc: BaseException) -> bool:
    error = getattr(exc, "error", None)
    if getattr(error, "code", None) == -32601:
        return True
    return "method not found" in str(exc).lower()


async def _list_skills(client: Any) -> list[dict[str, Any]]:
    """``skills/list`` entries, or [] when the server has no Skills extension."""
    from mcp.types import Request, RequestParams
    from pydantic import ConfigDict, TypeAdapter

    class _Params(RequestParams):
        model_config = ConfigDict(extra="allow")

    try:
        listing = await client.session.send_request(
            Request[_Params, str](method="skills/list", params=_Params()),
            TypeAdapter(dict),
        )
    except Exception as exc:
        if _skills_method_missing(exc):
            return []
        raise
    skills = listing.get("skills") if isinstance(listing, dict) else None
    if not isinstance(skills, list):
        return []
    return [item for item in skills if isinstance(item, dict)]


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
        ignores: dict[str, dict[str, str]] = {}
        if not url:
            from ..tools.tool_decorator import get_tool_registry

            for name, meta in get_tool_registry().items():
                if meta.get("lint_ignore"):
                    ignores[f"tool:{name}"] = dict(meta["lint_ignore"])
        return Surface(
            server_info=info.model_dump(by_alias=True, exclude_none=True, mode="json")
            if info
            else {},
            server_name=getattr(info, "name", None),
            server_version=getattr(info, "version", None),
            instructions=client.instructions,
            ignores=ignores,
            tools=_dump(await client.list_tools()),
            resources=_dump(await client.list_resources()),
            resource_templates=_dump(await client.list_resource_templates()),
            prompts=_dump(await client.list_prompts()),
            skills=await _list_skills(client),
        )


__all__ = [
    "EXTENDED_RULES",
    "GRADES",
    "POINTS",
    "Report",
    "Surface",
    "apply_ignores",
    "fetch_surface",
    "grade_for",
    "lint_prompt",
    "lint_resource",
    "lint_server",
    "lint_skill",
    "lint_surface",
    "lint_tool",
    "parse_ignore",
    "token_estimate",
]
