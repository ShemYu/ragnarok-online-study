// T07.007.014.023 authored tests for tools/renewal/observe_model_geometry.mjs.
//
//   /usr/bin/perl -e 'alarm shift; exec @ARGV or die "exec: $!"' 120 \
//     node --max-old-space-size=125 --max-semi-space-size=1 tests/model_geometry_observer.test.mjs
//
// Run the file directly (node:test in-process, no runner child). Reads the
// frozen profile metadata, saved source, inventory and the .023 authored
// fixture only; never opens the actual body path and never invokes actual
// mode on the real profile. Copied source executes only on tiny authored
// bodies within TINY_BOUNDS; larger caps and guard faults use handwritten
// stubs, owned fake files and fault-injected fs calls. A stubbed PASS is
// lifecycle evidence only, never compile evidence.
import assert from 'node:assert/strict';
import { createHash, randomBytes } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import {
  CLOSURE_PIN, FIXTURE_PIN, FROZEN, INVENTORY_PIN, ObserverFailure, ObserverRefusal, PRELUDE, PROFILE_BOUNDS, PROFILE_PIN, SOURCE_PIN, SPANS, TINY_BOUNDS,
  ColumnAdmissionError, buildScaffold, checkBoundsWithin, checkEffectiveHeap, checkLittleEndian, checkRoundedColumns, checkStructure, compileInRealm, extractSpans,
  identityOf, main, makeDeadline, preflightModel, readHeldInput, realmStats, runObserver, validateBridge, validateInventory, validateProfile, validateStructure,
  writeExclusive,
} from '../tools/renewal/observe_model_geometry.mjs';
import vm from 'node:vm';

const sha256 = (b) => createHash('sha256').update(b).digest('hex');
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PROFILE_REL = '.tools/renewal/t07-014-023-preparation-root-1/PROFILE_ROOT.json';
const ROOT = process.env.T07_023_ROOT
  ?? (fs.existsSync(path.join(REPO, PROFILE_REL)) ? REPO : path.resolve(REPO, '..', 'reverse-the-Ragnarok-Online-to-play-by-myself'));
const PROFILE_PATH = path.join(ROOT, PROFILE_REL);
const FIXTURE_PATH = path.join(REPO, 'docs/project/fixtures/T07.007.014.023-cases.json');
const PREFIX = process.env.T07_023_PRIVATE_PREFIX ?? path.join(REPO, '.tools/renewal/t07-014-023-claude-c1');

// Fresh exclusive per-run test directory; earlier captures are never touched.
fs.mkdirSync(PREFIX, { recursive: true, mode: 0o700 });
const TEST_DIR = path.join(PREFIX, `tests-${new Date().toISOString().replace(/[:.]/g, '')}-${randomBytes(3).toString('hex')}`);
fs.mkdirSync(TEST_DIR, { mode: 0o700 });
let seq = 0;
const freshDir = (name) => { const d = path.join(TEST_DIR, `${String(++seq).padStart(2, '0')}-${name}`); fs.mkdirSync(d, { mode: 0o700 }); return d; };
const writeOwned = (file, bytes) => { fs.writeFileSync(file, bytes, { mode: 0o600, flag: 'wx' }); return file; };
const pinOf = (file) => { const b = fs.readFileSync(file); return { bytes: b.length, sha256: sha256(b) }; };
const deadline = (ms = 10000) => makeDeadline(ms);
const failsWith = (fn, code, detail) => assert.throws(fn, (e) => {
  assert.ok(e instanceof ObserverFailure || e instanceof ObserverRefusal, String(e?.stack ?? e));
  assert.equal(e.code, code, e.message);
  if (detail !== undefined) assert.equal(e.message, `${code}: ${detail}`);
  return true;
});

const forever = makeDeadline(10000);
const fixtureHeld = readHeldInput(FIXTURE_PATH, FIXTURE_PIN, 1 << 20, forever, 'fixture');
let fixture;
try { fixture = JSON.parse(fixtureHeld.bytes.toString('utf8')); } finally { fixtureHeld.close(); fixtureHeld.releaseBytes(); }
const profileHeld = readHeldInput(PROFILE_PATH, PROFILE_PIN, 1 << 20, forever, 'profile');
profileHeld.close();
const PROFILE_TEXT = profileHeld.bytes.toString('utf8');
const realProfile = () => JSON.parse(PROFILE_TEXT);
const P0 = realProfile();
const sourceHeld = readHeldInput(P0.source.path, { ...SOURCE_PIN, identity: P0.source.identity }, SOURCE_PIN.bytes, forever, 'source');
sourceHeld.close();
const inventoryHeld = readHeldInput(P0.inventory.path, { ...INVENTORY_PIN, identity: P0.inventory.identity }, INVENTORY_PIN.bytes, forever, 'inventory');
inventoryHeld.close();
const INVENTORY = JSON.parse(inventoryHeld.bytes.toString('utf8'));
const SPAN_TEXTS = extractSpans(sourceHeld.bytes);
const SCAFFOLD = buildScaffold(SPAN_TEXTS);
const caseById = new Map(fixture.cases.map((c) => [c.id, c]));
const POSITIVE = fixture.cases.filter((c) => c.expected.outcome === 'returned');
const NEGATIVE = fixture.cases.filter((c) => c.expected.outcome === 'host_refusal');
const bodyOf = (id) => Uint8Array.from(caseById.get(id).body_bytes);
const P01 = caseById.get('P01_simple_smooth_XY');
const ID3 = [1, 0, 0, 0, 1, 0, 0, 0, 1];

// Authored RSM2.3 writer (independent of the observer) for new controls.
function rsm({ magic = 'GRSM', ver = [2, 3], animLen = 0, shade = 2, alpha = 255, fps = 30, globals = [], nodes, volume, trailing } = {}) {
  const parts = [];
  const i32 = (v) => { const b = Buffer.alloc(4); b.writeInt32LE(v); parts.push(b); };
  const f32 = (v) => { const b = Buffer.alloc(4); b.writeFloatLE(v); parts.push(b); };
  const str = (s) => { const b = Buffer.isBuffer(s) ? s : Buffer.from(s, 'latin1'); i32(b.length); parts.push(b); };
  parts.push(Buffer.from(magic, 'latin1'), Buffer.from(ver));
  i32(animLen); i32(shade); parts.push(Buffer.from([alpha])); f32(fps);
  i32(globals.length); globals.forEach(str);
  i32(nodes.length);
  for (const n of nodes) {
    str(n.name ?? 'n'); str(n.parent ?? '');
    const tex = n.textures ?? ['a.bmp']; i32(tex.length); tex.forEach(str);
    (n.mat3 ?? ID3).forEach(f32); (n.offset ?? [0, 0, 0]).forEach(f32);
    const vs = n.vertices ?? [[0, 0, 0], [1, 0, 0], [0, 1, 0]]; i32(vs.length); vs.forEach((v) => v.forEach(f32));
    const uv = n.uvs ?? [[255, 255, 255, 255, 0, 0], [255, 255, 255, 255, 1, 0], [255, 255, 255, 255, 0, 1]];
    i32(uv.length); uv.forEach((u) => { parts.push(Buffer.from(u.slice(0, 4))); f32(u[4]); f32(u[5]); });
    const fs_ = n.faces ?? [{}]; i32(fs_.length);
    for (const f of fs_) {
      const len = f.len ?? 24; i32(len);
      const b = Buffer.alloc(16);
      [...(f.v ?? [0, 1, 2]), ...(f.t ?? [0, 1, 2]), f.tex ?? 0, f.pad ?? 0].forEach((x, i) => b.writeUInt16LE(x, i * 2));
      parts.push(b); i32(f.twoSide ?? 0); i32(f.group ?? 0);
      if (len > 24) i32(f.g1 ?? 7);
      if (len > 28) i32(f.g2 ?? 9);
      if (len > 32) parts.push(Buffer.alloc(len - 32, 0xab));
    }
    (n.keys ?? [0, 0, 0, 0]).forEach(i32);
  }
  if (volume !== undefined) i32(volume);
  if (trailing) parts.push(trailing);
  return Uint8Array.from(Buffer.concat(parts));
}
const ZP = { position: [0, 0, 0], rotation: [0, 0, 0], scale: [1, 1, 1] };
const ZG = { width: 0, height: 0 };
const pre = (body, limits = TINY_BOUNDS, placement = ZP, ground = ZG) => preflightModel(body, placement, ground, limits);
// Pre-VM refusal: the counters are read after the call/catch completes and
// must show zero realm creations and no definitions evaluation.
const refused = (fn, detail, code = 'preflight_refused') => {
  const created = realmStats.created; const definitions = realmStats.definitions;
  failsWith(fn, code, detail);
  assert.equal(realmStats.created - created, 0, 'no realm before refusal');
  assert.equal(realmStats.definitions - definitions, 0, 'no definitions before refusal');
};
const meshMatches = (out, c) => {
  assert.equal(out.meshes.length, c.expected.meshes.length, c.id);
  out.meshes.forEach((m, i) => {
    const e = c.expected.meshes[i];
    for (const k of ['node_index', 'texture_key', 'float_count', 'byte_length', 'float32_le_hex', 'sha256']) assert.equal(m[k], e[k], `${c.id} mesh${i}.${k}`);
  });
  assert.deepEqual(out.textures, c.expected.reference_geometry.textures, c.id);
};

// Handwritten stub scaffold mirroring a preflight's constructed structure;
// meshes are supplied by `meshExpr` (realm source text). Guard faults only.
// faces mirror the preflight's primary groups unless facesExpr overrides them.
function stub(p, meshExpr, { hasAnimation = 'false', instances = '[]', ctorExtra = '', definitions = '', facesExpr, markers = false } = {}) {
  const facesOf = (n, i) => facesExpr?.(n, i) ?? `[${n.raw.faces.map((f) => `{ smoothGroup: ${f.smoothGroup} }`).join(',')}]`;
  const nodes = p.nodes.map((n, i) => `{ name: ${JSON.stringify(n.name)}, parentname: "", textures: ${JSON.stringify(n.global_texture_keys)}, mat3: [${n.mat3.join(',')}], offset: [0,0,0], vertices: new Array(${n.vertices}), tvertices: new Float32Array(${6 * n.uvs}), faces: ${facesOf(n, i)}, scaleKeyFrames: [], rotKeyframes: [], posKeyframes: [], textureKeyFrameGroup: [], is_only: ${p.nodes.length === 1} }`);
  if (markers) {
    hasAnimation = '(function () { throw new Error("MARKER_hasAnimation"); })()';
  }
  return `${PRELUDE}${definitions}
var RSM = class RSM {
  constructor(input) { this.version = 2 + 3 / 10; this.animLen = ${p.animLen}; this.shadeType = ${p.shadeType}; this.alpha = ${p.alpha}; this.frameRatePerSecond = ${p.frameRatePerSecond};
    this.textures = ${JSON.stringify(p.textures)}; this.volumebox = []; this.posKeyframes = []; this.nodes = [${nodes.join(',')}]; this.main_node = this.nodes[0]; this.instances = ${instances}; ${ctorExtra} }
  hasAnimation() { return ${hasAnimation}; }
  createInstance() { ${markers ? 'throw new Error("MARKER_createInstance");' : ''} this.instances.push(1); }
  compile() { ${markers ? 'throw new Error("MARKER_compile");' : ''} return { meshes: ${meshExpr}, textures: this.textures }; }
};
`;
}
const P01_PRE = pre(Uint8Array.from(P01.body_bytes));
const P01_HEX = P01.expected.meshes[0].float32_le_hex;
const f32FromHex = (hex) => `new Float32Array(new Uint8Array([${Buffer.from(hex, 'hex').join(',')}]).buffer)`;
const P01_STUB_OK = stub(P01_PRE, `[{ 0: ${f32FromHex(P01_HEX)} }]`);
const runStub = (scaffold, opts) => compileInRealm(scaffold, Uint8Array.from(P01.body_bytes), ZP, ZG, TINY_BOUNDS, deadline(), opts);

// ------------------------------------------------------------------ guards

