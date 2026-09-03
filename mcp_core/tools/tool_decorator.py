"""Decorator system for MCP tools."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, cast

logger = logging.getLogger(__name__)

_registered_tools: dict[str, dict[str, Any]] = {}

# MIME types we attach to results as inline MCP ``image`` content blocks so that
# image-capable MCP clients (Cursor, Copilot, etc.) render the diagram directly in
# the chat instead of showing a URL. PNG/JPEG are universally rendered; SVG is
# included for clients that support ``image/svg+xml`` content blocks.
IMAGE_CONTENT_MIMES = frozenset({"image/png", "image/jpeg", "image/svg+xml"})

# Tool names that produce a rendered diagram result (used for the compact summary).
_RENDER_TOOL_NAMES = frozenset({"generate_uml", "generate_uml_image"})

F = TypeVar("F", bound=Callable[..., Any])


def _normalize_output_schema(output_schema: Any) -> dict[str, Any] | None:
    """Convert a Pydantic model class or mapping to FastMCP's JSON Schema shape."""
    if output_schema is None:
        return None
    if isinstance(output_schema, dict):
        return output_schema
    model_json_schema = getattr(output_schema, "model_json_schema", None)
    if callable(model_json_schema):
        schema = model_json_schema()
        if isinstance(schema, dict):
            return schema
    raise TypeError(
        "output_schema must be a JSON Schema dict or a Pydantic model class with model_json_schema()"
    )


def _summarize_tool_result(tool_name: str, result: dict[str, Any]) -> str:
    """Build a compact LLM-facing summary without repeating large payload fields."""
    if tool_name in _RENDER_TOOL_NAMES:
        summary = (
            f"Generated {result.get('diagram_type') or 'diagram'} successfully. "
            f"Renderer: {result.get('source') or 'unknown'}. "
            f"Format: {result.get('output_format') or 'unknown'}. "
            f"Render: {result.get('render_ms') if result.get('render_ms') is not None else 'n/a'} ms. "
            f"Cache hit: {bool(result.get('cache_hit'))}."
        )
        # Markdown image + links help Cursor / Copilot / Claude show and open the diagram
        # when ImageContent is missing (URL-only mode) or when the client prefers URLs.
        extras: list[str] = []
        url = result.get("url")
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            extras.append(f"![diagram]({url})")
            extras.append(f"URL: {url}")
        playground = result.get("playground")
        if isinstance(playground, str) and playground.startswith(("http://", "https://")):
            extras.append(f"Playground: {playground}")
        if extras:
            summary = summary + "\n\n" + "\n\n".join(extras)
        return summary
    if tool_name == "generate_uml_batch":
        rows = result.get("results") or []
        failures = sum(1 for row in rows if isinstance(row, dict) and row.get("error"))
        return f"Processed {len(rows)} diagrams; {failures} failed."
    if tool_name == "validate_uml":
        state = "valid" if result.get("valid") else "invalid"
        diagnostics = result.get("diagnostics") or []
        return f"Diagram is {state}; {len(diagnostics)} diagnostic(s)."
    if tool_name == "list_diagram_types":
        return f"Returned {len(result)} supported diagram type(s)."
    return "Tool completed successfully."


def _as_mcp_tool_result(tool_name: str, result: Any) -> Any:
    """Adapt legacy Python return values to first-class MCP structured results."""
    if not isinstance(result, dict):
        return result

    if result.get("error"):
        try:
            from fastmcp.exceptions import ToolError
        except (
            ImportError
        ) as exc:  # pragma: no cover - package is required in production
            raise RuntimeError(str(result["error"])) from exc
        raise ToolError(str(result["error"]))

    try:
        from fastmcp.tools import ToolResult
        from mcp.types import ImageContent, TextContent
    except ImportError:
        # The mock server used in unit tests does not need protocol result objects.
        return result

    content: list[Any] = [
        TextContent(type="text", text=_summarize_tool_result(tool_name, result))
    ]
    mime_type = str(result.get("mime_type") or "").lower()
    image_data = result.get("content_base64")
    # Prefer raster ImageContent for chat UIs (Cursor/Copilot/Claude); SVG blocks
    # are still attached when present for clients that support image/svg+xml.
    if image_data and mime_type in IMAGE_CONTENT_MIMES:
        content.append(
            ImageContent(type="image", data=str(image_data), mime_type=mime_type)
        )

    meta: dict[str, Any] = {}
    for key in ("render_ms", "cache_hit", "fallback_used", "source"):
        if key in result and result[key] is not None:
            meta[key] = result[key]

    return ToolResult(
        content=content,
        structured_content=result,
        meta=meta or None,
    )


