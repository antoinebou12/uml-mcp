"""The agent-trace page in a real browser, including the 560x430 MCP App frame.

Skipped when Playwright or a Chromium build is not available (plain CI runners); run
locally with ``uv sync --all-groups``. Set ``PLAYWRIGHT_CHROMIUM`` to use a specific binary.
"""

from __future__ import annotations

import glob
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _name in ("trace", "d3"):
    _src = str(ROOT / "examples" / "plugins" / f"uml-mcp-plugin-{_name}" / "src")
    if _src not in sys.path:
        sys.path.insert(0, _src)

from uml_mcp_plugin_trace import OTEL_EXAMPLE, TraceRenderer
from uml_mcp_plugin_trace.samples import EXAMPLE

sync_api = pytest.importorskip("playwright.sync_api")

EVIL = '<img src=x onerror="window.pwned=1"><b>bold</b>'


def _chromium_path() -> str | None:
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
        except Exception as exc:  # noqa: BLE001 - no browser on this machine
            pytest.skip(f"Chromium not available: {exc}")
        yield b
        b.close()


def _source(**changes) -> str:
    data = json.loads(EXAMPLE)
    data.update(changes)
    return json.dumps(data)


@pytest.fixture
def open_page(browser, tmp_path):
    contexts = []

    def run(
        source: str = EXAMPLE,
        *,
        width: int = 1200,
        height: int = 800,
        scheme: str = "dark",
    ):
        path = tmp_path / f"trace-{len(contexts)}.html"
        path.write_bytes(TraceRenderer().render("agent_trace", source, "html").content)
        context = browser.new_context(
            viewport={"width": width, "height": height},
            color_scheme=scheme,
            accept_downloads=True,
        )
        contexts.append(context)
        page = context.new_page()
        page.errors = []  # type: ignore[attr-defined]
        page.on("pageerror", lambda exc: page.errors.append(str(exc)))  # type: ignore[attr-defined]
        page.on(
            "console",
            lambda msg: page.errors.append(msg.text) if msg.type == "error" else None,  # type: ignore[attr-defined]
        )
        page.goto(path.as_uri())
        page.locator("body[data-ready]").wait_for(state="attached")
        return page

    yield run
    for context in contexts:
        context.close()


def visible_rows(page, view: str = "waterfall") -> list[str]:
    return page.evaluate(
        f"[...document.querySelectorAll('#{view} g.row:not(.gone), #{view} g.msg:not(.gone)')].map(g => g.dataset.id)"
    )


def test_page_opens_clean_and_fitted_in_the_chat_frame(open_page):
    page = open_page(width=560, height=430)
    assert page.errors == []
    zoom = page.evaluate("__trace.zoom")
    assert 0.3 < zoom < 1
    box = page.locator("#waterfall").bounding_box()
    main = page.locator("main").bounding_box()
    assert (
        box["x"] >= main["x"] - 1
        and box["x"] + box["width"] <= main["x"] + main["width"] + 1
    )
    # nothing in the toolbar pushes the page sideways
    assert page.evaluate("document.documentElement.scrollWidth") <= 560
    for control in (
        "#v-waterfall",
        "#v-flow",
        "#crit",
        "#collapse",
        "#fit",
        "#theme",
        "#export summary",
    ):
        b = page.locator(control).bounding_box()
        assert b and b["x"] + b["width"] <= 560 and b["y"] + b["height"] <= 430, control


def test_clicking_a_step_opens_its_card_with_docs_and_documents(open_page):
    page = open_page(width=560, height=430)
    page.locator('#waterfall g.row[data-id="search"] .bar').click()
    card = page.locator("#card")
    assert card.is_visible()
    assert page.locator("#c-title").text_content() == "Search policy docs"
    assert "elasticsearch" in page.locator("#c-sub").text_content()
    docs = page.locator("#c-docs")
    assert docs.is_visible()
    b = docs.bounding_box()
    assert b["y"] + b["height"] <= 430  # visible without scrolling the card
    assert page.locator("#card .doc").count() == 3
    assert page.locator("#card .doc .score").first.text_content() == "0.91"
    assert page.evaluate("__trace.selected") == "search"
    assert page.locator('#waterfall g.row.sel[data-id="search"]').count() == 1
    page.keyboard.press("Escape")
    assert card.is_hidden()


