"""Lay out a statechart: nested containers, ranked children, orthogonal arrows.

Each compound state lays out its children in ranks along the flow (``LR`` or ``TB``),
starting from its initial pseudo-state, so the usual path reads in one direction.
Parallel regions stack across the flow, separated by dashed lines. Sizes are computed
bottom-up, positions top-down; then every transition is routed with A* around the
atomic states (``router.py``) and its label is put on a straight run clear of them.
"""

from __future__ import annotations

import itertools
import math
from collections import deque
from dataclasses import dataclass, field

from . import router
from .model import Machine, State, Transition

Rect = tuple[float, float, float, float]

PAD = 18  # inside a container, around its children
HEADER = 30  # a container's name band
LINE = 15  # one activity line ("entry / start")
REGION_HEADER = 22
MARGIN = 28
TITLE_H = 54
ANY_H = 22
CROSS_GAP = {"LR": 34, "TB": 46}
FINAL_D = 26
HISTORY_D = 26
DOT = 12
LABEL_H = 18


def text_width(text: str, size: float = 12.0, bold: bool = False) -> float:
    """A close estimate of rendered width for system-ui (no font metrics on the server)."""
    total = 0.0
    for ch in text:
        if ch in "il.,:;'|!()[]" or ch == " ":
            total += 0.3
        elif ch in "mwMW@":
            total += 0.86
        elif ch.isupper() or ch.isdigit():
            total += 0.66
        else:
            total += 0.55
    return total * size * (1.06 if bold else 1.0)


def clip(text: str, limit: int = 42) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def activity_lines(st: State, internal: list[Transition]) -> list[str]:
    lines = []
    if st.entry:
        lines.append(clip("entry / " + ", ".join(st.entry)))
    if st.exit:
        lines.append(clip("exit / " + ", ".join(st.exit)))
    for tr in internal:
        lines.append(clip(tr.label))
    return lines


@dataclass
class Block:
    id: str
    kind: str  # atomic final history initial compound parallel region root
    w: float
    h: float
    children: list[tuple[Block, float, float]] = field(default_factory=list)
    header: float = 0.0
    lines: list[str] = field(default_factory=list)
    shape: Rect = (0.0, 0.0, 0.0, 0.0)  # relative to the block
    #: separators between parallel regions, relative to the block
    seps: list[tuple[float, float, float, float]] = field(default_factory=list)


@dataclass
class Box:
    id: str
    kind: str
    x: float
    y: float
    w: float
    h: float
    shape: Rect
    header: float
    lines: list[str]
    label: str
    depth: int


@dataclass
class Edge:
    tid: str | None  # None for an initial arrow
    source: str
    target: str
    points: list[tuple[float, float]]
    label: str = ""
    lx: float = 0.0
    ly: float = 0.0
    lw: float = 0.0
    self_loop: bool = False


@dataclass
class Layout:
    x: float
    y: float
    width: float
    height: float
    boxes: list[Box]
    edges: list[Edge]
    seps: list[tuple[float, float, float, float]]
    any_items: list[tuple[str, str, float]]  # (tid, text, x) under the title
    title_y: float
    any_y: float


