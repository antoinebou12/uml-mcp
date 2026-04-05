"""
MCP Core package. Submodules load on demand; avoid eager imports so optional
entrypoints (e.g. Vercel server-card generation) do not pull the full stack until needed.
"""

__all__ = [
    "MCP_SETTINGS",
    "create_mcp_server",
    "get_mcp_server",
    "start_server",
    "generate_diagram",
]


def __getattr__(name: str):
    if name == "MCP_SETTINGS":
        from .config import MCP_SETTINGS

        return MCP_SETTINGS
    if name in ("create_mcp_server", "get_mcp_server", "start_server"):
        from . import server

        return getattr(server, name)
    if name == "generate_diagram":
        from .utils import generate_diagram

        return generate_diagram
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