test('effective heap is measured, not inferred from flags', () => {
  const limit = checkEffectiveHeap();
  assert.ok(limit <= PROFILE_BOUNDS.max_effective_v8_heap_bytes, `run with --max-old-space-size=125 (got ${limit})`);
  failsWith(() => checkEffectiveHeap({ heap_size_limit: 4345298944 }), 'effective_heap_exceeded');
  failsWith(() => checkEffectiveHeap({}), 'effective_heap_unknown');
  failsWith(() => checkLittleEndian('BE'), 'not_little_endian');
});

test('limits may tighten but never loosen; tiny caps are within profile caps', () => {
  checkBoundsWithin(TINY_BOUNDS);
  checkBoundsWithin({ ...PROFILE_BOUNDS, max_ground_dimension: 0, max_primary_smooth_group: 0 });
  for (const k of Object.keys(PROFILE_BOUNDS)) failsWith(() => checkBoundsWithin({ ...PROFILE_BOUNDS, [k]: PROFILE_BOUNDS[k] + 1 }), 'bad_limits');
  failsWith(() => checkBoundsWithin({ ...PROFILE_BOUNDS, extra: 1 }), 'bad_limits');
  failsWith(() => checkBoundsWithin({ ...PROFILE_BOUNDS, max_nodes: 0 }), 'bad_limits');
  failsWith(() => checkBoundsWithin({ ...PROFILE_BOUNDS, max_nodes: 1.5 }), 'bad_limits');
  // A loosened limit is refused by the direct helper before preflight or realm.
  const before = realmStats.created;
  failsWith(() => compileInRealm(SCAFFOLD, Uint8Array.from(P01.body_bytes), ZP, ZG, { ...TINY_BOUNDS, max_mesh_bytes: 1 << 20 }, deadline()), 'bad_limits');
  assert.equal(realmStats.created, before);
});

test('CLI refuses default/odd argv and excess heap before any IO or write', () => {
  const before = fs.readdirSync(PREFIX).length;
  for (const argv of [[], ['--actual'], ['--profile', PROFILE_PATH], ['--actual', '--profile', PROFILE_PATH, '--private-prefix'],
    ['--actual', '--profile', PROFILE_PATH, '--private-prefix', TEST_DIR, '--source', '/x'], ['--actual', '--model', PROFILE_PATH, '--private-prefix', TEST_DIR]]) {
    failsWith(() => main(argv), 'usage');
  }
  failsWith(() => main(['--actual', '--profile', PROFILE_PATH, '--private-prefix', TEST_DIR], { heapStats: { heap_size_limit: 1 << 30 } }), 'effective_heap_exceeded');
  assert.equal(fs.readdirSync(PREFIX).length, before);
});

// ------------------------------------------------------------------ pins

test('frozen pins agree across profile, inventory, source and fixture', () => {
  assert.equal(fixture.task, 'T07.007.014.023');
  assert.equal(fixture.actual_execution_admitted, false);
  assert.equal(fixture.cases.length, 26);
  assert.equal(POSITIVE.length, 10);
  assert.equal(NEGATIVE.length, 16);
  assert.deepEqual(pinOf(P0.fixture.path), { ...FIXTURE_PIN });
  assert.equal(sha256(sourceHeld.bytes), SOURCE_PIN.sha256);
  validateInventory(INVENTORY);
  assert.equal(SPAN_TEXTS.reduce((a, s) => a + s.bytes, 0), CLOSURE_PIN.bytes);
  assert.equal(sha256(Buffer.from(SPAN_TEXTS.map((s) => s.text).join(''), 'latin1')), CLOSURE_PIN.sha256);
  assert.ok(SCAFFOLD.startsWith(PRELUDE) && SCAFFOLD.length === PRELUDE.length + CLOSURE_PIN.bytes);
  // Unused methods and provenance boundaries are retained/excluded as pinned.
  for (const anchor of ['compileAtFrame(frame)', 'getStruct', 'readInt64', 'function slerpQuat', 'var gl_matrix_default = exports;']) assert.ok(SCAFFOLD.includes(anchor), anchor);
  for (const absent of ['loadModels(models, ground)', 'mergeMeshes(objects, bufferSize)', 'case "rsm":']) assert.ok(!SCAFFOLD.includes(absent), absent);
  for (const c of fixture.cases) assert.equal(sha256(Uint8Array.from(c.body_bytes)), c.body_sha256, c.id);
});

test('real profile metadata validates completely without opening the body', () => {
  const v = validateProfile(realProfile());
  assert.deepEqual(v.resources, { ...FROZEN.resource_expected });
  assert.ok(Object.is(v.placement.rotation[0], -0));
  assert.deepEqual(v.ground, { width: 200, height: 200 });
  assert.equal(v.body.bytes, 19113);
  // Tight author limits refuse the real totals before any body is opened.
  failsWith(() => validateProfile(realProfile(), { limits: TINY_BOUNDS }), 'over_cap');
});

test('profile schema/value/sum/identity/scalar mutations are rejected', () => {
  const bad = (edit, code = 'profile_schema') => { const p = realProfile(); edit(p); failsWith(() => validateProfile(p), code); };
  bad((p) => { p.profile_admits_execution = true; });
  bad((p) => { p.extra = 1; });
  bad((p) => { const { task, ...rest } = p; Object.keys(p).forEach((k) => delete p[k]); Object.assign(p, rest, { task }); });
  bad((p) => { p.model_index = 703; });
  bad((p) => { p.group_index = 36; });
  bad((p) => { p.placement.rotation[0] = 0; }); // negative zero lost
  bad((p) => { p.placement.rotation[1] = { number: '-0' }; }); // tag outside its lane
  bad((p) => { p.placement.position[0] = { number: '63.42008666992187' }; });
  bad((p) => { p.placement.rotation[0] = { number: '-0', extra: 1 }; });
  bad((p) => { p.placement.scale[0] = -0.096 * 5; }); // second division state differs
  bad((p) => { p.ground.width = 199; });
  bad((p) => { p.expected_static_structure.nodes[1].faces = 264; });
  bad((p) => { p.expected_static_structure.nodes[0].mat3[1] = -0; });
  bad((p) => { p.expected_static_structure.nodes.reverse(); });
  bad((p) => { p.resource_expected.principal_typed_bytes += 4; });
  bad((p) => { p.bounds.max_mesh_bytes = 262144; });
  bad((p) => { p.bounds.per_vm_timeout_ms = 400; }); // fixed, even when tighter
  bad((p) => { p.source.identity[1] = '020430727'; });
  bad((p) => { p.body.identity[6] = '2'; });
  bad((p) => { p.body.identity[0] = '18446744073709551616'; });
  bad((p) => { p.body.sha256 = '0'.repeat(64); });
  bad((p) => { p.body.path = p.body.path.replace('body-0911', 'body-0912'); });
  bad((p) => { p.body.path = `${p.body.path}/../body-0911.bin`; });
  bad((p) => { p.inventory.bytes += 1; });
  bad((p) => { p.source_closure_sha256 = SPANS[0].sha256; });
  bad((p) => { p.independent_preflight_provenance.bytes += 1; });
  bad((p) => { p.identity_fields.reverse(); });
});

test('span reconstruction rejects shifted pins, changed bytes and inventory drift', () => {
  const src = Buffer.from(sourceHeld.bytes);
  failsWith(() => extractSpans(src, SPANS.map((s, i) => (i === 2 ? { ...s, offset: s.offset + 1 } : s))), 'span_lines');
  failsWith(() => extractSpans(src, SPANS.map((s, i) => (i === 4 ? { ...s, LF_end: s.LF_end - 1 } : s))), 'span_lines');
  const changed = Buffer.from(src); changed[SPANS[4].offset + 100] ^= 1;
  failsWith(() => extractSpans(changed), 'span_sha');
  const high = Buffer.from(src); high[SPANS[1].offset + 10] = 0xc3;
  failsWith(() => extractSpans(high), 'span_not_ascii');
  failsWith(() => extractSpans(src.subarray(0, src.length - 1)), 'source_shape');
  failsWith(() => extractSpans(src, SPANS.slice(0, 4)), 'closure_sha');
  const inv = JSON.parse(JSON.stringify(INVENTORY)); inv.executable_closure[3].sha256 = '0'.repeat(64);
  failsWith(() => validateInventory(inv), 'inventory_schema');
  const inv2 = JSON.parse(JSON.stringify(INVENTORY)); inv2.executable_closure_order.reverse();
  failsWith(() => validateInventory(inv2), 'inventory_schema');
});

// ------------------------------------------------------------------ fixture

test('copied source reproduces all 10 authored meshes byte-for-byte', () => {
  for (const c of POSITIVE) {
    const before = realmStats.created;
    const out = compileInRealm(SCAFFOLD, Uint8Array.from(c.body_bytes), c.placement, c.ground, TINY_BOUNDS, deadline());
    assert.equal(realmStats.created, before + 1, 'one fresh realm per compile');
    meshMatches(out, c);
    // Observed emitted bounds agree with the reference's emitted (not all-vertex) bounds.
    c.expected.reference_geometry.nodes.forEach((n) => {
      const ob = out.observed_emitted_bounds[n.node_index];
      assert.deepEqual([...ob.min, ...ob.max].map((x) => x + 0), [...n.emitted_vertex_bounds.min, ...n.emitted_vertex_bounds.max].map((x) => x + 0), `${c.id} bounds`);
    });
  }
  // The unused-vertex case keeps emitted bounds distinct from all-vertex reference bounds.
  const p09 = caseById.get('P09_unused_fourth_vertex').expected.reference_geometry.nodes[0];
  assert.notDeepEqual(p09.all_vertex_bounds, p09.emitted_vertex_bounds);
});

test('all 16 negative fixture cases refuse before any realm with the independent error', () => {
  for (const c of NEGATIVE) {
    refused(() => compileInRealm(SCAFFOLD, Uint8Array.from(c.body_bytes), c.placement, c.ground, TINY_BOUNDS, deadline()), c.expected.independent_reader_error);
  }
});

test('signed zero and single-lane changes are discriminated by bytes and hashes', () => {
  const hex = P01_HEX;
  const zeroLane = [...Array(hex.length / 8).keys()].find((i) => hex.slice(i * 8, i * 8 + 8) === '00000000');
  assert.notEqual(zeroLane, undefined);
  const flipped = hex.slice(0, zeroLane * 8) + '00000080' + hex.slice(zeroLane * 8 + 8);
  const out = runStub(stub(P01_PRE, `[{ 0: ${f32FromHex(flipped)} }]`));
  assert.equal(out.meshes[0].float32_le_hex, flipped);
  assert.notEqual(out.meshes[0].sha256, P01.expected.meshes[0].sha256);
  assert.equal(out.copy_sha256, P01.body_sha256);
  // Mocked PASS: lifecycle only, never compile evidence.
  assert.equal(runStub(P01_STUB_OK).meshes[0].sha256, P01.expected.meshes[0].sha256);
});

// ------------------------------------------------------------------ preflight controls

