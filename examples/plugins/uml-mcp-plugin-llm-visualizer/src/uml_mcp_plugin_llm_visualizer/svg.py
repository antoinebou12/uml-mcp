"""Static SVG renderers for LLM architecture diagrams."""

from __future__ import annotations

from html import escape

from .glyphs import glyph_svg
from .model import Connection, Group, Layer, LLMSpec


def _shape(layer: Layer) -> str:
    return " × ".join(str(part) for part in layer.shape)


def _sub(layer: Layer) -> str:
    """Shape and repeat on one line, or nothing when neither is set."""
    parts = [_shape(layer)] if layer.shape else []
    if layer.repeat > 1:
        parts.append(f"×{layer.repeat}")
    return " · ".join(parts)


def _theme(spec: LLMSpec) -> dict[str, str]:
    if spec.theme == "light":
        return {
            "bg": "#f8fafc",
            "panel": "#ffffff",
            "text": "#0f172a",
            "muted": "#475569",
            "line": "#64748b",
            "border": "#cbd5e1",
        }
    return {
        "bg": "#08111f",
        "panel": "#111c2f",
        "text": "#e5eefb",
        "muted": "#9fb0c8",
        "line": "#8da2bf",
        "border": "#2a3a52",
    }


def _header(spec: LLMSpec, width: int) -> tuple[str, int]:
    title = escape(spec.title)
    subtitle = escape(spec.subtitle)
    subtitle_tag = (
        f'<text class="subtitle" x="40" y="70">{subtitle}</text>' if subtitle else ""
    )
    return (
        (
            f'<text class="title" x="40" y="42">{title}</text>{subtitle_tag}'
            f'<text class="mode" x="{width - 40}" y="42">LLM VISUALIZER</text>'
        ),
        96 if subtitle else 72,
    )


def _defs(colors: dict[str, str]) -> str:
    return (
        "<defs>"
        '<marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" '
        'orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,6 L9,3 z" '
        f'fill="{colors["line"]}"/></marker>'
        '<filter id="shadow" x="-20%" y="-20%" width="140%" height="150%">'
        '<feDropShadow dx="0" dy="5" stdDeviation="7" flood-opacity=".2"/>'
        "</filter></defs>"
    )


def _style(colors: dict[str, str]) -> str:
    return (
        "<style>"
        f".title{{fill:{colors['text']};font:700 26px system-ui,sans-serif}}"
        f".subtitle{{fill:{colors['muted']};font:14px system-ui,sans-serif}}"
        f".mode{{fill:{colors['muted']};font:700 10px system-ui,sans-serif;text-anchor:end;letter-spacing:2px}}"
        f".label{{fill:{colors['text']};font:700 15px system-ui,sans-serif}}"
        f".meta{{fill:{colors['muted']};font:12px system-ui,sans-serif}}"
        f".edge{{fill:none;stroke:{colors['line']};stroke-width:2;marker-end:url(#arrow)}}"
        f".edge-label{{fill:{colors['muted']};font:11px system-ui,sans-serif;text-anchor:middle;"
        f"paint-order:stroke;stroke:{colors['bg']};stroke-width:4px;stroke-linejoin:round}}"
        ".glabel{font:700 13px system-ui,sans-serif}"
        ".kind{fill:#fff;font:700 9px system-ui,sans-serif;letter-spacing:.8px}"
        "</style>"
    )


_KIND_DIMS = {
    "encoder": (170, 260),
    "decoder": (170, 260),
    "vector": (64, 260),
    "bottleneck": (72, 72),
    "decision": (92, 92),
    "token": (110, 46),
}
_FLOW_GAP = 90
_PADG = 16
_PER, _CW, _CH, _GX, _GY = 6, 300, 108, 344, 128
_FLOW_CARD = (236, 108)
_GLYPH = 52  # pictogram size on a card

Box = tuple[float, float, float, float]  # x, y, width, height


_STACK_GAP = 34  # between layers that share a column (parallel branches)
#: Small shapes carry their name underneath instead of inside.
_LABEL_BELOW = frozenset({"vector", "bottleneck", "decision"})


def _label_room(layer: Layer) -> float:
    """Width a below-shape label needs, so neighbouring columns keep clear of it."""
    if layer.kind not in _LABEL_BELOW:
        return 0
    return max(len(layer.label) * 8.6, len(_sub(layer)) * 6.8) + 16


