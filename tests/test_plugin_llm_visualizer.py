"""The LLM visualizer plugin: source validation, SVG/HTML safety and the browser viewer."""

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
    / "examples/plugins/uml-mcp-plugin-llm-visualizer/src"
)
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from uml_mcp_plugin_llm_visualizer import LLMVisualizerRenderer
from uml_mcp_plugin_llm_visualizer.model import parse
from uml_mcp_plugin_llm_visualizer.samples import (
    AUTOENCODER,
    EXAMPLE,
    SAMPLES,
    TRANSFORMER,
)

TYPES = ("llm_2d", "llm_3d")


def src(**overrides) -> str:
    base = {"layers": [{"id": "a"}, {"id": "b", "kind": "output"}]}
    return json.dumps({**base, **overrides})


def test_registers_both_types():
    renderer = LLMVisualizerRenderer()
    assert set(renderer.diagram_types) == set(TYPES) == set(SAMPLES)
    for spec in renderer.diagram_types.values():
        assert spec.security_profile == "sandboxed"


@pytest.mark.parametrize("dtype", TYPES)
@pytest.mark.parametrize("fmt", ["svg", "html"])
def test_example_renders(dtype, fmt):
    out = LLMVisualizerRenderer().render(dtype, EXAMPLE, fmt)
    assert out.content
    if fmt == "svg":
        root = ET.fromstring(out.content)
        assert root.tag.endswith("svg")
        assert b"<script" not in out.content
    else:
        assert out.mime_type.startswith("text/html")


def test_flow_layout_draws_shaped_kinds():
    renderer = LLMVisualizerRenderer()
    svg = renderer.render("llm_2d", AUTOENCODER, "svg").content.decode()
    ET.fromstring(svg)
    assert svg.count("<polygon") == 2  # encoder and decoder trapezoids
    assert "<circle" not in svg
    assert 'stroke-dasharray="7 6"' in svg  # the dashed skip edge arches over
    assert renderer.render("llm_3d", AUTOENCODER, "svg").content
    assert renderer.render("llm_2d", AUTOENCODER, "html").content


def test_groups_draw_containers_with_repeat_badges():
    renderer = LLMVisualizerRenderer()
    for dtype in TYPES:
        svg = renderer.render(dtype, TRANSFORMER, "svg").content.decode()
        ET.fromstring(svg)
    svg2d = renderer.render("llm_2d", TRANSFORMER, "svg").content.decode()
    assert svg2d.count('stroke-dasharray="6 5"') == 2  # one container per group
    assert "Encoder block" in svg2d and "×6" in svg2d


def test_top_down_flow_stacks_vertically_and_left_right_spreads():
    from uml_mcp_plugin_llm_visualizer.svg import _place

    for direction, axis in (("LR", 0), ("TB", 1)):
        spec = parse(variant_source(AUTOENCODER, direction=direction))
        pos, _, _, _ = _place(spec)
        values = [pos[layer.id][axis] for layer in spec.layers]
        assert values == sorted(values) and len(set(values)) == len(values)
        other = 1 - axis
        centres = {round(pos[k][other] + pos[k][other + 2] / 2) for k in pos}
        assert len(centres) == 1  # one lane: everything centred on the flow line


def variant_source(base: str, **changes) -> str:
    return json.dumps({**json.loads(base), **changes})


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (src(direction="UP"), "direction"),
        (src(groups=[{"id": "g"}, {"id": "g"}]), "duplicate group"),
        (src(groups=[{"id": "g", "color": "blue"}]), "hex color"),
        (src(groups=[{"id": "g", "repeat": 0}]), "repeat"),
        (json.dumps({"layers": [{"id": "a", "group": "nope"}]}), "unknown group"),
    ],
)
def test_invalid_groups_and_direction(source, message):
    errors = LLMVisualizerRenderer().validate("llm_2d", source)
    assert errors and message in errors[0]


def test_auto_theme_is_accepted():
    assert not LLMVisualizerRenderer().validate("llm_2d", src(theme="auto"))


def test_invalid_layout():
    errors = LLMVisualizerRenderer().validate("llm_2d", src(layout="radial"))
    assert errors and "layout" in errors[0]


def test_default_connections_chain_layers():
    spec = parse(src())
    assert [(c.source, c.target) for c in spec.connections] == [("a", "b")]


