"""The statechart plugin: validation messages, SVG/HTML safety and the simulator."""

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
    Path(__file__).resolve().parents[1]
    / "examples/plugins/uml-mcp-plugin-statechart/src"
)
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import itertools

from uml_mcp_plugin_statechart import StatechartRenderer
from uml_mcp_plugin_statechart.layout import layout, text_width
from uml_mcp_plugin_statechart.model import SpecError, parse, warnings_for
from uml_mcp_plugin_statechart.samples import (
    EXAMPLE,
    ORDER,
    SAMPLES,
    TEMPLATE,
    TRAFFIC_LIGHT,
)

TYPE = "state_machine"
NS = "{http://www.w3.org/2000/svg}"


def problems(source: dict) -> list[str]:
    return StatechartRenderer().validate(TYPE, json.dumps(source))


def test_registers_one_sandboxed_type():
    renderer = StatechartRenderer()
    assert list(renderer.diagram_types) == [TYPE]
    spec = renderer.diagram_types[TYPE]
    assert spec.formats == ("html", "svg")
    assert spec.security_profile == "sandboxed"
    assert spec.example == EXAMPLE and spec.template == TEMPLATE


@pytest.mark.parametrize("name", sorted(SAMPLES))
@pytest.mark.parametrize("fmt", ["svg", "html"])
def test_samples_validate_and_render(name, fmt):
    renderer = StatechartRenderer()
    source = SAMPLES[name]
    assert renderer.validate(TYPE, source) == []
    assert renderer.warnings(TYPE, source) == []
    out = renderer.render(TYPE, source, fmt)
    if fmt == "svg":
        assert out.mime_type == "image/svg+xml"
        root = ET.fromstring(out.content)
        assert root.tag == f"{NS}svg"
        assert b"<script" not in out.content
        assert b"var(--" not in out.content  # resvg has no CSS variables
    else:
        assert out.mime_type.startswith("text/html")


def test_static_svg_draws_every_kind_of_state():
    svg = StatechartRenderer().render(TYPE, ORDER, "svg").content.decode()
    root = ET.fromstring(svg)
    kinds = {
        g.get("data-id"): g.get("class")
        for g in root.iter(f"{NS}g")
        if "sc-state" in (g.get("class") or "")
    }
    assert kinds["checkout"] == "sc-state sc-compound"
    assert kinds["fulfilment"] == "sc-state sc-parallel"
    assert kinds["fulfilment.packing"] == "sc-state sc-region"
    assert kinds["delivered"] == "sc-state sc-final"
    assert kinds["checkout.hist"] == "sc-state sc-history"
    assert kinds["cart"] == "sc-state sc-atomic"
    assert svg.count('class="sc-sep"') == 1  # two regions, one dashed separator
    assert svg.count('class="sc-dot"') == 4  # machine, checkout, packing, invoice
    assert ">H<" in svg
    # guard and actions get their own colours
    assert '<tspan class="sc-guard"> [cardOk]</tspan>' in svg
    assert '<tspan class="sc-acts"> / charge</tspan>' in svg
    # a targetless transition is an internal activity line, not an arrow
    assert "ADD_ITEM / addItem" in svg
    assert 'data-event="ADD_ITEM"' not in svg


def test_transitions_are_orthogonal_and_avoid_states():
    machine = parse(ORDER)
    lay = layout(machine)
    solid = [b for b in lay.boxes if b.kind in ("atomic", "final", "history")]
    for edge in lay.edges:
        pts = edge.points
        for (x1, y1), (x2, y2) in itertools.pairwise(pts):
            assert x1 == x2 or y1 == y2, (edge.tid, pts)
        if edge.self_loop:
            continue
        for (x1, y1), (x2, y2) in itertools.pairwise(pts):
            for b in solid:
                if b.id in (edge.source, edge.target):
                    continue
                bx, by, bw, bh = b.shape
                inside_x = min(x1, x2) < bx + bw - 1 and bx + 1 < max(x1, x2)
                inside_y = min(y1, y2) < by + bh - 1 and by + 1 < max(y1, y2)
                assert not (inside_x and inside_y), (edge.tid, b.id)
    # labels never sit on a state
    for edge in lay.edges:
        if not edge.label:
            continue
        for b in solid:
            bx, by, bw, bh = b.shape
            assert not (
                edge.lx - edge.lw / 2 < bx + bw
                and bx < edge.lx + edge.lw / 2
                and edge.ly - 9 < by + bh
                and by < edge.ly + 9
            ), (edge.label, b.id)


