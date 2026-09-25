"""Read-only admin console (``MCP_ADMIN_UI=true``; requires the MCP.Admin app role).

The HTML shell and script are public and contain no data; every ``/admin/api``
call goes through :class:`~mcp_core.auth.mcp_auth.AuthMiddleware` (admin
permission) and is re-checked here (defense in depth).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from ..entra import KNOWN_CLIENTS
from ..errors import AuthError
from ..generators import KINDS, GeneratorParams, generate
from ..metadata import build_as_metadata, build_prm
from .ui import ADMIN_HTML, ADMIN_JS

if TYPE_CHECKING:  # pragma: no cover
    from ..integration import AuthRuntime

_NO_STORE = {"Cache-Control": "no-store"}

CLIENT_MATRIX = [
    {
        "client": "VS Code / GitHub Copilot",
        "jwt": "yes (pre-authorized first-party client)",
        "entra-proxy": "yes (DCR, vscode.dev or loopback redirect)",
    },
    {
        "client": "Visual Studio",
        "jwt": "yes (pre-authorized first-party client)",
        "entra-proxy": "yes",
    },
    {
        "client": "Claude Code",
        "jwt": "only with --client-id and an App ID URI equal to the MCP URL",
        "entra-proxy": "yes (DCR + PKCE S256, loopback redirect)",
    },
    {
        "client": "Cursor",
        "jwt": "no (needs DCR)",
        "entra-proxy": "yes (loopback redirect)",
    },
]


def _require_admin(request: Request) -> None:
    principal = getattr(request.state, "auth_principal", None)
    if principal is None or "admin" not in principal.permissions:
        raise HTTPException(status_code=403, detail="MCP.Admin app role required")


def build_admin_router(runtime: AuthRuntime) -> APIRouter:
    router = APIRouter(include_in_schema=False)
    settings = runtime.settings
    csp = (
        "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; "
        "form-action 'self'"
    )
    page_headers = {
        **_NO_STORE,
        "Content-Security-Policy": csp,
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
    }

    @router.get("/admin", response_class=HTMLResponse)
    @router.get("/admin/", response_class=HTMLResponse)
    async def admin_page() -> HTMLResponse:
        return HTMLResponse(ADMIN_HTML, headers=page_headers)

    @router.get("/admin/app.js")
    async def admin_js() -> Response:
        return Response(ADMIN_JS, media_type="text/javascript", headers=page_headers)

    @router.get("/admin/api/overview")
    async def overview(request: Request) -> JSONResponse:
        _require_admin(request)
        scopes = runtime.policy.advertised_scopes()
        from ...core.config import MCP_SETTINGS

        data: dict[str, Any] = {
            "mode": settings.mode,
            "version": MCP_SETTINGS.version,
            "settings": settings.redacted_dict(),
            "protected_resource_metadata": build_prm(settings, scopes, for_mcp=True),
            "preflight": runtime.preflight.as_dict(),
            "signing_keys": runtime.keys.health(),
            "known_clients": KNOWN_CLIENTS,
            "client_matrix": CLIENT_MATRIX,
            "counters": runtime.audit.counters,
            "sign_in": {
                "proxy_client_id": "uml-mcp-admin"
                if settings.mode == "entra-proxy"
                else None,
                "authorize_endpoint": f"{settings.origin}/oauth/authorize"
                if settings.mode == "entra-proxy"
                else None,
                "token_endpoint": f"{settings.origin}/oauth/token"
                if settings.mode == "entra-proxy"
                else None,
            },
        }
        if settings.mode == "entra-proxy":
            data["authorization_server_metadata"] = build_as_metadata(settings, scopes)
        return JSONResponse(data, headers=_NO_STORE)

    @router.get("/admin/api/events")
    async def events(request: Request) -> JSONResponse:
        _require_admin(request)
        return JSONResponse({"events": runtime.audit.snapshot()}, headers=_NO_STORE)

    @router.post("/admin/api/token-check")
    async def token_check(request: Request) -> JSONResponse:
        _require_admin(request)
        try:
            body = await request.json()
        except ValueError:
            body = {}
        token = str((body or {}).get("token") or "").strip()
        if not token:
            return JSONResponse(
                {"error": "token is required"}, status_code=400, headers=_NO_STORE
            )
        checks = await runtime.validator.explain(token)
        result: dict[str, Any] = {
            "valid": False,
            "checks": [c.__dict__ for c in checks],
        }
        try:
            principal = await runtime.validator.validate(token)
            result["valid"] = True
            result["principal"] = {
                "kind": principal.kind,
                "tenant_id": principal.tenant_id,
                "client_id": principal.client_id,
                "scopes": sorted(principal.scopes),
                "roles": sorted(principal.roles),
                "permissions": sorted(principal.permissions),
                "token_version": principal.token_version,
                "expires_at": principal.expires_at,
            }
        except AuthError:
            pass
        return JSONResponse(result, headers=_NO_STORE)

    @router.get("/admin/api/generate/{kind}")
    async def generate_artifact(kind: str, request: Request) -> Response:
        _require_admin(request)
        if kind not in KINDS:
            raise HTTPException(status_code=404, detail="Unknown generator")
        params = GeneratorParams(
            resource_url=settings.resource_url,
            tenant_id=settings.entra.tenant_id if settings.entra else "<tenant-id>",
            client_id=settings.entra.client_id if settings.entra else "<api-client-id>",
            mode=settings.mode,
        )
        return Response(
            generate(kind, params), media_type="text/plain", headers=_NO_STORE
        )

    from ...observability.admin_api import add_ops_routes

    add_ops_routes(router, _require_admin)
    return router


__all__ = ["CLIENT_MATRIX", "build_admin_router"]
