"""Diagram generation entry for MCP tools: validate once, then render."""

from __future__ import annotations

import base64
import logging
import time
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from .config import MCP_SETTINGS
from .render_cache import build_render_cache_key, get_render_cache
from .svg_raster import is_raster_format, normalize_raster_format, rasterize_svg
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
            f"mermaid_ink={MCP_SETTINGS.mermaid_ink_server}",
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

    requested_fmt = validated.output_format.lower().strip()
    allowed = [f.lower() for f in getattr(types_map[dt_key], "formats", [])]
    rasterize_to: str | None = None
    render_fmt = requested_fmt
    if (
        is_raster_format(requested_fmt)
        and requested_fmt not in allowed
        and "svg" in allowed
    ):
        render_fmt = "svg"
        rasterize_to = normalize_raster_format(requested_fmt)

    cache = get_render_cache()
    cache_key: str | None = None
    # File-producing calls are intentionally not cached because a cached local_path may
    # refer to a different request or a file that has since been removed.
    force_fetch = req.force_fetch or rasterize_to is not None
    if validated.output_dir is None and cache.enabled:
        cache_key = build_render_cache_key(
            diagram_type=dt_key,
            code=validated.code,
            output_format=requested_fmt,
            theme=validated.theme,
            scale=validated.scale,
            renderer_identity=_renderer_identity(force_fetch=force_fetch),
        )
        lookup_start = time.perf_counter()
        cached = cache.get(cache_key)
        lookup_ms = (time.perf_counter() - lookup_start) * 1000.0
        if cached is not None:
            cached["success"] = True
            cached["diagram_type"] = dt_key
            cached["output_format"] = cached.get("output_format") or requested_fmt
            cached["cache_hit"] = True
            cached["cache_lookup_ms"] = round(lookup_ms, 3)
            return cached

    result = generate_diagram(
        validated.diagram_type,
        validated.code,
        render_fmt,
        validated.output_dir,
        validated.theme,
        validated.scale,
        force_fetch=force_fetch,
    )
    out = dict(result)
    out["diagram_type"] = dt_key
    out["output_format"] = requested_fmt
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

    if rasterize_to:
        out = _apply_svg_raster_fallback(out, rasterize_to)

    from mcp_core.core.chat_packet import build_display_markdown

    display = build_display_markdown(out)
    if display:
        out["display_markdown"] = display

    if cache_key is not None:
        cache.set(cache_key, out)
    return out


def _apply_svg_raster_fallback(result: dict[str, Any], target: str) -> dict[str, Any]:
    """Turn SVG bytes into PNG/JPEG when the Kroki type has no native raster."""
    encoded = result.get("content_base64")
    if not encoded:
        out = dict(result)
        out["output_format"] = "svg"
        out["requested_format"] = target
        out["format_fallback"] = "svg_no_bytes"
        out["format_note"] = (
            f"Native '{target}' is unavailable for this diagram type and no SVG "
            "bytes were fetched to rasterize; returning SVG URL only. "
            "Call with force-fetch / generate_uml_image, or use output_format=svg."
        )
        return out
    try:
        svg_bytes = base64.b64decode(encoded)
    except (TypeError, ValueError):
        return result
    raster = rasterize_svg(svg_bytes, target)
    out = dict(result)
    if raster is None:
        out["output_format"] = "svg"
        out["mime_type"] = result.get("mime_type") or "image/svg+xml"
        out["requested_format"] = target
        out["format_fallback"] = "svg_passthrough"
        out["format_note"] = (
            f"Native '{target}' is not offered by Kroki for this type; SVG was "
            "returned because local SVG→raster conversion is unavailable."
        )
        return out
    raw, mime = raster
    out["content_base64"] = base64.b64encode(raw).decode("ascii")
    out["mime_type"] = mime
    out["output_format"] = target
    out["native_format"] = "svg"
    out["format_fallback"] = "svg_rasterized"
    out["format_note"] = (
        f"Kroki only serves SVG for this type; '{target}' was produced by local "
        "SVG rasterization (resvg)."
    )
    return out
