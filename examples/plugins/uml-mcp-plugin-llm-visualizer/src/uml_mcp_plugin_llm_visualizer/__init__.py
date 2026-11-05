"""Interactive 2D and 3D LLM architecture diagrams for UML-MCP."""

from __future__ import annotations

from typing import Any

from mcp_core.plugins import DiagramTypeSpec, RenderOutput

from . import html, svg
from .model import MAX_LAYERS, SpecError, parse
from .samples import SAMPLES

__all__ = ["LLMVisualizerRenderer"]


class LLMVisualizerRenderer:
    """Render one architecture source as a 2D map or interactive 3D scene."""

    name = "llm-visualizer"

    def __init__(self) -> None:
        self.max_layers = MAX_LAYERS
        features = ("zoom", "pan", "inspect", "rotate", "switch-view", "reset")
        descriptions = {
            "llm_2d": (
                "LLM architecture as a 2D layer and tensor map. JSON layers and "
                "connections; standalone interactive HTML or static SVG"
            ),
            "llm_3d": (
                "LLM architecture as a rotatable perspective scene. JSON layers and "
                "connections; standalone interactive HTML or static isometric SVG"
            ),
        }
        self.diagram_types = {
            diagram_type: DiagramTypeSpec(
                descriptions[diagram_type],
                ("html", "svg"),
                example=example,
                template=template,
                version="0.1.0",
                source_schema="urn:uml-mcp:llm-visualizer:1",
                interaction_features=features,
                security_profile="sandboxed",
                renderer_capabilities_version=2,
            )
            for diagram_type, (example, template) in SAMPLES.items()
        }

    def configure(self, settings: dict[str, Any]) -> None:
        value = settings.get("max_layers", MAX_LAYERS)
        if type(value) is not int or not 1 <= value <= MAX_LAYERS:
            raise ValueError(f"max_layers must be an integer from 1 to {MAX_LAYERS}")
        self.max_layers = value

    def validate(self, diagram_type: str, code: str) -> list[str]:
        if diagram_type not in self.diagram_types:
            return [f"unknown LLM visualizer type: {diagram_type}"]
        try:
            parse(code, max_layers=self.max_layers)
        except SpecError as exc:
            return [str(exc)]
        return []

    def render(self, diagram_type: str, code: str, output_format: str) -> RenderOutput:
        if diagram_type not in self.diagram_types:
            raise ValueError(f"unknown LLM visualizer type: {diagram_type}")
        if output_format not in {"html", "svg"}:
            raise ValueError("LLM visualizer renders html or svg")
        spec = parse(code, max_layers=self.max_layers)
        if output_format == "html":
            content = html.page(
                spec, initial_mode="2d" if diagram_type == "llm_2d" else "3d"
            )
            return RenderOutput(content.encode("utf-8"), "text/html; charset=utf-8")
        content = (
            svg.render_2d(spec) if diagram_type == "llm_2d" else svg.render_3d(spec)
        )
        return RenderOutput(content.encode("utf-8"), "image/svg+xml")
