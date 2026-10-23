"""MCP ``completion/complete`` candidates for resource templates and prompts.

Completions cover prompt arguments and resource-template parameters (not tool
args). UML-MCP wires them for ``uml://…/{diagram_type|recipe_id}`` and for
``diagram_theme`` / ``uml_diagram`` prompt ``context`` prefixes.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from mcp_core.core.config import MCP_SETTINGS
from mcp_core.core.diagram_themes import (
    D2_THEME_ALIASES,
    PLANTUML_RECOMMENDED_THEMES,
)
from mcp_core.core.mermaid_source import MERMAID_THEMES

RECIPE_IDS: tuple[str, ...] = ("algorithm_flowchart", "paper_concept")

TEMPLATE_URIS: frozenset[str] = frozenset(
    {
        "uml://templates/{diagram_type}",
        "uml://examples/{diagram_type}",
        "uml://formats/{diagram_type}",
        "uml://recipes/{recipe_id}",
    }
)

BACKGROUND_VALUES: tuple[str, ...] = (
    "light",
    "white",
    "dark",
    "black",
    "bw",
    "print",
    "mono",
)


def filter_completion_values(
    candidates: Iterable[str],
    prefix: str | None,
    *,
    limit: int = 100,
) -> list[str]:
    """Return up to ``limit`` candidates matching ``prefix`` (case-insensitive)."""
    ordered = sorted({c for c in candidates if c})
    needle = (prefix or "").strip().lower()
    if not needle:
        return ordered[:limit]
    starts = [c for c in ordered if c.lower().startswith(needle)]
    if starts:
        return starts[:limit]
    return [c for c in ordered if needle in c.lower()][:limit]


def diagram_type_names() -> list[str]:
    return sorted(MCP_SETTINGS.diagram_types.keys())


def _plantuml_theme_names() -> list[str]:
    try:
        from tools.kroki.plantuml_themes import THEMES

        return [t.value for t in THEMES if t.value != "none"]
    except Exception:  # noqa: BLE001
        return list(PLANTUML_RECOMMENDED_THEMES)


def theme_names(*, diagram_type: str | None = None) -> list[str]:
    """Theme strings accepted by ``generate_uml`` ``theme=``."""
    if diagram_type:
        cfg = MCP_SETTINGS.diagram_types.get(diagram_type.strip().lower())
        backend = (cfg.backend if cfg else "") or ""
        if backend in {"plantuml", "c4plantuml"}:
            return sorted(_plantuml_theme_names())
        if backend == "mermaid":
            return sorted(MERMAID_THEMES)
        if backend == "d2":
            return sorted(D2_THEME_ALIASES.keys())
    names: set[str] = set(PLANTUML_RECOMMENDED_THEMES)
    names.update(MERMAID_THEMES)
    names.update(D2_THEME_ALIASES.keys())
    return sorted(names)


def _json_value_prefix(partial: str) -> str:
    """Best-effort extract of the string value being typed inside a JSON blob."""
    text = partial or ""
    for sep in (': "', ": '", ':"', ":'"):
        if sep in text:
            text = text.rsplit(sep, 1)[-1]
            break
    return text.rstrip('",} \t\n')


def complete_argument(
    ref: Any,
    argument: Any,
    context: Any | None = None,
) -> list[str] | None:
    """FastMCP ``@server.completion`` handler body."""
    try:
        from mcp import types as mcp_types
    except ImportError:  # pragma: no cover
        return None

    name = getattr(argument, "name", None) or ""
    value = getattr(argument, "value", None)
    prefix = value if isinstance(value, str) else ""

    if isinstance(ref, mcp_types.ResourceTemplateReference):
        uri = str(getattr(ref, "uri", "") or "")
        if uri not in TEMPLATE_URIS:
            return None
        if name == "diagram_type":
            return filter_completion_values(diagram_type_names(), prefix)
        if name == "recipe_id":
            return filter_completion_values(RECIPE_IDS, prefix)
        return None

    if isinstance(ref, mcp_types.PromptReference):
        prompt_name = str(getattr(ref, "name", "") or "")
        if name != "context":
            return None
        if prompt_name == "diagram_theme":
            token = _json_value_prefix(prefix)
            if '"background"' in prefix or "background" in prefix.lower():
                return filter_completion_values(BACKGROUND_VALUES, token)
            if '"diagram_type"' in prefix or "diagram_type" in prefix.lower():
                return filter_completion_values(diagram_type_names(), token)
            return filter_completion_values(
                [*BACKGROUND_VALUES, *diagram_type_names()], prefix
            )
        if prompt_name == "uml_diagram":
            token = _json_value_prefix(prefix) or prefix
            return filter_completion_values(diagram_type_names(), token)
        return None

    return None


def register_completions(server: Any) -> None:
    """Attach the server-level completion handler (declares completions capability)."""
    completion = getattr(server, "completion", None)
    if not callable(completion):
        return

    def _handler(
        ref: Any, argument: Any, context: Any | None = None
    ) -> list[str] | None:
        return complete_argument(ref, argument, context)

    try:
        completion(_handler)
    except TypeError:
        decorated = completion()
        if callable(decorated):
            decorated(_handler)
