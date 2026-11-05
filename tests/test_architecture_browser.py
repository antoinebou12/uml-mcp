"""Exercise architecture HTML inside the actual MCP App viewer iframe."""

import base64

import pytest

from mcp_core.apps.diagram_viewer import diagram_viewer_html
from mcp_core.plugins.architecture import EXAMPLE, ArchitectureRenderer

playwright = pytest.importorskip("playwright.sync_api")


def test_architecture_renders_in_mcp_app(tmp_path):
    output = ArchitectureRenderer().render("architecture", EXAMPLE, "html")
    packet = {
        "success": True,
        "diagram_type": "architecture",
        "output_format": "html",
        "mime_type": output.mime_type,
        "content_base64": base64.b64encode(output.content).decode(),
        "code": EXAMPLE,
    }
    with playwright.sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 850})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.set_content(diagram_viewer_html())
        page.evaluate(
            "packet => window.postMessage({jsonrpc:'2.0',method:'ui/notifications/tool-result',params:{structuredContent:packet}}, '*')",
            packet,
        )
        iframe = page.locator("iframe.plugin-frame")
        iframe.wait_for()
        frame = page.frame_locator("iframe.plugin-frame")
        frame.get_by_text("Application", exact=True).wait_for()
        assert frame.locator("svg path[marker-end]").count() == 2
        assert iframe.get_attribute("sandbox") == "allow-scripts"
        assert not errors
        page.screenshot(path=str(tmp_path / "architecture-mcp-app.png"), full_page=True)
        browser.close()
