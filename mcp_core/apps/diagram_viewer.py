"""MCP Apps sandboxed diagram viewer (``ui://uml-mcp/diagram-viewer``).

Linked from ``generate_uml`` / ``generate_uml_image`` via tool ``_meta.ui``.
Hosts that do not advertise ``text/html;profile=mcp-app`` keep markdown /
ImageContent; hosts that do open this HTML with the tool result the host already
holds. The iframe never calls Kroki; re-render goes through the host as
``tools/call`` on the app-only ``rerender_diagram`` tool.
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlsplit

DIAGRAM_VIEWER_URI = "ui://uml-mcp/diagram-viewer"
DIAGRAM_VIEWER_DESCRIPTION = (
    "Interactive UML-MCP diagram viewer with zoom, pan, fit, reset and a "
    "safe render preview. SVG, PNG and JPEG results are supported."
)
# All app views must agree on an exact HTTPS origin. Override for other
# trusted deployments, e.g. MCP_APP_DOMAIN=https://uml-mcp.vercel.app.
_DEFAULT_APP_DOMAIN = "https://fast-steel-xf470.run.mcp-use.com"


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


# Self-contained HTML: postMessage bridge + SVG sanitize (mirrors svg_sanitize.py).
_DIAGRAM_VIEWER_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>UML-MCP diagram</title>
<style>
  :root {
    color-scheme: light dark;
    --bg: var(--color-background-primary, #fff);
    --fg: var(--color-text-primary, #111);
    --muted: var(--color-text-secondary, #555);
    --border: var(--color-border-primary, #ddd);
    --link: var(--color-text-link, #0b57d0);
    --font: var(--font-sans, system-ui, sans-serif);
  }
  * { box-sizing: border-box; }
  [hidden] { display: none !important; }
  button:focus-visible, a:focus-visible, select:focus-visible { outline: 2px solid var(--link); outline-offset: 2px; }
  body {
    margin: 0;
    padding: 12px;
    font-family: var(--font);
    background: var(--bg);
    color: var(--fg);
  }
  #status { font-size: 13px; color: var(--muted); margin-bottom: 8px; }
  #toolbar {
    display: flex; flex-wrap: wrap; gap: 6px; align-items: center;
    margin-bottom: 8px; font-size: 13px;
  }
  #toolbar button, #toolbar a.btn {
    appearance: none; border: 1px solid var(--border); background: var(--bg);
    color: var(--fg); border-radius: 6px; padding: 4px 10px; cursor: pointer;
    font: inherit; text-decoration: none;
  }
  #toolbar button:hover, #toolbar a.btn:hover { border-color: var(--muted); }
  #toolbar .spacer { flex: 1; }
  #zoomLabel { color: var(--muted); min-width: 3em; }
  #toolbar select {
    border: 1px solid var(--border); background: var(--bg); color: var(--fg);
    border-radius: 6px; padding: 4px 8px; font: inherit;
  }
  #rerenderRow { display: none; flex-wrap: wrap; gap: 6px; align-items: center;
    margin-bottom: 8px; font-size: 13px; }
  #rerenderRow.visible { display: flex; }
  #frame {
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 280px;
    height: min(65vh, 560px);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 8px;
    overflow: hidden;
    background: var(--bg);
    touch-action: none;
    cursor: grab;
  }
  #frame.panning { cursor: grabbing; }
  #frame img, #frame svg {
    max-width: none; height: auto; display: block;
    transform-origin: center center;
    user-select: none;
    -webkit-user-drag: none;
  }
  #meta { margin-top: 10px; font-size: 13px; line-height: 1.45; }
  #meta a { color: var(--link); word-break: break-all; }
  .err { color: #b00020; }
</style>
</head>
<body>
  <div id="status" role="status" aria-live="polite">Waiting for diagram…</div>
  <div id="toolbar" hidden>
    <button type="button" id="zoomOut" aria-label="Zoom out" title="Zoom out">−</button>
    <span id="zoomLabel">100%</span>
    <button type="button" id="zoomIn" aria-label="Zoom in" title="Zoom in">+</button>
    <button type="button" id="zoomFit" title="Fit entire diagram" aria-label="Fit diagram to screen">Fit</button>
    <button type="button" id="zoomReset" title="Reset zoom and pan">Reset</button>
    <span class="spacer"></span>
    <a class="btn" id="openUrl" href="#" target="_blank" rel="noopener" hidden>Open URL</a>
    <a class="btn" id="openPlay" href="#" target="_blank" rel="noopener" hidden>Playground</a>
  </div>
  <div id="rerenderRow">
    <label for="themeSelect">Theme</label>
    <select id="themeSelect" title="Diagram theme for re-render">
      <option value="">(default)</option>
      <option value="cerulean">cerulean</option>
      <option value="materia">materia</option>
      <option value="sketchy">sketchy</option>
      <option value="cyborg">cyborg</option>
      <option value="blueprint">blueprint</option>
      <option value="plain">plain</option>
      <option value="forest">forest</option>
      <option value="dark">dark</option>
      <option value="neutral">neutral</option>
      <option value="default">default</option>
    </select>
    <label for="formatSelect">Format</label>
    <select id="formatSelect" title="Output format for re-render">
      <option value="png">png</option>
      <option value="svg">svg</option>
      <option value="jpeg">jpeg</option>
    </select>
    <button type="button" id="rerenderBtn" title="Re-render via app-only tools/call">Re-render</button>
  </div>
  <div id="frame" aria-label="Diagram canvas"></div>
  <div id="meta"></div>
<script>
(function () {
  "use strict";
  var STATUS = document.getElementById("status");
  var FRAME = document.getElementById("frame");
  var META = document.getElementById("meta");
  var TOOLBAR = document.getElementById("toolbar");
  var REROW = document.getElementById("rerenderRow");
  var ZOOM_LABEL = document.getElementById("zoomLabel");
  var OPEN_URL = document.getElementById("openUrl");
  var OPEN_PLAY = document.getElementById("openPlay");
  var THEME_SEL = document.getElementById("themeSelect");
  var FORMAT_SEL = document.getElementById("formatSelect");
  var zoom = 1;
  var panX = 0, panY = 0, panStart = null;
  var nextId = 1;
  var pending = Object.create(null);
  /** @type {{diagram_type?: string, code?: string, theme?: string, output_format?: string}|null} */
  var lastArgs = null;
  var canCallTools = true;
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

  function applyTheme(hostContext) {
    var vars = hostContext && hostContext.styles && hostContext.styles.variables;
    if (!vars) return;
    var root = document.documentElement;
    Object.keys(vars).forEach(function (k) {
      if (vars[k] != null) root.style.setProperty(k, vars[k]);
    });
  }

  function setStatus(text, isErr) {
    STATUS.textContent = text || "";
    STATUS.className = isErr ? "err" : "";
  }

  function applyZoom() {
    var media = FRAME.querySelector("img, svg");
    if (media) media.style.transform = "translate(" + panX + "px," + panY + "px) scale(" + zoom + ")";
    ZOOM_LABEL.textContent = Math.round(zoom * 100) + "%";
    notifySize();
  }

  function fitDiagram() {
    var media = FRAME.querySelector("img, svg");
    if (!media) return;
    var width = media.offsetWidth || media.getBoundingClientRect().width;
    var height = media.offsetHeight || media.getBoundingClientRect().height;
    if (!width || !height) return;
    zoom = Math.max(0.25, Math.min(4, Math.min(
      (FRAME.clientWidth - 24) / width, (FRAME.clientHeight - 24) / height
    )));
    panX = panY = 0;
    applyZoom();
  }

  function safeUrl(value) {
    try {
      var url = new URL(String(value));
      return (url.protocol === "https:" || url.protocol === "http:") ? url.href : "";
    } catch (e) { return ""; }
  }

  function showLinks(data) {
    data = Object.assign({}, data, {
      url: safeUrl(data.url), playground: safeUrl(data.playground)
    });
    var parts = [];
    if (data.url) {
      parts.push('<div><strong>URL</strong>: <a href="' + escapeHtml(data.url) +
        '" target="_blank" rel="noopener">' + escapeHtml(data.url) + "</a></div>");
      OPEN_URL.href = data.url;
      OPEN_URL.hidden = false;
    } else {
      OPEN_URL.hidden = true;
    }
    if (data.playground) {
      parts.push('<div><strong>Playground</strong>: <a href="' +
        escapeHtml(data.playground) + '" target="_blank" rel="noopener">' +
        escapeHtml(data.playground) + "</a></div>");
      OPEN_PLAY.href = data.playground;
      OPEN_PLAY.hidden = false;
    } else {
      OPEN_PLAY.hidden = true;
    }
    if (data.diagram_type) {
      parts.push("<div><strong>Type</strong>: " + escapeHtml(String(data.diagram_type)) + "</div>");
    }
    META.innerHTML = parts.join("");
    TOOLBAR.hidden = false;
    updateRerenderRow();
  }

  function updateRerenderRow() {
    var hasCode = !!(lastArgs && lastArgs.code && lastArgs.diagram_type);
    REROW.className = hasCode && canCallTools ? "visible" : "";
    if (lastArgs) {
      if (lastArgs.theme != null && lastArgs.theme !== "") {
        THEME_SEL.value = String(lastArgs.theme);
      }
      if (lastArgs.output_format) {
        FORMAT_SEL.value = String(lastArgs.output_format).toLowerCase() === "jpg"
          ? "jpeg" : String(lastArgs.output_format).toLowerCase();
      }
    }
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

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderFromStructured(data) {
    FRAME.innerHTML = "";
    META.textContent = "";
    zoom = 1;
    panX = panY = 0;
    rememberArgsFromData(data);
    if (!data || typeof data !== "object") {
      setStatus("No diagram data in tool result.", true);
      TOOLBAR.hidden = true;
      REROW.className = "";
      return;
    }
    if (data.error) {
      setStatus(String(data.error), true);
      showLinks(data);
      return;
    }
    var mime = String(data.mime_type || "").toLowerCase();
    var b64 = data.content_base64;
    if (b64 && (mime === "image/png" || mime === "image/jpeg" || mime.indexOf("jpeg") >= 0)) {
      var img = document.createElement("img");
      img.alt = (data.diagram_type || "diagram") + "";
      img.src = "data:" + (mime || "image/png") + ";base64," + b64;
      FRAME.appendChild(img);
      setStatus("Diagram ready");
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
        setStatus("Diagram ready");
        showLinks(data);
        applyZoom();
        return;
      }
    }
    // URL-only: never fetch Kroki from the iframe; show links.
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
    FRAME.setAttribute("aria-busy", "true");
    setStatus("Re-rendering…");
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
        FRAME.removeAttribute("aria-busy");
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
      setStatus("Tool cancelled" + (msg.params && msg.params.reason ? ": " + msg.params.reason : ""), true);
    } else if (msg.method === "ui/notifications/host-context-changed") {
      applyTheme(msg.params || {});
    } else if (msg.method === "ui/resource-teardown" && msg.id != null) {
      post({ jsonrpc: "2.0", id: msg.id, result: {} });
    }
  });

  document.getElementById("zoomIn").addEventListener("click", function () {
    zoom = Math.min(4, zoom + 0.25);
    applyZoom();
  });
  document.getElementById("zoomOut").addEventListener("click", function () {
    zoom = Math.max(0.25, zoom - 0.25);
    applyZoom();
  });
  document.getElementById("zoomFit").addEventListener("click", fitDiagram);
  document.getElementById("zoomReset").addEventListener("click", function () {
    zoom = 1;
    panX = panY = 0;
    applyZoom();
  });
  FRAME.addEventListener("pointerdown", function (event) {
    if (event.button !== 0 || !FRAME.querySelector("img, svg")) return;
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
  FRAME.addEventListener("wheel", function (event) {
    if (!FRAME.querySelector("img, svg")) return;
    event.preventDefault();
    zoom = Math.max(0.25, Math.min(4, zoom * (event.deltaY < 0 ? 1.1 : 1 / 1.1)));
    applyZoom();
  }, { passive: false });
  document.addEventListener("keydown", function (event) {
    if (event.altKey || event.ctrlKey || event.metaKey || /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) return;
    if (event.key === "+" || event.key === "=") zoom = Math.min(4, zoom + 0.25);
    else if (event.key === "-") zoom = Math.max(0.25, zoom - 0.25);
    else if (event.key === "0") { zoom = 1; panX = panY = 0; }
    else if (event.key.toLowerCase() === "f") { fitDiagram(); return; }
    else return;
    event.preventDefault();
    applyZoom();
  });
  document.getElementById("rerenderBtn").addEventListener("click", rerender);

  request("ui/initialize", {
    appInfo: { name: "uml-mcp-diagram-viewer", version: "1.2.0" },
    appCapabilities: { availableDisplayModes: ["inline"] }
  }).then(function (result) {
    applyTheme(result && result.hostContext);
    notify("ui/notifications/initialized", {});
    if (!FRAME.firstChild) setStatus("Ready — waiting for tool result…");
  }).catch(function () {
    // Standalone open (no host): keep waiting; tests can inject results via postMessage.
    setStatus("Open this view from an MCP Apps host to receive a diagram.");
  });
})();
</script>
</body>
</html>
"""


def diagram_viewer_html() -> str:
    """Return the Apps HTML document (no CDN, inline script only)."""
    return _DIAGRAM_VIEWER_HTML


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
