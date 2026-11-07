"""Colours, kind glyphs and the stylesheets of the trace pictures.

The static SVG carries one concrete stylesheet (simple class selectors and literal
colours, so resvg paints it the same as a browser). The page carries both themes under
``:root[data-theme=...]`` and swaps them with one attribute.
"""

from __future__ import annotations

KIND_COLORS: dict[str, str] = {
    "user": "#64748b",
    "llm": "#7c3aed",
    "tool": "#0891b2",
    "retrieval": "#059669",
    "subagent": "#2563eb",
    "guardrail": "#d97706",
    "memory": "#db2777",
    "reply": "#475569",
    "error": "#dc2626",
}

KIND_LABELS: dict[str, str] = {
    "user": "User",
    "llm": "LLM call",
    "tool": "Tool call",
    "retrieval": "Retrieval",
    "subagent": "Sub-agent",
    "guardrail": "Guardrail",
    "memory": "Memory",
    "reply": "Reply",
    "error": "Error",
}

ERROR = "#dc2626"
RETRY = "#d97706"

PALETTE: dict[str, dict[str, str]] = {
    "light": {
        "bg": "#ffffff",
        "panel": "#f6f8fb",
        "ink": "#0f172a",
        "muted": "#64748b",
        "grid": "#e5e9f0",
        "stripe": "#f8fafc",
        "edge": "#d5dbe5",
        "track": "#eef2f7",
        "accent": "#2563eb",
    },
    "dark": {
        "bg": "#0b1220",
        "panel": "#111a2c",
        "ink": "#e2e8f0",
        "muted": "#94a3b8",
        "grid": "#1d2738",
        "stripe": "#0e1626",
        "edge": "#26324a",
        "track": "#152034",
        "accent": "#60a5fa",
    },
}

#: 16x16 glyphs, drawn in white over the kind colour.
GLYPHS: dict[str, str] = {
    "user": '<circle cx="8" cy="5.6" r="2.6"/><path d="M3.2 13.6c0-2.8 2.1-4.4 4.8-4.4s4.8 1.6 4.8 4.4"/>',
    "llm": '<path class="gfill" d="M8 1.8l1.5 4.7 4.7 1.5-4.7 1.5L8 14.2l-1.5-4.7L1.8 8l4.7-1.5z"/>',
    "tool": '<path d="M10.6 2.4a3.2 3.2 0 0 0-4 4L2.4 10.6l3 3 4.2-4.2a3.2 3.2 0 0 0 4-4l-1.9 1.9-1.8-.4-.4-1.8z"/>',
    "retrieval": '<circle cx="7" cy="7" r="4.2"/><path d="M10.2 10.2l3.8 3.8"/>',
    "subagent": '<rect x="3" y="5" width="10" height="8" rx="2.2"/><path d="M8 2.2V5"/><circle class="gfill" cx="6.2" cy="9" r=".9"/><circle class="gfill" cx="9.8" cy="9" r=".9"/>',
    "guardrail": '<path d="M8 1.8l5.2 2v4.1c0 3.1-2.2 5.3-5.2 6.3-3-1-5.2-3.2-5.2-6.3V3.8z"/>',
    "memory": '<ellipse cx="8" cy="4" rx="5" ry="1.9"/><path d="M3 4v8c0 1.05 2.2 1.9 5 1.9s5-.85 5-1.9V4M3 8c0 1.05 2.2 1.9 5 1.9s5-.85 5-1.9"/>',
    "reply": '<path d="M2.6 3h10.8v7.2H7.4L4.4 13v-2.8H2.6z"/>',
    "error": '<circle cx="8" cy="8" r="5.8"/><path d="M8 4.8v3.8M8 10.9v.3"/>',
}


def glyph(kind: str, x: float, y: float, size: float = 18) -> str:
    """A rounded tile in the kind colour with its white glyph, top-left at (x, y)."""
    scale = (size - 4) / 16
    return (
        f'<g class="glyph" transform="translate({x:g},{y:g})">'
        f'<rect class="k-{kind}" width="{size:g}" height="{size:g}" rx="{size * 0.28:.1f}"/>'
        f'<g class="gl" transform="translate(2,2) scale({scale:.3f})">{GLYPHS[kind]}</g></g>'
    )


