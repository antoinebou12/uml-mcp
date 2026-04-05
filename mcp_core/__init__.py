"""
MCP (Model Context Protocol) module for diagram generation.
"""

__all__ = ["MCP_SETTINGS"]


def __getattr__(name: str):
    if name == "MCP_SETTINGS":
        from mcp_core.core.config import MCP_SETTINGS

        return MCP_SETTINGS
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
