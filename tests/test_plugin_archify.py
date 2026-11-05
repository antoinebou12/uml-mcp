"""The archify plugin: its types, skin, group tones, and use of the shared engine."""

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
from uml_mcp_plugin_archify.samples import ARCHITECTURE, WORKFLOW, WORKFLOW_TEMPLATE
from uml_mcp_plugin_archify.skin import STYLE_TONE, ArchifySkin
from uml_mcp_plugin_stack_diagram.layout import layout

TYPES = ("archify_architecture", "archify_workflow")
ALL_TYPES = (*TYPES, "archify_sequence")


def variant(base: str, **changes) -> str:
    return json.dumps({**json.loads(base), **changes})


def test_registers_both_types():
    renderer = ArchifyRenderer()
    assert set(renderer.diagram_types) == set(ALL_TYPES)
    assert all(
        t.security_profile == "sandboxed" for t in renderer.diagram_types.values()
    )


@pytest.mark.parametrize("dtype", TYPES)
@pytest.mark.parametrize("source", [ARCHITECTURE, WORKFLOW, WORKFLOW_TEMPLATE])
@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("fmt", ["svg", "html"])
def test_renders(dtype, source, theme, fmt):
    out = ArchifyRenderer().render(dtype, variant(source, theme=theme), fmt)
    if fmt == "svg":
        ET.fromstring(out.content)
        assert b"<script" not in out.content
    else:
        assert b"data-theme" in out.content


def test_workflow_defaults_to_top_down_and_architecture_to_left_right():
    renderer = ArchifyRenderer()
    plain = json.dumps(
        {"nodes": [{"id": "a"}, {"id": "b"}], "edges": [{"from": "a", "to": "b"}]}
    )

    def centres(dtype):
        spec = renderer._parse(dtype, plain)
        lay = layout(spec, renderer.skin.metrics)
        return {p.node.id: p.rect for p in lay.nodes}

    arch = centres("archify_architecture")
    flow = centres("archify_workflow")
    assert arch["b"][0] > arch["a"][0] and arch["b"][1] == arch["a"][1]
    assert flow["b"][1] > flow["a"][1] and flow["b"][0] == flow["a"][0]


def test_group_styles_colour_the_groups_and_their_nodes():
    svg = (
        ArchifyRenderer()
        .render("archify_architecture", ARCHITECTURE, "svg")
        .content.decode()
    )
    for tone in {
        STYLE_TONE[s] for s in ("security", "backend", "bus", "database", "frontend")
    }:
        assert f"t-{tone}" in svg
    assert "stroke-dasharray:6 5" in svg  # dashed containers
    # a node inherits the tone of its group: Auth Service sits in the red security group
    assert 'class="card t-red"' in svg


def test_unknown_group_style_is_rejected():
    source = json.dumps(
        {"nodes": [{"id": "a"}], "groups": [{"id": "g", "style": "stack-vendor"}]}
    )
    errors = ArchifyRenderer().validate("archify_architecture", source)
    assert errors and "style must be one of" in errors[0]


def test_palettes_match():
    assert set(ArchifySkin.palettes["dark"]) == set(ArchifySkin.palettes["light"])
