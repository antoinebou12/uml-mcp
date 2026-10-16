"""Orthogonal edge routing with A* on a grid.

Boxes are obstacles. The cost of a path is its length, plus a penalty for every turn (so
edges stay straight where they can) and for running over or crossing edges that were
routed before it (so arrows spread apart instead of piling up). The same algorithm lives
in ``assets/router.js`` so that an arrow is routed again while its box is dragged in the
browser. It uses integer costs and a fixed expansion order so both give identical paths;
``tests/test_plugin_d3.py`` checks that with Node when it is installed.
"""

from __future__ import annotations

import heapq
import itertools
import math
from collections.abc import Sequence

Point = tuple[float, float]
Rect = tuple[float, float, float, float]  # x, y, width, height

# A turn costs three steps, so an arrow bends only when going around a box or
# reaching a different row is cheaper than a long detour. Running along another
# arrow costs four steps and crossing one a step and a half, so arrows spread
# apart instead of piling up, and cross rarely.
STEP, TURN, OVERLAP, CROSS = 10, 30, 40, 16
LABEL_MARGIN = 3  # clear space kept between a label and a box
MAX_EXPANSIONS = 60000
#: E, S, W, N: the order in which neighbours are tried (part of the contract with the JS)
DIRS = ((1, 0), (0, 1), (-1, 0), (0, -1))


def _snap(value: float, origin: float, cell: float) -> int:
    return math.floor((value - origin) / cell + 0.5)


