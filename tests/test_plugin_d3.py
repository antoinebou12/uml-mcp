"""The D3 plugin: source validation, icons, A* routing, layout, SVG/HTML safety, loader.

The plugin is an installable package under ``examples/plugins``; like the hello plugin it is
loaded here through patched entry points, so these tests need no installation. The browser
behaviour (zoom, drag, re-routing) is covered by ``test_plugin_d3_browser.py``.
"""

from __future__ import annotations

import base64
import hashlib
import itertools
import json
import random
import re
import shutil
import subprocess
import textwrap
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest
from uml_mcp_plugin_d3 import (
    D3Renderer,
    force,
    html,
    layout,
    router,
    spec,
)
from uml_mcp_plugin_d3.icons import (
    KINDS,
    PROVIDERS,
    SERVICES,
    catalog,
    resolve_service,
)
from uml_mcp_plugin_d3.samples import SAMPLES
from uml_mcp_plugin_d3.svg import architecture_svg

from tests.fixtures_d3 import D3_SRC, PNG_1PX, grab, spec_of

ARCH_TYPES = ("d3_architecture", "d3_topology")
ALL_TYPES = ("d3_force", *ARCH_TYPES)


def example(dtype: str) -> dict:
    return json.loads(SAMPLES[dtype][0])


def arch(**overrides) -> str:
    base = {
        "nodes": [{"id": "a", "kind": "server"}, {"id": "b", "kind": "database"}],
        "links": [{"from": "a", "to": "b"}],
    }
    return json.dumps({**base, **overrides})


# --------------------------------------------------------------------- vendored D3
def test_vendored_d3_is_the_published_file() -> None:
    raw = html.files("uml_mcp_plugin_d3").joinpath("assets", html.D3_FILE).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == html.D3_SHA256
    assert (
        html.d3_sri()
        == "sha384-CjloA8y00+1SDAUkjs099PVfnY2KmDC2BZnws9kh8D/lX1s46w6EPhpXdqMfjK6i"
    )
    licence = (
        html.files("uml_mcp_plugin_d3")
        .joinpath("assets", "d3.LICENSE")
        .read_text(encoding="utf-8")
    )
    assert "Mike Bostock" in licence and "Permission to use" in licence


@pytest.mark.parametrize(
    "name", ["common.js", "router.js", "arch.js", "force.js", html.D3_FILE]
)
def test_scripts_are_safe_to_inline(name: str) -> None:
    """A ``</script``, ``<script`` or ``<!--`` inside an inline script would end or confuse it."""
    text = html.asset(name).lower()
    assert "<script" not in text and "</script" not in text and "<!--" not in text


# ------------------------------------------------------------------------ the spec
@pytest.mark.parametrize("dtype", ALL_TYPES)
def test_examples_and_templates_are_valid(dtype: str) -> None:
    for source in SAMPLES[dtype]:
        spec.parse(dtype, source)


def problems(dtype: str, code: str) -> list[str]:
    with pytest.raises(spec.SpecError) as err:
        spec.parse(dtype, code)
    return err.value.problems


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("{not json", "not valid JSON"),
        ("[1, 2]", "must be a JSON object"),
        ("{}", "nodes: required"),
        ('{"nodes": []}', "at least one node"),
        ('{"nodes": [{"id": "a", "lable": "x"}]}', "unknown field"),
        ('{"nodes": [{"id": "a"}, {"id": "a"}]}', "duplicate"),
        ('{"nodes": [{"id": "a b"}]}', "use 1-64 letters"),
        (
            '{"nodes": [{"id": "a"}], "links": [{"source": "a", "target": "zzz"}]}',
            "no such node",
        ),
        (
            '{"nodes": [{"id": "a"}], "links": [{"source": "a", "target": "a"}]}',
            "cannot link to itself",
        ),
        ('{"nodes": [{"id": "a", "size": 99}]}', "less than or equal"),
    ],
)
def test_force_source_errors_are_specific(code: str, expected: str) -> None:
    assert any(expected in p for p in problems("d3_force", code))


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"provider": "oracle"}, "provider 'oracle'"),
        ({"direction": "RL"}, "direction"),
        ({"groups": [{"id": "g", "parent": "nope"}]}, "no such group"),
        ({"groups": [{"id": "g", "type": "weird"}]}, "type 'weird'"),
        ({"groups": [{"id": "g"}]}, "contains no nodes"),
        (
            {"groups": [{"id": "g", "parent": "h"}, {"id": "h", "parent": "g"}]},
            "its own ancestor",
        ),
        ({"nodes": [{"id": "a", "group": "ghost"}]}, "no such group"),
        ({"nodes": [{"id": "a", "kind": "toaster"}]}, "kind 'toaster'"),
        ({"nodes": [{"id": "a", "service": "oracle:db"}]}, "unknown provider 'oracle'"),
        (
            {
                "nodes": [{"id": "a", "outputs": ["x"]}, {"id": "b"}],
                "links": [{"from": "a:y", "to": "b"}],
            },
            "no output port 'y'",
        ),
        (
            {
                "nodes": [{"id": "a"}, {"id": "b"}],
                "links": [{"from": "a", "to": "b:in"}],
            },
            "no input port 'in'",
        ),
        (
            {"nodes": [{"id": "a"}], "links": [{"from": "a", "to": "a"}]},
            "cannot link to itself",
        ),
    ],
)
def test_architecture_source_errors_are_specific(
    overrides: dict, expected: str
) -> None:
    code = json.dumps({"nodes": [{"id": "a"}, {"id": "b"}], "links": [], **overrides})
    assert any(expected in p for p in problems("d3_architecture", code))


def test_every_problem_is_reported_at_once() -> None:
    code = json.dumps(
        {
            "provider": "oracle",
            "nodes": [{"id": "a", "kind": "toaster"}, {"id": "a"}],
            "links": [{"from": "a", "to": "ghost"}],
        }
    )
    found = problems("d3_architecture", code)
    assert len(found) >= 4, found


def test_limits_protect_the_renderer() -> None:
    many = json.dumps({"nodes": [{"id": f"n{i}"} for i in range(spec.MAX_NODES + 1)]})
    assert any("at most" in p for p in problems("d3_force", many))
    assert any("at most 3" in p for p in _limited(3))


def _limited(max_nodes: int) -> list[str]:
    code = json.dumps({"nodes": [{"id": f"n{i}"} for i in range(5)]})
    with pytest.raises(spec.SpecError) as err:
        spec.parse_force(code, max_nodes=max_nodes)
    return err.value.problems


# ----------------------------------------------------------------------- the icons
def test_every_service_maps_to_a_known_glyph_and_provider() -> None:
    for key, (kind, name) in SERVICES.items():
        provider, _, service = key.partition(":")
        assert provider in PROVIDERS and service and name
        assert kind in KINDS, key


def test_every_glyph_is_well_formed_svg() -> None:
    for kind, fragment in KINDS.items():
        ET.fromstring(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">{fragment}</svg>'
        )
        assert fragment.strip(), kind


@pytest.mark.parametrize(
    ("service", "kind", "default", "expected"),
    [
        ("aws:lambda", None, "generic", ("aws", "function", "Lambda")),
        ("lambda", None, "aws", ("aws", "function", "Lambda")),
        ("azure:aks", None, "aws", ("azure", "kubernetes", "AKS")),
        ("gcp:pubsub", None, "generic", ("gcp", "topic", "Pub/Sub")),
        ("database", None, "generic", ("generic", "database", "Database")),
        ("aws:glue-jobs", None, "generic", ("aws", "service", "Glue Jobs")),
        (None, "cache", "gcp", ("gcp", "cache", "Cache")),
        ("aws:s3", "database", "generic", ("aws", "database", "S3")),
        (None, None, "weird", ("generic", "service", "Service")),
    ],
)
def test_service_resolution(service, kind, default, expected) -> None:
    got = resolve_service(service, kind, default)
    assert (got.provider, got.kind, got.name) == expected


