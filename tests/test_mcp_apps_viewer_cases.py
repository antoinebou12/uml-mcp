"""Browser tests for every result shape the MCP Apps diagram viewer handles.

A fake host page embeds the viewer, answers ``ui/initialize`` with chosen host
capabilities, records every request the view makes, and answers ``tools/call``
from a per-test table. Each test drives one use case end to end.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from mcp_core.apps.diagram_viewer import diagram_viewer_html

playwright = pytest.importorskip("playwright.sync_api")

HOST = """([html, caps, responses]) => {
    window.calls = [];
    window.addEventListener('message', event => {
        const m = event.data;
        if (!m || m.id == null || !m.method) return;
        const reply = body => event.source.postMessage(
            Object.assign({jsonrpc: '2.0', id: m.id}, body), '*');
        if (m.method === 'ui/initialize') {
            return reply({result: {hostCapabilities: caps, hostContext: {}}});
        }
        window.calls.push({method: m.method, params: m.params});
        if (m.method === 'tools/call') {
            const args = m.params.arguments || {};
            const res = responses[m.params.name + ':' + args.output_format + ':' + (args.offset || 0)] || responses[m.params.name];
            return res ? reply({result: res})
                       : reply({error: {code: -32603, message: 'no stub'}});
        }
        if (m.method === 'ui/download-file' && responses['ui/download-file']) {
            return reply({result: responses['ui/download-file']});
        }
        reply({result: {}});
    });
    document.querySelector('iframe').srcdoc = html;
}"""

SEND = (
    "([method, params]) => document.querySelector('iframe').contentWindow"
    ".postMessage({jsonrpc: '2.0', method, params}, '*')"
)


def _svg(label: str) -> str:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="300" height="120">'
        f'<text x="10" y="40">{label}</text></svg>'
    )
    return base64.b64encode(svg.encode()).decode()


def _svg_result(label: str, **extra: Any) -> dict[str, Any]:
    return {
        "structuredContent": {
            "diagram_type": "mermaid",
            "code": "graph TD; A-->B",
            "mime_type": "image/svg+xml",
            "content_base64": _svg(label),
            "output_format": "svg",
            **extra,
        }
    }


@pytest.fixture
def browser() -> Iterator[Any]:
    with playwright.sync_playwright() as pw:
        try:
            chromium = pw.chromium.launch()
        except playwright.Error as exc:
            pytest.skip(f"Playwright Chromium is not available: {exc}")
        try:
            yield chromium
        finally:
            chromium.close()


class Host:
    def __init__(self, browser: Any, caps: dict[str, Any], responses: dict[str, Any]):
        self.page = browser.new_page(viewport={"width": 900, "height": 1100})
        self.page.set_content(
            "<iframe title='Diagram' style='width:860px;height:1000px'></iframe>"
        )
        self.page.evaluate(HOST, [diagram_viewer_html(), caps, responses])
        self.frame = self.page.frame_locator("iframe")
        self.expect = playwright.expect
        self.expect(self.frame.locator("#status")).to_contain_text("Ready")

    def send(self, method: str, params: dict[str, Any]) -> None:
        self.page.evaluate(SEND, [method, params])

    def calls(self, method: str | None = None) -> list[dict[str, Any]]:
        calls = self.page.evaluate("window.calls")
        return [c for c in calls if method is None or c["method"] == method]

    def wait_calls(self, method: str, count: int = 1) -> list[dict[str, Any]]:
        """Wait for the view's postMessage requests to reach the host."""
        self.page.wait_for_function(
            "([m, n]) => window.calls.filter(c => c.method === m).length >= n",
            arg=[method, count],
        )
        return self.calls(method)

    def tool_calls(self, name: str) -> list[dict[str, Any]]:
        return [
            c["params"]["arguments"]
            for c in self.calls("tools/call")
            if c["params"]["name"] == name
        ]


TOOLS = {"serverTools": {}}


def test_tool_error_offers_edit_retry_and_ask_to_fix(browser: Any) -> None:
    host = Host(browser, {**TOOLS, "message": {"text": {}}}, {})
    source = "@startuml\nAlice -> \n@enduml"
    host.send(
        "ui/notifications/tool-input",
        {"arguments": {"diagram_type": "sequence", "code": source}},
    )
    host.send(
        "ui/notifications/tool-result",
        {
            "isError": True,
            "content": [{"type": "text", "text": "Syntax Error? (line 2)"}],
        },
    )
    f = host.frame
    host.expect(f.locator("#status")).to_contain_text("Syntax Error")
    host.expect(f.locator(".notice.error h3")).to_have_text(
        "This diagram did not render"
    )
    host.expect(f.locator("#issueCount")).to_have_text("1")

    f.get_by_role("button", name="Ask assistant to fix").click()
    host.expect(f.get_by_role("button", name="Sent to assistant ✓")).to_be_visible()
    (message,) = host.calls("ui/message")
    text = message["params"]["content"]["text"]
    assert "Syntax Error? (line 2)" in text and "Alice ->" in text
    assert message["params"]["role"] == "user"

    f.get_by_role("button", name="Edit source").click()
    host.expect(f.locator("#sourcePane")).to_be_visible()
    host.expect(f.locator("#sourceEdit")).to_have_value(source)