def test_fenced_json_is_accepted():
    assert parse("```json\n" + src() + "\n```").layers[0].id == "a"


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("not json", "must be JSON"),
        ("[]", "source must be an object"),
        (json.dumps({"layers": []}), "non-empty"),
        (src(theme="neon"), "theme"),
        (json.dumps({"layers": [{"id": "a"}, {"id": "a"}]}), "duplicate"),
        (json.dumps({"layers": [{"id": "a b"}]}), "id must use"),
        (json.dumps({"layers": [{"id": "a", "kind": "bogus"}]}), "kind"),
        (json.dumps({"layers": [{"id": "a", "color": "red"}]}), "hex color"),
        (json.dumps({"layers": [{"id": "a", "repeat": 0}]}), "repeat"),
        (json.dumps({"layers": [{"id": "a", "shape": [1, 2, 3, 4, 5]}]}), "shape"),
        (src(connections=[{"from": "a", "to": "zzz"}]), "unknown layer"),
        (src(connections=[{"from": "a", "to": "a"}]), "itself"),
    ],
)
def test_invalid_sources(source, message):
    errors = LLMVisualizerRenderer().validate("llm_2d", source)
    assert errors and message in errors[0]


def test_max_layers_setting():
    renderer = LLMVisualizerRenderer()
    renderer.configure({"max_layers": 1})
    assert "limit is 1" in renderer.validate("llm_2d", src())[0]
    with pytest.raises(ValueError):
        renderer.configure({"max_layers": 0})


def test_labels_are_escaped_in_svg_and_html():
    evil = "</script><img src=x onerror=alert(1)>"
    source = json.dumps(
        {"title": evil, "layers": [{"id": "a", "label": evil, "note": evil}]}
    )
    renderer = LLMVisualizerRenderer()
    for dtype in TYPES:
        svg = renderer.render(dtype, source, "svg").content.decode()
        ET.fromstring(svg)
        assert "<img" not in svg
        page = renderer.render(dtype, source, "html").content.decode()
        assert "<img" not in page
        assert page.count("</script>") == 2  # the JSON block and the runtime only


def _grab(pattern: str, text: str) -> str:
    match = re.search(pattern, text, re.DOTALL)
    assert match, f"{pattern!r} not found"
    return match.group(1)


def test_html_csp_hashes_match_inline_code():
    page = LLMVisualizerRenderer().render("llm_3d", EXAMPLE, "html").content.decode()
    csp = unescape(_grab(r'Content-Security-Policy" content="([^"]+)"', page))
    script = _grab(r"<script>(.*?)</script>", page)
    style = _grab(r"<style>(.*?)</style>", page)
    for text in (script, style):
        digest = base64.b64encode(hashlib.sha256(text.encode()).digest()).decode()
        assert f"sha256-{digest}" in csp
    assert "default-src 'none'" in csp
    assert "http" not in script


playwright = pytest.importorskip("playwright.sync_api")


@pytest.mark.parametrize("dtype", TYPES)
@pytest.mark.parametrize("source", [AUTOENCODER, TRANSFORMER])
def test_flow_viewer_has_no_errors(dtype, source):
    page_html = LLMVisualizerRenderer().render(dtype, source, "html").content.decode()
    with playwright.sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 800})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.set_content(page_html)
        for mode in ("3d", "2d"):
            page.click(f"#mode-{mode}")
        page.click("#layers button:nth-child(2)")
        assert page.inner_text("#inspect-title") in {"Encoder", "Multi-head attention"}
        assert not errors
        browser.close()


@pytest.mark.parametrize("dtype", TYPES)
def test_viewer_switches_modes_and_inspects(dtype, tmp_path):
    page_html = LLMVisualizerRenderer().render(dtype, EXAMPLE, "html").content.decode()
    with playwright.sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 800})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.set_content(page_html)
        want = "2d" if dtype == "llm_2d" else "3d"
        assert page.evaluate("window.__llmViewer.view.mode") == want
        for mode in ("2d", "3d"):
            page.click(f"#mode-{mode}")
            assert page.evaluate("window.__llmViewer.view.mode") == mode
            assert page.get_attribute(f"#mode-{mode}", "aria-pressed") == "true"
        page.click("#layers button:nth-child(3)")
        assert page.inner_text("#inspect-title") == "Grouped-query attention"
        assert page.inner_text("#inspect-repeat") == "×32"
        yaw = page.evaluate("window.__llmViewer.view.yaw")
        box = page.locator("#scene").bounding_box()
        page.mouse.move(box["x"] + 300, box["y"] + 300)
        page.mouse.down()
        page.mouse.move(box["x"] + 380, box["y"] + 300, steps=4)
        page.mouse.up()
        assert page.evaluate("window.__llmViewer.view.yaw") != yaw
        page.screenshot(path=str(tmp_path / f"{dtype}.png"))
        assert not errors
        browser.close()


