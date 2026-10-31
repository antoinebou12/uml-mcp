/* Interactive architecture / topology diagram.
 *
 * The SVG is drawn by the server. This adds, with D3: draggable boxes that cannot overlap
 * each other, group boxes that resize around their members, and arrows that are routed
 * again around the boxes (UmlRouter, A*) while a box moves. Zoom, pan, tooltips and the
 * exports come from UmlViewer. Text is only ever set with textContent, never as markup.
 */
(function () {
  'use strict';

  var data = JSON.parse(document.getElementById('spec').textContent);
  var C = data.consts;
  var svg = d3.select('#diagram');
  var vp = svg.select('g.viewport');

  var nodes = {}, initial = {};
  data.nodes.forEach(function (n) { nodes[n.id] = n; initial[n.id] = [n.x, n.y]; });
  var nodeEls = {};
  vp.selectAll('g.node').each(function () { nodeEls[this.getAttribute('data-id')] = d3.select(this); });
  var groupEls = {};
  vp.selectAll('g.group').each(function () { groupEls[this.getAttribute('data-id')] = d3.select(this); });

  var edges = data.edges.map(function (e) {
    var el = vp.select('g.edge[data-id="' + e.id + '"]');
    return {
      id: e.id, from: e.from, to: e.to, srcOffset: e.srcOffset, dstOffset: e.dstOffset,
      srcDir: e.srcDir, dstDir: e.dstDir, points: e.points, labelWidth: e.labelWidth,
      initialPoints: e.points.map(function (p) { return p.slice(); }),
      el: el, path: el.select('path'), label: el.select('g.edge-label')
    };
  });
  var incident = {};
  edges.forEach(function (e) {
    (incident[e.from] = incident[e.from] || []).push(e.id);
    (incident[e.to] = incident[e.to] || []).push(e.id);
  });

  // ---------------------------------------------------------------- groups
  var children = {}, members = {}, rootGroups = [];
  data.groups.forEach(function (g) { children[g.id] = children[g.id] || []; });
  data.groups.forEach(function (g) {
    if (g.parent) children[g.parent].push(g.id);
    else rootGroups.push(g.id);
  });
  data.nodes.forEach(function (n) { if (n.group) (members[n.group] = members[n.group] || []).push(n); });

  function groupRect(id, out) {
    var parts = (members[id] || []).map(function (n) { return [n.x, n.y, n.w, n.h]; });
    (children[id] || []).forEach(function (c) { parts.push(groupRect(c, out)); });
    var x1 = Math.min.apply(null, parts.map(function (p) { return p[0]; }));
    var y1 = Math.min.apply(null, parts.map(function (p) { return p[1]; }));
    var x2 = Math.max.apply(null, parts.map(function (p) { return p[0] + p[2]; }));
    var y2 = Math.max.apply(null, parts.map(function (p) { return p[1] + p[3]; }));
    var r = [x1 - C.groupPad, y1 - C.groupPad - C.groupHeader, x2 - x1 + 2 * C.groupPad, y2 - y1 + 2 * C.groupPad + C.groupHeader];
    out[id] = r;
    return r;
  }

  function updateGroups() {
    var rects = {};
    rootGroups.forEach(function (id) { groupRect(id, rects); });
    Object.keys(rects).forEach(function (id) {
      var r = rects[id], el = groupEls[id];
      el.select('rect').attr('x', r[0]).attr('y', r[1]).attr('width', r[2]).attr('height', r[3]);
      // the title sits on the border line, its halo breaks the dashes behind it
      el.select('text').attr('x', r[0] + 14).attr('y', r[1] + 4);
    });
  }

  // ----------------------------------------------------------------- edges
  function boxRects() {
    return data.nodes.map(function (n) { return [n.x, n.y, n.w, n.h]; });
  }

  function drawEdge(e, rects) {
    e.path.attr('d', UmlRouter.roundedPath(e.points));
    if (!e.label.empty()) {
      var mid = UmlRouter.labelPoint(e.points, e.labelWidth, rects || boxRects());
      e.label.attr('transform', 'translate(' + mid[0] + ' ' + mid[1] + ')');
    }
  }

  function routeEdges(subset) {
    var rects = boxRects();
    data.groups.forEach(function(g) {
      var bounds = groupEls[g.id].select('rect.group-box');
      var title = g.label || groupEls[g.id].select('text').text() || g.id;
      rects.push([+bounds.attr('x') + 10, +bounds.attr('y') - 10, title.length * 6.6 + 12, 20]);
    });
    var labels = rects.slice();
    function reserveLabel(e) {
      if (e.label.empty()) return;
      var p = /translate\(([-\d.]+)[ ,]+([-\d.]+)\)/.exec(e.label.attr('transform') || '');
      if (p) labels.push([+p[1] - e.labelWidth / 2 - 3, +p[2] - 11, e.labelWidth + 6, 22]);
    }
    var grid = new UmlRouter.Grid(boxRects(), { cell: C.gridCell, margin: C.gridMargin });
    rects.slice(data.nodes.length).forEach(function(r) {
      [5,10,15].forEach(function(dy) {grid.mark([[r[0],r[1]+dy],[r[0]+r[2],r[1]+dy]]);});
    });
    if (subset) edges.forEach(function (e) { if (!subset[e.id]) { grid.mark(e.points); reserveLabel(e); } });
    edges.forEach(function (e) {
      if (subset && !subset[e.id]) return;
      var a = nodes[e.from], b = nodes[e.to];
      e.points = UmlRouter.route(
        grid,
        [a.x + e.srcOffset[0], a.y + e.srcOffset[1]], e.srcDir,
        [b.x + e.dstOffset[0], b.y + e.dstOffset[1]], e.dstDir);
      drawEdge(e, labels);
      reserveLabel(e);
    });
  }

  // ----------------------------------------------------- boxes never overlap
  // Boxes keep C.nodeGap between them, which leaves a corridor an arrow can be routed
  // through (a box any closer would wall in the start of its neighbours' arrows).
  function crowded(x, y, n) {
    var gap = C.nodeGap;
    for (var i = 0; i < data.nodes.length; i++) {
      var m = data.nodes[i];
      if (m === n) continue;
      if (x < m.x + m.w + gap && m.x < x + n.w + gap && y < m.y + m.h + gap && m.y < y + n.h + gap) return true;
    }
    return false;
  }

  // A box dropped too close to another goes to the nearest free place on the grid. Pushing
  // it off one neighbour could shove it into the next, and may never settle.
  function separate(n) {
    if (!crowded(n.x, n.y, n)) return;
    var cell = C.gridCell, best = null;
    for (var ring = 1; ring <= 80 && best === null; ring++) {
      var bestDistance = Infinity;
      for (var dx = -ring; dx <= ring; dx++) {
        for (var dy = -ring; dy <= ring; dy++) {
          if (Math.max(Math.abs(dx), Math.abs(dy)) !== ring) continue;
          var x = n.x + dx * cell, y = n.y + dy * cell, distance = dx * dx + dy * dy;
          if (distance < bestDistance && !crowded(x, y, n)) { bestDistance = distance; best = [x, y]; }
        }
      }
    }
    if (best) { n.x = best[0]; n.y = best[1]; }
  }

  function place(n) {
    nodeEls[n.id].attr('transform', 'translate(' + n.x + ' ' + n.y + ')');
  }

  var frame = null, pending = {};
  function scheduleRoute(id) {
    (incident[id] || []).forEach(function (eid) { pending[eid] = true; });
    if (frame !== null) return;
    frame = requestAnimationFrame(function () {
      frame = null;
      var subset = pending;
      pending = {};
      routeEdges(subset);
    });
  }

  var viewer = UmlViewer.init({
    svg: svg, vp: vp, extent: [0.2, 6], title: data.title, name: 'diagram',
    // the spec as it is now: moved boxes and the arrows routed around them
    snapshot: function () {
      var spec = JSON.parse(JSON.stringify(data));
      spec.edges.forEach(function (e, i) { e.points = edges[i].points; });
      return spec;
    },
    onReset: function () {
      data.nodes.forEach(function (n) { n.x = initial[n.id][0]; n.y = initial[n.id][1]; place(n); });
      edges.forEach(function (e) { e.points = e.initialPoints.map(function (p) { return p.slice(); }); drawEdge(e); });
      updateGroups();
    }
  });

  var drag = d3.drag()
    .on('start', function () {
      d3.select(this).raise().classed('dragging', true);
      svg.classed('dragging', true);
      viewer.hideTip();
    })
    .on('drag', function (event, n) {
      // boxes snap to the routing grid, so arrows always meet them in straight lines
      n.x = Math.round(event.x / C.gridCell) * C.gridCell;
      n.y = Math.round(event.y / C.gridCell) * C.gridCell;
      separate(n);
      place(n);
      updateGroups();
      scheduleRoute(n.id);
    })
    .on('end', function () {
      d3.select(this).classed('dragging', false);
      svg.classed('dragging', false);
      routeEdges(null);
    });

  data.nodes.forEach(function (n) { nodeEls[n.id].datum(n); });
  vp.selectAll('g.node').call(drag);

  // ----------------------------------------------------- hover and tooltips
  vp.selectAll('g.node')
    .on('mouseenter', function (event, n) {
      var near = {}; near[n.id] = true;
      edges.forEach(function (e) {
        var on = e.from === n.id || e.to === n.id;
        e.el.classed('on', on);
        if (on) { near[e.from] = true; near[e.to] = true; }
      });
      data.nodes.forEach(function (m) { nodeEls[m.id].classed('on', !!near[m.id]); });
      svg.classed('hl', true);
    })
    .on('mousemove', function (event, n) {
      if (svg.classed('dragging')) return;
      viewer.showTip(event, n.label + (n.sub ? ' (' + n.sub + ')' : '') + (n.note ? ' - ' + n.note : ''));
    })
    .on('mouseleave', function () {
      svg.classed('hl', false);
      vp.selectAll('.on').classed('on', false);
      viewer.hideTip();
    });

  document.body.setAttribute('data-ready', 'architecture');
})();
