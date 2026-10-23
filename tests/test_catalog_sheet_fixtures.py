"""Contact-sheet fixture assembly (PlantUML/Mermaid kinds, themes, recipes)."""

from __future__ import annotations

from mcp_core.core.config import DIAGRAM_TYPES
from scripts.catalog_sheet_fixtures import (
    MERMAID_KIND_FIXTURES,
    PLANTUML_CATALOG_TYPES,
    PLANTUML_EXTRA_KINDS,
    assemble_fixtures,
    plantuml_theme_names,
    theme_catalog_full,
)


def test_plantuml_catalog_types_cover_plantuml_backends():
    assert "class" in PLANTUML_CATALOG_TYPES
    assert "c4plantuml" in PLANTUML_CATALOG_TYPES
    assert "plantuml" in PLANTUML_CATALOG_TYPES
    for name in PLANTUML_CATALOG_TYPES:
        assert DIAGRAM_TYPES[name].backend in ("plantuml", "c4plantuml")


def test_mermaid_kinds_have_distinct_openers():
    labels = {fx["label"] for fx in MERMAID_KIND_FIXTURES}
    assert "mermaid:flowchart" in labels
    assert "mermaid:sequence" in labels
    assert "mermaid:class" in labels
    codes = "\n".join(fx["code"] for fx in MERMAID_KIND_FIXTURES)
    assert "sequenceDiagram" in codes
    assert "stateDiagram-v2" in codes


def test_theme_catalog_full_skips_kroki_broken_materia():
    names = plantuml_theme_names()
    assert "cerulean" in names
    assert "materia" not in names
    pairs = theme_catalog_full()
    assert ("mermaid", "forest") in pairs
    assert ("d2", "dark") in pairs
    assert ("class", "materia") not in pairs


def test_assemble_full_includes_labeled_groups():
    fixtures = assemble_fixtures(
        catalog=True,
        plantuml_kinds=True,
        mermaid_kinds=True,
        recipes=True,
        skills=True,
        prompts=True,
        themes=True,
        themes_full=False,
    )
    labels = {fx.get("label") or fx["diagram_type"] for fx in fixtures}
    assert "plantuml:timing" in labels
    assert "mermaid:pie" in labels
    assert "recipe:algorithm_flowchart" in labels
    assert any(lbl.startswith("skill:") for lbl in labels)
    assert "prompt:uml_diagram" in labels
    assert any(lbl.startswith("theme:") for lbl in labels)
    assert len(PLANTUML_EXTRA_KINDS) >= 5
