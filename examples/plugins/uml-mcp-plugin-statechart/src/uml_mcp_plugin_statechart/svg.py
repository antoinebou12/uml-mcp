"""The statechart as SVG: one drawing for the static image and the simulator page.

The static file carries a stylesheet with concrete colours (``resvg`` has no CSS
variables); the page uses ``var(--name)`` so the theme toggle restyles it in place.
"""

from __future__ import annotations

from html import escape

from .layout import LABEL_H, MARGIN, Box, Layout, text_width
from .model import Machine
from .router import rounded_path

PALETTES: dict[str, dict[str, str]] = {
    "light": {
        "bg": "#f6f8fb",
        "panel": "#ffffff",
        "ink": "#18212f",
        "muted": "#5a6577",
        "line": "#c8d0dc",
        "stroke": "#8391a6",
        "state": "#ffffff",
        "cont": "#eef2f8",
        "region": "#f6f8fc",
        "edge": "#5d6b80",
        "accent": "#2563eb",
        "activefill": "#dbe8ff",
        "can": "#0f9d76",
        "guard": "#b45309",
    },
    "dark": {
        "bg": "#0e131b",
        "panel": "#151c27",
        "ink": "#e5eaf2",
        "muted": "#94a1b5",
        "line": "#2a3443",
        "stroke": "#5d6b81",
        "state": "#1a2230",
        "cont": "#131a25",
        "region": "#111821",
        "edge": "#8a98ad",
        "accent": "#6aa5ff",
        "activefill": "#1d3456",
        "can": "#34d3a2",
        "guard": "#f0b25a",
    },
}

FONT = "system-ui,-apple-system,'Segoe UI',Roboto,sans-serif"


def css(pal: dict[str, str]) -> str:
    """Diagram rules. ``pal`` maps names to colours or to ``var(--name)``."""
    p = pal
    return (
        f".sc-bg{{fill:{p['bg']}}}"
        f"text{{font-family:{FONT}}}"
        f".sc-title{{font-size:18px;font-weight:700;fill:{p['ink']}}}"
        f".sc-sub{{font-size:12px;fill:{p['muted']}}}"
        f".sc-anyk{{font-size:10.5px;font-weight:700;letter-spacing:.08em;fill:{p['muted']}}}"
        f".sc-box{{fill:{p['state']};stroke:{p['stroke']};stroke-width:1.4}}"
        f".sc-compound>.sc-box,.sc-parallel>.sc-box{{fill:{p['cont']}}}"
        f".sc-region>.sc-box{{fill:{p['region']};fill-opacity:.55;stroke:none}}"
        f".sc-name{{font-size:13px;font-weight:650;fill:{p['ink']}}}"
        f".sc-rname{{font-size:11px;font-weight:700;letter-spacing:.04em;fill:{p['muted']}}}"
        f".sc-pname{{font-size:11.5px;fill:{p['muted']}}}"
        f".sc-tag{{font-size:10px;font-weight:700;letter-spacing:.08em;fill:{p['muted']}}}"
        f".sc-act{{font-size:11.5px;fill:{p['muted']}}}"
        f".sc-rule{{stroke:{p['line']};stroke-width:1}}"
        f".sc-sep{{stroke:{p['stroke']};stroke-width:1.2;stroke-dasharray:6 5}}"
        f".sc-line{{fill:none;stroke:{p['edge']};stroke-width:1.5}}"
        f".sc-headfill{{fill:{p['edge']}}}"
        f".sc-dot,.sc-core{{fill:{p['ink']}}}"
        f".sc-ring{{fill:{p['state']};stroke:{p['ink']};stroke-width:1.6}}"
        f".sc-h{{font-size:12px;font-weight:700;fill:{p['ink']}}}"
        f".sc-lbg{{fill:{p['panel']};stroke:{p['line']};stroke-width:1}}"
        f".sc-ltext{{font-size:11.5px;font-weight:600;fill:{p['ink']}}}"
        f".sc-guard{{fill:{p['guard']};font-weight:500}}"
        f".sc-acts{{fill:{p['muted']};font-weight:400}}"
    )


def _n(value: float) -> str:
    text = f"{value:.1f}"
    return text.removesuffix(".0")


