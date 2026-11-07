"""Bundled diagram renderers load by default; tools and other packages stay opt-in."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from mcp_core.core.settings_file import reset_config_cache
from mcp_core.plugins import loader
from mcp_core.plugins.api import RENDERERS_GROUP, TOOLS_GROUP

PLUGINS = Path(__file__).resolve().parents[1] / "examples/plugins"
for name in ("d3", "stack-diagram", "archify"):
    path = str(PLUGINS / f"uml-mcp-plugin-{name}" / "src")
    if path not in sys.path:
        sys.path.insert(0, path)


def ep(name: str, dist: str) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        value=f"pkg:{name}",
        dist=SimpleNamespace(name=dist, version="1.0"),
    )


FAKE = {
    RENDERERS_GROUP: [
        ep("d3", "uml-mcp"),
        ep("stack-diagram", "uml-mcp"),
        ep("archify", "uml-mcp"),
        ep("llm-visualizer", "uml-mcp"),
        ep("deps", "uml-mcp"),
        ep("architecture", "uml-mcp"),  # in uml-mcp, but not a bundled default
        ep("archify", "evil-package"),  # same name, other distribution
        ep("hello", "uml-mcp-plugin-hello"),
    ],
    TOOLS_GROUP: [ep("d3", "uml-mcp")],
}


@pytest.fixture
def discover(tmp_path, monkeypatch):
    monkeypatch.setattr(loader, "entry_points", lambda group: FAKE.get(group, []))

    def run(yaml: str | None) -> dict[tuple[str, str, str | None], bool]:
        if yaml is None:
            monkeypatch.setenv("UML_MCP_CONFIG", "none")
        else:
            cfg = tmp_path / "uml-mcp.yaml"
            cfg.write_text(yaml, encoding="utf-8")
            monkeypatch.setenv("UML_MCP_CONFIG", str(cfg))
        reset_config_cache()
        return {(s.group, s.name, s.distribution): s.enabled for s in loader.discover()}

    yield run
    reset_config_cache()


def test_bundled_renderers_are_on_without_any_config(discover):
    got = discover(None)
    for name in ("d3", "stack-diagram", "archify", "llm-visualizer", "deps"):
        assert got[("renderers", name, "uml-mcp")] is True
    assert got[("tools", "d3", "uml-mcp")] is False  # tools add tokens: opt-in
    assert got[("renderers", "architecture", "uml-mcp")] is False
    assert got[("renderers", "archify", "evil-package")] is False
    assert got[("renderers", "hello", "uml-mcp-plugin-hello")] is False


def test_bundled_false_returns_to_a_strict_allow_list(discover):
    got = discover("plugins:\n  bundled: false\n  enabled: [archify]\n")
    assert got[("renderers", "archify", "uml-mcp")] is True
    assert got[("renderers", "d3", "uml-mcp")] is False
    assert got[("renderers", "stack-diagram", "uml-mcp")] is False


def test_listing_a_tool_still_enables_it(discover):
    got = discover("plugins:\n  enabled: [d3]\n")
    assert got[("tools", "d3", "uml-mcp")] is True
    assert got[("renderers", "llm-visualizer", "uml-mcp")] is True


def test_stack_and_archify_draw_real_logos_from_names():
    import json

    from uml_mcp_plugin_archify import ArchifyRenderer
    from uml_mcp_plugin_stack_diagram import StackDiagramRenderer

    source = json.dumps(
        {
            "nodes": [
                {"id": "gh", "name": "GitHub Actions", "role": "ci"},
                {"id": "c", "name": "Claude", "icon": "claude"},
                {"id": "db", "name": "Postgres", "icon": "database"},
            ]
        }
    )
    stack = (
        StackDiagramRenderer().render("stack_diagram", source, "svg").content.decode()
    )
    archify = (
        ArchifyRenderer().render("archify_architecture", source, "svg").content.decode()
    )
    for svg in (stack, archify):
        assert svg.count('<svg class="logo"') == 2  # GitHub (from its name) and Claude
        assert 'class="ico' in svg  # Postgres keeps its glyph
        assert "<script" not in svg
    assert 'fill="#ffffff"' in archify  # dark cards back logos with a white tile
