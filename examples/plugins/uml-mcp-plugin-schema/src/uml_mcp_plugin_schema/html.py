"""The interactive page: a CSP-locked standalone HTML file with no network access.

Pan, zoom and fit; click a table to focus it and its joins and open its detail card;
hover a column to trace its foreign-key path; search tables and columns; light and dark;
export SVG, PNG or the page itself. Inside the MCP App viewer the page drops its own title
(the viewer has one) and hands exports to the host.
"""

from __future__ import annotations

import base64
import hashlib
import json
from html import escape
from typing import Any

from .layout import Layout
from .model import Schema
from .svg import PALETTES, css, palette_vars, svg_parts

_PAGE_CSS = (
    "*{box-sizing:border-box}html,body{height:100%;margin:0}"
    "body{display:flex;flex-direction:column;background:var(--bg);color:var(--ink);"
    "font:14px/1.4 Inter,ui-sans-serif,system-ui,-apple-system,'Segoe UI',sans-serif}"
    "header{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px 14px;"
    "padding:9px 14px;border-bottom:1px solid var(--stroke);background:var(--card)}"
    ".ident{min-width:0}h1{margin:0;font-size:16px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}"
    ".meta{color:var(--muted);font-size:12px}"
    ".toolbar{display:flex;flex-wrap:wrap;align-items:center;gap:6px}"
    "button,input,summary{font:inherit;color:var(--ink);background:var(--bg);border:1px solid var(--stroke);"
    "border-radius:8px;padding:4px 10px;cursor:pointer}"
    "input{cursor:text;width:190px}input::placeholder{color:var(--muted)}"
    "button:hover,summary:hover,input:hover{border-color:var(--accent)}"
    "button:focus-visible,input:focus-visible,summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px}"
    ".zoom{min-width:44px;text-align:center;color:var(--muted);font-size:12px}"
    ".search{position:relative}"
    "#results{position:absolute;z-index:5;top:calc(100% + 4px);left:0;min-width:240px;max-height:260px;overflow:auto;"
    "margin:0;padding:4px;list-style:none;background:var(--card);border:1px solid var(--stroke);border-radius:10px;"
    "box-shadow:0 10px 28px rgba(0,0,0,.22)}#results[hidden]{display:none}"
    "#results button{display:block;width:100%;text-align:left;border:0;background:none;padding:5px 8px}"
    "#results button:hover,#results button.cur{background:var(--head)}"
    "#results .in{color:var(--muted);font-size:12px}"
    "details.menu{position:relative}details.menu summary{list-style:none}"
    "details.menu summary::-webkit-details-marker{display:none}"
    "details.menu .items{position:absolute;right:0;z-index:5;top:calc(100% + 4px);display:grid;gap:2px;padding:4px;"
    "background:var(--card);border:1px solid var(--stroke);border-radius:10px;box-shadow:0 10px 28px rgba(0,0,0,.22)}"
    "details.menu .items button{border:0;background:none;text-align:left;white-space:nowrap}"
    "details.menu .items button:hover{background:var(--head)}"
    "main{flex:1;min-height:0;position:relative;overflow:hidden;cursor:grab;touch-action:none}"
    "main.drag{cursor:grabbing}"
    "#stage{position:absolute;left:0;top:0;transform-origin:0 0;user-select:none;-webkit-user-select:none}"
    "#stage svg{display:block}.table{cursor:pointer}.col{cursor:default}"
    "#detail{position:absolute;right:12px;top:12px;width:300px;max-height:calc(100% - 24px);overflow:auto;"
    "padding:12px 14px;border:1px solid var(--stroke);border-radius:12px;background:var(--card);"
    "box-shadow:0 12px 32px rgba(0,0,0,.25);cursor:default}#detail[hidden]{display:none}"
    "#detail .kicker{font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent)}"
    "#detail h2{margin:2px 0 4px;font-size:16px;word-break:break-word}"
    "#detail .note{margin:0 0 8px;color:var(--muted);font-size:12.5px}"
    "#detail .close{float:right;padding:0 8px;border:0;font-size:18px;line-height:1.2;background:none}"
    "#detail table{width:100%;border-collapse:collapse;font-size:12.5px;margin:4px 0 8px}"
    "#detail td{padding:3px 4px;border-top:1px solid var(--stroke);vertical-align:top}"
    "#detail td.t{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:11px;color:var(--type)}"
    "#detail .k{color:var(--pk);font-weight:700}#detail .f{color:var(--fk);font-weight:700}"
    "#detail .b{display:inline-block;margin-left:4px;padding:0 5px;border-radius:4px;background:var(--badge);"
    "color:var(--muted);font-size:10px;font-weight:700}"
    "#detail .h{margin:8px 0 2px;font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}"
    "#detail .link{display:block;width:100%;text-align:left;border:0;background:none;padding:4px 6px;border-radius:6px;font-size:12.5px}"
    "#detail .link:hover{background:var(--head)}#detail .via{color:var(--muted);font-size:11.5px}"
    ".hint{position:absolute;left:12px;bottom:8px;color:var(--muted);font-size:12px;pointer-events:none}"
    ".sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}"
    "@media (max-width:700px){#detail{left:8px;right:8px;top:auto;bottom:8px;width:auto;max-height:55%}"
    ".hint{display:none}input{width:130px}}"
    # inside the MCP App the viewer already shows a title: keep only the toolbar
    ':root[data-embedded="1"] header{padding:5px 8px}'
    ':root[data-embedded="1"] .ident{display:none}'
    ':root[data-embedded="1"] button,:root[data-embedded="1"] input,:root[data-embedded="1"] summary'
    "{padding:3px 8px;font-size:13px}"
)

