"""The stack-diagram plugin: parsing, auto-layout in four directions, routing, themes, page."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from html import unescape
from pathlib import Path

import pytest

SRC = (
    Path(__file__).resolve().parents[1]
    / "examples/plugins/uml-mcp-plugin-stack-diagram/src"
)
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import itertools

from uml_mcp_plugin_stack_diagram import StackDiagramRenderer
from uml_mcp_plugin_stack_diagram.layout import layout
from uml_mcp_plugin_stack_diagram.samples import CLOUD_EXAMPLE, EXAMPLE, TEMPLATE
from uml_mcp_plugin_stack_diagram.skins import StackSkin

TYPE = "stack_diagram"
DIRECTIONS = ("LR", "RL", "TB", "BT")
PNG_1PX = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def variant(base: str, **changes) -> str:
    return json.dumps({**json.loads(base), **changes})


def arranged(source: str):
    renderer = StackDiagramRenderer()
    spec = renderer._parse(TYPE, source)
    return spec, layout(spec, renderer.skin.metrics)


def test_registers_type():
    renderer = StackDiagramRenderer()
    spec = renderer.diagram_types[TYPE]
    assert spec.formats == ("html", "svg")
    assert spec.security_profile == "sandboxed"
    assert "directions" in spec.interaction_features


@pytest.mark.parametrize("source", [EXAMPLE, CLOUD_EXAMPLE, TEMPLATE])
@pytest.mark.parametrize("theme", ["dark", "light", "auto"])
@pytest.mark.parametrize("fmt", ["svg", "html"])
def test_examples_render(source, theme, fmt):
    out = StackDiagramRenderer().render(TYPE, variant(source, theme=theme), fmt)
    if fmt == "svg":
        root = ET.fromstring(out.content)
        assert root.tag.endswith("svg")
        assert b"<script" not in out.content
        assert b"var(--" not in out.content  # static output uses literal colours
    else:
        assert out.mime_type.startswith("text/html")


@pytest.mark.parametrize("direction", DIRECTIONS)
@pytest.mark.parametrize("source", [EXAMPLE, CLOUD_EXAMPLE])
def test_flow_follows_direction(direction, source):
    spec, lay = arranged(variant(source, direction=direction))
    centre = {
        p.node.id: (p.rect[0] + p.rect[2] / 2, p.rect[1] + p.rect[3] / 2)
        for p in lay.nodes
    }
    axis, sign = {"LR": (0, 1), "RL": (0, -1), "TB": (1, 1), "BT": (1, -1)}[direction]
    for edge in spec.edges:
        delta = centre[edge.target][axis] - centre[edge.source][axis]
        assert delta * sign > 0, (
            f"{edge.source}->{edge.target} runs against {direction}"
        )


@pytest.mark.parametrize("direction", DIRECTIONS)
@pytest.mark.parametrize("source", [EXAMPLE, CLOUD_EXAMPLE])
def test_layout_is_tidy(direction, source):
    spec, lay = arranged(variant(source, direction=direction))
    rects = {p.node.id: p.rect for p in lay.nodes}

    def overlap(a, b):
        return (
            a[0] < b[0] + b[2]
            and b[0] < a[0] + a[2]
            and a[1] < b[1] + b[3]
            and b[1] < a[1] + a[3]
        )

    ids = list(rects)
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            assert not overlap(rects[a], rects[b]), f"{a} overlaps {b}"

    def inside(inner, outer):
        return (
            outer[0] <= inner[0] + 0.5
            and outer[1] <= inner[1] + 0.5
            and inner[0] + inner[2] <= outer[0] + outer[2] + 0.5
            and inner[1] + inner[3] <= outer[1] + outer[3] + 0.5
        )

    boxes = {b.group.id: b.rect for b in lay.boxes}
    groups = {g.id: g for g in spec.groups}
    for node in spec.nodes:
        for gid, rect in boxes.items():
            member = node.group == gid or _descends(node.group, gid, groups)
            assert inside(rects[node.id], rect) == member, f"{node.id} vs group {gid}"
    for gid, group in groups.items():
        if group.parent:
            assert inside(boxes[gid], boxes[group.parent])
    # everything stays inside the canvas
    for rect in [*rects.values(), *boxes.values()]:
        assert rect[0] >= 0 and rect[1] >= 0
        assert rect[0] + rect[2] <= lay.width and rect[1] + rect[3] <= lay.height


def _descends(group_id, ancestor, groups):
    while group_id:
        if group_id == ancestor:
            return True
        group_id = groups[group_id].parent
    return False


@pytest.mark.parametrize("direction", DIRECTIONS)
@pytest.mark.parametrize("source", [EXAMPLE, CLOUD_EXAMPLE])
def test_routes_are_orthogonal_and_clear(direction, source):
    _spec, lay = arranged(variant(source, direction=direction))
    rects = {p.node.id: p.rect for p in lay.nodes}
    for route in lay.routes:
        pts = route.points
        assert len(pts) >= 2
        for a, b in itertools.pairwise(pts):
            assert abs(a[0] - b[0]) < 0.5 or abs(a[1] - b[1]) < 0.5, "diagonal segment"
            lo_x, hi_x = sorted((a[0], b[0]))
            lo_y, hi_y = sorted((a[1], b[1]))
            for nid, r in rects.items():
                if nid in (route.edge.source, route.edge.target):
                    continue
                crosses = (
                    lo_x < r[0] + r[2] - 2
                    and hi_x > r[0] + 2
                    and lo_y < r[1] + r[3] - 2
                    and hi_y > r[1] + 2
                )
                assert not crosses, (
                    f"{route.edge.source}->{route.edge.target} crosses {nid}"
                )


def test_cycles_and_back_edges_still_lay_out():
    source = json.dumps(
        {
            "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
            "edges": [
                {"from": "a", "to": "b"},
                {"from": "b", "to": "c"},
                {"from": "c", "to": "a", "label": "retry"},
            ],
        }
    )
    _, lay = arranged(source)
    assert len(lay.routes) == 3 and all(len(r.points) >= 3 for r in lay.routes[2:])
    assert StackDiagramRenderer().render(TYPE, source, "svg").content


def test_isolated_nodes_and_groups_without_nodes():
    source = json.dumps(
        {"nodes": [{"id": "solo"}], "groups": [{"id": "empty", "name": "Empty"}]}
    )
    spec, lay = arranged(source)
    assert len(lay.nodes) == 1 and not lay.boxes and not spec.edges


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("nope", "must be JSON"),
        ("[]", "must be an object"),
        (json.dumps({"nodes": []}), "non-empty"),
        (json.dumps({"nodes": [{"id": "a b"}]}), "id must use"),
        (json.dumps({"nodes": [{"id": "a"}, {"id": "a"}]}), "duplicate node"),
        (json.dumps({"nodes": [{"id": "a"}], "direction": "UP"}), "direction"),
        (json.dumps({"nodes": [{"id": "a"}], "theme": "neon"}), "theme"),
        (json.dumps({"nodes": [{"id": "a", "group": "g"}]}), "unknown group"),
        (
            json.dumps(
                {"nodes": [{"id": "a"}], "groups": [{"id": "g", "parent": "x"}]}
            ),
            "unknown parent",
        ),
        (
            json.dumps(
                {
                    "nodes": [{"id": "a"}],
                    "groups": [
                        {"id": "g", "parent": "h"},
                        {"id": "h", "parent": "g"},
                    ],
                }
            ),
            "inside itself",
        ),
        (
            json.dumps({"nodes": [{"id": "a"}], "edges": [{"from": "a", "to": "zz"}]}),
            "unknown node",
        ),
        (
            json.dumps({"nodes": [{"id": "a"}], "edges": [{"from": "a", "to": "a"}]}),
            "itself",
        ),
        (json.dumps({"nodes": [{"id": "a", "tone": "pink"}]}), "tone"),
        (
            json.dumps({"nodes": [{"id": "a", "icon": "data:text/html;base64,AAAA"}]}),
            "icon",
        ),
        (
            json.dumps(
                {"nodes": [{"id": "a"}], "groups": [{"id": "g", "style": "wild"}]}
            ),
            "style",
        ),
    ],
)
def test_invalid_sources(source, message):
    errors = StackDiagramRenderer().validate(TYPE, source)
    assert errors and message in errors[0]


def test_max_nodes_setting():
    renderer = StackDiagramRenderer()
    renderer.configure({"max_nodes": 1})
    two = json.dumps({"nodes": [{"id": "a"}, {"id": "b"}]})
    assert "limit is 1" in renderer.validate(TYPE, two)[0]
    with pytest.raises(ValueError):
        renderer.configure({"max_nodes": 0})


def test_icons_glyph_monogram_and_image():
    source = json.dumps(
        {
            "nodes": [
                {"id": "a", "name": "Database", "icon": "database"},
                {"id": "b", "name": "Acme Billing", "icon": "unknownbrand"},
                {"id": "c", "name": "Logo", "icon": PNG_1PX},
            ]
        }
    )
    svg = StackDiagramRenderer().render(TYPE, source, "svg").content.decode()
    assert 'class="ico' in svg  # glyph
    assert "mono-letter" in svg and ">AB<" in svg  # monogram for an unknown name
    assert "<image" in svg and "data:image/png;base64" in svg


def test_markup_is_escaped():
    evil = "</text><script>alert(1)</script>"
    source = json.dumps(
        {
            "title": evil,
            "nodes": [{"id": "a", "name": evil, "role": evil}],
            "groups": [{"id": "g", "name": evil}],
            "edges": [],
        }
    )
    renderer = StackDiagramRenderer()
    svg = renderer.render(TYPE, source, "svg").content.decode()
    ET.fromstring(svg)
    assert "<script" not in svg
    page = renderer.render(TYPE, source, "html").content.decode()
    assert "<script>alert" not in page
    assert page.count("<script") == 2  # the graph data block and the viewer runtime
    assert "\u003cscript" in page  # data is escaped, never raw markup


def _grab(pattern: str, text: str) -> str:
    match = re.search(pattern, text, re.DOTALL)
    assert match, f"{pattern!r} not found"
    return match.group(1)


def test_html_csp_hashes_match_and_no_inline_style_attributes():
    page = StackDiagramRenderer().render(TYPE, EXAMPLE, "html").content.decode()
    csp = unescape(_grab(r'Content-Security-Policy" content="([^"]+)"', page))
    script = _grab(r"<script>(.*?)</script>", page)
    style = _grab(r"<style>(.*?)</style>", page)
    for text in (script, style):
        digest = base64.b64encode(hashlib.sha256(text.encode()).digest()).decode()
        assert f"sha256-{digest}" in csp
    assert "default-src 'none'" in csp
    assert ' style="' not in page  # the CSP would block style attributes
    assert page.count("<style") == 1
    assert "http" not in script
    assert ':root[data-theme="light"]' in style and ':root[data-theme="dark"]' in style


def test_both_palettes_define_every_colour():
    palettes = StackSkin.palettes
    assert set(palettes["dark"]) == set(palettes["light"])


playwright = pytest.importorskip("playwright.sync_api")


def test_page_theme_toggle_and_zoom(tmp_path):
    page_html = StackDiagramRenderer().render(TYPE, EXAMPLE, "html").content.decode()
    with playwright.sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1100, "height": 700})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on(
            "console", lambda m: errors.append(m.text) if m.type == "error" else None
        )
        page.set_content(page_html)
        bg = lambda: page.evaluate("getComputedStyle(document.body).backgroundColor")
        dark = bg()
        assert page.evaluate("document.documentElement.dataset.theme") == "dark"
        page.click("#theme")
        assert page.evaluate("document.documentElement.dataset.theme") == "light"
        assert bg() != dark
        # the SVG repaints with the page theme, not just the chrome
        assert (
            page.evaluate("getComputedStyle(document.querySelector('svg .bg')).fill")
            != "rgb(14, 18, 22)"
        )
        before = page.evaluate("document.getElementById('stage').style.transform")
        page.click("#zin")
        assert (
            page.evaluate("document.getElementById('stage').style.transform") != before
        )
        page.click("#fit")
        assert not errors
        page.screenshot(path=str(tmp_path / "stack.png"))
        browser.close()


def test_auto_theme_follows_system_preference():
    page_html = (
        StackDiagramRenderer()
        .render(TYPE, variant(EXAMPLE, theme="auto"), "html")
        .content.decode()
    )
    with playwright.sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(color_scheme="light")
        page.set_content(page_html)
        assert page.evaluate("document.documentElement.dataset.theme") == "light"
        browser.close()


@pytest.mark.parametrize("which", ["stack", "archify"])
def test_renders_inside_the_mcp_app_viewer(which, tmp_path):
    """The page runs in the viewer's sandboxed iframe: scripts, CSP, theme toggle and all."""
    from mcp_core.apps.diagram_viewer import diagram_viewer_html

    if which == "stack":
        renderer, dtype, source = StackDiagramRenderer(), TYPE, EXAMPLE
    else:
        plugins = Path(__file__).resolve().parents[1] / "examples/plugins"
        sys.path.insert(0, str(plugins / "uml-mcp-plugin-archify/src"))
        from uml_mcp_plugin_archify import ArchifyRenderer
        from uml_mcp_plugin_archify.samples import ARCHITECTURE

        renderer, dtype, source = (
            ArchifyRenderer(),
            "archify_architecture",
            ARCHITECTURE,
        )
    output = renderer.render(dtype, source, "html")
    packet = {
        "success": True,
        "diagram_type": dtype,
        "output_format": "html",
        "mime_type": output.mime_type,
        "content_base64": base64.b64encode(output.content).decode(),
        "code": source,
    }
    with playwright.sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 850})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.set_content(diagram_viewer_html())
        page.evaluate(
            "packet => window.postMessage({jsonrpc:'2.0',method:'ui/notifications/tool-result',params:{structuredContent:packet}}, '*')",
            packet,
        )
        iframe = page.locator("iframe.plugin-frame")
        iframe.wait_for()
        frame = page.frame_locator("iframe.plugin-frame")
        frame.locator("svg.diagram").wait_for()
        assert iframe.get_attribute("sandbox") == "allow-scripts"
        before = frame.locator("html").get_attribute("data-theme")
        frame.locator("#theme").click()
        assert frame.locator("html").get_attribute("data-theme") != before
        assert frame.locator("svg.diagram g[id^=node-]").count() >= 3
        assert not errors
        page.screenshot(path=str(tmp_path / f"{which}-viewer.png"))
        browser.close()
