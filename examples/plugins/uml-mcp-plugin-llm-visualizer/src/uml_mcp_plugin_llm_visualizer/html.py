"""Standalone, CSP-locked HTML page for the canvas visualizer."""

from __future__ import annotations

import base64
import hashlib
import json
from functools import cache
from html import escape
from importlib.resources import files
from typing import Any

from .model import LLMSpec


@cache
def asset(name: str) -> str:
    return (
        files("uml_mcp_plugin_llm_visualizer")
        .joinpath("assets", name)
        .read_text(encoding="utf-8")
    )


def _hash(text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return base64.b64encode(digest).decode("ascii")


def json_for_script(data: Any) -> str:
    text = json.dumps(data, separators=(",", ":"), ensure_ascii=True)
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def page(spec: LLMSpec, *, initial_mode: str) -> str:
    runtime = asset("viewer.js")
    style = asset("viewer.css")
    csp = (
        "default-src 'none'; "
        f"script-src 'sha256-{_hash(runtime)}'; "
        f"style-src 'sha256-{_hash(style)}'; "
        "img-src data: blob:; base-uri 'none'; form-action 'none'"
    )
    title = escape(spec.title)
    subtitle = (
        f'<p class="subtitle">{escape(spec.subtitle)}</p>' if spec.subtitle else ""
    )
    data = spec.as_dict() | {"initialMode": initial_mode}
    return (
        "<!doctype html>\n"
        f'<html lang="en" class="{spec.theme}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta http-equiv="Content-Security-Policy" content="{escape(csp, quote=True)}">'
        f"<title>{title}</title><style>{style}</style></head><body>"
        '<header><div class="identity"><span class="eyebrow">LLM VISUALIZER</span>'
        f"<h1>{title}</h1>{subtitle}</div>"
        '<div class="toolbar" role="toolbar" aria-label="Viewer controls">'
        '<div class="segmented"><button id="mode-2d" type="button">2D</button>'
        '<button id="mode-3d" type="button">3D</button></div>'
        '<button id="reset" type="button">Reset view</button>'
        '<button id="theme" type="button">Theme</button></div></header>'
        '<main><section class="stage" aria-label="Interactive LLM architecture">'
        '<canvas id="scene" tabindex="0" aria-label="LLM architecture canvas"></canvas>'
        '<p id="hint" class="hint"></p></section>'
        '<aside><div><span class="eyebrow">LAYERS</span><nav id="layers" '
        'aria-label="Model layers"></nav></div><section id="inspector" aria-live="polite">'
        '<span class="eyebrow">INSPECTOR</span><h2 id="inspect-title">Select a layer</h2>'
        '<dl><div><dt>Kind</dt><dd id="inspect-kind">—</dd></div>'
        '<div><dt>Shape</dt><dd id="inspect-shape">—</dd></div>'
        '<div><dt>Repeat</dt><dd id="inspect-repeat">—</dd></div></dl>'
        '<p id="inspect-note">Click a layer in the scene or the list.</p></section></aside></main>'
        '<footer><output id="status" aria-live="polite"></output>'
        "<span>Drag to orbit or pan · wheel to zoom · click to inspect</span></footer>"
        f'<script type="application/json" id="spec">{json_for_script(data)}</script>'
        f"<script>{runtime}</script></body></html>\n"
    )
