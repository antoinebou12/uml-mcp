"""Real end-to-end journeys against a running server (no mocks in the app).

* **Agent use:** a real MCP client (Streamable HTTP) behaves like an LLM agent,
  using ``initialize`` instructions, the catalog, resources, prompts, validation
  with self-correction, rendering, inline images, batches and error recovery.
  Rendering goes over real HTTP to a local **fake Kroki**, so no internet is needed.
* **Computer use:** Chromium drives the console like a person: getting started from
  an empty configuration, the setup wizard, then seeing the agent's calls in Activity,
  Metrics and Quality, with an accessibility (axe) scan of every page.
"""

from __future__ import annotations

import asyncio
import base64
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Self

import httpx
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
LOCAL = httpx.Client(trust_env=False, timeout=15)
TOKEN = "journey-token"
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


# ------------------------------------------------------------------ fake Kroki
class FakeKroki:
    """Minimal Kroki: POST /{type}/{format} and GET /{type}/{format}/{encoded}."""

    def __init__(self) -> None:
        from starlette.applications import Starlette
        from starlette.requests import Request
        from starlette.responses import Response
        from starlette.routing import Route

        self.requests: list[tuple[str, str, str]] = []

        def respond(dtype: str, fmt: str, body: str) -> Response:
            self.requests.append((dtype, fmt, body))
            if "SYNTAX_ERROR" in body:
                return Response("Error 400: syntax error in diagram", status_code=400)
            if fmt == "png":
                return Response(PNG_1X1, media_type="image/png")
            svg = f'<svg xmlns="http://www.w3.org/2000/svg"><text>{dtype}</text></svg>'
            return Response(svg, media_type="image/svg+xml")

        async def post(request: Request) -> Response:
            p = request.path_params
            return respond(p["dtype"], p["fmt"], (await request.body()).decode())

        async def get(request: Request) -> Response:
            p = request.path_params
            return respond(p["dtype"], p["fmt"], p["encoded"])

        app = Starlette(
            routes=[
                Route("/{dtype}/{fmt}", post, methods=["POST"]),
                Route("/{dtype}/{fmt}/{encoded:path}", get, methods=["GET"]),
            ]
        )
        import uvicorn

        self.port = _free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="warning")
        )
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    def __enter__(self) -> Self:
        self.thread.start()
        for _ in range(100):
            if self.server.started:
                return self
            time.sleep(0.05)
        raise RuntimeError("fake Kroki did not start")

    def __exit__(self, *exc: object) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=5)


# ---------------------------------------------------------------- real server
@pytest.fixture(scope="module", autouse=True)
def loopback_bypasses_proxy():
    """The MCP client honours HTTP(S)_PROXY; loopback must never go through it."""
    saved = {k: os.environ.get(k) for k in ("NO_PROXY", "no_proxy")}
    for key in saved:
        current = [v for v in (os.environ.get(key) or "").split(",") if v]
        os.environ[key] = ",".join([*current, "127.0.0.1", "localhost"])
    yield
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@pytest.fixture(scope="module")
def kroki():
    with FakeKroki() as fake:
        yield fake


