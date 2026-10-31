/* Rectangular collisions and container constraints for d3-force.
 * Positions are card centres; bounds describe the allowed card top-left corner.
 */
var UmlBounds = (function () {
  'use strict';

  function constrain(node, bounds, cell) {
    var x = node.x - node.w / 2, y = node.y - node.h / 2;
    if (cell) { x = Math.round(x / cell) * cell; y = Math.round(y / cell) * cell; }
    x = Math.max(bounds[0], Math.min(bounds[2], x));
    y = Math.max(bounds[1], Math.min(bounds[3], y));
    if (node.x !== x + node.w / 2) node.vx = 0;
    if (node.y !== y + node.h / 2) node.vy = 0;
    node.x = x + node.w / 2; node.y = y + node.h / 2;
    if (node.fx != null) node.fx = node.x;
    if (node.fy != null) node.fy = node.y;
  }

  function collide(gap) {
    var nodes = [];
    function force() {
      for (var i = 0; i < nodes.length; i++) {
        for (var j = i + 1; j < nodes.length; j++) {
          var a = nodes[i], b = nodes[j];
          var dx = b.x + b.vx - a.x - a.vx, dy = b.y + b.vy - a.y - a.vy;
          var ox = (a.w + b.w) / 2 + gap - Math.abs(dx);
          var oy = (a.h + b.h) / 2 + gap - Math.abs(dy);
          if (ox <= 0 || oy <= 0) continue;
          var aFree = a.fx == null, bFree = b.fx == null;
          var divisor = Number(aFree) + Number(bFree);
          if (!divisor) continue;
          var axis = ox < oy ? 'vx' : 'vy';
          var delta = ((axis === 'vx' ? dx : dy) < 0 ? -1 : 1) * Math.min(ox, oy) * 0.7 / divisor;
          if (aFree) a[axis] -= delta;
          if (bFree) b[axis] += delta;
        }
      }
    }
    force.initialize = function (value) { nodes = value; };
    return force;
  }

  return { constrain: constrain, collide: collide };
})();
