"""The timeline plugin: validation messages, the static SVG, page safety and the browser page."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from html import unescape
from pathlib import Path

import pytest

SRC = (
    Path(__file__).resolve().parents[1] / "examples/plugins/uml-mcp-plugin-timeline/src"
)
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from uml_mcp_plugin_timeline import TimelineRenderer
from uml_mcp_plugin_timeline.model import iso, parse, parse_date
from uml_mcp_plugin_timeline.samples import EXAMPLE, TEMPLATE
from uml_mcp_plugin_timeline.svg import LEVELS, tick_unit

SVG_NS = "{http://www.w3.org/2000/svg}"
ROADMAP = json.loads(EXAMPLE)
DEPENDENCIES = sum(len(i.get("depends_on", [])) for i in ROADMAP["items"])


def src(*items, lanes=None, **top) -> str:
    return json.dumps(
        {"lanes": lanes or [{"id": "a", "name": "A"}], "items": list(items), **top}
    )


def num(element: ET.Element, attr: str) -> float:
    value = element.get(attr)
    assert value is not None, attr
    return float(value)


def problems(code: str) -> list[str]:
    return TimelineRenderer().validate("timeline", code)


def test_registers_one_sandboxed_type():
    renderer = TimelineRenderer()
    assert set(renderer.diagram_types) == {"timeline"}
    spec = renderer.diagram_types["timeline"]
    assert spec.formats == ("html", "svg")
    assert spec.security_profile == "sandboxed"
    for code in (spec.example, spec.template, EXAMPLE, TEMPLATE):
        assert code is not None and problems(code) == []


def test_the_roadmap_example_has_what_the_docs_promise():
    lanes = {lane["id"] for lane in ROADMAP["lanes"]}
    kinds = [i.get("kind", "task") for i in ROADMAP["items"]]
    assert len(lanes) == 3
    assert {"phase", "milestone", "release"} <= set(kinds)
    assert any(i.get("status") == "blocked" for i in ROADMAP["items"])
    assert DEPENDENCIES >= 5


@pytest.mark.parametrize(
    ("text", "end", "want"),
    [
        ("2026-11-07", False, "2026-11-07"),
        ("2026-Q3", False, "2026-07-01"),
        ("2026-Q3", True, "2026-09-30"),
        ("2026-q4", True, "2026-12-31"),
        ("2028-02", True, "2028-02-29"),
        ("2026-12", True, "2026-12-31"),
        (" 2026-01-05 ", False, "2026-01-05"),
    ],
)
def test_dates_months_and_quarters(text, end, want):
    assert iso(parse_date(text, end=end)) == want


@pytest.mark.parametrize(
    ("code", "message"),
    [
        ("{", "not valid JSON"),
        ("[]", "JSON object"),
        (src(), '"items" must be a non-empty list'),
        (
            json.dumps({"items": [{"id": "x", "start": "2026-01-01"}]}),
            '"lanes" must be',
        ),
        (
            src({"id": "x", "start": "2026-13-01"}),
            'item "x": start "2026-13-01" is not a real date',
        ),
        (
            src({"id": "x", "start": "next week"}),
            'item "x": start "next week" is not a date',
        ),
        (
            src({"id": "x", "start": "2026-05-01", "end": "2026-04-01"}),
            'item "x": end 2026-04-01 is before start 2026-05-01',
        ),
        (
            src(
                {"id": "x", "start": "2026-01-01"},
                {"id": "y", "start": "2026-01-01", "lane": "b"},
            ),
            'item "y": lane "b" is not a lane id (lanes: a)',
        ),
        (
            src({"id": "x", "start": "2026-01-01", "depends_on": ["nope"]}),
            'item "x": depends_on "nope" is not an item id',
        ),
        (
            src({"id": "x", "start": "2026-01-01", "depends_on": ["x"]}),
            'item "x": depends on itself',
        ),
        (
            src(
                {"id": "a1", "start": "2026-01-01", "depends_on": ["c1"]},
                {"id": "b1", "start": "2026-01-01", "depends_on": ["a1"]},
                {"id": "c1", "start": "2026-01-01", "depends_on": ["b1"]},
            ),
            "dependency cycle: a1 → c1 → b1 → a1",
        ),
        (
            src(
                {
                    "id": "m",
                    "kind": "milestone",
                    "start": "2026-01-01",
                    "end": "2026-01-09",
                }
            ),
            'item "m": a milestone is a single date',
        ),
        (
            src({"id": "x", "start": "2026-01-01", "kind": "epic"}),
            'item "x": kind "epic" is not one of',
        ),
        (
            src({"id": "x", "start": "2026-01-01", "status": "late"}),
            'item "x": status "late" is not one of',
        ),
        (
            src({"id": "x", "start": "2026-01-01", "progress": 140}),
            'item "x": progress must be a number from 0 to 100',
        ),
        (
            src({"id": "x", "start": "2026-01-01", "link": "http://example.com"}),
            'item "x": link "http://example.com" must be an https:// URL',
        ),
        (
            src({"id": "x", "start": "2026-01-01", "dependencies": []}),
            'item "x": unknown field "dependencies"; use "depends_on"',
        ),
        (
            src({"id": "x", "start": "2026-01-01"}, {"id": "x", "start": "2026-01-02"}),
            'item "x": duplicate item id',
        ),
        (src({"id": "x"}), 'item "x": start is required'),
        (src({"start": "2026-01-01"}), "item 1: id is required"),
        (
            src(
                {"id": "x", "start": "2026-01-01"}, lanes=[{"id": "a", "color": "blue"}]
            ),
            'lane "a": color "blue" must be a hex colour',
        ),
        (
            src({"id": "x", "start": "2026-01-01"}, scale="year"),
            'scale "year" is not one of',
        ),
        (src({"id": "x", "start": "2026-01-01"}, today="soon"), "timeline: today"),
        (
            src({"id": "x", "start": "2026-01-01"}, lanes=[{"id": "a"}, {"id": "b"}]),
            'item "x": lane is required (lanes: a, b)',
        ),
    ],
)
def test_readable_validation_messages(code, message):
    found = problems(code)
    assert any(message in p for p in found), found


def test_every_problem_is_reported_at_once():
    found = problems(
        src(
            {"id": "x", "start": "2026-02-30"},
            {"id": "y", "start": "2026-01-01", "lane": "zzz"},
            {"id": "z", "start": "2026-01-01", "depends_on": ["ghost"]},
        )
    )
    assert len(found) == 3
    with pytest.raises(ValueError, match="invalid timeline source"):
        TimelineRenderer().render("timeline", src({"id": "x"}), "svg")


def test_defaults_single_lane_quarter_tasks_and_progress():
    tl = parse(
        src(
            {"id": "t", "start": "2026-Q2"},
            {"id": "d", "start": "2026-01-01", "end": "2026-01-10", "status": "done"},
            {"id": "m", "kind": "release", "start": "2026-03-01"},
        )
    )
    by_id = {i.id: i for i in tl.items}
    assert by_id["t"].lane == "a"
    assert (iso(by_id["t"].start), iso(by_id["t"].end)) == ("2026-04-01", "2026-06-30")
    assert by_id["d"].progress == 100 and by_id["t"].progress == 0
    assert by_id["m"].point and by_id["m"].start == by_id["m"].end
    assert tl.title == "Roadmap" and tl.theme == "auto"


def test_configure_limits_items():
    renderer = TimelineRenderer()
    renderer.configure({"max_items": 2})
    code = src(*({"id": f"i{n}", "start": "2026-01-01"} for n in range(3)))
    assert "3 items; the limit is 2" in renderer.validate("timeline", code)[0]
    with pytest.raises(ValueError):
        renderer.configure({"max_items": 0})
    assert renderer.validate("other", code) == ["unknown timeline type: other"]
    with pytest.raises(ValueError):
        renderer.render("timeline", EXAMPLE, "png")


def _svg(code: str = EXAMPLE) -> ET.Element:
    out = TimelineRenderer().render("timeline", code, "svg")
    assert out.mime_type == "image/svg+xml"
    assert b"<script" not in out.content and b"var(--" not in out.content
    return ET.fromstring(out.content)


def test_static_svg_draws_every_part():
    root = _svg()
    groups = {g.get("data-id"): g for g in root.iter(f"{SVG_NS}g") if g.get("data-id")}
    assert set(groups) == {i["id"] for i in ROADMAP["items"]}
    classes = {i: g.get("class") or "" for i, g in groups.items()}
    assert "phase" in classes["beta-phase"] and "milestone" in classes["beta"]
    assert "release" in classes["ga"] and "st-blocked" in classes["billing"]
    deps = [p for p in root.iter(f"{SVG_NS}path") if p.get("marker-end")]
    assert len(deps) == DEPENDENCIES  # the legend arrow is a line
    text = ET.tostring(root, encoding="unicode")
    for word in (
        "Platform",
        "Product",
        "Go-to-market",
        "TODAY",
        "Depends on",
        "Blocked",
        "2027",
    ):
        assert word in text
    # the blocked bar is dashed; the progress fill covers 55% of the API bar
    bars = [r for r in groups["api"].iter(f"{SVG_NS}rect") if r.get("height") == "18"]
    assert abs(num(bars[1], "width") / num(bars[0], "width") - 0.55) < 0.01
    assert any(
        r.get("stroke-dasharray") for r in groups["billing"].iter(f"{SVG_NS}rect")
    )


def test_dependency_arrows_run_from_end_to_start():
    root = _svg(
        src(
            {"id": "a", "start": "2026-01-05", "end": "2026-01-16"},
            {
                "id": "b",
                "start": "2026-02-02",
                "end": "2026-02-13",
                "depends_on": ["a"],
            },
            scale="week",
        )
    )
    bars = {
        g.get("data-id"): next(g.iter(f"{SVG_NS}rect"))
        for g in root.iter(f"{SVG_NS}g")
        if g.get("data-id")
    }
    a_end = num(bars["a"], "x") + num(bars["a"], "width")
    b_start = num(bars["b"], "x")
    deps = next(g for g in root.iter(f"{SVG_NS}g") if g.get("class") == "deps")
    (path,) = list(deps)
    numbers = [float(n) for n in re.findall(r"[\d.]+", path.get("d") or "")]
    assert abs(numbers[0] - a_end) < 0.2
    assert abs(numbers[-1] - (b_start - 1)) < 0.2


@pytest.mark.parametrize(
    ("scale", "label"),
    [("quarter", ">Q3<"), ("month", ">Aug<"), ("week", ">Aug 3<"), ("day", ">12<")],
)
def test_scale_picks_ticks(scale, label):
    code = src({"id": "x", "start": "2026-08-03", "end": "2026-08-20"}, scale=scale)
    text = TimelineRenderer().render("timeline", code, "svg").content.decode()
    assert label in text
    assert tick_unit(LEVELS[scale]) == scale


def test_themes_and_today_line():
    light = (
        TimelineRenderer()
        .render("timeline", json.dumps(ROADMAP | {"theme": "light"}), "svg")
        .content.decode()
    )
    dark = (
        TimelineRenderer()
        .render("timeline", json.dumps(ROADMAP | {"theme": "dark"}), "svg")
        .content.decode()
    )
    assert 'fill="#ffffff"' in light and 'fill="#0b1020"' in dark
    far = src({"id": "x", "start": "2001-01-01", "end": "2001-02-01"})
    assert (
        "TODAY"
        not in TimelineRenderer().render("timeline", far, "svg").content.decode()
    )


def test_text_is_escaped():
    code = src(
        {
            "id": "x",
            "name": "<script>alert(1)</script> & co",
            "start": "2026-01-01",
            "end": "2026-01-30",
        },
        title="A <b>&</b>",
    )
    svg = TimelineRenderer().render("timeline", code, "svg").content.decode()
    ET.fromstring(svg)
    assert "<script" not in svg and "&lt;script&gt;" in svg
    page = TimelineRenderer().render("timeline", code, "html").content.decode()
    data = re.search(
        r'<script type="application/json" id="spec">(.*?)</script>', page, re.DOTALL
    )
    assert data and "<" not in data.group(1)


def test_static_svg_rasterizes():
    resvg_py = pytest.importorskip("resvg_py")
    from mcp_core.core.svg_raster import _resvg_kwargs

    svg = TimelineRenderer().render("timeline", EXAMPLE, "svg").content.decode()
    png = bytes(resvg_py.svg_to_bytes(**_resvg_kwargs(svg, zoom=1.0)))
    assert png.startswith(b"\x89PNG")


def _grab(pattern: str, text: str) -> str:
    match = re.search(pattern, text, re.DOTALL)
    assert match
    return match.group(1)


def test_page_is_csp_locked_and_offline():
    page = TimelineRenderer().render("timeline", EXAMPLE, "html").content.decode()
    csp = unescape(
        _grab(r'http-equiv="Content-Security-Policy" content="([^"]+)"', page)
    )
    script = _grab(r"<script>(.*?)</script>", page)
    style = _grab(r"<style>(.*?)</style>", page)
    for text in (script, style):
        digest = base64.b64encode(hashlib.sha256(text.encode()).digest()).decode()
        assert f"sha256-{digest}" in csp
    assert "default-src 'none'" in csp and "connect-src" not in csp
    assert not re.search(r"https?://(?!www\.w3\.org)", script)
    assert " style=" not in page


playwright = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as pw:
        b = pw.chromium.launch()
        yield b
        b.close()


def _open(browser, code: str = EXAMPLE, width: int = 1280, height: int = 760):
    page = browser.new_page(viewport={"width": width, "height": height})
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.set_content(
        TimelineRenderer().render("timeline", code, "html").content.decode()
    )
    page.wait_for_selector("body[data-ready='1']")
    return page, errors


def _visible_ids(page) -> list[str]:
    return page.eval_on_selector_all(
        "#stage .item", "els => els.map(e => e.dataset.id)"
    )


def test_page_fits_on_load_and_zooms(browser):
    page, errors = _open(browser)
    span = page.evaluate(
        """() => { const t = window.__timeline, s = t.state, v = document.getElementById('view');
          const plot = v.clientWidth - (v.clientWidth < 640 ? 108 : 168);
          return [s.t0, s.t0 + plot / s.ppd]; }"""
    )
    tl = parse(EXAMPLE)
    first, last = tl.span
    assert span[0] <= first and span[1] >= last
    assert sorted(_visible_ids(page)) == sorted(i["id"] for i in ROADMAP["items"])
    for level in ("quarter", "month", "week", "day"):
        page.click(f"button[data-level={level}]")
        assert page.evaluate("window.__timeline.state.ppd") == LEVELS[level]
        page.wait_for_selector(f"button[data-level={level}][aria-pressed=true]")
    ppd = page.evaluate("window.__timeline.state.ppd")
    page.click("#zout")
    assert page.evaluate("window.__timeline.state.ppd") < ppd
    box = page.locator("#view").bounding_box()
    page.mouse.move(box["x"] + 600, box["y"] + 200)
    before = page.evaluate("window.__timeline.state.ppd")
    page.mouse.wheel(0, -400)
    page.wait_for_timeout(50)
    assert page.evaluate("window.__timeline.state.ppd") > before
    t0 = page.evaluate("window.__timeline.state.t0")
    page.mouse.down()
    page.mouse.move(box["x"] + 400, box["y"] + 200, steps=5)
    page.mouse.up()
    page.wait_for_timeout(50)
    assert page.evaluate("window.__timeline.state.t0") > t0
    page.click("#fit")
    assert page.evaluate("window.__timeline.state.t0") <= first
    page.keyboard.press("+")
    page.click("#now")
    centre = page.evaluate(
        """() => { const s = window.__timeline.state, v = document.getElementById('view');
          return s.t0 + (v.clientWidth - 168 - 16) / 2 / s.ppd; }"""
    )
    assert abs(centre - (parse_date("2026-11-07") + 0.5)) < 0.01
    assert page.locator("#stage .today").count() == 1
    assert not errors
    page.close()


def test_filters_by_lane_owner_and_status(browser):
    page, errors = _open(browser)
    page.select_option("#f-lane", "gtm")
    assert sorted(_visible_ids(page)) == ["launch", "pricing", "summit"]
    assert page.locator("#stage text", has_text="Platform").count() == 0
    page.select_option("#f-lane", "")
    page.select_option("#f-owner", "Marco")
    assert sorted(_visible_ids(page)) == ["api", "beta-phase", "billing"]
    page.select_option("#f-owner", "")
    page.select_option("#f-status", "blocked")
    assert _visible_ids(page) == ["billing"]
    page.select_option("#f-status", "")
    assert len(_visible_ids(page)) == len(ROADMAP["items"])
    assert not errors
    page.close()


def test_detail_card_and_dependency_chain(browser):
    page, errors = _open(browser)
    page.locator('#stage .item[data-id="api"] text').click()
    card = page.locator("#card")
    assert card.is_visible()
    text = card.inner_text()
    for want in (
        "Public API v2",
        "Oct 12, 2026 → Dec 11, 2026",
        "61 days",
        "Marco",
        "55%",
        "SSO and SCIM",
        "Usage billing",
        "Mobile app",
        "REST and webhooks",
    ):
        assert want in text, want
    assert page.locator("#card progress").evaluate("p => p.value") == 55
    dim = set(
        page.eval_on_selector_all(
            "#stage .item.dim", "els => els.map(e => e.dataset.id)"
        )
    )
    # api's chain: auth upstream; billing, mobile and ga downstream
    assert dim == {"beta-phase", "editor", "beta", "pricing", "launch", "summit"}
    assert page.locator("#stage .deps path.on").count() == 5
    assert page.locator("#open-link").count() == 0
    page.click("#card ul.links button:has-text('SSO and SCIM')")
    assert page.evaluate("window.__timeline.state.selected") == "auth"
    page.evaluate(
        "() => { window.__opened = []; window.open = (u) => { window.__opened.push(u); return null; }; }"
    )
    page.click("#open-link")
    assert page.evaluate("window.__opened") == ["https://example.com/roadmap/sso"]
    page.keyboard.press("Escape")
    assert card.is_hidden()
    assert page.locator("#stage .item.dim").count() == 0
    page.locator('#stage .item[data-id="beta"] path').click()
    assert "Nov 2, 2026" in card.inner_text() and "Duration" not in card.inner_text()
    assert not errors
    page.close()


def test_theme_and_exports(browser, tmp_path):
    page, errors = _open(browser)
    before = page.get_attribute("html", "data-theme")
    page.click("#theme")
    after = page.get_attribute("html", "data-theme")
    assert after != before
    bg = page.get_attribute("#stage svg rect.bg", "fill")
    assert bg == ("#0b1020" if after == "dark" else "#ffffff")
    svg = page.evaluate("window.__timeline.svgText()")
    root = ET.fromstring(svg.split("?>", 1)[1])
    ids = {g.get("data-id") for g in root.iter(f"{SVG_NS}g") if g.get("data-id")}
    assert ids == {i["id"] for i in ROADMAP["items"]}
    assert "Product roadmap" in svg and "Depends on" in svg
    page.click("details.menu summary")
    with page.expect_download() as dl:
        page.click("#png")
    path = tmp_path / "out.png"
    dl.value.save_as(path)
    assert path.read_bytes().startswith(b"\x89PNG")
    with page.expect_download() as dl:
        page.click("details.menu summary")
        page.click("#save")
    assert dl.value.suggested_filename == "Product-roadmap-2026-27.svg"
    exported = page.evaluate("window.__timeline.htmlText()")
    html_tag = re.search(r"<html[^>]*>", exported)
    assert html_tag and "data-embedded" not in html_tag.group(0)
    assert f'data-theme="{after}"' in html_tag.group(0)
    again, again_errors = _open_html(browser, exported)
    assert len(_visible_ids(again)) == len(ROADMAP["items"])
    assert not errors and not again_errors
    again.close()
    page.close()


def _open_html(browser, html: str):
    page = browser.new_page(viewport={"width": 1000, "height": 700})
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.set_content(html)
    page.wait_for_selector("body[data-ready='1']")
    return page, errors


def test_static_and_interactive_layouts_agree(browser):
    """svg.py and timeline.js lay out the same bars at the same zoom."""
    tl = parse(EXAMPLE)
    first, last = tl.span
    ppd = min(60.0, max(0.25, 1000 / (last - first)))
    root = _svg()
    static = {
        g.get("data-id"): num(next(g.iter(f"{SVG_NS}rect")), "x")
        for g in root.iter(f"{SVG_NS}g")
        if g.get("data-id") and "task" in (g.get("class") or "")
    }
    page, _ = _open(browser)
    live = page.evaluate(
        f"""() => {{ const t = window.__timeline; t.state.ppd = {ppd};
          const out = t.draw({{full: true}}).svg, got = {{}};
          out.querySelectorAll('g.item.task').forEach(g => got[g.dataset.id] = +g.querySelector('rect').getAttribute('x'));
          return got; }}"""
    )
    assert static.keys() == live.keys()
    for key, x in static.items():
        assert abs(live[key] - x) < 0.2, key
    page.close()


def test_small_frame_560x430(browser, tmp_path):
    page, errors = _open(browser, width=560, height=430)
    assert page.evaluate("document.documentElement.scrollWidth") <= 560
    view = page.locator("#view").bounding_box()
    assert view["height"] >= 250
    header = page.locator("header").bounding_box()
    assert header["height"] <= 90
    for control in ("#zin", "#now", "#fit", "#theme"):
        assert page.locator(control).is_visible()
    assert page.locator("button[data-level=month] .short").is_visible()
    page.locator('#stage .item[data-id="api"] text').click()
    card = page.locator("#card").bounding_box()
    assert (
        card["y"] + card["height"] <= 430
        and card["x"] >= 0
        and card["x"] + card["width"] <= 560
    )
    page.keyboard.press("Escape")
    page.screenshot(path=str(tmp_path / "small.png"))
    assert not errors
    page.close()


def test_embedded_page_hides_title_and_asks_host_to_open_links(browser):
    page = browser.new_page(viewport={"width": 560, "height": 430})
    page.set_content(
        "<!doctype html><body style='margin:0'><iframe id='f' style='border:0;width:560px;height:430px'></iframe>"
        "<script>window.got=[];addEventListener('message',e=>got.push(e.data));</script></body>"
    )
    html = TimelineRenderer().render("timeline", EXAMPLE, "html").content.decode()
    frame = page.frame_locator("#f")
    page.eval_on_selector("#f", "(f, html) => { f.srcdoc = html; }", html)
    frame.locator("body[data-ready='1']").wait_for()
    inner = page.frames[1]
    assert inner.get_attribute("html", "data-embedded") == "1"
    assert not inner.locator("h1").is_visible()
    inner.evaluate("window.__timeline.select('ga', true)")
    inner.click("#open-link")
    page.wait_for_function("window.got.some(m => m.type === 'uml-mcp/open-link')")
    messages = page.evaluate("window.got")
    assert {
        "type": "uml-mcp/plugin-ready",
        "exports": ["svg", "png", "html"],
    } in messages
    assert {
        "type": "uml-mcp/open-link",
        "url": "https://example.com/releases/2.0",
    } in messages
    page.close()


_MCP_DRIVER = r"""
import asyncio, base64, importlib.metadata as md, json, logging, sys
logging.disable(logging.CRITICAL)
sys.path.insert(0, sys.argv[1])
from mcp_core.plugins import loader
from mcp_core.plugins.api import RENDERERS_GROUP
EPS = {RENDERERS_GROUP: [md.EntryPoint("timeline", "uml_mcp_plugin_timeline:TimelineRenderer", RENDERERS_GROUP)]}
loader.entry_points = lambda group: EPS.get(group, [])
from fastmcp import Client
from fastmcp.exceptions import ToolError
from mcp_core.core.server import get_mcp_server
from uml_mcp_plugin_timeline.samples import EXAMPLE

