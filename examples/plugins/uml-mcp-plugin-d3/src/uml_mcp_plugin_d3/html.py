"""The standalone HTML page around a diagram.

Safety, because the diagram source comes from a model or a user:

* the data reaches the page only as JSON in a ``<script type="application/json">`` block
  with ``<``, ``>`` and ``&`` escaped, and the runtime scripts set text with ``textContent``;
* a ``Content-Security-Policy`` allows exactly the scripts and the two stylesheets this page
  contains (by SHA-256) plus D3 itself, forbids every network request, and sets
  ``base-uri``/``form-action`` to ``'none'``;
* D3 is either loaded from a pinned jsDelivr URL with a Subresource Integrity hash, or
  inlined from the copy vendored in this package (offline, about 280 KB larger).
"""

from __future__ import annotations

import base64
import hashlib
import json
from functools import cache
from html import escape
from importlib.resources import files
from typing import Any

from . import force as force_mod
from .layout import (
    GRID_CELL,
    GRID_MARGIN,
    GROUP_HEADER,
    GROUP_PAD,
    NODE_GAP,
    Layout,
)
from .spec import ArchSpec, ForceSpec
from .svg import architecture_svg
from .theme import chrome_css, diagram_css

D3_VERSION = "7.9.0"
D3_FILE = f"d3.v{D3_VERSION}.min.js"
D3_CDN_URL = f"https://cdn.jsdelivr.net/npm/d3@{D3_VERSION}/dist/d3.min.js"
#: SHA-256 of the vendored file (the same bytes as the npm package's dist/d3.min.js)
D3_SHA256 = "f2094bbf6141b359722c4fe454eb6c4b0f0e42cc10cc7af921fc158fceb86539"


@cache
def asset(name: str) -> str:
    return (
        files("uml_mcp_plugin_d3").joinpath("assets", name).read_text(encoding="utf-8")
    )


def _sha256_b64(text: str) -> str:
    return base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode(
        "ascii"
    )


def d3_sri() -> str:
    raw = files("uml_mcp_plugin_d3").joinpath("assets", D3_FILE).read_bytes()
    return "sha384-" + base64.b64encode(hashlib.sha384(raw).digest()).decode("ascii")


def json_for_script(data: Any) -> str:
    """JSON that is safe inside a ``<script>`` element (no ``</script>``, no ``<!--``)."""
    text = json.dumps(data, separators=(",", ":"), ensure_ascii=True)
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _toolbar(kind: str) -> str:
    """The buttons above the diagram: theme, flow, fit, reset and the Export menu."""
    extra = (
        '<button id="pause" type="button">Pause</button>'
        if kind == "force"
        else '<button id="flow" type="button" aria-pressed="false">Flow</button>'
    )
    return (
        '<div class="bar">'
        '<button id="theme" type="button" title="Switch between light and dark">Theme</button>'
        f"{extra}"
        '<button id="fit" type="button">Fit</button>'
        '<button id="reset" type="button">Reset</button>'
        '<details class="menu"><summary>Export</summary><div class="items">'
        '<button id="save" type="button">Save SVG</button>'
        '<button id="png" type="button">Save PNG</button>'
        '<button id="html" type="button">Save HTML</button>'
        "</div></details></div>"
    )


def _page(
    *,
    title: str,
    theme: str,
    kind: str,
    svg: str,
    data: dict[str, Any],
    runtime: list[str],
    hint: str,
    d3_source: str,
) -> str:
    script = "\n".join(runtime)
    hashes = [f"'sha256-{_sha256_b64(script)}'"]
    if d3_source == "inline":
        d3_js = asset(D3_FILE)
        hashes.append(f"'sha256-{_sha256_b64(d3_js)}'")
        d3_tag = f"<script>{d3_js}</script>"
    else:
        hashes.append(D3_CDN_URL)
        d3_tag = f'<script src="{D3_CDN_URL}" integrity="{d3_sri()}" crossorigin="anonymous"></script>'
    chrome, diagram = chrome_css(), diagram_css()
    csp = (
        "default-src 'none'; "
        f"script-src {' '.join(hashes)}; "
        f"style-src 'sha256-{_sha256_b64(chrome)}' 'sha256-{_sha256_b64(diagram)}'; "
        "img-src data:; base-uri 'none'; form-action 'none'"
    )
    heading = escape(title or "Diagram")
    return (
        "<!doctype html>\n"
        f'<html lang="en" class="{theme}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta http-equiv="Content-Security-Policy" content="{escape(csp, quote=True)}">'
        f'<title>{heading}</title><style id="chrome-css">{chrome}</style>'
        f'<style id="diagram-css">{diagram}</style></head>'
        f"<body><header><h1>{heading}</h1>{_toolbar(kind)}</header>"
        f"<main>{svg}"
        '<div class="zoom bar"><button id="zout" type="button" title="Zoom out">−</button>'
        '<output id="zlevel">100%</output>'
        '<button id="zin" type="button" title="Zoom in">+</button></div>'
        f'<div class="hint">{escape(hint)}</div></main>'
        '<div id="tip" role="tooltip"></div>'
        f'<script type="application/json" id="spec">{json_for_script(data)}</script>'
        f"{d3_tag}<script>{script}</script></body></html>\n"
    )


def architecture_page(layout: Layout, spec: ArchSpec, *, d3_source: str = "cdn") -> str:
    data = {
        "kind": "architecture",
        "title": spec.title or "",
        "direction": layout.direction,
        "consts": {
            "groupPad": GROUP_PAD,
            "groupHeader": GROUP_HEADER,
            "gridCell": GRID_CELL,
            "gridMargin": GRID_MARGIN,
            "nodeGap": NODE_GAP,
        },
        "nodes": [
            {
                "id": b.id,
                "x": b.x,
                "y": b.y,
                "w": b.w,
                "h": b.h,
                "group": b.group,
                "label": b.label,
                "sub": b.sub,
                "note": b.note,
            }
            for b in layout.boxes
        ],
        "groups": [{"id": g.id, "parent": g.parent} for g in layout.groups],
        "edges": [
            {
                "id": e.id,
                "from": e.source,
                "to": e.target,
                "srcOffset": list(e.src_offset),
                "dstOffset": list(e.dst_offset),
                "srcDir": e.src_dir,
                "dstDir": e.dst_dir,
                "points": [list(p) for p in e.points],
                "labelWidth": e.label_width,
            }
            for e in layout.edges
        ],
    }
    return _page(
        title=spec.title or "Architecture",
        theme=spec.theme,
        kind="architecture",
        svg=architecture_svg(layout, title=None, theme=spec.theme, page=True),
        data=data,
        runtime=[asset("common.js"), asset("router.js"), asset("arch.js")],
        hint="Scroll to zoom, drag the background to pan, drag a box to move it (arrows re-route)",
        d3_source=d3_source,
    )


def force_page(
    model: force_mod.ForceModel, spec: ForceSpec, *, d3_source: str = "cdn"
) -> str:
    data = {
        "kind": "force",
        "title": spec.title or "",
        "directed": spec.directed,
        "charge": spec.charge,
        "distance": spec.distance,
        "nodes": model.nodes,
        "links": model.links,
        "legend": model.legend,
    }
    return _page(
        title=spec.title or "Force-directed graph",
        theme=spec.theme,
        kind="force",
        svg=force_mod.force_svg(model, spec, page=True),
        data=data,
        runtime=[asset("common.js"), asset("force.js")],
        hint="Scroll to zoom, drag the background to pan, drag a node to pin it, double-click to release",
        d3_source=d3_source,
    )