def test_catalog_can_be_filtered_by_provider() -> None:
    aws = catalog("aws")
    assert aws["services"] and all(key.startswith("aws:") for key in aws["services"])
    assert set(aws["providers"]) == set(PROVIDERS) and "database" in aws["kinds"]


# ---------------------------------------------------------------------- the router
def route_between(rects, a, a_dir, b, b_dir, **grid_kwargs):
    grid = router.Grid(rects, **grid_kwargs)
    return grid, router.route(grid, a, a_dir, b, b_dir)


def inside(point, rect, shrink=1.0) -> bool:
    x, y, w, h = rect
    return (
        x + shrink < point[0] < x + w - shrink
        and y + shrink < point[1] < y + h - shrink
    )


def sample(points, step=2):
    for (x1, y1), (x2, y2) in itertools.pairwise(points):
        length = max(abs(x2 - x1), abs(y2 - y1))
        for i in range(0, int(length) + 1, step):
            t = i / length if length else 0
            yield (x1 + (x2 - x1) * t, y1 + (y2 - y1) * t)


def test_a_clear_path_is_a_straight_line() -> None:
    left, right = (0, 0, 100, 50), (300, 0, 100, 50)
    _, points = route_between([left, right], (100, 30), 0, (300, 30), 2)
    assert points == [(100, 30), (400 - 100, 30)] or {p[1] for p in points} == {30}


def test_the_path_goes_around_a_box_in_the_way() -> None:
    left, wall, right = (0, 0, 100, 50), (150, -100, 100, 300), (300, 0, 100, 50)
    _, points = route_between([left, wall, right], (100, 20), 0, (300, 20), 2)
    assert not any(inside(p, wall) for p in sample(points))
    assert all(p[0] == q[0] or p[1] == q[1] for p, q in itertools.pairwise(points))
    assert (
        max(p[1] for p in points) > 200 or min(p[1] for p in points) < -100
    )  # detoured


def test_fewer_turns_win_over_a_slightly_shorter_staircase() -> None:
    _, points = route_between(
        [(0, 0, 50, 50), (400, 300, 50, 50)], (50, 20), 0, (400, 320), 2
    )
    assert len(points) <= 6  # a staircase would have many corners


def test_arrows_spread_apart_instead_of_overlapping() -> None:
    rects = [(0, 0, 100, 100), (400, 0, 100, 100)]
    grid = router.Grid(rects)
    first = router.route(grid, (100, 50), 0, (400, 50), 2)
    second = router.route(grid, (100, 50), 0, (400, 50), 2)
    assert first != second  # the second one avoids running on top of the first


def test_blocked_everywhere_falls_back_to_an_orthogonal_route() -> None:
    rects = [(0, 0, 100, 100), (300, 0, 100, 100)]
    grid = router.Grid(rects, pad=0)
    grid.blocked.update(range(grid.cols * grid.rows))  # nothing is free
    points = router.route(grid, (100, 50), 0, (300, 50), 2)
    assert all(p[0] == q[0] or p[1] == q[1] for p, q in itertools.pairwise(points))


def test_routing_is_deterministic() -> None:
    rects = [(0, 0, 100, 50), (200, -50, 80, 200), (400, 0, 100, 50)]
    runs = [route_between(rects, (100, 20), 0, (400, 20), 2)[1] for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]


def test_simplify_rounded_path_and_midpoint() -> None:
    assert router.simplify([(0, 0), (5, 0), (5, 0), (10, 0), (10, 10)]) == [
        (0, 0),
        (10, 0),
        (10, 10),
    ]
    d = router.rounded_path([(0, 0), (20, 0), (20, 20)], radius=5)
    assert d.startswith("M0,0") and "Q20,0 20,5" in d and d.endswith("L20,20")
    assert router.path_midpoint([(0, 0), (10, 0), (10, 10)]) == (10, 0)
    assert router.rounded_path([]) == ""


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node to run router.js")
def test_javascript_router_returns_the_same_paths(tmp_path: Path) -> None:
    """The browser re-routes with router.js; it must agree with router.py exactly."""
    rng = random.Random(11)
    scenes: list[dict[str, Any]] = []
    for _ in range(25):
        rects = [
            [
                rng.randrange(0, 900, 10),
                rng.randrange(0, 600, 10),
                rng.randrange(80, 200, 10),
                rng.randrange(40, 120, 10),
            ]
            for _ in range(rng.randint(3, 10))
        ]
        edges: list[list[Any]] = []
        for _ in range(rng.randint(2, 10)):
            a, b = rng.sample(rects, 2)
            ad, bd = rng.randrange(4), rng.randrange(4)

            def anchor(r, d):
                x = r[0] + (
                    r[2]
                    if d == 0
                    else 0
                    if d == 2
                    else r[2] // 2 + rng.randrange(-20, 20)
                )
                y = r[1] + (
                    r[3]
                    if d == 1
                    else 0
                    if d == 3
                    else r[3] // 2 + rng.randrange(-10, 10)
                )
                return [x, y]

            edges.append([anchor(a, ad), ad, anchor(b, bd), bd])
        scenes.append(
            {
                "rects": rects,
                "edges": edges,
                "opts": {"cell": rng.choice([10, 10, 16]), "margin": 8},
            }
        )
    runner = tmp_path / "run.js"
    runner.write_text(
        "const R = require(process.argv[2]);"
        "const scenes = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
        "process.stdout.write(JSON.stringify(scenes.map(s => {"
        "const g = new R.Grid(s.rects, s.opts); return s.edges.map(e => R.route(g, e[0], e[1], e[2], e[3])); })));",
        encoding="utf-8",
    )
    done = subprocess.run(
        ["node", str(runner), str(D3_SRC / "uml_mcp_plugin_d3/assets/router.js")],
        input=json.dumps(scenes),
        capture_output=True,
        text=True,
        check=True,
    )
    js = json.loads(done.stdout)
    for scene, js_scene in zip(scenes, js, strict=True):
        grid = router.Grid([tuple(r) for r in scene["rects"]], **scene["opts"])
        for edge, js_route in zip(scene["edges"], js_scene, strict=True):
            py_route = router.route(
                grid, tuple(edge[0]), edge[1], tuple(edge[2]), edge[3]
            )
            assert [list(p) for p in py_route] == js_route


# ---------------------------------------------------------------------- the layout
def build_layout(dtype: str, code: str) -> layout.Layout:
    parsed = spec.parse_arch(dtype, code)
    return layout.build(parsed, dtype, spec.DEFAULT_DIRECTION[dtype])


def random_arch_source(seed: int) -> str:
    rng = random.Random(seed)
    groups: list[dict] = []
    for i in range(rng.randint(0, 4)):
        item: dict = {
            "id": f"g{i}",
            "type": rng.choice(["vpc", "subnet", "zone", "system", "cluster"]),
        }
        if groups and rng.random() < 0.6:
            item["parent"] = rng.choice(groups)["id"]
        groups.append(item)
    nodes: list[dict] = []
    for i in range(rng.randint(4, 14)):
        node: dict = {"id": f"n{i}", "kind": rng.choice(sorted(KINDS))}
        if groups and rng.random() < 0.75:
            node["group"] = rng.choice(groups)["id"]
        if rng.random() < 0.3:
            node["inputs"] = ["in1", "in2"][: rng.randint(1, 2)]
        if rng.random() < 0.3:
            node["outputs"] = ["out1", "out2"][: rng.randint(1, 2)]
        nodes.append(node)
    links = []
    for _ in range(rng.randint(3, 16)):
        a, b = rng.sample(nodes, 2)
        src = (
            f"{a['id']}:{rng.choice(a['outputs'])}"
            if a.get("outputs") and rng.random() < 0.6
            else a["id"]
        )
        dst = (
            f"{b['id']}:{rng.choice(b['inputs'])}"
            if b.get("inputs") and rng.random() < 0.6
            else b["id"]
        )
        link = {"from": src, "to": dst}
        if rng.random() < 0.4:
            link["label"] = f"label {len(links)}"
        links.append(link)
    return json.dumps({"groups": groups, "nodes": nodes, "links": links})


