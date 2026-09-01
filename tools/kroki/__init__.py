"""
Kroki integration module for UML-MCP.

This package consolidates all diagram rendering clients and utilities:
  - Kroki service client (kroki.py)
  - Diagram templates and examples (kroki_templates.py)
  - Mermaid URL/state utilities (mermaid.py)
  - PlantUML client (plantuml.py)
  - PlantUML themes (plantuml_themes.py)
  - D2 encoding/URL utilities (d2.py)
"""

# D2 utilities
from .d2 import Layout as D2Layout
from .d2 import Theme as D2Theme
from .d2 import decode as d2_decode
from .d2 import encode as d2_encode
from .d2 import generate_d2graphviz_url
from .kroki import LANGUAGE_OUTPUT_SUPPORT, generate_diagram, generate_kroki_url
from .kroki_templates import DiagramTemplates

# Mermaid utilities
from .mermaid import (
    MERMAID_INK_BASE,
    MERMAID_LIVE_EDIT_BASE,
    MermaidUrls,
    deserialize_state,
    generate_diagram_state,
    generate_mermaid_live_editor_url,
    generate_mermaid_urls,
    get_edit_url,
    get_image_url,
    serialize_state,
)

# PlantUML client and themes
from .plantuml import (
    PlantUML,
    PlantUMLConnectionError,
    PlantUMLError,
    PlantUMLHTTPError,
)
from .plantuml_themes import EXTERNAL_THEMES, THEMES, Theme

__all__ = [
    "EXTERNAL_THEMES",
    "LANGUAGE_OUTPUT_SUPPORT",
    "MERMAID_INK_BASE",
    "MERMAID_LIVE_EDIT_BASE",
    "THEMES",
    "D2Layout",
    "D2Theme",
    "DiagramTemplates",
    "MermaidUrls",
    "PlantUML",
    "PlantUMLConnectionError",
    "PlantUMLError",
    "PlantUMLHTTPError",
    "Theme",
    "d2_decode",
    "d2_encode",
    "deserialize_state",
    "generate_d2graphviz_url",
    "generate_diagram",
    "generate_diagram_state",
    "generate_kroki_url",
    "generate_mermaid_live_editor_url",
    "generate_mermaid_urls",
    "get_edit_url",
    "get_image_url",
    "serialize_state",
]
