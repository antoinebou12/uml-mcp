"""
Integration-style unit tests for MCP server bootstrap.

When pytest runs, the FastMCP wrapper uses the mock implementation (pytest in sys.modules),
so create_mcp_server() returns a mock server with _tools, _prompts, _resources populated.
"""

import os

import pytest

# Ensure mock FastMCP is used (TESTING or pytest already set in test env)
os.environ.setdefault("TESTING", "true")

from mcp_core.server.fastmcp_wrapper import USING_MOCK_FASTMCP  # noqa: E402

from mcp_core.core.server import create_mcp_server  # noqa: E402

pytestmark = pytest.mark.skipif(
    not USING_MOCK_FASTMCP,
    reason="Requires mock FastMCP (unset USE_REAL_FASTMCP for unit tests)",
)

# Expected tool names from register_diagram_tools (single diagram tool)
EXPECTED_TOOLS = [
    "list_diagram_types",
    "generate_uml_batch",
    "generate_uml",
    "validate_uml",
]

# Expected resource URIs from register_diagram_resources
EXPECTED_RESOURCES = [
    "uml://types",
    "uml://templates",
    "uml://examples",
    "uml://formats",
    "uml://server-info",
    "uml://workflow",
]

# Expected prompt names from register_diagram_prompts
EXPECTED_PROMPTS = [
    "uml_diagram",
    "uml_diagram_with_thinking",
    "class_diagram",
    "sequence_diagram",
    "activity_diagram",
    "usecase_diagram",
    "mermaid_sequence_api",
    "mermaid_gantt",
    "bpmn_process_guide",
    "c4_model",
    "wireviz_harness",
    "bpmn_executable_process",
    "convert_class_to_mermaid",
]


class TestServerBootstrap:
    """Tests that server creation wires tools, resources, and prompts correctly."""

    def test_create_mcp_server_returns_server_with_name(
        self, reset_mcp_server_singleton
    ):
        """create_mcp_server returns a server instance with the configured name."""
        server = create_mcp_server()
        assert server is not None
        assert hasattr(server, "name")
        assert server.name == "uml_mcp"

    def test_server_has_tools_registered(self, reset_mcp_server_singleton):
        """Server _tools dict contains generate_uml and validate_uml."""
        server = create_mcp_server()
        assert hasattr(server, "_tools")
        tools = server._tools
        for name in EXPECTED_TOOLS:
            assert name in tools, f"Tool {name} should be registered"
        assert len(tools) >= len(EXPECTED_TOOLS)

    def test_server_has_resources_registered(self, reset_mcp_server_singleton):
        """Server _resources dict contains all expected resource URIs."""
        server = create_mcp_server()
        assert hasattr(server, "_resources")
        resources = server._resources
        for uri in EXPECTED_RESOURCES:
            assert uri in resources, f"Resource {uri} should be registered"
        assert len(resources) >= len(EXPECTED_RESOURCES)

    def test_server_has_prompts_registered(self, reset_mcp_server_singleton):
        """Server _prompts dict contains all expected prompt names."""
        server = create_mcp_server()
        assert hasattr(server, "_prompts")
        prompts = server._prompts
        for name in EXPECTED_PROMPTS:
            assert name in prompts, f"Prompt {name} should be registered"
        assert len(prompts) >= len(EXPECTED_PROMPTS)

    def test_registered_tools_are_callable(self, reset_mcp_server_singleton):
        """Each registered tool is a callable (function)."""
        server = create_mcp_server()
        for name, func in server._tools.items():
            assert callable(func), f"Tool {name} should be callable"

    def test_registered_resources_are_callable(self, reset_mcp_server_singleton):
        """Each registered resource handler is callable."""
        server = create_mcp_server()
        for uri, func in server._resources.items():
            assert callable(func), f"Resource {uri} handler should be callable"

    def test_registered_prompts_are_callable(self, reset_mcp_server_singleton):
        """Each registered prompt handler is callable."""
        server = create_mcp_server()
        for name, func in server._prompts.items():
            assert callable(func), f"Prompt {name} handler should be callable"
