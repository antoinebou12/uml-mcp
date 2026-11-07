"""Draw a laid-out C4 view as SVG, in the usual C4 notation.

People are a head over a rounded body, software systems and containers are blue boxes
(external ones grey), databases are cylinders, queues are pipes on their side, and each
relationship carries its label with the technology in brackets. The stylesheet uses plain
colours (no CSS variables) so rasterizers such as resvg paint it the same as a browser.
"""

from __future__ import annotations

import re
from html import escape

from .model import Model
from .views import PERSON_HEAD, Node, View, wrap

FONT = "system-ui,-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
LEGEND_H = 64

LIGHT = {
    "bg": "#ffffff",
    "ink": "#1f2a37",
    "muted": "#5b6675",
    "edge": "#6b7685",
    "boundary": "#8792a2",
    "person": "#08427b",
    "person-s": "#073b6f",
    "system": "#1168bd",
    "system-s": "#0e5aa7",
    "container": "#438dd5",
    "container-s": "#3c7fc0",
    "component": "#85bbf0",
    "component-s": "#78a8d8",
    "ext": "#8c8c8c",
    "ext-s": "#7a7a7a",
    "ext-person": "#6b6b6b",
    "on": "#ffffff",
    "on-component": "#0b2540",
    "select": "#f59e0b",
}
DARK = {
    **LIGHT,
    "bg": "#0e141b",
    "ink": "#e6edf3",
    "muted": "#9aa7b4",
    "edge": "#9aa7b4",
    "boundary": "#7d8a99",
    "person": "#0b5aa6",
    "person-s": "#3d84cc",
    "system": "#1a6fc4",
    "system-s": "#4f95dc",
    "container": "#3f86cc",
    "container-s": "#6aa6e0",
    "component": "#7fb3e6",
    "component-s": "#a3c9ef",
    "ext": "#5d6670",
    "ext-s": "#7b858f",
    "ext-person": "#56606a",
}

_RULES = (
    ("", "font-family:{font}"),
    (" .bg", "fill:{bg}"),
    (" .title", "fill:{ink};font-size:20px;font-weight:700"),
    (" .subtitle", "fill:{muted};font-size:12.5px"),
    (" .el .shape", "stroke-width:1.5"),
    (" .el .line2", "fill:none;stroke-width:1.5"),
    (" .person .shape", "fill:{person};stroke:{person-s}"),
    (" .system .shape", "fill:{system};stroke:{system-s}"),
    (" .container .shape", "fill:{container};stroke:{container-s}"),
    (" .container .line2", "stroke:{container-s}"),
    (" .component .shape", "fill:{component};stroke:{component-s}"),
    (" .component .line2", "stroke:{component-s}"),
    (" .ext .shape", "fill:{ext};stroke:{ext-s}"),
    (" .ext .line2", "stroke:{ext-s}"),
    (" .person.ext .shape", "fill:{ext-person};stroke:{ext-s}"),
    (" .el text", "fill:{on}"),
    (" .component text", "fill:{on-component}"),
    (" .name", "font-size:15px;font-weight:700"),
    (" .type", "font-size:11.5px;opacity:.88"),
    (" .desc", "font-size:12px"),
    (" .dots", "fill:{on};opacity:.75"),
    (
        " .boundary .frame",
        "fill:none;stroke:{boundary};stroke-width:1.5;stroke-dasharray:9 6",
    ),
    (" .boundary .bname", "fill:{ink};font-size:14px;font-weight:700"),
    (" .boundary .btype", "fill:{muted};font-size:11.5px"),
    (" .rel .line", "fill:none;stroke:{edge};stroke-width:1.6"),
    (" .rel.async .line", "stroke-dasharray:7 5"),
    (" .rel .hit", "fill:none;stroke:{bg};stroke-opacity:0;stroke-width:14"),
    (" .arrow", "fill:{edge}"),
    (
        " .rel text",
        (
            "fill:{ink};font-size:12px;paint-order:stroke;stroke:{bg};stroke-width:4px;"
            "stroke-linejoin:round"
        ),
    ),
    (" .rel .tech", "fill:{muted};font-size:11px"),
    (" .legend .lt", "fill:{muted};font-size:12px"),
    (" .legend .lh", "fill:{ink};font-size:12px;font-weight:700"),
    (" .legend .shape", "stroke-width:1.2"),
    (" .badge circle", "fill:{bg};stroke:{edge};stroke-width:1.2"),
    (" .badge path", "fill:none;stroke:{ink};stroke-width:1.6;stroke-linecap:round"),
)