def _gap_after(spec: LLMSpec, ranks: dict[str, int], column: int) -> float:
    """Room after a column for the labels of the edges into the next one."""
    labels = [
        c.label
        for c in spec.connections
        if c.label and ranks[c.source] == column and ranks[c.target] == column + 1
    ]
    return max([_FLOW_GAP, *(len(text) * 6.6 + 34 for text in labels)])


def _flow_dims(layer: Layer, horiz: bool, stacked: int) -> tuple[float, float]:
    """Width and height of a layer in the flow layout; tall shapes shrink when stacked."""
    base = _KIND_DIMS.get(layer.kind)
    if not base:
        return _FLOW_CARD  # cards keep their size in both directions
    along, across = base
    if stacked > 1 and across > 120:
        across = max(108.0, (260 - _STACK_GAP * (stacked - 1)) / stacked)
    return (along, across) if horiz else (across, along)


def _loop(
    pos: dict[str, tuple[float, float, float, float, int]], edge: Connection
) -> tuple[float, int]:
    """How far a grid edge between non-adjacent cards of one column loops out to the
    right (0 when it is not such an edge), and how many rows it skips."""
    sx, sy, *_ = pos[edge.source]
    tx, ty, *_ = pos[edge.target]
    rows = round(abs(ty - sy) / _GY)
    if abs(tx - sx) >= 10 or rows <= 1:
        return 0, rows
    return 36 + 14 * rows, rows


def _apex(span: int) -> int:
    return 34 + 22 * span


