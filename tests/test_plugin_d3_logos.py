"""Bundled brand logos: safe, complete, linked, and drawn by every plugin that uses them."""

from __future__ import annotations

import base64
import json
import re
import sys
from pathlib import Path

import pytest
from uml_mcp_plugin_d3.brand_icons import PROVIDER_LOGOS, TECH_LOGOS, brand_svg
from uml_mcp_plugin_d3.icons import BRANDS, SERVICES

from tests.fixtures_d3 import D3_SRC

BRANDS_DIR = D3_SRC / "uml_mcp_plugin_d3" / "assets" / "brands"
LOGOS = sorted(BRANDS_DIR.glob("*.svg"))

STACK_SRC = (
    Path(__file__).resolve().parents[1]
    / "examples/plugins/uml-mcp-plugin-stack-diagram/src"
)
if str(STACK_SRC) not in sys.path:
    sys.path.insert(0, str(STACK_SRC))


def test_there_are_many_logos():
    assert len(LOGOS) >= 60


@pytest.mark.parametrize("svg", LOGOS, ids=lambda p: p.stem)
def test_every_logo_is_inert_svg(svg):
    from uml_mcp_plugin_stack_diagram.images import validate_icon

    raw = svg.read_bytes()
    assert len(raw) < 20_000
    validate_icon("data:image/svg+xml;base64," + base64.b64encode(raw).decode())


def test_every_mapping_points_at_a_bundled_file():
    names = {p.stem for p in LOGOS}
    assert set(PROVIDER_LOGOS.values()) | set(TECH_LOGOS.values()) <= names
    # and every bundled file is used by at least one name
    assert names <= set(PROVIDER_LOGOS.values()) | set(TECH_LOGOS.values())


def test_every_logo_service_draws_its_logo():
    services = [key.split(":", 1)[1] for key in SERVICES if key.startswith("tech:")]
    with_logo = [name for name in services if name in TECH_LOGOS]
    assert len(with_logo) >= 55
    for name in with_logo:
        display = SERVICES[f"tech:{name}"][1]
        # by key, and by the display name a resolved node carries
        assert brand_svg("tech", name).startswith('<svg class="brand-logo"'), name
        assert brand_svg("tech", display), display
        assert name in BRANDS  # monogram fallback and tint exist too


def test_readme_links_every_logo_to_its_source():
    readme = (BRANDS_DIR / "README.md").read_text(encoding="utf-8")
    for svg in LOGOS:
        url = f"https://cdn.jsdelivr.net/npm/@lobehub/icons-static-svg@1.101.0/icons/{svg.name}"
        assert f"({url})" in readme, svg.name
    assert "MIT" in readme and "trademarks" in readme


def test_logos_render_offline_in_every_plugin():
    """The marks are inlined: no URL is fetched to draw them, locally or hosted."""
    sys.path.insert(0, str(STACK_SRC.parent.parent / "uml-mcp-plugin-archify/src"))
    from uml_mcp_plugin_archify import ArchifyRenderer
    from uml_mcp_plugin_d3 import D3Renderer
    from uml_mcp_plugin_stack_diagram import StackDiagramRenderer

    names = ["github", "qwen", "openrouter", "langgraph", "snowflake", "claudecode"]
    d3 = json.dumps({"nodes": [{"id": n, "service": f"tech:{n}"} for n in names]})
    plain = json.dumps({"nodes": [{"id": n, "name": n, "icon": n} for n in names]})
    outputs = {
        "d3": D3Renderer().render("d3_architecture", d3, "svg").content.decode(),
        "stack": StackDiagramRenderer()
        .render("stack_diagram", plain, "svg")
        .content.decode(),
        "archify": ArchifyRenderer()
        .render("archify_architecture", plain, "svg")
        .content.decode(),
    }
    for plugin, svg in outputs.items():
        drawn = svg.count('class="brand-logo"') + svg.count('<svg class="logo"')
        assert drawn == len(names), plugin
        assert not re.search(r'href="https?://', svg), plugin
