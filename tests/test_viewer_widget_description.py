"""The ``ui://`` viewer resource carries a widget description where ChatGPT reads it."""

from __future__ import annotations

import asyncio

import pytest

fastmcp = pytest.importorskip("fastmcp")

from mcp_core.apps.diagram_viewer import (
    DIAGRAM_VIEWER_DESCRIPTION,
    DIAGRAM_VIEWER_URI,
    register_diagram_viewer,
)


def _listed_and_read() -> tuple[dict, list[dict]]:
    server = fastmcp.FastMCP("viewer-meta")
    register_diagram_viewer(server)

    async def run():
        async with fastmcp.Client(server) as client:
            listed = next(
                r
                for r in await client.list_resources()
                if str(r.uri) == DIAGRAM_VIEWER_URI
            )
            contents = await client.read_resource(DIAGRAM_VIEWER_URI)
            return listed.meta or {}, [c.meta or {} for c in contents]

    return asyncio.run(run())


def test_widget_description_is_read_but_not_listed():
    listed, contents = _listed_and_read()
    # off resources/list, so it adds nothing to the connect-time surface
    assert "openai/widgetDescription" not in listed
    assert contents and all(
        c.get("openai/widgetDescription") == DIAGRAM_VIEWER_DESCRIPTION
        for c in contents
    )
    # the MCP Apps ui block (domain and CSP) is identical on the list and the contents
    assert listed["ui"]["domain"].startswith("https://")
    assert all(c["ui"] == listed["ui"] for c in contents)
    assert DIAGRAM_VIEWER_URI.startswith("ui://")
