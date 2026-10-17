"""Layered layout of boxes and groups, arrow anchors, and A* routed arrows.

Flow runs left to right (``LR``, architecture) or top to bottom (``TB``, topology). Boxes
sit in layers by longest path. Every group owns a band of the other axis, so the boxes of
a group are contiguous and two groups can never overlap. A group's rectangle is always
"the box around its members and sub-groups, plus padding and a header"; the browser code
uses the same rule to resize groups while boxes are dragged.

Arrows are kept straight on purpose. Boxes in a lane line up on the row their arrows use,
every arrow end then slides along its box side to the spot nearest the other end, and the
router (A*, see ``router``) charges for every turn. A chain of boxes is one straight line.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .icons import resolve_service
from .router import DIRS, Grid, Point, label_point, route
from .spec import ArchSpec, node_label
from .theme import CATEGORIES, CATEGORY_LABELS

# Geometry (px). Everything is a multiple of the routing grid cell so arrow anchors sit on
# the grid and arrows leave and enter boxes in straight lines, with no little jogs.
BASE_H = 60  # the card: icon, title and subtitle
PORT_ROW = 20
PORT_PAD = 10
SLOT_SPACING = 20  # between two arrows meeting the same side
SLOT_INSET = 20  # from a corner
MIN_W = 140
GROUP_PAD = 20
GROUP_HEADER = 10  # the title sits on the border; this is the room it needs above
#: Space kept between boxes, here and while dragging. Arrows keep GRID_MARGIN away from a
#: box, so this leaves a two-cell corridor to route through (and room for the stub an
#: arrow leaves its own box with), instead of walling the neighbours' arrows in.
NODE_GAP = 40
MARGIN = 40
TITLE_H = 40
LAYER_GAP = 80
GRID_CELL = 10
GRID_MARGIN = 8
LEGEND_GAP = 28
LEGEND_H = 24
TITLE_SIZE = 13
SUB_SIZE = 10
MONO_EM = 0.6  # a monospace character is about this many ems wide


def mono_width(text: str, size: float) -> float:
    """Width of ``text`` in a monospace font (the browser does the real layout)."""
    return len(text) * size * MONO_EM


def _up(value: float, multiple: int = GRID_CELL) -> int:
    return int(math.ceil(value / multiple) * multiple)


def _snap(value: float) -> int:
    """Nearest multiple of the grid cell (halves round up, like the browser code)."""
    return math.floor(value / GRID_CELL + 0.5) * GRID_CELL


@dataclass
class Box:
    id: str
    label: str
    sub: str
    kind: str
    provider: str
    category: str
    group: str | None
    inputs: list[str]
    outputs: list[str]
    note: str
    mono: str | None = None  # monogram of a software service
    color: str | None = None  # its tile colour
    logo: str | None = None  # the node's own logo, a data URI
    w: int = 0
    h: int = 0
    x: float = 0.0
    y: float = 0.0
    layer: int = 0

    def port_y(self, index: int) -> int:
        return BASE_H + index * PORT_ROW + PORT_ROW // 2

    def rect(self) -> tuple[float, float, float, float]:
        return (self.x, self.y, self.w, self.h)


@dataclass
class GroupBox:
    id: str
    label: str
    type: str
    parent: str | None
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0


@dataclass
class Edge:
    id: str
    source: str
    target: str
    source_port: str | None
    target_port: str | None
    label: str
    style: str
    src_offset: tuple[float, float] = (0.0, 0.0)
    dst_offset: tuple[float, float] = (0.0, 0.0)
    src_dir: int = 0
    dst_dir: int = 2
    points: list[Point] = field(default_factory=list)
    label_at: Point = (0.0, 0.0)

    @property
    def label_width(self) -> float:
        return mono_width(self.label, SUB_SIZE) + 8


@dataclass
class Layout:
    direction: str
    boxes: list[Box]
    groups: list[GroupBox]
    edges: list[Edge]
    width: float
    height: float
    title_h: float
    legend: list[tuple[str, int]] = field(default_factory=list)  # (category, count)
    legend_y: float = 0.0


def _endpoint(value: str) -> tuple[str, str | None]:
    node, _, port = value.partition(":")
    return node, (port or None)


def assign_layers(order: list[str], links: list[tuple[str, str]]) -> dict[str, int]:
    """Longest-path layers; links that close a cycle are ignored for layering."""
    out: dict[str, list[str]] = {n: [] for n in order}
    for a, b in links:
        if a != b and b not in out[a]:
            out[a].append(b)
    state: dict[str, int] = {}
    back: set[tuple[str, str]] = set()
    for root in order:
        if root in state:
            continue
        state[root] = 1
        stack = [(root, iter(out[root]))]
        while stack:
            node, it = stack[-1]
            for nxt in it:
                if state.get(nxt) == 1:
                    back.add((node, nxt))
                elif nxt not in state:
                    state[nxt] = 1
                    stack.append((nxt, iter(out[nxt])))
                    break
            else:
                state[node] = 2
                stack.pop()
    forward = {n: [m for m in out[n] if (n, m) not in back] for n in order}
    indeg = {n: 0 for n in order}
    for n in order:
        for m in forward[n]:
            indeg[m] += 1
    layer = {n: 0 for n in order}
    queue = [n for n in order if indeg[n] == 0]
    while queue:
        node = queue.pop(0)
        for m in forward[node]:
            layer[m] = max(layer[m], layer[node] + 1)
            indeg[m] -= 1
            if indeg[m] == 0:
                queue.append(m)
    return layer


def group_rect(
    gid: str,
    children: dict[str | None, list[str]],
    members: dict[str | None, list[Box]],
    rects: dict[str, tuple[float, float, float, float]],
) -> tuple[float, float, float, float]:
    """The box around a group's members and sub-groups, with padding and a header."""
    parts = [b.rect() for b in members.get(gid, [])]
    for child in children.get(gid, []):
        rects[child] = group_rect(child, children, members, rects)
        parts.append(rects[child])
    x1 = min(p[0] for p in parts)
    y1 = min(p[1] for p in parts)
    x2 = max(p[0] + p[2] for p in parts)
    y2 = max(p[1] + p[3] for p in parts)
    return (
        x1 - GROUP_PAD,
        y1 - GROUP_PAD - GROUP_HEADER,
        x2 - x1 + 2 * GROUP_PAD,
        y2 - y1 + 2 * GROUP_PAD + GROUP_HEADER,
    )