_SCRIPT = r"""(() => {
  "use strict";
  const root = document.documentElement, main = document.querySelector("main");
  const stage = document.getElementById("stage"), svg = stage.querySelector("svg");
  const data = JSON.parse(document.getElementById("schema-data").textContent);
  const exportCss = JSON.parse(document.getElementById("export-css").textContent);
  const W = svg.viewBox.baseVal.width, H = svg.viewBox.baseVal.height;
  const embedded = window.self !== window.top;
  if (embedded) root.dataset.embedded = "1";
  if (root.dataset.auto === "1") root.dataset.theme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  let k = 1, x = 0, y = 0, drag = null, moved = 0, fitted = true, bridge = false;
  const readout = document.getElementById("zoomval");
  const apply = () => { stage.style.transform = `translate(${x}px,${y}px) scale(${k})`; readout.textContent = Math.round(k * 100) + "%"; };
  const fit = () => {
    const r = main.getBoundingClientRect();
    k = Math.max(0.08, Math.min(r.width / W, r.height / H, 1.4) * 0.97);
    x = (r.width - W * k) / 2; y = (r.height - H * k) / 2; fitted = true; apply();
  };
  const zoom = (f, px, py) => {
    const r = main.getBoundingClientRect(), cx = px ?? r.width / 2, cy = py ?? r.height / 2;
    const nk = Math.max(0.08, Math.min(5, k * f));
    x = cx - ((cx - x) / k) * nk; y = cy - ((cy - y) / k) * nk; k = nk; fitted = false; apply();
  };

  // ---- the model ------------------------------------------------------------------
  const tables = new Map(data.tables.map((t) => [t.name, t]));
  const tableEls = new Map([...svg.querySelectorAll(".table")].map((g) => [g.dataset.table, g]));
  const relEls = [...svg.querySelectorAll(".rel")];
  const groupEls = [...svg.querySelectorAll(".group")];
  const colEl = (table, col) => [...(tableEls.get(table)?.querySelectorAll(".col") || [])].find((c) => c.dataset.col === col);
  const rels = data.relations;
  const lower = (s) => String(s).toLowerCase();
  let selected = null;

  const clearMarks = () => svg.querySelectorAll(".dim,.on,.hl").forEach((e) => e.classList.remove("dim", "on", "hl"));
  const detail = document.getElementById("detail");
  const el = (tag, text, cls) => { const e = document.createElement(tag); if (text !== undefined) e.textContent = text; if (cls) e.className = cls; return e; };

  function center(name) {
    const g = tableEls.get(name);
    if (!g) return;
    const b = g.getBBox(), r = main.getBoundingClientRect();
    const narrow = r.width < 700, room = narrow || detail.hidden ? r.width : r.width - 320;
    const visibleH = narrow && !detail.hidden ? r.height * 0.45 : r.height;
    if (k < 0.55) k = Math.min(0.9, Math.max(k, Math.min(room / (b.width + 160), visibleH / (b.height + 120))));
    x = room / 2 - (b.x + b.width / 2) * k; y = visibleH / 2 - (b.y + b.height / 2) * k; fitted = false; apply();
  }

  function focus(name, opts = {}) {
    const t = tables.get(name);
    if (!t) return;
    selected = name;
    clearMarks();
    const keep = new Set([name]);
    rels.forEach((r) => { if (r.from === name || r.to === name) { keep.add(r.from); keep.add(r.to); } });
    tableEls.forEach((g, n) => g.classList.toggle("dim", !keep.has(n)));
    tableEls.get(name).classList.add("on");
    relEls.forEach((g, i) => {
      const r = rels[i], mine = r.from === name || r.to === name;
      g.classList.toggle("dim", !mine); g.classList.toggle("on", mine);
    });
    groupEls.forEach((g) => g.classList.toggle("dim", ![...keep].some((n) => (tables.get(n) || {}).group === g.dataset.group)));
    showDetail(t);
    if (opts.column) { const c = colEl(name, opts.column); if (c) c.classList.add("hl"); }
    if (opts.center) center(name);
  }

  function clear() {
    selected = null; clearMarks(); detail.hidden = true;
  }

  function jump(name, column) { focus(name, { center: true, column }); }

  function showDetail(t) {
    const kind = t.join ? "Join table" : t.group ? t.group : "Table";
    const close = el("button", "×", "close"); close.type = "button"; close.setAttribute("aria-label", "Close"); close.addEventListener("click", clear);
    detail.replaceChildren(close, el("div", kind, "kicker"), el("h2", t.name));
    if (t.note) detail.append(el("p", t.note, "note"));
    const tbl = el("table"), body = el("tbody");
    t.columns.forEach((c) => {
      const tr = el("tr"), name = el("td"), type = el("td", c.type, "t");
      if (c.pk) name.append(el("span", "PK ", "k"));
      if (c.fk) name.append(el("span", "FK ", "f"));
      name.append(document.createTextNode(c.name));
      if (c.unique && !c.pk) name.append(el("span", "UQ", "b"));
      if (c.nullable && !c.pk) name.append(el("span", "null", "b"));
      if (c.default) type.append(el("div", "= " + c.default, "via"));
      if (c.note) name.append(el("div", c.note, "via"));
      tr.append(name, type); body.append(tr);
    });
    tbl.append(body); detail.append(tbl);
    const out = rels.filter((r) => r.from === t.name), inc = rels.filter((r) => r.to === t.name && r.from !== t.name);
    const section = (title, list, pick) => {
      if (!list.length) return;
      detail.append(el("div", `${title} · ${list.length}`, "h"));
      list.forEach((r) => {
        const [target, label, via] = pick(r);
        const b = el("button", label, "link"); b.type = "button";
        b.append(el("span", "  " + via, "via"));
        b.addEventListener("click", () => jump(target[0], target[1]));
        detail.append(b);
      });
    };
    section("References", out, (r) => [[r.to, r.tcol], `${r.cols.join(", ")} → ${r.to}.${r.tcol}`, r.card]);
    section("Referenced by", inc, (r) => [[r.from, r.fcol], `${r.from}.${r.cols.join(", ")} → ${r.tcol}`, r.card]);
    detail.hidden = false;
  }

  // ---- hover a column: its foreign-key path -----------------------------------------
  function trace(table, col) {
    const seenCols = new Set(), onRels = new Set(), todo = [[table, col]];
    while (todo.length) {
      const [t, c] = todo.pop(), key = t + "\u0000" + lower(c);
      if (seenCols.has(key)) continue;
      seenCols.add(key);
      rels.forEach((r, i) => {
        if (r.from === t && r.cols.some((n) => lower(n) === lower(c))) { onRels.add(i); todo.push([r.to, r.tcol]); }
        if (r.to === t && lower(r.tcol) === lower(c) && t === table) { onRels.add(i); seenCols.add(r.from + "\u0000" + lower(r.fcol)); }
      });
    }
    if (!onRels.size) return false;
    svg.querySelectorAll(".col.hl").forEach((e) => e.classList.remove("hl"));
    seenCols.forEach((key) => { const [t, c] = key.split("\u0000"); const e = [...(tableEls.get(t)?.querySelectorAll(".col") || [])].find((x) => lower(x.dataset.col) === c); if (e) e.classList.add("hl"); });
    relEls.forEach((g, i) => { g.classList.toggle("on", onRels.has(i)); g.classList.toggle("dim", !onRels.has(i)); });
    return true;
  }
  function untrace() { if (selected) focus(selected); else clearMarks(); }
  svg.addEventListener("pointerover", (e) => {
    if (drag) return;
    const c = e.target.closest && e.target.closest(".col");
    if (!c) return;
    const t = c.closest(".table").dataset.table;
    if (!trace(t, c.dataset.col)) return;
    c.addEventListener("pointerleave", untrace, { once: true });
  });

  // ---- search ---------------------------------------------------------------------
  const input = document.getElementById("q"), results = document.getElementById("results");
  let hits = [], cur = 0;
  const paint = () => [...results.children].forEach((li, i) => li.firstChild.classList.toggle("cur", i === cur));
  function search() {
    const q = lower(input.value.trim());
    results.replaceChildren(); hits = []; cur = 0;
    if (!q) { results.hidden = true; return; }
    data.tables.forEach((t) => {
      if (lower(t.name).includes(q)) hits.push({ table: t.name, label: t.name, sub: t.group || "table" });
    });
    data.tables.forEach((t) => t.columns.forEach((c) => {
      if (lower(c.name).includes(q)) hits.push({ table: t.name, column: c.name, label: c.name, sub: "in " + t.name });
    }));
    hits = hits.slice(0, 30);
    hits.forEach((h, i) => {
      const li = el("li"), b = el("button", h.label); b.type = "button";
      b.append(el("span", "  " + h.sub, "in"));
      b.addEventListener("click", () => pick(i));
      li.append(b); results.append(li);
    });
    if (!hits.length) results.append(el("li", "No table or column matches", "in"));
    results.hidden = false; paint();
  }
  function pick(i) {
    const h = hits[i];
    if (!h) return;
    results.hidden = true;
    jump(h.table, h.column);
  }
  input.addEventListener("input", search);
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { cur = Math.min(hits.length - 1, cur + 1); paint(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { cur = Math.max(0, cur - 1); paint(); e.preventDefault(); }
    else if (e.key === "Enter") { pick(cur); e.preventDefault(); }
    else if (e.key === "Escape") { input.value = ""; results.hidden = true; }
    e.stopPropagation();
  });
  document.addEventListener("pointerdown", (e) => { if (!e.target.closest(".search")) results.hidden = true; });

  // ---- pointer: pan, zoom, click --------------------------------------------------
  main.addEventListener("pointerdown", (e) => {
    if (detail.contains(e.target) || e.button) return;
    drag = [e.clientX, e.clientY]; moved = 0;
  });
  main.addEventListener("pointermove", (e) => {
    if (!drag) return;
    const dx = e.clientX - drag[0], dy = e.clientY - drag[1];
    moved += Math.abs(dx) + Math.abs(dy);
    if (moved > 4) { if (!main.classList.contains("drag")) { main.classList.add("drag"); main.setPointerCapture(e.pointerId); } fitted = false; x += dx; y += dy; apply(); }
    drag = [e.clientX, e.clientY];
  });
  main.addEventListener("pointerup", (e) => {
    const was = drag; drag = null; main.classList.remove("drag");
    if (!was || moved > 4) return;
    const g = e.target.closest && e.target.closest(".table");
    if (g) focus(g.dataset.table); else if (!detail.contains(e.target)) clear();
  });
  main.addEventListener("pointercancel", () => { drag = null; main.classList.remove("drag"); });
  main.addEventListener("wheel", (e) => { e.preventDefault(); const r = main.getBoundingClientRect(); zoom(Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top); }, { passive: false });
  document.addEventListener("keydown", (e) => {
    if (e.target === input) return;
    if (e.key === "Escape") clear();
    else if (e.key === "/") { input.focus(); e.preventDefault(); }
    else if (e.key === "+" || e.key === "=") zoom(1.2);
    else if (e.key === "-") zoom(1 / 1.2);
    else if (e.key === "0") fit();
  });

  // ---- toolbar and exports ----------------------------------------------------------
  const on = (id, fn) => document.getElementById(id).addEventListener("click", fn);
  on("fit", fit); on("zin", () => zoom(1.2)); on("zout", () => zoom(1 / 1.2));
  const themeBtn = document.getElementById("theme");
  const label = () => { themeBtn.textContent = root.dataset.theme === "dark" ? "Light" : "Dark"; };
  on("theme", () => { root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark"; label(); });
  const fileName = (ext) => (data.title.replace(/[^A-Za-z0-9_-]+/g, "-").replace(/^-+|-+$/g, "") || "schema") + "." + ext;
  function download(content, type, name) {
    const blob = content instanceof Blob ? content : new Blob([content], { type });
    if (bridge) {
      const reader = new FileReader();
      reader.onload = () => window.parent.postMessage({ type: "uml-mcp/plugin-download", filename: name, mime_type: type, blob: String(reader.result).split(",")[1] }, "*");
      reader.readAsDataURL(blob);
      return;
    }
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = name;
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }
  function svgText() {
    const clone = svg.cloneNode(true);
    clone.querySelectorAll(".dim,.on,.hl").forEach((e) => e.classList.remove("dim", "on", "hl"));
    const style = document.createElementNS("http://www.w3.org/2000/svg", "style");
    style.textContent = exportCss[root.dataset.theme === "dark" ? "dark" : "light"];
    clone.insertBefore(style, clone.querySelector("defs").nextSibling);
    return new XMLSerializer().serializeToString(clone);
  }
  function pngBlob(done) {
    const scale = Math.min(2, 8192 / Math.max(W, H)), img = new Image();
    img.onload = () => {
      const c = document.createElement("canvas");
      c.width = Math.max(1, Math.round(W * scale)); c.height = Math.max(1, Math.round(H * scale));
      const ctx = c.getContext("2d"); ctx.scale(scale, scale); ctx.drawImage(img, 0, 0, W, H);
      c.toBlob(done, "image/png");
    };
    img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svgText());
  }
  function htmlText() {
    const doc = root.cloneNode(true);
    doc.querySelectorAll(".dim,.on,.hl").forEach((e) => e.classList.remove("dim", "on", "hl"));
    doc.removeAttribute("data-embedded"); doc.dataset.auto = "0";  // keep the theme on screen
    doc.querySelector("#stage").removeAttribute("style");
    doc.querySelector("#detail").hidden = true;
    doc.querySelector("#results").hidden = true;
    doc.querySelector("#q").removeAttribute("value");
    doc.querySelector("details.menu").removeAttribute("open");
    return "<!doctype html>\n" + doc.outerHTML + "\n";
  }
  const closeMenu = () => document.querySelector("details.menu").removeAttribute("open");
  const exporters = {
    svg: () => download(svgText(), "image/svg+xml", fileName("svg")),
    png: () => pngBlob((b) => { if (b) download(b, "image/png", fileName("png")); }),
    html: () => download(htmlText(), "text/html", fileName("html")),
  };
  Object.keys(exporters).forEach((f) => on("x-" + f, () => { closeMenu(); exporters[f](); }));
  if (embedded) {
    window.addEventListener("message", (e) => {
      if (e.source !== window.parent || !e.data) return;
      if (e.data.type === "uml-mcp/plugin-bridge-ready") bridge = true;
      else if (e.data.type === "uml-mcp/plugin-export" && exporters[e.data.format]) exporters[e.data.format]();
    });
    window.parent.postMessage({ type: "uml-mcp/plugin-ready", exports: ["svg", "png", "html"] }, "*");
  }
  window.addEventListener("resize", () => { if (fitted) fit(); });
  label(); fit();
  window.__schema = { focus, jump, clear, trace, search: (q) => { input.value = q; search(); return hits; },
    get selected() { return selected; }, get zoom() { return k; }, svgText, htmlText };
})();"""


