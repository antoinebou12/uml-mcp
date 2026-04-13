"""
Unit tests for MCP diagram prompts.
"""

from unittest.mock import MagicMock

from mcp_core.prompts.diagram_prompts import (
    class_diagram_prompt,
    get_prompt_registry,
    register_diagram_prompts,
    sequence_diagram_prompt,
    uml_diagram_prompt,
)


class TestUmlDiagramPrompt:
    """Tests for uml_diagram_prompt."""

    def test_returns_non_empty_string(self):
        """uml_diagram_prompt returns a non-empty string."""
        result = uml_diagram_prompt()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_with_empty_context(self):
        """uml_diagram_prompt(context={}) returns prompt with UML guidance."""
        result = uml_diagram_prompt(context={})
        assert "UML" in result
        assert "notation" in result or "syntax" in result or "diagram" in result
        assert "uml://types" in result
        assert "uml://formats" in result
        assert "generate_uml" in result
        assert "output_dir" in result

    def test_with_diagram_type_in_context(self):
        """uml_diagram_prompt adds diagram type when provided in context."""
        result = uml_diagram_prompt(context={"diagram_type": "class"})
        assert "class" in result
        assert "diagram" in result


class TestClassDiagramPrompt:
    """Tests for class_diagram_prompt."""

    def test_returns_string_with_class_guidance(self):
        """class_diagram_prompt returns string containing class diagram guidance."""
        result = class_diagram_prompt(context={"description": "User and Account"})
        assert isinstance(result, str)
        assert "class" in result.lower()
        assert "PlantUML" in result or "@startuml" in result
        assert "`diagram_type` **class**" in result

    def test_includes_visibility_and_relationships(self):
        """class_diagram_prompt mentions visibility and relationships."""
        result = class_diagram_prompt()
        assert "visibility" in result or "+" in result or "-" in result
        assert (
            "relationship" in result
            or "inheritance" in result
            or "association" in result
        )


class TestSequenceDiagramPrompt:
    """Tests for sequence_diagram_prompt."""

    def test_returns_string_with_sequence_guidance(self):
        """sequence_diagram_prompt returns string with sequence diagram content."""
        result = sequence_diagram_prompt(context={"description": "Login flow"})
        assert isinstance(result, str)
        assert "sequence" in result.lower()
        assert "participant" in result or "PlantUML" in result or "@startuml" in result
        assert "`diagram_type` **sequence**" in result


class TestRegisterDiagramPrompts:
    """Tests for register_diagram_prompts."""

    def test_server_prompt_called_for_each_registered_prompt(self):
        """register_diagram_prompts calls server.prompt(name) for each prompt."""
        server = MagicMock()
        server.prompt.return_value = lambda f: f

        registered = register_diagram_prompts(server)

        registry = get_prompt_registry()
        expected_names = list(registry.keys())
        assert len(registered) == len(expected_names)
        assert server.prompt.call_count == len(expected_names)
        for name in expected_names:
            assert name in registered

    def test_registry_contains_uml_and_class_prompts(self):
        """Prompt registry includes uml_diagram and class_diagram."""
        registry = get_prompt_registry()
        assert "uml_diagram" in registry
        assert "class_diagram" in registry
        assert "uml_diagram_with_thinking" in registry
