"""
Tests for the Kroki API integration.
"""

import base64
import zlib
from unittest.mock import MagicMock, patch

import httpx
import pytest

from tools.kroki.kroki import (
    Kroki,
    KrokiConnectionError,
    KrokiHTTPError,
    LANGUAGE_OUTPUT_SUPPORT,
    scale_svg,
)
from tools.kroki.kroki_templates import DiagramExamples, DiagramTemplates


@pytest.fixture
def mock_httpx_client():
    """Mock the httpx client for testing."""
    with patch("httpx.Client") as mock_client:
        # Create mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"<svg>test content</svg>"
        mock_response.raise_for_status = MagicMock()

        # Make client.get return the mock response
        client_instance = mock_client.return_value
        client_instance.get.return_value = mock_response

        yield client_instance


def test_kroki_initialization():
    """Test Kroki client initialization."""
    # Test with default URL
    client = Kroki()
    assert client.base_url == "https://kroki.io"

    # Test with custom URL
    custom_url = "http://custom-kroki.example.com"
    client = Kroki(base_url=custom_url)
    assert client.base_url == custom_url


def test_get_url():
    """Test URL generation for a diagram."""
    client = Kroki()
    diagram_type = "plantuml"
    diagram_text = "@startuml\nclass Test\n@enduml"
    output_format = "svg"

    url = client.get_url(diagram_type, diagram_text, output_format)

    # URL should contain the encoded diagram
    assert url.startswith(f"https://kroki.io/{diagram_type}/{output_format}/")

    # Verify encoding by manually encoding the diagram text
    encoded = client.deflate_and_encode(diagram_text)
    assert encoded in url


def test_plantuml_playground_path_segment_strips_erroneous_prefix():
    """Leading ~1 is Huffman on plantuml.com; deflate payloads must not use it."""
    from tools.kroki.kroki import plantuml_playground_path_segment

    assert plantuml_playground_path_segment("~1SoWkIImg") == "SoWkIImg"
    assert plantuml_playground_path_segment("SoWkIImg") == "SoWkIImg"


def test_get_playground_url():
    """Test playground URL generation."""
    client = Kroki()

    # PlantUML playground: /plantuml/uml/<encoded> (no ~1; see plantuml.com/text-encoding)
    plantuml_url = client.get_playground_url(
        "plantuml", "@startuml\nclass Test\n@enduml"
    )
    assert plantuml_url is not None
    assert plantuml_url.startswith("https://www.plantuml.com/plantuml/uml/")
    encoded_suffix = plantuml_url.removeprefix("https://www.plantuml.com/plantuml/uml/")
    assert encoded_suffix
    assert "~1" not in plantuml_url

    with patch.object(client, "encode_plantuml", return_value="~1SoWkIImgAStD"):
        stripped = client.get_playground_url("plantuml", "x")
        assert stripped == "https://www.plantuml.com/plantuml/uml/SoWkIImgAStD"
        assert "~1" not in stripped

    # Test Mermaid playground
    mermaid_url = client.get_playground_url("mermaid", "graph TD;\nA-->B;")
    assert mermaid_url is not None
    assert mermaid_url.startswith("https://mermaid.live/edit#")

    # Test non-existent playground
    nonexistent_url = client.get_playground_url("nonexistent", "test")
    assert nonexistent_url is None


def test_render_diagram_success(mock_httpx_client):
    """Test successful diagram rendering."""
    client = Kroki()

    # Test rendering
    result = client.render_diagram("plantuml", "@startuml\nclass Test\n@enduml", "svg")

    # Verify result and mock calls
    assert result == b"<svg>test content</svg>"
    mock_httpx_client.get.assert_called_once()
    url_arg = mock_httpx_client.get.call_args[0][0]
    assert url_arg.startswith("https://kroki.io/plantuml/svg/")


def test_render_diagram_http_error(mock_httpx_client):
    """Test HTTP error handling."""
    # Setup mock to raise HTTP error
    mock_response = mock_httpx_client.get.return_value
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "HTTP Error",
        request=httpx.Request("GET", "https://kroki.io"),
        response=mock_response,
    )

    client = Kroki()

    # Test error handling
    with pytest.raises(KrokiHTTPError):
        client.render_diagram("plantuml", "@startuml\nclass Test\n@enduml", "svg")


