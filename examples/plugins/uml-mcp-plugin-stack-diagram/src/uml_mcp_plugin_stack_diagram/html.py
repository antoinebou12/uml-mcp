"""Standalone, CSP-locked HTML page: pan, zoom, fit, themes, presets, focus and path tracing."""

from __future__ import annotations

import base64
import hashlib
import json
from html import escape
from typing import Any

from .layout import Layout
from .render import Skin, resolve_theme, svg_parts, vars_css
from .spec import Spec

_PAGE_CSS = (
    "*{box-sizing:border-box}html,body{height:100%;margin:0}"
    "body{display:flex;flex-direction:column;background:var(--bg);color:var(--ink);"
    "font:14px/1.4 system-ui,-apple-system,'Segoe UI',sans-serif}"
    "header{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px 16px;"
    "padding:10px 16px;border-bottom:1px solid var(--edge);background:var(--panel)}"
    "h1{margin:0;font-size:16px}.meta{color:var(--muted);font-size:12px}"
    ".toolbar{display:flex;flex-wrap:wrap;align-items:center;gap:6px}"
    "button,select{font:inherit;color:var(--ink);background:var(--bg);border:1px solid var(--edge);"
    "border-radius:8px;padding:5px 11px;cursor:pointer}"
    "button:hover,select:hover{border-color:var(--accent)}"
    "button:focus-visible,select:focus-visible{outline:2px solid var(--accent);outline-offset:2px}"
    "button[aria-pressed=true]{border-color:var(--accent);color:var(--accent)}"
    ".zoom{min-width:46px;text-align:center;color:var(--muted);font-size:12px}"
    "main{flex:1;min-height:0;position:relative;overflow:hidden;cursor:grab;touch-action:none}"
    "main.drag{cursor:grabbing}"
    "#stage{position:absolute;left:0;top:0;transform-origin:0 0}#stage svg{display:block}"
    ".node,.gwrap{transition:opacity .15s}.edge{transition:opacity .15s}.node{cursor:pointer}"
    ".node.sel .card,.node.sel .tile{stroke-width:2.6}"
    ".node.sel{filter:drop-shadow(0 0 7px var(--accent))}"
    "#passport{position:absolute;left:14px;top:14px;width:290px;max-height:calc(100% - 28px);overflow:auto;"
    "padding:14px;border:1px solid var(--edge);border-radius:12px;background:var(--panel);"
    "box-shadow:0 10px 30px rgba(0,0,0,.25);cursor:default}"
    "#passport[hidden]{display:none}"
    "#passport h2{margin:2px 0 4px;font-size:15px}#passport .kicker{font-size:10px;letter-spacing:.14em;"
    "color:var(--accent);text-transform:uppercase}"
    "#passport .sub{color:var(--muted);font-size:12px;margin:0 0 8px}"
    "#passport .reach{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin:8px 0}"
    "#passport .reach div{border:1px solid var(--edge);border-radius:8px;padding:6px 8px;font-size:12px;color:var(--muted)}"
    "#passport .reach b{display:block;color:var(--ink);font-size:16px}"
    "#passport ul{list-style:none;margin:4px 0 8px;padding:0}"
    "#passport li button{width:100%;text-align:left;border:0;padding:4px 6px;background:none;border-radius:6px}"
    "#passport li button:hover{background:var(--bg)}"
    "#passport .close{float:right;padding:0 8px}"
    ".hint{position:absolute;right:14px;bottom:10px;color:var(--muted);font-size:12px;pointer-events:none}"
    ".live .line{stroke-dasharray:7 7;animation:flow 1.1s linear infinite}"
    "@keyframes flow{to{stroke-dashoffset:-14}}"
    "@media (prefers-reduced-motion:reduce){.live .line{animation:none}}"
    "@media (max-width:640px){#passport{width:calc(100% - 28px)}.hint{display:none}}"
)

