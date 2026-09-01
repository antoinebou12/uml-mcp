"""
Shared diagram type metadata for MCP resources and tools (single source of truth).
"""

from typing import Any

from .config import MCP_SETTINGS


def get_diagram_types_dict() -> dict[str, Any]:
    """Return the same structure as the uml://types JSON object (before stringification)."""
    types: dict[str, Any] = {}
    for name, config in MCP_SETTINGS.diagram_types.items():
        types[name] = {
            "backend": config.backend,
            "description": config.description,
            "formats": config.formats,
        }
    return types
