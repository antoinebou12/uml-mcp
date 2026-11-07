"""Draw a laid-out schema as SVG: table cards, group containers, crow's-foot edges.

Colours only ever come from CSS classes. The static SVG carries one literal palette; the
interactive page carries ``var(--name)`` rules and both palettes, so its theme toggle works
without re-rendering and without inline ``style`` attributes (its CSP forbids them).
"""

from __future__ import annotations

import re
from html import escape

from .layout import HEADER, MARGIN, ROW, Card, Layout, Route, clip
from .model import Schema

PALETTES: dict[str, dict[str, str]] = {
    "light": {
        "bg": "#f6f7f9",
        "dot": "#dfe3ea",
        "card": "#ffffff",
        "stroke": "#cfd6e1",
        "head": "#eef2f8",
        "zebra": "#f8f9fb",
        "ink": "#18202e",
        "muted": "#677084",
        "type": "#6a52b3",
        "pk": "#b57f00",
        "fk": "#2a72d6",
        "edge": "#8a95a8",
        "accent": "#e8590c",
        "badge": "#eef0f4",
        "join": "#0f8a6a",
        "t0": "#2a72d6",
        "t1": "#0f8a6a",
        "t2": "#b57f00",
        "t3": "#8b4fd1",
        "t4": "#c2410c",
        "t5": "#0e7490",
    },
    "dark": {
        "bg": "#0e131d",
        "dot": "#1d2534",
        "card": "#161d2a",
        "stroke": "#2c374a",
        "head": "#1d2637",
        "zebra": "#192131",
        "ink": "#e7ebf3",
        "muted": "#96a1b6",
        "type": "#b9a7f5",
        "pk": "#f1c24f",
        "fk": "#6fa9ff",
        "edge": "#6c7a92",
        "accent": "#ff8a4c",
        "badge": "#232d3f",
        "join": "#3ccf9f",
        "t0": "#6fa9ff",
        "t1": "#3ccf9f",
        "t2": "#f1c24f",
        "t3": "#b98af5",
        "t4": "#ff8a4c",
        "t5": "#4cc3dc",
    },
}
TONES = 6
FONT = "Inter,ui-sans-serif,system-ui,-apple-system,'Segoe UI',Roboto,sans-serif"
MONO = "ui-monospace,'SFMono-Regular','Cascadia Code',Menlo,Consolas,monospace"

#: A key and a chain link, 12 x 12, drawn with strokes in currentColor.
ICONS = (
    '<symbol id="i-key" viewBox="0 0 12 12"><circle cx="3.6" cy="6" r="2.5" '
    'fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M6 6h5.2M9.4 6v2.2M11 6v1.6" '
    'fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></symbol>'
    '<symbol id="i-link" viewBox="0 0 12 12"><path d="M5 7.2 7.2 5M4.4 5.6 3.2 6.8a1.9 1.9 0 0 0 '
    '2.7 2.7l1.2-1.2M7.6 6.4l1.2-1.2a1.9 1.9 0 0 0-2.7-2.7L4.9 3.7" fill="none" '
    'stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></symbol>'
)


