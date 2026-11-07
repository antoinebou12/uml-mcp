"""Skills for the bundled plugin diagram types: present, current, and their examples render."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "build_plugin_skills", ROOT / "scripts" / "build_plugin_skills.py"
)
assert spec and spec.loader
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

RENDERERS = builder.renderers()
BY_TYPE = {
    dtype: renderer
    for renderer in RENDERERS.values()
    for dtype in renderer.diagram_types  # type: ignore[attr-defined]
}


def test_every_plugin_type_has_skill_metadata():
    assert set(BY_TYPE) == set(builder.TYPES)


def test_generated_files_are_current():
    assert builder.main(["--check"]) == 0


@pytest.mark.parametrize("dtype", sorted(builder.TYPES))
def test_type_skill_is_well_formed_and_its_example_validates(dtype):
    text = (builder.SKILLS / dtype / "SKILL.md").read_text(encoding="utf-8")
    front = yaml.safe_load(text.split("---", 2)[1])
    assert front["name"] == dtype
    assert len(" ".join(front["description"].split())) <= builder.MAX_DESCRIPTION
    assert f"**`diagram_type`:** `{dtype}`" in text
    for heading in (
        "## Example prompt",
        "## Notation tips",
        "## Styling",
        "## Example source",
    ):
        assert heading in text, heading
    example = re.search(r"```(json|sql)\n(.*?)\n```", text, re.DOTALL)
    assert example, "missing example source"
    source = example.group(2)
    if example.group(1) == "json":
        json.loads(source)
    renderer = BY_TYPE[dtype]
    assert renderer.validate(dtype, source) == []  # type: ignore[attr-defined]
    out = renderer.render(dtype, source, "svg")  # type: ignore[attr-defined]
    assert out.content.startswith(b"<svg")


@pytest.mark.parametrize("topic", sorted(builder.GUIDES))
def test_guides_point_to_the_workflow_and_render_their_example(topic):
    text = (ROOT / ".skill" / "skills" / f"uml-mcp-{topic}" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "skill://uml-mcp-diagrams/SKILL.md" in text
    types = [t for t, meta in builder.TYPES.items() if meta[1] == topic]
    match = re.search(r"```(?:json|sql)\n(.*?)\n```", text, re.DOTALL)
    assert match, "missing example source"
    source = match.group(1)
    assert BY_TYPE[types[0]].validate(types[0], source) == []  # type: ignore[attr-defined]


def test_workflow_skill_lists_every_guide():
    from mcp_core.resources.diagram_skills import GUIDE_TOPICS

    text = (ROOT / "mcp_core" / "skills" / "uml-mcp-diagrams" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    for topic in GUIDE_TOPICS:
        assert f"skill://uml-mcp-guides/{topic}/SKILL.md" in text, topic