def css(theme: str, prefix: str = ".c4") -> str:
    """The diagram stylesheet with colours resolved for ``theme`` (``light`` or ``dark``)."""
    palette = {**(DARK if theme == "dark" else LIGHT), "font": FONT}
    return "".join(
        prefix
        + sel
        + "{"
        + re.sub(r"\{([\w-]+)\}", lambda m: palette[m[1]], body)
        + "}"
        for sel, body in _RULES
    )


def _attr(text: str) -> str:
    return escape(text, quote=True)


def _marker_id(key: str) -> str:
    return "c4a-" + re.sub(r"[^A-Za-z0-9_-]", "_", key)


# ---------------------------------------------------------------- shapes


def shape_path(shape: str, x: float, y: float, w: float, h: float) -> tuple[str, str]:
    """(outline, extra stroke) path data for a node shape."""
    if shape == "db":
        ry = 11
        outline = (
            f"M{x},{y + ry} A{w / 2},{ry} 0 0 1 {x + w},{y + ry} V{y + h - ry} "
            f"A{w / 2},{ry} 0 0 1 {x},{y + h - ry} Z"
        )
        return outline, f"M{x},{y + ry} A{w / 2},{ry} 0 0 0 {x + w},{y + ry}"
    if shape == "queue":
        rx = min(16.0, w / 8)
        outline = (
            f"M{x + rx},{y} H{x + w - rx} A{rx},{h / 2} 0 0 1 {x + w - rx},{y + h} "
            f"H{x + rx} A{rx},{h / 2} 0 0 1 {x + rx},{y} Z"
        )
        return outline, f"M{x + w - rx},{y} A{rx},{h / 2} 0 0 0 {x + w - rx},{y + h}"
    if shape == "storage":
        ry, inset = 10, 12
        outline = (
            f"M{x},{y + ry} A{w / 2},{ry} 0 0 1 {x + w},{y + ry} "
            f"L{x + w - inset},{y + h} H{x + inset} Z"
        )
        return outline, f"M{x},{y + ry} A{w / 2},{ry} 0 0 0 {x + w},{y + ry}"
    if shape == "function":
        c = min(18.0, w / 5)
        outline = (
            f"M{x + c},{y} H{x + w - c} L{x + w},{y + h / 2} L{x + w - c},{y + h} "
            f"H{x + c} L{x},{y + h / 2} Z"
        )
        return outline, ""
    if shape == "web":
        outline = _round_rect(x, y, w, h, 10)
        return outline, f"M{x},{y + 20} H{x + w}"
    return _round_rect(x, y, w, h, 28 if shape == "person" else 10), ""


def _round_rect(x: float, y: float, w: float, h: float, r: float) -> str:
    r = min(r, w / 2, h / 2)
    return (
        f"M{x + r},{y} H{x + w - r} A{r},{r} 0 0 1 {x + w},{y + r} V{y + h - r} "
        f"A{r},{r} 0 0 1 {x + w - r},{y + h} H{x + r} A{r},{r} 0 0 1 {x},{y + h - r} "
        f"V{y + r} A{r},{r} 0 0 1 {x + r},{y} Z"
    )


def _content_box(n: Node) -> tuple[float, float]:
    """(top, bottom) of the area the text is centred in."""
    top, bottom = n.y, n.y + n.h
    if n.shape == "person":
        top += PERSON_HEAD
    elif n.shape in ("db", "storage"):
        top += 20
    elif n.shape == "queue":
        top += 6
    elif n.shape == "web":
        top += 18
    return top, bottom


def _shape(n: Node, *, glyph: bool = True) -> str:
    x, y, w, h = n.x, n.y, n.w, n.h
    parts = []
    if n.shape == "person":
        body_y = y + PERSON_HEAD - 8
        parts.append(
            f'<path class="shape" d="{shape_path("person", x, body_y, w, h - PERSON_HEAD + 8)[0]}"/>'
        )
        parts.append(
            f'<circle class="shape" cx="{x + w / 2:.1f}" cy="{y + 22}" r="24"/>'
        )
        return "".join(parts)
    outline, extra = shape_path(n.shape, x, y, w, h)
    parts.append(f'<path class="shape" d="{outline}"/>')
    if extra:
        parts.append(f'<path class="line2" d="{extra}"/>')
    if n.shape == "web" and glyph:
        parts.extend(
            f'<circle class="dots" cx="{x + 14 + 10 * k}" cy="{y + 10}" r="3"/>'
            for k in range(3)
        )
    return "".join(parts)


