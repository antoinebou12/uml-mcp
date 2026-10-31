"""MCP Apps sandboxed diagram viewer (``ui://uml-mcp/diagram-viewer``).

Linked from the single and batch generation tools via tool ``_meta.ui``.
Hosts that do not advertise ``text/html;profile=mcp-app`` keep markdown /
ImageContent; hosts that do open this HTML with the tool result the host already
holds. The iframe never calls Kroki; re-render goes through the host as
``tools/call`` on the app-only ``rerender_diagram`` tool.
"""

from __future__ import annotations

import json
import logging
import os
import re
from ipaddress import ip_address
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
    domain = (
        os.environ.get("MCP_APP_DOMAIN", _DEFAULT_APP_DOMAIN).strip().removesuffix("/")
    )
    message = "MCP_APP_DOMAIN must be one HTTPS origin with a valid host and optional port, without credentials, a path, query or fragment"
    try:
        parsed = urlsplit(domain)
        port = parsed.port
        host = (parsed.hostname or "").encode("idna").decode("ascii")
    except ValueError:
        raise ValueError(message) from None
    try:
        ip_address(host)
        valid_host = True
    except ValueError:
        valid_host = (
            bool(host)
            and len(host) <= 253
            and all(
                re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", label)
                for label in host.split(".")
            )
        )
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
        or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in domain)
        or "\\" in domain
        or "?" in domain
        or "#" in domain
        or parsed.netloc.endswith(":")
        or port == 0
        or not valid_host
    ):
        raise ValueError(message)
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
    --danger-bg: rgba(198, 40, 40, 0.07);
    --warn: #a15c00;
    --ok: #1b873f;
    --dot: rgba(22, 26, 35, 0.09);
    --glass: rgba(255, 255, 255, 0.82);
    --shadow: 0 1px 2px rgba(16, 24, 40, 0.06), 0 6px 20px rgba(16, 24, 40, 0.08);
    --radius: 12px;
    --frame-h: min(65vh, 560px);
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
      --danger-bg: rgba(255, 138, 128, 0.08);
      --warn: #f5b041;
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
  button, a.btn, select, textarea { font: inherit; color: inherit; }
  :focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

  /* Header: type badge + status chip, link actions on the right. */
  #header { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 10px; }
  #brand { display: flex; align-items: center; gap: 8px; min-width: 0; flex: 1; }
  #brandMark {
    width: 24px; height: 24px; border-radius: 7px; flex: none;
    display: grid; place-items: center; font-size: 13px; font-weight: 700;
    color: var(--accent-fg); background: linear-gradient(135deg, var(--accent), #06b6d4);
  }
  #typeBadge {
    font: 600 12px/1 var(--mono); padding: 5px 8px; border-radius: 999px;
    background: var(--surface); border: 1px solid var(--border); white-space: nowrap;
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
  .btn.sm { height: 26px; padding: 0 9px; font-size: 12px; }

  /* Batch gallery: one card per diagram. */
  #gallery { display: flex; gap: 8px; overflow-x: auto; padding: 2px 2px 10px; scrollbar-width: thin; }
  .card {
    flex: none; width: 132px; padding: 6px; border-radius: 10px; cursor: pointer; text-align: left;
    border: 1px solid var(--border); background: var(--bg); display: grid; gap: 6px;
  }
  .card:hover { border-color: var(--muted); }
  .card[aria-selected="true"] { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent); }
  .card .thumb {
    height: 64px; border-radius: 6px; background: #ffffff; display: grid; place-items: center;
    overflow: hidden; color: #5d6472; font-size: 11px;
  }
  .card .thumb img { max-width: 100%; max-height: 100%; object-fit: contain; }
  .card .cap { display: flex; align-items: center; gap: 6px; font-size: 12px; min-width: 0; }
  .card .cap span:last-child { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: var(--mono); }
  .dot { width: 7px; height: 7px; border-radius: 50%; flex: none; background: var(--ok); }
  .dot.err { background: var(--danger); }
  .dot.wait { background: var(--muted); }

  /* View tabs. */
  #tabs { display: flex; gap: 2px; margin-bottom: 8px; border-bottom: 1px solid var(--border); }
  #tabs button {
    appearance: none; border: 0; background: transparent; cursor: pointer;
    padding: 6px 12px; color: var(--muted); border-bottom: 2px solid transparent; margin-bottom: -1px;
  }
  #tabs button[aria-selected="true"] { color: var(--fg); border-bottom-color: var(--accent); font-weight: 600; }
  #tabs .count {
    display: inline-block; min-width: 18px; padding: 0 5px; margin-left: 4px; border-radius: 999px;
    font-size: 11px; line-height: 16px; background: var(--danger); color: #fff; text-align: center;
  }

  /* Canvas: dotted board, diagram sits on a sheet of paper. */
  #stage { position: relative; }
  #frame {
    position: relative;
    display: flex; justify-content: center; align-items: center;
    min-height: 220px; height: var(--frame-h);
    border: 1px solid var(--border); border-radius: var(--radius);
    overflow: hidden;
    background-color: var(--surface);
    background-image: radial-gradient(var(--dot) 1px, transparent 1px);
    background-size: 16px 16px;
    touch-action: none; cursor: grab;
  }
  #frame.panning { cursor: grabbing; }
  #frame.static { cursor: default; touch-action: auto; overflow: auto; align-items: flex-start; }
  #frame > img, #frame > svg {
    flex: none; max-width: none; height: auto; display: block;
    transform-origin: center center;
    user-select: none; -webkit-user-drag: none;
    padding: 14px; border-radius: 10px;
    background: #ffffff; box-shadow: var(--shadow);
  }
  #frame.paper-dark > img, #frame.paper-dark > svg { background: #101217; }
  #frame pre.ascii {
    margin: 16px; padding: 14px; border-radius: 10px; background: #ffffff; color: #161a23;
    box-shadow: var(--shadow); font: 12px/1.35 var(--mono); white-space: pre; overflow: auto; max-width: 100%;
  }
  body.fullscreen { --frame-h: calc(100vh - 170px); }

  .empty { display: grid; justify-items: center; gap: 10px; color: var(--muted); text-align: center; padding: 24px; }
  .skeleton {
    width: min(320px, 70%); height: 120px; border-radius: 10px;
    background: linear-gradient(90deg, var(--border) 0%, var(--bg) 50%, var(--border) 100%);
    background-size: 200% 100%; animation: shimmer 1.4s linear infinite; opacity: .7;
  }
  #streamPreview {
    margin: 0; max-width: min(520px, 90%); max-height: 70%; overflow: hidden; text-align: left;
    font: 12px/1.4 var(--mono); color: var(--muted); white-space: pre-wrap;
    -webkit-mask-image: linear-gradient(180deg, transparent 0, #000 30%);
            mask-image: linear-gradient(180deg, transparent 0, #000 30%);
  }

  /* Error / notice cards inside the canvas. */
  .notice {
    margin: 16px; max-width: 560px; width: calc(100% - 32px); padding: 14px 16px; border-radius: 12px;
    border: 1px solid var(--border); background: var(--bg); box-shadow: var(--shadow); cursor: default;
  }
  .notice.error { border-color: var(--danger); background: linear-gradient(var(--danger-bg), var(--danger-bg)), var(--bg); }
  .notice h3 { margin: 0 0 6px; font-size: 14px; }
  .notice.error h3 { color: var(--danger); }
  .notice p { margin: 0 0 8px; overflow-wrap: anywhere; }
  .notice .where { font: 12px var(--mono); color: var(--muted); margin-bottom: 8px; }
  .notice .tip { padding: 8px 10px; border-radius: 8px; background: var(--surface); margin-bottom: 10px; }
  .notice .row-actions { display: flex; flex-wrap: wrap; gap: 6px; }
  .notice details { margin-bottom: 10px; color: var(--muted); font-size: 12px; }
  .notice details li { font-family: var(--mono); }

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

  /* Source editor. */
  #sourcePane { display: grid; gap: 8px; }
  #sourceEdit {
    width: 100%; height: var(--frame-h); min-height: 220px; resize: vertical;
    padding: 12px; border-radius: var(--radius); border: 1px solid var(--border);
    background: var(--surface); color: var(--fg); font: 12.5px/1.5 var(--mono); tab-size: 2;
  }
  #sourceBar { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
  #sourceBar .grow { flex: 1; }
  #sourceHint { color: var(--muted); font-size: 12px; }
  #checks { display: grid; gap: 4px; }
  .check {
    display: grid; grid-template-columns: 18px minmax(0, 1fr); gap: 6px; align-items: start;
    padding: 6px 8px; border-radius: 8px; background: var(--surface); font-size: 12px;
  }
  .check.err { color: var(--danger); }
  .check.warn { color: var(--warn); }
  .check.ok { color: var(--ok); }
  .check button { all: unset; cursor: pointer; text-decoration: underline; font-family: var(--mono); }

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
      <select id="exportFormat" aria-label="Download format"><option value="current">Current preview</option><option value="source">Source</option><option value="svg" selected>SVG</option><option value="png">PNG</option><option value="html">HTML</option><option value="pdf">PDF</option></select>
      <button type="button" class="btn" id="downloadBtn" title="Download the rendered file" hidden>Download</button>
      <button type="button" class="btn icon" id="fullscreenBtn" title="Toggle fullscreen" aria-label="Toggle fullscreen" hidden>⤢</button>
    </div>
  </div>
  <div id="gallery" role="tablist" aria-label="Diagrams in this batch" hidden></div>
  <div id="tabs" role="tablist" aria-label="View" hidden>
    <button type="button" role="tab" id="tabDiagram" aria-controls="stage" aria-selected="true">Diagram</button>
    <button type="button" role="tab" id="tabSource" aria-controls="sourcePane" aria-selected="false" tabindex="-1">Source<span class="count" id="issueCount" hidden></span></button>
  </div>
  <div id="stage" role="tabpanel" aria-labelledby="tabDiagram">
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
  <div id="sourcePane" role="tabpanel" aria-labelledby="tabSource" hidden>
    <textarea id="sourceEdit" spellcheck="false" autocapitalize="off" autocomplete="off" aria-label="Diagram source"></textarea>
    <div id="sourceBar">
      <button type="button" class="btn" id="checkBtn" title="Check syntax without rendering">Check</button>
      <button type="button" class="btn" id="revertBtn" title="Discard edits">Revert</button>
      <span id="sourceHint">Ctrl+Enter renders the edited source.</span>
      <span class="grow"></span>
      <button type="button" class="btn" id="copySource" title="Copy diagram source">Copy source</button>
    </div>
    <div id="checks" aria-live="polite"></div>
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
    <button type="button" class="btn primary" id="rerenderBtn" title="Re-render via app-only tools/call">Re-render</button>
  </div>
  <div id="meta"></div>
