(() => {
  "use strict";
  const spec = JSON.parse(document.getElementById("spec").textContent);
  const $ = (id) => document.getElementById(id);
  const canvas = $("scene");
  const ctx = canvas.getContext("2d");
  const root = document.documentElement;
  const layers = spec.layers;
  const byId = new Map(layers.map((l) => [l.id, l]));
  const view = { mode: spec.initialMode === "2d" ? "2d" : "3d", yaw: -0.6, pitch: 0.5, zoom: 1, panX: 0, panY: 0 };
  let selected = null;
  let W = 0, H = 0, hits = [];

  // ---- layout -------------------------------------------------------------
  const PER = 6, CW = 300, CH = 108, GX = 344, GY = 128, GLYPH = 52, FLOW_CARD = [236, 108];
  const FLOW = spec.layout === "flow", HORIZ = spec.direction !== "TB";
  // Shape conventions of autoencoder / GAN / VAE diagrams, used by the flow layout.
  const KIND_DIMS = { encoder: [170, 260], decoder: [170, 260], vector: [64, 260], bottleneck: [72, 72], decision: [92, 92], token: [110, 46] };
  // Columns come from the server (longest path from an input), so parallel branches
  // such as a VAE's mean and log-variance heads share one.
  const rankOf = (id) => byId.get(id).rank || 0;
  const span = (e) => Math.abs(rankOf(e.to) - rankOf(e.from));
  const STACK_GAP = 34, LABEL_BELOW = new Set(["vector", "bottleneck", "decision"]);
  const subLen = (l) => l.shape.join(" × ").length + (l.repeat > 1 ? 6 : 0);
  // Small shapes carry their name underneath; their column widens to fit it.
  const labelRoom = (l) => (LABEL_BELOW.has(l.kind) ? Math.max(l.label.length * 8.6, subLen(l) * 6.8) + 16 : 0);
  const flowDims = (l, stacked) => {
    const base = KIND_DIMS[l.kind];
    if (!base) return FLOW_CARD;
    let [along, across] = base;
    if (stacked > 1 && across > 120) across = Math.max(108, (260 - STACK_GAP * (stacked - 1)) / stacked);
    return HORIZ ? [along, across] : [across, along];
  };
  const apex = (n) => 34 + 22 * n;
  const maxSpan = FLOW ? Math.max(0, ...spec.connections.map((e) => (span(e) > 1 ? span(e) : 0))) : 0;
  const FLOW_GAP = 90, PADG = 16, HEADG = spec.groups.length ? 26 : 0;
  // Room after column r for the labels of the edges into the next column.
  const gapAfter = (r) => {
    if (!HORIZ) return FLOW_GAP;
    const widths = spec.connections.filter((c) => c.label && rankOf(c.from) === r && rankOf(c.to) === r + 1).map((c) => c.label.length * 6.6 + 34);
    return Math.max(FLOW_GAP, ...widths);
  };
  const pos2d = new Map(), groupBoxes = [];
  let bounds2d;
  (function layout2d() {
    if (FLOW) {
      const cols = new Map();
      layers.forEach((l, i) => { if (!cols.has(rankOf(l.id))) cols.set(rankOf(l.id), []); cols.get(rankOf(l.id)).push([i, l]); });
      let m = 0;
      [...cols.keys()].sort((a, b) => a - b).forEach((r) => {
        const mem = cols.get(r), dims = mem.map(([, l]) => flowDims(l, mem.length));
        let along = Math.max(...dims.map(([w, h]) => (HORIZ ? w : h)));
        if (HORIZ) along = Math.max(along, ...mem.map(([, l]) => labelRoom(l)));
        const gaps = mem.map(([, l]) => STACK_GAP + (HORIZ && LABEL_BELOW.has(l.kind) ? 40 : 0));
        let c = -(dims.reduce((s, [w, h]) => s + (HORIZ ? h : w), 0) + gaps.slice(0, -1).reduce((s, g) => s + g, 0)) / 2;
        mem.forEach(([i, l], k) => {
          const [w, h] = dims[k];
          if (HORIZ) { pos2d.set(l.id, { x: m + (along - w) / 2, y: c, w, h, i, r }); c += h + gaps[k]; }
          else { pos2d.set(l.id, { x: c, y: m + (along - h) / 2, w, h, i, r }); c += w + gaps[k]; }
        });
        m += along + gapAfter(r);
      });
    } else {
      layers.forEach((l, i) => pos2d.set(l.id, { x: Math.floor(i / PER) * GX, y: (i % PER) * GY, w: CW, h: CH, i, r: i }));
    }
    spec.groups.forEach((g) => {
      const mem = layers.filter((l) => l.group === g.id).map((l) => pos2d.get(l.id));
      if (!mem.length) return;
      const low = FLOW && mem.some((p) => layers[p.i].kind === "vector") ? 44 : 0;
      const x0 = Math.min(...mem.map((p) => p.x)) - PADG, y0 = Math.min(...mem.map((p) => p.y)) - PADG - HEADG;
      groupBoxes.push({ g, x: x0, y: y0, w: Math.max(...mem.map((p) => p.x + p.w)) + PADG - x0, h: Math.max(...mem.map((p) => p.y + p.h)) + PADG + low - y0 });
    });
    const rects = [...pos2d.values(), ...groupBoxes];
    let minX = Math.min(...rects.map((r) => r.x)), minY = Math.min(...rects.map((r) => r.y));
    // grid skip edges loop out to the right of their column, with the label beyond
    const loops = FLOW ? [0] : spec.connections.map((e) => {
      const s = pos2d.get(e.from), t = pos2d.get(e.to), rows = Math.round(Math.abs(t.y - s.y) / GY);
      return Math.abs(t.x - s.x) < 10 && rows > 1 ? 36 + 14 * rows + (e.label || "").length * 6.6 + 16 : 0;
    });
    const maxX = Math.max(...rects.map((r) => r.x + r.w)) + Math.max(0, ...loops), maxY = Math.max(...rects.map((r) => r.y + r.h)) + (FLOW ? 46 : 0);
    if (maxSpan) { if (HORIZ) minY -= apex(maxSpan) + 24; else minX -= apex(maxSpan) + 24; }
    rects.forEach((r) => { r.x -= minX; r.y -= minY; });
    bounds2d = { w: maxX - minX, h: maxY - minY };
  })();

  const box3d = new Map();
  // Glass panels receding in depth, one per layer, like a stack of activation planes.
  const SPACING = 150, STACK = 12, GRID_X = 10, GRID_Y = 6;
  const columns3d = [...new Set(layers.map((l) => rankOf(l.id)))].sort((a, b) => a - b);
  const SIZE3D = (l) => ({ vector: [30, 85], bottleneck: [32, 32], decision: [38, 38], token: [55, 22] }[l.kind] || [135, 85]);
  columns3d.forEach((r, slot) => {
    const mem = layers.filter((l) => rankOf(l.id) === r);
    const pitch = 2 * Math.max(...mem.map((l) => SIZE3D(l)[0])) + 50;
    mem.forEach((l, k) => {
      const [hx, hy] = SIZE3D(l);
      // Encoders narrow and decoders widen along the flow: the autoencoder funnel.
      const taper = l.kind === "encoder" ? "narrow" : l.kind === "decoder" ? "wide" : "";
      const z = (slot - (columns3d.length - 1) / 2) * SPACING;
      box3d.set(l.id, { x: (k - (mem.length - 1) / 2) * pitch, y: hy, z, hx, hy, hz: 2, index: layers.indexOf(l), taper, lane: k });
    });
  });
  const FUNNEL = 0.42, FLEN = SPACING * 0.62;
  // Where a layer's input and output faces sit along the flow.
  const zIn = (b) => (b.taper ? b.z - FLEN / 2 : b.z);
  const zOut = (b, l) => (b.taper ? b.z + FLEN / 2 : b.z + copies(l) * STACK);
  // Half sizes of a frustum's input (end 0) and output (end 1) faces.
  const ends = (b) => (b.taper === "narrow" ? [1, FUNNEL] : [FUNNEL, 1]).map((f) => [b.hx * f, b.hy * f]);
  const copies = (l) => Math.min(l.repeat, 5);
  // Deterministic pseudo activations so a layer always looks the same.
  const activation = (i, cx, cy) => {
    const v = Math.sin(i * 12.9898 + cx * 78.233 + cy * 37.719) * 43758.5453;
    return v - Math.floor(v);
  };

  // ---- helpers ------------------------------------------------------------
  const css = (name) => getComputedStyle(root).getPropertyValue(name).trim();
  const shade = (hex, f) => {
    const n = parseInt(hex.slice(1), 16);
    const c = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => Math.max(0, Math.min(255, Math.round(v * f))));
    return `rgb(${c[0]},${c[1]},${c[2]})`;
  };
  const shapeText = (l) => l.shape.join(" × ");
  const subText = (l) => [shapeText(l), l.repeat > 1 ? `×${l.repeat}` : ""].filter(Boolean).join(" · ");
  const fit = (text, max) => {
    if (ctx.measureText(text).width <= max) return text;
    while (text.length > 1 && ctx.measureText(text + "…").width > max) text = text.slice(0, -1);
    return text + "…";
  };
  const inPoly = (p, poly) => {
    let inside = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      const a = poly[i], b = poly[j];
      if (a[1] > p[1] !== b[1] > p[1] && p[0] < ((b[0] - a[0]) * (p[1] - a[1])) / (b[1] - a[1]) + a[0]) inside = !inside;
    }
    return inside;
  };

  // ---- 3D projection ------------------------------------------------------
  // World: x right, y up, z away. Camera looks along +z from above (pitch).
  const D = 1400;
  const rot = (x, y, z) => {
    const cy = Math.cos(view.yaw), sy = Math.sin(view.yaw), cp = Math.cos(view.pitch), sp = Math.sin(view.pitch);
    const x1 = x * cy + z * sy, z1 = -x * sy + z * cy;
    return [x1, y * cp + z1 * sp, -y * sp + z1 * cp];
  };
  const proj = (x, y, z) => {
    const [rx, ry, rz] = rot(x, y, z);
    const s = D / (D + rz);
    return [W / 2 + view.panX + rx * s * view.zoom, H / 2 + view.panY - ry * s * view.zoom, rz];
  };

  // ---- fit ----------------------------------------------------------------
  function reset() {
    view.panX = view.panY = 0;
    if (view.mode === "2d") {
      view.zoom = Math.max(0.2, Math.min((W - 80) / bounds2d.w, (H - 80) / bounds2d.h, 1.6));
      return;
    }
    view.yaw = 0.95; view.pitch = 0.32; view.zoom = 1;
    const pts = [];
    layers.forEach((l) => {
      const b = box3d.get(l.id);
      for (const sx of [-1, 1]) for (const sy of [0, 2]) for (const sz of [b.z - 60, b.z + copies(l) * STACK + 20]) {
        pts.push(proj(b.x + sx * (b.hx + 20), sy * b.hy + 40, sz));
      }
    });
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    const lo = [Math.min(...xs), Math.min(...ys)], hi = [Math.max(...xs), Math.max(...ys)];
    view.zoom = Math.max(0.2, Math.min((W - 100) / (hi[0] - lo[0]), (H - 120) / (hi[1] - lo[1]), 2));
    // proj() at zoom 1 is centred on the viewport, so the offset scales with the new zoom
    view.panX = -((lo[0] + hi[0]) / 2 - W / 2) * view.zoom;
    view.panY = -((lo[1] + hi[1]) / 2 - H / 2) * view.zoom;
  }

  // ---- drawing ------------------------------------------------------------
  function arrowHead(x, y, angle) {
    ctx.beginPath(); ctx.moveTo(x, y);
    ctx.lineTo(x - 10 * Math.cos(angle - 0.4), y - 10 * Math.sin(angle - 0.4));
    ctx.lineTo(x - 10 * Math.cos(angle + 0.4), y - 10 * Math.sin(angle + 0.4));
    ctx.closePath(); ctx.fill();
  }
  // size: font px; 2D edge labels pass a zoom-scaled size so they shrink with the diagram
  // align "left": x is where the label starts (labels set beside an arrow)
  function tag(text, x, y, color, size = 12, align = "center") {
    ctx.font = `${size}px system-ui,sans-serif`;
    const w = ctx.measureText(text).width + size;
    if (align === "left") x += w / 2;
    ctx.fillStyle = css("--panel"); ctx.globalAlpha = 0.9;
    ctx.fillRect(x - w / 2, y - size * 0.85, w, size * 1.7); ctx.globalAlpha = 1;
    ctx.fillStyle = color; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText(text, x, y);
  }

  // The kind's pictogram (shared with the static SVG): primitives in a unit box.
  function drawGlyph(kind, color, x, y, s) {
    for (const g of spec.glyphs[kind] || spec.glyphs.generic) {
      ctx.beginPath();
      if (g.t === "rect") {
        if (g.r) ctx.roundRect(x + g.x * s, y + g.y * s, g.w * s, g.h * s, g.r * g.w * s);
        else ctx.rect(x + g.x * s, y + g.y * s, g.w * s, g.h * s);
      } else if (g.t === "ellipse") ctx.ellipse(x + g.x * s, y + g.y * s, g.rx * s, g.ry * s, 0, 0, Math.PI * 2);
      else g.p.forEach(([px, py], i) => (i ? ctx.lineTo(x + px * s, y + py * s) : ctx.moveTo(x + px * s, y + py * s)));
      ctx.strokeStyle = color; ctx.lineWidth = Math.max(1, (2 * s) / GLYPH);
      if (g.t === "path") { ctx.lineCap = ctx.lineJoin = "round"; ctx.stroke(); continue; }
      if (g.t === "poly") ctx.closePath();
      ctx.fillStyle = rgba(color, g.o); ctx.fill();
      if (g.t !== "rect") { ctx.lineWidth = 1; ctx.stroke(); }
    }
  }

  function drawShape2d(l, x, y, w, h, z, sel) {
    const stroke = sel ? css("--accent") : l.color;
    ctx.fillStyle = rgba(l.color, 0.32); ctx.strokeStyle = stroke; ctx.lineWidth = sel ? 3 : 2;
    ctx.beginPath();
    // Polygon points are fractions along (flow, cross); they swap axes when the flow runs top down.
    const poly = { encoder: [[0, 0], [1, 0.25], [1, 0.75], [0, 1]], decoder: [[0, 0.25], [1, 0], [1, 1], [0, 0.75]] }[l.kind];
    if (poly) {
      poly.forEach(([a, b], i) => {
        const px = x + (HORIZ ? a : b) * w, py = y + (HORIZ ? b : a) * h;
        if (i) ctx.lineTo(px, py); else ctx.moveTo(px, py);
      });
      ctx.closePath();
    } else if (l.kind === "decision") ctx.arc(x + w / 2, y + h / 2, w / 2, 0, Math.PI * 2);
    else if (l.kind === "token") ctx.roundRect(x, y, w, h, 9 * z);
    else ctx.rect(x, y, w, h);
    ctx.fill(); ctx.stroke();
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    const sub = subText(l);
    ctx.fillStyle = css("--text"); ctx.font = `700 ${(l.kind === "token" ? 14 : 16) * z}px system-ui,sans-serif`;
    if (l.kind === "encoder" || l.kind === "decoder") {
      ctx.fillText(fit(l.label, Math.min(w, h) * 0.8), x + w / 2, y + h / 2 - 8 * z);
      ctx.fillStyle = css("--muted"); ctx.font = `${12 * z}px system-ui,sans-serif`;
      ctx.fillText(fit(sub, Math.min(w, h) * 0.8), x + w / 2, y + h / 2 + 14 * z);
    } else if (!LABEL_BELOW.has(l.kind)) {
      ctx.fillText(fit(l.label, w - 8 * z), x + w / 2, y + h / 2);
    } else {
      const room = Math.max(150, labelRoom(l)) * z;
      ctx.textBaseline = "alphabetic";
      ctx.fillText(fit(l.label, room), x + w / 2, y + h + 20 * z);
      ctx.fillStyle = css("--muted"); ctx.font = `${12 * z}px system-ui,sans-serif`;
      ctx.fillText(fit(sub, room), x + w / 2, y + h + 36 * z);
    }
  }

  function drawGroup2d(b, P, z) {
    const [x, y] = P(b.x, b.y), w = b.w * z, h = b.h * z;
    ctx.beginPath(); ctx.roundRect(x, y, w, h, 16 * z);
    ctx.fillStyle = rgba(b.g.color, 0.07); ctx.fill();
    ctx.strokeStyle = rgba(b.g.color, 0.7); ctx.lineWidth = 1.4; ctx.setLineDash([6, 5]); ctx.stroke(); ctx.setLineDash([]);
    ctx.textAlign = "left"; ctx.textBaseline = "alphabetic";
    ctx.fillStyle = b.g.color; ctx.font = `700 ${13 * z}px system-ui,sans-serif`;
    ctx.fillText(fit(b.g.label, w - 90 * z), x + 14 * z, y + 21 * z);
    if (b.g.repeat > 1) {
      const text = `×${b.g.repeat}`;
      ctx.font = `700 ${14 * z}px system-ui,sans-serif`; ctx.textAlign = "right";
      ctx.fillText(text, x + w - 14 * z, y + h - 12 * z);
    }
  }

  function draw2d() {
    const z = view.zoom, ox = W / 2 + view.panX - (bounds2d.w / 2) * z, oy = H / 2 + view.panY - (bounds2d.h / 2) * z;
    const P = (x, y) => [ox + x * z, oy + y * z];
    const color = css("--line");
    groupBoxes.forEach((b) => drawGroup2d(b, P, z));
    for (const e of spec.connections) {
      const s = pos2d.get(e.from), t = pos2d.get(e.to), n = Math.abs(t.r - s.r);
      const gridVertical = !FLOW && Math.abs(t.x - s.x) < 10, arch = FLOW && n > 1;
      let a, c, mx, my, angle, side = false;
      ctx.strokeStyle = ctx.fillStyle = color; ctx.lineWidth = 2; ctx.setLineDash(e.style === "dashed" ? [7, 6] : []);
      ctx.beginPath();
      if (arch) {
        // arch over every column in between, measured from the highest of them
        const lift = (apex(n) * 4 * z) / 3, lo = Math.min(s.r, t.r), hi = Math.max(s.r, t.r);
        const between = [...pos2d.values()].filter((p) => p.r >= lo && p.r <= hi);
        if (HORIZ) {
          a = P(s.x + s.w / 2, s.y); c = P(t.x + t.w / 2, t.y);
          const top = P(0, Math.min(...between.map((p) => p.y)))[1];
          ctx.moveTo(a[0], a[1]); ctx.bezierCurveTo(a[0], top - lift, c[0], top - lift, c[0], c[1]);
          mx = (a[0] + c[0]) / 2; my = top - apex(n) * z - 12; angle = Math.PI / 2;
        } else {
          a = P(s.x, s.y + s.h / 2); c = P(t.x, t.y + t.h / 2);
          const left = P(Math.min(...between.map((p) => p.x)), 0)[0];
          ctx.moveTo(a[0], a[1]); ctx.bezierCurveTo(left - lift, a[1], left - lift, c[1], c[0], c[1]);
          mx = left - apex(n) * z - 12; my = (a[1] + c[1]) / 2; angle = 0;
        }
      } else if (FLOW) {
        // neighbouring columns: an S-curve, so branches fan out and merge cleanly
        const fwd = t.r >= s.r;
        ctx.moveTo(...(a = HORIZ ? P(s.x + (fwd ? s.w : 0), s.y + s.h / 2) : P(s.x + s.w / 2, s.y + (fwd ? s.h : 0))));
        c = HORIZ ? P(t.x + (fwd ? 0 : t.w), t.y + t.h / 2) : P(t.x + t.w / 2, t.y + (fwd ? 0 : t.h));
        if (HORIZ) { const b = (a[0] + c[0]) / 2; ctx.bezierCurveTo(b, a[1], b, c[1], c[0], c[1]); angle = fwd ? 0 : Math.PI; }
        else { const b = (a[1] + c[1]) / 2; ctx.bezierCurveTo(a[0], b, c[0], b, c[0], c[1]); angle = fwd ? Math.PI / 2 : -Math.PI / 2; }
        mx = (a[0] + c[0]) / 2; my = (a[1] + c[1]) / 2 - 12;
      } else {
        const rows = Math.round(Math.abs(t.y - s.y) / GY);
        if (gridVertical && rows > 1) {
          // a skip connection (a residual path): out of the right side and back in
          const bulge = (36 + 14 * rows) * z;
          a = P(s.x + s.w, s.y + s.h / 2); c = P(t.x + t.w, t.y + t.h / 2);
          ctx.moveTo(a[0], a[1]); ctx.bezierCurveTo(a[0] + bulge, a[1], c[0] + bulge, c[1], c[0], c[1]);
          angle = Math.PI; side = true;
          mx = a[0] + bulge * 0.75 + 8 * z; my = (a[1] + c[1]) / 2;
        } else if (gridVertical) {
          const down = t.y >= s.y;
          a = P(s.x + s.w / 2, s.y + (down ? s.h : 0)); c = P(t.x + t.w / 2, t.y + (down ? 0 : t.h));
          angle = Math.atan2(c[1] - a[1], 0);
          ctx.moveTo(a[0], a[1]); ctx.lineTo(c[0], c[1]);
          mx = a[0] + 10 * z; my = (a[1] + c[1]) / 2; side = true;  // beside the arrow, not on it
        } else {
          const right = t.x > s.x;
          a = P(s.x + (right ? s.w : 0), s.y + s.h / 2); c = P(t.x + (right ? 0 : t.w), t.y + t.h / 2);
          mx = (a[0] + c[0]) / 2; my = (a[1] + c[1]) / 2 - 12;
          ctx.moveTo(a[0], a[1]); ctx.bezierCurveTo(mx, a[1], mx, c[1], c[0], c[1]);
          angle = c[0] >= mx ? 0 : Math.PI;
        }
      }
      ctx.stroke(); ctx.setLineDash([]);
      arrowHead(c[0], c[1], angle);
      if (e.label) tag(e.label, mx, my, css("--muted"), Math.max(6.5, Math.min(12, 11.5 * z)), side ? "left" : "center");
    }
    for (const l of layers) {
      const p = pos2d.get(l.id), [x, y] = P(p.x, p.y), w = p.w * z, h = p.h * z, sel = l.id === selected;
      if (FLOW && KIND_DIMS[l.kind]) {
        drawShape2d(l, x, y, w, h, z, sel);
        hits.push({ id: l.id, poly: [[x, y], [x + w, y], [x + w, y + h], [x, y + h]] });
        continue;
      }
      ctx.fillStyle = css("--panel"); ctx.strokeStyle = sel ? css("--accent") : css("--border");
      ctx.lineWidth = sel ? 3 : 1;
      ctx.beginPath(); ctx.roundRect(x, y, w, h, 14 * z); ctx.fill(); ctx.stroke();
      ctx.fillStyle = l.color; ctx.fillRect(x, y + 6 * z, 7 * z, h - 12 * z);
      const chip = Math.max(86, l.kind.length * 7.4 + 18);  // the kind badge fits its text
      ctx.beginPath(); ctx.roundRect(x + 18 * z, y + 14 * z, chip * z, 19 * z, 9 * z); ctx.fill();
      ctx.fillStyle = "#fff"; ctx.font = `700 ${9 * z}px system-ui,sans-serif`; ctx.textAlign = "center"; ctx.textBaseline = "alphabetic";
      ctx.fillText(l.kind.toUpperCase(), x + (18 + chip / 2) * z, y + 27 * z);
      const room = (p.w - 36 - GLYPH - 12) * z;
      drawGlyph(l.kind, l.color, x + w - (16 + GLYPH) * z, y + (h - GLYPH * z) / 2, GLYPH * z);
      ctx.textAlign = "left"; ctx.fillStyle = css("--text"); ctx.font = `700 ${15 * z}px system-ui,sans-serif`;
      ctx.fillText(fit(l.label, room), x + 18 * z, y + 57 * z);
      ctx.fillStyle = css("--muted"); ctx.font = `${12 * z}px system-ui,sans-serif`;
      ctx.fillText(fit(subText(l), room), x + 18 * z, y + 78 * z);
      if (l.note) ctx.fillText(fit(l.note, room), x + 18 * z, y + 94 * z);
      hits.push({ id: l.id, poly: [[x, y], [x + w, y], [x + w, y + h], [x, y + h]] });
    }
  }

  function rgba(hex, a) {
    const n = parseInt(hex.slice(1), 16);
    return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
  }
  const quad = (b, z, x0, x1, y0, y1) => [proj(b.x + x0, y0, z), proj(b.x + x1, y0, z), proj(b.x + x1, y1, z), proj(b.x + x0, y1, z)];

  // A frustum from the input face to the output face, faces painted back to front.
  function drawFunnel(l, b) {
    const sel = l.id === selected, [[w0, h0], [w1, h1]] = ends(b), z0 = zIn(b), z1 = zOut(b, l);
    const face = (w, h, z) => [[-w, b.hy - h, z], [w, b.hy - h, z], [w, b.hy + h, z], [-w, b.hy + h, z]];
    const A = face(w0, h0, z0), B = face(w1, h1, z1);
    const faces = [A, B, ...[0, 1, 2, 3].map((k) => [A[k], A[(k + 1) % 4], B[(k + 1) % 4], B[k]])];
    const shapes = faces.map((f) => ({ pts: f.map(([x, y, z]) => proj(b.x + x, y, z)), depth: f.reduce((s, [x, y, z]) => s + rot(b.x + x, y, z)[2], 0) / 4 }));
    shapes.sort((p, q) => q.depth - p.depth);
    for (const s of shapes) {
      trace(s.pts);
      ctx.fillStyle = rgba(l.color, sel ? 0.3 : 0.16); ctx.fill();
      ctx.strokeStyle = sel ? css("--accent") : rgba(l.color, 0.9); ctx.lineWidth = sel ? 3 : 1.6; ctx.stroke();
      hits.push({ id: l.id, poly: s.pts.map((p) => [p[0], p[1]]) });
    }
    // activation dots on the larger face
    const [w, h, z] = w0 >= w1 ? [w0, h0, z0] : [w1, h1, z1];
    for (let gy = 0; gy < GRID_Y; gy++) for (let gx = 0; gx < GRID_X; gx++) {
      const v = activation(b.index, gx, gy);
      const px = -w + ((gx + 0.5) * 2 * w) / GRID_X, py = b.hy - h + ((gy + 0.5) * 2 * h) / GRID_Y;
      const p = proj(b.x + px, py, z), r = Math.max(1.2, (1.5 + v * 3.5) * view.zoom * (D / (D + p[2])));
      ctx.fillStyle = rgba(v > 0.93 ? "#facc15" : l.color, 0.3 + v * 0.6);
      ctx.beginPath(); ctx.arc(p[0], p[1], r, 0, Math.PI * 2); ctx.fill();
    }
  }
  const trace = (poly) => { ctx.beginPath(); poly.forEach((p, i) => (i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]))); ctx.closePath(); };

  const size3d = () => Math.max(8.5, Math.min(12, 13 * view.zoom));
  function draw3d() {
    const first = box3d.get(layers[0].id), last = box3d.get(layers[layers.length - 1].id);
    // floor plate under the whole stack
    const floorZ0 = first.z - 90, floorZ1 = last.z + 90;
    const fx = Math.max(...[...box3d.values()].map((b) => Math.abs(b.x) + b.hx)) + 30;
    const floor = [proj(-fx, 0, floorZ0), proj(fx, 0, floorZ0), proj(fx, 0, floorZ1), proj(-fx, 0, floorZ1)];
    trace(floor); ctx.fillStyle = rgba(css("--accent"), 0.06); ctx.fill();
    ctx.strokeStyle = rgba(css("--accent"), 0.35); ctx.lineWidth = 1.5; ctx.stroke();
    ctx.strokeStyle = rgba(css("--accent"), 0.12); ctx.lineWidth = 1;
    for (let i = 1; i < 8; i++) {
      const x = -fx + (2 * fx * i) / 8, a = proj(x, 0, floorZ0), c = proj(x, 0, floorZ1);
      ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(c[0], c[1]); ctx.stroke();
    }

    // group containers as tinted slabs on the floor around their panels
    spec.groups.forEach((g) => {
      const mem = layers.filter((l) => l.group === g.id).map((l) => box3d.get(l.id));
      if (!mem.length) return;
      const z0 = Math.min(...mem.map((b) => b.z)) - 70, z1 = Math.max(...mem.map((b) => b.z)) + 70, hx = 175;
      trace([proj(-hx, 0, z0), proj(hx, 0, z0), proj(hx, 0, z1), proj(-hx, 0, z1)]);
      ctx.fillStyle = rgba(g.color, 0.16); ctx.fill();
      ctx.strokeStyle = rgba(g.color, 0.9); ctx.lineWidth = 1.6; ctx.setLineDash([6, 5]); ctx.stroke(); ctx.setLineDash([]);
      const p = proj(hx - 10, 0, z0);
      tag(g.label + (g.repeat > 1 ? ` ×${g.repeat}` : ""), p[0] - 30, p[1] + 14, g.color, size3d());
    });

    // data flow: connectors between panel centres, behind the glass
    const color = css("--line");
    for (const e of spec.connections) {
      const s = box3d.get(e.from), t = box3d.get(e.to);
      const a = proj(s.x, s.y, zOut(s, byId.get(e.from))), c = proj(t.x, t.y, zIn(t));
      ctx.strokeStyle = ctx.fillStyle = color; ctx.lineWidth = 2; ctx.setLineDash(e.style === "dashed" ? [7, 6] : []);
      ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(c[0], c[1]); ctx.stroke(); ctx.setLineDash([]);
      arrowHead(c[0], c[1], Math.atan2(c[1] - a[1], c[0] - a[0]));
      // edges into or out of parallel branches would share a midpoint: spread their labels
      const lane = (s.lane || 0) + (t.lane || 0);
      // zoomed out (a small chat frame) the 2D view carries the edge labels instead
      if (e.label && view.zoom >= 0.6) tag(e.label, (a[0] + c[0]) / 2, (a[1] + c[1]) / 2 - 12 + lane * 20, css("--muted"), size3d());
    }

    const items = [];
    layers.forEach((l) => {
      const b = box3d.get(l.id);
      if (b.taper) { items.push({ l, b, z: b.z, front: true, funnel: true, depth: rot(b.x, b.y, b.z)[2] }); return; }
      for (let i = copies(l) - 1; i >= 0; i--) items.push({ l, b, z: b.z + i * STACK, front: i === 0, depth: rot(b.x, b.y, b.z + i * STACK)[2] });
    });
    items.sort((p, q) => q.depth - p.depth);
    for (const { l, b, z, front, funnel } of items) {
      if (funnel) { drawFunnel(l, b); continue; }
      const sel = l.id === selected, panel = quad(b, z, -b.hx, b.hx, 0, b.hy * 2);
      trace(panel);
      ctx.fillStyle = rgba(l.color, sel ? 0.28 : front ? 0.14 : 0.07); ctx.fill();
      ctx.strokeStyle = sel ? css("--accent") : rgba(l.color, front ? 0.9 : 0.45);
      ctx.lineWidth = sel ? 3 : front ? 1.8 : 1; ctx.stroke();
      if (front) {
        // activation dots, sized and lit by a stable pseudo activation
        const idx = b.index;
        for (let gy = 0; gy < GRID_Y; gy++) for (let gx = 0; gx < GRID_X; gx++) {
          const v = activation(idx, gx, gy);
          const px = -b.hx + ((gx + 0.5) * 2 * b.hx) / GRID_X, py = ((gy + 0.5) * 2 * b.hy) / GRID_Y;
          const p = proj(b.x + px, py, z), r = Math.max(1.2, (1.5 + v * 3.5) * view.zoom * (D / (D + p[2])));
          ctx.fillStyle = rgba(v > 0.93 ? "#facc15" : l.color, 0.3 + v * 0.6);
          ctx.beginPath(); ctx.arc(p[0], p[1], r, 0, Math.PI * 2); ctx.fill();
        }
        hits.push({ id: l.id, poly: panel.map((p) => [p[0], p[1]]) });
      }
    }

    for (const l of layers) {
      const b = box3d.get(l.id), p = proj(b.x, -18 - 22 * (b.lane || 0), b.z);
      tag(l.label + (l.repeat > 1 ? ` ×${l.repeat}` : ""), p[0], p[1], l.id === selected ? css("--accent") : css("--text"), size3d());
    }
  }

  function render() {
    const dpr = window.devicePixelRatio || 1;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = css("--bg"); ctx.fillRect(0, 0, W, H);
    hits = [];
    if (view.mode === "2d") draw2d(); else draw3d();
  }

  // ---- UI -----------------------------------------------------------------
  const nav = $("layers");
  const buttons = new Map();
  layers.forEach((l) => {
    const b = document.createElement("button");
    b.type = "button";
    const dot = document.createElement("span");
    dot.className = "dot"; dot.style.background = l.color;
    b.append(dot, document.createTextNode(l.label));
    b.addEventListener("click", () => select(l.id));
    nav.append(b); buttons.set(l.id, b);
  });

  function select(id) {
    selected = id;
    const l = id && byId.get(id);
    buttons.forEach((b, key) => b.setAttribute("aria-pressed", String(key === id)));
    $("inspect-title").textContent = l ? l.label : "Select a layer";
    $("inspect-kind").textContent = l ? l.kind : "—";
    $("inspect-shape").textContent = l ? shapeText(l) || "not set" : "—";
    $("inspect-repeat").textContent = l ? `×${l.repeat}` : "—";
    $("inspect-note").textContent = l ? l.note || "No notes for this layer." : "Click a layer in the scene or the list.";
    $("status").textContent = l ? `Selected ${l.label}` : "";
    render();
  }

  function setMode(mode) {
    view.mode = mode;
    $("mode-2d").setAttribute("aria-pressed", String(mode === "2d"));
    $("mode-3d").setAttribute("aria-pressed", String(mode === "3d"));
    $("hint").textContent = mode === "3d" ? "Drag to orbit · Shift+drag to pan · wheel to zoom" : "Drag to pan · wheel to zoom";
    reset(); render();
  }

  function resize() {
    const r = canvas.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
    W = Math.max(1, Math.round(r.width)); H = Math.max(1, Math.round(r.height));
    canvas.width = W * dpr; canvas.height = H * dpr;
    reset(); render();
  }

  let drag = null;
  canvas.addEventListener("pointerdown", (e) => {
    canvas.setPointerCapture(e.pointerId); canvas.classList.add("dragging");
    drag = { x: e.clientX, y: e.clientY, sx: e.clientX, sy: e.clientY, pan: e.shiftKey || view.mode === "2d" };
  });
  canvas.addEventListener("pointermove", (e) => {
    if (!drag) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    drag.x = e.clientX; drag.y = e.clientY;
    if (drag.pan) { view.panX += dx; view.panY += dy; }
    else { view.yaw += dx * 0.01; view.pitch = Math.max(-1.4, Math.min(1.4, view.pitch + dy * 0.01)); }
    render();
  });
  canvas.addEventListener("pointerup", (e) => {
    canvas.classList.remove("dragging");
    if (drag && Math.hypot(e.clientX - drag.sx, e.clientY - drag.sy) < 4) {
      const r = canvas.getBoundingClientRect(), p = [e.clientX - r.left, e.clientY - r.top];
      let hit = null;
      for (let i = hits.length - 1; i >= 0 && !hit; i--) if (inPoly(p, hits[i].poly)) hit = hits[i].id;
      select(hit);
    }
    drag = null;
  });
  canvas.addEventListener("pointercancel", () => { drag = null; canvas.classList.remove("dragging"); });
  canvas.addEventListener("wheel", (e) => {
    e.preventDefault();
    view.zoom = Math.max(0.15, Math.min(6, view.zoom * Math.exp(-e.deltaY * 0.0015)));
    render();
  }, { passive: false });
  canvas.addEventListener("keydown", (e) => {
    const keys = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
    if (keys[e.key]) {
      const [kx, ky] = keys[e.key];
      if (view.mode === "3d" && !e.shiftKey) { view.yaw += kx * 0.08; view.pitch = Math.max(-1.4, Math.min(1.4, view.pitch + ky * 0.08)); }
      else { view.panX -= kx * 24; view.panY -= ky * 24; }
    } else if (e.key === "+" || e.key === "=") view.zoom = Math.min(6, view.zoom * 1.15);
    else if (e.key === "-") view.zoom = Math.max(0.15, view.zoom / 1.15);
    else if (e.key === "0") reset();
    else return;
    e.preventDefault(); render();
  });
  $("mode-2d").addEventListener("click", () => setMode("2d"));
  $("mode-3d").addEventListener("click", () => setMode("3d"));
  $("reset").addEventListener("click", () => { reset(); render(); });
  $("theme").addEventListener("click", () => { root.classList.toggle("light"); root.classList.toggle("dark"); render(); });

  window.addEventListener("resize", resize);
  setMode(view.mode);
  resize();
  window.__llmViewer = { view, select, setMode, layerCount: layers.length };
})();
