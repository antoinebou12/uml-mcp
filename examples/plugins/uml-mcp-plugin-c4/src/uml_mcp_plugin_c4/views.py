"""Views of a C4 model and their layout.

A view is one level of the model: ``context`` (people and software systems), ``container:<id>``
(a system opened into its containers) or ``component:<id>`` (a container opened into its
components). Every view is laid out here, once, so the static SVG and the interactive page
draw exactly the same picture.

Relations are *lifted* to the view: an endpoint that is not visible is replaced by its
nearest visible ancestor, so a component-to-component relation shows as a line between their
containers when those are collapsed. Relations that land on the same pair are merged.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field

from .model import Element, Model

NODE_W = 230
COL_GAP = 80
ROW_GAP = 120
LR_GAP = 190  # between columns when the flow runs left to right
MARGIN = 40
TITLE_H = 64
BOUNDARY_PAD = 34
BOUNDARY_LABEL = 40
PERSON_HEAD = 44
MAX_PER_ROW = 5
NAME_SIZE = 15
DESC_SIZE = 12
LINE = 15


def wrap(text: str, size: float, width: float, max_lines: int, bold=False) -> list[str]:
    """Greedy word wrap with an average glyph width; the last line gets an ellipsis."""
    if not text:
        return []
    per_line = max(4, int(width / (size * (0.6 if bold else 0.53))))
    lines: list[str] = []
    current = ""
    for word in text.split():
        while len(word) > per_line:
            if current:
                lines.append(current)
                current = ""
            lines.append(word[: per_line - 1] + "-")
            word = word[per_line - 1 :]
        candidate = f"{current} {word}".strip()
        if len(candidate) <= per_line:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: per_line - 1].rstrip() + "…"
    return lines


def type_line(item: Element) -> str:
    """The C4 stereotype under a name: ``[Container: Java]``, ``[Software System]``..."""
    ext = "External " if item.external else ""
    if item.level == "person":
        return f"[{ext}Person]"
    if item.level == "system":
        return f"[{ext}Software System]"
    if item.level == "container":
        return f"[Container: {item.technology}]" if item.technology else "[Container]"
    return f"[Component: {item.technology}]" if item.technology else "[Component]"


def shape_of(item: Element) -> str:
    if item.level == "person":
        return "person"
    if item.level == "container" and item.kind in (
        "db",
        "queue",
        "storage",
        "function",
        "web",
    ):
        return item.kind
    return "box"


@dataclass
class Node:
    id: str
    x: float
    y: float
    w: float
    h: float
    shape: str
    name: list[str]
    type: str
    desc: list[str]
    drill: str | None = None

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2


@dataclass
class Edge:
    id: str
    source: str
    target: str
    label: str
    technology: str
    is_async: bool
    count: int
    members: list[int]
    path: str = ""
    label_lines: list[str] = field(default_factory=list)
    label_x: float = 0
    label_y: float = 0


@dataclass
class Boundary:
    id: str
    x: float
    y: float
    w: float
    h: float
    label: str
    type: str


@dataclass
class View:
    key: str
    level: str
    focus: str | None
    title: str
    crumbs: list[tuple[str, str]]
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    boundary: Boundary | None = None
    direction: str = "TB"
    width: float = 0
    height: float = 0


def view_key(model: Model, level: str, focus: str | None) -> str:
    return "context" if level == "context" or not focus else f"{level}:{focus}"


def drill_key(item: Element) -> str | None:
    if not item.children:
        return None
    return f"{'container' if item.level == 'system' else 'component'}:{item.id}"


def home_view(model: Model, element_id: str) -> str:
    """The view where ``element_id`` is drawn as a box."""
    item = model.elements[element_id]
    if item.level in ("person", "system"):
        return "context"
    return f"{'container' if item.level == 'container' else 'component'}:{item.parent}"


def all_views(model: Model, direction: str = "TB") -> dict[str, View]:
    views = {"context": build(model, "context", None, direction)}
    for item in model.elements.values():
        key = drill_key(item)
        if key:
            level, _, focus = key.partition(":")
            views[key] = build(model, level, focus, direction)
    return views


def best_direction(model: Model, level: str, focus: str | None) -> str:
    """For a static picture: the flow whose shape is closest to a 4:3 landscape page."""

    def misfit(v: View) -> float:
        return abs(math.log((v.width / max(v.height, 1.0)) / (4 / 3)))

    if model.direction in ("TB", "LR"):
        return model.direction
    return min(("TB", "LR"), key=lambda d: misfit(build(model, level, focus, d)))


# ---------------------------------------------------------------- which boxes, which lines


def _visible(
    model: Model, level: str, focus: str | None
) -> tuple[list[str], list[str]]:
    """(inside, outside candidates) for a view."""
    tops = [i for i in model.order if model.elements[i].level in ("person", "system")]
    if level == "context" or focus is None:
        return tops, []
    inside = list(model.elements[focus].children)
    if level == "container":
        outside = [i for i in tops if i != focus]
    else:
        system = model.elements[focus].parent
        assert system is not None
        siblings = [c for c in model.elements[system].children if c != focus]
        outside = [i for i in tops if i != system] + siblings
    return inside, outside


def _lift(model: Model, level, focus, inside, outside) -> tuple[list[Edge], set[str]]:
    shown = set(inside) | set(outside)
    merged: dict[tuple[str, str], Edge] = {}
    for index, rel in enumerate(model.relations):
        ends = []
        for end in (rel.source, rel.target):
            rep = next(
                (a for a in model.ancestors(end) if a in shown or a == focus), None
            )
            ends.append(rep)
        a, b = ends
        if a is None or b is None or a == b:
            continue
        if level != "context":
            if not (a in inside or b in inside or a == focus or b == focus):
                continue
            if a == focus and b == focus:
                continue
        edge = merged.get((a, b))
        if edge is None:
            edge = merged[(a, b)] = Edge(
                id=f"e{len(merged)}",
                source=a,
                target=b,
                label="",
                technology="",
                is_async=True,
                count=0,
                members=[],
            )
        edge.count += 1
        edge.members.append(index)
        edge.is_async = edge.is_async and rel.is_async
        labels = [x for x in edge.label.split("; ") if x]
        if rel.label and rel.label not in labels:
            labels.append(rel.label)
        edge.label = "; ".join(labels)
        techs = [x for x in edge.technology.split(", ") if x]
        if rel.technology and rel.technology not in techs:
            techs.append(rel.technology)
        edge.technology = ", ".join(techs)
    edges = list(merged.values())
    used = {e.source for e in edges} | {e.target for e in edges}
    return edges, used


# ---------------------------------------------------------------- layered layout


def _ranks(
    ids: list[str], edges: list[tuple[str, str]], people: set[str]
) -> dict[str, int]:
    """Longest-path layering; back edges (cycles) are ignored."""
    succ: dict[str, list[str]] = {i: [] for i in ids}
    for a, b in edges:
        if a in succ and b in succ and a != b:
            succ[a].append(b)
    state: dict[str, int] = {}
    keep: dict[str, list[str]] = {i: [] for i in ids}

    def visit(start: str) -> None:
        stack = [(start, iter(succ[start]))]
        state[start] = 1
        while stack:
            node, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                state[node] = 2
                stack.pop()
                continue
            if state.get(nxt) == 1:
                continue  # back edge
            keep[node].append(nxt)
            if nxt not in state:
                state[nxt] = 1
                stack.append((nxt, iter(succ[nxt])))

    for i in sorted(ids, key=lambda x: (x not in people, ids.index(x))):
        if i not in state:
            visit(i)
    rank = {i: 0 for i in ids}
    order = _topo(ids, keep)
    for node in order:
        for nxt in keep[node]:
            rank[nxt] = max(rank[nxt], rank[node] + 1)
    # a source that is not a person sits just above the first box it talks to, not on top
    has_pred = {b for a in ids for b in keep[a]}
    for node in reversed(order):
        if node not in people and node not in has_pred and keep[node]:
            rank[node] = max(0, min(rank[b] for b in keep[node]) - 1)
    return rank


def _topo(ids: list[str], succ: dict[str, list[str]]) -> list[str]:
    indeg = {i: 0 for i in ids}
    for a in ids:
        for b in succ[a]:
            indeg[b] += 1
    todo = [i for i in ids if indeg[i] == 0]
    out: list[str] = []
    while todo:
        node = todo.pop(0)
        out.append(node)
        for b in succ[node]:
            indeg[b] -= 1
            if indeg[b] == 0:
                todo.append(b)
    return out + [i for i in ids if i not in out]


def _rows(
    ids: list[str], edges: list[tuple[str, str]], people: set[str]
) -> list[list[str]]:
    if not ids:
        return []
    rank = _ranks(ids, edges, people)
    rows: list[list[str]] = [[] for _ in range(max(rank.values()) + 1)]
    for i in ids:
        rows[rank[i]].append(i)
    rows = [r for r in rows if r]
    wrapped: list[list[str]] = []
    for row in rows:
        for start in range(0, len(row), MAX_PER_ROW):
            wrapped.append(row[start : start + MAX_PER_ROW])
    _order(wrapped, edges)
    return wrapped


def _order(rows: list[list[str]], edges: list[tuple[str, str]]) -> None:
    """A few barycenter sweeps to untangle the lines between rows."""
    nbrs: dict[str, list[str]] = {}
    for a, b in edges:
        nbrs.setdefault(a, []).append(b)
        nbrs.setdefault(b, []).append(a)

    def pos() -> dict[str, float]:
        out = {}
        for row in rows:
            for k, i in enumerate(row):
                out[i] = k - (len(row) - 1) / 2
        return out

    for sweep in range(4):
        sequence = rows[1:] if sweep % 2 == 0 else rows[-2::-1]
        for row in sequence:
            at = pos()
            row.sort(
                key=lambda i, at=at: (
                    sum(at[n] for n in nbrs.get(i, []) if n in at and n not in row)
                    / max(
                        1, sum(1 for n in nbrs.get(i, []) if n in at and n not in row)
                    )
                    if any(n in at and n not in row for n in nbrs.get(i, []))
                    else at[i]
                )
            )


# ---------------------------------------------------------------- geometry


def _node(model: Model, element_id: str) -> Node:
    item = model.elements[element_id]
    shape = shape_of(item)
    inner = NODE_W - 28
    name = wrap(item.name, NAME_SIZE, inner, 2, bold=True)
    desc = wrap(item.description, DESC_SIZE, inner, 4)
    h = 26 + len(name) * 19 + 17 + (8 + len(desc) * LINE if desc else 0) + 18
    if shape in ("db", "queue", "storage"):
        h += 16
    if shape == "web":
        h += 14
    if shape == "person":
        h += PERSON_HEAD
    return Node(
        element_id,
        0,
        0,
        NODE_W,
        max(h, 118),
        shape,
        name,
        type_line(item),
        desc,
        drill_key(item),
    )


def _place_rows(
    rows: list[list[Node]], top: float, gap: float = ROW_GAP
) -> tuple[float, float]:
    """Centre each row on x = 0, starting at ``top``; return (half width, bottom)."""
    y = top
    half = 0.0
    for row in rows:
        width = sum(n.w for n in row) + COL_GAP * (len(row) - 1)
        x = -width / 2
        height = max(n.h for n in row)
        for n in row:
            n.x, n.y = x, y + (height - n.h) / 2
            x += n.w + COL_GAP
        half = max(half, width / 2)
        y += height + gap
    return half, y - gap if rows else top


def build(model: Model, level: str, focus: str | None, direction: str = "TB") -> View:
    """Lay out one view, flowing top to bottom (``TB``) or left to right (``LR``).

    Both flows are placed as rows; ``LR`` swaps every box's width and height first and
    transposes the result, so one placement routine serves both.
    """
    key = view_key(model, level, focus)
    lr = direction == "LR"
    gap = LR_GAP if lr else ROW_GAP
    label_room = 0 if lr else BOUNDARY_LABEL
    inside, outside = _visible(model, level, focus)
    edges, used = _lift(model, level, focus, inside, outside)
    if level != "context":
        outside = [i for i in outside if i in used]
    pairs = [(e.source, e.target) for e in edges]
    people = {i for i in model.elements if model.elements[i].level == "person"}
    nodes = {i: _node(model, i) for i in inside + outside}
    if lr:
        for n in nodes.values():
            n.w, n.h = n.h, n.w
    view = View(
        key, level, focus, _title(model, level, focus), _crumbs(model, level, focus)
    )
    view.direction = direction

    if level == "context":
        rows = _rows(inside, pairs, people)
        _place_rows([[nodes[i] for i in r] for r in rows], 0, gap)
    else:
        assert focus is not None
        inner_rows = _rows(inside, pairs, people)
        in_set = set(inside)
        above, below = [], []
        for i in outside:
            into = any(b in in_set or b == focus for a, b in pairs if a == i)
            outof = any(a in in_set or a == focus for a, b in pairs if b == i)
            (above if i in people or (into and not outof) else below).append(i)
        above_rows = [
            above[k : k + MAX_PER_ROW] for k in range(0, len(above), MAX_PER_ROW)
        ]
        below_rows = [
            below[k : k + MAX_PER_ROW] for k in range(0, len(below), MAX_PER_ROW)
        ]
        y = 0.0
        half = 0.0
        if above_rows:
            h, y = _place_rows([[nodes[i] for i in r] for r in above_rows], 0, gap)
            half = max(half, h)
            y += gap
        b_top = y
        h, inner_bottom = _place_rows(
            [[nodes[i] for i in r] for r in inner_rows], b_top + BOUNDARY_PAD, gap
        )
        b_half = h + BOUNDARY_PAD
        b_bottom = inner_bottom + BOUNDARY_PAD + label_room
        item = model.elements[focus]
        view.boundary = Boundary(
            focus,
            -b_half,
            b_top,
            2 * b_half,
            b_bottom - b_top,
            item.name,
            "Software System" if item.level == "system" else "Container",
        )
        half = max(half, b_half)
        y = b_bottom
        if below_rows:
            h, y = _place_rows(
                [[nodes[i] for i in r] for r in below_rows], y + gap, gap
            )
            half = max(half, h)
        _sort_outer(above_rows + below_rows, nodes, pairs)

    if lr:
        for n in nodes.values():
            n.x, n.y, n.w, n.h = n.y, n.x, n.h, n.w
        if view.boundary:
            b = view.boundary
            b.x, b.y, b.w, b.h = b.y, b.x, b.h, b.w + BOUNDARY_LABEL
    rects = [(n.x, n.y, n.x + n.w, n.y + n.h) for n in nodes.values()]
    if view.boundary:
        b = view.boundary
        rects.append((b.x, b.y, b.x + b.w, b.y + b.h))
    left, top = min(r[0] for r in rects), min(r[1] for r in rects)
    box = (left, top, max(r[2] for r in rects) - left, max(r[3] for r in rects) - top)

    # shift everything so the drawing starts at (MARGIN, TITLE_H)
    dx, dy = MARGIN - box[0], TITLE_H - box[1]
    for n in nodes.values():
        n.x += dx
        n.y += dy
    if view.boundary:
        view.boundary.x += dx
        view.boundary.y += dy
    view.nodes = [nodes[i] for i in inside + outside]
    view.width = box[2] + 2 * MARGIN
    view.height = box[3] + TITLE_H + MARGIN
    view.edges = edges
    left, top, right, bottom = _route(view)
    shift = max(0.0, 12 - left)
    if shift:  # a detour or a label ran off the left edge: move everything right
        for n in view.nodes:
            n.x += shift
        if view.boundary:
            view.boundary.x += shift
        view.width += shift
        left, top, right, bottom = _route(view)
    view.width = max(view.width, right + 12)
    view.height = max(view.height, bottom + 12)
    return view


def _sort_outer(rows: list[list[str]], nodes: dict[str, Node], pairs) -> None:
    """Re-order an outer row under or over the boxes it talks to, keeping its slots."""
    for row in rows:
        slots = sorted((nodes[i].x, nodes[i].y) for i in row)

        def anchor(i: str) -> float:
            xs = [nodes[b].cx for a, b in pairs if a == i and b in nodes]
            xs += [nodes[a].cx for a, b in pairs if b == i and a in nodes]
            return sum(xs) / len(xs) if xs else 0.0

        for i, (x, _) in zip(sorted(row, key=anchor), slots, strict=True):
            nodes[i].x = x


def _title(model: Model, level: str, focus: str | None) -> str:
    if level == "context" or not focus:
        return f"System context: {model.title}"
    name = model.elements[focus].name
    return f"{'Container' if level == 'container' else 'Component'} view: {name}"


def _crumbs(model: Model, level: str, focus: str | None) -> list[tuple[str, str]]:
    crumbs = [("context", "Context")]
    if level == "context" or not focus:
        return crumbs
    item = model.elements[focus]
    if level == "component" and item.parent:
        crumbs.append((f"container:{item.parent}", model.elements[item.parent].name))
    crumbs.append((f"{level}:{focus}", item.name))
    return crumbs


# ---------------------------------------------------------------- lines


def _rect(view: View, element_id: str) -> tuple[float, float, float, float]:
    for n in view.nodes:
        if n.id == element_id:
            top = n.y + (PERSON_HEAD - 8 if n.shape == "person" else 0)
            return n.x, top, n.w, n.y + n.h - top
    b = view.boundary
    assert b is not None and b.id == element_id
    return b.x, b.y, b.w, b.h


def _side(src, dst) -> tuple[str, str]:
    sx, sy, sw, sh = src
    tx, ty, tw, th = dst
    if ty >= sy + sh - 1:
        return "bottom", "top"
    if ty + th <= sy + 1:
        return "top", "bottom"
    return ("right", "left") if tx + tw / 2 >= sx + sw / 2 else ("left", "right")


def _route(view: View) -> tuple[float, float, float, float]:
    """Cubic curves between box sides; several lines on one side share it out evenly."""
    ends: dict[tuple[str, str], list[tuple[float, Edge, bool]]] = {}
    plan = []
    for e in view.edges:
        src, dst = _rect(view, e.source), _rect(view, e.target)
        s_side, t_side = _side(src, dst)
        # a node inside the boundary talking to the boundary itself never happens (the
        # model forbids relations to an ancestor), so both rects are disjoint or nested-free
        plan.append((e, src, dst, s_side, t_side))
        for rect, side, other, is_src in (
            (src, s_side, dst, True),
            (dst, t_side, src, False),
        ):
            key = (e.source if is_src else e.target, side)
            along = (
                other[0] + other[2] / 2
                if side in ("top", "bottom")
                else other[1] + other[3] / 2
            )
            ends.setdefault(key, []).append((along, e, is_src))
    spot: dict[tuple[str, bool], float] = {}
    for items in ends.values():
        items.sort(key=lambda t: t[0])
        for k, (_, e, is_src) in enumerate(items):
            spot[(e.id, is_src)] = (k + 1) / (len(items) + 1)
    nodes = {n.id: _rect(view, n.id) for n in view.nodes}
    labels: list[tuple[float, float, float, float]] = []
    reach: list[Point] = []
    for e, src, dst, s_side, t_side in plan:
        p0 = _port(src, s_side, spot[(e.id, True)])
        p3 = _port(dst, t_side, spot[(e.id, False)])
        obstacles = [r for i, r in nodes.items() if i not in (e.source, e.target)]
        dist = max(40.0, math.dist(p0, p3) * 0.35)
        curves = [(p0, _push(p0, s_side, dist), _push(p3, t_side, dist), p3)]
        if any(_hits(seg, obstacles) for seg in _pairs(_sample(curves))):
            points = _detour(
                [p0, _push(p0, s_side, 24), _push(p3, t_side, 24), p3], obstacles
            )
            curves = _smooth(points)
        e.path = "M{:.1f},{:.1f}".format(*p0) + "".join(
            " C{:.1f},{:.1f} {:.1f},{:.1f} {:.1f},{:.1f}".format(*c1, *c2, *q)
            for _, c1, c2, q in curves
        )
        e.label_lines = wrap(e.label, 12, 170, 3) + (
            [f"[{e.technology}]"] if e.technology else []
        )
        size = (
            max((len(t) for t in e.label_lines), default=0) * 6.4 + 10,
            len(e.label_lines) * 14 + 4,
        )
        e.label_x, e.label_y = _label_spot(
            _sample(curves), size, list(nodes.values()), labels
        )
        if e.label_lines:
            labels.append(_box_at(e.label_x, e.label_y, size))
        reach.extend(_sample(curves, 4))
    for x, y, w, h in labels:
        reach.extend(((x, y), (x + w, y + h)))
    xs, ys = [p[0] for p in reach] or [0.0], [p[1] for p in reach] or [0.0]
    return min(xs), min(ys), max(xs), max(ys)


Point = tuple[float, float]
Rect = tuple[float, float, float, float]


def _sample(curves, steps: int = 16) -> list[Point]:
    pts: list[Point] = [curves[0][0]]
    for p, c1, c2, q in curves:
        for k in range(1, steps + 1):
            t = k / steps
            u = 1 - t
            pts.append(
                (
                    u**3 * p[0]
                    + 3 * u * u * t * c1[0]
                    + 3 * u * t * t * c2[0]
                    + t**3 * q[0],
                    u**3 * p[1]
                    + 3 * u * u * t * c1[1]
                    + 3 * u * t * t * c2[1]
                    + t**3 * q[1],
                )
            )
    return pts


def _pairs(pts: list[Point]) -> list[tuple[Point, Point]]:
    return list(itertools.pairwise(pts))


def _grow(r: Rect, d: float) -> Rect:
    return r[0] - d, r[1] - d, r[2] + 2 * d, r[3] + 2 * d


def _cuts(a: Point, b: Point, r: Rect) -> bool:
    """Does segment ab pass through the inside of rectangle r (Liang-Barsky)?"""
    x, y, w, h = r
    dx, dy = b[0] - a[0], b[1] - a[1]
    lo, hi = 0.0, 1.0
    for p, q in (
        (-dx, a[0] - x),
        (dx, x + w - a[0]),
        (-dy, a[1] - y),
        (dy, y + h - a[1]),
    ):
        if p == 0:
            if q <= 0:
                return False
            continue
        t = q / p
        if p < 0:
            lo = max(lo, t)
        else:
            hi = min(hi, t)
        if lo >= hi:
            return False
    return hi - lo > 1e-6


def _hits(seg: tuple[Point, Point], obstacles: list[Rect]) -> bool:
    return any(_cuts(seg[0], seg[1], _grow(r, 8)) for r in obstacles)


def _detour(points: list[Point], obstacles: list[Rect]) -> list[Point]:
    """Insert waypoints that step around every box a polyline crosses."""
    for _ in range(12):
        hit = next(
            (
                (i, r)
                for i in range(len(points) - 1)
                for r in obstacles
                if _cuts(points[i], points[i + 1], _grow(r, 8))
            ),
            None,
        )
        if hit is None:
            break
        i, (x, y, w, h) = hit
        a, b = points[i], points[i + 1]
        if abs(b[1] - a[1]) >= abs(b[0] - a[0]):
            mid = (a[0] + b[0]) / 2
            left, right = x - COL_GAP / 2, x + w + COL_GAP / 2
            gx = left if abs(mid - left) <= abs(mid - right) else right
            ys = (y - 16, y + h + 16) if b[1] >= a[1] else (y + h + 16, y - 16)
            detour = [(gx, ys[0]), (gx, ys[1])]
        else:
            mid = (a[1] + b[1]) / 2
            top, bottom = y - 24, y + h + 24
            gy = top if abs(mid - top) <= abs(mid - bottom) else bottom
            xs = (x - 16, x + w + 16) if b[0] >= a[0] else (x + w + 16, x - 16)
            detour = [(xs[0], gy), (xs[1], gy)]
        points = points[: i + 1] + detour + points[i + 1 :]
    return points


def _smooth(points: list[Point]):
    """Catmull-Rom through the waypoints, as cubic Bezier pieces."""
    out = []
    n = len(points)
    for i in range(n - 1):
        p0 = points[max(i - 1, 0)]
        p1, p2 = points[i], points[i + 1]
        p3 = points[min(i + 2, n - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        out.append((p1, c1, c2, p2))
    return out


def _box_at(x: float, y: float, size: tuple[float, float]) -> Rect:
    return x - size[0] / 2, y - size[1] / 2, size[0], size[1]


def _overlaps(a: Rect, b: Rect) -> bool:
    return (
        a[0] < b[0] + b[2]
        and b[0] < a[0] + a[2]
        and a[1] < b[1] + b[3]
        and b[1] < a[1] + a[3]
    )


def _label_spot(pts: list[Point], size, boxes: list[Rect], labels: list[Rect]) -> Point:
    """The point nearest the middle of the line where its label covers no box or label."""
    lengths = [0.0]
    for a, b in _pairs(pts):
        lengths.append(lengths[-1] + math.dist(a, b))
    total = lengths[-1] or 1.0

    def at(f: float) -> Point:
        goal = total * f
        for k in range(1, len(pts)):
            if lengths[k] >= goal:
                span = lengths[k] - lengths[k - 1] or 1.0
                t = (goal - lengths[k - 1]) / span
                a, b = pts[k - 1], pts[k]
                return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
        return pts[-1]

    for f in (0.5, 0.42, 0.58, 0.34, 0.66, 0.26, 0.74, 0.18, 0.82):
        x, y = at(f)
        box = _box_at(x, y, size)
        if not any(_overlaps(box, r) for r in boxes) and not any(
            _overlaps(box, r) for r in labels
        ):
            return x, y
    return at(0.5)


def _port(rect, side: str, t: float) -> tuple[float, float]:
    x, y, w, h = rect
    spread = 0.6
    f = 0.5 + (t - 0.5) * spread
    if side == "top":
        return x + w * f, y
    if side == "bottom":
        return x + w * f, y + h
    if side == "left":
        return x, y + h * f
    return x + w, y + h * f


def _push(p: tuple[float, float], side: str, d: float) -> tuple[float, float]:
    dx, dy = {"top": (0, -1), "bottom": (0, 1), "left": (-1, 0), "right": (1, 0)}[side]
    return p[0] + dx * d, p[1] + dy * d
