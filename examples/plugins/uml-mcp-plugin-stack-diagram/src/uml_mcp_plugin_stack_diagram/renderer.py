"""A reusable UML-MCP renderer for auto-layout diagram types with a pluggable skin."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from mcp_core.plugins import DiagramTypeSpec, RenderOutput

from . import html
from .layout import layout
from .render import Skin, render_svg
from .spec import MAX_NODES, SpecError, parse

FEATURES = ("zoom", "pan", "fit", "theme", "directions")


@dataclass(frozen=True)
class TypeDef:
    description: str
    example: str
    template: str
    direction: str = "LR"


class AutoLayoutRenderer:
    """Subclass and set ``name``, ``skin`` and ``types``."""

    name: ClassVar[str] = "autolayout"
    skin: ClassVar[Skin]
    types: ClassVar[dict[str, TypeDef]]
    schema: ClassVar[str] = "urn:uml-mcp:autolayout:1"
    version: ClassVar[str] = "0.1.0"

    def __init__(self) -> None:
        self.max_nodes = MAX_NODES
        self.diagram_types = {
            key: DiagramTypeSpec(
                t.description,
                ("html", "svg"),
                example=t.example,
                template=t.template,
                version=self.version,
                source_schema=self.schema,
                interaction_features=FEATURES,
                security_profile="sandboxed",
                renderer_capabilities_version=2,
            )
            for key, t in self.types.items()
        }

    def configure(self, settings: dict[str, Any]) -> None:
        value = settings.get("max_nodes", MAX_NODES)
        if type(value) is not int or not 1 <= value <= MAX_NODES:
            raise ValueError(f"max_nodes must be an integer from 1 to {MAX_NODES}")
        self.max_nodes = value

    def _parse(self, diagram_type: str, code: str):
        if diagram_type not in self.types:
            raise SpecError(f"unknown {self.name} type: {diagram_type}")
        return parse(
            code,
            group_styles=self.skin.group_styles,
            default_direction=self.types[diagram_type].direction,
            max_nodes=self.max_nodes,
            presets=tuple(self.skin.presets),
        )

    def validate(self, diagram_type: str, code: str) -> list[str]:
        try:
            self._parse(diagram_type, code)
        except SpecError as exc:
            return [str(exc)]
        return []

    def render(self, diagram_type: str, code: str, output_format: str) -> RenderOutput:
        if output_format not in {"html", "svg"}:
            raise ValueError(f"{self.name} renders html or svg")
        try:
            spec = self._parse(diagram_type, code)
        except SpecError as exc:
            raise ValueError(f"invalid {diagram_type} source: {exc}") from exc
        arranged = layout(spec, self.skin.metrics)
        if output_format == "html":
            return RenderOutput(
                html.page(spec, arranged, self.skin).encode("utf-8"),
                "text/html; charset=utf-8",
            )
        return RenderOutput(
            render_svg(spec, arranged, self.skin).encode("utf-8"), "image/svg+xml"
        )
