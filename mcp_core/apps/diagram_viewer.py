"""MCP Apps sandboxed diagram viewer (``ui://uml-mcp/diagram-viewer``).

Linked from ``generate_uml`` / ``generate_uml_image`` via tool ``_meta.ui``.
Hosts that do not advertise ``text/html;profile=mcp-app`` keep markdown /
ImageContent; hosts that do open this HTML with the tool result the host already
holds. The iframe never calls Kroki; re-render goes through the host as
``tools/call`` on the app-only ``rerender_diagram`` tool.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

DIAGRAM_VIEWER_URI = "ui://uml-mcp/diagram-viewer"
DIAGRAM_VIEWER_DESCRIPTION = (
    "Interactive UML-MCP diagram viewer with zoom, pan, fit, reset and a "
    "safe render preview. SVG, PNG and JPEG results are supported; theme and "
    "format can be switched and re-rendered, and links or source copied."
)
# All app views must agree on an exact HTTPS origin. The default is the Vercel
# production host that also serves /mcp and the OpenAI Apps domain challenge.
# Override for other trusted deployments, e.g. MCP_APP_DOMAIN=https://uml-mcp.vercel.app.
_DEFAULT_APP_DOMAIN = "https://uml-mcp.antoineboucher.info"


def diagram_viewer_domain() -> str:
    """Validate the dedicated iframe origin (no URL path or credentials)."""
    domain = os.environ.get("MCP_APP_DOMAIN", _DEFAULT_APP_DOMAIN).strip().rstrip("/")
    parsed = urlsplit(domain)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("MCP_APP_DOMAIN must be one HTTPS origin without a path")
    return domain


#: Formats the viewer can display inline (and offer for re-render).
VIEWER_FORMATS = ("png", "svg", "jpeg")

_THEME_DATA_PLACEHOLDER = "__UML_MCP_VIEWER_DATA__"

# Self-contained HTML: postMessage bridge + SVG sanitize (mirrors svg_sanitize.py).
# No inline <svg> chrome: the only <svg> in the document is the rendered diagram.
_DIAGRAM_VIEWER_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>UML-MCP diagram</title>
<style>
  :root {
    color-scheme: light dark;
    --bg: var(--color-background-primary, #ffffff);
    --surface: var(--color-background-secondary, #f6f7f9);
    --fg: var(--color-text-primary, #161a23);
    --muted: var(--color-text-secondary, #5d6472);
    --border: var(--color-border-primary, #e3e6eb);
    --link: var(--color-text-link, #4f46e5);
    --accent: #4f46e5;
    --accent-fg: #ffffff;
    --danger: #c62828;
    --ok: #1b873f;
    --dot: rgba(22, 26, 35, 0.09);
    --glass: rgba(255, 255, 255, 0.82);
    --shadow: 0 1px 2px rgba(16, 24, 40, 0.06), 0 6px 20px rgba(16, 24, 40, 0.08);
    --radius: 12px;
    --font: var(--font-sans, ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif);
    --mono: var(--font-mono, ui-monospace, "SF Mono", "Cascadia Code", Consolas, monospace);
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: var(--color-background-primary, #14161b);
      --surface: var(--color-background-secondary, #1b1e25);
      --fg: var(--color-text-primary, #e8eaef);
      --muted: var(--color-text-secondary, #9aa1ae);
      --border: var(--color-border-primary, #2c313b);
      --link: var(--color-text-link, #a5b4fc);
      --accent: #818cf8;
      --accent-fg: #0f1115;
      --danger: #ff8a80;
      --ok: #6fdc8c;
      --dot: rgba(232, 234, 239, 0.08);
      --glass: rgba(27, 30, 37, 0.84);
      --shadow: 0 1px 2px rgba(0, 0, 0, 0.3), 0 8px 24px rgba(0, 0, 0, 0.35);
    }
  }
  * { box-sizing: border-box; }
  [hidden] { display: none !important; }
  html, body { background: var(--bg); }
  body {
    margin: 0; padding: 12px;
    font: 13px/1.45 var(--font);
    color: var(--fg);
    -webkit-font-smoothing: antialiased;
  }
  button, a.btn, select { font: inherit; color: inherit; }
  :focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

  /* Header: type badge + status chip, link actions on the right. */
  #header {
    display: flex; flex-wrap: wrap; align-items: center; gap: 8px;
    margin-bottom: 10px;
  }
  #brand { display: flex; align-items: center; gap: 8px; min-width: 0; flex: 1; }
  #brandMark {
    width: 24px; height: 24px; border-radius: 7px; flex: none;
    display: grid; place-items: center; font-size: 13px; font-weight: 700;
    color: var(--accent-fg);
    background: linear-gradient(135deg, var(--accent), #06b6d4);
  }
  #typeBadge {
    font: 600 12px/1 var(--mono); padding: 5px 8px; border-radius: 999px;
    background: var(--surface); border: 1px solid var(--border);
    white-space: nowrap;
  }
  #status {
    display: inline-flex; align-items: center; gap: 6px; min-width: 0;
    color: var(--muted); font-size: 12px;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  #status::before {
    content: ""; width: 7px; height: 7px; border-radius: 50%; flex: none;
    background: var(--muted); opacity: 0.6;
  }
  #status.ok::before { background: var(--ok); opacity: 1; }
  #status.busy::before { background: var(--accent); opacity: 1; animation: pulse 1s ease-in-out infinite; }
  #status.err { color: var(--danger); white-space: normal; }
  #status.err::before { background: var(--danger); opacity: 1; }
  #actions { display: flex; flex-wrap: wrap; gap: 6px; }

  .btn {
    appearance: none; display: inline-flex; align-items: center; justify-content: center; gap: 6px;
    height: 30px; padding: 0 11px; border-radius: 8px;
    border: 1px solid var(--border); background: var(--bg);
    cursor: pointer; text-decoration: none; white-space: nowrap;
    transition: background-color .15s, border-color .15s, transform .05s;
  }
  .btn:hover { background: var(--surface); border-color: var(--muted); }
  .btn:active { transform: translateY(1px); }
  .btn:disabled { opacity: .55; cursor: progress; }
  .btn.primary { background: var(--accent); border-color: var(--accent); color: var(--accent-fg); font-weight: 600; }
  .btn.primary:hover { filter: brightness(1.08); background: var(--accent); }
  .btn.icon { width: 30px; padding: 0; font-size: 15px; }

  /* Canvas: dotted board, diagram sits on a sheet of paper. */
  #stage { position: relative; }
  #frame {
    position: relative;
    display: flex; justify-content: center; align-items: center;
    min-height: 280px; height: min(65vh, 560px);
    border: 1px solid var(--border); border-radius: var(--radius);
    overflow: hidden;
    background-color: var(--surface);
    background-image: radial-gradient(var(--dot) 1px, transparent 1px);
    background-size: 16px 16px;
    touch-action: none; cursor: grab;
  }
  #frame.panning { cursor: grabbing; }
  #frame img, #frame svg {
    flex: none; max-width: none; height: auto; display: block;
    transform-origin: center center;
    user-select: none; -webkit-user-drag: none;
    padding: 14px; border-radius: 10px;
    background: #ffffff; box-shadow: var(--shadow);
  }
  #frame.paper-dark img, #frame.paper-dark svg { background: #101217; }
  body.fullscreen #frame { height: calc(100vh - 150px); }

  .empty { display: grid; justify-items: center; gap: 10px; color: var(--muted); text-align: center; padding: 24px; }
  .skeleton {
    width: min(320px, 70%); height: 120px; border-radius: 10px;
    background: linear-gradient(90deg, var(--border) 0%, var(--bg) 50%, var(--border) 100%);
    background-size: 200% 100%; animation: shimmer 1.4s linear infinite; opacity: .7;
  }

  #loading {
    position: absolute; inset: 0; display: grid; place-items: center;
    background: color-mix(in srgb, var(--surface) 55%, transparent);
    border-radius: var(--radius); pointer-events: none;
  }
  .spinner {
    width: 28px; height: 28px; border-radius: 50%;
    border: 3px solid var(--border); border-top-color: var(--accent);
    animation: spin .8s linear infinite;
  }

  /* Floating zoom bar (bottom-centre of the canvas). */
  #toolbar {
    position: absolute; left: 50%; bottom: 12px; transform: translateX(-50%);
    display: flex; align-items: center; gap: 2px; padding: 4px;
    border: 1px solid var(--border); border-radius: 999px;
    background: var(--glass); box-shadow: var(--shadow);
    -webkit-backdrop-filter: blur(10px); backdrop-filter: blur(10px);
  }
  #toolbar button {
    appearance: none; border: 0; background: transparent; cursor: pointer;
    height: 28px; min-width: 28px; padding: 0 10px; border-radius: 999px;
  }
  #toolbar button:hover { background: var(--surface); }
  #toolbar .sep { width: 1px; height: 16px; background: var(--border); margin: 0 4px; }
  #zoomLabel { min-width: 3.4em; text-align: center; font: 600 12px/1 var(--mono); color: var(--muted); }

  /* Re-render controls. */
  #rerenderRow {
    display: none; flex-wrap: wrap; align-items: center; gap: 8px;
    margin-top: 10px; padding: 8px; border: 1px solid var(--border);
    border-radius: var(--radius); background: var(--surface);
  }
  #rerenderRow.visible { display: flex; }
  #rerenderRow label { display: inline-flex; align-items: center; gap: 6px; color: var(--muted); font-size: 12px; }
  #rerenderRow .grow { flex: 1; }
  select {
    appearance: none; height: 30px; padding: 0 28px 0 10px; border-radius: 8px;
    border: 1px solid var(--border); background-color: var(--bg); color: var(--fg); cursor: pointer;
    background-image: linear-gradient(45deg, transparent 50%, var(--muted) 50%), linear-gradient(135deg, var(--muted) 50%, transparent 50%);
    background-position: right 13px top 13px, right 9px top 13px;
    background-size: 4px 4px; background-repeat: no-repeat;
  }

  /* Result details: compact copyable links + render stats. */
  #meta { margin-top: 10px; display: grid; gap: 6px; }
  .row {
    display: grid; grid-template-columns: 84px minmax(0, 1fr) auto; align-items: center; gap: 8px;
    padding: 6px 6px 6px 10px; border: 1px solid var(--border); border-radius: 10px; background: var(--bg);
  }
  .row .k { color: var(--muted); font-size: 12px; }
  .row a { color: var(--link); font: 12px/1.3 var(--mono); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; text-decoration: none; }
  .row a:hover { text-decoration: underline; }
  .row .btn { height: 26px; padding: 0 9px; font-size: 12px; }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; }
  .chip {
    font-size: 11px; padding: 3px 8px; border-radius: 999px;
    border: 1px solid var(--border); color: var(--muted); background: var(--surface);
  }

  @keyframes spin { to { transform: rotate(360deg); } }
  @keyframes pulse { 50% { opacity: .35; } }
  @keyframes shimmer { to { background-position: -200% 0; } }
  @media (prefers-reduced-motion: reduce) {
    *, *::before { animation: none !important; transition: none !important; }
  }
  @media (max-width: 480px) {
    body { padding: 8px; }
    .row { grid-template-columns: minmax(0, 1fr) auto; }
    .row .k { display: none; }
  }
</style>
</head>
<body>
  <div id="header">
    <div id="brand">
      <span id="brandMark" aria-hidden="true">U</span>
      <span id="typeBadge" hidden></span>
      <span id="status" role="status" aria-live="polite">Waiting for diagram…</span>
    </div>
    <div id="actions">
      <a class="btn" id="openUrl" href="#" target="_blank" rel="noopener" hidden>Open image ↗</a>
      <a class="btn" id="openPlay" href="#" target="_blank" rel="noopener" hidden>Playground ↗</a>
      <button type="button" class="btn icon" id="fullscreenBtn" title="Toggle fullscreen" aria-label="Toggle fullscreen" hidden>⤢</button>
    </div>
  </div>
  <div id="stage">
    <div id="frame" aria-label="Diagram canvas">
      <div class="empty"><div class="skeleton"></div><div>Waiting for a diagram from the host…</div></div>
    </div>
    <div id="loading" hidden><span class="spinner" aria-hidden="true"></span></div>
    <div id="toolbar" role="toolbar" aria-label="Zoom" hidden>
      <button type="button" id="zoomOut" aria-label="Zoom out" title="Zoom out (-)">−</button>
      <span id="zoomLabel">100%</span>
      <button type="button" id="zoomIn" aria-label="Zoom in" title="Zoom in (+)">+</button>
      <span class="sep" aria-hidden="true"></span>
      <button type="button" id="zoomFit" title="Fit entire diagram (F)" aria-label="Fit diagram to screen">Fit</button>
      <button type="button" id="zoomReset" title="Reset zoom and pan (0)" aria-label="Reset zoom to 100%">1:1</button>
    </div>
  </div>
  <div id="rerenderRow">
    <label id="themeWrap">Theme
      <select id="themeSelect" title="Diagram theme for re-render"><option value="">Default</option></select>
    </label>
    <label>Format
      <select id="formatSelect" title="Output format for re-render">
        <option value="png">PNG</option>
        <option value="svg">SVG</option>
        <option value="jpeg">JPEG</option>
      </select>
    </label>
    <span class="grow"></span>
    <button type="button" class="btn" id="copySource" title="Copy diagram source">Copy source</button>
    <button type="button" class="btn primary" id="rerenderBtn" title="Re-render via app-only tools/call">Re-render</button>
  </div>
  <div id="meta"></div>
<script>
(function () {
  "use strict";
  var DATA = __UML_MCP_VIEWER_DATA__;
  var STATUS = document.getElementById("status");
  var FRAME = document.getElementById("frame");
  var META = document.getElementById("meta");
  var TOOLBAR = document.getElementById("toolbar");
  var REROW = document.getElementById("rerenderRow");
  var LOADING = document.getElementById("loading");
  var TYPE_BADGE = document.getElementById("typeBadge");
  var ZOOM_LABEL = document.getElementById("zoomLabel");
  var OPEN_URL = document.getElementById("openUrl");
  var OPEN_PLAY = document.getElementById("openPlay");
  var FULLSCREEN_BTN = document.getElementById("fullscreenBtn");
  var THEME_WRAP = document.getElementById("themeWrap");
  var THEME_SEL = document.getElementById("themeSelect");
  var FORMAT_SEL = document.getElementById("formatSelect");
  var MIN_ZOOM = 0.1, MAX_ZOOM = 8;
  var zoom = 1;
  var fitZoom = 1;
  var panX = 0, panY = 0, panStart = null;
  var nextId = 1;
  var pending = Object.create(null);
  /** @type {{diagram_type?: string, code?: string, theme?: string, output_format?: string}|null} */
  var lastArgs = null;
  var canCallTools = true;
  var displayMode = "inline";
  var STRIP_TAGS = {
    script: 1, foreignobject: 1, iframe: 1, object: 1, embed: 1, link: 1, meta: 1, base: 1
  };

  function post(msg) {
    try { window.parent.postMessage(msg, "*"); } catch (e) { /* host gone */ }
  }

  function request(method, params) {
    var id = nextId++;
    return new Promise(function (resolve, reject) {
      var timer = setTimeout(function () {
        delete pending[id];
        reject(new Error("MCP App host did not respond. Retry the action."));
      }, 30000);
      pending[id] = { resolve: resolve, reject: reject, timer: timer };
      post({ jsonrpc: "2.0", id: id, method: method, params: params || {} });
    });
  }

  function notify(method, params) {
    post({ jsonrpc: "2.0", method: method, params: params || {} });
  }

  function localName(el) {
    return (el.localName || el.nodeName || "").toLowerCase();
  }

  function sanitizeSvg(svgText) {
    if (!svgText || !String(svgText).trim()) return "";
    var parser = new DOMParser();
    var doc = parser.parseFromString(String(svgText), "image/svg+xml");
    if (doc.querySelector("parsererror")) return "";
    var root = doc.documentElement;
    if (!root || localName(root) !== "svg") return "";
    var walk = [root].concat(Array.from(root.querySelectorAll("*")));
    for (var i = walk.length - 1; i >= 0; i--) {
      var node = walk[i];
      if (STRIP_TAGS[localName(node)]) {
        node.parentNode && node.parentNode.removeChild(node);
        continue;
      }
      var attrs = Array.prototype.slice.call(node.attributes || []);
      for (var j = 0; j < attrs.length; j++) {
        var a = attrs[j];
        var name = a.name;
        var val = a.value || "";
        var base = name.indexOf(":") >= 0 ? name.split(":").pop() : name;
        if (/^on/i.test(base) ||
            ((base === "href" || name === "xlink:href") && /^\s*javascript:/i.test(val))) {
          node.removeAttribute(name);
        }
      }
    }
    if (STRIP_TAGS[localName(root)]) return "";
    return new XMLSerializer().serializeToString(root);
  }

  function applyHostContext(hostContext) {
    if (!hostContext) return;
    var vars = hostContext.styles && hostContext.styles.variables;
    if (vars) {
      var root = document.documentElement;
      Object.keys(vars).forEach(function (k) {
        if (vars[k] != null) root.style.setProperty(k, vars[k]);
      });
    }
    if (hostContext.theme === "dark" || hostContext.theme === "light") {
      document.documentElement.style.colorScheme = hostContext.theme;
    }
    var modes = hostContext.availableDisplayModes;
    if (Array.isArray(modes)) FULLSCREEN_BTN.hidden = modes.indexOf("fullscreen") < 0;
    if (hostContext.displayMode) setDisplayMode(hostContext.displayMode);
  }

  function setDisplayMode(mode) {
    displayMode = mode === "fullscreen" ? "fullscreen" : "inline";
    document.body.classList.toggle("fullscreen", displayMode === "fullscreen");
    FULLSCREEN_BTN.textContent = displayMode === "fullscreen" ? "⤡" : "⤢";
    notifySize();
  }

  function setStatus(text, kind) {
    STATUS.textContent = text || "";
    STATUS.className = kind === true ? "err" : (kind || "");
    STATUS.title = text || "";
  }

  function setBusy(busy) {
    LOADING.hidden = !busy;
    if (busy) FRAME.setAttribute("aria-busy", "true");
    else FRAME.removeAttribute("aria-busy");
  }

  function media() {
    return FRAME.querySelector("img, svg");
  }

  function clampZoom(value) {
    return Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, value));
  }

  function applyZoom() {
    var m = media();
    if (m) m.style.transform = "translate(" + panX + "px," + panY + "px) scale(" + zoom + ")";
    ZOOM_LABEL.textContent = Math.round(zoom * 100) + "%";
    notifySize();
  }

  function computeFit() {
    var m = media();
    if (!m) return 1;
    // SVG elements have no offsetWidth and their bounding box includes the scale.
    var rect = m.getBoundingClientRect();
    var width = m.offsetWidth || rect.width / zoom;
    var height = m.offsetHeight || rect.height / zoom;
    if (!width || !height) return 1;
    return clampZoom(Math.min(
      (FRAME.clientWidth - 32) / width, (FRAME.clientHeight - 72) / height
    ));
  }

  function fitDiagram() {
    fitZoom = computeFit();
    zoom = fitZoom;
    panX = panY = 0;
    applyZoom();
  }

  /** Shrink oversized diagrams to fit on first paint; never upscale small ones. */
  function autoFit() {
    fitZoom = computeFit();
    zoom = Math.min(1, fitZoom);
    panX = panY = 0;
    applyZoom();
  }

  function zoomBy(factor) {
    zoom = clampZoom(Math.round(zoom * factor * 100) / 100);
    applyZoom();
  }

  function safeUrl(value) {
    try {
      var url = new URL(String(value));
      return (url.protocol === "https:" || url.protocol === "http:") ? url.href : "";
    } catch (e) { return ""; }
  }

  function legacyCopy(text) {
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    document.body.removeChild(ta);
    return ok;
  }

  function copyText(text, btn) {
    var label = btn.textContent;
    function done(ok) {
      btn.textContent = ok ? "Copied ✓" : "Copy blocked";
      setTimeout(function () { btn.textContent = label; }, 1400);
    }
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(
          function () { done(true); },
          function () { done(legacyCopy(text)); }
        );
        return;
      }
    } catch (e) { /* fall through to the legacy path */ }
    done(legacyCopy(text));
  }

  function linkRow(label, href) {
    var row = document.createElement("div");
    row.className = "row";
    var k = document.createElement("span");
    k.className = "k";
    k.textContent = label;
    var a = document.createElement("a");
    a.href = href;
    a.target = "_blank";
    a.rel = "noopener";
    a.title = href;
    a.textContent = href;
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn";
    btn.textContent = "Copy";
    btn.addEventListener("click", function () { copyText(href, btn); });
    row.appendChild(k);
    row.appendChild(a);
    row.appendChild(btn);
    return row;
  }

  function statChips(data) {
    var chips = [];
    if (data.output_format) chips.push(String(data.output_format).toUpperCase());
    if (data.theme) chips.push("theme: " + data.theme);
    if (typeof data.render_ms === "number") chips.push(Math.round(data.render_ms) + " ms");
    if (data.cache_hit) chips.push("cached");
    if (data.fallback_used) chips.push("fallback renderer");
    if (!chips.length) return null;
    var wrap = document.createElement("div");
    wrap.className = "chips";
    chips.forEach(function (text) {
      var chip = document.createElement("span");
      chip.className = "chip";
      chip.textContent = text;
      wrap.appendChild(chip);
    });
    return wrap;
  }

  function showLinks(data) {
    var url = safeUrl(data.url);
    var playground = safeUrl(data.playground);
    META.textContent = "";
    if (url) {
      META.appendChild(linkRow("Image URL", url));
      OPEN_URL.href = url;
      OPEN_URL.hidden = false;
    } else {
      OPEN_URL.hidden = true;
    }
    if (playground) {
      META.appendChild(linkRow("Playground", playground));
      OPEN_PLAY.href = playground;
      OPEN_PLAY.hidden = false;
    } else {
      OPEN_PLAY.hidden = true;
    }
    var chips = statChips(data);
    if (chips) META.appendChild(chips);
    if (data.diagram_type) {
      TYPE_BADGE.textContent = String(data.diagram_type);
      TYPE_BADGE.hidden = false;
    }
    TOOLBAR.hidden = !media();
    updateRerenderRow();
  }

  function typeInfo(diagramType) {
    return (DATA.types && DATA.types[diagramType]) || {};
  }

  function fillSelect(select, values, current, defaultLabel) {
    select.textContent = "";
    if (defaultLabel) {
      var def = document.createElement("option");
      def.value = "";
      def.textContent = defaultLabel;
      select.appendChild(def);
    }
    var list = values.slice();
    if (current && list.indexOf(current) < 0) list.push(current);
    list.forEach(function (value) {
      var opt = document.createElement("option");
      opt.value = value;
      opt.textContent = defaultLabel ? value : value.toUpperCase();
      select.appendChild(opt);
    });
    select.value = current || (defaultLabel ? "" : list[0] || "");
  }

  function updateRerenderRow() {
    var hasCode = !!(lastArgs && lastArgs.code && lastArgs.diagram_type);
    REROW.className = hasCode && canCallTools ? "visible" : "";
    if (!lastArgs) return;
    var info = typeInfo(lastArgs.diagram_type);
    var themes = (DATA.themes && DATA.themes[info.theme_family]) || [];
    var theme = lastArgs.theme != null ? String(lastArgs.theme) : "";
    THEME_WRAP.hidden = !themes.length && !theme;
    fillSelect(THEME_SEL, themes, theme, "Default");
    var format = String(lastArgs.output_format || "png").toLowerCase();
    if (format === "jpg") format = "jpeg";
    var formats = info.formats && info.formats.length ? info.formats : DATA.formats;
    fillSelect(FORMAT_SEL, formats, formats.indexOf(format) >= 0 ? format : "", "");
    FRAME.classList.toggle("paper-dark", (DATA.dark_themes || []).indexOf(theme.toLowerCase()) >= 0);
  }

  function rememberArgsFromData(data) {
    if (!data || typeof data !== "object") return;
    if (typeof data.code === "string" && data.code && data.diagram_type) {
      lastArgs = {
        diagram_type: String(data.diagram_type),
        code: data.code,
        theme: data.theme != null ? String(data.theme) : (lastArgs && lastArgs.theme) || "",
        output_format: data.output_format ? String(data.output_format) : (lastArgs && lastArgs.output_format) || "png"
      };
    }
  }

  function showEmpty(text) {
    FRAME.textContent = "";
    var box = document.createElement("div");
    box.className = "empty";
    box.textContent = text;
    FRAME.appendChild(box);
  }

  function mount(node) {
    FRAME.textContent = "";
    FRAME.appendChild(node);
    TOOLBAR.hidden = false;
  }

  function renderFromStructured(data) {
    META.textContent = "";
    zoom = 1;
    panX = panY = 0;
    rememberArgsFromData(data);
    if (!data || typeof data !== "object") {
      showEmpty("No diagram in this tool result.");
      setStatus("No diagram data in tool result.", true);
      TOOLBAR.hidden = true;
      REROW.className = "";
      return;
    }
    if (data.error) {
      showEmpty("The renderer returned an error. Edit the source and re-render, or open the playground.");
      setStatus(String(data.error), true);
      showLinks(data);
      return;
    }
    var mime = String(data.mime_type || "").toLowerCase();
    var b64 = data.content_base64;
    if (b64 && (mime === "image/png" || mime === "image/jpeg" || mime.indexOf("jpeg") >= 0)) {
      var img = document.createElement("img");
      img.alt = (data.diagram_type || "diagram") + " diagram";
      img.addEventListener("load", autoFit);
      img.src = "data:" + (mime || "image/png") + ";base64," + b64;
      mount(img);
      setStatus("Diagram ready", "ok");
      showLinks(data);
      applyZoom();
      return;
    }
    if (b64 && (mime === "image/svg+xml" || mime.indexOf("svg") >= 0)) {
      var raw;
      try {
        raw = new TextDecoder("utf-8", { fatal: true }).decode(
          Uint8Array.from(atob(b64), function (c) { return c.charCodeAt(0); })
        );
      } catch (e) { raw = ""; }
      var clean = sanitizeSvg(raw);
      if (clean) {
        FRAME.innerHTML = clean;
        TOOLBAR.hidden = false;
        setStatus("Diagram ready", "ok");
        showLinks(data);
        autoFit();
        return;
      }
    }
    // URL-only: never fetch Kroki from the iframe; show links.
    showEmpty(b64 ? "Could not display the image bytes — open the image URL instead." :
      "This result has links only (no inline image). Open it below, or re-render as PNG.");
    setStatus(
      data.inline_note ||
      (b64 ? "Could not display image bytes; use the URL below." : "URL-only result (no inline bytes)."),
      Boolean(data.inline_omitted && !data.url)
    );
    showLinks(data);
    notifySize();
  }

  function notifySize() {
    var h = Math.max(document.body.scrollHeight, 160);
    notify("ui/notifications/size-changed", { height: h });
  }

  function extractStructured(params) {
    var data = (params && params.structuredContent) ||
      (params && params.structured_content) || null;
    if (!data && params && Array.isArray(params.content)) {
      for (var i = 0; i < params.content.length; i++) {
        var c = params.content[i];
        if (c && c.type === "text" && typeof c.text === "string") {
          try { data = JSON.parse(c.text); break; } catch (e) { /* keep looking */ }
        }
      }
    }
    return data || {};
  }

  function onToolResult(params) {
    setBusy(false);
    renderFromStructured(extractStructured(params));
  }

  function onToolInput(params) {
    var args = (params && params.arguments) || params || {};
    if (typeof args === "object" && args.diagram_type && args.code) {
      lastArgs = {
        diagram_type: String(args.diagram_type),
        code: String(args.code),
        theme: args.theme != null ? String(args.theme) : "",
        output_format: args.output_format ? String(args.output_format) : "png"
      };
      TYPE_BADGE.textContent = lastArgs.diagram_type;
      TYPE_BADGE.hidden = false;
      if (!media()) {
        setBusy(true);
        setStatus("Rendering…", "busy");
      }
      updateRerenderRow();
    }
  }

  function rerender() {
    if (!lastArgs || !lastArgs.code || !lastArgs.diagram_type) {
      setStatus("Nothing to re-render yet.", true);
      return;
    }
    var args = {
      diagram_type: lastArgs.diagram_type,
      code: lastArgs.code,
      theme: THEME_SEL.value || null,
      output_format: FORMAT_SEL.value || "png"
    };
    var btn = document.getElementById("rerenderBtn");
    if (btn.disabled) return;
    btn.disabled = true;
    setBusy(true);
    setStatus("Re-rendering…", "busy");
    request("tools/call", { name: "rerender_diagram", arguments: args })
      .then(function (result) {
        lastArgs.theme = args.theme || "";
        lastArgs.output_format = args.output_format;
        onToolResult(result || {});
      })
      .catch(function (err) {
        updateRerenderRow();
        var msg = (err && err.message) || (typeof err === "string" ? err : "host rejected tools/call");
        setStatus("Re-render failed: " + msg, true);
      }).finally(function () {
        btn.disabled = false;
        setBusy(false);
      });
  }

  window.addEventListener("message", function (ev) {
    if (ev.source !== window.parent) return;
    var msg = ev.data;
    if (!msg || msg.jsonrpc !== "2.0") return;
    if (msg.id != null && (msg.result !== undefined || msg.error)) {
      var p = pending[msg.id];
      if (!p) return;
      clearTimeout(p.timer);
      delete pending[msg.id];
      if (msg.error) p.reject(msg.error);
      else p.resolve(msg.result);
      return;
    }
    if (!msg.method) return;
    if (msg.method === "ui/notifications/tool-result") {
      onToolResult(msg.params || {});
    } else if (msg.method === "ui/notifications/tool-input") {
      onToolInput(msg.params || {});
    } else if (msg.method === "ui/notifications/tool-cancelled") {
      setBusy(false);
      setStatus("Tool cancelled" + (msg.params && msg.params.reason ? ": " + msg.params.reason : ""), true);
    } else if (msg.method === "ui/notifications/host-context-changed") {
      applyHostContext(msg.params || {});
    } else if (msg.method === "ui/resource-teardown" && msg.id != null) {
      post({ jsonrpc: "2.0", id: msg.id, result: {} });
    }
  });

  document.getElementById("zoomIn").addEventListener("click", function () { zoomBy(1.25); });
  document.getElementById("zoomOut").addEventListener("click", function () { zoomBy(0.8); });
  document.getElementById("zoomFit").addEventListener("click", fitDiagram);
  document.getElementById("zoomReset").addEventListener("click", function () {
    zoom = 1;
    panX = panY = 0;
    applyZoom();
  });
  document.getElementById("copySource").addEventListener("click", function (event) {
    if (lastArgs && lastArgs.code) copyText(lastArgs.code, event.currentTarget);
  });
  FULLSCREEN_BTN.addEventListener("click", function () {
    var want = displayMode === "fullscreen" ? "inline" : "fullscreen";
    request("ui/request-display-mode", { mode: want })
      .then(function (result) { setDisplayMode((result && result.mode) || want); })
      .catch(function () { setStatus("Fullscreen is not available in this host.", true); });
  });
  FRAME.addEventListener("pointerdown", function (event) {
    if (event.button !== 0 || !media()) return;
    panStart = { x: event.clientX, y: event.clientY, panX: panX, panY: panY };
    FRAME.classList.add("panning");
    FRAME.setPointerCapture(event.pointerId);
  });
  FRAME.addEventListener("pointermove", function (event) {
    if (!panStart) return;
    panX = panStart.panX + event.clientX - panStart.x;
    panY = panStart.panY + event.clientY - panStart.y;
    applyZoom();
  });
  function stopPan() { panStart = null; FRAME.classList.remove("panning"); }
  FRAME.addEventListener("pointerup", stopPan);
  FRAME.addEventListener("pointercancel", stopPan);
  FRAME.addEventListener("lostpointercapture", stopPan);
  FRAME.addEventListener("dblclick", function () { if (media()) fitDiagram(); });
  FRAME.addEventListener("wheel", function (event) {
    if (!media()) return;
    event.preventDefault();
    zoomBy(event.deltaY < 0 ? 1.1 : 1 / 1.1);
  }, { passive: false });
  document.addEventListener("keydown", function (event) {
    if (event.altKey || event.ctrlKey || event.metaKey || /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) return;
    if (event.key === "+" || event.key === "=") { zoomBy(1.25); }
    else if (event.key === "-") { zoomBy(0.8); }
    else if (event.key === "0") { zoom = 1; panX = panY = 0; applyZoom(); }
    else if (event.key.toLowerCase() === "f") { fitDiagram(); }
    else return;
    event.preventDefault();
  });
  document.getElementById("rerenderBtn").addEventListener("click", rerender);

  request("ui/initialize", {
    appInfo: { name: "uml-mcp-diagram-viewer", version: "1.3.0" },
    appCapabilities: { availableDisplayModes: ["inline", "fullscreen"] }
  }).then(function (result) {
    applyHostContext(result && result.hostContext);
    notify("ui/notifications/initialized", {});
    if (!media()) setStatus("Ready — waiting for tool result…");
  }).catch(function () {
    // Standalone open (no host): keep waiting; tests can inject results via postMessage.
    setStatus("Open this view from an MCP Apps host to receive a diagram.");
  });
})();
</script>
</body>
</html>
"""