class _Layouter:
    def __init__(self, machine: Machine) -> None:
        self.m = machine
        self.states = machine.states
        self.dir = machine.direction
        # targetless transitions are drawn inside their state, not as arrows
        self.internal: dict[str, list[Transition]] = {}
        for tr in machine.transitions:
            if not tr.targets and tr.source:
                self.internal.setdefault(tr.source, []).append(tr)
        self.order = {sid: i for i, sid in enumerate(self.states)}

    # ---- measuring ---------------------------------------------------------------------
    def leaf(self, st: State) -> Block:
        if st.type == "final":
            w = max(FINAL_D, text_width(st.name, 11.5) + 4)
            return Block(
                st.id,
                "final",
                w,
                FINAL_D + 17,
                shape=((w - FINAL_D) / 2, 0, FINAL_D, FINAL_D),
            )
        if st.type == "history":
            w = max(HISTORY_D, text_width(st.name, 11) + 4)
            return Block(
                st.id,
                "history",
                w,
                HISTORY_D + 16,
                shape=((w - HISTORY_D) / 2, 0, HISTORY_D, HISTORY_D),
            )
        lines = activity_lines(st, self.internal.get(st.id, []))
        w = max(
            96.0,
            text_width(st.name, 13, True) + 32,
            *(text_width(line, 11.5) + 24 for line in lines),
        )
        h = 38.0 + (len(lines) * LINE + 8 if lines else 0)
        w, h = math.ceil(w / 2) * 2, math.ceil(h / 2) * 2
        return Block(st.id, "atomic", w, h, lines=lines, shape=(0, 0, w, h))

    def block(self, st: State) -> Block:
        if st.type in ("atomic", "final", "history"):
            return self.leaf(st)
        lines = activity_lines(st, self.internal.get(st.id, []))
        header = HEADER + len(lines) * LINE
        name_w = text_width(st.name, 13, True) + 40
        if st.type == "parallel":
            inner = self.regions(st)
            w = max(inner.w, name_w, *(text_width(x, 11.5) + 28 for x in lines or [""]))
            blk = Block(
                st.id, "parallel", w, header + inner.h, header=header, lines=lines
            )
            dx = (w - inner.w) / 2
            blk.children = [(b, x + dx, y + header) for b, x, y in inner.children]
            blk.seps = [
                (a + dx, b + header, c + dx, d + header) for a, b, c, d in inner.seps
            ]
            if self.dir == "LR":  # regions span the whole width
                blk.children = [(self.widen(b, w), 0, y) for b, _x, y in blk.children]
                blk.seps = [(0, b, w, d) for _a, b, _c, d in blk.seps]
            blk.shape = (0, 0, blk.w, blk.h)
            return blk
        cw, ch, placed = self.arrange(st)
        w = max(
            cw + 2 * PAD, name_w, *(text_width(x, 11.5) + 28 for x in lines or [""])
        )
        h = header + 6 + ch + PAD
        dx = (w - cw) / 2
        blk = Block(st.id, "compound", w, h, header=header, lines=lines)
        blk.children = [(b, x + dx, y + header + 6) for b, x, y in placed]
        blk.shape = (0, 0, w, h)
        return blk

    def widen(self, b: Block, w: float) -> Block:
        if b.kind != "region" or b.w >= w:
            return b
        dx = (w - b.w) / 2
        b.children = [(c, x + dx, y) for c, x, y in b.children]
        b.w = w
        b.shape = (0, 0, w, b.h)
        return b

    def regions(self, st: State) -> Block:
        """The regions of a parallel state, stacked across the flow."""
        blocks = []
        for cid in st.children:
            child = self.states[cid]
            if child.type in ("compound",):
                cw, ch, placed = self.arrange(child)
                w = max(cw + 2 * PAD, text_width(child.name, 11, True) + 2 * PAD)
                dx = (w - cw) / 2
                reg = Block(
                    cid, "region", w, REGION_HEADER + ch + PAD, header=REGION_HEADER
                )
                reg.children = [(b, x + dx, y + REGION_HEADER) for b, x, y in placed]
                reg.shape = (0, 0, reg.w, reg.h)
            else:
                inner = self.block(child)
                reg = Block(
                    f"{cid}\0band", "band", inner.w + 2 * PAD, inner.h + 2 * PAD
                )
                reg.children = [(inner, PAD, PAD)]
            blocks.append(reg)
        out = Block(st.id, "regions", 0, 0)
        pos = 0.0
        if self.dir == "LR":
            out.w = max(b.w for b in blocks)
            for i, b in enumerate(blocks):
                out.children.append((b, (out.w - b.w) / 2, pos))
                pos += b.h
                if i < len(blocks) - 1:
                    out.seps.append((0, pos, out.w, pos))
            out.h = pos
        else:
            out.h = max(b.h for b in blocks)
            for i, b in enumerate(blocks):
                b.h = out.h
                b.shape = (0, 0, b.w, b.h)
                out.children.append((b, pos, 0))
                pos += b.w
                if i < len(blocks) - 1:
                    out.seps.append((pos, 0, pos, out.h))
            out.w = pos
        return out

    def child_under(self, container: str, state_id: str) -> str | None:
        cursor: str | None = state_id
        while cursor is not None and cursor != "":
            st = self.states[cursor]
            if st.parent == container:
                return cursor
            cursor = st.parent
        return None

    def arrange(
        self, st: State
    ) -> tuple[float, float, list[tuple[Block, float, float]]]:
        """Children of a compound state (or the root) in ranks along the flow."""
        kids = list(st.children)
        blocks = {cid: self.block(self.states[cid]) for cid in kids}
        init_id = f"{st.id}\0init"
        nodes = list(kids)
        if st.initial:
            blocks[init_id] = Block(
                init_id, "initial", DOT, DOT, shape=(0, 0, DOT, DOT)
            )
            nodes.insert(0, init_id)
        succ: dict[str, list[str]] = {n: [] for n in nodes}
        label_w: dict[tuple[str, str], float] = {}
        if st.initial:
            succ[init_id].append(st.initial)
        for tr in self.m.transitions:
            if not tr.source or not tr.targets:
                continue
            a = self.child_under(st.id, tr.source) if tr.source != st.id else None
            for target in tr.targets:
                b = self.child_under(st.id, target)
                if a and b and a != b:
                    succ[a].append(b)
                    key = (a, b)
                    label_w[key] = max(
                        label_w.get(key, 0), text_width(tr.label, 11.5) + 14
                    )
        # ranks: breadth first from the initial state, then anything left over
        rank: dict[str, int] = {}
        start = [init_id] if st.initial else nodes[:1]
        for s in start:
            rank[s] = 0
        queue = deque(start)
        pending = [n for n in nodes if n not in rank]
        while True:
            while queue:
                cur = queue.popleft()
                for nxt in succ[cur]:
                    if nxt not in rank:
                        rank[nxt] = rank[cur] + 1
                        queue.append(nxt)
            pending = [n for n in pending if n not in rank]
            if not pending:
                break
            n = pending[0]
            preds = [rank[p] for p in nodes if p in rank and n in succ[p]]
            rank[n] = (
                (max(preds) + 1) if preds else (max(rank.values(), default=-1) + 1)
            )
            queue.append(n)
        layers: list[list[str]] = [[] for _ in range(max(rank.values()) + 1)]
        for n in nodes:
            layers[rank[n]].append(n)
        # barycentre ordering: two sweeps against the previous layer
        neighbours: dict[str, set[str]] = {n: set() for n in nodes}
        for a, outs in succ.items():
            for b in outs:
                neighbours[a].add(b)
                neighbours[b].add(a)
        for _ in range(2):
            for i in range(1, len(layers)):
                pos = {n: j for j, n in enumerate(layers[i - 1])}

                def key(n: str, pos: dict[str, int] = pos) -> float:
                    near = [pos[x] for x in neighbours[n] if x in pos]
                    return sum(near) / len(near) if near else math.inf

                layers[i].sort(key=lambda n: (key(n), self.order.get(n, -1)))
        lr = self.dir == "LR"
        main = (lambda b: b.w) if lr else (lambda b: b.h)
        cross = (lambda b: b.h) if lr else (lambda b: b.w)
        gap_cross = CROSS_GAP[self.dir]
        sizes = []
        for layer in layers:
            m = max(main(blocks[n]) for n in layer)
            c = sum(cross(blocks[n]) for n in layer) + gap_cross * (len(layer) - 1)
            sizes.append((m, c))
        total_cross = max(c for _m, c in sizes)
        placed: list[tuple[Block, float, float]] = []
        at = 0.0
        for i, layer in enumerate(layers):
            m, c = sizes[i]
            off = (total_cross - c) / 2
            for n in layer:
                b = blocks[n]
                along = at + (m - main(b)) / 2
                placed.append((b, along, off) if lr else (b, off, along))
                off += cross(b) + gap_cross
            if i < len(layers) - 1:
                widest = 0.0
                for a in layer:
                    for b in layers[i + 1]:
                        widest = max(
                            widest, label_w.get((a, b), 0), label_w.get((b, a), 0)
                        )
                if layer == [init_id]:
                    gap = 34.0
                elif lr:
                    gap = min(max(widest + 34, 64), 260)
                else:
                    gap = 70.0
                at += m + gap
            else:
                at += m
        w, h = (at, total_cross) if lr else (total_cross, at)
        return w, h, placed

    # ---- placing -----------------------------------------------------------------------
    def flatten(
        self, blk: Block, x: float, y: float, out: list[Box], seps: list
    ) -> None:
        sx, sy, sw, sh = blk.shape
        st = self.states.get(blk.id)
        if blk.kind not in ("regions", "band"):
            out.append(
                Box(
                    blk.id,
                    blk.kind,
                    x,
                    y,
                    blk.w,
                    blk.h,
                    (x + sx, y + sy, sw, sh),
                    blk.header,
                    blk.lines,
                    st.name if st else "",
                    st.depth if st else 0,
                )
            )
        for a, b, c, d in blk.seps:
            seps.append((x + a, y + b, x + c, y + d))
        for child, cx, cy in blk.children:
            self.flatten(child, x + cx, y + cy, out, seps)

    def run(self) -> Layout:
        root = self.states[""]
        any_trs = [t for t in root.transitions if t.kind != "done"]
        top = TITLE_H + (ANY_H if any_trs else 0)
        if root.type == "parallel":
            content = self.regions(root)
        else:
            cw, ch, placed = self.arrange(root)
            content = Block("", "regions", cw, ch, children=placed)
        boxes: list[Box] = []
        seps: list[tuple[float, float, float, float]] = []
        self.flatten(content, MARGIN, top, boxes, seps)
        edges = self.route(boxes, seps, content, top)
        # the drawing's extent: boxes, arrows and labels
        xs = [MARGIN + content.w + MARGIN, 360.0]
        ys = [top + content.h + MARGIN]
        x0, y0 = 0.0, 0.0
        for e in edges:
            for px, py in e.points:
                xs.append(px + MARGIN)
                ys.append(py + MARGIN)
                x0 = min(x0, px - MARGIN)
                y0 = min(y0, py - MARGIN)
            if e.label:
                xs.append(e.lx + e.lw / 2 + 12)
                x0 = min(x0, e.lx - e.lw / 2 - 12)
        any_items = []
        ax = MARGIN + 74
        for t in any_trs:
            text = (
                t.label + " → " + ", ".join(self.states[x].name for x in t.targets)
                if t.targets
                else t.label
            )
            any_items.append((t.id, text, ax))
            ax += text_width(text, 11.5) + 26
        xs.append(ax + MARGIN)
        return Layout(
            x=x0,
            y=y0,
            width=max(xs) - x0,
            height=max(ys) - y0,
            boxes=boxes,
            edges=edges,
            seps=seps,
            any_items=any_items,
            title_y=30,
            any_y=TITLE_H + 6,
        )

    # ---- routing -----------------------------------------------------------------------
    def route(
        self,
        boxes: list[Box],
        seps: list[tuple[float, float, float, float]],
        content: Block,
        top: float,
    ) -> list[Edge]:
        by_id = {b.id: b for b in boxes}
        solid = [
            b for b in boxes if b.kind in ("atomic", "final", "history", "initial")
        ]
        obstacles: list[Rect] = [b.shape for b in solid]
        label_boxes: list[Rect] = []
        for b in boxes:
            if b.kind in ("final", "history"):  # their name, under the circle
                label_boxes.append((b.x, b.y + b.shape[3], b.w, b.h - b.shape[3]))
            elif b.kind in ("compound", "parallel"):
                label_boxes.append(
                    (b.x + 10, b.y + 6, text_width(b.label, 13, True) + 8, 18)
                )
            elif b.kind == "region":
                label_boxes.append(
                    (b.x + 10, b.y + 4, text_width(b.label, 11, True) + 8, 14)
                )
        grid = router.Grid(
            obstacles + label_boxes + [(0, 0, MARGIN * 2 + content.w, top - 8)],
            cell=10,
            margin=8,
            pad=70,
        )
        for b in boxes:
            if b.kind in ("compound", "parallel", "region"):
                grid.wall(b.x, b.y, b.w, b.h)
        for x1, y1, x2, y2 in seps:
            grid.mark([(x1, y1), (x2, y2)])

        plans: list[tuple[str | None, str, str, str]] = []  # tid, source, target, label
        for b in boxes:
            if b.kind == "initial":
                parent = self.states[b.id.split("\0")[0]]
                if parent.initial:
                    plans.append((None, b.id, parent.initial, ""))
        for tr in self.m.transitions:
            if not tr.source or not tr.targets:
                continue
            for i, target in enumerate(tr.targets):
                if target in by_id and tr.source in by_id:
                    plans.append((tr.id, tr.source, target, tr.label if i == 0 else ""))

        # sides first, so the arrows sharing a side can be spread along it
        sides: list[tuple[int, int]] = []
        ends: dict[tuple[str, int], list[tuple[int, int]]] = {}
        for k, (_tid, s, t, _l) in enumerate(plans):
            if s == t:
                sides.append((-1, -1))
                continue
            a_dir, b_dir = self.sides(by_id[s], by_id[t])
            sides.append((a_dir, b_dir))
            ends.setdefault((s, a_dir), []).append((k, 0))
            ends.setdefault((t, b_dir), []).append((k, 1))
        anchor: dict[tuple[int, int], tuple[float, float]] = {}
        for (bid, side), items in ends.items():
            box = by_id[bid]
            x, y, w, h = box.shape
            horizontal = side in (1, 3)  # spread along x on top and bottom sides
            length = w if horizontal else h
            round_shape = box.kind in ("final", "history", "initial")

            def other(item: tuple[int, int], horizontal: bool = horizontal) -> float:
                k, end = item
                ob = by_id[plans[k][2] if end == 0 else plans[k][1]]
                ox, oy, ow, oh = ob.shape
                return ox + ow / 2 if horizontal else oy + oh / 2

            items.sort(key=other)
            n = len(items)
            step = 0.0 if round_shape else min(length * 0.7 / max(n, 1), 24.0)
            for i, item in enumerate(items):
                off = (i - (n - 1) / 2) * step
                if side == 0:
                    p = (x + w, y + h / 2 + off)
                elif side == 2:
                    p = (x, y + h / 2 + off)
                elif side == 1:
                    p = (x + w / 2 + off, y + h)
                else:
                    p = (x + w / 2 + off, y)
                anchor[item] = p

        edges: list[Edge] = []
        loops: dict[str, int] = {}
        placed_labels: list[Rect] = []
        # short arrows first: they have the fewest ways around, so they get first pick
        order = sorted(
            range(len(plans)),
            key=lambda k: (
                plans[k][0] is not None,
                self.distance(by_id[plans[k][1]], by_id[plans[k][2]]),
            ),
        )
        results: dict[int, Edge] = {}
        for k in order:
            tid, s, t, label = plans[k]
            if s == t:
                n = loops.get(s, 0)
                loops[s] = n + 1
                x, y, w, h = by_id[s].shape
                inset = 14 + n * 10
                out = 20 + n * 12
                pts = [
                    (x + w - inset - 16, y),
                    (x + w - inset - 16, y - out),
                    (x + w + out, y - out),
                    (x + w + out, y + min(h / 2, 18 + n * 6)),
                    (x + w, y + min(h / 2, 18 + n * 6)),
                ]
                results[k] = Edge(tid, s, t, pts, label, self_loop=True)
                continue
            a_dir, b_dir = sides[k]
            pts = self.straight(
                by_id[s],
                by_id[t],
                anchor[(k, 0)],
                anchor[(k, 1)],
                a_dir,
                b_dir,
                obstacles,
            )
            if pts:
                grid.mark(pts)
            else:
                pts = router.route(grid, anchor[(k, 0)], a_dir, anchor[(k, 1)], b_dir)
            results[k] = Edge(tid, s, t, pts, label)
        for k in range(len(plans)):  # labels in source order, each avoiding the last
            e = results[k]
            if e.label:
                lw = text_width(e.label, 11.5) + 14
                if e.self_loop:
                    lx = e.points[2][0] - 6
                    ly = e.points[1][1] - LABEL_H / 2 - 4
                else:
                    lx, ly = place_label(
                        e.points, lw, obstacles + label_boxes + placed_labels
                    )
                e.lx, e.ly, e.lw = lx, ly, lw
                placed_labels.append((lx - lw / 2, ly - LABEL_H / 2, lw, LABEL_H))
            edges.append(e)
        return edges

    def straight(
        self,
        a: Box,
        b: Box,
        pa: tuple[float, float],
        pb: tuple[float, float],
        a_dir: int,
        b_dir: int,
        obstacles: list[Rect],
    ) -> list[tuple[float, float]] | None:
        """A straight arrow when the two sides face each other and nothing is between."""
        if (
            b_dir != (a_dir + 2) % 4
            or self.inside(a.id, b.id)
            or self.inside(b.id, a.id)
        ):
            return None
        horizontal = a_dir in (0, 2)
        k = 1 if horizontal else 0  # the shared coordinate

        def span(box: Box) -> tuple[float, float]:
            x, y, w, h = box.shape
            lo, size = (y, h) if horizontal else (x, w)
            if box.kind in ("final", "history", "initial"):
                return lo + size / 2, lo + size / 2
            return lo + 6, lo + size - 6

        (alo, ahi), (blo, bhi) = span(a), span(b)
        lo, hi = max(alo, blo), min(ahi, bhi)
        if lo > hi:
            return None
        if lo <= pa[k] <= hi:
            c = pa[k]
        elif lo <= pb[k] <= hi:
            c = pb[k]
        else:
            c = (lo + hi) / 2
        p1 = (pa[0], c) if horizontal else (c, pa[1])
        p2 = (pb[0], c) if horizontal else (c, pb[1])
        forward = p2[1 - k] - p1[1 - k]
        if (a_dir in (0, 1) and forward <= 0) or (a_dir in (2, 3) and forward >= 0):
            return None
        x1, x2 = sorted((p1[0], p2[0]))
        y1, y2 = sorted((p1[1], p2[1]))
        for ox, oy, ow, oh in obstacles:
            if (ox, oy, ow, oh) in (a.shape, b.shape):
                continue
            if x1 < ox + ow + 2 and ox - 2 < x2 and y1 < oy + oh + 2 and oy - 2 < y2:
                return None
        return [p1, p2]

    @staticmethod
    def distance(a: Box, b: Box) -> float:
        ax, ay, aw, ah = a.shape
        bx, by, bw, bh = b.shape
        return abs(ax + aw / 2 - bx - bw / 2) + abs(ay + ah / 2 - by - bh / 2)

    def sides(self, a: Box, b: Box) -> tuple[int, int]:
        ax, ay, aw, ah = a.shape
        bx, by, bw, bh = b.shape
        acx, acy, bcx, bcy = ax + aw / 2, ay + ah / 2, bx + bw / 2, by + bh / 2

        def nearest_side(outer: Rect, px: float, py: float) -> int:
            ox, oy, ow, oh = outer
            gaps = [ox + ow - px, oy + oh - py, px - ox, py - oy]  # E S W N
            return gaps.index(min(gaps))

        if self.inside(
            a.id, b.id
        ):  # leaving for an enclosing state: exit through its border
            d = nearest_side(b.shape, acx, acy)
            return d, (d + 2) % 4
        if self.inside(b.id, a.id):  # a container entering one of its own children
            d = nearest_side(a.shape, bcx, bcy)
            return (d + 2) % 4, d
        ox = min(ax + aw, bx + bw) - max(ax, bx)
        oy = min(ay + ah, by + bh) - max(ay, by)
        if oy > 0 >= ox:
            horizontal = True
        elif ox > 0 >= oy:
            horizontal = False
        else:
            dx, dy = bcx - acx, bcy - acy
            prefer = 1.0 if self.dir == "LR" else 0.6
            horizontal = abs(dx) * prefer >= abs(dy)
        if horizontal:
            return (0, 2) if bcx > acx else (2, 0)
        return (1, 3) if bcy > acy else (3, 1)

    def inside(self, inner: str, outer: str) -> bool:
        base = inner.split("\0")[0]
        return bool(outer) and "\0" not in outer and base.startswith(outer + ".")


