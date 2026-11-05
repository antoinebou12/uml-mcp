"""D3 routing quality: A* keeps arrows out of boxes and spreads parallel arrows apart."""

from __future__ import annotations

import itertools
import json

import pytest
from uml_mcp_plugin_d3 import layout, router, spec
from uml_mcp_plugin_d3.samples import SAMPLES

from tests.fixtures_d3 import D3_SRC  # noqa: F401  (puts the plugin on sys.path)

#: Ten services, each linked to the next one, two and three along, and five along:
#: a busy diagram where arrows must share corridors.
DENSE = json.dumps(
    {
        "title": "Dense",
        "nodes": [
            {"id": f"n{i}", "label": f"Service {i}", "kind": "server"}
            for i in range(10)
        ],
        "links": [
            {"from": f"n{i}", "to": f"n{j}", "label": f"e{i}{j}"}
            for i in range(10)
            for j in range(10)
            if i < j and (j - i) in (1, 2, 3, 5)
        ],
    }
)


def _segments(points):
    return [(a, b) for a, b in itertools.pairwise(points) if a != b]


def quality(dtype: str, source: str) -> dict[str, float]:
    """Overlapping and near-parallel run length, crossings, box hits and label clashes."""
    arranged = layout.build(
        spec.parse_arch(dtype, source), dtype, "TB" if dtype == "d3_topology" else "LR"
    )
    overlap = near = cross = 0.0
    for e1, e2 in itertools.combinations(arranged.edges, 2):
        for a, b in _segments(e1.points):
            for c, d in _segments(e2.points):
                h1, h2 = a[1] == b[1], c[1] == d[1]
                if h1 == h2:
                    axis, other = (0, 1) if h1 else (1, 0)
                    lo = max(min(a[axis], b[axis]), min(c[axis], d[axis]))
                    hi = min(max(a[axis], b[axis]), max(c[axis], d[axis]))
                    gap = abs(a[other] - c[other])
                    if hi > lo and gap < 1:
                        overlap += hi - lo
                    elif hi > lo and gap <= router.STEP:
                        near += hi - lo
                else:
                    (p, q), (r, s) = ((a, b), (c, d)) if h1 else ((c, d), (a, b))
                    x, y = r[0], p[1]
                    if min(p[0], q[0]) < x < max(p[0], q[0]) and min(
                        r[1], s[1]
                    ) < y < max(r[1], s[1]):
                        cross += 1
    through = 0
    for e in arranged.edges:
        for a, b in _segments(e.points):
            for box in arranged.boxes:
                if box.id in (e.source, e.target):
                    continue
                x, y, w, h = box.rect()
                if (
                    min(a[0], b[0]) < x + w
                    and max(a[0], b[0]) > x
                    and min(a[1], b[1]) < y + h
                    and max(a[1], b[1]) > y
                ):
                    through += 1
    labels = [
        (e.label_at[0] - e.label_width / 2, e.label_at[1] - 8, e.label_width, 16)
        for e in arranged.edges
        if e.label
    ]
    clashes = sum(
        1
        for p, q in itertools.combinations(labels, 2)
        if p[0] < q[0] + q[2]
        and q[0] < p[0] + p[2]
        and p[1] < q[1] + q[3]
        and q[1] < p[1] + p[3]
    )
    return {
        "overlap": overlap,
        "near": near,
        "cross": cross,
        "through": through,
        "labels": clashes,
    }


@pytest.mark.parametrize("dtype", ["d3_architecture", "d3_topology"])
def test_samples_route_cleanly(dtype):
    q = quality(dtype, SAMPLES[dtype][0])
    assert q["through"] == 0 and q["labels"] == 0 and q["cross"] == 0
    assert q["overlap"] <= 10


def test_dense_graph_spreads_parallel_arrows_apart():
    """The lane-spacing cost keeps parallel arrows a lane apart where there is room.

    Without it this graph had about 5,400 px of arrows running one lane apart; with it,
    about 630 px. The bounds leave room for small layout changes but catch a regression.
    """
    q = quality("d3_architecture", DENSE)
    assert q["through"] == 0  # A* never routes through a box
    assert q["labels"] == 0
    assert q["near"] < 1500
    assert q["overlap"] <= 60
    assert q["cross"] <= 50


def test_without_the_lane_cost_the_dense_graph_bunches_up(monkeypatch):
    """Guards the metric itself: turning the cost off brings the bunching back."""
    monkeypatch.setattr(router, "NEAR", 0)
    assert quality("d3_architecture", DENSE)["near"] > 3000
