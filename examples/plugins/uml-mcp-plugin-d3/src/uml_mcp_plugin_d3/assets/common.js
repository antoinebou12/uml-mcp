/* Behaviour shared by the D3 pages: zoom and pan, fit, theme, flow, toolbar, tooltip,
 * keyboard, and the exports (SVG, PNG, HTML).
 *
 * Text is only ever set with textContent, never as markup. Exports are built from the
 * live document, so they carry the current state (moved boxes, re-routed arrows, pinned
 * nodes, the theme) and open exactly as they were left.
 */
var UmlViewer = (function () {
  'use strict';

  var SVG_NS = 'http://www.w3.org/2000/svg';
  var hostBridge = false;

  function escapeJson(text) {
    // same escaping the server uses, so the data block can never close its own script element
    return text.replace(/</g, '\\u003c').replace(/>/g, '\\u003e').replace(/&/g, '\\u0026');
  }

  function fileName(title, fallback, ext) {
    return ((title || fallback).replace(/[^A-Za-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '') || fallback) + '.' + ext;
  }

  function download(content, type, name) {
    var blob = content instanceof Blob ? content : new Blob([content], { type: type });
    if (hostBridge) {
      var reader = new FileReader();
      reader.onload = function () {
        window.parent.postMessage({type:'uml-mcp/plugin-download', filename:name,
          mime_type:type, blob:String(reader.result).split(',')[1]}, '*');
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

  // dark when the page was told so, or when it follows the system and the system is dark
  function isDark() {
    var cl = document.documentElement.classList;
    if (cl.contains('dark')) return true;
    return cl.contains('auto') && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  }

  function setTheme(svgEl, next) {
    [document.documentElement, svgEl].forEach(function (el) {
      el.classList.remove('light', 'dark', 'auto');
      el.classList.add(next);
    });
  }

  // A copy of the diagram without the transient state (zoom, hover, drag, tooltip position).
  function cleanClone(root) {
    var clone = root.cloneNode(true);
    var viewport = clone.querySelector ? clone.querySelector('g.viewport') : null;
    if (viewport) viewport.removeAttribute('transform');
    var dots = clone.querySelector ? clone.querySelector('pattern#dots') : null;
    if (dots) dots.removeAttribute('patternTransform');
    clone.querySelectorAll('.on, .dragging, .hl, .flow').forEach(function (el) {
      el.classList.remove('on', 'dragging', 'hl', 'flow');
    });
    // inline style attributes are not allowed by the page's Content-Security-Policy
    clone.querySelectorAll('[style]').forEach(function (el) { el.removeAttribute('style'); });
    if (clone.removeAttribute) clone.removeAttribute('style');
    return clone;
  }

  // The canvas that shows everything: the drawn area, grown to take in boxes that were
  // dragged past its edge (they would be clipped, or off-screen when the file is opened).
  function canvasBox(svg, vp) {
    var content = vp.node().getBBox();
    var vb = svg.node().viewBox.baseVal;
    var pad = 40;
    var x1 = Math.min(vb.x, content.x - pad), y1 = Math.min(vb.y, content.y - pad);
    var x2 = Math.max(vb.x + vb.width, content.x + content.width + pad);
    var y2 = Math.max(vb.y + vb.height, content.y + content.height + pad);
    return [x1, y1, x2 - x1, y2 - y1];
  }

  function setCanvas(svgEl, box, fixedSize) {
    svgEl.setAttribute('viewBox', box.join(' '));
    if (fixedSize) {
      svgEl.setAttribute('width', box[2]);
      svgEl.setAttribute('height', box[3]);
    }
    ['rect.bg', 'rect.dotfill'].forEach(function (selector) {
      var rect = svgEl.querySelector(selector);
      if (rect) {
        rect.setAttribute('x', box[0]); rect.setAttribute('y', box[1]);
        rect.setAttribute('width', box[2]); rect.setAttribute('height', box[3]);
      }
    });
  }

  // A standalone SVG: the stylesheet travels inside it and the theme is the one on screen.
  function svgText(svg, box) {
    var clone = cleanClone(svg);
    setCanvas(clone, box, true);
    var css = document.getElementById('diagram-css');
    if (css) {
      var style = document.createElementNS(SVG_NS, 'style');
      var exportCss = document.getElementById('svg-export-css');
      style.textContent = exportCss ? JSON.parse(exportCss.textContent)[isDark() ? 'dark' : 'light'] : css.textContent;
      clone.insertBefore(style, clone.querySelector('defs'));
    }
    clone.classList.remove('light', 'dark', 'auto');
    clone.classList.add(isDark() ? 'dark' : 'light');
    return new XMLSerializer().serializeToString(clone);
  }

  function pngBlob(text, width, height, done) {
    var scale = Math.min(2, 8192 / Math.max(width, height));
    var img = new Image();
    img.onload = function () {
      var canvas = document.createElement('canvas');
      canvas.width = Math.max(1, Math.round(width * scale));
      canvas.height = Math.max(1, Math.round(height * scale));
      var ctx = canvas.getContext('2d');
      ctx.scale(scale, scale);
      ctx.drawImage(img, 0, 0, width, height);
      canvas.toBlob(done, 'image/png');
    };
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(text);
  }

  // The whole page as a standalone file, its data block replaced by the current state.
  function htmlText(spec, box) {
    var doc = cleanClone(document.documentElement);
    doc.querySelector('#spec').textContent = escapeJson(JSON.stringify(spec));
    doc.querySelector('body').removeAttribute('data-ready');
    var tip = doc.querySelector('#tip');
    if (tip) { tip.className = ''; tip.textContent = ''; }
    var menu = doc.querySelector('details.menu');
    if (menu) menu.removeAttribute('open');
    var flow = doc.querySelector('#flow');
    if (flow) flow.setAttribute('aria-pressed', 'false');
    setCanvas(doc.querySelector('svg'), box, false);
    return '<!doctype html>\n' + doc.outerHTML + '\n';
  }

  /* options:
   *   svg, vp        d3 selections of the <svg> and its g.viewport
   *   extent         zoom scale extent, default [0.2, 6]
   *   title, name    file names for exports ('diagram' or 'graph')
   *   snapshot()     the spec object with the current state, for "Save HTML"
   *   onReset()      put the diagram back as it was drawn
   */
  function init(o) {
    var svg = o.svg, vp = o.vp, tip = document.getElementById('tip');
    var level = document.getElementById('zlevel');
    var dots = svg.select('pattern#dots');

    function hideTip() { tip.className = ''; }
    function showTip(event, text) {
      tip.textContent = text;
      tip.className = 'show';
      tip.style.left = Math.min(event.clientX + 14, window.innerWidth - 260) + 'px';
      tip.style.top = (event.clientY + 14) + 'px';
    }

    var zoom = d3.zoom()
      .scaleExtent(o.extent || [0.2, 6])
      .filter(function (event) {
        // a drag that starts on a node moves the node, it does not pan the page
        if (event.target.closest && event.target.closest('g.node') && event.type !== 'wheel') return false;
        return (!event.ctrlKey || event.type === 'wheel') && !event.button;
      })
      .on('zoom', function (event) {
        vp.attr('transform', event.transform);
        // the dotted canvas pans and zooms with the drawing
        if (!dots.empty()) dots.attr('patternTransform', event.transform.toString());
        if (level) level.textContent = Math.round(event.transform.k * 100) + '%';
      });
    svg.call(zoom).on('dblclick.zoom', null);

    function fit() {
      var box = vp.node().getBBox();
      var vb = svg.node().viewBox.baseVal;
      if (!box.width || !box.height) return;
      var low = (o.extent || [0.2, 6])[0];
      var k = Math.min(4, Math.max(low, 0.94 * Math.min(vb.width / box.width, vb.height / box.height)));
      var t = d3.zoomIdentity
        .translate(vb.width / 2 - k * (box.x + box.width / 2), vb.height / 2 - k * (box.y + box.height / 2))
        .scale(k);
      svg.transition().duration(250).call(zoom.transform, t);
    }

    function button(id, fn) {
      var el = document.getElementById(id);
      if (el) el.addEventListener('click', fn);
    }
    function closeMenu() {
      var menu = document.querySelector('details.menu');
      if (menu) menu.removeAttribute('open');
    }

    button('zin', function () { svg.transition().duration(150).call(zoom.scaleBy, 1.3); });
    button('zout', function () { svg.transition().duration(150).call(zoom.scaleBy, 1 / 1.3); });
    button('fit', fit);
    button('reset', function () {
      if (o.onReset) o.onReset();
      svg.transition().duration(250).call(zoom.transform, d3.zoomIdentity);
    });
    button('theme', function () { setTheme(svg.node(), isDark() ? 'light' : 'dark'); });
    button('flow', function () {
      var on = !svg.classed('flow');
      svg.classed('flow', on);
      this.setAttribute('aria-pressed', String(on));
    });
    button('save', function () {
      closeMenu();
      download(svgText(svg.node(), canvasBox(svg, vp)), 'image/svg+xml', fileName(o.title, o.name, 'svg'));
    });
    button('png', function () {
      closeMenu();
      var box = canvasBox(svg, vp);
      pngBlob(svgText(svg.node(), box), box[2], box[3], function (blob) {
        if (blob) download(blob, 'image/png', fileName(o.title, o.name, 'png'));
      });
    });
    button('html', function () {
      closeMenu();
      download(htmlText(o.snapshot(), canvasBox(svg, vp)), 'text/html', fileName(o.title, o.name, 'html'));
    });
    document.addEventListener('keydown', function (event) {
      if (event.key === '+' || event.key === '=') svg.call(zoom.scaleBy, 1.3);
      else if (event.key === '-') svg.call(zoom.scaleBy, 1 / 1.3);
      else if (event.key === '0') fit();
    });

    if (window.parent !== window) {
      window.addEventListener('message', function (event) {
        if (event.source !== window.parent || !event.data) return;
        if (event.data.type === 'uml-mcp/plugin-bridge-ready') { hostBridge = true; return; }
        if (event.data.type !== 'uml-mcp/plugin-export') return;
        var id = {svg:'save', png:'png', html:'html'}[event.data.format];
        var control = id && document.getElementById(id);
        if (control) control.click();
      });
      window.parent.postMessage({type:'uml-mcp/plugin-ready', exports:['svg','png','html']}, '*');
    }
    return { zoom: zoom, fit: fit, showTip: showTip, hideTip: hideTip, button: button };
  }

  return { init: init };
})();