def test_long_text_is_folded_and_markup_stays_text(open_page):
    data = json.loads(EXAMPLE)
    data["steps"][1]["name"] = EVIL
    data["steps"][1]["input"] = EVIL + " " + "word " * 120
    page = open_page(json.dumps(data))
    page.evaluate("__trace.select('ask')")
    assert page.locator("#c-title").text_content() == EVIL
    assert page.locator("#card img, #card b:not(.stats b)").count() == 0
    pre = page.locator("#card pre").first
    assert len(pre.text_content()) <= 282
    more = page.locator("#card .more")
    assert more.text_content().startswith("Show all (")
    more.click()
    assert pre.text_content().startswith(EVIL) and len(pre.text_content()) > 500
    assert more.get_attribute("aria-expanded") == "true"
    assert page.evaluate("window.pwned") is None


def test_hover_shows_timing(open_page):
    page = open_page()
    page.locator('#waterfall g.row[data-id="answer"] .bar').hover()
    tip = page.locator("#tip")
    assert tip.is_visible()
    assert "Compose the answer" in tip.text_content()
    assert "2.14 s → 4.12 s · 1.98 s" in tip.text_content()


def test_flow_view_and_its_steps(open_page):
    page = open_page(width=560, height=430)
    page.click("#v-flow")
    assert page.evaluate("__trace.view") == "flow"
    assert page.locator("#flow").is_visible() and page.locator("#waterfall").is_hidden()
    assert page.locator("#v-flow").get_attribute("aria-pressed") == "true"
    assert len(visible_rows(page, "flow")) == 9
    lanes = page.locator("#flow .lane").all_text_contents()
    assert lanes[0] == "User" and "Support agent" in lanes[1]
    page.locator('#flow g.msg[data-id="refund"] text.t-msg').click()
    assert page.locator("#c-title").text_content() == "calculate_refund"
    page.click("#v-waterfall")
    assert page.locator("#waterfall").is_visible() and page.locator("#flow").is_hidden()


def _nested() -> str:
    def s(id, start, end, **kw):
        return {
            "id": id,
            "kind": "tool",
            "name": id,
            "start_ms": start,
            "end_ms": end,
            **kw,
        }

    return json.dumps(
        {
            "title": "Planner and researchers",
            "steps": [
                s("planner", 0, 1000, kind="subagent"),
                s("r1", 0, 400, kind="subagent", parent="planner"),
                s("r1-search", 0, 300, kind="retrieval", parent="r1"),
                s("r2", 0, 900, kind="subagent", parent="planner"),
                s(
                    "r2-llm",
                    10,
                    880,
                    kind="llm",
                    parent="r2",
                    model="claude-sonnet-5-5",
                ),
                s("final", 900, 1000, kind="reply", parent="planner"),
            ],
        }
    )


def test_carets_and_collapse_fold_sub_agents(open_page):
    page = open_page(_nested())
    assert len(visible_rows(page)) == 6
    height = page.evaluate(
        "document.getElementById('waterfall').viewBox.baseVal.height"
    )
    page.locator('#waterfall g.row[data-id="r2"] .caret').click()
    assert visible_rows(page) == ["planner", "r1", "r1-search", "r2", "final"]
    assert (
        page.locator('#waterfall g.row[data-id="r2"]').get_attribute("aria-expanded")
        == "false"
    )
    assert (
        page.evaluate("document.getElementById('waterfall').viewBox.baseVal.height")
        == height - 30
    )
    # the flow view folds the same steps
    assert "r2-llm" not in visible_rows(page, "flow")
    page.locator('#waterfall g.row[data-id="r2"] .caret').click()
    assert len(visible_rows(page)) == 6
    page.click("#collapse")
    assert visible_rows(page) == ["planner", "r1", "r2", "final"]
    assert page.locator("#collapse").text_content() == "Expand"
    page.click("#collapse")
    assert len(visible_rows(page)) == 6
    page.locator('#waterfall g.row[data-id="r1"]').focus()
    page.keyboard.press("ArrowLeft")
    assert "r1-search" not in visible_rows(page)
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Enter")
    assert page.evaluate("__trace.selected") == "r1"


def test_critical_path_highlights_the_chain_that_sets_the_total(open_page):
    page = open_page(_nested())
    page.click("#crit")
    assert page.locator("#crit").get_attribute("aria-pressed") == "true"
    crit = page.evaluate(
        "[...document.querySelectorAll('#waterfall g.row.crit')].map(g => g.dataset.id)"
    )
    assert crit == ["planner", "r2", "r2-llm", "final"]
    dim = page.evaluate(
        "getComputedStyle(document.querySelector('#waterfall g.row[data-id=r1]')).opacity"
    )
    assert float(dim) < 0.5
    stroke = page.evaluate(
        "getComputedStyle(document.querySelector('#waterfall g.row[data-id=r2] .bar')).stroke"
    )
    assert stroke == "rgb(245, 158, 11)"
    page.click("#crit")
    assert (
        page.evaluate(
            "getComputedStyle(document.querySelector('#waterfall g.row[data-id=r1]')).opacity"
        )
        == "1"
    )


