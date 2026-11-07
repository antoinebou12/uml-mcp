"""Static SVG: time axis, swimlanes, bars, phases, milestones, releases, dependencies, legend.

Colours are written as presentation attributes (no CSS variables), so resvg turns the SVG
into the same PNG. ``assets/timeline.js`` draws the interactive page with the same layout
rules; keep the two in step (``tests/test_plugin_timeline.py`` compares their geometry).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from html import escape

from .model import Item, Timeline, from_day, iso, to_day

FONT = "system-ui, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
ROW = 30
BAR = 18
GUTTER = 168
AXIS = 44
HEADER = 62
LEGEND = 46
CHAR = 6.6  # average width of a 12px label character
#: pixels per day for each named scale
LEVELS = {"quarter": 1.0, "month": 3.4, "week": 12.0, "day": 36.0}
MIN_PPD, MAX_PPD = 0.25, 60.0
MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)
FULL_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

PALETTES: dict[str, dict[str, str]] = {
    "light": {
        "bg": "#ffffff",
        "ink": "#0f172a",
        "muted": "#64748b",
        "grid": "#e2e8f0",
        "major": "#cbd5e1",
        "band": "#f8fafc",
        "band2": "#f1f5f9",
        "today": "#e11d48",
        "dep": "#94a3b8",
        "accent": "#4f46e5",
        "planned": "#64748b",
        "active": "#2563eb",
        "done": "#16a34a",
        "blocked": "#dc2626",
        "at-risk": "#d97706",
    },
    "dark": {
        "bg": "#0b1020",
        "ink": "#e2e8f0",
        "muted": "#94a3b8",
        "grid": "#1e293b",
        "major": "#334155",
        "band": "#0f172a",
        "band2": "#131c31",
        "today": "#fb7185",
        "dep": "#64748b",
        "accent": "#a5b4fc",
        "planned": "#94a3b8",
        "active": "#60a5fa",
        "done": "#4ade80",
        "blocked": "#f87171",
        "at-risk": "#fbbf24",
    },
}
STATUS_LABELS = {
    "planned": "Planned",
    "active": "Active",
    "done": "Done",
    "blocked": "Blocked",
    "at-risk": "At risk",
}


def tick_unit(ppd: float) -> str:
    if ppd >= 22:
        return "day"
    if ppd >= 6.5:
        return "week"
    if ppd >= 1.15:
        return "month"
    if ppd >= 0.33:
        return "quarter"
    return "year"


MAJOR = {"day": "month", "week": "month", "month": "year", "quarter": "year"}


def floor_unit(day: int, unit: str) -> int:
    d = from_day(day)
    if unit == "day":
        return day
    if unit == "week":
        return day - d.weekday()
    if unit == "month":
        return to_day(date(d.year, d.month, 1))
    if unit == "quarter":
        return to_day(date(d.year, (d.month - 1) // 3 * 3 + 1, 1))
    return to_day(date(d.year, 1, 1))


def next_unit(day: int, unit: str) -> int:
    if unit == "day":
        return day + 1
    if unit == "week":
        return day + 7
    d = from_day(day)
    months = {"month": 1, "quarter": 3}.get(unit, 12)
    total = d.year * 12 + d.month - 1 + months
    return to_day(date(total // 12, total % 12 + 1, 1))


def tick_label(day: int, unit: str) -> str:
    d = from_day(day)
    if unit == "day":
        return str(d.day)
    if unit == "week":
        return f"{MONTHS[d.month - 1]} {d.day}"
    if unit == "month":
        return MONTHS[d.month - 1]
    if unit == "quarter":
        return f"Q{(d.month - 1) // 3 + 1}"
    return str(d.year)


def major_label(day: int, unit: str) -> str:
    d = from_day(day)
    return f"{FULL_MONTHS[d.month - 1]} {d.year}" if unit == "month" else str(d.year)


def text_width(text: str, size: float = 12) -> float:
    return len(text) * CHAR * size / 12


def fmt_date(day: int) -> str:
    d = from_day(day)
    return f"{MONTHS[d.month - 1]} {d.day}, {d.year}"


@dataclass
class Placed:
    item: Item
    x0: float
    x1: float
    y: float  # centre line of its row
    inside: bool


@dataclass
class LaneBox:
    id: str
    y: float
    height: float


def layout(
    tl: Timeline, items: list[Item], x_of, lane_ids: list[str], top: float
) -> tuple[list[LaneBox], dict[str, Placed], list[tuple[Item, LaneBox]]]:
    """Pack each lane's items into rows; phases span the whole lane behind them."""
    boxes: list[LaneBox] = []
    placed: dict[str, Placed] = {}
    phases: list[tuple[Item, LaneBox]] = []
    y = top
    for lane_id in lane_ids:
        own = [i for i in items if i.lane == lane_id]
        lane_phases = [i for i in own if i.kind == "phase"]
        rest = sorted(
            (i for i in own if i.kind != "phase"), key=lambda i: (i.start, -i.end)
        )
        pad = 20 if lane_phases else 8
        rows: list[float] = []
        slots: list[tuple[Item, float, float, bool, int]] = []
        for item in rest:
            width = text_width(item.name)
            if item.point:
                cx = x_of(item.start + 0.5)
                x0, x1, inside = cx - 8, cx + 8, False
                extent = cx + 12 + width
            else:
                x0, x1 = x_of(item.start), x_of(item.end + 1)
                inside = width + 16 <= x1 - x0
                extent = x1 if inside else x1 + 6 + width
            row = next((r for r, end in enumerate(rows) if end <= x0 - 4), len(rows))
            if row == len(rows):
                rows.append(0.0)
            rows[row] = extent + 10
            slots.append((item, x0, x1, inside, row))
        height = pad + max(1, len(rows)) * ROW + 8
        box = LaneBox(lane_id, y, height)
        boxes.append(box)
        for item, x0, x1, inside, row in slots:
            placed[item.id] = Placed(
                item, x0, x1, y + pad + row * ROW + ROW / 2, inside
            )
        phases += [(p, box) for p in lane_phases]
        y += height
    return boxes, placed, phases