async def call(client, name, arguments):
    try:
        return (await client.call_tool(name, arguments)).structured_content
    except ToolError as exc:
        return {"error": str(exc)}

async def main():
    out = {}
    async with Client(get_mcp_server()) as client:
        out["examples"] = "timeline" in (await client.read_resource("uml://examples"))[0].text
        svg = await call(client, "generate_uml", {"diagram_type": "timeline", "code": EXAMPLE, "output_format": "svg", "theme": "light"})
        out["svg"] = base64.b64decode(svg["content_base64"]).decode()[:4000]
        out["png"] = (await call(client, "generate_uml_image", {"diagram_type": "timeline", "code": EXAMPLE})).get("mime_type")
        html = await call(client, "generate_uml", {"diagram_type": "timeline", "code": EXAMPLE, "output_format": "html", "output_dir": sys.argv[2]})
        out["html"] = html.get("local_path")
        bad = '{"lanes": [{"id": "a"}], "items": [{"id": "x", "start": "2026-05-01", "end": "2026-04-01"}]}'
        out["validate"] = await call(client, "validate_uml", {"diagram_type": "timeline", "code": bad, "output_format": "svg"})
    print("TIMELINE_JSON " + json.dumps(out))

asyncio.run(main())
"""


def test_through_a_real_mcp_server(tmp_path):
    import os
    import subprocess

    root = Path(__file__).resolve().parents[1]
    config = tmp_path / "uml-mcp.yaml"
    config.write_text("plugins:\n  enabled: [timeline]\n", encoding="utf-8")
    env = os.environ.copy()
    env.pop("MOCK_FASTMCP", None)
    env.update(
        {
            "USE_REAL_FASTMCP": "1",
            "TESTING": "0",
            "UML_MCP_CONFIG": str(config),
            "MCP_OUTPUT_ROOT": str(tmp_path),
            "MCP_MEMORY_ONLY": "false",
            "MCP_URL_ONLY": "false",
            "PYTHONPATH": str(root) + os.pathsep + env.get("PYTHONPATH", ""),
        }
    )
    done = subprocess.run(
        [sys.executable, "-c", _MCP_DRIVER, str(SRC), str(tmp_path)],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=180,
        check=False,
    )
    line = next(
        (x for x in done.stdout.splitlines() if x.startswith("TIMELINE_JSON ")), None
    )
    assert line, done.stdout[-2000:] + done.stderr[-4000:]
    report = json.loads(line.removeprefix("TIMELINE_JSON "))
    assert report["examples"]
    assert 'fill="#ffffff"' in report["svg"]  # the theme argument reached the source
    assert report["png"] == "image/png"
    assert report["html"] and Path(report["html"]).read_text(
        encoding="utf-8"
    ).startswith("<!doctype html>")
    assert "end 2026-04-01 is before start 2026-05-01" in json.dumps(report["validate"])
