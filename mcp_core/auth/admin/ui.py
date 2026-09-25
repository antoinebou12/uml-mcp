"""Static admin dashboard shell and script (no data; everything comes from the API)."""

ADMIN_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>UML-MCP admin</title>
<style>
:root{--bg:#fff;--fg:#1f2328;--muted:#59636e;--line:#d0d7de;--card:#f6f8fa;--ok:#1a7f37;--bad:#cf222e;--warn:#9a6700;--acc:#0969da}
@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--fg:#e6edf3;--muted:#9198a1;--line:#30363d;--card:#161b22;--ok:#3fb950;--bad:#f85149;--warn:#d29922;--acc:#4493f8}}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,sans-serif;background:var(--bg);color:var(--fg);line-height:1.5}
header{display:flex;flex-wrap:wrap;gap:.5rem;align-items:center;justify-content:space-between;padding:1rem;border-bottom:1px solid var(--line)}
h1{font-size:1.2rem;margin:0}main{max-width:1200px;margin:0 auto;padding:1rem}
nav{display:flex;flex-wrap:wrap;gap:.25rem;padding:0 1rem;border-bottom:1px solid var(--line)}
nav button{border:0;border-bottom:2px solid transparent;border-radius:0;background:none}
nav button[aria-selected=true]{border-bottom-color:var(--acc);color:var(--acc);font-weight:600}
section{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:1rem;margin:1rem 0;overflow-x:auto}
textarea,input,select{font:inherit;background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:.3rem .5rem}
textarea{width:100%;min-height:5rem;font-family:ui-monospace,monospace}
button{font:inherit;padding:.35rem .9rem;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--fg);cursor:pointer}
pre{white-space:pre-wrap;word-break:break-word;font-size:.85rem}
table{border-collapse:collapse;width:100%;font-size:.85rem}td,th{border-bottom:1px solid var(--line);padding:.3rem .5rem;text-align:left;vertical-align:top;max-width:28rem;overflow-wrap:anywhere}section{overflow-x:auto}
.ok,.success,.allow{color:var(--ok)}.failed,.error,.deny{color:var(--bad)}.warning{color:var(--warn)}.muted{color:var(--muted)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:.75rem}
.card{background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:.75rem}.card b{display:block;font-size:1.4rem}
.filters{display:flex;flex-wrap:wrap;gap:.5rem;margin-bottom:.75rem}[hidden]{display:none!important}
</style></head><body>
<header><h1>UML-MCP admin <span class="muted">(read-only)</span></h1>
<div id="auth"><input id="token" type="password" placeholder="Paste access token (MCP.Admin)" autocomplete="off">
<button id="use">Use token</button> <button id="sso" hidden>Sign in (SSO)</button>
<button id="signout">Sign out</button> <span id="who" class="muted"></span></div></header>
<nav id="tabs" role="tablist"></nav>
<main>
<div data-tab="Overview"><section><div id="overview" class="cards muted">Sign in to load data.</div></section>
<section><h2>Preflight</h2><div id="preflight" class="muted">-</div></section></div>
<div data-tab="Activity"><section><div class="filters">
<select id="f-status"><option value="">any status</option><option>success</option><option>error</option></select>
<select id="f-decision"><option value="">any decision</option><option>allow</option><option>deny</option><option>n/a</option></select>
<input id="f-op" placeholder="operation contains"><input id="f-user" placeholder="user id">
<button id="f-apply">Filter</button><button id="f-more">Older</button><button id="export">Export JSONL</button></div>
<div id="audit" class="muted">-</div></section></div>
<div data-tab="Metrics"><section><div id="metrics" class="muted">-</div></section></div>
<div data-tab="Rate limits"><section><div id="limits" class="muted">-</div></section></div>
<div data-tab="Configuration"><section><p><button id="dlconfig">Download uml-mcp.yaml</button>
<span class="muted">Generated from the effective file config; review and apply through GitOps.</span></p>
<div id="sources"></div><pre id="config">-</pre></section></div>
<div data-tab="Lint"><section><div id="lint" class="muted">-</div></section></div>
<div data-tab="Tools"><section><div id="tools" class="muted">-</div></section></div>
<div data-tab="Clients"><section><div id="clients" class="muted">-</div></section></div>
<div data-tab="Token tester"><section><textarea id="probe" placeholder="token to inspect (never stored)"></textarea>
<p><button id="check">Check token</button></p><pre id="probeout"></pre></section></div>
<div data-tab="Generators"><section><p><select id="kind">
<option>entra-manifest</option><option>az-script</option><option>helm-values</option>
<option>vscode</option><option>visual-studio</option><option>cursor</option><option>claude-code</option>
</select> <button id="gen">Generate</button></p><pre id="genout"></pre></section></div>
</main><script src="/admin/app.js"></script></body></html>
"""

ADMIN_JS = r"""(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var KEY = "uml-mcp-admin-token", auditOffset = 0, local = false;
  function token() { try { return sessionStorage.getItem(KEY) || ""; } catch (e) { return ""; } }
  function setToken(t) { try { t ? sessionStorage.setItem(KEY, t) : sessionStorage.removeItem(KEY); } catch (e) {} }
  function clear(el) { while (el.firstChild) { el.removeChild(el.firstChild); } return el; }
  function text(el, v) { el.textContent = v; }
  function api(path, opts) {
    opts = opts || {};
    var h = Object.assign({}, opts.headers || {});
    if (token()) { h.Authorization = "Bearer " + token(); }
    opts.headers = h;
    return fetch(path, opts).then(function (r) {
      var ct = r.headers.get("content-type") || "";
      var body = ct.indexOf("json") >= 0 ? r.json() : r.text();
      return body.then(function (b) { if (!r.ok) { throw { status: r.status, body: b }; } return b; });
    });
  }
  function fail(el, err) {
    var b = err && err.body;
    text(el, "HTTP " + (err && err.status) + ": " + ((b && (b.error_description || b.detail)) || JSON.stringify(b)));
  }
  function table(rows, cols) {
    var t = document.createElement("table"), h = t.insertRow();
    cols.forEach(function (c) { var th = document.createElement("th"); th.textContent = c; h.appendChild(th); });
    rows.forEach(function (row) {
      var tr = t.insertRow();
      cols.forEach(function (c) {
        var v = row[c], td = tr.insertCell();
        td.textContent = v == null ? "" : (typeof v === "object" ? JSON.stringify(v) : String(v));
        if (c === "status" || c === "operation_status" || c === "policy_decision" || c === "severity") { td.className = String(v); }
      });
    });
    return t;
  }
  function card(label, value) {
    var d = document.createElement("div"), b = document.createElement("b"), s = document.createElement("span");
    d.className = "card"; b.textContent = value; s.textContent = label; s.className = "muted";
    d.appendChild(b); d.appendChild(s); return d;
  }
  var loaders = {
    "Overview": function () {
      api("/admin/api/overview").then(function (d) {
        var el = clear($("overview")); el.classList.remove("muted");
        el.appendChild(card("auth mode", d.mode));
        if (d.version) { el.appendChild(card("version", d.version)); }
        if (d.signing_keys) { el.appendChild(card("signing keys", d.signing_keys.status)); }
        if (d.preflight) {
          el.appendChild(card("preflight", d.preflight.status));
          clear($("preflight")).appendChild(table(d.preflight.checks, ["name", "status", "detail"]));
        } else { text($("preflight"), local ? "Local mode (auth disabled)." : "-"); }
        text($("who"), local ? "local mode (loopback)" : "signed in");
        api("/admin/api/metrics").then(function (m) {
          var total = 0, errors = 0, denied = 0;
          m.operations.forEach(function (o) { total += o.total; errors += o.error; denied += o.denied; });
          el.appendChild(card("calls", total)); el.appendChild(card("errors", errors));
          el.appendChild(card("denied", denied)); el.appendChild(card("uptime (s)", m.uptime_seconds));
        });
        if (d.client_matrix) { clear($("clients")).appendChild(table(d.client_matrix, ["client", "jwt", "entra-proxy"])); }
      }).catch(function (e) { fail($("overview"), e); });
    },
    "Activity": function () {
      var q = new URLSearchParams({ limit: "100", offset: String(auditOffset) });
      [["status", "f-status"], ["decision", "f-decision"], ["operation", "f-op"], ["user", "f-user"]].forEach(function (p) {
        if ($(p[1]).value) { q.set(p[0], $(p[1]).value); }
      });
      api("/admin/api/audit?" + q.toString()).then(function (d) {
        var el = clear($("audit"));
        if (!d.enabled) { el.textContent = d.hint; return; }
        if (!d.records.length) { el.textContent = "No records."; return; }
        el.appendChild(table(d.records, ["timestamp", "caller_type", "operation_type", "operation_name", "operation_status",
          "policy_decision", "policy_reason", "duration_ms", "user_id", "error", "input_data"]));
      }).catch(function (e) { fail($("audit"), e); });
    },
    "Metrics": function () {
      api("/admin/api/metrics").then(function (m) {
        var el = clear($("metrics"));
        el.appendChild(table(m.operations, ["operation_type", "operation_name", "total", "success", "error", "denied", "error_rate", "p50_ms", "p95_ms"]));
        var reasons = Object.keys(m.denial_reasons).map(function (k) { return { reason: k, count: m.denial_reasons[k] }; });
        if (reasons.length) { el.appendChild(table(reasons, ["reason", "count"])); }
      }).catch(function (e) { fail($("metrics"), e); });
    },
    "Rate limits": function () {
      api("/admin/api/rate-limits").then(function (d) {
        var el = clear($("limits")), pre = document.createElement("pre");
        pre.textContent = JSON.stringify(d.policy, null, 2); el.appendChild(pre);
        el.appendChild(table(d.hot_keys, ["scope", "key", "tokens_left"]));
        el.appendChild(table(Object.keys(d.rejected).map(function (k) { return { scope: k, rejected: d.rejected[k] }; }), ["scope", "rejected"]));
      }).catch(function (e) { fail($("limits"), e); });
    },
    "Configuration": function () {
      api("/admin/api/config").then(function (d) {
        text($("config"), JSON.stringify({ config_file: d.config_file, sections: d.sections }, null, 2));
        clear($("sources")).appendChild(table(Object.keys(d.sources).map(function (k) {
          return { key: k, env: d.sources[k].env, source: d.sources[k].source }; }), ["key", "env", "source"]));
      }).catch(function (e) { fail($("config"), e); });
      if (!local) { api("/admin/api/overview").then(function (d) { if (d.settings) {
        text($("config"), $("config").textContent + "\n\n# auth (redacted)\n" + JSON.stringify(d.settings, null, 2)); } }); }
    },
    "Lint": function () {
      api("/admin/api/lint").then(function (issues) {
        var el = clear($("lint"));
        if (!issues.length) { el.textContent = "No lint issues."; return; }
        el.appendChild(table(issues, ["severity", "code", "target", "message", "fix"]));
      }).catch(function (e) { fail($("lint"), e); });
    },
    "Tools": function () {
      api("/admin/api/tools").then(function (t) {
        clear($("tools")).appendChild(table(t, ["name", "enabled", "permission", "rate_limit_per_minute", "annotations", "description"]));
      }).catch(function (e) { fail($("tools"), e); });
    },
    "Clients": function () { loaders.Overview(); },
    "Token tester": function () {},
    "Generators": function () {}
  };
  var names = Object.keys(loaders), nav = $("tabs");
  function show(name) {
    Array.prototype.forEach.call(document.querySelectorAll("[data-tab]"), function (d) { d.hidden = d.getAttribute("data-tab") !== name; });
    Array.prototype.forEach.call(nav.children, function (b) { b.setAttribute("aria-selected", String(b.textContent === name)); });
    loaders[name]();
  }
  names.forEach(function (n) {
    var b = document.createElement("button"); b.textContent = n; b.setAttribute("role", "tab");
    b.addEventListener("click", function () { show(n); }); nav.appendChild(b);
  });
  function b64url(bytes) {
    var s = ""; bytes.forEach(function (b) { s += String.fromCharCode(b); });
    return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }
  function sso() {
    var verifier = b64url(crypto.getRandomValues(new Uint8Array(32))), state = b64url(crypto.getRandomValues(new Uint8Array(16)));
    crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier)).then(function (d) {
      sessionStorage.setItem("uml-mcp-admin-pkce", JSON.stringify({ v: verifier, s: state }));
      var q = new URLSearchParams({ response_type: "code", client_id: "uml-mcp-admin", redirect_uri: location.origin + "/admin/",
        code_challenge: b64url(new Uint8Array(d)), code_challenge_method: "S256", state: state });
      location.assign("/oauth/authorize?" + q.toString());
    });
  }
  function finishSso() {
    var q = new URLSearchParams(location.search), code = q.get("code");
    if (!code) { return Promise.resolve(); }
    var saved = JSON.parse(sessionStorage.getItem("uml-mcp-admin-pkce") || "{}");
    history.replaceState(null, "", "/admin/");
    if (q.get("state") !== saved.s) { return Promise.resolve(); }
    return fetch("/oauth/token", { method: "POST", body: new URLSearchParams({ grant_type: "authorization_code", code: code,
      client_id: "uml-mcp-admin", redirect_uri: location.origin + "/admin/", code_verifier: saved.v }) })
      .then(function (r) { return r.json(); }).then(function (t) { if (t.access_token) { setToken(t.access_token); } });
  }
  $("use").addEventListener("click", function () { setToken($("token").value.trim()); $("token").value = ""; show("Overview"); });
  $("signout").addEventListener("click", function () { setToken(""); location.reload(); });
  $("sso").addEventListener("click", sso);
  $("f-apply").addEventListener("click", function () { auditOffset = 0; loaders.Activity(); });
  $("f-more").addEventListener("click", function () { auditOffset += 100; loaders.Activity(); });
  function download(path, name) {
    api(path).then(function (body) {
      var a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([typeof body === "string" ? body : JSON.stringify(body)]));
      a.download = name; a.click();
    }).catch(function (e) { fail($("audit"), e); });
  }
  $("export").addEventListener("click", function () { download("/admin/api/audit/export", "uml-mcp-audit.jsonl"); });
  $("dlconfig").addEventListener("click", function () { download("/admin/api/config/download", "uml-mcp.yaml"); });
  $("check").addEventListener("click", function () {
    api("/admin/api/token-check", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: $("probe").value.trim() }) })
      .then(function (d) { text($("probeout"), JSON.stringify(d, null, 2)); }).catch(function (e) { fail($("probeout"), e); });
  });
  $("gen").addEventListener("click", function () {
    api("/admin/api/generate/" + encodeURIComponent($("kind").value))
      .then(function (d) { text($("genout"), typeof d === "string" ? d : JSON.stringify(d, null, 2)); })
      .catch(function (e) { fail($("genout"), e); });
  });
  fetch("/.well-known/oauth-authorization-server").then(function (r) { if (r.ok) { $("sso").hidden = false; } });
  fetch("/admin/api/overview").then(function (r) { return r.ok ? r.json() : null; }).then(function (d) {
    if (d && d.local) {
      local = true; $("auth").hidden = true;
      // Clients, token tester and generators need enterprise auth: hide them locally.
      Array.prototype.forEach.call(nav.children, function (b) {
        if (["Clients", "Token tester", "Generators"].indexOf(b.textContent) >= 0) { b.hidden = true; }
      });
    }
  }).catch(function () {}).then(function () { return finishSso(); }).then(function () { show("Overview"); });
})();
"""
