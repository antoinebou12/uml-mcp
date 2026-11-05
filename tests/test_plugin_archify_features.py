"""Archify presets, legend, header, tags, the sequence type and the page's interactions."""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

PLUGINS = Path(__file__).resolve().parents[1] / "examples/plugins"
for name in ("uml-mcp-plugin-stack-diagram", "uml-mcp-plugin-archify"):
    path = str(PLUGINS / name / "src")
    if path not in sys.path:
        sys.path.insert(0, path)

from uml_mcp_plugin_archify import ArchifyRenderer
from uml_mcp_plugin_archify.samples import (
    ARCHITECTURE,
    SEQUENCE,
    SEQUENCE_TEMPLATE,
    WORKFLOW_TEMPLATE,
)


def variant(base: str, **changes) -> str:
    return json.dumps({**json.loads(base), **changes})


def static(source: str, dtype: str = "archify_architecture", **changes) -> str:
    out = ArchifyRenderer().render(dtype, variant(source, **changes), "svg")
    return out.content.decode()


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_presets_change_the_static_output(theme):
    classic = static(ARCHITECTURE, preset="classic", theme=theme)
    blueprint = static(ARCHITECTURE, preset="blueprint", theme=theme)
    flow = static(ARCHITECTURE, preset="flow", theme=theme)
    for svg in (classic, blueprint, flow):
        ET.fromstring(svg)
    assert ".bracket{display:none}" in classic
    assert ".bracket{display:inline}" in blueprint
    assert ".gbox{stroke-dasharray:12 3 2 3}" in blueprint
    assert ".glow{opacity:.16}" in flow and ".glow{opacity:0}" in classic
    assert "BLUEPRINT" in blueprint


def test_unknown_preset_is_rejected():
    errors = ArchifyRenderer().validate(
        "archify_architecture", variant(ARCHITECTURE, preset="neon")
    )
    assert errors and "preset must be one of" in errors[0]


def test_legend_counts_nodes_per_group_style_and_header_shows_subtitle():
    svg = static(ARCHITECTURE)
    assert "Legend" in svg and "Backend" in svg and "Database" in svg
    assert 'class="badge-n"' in svg and ">3</text>" in svg  # three backend services
    assert "Auth, API, bus and data, grouped by ownership" in svg
    assert "Legend" not in static(WORKFLOW_TEMPLATE)  # no groups, nothing to list


def test_tag_line_is_drawn_and_limited():
    source = json.dumps(
        {"nodes": [{"id": "a", "name": "A", "role": "r", "tag": "app team"}]}
    )
    assert ">app team<" in static(source)
    too_long = json.dumps({"nodes": [{"id": "a", "tag": "x" * 40}]})
    assert "tag" in ArchifyRenderer().validate("archify_architecture", too_long)[0]


def test_every_preset_is_scoped_in_the_page_and_theme_defaults_to_auto():
    renderer = ArchifyRenderer()
    page = renderer.render(
        "archify_architecture", ARCHITECTURE, "html"
    ).content.decode()
    for name in ("classic", "blueprint", "flow"):
        assert f':root[data-preset="{name}"] .gbox' in page
        assert f'<option value="{name}"' in page
    assert 'data-auto="1"' in page
    bare = json.dumps({"nodes": [{"id": "a"}]})
    assert (
        'data-auto="1"'
        in renderer.render("archify_architecture", bare, "html").content.decode()
    )


def test_sequence_renders_participants_messages_and_replies():
    renderer = ArchifyRenderer()
    for template in (SEQUENCE, SEQUENCE_TEMPLATE):
        ET.fromstring(renderer.render("archify_sequence", template, "svg").content)
    svg = static(SEQUENCE, "archify_sequence")
    assert svg.count('class="node"') == 5 and svg.count('class="edge"') == 10
    assert "e-dash" in svg  # replies are dashed
    assert "v26" in svg  # the self message loops back
    assert "indexed by account" in svg
    assert 'class="life"' in svg


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("nope", "must be JSON"),
        (json.dumps({"participants": [{"id": "a"}], "messages": []}), "at least two"),
        (
            json.dumps({"participants": [{"id": "a"}, {"id": "a"}], "messages": []}),
            "duplicate",
        ),
        (
            json.dumps({"participants": [{"id": "a"}, {"id": "b"}], "messages": []}),
            "non-empty",
        ),
        (
            json.dumps(
                {
                    "participants": [{"id": "a"}, {"id": "b"}],
                    "messages": [{"from": "a", "to": "zz", "label": "x"}],
                }
            ),
            "unknown participant",
        ),
        (
            json.dumps(
                {
                    "participants": [{"id": "a"}, {"id": "b"}],
                    "messages": [{"from": "a", "to": "b", "style": "wavy"}],
                }
            ),
            "style",
        ),
    ],
)
def test_invalid_sequences(source, message):
    errors = ArchifyRenderer().validate("archify_sequence", source)
    assert errors and message in errors[0]


