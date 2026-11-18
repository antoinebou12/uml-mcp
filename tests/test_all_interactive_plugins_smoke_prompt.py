"""The 15-type plugin smoke prompt stays one batched plan, and every source renders."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _name in (
    "d3",
    "stack-diagram",
    "archify",
    "llm-visualizer",
    "schema",
    "deps",
    "statechart",
    "c4",
    "timeline",
    "trace",
):
    _src = str(ROOT / "examples" / "plugins" / f"uml-mcp-plugin-{_name}" / "src")
    if _src not in sys.path:
        sys.path.insert(0, _src)

from uml_mcp_plugin_archify import ArchifyRenderer
from uml_mcp_plugin_c4 import C4Renderer
from uml_mcp_plugin_d3 import D3Renderer
from uml_mcp_plugin_deps import DepsRenderer
from uml_mcp_plugin_llm_visualizer import LLMVisualizerRenderer
from uml_mcp_plugin_schema import SchemaRenderer
from uml_mcp_plugin_stack_diagram import StackDiagramRenderer
from uml_mcp_plugin_statechart import StatechartRenderer
from uml_mcp_plugin_timeline import TimelineRenderer
from uml_mcp_plugin_trace import TraceRenderer

PROMPT = ROOT / "tests" / "prompts" / "all_interactive_plugins_smoke_test.md"
BATCH_A = (
    "d3_force",
    "d3_architecture",
    "d3_topology",
    "stack_diagram",
    "archify_architecture",
    "archify_workflow",
    "archify_sequence",
    "llm_2d",
)
BATCH_B = (
    "llm_3d",
    "db_schema",
    "dependency_graph",
    "state_machine",
    "agent_trace",
    "c4_model",
    "timeline",
)

RENDERERS = {}
for _renderer in (
    D3Renderer(),
    StackDiagramRenderer(),
    ArchifyRenderer(),
    LLMVisualizerRenderer(),
    SchemaRenderer(),
    DepsRenderer(),
    StatechartRenderer(),
    C4Renderer(),
    TimelineRenderer(),
    TraceRenderer(),
):
    for _dtype in _renderer.diagram_types:
        RENDERERS[_dtype] = _renderer


def prompt_sources() -> dict[str, str]:
    text = PROMPT.read_text(encoding="utf-8")
    sections = re.split(r"^#### (\w+)\s*$", text, flags=re.MULTILINE)
    found: dict[str, str] = {}
    for index in range(1, len(sections), 2):
        name, body = sections[index], sections[index + 1]
        match = re.search(r"```json\s*(.*?)\s*```", body, re.DOTALL)
        if name == "llm_3d":
            assert match is None
            assert "Same JSON as `llm_2d`" in body
            continue
        assert match, name
        found[name] = match.group(1)
    found["llm_3d"] = found["llm_2d"]
    return found


def test_prompt_is_one_batched_plan_and_covers_every_type():
    text = PROMPT.read_text(encoding="utf-8")
    sources = prompt_sources()
    headings = re.findall(r"^#### (\w+)", text, flags=re.MULTILINE)
    assert headings == list(BATCH_A + BATCH_B)
    assert set(sources) == set(headings)
    assert "Eight calls, in this order." in text
    assert text.count("`generate_uml_batch` once") == 4
    assert "theme: light" in text and "theme: dark" in text
    assert "procedure incomplete" in text
    assert "links[0].target 'missing': no such node" in text
    assert "download_diagram" in text
    assert "Repeat each type" not in text
    assert "each plugin family" not in text
    assert "ALL_PLUGIN_SMOKE_TEST: PASS" in text
    assert "ALL_PLUGIN_SMOKE_TEST: UNVERIFIED" in text


def test_invalid_force_source_names_the_missing_node():
    text = PROMPT.read_text(encoding="utf-8")
    invalid = re.search(
        r"```json\s*(\{\"title\":\"broken\".*?\})\s*```", text, re.DOTALL
    )
    assert invalid
    errors = D3Renderer().validate("d3_force", invalid.group(1))
    assert errors == ["links[0].target 'missing': no such node"]


@pytest.mark.parametrize("dtype", BATCH_A + BATCH_B)
def test_every_prompt_source_validates_and_renders(dtype: str):
    source = prompt_sources()[dtype]
    json.loads(source)
    renderer = RENDERERS[dtype]
    assert renderer.validate(dtype, source) == []
    svg = renderer.render(dtype, source, "svg").content.decode()
    assert svg.startswith("<svg") and "<script" not in svg
    html = renderer.render(dtype, source, "html").content.decode()
    assert html.startswith("<!doctype html>")
