"""Regression checks for ChatGPT MCP smoke-test prompts."""

from pathlib import Path

from mcp_core.core.diagram_validation import validate_uml_inputs

SMOKE_PATH = Path(__file__).parent / "prompts" / "chatgpt_mcp_smoke_test.md"

_SMOKE_SEQUENCE = """sequenceDiagram
       participant Client
       participant Server
       Client->>Server: request
       Server-->>Client: response"""

_BATCH_SEQUENCE = """sequenceDiagram
  participant A
  participant B
  A->>B: MCP 2026 request
  B-->>A: Stateless response"""


def test_smoke_prompt_requires_image_url_and_playground():
    text = SMOKE_PATH.read_text(encoding="utf-8")
    assert "generate_uml_image" in text
    assert "Playground" in text
    assert "![diagram]" in text
    assert "output/*.png" in text
    assert "MCP_SMOKE_TEST: PASS" in text
    assert "MCP_BATCH_TEST: PASS" in text
    assert "sequenceDiagram; participant A" not in text
    assert "participant Client" in text
    assert "participant Server" in text
    assert "graph TD; Client-->MCP;" in text
    assert "If that tool is missing" in text


def test_smoke_client_server_fixture_validates_strict():
    assert validate_uml_inputs("mermaid", _SMOKE_SEQUENCE, "svg", strict=True)["valid"]


def test_smoke_batch_fixtures_validate_strict():
    flowchart = "graph TD; Client-->MCP; MCP-->Kroki; Kroki-->MCP; MCP-->Client;"
    assert validate_uml_inputs("mermaid", flowchart, "svg", strict=True)["valid"]
    assert validate_uml_inputs("mermaid", _BATCH_SEQUENCE, "svg", strict=True)["valid"]
    packed = (
        "sequenceDiagram; participant A; participant B; "
        "A->>B: MCP 2026 request; B-->>A: Stateless response;"
    )
    assert validate_uml_inputs("mermaid", packed, "svg", strict=True)["valid"] is False
