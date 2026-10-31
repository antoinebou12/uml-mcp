"""The D3 pages in a real browser: zoom, pan, drag, A* re-routing, pinning, HTML export.

The pages opened here are the ones an MCP client received from the real server
(``mcp_report`` writes them to disk), so this covers the whole chain: MCP tool call, page,
browser. Skipped when Playwright or a Chromium build is not available (plain CI runners);
run locally with ``uv sync --all-groups``. Set ``PLAYWRIGHT_CHROMIUM`` to use a specific
browser binary.
"""

from __future__ import annotations

import glob
import itertools
import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from tests.fixtures_d3 import PNG_1PX, grab, spec_of

sync_api = pytest.importorskip("playwright.sync_api")

# What the page looks like right now: where every box is, and whether any arrow passes
# through a box (sampled along the real SVG path, not computed from our own data).
MEASURE = """
() => {
  const rects = [...document.querySelectorAll('g.node')].map(g => {
    const m = /translate\\(([-\\d.]+)[ ,]+([-\\d.]+)\\)/.exec(g.getAttribute('transform'));
    const t = g.querySelector('rect.card');
    return {id: g.dataset.id, x: +m[1], y: +m[2], w: +t.getAttribute('width'), h: +t.getAttribute('height')};
  });
  const through = [];
  for (const e of document.querySelectorAll('g.edge')) {
    const p = e.querySelector('path'), len = p.getTotalLength();
    for (let s = 0; s <= len; s += 2) {
      const pt = p.getPointAtLength(s);
      const hit = rects.find(r => pt.x > r.x + 2 && pt.x < r.x + r.w - 2 && pt.y > r.y + 2 && pt.y < r.y + r.h - 2);
      if (hit) { through.push(e.dataset.from + '->' + e.dataset.to + ' through ' + hit.id); break; }
    }
  }
  const overlaps = [];
  for (let i = 0; i < rects.length; i++) for (let j = i + 1; j < rects.length; j++) {
    const a = rects[i], b = rects[j];
    if (a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h) overlaps.push(a.id + '/' + b.id);
  }
  const groups = [...document.querySelectorAll('g.group')].map(g => {
    const r = g.querySelector('rect');
    return {id: g.dataset.id, x: +r.getAttribute('x'), y: +r.getAttribute('y'), w: +r.getAttribute('width'), h: +r.getAttribute('height')};
  });
  return {rects, groups, through, overlaps};
}
"""


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


@pytest.fixture
def open_page(browser, request):
    """Open a page the MCP client received (or any file path) and collect its errors."""
    contexts = []

    def open_(name: str | Path):
        path = (
            name
            if isinstance(name, Path)
            else Path(request.getfixturevalue("mcp_report")["pages_dir"]) / name
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 720}, accept_downloads=True
        )
        contexts.append(context)
        page = context.new_page()
        problems: list[str] = []
        page.on(
            "console",
            lambda m: (
                problems.append(f"{m.type}: {m.text}")
                if m.type in ("error", "warning")
                else None
            ),
        )
        page.on("pageerror", lambda e: problems.append(f"pageerror: {e}"))
        page.goto(path.as_uri())
        page.wait_for_selector("body[data-ready]", timeout=15000)
        page.wait_for_timeout(300)
        return page, problems

    yield open_
    for context in contexts:
        context.close()


def choose_export(page, button: str) -> None:
    """Export is a menu: open it, then pick Save SVG, Save PNG or Save HTML."""
    page.click("details.menu summary")
    page.click(button)


@pytest.mark.parametrize("automatic", [False, True])
def test_commerce_containers_route_and_survive_html_export(
    open_page, tmp_path, automatic
) -> None:
    from uml_mcp_plugin_d3 import D3Renderer

    from tests.fixtures_d3 import D3_SRC

    source = json.loads(
        (D3_SRC.parent / "examples/commerce-containers.json").read_text(
            encoding="utf-8"
        )
    )
    # "root" is a valid group ID, not a reserved browser hierarchy sentinel.
    source["groups"][0]["id"] = "root"
    for group in source["groups"]:
        if group.get("parent") == "commerce":
            group["parent"] = "root"
    if automatic:
        source.pop("groups")
        source["group_by"] = "category"
        for node in source["nodes"]:
            node.pop("group")
    renderer = D3Renderer()
    renderer.configure({"d3_source": "inline"})
    path = tmp_path / "commerce.html"
    path.write_bytes(
        renderer.render("d3_architecture", json.dumps(source), "html").content
    )
    page, errors = open_page(path)
    assert page.locator("g.node").count() == 11
    assert page.locator("g.edge text").count() == 10
    assert page.locator("g.group").count() == (7 if automatic else 4)
    drag(page, 'g.node[data-id="database"] rect.card', -100, 90)
    live = measure(page)
    assert not live["through"] and not live["overlaps"]
    with page.expect_download() as download:
        choose_export(page, "#html")
    saved = tmp_path / "saved.html"
    download.value.save_as(saved)
    again, reopen_errors = open_page(saved)
    assert measure(again) == live
    drag(again, 'g.node[data-id="cache"] rect.card', 90, 50)
    assert not measure(again)["through"]
    assert errors == reopen_errors == []


