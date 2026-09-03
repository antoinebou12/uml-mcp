"""Tests for validate_uml_inputs / structural validation."""

from mcp_core.core.diagram_validation import validate_uml_inputs


def test_validate_uml_ok_class_diagram():
    out = validate_uml_inputs(
        "class",
        "@startuml\nclass User\n@enduml",
        "svg",
    )
    assert out["valid"] is True
    assert out["backend"] == "plantuml"
    assert out["errors"] == []


def test_validate_uml_invalid_type():
    out = validate_uml_inputs("not_a_real_type", "x", "svg")
    assert out["valid"] is False
    assert out["errors"]


def test_validate_uml_format_not_allowed_for_type():
    out = validate_uml_inputs(
        "mermaid",
        "graph TD; A-->B;",
        "pdf",
    )
    assert out["valid"] is False
    assert any("output_format" in e.lower() for e in out["errors"])


def test_validate_uml_unbalanced_plantuml():
    out = validate_uml_inputs(
        "class",
        "@startuml\n@startuml\nclass A\n@enduml",
        "svg",
    )
    assert out["valid"] is False
    assert any("@startuml" in e for e in out["errors"])


def test_validate_uml_mermaid_minimal_ok():
    out = validate_uml_inputs("mermaid", "graph TD; A-->B;", "svg")
    assert out["valid"] is True
    assert out["backend"] == "mermaid"


def test_validate_uml_strict_mermaid_rejects_garbage():
    out = validate_uml_inputs(
        "mermaid",
        "not a diagram",
        "svg",
        strict=True,
    )
    assert out["valid"] is False
    assert any("strict" in e.lower() for e in out["errors"])


def test_validate_uml_strict_mermaid_rejects_dangling_sequence_arrow():
    out = validate_uml_inputs(
        "mermaid",
        "sequenceDiagram\nA->>",
        "svg",
        strict=True,
    )
    assert out["valid"] is False
    assert any("target actor" in e.lower() for e in out["errors"])
    assert any("A->>B: message" in s for s in out["suggestions"])


def test_validate_uml_strict_mermaid_rejects_semicolon_packed_sequence():
    out = validate_uml_inputs(
        "mermaid",
        "sequenceDiagram; participant A; participant B; A->>B: hi",
        "svg",
        strict=True,
    )
    assert out["valid"] is False
    assert any("separate lines" in e.lower() for e in out["errors"])
    assert any("`;`" in s or "semicolon" in s.lower() or "separate" in s.lower() for s in out["suggestions"])


def test_validate_uml_strict_mermaid_accepts_complete_sequence_message():
    out = validate_uml_inputs(
        "mermaid",
        "sequenceDiagram\nA->>B: message\nB-->>A: reply",
        "svg",
        strict=True,
    )
    assert out["valid"] is True
    assert out["errors"] == []


def test_validate_uml_strict_mermaid_ok():
    out = validate_uml_inputs(
        "mermaid",
        "graph TD; A-->B;",
        "svg",
        strict=True,
    )
    assert out["valid"] is True


def test_validate_uml_strict_d2_unclosed_quote():
    out = validate_uml_inputs(
        "d2",
        'x: "broken',
        "svg",
        strict=True,
    )
    assert out["valid"] is False
    assert any("quote" in e.lower() for e in out["errors"])
