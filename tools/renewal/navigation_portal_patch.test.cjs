// T07.006.002 authored controls (authored; not executed by the worker). Runs the
// actual patched MapPathFinder+Navigation fragment and complete patched Worker in
// Node vm contexts with authored stubs/maps. Test-only substitution: the two exact
// `import.meta.url` occurrences become a fixed fixture URL string for vm.Script.
"use strict";

const assert = require("assert");
const crypto = require("crypto");
const vm = require("vm");
const patch = require("./navigation_portal_patch.cjs");

const POLICY = "ordinary-portals-only";
const FIXTURE_URL = "file:///t07-006-002-fixture/Online.js";
const FRAGMENT_START = "//#region src/UI/Components/Navigation/MapPathFinder.js\n";
const FRAGMENT_END = "//#endregion\n//#region src/UI/Components/WorldMap/WorldMap.js\n";
const LABELS = ["找不到路徑", "地圖選點", "請選擇結果"];
const INIT_NAMES = ["DBManager", "KeyEventHandler", "Renderer", "MapRenderer", "UIManager", "GUIComponent", "Elements", "Altitude", "SessionStorage", "Client", "Entity$1", "SpriteRenderer", "Navigation$2", "Navigation$1"];
// Authored fixtures, not navigation data: alpha has a wall at x=6.
const MAPS = { alpha: { width: 12, height: 3, wall: 6 }, beta: { width: 12, height: 3, wall: -1 } };
const link = (src, id, type, sx, sy, dst, dx, dy) => [src, id, type, 0, "link" + id, 0, sx, sy, dst, dx, dy];
const LINKS = [
  link("alpha", 603, 203, 1, 2, "beta", 1, 1), link("alpha", 601, 201, 2, 2, "beta", 1, 1), link("alpha", 602, 200, 5, 2, "beta", 1, 1),
  link("alpha", 503, 205, 1, 0, "alpha", 11, 0), link("alpha", 501, 201, 2, 1, "alpha", 8, 1), link("alpha", 502, 200, 4, 1, "alpha", 9, 1),
  link("beta", 701, 200, 10, 2, "alpha", 10, 2),
];
const MANUAL_KEYS = ["endX", "endY", "existingPath", "mapData", "startX", "startY", "type", "workerId"];
const CTX2D = new Proxy({}, {
  get: (t, p) => (p === "canvas" ? { width: 280, height: 230 } : p in t ? t[p] : () => undefined),
  set: (t, p, v) => { t[p] = v; return true; },
});

const sha = (text) => crypto.createHash("sha256").update(text, "utf8").digest("hex");
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const ids = (path) => (Array.isArray(path) ? path : []).filter((p) => p && p.isWarp).map((p) => p.warpId);
const summ = (path) => (Array.isArray(path) ? path.slice(0, 16).map((p) => (p.isWarp ? [p.x, p.y, p.warpId] : [p.x, p.y])) : path);
const errorText = (e) => String((e && e.message) || e);

function clone(v) {
  if (v === null || typeof v !== "object") return v;
  if (ArrayBuffer.isView(v)) return Uint8Array.from(v);
  if (Array.isArray(v)) return v.map(clone);
  const out = {};
  for (const k of Object.keys(v)) out[k] = clone(v[k]);
  return out;
}

function bound(v) {
  let s;
  try { s = JSON.stringify(v === undefined ? null : v); } catch (e) { s = JSON.stringify(errorText(e)); }
  if (s === undefined) s = "null";
  return s.length <= 360 ? JSON.parse(s) : s.slice(0, 360) + "...";
}

function gat(name) {
  const m = MAPS[name];
  const cells = new Uint8Array(m.width * m.height * 5);
  for (let i = 0; i < m.width * m.height; i++) cells[i * 5 + 4] = i % m.width === m.wall ? 0 : 1;
  return { width: m.width, height: m.height, cells };
}

function mapData(name, warps) {
  const g = gat(name);
  const cellTypes = new Uint8Array(g.width * g.height);
  for (let i = 0; i < cellTypes.length; i++) cellTypes[i] = g.cells[i * 5 + 4];
  return { walkableType: 1, width: g.width, height: g.height, cellTypes, warps };
}

const localWarps = (wanted) => LINKS.filter((r) => wanted.includes(r[1])).map((r) => ({ id: r[1], type: r[2], srcX: r[6], srcY: r[7], destX: r[9], destY: r[10] }));
const findMsg = (map, warps, extra) => Object.assign({ type: "findPath", startX: 1, startY: 1, endX: 11, endY: 1, mapData: mapData(map, warps), workerId: "w" }, extra);

