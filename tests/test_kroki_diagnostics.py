"""Cleaning Kroki error bodies into safe, useful diagnostics.

The bodies below are verbatim responses from a real Kroki 0.33.0 (Mermaid 12.1.0,
Graphviz, D2, PlantUML), so the cleaner is tested against what the renderers send.
"""

import pytest

from mcp_core.core.kroki_diagnostics import clean_kroki_error_body

MERMAID = (
    "Error 400: SyntaxError: Parse error on line 4:\n"
    "...D  A --> B  B -->\n"
    "--------------------^\n"
    "Expecting 'AMP', 'COLON', 'PIPE', 'TESTSTR', 'DOWN', got 'EOF'\n"
    "Error: Syntax error in graph\n"
    "    at Worker.convert (file:///usr/local/kroki/src/worker.js:103:15)\n"
    "    at async file:///usr/local/kroki/src/index.js:36:28"
)


def test_mermaid_keeps_the_line_context_and_expectation() -> None:
    cleaned = clean_kroki_error_body(MERMAID)

    assert cleaned == (
        "Parse error on line 4: ...D A --> B B --> "
        "Expecting 'AMP', 'COLON', 'PIPE', 'TESTSTR', 'DOWN', got 'EOF'"
    )


def test_mermaid_drops_stack_frames_and_server_paths() -> None:
    cleaned = clean_kroki_error_body(MERMAID)

    for leaked in ("worker.js", "file://", "/usr/local", "    at ", "Worker.convert"):
        assert leaked not in cleaned


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (
            "Error 400: Error: <stdin>: syntax error in line 1 near '}'\n (exit code 1)",
            "<stdin>: syntax error in line 1 near '}'",
        ),
        (
            (
                "Error 400: err: failed to compile -: -:1:1: connection missing "
                "destination\n (exit code 1)"
            ),
            "err: failed to compile -: -:1:1: connection missing destination",
        ),
        (
            "Error 400: Syntax Error? (Assumed diagram type: sequence) (line: 1)",
            "Syntax Error? (Assumed diagram type: sequence) (line: 1)",
        ),
    ],
    ids=["graphviz", "d2", "plantuml"],
)
def test_other_backends(body: str, expected: str) -> None:
    assert clean_kroki_error_body(body) == expected


def test_accepts_bytes() -> None:
    assert clean_kroki_error_body(MERMAID.encode()).startswith("Parse error on line 4")


@pytest.mark.parametrize(
    "body",
    [
        None,
        b"",
        "",
        "   \n  ",
        "<html><body>502 Bad Gateway</body></html>",
        "<?xml version='1.0'?><error/>",
    ],
)
def test_nothing_useful_returns_empty(body: str | bytes | None) -> None:
    """An empty body or a proxy's HTML page is not a renderer message."""
    assert clean_kroki_error_body(body) == ""


def test_long_messages_are_truncated() -> None:
    cleaned = clean_kroki_error_body("Error 400: " + "x " * 600, limit=100)

    assert len(cleaned) <= 100
    assert cleaned.endswith("…")


def test_invalid_utf8_does_not_raise() -> None:
    assert "Parse error" in clean_kroki_error_body(b"Error 400: Parse error \xff\xfe")
