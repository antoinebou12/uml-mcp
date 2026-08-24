"""FastMCP wire-schema compatibility helpers.

Some MCP inspectors treat a missing JSON Schema ``required`` keyword as
ambiguous even though JSON Schema defines it equivalently to an empty list.
Keep runtime signatures unchanged and normalize only the schemas advertised by
``tools/list``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

try:
    from fastmcp.server.transforms import Transform
except ImportError:  # pragma: no cover - production pins FastMCP 4
    Transform = object  # type: ignore[assignment,misc]


class ExplicitRequiredSchemaTransform(Transform):  # type: ignore[misc]
    """Ensure every advertised tool input schema has a ``required`` array."""

    async def list_tools(self, tools: Sequence[Any]) -> Sequence[Any]:
        normalized: list[Any] = []
        for tool in tools:
            parameters = getattr(tool, "parameters", None)
            if not isinstance(parameters, dict) or "required" in parameters:
                normalized.append(tool)
                continue

            updated_parameters = {**parameters, "required": []}
            model_copy = getattr(tool, "model_copy", None)
            if callable(model_copy):
                tool = model_copy(update={"parameters": updated_parameters})
            else:  # pragma: no cover - compatibility fallback for non-Pydantic mocks
                try:
                    tool.parameters = updated_parameters
                except (AttributeError, TypeError):
                    pass
            normalized.append(tool)
        return normalized


def install_schema_compat(server: Any) -> None:
    """Install wire-schema normalization once when supported by the server."""
    add_transform = getattr(server, "add_transform", None)
    if not callable(add_transform):
        return

    marker = "_uml_mcp_schema_compat_installed"
    if getattr(server, marker, False):
        return

    add_transform(ExplicitRequiredSchemaTransform())
    try:
        setattr(server, marker, True)
    except (AttributeError, TypeError):
        # A server implementation may disallow arbitrary attributes. Duplicate
        # installation is still harmless because the transform is idempotent.
        pass


__all__ = ["ExplicitRequiredSchemaTransform", "install_schema_compat"]