def _viewer_data() -> dict[str, Any]:
    """Per-type theme families and formats the viewer offers for re-render."""
    from ..core.diagram_themes import (
        D2_DARK_BG,
        MERMAID_DARK_BG,
        MERMAID_LIGHT_BG,
        PLANTUML_BW_BG,
        PLANTUML_DARK_BG,
        PLANTUML_LIGHT_BG,
        PLANTUML_RECOMMENDED_THEMES,
    )

    plantuml = list(
        dict.fromkeys(
            PLANTUML_RECOMMENDED_THEMES
            + PLANTUML_LIGHT_BG
            + PLANTUML_DARK_BG
            + PLANTUML_BW_BG
        )
    )
    data: dict[str, Any] = {
        "formats": list(VIEWER_FORMATS),
        "themes": {
            "plantuml": plantuml,
            "mermaid": list(dict.fromkeys(MERMAID_LIGHT_BG + MERMAID_DARK_BG)),
            "d2": ["default", "dark"],
        },
        "dark_themes": sorted({*PLANTUML_DARK_BG, *MERMAID_DARK_BG, *D2_DARK_BG}),
        "types": {},
    }
    try:
        from ..core.config import MCP_SETTINGS

        families = {"plantuml": "plantuml", "c4plantuml": "plantuml"}
        for name, cfg in MCP_SETTINGS.diagram_types.items():
            backend = str(cfg.backend)
            data["types"][name] = {
                "theme_family": families.get(backend, backend)
                if backend in {"plantuml", "c4plantuml", "mermaid", "d2"}
                else "",
                "formats": [f for f in VIEWER_FORMATS if f in cfg.formats],
            }
    except Exception as exc:  # noqa: BLE001 - the viewer still works with generic options
        logger.debug("Diagram viewer: per-type options unavailable: %s", exc)
    return data


