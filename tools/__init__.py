"""
Diagram generation tools: Kroki client plus Mermaid, PlantUML, and D2 utilities.

All diagram rendering lives under tools.kroki:
  - tools.kroki.kroki — Kroki service client
  - tools.kroki.mermaid — Mermaid URL/state utilities
  - tools.kroki.plantuml — PlantUML client
  - tools.kroki.d2 — D2 encoding/URL utilities
"""

from .kroki import (
    LANGUAGE_OUTPUT_SUPPORT,
    generate_diagram,
    generate_kroki_url,
    DiagramTemplates,
)

__all__ = [
    "LANGUAGE_OUTPUT_SUPPORT",
    "generate_diagram",
    "generate_kroki_url",
    "DiagramTemplates",
]
