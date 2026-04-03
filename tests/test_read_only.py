"""
Tests for MCP_READ_ONLY mode.

Verifies that when MCP_READ_ONLY=true:
- generate_uml is not registered as a tool
- generate_diagram_url is still registered
- generate_diagram() forces output_dir=None (no file writes)

And when MCP_READ_ONLY is unset, both tools are registered as usual.
"""

import os
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def _reset_tool_registry():
    """Reset the tool decorator registry and re-import diagram_tools to re-populate it."""
    from mcp_core.tools import tool_decorator

    original = dict(tool_decorator._registered_tools)
    yield
    tool_decorator._registered_tools.clear()
    tool_decorator._registered_tools.update(original)


class TestReadOnlyMode:
    """Test suite for MCP_READ_ONLY behaviour."""

    def test_read_only_skips_generate_uml(self, _reset_tool_registry):
        """With MCP_READ_ONLY=true, generate_uml must not appear in registered tools."""
        from mcp_core.tools import tool_decorator
        from mcp_core.core import config

        # Ensure generate_uml is present before we test
        assert "generate_uml" in tool_decorator._registered_tools

        # Temporarily set read_only on the singleton
        original_read_only = config.MCP_SETTINGS.read_only
        config.MCP_SETTINGS.read_only = True
        try:
            server = MagicMock()
            server.tool = MagicMock()

            from mcp_core.tools.diagram_tools import register_diagram_tools

            registered = register_diagram_tools(server)

            assert "generate_uml" not in registered
            assert "generate_diagram_url" in registered
        finally:
            config.MCP_SETTINGS.read_only = original_read_only

    def test_default_registers_both_tools(self, _reset_tool_registry):
        """When MCP_READ_ONLY is unset/false, both tools are registered."""
        from mcp_core.core import config

        original_read_only = config.MCP_SETTINGS.read_only
        config.MCP_SETTINGS.read_only = False
        try:
            server = MagicMock()
            server.tool = MagicMock()

            from mcp_core.tools.diagram_tools import register_diagram_tools

            registered = register_diagram_tools(server)

            assert "generate_uml" in registered
            assert "generate_diagram_url" in registered
        finally:
            config.MCP_SETTINGS.read_only = original_read_only

    def test_read_only_forces_no_file_write(self, tmp_path):
        """In read-only mode, generate_diagram() must not write files even if output_dir is given."""
        from mcp_core.core import config
        from mcp_core.core.utils import generate_diagram, set_diagram_generator

        output_dir = str(tmp_path / "diagrams")

        # Use a fake generator that captures the output_dir it receives
        captured = {}

        def fake_generator(diagram_type, code, output_format, output_dir, theme, scale):
            captured["output_dir"] = output_dir
            return {
                "code": code,
                "url": "https://example.com/diagram.svg",
                "playground": None,
                "local_path": None,
            }

        original_read_only = config.MCP_SETTINGS.read_only
        config.MCP_SETTINGS.read_only = True
        set_diagram_generator(fake_generator)
        try:
            generate_diagram("class", "@startuml\nclass A\n@enduml", "svg", output_dir)
            assert captured["output_dir"] is None, (
                "output_dir should be forced to None in read-only mode"
            )
        finally:
            config.MCP_SETTINGS.read_only = original_read_only
            set_diagram_generator(None)

    def test_config_read_only_from_env(self):
        """MCP_READ_ONLY env var is correctly parsed into MCPSettings.read_only."""
        from mcp_core.core.config import MCPSettings

        for truthy in ("true", "1", "yes", "True", "YES"):
            with patch.dict(os.environ, {"MCP_READ_ONLY": truthy}):
                settings = MCPSettings()
                assert settings.read_only is True, (
                    f"Expected True for MCP_READ_ONLY={truthy!r}"
                )

        for falsy in ("false", "0", "no", ""):
            with patch.dict(os.environ, {"MCP_READ_ONLY": falsy}):
                settings = MCPSettings()
                assert settings.read_only is False, (
                    f"Expected False for MCP_READ_ONLY={falsy!r}"
                )
