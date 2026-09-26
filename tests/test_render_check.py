"""mcp_core.quality.render_check: real diagram vs. error page or placeholder."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from mcp_core.quality.render_check import (
    RenderCheckError,
    check_png,
    check_svg,
    png_size,
    svg_text,
)


def _png(width: int, height: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height)).save(buf, "PNG")
    return buf.getvalue()


def test_svg_text_reads_labels_and_skips_styles():
    svg = (
        '<?xml version="1.0"?>\n'
        '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" '
        '"http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">'
        '<svg xmlns="http://www.w3.org/2000/svg"><style>.Alice{fill:red}</style>'
        "<title>ignored</title><g><text>Alice</text>"
        '<foreignObject><div xmlns="http://www.w3.org/1999/xhtml">Bob</div>'
        "</foreignObject> tail</g></svg>"
    )
    assert svg_text(svg) == "Alice Bob tail"
    assert check_svg(svg.encode(), ("Alice", "Bob")) == "Alice Bob tail"


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("Error 400: syntax error", "not well-formed"),
        ('<html xmlns="http://www.w3.org/1999/xhtml"/>', "not <svg>"),
        ('<!DOCTYPE svg [<!ENTITY a "x">]><svg/>', "internal DTD"),
        ('<svg xmlns="http://www.w3.org/2000/svg"><text>Alice</text></svg>', "Bob"),
    ],
)
def test_svg_problems_are_reported(content, message):
    with pytest.raises(RenderCheckError, match=message):
        check_svg(content, ("Alice", "Bob"))


def test_png_checks():
    assert png_size(_png(40, 30)) == (40, 30)
    assert check_png(_png(40, 30)) == (40, 30)
    with pytest.raises(RenderCheckError, match="only 1x1"):
        check_png(_png(1, 1))
    with pytest.raises(RenderCheckError, match="signature"):
        check_png(b"<svg/>")
    with pytest.raises(RenderCheckError, match="does not decode"):
        check_png(b"\x89PNG\r\n\x1a\n" + b"\0" * 40)