test('authored writer reproduces fixture bytes; equivalent encodings compile identically', () => {
  const p = P01_PRE.nodes[0].raw;
  const rebuilt = rsm({
    animLen: P01_PRE.animLen, alpha: Math.round(P01_PRE.alpha * 255), fps: P01_PRE.frameRatePerSecond, globals: [...P01_PRE.unused_global_names], volume: 0,
    nodes: [{ name: P01_PRE.nodes[0].name, textures: [...P01_PRE.nodes[0].textures], vertices: p.vertices, uvs: p.uvs.map((u) => [...u.color, ...u.uv]),
      faces: p.faces.map((f) => ({ v: f.vertidx, t: f.tvertidx, tex: f.texid, pad: f.padding, twoSide: f.twoSide, group: f.smoothGroup, len: f.record_bytes })) }],
  });
  assert.deepEqual(Buffer.from(rebuilt), Buffer.from(P01.body_bytes));
  const variant = (over) => rsm({
    magic: over.magic, animLen: over.animLen ?? P01_PRE.animLen, alpha: Math.round(P01_PRE.alpha * 255), fps: P01_PRE.frameRatePerSecond, globals: [...P01_PRE.unused_global_names], volume: over.volume === 'absent' ? undefined : 0,
    nodes: [{ name: over.name ?? P01_PRE.nodes[0].name, textures: over.textures ?? [...P01_PRE.nodes[0].textures], vertices: p.vertices, uvs: p.uvs.map((u) => [...u.color, ...u.uv]),
      faces: p.faces.map((f) => ({ v: f.vertidx, t: f.tvertidx, tex: f.texid, pad: f.padding, twoSide: 1, group: f.smoothGroup, len: over.len ?? 24 })) }],
  });
  // GRSX, absent optional volume count at exact EOF, nonzero animLen, extra smooth groups,
  // uninterpreted face bytes, twoSide and a NUL-terminated name interval do
  // not enter the mesh lanes or texture names.
  const nulName = Buffer.concat([Buffer.from(P01_PRE.nodes[0].textures[0], 'latin1'), Buffer.from([0]), Buffer.from('junk')]);
  for (const over of [{ magic: 'GRSX' }, { volume: 'absent' }, { animLen: 999 }, { len: 28 }, { len: 32 }, { len: 44 }, { textures: [nulName] }]) {
    const out = compileInRealm(SCAFFOLD, variant(over), ZP, ZG, TINY_BOUNDS, deadline());
    meshMatches(out, P01);
  }
  // Latin1 names survive the bridge byte-for-byte.
  const latin = Buffer.from([0x61, 0xe9, 0x5c, 0xff, 0x2e, 0x62]);
  const out = compileInRealm(SCAFFOLD, variant({ textures: [latin] }), ZP, ZG, TINY_BOUNDS, deadline());
  assert.deepEqual(out.textures, [latin.toString('latin1')]);
  assert.equal(out.meshes[0].float32_le_hex, P01_HEX);
});

test('malformed/oversized bodies and finite-subset violations refuse before any realm', () => {
  const ok = rsm({ nodes: [{}] });
  pre(ok);
  const run = (body, detail, limits = TINY_BOUNDS) => refused(() => compileInRealm(SCAFFOLD, body, ZP, ZG, limits, deadline()), detail);
  run(rsm({ nodes: [{}], trailing: Buffer.from([1]) }), 'short interval');
  run(rsm({ nodes: [{}], volume: 0, trailing: Buffer.from([1]) }), 'trailing bytes');
  run(rsm({ nodes: [{}], volume: 1 }), 'count volume boxes');
  run(rsm({ nodes: [{}], shade: 1 }), 'unsupported shadeType');
  run(rsm({ nodes: [{}], shade: 3 }), 'model header');
  run(rsm({ nodes: [{}], animLen: -1 }), 'model header');
  run(rsm({ nodes: [{}], fps: 0 }), 'model header');
  run(rsm({ nodes: [{}], ver: [2, 4] }), 'signature/version');
  run(rsm({ nodes: [] }), 'no nodes');
  run(rsm({ nodes: [{}, {}, {}] }), 'count nodes');
  run(rsm({ nodes: [{ name: 'a' }, { name: 'a' }] }), 'empty/duplicate node name');
  run(rsm({ nodes: [{ name: '' }] }), 'empty/duplicate node name');
  run(rsm({ nodes: [{ name: 'a' }, { name: 'b', parent: 'a' }] }), 'parented node');
  run(rsm({ nodes: [{ mat3: [1, 0, 0, 0, 2, 0, 0, 0, 1] }] }), 'non-identity mat3');
  run(rsm({ nodes: [{ mat3: [1, -0, 0, 0, 1, 0, 0, 0, 1] }] }), 'non-identity mat3');
  run(rsm({ nodes: [{ offset: [0, -0, 0] }] }), 'nonzero offset');
  run(rsm({ nodes: [{ offset: [0, 1, 0] }] }), 'nonzero offset');
  run(rsm({ nodes: [{ textures: [] }] }), 'empty/duplicate node texture key');
  run(rsm({ nodes: [{ textures: Array.from({ length: 9 }, (_, i) => `${i}`) }] }), 'count node textures');
  run(rsm({ globals: Array.from({ length: 9 }, (_, i) => `${i}`), nodes: [{}] }), 'count global texture strings');
  run(rsm({ nodes: [{ vertices: [] }] }), 'no vertices');
  run(rsm({ nodes: [{ faces: [] }] }), 'no faces');
  run(rsm({ nodes: [{ uvs: Array(9).fill([0, 0, 0, 0, 0, 0]) }] }), 'count uvs');
  run(rsm({ nodes: [{ faces: Array(9).fill({}) }] }), 'count faces');
  run(rsm({ nodes: [{ faces: [{ len: 26 }] }] }), 'face record length');
  run(rsm({ nodes: [{ faces: [{ len: 68 }] }] }), 'face record length');
  run(rsm({ nodes: [{ faces: [{ len: 36 }] }] }), 'face record length', { ...TINY_BOUNDS, max_face_record_bytes: 32 });
  run(rsm({ nodes: [{ faces: [{ group: -1 }] }] }), 'smooth group outside compiled32');
  run(rsm({ nodes: [{ faces: [{ group: 5 }] }] }), 'smooth group over profile cap', { ...TINY_BOUNDS, max_primary_smooth_group: 4 });
  run(rsm({ nodes: [{ vertices: [[0, 0, 0], [1e6, 0, 0], [0, 1.5e6, 0]] }] }), 'excess raw scalar');
  run(rsm({ nodes: [{ vertices: [[0, 0, 0], [Infinity, 0, 0], [0, 1, 0]] }] }), 'nonfinite raw float');
  run(rsm({ nodes: [{ uvs: [[0, 0, 0, 0, NaN, 0], [0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0]] }] }), 'nonfinite raw float');
  run(rsm({ nodes: [{}], fps: 2e6 }), 'excess raw scalar');
  run(rsm({ nodes: [{ keys: [0, 0, 0, 1] }] }), 'count texture key groups');
  run(rsm({ nodes: [{ name: 'x'.repeat(65) }] }), 'count string');
  run(new Uint8Array(0), 'encoded cap/type');
  run(new Uint8Array(4097), 'encoded cap/type');
  run(rsm({ nodes: [{}] }).subarray(0, 40), 'short interval');
  refused(() => compileInRealm(SCAFFOLD, Buffer.from(ok).toString('latin1'), ZP, ZG, TINY_BOUNDS, deadline()), 'encoded cap/type');
  refused(() => compileInRealm(SCAFFOLD, new Proxy(ok, {}), ZP, ZG, TINY_BOUNDS, deadline()), 'encoded cap/type');
});

test('resource budgets (principal typed, smooth visits, mesh, result) refuse before any realm', () => {
  const body = caseById.get('P08_two_unparented_roots').body_bytes;
  const p = pre(Uint8Array.from(body));
  assert.equal(p.resources.mesh_bytes, 108 * p.nodes.reduce((a, n) => a + n.faces, 0));
  const tight = (k, v, detail) => refused(() => compileInRealm(SCAFFOLD, Uint8Array.from(body), ZP, ZG, { ...TINY_BOUNDS, [k]: v }, deadline()), detail);
  tight('max_principal_typed_bytes', p.resources.principal_typed_bytes - 1, 'principal typed budget');
  tight('max_smooth_face_visits', p.resources.smooth_face_visits - 1, 'smooth face visit budget');
  tight('max_mesh_bytes', p.resources.mesh_bytes - 1, 'mesh budget');
  tight('max_result_bytes', p.resources.result_estimate_bytes - 1, 'result budget');
  // Exactly-at-limit is admitted (counted before allocation, no off-by-one).
  const out = compileInRealm(SCAFFOLD, Uint8Array.from(body), ZP, ZG, { ...TINY_BOUNDS, max_mesh_bytes: p.resources.mesh_bytes, max_smooth_face_visits: p.resources.smooth_face_visits, max_principal_typed_bytes: p.resources.principal_typed_bytes }, deadline());
  meshMatches(out, caseById.get('P08_two_unparented_roots'));
  // Full-profile formula on the frozen actual structure (metadata only).
  const st = FROZEN.expected_static_structure.nodes;
  assert.equal(st.reduce((a, n) => a + 120 * n.faces + 12 * n.vertices + 12 * n.primary_smooth_groups.length * n.vertices, 0), 73668);
  assert.equal(st.reduce((a, n) => a + n.primary_smooth_groups.length * n.vertices * n.faces, 0), 438600);
});

test('placement and ground values are validated before any realm', () => {
  const body = Uint8Array.from(P01.body_bytes);
  const pl = (edit, detail, ground = ZG) => { const p = JSON.parse(JSON.stringify(ZP)); edit(p); refused(() => compileInRealm(SCAFFOLD, body, p, ground, TINY_BOUNDS, deadline()), detail); };
  pl((p) => { p.position[0] = NaN; }, 'nonfinite placement');
  pl((p) => { p.rotation[2] = Infinity; }, 'nonfinite placement');
  pl((p) => { p.scale[0] = 1e6 + 1; }, 'excess placement scalar');
  pl((p) => { p.scale[2] = -0; }, 'zero placement scale');
  pl((p) => { p.rotation[0] = { number: '-0' }; }, 'placement rotation non-number scalar');
  pl((p) => { p.position[1] = '1'; }, 'placement position non-number scalar');
  pl((p) => { p.position.push(0); }, 'placement position shape');
  pl((p) => { p.scale = new Proxy([1, 1, 1], {}); }, 'placement scale shape');
  pl(() => {}, 'ground width', { width: 4097, height: 0 });
  pl(() => {}, 'ground height', { width: 0, height: -1 });
  pl(() => {}, 'ground width', { width: 1.5, height: 0 });
  refused(() => preflightModel(body, ZP, { width: 1, height: 0 }, { ...TINY_BOUNDS, max_ground_dimension: 0 }), 'ground width');
});

// ------------------------------------------------------------------ realm

test('direct helper preflights the body before evaluating a handwritten stub', () => {
  const marker = `${PRELUDE} throw new Error("stub evaluated");`;
  for (const c of NEGATIVE) refused(() => compileInRealm(marker, Uint8Array.from(c.body_bytes), c.placement, c.ground, TINY_BOUNDS, deadline()), c.expected.independent_reader_error);
  refused(() => compileInRealm(marker, new Uint8Array(PROFILE_BOUNDS.max_body_bytes), ZP, ZG, PROFILE_BOUNDS, deadline()), 'signature/version');
  refused(() => compileInRealm(marker, new Uint8Array(PROFILE_BOUNDS.max_body_bytes + 1), ZP, ZG, PROFILE_BOUNDS, deadline()), 'encoded cap/type');
  failsWith(() => compileInRealm(marker, Uint8Array.from(P01.body_bytes), ZP, ZG, TINY_BOUNDS, deadline()), 'vm_error');
  failsWith(() => compileInRealm(null, Uint8Array.from(P01.body_bytes), ZP, ZG, TINY_BOUNDS, deadline()), 'bad_scaffold');
  failsWith(() => runStub(P01_STUB_OK, { timeoutMs: 101 }), 'over_cap');
  failsWith(() => runStub(P01_STUB_OK, { heapStats: { heap_size_limit: 1 << 30 } }), 'effective_heap_exceeded');
  failsWith(() => runStub(P01_STUB_OK, { endianness: 'BE' }), 'not_little_endian');
});

test('timeouts and command deadlines are distinct observer failures', () => {
  failsWith(() => runStub(`${PRELUDE} for(;;){}`), 'vm_timeout');
  failsWith(() => runStub(stub(P01_PRE, '(function(){ for(;;){} })()')), 'vm_timeout');
  assert.throws(() => runStub(stub(P01_PRE, '(function(){ throw new RangeError("bad"); })()')), (e) => e.code === 'compile_error' && /RangeError/.test(e.message));
  let calls = 0;
  const counting = makeDeadline(10000, () => { calls++; return 0; });
  compileInRealm(SCAFFOLD, Uint8Array.from(P01.body_bytes), ZP, ZG, TINY_BOUNDS, counting);
  const total = calls;
  for (let k = 1; k < total; k++) {
    let n = 0;
    const d = makeDeadline(10000, () => (++n > k ? 20000 : 0));
    failsWith(() => compileInRealm(SCAFFOLD, Uint8Array.from(P01.body_bytes), ZP, ZG, TINY_BOUNDS, d), 'deadline_exceeded');
  }
});