def _text(n: Node) -> str:
    top, bottom = _content_box(n)
    lines: list[tuple[str, str, float]] = [(t, "name", 19) for t in n.name]
    lines.append((n.type, "type", 17))
    lines.extend((t, "desc", 15) for t in n.desc)
    gap = 8 if n.desc else 0
    total = sum(step for _, _, step in lines) + gap
    y = top + (bottom - top - total) / 2 + 13
    out = []
    cx = n.x + n.w / 2
    for k, (text, cls, step) in enumerate(lines):
        if cls == "desc" and lines[k - 1][1] != "desc":
            y += gap
        out.append(
            f'<text class="{cls}" x="{cx:.1f}" y="{y:.1f}" text-anchor="middle">{escape(text)}</text>'
        )
        y += step
    return "".join(out)


def _badge(n: Node) -> str:
    """The zoom-in mark on a box that opens into a lower level (interactive page only)."""
    top, _ = _content_box(n)
    cx, cy = n.x + n.w - 16, top + 14 if n.shape != "person" else n.y + PERSON_HEAD + 6
    return (
        f'<g class="badge" aria-hidden="true"><circle cx="{cx}" cy="{cy}" r="10"/>'
        f'<path d="M{cx - 5},{cy} H{cx + 5} M{cx},{cy - 5} V{cy + 5}"/></g>'
    )


# ---------------------------------------------------------------- view


def view_svg(model: Model, view: View, theme: str, *, page: bool = False) -> str:
    """One view as an ``<svg>``: standalone (with its stylesheet) or for the page."""
    legend, legend_h = _legend(model, view)
    width, height = view.width, view.height + legend_h
    marker = _marker_id(f"{view.key}-{view.direction}")
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" class="c4 {theme}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" '
        + (f'width="{width:.0f}" height="{height:.0f}" ' if not page else "")
        + f'role="img" aria-label="{_attr(view.title)}" data-view="{_attr(view.key)}">'
    ]
    if not page:
        out.append(f"<style>{css(theme)}</style>")
    out.append(
        f'<defs><marker id="{marker}" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="9" markerHeight="9" orient="auto-start-reverse">'
        '<path class="arrow" d="M0,0 L10,5 L0,10 z"/></marker></defs>'
    )
    out.append(
        f'<rect class="bg" x="0" y="0" width="{width:.0f}" height="{height:.0f}"/>'
    )
    out.append(f'<text class="title" x="40" y="34">{escape(view.title)}</text>')
    subtitle = _subtitle(model, view)
    out.append(f'<text class="subtitle" x="40" y="54">{escape(subtitle)}</text>')
    if view.boundary:
        b = view.boundary
        out.append(
            f'<g class="boundary" data-id="{_attr(b.id)}"'
            + (
                f' tabindex="0" role="button" aria-label="{_attr(b.label)} details"'
                if page
                else ""
            )
            + f'><rect class="frame" x="{b.x:.1f}" y="{b.y:.1f}" width="{b.w:.1f}" '
            f'height="{b.h:.1f}" rx="6"/>'
            f'<text class="bname" x="{b.x + 14:.1f}" y="{b.y + b.h - 20:.1f}">{escape(b.label)}</text>'
            f'<text class="btype" x="{b.x + 14:.1f}" y="{b.y + b.h - 6:.1f}">[{escape(b.type)}]</text></g>'
        )
    for e in view.edges:
        out.append(_edge(e, marker, page))
    for n in view.nodes:
        item = model.elements[n.id]
        classes = ["el", item.level]
        if item.external:
            classes.append("ext")
        if n.drill:
            classes.append("drillable")
        attrs = f' class="{" ".join(classes)}" data-id="{_attr(n.id)}"'
        if n.drill:
            attrs += f' data-drill="{_attr(n.drill)}"'
        if page:
            hint = f"open {item.name}" if n.drill else f"{item.name} details"
            attrs += f' tabindex="0" role="button" aria-label="{_attr(hint)}"'
        out.append(f"<g{attrs}>{_shape(n)}{_text(n)}")
        if page and n.drill:
            out.append(_badge(n))
        out.append("</g>")
    out.append(legend)
    out.append("</svg>")
    return "".join(out)