def measure(page) -> dict:
    return page.evaluate(MEASURE)


@pytest.fixture
def commerce_page(open_page, tmp_path):
    from uml_mcp_plugin_d3 import D3Renderer

    from tests.fixtures_d3 import D3_SRC

    renderer = D3Renderer()
    renderer.configure({"d3_source": "inline"})
    source = (D3_SRC.parent / "examples/commerce-containers.json").read_text(
        encoding="utf-8"
    )
    path = tmp_path / "commerce.html"
    path.write_bytes(renderer.render("d3_architecture", source, "html").content)
    return open_page(path)


def assert_contained(page, original_groups):
    now = measure(page)
    assert now["groups"] == original_groups
    groups = {g["id"]: g for g in now["groups"]}
    for node in spec_of(page.content())["nodes"]:
        if not node["group"]:
            continue
        box = next(r for r in now["rects"] if r["id"] == node["id"])
        group = groups[node["group"]]
        assert group["x"] <= box["x"] <= group["x"] + group["w"] - box["w"]
        assert group["y"] <= box["y"] <= group["y"] + group["h"] - box["h"]


def test_click_selection_traces_nodes_nested_containers_and_keyboard(commerce_page):
    page, errors = commerce_page
    assert (
        page.get_by_role("button", name="Select node: Commerce API", exact=True).count()
        == 1
    )
    page.locator('g.node[data-id="api"] rect.card').click()
    page.mouse.move(2, 2)
    assert page.locator("g.node.selected").count() == 1
    assert page.locator(".connection-overlay path").count() == 9
    assert page.locator("g.edge.on").count() == 9
    assert "9 connections" in page.inner_text("#selection-status")
    page.locator('g.group[data-id="data"]').focus()
    page.keyboard.press("Enter")
    assert page.locator(".connection-overlay path").count() == 5
    page.locator('g.group[data-id="commerce"]').focus()
    page.keyboard.press("Space")
    assert page.locator(".connection-overlay path").count() == 10
    page.keyboard.press("Escape")
    assert page.locator(".connection-overlay path").count() == 0
    assert page.locator("#focus").is_disabled()
    assert page.locator("svg.hl").count() == 0
    assert errors == []


def test_focus_selection_zoom_and_background_clear(commerce_page):
    page, errors = commerce_page
    page.locator('g.node[data-id="api"] rect.card').click()
    page.click("#focus")
    page.wait_for_timeout(350)
    assert viewport_transform(page)[2] > 1.5
    box = page.locator('g.node[data-id="api"] rect.card').bounding_box()
    canvas = page.locator("#diagram").bounding_box()
    assert canvas["x"] < box["x"] < canvas["x"] + canvas["width"]
    assert canvas["y"] < box["y"] < canvas["y"] + canvas["height"]
    page.click("#fit")
    page.wait_for_timeout(350)
    page.locator("#diagram").click(position={"x": 4, "y": 4})
    assert page.locator(".connection-overlay path").count() == 0
    page.locator('g.group[data-id="data"] text').dblclick()
    page.wait_for_timeout(350)
    assert page.get_attribute('g.group[data-id="data"]', "aria-pressed") == "true"
    assert page.locator(".connection-overlay path").count() == 5
    assert errors == []


def test_physics_keeps_nodes_inside_fixed_containers_and_resets(commerce_page):
    page, errors = commerce_page
    before = measure(page)
    page.click("#physics")
    assert page.get_attribute("#physics", "aria-pressed") == "true"
    page.wait_for_function(
        "() => document.body.dataset.physics === 'settled'", timeout=15000
    )
    assert_contained(page, before["groups"])
    assert not measure(page)["overlaps"] and not measure(page)["through"]
    x, y = centre(page, 'g.node[data-id="database"] rect.card')
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x - 500, y + 350, steps=10)
    assert_contained(page, before["groups"])
    page.mouse.up()
    page.wait_for_function(
        "() => document.body.dataset.physics === 'settled'", timeout=15000
    )
    assert_contained(page, before["groups"])
    assert not measure(page)["overlaps"] and not measure(page)["through"]
    page.click("#reset")
    page.wait_for_timeout(350)
    assert page.get_attribute("#physics", "aria-pressed") == "false"
    assert sorted(measure(page)["rects"], key=lambda n: n["id"]) == sorted(
        before["rects"], key=lambda n: n["id"]
    )
    assert errors == []