function hostScript(onlineText, label) {
  const start = onlineText.indexOf(FRAGMENT_START);
  const end = onlineText.indexOf(FRAGMENT_END);
  assert(start > 0 && end > start && onlineText.indexOf(FRAGMENT_START, start + 1) === -1, "fragment markers");
  const parts = onlineText.slice(start, end + "//#endregion\n".length).split("import.meta.url");
  assert.strictEqual(parts.length, 3, "exactly two import.meta.url occurrences");
  return new vm.Script(parts.join(JSON.stringify(FIXTURE_URL)), { filename: label });
}

function makeHarness(scripts, opts) {
  const st = { now: 0, timers: [], workers: [], renders: [], ui: [], spy: [], appends: 0, gat: [], storage: [], links: opts.links || LINKS, ready: new Set(opts.ready || ["alpha", "beta"]) };
  const els = new Map();
  const el = (key) => {
    if (!els.has(key)) els.set(key, { style: {}, textContent: "", checked: false, classList: { add() {}, remove() {}, toggle() {} },
      addEventListener() {}, appendChild() {}, replaceChildren() {}, setAttribute() {}, querySelector: (s) => el(s), querySelectorAll: () => [],
      getContext: () => CTX2D, getBoundingClientRect: () => ({ left: 0, top: 0, width: 280, height: 230 }) });
    return els.get(key);
  };
  class FakeWorker {
    constructor() { this.sent = []; this.cursor = 0; this.terminated = false; st.workers.push(this); }
    postMessage(m) { this.sent.push(clone(m)); }
    terminate() { this.terminated = true; }
  }
  class GUIComponent {
    constructor() {
      const host = this._host = el("#host");
      this._root = el("#root");
      this.ui = { show: () => { st.ui.push("show"); host.style.display = "block"; }, hide: () => { st.ui.push("hide"); host.style.display = "none"; } };
    }
    getRoot() { return this._root; }
    draggable() {}
  }
  const loadFile = (path, cb) => {
    const m = /^data\/(\w+)\.gat$/.exec(path);
    if (m && st.ready.has(m[1])) cb(gat(m[1])); else if (m) st.gat.push([m[1], cb]);
  };
  const sandbox = {
    __esmMin: (fn) => { let done = false; return () => { if (!done) { done = true; fn(); } }; },
    Navigation_default$1: "", Navigation_default$2: "", GUIComponent, URL, UIManager: { addComponent: (c) => c },
    Renderer: { render: (fn) => st.renders.push(fn), stop() {}, getContext: () => null, width: 1280, height: 720 },
    MapRenderer: { currentMap: (opts.map || "alpha") + ".gat" },
    SessionStorage_default: { Entity: { position: [1, 1, 0], direction: 0 } },
    Altitude: { TYPE: { WALKABLE: 1 }, getCell: () => null }, Client: { loadFile },
    DB: { INTERFACE_PATH: "data/texture/", mapalias: {}, getNaviLinkTable: () => st.links, getNaviLinkDistanceTable: () => [], getNaviMapTable: () => [], getTownInfo: () => [] },
    KEYS: { ENTER: 13, ESCAPE: 27 }, SpriteRenderer: {}, Camera: {}, Texture: {}, WebGL_default: {},
    Image: class { constructor() { this.complete = false; this.width = 0; } },
    Worker: FakeWorker, Date: class { getTime() { return 1700000000000; } },
    document: { createElement: () => el("canvas"), addEventListener() {}, removeEventListener() {} },
    getComputedStyle: (e) => ({ display: e.style.display === "none" ? "none" : "block", color: "" }),
    localStorage: { getItem: () => null, setItem: (k) => st.storage.push(k) },
    setTimeout: (fn, ms) => st.timers.push({ at: st.now + (Number(ms) || 0), fn }),
    setInterval: () => 1, clearInterval() {}, performance: { now: () => st.now },
  };
  for (const name of INIT_NAMES) sandbox["init_" + name] = () => {};
  const ctx = vm.createContext(sandbox);
  scripts.host.runInContext(ctx, { timeout: 5000 });
  ctx.init_Navigation();
  const finder = ctx.MapPathFinder.findPathBetweenMaps;
  ctx.MapPathFinder.findPathBetweenMaps = function(...args) { st.spy.push(Array.from(args[6] || [])); return finder.apply(this, args); };
  const Nav = ctx.Navigation;
  Nav.init();
  const wout = [];
  const wctx = vm.createContext({ self: { postMessage: (m) => wout.push(m) } });
  scripts.worker.runInContext(wctx, { timeout: 5000 });
  const compute = (msg) => { wout.length = 0; wctx.self.onmessage({ data: clone(msg) }); return clone(wout.pop()); };
  const pos = () => ctx.SessionStorage_default.Entity.position;
  const status = () => Nav.getLinkPolicyStatus();
  const h = {
    st, ctx, Nav, el, compute,
    append() { st.appends++; Nav.onAppend(); },
    remove() { Nav.onRemove(); },
    ready(name) {
      st.ready.add(name);
      const due = st.gat.filter((g) => g[0] === name);
      st.gat = st.gat.filter((g) => g[0] !== name);
      for (const g of due) g[1](gat(name));
    },
    advance(to) { // fake monotonic clock; runs due 100ms readiness polls in order
      for (let guard = 0, next; guard < 2000; guard++) {
        next = st.timers.filter((x) => x.at <= to).sort((a, b) => a.at - b.at)[0];
        if (!next) break;
        st.timers.splice(st.timers.indexOf(next), 1); st.now = next.at; next.fn();
      }
      st.now = Math.max(st.now, to);
    },
    render(tick) { for (const fn of st.renders.slice()) fn(tick); },
    at(x, y) { ctx.SessionStorage_default.Entity.position = [x, y, 0]; },
    map(name) { ctx.MapRenderer.currentMap = name + ".gat"; },
    worker: () => ctx._pathFindingWorker,
    sent: () => st.workers.flatMap((w) => w.sent),
    last: () => h.sent()[h.sent().length - 1],
    n: () => h.sent().length,
    timers: () => st.timers.length,
    live: () => st.workers.filter((w) => !w.terminated).length,
    spy: () => st.spy[st.spy.length - 1],
    status: () => clone(status()),
    state: () => status().state,
    gen: () => status().requestGeneration,
    display: () => el("#host").style.display,
    deliver(w, result) { w.onmessage({ data: clone(result) }); },
    pump(w = ctx._pathFindingWorker, out = []) {
      while (w && w.cursor < w.sent.length) { const r = compute(w.sent[w.cursor++]); out.push(r); h.deliver(w, r); }
      return out;
    },
    hold() { const w = ctx._pathFindingWorker; const r = compute(h.last()); w.cursor = w.sent.length; return [w, r]; },
    snap: () => clone({ final: ctx._finalTargetData, target: ctx._targetData, path: summ(ctx._path), lock: ctx._pathUpdateLock }),
    manual: (endMap, endX, endY, extra) => Nav.navigateTo(Object.assign({ startMap: ctx.getCurrentMap(), startX: Math.ceil(pos()[0]), startY: Math.ceil(pos()[1]), endMap, endX, endY, displayName: "T" }, extra)),
    tag: (endMap, endX, endY) => h.manual(endMap, endX, endY, { linkPolicy: POLICY }),
  };
  return h;
}

