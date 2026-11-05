"""Auto-layout and orthogonal routing for nested, directional diagrams.

Everything is computed in an abstract frame where the flow always runs along ``m`` (main
axis, increasing) and nodes spread along ``c`` (cross axis). One mirror/transpose at the
end turns that into left-to-right, right-to-left, top-down or bottom-up.

* Nodes get a layer from the longest path (cycles are broken with a DFS).
* Groups nest. Each group is packed as a unit: units whose layer ranges do not overlap
  share a row, so a pipeline stays on one line and branches stack.
* Edges are orthogonal. The router tries straight, elbow and lane detours and keeps the
  first route that does not run through another node.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import pairwise

from .spec import Edge, Group, Node, Spec

Rect = tuple[float, float, float, float]  # x, y, width, height
Point = tuple[float, float]


@dataclass(frozen=True)
class Metrics:
    node: tuple[int, int]  # footprint width, height (tile plus labels)
    shape: tuple[int, int, int, int]  # visible shape inside the footprint: x, y, w, h
    gap_main: int = 84
    gap_cross: int = 30
    pad: int = 22
    head: int = 34
    margin: int = 48


@dataclass
class Placed:
    node: Node
    rect: Rect
    shape: Rect


@dataclass
class Box:
    group: Group
    rect: Rect
    depth: int


@dataclass
class Route:
    edge: Edge
    points: list[Point]
    label: tuple[float, float, str] | None = None


@dataclass
class Layout:
    width: float
    height: float
    nodes: list[Placed] = field(default_factory=list)
    boxes: list[Box] = field(default_factory=list)
    routes: list[Route] = field(default_factory=list)
    direction: str = "LR"


@dataclass
class _Unit:
    m0: float
    m1: float
    c_ext: float
    node: Node | None = None
    group: Group | None = None
    depth: int = 0
    kids: list[_Unit] = field(default_factory=list)
    c_in: float = 0.0
    c_off: float = 0.0
    c0: float = 0.0


def _layers(spec: Spec) -> dict[str, int]:
    ids = [n.id for n in spec.nodes]
    out: dict[str, list[str]] = {i: [] for i in ids}
    for e in spec.edges:
        out[e.source].append(e.target)
    state: dict[str, int] = {}
    back: set[tuple[str, str]] = set()
    for root in ids:
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
    preds: dict[str, list[str]] = {i: [] for i in ids}
    succs: dict[str, list[str]] = {i: [] for i in ids}
    for e in spec.edges:
        if (e.source, e.target) not in back:
            preds[e.target].append(e.source)
            succs[e.source].append(e.target)
    layer: dict[str, int] = {}

    def depth(node: str) -> int:
        if node not in layer:
            layer[node] = 0  # guards against any residual cycle
            layer[node] = 1 + max((depth(p) for p in preds[node]), default=-1)
        return layer[node]

    for i in ids:
        depth(i)
    # Pull pure sources next to their first consumer instead of leaving them at layer 0.
    for i in ids:
        if not preds[i] and succs[i]:
            layer[i] = max(0, min(layer[s] for s in succs[i]) - 1)
    return layer


def layout(spec: Spec, metrics: Metrics) -> Layout:
    horizontal = spec.direction in ("LR", "RL")
    nw, nh = metrics.node
    node_m, node_c = (nw, nh) if horizontal else (nh, nw)
    layer = _layers(spec)
    pad, head = metrics.pad, metrics.head
    head_main = not horizontal
    head_end = spec.direction == "BT"

    by_id = {g.id: g for g in spec.groups}

    def depth_of(group: Group) -> int:
        depth, cursor = 1, group
        while cursor.parent:
            cursor = by_id[cursor.parent]
            depth += 1
        return depth

    max_depth = max((depth_of(g) for g in spec.groups), default=0)
    gap_main = metrics.gap_main + (2 * pad + (head if head_main else 0)) * max_depth
    if horizontal:
        longest = max((len(e.label) for e in spec.edges), default=0)
        gap_main = max(gap_main, int(longest * 6.8) + 40 + 2 * pad * max_depth)
    n_layers = max(layer.values()) + 1
    pos = [metrics.margin + k * (node_m + gap_main) for k in range(n_layers)]

    index = {n.id: i for i, n in enumerate(spec.nodes)}
    first_index: dict[str, int] = {}

    def first_of(group_id: str) -> int:
        if group_id not in first_index:
            hits = [index[n.id] for n in spec.nodes if n.group == group_id]
            hits += [first_of(g.id) for g in spec.groups if g.parent == group_id]
            first_index[group_id] = min(hits, default=10**6)
        return first_index[group_id]

    def pack(units: list[_Unit]) -> float:
        placed: list[_Unit] = []
        for unit in units:
            candidates = sorted(
                {0.0, *[p.c_off + p.c_ext + metrics.gap_cross for p in placed]}
            )
            for c in candidates:
                clash = any(
                    unit.m0 < p.m1
                    and p.m0 < unit.m1
                    and c < p.c_off + p.c_ext + metrics.gap_cross
                    and p.c_off < c + unit.c_ext + metrics.gap_cross
                    for p in placed
                )
                if not clash:
                    unit.c_off = c
                    break
            placed.append(unit)
        return max((p.c_off + p.c_ext for p in placed), default=0.0)

    def build(parent: str | None, depth: int) -> list[_Unit]:
        keyed: list[tuple[int, _Unit]] = []
        for n in spec.nodes:
            if n.group == parent:
                m0 = pos[layer[n.id]]
                keyed.append((index[n.id], _Unit(m0, m0 + node_m, node_c, node=n)))
        for g in spec.groups:
            if g.parent == parent:
                kids = build(g.id, depth + 1)
                if not kids:
                    continue
                extent = pack(kids)
                m0 = (
                    min(k.m0 for k in kids)
                    - pad
                    - (head if head_main and not head_end else 0)
                )
                m1 = (
                    max(k.m1 for k in kids)
                    + pad
                    + (head if head_main and head_end else 0)
                )
                c_in = pad + (0 if head_main else head)
                unit = _Unit(
                    m0,
                    m1,
                    extent + 2 * pad + (0 if head_main else head),
                    group=g,
                    depth=depth,
                    kids=kids,
                    c_in=c_in,
                )
                keyed.append((first_of(g.id), unit))
        keyed.sort(key=lambda item: item[0])
        return [unit for _, unit in keyed]

    roots = build(None, 1)
    pack(roots)

    def assign(unit: _Unit, origin: float) -> None:
        unit.c0 = origin + unit.c_off
        for kid in unit.kids:
            assign(kid, unit.c0 + unit.c_in)

    for root in roots:
        assign(root, metrics.margin)

    total_m = max(u.m1 for u in _walk(roots)) + metrics.margin

    def to_final(m0: float, m1: float, c0: float, c1: float) -> Rect:
        if spec.direction == "LR":
            return (m0, c0, m1 - m0, c1 - c0)
        if spec.direction == "RL":
            return (total_m - m1, c0, m1 - m0, c1 - c0)
        if spec.direction == "TB":
            return (c0, m0, c1 - c0, m1 - m0)
        return (c0, total_m - m1, c1 - c0, m1 - m0)

    def to_abs(rect: Rect) -> tuple[float, float, float, float]:
        x, y, w, h = rect
        if spec.direction == "LR":
            return (x, x + w, y, y + h)
        if spec.direction == "RL":
            return (total_m - (x + w), total_m - x, y, y + h)
        if spec.direction == "TB":
            return (y, y + h, x, x + w)
        return (total_m - (y + h), total_m - y, x, x + w)

    def to_point(m: float, c: float) -> Point:
        if spec.direction == "LR":
            return (m, c)
        if spec.direction == "RL":
            return (total_m - m, c)
        if spec.direction == "TB":
            return (c, m)
        return (c, total_m - m)

    result = Layout(0, 0, direction=spec.direction)
    abs_nodes: dict[str, tuple[float, float, float, float]] = {}  # footprint
    abs_shape: dict[str, tuple[float, float, float, float]] = {}
    sx, sy, sw, sh = metrics.shape
    for unit in _walk(roots):
        if unit.node:
            rect = to_final(unit.m0, unit.m1, unit.c0, unit.c0 + node_c)
            shape = (rect[0] + sx, rect[1] + sy, sw, sh)
            result.nodes.append(Placed(unit.node, rect, shape))
            abs_nodes[unit.node.id] = to_abs(rect)
            tile = to_abs(shape)
            # Down or up the page the labels sit in the flow, so edges leave the whole
            # footprint; across the page they leave the tile.
            foot = abs_nodes[unit.node.id]
            abs_shape[unit.node.id] = (
                tile if horizontal else (foot[0], foot[1], tile[2], tile[3])
            )
        else:
            assert unit.group
            rect = to_final(unit.m0, unit.m1, unit.c0, unit.c0 + unit.c_ext)
            result.boxes.append(Box(unit.group, rect, unit.depth))
    result.boxes.sort(key=lambda b: b.depth)

    lane_lo = min(u.c0 for u in _walk(roots)) - 28
    lane_hi = max(u.c0 + u.c_ext for u in _walk(roots)) + 28
    lanes = {"lo": 0, "hi": 0}

    # Edges that share a gap get small offsets so parallel channels do not overlap.
    gap_total: dict[int, int] = {}
    for e in spec.edges:
        for g in {layer[e.source], layer[e.target] - 1}:
            gap_total[g] = gap_total.get(g, 0) + 1
    gap_used: dict[int, int] = {}

    def channel(g: int) -> float:
        used = gap_used.get(g, 0)
        gap_used[g] = used + 1
        total = max(1, gap_total.get(g, 1))
        mid = pos[min(max(g, 0), n_layers - 1)] + node_m + gap_main / 2
        return mid + (used - (total - 1) / 2) * 9

    def clear(points: list[Point], skip: tuple[str, str]) -> bool:
        for a, b in pairwise(points):
            lo_m, hi_m = sorted((a[0], b[0]))
            lo_c, hi_c = sorted((a[1], b[1]))
            for nid, (m0, m1, c0, c1) in abs_nodes.items():
                if nid in skip:
                    continue
                if lo_m < m1 - 2 and hi_m > m0 + 2 and lo_c < c1 - 2 and hi_c > c0 + 2:
                    return False
        return True

    def length(points: list[Point]) -> float:
        return sum(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in pairwise(points))

    def lane(side: str, *, use: bool = True) -> float:
        """Cross position of the next free lane outside the content on one side."""
        position = (
            (lane_lo - 12 * lanes[side])
            if side == "lo"
            else (lane_hi + 12 * lanes[side])
        )
        if use:
            lanes[side] += 1
        return position

    for edge in spec.edges:
        s, t = abs_shape[edge.source], abs_shape[edge.target]
        ls, lt = layer[edge.source], layer[edge.target]
        s_c, t_c = (s[2] + s[3]) / 2, (t[2] + t[3]) / 2
        a = (s[1], s_c)
        skip = (edge.source, edge.target)
        points: list[Point]
        if lt > ls:
            b = (t[0], t_c)
            chan_s, chan_t = channel(ls), channel(lt - 1)
            candidates: list[list[Point]] = []
            if abs(s_c - t_c) < 0.5:
                candidates.append([a, b])
            candidates.append([a, (chan_s, s_c), (chan_s, t_c), b])
            if lt - ls > 1:
                candidates.append([a, (chan_t, s_c), (chan_t, t_c), b])
            found = next((c for c in candidates if clear(c, skip)), None)
            if found is None and lt - ls > 1:
                detours = {
                    side: [
                        a,
                        (chan_s, s_c),
                        (chan_s, lane(side, use=False)),
                        (chan_t, lane(side, use=False)),
                        (chan_t, t_c),
                        b,
                    ]
                    for side in ("lo", "hi")
                }
                ok = {k: v for k, v in detours.items() if clear(v, skip)}
                if ok:
                    side = min(ok, key=lambda k: length(ok[k]))
                    lane(side)  # claim the lane so the next detour sits beside it
                    found = ok[side]
            points = found or candidates[min(1, len(candidates) - 1)]
        elif lt == ls:
            b = (t[1], t_c)
            chan = channel(ls)
            points = [a, (chan, s_c), (chan, t_c), b]
        else:
            b = (t[1], t_c)
            chan_s, chan_t = channel(ls), channel(lt)
            options = {
                side: [
                    a,
                    (chan_s, s_c),
                    (chan_s, lane(side, use=False)),
                    (chan_t, lane(side, use=False)),
                    (chan_t, t_c),
                    b,
                ]
                for side in ("lo", "hi")
            }
            side = min(options, key=lambda k: length(options[k]))
            lane(side)
            points = options[side]
        final = [to_point(m, c) for m, c in points]
        result.routes.append(
            Route(edge, final, _label_spot(final) if edge.label else None)
        )

    _normalise(result, metrics.margin)
    return result


def _walk(units: list[_Unit]) -> list[_Unit]:
    out: list[_Unit] = []
    for u in units:
        out.append(u)
        out.extend(_walk(u.kids))
    return out


def _label_spot(points: list[Point]) -> tuple[float, float, str]:
    a, b = max(
        pairwise(points),
        key=lambda seg: abs(seg[0][0] - seg[1][0]) + abs(seg[0][1] - seg[1][1]),
    )
    if abs(a[1] - b[1]) < 0.5:  # horizontal: label above the line
        return ((a[0] + b[0]) / 2, a[1] - 9, "middle")
    return (a[0] + 10, (a[1] + b[1]) / 2 + 4, "start")  # vertical: label to the right


def _normalise(result: Layout, margin: float) -> None:
    xs: list[float] = []
    ys: list[float] = []
    for p in result.nodes:
        xs += [p.rect[0], p.rect[0] + p.rect[2]]
        ys += [p.rect[1], p.rect[1] + p.rect[3]]
    for b in result.boxes:
        xs += [b.rect[0], b.rect[0] + b.rect[2]]
        ys += [b.rect[1], b.rect[1] + b.rect[3]]
    for r in result.routes:
        xs += [p[0] for p in r.points]
        ys += [p[1] for p in r.points]
        if r.label:
            xs.append(r.label[0] + (60 if r.label[2] == "start" else 40))
            xs.append(r.label[0] - (0 if r.label[2] == "start" else 40))
    dx, dy = margin - min(xs), margin - min(ys)
    result.width = max(xs) + dx + margin
    result.height = max(ys) + dy + margin

    def shift(rect: Rect) -> Rect:
        return (rect[0] + dx, rect[1] + dy, rect[2], rect[3])

    for p in result.nodes:
        p.rect, p.shape = shift(p.rect), shift(p.shape)
    for b in result.boxes:
        b.rect = shift(b.rect)
    for r in result.routes:
        r.points = [(x + dx, y + dy) for x, y in r.points]
        if r.label:
            r.label = (r.label[0] + dx, r.label[1] + dy, r.label[2])
