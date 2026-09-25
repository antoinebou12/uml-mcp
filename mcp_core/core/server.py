"""Core MCP server implementation.

The HTTP transport defaults to stateless mode for legacy MCP clients. Modern
2026-07-28 clients are sessionless at the protocol level and are handled by
FastMCP 4 / MCP Python SDK 2 without a protocol session.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any
from urllib.parse import urlsplit

from ..auth import auth_requested
from .env import parse_env_list

# Default HTTP deployments to stateless transport semantics. This removes
# Mcp-Session-Id affinity for legacy clients too, which is important for Vercel,
# Cloud Run, multi-worker Uvicorn, and other horizontally scaled deployments.
os.environ.setdefault("FASTMCP_STATELESS_HTTP", "true")

logger = logging.getLogger(__name__)

_mcp_server = None


def _parse_env_list(value: str) -> list[str]:
    """Accept either a JSON array or a comma-separated allowlist."""
    return parse_env_list(value)


def _host_from_urlish(value: str) -> str:
    """Extract a hostname from a host or URL-like environment value."""
    raw = value.strip()
    if not raw:
        return ""
    parsed = urlsplit(raw if "://" in raw else f"https://{raw}")
    return parsed.hostname or ""


def _vercel_allowed_hosts() -> list[str]:
    """Return the exact Vercel public hosts exposed for this deployment."""
    hosts: list[str] = []
    for name in (
        "VERCEL_URL",
        "VERCEL_BRANCH_URL",
        "VERCEL_PROJECT_PRODUCTION_URL",
    ):
        host = _host_from_urlish(os.environ.get(name, ""))
        if host and host not in hosts:
            hosts.append(host)
    return hosts


def _configure_fastmcp_http_security() -> None:
    """Configure FastMCP Host/Origin protection for direct and proxied HTTP.

    Explicit MCP_ALLOWED_HOSTS / MCP_ALLOWED_ORIGINS remain authoritative. On
    Vercel, append the exact deployment hosts supplied by Vercel so FastMCP does
    not mistake the platform's loopback ASGI server address for a local-only
    deployment and reject the public Host header with HTTP 421.
    """
    hosts = _parse_env_list(os.environ.get("MCP_ALLOWED_HOSTS", ""))
    origins = _parse_env_list(os.environ.get("MCP_ALLOWED_ORIGINS", ""))

    # Enterprise auth: the canonical resource host must pass FastMCP's Host guard
    # (avoids HTTP 421 behind an ingress / reverse proxy).
    auth_host = _host_from_urlish(os.environ.get("MCP_AUTH_RESOURCE_URL", ""))
    if auth_host and auth_host not in hosts:
        hosts.append(auth_host)

    if os.environ.get("VERCEL") == "1":
        for host in _vercel_allowed_hosts():
            if host not in hosts:
                hosts.append(host)

    if hosts:
        os.environ["FASTMCP_HTTP_ALLOWED_HOSTS"] = json.dumps(hosts)
    else:
        os.environ.pop("FASTMCP_HTTP_ALLOWED_HOSTS", None)

    if origins:
        os.environ["FASTMCP_HTTP_ALLOWED_ORIGINS"] = json.dumps(origins)
    else:
        os.environ.pop("FASTMCP_HTTP_ALLOWED_ORIGINS", None)

    if hosts or origins:
        os.environ["FASTMCP_HTTP_HOST_ORIGIN_PROTECTION"] = "true"
    else:
        os.environ["FASTMCP_HTTP_HOST_ORIGIN_PROTECTION"] = "auto"


_configure_fastmcp_http_security()


def _guard_enterprise_auth_platform() -> None:
    """Refuse enterprise auth on Vercel: static PRM files would shadow live metadata."""
    if os.environ.get("VERCEL") == "1" and auth_requested():
        raise RuntimeError(
            "MCP_AUTH_MODE is not supported on Vercel (public/.well-known is static and "
            "would advertise no authorization server). Deploy with Docker or Helm."
        )


_guard_enterprise_auth_platform()


def get_mcp_cache_policy() -> dict[str, Any]:
    """Return FastMCP 4 server-wide SEP-2549 cache policy.

    The policy is intentionally public because UML-MCP's tools, prompts, resource
    catalog and documentation resources are deployment metadata rather than
    authorization-specific data.
    """
    if auth_requested():
        # Authenticated responses must never be stored by shared caches.
        return {"cache_ttl": 300, "cache_scope": "private"}
    return {"cache_ttl": 300, "cache_scope": "public"}


def create_mcp_server():
    """Create and configure the server with all tools, resources, and prompts."""
    from ..prompts.diagram_prompts import register_diagram_prompts
    from ..resources.diagram_resources import register_diagram_resources
    from ..server.fastmcp_wrapper import FastMCP
    from ..tools.diagram_tools import register_diagram_tools
    from ..tools.schema_compat import install_schema_compat
    from .config import MCP_SETTINGS

    logger.info("Creating MCP server: %s", MCP_SETTINGS.server_name)
    server = FastMCP(
        MCP_SETTINGS.server_name,
        version=MCP_SETTINGS.version,  # else initialize reports FastMCP's own version
        **get_mcp_cache_policy(),
    )

    from ..plugins.loader import load_plugins

    load_plugins()  # before registration: plugin tools/diagram types join the catalog
    tool_names = register_diagram_tools(server)
    resource_names = register_diagram_resources(server)
    prompt_names = register_diagram_prompts(server)
    install_schema_compat(server)

    MCP_SETTINGS.tools = tool_names
    MCP_SETTINGS.prompts = prompt_names
    MCP_SETTINGS.resources = resource_names

    logger.info(
        "MCP server created with %s tools, %s prompts, and %s resources",
        len(MCP_SETTINGS.tools),
        len(MCP_SETTINGS.prompts),
        len(MCP_SETTINGS.resources),
    )
    return server


def get_mcp_server():
    """Get the singleton MCP server instance."""
    global _mcp_server
    if _mcp_server is None:
        _mcp_server = create_mcp_server()
    return _mcp_server


def main():
    """Entry point for the mcp-server console script."""
    from .cli import run

    run()


def start_server(transport="stdio", host=None, port=None):
    """Start the MCP server with stdio or HTTP transport."""
    server = get_mcp_server()

    if transport == "stdio":
        server.run()
    elif transport == "http":
        if auth_requested():
            # FastMCP's own HTTP server bypasses app.py (and therefore the auth
            # middleware). Never serve an unauthenticated /mcp when auth is configured.
            raise SystemExit(
                "MCP_AUTH_MODE requires the ASGI app: run `uvicorn app:app` "
                "(the Docker image and Helm chart already do)."
            )
        if not host or not port:
            raise ValueError("Host and port must be specified for HTTP transport")
        if hasattr(server, "run_http"):
            server.run_http(host=host, port=port)
        else:
            server.run(transport="http", host=host, port=port)
    else:
        raise ValueError(f"Unsupported transport: {transport}")
