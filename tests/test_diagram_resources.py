"""
Unit tests for MCP diagram resources.
"""

import json
from unittest.mock import MagicMock

from mcp_core.resources.diagram_resources import (
    get_capabilities,
    get_diagram_examples,
    get_diagram_recipes,
    get_diagram_templates,
    get_diagram_types,
    get_output_formats,
    get_recommended_workflow,
    get_server_info,
    register_diagram_resources,
    register_resources_with_server,
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
        for config in result.values():
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
        for template in result.values():
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
        for example in result.values():
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


class TestGetCapabilities:
    """Tests for get_capabilities resource (uml://capabilities)."""

    def test_returns_matrix_with_backend_formats_description(self):
        """Each diagram type maps to backend, formats list, and description."""
        result = json.loads(get_capabilities())
        assert isinstance(result, dict)
        assert "class" in result
        assert "mermaid" in result
        for entry in result.values():
            assert "backend" in entry
            assert "formats" in entry
            assert isinstance(entry["formats"], list)
            assert "description" in entry
            assert isinstance(entry["description"], str)


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


class TestGetDiagramRecipes:
    """Tests for the uml://recipes resource."""

    def test_returns_dict_with_known_recipes(self):
        """get_diagram_recipes exposes algorithm_flowchart and paper_concept."""
        result = json.loads(get_diagram_recipes())
        assert isinstance(result, dict)
        assert "algorithm_flowchart" in result
        assert "paper_concept" in result

    def test_each_recipe_has_required_fields(self):
        """Each recipe entry has diagram_type, output_format, description, prompt, template."""
        result = json.loads(get_diagram_recipes())
        for name, recipe in result.items():
            assert recipe["diagram_type"], f"{name} missing diagram_type"
            assert recipe["output_format"], f"{name} missing output_format"
            assert isinstance(recipe["description"], str) and recipe["description"]
            assert isinstance(recipe["prompt"], str) and recipe["prompt"]
            assert isinstance(recipe["template"], str) and recipe["template"]

    def test_algorithm_template_has_complexity_labels(self):
        """The algorithm starter ships with at least one Big-O label."""
        result = json.loads(get_diagram_recipes())
        template = result["algorithm_flowchart"]["template"]
        assert "flowchart TD" in template
        assert "O(n" in template
        assert template.strip().startswith("flowchart TD")

    def test_paper_concept_template_has_clickable_link(self):
        """The paper-concept starter has a Mermaid click directive to an arXiv URL."""
        result = json.loads(get_diagram_recipes())
        template = result["paper_concept"]["template"]
        assert "flowchart LR" in template
        assert "click " in template
        assert "arxiv.org" in template

    def test_recipes_point_back_to_named_prompts(self):
        """Each recipe references the matching MCP prompt name."""
        result = json.loads(get_diagram_recipes())
        assert result["algorithm_flowchart"]["prompt"] == "algorithm_explainer"
        assert result["paper_concept"]["prompt"] == "paper_concept_diagram"

    def test_recipes_recommend_svg_output(self):
        """SVG is the only output_format that preserves clickable links and crisp arrows."""
        result = json.loads(get_diagram_recipes())
        for name, recipe in result.items():
            assert recipe["output_format"] == "svg", (
                f"{name} should recommend svg to keep links and arrows crisp"
            )

    def test_recipes_target_mermaid_backend(self):
        """Both recipes ship Mermaid bodies; diagram_type should match."""
        result = json.loads(get_diagram_recipes())
        for name, recipe in result.items():
            assert recipe["diagram_type"] == "mermaid", name

    def test_recipes_are_valid_json(self):
        """The resource body should be valid, indented JSON (matches uml://types style)."""
        body = get_diagram_recipes()
        assert isinstance(body, str)
        json.loads(body)
        assert "\n" in body and "  " in body


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
            "uml://capabilities",
            "uml://recipes",
            "uml://server-info",
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


class TestRegisterResourcesWithServer:
    """Tests for register_resources_with_server."""

    def test_registers_each_decorated_resource(self):
        """Each URI in the decorator registry is passed to server.resource(uri)."""
        server = MagicMock()
        server.resource.return_value = lambda f: f

        uris = register_resources_with_server(server)

        assert isinstance(uris, list)
        assert len(uris) > 0
        assert server.resource.call_count == len(uris)
        for uri in uris:
            server.resource.assert_any_call(uri)
