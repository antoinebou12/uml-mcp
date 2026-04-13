"""
Unit tests for the Kroki-first diagram rendering pipeline (mcp_core.core.diagram_rendering).
"""

from typing import Optional
from unittest.mock import MagicMock, patch

from mcp_core.core.diagram_rendering import (
    DiagramRenderContext,
    prepare_diagram_code,
    run_diagram_pipeline,
    run_fallback_if_needed,
    try_kroki_render,
)
from tools.kroki.kroki import KrokiConnectionError


def _ctx(
    diagram_type: str = "class",
    backend_type: str = "plantuml",
    prepared_code: str = "@startuml\nclass A\n@enduml",
    output_format: str = "svg",
    output_dir: Optional[str] = None,
    theme: Optional[str] = None,
    scale: float = 1.0,
) -> DiagramRenderContext:
    return DiagramRenderContext(
        diagram_type=diagram_type,
        backend_type=backend_type,
        prepared_code=prepared_code,
        output_format=output_format,
        output_dir=output_dir,
        theme=theme,
        scale=scale,
    )


def test_prepare_diagram_code_plantuml_wraps_and_theme():
    raw = "class Foo\n"
    out = prepare_diagram_code(raw, "plantuml", "cerulean")
    assert "@startuml" in out
    assert "@enduml" in out
    assert "!theme cerulean" in out


def test_prepare_diagram_code_mermaid_strip_only():
    out = prepare_diagram_code("  graph TD; A-->B;  ", "mermaid", None)
    assert out == "graph TD; A-->B;"


def test_try_kroki_render_success():
    mock_client = MagicMock()
    mock_client.generate_diagram.return_value = {
        "url": "https://kroki.io/plantuml/svg/x",
        "content": b"<svg/>",
        "playground": "https://p.example",
    }
    result, err = try_kroki_render(_ctx(), kroki_client=mock_client)
    assert err is None
    assert result is not None
    assert result["source"] == "kroki"
    assert result["url"] == "https://kroki.io/plantuml/svg/x"
    assert "content_base64" in result


def test_try_kroki_render_failure_returns_error():
    mock_client = MagicMock()
    mock_client.generate_diagram.side_effect = KrokiConnectionError("down")
    result, err = try_kroki_render(_ctx(), kroki_client=mock_client)
    assert result is None
    assert err is not None


def test_run_diagram_pipeline_kroki_success():
    mock_client = MagicMock()
    mock_client.generate_diagram.return_value = {
        "url": "https://kroki.io/plantuml/svg/x",
        "content": b"<svg/>",
        "playground": None,
    }
    out = run_diagram_pipeline(_ctx(), kroki_client=mock_client)
    assert out.get("source") == "kroki"
    assert "error" not in out
    assert out.get("fallback_used") is False
    assert out.get("attempts") == [{"backend": "kroki", "ok": True}]


def test_run_diagram_pipeline_plantuml_fallback_after_kroki_fails(tmp_path):
    mock_client = MagicMock()
    mock_client.generate_diagram.side_effect = KrokiConnectionError("down")

    mock_response = MagicMock()
    mock_response.content = b"<svg>fb</svg>"
    mock_response.raise_for_status = MagicMock()

    import httpx

    with patch.object(httpx, "get", return_value=mock_response):
        out = run_diagram_pipeline(
            _ctx(output_dir=str(tmp_path)),
            kroki_client=mock_client,
        )

    assert out.get("source") == "plantuml_server"
    assert out.get("url")
    assert "error" not in out
    assert out.get("fallback_used") is True


def test_run_diagram_pipeline_mermaid_fallback_after_kroki_fails(tmp_path):
    mock_client = MagicMock()
    mock_client.generate_diagram.side_effect = KrokiConnectionError("down")

    mock_response = MagicMock()
    mock_response.content = b"<svg>m</svg>"
    mock_response.raise_for_status = MagicMock()

    mock_urls = MagicMock()
    mock_urls.image_url = "https://mermaid.ink/svg/z"
    mock_urls.edit_url = "https://mermaid.live/edit#z"

    import httpx

    with (
        patch.object(httpx, "get", return_value=mock_response),
        patch(
            "tools.kroki.mermaid.generate_mermaid_urls",
            return_value=mock_urls,
        ),
    ):
        out = run_diagram_pipeline(
            _ctx(
                diagram_type="mermaid",
                backend_type="mermaid",
                prepared_code="graph TD; A-->B;",
                output_dir=str(tmp_path),
            ),
            kroki_client=mock_client,
        )

    assert out.get("source") == "mermaid_ink"
    assert "mermaid.ink" in (out.get("url") or "")
    assert "error" not in out
    assert out.get("fallback_used") is True


def test_run_fallback_if_needed_no_fallback_aggregates_message():
    kroki_err = KrokiConnectionError("primary down")
    out = run_fallback_if_needed(
        _ctx(diagram_type="d2", backend_type="d2", prepared_code="x -> y"),
        kroki_err,
    )
    assert "error" in out
    assert "Primary (Kroki) failed" in out["error"]
    assert "No fallback available" in out["error"]
    assert out.get("fallback_used") is False
    assert out.get("attempts")


def test_run_fallback_plantuml_and_kroki_message_on_double_failure():
    """When Kroki fails and PlantUML fallback raises, error combines both."""
    kroki_err = KrokiConnectionError("kroki down")
    with patch(
        "mcp_core.core.diagram_rendering._generate_diagram_plantuml_fallback",
        side_effect=RuntimeError("plantuml boom"),
    ):
        out = run_fallback_if_needed(_ctx(), kroki_err)
    assert "error" in out
    assert "Primary (Kroki) failed" in out["error"]
    assert "plantuml boom" in out["error"]


def test_run_diagram_pipeline_skips_fallback_when_disabled(tmp_path, monkeypatch):
    """When diagram_fallback_enabled is False, Kroki failure does not call fallbacks."""
    from mcp_core.core.config import MCP_SETTINGS

    monkeypatch.setattr(MCP_SETTINGS, "diagram_fallback_enabled", False)
    mock_client = MagicMock()
    mock_client.generate_diagram.side_effect = KrokiConnectionError("down")

    with patch(
        "mcp_core.core.diagram_rendering._generate_diagram_plantuml_fallback"
    ) as mock_fb:
        out = run_diagram_pipeline(
            _ctx(output_dir=str(tmp_path)),
            kroki_client=mock_client,
        )

    mock_fb.assert_not_called()
    assert "error" in out
    assert "Diagram fallback is disabled" in out["error"]
    assert out.get("fallback_used") is False
    assert out.get("attempts")
    assert out["attempts"][0]["backend"] == "kroki"
    assert out["attempts"][0]["ok"] is False
