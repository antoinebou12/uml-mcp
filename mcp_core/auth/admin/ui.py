"""Static admin console shell and script (no data; everything comes from the API)."""

ADMIN_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>UML-MCP admin</title>
<style>
:root{--bg:#fff;--fg:#1f2328;--muted:#59636e;--line:#d0d7de;--card:#f6f8fa;--ok:#1a7f37;--bad:#cf222e;--warn:#9a6700}
@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--fg:#e6edf3;--muted:#9198a1;--line:#30363d;--card:#161b22;--ok:#3fb950;--bad:#f85149;--warn:#d29922}}
body{margin:0;font-family:system-ui,sans-serif;background:var(--bg);color:var(--fg);line-height:1.5}
main{max-width:1100px;margin:0 auto;padding:1.5rem 1rem}
h1{font-size:1.4rem}h2{font-size:1.1rem;margin-top:1.5rem}
section{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:1rem;margin:1rem 0;overflow-x:auto}
textarea{width:100%;min-height:5rem;font-family:ui-monospace,monospace;background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:8px}
button,select{font:inherit;padding:.35rem .9rem;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--fg);cursor:pointer}
pre{white-space:pre-wrap;word-break:break-word;font-size:.85rem}
table{border-collapse:collapse;width:100%;font-size:.9rem}td,th{border-bottom:1px solid var(--line);padding:.3rem .5rem;text-align:left;vertical-align:top}
.ok{color:var(--ok)}.failed{color:var(--bad)}.warning{color:var(--warn)}.muted{color:var(--muted)}
</style></head><body><main>
<h1>UML-MCP enterprise auth &mdash; admin console <span class="muted">(read-only)</span></h1>
<section id="signin"><h2>Sign in</h2>
<p class="muted">Requires the <code>MCP.Admin</code> app role. Paste an access token for this API
(for example <code>az account get-access-token --scope api://&lt;client-id&gt;/mcp.read</code>)
or use single sign-on when the server runs in entra-proxy mode.</p>
<textarea id="token" placeholder="eyJ..." autocomplete="off" spellcheck="false"></textarea>
<p><button id="use">Use token</button> <button id="sso" hidden>Sign in (SSO)</button>
<button id="signout">Sign out</button> <span id="who" class="muted"></span></p></section>
<section><h2>Status</h2><div id="status" class="muted">Not signed in.</div></section>
<section><h2>Recent 401/403 decisions (this replica)</h2><div id="events" class="muted">-</div></section>
<section><h2>Token tester</h2><textarea id="probe" placeholder="token to inspect (never stored)"></textarea>
<p><button id="check">Check token</button></p><pre id="probeout"></pre></section>
<section><h2>Generators</h2><p><select id="kind">
<option>entra-manifest</option><option>az-script</option><option>helm-values</option>
<option>vscode</option><option>visual-studio</option><option>cursor</option><option>claude-code</option>
</select> <button id="gen">Generate</button></p><pre id="genout"></pre></section>
<section><h2>Effective configuration (secrets redacted)</h2><pre id="config">-</pre></section>
</main><script src="/admin/app.js"></script></body></html>
"""

ADMIN_JS = r"""(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var KEY = "uml-mcp-admin-token";
  function token() { try { return sessionStorage.getItem(KEY) || ""; } catch (e) { return ""; } }
  function setToken(t) { try { t ? sessionStorage.setItem(KEY, t) : sessionStorage.removeItem(KEY); } catch (e) {} }
  function text(el, value) { el.textContent = value; }
  function api(path, opts) {
    opts = opts || {};
    opts.headers = Object.assign({}, opts.headers || {}, { Authorization: "Bearer " + token() });
    return fetch(path, opts).then(function (r) {
      var ct = r.headers.get("content-type") || "";
      var body = ct.indexOf("json") >= 0 ? r.json() : r.text();
      return body.then(function (b) { if (!r.ok) { throw { status: r.status, body: b }; } return b; });
    });
  }
  function fail(el, err) {
    var b = err && err.body;
    text(el, "HTTP " + (err && err.status) + ": " + (b && (b.error_description || b.detail) || JSON.stringify(b)));
  }
  function table(rows, cols) {
    var t = document.createElement("table"), h = t.insertRow();
    cols.forEach(function (c) { var th = document.createElement("th"); th.textContent = c; h.appendChild(th); });
    rows.forEach(function (row) {
      var tr = t.insertRow();
      cols.forEach(function (c) { var td = tr.insertCell(); td.textContent = row[c] == null ? "" : String(row[c]); if (c === "status") td.className = String(row[c]); });
    });
    return t;
  }
  function load() {
    if (!token()) { return; }
    api("/admin/api/overview").then(function (d) {
      var s = $("status"); s.textContent = "";
      var p = document.createElement("p");
      p.textContent = "Mode: " + d.mode + " · preflight: " + d.preflight.status + " · signing keys: " + d.signing_keys.status;
      s.appendChild(p);
      s.appendChild(table(d.preflight.checks, ["name", "status", "detail"]));
      s.appendChild(table(d.client_matrix, ["client", "jwt", "entra-proxy"]));
      text($("config"), JSON.stringify(d.settings, null, 2));
      text($("who"), "signed in");
    }).catch(function (e) { fail($("status"), e); });
    api("/admin/api/events").then(function (d) {
      var el = $("events"); el.textContent = "";
      if (!d.events.length) { el.textContent = "No denials recorded."; return; }
      el.appendChild(table(d.events.map(function (e) { e.time = new Date(e.ts * 1000).toISOString(); return e; }),
        ["time", "status", "reason", "method", "path", "tool", "client_id", "tenant_id"]));
    }).catch(function (e) { fail($("events"), e); });
  }
  function b64url(bytes) {
    var s = ""; bytes.forEach(function (b) { s += String.fromCharCode(b); });
    return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }
  function sso() {
    var v = new Uint8Array(32); crypto.getRandomValues(v);
    var verifier = b64url(v), state = b64url(crypto.getRandomValues(new Uint8Array(16)));
    crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier)).then(function (d) {
      sessionStorage.setItem("uml-mcp-admin-pkce", JSON.stringify({ v: verifier, s: state }));
      var q = new URLSearchParams({ response_type: "code", client_id: "uml-mcp-admin",
        redirect_uri: location.origin + "/admin/", code_challenge: b64url(new Uint8Array(d)),
        code_challenge_method: "S256", state: state });
      location.assign("/oauth/authorize?" + q.toString());
    });
  }
  function finishSso() {
    var q = new URLSearchParams(location.search), code = q.get("code");
    if (!code) { return Promise.resolve(); }
    var saved = JSON.parse(sessionStorage.getItem("uml-mcp-admin-pkce") || "{}");
    history.replaceState(null, "", "/admin/");
    if (q.get("state") !== saved.s) { return Promise.resolve(); }
    var body = new URLSearchParams({ grant_type: "authorization_code", code: code,
      client_id: "uml-mcp-admin", redirect_uri: location.origin + "/admin/", code_verifier: saved.v });
    return fetch("/oauth/token", { method: "POST", body: body }).then(function (r) { return r.json(); })
      .then(function (t) { if (t.access_token) { setToken(t.access_token); } });
  }
  $("use").addEventListener("click", function () { setToken($("token").value.trim()); $("token").value = ""; load(); });
  $("signout").addEventListener("click", function () { setToken(""); location.reload(); });
  $("sso").addEventListener("click", sso);
  $("check").addEventListener("click", function () {
    api("/admin/api/token-check", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: $("probe").value.trim() }) })
      .then(function (d) { text($("probeout"), JSON.stringify(d, null, 2)); })
      .catch(function (e) { fail($("probeout"), e); });
  });
  $("gen").addEventListener("click", function () {
    api("/admin/api/generate/" + encodeURIComponent($("kind").value))
      .then(function (d) { text($("genout"), typeof d === "string" ? d : JSON.stringify(d, null, 2)); })
      .catch(function (e) { fail($("genout"), e); });
  });
  fetch("/.well-known/oauth-authorization-server").then(function (r) { if (r.ok) { $("sso").hidden = false; } });
  finishSso().then(load);
})();
"""