test('realm has no host globals, console is deleted and code generation is disabled', () => {
  const probe = stub(P01_PRE, `[{ 0: ${f32FromHex(P01_HEX)} }]`, { definitions: `
if (typeof process !== "undefined" || typeof require !== "undefined" || typeof Buffer !== "undefined" || typeof console !== "undefined" || typeof setTimeout !== "undefined") throw new Error("host global");
if (self !== globalThis) throw new Error("self");
if (typeof CodepageManager !== "undefined" || typeof Struct !== "undefined") throw new Error("bound");
` });
  runStub(probe);
  assert.throws(() => runStub(stub(P01_PRE, '[(0, eval)("1")]')), (e) => e.code === 'compile_error' && /EvalError/.test(e.message));
  assert.throws(() => runStub(stub(P01_PRE, '[new Function("return 1")()]')), (e) => e.code === 'compile_error' && /EvalError/.test(e.message));
  assert.throws(() => runStub(stub(P01_PRE, '[WebAssembly.compile]')), (e) => e.code === 'compile_error');
  // Unbound unused readers refuse instead of acquiring modules.
  const r = new BinaryReaderProbe();
  assert.throws(() => runStub(r.scaffold('new BinaryReader(new Uint8Array(8)).readString(1)')), (e) => e.code === 'compile_error' && /CodepageManager/.test(e.message));
  assert.throws(() => runStub(r.scaffold('new BinaryReader(new Uint8Array(8)).getStruct({})')), (e) => e.code === 'compile_error' && /Struct/.test(e.message));
  assert.throws(() => runStub(r.scaffold('new BinaryReader(new Uint8Array([255, 255, 255, 255, 255, 255, 255, 127])).readInt64()')), (e) => e.code === 'compile_error' && /console/.test(e.message));
});
// Uses the real copied scaffold, then exercises an unused reader in the call phase.
class BinaryReaderProbe {
  scaffold(expr) { return `${SCAFFOLD}\nvar __real = RSM; RSM = class extends __real { compile() { ${expr}; return super.compile(); } };\n`; }
}

test('spoofed brands, extents, nonfinite lanes and lifecycle gates are refused', () => {
  const bad = (meshExpr, code, opts) => failsWith(() => runStub(stub(P01_PRE, meshExpr, opts)), code);
  const good = f32FromHex(P01_HEX);
  bad(`[{ 0: Array.from(${good}) }]`, 'compile_error');
  bad(`[{ 0: Object.assign(Object.create(Float32Array.prototype), { length: 27 }) }]`, 'compile_error');
  bad(`[{ 0: (function(){ var a = ${good}; var o = { length: 27, buffer: a.buffer, byteOffset: 0 }; o[Symbol.toStringTag] = "Float32Array"; return o; })() }]`, 'compile_error');
  bad(`[{ 0: new Float32Array(new ArrayBuffer(112), 4, 27) }]`, 'compile_error');
  bad(`[{ 0: new Float32Array(new ArrayBuffer(112), 0, 27) }]`, 'compile_error');
  bad(`[{ 0: new Float64Array(27) }]`, 'compile_error');
  bad(`[{ 0: (function(){ var a = ${good}; a[4] = NaN; return a; })() }]`, 'compile_error');
  bad(`[{ 0: (function(){ var a = ${good}; a[8] = Infinity; return a; })() }]`, 'compile_error');
  bad(`[{ 0: new Float32Array(26) }]`, 'compile_error');
  bad(`[{ 0: new Float32Array(18) }]`, 'mesh_shape');
  bad(`[{ 1: ${good} }]`, 'mesh_shape');
  bad(`[{ 0: ${good}, 1: new Float32Array(0) }]`, 'mesh_shape');
  bad(`[{ 0: ${good} }, { 0: ${good} }]`, 'mesh_shape');
  bad(`[{ 0: new Float32Array(9 * 1000) }]`, 'compile_error'); // realm mesh byte cap
  bad(`[{ 0: ${good} }]`, 'compile_error', { hasAnimation: 'true' });
  bad(`[{ 0: ${good} }]`, 'compile_error', { instances: '[1]' });
  // Shadowing is now refused in the structure phase, before any lifecycle call.
  bad(`[{ 0: ${good} }]`, 'vm_error', { ctorExtra: 'this.compile = function(){ return { meshes: [], textures: [] }; };' });
  bad(`[{ 0: ${good} }]`, 'structure_mismatch', { ctorExtra: 'this.nodes[0].faces = [{ smoothGroup: 0 }, { smoothGroup: 0 }];' });
  bad(`[{ 0: ${good} }]`, 'structure_mismatch', { ctorExtra: 'this.textures = ["b.bmp"];' });
  bad(`[{ 0: ${good} }]`, 'structure_mismatch', { ctorExtra: 'this.nodes[0].offset = [0, -0, 0];' });
  bad(`[{ 0: ${good} }]`, 'structure_mismatch', { ctorExtra: 'this.nodes[0].rotKeyframes = undefined;' });
});

test('host bridge validation rejects malformed primitive strings', () => {
  const structureText = runStubBridge();
  validateStructure(structureText, P01_PRE, TINY_BOUNDS);
  const okText = JSON.stringify({ v: 1, hasAnimation: false, instances_before: 0, instances_after: 1, textures: ['a.bmp'], meshes: [[['0', 27, P01_HEX]]] });
  validateBridge(okText, P01_PRE, TINY_BOUNDS);
  const mut = (edit, code) => { const o = JSON.parse(okText); edit(o); failsWith(() => validateBridge(JSON.stringify(o), P01_PRE, TINY_BOUNDS), code); };
  const smut = (edit, code) => { const o = JSON.parse(structureText); edit(o); failsWith(() => validateStructure(JSON.stringify(o), P01_PRE, TINY_BOUNDS), code); };
  failsWith(() => validateBridge({ toString: () => okText }, P01_PRE, TINY_BOUNDS), 'bridge_type');
  failsWith(() => validateBridge('{', P01_PRE, TINY_BOUNDS), 'bridge_json');
  failsWith(() => validateBridge(okText + ' '.repeat(TINY_BOUNDS.max_result_bytes), P01_PRE, TINY_BOUNDS), 'result_over_cap');
  failsWith(() => validateStructure(structureText + ' '.repeat(TINY_BOUNDS.max_result_bytes), P01_PRE, TINY_BOUNDS), 'result_over_cap');
  mut((o) => { o.extra = 1; }, 'bridge_shape');
  mut((o) => { o.instances_after = 2; }, 'bridge_lifecycle');
  mut((o) => { o.hasAnimation = 'false'; }, 'bridge_lifecycle');
  mut((o) => { o.meshes[0][0][2] = P01_HEX.toUpperCase(); }, 'mesh_bytes');
  mut((o) => { o.meshes[0][0][2] = P01_HEX.slice(8); }, 'mesh_bytes');
  mut((o) => { o.meshes[0][0][2] = P01_HEX.slice(0, -8) + '0000c07f'; }, 'mesh_nonfinite');
  mut((o) => { o.meshes[0][0][2] = P01_HEX.slice(0, -8) + '0000807f'; }, 'mesh_nonfinite');
  mut((o) => { o.meshes[0][0][1] = 18; }, 'mesh_shape');
  mut((o) => { o.meshes[0][0][0] = 0; }, 'mesh_shape');
  mut((o) => { o.textures = ['A.bmp']; }, 'structure_mismatch');
  smut((o) => { o.extra = 1; }, 'bridge_shape');
  smut((o) => { o.version = '2.3000000000000003'; }, 'structure_mismatch');
  smut((o) => { o.alpha = '1e0'; }, 'bridge_shape');
  smut((o) => { o.nodes[0].mat3[0] = '-0'; }, 'structure_mismatch');
  smut((o) => { o.nodes[0].faces += 1; }, 'structure_mismatch');
  smut((o) => { o.nodes[0].primary_smooth_groups = [...o.nodes[0].primary_smooth_groups, 31]; }, 'structure_mismatch');
  smut((o) => { o.nodes[0].primary_smooth_groups = o.nodes[0].primary_smooth_groups.map(String); }, 'structure_mismatch');
  smut((o) => { delete o.nodes[0].primary_smooth_groups; }, 'bridge_shape');
  smut((o) => { o.textures = ['A.bmp']; }, 'structure_mismatch');
});
// Structure exactly as the real copied constructor reports it for P01.
function runStubBridge() {
  const out = compileInRealm(SCAFFOLD, Uint8Array.from(P01.body_bytes), ZP, ZG, TINY_BOUNDS, deadline());
  assert.deepEqual(out.structure.nodes[0].primary_smooth_groups, [...P01_PRE.nodes[0].primary_smooth_groups]);
  return JSON.stringify(out.structure);
}

// ------------------------------------------------------------------ held inputs

test('held reads reject changed/symlinked/hardlinked/short/extra/identity faults', () => {
  const d = freshDir('held');
  const f = writeOwned(path.join(d, 'a.bin'), Buffer.from('abcdef'));
  const pin = pinOf(f);
  const h = readHeldInput(f, { ...pin, identity: identityOf(fs.lstatSync(f, { bigint: true })) }, 64, deadline(), 't');
  h.recheck('x'); h.close(); failsWith(() => h.recheck('after'), 'descriptor_closed'); h.literalRecheck('closed');
  failsWith(() => readHeldInput(f, { bytes: 6, sha256: '0'.repeat(64) }, 64, deadline(), 't'), 'sha_mismatch');
  failsWith(() => readHeldInput(f, { bytes: 7, sha256: pin.sha256 }, 64, deadline(), 't'), 'size_mismatch');
  failsWith(() => readHeldInput(f, { bytes: 5, sha256: pin.sha256 }, 64, deadline(), 't'), 'size_mismatch');
  failsWith(() => readHeldInput(f, pin, 5, deadline(), 't'), 'input_over_cap');
  failsWith(() => readHeldInput(f, { ...pin, identity: identityOf(fs.lstatSync(f, { bigint: true })).map((v, i) => (i === 1 ? '1' : v)) }, 64, deadline(), 't'), 'identity_mismatch');
  const link = path.join(d, 'link.bin'); fs.symlinkSync(f, link);
  failsWith(() => readHeldInput(link, pin, 64, deadline(), 't'), 'symlink');
  const hard = path.join(d, 'hard.bin'); fs.linkSync(f, hard);
  failsWith(() => readHeldInput(f, pin, 64, deadline(), 't'), 'link_count');
  fs.rmSync(hard);
  failsWith(() => readHeldInput(d, pin, 64, deadline(), 't'), 'not_regular');
  failsWith(() => readHeldInput('rel/a.bin', pin, 64, deadline(), 't'), 'bad_path');
  // Short and extra reads on a file whose size changes under the held descriptor.
  const read = fs.readSync;
  fs.readSync = (fd, buf, off, len, pos) => (pos === 0 ? read(fd, buf, off, 3, pos) : pos === 3 ? 0 : read(fd, buf, off, len, pos));
  try { failsWith(() => readHeldInput(f, pin, 64, deadline(), 't'), 'short_read'); } finally { fs.readSync = read; }
  fs.readSync = (fd, buf, off, len, pos) => (pos === 6 ? 1 : read(fd, buf, off, len, pos));
  try { failsWith(() => readHeldInput(f, pin, 64, deadline(), 't'), 'extra_bytes'); } finally { fs.readSync = read; }
  // Ancestor symlink is refused before reading its owned leaf.
  const real = path.join(d, 'real'); fs.mkdirSync(real, { mode: 0o700 }); const leaf = writeOwned(path.join(real, 'leaf'), 'xyz');
  const alias = path.join(d, 'alias'); fs.symlinkSync(real, alias);
  failsWith(() => readHeldInput(path.join(alias, 'leaf'), pinOf(leaf), 64, deadline(), 't'), 'input_ancestor');
});

// ------------------------------------------------------------------ observer lifecycle

