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


def test_cache_hints_cover_all_2026_cacheable_server_methods():
    from mcp_core.core.server import get_mcp_cache_hints

    hints = get_mcp_cache_hints()
    assert set(hints) == {
        "tools/list",
        "prompts/list",
        "resources/list",
        "resources/templates/list",
        "resources/read",
        "server/discover",
    }


def test_cache_hints_are_public_and_positive():
    from mcp_core.core.server import get_mcp_cache_hints

    hints = get_mcp_cache_hints()
    for method, hint in hints.items():
        if isinstance(hint, dict):
            ttl_ms = hint["ttl_ms"]
            scope = hint["scope"]
        else:
            ttl_ms = hint.ttl_ms
            scope = hint.scope

        assert ttl_ms > 0, method
        assert scope == "public", method

    read_hint = hints["resources/read"]
    catalog_hint = hints["tools/list"]
    read_ttl = read_hint["ttl_ms"] if isinstance(read_hint, dict) else read_hint.ttl_ms
    catalog_ttl = (
        catalog_hint["ttl_ms"]
        if isinstance(catalog_hint, dict)
        else catalog_hint.ttl_ms
    )
    assert read_ttl < catalog_ttl
