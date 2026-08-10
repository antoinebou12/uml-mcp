"""Regression checks for the tool-only full-catalog MCP stress-test prompt."""

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
        if diagram_type not in text
    ]

    assert not missing, f"Stress prompt is missing catalog types: {missing}"


def test_stress_prompt_is_tool_only_and_directly_executable():
    text = _prompt_text()

    for tool_name in (
        "list_diagram_types",
        "validate_uml",
        "generate_uml",
        "generate_uml_batch",
    ):
        assert tool_name in text

    assert "EXECUTE THIS TEST NOW." in text
    assert "Do NOT stop and ask me to paste outputs." in text
    assert "Do NOT ask me which resources are available." in text
    assert "Do NOT require or attempt to read MCP resources" in text

    # Guard against reintroducing the old resource-gated execution path.
    assert "Read these MCP resources" not in text
    assert "If neither resource can be read" not in text
    assert "this phase fails because the test must not invent" not in text


def test_stress_prompt_embeds_full_catalog_batches():
    text = _prompt_text()

    assert "PHASE 4 - TOOL-ONLY FULL 35-TYPE CATALOG SWEEP" in text
    assert "batch 1 = fixtures 1 through 20" in text
    assert "batch 2 = fixtures 21 through 35" in text
    assert "Do not silently omit a fixture." in text


def test_stress_prompt_keeps_complex_repeatability_and_negative_phases():
    text = _prompt_text()

    assert "PHASE 2 - COMPLEX MERMAID SMOKE TESTS" in text
    assert "PHASE 3 - COMPLEX PLANTUML FAMILY SMOKE TESTS" in text
    assert "PHASE 5 - STATELESS REPEATABILITY" in text
    assert "PHASE 6 - NEGATIVE TESTS" in text
    assert "items must not be empty" in text
    assert "MCP_KROKI_TOOL_ONLY_STRESS_TEST: PASS" in text
    assert "MCP_KROKI_TOOL_ONLY_STRESS_TEST: FAIL - <short reason>" in text
