"""Serve the built admin console (React/Vite, sources in ``frontend/``).

``dist/`` is committed so ``pip``/``uvx`` installs need no Node. Rebuild with
``cd frontend && npm ci && npm run build`` (CI fails on drift).
"""

from __future__ import annotations

from collections.abc import Callable
from importlib import resources
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

DIST = Path(str(resources.files("mcp_core.admin_ui"))) / "dist"
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; font-src 'self' data:; connect-src 'self'; "
    "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)
SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
}
_PLACEHOLDER = """<!doctype html><meta charset="utf-8"><title>UML-MCP Console</title>
<body style="font-family:system-ui;padding:2rem">The admin console assets are missing.
Build them with <code>cd frontend &amp;&amp; npm ci &amp;&amp; npm run build</code>.</body>"""

Guard = Callable[[Request], None]


def available() -> bool:
    return (DIST / "index.html").is_file()


def add_spa_routes(router: APIRouter, guard: Guard | None = None) -> None:
    """``/admin`` shell + hashed assets. The shell holds no data (APIs are guarded)."""

    def check(request: Request) -> None:
        if guard is not None:
            guard(request)

    @router.get("/admin", include_in_schema=False)
    @router.get("/admin/", include_in_schema=False)
    async def admin_index(request: Request) -> HTMLResponse:
        check(request)
        body = (
            (DIST / "index.html").read_text(encoding="utf-8")
            if available()
            else _PLACEHOLDER
        )
        return HTMLResponse(
            body, headers={**SECURITY_HEADERS, "Cache-Control": "no-store"}
        )

    @router.get("/admin/favicon.svg", include_in_schema=False)
    async def admin_favicon(request: Request) -> FileResponse:
        check(request)
        return _file(DIST / "favicon.svg", immutable=False)

    @router.get("/admin/assets/{name}", include_in_schema=False)
    async def admin_asset(request: Request, name: str) -> FileResponse:
        check(request)
        return _file(DIST / "assets" / name, immutable=True)


def _file(path: Path, *, immutable: bool) -> FileResponse:
    root = DIST.resolve()
    resolved = path.resolve()
    if root not in resolved.parents or not resolved.is_file():
        raise HTTPException(status_code=404, detail="Not Found")
    cache = (
        "public, max-age=31536000, immutable" if immutable else "public, max-age=3600"
    )
    return FileResponse(resolved, headers={**SECURITY_HEADERS, "Cache-Control": cache})


__all__ = ["CSP", "DIST", "add_spa_routes", "available"]