@pytest.fixture(scope="module")
def stack(tmp_path_factory, kroki):
    """app.py (real FastMCP) wired to the fake Kroki; empty config (first run)."""
    tmp = tmp_path_factory.mktemp("journey")
    cfg = tmp / "uml-mcp.yaml"
    cfg.write_text(
        "admin: {allow_local_without_auth: true}\n"
        "audit: {enabled: true, sinks: [memory]}\n",
        encoding="utf-8",
    )
    port = _free_port()
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(
            (
                "MCP_AUTH",
                "KROKI",
                "HTTP_PROXY",
                "HTTPS_PROXY",
                "http_proxy",
                "https_proxy",
            )
        )
    }
    env.update(
        {
            "UML_MCP_CONFIG": str(cfg),
            "USE_REAL_FASTMCP": "1",
            "MOCK_FASTMCP": "",
            "UML_MCP_ADMIN_TOKEN": TOKEN,
            "KROKI_SERVER": kroki.url,
            "MCP_DIAGRAM_FALLBACK": "false",
            "MCP_MEMORY_ONLY": "true",
            "NO_PROXY": "127.0.0.1,localhost",
            "HOME": str(tmp / "home"),
            "XDG_CONFIG_HOME": str(tmp / "xdg"),
        }
    )
    log = (tmp / "server.log").open("wb")
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
    for _ in range(80):
        try:
            if LOCAL.get(f"{base}/health").status_code == 200:
                break
        except httpx.HTTPError:
            pass
        time.sleep(0.25)
    else:
        proc.kill()
        pytest.fail("server did not start: " + (tmp / "server.log").read_text()[-3000:])
    yield {"base": base, "cfg": cfg, "log": tmp / "server.log"}
    proc.terminate()
    proc.wait(timeout=10)


def run_agent(base: str) -> dict[str, Any]:
    """Run the agent session in its own thread (Playwright's sync API owns a loop)."""
    out: dict[str, Any] = {}
    errors: list[BaseException] = []

    def target() -> None:
        try:
            out.update(asyncio.run(_agent_session(base)))
        except BaseException as exc:  # noqa: BLE001 - re-raised in the test thread
            errors.append(exc)

    worker = threading.Thread(target=target)
    worker.start()
    worker.join(timeout=120)
    if errors:
        raise errors[0]
    assert out, "agent session did not finish"
    return out


def _text(result: Any) -> str:
    return "\n".join(getattr(c, "text", "") for c in result.content)


async def _agent_session(base: str) -> dict[str, Any]:
    """What a well-behaved agent does with UML-MCP, step by step."""
    from fastmcp import Client

    seen: dict[str, Any] = {}
    async with Client(f"{base}/mcp") as client:
        # 1. read the server's instructions and discover capabilities
        seen["instructions"] = client.instructions or ""
        tools = {t.name: t for t in await client.list_tools()}
        seen["tools"] = sorted(tools)
        # 2. check the catalog before choosing a type
        catalog = await client.call_tool("list_diagram_types", {"query": "sequence"})
        seen["catalog"] = catalog.structured_content
        # 3. read guidance resources and a prompt
        workflow = await client.read_resource("uml://workflow")
        seen["workflow"] = workflow[0].text if hasattr(workflow[0], "text") else ""
        prompts = {p.name for p in await client.list_prompts()}
        seen["prompts"] = prompts
        # 4. validate a draft, self-correct from the diagnostics
        packed = "sequenceDiagram; Alice->>Bob: hi; Bob-->>Alice: ok"
        first = await client.call_tool(
            "validate_uml", {"diagram_type": "mermaid", "code": packed, "strict": True}
        )
        seen["first_validation"] = first.structured_content
        fixed = (first.structured_content or {}).get("corrected_code") or (
            "sequenceDiagram\n  Alice->>Bob: hi\n  Bob-->>Alice: ok"
        )
        second = await client.call_tool(
            "validate_uml", {"diagram_type": "mermaid", "code": fixed, "strict": True}
        )
        seen["second_validation"] = second.structured_content
        # 5. render (through real HTTP to the Kroki server)
        rendered = await client.call_tool(
            "generate_uml",
            {"diagram_type": "mermaid", "code": fixed, "output_format": "svg"},
        )
        seen["render"] = rendered.structured_content
        seen["render_text"] = _text(rendered)
        # 6. inline chat image
        image = await client.call_tool(
            "generate_uml_image",
            {
                "diagram_type": "class",
                "code": "@startuml\nclass A\nclass B\nA --> B\n@enduml",
            },
        )
        seen["image_types"] = [c.type for c in image.content]
        # 7. batch
        batch = await client.call_tool(
            "generate_uml_batch",
            {
                "items": [
                    {"diagram_type": "mermaid", "code": "graph TD; A-->B"},
                    {"diagram_type": "d2", "code": "a -> b"},
                ]
            },
        )
        seen["batch"] = batch.structured_content
        # 8. recover from a renderer error
        broken = await client.call_tool(
            "generate_uml",
            {"diagram_type": "mermaid", "code": "graph TD; SYNTAX_ERROR"},
            raise_on_error=False,
        )
        seen["error_is_error"] = broken.is_error
        seen["error_text"] = _text(broken)
    return seen


