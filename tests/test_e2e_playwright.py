"""Browser e2e with Playwright: the admin dashboard and the MCP endpoint.

Starts the real app (real FastMCP) with uvicorn on a free port. Skipped when
Playwright or a Chromium build is not available (e.g. plain CI runners); run
locally with ``uv sync --all-groups`` and ``uv run pytest tests/test_e2e_playwright.py``.
Set ``PLAYWRIGHT_CHROMIUM`` to use a specific browser binary.
"""

from __future__ import annotations

import glob
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

sync_api = pytest.importorskip("playwright.sync_api")

ROOT = Path(__file__).resolve().parents[1]
TABS = [
    "Overview",
    "Activity",
    "Metrics",
    "Rate limits",
    "Configuration",
    "Lint",
    "Tools",
]
LOCAL = httpx.Client(trust_env=False, timeout=10)  # loopback: never via HTTP(S)_PROXY
MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


def _chromium_path() -> str | None:
    explicit = os.environ.get("PLAYWRIGHT_CHROMIUM")
    if explicit:
        return explicit
    found = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))
    return found[-1] if found else None


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    cfg = tmp_path_factory.mktemp("e2e") / "uml-mcp.yaml"
    cfg.write_text(
        "audit: {enabled: true, sinks: [memory]}\n"
        "metrics: {enabled: true, endpoint: true}\n"
        "admin: {allow_local_without_auth: true}\n",
        encoding="utf-8",
    )
    port = _free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith("MCP_AUTH")}
    env.update(
        {"UML_MCP_CONFIG": str(cfg), "USE_REAL_FASTMCP": "1", "MOCK_FASTMCP": ""}
    )
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    base = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            if LOCAL.get(f"{base}/health", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.5)
    else:
        proc.kill()
        _, err = proc.communicate(timeout=10)
        pytest.fail("server did not start: " + (err or b"").decode()[-2000:])
    yield base
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as pw:
        try:
            b = pw.chromium.launch(executable_path=_chromium_path())
        except Exception as exc:  # noqa: BLE001 - no browser on this machine
            pytest.skip(f"Chromium not available: {exc}")
        yield b
        b.close()


def _rpc(method: str, params: dict | None = None, rid: int = 1) -> str:
    return json.dumps(
        {"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}}
    )


def _result(body: str) -> dict:
    """Streamable HTTP answers JSON or a one-event SSE stream."""
    text = body.strip()
    if text.startswith("{"):
        return json.loads(text)
    data = [line[5:].strip() for line in text.splitlines() if line.startswith("data:")]
    return json.loads(data[-1])


def test_mcp_endpoint_over_playwright_request(browser, server):
    ctx = browser.new_context()
    api = ctx.request
    init = api.post(
        f"{server}/mcp",
        headers=MCP_HEADERS,
        data=_rpc(
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "playwright", "version": "1"},
            },
        ),
        max_redirects=0,
    )
    assert init.status == 200  # no 307 on the exact /mcp path
    info = _result(init.text())["result"]["serverInfo"]
    assert info["name"] == "uml_mcp" and info["version"].startswith("1.")
    session = init.headers.get("mcp-session-id")
    headers = {**MCP_HEADERS, **({"mcp-session-id": session} if session else {})}
    tools = _result(
        api.post(
            f"{server}/mcp", headers=headers, data=_rpc("tools/list", rid=2)
        ).text()
    )
    names = {t["name"] for t in tools["result"]["tools"]}
    assert {"generate_uml", "validate_uml", "list_diagram_types"} <= names
    call = _result(
        api.post(
            f"{server}/mcp",
            headers=headers,
            data=_rpc(
                "tools/call",
                {
                    "name": "validate_uml",
                    "arguments": {"diagram_type": "mermaid", "code": "graph TD; A-->B"},
                },
                rid=3,
            ),
        ).text()
    )
    assert call["result"]["isError"] is False
    ctx.close()


def test_dashboard_tabs_render_without_errors(browser, server):
    LOCAL.post(
        f"{server}/kroki_encode", json={"type": "mermaid", "code": "graph TD; A-->B"}
    )
    page = browser.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{server}/admin")
    page.wait_for_selector("#tabs button")
    visible = page.eval_on_selector_all(
        "#tabs button:not([hidden])", "bs => bs.map(b => b.textContent)"
    )
    assert visible == TABS  # auth-only tabs hidden in local mode
    for tab in TABS:
        page.click(f"#tabs button:has-text('{tab}')")
        panel = page.locator(f"[data-tab='{tab}']")
        panel.wait_for(state="visible")
        page.wait_for_function(
            "t => !document.querySelector(`[data-tab='${t}']`).innerText.includes('Loading')",
            arg=tab,
        )
    page.click("#tabs button:has-text('Activity')")
    page.wait_for_selector("[data-tab='Activity'] table")
    assert "/kroki_encode" in page.inner_text("[data-tab='Activity']")
    page.click("#tabs button:has-text('Tools')")
    page.wait_for_selector("[data-tab='Tools'] table")
    assert "generate_uml" in page.inner_text("[data-tab='Tools']")
    assert errors == []
    page.close()


def test_prometheus_metrics_endpoint(server):
    body = LOCAL.get(f"{server}/metrics").text
    assert "uml_mcp_uptime_seconds" in body
