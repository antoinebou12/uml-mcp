"""Static SVG for architecture and topology diagrams.

This is the single drawing of those diagrams: it is the ``svg`` output, and the HTML page
embeds the same markup and only adds behaviour (zoom, pan, dragging boxes, re-routing).
Colours and type come from the stylesheet in ``theme`` (classes and CSS variables, so the
page can switch theme), and everything else is a presentation attribute: there are no
``style=`` attributes, so the page can run under a strict Content-Security-Policy.
"""

from __future__ import annotations

from html import escape

from .icons import KINDS
from .layout import (
    GROUP_HEADER,
    MARGIN,
    Box,
    Edge,
    GroupBox,
    Layout,
    legend_width,
    mono_width,
)
from .router import rounded_path
from .theme import CATEGORY_LABELS, GROUP_STYLES, diagram_css

#: provider -> the badge printed on a node (none for generic and software nodes)
BADGES = {
    "aws": "AWS",
    "azure": "AZURE",
    "gcp": "GCP",
    "kubernetes": "K8S",
    "onprem": "ON-PREM",
}
TITLE_Y = 38
SUB_Y = 52


def _a(value: object) -> str:
    return escape(str(value), quote=True)


def _num(value: float) -> str:
    text = f"{value:.1f}"
    return text.removesuffix(".0")


def defs_svg() -> str:
    """Arrowheads and the dotted canvas pattern, shared by every diagram family."""
    heads = "".join(
        f'<marker id="{mid}" viewBox="0 0 8 6" refX="7.5" refY="3" markerWidth="8" '
        f'markerHeight="6" orient="auto"><polygon points="0 0, 8 3, 0 6" class="{cls}"/></marker>'
        for mid, cls in (
            ("arrow", "head"),
            ("arrow-dashed", "head-dashed"),
            ("arrow-primary", "head-primary"),
        )
    )
    return (
        f"<defs>{heads}"
        '<pattern id="dots" width="20" height="20" patternUnits="userSpaceOnUse">'
        '<circle cx="2" cy="2" r="1" class="dot"/></pattern></defs>'
    )


#: In the page the canvas is far larger than the drawing, so the dots fill the view
#: however it is zoomed or panned. An export shrinks it back to the drawing.
BLEED = 6000


def canvas_svg(width: float, height: float, *, page: bool = False) -> str:
    """The panel and its dots; ``rect.bg`` is what an export resizes to cover everything."""
    x = y = -BLEED if page else 0
    w = width + 2 * BLEED if page else width
    h = height + 2 * BLEED if page else height
    size = f'x="{x}" y="{y}" width="{_num(w)}" height="{_num(h)}"'
    return (
        f'<rect class="panel bg" {size}/>'
        f'<rect class="dotfill" {size} fill="url(#dots)"/>'
    )


def root_open(
    *,
    dom_id: str,
    classes: str,
    label: str,
    width: float,
    height: float,
    page: bool,
    description: str = "",
) -> str:
    size = (
        'width="100%" height="100%"'
        if page
        else f'width="{_num(width)}" height="{_num(height)}"'
    )
    parts = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" id="{dom_id}" class="{classes}" '
            f'role="img" aria-label="{_a(label)}" viewBox="0 0 {_num(width)} {_num(height)}" '
            f'{size} preserveAspectRatio="xMidYMid meet">'
        ),
        f"<title>{escape(label)}</title>",
    ]
    if description:
        parts.append(f"<desc>{escape(description)}</desc>")
    if not page:  # the page carries the stylesheet once, in its own <style>
        parts.append(f"<style>{diagram_css()}</style>")
    parts.append(defs_svg())
    return "".join(parts)


def _glyph(kind: str) -> str:
    fragment = KINDS.get(kind, KINDS["service"])
    return f'<g class="glyph" transform="translate(10 8) scale(0.667)">{fragment}</g>'


def _icon(b: Box) -> str:
    if b.logo:
        return (
            f'<image class="logo" href="{_a(b.logo)}" x="10" y="8" width="20" height="20" '
            'preserveAspectRatio="xMidYMid meet"/>'
        )
    if b.mono and b.color:
        return (
            f'<rect x="10" y="9" width="26" height="16" rx="4" fill="{_a(b.color)}"/>'
            f'<text class="t-mono" x="23" y="20.5">{escape(b.mono)}</text>'
        )
    return _glyph(b.kind)


def group_svg(g: GroupBox) -> str:
    category, border = GROUP_STYLES.get(g.type, ("external", "solid"))
    box_class = "group-box" + ("" if border == "solid" else f" {border}")
    return (
        f'<g class="group g-{category}" data-id="{_a(g.id)}" data-type="{_a(g.type)}">'
        f'<rect class="{box_class}" x="{_num(g.x)}" y="{_num(g.y)}" width="{_num(g.w)}" '
        f'height="{_num(g.h)}" rx="10"/>'
        f'<text class="t-group" x="{_num(g.x + 14)}" y="{_num(g.y + 4)}">{escape(g.label)}</text></g>'
    )