def _hash(text: str) -> str:
    return base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode(
        "ascii"
    )


def json_for_script(data: Any) -> str:
    text = json.dumps(data, separators=(",", ":"), ensure_ascii=True)
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def data_of(schema: Schema) -> dict[str, Any]:
    """What the page needs for the detail card, search and tracing."""

    def card(r) -> str:
        a = "N" if r.source_card == "many" else "1"
        b = "N" if r.target_card == "many" else "1"
        return f"{a}:{b}" + (" optional" if r.optional else "")

    return {
        "title": schema.title,
        "tables": [
            {
                "name": t.name,
                "group": t.group,
                "note": t.note,
                "join": t.name in schema.join_tables,
                "columns": [
                    {
                        "name": c.name,
                        "type": c.type,
                        "pk": c.pk,
                        "fk": list(c.fk) if c.fk else None,
                        "nullable": c.nullable,
                        "unique": c.unique,
                        "default": c.default,
                        "note": c.note,
                    }
                    for c in t.columns
                ],
            }
            for t in schema.tables
        ],
        "relations": [
            {
                "from": r.source,
                "fcol": r.source_column,
                "cols": list(r.columns),
                "to": r.target,
                "tcol": r.target_column,
                "card": card(r),
                "label": r.label,
            }
            for r in schema.relations
        ],
    }


