// Before/after review. Data: assets/review/review.json (export_review.gd).
const $ = id => document.getElementById(id);
const SVG = 'http://www.w3.org/2000/svg';
const ASSETS = './assets/';
const PROMPT_SERIES = {'v0.1.0': 'var(--series-1)', 'v0.2.0': 'var(--series-2)'};
const pct = v => `${Math.round(v * 100)}%`;
const median = values => { const s = [...values].sort((a, b) => a - b); if (!s.length) return NaN; const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };

function el(tag, attrs = {}, parent, text) {
  const node = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (text !== undefined) node.textContent = text;
  parent?.append(node);
  return node;
}
function html(tag, attrs = {}, parent, text) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (text !== undefined) node.textContent = text;
  parent?.append(node);
  return node;
}

// Tooltip: values lead, labels follow; line keys; same content on focus.
const tip = $('tooltip');
function showTip(event, title, rows, notes = []) {
  tip.replaceChildren();
  html('div', {class: 't-title'}, tip, title);
  for (const row of rows) {
    const line = html('div', {class: 't-row'}, tip);
    if (row.color) html('span', {class: 't-key', style: `background:${row.color}`}, line);
    html('b', {}, line, row.value);
    html('span', {}, line, row.label);
  }
  if (notes.length) { const list = html('ul', {}, tip); notes.forEach(n => html('li', {}, list, n)); }
  tip.hidden = false;
  const box = event.target.getBoundingClientRect?.() || {left: 0, top: 0, width: 0};
  const x = event.clientX ?? box.left + box.width / 2, y = event.clientY ?? box.top;
  tip.style.left = `${Math.min(window.innerWidth - tip.offsetWidth - 8, x + 14)}px`;
  tip.style.top = `${Math.max(8, y - tip.offsetHeight - 10)}px`;
}
const hideTip = () => { tip.hidden = true; };
function hoverable(node, content) {
  node.setAttribute('tabindex', '0');
  node.addEventListener('pointermove', e => showTip(e, ...content()));
  node.addEventListener('focus', e => showTip(e, ...content()));
  node.addEventListener('pointerleave', hideTip);
  node.addEventListener('blur', hideTip);
}

function barPath(x0, x1, y, h, r = 4) {
  if (x1 - x0 < r) return `M${x0} ${y}H${x1}V${y + h}H${x0}Z`;
  return `M${x0} ${y}H${x1 - r}Q${x1} ${y} ${x1} ${y + r}V${y + h - r}Q${x1} ${y + h} ${x1 - r} ${y + h}H${x0}Z`;
}

function statusBadge(parent, pass) {
  const s = html('span', {class: `status ${pass ? 'pass' : 'fail'}`}, parent);
  html('i', {'aria-hidden': 'true'}, s, pass ? '✓' : '✕');
  s.append(pass ? 'Pass' : 'Fail');
  return s;
}

function table(container, head, rows) {
  const t = html('table', {}, container);
  const tr = html('tr', {}, html('thead', {}, t));
  head.forEach(([label, num]) => html('th', num ? {class: 'num', scope: 'col'} : {scope: 'col'}, tr, label));
  const body = html('tbody', {}, t);
  for (const row of rows) {
    const r = html('tr', {}, body);
    row.forEach((cell, i) => {
      const td = html('td', head[i][1] ? {class: 'num'} : {}, r);
      if (cell instanceof Node) td.append(cell); else td.textContent = cell;
    });
  }
}

function tile(label, value, from, detail, pass) {
  const t = html('div', {class: 'tile'}, $('kpis'));
  html('div', {class: 'label'}, t, label);
  const v = html('div', {class: 'value'}, t);
  if (from !== null) { html('span', {class: 'from'}, v, `${from} → `); }
  v.append(value);
  const d = html('div', {class: 'detail'}, t);
  if (pass !== undefined) { statusBadge(d, pass); d.append(' '); }
  d.append(detail);
}

