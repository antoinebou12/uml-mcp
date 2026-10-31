import base64
from types import SimpleNamespace

from mcp_core.tools import tool_decorator as tools


def sample():
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="80" height="40"><text x="1" y="25">Diagram</text></svg>'
    return {
        "code": "graph TD; A-->B",
        "content_base64": base64.b64encode(svg).decode(),
        "mime_type": "image/svg+xml",
        "url": "https://example.com/a.svg",
        "diagram_type": "mermaid",
    }


def test_apps_receive_one_view_without_duplicate_image(monkeypatch):
    monkeypatch.setattr(tools, "_client_uses_apps", lambda: True)
    result = tools._as_mcp_tool_result("generate_uml_image", sample())
    assert [c.type for c in result.content] == ["text"]
    assert "https://" not in result.content[0].text
    assert result.structured_content["content_base64"]


def test_plain_clients_receive_png_and_clickable_links(monkeypatch):
    monkeypatch.setattr(tools, "_client_uses_apps", lambda: False)
    result = tools._as_mcp_tool_result("generate_uml_image", sample())
    assert [c.type for c in result.content] == ["text", "image"]
    assert result.content[1].mime_type == "image/png"
    assert "https://example.com/a.svg" in result.content[0].text
    assert "![diagram]" not in result.content[0].text


def test_apps_are_detected_from_capabilities(monkeypatch):
    from fastmcp.apps import UI_EXTENSION_ID
    from fastmcp.server import dependencies

    context = SimpleNamespace(
        session=SimpleNamespace(
            client_capabilities=SimpleNamespace(extensions={UI_EXTENSION_ID: {}})
        )
    )
    monkeypatch.setattr(dependencies, "get_context", lambda: context)
    assert tools._client_uses_apps()
    context.session.client_capabilities.extensions = {}
    assert not tools._client_uses_apps()


def test_every_batch_item_keeps_a_bounded_thumbnail():
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800"><rect width="1200" height="800" fill="white"/><text x="20" y="40">Readable label</text></svg>'
    encoded = base64.b64encode(
        svg.replace(b"</svg>", b"<!--" + b"x" * 18000 + b"--></svg>")
    ).decode()
    result = tools._bounded_batch_result(
        {
            "results": [
                {
                    "content_base64": encoded,
                    "mime_type": "image/svg+xml",
                    "code": "source",
                }
                for i in range(4)
            ]
        }
    )
    rows = result["results"]
    assert all(
        row["content_base64"] and row["mime_type"] == "image/png" for row in rows
    )
    assert sum(len(row["content_base64"]) for row in rows) <= 48000


def test_apps_batch_summary_reports_failures_instead_of_claiming_ready(monkeypatch):
    monkeypatch.setattr(tools, "_client_uses_apps", lambda: True)
    result = tools._as_mcp_tool_result(
        "generate_uml_batch",
        {"results": [sample(), {"success": False, "error": "Cannot load theme"}]},
    )
    assert "1 failed" in result.content[0].text
    assert "ready" not in result.content[0].text.lower()
    assert [c.type for c in result.content] == ["text"]