def extent(p: Placed) -> float:
    """Where an item's drawing ends on the right, label included."""
    w = text_width(p.item.name)
    if p.item.point:
        return (p.x0 + p.x1) / 2 + 14 + w
    return p.x1 if p.inside else p.x1 + 6 + w


def dep_path(a: Placed, b: Placed) -> str:
    """An elbow from the end of ``a`` to the start of ``b``; loops round when b starts earlier."""
    ax = a.x1 - (1 if a.item.point else 0)
    bx = b.x0
    ay, by = a.y, b.y
    if bx - ax >= 14:
        mx = max(ax + 6, bx - 10)
        return f"M{ax:.1f} {ay:.1f}H{mx:.1f}V{by:.1f}H{bx - 1:.1f}"
    mid = ay + (ROW / 2 if by >= ay else -ROW / 2)
    return (
        f"M{ax:.1f} {ay:.1f}H{ax + 8:.1f}V{mid:.1f}H{bx - 10:.1f}V{by:.1f}H{bx - 1:.1f}"
    )


def _e(text: str) -> str:
    return escape(text, quote=True)


def resolve_theme(tl: Timeline) -> str:
    return "light" if tl.theme == "light" else "dark"


def render_svg(tl: Timeline, *, today: int | None = None) -> str:
    theme = resolve_theme(tl)
    pal = PALETTES[theme]
    lanes = {lane.id: lane for lane in tl.lanes}
    first, last = tl.span
    ppd = (
        LEVELS[tl.scale]
        if tl.scale
        else min(MAX_PPD, max(MIN_PPD, 1000 / (last - first)))
    )
    unit = tick_unit(ppd)
    t0 = floor_unit(first, unit)
    t1 = (
        last
        if floor_unit(last, unit) == last
        else next_unit(floor_unit(last, unit), unit)
    )
    width = max(780.0, GUTTER + (t1 - t0) * ppd + 24)

    def x_of(day: float) -> float:
        return GUTTER + (day - t0) * ppd

    top = HEADER + AXIS
    boxes, placed, phases = layout(
        tl, list(tl.items), x_of, [lane.id for lane in tl.lanes], top
    )
    width = max(width, max((extent(p) for p in placed.values()), default=0) + 16)
    bottom = boxes[-1].y + boxes[-1].height
    height = bottom + LEGEND
    out: list[str] = []
    add = out.append
    add(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" '
        f'width="{width:.0f}" height="{height:.0f}" role="img" aria-label="{_e(tl.title)}" '
        f'font-family="{_e(FONT)}" class="tl {theme}">'
    )
    add(f"<title>{_e(tl.title)}</title>")
    add(
        "<defs>"
        f'<marker id="tl-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="8" markerHeight="8" markerUnits="userSpaceOnUse" orient="auto">'
        f'<path d="M0 0L8 4L0 8z" fill="{pal["dep"]}"/></marker>'
        "</defs>"
    )
    add(
        f'<rect class="bg" width="{width:.0f}" height="{height:.0f}" fill="{pal["bg"]}"/>'
    )
    add(
        f'<text x="20" y="30" font-size="18" font-weight="700" fill="{pal["ink"]}">{_e(tl.title)}</text>'
    )
    meta = f"{fmt_date(first)} – {fmt_date(last - 1)} · {len(tl.items)} items"
    add(
        f'<text x="20" y="50" font-size="12" fill="{pal["muted"]}">{_e(tl.subtitle or meta)}</text>'
    )

    # lane bands
    for n, box in enumerate(boxes):
        fill = pal["band"] if n % 2 == 0 else pal["band2"]
        add(
            f'<rect x="0" y="{box.y:.1f}" width="{width:.0f}" height="{box.height:.1f}" fill="{fill}"/>'
        )

    # grid and axis
    add(f'<g class="axis" font-size="11" fill="{pal["muted"]}">')
    major = MAJOR.get(unit)
    day = t0
    while day <= t1:
        x = x_of(day)
        is_major = major is not None and floor_unit(day, major) == day
        add(
            f'<line x1="{x:.1f}" y1="{HEADER + 22 if not is_major else HEADER}" x2="{x:.1f}" '
            f'y2="{bottom:.1f}" stroke="{pal["major"] if is_major else pal["grid"]}" stroke-width="1"/>'
        )
        if day < t1:
            add(
                f'<text x="{x + 4:.1f}" y="{HEADER + 37}">{_e(tick_label(day, unit))}</text>'
            )
        day = next_unit(day, unit)
    if major:
        marks = []
        day = floor_unit(t0, major)
        while day < t1:
            marks.append(day)
            day = next_unit(day, major)
        for n, day in enumerate(marks):
            x = max(x_of(day), GUTTER)
            label = major_label(day, major)
            nxt = x_of(marks[n + 1]) if n + 1 < len(marks) else width
            if nxt - x >= text_width(label) + 12:
                add(
                    f'<text x="{x + 4:.1f}" y="{HEADER + 16}" font-size="12" font-weight="600" '
                    f'fill="{pal["ink"]}">{_e(label)}</text>'
                )
    add("</g>")
    add(
        f'<line x1="0" y1="{top:.1f}" x2="{width:.0f}" y2="{top:.1f}" stroke="{pal["major"]}"/>'
    )

    # phases: translucent bands behind the lane's items
    for item, box in phases:
        color = lanes[item.lane].color
        x0, x1 = x_of(item.start), x_of(item.end + 1)
        add(
            f'<g class="item phase" data-id="{_e(item.id)}">'
            f'<rect x="{x0:.1f}" y="{box.y + 3:.1f}" width="{x1 - x0:.1f}" height="{box.height - 6:.1f}" '
            f'rx="6" fill="{color}" fill-opacity="0.12" stroke="{color}" stroke-opacity="0.55" '
            f'stroke-dasharray="4 3"/>'
            f'<text x="{x0 + 8:.1f}" y="{box.y + 15:.1f}" font-size="10" font-weight="700" '
            f'letter-spacing="0.8" fill="{color}">{_e(item.name.upper())}</text></g>'
        )

    # dependencies
    add(f'<g class="deps" fill="none" stroke="{pal["dep"]}" stroke-width="1.3">')
    for item in tl.items:
        for dep in item.depends_on:
            if dep in placed and item.id in placed:
                add(
                    f'<path d="{dep_path(placed[dep], placed[item.id])}" '
                    f'stroke-linejoin="round" marker-end="url(#tl-arrow)"/>'
                )
    add("</g>")

    # items
    for p in placed.values():
        add(_item_svg(p, pal, lanes[p.item.lane].color))

    # lane labels sit on an opaque gutter so bars never run under them
    for n, box in enumerate(boxes):
        lane = lanes[box.id]
        add(
            f'<rect x="0" y="{box.y:.1f}" width="{GUTTER - 8}" height="{box.height:.1f}" '
            f'fill="{pal["band"] if n % 2 == 0 else pal["band2"]}"/>'
            f'<rect x="16" y="{box.y + 10:.1f}" width="4" height="{box.height - 20:.1f}" rx="2" fill="{lane.color}"/>'
            f'<text x="28" y="{box.y + 24:.1f}" font-size="13" font-weight="600" fill="{pal["ink"]}">{_e(_clip(lane.name, GUTTER - 44, 13))}</text>'
        )

    add(
        f'<line x1="{GUTTER - 8}" y1="{top:.1f}" x2="{GUTTER - 8}" y2="{bottom:.1f}" stroke="{pal["grid"]}"/>'
    )

    # today
    now = tl.today if tl.today is not None else today
    if now is not None and t0 <= now < t1:
        x = x_of(now + 0.5)
        add(
            f'<line x1="{x:.1f}" y1="{HEADER + 40}" x2="{x:.1f}" y2="{bottom:.1f}" '
            f'stroke="{pal["today"]}" stroke-width="1.5" stroke-dasharray="5 4"/>'
            f'<rect x="{x - 22:.1f}" y="{HEADER + 38:.1f}" width="44" height="14" rx="7" fill="{pal["today"]}"/>'
            f'<text x="{x:.1f}" y="{HEADER + 48.5:.1f}" font-size="9.5" font-weight="700" fill="#ffffff" '
            f'text-anchor="middle">TODAY</text>'
        )

    add(_legend(pal, bottom))
    add("</svg>")
    return "".join(out)