def css(pal: dict[str, str]) -> str:
    """The diagram stylesheet over a palette (literal colours or ``var(--x)``)."""
    tones = "".join(
        f".tone-{i} .gbox{{fill:{pal[f't{i}']};stroke:{pal[f't{i}']}}}"
        f".tone-{i} .glabel{{fill:{pal[f't{i}']}}}"
        f".tone-{i} .accentbar{{fill:{pal[f't{i}']}}}"
        for i in range(TONES)
    )
    return (
        f".bg{{fill:{pal['bg']}}}.dots{{fill:{pal['dot']}}}"
        f"text{{font-family:{FONT};fill:{pal['ink']}}}"
        f".title{{font-size:20px;font-weight:700}}.subtitle{{font-size:12.5px;fill:{pal['muted']}}}"
        f".gbox{{fill-opacity:.07;stroke-opacity:.45;stroke-width:1.2;stroke-dasharray:6 5}}"
        f".glabel{{font-size:12px;font-weight:700;letter-spacing:.08em}}"
        f".card{{fill:{pal['card']};stroke:{pal['stroke']};stroke-width:1.2}}"
        f".head{{fill:{pal['head']}}}.accentbar{{fill:{pal['fk']}}}"
        f".tname{{font-size:14px;font-weight:700}}.tmeta{{font-size:11px;fill:{pal['muted']}}}"
        f".zebra{{fill:{pal['zebra']}}}.sep{{stroke:{pal['stroke']};stroke-width:1}}"
        f".cname{{font-size:12.5px}}.pkname{{font-weight:700}}"
        f".ctype{{font-family:{MONO};font-size:11px;fill:{pal['type']}}}"
        f".pk{{color:{pal['pk']}}}.fk{{color:{pal['fk']}}}"
        f".pill{{fill:{pal['badge']}}}.pilltext{{font-size:9.5px;font-weight:700;fill:{pal['muted']}}}"
        f".joinpill{{fill:{pal['join']};fill-opacity:.16}}.jointext{{font-size:9.5px;font-weight:700;fill:{pal['join']}}}"
        f".wire,.mark{{fill:none;stroke:{pal['edge']};stroke-width:1.5;stroke-linejoin:round}}"
        f".dot-o{{fill:{pal['card']};stroke:{pal['edge']};stroke-width:1.5}}"
        f".rlabel{{font-size:11px;fill:{pal['muted']}}}"
        f".hit{{fill:none;stroke:transparent;stroke-width:12}}"
        f".rel.on .wire,.rel.on .mark{{stroke:{pal['accent']};stroke-width:2.4}}"
        f".rel.on .dot-o{{stroke:{pal['accent']}}}"
        f".table.on .card{{stroke:{pal['accent']};stroke-width:2.2}}"
        f".col.on .zebra,.col.hl .zebra{{fill:{pal['accent']};fill-opacity:.16}}"
        f".dim{{opacity:.22}}.table,.rel,.group{{transition:opacity .15s}}" + tones
    )


def palette_vars(name: str) -> str:
    return ";".join(f"--{k}:{v}" for k, v in PALETTES[name].items())


def slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", name).strip("-") or "t"


def _ids(schema: Schema) -> dict[str, str]:
    out: dict[str, str] = {}
    for t in schema.tables:
        base = slug(t.name)
        key, n = base, 2
        while key in out.values():
            key, n = f"{base}-{n}", n + 1
        out[t.name] = key
    return out


def _f(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".")