def test_batch_gallery_switches_and_lazy_loads_previews(browser: Any) -> None:
    host = Host(browser, TOOLS, {"rerender_diagram": _svg_result("Second")})
    items = [
        {"diagram_type": "mermaid", "code": "graph TD; A-->B"},
        {"diagram_type": "mermaid", "code": "graph TD; C-->D", "output_format": "svg"},
        {"diagram_type": "mermaid", "code": "graph TD; ?"},
    ]
    host.send("ui/notifications/tool-input", {"arguments": {"items": items}})
    host.send(
        "ui/notifications/tool-result",
        {
            "structuredContent": {
                "results": [
                    {
                        "index": 0,
                        "diagram_type": "mermaid",
                        "mime_type": "image/svg+xml",
                        "content_base64": _svg("First"),
                        "output_format": "svg",
                        "code": "graph TD; A-->B",
                    },
                    # Over the shared inline budget: bytes and source come from input.
                    {
                        "index": 1,
                        "diagram_type": "mermaid",
                        "url": "https://kroki.io/x",
                    },
                    {"index": 2, "success": False, "error": "Parse error on line 1"},
                ]
            }
        },
    )
    f = host.frame
    cards = f.locator("#gallery .card")
    host.expect(cards).to_have_count(3)
    host.expect(f.locator("#frame svg text")).to_have_text("First")
    host.expect(f.locator("#status")).to_contain_text("1 of 3")
    host.expect(f.locator("#status")).to_contain_text("1 failed")
    host.expect(cards.nth(2).locator(".dot.err")).to_have_count(1)

    cards.nth(1).click()
    host.expect(f.locator("#frame svg text")).to_have_text("Second")
    (call,) = host.tool_calls("rerender_diagram")
    assert call["code"] == "graph TD; C-->D"
    assert call["output_format"] == "svg"
    # The fetched preview is kept: reopening the card does not call again.
    cards.nth(0).click()
    cards.nth(1).click()
    host.expect(f.locator("#frame svg text")).to_have_text("Second")
    assert len(host.tool_calls("rerender_diagram")) == 1

    cards.nth(2).click()
    host.expect(f.locator(".notice.error")).to_contain_text("Parse error on line 1")


def test_source_tab_checks_then_renders_edited_source(browser: Any) -> None:
    validation = {
        "structuredContent": {
            "valid": False,
            "errors": ["Unknown arrow"],
            "diagnostics": [
                {"severity": "error", "message": "Unknown arrow", "line": 2}
            ],
        }
    }
    host = Host(
        browser,
        {**TOOLS, "updateModelContext": {"text": {}}},
        {"validate_uml": validation, "rerender_diagram": _svg_result("Edited")},
    )
    host.send("ui/notifications/tool-result", _svg_result("Original"))
    f = host.frame
    host.expect(f.locator("#frame svg text")).to_have_text("Original")

    f.locator("#tabSource").click()
    edited = "graph TD\n  A ==> B"
    f.locator("#sourceEdit").fill(edited)
    f.locator("#checkBtn").click()
    host.expect(f.locator(".check.err")).to_contain_text("Unknown arrow")
    host.expect(f.locator(".check.err button")).to_have_text("L2")
    host.expect(f.locator("#issueCount")).to_have_text("1")
    (check,) = host.tool_calls("validate_uml")
    assert check["code"] == edited and check["strict"] is True

    f.locator("#sourceEdit").press("Control+Enter")
    host.expect(f.locator("#frame svg text")).to_have_text("Edited")
    host.expect(f.locator("#stage")).to_be_visible()
    (render,) = host.tool_calls("rerender_diagram")
    assert render["code"] == edited
    (context,) = host.wait_calls("ui/update-model-context")
    assert edited in context["params"]["content"][0]["text"]
    assert context["params"]["structuredContent"]["diagram_type"] == "mermaid"


