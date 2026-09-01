"""
Tests for MCP server creation and registry wiring.
"""

from unittest.mock import MagicMock, patch

import pytest

from mcp_core.core.config import MCP_SETTINGS
from mcp_core.core.server import create_mcp_server, get_mcp_server, start_server
from mcp_core.server.fastmcp_wrapper import USING_MOCK_FASTMCP


class TestCreateMcpServer:
    """Tests for create_mcp_server() and registry wiring."""

    def test_create_mcp_server_returns_server_with_name(
        self, reset_mcp_server_singleton
    ):
        server = create_mcp_server()
        assert server is not None
        assert server.name == MCP_SETTINGS.server_name

    @pytest.mark.skipif(
        not USING_MOCK_FASTMCP,
        reason="Requires mock FastMCP (unset USE_REAL_FASTMCP for unit tests)",
    )
    def test_create_mcp_server_registers_tools(self, reset_mcp_server_singleton):
        server = create_mcp_server()
        assert hasattr(server, "_tools")
        assert len(server._tools) >= 1
        assert "generate_uml" in server._tools
        assert "validate_uml" in server._tools

    @pytest.mark.skipif(
        not USING_MOCK_FASTMCP,
        reason="Requires mock FastMCP (unset USE_REAL_FASTMCP for unit tests)",
    )
    def test_create_mcp_server_registers_prompts(self, reset_mcp_server_singleton):
        server = create_mcp_server()
        assert hasattr(server, "_prompts")
        assert len(server._prompts) >= 1

    @pytest.mark.skipif(
        not USING_MOCK_FASTMCP,
        reason="Requires mock FastMCP (unset USE_REAL_FASTMCP for unit tests)",
    )
    def test_create_mcp_server_registers_resources(self, reset_mcp_server_singleton):
        server = create_mcp_server()
        assert hasattr(server, "_resources")
        assert len(server._resources) >= 1

    def test_mcp_settings_updated_with_registered_names(
        self, reset_mcp_server_singleton
    ):
        create_mcp_server()
        assert len(MCP_SETTINGS.tools) >= 1
        assert "generate_uml" in MCP_SETTINGS.tools
        assert "validate_uml" in MCP_SETTINGS.tools
        assert len(MCP_SETTINGS.prompts) >= 1
        assert len(MCP_SETTINGS.resources) >= 1

    def test_get_mcp_server_returns_singleton(self, reset_mcp_server_singleton):
        s1 = get_mcp_server()
        s2 = get_mcp_server()
        assert s1 is s2


class TestStartServer:
    """Tests for start_server()."""

    @patch("mcp_core.core.server.get_mcp_server")
    def test_start_server_http_calls_run_http(self, get_mcp_server_mock):
        """start_server(transport='http', ...) calls server.run_http(host=..., port=...)."""
        mock_server = MagicMock()
        get_mcp_server_mock.return_value = mock_server
        start_server(transport="http", host="127.0.0.1", port=9999)
        mock_server.run_http.assert_called_once_with(host="127.0.0.1", port=9999)

    def test_start_server_http_without_host_raises(self):
        """start_server(transport='http', host=None) raises ValueError."""
        with (
            patch("mcp_core.core.server.get_mcp_server", return_value=MagicMock()),
            pytest.raises(ValueError, match="Host and port must be specified"),
        ):
            start_server(transport="http", host=None, port=8000)

    def test_start_server_unsupported_transport_raises(self):
        """start_server(transport='invalid') raises ValueError."""
        with (
            patch("mcp_core.core.server.get_mcp_server", return_value=MagicMock()),
            pytest.raises(ValueError, match="Unsupported transport: invalid"),
        ):
            start_server(transport="invalid")
