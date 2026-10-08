"""Best-effort MCP progress and log notifications for synchronous tools.

Tools stay plain functions: their signatures feed the tool schemas, ``uml-mcp lint``
and the server card, so a ``ctx`` parameter is not an option. The request context is
fetched with FastMCP's ``get_context()`` instead. FastMCP runs sync tools in an AnyIO
worker thread, and ``anyio.from_thread.run`` hops back to the event loop to send.

Everything here is a silent no-op outside an MCP request (REST routes, tests, the
mock server) and for clients that did not ask for progress, and it never raises: a
lost notification must not fail a render.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_LOG_LEVELS = frozenset({"debug", "info", "warning", "error"})


def _request_context() -> Any | None:
    """Return the active FastMCP request context, or None when there is none."""
    try:
        from fastmcp.server.dependencies import get_context

        return get_context()
    except (ImportError, RuntimeError):  # no FastMCP, or no active request
        return None


def _send(method: str, *args: Any) -> None:
    ctx = _request_context()
    if ctx is None:
        return
    try:
        from anyio import from_thread

        from_thread.run(getattr(ctx, method), *args)
    except Exception:  # never fail a tool call over a notification
        logger.debug("MCP %s notification skipped", method, exc_info=True)


def report_progress(progress: float, total: float, message: str) -> None:
    """Send ``notifications/progress`` (only delivered if the client sent a token)."""
    _send("report_progress", progress, total, message)


def log(level: str, message: str) -> None:
    """Send ``notifications/message`` at ``debug``/``info``/``warning``/``error``."""
    _send(level if level in _LOG_LEVELS else "info", message)