def test_selected_physics_export_reopens_without_transient_overlay(
    commerce_page, open_page, tmp_path
):
    page, errors = commerce_page
    page.click("#physics")
    page.locator('g.group[data-id="data"]').focus()
    page.keyboard.press("Enter")
    with page.expect_download() as download:
        choose_export(page, "#html")
    saved = tmp_path / "physics.html"
    download.value.save_as(saved)
    live = measure(page)
    again, reopen_errors = open_page(saved)
    assert measure(again) == live
    assert again.get_attribute("#physics", "aria-pressed") == "false"
    assert again.locator(".connection-overlay path").count() == 0
    assert again.locator("svg.hl,.selected").count() == 0
    assert again.locator("#focus").is_disabled()
    with page.expect_download() as svg_download:
        choose_export(page, "#save")
    svg_path = tmp_path / "physics.svg"
    svg_download.value.save_as(svg_path)
    svg = ET.fromstring(svg_path.read_text(encoding="utf-8"))
    assert "hl" not in svg.attrib.get("class", "").split()
    assert "connection-overlay" not in svg_path.read_text(encoding="utf-8")
    assert errors == reopen_errors == []


def test_physics_reduced_motion_and_narrow_toolbar(commerce_page):
    page, errors = commerce_page
    page.set_viewport_size({"width": 390, "height": 700})
    page.emulate_media(reduced_motion="reduce")
    page.click("#physics")
    assert page.get_attribute("body", "data-physics") == "settled"
    drag(page, 'g.node[data-id="database"] rect.card', -50, 60)
    assert page.get_attribute("body", "data-physics") == "settled"
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert not measure(page)["overlaps"]
    assert errors == []


def centre(page, selector: str) -> tuple[float, float]:
    box = page.locator(selector).first.bounding_box()
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


def drag(page, selector: str, dx: float, dy: float) -> None:
    x, y = centre(page, selector)
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + dx, y + dy, steps=14)
    page.mouse.up()
    page.wait_for_timeout(250)


def node_xy(page, node_id: str) -> tuple[float, float]:
    t = page.get_attribute(f'g.node[data-id="{node_id}"]', "transform")
    x, y = grab(r"translate\(([-\d.]+)[ ,]+([-\d.]+)\)", t).groups()
    return float(x), float(y)


def viewport_transform(page) -> tuple[float, float, float]:
    t = page.get_attribute("g.viewport", "transform") or "translate(0,0) scale(1)"
    x, y = grab(r"translate\(([-\d.e]+)[ ,]+([-\d.e]+)\)", t).groups()
    k = re.search(r"scale\(([-\d.e]+)\)", t)
    return float(x), float(y), float(k.group(1)) if k else 1.0


ALL = ("d3_force", "d3_architecture", "d3_topology")
ARCH = ("d3_architecture", "d3_topology")
SVG_SELECTOR = {
    "d3_force": "#graph",
    "d3_architecture": "#diagram",
    "d3_topology": "#diagram",
}


@pytest.mark.parametrize("dtype", ALL)
def test_pages_start_clean(open_page, dtype: str) -> None:
    page, problems = open_page(f"{dtype}.html")
    assert problems == []  # no script errors and no Content-Security-Policy violations
    assert page.get_attribute("body", "data-ready") in ("force", "architecture")
    assert page.locator("g.node").count() == 8 if dtype == "d3_force" else 7
    assert page.title()


@pytest.mark.parametrize("dtype", ALL)
def test_the_content_security_policy_is_enforced(open_page, dtype: str) -> None:
    page, _ = open_page(f"{dtype}.html")
    page.evaluate(
        "() => { window.__violations = [];"
        " document.addEventListener('securitypolicyviolation',"
        " e => window.__violations.push(e.effectiveDirective)); }"
    )
    page.evaluate(
        "() => { const s = document.createElement('script');"
        " s.textContent = 'window.__injected = 1'; document.head.appendChild(s); }"
    )
    page.evaluate("() => fetch('http://127.0.0.1:9/leak').catch(() => null)")
    page.evaluate(
        "() => { const i = document.createElement('img');"
        " i.src = 'http://127.0.0.1:9/pixel.png'; document.body.appendChild(i); }"
    )
    page.wait_for_timeout(300)
    assert (
        page.evaluate("window.__injected") is None
    )  # an injected inline script never runs
    violations = set(page.evaluate("window.__violations"))
    assert {
        "script-src-elem",
        "connect-src",
        "img-src",
    } <= violations  # and nothing leaves


@pytest.mark.parametrize("dtype", ALL)
def test_wheel_zoom_and_background_drag_pan(open_page, dtype: str) -> None:
    page, _ = open_page(f"{dtype}.html")
    box = page.locator(SVG_SELECTOR[dtype]).bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.wheel(0, -500)
    page.wait_for_timeout(300)
    x0, y0, k = viewport_transform(page)
    assert k > 1.3
    page.mouse.move(box["x"] + 12, box["y"] + 12)
    page.mouse.down()
    page.mouse.move(box["x"] + 112, box["y"] + 72, steps=8)
    page.mouse.up()
    page.wait_for_timeout(200)
    x1, y1, k1 = viewport_transform(page)
    scale = page.evaluate(
        f"document.querySelector('{SVG_SELECTOR[dtype]}').getScreenCTM().a"
    )
    assert k1 == pytest.approx(k)
    assert x1 - x0 == pytest.approx(100 / scale, abs=2) and y1 - y0 == pytest.approx(
        60 / scale, abs=2
    )


