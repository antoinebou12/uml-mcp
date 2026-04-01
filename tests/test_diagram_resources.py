"""
Unit tests for MCP diagram resources.
"""

import json
from unittest.mock import MagicMock

from mcp_core.resources.diagram_resources import (
    get_diagram_examples,
    get_diagram_templates,
    get_diagram_types,
    get_output_formats,
    get_recommended_workflow,
    get_server_info,
    register_diagram_resources,
)


class TestGetDiagramTypes:
    """Tests for get_diagram_types resource."""

    def test_returns_dict_keyed_by_diagram_type(self):
        """get_diagram_types returns a JSON string with diagram type keys."""
        result = json.loads(get_diagram_types())
        assert isinstance(result, dict)
        assert "class" in result
        assert "sequence" in result
        assert "mermaid" in result

    def test_each_entry_has_backend_description_formats(self):
        """Each diagram type has backend, description, formats."""
        result = json.loads(get_diagram_types())
        for name, config in result.items():
            assert "backend" in config
            assert "description" in config
            assert "formats" in config
            assert isinstance(config["formats"], list)


class TestGetDiagramTemplates:
    """Tests for get_diagram_templates resource."""

    def test_returns_dict_keyed_by_diagram_type(self):
        """get_diagram_templates returns a JSON string with template strings."""
        result = json.loads(get_diagram_templates())
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_values_are_strings(self):
        """Each template value is a non-empty string."""
        result = json.loads(get_diagram_templates())
        for name, template in result.items():
            assert isinstance(template, str)
            assert len(template) > 0


class TestGetDiagramExamples:
    """Tests for get_diagram_examples resource."""

    def test_returns_dict_keyed_by_diagram_type(self):
        """get_diagram_examples returns a JSON string with example strings."""
        result = json.loads(get_diagram_examples())
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_values_are_strings(self):
        """Each example value is a string."""
        result = json.loads(get_diagram_examples())
        for name, example in result.items():
            assert isinstance(example, str)

    def test_every_diagram_type_has_template_and_example(self):
        """Every diagram type from get_diagram_types has non-default template and example."""
        types_result = json.loads(get_diagram_types())
        templates_result = json.loads(get_diagram_templates())
        examples_result = json.loads(get_diagram_examples())
        for diagram_type in types_result:
            assert diagram_type in templates_result, (
                f"Missing template for {diagram_type}"
            )
            assert diagram_type in examples_result, (
                f"Missing example for {diagram_type}"
            )
            t = templates_result[diagram_type]
            e = examples_result[diagram_type]
            assert isinstance(t, str) and len(t) > 0, (
                f"Empty template for {diagram_type}"
            )
            assert isinstance(e, str) and len(e) > 0, (
                f"Empty example for {diagram_type}"
            )
            assert "No specific template" not in t, (
                f"Default template for {diagram_type}"
            )
            assert "No specific example" not in e, f"Default example for {diagram_type}"


class TestGetOutputFormats:
    """Tests for get_output_formats resource."""

    def test_returns_dict_mapping_type_to_formats_list(self):
        """get_output_formats returns JSON with diagram type -> list of formats."""
        result = json.loads(get_output_formats())
        assert isinstance(result, dict)
        assert "class" in result
        assert isinstance(result["class"], list)
        assert "svg" in result["class"] or "png" in result["class"]


class TestGetServerInfo:
    """Tests for get_server_info resource."""

    def test_contains_expected_keys(self):
        """get_server_info returns JSON with server_name, version, description, tools, prompts, kroki_server, plantuml_server."""
        result = json.loads(get_server_info())
        assert "server_name" in result
        assert "version" in result
        assert "description" in result
        assert "tools" in result
        assert "prompts" in result
        assert "kroki_server" in result
        assert "plantuml_server" in result

    def test_tools_and_prompts_are_lists(self):
        """tools and prompts are lists (may be empty before server bootstrap)."""
        result = json.loads(get_server_info())
        assert isinstance(result["tools"], list)
        assert isinstance(result["prompts"], list)


class TestGetRecommendedWorkflow:
    """Tests for get_recommended_workflow resource."""

    def test_contains_workflow_and_prompt(self):
        """Result has workflow and prompt strings."""
        result = json.loads(get_recommended_workflow())
        assert "workflow" in result
        assert "prompt" in result
        assert isinstance(result["workflow"], str)
        assert isinstance(result["prompt"], str)
        assert "generate_uml" in result["workflow"]
        assert "plan" in result["workflow"].lower()


class TestRegisterDiagramResources:
    """Tests for register_diagram_resources."""

    def test_server_resource_called_for_each_uri(self):
        """register_diagram_resources calls server.resource(uri) for each resource."""
        server = MagicMock()
        server.resource.return_value = lambda f: f

        registered = register_diagram_resources(server)

        expected_uris = [
            "uml://types",
            "uml://templates",
            "uml://examples",
            "uml://formats",
            "uml://server-info",
            "uml://mermaid-examples",
            "uml://bpmn-guide",
            "uml://workflow",
        ]
        for uri in expected_uris:
            assert uri in registered
        assert server.resource.call_count == len(expected_uris)

    def test_returns_list_of_uris(self):
        """register_diagram_resources returns list of registered URIs."""
        server = MagicMock()
        server.resource.return_value = lambda f: f

        result = register_diagram_resources(server)

        assert isinstance(result, list)
        assert "uml://types" in result
        assert "uml://workflow" in result
