"""``archify_sequence``: participants across the top, lifelines, ordered messages."""

from __future__ import annotations

import json
from dataclasses import dataclass
from html import escape

from uml_mcp_plugin_stack_diagram import spec as base
from uml_mcp_plugin_stack_diagram.layout import Placed
from uml_mcp_plugin_stack_diagram.render import (
    marker_defs,
    preset_css,
    resolve_theme,
    tone_css,
)
from uml_mcp_plugin_stack_diagram.spec import SpecError

from .skin import NODE_H, NODE_W, ArchifySkin

MAX_PARTICIPANTS = 12
MAX_MESSAGES = 100
LANE = 250  # distance between lifelines
ROW = 62  # distance between messages
CYCLE = ("blue", "green", "purple", "orange", "teal", "red", "yellow")


@dataclass(frozen=True)
class Message:
    source: str
    target: str
    label: str
    dashed: bool
    tone: str | None
    note: str


@dataclass(frozen=True)
class SeqSpec:
    title: str
    subtitle: str
    theme: str
    preset: str
    participants: tuple[base.Node, ...]
    messages: tuple[Message, ...]


def parse(
    source: str, *, presets: tuple[str, ...], max_participants: int = MAX_PARTICIPANTS
) -> SeqSpec:
    try:
        root = json.loads(base._strip_fence(source))
    except json.JSONDecodeError as exc:
        raise SpecError(
            f"source must be JSON: line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    if not isinstance(root, dict):
        raise SpecError("source must be an object")
    theme = base._text(root.get("theme"), "theme", default="auto", maximum=5)
    if theme not in base.THEMES:
        raise SpecError("theme must be 'dark', 'light' or 'auto'")
    preset = base._text(root.get("preset"), "preset", default=presets[0], maximum=12)
    if preset not in presets:
        raise SpecError(f"preset must be one of: {', '.join(presets)}")

    raw = base._list(root, "participants", max_participants)
    if len(raw) < 2:
        raise SpecError("participants needs at least two entries")
    people: list[base.Node] = []
    seen: set[str] = set()
    for i, item in enumerate(raw):
        pid = base._ident(item.get("id"), f"participants[{i}].id")
        if pid in seen:
            raise SpecError(f"duplicate participant id: {pid}")
        seen.add(pid)
        people.append(
            base.Node(
                pid,
                base._text(item.get("name"), f"participants[{i}].name", default=pid),
                base._text(item.get("role"), f"participants[{i}].role", maximum=40),
                base._icon(item.get("icon"), f"participants[{i}].icon"),
                None,
                base._tone(item.get("tone"), f"participants[{i}].tone", base.TONES),
                base._text(item.get("tag"), f"participants[{i}].tag", maximum=24),
            )
        )
    messages: list[Message] = []
    for i, item in enumerate(base._list(root, "messages", MAX_MESSAGES)):
        ends = []
        for end in ("from", "to"):
            value = base._ident(item.get(end), f"messages[{i}].{end}")
            if value not in seen:
                raise SpecError(
                    f"messages[{i}].{end} references unknown participant {value!r}"
                )
            ends.append(value)
        style = base._text(
            item.get("style"), f"messages[{i}].style", default="solid", maximum=6
        )
        if style not in {"solid", "dashed"}:
            raise SpecError(
                f"messages[{i}].style must be 'solid' (call) or 'dashed' (reply)"
            )
        messages.append(
            Message(
                ends[0],
                ends[1],
                base._text(item.get("label"), f"messages[{i}].label", maximum=60),
                style == "dashed",
                base._tone(item.get("tone"), f"messages[{i}].tone", base.TONES),
                base._text(item.get("note"), f"messages[{i}].note", maximum=60),
            )
        )
    if not messages:
        raise SpecError("messages must be a non-empty array")
    return SeqSpec(
        base._text(root.get("title"), "title", default="Sequence"),
        base._text(root.get("subtitle"), "subtitle", maximum=160),
        theme,
        preset,
        tuple(people),
        tuple(messages),
    )


def build(
    spec: SeqSpec, skin: ArchifySkin, *, theme: str, live: bool
) -> tuple[str, str, dict]:
    """``(svg without style, css, graph)`` for the page or the static file."""
    source = skin.palettes[theme]
    pal = {key: f"var(--{key})" for key in source} if live else source
    margin = 56
    centres = {
        p.id: margin + NODE_W / 2 + i * LANE for i, p in enumerate(spec.participants)
    }
    tone_of = {
        p.id: p.tone or CYCLE[i % len(CYCLE)] for i, p in enumerate(spec.participants)
    }
    top = 0 if live else skin.header_height(spec)  # type: ignore[arg-type]
    body_top = NODE_H + 54
    height_body = body_top + len(spec.messages) * ROW + 40
    width = margin * 2 + NODE_W + (len(spec.participants) - 1) * LANE
    height = top + height_body

    lifelines, cards, messages = [], [], []
    for p in spec.participants:
        cx = centres[p.id]
        lifelines.append(
            f'<line class="life" x1="{cx:.0f}" y1="{NODE_H}" x2="{cx:.0f}" y2="{height_body - 20}"/>'
        )
        rect = (cx - NODE_W / 2, 0.0, float(NODE_W), float(NODE_H))
        cards.append(skin.node(Placed(p, rect, rect), tone_of[p.id]))

    tones: set[str] = set()
    for i, m in enumerate(spec.messages):
        y = body_top + i * ROW + 22
        tone = m.tone or tone_of[m.source]
        tones.add(tone)
        x1, x2 = centres[m.source], centres[m.target]
        dash = " e-dash" if m.dashed else ""
        marker = f'marker-end="url(#ar-{tone})"'
        if m.source == m.target:
            d = f"M{x1 + 4:.0f} {y}h44v26h-40"
            lx, ly, anchor = x1 + 58, y + 16, "start"
        else:
            sign = 1 if x2 > x1 else -1
            d = f"M{x1 + 6 * sign:.0f} {y}H{x2 - 7 * sign:.0f}"
            lx, ly, anchor = (x1 + x2) / 2, y - 9, "middle"
        act = (
            f'<rect class="act t-{tone}" x="{x2 - 6:.0f}" y="{y - 8}" width="12" height="30" rx="3"/>'
            if not m.dashed and m.source != m.target
            else ""
        )
        note = (
            f'<text class="note" x="{lx:.0f}" y="{ly + 22}" text-anchor="{anchor}">{escape(m.note)}</text>'
            if m.note
            else ""
        )
        messages.append(
            f'<g class="edge" data-from="{escape(m.source, quote=True)}" data-to="{escape(m.target, quote=True)}">'
            f'{act}<path class="glow e-{tone}" d="{d}"/>'
            f'<path class="line e-{tone}{dash}" d="{d}" {marker}/>'
            f'<text class="elabel seq l-{tone}" x="{lx:.0f}" y="{ly}" text-anchor="{anchor}">'
            f"{escape(m.label)}</text>{note}</g>"
        )

    chrome = skin.header(spec, width, theme) if top else ""  # type: ignore[arg-type]
    label = escape(spec.title, quote=True)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" role="img" aria-label="{label}" class="diagram">'
        f"<title>{escape(spec.title)}</title><defs>{marker_defs(tones)}</defs>"
        f"{skin.background(width, height)}{chrome}"
        f'<g class="scene" transform="translate({0} {top})">'
        f'<g transform="translate({0} {0})">{"".join(lifelines)}</g>'
        f"{''.join(messages)}{''.join(cards)}</g>{skin.frame(width, height)}</svg>"
    )
    css = (
        tone_css(pal)
        + skin.css(pal)
        + f".life{{stroke:{pal['edge']};stroke-width:1.4;stroke-dasharray:5 6}}"
        + ".act{fill-opacity:.35;stroke-width:1.3}.seq{font-size:12px}"
        + f".note{{fill:{pal['muted']};font:10.5px ui-monospace,Consolas,monospace}}"
        + preset_css(skin, spec.preset, live=live)
    )
    graph = {
        "nodes": [
            {
                "id": p.id,
                "name": p.name,
                "role": p.role,
                "tag": p.tag,
                "path": "",
                "kind": "Participant",
            }
            for p in spec.participants
        ],
        "edges": [
            {"from": m.source, "to": m.target, "label": m.label} for m in spec.messages
        ],
        "groups": [],
    }
    return svg, css, graph


def render_static(spec: SeqSpec, skin: ArchifySkin) -> str:
    svg, css, _ = build(spec, skin, theme=resolve_theme(spec), live=False)  # type: ignore[arg-type]
    return svg.replace("<defs>", f"<style>{css}</style><defs>", 1)


def page(spec: SeqSpec, skin: ArchifySkin) -> str:
    from uml_mcp_plugin_stack_diagram import html

    theme = resolve_theme(spec)  # type: ignore[arg-type]
    svg, css, graph = build(spec, skin, theme=theme, live=True)
    return html.shell(
        title=spec.title,
        subtitle=spec.subtitle,
        theme=theme,
        auto=spec.theme == "auto",
        preset=spec.preset,
        svg=svg,
        css=css,
        skin=skin,
        graph=graph,
        meta=f"archify · sequence · {len(spec.participants)} participants",
    )