def test_url_only_result_fetches_one_preview_and_opens_links_via_host(
    browser: Any,
) -> None:
    host = Host(
        browser,
        {**TOOLS, "openLinks": {}},
        {"rerender_diagram": _svg_result("Fetched")},
    )
    host.send(
        "ui/notifications/tool-result",
        {
            "structuredContent": {
                "diagram_type": "mermaid",
                "code": "graph TD; A-->B",
                "output_format": "svg",
                "url": "https://kroki.io/mermaid/svg/abc",
                "playground": "https://mermaid.live/edit#abc",
            }
        },
    )
    f = host.frame
    host.expect(f.locator("#frame svg text")).to_have_text("Fetched")
    assert len(host.tool_calls("rerender_diagram")) == 1
    # The original render link survives the preview fetch.
    host.expect(f.locator("#openUrl")).to_have_attribute(
        "href", "https://kroki.io/mermaid/svg/abc"
    )
    f.locator("#openUrl").click()
    (link,) = host.wait_calls("ui/open-link")
    assert link["params"]["url"] == "https://kroki.io/mermaid/svg/abc"


def test_host_without_server_tools_shows_links_only(browser: Any) -> None:
    host = Host(browser, {}, {})
    host.send(
        "ui/notifications/tool-result",
        {
            "structuredContent": {
                "diagram_type": "class",
                "code": "@startuml\nclass A\n@enduml",
                "output_format": "pdf",
                "mime_type": "application/pdf",
                "url": "https://kroki.io/plantuml/pdf/abc",
            }
        },
    )
    f = host.frame
    host.expect(f.locator(".notice h3")).to_have_text("PDF ready")
    host.expect(f.locator("#rerenderRow")).to_be_hidden()
    host.expect(f.locator("#checkBtn")).to_be_hidden()
    assert host.calls("tools/call") == []


def test_streaming_input_then_text_diagram_and_download(browser: Any) -> None:
    host = Host(browser, {**TOOLS, "downloadFile": {}}, {})
    f = host.frame
    host.send(
        "ui/notifications/tool-input-partial",
        {"arguments": {"diagram_type": "sequence", "code": "@startuml\nA -> B\n"}},
    )
    host.expect(f.locator("#status")).to_contain_text("Writing diagram source")
    host.expect(f.locator("#streamPreview")).to_contain_text("A -> B")

    ascii_art = "     ,-.\n     `-'\n     /|\\\n      |\n     / \\\n     Alice"
    host.send(
        "ui/notifications/tool-result",
        {
            "structuredContent": {
                "diagram_type": "sequence",
                "code": "@startuml\nactor Alice\n@enduml",
                "output_format": "txt",
                "mime_type": "text/plain",
                "content_base64": base64.b64encode(ascii_art.encode()).decode(),
            }
        },
    )
    host.expect(f.locator("pre.ascii")).to_contain_text("Alice")
    host.expect(f.locator("#status")).to_contain_text("Text diagram ready")
    f.locator("#downloadBtn").click()
    (download,) = host.wait_calls("ui/download-file")
    resource = download["params"]["contents"][0]["resource"]
    assert resource["uri"] == "file:///sequence.txt"
    assert resource["mimeType"] == "text/plain"
    assert base64.b64decode(resource["blob"]).decode() == ascii_art


def test_viewer_html_keeps_bridge_methods() -> None:
    html = diagram_viewer_html()
    for method in (
        "ui/open-link",
        "ui/download-file",
        "ui/message",
        "ui/update-model-context",
        "ui/notifications/tool-input-partial",
        "ui/request-display-mode",
    ):
        assert json.dumps(method) in html, method


@pytest.mark.parametrize("width", [360, 768, 1280])
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_responsive_keyboard_tabs(
    browser: Any, tmp_path: Path, width: int, theme: str
) -> None:
    host = Host(browser, TOOLS, {})
    host.page.set_viewport_size({"width": width, "height": 900})
    host.page.emulate_media(color_scheme=theme, reduced_motion="reduce")
    host.page.locator("iframe").evaluate(
        "el => { el.style.width = '100%'; el.style.border = '0'; }"
    )
    host.send(
        "ui/notifications/tool-result",
        {
            "structuredContent": {
                "results": [
                    _svg_result("First")["structuredContent"],
                    _svg_result("Second")["structuredContent"],
                ]
            }
        },
    )
    f = host.frame
    host.expect(f.locator("#gallery .card")).to_have_count(2)
    f.locator("#gallery .card").first.focus()
    host.page.keyboard.press("ArrowRight")
    host.expect(f.locator("#gallery .card").nth(1)).to_be_focused()
    host.expect(f.locator("#gallery .card").nth(1)).to_have_attribute(
        "aria-selected", "true"
    )
    host.page.keyboard.press("Home")
    host.expect(f.locator("#gallery .card").first).to_be_focused()
    f.locator("#tabDiagram").focus()
    host.page.keyboard.press("ArrowRight")
    host.expect(f.locator("#tabSource")).to_be_focused()
    host.expect(f.locator("#sourcePane")).to_be_visible()
    host.page.keyboard.press("Tab")
    host.expect(f.locator("#sourceEdit")).to_be_focused()
    host.page.keyboard.press("Shift+Tab")
    host.page.keyboard.press("Home")
    host.expect(f.locator("#tabDiagram")).to_be_focused()
    host.expect(f.locator("#stage")).to_be_visible()
    assert f.locator("body").evaluate(
        "() => document.documentElement.scrollWidth <= innerWidth"
    )
    host.page.screenshot(path=str(tmp_path / f"viewer-{width}-{theme}.png"))