def place_label(
    points: list[tuple[float, float]], width: float, avoid: list[Rect]
) -> tuple[float, float]:
    """A spot on the arrow for its label, clear of states and of labels placed before.

    Runs are tried longest first (the run with the arrowhead last); on each, the middle,
    then points toward either end; then the same spots nudged off the line, so labels of
    parallel arrows stack instead of covering each other.
    """
    runs = [(a, b) for a, b in itertools.pairwise(points) if a != b]
    if not runs:
        return points[0]
    last = len(runs) - 1
    ranked = sorted(
        range(len(runs)),
        key=lambda i: (
            i == last and last > 0,
            -math.hypot(runs[i][1][0] - runs[i][0][0], runs[i][1][1] - runs[i][0][1]),
        ),
    )
    spots: list[tuple[float, float]] = []
    for i in ranked:
        (ax, ay), (bx, by) = runs[i]
        for t in (0.5, 0.32, 0.68, 0.2, 0.8):
            spots.append((ax + (bx - ax) * t, ay + (by - ay) * t))
    shifted = []
    for x, y in spots[:5]:
        (ax, ay), (bx, by) = runs[ranked[0]]
        if ay == by:  # horizontal: stack above or below
            shifted += [(x, y - LABEL_H - 2), (x, y + LABEL_H + 2)]
        else:  # vertical: beside the line
            shifted += [(x + width / 2 + 4, y), (x - width / 2 - 4, y)]
    half_w, half_h = width / 2 + 3, LABEL_H / 2 + 2
    for x, y in spots + shifted:
        if not any(
            x - half_w < rx + rw
            and rx < x + half_w
            and y - half_h < ry + rh
            and ry < y + half_h
            for rx, ry, rw, rh in avoid
        ):
            return (x, y)
    return spots[0]


def layout(machine: Machine) -> Layout:
    return _Layouter(machine).run()
