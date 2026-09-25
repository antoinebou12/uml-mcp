"""``uml-mcp lint``: quality checks for MCP definitions and configuration.

Inspired by MXCP's linter: good descriptions and annotations make tools usable
by LLMs, and configuration mistakes should be caught before deployment.
"""

from __future__ import annotations

import inspect
import re
from dataclasses import asdict, dataclass
from typing import Any

MIN_TOOL_DESCRIPTION = 40
MIN_DESCRIPTION = 15


@dataclass(frozen=True)
class LintIssue:
    severity: str  # error | warning | info
    code: str
    target: str
    message: str
    fix: str = ""

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _documented_params(func: Any) -> set[str]:
    doc = inspect.getdoc(func) or ""
    match = re.search(r"Args:\n(.*?)(\n\S|\Z)", doc, re.DOTALL)
    if not match:
        return set()
    return set(
        re.findall(r"^\s{2,}(\w+)(?:\s*\([^)]*\))?:", match.group(1), re.MULTILINE)
    )


def lint_tools(tools: dict[str, dict[str, Any]]) -> list[LintIssue]:
    issues: list[LintIssue] = []
    for name, info in sorted(tools.items()):
        target = f"tool:{name}"
        desc = (info.get("description") or "").strip()
        if not desc:
            issues.append(
                LintIssue(
                    "error",
                    "TOOL001",
                    target,
                    "tool has no description",
                    "add description= to @mcp_tool",
                )
            )
        elif len(desc) < MIN_TOOL_DESCRIPTION:
            issues.append(
                LintIssue(
                    "warning",
                    "TOOL002",
                    target,
                    f"description is short ({len(desc)} chars)",
                    "say what it does, when to use it and what it returns",
                )
            )
        ann = info.get("annotations") or {}
        for hint in (
            "readOnlyHint",
            "destructiveHint",
            "idempotentHint",
            "openWorldHint",
        ):
            if hint not in ann:
                issues.append(
                    LintIssue(
                        "warning",
                        "TOOL003",
                        target,
                        f"missing annotation {hint}",
                        "set MCP tool annotations (also drives read/write auth)",
                    )
                )
        if "title" not in ann:
            issues.append(
                LintIssue("info", "TOOL004", target, "missing annotations.title")
            )
        if info.get("output_schema") is None:
            issues.append(
                LintIssue(
                    "warning",
                    "TOOL005",
                    target,
                    "no output schema",
                    "declare output_schema= for structured results",
                )
            )
        func = info.get("function")
        if func is not None:
            params = [
                p
                for p in inspect.signature(func).parameters.values()
                if p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
            ]
            documented = _documented_params(func)
            for p in params:
                if p.annotation is inspect.Parameter.empty:
                    issues.append(
                        LintIssue(
                            "warning",
                            "TOOL006",
                            target,
                            f"parameter '{p.name}' has no type annotation",
                        )
                    )
                if p.name not in documented:
                    issues.append(
                        LintIssue(
                            "warning",
                            "TOOL007",
                            target,
                            f"parameter '{p.name}' is not described in Args:",
                            "document every parameter in the docstring",
                        )
                    )
        if not info.get("example"):
            issues.append(LintIssue("info", "TOOL008", target, "no usage example"))
    return issues


def lint_named(kind: str, items: dict[str, dict[str, Any]]) -> list[LintIssue]:
    issues = []
    for name, info in sorted(items.items()):
        desc = (info.get("description") or "").strip()
        if len(desc) < MIN_DESCRIPTION:
            issues.append(
                LintIssue(
                    "warning",
                    f"{kind.upper()[:4]}001",
                    f"{kind}:{name}",
                    "description missing or too short",
                )
            )
    return issues


def lint_config(
    app: Any, auth: Any | None, tools: dict[str, dict[str, Any]]
) -> list[LintIssue]:
    issues: list[LintIssue] = []
    auth_on = auth is not None and getattr(auth, "enabled", False)
    if auth_on and not str(auth.resource_url).startswith("https://"):
        issues.append(
            LintIssue(
                "warning",
                "CFG001",
                "auth.resource_url",
                "resource URL is not https (loopback development only)",
            )
        )
    if auth_on and not app.audit.enabled:
        issues.append(
            LintIssue(
                "warning",
                "CFG002",
                "audit.enabled",
                "auth is enabled but the audit trail is off",
                "set audit.enabled: true (sinks: stream/file)",
            )
        )
    if auth_on and not app.rate_limit.enabled:
        issues.append(
            LintIssue(
                "warning",
                "CFG003",
                "rate_limit.enabled",
                "auth is enabled but rate limiting is off",
            )
        )
    if app.audit.enabled and app.audit.include_inputs == "full":
        issues.append(
            LintIssue(
                "warning",
                "CFG004",
                "audit.include_inputs",
                "full inputs may store sensitive diagram content",
                "prefer 'redacted'",
            )
        )
    if app.audit.enabled and "file" in app.audit.sinks and app.audit.file is None:
        issues.append(
            LintIssue("error", "CFG005", "audit.file", "file sink without audit.file")
        )
    if app.admin.allow_local_without_auth and auth_on:
        issues.append(
            LintIssue(
                "info",
                "CFG006",
                "admin.allow_local_without_auth",
                "ignored while auth is enabled",
            )
        )
    unknown = [
        t for t in [*(app.tools.enabled or []), *app.tools.disabled] if t not in tools
    ]
    for name in unknown:
        issues.append(LintIssue("error", "CFG007", "tools", f"unknown tool '{name}'"))
    for name in app.rate_limit.tools:
        if name not in tools:
            issues.append(
                LintIssue(
                    "error", "CFG008", "rate_limit.tools", f"unknown tool '{name}'"
                )
            )
    for name in app.tools.disabled:
        issues.append(
            LintIssue("info", "CFG009", f"tool:{name}", "disabled by configuration")
        )
    if auth_on:
        for name, info in tools.items():
            if "readOnlyHint" not in (info.get("annotations") or {}) and (
                name not in auth.tool_permissions
            ):
                issues.append(
                    LintIssue(
                        "warning",
                        "AUTH001",
                        f"tool:{name}",
                        "no readOnlyHint/tool_permissions: defaults to write",
                    )
                )
    return issues


def run_lint() -> list[LintIssue]:
    """Lint the live registries and the effective configuration."""
    from ..core.settings_file import get_app_config
    from ..prompts.diagram_prompts import get_prompt_registry
    from ..resources import diagram_resources
    from ..tools import diagram_tools  # noqa: F401 - populate the registry
    from ..tools.tool_decorator import get_tool_registry

    tools = get_tool_registry()
    issues = lint_tools(tools)
    issues += lint_named("prompt", get_prompt_registry())
    resources = getattr(diagram_resources, "_registered_resources", {})
    issues += lint_named("resource", resources)
    auth = None
    try:
        from ..auth import auth_requested

        if auth_requested():
            from ..auth.settings import get_auth_settings

            auth = get_auth_settings()
    except Exception as exc:  # noqa: BLE001 - surfaced as a lint error
        issues.append(LintIssue("error", "CFG000", "auth", str(exc)))
    issues += lint_config(get_app_config(), auth, tools)
    return issues


def exit_code(issues: list[LintIssue], strict: bool = False) -> int:
    if any(i.severity == "error" for i in issues):
        return 1
    if strict and any(i.severity == "warning" for i in issues):
        return 1
    return 0


__all__ = [
    "LintIssue",
    "exit_code",
    "lint_config",
    "lint_named",
    "lint_tools",
    "run_lint",
]
