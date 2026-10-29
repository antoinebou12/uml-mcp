"""Browser-level regression tests for the MCP Apps diagram viewer."""

from __future__ import annotations

import base64

import pytest

from mcp_core.apps.diagram_viewer import diagram_viewer_html


def test_viewer_fit_pan_safety_and_rerender_retry() -> None:
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except playwright.Error as exc:
            if "Executable doesn't exist" in str(exc) or "browserType.launch" in str(exc):
                pytest.skip("Playwright Chromium is not installed")
            raise

        try:
            page = browser.new_page()
            page.set_content("<iframe title='Diagram'></iframe>")
            page.evaluate(
                """html => {
                    window.rerenderCalls = 0;
                    window.addEventListener('message', event => {
                        const m = event.data;
                        if (m.method === 'ui/initialize') {
                            event.source.postMessage({jsonrpc:'2.0', id:m.id, result:{}}, '*');
                        } else if (m.method === 'tools/call') {
                            window.rerenderCalls++;
                            event.source.postMessage({jsonrpc:'2.0', id:m.id,
                                error:{code:-32603, message:'Temporary failure'}}, '*');
                        }
                    });
                    document.querySelector('iframe').srcdoc = html;
                }""",
                diagram_viewer_html(),
            )
            frame = page.frame_locator("iframe")
            playwright.expect(frame.locator("#status")).to_contain_text("Ready")

            # Unicode round-trips through content_base64; unsafe root events and URLs do not.
            svg = (
                '<svg xmlns="http://www.w3.org/2000/svg" width="1600" '
                'height="800" viewBox="0 0 1600 800" onload="alert(1)">'
                '<text x="20" y="50">Été 日本</text></svg>'
            )
            payload = {
                "jsonrpc": "2.0",
                "method": "ui/notifications/tool-result",
                "params": {
                    "structuredContent": {
                        "diagram_type": "mermaid",
                        "code": "graph TD; A-->B",
                        "mime_type": "image/svg+xml",
                        "content_base64": base64.b64encode(svg.encode("utf-8")).decode(),
                        "url": "javascript:alert(1)",
                        "playground": "https://mermaid.live/",
                    }
                },
            }
            page.evaluate(
                "m => document.querySelector('iframe').contentWindow.postMessage(m, '*')",
                payload,
            )
            playwright.expect(frame.locator("svg text")).to_have_text("Été 日本")
            assert frame.locator("svg").get_attribute("onload") is None
            playwright.expect(frame.locator("#openUrl")).to_be_hidden()
            playwright.expect(frame.locator("#openPlay")).to_be_visible()

            frame.locator("#zoomIn").click()
            playwright.expect(frame.locator("#zoomLabel")).to_have_text("125%")
            frame.locator("#zoomFit").click()
            playwright.expect(frame.locator("#zoomLabel")).not_to_have_text("125%")
            frame.locator("#zoomReset").click()
            playwright.expect(frame.locator("#zoomLabel")).to_have_text("100%")
            assert "translate(0px, 0px)" in (
                frame.locator("svg").get_attribute("style") or ""
            )

            # Failures remain retryable rather than permanently hiding the tool.
            for calls in (1, 2):
                frame.locator("#rerenderBtn").click()
                playwright.expect(frame.locator("#status")).to_contain_text(
                    "Temporary failure"
                )
                playwright.expect(frame.locator("#rerenderBtn")).to_be_enabled()
                assert page.evaluate("window.rerenderCalls") == calls

            # An event originating within the frame is not a trusted host notification.
            frame.locator("body").evaluate(
                """() => window.dispatchEvent(new MessageEvent('message', {
                    source: window,
                    data: {jsonrpc:'2.0', method:'ui/notifications/tool-cancelled'}
                }))"""
            )
            playwright.expect(frame.locator("#status")).to_contain_text(
                "Temporary failure"
            )
        finally:
            browser.close()