function setup(scripts, opts) {
  const h = makeHarness(scripts, opts || {});
  h.append();
  h.st.ui.length = 0;
  return h;
}

function group(id, cases) {
  const checks = cases.map(([name, fn]) => {
    try {
      const [passed, observed] = fn();
      return { name, observed: bound(observed), passed: passed === true };
    } catch (error) {
      return { name, observed: bound({ error: errorText(error) }), passed: false };
    }
  });
  return { id, passed: checks.length > 0 && checks.every((c) => c.passed), checks };
}

const eq = (observed, expected, extra) => [same(observed, expected), extra === undefined ? observed : Object.assign({ extra }, observed)];

function refuses(fn) {
  try { fn(); return false; } catch (e) { return /refusing|must be a string/.test(errorText(e)); }
}

const FINAL = (map, x) => ({ map, x, y: 1, displayName: "T", linkPolicy: POLICY });

const g01 = (c) => group("G01", [
  ["pinned pair patches once", () => {
    const p = c.patched, again = patch.applyNavigationPortalPolicy(c.online, c.worker);
    return eq({ keys: Object.keys(p).join(), repeat: again.onlineText === p.onlineText && again.workerText === p.workerText,
      changed: [sha(p.onlineText) !== patch.PINS.online.sha256, sha(p.workerText) !== patch.PINS.worker.sha256],
      capped: [Buffer.byteLength(p.onlineText) <= patch.CAPS.online, Buffer.byteLength(p.workerText) <= patch.CAPS.worker] },
    { keys: "onlineText,workerText", repeat: true, changed: [true, true], capped: [true, true] });
  }],
  ["drift and re-patch refuse", () => {
    const a = patch.applyNavigationPortalPolicy;
    const o = { repatch: refuses(() => a(c.patched.onlineText, c.patched.workerText)), onlineByte: refuses(() => a(c.online + " ", c.worker)),
      onlineAnchor: refuses(() => a(c.online.replace("function navigateTo(options) {", "function navigateTo(opts) {"), c.worker)),
      workerByte: refuses(() => a(c.online, c.worker.replace("workerId: data.workerId", "workerId: data.workerID"))), nonString: refuses(() => a(null, c.worker)) };
    return [Object.values(o).every(Boolean), o];
  }],
  ["malformed tagged options do not mutate", () => {
    const h = setup(c.s); h.manual("alpha", 11, 1); h.pump();
    const view = () => JSON.stringify([h.snap(), h.n(), h.st.workers.length, h.st.spy.length, h.ctx._navigationRequestGeneration]);
    const before = view();
    const base = { startMap: "alpha", startX: 1, startY: 1, endMap: "beta", endX: 11, endY: 1, linkPolicy: POLICY };
    const bad = [{ endX: -1 }, { endX: 1.5 }, { endY: NaN }, { startX: "1" }, { endX: Infinity }, { startY: undefined }, { endMap: "" }, { endMap: ".gat" }, { startMap: 7 }, { endMap: null },
      { linkPolicy: "all" }, { linkPolicy: null }, { linkPolicy: "ORDINARY-PORTALS-ONLY" }, { linkPolicy: 101 }, { linkPolicy: [POLICY] }];
    const results = bad.map((b) => h.Nav.navigateTo(Object.assign({}, base, b)));
    return eq({ results, unchanged: before === view() }, { results: bad.map(() => false), unchanged: true });
  }],
  ["raw service101 alone stays manual", () => {
    const h = setup(c.s); const r = h.manual("beta", 11, 1, { service: 101, serviceType: 101, hideWindow: true }); const m = h.last();
    return eq({ r: String(r), spy: h.spy(), policy: h.ctx._finalTargetData.linkPolicy || null, tagged: !!m && "requestGeneration" in m, state: h.state() },
      { r: "undefined", spy: [200, 201], policy: null, tagged: false, state: "none" });
  }],
]);

