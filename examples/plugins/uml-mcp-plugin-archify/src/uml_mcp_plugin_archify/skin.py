"""The archify look: tinted dashed containers, glowing icon cards, legend and presets.

Presets are pure CSS over one SVG: ``classic`` (dot grid), ``blueprint`` (line grid, corner
brackets, dash-dot containers) and ``flow`` (soft glow under every edge).
"""

from __future__ import annotations

from html import escape
from typing import ClassVar

from uml_mcp_plugin_stack_diagram.icons import icon_svg
from uml_mcp_plugin_stack_diagram.layout import Box, Metrics, Placed
from uml_mcp_plugin_stack_diagram.render import Rules, Skin
from uml_mcp_plugin_stack_diagram.spec import Spec

STYLE_TONE = {
    "default": "gray",
    "security": "red",
    "frontend": "teal",
    "backend": "green",
    "bus": "orange",
    "workers": "teal",
    "database": "purple",
    "cloud": "yellow",
    "external": "gray",
}

_DARK_TONES = {
    "blue": "#38bdf8",
    "orange": "#fb923c",
    "green": "#34d399",
    "purple": "#a78bfa",
    "red": "#fb7185",
    "teal": "#2dd4bf",
    "yellow": "#facc15",
    "gray": "#94a3b8",
    "accent": "#22d3ee",
    "neutral": "#8a99b5",
}
_LIGHT_TONES = {
    "blue": "#0284c7",
    "orange": "#ea580c",
    "green": "#059669",
    "purple": "#7c3aed",
    "red": "#e11d48",
    "teal": "#0d9488",
    "yellow": "#ca8a04",
    "gray": "#64748b",
    "accent": "#0891b2",
    "neutral": "#64748b",
}

PRESETS: dict[str, Rules] = {
    "classic": (
        (".grid-line", "opacity:0"),
        (".dot", "opacity:1"),
        (".bracket", "display:none"),
        (".glow", "opacity:0"),
        (".gbox", "stroke-dasharray:6 5"),
    ),
    "blueprint": (
        (".grid-line", "opacity:1"),
        (".dot", "opacity:0"),
        (".bracket", "display:inline"),
        (".glow", "opacity:0"),
        (".gbox", "stroke-dasharray:12 3 2 3"),
        (".card", "stroke-width:1.7"),
    ),
    "flow": (
        (".grid-line", "opacity:0"),
        (".dot", "opacity:1"),
        (".bracket", "display:none"),
        (".glow", "opacity:.16"),
        (".gbox", "stroke-dasharray:3 4"),
        (".line", "stroke-width:2.2"),
    ),
}

NODE_W, NODE_H = 196, 72