def box_size(box: Box, slots: int, lr: bool) -> tuple[int, int]:
    """Width and height of a card: its text and ports, and room for the arrows meeting it."""
    rows = max(len(box.inputs), len(box.outputs))
    head_w = max(mono_width(box.label, TITLE_SIZE), mono_width(box.sub, SUB_SIZE)) + 44
    port_w = (
        max([mono_width(p, SUB_SIZE) for p in box.inputs], default=0)
        + max([mono_width(p, SUB_SIZE) for p in box.outputs], default=0)
        + 60
    )
    # room for the arrows without a port and for the rows of the declared ports
    room = SLOT_SPACING * (slots + rows) + 2 * SLOT_INSET - SLOT_SPACING
    w = max(MIN_W, head_w, port_w if rows else 0, 0 if lr else room)
    h = BASE_H if not rows else BASE_H + rows * PORT_ROW + PORT_PAD
    if lr:
        h = max(h, room)
    return _up(w, 2 * GRID_CELL), _up(h)


def build(spec: ArchSpec, diagram_type: str, default_direction: str) -> Layout:
    direction = spec.direction or default_direction
    lr = direction == "LR"
    provider = spec.provider

    # ---------------------------------------------------------------- boxes
    boxes: dict[str, Box] = {}
    for node in spec.nodes:
        r = resolve_service(node.service, node.kind, provider)
        label = node_label(node)
        sub = (
            r.name if r.name and r.name != label and (node.service or node.kind) else ""
        )
        boxes[node.id] = Box(
            id=node.id,
            label=label,
            sub=sub,
            kind=r.kind,
            # only a node that names a service wears a provider badge, not every box of the diagram
            provider=r.provider if node.service else "generic",
            category=node.category or r.category,
            group=node.group,
            inputs=list(node.inputs),
            outputs=list(node.outputs),
            note=node.note or "",
            mono=r.mono,
            color=r.color,
            logo=node.logo,
        )
    order = [n.id for n in spec.nodes]

    edges: list[Edge] = []
    for index, link in enumerate(spec.links):
        (s, sp), (t, tp) = _endpoint(link.source), _endpoint(link.target)
        edges.append(Edge(f"e{index}", s, t, sp, tp, link.label or "", link.style))

    # how many arrows meet a box side without a port (they need room to be spread out)
    out_slots = {n: 0 for n in order}
    in_slots = {n: 0 for n in order}
    connected_rows: dict[str, list[int]] = {n: [] for n in order}
    for e in edges:
        if e.source_port is None:
            out_slots[e.source] += 1
        else:
            connected_rows[e.source].append(
                boxes[e.source].outputs.index(e.source_port)
            )
        if e.target_port is None:
            in_slots[e.target] += 1
        else:
            connected_rows[e.target].append(boxes[e.target].inputs.index(e.target_port))
    for box in boxes.values():
        slots = max(out_slots[box.id], in_slots[box.id], 1)
        box.w, box.h = box_size(box, slots, lr)

    def reference(box: Box) -> int:
        """Offset from a box's top (left) edge to the line its arrows use."""
        if not lr:
            return box.w // 2
        rows = connected_rows[box.id]
        return box.port_y(min(rows)) if rows else BASE_H // 2

    # --------------------------------------------------------------- layers
    pairs = [(e.source, e.target) for e in edges]
    layers = assign_layers(order, pairs)
    for n, layer in layers.items():
        boxes[n].layer = layer
    n_layers = max(layers.values(), default=0) + 1

    # ------------------------------------------------------- group structure
    group_by_id = {g.id: g for g in spec.groups}
    children: dict[str | None, list[str]] = {None: []}
    for g in spec.groups:
        children.setdefault(g.id, [])
    first_seen: dict[str, int] = {}
    for index, n in enumerate(order):
        cur = boxes[n].group
        while cur is not None:
            first_seen.setdefault(cur, index)
            cur = group_by_id[cur].parent
    for g in sorted(spec.groups, key=lambda g: (first_seen.get(g.id, 10**6), g.id)):
        children[g.parent].append(g.id)
    members: dict[str | None, list[Box]] = {None: []}
    for g in spec.groups:
        members.setdefault(g.id, [])
    for n in order:
        members[boxes[n].group].append(boxes[n])

    def depth(gid: str | None) -> int:
        return (
            0 if gid is None else 1 + max((depth(c) for c in children[gid]), default=0)
        )

    max_depth = max((depth(c) for c in children[None]), default=0)

    # ------------------------------------------- abstract axes: u = flow, v = order
    def u_size(b: Box) -> float:
        return b.w if lr else b.h

    def v_size(b: Box) -> float:
        return b.h if lr else b.w

    layer_size = [0.0] * n_layers
    for b in boxes.values():
        layer_size[b.layer] = max(layer_size[b.layer], u_size(b))
    gap = LAYER_GAP + (2 * GROUP_PAD if lr else GROUP_HEADER + GROUP_PAD) * max_depth
    title_h = TITLE_H if spec.title else 0
    u0 = (
        MARGIN
        + (0 if lr else title_h)
        + (GROUP_PAD if lr else GROUP_HEADER + GROUP_PAD) * max_depth
    )
    layer_u: list[float] = []
    cursor = u0
    for size in layer_size:
        layer_u.append(cursor)
        cursor += size + gap

    inset_before = (GROUP_HEADER if lr else 0) + GROUP_PAD
    index_of = {n: i for i, n in enumerate(order)}
    linked: dict[str, set[str]] = {n: set() for n in order}
    for e in edges:
        linked[e.source].add(e.target)
        linked[e.target].add(e.source)

    def arrange(
        gid: str | None,
    ) -> tuple[dict[str, float], float, tuple[int, int]]:
        """Pack a group's boxes and sub-groups into lanes of the order axis.

        An item joins the first lane where its span of layers does not overlap anything
        already there, so a chain such as users -> cdn -> api -> orders reads as one
        straight line, while boxes in the same layer stack in separate lanes. The items of
        a lane line up on their reference line (the row their arrows use), not on their
        tops, so boxes of different heights still meet in straight arrows. Returns the
        offset of every box below the group's top, the group's height (its header and
        padding included) and the layers it covers. A group's box is drawn around its
        members (see ``group_rect``), so groups in different lanes never overlap.
        """
        before = 0 if gid is None else inset_before
        after = 0 if gid is None else GROUP_PAD
        # (first appearance, offsets of the item's boxes, height, span of layers, reference)
        items: list[tuple[int, dict[str, float], float, tuple[int, int], float]] = []
        for b in members[gid]:
            items.append(
                (
                    index_of[b.id],
                    {b.id: 0.0},
                    v_size(b),
                    (b.layer, b.layer),
                    reference(b),
                )
            )
        for child in children[gid]:
            offsets, height, span = arrange(child)
            # a group lines up on the row its first declared box uses, so an arrow into
            # the group from a neighbour in the lane stays straight
            lead = min(offsets, key=lambda n: index_of[n])
            items.append(
                (
                    first_seen[child],
                    offsets,
                    height,
                    span,
                    offsets[lead] + reference(boxes[lead]),
                )
            )
        items.sort(key=lambda item: item[0])

        lanes: list[dict[str, Any]] = []
        for _seen, offsets, height, span, ref in items:
            free = [
                lane
                for lane in lanes
                if all(span[1] < lo or hi < span[0] for lo, hi in lane["spans"])
            ]
            neighbours = set().union(*(linked[n] for n in offsets)) - set(offsets)
            # the free lane with most of the item's neighbours (the first one on a tie), so
            # a chain such as queue -> mail stays on one row
            lane = max(free, key=lambda ln: len(ln["nodes"] & neighbours), default=None)
            if lane is None:
                lane = {"spans": [], "items": [], "nodes": set()}
                lanes.append(lane)
            lane["spans"].append(span)
            lane["items"].append((offsets, height, ref))
            lane["nodes"].update(offsets)

        result: dict[str, float] = {}
        cursor = float(before)
        for lane in lanes:
            top_ref = max(ref for _o, _h, ref in lane["items"])
            lane_h = max(top_ref - ref + height for _o, height, ref in lane["items"])
            for offsets, _height, ref in lane["items"]:
                shift = cursor + top_ref - ref
                for node_id, offset in offsets.items():
                    result[node_id] = shift + offset
            cursor += lane_h + NODE_GAP
        span = (min(item[3][0] for item in items), max(item[3][1] for item in items))
        return result, cursor - NODE_GAP + after, span

    root_offsets, _height, _span = arrange(None)
    v_top = MARGIN + (title_h if lr else 0)
    placed_v = {n: _snap(v_top + off) for n, off in root_offsets.items()}

    for b in boxes.values():
        u = _snap(layer_u[b.layer] + (layer_size[b.layer] - u_size(b)) / 2)
        v = placed_v[b.id]
        b.x, b.y = (u, v) if lr else (v, u)

    # -------------------------------------------------- shift so the margin holds
    rects: dict[str, tuple[float, float, float, float]] = {}
    top_groups = {
        gid: group_rect(gid, children, members, rects) for gid in children[None]
    }
    rects.update(top_groups)
    everything = [b.rect() for b in boxes.values()] + list(rects.values())
    dx = MARGIN - min(r[0] for r in everything)
    dy = MARGIN + title_h - min(r[1] for r in everything)
    for b in boxes.values():
        b.x += dx
        b.y += dy
    rects = {}
    for gid in children[None]:
        rects[gid] = group_rect(gid, children, members, rects)

    groups = [
        GroupBox(g.id, g.label or g.id, g.type, g.parent, *rects[g.id])
        for g in spec.groups
    ]

    # ----------------------------------------------------------- arrow anchors
    place_anchors(boxes, edges, lr)
    route_edges(list(boxes.values()), edges)

    everything = [b.rect() for b in boxes.values()] + [
        (g.x, g.y, g.w, g.h) for g in groups
    ]
    pts = [p for e in edges for p in e.points]
    right = max([r[0] + r[2] for r in everything] + [p[0] for p in pts])
    bottom = max([r[1] + r[3] for r in everything] + [p[1] for p in pts])

    counts = {c: 0 for c in CATEGORIES}
    for b in boxes.values():
        counts[b.category] += 1
    legend = [(c, counts[c]) for c in CATEGORIES if counts[c]]
    width = right + MARGIN
    legend_y = 0.0
    height = bottom + MARGIN
    if legend:
        legend_y = bottom + LEGEND_GAP
        height = legend_y + LEGEND_H + MARGIN
        width = max(width, MARGIN * 2 + legend_width(legend))
    return Layout(
        direction,
        list(boxes.values()),
        groups,
        edges,
        width,
        height,
        title_h,
        legend,
        legend_y,
    )