// Dumbbell: before → after per drawing, native as a reference tick, log x.
function dumbbell(rows) {
  const W = 760, L = 150, R = 30, T = 26, rowH = 34, H = T + rows.length * rowH + 8;
  const lo = Math.log10(10), hi = Math.log10(3000);
  const x = v => L + (Math.log10(Math.max(10, v)) - lo) / (hi - lo) * (W - L - R);
  const svg = el('svg', {viewBox: `0 0 ${W} ${H}`, style: `max-width:${W}px`, role: 'img', 'aria-label': 'Colors per drawing before and after palette cleanup'}, $('chart-colors'));
  for (const t of [10, 20, 50, 100, 200, 500, 1000, 2000]) {
    el('line', {class: 'grid', x1: x(t), x2: x(t), y1: T - 6, y2: H - 8}, svg);
    el('text', {x: x(t), y: T - 12, 'text-anchor': 'middle'}, svg, t.toLocaleString());
  }
  rows.forEach((row, i) => {
    const cy = T + i * rowH + rowH / 2;
    el('text', {class: 'label', x: L - 12, y: cy + 4, 'text-anchor': 'end'}, svg, row.label);
    el('line', {x1: x(row.after), x2: x(row.before), y1: cy, y2: cy, stroke: 'var(--axis)', 'stroke-width': 2}, svg);
    el('line', {x1: x(row.native), x2: x(row.native), y1: cy - 8, y2: cy + 8, stroke: 'var(--text-muted)', 'stroke-width': 2}, svg);
    el('circle', {cx: x(row.before), cy, r: 5, fill: 'var(--before)', stroke: 'var(--surface-1)', 'stroke-width': 2}, svg);
    el('circle', {cx: x(row.after), cy, r: 5, fill: 'var(--after)', stroke: 'var(--surface-1)', 'stroke-width': 2}, svg);
    if (i === 0) {
      el('text', {class: 'value', x: x(row.before) + 10, y: cy + 4}, svg, `${row.before.toLocaleString()} before`);
      el('text', {class: 'value', x: x(row.after) + 10, y: cy - 8}, svg, `${row.after} after`);
    }
    const hit = el('rect', {class: 'hit', x: 0, y: cy - rowH / 2, width: W, height: rowH}, svg);
    hoverable(hit, () => [row.label, [
      {value: row.before.toLocaleString(), label: 'before · colors', color: 'var(--before)'},
      {value: String(row.after), label: 'after · colors', color: 'var(--after)'},
      {value: String(row.native), label: 'native RO drawing', color: 'var(--text-muted)'},
      {value: `${row.fringeBefore} → ${row.fringeAfter}`, label: 'magenta specks'}]]);
  });
}

// Horizontal bars in % of native with the passing band shaded.
function percentBars(container, rows, band, label) {
  const W = 520, L = 110, R = 92, T = 22, rowH = 30, H = T + rows.length * rowH + 6;
  const max = Math.max(1.3, ...rows.map(r => r.value + 0.1));
  const x = v => L + v / max * (W - L - R);
  const svg = el('svg', {viewBox: `0 0 ${W} ${H}`, style: `max-width:${W}px`, role: 'img', 'aria-label': label}, container);
  el('rect', {class: 'band', x: x(band[0]), y: T - 4, width: x(Math.min(max, band[1])) - x(band[0]), height: H - T}, svg);
  for (const t of [0, 0.25, 0.5, 0.75, 1, 1.25].filter(t => t <= max)) {
    el('line', {class: t === 1 ? 'axis' : 'grid', x1: x(t), x2: x(t), y1: T - 4, y2: H - 2}, svg);
    el('text', {x: x(t), y: T - 9, 'text-anchor': 'middle'}, svg, pct(t));
  }
  el('line', {class: 'axis', x1: L, x2: L, y1: T - 4, y2: H - 2}, svg);
  rows.forEach((row, i) => {
    const y = T + i * rowH + (rowH - 16) / 2;
    el('text', {class: 'label', x: L - 10, y: y + 12, 'text-anchor': 'end'}, svg, row.label);
    if (row.value < 0) { el('text', {x: L + 6, y: y + 12}, svg, 'not measurable'); return; }
    el('path', {d: barPath(L, x(row.value), y, 16), fill: row.color}, svg);
    el('text', {class: 'value', x: x(row.value) + 6, y: y + 12}, svg, pct(row.value));
    const ok = row.value >= band[0] && row.value <= band[1];
    const g = el('g', {transform: `translate(${W - R + 14} ${y + 8})`}, svg);
    el('circle', {r: 7, fill: ok ? 'var(--good)' : 'var(--critical)'}, g);
    el('text', {'text-anchor': 'middle', y: 3.5, style: 'fill:#fff;font-size:9px'}, g, ok ? '✓' : '✕');
    el('text', {x: 12, y: 4, class: 'value'}, g, ok ? 'in band' : 'outside');
    const hit = el('rect', {class: 'hit', x: 0, y: y - 7, width: W, height: rowH}, svg);
    hoverable(hit, () => [row.label, [{value: pct(row.value), label: 'of native', color: row.color}], row.notes || []]);
  });
}