@pytest.mark.parametrize("dtype", ALL)
def test_toolbar_zoom_fit_and_keys(open_page, dtype: str) -> None:
    page, _ = open_page(f"{dtype}.html")
    page.click("#zin")
    page.wait_for_timeout(350)
    assert viewport_transform(page)[2] > 1.2
    page.click("#zout")
    page.wait_for_timeout(350)
    assert viewport_transform(page)[2] == pytest.approx(1.0, abs=0.05)
    page.keyboard.press("+")
    page.wait_for_timeout(200)
    assert viewport_transform(page)[2] > 1.2
    page.click("#fit")
    page.wait_for_timeout(500)
    _, _, fitted = viewport_transform(page)
    assert 0.1 < fitted <= 4


def drag_to(page, node_id: str, x: float, y: float) -> None:
    """Grab a box by its tile and drop it with its grab point at screen ``(x, y)``."""
    start = node_xy(page, node_id)
    gx, gy = centre(page, f'g.node[data-id="{node_id}"] rect.card')
    page.mouse.move(gx, gy)
    page.mouse.down()
    page.mouse.move(x, y, steps=16)
    page.mouse.up()
    page.wait_for_timeout(250)
    # a drag that grabbed nothing would leave every later check passing for nothing
    assert node_xy(page, node_id) != start, f"{node_id} did not move"


def reset_view(page) -> None:
    page.click("#reset")
    page.wait_for_timeout(450)


@pytest.mark.parametrize("dtype", ARCH)
def test_dropping_a_box_on_another_pushes_it_aside(open_page, dtype: str) -> None:
    page, _ = open_page(f"{dtype}.html")
    initial = measure(page)
    assert initial["overlaps"] == [] and initial["through"] == []
    ids = [r["id"] for r in initial["rects"]]
    for dragged, target in itertools.pairwise(ids):
        x, y = centre(page, f'g.node[data-id="{target}"] rect.card')
        drag_to(page, dragged, x, y)  # straight onto the middle of its neighbour
        now = measure(page)
        assert now["overlaps"] == [], (dragged, target, now["overlaps"])
        assert now["through"] == [], (dragged, target, now["through"])
        reset_view(page)


@pytest.mark.parametrize("dtype", ARCH)
def test_a_box_dropped_on_an_arrow_makes_the_arrow_go_around(
    open_page, dtype: str
) -> None:
    page, _ = open_page(f"{dtype}.html")
    spec = spec_of(page.content())
    edge = max(
        spec["edges"], key=lambda e: len(e["points"])
    )  # the arrow with the most corners
    others = [
        n["id"] for n in spec["nodes"] if n["id"] not in (edge["from"], edge["to"])
    ]
    midpoint = """
    (id) => {
      const p = document.querySelector(`g.edge[data-id="${id}"] path`);
      const pt = p.getPointAtLength(p.getTotalLength() / 2), m = p.getScreenCTM();
      return [m.a * pt.x + m.c * pt.y + m.e, m.b * pt.x + m.d * pt.y + m.f];
    }
    """
    for victim in others[:3]:
        d_before = page.get_attribute(f'g.edge[data-id="{edge["id"]}"] path', "d")
        x, y = page.evaluate(midpoint, edge["id"])
        drag_to(page, victim, x, y)  # the box lands right on the arrow
        now = measure(page)
        assert now["through"] == [] and now["overlaps"] == [], (victim, now)
        reset_view(page)
        assert (
            page.get_attribute(f'g.edge[data-id="{edge["id"]}"] path', "d") == d_before
        )


@pytest.mark.parametrize("dtype", ARCH)
def test_many_drags_never_cause_a_collision(open_page, dtype: str) -> None:
    page, _ = open_page(f"{dtype}.html")
    ids = [r["id"] for r in measure(page)["rects"]]
    moves = [(-160, 120), (140, -90), (60, 200), (-220, -60), (90, 90), (-40, -180)]
    for index, (dx, dy) in enumerate(moves):
        victim = ids[(index * 3 + 1) % len(ids)]
        gx, gy = centre(page, f'g.node[data-id="{victim}"] rect.card')
        drag_to(page, victim, min(max(gx + dx, 80), 1200), min(max(gy + dy, 90), 640))
        now = measure(page)
        assert now["overlaps"] == [], (index, victim, now["overlaps"])
        assert now["through"] == [], (index, victim, now["through"])
        page.click("#fit")  # keep every box reachable for the next drag
        page.wait_for_timeout(450)


@pytest.mark.parametrize("dtype", ARCH)
def test_dragged_boxes_snap_to_the_routing_grid(open_page, dtype: str) -> None:
    page, _ = open_page(f"{dtype}.html")
    victim = measure(page)["rects"][-1]["id"]
    drag(page, f'g.node[data-id="{victim}"] rect.card', -133, 77)
    x, y = node_xy(page, victim)
    cell = spec_of(page.content())["consts"]["gridCell"]
    assert x % cell == 0 and y % cell == 0


