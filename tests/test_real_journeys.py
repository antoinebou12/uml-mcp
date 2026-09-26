"""Real end-to-end journeys against a running server (no mocks in the app).

* **Agent use:** a real MCP client (Streamable HTTP) behaves like an LLM agent,
  using ``initialize`` instructions, the catalog, resources, prompts, validation
  with self-correction, rendering, inline images, batches and error recovery.
  It runs against every Kroki tier (see ``tests/fixtures_real.py``): the in-test
  fake, a real local Kroki (Docker) and the public https://kroki.io, and checks
  that what comes back is a correct diagram (SVG labels, decodable PNG).
* **Computer use:** Chromium drives the console like a person: getting started from
  an empty configuration, the setup wizard, then seeing the agent's calls in Activity,
  Metrics and Quality, with an accessibility (axe) scan of every page.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

import pytest
import yaml

from mcp_core.quality.render_check import check_png, check_svg
from tests.fixtures_real import LOCAL, ROOT, TOKEN, run_in_thread

pytestmark = pytest.mark.usefixtures("loopback_bypasses_proxy")

SEQUENCE = "sequenceDiagram\n  Alice->>Bob: hi\n  Bob-->>Alice: ok"
CLASSES = "@startuml\nclass Order\nclass Customer\nCustomer --> Order\n@enduml"
BROKEN = "digraph { a -> SYNTAX_ERROR -> }"  # Kroki answers HTTP 400


def run_agent(base: str) -> dict[str, Any]:
    return run_in_thread(lambda: _agent_session(base))


def _text(result: Any) -> str:
    return "\n".join(getattr(c, "text", "") for c in result.content)


async def _agent_session(base: str) -> dict[str, Any]:
    """What a well-behaved agent does with UML-MCP, step by step."""
    from fastmcp import Client

    seen: dict[str, Any] = {}
    async with Client(f"{base}/mcp", timeout=120) as client:
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
        fixed = (first.structured_content or {}).get("corrected_code") or SEQUENCE
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
            "generate_uml_image", {"diagram_type": "class", "code": CLASSES}
        )
        seen["image_types"] = [c.type for c in image.content]
        seen["image_png"] = [
            base64.b64decode(c.data) for c in image.content if c.type == "image"
        ]
        # 7. batch
        batch = await client.call_tool(
            "generate_uml_batch",
            {
                "items": [
                    {"diagram_type": "mermaid", "code": "graph TD; Start-->Finish"},
                    {"diagram_type": "d2", "code": "gateway -> backend"},
                    {"diagram_type": "class", "code": CLASSES},
                ]
            },
        )
        seen["batch"] = batch.structured_content
        # 8. recover from a renderer error
        broken = await client.call_tool(
            "generate_uml",
            {"diagram_type": "graphviz", "code": BROKEN},
            raise_on_error=False,
        )
        seen["error_is_error"] = broken.is_error
        seen["error_text"] = _text(broken)
    return seen


def _svg(result: dict[str, Any]) -> bytes:
    return base64.b64decode(result["content_base64"])


def test_agent_uses_the_server_end_to_end(tier_stack):
    """The whole agent workflow, rendered by the fake, local or public Kroki."""
    tier = tier_stack["tier"]
    seen = run_agent(tier_stack["base"])
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

    # rendering is correct, not just "some bytes came back"
    render = seen["render"]
    assert render["url"].startswith(tier.url) and render["source"] == "kroki"
    assert render["playground"]  # mermaid.live link for the chat
    check_svg(_svg(render), ("Alice", "Bob"))
    assert "![" in seen["render_text"]  # markdown image for the chat
    assert "image" in seen["image_types"]  # inline PNG for chat UIs
    width, height = check_png(seen["image_png"][0])
    assert width * height > 20 * 20
    results = seen["batch"]["results"]
    assert [bool(r.get("url")) and not r.get("error") for r in results] == [True] * 3
    check_svg(_svg(results[0]), ("Start", "Finish"))
    check_svg(_svg(results[1]), ("gateway", "backend"))
    check_svg(_svg(results[2]), ("Order", "Customer"))
    assert seen["error_is_error"] and "syntax error" in seen["error_text"].lower()

    if tier.fake is not None:
        assert {"mermaid", "plantuml", "d2", "graphviz"} <= {
            r[0] for r in tier.fake.requests
        }
    # the operator sees exactly these calls in the audit trail
    audit = LOCAL.get(f"{tier_stack['base']}/admin/api/audit?limit=100").json()
    names = [r["operation_name"] for r in audit["records"]]
    assert names.count("validate_uml") >= 2 and "generate_uml_batch" in names
    assert any(
        r["operation_status"] == "error"
        for r in audit["records"]
        if r["operation_name"] == "generate_uml"
    )
    for r in audit["records"]:  # diagram code is summarized, never raw
        code = (r["input_data"] or {}).get("code")
        assert code is None or {"sha256", "chars", "preview"} <= set(code), r


async def _render_all(base: str, sources: dict[str, tuple[str, str]]) -> dict:
    """Render ``{name: (diagram_type, code)}`` as SVG through generate_uml_batch."""
    from fastmcp import Client

    names = list(sources)
    out: dict[str, Any] = {}
    async with Client(f"{base}/mcp", timeout=180) as client:
        for start in range(0, len(names), 20):  # MCP_BATCH_MAX_ITEMS
            chunk = names[start : start + 20]
            items = [
                {"diagram_type": sources[n][0], "code": sources[n][1]} for n in chunk
            ]
            batch = await client.call_tool("generate_uml_batch", {"items": items})
            for name, row in zip(chunk, batch.structured_content["results"]):
                out[name] = row
    return out


def _render_problems(base: str, sources: dict[str, tuple[str, str]]) -> dict:
    rows = run_in_thread(lambda: _render_all(base, sources))
    assert len(rows) == len(sources)
    problems: dict[str, str] = {}
    for name, row in rows.items():
        if row.get("error") or not row.get("content_base64"):
            problems[name] = str(row.get("error") or "no content")[:160]
            continue
        try:
            check_svg(_svg(row))
        except ValueError as exc:
            problems[name] = str(exc)[:160]
    return problems


def test_every_example_and_template_renders(tier_stack):
    """What uml://examples and uml://templates teach agents must actually render."""
    from mcp_core.core.config import MCP_SETTINGS
    from tools.kroki.kroki_templates import DiagramExamples, DiagramTemplates

    sources: dict[str, tuple[str, str]] = {}
    for dtype in MCP_SETTINGS.diagram_types:
        sources[f"example:{dtype}"] = (dtype, DiagramExamples.get_example(dtype))
        sources[f"template:{dtype}"] = (dtype, DiagramTemplates.get_template(dtype))
    assert _render_problems(tier_stack["base"], sources) == {}


def test_every_diagram_in_the_docs_renders(tier_stack):
    """Fenced diagrams in docs/ (```mermaid, ```d2, ...) are copy-paste ready."""
    import re

    from mcp_core.core.config import MCP_SETTINGS

    fence = re.compile(r"^```([a-z0-9]+)[^\n]*\n(.*?)^```", re.DOTALL | re.MULTILINE)
    sources: dict[str, tuple[str, str]] = {}
    for path in sorted((ROOT / "docs").rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        for index, (lang, body) in enumerate(fence.findall(text)):
            if lang in MCP_SETTINGS.diagram_types:
                sources[f"{path.relative_to(ROOT)}#{index}"] = (lang, body)
    assert len(sources) > 20
    assert _render_problems(tier_stack["base"], sources) == {}


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