<script>
(function () {
  "use strict";
  var DATA = __UML_MCP_VIEWER_DATA__;
  var $ = function (id) { return document.getElementById(id); };
  var STATUS = $("status"), FRAME = $("frame"), META = $("meta"), TOOLBAR = $("toolbar");
  var REROW = $("rerenderRow"), LOADING = $("loading"), TYPE_BADGE = $("typeBadge");
  var ZOOM_LABEL = $("zoomLabel"), OPEN_URL = $("openUrl"), OPEN_PLAY = $("openPlay");
  var DOWNLOAD_BTN = $("downloadBtn"), FULLSCREEN_BTN = $("fullscreenBtn");
  var THEME_WRAP = $("themeWrap"), THEME_SEL = $("themeSelect"), FORMAT_SEL = $("formatSelect");
  var GALLERY = $("gallery"), TABS = $("tabs"), TAB_DIAGRAM = $("tabDiagram"), TAB_SOURCE = $("tabSource");
  var STAGE = $("stage"), SOURCE_PANE = $("sourcePane"), SOURCE_EDIT = $("sourceEdit");
  var CHECKS = $("checks"), ISSUE_COUNT = $("issueCount"), RERENDER_BTN = $("rerenderBtn");
  var MIN_ZOOM = 0.1, MAX_ZOOM = 8;
  var MAX_CONTEXT_SOURCE = 4000;
  var zoom = 1, fitZoom = 1;
  var panX = 0, panY = 0, panStart = null;
  var nextId = 1;
  var pending = Object.create(null);
  /** Host capabilities from ui/initialize; null = unknown (assume tools work). */
  var hostCaps = null;
  var displayMode = "inline";
  var view = "diagram";
  /** Rendered results: one for generate_uml / generate_uml_image, N for a batch. */
  var items = [];
  var current = 0;
  /** Arguments of the last call (single render) and per-index batch input. */
  var lastArgs = null;
  var batchInput = [];
  var STRIP_TAGS = {
    script: 1, foreignobject: 1, iframe: 1, object: 1, embed: 1, link: 1, meta: 1, base: 1
  };
  var EXT = { "image/png": "png", "image/jpeg": "jpg", "image/svg+xml": "svg", "application/pdf": "pdf", "text/plain": "txt" };

  // ------------------------------------------------------------ host bridge

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

  function can(cap) {
    if (cap === "serverTools") return !hostCaps || !!hostCaps.serverTools;
    return !!(hostCaps && hostCaps[cap]);
  }

  function errorText(err) {
    return (err && err.message) || (typeof err === "string" ? err : "the host rejected the request");
  }

  /** tools/call through the host; a CallToolResult with isError rejects. */
  function callTool(name, args) {
    return request("tools/call", { name: name, arguments: args }).then(function (result) {
      if (result && result.isError) throw new Error(textOf(result) || name + " failed");
      return result || {};
    });
  }

  function openLink(url) {
    if (!url) return;
    if (window.parent !== window) {
      request("ui/open-link", { url: url }).catch(function () {
        window.open(url, "_blank", "noopener");
      });
    } else {
      window.open(url, "_blank", "noopener");
    }
  }

  // ------------------------------------------------------------ SVG safety

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

  function decodeBase64Text(b64) {
    try {
      return new TextDecoder("utf-8", { fatal: true }).decode(
        Uint8Array.from(atob(b64), function (c) { return c.charCodeAt(0); })
      );
    } catch (e) { return ""; }
  }

  function safeUrl(value) {
    try {
      var url = new URL(String(value));
      return (url.protocol === "https:" || url.protocol === "http:") ? url.href : "";
    } catch (e) { return ""; }
  }

  // ------------------------------------------------------------ host context

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
    var dims = hostContext.containerDimensions;
    var limit = dims && (dims.height || dims.maxHeight);
    if (typeof limit === "number" && limit > 0 && displayMode !== "fullscreen") {
      // Leave room for header, tabs, controls and links below the canvas.
      var h = Math.max(220, Math.min(560, limit - 230));
      document.documentElement.style.setProperty("--frame-h", h + "px");
    }
  }

  function setDisplayMode(mode) {
    displayMode = mode === "fullscreen" ? "fullscreen" : "inline";
    document.body.classList.toggle("fullscreen", displayMode === "fullscreen");
    FULLSCREEN_BTN.textContent = displayMode === "fullscreen" ? "⤡" : "⤢";
    notifySize();
  }

  // ------------------------------------------------------------ status & zoom

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

  function notifySize() {
    var h = Math.max(document.body.scrollHeight, 160);
    notify("ui/notifications/size-changed", { height: h });
  }

  // ------------------------------------------------------------ small DOM helpers

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }

  function button(label, cls, onClick) {
    var b = el("button", "btn " + (cls || ""), label);
    b.type = "button";
    b.addEventListener("click", onClick);
    return b;
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

  // ------------------------------------------------------------ result model

  function textOf(params) {
    var parts = [];
    if (params && Array.isArray(params.content)) {
      params.content.forEach(function (c) {
        if (c && c.type === "text" && typeof c.text === "string") parts.push(c.text);
      });
    }
    return parts.join("\n").trim();
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
    return data && typeof data === "object" ? data : null;
  }

  function argsFor(index) {
    if (batchInput[index]) return batchInput[index];
    return index === 0 ? lastArgs : null;
  }

  /** Fill source/type/theme/format a result omits from the call arguments. */
  function withArgs(data, index) {
    var args = argsFor(index) || {};
    var out = Object.assign({}, data);
    if (!out.diagram_type && args.diagram_type) out.diagram_type = String(args.diagram_type);
    if (!out.code && args.code) { out.code = String(args.code); out.source_omitted = false; }
    if (out.theme == null && args.theme) out.theme = String(args.theme);
    if (!out.output_format && args.output_format) out.output_format = String(args.output_format);
    return out;
  }

  function isFailed(item) {
    return !!(item && (item.error || item.success === false));
  }

  function hasBytes(item) {
    return !!(item && item.content_base64);
  }

  function inlineFormat(item) {
    if ((typeInfo(item.diagram_type).formats || []).indexOf("svg") >= 0) return "svg";
    var f = String(item.output_format || "svg").toLowerCase();
    if (f === "jpg") f = "jpeg";
    return DATA.formats.indexOf(f) >= 0 ? f : "png";
  }

  // ------------------------------------------------------------ rendering

  function showEmpty(text) {
    FRAME.classList.add("static");
    FRAME.textContent = "";
    var box = el("div", "empty");
    box.appendChild(el("div", "", text));
    FRAME.appendChild(box);
    TOOLBAR.hidden = true;
  }

  function mount(node) {
    FRAME.classList.remove("static");
    FRAME.textContent = "";
    FRAME.appendChild(node);
    TOOLBAR.hidden = false;
  }

  function renderNotice(item, opts) {
    FRAME.classList.add("static");
    FRAME.textContent = "";
    TOOLBAR.hidden = true;
    var card = el("div", "notice" + (opts.error ? " error" : ""));
    card.setAttribute("role", opts.error ? "alert" : "note");
    card.appendChild(el("h3", "", opts.title));
    card.appendChild(el("p", "", opts.message));
    var detail = item.error_detail || {};
    if (detail.line) {
      card.appendChild(el("div", "where",
        "Line " + detail.line + (detail.column ? ", column " + detail.column : "")));
    }
    if (detail.suggestion) card.appendChild(el("div", "tip", "💡 " + detail.suggestion));
    if (Array.isArray(item.attempts) && item.attempts.length) {
      var d = el("details");
      d.appendChild(el("summary", "", "Renderers tried (" + item.attempts.length + ")"));
      var ul = el("ul");
      item.attempts.forEach(function (a) {
        ul.appendChild(el("li", "", [a.backend, a.ok ? "ok" : "failed", a.status,
          a.duration_ms != null ? a.duration_ms + " ms" : "", a.error_summary || ""]
          .filter(function (x) { return x !== undefined && x !== null && x !== ""; }).join(" · ")));
      });
      d.appendChild(ul);
      card.appendChild(d);
    }
    var actions = el("div", "row-actions");
    (opts.actions || []).forEach(function (a) { actions.appendChild(a); });
    if (actions.childNodes.length) card.appendChild(actions);
    FRAME.appendChild(card);
  }

  function errorActions(item) {
    var acts = [];
    if (item.code) {
      acts.push(button("Edit source", "primary", function () {
        setView("source");
        var line = item.error_detail && item.error_detail.line;
        if (line) selectLine(line);
      }));
    }
    if (item.code && can("serverTools")) acts.push(button("Retry", "", function () { rerender(); }));
    if (can("message")) {
      acts.push(button("Ask assistant to fix", "", function (ev) { askToFix(item, ev.currentTarget); }));
    }
    var play = safeUrl(item.playground);
    if (play) acts.push(button("Open playground ↗", "", function () { openLink(play); }));
    return acts;
  }

  function renderItem() {
    var item = items[current];
    zoom = 1;
    panX = panY = 0;
    FRAME.classList.remove("paper-dark");
    if (!item) {
      showEmpty("No diagram in this tool result.");
      setStatus("No diagram data in tool result.", true);
      REROW.className = "";
      return;
    }
    loadFullPreview(item);
    if (item.diagram_type) {
      TYPE_BADGE.textContent = String(item.diagram_type);
      TYPE_BADGE.hidden = false;
    }
    syncSource();
    updateRerenderRow();
    updateGallery();
    if (isFailed(item)) {
      renderNotice(item, {
        error: true,
        title: "This diagram did not render",
        message: String(item.error || "The renderer rejected the source."),
        actions: errorActions(item)
      });
      setStatus(String(item.error || "Render failed"), true);
      showLinks(item);
      return;
    }
    var mime = String(item.mime_type || "").toLowerCase();
    var b64 = item.content_base64;
    var ready = item.preview_resized ? "Compact preview" : "Diagram ready";
    if (items.length > 1) {
      var failed = items.filter(isFailed).length;
      ready += " · " + (current + 1) + " of " + items.length + (failed ? " · " + failed + " failed" : "");
    }
    if (b64 && (mime === "image/png" || mime === "image/jpeg" || mime.indexOf("jpeg") >= 0)) {
      var img = el("img");
      img.alt = (item.diagram_type || "diagram") + " diagram";
      img.addEventListener("load", autoFit);
      img.src = "data:" + (mime || "image/png") + ";base64," + b64;
      mount(img);
      setStatus(ready, "ok");
      showLinks(item);
      applyZoom();
      return;
    }
    if (b64 && mime.indexOf("svg") >= 0) {
      var clean = sanitizeSvg(decodeBase64Text(b64));
      if (clean) {
        FRAME.classList.remove("static");
        FRAME.innerHTML = clean;
        TOOLBAR.hidden = false;
        setStatus(ready, "ok");
        showLinks(item);
        autoFit();
        return;
      }
    }
    if (b64 && mime.indexOf("text/") === 0) {
      FRAME.classList.add("static");
      FRAME.textContent = "";
      FRAME.appendChild(el("pre", "ascii", decodeBase64Text(b64)));
      TOOLBAR.hidden = true;
      setStatus("Text diagram ready", "ok");
      showLinks(item);
      return;
    }
    // URL-only: never fetch Kroki from the iframe. Ask the server for inline
    // bytes once (app-only rerender_diagram), otherwise show links.
    if (!b64 && item.code && item.diagram_type && can("serverTools") && !item._previewTried &&
        !item.inline_omitted) {
      item._previewTried = true;
      showEmpty("Loading an inline preview…");
      setBusy(true);
      setStatus("Loading preview…", "busy");
      showLinks(item);
      var idx = current;
      callTool("rerender_diagram", {
        diagram_type: item.diagram_type, code: item.code,
        theme: item.theme || null, output_format: inlineFormat(item)
      }).then(function (result) {
        var data = extractStructured(result);
        if (data && data.content_base64) {
          items[idx] = Object.assign({}, item, data, { output_format: data.output_format || inlineFormat(item),
            url: data.url || item.url, playground: data.playground || item.playground, _previewTried: true });
        }
      }).catch(function () { /* links stay usable */ }).finally(function () {
        setBusy(false);
        if (idx === current) renderItem();
      });
      return;
    }
    var pdf = mime.indexOf("pdf") >= 0 || String(item.output_format || "").toLowerCase() === "pdf";
    renderNotice(item, {
      title: pdf ? "PDF ready" : "Rendered as a link",
      message: item.inline_note || (pdf
        ? "PDF output can't be previewed here. Open or download it, or re-render as SVG to preview."
        : "This result has links only (no inline image). Open it, or re-render as PNG or SVG."),
      actions: [].concat(
        safeUrl(item.url) ? [button("Open " + (pdf ? "PDF" : "image") + " ↗", "primary", function () { openLink(safeUrl(item.url)); })] : [],
        item.code && can("serverTools") ? [button("Preview as SVG", "", function () {
          FORMAT_SEL.value = "svg";
          rerender();
        })] : []
      )
    });
    setStatus(
      item.inline_note ||
      (b64 ? "Could not display image bytes; use the URL below." : "URL-only result (no inline bytes)."),
      Boolean(item.inline_omitted && !item.url)
    );
    showLinks(item);
    notifySize();
  }

  // ------------------------------------------------------------ links & meta

  function linkRow(label, href) {
    var row = el("div", "row");
    row.appendChild(el("span", "k", label));
    var a = el("a", "", href);
    a.href = href;
    a.target = "_blank";
    a.rel = "noopener";
    a.title = href;
    a.addEventListener("click", function (ev) {
      if (can("openLinks")) { ev.preventDefault(); openLink(href); }
    });
    row.appendChild(a);
    var b = button("Copy", "sm", function () { copyText(href, b); });
    row.appendChild(b);
    return row;
  }

  function statChips(item) {
    var chips = [];
    if (item.output_format) chips.push(String(item.output_format).toUpperCase());
    if (item.theme) chips.push("theme: " + item.theme);
    if (item.source) chips.push(String(item.source));
    if (typeof item.render_ms === "number") chips.push(Math.round(item.render_ms) + " ms");
    if (item.cache_hit) chips.push("cached");
    if (item.fallback_used) chips.push("fallback renderer");
    if (item.preview_resized) chips.push("compact preview");
    if (!chips.length) return null;
    var wrap = el("div", "chips");
    chips.forEach(function (text) { wrap.appendChild(el("span", "chip", text)); });
    return wrap;
  }

  function showLinks(item) {
    var url = safeUrl(item.url);
    var playground = safeUrl(item.playground);
    META.textContent = "";
    OPEN_URL.hidden = !url;
    OPEN_PLAY.hidden = !playground;
    if (url) OPEN_URL.href = url;
    if (playground) OPEN_PLAY.href = playground;
    DOWNLOAD_BTN.hidden = !((item.code && can("serverTools")) || hasBytes(item));
    if (item.mime_type === "text/plain" || !can("serverTools")) $("exportFormat").value = "current";
    $("exportFormat").hidden = DOWNLOAD_BTN.hidden;
    Array.from($("exportFormat").options).forEach(function(option) {
      option.disabled = option.value !== "current" && !can("serverTools");
    });
    $("exportFormat").querySelector('option[value="pdf"]').disabled = !can("serverTools") || (typeInfo(item.diagram_type).native_formats || []).indexOf("pdf") < 0;
    var chips = statChips(item);
    if (chips) META.appendChild(chips);
    TOOLBAR.hidden = !media();
    notifySize();
  }

  async function readExport(item, format, source, theme) {
    var args = {diagram_type:item.diagram_type,code:source || item.code,
      output_format:format,theme:theme || null,offset:0};
    var encoded = "", checksum = null, file;
    do {
      if (checksum) args.sha256 = checksum;
      file = extractStructured(await callTool("download_diagram", args));
      if (!file || file.error) throw new Error(file && file.error || "No download data returned");
      if (typeof file.chunk !== "string" || file.chunk.length > 32000 ||
          file.offset !== args.offset || file.next_offset !== args.offset + file.chunk.length ||
          file.next_offset <= args.offset || file.total > 11000000 ||
          file.next_offset > file.total || (checksum && checksum !== file.sha256))
        throw new Error("Invalid download sequence. Try again.");
      checksum = file.sha256; encoded += file.chunk; args.offset = file.next_offset;
    } while (args.offset < file.total);
    return {file:file,encoded:encoded};
  }

  function loadFullPreview(item) {
    if (!item || !item.code || !can("serverTools") || item._fullTried ||
        !(item.preview_resized || item.inline_omitted ||
          (item.mime_type && item.mime_type.indexOf("image/") === 0 && item.mime_type !== "image/svg+xml" && (typeInfo(item.diagram_type).formats || []).indexOf("svg") >= 0))) return;
    item._fullTried = true;
    var format = item._requestedFormat || ((typeInfo(item.diagram_type).formats || []).indexOf("svg") >= 0 || item.output_format === "svg" ? "svg" : "png");
    readExport(item, format, item.code, item.theme).then(function(result) {
      item.content_base64 = result.encoded; item.mime_type = result.file.mime_type; item.output_format = format;
      item.preview_resized = false; item.inline_omitted = false; item.inline_note = "";
      if (items[current] === item) renderItem();
    }).catch(function() { /* Keep the bounded preview and download controls usable. */ });
  }

  async function download() {
    var item = items[current];
    if (!item) return;
    DOWNLOAD_BTN.disabled = true;
    try {
      var format = $("exportFormat").value;
      var result = format === "current" ? {encoded:item.content_base64, file:{filename:String(item.diagram_type || "diagram").replace(/[^a-z0-9_-]/gi,"-") + "." + (EXT[item.mime_type] || "bin"),mime_type:item.mime_type}} :
        await readExport(item, format, SOURCE_EDIT.value || item.code, THEME_SEL.value || item.theme);
      var file = result.file, encoded = result.encoded;
      if (can("downloadFile")) {
        await request("ui/download-file", {contents:[{type:"resource",resource:{
          uri:"file:///" + file.filename,mimeType:file.mime_type,blob:encoded}}]});
      } else {
        var bytes = Uint8Array.from(atob(encoded), function(c) { return c.charCodeAt(0); });
        var blobUrl = URL.createObjectURL(new Blob([bytes], {type:file.mime_type}));
        var anchor = document.createElement("a"); anchor.href = blobUrl;
        anchor.download = file.filename; document.body.appendChild(anchor); anchor.click(); anchor.remove();
        setTimeout(function() { URL.revokeObjectURL(blobUrl); }, 60000);
      }
      setStatus("Download ready", "ok");
    } catch (err) { setStatus("Download failed: " + errorText(err), true); }
    finally { DOWNLOAD_BTN.disabled = false; }
  }

  // ------------------------------------------------------------ batch gallery

  function thumbFor(item) {
    var box = el("div", "thumb");
    var mime = String(item.mime_type || "").toLowerCase();
    if (isFailed(item)) {
      box.textContent = "Error";
    } else if (item.content_base64 && /^image\/(png|jpeg|svg\+xml)$/.test(mime)) {
      // <img> never runs scripts, so SVG thumbnails need no sanitizing here.
      var img = el("img");
      img.alt = "";
      img.src = "data:" + mime + ";base64," + item.content_base64;
      box.appendChild(img);
    } else {
      box.textContent = item.url ? "Link" : "No preview";
    }
    return box;
  }

  function updateGallery() {
    GALLERY.hidden = items.length < 2;
    if (items.length < 2) return;
    GALLERY.textContent = "";
    items.forEach(function (item, i) {
      var card = el("button", "card");
      card.type = "button";
      card.setAttribute("role", "tab");
      card.setAttribute("aria-selected", i === current ? "true" : "false");
      card.tabIndex = i === current ? 0 : -1;
      card.title = (i + 1) + ". " + (item.diagram_type || "diagram") + (isFailed(item) ? " — failed" : "");
      card.appendChild(thumbFor(item));
      var cap = el("div", "cap");
      cap.appendChild(el("span", "dot" + (isFailed(item) ? " err" : "")));
      cap.appendChild(el("span", "", (i + 1) + " · " + (item.diagram_type || "diagram")));
      card.appendChild(cap);
      card.addEventListener("click", function () {
        if (i === current) return;
        current = i;
        renderItem();
      });
      GALLERY.appendChild(card);
    });
  }

  // ------------------------------------------------------------ source tab

  function setView(next) {
    view = next === "source" ? "source" : "diagram";
    TAB_DIAGRAM.setAttribute("aria-selected", view === "diagram" ? "true" : "false");
    TAB_SOURCE.setAttribute("aria-selected", view === "source" ? "true" : "false");
    TAB_DIAGRAM.tabIndex = view === "diagram" ? 0 : -1;
    TAB_SOURCE.tabIndex = view === "source" ? 0 : -1;
    STAGE.hidden = view !== "diagram";
    SOURCE_PANE.hidden = view !== "source";
    if (view === "source") SOURCE_EDIT.focus();
    notifySize();
  }

  function syncSource() {
    var item = items[current];
    var code = item && item.code ? String(item.code) : "";
    TABS.hidden = !code;
    if (!code && view === "source") setView("diagram");
    SOURCE_EDIT.value = code;
    SOURCE_EDIT.readOnly = !can("serverTools");
    $("checkBtn").hidden = !can("serverTools");
    $("sourceHint").hidden = !can("serverTools");
    CHECKS.textContent = "";
    var detail = item && item.error_detail;
    var count = isFailed(item) ? 1 : 0;
    ISSUE_COUNT.hidden = !count;
    ISSUE_COUNT.textContent = String(count);
    if (isFailed(item)) {
      CHECKS.appendChild(checkLine("err", String(item.error || "Render failed"), detail && detail.line));
    }
  }

  function selectLine(line) {
    var lines = SOURCE_EDIT.value.split("\n");
    var n = Math.max(1, Math.min(lines.length, Number(line) || 1));
    var start = 0;
    for (var i = 0; i < n - 1; i++) start += lines[i].length + 1;
    SOURCE_EDIT.focus();
    SOURCE_EDIT.setSelectionRange(start, start + lines[n - 1].length);
    var lineHeight = parseFloat(getComputedStyle(SOURCE_EDIT).lineHeight) || 18;
    SOURCE_EDIT.scrollTop = Math.max(0, (n - 4) * lineHeight);
  }

  function checkLine(kind, text, line) {
    var row = el("div", "check " + kind);
    row.appendChild(el("span", "", kind === "ok" ? "✓" : kind === "warn" ? "!" : "✕"));
    var body = el("span", "");
    if (line) {
      var go = el("button", "", "L" + line);
      go.type = "button";
      go.title = "Go to line " + line;
      go.addEventListener("click", function () { selectLine(line); });
      body.appendChild(go);
      body.appendChild(document.createTextNode(" "));
    }
    body.appendChild(document.createTextNode(text));
    row.appendChild(body);
    return row;
  }

  function showValidation(result) {
    CHECKS.textContent = "";
    var issues = 0;
    (result.diagnostics || []).forEach(function (d) {
      var sev = String(d.severity || "error").toLowerCase();
      var kind = sev.indexOf("warn") === 0 ? "warn" : sev.indexOf("info") === 0 ? "ok" : "err";
      if (kind === "err") issues++;
      CHECKS.appendChild(checkLine(kind, String(d.message || d.code || "Issue"), d.line));
    });
    if (!(result.diagnostics || []).length) {
      (result.errors || []).forEach(function (m) { issues++; CHECKS.appendChild(checkLine("err", String(m))); });
      (result.warnings || []).forEach(function (m) { CHECKS.appendChild(checkLine("warn", String(m))); });
    }
    (result.suggestions || []).forEach(function (m) { CHECKS.appendChild(checkLine("ok", "Tip: " + m)); });
    if (result.valid && !issues) CHECKS.insertBefore(checkLine("ok", "Source looks valid."), CHECKS.firstChild);
    ISSUE_COUNT.hidden = !issues;
    ISSUE_COUNT.textContent = String(issues);
    notifySize();
  }

  function checkSource() {
    var item = items[current];
    if (!item || !item.diagram_type) return;
    var btn = $("checkBtn");
    btn.disabled = true;
    CHECKS.textContent = "";
    CHECKS.appendChild(checkLine("ok", "Checking…"));
    callTool("validate_uml", {
      diagram_type: item.diagram_type, code: SOURCE_EDIT.value,
      output_format: FORMAT_SEL.value || "svg", strict: true
    }).then(function (result) {
      showValidation(extractStructured(result) || {});
    }).catch(function (err) {
      CHECKS.textContent = "";
      CHECKS.appendChild(checkLine("err", "Check failed: " + errorText(err)));
    }).finally(function () { btn.disabled = false; });
  }

  // ------------------------------------------------------------ re-render

  function typeInfo(diagramType) {
    return (DATA.types && DATA.types[diagramType]) || {};
  }

  function fillSelect(select, values, value, defaultLabel) {
    select.textContent = "";
    if (defaultLabel) {
      var def = el("option", "", defaultLabel);
      def.value = "";
      select.appendChild(def);
    }
    var list = values.slice();
    if (value && list.indexOf(value) < 0) list.push(value);
    list.forEach(function (v) {
      var opt = el("option", "", defaultLabel ? v : v.toUpperCase());
      opt.value = v;
      select.appendChild(opt);
    });
    select.value = value || (defaultLabel ? "" : list[0] || "");
  }

  function updateRerenderRow() {
    var item = items[current];
    var ok = !!(item && item.code && item.diagram_type && can("serverTools"));
    REROW.className = ok ? "visible" : "";
    if (!item || !item.diagram_type) return;
    var info = typeInfo(item.diagram_type);
    var themes = (DATA.themes && DATA.themes[info.theme_family]) || [];
    var theme = item.theme != null ? String(item.theme) : "";
    THEME_WRAP.hidden = !themes.length && !theme;
    fillSelect(THEME_SEL, themes, theme, "Default");
    var format = String(item.output_format || "png").toLowerCase();
    if (format === "jpg") format = "jpeg";
    var formats = info.formats && info.formats.length ? info.formats : DATA.formats;
    fillSelect(FORMAT_SEL, formats, formats.indexOf(format) >= 0 ? format : "", "");
    FRAME.classList.toggle("paper-dark", (DATA.dark_themes || []).indexOf(theme.toLowerCase()) >= 0);
  }

  function rerender() {
    var item = items[current];
    if (!item || !item.diagram_type) {
      setStatus("Nothing to re-render yet.", true);
      return;
    }
    var code = SOURCE_EDIT.value || item.code;
    if (!code) {
      setStatus("The source was too large to send back; ask the assistant to re-render.", true);
      return;
    }
    var args = {
      diagram_type: item.diagram_type,
      code: code,
      theme: THEME_SEL.value || null,
      output_format: FORMAT_SEL.value || inlineFormat(item)
    };
    if (RERENDER_BTN.disabled) return;
    RERENDER_BTN.disabled = true;
    setBusy(true);
    setStatus("Re-rendering…", "busy");
    var idx = current;
    request("tools/call", { name: "rerender_diagram", arguments: args })
      .then(function (result) {
        var data = result && result.isError
          ? { error: textOf(result) || "Render failed", success: false }
          : extractStructured(result) || {};
        items[idx] = Object.assign({ index: item.index }, args, data, { _previewTried: true, _requestedFormat: args.output_format });
        // The source the user sent is the truth (a bounded result may omit it).
        items[idx].code = args.code;
        if (idx === current) renderItem();
        if (!isFailed(items[idx])) {
          if (view === "source") setView("diagram");
          shareContext(items[idx]);
        }
      })
      .catch(function (err) {
        setStatus("Re-render failed: " + errorText(err), true);
      }).finally(function () {
        RERENDER_BTN.disabled = false;
        setBusy(false);
      });
  }

  /** Tell the model what the user now sees (theme, format, edited source). */
  function shareContext(item) {
    if (!can("updateModelContext") || !item) return;
    var code = String(item.code || "");
    if (code.length > MAX_CONTEXT_SOURCE) code = code.slice(0, MAX_CONTEXT_SOURCE) + "\n…";
    var text = "In the UML-MCP viewer the user re-rendered the " + (item.diagram_type || "") +
      " diagram" + (item.theme ? " with theme " + item.theme : "") +
      " as " + String(item.output_format || "").toUpperCase() + "." +
      (safeUrl(item.url) ? " Render URL: " + safeUrl(item.url) : "") +
      "\nCurrent source:\n```\n" + code + "\n```";
    request("ui/update-model-context", {
      content: [{ type: "text", text: text }],
      structuredContent: {
        diagram_type: item.diagram_type, theme: item.theme || null,
        output_format: item.output_format, url: safeUrl(item.url) || null, code: code
      }
    }).catch(function () { /* optional host feature */ });
  }

  function askToFix(item, btn) {
    var code = String(SOURCE_EDIT.value || item.code || "");
    if (code.length > MAX_CONTEXT_SOURCE) code = code.slice(0, MAX_CONTEXT_SOURCE) + "\n…";
    var detail = item.error_detail || {};
    var text = "The " + (item.diagram_type || "") + " diagram failed to render: " +
      String(item.error || "unknown error") +
      (detail.line ? " (line " + detail.line + ")" : "") +
      ". Please fix the source and render it again.\n\n```\n" + code + "\n```";
    btn.disabled = true;
    request("ui/message", { role: "user", content: { type: "text", text: text } })
      .then(function () { btn.textContent = "Sent to assistant ✓"; })
      .catch(function (err) { btn.disabled = false; setStatus("Could not send: " + errorText(err), true); });
  }

  // ------------------------------------------------------------ host notifications

  function onToolResult(params) {
    setBusy(false);
    params = params || {};
    var data = extractStructured(params);
    current = 0;
    if (params.isError || !data) {
      var msg = textOf(params);
      items = [withArgs({ error: msg || "The tool returned no diagram.", success: false }, 0)];
      if (!msg && !data) {
        showEmpty("No diagram in this tool result.");
        setStatus("No diagram data in tool result.", true);
        TOOLBAR.hidden = true;
        REROW.className = "";
        return;
      }
    } else if (Array.isArray(data.results)) {
      items = data.results.map(function (row, i) {
        var index = row && typeof row.index === "number" ? row.index : i;
        return withArgs(row || {}, index);
      });
      if (!items.length) items = [{ error: data.error || "The batch returned no diagrams.", success: false }];
      var firstOk = items.findIndex(function (it) { return !isFailed(it); });
      current = firstOk >= 0 ? firstOk : 0;
    } else {
      items = [withArgs(data, 0)];
    }
    renderItem();
  }

  function rememberInput(args) {
    if (!args || typeof args !== "object") return;
    if (Array.isArray(args.items)) {
      batchInput = args.items.map(function (it) { return it && typeof it === "object" ? it : {}; });
      lastArgs = null;
      setStatus("Rendering " + batchInput.length + " diagrams…", "busy");
      return;
    }
    if (args.diagram_type || args.code) {
      lastArgs = {
        diagram_type: args.diagram_type ? String(args.diagram_type) : "",
        code: args.code ? String(args.code) : "",
        theme: args.theme != null ? String(args.theme) : "",
        output_format: args.output_format ? String(args.output_format) : "png"
      };
      batchInput = [];
      if (lastArgs.diagram_type) {
        TYPE_BADGE.textContent = lastArgs.diagram_type;
        TYPE_BADGE.hidden = false;
      }
    }
  }

  function onToolInput(params) {
    rememberInput((params && params.arguments) || params || {});
    if (!media() && !items.length) {
      setBusy(true);
      if (lastArgs) setStatus("Rendering…", "busy");
      if (lastArgs && lastArgs.diagram_type && lastArgs.code) {
        items = [Object.assign({ _pending: true }, lastArgs)];
        syncSource();
        updateRerenderRow();
      }
    }
  }

  function onToolInputPartial(params) {
    var args = (params && params.arguments) || {};
    if (items.length && !items[0]._pending) return;
    if (args.diagram_type) {
      TYPE_BADGE.textContent = String(args.diagram_type);
      TYPE_BADGE.hidden = false;
    }
    var code = typeof args.code === "string" ? args.code : "";
    var count = Array.isArray(args.items) ? args.items.length : 0;
    setStatus(count ? "Writing " + count + " diagram(s)…" :
      code ? "Writing diagram source… " + code.split("\n").length + " lines" : "Preparing diagram…", "busy");
    if (code) {
      FRAME.classList.add("static");
      var pre = $("streamPreview");
      if (!pre) {
        FRAME.textContent = "";
        pre = el("pre");
        pre.id = "streamPreview";
        var wrap = el("div", "empty");
        wrap.appendChild(pre);
        FRAME.appendChild(wrap);
      }
      pre.textContent = code.split("\n").slice(-14).join("\n");
    }
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
    } else if (msg.method === "ui/notifications/tool-input-partial") {
      onToolInputPartial(msg.params || {});
    } else if (msg.method === "ui/notifications/tool-cancelled") {
      setBusy(false);
      setStatus("Tool cancelled" + (msg.params && msg.params.reason ? ": " + msg.params.reason : ""), true);
    } else if (msg.method === "ui/notifications/host-context-changed") {
      applyHostContext(msg.params || {});
    } else if (msg.method === "ui/resource-teardown" && msg.id != null) {
      post({ jsonrpc: "2.0", id: msg.id, result: {} });
    }
  });

  // ------------------------------------------------------------ controls

  $("zoomIn").addEventListener("click", function () { zoomBy(1.25); });
  $("zoomOut").addEventListener("click", function () { zoomBy(0.8); });
  $("zoomFit").addEventListener("click", fitDiagram);
  $("zoomReset").addEventListener("click", function () {
    zoom = 1;
    panX = panY = 0;
    applyZoom();
  });
  TAB_DIAGRAM.addEventListener("click", function () { setView("diagram"); });
  TAB_SOURCE.addEventListener("click", function () { setView("source"); });
  TABS.addEventListener("keydown", function (event) {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    var next = event.key === "Home" ? "diagram" : event.key === "End" ? "source" : view === "diagram" ? "source" : "diagram";
    setView(next);
    (next === "source" ? TAB_SOURCE : TAB_DIAGRAM).focus();
  });
  GALLERY.addEventListener("keydown", function (event) {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    current = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1 : (current + (event.key === "ArrowRight" ? 1 : -1) + items.length) % items.length;
    renderItem();
    GALLERY.querySelector('[aria-selected="true"]').focus();
  });
  $("copySource").addEventListener("click", function (event) {
    if (SOURCE_EDIT.value) copyText(SOURCE_EDIT.value, event.currentTarget);
  });
  $("checkBtn").addEventListener("click", checkSource);
  $("revertBtn").addEventListener("click", function () {
    syncSource();
  });
  SOURCE_EDIT.addEventListener("keydown", function (event) {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      rerender();
    } else if (event.key === "Tab" && !event.shiftKey && !SOURCE_EDIT.readOnly) {
      event.preventDefault();
      var s = SOURCE_EDIT.selectionStart;
      SOURCE_EDIT.setRangeText("  ", s, SOURCE_EDIT.selectionEnd, "end");
    }
  });
  [OPEN_URL, OPEN_PLAY].forEach(function (a) {
    a.addEventListener("click", function (ev) {
      ev.preventDefault(); openLink(a.href);
    });
  });
  FRAME.addEventListener("click", function(ev) {
    var a = ev.target.closest && ev.target.closest("a");
    if (!a) return;
    var href = safeUrl(a.getAttribute("href") || a.getAttribute("xlink:href"));
    if (href) { ev.preventDefault(); openLink(href); }
  });
  DOWNLOAD_BTN.addEventListener("click", download);
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
    if (event.altKey || event.ctrlKey || event.metaKey ||
        /INPUT|TEXTAREA|SELECT|BUTTON/.test(document.activeElement.tagName) || view !== "diagram") return;
    if (event.key === "+" || event.key === "=") { zoomBy(1.25); }
    else if (event.key === "-") { zoomBy(0.8); }
    else if (event.key === "0") { zoom = 1; panX = panY = 0; applyZoom(); }
    else if (event.key.toLowerCase() === "f") { fitDiagram(); }
    else if (event.key === "ArrowRight" && items.length > 1) { current = (current + 1) % items.length; renderItem(); }
    else if (event.key === "ArrowLeft" && items.length > 1) { current = (current + items.length - 1) % items.length; renderItem(); }
    else return;
    event.preventDefault();
  });
  RERENDER_BTN.addEventListener("click", rerender);

  request("ui/initialize", {
    appInfo: { name: "uml-mcp-diagram-viewer", version: "1.4.0" },
    appCapabilities: { availableDisplayModes: ["inline", "fullscreen"] }
  }).then(function (result) {
    hostCaps = (result && result.hostCapabilities) || null;
    applyHostContext(result && result.hostContext);
    notify("ui/notifications/initialized", {});
    if (!media() && !items.length) setStatus("Ready — waiting for tool result…");
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
            "plugin:d3": ["light", "dark", "auto"],
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
                if backend in {"plantuml", "c4plantuml", "mermaid", "d2", "plugin:d3"}
                else "",
                "native_formats": list(cfg.formats),
                "formats": [
                    f
                    for f in VIEWER_FORMATS
                    if f in cfg.formats
                    or (backend == "plugin:d3" and f in {"svg", "png"})
                ],
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
