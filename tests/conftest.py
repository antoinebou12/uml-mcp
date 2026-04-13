"""
Pytest configuration and fixtures for UML-MCP tests.

Ensures deterministic test environment (e.g. mock FastMCP when TESTING=1).
"""

import os

# Force mock FastMCP for default test run unless integration tests requested.
# fastmcp_wrapper decides mock vs real at import time; set before any mcp_core import.
if not os.environ.get("USE_REAL_FASTMCP", "").strip():
    os.environ["TESTING"] = "1"
    os.environ["MOCK_FASTMCP"] = "1"

import pytest


@pytest.fixture(autouse=True)
def _testing_env(monkeypatch):
    """Use mock FastMCP and avoid real I/O in tests."""
    monkeypatch.setenv("TESTING", "1")


@pytest.fixture(autouse=True)
def _clear_diagram_render_cache():
    """Isolate diagram LRU cache between tests (avoids mock bleed-through)."""
    from mcp_core.core import diagram_rendering

    diagram_rendering._render_cache.clear()
    yield


@pytest.fixture(autouse=True)
def _enable_diagram_fallback_for_tests(monkeypatch):
    """Match local-desktop defaults: allow Kroki→PlantUML/Mermaid after Kroki fails."""
    from mcp_core.core.config import MCP_SETTINGS

    monkeypatch.setattr(MCP_SETTINGS, "diagram_fallback_enabled", True)


@pytest.fixture
def reset_mcp_server_singleton():
    """Reset the MCP server singleton so create_mcp_server() runs fresh."""
    import mcp_core.core.server as server_module

    old = server_module._mcp_server
    server_module._mcp_server = None
    try:
        yield
    finally:
        server_module._mcp_server = old