playwright = pytest.importorskip("playwright.sync_api")


def _open(dtype: str, source: str, pw):
    page = pw.chromium.launch().new_page(viewport={"width": 1300, "height": 760})
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    html = ArchifyRenderer().render(dtype, source, "html").content.decode()
    page.set_content(html)
    return page, errors


def test_page_focus_path_live_preset_and_escape():
    with playwright.sync_playwright() as pw:
        page, errors = _open("archify_architecture", ARCHITECTURE, pw)

        def dimmed() -> int:
            return page.evaluate("document.querySelectorAll('.node.dim').length")

        assert dimmed() == 0
        # click a node: the rest dims and the detail panel opens with reach counts
        box = page.locator("#node-web").bounding_box()
        page.mouse.click(box["x"] + 20, box["y"] + 20)
        assert page.evaluate("window.__diagram.selected") == "web"
        assert dimmed() > 0 and page.locator("#passport").is_visible()
        assert "Web App" in page.inner_text("#passport")
        assert "downstream" in page.inner_text("#passport").lower()
        # shift+click another node: the shortest path replaces the focus
        target = page.locator("#node-pg").bounding_box()
        page.keyboard.down("Shift")
        page.mouse.click(target["x"] + 20, target["y"] + 20)
        page.keyboard.up("Shift")
        panel = page.inner_text("#passport")
        assert "shortest path · 3 steps" in panel.lower()
        steps = page.locator("#passport ol.steps .chip").all_inner_texts()
        assert steps == ["Web App", "API Service", "User Service", "PostgreSQL"]
        assert "→ HTTPS" in panel  # each step names the edge it follows
        # the path itself is highlighted: its nodes and edges, nothing else
        on_nodes = page.evaluate(
            "[...document.querySelectorAll('.node.on')].map(n => n.dataset.id)"
        )
        assert on_nodes == ["web", "api", "users", "pg"]
        assert page.evaluate("document.querySelectorAll('.edge.on').length") == 3
        # the panel docks on the right and the diagram is re-fitted beside it
        panel_box = page.locator("#passport").bounding_box()
        svg_box = page.locator("svg.diagram").bounding_box()
        assert svg_box["x"] + svg_box["width"] <= panel_box["x"] + 1
        # Esc clears everything
        page.keyboard.press("Escape")
        assert dimmed() == 0 and not page.locator("#passport").is_visible()
        assert page.evaluate("document.querySelectorAll('.on').length") == 0
        # Live animates the edges; the preset picker switches the look
        page.click("#live")
        assert page.evaluate(
            "document.getElementById('stage').classList.contains('live')"
        )
        page.select_option("#preset", "blueprint")
        assert page.evaluate("document.documentElement.dataset.preset") == "blueprint"
        assert (
            page.evaluate(
                "getComputedStyle(document.querySelector('.bracket')).display"
            )
            == "inline"
        )
        page.select_option("#preset", "classic")
        assert (
            page.evaluate(
                "getComputedStyle(document.querySelector('.bracket')).display"
            )
            == "none"
        )
        assert not errors


def test_sequence_page_focus_and_trace():
    with playwright.sync_playwright() as pw:
        page, errors = _open("archify_sequence", SEQUENCE, pw)
        page.evaluate("window.__diagram.focus('cache')")
        assert "Redis" in page.inner_text("#passport")
        assert "participant" in page.inner_text("#passport").lower()
        page.evaluate("window.__diagram.trace('web', 'db')")
        steps = page.locator("#passport ol.steps .chip").all_inner_texts()
        assert steps == ["Web App", "API", "Postgres"]
        assert "→ GET /dashboard" in page.inner_text("#passport")
        assert not errors


def test_both_themes_paint_the_svg_in_the_page():
    with playwright.sync_playwright() as pw:
        page, errors = _open(
            "archify_architecture", variant(ARCHITECTURE, theme="dark"), pw
        )
        dark = page.evaluate("getComputedStyle(document.querySelector('svg .bg')).fill")
        page.click("#theme")
        light = page.evaluate(
            "getComputedStyle(document.querySelector('svg .bg')).fill"
        )
        assert dark != light and not errors
