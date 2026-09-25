"""Wire enterprise auth into the FastAPI app (only imported when auth is enabled)."""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

import httpx

from .audit import AuditLog
from .jwks import JwksCache, KeyProvider, StaticKeySet
from .policy import Policy
from .preflight import PreflightReport, run_preflight
from .settings import AuthSettings, get_auth_settings
from .validator import TokenValidator

logger = logging.getLogger(__name__)


@dataclass
class AuthRuntime:
    settings: AuthSettings
    keys: KeyProvider
    validator: TokenValidator
    policy: Policy
    audit: AuditLog
    http: httpx.AsyncClient | None = None
    sealer: Any = None
    upstream: Any = None
    preflight: PreflightReport = field(default_factory=PreflightReport)


def build_auth_runtime(
    settings: AuthSettings | None = None,
    *,
    http: httpx.AsyncClient | None = None,
    tool_registry: dict[str, dict] | None = None,
) -> AuthRuntime:
    """Build the runtime; raises :class:`~mcp_core.auth.AuthConfigError` on bad config."""
    settings = settings or get_auth_settings()
    if tool_registry is None:
        from ..tools.tool_decorator import get_tool_registry

        tool_registry = get_tool_registry()
    keys: KeyProvider
    if settings.public_key_pem and not settings.effective_jwks_uri:
        keys = StaticKeySet([settings.public_key_pem])
    else:
        assert settings.effective_jwks_uri is not None
        keys = JwksCache(
            settings.effective_jwks_uri, http=http, ttl=settings.jwks_cache_seconds
        )
    runtime = AuthRuntime(
        settings=settings,
        keys=keys,
        validator=TokenValidator(settings, keys),
        policy=Policy(settings, tool_registry),
        audit=AuditLog(),
        http=http,
    )
    if settings.mode == "entra-proxy":
        from .proxy.upstream import UpstreamClient
        from .sealing import Sealer, parse_keys

        assert settings.proxy.encryption_keys is not None
        runtime.sealer = Sealer(
            parse_keys(settings.proxy.encryption_keys.get_secret_value()),
            settings.origin,
        )
        runtime.upstream = UpstreamClient(settings, http)
    return runtime


def install_auth(app: Any, runtime: AuthRuntime) -> None:
    """Add the middleware (innermost when called before CORS) and the routers."""
    from .mcp_auth import AuthMiddleware
    from .metadata import build_metadata_router

    app.add_middleware(AuthMiddleware, runtime=runtime)
    app.include_router(build_metadata_router(runtime))
    if runtime.settings.mode == "entra-proxy":
        from .proxy import build_proxy_router

        app.include_router(build_proxy_router(runtime))
    if runtime.settings.admin_ui:
        from .admin import build_admin_router

        app.include_router(build_admin_router(runtime))
    _install_log_redaction()
    logger.info(
        "Enterprise auth enabled: mode=%s resource=%s",
        runtime.settings.mode,
        runtime.settings.resource_url,
    )


def cors_expose_headers() -> list[str]:
    return [
        "WWW-Authenticate",
        "X-Request-ID",
        "Mcp-Session-Id",
        "Mcp-Protocol-Version",
    ]


def compose_lifespan(inner: Callable[[Any], Any] | None, runtime: AuthRuntime):
    """Run the MCP lifespan and warm auth caches / preflight on startup."""

    @asynccontextmanager
    async def lifespan(app: Any) -> AsyncIterator[Any]:
        async with AsyncExitStack() as stack:
            state = None
            if inner is not None:
                state = await stack.enter_async_context(inner(app))
            if runtime.settings.preflight != "off":
                runtime.preflight = await run_preflight(runtime)
                for check in runtime.preflight.checks:
                    level = logging.INFO if check["status"] == "ok" else logging.WARNING
                    logger.log(
                        level, "auth preflight %s: %s", check["name"], check["detail"]
                    )
                if (
                    runtime.settings.preflight == "strict"
                    and runtime.preflight.status != "ok"
                ):
                    raise RuntimeError(
                        "enterprise auth preflight failed (MCP_AUTH_PREFLIGHT=strict)"
                    )
            yield state

    return lifespan


_SENSITIVE_QUERY = re.compile(
    r"((?:access_token|code|state|client_assertion|refresh_token)=)[^&\s\"]+"
)


class QueryRedactionFilter(logging.Filter):
    """Redact tokens/codes that may appear in access-log query strings."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.args:
            record.args = tuple(
                _SENSITIVE_QUERY.sub(r"\1[redacted]", a) if isinstance(a, str) else a
                for a in (
                    record.args if isinstance(record.args, tuple) else (record.args,)
                )
            )
        if isinstance(record.msg, str):
            record.msg = _SENSITIVE_QUERY.sub(r"\1[redacted]", record.msg)
        return True


def _install_log_redaction() -> None:
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, QueryRedactionFilter) for f in access.filters):
        access.addFilter(QueryRedactionFilter())


__all__ = [
    "AuthRuntime",
    "QueryRedactionFilter",
    "build_auth_runtime",
    "compose_lifespan",
    "cors_expose_headers",
    "install_auth",
]
