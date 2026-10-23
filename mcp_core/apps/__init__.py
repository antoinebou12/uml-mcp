"""MCP Apps extension: sandboxed UI resources for diagram hosts."""

from .diagram_viewer import (
    DIAGRAM_VIEWER_URI,
    diagram_viewer_app_config,
    register_diagram_viewer,
)

__all__ = [
    "DIAGRAM_VIEWER_URI",
    "diagram_viewer_app_config",
    "register_diagram_viewer",
]
