"""MCP Apps diagram viewer: discover, tools/list meta, resources/read, SVG sanitize."""

from __future__ import annotations

import pytest
from fastmcp import Client, FastMCP
from fastmcp.apps import UI_EXTENSION_ID, UI_MIME_TYPE

from mcp_core.apps.diagram_viewer import (
    DIAGRAM_VIEWER_DESCRIPTION,
    DIAGRAM_VIEWER_URI,
    diagram_viewer_domain,
    diagram_viewer_html,
    register_diagram_viewer,
)
from mcp_core.apps.svg_sanitize import sanitize_svg
from mcp_core.tools.diagram_tools import register_diagram_tools

# ---------------------------------------------------------------- SVG sanitizer


def test_sanitize_svg_removes_script_and_event_handlers() -> None:
    dirty = """
    <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">
      <script>alert(1)</script>
      <rect width="10" height="10" onclick="evil()" fill="blue"/>
      <a href="javascript:alert(2)"><text>x</text></a>
      <foreignObject width="10" height="10"><body xmlns="http://www.w3.org/1999/xhtml">
        <p>nope</p>
      </body></foreignObject>
    </svg>
    """
    clean = sanitize_svg(dirty)
    assert "script" not in clean.lower()
    assert "onclick" not in clean.lower()
    assert "javascript:" not in clean.lower()
    assert "foreignobject" not in clean.lower()
    assert "rect" in clean.lower()
    assert 'fill="blue"' in clean or "fill='blue'" in clean or "fill=" in clean


def test_sanitize_svg_keeps_ordinary_shapes() -> None:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<circle cx="5" cy="5" r="4" fill="red"/>'
        "</svg>"
    )
    assert "circle" in sanitize_svg(svg)
    assert "fill" in sanitize_svg(svg)


def test_sanitize_svg_rejects_unparseable() -> None:
    assert sanitize_svg("not svg at all <<<") == ""


def test_viewer_html_is_self_contained() -> None:
    html = diagram_viewer_html()
    assert "text/html" not in html[:50]  # raw document, not a MIME wrapper
    assert "<!DOCTYPE html>" in html
    assert "cdn." not in html.lower()
    assert "ui/initialize" in html
    assert "ui/notifications/tool-result" in html
    assert "ui/notifications/tool-input" in html
    assert "sanitizeSvg" in html
    assert "content_base64" in html
    assert "zoomIn" in html and "Playground" in html
    assert 'name: "rerender_diagram"' in html or "rerender_diagram" in html
    assert "tools/call" in html


def test_viewer_html_embeds_per_type_theme_and_format_data() -> None:
    import json
    import re

    html = diagram_viewer_html()
    assert "__UML_MCP_VIEWER_DATA__" not in html
    # The only <svg> in the page must be the rendered diagram (tests locate it by tag).
    assert "<svg" not in html
    match = re.search(r"var DATA = (\{.*?\});\n", html)
    assert match
    data = json.loads(match.group(1).replace("<\\/", "</"))
    assert "cerulean" in data["themes"]["plantuml"]
    assert "dark" in data["themes"]["mermaid"]
    assert data["types"]["sequence"]["theme_family"] == "plantuml"
    assert data["types"]["mermaid"]["theme_family"] == "mermaid"
    assert data["types"]["graphviz"]["theme_family"] == ""
    assert set(data["types"]["class"]["formats"]) <= {"png", "svg", "jpeg"}
    assert "cyborg" in data["dark_themes"]


def test_default_app_domain_is_the_submission_host(monkeypatch) -> None:
    monkeypatch.delenv("MCP_APP_DOMAIN", raising=False)
    assert diagram_viewer_domain() == "https://uml-mcp.antoineboucher.info"


# ---------------------------------------------------------------- protocol surface


@pytest.fixture
def apps_server() -> FastMCP:
    # Decorators already populated the tool registry at import time.
    server = FastMCP("mcp-apps-viewer-test", cache_ttl=300, cache_scope="public")
    register_diagram_tools(server)
    register_diagram_viewer(server)
    return server


@pytest.mark.asyncio
async def test_discover_advertises_ui_extension(apps_server: FastMCP) -> None:
    async with Client(apps_server, timeout=10) as client:
        discovery = await client.session.send_discover("2026-07-28")
        extensions = discovery["capabilities"].get("extensions") or {}
        assert UI_EXTENSION_ID in extensions


@pytest.mark.asyncio
async def test_render_tools_link_viewer_in_meta(apps_server: FastMCP) -> None:
    async with Client(apps_server, timeout=10) as client:
        tools = {t.name: t for t in await client.list_tools()}
        for name in ("generate_uml", "generate_uml_image", "generate_uml_batch"):
            tool = tools[name]
            meta = tool.meta or {}
            ui = meta.get("ui") or {}
            assert ui.get("resourceUri") == DIAGRAM_VIEWER_URI, name
            assert set(ui.get("visibility") or []) == {"model", "app"}, name
        # App-only re-render helper (host hides from the model; FastMCP still lists it).
        assert "rerender_diagram" in tools
        rerender_ui = (tools["rerender_diagram"].meta or {}).get("ui") or {}
        assert rerender_ui.get("resourceUri") == DIAGRAM_VIEWER_URI
        assert rerender_ui.get("visibility") == ["app"]
        assert tools["rerender_diagram"].annotations.read_only_hint is True
        # Checks and catalog lookups stay without Apps meta (no widget per call);
        # the viewer still calls validate_uml itself from the Source tab.
        for name in ("validate_uml", "list_diagram_types"):
            meta = (tools[name].meta or {}) if name in tools else {}
            assert "ui" not in meta or not (meta.get("ui") or {}).get("resourceUri")


