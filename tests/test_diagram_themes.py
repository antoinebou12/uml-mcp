"""Theme catalogs and prepare_diagram_code injection for skill-documented themes."""

from __future__ import annotations

from mcp_core.core.config import DIAGRAM_TYPES
from mcp_core.core.diagram_rendering import prepare_diagram_code
from mcp_core.core.diagram_themes import (
    THEME_CATALOG_SMOKE,
    resolve_d2_theme_id,
    theme_backends,
)
from scripts.run_vercel_kroki_stress import FIXTURES_1_20, FIXTURES_21_37


def _fixture_code(diagram_type: str) -> str:
    for fx in list(FIXTURES_1_20) + list(FIXTURES_21_37):
        if fx["diagram_type"] == diagram_type:
            return fx["code"]
    raise KeyError(diagram_type)


def test_theme_catalog_smoke_injects_into_prepared_source():
    for diagram_type, theme in THEME_CATALOG_SMOKE:
        backend = DIAGRAM_TYPES[diagram_type].backend
        assert backend in theme_backends()
        prepared = prepare_diagram_code(_fixture_code(diagram_type), backend, theme)
        if backend in ("plantuml", "c4plantuml"):
            assert f"!theme {theme}" in prepared, (diagram_type, theme)
        elif backend == "mermaid":
            assert f"'theme': '{theme}'" in prepared, (diagram_type, theme)
        elif backend == "d2":
            tid = resolve_d2_theme_id(theme)
            assert tid and f"theme-id: {tid}" in prepared, (diagram_type, theme)


def test_resolve_d2_theme_id_aliases():
    assert resolve_d2_theme_id("dark") == "103"
    assert resolve_d2_theme_id("DEFAULT") == "0"
    assert resolve_d2_theme_id("200") == "200"
    assert resolve_d2_theme_id("cerulean") is None


def test_background_theme_picks():
    from mcp_core.core.diagram_themes import (
        THEME_BG_CATALOG_SMOKE,
        normalize_background,
        pick_theme,
        themes_for_background,
    )

    assert normalize_background("black") == "dark"
    assert normalize_background("B&W") == "bw"
    assert normalize_background("print") == "bw"
    assert pick_theme("plantuml", "bw") == "plain"
    assert pick_theme("mermaid", "dark") == "dark"
    assert "blueprint" in themes_for_background("plantuml", "dark")
    for _bg, diagram_type, theme in THEME_BG_CATALOG_SMOKE:
        assert diagram_type in DIAGRAM_TYPES
        backend = DIAGRAM_TYPES[diagram_type].backend
        prepared = prepare_diagram_code(_fixture_code(diagram_type), backend, theme)
        assert prepared
        if backend in ("plantuml", "c4plantuml"):
            assert f"!theme {theme}" in prepared