def test_export_and_link_buttons_without_duplicate_rows(browser):
    encoded = base64.b64encode(b"<!doctype html><title>Export</title>").decode()
    response = {
        "structuredContent": {
            "chunk": encoded,
            "offset": 0,
            "next_offset": len(encoded),
            "total": len(encoded),
            "sha256": "test",
            "mime_type": "text/html",
            "filename": "diagram.html",
        }
    }
    host = Host(
        browser,
        {**TOOLS, "downloadFile": {}, "openLinks": {}},
        {"download_diagram": response},
    )
    host.send(
        "ui/notifications/tool-result",
        _svg_result(
            "Diagram",
            url="https://example.com/render.svg",
            playground="https://mermaid.live/edit#test",
        ),
    )
    f = host.frame
    host.expect(f.locator("#meta .row")).to_have_count(0)
    f.locator("#openPlay").click()
    assert (
        host.wait_calls("ui/open-link")[0]["params"]["url"]
        == "https://mermaid.live/edit#test"
    )
    f.locator("#exportFormat").select_option("html")
    f.locator("#downloadBtn").click()
    resource = host.wait_calls("ui/download-file")[0]["params"]["contents"][0][
        "resource"
    ]
    assert base64.b64decode(resource["blob"]).startswith(b"<!doctype html>")
    assert host.tool_calls("download_diagram")[0]["output_format"] == "html"


def test_compact_preview_loads_full_vector_on_demand(browser):
    encoded = _svg("Full resolution")
    response = {
        "structuredContent": {
            "chunk": encoded,
            "offset": 0,
            "next_offset": len(encoded),
            "total": len(encoded),
            "sha256": "test",
            "mime_type": "image/svg+xml",
            "filename": "diagram.svg",
        }
    }
    host = Host(browser, TOOLS, {"download_diagram": response})
    host.send(
        "ui/notifications/tool-result",
        _svg_result("Small preview", preview_resized=True),
    )
    host.expect(host.frame.locator("#frame svg text")).to_have_text("Full resolution")
    host.expect(host.frame.locator("#status")).to_contain_text("Diagram ready")


def test_png_to_svg_rerender_keeps_labels_and_new_link(browser):
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (300, 120), "white").save(buffer, format="PNG")
    initial = _svg_result(
        "unused",
        mime_type="image/png",
        content_base64=base64.b64encode(buffer.getvalue()).decode(),
        output_format="png",
        url="https://example.com/old.png",
    )
    result = _svg_result("New vector labels", url="https://example.com/new.svg")
    host = Host(browser, TOOLS, {"rerender_diagram": result})
    host.send("ui/notifications/tool-result", initial)
    host.expect(host.frame.locator("#frame > img")).to_be_visible()
    host.frame.locator("#formatSelect").select_option("svg")
    host.frame.locator("#rerenderBtn").click()
    host.expect(host.frame.locator("#frame > svg text")).to_have_text(
        "New vector labels"
    )
    host.expect(host.frame.locator("#openUrl")).to_have_attribute(
        "href", "https://example.com/new.svg"
    )
    host.expect(host.frame.locator("#formatSelect")).to_have_value("svg")


def test_current_svg_download_probes_unadvertised_host_download_support(browser):
    host = Host(browser, {}, {})
    host.send("ui/notifications/tool-result", _svg_result("Standalone download"))
    host.expect(host.frame.locator("#downloadBtn")).to_be_visible()
    host.expect(host.frame.locator("#exportFormat")).to_have_value("current")
    host.frame.locator("#downloadBtn").click()
    call = host.wait_calls("ui/download-file")[0]
    raw = base64.b64decode(call["params"]["contents"][0]["resource"]["blob"]).decode()
    assert "Standalone download" in raw and "<svg" in raw
    assert not host.tool_calls("download_diagram")


