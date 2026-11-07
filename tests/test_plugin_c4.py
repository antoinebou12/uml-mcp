"""The C4 model plugin: validation, lifted relations, layout, SVG/HTML safety and the drill-down page."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from html import unescape
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _name in ("c4", "d3"):
    _src = str(ROOT / "examples" / "plugins" / f"uml-mcp-plugin-{_name}" / "src")
    if _src not in sys.path:
        sys.path.insert(0, _src)

from uml_mcp_plugin_c4 import C4Renderer
from uml_mcp_plugin_c4.html import docs_link, page_data
from uml_mcp_plugin_c4.model import SpecError, parse
from uml_mcp_plugin_c4.samples import BANKING, EXAMPLE, TEMPLATE
from uml_mcp_plugin_c4.views import all_views, best_direction, build, wrap

SVG = "{http://www.w3.org/2000/svg}"


def found(pattern: str, text: str) -> str:
    match = re.search(pattern, text, re.DOTALL)
    assert match, pattern
    return match[1]


def source(**changes) -> str:
    return json.dumps({**copy.deepcopy(BANKING), **changes})


def render(code: str, fmt: str) -> str:
    return C4Renderer().render("c4_model", code, fmt).content.decode("utf-8")


# ---------------------------------------------------------------- registration


def test_registers_one_sandboxed_type():
    renderer = C4Renderer()
    assert set(renderer.diagram_types) == {"c4_model"}
    spec = renderer.diagram_types["c4_model"]
    assert spec.formats == ("html", "svg")
    assert spec.security_profile == "sandboxed"
    assert "drilldown" in spec.interaction_features
    assert spec.example and spec.template
    assert not renderer.validate("c4_model", spec.example)
    assert not renderer.validate("c4_model", spec.template)


def test_is_a_bundled_renderer_entry_point():
    from importlib.metadata import entry_points

    from mcp_core.plugins.loader import BUNDLED_RENDERERS

    assert "c4" in BUNDLED_RENDERERS
    names = {ep.name: ep.value for ep in entry_points(group="uml_mcp.renderers")}
    assert names.get("c4") == "uml_mcp_plugin_c4:C4Renderer"


def test_unknown_type_and_format_are_refused():
    renderer = C4Renderer()
    assert renderer.validate("c4plantuml", EXAMPLE)
    with pytest.raises(ValueError, match="html or svg"):
        renderer.render("c4_model", EXAMPLE, "png")
    with pytest.raises(ValueError, match="unknown c4 type"):
        renderer.render("c4plantuml", EXAMPLE, "svg")
    with pytest.raises(ValueError, match="invalid c4_model source"):
        renderer.render("c4_model", "{}", "svg")


def test_max_elements_setting():
    renderer = C4Renderer()
    renderer.configure({"max_elements": 5})
    assert "too many elements" in renderer.validate("c4_model", EXAMPLE)[0]
    for bad in (0, 301, "5", True):
        with pytest.raises(ValueError):
            renderer.configure({"max_elements": bad})


# ---------------------------------------------------------------- validation


@pytest.mark.parametrize(
    ("code", "message"),
    [
        ("not json", "source must be JSON"),
        ("[]", "must be a JSON object"),
        ("{}", "the model is empty"),
        (json.dumps({"people": [{"id": "a b"}]}), "short identifier"),
        (
            json.dumps({"people": [{"id": "a"}, {"id": "a"}]}),
            "already used by a person",
        ),
        (json.dumps({"people": [{"id": "a", "role": "x"}]}), "unknown field(s) role"),
        (
            json.dumps({"people": [{"id": "a"}], "colour": 1}),
            "unknown top-level field(s) colour",
        ),
        (json.dumps({"people": "a"}), "people must be a list"),
        (json.dumps({"people": [{"id": "a", "external": "yes"}]}), "true or false"),
        (json.dumps({"people": [{"id": "a", "docs": "http://x"}]}), "https:// URL"),
        (source(theme="neon"), "theme must be one of"),
        (source(direction="RL"), "direction must be one of"),
        (
            source(relations=[{"from": "customer", "to": "paymnts"}]),
            "relations[0].to 'paymnts' is not a known element; known ids: customer, staff",
        ),
        (source(relations=[{"from": "api"}]), "relations[0].to is required"),
        (source(relations=[{"from": "api", "to": "api"}]), "connects 'api' to itself"),
        (
            source(relations=[{"from": "signin", "to": "banking"}]),
            "connects 'signin' to 'banking', which contains it",
        ),
        (source(view={"level": "deployment"}), "view.level must be one of"),
        (source(view={"level": "container"}), "view.focus is required"),
        (
            source(view={"level": "container", "focus": "api"}),
            "the container level needs a system id",
        ),
        (
            source(view={"level": "component", "focus": "banking"}),
            "the component level needs a container id",
        ),
        (source(view={"level": "component", "focus": "db"}), "'db' has no components"),
        (
            source(view={"level": "container", "focus": "email"}),
            "'email' has no containers",
        ),
        (
            source(view={"level": "context", "focus": "api"}),
            "the context level focuses a person",
        ),
        (
            source(view={"level": "context", "focus": "nope"}),
            "view.focus 'nope' is not a known element",
        ),
        (source(view="container"), "view must be an object"),
    ],
)
def test_invalid_sources_have_readable_messages(code, message):
    errors = C4Renderer().validate("c4_model", code)
    assert errors and any(message in e for e in errors), errors


def test_bad_container_kind_names_the_field():
    data = copy.deepcopy(BANKING)
    data["systems"][0]["containers"][1]["kind"] = "mobile"
    (error,) = C4Renderer().validate("c4_model", json.dumps(data))
    assert error.startswith("systems[0].containers[1].kind must be one of app, web, db")


def test_every_problem_is_reported_at_once():
    code = json.dumps(
        {
            "people": [{"id": "a"}, {"id": "a"}],
            "relations": [{"from": "a", "to": "b"}, {"from": "a", "to": "a"}],
            "theme": "x",
        }
    )
    with pytest.raises(SpecError) as info:
        parse(code)
    assert len(info.value.problems) == 4


def test_fenced_json_and_defaults():
    model = parse("```json\n" + TEMPLATE + "\n```")
    assert model.level == "context" and model.focus is None
    assert model.theme == "dark" and model.direction == "auto"
    assert model.elements["db"].kind == "db" and model.elements["api"].kind == "app"
    assert model.ancestors("db") == ["db", "app"]


def test_docs_page_example_and_messages_are_real():
    text = (ROOT / "docs/plugins/c4.md").read_text(encoding="utf-8")
    example = found(r"```json\n(.*?)\n```", text)
    assert not C4Renderer().validate("c4_model", example)
    assert parse(example).level == "container"
    # the sample messages are the ones the validation tests above assert
    for stem in (
        "is not a known element; known ids:",
        "is a container; the container level needs a system id",
        "which contains it; relate elements to their siblings or to other elements instead",
    ):
        assert stem in text


# ---------------------------------------------------------------- views and lifting


def edges_of(view):
    return {(e.source, e.target): e for e in view.edges}


def test_context_view_lifts_everything_to_systems():
    model = parse(EXAMPLE)
    view = build(model, "context", None)
    assert {n.id for n in view.nodes} == {
        "customer",
        "staff",
        "banking",
        "mainframe",
        "email",
    }
    edges = edges_of(view)
    # web, spa: two customer relations merged onto the banking system
    assert edges[("customer", "banking")].count == 2
    assert (
        edges[("customer", "banking")].label == "Visits; Views balances, makes payments"
    )
    assert edges[("banking", "mainframe")].technology == "XML/HTTPS"
    assert ("banking", "banking") not in edges  # internal relations disappear
    assert view.boundary is None


def test_container_view_lifts_components_to_their_container():
    model = parse(EXAMPLE)
    view = build(model, "container", "banking")
    assert view.boundary and view.boundary.id == "banking"
    inside = {"web", "spa", "api", "events", "mailer", "db"}
    assert inside <= {n.id for n in view.nodes}
    assert "staff" not in {n.id for n in view.nodes}  # does not talk to the containers
    edges = edges_of(view)
    spa_api = edges[("spa", "api")]
    assert spa_api.count == 2 and spa_api.label == "Signs in; Reads accounts"
    assert spa_api.technology == "JSON/HTTPS"
    assert edges[("api", "db")].label == "Reads and writes"
    assert edges[("api", "events")].is_async
    assert not edges[("api", "db")].is_async


def test_component_view_shows_neighbours_and_drill_targets():
    model = parse(EXAMPLE)
    view = build(model, "component", "api")
    ids = {n.id for n in view.nodes}
    assert {"signin", "accounts", "security", "facade", "notifier"} <= ids
    assert {"spa", "db", "events", "mainframe"} <= ids
    assert "customer" not in ids and "web" not in ids
    assert ("spa", "signin") in edges_of(view)
    assert [c[0] for c in view.crumbs] == [
        "context",
        "container:banking",
        "component:api",
    ]
    assert view.title == "Component view: API Application"


def test_relation_to_the_open_element_ends_on_its_boundary():
    data = copy.deepcopy(BANKING)
    data["relations"].append({"from": "staff", "to": "banking", "label": "Administers"})
    view = build(parse(json.dumps(data)), "container", "banking")
    edge = edges_of(view)[("staff", "banking")]
    assert edge.label == "Administers"
    assert "staff" in {n.id for n in view.nodes}


def test_all_views_and_drill_targets():
    model = parse(EXAMPLE)
    views = all_views(model)
    assert set(views) == {"context", "container:banking", "component:api"}
    drill = {n.id: n.drill for n in views["context"].nodes}
    assert drill["banking"] == "container:banking" and drill["mainframe"] is None
    assert {n.id: n.drill for n in views["container:banking"].nodes}[
        "api"
    ] == "component:api"


@pytest.mark.parametrize("direction", ["TB", "LR"])
def test_layouts_never_overlap_boxes_and_fit_the_canvas(direction):
    model = parse(EXAMPLE)
    for view in all_views(model, direction).values():
        rects = [(n.x, n.y, n.w, n.h) for n in view.nodes]
        for i, a in enumerate(rects):
            assert a[0] >= 0 and a[1] >= 0
            assert a[0] + a[2] <= view.width and a[1] + a[3] <= view.height
            for b in rects[i + 1 :]:
                apart = (
                    a[0] + a[2] <= b[0]
                    or b[0] + b[2] <= a[0]
                    or a[1] + a[3] <= b[1]
                    or b[1] + b[3] <= a[1]
                )
                assert apart, (view.key, a, b)
        if view.boundary:
            b = view.boundary
            for n in view.nodes:
                assert view.focus
                inside = n.id in model.elements[view.focus].children
                within = (
                    b.x < n.x
                    and n.x + n.w < b.x + b.w
                    and b.y < n.y
                    and n.y + n.h < b.y + b.h
                )
                assert inside == within, (view.key, n.id)
        for e in view.edges:
            assert 0 <= e.label_x <= view.width and 0 <= e.label_y <= view.height


def test_lr_flows_left_to_right_and_auto_picks_a_landscape_shape():
    model = parse(EXAMPLE)
    lr = build(model, "context", None, "LR")
    x = {n.id: n.x for n in lr.nodes}
    assert x["customer"] < x["banking"] < x["mainframe"]
    tb = build(model, "context", None, "TB")
    y = {n.id: n.y for n in tb.nodes}
    assert y["customer"] < y["banking"] < y["mainframe"]
    assert best_direction(model, "context", None) in ("TB", "LR")
    model.direction = "LR"
    assert best_direction(model, "container", "banking") == "LR"


def test_wrap_ellipsizes_and_splits_long_words():
    assert wrap("", 12, 100, 3) == []
    lines = wrap("word " * 40, 12, 100, 3)
    assert len(lines) == 3 and lines[-1].endswith("…")
    assert all(len(line) <= 16 for line in wrap("x" * 50, 12, 100, 9))


# ---------------------------------------------------------------- SVG


@pytest.mark.parametrize(
    ("view", "title"),
    [
        (None, "System context: Internet banking system"),
        (
            {"level": "container", "focus": "banking"},
            "Container view: Internet Banking System",
        ),
        ({"level": "component", "focus": "api"}, "Component view: API Application"),
    ],
)
def test_static_svg_draws_the_starting_view_in_c4_notation(view, title):
    code = source(view=view) if view else EXAMPLE
    svg = render(code, "svg")
    root = ET.fromstring(svg)
    assert root.tag == SVG + "svg" and "<script" not in svg
    assert title in svg
    assert "var(--" not in svg  # rasterizers have no CSS variables
    assert root.find(f".//{SVG}g[@class='legend']") is not None
    text = " ".join(t.text or "" for t in root.iter(SVG + "text"))
    if view is None:
        assert "[Person]" in text and "[External Software System]" in text
        mainframe = root.find(f".//{SVG}g[@data-id='mainframe']")
        assert mainframe is not None
        assert mainframe.get("class") == "el system ext"
    if view and view["level"] == "container":
        assert "[Container: PostgreSQL]" in text and "Internet Banking System" in text
        assert root.find(f".//{SVG}g[@class='boundary']") is not None
        assert "[JSON/HTTPS]" in text  # technology in brackets on the merged line
        assert "stroke-dasharray:7 5" in svg  # async relation style
    # the static picture has no page affordances
    assert "tabindex" not in svg and 'class="badge"' not in svg


def test_database_is_a_cylinder_and_queue_a_pipe():
    svg = render(
        source(view={"level": "container", "focus": "banking"}, direction="TB"), "svg"
    )
    root = ET.fromstring(svg)
    db = root.find(f".//{SVG}g[@data-id='db']")
    queue = root.find(f".//{SVG}g[@data-id='events']")
    assert db is not None and queue is not None
    outline = db.find(SVG + "path")
    assert outline is not None and " A" in str(outline.get("d"))  # elliptical arcs
    assert len(db.findall(SVG + "path")) == 2 and len(queue.findall(SVG + "path")) == 2


def test_light_theme_and_svg_rasterizes():
    from mcp_core.core.svg_raster import svg_to_png

    svg = render(source(theme="light"), "svg")
    assert 'class="c4 light"' in svg and "#ffffff" in svg
    png = svg_to_png(svg.encode("utf-8"))
    assert png and png[:8] == b"\x89PNG\r\n\x1a\n"


def test_text_is_escaped_everywhere():
    data = copy.deepcopy(BANKING)
    data["title"] = "<script>alert(1)</script>"
    data["people"][0]["name"] = "</script><img src=x onerror=alert(1)>"
    data["relations"][0]["label"] = "a & <b>"
    code = json.dumps(data)
    svg = render(code, "svg")
    ET.fromstring(svg)
    assert "<img" not in svg and "<script" not in svg
    html = render(code, "html")
    assert "<img" not in html and "<script>alert" not in html
    data_block = found(r'id="model">(.*?)</script>', html)
    assert "<" not in data_block and json.loads(data_block)["title"] == data["title"]


# ---------------------------------------------------------------- HTML


def _sha(text: str) -> str:
    return base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode()


def test_html_csp_allows_exactly_its_own_script_and_style():
    html = render(EXAMPLE, "html")
    csp = unescape(
        found(r'http-equiv="Content-Security-Policy" content="([^"]+)"', html)
    )
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    styles = re.findall(r"<style>(.*?)</style>", html.split("</head>")[0], re.DOTALL)
    assert len(scripts) == 1 and len(styles) == 1
    assert (
        f"'sha256-{_sha(scripts[0])}'" in csp and f"'sha256-{_sha(styles[0])}'" in csp
    )
    assert "default-src 'none'" in csp and "connect-src" not in csp
    assert "fetch(" not in scripts[0] and "XMLHttpRequest" not in scripts[0]
    assert "cdn" not in html.lower()


def test_page_carries_every_view_in_both_flows_and_docs_links():
    html = render(EXAMPLE, "html")
    views = re.findall(
        r'data-dir="(TB|LR)" class="view c4 \w+"[^>]*data-view="([^"]+)"', html
    )
    assert sorted(views) == sorted(
        (d, k)
        for d in ("TB", "LR")
        for k in ("context", "container:banking", "component:api")
    )
    fixed = render(source(direction="TB"), "html")
    assert 'data-dir="LR"' not in fixed
    model = parse(EXAMPLE)
    data = page_data(model, all_views(model))
    assert data["start"] == "context"
    assert data["elements"]["mailer"]["docs"] == "https://docs.aws.amazon.com/lambda/"
    assert data["elements"]["db"]["docs"] == "https://www.postgresql.org/docs/"
    assert data["elements"]["spa"]["docs"] == "https://react.dev/"
    assert data["elements"]["api"]["docs"] is None
    assert data["elements"]["signin"]["home"] == "component:api"
    assert data["elements"]["banking"]["drill"] == "container:banking"


def test_docs_override_and_provider_search():
    model = parse(
        json.dumps(
            {
                "systems": [
                    {
                        "id": "s",
                        "containers": [
                            {"id": "a", "service": "aws:somethingnew"},
                            {
                                "id": "b",
                                "service": "postgres",
                                "docs": "https://example.com/db",
                            },
                            {"id": "c", "service": "unknownthing"},
                        ],
                    }
                ]
            }
        )
    )
    assert str(docs_link(model.elements["a"])).startswith(
        "https://docs.aws.amazon.com/search/"
    )
    assert docs_link(model.elements["b"]) == "https://example.com/db"
    assert docs_link(model.elements["c"]) is None


def test_starting_view_is_the_requested_one():
    html = render(source(view={"level": "component", "focus": "api"}), "html")
    data = json.loads(found(r'id="model">(.*?)</script>', html))
    assert data["start"] == "component:api"
    focused = render(source(view={"level": "context", "focus": "banking"}), "html")
    assert (
        json.loads(found(r'id="model">(.*?)</script>', focused))["select"] == "banking"
    )


# ---------------------------------------------------------------- browser

playwright = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as pw:
        try:
            chromium = pw.chromium.launch()
        except playwright.Error as exc:  # pragma: no cover - no browser installed
            pytest.skip(f"chromium is not available: {exc}")
        yield chromium
        chromium.close()


def open_page(browser, html: str, width: int, height: int):
    page = browser.new_page(viewport={"width": width, "height": height})
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.set_content(html)
    return page, errors


def wait_for(page, expression: str, want, timeout: float = 5.0) -> None:
    """Poll ``expression`` (wait_for_function evaluates strings, which the page's CSP forbids)."""
    import time

    end = time.monotonic() + timeout
    while (got := page.evaluate(expression)) != want:
        assert time.monotonic() < end, f"{expression} is {got!r}, not {want!r}"
        page.wait_for_timeout(50)


def wait_view(page, key: str) -> None:
    wait_for(page, "window.__c4.view", key)


def crumbs(page) -> list[str]:
    return page.locator("#crumbs button").all_inner_texts()


@pytest.mark.parametrize(("width", "height"), [(1200, 800), (560, 430)])
def test_drill_down_and_back_up(browser, width, height, tmp_path):
    page, errors = open_page(browser, render(EXAMPLE, "html"), width, height)
    assert page.evaluate("window.__c4.view") == "context"
    assert crumbs(page) == ["Context"]
    assert page.is_disabled("#up")

    # click a system: its containers
    page.click('svg.view.on .el[data-id="banking"]')
    wait_view(page, "container:banking")
    assert crumbs(page) == ["Context", "Internet Banking System"]
    assert page.locator("svg.view.on").count() >= 1
    page.wait_for_timeout(450)  # the transition ends
    assert page.locator("svg.view.on").count() == 1
    # a component-to-component relation shows as one merged container line
    line = page.locator('svg.view.on .rel[data-from="spa"][data-to="api"]')
    assert line.count() == 1
    assert "Signs in; Reads accounts" in line.text_content()

    # click a container: its components
    page.click('svg.view.on .el[data-id="api"]')
    wait_view(page, "component:api")
    assert crumbs(page) == ["Context", "Internet Banking System", "API Application"]
    page.wait_for_timeout(450)

    # a component opens its detail card; a relation in the card jumps across levels
    page.click('svg.view.on .el[data-id="facade"]')
    card = page.locator("#details")
    assert card.is_visible()
    assert "Mainframe Banking Facade" in card.inner_text()
    assert "→ Mainframe Banking System" in card.inner_text()
    page.screenshot(path=str(tmp_path / f"component-{width}.png"))
    # the mainframe is drawn here too, so the link selects it in place
    page.locator("#details .links button", has_text="Mainframe Banking System").click()
    assert page.evaluate("window.__c4.view") == "component:api"
    assert page.evaluate("window.__c4.selected") == "mainframe"
    assert "external" in page.inner_text("#details .kind").lower()
    # back office staff only appear in the context view: the link switches level
    page.locator("#details .links button", has_text="Back Office Staff").click()
    wait_view(page, "context")
    assert page.evaluate("window.__c4.selected") == "staff"
    assert page.inner_text("#details h2") == "Back Office Staff"

    # breadcrumbs and Esc go back up
    page.evaluate("window.__c4.go('component:api')")
    page.wait_for_timeout(450)
    page.locator("#crumbs button", has_text="Internet Banking System").click()
    wait_view(page, "container:banking")
    assert page.evaluate("window.__c4.selected") == "api"  # where we came from
    page.keyboard.press("Escape")
    wait_view(page, "context")
    assert not errors
    page.close()


def test_detail_card_docs_and_drill_button(browser):
    page, errors = open_page(browser, render(EXAMPLE, "html"), 1200, 800)
    page.evaluate("window.open = (url) => { window.__opened = url; return null; }")
    page.click('svg.view.on .el[data-id="banking"]', modifiers=["Shift"])
    assert page.evaluate("window.__c4.view") == "context"
    assert "Open containers" in page.inner_text("#details")
    page.locator("#details .primary").click()
    wait_view(page, "container:banking")
    page.wait_for_timeout(450)
    page.click('svg.view.on .el[data-id="mailer"]')
    assert "[Container: AWS Lambda]" in page.inner_text("#details")
    page.click("#d-docs")
    assert page.evaluate("window.__opened") == "https://docs.aws.amazon.com/lambda/"
    # a line explains the relations behind it
    page.locator(
        'svg.view.on .rel[data-from="spa"][data-to="api"] .line'
    ).dispatch_event("click")
    assert "2 merged" in page.inner_text("#details .kind").lower()
    # the boundary opens the card of the system on screen
    page.locator("svg.view.on .boundary .bname").click()
    assert page.inner_text("#details h2") == "Internet Banking System"
    assert not errors
    page.close()


def test_docs_links_go_through_the_host_when_embedded(browser):
    html = render(EXAMPLE, "html")
    page = browser.new_page(viewport={"width": 700, "height": 500})
    page.set_content(
        "<iframe id=f style='width:680px;height:480px;border:0'></iframe>"
        "<script>window.got=[];addEventListener('message',e=>got.push(e.data));</script>"
    )
    page.evaluate("(h) => { document.getElementById('f').srcdoc = h; }", html)
    frame = page.frame_locator("#f")
    frame.locator('svg.view.on .el[data-id="banking"]').click()
    page.wait_for_timeout(500)
    frame.locator('svg.view.on .el[data-id="db"]').click()
    frame.locator("#d-docs").click()
    page.wait_for_function("window.got.some(m => m && m.type === 'uml-mcp/open-link')")
    messages = page.evaluate("window.got")
    assert {
        "type": "uml-mcp/open-link",
        "url": "https://www.postgresql.org/docs/",
    } in messages
    assert any(m.get("type") == "uml-mcp/plugin-ready" for m in messages)
    assert frame.locator("h1").is_hidden()  # the viewer has its own title
    page.close()


def test_pan_zoom_fit_theme_and_export(browser):
    page, errors = open_page(browser, render(EXAMPLE, "html"), 1000, 700)
    full = page.evaluate("window.__c4.box()")
    page.click("#zin")
    assert page.evaluate("window.__c4.box()")[2] < full[2]
    box = page.locator("main").bounding_box()
    page.mouse.move(box["x"] + 40, box["y"] + 40)
    page.mouse.down()
    page.mouse.move(box["x"] + 140, box["y"] + 90, steps=5)
    page.mouse.up()
    assert page.evaluate("window.__c4.view") == "context"  # a drag is not a click
    page.click("#fit")
    assert page.evaluate("window.__c4.box()") == full
    page.click("#theme")
    assert page.evaluate("document.documentElement.className") == "light"
    exported = page.evaluate("window.__c4.svgText()")
    root = ET.fromstring(exported)
    assert root.get("class") == "c4 light" and root.find(SVG + "style") is not None
    assert 'class="badge"' not in exported and "tabindex" not in exported
    with page.expect_download() as info:
        page.click("details.menu summary")
        page.click("#export-html")
    assert info.value.suggested_filename.endswith(".html")
    with page.expect_download() as info:
        page.click("details.menu summary")
        page.click("#export-png")
    assert info.value.suggested_filename.endswith(".png")
    assert not errors
    page.close()


def test_frame_shape_picks_the_flow_and_resizing_swaps_it(browser):
    page, errors = open_page(browser, render(EXAMPLE, "html"), 1400, 600)
    page.evaluate("window.__c4.go('container:banking')")
    assert page.evaluate("window.__c4.direction") == "LR"
    page.set_viewport_size({"width": 500, "height": 1000})
    wait_for(page, "window.__c4.direction", "TB")
    assert page.locator("svg.view.on").get_attribute("data-dir") == "TB"
    assert not errors
    page.close()


def test_keyboard_drills_with_enter(browser):
    page, errors = open_page(browser, render(EXAMPLE, "html"), 1200, 800)
    page.focus('svg.view.on .el[data-id="banking"]')
    page.keyboard.press("Enter")
    wait_view(page, "container:banking")
    page.keyboard.press("Backspace")
    wait_view(page, "context")
    assert not errors
    page.close()
