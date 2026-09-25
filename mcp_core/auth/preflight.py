"""Startup checks: authorization-server metadata (PKCE S256) and JWKS reachability."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

import httpx

if TYPE_CHECKING:  # pragma: no cover
    from .integration import AuthRuntime


@dataclass
class PreflightReport:
    status: str = "pending"  # pending | ok | degraded | failed
    checks: list[dict[str, Any]] = field(default_factory=list)

    def add(self, name: str, ok: bool | None, detail: str) -> None:
        self.checks.append(
            {
                "name": name,
                "status": "ok" if ok else ("warning" if ok is None else "failed"),
                "detail": detail,
            }
        )

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.status, "checks": self.checks}


def metadata_urls(issuer: str) -> list[str]:
    """Discovery order used by MCP clients (MCP 2025-11-25 authorization)."""
    parts = urlsplit(issuer)
    base = f"{parts.scheme}://{parts.netloc}"
    path = parts.path.rstrip("/")
    if path:
        return [
            f"{base}/.well-known/oauth-authorization-server{path}",
            f"{base}/.well-known/openid-configuration{path}",
            f"{base}{path}/.well-known/openid-configuration",
        ]
    return [
        f"{base}/.well-known/oauth-authorization-server",
        f"{base}/.well-known/openid-configuration",
    ]


async def _discover(http: httpx.AsyncClient, issuer: str) -> dict[str, Any] | None:
    for url in metadata_urls(issuer):
        try:
            resp = await http.get(url, timeout=5.0, follow_redirects=False)
        except httpx.HTTPError:
            continue
        if resp.status_code == 200:
            try:
                data = resp.json()
            except ValueError:
                continue
            if isinstance(data, dict):
                return data
    return None


async def run_preflight(runtime: AuthRuntime) -> PreflightReport:
    report = PreflightReport()
    settings = runtime.settings
    http = runtime.http or httpx.AsyncClient()
    try:
        if settings.mode == "entra-proxy":
            report.add(
                "authorization_server",
                True,
                "entra-proxy facade advertises PKCE S256 and dynamic registration",
            )
        else:
            for server in settings.effective_authorization_servers:
                if settings.entra is not None and (
                    "login.microsoft" in server or "chinacloudapi" in server
                ):
                    report.add(
                        "authorization_server",
                        None,
                        "Entra ID supports PKCE S256 but does not advertise "
                        "code_challenge_methods_supported; strict MCP clients (Claude "
                        "Code, Cursor) need MCP_AUTH_MODE=entra-proxy",
                    )
                    continue
                meta = await _discover(http, server)
                if meta is None:
                    report.add(
                        "authorization_server", False, f"no metadata at {server}"
                    )
                    continue
                if str(meta.get("issuer", "")).rstrip("/") != server.rstrip("/"):
                    report.add(
                        "authorization_server", False, f"issuer mismatch for {server}"
                    )
                    continue
                methods = meta.get("code_challenge_methods_supported") or []
                report.add(
                    "pkce_s256",
                    "S256" in methods,
                    f"{server}: code_challenge_methods_supported={methods}",
                )
        try:
            key_health = runtime.keys.health()
            refresh = getattr(runtime.keys, "refresh", None)
            if refresh is not None:
                await refresh()
                key_health = runtime.keys.health()
            report.add(
                "signing_keys",
                key_health.get("status") == "ok",
                str(key_health.get("source")),
            )
        except Exception as exc:  # noqa: BLE001 - reported, never raised here
            report.add("signing_keys", False, f"cannot load signing keys: {exc}")
    finally:
        if runtime.http is None:
            await http.aclose()
    statuses = {c["status"] for c in report.checks}
    report.status = "degraded" if "failed" in statuses else "ok"
    return report


__all__ = ["PreflightReport", "metadata_urls", "run_preflight"]
