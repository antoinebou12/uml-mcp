"""Turn a Kroki error response into a short, safe diagnostic.

Kroki answers a bad diagram with HTTP 400 and the renderer's own message, e.g.
Mermaid's ``Parse error on line 4 ... Expecting 'AMP', ..., got 'EOF'``. That is
exactly what a model needs to repair its diagram, but the raw body also carries a
JavaScript stack trace with server file paths and a ``(exit code 1)`` suffix, so it is
cleaned before it goes into a tool error.
"""

from __future__ import annotations

import re

_STATUS_PREFIX = re.compile(r"^\s*Error \d{3}:\s*")
_ERROR_PREFIX = re.compile(r"^(?:Syntax)?Error:\s*")
_STACK_FRAME = re.compile(r"^\s+at\s+\S")
_RULER = re.compile(r"^\s*-{3,}\^?\s*$")  # Mermaid's "-----^" caret line
_EXIT_CODE = re.compile(r"\s*\(exit code \d+\)\s*$")
_FILE_URL = re.compile(r"file://\S+")
# Lines that only restate that parsing failed, after the useful line already said why.
_REDUNDANT = frozenset({"error: syntax error in graph"})


def clean_kroki_error_body(content: str | bytes | None, *, limit: int = 500) -> str:
    """Return the renderer's message without stack frames, paths or status noise.

    Returns ``""`` when there is nothing useful (empty body, or an HTML error page from
    a proxy rather than a renderer message).
    """
    if not content:
        return ""
    text = (
        content.decode("utf-8", errors="replace")
        if isinstance(content, (bytes, bytearray))
        else str(content)
    )
    if text.lstrip().startswith("<"):
        return ""

    kept: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if (
            not line
            or _STACK_FRAME.match(raw)
            or _RULER.match(line)
            or line.lower() in _REDUNDANT
        ):
            continue
        kept.append(line)

    message = " ".join(kept)
    message = _STATUS_PREFIX.sub("", message)
    message = _ERROR_PREFIX.sub("", message)
    message = _EXIT_CODE.sub("", message)
    message = _FILE_URL.sub("", message)
    message = re.sub(r"\s+", " ", message).strip()
    if len(message) > limit:
        message = message[: limit - 1].rstrip() + "…"
    return message