// Authored tiny profile: same closed schema, real source/inventory/fixture
// pins, an owned body-0911.bin holding P08's authored bytes. Its expected
// structure is derived from the preflight (lifecycle wiring only; mesh bytes
// are compared to the independent fixture below).
const AUTHORED = caseById.get('P08_two_unparented_roots');
function authoredProfile(dir, edit = () => {}) {
  const bodyPath = writeOwned(path.join(dir, 'body-0911.bin'), Buffer.from(AUTHORED.body_bytes));
  const p = pre(Uint8Array.from(AUTHORED.body_bytes));
  const expected = {
    version: 2.3, animLen: p.animLen, shadeType: p.shadeType, alpha: p.alpha, frameRatePerSecond: p.frameRatePerSecond, unused_global_names: [...p.unused_global_names],
    volume_boxes: p.volume_boxes, consumed_bytes: p.consumed_bytes,
    nodes: p.nodes.map(({ raw, mesh_layout, ...n }) => JSON.parse(JSON.stringify(n))),
  };
  const resources = { mesh_bytes: p.resources.mesh_bytes, principal_typed_bytes: p.resources.principal_typed_bytes, principal_typed_bytes_if32groups: p.resources.principal_typed_bytes_if32groups, smooth_face_visits: p.resources.smooth_face_visits };
  const prof = realProfile();
  prof.body = { path: bodyPath, bytes: AUTHORED.body_bytes.length, sha256: AUTHORED.body_sha256, identity: identityOf(fs.lstatSync(bodyPath, { bigint: true })) };
  prof.placement = JSON.parse(JSON.stringify(AUTHORED.placement));
  prof.ground = { ...AUTHORED.ground };
  prof.expected_static_structure = JSON.parse(JSON.stringify(expected));
  prof.resource_expected = { ...resources };
  edit(prof, dir);
  const file = writeOwned(path.join(dir, 'PROFILE_AUTHORED.json'), JSON.stringify(prof, null, 1));
  const frozen = { ...FROZEN, body: { bytes: AUTHORED.body_bytes.length, sha256: AUTHORED.body_sha256 }, placement: AUTHORED.placement, ground: AUTHORED.ground, expected_static_structure: JSON.parse(JSON.stringify(expected)), resource_expected: resources };
  return { file, dir, bodyPath, pins: { profile: pinOf(file), frozen } };
}
const runAuthored = (a, extra = {}) => runObserver({ profilePath: a.file, prefix: extra.prefix ?? a.dir, pins: a.pins, limits: TINY_BOUNDS, clock: extra.clock, heapStats: extra.heapStats });

test('authored run publishes PASS with exact meshes, pins and private modes', () => {
  const a = authoredProfile(freshDir('pass'));
  const out = runAuthored(a);
  assert.equal(out.status, 'PASS', JSON.stringify(out));
  assert.equal(fs.statSync(out.dir).mode & 0o777, 0o700);
  const resultPath = path.join(out.dir, 'result.json');
  assert.equal(fs.statSync(resultPath).mode & 0o777, 0o600);
  const text = fs.readFileSync(resultPath);
  assert.equal(sha256(text), out.result.sha256);
  assert.ok(text.length <= TINY_BOUNDS.max_result_bytes);
  const r = JSON.parse(text);
  assert.equal(r.status, 'PASS');
  meshMatches(r, AUTHORED);
  assert.deepEqual(r.spans, SPANS.map((s) => ({ ...s })));
  assert.equal(r.source.sha256, SOURCE_PIN.sha256);
  assert.equal(r.inventory.sha256, INVENTORY_PIN.sha256);
  assert.equal(r.profile.sha256, a.pins.profile.sha256);
  assert.equal(r.body.sha256, AUTHORED.body_sha256);
  assert.equal(r.body.encoded_copy_sha256, AUTHORED.body_sha256);
  assert.equal(r.scaffold.sha256, sha256(SCAFFOLD));
  assert.equal(sha256(fs.readFileSync(path.join(out.dir, 'scaffold.js'))), sha256(SCAFFOLD));
  assert.deepEqual(r.gates, { structure_matched_before_lifecycle: true, hasAnimation: false, instances_before: 0, instances_after: 1, compileAtFrame_used: false, source_methods_patched: false });
  assert.ok(!text.includes('"body_bytes"') && !text.includes(Buffer.from(AUTHORED.body_bytes).toString('hex').slice(0, 64)), 'no body bytes published');
});

test('every command-deadline point fails without publishing a PASS', () => {
  const a = authoredProfile(freshDir('deadline'));
  let calls = 0;
  const counted = runAuthored(a, { clock: () => { calls++; return 0; } });
  assert.equal(counted.status, 'PASS');
  const total = calls;
  const points = new Set([1, 2, 3, 5, 8, 13, Math.floor(total / 3), Math.floor(total / 2), total - 5, total - 3, total - 2]);
  for (const k of points) {
    let n = 0;
    const out = runAuthored(a, { clock: () => (++n > k ? 20000 : 0) });
    assert.equal(out.status, 'FAIL', `k=${k}/${total}`);
    assert.equal(out.code, 'deadline_exceeded', `k=${k}`);
    assert.equal(fs.existsSync(path.join(out.dir, 'result.json')), false, `k=${k}`);
    assert.equal(JSON.parse(fs.readFileSync(path.join(out.dir, 'failure.json'))).timeout, true);
  }
  let m = 0;
  assert.equal(runAuthored(a, { clock: () => (++m > total - 1 ? 20000 : 0) }).status, 'FAIL');
  assert.equal(sha256(fs.readFileSync(path.join(counted.dir, 'result.json'))), counted.result.sha256);
});

test('body/profile/source pin faults fail with preserved evidence and no PASS', () => {
  const failing = (name, edit, code, after = () => {}, stage) => {
    const d = freshDir(name);
    const a = authoredProfile(d, edit);
    after(d, a);
    const out = runAuthored(a);
    assert.equal(out.status, 'FAIL', name);
    assert.equal(out.code, code, `${name}: ${JSON.stringify(out)}`);
    if (stage) assert.equal(out.stage, stage, name);
    assert.equal(fs.existsSync(path.join(out.dir, 'result.json')), false);
    const f = JSON.parse(fs.readFileSync(path.join(out.dir, 'failure.json')));
    assert.ok(!JSON.stringify(f).includes('body_bytes'));
    return f;
  };
  failing('identity', (p) => { p.body.identity[1] = '1'; }, 'identity_mismatch', undefined, 'body');
  failing('content', () => {}, 'identity_mismatch', (d) => { const f = path.join(d, 'body-0911.bin'); const b = fs.readFileSync(f); b[60] ^= 1; fs.writeFileSync(f, b); }, 'body');
  failing('symlink_body', () => {}, 'symlink', (d) => { const f = path.join(d, 'body-0911.bin'); fs.renameSync(f, path.join(d, 'moved.bin')); fs.symlinkSync(path.join(d, 'moved.bin'), f); });
  failing('hardlink_body', () => {}, 'link_count', (d) => { fs.linkSync(path.join(d, 'body-0911.bin'), path.join(d, 'second.bin')); });
  const f2 = failing('profile_bytes', () => {}, 'sha_mismatch', (d, a) => { const b = fs.readFileSync(a.file); b[b.length - 2] = 0x20; fs.writeFileSync(a.file, b); }, 'profile');
  assert.equal(f2.source, null);
  failing('schema', (p) => { p.expected_static_structure.nodes.reverse(); }, 'profile_schema');
  failing('sums', (p) => { p.resource_expected.mesh_bytes += 4; }, 'profile_schema');
  failing('source_identity', (p) => { p.source.identity[3] = '1'; }, 'identity_mismatch', undefined, 'source');
  failing('inventory_identity', (p) => { p.inventory.identity[4] = '1'; }, 'identity_mismatch', undefined, 'inventory');
  // Body that preflights but differs from the frozen expected structure.
  failing('structure', (p) => { p.expected_static_structure.animLen += 1; }, 'profile_schema');
});

test('preflight/structure mismatch between body and profile fails before any realm', () => {
  const p = pre(Uint8Array.from(AUTHORED.body_bytes));
  const expected = { version: 2.3, animLen: p.animLen, shadeType: 2, alpha: p.alpha, frameRatePerSecond: p.frameRatePerSecond, unused_global_names: [...p.unused_global_names], volume_boxes: 0, consumed_bytes: p.consumed_bytes, nodes: p.nodes.map(({ raw, mesh_layout, ...n }) => ({ ...n })) };
  const res = { mesh_bytes: p.resources.mesh_bytes, principal_typed_bytes: p.resources.principal_typed_bytes, principal_typed_bytes_if32groups: p.resources.principal_typed_bytes_if32groups, smooth_face_visits: p.resources.smooth_face_visits };
  checkStructure(p, expected, res);
  failsWith(() => checkStructure(p, { ...expected, nodes: [{ ...expected.nodes[0], primary_smooth_groups: [0, 1] }, expected.nodes[1]] }, res), 'structure_mismatch');
  failsWith(() => checkStructure(p, { ...expected, unused_global_names: ['x'] }, res), 'structure_mismatch');
  failsWith(() => checkStructure(p, expected, { ...res, smooth_face_visits: res.smooth_face_visits + 1 }), 'structure_mismatch');
});

test('run directory prefix must be a real private directory', () => {
  const d = freshDir('prefix');
  const a = authoredProfile(d);
  const link = path.join(TEST_DIR, `${seq}-link`);
  fs.symlinkSync(d, link);
  failsWith(() => runAuthored(a, { prefix: link }), 'bad_prefix');
  const open = freshDir('open');
  fs.chmodSync(open, 0o755);
  failsWith(() => runAuthored(a, { prefix: open }), 'bad_prefix');
  failsWith(() => runAuthored(a, { prefix: `${d}/` }), 'bad_prefix');
  failsWith(() => runAuthored(a, { heapStats: { heap_size_limit: 335544320 } }), 'effective_heap_exceeded');
  assert.deepEqual(fs.readdirSync(open), []);
});

test('candidate replacement after close fails without publishing', () => {
  const a = authoredProfile(freshDir('candidate-replacement'));
  const open = fs.openSync, close = fs.closeSync;
  let fdTarget, candidatePath, changed = false;
  fs.openSync = function (file, ...args) {
    const fd = open.call(this, file, ...args);
    if (typeof file === 'string' && file.endsWith('/result.candidate.json')) { fdTarget = fd; candidatePath = file; }
    return fd;
  };
  fs.closeSync = function (fd) {
    const result = close.call(this, fd);
    if (fd === fdTarget && !changed) { changed = true; fs.renameSync(candidatePath, candidatePath + '.original'); writeOwned(candidatePath, '{}\n'); }
    return result;
  };
  let out;
  try { out = runAuthored(a); } finally { fs.openSync = open; fs.closeSync = close; }
  assert.ok(changed);
  assert.equal(out.status, 'FAIL');
  assert.equal(out.code, 'output_identity');
  assert.equal(fs.existsSync(path.join(out.dir, 'result.json')), false);
});

test('published result replaced after linking is dequalified and renamed', () => {
  const a = authoredProfile(freshDir('final-replacement'));
  const link = fs.linkSync;
  let changed = false;
  fs.linkSync = function (from, to) {
    const r = link.call(this, from, to);
    if (to.endsWith('/result.json') && !changed) { changed = true; fs.appendFileSync(from, ' '); }
    return r;
  };
  let out;
  try { out = runAuthored(a); } finally { fs.linkSync = link; }
  assert.ok(changed);
  assert.equal(out.status, 'FAIL');
  assert.equal(fs.existsSync(path.join(out.dir, 'result.json')), false);
  assert.equal(fs.existsSync(path.join(out.dir, 'result.unqualified.json')), true);
});

