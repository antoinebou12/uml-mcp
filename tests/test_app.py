"""
Tests for the FastAPI application.
"""

import json
import os
from unittest.mock import MagicMock, mock_open, patch

import pytest
from fastapi.testclient import TestClient

# Set testing environment variable before importing app
os.environ["TESTING"] = "true"

from app import app  # noqa: E402

# Create test client
client = TestClient(app)


@pytest.fixture
def mock_generate_diagram():
    """Mock the generate_diagram function."""
    with patch("app.generate_diagram") as mock_func:
        # Setup mock response
        mock_func.return_value = {
            "code": "@startuml\nclass Test\n@enduml",
            "url": "https://kroki.io/plantuml/svg/test_url",
            "playground": "https://playground.example.com",
            "local_path": "/tmp/diagrams/test.svg",
        }
        yield mock_func


@pytest.fixture
def mock_plugin_manifest():
    """Mock the plugin manifest file read."""
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


def test_root_endpoint():
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Welcome to the UML-MCP API"
    assert "version" in data
    assert data.get("docs") == "/docs"
    assert data.get("openapi_json") == "/openapi.json"
    assert data.get("mcp") == "/mcp"
    assert data.get("kroki_encode") == "/kroki_encode"


def test_health_check():
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert "status" in response.json()
    assert "modules_available" in response.json()


def test_generate_diagram_endpoint_success(mock_generate_diagram):
    """Test successful diagram generation."""
    # Test data
    request_data = {
        "lang": "plantuml",
        "type": "class",
        "code": "@startuml\nclass Test\n@enduml",
        "theme": "default",
        "output_format": "svg",
    }

    # Make request
    response = client.post("/generate_diagram", json=request_data)

    # Verify response
    assert response.status_code == 200
    assert "url" in response.json()
    assert "playground" in response.json()

    # Verify mock was called with correct params (app injects !theme when theme is provided)
    mock_generate_diagram.assert_called_once()
    args, kwargs = mock_generate_diagram.call_args
    assert kwargs["diagram_type"] == "class"
    assert (
        "@startuml" in kwargs["code"]
        and "class Test" in kwargs["code"]
        and "@enduml" in kwargs["code"]
    )
    assert "!theme default" in kwargs["code"]
    assert kwargs["output_format"] == "svg"


def test_generate_diagram_endpoint_error(mock_generate_diagram):
    """Test error handling in diagram generation endpoint."""
    # Setup mock to return error
    mock_generate_diagram.return_value = {
        "code": "test code",
        "error": "Test error message",
        "url": None,
        "playground": None,
        "local_path": None,
    }

    # Test data
    request_data = {
        "lang": "plantuml",
        "type": "class",
        "code": "invalid code",
        "theme": "default",
    }

    # Make request
    response = client.post("/generate_diagram", json=request_data)

    # Verify response
    assert response.status_code == 400
    assert "detail" in response.json()
    assert "Test error message" in response.json()["detail"]


def test_plugin_manifest_endpoint(mock_plugin_manifest):
    """Test the plugin manifest endpoint (dynamic base URL for Smithery/logo)."""
    response = client.get("/.well-known/ai-plugin.json")
    assert response.status_code == 200
    data = response.json()
    assert "schema_version" in data
    assert "name_for_human" in data
    # Base URL from request so logo and OpenAPI work on any deployment
    assert data["api"]["type"] == "openapi"
    assert data["api"]["url"].endswith("/openapi.json")
    assert data["logo_url"].endswith("/logo.png")


def test_mcp_server_card_endpoint():
    """Test MCP server card for Smithery scanning (/.well-known/mcp/server-card.json)."""
    response = client.get("/.well-known/mcp/server-card.json")
    assert response.status_code == 200
    data = response.json()
    assert "serverInfo" in data
    assert data["serverInfo"]["name"] == "UML Diagram Generator"
    assert "tools" in data
    assert any(t["name"] == "generate_uml" for t in data["tools"])