def test_render_diagram_connection_error(mock_httpx_client):
    """Test connection error handling."""
    # Setup mock to raise connection error
    mock_httpx_client.get.side_effect = httpx.RequestError(
        "Connection error", request=None
    )

    client = Kroki()

    # Test error handling
    with pytest.raises(KrokiConnectionError):
        client.render_diagram("plantuml", "@startuml\nclass Test\n@enduml", "svg")


def test_generate_diagram(mock_httpx_client):
    """Test the generate_diagram method."""
    client = Kroki()

    # Test diagram generation
    result = client.generate_diagram(
        "plantuml", "@startuml\nclass Test\n@enduml", "svg"
    )

    # Verify result structure
    assert "url" in result
    assert "content" in result
    assert "playground" in result
    assert result["content"] == b"<svg>test content</svg>"

    # Verify URL format
    assert result["url"].startswith("https://kroki.io/plantuml/svg/")

    assert result["playground"].startswith("https://www.plantuml.com/plantuml/uml/")
    assert "~1" not in result["playground"]


def test_deflate_and_encode():
    """Test the deflate_and_encode method."""
    client = Kroki()
    text = "test text"

    encoded = client.deflate_and_encode(text)

    # Verify the result is non-empty and doesn't contain invalid characters
    assert encoded
    assert "+" not in encoded  # + should be replaced with -
    assert "/" not in encoded  # / should be replaced with _

    # Manual compression and encoding to verify
    compress_obj = zlib.compressobj(
        level=9,
        method=zlib.DEFLATED,
        wbits=15,
        memLevel=8,
        strategy=zlib.Z_DEFAULT_STRATEGY,
    )
    compressed_data = compress_obj.compress(text.encode("utf-8"))
    compressed_data += compress_obj.flush()

    expected = base64.urlsafe_b64encode(compressed_data).decode("ascii")
    expected = expected.replace("+", "-").replace("/", "_")

    assert encoded == expected


def test_unsupported_diagram_type():
    """Test error handling for unsupported diagram types."""
    client = Kroki()

    with pytest.raises(ValueError, match="Unsupported diagram type"):
        client.get_url("nonexistent_type", "test code", "svg")


def test_unsupported_output_format():
    """Test error handling for unsupported output formats."""
    client = Kroki()

    with pytest.raises(ValueError, match="Unsupported output format"):
        client.get_url("plantuml", "test code", "nonexistent_format")


class TestKrokiHTTPError:
    """Tests for KrokiHTTPError exception."""

    def test_kroki_http_error_attributes(self):
        """KrokiHTTPError exposes url, response, content and string message."""
        mock_response = MagicMock()
        mock_response.url = "https://kroki.io/plantuml/svg/xxx"
        mock_response.status_code = 500
        content = b"error body"
        e = KrokiHTTPError(mock_response, content)
        assert e.response is mock_response
        assert e.content == content
        assert e.url == "https://kroki.io/plantuml/svg/xxx"
        assert "500" in str(e)
        assert "kroki.io" in str(e)


def test_generate_diagram_http_error(mock_httpx_client):
    """generate_diagram raises KrokiHTTPError when server returns non-200."""
    mock_response = mock_httpx_client.get.return_value
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "HTTP Error",
        request=httpx.Request("GET", "https://kroki.io"),
        response=mock_response,
    )
    client = Kroki()
    with pytest.raises(KrokiHTTPError):
        client.generate_diagram("plantuml", "@startuml\nclass Test\n@enduml", "svg")


def test_generate_diagram_connection_error(mock_httpx_client):
    """generate_diagram raises KrokiConnectionError on connection failure."""
    mock_httpx_client.get.side_effect = httpx.ConnectError("Connection refused")
    client = Kroki()
    with pytest.raises(KrokiConnectionError):
        client.generate_diagram("plantuml", "@startuml\nclass Test\n@enduml", "svg")


def test_deflate_and_encode_empty_string():
    """deflate_and_encode returns empty string for empty input."""
    client = Kroki()
    assert client.deflate_and_encode("") == ""


def test_deflate_and_encode_base64_decodable():
    """deflate_and_encode output is base64-decodable and zlib-decompressible."""
    client = Kroki()
    text = "sample diagram code"
    encoded = client.deflate_and_encode(text)
    assert encoded
    decoded_b64 = base64.urlsafe_b64decode(encoded.replace("-", "+").replace("_", "/"))
    decompressed = zlib.decompress(decoded_b64, 15 + 32)
    assert decompressed.decode("utf-8") == text


