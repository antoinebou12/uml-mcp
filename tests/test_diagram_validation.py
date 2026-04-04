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
