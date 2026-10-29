"""MCP tools for diagram generation using the decorator pattern."""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, cast

from pydantic import ValidationError

from ..apps.diagram_viewer import (
    diagram_viewer_app_config,
    diagram_viewer_app_only_config,
)
from ..core.config import MCP_SETTINGS
from ..core.diagram_catalog import get_diagram_types_dict
from ..core.diagram_service import DiagramRequest, generate_from_request
from ..core.diagram_validation import validate_uml_inputs
from . import mrtr, notifications
from .schemas import (
    BatchDiagramResult,
    DiagramResult,
    DiagramTypesOutput,
    GenerateUMLInput,
    ValidationResult,
)
from .tool_decorator import get_tool_registry, mcp_tool, register_tools_with_server

logger = logging.getLogger(__name__)

# Shared MCP Apps link for both render tools (same viewer resource).
_DIAGRAM_VIEWER_APP = diagram_viewer_app_config()
# Viewer-only helper: host must hide from the model (visibility=["app"]).
_DIAGRAM_VIEWER_APP_ONLY = diagram_viewer_app_only_config()

ANNOTATIONS_DIAGRAM = {
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}

ANNOTATIONS_VALIDATE = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}

ANNOTATIONS_LIST = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}


def _bounded_limit(limit: int | None) -> int | None:
    if limit is None:
        return None
    return max(1, min(int(limit), 100))


