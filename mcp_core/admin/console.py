"""``uml-mcp admin``: a local HTTP server with the MCP endpoint and the console.

Works from an installed package (no ``app.py`` needed): FastMCP's Streamable
HTTP app at ``/mcp`` plus the loopback-only admin router at ``/admin``. The
setup token travels in the URL *fragment*, which browsers never send to the
server, so it doesn't end up in access logs.
"""

from __future__ import annotations

import ipaddress
import os
import sys
import webbrowser
from typing import Any

from .guards import TOKEN_ENV, setup_token


def build_console_app() -> Any:
    from fastapi import FastAPI

    from ..core.http_observability import (
        MCPExactPathMiddleware,
        RequestIdAndRateLimitMiddleware,
    )
    from ..core.server import get_mcp_server
    from ..observability.logging_setup import ensure_console_logging
    from .api import build_local_admin_router

    ensure_console_logging()
    mcp_app = get_mcp_server().http_app(path="/")
    app = FastAPI(
        title="UML-MCP console",
        lifespan=mcp_app.lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "healthy"}

    app.include_router(build_local_admin_router())
    app.mount("/mcp", mcp_app)
    app.add_middleware(RequestIdAndRateLimitMiddleware)
    app.add_middleware(MCPExactPathMiddleware)
    return app


def console_url(host: str, port: int, page: str, token: str) -> str:
    shown = f"[{host}]" if ":" in host else host
    return f"http://{shown}:{port}/admin/#/{page}?token={token}"


def run_console(
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
    page: str = "overview",
) -> None:
    try:
        loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = host == "localhost"
    if not loopback:
        raise SystemExit("The local console binds to loopback only (127.0.0.1 / ::1).")
    os.environ.setdefault(TOKEN_ENV, setup_token())
    import uvicorn

    app = build_console_app()
    url = console_url(host, port, page, os.environ[TOKEN_ENV])
    sys.stderr.write(
        f"\n  UML-MCP console:  {url}\n  MCP endpoint:     http://{host}:{port}/mcp\n"
        "  Press Ctrl+C (or the Stop button) to stop.\n\n"
    )
    if open_browser:
        webbrowser.open(url)
    uvicorn.run(app, host=host, port=port, log_level="warning")


__all__ = ["build_console_app", "console_url", "run_console"]
