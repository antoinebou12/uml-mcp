"""Architecture output reaches the MCP Apps result contract."""

import base64
import json

import pytest

from mcp_core.plugins.architecture import EXAMPLE, ArchitectureRenderer


def test_architecture_html_and_tsx_share_geometry():
    renderer = ArchitectureRenderer()
    page = renderer.render("architecture", EXAMPLE, "html")
    component = renderer.render("architecture", EXAMPLE, "tsx")
    assert page.mime_type == "text/html"
    assert component.mime_type == "text/tsx"
    for value in (b"M148 150 L306 150", b"HTTPS", b"Application"):
        assert value in page.content
        assert value in component.content
    assert b"woff2" not in component.content


def test_architecture_rejects_overlapping_nodes():
    spec = json.loads(EXAMPLE)
    spec["nodes"][1]["cx"] = 115
    assert (
        "spacing"
        in ArchitectureRenderer().validate("architecture", json.dumps(spec))[0]
    )


async def test_architecture_mcp_app_packet(monkeypatch):
    from fastmcp import Client, FastMCP
    from fastmcp.apps import UI_EXTENSION_ID

    from mcp_core.apps.diagram_viewer import register_diagram_viewer
    from mcp_core.core.config import MCP_SETTINGS, DiagramType
    from mcp_core.plugins.loader import RENDERERS
    from mcp_core.tools.diagram_tools import register_diagram_tools

    monkeypatch.setitem(RENDERERS, "architecture", ArchitectureRenderer())
    monkeypatch.setitem(
        MCP_SETTINGS.diagram_types,
        "architecture",
        DiagramType(
            description="Architecture diagram",
            backend="plugin:architecture",
            formats=["html", "tsx"],
        ),
    )
    from mcp.client.extension import ClientExtension

    extension = ClientExtension()
    extension.identifier = UI_EXTENSION_ID
    server = FastMCP("architecture-preview")
    register_diagram_tools(server)
    register_diagram_viewer(server)
    async with Client(server, extensions=[extension]) as client:
        result = await client.call_tool(
            "generate_uml",
            {"diagram_type": "architecture", "code": EXAMPLE, "output_format": "html"},
        )
        assert not result.is_error
        packet = result.structured_content
        assert packet is not None
        assert packet["mime_type"].startswith("text/html")
        assert b"Application" in base64.b64decode(packet["content_base64"])


def test_elbow_routes_below_source_labels():
    spec = json.loads(EXAMPLE)
    spec["groups"] = []
    spec["nodes"][2]["top"] = 350
    renderer = ArchitectureRenderer()
    assert renderer.validate("architecture", json.dumps(spec)) == []
    result = renderer.render("architecture", json.dumps(spec), "html")
    assert b"M342 226 L342 325 L487 325 L487 344" in result.content


@pytest.mark.parametrize(
    "via, message",
    [
        ([[342, 200], [487, 200]], "crosses node app"),
        ([[342, -10], [487, -10]], "leaves the canvas"),
        ([[400, 300]], "orthogonal"),
        ([[342]], "x and y"),
    ],
)
def test_invalid_custom_routes_rejected(via, message):
    spec = json.loads(EXAMPLE)
    spec["groups"] = []
    spec["nodes"][2]["top"] = 350
    spec["edges"][1]["via"] = via
    assert (
        message in ArchitectureRenderer().validate("architecture", json.dumps(spec))[0]
    )


def test_custom_route_avoids_middle_node():
    spec = json.loads(EXAMPLE)
    spec["height"] = 800
    spec["groups"] = []
    spec["nodes"][2]["top"] = 600
    spec["nodes"].append({"id": "queue", "name": "Queue", "cx": 342, "top": 350})
    renderer = ArchitectureRenderer()
    assert (
        "crosses node queue" in renderer.validate("architecture", json.dumps(spec))[0]
    )
    spec["edges"][1]["via"] = [[342, 280], [240, 280], [240, 560], [487, 560]]
    assert renderer.validate("architecture", json.dumps(spec)) == []


@pytest.mark.parametrize(
    "code, message",
    [
        ("not json", "must be JSON"),
        ("[1, 2]", "JSON object"),
        ('{"nodes": [{"id": "a", "name": "A"}]}', "needs cx and top"),
        ('{"nodes": [{"id": "a", "cx": 200, "top": 100}]}', "needs a name"),
        (
            (
                '{"nodes": [{"id": "a", "name": "A", "cx": 200, "top": 100}],'
                ' "groups": [{"name": "G", "nodes": ["b"]}]}'
            ),
            "unknown nodes",
        ),
        (
            (
                '{"nodes": [{"id": "a", "name": "A", "cx": 200, "top": 100}],'
                ' "edges": [{"source": "a"}]}'
            ),
            "source and target",
        ),
    ],
)
def test_malformed_sources_get_readable_errors(code, message):
    errors = ArchitectureRenderer().validate("architecture", code)
    assert errors and message in errors[0]
