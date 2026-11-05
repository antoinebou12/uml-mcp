"""Static SVG renderers for LLM architecture diagrams."""

from __future__ import annotations

from html import escape

from .model import Group, Layer, LLMSpec


def _shape(layer: Layer) -> str:
    return (
        " × ".join(str(part) for part in layer.shape)
        if layer.shape
        else "shape not set"
    )


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
        f".edge-label{{fill:{colors['muted']};font:11px system-ui,sans-serif;text-anchor:middle}}"
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
_PER, _CW, _CH, _GX, _GY = 6, 236, 108, 280, 128

Box = tuple[float, float, float, float]  # x, y, width, height


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
    index = {layer.id: i for i, layer in enumerate(spec.layers)}
    pos: dict[str, list[float]] = {}
    if flow:
        m = 0.0
        for i, layer in enumerate(spec.layers):
            base = _KIND_DIMS.get(layer.kind)
            w, h = (base if horiz else base[::-1]) if base else (190, 108)
            pos[layer.id] = [m if horiz else -w / 2, -h / 2 if horiz else m, w, h, i]
            m += (w if horiz else h) + _FLOW_GAP
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
            abs(index[c.target] - index[c.source])
            for c in spec.connections
            if abs(index[c.target] - index[c.source]) > 1
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

    sub = _shape(layer) + (f" · ×{layer.repeat}" if layer.repeat > 1 else "")
    label = escape(layer.label)
    cx = x + w / 2
    if kind in {"encoder", "decoder"}:
        text = (
            f'<text class="label" x="{cx}" y="{y + h / 2 - 4}" text-anchor="middle">{label}</text>'
            f'<text class="meta" x="{cx}" y="{y + h / 2 + 16}" text-anchor="middle">{escape(sub)}</text>'
        )
    elif kind == "vector":
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
    repeat = f" · ×{layer.repeat}" if layer.repeat > 1 else ""
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
        f'<rect x="{x + 18}" y="{y + 14}" width="86" height="19" rx="9" fill="{layer.color}"/>'
        f'<text class="kind" x="{x + 61}" y="{y + 27}" text-anchor="middle">'
        f"{escape(layer.kind.upper())}</text>"
        f'<text class="label" x="{x + 18}" y="{y + 57}">{escape(layer.label)}</text>'
        f'<text class="meta" x="{x + 18}" y="{y + 78}">'
        f"{escape(_shape(layer) + repeat)}</text>{note}</g>"
    )