def node_svg(b: Box) -> str:
    out = [
        (
            f'<g class="node cat-{b.category}" data-id="{_a(b.id)}" data-kind="{_a(b.kind)}" '
            f'data-note="{_a(b.note)}" transform="translate({_num(b.x)} {_num(b.y)})">'
        ),
        f'<rect class="card" width="{b.w}" height="{b.h}" rx="8"/>',
        _icon(b),
    ]
    badge = BADGES.get(b.provider)
    if badge:
        out.append(
            f'<text class="t-badge prov-{b.provider}" x="{b.w - 10}" y="19" '
            f'text-anchor="end">{badge}</text>'
        )
    out.append(
        f'<text class="t-title" x="{_num(b.w / 2)}" y="{TITLE_Y}" text-anchor="middle">'
        f"{escape(b.label)}</text>"
    )
    if b.sub:
        out.append(
            f'<text class="t-sub" x="{_num(b.w / 2)}" y="{SUB_Y}" text-anchor="middle">'
            f"{escape(b.sub)}</text>"
        )
    for i, name in enumerate(b.inputs):
        y = b.port_y(i)
        out.append(
            f'<circle class="port in" data-port="{_a(name)}" cx="0" cy="{y}" r="4.5"/>'
            f'<text class="t-port" x="12" y="{y + 3.5}">{escape(name)}</text>'
        )
    for i, name in enumerate(b.outputs):
        y = b.port_y(i)
        out.append(
            f'<circle class="port out" data-port="{_a(name)}" cx="{b.w}" cy="{y}" r="4.5"/>'
            f'<text class="t-port" x="{b.w - 12}" y="{y + 3.5}" text-anchor="end">'
            f"{escape(name)}</text>"
        )
    out.append("</g>")
    return "".join(out)


def edge_svg(e: Edge) -> str:
    kind = e.style if e.style in ("dashed", "primary") else ""
    marker = {"dashed": "arrow-dashed", "primary": "arrow-primary"}.get(kind, "arrow")
    parts = [
        (
            f'<g class="edge {kind}" data-id="{_a(e.id)}" data-from="{_a(e.source)}" '
            f'data-to="{_a(e.target)}">'
        ),
        f'<path class="edge-line" d="{rounded_path(e.points)}" marker-end="url(#{marker})"/>',
    ]
    if e.label:
        x, y = e.label_at
        parts.append(
            f'<g class="edge-label" transform="translate({_num(x)} {_num(y)})">'
            f'<text class="t-edge" y="3.5">{escape(e.label)}</text></g>'
        )
    parts.append("</g>")
    return "".join(parts)


def legend_svg(items: list[tuple[str, int]], x: float, y: float) -> str:
    """One swatch per category in use, with how many nodes belong to it."""
    parts = [
        f'<g class="legend" transform="translate({_num(x)} {_num(y)})">',
        '<text class="t-legend-head" x="0" y="0">Legend</text>',
    ]
    cursor = mono_width("Legend", 12) + 22
    for category, count in items:
        name = CATEGORY_LABELS[category]
        parts.append(
            f'<g class="cat-{category}"><rect class="swatch" x="{_num(cursor)}" y="-10" '
            f'width="18" height="12" rx="3"/>'
            f'<text class="t-legend" x="{_num(cursor + 26)}" y="0">{escape(name)}</text>'
            f'<text class="t-count" x="{_num(cursor + 26 + mono_width(name, 11) + 6)}" y="0">'
            f"{count}</text></g>"
        )
        cursor += 18 + 8 + mono_width(name, 11) + 6 + mono_width(str(count), 10) + 22
    parts.append("</g>")
    return "".join(parts)


def _depth(group: GroupBox, by_id: dict[str, GroupBox]) -> int:
    depth, current = 0, group.parent
    while current is not None:
        depth += 1
        current = by_id[current].parent
    return depth


def architecture_svg(
    layout: Layout,
    *,
    title: str | None,
    theme: str,
    page: bool = False,
    description: str = "",
) -> str:
    """The diagram as an ``<svg>`` element. ``page=True`` makes it fill its container."""
    by_id = {g.id: g for g in layout.groups}
    groups = sorted(layout.groups, key=lambda g: (_depth(g, by_id), g.y, g.x))
    parts = [
        root_open(
            dom_id="diagram",
            classes=f"d3d arch {theme}",
            label=title or "Architecture diagram",
            width=layout.width,
            height=layout.height,
            page=page,
            description=description,
        ),
        canvas_svg(layout.width, layout.height, page=page),
        '<g class="viewport">',
    ]
    if title and not page:
        parts.append(
            f'<text class="t-heading" x="{MARGIN}" y="34">{escape(title)}</text>'
        )
    parts.append('<g class="groups">' + "".join(group_svg(g) for g in groups) + "</g>")
    parts.append(
        '<g class="edges">' + "".join(edge_svg(e) for e in layout.edges) + "</g>"
    )
    parts.append(
        '<g class="nodes">' + "".join(node_svg(b) for b in layout.boxes) + "</g>"
    )
    if layout.legend:
        parts.append(legend_svg(layout.legend, MARGIN, layout.legend_y))
    parts.append("</g></svg>")
    return "".join(parts)


__all__ = [
    "GROUP_HEADER",
    "architecture_svg",
    "canvas_svg",
    "defs_svg",
    "legend_svg",
    "legend_width",
    "root_open",
]
