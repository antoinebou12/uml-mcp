"""
Tests for MCP_URL_ONLY / url_only: no Kroki image fetch, no content_base64.
"""

import os
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
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


KROKI_MERMAID_URL = "https://kroki.example/mermaid/svg/xx"
GET_PATCH = "mcp_core.core.diagram_rendering.httpx.get"


@pytest.fixture
def _mermaid_url_only():
    """URL-only mode with the diagram fallback on (the Vercel defaults)."""
    settings = config.MCP_SETTINGS
    saved = (settings.url_only, settings.diagram_fallback_enabled)
    settings.url_only = True
    settings.diagram_fallback_enabled = True
    yield settings
    settings.url_only, settings.diagram_fallback_enabled = saved


def _mermaid_ctx(**overrides: Any) -> DiagramRenderContext:
    fields: dict[str, Any] = {
        "diagram_type": "mermaid",
        "backend_type": "mermaid",
        "prepared_code": "graph TD; A-->B;",
        "output_format": "svg",
        "output_dir": None,
        "theme": None,
        "scale": 1.0,
        **overrides,
    }
    return DiagramRenderContext(**fields)


def _kroki_client() -> MagicMock:
    client = MagicMock()
    client.get_url.return_value = KROKI_MERMAID_URL
    client.get_playground_url.return_value = "https://mermaid.live/edit#yy"
    return client


def _http_response(status: int) -> httpx.Response:
    return httpx.Response(
        status,
        request=httpx.Request("GET", KROKI_MERMAID_URL),
        content=b"<svg/>" if status < 400 else b"Error",
    )


class TestUrlOnlyMermaidLinkVerification:
    """URL-only mode used to return the Kroki link without ever contacting Kroki, so a
    Mermaid link could be dead (public Kroki's Mermaid renderer 500s and hangs) while the
    tool reported success. The link is now verified and falls back to mermaid.ink."""

    def _run(self, ctx, get_side_effect=None, get_return=None, client=None):
        client = client or _kroki_client()
        with (
            patch("mcp_core.core.utils.get_kroki_client", return_value=client),
            patch(
                GET_PATCH, side_effect=get_side_effect, return_value=get_return
            ) as get,
        ):
            return run_diagram_pipeline(ctx), get, client

    def test_healthy_kroki_link_is_returned_after_one_check(self, _mermaid_url_only):
        out, get, client = self._run(_mermaid_ctx(), get_return=_http_response(200))

        get.assert_called_once()
        assert get.call_args.args[0] == KROKI_MERMAID_URL
        assert get.call_args.kwargs["timeout"] <= 8.0
        client.generate_diagram.assert_not_called()
        assert out["url"] == KROKI_MERMAID_URL
        assert out["source"] == "kroki"
        assert out["fallback_used"] is False
        assert "content_base64" not in out

    def test_http_500_falls_back_to_a_working_mermaid_ink_link(self, _mermaid_url_only):
        out, get, _ = self._run(_mermaid_ctx(), get_return=_http_response(500))

        assert out["source"] == "mermaid_ink"
        assert out["url"].startswith("https://mermaid.ink/svg/")
        assert out["fallback_used"] is True
        kroki_attempt, ink_attempt = out["attempts"]
        assert kroki_attempt["backend"] == "kroki" and kroki_attempt["ok"] is False
        assert "500" in kroki_attempt["error_summary"]
        assert ink_attempt == {"backend": "mermaid_ink", "ok": True}
        # Still URL-only: the fallback link is returned, not fetched or inlined.
        get.assert_called_once()
        assert "content_base64" not in out

    def test_timeout_falls_back_to_mermaid_ink(self, _mermaid_url_only):
        out, _, _ = self._run(_mermaid_ctx(), get_side_effect=httpx.ReadTimeout("slow"))

        assert out["source"] == "mermaid_ink"
        assert out["fallback_used"] is True
        assert "timed out" in out["attempts"][0]["error_summary"]

    def test_connection_error_falls_back_to_mermaid_ink(self, _mermaid_url_only):
        out, _, _ = self._run(
            _mermaid_ctx(), get_side_effect=httpx.ConnectError("refused")
        )

        assert out["source"] == "mermaid_ink"
        assert out["url"].startswith("https://mermaid.ink/svg/")
        assert out["attempts"][0]["ok"] is False

    def test_png_links_fall_back_to_the_png_endpoint(self, _mermaid_url_only):
        out, _, _ = self._run(
            _mermaid_ctx(output_format="png"), get_return=_http_response(500)
        )

        assert out["source"] == "mermaid_ink"
        assert out["url"].startswith("https://mermaid.ink/img/")

    def test_no_check_when_fallback_is_disabled(self, _mermaid_url_only):
        _mermaid_url_only.diagram_fallback_enabled = False
        out, get, _ = self._run(_mermaid_ctx(), get_return=_http_response(500))

        get.assert_not_called()  # nothing to fall back to, so keep the old behaviour
        assert out["url"] == KROKI_MERMAID_URL
        assert out["source"] == "kroki"

    def test_other_backends_are_not_checked(self, _mermaid_url_only):
        ctx = _mermaid_ctx(
            diagram_type="class",
            backend_type="plantuml",
            prepared_code="@startuml\nclass A\n@enduml",
        )
        out, get, _ = self._run(ctx, get_return=_http_response(500))

        get.assert_not_called()
        assert out["source"] == "kroki"

    def test_force_fetch_path_is_unchanged(self, _mermaid_url_only):
        client = _kroki_client()
        client.generate_diagram.return_value = {
            "content": b"<svg>forced</svg>",
            "url": KROKI_MERMAID_URL,
            "playground": None,
        }
        out, get, client = self._run(
            _mermaid_ctx(force_fetch=True),
            get_return=_http_response(500),
            client=client,
        )

        get.assert_not_called()
        client.get_url.assert_not_called()
        assert out["source"] == "kroki"
        assert out.get("content_base64")
