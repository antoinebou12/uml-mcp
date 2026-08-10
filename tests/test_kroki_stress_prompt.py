"""Regression checks for the full-catalog manual MCP stress-test prompt."""

from pathlib import Path

from mcp_core.core.config import MCP_SETTINGS


PROMPT_PATH = Path(__file__).parent / "prompts" / "kroki_full_catalog_stress_test.md"


def _prompt_text() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def test_stress_prompt_tracks_every_runtime_diagram_type():
    text = _prompt_text()

    missing = [
        diagram_type
        for diagram_type in MCP_SETTINGS.diagram_types
        if f"`{diagram_type}`" not in text
    ]

    assert not missing, f"Stress prompt is missing catalog types: {missing}"


def test_stress_prompt_exercises_mcp_resources_and_batch_limit():
    text = _prompt_text()

    for uri in (
        "uml://types",
        "uml://formats",
        "uml://examples",
        "uml://capabilities",
        "uml://server-info",
    ):
        assert uri in text

    assert "batch limit is 20" in text
    assert "first 20 catalog entries" in text
    assert "remaining 15 catalog entries" in text


def test_stress_prompt_keeps_complex_and_negative_phases():
    text = _prompt_text()

    assert "PHASE 2 - SUPER-COMPLEX MERMAID" in text
    assert "PHASE 3 - SUPER-COMPLEX PLANTUML FAMILY" in text
    assert "PHASE 4 - FULL 35-TYPE CATALOG SWEEP" in text
    assert "PHASE 5 - STATELESS REPEATABILITY" in text
    assert "PHASE 6 - NEGATIVE TESTS" in text
    assert "MCP_KROKI_FULL_STRESS_TEST: PASS" in text
    assert "MCP_KROKI_FULL_STRESS_TEST: FAIL - <short reason>" in text
