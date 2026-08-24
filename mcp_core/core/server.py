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

# Default HTTP deployments to stateless transport semantics. This removes
# Mcp-Session-Id affinity for legacy clients too, which is important for Vercel,
# Cloud Run, multi-worker Uvicorn, and other horizontally scaled deployments.
os.environ.setdefault("FASTMCP_STATELESS_HTTP", "true")

logger = logging.getLogger(__name__)

_mcp_server = None


def _parse_env_list(value: str) -> list[str]:
    """Accept either a JSON array or a comma-separated allowlist."""
    raw = value.strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            decoded = None
        if isinstance(decoded, list):
            return [str(item).strip() for item in decoded if str(item).strip()]
    return [item.strip() for item in raw.split(",") if item.strip()]


def _configure_fastmcp_http_security() -> None:
    """Map UML-MCP security env vars to FastMCP's native request guard.

    With no explicit allowlists FastMCP uses ``auto`` protection, which protects
    localhost-bound direct servers without breaking reverse-proxy/serverless hosts.
    Providing MCP_ALLOWED_HOSTS and/or MCP_ALLOWED_ORIGINS enables strict checking.
    """
    hosts = _parse_env_list(os.environ.get("MCP_ALLOWED_HOSTS", ""))
    origins = _parse_env_list(os.environ.get("MCP_ALLOWED_ORIGINS", ""))

    if hosts:
        os.environ["FASTMCP_HTTP_ALLOWED_HOSTS"] = json.dumps(hosts)
    if origins:
        os.environ["FASTMCP_HTTP_ALLOWED_ORIGINS"] = json.dumps(origins)

    if hosts or origins:
        os.environ["FASTMCP_HTTP_HOST_ORIGIN_PROTECTION"] = "true"
    else:
        os.environ.setdefault("FASTMCP_HTTP_HOST_ORIGIN_PROTECTION", "auto")


_configure_fastmcp_http_security()


def get_mcp_cache_policy() -> dict[str, Any]:
    """Return FastMCP 4 server-wide SEP-2549 cache policy.

    The policy is intentionally public because UML-MCP's tools, prompts, resource
    catalog and documentation resources are deployment metadata rather than
    authorization-specific data.
    """
    return {"cache_ttl": 300, "cache_scope": "public"}


def create_mcp_server():
    """Create and configure the server with all tools, resources, and prompts."""
    from ..prompts.diagram_prompts import register_diagram_prompts
    from ..resources.diagram_resources import register_diagram_resources
    from ..server.fastmcp_wrapper import FastMCP
    from ..tools.diagram_tools import register_diagram_tools
    from .config import MCP_SETTINGS

    logger.info("Creating MCP server: %s", MCP_SETTINGS.server_name)
    server = FastMCP(
        MCP_SETTINGS.server_name,
        **get_mcp_cache_policy(),
    )

    tool_names = register_diagram_tools(server)
    resource_names = register_diagram_resources(server)
    prompt_names = register_diagram_prompts(server)

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
        if not host or not port:
            raise ValueError("Host and port must be specified for HTTP transport")
        if hasattr(server, "run_http"):
            server.run_http(host=host, port=port)
        else:
            server.run(transport="http", host=host, port=port)
    else:
        raise ValueError(f"Unsupported transport: {transport}")