def test_children_sit_inside_their_containers():
    machine = parse(ORDER)
    boxes = {b.id: b for b in layout(machine).boxes}
    for box in boxes.values():
        st = machine.states.get(box.id)
        if not st or not st.parent:
            continue
        p = boxes[st.parent]
        assert p.x <= box.x and box.x + box.w <= p.x + p.w + 0.01, box.id
        assert p.y <= box.y and box.y + box.h <= p.y + p.h + 0.01, box.id


def test_self_transition_draws_a_loop():
    source = {
        "initial": "a",
        "states": {"a": {"on": {"PING": "a", "GO": "b"}}, "b": {"type": "final"}},
    }
    lay = layout(parse(json.dumps(source)))
    loops = [e for e in lay.edges if e.self_loop]
    assert len(loops) == 1 and loops[0].label == "PING"


def test_top_down_direction_and_root_events():
    lay = layout(parse(TRAFFIC_LIGHT))
    boxes = {b.id: b for b in lay.boxes}
    assert boxes["yellow"].y > boxes["green"].y  # flows top down
    assert [text for _tid, text, _x in lay.any_items] == [
        "FAULT / alertCrew → maintenance"
    ]
    svg = StatechartRenderer().render(TYPE, TRAFFIC_LIGHT, "svg").content.decode()
    assert "ANY STATE" in svg


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("not json", "source is not valid JSON"),
        ("[]", "source must be a JSON object"),
        ({"initial": "a"}, '"states" is required'),
        (
            {"initial": "a", "states": {"a": {"on": {"GO": "shiped"}}, "shipped": {}}},
            'state "a": event "GO" targets "shiped", which does not exist; did you mean "shipped"?',
        ),
        (
            {"states": {"a": {}, "b": {}}},
            'the machine is compound but has no "initial"; set it to one of a, b',
        ),
        (
            {
                "initial": "p",
                "states": {"p": {"states": {"x": {}, "y": {}}}},
            },
            'state "p" is compound but has no "initial"; set it to one of x, y',
        ),
        (
            {
                "initial": "p",
                "states": {"p": {"initial": "z", "states": {"x": {}}}},
            },
            'state "p": initial "z" is not one of its child states',
        ),
        (
            {"initial": "a", "states": {"a": {"type": "final", "on": {"GO": "a"}}}},
            'state "a" is final and cannot have "on"',
        ),
        (
            {"initial": "a", "states": {"a": {"type": "weird"}}},
            'state "a": unknown type "weird"',
        ),
        (
            {"initial": "a", "states": {"a": {"onn": {}}}},
            "state \"a\": unknown key 'onn'",
        ),
        (
            {
                "initial": "p",
                "states": {
                    "p": {
                        "type": "parallel",
                        "initial": "x",
                        "states": {"x": {}, "y": {}},
                    }
                },
            },
            'state "p" is parallel: every region starts at once, so it takes no "initial"',
        ),
        (
            {
                "initial": "a",
                "states": {
                    "a": {"on": {"GO": "b.c"}},
                    "b": {"initial": "d", "states": {"d": {}}},
                },
            },
            'state "a": event "GO" targets "b.c", which does not exist',
        ),
        (
            {"initial": "a", "states": {"a": {"type": "history", "history": "wide"}}},
            '"history" must be "shallow" or "deep"',
        ),
    ],
)
def test_validation_names_the_state(source, expected):
    code = source if isinstance(source, str) else json.dumps(source)
    messages = StatechartRenderer().validate(TYPE, code)
    assert any(expected in m for m in messages), messages