def _card(card: Card, tid: str, tone: int | None, join: bool) -> str:
    t = card.table
    x, y, w, h = card.x, card.y, card.w, card.h
    tone_cls = f" tone-{tone}" if tone is not None else ""
    parts = [
        f'<g class="table{tone_cls}" id="t-{tid}" data-table="{escape(t.name)}">',
        f'<rect class="card" x="{x}" y="{y}" width="{w}" height="{h}" rx="9"/>',
        (
            f'<path class="head" d="M{x + 1} {y + HEADER}V{y + 9}a8 8 0 0 1 8-8h{w - 18}'
            f'a8 8 0 0 1 8 8V{y + HEADER}Z"/>'
        ),
        f'<rect class="accentbar" x="{x + 1}" y="{y + 9}" width="3" height="{HEADER - 14}" rx="1.5"/>',
        f'<text class="tname" x="{x + 14}" y="{y + 22}">{escape(clip(t.name, 40))}</text>',
    ]
    if join:
        parts.append(
            f'<rect class="joinpill" x="{x + w - 46}" y="{y + 10}" width="36" height="15" rx="7.5"/>'
            f'<text class="jointext" x="{x + w - 28}" y="{y + 21}" text-anchor="middle">M:N</text>'
        )
    parts.append(
        f'<line class="sep" x1="{x}" y1="{y + HEADER}" x2="{x + w}" y2="{y + HEADER}"/>'
    )
    type_x = x + 36 + card.name_w + 14
    for i, c in enumerate(t.columns):
        ry = y + HEADER + i * ROW
        cy = ry + ROW / 2
        parts.append(f'<g class="col" data-col="{escape(c.name)}">')
        opacity = "" if i % 2 else ' fill-opacity="0"'
        parts.append(
            f'<rect class="zebra" x="{x + 1}" y="{ry}" width="{w - 2}" height="{ROW}"{opacity}/>'
        )
        if c.pk:
            parts.append(
                f'<use class="pk" href="#i-key" x="{x + 9}" y="{_f(cy - 6)}" width="12" height="12"/>'
            )
        if c.fk:
            parts.append(
                f'<use class="fk" href="#i-link" x="{x + (21 if c.pk else 9)}" y="{_f(cy - 6)}" '
                'width="12" height="12"/>'
            )
        name_cls = "cname pkname" if c.pk else "cname"
        parts.append(
            f'<text class="{name_cls}" x="{x + 36}" y="{_f(cy + 4.3)}">{escape(clip(c.name, 32))}</text>'
        )
        if c.type:
            parts.append(
                f'<text class="ctype" x="{_f(type_x)}" y="{_f(cy + 4)}">{escape(clip(c.type, 24))}</text>'
            )
        right = x + w - 10
        for flag, label, width in (
            (c.nullable and not c.pk, "null", 28),
            (c.unique and not c.pk, "UQ", 22),
        ):
            if not flag:
                continue
            right -= width
            parts.append(
                f'<rect class="pill" x="{_f(right)}" y="{_f(cy - 7.5)}" width="{width - 4}" height="15" rx="4"/>'
                f'<text class="pilltext" x="{_f(right + (width - 4) / 2)}" y="{_f(cy + 3.4)}" '
                f'text-anchor="middle">{label}</text>'
            )
        parts.append("</g>")
    parts.append("</g>")
    return "".join(parts)


def _marks(x: float, y: float, d: int, card: str, optional: bool) -> str:
    """Crow's-foot notation at a card edge ``(x, y)``; the line runs out along ``d``."""
    out = []
    if card == "many":
        out.append(
            f'<path class="mark" d="M{_f(x)} {_f(y - 7)}L{_f(x + d * 13)} {_f(y)}'
            f'L{_f(x)} {_f(y + 7)}M{_f(x)} {_f(y)}H{_f(x + d * 13)}"/>'
        )
        second = x + d * 19
    else:
        out.append(f'<path class="mark" d="M{_f(x + d * 9)} {_f(y - 6)}v12"/>')
        second = x + d * 15
    if optional:
        out.append(
            f'<circle class="dot-o" cx="{_f(second + d * 2)}" cy="{_f(y)}" r="3.6"/>'
        )
    else:
        out.append(f'<path class="mark" d="M{_f(second)} {_f(y - 6)}v12"/>')
    return "".join(out)


def _path(points: list[tuple[float, float]], radius: float = 7) -> str:
    """A polyline with rounded corners."""
    if len(points) < 3:
        return "M" + "L".join(f"{_f(x)} {_f(y)}" for x, y in points)
    d = [f"M{_f(points[0][0])} {_f(points[0][1])}"]
    for i in range(1, len(points) - 1):
        (x0, y0), (x1, y1), (x2, y2) = points[i - 1], points[i], points[i + 1]
        r = min(radius, abs(x1 - x0 + y1 - y0) / 2, abs(x2 - x1 + y2 - y1) / 2)
        ax = x1 - r * ((x1 > x0) - (x1 < x0))
        ay = y1 - r * ((y1 > y0) - (y1 < y0))
        bx = x1 + r * ((x2 > x1) - (x2 < x1))
        by = y1 + r * ((y2 > y1) - (y2 < y1))
        d.append(f"L{_f(ax)} {_f(ay)}Q{_f(x1)} {_f(y1)} {_f(bx)} {_f(by)}")
    d.append(f"L{_f(points[-1][0])} {_f(points[-1][1])}")
    return "".join(d)


