"""Static SVG for architecture and topology diagrams.

This is the single drawing of those diagrams: it is the ``svg`` output, and the HTML page
embeds the same markup and only adds behaviour (zoom, pan, dragging boxes, re-routing).
Colours and type come from the stylesheet in ``theme`` (classes and CSS variables, so the
page can switch theme), and everything else is a presentation attribute: there are no
``style=`` attributes, so the page can run under a strict Content-Security-Policy.
"""

from __future__ import annotations

import re
from html import escape

from .icons import KINDS
from .layout import (
    BASE_H,
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
from .theme import CATEGORY_LABELS, GROUP_STYLES, static_diagram_css

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
        '<circle cx="2" cy="2" r="1" class="dot"/></pattern>'
        # A soft shadow under cards; static renderers that skip filters just draw flat.
        '<filter id="lift" x="-10%" y="-10%" width="120%" height="140%">'
        '<feDropShadow dx="0" dy="2" stdDeviation="2.5" flood-color="#0f172a" '
        'flood-opacity=".14"/></filter></defs>'
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
        parts.append(
            f"<style>{static_diagram_css('dark' if 'dark' in classes.split() else 'light')}</style>"
        )
    parts.append(defs_svg())
    return "".join(parts)


#: The silhouette of a node by kind, so a reader tells a database from a queue at a
#: glance: databases are cylinders, queues and streams pipes, functions slanted cards,
#: gateways and balancers chamfered, security controls shields, people and devices pills.
SHAPES: dict[str, str] = {
    **dict.fromkeys(
        ("database", "storage", "backup", "cache", "search", "analytics", "document"),
        "cylinder",
    ),
    **dict.fromkeys(("queue", "topic", "stream", "mail"), "pipe"),
    **dict.fromkeys(("function", "batch", "workflow"), "slant"),
    **dict.fromkeys(
        ("gateway", "api", "loadbalancer", "cdn", "dns", "mesh"), "chamfer"
    ),
    **dict.fromkeys(("firewall", "identity", "secret", "lock"), "shield"),
    **dict.fromkeys(("user", "mobile", "device", "internet", "iot"), "pill"),
}
ICON = 36  # the icon tile
ICON_X = 10
ICON_Y = 12  # centred in the 60px head
TEXT_X = 56  # title and subtitle start right of the tile


def shape_of(kind: str) -> str:
    return SHAPES.get(kind, "card")


def card_path(shape: str, w: float, h: float) -> tuple[str, str]:
    """The outline of a node of ``w`` x ``h`` and an optional rim line (cylinder tops)."""
    if shape == "cylinder":
        e = 7
        return (
            f"M0 {e}A{w / 2} {e} 0 0 1 {w} {e}V{h - e}A{w / 2} {e} 0 0 1 0 {h - e}Z",
            f"M0 {e}A{w / 2} {e} 0 0 0 {w} {e}",
        )
    if shape == "pipe":
        r = min(12, w / 6)
        return (
            f"M{r} 0H{w - r}A{r} {h / 2} 0 0 1 {w - r} {h}H{r}A{r} {h / 2} 0 0 1 {r} 0Z",
            f"M{w - r} 0A{r} {h / 2} 0 0 0 {w - r} {h}",
        )
    if shape == "slant":
        s = 9
        return f"M{s} 0H{w}L{w - s} {h}H0Z", ""
    if shape == "chamfer":
        c = min(12, h / 4)
        return (
            f"M{c} 0H{w - c}L{w} {c}V{h - c}L{w - c} {h}H{c}L0 {h - c}V{c}Z",
            "",
        )
    if shape == "shield":
        c = min(14, h / 3)
        return f"M0 0H{w}V{h - c}Q{w / 2} {h + c / 2} 0 {h - c}Z", ""
    return _rounded(w, h, min(h / 2, 30) if shape == "pill" else 10), ""


def _rounded(w: float, h: float, r: float) -> str:
    return (
        f"M{r} 0H{w - r}A{r} {r} 0 0 1 {w} {r}V{h - r}A{r} {r} 0 0 1 {w - r} {h}"
        f"H{r}A{r} {r} 0 0 1 0 {h - r}V{r}A{r} {r} 0 0 1 {r} 0Z"
    )


def _place_svg(markup: str, x: float, y: float, size: float) -> str:
    """Move a bundled logo (drawn at 10,6 size 20) to ``x``, ``y`` at ``size``."""
    return markup.replace(
        'x="10" y="6" width="20" height="20"',
        f'x="{_num(x)}" y="{_num(y)}" width="{_num(size)}" height="{_num(size)}"',
        1,
    )


_LOGO = re.compile(
    r'<svg class="(brand-logo[^"]*)" x="([-\d.]+)" y="([-\d.]+)" width="([\d.]+)" '
    r'height="([\d.]+)"([^>]*)>(.*?)</svg>',
    re.DOTALL,
)


def share_logos(svg: str) -> str:
    """Write each distinct logo once as a ``<symbol>`` and draw it with ``<use>``.

    Six AWS services would otherwise carry six copies of the AWS mark, which pushes a
    diagram past the size a chat shows inline.
    """
    symbols: dict[str, str] = {}

    def use(match: re.Match) -> str:
        cls, x, y, w, h, attrs, inner = match.groups()
        key = attrs + inner
        if key not in symbols:
            view = re.search(r'viewBox="([^"]+)"', attrs)
            paint = " ".join(re.findall(r'(?:fill|fill-rule|stroke)="[^"]*"', attrs))
            symbols[key] = (
                f'<symbol id="logo-{len(symbols)}" '
                f'viewBox="{view[1] if view else "0 0 24 24"}" {paint}>{inner}</symbol>'
            )
        ref = f"logo-{list(symbols).index(key)}"
        return f'<use class="{cls}" href="#{ref}" x="{x}" y="{y}" width="{w}" height="{h}"/>'

    body = _LOGO.sub(use, svg)
    if not symbols:
        return svg
    return body.replace("</defs>", "".join(symbols.values()) + "</defs>", 1)


def _glyph(kind: str) -> str:
    fragment = KINDS.get(kind, KINDS["service"])
    scale = (ICON - 10) / 24
    return (
        f'<g class="glyph" transform="translate({ICON_X + 5} {ICON_Y + 5}) '
        f'scale({scale:.3f})">{fragment}</g>'
    )


def _icon(b: Box) -> str:
    """The large mark in the tile: the node's own logo, a software brand, or the
    service glyph (Lambda is a function, DynamoDB a database), never just the provider."""
    from .brand_icons import brand_svg

    inner, at = ICON - 8, ICON_X + 4
    if b.logo:
        return (
            f'<image class="logo" href="{_a(b.logo)}" x="{at}" y="{ICON_Y + 4}" '
            f'width="{inner}" height="{inner}" preserveAspectRatio="xMidYMid meet"/>'
        )
    if b.provider == "tech":
        brand = brand_svg(b.provider, b.sub or b.label)
        if brand:
            return _place_svg(brand, at, ICON_Y + 4, inner)
        if b.mono and b.color:
            return (
                f'<rect x="{ICON_X + 3}" y="{ICON_Y + 9}" width="{ICON - 6}" height="18" '
                f'rx="5" fill="{_a(b.color)}"/>'
                f'<text class="t-mono" x="{ICON_X + ICON / 2}" y="{ICON_Y + 21.5}">'
                f"{escape(b.mono)}</text>"
            )
    return _glyph(b.kind)


def _badge(b: Box) -> str:
    """The provider in the top-right corner: its logo when bundled, else its short name."""
    from .brand_icons import brand_svg

    if b.provider in ("tech", "generic"):
        return ""
    logo = brand_svg(b.provider, b.sub or b.label)
    if logo:
        return _place_svg(logo, b.w - 22, 6, 14).replace(
            'class="brand-logo"', 'class="brand-logo badge-logo"', 1
        )
    badge = BADGES.get(b.provider)
    if not badge:
        return ""
    return (
        f'<text class="t-badge prov-{b.provider}" x="{b.w - 10}" y="16" '
        f'text-anchor="end">{badge}</text>'
    )


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
            f'<g class="node cat-{b.category} shape-{shape_of(b.kind)}" '
            f'data-id="{_a(b.id)}" data-kind="{_a(b.kind)}" '
            f'data-note="{_a(b.note)}" transform="translate({_num(b.x)} {_num(b.y)})">'
        ),
    ]
    outline, rim = card_path(shape_of(b.kind), b.w, b.h)
    # rect.card is the node's box (what is dragged, measured and hit); the silhouette
    # drawn over it is path.shape
    out.append(f'<rect class="card" width="{b.w}" height="{b.h}" rx="10"/>')
    out.append(f'<path class="shape" d="{outline}" filter="url(#lift)"/>')
    if rim:
        out.append(f'<path class="card-rim" d="{rim}"/>')
    # a white tile keeps logos and glyphs legible on any card colour or theme
    out.append(
        f'<rect class="icon-tile" x="{ICON_X}" y="{ICON_Y}" width="{ICON}" height="{ICON}" '
        'rx="9"/>'
    )
    out.append(_icon(b))
    out.append(_badge(b))
    title_y, sub_y = (TITLE_Y - 8, SUB_Y - 6) if b.sub else (TITLE_Y - 3, 0)
    out.append(
        f'<text class="t-title" x="{TEXT_X}" y="{title_y}">{escape(b.label)}</text>'
    )
    if b.sub:
        out.append(
            f'<text class="t-sub" x="{TEXT_X}" y="{sub_y}">{escape(b.sub)}</text>'
        )
    if b.docs:
        out.append(
            f'<text class="t-docs" x="{b.w - 10}" y="{BASE_H - 9}" text-anchor="end">'
            "docs ↗</text>"
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
    return share_logos("".join(parts))


__all__ = [
    "GROUP_HEADER",
    "architecture_svg",
    "canvas_svg",
    "defs_svg",
    "legend_svg",
    "legend_width",
    "root_open",
]
