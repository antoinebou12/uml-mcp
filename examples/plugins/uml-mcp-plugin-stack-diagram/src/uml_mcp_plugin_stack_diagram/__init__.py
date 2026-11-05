"""UML-MCP plugin: stack diagrams with auto-layout, nested groups and two themes.

One diagram type, ``stack_diagram``: icon tiles on engineered paper, vendor and region
groups that nest, labelled orthogonal edges, flowing left to right (``LR``), right to left
(``RL``), top down (``TB``) or bottom up (``BT``), in ``dark`` or ``light``.

The layout engine, spec parser and HTML page here are reused by the ``archify`` plugin.
"""

from __future__ import annotations

from typing import ClassVar

from .renderer import AutoLayoutRenderer, TypeDef
from .samples import CLOUD_EXAMPLE, EXAMPLE, TEMPLATE
from .skins import StackSkin

__all__ = ["AutoLayoutRenderer", "StackDiagramRenderer", "StackSkin", "TypeDef"]


class StackDiagramRenderer(AutoLayoutRenderer):
    name = "stack-diagram"
    skin = StackSkin()
    schema = "urn:uml-mcp:stack-diagram:1"
    types: ClassVar[dict[str, TypeDef]] = {
        "stack_diagram": TypeDef(
            "Stack or cloud architecture diagram: icon tiles, nested vendor/region groups and "
            "labelled orthogonal edges, auto-laid out left-right or top-down in dark or light. "
            "JSON nodes, groups and edges; html or svg",
            EXAMPLE,
            TEMPLATE,
        ),
    }

    #: A second, nested cloud example, handy for tests and docs.
    cloud_example = CLOUD_EXAMPLE
