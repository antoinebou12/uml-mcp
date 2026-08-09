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


def test_cache_policy_uses_fastmcp4_server_level_api():
    from mcp_core.core.server import get_mcp_cache_policy

    policy = get_mcp_cache_policy()
    assert policy == {"cache_ttl": 300, "cache_scope": "public"}


def test_create_server_passes_supported_cache_kwargs(monkeypatch):
    """Guard against reintroducing the removed ``cache_hints=`` constructor kwarg."""
    import mcp_core.core.server as server_module
    import mcp_core.server.fastmcp_wrapper as wrapper

    captured: dict[str, object] = {}

    class FakeFastMCP:
        def __init__(self, name: str, **kwargs):
            captured["name"] = name
            captured.update(kwargs)

        def tool(self, *args, **kwargs):
            return lambda func: func

        def resource(self, *args, **kwargs):
            return lambda func: func

        def prompt(self, *args, **kwargs):
            return lambda func: func

    monkeypatch.setattr(wrapper, "FastMCP", FakeFastMCP)
    server_module.create_mcp_server()

    assert captured["cache_ttl"] == 300
    assert captured["cache_scope"] == "public"
    assert "cache_hints" not in captured