def test_explicit_png_preview_is_not_overridden_by_svg_hydration(browser):
    from io import BytesIO

    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (300, 120), "white").save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode()
    png_result = _svg_result(
        "unused", mime_type="image/png", content_base64=encoded, output_format="png"
    )
    chunk = {
        "structuredContent": {
            "chunk": encoded,
            "offset": 0,
            "next_offset": len(encoded),
            "total": len(encoded),
            "sha256": "test",
            "mime_type": "image/png",
            "filename": "diagram.png",
        }
    }
    host = Host(
        browser, TOOLS, {"rerender_diagram": png_result, "download_diagram": chunk}
    )
    host.send("ui/notifications/tool-result", _svg_result("Initial SVG"))
    host.frame.locator("#formatSelect").select_option("png")
    host.frame.locator("#rerenderBtn").click()
    host.expect(host.frame.locator("#frame > img")).to_be_visible()
    host.expect(host.frame.locator("#formatSelect")).to_have_value("png")
    host.wait_calls("tools/call", 2)
    assert host.tool_calls("download_diagram")[0]["output_format"] == "png"


def test_host_download_rejection_is_reported(browser):
    host = Host(browser, {}, {"ui/download-file": {"isError": True}})
    host.send("ui/notifications/tool-result", _svg_result("Rejected download"))
    host.frame.locator("#downloadBtn").click()
    host.expect(host.frame.locator("#status")).to_contain_text("Download failed")
    host.expect(host.frame.locator("#downloadBtn")).to_be_enabled()


def test_plugin_html_is_isolated_and_exports_live_svg_png_and_html(browser, d3_plugin):
    import hashlib
    from io import BytesIO

    from PIL import Image
    from uml_mcp_plugin_d3 import D3Renderer
    from uml_mcp_plugin_d3.samples import SAMPLES

    d3_plugin()
    code = SAMPLES["d3_architecture"][0]
    renderer = D3Renderer()
    renderer.configure({"d3_source": "inline"})
    raw = renderer.render("d3_architecture", code, "html").content
    encoded = base64.b64encode(raw).decode()
    digest = hashlib.sha256(raw).hexdigest()
    responses = {}
    for offset in range(0, len(encoded), 32000):
        chunk = encoded[offset : offset + 32000]
        responses[f"download_diagram:html:{offset}"] = {
            "structuredContent": {
                "chunk": chunk,
                "offset": offset,
                "next_offset": offset + len(chunk),
                "total": len(encoded),
                "sha256": digest,
                "mime_type": "text/html",
                "filename": "diagram.html",
            }
        }
    host = Host(browser, TOOLS, responses)
    host.send(
        "ui/notifications/tool-result",
        {
            "structuredContent": {
                "diagram_type": "d3_architecture",
                "code": code,
                "output_format": "html",
                "mime_type": "text/html; charset=utf-8",
                "inline_omitted": True,
            }
        },
    )
    outer = host.frame
    inner = outer.frame_locator("iframe.plugin-frame")
    host.expect(inner.locator("body")).to_have_attribute("data-ready", "architecture")
    host.expect(inner.locator("g.node")).to_have_count(7)
    assert (
        outer.locator("iframe.plugin-frame").get_attribute("sandbox") == "allow-scripts"
    )
    assert (
        inner.locator("body").evaluate(
            "() => { try { return window.parent.document.title; } catch (_) { return 'isolated'; } }"
        )
        == "isolated"
    )
    inner.locator("#theme").click()
    for count, format in enumerate(("svg", "png", "html"), start=1):
        outer.locator("#exportFormat").select_option(format)
        outer.locator("#downloadBtn").click()
        call = host.wait_calls("ui/download-file", count)[-1]
        resource = call["params"]["contents"][0]["resource"]
        data = base64.b64decode(resource["blob"])
        if format == "svg":
            assert b"var(" not in data and b"arch dark" in data
            exported = browser.new_page()
            exported.set_content(data.decode())
            colors = "nodes => nodes.map(node => getComputedStyle(node).fill)"
            assert exported.locator("rect.card").evaluate_all(colors) == inner.locator(
                "rect.card"
            ).evaluate_all(colors)
            exported.close()
        elif format == "png":
            assert Image.open(BytesIO(data)).width > 2000
        else:
            assert (
                data.startswith(b"<!doctype html>") and b"cdn.jsdelivr.net" not in data
            )
    assert not outer.locator('#exportFormat option[value="pdf"]').is_disabled()
