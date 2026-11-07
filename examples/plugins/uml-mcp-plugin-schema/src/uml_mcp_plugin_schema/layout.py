"""Auto layout: table cards in layers by foreign-key direction, groups as containers,
and orthogonal edges that leave and enter at the exact column rows.

Referenced tables sit on the left, the tables that point at them to their right. A group
is laid out on its own first (the same rule inside it), then placed as one block, so a
container never overlaps another. Edges are routed around the cards: a candidate path is
scored by length and bends and kept only when no segment crosses a card.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

from .model import Relation, Schema, Table

HEADER = 34
ROW = 24
FOOT = 6
MIN_W, MAX_W = 196, 400
GROUP_PAD, GROUP_TOP = 18, 36
V_GAP = 34
MARGIN = 28
TITLE_H = 48
STUB = 26  # the straight run out of a card, room for the crow's foot
MAX_COLUMN = 1400  # a column of unrelated tables wraps past this height


def text_width(text: str, size: float = 12.5, mono: bool = False) -> float:
    if mono:
        return len(text) * size * 0.6
    wide = sum(1 for ch in text if ch in "MWmw@%")
    narrow = sum(1 for ch in text if ch in "il.,:;|!'()[]ftjI1 ")
    return (
        (len(text) - wide - narrow) * size * 0.56
        + wide * size * 0.85
        + narrow * size * 0.3
    )


def clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


@dataclass
class Card:
    table: Table
    x: float = 0
    y: float = 0
    w: float = 0
    h: float = 0
    name_w: float = 0  # width of the name column inside the card

    def row_y(self, column: str) -> float:
        key = column.lower()
        for i, c in enumerate(self.table.columns):
            if c.name.lower() == key:
                return self.y + HEADER + i * ROW + ROW / 2
        return self.y + HEADER / 2

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h


@dataclass
class GroupBox:
    name: str
    x: float
    y: float
    w: float
    h: float
    tables: list[str]


@dataclass
class Route:
    relation: Relation
    points: list[tuple[float, float]]
    #: +1 when the path leaves the source card to the right, -1 to the left
    source_dir: int
    target_dir: int


@dataclass
class Layout:
    cards: dict[str, Card]
    groups: list[GroupBox]
    routes: list[Route]
    width: float
    height: float
    top: float = TITLE_H


@dataclass
class _Block:
    """A unit placed by the outer layout: one table, or a whole group."""

    key: str
    cards: list[Card]
    w: float = 0
    h: float = 0
    x: float = 0
    y: float = 0
    group: str = ""
    offsets: dict[str, tuple[float, float]] = field(default_factory=dict)


def _size(table: Table) -> Card:
    name_w = max((text_width(clip(c.name, 32)) for c in table.columns), default=40)
    type_w = max(
        (text_width(clip(c.type, 24), 11, mono=True) for c in table.columns), default=0
    )
    badges = (
        max(
            (
                (26 if c.unique and not c.pk else 0)
                + (30 if c.nullable and not c.pk else 0)
            )
            for c in table.columns
        )
        if table.columns
        else 0
    )
    row_w = 12 + 18 + 6 + name_w + 16 + type_w + (8 + badges if badges else 0) + 14
    head_w = 46 + text_width(clip(table.name, 40), 14) + 30
    w = min(MAX_W, max(MIN_W, row_w, head_w))
    h = HEADER + max(1, len(table.columns)) * ROW + FOOT
    return Card(table, w=round(w), h=h, name_w=name_w)


def _layers(nodes: list[str], edges: list[tuple[str, str]]) -> dict[str, int]:
    """Longest-path layering, parents (edge targets) first. Cycles are broken."""
    parents: dict[str, list[str]] = {n: [] for n in nodes}
    for child, parent in edges:
        if child != parent and parent not in parents[child]:
            parents[child].append(parent)
    layer: dict[str, int] = {}
    visiting: set[str] = set()

    def depth(n: str) -> int:
        if n in layer:
            return layer[n]
        if n in visiting:
            return -1  # a back edge: ignore it
        visiting.add(n)
        best = 0
        for p in parents[n]:
            d = depth(p)
            if d >= 0:
                best = max(best, d + 1)
        visiting.discard(n)
        layer[n] = best
        return best

    for n in nodes:
        depth(n)
    return layer


def _order(
    columns: list[list[str]], edges: list[tuple[str, str]], passes: int = 4
) -> list[list[str]]:
    """Barycentre ordering inside each column to shorten and uncross edges."""
    neighbours: dict[str, set[str]] = {}
    for a, b in edges:
        if a != b:
            neighbours.setdefault(a, set()).add(b)
            neighbours.setdefault(b, set()).add(a)
    for step in range(passes):
        pos = {n: i / max(1, len(col)) for col in columns for i, n in enumerate(col)}
        sweep = (
            range(1, len(columns)) if step % 2 == 0 else range(len(columns) - 2, -1, -1)
        )
        for ci in sweep:
            col = columns[ci]
            here = set(col)
            bary: dict[str, float] = {}
            for n in col:
                ns = [
                    pos[m] for m in neighbours.get(n, ()) if m in pos and m not in here
                ]
                bary[n] = sum(ns) / len(ns) if ns else pos[n]
            columns[ci] = sorted(col, key=bary.__getitem__)
            pos.update({n: i / max(1, len(col)) for i, n in enumerate(columns[ci])})
    return columns


def _arrange(
    items: dict[str, tuple[float, float]],
    edges: list[tuple[str, str]],
    order: list[str],
) -> tuple[dict[str, tuple[float, float]], float, float]:
    """Place sized items in layered columns. Returns top-left offsets and the extent."""
    layer = _layers(order, edges)
    connected = {n for e in edges for n in e if e[0] != e[1]}
    lonely = [n for n in order if n not in connected]
    columns: list[list[str]] = [[] for _ in range(max(layer.values(), default=0) + 1)]
    for n in order:
        if n in connected or len(lonely) == len(order):
            columns[layer[n]].append(n)
    columns = [c for c in columns if c]
    columns = _order(columns, edges)
    if lonely and len(lonely) < len(order):
        # unrelated tables go to the far right, wrapped into columns of a sensible height
        tallest = max(
            (sum(items[n][1] + V_GAP for n in col) for col in columns), default=0
        )
        limit = max(tallest, 520.0)
        cur: list[str] = []
        height = 0.0
        for n in lonely:
            if cur and height + items[n][1] > limit:
                columns.append(cur)
                cur, height = [], 0.0
            cur.append(n)
            height += items[n][1] + V_GAP
        columns.append(cur)
    # wrap a very tall column (many tables in one layer) into two or more
    wrapped: list[list[str]] = []
    for col in columns:
        total = sum(items[n][1] + V_GAP for n in col)
        if total <= MAX_COLUMN or len(col) < 4:
            wrapped.append(col)
            continue
        parts = int(total // MAX_COLUMN) + 1
        size = -(-len(col) // parts)
        wrapped += [col[i : i + size] for i in range(0, len(col), size)]
    columns = wrapped
    where = {n: ci for ci, col in enumerate(columns) for n in col}
    heights = [
        sum(items[n][1] for n in col) + V_GAP * (len(col) - 1) for col in columns
    ]
    tallest = max(heights, default=0)
    offsets: dict[str, tuple[float, float]] = {}
    x = 0.0
    for ci, col in enumerate(columns):
        width = max(items[n][0] for n in col)
        y = (tallest - heights[ci]) / 2
        for n in col:
            offsets[n] = (x + (width - items[n][0]) / 2, y)
            y += items[n][1] + V_GAP
        if ci + 1 < len(columns):
            crossing = sum(
                1
                for a, b in edges
                if a in where
                and b in where
                and min(where[a], where[b]) <= ci < max(where[a], where[b])
            )
            x += width + 76 + 9 * min(crossing, 14)
        else:
            x += width
    return offsets, x, tallest


def layout(schema: Schema) -> Layout:
    cards = {t.name: _size(t) for t in schema.tables}
    rel_edges = [(r.source, r.target) for r in schema.relations]
    # 1. each group on its own
    blocks: dict[str, _Block] = {}
    block_of: dict[str, str] = {}
    for t in schema.tables:
        key = f"g:{t.group}" if t.group else f"t:{t.name}"
        block_of[t.name] = key
        blk = blocks.setdefault(key, _Block(key, [], group=t.group))
        blk.cards.append(cards[t.name])
    for blk in blocks.values():
        names = [c.table.name for c in blk.cards]
        inside = [(a, b) for a, b in rel_edges if a in names and b in names]
        offsets, w, h = _arrange(
            {c.table.name: (c.w, c.h) for c in blk.cards}, inside, names
        )
        if blk.group:
            blk.offsets = {
                n: (ox + GROUP_PAD, oy + GROUP_TOP) for n, (ox, oy) in offsets.items()
            }
            blk.w, blk.h = w + 2 * GROUP_PAD, h + GROUP_TOP + GROUP_PAD
        else:
            blk.offsets, blk.w, blk.h = offsets, w, h
    # 2. the blocks, layered by the references between them
    outer = [(block_of[a], block_of[b]) for a, b in rel_edges]
    outer = [(a, b) for a, b in outer if a != b]
    order = list(dict.fromkeys(block_of[t.name] for t in schema.tables))
    placed, total_w, total_h = _arrange(
        {k: (b.w, b.h) for k, b in blocks.items()}, outer, order
    )
    groups: list[GroupBox] = []
    left, top = MARGIN + 30, MARGIN + TITLE_H
    for key, blk in blocks.items():
        bx, by = placed[key]
        blk.x, blk.y = left + bx, top + by
        for card in blk.cards:
            ox, oy = blk.offsets[card.table.name]
            card.x, card.y = round(blk.x + ox), round(blk.y + oy)
        if blk.group:
            groups.append(
                GroupBox(
                    blk.group,
                    blk.x,
                    blk.y,
                    blk.w,
                    blk.h,
                    [c.table.name for c in blk.cards],
                )
            )
    width = left + total_w + MARGIN + 30
    height = top + total_h + MARGIN + 30
    routes = Router(list(cards.values())).route_all(schema.relations, cards)
    for r in routes:
        for x, y in r.points:
            width = max(width, x + MARGIN)
            height = max(height, y + MARGIN)
    return Layout(cards, groups, routes, round(width), round(height))


# ----------------------------------------------------------------------------- routing

Seg = tuple[float, float, float, float]


class Router:
    """Orthogonal routes that avoid every card and spread out parallel runs."""

    CLEAR = 8  # keep this far from a card

    def __init__(self, cards: list[Card]):
        self.cards = cards
        self.used_v: list[tuple[float, float, float]] = []  # x, y1, y2
        self.used_h: list[tuple[float, float, float]] = []  # y, x1, x2
        self.min_y = min((c.y for c in cards), default=0)
        self.max_y = max((c.bottom for c in cards), default=0)

    # -- geometry -------------------------------------------------------------------
    def _hits(self, seg: Seg, skip: tuple[Card, ...]) -> bool:
        x1, y1, x2, y2 = seg
        lo_x, hi_x = min(x1, x2), max(x1, x2)
        lo_y, hi_y = min(y1, y2), max(y1, y2)
        m = self.CLEAR - 2
        for c in self.cards:
            near = c.x - m < hi_x and lo_x < c.right + m
            near = near and c.y - m < hi_y and lo_y < c.bottom + m
            if near and (not any(c is s for s in skip) or self._enters(seg, c)):
                return True
        return False

    def _enters(self, seg: Seg, c: Card) -> bool:
        """Whether a segment touching one of its own end cards runs into or along it."""
        x1, y1, x2, y2 = seg
        lo_x, hi_x = min(x1, x2), max(x1, x2)
        lo_y, hi_y = min(y1, y2), max(y1, y2)
        overlap_x = min(hi_x, c.right) - max(lo_x, c.x) > 1
        if lo_y == hi_y:  # horizontal: inside the card's rows, or grazing its edge
            return overlap_x and c.y - self.CLEAR + 2 < lo_y < c.bottom + self.CLEAR - 2
        # vertical: through the card, or hugging its sides
        return c.x - 4 < lo_x < c.right + 4 and min(hi_y, c.bottom) - max(lo_y, c.y) > 1

    def _crowding(self, points: list[tuple[float, float]]) -> float:
        cost = 0.0
        for (x1, y1), (x2, y2) in itertools.pairwise(points):
            if x1 == x2:
                lo, hi = sorted((y1, y2))
                for x, a, b in self.used_v:
                    if abs(x - x1) < 5 and a < hi and lo < b:
                        cost += 120
            else:
                lo, hi = sorted((x1, x2))
                for y, a, b in self.used_h:
                    if abs(y - y1) < 5 and a < hi and lo < b:
                        cost += 120
        return cost

    def _claim(self, points: list[tuple[float, float]]) -> None:
        for (x1, y1), (x2, y2) in itertools.pairwise(points):
            if x1 == x2:
                self.used_v.append((x1, *sorted((y1, y2))))
            else:
                self.used_h.append((y1, *sorted((x1, x2))))

    # -- candidates -----------------------------------------------------------------
    def _lanes(self, a: float, b: float) -> list[float]:
        """Free x positions strictly between ``a`` and ``b`` (gaps between cards)."""
        lo, hi = sorted((a, b))
        out: list[float] = []
        mid = (lo + hi) / 2
        for k in range(-4, 5):
            x = mid + k * 10
            if lo + STUB - 4 <= x <= hi - STUB + 4:
                out.append(x)
        return out

    def _corridors(self, x1: float, x2: float, near: float) -> list[float]:
        """Horizontal runs between cards across ``x1..x2``, nearest ``near`` first."""
        lo, hi = sorted((x1, x2))
        spans = sorted((c.y, c.bottom) for c in self.cards if c.x < hi and lo < c.right)
        free: list[float] = [self.min_y - 20, self.max_y + 20]
        reach = self.min_y - 20
        for top, bottom in spans:
            if top - reach > 2 * self.CLEAR + 4:
                free += [reach + (top - reach) / 2 + d for d in (-8, 0, 8)]
            reach = max(reach, bottom)
        return sorted(set(free), key=lambda y: abs(y - near))[:10]

    def route(self, rel: Relation, src: Card, dst: Card) -> Route:
        sy, ty = src.row_y(rel.source_column), dst.row_y(rel.target_column)
        options: list[tuple[float, list[tuple[float, float]], int, int]] = []
        if src is dst:
            sides = [(1, 1), (-1, -1)]
        elif dst.right + 2 * STUB <= src.x:
            sides = [(-1, 1), (-1, -1), (1, 1)]
        elif src.right + 2 * STUB <= dst.x:
            sides = [(1, -1), (1, 1), (-1, -1)]
        else:  # overlapping in x: one above the other
            sides = [(1, 1), (-1, -1), (1, -1), (-1, 1)]
        for sd, td in sides:
            sx = src.right if sd > 0 else src.x
            tx = dst.right if td > 0 else dst.x
            out_x, in_x = sx + sd * STUB, tx + td * STUB
            # three segments: out, one vertical lane, in
            if sd != td:
                if (tx - sx) * sd > 2 * STUB:
                    for lane in self._lanes(sx, tx):
                        pts = [(sx, sy), (lane, sy), (lane, ty), (tx, ty)]
                        options.append((self._cost(pts), pts, sd, td))
            else:
                edge = max(sx, tx) if sd > 0 else min(sx, tx)
                for k in range(6):
                    lane = edge + sd * (STUB + k * 10)
                    pts = [(sx, sy), (lane, sy), (lane, ty), (tx, ty)]
                    options.append((self._cost(pts), pts, sd, td))
            # five segments through a horizontal corridor
            for k in range(3):
                a = out_x + sd * k * 10
                b = in_x + td * k * 10
                for cy in self._corridors(a, b, (sy + ty) / 2):
                    pts = [(sx, sy), (a, sy), (a, cy), (b, cy), (b, ty), (tx, ty)]
                    options.append((self._cost(pts) + 40, pts, sd, td))
        options.sort(key=lambda o: o[0])
        best = None
        for _cost, pts, sd, td in options[:400]:
            pts = _simplify(pts)
            if not any(self._hits(seg, (src, dst)) for seg in _segments(pts)):
                best = (pts, sd, td)
                break
        if best is None:  # crowded: take the cheapest even if it grazes a card
            _c, pts, sd, td = options[0]
            best = (_simplify(pts), sd, td)
        pts, sd, td = best
        self._claim(pts)
        return Route(rel, pts, sd, td)

    def _cost(self, pts: list[tuple[float, float]]) -> float:
        length = sum(
            abs(x2 - x1) + abs(y2 - y1)
            for (x1, y1), (x2, y2) in itertools.pairwise(pts)
        )
        bends = sum(1 for i in range(1, len(pts) - 1) if pts[i] != pts[i - 1])
        return length + bends * 30 + self._crowding(pts)

    def route_all(
        self, relations: list[Relation], cards: dict[str, Card]
    ) -> list[Route]:
        # short, simple edges first so they get the straightest lanes
        def span(r: Relation) -> float:
            a, b = cards[r.source], cards[r.target]
            return abs(a.x - b.x) + abs(a.y - b.y)

        order = sorted(range(len(relations)), key=lambda i: span(relations[i]))
        routes: dict[int, Route] = {}
        for i in order:
            r = relations[i]
            routes[i] = self.route(r, cards[r.source], cards[r.target])
        return [routes[i] for i in range(len(relations))]


def _segments(pts: list[tuple[float, float]]) -> list[Seg]:
    return [(a[0], a[1], b[0], b[1]) for a, b in itertools.pairwise(pts)]


def _simplify(pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Drop repeated points and merge collinear runs."""
    out: list[tuple[float, float]] = []
    for p in pts:
        p = (round(p[0], 1), round(p[1], 1))
        if out and out[-1] == p:
            continue
        if len(out) >= 2 and (
            (out[-2][0] == out[-1][0] == p[0]) or (out[-2][1] == out[-1][1] == p[1])
        ):
            out[-1] = p
            continue
        out.append(p)
    return out
