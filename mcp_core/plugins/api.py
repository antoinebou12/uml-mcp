"""Public API for UML-MCP plugins (stable surface for plugin authors).

A plugin is a Python package that declares entry points:

.. code-block:: toml

    [project.entry-points."uml_mcp.tools"]
    hello = "uml_mcp_plugin_hello:register"          # callable(ctx: PluginContext)

    [project.entry-points."uml_mcp.renderers"]
    ascii = "uml_mcp_plugin_hello:AsciiRenderer"     # Renderer class or instance

and is loaded only when listed in ``plugins.enabled`` of ``uml-mcp.yaml``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

TOOLS_GROUP = "uml_mcp.tools"
RENDERERS_GROUP = "uml_mcp.renderers"


@dataclass(frozen=True)
class DiagramTypeSpec:
    """A diagram type contributed by a renderer."""

    description: str
    formats: tuple[str, ...] = ("svg",)


@dataclass(frozen=True)
class RenderOutput:
    """What a renderer returns: the bytes and their MIME type (URL optional)."""

    content: bytes
    mime_type: str
    url: str | None = None


@runtime_checkable
class Renderer(Protocol):
    """Render diagram source to bytes for the diagram types it declares."""

    name: str
    diagram_types: dict[str, DiagramTypeSpec]

    def render(
        self, diagram_type: str, code: str, output_format: str
    ) -> RenderOutput: ...


@dataclass
class PluginContext:
    """Handed to ``uml_mcp.tools`` entry points: register tools, read settings."""

    name: str
    settings: dict[str, Any] = field(default_factory=dict)
    registered: list[str] = field(default_factory=list)

    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger(f"uml_mcp.plugins.{self.name}")

    def tool(
        self,
        name: str,
        description: str,
        *,
        annotations: dict[str, Any] | None = None,
        output_schema: Any | None = None,
        example: str | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register an MCP tool named ``<plugin>_<name>``.

        Tools get everything built-in tools get: audit, metrics, OTel, rate
        limits, ``tools.enabled/disabled`` gating, lint and auth (read vs
        write from ``annotations["readOnlyHint"]``; missing means write).
        """
        from ..tools.tool_decorator import get_tool_registry, mcp_tool

        full = f"{self.name.replace('-', '_')}_{name}"
        if full in get_tool_registry():
            raise ValueError(f"tool name collision: {full}")

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            wrapped = mcp_tool(
                name=full,
                description=description,
                category=f"plugin:{self.name}",
                annotations={
                    "title": full.replace("_", " ").title(),
                    **(annotations or {}),
                },
                output_schema=output_schema,
                example=example,
            )(func)
            self.registered.append(full)
            return wrapped

        return decorator


__all__ = [
    "RENDERERS_GROUP",
    "TOOLS_GROUP",
    "DiagramTypeSpec",
    "PluginContext",
    "RenderOutput",
    "Renderer",
]