def _place(
    spec: LLMSpec,
) -> tuple[
    dict[str, tuple[float, float, float, float, int]],
    list[tuple[Group, Box]],
    float,
    float,
]:
    """Positions of every layer and group box, shifted so the content starts at 0,0.

    This mirrors the viewer's layout so the SVG and the interactive page agree.
    """
    flow = spec.layout == "flow"
    horiz = spec.direction != "TB"
    ranks = spec.ranks()
    pos: dict[str, list[float]] = {}
    if flow:
        columns: dict[int, list[tuple[int, Layer]]] = {}
        for i, layer in enumerate(spec.layers):
            columns.setdefault(ranks[layer.id], []).append((i, layer))
        m = 0.0
        for column in sorted(columns):
            members = columns[column]
            dims = [_flow_dims(layer, horiz, len(members)) for _, layer in members]
            along = max((w if horiz else h) for w, h in dims)
            if horiz:  # below-shape labels widen the column, not the shape
                along = max([along, *(_label_room(layer) for _, layer in members)])
            # leave room under a shape for its label before the next one in the column
            gaps = [
                _STACK_GAP + (40 if horiz and layer.kind in _LABEL_BELOW else 0)
                for _, layer in members
            ]
            across = sum((h if horiz else w) for w, h in dims) + sum(gaps[:-1])
            c = -across / 2
            for (i, layer), (w, h), gap in zip(members, dims, gaps, strict=True):
                if horiz:
                    pos[layer.id] = [m + (along - w) / 2, c, w, h, i]
                    c += h + gap
                else:
                    pos[layer.id] = [c, m + (along - h) / 2, w, h, i]
                    c += w + gap
            m += along + (_gap_after(spec, ranks, column) if horiz else _FLOW_GAP)
    else:
        for i, layer in enumerate(spec.layers):
            pos[layer.id] = [(i // _PER) * _GX, (i % _PER) * _GY, _CW, _CH, i]

    head = 26 if spec.groups else 0
    boxes: list[list[float]] = []
    owners: list[Group] = []
    for group in spec.groups:
        members = [pos[layer.id] for layer in spec.layers if layer.group == group.id]
        if not members:
            continue
        low = (
            44
            if flow and any(spec.layers[int(p[4])].kind == "vector" for p in members)
            else 0
        )
        x0 = min(p[0] for p in members) - _PADG
        y0 = min(p[1] for p in members) - _PADG - head
        boxes.append(
            [
                x0,
                y0,
                max(p[0] + p[2] for p in members) + _PADG - x0,
                max(p[1] + p[3] for p in members) + _PADG + low - y0,
            ]
        )
        owners.append(group)

    rects = [*pos.values(), *boxes]
    min_x = min(r[0] for r in rects)
    min_y = min(r[1] for r in rects)
    max_x = max(r[0] + r[2] for r in rects)
    max_y = max(r[1] + r[3] for r in rects) + (46 if flow else 0)
    max_span = max(
        (
            abs(ranks[c.target] - ranks[c.source])
            for c in spec.connections
            if abs(ranks[c.target] - ranks[c.source]) > 1
        ),
        default=0,
    )
    if flow and max_span:
        if horiz:
            min_y -= _apex(max_span) + 24
        else:
            min_x -= _apex(max_span) + 24
    for r in rects:
        r[0] -= min_x
        r[1] -= min_y
    placed = {k: (v[0], v[1], v[2], v[3], int(v[4])) for k, v in pos.items()}
    return (
        placed,
        [(g, (b[0], b[1], b[2], b[3])) for g, b in zip(owners, boxes, strict=True)],
        max_x - min_x,
        max_y - min_y,
    )


def _flow_shape(
    layer: Layer, x: float, y: float, w: float, h: float, horiz: bool
) -> str:
    style = f'fill="{layer.color}" fill-opacity=".32" stroke="{layer.color}" stroke-width="2"'
    kind = layer.kind
    fractions = {
        "encoder": [(0, 0), (1, 0.25), (1, 0.75), (0, 1)],
        "decoder": [(0, 0.25), (1, 0), (1, 1), (0, 0.75)],
    }.get(kind)
    if fractions:
        pts = " ".join(
            f"{x + (a if horiz else b) * w:.1f},{y + (b if horiz else a) * h:.1f}"
            for a, b in fractions
        )
        shape = f'<polygon points="{pts}" {style}/>'
    elif kind == "decision":
        shape = f'<circle cx="{x + w / 2}" cy="{y + h / 2}" r="{w / 2}" {style}/>'
    elif kind == "token":
        shape = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" {style}/>'
    else:
        shape = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" {style}/>'

    sub = _sub(layer)
    label = escape(layer.label)
    cx = x + w / 2
    if kind in {"encoder", "decoder"}:
        text = (
            f'<text class="label" x="{cx}" y="{y + h / 2 - 4}" text-anchor="middle">{label}</text>'
            f'<text class="meta" x="{cx}" y="{y + h / 2 + 16}" text-anchor="middle">{escape(sub)}</text>'
        )
    elif kind in _LABEL_BELOW:
        text = (
            f'<text class="label" x="{cx}" y="{y + h + 20}" text-anchor="middle">{label}</text>'
            f'<text class="meta" x="{cx}" y="{y + h + 36}" text-anchor="middle">{escape(sub)}</text>'
        )
    else:
        text = f'<text class="label" x="{cx}" y="{y + h / 2 + 5}" text-anchor="middle">{label}</text>'
    return f'<g id="layer-{escape(layer.id, quote=True)}">{shape}{text}</g>'


def _card(
    layer: Layer, x: float, y: float, w: float, h: float, colors: dict[str, str]
) -> str:
    chip = max(86, len(layer.kind) * 7.4 + 18)  # the kind badge fits its text
    note = (
        f'<text class="meta" x="{x + 18}" y="{y + 94}">{escape(layer.note)}</text>'
        if layer.note
        else ""
    )
    return (
        f'<g id="layer-{escape(layer.id, quote=True)}" filter="url(#shadow)">'
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" '
        f'fill="{colors["panel"]}" stroke="{colors["border"]}"/>'
        f'<rect x="{x}" y="{y}" width="7" height="{h}" rx="4" fill="{layer.color}"/>'
        f'<rect x="{x + 18}" y="{y + 14}" width="{chip}" height="19" rx="9" fill="{layer.color}"/>'
        f'<text class="kind" x="{x + 18 + chip / 2}" y="{y + 27}" text-anchor="middle">'
        f"{escape(layer.kind.upper())}</text>"
        f"{glyph_svg(layer.kind, layer.color, x + w - 16 - _GLYPH, y + (h - _GLYPH) / 2, _GLYPH)}"
        f'<text class="label" x="{x + 18}" y="{y + 57}">{escape(layer.label)}</text>'
        f'<text class="meta" x="{x + 18}" y="{y + 78}">'
        f"{escape(_sub(layer))}</text>{note}</g>"
    )


def render_2d(spec: LLMSpec) -> str:
    """Render the 2D map: cards in a grid, or shaped nodes in a left-right / top-down flow."""
    colors = _theme(spec)
    flow = spec.layout == "flow"
    horiz = spec.direction != "TB"
    pos, boxes, content_w, content_h = _place(spec)
    # grid skip edges loop out to the right of their column, with the label beyond
    loop = max(
        (
            _loop(pos, edge)[0] + len(edge.label) * 6.6 + 16
            for edge in spec.connections
            if not flow and _loop(pos, edge)[0]
        ),
        default=0,
    )
    width = int(max(980, content_w + 88 + loop))
    header, top = _header(spec, width)
    height = int(top + content_h + 40)
    ox = 44 + (width - 88 - content_w - loop) / 2
    oy = top + 10

    groups: list[str] = []
    for group, (bx, by, bw, bh) in boxes:
        x, y = bx + ox, by + oy
        badge = (
            f'<text class="glabel" x="{x + bw - 14}" y="{y + bh - 12}" text-anchor="end" '
            f'fill="{group.color}">×{group.repeat}</text>'
            if group.repeat > 1
            else ""
        )
        groups.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="16" '
            f'fill="{group.color}" fill-opacity=".07" stroke="{group.color}" '
            f'stroke-opacity=".7" stroke-width="1.4" stroke-dasharray="6 5"/>'
            f'<text class="glabel" x="{x + 14:.1f}" y="{y + 21:.1f}" fill="{group.color}">'
            f"{escape(group.label)}</text>{badge}"
        )

    ranks = spec.ranks()
    edges: list[str] = []
    for edge in spec.connections:
        sx, sy, sw, sh, _ = pos[edge.source]
        tx, ty, tw, th, _ = pos[edge.target]
        sx, sy, tx, ty = sx + ox, sy + oy, tx + ox, ty + oy
        rs, rt = ranks[edge.source], ranks[edge.target]
        n = abs(rt - rs)
        dash = ' stroke-dasharray="7 6"' if edge.style == "dashed" else ""
        if flow and n > 1:
            # arch over every column in between, measured from the highest of them
            span = [
                pos[layer.id]
                for layer in spec.layers
                if min(rs, rt) <= ranks[layer.id] <= max(rs, rt)
            ]
            lift = _apex(n) * 4 / 3
            if horiz:
                top = min(p[1] for p in span) + oy
                ax, ay, cx, cy = sx + sw / 2, sy, tx + tw / 2, ty
                path = f"M{ax},{ay} C{ax},{top - lift} {cx},{top - lift} {cx},{cy}"
                lx, ly = (ax + cx) / 2, top - _apex(n) - 8
            else:
                left = min(p[0] for p in span) + ox
                ax, ay, cx, cy = sx, sy + sh / 2, tx, ty + th / 2
                path = f"M{ax},{ay} C{left - lift},{ay} {left - lift},{cy} {cx},{cy}"
                lx, ly = left - _apex(n) - 8, (ay + cy) / 2
        elif flow:
            # neighbouring columns: an S-curve from the out side to the in side, so
            # branches fan out and merge cleanly
            fwd = rt >= rs
            if horiz:
                ax, ay = sx + (sw if fwd else 0), sy + sh / 2
                cx, cy = tx + (0 if fwd else tw), ty + th / 2
                bend = (ax + cx) / 2
                path = f"M{ax},{ay} C{bend},{ay} {bend},{cy} {cx},{cy}"
            else:
                ax, ay = sx + sw / 2, sy + (sh if fwd else 0)
                cx, cy = tx + tw / 2, ty + (0 if fwd else th)
                bend = (ay + cy) / 2
                path = f"M{ax},{ay} C{ax},{bend} {cx},{bend} {cx},{cy}"
            lx, ly = (ax + cx) / 2, (ay + cy) / 2 - 7
        else:
            ax, ay, cx, cy = sx + sw, sy + sh / 2, tx, ty + th / 2
            bulge, _ = _loop(pos, edge)
            anchor = ' style="text-anchor:start"'
            if bulge:
                # a skip connection (a residual path): out of the right side and back
                cx = tx + tw
                path = f"M{ax},{ay} C{ax + bulge},{ay} {cx + bulge},{cy} {cx},{cy}"
                lx, ly = ax + bulge * 0.75 + 8, (ay + cy) / 2 + 4
            elif abs(tx - sx) < 10:
                ax, cx = sx + sw / 2, tx + tw / 2
                down = ty >= sy
                ay, cy = (sy + sh, ty) if down else (sy, ty + th)
                path = f"M{ax},{ay} L{cx},{cy}"
                lx, ly = ax + 10, (ay + cy) / 2 + 4  # beside the arrow, not on it
            else:
                bend = (ax + cx) / 2
                path = f"M{ax},{ay} C{bend},{ay} {bend},{cy} {cx},{cy}"
                lx, ly = bend, (ay + cy) / 2 - 7
                anchor = ""
        label = (
            f'<text class="edge-label" x="{lx}" y="{ly}"{"" if flow else anchor}>'
            f"{escape(edge.label)}</text>"
            if edge.label
            else ""
        )
        edges.append(f'<path class="edge" d="{path}"{dash}/>{label}')

    nodes: list[str] = []
    for layer in spec.layers:
        x, y, w, h, _ = pos[layer.id]
        x, y = x + ox, y + oy
        if flow and layer.kind in _KIND_DIMS:
            nodes.append(_flow_shape(layer, x, y, w, h, horiz))
        else:
            nodes.append(_card(layer, x, y, w, h, colors))

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(spec.title, quote=True)}">'
        f'<rect width="100%" height="100%" fill="{colors["bg"]}"/>'
        f"{_defs(colors)}{_style(colors)}{header}"
        f"{''.join(groups)}{''.join(edges)}{''.join(nodes)}</svg>"
    )