def _clip(text: str, room: float, size: float = 12) -> str:
    if text_width(text, size) <= room:
        return text
    keep = max(1, int(room / (CHAR * size / 12)) - 1)
    return text[:keep] + "…"


def _item_svg(p: Placed, pal: dict[str, str], lane_color: str) -> str:
    item = p.item
    color = pal[item.status]
    cls = f"item {item.kind} st-{item.status}"
    head = f'<g class="{cls}" data-id="{_e(item.id)}"><title>{_e(item.name)}</title>'
    if item.kind == "milestone":
        cx, cy = (p.x0 + p.x1) / 2, p.y
        shape = (
            f'<path d="M{cx:.1f} {cy - 8:.1f}L{cx + 8:.1f} {cy:.1f}L{cx:.1f} {cy + 8:.1f}L{cx - 8:.1f} {cy:.1f}Z" '
            f'fill="{color}" stroke="{pal["bg"]}" stroke-width="1.5"/>'
        )
        label = f'<text x="{cx + 12:.1f}" y="{cy + 4:.1f}" font-size="12" fill="{pal["ink"]}">{_e(item.name)}</text>'
        return head + shape + label + "</g>"
    if item.kind == "release":
        cx, cy = (p.x0 + p.x1) / 2, p.y
        shape = (
            f'<line x1="{cx:.1f}" y1="{cy - 10:.1f}" x2="{cx:.1f}" y2="{cy + 10:.1f}" stroke="{color}" stroke-width="2"/>'
            f'<path d="M{cx:.1f} {cy - 10:.1f}H{cx + 11:.1f}L{cx + 8:.1f} {cy - 5.5:.1f}L{cx + 11:.1f} {cy - 1:.1f}H{cx:.1f}Z" fill="{color}"/>'
            f'<circle cx="{cx:.1f}" cy="{cy + 10:.1f}" r="2.2" fill="{color}"/>'
        )
        label = f'<text x="{cx + 14:.1f}" y="{cy + 4:.1f}" font-size="12" font-weight="600" fill="{pal["ink"]}">{_e(item.name)}</text>'
        return head + shape + label + "</g>"
    w = max(2.0, p.x1 - p.x0)
    y = p.y - BAR / 2
    dash = ' stroke-dasharray="4 3"' if item.status == "blocked" else ""
    parts = [
        head,
        f'<rect x="{p.x0:.1f}" y="{y:.1f}" width="{w:.1f}" height="{BAR}" rx="5" fill="{color}" fill-opacity="0.16" stroke="{color}" stroke-width="1.4"{dash}/>',
    ]
    if item.progress > 0:
        pw = w * item.progress / 100
        parts.append(
            f'<rect x="{p.x0:.1f}" y="{y:.1f}" width="{pw:.1f}" height="{BAR}" rx="5" fill="{color}" fill-opacity="0.5"/>'
        )
    parts.append(
        f'<rect x="{p.x0 + 3:.1f}" y="{y + 4:.1f}" width="3" height="{BAR - 8}" rx="1.5" fill="{lane_color}"/>'
        if w > 14
        else ""
    )
    if p.inside:
        parts.append(
            f'<text x="{p.x0 + 10:.1f}" y="{p.y + 4:.1f}" font-size="12" font-weight="600" fill="{pal["ink"]}">{_e(item.name)}</text>'
        )
    else:
        parts.append(
            f'<text x="{p.x1 + 6:.1f}" y="{p.y + 4:.1f}" font-size="12" fill="{pal["ink"]}">{_e(item.name)}</text>'
        )
    parts.append("</g>")
    return "".join(parts)


