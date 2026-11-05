"""The "stack diagram" look: engineered paper, white icon tiles, mono edge labels."""

from __future__ import annotations

from html import escape
from typing import ClassVar

from .icons import icon_svg
from .layout import Box, Metrics, Placed
from .render import Skin

_TONES_DARK = {
    "blue": "#4996ff",
    "orange": "#f08a3c",
    "green": "#34d399",
    "purple": "#a78bfa",
    "red": "#f87171",
    "teal": "#2dd4bf",
    "yellow": "#fbbf24",
    "gray": "#969da6",
    "accent": "#4996ff",
    "neutral": "#969da6",
}
_TONES_LIGHT = {
    "blue": "#2670de",
    "orange": "#d9641a",
    "green": "#059669",
    "purple": "#7c3aed",
    "red": "#dc2626",
    "teal": "#0d9488",
    "yellow": "#b7791f",
    "gray": "#6b7380",
    "accent": "#2670de",
    "neutral": "#7d8591",
}

STYLE_TONE = {
    "vendor": "orange",
    "aws": "orange",
    "gcp": "blue",
    "azure": "blue",
    "dashed": "gray",
    "plain": "gray",
}


class StackSkin(Skin):
    name: ClassVar[str] = "stack"
    metrics: ClassVar[Metrics] = Metrics(node=(132, 104), shape=(36, 0, 60, 60))
    group_styles: ClassVar[tuple[str, ...]] = (
        "plain",
        "vendor",
        "aws",
        "gcp",
        "azure",
        "dashed",
    )
    palettes: ClassVar[dict[str, dict[str, str]]] = {
        "dark": {
            "bg": "#0e1216",
            "grid": "#1a2027",
            "ink": "#e6e9ee",
            "muted": "#929aa6",
            "panel": "#151a20",
            "edge": "#3a444f",
            "tile": "#ffffff",
            "tile-edge": "#d5dae1",
            "tile-ink": "#303744",
            **_TONES_DARK,
        },
        "light": {
            "bg": "#fafbfc",
            "grid": "#e7eaef",
            "ink": "#252b35",
            "muted": "#6b7380",
            "panel": "#f3f5f8",
            "edge": "#c4cbd4",
            "tile": "#ffffff",
            "tile-edge": "#d5dae1",
            "tile-ink": "#303744",
            **_TONES_LIGHT,
        },
    }

    def group_tone(self, group):  # type: ignore[override]
        return group.tone or STYLE_TONE[group.style]

    def background(self, width: float, height: float) -> str:
        return (
            '<defs><pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse">'
            '<path class="grid-line" d="M24 0H0V24"/></pattern></defs>'
            f'<rect class="bg" width="{width:.0f}" height="{height:.0f}"/>'
            f'<rect width="{width:.0f}" height="{height:.0f}" fill="url(#grid)"/>'
        )

    def group(self, box: Box, tone: str | None) -> str:
        x, y, w, h = box.rect
        g = box.group
        tone = tone or "gray"
        radius = 0 if g.style == "aws" else 14
        classes = ["box", f"t-{tone}"]
        if g.style == "plain":
            classes = ["box", "box-plain"]
        if g.style in ("aws", "gcp", "azure"):
            classes.append("box-outline")
        if g.style == "dashed":
            classes.append("box-dashed")
        label_x = x + 16
        icon = ""
        if g.icon:
            icon = icon_svg(g.icon, (g.name,), x + 14, y + 9, 18, tone)
            label_x = x + 40
        return (
            f'<g class="gwrap" data-id="{escape(g.id, quote=True)}">'
            f'<rect class="{" ".join(classes)}" x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{radius}"/>'
            f"{icon}"
            f'<text class="glabel" x="{label_x:.1f}" y="{y + 23:.1f}">{escape(g.name)}</text></g>'
        )

    def node(self, placed: Placed, tone: str | None) -> str:
        x, y, w, _h = placed.rect
        sx, sy, sw, sh = placed.shape
        n = placed.node
        icon = icon_svg(
            n.icon,
            (n.icon, n.name, n.role),
            sx + (sw - 30) / 2,
            sy + (sh - 30) / 2,
            30,
            tone,
            n.name,
        )
        if n.icon.startswith("data:"):
            icon = icon_svg(
                n.icon, (n.name,), sx + (sw - 36) / 2, sy + (sh - 36) / 2, 36, tone
            )
        cx = x + w / 2
        role = (
            f'<text class="role" x="{cx:.1f}" y="{y + 99:.1f}" text-anchor="middle">{escape(n.role)}</text>'
            if n.role
            else ""
        )
        return (
            f'<g class="node" id="node-{escape(n.id, quote=True)}" data-id="{escape(n.id, quote=True)}">'
            f'<rect class="tile" x="{sx:.1f}" y="{sy:.1f}" width="{sw}" height="{sh}" rx="14"/>{icon}'
            f'<text class="name" x="{cx:.1f}" y="{y + 82:.1f}" text-anchor="middle">{escape(n.name)}</text>{role}</g>'
        )

    def css(self, pal: dict[str, str]) -> str:
        font = "system-ui,-apple-system,'Segoe UI',sans-serif"
        mono = "ui-monospace,'JetBrains Mono',Consolas,monospace"
        return (
            f".bg{{fill:{pal['bg']}}}.grid-line{{fill:none;stroke:{pal['grid']};stroke-width:1}}"
            f".box{{stroke-width:1.5}}.box-plain{{fill:{pal['panel']};stroke:{pal['edge']}}}"
            ".box-outline{fill-opacity:.03}.box-dashed{stroke-dasharray:6 5}"
            f".glabel{{fill:{pal['ink']};font:600 13px {font}}}"
            f".tile{{fill:{pal['tile']};stroke:{pal['tile-edge']};stroke-width:1}}"
            f".s-tile{{stroke:{pal['tile-ink']}}}.ico.s-ink{{stroke:{pal['tile-ink']}}}"
            f".name{{fill:{pal['ink']};font:600 13px {font};paint-order:stroke;stroke:{pal['bg']};stroke-width:4px;stroke-linejoin:round}}"
            f".role{{fill:{pal['muted']};font:10px {mono};paint-order:stroke;stroke:{pal['bg']};stroke-width:4px;stroke-linejoin:round}}"
            f".elabel{{font:11px {mono};paint-order:stroke;stroke:{pal['bg']};stroke-width:5px;stroke-linejoin:round}}"
            f".mono-letter{{fill:#fff;font:700 11px {font}}}"
        )
