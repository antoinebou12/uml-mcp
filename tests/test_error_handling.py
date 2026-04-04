"""
Tests for error handling in mcp_core.core.utils.
"""

from unittest.mock import MagicMock

from mcp_core.core.utils import _handle_diagram_error


def _make_http_error(status_code):
    """Helper to create a KrokiHTTPError with given status code."""
    from tools.kroki.kroki import KrokiHTTPError

    response = MagicMock()
    response.status_code = status_code
    response.url = f"https://kroki.io/test/{status_code}"
    return KrokiHTTPError(response, content=b"error")


class TestHandleDiagramError:
    """Tests for _handle_diagram_error."""

    def test_http_404_error(self):
        """404 error returns endpoint not found message."""
        msg = _handle_diagram_error(_make_http_error(404), "code")
        assert "not found" in msg.lower()

    def test_http_503_error(self):
        """503 error returns service unavailable message."""
        msg = _handle_diagram_error(_make_http_error(503), "code")
        assert "unavailable" in msg.lower()

    def test_http_400_error(self):
        """400 error returns syntax error message."""
        msg = _handle_diagram_error(_make_http_error(400), "bad code")
        assert "syntax" in msg.lower()

    def test_http_500_error(self):
        """500 error returns generic HTTP error message."""
        msg = _handle_diagram_error(_make_http_error(500), "code")
        assert "500" in msg

    def test_connection_error(self):
        """Connection error returns connectivity message."""
        from tools.kroki.kroki import KrokiConnectionError

        err = KrokiConnectionError("connection refused")
        msg = _handle_diagram_error(err, "code")
        assert "connect" in msg.lower()

    def test_unexpected_error(self):
        """Unknown exception returns generic message with type name."""
        err = ValueError("something went wrong")
        msg = _handle_diagram_error(err, "code")
        assert "ValueError" in msg
        assert "something went wrong" in msg
