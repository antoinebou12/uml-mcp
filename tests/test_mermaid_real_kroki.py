"""Mermaid through a *real* Kroki: the repairs render and the errors are actionable.

The in-test fake Kroki does not parse Mermaid, so these need a real one
(UML_MCP_TEST_KROKI_URL; the CI test job starts one) and skip otherwise.
"""

import base64
import os

import httpx
import pytest

from mcp_core.core.config import MCP_SETTINGS
from mcp_core.core.diagram_rendering import (
    DiagramRenderContext,
    prepare_diagram_code,
    run_diagram_pipeline,
)
from tools.kroki.kroki import Kroki

KROKI_URL = os.environ.get("UML_MCP_TEST_KROKI_URL", "").rstrip("/")

pytestmark = pytest.mark.skipif(
    not KROKI_URL, reason="needs a real Kroki (set UML_MCP_TEST_KROKI_URL)"
)

FLOW = "graph TD\n  A[Start] --> B[End]"


@pytest.fixture(autouse=True)
def _real_kroki_only(monkeypatch):
    """No fallback (it would call the public mermaid.ink) and always fetch the bytes."""
    try:
        httpx.get(f"{KROKI_URL}/health", timeout=5, trust_env=False).raise_for_status()
    except httpx.HTTPError as exc:
        pytest.skip(f"Kroki at {KROKI_URL} is not reachable: {exc}")
    monkeypatch.setattr(MCP_SETTINGS, "diagram_fallback_enabled", False)
    monkeypatch.setattr(MCP_SETTINGS, "url_only", False)
    monkeypatch.setattr(MCP_SETTINGS, "memory_only", True)


def _render(code: str, theme: str | None = None) -> dict:
    ctx = DiagramRenderContext(
        diagram_type="mermaid",
        backend_type="mermaid",
        prepared_code=prepare_diagram_code(code, "mermaid", theme),
        output_format="svg",
        output_dir=None,
        theme=theme,
        scale=1.0,
    )
    return run_diagram_pipeline(ctx, kroki_client=Kroki(base_url=KROKI_URL, timeout=60))


def _svg(out: dict) -> str:
    assert not out.get("error"), out.get("error")
    return base64.b64decode(out["content_base64"]).decode()


@pytest.mark.parametrize(
    "code",
    [
        "```mermaid\n" + FLOW + "\n```",
        "```mermaid\n" + FLOW + "\n```\nHere is your diagram!",
        "graph TD\\n  A[Start] --> B[End]",
        "graph TD\n  A[Start]\u200b --> B[End]",
    ],
    ids=["fence", "fence-and-prose", "escaped-newlines", "zero-width-space"],
)
def test_input_kroki_rejects_as_written_now_renders(code: str) -> None:
    svg = _svg(_render(code))

    assert svg.lstrip().startswith("<svg") or "<svg" in svg
    assert "Start" in svg and "End" in svg


def test_valid_input_still_renders() -> None:
    assert "Start" in _svg(_render(FLOW))


def test_theme_changes_the_picture() -> None:
    default = _svg(_render(FLOW))
    dark = _svg(_render(FLOW, theme="dark"))
    forest = _svg(_render(FLOW, theme="forest"))

    assert len({default, dark, forest}) == 3


def test_a_plantuml_theme_name_does_not_break_a_mermaid_diagram() -> None:
    assert _svg(_render(FLOW, theme="cerulean")) == _svg(_render(FLOW))


def test_theme_with_frontmatter_renders() -> None:
    svg = _svg(_render("---\ntitle: My Flow\n---\n" + FLOW, theme="forest"))

    assert "My Flow" in svg


def test_syntax_error_reports_line_and_expectation_without_server_internals() -> None:
    out = _render("graph TD\n  A --> B\n  B -->")

    error = out["error"]
    assert "Parse error on line 4" in error
    assert "Expecting" in error and "got 'EOF'" in error
    for leaked in ("worker.js", "file://", "/usr/local", "    at "):
        assert leaked not in error


def test_unquoted_parentheses_error_points_at_the_line() -> None:
    """The commonest model mistake: the message must name the line to fix."""
    error = _render("graph TD\n  A[Hello (world)] --> B")["error"]

    assert "Parse error on line 2" in error
    assert "Hello (world)" in error
