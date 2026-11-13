"""Render each bundled interactive diagram example for the README gallery.

Run with ``uv run python scripts/build_interactive_gallery.py``.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for source in (ROOT / "examples/plugins").glob("*/src"):
    sys.path.insert(0, str(source))

from mcp_core.core.svg_raster import svg_to_png

RENDERERS = (
    ("d3", "D3Renderer"),
    ("stack_diagram", "StackDiagramRenderer"),
    ("archify", "ArchifyRenderer"),
    ("llm_visualizer", "LLMVisualizerRenderer"),
    ("schema", "SchemaRenderer"),
    ("deps", "DepsRenderer"),
    ("statechart", "StatechartRenderer"),
    ("trace", "TraceRenderer"),
    ("c4", "C4Renderer"),
    ("timeline", "TimelineRenderer"),
)


def main() -> None:
    destination = ROOT / "docs/assets/interactive"
    destination.mkdir(parents=True, exist_ok=True)
    for module, class_name in RENDERERS:
        renderer = getattr(
            importlib.import_module(f"uml_mcp_plugin_{module}"), class_name
        )()
        for diagram_type, spec in renderer.diagram_types.items():
            if not spec.example:
                raise ValueError(f"Missing example for {diagram_type}")
            errors = renderer.validate(diagram_type, spec.example)
            if errors:
                raise ValueError(f"Invalid {diagram_type} example: {errors}")
            svg = renderer.render(diagram_type, spec.example, "svg").content
            png = svg_to_png(svg, zoom=1.5)
            if not png:
                raise RuntimeError(f"Could not rasterize {diagram_type}")
            (destination / f"{diagram_type}.png").write_bytes(png)
            print(diagram_type)


if __name__ == "__main__":
    main()