@mcp_tool(
    description=(
        "Find diagram types by text, renderer, or output format. Returns a map keyed "
        "by diagram_type, with each type’s backend, description, and supported formats."
    ),
    category="uml",
    example="list_diagram_types(query='sequence', output_format='svg')",
    annotations={**ANNOTATIONS_LIST, "title": "List Diagram Types"},
    output_schema=DiagramTypesOutput,
    lint_ignore={
        "tool-no-required": "Every parameter is an optional filter; calling it with "
        "no arguments lists the whole catalog, which is the common first call.",
    },
)
def list_diagram_types(
    query: str | None = None,
    backend: str | None = None,
    output_format: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Return optionally filtered diagram type metadata.

    Args:
        query: Optional text matched against type name, backend, and description.
        backend: Optional renderer/backend name to match exactly.
        output_format: Optional required output format such as svg or png.
        limit: Maximum number of matching types to return; omit for all matches.
    """
    logger.info(
        "Called list_diagram_types: query=%s backend=%s format=%s limit=%s",
        query,
        backend,
        output_format,
        limit,
    )
    types_map = get_diagram_types_dict()
    query_value = (query or "").strip().lower()
    backend_value = (backend or "").strip().lower()
    format_value = (output_format or "").strip().lower()

    filtered: dict[str, Any] = {}
    for name, info in types_map.items():
        if query_value:
            haystack = " ".join(
                (
                    name,
                    str(info.get("backend", "")),
                    str(info.get("description", "")),
                )
            ).lower()
            if query_value not in haystack:
                continue
        if backend_value and str(info.get("backend", "")).lower() != backend_value:
            continue
        if format_value and format_value not in {
            str(fmt).lower() for fmt in info.get("formats", [])
        }:
            continue
        filtered[name] = info
        bounded = _bounded_limit(limit)
        if bounded is not None and len(filtered) >= bounded:
            break
    return filtered


def _format_validation_error(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors():
        loc = err.get("loc", ())
        name = ".".join(str(x) for x in loc) if loc else "input"
        parts.append(f"{name}: {err.get('msg', '')}")
    return "; ".join(parts)


def _batch_concurrency(item_count: int, items: list[Any] | None = None) -> int:
    try:
        configured = int(os.environ.get("MCP_BATCH_CONCURRENCY", "4"))
    except ValueError:
        configured = 4
    configured = max(1, min(configured, 16))
    # Mermaid-heavy batches often fall back to mermaid.ink (~30s each) on hosted
    # deployments; keep concurrency low to avoid stampedes/timeouts.
    if items:
        mermaid_count = 0
        for raw in items:
            if isinstance(raw, dict):
                dt = str(raw.get("diagram_type", "")).strip().lower()
                if dt == "mermaid":
                    mermaid_count += 1
        if mermaid_count > len(items) / 2:
            configured = min(configured, 2)
    return max(1, min(configured, item_count))


def _render_batch_item(
    index: int,
    raw: Any,
    output_dir: str | None,
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {
            "index": index,
            "success": False,
            "error": f"items[{index}] must be an object with diagram_type and code",
        }
    try:
        validated = GenerateUMLInput.model_validate({**raw, "output_dir": output_dir})
    except ValidationError as exc:
        return {
            "index": index,
            "success": False,
            "error": _format_validation_error(exc),
        }

    try:
        out = generate_from_request(
            DiagramRequest(
                diagram_type=validated.diagram_type,
                code=validated.code,
                output_dir=validated.output_dir,
                output_format=validated.output_format,
                theme=validated.theme,
                scale=validated.scale,
            )
        )
        return {"index": index, **out}
    except Exception as exc:
        logger.exception("Unexpected batch item failure at index=%s", index)
        return {
            "index": index,
            "success": False,
            "diagram_type": validated.diagram_type,
            "output_format": validated.output_format,
            "error": f"Unexpected batch render failure: {type(exc).__name__}: {exc!s}",
        }


@mcp_tool(
    description=(
        "Render several diagrams with bounded concurrency. Each item uses the same "
        "fields as generate_uml. Partial failures stay isolated per index."
    ),
    category="uml",
    example=(
        "generate_uml_batch([{'diagram_type': 'mermaid', 'code': 'graph TD; A-->B;'}])"
    ),
    annotations={**ANNOTATIONS_DIAGRAM, "title": "Generate Diagram Batch"},
    output_schema=BatchDiagramResult,
)
def generate_uml_batch(
    items: list[dict[str, Any]],
    output_dir: str | None = None,
) -> dict[str, Any] | Any:
    """Render multiple diagrams with bounded concurrency and stable ordering.

    Args:
        items: Source diagrams and render options, in the order results should follow.
        output_dir: Shared local directory for rendered files. Omit for URLs and inline data without file writes.
    """
    logger.info(
        "Called generate_uml_batch: count=%s, output_dir=%s",
        len(items) if items else 0,
        output_dir,
    )
    if not items:
        return {"error": "items must not be empty", "results": []}

    max_n = MCP_SETTINGS.batch_max_items
    if len(items) > max_n:
        return {
            "error": f"At most {max_n} items allowed (MCP_BATCH_MAX_ITEMS).",
            "results": [],
        }

    confirm = mrtr.maybe_confirm_batch(items)
    if confirm is not None:
        return confirm

    total = len(items)
    workers = _batch_concurrency(total, items)
    notifications.report_progress(
        0, total, f"Rendering {total} diagram(s), up to {workers} at a time"
    )
    # Rows are stored by index so output ordering stays deterministic, even though the
    # independent renders finish (and are reported as progress) in completion order.
    results: list[dict[str, Any]] = [{} for _ in items]
    with ThreadPoolExecutor(
        max_workers=workers, thread_name_prefix="uml-batch"
    ) as pool:
        futures = {
            pool.submit(_render_batch_item, index, raw, output_dir): index
            for index, raw in enumerate(items)
        }
        for done, future in enumerate(as_completed(futures), start=1):
            index = futures[future]
            row = future.result()
            results[index] = row
            _notify_batch_item(index, total, row)
            notifications.report_progress(
                done,
                total,
                f"{done}/{total} rendered",
                data={
                    "index": index,
                    "done": done,
                    "total": total,
                    "diagram_type": row.get("diagram_type"),
                    "ok": not bool(row.get("error") or row.get("success") is False),
                    "url": row.get("url"),
                },
            )
    return {"results": results}


def _notify_batch_item(index: int, total: int, row: dict[str, Any]) -> None:
    """Log one finished batch item; failures are warnings, successes are info."""
    label = f"[{index + 1}/{total}]"
    if row.get("error") or row.get("success") is False:
        notifications.log("warning", f"{label} failed: {row.get('error')}")
        return
    notifications.log(
        "info",
        f"{label} {row.get('diagram_type')} rendered via {row.get('source')} "
        f"in {row.get('render_ms')} ms",
    )


@mcp_tool(
    description=(
        "Render diagram source into an image. Returns url (render link), playground "
        "(source editor), display_markdown (chat embed), and content_base64/mime_type "
        "when image bytes are fetched. local_path identifies a saved file. "
        "Use output_format=png for inline bytes, or call generate_uml_image. "
        "MCP Apps hosts may open the linked diagram viewer."
    ),
    category="uml",
    example="generate_uml('mermaid', 'graph TD; A-->B;')",
    annotations={**ANNOTATIONS_DIAGRAM, "title": "Generate Diagram"},
    output_schema=DiagramResult,
    app=_DIAGRAM_VIEWER_APP,
)
def generate_uml(
    diagram_type: str,
    code: str,
    output_dir: str | None = None,
    output_format: str = "svg",
    theme: str | None = None,
    scale: float = 1.0,
) -> dict[str, Any] | Any:
    """Generate a diagram using the specified diagram type.

    Args:
        diagram_type: Catalog key selecting the source language and renderer; discover keys with list_diagram_types.
        code: Diagram source code in the syntax required by diagram_type.
        output_dir: Optional local directory for the rendered file; omit on hosted deployments.
        output_format: Image or document encoding to produce; consult the type’s formats from list_diagram_types.
        theme: Optional theme — PlantUML name (e.g. cerulean), Mermaid default/dark/forest/neutral/base, or D2 default/dark (theme-id).
            Background aliases (light/dark/bw) elicit a concrete theme when the client supports MRTR.
        scale: SVG scale factor; ignored for non-SVG output.
    """
    logger.info(
        "Called generate_uml tool: type=%s, code length=%s",
        diagram_type,
        len(code),
    )
    resolved = mrtr.resolve_diagram_type(diagram_type)
    if mrtr.is_input_required(resolved) or (
        isinstance(resolved, dict) and resolved.get("error")
    ):
        return resolved
    diagram_type = str(resolved)

    theme_resolved = mrtr.resolve_theme(diagram_type, theme)
    if mrtr.is_input_required(theme_resolved) or (
        isinstance(theme_resolved, dict) and theme_resolved.get("error")
    ):
        return theme_resolved
    theme = cast(str | None, theme_resolved)

    fmt = (output_format or "svg").strip().lower()
    # Raster formats: fetch bytes even under MCP_URL_ONLY so chat clients get ImageContent.
    force_fetch = fmt in {"png", "jpeg", "jpg"}
    return generate_from_request(
        DiagramRequest(
            diagram_type=diagram_type,
            code=code,
            output_dir=output_dir,
            output_format=output_format,
            theme=theme,
            scale=scale,
            force_fetch=force_fetch,
        )
    )


@mcp_tool(
    description=(
        "Render a diagram as MCP ImageContent for chat with a bounded inline preview. "
        "Returns content_base64, mime_type, render and playground links. "
        "Fetches bytes even under URL-only. Large images use a PNG thumbnail in MCP Apps."
    ),
    category="uml",
    example="generate_uml_image('mermaid', 'graph TD; A-->B;', 'png')",
    annotations={**ANNOTATIONS_DIAGRAM, "title": "Generate Diagram Image"},
    output_schema=DiagramResult,
    app=_DIAGRAM_VIEWER_APP,
)
def generate_uml_image(
    diagram_type: str,
    code: str,
    output_format: str = "png",
    theme: str | None = None,
    scale: float = 1.0,
) -> dict[str, Any] | Any:
    """Generate a diagram and return it as an inline MCP image content block.

    Args:
        diagram_type: Catalog key selecting the source language and renderer; discover keys with list_diagram_types.
        code: Diagram source code in the syntax required by diagram_type.
        output_format: Output format for the inline image; png (default), svg, or jpeg.
        theme: Optional theme — PlantUML name (e.g. cerulean), Mermaid default/dark/forest/neutral/base, or D2 default/dark (theme-id).
            Background aliases (light/dark/bw) elicit a concrete theme when the client supports MRTR.
        scale: SVG scale factor; ignored unless output_format is svg.
    """
    logger.info(
        "Called generate_uml_image tool: type=%s, format=%s, code length=%s",
        diagram_type,
        output_format,
        len(code),
    )
    resolved = mrtr.resolve_diagram_type(diagram_type)
    if mrtr.is_input_required(resolved) or (
        isinstance(resolved, dict) and resolved.get("error")
    ):
        return resolved
    diagram_type = str(resolved)

    theme_resolved = mrtr.resolve_theme(diagram_type, theme)
    if mrtr.is_input_required(theme_resolved) or (
        isinstance(theme_resolved, dict) and theme_resolved.get("error")
    ):
        return theme_resolved
    theme = cast(str | None, theme_resolved)

    return generate_from_request(
        DiagramRequest(
            diagram_type=diagram_type,
            code=code,
            output_dir=None,
            output_format=output_format,
            theme=theme,
            scale=scale,
            force_fetch=True,
        )
    )


@mcp_tool(
    description=(
        "Render the viewer’s diagram source again with the selected theme and format. "
        "Returns content_base64, mime_type, url, playground, and display_markdown. "
        "Hidden from the model; callable from ui://uml-mcp/diagram-viewer via tools/call."
    ),
    category="uml",
    example="rerender_diagram('mermaid', 'graph TD; A-->B;', 'png', 'forest')",
    annotations={
        **ANNOTATIONS_DIAGRAM,
        "readOnlyHint": True,
        "title": "Re-render Diagram",
    },
    output_schema=DiagramResult,
    app=_DIAGRAM_VIEWER_APP_ONLY,
    lint_ignore={
        "tool-name-convention": (
            "App-only Apps helper (visibility=['app']); not a model workflow verb."
        ),
    },
)
def rerender_diagram(
    diagram_type: str,
    code: str,
    output_format: str = "png",
    theme: str | None = None,
    scale: float = 1.0,
) -> dict[str, Any] | Any:
    """Re-render for the sandboxed Apps viewer (same pipeline as generate_uml_image).

    Args:
        diagram_type: Catalog key selecting the source language and renderer for this diagram.
        code: Diagram source text in the language selected by diagram_type, taken from the viewer’s previous render.
        output_format: png (default), svg, or jpeg for the viewer.
        theme: Visual style for the selected renderer; omit to use its default styling.
        scale: SVG scale factor; ignored unless output_format is svg.
    """
    logger.info(
        "Called rerender_diagram (app-only): type=%s, format=%s, theme=%s",
        diagram_type,
        output_format,
        theme,
    )
    resolved = mrtr.resolve_diagram_type(diagram_type)
    if mrtr.is_input_required(resolved) or (
        isinstance(resolved, dict) and resolved.get("error")
    ):
        return resolved
    diagram_type = str(resolved)

    theme_resolved = mrtr.resolve_theme(diagram_type, theme)
    if mrtr.is_input_required(theme_resolved) or (
        isinstance(theme_resolved, dict) and theme_resolved.get("error")
    ):
        return theme_resolved
    theme = cast(str | None, theme_resolved)

    out = generate_from_request(
        DiagramRequest(
            diagram_type=diagram_type,
            code=code,
            output_dir=None,
            output_format=output_format,
            theme=theme,
            scale=scale,
            force_fetch=True,
        )
    )
    if isinstance(out, dict) and theme is not None:
        out = dict(out)
        out["theme"] = theme
    return out


@mcp_tool(
    description=(
        "Validate diagram type, format, and syntax locally (no render). "
        "Returns valid, errors, warnings, suggestions, and diagnostics; prepared_code "
        "is normalized source and changes explains normalization. "
        "Set strict=true for extra Mermaid/D2 checks."
    ),
    category="uml",
    example="validate_uml('class', '@startuml\\nclass A\\n@enduml', 'svg')",
    annotations={**ANNOTATIONS_VALIDATE, "title": "Check Diagram Source"},
    output_schema=ValidationResult,
)
def validate_uml(
    diagram_type: str,
    code: str,
    output_format: str = "svg",
    strict: bool = False,
) -> dict[str, Any]:
    """Check inputs and light structure without rendering.

    Args:
        diagram_type: Catalog key selecting the source language and renderer to check.
        code: Diagram source code to validate locally without rendering.
        output_format: Output format whose compatibility should be checked.
        strict: Enable additional syntax checks when supported.
    """
    logger.info(
        "Called validate_uml tool: type=%s, code length=%s, strict=%s",
        diagram_type,
        len(code or ""),
        strict,
    )
    return validate_uml_inputs(diagram_type, code, output_format, strict=strict)


def register_diagram_tools(server: Any) -> list[str]:
    """Register all diagram generation tools with the MCP server."""
    logger.info("Registering diagram tools")
    registered_tools = register_tools_with_server(server)
    MCP_SETTINGS.tools = registered_tools
    logger.info("Registered %s diagram tools successfully", len(registered_tools))
    logger.debug("Registered tools: %s", registered_tools)
    return registered_tools


def get_tool_info() -> dict[str, dict[str, Any]]:
    """Get information about all registered tools."""
    return get_tool_registry()