_SCRIPT = """(() => {
  "use strict";
  const main = document.querySelector("main"), stage = document.getElementById("stage");
  const svg = stage.querySelector("svg"), root = document.documentElement;
  const graph = JSON.parse(document.getElementById("graph").textContent);
  const W = svg.viewBox.baseVal.width, H = svg.viewBox.baseVal.height;
  let k = 1, x = 0, y = 0, drag = null, moved = 0;
  const readout = document.getElementById("zoomval");
  const apply = () => { stage.style.transform = `translate(${x}px,${y}px) scale(${k})`; readout.textContent = Math.round(k * 100) + "%"; };
  const fit = () => {
    const r = main.getBoundingClientRect();
    k = Math.min(r.width / W, r.height / H, 1.6) * 0.96;
    x = (r.width - W * k) / 2; y = (r.height - H * k) / 2; apply();
  };
  const zoom = (f, px, py) => {
    const r = main.getBoundingClientRect(), cx = px ?? r.width / 2, cy = py ?? r.height / 2;
    const nk = Math.max(0.1, Math.min(6, k * f));
    x = cx - ((cx - x) / k) * nk; y = cy - ((cy - y) / k) * nk; k = nk; apply();
  };

  // ---- graph: reach, focus and shortest path -----------------------------------------
  const nodes = new Map(graph.nodes.map((n) => [n.id, n]));
  const out = new Map(), inn = new Map();
  graph.nodes.forEach((n) => { out.set(n.id, []); inn.set(n.id, []); });
  graph.edges.forEach((e) => { out.get(e.from)?.push(e); inn.get(e.to)?.push(e); });
  const nodeEls = new Map([...svg.querySelectorAll(".node")].map((g) => [g.dataset.id, g]));
  const edgeEls = [...svg.querySelectorAll(".edge")];
  const groupEls = [...svg.querySelectorAll(".gwrap")];
  const reach = (id, next) => {
    const seen = new Set(), todo = [id];
    while (todo.length) for (const e of next.get(todo.pop()) || []) {
      const other = next === out ? e.to : e.from;
      if (!seen.has(other) && other !== id) { seen.add(other); todo.push(other); }
    }
    return seen;
  };
  const shortest = (a, b, directed) => {
    const prev = new Map([[a, null]]), queue = [a];
    while (queue.length) {
      const cur = queue.shift();
      if (cur === b) break;
      const hops = [...(out.get(cur) || []).map((e) => e.to), ...(directed ? [] : (inn.get(cur) || []).map((e) => e.from))];
      for (const nx of hops) if (!prev.has(nx)) { prev.set(nx, cur); queue.push(nx); }
    }
    if (!prev.has(b)) return null;
    const route = [];
    for (let c = b; c !== null; c = prev.get(c)) route.unshift(c);
    return route;
  };
  let selected = null;
  const passport = document.getElementById("passport");
  const show = (keepNodes, keepEdge) => {
    nodeEls.forEach((el, id) => { el.classList.toggle("dim", !keepNodes.has(id)); el.classList.toggle("sel", id === selected); });
    edgeEls.forEach((el) => el.classList.toggle("dim", !keepEdge(el.dataset.from, el.dataset.to)));
    groupEls.forEach((el) => {
      const g = graph.groups.find((q) => q.id === el.dataset.id);
      el.classList.toggle("dim", !(g && g.nodes.some((id) => keepNodes.has(id))));
    });
  };
  const clear = () => {
    selected = null;
    [...nodeEls.values(), ...edgeEls, ...groupEls].forEach((el) => el.classList.remove("dim", "sel"));
    passport.hidden = true;
  };
  const el = (tag, text, cls) => { const e = document.createElement(tag); if (text !== undefined) e.textContent = text; if (cls) e.className = cls; return e; };
  const list = (title, edges, pick) => {
    const box = document.createDocumentFragment();
    box.append(el("div", `${title} · ${edges.length}`, "kicker"));
    const ul = el("ul");
    edges.forEach((e) => {
      const li = el("li"), b = el("button", (nodes.get(pick(e)) || {}).name || pick(e));
      b.type = "button"; b.addEventListener("click", () => focus(pick(e)));
      li.append(b); ul.append(li);
    });
    box.append(ul);
    return box;
  };
  const closer = () => { const c = el("button", "×", "close"); c.type = "button"; c.setAttribute("aria-label", "Close"); c.addEventListener("click", clear); return c; };
  function focus(id) {
    const n = nodes.get(id);
    if (!n) return;
    selected = id;
    const up = reach(id, inn), down = reach(id, out), keep = new Set([id, ...up, ...down]);
    show(keep, (a, b) => keep.has(a) && keep.has(b));
    passport.replaceChildren(closer(), el("div", n.kind || "Node", "kicker"), el("h2", n.name));
    if (n.role) passport.append(el("p", n.role, "sub"));
    if (n.path) passport.append(el("p", n.path, "sub"));
    if (n.tag) passport.append(el("p", n.tag, "sub"));
    const r = el("div", undefined, "reach"), a = el("div", "Upstream"), d = el("div", "Downstream");
    a.append(el("b", String(up.size))); d.append(el("b", String(down.size))); r.append(a, d);
    passport.append(r, list("Outgoing", out.get(id), (e) => e.to), list("Incoming", inn.get(id), (e) => e.from));
    passport.hidden = false;
  }
  function trace(a, b) {
    const route = shortest(a, b, true) || shortest(a, b, false);
    if (!route) { focus(b); return; }
    const keep = new Set(route), pairs = new Set(route.slice(1).map((v, i) => route[i] + ">" + v));
    selected = b;
    show(keep, (f, t) => pairs.has(f + ">" + t) || pairs.has(t + ">" + f));
    passport.replaceChildren(closer(), el("div", "Path", "kicker"),
      el("h2", `${nodes.get(a).name} → ${nodes.get(b).name}`),
      el("p", route.map((id) => nodes.get(id).name).join(" → "), "sub"),
      el("p", `${route.length} nodes · ${route.length - 1} steps · shortest path`, "sub"));
    passport.hidden = false;
  }

  // ---- pointer: pan, zoom, click ----------------------------------------------------
  main.addEventListener("pointerdown", (e) => { if (passport.contains(e.target)) return; main.setPointerCapture(e.pointerId); main.classList.add("drag"); drag = [e.clientX, e.clientY]; moved = 0; });
  main.addEventListener("pointermove", (e) => { if (!drag) return; const dx = e.clientX - drag[0], dy = e.clientY - drag[1]; moved += Math.abs(dx) + Math.abs(dy); x += dx; y += dy; drag = [e.clientX, e.clientY]; apply(); });
  main.addEventListener("pointerup", (e) => {
    const was = drag; drag = null; main.classList.remove("drag");
    if (!was || moved > 5) return;
    const hit = document.elementsFromPoint(e.clientX, e.clientY).find((n) => n.closest && n.closest(".node"));
    const id = hit && hit.closest(".node").dataset.id;
    if (!id) { clear(); return; }
    if (e.shiftKey && selected && selected !== id) trace(selected, id); else focus(id);
  });
  main.addEventListener("pointercancel", () => { drag = null; main.classList.remove("drag"); });
  main.addEventListener("wheel", (e) => { e.preventDefault(); const r = main.getBoundingClientRect(); zoom(Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top); }, { passive: false });
  window.addEventListener("keydown", (e) => { if (e.key === "Escape") clear(); });

  // ---- toolbar -----------------------------------------------------------------------
  document.getElementById("fit").addEventListener("click", fit);
  document.getElementById("zin").addEventListener("click", () => zoom(1.2));
  document.getElementById("zout").addEventListener("click", () => zoom(1 / 1.2));
  const theme = document.getElementById("theme");
  const label = () => { theme.textContent = root.dataset.theme === "dark" ? "Light" : "Dark"; };
  theme.addEventListener("click", () => { root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark"; label(); });
  const live = document.getElementById("live");
  live.addEventListener("click", () => { const on = stage.classList.toggle("live"); live.setAttribute("aria-pressed", String(on)); });
  const preset = document.getElementById("preset");
  if (preset) preset.addEventListener("change", () => { root.dataset.preset = preset.value; });
  window.addEventListener("resize", fit);
  if (root.dataset.auto === "1" && window.matchMedia("(prefers-color-scheme: light)").matches) root.dataset.theme = "light";
  label(); fit();
  window.__diagram = { focus, trace, clear, get selected() { return selected; } };
})();"""


