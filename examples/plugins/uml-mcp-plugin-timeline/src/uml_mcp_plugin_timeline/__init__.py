"""UML-MCP plugin: project timelines and roadmaps (``timeline``).

Swimlanes, tasks with progress and status, phases, milestones, releases and dependency
arrows, from a JSON source. Renders a static SVG, or a standalone interactive page that zooms
between quarters, months, weeks and days, filters by lane, owner and status, and shows a
detail card with the item's dependency chain.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from mcp_core.plugins import DiagramTypeSpec, RenderOutput

from . import html, svg
from .model import MAX_ITEMS, SpecError, parse, to_day
from .samples import EXAMPLE, TEMPLATE

__all__ = ["TimelineRenderer"]

FEATURES = ("zoom", "pan", "fit", "filter", "inspect", "trace", "theme", "export")


class TimelineRenderer:
    """Render a timeline source to SVG or an interactive HTML page."""

    name = "timeline"

    def __init__(self) -> None:
        self.max_items = MAX_ITEMS
        self.diagram_types = {
            "timeline": DiagramTypeSpec(
                "Project timeline or product roadmap: swimlanes, task bars with progress and "
                "status, phases, milestones, releases, dependency arrows and a today line. "
                "JSON lanes and items with ISO dates or quarters; html or svg",
                ("html", "svg"),
                example=EXAMPLE,
                template=TEMPLATE,
                version="0.1.0",
                source_schema="urn:uml-mcp:timeline:1",
                interaction_features=FEATURES,
                security_profile="sandboxed",
                renderer_capabilities_version=2,
            )
        }

    def configure(self, settings: dict[str, Any]) -> None:
        value = settings.get("max_items", MAX_ITEMS)
        if type(value) is not int or not 1 <= value <= MAX_ITEMS:
            raise ValueError(f"max_items must be an integer from 1 to {MAX_ITEMS}")
        self.max_items = value

    def validate(self, diagram_type: str, code: str) -> list[str]:
        if diagram_type not in self.diagram_types:
            return [f"unknown timeline type: {diagram_type}"]
        try:
            parse(code, max_items=self.max_items)
        except SpecError as exc:
            return list(exc.problems)
        return []

    def render(self, diagram_type: str, code: str, output_format: str) -> RenderOutput:
        if diagram_type not in self.diagram_types:
            raise ValueError(f"unknown timeline type: {diagram_type}")
        if output_format not in {"html", "svg"}:
            raise ValueError("timeline renders html or svg")
        try:
            spec = parse(code, max_items=self.max_items)
        except SpecError as exc:
            raise ValueError(f"invalid timeline source: {exc}") from exc
        if output_format == "html":
            return RenderOutput(
                html.page(spec).encode("utf-8"), "text/html; charset=utf-8"
            )
        content = svg.render_svg(spec, today=to_day(datetime.now(UTC).date()))
        return RenderOutput(content.encode("utf-8"), "image/svg+xml")
