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

    def test_http_400_keeps_the_renderers_diagnosis(self):
        """Kroki's own parse error reaches the caller so the diagram can be repaired."""
        from tools.kroki.kroki import KrokiHTTPError

        response = MagicMock()
        response.status_code = 400
        response.url = "https://kroki.io/mermaid/svg"
        body = (
            b"Error 400: SyntaxError: Parse error on line 4:\n"
            b"...D  A --> B  B -->\n--------------------^\n"
            b"Expecting 'AMP', 'PIPE', got 'EOF'\n"
            b"Error: Syntax error in graph\n"
            b"    at Worker.convert (file:///usr/local/kroki/src/worker.js:103:15)"
        )
        msg = _handle_diagram_error(KrokiHTTPError(response, body), "graph TD")

        assert "syntax error" in msg.lower()
        assert "Parse error on line 4" in msg
        assert "Expecting 'AMP', 'PIPE', got 'EOF'" in msg
        assert "worker.js" not in msg and "file://" not in msg

    def test_http_500_includes_detail_when_kroki_sends_one(self):
        from tools.kroki.kroki import KrokiHTTPError

        response = MagicMock()
        response.status_code = 500
        response.url = "https://kroki.io/vega/svg"
        msg = _handle_diagram_error(
            KrokiHTTPError(response, b"Error 500: vega failed to compile"), "code"
        )

        assert "500" in msg and "vega failed to compile" in msg

    def test_infrastructure_errors_ignore_the_body(self):
        """404/503 are about the service, not the diagram: keep the fixed guidance."""
        from tools.kroki.kroki import KrokiHTTPError

        for status, word in ((404, "not found"), (503, "unavailable")):
            response = MagicMock()
            response.status_code = status
            response.url = f"https://kroki.io/x/{status}"
            msg = _handle_diagram_error(
                KrokiHTTPError(response, b"<html>proxy page</html>"), "code"
            )
            assert word in msg.lower()
            assert "proxy page" not in msg

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
