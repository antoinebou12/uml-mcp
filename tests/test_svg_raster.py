"""SVG→PNG fallback for Kroki SVG-only diagram types."""

from __future__ import annotations

import base64
from unittest.mock import patch

from mcp_core.core.diagram_service import DiagramRequest, generate_from_request
from mcp_core.core.svg_raster import rasterize_svg, svg_to_png
from mcp_core.tools.schemas import GenerateUMLInput

TINY_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="80" height="40">'
    b'<rect width="80" height="40" fill="#ccd"/>'
    b'<text x="8" y="26" font-size="14">d2</text></svg>'
)


def test_svg_to_png_produces_png_magic():
    png = svg_to_png(TINY_SVG)
    assert png is not None
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_svg_to_png_accepts_graphviz_pt_units():
    svg = (
        b'<?xml version="1.0"?>'
        b'<svg width="100pt" height="50pt" viewBox="0 0 100 50" '
        b'xmlns="http://www.w3.org/2000/svg">'
        b'<rect width="100" height="50" fill="#abc"/></svg>'
    )
    png = svg_to_png(svg)
    assert png is not None
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_svg_to_png_ignores_nested_marker_viewboxes():
    """svgbob embeds tiny marker viewBoxes; root size must win."""
    from io import BytesIO

    from PIL import Image

    svg = (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="256" height="64">'
        b'<symbol viewBox="0 0 8 8"><path d="M0 0h8v8z"/></symbol>'
        b'<rect width="256" height="64" fill="#ddd"/>'
        b'<text x="10" y="36" font-size="16">Client</text></svg>'
    )
    png = svg_to_png(svg)
    assert png is not None
    size = Image.open(BytesIO(png)).size
    assert size[0] >= 128 and size[1] >= 32


def test_svg_to_png_renders_nomnoml_style_pt_fonts():
    """Nomnoml uses Helvetica + font-size=12pt; glyphs must still paint."""
    from io import BytesIO

    from PIL import Image

    svg = (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="120" height="40" '
        b'style="background:#000">'
        b'<rect x="10" y="8" width="100" height="24" fill="#eee8d5"/>'
        b'<g font-family="Helvetica" font-size="12pt" fill="#33322E">'
        b'<text x="60" y="25" text-anchor="middle">Client</text></g></svg>'
    )
    png = svg_to_png(svg)
    assert png is not None
    im = Image.open(BytesIO(png)).convert("RGB")
    # Cream box alone is bright; text introduces darker ink.
    assert any(p[0] < 100 for p in im.get_flattened_data())


def test_rasterize_svg_jpeg():
    out = rasterize_svg(TINY_SVG, "jpeg")
    assert out is not None
    raw, mime = out
    assert mime == "image/jpeg"
    assert raw[:2] == b"\xff\xd8"


def test_generate_uml_input_allows_png_for_svg_only_type():
    GenerateUMLInput(diagram_type="d2", code="a -> b", output_format="png")


def test_generate_uml_input_still_rejects_pdf_for_d2():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="not supported"):
        GenerateUMLInput(diagram_type="d2", code="a -> b", output_format="pdf")


@patch("mcp_core.core.diagram_service.generate_diagram")
def test_generate_from_request_rasterizes_svg_only_png(mock_generate):
    mock_generate.return_value = {
        "code": "a -> b",
        "url": "https://kroki.io/d2/svg/x",
        "playground": None,
        "local_path": None,
        "content_base64": base64.b64encode(TINY_SVG).decode(),
        "mime_type": "image/svg+xml",
        "source": "kroki",
    }
    out = generate_from_request(
        DiagramRequest(diagram_type="d2", code="a -> b", output_format="png")
    )
    mock_generate.assert_called_once()
    assert mock_generate.call_args.args[2] == "svg"
    assert out["success"] is True
    assert out["output_format"] == "png"
    assert out["mime_type"] == "image/png"
    assert out["format_fallback"] == "svg_rasterized"
    assert base64.b64decode(out["content_base64"])[:8] == b"\x89PNG\r\n\x1a\n"
