"""
Shared diagram type metadata for MCP resources and tools (single source of truth).
"""

from typing import Any

from .config import MCP_SETTINGS


def get_diagram_types_dict() -> dict[str, Any]:
    """Return the same structure as the uml://types JSON object (before stringification).

    For plugin-provided types, optional capability manifest fields
    (``interaction_features``, ``security_profile``, ``version``, ``source_schema``,
    ``renderer_capabilities_version``) are included when non-default so the viewer
    and model can discover what interactions are available for each type.
    """
    from ..plugins.loader import RENDERERS

    types: dict[str, Any] = {}
    for name, config in MCP_SETTINGS.diagram_types.items():
        entry: dict[str, Any] = {
            "backend": config.backend,
            "description": config.description,
            "formats": config.formats,
        }
        # Enrich with plugin capability manifest when available.
        renderer = RENDERERS.get(name)
        if renderer is not None:
            spec = renderer.diagram_types.get(name)
            if spec is not None:
                if spec.interaction_features:
                    entry["interaction_features"] = list(spec.interaction_features)
                if spec.security_profile != "static":
                    entry["security_profile"] = spec.security_profile
                if spec.version is not None:
                    entry["version"] = spec.version
                if spec.source_schema is not None:
                    entry["source_schema"] = spec.source_schema
                if spec.renderer_capabilities_version > 1:
                    entry["renderer_capabilities_version"] = (
                        spec.renderer_capabilities_version
                    )
        types[name] = entry
    return types