def test_agent_uses_the_server_end_to_end(stack, kroki):
    seen = run_agent(stack["base"])
    assert (
        "validate_uml" in seen["instructions"]
        and "generate_uml" in seen["instructions"]
    )
    assert {
        "generate_uml",
        "generate_uml_image",
        "validate_uml",
        "list_diagram_types",
        "generate_uml_batch",
    } <= set(seen["tools"])
    assert any("sequence" in k for k in (seen["catalog"] or {}))
    assert seen["workflow"] and seen["prompts"]
    assert seen["first_validation"]["valid"] is False  # packed sequence is rejected
    assert seen["second_validation"]["valid"] is True  # the agent fixed it
    render = seen["render"]
    assert render["url"].startswith(kroki.url) and render["source"] == "kroki"
    assert base64.b64decode(render["content_base64"]).startswith(b"<svg")
    assert "![" in seen["render_text"]  # markdown image for the chat
    assert "image" in seen["image_types"]  # inline PNG for chat UIs
    assert len(seen["batch"]["results"]) == 2
    assert seen["error_is_error"] and "syntax error" in seen["error_text"].lower()
    rendered_types = {r[0] for r in kroki.requests}
    assert {"mermaid", "plantuml", "d2"} <= rendered_types
    # the operator sees exactly these calls in the audit trail
    audit = LOCAL.get(f"{stack['base']}/admin/api/audit?limit=100").json()["records"]
    names = [r["operation_name"] for r in audit]
    assert names.count("validate_uml") >= 2 and "generate_uml_batch" in names
    assert any(
        r["operation_status"] == "error"
        for r in audit
        if r["operation_name"] == "generate_uml"
    )
    for r in audit:  # diagram code is summarized (hash + length + preview), never raw
        code = (r["input_data"] or {}).get("code")
        assert code is None or {"sha256", "chars", "preview"} <= set(code), r


def test_mcp_over_raw_http_like_any_client(stack):
    """Protocol-level checks a non-Python client relies on."""
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    init = LOCAL.post(
        f"{stack['base']}/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "curl", "version": "1"},
            },
        },
    )
    assert init.status_code == 200  # no redirect on the exact /mcp path
    body = init.text
    assert '"instructions"' in body and '"uml_mcp"' in body
    bad = LOCAL.post(f"{stack['base']}/mcp", headers=headers, content=b"{not json")
    assert bad.status_code in (400, 422)
    # Clients that send an incomplete Accept header are tolerated on purpose
    # (app.py normalizes it): they still get a JSON-RPC answer.
    lenient = LOCAL.post(
        f"{stack['base']}/mcp",
        json={"jsonrpc": "2.0", "id": 2, "method": "ping"},
        headers={"Accept": "application/json"},
    )
    assert lenient.status_code == 200 and '"jsonrpc"' in lenient.text


# ------------------------------------------------------------- computer use
sync_api = pytest.importorskip("playwright.sync_api")


def _chromium_path() -> str | None:
    import glob

    explicit = os.environ.get("PLAYWRIGHT_CHROMIUM")
    if explicit:
        return explicit
    found = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))
    return found[-1] if found else None


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as pw:
        try:
            b = pw.chromium.launch(executable_path=_chromium_path())
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"Chromium not available: {exc}")
        yield b
        b.close()