#: 3D solids per kind: (length along the flow, (half height, half depth) at the input
#: end, (half height, half depth) at the output end). Encoders narrow and decoders widen,
#: the funnel shape of autoencoder diagrams; other layers are thin activation slabs.
_SOLIDS: dict[str, tuple[float, tuple[float, float], tuple[float, float]]] = {
    "encoder": (150, (95, 70), (40, 28)),
    "decoder": (150, (40, 28), (95, 70)),
    "vector": (22, (60, 18), (60, 18)),
    "bottleneck": (56, (30, 30), (30, 30)),
    "decision": (60, (30, 30), (30, 30)),
    "token": (80, (24, 40), (24, 40)),
}
_SLAB: tuple[float, tuple[float, float], tuple[float, float]] = (26, (95, 70), (95, 70))
_DEPTH_X, _DEPTH_Y = 0.55, 0.32  # oblique projection: depth recedes up and to the right

Solid = tuple[float, float, tuple[float, float], tuple[float, float]]


def _project(x: float, y: float, z: float) -> tuple[float, float]:
    return x + z * _DEPTH_X, -y - z * _DEPTH_Y


def _poly(points: list[tuple[float, float, float]], ox: float, oy: float) -> str:
    out = []
    for point in points:
        px, py = _project(*point)
        out.append(f"{px + ox:.1f},{py + oy:.1f}")
    return " ".join(out)


