"""Shared pytest fixtures for MCP, HTTP, Kroki, and FastAPI tests."""

import json
from unittest.mock import MagicMock, mock_open, patch

import httpx
import pytest

from tools.kroki.kroki import KrokiConnectionError


@pytest.fixture
def mock_mcp_server():
    """Mock MCP server with .tool registration."""
    server = MagicMock()
    server.tool = MagicMock()
    return server


@pytest.fixture
def mock_generate_diagram():
    """Patch app.generate_diagram with a default success payload."""
    with patch("app.generate_diagram") as mock_func:
        mock_func.return_value = {
            "code": "@startuml\nclass Test\n@enduml",
            "url": "https://kroki.io/plantuml/svg/test_url",
            "playground": "https://playground.example.com",
            "local_path": "/tmp/diagrams/test.svg",
        }
        yield mock_func


@pytest.fixture
def mock_plugin_manifest():
    """Mock the plugin manifest file read for /.well-known/ai-plugin.json."""
    manifest_content = {
        "schema_version": "v1",
        "name_for_human": "UML Diagram Generator",
        "description_for_human": "Generate UML diagrams from text",
        "auth": {"type": "none"},
        "api": {"type": "openapi", "url": "https://example.com/openapi.json"},
        "logo_url": "https://example.com/logo.png",
    }

    with patch("builtins.open", mock_open(read_data=json.dumps(manifest_content))):
        yield


@pytest.fixture
def mock_httpx_client():
    """Mock sync httpx.Client for Kroki tests."""
    with patch("httpx.Client") as mock_client:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"<svg>test content</svg>"
        mock_response.raise_for_status = MagicMock()

        client_instance = mock_client.return_value
        client_instance.get.return_value = mock_response

        yield client_instance


@pytest.fixture
def mock_kroki_failure():
    """Mock the Kroki client to simulate connection failure."""
    mock_client = MagicMock()
    mock_client.generate_diagram.side_effect = KrokiConnectionError("Cannot connect to Kroki")
    with patch("mcp_core.core.utils.get_kroki_client", return_value=mock_client):
        yield mock_client


@pytest.fixture
def mock_plantuml_fallback():
    """Mock httpx.get for PlantUML fallback success."""
    mock_response = MagicMock()
    mock_response.content = b"<svg>fallback content</svg>"
    mock_response.raise_for_status = MagicMock()

    with patch.object(httpx, "get", return_value=mock_response):
        yield mock_response


@pytest.fixture
def mock_mermaid_fallback():
    """Mock httpx.get and mermaid URL helpers for Mermaid.ink fallback success."""
    mock_response = MagicMock()
    mock_response.content = b"<svg>mermaid fallback content</svg>"
    mock_response.raise_for_status = MagicMock()

    mock_urls = MagicMock()
    mock_urls.image_url = "https://mermaid.ink/svg/test"
    mock_urls.edit_url = "https://mermaid.live/edit#test"

    with (
        patch.object(httpx, "get", return_value=mock_response),
        patch("tools.kroki.mermaid.generate_mermaid_urls", return_value=mock_urls),
    ):
        yield mock_response
