"""UML-MCP plugin: statecharts you can run.

One diagram type, ``state_machine``: an XState-like JSON machine drawn as a statechart
(nested compound states, parallel regions, initial, final and history pseudo-states,
labelled orthogonal transitions), as a static SVG or an interactive simulator page that
highlights the active states and fires the events enabled in them.
"""

from __future__ import annotations

from typing import Any

from mcp_core.plugins import DiagramTypeSpec, RenderOutput

from . import html
from .layout import layout
from .model import MAX_STATES, SpecError, parse, warnings_for
from .samples import EXAMPLE, TEMPLATE
from .svg import render_svg

__all__ = ["StatechartRenderer"]

TYPE = "state_machine"
FEATURES = ("zoom", "pan", "fit", "theme", "inspect", "simulate", "undo", "export")


class StatechartRenderer:
    """Render an XState-like machine as a statechart image or a simulator page."""

    name = "statechart"
    version = "0.1.0"

    def __init__(self) -> None:
        self.max_states = MAX_STATES
        self.diagram_types = {
            TYPE: DiagramTypeSpec(
                "State machine (statechart) from XState-like JSON: compound and parallel "
                "states, initial, final and history states, guarded transitions with actions. "
                "html is a simulator (fire events, step log, undo); svg is a static image",
                ("html", "svg"),
                example=EXAMPLE,
                template=TEMPLATE,
                version=self.version,
                source_schema="urn:uml-mcp:statechart:1",
                interaction_features=FEATURES,
                security_profile="sandboxed",
                renderer_capabilities_version=2,
            )
        }

    def configure(self, settings: dict[str, Any]) -> None:
        value = settings.get("max_states", MAX_STATES)
        if type(value) is not int or not 1 <= value <= MAX_STATES:
            raise ValueError(f"max_states must be an integer from 1 to {MAX_STATES}")
        self.max_states = value

    def _parse(self, diagram_type: str, code: str):
        if diagram_type not in self.diagram_types:
            raise SpecError([f"unknown statechart type: {diagram_type}"])
        return parse(code, max_states=self.max_states)

    def validate(self, diagram_type: str, code: str) -> list[str]:
        try:
            self._parse(diagram_type, code)
        except SpecError as exc:
            return list(exc.problems)
        return []

    def warnings(self, diagram_type: str, code: str) -> list[str]:
        """Problems that still render, such as states no transition reaches."""
        try:
            return warnings_for(self._parse(diagram_type, code))
        except SpecError:
            return []

    def render(self, diagram_type: str, code: str, output_format: str) -> RenderOutput:
        if output_format not in {"html", "svg"}:
            raise ValueError("statechart renders html or svg")
        try:
            machine = self._parse(diagram_type, code)
        except SpecError as exc:
            raise ValueError(f"invalid {diagram_type} source: {exc}") from exc
        arranged = layout(machine)
        if output_format == "html":
            return RenderOutput(
                html.page(machine, arranged, warnings_for(machine)).encode("utf-8"),
                "text/html; charset=utf-8",
            )
        return RenderOutput(
            render_svg(machine, arranged, machine.theme).encode("utf-8"),
            "image/svg+xml",
        )
