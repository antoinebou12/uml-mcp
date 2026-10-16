/* Interactive force-directed graph.
 *
 * The SVG is drawn by the server at the positions its own layout settled on. This binds
 * D3 to it: the real d3-force simulation (starting from those positions, so nothing
 * jumps), and draggable, pinnable nodes. Zoom, pan, tooltips and the exports come from
 * UmlViewer. Text is only ever set with textContent, never as markup.
 */
(function () {
  'use strict';

  var data = JSON.parse(document.getElementById('spec').textContent);
  var svg = d3.select('#graph');
  var vp = svg.select('g.viewport');

  var nodes = data.nodes.map(function (n) {
    var copy = Object.assign({}, n);
    copy.ix = n.x; copy.iy = n.y;
    // circles keep apart, and so do their labels
    copy.cr = Math.max(n.r + 8, n.label.length * 2.8);
    if (n.fixed) { copy.fx = n.x; copy.fy = n.y; }  // pinned when the page was exported
    return copy;
  });
  var byId = {};
  nodes.forEach(function (n) { byId[n.id] = n; });
  var links = data.links.map(function (l) {
    return { source: l.source, target: l.target, value: l.value, label: l.label };
  });

  var nodeSel = vp.selectAll('g.node');
  nodeSel.each(function () { d3.select(this).datum(byId[this.getAttribute('data-id')]); });
  nodeSel.classed('pinned', function (d) { return d.fx !== undefined && d.fx !== null; });
  // the opaque mask under each node keeps links from showing through its tinted fill
  var circles = [nodeSel.select('circle.f-mask'), nodeSel.select('circle.f-node')];
  var captions = nodeSel.select('text');
  var linkSel = vp.selectAll('line.f-link');
  var labelNodes = vp.selectAll('g.link-labels text').nodes();
  var labelLinks = links.filter(function (l) { return l.label; });

  var cx = d3.mean(nodes, function (n) { return n.x; });
  var cy = d3.mean(nodes, function (n) { return n.y; });

  var sim = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(function (d) { return d.id; }).distance(data.distance))
    .force('charge', d3.forceManyBody().strength(data.charge))
    .force('center', d3.forceCenter(cx, cy))
    .force('collide', d3.forceCollide(function (d) { return d.cr; }))
    .alpha(0.3)
    .alphaDecay(0.04)
    .on('tick', ticked);

  function ticked() {
    circles.forEach(function (c) {
      c.attr('cx', function (d) { return d.x; }).attr('cy', function (d) { return d.y; });
    });
    captions.attr('x', function (d) { return d.x; }).attr('y', function (d) { return d.y + d.r + 13; });
    linkSel.each(function (d, i) {
      var l = links[i], a = l.source, b = l.target;
      if (typeof a !== 'object') return;
      var dx = b.x - a.x, dy = b.y - a.y, dist = Math.hypot(dx, dy) || 1;
      var trim = b.r + (data.directed ? 3 : 0);
      d3.select(this)
        .attr('x1', a.x).attr('y1', a.y)
        .attr('x2', b.x - dx / dist * trim).attr('y2', b.y - dy / dist * trim);
    });
    labelNodes.forEach(function (el, i) {
      var l = labelLinks[i];
      if (!l || typeof l.source !== 'object') return;
      el.setAttribute('x', (l.source.x + l.target.x) / 2);
      el.setAttribute('y', (l.source.y + l.target.y) / 2 - 4);
    });
  }

  var paused = false;
  var viewer = UmlViewer.init({
    svg: svg, vp: vp, extent: [0.1, 8], title: data.title, name: 'graph',
    // the spec as it is now: where every node is, and which ones are pinned
    snapshot: function () {
      var spec = JSON.parse(JSON.stringify(data));
      spec.nodes.forEach(function (n) {
        var live = byId[n.id];
        n.x = Math.round(live.x * 10) / 10;
        n.y = Math.round(live.y * 10) / 10;
        n.fixed = live.fx !== undefined && live.fx !== null;
      });
      return spec;
    },
    onReset: function () {
      nodes.forEach(function (n) { n.x = n.ix; n.y = n.iy; n.vx = 0; n.vy = 0; n.fx = null; n.fy = null; });
      nodeSel.classed('pinned', false);
      sim.alpha(0.5).restart();
    }
  });

  // --------------------------------------------------------- move and pin
  nodeSel.call(d3.drag()
    .on('start', function (event, d) {
      if (!event.active) sim.alphaTarget(0.25).restart();
      d.fx = d.x; d.fy = d.y;
      d3.select(this).classed('dragging', true);
      viewer.hideTip();
    })
    .on('drag', function (event, d) { d.fx = event.x; d.fy = event.y; })
    .on('end', function (event, d) {
      if (!event.active) sim.alphaTarget(0);
      d3.select(this).classed('dragging', false).classed('pinned', true);
    }));
  nodeSel.on('dblclick', function (event, d) {
    d.fx = null; d.fy = null;
    d3.select(this).classed('pinned', false);
    sim.alpha(0.3).restart();
    event.stopPropagation();
  });

  // ------------------------------------------------------ hover and tooltips
  nodeSel
    .on('mouseenter', function (event, n) {
      var near = {}; near[n.id] = true;
      linkSel.each(function (d, i) {
        var l = links[i], a = l.source.id || l.source, b = l.target.id || l.target;
        var on = a === n.id || b === n.id;
        d3.select(this).classed('on', on);
        if (on) { near[a] = true; near[b] = true; }
      });
      nodeSel.classed('on', function (d) { return !!near[d.id]; });
      svg.classed('hl', true);
    })
    .on('mousemove', function (event, n) {
      if (event.buttons) return;
      viewer.showTip(event, n.label + (n.group ? ' [' + n.group + ']' : '') + (n.note ? ' - ' + n.note : ''));
    })
    .on('mouseleave', function () {
      svg.classed('hl', false);
      vp.selectAll('.on').classed('on', false);
      viewer.hideTip();
    });

  viewer.button('pause', function () {
    paused = !paused;
    if (paused) sim.stop(); else sim.alpha(0.3).restart();
    this.textContent = paused ? 'Resume' : 'Pause';
  });

  document.body.setAttribute('data-ready', 'force');
})();
