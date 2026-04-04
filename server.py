#!/usr/bin/env python3
"""
Canonical MCP server entry point for UML diagram generation.

Uses mcp_core (tools, config, Kroki) for consistent diagram generation.
Run with: python server.py [--transport stdio|http] [--host 127.0.0.1] [--port 8000]
Or with FastMCP CLI: fastmcp run server.py / fastmcp run fastmcp.json
"""

import os

# Redirect fd 1 to stderr during imports to prevent any stdout writes
# (Python print() or C-level) from polluting the MCP stdio transport.
_saved_fd = os.dup(1)
os.dup2(2, 1)
try:
    from mcp_core.core.server import get_mcp_server, main

    # Expose for FastMCP CLI (fastmcp run server.py / fastmcp run fastmcp.json)
    mcp = get_mcp_server()
finally:
    # Restore stdout so the MCP JSON-RPC transport works correctly.
    os.dup2(_saved_fd, 1)
    os.close(_saved_fd)

if __name__ == "__main__":
    main()
