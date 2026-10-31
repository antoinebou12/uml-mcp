import base64
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image

from mcp_core.apps.preview import compact_preview
from mcp_core.core import svg_raster


def test_text_renders_without_system_fonts(monkeypatch):
    import resvg_py

    font = (
        Path(svg_raster.__file__).resolve().parents[1]
        / "assets/fonts/NotoSans-Regular.ttf"
    )
    assert font.is_file()
    monkeypatch.setattr(svg_raster, "_system_font_files", lambda: (str(font),))
    render = resvg_py.svg_to_bytes

    def render_without_fonts(**kwargs: Any):
        kwargs["skip_system_fonts"] = True
        return render(**kwargs)

    monkeypatch.setattr(resvg_py, "svg_to_bytes", render_without_fonts)
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="300" height="70"><rect width="300" height="70" fill="white"/><text x="10" y="45" font-size="24" font-family="monospace" fill="black">Frontend API</text></svg>'
    png = svg_raster.svg_to_png(svg)
    assert png
    image = Image.open(BytesIO(png)).convert("RGB")
    assert (
        sum(
            isinstance(p, tuple) and all(c < 100 for c in p)
            for p in image.get_flattened_data()
        )
        > 150
    )


def test_labelled_preview_keeps_resolution_within_budget():
    text = "".join(
        f'<text x="20" y="{35 + i * 26}" font-size="20">Frontend API request {i}: Users Gateway Backend Database</text>'
        for i in range(12)
    )
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="800"><rect width="1400" height="800" fill="white"/>{text}</svg>'
    result = compact_preview(
        base64.b64encode(svg.encode()).decode(), "image/svg+xml", 48_000
    )
    assert result and len(result) <= 48_000
    image = Image.open(BytesIO(base64.b64decode(result)))
    assert image.width >= 960


def test_c4_embedded_raster_icon_keeps_a_bounded_preview():
    buf = BytesIO()
    Image.new("RGB", (52, 52), "blue").save(buf, format="PNG")
    icon = base64.b64encode(buf.getvalue()).decode()
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="400" height="200"><image xlink:href="data:image/png;base64,{icon}" width="52" height="52"/><text x="20" y="100">C4 Container</text></svg>'
    result = compact_preview(
        base64.b64encode(svg.encode()).decode(),
        "image/svg+xml",
        12000,
        max_dimension=160,
    )
    assert result and len(result) <= 12000
    assert Image.open(BytesIO(base64.b64decode(result))).width <= 160


def test_embedded_svg_or_invalid_raster_does_not_bypass_resource_guard():
    nested = base64.b64encode(
        b'<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.com/tracker.png"/></svg>'
    ).decode()
    for mime in ("svg+xml", "png"):
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><image href="data:image/{mime};base64,{nested}"/></svg>'
        assert (
            compact_preview(
                base64.b64encode(svg.encode()).decode(), "image/svg+xml", 12000
            )
            is None
        )