const g02 = (c) => group("G02", [
  ["tagged local route excludes 201/205 shortcuts", () => {
    const h = setup(c.s); h.tag("alpha", 11, 1); const m = h.last(); const [r] = h.pump();
    return eq({ posted: m.mapData.warps.map((w) => [w.id, w.type]), used: ids(r.path), state: h.state(), existingPath: m.existingPath, hostPath: same(summ(h.ctx._path), summ(r.path)) },
      { posted: [[502, 200]], used: [502], state: "routed", existingPath: null, hostPath: true }, summ(r.path));
  }],
  ["manual control would take excluded shortcut", () => {
    const h = setup(c.s); h.manual("alpha", 11, 1); const m = h.last(); const [r] = h.pump(); const used = ids(r.path);
    return [used.some((id) => id === 501 || id === 503) && m.mapData.warps.length === 3, used];
  }],
  ["worker filters host-supplied excluded links", () => {
    const h = setup(c.s);
    const msg = findMsg("alpha", localWarps([503, 501, 502]), { existingPath: null, requestGeneration: 9, requestMap: "alpha", linkPolicy: POLICY });
    const r = h.compute(msg); const u = h.compute(Object.assign({}, msg, { linkPolicy: "unknown" }));
    return eq({ used: ids(r.path), echo: [r.requestGeneration, r.requestMap, r.linkPolicy, r.workerId], unknown: u.path }, { used: [502], echo: [9, "alpha", POLICY, "w"], unknown: null });
  }],
  ["map planner admits type200 only", () => {
    const run = (checked, tagged) => {
      const h = setup(c.s); h.el(".services-toggle").checked = checked;
      if (tagged) h.tag("beta", 11, 1); else h.manual("beta", 11, 1);
      const m = h.last();
      return { spy: h.spy(), hop: m && [m.endX, m.endY] };
    };
    return eq({ tagged: run(false, true), taggedChecked: run(true, true), manual: run(false, false), manualChecked: run(true, false) },
      { tagged: { spy: [200], hop: [5, 2] }, taggedChecked: { spy: [200], hop: [5, 2] }, manual: { spy: [200, 201], hop: [2, 2] }, manualChecked: { spy: [200, 201, 202, 203, 204, 205], hop: [1, 2] } });
  }],
  ["no links is honest unavailable", () => {
    const h = setup(c.s, { links: [] }); const r = h.tag("beta", 11, 1); const s = h.snap();
    return eq({ r, state: h.state(), sent: h.n(), final: s.final, path: s.path.length }, { r: true, state: "unavailable", sent: 0, final: FINAL("beta", 11), path: 0 });
  }],
  ["walking only when no admitted local link exists", () => {
    const run = (opts, map, x) => { const h = setup(c.s, opts); h.tag(map, x, 1); const m = h.last(); const [r] = h.pump(); return [m.mapData.warps.length, r.path.length > 0, ids(r.path), h.state()]; };
    return eq([run({ links: [], map: "beta" }, "beta", 10), run({ links: LINKS.filter((l) => l[1] === 501 || l[1] === 503) }, "alpha", 11)], [[0, true, [], "routed"], [0, false, [], "empty"]]);
  }],
]);

