/* Orthogonal edge routing with A* on a grid.
 *
 * A line-for-line twin of router.py: boxes are obstacles, and a path pays for its length,
 * for every turn, and for running over or crossing edges routed before it. Costs are
 * integers and neighbours are tried in a fixed order so both implementations return the
 * same path (the Python tests check that with Node). Used to route an arrow again while
 * its box is dragged.
 */
var UmlRouter = (function () {
  'use strict';

  var STEP = 10, TURN = 30, OVERLAP = 40, CROSS = 16, MAX_EXPANSIONS = 60000, LABEL_MARGIN = 3;
  var DIRS = [[1, 0], [0, 1], [-1, 0], [0, -1]]; // E, S, W, N

  function snap(value, origin, cell) {
    return Math.floor((value - origin) / cell + 0.5);
  }

  function Grid(rects, opts) {
    opts = opts || {};
    var cell = opts.cell || 10;
    var margin = opts.margin === undefined ? 8 : opts.margin;
    var pad = opts.pad === undefined ? 80 : opts.pad;
    var xs = [], ys = [];
    rects.forEach(function (r) { xs.push(r[0], r[0] + r[2]); ys.push(r[1], r[1] + r[3]); });
    if (!xs.length) { xs = [0]; ys = [0]; }
    this.cell = cell;
    this.margin = margin;
    // a whole number of cells, so a stub from an anchor on the grid is on the grid too
    this.stub = Math.ceil((margin + cell) / cell) * cell;
    this.ox = Math.floor((Math.min.apply(null, xs) - pad) / cell) * cell;
    this.oy = Math.floor((Math.min.apply(null, ys) - pad) / cell) * cell;
    this.cols = Math.ceil((Math.max.apply(null, xs) + pad - this.ox) / cell) + 1;
    this.rows = Math.ceil((Math.max.apply(null, ys) + pad - this.oy) / cell) + 1;
    this.blocked = new Set();
    this.usage = new Map();
    for (var k = 0; k < rects.length; k++) {
      var x = rects[k][0], y = rects[k][1], w = rects[k][2], h = rects[k][3];
      var loX = snap(x - margin, this.ox, cell) - 1, hiX = snap(x + w + margin, this.ox, cell) + 1;
      var loY = snap(y - margin, this.oy, cell) - 1, hiY = snap(y + h + margin, this.oy, cell) + 1;
      for (var iy = Math.max(loY, 0); iy <= Math.min(hiY, this.rows - 1); iy++) {
        var py = this.oy + iy * cell;
        if (!(y - margin < py && py < y + h + margin)) continue;
        for (var ix = Math.max(loX, 0); ix <= Math.min(hiX, this.cols - 1); ix++) {
          var px = this.ox + ix * cell;
          if (x - margin < px && px < x + w + margin) this.blocked.add(iy * this.cols + ix);
        }
      }
    }
  }

  Grid.prototype.index = function (x, y) {
    var ix = Math.min(Math.max(snap(x, this.ox, this.cell), 0), this.cols - 1);
    var iy = Math.min(Math.max(snap(y, this.oy, this.cell), 0), this.rows - 1);
    return iy * this.cols + ix;
  };

  Grid.prototype.point = function (index) {
    return [this.ox + (index % this.cols) * this.cell, this.oy + Math.floor(index / this.cols) * this.cell];
  };

  Grid.prototype.mark = function (points) {
    for (var i = 0; i + 1 < points.length; i++) {
      var x1 = points[i][0], y1 = points[i][1], x2 = points[i + 1][0], y2 = points[i + 1][1];
      var a, b, fixed, k, idx;
      if (y1 === y2) {
        a = snap(x1, this.ox, this.cell); b = snap(x2, this.ox, this.cell); fixed = snap(y1, this.oy, this.cell);
        for (k = Math.min(a, b); k <= Math.max(a, b); k++) {
          if (k >= 0 && k < this.cols && fixed >= 0 && fixed < this.rows) {
            idx = fixed * this.cols + k;
            this.usage.set(idx, (this.usage.get(idx) || 0) | 1);
          }
        }
      } else if (x1 === x2) {
        a = snap(y1, this.oy, this.cell); b = snap(y2, this.oy, this.cell); fixed = snap(x1, this.ox, this.cell);
        for (k = Math.min(a, b); k <= Math.max(a, b); k++) {
          if (k >= 0 && k < this.rows && fixed >= 0 && fixed < this.cols) {
            idx = k * this.cols + fixed;
            this.usage.set(idx, (this.usage.get(idx) || 0) | 2);
          }
        }
      }
    }
  };

  // Binary min-heap of [f, h, seq, state], ordered by f, then h, then seq.
  function less(p, q) {
    if (p[0] !== q[0]) return p[0] < q[0];
    if (p[1] !== q[1]) return p[1] < q[1];
    return p[2] < q[2];
  }
  function push(heap, item) {
    heap.push(item);
    var i = heap.length - 1;
    while (i > 0) {
      var parent = (i - 1) >> 1;
      if (!less(heap[i], heap[parent])) break;
      var t = heap[i]; heap[i] = heap[parent]; heap[parent] = t;
      i = parent;
    }
  }
  function pop(heap) {
    var top = heap[0], last = heap.pop();
    if (heap.length) {
      heap[0] = last;
      var i = 0, n = heap.length;
      for (;;) {
        var l = 2 * i + 1, r = l + 1, m = i;
        if (l < n && less(heap[l], heap[m])) m = l;
        if (r < n && less(heap[r], heap[m])) m = r;
        if (m === i) break;
        var t = heap[i]; heap[i] = heap[m]; heap[m] = t;
        i = m;
      }
    }
    return top;
  }

  function astar(grid, start, goal, startDir) {
    var cols = grid.cols;
    var gx = goal % cols, gy = Math.floor(goal / cols);
    var sx = start % cols, sy = Math.floor(start / cols);
    var gCost = new Map(), came = new Map(), closed = new Set();
    var startState = start * 4 + startDir;
    gCost.set(startState, 0);
    var h0 = STEP * (Math.abs(sx - gx) + Math.abs(sy - gy));
    var heap = [[h0, h0, 0, startState]];
    var seq = 0, expansions = 0;
    while (heap.length) {
      var state = pop(heap)[3];
      if (closed.has(state)) continue;
      closed.add(state);
      var idx = Math.floor(state / 4), d = state % 4;
      if (idx === goal) {
        var path = [idx];
        while (came.has(state)) { state = came.get(state); path.push(Math.floor(state / 4)); }
        path.reverse();
        return path;
      }
      expansions++;
      if (expansions > MAX_EXPANSIONS) return null;
      var x = idx % cols, y = Math.floor(idx / cols), base = gCost.get(state);
      for (var nd = 0; nd < 4; nd++) {
        if (nd === (d + 2) % 4) continue;
        var nx = x + DIRS[nd][0], ny = y + DIRS[nd][1];
        if (nx < 0 || ny < 0 || nx >= cols || ny >= grid.rows) continue;
        var nidx = ny * cols + nx;
        if (nidx !== start && nidx !== goal && grid.blocked.has(nidx)) continue;
        var cost = base + STEP + (nd !== d ? TURN : 0);
        var used = grid.usage.get(nidx) || 0;
        if (used) cost += (used & (nd % 2 === 0 ? 1 : 2)) ? OVERLAP : CROSS;
        var nstate = nidx * 4 + nd;
        var known = gCost.get(nstate);
        if (known === undefined || cost < known) {
          gCost.set(nstate, cost);
          came.set(nstate, state);
          seq++;
          var h = STEP * (Math.abs(nx - gx) + Math.abs(ny - gy));
          push(heap, [cost + h, h, seq, nstate]);
        }
      }
    }
    return null;
  }

  function simplify(points) {
    var out = [];
    points.forEach(function (p) {
      var last = out[out.length - 1];
      if (!last || last[0] !== p[0] || last[1] !== p[1]) out.push(p);
    });
    var result = [];
    out.forEach(function (p, i) {
      if (i > 0 && i < out.length - 1) {
        var a = out[i - 1], b = out[i + 1];
        if ((p[0] - a[0]) * (b[1] - p[1]) - (p[1] - a[1]) * (b[0] - p[0]) === 0) return;
      }
      result.push(p);
    });
    return result;
  }

  function elbow(stub, snapped, horizontal) {
    return [stub, horizontal ? [stub[0], snapped[1]] : [snapped[0], stub[1]], snapped];
  }

  function route(grid, a, aDir, b, bDir) {
    var s = grid.stub;
    var sa = [a[0] + DIRS[aDir][0] * s, a[1] + DIRS[aDir][1] * s];
    var sb = [b[0] + DIRS[bDir][0] * s, b[1] + DIRS[bDir][1] * s];
    var cells = astar(grid, grid.index(sa[0], sa[1]), grid.index(sb[0], sb[1]), aDir);
    var points;
    if (cells === null) {
      var midX = (sa[0] + sb[0]) / 2;
      points = simplify([a, sa, [midX, sa[1]], [midX, sb[1]], sb, b]);
    } else {
      var gp = cells.map(function (i) { return grid.point(i); });
      points = simplify(
        [a].concat(elbow(sa, gp[0], aDir % 2 === 0), gp.slice(1, -1),
          elbow(sb, gp[gp.length - 1], bDir % 2 === 0).reverse(), [b]));
    }
    grid.mark(points);
    return points;
  }

  function fmt(value) {
    var text = value.toFixed(1);
    return text.slice(-2) === '.0' ? text.slice(0, -2) : text;
  }

  function roundedPath(points, radius) {
    if (!points.length) return '';
    radius = radius === undefined ? 8 : radius;
    var parts = ['M' + fmt(points[0][0]) + ',' + fmt(points[0][1])];
    for (var i = 1; i < points.length - 1; i++) {
      var p = points[i], prev = points[i - 1], next = points[i + 1];
      var len1 = Math.hypot(p[0] - prev[0], p[1] - prev[1]);
      var len2 = Math.hypot(next[0] - p[0], next[1] - p[1]);
      var r = Math.min(radius, len1 / 2, len2 / 2);
      if (r <= 0) { parts.push('L' + fmt(p[0]) + ',' + fmt(p[1])); continue; }
      var ax = p[0] - (p[0] - prev[0]) / len1 * r, ay = p[1] - (p[1] - prev[1]) / len1 * r;
      var bx = p[0] + (next[0] - p[0]) / len2 * r, by = p[1] + (next[1] - p[1]) / len2 * r;
      parts.push('L' + fmt(ax) + ',' + fmt(ay) + 'Q' + fmt(p[0]) + ',' + fmt(p[1]) + ' ' + fmt(bx) + ',' + fmt(by));
    }
    var end = points[points.length - 1];
    parts.push('L' + fmt(end[0]) + ',' + fmt(end[1]));
    return parts.join('');
  }

  // Where an arrow's label goes: on a straight run that is long enough, clear of the boxes
  // (twin of label_point). Runs are tried best first, and on each the middle and, for a long
  // run, the quarter points; the first spot where the label touches no box wins.
  function labelPoint(points, width, boxes) {
    var runs = [], i;
    for (i = 0; i + 1 < points.length; i++) {
      runs.push({
        len: Math.hypot(points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1]),
        a: points[i], b: points[i + 1], index: i
      });
    }
    if (!runs.length) return points[0];
    var need = width + 24, last = runs.length - 1;
    function rank(r) {
      var head = r.index === last && last > 0, fits = r.len >= need;
      return fits && !head ? 0 : fits ? 1 : 2;
    }
    var ordered = runs.slice().sort(function (p, q) {
      return (rank(p) - rank(q)) || (q.len - p.len) || (p.index - q.index);
    });
    var candidates = [];
    ordered.forEach(function (r) {
      (r.len >= need ? [0.5, 0.25, 0.75] : [0.5]).forEach(function (t) {
        candidates.push([r.a[0] + (r.b[0] - r.a[0]) * t, r.a[1] + (r.b[1] - r.a[1]) * t]);
      });
    });
    var halfW = width / 2 + LABEL_MARGIN, halfH = 8 + LABEL_MARGIN, list = boxes || [];
    for (i = 0; i < candidates.length; i++) {
      var x = candidates[i][0], y = candidates[i][1], hit = false;
      for (var k = 0; k < list.length; k++) {
        var b = list[k];
        if (x - halfW < b[0] + b[2] && b[0] < x + halfW && y - halfH < b[1] + b[3] && b[1] < y + halfH) { hit = true; break; }
      }
      if (!hit) return candidates[i];
    }
    return candidates[0];
  }

  function pathMidpoint(points) {
    var lengths = [], total = 0, i;
    for (i = 0; i + 1 < points.length; i++) {
      var len = Math.hypot(points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1]);
      lengths.push(len); total += len;
    }
    var half = total / 2;
    for (i = 0; i < lengths.length; i++) {
      if (half <= lengths[i] && lengths[i] > 0) {
        var t = half / lengths[i];
        return [points[i][0] + (points[i + 1][0] - points[i][0]) * t, points[i][1] + (points[i + 1][1] - points[i][1]) * t];
      }
      half -= lengths[i];
    }
    return points[points.length - 1];
  }

  return { Grid: Grid, route: route, simplify: simplify, roundedPath: roundedPath, pathMidpoint: pathMidpoint, labelPoint: labelPoint, DIRS: DIRS };
})();
if (typeof module !== 'undefined' && module.exports) module.exports = UmlRouter;
