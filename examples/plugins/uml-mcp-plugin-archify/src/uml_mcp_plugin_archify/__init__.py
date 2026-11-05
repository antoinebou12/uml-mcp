"""UML-MCP plugin: archify-style architecture, workflow and sequence diagrams.

Dashed, colour-coded group containers (security, frontend, backend, bus, workers,
database, cloud), icon cards, labelled arrows, a legend and three presets (``classic``,
``blueprint``, ``flow``), auto-laid out left to right or top down in dark, light or
``auto``. The layout engine comes from ``uml-mcp-plugin-stack-diagram``.

* ``archify_architecture``: systems and their groups, flowing left to right.
* ``archify_workflow``: steps and hand-offs, flowing top down.
* ``archify_sequence``: participants, lifelines and ordered messages.

Every type renders to ``html`` (focus, shortest path, live edges, theme and preset picker)
or ``svg`` (also previewed as PNG for clients without MCP Apps).
"""

from __future__ import annotations

from typing import Any, ClassVar

from uml_mcp_plugin_stack_diagram.renderer import AutoLayoutRenderer, TypeDef
from uml_mcp_plugin_stack_diagram.spec import SpecError

from mcp_core.plugins import RenderOutput

from . import sequence
from .samples import (
    ARCHITECTURE,
    SEQUENCE,
    SEQUENCE_TEMPLATE,
    WORKFLOW,
    WORKFLOW_TEMPLATE,
)
from .skin import ArchifySkin

__all__ = ["ArchifyRenderer", "ArchifySkin"]

SEQUENCE_TYPE = "archify_sequence"


class ArchifyRenderer(AutoLayoutRenderer):
    name = "archify"
    skin = ArchifySkin()
    schema = "urn:uml-mcp:archify:1"
    types: ClassVar[dict[str, TypeDef]] = {
        "archify_architecture": TypeDef(
            "Architecture diagram with dashed colour-coded groups (security, frontend, backend, "
            "bus, workers, database, cloud), icon cards, a legend and labelled arrows; auto-laid "
            "out left-right or top-down, dark, light or auto, in classic, blueprint or flow "
            "presets. JSON nodes, groups, edges; html or svg",
            ARCHITECTURE,
            WORKFLOW_TEMPLATE,
            direction="LR",
        ),
        "archify_workflow": TypeDef(
            "Workflow or process diagram: steps grouped into stages, hand-offs between them, "
            "flowing top-down by default; dark, light or auto. Same JSON as "
            "archify_architecture; html or svg",
            WORKFLOW,
            WORKFLOW_TEMPLATE,
            direction="TB",
        ),
        SEQUENCE_TYPE: TypeDef(
            "Sequence diagram: participants across the top, lifelines and ordered call and "
            "reply messages; dark, light or auto. JSON participants and messages; html or svg",
            SEQUENCE,
            SEQUENCE_TEMPLATE,
        ),
    }

    def validate(self, diagram_type: str, code: str) -> list[str]:
        if diagram_type != SEQUENCE_TYPE:
            return super().validate(diagram_type, code)
        try:
            self._sequence(code)
        except SpecError as exc:
            return [str(exc)]
        return []

    def render(self, diagram_type: str, code: str, output_format: str) -> RenderOutput:
        if diagram_type != SEQUENCE_TYPE:
            return super().render(diagram_type, code, output_format)
        if output_format not in {"html", "svg"}:
            raise ValueError("archify renders html or svg")
        try:
            spec = self._sequence(code)
        except SpecError as exc:
            raise ValueError(f"invalid {diagram_type} source: {exc}") from exc
        if output_format == "html":
            return RenderOutput(
                sequence.page(spec, self.skin).encode("utf-8"),
                "text/html; charset=utf-8",
            )
        return RenderOutput(
            sequence.render_static(spec, self.skin).encode("utf-8"), "image/svg+xml"
        )

    def _sequence(self, code: str) -> Any:
        return sequence.parse(
            code,
            presets=tuple(self.skin.presets),
            max_participants=min(self.max_nodes, sequence.MAX_PARTICIPANTS),
        )
