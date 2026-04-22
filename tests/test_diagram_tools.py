"""
Unit tests for diagram tool functions
"""

from unittest.mock import MagicMock, patch

from mcp_core.tools.diagram_tools import (
    generate_uml,
    generate_uml_batch,
    list_diagram_types,
    register_diagram_tools,
)


class TestDiagramTools:
    """Test suite for diagram tools functionality"""

    def test_generate_uml_rejects_output_dir_when_read_only(self):
        """MCP_READ_ONLY must reject output_dir at validation time."""
        from mcp_core.core import config

        original = config.MCP_SETTINGS.read_only
        config.MCP_SETTINGS.read_only = True
        try:
            result = generate_uml(
                diagram_type="class",
                code="@startuml\nclass A\n@enduml",
                output_dir="/tmp/out",
            )
            assert "error" in result
            assert (
                "read_only" in result["error"].lower()
                or "mcp_read_only" in result["error"].lower()
            )
        finally:
            config.MCP_SETTINGS.read_only = original

    def test_register_diagram_tools(self, mock_mcp_server):
        """Test that diagram tools are registered correctly (generate_uml and validate_uml)."""
        register_diagram_tools(mock_mcp_server)

        expected_tools = [
            "list_diagram_types",
            "generate_uml_batch",
            "generate_uml",
            "validate_uml",
        ]

        for tool_name in expected_tools:
            matching_calls = [
                c
                for c in mock_mcp_server.tool.call_args_list
                if (c[0] and c[0][0] == tool_name)
                or (c[1] and c[1].get("name") == tool_name)
            ]
            assert len(matching_calls) > 0, f"Tool {tool_name} was not registered"

        assert mock_mcp_server.tool.call_count == len(expected_tools)

    @patch("mcp_core.core.diagram_service.generate_diagram")
    def test_generate_uml_tool_returns_structure(self, mock_generate_diagram):
        """Test that generate_uml tool returns url, code, playground, and optional local_path."""
        mock_generate_diagram.return_value = {
            "code": "@startuml\nclass Test\n@enduml",
            "url": "https://kroki.io/plantuml/svg/abc123",
            "playground": "https://www.plantuml.com/plantuml/uml/xyz",
            "local_path": "/tmp/out/class_123.svg",
        }
        result = generate_uml(
            diagram_type="class",
            code="@startuml\nclass Test\n@enduml",
            output_dir="/tmp/out",
        )
        assert "url" in result
        assert "code" in result
        assert result.get("playground") is not None
        assert result.get("local_path") is not None
        mock_generate_diagram.assert_called_once_with(
            "class", "@startuml\nclass Test\n@enduml", "svg", "/tmp/out", None, 1.0
        )

    @patch("mcp_core.core.diagram_service.generate_diagram")
    def test_generate_uml_unsupported_diagram_type_returns_error(
        self, mock_generate_diagram
    ):
        """generate_uml with unsupported diagram type returns error dict and does not call generate_diagram."""
        result = generate_uml(
            diagram_type="invalid_type",
            code="some code",
        )
        assert "error" in result
        assert "Unsupported diagram type" in result["error"]
        assert "invalid_type" in result["error"]
        mock_generate_diagram.assert_not_called()

    @patch("mcp_core.core.diagram_service.generate_diagram")
    def test_generate_uml_with_different_types(self, mock_generate_diagram):
        """generate_uml accepts all diagram types via diagram_type argument."""
        mock_generate_diagram.return_value = {
            "code": "sample",
            "url": "https://example.com/svg/abc",
            "playground": "https://example.com/playground",
            "local_path": "/tmp/out/diagram.svg",
        }
        for diagram_type in ("sequence", "class", "mermaid", "d2", "bpmn"):
            result = generate_uml(
                diagram_type=diagram_type,
                code="sample code",
                output_dir="/tmp/out",
            )
            assert "url" in result
            assert result["code"] == "sample"
            call_args = mock_generate_diagram.call_args[0]
            assert call_args[0] == diagram_type

    @patch("mcp_core.core.diagram_service.generate_diagram")
    def test_generate_uml_without_output_dir_returns_url_and_base64(
        self, mock_generate_diagram
    ):
        """generate_uml with no output_dir returns url, playground, content_base64; no local_path."""
        mock_generate_diagram.return_value = {
            "code": "graph TD; A-->B;",
            "url": "https://kroki.io/mermaid/svg/abc",
            "playground": "https://mermaid.live/edit#...",
            "local_path": None,
            "content_base64": "PHN2Zz48L3N2Zz4=",
        }
        result = generate_uml(
            diagram_type="mermaid",
            code="graph TD; A-->B;",
        )
        assert "error" not in result
        assert result["url"] == "https://kroki.io/mermaid/svg/abc"
        assert result["playground"] == "https://mermaid.live/edit#..."
        assert result.get("local_path") is None
        assert "content_base64" in result
        mock_generate_diagram.assert_called_once()
        args = mock_generate_diagram.call_args[0]
        assert args[0] == "mermaid"
        assert args[2] == "svg"  # output_format
        assert args[3] is None  # output_dir

    @patch("mcp_core.core.diagram_service.generate_diagram")
    def test_generate_uml_validation_error_unsupported_format_without_output_dir(
        self, mock_generate_diagram
    ):
        """generate_uml with format not supported by type returns validation error."""
        result = generate_uml(
            diagram_type="mermaid",
            code="graph TD; A-->B;",
            output_format="pdf",
        )
        assert "error" in result
        assert (
            "output_format" in result["error"].lower()
            or "validation" in result["error"].lower()
        )
        mock_generate_diagram.assert_not_called()

    @patch("mcp_core.core.diagram_service.generate_diagram")
    def test_generate_uml_accepts_jpeg_for_graphviz(self, mock_generate_diagram):
        """generate_uml accepts output_format jpeg for diagram types that support it (e.g. graphviz)."""
        mock_generate_diagram.return_value = {
            "code": "digraph { A -> B; }",
            "url": "https://kroki.io/graphviz/jpeg/abc",
            "playground": None,
            "local_path": None,
            "content_base64": "/9j/4AAQ=",
        }
        result = generate_uml(
            diagram_type="graphviz",
            code="digraph { A -> B; }",
            output_format="jpeg",
        )
        assert "error" not in result
        mock_generate_diagram.assert_called_once()
        args = mock_generate_diagram.call_args[0]
        assert args[0] == "graphviz"
        assert args[2] == "jpeg"

    def test_list_diagram_types_matches_resource_shape(self):
        """list_diagram_types returns the same keys as uml://types (per-type metadata)."""
        types_map = list_diagram_types()
        assert isinstance(types_map, dict)
        assert "class" in types_map
        assert types_map["class"]["backend"] == "plantuml"
        assert "formats" in types_map["class"]

    @patch("mcp_core.core.diagram_service.generate_diagram")
    def test_generate_uml_batch_two_items(self, mock_generate_diagram):
        """Batch runs each item and returns indexed results."""
        mock_generate_diagram.return_value = {
            "code": "x",
            "url": "https://kroki.io/mermaid/svg/x",
            "playground": None,
            "local_path": None,
        }
        out = generate_uml_batch(
            [
                {"diagram_type": "mermaid", "code": "graph TD; A-->B;"},
                {"diagram_type": "mermaid", "code": "graph TD; C-->D;"},
            ]
        )
        assert "results" in out
        assert len(out["results"]) == 2
        assert out["results"][0]["index"] == 0
        assert "url" in out["results"][0]
        assert mock_generate_diagram.call_count == 2

    def test_generate_uml_batch_empty(self):
        out = generate_uml_batch([])
        assert out.get("error")
        assert out["results"] == []

    def test_generate_uml_batch_invalid_item(self):
        out = generate_uml_batch([{"diagram_type": "not_a_type", "code": "x"}])
        assert len(out["results"]) == 1
        assert "error" in out["results"][0]
