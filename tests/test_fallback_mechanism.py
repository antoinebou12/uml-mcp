"""
Tests for the diagram generation fallback mechanism.
"""

from unittest.mock import MagicMock, patch

import pytest

from mcp_core.core.utils import generate_diagram
from tools.kroki.kroki import KrokiConnectionError, KrokiHTTPError


@pytest.fixture
def mock_kroki_failure():
    """Mock the Kroki client to simulate failure."""
    mock_client = MagicMock()
    mock_client.generate_diagram.side_effect = KrokiConnectionError(
        "Cannot connect to Kroki"
    )
    with patch("mcp_core.core.utils.get_kroki_client", return_value=mock_client):
        yield mock_client


@pytest.fixture
def mock_plantuml_fallback():
    """Mock the PlantUML fallback to succeed."""
    mock_response = MagicMock()
    mock_response.content = b"<svg>fallback content</svg>"
    mock_response.raise_for_status = MagicMock()

    # Mock httpx at the module level where it's imported
    import httpx

    with patch.object(httpx, "get", return_value=mock_response):
        yield mock_response


@pytest.fixture
def mock_mermaid_fallback():
    """Mock the Mermaid.ink fallback to succeed."""
    mock_response = MagicMock()
    mock_response.content = b"<svg>mermaid fallback content</svg>"
    mock_response.raise_for_status = MagicMock()

    mock_urls = MagicMock()
    mock_urls.image_url = "https://mermaid.ink/svg/test"
    mock_urls.edit_url = "https://mermaid.live/edit#test"

    # Mock httpx at the module level and mermaid urls
    import httpx

    with (
        patch.object(httpx, "get", return_value=mock_response),
        patch("tools.kroki.mermaid.generate_mermaid_urls", return_value=mock_urls),
    ):
        yield mock_response


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
            "mcp_core.core.utils._generate_diagram_plantuml_fallback"
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

        # Verify Kroki was attempted
        mock_client.generate_diagram.assert_called_once()
