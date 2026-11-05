"""Turn a layout into SVG. A ``Skin`` supplies the look; this module owns the mechanics.

Colours are only ever used through CSS classes. A static SVG gets a literal palette; the
interactive page gets ``var(--name)`` values plus both palettes, so the theme toggle works
without re-rendering and without inline ``style`` attributes (the page CSP forbids them).
Presets work the same way: static output carries the chosen preset's rules, the page carries
every preset scoped to ``:root[data-preset=...]``.
"""

from __future__ import annotations

from html import escape
from typing import ClassVar

from .layout import Box, Layout, Metrics, Placed, Route
from .spec import EDGE_TONES, Group, Node, Spec

Rules = tuple[tuple[str, str], ...]  # (selector, declarations)


class Skin:
    """Look and feel: node and group markup, palettes, presets and extra CSS."""

    name: ClassVar[str] = "base"
    metrics: ClassVar[Metrics]
    group_styles: ClassVar[tuple[str, ...]] = ("plain",)
    #: whether nodes without a ``tone`` borrow the tone of their group
    inherit_tone: ClassVar[bool] = False
    palettes: ClassVar[dict[str, dict[str, str]]]
    #: preset name -> CSS rules; the first preset is the default. Empty: no presets
    presets: ClassVar[dict[str, Rules]] = {}
    #: draw a soft underlay beneath each edge (shown by presets that want a glow)
    glow: ClassVar[bool] = False

    def group_tone(self, group: Group) -> str | None:
        return group.tone

    def background(self, width: float, height: float) -> str:
        raise NotImplementedError

    def group(self, box: Box, tone: str | None) -> str:
        raise NotImplementedError

    def node(self, placed: Placed, tone: str | None) -> str:
        raise NotImplementedError

    def css(self, pal: dict[str, str]) -> str:
        raise NotImplementedError

    # Optional chrome around the diagram. Heights of 0 draw nothing.
    def header_height(self, spec: Spec) -> int:
        return 0

    def header(self, spec: Spec, width: float, theme: str) -> str:
        return ""

    def legend_height(self, spec: Spec) -> int:
        return 0

    def legend(
        self, spec: Spec, width: float, y: float, counts: list[tuple[str, str, int]]
    ) -> str:
        return ""

    def frame(self, width: float, height: float) -> str:
        """Decoration over the whole canvas, e.g. corner brackets."""
        return ""


def tone_css(pal: dict[str, str]) -> str:
    rules = [
        ".ico{fill:none}",
        ".e-dash{stroke-dasharray:6 5}",
        ".dim{opacity:.16}",
        ".step-n{fill:#fff;font:700 10px system-ui,sans-serif}",
    ]
    for key in EDGE_TONES:
        color = pal[key]
        rules.append(
            f".e-{key}{{fill:none;stroke:{color};stroke-width:1.6}}"
            f".m-{key}{{fill:{color}}}.s-{key}{{stroke:{color}}}"
            f".f-{key}{{fill:{color}}}.l-{key}{{fill:{color}}}"
            f".t-{key}{{fill:{color};fill-opacity:.07;stroke:{color}}}"
        )
    rules.append(f".s-ink{{stroke:{pal['ink']}}}")
    return "".join(rules)


def rounded_path(points: list[tuple[float, float]], radius: float = 8) -> str:
    """An orthogonal polyline with rounded corners."""
    if len(points) < 3:
        return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in points)
    parts = [f"M{points[0][0]:.1f} {points[0][1]:.1f}"]

    def toward(
        a: tuple[float, float], b: tuple[float, float], dist: float
    ) -> tuple[float, float]:
        length = abs(b[0] - a[0]) + abs(b[1] - a[1]) or 1
        return (
            a[0] + (b[0] - a[0]) * dist / length,
            a[1] + (b[1] - a[1]) * dist / length,
        )

    for prev, corner, nxt in zip(points, points[1:], points[2:], strict=False):
        d_in = abs(corner[0] - prev[0]) + abs(corner[1] - prev[1])
        d_out = abs(nxt[0] - corner[0]) + abs(nxt[1] - corner[1])
        r = min(radius, d_in / 2, d_out / 2)
        if r < 1:
            parts.append(f"L{corner[0]:.1f} {corner[1]:.1f}")
            continue
        start, end = toward(corner, prev, r), toward(corner, nxt, r)
        parts.append(
            f"L{start[0]:.1f} {start[1]:.1f}Q{corner[0]:.1f} {corner[1]:.1f} {end[0]:.1f} {end[1]:.1f}"
        )
    parts.append(f"L{points[-1][0]:.1f} {points[-1][1]:.1f}")
    return "".join(parts)


def _step_badge(route: Route, step: int, tone: str) -> str:
    """A numbered circle a little way along the first segment of an edge."""
    (x1, y1), (x2, y2) = route.points[0], route.points[1]
    length = abs(x2 - x1) + abs(y2 - y1) or 1
    t = min(18.0, length / 2) / length
    x, y = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
    return (
        f'<circle class="step f-{tone}" cx="{x:.1f}" cy="{y:.1f}" r="9"/>'
        f'<text class="step-n" x="{x:.1f}" y="{y + 3.5:.1f}" text-anchor="middle">{step}</text>'
    )