# The VAE an agent actually sent: ``name``/``type`` instead of ``label``/``kind``.
VAE_AS_SENT = json.dumps(
    {
        "title": "VAE",
        "layers": [
            {"id": "input", "name": "Input x", "type": "input"},
            {"id": "encoder", "name": "Encoder qφ(z|x)", "type": "block"},
            {"id": "latent", "name": "Latent z", "type": "tensor"},
            {"id": "decoder", "name": "Decoder pθ(x|z)", "type": "block"},
            {"id": "output", "name": "Reconstruction x̂", "type": "output"},
        ],
        "connections": [
            {"from": "input", "to": "encoder"},
            {"from": "encoder", "to": "latent", "label": "μ, σ → sample z"},
            {"from": "latent", "to": "decoder"},
            {"from": "decoder", "to": "output"},
        ],
    },
    ensure_ascii=False,
)


def test_name_and_type_aliases_and_inferred_kinds():
    spec = parse(VAE_AS_SENT)
    assert [layer.label for layer in spec.layers][1] == "Encoder qφ(z|x)"
    assert [layer.kind for layer in spec.layers] == [
        "input",
        "encoder",
        "vector",
        "decoder",
        "output",
    ]
    # encoder/decoder shapes switch an unspecified layout to the flow of shapes
    assert spec.layout == "flow"


def test_explicit_kind_and_layout_win_over_inference():
    spec = parse(
        json.dumps(
            {
                "layout": "grid",
                "layers": [{"id": "encoder", "kind": "attention"}, {"id": "b"}],
            }
        )
    )
    assert spec.layers[0].kind == "attention"
    assert spec.layout == "grid"
    assert parse(src()).layout == "grid"  # nothing shaped: cards stay the default


def test_vae_draws_trapezoids_in_2d_and_funnels_in_3d():
    renderer = LLMVisualizerRenderer()
    flat = renderer.render("llm_2d", VAE_AS_SENT, "svg").content.decode()
    assert flat.count("<polygon") == 2  # encoder and decoder trapezoids
    assert "shape not set" not in flat
    solid = renderer.render("llm_3d", VAE_AS_SENT, "svg").content.decode()
    root = ET.fromstring(solid)
    ns = "{http://www.w3.org/2000/svg}"

    def front(layer_id):  # the last polygon of a solid is its front face
        group = root.find(f".//{ns}g[@id='layer-{layer_id}']")
        assert group is not None
        points = group.findall(f"{ns}polygon")[-1].get("points") or ""
        pts = [tuple(map(float, p.split(","))) for p in points.split()]
        left = [y for x, y in pts if x == min(px for px, _ in pts)]
        right = [y for x, y in pts if x == max(px for px, _ in pts)]
        return max(left) - min(left), max(right) - min(right)

    enc_in, enc_out = front("encoder")
    dec_in, dec_out = front("decoder")
    assert enc_in > 2 * enc_out  # narrows along the flow
    assert dec_out > 2 * dec_in  # widens back
    assert "shape not set" not in solid


def test_3d_page_draws_the_vae_funnel_without_errors():
    page_html = (
        LLMVisualizerRenderer().render("llm_3d", VAE_AS_SENT, "html").content.decode()
    )
    with playwright.sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 800})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.set_content(page_html)
        page.click("#layers button:nth-child(2)")
        assert page.inner_text("#inspect-title") == "Encoder qφ(z|x)"
        assert page.inner_text("#inspect-kind") == "encoder"
        assert page.inner_text("#inspect-shape") == "not set"
        assert not errors
        browser.close()


# The VAE with mean and log-variance heads that an agent sent (``dense`` everywhere).
VAE_HEADS = json.dumps(
    {
        "layers": [
            {"id": "input", "name": "Input x", "type": "input", "shape": [784]},
            {"id": "enc", "name": "Encoder", "type": "dense", "shape": [256]},
            {"id": "mu", "name": "Mean μ", "type": "dense", "shape": [2]},
            {
                "id": "logvar",
                "name": "Log variance log σ²",
                "type": "dense",
                "shape": [2],
            },
            {"id": "z", "name": "Latent z = μ + σ ⊙ ε", "type": "latent", "shape": [2]},
            {"id": "dec", "name": "Decoder", "type": "dense", "shape": [256]},
            {"id": "out", "name": "Reconstruction x̂", "type": "output", "shape": [784]},
        ],
        "connections": [
            {"from": "input", "to": "enc", "label": "encode x"},
            {"from": "enc", "to": "mu", "label": "predict μ"},
            {"from": "enc", "to": "logvar", "label": "predict log σ²"},
            {"from": "mu", "to": "z", "label": "sample z = μ + σ ⊙ ε"},
            {"from": "logvar", "to": "z", "label": "σ = exp(½ log σ²)"},
            {"from": "z", "to": "dec", "label": "decode z"},
            {"from": "dec", "to": "out", "label": "reconstruct x̂"},
        ],
    },
    ensure_ascii=False,
)


