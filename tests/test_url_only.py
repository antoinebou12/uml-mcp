"""
Tests for MCP_URL_ONLY / url_only: no Kroki image fetch, no content_base64.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from mcp_core.core import config
from mcp_core.core.diagram_rendering import DiagramRenderContext, run_diagram_pipeline


@pytest.fixture
def _restore_url_only():
    original = config.MCP_SETTINGS.url_only
    yield
    config.MCP_SETTINGS.url_only = original


class TestUrlOnlyMode:
    def test_url_only_skips_generate_diagram_and_omits_base64(self, _restore_url_only):
        mock_client = MagicMock()
        mock_client.get_url.return_value = "https://kroki.example/plantuml/svg/xx"
        mock_client.get_playground_url.return_value = (
            "https://www.plantuml.com/plantuml/uml/yy"
        )

        config.MCP_SETTINGS.url_only = True
        ctx = DiagramRenderContext(
            diagram_type="class",
            backend_type="plantuml",
            prepared_code="@startuml\nclass A\n@enduml",
            output_format="svg",
            output_dir=None,
            theme=None,
            scale=1.0,
        )

        with patch("mcp_core.core.utils.get_kroki_client", return_value=mock_client):
            out = run_diagram_pipeline(ctx)

        mock_client.generate_diagram.assert_not_called()
        mock_client.get_url.assert_called_once()
        assert out.get("url") == "https://kroki.example/plantuml/svg/xx"
        assert "content_base64" not in out
        assert out.get("local_path") in (None, "")

    def test_url_only_plantuml_fallback_no_httpx_get(self, _restore_url_only):
        mock_client = MagicMock()
        mock_client.get_url.side_effect = RuntimeError("Kroki unavailable")

        config.MCP_SETTINGS.url_only = True
        ctx = DiagramRenderContext(
            diagram_type="class",
            backend_type="plantuml",
            prepared_code="@startuml\nclass A\n@enduml",
            output_format="svg",
            output_dir=None,
            theme=None,
            scale=1.0,
        )

        with patch("mcp_core.core.utils.get_kroki_client", return_value=mock_client):
            with patch("mcp_core.core.diagram_rendering.httpx.get") as mock_get:
                out = run_diagram_pipeline(ctx)

        mock_get.assert_not_called()
        assert out.get("source") == "plantuml_server"
        assert out.get("url")
        assert "content_base64" not in out

    def test_url_only_default_true_when_vercel_unless_disabled(self):
        from mcp_core.core.config import DIAGRAM_TYPES, MCPSettings

        with patch.dict(os.environ, {"VERCEL": "1", "MCP_URL_ONLY": ""}):
            s = MCPSettings(diagram_types=DIAGRAM_TYPES)
            assert s.url_only is True

        with patch.dict(os.environ, {"VERCEL": "1", "MCP_URL_ONLY": "false"}):
            s = MCPSettings(diagram_types=DIAGRAM_TYPES)
            assert s.url_only is False
