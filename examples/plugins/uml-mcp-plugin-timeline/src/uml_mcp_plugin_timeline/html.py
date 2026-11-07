"""Standalone, CSP-locked HTML page: hashed inline script and style, no network."""

from __future__ import annotations

import base64
import hashlib
import json
from functools import cache
from html import escape
from importlib.resources import files
from typing import Any

from .model import STATUSES, Timeline
from .svg import LEVELS, PALETTES, STATUS_LABELS, fmt_date

_LEVEL_NAMES = (
    ("quarter", "Quarters", "Q"),
    ("month", "Months", "M"),
    ("week", "Weeks", "W"),
    ("day", "Days", "D"),
)


@cache
def asset(name: str) -> str:
    return (
        files("uml_mcp_plugin_timeline")
        .joinpath("assets", name)
        .read_text(encoding="utf-8")
    )


def _hash(text: str) -> str:
    return base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode(
        "ascii"
    )


def json_for_script(data: Any) -> str:
    text = json.dumps(data, separators=(",", ":"), ensure_ascii=True)
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _options(label: str, values: list[tuple[str, str]]) -> str:
    return f'<option value="">{escape(label)}</option>' + "".join(
        f'<option value="{escape(v, quote=True)}">{escape(text)}</option>'
        for v, text in values
    )


def page(tl: Timeline) -> str:
    script = asset("timeline.js")
    style = asset("timeline.css")
    csp = (
        "default-src 'none'; "
        f"script-src 'sha256-{_hash(script)}'; "
        f"style-src 'sha256-{_hash(style)}'; "
        "img-src data: blob:; base-uri 'none'; form-action 'none'"
    )
    first, last = tl.span
    meta = tl.subtitle or (
        f"{fmt_date(first)} – {fmt_date(last - 1)} · {len(tl.items)} items · "
        f"{len(tl.lanes)} lanes"
    )
    theme = "light" if tl.theme == "light" else "dark"
    owners = sorted({i.owner for i in tl.items if i.owner}, key=str.lower)
    levels = "".join(
        f'<button type="button" data-level="{key}" aria-label="{long}" title="{long}">'
        f'<span class="long">{long}</span><span class="short">{short}</span></button>'
        for key, long, short in _LEVEL_NAMES
    )
    legend = "".join(
        f'<span class="chip s-{s}">{escape(STATUS_LABELS[s])}</span>' for s in STATUSES
    )
    data = {
        "timeline": tl.as_dict(),
        "palettes": PALETTES,
        "levels": LEVELS,
        "statusLabels": STATUS_LABELS,
    }
    return (
        "<!doctype html>\n"
        f'<html lang="en" data-theme="{theme}" data-auto="{"1" if tl.theme == "auto" else "0"}">'
        '<head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta http-equiv="Content-Security-Policy" content="{escape(csp, quote=True)}">'
        f"<title>{escape(tl.title)}</title><style>{style}</style></head><body>"
        f'<header><div class="ident"><h1>{escape(tl.title)}</h1>'
        f'<span class="meta">{escape(meta)}</span></div>'
        '<div class="toolbar" role="toolbar" aria-label="Timeline controls">'
        '<div class="seg" role="group" aria-label="Zoom">'
        '<button id="zout" type="button" aria-label="Zoom out" title="Zoom out">−</button>'
        f"{levels}"
        '<button id="zin" type="button" aria-label="Zoom in" title="Zoom in">+</button></div>'
        '<button id="now" type="button" title="Scroll to today">Now</button>'
        '<button id="fit" type="button" title="Fit the whole timeline">Fit</button>'
        '<select id="f-lane" aria-label="Filter by lane">'
        f"{_options('All lanes', [(lane.id, lane.name) for lane in tl.lanes])}</select>"
        '<select id="f-owner" aria-label="Filter by owner">'
        f"{_options('All owners', [(o, o) for o in owners])}</select>"
        '<select id="f-status" aria-label="Filter by status">'
        f"{_options('All statuses', [(s, STATUS_LABELS[s]) for s in STATUSES])}</select>"
        '<button id="theme" type="button">Theme</button>'
        '<details class="menu"><summary>Export</summary><div>'
        '<button id="save" type="button">SVG</button>'
        '<button id="png" type="button">PNG</button>'
        '<button id="html" type="button">HTML</button></div></details>'
        "</div></header>"
        '<main id="view" tabindex="0" aria-label="Timeline: drag to pan, wheel or pinch to zoom">'
        '<div id="stage"></div><aside id="card" hidden aria-live="polite"></aside></main>'
        f"<footer>{legend}<span>◆ milestone</span><span>⚑ release</span>"
        '<span class="hint">Click an item for details and its dependency chain · '
        "drag to pan · wheel to zoom · Esc clears</span></footer>"
        f'<script type="application/json" id="spec">{json_for_script(data)}</script>'
        f"<script>{script}</script></body></html>\n"
    )