def test_groups_follow_their_members(open_page) -> None:
    page, _ = open_page("d3_architecture.html")
    spec = spec_of(page.content())
    member_of = {n["id"]: n["group"] for n in spec["nodes"]}
    parent = {g["id"]: g["parent"] for g in spec["groups"]}

    def chain(gid):
        while gid:
            yield gid
            gid = parent[gid]

    drag(page, 'g.node[data-id="mail"] rect.card', -200, 260)
    now = measure(page)
    rects = {r["id"]: r for r in now["rects"]}
    groups = {g["id"]: g for g in now["groups"]}
    for node_id, gid in member_of.items():
        for ancestor in chain(gid):
            g, r = groups[ancestor], rects[node_id]
            assert g["x"] <= r["x"] and g["y"] <= r["y"]
            assert (
                r["x"] + r["w"] <= g["x"] + g["w"]
                and r["y"] + r["h"] <= g["y"] + g["h"]
            ), (node_id, ancestor)


def test_hovering_a_box_highlights_its_arrows_and_shows_a_tooltip(open_page) -> None:
    page, _ = open_page("d3_architecture.html")
    x, y = centre(page, 'g.node[data-id="orders"] rect.card')
    page.mouse.move(x, y)
    page.mouse.move(x + 2, y + 2)
    page.wait_for_timeout(200)
    assert page.locator("svg.hl").count() == 1
    lit = page.locator("g.edge.on")
    assert lit.count() == 3  # api->orders, orders->db and orders->queue
    assert page.locator("g.node.on").count() >= 3
    assert (
        "Orders" in page.inner_text("#tip")
        and page.get_attribute("#tip", "class") == "show"
    )
    page.mouse.move(5, 300)
    page.wait_for_timeout(150)
    assert page.locator("svg.hl").count() == 0 and page.locator(".on").count() == 0


def test_reset_puts_the_diagram_back(open_page) -> None:
    page, _ = open_page("d3_architecture.html")
    start = {r["id"]: (r["x"], r["y"]) for r in measure(page)["rects"]}
    drag(page, 'g.node[data-id="db"] rect.card', 150, 150)
    page.mouse.wheel(0, -300)
    page.click("#reset")
    page.wait_for_timeout(500)
    assert {r["id"]: (r["x"], r["y"]) for r in measure(page)["rects"]} == start
    assert viewport_transform(page) == (0.0, 0.0, 1.0)


def test_force_nodes_pin_when_dragged_and_release_on_double_click(open_page) -> None:
    page, _ = open_page("d3_force.html")
    node = page.locator("g.node").nth(3)
    before = float(node.locator("circle.f-node").get_attribute("cx"))
    drag(page, "g.node:nth-of-type(4) circle.f-node", 140, 80)
    assert "pinned" in node.get_attribute("class")
    assert float(node.locator("circle.f-node").get_attribute("cx")) != pytest.approx(
        before, abs=5
    )
    pinned_at = float(node.locator("circle.f-node").get_attribute("cx"))
    page.wait_for_timeout(800)  # the simulation keeps running, a pinned node stays put
    assert float(node.locator("circle.f-node").get_attribute("cx")) == pytest.approx(
        pinned_at, abs=0.5
    )
    node.dblclick()
    page.wait_for_timeout(200)
    assert "pinned" not in node.get_attribute("class")


def test_force_pause_and_resume(open_page) -> None:
    page, _ = open_page("d3_force.html")
    page.click("#pause")
    assert page.inner_text("#pause") == "Resume"
    page.click("#pause")
    assert page.inner_text("#pause") == "Pause"


@pytest.mark.parametrize("dtype", ALL)
def test_save_svg_downloads_a_standalone_picture(
    open_page, tmp_path, dtype: str
) -> None:
    page, _ = open_page(f"{dtype}.html")
    page.mouse.wheel(0, -300)  # zoomed in: the export must not carry the zoom
    with page.expect_download() as info:
        choose_export(page, "#save")
    target = tmp_path / info.value.suggested_filename
    info.value.save_as(target)
    assert target.suffix == ".svg"
    root = ET.fromstring(target.read_text(encoding="utf-8"))
    assert root.tag.endswith("svg")
    text = target.read_text(encoding="utf-8")
    assert "style=" not in text
    assert not re.search(
        r'class="viewport"[^>]*transform=', text
    )  # no zoom carried over
    assert text.count('class="node cat-') == (8 if dtype == "d3_force" else 7)