def valid_random_specs(count: int) -> list[str]:
    found, seed = [], 0
    while len(found) < count:
        seed += 1
        source = random_arch_source(seed)
        try:
            spec.parse_arch("d3_architecture", source)
        except spec.SpecError:
            continue
        found.append(source)
    return found


def rect_overlap(a, b) -> bool:
    return (
        a[0] < b[0] + b[2]
        and b[0] < a[0] + a[2]
        and a[1] < b[1] + b[3]
        and b[1] < a[1] + a[3]
    )


def contains(outer, inner) -> bool:
    return (
        outer[0] <= inner[0]
        and outer[1] <= inner[1]
        and inner[0] + inner[2] <= outer[0] + outer[2]
        and inner[1] + inner[3] <= outer[1] + outer[3]
    )


def assert_layout_is_sound(arranged: layout.Layout, parsed: spec.ArchSpec) -> None:
    boxes = {b.id: b for b in arranged.boxes}
    cell = layout.GRID_CELL
    for b in arranged.boxes:  # on the grid, so arrows meet boxes in straight lines
        assert (
            b.x % cell == 0 and b.y % cell == 0 and b.w % cell == 0 and b.h % cell == 0
        ), b
    ids = list(boxes)
    for i, a in enumerate(ids):  # boxes never overlap
        for b in ids[i + 1 :]:
            assert not rect_overlap(boxes[a].rect(), boxes[b].rect()), (a, b)

    groups = {g.id: g for g in arranged.groups}
    parent = {g.id: g.parent for g in parsed.groups}

    def ancestors(gid):
        while gid is not None:
            yield gid
            gid = parent[gid]

    for node in parsed.nodes:  # a group's box contains its members, and no foreign box
        mine = set(ancestors(node.group)) if node.group else set()
        for gid, g in groups.items():
            rect = (g.x, g.y, g.w, g.h)
            if gid in mine:
                assert contains(rect, boxes[node.id].rect()), (gid, node.id)
            else:
                assert not rect_overlap(rect, boxes[node.id].rect()), (gid, node.id)
    for (
        gid,
        g,
    ) in (
        groups.items()
    ):  # sibling groups do not overlap; children sit inside their parent
        for other_id, other in groups.items():
            if gid < other_id and parent[gid] == parent[other_id]:
                assert not rect_overlap(
                    (g.x, g.y, g.w, g.h), (other.x, other.y, other.w, other.h)
                ), (gid, other_id)
        parent_id = parent[gid]
        if parent_id is not None:
            p = groups[parent_id]
            assert contains((p.x, p.y, p.w, p.h), (g.x, g.y, g.w, g.h)), gid

    for e in (
        arranged.edges
    ):  # arrows are orthogonal, start and end on their boxes, and avoid every box
        assert len(e.points) >= 2
        assert all(
            p[0] == q[0] or p[1] == q[1]
            for p, q in zip(e.points, e.points[1:], strict=False)
        ), e.id
        a, b = boxes[e.source], boxes[e.target]
        assert e.points[0] == (a.x + e.src_offset[0], a.y + e.src_offset[1])
        assert e.points[-1] == (b.x + e.dst_offset[0], b.y + e.dst_offset[1])
        for point in sample(e.points):
            for box in boxes.values():
                assert not inside(point, box.rect(), 1.5), (e.id, box.id, point)


@pytest.mark.parametrize("dtype", ARCH_TYPES)
def test_examples_lay_out_cleanly(dtype: str) -> None:
    code = SAMPLES[dtype][0]
    assert_layout_is_sound(build_layout(dtype, code), spec.parse_arch(dtype, code))


def test_random_diagrams_lay_out_cleanly() -> None:
    """No overlapping boxes or groups, grid-aligned boxes, and arrows that avoid every box."""
    for source in valid_random_specs(40):
        parsed = spec.parse_arch("d3_architecture", source)
        assert_layout_is_sound(layout.build(parsed, "d3_architecture", "LR"), parsed)
        assert_layout_is_sound(layout.build(parsed, "d3_architecture", "TB"), parsed)


def test_layout_is_deterministic() -> None:
    source = valid_random_specs(1)[0]
    parsed = spec.parse_arch("d3_architecture", source)
    one = layout.build(parsed, "d3_architecture", "LR")
    two = layout.build(parsed, "d3_architecture", "LR")
    assert [(b.id, b.x, b.y) for b in one.boxes] == [
        (b.id, b.x, b.y) for b in two.boxes
    ]
    assert [e.points for e in one.edges] == [e.points for e in two.edges]


def test_flow_goes_left_to_right_and_top_to_bottom() -> None:
    code = arch(links=[{"from": "a", "to": "b"}])
    lr = build_layout("d3_architecture", code)
    tb = build_layout("d3_topology", code)
    a, b = {x.id: x for x in lr.boxes}["a"], {x.id: x for x in lr.boxes}["b"]
    assert a.x + a.w < b.x
    a, b = {x.id: x for x in tb.boxes}["a"], {x.id: x for x in tb.boxes}["b"]
    assert a.y + a.h < b.y


def test_a_chain_shares_one_lane() -> None:
    """Boxes in different layers line up, instead of stair-stepping down the page."""
    chain = {
        "nodes": [{"id": c, "kind": "server"} for c in "abcd"],
        "links": [
            {"from": "a", "to": "b"},
            {"from": "b", "to": "c"},
            {"from": "c", "to": "d"},
        ],
    }
    arranged = build_layout("d3_architecture", json.dumps(chain))
    assert len({b.y for b in arranged.boxes}) == 1


def test_cycles_still_lay_out() -> None:
    code = arch(
        nodes=[{"id": "a"}, {"id": "b"}, {"id": "c"}],
        links=[
            {"from": "a", "to": "b"},
            {"from": "b", "to": "c"},
            {"from": "c", "to": "a"},
        ],
    )
    arranged = build_layout("d3_architecture", code)
    assert len(arranged.edges) == 3 and all(len(e.points) >= 2 for e in arranged.edges)


def test_assign_layers_ignores_back_edges() -> None:
    layers = layout.assign_layers(["a", "b", "c"], [("a", "b"), ("b", "c"), ("c", "a")])
    assert layers == {"a": 0, "b": 1, "c": 2}


def test_ports_are_drawn_on_the_box_edges() -> None:
    arranged = build_layout("d3_architecture", SAMPLES["d3_architecture"][0])
    orders = {b.id: b for b in arranged.boxes}["orders"]
    edge = next(
        e for e in arranged.edges if e.target == "orders" and e.target_port == "invoke"
    )
    assert edge.dst_offset == (0, orders.port_y(0)) and edge.dst_dir == 2
    out = next(
        e for e in arranged.edges if e.source == "orders" and e.source_port == "events"
    )
    assert out.src_offset == (orders.w, orders.port_y(1)) and out.src_dir == 0


# ------------------------------------------------------------------------- force
def test_force_layout_is_deterministic_and_finite() -> None:
    parsed = spec.parse_force(SAMPLES["d3_force"][0])
    one, two = force.build(parsed), force.build(parsed)
    assert one.nodes == two.nodes
    assert all(abs(n["x"]) < 5000 and abs(n["y"]) < 5000 for n in one.nodes)
    assert {item["name"] for item in one.legend} == {
        "frontend",
        "edge",
        "backend",
        "data",
    }


