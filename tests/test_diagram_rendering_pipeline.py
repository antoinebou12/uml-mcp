"""Unit tests for Kroki-first diagram_rendering pipeline (explicit steps)."""

from unittest.mock import MagicMock

import pytest

from mcp_core.core.diagram_rendering import (
    DiagramRenderContext,
    run_diagram_pipeline,
    try_kroki_render,
)


@pytest.fixture
def sample_ctx(tmp_path) -> DiagramRenderContext:
    return DiagramRenderContext(
        diagram_type="class",
        backend_type="plantuml",
        prepared_code="@startuml\nclass A\n@enduml",
        output_format="svg",
        output_dir=str(tmp_path),
        theme=None,
        scale=1.0,
    )


def test_try_kroki_render_success_includes_source(sample_ctx):
    mock_client = MagicMock()
    mock_client.generate_diagram.return_value = {
        "url": "https://kroki.io/plantuml/svg/abc",
        "content": b"<svg>x</svg>",
        "playground": "https://example.com/play",
    }
    out, err = try_kroki_render(sample_ctx, kroki_client=mock_client)
    assert err is None
    assert out is not None
    assert out["source"] == "kroki"
    assert out["url"] == "https://kroki.io/plantuml/svg/abc"
    mock_client.generate_diagram.assert_called_once_with(
        "plantuml", sample_ctx.prepared_code, "svg", timeout=None
    )


def test_try_kroki_render_mermaid_uses_fail_fast_timeout():
    ctx = DiagramRenderContext(
        diagram_type="mermaid",
        backend_type="mermaid",
        prepared_code="graph TD; A-->B;",
        output_format="svg",
        output_dir=None,
        theme=None,
        scale=1.0,
    )
    mock_client = MagicMock()
    mock_client.generate_diagram.return_value = {
        "url": "https://kroki.io/mermaid/svg/x",
        "content": b"<svg/>",
        "playground": None,
    }
    out, err = try_kroki_render(ctx, kroki_client=mock_client)
    assert err is None
    assert out is not None
    kwargs = mock_client.generate_diagram.call_args
    assert kwargs.kwargs.get("timeout") is not None
    assert kwargs.kwargs["timeout"] <= 8.0


def test_try_kroki_render_no_disk_when_output_dir_none(tmp_path):
    ctx = DiagramRenderContext(
        diagram_type="mermaid",
        backend_type="mermaid",
        prepared_code="graph TD; A-->B;",
        output_format="svg",
        output_dir=None,
        theme=None,
        scale=1.0,
    )
    mock_client = MagicMock()
    mock_client.generate_diagram.return_value = {
        "url": "https://kroki.io/mermaid/svg/x",
        "content": b"<svg/>",
        "playground": None,
    }
    out, err = try_kroki_render(ctx, kroki_client=mock_client)
    assert err is None
    assert out is not None
    assert out["local_path"] is None
    assert "content_base64" in out


def test_run_diagram_pipeline_delegates_to_try_kroki_then_fallback(
    sample_ctx, monkeypatch
):
    """When Kroki fails for plantuml, pipeline runs PlantUML fallback."""
    from tools.kroki.kroki import KrokiConnectionError

    mock_client = MagicMock()
    mock_client.generate_diagram.side_effect = KrokiConnectionError("down")

    fallback_result = {
        "code": sample_ctx.prepared_code,
        "url": "http://plantuml/svg/x",
        "playground": "https://plantuml.com/",
        "local_path": None,
        "source": "plantuml_server",
    }

    def fake_fallback(*_a, **_k):
        return fallback_result

    monkeypatch.setattr(
        "mcp_core.core.diagram_rendering._generate_diagram_plantuml_fallback",
        fake_fallback,
    )

    result = run_diagram_pipeline(sample_ctx, kroki_client=mock_client)
    assert result["source"] == "plantuml_server"
    assert result["url"] == "http://plantuml/svg/x"
    assert result["fallback_used"] is True
    assert len(result["attempts"]) == 2
    assert result["attempts"][0]["backend"] == "kroki"
    assert result["attempts"][0]["ok"] is False
    assert result["attempts"][1]["backend"] == "plantuml_server"
    assert result["attempts"][1]["ok"] is True
    assert result["cache_hit"] is False
    assert "render_ms" in result
    assert result.get("mime_type") == "image/svg+xml"
    mock_client.generate_diagram.assert_called_once()


def test_run_diagram_pipeline_kroki_success_has_metadata(sample_ctx):
    mock_client = MagicMock()
    mock_client.generate_diagram.return_value = {
        "url": "https://kroki.io/plantuml/svg/abc",
        "content": b"<svg>x</svg>",
        "playground": "https://example.com/play",
    }
    ctx = DiagramRenderContext(
        diagram_type="class",
        backend_type="plantuml",
        prepared_code="@startuml\nclass A\n@enduml",
        output_format="svg",
        output_dir=None,
        theme=None,
        scale=1.0,
    )
    result = run_diagram_pipeline(ctx, kroki_client=mock_client)
    assert result["source"] == "kroki"
    assert result["fallback_used"] is False
    assert result["attempts"] == [{"backend": "kroki", "ok": True}]
    assert result["cache_hit"] is False
    assert result.get("mime_type") == "image/svg+xml"