@pytest.mark.parametrize("dtype", ARCH)
def test_save_html_keeps_the_current_layout(open_page, tmp_path, dtype: str) -> None:
    page, _ = open_page(f"{dtype}.html")
    victim = measure(page)["rects"][-1]["id"]
    drag(page, f'g.node[data-id="{victim}"] rect.card', -180, 140)
    moved = node_xy(page, victim)
    live = measure(page)
    page.mouse.wheel(0, -400)  # the export is always opened unzoomed
    with page.expect_download() as info:
        choose_export(page, "#html")
    exported = tmp_path / info.value.suggested_filename
    info.value.save_as(exported)
    text = exported.read_text(encoding="utf-8")

    assert exported.suffix == ".html" and text.startswith("<!doctype html>")
    assert "Content-Security-Policy" in text and "Save HTML" in text
    markup = text.split("<script", 1)[0]
    assert not re.search(r"<[a-zA-Z]+\s[^>]*\bstyle=", markup)  # a CSP would drop them
    assert "data-ready" not in markup and 'class="viewport" transform' not in markup
    saved = {n["id"]: (n["x"], n["y"]) for n in spec_of(text)["nodes"]}
    assert saved[victim] == moved  # the data block holds where the box is now

    # opened again, the page is exactly as it was left, and still behaves
    again, problems = open_page(exported)
    assert problems == []
    assert node_xy(again, victim) == moved
    reopened = measure(again)
    assert reopened["rects"] == live["rects"] and reopened["groups"] == live["groups"]
    assert reopened["overlaps"] == [] and reopened["through"] == []
    drag(again, f'g.node[data-id="{victim}"] rect.card', 100, 60)
    assert node_xy(again, victim) != moved
    after = measure(again)
    assert after["overlaps"] == [] and after["through"] == []


@pytest.mark.parametrize("dtype", ARCH)
def test_exports_grow_to_include_boxes_dragged_off_the_canvas(
    open_page, tmp_path, dtype: str
) -> None:
    page, _ = open_page(f"{dtype}.html")
    svg = SVG_SELECTOR[dtype]
    original = [float(v) for v in page.get_attribute(svg, "viewBox").split()]
    victim = measure(page)["rects"][-1]["id"]
    page.mouse.move(640, 360)
    page.mouse.wheel(0, 900)  # zoom out so the mouse can reach past the drawn area
    page.wait_for_timeout(400)
    x, y = centre(page, f'g.node[data-id="{victim}"] rect.card')
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(1250, 700, steps=18)
    page.mouse.up()
    page.wait_for_timeout(300)
    vx, vy = node_xy(page, victim)
    assert (
        vx + 200 > original[0] + original[2] or vy + 60 > original[1] + original[3]
    )  # past the edge

    def covers(box: list[float]) -> bool:
        return (
            box[0] <= vx
            and box[1] <= vy
            and vx + 160 <= box[0] + box[2]
            and vy + 60 <= box[1] + box[3]
        )

    with page.expect_download() as info:
        choose_export(page, "#save")
    svg_file = tmp_path / info.value.suggested_filename
    info.value.save_as(svg_file)
    root = ET.fromstring(svg_file.read_text(encoding="utf-8"))
    box = [float(v) for v in root.attrib["viewBox"].split()]
    assert (
        covers(box)
        and [float(root.attrib["width"]), float(root.attrib["height"])] == box[2:]
    )

    with page.expect_download() as info:
        choose_export(page, "#html")
    html_file = tmp_path / info.value.suggested_filename
    info.value.save_as(html_file)
    reopened, problems = open_page(html_file)
    assert problems == [] and covers(
        [float(v) for v in reopened.get_attribute(svg, "viewBox").split()]
    )
    shown = reopened.locator(f'g.node[data-id="{victim}"] rect.card').bounding_box()
    assert 0 <= shown["x"] and shown["x"] + shown["width"] <= 1280
    assert (
        0 <= shown["y"] and shown["y"] + shown["height"] <= 720
    )  # on screen, not lost


def test_save_html_keeps_pinned_force_nodes_pinned(open_page, tmp_path) -> None:
    page, _ = open_page("d3_force.html")
    drag(page, "g.node:nth-of-type(4) circle.f-node", 140, 80)
    pinned_id = page.locator("g.node.pinned").first.get_attribute("data-id")
    with page.expect_download() as info:
        choose_export(page, "#html")
    exported = tmp_path / info.value.suggested_filename
    info.value.save_as(exported)
    spec = spec_of(exported.read_text(encoding="utf-8"))
    assert [n["id"] for n in spec["nodes"] if n.get("fixed")] == [pinned_id]

    again, problems = open_page(exported)
    assert problems == []
    assert again.locator("g.node.pinned").count() == 1
    assert again.locator("g.node.pinned").first.get_attribute("data-id") == pinned_id
    here = float(
        page.locator(f'g.node[data-id="{pinned_id}"] circle.f-node').get_attribute("cx")
    )
    there = float(
        again.locator(f'g.node[data-id="{pinned_id}"] circle.f-node').get_attribute(
            "cx"
        )
    )
    again.wait_for_timeout(600)
    assert float(
        again.locator(f'g.node[data-id="{pinned_id}"] circle.f-node').get_attribute(
            "cx"
        )
    ) == pytest.approx(there, abs=0.5)
    assert there == pytest.approx(here, abs=1)


