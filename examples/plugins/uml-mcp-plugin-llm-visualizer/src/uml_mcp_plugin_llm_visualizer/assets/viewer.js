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
  const PER = 6, CW = 236, CH = 108, GX = 280, GY = 128;
  const FLOW = spec.layout === "flow", HORIZ = spec.direction !== "TB";
  // Shape conventions of autoencoder / GAN / VAE diagrams, used by the flow layout.
  const KIND_DIMS = { encoder: [170, 260], decoder: [170, 260], vector: [64, 260], bottleneck: [72, 72], decision: [92, 92], token: [110, 46] };
  const layerIndex = new Map(layers.map((l, i) => [l.id, i]));
  const span = (e) => Math.abs(layerIndex.get(e.to) - layerIndex.get(e.from));
  const apex = (n) => 34 + 22 * n;
  const maxSpan = FLOW ? Math.max(0, ...spec.connections.map((e) => (span(e) > 1 ? span(e) : 0))) : 0;
  const FLOW_GAP = 90, PADG = 16, HEADG = spec.groups.length ? 26 : 0;
  const pos2d = new Map(), groupBoxes = [];
  let bounds2d;
  (function layout2d() {
    if (FLOW) {
      let m = 0;
      layers.forEach((l, i) => {
        const base = KIND_DIMS[l.kind];
        const [w, h] = base ? (HORIZ ? base : [base[1], base[0]]) : [190, 108];
        pos2d.set(l.id, { x: HORIZ ? m : -w / 2, y: HORIZ ? -h / 2 : m, w, h, i });
        m += (HORIZ ? w : h) + FLOW_GAP;
      });
    } else {
      layers.forEach((l, i) => pos2d.set(l.id, { x: Math.floor(i / PER) * GX, y: (i % PER) * GY, w: CW, h: CH, i }));
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
    const maxX = Math.max(...rects.map((r) => r.x + r.w)), maxY = Math.max(...rects.map((r) => r.y + r.h)) + (FLOW ? 46 : 0);
    if (maxSpan) { if (HORIZ) minY -= apex(maxSpan) + 24; else minX -= apex(maxSpan) + 24; }
    rects.forEach((r) => { r.x -= minX; r.y -= minY; });
    bounds2d = { w: maxX - minX, h: maxY - minY };
  })();

  const box3d = new Map();
  // Glass panels receding in depth, one per layer, like a stack of activation planes.
  const SPACING = 150, STACK = 12, GRID_X = 10, GRID_Y = 6;
  layers.forEach((l, i) => {
    const [hx, hy] = { vector: [30, 85], bottleneck: [32, 32], decision: [38, 38], token: [55, 22] }[l.kind] || [135, 85];
    const taper = l.kind === "encoder" ? "narrow" : l.kind === "decoder" ? "wide" : "";
    box3d.set(l.id, { x: 0, y: hy, z: (i - (layers.length - 1) / 2) * SPACING, hx, hy, hz: 2, index: i, taper });
  });
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
  const shapeText = (l) => (l.shape.length ? l.shape.join(" × ") : "shape not set");
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
    view.yaw = -0.75; view.pitch = 0.38; view.zoom = 1;
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
  function tag(text, x, y, color) {
    ctx.font = "12px system-ui,sans-serif";
    const w = ctx.measureText(text).width + 12;
    ctx.fillStyle = css("--panel"); ctx.globalAlpha = 0.9;
    ctx.fillRect(x - w / 2, y - 10, w, 20); ctx.globalAlpha = 1;
    ctx.fillStyle = color; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText(text, x, y);
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
    const sub = shapeText(l) + (l.repeat > 1 ? ` · ×${l.repeat}` : "");
    ctx.fillStyle = css("--text"); ctx.font = `700 ${(l.kind === "token" ? 14 : 16) * z}px system-ui,sans-serif`;
    if (l.kind === "encoder" || l.kind === "decoder") {
      ctx.fillText(fit(l.label, Math.min(w, h) * 0.8), x + w / 2, y + h / 2 - 8 * z);
      ctx.fillStyle = css("--muted"); ctx.font = `${12 * z}px system-ui,sans-serif`;
      ctx.fillText(fit(sub, Math.min(w, h) * 0.8), x + w / 2, y + h / 2 + 14 * z);
    } else if (l.kind !== "vector") {
      ctx.fillText(fit(l.label, w - 8 * z), x + w / 2, y + h / 2);
    } else {
      ctx.textBaseline = "alphabetic";
      ctx.fillText(fit(l.label, 150 * z), x + w / 2, y + h + 20 * z);
      ctx.fillStyle = css("--muted"); ctx.font = `${12 * z}px system-ui,sans-serif`;
      ctx.fillText(fit(sub, 150 * z), x + w / 2, y + h + 36 * z);
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
      const s = pos2d.get(e.from), t = pos2d.get(e.to), n = Math.abs(t.i - s.i);
      const gridVertical = !FLOW && Math.abs(t.x - s.x) < 10, arch = FLOW && n > 1;
      let a, c, mx, my, angle;
      ctx.strokeStyle = ctx.fillStyle = color; ctx.lineWidth = 2; ctx.setLineDash(e.style === "dashed" ? [7, 6] : []);
      ctx.beginPath();
      if (arch) {
        const lift = (apex(n) * 4 * z) / 3;
        if (HORIZ) {
          a = P(s.x + s.w / 2, s.y); c = P(t.x + t.w / 2, t.y);
          ctx.moveTo(a[0], a[1]); ctx.bezierCurveTo(a[0], a[1] - lift, c[0], c[1] - lift, c[0], c[1]);
          mx = (a[0] + c[0]) / 2; my = Math.min(a[1], c[1]) - apex(n) * z - 12; angle = Math.PI / 2;
        } else {
          a = P(s.x, s.y + s.h / 2); c = P(t.x, t.y + t.h / 2);
          ctx.moveTo(a[0], a[1]); ctx.bezierCurveTo(a[0] - lift, a[1], c[0] - lift, c[1], c[0], c[1]);
          mx = Math.min(a[0], c[0]) - apex(n) * z - 12; my = (a[1] + c[1]) / 2; angle = 0;
        }
      } else if (FLOW) {
        const fwd = t.i > s.i;
        if (HORIZ) { a = P(s.x + (fwd ? s.w : 0), s.y + s.h / 2); c = P(t.x + (fwd ? 0 : t.w), t.y + t.h / 2); angle = fwd ? 0 : Math.PI; }
        else { a = P(s.x + s.w / 2, s.y + (fwd ? s.h : 0)); c = P(t.x + t.w / 2, t.y + (fwd ? 0 : t.h)); angle = fwd ? Math.PI / 2 : -Math.PI / 2; }
        mx = (a[0] + c[0]) / 2; my = (a[1] + c[1]) / 2 - 12;
        ctx.moveTo(a[0], a[1]); ctx.lineTo(c[0], c[1]);
      } else {
        if (gridVertical) {
          const down = t.y >= s.y;
          a = P(s.x + s.w / 2, s.y + (down ? s.h : 0)); c = P(t.x + t.w / 2, t.y + (down ? 0 : t.h));
          angle = Math.atan2(c[1] - a[1], 0);
        } else {
          const right = t.x > s.x;
          a = P(s.x + (right ? s.w : 0), s.y + s.h / 2); c = P(t.x + (right ? 0 : t.w), t.y + t.h / 2);
        }
        mx = (a[0] + c[0]) / 2; my = (a[1] + c[1]) / 2 - 12;
        ctx.moveTo(a[0], a[1]);
        if (gridVertical) ctx.lineTo(c[0], c[1]); else ctx.bezierCurveTo(mx, a[1], mx, c[1], c[0], c[1]);
        if (!gridVertical) angle = c[0] >= mx ? 0 : Math.PI;
      }
      ctx.stroke(); ctx.setLineDash([]);
      arrowHead(c[0], c[1], angle);
      if (e.label) tag(e.label, mx, my, css("--muted"));
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
      ctx.beginPath(); ctx.roundRect(x + 18 * z, y + 14 * z, 86 * z, 19 * z, 9 * z); ctx.fill();
      ctx.fillStyle = "#fff"; ctx.font = `700 ${9 * z}px system-ui,sans-serif`; ctx.textAlign = "center"; ctx.textBaseline = "alphabetic";
      ctx.fillText(l.kind.toUpperCase(), x + 61 * z, y + 27 * z);
      const room = (p.w - 36) * z;
      ctx.textAlign = "left"; ctx.fillStyle = css("--text"); ctx.font = `700 ${15 * z}px system-ui,sans-serif`;
      ctx.fillText(fit(l.label, room), x + 18 * z, y + 57 * z);
      ctx.fillStyle = css("--muted"); ctx.font = `${12 * z}px system-ui,sans-serif`;
      ctx.fillText(fit(shapeText(l) + (l.repeat > 1 ? ` · ×${l.repeat}` : ""), room), x + 18 * z, y + 78 * z);
      if (l.note) ctx.fillText(fit(l.note, room), x + 18 * z, y + 94 * z);
      hits.push({ id: l.id, poly: [[x, y], [x + w, y], [x + w, y + h], [x, y + h]] });
    }
  }

  function rgba(hex, a) {
    const n = parseInt(hex.slice(1), 16);
    return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
  }
  const inset = (b, side) => ((side === 0 ? b.taper === "wide" : b.taper === "narrow") ? b.hy * 0.5 : 0);
  const quad = (b, z, x0, x1, y0, y1) => {
    const il = inset(b, 0) , ir = inset(b, 1);
    return [proj(b.x + x0, y0 + il, z), proj(b.x + x1, y0 + ir, z), proj(b.x + x1, y1 - ir, z), proj(b.x + x0, y1 - il, z)];
  };
  const trace = (poly) => { ctx.beginPath(); poly.forEach((p, i) => (i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]))); ctx.closePath(); };

  function draw3d() {
    const first = box3d.get(layers[0].id), last = box3d.get(layers[layers.length - 1].id);
    // floor plate under the whole stack
    const floorZ0 = first.z - 90, floorZ1 = last.z + 90, fx = first.hx + 30;
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
      tag(g.label + (g.repeat > 1 ? ` ×${g.repeat}` : ""), p[0] - 30, p[1] + 14, g.color);
    });

    // data flow: connectors between panel centres, behind the glass
    const color = css("--line");
    for (const e of spec.connections) {
      const s = box3d.get(e.from), t = box3d.get(e.to);
      const a = proj(s.x, s.y, s.z + copies(byId.get(e.from)) * STACK), c = proj(t.x, t.y, t.z);
      ctx.strokeStyle = ctx.fillStyle = color; ctx.lineWidth = 2; ctx.setLineDash(e.style === "dashed" ? [7, 6] : []);
      ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(c[0], c[1]); ctx.stroke(); ctx.setLineDash([]);
      arrowHead(c[0], c[1], Math.atan2(c[1] - a[1], c[0] - a[0]));
      if (e.label) tag(e.label, (a[0] + c[0]) / 2, (a[1] + c[1]) / 2 - 12, css("--muted"));
    }

    const items = [];
    layers.forEach((l) => {
      const b = box3d.get(l.id);
      for (let i = copies(l) - 1; i >= 0; i--) items.push({ l, b, z: b.z + i * STACK, front: i === 0, depth: rot(b.x, b.y, b.z + i * STACK)[2] });
    });
    items.sort((p, q) => q.depth - p.depth);
    for (const { l, b, z, front } of items) {
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
          const f = (px + b.hx) / (2 * b.hx), cut = b.taper === "narrow" ? f : b.taper === "wide" ? 1 - f : 0;
          if (Math.abs(py - b.hy) > b.hy * (1 - 0.5 * cut)) continue;
          const p = proj(b.x + px, py, z), r = Math.max(1.2, (1.5 + v * 3.5) * view.zoom * (D / (D + p[2])));
          ctx.fillStyle = rgba(v > 0.93 ? "#facc15" : l.color, 0.3 + v * 0.6);
          ctx.beginPath(); ctx.arc(p[0], p[1], r, 0, Math.PI * 2); ctx.fill();
        }
        hits.push({ id: l.id, poly: panel.map((p) => [p[0], p[1]]) });
      }
    }

    for (const l of layers) {
      const b = box3d.get(l.id), p = proj(b.x, -18, b.z);
      tag(l.label + (l.repeat > 1 ? ` ×${l.repeat}` : ""), p[0], p[1], l.id === selected ? css("--accent") : css("--text"));
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
    $("inspect-shape").textContent = l ? shapeText(l) : "—";
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
