"""The simulator page: the statechart, the enabled events, a step log and a detail card.

Safety, because the source comes from a model or a user: the machine reaches the page
only as JSON in a ``<script type="application/json">`` block with ``<``, ``>`` and ``&``
escaped; the script sets text with ``textContent``; a Content-Security-Policy allows only
this page's own script and stylesheet (by SHA-256), no network at all, and sets
``base-uri`` and ``form-action`` to ``'none'``.
"""

from __future__ import annotations

import base64
import hashlib
import json
from functools import cache
from html import escape
from importlib.resources import files
from typing import Any

from .layout import Layout
from .model import Machine, reachable
from .svg import PALETTES, css, drawing, static_css


@cache
def asset(name: str) -> str:
    return (
        files("uml_mcp_plugin_statechart")
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


def _vars(theme: str) -> str:
    return ";".join(f"--{k}:{v}" for k, v in PALETTES[theme].items())


PAGE_CSS = (
    "*{box-sizing:border-box}html,body{height:100%;margin:0}"
    "body{display:flex;flex-direction:column;background:var(--bg);color:var(--ink);"
    "font:14px/1.4 system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;overflow:hidden}"
    "header{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:6px 14px;"
    "padding:8px 14px;border-bottom:1px solid var(--line);background:var(--panel)}"
    "h1{margin:0;font-size:16px}.meta{color:var(--muted);font-size:12px;margin-left:8px}"
    ".toolbar{display:flex;flex-wrap:wrap;align-items:center;gap:5px}"
    "button{font:inherit;font-size:13px;color:var(--ink);background:var(--bg);border:1px solid var(--line);"
    "border-radius:8px;padding:4px 10px;cursor:pointer}"
    "button:hover:not(:disabled){border-color:var(--accent)}"
    "button:disabled{opacity:.45;cursor:default}"
    "button:focus-visible,summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px}"
    ".zoom{min-width:42px;text-align:center;color:var(--muted);font-size:12px}"
    "details.menu{position:relative}details.menu summary{list-style:none;cursor:pointer;font-size:13px;"
    "border:1px solid var(--line);border-radius:8px;padding:4px 10px;background:var(--bg)}"
    "details.menu summary::-webkit-details-marker{display:none}"
    "details.menu .items{position:absolute;right:0;top:calc(100% + 4px);z-index:5;display:grid;gap:4px;"
    "padding:6px;background:var(--panel);border:1px solid var(--line);border-radius:10px;"
    "box-shadow:0 10px 30px rgba(0,0,0,.2);min-width:120px}"
    "#sim{display:grid;grid-template-columns:auto 1fr;gap:4px 10px;align-items:center;padding:7px 14px;"
    "border-bottom:1px solid var(--line);background:var(--panel)}"
    "#sim .lbl{font-size:10.5px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}"
    "#events,#active{display:flex;flex-wrap:wrap;gap:5px;min-width:0;max-height:66px;overflow:auto}"
    "#events .ev{border-color:var(--can);color:var(--can);font-weight:650}"
    "#events .ev:hover{background:var(--can);color:var(--panel)}"
    "#events .g,.out .g{color:var(--guard);font-weight:500}"
    "#events .none{color:var(--muted);font-size:13px}"
    ".chip{display:inline-block;padding:2px 9px;border:1px solid var(--line);border-radius:999px;"
    "font-size:12px;background:var(--bg);color:var(--ink)}"
    "#active .chip{border-color:var(--accent);color:var(--accent)}"
    ".row2{flex:1;min-height:0;display:flex}"
    "main{flex:1;min-width:0;position:relative;overflow:hidden;cursor:grab;touch-action:none}"
    "main.drag{cursor:grabbing}"
    "#stage{position:absolute;left:0;top:0;transform-origin:0 0;user-select:none;-webkit-user-select:none}"
    "#stage svg{display:block}"
    ".sc-heading{display:none}"
    ".sc-state text,.sc-label text{pointer-events:none}"
    ".sc-state{cursor:pointer}.sc-state .sc-box{transition:fill .25s,stroke .25s,stroke-width .25s}"
    ".sc-state.on>.sc-box{stroke:var(--accent);stroke-width:2.6}"
    ".sc-atomic.on>.sc-box{fill:var(--activefill)}"
    ".sc-region.on>.sc-box{stroke:none}"
    ".sc-final.on .sc-core{fill:var(--accent)}"
    ".sc-history.on>.sc-box{fill:var(--activefill)}"
    ".sc-state.sel>.sc-box{stroke-dasharray:5 3}"
    ".sc-tr.can .sc-line{stroke:var(--can);stroke-width:2}"
    ".sc-label{cursor:pointer}.sc-label.can .sc-lbg{stroke:var(--can);stroke-width:1.6}"
    ".sc-label.can:hover .sc-lbg{fill:var(--can)}.sc-label.can:hover .sc-ltext,.sc-label.can:hover tspan{fill:var(--panel)}"
    ".sc-tr.fire .sc-line{stroke:var(--accent);stroke-width:3;stroke-dasharray:8 6;animation:sc-flow .9s linear}"
    ".sc-label.fire .sc-lbg{fill:var(--accent);stroke:var(--accent)}.sc-label.fire .sc-ltext,.sc-label.fire tspan{fill:var(--panel)}"
    ".sc-token{fill:var(--accent);stroke:var(--panel);stroke-width:2;pointer-events:none}"
    "@keyframes sc-flow{to{stroke-dashoffset:-42}}"
    "@media (prefers-reduced-motion:reduce){.sc-tr.fire .sc-line{animation:none}.sc-state .sc-box{transition:none}}"
    "#card{position:absolute;right:12px;top:12px;width:280px;max-width:calc(100% - 24px);max-height:calc(100% - 24px);"
    "overflow:auto;padding:12px 14px;border:1px solid var(--line);border-radius:12px;background:var(--panel);"
    "box-shadow:0 10px 30px rgba(0,0,0,.25);cursor:default;z-index:3}"
    "#card[hidden]{display:none}"
    "#card .kicker{font-size:10px;letter-spacing:.14em;color:var(--accent);text-transform:uppercase;font-weight:700}"
    "#card h2{margin:2px 0;font-size:16px}#card .sub{color:var(--muted);font-size:12px}"
    "#card .chips{display:flex;gap:4px;margin:8px 0}"
    "#card .chip.on{border-color:var(--accent);color:var(--accent)}#card .chip.warn{border-color:var(--guard);color:var(--guard)}"
    "#card .desc{margin:6px 0;font-size:13px}"
    "#card .h{margin:10px 0 3px;font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);font-weight:700}"
    "#card ul{list-style:none;margin:0;padding:0;display:grid;gap:3px}"
    "#card li.act{font-size:13px;font-family:ui-monospace,SFMono-Regular,Consolas,monospace}"
    "#card .out{width:100%;text-align:left;font-size:12.5px}"
    "#card .out.can{border-color:var(--can)}#card .out.can b{color:var(--can)}"
    "#card .out .to,#card .out .a{color:var(--muted)}"
    "#card .close{float:right;padding:0 8px;margin-left:6px}"
    "#logbox{width:280px;flex:none;border-left:1px solid var(--line);background:var(--panel);display:flex;"
    "flex-direction:column;min-height:0}"
    "#logbox summary{padding:8px 12px;font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;"
    "color:var(--muted);cursor:pointer}"
    "#log{margin:0;padding:0 12px 10px 34px;overflow:auto;font-size:12.5px;flex:1}"
    "#log li{margin:0 0 6px}#log li.last b{color:var(--accent)}#log .to{color:var(--ink)}"
    "#log .acts{color:var(--muted);font-size:11.5px}"
    "#logbox:not([open]){width:auto}"
    "#logbox .ctx{padding:0 12px 8px;font-size:12px;color:var(--muted)}"
    "#logbox pre{font-size:11.5px;overflow:auto;margin:4px 0;color:var(--ink)}"
    ".statusbar{display:flex;gap:10px;align-items:center;padding:4px 14px;border-top:1px solid var(--line);"
    "background:var(--panel);font-size:12px;color:var(--muted);min-height:24px}"
    "#status{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}"
    "#warn{color:var(--guard);font-weight:700}"
    "@media (max-width:760px){.row2{flex-direction:column}"
    "#logbox{width:auto;border-left:0;border-top:1px solid var(--line);max-height:34%}"
    "#logbox summary{padding:5px 12px}.meta{display:none}}"
    "@media (max-height:480px){header{padding:4px 10px}#sim{padding:4px 10px}"
    "#events,#active{max-height:58px}}"
    # inside the MCP App the viewer has its own title bar
    ':root[data-embedded="1"] h1,:root[data-embedded="1"] .meta{display:none}'
    ':root[data-embedded="1"] header{padding:4px 10px}'
)


def _style() -> str:
    live = {k: f"var(--{k})" for k in PALETTES["light"]}
    return (
        f":root{{{_vars('light')};color-scheme:light}}"
        f":root[data-theme=dark]{{{_vars('dark')};color-scheme:dark}}"
        + PAGE_CSS
        + css(live)
    )


def machine_data(machine: Machine, warnings: list[str]) -> dict[str, Any]:
    seen = reachable(machine)
    states = {}
    for st in machine.states.values():
        done = next((t.id for t in st.transitions if t.kind == "done"), None)
        states[st.id] = {
            "key": st.key,
            "name": st.name if st.id else machine.title,
            "parent": st.parent,
            "type": st.type,
            "depth": st.depth,
            "initial": st.initial,
            "children": st.children,
            "entry": st.entry,
            "exit": st.exit,
            "description": st.description,
            "history": st.history,
            "historyTarget": st.history_target,
            "transitions": [t.id for t in st.transitions],
            "done": done,
            "unreachable": bool(st.id) and st.id not in seen,
        }
    return {
        "id": machine.id,
        "title": machine.title,
        "context": machine.context,
        "warnings": warnings,
        "states": states,
        "transitions": {
            t.id: {
                "id": t.id,
                "source": t.source,
                "event": t.event,
                "targets": t.targets,
                "guard": t.guard,
                "actions": t.actions,
                "kind": t.kind,
                "label": t.label,
            }
            for t in machine.transitions
        },
    }


def page(machine: Machine, lay: Layout, warnings: list[str]) -> str:
    script = asset("sim.js")
    style = _style()
    csp = (
        "default-src 'none'; "
        f"script-src 'sha256-{_hash(script)}'; "
        f"style-src 'sha256-{_hash(style)}'; "
        "img-src data: blob:; base-uri 'none'; form-action 'none'"
    )
    theme = "dark" if machine.theme == "dark" else "light"
    auto = "1" if machine.theme == "auto" else "0"
    title = escape(machine.title)
    count = len([s for s in machine.states.values() if s.id])
    meta = f"{count} states · {len(machine.transitions)} transitions"
    warn_list = "\n".join(warnings)
    context = (
        '<details class="ctx"><summary>Context</summary>'
        f"<pre>{escape(json.dumps(machine.context, indent=2, ensure_ascii=False))}</pre></details>"
        if machine.context is not None
        else ""
    )
    export_css = {"light": static_css("light"), "dark": static_css("dark")}
    return (
        "<!doctype html>\n"
        f'<html lang="en" data-theme="{theme}" data-auto="{auto}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta http-equiv="Content-Security-Policy" content="{escape(csp, quote=True)}">'
        f"<title>{title}</title><style>{style}</style></head><body>"
        f'<header><div class="ident"><h1>{title}<span class="meta">{escape(meta)}</span></h1></div>'
        '<div class="toolbar" role="toolbar" aria-label="Simulator controls">'
        '<button id="undo" type="button" title="Undo the last step (Ctrl+Z)">Undo</button>'
        '<button id="reset" type="button" title="Back to the initial state">Reset</button>'
        '<button id="zout" type="button" aria-label="Zoom out">−</button>'
        '<span id="zoomval" class="zoom">100%</span>'
        '<button id="zin" type="button" aria-label="Zoom in">+</button>'
        '<button id="fit" type="button">Fit</button>'
        '<button id="theme" type="button">Theme</button>'
        '<details class="menu"><summary>Export</summary><div class="items">'
        '<button id="save-svg" type="button">Save SVG</button>'
        '<button id="save-png" type="button">Save PNG</button>'
        '<button id="save-html" type="button">Save HTML</button>'
        "</div></details></div></header>"
        '<section id="sim" aria-label="Simulator">'
        '<span class="lbl">Events</span><div id="events" role="group" aria-label="Enabled events"></div>'
        '<span class="lbl">Active</span><div id="active" aria-live="polite"></div></section>'
        '<div class="row2"><main>'
        f'<div id="stage">{drawing(machine, lay, theme=theme)}</div>'
        '<aside id="card" hidden aria-live="polite"></aside></main>'
        '<details id="logbox" open><summary>Step log · <span id="stepcount">0</span></summary>'
        f'<ol id="log"></ol>{context}</details></div>'
        '<div class="statusbar"><span id="status" role="status"></span>'
        f'<span id="warn" title="{escape(warn_list, quote=True)}"></span></div>'
        f'<script type="application/json" id="machine">{json_for_script(machine_data(machine, warnings))}</script>'
        f'<script type="application/json" id="export-css">{json_for_script(export_css)}</script>'
        f"<script>{script}</script></body></html>\n"
    )