function g03(c) {
  const run = (checked) => {
    const h = setup(c.s); const toggle = h.el(".services-toggle"); toggle.checked = checked; const display = h.display();
    h.tag("beta", 11, 1); const m = h.last(); h.pump();
    return { spy: h.spy(), hop: [m.endX, m.endY], warps: m.mapData.warps.map((w) => w.type), policy: m.linkPolicy, existingPath: m.existingPath,
      checked: toggle.checked, display: [display, h.display()], ui: h.st.ui.slice(), storage: h.st.storage.slice(), state: h.state() };
  };
  const manual = (checked) => {
    const h = setup(c.s); h.el(".services-toggle").checked = checked; h.manual("beta", 11, 1);
    return { spy: h.spy(), checked: h.el(".services-toggle").checked };
  };
  return group("G03", [
    ["tagged policy identical for both checkbox states", () => {
      const off = run(false), on = run(true), strip = (o) => Object.assign({}, o, { checked: null });
      return eq({ equal: same(strip(off), strip(on)), spy: off.spy, warps: off.warps, policy: off.policy, state: off.state }, { equal: true, spy: [200], warps: [200], policy: POLICY, state: "routed" });
    }],
    ["preferences visibility and manual checkbox behavior retained", () => {
      const off = run(false), on = run(true);
      return eq({ checked: [off.checked, on.checked], display: [off.display, on.display], ui: [off.ui, on.ui], storage: [off.storage, on.storage], manual: [manual(false), manual(true)] },
        { checked: [false, true], display: [["none", "none"], ["none", "none"]], ui: [[], []], storage: [[], []], manual: [{ spy: [200, 201], checked: false }, { spy: [200, 201, 202, 203, 204, 205], checked: true }] });
    }],
  ]);
}

const g04 = (c) => group("G04", [
  ["hidden render callback replans with policy", () => {
    const h = setup(c.s); h.tag("alpha", 11, 1); const first = h.last(); h.pump(); h.at(2, 1); h.advance(1000); h.render(1000); const m = h.last();
    return eq({ newer: m.requestGeneration > first.requestGeneration, start: [m.startX, m.startY], policy: m.linkPolicy, existingPath: m.existingPath, display: h.display(), ui: h.st.ui, count: h.n() },
      { newer: true, start: [2, 1], policy: POLICY, existingPath: null, display: "none", ui: [], count: 2 });
  }],
  ["shown panel keeps visibility and single maintenance", () => {
    const h = setup(c.s); h.Nav.show(); h.st.ui.length = 0;
    h.tag("alpha", 11, 1); h.pump(); h.at(2, 1); h.advance(1000); h.render(1000); h.render(1100);
    return eq({ display: h.display(), ui: h.st.ui, count: h.n(), tagged: h.sent().every((m) => m.linkPolicy === POLICY) }, { display: "block", ui: [], count: 2, tagged: true });
  }],
  ["show and repeated append keep policy and coalesce", () => {
    const h = setup(c.s); h.tag("alpha", 11, 1); h.pump(); h.Nav.show(); const afterShow = h.last(); const s1 = h.status(); h.append(); const s2 = h.status();
    return eq({ count: h.n(), policy: afterShow.linkPolicy, sameGen: s1.requestGeneration === s2.requestGeneration, states: [s1.state, s2.state], loops: h.st.renders.length === h.st.appends },
      { count: 2, policy: POLICY, sameGen: true, states: ["worker", "worker"], loops: true });
  }],
  ["map transition keeps policy through removal and append", () => {
    const h = setup(c.s); h.tag("beta", 11, 1); const m1 = h.last(); h.pump();
    h.remove(); h.map("beta"); h.at(1, 1); h.append(); const m2 = h.last(); const s = h.snap();
    return eq({ m1: [m1.requestMap, m1.endX, m1.endY], m2: [m2.requestMap, m2.endX, m2.endY, m2.linkPolicy], newer: m2.requestGeneration > m1.requestGeneration,
      final: [s.final.x, s.final.linkPolicy], ui: h.st.ui, live: h.live(), loops: h.st.renders.length === h.st.appends },
    { m1: ["alpha", 5, 2], m2: ["beta", 11, 1, POLICY], newer: true, final: [11, POLICY], ui: [], live: 1, loops: true });
  }],
]);

