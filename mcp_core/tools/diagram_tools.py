"""MCP tools for diagram generation using the decorator pattern."""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from ..core.config import MCP_SETTINGS
from ..core.diagram_catalog import get_diagram_types_dict
from ..core.diagram_service import DiagramRequest, generate_from_request
from ..core.diagram_validation import validate_uml_inputs
from .schemas import (
    BatchDiagramResult,
    DiagramResult,
    DiagramTypesOutput,
    GenerateUMLInput,
    ValidationResult,
)
from .tool_decorator import get_tool_registry, mcp_tool, register_tools_with_server

logger = logging.getLogger(__name__)

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


def _bounded_limit(limit: Optional[int]) -> Optional[int]:
    if limit is None:
        return None
    return max(1, min(int(limit), 100))


@mcp_tool(
    description=(
        "Find supported diagram types and their renderer/formats. Input optional query, "
        "backend, output_format, and limit filters; returns matching type metadata. Use "
        "this when you are unsure which diagram type or format to choose."
    ),
    category="uml",
    example="list_diagram_types(query='sequence', output_format='svg')",
    annotations={**ANNOTATIONS_LIST, "title": "List Diagram Types"},
    output_schema=DiagramTypesOutput,
)
def list_diagram_types(
    query: Optional[str] = None,
    backend: Optional[str] = None,
    output_format: Optional[str] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Return optionally filtered diagram type metadata."""
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


def _batch_concurrency(item_count: int) -> int:
    try:
        configured = int(os.environ.get("MCP_BATCH_CONCURRENCY", "4"))
    except ValueError:
        configured = 4
    configured = max(1, min(configured, 16))
    return max(1, min(configured, item_count))


def _render_batch_item(
    index: int,
    raw: Any,
    output_dir: Optional[str],
) -> Dict[str, Any]:
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
    except Exception as exc:  # noqa: BLE001 - isolate each independent batch item
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
        "Render several independent diagrams in one call using bounded concurrency. Input "
        "items use the same diagram_type/code/format/theme/scale fields as generate_uml; "
        "returns ordered per-index results and keeps partial failures isolated. Use this for "
        "multiple diagrams, not repeated repair attempts for one invalid diagram."
    ),
    category="uml",
    example=(
        "generate_uml_batch([{'diagram_type': 'mermaid', 'code': 'graph TD; A-->B;'}])"
    ),
    annotations={**ANNOTATIONS_DIAGRAM, "title": "Generate Diagram Batch"},
    output_schema=BatchDiagramResult,
)
def generate_uml_batch(
    items: List[Dict[str, Any]],
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Render multiple diagrams with bounded concurrency and stable ordering."""
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

    workers = _batch_concurrency(len(items))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="uml-batch") as pool:
        futures = [
            pool.submit(_render_batch_item, index, raw, output_dir)
            for index, raw in enumerate(items)
        ]
        # Futures are consumed in submission order so output ordering is deterministic,
        # even though the independent renders execute concurrently.
        results = [future.result() for future in futures]
    return {"results": results}


@mcp_tool(
    description=(
        "Render one UML or diagram from source code. Input diagram_type, code, optional "
        "output_format/theme/scale/output_dir; returns renderer metadata plus URL and "
        "inline image data when appropriate. Use when you already have valid or nearly "
        "valid diagram source; call validate_uml first for uncertain complex syntax."
    ),
    category="uml",
    example="generate_uml('mermaid', 'graph TD; A-->B;')",
    annotations={**ANNOTATIONS_DIAGRAM, "title": "Generate Diagram"},
    output_schema=DiagramResult,
)
def generate_uml(
    diagram_type: str,
    code: str,
    output_dir: Optional[str] = None,
    output_format: str = "svg",
    theme: Optional[str] = None,
    scale: float = 1.0,
) -> Dict[str, Any]:
    """Generate a diagram using the specified diagram type."""
    logger.info(
        "Called generate_uml tool: type=%s, code length=%s",
        diagram_type,
        len(code),
    )
    return generate_from_request(
        DiagramRequest(
            diagram_type=diagram_type,
            code=code,
            output_dir=output_dir,
            output_format=output_format,
            theme=theme,
            scale=scale,
        )
    )


@mcp_tool(
    description=(
        "Validate diagram type, format, size, and syntax locally without rendering. Input "
        "diagram_type/code/output_format and optional strict=true for additional Mermaid/D2 "
        "checks; returns structured diagnostics, suggestions, and deterministic normalization "
        "details. Use before rendering complex or uncertain source."
    ),
    category="uml",
    example="validate_uml('class', '@startuml\\nclass A\\n@enduml', 'svg')",
    annotations={**ANNOTATIONS_VALIDATE, "title": "Validate Diagram"},
    output_schema=ValidationResult,
)
def validate_uml(
    diagram_type: str,
    code: str,
    output_format: str = "svg",
    strict: bool = False,
) -> Dict[str, Any]:
    """Check inputs and light structure without rendering."""
    logger.info(
        "Called validate_uml tool: type=%s, code length=%s, strict=%s",
        diagram_type,
        len(code or ""),
        strict,
    )
    return validate_uml_inputs(diagram_type, code, output_format, strict=strict)


def register_diagram_tools(server: Any) -> List[str]:
    """Register all diagram generation tools with the MCP server."""
    logger.info("Registering diagram tools")
    registered_tools = register_tools_with_server(server)
    MCP_SETTINGS.tools = registered_tools
    logger.info("Registered %s diagram tools successfully", len(registered_tools))
    logger.debug("Registered tools: %s", registered_tools)
    return registered_tools


def get_tool_info() -> Dict[str, Dict[str, Any]]:
    """Get information about all registered tools."""
    return get_tool_registry()
