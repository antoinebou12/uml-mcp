/* Dependency graph page: tree and force views, collapse, search, kind filters, a detail
 * card with the path from the project, theme, and SVG/PNG/HTML export.
 *
 * Text only ever goes in through textContent. No network: documentation links open via
 * the host (inside the MCP App viewer) or window.open.
 */
(() => {
  "use strict";
  const doc = document.documentElement;
  if (window.self !== window.top) doc.dataset.embedded = "1";
  const data = JSON.parse(document.getElementById("deps-data").textContent);
  const N = data.nodes, E = data.edges, ROOT = 0, NS = "http://www.w3.org/2000/svg";
  const main = document.querySelector("main"), svg = document.getElementById("canvas");
  const vp = document.getElementById("viewport"), card = document.getElementById("card");
  const search = document.getElementById("search"), found = document.getElementById("found");
  const $ = (id) => document.getElementById(id);

  // ---- graph ------------------------------------------------------------------------
  const out = N.map(() => []), inn = N.map(() => []), kids = N.map(() => []);
  E.forEach((e, k) => { out[e.f].push(k); inn[e.t].push(k); });
  N.forEach((n, i) => { if (n.p >= 0) kids[n.p].push(i); });
  const versions = new Map();
  N.forEach((n, i) => { if (i === ROOT) return; const key = n.name.toLowerCase(); if (!versions.has(key)) versions.set(key, []); versions.get(key).push(i); });
  const dup = (i) => i !== ROOT && versions.get(N[i].name.toLowerCase()).length > 1;
  const size = N.map(() => 0);  // tree descendants; parents always come before children
  for (let i = N.length - 1; i > 0; i--) size[N[i].p] += size[i] + 1;
  const ancestors = (i) => { const a = []; for (let c = N[i].p; c >= 0; c = N[c].p) a.push(c); return a; };
  const pathTo = (i) => [i, ...ancestors(i)].reverse();

  const state = { view: "tree", hidden: new Set(), collapsed: new Set(), selected: -1, matches: [] };
  if (N.length > 60) N.forEach((n, i) => { if (n.d >= 2 && kids[i].length) state.collapsed.add(i); });
  const shown = (i) => i === ROOT || !state.hidden.has(N[i].kind);

  // ---- drawing helpers --------------------------------------------------------------
  const ctx = document.createElement("canvas").getContext("2d");
  const FONT = "11.5px system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";
  const LIC_FONT = "9.5px system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";
  const measure = (text, font) => { ctx.font = font; return ctx.measureText(text).width; };
  const label = (i) => { const n = N[i]; return n.version ? `${n.name}@${n.version}` : (n.req ? `${n.name} ${n.req}` : n.name); };
  const short = (text, max) => text.length > max ? text.slice(0, max - 1) + "…" : text;
  const lic = (n) => short(n.license, 12);
  const widths = new Map();
  const pillW = (i) => {
    if (!widths.has(i)) {
      const n = N[i];
      let w = (i === ROOT ? 22 : 30) + measure(short(label(i), 46), FONT);
      if (n.license) w += 16 + measure(lic(n), LIC_FONT);
      widths.set(i, Math.ceil(Math.min(w, 380)));
    }
    return widths.get(i);
  };
  const make = (tag, attrs, parent, text) => {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    if (parent) parent.appendChild(e);
    return e;
  };
  const nodeClass = (i) => ["node", i === ROOT ? "root" : "k-" + N[i].kind, dup(i) ? "dup" : ""].join(" ").trim();
  let nodeEls = new Map(), edgeEls = [], pos = new Map();

  function nodeGroup(parent, i, x, y) {
    const n = N[i];
    const g = make("g", { class: nodeClass(i), transform: `translate(${x},${y})`, "data-i": i, tabindex: 0, role: "button",
      "aria-label": `${label(i)}${i === ROOT ? ", project" : ", " + n.kind}` }, parent);
    nodeEls.set(i, g);
    return g;
  }

  // ---- tree view ----------------------------------------------------------------------
  function layoutTree() {
    const open = new Set();
    state.matches.slice(0, 200).forEach((m) => ancestors(m).forEach((a) => open.add(a)));
    const vk = new Map();
    const visibleKids = (i) => {
      if (!vk.has(i)) vk.set(i, state.collapsed.has(i) && !open.has(i) ? [] : kids[i].filter(shown));
      return vk.get(i);
    };
    const order = [], stack = [ROOT];
    while (stack.length) {
      const i = stack.pop(); order.push(i);
      const k = visibleKids(i);
      for (let j = k.length - 1; j >= 0; j--) stack.push(k[j]);
    }
    const wide = [];
    order.forEach((i) => { wide[N[i].d] = Math.max(wide[N[i].d] || 0, pillW(i)); });
    const cols = []; let x = 0;
    for (let d = 0; d < wide.length; d++) { cols[d] = x; x += (wide[d] || 0) + 70; }
    const y = new Map(); let row = 0;
    order.forEach((i) => { if (!visibleKids(i).length) y.set(i, row++ * 30); });
    for (let k = order.length - 1; k >= 0; k--) {
      const i = order[k], c = visibleKids(i);
      if (c.length) y.set(i, (y.get(c[0]) + y.get(c[c.length - 1])) / 2);
    }
    return { order, x: (i) => cols[N[i].d], y: (i) => y.get(i), visibleKids, open };
  }

  function drawTree() {
    const L = layoutTree();
    const edges = make("g", { class: "edges" }, vp), nodes = make("g", { class: "nodes" }, vp);
    const kindOf = new Map(E.map((e) => [e.f + ">" + e.t, e.k]));
    L.order.forEach((i) => {
      const x = L.x(i), y = L.y(i), w = pillW(i), n = N[i];
      pos.set(i, [x + w / 2, y]);
      if (i !== ROOT) {
        const p = n.p, x1 = L.x(p) + pillW(p) + 11, y1 = L.y(p), mid = (x1 + x) / 2;
        const path = make("path", { class: "edge e-" + (kindOf.get(p + ">" + i) || n.kind), d: `M${x1},${y1} C${mid},${y1} ${mid},${y} ${x},${y}` }, edges);
        edgeEls.push({ el: path, f: p, t: i });
      }
      const g = nodeGroup(nodes, i, x, y - 11);
      make("title", {}, g, `${label(i)}${n.license ? " · " + n.license : ""}`);
      make("rect", { class: "pill", width: w, height: 22, rx: 11 }, g);
      if (i !== ROOT) make("circle", { class: "dot", cx: 11, cy: 11, r: 4 }, g);
      make("text", { class: "name", x: i === ROOT ? 11 : 20, y: 15 }, g, short(label(i), 46));
      if (n.license) {
        const bw = 8 + measure(lic(n), LIC_FONT);
        make("rect", { class: "badge", x: w - bw - 4, y: 4, width: bw, height: 14, rx: 7 }, g);
        make("text", { class: "lic", x: w - bw, y: 14.5 }, g, lic(n));
      }
      const all = kids[i].filter(shown);
      if (all.length) {
        const closed = !L.visibleKids(i).length;
        const t = make("g", { class: "toggle", transform: `translate(${w + 11},11)`, "data-toggle": i }, g);
        make("title", {}, t, closed ? `Expand (${size[i]} packages)` : "Collapse");
        make("circle", { r: 8 }, t);
        make("text", { y: 4 }, t, closed ? "+" : "−");
        if (closed) make("text", { class: "more", x: w + 23, y: 15 }, g, String(size[i]));
      }
      if (dup(i)) make("text", { class: "dupmark", x: w + (all.length ? 22 : 4), y: all.length ? -2 : 15 }, g, "×" + versions.get(n.name.toLowerCase()).length);
    });
  }

  // ---- force view ---------------------------------------------------------------------
  const forceCache = new Map();
  function forceLayout() {
    const key = [...state.hidden].sort().join(",");
    if (forceCache.has(key)) return forceCache.get(key);
    const vis = N.map((_, i) => i).filter(shown), idx = new Map(vis.map((i, k) => [i, k]));
    const links = E.filter((e) => idx.has(e.f) && idx.has(e.t)).map((e) => [idx.get(e.f), idx.get(e.t)]);
    const n = vis.length, x = new Float64Array(n), y = new Float64Array(n);
    const dx = new Float64Array(n), dy = new Float64Array(n), per = {}, seen = {};
    vis.forEach((i) => { per[N[i].d] = (per[N[i].d] || 0) + 1; });
    vis.forEach((i, k) => {
      const d = N[i].d, c = (seen[d] = (seen[d] || 0) + 1), a = (c / per[d]) * Math.PI * 2 + d * 0.7;
      x[k] = Math.cos(a) * d * 110; y[k] = Math.sin(a) * d * 110;
    });
    const iters = Math.max(25, Math.min(300, Math.floor(3e7 / (n * n + 1))));
    for (let it = 0; it < iters; it++) {
      const alpha = 1 - it / iters;
      dx.fill(0); dy.fill(0);
      for (let a = 0; a < n; a++) for (let b = a + 1; b < n; b++) {
        const ex = x[a] - x[b], ey = y[a] - y[b], d2 = ex * ex + ey * ey + 0.01;
        if (d2 > 360000) continue;
        const f = 2400 / d2;
        dx[a] += ex * f; dy[a] += ey * f; dx[b] -= ex * f; dy[b] -= ey * f;
      }
      for (const [a, b] of links) {
        const ex = x[b] - x[a], ey = y[b] - y[a], d = Math.sqrt(ex * ex + ey * ey) || 1, f = (d - 70) / d * 0.25;
        dx[a] += ex * f; dy[a] += ey * f; dx[b] -= ex * f; dy[b] -= ey * f;
      }
      const cap = 4 + 40 * alpha;
      for (let k = 1; k < n; k++) {
        dx[k] -= x[k] * 0.01; dy[k] -= y[k] * 0.01;
        const m = Math.sqrt(dx[k] * dx[k] + dy[k] * dy[k]) || 1, s = Math.min(m, cap) / m;
        x[k] += dx[k] * s; y[k] += dy[k] * s;
      }
    }
    const result = { vis, links, at: new Map(vis.map((i, k) => [i, [x[k], y[k]]])) };
    forceCache.set(key, result);
    return result;
  }

  function drawForce() {
    const F = forceLayout();
    const edges = make("g", { class: "edges" }, vp), nodes = make("g", { class: "nodes" }, vp);
    E.forEach((e) => {
      const a = F.at.get(e.f), b = F.at.get(e.t);
      if (!a || !b) return;
      edgeEls.push({ el: make("path", { class: "edge e-" + e.k, d: `M${a[0]},${a[1]} L${b[0]},${b[1]}` }, edges), f: e.f, t: e.t });
    });
    F.vis.forEach((i) => {
      const [x, y] = F.at.get(i), r = i === ROOT ? 13 : 5 + Math.min(7, Math.sqrt(inn[i].length) * 2);
      pos.set(i, [x, y]);
      const g = nodeGroup(nodes, i, x, y);
      make("title", {}, g, label(i));
      make("circle", { class: "fdot", r }, g);
      make("text", { class: "flabel", x: r + 4, y: 4 }, g, short(N[i].name, 28));
    });
  }

  // ---- render, highlight ------------------------------------------------------------
  function draw() {
    vp.replaceChildren(); nodeEls = new Map(); edgeEls = []; pos = new Map();
    if (state.view === "tree") drawTree(); else drawForce();
    paint();
  }
  function paint() {
    const path = state.selected >= 0 ? new Set(pathTo(state.selected)) : null;
    const hits = new Set(state.matches), focus = !!path || hits.size > 0;
    nodeEls.forEach((g, i) => {
      g.classList.toggle("sel", i === state.selected);
      g.classList.toggle("path", !!path && path.has(i));
      g.classList.toggle("match", hits.has(i));
      g.classList.toggle("dim", focus && !(path && path.has(i)) && !hits.has(i));
    });
    edgeEls.forEach(({ el, f, t }) => {
      const on = !!path && path.has(f) && path.has(t) && N[t].p === f;
      el.classList.toggle("path", on);
      el.classList.toggle("dim", focus && !on);
    });
  }

  // ---- zoom and pan -------------------------------------------------------------------
  let k = 1, tx = 0, ty = 0;
  const zoomval = $("zoomval");
  const apply = () => { vp.setAttribute("transform", `translate(${tx},${ty}) scale(${k})`); zoomval.textContent = Math.round(k * 100) + "%"; };
  const area = () => {
    const r = main.getBoundingClientRect();
    const side = !card.hidden && r.width >= 720 ? card.offsetWidth + 24 : 0;
    const below = !card.hidden && r.width < 720 ? card.offsetHeight + 8 : 0;
    return { w: Math.max(120, r.width - side), h: Math.max(120, r.height - below) };
  };
  function fit(floor) {
    const b = vp.getBBox(), { w, h } = area(), pad = 20;
    k = Math.min((w - pad * 2) / Math.max(b.width, 1), (h - pad * 2) / Math.max(b.height, 1), 1.5);
    if (floor && k < floor) {
      // too big to read when fitted: show it at a readable scale, the project on the left
      k = floor;
      const [rx, ry] = pos.get(ROOT) || [0, 0];
      tx = state.view === "tree" ? pad - b.x * k : w / 2 - rx * k;
      ty = h / 2 - ry * k;
    } else {
      tx = (w - b.width * k) / 2 - b.x * k; ty = (h - b.height * k) / 2 - b.y * k;
    }
    apply();
  }
  function zoom(f, cx, cy) {
    const r = main.getBoundingClientRect();
    cx = cx ?? r.width / 2; cy = cy ?? r.height / 2;
    const nk = Math.max(0.03, Math.min(6, k * f));
    tx = cx - ((cx - tx) / k) * nk; ty = cy - ((cy - ty) / k) * nk; k = nk; apply();
  }
  function reveal(i, closer) {
    const p = pos.get(i); if (!p) return;
    const zoomIn = closer && k < 0.55;
    if (zoomIn) k = 0.85;
    // centre the package when zoomed in for it, or when it is off screen or under the card
    const { w, h } = area(), sx = p[0] * k + tx, sy = p[1] * k + ty;
    if (zoomIn || sx < 20 || sx > w - 20 || sy < 20 || sy > h - 20) { tx = w / 2 - p[0] * k; ty = h / 2 - p[1] * k; }
    apply();
  }

  let drag = null, moved = 0;
  svg.addEventListener("pointerdown", (e) => { if (e.button === 0) { drag = [e.clientX, e.clientY]; moved = 0; } });
  window.addEventListener("pointermove", (e) => {
    if (!drag) return;
    const dx = e.clientX - drag[0], dy = e.clientY - drag[1];
    moved += Math.abs(dx) + Math.abs(dy); drag = [e.clientX, e.clientY];
    if (moved > 4) { main.classList.add("panning"); tx += dx; ty += dy; apply(); }
  });
  window.addEventListener("pointerup", (e) => {
    if (!drag) return;
    const click = moved <= 4; drag = null; main.classList.remove("panning");
    if (!click) return;
    const t = e.target instanceof Element ? e.target : null;
    const toggle = t && t.closest("[data-toggle]"), node = t && t.closest("[data-i]");
    if (toggle) flip(+toggle.getAttribute("data-toggle"));
    else if (node) select(+node.getAttribute("data-i"));
    else clear();
  });
  svg.addEventListener("wheel", (e) => {
    e.preventDefault();
    const r = main.getBoundingClientRect();
    zoom(Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top);
  }, { passive: false });
  svg.addEventListener("keydown", (e) => {
    const node = e.target instanceof Element && e.target.closest("[data-i]");
    if (!node) return;
    const i = +node.getAttribute("data-i");
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(i); }
    else if ((e.key === "ArrowRight" || e.key === "ArrowLeft") && state.view === "tree" && kids[i].length) {
      e.preventDefault();
      if ((e.key === "ArrowRight") === state.collapsed.has(i)) flip(i);
    }
  });

  // ---- actions --------------------------------------------------------------------------
  function flip(i) {
    if (state.collapsed.has(i)) state.collapsed.delete(i); else state.collapsed.add(i);
    draw();
    const g = nodeEls.get(i); if (g) g.focus({ preventScroll: true });
  }
  function select(i, opts) {
    if (i < 0 || i >= N.length) return;
    let redraw = state.view === "tree" && ancestors(i).some((a) => state.collapsed.has(a));
    ancestors(i).forEach((a) => state.collapsed.delete(a));
    [i, ...ancestors(i)].forEach((a) => {
      if (a !== ROOT && state.hidden.has(N[a].kind)) { state.hidden.delete(N[a].kind); syncKinds(); redraw = true; }
    });
    state.selected = i;
    if (redraw) draw(); else paint();
    showCard(i);
    reveal(i, !!(opts && opts.reveal));
  }
  function clear() {
    state.selected = -1; card.hidden = true; paint();
  }

  // ---- detail card ------------------------------------------------------------------
  const div = (cls, text) => { const d = document.createElement("div"); if (cls) d.className = cls; if (text !== undefined) d.textContent = text; return d; };
  function linkList(title, items) {
    const box = document.createDocumentFragment();
    if (!items.length) return box;
    box.append(div("h", `${title} · ${items.length}`));
    const list = div("list");
    items.slice(0, 60).forEach(([j, via]) => {
      const b = document.createElement("button"); b.type = "button"; b.textContent = label(j);
      if (via) { const s = document.createElement("span"); s.className = "via"; s.textContent = via; b.append(s); }
      b.addEventListener("click", () => select(j, { reveal: true }));
      list.append(b);
    });
    if (items.length > 60) list.append(div("more", `and ${items.length - 60} more`));
    box.append(list);
    return box;
  }
  function openLink(url) {
    if (!/^https:\/\/[^\s"'<>]+$/.test(url || "")) return;
    if (window.parent !== window) {
      window.parent.postMessage({ type: "uml-mcp/open-link", url }, "*");
      if (hostBridge) return;
    }
    window.open(url, "_blank", "noopener,noreferrer");
  }
  function showCard(i) {
    const n = N[i], body = $("card-body");
    body.replaceChildren();
    $("card-kind").textContent = i === ROOT ? "Project" : `${n.kind} dependency${n.group ? " · " + n.group : ""}`;
    $("card-dot").className = "dot " + (i === ROOT ? "root" : "k-" + n.kind);
    $("card-title").textContent = n.name;
    const facts = div("facts");
    const fact = (name, value) => { if (!value) return; const r = div("fact"); r.append(div("k", name), div("v", value)); facts.append(r); };
    fact("Version", n.version || "not pinned");
    const asked = inn[i].map((k2) => E[k2].r).filter(Boolean);
    fact("Requested", [...new Set(asked)].join(", "));
    fact("Licence", n.license);
    fact("Registry", n.eco === "pypi" ? "PyPI" : n.eco === "npm" ? "npm" : "");
    fact("Extras", n.extras);
    fact("Marker", n.marker);
    fact("Level", i === ROOT ? "" : n.d === 1 ? "direct" : `transitive (level ${n.d})`);
    body.append(facts);
    if (i !== ROOT) body.append(div("h", "Path from the project"), div("trail", pathTo(i).map((j) => N[j].name).join(" › ")));
    const others = dup(i) ? versions.get(n.name.toLowerCase()).filter((j) => j !== i) : [];
    if (others.length) {
      body.append(div("warn", `${others.length + 1} versions of ${n.name} in the tree`));
      body.append(linkList("Other versions", others.map((j) => [j, ""])));
    }
    body.append(linkList("Required by", inn[i].map((k2) => [E[k2].f, E[k2].r])));
    body.append(linkList("Depends on", out[i].map((k2) => [E[k2].t, E[k2].r])));
    const docs = $("card-docs");
    docs.hidden = !n.docs;
    docs.onclick = () => openLink(n.docs);
    card.hidden = false;
  }
  $("card-close").addEventListener("click", clear);

  // ---- search -----------------------------------------------------------------------
  function runSearch(fromInput) {
    const q = search.value.trim().toLowerCase();
    state.matches = q ? N.map((n, i) => i).filter((i) => i !== ROOT && (N[i].name.toLowerCase().includes(q) || label(i).toLowerCase().includes(q))) : [];
    found.textContent = q ? (state.matches.length ? `${state.matches.length} found` : "none") : "";
    if (fromInput) draw();
  }
  search.addEventListener("input", () => runSearch(true));
  search.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && state.matches.length) { e.preventDefault(); select(state.matches[0], { reveal: true }); }
    if (e.key === "Escape") { search.value = ""; runSearch(true); }
  });

  // ---- toolbar ----------------------------------------------------------------------
  const kindButtons = [...document.querySelectorAll("[data-kind]")];
  function syncKinds() { kindButtons.forEach((b) => b.setAttribute("aria-pressed", String(!state.hidden.has(b.dataset.kind)))); }
  kindButtons.forEach((b) => b.addEventListener("click", () => {
    const kind = b.dataset.kind;
    if (state.hidden.has(kind)) state.hidden.delete(kind); else state.hidden.add(kind);
    if (state.selected >= 0 && !pathTo(state.selected).every(shown)) clear();
    syncKinds(); draw();
  }));
  function setView(view) {
    state.view = view;
    ["tree", "graph"].forEach((v) => $("view-" + v).setAttribute("aria-pressed", String(v === (view === "tree" ? "tree" : "graph"))));
    doc.dataset.view = view;
    draw(); fit(view === "tree" ? 0.75 : 0.35);
  }
  $("view-tree").addEventListener("click", () => setView("tree"));
  $("view-graph").addEventListener("click", () => setView("force"));
  $("expand").addEventListener("click", () => { state.collapsed.clear(); draw(); fit(0.75); });
  $("collapse").addEventListener("click", () => {
    N.forEach((n, i) => { if (n.d >= 1 && kids[i].length) state.collapsed.add(i); });
    draw(); fit(0.75);
  });
  $("fit").addEventListener("click", () => fit(0));
  $("zin").addEventListener("click", () => zoom(1.25));
  $("zout").addEventListener("click", () => zoom(1 / 1.25));
  const themeBtn = $("theme");
  const syncTheme = () => { themeBtn.setAttribute("aria-label", doc.dataset.theme === "dark" ? "Switch to light theme" : "Switch to dark theme"); };
  themeBtn.addEventListener("click", () => { doc.dataset.theme = doc.dataset.theme === "dark" ? "light" : "dark"; syncTheme(); });
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && document.activeElement !== search) clear();
    if (e.key === "/" && document.activeElement !== search) { e.preventDefault(); search.focus(); }
  });

  // ---- export -----------------------------------------------------------------------
  let hostBridge = false;
  const fileName = (ext) => (data.title.replace(/[^A-Za-z0-9_-]+/g, "-").replace(/^-+|-+$/g, "") || "dependencies") + "." + ext;
  function download(content, type, name) {
    const blob = content instanceof Blob ? content : new Blob([content], { type });
    if (hostBridge) {
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
  function svgExport() {
    const b = vp.getBBox(), pad = 24, head = 44;
    const box = [b.x - pad, b.y - pad - head, b.width + pad * 2, b.height + pad * 2 + head].map((v) => Math.round(v));
    const clone = svg.cloneNode(true);
    clone.removeAttribute("id"); clone.setAttribute("xmlns", NS); clone.setAttribute("role", "img");
    clone.setAttribute("viewBox", box.join(" ")); clone.setAttribute("width", box[2]); clone.setAttribute("height", box[3]);
    clone.setAttribute("class", "deps-svg " + doc.dataset.theme);
    const view = clone.querySelector("#viewport"); view.removeAttribute("transform"); view.removeAttribute("id");
    clone.querySelectorAll(".dim,.sel,.path,.match").forEach((e) => e.classList.remove("dim", "sel", "path", "match"));
    clone.querySelectorAll("[tabindex]").forEach((e) => { e.removeAttribute("tabindex"); e.removeAttribute("role"); });
    const style = make("style", {}, null, data.css[doc.dataset.theme]);
    const bg = make("rect", { class: "bg", x: box[0], y: box[1], width: box[2], height: box[3] });
    const title = make("text", { class: "title", x: box[0] + pad, y: box[1] + 32 }, null, data.title);
    clone.prepend(style, bg, title);
    return { text: new XMLSerializer().serializeToString(clone), w: box[2], h: box[3] };
  }
  function pngExport() {
    const s = svgExport(), scale = Math.min(2, 8192 / Math.max(s.w, s.h));
    const img = new Image(), url = URL.createObjectURL(new Blob([s.text], { type: "image/svg+xml" }));
    img.onload = () => {
      const c = document.createElement("canvas");
      c.width = Math.max(1, Math.round(s.w * scale)); c.height = Math.max(1, Math.round(s.h * scale));
      const g = c.getContext("2d"); g.scale(scale, scale); g.drawImage(img, 0, 0, s.w, s.h);
      URL.revokeObjectURL(url);
      c.toBlob((blob) => { if (blob) download(blob, "image/png", fileName("png")); }, "image/png");
    };
    img.src = url;
  }
  function htmlExport() {
    const clone = doc.cloneNode(true);
    clone.removeAttribute("data-embedded");
    clone.querySelector("#viewport").replaceChildren();
    clone.querySelector("#card").hidden = true;
    return "<!doctype html>\n" + clone.outerHTML;
  }
  const menu = $("export-menu"), exportBtn = $("export");
  const closeMenu = () => { menu.hidden = true; exportBtn.setAttribute("aria-expanded", "false"); };
  exportBtn.addEventListener("click", (e) => { e.stopPropagation(); menu.hidden = !menu.hidden; exportBtn.setAttribute("aria-expanded", String(!menu.hidden)); });
  document.addEventListener("click", (e) => { if (!menu.contains(e.target)) closeMenu(); });
  $("save-svg").addEventListener("click", () => { closeMenu(); download(svgExport().text, "image/svg+xml", fileName("svg")); });
  $("save-png").addEventListener("click", () => { closeMenu(); pngExport(); });
  $("save-html").addEventListener("click", () => { closeMenu(); download(htmlExport(), "text/html", fileName("html")); });
  if (window.parent !== window) {
    window.addEventListener("message", (event) => {
      if (event.source !== window.parent || !event.data) return;
      if (event.data.type === "uml-mcp/plugin-bridge-ready") { hostBridge = true; return; }
      if (event.data.type !== "uml-mcp/plugin-export") return;
      const id = { svg: "save-svg", png: "save-png", html: "save-html" }[event.data.format];
      if (id) $(id).click();
    });
    window.parent.postMessage({ type: "uml-mcp/plugin-ready", exports: ["svg", "png", "html"] }, "*");
  }

  // ---- start ------------------------------------------------------------------------
  if (doc.dataset.theme === "auto") doc.dataset.theme = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  syncTheme(); syncKinds();
  doc.dataset.view = "tree";
  draw(); fit(0.75);
  let resizeTimer = 0;
  window.addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => fit(state.view === "tree" ? 0.75 : 0.35), 120); });
  window.__deps = {
    state, select, clear, flip, setView, fit, svgExport, htmlExport,
    get scale() { return k; }, index: (id) => N.findIndex((n) => n.id === id),
    visible: () => [...nodeEls.keys()].map((i) => N[i].id),
  };
})();
