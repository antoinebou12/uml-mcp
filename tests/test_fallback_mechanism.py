"""
Tests for the diagram generation fallback mechanism.
"""

from unittest.mock import MagicMock, patch

import pytest

from mcp_core.core.utils import generate_diagram
from tools.kroki.kroki import KrokiHTTPError


def test_fallback_plantuml_success(
    mock_kroki_failure, mock_plantuml_fallback, tmp_path
):
    """Test that PlantUML fallback works when Kroki fails."""
    # Call generate_diagram with test data
    result = generate_diagram(
        diagram_type="class",
        code="@startuml\nclass Test\n@enduml",
        output_format="svg",
        output_dir=str(tmp_path),
    )

    # Verify that we got a result (fallback succeeded)
    assert "url" in result
    assert "local_path" in result
    assert result["url"] is not None
    assert result.get("fallback_used") is True
    assert result.get("attempts")

    # Verify Kroki was attempted first
    mock_kroki_failure.generate_diagram.assert_called_once()


def test_fallback_mermaid_success(mock_kroki_failure, mock_mermaid_fallback, tmp_path):
    """Test that Mermaid.ink fallback works when Kroki fails."""
    # Call generate_diagram with test data
    result = generate_diagram(
        diagram_type="mermaid",
        code="graph TD; A-->B;",
        output_format="svg",
        output_dir=str(tmp_path),
    )

    # Verify that we got a result (fallback succeeded)
    assert "url" in result
    assert "local_path" in result
    assert result["url"] is not None
    assert "mermaid.ink" in result["url"]
    assert result.get("fallback_used") is True

    # Verify Kroki was attempted first
    mock_kroki_failure.generate_diagram.assert_called_once()


def test_fallback_no_fallback_available(mock_kroki_failure, tmp_path):
    """Test that error is returned when no fallback is available."""
    # Call generate_diagram with a diagram type that has no fallback (e.g., D2)
    result = generate_diagram(
        diagram_type="d2",
        code="x -> y",
        output_format="svg",
        output_dir=str(tmp_path),
    )

    # Verify that we got an error
    assert "error" in result
    assert result["error"] is not None
    assert "Primary (Kroki) failed" in result["error"]
    assert result.get("fallback_used") is False
    assert any(a.get("backend") == "none" for a in (result.get("attempts") or []))

    # Verify Kroki was attempted
    mock_kroki_failure.generate_diagram.assert_called_once()


def test_fallback_not_triggered_on_success(tmp_path):
    """Test that fallback is not used when Kroki succeeds."""
    mock_client = MagicMock()
    mock_client.generate_diagram.return_value = {
        "url": "https://kroki.io/plantuml/svg/test_url",
        "content": b"<svg>kroki content</svg>",
        "playground": "https://playground.example.com",
    }

    with (
        patch("mcp_core.core.utils.get_kroki_client", return_value=mock_client),
        patch(
            "mcp_core.core.diagram_rendering._generate_diagram_plantuml_fallback"
        ) as mock_fallback,
    ):
        result = generate_diagram(
            diagram_type="class",
            code="@startuml\nclass Test\n@enduml",
            output_format="svg",
            output_dir=str(tmp_path),
        )

        # Verify Kroki succeeded
        assert result["url"] == "https://kroki.io/plantuml/svg/test_url"
        assert result.get("fallback_used") is False
        assert result.get("attempts") == [{"backend": "kroki", "ok": True}]

        # Verify fallback was NOT called
        mock_fallback.assert_not_called()


def test_kroki_http_error_triggers_fallback(mock_plantuml_fallback, tmp_path):
    """Test that HTTP errors from Kroki trigger fallback."""
    mock_response = MagicMock()
    mock_response.status_code = 503

    mock_client = MagicMock()
    mock_client.generate_diagram.side_effect = KrokiHTTPError(
        mock_response, "Service unavailable"
    )

    with patch("mcp_core.core.utils.get_kroki_client", return_value=mock_client):
        result = generate_diagram(
            diagram_type="class",
            code="@startuml\nclass Test\n@enduml",
            output_format="svg",
            output_dir=str(tmp_path),
        )

        # Verify that we got a result (fallback succeeded)
        assert "url" in result
        assert result["url"] is not None

        assert result.get("fallback_used") is True

        # Verify Kroki was attempted
        mock_client.generate_diagram.assert_called_once()