def _label_text(label: str, x: float, y: float, anchor: str = "middle") -> str:
    """``EVENT [guard] / actions`` with the guard and actions in their own colours."""
    event, guard, actions = label, "", ""
    if " / " in event:
        event, actions = event.split(" / ", 1)
        actions = " / " + actions
    if " [" in event and event.endswith("]"):
        event, guard = event.split(" [", 1)
        guard = " [" + guard
    parts = escape(event)
    if guard:
        parts += f'<tspan class="sc-guard">{escape(guard)}</tspan>'
    if actions:
        parts += f'<tspan class="sc-acts">{escape(actions)}</tspan>'
    return f'<text class="sc-ltext" x="{_n(x)}" y="{_n(y + 4)}" text-anchor="{anchor}">{parts}</text>'


def _state(box: Box, machine: Machine) -> str:
    st = machine.states.get(box.id)
    attrs = (
        f'data-id="{escape(box.id)}" data-type="{escape(st.type if st else box.kind)}"'
    )
    x, y, w, h = box.x, box.y, box.w, box.h
    sx, sy, sw, sh = box.shape
    name = escape(box.label)
    if box.kind == "initial":
        cx, cy = sx + sw / 2, sy + sh / 2
        return f'<circle class="sc-dot" cx="{_n(cx)}" cy="{_n(cy)}" r="6"/>'
    if box.kind == "final":
        cx, cy, r = sx + sw / 2, sy + sh / 2, sw / 2
        return (
            f'<g class="sc-state sc-final" {attrs} tabindex="-1">'
            f'<circle class="sc-ring sc-box" cx="{_n(cx)}" cy="{_n(cy)}" r="{_n(r)}"/>'
            f'<circle class="sc-core" cx="{_n(cx)}" cy="{_n(cy)}" r="{_n(r - 6)}"/>'
            f'<text class="sc-pname" x="{_n(cx)}" y="{_n(sy + sh + 13)}" text-anchor="middle">{name}</text></g>'
        )
    if box.kind == "history":
        cx, cy, r = sx + sw / 2, sy + sh / 2, sw / 2
        mark = "H*" if st and st.history == "deep" else "H"
        return (
            f'<g class="sc-state sc-history" {attrs} tabindex="-1">'
            f'<circle class="sc-box" cx="{_n(cx)}" cy="{_n(cy)}" r="{_n(r)}"/>'
            f'<text class="sc-h" x="{_n(cx)}" y="{_n(cy + 4.5)}" text-anchor="middle">{mark}</text>'
            f'<text class="sc-pname" x="{_n(cx)}" y="{_n(sy + sh + 13)}" text-anchor="middle">{name}</text></g>'
        )
    if box.kind == "atomic":
        out = [
            (
                f'<g class="sc-state sc-atomic" {attrs} tabindex="-1">'
                f'<rect class="sc-box" x="{_n(x)}" y="{_n(y)}" width="{_n(w)}" height="{_n(h)}" rx="10"/>'
                f'<text class="sc-name" x="{_n(x + w / 2)}" y="{_n(y + 24)}" text-anchor="middle">{name}</text>'
            )
        ]
        if box.lines:
            out.append(
                f'<line class="sc-rule" x1="{_n(x + 8)}" y1="{_n(y + 36)}" x2="{_n(x + w - 8)}" y2="{_n(y + 36)}"/>'
            )
            for i, line in enumerate(box.lines):
                out.append(
                    f'<text class="sc-act" x="{_n(x + 12)}" y="{_n(y + 51 + i * 15)}">{escape(line)}</text>'
                )
        out.append("</g>")
        return "".join(out)
    if box.kind == "region":
        return (
            f'<g class="sc-state sc-region" {attrs} tabindex="-1">'
            f'<rect class="sc-box" x="{_n(x + 6)}" y="{_n(y + 4)}" width="{_n(w - 12)}" height="{_n(h - 8)}" rx="8"/>'
            f'<text class="sc-rname" x="{_n(x + 14)}" y="{_n(y + 17)}">{name}</text></g>'
        )
    # compound and parallel containers
    tag = "PARALLEL" if box.kind == "parallel" else ""
    out = [
        (
            f'<g class="sc-state sc-{box.kind}" {attrs} tabindex="-1">'
            f'<rect class="sc-box" x="{_n(x)}" y="{_n(y)}" width="{_n(w)}" height="{_n(h)}" rx="14"/>'
            f'<text class="sc-name" x="{_n(x + 14)}" y="{_n(y + 20)}">{name}</text>'
        )
    ]
    if tag:
        tx = x + 14 + text_width(box.label, 13, True) + 10
        out.append(f'<text class="sc-tag" x="{_n(tx)}" y="{_n(y + 20)}">‖ {tag}</text>')
    for i, line in enumerate(box.lines):
        out.append(
            f'<text class="sc-act" x="{_n(x + 14)}" y="{_n(y + 36 + i * 15)}">{escape(line)}</text>'
        )
    out.append("</g>")
    return "".join(out)


