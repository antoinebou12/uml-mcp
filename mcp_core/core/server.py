"""
Core MCP server implementation.

The HTTP transport defaults to stateless mode for legacy MCP clients. Modern
2026-07-28 clients are sessionless at the protocol level and are handled by
FastMCP 4 / MCP Python SDK 2 without a protocol session.
"""

import logging
import os
from typing import Any

# Default HTTP deployments to stateless transport semantics. This removes
# Mcp-Session-Id affinity for legacy clients too, which is important for Vercel,
# Cloud Run, multi-worker Uvicorn, and other horizontally scaled deployments.
# Operators can explicitly set FASTMCP_STATELESS_HTTP=false if they need a
# legacy stateful deployment.
os.environ.setdefault("FASTMCP_STATELESS_HTTP", "true")

# Get logger
logger = logging.getLogger(__name__)

# Create a singleton MCP server instance
_mcp_server = None


def get_mcp_cache_hints() -> dict[str, Any]:
    """Return MCP 2026-07-28 cache hints for deterministic discovery data.

    UML-MCP's tool, prompt, resource, and discovery catalogs are deployment
    metadata rather than per-user state, so they are safe to cache publicly.
    Resource reads are also static catalog/documentation resources in this
    server and receive a shorter TTL to make future content changes visible
    quickly after a deployment.

    The Python SDK only emits these hints on protocol revisions that support
    SEP-2549; legacy MCP responses remain unchanged.
    """
    try:
        from mcp.server.caching import CacheHint
    except ImportError:
        # Tests using the lightweight FastMCP mock do not need the MCP v2
        # caching classes. Returning plain metadata keeps the policy testable
        # while production always uses CacheHint objects from MCP SDK 2.x.
        return {
            "tools/list": {"ttl_ms": 300_000, "scope": "public"},
            "prompts/list": {"ttl_ms": 300_000, "scope": "public"},
            "resources/list": {"ttl_ms": 300_000, "scope": "public"},
            "resources/templates/list": {"ttl_ms": 300_000, "scope": "public"},
            "resources/read": {"ttl_ms": 60_000, "scope": "public"},
            "server/discover": {"ttl_ms": 300_000, "scope": "public"},
        }

    return {
        "tools/list": CacheHint(ttl_ms=300_000, scope="public"),
        "prompts/list": CacheHint(ttl_ms=300_000, scope="public"),
        "resources/list": CacheHint(ttl_ms=300_000, scope="public"),
        "resources/templates/list": CacheHint(ttl_ms=300_000, scope="public"),
        "resources/read": CacheHint(ttl_ms=60_000, scope="public"),
        "server/discover": CacheHint(ttl_ms=300_000, scope="public"),
    }


def create_mcp_server():
    """Create and configure the MCP server with all tools and resources.

    Returns:
        Configured FastMCP server instance
    """
    # Lazy import to avoid circular dependencies
    from ..prompts.diagram_prompts import register_diagram_prompts
    from ..resources.diagram_resources import register_diagram_resources
    from ..server.fastmcp_wrapper import FastMCP
    from ..tools.diagram_tools import register_diagram_tools
    from .config import MCP_SETTINGS

    # FastMCP 4 negotiates both the modern 2026-07-28 sessionless protocol and
    # legacy protocol revisions on the same server. Transport-level stateless
    # behavior for legacy HTTP clients is configured by FASTMCP_STATELESS_HTTP.
    logger.info(f"Creating MCP server: {MCP_SETTINGS.server_name}")
    server = FastMCP(
        MCP_SETTINGS.server_name,
        cache_hints=get_mcp_cache_hints(),
    )

    # Register all tools, resources, and prompts
    tool_names = register_diagram_tools(server)
    resource_names = register_diagram_resources(server)
    prompt_names = register_diagram_prompts(server)

    # Update settings with registered tools and prompts
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
    """Get the singleton MCP server instance.

    Returns:
        FastMCP server instance
    """
    global _mcp_server
    if _mcp_server is None:
        _mcp_server = create_mcp_server()
    return _mcp_server


def main():
    """Entry point for the mcp-server console script (argparse, Rich UI, then start server)."""
    from .cli import run

    run()


def start_server(transport="stdio", host=None, port=None):
    """Start the MCP server with the specified transport.

    Args:
        transport (str): Transport protocol to use ('stdio' or 'http')
        host (str, optional): Host address for HTTP transport
        port (int, optional): Port number for HTTP transport
    """
    server = get_mcp_server()

    if transport == "stdio":
        server.run()
    elif transport == "http":
        if not host or not port:
            raise ValueError("Host and port must be specified for HTTP transport")
        # FastMCP v3+ uses run(transport="http"). FASTMCP_STATELESS_HTTP is
        # intentionally set above so the same setting also applies when this
        # server is embedded through http_app() in app.py.
        if hasattr(server, "run_http"):
            server.run_http(host=host, port=port)
        else:
            server.run(transport="http", host=host, port=port)
    else:
        raise ValueError(f"Unsupported transport: {transport}")