def legend_width(legend: list[tuple[str, int]]) -> float:
    """Width of the legend row: a swatch, the category name and its count, per category."""
    return sum(
        18 + 8 + mono_width(CATEGORY_LABELS[c], 11) + 6 + mono_width(str(n), 10) + 22
        for c, n in legend
    ) + mono_width("Legend", 12)


def pack_slots(
    wanted: list[float], candidates: list[int], taken: list[float]
) -> list[int]:
    """Choose a distinct spot for each wish, as near as possible, and never too close.

    ``wanted`` is sorted. Spots come from ``candidates`` (grid points), keep
    ``SLOT_SPACING`` from each other and from ``taken`` (ports already on the side), and
    keep the order of the wishes so arrows do not cross. The total distance moved is the
    least possible (dynamic programming), which a greedy "nearest free spot" cannot promise:
    it can leave the last arrow nowhere to go. When the side is too crowded for the full
    spacing, half of it is used, and failing that the nearest spots, even if shared.
    """
    for spacing in (SLOT_SPACING, SLOT_SPACING // 2):
        spots = [c for c in candidates if all(abs(c - t) >= spacing for t in taken)]
        n, m = len(wanted), len(spots)
        if n > m:
            continue
        inf = float("inf")
        cost = [[inf] * m for _ in range(n)]
        back: list[list[int]] = [[-1] * m for _ in range(n)]
        for j in range(m):
            cost[0][j] = abs(spots[j] - wanted[0])
        for i in range(1, n):
            best, arg, k = inf, -1, 0
            for j in range(m):
                while k < m and spots[k] <= spots[j] - spacing:
                    if cost[i - 1][k] < best:
                        best, arg = cost[i - 1][k], k
                    k += 1
                if arg >= 0:
                    cost[i][j] = best + abs(spots[j] - wanted[i])
                    back[i][j] = arg
        j = min(range(m), key=lambda x: (cost[n - 1][x], x), default=-1)
        if j < 0 or cost[n - 1][j] == inf:
            continue
        chosen = [0] * n
        for i in range(n - 1, -1, -1):
            chosen[i] = spots[j]
            j = back[i][j]
        return chosen
    return [min(candidates, key=lambda c: (abs(c - w), c)) for w in wanted]


def place_anchors(boxes: dict[str, Box], edges: list[Edge], lr: bool) -> None:
    """Choose where every arrow meets its boxes, so that arrows come out straight.

    An end that names a port is fixed at the port. Every other end slides along its box
    side to the free spot (on the grid, clear of the others) nearest the other end of
    the arrow, so two boxes whose rows overlap get a straight arrow between them. The
    other end moves too, so the choice is repeated a few times.
    """
    axis = 1 if lr else 0

    def fixed(e: Edge, end: str) -> tuple[float, float] | None:
        box = boxes[e.source if end == "src" else e.target]
        port = e.source_port if end == "src" else e.target_port
        if port is None:
            return None
        if end == "src":
            return (box.x + box.w, box.y + box.port_y(box.outputs.index(port)))
        return (box.x, box.y + box.port_y(box.inputs.index(port)))

    current: dict[tuple[str, str], tuple[float, float]] = {}
    for e in edges:
        for end, bid in (("src", e.source), ("dst", e.target)):
            b = boxes[bid]
            current[(e.id, end)] = fixed(e, end) or (b.x + b.w / 2, b.y + b.h / 2)

    sides: dict[tuple[str, str], list[tuple[Edge, str]]] = {}
    for e in edges:
        for end, bid, port in (
            ("src", e.source, e.source_port),
            ("dst", e.target, e.target_port),
        ):
            if port is None:
                sides.setdefault((bid, "out" if end == "src" else "in"), []).append(
                    (e, end)
                )

    for _ in range(3):
        for (bid, side), ends in sides.items():
            b = boxes[bid]
            start, length = (b.y, b.h) if lr else (b.x, b.w)
            candidates = range(
                int(start + SLOT_INSET), int(start + length - SLOT_INSET) + 1, GRID_CELL
            )
            # declared ports keep their rows clear, in LR where they share the side
            names = b.outputs if side == "out" else b.inputs
            taken = [b.y + b.port_y(i) for i in range(len(names))] if lr else []

            def want(item: tuple[Edge, str]) -> float:
                edge, end = item
                other = current[(edge.id, "dst" if end == "src" else "src")]
                return other[axis]

            ordered = sorted(ends, key=lambda t: (want(t), int(t[0].id[1:])))
            spots = pack_slots([want(t) for t in ordered], list(candidates), taken)
            for (e, end), spot in zip(ordered, spots, strict=True):
                if lr:
                    point = (b.x + b.w if side == "out" else b.x, float(spot))
                else:
                    point = (float(spot), b.y + b.h if side == "out" else b.y)
                current[(e.id, end)] = point

    for e in edges:
        a, b = boxes[e.source], boxes[e.target]
        sx, sy = current[(e.id, "src")]
        dx, dy = current[(e.id, "dst")]
        e.src_offset = (sx - a.x, sy - a.y)
        e.dst_offset = (dx - b.x, dy - b.y)
        if e.source_port is not None or lr:
            e.src_dir = 0
        else:
            e.src_dir = 1
        if e.target_port is not None or lr:
            e.dst_dir = 2
        else:
            e.dst_dir = 3


def route_edges(boxes: list[Box], edges: list[Edge]) -> None:
    """Route every arrow around the boxes, in declaration order."""
    by_id = {b.id: b for b in boxes}
    grid = Grid([b.rect() for b in boxes], cell=GRID_CELL, margin=GRID_MARGIN)
    for e in edges:
        a, b = by_id[e.source], by_id[e.target]
        start = (a.x + e.src_offset[0], a.y + e.src_offset[1])
        goal = (b.x + e.dst_offset[0], b.y + e.dst_offset[1])
        e.points = route(grid, start, e.src_dir, goal, e.dst_dir)
        e.label_at = (
            label_point(e.points, e.label_width, [b.rect() for b in boxes])
            if e.label
            else e.points[0]
        )


__all__ = [
    "DIRS",
    "Box",
    "Edge",
    "GroupBox",
    "Layout",
    "build",
    "group_rect",
    "legend_width",
    "mono_width",
    "pack_slots",
    "place_anchors",
    "route_edges",
]