def render_2d(spec: LLMSpec) -> str:
    """Render the 2D map: cards in a grid, or shaped nodes in a left-right / top-down flow."""
    colors = _theme(spec)
    flow = spec.layout == "flow"
    horiz = spec.direction != "TB"
    pos, boxes, content_w, content_h = _place(spec)
    width = int(max(980, content_w + 88))
    header, top = _header(spec, width)
    height = int(top + content_h + 40)
    ox = 44 + (width - 88 - content_w) / 2
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

    edges: list[str] = []
    for edge in spec.connections:
        sx, sy, sw, sh, si = pos[edge.source]
        tx, ty, tw, th, ti = pos[edge.target]
        sx, sy, tx, ty = sx + ox, sy + oy, tx + ox, ty + oy
        n = abs(ti - si)
        dash = ' stroke-dasharray="7 6"' if edge.style == "dashed" else ""
        if flow and n > 1:
            lift = _apex(n) * 4 / 3
            if horiz:
                ax, ay, cx, cy = sx + sw / 2, sy, tx + tw / 2, ty
                path = f"M{ax},{ay} C{ax},{ay - lift} {cx},{cy - lift} {cx},{cy}"
                lx, ly = (ax + cx) / 2, min(ay, cy) - _apex(n) - 8
            else:
                ax, ay, cx, cy = sx, sy + sh / 2, tx, ty + th / 2
                path = f"M{ax},{ay} C{ax - lift},{ay} {cx - lift},{cy} {cx},{cy}"
                lx, ly = min(ax, cx) - _apex(n) - 8, (ay + cy) / 2
        elif flow:
            fwd = ti > si
            if horiz:
                ax, ay = sx + (sw if fwd else 0), sy + sh / 2
                cx, cy = tx + (0 if fwd else tw), ty + th / 2
            else:
                ax, ay = sx + sw / 2, sy + (sh if fwd else 0)
                cx, cy = tx + tw / 2, ty + (0 if fwd else th)
            path = f"M{ax},{ay} L{cx},{cy}"
            lx, ly = (ax + cx) / 2, (ay + cy) / 2 - 7
        else:
            ax, ay, cx, cy = sx + sw, sy + sh / 2, tx, ty + th / 2
            if abs(tx - sx) < 10:
                ax, cx = sx + sw / 2, tx + tw / 2
                ay, cy = sy + sh, ty
                path = f"M{ax},{ay} L{cx},{cy}"
                lx, ly = ax, (ay + cy) / 2 - 7
            else:
                bend = (ax + cx) / 2
                path = f"M{ax},{ay} C{bend},{ay} {bend},{cy} {cx},{cy}"
                lx, ly = bend, (ay + cy) / 2 - 7
        label = (
            f'<text class="edge-label" x="{lx}" y="{ly}">{escape(edge.label)}</text>'
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


def _project(x: float, y: float, z: float) -> tuple[float, float]:
    return (x - z) * 0.82, y + (x + z) * 0.34


def _points(points: list[tuple[float, float, float]], ox: float, oy: float) -> str:
    return " ".join(
        f"{_project(x, y, z)[0] + ox:.1f},{_project(x, y, z)[1] + oy:.1f}"
        for x, y, z in points
    )


def render_3d(spec: LLMSpec) -> str:
    """Render a static isometric view of the interactive scene."""
    colors = _theme(spec)
    width = max(1080, 360 + len(spec.layers) * 155)
    header, top = _header(spec, width)
    height = 640
    ox, oy = 155.0, top + 125.0
    boxes: list[str] = []
    centers: dict[str, tuple[float, float]] = {}

    for index, layer in enumerate(spec.layers):
        x = index * 185.0
        z = (index % 3 - 1) * 48.0
        box_width, box_height, depth = 128.0, 105.0, 72.0
        lift = min(56.0, (layer.repeat - 1) * 2.0)
        y = 130.0 - lift
        top_face = [
            (x, y, z),
            (x + box_width, y, z),
            (x + box_width, y, z + depth),
            (x, y, z + depth),
        ]
        front = [
            (x, y, z),
            (x + box_width, y, z),
            (x + box_width, y + box_height, z),
            (x, y + box_height, z),
        ]
        side = [
            (x + box_width, y, z),
            (x + box_width, y, z + depth),
            (x + box_width, y + box_height, z + depth),
            (x + box_width, y + box_height, z),
        ]
        cx, cy = _project(x + box_width / 2, y + box_height / 2, z)
        centers[layer.id] = (cx + ox, cy + oy)
        repeat = f"×{layer.repeat}" if layer.repeat > 1 else escape(_shape(layer))
        boxes.append(
            f'<g id="layer-{escape(layer.id, quote=True)}" filter="url(#shadow)">'
            f'<polygon points="{_points(front, ox, oy)}" fill="{colors["panel"]}" '
            f'stroke="{layer.color}" stroke-width="2"/>'
            f'<polygon points="{_points(side, ox, oy)}" fill="{layer.color}" opacity=".52"/>'
            f'<polygon points="{_points(top_face, ox, oy)}" fill="{layer.color}" opacity=".82"/>'
            f'<text class="label" x="{cx + ox:.1f}" y="{cy + oy - 5:.1f}" text-anchor="middle">'
            f"{escape(layer.label)}</text>"
            f'<text class="meta" x="{cx + ox:.1f}" y="{cy + oy + 17:.1f}" text-anchor="middle">'
            f"{repeat}</text></g>"
        )

    edges: list[str] = []
    for edge in spec.connections:
        sx, sy = centers[edge.source]
        tx, ty = centers[edge.target]
        dash = ' stroke-dasharray="7 6"' if edge.style == "dashed" else ""
        edges.append(
            f'<path class="edge" d="M{sx:.1f},{sy:.1f} L{tx:.1f},{ty:.1f}"{dash}/>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(spec.title, quote=True)}">'
        f'<rect width="100%" height="100%" fill="{colors["bg"]}"/>'
        f"{_defs(colors)}{_style(colors)}{header}{''.join(edges)}{''.join(boxes)}</svg>"
    )