def _hash(text: str) -> str:
    return base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode(
        "ascii"
    )


def json_for_script(data: Any) -> str:
    text = json.dumps(data, separators=(",", ":"), ensure_ascii=True)
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def graph_of(spec: Spec, skin: Skin) -> dict[str, Any]:
    """The data the page needs for the detail panel, focus and path tracing."""
    groups = {g.id: g for g in spec.groups}

    def trail(group_id: str | None) -> list[str]:
        names: list[str] = []
        cursor = groups.get(group_id) if group_id else None
        while cursor is not None:
            names.append(cursor.name)
            cursor = groups.get(cursor.parent) if cursor.parent else None
        return names[::-1]

    def descends(group_id: str | None, ancestor: str) -> bool:
        cursor = groups.get(group_id) if group_id else None
        while cursor is not None:
            if cursor.id == ancestor:
                return True
            cursor = groups.get(cursor.parent) if cursor.parent else None
        return False

    return {
        "nodes": [
            {
                "id": n.id,
                "name": n.name,
                "role": n.role,
                "tag": n.tag,
                "path": " › ".join(trail(n.group)),
                "kind": groups[n.group].style.title() if n.group else "Node",
            }
            for n in spec.nodes
        ],
        "edges": [
            {"from": e.source, "to": e.target, "label": e.label} for e in spec.edges
        ],
        "groups": [
            {"id": g.id, "nodes": [n.id for n in spec.nodes if descends(n.group, g.id)]}
            for g in spec.groups
        ],
    }