test('input close failure is sticky and remaining closes are attempted', () => {
  const a = authoredProfile(freshDir('sticky-close'));
  const open = fs.openSync, close = fs.closeSync;
  let profileFd, sourceFd, inventoryFd, profileClosed = false, sourceClosed = false, inventoryClosed = false;
  fs.openSync = function (file, ...args) {
    const fd = open.call(this, file, ...args);
    if (file === a.file) profileFd = fd;
    if (file === P0.source.path) sourceFd = fd;
    if (file === P0.inventory.path) inventoryFd = fd;
    return fd;
  };
  fs.closeSync = function (fd) {
    const result = close.call(this, fd);
    if (fd === profileFd && !profileClosed) { profileClosed = true; throw Object.assign(new Error('owned close fault'), { code: 'EIO' }); }
    if (fd === sourceFd) sourceClosed = true;
    if (fd === inventoryFd) inventoryClosed = true;
    return result;
  };
  let out;
  try { out = runAuthored(a); } finally { fs.openSync = open; fs.closeSync = close; }
  assert.ok(profileClosed && sourceClosed && inventoryClosed);
  assert.equal(out.status, 'FAIL');
  assert.equal(out.code, 'cleanup_failed');
  assert.equal(fs.existsSync(path.join(out.dir, 'result.json')), false);
  const f = JSON.parse(fs.readFileSync(path.join(out.dir, 'failure.json')));
  assert.equal(f.close_errors[0].code, 'EIO');
  assert.equal(f.meshes.length, 3, 'full mesh evidence retained on failure');
});

test('body close failure is a failure even after a returned compile', () => {
  const a = authoredProfile(freshDir('body-close'));
  const open = fs.openSync, close = fs.closeSync;
  let bodyFd, faulted = false;
  fs.openSync = function (file, ...args) { const fd = open.call(this, file, ...args); if (file === a.bodyPath) bodyFd = fd; return fd; };
  fs.closeSync = function (fd) { const r = close.call(this, fd); if (fd === bodyFd && !faulted) { faulted = true; throw Object.assign(new Error('body close'), { code: 'EIO' }); } return r; };
  let out;
  try { out = runAuthored(a); } finally { fs.openSync = open; fs.closeSync = close; }
  assert.ok(faulted);
  assert.equal(out.status, 'FAIL');
  assert.equal(fs.existsSync(path.join(out.dir, 'result.json')), false);
});

test('fresh run directory replacement is refused before first output', () => {
  const a = authoredProfile(freshDir('run-directory-replacement'));
  const mkdir = fs.mkdirSync, open = fs.openSync;
  let runDir, changed = false;
  fs.mkdirSync = function (file, ...args) {
    const result = mkdir.call(this, file, ...args);
    if (typeof file === 'string' && path.basename(file).startsWith('run-')) runDir = file;
    return result;
  };
  fs.openSync = function (file, ...args) {
    if (file === P0.source.path && !changed) { fs.renameSync(runDir, runDir + '.original'); mkdir(runDir, { mode: 0o700 }); changed = true; }
    return open.call(this, file, ...args);
  };
  let out;
  try { out = runAuthored(a); } finally { fs.mkdirSync = mkdir; fs.openSync = open; }
  assert.ok(changed);
  assert.equal(out.status, 'FAIL');
  assert.equal(out.code, 'input_ancestor');
  assert.equal(out.ownership_lost, true);
  assert.deepEqual(fs.readdirSync(runDir), [], 'no scaffold or failure written into the replacement');
  assert.deepEqual(fs.readdirSync(runDir + '.original'), []);
});

test('run-directory ancestor replaced after scaffold output fails publication', () => {
  const a = authoredProfile(freshDir('ancestor-after-scaffold'));
  const open = fs.openSync;
  let runDir, changed = false;
  fs.openSync = function (file, ...args) {
    if (typeof file === 'string' && file === a.bodyPath && !changed) {
      runDir = fs.readdirSync(a.dir).filter((n) => n.startsWith('run-')).map((n) => path.join(a.dir, n)).at(-1);
      fs.renameSync(runDir, runDir + '.moved'); fs.mkdirSync(runDir, { mode: 0o700 }); changed = true;
    }
    return open.call(this, file, ...args);
  };
  let out;
  try { out = runAuthored(a); } finally { fs.openSync = open; }
  assert.ok(changed);
  assert.equal(out.status, 'FAIL');
  assert.equal(out.code, 'input_ancestor');
  assert.equal(fs.existsSync(path.join(runDir + '.moved', 'scaffold.js')), true, 'earlier capture preserved');
  assert.equal(out.ownership_lost, true);
  assert.deepEqual(fs.readdirSync(runDir), [], 'nothing adopted into the replacement');
});

test('combined faults (close failure plus expiring deadline) never publish', () => {
  const a = authoredProfile(freshDir('combined'));
  const open = fs.openSync, close = fs.closeSync;
  let srcFd, faulted = false, n = 0;
  fs.openSync = function (file, ...args) { const fd = open.call(this, file, ...args); if (file === P0.source.path) srcFd = fd; return fd; };
  fs.closeSync = function (fd) { const r = close.call(this, fd); if (fd === srcFd && !faulted) { faulted = true; throw Object.assign(new Error('src close'), { code: 'EIO' }); } return r; };
  let out;
  try { out = runAuthored(a, { clock: () => (++n > 400 ? 20000 : 0) }); } finally { fs.openSync = open; fs.closeSync = close; }
  assert.equal(out.status, 'FAIL');
  assert.ok(['cleanup_failed', 'deadline_exceeded'].includes(out.code), out.code);
  assert.equal(fs.existsSync(path.join(out.dir, 'result.json')), false);
});

test('exclusive outputs never overwrite earlier captures', () => {
  const d = freshDir('exclusive');
  const r = writeExclusive(d, 'x.json', '{}\n');
  assert.equal(fs.statSync(path.join(d, 'x.json')).mode & 0o777, 0o600);
  assert.throws(() => writeExclusive(d, 'x.json', '[]\n'), (e) => e.code === 'EEXIST');
  assert.equal(sha256(fs.readFileSync(path.join(d, 'x.json'))), r.sha256);
  failsWith(() => writeExclusive(d, 'big.json', Buffer.alloc(PROFILE_BOUNDS.max_result_bytes + 1)), 'result_over_cap');
});

// ================================================================== T07.007.014.023.001 corrections

const EIO = (what) => Object.assign(new Error(`injected ${what}`), { code: 'EIO' });
const failureOf = (out) => JSON.parse(fs.readFileSync(path.join(out.dir, 'failure.json')));
// Swaps vm.Script for one filename (fault injection only; never a PASS basis).
function withScriptSwap(filename, code, fn) {
  const Original = vm.Script; let swapped = 0; const seen = [];
  vm.Script = class extends Original {
    constructor(src, opts) { seen.push(opts?.filename); if (opts?.filename === filename) { swapped++; super(code, opts); } else super(src, opts); }
  };
  try { return { value: fn(), swapped, seen }; } finally { vm.Script = Original; }
}

// ------------------------------------------------------------------ 1. creation ownership

test('run directory replaced after its first stat (or before authority) refuses with no local writes', () => {
  for (const k of [1, 2, 3, 4]) {
    const a = authoredProfile(freshDir(`creation-${k}`));
    const lstat = fs.lstatSync, mkdir = fs.mkdirSync;
    let runDir, calls = 0, replaced = false;
    fs.mkdirSync = function (file, ...args) { const r = mkdir.call(this, file, ...args); if (typeof file === 'string' && path.basename(file).startsWith('run-')) runDir = file; return r; };
    fs.lstatSync = function (file, ...args) {
      const r = lstat.call(this, file, ...args);
      if (file === runDir && ++calls === k && !replaced) { fs.renameSync(runDir, `${runDir}.original`); mkdir.call(fs, runDir, { mode: 0o700 }); replaced = true; }
      return r;
    };
    const created = realmStats.created;
    try {
      if (k < 4) assert.throws(() => runAuthored(a), (e) => e instanceof ObserverRefusal && e.code === 'run_directory_ownership', `k=${k}`);
      // After the last creation check, the first authority check owns the refusal.
      else assert.equal(runAuthored(a).ownership_lost, true);
    } finally { fs.lstatSync = lstat; fs.mkdirSync = mkdir; }
    assert.ok(replaced, `k=${k} injection ran`);
    assert.equal(realmStats.created - created, 0);
    assert.deepEqual(fs.readdirSync(runDir), [], `k=${k}: nothing written into the replacement`);
    assert.deepEqual(fs.readdirSync(`${runDir}.original`), [], `k=${k}: original untouched`);
  }
});

// ------------------------------------------------------------------ 2. run ownership vs deadline

test('lost run ownership returns bounded external failure and never writes into the replacement', () => {
  const a = authoredProfile(freshDir('ownership-lost'));
  const open = fs.openSync;
  let runDir, changed = false, n = 0;
  fs.openSync = function (file, ...args) {
    if (file === a.bodyPath && !changed) {
      runDir = fs.readdirSync(a.dir).filter((x) => x.startsWith('run-')).map((x) => path.join(a.dir, x)).at(-1);
      fs.renameSync(runDir, `${runDir}.moved`); fs.mkdirSync(runDir, { mode: 0o700 }); changed = true;
    }
    return open.call(this, file, ...args);
  };
  // Combined: the deadline also expires after the replacement.
  let out;
  try { out = runAuthored(a, { clock: () => (changed && ++n > 3 ? 20000 : 0) }); } finally { fs.openSync = open; }
  assert.ok(changed && n > 3, 'both injections ran');
  assert.equal(out.status, 'FAIL');
  assert.equal(out.ownership_lost, true);
  assert.equal(out.failure_write_error, 'run_directory_ownership_lost');
  assert.ok(JSON.stringify(out.failure_summary).length < 8192, 'bounded summary');
  assert.equal(typeof out.failure_summary.code, 'string');
  assert.deepEqual(fs.readdirSync(runDir), [], 'replacement left empty');
  assert.deepEqual(fs.readdirSync(`${runDir}.moved`), ['scaffold.js'], 'original evidence preserved, no failure.json adopted');
});

test('failure publication after an expired deadline still requires and uses original ownership', () => {
  const a = authoredProfile(freshDir('deadline-owned'));
  let n = 0;
  const out = runAuthored(a, { clock: () => (++n > 40 ? 20000 : 0) });
  assert.equal(out.code, 'deadline_exceeded');
  assert.equal(out.ownership_lost, undefined);
  const f = failureOf(out);
  assert.equal(f.timeout, true);
  assert.equal(fs.existsSync(path.join(out.dir, 'result.json')), false);
});

// ------------------------------------------------------------------ 3. exclusive dequalification

function dequalifyRun(name, prepare, extraHooks = {}) {
  const a = authoredProfile(freshDir(name));
  const link = fs.linkSync, unlink = fs.unlinkSync;
  let changed = false;
  fs.linkSync = function (from, to) {
    const r = link.call(this, from, to);
    if (to.endsWith('/result.json') && !changed) { changed = true; prepare(path.dirname(to)); fs.appendFileSync(from, ' '); }
    return r;
  };
  if (extraHooks.unlink) fs.unlinkSync = function (file) { return extraHooks.unlink(file, () => unlink.call(fs, file)); };
  let out;
  try { out = runAuthored(a); } finally { fs.linkSync = link; fs.unlinkSync = unlink; }
  assert.ok(changed, `${name}: injection ran`);
  assert.equal(out.status, 'FAIL');
  return { out, f: failureOf(out) };
}

test('dequalification preserves an occupied unqualified file and retires only this alias', () => {
  const { out, f } = dequalifyRun('occupied-file', (d) => writeOwned(path.join(d, 'result.unqualified.json'), 'earlier capture\n'));
  assert.equal(fs.readFileSync(path.join(out.dir, 'result.unqualified.json'), 'utf8'), 'earlier capture\n');
  assert.equal(fs.existsSync(path.join(out.dir, 'result.json')), false);
  assert.equal(f.retirement.status, 'retired');
  assert.deepEqual(f.retirement.occupied, ['result.unqualified.json']);
  assert.equal(f.retirement.preserved_as, 'result.unqualified-1.json');
  const kept = fs.lstatSync(path.join(out.dir, 'result.unqualified-1.json')); const cand = fs.lstatSync(path.join(out.dir, 'result.candidate.json'));
  assert.equal(kept.ino, cand.ino, 'preserved alias is this run\'s candidate inode');
});

