"""UML-MCP plugin: a C4 model you can drill into.

One diagram type, ``c4_model``. The source is a single JSON model covering three C4 levels:
people and software systems (context), the containers inside a system, and the components
inside a container, with relations between elements at any level.

* ``svg``: the starting view (``view.level`` and ``view.focus``) in C4 notation, with a legend.
* ``html``: a standalone page that starts there; click a system to open its containers, a
  container to open its components, and the breadcrumbs to go back up. Relations are lifted
  to the level on screen, each element has a detail card, and the current level exports to
  SVG, PNG or HTML.
"""

from __future__ import annotations

from typing import Any

from mcp_core.plugins import DiagramTypeSpec, RenderOutput

from . import html
from .model import MAX_ELEMENTS, SpecError, parse
from .samples import EXAMPLE, TEMPLATE
from .svg import view_svg
from .views import best_direction, build

__all__ = ["C4Renderer"]

DESCRIPTION = (
    "C4 model (context, containers, components) from one JSON model: static C4 diagram of a "
    "chosen level, or an interactive page that drills from systems into containers and "
    "components; html or svg"
)


class C4Renderer:
    """Render ``c4_model`` locally, without network access."""

    name = "c4"
    version = "0.1.0"

    def __init__(self) -> None:
        self.max_elements = MAX_ELEMENTS
        self.diagram_types = {
            "c4_model": DiagramTypeSpec(
                DESCRIPTION,
                ("html", "svg"),
                example=EXAMPLE,
                template=TEMPLATE,
                version=self.version,
                source_schema="urn:uml-mcp:c4-model:1",
                interaction_features=("zoom", "pan", "fit", "drilldown", "inspect"),
                security_profile="sandboxed",
                renderer_capabilities_version=2,
            )
        }

    def configure(self, settings: dict[str, Any]) -> None:
        """``plugins.settings.c4``: ``max_elements`` (1 to 300)."""
        value = settings.get("max_elements", MAX_ELEMENTS)
        if type(value) is not int or not 1 <= value <= MAX_ELEMENTS:
            raise ValueError(
                f"max_elements must be an integer from 1 to {MAX_ELEMENTS}"
            )
        self.max_elements = value

    def validate(self, diagram_type: str, code: str) -> list[str]:
        if diagram_type not in self.diagram_types:
            return [f"unknown c4 type: {diagram_type}"]
        try:
            parse(code, max_elements=self.max_elements)
        except SpecError as exc:
            return exc.problems
        return []

    def render(self, diagram_type: str, code: str, output_format: str) -> RenderOutput:
        if diagram_type not in self.diagram_types:
            raise ValueError(f"unknown c4 type: {diagram_type}")
        if output_format not in ("html", "svg"):
            raise ValueError("c4_model renders html or svg")
        try:
            model = parse(code, max_elements=self.max_elements)
        except SpecError as exc:
            raise ValueError(
                "invalid c4_model source: " + "; ".join(exc.problems)
            ) from exc
        if output_format == "html":
            return RenderOutput(
                html.page(model).encode("utf-8"), "text/html; charset=utf-8"
            )
        theme = "light" if model.theme == "light" else "dark"
        direction = best_direction(model, model.level, model.focus)
        view = build(model, model.level, model.focus, direction)
        return RenderOutput(
            view_svg(model, view, theme).encode("utf-8"), "image/svg+xml"
        )