def _axe(page) -> list[dict[str, Any]]:
    """Serious/critical accessibility violations on the current page (axe-core)."""
    axe_mod = pytest.importorskip("axe_playwright_python")
    script = Path(axe_mod.__file__).with_name("axe.min.js").read_text(encoding="utf-8")
    page.evaluate(script)
    result = page.evaluate(
        "() => axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa']}})"
    )
    return [
        {
            "id": v["id"],
            "impact": v["impact"],
            "nodes": len(v["nodes"]),
            "help": v["help"],
        }
        for v in result["violations"]
        if v["impact"] in ("serious", "critical")
    ]


def _title(page, title: str) -> None:
    page.wait_for_function(
        "t => document.querySelector('[data-testid=page-title]')?.textContent === t",
        arg=title,
    )


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_getting_started_journey_and_accessibility(browser, stack, scheme):
    """First run: open the console, finish setup, see the agent's work, stay accessible."""
    base = stack["base"]
    run_agent(base)  # an agent has been using the server
    ctx = browser.new_context(
        viewport={"width": 1280, "height": 860}, color_scheme=scheme
    )
    page = ctx.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{base}/admin/#/overview?token={TOKEN}")
    _title(page, "Overview")
    page.get_by_text("Getting started").wait_for()

    # Setup wizard from scratch
    page.locator("aside").get_by_role("link", name="Setup").click()
    _title(page, "Setup")
    page.click("[data-profile=local]")
    page.click("[data-testid=setup-next]")
    page.get_by_role("switch", name="Audit trail").or_(
        page.locator("#feat-audit")
    ).first.click()
    page.click("[data-testid=setup-next]")
    page.click("[data-testid=setup-next]")
    page.wait_for_selector("pre code")
    page.click("[data-testid=setup-finish]")
    page.wait_for_selector("[data-testid=setup-done]")
    saved = yaml.safe_load(stack["cfg"].read_text())
    assert saved["setup"]["profile"] == "local"

    # Overview: checklist advanced, charts rendered
    page.get_by_role("link", name="Go to overview").click()
    _title(page, "Overview")
    page.get_by_text("of 4 done").wait_for()
    assert "0 of 4" not in page.inner_text("main")
    page.wait_for_selector("[data-testid=traffic-chart] svg")

    # Activity shows what the agent did
    page.locator("aside").get_by_role("link", name="Activity").click()
    _title(page, "Activity")
    page.get_by_text("generate_uml_batch").first.wait_for()
    page.get_by_text("validate_uml").first.click()
    page.get_by_role("dialog").get_by_text("operation_status").wait_for()
    page.keyboard.press("Escape")

    # Quality: 100/100
    page.locator("aside").get_by_role("link", name="Quality").click()
    _title(page, "Quality")
    page.get_by_text("100/100").wait_for(timeout=30000)
    page.get_by_text("Documented exceptions").wait_for()

    # Accessibility on every page
    problems: dict[str, list[dict[str, Any]]] = {}
    for route in (
        "overview",
        "setup",
        "settings",
        "activity",
        "logs",
        "metrics",
        "limits",
        "tools",
        "clients",
        "lint",
    ):
        page.goto(f"{base}/admin/#/{route}")
        page.wait_for_selector("[data-testid=page-title]")
        page.wait_for_timeout(300)
        found = _axe(page)
        if found:
            problems[route] = found
    assert problems == {}, problems
    assert errors == []
    ctx.close()


def test_keyboard_only_navigation(browser, stack):
    """The console is usable without a mouse (tab to a nav link, Enter)."""
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    page = ctx.new_page()
    page.goto(f"{stack['base']}/admin/#/overview?token={TOKEN}")
    _title(page, "Overview")
    for _ in range(12):
        page.keyboard.press("Tab")
        if page.evaluate("document.activeElement?.textContent?.trim()") == "Settings":
            break
    page.keyboard.press("Enter")
    _title(page, "Settings")
    ctx.close()
