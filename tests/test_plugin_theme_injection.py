"""``theme`` reaches plugin diagrams: the viewer picker and the tool argument set it."""

from __future__ import annotations

import json

import pytest

from mcp_core.core.diagram_rendering import prepare_diagram_code


@pytest.mark.parametrize("theme", ["light", "dark", "auto", "LIGHT"])
def test_theme_is_written_into_a_json_plugin_source(theme):
    out = prepare_diagram_code(
        json.dumps({"title": "x", "nodes": []}), "plugin:stack-diagram", theme
    )
    assert json.loads(out)["theme"] == theme.lower()
    assert json.loads(out)["title"] == "x"


@pytest.mark.parametrize("theme", [None, "", "neon", "default"])
def test_other_themes_leave_the_source_alone(theme):
    code = '{"theme": "dark", "nodes": []}'
    assert prepare_diagram_code(code, "plugin:stack-diagram", theme) == code


@pytest.mark.parametrize("code", ["not json", "[1, 2]", "42"])
def test_non_object_sources_are_untouched(code):
    assert prepare_diagram_code(code, "plugin:x", "dark") == code


def test_other_backends_are_unaffected():
    assert prepare_diagram_code("a -> b", "d2", None) == "a -> b"


def test_viewer_offers_the_theme_picker_for_every_plugin_type():
    from mcp_core.apps.diagram_viewer import _viewer_data

    data = _viewer_data()
    assert data["themes"]["plugin"] == ["light", "dark", "auto"]
    assert "plugin:d3" not in data["themes"]