test('dequalification preserves an occupied unqualified directory', () => {
  const { out, f } = dequalifyRun('occupied-dir', (d) => { fs.mkdirSync(path.join(d, 'result.unqualified.json'), { mode: 0o700 }); writeOwned(path.join(d, 'result.unqualified.json', 'inner'), 'x'); });
  assert.ok(fs.lstatSync(path.join(out.dir, 'result.unqualified.json')).isDirectory());
  assert.deepEqual(fs.readdirSync(path.join(out.dir, 'result.unqualified.json')), ['inner']);
  assert.equal(fs.existsSync(path.join(out.dir, 'result.json')), false);
  assert.equal(f.retirement.status, 'retired');
  assert.equal(f.retirement.preserved_as, 'result.unqualified-1.json');
});

test('a foreign final is left untouched and reported, never retired', () => {
  const { out, f } = dequalifyRun('foreign-final', (d) => { writeOwned(path.join(d, 'foreign.tmp'), 'foreign bytes\n'); fs.renameSync(path.join(d, 'foreign.tmp'), path.join(d, 'result.json')); });
  assert.equal(fs.readFileSync(path.join(out.dir, 'result.json'), 'utf8'), 'foreign bytes\n');
  assert.equal(f.retirement.status, 'foreign_final_untouched');
  assert.equal(out.retirement, 'foreign_final_untouched');
  assert.equal(fs.existsSync(path.join(out.dir, 'result.unqualified.json')), false);
});

test('a retirement IO failure is reported explicitly and never as retired', () => {
  let faulted = false;
  const { out, f } = dequalifyRun('retire-eio', () => {}, { unlink: (file, real) => { if (file.endsWith('/result.json') && !faulted) { faulted = true; throw EIO('unlink'); } return real(); } });
  assert.ok(faulted, 'unlink fault ran');
  assert.equal(f.retirement.status, 'failed');
  assert.ok(f.retirement.errors.some((e) => e.code === 'EIO' && e.during === 'unlink final'));
  assert.equal(out.retirement, 'failed');
  assert.equal(f.retirement.preserved_as, 'result.unqualified.json', 'bytes still preserved exclusively');
  assert.equal(fs.existsSync(path.join(out.dir, 'result.json')), true, 'alias remains; no forced deletion claimed');
});

// ------------------------------------------------------------------ 4. primary errors and sticky diagnostics

test('held-read primary error keeps the close EIO as a diagnostic', () => {
  const d = freshDir('held-primary');
  const f = writeOwned(path.join(d, 'a.bin'), Buffer.from('abcdef'));
  const pin = pinOf(f);
  const read = fs.readSync, open = fs.openSync, close = fs.closeSync;
  let fdT, shorted = false, closed = false;
  fs.openSync = function (file, ...args) { const fd = open.call(this, file, ...args); if (file === f) fdT = fd; return fd; };
  fs.readSync = (fd, buf, off, len, pos) => { if (fd === fdT) { shorted = true; return 0; } return read(fd, buf, off, len, pos); };
  fs.closeSync = function (fd) { const r = close.call(this, fd); if (fd === fdT) { closed = true; throw EIO('close'); } return r; };
  try {
    assert.throws(() => readHeldInput(f, pin, 64, deadline(), 't'), (e) => e.code === 'short_read' && e.closeDiagnostics?.[0]?.code === 'EIO');
  } finally { fs.readSync = read; fs.openSync = open; fs.closeSync = close; }
  assert.ok(shorted && closed, 'both injections ran');
});

test('output write and readback primary errors keep their close EIO diagnostics', () => {
  const d = freshDir('output-primary');
  const write = fs.writeFileSync, close = fs.closeSync, open = fs.openSync;
  let fds = [], wrote = false, closes = 0;
  fs.openSync = function (file, ...args) { const fd = open.call(this, file, ...args); if (typeof file === 'string' && file.startsWith(d)) fds.push(fd); return fd; };
  fs.closeSync = function (fd) { const r = close.call(this, fd); if (fds.includes(fd)) { closes++; throw EIO('close'); } return r; };
  fs.writeFileSync = function (target, ...args) { if (fds.includes(target)) { wrote = true; throw Object.assign(new Error('injected write'), { code: 'ENOSPC' }); } return write.call(this, target, ...args); };
  try {
    assert.throws(() => writeExclusive(d, 'w.json', '{}\n'), (e) => e.code === 'ENOSPC' && e.closeDiagnostics?.[0]?.code === 'EIO');
  } finally { fs.writeFileSync = write; }
  assert.ok(wrote && closes === 1, 'write and close injections ran');
  // Readback: the guard expires inside the readback loop and its close fails.
  const RO = fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW;
  fds = []; closes = 0;
  fs.openSync = function (file, flags, ...args) { const fd = open.call(this, file, flags, ...args); if (typeof file === 'string' && file.startsWith(d) && flags === RO) fds.push(fd); return fd; };
  let g = 0;
  const guard = () => { if (++g === 3) throw new ObserverFailure('deadline_exceeded', 'injected', 'publication'); };
  try {
    assert.throws(() => writeExclusive(d, 'r.json', '{}\n', guard), (e) => e.code === 'deadline_exceeded' && e.closeDiagnostics?.some((x) => x.code === 'EIO'));
  } finally { fs.openSync = open; fs.closeSync = close; }
  assert.ok(g === 3 && closes === 1, 'guard and readback close injections ran');
  // A close failure alone is an explicit output failure, never success.
  fs.closeSync = function (fd) { close.call(this, fd); throw EIO('close'); };
  try { failsWith(() => writeExclusive(d, 'c.json', '{}\n'), 'output_close'); } finally { fs.closeSync = close; }
});

test('VM timeout plus body close EIO keeps timeout:true and the EIO', () => {
  const a = authoredProfile(freshDir('timeout-body-eio'));
  const open = fs.openSync, close = fs.closeSync;
  let bodyFd, faulted = false;
  fs.openSync = function (file, ...args) { const fd = open.call(this, file, ...args); if (file === a.bodyPath) bodyFd = fd; return fd; };
  fs.closeSync = function (fd) { const r = close.call(this, fd); if (fd === bodyFd && !faulted) { faulted = true; throw EIO('body close'); } return r; };
  let res;
  try { res = withScriptSwap('model-geometry-lifecycle.js', 'for(;;){}', () => runAuthored(a)); } finally { fs.openSync = open; fs.closeSync = close; }
  const out = res.value;
  assert.ok(res.swapped === 1 && faulted, 'real VM timeout and body close injection both ran');
  assert.equal(out.code, 'vm_timeout');
  const f = failureOf(out);
  assert.equal(f.timeout, true);
  assert.ok(f.close_errors.some((e) => e.code === 'EIO' && e.during === 'body close'));
  assert.ok(res.seen.includes('model-geometry-cleanup.js'), 'realm cleanup ran on the timeout path');
});

test('returned mesh/body metadata survives a later body recheck failure without body bytes', () => {
  const a = authoredProfile(freshDir('later-recheck'));
  const open = fs.openSync, fstat = fs.fstatSync;
  let bodyFd, faulted = false;
  const lifecycle = realmStats.lifecycle;
  fs.openSync = function (file, ...args) { const fd = open.call(this, file, ...args); if (file === a.bodyPath) bodyFd = fd; return fd; };
  fs.fstatSync = function (fd, ...args) { if (fd === bodyFd && realmStats.lifecycle > lifecycle && !faulted) { faulted = true; throw EIO('fstat'); } return fstat.call(this, fd, ...args); };
  let out;
  try { out = runAuthored(a); } finally { fs.openSync = open; fs.fstatSync = fstat; }
  assert.ok(faulted, 'recheck fault ran after compile returned');
  assert.equal(out.status, 'FAIL');
  const f = failureOf(out);
  assert.equal(f.meshes.length, 3);
  meshMatches({ meshes: f.meshes, textures: AUTHORED.expected.reference_geometry.textures }, AUTHORED);
  assert.equal(f.body.sha256, AUTHORED.body_sha256);
  assert.equal(f.body.identity_post_matches, false);
  assert.ok(f.structure && f.structure.nodes.length === 2);
  const text = fs.readFileSync(path.join(out.dir, 'failure.json'), 'utf8');
  assert.ok(!text.includes(Buffer.from(AUTHORED.body_bytes).toString('hex').slice(0, 64)), 'no body bytes');
});

test('a source close fault is sticky, keeps its diagnostic and the returned evidence', () => {
  const a = authoredProfile(freshDir('source-close'));
  const open = fs.openSync, close = fs.closeSync;
  let srcFd, srcFault = false;
  fs.openSync = function (file, ...args) { const fd = open.call(this, file, ...args); if (file === P0.source.path) srcFd = fd; return fd; };
  fs.closeSync = function (fd) {
    const r = close.call(this, fd);
    if (fd === srcFd && !srcFault) { srcFault = true; throw EIO('source close'); }
    return r;
  };
  let out;
  try { out = runAuthored(a); } finally { fs.openSync = open; fs.closeSync = close; }
  assert.ok(srcFault, 'source close fault ran');
  assert.equal(fs.existsSync(path.join(out.dir, 'result.candidate.json')), false, 'no candidate written');
  assert.equal(out.code, 'cleanup_failed');
  const f = failureOf(out);
  assert.ok(f.close_errors.some((e) => e.code === 'EIO' && /source/.test(e.during)));
  assert.equal(f.meshes.length, 3, 'returned evidence retained');
});

// ------------------------------------------------------------------ 5. structure gate before lifecycle

test('constructed structure is matched before hasAnimation/createInstance/compile', () => {
  const good = f32FromHex(P01_HEX);
  const gated = (opts, code, detail) => {
    const s0 = realmStats.structure, l0 = realmStats.lifecycle;
    assert.throws(() => runStub(stub(P01_PRE, `[{ 0: ${good} }]`, { markers: true, ...opts })), (e) => {
      assert.equal(e.code, code, e.message);
      if (detail) assert.match(e.message, detail);
      assert.doesNotMatch(e.message, /MARKER_/);
      return true;
    });
    assert.equal(realmStats.structure - s0, 1, 'structure phase ran');
    assert.equal(realmStats.lifecycle - l0, 0, 'no marker method reachable');
  };
  const groups = P01_PRE.nodes[0].raw.faces.map((f) => f.smoothGroup);
  const other = [...Array(32).keys()].find((g) => !groups.includes(g));
  // Group-only mismatch: same face count, one primary group changed.
  gated({ facesExpr: () => `[${groups.map((g, i) => `{ smoothGroup: ${i === 0 ? other : g} }`).join(',')}]` }, 'structure_mismatch', /primary smooth groups/);
  // Wrong face count with valid groups.
  gated({ facesExpr: () => `[${[...groups, groups[0]].map((g) => `{ smoothGroup: ${g} }`).join(',')}]` }, 'structure_mismatch', /node 0/);
  // Realm-side bounds: out-of-range group and face count above the cap.
  gated({ facesExpr: () => `[${groups.map((g, i) => `{ smoothGroup: ${i === 0 ? 32 : g} }`).join(',')}]` }, 'vm_error', /primary group bound/);
  gated({ facesExpr: () => `[${groups.map((g, i) => `{ smoothGroup: ${i === 0 ? 1.5 : g} }`).join(',')}]` }, 'vm_error', /primary group bound/);
  gated({ facesExpr: () => `new Array(${TINY_BOUNDS.max_faces_per_node + 1}).fill({ smoothGroup: 0 })` }, 'vm_error', /face count bound/);
  gated({ ctorExtra: 'this.nodes.push(this.nodes[0], this.nodes[0]);' }, 'vm_error', /node count bound/);
  // Positive control: the matching stub reaches all three marker methods only after the gate.
  const l0 = realmStats.lifecycle;
  assert.throws(() => runStub(stub(P01_PRE, `[{ 0: ${good} }]`, { markers: true })), (e) => e.code === 'compile_error' && /MARKER_hasAnimation/.test(e.message));
  assert.equal(realmStats.lifecycle - l0, 1);
  // Real copied constructor: observed groups come from the realm, model constructed once.
  const res = withScriptSwap('none', '', () => compileInRealm(SCAFFOLD, bodyOf('P07_distinct_primary_groups'), ZP, ZG, TINY_BOUNDS, deadline()));
  assert.deepEqual(res.seen.filter(Boolean), ['model-geometry-scaffold.js', 'model-geometry-structure.js', 'model-geometry-lifecycle.js', 'model-geometry-cleanup.js']);
});