def mcp_tool(
    name: str | None = None,
    description: str | None = None,
    category: str = "default",
    required_params: list[str] | None = None,
    example: str | None = None,
    annotations: dict[str, Any] | None = None,
    output_schema: Any | None = None,
) -> Callable[[F], F]:
    """Decorator for registering a function as an MCP tool."""

    def decorator(func: F) -> F:
        func_name = name or getattr(func, "__name__", "tool")
        func_doc = inspect.getdoc(func) or ""
        func_description = description or (func_doc.split("\n")[0] if func_doc else "")

        sig = inspect.signature(func)
        param_info: dict[str, dict[str, Any]] = {}
        for param_name, param in sig.parameters.items():
            param_type = (
                param.annotation
                if param.annotation is not inspect.Parameter.empty
                else None
            )
            param_default = (
                None if param.default is inspect.Parameter.empty else param.default
            )
            param_info[param_name] = {
                "type": (
                    param_type.__name__
                    if param_type is not None and hasattr(param_type, "__name__")
                    else str(param_type)
                ),
                "required": param.default is inspect.Parameter.empty,
                "default": param_default,
            }

        _registered_tools[func_name] = {
            "function": func,
            "name": func_name,
            "description": func_description,
            "category": category,
            "parameters": param_info,
            "required_params": required_params
            or [p for p, info in param_info.items() if info["required"]],
            "example": example,
            "annotations": annotations or {},
            "output_schema": output_schema,
            "return_type": (
                sig.return_annotation
                if sig.return_annotation is not inspect.Parameter.empty
                else None
            ),
        }
        return cast(F, func)

    return decorator


def register_tools_with_server(server: Any) -> list[str]:
    """Register all decorated tools with the MCP server."""
    logger.info("Registering %s tools with the MCP server", len(_registered_tools))

    registered_tools: list[str] = []
    server_any = cast(Any, server)

    for tool_name, tool_info in _registered_tools.items():
        func = tool_info["function"]
        annotations = tool_info.get("annotations") or {}
        output_schema = _normalize_output_schema(tool_info.get("output_schema"))

        @wraps(func)
        def protocol_func(
            *args: Any,
            __func: Callable[..., Any] = func,
            __name: str = tool_name,
            **kwargs: Any,
        ) -> Any:
            return _as_mcp_tool_result(__name, __func(*args, **kwargs))

        tool_kwargs: dict[str, Any] = {
            "name": tool_name,
            "description": tool_info["description"],
        }
        if annotations:
            tool_kwargs["annotations"] = annotations
        if output_schema is not None:
            tool_kwargs["output_schema"] = output_schema

        try:
            dec = server_any.tool(**tool_kwargs)
            dec(protocol_func)
        except TypeError:
            # Compatibility path for older/mock server APIs. The project is pinned to
            # FastMCP 4 in production, but tests intentionally exercise a minimal mock.
            try:
                dec = server_any.tool(
                    name=tool_name,
                    description=tool_info["description"],
                )
                dec(protocol_func)
            except TypeError:
                try:
                    dec = server_any.tool(tool_info["description"])
                    dec(protocol_func)
                except TypeError:
                    server_any.tool(protocol_func)

                if tool_name != protocol_func.__name__:
                    if hasattr(server, "_tools"):
                        tools_map: Any = server._tools
                        tools_map[tool_name] = tools_map.pop(
                            protocol_func.__name__, protocol_func
                        )
                    else:
                        logger.warning(
                            "Could not rename tool '%s' to '%s'; server API does not support it",
                            protocol_func.__name__,
                            tool_name,
                        )

        registered_tools.append(tool_name)
        logger.debug("Registered tool: %s", tool_name)

    return registered_tools


def get_tool_registry() -> dict[str, dict[str, Any]]:
    """Get information about all registered tools."""
    return _registered_tools


def get_tool_categories() -> dict[str, list[str]]:
    """Get tools organized by category."""
    categories: dict[str, list[str]] = {}
    for tool_name, tool_info in _registered_tools.items():
        category = tool_info["category"]
        categories.setdefault(category, []).append(tool_name)
    return categories


def clear_tool_registry() -> None:
    """Clear the tool registry (mainly for testing)."""
    _registered_tools.clear()


__all__ = [
    "clear_tool_registry",
    "get_tool_categories",
    "get_tool_registry",
    "mcp_tool",
    "register_tools_with_server",
]
