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
  var svg = d3.select('#diagram').attr('role', 'group').attr('aria-label', 'Interactive architecture diagram');
  var vp = svg.select('g.viewport');

  var nodes = Object.create(null), initial = Object.create(null);
  data.nodes.forEach(function (n) { nodes[n.id] = n; initial[n.id] = [n.x, n.y]; });
  var nodeEls = Object.create(null);
  vp.selectAll('g.node').each(function () { nodeEls[this.getAttribute('data-id')] = d3.select(this); });
  var groupEls = Object.create(null);
  vp.selectAll('g.group').each(function () { groupEls[this.getAttribute('data-id')] = d3.select(this); });

  var edges = data.edges.map(function (e) {
    var el = vp.select('g.edge[data-id="' + e.id + '"]');
    return {
      id: e.id, from: e.from, to: e.to, srcOffset: e.srcOffset, dstOffset: e.dstOffset,
      srcDir: e.srcDir, dstDir: e.dstDir, points: e.points, labelWidth: e.labelWidth,
      initialPoints: e.points.map(function (p) { return p.slice(); }),
      initialLabel: el.select('g.edge-label').empty() ? null : el.select('g.edge-label').attr('transform'),
      el: el, path: el.select('path'), label: el.select('g.edge-label')
    };
  });
  var incident = Object.create(null);
  edges.forEach(function (e) {
    (incident[e.from] = incident[e.from] || []).push(e.id);
    (incident[e.to] = incident[e.to] || []).push(e.id);
  });

  // ---------------------------------------------------------------- groups
  var children = Object.create(null), members = Object.create(null), rootGroups = [];
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
    var rects = Object.create(null);
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
    updateOverlay();
  }

  // Physics is opt-in: the deterministic initial layout stays still until requested.
  // Container rectangles are frozen while it runs; they cannot chase escaping nodes.
  var physics = null, physicsEnabled = false, physicsNodes = [], lastRoute = 0;

  function boundsFor(n) {
    var vb = svg.node().viewBox.baseVal;
    var r = n.group && groupEls[n.group].select('rect.group-box');
    var x = r ? +r.attr('x') : vb.x, y = r ? +r.attr('y') : vb.y;
    var w = r ? +r.attr('width') : vb.width, h = r ? +r.attr('height') : vb.height;
    var cell = C.gridCell;
    return [Math.ceil((x + 10) / cell) * cell, Math.ceil((y + C.groupHeader + 10) / cell) * cell,
      Math.floor((x + w - n.w - 10) / cell) * cell, Math.floor((y + h - n.h - 10) / cell) * cell];
  }

  function paintPhysics(final) {
    physicsNodes.forEach(function (p) {
      UmlBounds.constrain(p, p.bounds, final ? C.gridCell : 0);
      p.node.x = p.x - p.w / 2; p.node.y = p.y - p.h / 2;
      place(p.node);
    });
    if (final || Date.now() - lastRoute > 160) { routeEdges(null); lastRoute = Date.now(); }
  }

  function settlePhysics() {
    if (!physics) return;
    physics.stop();
    paintPhysics(true);
    // Dense containers may have no alternative grid packing. Keep their last valid
    // layout rather than exporting overlapping cards or trapping an arrow endpoint.
    if (data.nodes.some(function (n) { return crowded(n.x, n.y, n); })) {
      physicsNodes.forEach(function (p) {
        p.x = p.startX; p.y = p.startY; p.vx = 0; p.vy = 0;
      });
      paintPhysics(true);
    }
    document.body.setAttribute('data-physics', physicsEnabled ? 'settled' : 'off');
  }

  function stopPhysics() {
    physicsEnabled = false;
    settlePhysics();
    physics = null;
    document.getElementById('physics').setAttribute('aria-pressed', 'false');
    document.body.setAttribute('data-physics', 'off');
  }

  function startPhysics() {
    physicsEnabled = true;
    physicsNodes = data.nodes.map(function (n) {
      return {id:n.id, node:n, w:n.w, h:n.h, x:n.x+n.w/2, y:n.y+n.h/2,
        startX:n.x+n.w/2, startY:n.y+n.h/2, bounds:boundsFor(n)};
    });
    var links = edges.filter(function (e) { return nodes[e.from].group === nodes[e.to].group; })
      .map(function (e) { return {source:e.from, target:e.to}; });
    physics = d3.forceSimulation(physicsNodes).stop()
      .randomSource(d3.randomLcg(0.42))
      .force('x', d3.forceX(function (p) { return p.startX; }).strength(0.035))
      .force('y', d3.forceY(function (p) { return p.startY; }).strength(0.035))
      .force('links', d3.forceLink(links).id(function (p) { return p.id; }).distance(180).strength(0.015))
      .force('cards', UmlBounds.collide(C.nodeGap))
      .velocityDecay(0.55).alpha(0.5).alphaMin(0.02).alphaDecay(0.065)
      .on('tick', function () { paintPhysics(false); })
      .on('end', settlePhysics);
    document.getElementById('physics').setAttribute('aria-pressed', 'true');
    document.body.setAttribute('data-physics', 'running');
    runPhysics();
  }

  function runPhysics() {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      for (var i = 0; i < 60; i++) { physics.tick(); physicsNodes.forEach(function (p) { UmlBounds.constrain(p, p.bounds, 0); }); }
      settlePhysics();
    } else physics.restart();
  }

  function movingParticle(n) {
    return physicsNodes.find(function (p) { return p.id === n.id; });
  }

  // Persistent click/keyboard selection, with an overlay underneath the real edges.
  var selected = null;
  var overlay = vp.append('g').attr('class', 'connection-overlay').attr('aria-hidden', 'true').lower();
  function selectedIds() {
    var ids = Object.create(null);
    function collect(id) {
      (members[id] || []).forEach(function (n) { ids[n.id] = true; });
      (children[id] || []).forEach(collect);
    }
    if (selected) {
      if (selected.kind === 'node') ids[selected.id] = true;
      else collect(selected.id);
    }
    return ids;
  }
  function updateOverlay() {
    if (!overlay) return;
    var ids = selectedIds();
    overlay.selectAll('path').data(edges.filter(function (e) { return ids[e.from] || ids[e.to]; }), function (e) { return e.id; })
      .join('path').attr('d', function (e) { return e.path.attr('d'); });
  }
  function highlight(ids) {
    var near = Object.assign(Object.create(null), ids);
    edges.forEach(function (e) {
      var on = !!(ids[e.from] || ids[e.to]);
      e.el.classed('on', on);
      if (on) { near[e.from] = true; near[e.to] = true; }
    });
    data.nodes.forEach(function (n) { nodeEls[n.id].classed('on', !!near[n.id]); });
    svg.classed('hl', Object.keys(ids).length > 0);
  }
  function select(kind, id, toggle) {
    selected = toggle && selected && selected.kind === kind && selected.id === id ? null : {kind:kind, id:id};
    vp.selectAll('g.node,g.group').classed('selected', false).attr('aria-pressed', 'false');
    if (selected) (kind === 'node' ? nodeEls[id] : groupEls[id]).classed('selected', true).attr('aria-pressed', 'true');
    highlight(selectedIds()); updateOverlay();
    document.getElementById('focus').disabled = !selected;
    var label = selected ? (kind === 'node' ? nodes[id].label : groupEls[id].select('text').text()) : '';
    document.getElementById('selection-status').textContent = selected ? label + ': ' + overlay.selectAll('path').size() + ' connections selected' : 'Selection cleared';
  }
  function clearSelection() {
    selected = null;
    vp.selectAll('g.node,g.group').classed('selected', false).attr('aria-pressed', 'false');
    highlight({}); updateOverlay();
    document.getElementById('focus').disabled = true;
    document.getElementById('selection-status').textContent = 'Selection cleared';
  }
  function focusSelection() {
    if (!selected) return;
    var element = selected.kind === 'node' ? nodeEls[selected.id] : groupEls[selected.id];
    var box = element.node().getBBox();
    // A node's bounding box is local to its translate; groups use canvas coordinates.
    var n = selected.kind === 'node' && nodes[selected.id];
    viewer.fitTo({x:box.x+(n ? n.x : 0)-24, y:box.y+(n ? n.y : 0)-24, width:box.width+48, height:box.height+48});
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
    beforeExport: settlePhysics,
    onReset: function () {
      stopPhysics(); clearSelection();
      data.nodes.forEach(function (n) { n.x = initial[n.id][0]; n.y = initial[n.id][1]; place(n); });
      edges.forEach(function (e) {
        e.points = e.initialPoints.map(function (p) { return p.slice(); }); drawEdge(e);
        if (!e.label.empty()) e.label.attr('transform', e.initialLabel);
      });
      updateGroups();
    }
  });
  viewer.button('physics', function () { if (physicsEnabled) stopPhysics(); else startPhysics(); });
  viewer.button('focus', focusSelection);
  document.body.setAttribute('data-physics', 'off');
  clearSelection();

  var dragMoved = false;
  var drag = d3.drag().clickDistance(4)
    .on('start', function (event, n) {
      dragMoved = false;
      d3.select(this).classed('dragging', true);
      svg.classed('dragging', true);
      viewer.hideTip();
      if (physicsEnabled) {
        var p = movingParticle(n); p.fx = p.x; p.fy = p.y;
      }
    })
    .on('drag', function (event, n) {
      if (!dragMoved) {
        dragMoved = true; d3.select(this).raise();
        if (physicsEnabled) {
          if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) physics.alphaTarget(0.15).restart();
          document.body.setAttribute('data-physics', 'running');
        }
      }
      // boxes snap to the routing grid, so arrows always meet them in straight lines
      n.x = Math.round(event.x / C.gridCell) * C.gridCell;
      n.y = Math.round(event.y / C.gridCell) * C.gridCell;
      if (physicsEnabled) {
        var p = movingParticle(n);
        p.x = n.x + n.w / 2; p.y = n.y + n.h / 2;
        UmlBounds.constrain(p, p.bounds, C.gridCell);
        p.fx = p.x; p.fy = p.y;
        n.x = p.x - n.w / 2; n.y = p.y - n.h / 2;
      } else separate(n);
      place(n);
      if (!physicsEnabled) updateGroups();
      scheduleRoute(n.id);
    })
    .on('end', function (event, n) {
      d3.select(this).classed('dragging', false);
      svg.classed('dragging', false);
      if (physicsEnabled) {
        var p = movingParticle(n); p.fx = null; p.fy = null;
        if (dragMoved) { physics.alphaTarget(0).alpha(0.4); runPhysics(); }
      }
      routeEdges(null);
    });

  data.nodes.forEach(function (n) { nodeEls[n.id].datum(n); });
  vp.selectAll('g.node').call(drag);

  function bindSelection(selection, kind) {
    selection.attr('tabindex', '0').attr('role', 'button').attr('aria-pressed', 'false')
      .attr('aria-label', function () { return 'Select ' + kind + ': ' + (kind === 'node' ? nodes[this.getAttribute('data-id')].label : d3.select(this).select('text').text()); })
      .on('click.selection', function (event) {
        if (event.defaultPrevented) return;
        event.stopPropagation(); select(kind, this.getAttribute('data-id'), true);
      })
      .on('dblclick.selection', function (event) {
        event.preventDefault(); event.stopPropagation(); select(kind, this.getAttribute('data-id'), false); focusSelection();
      })
      .on('keydown.selection', function (event) {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        event.preventDefault(); select(kind, this.getAttribute('data-id'), true);
      });
  }
  bindSelection(vp.selectAll('g.node'), 'node');
  bindSelection(vp.selectAll('g.group'), 'container');
  svg.on('click.selection', clearSelection);
  document.addEventListener('keydown', function (event) { if (event.key === 'Escape') clearSelection(); });

  // ----------------------------------------------------- hover and tooltips
  vp.selectAll('g.node')
    .on('mouseenter', function (event, n) {
      if (selected) return;
      var near = Object.create(null); near[n.id] = true;
      highlight(near);
    })
    .on('mousemove', function (event, n) {
      if (svg.classed('dragging')) return;
      viewer.showTip(event, n.label + (n.sub ? ' (' + n.sub + ')' : '') + (n.note ? ' - ' + n.note : ''));
    })
    .on('mouseleave', function () {
      highlight(selectedIds());
      viewer.hideTip();
    });

  document.body.setAttribute('data-ready', 'architecture');
})();