def diagram_viewer_html() -> str:
    """Return the Apps HTML document (no CDN, inline script only)."""
    payload = json.dumps(_viewer_data(), separators=(",", ":")).replace("</", "<\\/")
    return _DIAGRAM_VIEWER_HTML.replace(_THEME_DATA_PLACEHOLDER, payload)


def diagram_viewer_app_config() -> Any:
    """Tool-side AppConfig linking render tools to the viewer resource."""
    from fastmcp.apps import AppConfig

    return AppConfig(
        resource_uri=DIAGRAM_VIEWER_URI,
        visibility=["model", "app"],
    )


def diagram_viewer_app_only_config() -> Any:
    """App-only tool meta: callable from the viewer, hidden from the model."""
    from fastmcp.apps import AppConfig

    return AppConfig(
        resource_uri=DIAGRAM_VIEWER_URI,
        visibility=["app"],
    )


def diagram_viewer_resource_app_config() -> Any:
    """Resource-side AppConfig: CSP on the resource (SEP-1865 / FastMCP)."""
    from fastmcp.apps import AppConfig, ResourceCSP

    return AppConfig(
        domain=diagram_viewer_domain(),
        csp=ResourceCSP(
            connect_domains=[],
            resource_domains=["data:", "blob:"],
        ),
        prefers_border=False,
    )


def register_diagram_viewer(server: Any) -> list[str]:
    """Register ``ui://uml-mcp/diagram-viewer`` on a FastMCP server."""
    from fastmcp.apps import UI_MIME_TYPE

    def read_viewer() -> str:
        return diagram_viewer_html()

    resource_kwargs: dict[str, Any] = {
        "description": DIAGRAM_VIEWER_DESCRIPTION,
        "mime_type": UI_MIME_TYPE,
        "app": diagram_viewer_resource_app_config(),
    }
    try:
        server.resource(DIAGRAM_VIEWER_URI, **resource_kwargs)(read_viewer)
    except TypeError:
        # Mock / older FastMCP: drop app= then mime_type if needed.
        try:
            slim = {k: v for k, v in resource_kwargs.items() if k != "app"}
            server.resource(DIAGRAM_VIEWER_URI, **slim)(read_viewer)
        except TypeError:
            server.resource(DIAGRAM_VIEWER_URI)(read_viewer)
    return [DIAGRAM_VIEWER_URI]
