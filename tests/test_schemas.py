"""Unit tests for MCP tool Pydantic schemas (generate_uml / validate_uml inputs)."""

import pytest
from pydantic import ValidationError

from mcp_core.core.config import MCP_SETTINGS
from mcp_core.tools.schemas import GenerateUMLInput, ValidateUMLInput


class TestGenerateUMLInput:
    """Validation rules for generate_uml tool arguments."""

    def test_accepts_valid_class_svg(self):
        m = GenerateUMLInput(
            diagram_type="class",
            code="@startuml\nclass A\n@enduml\n",
            output_format="svg",
        )
        assert m.diagram_type == "class"
        assert m.output_format == "svg"

    def test_diagram_type_unknown_raises(self):
        with pytest.raises(ValidationError) as ei:
            GenerateUMLInput(diagram_type="not_a_real_type_xyz", code="x")
        assert "Unsupported diagram type" in str(ei.value)

    def test_diagram_type_whitespace_only_raises(self):
        with pytest.raises(ValidationError) as ei:
            GenerateUMLInput(diagram_type="   ", code="body")
        assert (
            "diagram_type" in str(ei.value).lower() or "empty" in str(ei.value).lower()
        )

    def test_empty_code_raises(self):
        with pytest.raises(ValidationError) as ei:
            GenerateUMLInput(diagram_type="class", code="   ")
        msg = str(ei.value).lower()
        assert (
            "empty" in msg or "at least 1 character" in msg or "string_too_short" in msg
        )

    def test_invalid_global_output_format_raises(self):
        with pytest.raises(ValidationError) as ei:
            GenerateUMLInput(
                diagram_type="class", code="@startuml\n@enduml", output_format="exe"
            )
        assert "output_format" in str(ei.value)

    def test_output_format_not_supported_for_diagram_type_raises(self):
        with pytest.raises(ValidationError) as ei:
            GenerateUMLInput(
                diagram_type="mermaid",
                code="graph TD\nA-->B\n",
                output_format="pdf",
            )
        assert "not supported" in str(ei.value).lower()

    def test_code_over_max_length_raises(self, monkeypatch):
        monkeypatch.setattr(MCP_SETTINGS, "max_code_length", 10)
        with pytest.raises(ValidationError) as ei:
            GenerateUMLInput(diagram_type="class", code="x" * 11)
        assert "maximum length" in str(ei.value).lower()

    def test_output_dir_rejected_when_read_only(self, monkeypatch):
        monkeypatch.setattr(MCP_SETTINGS, "read_only", True)
        with pytest.raises(ValidationError) as ei:
            GenerateUMLInput(
                diagram_type="class",
                code="@startuml\n@enduml",
                output_dir="/tmp/out",
            )
        assert (
            "read_only" in str(ei.value).lower()
            or "output_dir" in str(ei.value).lower()
        )


class TestValidateUMLInput:
    """Validation rules for validate_uml (subset of generate fields)."""

    def test_accepts_valid_mermaid_svg(self):
        m = ValidateUMLInput(
            diagram_type="mermaid",
            code="graph LR\nA-->B\n",
            output_format="svg",
        )
        assert m.diagram_type == "mermaid"

    def test_unknown_diagram_type_raises(self):
        with pytest.raises(ValidationError) as ei:
            ValidateUMLInput(diagram_type="bogus_type", code="x")
        assert "Unsupported diagram type" in str(ei.value)

    def test_invalid_output_format_raises(self):
        with pytest.raises(ValidationError):
            ValidateUMLInput(
                diagram_type="class", code="@startuml\n@enduml", output_format="xyz"
            )

    def test_format_mismatch_for_type_raises(self):
        with pytest.raises(ValidationError) as ei:
            ValidateUMLInput(
                diagram_type="mermaid",
                code="graph TD\nA-->B\n",
                output_format="txt",
            )
        assert "not supported" in str(ei.value).lower()
