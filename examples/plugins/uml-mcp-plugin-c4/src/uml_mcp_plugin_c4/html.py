"""The standalone drill-down page.

Safety, because the model comes from a model or a user: every view is SVG built here with
escaped text, the data reaches the page only as JSON in a ``<script type="application/json">``
block with ``<``, ``>`` and ``&`` escaped, the script sets text with ``textContent``, and a
Content-Security-Policy allows exactly the one script and stylesheet (by SHA-256) with no
network access at all.
"""

from __future__ import annotations

import base64
import hashlib
import json
from functools import cache
from html import escape
from importlib.resources import files
from typing import Any

from .model import Element, Model
from .svg import DARK, LIGHT, css, view_svg
from .views import all_views, drill_key, home_view, type_line, view_key


@cache
def asset(name: str) -> str:
    return (
        files("uml_mcp_plugin_c4").joinpath("assets", name).read_text(encoding="utf-8")
    )


def _hash(text: str) -> str:
    return base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode(
        "ascii"
    )


def json_for_script(data: Any) -> str:
    text = json.dumps(data, separators=(",", ":"), ensure_ascii=True)
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def docs_link(item: Element) -> str | None:
    """The element's own ``docs`` URL, else the official docs of its ``service``."""
    if item.docs:
        return item.docs
    if not item.service:
        return None
    from uml_mcp_plugin_d3.docs import docs_url

    provider = item.service.partition(":")[0] if ":" in item.service else ""
    return docs_url(item.service, provider, item.technology or item.name)


_KIND = {
    "db": "Database",
    "queue": "Queue",
    "storage": "Storage",
    "function": "Function",
    "web": "Web app",
    "app": "Application",
}


def _kicker(item: Element) -> str:
    level = {
        "person": "Person",
        "system": "Software system",
        "container": "Container",
        "component": "Component",
    }[item.level]
    extra = [_KIND[item.kind]] if item.level == "container" else []
    if item.external:
        extra.append("External")
    return " · ".join([level, *extra])


def page_data(model: Model, views: dict) -> dict[str, Any]:
    return {
        "title": model.title,
        "start": view_key(model, model.level, model.focus),
        "select": model.focus if model.level == "context" else None,
        "css": {"light": css("light"), "dark": css("dark")},
        "background": {"light": LIGHT["bg"], "dark": DARK["bg"]},
        "elements": {
            i: {
                "name": e.name,
                "level": e.level,
                "kicker": _kicker(e),
                "type": type_line(e),
                "description": e.description,
                "technology": e.technology,
                "parent": e.parent,
                "drill": drill_key(e),
                "home": home_view(model, i),
                "docs": docs_link(e),
            }
            for i, e in model.elements.items()
        },
        "relations": [
            {
                "from": r.source,
                "to": r.target,
                "label": r.label,
                "technology": r.technology,
                "async": r.is_async,
            }
            for r in model.relations
        ],
        "views": {
            key: {
                "title": v.title,
                "level": v.level,
                "focus": v.focus,
                "crumbs": [list(c) for c in v.crumbs],
                "edges": {
                    e.id: {"from": e.source, "to": e.target, "members": e.members}
                    for e in v.edges
                },
            }
            for key, v in views.items()
        },
    }


def page(model: Model) -> str:
    directions = ("TB", "LR") if model.direction == "auto" else (model.direction,)
    layouts = {d: all_views(model, d) for d in directions}
    views = layouts[directions[0]]
    script = asset("page.js")
    style = (
        asset("page.css")
        + css("light", ":root.light .c4")
        + css("dark", ":root.dark .c4")
    )
    csp = (
        "default-src 'none'; "
        f"script-src 'sha256-{_hash(script)}'; "
        f"style-src 'sha256-{_hash(style)}'; "
        "img-src data: blob:; base-uri 'none'; form-action 'none'"
    )
    theme = "light" if model.theme == "light" else "dark"
    title = escape(model.title)
    drawings = "".join(
        view_svg(model, v, theme, page=True).replace(
            'class="c4 ', f'data-dir="{d}" class="view c4 ', 1
        )
        for d, vs in layouts.items()
        for v in vs.values()
    )
    return (
        "<!doctype html>\n"
        f'<html lang="en" class="{theme}" data-auto="{"1" if model.theme == "auto" else "0"}">'
        '<head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta http-equiv="Content-Security-Policy" content="{escape(csp, quote=True)}">'
        f"<title>{title}</title><style>{style}</style></head><body>"
        f'<header><h1>{title}</h1><nav id="crumbs" class="crumbs" aria-label="C4 level"></nav>'
        '<div class="bar" role="toolbar" aria-label="Viewer controls">'
        '<button id="up" type="button" title="Up one level (Esc)" aria-label="Up one level">↑</button>'
        '<button id="zout" type="button" aria-label="Zoom out">−</button>'
        '<button id="zin" type="button" aria-label="Zoom in">+</button>'
        '<button id="fit" type="button">Fit</button>'
        '<button id="theme" type="button" title="Switch between light and dark">Theme</button>'
        '<details class="menu"><summary>Export</summary><div class="items">'
        '<button id="export-svg" type="button">Save SVG</button>'
        '<button id="export-png" type="button">Save PNG</button>'
        '<button id="export-html" type="button">Save HTML</button>'
        "</div></details></div></header>"
        f"<main>{drawings}"
        '<aside id="details" class="details" hidden aria-live="polite"></aside>'
        '<div class="hint">Click a system or container to open it · Shift+click for details · '
        "Esc goes up</div></main>"
        '<output id="status" class="sr-only" aria-live="polite"></output>'
        f'<script type="application/json" id="model">{json_for_script(page_data(model, views))}</script>'
        f"<script>{script}</script></body></html>\n"
    )
