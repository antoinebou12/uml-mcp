"""The standalone, CSP-locked interactive page around the two trace views.

* The trace reaches the page only as JSON in a ``<script type="application/json">`` block
  with ``<``, ``>`` and ``&`` escaped; the script shows every string with ``textContent``.
* The ``Content-Security-Policy`` allows exactly the one script and the one stylesheet on
  the page (by SHA-256), no network at all, and sets ``base-uri``/``form-action`` to none.
"""

from __future__ import annotations

import base64
import hashlib
import json
from functools import cache
from html import escape
from importlib.resources import files
from typing import Any

from .docs import step_docs
from .spec import Trace
from .svg import flow_svg, fmt_cost, fmt_ms, fmt_tokens, waterfall_svg
from .theme import KIND_COLORS, KIND_LABELS, page_css, static_css


@cache
def asset(name: str) -> str:
    return (
        files("uml_mcp_plugin_trace")
        .joinpath("assets", name)
        .read_text(encoding="utf-8")
        .replace("\r\n", "\n")
    )


def _hash(text: str) -> str:
    return base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode(
        "ascii"
    )


def json_for_script(data: Any) -> str:
    text = json.dumps(data, separators=(",", ":"), ensure_ascii=True)
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def page_data(trace: Trace) -> dict[str, Any]:
    """Everything the script needs for the detail card, collapse and the critical path."""
    return {
        "title": trace.title,
        "model": trace.model,
        "start": trace.start_ms,
        "end": trace.end_ms,
        "critical": trace.critical,
        "steps": [
            {
                "id": s.id,
                "parent": s.parent,
                "children": list(s.children),
                "kind": s.kind,
                "kindLabel": KIND_LABELS[s.kind],
                "color": KIND_COLORS[s.kind],
                "name": s.name,
                "start": s.start_ms,
                "end": s.end_ms,
                "status": s.status,
                "model": s.model,
                "tool": s.tool,
                "note": s.note,
                "input": s.input,
                "output": s.output,
                "tokens": (
                    {"in": s.tokens_in, "out": s.tokens_out, "cached": s.tokens_cached}
                    if s.has_tokens
                    else None
                ),
                "cost_usd": s.cost_usd,
                "docs": [
                    {"title": d.title, "score": d.score, "source": d.source}
                    for d in s.docs
                ],
                "docs_url": step_docs(s.kind, s.model, s.tool, trace.model),
            }
            for s in trace.steps
        ],
    }


def _meta(trace: Trace) -> str:
    t = trace.totals()
    parts = [
        trace.model,
        fmt_ms(t["duration_ms"]),
        f"{fmt_tokens(t['tokens_in'])} in / {fmt_tokens(t['tokens_out'])} out",
        fmt_cost(t["cost_usd"]) if t["cost_usd"] is not None else "",
    ]
    return " · ".join(p for p in parts if p)


def page(trace: Trace) -> str:
    dark = trace.theme != "light"
    theme = "dark" if dark else "light"
    waterfall = waterfall_svg(trace, theme=theme, page=True)
    flow = flow_svg(trace, theme=theme, page=True).replace(
        'class="view flow"', 'class="view flow" hidden', 1
    )
    script = asset("trace.js")
    style = asset("page.css") + page_css()
    csp = (
        "default-src 'none'; "
        f"script-src 'sha256-{_hash(script)}'; "
        f"style-src 'sha256-{_hash(style)}'; "
        "img-src data: blob:; base-uri 'none'; form-action 'none'"
    )
    title = escape(trace.title)
    export_css = {"light": static_css("light"), "dark": static_css("dark")}
    return (
        "<!doctype html>\n"
        f'<html lang="en" data-theme="{theme}" data-auto="{"1" if trace.theme == "auto" else "0"}">'
        '<head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta http-equiv="Content-Security-Policy" content="{escape(csp, quote=True)}">'
        f"<title>{title}</title><style>{style}</style></head><body>"
        f'<header><div class="ident"><h1>{title}</h1><span class="meta">{escape(_meta(trace))}</span></div>'
        '<div class="toolbar" role="toolbar" aria-label="Trace controls">'
        '<span class="seg" role="group" aria-label="View">'
        '<button id="v-waterfall" type="button" aria-pressed="true">Waterfall</button>'
        '<button id="v-flow" type="button" aria-pressed="false">Flow</button></span>'
        '<button id="crit" type="button" aria-pressed="false" title="Highlight the steps that decide the total time">Critical path</button>'
        '<button id="collapse" type="button" aria-pressed="false" title="Fold sub-agents">Collapse</button>'
        '<button id="zout" type="button" aria-label="Zoom out">−</button>'
        '<span id="zoomval" class="zoom">100%</span>'
        '<button id="zin" type="button" aria-label="Zoom in">+</button>'
        '<button id="fit" type="button">Fit</button>'
        '<button id="theme" type="button">Theme</button>'
        '<details class="menu" id="export"><summary>Export</summary><div class="items">'
        '<button id="save" type="button">Save SVG</button>'
        '<button id="png" type="button">Save PNG</button>'
        '<button id="html" type="button">Save HTML</button></div></details>'
        "</div></header>"
        f'<main><div id="stage">{waterfall}{flow}</div>'
        '<aside id="card" hidden aria-live="polite" aria-label="Step details">'
        '<button id="c-close" type="button" class="close" aria-label="Close">×</button>'
        '<div class="c-head"><span id="c-dot"></span><div><div id="c-kind" class="kicker"></div>'
        '<h2 id="c-title"></h2><div id="c-sub" class="sub"></div></div></div>'
        '<button id="c-docs" type="button" class="docs" hidden>Open documentation ↗</button>'
        '<div id="c-body"></div></aside>'
        '<div id="tip" role="tooltip" hidden></div>'
        '<div class="hint">Click a step for details · ▸ folds a step · drag to pan · scroll to zoom</div>'
        "</main>"
        '<output id="status" class="sr-only" aria-live="polite"></output>'
        f'<script type="application/json" id="trace">{json_for_script(page_data(trace))}</script>'
        f'<script type="application/json" id="export-css">{json_for_script(export_css)}</script>'
        f"<script>{script}</script></body></html>\n"
    )