test('retained realm state is cleared on success, mismatch and timeout paths', () => {
  for (const [scaffold, ok] of [[P01_STUB_OK, true], [stub(P01_PRE, '[]', { ctorExtra: 'this.textures = ["b.bmp"];' }), false], [stub(P01_PRE, '(function(){ for(;;){} })()'), false]]) {
    const res = withScriptSwap('none', '', () => { try { return runStub(scaffold); } catch (e) { return e; } });
    assert.equal(res.value instanceof Error, !ok);
    assert.equal(res.seen.at(-1), 'model-geometry-cleanup.js');
  }
});

// ------------------------------------------------------------------ 6. dense placement triples

test('sparse, accessor and inherited placement lanes refuse before any realm', () => {
  const body = Uint8Array.from(P01.body_bytes);
  const run = (placement, detail) => refused(() => compileInRealm(SCAFFOLD, body, placement, ZG, TINY_BOUNDS, deadline()), detail);
  // eslint-disable-next-line no-sparse-arrays
  run({ ...ZP, position: [0, , 0] }, 'placement position sparse lane');
  // eslint-disable-next-line no-sparse-arrays
  run({ ...ZP, scale: [1, 1, ,] }, 'placement scale sparse lane');
  const hole = [1, 1, 1]; delete hole[2];
  run({ ...ZP, scale: hole }, 'placement scale sparse lane');
  const getter = [0, 0, 0]; Object.defineProperty(getter, 1, { get: () => 0, enumerable: true });
  run({ ...ZP, rotation: getter }, 'placement rotation sparse lane');
  const inherited = [0, 0, 0]; delete inherited[0]; Object.setPrototypeOf(inherited, Object.assign(Object.create(Array.prototype), { 0: 0 }));
  run({ ...ZP, position: inherited }, 'placement position sparse lane');
  run({ ...ZP, rotation: [0, { number: '-0' }, 0] }, 'placement rotation non-number scalar');
  run({ ...ZP, rotation: [0, 0, { number: '-0' }] }, 'placement rotation non-number scalar');
  run({ ...ZP, scale: [{ number: '-0' }, 1, 1] }, 'placement scale non-number scalar');
  // Profile: the tag restores -0 only at rotation lane 0; every other lane refuses.
  const bad = (edit) => { const p = realProfile(); edit(p); failsWith(() => validateProfile(p), 'profile_schema'); };
  bad((p) => { p.placement.rotation[2] = { number: '-0' }; });
  bad((p) => { p.placement.scale[1] = { number: '-0' }; });
  bad((p) => { p.placement.position[2] = { number: '-0' }; });
  bad((p) => { delete p.placement.position[1]; });
  assert.ok(Object.is(validateProfile(realProfile()).placement.rotation[0], -0));
});

// ------------------------------------------------------------------ 7. Float32-degenerate columns

test('Float32-degenerate transform columns refuse before any realm; safe neighbors admit', () => {
  const body = Uint8Array.from(P01.body_bytes);
  const tiny = 0.6 * 2 ** -149;
  const split = [[0, 0, 45], [45, 0, 0], [45, 0, 0]]; // rotation splitting scaled axis j into two lanes
  const scaleAt = (j, v) => [1, 1, 1].map((x, i) => (i === j ? v : x));
  const reject = (rotation, scale, code) => {
    assert.throws(() => checkRoundedColumns(rotation, scale), (e) => e instanceof ColumnAdmissionError && e.code === code);
    refused(() => compileInRealm(SCAFFOLD, body, { position: [0, 0, 0], rotation, scale }, ZG, TINY_BOUNDS, deadline()), `transform column ${code}: ${scale.findIndex((x) => x !== 1)}`);
  };
  const admit = (rotation, scale) => { checkRoundedColumns(rotation, scale); pre(body, TINY_BOUNDS, { position: [0, 0, 0], rotation, scale }); };
  for (const sign of [1, -1]) {
    for (let j = 0; j < 3; j++) {
      reject([0, 0, 0], scaleAt(j, sign * Number.MIN_VALUE), 'degenerate_column');
      reject(split[j], scaleAt(j, sign * tiny), 'degenerate_column');
      admit([0, 0, 0], scaleAt(j, sign * tiny)); // rounds to a nonzero 2^-149 lane
      admit(split[j], scaleAt(j, sign * 2 ** -149));
      assert.notEqual(Math.fround(sign * tiny), 0);
    }
  }
  // Ordinary reflected and nonuniform scales, noncommuting rotations.
  admit([0, 0, 0], [-1, 1, -1]);
  admit([23, -41, 67], [-0.5, 2, 3]);
  admit([...FROZEN.placement.rotation], [...FROZEN.placement.scale]);
  assert.throws(() => checkRoundedColumns([0, 0, 0], [0, 1, 1]), (e) => e.code === 'zero_scale');
  // eslint-disable-next-line no-sparse-arrays
  assert.throws(() => checkRoundedColumns([0, , 0], [1, 1, 1]), (e) => e.code === 'invalid_lane');
  // The reflected fixture cases still compile byte-exactly (no tolerance change).
  for (const c of POSITIVE) checkRoundedColumns(c.placement.rotation, c.placement.scale);
});

// ------------------------------------------------------------------ 8. declared fixture is held

test('declared fixture is held, hashed and recorded; a changed fixture refuses before any realm', () => {
  const ok = authoredProfile(freshDir('fixture-ok'));
  const out = runAuthored(ok);
  assert.equal(out.status, 'PASS');
  const r = JSON.parse(fs.readFileSync(path.join(out.dir, 'result.json')));
  assert.equal(r.fixture.sha256, FIXTURE_PIN.sha256);
  assert.equal(r.fixture.bytes, FIXTURE_PIN.bytes);
  assert.equal(r.fixture.identity_post_matches, true);
  assert.equal(r.fixture.path, P0.fixture.path);
  // Same size, one byte changed, at the declared path.
  const real = fs.readFileSync(P0.fixture.path);
  const bad = authoredProfile(freshDir('fixture-bad'), (p, dir) => { const b = Buffer.from(real); b[200] ^= 1; p.fixture.path = writeOwned(path.join(dir, 'cases.json'), b); });
  const created = realmStats.created; const defs = realmStats.definitions;
  const o2 = runAuthored(bad);
  assert.equal(realmStats.created - created, 0, 'no realm');
  assert.equal(realmStats.definitions - defs, 0, 'no definitions');
  assert.equal(o2.code, 'sha_mismatch');
  assert.equal(o2.stage, 'fixture');
  assert.equal(fs.existsSync(path.join(o2.dir, 'result.json')), false);
  assert.equal(fs.existsSync(path.join(o2.dir, 'scaffold.js')), false);
  // Fixture replaced after its read: final authority refuses PASS.
  const moved = authoredProfile(freshDir('fixture-moved'), (p, dir) => { p.fixture.path = writeOwned(path.join(dir, 'cases.json'), real); });
  const prof = JSON.parse(fs.readFileSync(moved.file)); const fixPath = prof.fixture.path;
  const open = fs.openSync; let swapped = false;
  fs.openSync = function (file, ...args) {
    if (file === moved.bodyPath && !swapped) { swapped = true; fs.renameSync(fixPath, `${fixPath}.orig`); writeOwned(fixPath, real); }
    return open.call(this, file, ...args);
  };
  let o3;
  try { o3 = runAuthored(moved); } finally { fs.openSync = open; }
  assert.ok(swapped);
  assert.equal(o3.status, 'FAIL');
  assert.equal(o3.code, 'identity_changed');
  assert.equal(fs.existsSync(path.join(o3.dir, 'result.json')), false);
});

// Root follow-up: all three controls were independently red against C1434e264.
test('failed failure publication retains original error, ENOSPC and close EIO externally', () => {
  const a = authoredProfile(freshDir('root-failure-publication'), (p) => { p.profile_admits_execution = true; });
  const open = fs.openSync, write = fs.writeFileSync, close = fs.closeSync;
  let target, writes = 0, closes = 0, out;
  const created = realmStats.created;
  fs.openSync = function (file, ...args) { const fd = open.call(this, file, ...args); if (typeof file === 'string' && file.endsWith('/failure.json')) target = fd; return fd; };
  fs.writeFileSync = function (fd, ...args) { if (fd === target) { writes++; throw Object.assign(new Error('Root failure publication full'), { code: 'ENOSPC' }); } return write.call(this, fd, ...args); };
  fs.closeSync = function (fd) { const r = close.call(this, fd); if (fd === target) { closes++; target = undefined; throw EIO('Root failure publication close'); } return r; };
  try { out = runAuthored(a); } finally { fs.openSync = open; fs.writeFileSync = write; fs.closeSync = close; }
  assert.equal(writes, 1); assert.equal(closes, 1);
  assert.equal(realmStats.created - created, 0);
  assert.equal(out.code, 'profile_schema'); assert.equal(out.stage, 'profile');
  assert.equal(out.failure_write_error, 'ENOSPC');
  assert.equal(out.failure_summary.code, 'profile_schema');
  assert.equal(out.failure_summary.publication_error.code, 'ENOSPC');
  assert.ok(out.failure_summary.close_errors.some((e) => e.code === 'EIO' && e.during === 'write failure.json'));
  assert.ok(Buffer.byteLength(JSON.stringify(out.failure_summary)) < 8192);
});

test('preservation link EIO stops retirement and keeps candidate and own final alias', () => {
  const a = authoredProfile(freshDir('root-preservation-EIO')), link = fs.linkSync;
  let linked = 0, faults = 0, late = false, out;
  fs.linkSync = function (from, to, ...args) {
    if (path.basename(to).startsWith('result.unqualified')) { faults++; throw EIO('Root preservation link'); }
    const r = link.call(this, from, to, ...args);
    if (to.endsWith('/result.json')) { linked++; late = true; }
    return r;
  };
  try { out = runAuthored(a, { clock: () => (late ? 20000 : 0) }); } finally { fs.linkSync = link; }
  assert.equal(linked, 1); assert.equal(faults, 1);
  assert.equal(out.code, 'deadline_exceeded'); assert.equal(out.timeout, true);
  const f = failureOf(out);
  assert.equal(f.retirement.status, 'failed'); assert.equal(f.retirement.preserved_as, null);
  assert.ok(f.retirement.errors.some((e) => e.code === 'EIO' && e.during === 'preserve result.unqualified.json'));
  const candidate = path.join(out.dir, 'result.candidate.json'), final = path.join(out.dir, 'result.json');
  assert.deepEqual(fs.readFileSync(final), fs.readFileSync(candidate));
  assert.equal(fs.statSync(final).ino, fs.statSync(candidate).ino);
});

test('successful realm cleanup is inside helper deadline and does not replace a primary timeout', () => {
  for (const timeout of [false, true]) {
    let now = 0, cleanups = 0, error;
    const Script = vm.Script;
    vm.Script = class extends Script {
      constructor(src, opts) { super(src, opts); this.rootCleanup = opts?.filename === 'model-geometry-cleanup.js'; }
      runInContext(...args) { const out = super.runInContext(...args); if (this.rootCleanup) { cleanups++; now = 20000; } return out; }
    };
    const scaffold = timeout ? stub(P01_PRE, '(function(){ for(;;){} })()') : P01_STUB_OK;
    try { compileInRealm(scaffold, Uint8Array.from(P01.body_bytes), ZP, ZG, TINY_BOUNDS, makeDeadline(10000, () => now)); } catch (e) { error = e; } finally { vm.Script = Script; }
    assert.equal(cleanups, 1); assert.equal(now, 20000);
    assert.equal(error?.code, timeout ? 'vm_timeout' : 'deadline_exceeded');
    assert.equal(error?.stage, timeout ? 'compile' : 'cleanup');
  }
});
