"""Regression tests for agent-facing MCP tool contracts."""

from __future__ import annotations

from fastmcp.tools.function_parsing import ParsedFunction

from mcp_core.tools import diagram_tools
from mcp_core.tools.schemas import (
    BatchDiagramResult,
    DiagramResult,
    DiagramTypesOutput,
    ValidationResult,
)


def _input_schema(fn):
    return ParsedFunction.from_function(fn).input_schema


def test_list_diagram_types_schema_describes_all_optional_filters() -> None:
    schema = _input_schema(diagram_tools.list_diagram_types)
    props = schema["properties"]

    assert set(props) == {"query", "backend", "output_format", "limit"}
    assert all(props[name].get("description") for name in props)
    # All discovery filters are intentionally optional. JSON Schema may omit
    # `required` entirely when the set is empty; both forms mean the same thing.
    assert schema.get("required", []) == []


def test_generate_uml_schema_describes_parameters_and_required_fields() -> None:
    schema = _input_schema(diagram_tools.generate_uml)
    props = schema["properties"]

    assert set(props) == {
        "diagram_type",
        "code",
        "output_dir",
        "output_format",
        "theme",
        "scale",
    }
    assert all(props[name].get("description") for name in props)
    assert set(schema.get("required", [])) == {"diagram_type", "code"}


def test_validate_uml_schema_describes_parameters_and_required_fields() -> None:
    schema = _input_schema(diagram_tools.validate_uml)
    props = schema["properties"]

    assert set(props) == {"diagram_type", "code", "output_format", "strict"}
    assert all(props[name].get("description") for name in props)
    assert set(schema.get("required", [])) == {"diagram_type", "code"}


def test_generate_uml_batch_schema_describes_parameters_and_required_fields() -> None:
    schema = _input_schema(diagram_tools.generate_uml_batch)
    props = schema["properties"]

    assert set(props) == {"items", "output_dir"}
    assert all(props[name].get("description") for name in props)
    assert schema.get("required", []) == ["items"]


def test_list_diagram_types_response_matches_declared_output_schema() -> None:
    result = diagram_tools.list_diagram_types(limit=2)
    parsed = DiagramTypesOutput.model_validate(result)
    assert len(parsed.root) <= 2


def test_validate_uml_response_matches_declared_output_schema() -> None:
    result = diagram_tools.validate_uml(
        "class",
        "@startuml\nclass A\n@enduml",
        "svg",
    )
    parsed = ValidationResult.model_validate(result)
    assert isinstance(parsed.valid, bool)


def test_generate_uml_response_matches_declared_output_schema(monkeypatch) -> None:
    expected = {
        "code": "graph TD; A-->B;",
        "success": True,
        "diagram_type": "mermaid",
        "output_format": "svg",
        "url": "https://example.test/diagram.svg",
        "source": "test",
        "cache_hit": False,
        "mime_type": "image/svg+xml",
    }
    monkeypatch.setattr(diagram_tools, "generate_from_request", lambda _request: expected)

    result = diagram_tools.generate_uml("mermaid", expected["code"])
    parsed = DiagramResult.model_validate(result)
    assert parsed.success is True


def test_generate_uml_batch_response_matches_declared_output_schema(monkeypatch) -> None:
    def fake_generate(request):
        return {
            "code": request.code,
            "success": True,
            "diagram_type": request.diagram_type,
            "output_format": request.output_format,
            "url": "https://example.test/diagram.svg",
            "source": "test",
            "cache_hit": False,
            "mime_type": "image/svg+xml",
        }

    monkeypatch.setattr(diagram_tools, "generate_from_request", fake_generate)
    result = diagram_tools.generate_uml_batch(
        [{"diagram_type": "mermaid", "code": "graph TD; A-->B;"}]
    )
    parsed = BatchDiagramResult.model_validate(result)
    assert len(parsed.results) == 1
    assert parsed.results[0].success is True