def test_every_problem_is_reported_at_once():
    messages = problems(
        {
            "initial": "a",
            "states": {
                "a": {"on": {"X": "nowhere", "Y": "elsewhere"}},
                "b": {"type": "bogus"},
            },
        }
    )
    assert len(messages) == 3


def test_render_refuses_invalid_source_and_formats():
    renderer = StatechartRenderer()
    with pytest.raises(ValueError, match="does not exist"):
        renderer.render(
            TYPE,
            json.dumps({"initial": "a", "states": {"a": {"on": {"X": "b"}}}}),
            "svg",
        )
    with pytest.raises(ValueError, match="html or svg"):
        renderer.render(TYPE, ORDER, "png")
    assert renderer.validate("other", ORDER) == ["unknown statechart type: other"]


def test_target_forms_resolve():
    machine = parse(
        json.dumps(
            {
                "id": "m",
                "initial": "a",
                "states": {
                    "a": {
                        "initial": "x",
                        "on": {"IN": ".y", "ABS": "#m.b", "ALIAS": "#bee"},
                        "states": {"x": {"on": {"UP": "b", "SIB": "y"}}, "y": {}},
                    },
                    "b": {"id": "bee"},
                },
            }
        )
    )
    targets = {t.event: t.targets for t in machine.transitions}
    assert targets == {
        "IN": ["a.y"],
        "ABS": ["b"],
        "ALIAS": ["b"],
        "UP": ["b"],
        "SIB": ["a.y"],
    }


def test_unreachable_states_are_warnings_not_errors():
    source = json.dumps(
        {
            "initial": "a",
            "states": {
                "a": {"on": {"GO": "b"}},
                "b": {},
                "orphan": {"initial": "x", "states": {"x": {}}},
            },
        }
    )
    renderer = StatechartRenderer()
    assert renderer.validate(TYPE, source) == []
    assert renderer.warnings(TYPE, source) == [
        'state "orphan" is unreachable: no initial state or transition leads to it'
    ]
    assert warnings_for(parse(ORDER)) == []
    assert renderer.warnings(TYPE, "nope") == []


def test_configure_limits_states():
    renderer = StatechartRenderer()
    renderer.configure({"max_states": 3})
    assert any("too many states" in m for m in renderer.validate(TYPE, ORDER))
    with pytest.raises(ValueError):
        renderer.configure({"max_states": 0})


def test_xstate_extras_are_accepted():
    machine = parse(
        json.dumps(
            {
                "id": "x",
                "initial": "a",
                "predictableActionArguments": True,
                "states": {
                    "a": {
                        "after": {"1000": "b"},
                        "always": {"target": "b", "cond": "ready"},
                        "meta": {"note": 1},
                        "entry": [{"type": "log"}],
                    },
                    "b": {"tags": ["x"], "type": "final"},
                },
            }
        )
    )
    events = [(t.event, t.kind, t.guard) for t in machine.transitions]
    assert events == [("always", "always", "ready"), ("after 1000ms", "after", None)]
    assert machine.states["a"].entry == ["log"]


def test_text_width_grows_with_text():
    assert text_width("WWW") > text_width("iii")
    assert text_width("abc", bold=True) > text_width("abc")


def test_spec_error_lists_problems():
    with pytest.raises(SpecError) as info:
        parse("{}")
    assert info.value.problems


def _sha(text: str) -> str:
    return base64.b64encode(hashlib.sha256(text.encode()).digest()).decode()


