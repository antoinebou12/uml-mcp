"""UML-MCP plugin: dependency graphs from manifests and lock files.

One diagram type, ``dependency_graph``. Paste a ``package.json``, ``package-lock.json``
(v2/v3), ``pyproject.toml``, ``requirements.txt`` or ``uv.lock``, or a JSON graph
``{root, nodes, edges}``; the file kind is detected. Renders ``svg`` (a layered tree with
kind colours, licence badges and duplicate versions flagged) or ``html`` (a standalone,
CSP-locked page with collapse, search, filters, a detail card, tree and force views and
SVG/PNG/HTML export). Parsing uses the standard library only and never fetches anything.
"""

from __future__ import annotations

from typing import Any

from mcp_core.plugins import DiagramTypeSpec, RenderOutput

from . import html, svg
from .layout import DEFAULT_MAX_NODES, MAX_NODES, build
from .model import SpecError
from .parsers import parse
from .samples import EXAMPLE, TEMPLATE

__all__ = ["DepsRenderer"]

DESCRIPTION = (
    "Dependency graph of a project from its package.json, package-lock.json, "
    "pyproject.toml, requirements.txt or uv.lock (auto-detected): layered tree, kind "
    "colours, licences, duplicate versions; html (search, collapse, force view) or svg"
)


class DepsRenderer:
    """Render ``dependency_graph`` locally, without network access."""

    name = "deps"

    def __init__(self) -> None:
        self.max_nodes = DEFAULT_MAX_NODES
        self.diagram_types = {
            "dependency_graph": DiagramTypeSpec(
                DESCRIPTION,
                ("html", "svg"),
                example=EXAMPLE,
                template=TEMPLATE,
                version="1.0.0",
                source_schema="urn:uml-mcp:dependency-graph:1",
                interaction_features=("zoom", "pan", "fit", "inspect", "trace"),
                security_profile="sandboxed",
                renderer_capabilities_version=2,
            )
        }

    def configure(self, settings: dict[str, Any]) -> None:
        """``plugins.settings.deps``: ``max_nodes`` (packages drawn, default 300)."""
        limit = int(settings.get("max_nodes", DEFAULT_MAX_NODES))
        if not 1 <= limit <= MAX_NODES:
            raise ValueError(f"max_nodes must be between 1 and {MAX_NODES}")
        self.max_nodes = limit

    def validate(self, diagram_type: str, code: str) -> list[str]:
        self._check_type(diagram_type)
        try:
            parse(code)
        except SpecError as exc:
            return exc.problems
        return []

    def render(self, diagram_type: str, code: str, output_format: str) -> RenderOutput:
        self._check_type(diagram_type)
        if output_format not in ("html", "svg"):
            raise ValueError("dependency_graph renders html or svg")
        try:
            graph = parse(code)
        except SpecError as exc:
            raise ValueError(
                "invalid dependency_graph source: " + "; ".join(exc.problems)
            ) from exc
        tree = build(graph, self.max_nodes)
        if output_format == "svg":
            text = svg.render(tree, graph.theme)
            return RenderOutput(text.encode("utf-8"), "image/svg+xml")
        text = html.page(tree)
        return RenderOutput(text.encode("utf-8"), "text/html; charset=utf-8")

    def _check_type(self, diagram_type: str) -> None:
        if diagram_type not in self.diagram_types:
            raise ValueError(f"unknown diagram type {diagram_type!r} for plugin deps")