def _route(i: int, r: Route) -> str:
    rel = r.relation
    d = _path(r.points)
    (sx, sy), (tx, ty) = r.points[0], r.points[-1]
    out = [
        (
            f'<g class="rel" id="r-{i}" data-from="{escape(rel.source)}" data-to="{escape(rel.target)}" '
            f'data-fcol="{escape(rel.source_column)}" data-tcol="{escape(rel.target_column)}">'
        ),
        (
            f"<title>{escape(rel.source)}.{escape(', '.join(rel.columns))} → "
            f"{escape(rel.target)}.{escape(rel.target_column)}</title>"
        ),
        f'<path class="hit" d="{d}"/><path class="wire" d="{d}"/>',
        _marks(sx, sy, r.source_dir, rel.source_card, rel.optional),
        _marks(tx, ty, r.target_dir, rel.target_card, False),
    ]
    if rel.label:
        segs = list(zip(r.points, r.points[1:], strict=False))
        (ax, ay), (bx, by) = max(
            segs, key=lambda s: abs(s[1][0] - s[0][0]) + abs(s[1][1] - s[0][1])
        )
        lx, ly = (ax + bx) / 2, (ay + by) / 2
        anchor = "middle" if ay == by else "start"
        out.append(
            f'<text class="rlabel" x="{_f(lx + (0 if ay == by else 6))}" y="{_f(ly - 5)}" '
            f'text-anchor="{anchor}">{escape(clip(rel.label, 40))}</text>'
        )
    out.append("</g>")
    return "".join(out)


def svg_parts(
    schema: Schema, lay: Layout, *, static: bool, theme: str
) -> tuple[str, str]:
    """The ``<svg>`` element and its stylesheet."""
    ids = _ids(schema)
    tone_of = {g.name: i % TONES for i, g in enumerate(lay.groups)}
    w, h = lay.width, lay.height
    pal = PALETTES[theme] if static else {k: f"var(--{k})" for k in PALETTES["light"]}
    sheet = css(pal)
    style = f"<style>{sheet}</style>" if static else ""
    n_t, n_r = len(schema.tables), len(schema.relations)
    sub = f"{n_t} table{'s' * (n_t != 1)} · {n_r} relationship{'s' * (n_r != 1)}"
    body = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'class="schema" role="img" aria-label="{escape(schema.title)}">'
        ),
        f"<title>{escape(schema.title)}</title>",
        (
            f"<defs>{ICONS}"
            '<pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse">'
            '<circle class="dots" cx="2" cy="2" r="1"/></pattern></defs>'
        ),
        style,
        f'<rect class="bg" width="{w}" height="{h}"/>',
        f'<rect width="{w}" height="{h}" fill="url(#dots)"/>',
        (
            f'<g class="heading"><text class="title" x="{MARGIN}" y="{MARGIN + 14}">'
            f"{escape(clip(schema.title, 80))}</text>"
            f'<text class="subtitle" x="{MARGIN}" y="{MARGIN + 33}">{sub}</text></g>'
        ),
        '<g class="groups">',
    ]
    for g in lay.groups:
        tone = tone_of[g.name]
        label = clip(g.name.upper(), 40)
        body.append(
            f'<g class="group tone-{tone}" data-group="{escape(g.name)}">'
            f'<rect class="gbox" x="{_f(g.x)}" y="{_f(g.y)}" width="{_f(g.w)}" height="{_f(g.h)}" rx="14"/>'
            f'<text class="glabel" x="{_f(g.x + 16)}" y="{_f(g.y + 23)}">{escape(label)}</text></g>'
        )
    body.append('</g><g class="rels">')
    body += [_route(i, r) for i, r in enumerate(lay.routes)]
    body.append('</g><g class="tables">')
    for t in schema.tables:
        tone = tone_of.get(t.group) if t.group else None
        body.append(
            _card(lay.cards[t.name], ids[t.name], tone, t.name in schema.join_tables)
        )
    body.append("</g></svg>")
    return "".join(body), sheet


def render_svg(schema: Schema, lay: Layout, theme: str) -> str:
    svg, _ = svg_parts(schema, lay, static=True, theme=theme)
    return svg