def test_force_circles_do_not_overlap() -> None:
    model = force.build(spec.parse_force(SAMPLES["d3_force"][0]))
    for i, a in enumerate(model.nodes):
        for b in model.nodes[i + 1 :]:
            distance = ((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2) ** 0.5
            assert distance >= a["r"] + b["r"], (a["id"], b["id"])


def test_large_graphs_use_the_ring_layout() -> None:
    nodes = [
        {"id": f"n{i}", "group": f"g{i % 3}"} for i in range(force.SIMULATE_UP_TO + 10)
    ]
    model = force.build(spec.parse_force(json.dumps({"nodes": nodes})))
    assert len(model.nodes) == len(nodes)


def test_single_node_graph() -> None:
    model = force.build(spec.parse_force('{"nodes": [{"id": "only"}]}'))
    assert model.nodes[0]["id"] == "only"


# -------------------------------------------------------------------------- svg
def parse_svg(text: str) -> ET.Element:
    return ET.fromstring(text)


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("dtype", ALL_TYPES)
def test_svg_is_well_formed_and_has_no_inline_style_attributes(
    dtype: str, theme: str
) -> None:
    code = json.dumps({**example(dtype), "theme": theme})
    out = D3Renderer().render(dtype, code, "svg")
    root = parse_svg(out.content.decode())
    assert root.tag.endswith("svg") and out.mime_type == "image/svg+xml"
    assert "style=" not in out.content.decode()  # a strict CSP would drop it


def test_svg_escapes_labels_instead_of_trusting_them() -> None:
    payload = '<script>alert(1)</script><img src=x onerror=alert(2)>"&'
    code = json.dumps(
        {
            "title": payload,
            "groups": [{"id": "g", "label": payload}],
            "nodes": [
                {
                    "id": "a",
                    "label": payload,
                    "note": payload,
                    "group": "g",
                    "inputs": ["p"],
                    "outputs": ["q"],
                },
                {"id": "b"},
            ],
            "links": [{"from": "a:q", "to": "b", "label": payload}],
        }
    )
    for fmt in ("svg", "html"):
        text = D3Renderer().render("d3_architecture", code, fmt).content.decode()
        assert "<script>alert(1)" not in text and "<img src=x" not in text
    root = parse_svg(
        D3Renderer().render("d3_architecture", code, "svg").content.decode()
    )
    assert not [
        el
        for el in root.iter()
        if el.tag.split("}")[-1] in {"script", "img", "foreignObject"}
    ]


# ------------------------------------------------------------------------- html
def page(dtype: str, d3_source: str = "cdn", code: str | None = None) -> str:
    renderer = D3Renderer()
    renderer.configure({"d3_source": d3_source})
    return renderer.render(dtype, code or SAMPLES[dtype][0], "html").content.decode()


def csp_of(text: str) -> str:
    csp = grab(r'http-equiv="Content-Security-Policy" content="([^"]*)"', text)
    return csp.group(1).replace("&#x27;", "'")


@pytest.mark.parametrize("d3_source", ["cdn", "inline"])
@pytest.mark.parametrize("dtype", ALL_TYPES)
def test_page_csp_pins_exactly_the_scripts_and_style_it_contains(
    dtype: str, d3_source: str
) -> None:
    text = page(dtype, d3_source)
    csp = csp_of(text)
    assert (
        "default-src 'none'" in csp
        and "base-uri 'none'" in csp
        and "form-action 'none'" in csp
    )
    assert "unsafe-inline" not in csp and "unsafe-eval" not in csp

    def digest(body: str) -> str:
        return (
            "'sha256-"
            + base64.b64encode(hashlib.sha256(body.encode()).digest()).decode()
            + "'"
        )

    scripts = re.findall(
        r"<script(?![^>]*src=)(?![^>]*application/json)>(.*?)</script>", text, re.DOTALL
    )
    assert scripts, "inline scripts expected"
    for body in scripts:
        assert digest(body) in csp
    styles = re.findall(r"<style[^>]*>(.*?)</style>", text, re.DOTALL)
    assert len(styles) == 2  # the page chrome and the diagram, each pinned by hash
    assert "style-src " + " ".join(digest(css) for css in styles) in csp
    if d3_source == "cdn":
        assert html.D3_CDN_URL in csp and f'integrity="{html.d3_sri()}"' in text
        assert len(scripts) == 1
    else:
        assert html.D3_CDN_URL not in text and len(scripts) == 2


@pytest.mark.parametrize("dtype", ALL_TYPES)
def test_page_makes_no_requests_beyond_the_pinned_d3(dtype: str) -> None:
    text = page(dtype)
    urls = {u.rstrip(";") for u in re.findall(r"https?://[^\s\"'<>)]+", text)}
    assert urls <= {html.D3_CDN_URL, "http://www.w3.org/2000/svg"}, urls
    assert "style=" not in text.replace("<style>", "").replace("</style>", "")


def test_inline_d3_makes_the_page_self_contained() -> None:
    text = page("d3_force", "inline")
    assert html.asset(html.D3_FILE) in text and "<script src=" not in text


def test_user_text_cannot_break_out_of_the_data_block() -> None:
    payload = "</script><script>alert(1)</script><!-- &   end"
    code = json.dumps(
        {
            "nodes": [{"id": "a", "label": payload, "note": payload}, {"id": "b"}],
            "links": [{"source": "a", "target": "b"}],
        }
    )
    text = page("d3_force", code=code)
    block = grab(
        r'<script type="application/json" id="spec">(.*?)</script>', text, re.DOTALL
    ).group(1)
    assert "<" not in block and ">" not in block and "&" not in block
    data = json.loads(block)
    assert data["nodes"][0]["label"] == payload  # and it round-trips unchanged
    assert (
        text.lower().count("<script") == 3
    )  # data, d3 (cdn) and the runtime: nothing injected


def test_page_data_matches_the_layout() -> None:
    parsed = spec.parse_arch("d3_architecture", SAMPLES["d3_architecture"][0])
    arranged = layout.build(parsed, "d3_architecture", "LR")
    text = page("d3_architecture")
    data = spec_of(text)
    assert [n["id"] for n in data["nodes"]] == [b.id for b in arranged.boxes]
    assert data["consts"]["gridCell"] == layout.GRID_CELL
    assert all(len(e["points"]) >= 2 for e in data["edges"])


def test_title_is_escaped_in_the_page() -> None:
    text = page(
        "d3_force", code=json.dumps({"title": "<b>x</b>", "nodes": [{"id": "a"}]})
    )
    assert "<title>&lt;b&gt;x&lt;/b&gt;</title>" in text


# ----------------------------------------------------------------------- renderer
def test_renderer_declares_types_with_samples() -> None:
    renderer = D3Renderer()
    assert set(renderer.diagram_types) == set(ALL_TYPES)
    for dtype, declared in renderer.diagram_types.items():
        assert (
            declared.formats == ("html", "svg")
            and declared.example
            and declared.template
        )
        assert len(declared.description) < 260
        renderer.render(dtype, declared.template, "html")


def test_renderer_rejects_other_formats_and_bad_sources() -> None:
    renderer = D3Renderer()
    with pytest.raises(ValueError, match="html or svg"):
        renderer.render("d3_force", SAMPLES["d3_force"][0], "png")
    with pytest.raises(
        ValueError, match="invalid d3_architecture source: .*no such node"
    ):
        renderer.render(
            "d3_architecture", arch(links=[{"from": "a", "to": "zzz"}]), "svg"
        )


def test_renderer_validate_hook() -> None:
    renderer = D3Renderer()
    assert renderer.validate("d3_force", SAMPLES["d3_force"][0]) == []
    assert any(
        "no such node" in p
        for p in renderer.validate(
            "d3_architecture", arch(links=[{"from": "a", "to": "zzz"}])
        )
    )


def test_configure_validates_settings() -> None:
    renderer = D3Renderer()
    renderer.configure({"d3_source": "inline", "max_nodes": 5})
    assert (renderer.d3_source, renderer.max_nodes) == ("inline", 5)
    with pytest.raises(ValueError, match="d3_source"):
        renderer.configure({"d3_source": "https://example.com/d3.js"})
    with pytest.raises(ValueError, match="max_nodes"):
        renderer.configure({"max_nodes": 0})
    with pytest.raises(ValueError, match="max_nodes"):
        renderer.configure({"max_nodes": spec.MAX_NODES + 1})


def test_architecture_svg_title_and_description() -> None:
    arranged = build_layout("d3_architecture", SAMPLES["d3_architecture"][0])
    text = architecture_svg(arranged, title="T", theme="dark", description="d")
    root = parse_svg(text)
    title = root.find("{http://www.w3.org/2000/svg}title")
    assert title is not None and title.text == "T"


# ------------------------------------------- through the server's own rendering pipeline
def test_source_may_be_wrapped_in_a_markdown_fence() -> None:
    fenced = "```json\n" + SAMPLES["d3_force"][1] + "\n```"
    assert spec.parse_force(fenced) == spec.parse_force(SAMPLES["d3_force"][1])
    assert any(
        "not valid JSON" in p for p in problems("d3_force", "```json\nnope\n```")
    )


def test_plugin_types_flow_through_generate_diagram(
    d3_plugin, tmp_path, monkeypatch
) -> None:
    from mcp_core.core.utils import generate_diagram

    status = {s.group: s for s in d3_plugin()}
    assert status["renderers"].loaded and status["tools"].tools == ["d3_catalog"]
    code = SAMPLES["d3_architecture"][0]

    # memory only: the page comes back as bytes with its MIME type
    out = generate_diagram("d3_architecture", code, "html")
    assert (
        out["source"] == "plugin:d3" and out["mime_type"] == "text/html; charset=utf-8"
    )
    page_text = base64.b64decode(out["content_base64"]).decode()
    assert page_text.startswith("<!doctype html>") and out["local_path"] is None

    # with an output_dir inside the sandbox: a file, and the bytes are not repeated
    monkeypatch.setenv("MCP_OUTPUT_ROOT", str(tmp_path))
    saved = generate_diagram("d3_architecture", code, "html", str(tmp_path / "out"))
    written = Path(saved["local_path"])
    assert written.parent == (tmp_path / "out").resolve() and written.suffix == ".html"
    assert written.read_text(encoding="utf-8") == page_text
    assert "content_base64" not in saved and saved["attempts"] == [
        {"backend": "plugin:d3", "ok": True}
    ]

    # outside the sandbox: refused, so it falls back to returning the content
    escaped = generate_diagram(
        "d3_architecture", code, "html", str(tmp_path.parent / "elsewhere")
    )
    assert escaped["local_path"] is None and "content_base64" in escaped


def test_save_falls_back_to_content_when_the_file_cannot_be_written(tmp_path) -> None:
    from mcp_core.core.diagram_rendering import (
        DiagramRenderContext,
        _save_plugin_output,
    )

    blocker = tmp_path / "a-file"
    blocker.write_text("x")
    ctx = DiagramRenderContext(
        diagram_type="d3_force",
        backend_type="plugin:d3",
        prepared_code="{}",
        output_format="html",
        output_dir=str(blocker / "sub"),
        theme=None,
        scale=1.0,
        force_fetch=False,
    )
    out = {"content_base64": "eA=="}
    _save_plugin_output(ctx, out)
    assert out == {"content_base64": "eA=="}


def test_html_is_accepted_for_plugin_types_that_declare_it_only(d3_plugin) -> None:
    from pydantic import ValidationError

    from mcp_core.tools.schemas import GenerateUMLInput

    d3_plugin()
    ok = GenerateUMLInput(diagram_type="d3_force", code="{}", output_format="html")
    assert ok.output_format == "html"
    with pytest.raises(ValidationError, match="not supported for diagram type 'class'"):
        GenerateUMLInput(
            diagram_type="class", code="@startuml\n@enduml", output_format="html"
        )
    # PNG is accepted when SVG is declared (local SVG→PNG raster fallback).
    png = GenerateUMLInput(diagram_type="d3_force", code="{}", output_format="png")
    assert png.output_format == "png"
    with pytest.raises(ValidationError, match="not supported for diagram type"):
        GenerateUMLInput(diagram_type="d3_force", code="{}", output_format="pdf")


def test_validate_uml_reports_the_plugin_renderers_own_problems(d3_plugin) -> None:
    from mcp_core.core.diagram_validation import validate_uml_inputs

    d3_plugin()
    good = validate_uml_inputs("d3_architecture", SAMPLES["d3_architecture"][0], "html")
    assert good["valid"] and good["backend"] == "plugin:d3"
    bad = validate_uml_inputs(
        "d3_architecture", arch(links=[{"from": "a", "to": "zzz"}]), "svg"
    )
    assert not bad["valid"] and any("no such node" in e for e in bad["errors"])


def test_a_validate_hook_that_raises_never_breaks_validation(
    d3_plugin, monkeypatch
) -> None:
    from mcp_core.plugins import loader

    d3_plugin()
    monkeypatch.setattr(D3Renderer, "validate", lambda self, t, c: 1 / 0)
    assert loader.plugin_validate("d3_force", SAMPLES["d3_force"][1]) is None
    assert loader.plugin_validate("class", "x") is None  # a built-in type has no hook


def test_resources_show_the_plugin_types_own_examples_and_templates(d3_plugin) -> None:
    from mcp_core.resources.diagram_resources import (
        get_diagram_examples,
        get_diagram_templates,
    )

    d3_plugin()
    examples = json.loads(get_diagram_examples())
    templates = json.loads(get_diagram_templates())
    for dtype, (example, template) in SAMPLES.items():
        assert examples[dtype] == example and templates[dtype] == template
    assert "@startuml" in examples["class"]  # built-in types are unchanged


def test_admin_catalog_lists_the_plugin_example(d3_plugin) -> None:
    from mcp_core.admin import kroki_routes

    d3_plugin()
    row = next(r for r in kroki_routes.catalog() if r["name"] == "d3_force")
    assert row["backend"] == "plugin:d3" and row["example"] == SAMPLES["d3_force"][0]


def test_a_bad_setting_fails_the_plugin_not_the_server(d3_plugin) -> None:
    from mcp_core.core.config import MCP_SETTINGS

    status = {
        s.group: s for s in d3_plugin("  settings:\n    d3: {d3_source: bogus}\n")
    }
    assert not status["renderers"].loaded and "d3_source" in status["renderers"].error
    assert "d3_force" not in MCP_SETTINGS.diagram_types
    assert status["tools"].loaded  # the tool half is independent


def test_render_summary_names_the_saved_file() -> None:
    from mcp_core.tools.tool_decorator import _summarize_tool_result

    base = {
        "diagram_type": "d3_force",
        "source": "plugin:d3",
        "output_format": "html",
        "render_ms": 3,
    }
    assert "Saved to" not in _summarize_tool_result("generate_uml", base)
    saved = _summarize_tool_result(
        "generate_uml", {**base, "local_path": "/tmp/x.html"}
    )
    assert saved.endswith("Saved to: /tmp/x.html")


def test_html_has_a_mime_type() -> None:
    from mcp_core.core.diagram_rendering import _mime_for_output_format

    assert _mime_for_output_format("html") == "text/html; charset=utf-8"


# ------------------------------------------------- samples and docs stay correct
def svg_text_of(svg: bytes) -> str:
    return "".join(ET.fromstring(svg).itertext())


def labels_of(parsed: spec.ForceSpec | spec.ArchSpec) -> list[str]:
    if isinstance(parsed, spec.ForceSpec):
        return [n.label or n.id for n in parsed.nodes]
    return [spec.node_label(n) for n in parsed.nodes]


@pytest.mark.parametrize("dtype", ALL_TYPES)
@pytest.mark.parametrize("kind", [0, 1], ids=["example", "template"])
def test_every_shipped_sample_renders_readable_text(dtype: str, kind: int) -> None:
    """A valid but empty source draws a blank canvas and the catalog still looks healthy."""
    source = SAMPLES[dtype][kind]
    parsed = spec.parse(dtype, source)
    shown = svg_text_of(D3Renderer().render(dtype, source, "svg").content)
    for label in labels_of(parsed):
        assert label in shown, (dtype, label)
    assert (
        D3Renderer()
        .render(dtype, source, "html")
        .content.startswith(b"<!doctype html>")
    )


DOC = D3_SRC.parents[2].parent / "docs/plugins/d3.md"


def documented_sources() -> list[tuple[str, str]]:
    found = re.findall(
        r'^( *)```json title="(d3_\w+)"\n(.*?)\n\1```',
        DOC.read_text(encoding="utf-8"),
        re.DOTALL | re.MULTILINE,
    )
    return [(dtype, textwrap.dedent(body)) for _indent, dtype, body in found]


def test_the_docs_have_examples_for_every_provider_and_type() -> None:
    sources = documented_sources()
    assert {dtype for dtype, _ in sources} == set(ALL_TYPES)
    providers = {json.loads(body).get("provider") for _, body in sources}
    assert {"aws", "azure", "gcp", "kubernetes"} <= providers


@pytest.mark.parametrize(
    ("dtype", "source"),
    documented_sources(),
    ids=lambda v: v if v.startswith("d3_") else json.loads(v).get("title", "untitled"),
)
def test_every_documented_example_is_valid_and_renders_cleanly(
    dtype: str, source: str
) -> None:
    parsed = spec.parse(dtype, source)
    if isinstance(parsed, spec.ArchSpec):
        assert_layout_is_sound(build_layout(dtype, source), parsed)
    renderer = D3Renderer()
    shown = svg_text_of(renderer.render(dtype, source, "svg").content)
    assert all(label in shown for label in labels_of(parsed))
    assert renderer.render(dtype, source, "html").content.startswith(b"<!doctype html>")


def section(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


def test_the_documented_reference_tables_match_the_code() -> None:
    docs = DOC.read_text(encoding="utf-8")

    services = section(docs, "### Services", "### Icon kinds")
    documented = set(re.findall(r"`([a-z]+:[a-z0-9]+)`", services)) - {
        "provider:service"
    }  # the prose placeholder
    assert documented == set(SERVICES)

    from uml_mcp_plugin_d3.icons import KIND_CATEGORY
    from uml_mcp_plugin_d3.theme import CATEGORIES, CATEGORY_LABELS

    kinds = section(docs, "### Icon kinds", "### Categories")
    assert set(re.findall(r"`([a-z]+)`", kinds)) - {"kind"} == set(KINDS)

    table = section(docs, "### Categories", "### Logos")
    documented_categories = {
        name: (label, set(re.findall(r"`(\w+)`", cell)))
        for name, label, cell in re.findall(
            r"^\| `(\w+)` \| ([^|]+?) \| ([^|]+) \|$", table, re.MULTILINE
        )
        if name in CATEGORIES
    }
    assert documented_categories == {
        name: (
            CATEGORY_LABELS[name],
            {k for k, v in KIND_CATEGORY.items() if v == name},
        )
        for name in CATEGORIES
    }

    rows = re.findall(
        r"^\| `(\w+)` \| ([^|]+?) \| `(#[0-9A-Fa-f]{6})` \|$",
        section(docs, "### Providers", "### Services"),
        re.MULTILINE,
    )
    assert {key: (name, accent) for key, name, accent in rows} == {
        key: (p.name, p.accent) for key, p in PROVIDERS.items()
    }

    group_row = next(
        line for line in docs.splitlines() if line.startswith("| `type` | group |")
    )
    assert all(f"`{t}`" in group_row for t in spec._GROUP_TYPES)

    limits = section(docs, "| Limit | Value |", "The diagram source comes")
    for label, value in (
        ("Nodes", spec.MAX_NODES),
        ("Links", spec.MAX_LINKS),
        ("Groups", spec.MAX_GROUPS),
        ("Ports", f"{spec.MAX_PORTS} inputs and {spec.MAX_PORTS} outputs per node"),
        ("Label length", f"{spec.MAX_LABEL} characters"),
    ):
        assert re.search(rf"^\| {label} \| {value}\b", limits, re.MULTILINE), label
    assert (
        f"D3 {html.D3_VERSION}" in docs
        and f"d3@{html.D3_VERSION}" not in docs.split("## Settings")[0]
    )


def test_plugin_tools_can_document_a_lint_exception(d3_plugin) -> None:
    from mcp_core.tools.tool_decorator import get_tool_registry

    d3_plugin()
    meta = get_tool_registry()["d3_catalog"]
    assert meta["lint_ignore"] == {
        "tool-no-required": "the only argument is an optional filter"
    }


# ------------------------------------------------------------ arrow label placement
def test_a_label_goes_on_the_longest_run_that_fits() -> None:
    corners = [
        (0, 0),
        (200, 0),
        (200, 100),
        (260, 100),
    ]  # runs of 200, 100 and 60 (head)
    assert router.label_point(corners, 40) == (100, 0)


def test_a_label_stays_off_the_arrowhead_unless_nothing_else_fits() -> None:
    assert router.label_point([(0, 0), (60, 0), (60, 200)], 40) == (
        60,
        100,
    )  # head run fits
    assert router.label_point([(0, 0), (200, 0), (200, 60)], 40) == (
        100,
        0,
    )  # body fits: skip head
    assert router.label_point([(0, 0), (30, 0), (30, 20)], 100) == (
        15,
        0,
    )  # nothing fits
    assert router.label_point([(5, 5)], 40) == (5, 5)


def test_equally_long_runs_put_the_label_nearest_the_source() -> None:
    assert router.label_point([(0, 0), (100, 0), (100, 100), (200, 100)], 20) == (50, 0)


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node to run router.js")
def test_javascript_label_placement_matches_python(tmp_path: Path) -> None:
    rng = random.Random(5)
    cases: list[dict[str, Any]] = []
    for _ in range(120):
        points = [(rng.randrange(0, 400, 10), rng.randrange(0, 400, 10))]
        for _ in range(rng.randint(1, 6)):
            x, y = points[-1]
            points.append(
                (rng.randrange(0, 400, 10), y)
                if len(points) % 2
                else (x, rng.randrange(0, 400, 10))
            )
        cases.append({"points": points, "width": rng.randrange(10, 200, 5)})
    runner = tmp_path / "labels.js"
    runner.write_text(
        "const R = require(process.argv[2]);"
        "const cases = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
        "process.stdout.write(JSON.stringify(cases.map(c => R.labelPoint(c.points, c.width))));",
        encoding="utf-8",
    )
    done = subprocess.run(
        ["node", str(runner), str(D3_SRC / "uml_mcp_plugin_d3/assets/router.js")],
        input=json.dumps(cases),
        capture_output=True,
        text=True,
        check=True,
    )
    for case, js_point in zip(cases, json.loads(done.stdout), strict=True):
        py = router.label_point([tuple(p) for p in case["points"]], case["width"])
        assert list(py) == js_point, case


# ------------------------------------------------------------- straight arrows
def corners(points) -> int:
    return max(0, len(points) - 2)


def sample_edges(dtype: str) -> dict[str, list]:
    arranged = build_layout(dtype, SAMPLES[dtype][0])
    return {f"{e.source}->{e.target}": e.points for e in arranged.edges}


def test_a_chain_of_boxes_is_joined_by_straight_arrows() -> None:
    """Boxes in a lane line up on the row their arrows use, so the chain is one line."""
    routes = sample_edges("d3_architecture")
    for name in ("users->cdn", "cdn->api", "api->orders", "orders->db", "queue->mail"):
        assert corners(routes[name]) == 0, name
    topology = sample_edges("d3_topology")
    for name in ("client->fw", "fw->lb", "lb->web1", "web1->cache", "web2->db"):
        assert corners(topology[name]) == 0, name


def random_arch_layouts(count: int, direction: str = "LR") -> list[layout.Layout]:
    return [
        layout.build(
            spec.parse_arch("d3_architecture", source), "d3_architecture", direction
        )
        for source in valid_random_specs(count)
    ]


def test_arrows_are_straighter_than_the_previous_layout() -> None:
    """Over random diagrams the share of straight arrows and the corners per arrow improved.

    The earlier layout (equal slots, centred boxes, cheap turns) had 5% straight arrows
    and 2.39 corners per arrow on these same specs.
    """
    arrows = [e for lay in random_arch_layouts(60) for e in lay.edges]
    straight = sum(corners(e.points) == 0 for e in arrows) / len(arrows)
    mean = sum(corners(e.points) for e in arrows) / len(arrows)
    assert straight >= 0.15 and mean <= 2.3, (straight, mean)


def test_an_arrow_end_slides_to_meet_the_other_box_head_on() -> None:
    """Two boxes whose rows overlap get a straight arrow, whatever their heights."""
    code = json.dumps(
        {
            "nodes": [
                {"id": "a", "kind": "server"},
                {
                    "id": "b",
                    "kind": "database",
                    "outputs": ["x", "y", "z"],
                    "inputs": ["i"],
                },
            ],
            "links": [{"from": "a", "to": "b"}],
        }
    )
    arranged = layout.build(
        spec.parse_arch("d3_architecture", code), "d3_architecture", "LR"
    )
    edge = arranged.edges[0]
    assert corners(edge.points) == 0
    assert edge.points[0][1] == edge.points[-1][1]


def test_parallel_arrows_to_one_side_keep_their_distance() -> None:
    nodes = [{"id": "hub", "kind": "gateway"}] + [
        {"id": f"s{i}", "kind": "server"} for i in range(4)
    ]
    code = json.dumps(
        {"nodes": nodes, "links": [{"from": "hub", "to": f"s{i}"} for i in range(4)]}
    )
    arranged = layout.build(
        spec.parse_arch("d3_architecture", code), "d3_architecture", "LR"
    )
    starts = sorted(e.points[0][1] for e in arranged.edges)
    assert all(b - a >= layout.SLOT_SPACING for a, b in itertools.pairwise(starts)), (
        starts
    )


# ------------------------------------------------------------------ arrow labels
def labelled_layouts() -> list[layout.Layout]:
    return [build_layout(d, SAMPLES[d][0]) for d in ARCH_TYPES] + random_arch_layouts(
        30
    )


def on_polyline(point, points, slack=0.01) -> bool:
    for (x1, y1), (x2, y2) in itertools.pairwise(points):
        if (
            min(x1, x2) - slack <= point[0] <= max(x1, x2) + slack
            and min(y1, y2) - slack <= point[1] <= max(y1, y2) + slack
        ):
            return True
    return False


def test_every_label_sits_on_its_own_arrow() -> None:
    labelled = 0
    for arranged in labelled_layouts():
        for e in arranged.edges:
            if e.label:
                labelled += 1
                assert on_polyline(e.label_at, e.points), e.label
    assert labelled >= 30


def test_labels_in_the_samples_clear_every_box() -> None:
    """The shipped samples' labels sit in open space, not on a box (the halo breaks the line)."""
    for dtype in ARCH_TYPES:
        arranged = build_layout(dtype, SAMPLES[dtype][0])
        for e in arranged.edges:
            if not e.label:
                continue
            x, y = e.label_at
            half = e.label_width / 2
            box = (x - half, y - 8, e.label_width, 16)
            for b in arranged.boxes:
                assert not rect_overlap(box, b.rect()), (dtype, e.label, b.id)


# ------------------------------------------------------------ categories and icons
def test_every_kind_has_a_category_and_every_category_is_used() -> None:
    from uml_mcp_plugin_d3.icons import KIND_CATEGORY
    from uml_mcp_plugin_d3.theme import CATEGORIES

    assert set(KIND_CATEGORY) == set(KINDS)
    assert set(KIND_CATEGORY.values()) == set(CATEGORIES)
    for dtype, (kind, _name) in ((k, v) for k, v in SERVICES.items()):
        assert kind in KINDS, dtype


def test_software_services_have_a_brand_tile_and_the_other_way_round() -> None:
    from uml_mcp_plugin_d3.icons import BRANDS

    tech = {key.split(":", 1)[1] for key in SERVICES if key.startswith("tech:")}
    assert tech == set(BRANDS)
    for mono, color in BRANDS.values():
        assert 1 <= len(mono) <= 2 and color.startswith("#") and len(color) == 7


def test_a_bare_software_name_works_under_any_provider_and_kinds_win() -> None:
    redis = resolve_service("redis", None, "aws")
    assert (redis.provider, redis.kind, redis.mono) == ("tech", "cache", "Rd")
    assert resolve_service("tech:postgres", None, "generic").name == "PostgreSQL"
    assert (
        resolve_service("aws:redis", None, "aws").provider == "aws"
    )  # no such AWS service
    assert (
        resolve_service("kubernetes", None, "kubernetes").kind == "kubernetes"
    )  # the glyph
    assert resolve_service("database", None, "aws").mono is None


def test_a_node_may_override_its_category() -> None:
    code = json.dumps(
        {"nodes": [{"id": "a", "kind": "server", "category": "security"}]}
    )
    arranged = layout.build(
        spec.parse_arch("d3_architecture", code), "d3_architecture", "LR"
    )
    assert arranged.boxes[0].category == "security"
    assert arranged.legend == [("security", 1)]
    assert any(
        "category" in p
        for p in problems(
            "d3_architecture", json.dumps({"nodes": [{"id": "a", "category": "pink"}]})
        )
    )


def test_only_nodes_that_name_a_service_wear_a_provider_badge() -> None:
    svg = (
        D3Renderer()
        .render("d3_architecture", SAMPLES["d3_architecture"][0], "svg")
        .content.decode()
    )
    named = [n for n in example("d3_architecture")["nodes"] if n.get("service")]
    assert (
        svg.count('class="t-badge prov-aws"') == len(named) == 6
    )  # the user box names none
    assert 'data-id="users"' in svg


def test_software_nodes_get_a_monogram_tile_and_cloud_nodes_a_glyph() -> None:
    code = json.dumps(
        {
            "nodes": [
                {"id": "db", "service": "postgres"},
                {"id": "q", "service": "aws:sqs"},
            ]
        }
    )
    svg = D3Renderer().render("d3_architecture", code, "svg").content.decode()
    assert (
        '<text class="t-mono"' in svg
        and ">Pg</text>" in svg
        and 'fill="#336791"' in svg
    )
    assert svg.count('class="glyph"') == 1


def test_the_legend_counts_what_is_drawn() -> None:
    arranged = build_layout("d3_architecture", SAMPLES["d3_architecture"][0])
    counts = {}
    for b in arranged.boxes:
        counts[b.category] = counts.get(b.category, 0) + 1
    assert dict(arranged.legend) == counts and sum(counts.values()) == len(
        arranged.boxes
    )
    svg = (
        D3Renderer()
        .render("d3_architecture", SAMPLES["d3_architecture"][0], "svg")
        .content.decode()
    )
    assert svg.count('class="swatch"') == len(counts) and "Legend" in svg


# -------------------------------------------------------------------------- logos
SVG_LOGO = (
    "data:image/svg+xml;base64,"
    + base64.b64encode(
        b'<svg xmlns="http://www.w3.org/2000/svg"><circle r="4"/></svg>'
    ).decode()
)


def node_with_logo(logo: str) -> str:
    return json.dumps({"nodes": [{"id": "a", "label": "Acme", "logo": logo}]})


def test_a_node_can_carry_its_own_logo() -> None:
    for logo in (PNG_1PX, SVG_LOGO):
        spec.parse_arch("d3_architecture", node_with_logo(logo))
    svg = (
        D3Renderer()
        .render("d3_architecture", node_with_logo(PNG_1PX), "svg")
        .content.decode()
    )
    assert '<image class="logo" href="data:image/png;base64,' in svg
    ET.fromstring(svg)  # still well formed


@pytest.mark.parametrize(
    ("logo", "expected"),
    [
        ("https://example.com/logo.png", "use a data URI"),
        ("data:text/html;base64,PGI+", "use a data URI"),
        ("data:image/gif;base64,R0lGOD", "use a data URI"),
        ("data:image/png;base64,@@@@", "use a data URI"),
        ("data:image/png;base64,abc", "not valid"),
        (
            "data:image/svg+xml;base64,"
            + base64.b64encode(b"<svg><script>alert(1)</script></svg>").decode(),
            "may not contain scripts",
        ),
        (
            "data:image/svg+xml;base64,"
            + base64.b64encode(b"<svg><foreignObject/></svg>").decode(),
            "may not contain scripts",
        ),
    ],
)
def test_a_logo_must_be_a_small_safe_data_uri(logo: str, expected: str) -> None:
    assert any(
        expected in p for p in problems("d3_architecture", node_with_logo(logo))
    ), logo


def test_logos_are_bounded() -> None:
    too_big = "data:image/png;base64," + "A" * spec.MAX_LOGO
    assert any(
        "at most" in p or "String should have at most" in p
        for p in problems("d3_architecture", node_with_logo(too_big))
    )
    many = json.dumps(
        {"nodes": [{"id": f"n{i}", "logo": PNG_1PX} for i in range(spec.MAX_LOGOS + 1)]}
    )
    assert any(
        f"at most {spec.MAX_LOGOS} may carry a logo" in p
        for p in problems("d3_architecture", many)
    )


# --------------------------------------------------------------------- themes
def contrast(a: str, b: str) -> float:
    def luminance(hex_color: str) -> float:
        channels = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        lin = [
            c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
            for c in channels
        ]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_both_palettes_define_every_category_and_keep_text_readable() -> None:
    from uml_mcp_plugin_d3.theme import CATEGORIES, DARK, LIGHT

    for palette in (LIGHT, DARK):
        for category in CATEGORIES:
            assert f"{category}-fill" in palette and f"{category}-stroke" in palette
        assert contrast(palette["text"], palette["panel"]) >= 7
        assert contrast(palette["muted"], palette["panel"]) >= 4.5
        for category in CATEGORIES:  # an outline must stand out from the panel
            assert contrast(palette[f"{category}-stroke"], palette["panel"]) >= 3, (
                category
            )


@pytest.mark.parametrize("theme", ["light", "dark", "auto"])
def test_static_theme_is_resolved_and_browser_styles_support_all_themes(
    theme: str,
) -> None:
    from uml_mcp_plugin_d3.theme import diagram_css, static_diagram_css

    code = json.dumps({**example("d3_architecture"), "theme": theme})
    svg = D3Renderer().render("d3_architecture", code, "svg").content.decode()
    root = parse_svg(svg)
    assert f"d3d arch {theme}" == root.attrib["class"]
    css = diagram_css()
    assert (
        ".d3d.dark{" in css
        and "prefers-color-scheme:dark" in css
        and ".d3d.auto" in css
    )
    assert (
        "<style>" in svg
        and static_diagram_css("dark" if theme == "dark" else "light") in svg
    )  # a standalone SVG carries its own stylesheet


def test_the_page_carries_the_stylesheet_once_not_inside_the_svg() -> None:
    text = page("d3_architecture")
    inline_svg = text[text.index("<svg") : text.index("</svg>")]
    assert "<style" not in inline_svg
    assert (
        text.count('id="diagram-css"') == 1
        and 'class="light"' in text.split("<head>")[0]
    )


def test_dashed_and_primary_arrows_get_their_own_colour_and_head() -> None:
    code = arch(links=[{"from": "a", "to": "b", "style": "dashed"}])
    svg = D3Renderer().render("d3_architecture", code, "svg").content.decode()
    assert 'class="edge dashed"' in svg and 'marker-end="url(#arrow-dashed)"' in svg
    code = arch(links=[{"from": "a", "to": "b", "style": "primary"}])
    svg = D3Renderer().render("d3_architecture", code, "svg").content.decode()
    assert 'class="edge primary"' in svg and 'marker-end="url(#arrow-primary)"' in svg


def test_group_titles_sit_on_their_border_and_borders_follow_the_type() -> None:
    svg = (
        D3Renderer()
        .render("d3_architecture", SAMPLES["d3_architecture"][0], "svg")
        .content.decode()
    )
    assert 'class="group-box dashed"' in svg  # the region
    assert 'class="group g-cloud"' in svg and 'class="group g-backend"' in svg
    assert svg.count('class="t-group"') == 3


# ---------------------------------------------------------------------- force look
def test_the_force_graph_shares_the_look_and_counts_its_groups() -> None:
    model = force.build(spec.parse_force(SAMPLES["d3_force"][0]))
    assert [item["name"] for item in model.legend] == [
        "frontend",
        "edge",
        "backend",
        "data",
    ]
    assert sum(item["count"] for item in model.legend) == len(model.nodes)
    assert {n["category"] for n in model.nodes} <= {
        "frontend",
        "backend",
        "database",
        "cloud",
        "security",
        "messagebus",
        "external",
    }
    svg = (
        D3Renderer().render("d3_force", SAMPLES["d3_force"][0], "svg").content.decode()
    )
    assert "d3d force light" in svg and svg.count('class="f-mask"') == len(model.nodes)
    assert "Legend" in svg and 'class="swatch"' in svg


def test_the_documented_straight_arrow_count_is_true() -> None:
    """docs/plugins/d3.md says 10 of the 14 arrows in the shipped examples are straight."""
    routes = [r for d in ARCH_TYPES for r in sample_edges(d).values()]
    assert len(routes) == 14 and sum(corners(r) == 0 for r in routes) >= 10
    assert "10 of the 14 arrows" in DOC.read_text(encoding="utf-8")


# -------------------------------------------------- labels keep clear of the boxes
def test_a_label_moves_along_the_run_to_clear_a_neighbouring_box() -> None:
    """A wide label centred on a vertical run beside a box would overlap it, so it slides."""
    run = [(100, 0), (100, 300), (400, 300)]
    beside = (108, 130, 140, 40)  # right next to the middle of the vertical run
    assert router.label_point(run, 60, []) == (100, 150)
    x, y = router.label_point(run, 60, [beside])
    assert (x, y) == (100, 75) and not rect_overlap((x - 30, y - 8, 60, 16), beside)


def test_a_label_falls_back_to_the_best_run_when_every_spot_is_blocked() -> None:
    run = [(0, 0), (300, 0), (300, 100)]
    everything = (-50, -50, 500, 300)
    assert router.label_point(run, 60, [everything]) == router.label_point(run, 60, [])


def random_polyline_and_boxes(rng: random.Random) -> dict[str, Any]:
    points = [(rng.randrange(0, 400, 10), rng.randrange(0, 400, 10))]
    for step in range(rng.randint(1, 6)):
        x, y = points[-1]
        points.append(
            (rng.randrange(0, 400, 10), y)
            if step % 2 == 0
            else (x, rng.randrange(0, 400, 10))
        )
    boxes = [
        [
            rng.randrange(0, 400, 10),
            rng.randrange(0, 400, 10),
            rng.randrange(40, 160, 10),
            rng.randrange(30, 100, 10),
        ]
        for _ in range(rng.randint(0, 5))
    ]
    return {"points": points, "width": rng.randrange(10, 200, 5), "boxes": boxes}


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node to run router.js")
def test_javascript_label_placement_with_boxes_matches_python(tmp_path: Path) -> None:
    rng = random.Random(9)
    cases = [random_polyline_and_boxes(rng) for _ in range(200)]
    runner = tmp_path / "labels_boxes.js"
    runner.write_text(
        "const R = require(process.argv[2]);"
        "const cases = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
        "process.stdout.write(JSON.stringify(cases.map(c => R.labelPoint(c.points, c.width, c.boxes))));",
        encoding="utf-8",
    )
    done = subprocess.run(
        ["node", str(runner), str(D3_SRC / "uml_mcp_plugin_d3/assets/router.js")],
        input=json.dumps(cases),
        capture_output=True,
        text=True,
        check=True,
    )
    for case, js_point in zip(cases, json.loads(done.stdout), strict=True):
        py = router.label_point(
            [tuple(p) for p in case["points"]],
            case["width"],
            [tuple(b) for b in case["boxes"]],
        )
        assert list(py) == js_point, case


def test_a_label_in_a_random_diagram_avoids_boxes_whenever_it_can() -> None:
    """Of all labels in random diagrams, nearly all clear every box (a few are boxed in)."""
    clear = total = 0
    for arranged in random_arch_layouts(40):
        for e in arranged.edges:
            if not e.label:
                continue
            total += 1
            x, y = e.label_at
            half = e.label_width / 2
            box = (x - half, y - 8, e.label_width, 16)
            clear += not any(rect_overlap(box, b.rect()) for b in arranged.boxes)
    assert total > 100 and clear / total >= 0.97, (clear, total)