def edge_svg(route: Route, skin: Skin) -> str:
    edge = route.edge
    d = rounded_path(route.points)
    dash = " e-dash" if edge.dashed else ""
    glow = f'<path class="glow e-{edge.tone}" d="{d}"/>' if skin.glow else ""
    out = (
        f'<g class="edge" data-from="{escape(edge.source, quote=True)}" data-to="{escape(edge.target, quote=True)}">'
        f'{glow}<path class="line e-{edge.tone}{dash}" d="{d}" marker-end="url(#ar-{edge.tone})"/>'
    )
    if edge.step is not None:
        out += _step_badge(route, edge.step, edge.tone)
    if route.label:
        x, y, anchor = route.label
        out += (
            f'<text class="elabel l-{edge.tone}" x="{x:.1f}" y="{y:.1f}" '
            f'text-anchor="{anchor}">{escape(edge.label)}</text>'
        )
    return out + "</g>"


def marker_defs(tones: set[str]) -> str:
    return "".join(
        f'<marker id="ar-{tone}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        f'markerHeight="7" orient="auto"><path class="m-{tone}" d="M0 0L10 5L0 10z"/></marker>'
        for tone in sorted(tones)
    )


def vars_css(skin: Skin) -> str:
    """``:root[data-theme=...]`` blocks holding every palette entry as a custom property."""
    blocks = []
    for theme, pal in skin.palettes.items():
        body = "".join(f"--{key}:{value};" for key, value in pal.items())
        blocks.append(f':root[data-theme="{theme}"]{{{body}}}')
    return "".join(blocks)


def preset_css(skin: Skin, preset: str, *, live: bool) -> str:
    if not skin.presets:
        return ""
    if not live:
        return "".join(f"{sel}{{{decl}}}" for sel, decl in skin.presets[preset])
    return "".join(
        f':root[data-preset="{name}"] {sel}{{{decl}}}'
        for name, rules in skin.presets.items()
        for sel, decl in rules
    )


def node_tone(spec: Spec, skin: Skin, node: Node) -> str | None:
    """A node's tone: its own, else (for skins that inherit) the nearest group's."""
    if node.tone:
        return node.tone
    if not skin.inherit_tone:
        return None
    groups = {g.id: g for g in spec.groups}
    cursor = groups.get(node.group) if node.group else None
    while cursor is not None:
        tone = skin.group_tone(cursor)
        if tone:
            return tone
        cursor = groups.get(cursor.parent) if cursor.parent else None
    return None


def legend_counts(spec: Spec, skin: Skin) -> list[tuple[str, str, int]]:
    """``(style, tone, node count)`` for every group style in use, in first-use order."""
    groups = {g.id: g for g in spec.groups}
    order: dict[str, list[int | str]] = {}
    for node in spec.nodes:
        cursor = groups.get(node.group) if node.group else None
        if cursor is None:
            continue
        tone = skin.group_tone(cursor) or "gray"
        entry = order.setdefault(cursor.style, [tone, 0])
        entry[1] = int(entry[1]) + 1
    return [(style, str(v[0]), int(v[1])) for style, v in order.items()]


def svg_parts(
    spec: Spec,
    lay: Layout,
    skin: Skin,
    *,
    theme: str,
    live: bool,
) -> tuple[str, str]:
    """Return ``(svg_markup_without_style, css)``."""
    source = skin.palettes[theme]
    pal = {key: f"var(--{key})" for key in source} if live else source

    top = 0 if live else skin.header_height(spec)  # the page has its own header
    counts = legend_counts(spec, skin)
    foot = skin.legend_height(spec) if counts else 0
    width = lay.width
    height = lay.height + top + foot

    markers = marker_defs({r.edge.tone for r in lay.routes})
    body = (
        "".join(skin.group(box, skin.group_tone(box.group)) for box in lay.boxes)
        + "".join(edge_svg(route, skin) for route in lay.routes)
        + "".join(skin.node(p, node_tone(spec, skin, p.node)) for p in lay.nodes)
    )
    chrome = skin.header(spec, width, theme) if top else ""
    legend = skin.legend(spec, width, top + lay.height, counts) if foot else ""
    label = escape(spec.title, quote=True)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" role="img" aria-label="{label}" '
        f'class="diagram"><title>{escape(spec.title)}</title><defs>{markers}</defs>'
        f"{skin.background(width, height)}{chrome}"
        f'<g class="scene" transform="translate(0 {top})">{body}</g>'
        f"{skin.frame(width, height)}{legend}</svg>"
    )
    css = tone_css(pal) + skin.css(pal) + preset_css(skin, spec.preset, live=live)
    return svg, css


def resolve_theme(spec: Spec) -> str:
    """The theme for static output: ``auto`` is dark."""
    return "dark" if spec.theme == "auto" else spec.theme


def render_svg(spec: Spec, lay: Layout, skin: Skin) -> str:
    """A static, self-contained SVG in the spec's theme (literal colours, no scripts)."""
    svg, css = svg_parts(spec, lay, skin, theme=resolve_theme(spec), live=False)
    return svg.replace("<defs>", f"<style>{css}</style><defs>", 1)


__all__ = [
    "Skin",
    "edge_svg",
    "marker_defs",
    "node_tone",
    "preset_css",
    "render_svg",
    "resolve_theme",
    "svg_parts",
    "vars_css",
]