def test_page_is_csp_locked_and_escapes_source():
    hostile = json.dumps(
        {
            "title": "</script><img src=x onerror=alert(1)>",
            "initial": "a",
            "states": {
                "a": {
                    "description": "<b>bold</b> & </script>",
                    "on": {"GO": "b"},
                },
                "b": {"type": "final"},
            },
        }
    )
    page = StatechartRenderer().render(TYPE, hostile, "html").content.decode()
    found = re.search(r'Content-Security-Policy" content="([^"]+)"', page)
    assert found
    csp = unescape(found[1])
    assert "default-src 'none'" in csp and "connect-src" not in csp
    scripts = re.findall(r"<script>(.*?)</script>", page, re.DOTALL)
    styles = re.findall(r"<style>(.*?)</style>", page, re.DOTALL)
    assert len(scripts) == 1 and len(styles) == 1
    assert f"'sha256-{_sha(scripts[0])}'" in csp
    assert f"'sha256-{_sha(styles[0])}'" in csp
    assert "<img src=x" not in page
    block = re.search(
        r'<script type="application/json" id="machine">(.*?)</script>', page, re.DOTALL
    )
    assert block
    data = block[1]
    assert "<" not in data
    assert json.loads(data)["states"]["a"]["description"] == "<b>bold</b> & </script>"
    assert "http" not in scripts[0].replace("http://www.w3.org/2000/svg", "")


@pytest.fixture
def loaded(tmp_path, monkeypatch):
    """The statechart renderer loaded through the plugin loader, as the server does."""
    import importlib.metadata as md

    from mcp_core.core.config import MCP_SETTINGS
    from mcp_core.core.settings_file import reset_config_cache
    from mcp_core.plugins import loader
    from mcp_core.plugins.api import RENDERERS_GROUP

    eps = {
        RENDERERS_GROUP: [
            md.EntryPoint(
                "statechart",
                "uml_mcp_plugin_statechart:StatechartRenderer",
                RENDERERS_GROUP,
            )
        ]
    }
    monkeypatch.setattr(loader, "entry_points", lambda group: eps.get(group, []))
    cfg = tmp_path / "uml-mcp.yaml"
    cfg.write_text("plugins:\n  enabled: [statechart]\n", encoding="utf-8")
    monkeypatch.setenv("UML_MCP_CONFIG", str(cfg))
    reset_config_cache()
    loader.load_plugins()
    yield loader
    for dtype in list(loader.RENDERERS):
        MCP_SETTINGS.diagram_types.pop(dtype, None)
    loader.RENDERERS.clear()
    loader.STATUS.clear()
    reset_config_cache()


def test_validate_uml_returns_errors_and_warnings(loaded):
    from mcp_core.core.diagram_validation import validate_uml_inputs

    good = validate_uml_inputs(TYPE, ORDER, "svg")
    assert good["valid"] and good["backend"] == "plugin:statechart"
    assert good["warnings"] == []
    orphan = json.dumps(
        {"initial": "a", "states": {"a": {}, "lost": {"on": {"GO": "a"}}}}
    )
    warned = validate_uml_inputs(TYPE, orphan, "html")
    assert warned["valid"] and warned["warnings"] == [
        'state "lost" is unreachable: no initial state or transition leads to it'
    ]
    bad = validate_uml_inputs(
        TYPE, json.dumps({"initial": "x", "states": {"a": {}}}), "svg"
    )
    assert not bad["valid"] and bad["warnings"] == []
    assert any('initial "x" is not one of its child states' in e for e in bad["errors"])


def test_a_warnings_hook_that_raises_is_ignored(loaded, monkeypatch):
    monkeypatch.setattr(StatechartRenderer, "warnings", lambda self, t, c: 1 / 0)
    assert loaded.plugin_warnings(TYPE, ORDER) == []
    assert loaded.plugin_warnings("class", "x") == []


# ---------------------------------------------------------------------------- browser

playwright = pytest.importorskip("playwright.sync_api")


def _open(pw, source: str, width: int = 1280, height: int = 800):
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={"width": width, "height": height})
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on(
        "console",
        lambda m: errors.append(m.text) if m.type == "error" else None,
    )
    page.set_content(StatechartRenderer().render(TYPE, source, "html").content.decode())
    return browser, page, errors


def _leaves(page) -> list[str]:
    return page.evaluate("window.__statechart.leaves()")


def _buttons(page) -> list[str]:
    return page.locator("#events button").all_inner_texts()