const g05 = (c) => group("G05", [
  ["replacement fences old result with reused worker id", () => {
    const h = setup(c.s); h.tag("alpha", 11, 1); const [w1, r1] = h.hold(); h.tag("beta", 11, 1); const w2 = h.worker();
    h.deliver(w1, r1); const stale = h.snap(); h.pump(w2); const fresh = h.snap();
    return eq({ distinct: w1 !== w2, sameId: w1.id === w2.id, terminated: w1.terminated, stale: [stale.path.length, stale.lock], fresh: [fresh.path.length > 0, fresh.lock], state: h.state() },
      { distinct: true, sameId: true, terminated: true, stale: [0, true], fresh: [true, false], state: "routed" });
  }],
  ["same worker stale or forged results cannot unlock", () => {
    const h = setup(c.s); h.tag("alpha", 11, 1); h.pump(); const p1 = h.snap().path; h.at(2, 1); h.render(1000); const m2 = h.last(); const [w, r2] = h.hold();
    const forged = [Object.assign({}, r2, { requestGeneration: m2.requestGeneration - 1, path: [{ x: 0, y: 0 }] }), Object.assign({}, r2, { requestMap: "beta" }),
      Object.assign({}, r2, { linkPolicy: "all" }), { type: "pathResult", path: [{ x: 0, y: 0 }], workerId: r2.workerId }];
    const held = forged.map((f) => { h.deliver(w, f); const s = h.snap(); return [s.lock, same(s.path, p1)]; });
    h.deliver(w, r2); const fin = h.snap();
    return eq({ held, fin: [fin.lock, fin.path.length > 0] }, { held: forged.map(() => [true, true]), fin: [false, true] });
  }],
  ["manual override retires tagged request", () => {
    const h = setup(c.s); h.tag("alpha", 11, 1); const [w1, r1] = h.hold(); h.manual("alpha", 11, 1); const w2 = h.worker(); const mm = h.last();
    h.deliver(w1, r1); const stale = h.snap(); h.pump(w2); const fin = h.snap();
    return eq({ distinct: w1 !== w2, keys: Object.keys(mm).sort(), existingPath: Array.isArray(mm.existingPath), state: h.state(), stale: stale.path.length, fin: [fin.path.length > 0, fin.final.linkPolicy || null] },
      { distinct: true, keys: MANUAL_KEYS, existingPath: true, state: "none", stale: 0, fin: [true, null] });
  }],
  ["tagged existingPath cannot bypass policy", () => {
    const h = setup(c.s); const cached = [{ x: 1, y: 1 }, { x: 2, y: 1, isWarp: true, warpId: 501 }, { x: 9, y: 1 }];
    const base = findMsg("alpha", localWarps([503, 501, 502]), { existingPath: cached });
    const legacy = h.compute(base); const tagged = h.compute(Object.assign({}, base, { requestGeneration: 3, requestMap: "alpha", linkPolicy: POLICY }));
    return eq({ legacyReused: same(legacy.path, cached), taggedUsed: ids(tagged.path) }, { legacyReused: true, taggedUsed: [502] });
  }],
  ["late manual readiness callback is fenced", () => {
    const h = setup(c.s, { ready: [] }); h.manual("alpha", 11, 1); h.tag("alpha", 10, 1); h.ready("alpha"); h.advance(300); const t = h.snap().target;
    return eq({ msgs: h.sent().map((m) => [m.endX, m.linkPolicy || null]), target: t && t.x }, { msgs: [[10, POLICY]], target: 10 });
  }],
]);

const g06 = (c) => group("G06", [
  ["user close and escape cancel fence pending work", () => {
    const run = (close) => {
      const h = setup(c.s); h.Nav.show(); h.tag("alpha", 11, 1); const [w1, r1] = h.hold(); close(h); h.deliver(w1, r1); h.advance(1000); h.render(1000); const s = h.snap();
      return { final: s.final, path: s.path.length, state: h.state(), sent: h.n(), terminated: w1.terminated, live: h.live() };
    };
    const e = { final: null, path: 0, state: "none", sent: 1, terminated: true, live: 0 };
    return eq([run((h) => h.Nav.hide()), run((h) => h.Nav.onKeyDown({ key: "Escape", which: 27 }))], [e, e]);
  }],
  ["arrival completion fences late result", () => {
    const h = setup(c.s); h.tag("alpha", 11, 1); const [w, r1] = h.hold(); h.at(9, 1); h.render(1000); h.deliver(w, r1); h.advance(2000); h.render(2000); const s = h.snap();
    return eq({ final: s.final, path: s.path.length, sent: h.n(), state: h.state() }, { final: null, path: 0, sent: 1, state: "none" });
  }],
  ["removal is inactive and re-entry resumes freshly", () => {
    const h = setup(c.s, { ready: [] }); h.tag("alpha", 11, 1); const g1 = h.gen(); h.remove(); const removed = h.state();
    h.ready("alpha"); h.advance(1000); h.render(600); h.render(1200); const during = { sent: h.n(), live: h.live() };
    h.append(); const m = h.last();
    return eq({ removed, during, after: m && [m.endX, m.endY, m.linkPolicy], newer: !!m && m.requestGeneration > g1, state: h.state(), workers: h.st.workers.length, live: h.live() },
      { removed: "inactive", during: { sent: 0, live: 0 }, after: [11, 1, POLICY], newer: true, state: "worker", workers: 2, live: 1 });
  }],
  ["repeated append cannot evade pending deadline", () => {
    const h = setup(c.s, { ready: [] }); h.tag("alpha", 11, 1); const g = h.gen();
    h.advance(3000); h.append(); const mid = h.status(); h.advance(5000); const end = h.state(); h.ready("alpha"); h.advance(6000);
    return eq({ sameGen: mid.requestGeneration === g, mid: mid.state, end, sent: h.n(), timers: h.timers(), live: h.live() },
      { sameGen: true, mid: "waiting", end: "unavailable", sent: 0, timers: 0, live: 1 });
  }],
]);