def _text_width(text: str, size: float) -> float:
    return len(text) * size * 0.56


def _solid_svg(layer: Layer, solid: Solid, ox: float, oy: float) -> str:
    x0, x1, (a0, p0), (a1, p1) = solid
    left = [(x0, -a0, -p0), (x0, a0, -p0), (x0, a0, p0), (x0, -a0, p0)]
    right = [(x1, -a1, -p1), (x1, a1, -p1), (x1, a1, p1), (x1, -a1, p1)]
    front = [left[0], right[0], right[1], left[1]]
    top_face = [left[1], right[1], right[2], left[2]]
    ghosts = "".join(
        f'<polygon points="{_poly(front, ox + 9 * k, oy - 9 * k)}" fill="none" '
        f'stroke="{layer.color}" stroke-opacity="{0.5 - 0.12 * k:.2f}"/>'
        for k in range(min(layer.repeat, 4) - 1, 0, -1)
    )
    face = f'stroke="{layer.color}" stroke-width="1.5"'
    return (
        f'<g id="layer-{escape(layer.id, quote=True)}" filter="url(#shadow)">{ghosts}'
        f'<polygon points="{_poly(top_face, ox, oy)}" fill="{layer.color}" '
        f'fill-opacity=".55" {face}/>'
        f'<polygon points="{_poly(right, ox, oy)}" fill="{layer.color}" '
        f'fill-opacity=".38" {face}/>'
        f'<polygon points="{_poly(front, ox, oy)}" fill="{layer.color}" '
        f'fill-opacity=".22" stroke="{layer.color}" stroke-width="2"/></g>'
    )