def test_simulator_runs_the_order_lifecycle():
    with playwright.sync_playwright() as pw:
        browser, page, errors = _open(pw, ORDER)
        assert _leaves(page) == ["cart"]
        assert _buttons(page) == ["ADD_ITEM", "CHECKOUT"]
        assert page.locator('.sc-state.on[data-id="cart"]').count() == 1
        assert page.is_disabled("#undo")

        page.click('#events button[data-event="ADD_ITEM"]')  # internal: stays in cart
        assert _leaves(page) == ["cart"]
        assert page.evaluate("window.__statechart.log()[1].actions") == ["addItem"]

        page.click('#events button[data-event="CHECKOUT"]')
        assert _leaves(page) == ["checkout.address"]
        assert page.locator('.sc-state.on[data-id="checkout"]').count() == 1
        assert "startTimer" in " ".join(
            page.evaluate("window.__statechart.log()[2].actions")
        )

        page.click('#events button[data-event="NEXT"]')
        assert _leaves(page) == ["checkout.payment"]
        # two guarded alternatives: the reader picks one
        assert "PAY [cardOk]" in _buttons(page) and "PAY [cardDeclined]" in _buttons(
            page
        )

        # history: leave for help and come back to the same step
        page.click('#events button[data-event="HELP"]')
        assert _leaves(page) == ["help"]
        page.click('#events button[data-event="RESUME"]')
        assert _leaves(page) == ["checkout.payment"]

        page.click('#events button[data-event="PAY"][data-guard="cardDeclined"]')
        assert _leaves(page) == ["checkout.declined"]
        page.click('#events button[data-event="RETRY"]')

        # a clickable transition label fires that alternative
        page.locator(".sc-label.can", has_text="cardOk").click()
        # parallel: both regions start
        assert _leaves(page) == [
            "fulfilment.packing.picking",
            "fulfilment.invoice.drafting",
        ]
        active = page.evaluate("window.__statechart.active()")
        assert {"fulfilment", "fulfilment.packing", "fulfilment.invoice"} <= set(active)
        assert "stopTimer" in " ".join(
            page.evaluate("window.__statechart.log().at(-1).actions")
        )
        assert page.locator(".sc-state.on.sc-region").count() == 2

        page.click('#events button[data-event="PACKED"]')
        assert _leaves(page) == [
            "fulfilment.packing.packed",
            "fulfilment.invoice.drafting",
        ]
        assert not page.evaluate("window.__statechart.finished()")
        page.click('#events button[data-event="SEND"]')
        # both regions final: fulfilment is done and onDone moves on to delivered
        assert _leaves(page) == ["delivered"]
        assert page.evaluate("window.__statechart.finished()")
        assert _buttons(page) == []
        assert "Finished" in page.inner_text("#events")
        assert "notifyCustomer" in " ".join(
            page.evaluate("window.__statechart.log().at(-1).actions")
        )

        page.click("#undo")
        assert _leaves(page) == [
            "fulfilment.packing.packed",
            "fulfilment.invoice.drafting",
        ]
        page.click("#reset")
        assert _leaves(page) == ["cart"]
        assert page.is_disabled("#undo") and page.is_disabled("#reset")
        assert not errors
        browser.close()


def test_label_click_and_detail_card():
    with playwright.sync_playwright() as pw:
        browser, page, errors = _open(pw, ORDER)
        # click the CHECKOUT label on the drawing
        label = page.locator(".sc-label.can").first
        assert "CHECKOUT" in (label.text_content() or "")
        label.click()
        assert _leaves(page) == ["checkout.address"]
        assert page.locator(".sc-tr.fire, .sc-label.fire").count() >= 1
        # a disabled label explains itself instead of firing
        disabled = page.locator(".sc-label:not(.can)", has_text="SEND").first
        disabled.click(force=True)  # aria-disabled: Playwright would wait for it
        assert "not enabled" in page.inner_text("#status")
        assert _leaves(page) == ["checkout.address"]
        # the detail card of a compound state
        page.evaluate("window.__statechart.select('checkout')")
        assert page.is_visible("#card")
        card = page.inner_text("#card")
        assert (
            "COMPOUND STATE" in card.upper()
            and "startTimer" in card
            and "stopTimer" in card
        )
        assert "HELP" in card and "CANCEL" in card
        assert "Address, then payment" in card
        page.click("#card .close")
        assert page.is_hidden("#card")
        # clicking a state on the drawing opens its card
        page.locator('.sc-state[data-id="help"] .sc-box').click()
        assert page.inner_text("#card h2") == "help"
        page.keyboard.press("Escape")
        assert page.is_hidden("#card")
        assert not errors
        browser.close()


