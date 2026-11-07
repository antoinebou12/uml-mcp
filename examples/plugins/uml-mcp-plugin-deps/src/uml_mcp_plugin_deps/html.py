"""Standalone, CSP-locked interactive page: no network, hashed inline script and style."""

from __future__ import annotations

import base64
import hashlib
import json
from functools import cache
from html import escape
from importlib.resources import files
from typing import Any

from .layout import Tree, requested
from .svg import (
    KIND_LABELS,
    PALETTES,
    RULES,
    cap_notice,
    counts,
    css,
    summary,
    title_of,
)
from .svg import variables as theme_vars

_PAGE_CSS = (
    "*{box-sizing:border-box}html,body{height:100%;margin:0}"
    "body{display:flex;flex-direction:column;background:var(--bg);color:var(--ink);"
    "font:13px/1.4 system-ui,-apple-system,'Segoe UI',Roboto,sans-serif}"
    "header{display:flex;flex-wrap:wrap;align-items:center;gap:6px 14px;padding:8px 12px;"
    "border-bottom:1px solid var(--line);background:var(--panel)}"
    ".ident{display:flex;flex-direction:column;min-width:0;margin-right:auto}"
    "h1{margin:0;font-size:15px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}"
    ".meta{color:var(--muted);font-size:12px}"
    ".toolbar{display:flex;flex-wrap:wrap;align-items:center;gap:4px}"
    ".grp{display:inline-flex;gap:2px}"
    "button,input{font:inherit;color:var(--ink);background:var(--bg);border:1px solid var(--line);"
    "border-radius:7px;padding:3px 9px;cursor:pointer}"
    "input{cursor:text;width:150px}"
    "button:hover{border-color:var(--accent)}"
    "button:focus-visible,input:focus-visible,[data-i]:focus-visible{outline:2px solid var(--accent);"
    "outline-offset:2px}"
    "button[aria-pressed=true]{border-color:var(--ink);font-weight:600}"
    "button[aria-pressed=false][data-kind]{opacity:.55;text-decoration:line-through}"
    "[data-kind]::before{content:'';display:inline-block;width:8px;height:8px;border-radius:50%;"
    "margin-right:5px;background:var(--c)}"
    "[data-kind=runtime],[data-legend=runtime]{--c:var(--runtime)}"
    "[data-kind=dev],[data-legend=dev]{--c:var(--dev)}"
    "[data-kind=optional],[data-legend=optional]{--c:var(--optional)}"
    "[data-kind=peer],[data-legend=peer]{--c:var(--peer)}"
    ".found{color:var(--muted);font-size:12px;min-width:3.5em}"
    ".zoom{min-width:40px;text-align:center;color:var(--muted);font-size:12px}"
    ".menu{position:relative}"
    "#export-menu{position:absolute;right:0;top:calc(100% + 4px);z-index:5;display:grid;gap:2px;"
    "padding:4px;background:var(--panel);border:1px solid var(--line);border-radius:8px;"
    "box-shadow:0 8px 24px rgba(0,0,0,.2)}"
    "#export-menu[hidden]{display:none}#export-menu button{border:0;text-align:left}"
    "main{flex:1;min-height:0;position:relative;overflow:hidden;cursor:grab;touch-action:none}"
    "main.panning{cursor:grabbing}"
    "#canvas{display:block;width:100%;height:100%;user-select:none;-webkit-user-select:none}"
    "[data-i]{cursor:pointer}[data-toggle]{cursor:pointer}"
    ".notice{position:absolute;left:10px;top:8px;right:10px;padding:4px 10px;border-radius:7px;"
    "font-size:12px;color:var(--ink);background:var(--panel);border:1px solid var(--dup);pointer-events:none;"
    "width:max-content;max-width:calc(100% - 20px)}"
    ".legend{position:absolute;left:10px;bottom:8px;display:flex;flex-wrap:wrap;gap:4px 12px;"
    "padding:4px 10px;border-radius:7px;font-size:11.5px;color:var(--muted);background:var(--panel);"
    "border:1px solid var(--line);pointer-events:none;max-width:calc(100% - 20px)}"
    ".legend span::before{content:'';display:inline-block;width:8px;height:8px;border-radius:50%;"
    "margin-right:5px;background:var(--c)}"
    ".legend .dupkey::before{background:none;border:2px dashed var(--dup);width:12px;height:6px;border-radius:4px}"
    "#card{position:absolute;right:12px;top:12px;width:300px;max-height:calc(100% - 24px);overflow:auto;"
    "padding:12px 14px;border:1px solid var(--line);border-radius:12px;background:var(--panel);"
    "box-shadow:0 10px 30px rgba(0,0,0,.22);cursor:default}"
    "#card[hidden]{display:none}"
    "#card .top{display:flex;align-items:center;gap:6px}"
    "#card .kicker{font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);flex:1}"
    "#card .dot{width:9px;height:9px;border-radius:50%;background:var(--root)}"
    "#card .dot.k-runtime{background:var(--runtime)}#card .dot.k-dev{background:var(--dev)}"
    "#card .dot.k-optional{background:var(--optional)}#card .dot.k-peer{background:var(--peer)}"
    "#card h2{margin:4px 0 8px;font-size:16px;word-break:break-word}"
    "#card-close{border:0;padding:0 6px;font-size:16px;line-height:1}"
    ".facts{display:grid;gap:3px;margin-bottom:6px}.fact{display:flex;gap:8px}"
    ".fact .k{color:var(--muted);width:76px;flex:none}.fact .v{word-break:break-word}"
    "#card .h{margin:10px 0 3px;font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}"
    "#card .trail{font-size:12px;word-break:break-word}"
    "#card .warn{margin-top:8px;padding:4px 8px;border-radius:6px;border:1px dashed var(--dup);font-size:12px}"
    "#card .list{display:grid;gap:1px}"
    "#card .list button{border:0;background:none;text-align:left;padding:3px 6px;border-radius:5px;"
    "display:flex;justify-content:space-between;gap:8px}"
    "#card .list button:hover{background:var(--bg)}"
    "#card .via{color:var(--muted);font-size:11.5px}#card .more{color:var(--muted);font-size:12px;padding:2px 6px}"
    "#card-docs{margin-top:10px;width:100%;border-color:var(--accent)}#card-docs[hidden]{display:none}"
    ":root[data-view=force] [data-tree]{display:none}"
    # inside the MCP App viewer: the viewer shows the title, keep only a slim toolbar
    ':root[data-embedded="1"] .ident{display:none}'
    ':root[data-embedded="1"] header{padding:5px 8px}'
    "@media (max-width:720px){#card{left:8px;right:8px;top:auto;bottom:8px;width:auto;max-height:55%}"
    "input{width:110px}.legend{display:none}header{gap:4px 8px}button{padding:2px 7px}"
    ".zoom,#zin,#zout{display:none}}"
)


