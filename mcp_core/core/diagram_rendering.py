"""
Kroki-first diagram rendering pipeline: try Kroki, then optional fallbacks by backend.

Synchronous steps with explicit functions; fallbacks are adapters keyed by backend type.
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

from .config import MCP_SETTINGS

logger = logging.getLogger(__name__)

# Bounded LRU of successful memory-only renders (output_dir is None); limits RAM vs repeated Kroki calls.
_render_cache: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()


def _http_timeout() -> httpx.Timeout:
    r = float(MCP_SETTINGS.max_render_seconds)
    return httpx.Timeout(connect=3.0, read=r, write=10.0, pool=5.0)


@dataclass(frozen=True)
class DiagramRenderContext:
    """Inputs needed after config resolution and code preparation."""

    diagram_type: str
    backend_type: str
    prepared_code: str
    output_format: str
    output_dir: Optional[str]
    theme: Optional[str]
    scale: float


def _cache_key(ctx: DiagramRenderContext) -> str:
    raw = (
        f"{ctx.backend_type}\n{ctx.output_format}\n{ctx.scale}\n{ctx.theme or ''}\n"
        f"{ctx.prepared_code}"
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _diagram_cache_capacity() -> int:
    return max(0, int(MCP_SETTINGS.diagram_cache_size))


def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    cap = _diagram_cache_capacity()
    if cap <= 0 or key not in _render_cache:
        return None
    _render_cache.move_to_end(key)
    return dict(_render_cache[key])


def _cache_set(key: str, value: Dict[str, Any]) -> None:
    cap = _diagram_cache_capacity()
    if cap <= 0:
        return
    _render_cache[key] = dict(value)
    _render_cache.move_to_end(key)
    while len(_render_cache) > cap:
        _render_cache.popitem(last=False)


def prepare_diagram_code(code: str, backend_type: str, theme: Optional[str]) -> str:
    """Strip and wrap PlantUML when needed; Mermaid/D2 pass through (with strip)."""
    prepared_code = code.strip()
    if backend_type == "plantuml":
        if "@startuml" not in prepared_code:
            prepared_code = f"@startuml\n{prepared_code}"
        if "@enduml" not in prepared_code:
            prepared_code = f"{prepared_code}\n@enduml"
        if theme and "!theme" not in prepared_code:
            prepared_code = prepared_code.replace(
                "@startuml", f"@startuml\n!theme {theme}"
            )
    return prepared_code


def _mime_for_output_format(output_format: str) -> Optional[str]:
    """Normalized MIME type for the requested output format (image/text)."""
    fmt = (output_format or "").lower().strip()
    mapping = {
        "svg": "image/svg+xml",
        "png": "image/png",
        "pdf": "application/pdf",
        "jpeg": "image/jpeg",
        "txt": "text/plain; charset=utf-8",
        "base64": None,
    }
    return mapping.get(fmt)


def _attach_render_metadata(
    out: Dict[str, Any],
    *,
    attempts: List[Dict[str, Any]],
    fallback_used: bool,
    render_ms: float,
    cache_hit: bool,
    output_format: str,
) -> Dict[str, Any]:
    out["attempts"] = attempts
    out["fallback_used"] = fallback_used
    out["render_ms"] = round(render_ms, 2)
    out["cache_hit"] = cache_hit
    mime = _mime_for_output_format(output_format)
    if mime is not None:
        out["mime_type"] = mime
    return out


def _handle_diagram_error(e: Exception, code: str) -> str:
    """Return actionable error message for diagram generation failures."""
    try:
        from tools.kroki.kroki import KrokiConnectionError, KrokiHTTPError
    except ImportError:
        return f"Unexpected error generating diagram: {type(e).__name__}: {str(e)}"

    if isinstance(e, KrokiHTTPError):
        status = getattr(e.response, "status_code", None)
        if status == 404:
            return (
                "Diagram service endpoint not found. Check KROKI_SERVER and that "
                "the service is running."
            )
        if status == 503:
            return (
                "Diagram service temporarily unavailable. Check KROKI_SERVER and "
                "network connectivity."
            )
        if status == 400:
            return (
                "Diagram code syntax error. Check examples at uml://examples resource "
                "for valid syntax."
            )
        return (
            f"Diagram service returned HTTP {status}. Check KROKI_SERVER and network."
        )
    if isinstance(e, KrokiConnectionError):
        return (
            "Cannot connect to diagram service. Check KROKI_SERVER and network "
            "connectivity."
        )
    return f"Unexpected error generating diagram: {type(e).__name__}: {str(e)}"


def _generate_diagram_plantuml_fallback(
    diagram_type: str,
    code: str,
    output_format: str,
    output_dir: Optional[str],
    scale: float,
) -> Dict[str, Any]:
    """Fallback to PlantUML server when Kroki fails."""
    from tools.kroki.plantuml import PlantUML

    plantuml_server = MCP_SETTINGS.plantuml_server
    logger.info("Using PlantUML server fallback: %s", plantuml_server)

    plantuml_client = PlantUML(url=plantuml_server)
    encoded = plantuml_client.deflate_and_encode(code)
    url = f"{plantuml_server}/{output_format}/~1{encoded}"
    playground = f"https://www.plantuml.com/plantuml/uml/~1{encoded}"

    if MCP_SETTINGS.url_only:
        return {
            "code": code,
            "url": url,
            "playground": playground,
            "local_path": None,
            "source": "plantuml_server",
        }

    response = httpx.get(url, timeout=_http_timeout())
    response.raise_for_status()
    content = response.content

    if (
        output_format.lower() == "svg"
        and scale is not None
        and abs(scale - 1.0) >= 1e-9
        and scale >= 0.1
    ):
        from tools.kroki.kroki import scale_svg

        content = scale_svg(content, scale)

    local_path = None
    if output_dir:
        filename_prefix = (
            f"{diagram_type}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        )
        out = Path(output_dir)
        try:
            out.mkdir(parents=True, exist_ok=True)
            path = out / f"{filename_prefix}.{output_format}"
            path.write_bytes(content)
            local_path = str(path)
            logger.info("Diagram saved to %s via PlantUML fallback", local_path)
        except OSError as e:
            logger.warning("Could not save diagram to %s (%s)", out, e)
            local_path = None

    out: Dict[str, Any] = {
        "code": code,
        "url": url,
        "playground": playground,
        "local_path": local_path,
        "source": "plantuml_server",
    }
    if local_path is None and content:
        out["content_base64"] = base64.b64encode(content).decode("ascii")
    return out


def _generate_diagram_mermaid_fallback(
    diagram_type: str,
    code: str,
    output_format: str,
    output_dir: Optional[str],
) -> Dict[str, Any]:
    """Fallback to Mermaid.ink when Kroki fails."""
    from tools.kroki.mermaid import generate_mermaid_urls

    logger.info("Using Mermaid.ink fallback")

    urls = generate_mermaid_urls(
        diagram_text=code, theme="default", image_format=output_format.lower()
    )
    url = urls.image_url
    playground = urls.edit_url

    if MCP_SETTINGS.url_only:
        return {
            "code": code,
            "url": url,
            "playground": playground,
            "local_path": None,
            "source": "mermaid_ink",
        }

    response = httpx.get(url, timeout=_http_timeout())
    response.raise_for_status()
    content = response.content

    local_path = None
    if output_dir:
        filename_prefix = (
            f"{diagram_type}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        )
        out = Path(output_dir)
        try:
            out.mkdir(parents=True, exist_ok=True)
            path = out / f"{filename_prefix}.{output_format}"
            path.write_bytes(content)
            local_path = str(path)
            logger.info("Diagram saved to %s via Mermaid.ink fallback", local_path)
        except OSError as e:
            logger.warning("Could not save diagram to %s (%s)", out, e)
            local_path = None

    out: Dict[str, Any] = {
        "code": code,
        "url": url,
        "playground": playground,
        "local_path": local_path,
        "source": "mermaid_ink",
    }
    if local_path is None and content:
        out["content_base64"] = base64.b64encode(content).decode("ascii")
    return out


def try_kroki_render(
    ctx: DiagramRenderContext,
    kroki_client: Any = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[Exception]]:
    """
    Attempt Kroki render. Returns (result_dict, None) on success or (None, exception).
    """
    from mcp_core.core.utils import get_kroki_client

    client = kroki_client if kroki_client is not None else get_kroki_client()
    filename_prefix = (
        f"{ctx.diagram_type}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    )

    try:
        logger.info("Attempting Kroki for %s diagram", ctx.diagram_type)
        if MCP_SETTINGS.url_only:
            kroki_url = client.get_url(
                ctx.backend_type, ctx.prepared_code, ctx.output_format
            )
            playground = client.get_playground_url(ctx.backend_type, ctx.prepared_code)
            out_url_only: Dict[str, Any] = {
                "code": ctx.prepared_code,
                "url": kroki_url,
                "playground": playground,
                "local_path": None,
                "source": "kroki",
            }
            logger.info(
                "URL-only Kroki for %s diagram (no image fetch)", ctx.diagram_type
            )
            return out_url_only, None

        result = client.generate_diagram(
            ctx.backend_type, ctx.prepared_code, ctx.output_format
        )
        content = result["content"]
        if (
            ctx.output_format.lower() == "svg"
            and ctx.scale is not None
            and abs(ctx.scale - 1.0) >= 1e-9
            and ctx.scale >= 0.1
        ):
            from tools.kroki.kroki import scale_svg

            content = scale_svg(content, ctx.scale)

        local_path = None
        if ctx.output_dir:
            out = Path(ctx.output_dir)
            path = out / f"{filename_prefix}.{ctx.output_format}"
            try:
                out.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
                local_path = str(path)
                logger.info("Diagram saved to %s", local_path)
            except OSError as e:
                logger.warning(
                    "Could not save diagram to %s (%s); returning Kroki URL only.",
                    path,
                    e,
                )
                local_path = None

        out: Dict[str, Any] = {
            "code": ctx.prepared_code,
            "url": result["url"],
            "playground": result.get("playground"),
            "local_path": local_path,
            "source": "kroki",
        }
        if local_path is None and content:
            out["content_base64"] = base64.b64encode(content).decode("ascii")

        logger.info("Successfully generated %s diagram via Kroki", ctx.diagram_type)
        return out, None
    except Exception as e:
        logger.warning(
            "Kroki failed for %s: %s. Attempting fallback...",
            ctx.diagram_type,
            str(e),
        )
        return None, e


def run_fallback_if_needed(
    ctx: DiagramRenderContext,
    kroki_error: Exception,
) -> Dict[str, Any]:
    """
    Run backend-specific fallback after Kroki failure, or return aggregated error dict.

    On error, the returned dict includes ``attempts`` and ``fallback_used``.
    On success, returns the same shape as Kroki (no ``attempts``; added by pipeline).
    """
    kroki_summary = _handle_diagram_error(kroki_error, ctx.prepared_code)
    kroki_attempt: Dict[str, Any] = {
        "backend": "kroki",
        "ok": False,
        "error_summary": kroki_summary,
    }

    if ctx.backend_type == "plantuml":
        try:
            logger.info("Falling back to PlantUML server for %s", ctx.diagram_type)
            return _generate_diagram_plantuml_fallback(
                ctx.diagram_type,
                ctx.prepared_code,
                ctx.output_format,
                ctx.output_dir,
                ctx.scale,
            )
        except Exception as fallback_error:
            logger.error(
                "Fallback also failed for %s: %s", ctx.diagram_type, str(fallback_error)
            )
            error_msg = (
                f"Primary (Kroki) failed: {kroki_summary}. "
                f"Fallback also failed: {str(fallback_error)}"
            )
            return {
                "code": ctx.prepared_code,
                "url": None,
                "playground": None,
                "local_path": None,
                "error": error_msg,
                "attempts": [
                    kroki_attempt,
                    {
                        "backend": "plantuml_server",
                        "ok": False,
                        "error_summary": str(fallback_error),
                    },
                ],
                "fallback_used": True,
            }

    if ctx.backend_type == "mermaid":
        try:
            logger.info("Falling back to Mermaid.ink for %s", ctx.diagram_type)
            return _generate_diagram_mermaid_fallback(
                ctx.diagram_type,
                ctx.prepared_code,
                ctx.output_format,
                ctx.output_dir,
            )
        except Exception as fallback_error:
            logger.error(
                "Fallback also failed for %s: %s", ctx.diagram_type, str(fallback_error)
            )
            error_msg = (
                f"Primary (Kroki) failed: {kroki_summary}. "
                f"Fallback also failed: {str(fallback_error)}"
            )
            return {
                "code": ctx.prepared_code,
                "url": None,
                "playground": None,
                "local_path": None,
                "error": error_msg,
                "attempts": [
                    kroki_attempt,
                    {
                        "backend": "mermaid_ink",
                        "ok": False,
                        "error_summary": str(fallback_error),
                    },
                ],
                "fallback_used": True,
            }

    logger.error("No fallback available for %s backend", ctx.backend_type)
    error_msg = (
        f"Primary (Kroki) failed: {kroki_summary}. "
        f"No fallback available for backend '{ctx.backend_type}'."
    )
    return {
        "code": ctx.prepared_code,
        "url": None,
        "playground": None,
        "local_path": None,
        "error": error_msg,
        "attempts": [
            kroki_attempt,
            {
                "backend": "none",
                "ok": False,
                "error_summary": f"No fallback for backend '{ctx.backend_type}'",
            },
        ],
        "fallback_used": False,
    }


def _kroki_failure_when_fallback_disabled(
    ctx: DiagramRenderContext,
    kroki_error: Exception,
) -> Dict[str, Any]:
    """Error shape when Kroki failed and PlantUML/Mermaid fallback is turned off."""
    kroki_summary = _handle_diagram_error(kroki_error, ctx.prepared_code)
    kroki_attempt: Dict[str, Any] = {
        "backend": "kroki",
        "ok": False,
        "error_summary": kroki_summary,
    }
    error_msg = (
        f"Primary (Kroki) failed: {kroki_summary}. "
        "Diagram fallback is disabled (see MCP_DIAGRAM_FALLBACK, VERCEL, USE_LOCAL_KROKI)."
    )
    return {
        "code": ctx.prepared_code,
        "url": None,
        "playground": None,
        "local_path": None,
        "error": error_msg,
        "attempts": [
            kroki_attempt,
            {
                "backend": "none",
                "ok": False,
                "error_summary": "Diagram fallback disabled",
            },
        ],
        "fallback_used": False,
    }


def run_diagram_pipeline(
    ctx: DiagramRenderContext,
    kroki_client: Any = None,
) -> Dict[str, Any]:
    """Kroki first, then optional fallbacks; returns the standard result dict."""
    t0 = time.perf_counter()

    def elapsed_ms() -> float:
        return (time.perf_counter() - t0) * 1000

    if ctx.output_dir is None and not MCP_SETTINGS.url_only:
        cached = _cache_get(_cache_key(ctx))
        if cached is not None:
            logger.debug("Diagram render cache hit for %s", ctx.diagram_type)
            out = dict(cached)
            out["cache_hit"] = True
            out["render_ms"] = round(elapsed_ms(), 2)
            mime = _mime_for_output_format(ctx.output_format)
            if mime is not None:
                out["mime_type"] = mime
            return out

    success, err = try_kroki_render(ctx, kroki_client=kroki_client)
    if success is not None:
        out = dict(success)
        _attach_render_metadata(
            out,
            attempts=[{"backend": "kroki", "ok": True}],
            fallback_used=False,
            render_ms=elapsed_ms(),
            cache_hit=False,
            output_format=ctx.output_format,
        )
        if (
            ctx.output_dir is None
            and not MCP_SETTINGS.url_only
            and not out.get("error")
        ):
            _cache_set(_cache_key(ctx), dict(out))
        return out

    assert err is not None
    kroki_attempt: Dict[str, Any] = {
        "backend": "kroki",
        "ok": False,
        "error_summary": _handle_diagram_error(err, ctx.prepared_code),
    }
    if not MCP_SETTINGS.diagram_fallback_enabled:
        result = _kroki_failure_when_fallback_disabled(ctx, err)
    else:
        result = run_fallback_if_needed(ctx, err)

    if result.get("error"):
        out = dict(result)
        out["render_ms"] = round(elapsed_ms(), 2)
        out["cache_hit"] = False
        mime = _mime_for_output_format(ctx.output_format)
        if mime is not None:
            out["mime_type"] = mime
        return out

    out = dict(result)
    _attach_render_metadata(
        out,
        attempts=[
            kroki_attempt,
            {"backend": out["source"], "ok": True},
        ],
        fallback_used=True,
        render_ms=elapsed_ms(),
        cache_hit=False,
        output_format=ctx.output_format,
    )
    if ctx.output_dir is None and not MCP_SETTINGS.url_only and not out.get("error"):
        _cache_set(_cache_key(ctx), dict(out))
    return out
