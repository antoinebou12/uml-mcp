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

        with (
            patch("mcp_core.core.utils.get_kroki_client", return_value=mock_client),
            patch("mcp_core.core.diagram_rendering.httpx.get") as mock_get,
        ):
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

    def test_force_fetch_fetches_bytes_when_url_only(self, _restore_url_only):
        mock_client = MagicMock()
        mock_client.generate_diagram.return_value = {
            "content": b"<svg>forced</svg>",
            "url": "https://kroki.example/mermaid/svg/xx",
            "playground": "https://mermaid.live/edit#yy",
        }

        config.MCP_SETTINGS.url_only = True
        ctx = DiagramRenderContext(
            diagram_type="mermaid",
            backend_type="mermaid",
            prepared_code="graph TD; A-->B;",
            output_format="png",
            output_dir=None,
            theme=None,
            scale=1.0,
            force_fetch=True,
        )

        with patch("mcp_core.core.utils.get_kroki_client", return_value=mock_client):
            out = run_diagram_pipeline(ctx)

        mock_client.generate_diagram.assert_called_once()
        mock_client.get_url.assert_not_called()
        assert out.get("content_base64")
        assert out.get("source") == "kroki"

    def test_generate_uml_image_force_fetch_under_url_only(self, _restore_url_only):
        """generate_uml_image must request force_fetch even when MCP_URL_ONLY is on."""
        from mcp_core.tools.diagram_tools import generate_uml_image

        config.MCP_SETTINGS.url_only = True
        with patch(
            "mcp_core.core.diagram_service.generate_diagram"
        ) as mock_generate_diagram:
            mock_generate_diagram.return_value = {
                "code": "graph TD; A-->B;",
                "url": "https://kroki.io/mermaid/png/abc",
                "playground": None,
                "local_path": None,
                "content_base64": "aGVsbG8=",
                "source": "kroki",
                "mime_type": "image/png",
            }
            result = generate_uml_image(
                diagram_type="mermaid",
                code="graph TD; A-->B;",
                output_format="png",
            )
        assert result.get("content_base64") == "aGVsbG8="
        mock_generate_diagram.assert_called_once()
        assert mock_generate_diagram.call_args.kwargs.get("force_fetch") is True