function waitRun(c, readyAt, until) {
  const h = setup(c.s, { ready: [] });
  h.tag("alpha", 11, 1); h.advance(readyAt); h.ready("alpha"); h.advance(until);
  return h;
}

const g07 = (c) => group("G07", [
  ["readiness starts only strictly before 5000ms", () => {
    const run = (readyAt, until) => { const h = waitRun(c, readyAt, until); const m = h.last(); return [h.n(), h.state(), h.timers(), m ? m.linkPolicy : null]; };
    return eq([run(4850, 4950), run(4950, 5000)], [[1, "worker", 0, POLICY], [0, "unavailable", 0, null]]);
  }],
  ["after deadline stays honest and render cannot restart", () => {
    const h = waitRun(c, 7000, 8000); const g = h.gen(); h.render(8000); h.render(9000); const s = h.snap();
    const o = { state: h.state(), sameGen: h.gen() === g, sent: h.n(), timers: h.timers(), final: s.final, target: s.target, path: s.path.length };
    h.tag("alpha", 10, 1); const fresh = h.last(); o.fresh = fresh && [fresh.endX, fresh.requestGeneration > g];
    return eq(o, { state: "unavailable", sameGen: true, sent: 0, timers: 0, final: FINAL("alpha", 11), target: null, path: 0, fresh: [10, true] });
  }],
  ["maintenance does not extend pending deadline", () => {
    const h = setup(c.s, { ready: [] }); h.tag("alpha", 11, 1); const g = h.gen(); const seen = [];
    for (let t = 600; t <= 4800; t += 600) { h.advance(t); h.at(1 + (t / 600) % 2, 1); h.render(t); seen.push([h.gen(), h.timers()]); }
    h.advance(5000);
    return eq({ seen: seen.every(([gen, n]) => gen === g && n === 1), at: h.state(), timers: h.timers(), sent: h.n() }, { seen: true, at: "unavailable", timers: 0, sent: 0 }, seen);
  }],
  ["worker result accepted only before deadline", () => {
    const run = (at) => {
      const h = setup(c.s); h.tag("alpha", 11, 1); const [w, r] = h.hold(); h.advance(at - 1); h.render(at - 1); const before = h.state();
      h.advance(at); h.deliver(w, r); const s = h.snap(); const state = h.state(); h.render(at + 600);
      return { before, state, path: s.path.length > 0, lock: s.lock, sent: h.n(), later: h.state() };
    };
    return eq([run(4999), run(5000)], [{ before: "worker", state: "routed", path: true, lock: false, sent: 2, later: "worker" },
      { before: "worker", state: "unavailable", path: false, lock: false, sent: 1, later: "unavailable" }]);
  }],
]);