def test_role_in_the_name_beats_a_vague_type():
    kinds = [layer.kind for layer in parse(VAE_HEADS).layers]
    assert kinds == [
        "input",
        "encoder",
        "vector",
        "vector",
        "bottleneck",
        "decoder",
        "output",
    ]

    def kind(name, type_):
        return (
            parse(json.dumps({"layers": [{"id": "a", "name": name, "type": type_}]}))
            .layers[0]
            .kind
        )

    assert (
        kind("Multi-head attention", "dense") == "attention"
    )  # "mu" is not a token here
    assert kind("Projection", "dense") == "feedforward"
    assert parse(src()).title == "Model architecture"


def test_parallel_branches_share_a_column():
    spec = parse(VAE_HEADS)
    assert spec.ranks() == {
        "input": 0,
        "enc": 1,
        "mu": 2,
        "logvar": 2,
        "z": 3,
        "dec": 4,
        "out": 5,
    }
    # residual / feedback edges never reorder a chain
    assert list(parse(TRANSFORMER).ranks().values()) == sorted(
        parse(TRANSFORMER).ranks().values()
    )
    assert all("rank" in layer for layer in spec.as_dict()["layers"])


def _layer_box(svg_text, layer_id):
    root = ET.fromstring(svg_text)
    ns = "{http://www.w3.org/2000/svg}"
    group = root.find(f".//{ns}g[@id='layer-{layer_id}']")
    assert group is not None
    rect = group.find(f"{ns}rect")
    assert rect is not None
    return float(rect.get("x") or 0), float(rect.get("y") or 0)


def test_heads_stack_in_2d_and_3d():
    renderer = LLMVisualizerRenderer()
    flat = renderer.render("llm_2d", VAE_HEADS, "svg").content.decode()
    (mx, my), (lx, ly) = _layer_box(flat, "mu"), _layer_box(flat, "logvar")
    assert mx == lx and ly > my  # same column, log σ² under μ
    assert "<polygon" in flat  # encoder and decoder trapezoids
    solid = renderer.render("llm_3d", VAE_HEADS, "svg").content.decode()
    assert solid.count('id="layer-') == 7
    ET.fromstring(solid)


def test_heads_page_fits_a_chat_frame():
    page_html = (
        LLMVisualizerRenderer().render("llm_2d", VAE_HEADS, "html").content.decode()
    )
    with playwright.sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 560, "height": 430})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.set_content(page_html)
        assert page.is_hidden("aside")  # the layer list gives way to the canvas
        canvas = page.locator("#scene").bounding_box()
        assert canvas and canvas["height"] > 300
        page.click("#mode-3d")
        assert not errors
        browser.close()


def test_grid_residual_edge_loops_beside_the_stack():
    flat = LLMVisualizerRenderer().render("llm_2d", EXAMPLE, "svg").content.decode()
    root = ET.fromstring(flat)
    ns = "{http://www.w3.org/2000/svg}"
    labels = {
        t.text: t
        for t in root.iter(f"{ns}text")
        if "edge-label" in (t.get("class") or "")
    }
    card = _layer_box(flat, "embed")
    # the residual label sits right of the cards, not hidden behind them
    assert float(labels["residual path"].get("x") or 0) > card[0] + 236
    # adjacent-row labels start beside their arrow
    assert labels["hidden states"].get("style") == "text-anchor:start"


def test_every_kind_has_a_glyph_on_its_card():
    from uml_mcp_plugin_llm_visualizer.glyphs import GLYPHS
    from uml_mcp_plugin_llm_visualizer.model import LAYER_KINDS

    assert set(LAYER_KINDS) <= set(GLYPHS)
    flat = LLMVisualizerRenderer().render("llm_2d", EXAMPLE, "svg").content.decode()
    assert flat.count('class="glyph"') == len(parse(EXAMPLE).layers)
    ET.fromstring(flat)
    page_html = (
        LLMVisualizerRenderer().render("llm_2d", EXAMPLE, "html").content.decode()
    )
    assert '"glyphs":' in page_html  # the page draws the same primitives