def shell(
    *,
    title: str,
    subtitle: str,
    theme: str,
    auto: bool,
    preset: str,
    svg: str,
    css: str,
    skin: Skin,
    graph: dict[str, Any],
    meta: str,
) -> str:
    """The page around a diagram SVG. ``css`` is the diagram's own stylesheet."""
    style = _PAGE_CSS + vars_css(skin) + css
    csp = (
        "default-src 'none'; "
        f"script-src 'sha256-{_hash(_SCRIPT)}'; "
        f"style-src 'sha256-{_hash(style)}'; "
        "img-src data: blob:; base-uri 'none'; form-action 'none'"
    )
    options = "".join(
        f'<option value="{escape(name)}"{" selected" if name == preset else ""}>{escape(name.title())}</option>'
        for name in skin.presets
    )
    picker = (
        f'<select id="preset" aria-label="Preset">{options}</select>'
        if skin.presets
        else ""
    )
    preset_attr = f' data-preset="{escape(preset)}"' if preset else ""
    return (
        "<!doctype html>\n"
        f'<html lang="en" data-theme="{theme}" data-auto="{"1" if auto else "0"}"{preset_attr}>'
        '<head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta http-equiv="Content-Security-Policy" content="{escape(csp, quote=True)}">'
        f"<title>{escape(title)}</title><style>{style}</style></head><body>"
        f'<header><div><h1>{escape(title)}</h1><span class="meta">{escape(subtitle or meta)}</span></div>'
        '<div class="toolbar" role="toolbar" aria-label="Viewer controls">'
        f'{picker}<button id="live" type="button" aria-pressed="false">Live</button>'
        '<button id="zout" type="button" aria-label="Zoom out">−</button>'
        '<span id="zoomval" class="zoom">100%</span>'
        '<button id="zin" type="button" aria-label="Zoom in">+</button>'
        '<button id="fit" type="button">Fit</button>'
        '<button id="theme" type="button">Theme</button></div></header>'
        f'<main><div id="stage">{svg}</div>'
        '<aside id="passport" hidden aria-live="polite"></aside>'
        '<div class="hint">Click a node to focus · Shift+click another for the shortest path · Esc clears</div></main>'
        f'<script type="application/json" id="graph">{json_for_script(graph)}</script>'
        f"<script>{_SCRIPT}</script></body></html>\n"
    )


def page(spec: Spec, lay: Layout, skin: Skin) -> str:
    theme = resolve_theme(spec)
    svg, css = svg_parts(spec, lay, skin, theme=theme, live=True)
    return shell(
        title=spec.title,
        subtitle=spec.subtitle,
        theme=theme,
        auto=spec.theme == "auto",
        preset=spec.preset,
        svg=svg,
        css=css,
        skin=skin,
        graph=graph_of(spec, skin),
        meta=f"{skin.name} · {spec.direction} · {len(spec.nodes)} nodes",
    )
