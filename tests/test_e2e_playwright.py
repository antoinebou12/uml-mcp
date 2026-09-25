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
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
import yaml

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


TOKEN = "e2e-setup-token"


def _start(tmp: Path, cfg_text: str) -> tuple[str, subprocess.Popen]:
    cfg = tmp / "uml-mcp.yaml"
    cfg.write_text(cfg_text, encoding="utf-8")
    port = _free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith("MCP_AUTH")}
    env.update(
        {
            "UML_MCP_CONFIG": str(cfg),
            "USE_REAL_FASTMCP": "1",
            "MOCK_FASTMCP": "",
            "UML_MCP_ADMIN_TOKEN": TOKEN,
        }
    )
    log = (tmp / "server.log").open("wb")  # a file, not a pipe: never blocks the server
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
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            if LOCAL.get(f"{base}/health", timeout=1).status_code == 200:
                return base, proc
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    proc.kill()
    pytest.fail("server did not start: " + (tmp / "server.log").read_text()[-2000:])


BASE_CFG = (
    "audit: {enabled: true, sinks: [memory]}\n"
    "metrics: {enabled: true, endpoint: true}\n"
    "admin: {allow_local_without_auth: true}\n"
)


@pytest.fixture(scope="module")
def server_ctx(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("e2e")
    base, proc = _start(tmp, BASE_CFG)
    yield base, tmp / "uml-mcp.yaml"
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture(scope="module")
def server(server_ctx):
    return server_ctx[0]


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


PAGES = {
    "overview": "Overview",
    "setup": "Setup",
    "settings": "Settings",
    "clients": "Clients",
    "activity": "Activity",
    "logs": "Logs",
    "metrics": "Metrics",
    "limits": "Rate limits",
    "tools": "Tools & plugins",
    "lint": "Quality",
}
DESKTOP = {"width": 1280, "height": 800}
MOBILE = {"width": 390, "height": 844}
SHOTS = (
    Path(os.environ.get("UML_MCP_SCREENSHOTS", ""))
    if os.environ.get("UML_MCP_SCREENSHOTS")
    else None
)


def _page(browser, server, viewport, scheme="light"):
    ctx = browser.new_context(viewport=viewport, color_scheme=scheme)
    page = ctx.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{server}/admin/#/overview?token={TOKEN}")
    page.wait_for_selector("[data-testid=page-title]")
    return ctx, page, errors


@pytest.mark.parametrize("viewport", [DESKTOP, MOBILE], ids=["desktop", "mobile"])
def test_every_page_renders(browser, server, viewport):
    LOCAL.post(
        f"{server}/kroki_encode", json={"type": "mermaid", "code": "graph TD; A-->B"}
    )
    ctx, page, errors = _page(browser, server, viewport)
    mobile = viewport is MOBILE
    assert page.is_visible("aside") is not mobile  # sidebar on desktop, sheet on mobile
    assert "token=" not in page.url  # the setup token is stripped from the URL
    for route, title in PAGES.items():
        if mobile:
            page.click("[data-testid=menu-button]")
            sheet = page.get_by_role("dialog")
            sheet.get_by_role("link", name=title).click()
            sheet.wait_for(state="hidden")  # closing animation done
        else:
            page.locator("aside").get_by_role("link", name=title).click()
        page.wait_for_function(
            "t => document.querySelector('[data-testid=page-title]')?.textContent === t",
            arg=title,
        )
        assert page.url.endswith(f"#/{route}")
        if SHOTS:
            SHOTS.mkdir(parents=True, exist_ok=True)
            page.wait_for_timeout(400)
            page.screenshot(
                path=str(SHOTS / f"{'mobile' if mobile else 'desktop'}-{route}.png")
            )
        # no horizontal page scroll at any width
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
    assert errors == []
    ctx.close()


def test_theme_toggle_persists(browser, server):
    ctx, page, _ = _page(browser, server, DESKTOP)
    html = page.locator("html")
    start_dark = "dark" in (html.get_attribute("class") or "")
    for _ in range(3):  # light -> dark -> system -> light
        page.click("[data-testid=theme-toggle]")
        if ("dark" in (html.get_attribute("class") or "")) != start_dark:
            break
    theme = page.evaluate("localStorage.getItem('uml-mcp-theme')")
    page.reload()
    page.wait_for_selector("[data-testid=page-title]")
    assert page.evaluate("localStorage.getItem('uml-mcp-theme')") == theme
    ctx.close()


def test_setup_wizard_writes_config(browser, server_ctx):
    server, cfg = server_ctx
    ctx, page, errors = _page(browser, server, DESKTOP)
    page.goto(f"{server}/admin/#/setup")
    page.click("[data-profile=docker]")
    page.click("[data-testid=setup-next]")
    page.fill("#kroki", "http://kroki:8000")
    page.click("[data-testid=setup-next]")
    page.click("[data-testid=setup-next]")
    page.wait_for_selector("pre code")
    assert "kroki:8000" in page.inner_text("pre code")
    page.click("[data-testid=setup-finish]")
    page.wait_for_selector("[data-testid=setup-done]")
    data = yaml.safe_load(cfg.read_text())
    assert data["setup"]["profile"] == "docker"
    assert data["rendering"]["kroki_server"] == "http://kroki:8000"
    assert errors == []
    ctx.close()


def test_settings_save_and_reset(browser, server_ctx):
    server, cfg = server_ctx
    ctx, page, errors = _page(browser, server, DESKTOP)
    page.goto(f"{server}/admin/#/settings")
    page.click("[data-section=rate_limit]")
    field = page.locator("[data-field='rate_limit.auth_failures_per_minute'] input")
    field.fill("17")
    page.click("[data-testid=save-settings]")
    page.get_by_text(re.compile(r"^Saved \d+ change")).wait_for()
    assert (
        yaml.safe_load(cfg.read_text())["rate_limit"]["auth_failures_per_minute"] == 17
    )
    page.get_by_role("button", name="Reset", exact=True).click()
    page.wait_for_function(
        "() => !document.querySelector(\"[data-field='rate_limit.auth_failures_per_minute'] input\").value"
    )
    assert "auth_failures_per_minute" not in (
        yaml.safe_load(cfg.read_text()).get("rate_limit") or {}
    )
    assert errors == []
    ctx.close()


def test_logs_page_streams(browser, server):
    ctx, page, _ = _page(browser, server, DESKTOP)
    page.goto(f"{server}/admin/#/logs")
    page.wait_for_selector("[data-testid=log-view]")
    LOCAL.get(f"{server}/health")
    page.wait_for_function(
        "() => document.querySelector('[data-testid=log-view]').innerText.includes('INFO')",
        timeout=15000,
    )
    ctx.close()


def test_stop_button_stops_server(browser, tmp_path):
    base, proc = _start(tmp_path, BASE_CFG)
    try:
        ctx, page, _ = _page(browser, base, MOBILE)
        page.click("[data-testid=stop-button]")
        page.click("[data-testid=confirm-stop]")
        page.wait_for_selector("[data-testid=stopped]")
        assert proc.wait(timeout=15) is not None
        ctx.close()
    finally:
        if proc.poll() is None:
            proc.kill()


def test_prometheus_metrics_endpoint(server):
    body = LOCAL.get(f"{server}/metrics").text
    assert "uml_mcp_uptime_seconds" in body
