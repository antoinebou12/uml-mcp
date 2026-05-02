"""
Tests for FastMCP wrapper (mock) request routing.
"""

from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

from mcp_core.server.fastmcp_wrapper import FastMCP, USING_MOCK_FASTMCP

pytestmark = pytest.mark.skipif(
    not USING_MOCK_FASTMCP,
    reason="Requires mock FastMCP (unset USE_REAL_FASTMCP for unit tests)",
)


class TestFastMcpMockRouting:
    """Test mock FastMCP _handle_request routing."""

    @pytest.fixture
    def server(self):
        s = FastMCP("test-server")
        m = cast(Any, s)
        m._tools["echo"] = lambda msg: {"echo": msg}
        m._prompts["greet"] = lambda name: f"Hello, {name}"
        m._resources["test://x"] = lambda: {"data": "x"}
        return s

    def test_handle_request_tool(self, server):
        req = {"type": "tool", "tool": "echo", "args": {"msg": "hi"}}
        out = server._handle_request(req)
        assert "error" not in out
        assert out.get("result") == {"echo": "hi"}

    def test_handle_request_unknown_tool(self, server):
        req = {"type": "tool", "tool": "missing", "args": {}}
        out = server._handle_request(req)
        assert "error" in out
        assert "Unknown tool" in out["error"]

    def test_handle_request_prompt(self, server):
        req = {"type": "prompt", "prompt": "greet", "args": {"name": "World"}}
        out = server._handle_request(req)
        assert "error" not in out
        assert out.get("result") == "Hello, World"

    def test_handle_request_unknown_prompt(self, server):
        req = {"type": "prompt", "prompt": "missing", "args": {}}
        out = server._handle_request(req)
        assert "error" in out
        assert "Unknown prompt" in out["error"]

    def test_handle_request_resource(self, server):
        req = {"type": "resource", "path": "test://x"}
        out = server._handle_request(req)
        assert "error" not in out
        assert out.get("result") == {"data": "x"}

    def test_handle_request_unknown_resource(self, server):
        req = {"type": "resource", "path": "test://missing"}
        out = server._handle_request(req)
        assert "error" in out
        assert "Unknown resource" in out["error"]

    def test_handle_request_missing_type(self, server):
        req = {"tool": "echo", "args": {}}
        out = server._handle_request(req)
        assert "error" in out
        assert "Missing request type" in out["error"]

    def test_handle_request_unknown_type(self, server):
        req = {"type": "other", "x": 1}
        out = server._handle_request(req)
        assert "error" in out
        assert "Unknown request type" in out["error"]

    def test_handle_request_empty_type(self, server):
        """Request with empty type returns error."""
        req = {"type": ""}
        out = server._handle_request(req)
        assert "error" in out
        assert "Unknown request type" in out["error"]

    def test_run_http_calls_run_http(self):
        """run(transport='http', host=..., port=...) calls _run_http."""
        server = FastMCP("test-server")
        with patch.object(server, "_run_http", MagicMock()) as mock_run_http:
            server.run(transport="http", host="0.0.0.0", port=9999)
            mock_run_http.assert_called_once_with("0.0.0.0", 9999)