def _legend(pal: dict[str, str], bottom: float) -> str:
    y = bottom + 26
    x = 20.0
    parts = [f'<g class="legend" font-size="11" fill="{pal["muted"]}">']
    for status, label in STATUS_LABELS.items():
        c = pal[status]
        dash = ' stroke-dasharray="3 2"' if status == "blocked" else ""
        parts.append(
            f'<rect x="{x:.1f}" y="{y - 9:.1f}" width="18" height="10" rx="3" fill="{c}" fill-opacity="0.35" stroke="{c}"{dash}/>'
            f'<text x="{x + 24:.1f}" y="{y:.1f}">{label}</text>'
        )
        x += 34 + text_width(label, 11)
    x += 10
    c = pal["muted"]
    parts.append(
        f'<rect x="{x:.1f}" y="{y - 10:.1f}" width="22" height="12" rx="3" fill="{c}" fill-opacity="0.15" stroke="{c}" stroke-dasharray="3 2"/>'
        f'<text x="{x + 28:.1f}" y="{y:.1f}">Phase</text>'
    )
    x += 74
    parts.append(
        f'<path d="M{x + 6:.1f} {y - 10:.1f}L{x + 12:.1f} {y - 4:.1f}L{x + 6:.1f} {y + 2:.1f}L{x:.1f} {y - 4:.1f}Z" fill="{c}"/>'
        f'<text x="{x + 18:.1f}" y="{y:.1f}">Milestone</text>'
    )
    x += 86
    parts.append(
        f'<line x1="{x + 1:.1f}" y1="{y - 11:.1f}" x2="{x + 1:.1f}" y2="{y + 3:.1f}" stroke="{c}" stroke-width="2"/>'
        f'<path d="M{x + 1:.1f} {y - 11:.1f}h9l-2.5 3.5l2.5 3.5h-9z" fill="{c}"/>'
        f'<text x="{x + 16:.1f}" y="{y:.1f}">Release</text>'
    )
    x += 76
    parts.append(
        f'<line x1="{x:.1f}" y1="{y - 4:.1f}" x2="{x + 22:.1f}" y2="{y - 4:.1f}" stroke="{pal["dep"]}" stroke-width="1.3" marker-end="url(#tl-arrow)"/>'
        f'<text x="{x + 30:.1f}" y="{y:.1f}">Depends on</text>'
    )
    x += 108
    parts.append(
        f'<line x1="{x + 6:.1f}" y1="{y - 12:.1f}" x2="{x + 6:.1f}" y2="{y + 4:.1f}" stroke="{pal["today"]}" stroke-width="1.5" stroke-dasharray="4 3"/>'
        f'<text x="{x + 14:.1f}" y="{y:.1f}">Today</text>'
    )
    parts.append("</g>")
    return "".join(parts)


__all__ = ["LEVELS", "PALETTES", "iso", "layout", "render_svg", "tick_unit"]
