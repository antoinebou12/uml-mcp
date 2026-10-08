"""Best-effort MCP progress and log notifications for synchronous tools.

Tools stay plain functions: their signatures feed the tool schemas, ``uml-mcp lint``
and the server card, so a ``ctx`` parameter is not an option. The request context is
fetched with FastMCP's ``get_context()`` instead. FastMCP runs sync tools in an AnyIO
worker thread, and ``anyio.from_thread.run`` hops back to the event loop to send.

Everything here is a silent no-op outside an MCP request (REST routes, tests, the
mock server) and, crucially, for clients that did not opt in by sending a
``progressToken`` or a log level: on streamable HTTP any notification turns the
response into an event stream, and simple hand-rolled clients that read only the
first event would then mistake a log line for the tool result. It never raises: a
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


_LOG_LEVEL_META_KEY = "io.modelcontextprotocol/logLevel"


def _client_opted_in(ctx: Any) -> bool:
    """True when the request asked for updates: a progress token or a log level.

    Request ``_meta`` is a dict keyed by wire names (``progressToken``); FastMCP's own
    internal copy uses ``progress_token``, so accept both.
    """
    meta = getattr(getattr(ctx, "request_context", None), "meta", None)
    if not hasattr(meta, "get"):
        return False
    return any(
        meta.get(key) is not None
        for key in ("progressToken", "progress_token", _LOG_LEVEL_META_KEY)
    )


def _send(method: str, *args: Any) -> None:
    ctx = _request_context()
    if ctx is None or not _client_opted_in(ctx):
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
