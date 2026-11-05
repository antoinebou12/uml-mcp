import base64

import pytest

from mcp_core.plugins.architecture_assets import inline_assets, validate_icon


@pytest.mark.parametrize(
    "content",
    [
        '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.com/a.png"/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>',
    ],
)
def test_active_svg_icons_rejected(content):
    uri = "data:image/svg+xml;base64," + base64.b64encode(content.encode()).decode()
    with pytest.raises(ValueError):
        validate_icon(uri)


def test_svg_brand_colors_preserved():
    raw = b'<svg xmlns="http://www.w3.org/2000/svg"><path fill="#ff3300" d="M0 0h10v10z"/></svg>'
    uri = "data:image/svg+xml;base64," + base64.b64encode(raw).decode()
    validate_icon(uri)
    assert base64.b64decode(uri.split(",")[1]) == raw


def test_assets_embed_original_bytes_and_reject_missing_tokens(tmp_path):
    raw = b'<svg xmlns="http://www.w3.org/2000/svg"/>'
    (tmp_path / "vendor.SVG").write_bytes(raw)
    result = inline_assets("%%ICON_vendor%%", tmp_path)
    assert result == "data:image/svg+xml;base64," + base64.b64encode(raw).decode()
    with pytest.raises(ValueError, match="ICON_missing"):
        inline_assets("%%ICON_missing%%", tmp_path)


def test_font_tokens_are_only_embedded_when_requested(tmp_path):
    (tmp_path / "Geist.woff2").write_bytes(b"font")
    assert inline_assets("%%FONT_DISPLAY%%", tmp_path, tmp_path) == "Zm9udA=="
    with pytest.raises(ValueError, match="FONT_DISPLAY"):
        inline_assets("%%FONT_DISPLAY%%", tmp_path)
