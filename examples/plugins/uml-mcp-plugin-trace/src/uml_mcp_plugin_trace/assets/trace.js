/* The agent-trace page: waterfall and flow views, collapse, detail card, critical path,
 * pan and zoom, themes and exports (SVG, PNG, HTML).
 *
 * Every string from the trace reaches the page as JSON and is shown with textContent,
 * never as markup. Links open only for https URLs, through the host when embedded.
 */
(() => {
  "use strict";
  const root = document.documentElement, main = document.querySelector("main");
  const stage = document.getElementById("stage");
  const data = JSON.parse(document.getElementById("trace").textContent);
  const exportCss = JSON.parse(document.getElementById("export-css").textContent);
  const steps = new Map(data.steps.map((s) => [s.id, s]));
  const views = { waterfall: document.getElementById("waterfall"), flow: document.getElementById("flow") };
  const critical = new Set(data.critical);
  const collapsed = new Set();
  let view = "waterfall", k = 1, x = 0, y = 0, drag = null, moved = 0, fitted = true;
  let selected = null, hostBridge = false;
  if (window.self !== window.top) root.dataset.embedded = "1";

  const $ = (id) => document.getElementById(id);
  const el = (tag, text, cls) => {
    const e = document.createElement(tag);
    if (text !== undefined && text !== null) e.textContent = String(text);
    if (cls) e.className = cls;
    return e;
  };
  const rowsOf = (svg) => [...svg.querySelectorAll("g.row, g.msg")];
  const fmtMs = (ms) => {
    if (ms < 1) return ms ? ms.toFixed(2) + " ms" : "0 ms";
    if (ms < 1000) return Math.round(ms) + " ms";
    if (ms < 60000) return (ms / 1000).toFixed(2) + " s";
    const m = Math.floor(ms / 60000);
    return m + "m " + ((ms - m * 60000) / 1000).toFixed(1).padStart(4, "0") + "s";
  };
  const fmtTok = (n) => n < 1000 ? String(n) : n < 10000 ? (n / 1000).toFixed(1) + "k" : n < 1e6 ? Math.round(n / 1000) + "k" : (n / 1e6).toFixed(1) + "M";
  const fmtCost = (c) => c === null || c === undefined ? "—" : c === 0 ? "$0" : c < 0.01 ? "$" + c.toFixed(4) : "$" + c.toFixed(2);

  // ---- links and downloads ------------------------------------------------------------
  function openLink(url) {
    if (!/^https:\/\/[^\s"'<>]+$/.test(url || "")) return;
    if (window.parent !== window) {
      window.parent.postMessage({ type: "uml-mcp/open-link", url: url }, "*");
      if (hostBridge) return;
    }
    window.open(url, "_blank", "noopener,noreferrer");
  }
  function download(content, type, name) {
    const blob = content instanceof Blob ? content : new Blob([content], { type: type });
    if (hostBridge) {
      const reader = new FileReader();
      reader.onload = () => window.parent.postMessage({ type: "uml-mcp/plugin-download", filename: name,
        mime_type: type, blob: String(reader.result).split(",")[1] }, "*");
      reader.readAsDataURL(blob);
      return;
    }
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }
  const fileName = (ext) => ((data.title || "agent-trace").replace(/[^A-Za-z0-9_-]+/g, "-").replace(/^-+|-+$/g, "") || "agent-trace") + (ext === "html" ? "" : "-" + view) + "." + ext;

  // ---- collapse: hide the rows under folded steps and close the gaps -----------------
  const hidden = (id) => {
    for (let p = steps.get(id).parent; p; p = steps.get(p).parent) if (collapsed.has(p)) return true;
    return false;
  };
  function reflow(svg) {
    const top = +svg.dataset.rowTop, h = +svg.dataset.row, gap = +svg.dataset.legendGap;
    let i = 0;
    rowsOf(svg).forEach((g) => {
      const gone = hidden(g.dataset.id);
      g.classList.toggle("gone", gone);
      g.classList.toggle("folded", collapsed.has(g.dataset.id));
      if (steps.get(g.dataset.id).children.length) g.setAttribute("aria-expanded", String(!collapsed.has(g.dataset.id)));
      if (gone) return;
      g.setAttribute("transform", "translate(0," + (top + i * h) + ")");
      const bg = g.querySelector(".rowbg");
      if (bg) bg.classList.toggle("stripe", i % 2 === 1);
      i += 1;
    });
    const end = top + i * h, H = end + gap + 34, W = svg.viewBox.baseVal.width;
    svg.querySelectorAll(".gridline, .lifeline").forEach((l) => l.setAttribute("y2", String(end)));
    const legend = svg.querySelector(".legend");
    if (legend) legend.setAttribute("transform", "translate(0," + (end + gap) + ")");
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    svg.setAttribute("height", String(H));
    svg.querySelector("rect.bg").setAttribute("height", String(H));
  }
  function setCollapsed(id, fold) {
    const s = steps.get(id);
    if (!s || !s.children.length) return;
    if (fold) collapsed.add(id); else collapsed.delete(id);
    if (fold && selected && hidden(selected)) closeCard();
    Object.values(views).forEach(reflow);
    syncCollapseButton();
  }
  const foldable = data.steps.filter((s) => s.kind === "subagent" && s.children.length && s.parent);
  const foldTargets = foldable.length ? foldable : data.steps.filter((s) => s.kind === "subagent" && s.children.length);
  const collapseBtn = $("collapse");
  function syncCollapseButton() {
    const all = foldTargets.length > 0 && foldTargets.every((s) => collapsed.has(s.id));
    collapseBtn.textContent = all ? "Expand" : "Collapse";
    collapseBtn.setAttribute("aria-pressed", String(all));
  }
  collapseBtn.disabled = !foldTargets.length;
  collapseBtn.addEventListener("click", () => {
    const fold = !foldTargets.every((s) => collapsed.has(s.id));
    foldTargets.forEach((s) => (fold ? collapsed.add(s.id) : collapsed.delete(s.id)));
    if (selected && hidden(selected)) closeCard();
    Object.values(views).forEach(reflow);
    syncCollapseButton();
    if (fitted) fit();
  });

  // ---- pan, zoom, fit ----------------------------------------------------------------
  const zoomval = $("zoomval");
  const apply = () => { stage.style.transform = "translate(" + x + "px," + y + "px) scale(" + k + ")"; zoomval.textContent = Math.round(k * 100) + "%"; };
  function fit() {
    const r = main.getBoundingClientRect(), vb = views[view].viewBox.baseVal;
    const kw = (r.width - 8) / vb.width, kh = (r.height - 8) / vb.height;
    k = Math.min(kw, kh);
    if (k < kw * 0.6) k = kw;  // a long trace fits its width and scrolls (drag) down
    k = Math.max(0.1, Math.min(k, 1.5));
    x = (r.width - vb.width * k) / 2;
    y = vb.height * k <= r.height ? (r.height - vb.height * k) / 2 : 4;
    fitted = true;
    apply();
  }
  function zoom(f, px, py) {
    const r = main.getBoundingClientRect(), cx = px ?? r.width / 2, cy = py ?? r.height / 2;
    const nk = Math.max(0.1, Math.min(6, k * f));
    x = cx - ((cx - x) / k) * nk; y = cy - ((cy - y) / k) * nk; k = nk; fitted = false; apply();
  }

  // ---- detail card -------------------------------------------------------------------
  const card = $("card"), docsBtn = $("c-docs");
  let docsUrl = null;
  docsBtn.addEventListener("click", () => openLink(docsUrl));
  $("c-close").addEventListener("click", () => closeCard());
  function markSelected() {
    Object.values(views).forEach((svg) => rowsOf(svg).forEach((g) => g.classList.toggle("sel", g.dataset.id === selected)));
  }
  function closeCard() { selected = null; card.hidden = true; markSelected(); }
  const PREVIEW = 280;
  function textBlock(label, text) {
    const box = el("section", null, "blk"), pre = el("pre");
    box.append(el("h3", label), pre);
    const long = text.length > PREVIEW;
    const short = text.slice(0, PREVIEW).trimEnd() + "…";
    pre.textContent = long ? short : text;
    if (long) {
      const more = el("button", "Show all (" + text.length + " characters)", "more");
      more.type = "button";
      more.setAttribute("aria-expanded", "false");
      more.addEventListener("click", () => {
        const open = more.getAttribute("aria-expanded") !== "true";
        pre.textContent = open ? text : short;
        more.textContent = open ? "Show less" : "Show all (" + text.length + " characters)";
        more.setAttribute("aria-expanded", String(open));
      });
      box.append(more);
    }
    return box;
  }
  function stat(label, value, cls) { const d = el("div", label, cls); d.append(el("b", value)); return d; }
  function select(id) {
    const s = steps.get(id);
    if (!s) return;
    selected = id;
    markSelected();
    $("c-kind").textContent = s.kindLabel + (critical.has(id) ? " · critical path" : "");
    $("c-title").textContent = s.name;
    const sub = [s.model, s.tool && s.tool !== s.name ? s.tool : "", fmtMs(s.end - s.start)].filter(Boolean);
    $("c-sub").textContent = sub.join(" · ");
    $("c-dot").style.background = s.color;
    docsUrl = s.docs_url;
    docsBtn.hidden = !docsUrl;
    docsBtn.textContent = "Open documentation ↗";
    if (docsUrl) docsBtn.title = docsUrl;
    const body = $("c-body");
    body.replaceChildren();
    const grid = el("div", null, "stats");
    grid.append(stat("Start", fmtMs(s.start - data.start)), stat("Duration", fmtMs(s.end - s.start)),
      stat("Status", s.status, s.status === "error" ? "bad" : s.status === "retry" ? "warn" : ""));
    if (s.tokens) grid.append(stat("Tokens in", fmtTok(s.tokens.in)), stat("Tokens out", fmtTok(s.tokens.out)), stat("Cached", fmtTok(s.tokens.cached)));
    if (s.cost_usd !== null && s.cost_usd !== undefined) grid.append(stat("Cost", fmtCost(s.cost_usd)));
    body.append(grid);
    if (s.note) { const n = el("section", null, "blk"); n.append(el("h3", "Note"), el("p", s.note)); body.append(n); }
    if (s.input) body.append(textBlock("Input", s.input));
    if (s.output) body.append(textBlock("Output", s.output));
    if (s.docs.length) {
      const box = el("section", null, "blk");
      box.append(el("h3", "Retrieved documents · " + s.docs.length));
      s.docs.forEach((d) => {
        const row = el("div", null, "doc");
        row.append(el("span", d.title, "dt"), el("span", d.score === null ? "" : d.score.toFixed(2), "score"));
        if (d.score !== null) {
          const meter = el("div", null, "meter"), bar = el("span");
          bar.style.width = Math.max(0, Math.min(1, d.score)) * 100 + "%";
          meter.append(bar);
          row.append(meter);
        }
        if (d.source) {
          const src = el("div", null, "ds");
          if (/^https:\/\//.test(d.source)) {
            const b = el("button", d.source.replace(/^https:\/\//, "") + " ↗");
            b.type = "button";
            b.addEventListener("click", () => openLink(d.source));
            src.append(b);
          } else src.textContent = d.source;
          row.append(src);
        }
        box.append(row);
      });
      body.append(box);
    }
    const related = [];
    if (s.parent) related.push(["Parent", [s.parent]]);
    if (s.children.length) related.push(["Steps inside · " + s.children.length, s.children]);
    related.forEach(([label, ids]) => {
      const box = el("section", null, "blk"), links = el("div", null, "links");
      box.append(el("h3", label), links);
      ids.forEach((cid) => {
        const b = el("button", steps.get(cid).name);
        b.type = "button";
        b.addEventListener("click", () => { if (hidden(cid)) { for (let p = steps.get(cid).parent; p; p = steps.get(p).parent) collapsed.delete(p); Object.values(views).forEach(reflow); syncCollapseButton(); } select(cid); });
        links.append(b);
      });
      body.append(box);
    });
    card.hidden = false;
    card.scrollTop = 0;
    $("status").textContent = "Selected " + s.kindLabel + ": " + s.name;
  }

  // ---- tooltip -----------------------------------------------------------------------
  const tip = $("tip");
  function showTip(id, cx, cy) {
    const s = steps.get(id), r = main.getBoundingClientRect();
    tip.replaceChildren(el("b", s.name), el("span", fmtMs(s.start - data.start) + " → " + fmtMs(s.end - data.start) + " · " + fmtMs(s.end - s.start)));
    tip.hidden = false;
    const w = tip.offsetWidth, h = tip.offsetHeight;
    tip.style.left = Math.min(cx - r.left + 14, r.width - w - 6) + "px";
    tip.style.top = Math.min(cy - r.top + 14, r.height - h - 6) + "px";
  }

  // ---- pointer -----------------------------------------------------------------------
  const hit = (cx, cy) => document.elementsFromPoint(cx, cy).find((n) => n.closest && n.closest("g.row, g.msg, .caret"));
  main.addEventListener("pointerdown", (e) => {
    if (card.contains(e.target) || e.button !== 0) return;
    main.setPointerCapture(e.pointerId); main.classList.add("drag"); drag = [e.clientX, e.clientY]; moved = 0; tip.hidden = true;
  });
  main.addEventListener("pointermove", (e) => {
    if (drag) {
      const dx = e.clientX - drag[0], dy = e.clientY - drag[1];
      moved += Math.abs(dx) + Math.abs(dy);
      if (moved > 5) fitted = false;
      x += dx; y += dy; drag = [e.clientX, e.clientY]; apply();
      return;
    }
    const row = card.contains(e.target) ? null : e.target.closest && e.target.closest("g.row, g.msg");
    if (row) showTip(row.dataset.id, e.clientX, e.clientY); else tip.hidden = true;
  });
  main.addEventListener("pointerleave", () => { tip.hidden = true; });
  main.addEventListener("pointerup", (e) => {
    const was = drag; drag = null; main.classList.remove("drag");
    if (!was || moved > 5) return;
    const target = hit(e.clientX, e.clientY);
    if (!target) { closeCard(); return; }
    const caret = target.closest(".caret"), row = target.closest("g.row, g.msg");
    if (caret && row) { setCollapsed(row.dataset.id, !collapsed.has(row.dataset.id)); return; }
    if (row) select(row.dataset.id);
  });
  main.addEventListener("pointercancel", () => { drag = null; main.classList.remove("drag"); });
  main.addEventListener("wheel", (e) => {
    if (card.contains(e.target)) return;
    e.preventDefault();
    const r = main.getBoundingClientRect();
    zoom(Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top);
  }, { passive: false });
  document.addEventListener("keydown", (e) => {
    const row = e.target.closest && e.target.closest("g.row, g.msg");
    if (row && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); select(row.dataset.id); return; }
    if (row && (e.key === "ArrowLeft" || e.key === "ArrowRight")) { setCollapsed(row.dataset.id, e.key === "ArrowLeft"); return; }
    if (e.key === "Escape") { closeCard(); $("export").removeAttribute("open"); }
  });

  // ---- toolbar -----------------------------------------------------------------------
  function setView(next) {
    view = next;
    Object.entries(views).forEach(([name, svg]) => svg.toggleAttribute("hidden", name !== next));
    $("v-waterfall").setAttribute("aria-pressed", String(next === "waterfall"));
    $("v-flow").setAttribute("aria-pressed", String(next === "flow"));
    fit();
  }
  $("v-waterfall").addEventListener("click", () => setView("waterfall"));
  $("v-flow").addEventListener("click", () => setView("flow"));
  Object.values(views).forEach((svg) => rowsOf(svg).forEach((g) => g.classList.toggle("crit", critical.has(g.dataset.id))));
  const critBtn = $("crit");
  critBtn.addEventListener("click", () => {
    const on = stage.classList.toggle("crit-on");
    critBtn.setAttribute("aria-pressed", String(on));
    $("status").textContent = on ? "Critical path: " + data.critical.map((id) => steps.get(id).name).join(" → ") : "Critical path hidden";
  });
  $("fit").addEventListener("click", fit);
  $("zin").addEventListener("click", () => zoom(1.25));
  $("zout").addEventListener("click", () => zoom(1 / 1.25));
  const themeBtn = $("theme");
  const labelTheme = () => { themeBtn.textContent = root.dataset.theme === "dark" ? "Light" : "Dark"; };
  themeBtn.addEventListener("click", () => { root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark"; labelTheme(); });

  // ---- exports -----------------------------------------------------------------------
  function svgText() {
    const clone = views[view].cloneNode(true);
    clone.removeAttribute("hidden");
    clone.removeAttribute("id");
    clone.querySelectorAll(".gone").forEach((n) => n.remove());
    clone.querySelectorAll("[style]").forEach((n) => n.removeAttribute("style"));
    clone.querySelectorAll("[tabindex]").forEach((n) => { n.removeAttribute("tabindex"); n.removeAttribute("role"); n.removeAttribute("aria-expanded"); });
    clone.querySelectorAll(".sel").forEach((n) => n.classList.remove("sel"));
    const style = document.createElementNS("http://www.w3.org/2000/svg", "style");
    style.textContent = exportCss[root.dataset.theme === "light" ? "light" : "dark"];
    clone.insertBefore(style, clone.querySelector("rect.bg"));
    return new XMLSerializer().serializeToString(clone);
  }
  function pngBlob(text, width, height, done) {
    const scale = Math.min(2, 8192 / Math.max(width, height)), img = new Image();
    img.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(width * scale));
      canvas.height = Math.max(1, Math.round(height * scale));
      const ctx = canvas.getContext("2d");
      ctx.scale(scale, scale);
      ctx.drawImage(img, 0, 0, width, height);
      canvas.toBlob(done, "image/png");
    };
    img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(text);
  }
  function htmlText() {
    const doc = root.cloneNode(true);
    doc.removeAttribute("data-embedded");
    doc.querySelectorAll("[style]").forEach((n) => n.removeAttribute("style"));
    doc.querySelectorAll(".sel").forEach((n) => n.classList.remove("sel"));
    doc.querySelector("#card").setAttribute("hidden", "");
    doc.querySelector("#tip").setAttribute("hidden", "");
    doc.querySelector("#export").removeAttribute("open");
    doc.querySelector("body").removeAttribute("data-ready");
    return "<!doctype html>\n" + doc.outerHTML;
  }
  const closeMenu = () => $("export").removeAttribute("open");
  $("save").addEventListener("click", () => { closeMenu(); download(svgText(), "image/svg+xml", fileName("svg")); });
  $("png").addEventListener("click", () => {
    closeMenu();
    const vb = views[view].viewBox.baseVal;
    pngBlob(svgText(), vb.width, vb.height, (blob) => { if (blob) download(blob, "image/png", fileName("png")); });
  });
  $("html").addEventListener("click", () => { closeMenu(); download(htmlText(), "text/html", fileName("html")); });
  if (window.parent !== window) {
    window.addEventListener("message", (event) => {
      if (event.source !== window.parent || !event.data) return;
      if (event.data.type === "uml-mcp/plugin-bridge-ready") { hostBridge = true; return; }
      if (event.data.type !== "uml-mcp/plugin-export") return;
      const id = { svg: "save", png: "png", html: "html" }[event.data.format];
      if (id) $(id).click();
    });
    window.parent.postMessage({ type: "uml-mcp/plugin-ready", exports: ["svg", "png", "html"] }, "*");
  }

  window.addEventListener("resize", () => { if (fitted) fit(); });
  if (root.dataset.auto === "1" && window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches) root.dataset.theme = "light";
  labelTheme();
  syncCollapseButton();
  fit();
  document.body.dataset.ready = "1";
  window.__trace = {
    select, setView, fit, close: closeCard,
    collapse: (id) => setCollapsed(id, true), expand: (id) => setCollapsed(id, false),
    get selected() { return selected; }, get view() { return view; }, get zoom() { return k; },
  };
})();
