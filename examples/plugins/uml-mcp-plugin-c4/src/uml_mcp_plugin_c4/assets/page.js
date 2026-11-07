/* The C4 drill-down page. Every view is already drawn (one <svg class="view"> each); this
 * script switches between them with a short zoom transition, pans and zooms the visible one
 * by its viewBox, fills the detail card (text only, never markup) and exports the current
 * level as SVG, PNG or a static HTML page. */
(function () {
  'use strict';
  var root = document.documentElement;
  var data = JSON.parse(document.getElementById('model').textContent);
  var main = document.querySelector('main');
  var card = document.getElementById('details');
  var crumbs = document.getElementById('crumbs');
  var status = document.getElementById('status');
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var embedded = window.self !== window.top;
  var hostBridge = false;
  if (embedded) root.setAttribute('data-embedded', '');
  if (root.dataset.auto === '1') {
    var dark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    root.className = dark ? 'dark' : 'light';
  }

  // every view is drawn flowing top-down (TB) and, unless the source fixed one, left-right
  // (LR); the page shows whichever is larger once fitted into the frame
  var layouts = {};
  document.querySelectorAll('svg.view').forEach(function (svg) {
    (layouts[svg.dataset.view] = layouts[svg.dataset.view] || {})[svg.dataset.dir] = svg;
    var vb = svg.viewBox.baseVal;
    svg._full = [vb.x, vb.y, vb.width, vb.height];
  });
  var current = null, selected = null;
  function bestDir(key) {
    var r = main.getBoundingClientRect(), best = null, scale = -1;
    Object.keys(layouts[key]).forEach(function (d) {
      var f = layouts[key][d]._full, s = Math.min(r.width / f[2], r.height / f[3]);
      if (s > scale * 1.04) { scale = s; best = d; }
    });
    return best;
  }
  // finish any transition: only the current drawing stays on screen
  function settle() {
    document.querySelectorAll('svg.view.on').forEach(function (svg) {
      if (svg.getAnimations) svg.getAnimations().forEach(function (a) { a.cancel(); });
      if (!current || svg !== cur()) svg.classList.remove('on');
    });
  }
  function svgFor(key) { return layouts[key] && layouts[key][bestDir(key)]; }
  function cur() { return layouts[current][cur.dir]; }

  // ------------------------------------------------------------------ pan and zoom
  function setBox(svg, box) { svg._box = box; svg.setAttribute('viewBox', box.map(function (v) { return v.toFixed(1); }).join(' ')); }
  function fit(svg) { setBox(svg || cur(), (svg || cur())._full.slice()); }
  function toSvg(svg, cx, cy) {
    var pt = svg.createSVGPoint(); pt.x = cx; pt.y = cy;
    return pt.matrixTransform(svg.getScreenCTM().inverse());
  }
  function zoomBy(f, cx, cy) {
    var svg = cur(), b = svg._box || svg._full, r = main.getBoundingClientRect();
    var p = toSvg(svg, cx === undefined ? r.left + r.width / 2 : cx, cy === undefined ? r.top + r.height / 2 : cy);
    var w = b[2] / f, h = b[3] / f;
    var full = svg._full;
    if (w > full[2] * 4 || w < full[2] / 12) return;
    setBox(svg, [p.x - (p.x - b[0]) / f, p.y - (p.y - b[1]) / f, w, h]);
  }
  var drag = null, moved = 0;
  main.addEventListener('pointerdown', function (e) {
    if (card.contains(e.target) || e.button !== 0) return;
    drag = [e.clientX, e.clientY]; moved = 0;
  });
  main.addEventListener('pointermove', function (e) {
    if (!drag) return;
    var dx = e.clientX - drag[0], dy = e.clientY - drag[1];
    moved += Math.abs(dx) + Math.abs(dy);
    if (moved < 5) return;
    if (!main.classList.contains('drag')) { main.classList.add('drag'); main.setPointerCapture(e.pointerId); }
    var svg = cur(), b = svg._box || svg._full, k = 1 / svg.getScreenCTM().a;
    setBox(svg, [b[0] - dx * k, b[1] - dy * k, b[2], b[3]]);
    drag = [e.clientX, e.clientY];
  });
  function endDrag() { drag = null; main.classList.remove('drag'); }
  main.addEventListener('pointerup', endDrag);
  main.addEventListener('pointercancel', endDrag);
  main.addEventListener('wheel', function (e) { e.preventDefault(); zoomBy(Math.exp(-e.deltaY * 0.0015), e.clientX, e.clientY); }, { passive: false });

  // ------------------------------------------------------------------ views
  function el(tag, text, cls) {
    var n = document.createElement(tag);
    if (text !== undefined && text !== null) n.textContent = text;
    if (cls) n.className = cls;
    return n;
  }
  function renderCrumbs() {
    crumbs.textContent = '';
    var list = data.views[current].crumbs;
    list.forEach(function (c, i) {
      if (i) crumbs.appendChild(el('span', '›', 'sep'));
      var b = el('button', c[1]); b.type = 'button';
      if (i === list.length - 1) b.setAttribute('aria-current', 'page');
      else b.addEventListener('click', function () { go(c[0]); });
      crumbs.appendChild(b);
    });
    document.getElementById('up').disabled = list.length < 2;
  }
  function centreOf(svg, id) {
    var g = id && svg.querySelector('[data-id="' + CSS.escape(id) + '"]');
    var r = g ? g.getBoundingClientRect() : main.getBoundingClientRect();
    var m = main.getBoundingClientRect();
    return (r.left + r.width / 2 - m.left) + 'px ' + (r.top + r.height / 2 - m.top) + 'px';
  }
  /* Switch to view ``key``. Going down zooms into the box that was opened; going up zooms
   * out of it, so the reader always sees where they are. */
  function go(key, opts) {
    opts = opts || {};
    if (!layouts[key]) return false;
    settle();
    var prev = current, oldSvg = prev && cur(), newSvg = svgFor(key);
    if (key === prev) { if (opts.select) select(opts.select); return true; }
    var down = prev && data.views[key].crumbs.length > data.views[prev].crumbs.length;
    var pivot = down ? data.views[key].focus : (prev ? data.views[prev].focus : null);
    clearSelection();
    hideCard();
    current = key;
    cur.dir = newSvg.dataset.dir;
    newSvg.classList.add('on');
    fit(newSvg);
    if (oldSvg && !reduce && newSvg.animate) {
      var origin = down ? centreOf(oldSvg, pivot) : centreOf(newSvg, pivot);
      oldSvg.style.transformOrigin = origin; newSvg.style.transformOrigin = origin;
      var t = { duration: 380, easing: 'cubic-bezier(.2,.7,.2,1)' };
      oldSvg.animate(down ? [{ transform: 'scale(1)', opacity: 1 }, { transform: 'scale(2.2)', opacity: 0 }]
        : [{ transform: 'scale(1)', opacity: 1 }, { transform: 'scale(.45)', opacity: 0 }], t)
        .onfinish = function () { if (current !== prev) oldSvg.classList.remove('on'); };
      newSvg.animate(down ? [{ transform: 'scale(.45)', opacity: 0 }, { transform: 'scale(1)', opacity: 1 }]
        : [{ transform: 'scale(2.2)', opacity: 0 }, { transform: 'scale(1)', opacity: 1 }], t);
    } else if (oldSvg) {
      oldSvg.classList.remove('on');
    }
    renderCrumbs();
    status.textContent = data.views[key].title;
    if (opts.select) select(opts.select);
    else if (!down && pivot && prev) select(pivot, { quiet: true });
    return true;
  }
  function up() {
    var list = data.views[current].crumbs;
    if (list.length > 1) go(list[list.length - 2][0]);
  }

  // ------------------------------------------------------------------ selection and card
  function clearSelection() {
    selected = null;
    if (!current) return;
    cur().querySelectorAll('.sel,.dim,.on').forEach(function (n) {
      if (n.classList.contains('view')) return;
      n.classList.remove('sel', 'dim', 'on');
    });
  }
  function hideCard() { card.hidden = true; }
  function nameOf(id) { return (data.elements[id] || {}).name || id; }
  function relText(r) { return [r.label, r.technology ? '[' + r.technology + ']' : ''].filter(Boolean).join(' '); }
  function within(id, ancestor) {
    for (var c = id; c; c = (data.elements[c] || {}).parent) if (c === ancestor) return true;
    return false;
  }
  /* Highlight ``id`` and its lines in the current view; ``quiet`` skips the card. */
  function select(id, opts) {
    opts = opts || {};
    var svg = cur();
    clearSelection();
    var target = svg.querySelector('.el[data-id="' + CSS.escape(id) + '"], .boundary[data-id="' + CSS.escape(id) + '"]');
    if (!target) return false;
    selected = id;
    target.classList.add('sel');
    var keep = new Set([id]);
    svg.querySelectorAll('.rel').forEach(function (r) {
      var hit = r.dataset.from === id || r.dataset.to === id;
      r.classList.toggle('on', hit);
      if (hit) { keep.add(r.dataset.from); keep.add(r.dataset.to); }
    });
    if (!target.classList.contains('boundary')) {
      svg.querySelectorAll('.el').forEach(function (n) { n.classList.toggle('dim', !keep.has(n.dataset.id)); });
      svg.querySelectorAll('.rel').forEach(function (r) { r.classList.toggle('dim', !r.classList.contains('on')); });
    }
    if (!opts.quiet) showElement(id);
    return true;
  }
  function openCard(kind, title, sub) {
    card.textContent = '';
    var close = el('button', '×', 'close'); close.type = 'button'; close.setAttribute('aria-label', 'Close');
    close.addEventListener('click', function () { hideCard(); clearSelection(); });
    card.append(close, el('div', kind, 'kind'), el('h2', title));
    if (sub) card.appendChild(el('p', sub, 'sub'));
    card.hidden = false;
  }
  function linkList(heading, items) {
    if (!items.length) return;
    card.appendChild(el('div', heading + ' · ' + items.length, 'h'));
    var box = el('div', null, 'links');
    items.forEach(function (item) {
      var b = el('button', item.label); b.type = 'button';
      if (item.via) b.appendChild(el('span', '  ' + item.via, 'via'));
      b.addEventListener('click', function (e) { e.stopPropagation(); reveal(item.id); });
      box.appendChild(b);
    });
    card.appendChild(box);
  }
  function showElement(id) {
    var item = data.elements[id];
    openCard(item.kicker, item.name, item.type);
    if (item.description) card.appendChild(el('p', item.description));
    var actions = el('div', null, 'actions');
    if (item.drill && item.drill !== current) {
      var open = el('button', item.level === 'system' ? 'Open containers ⤵' : 'Open components ⤵', 'primary');
      open.type = 'button'; open.addEventListener('click', function () { go(item.drill); });
      actions.appendChild(open);
    }
    if (item.docs) {
      var docs = el('button', 'Open documentation ↗'); docs.type = 'button'; docs.id = 'd-docs';
      docs.addEventListener('click', function () { openLink(item.docs); });
      actions.appendChild(docs);
    }
    if (actions.childNodes.length) card.appendChild(actions);
    var out = [], inn = [];
    data.relations.forEach(function (r) {
      var from = within(r.from, id), to = within(r.to, id);
      if (from && !to) out.push({ id: r.to, label: '→ ' + nameOf(r.to), via: relText(r) });
      else if (to && !from) inn.push({ id: r.from, label: '← ' + nameOf(r.from), via: relText(r) });
    });
    linkList('Uses', out);
    linkList('Used by', inn);
  }
  function showEdge(edgeId) {
    var e = data.views[current].edges[edgeId];
    if (!e) return;
    clearSelection();
    var svg = cur();
    svg.querySelectorAll('.rel').forEach(function (r) {
      r.classList.toggle('on', r.dataset.id === edgeId);
      r.classList.toggle('dim', r.dataset.id !== edgeId);
    });
    svg.querySelectorAll('.el').forEach(function (n) { n.classList.toggle('dim', n.dataset.id !== e.from && n.dataset.id !== e.to); });
    openCard('Relationship' + (e.members.length > 1 ? ' · ' + e.members.length + ' merged' : ''), nameOf(e.from) + ' → ' + nameOf(e.to));
    linkList('Underlying relations', e.members.map(function (i) {
      var r = data.relations[i];
      return { id: r.to, label: nameOf(r.from) + ' → ' + nameOf(r.to), via: relText(r) };
    }));
  }
  /* Show an element wherever it is drawn as a box, switching views when needed. */
  function reveal(id) {
    var item = data.elements[id];
    if (!item) return;
    if (cur().querySelector('.el[data-id="' + CSS.escape(id) + '"]')) { select(id); return; }
    go(item.home, { select: id });
  }

  function openLink(url) {
    if (!/^https:\/\/[^\s"'<>]+$/.test(url || '')) return;
    if (embedded) {
      window.parent.postMessage({ type: 'uml-mcp/open-link', url: url }, '*');
      if (hostBridge) return;
    }
    window.open(url, '_blank', 'noopener,noreferrer');
  }

  // ------------------------------------------------------------------ clicks and keys
  function activate(target, e) {
    var g = target.closest && target.closest('.el, .boundary, .rel');
    if (!g || !cur().contains(g)) { hideCard(); clearSelection(); return; }
    if (g.classList.contains('rel')) { showEdge(g.dataset.id); return; }
    var id = g.dataset.id;
    if (g.classList.contains('el') && g.dataset.drill && !(e && (e.shiftKey || e.altKey))) { go(g.dataset.drill); return; }
    select(id);
  }
  main.addEventListener('click', function (e) {
    if (moved >= 5) { moved = 0; return; }
    if (card.contains(e.target)) return;
    activate(e.target, e);
  });
  document.addEventListener('keydown', function (e) {
    var t = e.target;
    if ((e.key === 'Enter' || e.key === ' ') && t.closest && t.closest('svg.view')) { e.preventDefault(); activate(t, e); return; }
    if (t.tagName === 'BUTTON' || t.tagName === 'SUMMARY') return;
    if (e.key === 'Escape' || e.key === 'Backspace') {
      if (!card.hidden) { hideCard(); clearSelection(); } else up();
    } else if (e.key === '+' || e.key === '=') zoomBy(1.25);
    else if (e.key === '-') zoomBy(1 / 1.25);
    else if (e.key === '0') fit();
  });

  // ------------------------------------------------------------------ toolbar
  function on(id, fn) { document.getElementById(id).addEventListener('click', fn); }
  on('up', up);
  on('fit', function () { fit(); });
  on('zin', function () { zoomBy(1.25); });
  on('zout', function () { zoomBy(1 / 1.25); });
  on('theme', function () { root.className = root.className === 'dark' ? 'light' : 'dark'; });

  // ------------------------------------------------------------------ export
  function fileName(ext) {
    var base = (data.title + '-' + data.views[current].title).replace(/[^A-Za-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '');
    return (base || 'c4') + '.' + ext;
  }
  function svgText() {
    var theme = root.className === 'dark' ? 'dark' : 'light';
    var clone = cur().cloneNode(true);
    clone.querySelectorAll('.badge, .hit').forEach(function (n) { n.remove(); });
    clone.querySelectorAll('.sel, .dim, .on').forEach(function (n) { n.classList.remove('sel', 'dim', 'on'); });
    ['tabindex', 'role'].forEach(function (a) { clone.querySelectorAll('[' + a + ']').forEach(function (n) { n.removeAttribute(a); }); });
    var full = cur()._full;
    clone.setAttribute('viewBox', full.join(' '));
    clone.setAttribute('width', full[2]); clone.setAttribute('height', full[3]);
    clone.setAttribute('class', 'c4 ' + theme);
    clone.removeAttribute('style');
    var style = document.createElementNS('http://www.w3.org/2000/svg', 'style');
    style.textContent = data.css[theme];
    clone.insertBefore(style, clone.firstChild);
    return new XMLSerializer().serializeToString(clone);
  }
  function download(content, type, name) {
    var blob = content instanceof Blob ? content : new Blob([content], { type: type });
    if (hostBridge) {
      var reader = new FileReader();
      reader.onload = function () {
        window.parent.postMessage({ type: 'uml-mcp/plugin-download', filename: name, mime_type: type, blob: String(reader.result).split(',')[1] }, '*');
      };
      reader.readAsDataURL(blob);
      return;
    }
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
  }
  function closeMenu() { document.querySelector('details.menu').removeAttribute('open'); }
  var exporters = {
    svg: function () { download(svgText(), 'image/svg+xml', fileName('svg')); },
    png: function () {
      var text = svgText(), full = cur()._full;
      var scale = Math.min(2, 8192 / Math.max(full[2], full[3]));
      var img = new Image();
      img.onload = function () {
        var canvas = document.createElement('canvas');
        canvas.width = Math.round(full[2] * scale); canvas.height = Math.round(full[3] * scale);
        var ctx = canvas.getContext('2d'); ctx.scale(scale, scale); ctx.drawImage(img, 0, 0, full[2], full[3]);
        canvas.toBlob(function (blob) { if (blob) download(blob, 'image/png', fileName('png')); }, 'image/png');
      };
      img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(text);
    },
    html: function () {
      var theme = root.className === 'dark' ? 'dark' : 'light';
      var title = data.views[current].title.replace(/[<>&"]/g, function (c) { return { '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' }[c]; });
      var page = '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">' +
        '<meta name="viewport" content="width=device-width,initial-scale=1">' +
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; img-src data:">' +
        '<title>' + title + '</title><style>body{margin:0;background:' + data.background[theme] +
        '}svg{display:block;max-width:100%;height:auto;margin:auto}</style></head><body>' + svgText() + '</body></html>\n';
      download(page, 'text/html', fileName('html'));
    },
  };
  Object.keys(exporters).forEach(function (fmt) {
    on('export-' + fmt, function () { closeMenu(); exporters[fmt](); });
  });
  if (embedded) {
    window.addEventListener('message', function (event) {
      if (event.source !== window.parent || !event.data) return;
      if (event.data.type === 'uml-mcp/plugin-bridge-ready') { hostBridge = true; return; }
      if (event.data.type === 'uml-mcp/plugin-export' && exporters[event.data.format]) exporters[event.data.format]();
    });
    window.parent.postMessage({ type: 'uml-mcp/plugin-ready', exports: ['svg', 'png', 'html'] }, '*');
  }
  // the viewBox keeps a drawing fitted; a frame that turns from portrait to landscape (or
  // back) swaps in the other flow when it shows the view larger
  window.addEventListener('resize', function () {
    if (!current) return;
    var next = bestDir(current);
    if (next === cur.dir) return;
    var keep = selected;
    cur.dir = next;
    settle();
    cur().classList.add('on');
    fit(cur());
    if (keep) select(keep, { quiet: card.hidden });
  });

  go(data.start);
  if (data.select) select(data.select, { quiet: true });
  window.__c4 = {
    go: go, up: up, select: select, reveal: reveal, fit: fit, svgText: svgText,
    get view() { return current; },
    get direction() { return cur.dir; },
    get selected() { return selected; },
    box: function () { return (cur()._box || cur()._full).slice(); },
  };
})();
