"""The interactive-plugins smoke prompt stays runnable; step badges, hints and autonumber work."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _name in ("d3", "stack-diagram", "archify", "llm-visualizer"):
    _src = str(ROOT / "examples" / "plugins" / f"uml-mcp-plugin-{_name}" / "src")
    if _src not in sys.path:
        sys.path.insert(0, _src)

from uml_mcp_plugin_archify import ArchifyRenderer
from uml_mcp_plugin_d3 import D3Renderer
from uml_mcp_plugin_llm_visualizer import LLMVisualizerRenderer
from uml_mcp_plugin_stack_diagram import StackDiagramRenderer

PROMPT = ROOT / "tests" / "prompts" / "chatgpt_mcp_smoke_test.md"
RENDERERS = {}
for _renderer in (
    StackDiagramRenderer(),
    ArchifyRenderer(),
    D3Renderer(),
    LLMVisualizerRenderer(),
):
    for _dtype in _renderer.diagram_types:
        RENDERERS[_dtype] = _renderer


def prompt_sources() -> dict[str, str]:
    text = PROMPT.read_text(encoding="utf-8")
    section = text.split("## Interactive plugins smoke-test prompt", 1)[1].split(
        "\n## ", 1
    )[0]
    return dict(re.findall(r"^\s*- (\w+): (\{.*\})\s*$", section, re.MULTILINE))


def test_prompt_covers_every_plugin_family_and_ends_with_a_verdict():
    sources = prompt_sources()
    assert set(sources) == {
        "stack_diagram",
        "archify_architecture",
        "archify_sequence",
        "d3_architecture",
        "llm_2d",
        "llm_3d",
    }
    text = PROMPT.read_text(encoding="utf-8")
    assert "PLUGIN_SMOKE_TEST: PASS" in text and "output_format: html" in text
    assert "theme: light" in text and "MCP App: UNAVAILABLE" in text


@pytest.mark.parametrize("dtype", sorted(prompt_sources()))
def test_every_prompt_source_validates_and_renders(dtype):
    source = prompt_sources()[dtype]
    json.loads(source)
    renderer = RENDERERS[dtype]
    assert renderer.validate(dtype, source) == []
    svg = renderer.render(dtype, source, "svg").content.decode()
    assert svg.startswith("<svg") and "<script" not in svg
    html = renderer.render(dtype, source, "html").content.decode()
    assert html.startswith("<!doctype html>")


def test_prompt_expectations_match_what_renders():
    """The logos, badges and numbers the prompt asks the client to look for are really drawn."""
    sources = prompt_sources()
    stack = RENDERERS["stack_diagram"].render(
        "stack_diagram", sources["stack_diagram"], "svg"
    )
    stack_svg = stack.content.decode()
    assert stack_svg.count('<svg class="logo"') == 2  # Vercel (group) and GitHub (node)
    assert stack_svg.count('class="step ') == 2 and ">1</text>" in stack_svg
    d3 = RENDERERS["d3_architecture"].render(
        "d3_architecture", sources["d3_architecture"], "svg"
    )
    assert d3.content.decode().count('class="brand-logo"') == 5
    seq = (
        RENDERERS["archify_sequence"]
        .render("archify_sequence", sources["archify_sequence"], "svg")
        .content.decode()
    )
    for i, label in enumerate(("GET /dashboard", "SELECT", "rows", "200 OK"), start=1):
        assert f">{i}. {label}<" in seq


def test_bad_references_list_the_known_ids():
    renderer = StackDiagramRenderer()
    errors = renderer.validate(
        "stack_diagram",
        json.dumps(
            {
                "nodes": [{"id": "api"}, {"id": "db"}],
                "edges": [{"from": "api", "to": "dbb"}],
            }
        ),
    )
    assert errors == ["edges[0].to references unknown node 'dbb'; known: api, db"]
    errors = renderer.validate(
        "stack_diagram",
        json.dumps(
            {"nodes": [{"id": "a", "group": "web"}], "groups": [{"id": "edge"}]}
        ),
    )
    assert "known: edge" in errors[0]
    errors = ArchifyRenderer().validate(
        "archify_sequence",
        json.dumps(
            {
                "participants": [{"id": "a"}, {"id": "b"}],
                "messages": [{"from": "a", "to": "c", "label": "x"}],
            }
        ),
    )
    assert "known: a, b" in errors[0]


@pytest.mark.parametrize("bad", [0, 1000, "2", 1.5])
def test_step_must_be_a_small_positive_integer(bad):
    source = json.dumps(
        {
            "nodes": [{"id": "a"}, {"id": "b"}],
            "edges": [{"from": "a", "to": "b", "step": bad}],
        }
    )
    assert "step" in StackDiagramRenderer().validate("stack_diagram", source)[0]


def test_steps_reach_the_page_detail_data():
    source = json.dumps(
        {
            "nodes": [{"id": "a"}, {"id": "b"}],
            "edges": [{"from": "a", "to": "b", "step": 3}],
        }
    )
    page = (
        StackDiagramRenderer().render("stack_diagram", source, "html").content.decode()
    )
    match = re.search(
        r'<script type="application/json" id="graph">(.*?)</script>', page
    )
    assert match, "page has no graph data"
    graph = json.loads(match.group(1))
    assert graph["edges"] == [{"from": "a", "to": "b", "label": "", "step": 3}]
