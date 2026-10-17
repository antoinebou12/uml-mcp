"""Force-directed graph: a deterministic layout, and the static SVG snapshot of it.

The browser runs the real ``d3-force`` simulation. It starts from the positions computed
here, so the page opens near its settled shape instead of jittering from a spiral, and the
``svg`` output is the same picture. Large graphs skip the simulation (it is quadratic) and
use a ring layout, grouped by ``group``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from html import escape

from .layout import mono_width
from .spec import ForceSpec
from .svg import canvas_svg, root_open
from .theme import CATEGORIES

#: above this many nodes the quadratic simulation is replaced by a ring layout
SIMULATE_UP_TO = 150
MARGIN = 70
LEGEND_W = 200


@dataclass
class ForceModel:
    nodes: list[dict]
    links: list[dict]
    legend: list[dict]
    width: float
    height: float


def _radius(size: float) -> float:
    return 6 + 4 * size


def _simulate(
    n: int, links: list[tuple[int, int]], radii: list[float], spec: ForceSpec
) -> list[list[float]]:
    # d3's phyllotaxis start, then the same link / many-body / centre / collide forces
    pos = [
        [
            10 * math.sqrt(0.5 + i) * math.cos(i * math.pi * (3 - math.sqrt(5))),
            10 * math.sqrt(0.5 + i) * math.sin(i * math.pi * (3 - math.sqrt(5))),
        ]
        for i in range(n)
    ]
    vel = [[0.0, 0.0] for _ in range(n)]
    degree = [0] * n
    for a, b in links:
        degree[a] += 1
        degree[b] += 1
    ticks = min(300, max(60, 1_200_000 // max(1, n * (n - 1) // 2)))
    alpha, alpha_min = 1.0, 0.001
    decay = 1 - alpha_min ** (1 / ticks)
    for _ in range(ticks):
        alpha += (0 - alpha) * decay
        for a, b in links:
            dx = pos[b][0] + vel[b][0] - pos[a][0] - vel[a][0] or 1e-6
            dy = pos[b][1] + vel[b][1] - pos[a][1] - vel[a][1] or 1e-6
            dist = math.hypot(dx, dy)
            pull = (dist - spec.distance) / dist * alpha / min(degree[a], degree[b])
            dx, dy = dx * pull, dy * pull
            bias = degree[a] / (degree[a] + degree[b])
            vel[b][0] -= dx * bias
            vel[b][1] -= dy * bias
            vel[a][0] += dx * (1 - bias)
            vel[a][1] += dy * (1 - bias)
        for i in range(n):
            for j in range(i + 1, n):
                dx, dy = pos[j][0] - pos[i][0], pos[j][1] - pos[i][1]
                d2 = dx * dx + dy * dy
                if d2 < 1:
                    d2 = math.sqrt(d2) if d2 else 1.0
                w = spec.charge * alpha / d2
                vel[i][0] += dx * w
                vel[i][1] += dy * w
                vel[j][0] -= dx * w
                vel[j][1] -= dy * w
                gap = radii[i] + radii[j] + 6
                if d2 < gap * gap:  # keep circles apart (the collision force)
                    d = math.sqrt(d2) or 1e-6
                    push = (gap - d) / d * 0.5
                    vel[i][0] -= dx * push
                    vel[i][1] -= dy * push
                    vel[j][0] += dx * push
                    vel[j][1] += dy * push
        mx = sum(p[0] for p in pos) / n
        my = sum(p[1] for p in pos) / n
        for i in range(n):
            vel[i][0] *= 0.6
            vel[i][1] *= 0.6
            pos[i][0] += vel[i][0] - mx
            pos[i][1] += vel[i][1] - my
    return pos


def _ring(n: int, order: list[int]) -> list[list[float]]:
    radius = max(160.0, n * 11 / (2 * math.pi))
    pos = [[0.0, 0.0] for _ in range(n)]
    for rank, i in enumerate(order):
        angle = 2 * math.pi * rank / n
        pos[i] = [radius * math.cos(angle), radius * math.sin(angle)]
    return pos


def build(spec: ForceSpec) -> ForceModel:
    index = {node.id: i for i, node in enumerate(spec.nodes)}
    n = len(spec.nodes)
    pairs = [(index[link.source], index[link.target]) for link in spec.links]
    radii = [_radius(node.size) for node in spec.nodes]

    groups: list[str] = []
    for node in spec.nodes:
        if node.group and node.group not in groups:
            groups.append(node.group)
    category = {g: CATEGORIES[i % len(CATEGORIES)] for i, g in enumerate(groups)}
    counts = {g: 0 for g in groups}
    for node in spec.nodes:
        if node.group:
            counts[node.group] += 1

    if n == 1:
        pos = [[0.0, 0.0]]
    elif n <= SIMULATE_UP_TO:
        pos = _simulate(n, pairs, radii, spec)
    else:
        order = sorted(
            range(n), key=lambda i: (spec.nodes[i].group or "", spec.nodes[i].id)
        )
        pos = _ring(n, order)

    label_w = [mono_width(node.label or node.id, 11) for node in spec.nodes]
    x1 = min(p[0] - max(r, w / 2) for p, r, w in zip(pos, radii, label_w, strict=True))
    y1 = min(p[1] - r for p, r in zip(pos, radii, strict=True))
    x2 = max(p[0] + max(r, w / 2) for p, r, w in zip(pos, radii, label_w, strict=True))
    y2 = max(p[1] + r + 18 for p, r in zip(pos, radii, strict=True))
    top = MARGIN + (30 if spec.title else 0)
    dx, dy = MARGIN - x1, top - y1
    nodes = [
        {
            "id": node.id,
            "label": node.label or node.id,
            "group": node.group or "",
            "category": category.get(node.group or "", "external"),
            "r": round(radii[i], 1),
            "note": node.note or "",
            "x": round(pos[i][0] + dx, 1),
            "y": round(pos[i][1] + dy, 1),
        }
        for i, node in enumerate(spec.nodes)
    ]
    links = [
        {
            "source": link.source,
            "target": link.target,
            "label": link.label or "",
            "value": link.value,
        }
        for link in spec.links
    ]
    legend = [{"name": g, "category": category[g], "count": counts[g]} for g in groups]
    legend_w = LEGEND_W if legend else 0  # its own column, so it never covers a node
    return ForceModel(
        nodes, links, legend, x2 - x1 + 2 * MARGIN + legend_w, y2 - y1 + MARGIN + top
    )


def _fmt(value: float) -> str:
    text = f"{value:.1f}"
    return text.removesuffix(".0")


def force_svg(model: ForceModel, spec: ForceSpec, *, page: bool = False) -> str:
    """The graph as an ``<svg>`` element (the ``svg`` output and the page's no-script view)."""
    by_id = {node["id"]: node for node in model.nodes}
    parts = [
        root_open(
            dom_id="graph",
            classes=f"d3d force {spec.theme}",
            label=spec.title or "Force-directed graph",
            width=model.width,
            height=model.height,
            page=page,
        ),
        canvas_svg(model.width, model.height, page=page),
        '<g class="viewport">',
    ]
    if spec.title and not page:  # the page already shows the title in its header
        parts.append(
            f'<text class="t-heading" x="40" y="38">{escape(spec.title)}</text>'
        )
    parts.append('<g class="links">')
    for link in model.links:
        a, b = by_id[link["source"]], by_id[link["target"]]
        dxl, dyl = b["x"] - a["x"], b["y"] - a["y"]
        dist = math.hypot(dxl, dyl) or 1.0
        # stop at the circle's edge so an arrowhead is not hidden under the node
        tx = b["x"] - dxl / dist * (b["r"] + (3 if spec.directed else 0))
        ty = b["y"] - dyl / dist * (b["r"] + (3 if spec.directed else 0))
        marker = ' marker-end="url(#arrow)"' if spec.directed else ""
        parts.append(
            f'<line class="f-link" data-source="{escape(link["source"], quote=True)}" '
            f'data-target="{escape(link["target"], quote=True)}" x1="{_fmt(a["x"])}" '
            f'y1="{_fmt(a["y"])}" x2="{_fmt(tx)}" y2="{_fmt(ty)}" '
            f'stroke-width="{_fmt(1 + min(float(link["value"]), 6) * 0.5)}"{marker}/>'
        )
    parts.append("</g>")
    parts.append('<g class="link-labels">')
    for link in model.links:
        if not link["label"]:
            continue
        a, b = by_id[link["source"]], by_id[link["target"]]
        parts.append(
            f'<text class="t-llabel" x="{_fmt((a["x"] + b["x"]) / 2)}" '
            f'y="{_fmt((a["y"] + b["y"]) / 2 - 4)}">{escape(link["label"])}</text>'
        )
    parts.append("</g>")
    parts.append('<g class="nodes">')
    for node in model.nodes:
        parts.append(
            f'<g class="node cat-{node["category"]}" data-id="{escape(node["id"], quote=True)}">'
            f'<circle class="f-mask" cx="{_fmt(node["x"])}" cy="{_fmt(node["y"])}" '
            f'r="{_fmt(node["r"])}"/>'
            f'<circle class="f-node" cx="{_fmt(node["x"])}" cy="{_fmt(node["y"])}" '
            f'r="{_fmt(node["r"])}"/>'
            f'<text class="t-flabel" x="{_fmt(node["x"])}" y="{_fmt(node["y"] + node["r"] + 14)}">'
            f"{escape(node['label'])}</text></g>"
        )
    parts.append("</g>")
    if model.legend:
        left = model.width - LEGEND_W + 16
        parts.append(
            f'<g class="legend" transform="translate({_fmt(left)} 56)">'
            '<text class="t-legend-head" x="0" y="0">Legend</text>'
        )
        for i, item in enumerate(model.legend):
            y = 24 + i * 22
            name = item["name"]
            parts.append(
                f'<g class="cat-{item["category"]}"><circle class="swatch" cx="6" cy="{y - 4}" r="6"/>'
                f'<text class="t-legend" x="20" y="{y}">{escape(name)}</text>'
                f'<text class="t-count" x="{_fmt(20 + mono_width(name, 11) + 6)}" y="{y}">'
                f"{item['count']}</text></g>"
            )
        parts.append("</g>")
    parts.append("</g></svg>")
    return "".join(parts)