#: Labels of single-layer columns sit on one row under the tallest slab's front edge.
_LABEL_ROW = _project(0, -95, -70)[1] + 30


def _labels_3d(
    layer: Layer, solid: Solid, ox: float, oy: float, row: float | None
) -> str:
    """Kind above the solid; name and size on the shared ``row`` or, for a layer
    stacked with parallel branches, right under its own solid."""
    x0, x1, (a0, p0), (a1, p1) = solid
    cx, base, depth = (x0 + x1) / 2, max(a0, a1), max(p0, p1)
    kx, ky = _project(cx, base, depth)  # above the back edge of the top face
    lx, own = _project(cx, -base, -depth)
    y = (own + 24) if row is None else row
    out = (
        f'<text class="kind3d" x="{kx + ox:.1f}" y="{ky + oy - 10:.1f}" '
        f'fill="{layer.color}">{escape(layer.kind.upper())}</text>'
        f'<text class="label" x="{lx + ox:.1f}" y="{y + oy:.1f}" '
        f'text-anchor="middle">{escape(layer.label)}</text>'
    )
    if _sub(layer):
        out += (
            f'<text class="meta" x="{lx + ox:.1f}" y="{y + oy + 18:.1f}" '
            f'text-anchor="middle">{escape(_sub(layer))}</text>'
        )
    return out


