"""Who may read and change the running server through the admin console.

Local mode (enterprise auth off, loopback socket peer):
    * reads: loopback peer + a loopback ``Host`` header (DNS-rebinding defence)
    * writes: additionally the one-time **setup token** as a bearer and the
      ``X-UML-MCP-Admin: 1`` header (custom header => CORS preflight => no CSRF)

Enterprise mode (``MCP_AUTH_MODE`` on):
    * reads: the ``MCP.Admin`` app role (checked by the auth middleware and here)
    * writes/stop: additionally ``admin.allow_write`` / ``admin.allow_stop``
"""

from __future__ import annotations

import hmac
import ipaddress
import logging
import os
import secrets
import sys
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

TOKEN_ENV = "UML_MCP_ADMIN_TOKEN"
WRITE_HEADER = "x-uml-mcp-admin"
LOOPBACK_HOSTS = ("localhost", "127.0.0.1", "[::1]", "::1")

Guard = Callable[[Request], None]


@dataclass(frozen=True)
class Guards:
    read: Guard
    write: Guard
    stop: Guard
    mode: str  # local | enterprise


_TOKEN: str | None = None


def setup_token() -> str:
    """Process-wide local setup token (``UML_MCP_ADMIN_TOKEN`` or generated once)."""
    global _TOKEN
    if _TOKEN is None:
        _TOKEN = os.environ.get(TOKEN_ENV) or secrets.token_urlsafe(32)
        if TOKEN_ENV not in os.environ:
            # stderr only: never through logging (files are shipped and tailed in the UI)
            sys.stderr.write(
                f"UML-MCP admin setup token (needed to save settings): {_TOKEN}\n"
            )
    return _TOKEN


def reset_setup_token() -> None:
    global _TOKEN
    _TOKEN = None


def _is_loopback(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def local_read(request: Request) -> None:
    peer = request.client.host if request.client else ""
    if not _is_loopback(peer):
        raise HTTPException(status_code=404, detail="Not Found")
    host = (request.headers.get("host") or "").rsplit(":", 1)[0].lower()
    if host.startswith("[") and "]" in host:  # [::1]:8765
        host = host[: host.index("]") + 1]
    if host not in LOOPBACK_HOSTS:
        raise HTTPException(status_code=403, detail="Host must be localhost")


def _bearer(request: Request) -> str:
    auth = request.headers.get("authorization") or ""
    return auth[7:].strip() if auth[:7].lower() == "bearer " else ""


def local_write(request: Request) -> None:
    local_read(request)
    if request.headers.get(WRITE_HEADER) != "1":
        raise HTTPException(
            status_code=403, detail=f"{WRITE_HEADER}: 1 header required"
        )
    token = _bearer(request)
    if not token or not hmac.compare_digest(token, setup_token()):
        raise HTTPException(
            status_code=401,
            detail="setup token required (printed by `uml-mcp admin` / server logs)",
        )


def local_guards() -> Guards:
    return Guards(read=local_read, write=local_write, stop=local_write, mode="local")


def enterprise_guards(require_admin: Guard) -> Guards:
    from ..core.settings_file import get_app_config

    def write(request: Request) -> None:
        require_admin(request)
        if not get_app_config().admin.allow_write:
            raise HTTPException(
                status_code=403,
                detail="settings are read-only here; set admin.allow_write: true "
                "or change uml-mcp.yaml through GitOps",
            )

    def stop(request: Request) -> None:
        require_admin(request)
        if not get_app_config().admin.allow_stop:
            raise HTTPException(status_code=403, detail="set admin.allow_stop: true")

    return Guards(read=require_admin, write=write, stop=stop, mode="enterprise")


__all__ = [
    "TOKEN_ENV",
    "WRITE_HEADER",
    "Guards",
    "enterprise_guards",
    "local_guards",
    "local_read",
    "local_write",
    "reset_setup_token",
    "setup_token",
]