def test_theme_follows_the_system_and_the_button_toggles_it(open_page):
    page = open_page(scheme="light")
    assert page.evaluate("document.documentElement.dataset.theme") == "light"
    bg = page.evaluate(
        "getComputedStyle(document.querySelector('#waterfall rect.bg')).fill"
    )
    page.click("#theme")
    assert page.evaluate("document.documentElement.dataset.theme") == "dark"
    assert (
        page.evaluate(
            "getComputedStyle(document.querySelector('#waterfall rect.bg')).fill"
        )
        != bg
    )
    fixed = open_page(_source(theme="light"), scheme="dark")
    assert fixed.evaluate("document.documentElement.dataset.theme") == "light"


def test_zoom_buttons_and_fit(open_page):
    page = open_page()
    start = page.evaluate("__trace.zoom")
    page.click("#zin")
    assert page.evaluate("__trace.zoom") > start
    page.click("#fit")
    assert page.evaluate("__trace.zoom") == pytest.approx(start)


def test_exports_are_standalone(open_page, tmp_path):
    page = open_page(_nested())
    page.locator('#waterfall g.row[data-id="r2"] .caret').click()
    page.click("#export summary")
    with page.expect_download() as info:
        page.click("#save")
    svg = Path(info.value.path()).read_text(encoding="utf-8")
    assert svg.startswith("<svg") and "<style>" in svg and "r2-llm" not in svg
    assert "tabindex" not in svg and "<script" not in svg
    page.click("#export summary")
    with page.expect_download() as info:
        page.click("#png")
    png = Path(info.value.path()).read_bytes()
    assert png.startswith(b"\x89PNG") and len(png) > 5000
    page.click("#export summary")
    with page.expect_download() as info:
        page.click("#html")
    saved = tmp_path / "saved.html"
    saved.write_bytes(Path(info.value.path()).read_bytes())
    again = page.context.new_page()
    errors: list[str] = []
    again.on("pageerror", lambda exc: errors.append(str(exc)))
    again.on(
        "console", lambda msg: errors.append(msg.text) if msg.type == "error" else None
    )
    again.goto(saved.as_uri())
    again.locator("body[data-ready]").wait_for(state="attached")
    assert errors == []
    assert again.locator("#card").is_hidden()


def test_otel_source_renders_in_the_page(open_page):
    page = open_page(OTEL_EXAMPLE, width=560, height=430)
    assert page.errors == []
    page.evaluate("__trace.select('c1')")
    assert page.locator("#c-docs").is_visible()
    stats = page.locator("#card .stats").text_content()
    assert "1.4k" in stats and "120" in stats


def test_embedded_page_hides_its_title_and_asks_the_host_to_open_links(
    browser, tmp_path
):
    (tmp_path / "inner.html").write_bytes(
        TraceRenderer().render("agent_trace", EXAMPLE, "html").content
    )
    (tmp_path / "host.html").write_text(
        "<!doctype html><body style='margin:0'><script>window.got=[];"
        "addEventListener('message',e=>window.got.push(e.data))</script>"
        "<iframe src='inner.html' sandbox='allow-scripts' style='width:560px;height:430px;border:0'>"
        "</iframe></body>",
        encoding="utf-8",
    )
    context = browser.new_context(viewport={"width": 580, "height": 450})
    try:
        page = context.new_page()
        page.goto((tmp_path / "host.html").as_uri())
        frame = page.frame_locator("iframe")
        frame.locator("body[data-ready]").wait_for(state="attached")
        assert frame.locator("header h1").is_hidden()
        page.wait_for_function(
            "window.got.some(m => m && m.type === 'uml-mcp/plugin-ready')"
        )
        frame.locator('#waterfall g.row[data-id="answer"] .bar').click()
        frame.locator("#c-docs").click()
        page.wait_for_function(
            "window.got.some(m => m && m.type === 'uml-mcp/open-link')"
        )
        sent = page.evaluate(
            "window.got.filter(m => m && m.type === 'uml-mcp/open-link')"
        )
        assert sent == [
            {"type": "uml-mcp/open-link", "url": "https://platform.openai.com/docs"}
        ]
        frame.locator("#card .close").click()
        frame.locator('#waterfall g.row[data-id="search"] .bar').click()
        frame.locator("#card .doc .ds button").first.click()
        page.wait_for_function(
            "window.got.filter(m => m && m.type === 'uml-mcp/open-link').length === 2"
        )
        assert page.evaluate(
            "window.got.filter(m => m && m.type === 'uml-mcp/open-link')[1].url"
        ) == ("https://example.com/help/refunds")
    finally:
        context.close()