@cache
def _script() -> str:
    return (files(__package__) / "assets" / "page.js").read_text(encoding="utf-8")


def _hash(text: str) -> str:
    return base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode(
        "ascii"
    )


def _json(data: Any) -> str:
    text = json.dumps(data, separators=(",", ":"), ensure_ascii=True)
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _style() -> str:
    themes = "".join(
        f":root[data-theme={name}]{{{theme_vars(name)}}}" for name in PALETTES
    )
    # before the script runs, "auto" follows the system
    auto = (
        f":root[data-theme=auto]{{{theme_vars('light')}}}"
        f"@media (prefers-color-scheme:dark){{:root[data-theme=auto]{{{theme_vars('dark')}}}}}"
    )
    return _PAGE_CSS + auto + themes + RULES


def page_data(tree: Tree) -> dict[str, Any]:
    graph = tree.graph
    index = {pid: n for n, pid in enumerate(tree.order)}
    nodes = []
    for pid in tree.order:
        p = graph.packages[pid]
        owner = tree.parent[pid]
        nodes.append(
            {
                "id": pid,
                "name": p.name,
                "version": p.version,
                "license": p.license,
                "kind": p.kind or "runtime",
                "group": p.group,
                "eco": p.ecosystem,
                "extras": p.extras,
                "marker": p.marker,
                "docs": p.docs if p.docs.startswith("https://") else "",
                "d": tree.depth[pid],
                "p": index[owner] if owner is not None else -1,
                "req": requested(tree, pid) if owner is not None else "",
            }
        )
    edges = [
        {"f": index[e.source], "t": index[e.target], "r": e.range, "k": e.kind}
        for e in tree.edges
    ]
    return {
        "title": title_of(tree),
        "nodes": nodes,
        "edges": edges,
        "css": {name: css(name) for name in PALETTES},
    }