def test_simulator_fits_a_chat_frame():
    with playwright.sync_playwright() as pw:
        browser, page, errors = _open(pw, ORDER, 560, 430)
        stage = page.locator("#stage svg").bounding_box()
        main = page.locator("main").bounding_box()
        assert stage and main and main["height"] > 160
        # fitted on load: the whole drawing is inside the diagram area
        assert (
            stage["x"] >= main["x"] - 1
            and stage["x"] + stage["width"] <= main["x"] + main["width"] + 1
        )
        assert (
            stage["y"] >= main["y"] - 1
            and stage["y"] + stage["height"] <= main["y"] + main["height"] + 1
        )
        # every control is on screen and usable
        for selector in (
            "#undo",
            "#reset",
            "#fit",
            "#theme",
            '#events button[data-event="CHECKOUT"]',
        ):
            box = page.locator(selector).bounding_box()
            assert (
                box
                and box["x"] + box["width"] <= 560
                and box["y"] + box["height"] <= 430
            ), selector
        assert page.locator("#logbox").get_attribute("open") is None  # log folded away
        page.click('#events button[data-event="CHECKOUT"]')
        page.click('#events button[data-event="NEXT"]')
        page.click('#events button[data-event="PAY"][data-guard="cardOk"]')
        assert page.locator("#active .chip").all_inner_texts() == [
            "fulfilment › packing › picking",
            "fulfilment › invoice › drafting",
        ]
        page.click("#theme")
        assert page.get_attribute("html", "data-theme") == "dark"
        assert not errors
        browser.close()


def test_traffic_light_parallel_and_root_events():
    with playwright.sync_playwright() as pw:
        browser, page, errors = _open(pw, TRAFFIC_LIGHT, 560, 430)
        assert _leaves(page) == ["green"]
        assert set(_buttons(page)) == {"TIMER", "FAULT"}
        page.click('#events button[data-event="TIMER"]')
        page.click('#events button[data-event="TIMER"]')
        assert _leaves(page) == ["red.walk"]
        page.click('#events button[data-event="COUNTDOWN"]')
        page.click('#events button[data-event="COUNTDOWN"]')
        # red is done, so its onDone goes back to green
        assert _leaves(page) == ["green"]
        page.click('#events button[data-event="FAULT"]')
        assert _leaves(page) == ["maintenance.lamp.on", "maintenance.crew.working"]
        page.click('#events button[data-event="BLINK"]')
        assert _leaves(page) == ["maintenance.lamp.off", "maintenance.crew.working"]
        page.click('#events button[data-event="FINISH"]')
        page.click('#events button[data-event="RESUME"]')
        assert _leaves(page) == ["red.walk"]
        assert not errors
        browser.close()


def test_exports_svg_png_and_html():
    with playwright.sync_playwright() as pw:
        browser, page, errors = _open(pw, ORDER)
        svg = page.evaluate("window.__statechart.svgText()")
        root = ET.fromstring(svg)
        assert root.tag == f"{NS}svg" and "<style>" in svg and "var(--" not in svg
        for button, suffix in (
            ("#save-svg", ".svg"),
            ("#save-png", ".png"),
            ("#save-html", ".html"),
        ):
            page.click("details.menu summary")
            with page.expect_download() as info:
                page.click(button)
            assert info.value.suggested_filename == "Order-lifecycle" + suffix
        assert not errors
        browser.close()
