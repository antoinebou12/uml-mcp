"""
Unit tests for MCP tool decorator and registration.
"""

from unittest.mock import MagicMock

# Import diagram_tools so tools are registered in the global registry
from mcp_core.tools import diagram_tools  # noqa: F401
from mcp_core.tools.tool_decorator import (
    clear_tool_registry,
    get_tool_categories,
    get_tool_registry,
    mcp_tool,
    register_tools_with_server,
)


class TestGetToolRegistry:
    """Tests for get_tool_registry after diagram_tools is loaded."""

    def test_registry_contains_expected_tools(self):
        """Registry includes list, batch, generate, inline-image, validate."""
        registry = get_tool_registry()
        assert "list_diagram_types" in registry
        assert "generate_uml_batch" in registry
        assert "generate_uml" in registry
        assert "generate_uml_image" in registry
        assert "validate_uml" in registry
        assert len(registry) == 5

    def test_registry_tool_has_metadata(self):
        """Each registry entry has function, name, description, category, parameters."""
        registry = get_tool_registry()
        for tool_name, info in registry.items():
            assert "function" in info
            assert "name" in info
            assert info["name"] == tool_name
            assert "description" in info
            assert "category" in info
            assert "parameters" in info
            assert callable(info["function"])


class TestGetToolCategories:
    """Tests for get_tool_categories."""

    def test_categories_contain_expected_groups(self):
        """Categories include uml (single diagram tool)."""
        categories = get_tool_categories()
        assert "uml" in categories

    def test_uml_category_contains_generate_uml(self):
        """UML category lists all diagram tools."""
        categories = get_tool_categories()
        uml_tools = categories.get("uml", [])
        assert "generate_uml" in uml_tools
        assert "validate_uml" in uml_tools
        assert len(uml_tools) == 5


class TestMcpToolParameterExtraction:
    """Tests for mcp_tool parameter metadata extraction."""

    def test_generate_uml_parameters_in_registry(self):
        """generate_uml has diagram_type, code, output_dir with correct required/default."""
        registry = get_tool_registry()
        assert "generate_uml" in registry
        params = registry["generate_uml"]["parameters"]
        assert "diagram_type" in params
        assert "code" in params
        assert "output_dir" in params
        assert params["diagram_type"]["required"] is True
        assert params["code"]["required"] is True
        assert params["output_dir"]["required"] is False
        assert params["output_dir"]["default"] is None

    def test_mcp_tool_stores_required_and_optional(self):
        """Decorated function with mixed params gets correct required/default in registry."""
        # Use a clean registry for this test to avoid side effects on other tests
        from mcp_core.tools.tool_decorator import _registered_tools

        @mcp_tool(description="Test tool for param extraction")
        def test_tool(a: str, b: int = 0) -> str:
            """Docstring."""
            return f"{a}_{b}"

        try:
            registry = get_tool_registry()
            assert "test_tool" in registry
            info = registry["test_tool"]
            assert info["description"] == "Test tool for param extraction"
            params = info["parameters"]
            assert params["a"]["required"] is True
            assert params["b"]["required"] is False
            assert params["b"]["default"] == 0
        finally:
            _registered_tools.pop("test_tool", None)


class TestRegisterToolsWithServer:
    """Tests for register_tools_with_server."""

    def test_server_tool_called_for_each_registered_tool(self):
        """register_tools_with_server calls server.tool for each tool."""
        server = MagicMock()
        # server.tool(name=..., description=...) returns a decorator that we call with func

        def fake_decorator(func):
            return func

        server.tool.return_value = fake_decorator

        registered = register_tools_with_server(server)

        assert len(registered) == len(get_tool_registry())
        assert server.tool.call_count == len(registered)
        # Each call should be with name= and description=
        for call in server.tool.call_args_list:
            kwargs = call[1]
            assert "name" in kwargs
            assert "description" in kwargs

    def test_returns_list_of_tool_names(self):
        """register_tools_with_server returns list of tool names."""
        server = MagicMock()
        server.tool.return_value = lambda f: f

        result = register_tools_with_server(server)

        assert isinstance(result, list)
        assert "generate_uml" in result
        assert "validate_uml" in result
        assert "generate_uml_image" in result
        assert len(result) == 5

    def test_register_tools_typeerror_fallback_chain(self):
        """When server.tool rejects kwargs styles, fall back to bare tool(func)."""
        server = MagicMock()
        call_state = {"n": 0}

        def tool_side_effect(*args, **kwargs):
            call_state["n"] += 1
            if call_state["n"] % 4 in (1, 2, 3):
                raise TypeError("unsupported signature")
            return lambda f: f

        server.tool.side_effect = tool_side_effect

        registered = register_tools_with_server(server)

        assert len(registered) == len(get_tool_registry())
        assert call_state["n"] == 4 * len(registered)


class TestClearToolRegistry:
    """Tests for clear_tool_registry (isolation helper)."""

    def test_clear_tool_registry_empties_registry(self):
        """clear_tool_registry removes all entries (used for test isolation)."""
        from mcp_core.tools.tool_decorator import _registered_tools

        saved = dict(_registered_tools)
        try:
            clear_tool_registry()
            assert len(_registered_tools) == 0
        finally:
            _registered_tools.clear()
            _registered_tools.update(saved)


class TestSummarizeToolResult:
    def test_render_summary_includes_markdown_image(self):
        from mcp_core.tools.tool_decorator import _summarize_tool_result

        text = _summarize_tool_result(
            "generate_uml",
            {
                "diagram_type": "mermaid",
                "source": "mermaid_ink",
                "output_format": "svg",
                "render_ms": 12.5,
                "cache_hit": False,
                "url": "https://mermaid.ink/svg/example",
                "playground": "https://mermaid.live/edit#example",
            },
        )
        assert "![diagram](https://mermaid.ink/svg/example)" in text
        assert "URL: https://mermaid.ink/svg/example" in text
        assert "Playground: https://mermaid.live/edit#example" in text

    def test_render_summary_omits_missing_playground(self):
        from mcp_core.tools.tool_decorator import _summarize_tool_result

        text = _summarize_tool_result(
            "generate_uml",
            {
                "diagram_type": "mermaid",
                "source": "kroki",
                "output_format": "svg",
                "url": "https://kroki.io/mermaid/svg/x",
            },
        )
        assert "Playground:" not in text