class ArchifySkin(Skin):
    name: ClassVar[str] = "archify"
    metrics: ClassVar[Metrics] = Metrics(
        node=(NODE_W, NODE_H),
        shape=(0, 0, NODE_W, NODE_H),
        gap_main=76,
        gap_cross=24,
        pad=20,
        head=36,
    )
    group_styles: ClassVar[tuple[str, ...]] = tuple(STYLE_TONE)
    inherit_tone: ClassVar[bool] = True
    glow: ClassVar[bool] = True
    presets: ClassVar[dict[str, Rules]] = PRESETS
    palettes: ClassVar[dict[str, dict[str, str]]] = {
        "dark": {
            "bg": "#070b14",
            "grid": "#16213a",
            "ink": "#e8eefc",
            "muted": "#8a99b5",
            "panel": "#0d1424",
            "edge": "#1f2c47",
            **_DARK_TONES,
        },
        "light": {
            "bg": "#f6f8fc",
            "grid": "#d9e1ee",
            "ink": "#0f172a",
            "muted": "#52627a",
            "panel": "#ffffff",
            "edge": "#d5dcea",
            **_LIGHT_TONES,
        },
    }

    def group_tone(self, group):  # type: ignore[override]
        return group.tone or STYLE_TONE[group.style]

    # ---- canvas ------------------------------------------------------------------------
    def background(self, width: float, height: float) -> str:
        return (
            '<defs><pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse">'
            '<circle class="dot" cx="2" cy="2" r="1"/></pattern>'
            '<pattern id="lines" width="24" height="24" patternUnits="userSpaceOnUse">'
            '<path class="grid-line" d="M24 0H0V24"/></pattern></defs>'
            f'<rect class="bg" width="{width:.0f}" height="{height:.0f}"/>'
            f'<rect width="{width:.0f}" height="{height:.0f}" fill="url(#dots)"/>'
            f'<rect width="{width:.0f}" height="{height:.0f}" fill="url(#lines)"/>'
        )

    def frame(self, width: float, height: float) -> str:
        i, n = 14, 34
        corners = (
            f"M{i} {i + n}V{i}H{i + n}",
            f"M{width - i - n:.0f} {i}H{width - i:.0f}V{i + n}",
            f"M{i} {height - i - n:.0f}V{height - i:.0f}H{i + n}",
            f"M{width - i - n:.0f} {height - i:.0f}H{width - i:.0f}V{height - i - n:.0f}",
        )
        return "".join(f'<path class="bracket" d="{d}"/>' for d in corners)

    def header_height(self, spec: Spec) -> int:
        return 92 if spec.subtitle else 68

    def header(self, spec: Spec, width: float, theme: str) -> str:
        tagline = f"ARCHIFY · {spec.preset or 'classic'} · {theme}".upper()
        subtitle = (
            f'<text class="subtitle" x="40" y="72">{escape(spec.subtitle)}</text>'
            if spec.subtitle
            else ""
        )
        return (
            f'<text class="title" x="40" y="46">{escape(spec.title)}</text>{subtitle}'
            f'<text class="tagline l-accent" x="{width - 40:.0f}" y="40" text-anchor="end">{escape(tagline)}</text>'
        )

    # ---- legend ------------------------------------------------------------------------
    def legend_height(self, spec: Spec) -> int:
        return 62

    def legend(
        self, spec: Spec, width: float, y: float, counts: list[tuple[str, str, int]]
    ) -> str:
        out = [f'<text class="legend-title" x="40" y="{y + 20:.0f}">Legend</text>']
        x = 40.0
        for style, tone, count in counts:
            label = style.replace("-", " ").title()
            out.append(
                f'<rect class="t-{tone}" x="{x:.0f}" y="{y + 31:.0f}" width="22" height="12" rx="3"/>'
                f'<text class="legend-item" x="{x + 30:.0f}" y="{y + 41:.0f}">{escape(label)}</text>'
                f'<rect class="badge" x="{x + 36 + len(label) * 6.6:.0f}" y="{y + 30:.0f}" width="20" height="14" rx="3"/>'
                f'<text class="badge-n" x="{x + 46 + len(label) * 6.6:.0f}" y="{y + 41:.0f}" text-anchor="middle">{count}</text>'
            )
            x += 74 + len(label) * 6.6
        return "".join(out)

    # ---- groups and nodes --------------------------------------------------------------
    def group(self, box: Box, tone: str | None) -> str:
        x, y, w, h = box.rect
        g = box.group
        tone = tone or "gray"
        label_x = x + 16
        icon = ""
        if g.icon:
            icon = icon_svg(g.icon, (g.name,), x + 14, y + 11, 18, tone, g.name)
            label_x = x + 40
        return (
            f'<g class="gwrap" data-id="{escape(g.id, quote=True)}">'
            f'<rect class="gbox t-{tone}" x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="14"/>'
            f"{icon}"
            f'<text class="glabel l-{tone}" x="{label_x:.1f}" y="{y + 25:.1f}">{escape(g.name)}</text></g>'
        )

    def node(self, placed: Placed, tone: str | None) -> str:
        x, y, w, h = placed.rect
        n = placed.node
        tone = tone or "blue"
        icon = icon_svg(
            n.icon, (n.icon, n.name, n.role), x + 15, y + 15, 22, tone, n.name
        )
        text_x = x + 50
        lines = 1 + bool(n.role) + bool(n.tag)
        first = y + {1: 42, 2: 31, 3: 27}[lines]
        out = f'<text class="name" x="{text_x:.1f}" y="{first:.1f}">{escape(n.name)}</text>'
        if n.role:
            out += f'<text class="role" x="{text_x:.1f}" y="{first + 17:.1f}">{escape(n.role)}</text>'
        if n.tag:
            out += f'<text class="tag l-{tone}" x="{text_x:.1f}" y="{y + h - 9:.1f}">{escape(n.tag)}</text>'
        return (
            f'<g class="node" id="node-{escape(n.id, quote=True)}" data-id="{escape(n.id, quote=True)}">'
            f'<rect class="card-bg" x="{x:.1f}" y="{y:.1f}" width="{w}" height="{h}" rx="12"/>'
            f'<rect class="card t-{tone}" x="{x:.1f}" y="{y:.1f}" width="{w}" height="{h}" rx="12"/>'
            f"{icon}{out}</g>"
        )

    def css(self, pal: dict[str, str]) -> str:
        font = "system-ui,-apple-system,'Segoe UI',sans-serif"
        mono = "ui-monospace,'JetBrains Mono',Consolas,monospace"
        return (
            f".bg{{fill:{pal['bg']}}}.dot{{fill:{pal['grid']}}}"
            f".grid-line{{fill:none;stroke:{pal['grid']};stroke-width:1}}"
            f".bracket{{fill:none;stroke:{pal['accent']};stroke-width:1.6;display:none}}"
            ".gbox{fill-opacity:.05;stroke-width:1.3;stroke-dasharray:6 5}"
            f".glabel{{font:700 12px {mono};letter-spacing:.3px}}"
            f".card-bg{{fill:{pal['panel']}}}.card{{fill-opacity:.12;stroke-width:1.3}}"
            f".name{{fill:{pal['ink']};font:600 13px {font}}}"
            f".role{{fill:{pal['muted']};font:10.5px {mono}}}"
            f".tag{{font:700 8.5px {mono};letter-spacing:.8px;text-transform:uppercase}}"
            ".glow{stroke-width:7;stroke-linecap:round;opacity:0}"
            f".elabel{{font:11px {font};paint-order:stroke;stroke:{pal['bg']};stroke-width:5px;stroke-linejoin:round}}"
            f".mono-letter{{fill:#fff;font:700 11px {font}}}"
            f".title{{fill:{pal['ink']};font:700 26px {font}}}"
            f".subtitle{{fill:{pal['muted']};font:14px {mono}}}"
            f".tagline{{font:700 11px {mono};letter-spacing:2px}}"
            f".legend-title{{fill:{pal['ink']};font:700 12px {font}}}"
            f".legend-item{{fill:{pal['muted']};font:11px {mono}}}"
            f".badge{{fill:{pal['bg']};stroke:{pal['edge']}}}.badge-n{{fill:{pal['muted']};font:10px {mono}}}"
        )
