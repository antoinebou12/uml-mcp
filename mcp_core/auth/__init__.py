"""Optional enterprise authentication (OAuth 2.1 / Microsoft Entra ID) for HTTP MCP.

This module is intentionally **stdlib only**: ``app.py`` calls
:func:`auth_requested` on every cold start (including the public, unauthenticated
Vercel deployment) and the heavy submodules (PyJWT, cryptography, httpx clients)
are imported only when ``MCP_AUTH_MODE`` is not ``none``.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Literal, cast

AuthMode = Literal["none", "jwt", "entra-proxy"]
AUTH_MODES: tuple[str, ...] = ("none", "jwt", "entra-proxy")


class AuthConfigError(ValueError):
    """Raised when the enterprise auth configuration is invalid (fail closed)."""


def _mode_from_file(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError as exc:
        raise AuthConfigError(f"MCP_AUTH_CONFIG_FILE not found: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise AuthConfigError(f"MCP_AUTH_CONFIG_FILE is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise AuthConfigError("MCP_AUTH_CONFIG_FILE must contain a JSON object")
    mode = data.get("mode")
    return None if mode is None else str(mode)


def _mode_from_yaml() -> str | None:
    """``auth.mode`` from ``uml-mcp.yaml`` (process environment only)."""
    from ..core.settings_file import get_config

    mode = (get_config().data.get("auth") or {}).get("mode")
    return None if mode is None else str(mode)


def auth_mode_from_env(environ: Mapping[str, str] | None = None) -> AuthMode:
    """Return the configured auth mode (env wins over the JSON config file)."""
    env = os.environ if environ is None else environ
    raw = (env.get("MCP_AUTH_MODE") or "").strip().lower()
    if not raw:
        path = (env.get("MCP_AUTH_CONFIG_FILE") or "").strip()
        mode = _mode_from_file(path) if path else None
        if mode is None and environ is None:
            mode = _mode_from_yaml()
        raw = (mode or "none").strip().lower()
    if raw not in AUTH_MODES:
        raise AuthConfigError(
            f"Unknown MCP_AUTH_MODE {raw!r}; expected one of {', '.join(AUTH_MODES)}"
        )
    return cast(AuthMode, raw)


def auth_requested(environ: Mapping[str, str] | None = None) -> bool:
    """True when enterprise auth is enabled (mode is not ``none``)."""
    return auth_mode_from_env(environ) != "none"


__all__ = [
    "AUTH_MODES",
    "AuthConfigError",
    "AuthMode",
    "auth_mode_from_env",
    "auth_requested",
]
