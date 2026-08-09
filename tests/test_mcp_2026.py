"""Regression tests for the MCP 2026-07-28 migration surface."""

import importlib
import os


def test_http_defaults_to_stateless(monkeypatch):
    monkeypatch.delenv("FASTMCP_STATELESS_HTTP", raising=False)

    import mcp_core.core.server as server_module

    importlib.reload(server_module)
    assert os.environ["FASTMCP_STATELESS_HTTP"] == "true"


def test_operator_can_override_stateless_default(monkeypatch):
    monkeypatch.setenv("FASTMCP_STATELESS_HTTP", "false")

    import mcp_core.core.server as server_module

    importlib.reload(server_module)
    assert os.environ["FASTMCP_STATELESS_HTTP"] == "false"


def test_batch_task_is_advertised_as_task_capable():
    # Import registers diagram tools in the local decorator registry.
    from mcp_core.tools import diagram_tools  # noqa: F401
    from mcp_core.tools.tool_decorator import get_tool_registry

    registry = get_tool_registry()
    assert "generate_uml_batch_task" in registry
    assert registry["generate_uml_batch_task"]["task"] is True