def test_the_static_svg_matches_the_page_before_it_is_touched(
    open_page, mcp_report
) -> None:
    """The ``svg`` output and the page's own drawing are the same picture."""
    svg = (Path(mcp_report["pages_dir"]) / "d3_architecture.svg").read_text(
        encoding="utf-8"
    )
    page, _ = open_page("d3_architecture.html")
    page_nodes = {r["id"]: (r["x"], r["y"]) for r in measure(page)["rects"]}
    static = {
        n.attrib["data-id"]: tuple(
            float(v)
            for v in grab(
                r"translate\(([-\d.]+) ([-\d.]+)\)", n.attrib["transform"]
            ).groups()
        )
        for n in ET.fromstring(svg).iter("{http://www.w3.org/2000/svg}g")
        if "node" in n.attrib.get("class", "").split()
    }
    assert static == page_nodes


# --------------------------------------------------------- the look and its features
def scheme_of(page) -> tuple[str, str]:
    """(class of the page, class of the diagram)."""
    return (
        page.evaluate("document.documentElement.className"),
        page.evaluate("document.querySelector('svg.d3d').getAttribute('class')"),
    )


@pytest.mark.parametrize("dtype", ALL)
def test_the_theme_button_switches_the_page_and_the_diagram(
    open_page, dtype: str
) -> None:
    page, problems = open_page(f"{dtype}.html")
    light_panel = page.evaluate(
        "getComputedStyle(document.querySelector('rect.bg')).fill"
    )
    assert scheme_of(page)[0] == "light"
    page.click("#theme")
    page_class, svg_class = scheme_of(page)
    assert page_class == "dark" and "dark" in svg_class and "light" not in svg_class
    dark_panel = page.evaluate(
        "getComputedStyle(document.querySelector('rect.bg')).fill"
    )
    assert dark_panel != light_panel
    assert (
        page.evaluate("getComputedStyle(document.body).backgroundColor")
        != "rgb(244, 245, 247)"
    )
    page.click("#theme")
    assert scheme_of(page)[0] == "light"
    assert problems == []


def test_auto_follows_the_system_and_the_button_overrides_it(browser, tmp_path) -> None:
    from uml_mcp_plugin_d3 import D3Renderer
    from uml_mcp_plugin_d3.samples import SAMPLES

    renderer = D3Renderer()
    renderer.configure({"d3_source": "inline"})
    code = json.dumps({**json.loads(SAMPLES["d3_architecture"][0]), "theme": "auto"})
    target = tmp_path / "auto.html"
    target.write_bytes(renderer.render("d3_architecture", code, "html").content)
    for system in ("light", "dark"):
        context = browser.new_context(
            color_scheme=system, viewport={"width": 1280, "height": 720}
        )
        page = context.new_page()
        page.goto(target.as_uri())
        page.wait_for_selector("body[data-ready]")
        background = page.evaluate("getComputedStyle(document.body).backgroundColor")
        assert (background == "rgb(2, 6, 23)") == (system == "dark"), (
            system,
            background,
        )
        page.click("#theme")  # flips whatever the system chose
        flipped = page.evaluate("getComputedStyle(document.body).backgroundColor")
        assert flipped != background
        context.close()


@pytest.mark.parametrize("dtype", ARCH)
def test_flow_animates_the_arrows_and_stops_for_reduced_motion(
    browser, mcp_report, dtype: str
) -> None:
    page_file = Path(mcp_report["pages_dir"]) / f"{dtype}.html"
    for reduced, expected in (("no-preference", "d3flow"), ("reduce", "none")):
        context = browser.new_context(
            reduced_motion=reduced, viewport={"width": 1280, "height": 720}
        )
        page = context.new_page()
        page.goto(page_file.as_uri())
        page.wait_for_selector("body[data-ready]")
        assert page.get_attribute("#flow", "aria-pressed") == "false"
        assert (
            page.evaluate(
                "getComputedStyle(document.querySelector('.edge-line')).animationName"
            )
            == "none"
        )
        page.click("#flow")
        assert page.get_attribute("#flow", "aria-pressed") == "true"
        assert "flow" in page.get_attribute("svg.d3d", "class").split()
        assert (
            page.evaluate(
                "getComputedStyle(document.querySelector('.edge-line')).animationName"
            )
            == expected
        )
        context.close()


def png_size(data: bytes) -> tuple[int, int]:
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


@pytest.mark.parametrize("dtype", ALL)
def test_save_png_downloads_the_picture_at_twice_the_size(
    open_page, tmp_path, dtype: str
) -> None:
    page, _ = open_page(f"{dtype}.html")
    with page.expect_download() as info:
        choose_export(page, "#png")
    png = tmp_path / info.value.suggested_filename
    info.value.save_as(png)
    data = png.read_bytes()
    width, height = png_size(data)
    with page.expect_download() as info:
        choose_export(page, "#save")
    svg = tmp_path / info.value.suggested_filename
    info.value.save_as(svg)
    root = ET.fromstring(svg.read_text(encoding="utf-8"))
    assert (width, height) == (
        round(float(root.attrib["width"]) * 2),
        round(float(root.attrib["height"]) * 2),
    )
    assert png.suffix == ".png" and len(data) > 4000  # not a blank canvas


