"""Every example and template UML-MCP ships must render something a person can read.

An engine happily draws a blank canvas for a source that is valid but empty. The
Excalidraw template was a bare rectangle and the Vega example and template were
unlabeled dots, so the catalog looked healthy while showing nothing.
"""

from __future__ import annotations

import base64
import importlib.util
import json
from typing import Any

import httpx
import pytest

from mcp_core.core.config import DIAGRAM_TYPES
from mcp_core.core.diagram_rendering import prepare_diagram_code
from mcp_core.quality.render_check import RenderCheckError, svg_text
from tests.fixtures_real import ROOT
from tools.kroki.kroki_templates import DiagramExamples, DiagramTemplates


def _samples() -> list[tuple[str, str, str]]:
    found = []
    for name in sorted(DIAGRAM_TYPES):
        for kind, holder in (
            ("example", DiagramExamples),
            ("template", DiagramTemplates),
        ):
            code = getattr(holder, f"get_{kind}")(name)
            if code and code.strip():
                found.append((name, kind, code))
    return found


SAMPLES = _samples()


def _stress_script() -> Any:
    spec = importlib.util.spec_from_file_location(
        "run_vercel_kroki_stress", ROOT / "scripts" / "run_vercel_kroki_stress.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _excalidraw_has_text(code: str) -> bool:
    elements = json.loads(code)["elements"]
    return any(
        e.get("type") == "text" and str(e.get("text", "")).strip() for e in elements
    )


def _vega_marks(marks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flat = []
    for mark in marks:
        flat.append(mark)
        flat.extend(_vega_marks(mark.get("marks", [])))
    return flat


def _vega_has_labels(code: str) -> bool:
    spec = json.loads(code)
    return bool(spec.get("axes")) or any(
        mark.get("type") == "text" for mark in _vega_marks(spec.get("marks", []))
    )


def _json_sources() -> list[Any]:
    """Shipped samples plus the stress-test fixtures for the two engines that draw JSON."""
    params = [
        pytest.param(name, code, id=f"{name}-{kind}")
        for name, kind, code in SAMPLES
        if name in ("excalidraw", "vega")
    ]
    stress = _stress_script()
    params += [
        pytest.param(fx["diagram_type"], fx["code"], id=f"{fx['diagram_type']}-stress")
        for fx in stress.FIXTURES_1_20 + stress.FIXTURES_21_37
        if fx["diagram_type"] in ("excalidraw", "vega")
    ]
    return params


@pytest.mark.parametrize(("name", "code"), _json_sources())
def test_json_sources_carry_something_to_read(name: str, code: str) -> None:
    """Offline guard: a bare rectangle or unlabeled dots would render as a blank canvas."""
    has = _excalidraw_has_text if name == "excalidraw" else _vega_has_labels
    assert has(code)


BLANK = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
    '<rect width="10" height="10"/></svg>'
)
LABELLED = BLANK.replace("</svg>", '<text x="1" y="8">Hi</text></svg>')


def _row(svg: str) -> dict[str, str]:
    return {"content_base64": base64.b64encode(svg.encode()).decode()}


def test_stress_content_check_rejects_a_blank_drawing() -> None:
    problem = _stress_script()._content_problem

    assert problem(_row(LABELLED)) is None
    assert problem(_row(BLANK)) == "SVG shows no text"
    assert problem({}) == "no content_base64"


def test_every_shipped_sample_renders_visible_text(kroki_tier) -> None:
    """Through a real Kroki (local Docker or kroki.io), not the fake that echoes input."""
    if not kroki_tier.real:
        pytest.skip("the fake Kroki draws whatever it is given; needs a real engine")
    problems = []
    with httpx.Client(trust_env=kroki_tier.name == "public", timeout=60) as client:
        for name, kind, code in SAMPLES:
            config = DIAGRAM_TYPES[name]
            if "svg" not in [str(f).lower() for f in config.formats]:
                continue
            source = prepare_diagram_code(code, config.backend, None)
            response = client.post(
                f"{kroki_tier.url}/{config.backend}/svg",
                content=source.encode(),
                headers={"Content-Type": "text/plain"},
            )
            if response.status_code != 200:
                problems.append(f"{name} {kind}: HTTP {response.status_code}")
                continue
            try:
                shown = svg_text(response.content).strip()
            except RenderCheckError as exc:
                problems.append(f"{name} {kind}: {exc}")
                continue
            if not shown:
                problems.append(f"{name} {kind}: renders no text")
    assert not problems, "\n".join(problems)
