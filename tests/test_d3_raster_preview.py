import json
from io import BytesIO

import pytest
from PIL import Image
from uml_mcp_plugin_d3 import D3Renderer
from uml_mcp_plugin_d3.samples import SAMPLES

from mcp_core.core.svg_raster import rasterize_svg


@pytest.mark.parametrize("kind", list(SAMPLES))
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_d3_static_svg_raster_has_visible_content(kind, theme):
    spec = json.loads(SAMPLES[kind][0])
    spec["theme"] = theme
    renderer = D3Renderer()
    svg = renderer.render(kind, json.dumps(spec), "svg").content
    assert b"var(--" not in svg
    raster = rasterize_svg(svg, "png")
    assert raster is not None
    image = Image.open(BytesIO(raster[0])).convert("RGB")
    assert image.width > 100 and image.height > 100
    assert all(
        isinstance(pair, tuple) and pair[1] - pair[0] > 50
        for pair in image.getextrema()
    )
    # Standalone interactive pages still need variables for theme switching.
    assert b"var(--" in renderer.render(kind, json.dumps(spec), "html").content
