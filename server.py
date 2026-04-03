#!/usr/bin/env python3
"""
Canonical MCP server entry point for UML diagram generation.

Uses mcp_core (tools, config, Kroki) for consistent diagram generation.
Run with: python server.py [--transport stdio|http] [--host 127.0.0.1] [--port 8000]
Or with FastMCP CLI: fastmcp run server.py / fastmcp run fastmcp.json

The ``mcp`` symbol is resolved lazily via ``__getattr__`` so that merely
importing this module does not trigger server construction or write to
stdout (important for stdio transport where stdout carries JSON-RPC).
"""

from mcp_core.core.server import main


def __getattr__(name: str):
    """Lazy-resolve the ``mcp`` attribute on first access."""
    if name == "mcp":
        from mcp_core.core.server import get_mcp_server

        mcp = get_mcp_server()
        globals()["mcp"] = mcp
        return mcp
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if __name__ == "__main__":
    main()