def page(schema: Schema, lay: Layout) -> str:
    svg, sheet = svg_parts(schema, lay, static=False, theme="light")
    theme_css = (
        f":root,:root[data-theme=light]{{{palette_vars('light')}}}"
        f":root[data-theme=dark]{{{palette_vars('dark')}}}"
    )
    style = _PAGE_CSS + theme_css + sheet
    export_css = {name: css(PALETTES[name]) for name in PALETTES}
    csp = (
        "default-src 'none'; "
        f"script-src 'sha256-{_hash(_SCRIPT)}'; "
        f"style-src 'sha256-{_hash(style)}'; "
        "img-src data: blob:; base-uri 'none'; form-action 'none'"
    )
    theme = schema.theme if schema.theme in {"light", "dark"} else "light"
    auto = "1" if schema.theme == "auto" else "0"
    n_t, n_r = len(schema.tables), len(schema.relations)
    meta = f"{n_t} tables · {n_r} relationships"
    return (
        "<!doctype html>\n"
        f'<html lang="en" data-theme="{theme}" data-auto="{auto}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta http-equiv="Content-Security-Policy" content="{escape(csp, quote=True)}">'
        f"<title>{escape(schema.title)}</title><style>{style}</style></head><body>"
        f'<header><div class="ident"><h1>{escape(schema.title)}</h1><span class="meta">{meta}</span></div>'
        '<div class="toolbar" role="toolbar" aria-label="Schema controls">'
        '<div class="search"><label class="sr" for="q">Find a table or column</label>'
        '<input id="q" type="search" placeholder="Find table or column  /" autocomplete="off">'
        '<ul id="results" hidden></ul></div>'
        '<button id="zout" type="button" aria-label="Zoom out">−</button>'
        '<span id="zoomval" class="zoom">100%</span>'
        '<button id="zin" type="button" aria-label="Zoom in">+</button>'
        '<button id="fit" type="button">Fit</button>'
        '<button id="theme" type="button">Dark</button>'
        '<details class="menu"><summary>Export</summary><div class="items">'
        '<button id="x-svg" type="button">SVG</button><button id="x-png" type="button">PNG</button>'
        '<button id="x-html" type="button">HTML</button></div></details></div></header>'
        f'<main><div id="stage">{svg}</div>'
        '<aside id="detail" hidden aria-live="polite"></aside>'
        '<div class="hint">Click a table · hover a column to trace its keys · / to search · Esc clears</div></main>'
        f'<script type="application/json" id="schema-data">{json_for_script(data_of(schema))}</script>'
        f'<script type="application/json" id="export-css">{json_for_script(export_css)}</script>'
        f"<script>{_SCRIPT}</script></body></html>\n"
    )
