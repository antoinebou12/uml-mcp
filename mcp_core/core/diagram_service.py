"""Diagram generation entry for MCP tools: validate once, then render."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from .config import MCP_SETTINGS
from .render_cache import build_render_cache_key, get_render_cache
from .utils import generate_diagram

logger = logging.getLogger(__name__)


@dataclass
class DiagramRequest:
    """Tool-level inputs for diagram generation."""

    diagram_type: str
    code: str
    output_dir: str | None = None
    output_format: str = "svg"
    theme: str | None = None
    scale: float = 1.0
    # When True, fetch rendered bytes even if MCP_URL_ONLY is set.
    force_fetch: bool = False


def _error_detail(
    message: str,
    *,
    diagram_type: str | None,
    backend: str | None = None,
    code: str = "RENDER_FAILED",
) -> dict[str, Any]:
    lowered = message.lower()
    retryable = any(
        token in lowered
        for token in (
            "temporarily unavailable",
            "cannot connect",
            "connection",
            "timeout",
            "timed out",
            "http 429",
            "http 502",
            "http 503",
            "http 504",
        )
    )
    return {
        "code": code,
        "message": message,
        "diagram_type": diagram_type,
        "backend": backend,
        "retryable": retryable,
        "line": None,
        "column": None,
        "suggestion": None,
    }


def _validation_error_response(
    source_code: str,
    exc: ValidationError,
    *,
    diagram_type: str | None = None,
    output_format: str | None = None,
) -> dict[str, Any]:
    parts = []
    for err in exc.errors():
        loc = err.get("loc", ())
        name = loc[0] if loc else "input"
        parts.append(f"{name}: {err['msg']}")
    err_msg = "; ".join(parts)
    message = f"Validation error: {err_msg}"
    return {
        "code": source_code,
        "success": False,
        "diagram_type": diagram_type,
        "output_format": output_format,
        "url": None,
        "playground": None,
        "local_path": None,
        "error": message,
        "error_detail": _error_detail(
            message,
            diagram_type=diagram_type,
            code="INVALID_INPUT",
        ),
        "cache_hit": False,
    }


def _renderer_identity(*, force_fetch: bool = False) -> str:
    """Stable renderer/config identity included in cache keys."""
    return "|".join(
        (
            f"kroki={MCP_SETTINGS.kroki_server}",
            f"plantuml={MCP_SETTINGS.plantuml_server}",
            f"fallback={int(bool(MCP_SETTINGS.diagram_fallback_enabled))}",
            f"url_only={int(bool(MCP_SETTINGS.url_only))}",
            f"force_fetch={int(bool(force_fetch))}",
            f"memory_only={int(bool(MCP_SETTINGS.memory_only))}",
        )
    )


def generate_from_request(req: DiagramRequest) -> dict[str, Any]:
    """Validate, optionally use cache, then render a diagram."""
    # Lazy import avoids circular import via tools.__init__ -> diagram_tools.
    from mcp_core.tools.schemas import GenerateUMLInput

    try:
        validated = GenerateUMLInput(
            diagram_type=req.diagram_type,
            code=req.code,
            output_dir=req.output_dir,
            output_format=req.output_format,
            theme=req.theme,
            scale=req.scale,
        )
    except ValidationError as exc:
        return _validation_error_response(
            req.code,
            exc,
            diagram_type=(req.diagram_type or "").strip().lower() or None,
            output_format=(req.output_format or "").strip().lower() or None,
        )

    dt_key = validated.diagram_type.lower()
    types_map = getattr(MCP_SETTINGS, "diagram_types", None) or {}
    if dt_key not in types_map:
        error_msg = (
            f"Unsupported diagram type: {validated.diagram_type}. Use uml://types resource "
            "for valid types."
        )
        logger.error(error_msg)
        return {
            "code": validated.code,
            "success": False,
            "diagram_type": dt_key,
            "output_format": validated.output_format,
            "url": None,
            "playground": None,
            "local_path": None,
            "error": error_msg,
            "error_detail": _error_detail(
                error_msg,
                diagram_type=dt_key,
                code="UNSUPPORTED_DIAGRAM_TYPE",
            ),
            "cache_hit": False,
        }

    cache = get_render_cache()
    cache_key: str | None = None
    # File-producing calls are intentionally not cached because a cached local_path may
    # refer to a different request or a file that has since been removed.
    if validated.output_dir is None and cache.enabled:
        cache_key = build_render_cache_key(
            diagram_type=dt_key,
            code=validated.code,
            output_format=validated.output_format,
            theme=validated.theme,
            scale=validated.scale,
            renderer_identity=_renderer_identity(force_fetch=req.force_fetch),
        )
        lookup_start = time.perf_counter()
        cached = cache.get(cache_key)
        lookup_ms = (time.perf_counter() - lookup_start) * 1000.0
        if cached is not None:
            cached["success"] = True
            cached["diagram_type"] = dt_key
            cached["output_format"] = validated.output_format
            cached["cache_hit"] = True
            cached["cache_lookup_ms"] = round(lookup_ms, 3)
            return cached

    result = generate_diagram(
        validated.diagram_type,
        validated.code,
        validated.output_format,
        validated.output_dir,
        validated.theme,
        validated.scale,
        force_fetch=req.force_fetch,
    )
    out = dict(result)
    out["diagram_type"] = dt_key
    out["output_format"] = validated.output_format
    out["success"] = not bool(out.get("error"))
    out["cache_hit"] = False

    if out.get("error"):
        backend = getattr(types_map.get(dt_key), "backend", None)
        out["error_detail"] = _error_detail(
            str(out["error"]),
            diagram_type=dt_key,
            backend=backend,
        )
        return out

    from mcp_core.core.chat_packet import build_display_markdown

    display = build_display_markdown(out)
    if display:
        out["display_markdown"] = display

    if cache_key is not None:
        cache.set(cache_key, out)
    return out
