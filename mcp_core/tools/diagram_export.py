"""Bounded, app-initiated downloads without storing assets on the server."""

import base64
import hashlib
import html
from io import BytesIO

from pydantic import BaseModel, Field

from mcp_core.apps.diagram_viewer import diagram_viewer_app_only_config
from mcp_core.core.diagram_service import DiagramRequest, generate_from_request

from .tool_decorator import mcp_tool


class ExportChunk(BaseModel):
    chunk: str = Field(max_length=32_000)
    offset: int
    next_offset: int
    total: int
    sha256: str
    mime_type: str
    filename: str


@mcp_tool(
    name="download_diagram",
    description="Download source, SVG, PNG, PDF or HTML chunks. Repeat sha256 on follow-ups.",
    example="download_diagram('mermaid', 'graph TD; A-->B', 'svg')",
    annotations={
        "title": "Download Diagram",
        "readOnlyHint": True,
        "destructiveHint": False,
        "openWorldHint": True,
        "idempotentHint": True,
    },
    app=diagram_viewer_app_only_config(),
    output_schema=ExportChunk,
    lint_ignore={"tool-name-convention": "App-only download helper."},
)
def download_diagram(
    diagram_type: str,
    code: str,
    output_format: str = "svg",
    theme: str | None = None,
    offset: int = 0,
    sha256: str | None = None,
) -> dict:
    """Render a file on demand; return up to 32,000 base64 characters.

    Args:
        diagram_type: Catalog key of the diagram renderer.
        code: Source text to export or render.
        output_format: source, svg, png, pdf or html; HTML is standalone.
        theme: Selected diagram theme; omit to preserve source styling.
        offset: Base64 character offset, starting at zero then next_offset.
        sha256: Digest from the first chunk; repeat on subsequent calls.
    """
    if output_format not in {"source", "svg", "png", "html", "pdf"}:
        return {"error": "Choose source, svg, png, pdf or html for download."}
    if offset < 0 or offset % 32_000:
        return {"error": "Download offset must be a nonnegative multiple of 32000."}
    if not code.strip() or len(code) > 200_000:
        return {"error": "Download requires source between 1 and 200000 characters."}
    from mcp_core.core.diagram_service import _renderer_identity
    from mcp_core.core.render_cache import build_render_cache_key, get_render_cache
    from mcp_core.core.settings_file import get_app_config

    cache = get_render_cache()
    cache_key = "export:" + build_render_cache_key(
        diagram_type=diagram_type,
        code=hashlib.sha256(code.encode()).hexdigest(),
        output_format=output_format,
        theme=theme,
        scale=1.0,
        renderer_identity=_renderer_identity(force_fetch=True)
        + get_app_config().plugins.model_dump_json(),
    )
    cached = cache.get(cache_key)
    if cached is not None:
        return _export_chunk(cached, offset, sha256)
    from mcp_core.core.viewer_theme import apply_viewer_theme

    if output_format != "source":
        code = apply_viewer_theme(code, diagram_type, theme)
    if output_format == "source":
        raw, mime = code.encode(), "text/plain"
    elif output_format == "html" and diagram_type.startswith("d3_"):
        from uml_mcp_plugin_d3 import D3Renderer

        from mcp_core.plugins.loader import RENDERERS

        if diagram_type not in RENDERERS:
            return {"error": "Enable the D3 plugin before exporting interactive HTML."}
        renderer = D3Renderer()
        settings = dict(get_app_config().plugins.settings.get("d3") or {})
        renderer.configure({**settings, "d3_source": "inline"})
        try:
            raw, mime = renderer.render(diagram_type, code, "html").content, "text/html"
        except ValueError as exc:
            return {"error": str(exc)}
    else:
        from mcp_core.core.config import MCP_SETTINGS

        info = MCP_SETTINGS.diagram_types.get(diagram_type)
        plugin_pdf = bool(
            output_format == "pdf"
            and info is not None
            and info.backend.startswith("plugin:")
            and "svg" in info.formats
        )
        raster_from_svg = bool(
            (output_format == "png" or plugin_pdf)
            and info is not None
            and "svg" in info.formats
        )
        result = generate_from_request(
            DiagramRequest(
                diagram_type=diagram_type,
                code=code,
                output_format="svg"
                if output_format == "html" or raster_from_svg
                else output_format,
                theme=theme,
                force_fetch=True,
            )
        )
        if result.get("error"):
            return {"error": result["error"]}
        if not result.get("content_base64"):
            return {
                "error": "The renderer did not return file bytes. Try another format."
            }
        raw = base64.b64decode(result["content_base64"])
        mime = result.get("mime_type") or "application/octet-stream"
        if raster_from_svg:
            from mcp_core.core.svg_raster import svg_to_png

            png = svg_to_png(raw, zoom=2.0)
            if png is None:
                return {"error": "PNG conversion failed. Download SVG instead."}
            raw, mime = png, "image/png"
            if plugin_pdf:
                from PIL import Image

                with Image.open(BytesIO(png)) as image:
                    rgba = image.convert("RGBA")
                    paper = Image.new("RGB", rgba.size, "white")
                    paper.paste(rgba, mask=rgba.getchannel("A"))
                    pdf = BytesIO()
                    paper.save(
                        pdf,
                        format="PDF",
                        resolution=144.0,
                        quality=95,
                        creationDate=None,
                        modDate=None,
                    )
                    raw, mime = pdf.getvalue(), "application/pdf"
        if output_format == "html":
            image = base64.b64encode(raw).decode()
            raw = (
                f'<!doctype html><html><head><meta charset="utf-8"><title>Diagram</title></head><body style="margin:24px;background:#f5f5f5"><img alt="Diagram" style="max-width:100%" src="data:{html.escape(mime, quote=True)};base64,{image}"><details><summary>Source</summary><pre>{html.escape(code)}</pre></details></body></html>'
            ).encode()
            mime = "text/html"
    if len(raw) > 8_000_000:
        return {"error": "Export exceeds 8 MB. Reduce the diagram size."}
    file = {
        "encoded": base64.b64encode(raw).decode(),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "mime_type": mime,
        "filename": "diagram."
        + ("txt" if output_format == "source" else output_format),
    }
    cache.set(cache_key, file)
    return _export_chunk(file, offset, sha256)


def _export_chunk(file: dict, offset: int, digest: str | None) -> dict:
    if digest and digest != file["sha256"]:
        return {
            "error": "The render changed during download. Start the download again."
        }
    encoded = file["encoded"]
    if offset > len(encoded):
        return {"error": "Download offset exceeds the file size. Start again."}
    chunk = encoded[offset : offset + 32_000]
    return {
        "chunk": chunk,
        "offset": offset,
        "next_offset": offset + len(chunk),
        "total": len(encoded),
        "sha256": file["sha256"],
        "mime_type": file["mime_type"],
        "filename": file["filename"],
    }
