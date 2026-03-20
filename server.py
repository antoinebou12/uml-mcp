#!/usr/bin/env python3
"""
Canonical MCP server entry point for UML diagram generation.

Uses mcp_core (tools, config, Kroki) for consistent diagram generation.
Run with: python server.py [--transport stdio|http] [--host 127.0.0.1] [--port 8000]
Or with FastMCP CLI: fastmcp run server.py / fastmcp run fastmcp.json

The `mcp` export is resolved lazily so importing this module stays silent on
stdout until the server is explicitly requested.
"""

from mcp_core.core.server import get_mcp_server, main

__all__ = ["get_mcp_server", "main"]


def __getattr__(name):
    """Resolve the FastMCP export lazily to avoid import-time side effects."""
    if name == "mcp":
        return get_mcp_server()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if __name__ == "__main__":
    main()
