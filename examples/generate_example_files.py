"""
Generate one example file per Kroki diagram type from DiagramExamples.
Run from project root: uv run python examples/generate_example_files.py
"""

from pathlib import Path

from tools.kroki.kroki_templates import DiagramExamples

EXAMPLES_DIR = Path(__file__).resolve().parent

# Extension per diagram type (default .txt)
EXTENSION = {
    "plantuml": "puml",
    "class": "puml",
    "sequence": "puml",
    "activity": "puml",
    "usecase": "puml",
    "state": "puml",
    "component": "puml",
    "deployment": "puml",
    "object": "puml",
    "c4plantuml": "puml",
    "mermaid": "mmd",
    "d2": "d2",
    "graphviz": "dot",
    "erd": "erd",
    "blockdiag": "txt",
    "seqdiag": "txt",
    "actdiag": "txt",
    "nwdiag": "txt",
    "packetdiag": "txt",
    "rackdiag": "txt",
    "bpmn": "bpmn",
    "bytefield": "txt",
    "dbml": "dbml",
    "ditaa": "txt",
    "excalidraw": "json",
    "nomnoml": "txt",
    "pikchr": "txt",
    "structurizr": "dsl",
    "svgbob": "txt",
    "symbolator": "txt",
    "tikz": "tex",
    "vega": "json",
    "vegalite": "json",
    "wavedrom": "json",
    "wireviz": "yaml",
}


def main() -> None:
    # Use MCP config types so we get both aliases (class, sequence) and backends (plantuml, mermaid)
    from mcp_core.core.config import DIAGRAM_TYPES

    for diagram_type in DIAGRAM_TYPES:
        content = DiagramExamples.get_example(diagram_type)
        if not content or "No specific example" in content:
            continue
        ext = EXTENSION.get(diagram_type, "txt")
        path = EXAMPLES_DIR / f"example-{diagram_type}.{ext}"
        path.write_text(content, encoding="utf-8")
        print(f"Wrote {path.name}")


if __name__ == "__main__":
    main()