def page(tree: Tree) -> str:
    graph = tree.graph
    style, script = _style(), _script()
    csp = (
        "default-src 'none'; "
        f"script-src 'sha256-{_hash(script)}'; "
        f"style-src 'sha256-{_hash(style)}'; "
        "img-src data: blob:; base-uri 'none'; form-action 'none'"
    )
    c = counts(tree)
    kinds_present = [k for k in KIND_LABELS if c[k]]
    toggles = "".join(
        f'<button type="button" data-kind="{k}" aria-pressed="true" '
        f'title="Show or hide {k} dependencies">{k}</button>'
        for k in kinds_present
        if k != "runtime"
    )
    legend = "".join(
        f'<span data-legend="{k}">{k} {c[k]}</span>' for k in kinds_present
    )
    if tree.duplicates:
        legend += '<span class="dupkey">several versions</span>'
    notice = cap_notice(tree)
    notes = " · ".join(graph.notes[:2])
    title = title_of(tree)
    return (
        "<!doctype html>\n"
        f'<html lang="en" data-theme="{escape(graph.theme)}">'
        '<head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta http-equiv="Content-Security-Policy" content="{escape(csp, quote=True)}">'
        f"<title>{escape(title)}</title><style>{style}</style></head><body>"
        f'<header><div class="ident"><h1>{escape(title)}</h1>'
        f'<span class="meta">{escape(summary(tree))}</span></div>'
        '<div class="toolbar" role="toolbar" aria-label="Graph controls">'
        '<input id="search" type="search" placeholder="Search packages" aria-label="Search packages">'
        '<span id="found" class="found" aria-live="polite"></span>'
        '<span class="grp"><button id="view-tree" type="button" aria-pressed="true">Tree</button>'
        '<button id="view-graph" type="button" aria-pressed="false">Graph</button></span>'
        f'<span class="grp">{toggles}</span>'
        '<span class="grp" data-tree><button id="expand" type="button" title="Expand every package">Expand</button>'
        '<button id="collapse" type="button" title="Show direct dependencies only">Collapse</button></span>'
        '<span class="grp"><button id="zout" type="button" aria-label="Zoom out">−</button>'
        '<span id="zoomval" class="zoom">100%</span>'
        '<button id="zin" type="button" aria-label="Zoom in">+</button>'
        '<button id="fit" type="button">Fit</button>'
        '<button id="theme" type="button" aria-label="Switch theme">◐</button></span>'
        '<span class="menu"><button id="export" type="button" aria-haspopup="true" aria-expanded="false">Export</button>'
        '<span id="export-menu" role="menu" hidden>'
        '<button id="save-svg" type="button" role="menuitem">SVG image</button>'
        '<button id="save-png" type="button" role="menuitem">PNG image</button>'
        '<button id="save-html" type="button" role="menuitem">HTML page</button>'
        "</span></span></div></header>"
        '<main><svg id="canvas" class="deps-svg" role="application" aria-label="Dependency graph">'
        '<g id="viewport"></g></svg>'
        + (
            f'<div class="notice" role="status">{escape(notice)}</div>'
            if notice
            else ""
        )
        + (
            f'<div class="notice" role="status">{escape(notes)}</div>'
            if notes and not notice
            else ""
        )
        + f'<div class="legend">{legend}</div>'
        '<aside id="card" hidden aria-live="polite"><div class="top"><span id="card-dot" class="dot"></span>'
        '<span id="card-kind" class="kicker"></span>'
        '<button id="card-close" type="button" aria-label="Close details">×</button></div>'
        '<h2 id="card-title"></h2><div id="card-body"></div>'
        '<button id="card-docs" type="button" hidden>Open documentation</button></aside></main>'
        f'<script type="application/json" id="deps-data">{_json(page_data(tree))}</script>'
        f"<script>{script}</script></body></html>\n"
    )
