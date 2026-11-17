"""
Pytest configuration and fixtures for UML-MCP tests.

Ensures deterministic test environment (e.g. mock FastMCP when TESTING=1).
"""

import os

# Never pick up a developer's uml-mcp.yaml during tests.
os.environ.setdefault("UML_MCP_CONFIG", "none")

# Force mock FastMCP for default test run unless integration tests requested.
# fastmcp_wrapper decides mock vs real at import time; set before any mcp_core import.
if not os.environ.get("USE_REAL_FASTMCP", "").strip():
    os.environ["TESTING"] = "1"
    os.environ["MOCK_FASTMCP"] = "1"

import pytest

pytest_plugins = [
    "tests.fixtures_mcp",
    "tests.fixtures_auth",
    "tests.fixtures_real",
    "tests.fixtures_d3",
]


@pytest.fixture(autouse=True)
def _testing_env(monkeypatch):
    """Use mock FastMCP and avoid real I/O in tests."""
    monkeypatch.setenv("TESTING", "1")


@pytest.fixture(autouse=True)
def _enable_diagram_fallback_for_tests(monkeypatch):
    """Match local-desktop defaults: allow Kroki→PlantUML/Mermaid after Kroki fails."""
    from mcp_core.core.config import MCP_SETTINGS

    monkeypatch.setattr(MCP_SETTINGS, "diagram_fallback_enabled", True)


@pytest.fixture(autouse=True)
def _fresh_kroki_engine_health():
    """The Mermaid circuit breaker is process-global: failures simulated by one test
    must never make the next one skip Kroki."""
    from mcp_core.core.diagram_rendering import MERMAID_ENGINE

    MERMAID_ENGINE.reset()
    yield
    MERMAID_ENGINE.reset()


# GitHub CI installs Chromium and must fail if it is missing; `act` and local
# runs may lack the browser, so those browser tests skip instead.
_BROWSER_OPTIONAL = bool(os.environ.get("ACT")) or not os.environ.get("GITHUB_ACTIONS")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if (
        _BROWSER_OPTIONAL
        and call.excinfo is not None
        and "BrowserType.launch: Executable doesn't exist" in str(call.excinfo.value)
    ):
        report.outcome = "skipped"
        report.longrepr = (str(item.path), item.location[1], "Chromium not installed")


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
