"""Per-type agent skills stay in sync with DIAGRAM_TYPES (not on MCP skills/list)."""

from __future__ import annotations

from pathlib import Path

import yaml

from mcp_core.core.config import DIAGRAM_TYPES
from mcp_core.resources.diagram_skills import SKILL_URI

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".skill" / "skills"

# Contributor / workflow skills that are not catalog diagram_type keys.
NON_TYPE_SKILLS = frozenset(
    {
        "mcp-python",
        "modern-python",
        "sequential-thinking",
        "uml-diagramming",
        "uml-mcp-diagrams",
        "uml-mcp-navigation",
    }
)


def test_every_diagram_type_has_matching_agent_skill():
    for name in DIAGRAM_TYPES:
        path = SKILLS / name / "SKILL.md"
        assert path.is_file(), f"missing skill for diagram_type={name}"
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        assert lines[0] == "---"
        end = lines.index("---", 1)
        front = yaml.safe_load("\n".join(lines[1:end]))
        assert front["name"] == name
        assert (
            isinstance(front.get("description"), str) and front["description"].strip()
        )
        assert len(" ".join(front["description"].split())) <= 500
        assert f"**`diagram_type`:** `{name}`" in text
        backend = DIAGRAM_TYPES[name].backend
        if backend in ("plantuml", "c4plantuml", "mermaid", "d2"):
            assert "## Themes" in text, name
            assert "`theme`" in text or "**`theme`**" in text
        else:
            assert "## Styling" in text, name


def test_theme_catalog_smoke_types_exist_in_catalog():
    from mcp_core.core.diagram_themes import THEME_CATALOG_SMOKE

    for diagram_type, theme in THEME_CATALOG_SMOKE:
        assert diagram_type in DIAGRAM_TYPES, diagram_type
        assert theme
        skill = (SKILLS / diagram_type / "SKILL.md").read_text(encoding="utf-8")
        assert "## Themes" in skill


def test_no_extra_type_skill_directories():
    type_dirs = {
        p.name
        for p in SKILLS.iterdir()
        if p.is_dir() and (p / "SKILL.md").is_file() and p.name not in NON_TYPE_SKILLS
    }
    assert type_dirs == set(DIAGRAM_TYPES)


def test_generator_is_idempotent():
    import importlib.util

    path = ROOT / "scripts" / "build_diagram_type_skills.py"
    spec = importlib.util.spec_from_file_location("build_diagram_type_skills", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.write_all(check=True) == 0


def test_mcp_skills_list_still_only_workflow_skill():
    """Regression: per-type files must not appear on MCP skills/list."""
    assert SKILL_URI == "skill://uml-mcp-diagrams/SKILL.md"
    assert "uml-mcp-diagrams" not in DIAGRAM_TYPES