function sprite(parent, src, scale, alt) {
  const img = html('img', {src: ASSETS + src, alt}, parent);
  img.addEventListener('load', () => { img.width = img.naturalWidth * scale; img.height = img.naturalHeight * scale; });
  return img;
}

function render(data) {
  const body = data.body, head = data.head, cands = data.headCandidates;
  // KPIs
  const beforeColors = median(body.map(b => b.before.colors)), afterColors = median(body.map(b => b.after.colors)), nativeColors = median(body.map(b => b.native.colors));
  const specksBefore = body.reduce((s, b) => s + b.before.fringe, 0) + head.before.fringe, specksAfter = body.reduce((s, b) => s + b.after.fringe, 0) + head.after.fringe;
  const bodyPass = body.filter(b => b.contract.pass).length;
  const first = cands.find(c => c.prompt === 'v0.1.0'), next = cands.filter(c => c.prompt === 'v0.2.0');
  tile('Colors per body drawing (median)', String(Math.round(afterColors)), Math.round(beforeColors).toLocaleString(), `native RO drawings: ${Math.round(nativeColors)} · palette: ${data.palette.colors}`);
  tile('Magenta specks', String(specksAfter), String(specksBefore), 'pink pixels across 6 body drawings + head');
  tile('Body size check', `${bodyPass} / ${body.length}`, null, 'drawings inside 90–110% of native area', bodyPass === body.length);
  tile('Head · prompt v0.1.0', `${pct(first.contract.areaRatio)} · ${pct(first.contract.faceRatio)}`, null, 'area · face vs native', first.contract.pass);
  tile('Head · prompt v0.2.0', next.length ? `${next.filter(c => c.contract.pass).length} / ${next.length} pass` : 'Not generated yet', null, next.length ? `median face ${pct(median(next.map(c => c.contract.faceRatio)))}` : 'candidates appear here automatically');

  // 1. Colors
  const legend = $('legend-colors');
  for (const [cls, color, text] of [['key-dot', 'var(--before)', 'Before · threshold import'], ['key-dot', 'var(--after)', 'After · style palette']]) {
    const s = html('span', {}, legend); html('i', {class: cls, style: `background:${color}`}, s); s.append(text);
  }
  const t = html('span', {}, legend); html('i', {class: 'key-tick'}, t); t.append('Native RO drawing');
  const colorRows = body.map(b => ({label: `Body ${b.slot} · ${b.role}`, before: b.before.colors, after: b.after.colors, native: b.native.colors, fringeBefore: b.before.fringe, fringeAfter: b.after.fringe}));
  colorRows.push({label: 'Head 1', before: head.before.colors, after: head.after.colors, native: head.native.colors, fringeBefore: head.before.fringe, fringeAfter: head.after.fringe});
  dumbbell(colorRows);
  table($('table-colors'), [['Drawing'], ['Native colors', 1], ['Before colors', 1], ['After colors', 1], ['Specks before', 1], ['Specks after', 1]],
    colorRows.map(r => [r.label, r.native, r.before.toLocaleString(), r.after, r.fringeBefore, r.fringeAfter]));
  for (const b of body) {
    const f = html('figure', {}, $('strip-body'));
    const row = html('div', {class: 'row'}, f);
    for (const [key, name] of [['native', 'Native'], ['before', 'Before'], ['after', 'After']]) {
      const col = html('div', {}, row); sprite(col, b.images[key], 2, `${name} body ${b.slot}`); html('div', {class: 'tag'}, col, name);
    }
    html('figcaption', {}, f, `Body ${b.slot} · ${b.role}`);
  }
  { const f = html('figure', {}, $('strip-body')); const row = html('div', {class: 'row'}, f);
    for (const [key, name] of [['native', 'Native'], ['before', 'Before'], ['after', 'After']]) { const col = html('div', {}, row); sprite(col, head.images[key], 3, `${name} head`); html('div', {class: 'tag'}, col, name); }
    html('figcaption', {}, f, 'Head 1'); }

  // 2. Heads
  const hl = $('legend-heads');
  for (const [prompt, color] of Object.entries(PROMPT_SERIES)) { const s = html('span', {}, hl); html('i', {class: 'key-rect', style: `background:${color}`}, s); s.append(`Prompt ${prompt}`); }
  { const s = html('span', {}, hl); html('i', {class: 'key-band'}, s); s.append('Passing band'); }
  const rules = data.rules.head;
  percentBars($('chart-area'), cands.map(c => ({label: c.id, value: c.contract.areaRatio, color: PROMPT_SERIES[c.prompt], notes: c.contract.failures})), rules.areaRatio, 'Head area as a percentage of native');
  percentBars($('chart-face'), cands.map(c => ({label: c.id, value: c.contract.faceRatio, color: PROMPT_SERIES[c.prompt], notes: c.contract.failures})), [rules.face.minRatio, 99], 'Face skin as a percentage of native');
  table($('table-heads'), [['Candidate'], ['Result'], ['Area', 1], ['Face', 1], ['Silhouette overlap', 1], ['Outline', 1], ['Reasons']],
    cands.map(c => { const ul = document.createElement('ul'); c.contract.failures.forEach(f => html('li', {}, ul, f));
      return [c.id, statusBadge(document.createElement('span'), c.contract.pass), pct(c.contract.areaRatio), c.contract.faceRatio < 0 ? '—' : pct(c.contract.faceRatio), c.contract.alphaIoU.toFixed(3), pct(c.contract.outlineRatio), c.contract.failures.length ? ul : '—']; }));
  const face = data.nativeFace.box, S = 8;
  const headFigure = (src, caption, pass, failures) => {
    const f = html('figure', {}, $('strip-heads'));
    const box = html('div', {class: 'headbox'}, f);
    sprite(box, src, S, caption);
    html('div', {class: 'facebox', style: `left:${face[0] * S}px;top:${face[1] * S}px;width:${face[2] * S}px;height:${face[3] * S}px`}, box);
    const cap = html('figcaption', {}, f, caption + ' ');
    if (pass !== undefined) statusBadge(cap, pass);
    if (failures?.length) { const ul = html('ul', {class: 'tag', style: 'text-align:left;max-width:240px;margin:0;padding-left:14px'}, f); failures.forEach(x => html('li', {}, ul, x)); }
  };
  headFigure(head.images.native, 'Native RO head');
  cands.forEach(c => headFigure(c.image, `${c.id} · ${c.designReference}`, c.contract.pass, c.contract.failures));

  // 3. Prompt comparison
  const groups = Object.keys(PROMPT_SERIES).map(prompt => {
    const list = cands.filter(c => c.prompt === prompt);
    return [`Prompt ${prompt}`, list[0]?.designReference || (prompt === 'v0.2.0' ? 'V3 compact attack art' : '—'), list.length, list.length ? `${list.filter(c => c.contract.pass).length} / ${list.length}` : '—',
      list.length ? pct(median(list.map(c => c.contract.areaRatio))) : '—', list.length ? pct(median(list.map(c => c.contract.faceRatio))) : '—'];
  });
  table($('table-prompts'), [['Prompt'], ['Design reference'], ['Candidates', 1], ['Pass', 1], ['Median area', 1], ['Median face', 1]], groups);

  // 4. Body
  percentBars($('chart-body'), body.map(b => ({label: `Body ${b.slot}`, value: b.contract.areaRatio, color: 'var(--series-1)', notes: b.contract.failures})), data.rules.body.areaRatio, 'Body drawing area as a percentage of native');
  table($('table-body'), [['Drawing'], ['Result'], ['Area', 1], ['Silhouette overlap', 1], ['Outline', 1]],
    body.map(b => [`Body ${b.slot} · ${b.role}`, statusBadge(document.createElement('span'), b.contract.pass), pct(b.contract.areaRatio), b.contract.alphaIoU.toFixed(3), pct(b.contract.outlineRatio)]));
  $('status').textContent = `Data generated ${data.generatedAt} · palette ${data.palette.id}.`;
}

$('theme').addEventListener('click', () => {
  const dark = document.documentElement.dataset.theme !== 'dark' && !(document.documentElement.dataset.theme !== 'light' && matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  $('theme').textContent = dark ? 'Light mode' : 'Dark mode';
});

fetch(`${ASSETS}review/review.json`, {cache: 'no-store'}).then(r => { if (!r.ok) throw new Error(`review.json ${r.status}`); return r.json(); })
  .then(render).catch(error => { $('status').textContent = `Review data unavailable (${error.message}). Run export_review.gd first.`; });