class Grid:
    """Grid points over the diagram, with the points inside any box marked as blocked."""

    def __init__(
        self,
        rects: Sequence[Rect],
        *,
        cell: int = 10,
        margin: int = 8,
        pad: int = 80,
    ) -> None:
        self.cell = cell
        self.margin = margin
        # a whole number of cells, so a stub from an anchor on the grid is on the grid too
        self.stub = math.ceil((margin + cell) / cell) * cell
        xs = [r[0] for r in rects] + [r[0] + r[2] for r in rects] or [0.0]
        ys = [r[1] for r in rects] + [r[1] + r[3] for r in rects] or [0.0]
        self.ox = math.floor((min(xs) - pad) / cell) * cell
        self.oy = math.floor((min(ys) - pad) / cell) * cell
        self.cols = math.ceil((max(xs) + pad - self.ox) / cell) + 1
        self.rows = math.ceil((max(ys) + pad - self.oy) / cell) + 1
        self.blocked: set[int] = set()
        self.usage: dict[int, int] = {}
        for x, y, w, h in rects:
            lo_x = _snap(x - margin, self.ox, cell) - 1
            hi_x = _snap(x + w + margin, self.ox, cell) + 1
            lo_y = _snap(y - margin, self.oy, cell) - 1
            hi_y = _snap(y + h + margin, self.oy, cell) + 1
            for iy in range(max(lo_y, 0), min(hi_y, self.rows - 1) + 1):
                py = self.oy + iy * cell
                if not (y - margin < py < y + h + margin):
                    continue
                for ix in range(max(lo_x, 0), min(hi_x, self.cols - 1) + 1):
                    px = self.ox + ix * cell
                    if x - margin < px < x + w + margin:
                        self.blocked.add(iy * self.cols + ix)

    def index(self, x: float, y: float) -> int:
        ix = min(max(_snap(x, self.ox, self.cell), 0), self.cols - 1)
        iy = min(max(_snap(y, self.oy, self.cell), 0), self.rows - 1)
        return iy * self.cols + ix

    def point(self, index: int) -> Point:
        return (
            self.ox + (index % self.cols) * self.cell,
            self.oy + (index // self.cols) * self.cell,
        )

    def mark(self, points: list[Point]) -> None:
        """Remember an edge so later edges avoid running over it."""
        for (x1, y1), (x2, y2) in itertools.pairwise(points):
            if y1 == y2:
                bit, a, b = (
                    1,
                    _snap(x1, self.ox, self.cell),
                    _snap(x2, self.ox, self.cell),
                )
                row = _snap(y1, self.oy, self.cell)
                for ix in range(min(a, b), max(a, b) + 1):
                    if 0 <= ix < self.cols and 0 <= row < self.rows:
                        self.usage[row * self.cols + ix] = (
                            self.usage.get(row * self.cols + ix, 0) | bit
                        )
            elif x1 == x2:
                bit, a, b = (
                    2,
                    _snap(y1, self.oy, self.cell),
                    _snap(y2, self.oy, self.cell),
                )
                col = _snap(x1, self.ox, self.cell)
                for iy in range(min(a, b), max(a, b) + 1):
                    if 0 <= iy < self.rows and 0 <= col < self.cols:
                        self.usage[iy * self.cols + col] = (
                            self.usage.get(iy * self.cols + col, 0) | bit
                        )


def _astar(grid: Grid, start: int, goal: int, start_dir: int) -> list[int] | None:
    cols = grid.cols
    blocked = grid.blocked - {start, goal}
    gx, gy = goal % cols, goal // cols
    g_cost: dict[int, int] = {start * 4 + start_dir: 0}
    came: dict[int, int] = {}
    sx, sy = start % cols, start // cols
    h0 = STEP * (abs(sx - gx) + abs(sy - gy))
    heap: list[tuple[int, int, int, int]] = [(h0, h0, 0, start * 4 + start_dir)]
    seq = 0
    expansions = 0
    closed: set[int] = set()
    while heap:
        _f, _h, _s, state = heapq.heappop(heap)
        if state in closed:
            continue
        closed.add(state)
        idx, d = divmod(state, 4)
        if idx == goal:
            path = [idx]
            while state in came:
                state = came[state]
                path.append(state // 4)
            path.reverse()
            return path
        expansions += 1
        if expansions > MAX_EXPANSIONS:
            return None
        x, y = idx % cols, idx // cols
        base = g_cost[state]
        for nd in range(4):
            if nd == (d + 2) % 4:
                continue
            nx, ny = x + DIRS[nd][0], y + DIRS[nd][1]
            if nx < 0 or ny < 0 or nx >= cols or ny >= grid.rows:
                continue
            nidx = ny * cols + nx
            if nidx in blocked:
                continue
            cost = base + STEP + (TURN if nd != d else 0)
            used = grid.usage.get(nidx, 0)
            if used:
                cost += OVERLAP if used & (1 if nd % 2 == 0 else 2) else CROSS
            nstate = nidx * 4 + nd
            if cost < g_cost.get(nstate, 1 << 60):
                g_cost[nstate] = cost
                came[nstate] = state
                seq += 1
                h = STEP * (abs(nx - gx) + abs(ny - gy))
                heapq.heappush(heap, (cost + h, h, seq, nstate))
    return None


def simplify(points: list[Point]) -> list[Point]:
    """Drop repeated points and points in the middle of a straight run."""
    out: list[Point] = []
    for p in points:
        if out and out[-1] == p:
            continue
        out.append(p)
    result: list[Point] = []
    for i, p in enumerate(out):
        if 0 < i < len(out) - 1:
            a, b = out[i - 1], out[i + 1]
            if (p[0] - a[0]) * (b[1] - p[1]) - (p[1] - a[1]) * (b[0] - p[0]) == 0:
                continue
        result.append(p)
    return result


def _elbow(stub: Point, snapped: Point, axis_horizontal: bool) -> list[Point]:
    mid = (stub[0], snapped[1]) if axis_horizontal else (snapped[0], stub[1])
    return [stub, mid, snapped]


def route(grid: Grid, a: Point, a_dir: int, b: Point, b_dir: int) -> list[Point]:
    """An orthogonal polyline from anchor ``a`` to anchor ``b``.

    ``a_dir`` and ``b_dir`` are the outward directions (indexes into ``DIRS``) of the
    sides the edge leaves and enters through. The result is marked on the grid.
    """
    s = grid.stub
    sa = (a[0] + DIRS[a_dir][0] * s, a[1] + DIRS[a_dir][1] * s)
    sb = (b[0] + DIRS[b_dir][0] * s, b[1] + DIRS[b_dir][1] * s)
    start, goal = grid.index(*sa), grid.index(*sb)
    cells = _astar(grid, start, goal, a_dir)
    if cells is None:  # no clear path: a plain three-segment route is still orthogonal
        mid_x = (sa[0] + sb[0]) / 2
        points = simplify([a, sa, (mid_x, sa[1]), (mid_x, sb[1]), sb, b])
    else:
        grid_points = [grid.point(i) for i in cells]
        points = simplify(
            [a]
            + _elbow(sa, grid_points[0], a_dir % 2 == 0)
            + grid_points[1:-1]
            + list(reversed(_elbow(sb, grid_points[-1], b_dir % 2 == 0)))
            + [b]
        )
    grid.mark(points)
    return points


def label_point(
    points: Sequence[Point], width: float, boxes: Sequence[Rect] = ()
) -> Point:
    """Where an arrow's label goes: on a straight run that is long enough, clear of the boxes.

    Runs are tried best first: a run that is long enough and does not carry the arrowhead,
    then one that does, then the rest, the longer first (the one nearest the source on a tie).
    On each run the middle is tried, and the quarter points of a long run. The first spot
    where the label (``width`` wide, 16 tall, plus a margin) touches no box wins. When every
    spot touches a box, the middle of the best run is used. The browser applies the same rule
    (``labelPoint`` in router.js) while a box is being dragged.
    """
    runs = [
        (math.hypot(b[0] - a[0], b[1] - a[1]), a, b)
        for a, b in itertools.pairwise(points)
    ]
    if not runs:
        return points[0]
    need = width + 24
    last = len(runs) - 1

    def rank(item: tuple[int, tuple[float, Point, Point]]) -> tuple[int, float]:
        index, (length, _a, _b) = item
        head = index == last and last > 0
        fits = length >= need
        return (0 if fits and not head else 1 if fits else 2, -length)

    candidates: list[Point] = []
    for _index, (length, a, b) in sorted(enumerate(runs), key=rank):
        for t in (0.5, 0.25, 0.75) if length >= 2 * need else (0.5,):
            candidates.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    half_w, half_h = width / 2 + LABEL_MARGIN, 8 + LABEL_MARGIN
    for x, y in candidates:
        if not any(
            x - half_w < bx + bw
            and bx < x + half_w
            and y - half_h < by + bh
            and by < y + half_h
            for bx, by, bw, bh in boxes
        ):
            return (x, y)
    return candidates[0]


def _fmt(value: float) -> str:
    text = f"{value:.1f}"
    return text.removesuffix(".0")


def rounded_path(points: list[Point], radius: float = 8.0) -> str:
    """An SVG path through ``points`` with rounded corners."""
    if not points:
        return ""
    parts = [f"M{_fmt(points[0][0])},{_fmt(points[0][1])}"]
    for i in range(1, len(points) - 1):
        p, prev, nxt = points[i], points[i - 1], points[i + 1]
        len1 = math.hypot(p[0] - prev[0], p[1] - prev[1])
        len2 = math.hypot(nxt[0] - p[0], nxt[1] - p[1])
        r = min(radius, len1 / 2, len2 / 2)
        if r <= 0:
            parts.append(f"L{_fmt(p[0])},{_fmt(p[1])}")
            continue
        ax = p[0] - (p[0] - prev[0]) / len1 * r
        ay = p[1] - (p[1] - prev[1]) / len1 * r
        bx = p[0] + (nxt[0] - p[0]) / len2 * r
        by = p[1] + (nxt[1] - p[1]) / len2 * r
        parts.append(
            f"L{_fmt(ax)},{_fmt(ay)}Q{_fmt(p[0])},{_fmt(p[1])} {_fmt(bx)},{_fmt(by)}"
        )
    parts.append(f"L{_fmt(points[-1][0])},{_fmt(points[-1][1])}")
    return "".join(parts)


def path_midpoint(points: list[Point]) -> Point:
    """The point halfway along the polyline (where an edge label goes)."""
    lengths = [
        math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in itertools.pairwise(points)
    ]
    half = sum(lengths) / 2
    for (a, b), length in zip(itertools.pairwise(points), lengths, strict=False):
        if half <= length and length > 0:
            t = half / length
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        half -= length
    return points[-1]
