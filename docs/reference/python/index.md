---
title: Python API
description: Auto-generated reference for the mcp_core and tools.kroki Python packages.
---

# Python API

This section is generated from docstrings via [mkdocstrings](https://mkdocstrings.github.io/). It mirrors what is available when you import UML-MCP as a Python package, which helps when embedding the server, writing custom tools, or extending the rendering pipeline.

| Module group | Description |
| --- | --- |
| [`mcp_core.tools`](tools.md) | MCP tool implementations (`generate_uml`, `validate_uml`, `list_diagram_types`, `generate_uml_batch`) and Pydantic input schemas. |
| [`mcp_core.core`](core.md) | Service layer: rendering pipeline, validation, configuration, the `DiagramRequest` dataclass. |
| [`tools.kroki`](kroki.md) | Backend clients: Kroki, PlantUML, Mermaid, D2, TikZ. |

!!! note "Import paths"

    All classes and functions are documented with their full import path so you can copy and paste:

    ```python
    from mcp_core.tools.diagram_tools import generate_uml
    from mcp_core.core.diagram_service import DiagramRequest, generate_from_request
    from tools.kroki.kroki import LANGUAGE_OUTPUT_SUPPORT
    ```

!!! tip "Source links"

    Every page is generated from the live docstrings. To improve the rendered output, edit the docstrings in the source files (linked from each section header) and rebuild the docs.
