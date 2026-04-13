"""
Unit tests for MCP server configuration.
"""

import os
from pathlib import Path
from unittest.mock import patch

from mcp_core.core.config import DIAGRAM_TYPES, MCP_SETTINGS, DiagramType, MCPSettings


class TestDiagramType:
    """Tests for DiagramType model."""

    def test_diagram_type_required_fields(self):
        """DiagramType requires backend and description."""
        dt = DiagramType(backend="plantuml", description="Class diagram")
        assert dt.backend == "plantuml"
        assert dt.description == "Class diagram"
        assert dt.formats == ["png", "svg"]

    def test_diagram_type_custom_formats(self):
        """DiagramType accepts custom formats."""
        dt = DiagramType(
            backend="plantuml",
            description="Class diagram",
            formats=["svg", "png"],
        )
        assert dt.formats == ["svg", "png"]


class TestMCPSettingsDefaults:
    """Tests for MCPSettings default values."""

    @patch.dict(os.environ, {}, clear=False)
    def test_default_server_name_version_description(self):
        """MCPSettings has expected default server metadata."""
        settings = MCPSettings(diagram_types={})
        assert settings.server_name == "uml_mcp"
        assert settings.display_name == "UML Diagram Generator"
        assert settings.version == "1.3.0"
        assert settings.description == "Generate UML and other diagrams through MCP"

    @patch.dict(os.environ, {}, clear=False)
    def test_default_output_dir_contains_output(self):
        """Default output_dir ends with output."""
        settings = MCPSettings(diagram_types={})
        assert settings.output_dir.endswith("output")
        assert "output" in settings.output_dir

    @patch.dict(os.environ, {}, clear=False)
    def test_output_path_is_path(self):
        """output_path property returns Path."""
        settings = MCPSettings(diagram_types={})
        assert isinstance(settings.output_path, Path)
        assert str(settings.output_path) == settings.output_dir

    @patch.dict(os.environ, {}, clear=False)
    def test_default_kroki_and_plantuml_servers(self):
        """Default Kroki and PlantUML server URLs."""
        settings = MCPSettings(diagram_types={})
        assert settings.kroki_server == "https://kroki.io"
        assert "plantuml" in settings.plantuml_server.lower()
        assert "8080" in settings.plantuml_server

    @patch.dict(os.environ, {}, clear=False)
    def test_default_lists_empty(self):
        """Default tools, prompts, resources are empty lists."""
        settings = MCPSettings(diagram_types={})
        assert settings.tools == []
        assert settings.prompts == []
        assert settings.resources == []


class TestDiagramFallbackEnv:
    """MCP_DIAGRAM_FALLBACK / VERCEL / USE_LOCAL_KROKI interaction."""

    @patch.dict(
        os.environ,
        {"VERCEL": "", "USE_LOCAL_KROKI": "", "MCP_DIAGRAM_FALLBACK": ""},
        clear=False,
    )
    def test_diagram_fallback_enabled_desktop_default(self):
        settings = MCPSettings(diagram_types={})
        assert settings.diagram_fallback_enabled is True

    @patch.dict(
        os.environ,
        {"VERCEL": "1", "MCP_DIAGRAM_FALLBACK": ""},
        clear=False,
    )
    def test_diagram_fallback_disabled_on_vercel(self):
        settings = MCPSettings(diagram_types={})
        assert settings.diagram_fallback_enabled is False

    @patch.dict(
        os.environ,
        {"USE_LOCAL_KROKI": "true", "MCP_DIAGRAM_FALLBACK": ""},
        clear=False,
    )
    def test_diagram_fallback_disabled_with_use_local_kroki(self):
        settings = MCPSettings(diagram_types={})
        assert settings.diagram_fallback_enabled is False

    @patch.dict(
        os.environ,
        {"VERCEL": "1", "MCP_DIAGRAM_FALLBACK": "true"},
        clear=False,
    )
    def test_mcp_diagram_fallback_true_overrides_vercel(self):
        settings = MCPSettings(diagram_types={})
        assert settings.diagram_fallback_enabled is True


class TestMCPSettingsFromEnv:
    """Tests for MCPSettings reading from environment."""

    def test_explicit_output_dir(self):
        """MCPSettings accepts explicit output_dir."""
        settings = MCPSettings(diagram_types={}, output_dir="/custom/output")
        assert settings.output_dir == "/custom/output"

    def test_explicit_kroki_server(self):
        """MCPSettings accepts explicit kroki_server."""
        settings = MCPSettings(diagram_types={}, kroki_server="http://local-kroki:8000")
        assert settings.kroki_server == "http://local-kroki:8000"

    def test_explicit_plantuml_server(self):
        """MCPSettings accepts explicit plantuml_server."""
        settings = MCPSettings(
            diagram_types={},
            plantuml_server="http://local-plantuml:9090",
        )
        assert settings.plantuml_server == "http://local-plantuml:9090"


class TestMCPModuleLevel:
    """Tests for module-level MCP_SETTINGS and DIAGRAM_TYPES."""

    def test_diagram_types_has_expected_keys(self):
        """DIAGRAM_TYPES includes class, sequence, mermaid, etc."""
        assert "class" in DIAGRAM_TYPES
        assert "sequence" in DIAGRAM_TYPES
        assert "mermaid" in DIAGRAM_TYPES
        assert "d2" in DIAGRAM_TYPES
        assert "graphviz" in DIAGRAM_TYPES
        assert "erd" in DIAGRAM_TYPES

    def test_mcp_settings_has_diagram_types(self):
        """MCP_SETTINGS.diagram_types is populated from DIAGRAM_TYPES."""
        assert len(MCP_SETTINGS.diagram_types) > 0
        assert "class" in MCP_SETTINGS.diagram_types
        assert MCP_SETTINGS.diagram_types["class"].backend == "plantuml"
        assert MCP_SETTINGS.diagram_types["mermaid"].backend == "mermaid"

    def test_config_backends_and_formats_match_kroki(self):
        """Every config diagram type has backend in Kroki and formats match LANGUAGE_OUTPUT_SUPPORT."""
        from tools.kroki.kroki import LANGUAGE_OUTPUT_SUPPORT

        for name, config in DIAGRAM_TYPES.items():
            assert config.backend in LANGUAGE_OUTPUT_SUPPORT, (
                f"diagram_type {name} has backend {config.backend} not in LANGUAGE_OUTPUT_SUPPORT"
            )
            expected = LANGUAGE_OUTPUT_SUPPORT[config.backend]
            assert config.formats == expected, (
                f"diagram_type {name} formats {config.formats} != {expected}"
            )
