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


def test_view_requests_no_nested_frame_domains():
    """Plugin pages load through ``srcdoc``, so the CSP asks for no frame domains."""
    from mcp_core.apps.diagram_viewer import diagram_viewer_html

    listed, contents = _listed_and_read()
    for ui in [listed["ui"], *(c["ui"] for c in contents)]:
        assert not ui.get("csp", {}).get("frameDomains")
    page = diagram_viewer_html()
    assert "pluginFrame.srcdoc" in page
    assert "pluginFrame.src =" not in page


def test_plugin_pages_open_https_links_through_the_host():
    """A plugin page posts uml-mcp/open-link; the viewer forwards only https URLs."""
    from mcp_core.apps.diagram_viewer import diagram_viewer_html

    page = diagram_viewer_html()
    handler = page[page.index('packet.type === "uml-mcp/open-link"') :][:400]
    assert "/^https:" in handler and "openLink(packet.url)" in handler