def marker(status: str, x: float, y: float) -> str:
    """An error cross or a retry arrow in a small disc centred at (x, y)."""
    if status == "error":
        return (
            f'<g class="mark mark-error" transform="translate({x:g},{y:g})">'
            '<circle class="m-error" r="6.5"/>'
            '<path class="m-stroke" d="M-2.6-2.6l5.2 5.2M2.6-2.6l-5.2 5.2"/></g>'
        )
    return (
        f'<g class="mark mark-retry" transform="translate({x:g},{y:g})">'
        '<circle class="m-retry" r="6.5"/>'
        '<path class="m-stroke" d="M2.9-1.2A3.1 3.1 0 1 0 3 1.4"/>'
        '<path class="m-stroke" d="M3.4-3.4v2.4H1"/></g>'
    )


def _rules(p: dict[str, str]) -> list[str]:
    rules = [
        f".bg{{fill:{p['bg']}}}",
        f".panel{{fill:{p['panel']};stroke:{p['edge']}}}",
        f".track{{fill:{p['track']}}}",
        f".gridline{{stroke:{p['grid']};stroke-width:1}}",
        f".axisline{{stroke:{p['edge']};stroke-width:1}}",
        f".t-title{{fill:{p['ink']};font-size:17px;font-weight:700}}",
        f".t-sub{{fill:{p['muted']};font-size:12px}}",
        f".t-k{{fill:{p['muted']};font-size:10.5px;letter-spacing:.06em}}",
        f".t-v{{fill:{p['ink']};font-size:15px;font-weight:700}}",
        f".t-tick{{fill:{p['muted']};font-size:10.5px}}",
        f".t-name{{fill:{p['ink']};font-size:12.5px}}",
        f".t-meta{{fill:{p['muted']};font-size:11px}}",
        f".t-dur{{fill:{p['ink']};font-size:11px;font-weight:600}}",
        f".t-lane{{fill:{p['ink']};font-size:12px;font-weight:600}}",
        f".t-msg{{fill:{p['ink']};font-size:11.5px}}",
        f".t-err{{fill:{ERROR};font-size:11px;font-weight:600}}",
        f".t-retry{{fill:{RETRY};font-size:11px;font-weight:600}}",
        f".c-err{{fill:{ERROR}}}",
        f".c-retry{{fill:{RETRY}}}",
        f".lifeline{{stroke:{p['edge']};stroke-width:1.2;stroke-dasharray:4 4}}",
        f".lanebox{{fill:{p['panel']};stroke:{p['edge']}}}",
        f".arrow{{stroke:{p['muted']};stroke-width:1.5;fill:none}}",
        ".ret{stroke-dasharray:5 4;opacity:.8}",
        f".ahead{{fill:{p['muted']}}}",
        f".a-error{{stroke:{ERROR}}}",
        f".h-error{{fill:{ERROR}}}",
        f".a-retry{{stroke:{RETRY}}}",
        f".h-retry{{fill:{RETRY}}}",
        f".notebox{{fill:{p['panel']};stroke:{ERROR}}}",
        f".sep{{stroke:{p['edge']};stroke-width:1}}",
        ".bar{stroke-width:0}",
        f".rowbg{{fill:{p['bg']};fill-opacity:0}}",
        f".stripe{{fill:{p['stripe']};fill-opacity:1}}",
        f".b-error{{stroke:{ERROR};stroke-width:2}}",
        f".b-retry{{stroke:{RETRY};stroke-width:2;stroke-dasharray:4 3}}",
        f".m-error{{fill:{ERROR}}}",
        f".m-retry{{fill:{RETRY}}}",
        ".m-stroke{stroke:#ffffff;stroke-width:1.6;fill:none;stroke-linecap:round}",
        ".gl{stroke:#ffffff;stroke-width:1.5;fill:none;stroke-linecap:round;stroke-linejoin:round}",
        ".gfill{fill:#ffffff;stroke:none}",
        f".caret{{fill:{p['muted']}}}",
        "text{font-family:system-ui,-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif}",
    ]
    rules += [f".k-{kind}{{fill:{color}}}" for kind, color in KIND_COLORS.items()]
    rules += [f".s-{kind}{{stroke:{color}}}" for kind, color in KIND_COLORS.items()]
    return rules


def static_css(theme: str) -> str:
    """The stylesheet embedded in a standalone SVG (one theme, literal colours)."""
    return "".join(_rules(PALETTE[theme]))


def page_css() -> str:
    """Both themes for the page, scoped by ``:root[data-theme]``."""
    out: list[str] = []
    for theme, p in PALETTE.items():
        scope = f':root[data-theme="{theme}"]'
        out.append(
            f"{scope}{{--bg:{p['bg']};--panel:{p['panel']};--ink:{p['ink']};--muted:{p['muted']};"
            f"--edge:{p['edge']};--grid:{p['grid']};--accent:{p['accent']};--track:{p['track']}}}"
        )
        out += [f"{scope} {rule}" for rule in _rules(p)]
    return "".join(out)