def _subtitle(model: Model, view: View) -> str:
    if view.level == "context":
        return model.description or "Level 1 · people and software systems"
    return {
        "container": "Level 2 · the containers inside the system",
        "component": "Level 3 · the components inside the container",
    }[view.level]


def _edge(e, marker: str, page: bool) -> str:
    cls = "rel async" if e.is_async else "rel"
    lines = wrap(e.label, 12, 170, 3)
    tech = f"[{e.technology}]" if e.technology else ""
    rows = [(t, "") for t in lines] + ([(tech, "tech")] if tech else [])
    y0 = e.label_y - (len(rows) - 1) * 14 / 2 + 4
    text = "".join(
        f'<text{f" class={chr(34)}{c}{chr(34)}" if c else ""} x="{e.label_x:.1f}" '
        f'y="{y0 + k * 14:.1f}" text-anchor="middle">{escape(t)}</text>'
        for k, (t, c) in enumerate(rows)
    )
    hit = f'<path class="hit" d="{e.path}"/>' if page else ""
    return (
        f'<g class="{cls}" data-id="{e.id}" data-from="{_attr(e.source)}" data-to="{_attr(e.target)}">'
        f'{hit}<path class="line" d="{e.path}" marker-end="url(#{marker})"/>{text}</g>'
    )


_LEGEND_ITEMS = (
    ("person", "Person"),
    ("person-ext", "External person"),
    ("system", "Software system"),
    ("system-ext", "External system"),
    ("container", "Container"),
    ("container-db", "Database"),
    ("container-queue", "Queue"),
    ("container-storage", "Storage"),
    ("container-function", "Function"),
    ("container-web", "Web app"),
    ("component", "Component"),
)


def _legend(model: Model, view: View) -> tuple[str, float]:
    present: set[str] = set()
    for n in view.nodes:
        item = model.elements[n.id]
        if item.level in ("person", "system"):
            present.add(item.level + ("-ext" if item.external else ""))
        elif item.level == "container":
            present.add("container" if n.shape == "box" else f"container-{n.shape}")
        else:
            present.add("component")
    items = [(k, label) for k, label in _LEGEND_ITEMS if k in present]
    styles = {e.is_async for e in view.edges}
    x0, y0 = 40.0, view.height
    x, y = x0 + 64, y0 + 10
    out = [f'<g class="legend"><text class="lh" x="{x0}" y="{y + 16}">Legend</text>']
    for key, label in items:
        level, _, variant = key.partition("-")
        cls = f"el {level}" + (" ext" if variant == "ext" else "")
        shape = {"person": "person", "": "box", "ext": "box"}.get(variant, variant)
        if level == "person":
            shape = "person"
        width = 28 + 8 + len(label) * 6.6 + 22
        if x + width > view.width - 20:
            x, y = x0 + 64, y + 30
        if shape == "person":
            mini = (
                f'<path class="shape" d="{_round_rect(x, y + 9, 26, 13, 6)}"/>'
                f'<circle class="shape" cx="{x + 13}" cy="{y + 5}" r="5"/>'
            )
        else:
            outline, extra = shape_path(shape, x, y, 28, 22)
            mini = f'<path class="shape" d="{outline}"/>' + (
                f'<path class="line2" d="{extra}"/>' if extra else ""
            )
        out.append(
            f'<g class="{cls}">{mini}</g><text class="lt" x="{x + 36}" y="{y + 16}">{escape(label)}</text>'
        )
        x += width
    for is_async in sorted(styles):
        label = "Asynchronous" if is_async else "Synchronous"
        width = 44 + len(label) * 6.6 + 22
        if x + width > view.width - 20:
            x, y = x0 + 64, y + 30
        dash = ' stroke-dasharray="7 5"' if is_async else ""
        out.append(
            f'<g class="rel{" async" if is_async else ""}"><path class="line" d="M{x},{y + 11} H{x + 36}"{dash}/></g>'
            f'<text class="lt" x="{x + 44}" y="{y + 16}">{label}</text>'
        )
        x += width
    out.append("</g>")
    return "".join(out), (y - y0) + 40
