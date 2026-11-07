/* Statechart simulator: runs the machine drawn above it.
 *
 * Semantics (a small subset of SCXML, close to XState): a configuration is the set of
 * active states, ancestors included. Firing an event picks, for every active atomic state,
 * the nearest state (itself or an ancestor) that handles it. A transition exits every
 * active state under its domain (the nearest compound ancestor holding source and
 * targets), runs its actions, then enters the targets with their ancestors and defaults:
 * a compound enters its initial child, a parallel state all its regions, a history state
 * what was active when its parent was last left. Guards are labels: when one event has
 * several guarded alternatives, each gets its own button and the reader picks.
 * A compound whose active child is final, or a parallel whose regions are all done, is
 * done; its onDone transition fires by itself.
 *
 * Text is only ever set with textContent, never as markup.
 */
(function () {
  'use strict';
  var root = document.documentElement;
  var original = '<!doctype html>\n' + root.outerHTML + '\n';
  if (window.self !== window.top) root.setAttribute('data-embedded', '1');
  var M = JSON.parse(document.getElementById('machine').textContent);
  var S = M.states, T = M.transitions;
  var main = document.querySelector('main'), stage = document.getElementById('stage');
  var svg = stage.querySelector('svg');
  var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ---------------------------------------------------------------- the machine
  var order = {};
  Object.keys(S).forEach(function (id, i) { order[id] = i; });
  function parentOf(id) { return S[id].parent; }
  function isDesc(id, anc) { return anc === '' ? id !== '' : id.indexOf(anc + '.') === 0; }
  function byDoc(a, b) { return order[a] - order[b]; }
  function byDepth(a, b) { return (S[a].depth - S[b].depth) || byDoc(a, b); }
  function leaves(set) {
    return Object.keys(S).filter(function (id) {
      return set.has(id) && !S[id].children.some(function (c) { return set.has(c); });
    }).sort(byDoc);
  }

  var active = new Set(), hist = {}, doneSeen = new Set(), log = [], undo = [], finished = false;

  function domainOf(t) {
    if (!t.targets.length) return null;
    var src = t.source;
    if (t.targets.every(function (x) { return isDesc(x, src); }) && S[src].type === 'compound') return src;
    var p = parentOf(src);
    while (p !== null) {
      if ((p === '' || S[p].type === 'compound') && t.targets.every(function (x) { return isDesc(x, p); })) return p;
      p = parentOf(p);
    }
    return '';
  }
  function exitSet(t) {
    var d = domainOf(t);
    if (d === null) return [];
    return Array.from(active).filter(function (s) { return isDesc(s, d); });
  }
  // the targets and their ancestors up to the domain, then default descendants
  function entrySet(targets, domain) {
    var set = new Set();
    function up(id) { for (var c = id; c !== null && c !== domain && !set.has(c); c = parentOf(c)) set.add(c); }
    targets.forEach(function (tg) {
      var st = S[tg];
      if (st.type !== 'history') { up(tg); return; }
      var p = st.parent, rec = hist[p];
      if (rec) {
        (st.history === 'deep' ? rec.deep : rec.shallow).forEach(up);
      } else {
        var dflt = st.historyTarget || S[p].initial;
        if (dflt) up(dflt);
      }
    });
    var queue = Array.from(set);
    while (queue.length) {
      var id = queue.shift(), st = S[id];
      if (st.type === 'compound' && !st.children.some(function (c) { return set.has(c); }) && st.initial) {
        set.add(st.initial); queue.push(st.initial);
      } else if (st.type === 'parallel') {
        st.children.forEach(function (c) { if (!set.has(c)) { set.add(c); queue.push(c); } });
      }
    }
    return Array.from(set).sort(byDepth);
  }

  function microstep(tids, step) {
    var ts = tids.map(function (id) { return T[id]; });
    var exits = new Set();
    ts.forEach(function (t) { exitSet(t).forEach(function (s) { exits.add(s); }); });
    var exitList = Array.from(exits).sort(function (a, b) { return -byDepth(a, b); });
    exitList.forEach(function (s) {
      if (S[s].children.length) {
        hist[s] = {
          shallow: S[s].children.filter(function (c) { return active.has(c); }),
          deep: leaves(active).filter(function (l) { return isDesc(l, s); }),
        };
      }
    });
    exitList.forEach(function (s) {
      S[s].exit.forEach(function (a) { step.actions.push('exit ' + S[s].name + ': ' + a); });
      active.delete(s); doneSeen.delete(s);
      step.exited.push(s);
    });
    ts.forEach(function (t) { t.actions.forEach(function (a) { step.actions.push(a); }); });
    ts.forEach(function (t) {
      if (!t.targets.length) return;
      entrySet(t.targets, domainOf(t)).forEach(function (s) {
        if (active.has(s)) return;
        active.add(s);
        step.entered.push(s);
        S[s].entry.forEach(function (a) { step.actions.push('entry ' + S[s].name + ': ' + a); });
      });
    });
    step.tids = step.tids.concat(tids);
  }

  function isDone(id) {
    var st = S[id];
    if (!active.has(id)) return false;
    if (st.type === 'final') return true;
    if (st.type === 'compound' || (id === '' && st.type !== 'parallel')) {
      return st.children.some(function (c) { return active.has(c) && S[c].type === 'final'; });
    }
    if (st.type === 'parallel') return st.children.every(isDone);
    return false;
  }

  // onDone transitions fire by themselves, possibly in a chain
  function settle(step) {
    for (var guard = 0; guard < 24; guard++) {
      var fire = [];
      Object.keys(S).sort(function (a, b) { return -byDepth(a, b); }).forEach(function (id) {
        if (S[id].type === 'final' || S[id].type === 'atomic' || S[id].type === 'history') return;
        if (doneSeen.has(id) || !isDone(id)) return;
        doneSeen.add(id);
        step.done.push(id);
        if (S[id].done) fire.push(S[id].done);
      });
      if (!fire.length) break;
      microstep(pickConflictFree(fire), step);
    }
    finished = isDone('');
  }

  function pickConflictFree(tids) {
    var taken = new Set(), out = [];
    tids.forEach(function (id) {
      var ex = exitSet(T[id]);
      if (ex.some(function (s) { return taken.has(s); })) return;
      ex.forEach(function (s) { taken.add(s); });
      out.push(id);
    });
    return out;
  }

  /* Choices for the current configuration: [{event, tids, label, guard}].
   * One button per event, or one per guarded alternative when there are several. */
  function choices() {
    if (finished) return [];
    var groups = {}, events = [];
    leaves(active).forEach(function (leaf) {
      var claimed = {};
      for (var s = leaf; s !== null; s = parentOf(s)) {
        var mine = {};
        S[s].transitions.forEach(function (tid) {
          var t = T[tid];
          if (t.kind === 'done' || claimed[t.event]) return;
          (mine[t.event] = mine[t.event] || []).push(tid);
        });
        Object.keys(mine).forEach(function (ev) {
          claimed[ev] = true;
          if (!groups[ev]) { groups[ev] = []; events.push(ev); }
          var key = mine[ev].join(',');
          if (!groups[ev].some(function (g) { return g.join(',') === key; })) groups[ev].push(mine[ev]);
        });
      }
    });
    var out = [];
    events.forEach(function (ev) {
      var gs = groups[ev];
      var multi = gs.filter(function (g) { return g.length > 1; })[0];
      var base = gs.filter(function (g) { return g !== multi; }).map(function (g) { return g[0]; });
      if (!multi) { out.push({ event: ev, tids: pickConflictFree(base), label: ev, guard: '' }); return; }
      multi.forEach(function (tid) {
        var g = T[tid].guard || 'else';
        out.push({ event: ev, tids: pickConflictFree([tid].concat(base)), label: ev + ' [' + g + ']', guard: g });
      });
    });
    return out;
  }
  function enabledTids() {
    var set = new Set();
    choices().forEach(function (c) { c.tids.forEach(function (t) { set.add(t); }); });
    return set;
  }

  function snapshot() {
    return { active: Array.from(active), hist: JSON.parse(JSON.stringify(hist)), done: Array.from(doneSeen), log: log.length, finished: finished };
  }
  function restore(s) {
    active = new Set(s.active); hist = s.hist; doneSeen = new Set(s.done); log.length = s.log; finished = s.finished;
  }

  function fire(tids, label) {
    if (!tids.length) return false;
    undo.push(snapshot());
    var before = leaves(active);
    var step = { event: label, tids: [], exited: [], entered: [], actions: [], done: [], from: before };
    microstep(tids, step);
    settle(step);
    step.to = leaves(active);
    log.push(step);
    render(step);
    return true;
  }

  function start() {
    active = new Set(['']); hist = {}; doneSeen = new Set(); log = []; undo = []; finished = false;
    var step = { event: 'start', tids: [], exited: [], entered: [], actions: [], done: [], from: [] };
    entrySet(S[''].type === 'parallel' ? S[''].children : [S[''].initial], '').forEach(function (s) {
      active.add(s); step.entered.push(s);
      S[s].entry.forEach(function (a) { step.actions.push('entry ' + S[s].name + ': ' + a); });
    });
    S[''].entry.forEach(function (a) { step.actions.unshift(a); });
    settle(step);
    step.to = leaves(active);
    log.push(step);
  }

  // ---------------------------------------------------------------- the page
  var stateEls = {}, trEls = {}, labelEls = {};
  svg.querySelectorAll('.sc-state').forEach(function (g) { stateEls[g.getAttribute('data-id')] = g; });
  svg.querySelectorAll('.sc-tr').forEach(function (g) { (trEls[g.getAttribute('data-tid')] = trEls[g.getAttribute('data-tid')] || []).push(g); });
  svg.querySelectorAll('.sc-label').forEach(function (g) { (labelEls[g.getAttribute('data-tid')] = labelEls[g.getAttribute('data-tid')] || []).push(g); });
  var eventsBox = document.getElementById('events'), activeBox = document.getElementById('active');
  var logList = document.getElementById('log'), status = document.getElementById('status');
  var undoBtn = document.getElementById('undo'), resetBtn = document.getElementById('reset');
  var card = document.getElementById('card'), selected = null;

  function el(tag, text, cls) {
    var e = document.createElement(tag);
    if (text !== undefined && text !== null) e.textContent = text;
    if (cls) e.className = cls;
    return e;
  }
  function pathName(id) {
    var names = [];
    for (var c = id; c; c = parentOf(c)) names.unshift(S[c].name);
    return names.join(' › ');
  }
  function say(text) { status.textContent = text; }

  function animate(tids) {
    tids.forEach(function (tid) {
      (trEls[tid] || []).concat(labelEls[tid] || []).forEach(function (g) {
        g.classList.remove('fire'); void g.getBoundingClientRect(); g.classList.add('fire');
        setTimeout(function () { g.classList.remove('fire'); }, 900);
      });
      if (reduced) return;
      (trEls[tid] || []).forEach(function (g) {
        var path = g.querySelector('path'), len = path.getTotalLength();
        var dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        dot.setAttribute('r', '5'); dot.setAttribute('class', 'sc-token');
        svg.appendChild(dot);
        var t0 = performance.now();
        (function frame(now) {
          var k = Math.min(1, (now - t0) / 520), p = path.getPointAtLength(len * k);
          dot.setAttribute('cx', p.x); dot.setAttribute('cy', p.y);
          if (k < 1) requestAnimationFrame(frame); else dot.remove();
        })(t0);
      });
    });
  }

  function render(step) {
    Object.keys(stateEls).forEach(function (id) { stateEls[id].classList.toggle('on', active.has(id)); });
    var can = enabledTids();
    Object.keys(trEls).forEach(function (tid) { trEls[tid].forEach(function (g) { g.classList.toggle('can', can.has(tid)); }); });
    Object.keys(labelEls).forEach(function (tid) {
      labelEls[tid].forEach(function (g) {
        g.classList.toggle('can', can.has(tid));
        g.setAttribute('role', 'button');
        g.setAttribute('aria-disabled', String(!can.has(tid)));
      });
    });
    // event buttons
    eventsBox.textContent = '';
    var list = choices();
    list.forEach(function (c) {
      var b = el('button', c.event, 'ev');
      b.type = 'button';
      b.setAttribute('data-event', c.event);
      if (c.guard) { b.setAttribute('data-guard', c.guard); b.append(el('span', ' [' + c.guard + ']', 'g')); }
      b.title = c.tids.map(function (t) { return T[t].label + ' → ' + (T[t].targets.map(pathName).join(', ') || '(stays)'); }).join('\n');
      b.addEventListener('click', function () { fire(c.tids, c.label); });
      eventsBox.append(b);
    });
    if (!list.length) eventsBox.append(el('span', finished ? 'Finished: the machine reached a final state.' : 'No events are enabled here.', 'none'));
    // active chips
    activeBox.textContent = '';
    leaves(active).forEach(function (id) {
      var b = el('button', pathName(id), 'chip');
      b.type = 'button'; b.setAttribute('data-id', id);
      b.addEventListener('click', function () { select(id); });
      activeBox.append(b);
    });
    // log
    logList.textContent = '';
    log.forEach(function (s, i) {
      var li = el('li');
      li.append(el('b', s.event), el('span', ' → ' + s.to.map(pathName).join(', '), 'to'));
      if (s.actions.length) li.append(el('div', s.actions.join(' · '), 'acts'));
      if (s.done.length) li.append(el('div', 'done: ' + s.done.map(function (d) { return d ? pathName(d) : M.title; }).join(', '), 'acts'));
      if (i === log.length - 1) li.className = 'last';
      logList.append(li);
    });
    logList.scrollTop = logList.scrollHeight;
    document.getElementById('stepcount').textContent = String(log.length - 1);
    undoBtn.disabled = !undo.length;
    resetBtn.disabled = log.length <= 1;
    if (step) {
      animate(step.tids);
      say(step.event + ' → ' + step.to.map(pathName).join(', ') + (finished ? ' (finished)' : ''));
    }
    if (selected !== null) select(selected, true);
  }

  // ---------------------------------------------------------------- detail card
  function select(id, keep) {
    var st = S[id];
    if (!st) return;
    selected = id;
    Object.keys(stateEls).forEach(function (k) { stateEls[k].classList.toggle('sel', k === id); });
    var kinds = { atomic: 'State', compound: 'Compound state', parallel: 'Parallel state', final: 'Final state', history: (st.history === 'deep' ? 'Deep' : 'Shallow') + ' history' };
    var parentType = st.parent !== null && S[st.parent] ? S[st.parent].type : '';
    var kind = parentType === 'parallel' && st.parent !== '' ? 'Region' : kinds[st.type];
    var close = el('button', '×', 'close');
    close.type = 'button'; close.setAttribute('aria-label', 'Close');
    close.addEventListener('click', function () { deselect(); });
    card.replaceChildren(close, el('div', kind, 'kicker'), el('h2', st.name));
    if (st.parent) card.append(el('div', pathName(id), 'sub'));
    var chips = el('div', null, 'chips');
    chips.append(el('span', active.has(id) ? 'active' : 'inactive', 'chip ' + (active.has(id) ? 'on' : '')));
    if (st.unreachable) chips.append(el('span', 'unreachable', 'chip warn'));
    card.append(chips);
    if (st.description) card.append(el('p', st.description, 'desc'));
    function section(title, items) {
      if (!items.length) return;
      card.append(el('div', title, 'h'));
      var ul = el('ul');
      items.forEach(function (x) { ul.append(x); });
      card.append(ul);
    }
    section('Entry', st.entry.map(function (a) { return el('li', a, 'act'); }));
    section('Exit', st.exit.map(function (a) { return el('li', a, 'act'); }));
    var can = enabledTids();
    section('Events', st.transitions.map(function (tid) {
      var t = T[tid], li = el('li');
      var b = el('button', null, can.has(tid) ? 'out can' : 'out');
      b.type = 'button';
      b.append(el('b', t.kind === 'done' ? 'onDone' : t.event));
      if (t.guard) b.append(el('span', ' [' + t.guard + ']', 'g'));
      b.append(el('span', ' → ' + (t.targets.map(function (x) { return S[x].name; }).join(', ') || 'stays'), 'to'));
      if (t.actions.length) b.append(el('span', ' / ' + t.actions.join(', '), 'a'));
      b.title = can.has(tid) ? 'Fire this transition' : 'Show the target state';
      b.addEventListener('click', function () {
        if (can.has(tid)) fire([tid], t.event + (t.guard ? ' [' + t.guard + ']' : ''));
        else if (t.targets.length) select(t.targets[0]);
      });
      li.append(b);
      return li;
    }));
    card.hidden = false;
    if (!keep) refit();
  }
  function deselect() {
    selected = null;
    card.hidden = true;
    Object.keys(stateEls).forEach(function (k) { stateEls[k].classList.remove('sel'); });
    refit();
  }

  // ---------------------------------------------------------------- pan, zoom, fit
  var vb = svg.viewBox.baseVal, W = vb.width, H = vb.height;
  var k = 1, x = 0, y = 0, drag = null, moved = 0, fitted = true;
  var readout = document.getElementById('zoomval');
  function apply() { stage.style.transform = 'translate(' + x + 'px,' + y + 'px) scale(' + k + ')'; readout.textContent = Math.round(k * 100) + '%'; }
  function fit() {
    var r = main.getBoundingClientRect();
    var inset = (!card.hidden && r.width >= 760) ? 300 : 0;
    var w = Math.max(120, r.width - inset), h = Math.max(80, r.height);
    k = Math.min(w / W, h / H, 1.5) * 0.97;
    x = (w - W * k) / 2; y = (h - H * k) / 2; fitted = true; apply();
  }
  function refit() { if (fitted) fit(); }
  function zoom(f, px, py) {
    var r = main.getBoundingClientRect(), cx = px === undefined ? r.width / 2 : px, cy = py === undefined ? r.height / 2 : py;
    var nk = Math.max(0.1, Math.min(6, k * f));
    x = cx - ((cx - x) / k) * nk; y = cy - ((cy - y) / k) * nk; k = nk; fitted = false; apply();
  }
  main.addEventListener('pointerdown', function (e) {
    if (card.contains(e.target)) return;
    main.setPointerCapture(e.pointerId); main.classList.add('drag'); drag = [e.clientX, e.clientY]; moved = 0;
  });
  main.addEventListener('pointermove', function (e) {
    if (!drag) return;
    var dx = e.clientX - drag[0], dy = e.clientY - drag[1];
    moved += Math.abs(dx) + Math.abs(dy);
    if (moved > 5) fitted = false;
    x += dx; y += dy; drag = [e.clientX, e.clientY]; apply();
  });
  main.addEventListener('pointerup', function (e) {
    var was = drag; drag = null; main.classList.remove('drag');
    if (!was || moved > 5) return;
    var hits = document.elementsFromPoint(e.clientX, e.clientY);
    var label = hits.map(function (n) { return n.closest && n.closest('.sc-label'); }).filter(Boolean)[0];
    if (label) { clickLabel(label.getAttribute('data-tid')); return; }
    var hit = hits.map(function (n) { return n.closest && n.closest('.sc-state'); }).filter(Boolean)[0];
    if (hit) select(hit.getAttribute('data-id')); else if (selected !== null) deselect();
  });
  main.addEventListener('pointercancel', function () { drag = null; main.classList.remove('drag'); });
  main.addEventListener('wheel', function (e) {
    e.preventDefault();
    var r = main.getBoundingClientRect();
    zoom(Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top);
  }, { passive: false });

  function clickLabel(tid) {
    var t = T[tid];
    if (!t) return;
    if (enabledTids().has(tid)) {
      // fire just this alternative, alongside whatever the same event does in other regions
      var c = choices().filter(function (c) { return c.tids.indexOf(tid) >= 0; })[0];
      fire(c ? c.tids : [tid], c ? c.label : t.event);
    } else {
      say(t.event + ' is not enabled in ' + leaves(active).map(pathName).join(', '));
      select(t.source || (t.targets[0] || ''));
    }
  }

  // ---------------------------------------------------------------- toolbar
  undoBtn.addEventListener('click', function () {
    if (!undo.length) return;
    restore(undo.pop()); render(); say('Undone: back to ' + leaves(active).map(pathName).join(', '));
  });
  resetBtn.addEventListener('click', function () { start(); render(); say('Reset to the initial state'); });
  document.getElementById('fit').addEventListener('click', fit);
  document.getElementById('zin').addEventListener('click', function () { zoom(1.2); });
  document.getElementById('zout').addEventListener('click', function () { zoom(1 / 1.2); });
  var themeBtn = document.getElementById('theme');
  function isDark() { return root.getAttribute('data-theme') === 'dark'; }
  function label() { themeBtn.textContent = isDark() ? 'Light' : 'Dark'; }
  themeBtn.addEventListener('click', function () { root.setAttribute('data-theme', isDark() ? 'light' : 'dark'); label(); });
  window.addEventListener('keydown', function (e) {
    if (e.target && /INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) return;
    if (e.key === 'Escape') deselect();
    else if ((e.ctrlKey || e.metaKey) && e.key === 'z') { e.preventDefault(); undoBtn.click(); }
  });
  window.addEventListener('resize', refit);

  // ---------------------------------------------------------------- exports
  var hostBridge = false;
  function fileName(ext) { return ((M.title || 'state-machine').replace(/[^A-Za-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '') || 'state-machine') + '.' + ext; }
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
  function svgText() {
    var clone = svg.cloneNode(true);
    clone.querySelectorAll('.sc-token').forEach(function (n) { n.remove(); });
    clone.querySelectorAll('.sel,.fire').forEach(function (n) { n.classList.remove('sel', 'fire'); });
    clone.querySelectorAll('[style]').forEach(function (n) { n.removeAttribute('style'); });
    var style = document.createElementNS('http://www.w3.org/2000/svg', 'style');
    style.textContent = JSON.parse(document.getElementById('export-css').textContent)[isDark() ? 'dark' : 'light'];
    clone.insertBefore(style, clone.firstChild);
    clone.setAttribute('class', 'sc-svg ' + (isDark() ? 'dark' : 'light'));
    return new XMLSerializer().serializeToString(clone);
  }
  function closeMenu() { var m = document.querySelector('details.menu'); if (m) m.removeAttribute('open'); }
  document.getElementById('save-svg').addEventListener('click', function () { closeMenu(); download(svgText(), 'image/svg+xml', fileName('svg')); });
  document.getElementById('save-png').addEventListener('click', function () {
    closeMenu();
    var scale = Math.min(2, 8192 / Math.max(W, H)), img = new Image();
    img.onload = function () {
      var canvas = document.createElement('canvas');
      canvas.width = Math.round(W * scale); canvas.height = Math.round(H * scale);
      var ctx = canvas.getContext('2d'); ctx.scale(scale, scale); ctx.drawImage(img, 0, 0, W, H);
      canvas.toBlob(function (blob) { if (blob) download(blob, 'image/png', fileName('png')); }, 'image/png');
    };
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svgText());
  });
  document.getElementById('save-html').addEventListener('click', function () { closeMenu(); download(original, 'text/html', fileName('html')); });
  if (window.parent !== window) {
    window.addEventListener('message', function (event) {
      if (event.source !== window.parent || !event.data) return;
      if (event.data.type === 'uml-mcp/plugin-bridge-ready') { hostBridge = true; return; }
      if (event.data.type !== 'uml-mcp/plugin-export') return;
      var id = { svg: 'save-svg', png: 'save-png', html: 'save-html' }[event.data.format];
      var control = id && document.getElementById(id);
      if (control) control.click();
    });
    window.parent.postMessage({ type: 'uml-mcp/plugin-ready', exports: ['svg', 'png', 'html'] }, '*');
  }

  // ---------------------------------------------------------------- go
  if (root.getAttribute('data-auto') === '1') {
    root.setAttribute('data-theme', window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  }
  var logBox = document.getElementById('logbox');
  if (window.innerWidth < 760) logBox.removeAttribute('open');
  logBox.addEventListener('toggle', refit);
  label();
  start();
  render();
  say('Ready: ' + leaves(active).map(pathName).join(', '));
  fit();
  if (M.warnings.length) document.getElementById('warn').textContent = '⚠ ' + M.warnings.length;

  window.__statechart = {
    fire: function (event, guard) {
      var c = choices().filter(function (c) { return c.event === event && (guard === undefined || c.guard === guard); })[0];
      return c ? fire(c.tids, c.label) : false;
    },
    clickLabel: clickLabel,
    active: function () { return Array.from(active).filter(function (s) { return s !== ''; }).sort(byDoc); },
    leaves: function () { return leaves(active); },
    enabled: function () { return choices().map(function (c) { return c.label; }); },
    finished: function () { return finished; },
    select: select,
    undo: function () { undoBtn.click(); },
    reset: function () { resetBtn.click(); },
    log: function () { return log.map(function (s) { return { event: s.event, to: s.to, actions: s.actions, done: s.done }; }); },
    svgText: svgText,
  };
})();