def test_openapi_spec():
    """Test the OpenAPI specification endpoint."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    # OpenAPI spec should contain standard fields
    assert "openapi" in response.json()
    assert "info" in response.json()
    assert "paths" in response.json()


def test_swagger_docs_available():
    """Test Swagger UI is served at /docs."""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger" in response.text.lower() or "openapi" in response.text.lower()


def test_mcp_post_never_405():
    """POST /mcp must return 200 (MCP mounted) or 503 (fallback), never 405."""
    response = client.post("/mcp", json={})
    assert response.status_code != 405, "POST /mcp must not return Method Not Allowed"
    assert response.status_code in (200, 503)
    if response.status_code == 503:
        data = response.json()
        assert "detail" in data
        assert "MCP HTTP transport is not available" in data["detail"]


def test_mcp_get_fallback_returns_503():
    """When MCP fallback is active, GET /mcp returns 503 with clear detail."""
    response = client.get("/mcp")
    # In test env we use mock FastMCP (no http_app), so fallback is always active
    assert response.status_code == 503
    data = response.json()
    assert data.get("detail") == "MCP HTTP transport is not available."


def test_kroki_encode_success():
    """POST /kroki_encode with valid body returns 200 with url and playground (mocked Kroki)."""
    mock_kroki_instance = MagicMock()
    mock_kroki_instance.get_url.return_value = (
        "https://kroki.io/plantuml/svg/encoded123"
    )
    mock_kroki_instance.get_playground_url.return_value = (
        "https://www.plantuml.com/plantuml/uml/..."
    )

    with patch("tools.kroki.kroki.Kroki", return_value=mock_kroki_instance):
        response = client.post(
            "/kroki_encode",
            json={
                "type": "class",
                "code": "@startuml\nclass A\n@enduml",
                "output_format": "svg",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["url"] == "https://kroki.io/plantuml/svg/encoded123"
    assert data["playground"] == "https://www.plantuml.com/plantuml/uml/..."


def test_kroki_encode_tikz_snippet_wraps_standalone():
    """POST /kroki_encode with TikZ snippet runs prepare_diagram_code (standalone wrap)."""
    mock_kroki_instance = MagicMock()
    mock_kroki_instance.get_url.return_value = "https://kroki.io/tikz/svg/enc"
    mock_kroki_instance.get_playground_url.return_value = None

    with patch("tools.kroki.kroki.Kroki", return_value=mock_kroki_instance):
        response = client.post(
            "/kroki_encode",
            json={
                "type": "tikz",
                "code": r"\begin{tikzpicture}\draw (0,0) -- (1,1);\end{tikzpicture}",
                "output_format": "svg",
            },
        )

    assert response.status_code == 200
    mock_kroki_instance.get_url.assert_called_once()
    _dtype, diagram_text, _fmt = mock_kroki_instance.get_url.call_args[0]
    assert _dtype == "tikz"
    assert r"\documentclass" in diagram_text
    assert r"\begin{tikzpicture}" in diagram_text


def test_kroki_encode_plantuml_theme_in_prepared_code():
    """Optional theme is passed through prepare_diagram_code for PlantUML."""
    mock_kroki_instance = MagicMock()
    mock_kroki_instance.get_url.return_value = "https://kroki.io/plantuml/svg/x"
    mock_kroki_instance.get_playground_url.return_value = None

    with patch("tools.kroki.kroki.Kroki", return_value=mock_kroki_instance):
        response = client.post(
            "/kroki_encode",
            json={
                "type": "class",
                "code": "class A",
                "output_format": "svg",
                "theme": "cerulean",
            },
        )

    assert response.status_code == 200
    _dtype, diagram_text, _fmt = mock_kroki_instance.get_url.call_args[0]
    assert _dtype == "plantuml"
    assert "!theme cerulean" in diagram_text
    assert "@startuml" in diagram_text
    assert "@enduml" in diagram_text


def test_kroki_encode_unsupported_type():
    """POST /kroki_encode with unsupported type returns 400."""
    response = client.post(
        "/kroki_encode",
        json={
            "type": "invalid_type",
            "code": "some code",
            "output_format": "svg",
        },
    )
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert (
        "Unsupported diagram type" in data["detail"] or "invalid_type" in data["detail"]
    )


def test_kroki_encode_unsupported_format():
    """POST /kroki_encode with output_format not supported for the type returns 400."""
    # mermaid only supports svg, png; pdf is unsupported
    response = client.post(
        "/kroki_encode",
        json={
            "type": "mermaid",
            "code": "graph TD; A-->B;",
            "output_format": "pdf",
        },
    )
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "Format" in data["detail"] or "not supported" in data["detail"].lower()
