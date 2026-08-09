"""
Core MCP server implementation.

The HTTP transport defaults to stateless mode for legacy MCP clients. Modern
2026-07-28 clients are sessionless at the protocol level and are handled by
FastMCP 4 / MCP Python SDK 2 without a protocol session.
"""

import logging
import os

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


def get_mcp_cache_policy() -> dict[str, object]:
    """Return FastMCP 4 server-wide SEP-2549 cache policy.

    FastMCP 4.0.0b1 exposes cache hints as ``cache_ttl`` (seconds) and
    ``cache_scope`` constructor arguments. The policy is intentionally public
    because UML-MCP's tools, prompts, resource catalog and documentation
    resources are deployment metadata rather than authorization-specific data.

    FastMCP applies this uniform hint to every MCP 2026 cacheable method:
    ``tools/list``, ``prompts/list``, ``resources/list``,
    ``resources/templates/list``, ``resources/read`` and ``server/discover``.
    Legacy protocol responses are unaffected.
    """
    return {"cache_ttl": 300, "cache_scope": "public"}


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
        **get_mcp_cache_policy(),
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