function g08(c) {
  const rebuild = (text, hunks) => {
    const located = hunks.map(([, a, b]) => [text.indexOf(a), a, b]).sort((x, y) => x[0] - y[0]);
    let out = "", cursor = 0;
    for (const [at, a, b] of located) { out += text.slice(cursor, at) + b; cursor = at + a.length; }
    return out + text.slice(cursor);
  };
  return group("G08", [
    ["only frozen hunks changed", () => {
      const [regionStart, regionEnd] = patch.NAVIGATION_REGION, p = c.patched.onlineText;
      const lo = c.online.indexOf(regionStart), tail = c.online.indexOf(regionEnd), cut = c.worker.indexOf('\t\t\tcase "findPath": {\n');
      const o = { online: rebuild(c.online, patch.HOST_HUNKS) === p, worker: rebuild(c.worker, patch.WORKER_HUNKS) === c.patched.workerText,
        prefix: lo > 0 && p.slice(0, lo) === c.online.slice(0, lo), suffix: tail > lo && p.slice(p.indexOf(regionEnd)) === c.online.slice(tail),
        workerAlgorithm: cut > 0 && c.patched.workerText.slice(0, cut) === c.worker.slice(0, cut) };
      return [Object.values(o).every(Boolean), o];
    }],
    ["Chinese labels retained", () => {
      const counts = LABELS.map((l) => [c.online.split(l).length - 1, c.patched.onlineText.split(l).length - 1]);
      return [counts.every(([a, b]) => a > 0 && a === b), counts];
    }],
    ["no movement service network quest or UI calls added", () => {
      const added = patch.HOST_HUNKS.concat(patch.WORKER_HUNKS).map(([, a, b]) => b.split("\n").filter((line) => !a.includes(line)).join("\n")).join("\n");
      const forbidden = ["Network", "sendPacket", "ui.show", "ui.hide", "toggle(", ".show(", ".hide(", "Renderer.render", "setInterval", "new Worker", "Quest", "teleport", "focus(", "fetch(", "localStorage", ".checked", "addEventListener"];
      return eq({ hits: forbidden.filter((t) => added.includes(t)), added: added.length > 0 }, { hits: [], added: true });
    }],
    ["manual navigation matches original source", () => {
      const scenario = (scripts) => {
        const h = setup(scripts); h.manual("alpha", 11, 1); h.pump(); h.Nav.show(); h.at(2, 1); h.render(1000); h.pump();
        h.Nav.onMapClick({ clientX: 230, clientY: 115 }); h.pump(); h.manual("beta", 11, 1); h.pump();
        return { spy: h.st.spy, msgs: h.sent().map((m) => [Object.keys(m).sort().join(), m.startX, m.startY, m.endX, m.endY, (m.mapData.warps || []).map((w) => w.id), Array.isArray(m.existingPath) ? m.existingPath.length : m.existingPath]),
          path: summ(h.ctx._path), final: h.snap().final, title: h.el(".location-title").textContent, coords: h.el(".target-coordinates").textContent, ui: h.st.ui };
      };
      const a = scenario(c.original), b = scenario(c.s);
      return [same(a, b) && a.msgs.length >= 3 && a.msgs.every((m) => m[0] === MANUAL_KEYS.join()), { equal: same(a, b), messages: [a.msgs.length, b.msgs.length], title: b.title, coords: b.coords }];
    }],
    ["untagged worker results equal original worker", () => {
      const ho = setup(c.original), hp = setup(c.s);
      const msgs = [findMsg("alpha", localWarps([503, 501, 502]), { existingPath: [] }), findMsg("beta", [], { endX: 10, endY: 2, existingPath: [] }), findMsg("alpha", [], { endX: 6 }),
        findMsg("alpha", localWarps([502]), { existingPath: [{ x: 2, y: 1 }, { x: 3, y: 1 }] }), { type: "other" }];
      const results = msgs.map((m) => [ho.compute(m), hp.compute(m)]);
      return [results.every(([x, y]) => same(x, y)) && same(Object.keys(results[0][0]), ["type", "path", "workerId"]), results.map(([x]) => (x ? summ(x.path) : null))];
    }],
  ]);
}

function runAuthored(onlineText, workerText) {
  const result = {
    schema: "T07.006.002-authored-1",
    scope: "authored_source_controls",
    original_sha256: { online: typeof onlineText === "string" ? sha(onlineText) : null, worker: typeof workerText === "string" ? sha(workerText) : null },
    patched_sha256: { online: null, worker: null },
    groups: [],
  };
  let c = null;
  let failure = null;
  try {
    const patched = patch.applyNavigationPortalPolicy(onlineText, workerText);
    result.patched_sha256 = { online: sha(patched.onlineText), worker: sha(patched.workerText) };
    c = {
      online: onlineText, worker: workerText, patched,
      s: { host: hostScript(patched.onlineText, "patched-fragment.js"), worker: new vm.Script(patched.workerText, { filename: "patched-worker.js" }) },
      original: { host: hostScript(onlineText, "original-fragment.js"), worker: new vm.Script(workerText, { filename: "original-worker.js" }) },
    };
  } catch (error) {
    failure = errorText(error);
  }
  [g01, g02, g03, g04, g05, g06, g07, g08].forEach((build, i) => {
    let built = null;
    if (c) {
      try { built = build(c); } catch (error) { failure = errorText(error); }
    }
    result.groups.push(built || { id: "G0" + (i + 1), passed: false, checks: [{ name: "group harness", observed: bound({ error: failure }), passed: false }] });
  });
  return result;
}

module.exports = { runAuthored };
