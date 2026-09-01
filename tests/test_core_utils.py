"""
Tests for the core utilities of UML-MCP.
"""

import base64
import errno
import os
from unittest.mock import MagicMock, patch

import pytest

from mcp_core.core.utils import generate_diagram


@pytest.fixture
def mock_kroki_client():
    """Mock the Kroki client for testing."""
    mock_client = MagicMock()
    mock_client.generate_diagram.return_value = {
        "url": "https://kroki.io/plantuml/svg/test_url",
        "content": b"<svg>test content</svg>",
        "playground": "https://playground.example.com",
    }
    with patch("mcp_core.core.utils.get_kroki_client", return_value=mock_client):
        yield mock_client


def test_generate_diagram_success(mock_kroki_client, tmp_path):
    """Test successful diagram generation."""
    # Call generate_diagram with test data
    result = generate_diagram(
        diagram_type="class",
        code="@startuml\nclass Test\n@enduml",
        output_format="svg",
        output_dir=str(tmp_path),
    )

    # Verify result structure
    assert "code" in result
    assert "url" in result
    assert "playground" in result
    assert "local_path" in result

    assert result.get("source") == "kroki"

    # Verify mock was called with correct params
    mock_kroki_client.generate_diagram.assert_called_once()
    args, _ = mock_kroki_client.generate_diagram.call_args
    assert args[0] == "plantuml"  # Backend for class diagrams
    assert "@startuml" in args[1]  # Code contains correct markup
    assert args[2] == "svg"  # Correct output format


def test_generate_diagram_unsupported_type():
    """Test generating a diagram with unsupported type."""
    result = generate_diagram(
        diagram_type="unsupported_type", code="test code", output_format="svg"
    )

    # Should return error
    assert "error" in result
    assert "Unsupported diagram type" in result["error"]


def test_generate_diagram_exception(mock_kroki_client):
    """Test error handling during diagram generation."""
    # Make mock raise exception
    mock_kroki_client.generate_diagram.side_effect = Exception("Test error")

    # Call function and check result
    result = generate_diagram(
        diagram_type="class", code="@startuml\nclass Test\n@enduml", output_format="svg"
    )

    # Verify error is returned
    assert "error" in result
    assert "Test error" in result["error"]


def test_output_directory_creation(tmp_path, monkeypatch):
    """Test that the output directory is created if it doesn't exist."""
    # Absolute output_dir outside MCP_OUTPUT_ROOT needs the explicit opt-in
    # enforced by mcp_core.core.utils._sanitize_output_dir.
    monkeypatch.setenv("MCP_ALLOW_ARBITRARY_OUTPUT_DIR", "true")
    non_existent_dir = os.path.join(tmp_path, "new_dir")

    # Directory shouldn't exist initially
    assert not os.path.exists(non_existent_dir)

    # Call function with non-existent directory
    mock_client = MagicMock()
    mock_client.generate_diagram.return_value = {
        "url": "test_url",
        "content": b"test content",
        "playground": "test_playground",
    }
    with patch("mcp_core.core.utils.get_kroki_client", return_value=mock_client):
        generate_diagram(
            diagram_type="class",
            code="@startuml\nclass Test\n@enduml",
            output_format="svg",
            output_dir=non_existent_dir,
        )

    # Directory should now exist
    assert os.path.exists(non_existent_dir)


def test_generate_diagram_readonly_filesystem_returns_url_without_local_path(
    mock_kroki_client, tmp_path
):
    """When Path.write_bytes raises OSError (e.g. read-only FS), still return url with local_path=None."""
    with patch(
        "mcp_core.core.diagram_rendering.Path.write_bytes",
        side_effect=OSError(errno.EROFS, "Read-only file system"),
    ):
        result = generate_diagram(
            diagram_type="class",
            code="@startuml\nclass Test\n@enduml",
            output_format="svg",
            output_dir=str(tmp_path),
        )

    assert "error" not in result
    assert result["url"] == "https://kroki.io/plantuml/svg/test_url"
    assert result["playground"] == "https://playground.example.com"
    assert result["local_path"] is None
    assert "code" in result


def test_generate_diagram_output_dir_none_memory_only(mock_kroki_client, tmp_path):
    """When output_dir is None, no file is created; url, playground, and content_base64 are returned (memory-only)."""
    result = generate_diagram(
        diagram_type="class",
        code="@startuml\nclass Test\n@enduml",
        output_format="svg",
        output_dir=None,
    )

    assert "error" not in result
    assert result["url"] == "https://kroki.io/plantuml/svg/test_url"
    assert result["playground"] == "https://playground.example.com"
    assert result["local_path"] is None
    assert "code" in result
    assert "content_base64" in result
    # No file should have been created (we never passed a path; tmp_path should be empty of new diagram files)
    assert not any(
        f.startswith("class_") and f.endswith(".svg") for f in os.listdir(tmp_path)
    )


def test_generate_diagram_scale_ignored_for_png(mock_kroki_client):
    """Scale is only applied for SVG; for PNG, scale is ignored and content is unchanged."""
    mock_kroki_client.generate_diagram.return_value = {
        "url": "https://kroki.io/plantuml/png/test",
        "content": b"\x89PNG\r\n\x1a\n",
        "playground": "https://playground.example.com",
    }
    result = generate_diagram(
        diagram_type="class",
        code="@startuml\nclass Test\n@enduml",
        output_format="png",
        output_dir=None,
        scale=2.0,
    )
    assert "error" not in result
    assert result["content_base64"] == base64.b64encode(b"\x89PNG\r\n\x1a\n").decode(
        "ascii"
    )


def test_generate_diagram_scale_applied_for_svg(mock_kroki_client):
    """When output_format is svg and scale != 1.0, returned content_base64 is scaled SVG."""
    raw_svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="200"></svg>'
    mock_kroki_client.generate_diagram.return_value = {
        "url": "https://kroki.io/plantuml/svg/test",
        "content": raw_svg,
        "playground": "https://playground.example.com",
    }
    result = generate_diagram(
        diagram_type="class",
        code="@startuml\nclass Test\n@enduml",
        output_format="svg",
        output_dir=None,
        scale=2.0,
    )
    assert "error" not in result
    assert "content_base64" in result
    decoded = base64.b64decode(result["content_base64"])
    assert b'width="200' in decoded and b'height="400' in decoded