@pytest.mark.asyncio
async def test_viewer_resource_read_has_apps_mime(apps_server: FastMCP) -> None:
    async with Client(apps_server, timeout=10) as client:
        resources = {str(r.uri): r for r in await client.list_resources()}
        assert DIAGRAM_VIEWER_URI in resources
        listed = resources[DIAGRAM_VIEWER_URI]
        assert listed.mime_type == UI_MIME_TYPE
        meta = listed.meta or {}
        ui = meta.get("ui") or {}
        csp = ui.get("csp") or {}
        assert csp.get("connectDomains") == []
        assert "data:" in (csp.get("resourceDomains") or [])
        assert ui["domain"] == diagram_viewer_domain()

        contents = await client.read_resource(DIAGRAM_VIEWER_URI)
        assert contents
        assert contents[0].mime_type == UI_MIME_TYPE
        # The v2 MCP Apps description lives in the standard resource field.
        # The compatibility checker incorrectly requires a v1 widgetDescription key.
        assert listed.description == DIAGRAM_VIEWER_DESCRIPTION
        assert "<!DOCTYPE html>" in (contents[0].text or "")
        assert "cdn." not in (contents[0].text or "").lower()


@pytest.mark.asyncio
async def test_render_invocation_labels(apps_server: FastMCP) -> None:
    async with Client(apps_server) as client:
        tools = {t.name: t for t in await client.list_tools()}
        for name in ("generate_uml", "generate_uml_image", "rerender_diagram"):
            meta = tools[name].meta
            assert meta["openai/toolInvocation/invoking"] == "Rendering diagram…"
            assert meta["openai/toolInvocation"] == {
                "invoking": "Rendering diagram…",
                "invoked": "Diagram rendered",
            }
            assert meta["openai/toolInvocation/invoked"] == "Diagram rendered"
        assert tools["generate_uml_batch"].meta["openai/toolInvocation"] == {
            "invoking": "Rendering diagrams…",
            "invoked": "Diagrams rendered",
        }


@pytest.mark.asyncio
async def test_production_discovery_identity(monkeypatch) -> None:
    from mcp_core.core.config import MCP_SETTINGS
    from mcp_core.core.server import create_mcp_server

    monkeypatch.setattr("mcp_core.server.fastmcp_wrapper.FastMCP", FastMCP)
    server = create_mcp_server()
    async with Client(server) as client:
        discovery = await client.session.send_discover("2026-07-28")
        info = discovery["_meta"]["io.modelcontextprotocol/serverInfo"]
        assert info["name"] == MCP_SETTINGS.server_name
        assert info["version"] == MCP_SETTINGS.version
        assert info["title"] == MCP_SETTINGS.display_name
        assert info["description"] == MCP_SETTINGS.description
        assert info["websiteUrl"] == "https://antoinebou12.github.io/uml-mcp/"
        assert info["icons"][0]["sizes"] == ["any"]
        assert info["icons"][0]["mimeType"] == "image/svg+xml"
        assert UI_EXTENSION_ID in discovery["capabilities"]["extensions"]


def test_app_view_domain_validation(monkeypatch) -> None:
    monkeypatch.setenv("MCP_APP_DOMAIN", "https://uml-mcp.vercel.app")
    assert diagram_viewer_domain() == "https://uml-mcp.vercel.app"
    for invalid in (
        "http://example.org",
        "https://example.org/mcp",
        "https://user:pw@example.org",
        "not-a-domain",
        "https://example.org:abc",
        "https://example.org:65536",
        "https://example.org:0",
        "https://example.org:",
        "https://[invalid",
        "https://exa mple.org",
        "https://exam\tple.org",
        "https://bad<host>",
        "https://-invalid.example",
        "https://example.org?",
        "https://example.org#",
        "https://example.org//",
    ):
        monkeypatch.setenv("MCP_APP_DOMAIN", invalid)
        with pytest.raises(ValueError, match="one HTTPS origin"):
            diagram_viewer_domain()


@pytest.mark.parametrize(
    "origin",
    [
        "https://uml-mcp.vercel.app",
        "https://fast-steel-xf470.run.mcp-use.com",
        "https://example.org:8443",
        "https://[::1]:8443",
    ],
)
@pytest.mark.asyncio
async def test_configured_origin_reaches_resource_wire_metadata(monkeypatch, origin):
    monkeypatch.setenv("MCP_APP_DOMAIN", origin)
    server = FastMCP("origin-test")
    register_diagram_viewer(server)
    async with Client(server) as client:
        resources = await client.list_resources()
        resource = next(r for r in resources if str(r.uri) == DIAGRAM_VIEWER_URI)
        assert resource.meta["ui"]["domain"] == origin
        assert resource.description == DIAGRAM_VIEWER_DESCRIPTION
        assert resource.mime_type == UI_MIME_TYPE


def test_tool_result_schema_has_inline_limits() -> None:
    from mcp_core.tools.schemas import DiagramResult

    props = DiagramResult.model_json_schema()["properties"]
    inline = props["content_base64"]
    assert any(v.get("maxLength") == 48_000 for v in inline.get("anyOf", [inline]))
    assert props["code"]["maxLength"] == 12_000


def test_html_backed_mermaid_labels_become_portable_svg_text():
    from mcp_core.apps.svg_sanitize import flatten_svg_labels

    svg = '<svg xmlns="http://www.w3.org/2000/svg"><g transform="translate(20,30)"><foreignObject width="120" height="48"><div xmlns="http://www.w3.org/1999/xhtml"><p>Processing</p><p>Ready</p><script>alert(1)</script></div></foreignObject></g></svg>'
    clean = flatten_svg_labels(svg)
    assert "foreignObject" not in clean
    assert "Processing" in clean and "Ready" in clean and "alert" not in clean
    assert 'transform="translate(20,30)"' in clean
    assert "tspan" in clean
