"""RFC 9728 protected resource metadata and RFC 8414 authorization server metadata."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

if TYPE_CHECKING:  # pragma: no cover
    from .integration import AuthRuntime
    from .settings import AuthSettings

_META_HEADERS = {
    "Cache-Control": "public, max-age=300",
    "Access-Control-Allow-Origin": "*",
}


def build_prm(
    settings: AuthSettings, scopes: list[str], *, for_mcp: bool
) -> dict[str, Any]:
    """RFC 9728 document. ``resource`` equals the identifier the URL was built from."""
    doc: dict[str, Any] = {
        "resource": settings.resource_url if for_mcp else settings.root_resource,
        "authorization_servers": settings.effective_authorization_servers,
        "scopes_supported": scopes,
        "bearer_methods_supported": ["header"],
        "resource_name": settings.resource_name,
    }
    if settings.resource_documentation:
        doc["resource_documentation"] = settings.resource_documentation
    doc["resource_signing_alg_values_supported"] = list(settings.algorithms)
    return doc


def build_as_metadata(settings: AuthSettings, scopes: list[str]) -> dict[str, Any]:
    """RFC 8414 document for the ``entra-proxy`` facade (issuer = origin)."""
    origin = settings.origin
    supported = list(scopes)
    if settings.proxy.refresh_tokens and "offline_access" not in supported:
        supported.append("offline_access")  # SEP-2207: belongs to the AS, not the PRM
    grants = ["authorization_code"]
    if settings.proxy.refresh_tokens:
        grants.append("refresh_token")
    doc: dict[str, Any] = {
        "issuer": origin,
        "authorization_endpoint": f"{origin}/oauth/authorize",
        "token_endpoint": f"{origin}/oauth/token",
        "registration_endpoint": f"{origin}/oauth/register",
        "response_types_supported": ["code"],
        "response_modes_supported": ["query"],
        "grant_types_supported": grants,
        "token_endpoint_auth_methods_supported": ["none"],
        "code_challenge_methods_supported": ["S256"],
        "scopes_supported": supported,
        "authorization_response_iss_parameter_supported": True,
    }
    if settings.resource_documentation:
        doc["service_documentation"] = settings.resource_documentation
    return doc


def build_metadata_router(runtime: AuthRuntime) -> APIRouter:
    router = APIRouter(include_in_schema=False)
    settings = runtime.settings
    scopes = runtime.policy.advertised_scopes()
    mcp_path = "/.well-known/oauth-protected-resource" + (
        settings.resource_url.split(settings.origin, 1)[1].rstrip("/") or ""
    )

    @router.api_route("/.well-known/oauth-protected-resource", methods=["GET", "HEAD"])
    async def prm_root() -> JSONResponse:
        return JSONResponse(
            build_prm(settings, scopes, for_mcp=False), headers=_META_HEADERS
        )

    if mcp_path != "/.well-known/oauth-protected-resource":

        @router.api_route(mcp_path, methods=["GET", "HEAD"])
        async def prm_mcp() -> JSONResponse:
            return JSONResponse(
                build_prm(settings, scopes, for_mcp=True), headers=_META_HEADERS
            )

    if settings.mode == "entra-proxy":

        @router.api_route(
            "/.well-known/oauth-authorization-server", methods=["GET", "HEAD"]
        )
        async def as_metadata() -> JSONResponse:
            return JSONResponse(
                build_as_metadata(settings, scopes), headers=_META_HEADERS
            )

    return router


__all__ = ["build_as_metadata", "build_metadata_router", "build_prm"]