def test_the_png_shows_the_diagram_not_a_blank_canvas(
    open_page, browser, tmp_path
) -> None:
    page, _ = open_page("d3_architecture.html")
    with page.expect_download() as info:
        choose_export(page, "#png")
    png = tmp_path / "out.png"
    info.value.save_as(png)
    probe = browser.new_page()
    probe.goto(png.as_uri())
    colours = probe.evaluate(
        """async () => {
          const img = document.querySelector('img'); await img.decode();
          const c = document.createElement('canvas'); c.width = img.naturalWidth; c.height = img.naturalHeight;
          const x = c.getContext('2d'); x.drawImage(img, 0, 0);
          const d = x.getImageData(0, 0, c.width, c.height).data; const seen = new Set();
          for (let i = 0; i < d.length; i += 4 * 17) seen.add((d[i] >> 4) + ',' + (d[i + 1] >> 4) + ',' + (d[i + 2] >> 4));
          return seen.size;
        }"""
    )
    assert colours > 8  # several distinct card, border and text colours
    probe.close()


@pytest.mark.parametrize("dtype", ALL)
def test_the_zoom_level_and_the_dotted_canvas_follow_the_zoom(
    open_page, dtype: str
) -> None:
    page, _ = open_page(f"{dtype}.html")
    assert page.inner_text("#zlevel") == "100%"
    box = page.locator(SVG_SELECTOR[dtype]).bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.wheel(0, -400)
    page.wait_for_timeout(300)
    _x, _y, k = viewport_transform(page)
    assert page.inner_text("#zlevel") == f"{round(k * 100)}%" and k > 1
    transform = page.get_attribute("g.viewport", "transform")
    assert (
        page.get_attribute("pattern#dots", "patternTransform") == transform
    )  # the dots move with it
    covers = page.evaluate(
        "(() => { const r = document.querySelector('rect.dotfill').getBBox(); const v = document.querySelector('svg.d3d').viewBox.baseVal;"
        " return r.width > v.width * 3 && r.height > v.height * 3; })()"
    )
    assert covers  # the canvas is larger than the drawing, so the dots fill the view


@pytest.mark.parametrize("dtype", ALL)
def test_the_legend_counts_match_what_is_drawn(open_page, dtype: str) -> None:
    page, _ = open_page(f"{dtype}.html")
    items = page.evaluate(
        "[...document.querySelectorAll('g.legend g')].map(g => [g.querySelector('.t-legend').textContent, +g.querySelector('.t-count').textContent])"
    )
    assert (
        items and sum(count for _name, count in items) == page.locator("g.node").count()
    )


def test_straight_arrows_are_drawn_without_corners(open_page) -> None:
    page, _ = open_page("d3_architecture.html")
    for pair in ("users->cdn", "cdn->api", "api->orders", "orders->db"):
        source, target = pair.split("->")
        d = page.get_attribute(
            f'g.edge[data-from="{source}"][data-to="{target}"] path.edge-line', "d"
        )
        assert "Q" not in d and d.count("L") == 1, (pair, d)


def test_labels_keep_clear_of_the_boxes_while_dragging(open_page) -> None:
    page, _ = open_page("d3_architecture.html")
    for node, dx, dy in (("orders", 0, 120), ("db", 60, -140), ("cdn", 0, 100)):
        gx, gy = centre(page, f'g.node[data-id="{node}"] rect.card')
        drag_to(page, node, min(max(gx + dx, 80), 1200), min(max(gy + dy, 120), 640))
        overlaps = page.evaluate(
            """() => {
              const boxes = [...document.querySelectorAll('g.node rect.card')].map(r => r.getBoundingClientRect());
              return [...document.querySelectorAll('g.edge-label text')].filter(t => {
                const b = t.getBoundingClientRect();
                return boxes.some(r => b.left < r.right && r.left < b.right && b.top < r.bottom && r.top < b.bottom);
              }).map(t => t.textContent);
            }"""
        )
        assert overlaps == [], (node, overlaps)
        page.click("#fit")
        page.wait_for_timeout(400)


def test_logos_and_software_tiles_load_under_the_policy(browser, tmp_path) -> None:
    from uml_mcp_plugin_d3 import D3Renderer

    code = json.dumps(
        {
            "nodes": [
                {"id": "mine", "label": "Mine", "logo": PNG_1PX},
                {"id": "db", "service": "postgres"},
                {"id": "q", "service": "aws:sqs"},
            ],
            "links": [{"from": "mine", "to": "db"}, {"from": "db", "to": "q"}],
        }
    )
    renderer = D3Renderer()
    renderer.configure({"d3_source": "inline"})
    target = tmp_path / "logos.html"
    target.write_bytes(renderer.render("d3_architecture", code, "html").content)
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    page = context.new_page()
    problems: list[str] = []
    page.on(
        "console",
        lambda m: problems.append(m.text) if m.type in ("error", "warning") else None,
    )
    page.goto(target.as_uri())
    page.wait_for_selector("body[data-ready]")
    page.wait_for_function(
        "document.querySelector('image.logo').getBoundingClientRect().width > 0"
    )
    assert page.locator("image.logo").count() == 1
    assert page.locator("text.t-mono").text_content() == "Pg"
    assert problems == []  # the data: image is allowed, nothing else is requested
    context.close()
