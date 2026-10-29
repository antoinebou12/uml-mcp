"""UMLet catalog examples must not clip labels or use invalid ``++`` visibility."""

from __future__ import annotations

import re

from tools.kroki.kroki_templates import DiagramExamples, DiagramTemplates


def _class_panel(uxf: str) -> str:
    match = re.search(
        r"<panel_attributes>(.*?)</panel_attributes>", uxf, flags=re.DOTALL
    )
    assert match, "umlet UXF missing panel_attributes"
    return match.group(1)


def _box_width(uxf: str) -> int:
    match = re.search(r"<w>(\d+)</w>", uxf)
    assert match, "umlet UXF missing <w>"
    return int(match.group(1))


def test_umlet_template_and_example_use_single_plus_visibility():
    for body in (
        DiagramTemplates.get_template("umlet"),
        DiagramExamples.get_example("umlet"),
    ):
        panel = _class_panel(body)
        assert "++" not in panel
        assert re.search(r"(?m)^[+\-#]", panel), panel


def test_umlet_example_box_fits_longest_line():
    body = DiagramExamples.get_example("umlet")
    panel = _class_panel(body)
    longest = max(len(line) for line in panel.splitlines() if line.strip())
    # UMLet ~8px/char at zoom 10; require width headroom so labels do not clip.
    assert _box_width(body) >= longest * 8
