"""The two pictures of a trace: a waterfall on a time axis and a sequence (flow) view.

Every row is a ``<g class="row">`` (or ``<g class="msg">``) translated to its place, so the
page can hide collapsed sub-agents and move the rows below up without redrawing. Text is
always escaped; nothing from the source is ever written as markup.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from html import escape

from .spec import Step, Trace
from .theme import KIND_LABELS, glyph, marker, static_css

PAD = 20
WIDTH = 1100
HEADER_H = 140  # title, subtitle and the summary panel
LABEL_X = PAD
LABEL_W = 270
TL_X = 300
TL_W = 470
META_X = TL_X + TL_W + 16
ROW = 30
AXIS_Y = HEADER_H + 14
ROW_TOP = AXIS_Y + 12
LEGEND_GAP = 18
LANE_W = 150
LANE_TOP = HEADER_H + 10
LANE_H = 40
MSG_TOP = LANE_TOP + LANE_H + 14
MSG = 46
CHAR = 0.56  # average glyph width / font size for the system sans


# --------------------------------------------------------------------------- formatting
def fmt_ms(ms: float) -> str:
    if ms < 1:
        return f"{ms:.2f} ms" if ms else "0 ms"
    if ms < 1000:
        return f"{ms:.0f} ms"
    if ms < 60_000:
        return f"{ms / 1000:.2f} s"
    minutes, seconds = divmod(ms / 1000, 60)
    return f"{int(minutes)}m {seconds:04.1f}s"


def fmt_tokens(n: int) -> str:
    if n < 1000:
        return str(n)
    if n < 10_000:
        return f"{n / 1000:.1f}k"
    if n < 1_000_000:
        return f"{n / 1000:.0f}k"
    return f"{n / 1_000_000:.1f}M"


def fmt_cost(usd: float | None) -> str:
    if usd is None:
        return "—"
    if usd == 0:
        return "$0"
    if usd < 0.01:
        return f"${usd:.4f}"
    if usd < 100:
        return f"${usd:.2f}"
    return f"${usd:,.0f}"


def fit(text: str, px: float, size: float = 12.5) -> str:
    """``text`` cut with an ellipsis so it fits ``px`` at ``size``."""
    room = max(1, int(px / (size * CHAR)))
    return text if len(text) <= room else text[: max(1, room - 1)].rstrip() + "…"


def tokens_label(step: Step) -> str:
    if not step.has_tokens:
        return ""
    text = f"{fmt_tokens(step.tokens_in)}→{fmt_tokens(step.tokens_out)} tok"
    if step.tokens_cached:
        text += f" · {fmt_tokens(step.tokens_cached)} cached"
    return text


def step_meta(step: Step) -> str:
    parts = [
        tokens_label(step),
        fmt_cost(step.cost_usd) if step.cost_usd is not None else "",
    ]
    return " · ".join(p for p in parts if p)


def nice_step(span: float, target: int = 6) -> float:
    if span <= 0:
        return 1.0
    raw = span / target
    base = 10 ** math.floor(math.log10(raw))
    for mult in (1, 2, 2.5, 5, 10):
        if raw <= mult * base:
            return mult * base
    return 10 * base


def _t(x: float, y: float, text: str, cls: str, anchor: str = "start") -> str:
    a = "" if anchor == "start" else f' text-anchor="{anchor}"'
    return f'<text class="{cls}" x="{x:.1f}" y="{y:.1f}"{a}>{escape(text)}</text>'


# --------------------------------------------------------------------------- shared header
def summary(trace: Trace, width: float) -> str:
    totals = trace.totals()
    sub = [trace.model] if trace.model else []
    sub.append(f"{totals['steps']} steps · {totals['llm_calls']} LLM calls")
    errors = f"{totals['errors']} · {totals['retries']}"
    cells = [
        ("TOTAL TIME", fmt_ms(totals["duration_ms"])),
        ("TOKENS IN", fmt_tokens(totals["tokens_in"])),
        ("TOKENS OUT", fmt_tokens(totals["tokens_out"])),
        ("CACHED", fmt_tokens(totals["tokens_cached"])),
        ("COST", fmt_cost(totals["cost_usd"])),
        ("TOOL CALLS", str(totals["tool_calls"])),
        ("ERRORS · RETRIES", errors),
    ]
    inner = width - 2 * PAD
    cell = inner / len(cells)
    out = [
        '<g class="summary">',
        _t(PAD, 34, fit(trace.title, inner, 17), "t-title"),
        _t(PAD, 54, fit(" · ".join(sub), inner, 12), "t-sub"),
        f'<rect class="panel" x="{PAD}" y="68" width="{inner:g}" height="58" rx="10"/>',
    ]
    for i, (key, value) in enumerate(cells):
        x = PAD + i * cell + 12
        cls = "t-v"
        if key.startswith("ERRORS") and (totals["errors"] or totals["retries"]):
            cls = "t-v c-err" if totals["errors"] else "t-v c-retry"
        out.append(_t(x, 90, fit(key, cell - 14, 10.5), "t-k"))
        out.append(_t(x, 113, fit(value, cell - 14, 15), cls))
        if i:
            sx = PAD + i * cell
            out.append(
                f'<line class="sep" x1="{sx:.1f}" y1="78" x2="{sx:.1f}" y2="116"/>'
            )
    out.append("</g>")
    return "".join(out)


def _legend(trace: Trace, y: float) -> str:
    kinds = [k for k in KIND_LABELS if any(s.kind == k for s in trace.steps)]
    x = PAD
    out = [f'<g class="legend" transform="translate(0,{y:g})">']
    for kind in kinds:
        out.append(glyph(kind, x, 0, 16))
        out.append(_t(x + 21, 12.5, KIND_LABELS[kind], "t-meta"))
        x += 30 + len(KIND_LABELS[kind]) * 11 * CHAR + 6
    statuses = {s.status for s in trace.steps}
    for status, label in (("error", "Error"), ("retry", "Retry")):
        if status in statuses:
            out.append(marker(status, x + 7, 8))
            out.append(_t(x + 18, 12.5, label, "t-meta"))
            x += 30 + len(label) * 11 * CHAR + 6
    out.append("</g>")
    return "".join(out)


def _open(
    width: float,
    height: float,
    theme: str,
    title: str,
    view: str,
    page: bool,
    extra: str = "",
) -> str:
    style = "" if page else f"<style>{static_css(theme)}</style>"
    ident = f' id="{view}"' if page else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg"{ident} class="view {view}" viewBox="0 0 {width:g} {height:g}" '
        f'width="{width:g}" height="{height:g}" role="img" aria-label="{escape(title, quote=True)}"{extra}>'
        f"<title>{escape(title)}</title>{style}"
        f'<rect class="bg" width="{width:g}" height="{height:g}"/>'
    )


# --------------------------------------------------------------------------- waterfall
def waterfall_svg(trace: Trace, *, theme: str, page: bool = False) -> str:
    t0, span = trace.start_ms, max(trace.duration_ms, 1e-9)
    rows_h = len(trace.steps) * ROW
    legend_y = ROW_TOP + rows_h + LEGEND_GAP
    height = legend_y + 34
    scale = TL_W / span
    out = [
        _open(
            WIDTH,
            height,
            theme,
            f"{trace.title}: waterfall",
            "waterfall",
            page,
            f' data-row-top="{ROW_TOP}" data-row="{ROW}" data-legend-gap="{LEGEND_GAP}"',
        ),
        summary(trace, WIDTH),
    ]
    # axis and grid
    tick = nice_step(span)
    out.append('<g class="grid">')
    out.append(
        f'<line class="axisline" x1="{TL_X}" y1="{AXIS_Y + 4}" x2="{TL_X + TL_W}" y2="{AXIS_Y + 4}"/>'
    )
    n = 0
    while n * tick <= span + 1e-9 and n < 40:
        x = TL_X + n * tick * scale
        out.append(
            f'<line class="gridline" x1="{x:.1f}" y1="{AXIS_Y + 4}" x2="{x:.1f}" y2="{ROW_TOP + rows_h}"/>'
        )
        anchor = "start" if n == 0 else ("end" if x > TL_X + TL_W - 20 else "middle")
        out.append(_t(x, AXIS_Y, fmt_ms(n * tick), "t-tick", anchor))
        n += 1
    out.append("</g>")
    out.append(_t(LABEL_X, AXIS_Y, "STEP", "t-k"))
    out.append(_t(META_X, AXIS_Y, "DURATION · TOKENS · COST", "t-k"))
    for i, step in enumerate(trace.steps):
        out.append(_row(step, i, t0, scale, trace))
    out.append(_legend(trace, legend_y))
    out.append("</svg>")
    return "".join(out)


def _row(step: Step, index: int, t0: float, scale: float, trace: Trace) -> str:
    y = ROW_TOP + index * ROW
    indent = step.depth * 14
    label = f"{KIND_LABELS[step.kind]}: {step.name}"
    out = [
        (
            f'<g class="row" data-id="{escape(step.id, quote=True)}" data-kind="{step.kind}" '
            f'transform="translate(0,{y})" tabindex="0" role="button" aria-label="{escape(label, quote=True)}">'
        ),
        f'<rect class="rowbg{" stripe" if index % 2 else ""}" x="{PAD - 8}" y="0" width="{WIDTH - 2 * PAD + 16}" height="{ROW}" rx="4"/>',
    ]
    x = LABEL_X + indent
    if step.children:
        out.append(
            f'<g class="caret" transform="translate({x + 5},{ROW / 2})"><path d="M-3.5-2.2h7L0 2.8z"/></g>'
        )
    x += 12
    out.append(glyph(step.kind, x, (ROW - 18) / 2))
    out.append(
        _t(
            x + 24,
            ROW / 2 + 4.3,
            fit(step.name, LABEL_W - (x + 24 - LABEL_X) - 6),
            "t-name",
        )
    )
    bx = TL_X + (step.start_ms - t0) * scale
    bw = max(2.5, step.duration_ms * scale)
    status = f" b-{step.status}" if step.status != "ok" else ""
    out.append(
        f'<rect class="track" x="{TL_X}" y="{ROW / 2 - 1}" width="{TL_W}" height="2" rx="1"/>'
    )
    out.append(
        f'<rect class="bar k-{step.kind}{status}" x="{bx:.1f}" y="{ROW / 2 - 7}" width="{bw:.1f}" height="14" rx="3"/>'
    )
    if step.status != "ok":
        mx = min(bx + bw + 10, TL_X + TL_W + 6)
        out.append(marker(step.status, mx, ROW / 2))
    out.append(_t(META_X, ROW / 2 + 4, fmt_ms(step.duration_ms), "t-dur"))
    meta, cls = step_meta(step), "t-meta"
    if step.status != "ok":
        meta = " · ".join(p for p in (step.status, meta, step.note) if p)
        cls = "t-err" if step.status == "error" else "t-retry"
    if meta:
        out.append(
            _t(META_X + 52, ROW / 2 + 4, fit(meta, WIDTH - PAD - META_X - 52, 11), cls)
        )
    out.append("</g>")
    return "".join(out)


# --------------------------------------------------------------------------- flow
@dataclass
class Lane:
    key: str
    kind: str
    name: str


def lanes_of(trace: Trace) -> tuple[list[Lane], dict[str, str], str | None]:
    """The flow view's lanes, each step's lane, and the root folded into the agent lane."""
    roots = [
        s for s in trace.steps if s.parent is None and s.kind not in ("user", "reply")
    ]
    host = roots[0] if len(roots) == 1 and roots[0].kind == "subagent" else None
    lanes: dict[str, Lane] = {}
    if any(s.kind in ("user", "reply") for s in trace.steps):
        lanes["user"] = Lane("user", "user", "User")
    lanes["agent"] = Lane("agent", "subagent", host.name if host else "Agent")
    placed: dict[str, str] = {}
    by_kind_count: dict[str, set[str]] = {}
    for s in trace.steps:
        if s.kind in ("tool", "retrieval", "memory", "guardrail"):
            by_kind_count.setdefault(s.kind, set()).add(s.tool or s.name)
    many = sum(len(v) for v in by_kind_count.values()) > 6
    for s in trace.steps:
        if host is not None and s.id == host.id:
            placed[s.id] = "agent"
            continue
        if s.kind in ("user", "reply"):
            placed[s.id] = "user"
            continue
        if s.kind == "error":
            placed[s.id] = ""
            continue
        if s.kind == "subagent":
            key, name = f"sub:{s.id}", s.name
        elif s.kind == "llm":
            label = s.model or trace.model or "LLM"
            key, name = f"llm:{label}", label
        elif many:
            key, name = f"{s.kind}:*", KIND_LABELS[s.kind]
        else:
            label = s.tool or s.name
            key, name = f"{s.kind}:{label}", label
        lanes.setdefault(key, Lane(key, s.kind, name))
        placed[s.id] = key
    return list(lanes.values()), placed, host.id if host else None


def _caller(step: Step, trace: Trace, placed: dict[str, str]) -> str:
    cursor = trace.by_id.get(step.parent) if step.parent else None
    while cursor is not None:
        if cursor.kind == "subagent":
            return placed.get(cursor.id) or "agent"
        cursor = trace.by_id.get(cursor.parent) if cursor.parent else None
    return "agent"


def _arrow(x1: float, x2: float, y: float, cls: str, head_cls: str) -> str:
    if abs(x2 - x1) < 1:
        return (
            f'<path class="arrow {cls}" d="M{x1:.1f} {y - 6:.1f}h26v12h-22"/>'
            f'<path class="ahead {head_cls}" d="M{x1 + 1:.1f} {y + 6:.1f}l7 -4v8z"/>'
        )
    direction = 1 if x2 > x1 else -1
    tip = x2 - direction * 1
    return (
        f'<line class="arrow {cls}" x1="{x1:.1f}" y1="{y:.1f}" x2="{tip - direction * 7:.1f}" y2="{y:.1f}"/>'
        f'<path class="ahead {head_cls}" d="M{tip:.1f} {y:.1f}l{-direction * 8} -4.2v8.4z"/>'
    )


def flow_svg(trace: Trace, *, theme: str, page: bool = False) -> str:
    lanes, placed, host = lanes_of(trace)
    index = {lane.key: i for i, lane in enumerate(lanes)}
    width = max(760.0, 2 * PAD + len(lanes) * LANE_W)
    left = (width - len(lanes) * LANE_W) / 2

    def cx(key: str) -> float:
        return left + index[key] * LANE_W + LANE_W / 2

    order = {s.id: i for i, s in enumerate(trace.steps)}
    messages = sorted(
        (s for s in trace.steps if s.id != host),
        key=lambda s: (s.start_ms, order[s.id]),
    )
    rows_h = len(messages) * MSG
    legend_y = MSG_TOP + rows_h + LEGEND_GAP
    height = legend_y + 34
    out = [
        _open(
            width,
            height,
            theme,
            f"{trace.title}: flow",
            "flow",
            page,
            f' data-row-top="{MSG_TOP}" data-row="{MSG}" data-legend-gap="{LEGEND_GAP}"',
        ),
        summary(trace, width),
        '<g class="lanes">',
    ]
    for lane in lanes:
        x = cx(lane.key)
        out.append(
            f'<line class="lifeline" x1="{x:.1f}" y1="{LANE_TOP + LANE_H}" x2="{x:.1f}" y2="{MSG_TOP + rows_h}"/>'
        )
        bx = x - LANE_W / 2 + 8
        out.append(
            f'<g class="lane" data-lane="{escape(lane.key, quote=True)}">'
            f'<rect class="lanebox" x="{bx:.1f}" y="{LANE_TOP}" width="{LANE_W - 16}" height="{LANE_H}" rx="9"/>'
            + glyph(lane.kind, bx + 8, LANE_TOP + 11)
            + _t(
                bx + 32,
                LANE_TOP + LANE_H / 2 + 4,
                fit(lane.name, LANE_W - 16 - 38, 12),
                "t-lane",
            )
            + "</g>"
        )
    out.append("</g>")
    for i, step in enumerate(messages):
        y = MSG_TOP + i * MSG
        label = f"{KIND_LABELS[step.kind]}: {step.name}"
        out.append(
            f'<g class="msg" data-id="{escape(step.id, quote=True)}" data-kind="{step.kind}" '
            f'transform="translate(0,{y})" tabindex="0" role="button" aria-label="{escape(label, quote=True)}">'
            f'<rect class="rowbg{" stripe" if i % 2 else ""}" x="{PAD - 8}" y="0" width="{width - 2 * PAD + 16:g}" height="{MSG}" rx="4"/>'
        )
        caller = _caller(step, trace, placed)
        a_cls = f"a-{step.status}" if step.status != "ok" else ""
        h_cls = f"h-{step.status}" if step.status != "ok" else ""
        dur = fmt_ms(step.duration_ms)
        if step.kind == "error" or not placed.get(step.id):
            x = cx(caller)
            out.append(
                f'<rect class="notebox" x="{x - 66:.1f}" y="8" width="132" height="28" rx="6"/>'
            )
            out.append(marker("error", x - 52, 22))
            out.append(_t(x + 6, 26, fit(step.name, 100, 11.5), "t-msg", "middle"))
        elif step.kind == "user":
            x1, x2 = cx("user"), cx(caller)
            out.append(
                _t(
                    (x1 + x2) / 2,
                    16,
                    fit(step.name, abs(x2 - x1) + LANE_W - 30, 11.5),
                    "t-msg",
                    "middle",
                )
            )
            out.append(_arrow(x1, x2, 24, a_cls, h_cls))
        elif step.kind == "reply":
            x1, x2 = cx(caller), cx("user")
            out.append(
                _t(
                    (x1 + x2) / 2,
                    16,
                    fit(step.name, abs(x2 - x1) + LANE_W - 30, 11.5),
                    "t-msg",
                    "middle",
                )
            )
            out.append(_arrow(x1, x2, 24, a_cls, h_cls))
        else:
            x1, x2 = cx(caller), cx(placed[step.id])
            mid = (x1 + x2) / 2 if abs(x2 - x1) > 1 else x1 + 50
            room = max(abs(x2 - x1), LANE_W) - 20
            out.append(_t(mid, 14, fit(step.name, room, 11.5), "t-msg", "middle"))
            out.append(_arrow(x1, x2, 21, a_cls, h_cls))
            back = " · ".join(p for p in (dur, tokens_label(step)) if p)
            if abs(x2 - x1) > 1:
                out.append(_arrow(x2, x1, 35, f"ret {a_cls}", h_cls))
                out.append(_t(mid, 31, fit(back, room, 10.5), "t-tick", "middle"))
            if step.status != "ok":
                out.append(marker(step.status, x2 + (8 if x2 >= x1 else -8) * 1.6, 21))
        out.append("</g>")
    out.append(_legend(trace, legend_y))
    out.append("</svg>")
    return "".join(out)
