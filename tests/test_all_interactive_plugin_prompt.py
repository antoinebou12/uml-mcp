"""The complete interactive-plugin smoke prompt contains runnable examples."""

from __future__ import annotations

import importlib
import json
import re
import sys
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import yaml

from mcp_core.plugins.loader import BUNDLED_RENDERERS

ROOT = Path(__file__).resolve().parents[1]
for source in (ROOT / "examples/plugins").glob("*/src"):
    sys.path.insert(0, str(source))

PROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
ENTRY_POINTS = PROJECT["project"]["entry-points"]["uml_mcp.renderers"]
RENDERERS = {}
for name in sorted(BUNDLED_RENDERERS):
    module, class_name = ENTRY_POINTS[name].split(":")
    renderer = getattr(importlib.import_module(module), class_name)()
    RENDERERS.update(dict.fromkeys(renderer.diagram_types, renderer))

PROMPT = ROOT / "tests/prompts/all_interactive_plugins_smoke_test.md"
SOURCES = dict(
    re.findall(
        r"^### (\w+)\n\n```json\n(.*?)\n```",
        PROMPT.read_text(encoding="utf-8"),
        re.MULTILINE | re.DOTALL,
    )
)


def test_vercel_explicitly_enables_every_interactive_plugin():
    config = yaml.safe_load((ROOT / "uml-mcp.vercel.yaml").read_text())
    assert config["plugins"]["bundled"] is True
    assert set(config["plugins"]["enabled"]) == BUNDLED_RENDERERS


def test_prompt_covers_every_interactive_type():
    assert SOURCES.keys() == RENDERERS.keys()
    assert "ALL_PLUGIN_SMOKE_TEST: PASS" in PROMPT.read_text(encoding="utf-8")


@pytest.mark.parametrize("diagram_type", sorted(RENDERERS))
def test_prompt_source_validates_and_renders_both_formats(diagram_type):
    source = SOURCES[diagram_type]
    json.loads(source)
    renderer = RENDERERS[diagram_type]
    assert renderer.validate(diagram_type, source) == []
    svg = renderer.render(diagram_type, source, "svg")
    assert svg.mime_type == "image/svg+xml"
    assert ET.fromstring(svg.content).tag == "{http://www.w3.org/2000/svg}svg"
    page = renderer.render(diagram_type, source, "html")
    assert page.mime_type.startswith("text/html")
    assert page.content.decode().lower().startswith("<!doctype html>")