def test_scale_svg_doubles_width_height():
    """scale_svg multiplies root width/height by scale factor."""
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="200"><rect /></svg>'
    out = scale_svg(svg, 2.0)
    assert b'width="200' in out and b'height="400' in out

    out_half = scale_svg(svg, 0.5)
    assert b'width="50' in out_half and b'height="100' in out_half


def test_scale_svg_returns_unchanged_when_scale_one():
    """scale_svg returns same bytes when scale is 1.0."""
    svg = b'<svg width="100" height="200"></svg>'
    assert scale_svg(svg, 1.0) == svg


def test_scale_svg_invalid_scale_raises():
    """scale_svg raises ValueError when scale <= 0."""
    with pytest.raises(ValueError, match="greater than 0"):
        scale_svg(b"<svg></svg>", 0)
    with pytest.raises(ValueError, match="greater than 0"):
        scale_svg(b"<svg></svg>", -1.0)


def test_language_output_support_smoke():
    """LANGUAGE_OUTPUT_SUPPORT has expected diagram types with list of formats."""
    assert "plantuml" in LANGUAGE_OUTPUT_SUPPORT
    assert "mermaid" in LANGUAGE_OUTPUT_SUPPORT
    assert "d2" in LANGUAGE_OUTPUT_SUPPORT
    assert isinstance(LANGUAGE_OUTPUT_SUPPORT["plantuml"], list)
    assert "svg" in LANGUAGE_OUTPUT_SUPPORT["plantuml"]
    assert "png" in LANGUAGE_OUTPUT_SUPPORT["mermaid"]
    assert "svg" in LANGUAGE_OUTPUT_SUPPORT["d2"]


@pytest.mark.parametrize(
    "diagram_type",
    [
        "plantuml",
        "mermaid",
        "class",
        "sequence",
        "activity",
        "usecase",
        "state",
        "component",
        "deployment",
        "object",
        "blockdiag",
        "seqdiag",
        "actdiag",
        "nwdiag",
        "c4plantuml",
    ],
)
def test_diagram_examples_get_example(diagram_type):
    """DiagramExamples.get_example returns non-empty string for known types."""
    result = DiagramExamples.get_example(diagram_type)
    assert isinstance(result, str)
    assert len(result) > 0


def test_diagram_examples_get_example_unknown():
    """DiagramExamples.get_example returns default message for unknown type."""
    result = DiagramExamples.get_example("unknown_type")
    assert isinstance(result, str)
    assert "unknown_type" in result or "documentation" in result.lower()


def test_diagram_templates_get_template_known():
    """DiagramTemplates.get_template returns non-empty string for known types."""
    known_types = [
        "plantuml",
        "mermaid",
        "class",
        "sequence",
        "activity",
        "usecase",
        "state",
        "component",
        "deployment",
        "object",
        "d2",
        "graphviz",
        "blockdiag",
    ]
    for diagram_type in known_types:
        result = DiagramTemplates.get_template(diagram_type)
        assert isinstance(result, str), diagram_type
        assert len(result) > 0, diagram_type


def test_diagram_templates_get_template_unknown():
    """DiagramTemplates.get_template returns default for unknown type."""
    result = DiagramTemplates.get_template("unknown_type")
    assert isinstance(result, str)
    assert "documentation" in result.lower() or "template" in result.lower()


# All Kroki types that must have template/example (umlet not in default UI select)
_KROKI_TYPES_WITH_TEMPLATES = [k for k in LANGUAGE_OUTPUT_SUPPORT if k != "umlet"]


@pytest.mark.parametrize("diagram_type", _KROKI_TYPES_WITH_TEMPLATES)
def test_every_kroki_type_has_template(diagram_type):
    """Every Kroki type (except umlet) has a non-default DiagramTemplates entry."""
    result = DiagramTemplates.get_template(diagram_type)
    assert isinstance(result, str)
    assert len(result) > 0
    assert "No specific template" not in result


@pytest.mark.parametrize("diagram_type", _KROKI_TYPES_WITH_TEMPLATES)
def test_every_kroki_type_has_example(diagram_type):
    """Every Kroki type (except umlet) has a non-default DiagramExamples entry."""
    result = DiagramExamples.get_example(diagram_type)
    assert isinstance(result, str)
    assert len(result) > 0
    assert "No specific example" not in result