def drawing(machine: Machine, lay: Layout, *, theme: str, style: str = "") -> str:
    """The ``<svg>`` element. ``style`` is embedded when given (the static file)."""
    vx, vy, vw, vh = lay.x, lay.y, lay.width, lay.height
    out = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" class="sc-svg {theme}" '
            f'viewBox="{_n(vx)} {_n(vy)} {_n(vw)} {_n(vh)}" width="{_n(vw)}" height="{_n(vh)}" '
            f'role="img" aria-label="{escape(machine.title)} state machine">'
        )
    ]
    if style:
        out.append(f"<style>{style}</style>")
    out.append(
        "<defs>"
        '<marker id="sc-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" '
        'orient="auto-start-reverse"><path class="sc-headfill" d="M0,1 L10,5 L0,9 z"/></marker>'
        "</defs>"
    )
    out.append(
        f'<rect class="sc-bg" x="{_n(vx)}" y="{_n(vy)}" width="{_n(vw)}" height="{_n(vh)}"/>'
    )
    out.append(
        f'<g class="sc-heading"><text class="sc-title" x="{MARGIN}" y="{_n(lay.title_y)}">'
        f"{escape(machine.title)}</text>"
    )
    if machine.description:
        out.append(
            f'<text class="sc-sub" x="{MARGIN}" y="{_n(lay.title_y + 18)}">{escape(machine.description)}</text>'
        )
    out.append("</g>")
    if lay.any_items:
        y = lay.any_y + 8
        out.append(
            f'<text class="sc-anyk" x="{MARGIN}" y="{_n(y + 4)}">ANY STATE</text>'
        )
        for tid, text, x in lay.any_items:
            w = text_width(text, 11.5) + 14
            out.append(
                f'<g class="sc-label sc-any" data-tid="{tid}">'
                f'<rect class="sc-lbg" x="{_n(x - 7)}" y="{_n(y - LABEL_H / 2)}" width="{_n(w)}" height="{LABEL_H}" rx="9"/>'
                + _label_text(text, x, y, "start")
                + "</g>"
            )
    containers = [b for b in lay.boxes if b.kind in ("compound", "parallel", "region")]
    containers.sort(key=lambda b: b.depth)
    for box in containers:
        out.append(_state(box, machine))
    for x1, y1, x2, y2 in lay.seps:
        out.append(
            f'<line class="sc-sep" x1="{_n(x1)}" y1="{_n(y1)}" x2="{_n(x2)}" y2="{_n(y2)}"/>'
        )
    out.append('<g class="sc-edges">')
    for e in lay.edges:
        d = rounded_path(e.points, 6)
        if e.tid is None:
            out.append(
                f'<g class="sc-init"><path class="sc-line" d="{d}" marker-end="url(#sc-arrow)"/></g>'
            )
            continue
        tr = next(t for t in machine.transitions if t.id == e.tid)
        out.append(
            f'<g class="sc-tr" data-tid="{e.tid}" data-from="{escape(e.source)}" '
            f'data-to="{escape(e.target)}" data-event="{escape(tr.event)}">'
            f'<path class="sc-line" d="{d}" marker-end="url(#sc-arrow)"/></g>'
        )
    out.append("</g>")
    for box in lay.boxes:
        if box.kind in ("atomic", "final", "history", "initial"):
            out.append(_state(box, machine))
    out.append('<g class="sc-labels">')
    for e in lay.edges:
        if not e.label:
            continue
        out.append(
            f'<g class="sc-label" data-tid="{e.tid}">'
            f'<rect class="sc-lbg" x="{_n(e.lx - e.lw / 2)}" y="{_n(e.ly - LABEL_H / 2)}" '
            f'width="{_n(e.lw)}" height="{LABEL_H}" rx="9"/>'
            + _label_text(e.label, e.lx, e.ly)
            + "</g>"
        )
    out.append("</g></svg>")
    return "".join(out)


def static_css(theme: str) -> str:
    return css(PALETTES[theme])


def render_svg(machine: Machine, lay: Layout, theme: str) -> str:
    """A standalone SVG; ``auto`` is drawn dark, like the other plugins' static images."""
    resolved = "dark" if theme in ("auto", "dark") else "light"
    return drawing(machine, lay, theme=resolved, style=static_css(resolved))
