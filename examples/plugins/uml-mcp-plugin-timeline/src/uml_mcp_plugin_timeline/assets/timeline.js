/* Interactive timeline: zoom (quarters, months, weeks, days), pan, filters, detail card,
 * dependency chains, a "now" button, light and dark, and SVG/PNG/HTML export.
 *
 * The SVG is redrawn from the data on every change with the same layout rules as the
 * static renderer (svg.py). Text is only ever set with textContent, never as markup.
 */
(function () {
  'use strict';

  var NS = 'http://www.w3.org/2000/svg';
  var DATA = JSON.parse(document.getElementById('spec').textContent);
  var TL = DATA.timeline, PALETTES = DATA.palettes, LEVELS = DATA.levels, LABELS = DATA.statusLabels;
  var ROW = 30, BAR = 18, AXIS = 44, HEADER = 62, LEGEND = 46, CHAR = 6.6, MIN_PPD = 0.25, MAX_PPD = 60;
  var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  var FULL = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
    'October', 'November', 'December'];
  var MAJOR = { day: 'month', week: 'month', month: 'year', quarter: 'year' };
  var FONT = "system-ui, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif";

  var root = document.documentElement;
  var view = document.getElementById('view');
  var stage = document.getElementById('stage');
  var card = document.getElementById('card');
  var hostBridge = false;
  if (window.self !== window.top) root.setAttribute('data-embedded', '1');
  if (root.getAttribute('data-auto') === '1' && window.matchMedia &&
      window.matchMedia('(prefers-color-scheme: light)').matches) root.setAttribute('data-theme', 'light');

  // ---- dates (epoch days, UTC) -------------------------------------------------------------
  function dateOf(day) { return new Date(day * 86400000); }
  function dayOf(y, m, d) { return Math.round(Date.UTC(y, m, d) / 86400000); }
  function todayDay() {
    if (TL.today !== null && TL.today !== undefined) return TL.today;
    var now = new Date();
    return dayOf(now.getFullYear(), now.getMonth(), now.getDate());
  }
  function tickUnit(ppd) {
    if (ppd >= 22) return 'day';
    if (ppd >= 6.5) return 'week';
    if (ppd >= 1.15) return 'month';
    if (ppd >= 0.33) return 'quarter';
    return 'year';
  }
  function floorUnit(day, unit) {
    var d = dateOf(day), y = d.getUTCFullYear(), m = d.getUTCMonth();
    if (unit === 'day') return day;
    if (unit === 'week') return day - ((d.getUTCDay() + 6) % 7);
    if (unit === 'month') return dayOf(y, m, 1);
    if (unit === 'quarter') return dayOf(y, m - (m % 3), 1);
    return dayOf(y, 0, 1);
  }
  function nextUnit(day, unit) {
    if (unit === 'day') return day + 1;
    if (unit === 'week') return day + 7;
    var d = dateOf(day), add = unit === 'month' ? 1 : unit === 'quarter' ? 3 : 12;
    return dayOf(d.getUTCFullYear(), d.getUTCMonth() + add, 1);
  }
  function tickLabel(day, unit) {
    var d = dateOf(day);
    if (unit === 'day') return String(d.getUTCDate());
    if (unit === 'week') return MONTHS[d.getUTCMonth()] + ' ' + d.getUTCDate();
    if (unit === 'month') return MONTHS[d.getUTCMonth()];
    if (unit === 'quarter') return 'Q' + (Math.floor(d.getUTCMonth() / 3) + 1);
    return String(d.getUTCFullYear());
  }
  function majorLabel(day, unit) {
    var d = dateOf(day);
    return unit === 'month' ? FULL[d.getUTCMonth()] + ' ' + d.getUTCFullYear() : String(d.getUTCFullYear());
  }
  function fmt(day) { var d = dateOf(day); return MONTHS[d.getUTCMonth()] + ' ' + d.getUTCDate() + ', ' + d.getUTCFullYear(); }
  function textWidth(text, size) { return text.length * CHAR * (size || 12) / 12; }

  // ---- data -----------------------------------------------------------------------------------
  var items = TL.items, byId = {}, lanesById = {}, dependents = {};
  items.forEach(function (i) { byId[i.id] = i; dependents[i.id] = []; });
  TL.lanes.forEach(function (l) { lanesById[l.id] = l; });
  items.forEach(function (i) { i.depends_on.forEach(function (d) { dependents[d].push(i.id); }); });
  var FIRST = Math.min.apply(null, items.map(function (i) { return i.start; }));
  var LAST = Math.max.apply(null, items.map(function (i) { return i.end; })) + 1;
  function closure(id, next) {
    var seen = {}, todo = [id];
    while (todo.length) next(todo.pop()).forEach(function (n) { if (!seen[n]) { seen[n] = true; todo.push(n); } });
    return seen;
  }

  // ---- state --------------------------------------------------------------------------------
  var S = { ppd: 3, t0: FIRST, sy: 0, selected: null, lane: '', owner: '', status: '' };
  function theme() { return root.getAttribute('data-theme') === 'light' ? 'light' : 'dark'; }
  function gutter() { return view.clientWidth < 640 ? 108 : 168; }
  function visible(i) {
    if (S.lane && i.lane !== S.lane) return false;
    if (S.status && i.status !== S.status) return false;
    if (S.owner && i.kind !== 'phase' && i.owner !== S.owner) return false;
    return true;
  }
  function visibleLanes() { return TL.lanes.filter(function (l) { return !S.lane || l.id === S.lane; }); }

  // ---- layout (mirrors svg.layout) -------------------------------------------------------------
  function layout(list, X, laneIds, top) {
    var boxes = [], placed = {}, phases = [], y = top, maxRight = 0;
    laneIds.forEach(function (laneId) {
      var own = list.filter(function (i) { return i.lane === laneId; });
      var lanePhases = own.filter(function (i) { return i.kind === 'phase'; });
      var rest = own.filter(function (i) { return i.kind !== 'phase'; }).sort(function (a, b) {
        return a.start - b.start || b.end - a.end;
      });
      var pad = lanePhases.length ? 20 : 8, rows = [], slots = [];
      rest.forEach(function (item) {
        var w = textWidth(item.name), x0, x1, inside, extent;
        if (item.point) {
          var cx = X(item.start + 0.5);
          x0 = cx - 8; x1 = cx + 8; inside = false; extent = cx + 12 + w;
        } else {
          x0 = X(item.start); x1 = X(item.end + 1);
          inside = w + 16 <= x1 - x0;
          extent = inside ? x1 : x1 + 6 + w;
        }
        var row = rows.length;
        for (var r = 0; r < rows.length; r++) if (rows[r] <= x0 - 4) { row = r; break; }
        if (row === rows.length) rows.push(0);
        rows[row] = extent + 10;
        maxRight = Math.max(maxRight, item.point ? extent + 2 : extent);
        slots.push([item, x0, x1, inside, row]);
      });
      var box = { id: laneId, y: y, height: pad + Math.max(1, rows.length) * ROW + 8 };
      boxes.push(box);
      slots.forEach(function (s) {
        placed[s[0].id] = { item: s[0], x0: s[1], x1: s[2], y: y + pad + s[4] * ROW + ROW / 2, inside: s[3] };
      });
      lanePhases.forEach(function (p) { phases.push([p, box]); });
      y += box.height;
    });
    return { boxes: boxes, placed: placed, phases: phases, right: maxRight };
  }
  function depPath(a, b) {
    var ax = a.x1 - (a.item.point ? 1 : 0), bx = b.x0, ay = a.y, by = b.y;
    if (bx - ax >= 14) {
      var mx = Math.max(ax + 6, bx - 10);
      return 'M' + ax.toFixed(1) + ' ' + ay.toFixed(1) + 'H' + mx.toFixed(1) + 'V' + by.toFixed(1) + 'H' + (bx - 1).toFixed(1);
    }
    var mid = ay + (by >= ay ? ROW / 2 : -ROW / 2);
    return 'M' + ax.toFixed(1) + ' ' + ay.toFixed(1) + 'H' + (ax + 8).toFixed(1) + 'V' + mid.toFixed(1) +
      'H' + (bx - 10).toFixed(1) + 'V' + by.toFixed(1) + 'H' + (bx - 1).toFixed(1);
  }

  // ---- drawing ------------------------------------------------------------------------------------
  function el(tag, attrs, parent, text) {
    var n = document.createElementNS(NS, tag);
    for (var k in attrs) if (attrs[k] !== undefined && attrs[k] !== null) n.setAttribute(k, attrs[k]);
    if (text !== undefined) n.textContent = text;
    if (parent) parent.appendChild(n);
    return n;
  }
  function chain() {
    if (!S.selected) return null;
    var up = closure(S.selected, function (id) { return byId[id].depends_on; });
    var down = closure(S.selected, function (id) { return dependents[id]; });
    return { up: up, down: down };
  }
  function inChain(c, id) { return !c || id === S.selected || c.up[id] || c.down[id]; }
  function edgeOn(c, from, to) {
    if (!c) return false;
    var upEdge = c.up[from] && (to === S.selected || c.up[to]);
    var downEdge = (from === S.selected || c.down[from]) && c.down[to];
    return !!(upEdge || downEdge);
  }

  /* o.full: the whole timeline for export (title, axis, every lane, legend) instead of the view. */
  function draw(o) {
    o = o || {};
    var pal = PALETTES[theme()], full = !!o.full;
    var list = items.filter(visible), lanes = visibleLanes();
    var G = full ? 168 : gutter(), ppd = S.ppd;
    var unit = tickUnit(ppd);
    var left = full ? floorUnit(FIRST, unit) : S.t0;
    var lastFloor = floorUnit(LAST, unit);
    var right = full ? (lastFloor === LAST ? LAST : nextUnit(lastFloor, unit)) : null;
    var W = full ? Math.max(780, G + (right - left) * ppd + 24) : view.clientWidth;
    var H = view.clientHeight;
    if (!full) right = left + (W - G) / ppd;
    var head = full ? HEADER : 0, top = head + AXIS;
    function X(d) { return G + (d - left) * ppd; }
    var L = layout(list, X, lanes.map(function (l) { return l.id; }), top);
    if (full) W = Math.max(W, L.right + 16);
    var bottom = L.boxes.length ? L.boxes[L.boxes.length - 1].y + L.boxes[L.boxes.length - 1].height : top;
    if (!full) S.sy = Math.max(0, Math.min(S.sy, bottom - H + 8));
    var shift = full ? 0 : -S.sy;
    var height = full ? bottom + LEGEND : H;
    var c = full ? null : chain();

    var svg = el('svg', { xmlns: NS, viewBox: '0 0 ' + Math.round(W) + ' ' + Math.round(height),
      width: Math.round(W), height: Math.round(height), 'font-family': FONT, 'class': 'tl ' + theme(),
      role: 'img', 'aria-label': TL.title });
    el('title', {}, svg, TL.title);
    var defs = el('defs', {}, svg);
    [['tl-arrow', pal.dep], ['tl-arrow-on', pal.accent]].forEach(function (m) {
      var mk = el('marker', { id: m[0], viewBox: '0 0 8 8', refX: 7, refY: 4, markerWidth: 8, markerHeight: 8, markerUnits: 'userSpaceOnUse', orient: 'auto' }, defs);
      el('path', { d: 'M0 0L8 4L0 8z', fill: m[1] }, mk);
    });
    if (!full) {
      var cp = el('clipPath', { id: 'tl-plot' }, defs);
      el('rect', { x: G, y: AXIS, width: Math.max(0, W - G), height: Math.max(0, H - AXIS) }, cp);
    }
    el('rect', { 'class': 'bg', width: Math.round(W), height: Math.round(height), fill: pal.bg }, svg);
    if (full) {
      el('text', { x: 20, y: 30, 'font-size': 18, 'font-weight': 700, fill: pal.ink }, svg, TL.title);
      el('text', { x: 20, y: 50, 'font-size': 12, fill: pal.muted }, svg,
        TL.subtitle || (fmt(FIRST) + ' – ' + fmt(LAST - 1) + ' · ' + list.length + ' items'));
    }

    var body = el('g', { transform: 'translate(0 ' + shift + ')' }, svg);
    L.boxes.forEach(function (b, n) {
      el('rect', { x: 0, y: b.y, width: Math.round(W), height: b.height, fill: n % 2 ? pal.band2 : pal.band, 'class': 'lane' }, body);
    });
    var plot = el('g', full ? {} : { 'clip-path': 'url(#tl-plot)' }, svg);
    var inner = el('g', { transform: 'translate(0 ' + shift + ')' }, plot);

    // grid lines span the lanes; their labels go in the axis drawn later
    var major = MAJOR[unit], ticks = [];
    var day = floorUnit(left, unit), stop = full ? right : right + 1;
    for (var guard = 0; day <= stop && guard < 4000; guard++) {
      var isMajor = !!major && floorUnit(day, major) === day;
      ticks.push([day, isMajor]);
      el('line', { x1: X(day), y1: top - AXIS, x2: X(day), y2: Math.max(bottom, H - shift), stroke: isMajor ? pal.major : pal.grid }, inner);
      day = nextUnit(day, unit);
    }
    L.phases.forEach(function (pb) {
      var p = pb[0], b = pb[1], color = lanesById[p.lane].color, x0 = X(p.start), x1 = X(p.end + 1);
      var g = el('g', { 'class': 'item phase' + (inChain(c, p.id) ? '' : ' dim') + (p.id === S.selected ? ' sel' : ''), 'data-id': p.id }, inner);
      el('rect', { x: x0, y: b.y + 3, width: x1 - x0, height: b.height - 6, rx: 6, fill: color, 'fill-opacity': 0.12,
        stroke: color, 'stroke-opacity': p.id === S.selected ? 1 : 0.55, 'stroke-dasharray': '4 3', 'stroke-width': p.id === S.selected ? 2 : 1 }, g);
      el('text', { x: Math.max(x0, G) + 8, y: b.y + 15, 'font-size': 10, 'font-weight': 700, 'letter-spacing': 0.8, fill: color }, g, p.name.toUpperCase());
    });
    var deps = el('g', { 'class': 'deps', fill: 'none', stroke: pal.dep, 'stroke-width': 1.3 }, inner);
    list.forEach(function (item) {
      item.depends_on.forEach(function (d) {
        var a = L.placed[d], b = L.placed[item.id];
        if (!a || !b) return;
        var on = edgeOn(c, d, item.id);
        el('path', { d: depPath(a, b), 'stroke-linejoin': 'round', 'class': on ? 'on' : c ? 'dim' : '',
          stroke: on ? pal.accent : null, 'stroke-width': on ? 2.2 : null,
          'marker-end': on ? 'url(#tl-arrow-on)' : 'url(#tl-arrow)', 'data-from': d, 'data-to': item.id }, deps);
      });
    });
    Object.keys(L.placed).forEach(function (id) { drawItem(inner, L.placed[id], pal, c, G); });

    // lane labels on an opaque gutter
    var gut = el('g', { transform: 'translate(0 ' + shift + ')' }, svg);
    el('rect', { x: 0, y: top, width: G - 8, height: Math.max(bottom, H - shift) - top, fill: pal.bg }, gut);
    L.boxes.forEach(function (b, n) {
      el('rect', { x: 0, y: b.y, width: G - 8, height: b.height, fill: n % 2 ? pal.band2 : pal.band }, gut);
    });
    el('line', { x1: G - 8, y1: top, x2: G - 8, y2: Math.max(bottom, H - shift), stroke: pal.grid }, gut);
    L.boxes.forEach(function (b) {
      var lane = lanesById[b.id], room = G - 44, name = lane.name;
      if (textWidth(name, 13) > room) name = name.slice(0, Math.max(1, Math.floor(room / (CHAR * 13 / 12)) - 1)) + '…';
      el('rect', { x: 16, y: b.y + 10, width: 4, height: b.height - 20, rx: 2, fill: lane.color }, gut);
      el('text', { x: 28, y: b.y + 24, 'font-size': 13, 'font-weight': 600, fill: pal.ink }, gut, name);
    });

    // axis on top
    var axis = el('g', { 'class': 'axis', 'font-size': 11, fill: pal.muted }, svg);
    el('rect', { x: 0, y: head, width: Math.round(W), height: AXIS, fill: pal.bg }, axis);
    ticks.forEach(function (t) {
      el('line', { x1: X(t[0]), y1: t[1] ? head : head + 22, x2: X(t[0]), y2: top, stroke: t[1] ? pal.major : pal.grid }, axis);
      if (X(t[0]) >= G - 2 && t[0] < (full ? right : stop)) el('text', { x: X(t[0]) + 4, y: head + 37 }, axis, tickLabel(t[0], unit));
    });
    if (major) {
      var marks = [];
      for (var m = floorUnit(left, major), g2 = 0; m < (full ? right : stop) && g2 < 400; g2++, m = nextUnit(m, major)) marks.push(m);
      marks.forEach(function (mday, n) {
        var x = Math.max(X(mday), G), label = majorLabel(mday, major);
        var nx = n + 1 < marks.length ? X(marks[n + 1]) : W;
        if (nx - x >= textWidth(label) + 12)
          el('text', { x: x + 4, y: head + 16, 'font-size': 12, 'font-weight': 600, fill: pal.ink }, axis, label);
      });
    }
    el('rect', { x: 0, y: head, width: G - 8, height: AXIS, fill: pal.bg }, axis);
    el('line', { x1: 0, y1: top, x2: Math.round(W), y2: top, stroke: pal.major }, axis);

    var now = todayDay();
    if (now >= left && now < right) {
      var tx = X(now + 0.5);
      if (tx >= G) {
        var tg = el('g', { 'class': 'today' }, svg);
        el('line', { x1: tx, y1: head + 40, x2: tx, y2: full ? bottom : H, stroke: pal.today, 'stroke-width': 1.5, 'stroke-dasharray': '5 4' }, tg);
        el('rect', { x: tx - 22, y: head + 38, width: 44, height: 14, rx: 7, fill: pal.today }, tg);
        el('text', { x: tx, y: head + 48.5, 'font-size': 9.5, 'font-weight': 700, fill: '#ffffff', 'text-anchor': 'middle' }, tg, 'TODAY');
      }
    }
    if (full) legend(svg, pal, bottom);
    return { svg: svg, layout: L, width: W, height: height };
  }

  function drawItem(parent, p, pal, c, G) {
    var item = p.item, color = pal[item.status], sel = item.id === S.selected;
    var g = el('g', { 'class': 'item ' + item.kind + ' st-' + item.status + (inChain(c, item.id) ? '' : ' dim') + (sel ? ' sel' : ''),
      'data-id': item.id }, parent);
    el('title', {}, g, item.name);
    var cx = (p.x0 + p.x1) / 2, cy = p.y;
    if (sel) el('rect', { x: p.x0 - 5, y: cy - BAR / 2 - 5, width: Math.max(26, p.x1 - p.x0 + 10), height: BAR + 10, rx: 8,
      fill: 'none', stroke: pal.accent, 'stroke-width': 2, 'class': 'halo' }, g);
    if (item.kind === 'milestone') {
      el('path', { d: 'M' + cx + ' ' + (cy - 8) + 'L' + (cx + 8) + ' ' + cy + 'L' + cx + ' ' + (cy + 8) + 'L' + (cx - 8) + ' ' + cy + 'Z',
        fill: color, stroke: pal.bg, 'stroke-width': 1.5 }, g);
      el('text', { x: cx + 12, y: cy + 4, 'font-size': 12, fill: pal.ink }, g, item.name);
      return;
    }
    if (item.kind === 'release') {
      el('line', { x1: cx, y1: cy - 10, x2: cx, y2: cy + 10, stroke: color, 'stroke-width': 2 }, g);
      el('path', { d: 'M' + cx + ' ' + (cy - 10) + 'H' + (cx + 11) + 'L' + (cx + 8) + ' ' + (cy - 5.5) + 'L' + (cx + 11) + ' ' + (cy - 1) + 'H' + cx + 'Z', fill: color }, g);
      el('circle', { cx: cx, cy: cy + 10, r: 2.2, fill: color }, g);
      el('text', { x: cx + 14, y: cy + 4, 'font-size': 12, 'font-weight': 600, fill: pal.ink }, g, item.name);
      return;
    }
    var w = Math.max(2, p.x1 - p.x0), y = cy - BAR / 2;
    el('rect', { x: p.x0, y: y, width: w, height: BAR, rx: 5, fill: color, 'fill-opacity': 0.16, stroke: color, 'stroke-width': 1.4,
      'stroke-dasharray': item.status === 'blocked' ? '4 3' : null, 'class': 'bar' }, g);
    if (item.progress > 0) el('rect', { x: p.x0, y: y, width: w * item.progress / 100, height: BAR, rx: 5, fill: color, 'fill-opacity': 0.5, 'class': 'progress' }, g);
    if (w > 14) el('rect', { x: p.x0 + 3, y: y + 4, width: 3, height: BAR - 8, rx: 1.5, fill: lanesById[item.lane].color }, g);
    // a bar that starts left of the view keeps its name in sight, inside the bar
    if (p.inside) el('text', { x: Math.max(p.x0 + 10, Math.min(G + 8, p.x1 - textWidth(item.name) - 10)), y: cy + 4, 'font-size': 12, 'font-weight': 600, fill: pal.ink }, g, item.name);
    else el('text', { x: p.x1 + 6, y: cy + 4, 'font-size': 12, fill: pal.ink }, g, item.name);
  }

  function legend(svg, pal, bottom) {
    var y = bottom + 26, x = 20, g = el('g', { 'class': 'legend', 'font-size': 11, fill: pal.muted }, svg);
    Object.keys(LABELS).forEach(function (s) {
      el('rect', { x: x, y: y - 9, width: 18, height: 10, rx: 3, fill: pal[s], 'fill-opacity': 0.35, stroke: pal[s],
        'stroke-dasharray': s === 'blocked' ? '3 2' : null }, g);
      el('text', { x: x + 24, y: y }, g, LABELS[s]);
      x += 34 + textWidth(LABELS[s], 11);
    });
    x += 10;
    var m = pal.muted;
    el('rect', { x: x, y: y - 10, width: 22, height: 12, rx: 3, fill: m, 'fill-opacity': 0.15, stroke: m, 'stroke-dasharray': '3 2' }, g);
    el('text', { x: x + 28, y: y }, g, 'Phase'); x += 74;
    el('path', { d: 'M' + (x + 6) + ' ' + (y - 10) + 'L' + (x + 12) + ' ' + (y - 4) + 'L' + (x + 6) + ' ' + (y + 2) + 'L' + x + ' ' + (y - 4) + 'Z', fill: m }, g);
    el('text', { x: x + 18, y: y }, g, 'Milestone'); x += 86;
    el('line', { x1: x + 1, y1: y - 11, x2: x + 1, y2: y + 3, stroke: m, 'stroke-width': 2 }, g);
    el('path', { d: 'M' + (x + 1) + ' ' + (y - 11) + 'h9l-2.5 3.5l2.5 3.5h-9z', fill: m }, g);
    el('text', { x: x + 16, y: y }, g, 'Release'); x += 76;
    el('line', { x1: x, y1: y - 4, x2: x + 22, y2: y - 4, stroke: pal.dep, 'stroke-width': 1.3, 'marker-end': 'url(#tl-arrow)' }, g);
    el('text', { x: x + 30, y: y }, g, 'Depends on'); x += 108;
    el('line', { x1: x + 6, y1: y - 12, x2: x + 6, y2: y + 4, stroke: pal.today, 'stroke-width': 1.5, 'stroke-dasharray': '4 3' }, g);
    el('text', { x: x + 14, y: y }, g, 'Today');
  }

  var last = null, queued = false;
  function render() {
    queued = false;
    var out = draw();
    last = out;
    stage.replaceChildren(out.svg);
    var unit = tickUnit(S.ppd);
    document.querySelectorAll('[data-level]').forEach(function (b) {
      b.setAttribute('aria-pressed', String(b.getAttribute('data-level') === unit));
    });
  }
  function schedule() { if (!queued) { queued = true; window.requestAnimationFrame(render); } }

  // ---- view: fit, zoom, pan, now --------------------------------------------------------------------
  function plotWidth() { return Math.max(40, view.clientWidth - gutter() - 16); }
  function fit() {
    var span = Math.max(1, LAST - FIRST), pad = Math.max(1, span * 0.03), reserve = 0;
    // leave room for the names of milestones and releases near the end
    items.forEach(function (i) {
      if (i.point && i.end >= LAST - span * 0.2) reserve = Math.max(reserve, 16 + textWidth(i.name));
    });
    reserve = Math.min(reserve, plotWidth() * 0.35);
    S.ppd = Math.min(MAX_PPD, Math.max(MIN_PPD, (plotWidth() - reserve) / (span + 2 * pad)));
    S.t0 = FIRST - pad; S.sy = 0;
    render();
  }
  function zoomTo(ppd, px) {
    var G = gutter(), anchor = px === undefined ? G + plotWidth() / 2 : Math.max(G, px);
    var day = S.t0 + (anchor - G) / S.ppd;
    S.ppd = Math.min(MAX_PPD, Math.max(MIN_PPD, ppd));
    S.t0 = day - (anchor - G) / S.ppd;
    clampPan();
    schedule();
  }
  function clampPan() {
    var days = plotWidth() / S.ppd;
    S.t0 = Math.max(FIRST - days * 0.75, Math.min(S.t0, LAST - days * 0.25));
  }
  function panBy(dx, dy) { S.t0 -= dx / S.ppd; S.sy -= dy; clampPan(); schedule(); }
  function goNow() {
    S.t0 = todayDay() + 0.5 - plotWidth() / 2 / S.ppd;
    render();
  }

  // ---- detail card ----------------------------------------------------------------------------------
  function h(tag, text, cls) { var n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (cls) n.className = cls; return n; }
  function openLink(url) {
    if (!/^https:\/\/[^\s"'<>]+$/.test(url || '')) return;
    if (window.parent !== window) {
      window.parent.postMessage({ type: 'uml-mcp/open-link', url: url }, '*');
      if (hostBridge) return;
    }
    window.open(url, '_blank', 'noopener,noreferrer');
  }
  function itemList(title, ids) {
    var box = document.createDocumentFragment();
    if (!ids.length) return box;
    box.appendChild(h('dt', title));
    var dd = h('dd'), ul = h('ul', undefined, 'links');
    ids.forEach(function (id) {
      var li = h('li'), b = h('button', byId[id].name);
      b.type = 'button'; b.className = 's-' + byId[id].status;
      b.addEventListener('click', function () { select(id, true); });
      li.appendChild(b); ul.appendChild(li);
    });
    dd.appendChild(ul); box.appendChild(dd);
    return box;
  }
  function select(id, reveal) {
    var item = byId[id];
    if (!item) return;
    if (!visible(item)) { S.lane = ''; S.owner = ''; S.status = ''; syncFilters(); }
    S.selected = id;
    var lane = lanesById[item.lane];
    var close = h('button', '×', 'close'); close.type = 'button'; close.setAttribute('aria-label', 'Close');
    close.addEventListener('click', clear);
    var kicker = h('div', item.kind + ' · ' + lane.name, 'kicker');
    var chips = h('div', undefined, 'chips');
    chips.appendChild(h('span', LABELS[item.status], 'chip s-' + item.status));
    var dl = h('dl');
    function row(k, v) { dl.appendChild(h('dt', k)); dl.appendChild(h('dd', v)); }
    if (item.point) row('Date', fmt(item.start));
    else {
      row('Dates', fmt(item.start) + ' → ' + fmt(item.end));
      var days = item.end - item.start + 1, weeks = days / 7;
      row('Duration', days + (days === 1 ? ' day' : ' days') + (days >= 14 ? ' (' + (Math.round(weeks * 10) / 10) + ' weeks)' : ''));
    }
    if (item.owner) row('Owner', item.owner);
    if (!item.point) {
      dl.appendChild(h('dt', 'Progress'));
      var dd = h('dd', undefined, 'progress-row'), bar = document.createElement('progress');
      bar.max = 100; bar.value = item.progress; bar.setAttribute('aria-label', 'Progress');
      dd.appendChild(bar); dd.appendChild(h('span', item.progress + '%')); dl.appendChild(dd);
    }
    dl.appendChild(itemList('Depends on', item.depends_on));
    dl.appendChild(itemList('Blocks', dependents[id]));
    var c = chain(), up = Object.keys(c.up).length, down = Object.keys(c.down).length;
    if (up || down) row('Chain', up + ' upstream · ' + down + ' downstream');
    card.replaceChildren(close, kicker, h('h2', item.name), chips, dl);
    if (item.note) card.appendChild(h('p', item.note, 'note'));
    if (item.link) {
      var open = h('button', 'Open link', 'primary'); open.type = 'button'; open.id = 'open-link';
      open.addEventListener('click', function () { openLink(item.link); });
      card.appendChild(open);
    }
    card.hidden = false;
    if (reveal) revealItem(item);
    render();
  }
  function revealItem(item) {
    var a = item.start, b = item.end + 1, days = plotWidth() / S.ppd;
    if (b - a > days) S.ppd = Math.max(MIN_PPD, plotWidth() / ((b - a) * 1.2));
    days = plotWidth() / S.ppd;
    if (a < S.t0 || b > S.t0 + days) S.t0 = (a + b) / 2 - days / 2;
  }
  function clear() { S.selected = null; card.hidden = true; card.replaceChildren(); render(); }

  // ---- pointer: pan, pinch, click, wheel -----------------------------------------------------------
  var pointers = {}, moved = 0, pinch = null;
  view.addEventListener('pointerdown', function (e) {
    if (card.contains(e.target)) return;
    view.setPointerCapture(e.pointerId);
    pointers[e.pointerId] = [e.clientX, e.clientY];
    var ids = Object.keys(pointers);
    if (ids.length === 2) {
      var p = pointers[ids[0]], q = pointers[ids[1]];
      pinch = { d: Math.hypot(p[0] - q[0], p[1] - q[1]), ppd: S.ppd };
    } else { moved = 0; view.classList.add('drag'); }
  });
  view.addEventListener('pointermove', function (e) {
    var prev = pointers[e.pointerId];
    if (!prev) return;
    pointers[e.pointerId] = [e.clientX, e.clientY];
    var ids = Object.keys(pointers);
    if (pinch && ids.length === 2) {
      var p = pointers[ids[0]], q = pointers[ids[1]], r = view.getBoundingClientRect();
      var d = Math.hypot(p[0] - q[0], p[1] - q[1]);
      moved += 10;
      zoomTo(pinch.ppd * d / Math.max(1, pinch.d), (p[0] + q[0]) / 2 - r.left);
      return;
    }
    var dx = e.clientX - prev[0], dy = e.clientY - prev[1];
    moved += Math.abs(dx) + Math.abs(dy);
    if (moved > 4) panBy(dx, dy);
  });
  function up(e) {
    var was = pointers[e.pointerId];
    delete pointers[e.pointerId];
    if (Object.keys(pointers).length < 2) pinch = null;
    view.classList.remove('drag');
    if (!was || moved > 4 || e.type === 'pointercancel') return;
    var hit = e.target && e.target.closest ? e.target.closest('.item') : null;
    if (!hit) { var under = document.elementFromPoint(e.clientX, e.clientY); hit = under && under.closest ? under.closest('.item') : null; }
    if (hit) select(hit.getAttribute('data-id'), false); else if (S.selected) clear();
  }
  view.addEventListener('pointerup', up);
  view.addEventListener('pointercancel', up);
  view.addEventListener('wheel', function (e) {
    e.preventDefault();
    var r = view.getBoundingClientRect();
    if (e.shiftKey || Math.abs(e.deltaX) > Math.abs(e.deltaY)) { panBy(-(e.deltaX || e.deltaY), 0); return; }
    zoomTo(S.ppd * Math.exp(-e.deltaY * (e.ctrlKey ? 0.01 : 0.0015)), e.clientX - r.left);
  }, { passive: false });
  document.addEventListener('keydown', function (e) {
    if (e.target && /^(SELECT|INPUT|TEXTAREA)$/.test(e.target.tagName)) return;
    if (e.key === 'Escape') { if (S.selected) clear(); }
    else if (e.key === '+' || e.key === '=') zoomTo(S.ppd * 1.4);
    else if (e.key === '-') zoomTo(S.ppd / 1.4);
    else if (e.key === '0') fit();
    else if (e.key === 'ArrowLeft') panBy(80, 0);
    else if (e.key === 'ArrowRight') panBy(-80, 0);
    else if (e.key === 'ArrowUp') panBy(0, 60);
    else if (e.key === 'ArrowDown') panBy(0, -60);
    else return;
    e.preventDefault();
  });

  // ---- toolbar ------------------------------------------------------------------------------------------
  document.querySelectorAll('[data-level]').forEach(function (b) {
    b.addEventListener('click', function () { zoomTo(LEVELS[b.getAttribute('data-level')]); });
  });
  document.getElementById('zin').addEventListener('click', function () { zoomTo(S.ppd * 1.5); });
  document.getElementById('zout').addEventListener('click', function () { zoomTo(S.ppd / 1.5); });
  document.getElementById('fit').addEventListener('click', fit);
  document.getElementById('now').addEventListener('click', goNow);
  var themeBtn = document.getElementById('theme');
  function themeLabel() { themeBtn.textContent = theme() === 'dark' ? 'Light' : 'Dark'; }
  themeBtn.addEventListener('click', function () {
    root.setAttribute('data-theme', theme() === 'dark' ? 'light' : 'dark');
    root.setAttribute('data-auto', '0');
    themeLabel(); render();
  });
  var filters = { lane: document.getElementById('f-lane'), owner: document.getElementById('f-owner'), status: document.getElementById('f-status') };
  function syncFilters() { Object.keys(filters).forEach(function (k) { filters[k].value = S[k]; }); }
  Object.keys(filters).forEach(function (k) {
    filters[k].addEventListener('change', function () {
      S[k] = filters[k].value;
      if (S.selected && !visible(byId[S.selected])) { S.selected = null; card.hidden = true; }
      S.sy = 0;
      render();
    });
  });

  // ---- export -------------------------------------------------------------------------------------------
  function fileName(ext) {
    return ((TL.title || 'timeline').replace(/[^A-Za-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '') || 'timeline') + '.' + ext;
  }
  function download(content, type, name) {
    var blob = content instanceof Blob ? content : new Blob([content], { type: type });
    if (hostBridge) {
      var reader = new FileReader();
      reader.onload = function () {
        window.parent.postMessage({ type: 'uml-mcp/plugin-download', filename: name, mime_type: type,
          blob: String(reader.result).split(',')[1] }, '*');
      };
      reader.readAsDataURL(blob);
      return;
    }
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
  }
  function svgText() {
    var out = draw({ full: true });
    return { text: '<?xml version="1.0" encoding="UTF-8"?>\n' + new XMLSerializer().serializeToString(out.svg), width: out.width, height: out.height };
  }
  function pngBlob(done) {
    var s = svgText(), scale = Math.min(2, 8192 / Math.max(s.width, s.height));
    var img = new Image();
    img.onload = function () {
      var canvas = document.createElement('canvas');
      canvas.width = Math.max(1, Math.round(s.width * scale));
      canvas.height = Math.max(1, Math.round(s.height * scale));
      var ctx = canvas.getContext('2d');
      ctx.scale(scale, scale);
      ctx.drawImage(img, 0, 0, s.width, s.height);
      canvas.toBlob(done, 'image/png');
    };
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(s.text);
  }
  function htmlText() {
    var doc = root.cloneNode(true);
    doc.removeAttribute('data-embedded');
    doc.setAttribute('data-theme', theme());
    doc.setAttribute('data-auto', '0');
    doc.querySelector('#stage').replaceChildren();
    var c = doc.querySelector('#card'); c.replaceChildren(); c.setAttribute('hidden', '');
    var menu = doc.querySelector('details.menu'); if (menu) menu.removeAttribute('open');
    doc.querySelectorAll('[style]').forEach(function (n) { n.removeAttribute('style'); });
    doc.querySelectorAll('select').forEach(function (s) { s.querySelectorAll('option').forEach(function (o) { o.removeAttribute('selected'); }); });
    return '<!doctype html>\n' + doc.outerHTML;
  }
  var menu = document.querySelector('details.menu');
  function closeMenu() { if (menu) menu.removeAttribute('open'); }
  document.getElementById('save').addEventListener('click', function () { closeMenu(); download(svgText().text, 'image/svg+xml', fileName('svg')); });
  document.getElementById('png').addEventListener('click', function () { closeMenu(); pngBlob(function (b) { if (b) download(b, 'image/png', fileName('png')); }); });
  document.getElementById('html').addEventListener('click', function () { closeMenu(); download(htmlText(), 'text/html', fileName('html')); });

  if (window.parent !== window) {
    window.addEventListener('message', function (event) {
      if (event.source !== window.parent || !event.data) return;
      if (event.data.type === 'uml-mcp/plugin-bridge-ready') { hostBridge = true; return; }
      if (event.data.type !== 'uml-mcp/plugin-export') return;
      var id = { svg: 'save', png: 'png', html: 'html' }[event.data.format];
      var control = id && document.getElementById(id);
      if (control) control.click();
    });
    window.parent.postMessage({ type: 'uml-mcp/plugin-ready', exports: ['svg', 'png', 'html'] }, '*');
  }

  var lastW = 0;
  window.addEventListener('resize', function () {
    if (Math.abs(view.clientWidth - lastW) > 1 && !S.selected && S.fitted) fit(); else schedule();
    lastW = view.clientWidth;
  });
  themeLabel();
  fit();
  S.fitted = true;
  lastW = view.clientWidth;
  ['zin', 'zout'].forEach(function (id) { document.getElementById(id).addEventListener('click', function () { S.fitted = false; }); });
  view.addEventListener('wheel', function () { S.fitted = false; });
  document.getElementById('fit').addEventListener('click', function () { S.fitted = true; });
  document.body.setAttribute('data-ready', '1');

  window.__timeline = {
    state: S, select: select, clear: clear, fit: fit, zoomTo: zoomTo, goNow: goNow, panBy: panBy,
    draw: draw, svgText: function () { return svgText().text; }, htmlText: htmlText, levels: LEVELS,
    tickUnit: tickUnit, today: todayDay, get last() { return last; }
  };
})();