def render_3d(spec: LLMSpec) -> str:
    """Render a static oblique view: one column of solids per rank, left to right.

    Encoders are frustums that narrow along the flow and decoders frustums that widen,
    so an autoencoder reads as the familiar funnel; other layers are activation slabs.
    Parallel branches (a VAE's mean and log-variance heads) stack in one column.
    """
    colors = _theme(spec)
    ranks = spec.ranks()
    columns: dict[int, list[Layer]] = {}
    for layer in spec.layers:
        columns.setdefault(ranks[layer.id], []).append(layer)

    solids: dict[str, Solid] = {}
    height_of: dict[str, float] = {}  # world y of each solid's centre
    stacked: set[str] = set()
    cursor = 0.0
    for column in sorted(columns):
        members = columns[column]
        shapes = [_SOLIDS.get(layer.kind, _SLAB) for layer in members]
        length = max(s[0] for s in shapes)
        slot = max(
            [
                length + 80,
                *(_text_width(layer.label, 15) + 28 for layer in members),
                *(_text_width(_sub(layer), 12) + 28 for layer in members),
            ]
        )
        # stack parallel members top to bottom, leaving room for each one's label
        halves = [max(s[1][0], s[2][0]) for s in shapes]
        pitch = [2 * h + 96 for h in halves]
        y = (sum(pitch) - 96) / 2
        for layer, (own, near, far), half, step in zip(
            members, shapes, halves, pitch, strict=True
        ):
            x0 = cursor + (slot - own) / 2
            solids[layer.id] = (x0, x0 + own, near, far)
            height_of[layer.id] = y - half
            y -= step
            if len(members) > 1:
                stacked.add(layer.id)
        cursor += slot

    def lowest(layer: Layer) -> float:
        _, _, (a0, p0), (a1, p1) = solids[layer.id]
        return _project(0, height_of[layer.id] - max(a0, a1), -max(p0, p1))[1]

    def highest(layer: Layer) -> float:
        _, _, (a0, p0), (a1, p1) = solids[layer.id]
        return _project(0, height_of[layer.id] + max(a0, a1), max(p0, p1))[1]

    row = max(
        [
            _LABEL_ROW,
            *(lowest(layer) + 70 for layer in spec.layers if layer.id in stacked),
        ]
    )
    longest = max(
        (abs(ranks[c.target] - ranks[c.source]) for c in spec.connections), default=1
    )
    arch = 60 + 26 * longest if longest > 1 else 0
    reach = -min(highest(layer) for layer in spec.layers) + 20
    width = int(max(980, cursor + 70 * _DEPTH_X + 80))
    header, top = _header(spec, width)
    oy = top + 40 + arch + reach
    height = int(oy + row + 40)
    ox = (width - cursor - 70 * _DEPTH_X) / 2

    floor: list[str] = []
    base_y = min(height_of[k] - max(s[2][0], s[3][0]) for k, s in solids.items()) - 10
    for group in spec.groups:
        members = [solids[layer.id] for layer in spec.layers if layer.group == group.id]
        if not members:
            continue
        gx0 = min(m[0] for m in members) - 24
        gx1 = max(m[1] for m in members) + 24
        plate = [
            (gx0, base_y, -80),
            (gx1, base_y, -80),
            (gx1, base_y, 80),
            (gx0, base_y, 80),
        ]
        lx, ly = _project(gx0, base_y, -80)
        repeat = f" ×{group.repeat}" if group.repeat > 1 else ""
        floor.append(
            f'<polygon points="{_poly(plate, ox, oy)}" fill="{group.color}" '
            f'fill-opacity=".12" stroke="{group.color}" stroke-dasharray="6 5"/>'
            f'<text class="glabel" x="{lx + ox + 6:.1f}" y="{ly + oy + 18:.1f}" '
            f'fill="{group.color}">{escape(group.label + repeat)}</text>'
        )

    bodies = [
        _solid_svg(layer, solids[layer.id], ox, oy - height_of[layer.id])
        for layer in spec.layers
    ]
    labels = [
        _labels_3d(
            layer,
            solids[layer.id],
            ox,
            oy - height_of[layer.id],
            None if layer.id in stacked else row + height_of[layer.id],
        )
        for layer in spec.layers
    ]

    edges: list[str] = []
    for edge in spec.connections:
        sx0, sx1, (sa0, sp0), (sa1, sp1) = solids[edge.source]
        tx0, tx1, (ta0, tp0), (ta1, tp1) = solids[edge.target]
        sy, ty = height_of[edge.source], height_of[edge.target]
        dash = ' stroke-dasharray="7 6"' if edge.style == "dashed" else ""
        n = abs(ranks[edge.target] - ranks[edge.source])
        if n > 1:
            a = _project((sx0 + sx1) / 2, sy + max(sa0, sa1), 0)
            c = _project((tx0 + tx1) / 2, ty + max(ta0, ta1), 0)
            lift = 60 + 26 * n
            ax, ay, cx, cy = a[0] + ox, a[1] + oy, c[0] + ox, c[1] + oy
            path = (
                f"M{ax:.1f},{ay:.1f} C{ax:.1f},{ay - lift:.1f} "
                f"{cx:.1f},{cy - lift:.1f} {cx:.1f},{cy:.1f}"
            )
            mx, my = (ax + cx) / 2, min(ay, cy) - lift * 0.75 - 6
        else:
            # Along the front plane, from the source's front edge to the target's, so
            # the arrow never starts or ends inside a solid.
            forward = ranks[edge.target] >= ranks[edge.source]
            a = _project(sx1, sy, -sp1) if forward else _project(sx0, sy, -sp0)
            c = _project(tx0, ty, -tp0) if forward else _project(tx1, ty, -tp1)
            ax, ay, cx, cy = a[0] + ox, a[1] + oy, c[0] + ox, c[1] + oy
            bend = (ax + cx) / 2
            path = (
                f"M{ax:.1f},{ay:.1f} C{bend:.1f},{ay:.1f} {bend:.1f},{cy:.1f} "
                f"{cx:.1f},{cy:.1f}"
            )
            mx, my = (ax + cx) / 2, (ay + cy) / 2 - 10
        label = (
            f'<text class="edge-label" x="{mx:.1f}" y="{my:.1f}">{escape(edge.label)}</text>'
            if edge.label
            else ""
        )
        edges.append(f'<path class="edge" d="{path}"{dash}/>{label}')

    style = _style(colors).replace(
        "</style>",
        ".kind3d{font:700 10px system-ui,sans-serif;letter-spacing:1px;text-anchor:middle}"
        "</style>",
    )
    # Solids first, then edges and labels, so arrow heads and text stay readable.
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{escape(spec.title, quote=True)}">'
        f'<rect width="100%" height="100%" fill="{colors["bg"]}"/>'
        f"{_defs(colors)}{style}{header}{''.join(floor)}{''.join(bodies)}"
        f"{''.join(edges)}{''.join(labels)}</svg>"
    )
