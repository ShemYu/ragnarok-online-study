// T07.007.014.009: synthetic controls for probe_remaining_compiled_core.mjs.
//
// Every prefix, suffix and body here is an authored synthetic double in a fresh
// private temporary directory. Fake RSW/GAT/GND classes prove host plumbing
// only; the genuine compiled prefix, real suffix and real bodies are never
// read or evaluated. Run with the exact Node binary named by the profile:
//
//   <profile node> --test tools/renewal/tests/probe_remaining_compiled_core.test.mjs

import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

import {
  ADMISSION_SCHEMA, LIMITS, PROFILE_SCHEMA, IDENTITY_FIELDS, IDENTITY_ENCODING, Refusal,
  classifyMap, hostDescriptor, identityOf, parseArgs, readPinnedFile, runHost, sameIdentity, validateProfile
} from '../probe_remaining_compiled_core.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const hostPath = path.resolve(here, '..', 'probe_remaining_compiled_core.mjs');
const sha256 = (b) => createHash('sha256').update(b).digest('hex');
const tmpRoot = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 't07-014-009-test-')));
fs.chmodSync(tmpRoot, 0o700);
test.after(() => fs.rmSync(tmpRoot, { recursive: true, force: true }));
let fixtureCount = 0;

const describe = (p) => {
  const bytes = fs.readFileSync(p);
  return { path: p, bytes: bytes.length, sha256: sha256(bytes), identity: identityOf(fs.statSync(p, { bigint: true })) };
};
let nodeDescriptor = null;
const nodeDesc = () => (nodeDescriptor ??= describe(process.execPath));

// Synthetic prefix: fake parser classes, the bare `onmessage =` assignment and
// the immediate THREAD_READY, as the real prefix shape requires. Its own
// handler answers ROOT_CH1_CORE with a bogus result so early dispatch is visible.
const syntheticPrefix = (behavior = 'normal') => `/* synthetic prefix */
var BEHAVIOR = ${JSON.stringify(behavior)};
var SKIP_SUFFIX_INSTALL = BEHAVIOR === 'skip-install';
var decodeJson = (buffer) => { if (!(buffer instanceof ArrayBuffer)) throw new TypeError('cross-realm or non-ArrayBuffer input'); return JSON.parse(new TextDecoder().decode(buffer)); };
var RSW = class RSW {
  constructor(buffer) {
    const o = decodeJson(buffer);
    this.files = o.files; this.models = o.models; this.behavior = o.behavior; this.water = { level: 1, waveHeight: 2 };
    if (o.behavior === 'hang') for (;;) {}
    if (o.behavior === 'leak-timer') setInterval(() => {}, 1000);
  }
  compile() { return { lights: new Float32Array([0.5, -0, 2]) }; }
};
var GAT = class GAT { constructor(b) { this.o = decodeJson(b); this.version = 1.2; } compile() { return { cells: new Float32Array([1, 2, 3]) }; } };
var GND = class { constructor(b) { this.o = decodeJson(b); this.version = 1.7; } compile(level, wave) { return { mesh: new Float32Array([NaN, -0, Infinity, level, wave]) }; } };
onmessage = function receive(event) {
  if (event.data?.type === 'ROOT_CH1_CORE') postMessage({ type: 'ROOT_CH1_RESULT', encoded: '{"schema":"prefix-handler"}' });
};
${behavior === 'eval-throw' ? "throw new RangeError('synthetic prefix evaluation failure');" : ''}
${behavior === 'no-ready' ? '' : "postMessage({ type: 'THREAD_READY' });"}
`;

const inputsLiteral = (inputs) => `const CH1_INPUTS = [\n${inputs.map((p) => `  {kind:'${p.kind}',url:'/body/${p.kind}',bytes:${p.bytes},sha256:'${p.sha256}'}`).join(',\n')}\n];\n`;

// Synthetic suffix bound to the synthetic pilot, with the same two projected
// regions, fixed bound/deadline literals and terminal-message protocol.
const syntheticSuffix = (pilotInputs) => `// synthetic suffix
const CH1_LIMIT = 8 * 1024 * 1024;
${inputsLiteral(pilotInputs)}let ch1Busy = false;
if (!SKIP_SUFFIX_INSTALL) self.onmessage = async event => {
  if (event.data?.type !== 'ROOT_CH1_CORE' || ch1Busy) return;
  ch1Busy = true;
  const deadline = performance.now() + 48000;
  let phase = 'input', anomalies = 0;
  const need = (v,m) => {if(!v)throw new Error(m);};
  const sha = async b => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',b)),x=>x.toString(16).padStart(2,'0')).join('');
  const scan = async v => {const c={finite:0,nan:0,positiveInfinity:0,negativeInfinity:0,negativeZero:0};
    for (const n of v) { if (Number.isFinite(n)) {c.finite++; if (Object.is(n,-0)) c.negativeZero++;} else {anomalies++; c[Number.isNaN(n)?'nan':n>0?'positiveInfinity':'negativeInfinity']++;} }
    return {type:v.constructor.name,length:v.length,bytes:v.byteLength,sha256:await sha(new Uint8Array(v.buffer,v.byteOffset,v.byteLength)),counts:c};};
  const result = {schema:'root014004-compiled-core-1',stages:[],inputs:[],inputPostchecks:[],error:null,observationComplete:false,numericAnomalies:0,qualification:false};
  const buffers = [];
  const body = async p => {
    phase = 'fetch-'+p.kind;
    const r = await fetch(p.url,{cache:'no-store',redirect:'error'});
    need(r.status===200&&r.headers.get('content-length')===String(p.bytes),'fixed body framing');
    const b = await r.arrayBuffer();
    need(b.byteLength===p.bytes&&await sha(b)===p.sha256,'complete body pin');
    buffers.push([p,b]); result.inputs.push({...p}); return b;
  };
  let world;
  try {
    const rsw = await body(CH1_INPUTS[0]); phase = 'RSW'; world = new RSW(rsw); result.stages.push(phase);
    if (world.behavior === 'throw') throw new SyntaxError('synthetic genuine parser throw');
    need(world.files.gat==='gef_dun03.gat'&&world.files.gnd==='gef_dun03.gnd','embedded terrain names');
    const gat = await body(CH1_INPUTS[1]); phase = 'GAT'; const altitude = new GAT(gat); result.stages.push(phase);
    phase = 'GAT.compile'; const ca = altitude.compile(); result.stages.push(phase);
    const gnd = await body(CH1_INPUTS[2]); phase = 'GND'; const ground = new GND(gnd); result.stages.push(phase);
    phase = 'GND.compile'; const cg = ground.compile(world.water.level, world.water.waveHeight); result.stages.push(phase);
    phase = 'RSW.compile'; const cw = world.compile(); result.stages.push(phase);
    result.altitude = await scan(ca.cells); result.ground = await scan(cg.mesh); result.worldCompiled = await scan(cw.lights);
    result.placements = world.models.map((m,i) => ({index:i,request:m}));
    result.dependencyCounts = {placements:result.placements.length};
    result.observationComplete = true;
  } catch (e) { result.error = {phase,name:String(e?.name||'Error'),message:String(e?.message||e)}; }
  for (const [p,b] of buffers) result.inputPostchecks.push({kind:p.kind,bytes:b.byteLength,sha256:await sha(b)});
  result.numericAnomalies = anomalies;
  postMessage({type:'ROOT_CH1_RESULT',encoded:JSON.stringify(result)});
  if (world?.behavior === 'duplicate') postMessage({type:'ROOT_CH1_RESULT',encoded:JSON.stringify(result)});
};
`;

const writeFile = (p, data) => { fs.writeFileSync(p, data, { mode: 0o600 }); return describe(p); };

// Builds a complete synthetic runtime profile: 21 maps over 55 distinct body
// paths (four maps declare another map's terrain; maps 0-2 share one RSW hash) and
// a separate three-body pilot. `behaviors[mapIndex]` is embedded in that RSW body.
function makeFixture({ prefixBehavior = 'normal', behaviors = {}, rswFiles = {} } = {}) {
  const dir = path.join(tmpRoot, `fixture-${++fixtureCount}`);
  fs.mkdirSync(path.join(dir, 'bodies'), { recursive: true, mode: 0o700 });
  const bodies = [];
  const addBody = (list, kind, logical, content, sub = 'bodies') => {
    const file = path.join(dir, sub, `${sub}-${list.length}.body`);
    list.push({ body_index: list.length, kind, logical_path: logical, source: writeFile(file, content) });
    return list.length - 1;
  };
  const names = Array.from({ length: 21 }, (_, i) => `syn_${String(i).padStart(2, '0')}`);
  const aliasOf = { 1: 0, 2: 0, 10: 4, 11: 3 }; // the real profile's alias shape
  const terrainOwners = names.map((_, i) => !(i in aliasOf));
  const rswIndex = [];
  names.forEach((name, i) => {
    const terrain = names[aliasOf[i] ?? i];
    const files = rswFiles[i] ?? { gat: `${terrain}.gat`, gnd: `${terrain}.gnd` };
    // Unsalted content: maps 0-2 share identical RSW bytes (distinct paths, coinciding hashes).
    const behavior = behaviors[i] ?? 'normal';
    const content = JSON.stringify({ files, models: ['a.rsm', 'b.rsm'], behavior });
    rswIndex.push(addBody(bodies, 'rsw', `data/${name}.rsw`, content));
  });
  const terrainIndex = {};
  names.forEach((name, i) => {
    if (!terrainOwners[i]) return;
    terrainIndex[name] = {
      gnd: addBody(bodies, 'gnd', `data/${name}.gnd`, JSON.stringify({ gnd: name })),
      gat: addBody(bodies, 'gat', `data/${name}.gat`, JSON.stringify({ gat: name }))
    };
  });
  const hex = (s) => Buffer.from(s, 'latin1').toString('hex');
  const maps = names.map((name, i) => {
    const terrain = names[aliasOf[i] ?? i];
    return {
      body_indices: { gat: terrainIndex[terrain].gat, gnd: terrainIndex[terrain].gnd, rsw: rswIndex[i] },
      expected_world_files_raw_hex: { gat: hex(`${terrain}.gat`), gnd: hex(`${terrain}.gnd`), ini: '' },
      map_index: i, map_name: name
    };
  });
  fs.mkdirSync(path.join(dir, 'pilot'), { mode: 0o700 });
  const pilotBodies = [];
  addBody(pilotBodies, 'rsw', 'data/ch1_que01.rsw', JSON.stringify({ files: { gat: 'gef_dun03.gat', gnd: 'gef_dun03.gnd' }, models: ['p.rsm'], behavior: behaviors.pilot ?? 'normal' }), 'pilot');
  addBody(pilotBodies, 'gat', 'data/gef_dun03.gat', JSON.stringify({ gat: 'pilot' }), 'pilot');
  addBody(pilotBodies, 'gnd', 'data/gef_dun03.gnd', JSON.stringify({ gnd: 'pilot' }), 'pilot');
  const pilotInputs = ['rsw', 'gat', 'gnd'].map((kind, i) => ({ kind, bytes: pilotBodies[i].source.bytes, sha256: pilotBodies[i].source.sha256 }));
  const prefix = writeFile(path.join(dir, 'prefix.js'), syntheticPrefix(prefixBehavior));
  const suffix = writeFile(path.join(dir, 'suffix.js'), syntheticSuffix(pilotInputs));
  const profile = {
    bodies, claims: { actual_constructor_or_host_qualification: false }, compiled_prefix: prefix, execution_admitted: false,
    identity_encoding: IDENTITY_ENCODING, identity_fields: [...IDENTITY_FIELDS], limits: { ...LIMITS }, maps, node: nodeDesc(),
    pilot: {
      bodies: pilotBodies, body_indices: { gat: 1, gnd: 2, rsw: 0 },
      expected_world_files_raw_hex: { gat: hex('gef_dun03.gat'), gnd: hex('gef_dun03.gnd'), ini: '' }, map_index: -1, map_name: 'ch1_que01'
    },
    pilot_suffix: suffix, schema: PROFILE_SCHEMA
  };
  const sum = (list) => list.reduce((n, b) => n + b.source.bytes, 0);
  const limits = { main_unique_body_bytes: sum(bodies), pilot_unique_body_bytes: sum(pilotBodies) };
  return { dir, profile, limits, prefix, suffix };
}

function stage(fx, { mode = 'pilot', admission = {}, workerDeadline } = {}) {
  const profilePath = path.join(fx.dir, 'PROFILE.json');
  const profileBytes = Buffer.from(JSON.stringify(fx.profile, null, 1));
  fs.writeFileSync(profilePath, profileBytes, { mode: 0o600 });
  const outputPath = path.join(fx.dir, `out-${mode}-${Math.random().toString(16).slice(2)}`);
  const doc = {
    schema: ADMISSION_SCHEMA, root_bound: true, execution_admitted: true, mode,
    profile_sha256: sha256(profileBytes), output_path: outputPath, host: hostDescriptor(), ...admission
  };
  for (const [k, v] of Object.entries(admission)) if (v === undefined) delete doc[k];
  const admissionPath = path.join(fx.dir, `ADMISSION-${Math.random().toString(16).slice(2)}.json`);
  fs.writeFileSync(admissionPath, JSON.stringify(doc), { mode: 0o600 });
  const testing = {
    profilePin: { bytes: profileBytes.length, sha256: sha256(profileBytes) },
    prefixPin: { bytes: fx.prefix.bytes, sha256: fx.prefix.sha256 },
    suffixPin: { bytes: fx.suffix.bytes, sha256: fx.suffix.sha256 },
    limits: { ...fx.limits, ...(workerDeadline ? { worker_deadline_ms: workerDeadline } : {}) }
  };
  return { args: { profile: profilePath, admission: admissionPath }, testing, outputPath };
}

const readJson = (p) => JSON.parse(fs.readFileSync(p, 'utf8'));
const report = (out, label) => readJson(path.join(out, `${label}.host.json`));

// ---------------------------------------------------------------- arguments, admission, pins

test('CLI arguments: missing, unknown and duplicate arguments are refused', () => {
  assert.deepEqual(parseArgs(['--profile', 'a', '--admission', 'b']), { profile: 'a', admission: 'b' });
  assert.deepEqual(parseArgs(['--admission', 'b', '--profile', 'a']), { profile: 'a', admission: 'b' });
  for (const argv of [[], ['--profile', 'a'], ['--profile', 'a', '--admission'], ['--profile', 'a', '--profile', 'b'],
    ['--profile', 'a', '--admission', 'b', '--mode', 'pilot'], ['--profile=a', '--admission', 'b'], ['--profile', '--admission', 'b']]) {
    assert.throws(() => parseArgs(argv), (e) => e instanceof Refusal && e.code === 'usage', JSON.stringify(argv));
  }
  const cli = spawnSync(process.execPath, [hostPath, '--profile', 'x', '--profile', 'y'], { encoding: 'utf8', env: {} });
  assert.equal(cli.status, 2);
  assert.match(cli.stderr, /duplicate argument/);
});

test('CLI: the fixed profile byte/SHA pin is independent of the path', () => {
  const fx = makeFixture();
  const { args } = stage(fx);
  const cli = spawnSync(process.execPath, [hostPath, '--profile', args.profile, '--admission', args.admission], { encoding: 'utf8', env: {} });
  assert.equal(cli.status, 2);
  assert.match(cli.stderr, /refused: profile: bytes\/sha256 differ from pin/);
});

test('admission is validated before any source/body target is read', async () => {
  const fx = makeFixture();
  // Make every target unreadable: a refusal must come from the admission, not ENOENT.
  fs.rmSync(path.join(fx.dir, 'bodies'), { recursive: true });
  fs.rmSync(path.join(fx.dir, 'pilot'), { recursive: true });
  fs.rmSync(fx.prefix.path);
  const host = hostDescriptor();
  const cases = [
    { schema: 'other' }, { root_bound: false }, { execution_admitted: false }, { execution_admitted: 'true' },
    { mode: 'all' }, { profile_sha256: '0'.repeat(64) }, { output_path: 'relative/out' }, { extra: 1 }, { host: undefined },
    { host: { ...host, bytes: host.bytes + 1 } }, { host: { ...host, sha256: 'f'.repeat(64) } },
    { host: { ...host, identity: host.identity.map((v, i) => (i === 3 ? (BigInt(v) + 1n).toString() : v)) } },
    { host: { ...host, identity: host.identity.map(Number) } }
  ];
  for (const admission of cases) {
    const s = stage(fx, { admission });
    await assert.rejects(runHost(s.args, s.testing), (e) => e instanceof Refusal && e.code === 'admission', JSON.stringify(Object.keys(admission)));
    assert.equal(fs.existsSync(s.outputPath), false);
  }
  // A valid admission then reaches the (absent) targets and records the failure.
  const s = stage(fx);
  const result = await runHost(s.args, s.testing);
  assert.equal(result.status, 'failed');
  const manifest = readJson(path.join(s.outputPath, 'MANIFEST.json'));
  assert.match(manifest.errors[0].message, /ENOENT/);
  assert.deepEqual(manifest.maps.map((m) => m.status), ['not_started']);
});

test('exact bigint identity: a nanosecond difference lost by Number() is refused', () => {
  const dir = path.join(tmpRoot, 'identity');
  fs.mkdirSync(dir, { mode: 0o700 });
  const file = path.join(dir, 'a.body');
  const desc = writeFile(file, 'abc');
  assert.ok(readPinnedFile(file, { desc, maxBytes: 16, label: 'a' }).sha256 === desc.sha256);
  const mtime = BigInt(desc.identity[3]);
  assert.ok(mtime > BigInt(Number.MAX_SAFE_INTEGER));
  const off = desc.identity.map((v, i) => (i === 3 ? (mtime + 1n).toString() : v));
  assert.equal(Number(off[3]), Number(desc.identity[3]), 'Number() would call these equal');
  assert.equal(sameIdentity(off, desc.identity), false);
  assert.throws(() => readPinnedFile(file, { desc: { ...desc, identity: off }, maxBytes: 16, label: 'a' }), /identity differs/);
  // Symlink, hard link and size/hash differences are refused.
  fs.symlinkSync(file, path.join(dir, 'link.body'));
  assert.throws(() => readPinnedFile(path.join(dir, 'link.body'), { maxBytes: 16, label: 'l' }), /canonical|regular|ELOOP/);
  fs.linkSync(file, path.join(dir, 'hard.body'));
  assert.throws(() => readPinnedFile(file, { maxBytes: 16, label: 'h' }), /single-link/);
  fs.rmSync(path.join(dir, 'hard.body'));
  const fresh = describe(file);
  assert.throws(() => readPinnedFile(file, { desc: { ...fresh, sha256: '0'.repeat(64) }, maxBytes: 16, label: 'a' }), /sha256 differ/);
  assert.throws(() => readPinnedFile(file, { desc: fresh, maxBytes: 2, label: 'a' }), /exceeds/);
});

test('profile binding: body/hash/name/alias controls', () => {
  const fx = makeFixture();
  const opts = { limits: { ...LIMITS, ...fx.limits }, prefixPin: fx.prefix, suffixPin: fx.suffix };
  const bound = validateProfile(fx.profile, opts);
  assert.deepEqual(bound.aliases, [{ map_name: 'syn_01', terrain: 'syn_00' }, { map_name: 'syn_02', terrain: 'syn_00' }, { map_name: 'syn_10', terrain: 'syn_04' }, { map_name: 'syn_11', terrain: 'syn_03' }]);
  assert.equal(new Set(bound.bodies.map((b) => b.source.path)).size, 55);
  assert.ok(new Set(bound.bodies.map((b) => b.source.sha256)).size < 55, 'coinciding hashes keep distinct paths');
  const mutate = (fn) => { const p = structuredClone(fx.profile); fn(p); return () => validateProfile(p, opts); };
  assert.throws(mutate((p) => { [p.maps[0].body_indices.gat, p.maps[0].body_indices.gnd] = [p.maps[0].body_indices.gnd, p.maps[0].body_indices.gat]; }), /binds a non-/);
  assert.throws(mutate((p) => { p.maps[3].expected_world_files_raw_hex.gnd = Buffer.from('syn_04.gnd').toString('hex'); }), /embedded gnd name/);
  assert.throws(mutate((p) => { p.maps[2].map_name = 'other'; }), /RSW logical path/);
  assert.throws(mutate((p) => { p.bodies[7].source.path = p.bodies[6].source.path; }), /duplicate body path/);
  assert.throws(mutate((p) => { p.maps[1].body_indices.rsw = p.maps[0].body_indices.rsw; }), /RSW logical path is not data\/syn_01.rsw/);
  assert.throws(mutate((p) => { p.bodies[0].source.identity[3] = Number(p.bodies[0].source.identity[3]); }), /decimal strings/);
  assert.throws(mutate((p) => { p.bodies[0].source.identity[5] = String(0o040700); }), /regular file/);
  assert.throws(mutate((p) => { p.identity_fields = [...IDENTITY_FIELDS].reverse(); }), /identity field order/);
  assert.throws(mutate((p) => { p.execution_admitted = true; }), /execution_admitted:false/);
  assert.throws(mutate((p) => { p.limits.worker_deadline_ms = 60000; }), /frozen cap/);
  assert.throws(mutate((p) => { p.maps.pop(); }), /21 maps/);
});

// ---------------------------------------------------------------- end-to-end synthetic runs

test('pilot: unchanged prefix/suffix, suffix handshake, in-memory fetch, exact ledger and positive exit', async () => {
  const fx = makeFixture();
  const s = stage(fx);
  const result = await runHost(s.args, s.testing);
  assert.equal(result.status, 'observed', JSON.stringify(result));
  const out = s.outputPath;
  assert.equal(fs.statSync(out).mode & 0o777, 0o700);
  for (const f of fs.readdirSync(out)) assert.equal(fs.statSync(path.join(out, f)).mode & 0o777, 0o600, f);
  const manifest = readJson(path.join(out, 'MANIFEST.json'));
  assert.deepEqual(manifest.maps.map((m) => m.status), ['observed']);
  assert.ok(manifest.source_postchecks.every((p) => p.ok));
  assert.deepEqual(manifest.source_prechecks.map((p) => p.label), ['compiled_prefix', 'pilot_suffix', 'pilot.body[0]', 'pilot.body[1]', 'pilot.body[2]']);
  const r = report(out, 'pilot');
  assert.equal(r.suffix.unchanged, true);
  assert.equal(r.suffix.sha256, fx.suffix.sha256);
  assert.equal(r.prefix.sha256, fx.prefix.sha256);
  assert.equal(r.lifecycle.thread_ready, 1);
  assert.equal(r.lifecycle.suffix_installed, true);
  assert.equal(r.lifecycle.terminal_results, 1);
  assert.equal(r.lifecycle.exit_code, 0);
  assert.equal(r.lifecycle.positive_exit, true);
  assert.equal(r.bootstrap.evidence.handler_changed_after_thread_ready, true);
  assert.deepEqual(r.bootstrap.evidence.onmessage_assignments.map((a) => a.after_thread_ready), [false, true]);
  assert.deepEqual(r.closing.fetch.calls.map((c) => c.url), ['/body/rsw', '/body/gat', '/body/gnd']);
  assert.ok(r.closing.buffers.every((b) => b.ok));
  // The exact encoded string is retained byte-for-byte with every numeric anomaly.
  const coreBytes = fs.readFileSync(path.join(out, 'pilot.core.json'));
  const terminal = r.script_messages.find((m) => m.type === 'ROOT_CH1_RESULT');
  assert.equal(sha256(coreBytes), terminal.encoded_sha256);
  assert.equal(r.core_file.sha256, terminal.encoded_sha256);
  const core = JSON.parse(coreBytes);
  assert.deepEqual(core.ground.counts, { finite: 3, nan: 1, positiveInfinity: 1, negativeInfinity: 0, negativeZero: 1 });
  assert.equal(core.worldCompiled.counts.negativeZero, 1);
  assert.equal(core.numericAnomalies, 2);
  assert.equal(core.qualification, false);
  assert.deepEqual(core.stages, ['RSW', 'GAT', 'GAT.compile', 'GND', 'GND.compile', 'RSW.compile']);
  assert.deepEqual(core.placements, [{ index: 0, request: 'p.rsm' }]);
  assert.equal(r.core_summary.numeric_anomalies, 2);
});

test('remaining21: two-region suffix projection, inverse reconstruction, aliases and all maps observed', async () => {
  const fx = makeFixture();
  const s = stage(fx, { mode: 'remaining21' });
  const result = await runHost(s.args, s.testing);
  assert.equal(result.status, 'observed', JSON.stringify(result));
  const manifest = readJson(path.join(s.outputPath, 'MANIFEST.json'));
  assert.equal(manifest.maps.length, 21);
  assert.deepEqual(manifest.maps.map((m) => m.map_index), [...Array(21).keys()]);
  assert.ok(manifest.maps.every((m) => m.status === 'observed'));
  assert.equal(manifest.source_prechecks.length, 2 + 55);
  assert.deepEqual(manifest.terrain_aliases.map((a) => a.map_name), ['syn_01', 'syn_02', 'syn_10', 'syn_11']);
  const original = fs.readFileSync(fx.suffix.path, 'utf8');
  for (const m of manifest.maps) {
    const r = report(s.outputPath, m.label);
    const projected = fs.readFileSync(path.join(s.outputPath, `${m.label}.suffix.js`), 'utf8');
    assert.equal(sha256(projected), r.suffix.sha256);
    assert.equal(r.suffix.replacements.length, 2);
    // Independent inverse: undo both replacements at the recorded offsets.
    const [a, b] = r.suffix.replacements;
    assert.equal(projected.slice(a.new_offset, a.new_offset + a.new.length), a.new);
    assert.equal(projected.slice(b.new_offset, b.new_offset + b.new.length), b.new);
    const inverse = projected.slice(0, a.new_offset) + a.old + projected.slice(a.new_offset + a.new.length, b.new_offset) + b.old + projected.slice(b.new_offset + b.new.length);
    assert.equal(inverse, original);
    const terrain = { 1: 'syn_00', 2: 'syn_00', 10: 'syn_04', 11: 'syn_03' }[m.map_index] ?? m.map_name;
    assert.equal(b.new, `need(world.files.gat==='${terrain}.gat'&&world.files.gnd==='${terrain}.gnd','embedded terrain names');`);
    const core = readJson(path.join(s.outputPath, `${m.label}.core.json`));
    assert.deepEqual(core.inputs.map((i) => i.sha256), r.bindings.map((i) => i.sha256));
  }
  // Coinciding RSW hashes on distinct paths stay two separate bindings.
  const r0 = report(s.outputPath, 'map-00'), r1 = report(s.outputPath, 'map-01');
  assert.equal(r0.bindings[0].sha256, r1.bindings[0].sha256);
  assert.notEqual(r0.bindings[0].path, r1.bindings[0].path);
});

test('prefix THREAD_READY is not readiness: without the suffix handler the core is never sent', async () => {
  const fx = makeFixture({ prefixBehavior: 'skip-install' });
  const s = stage(fx, { mode: 'remaining21' });
  const result = await runHost(s.args, s.testing);
  assert.equal(result.status, 'failed');
  const manifest = readJson(path.join(s.outputPath, 'MANIFEST.json'));
  assert.equal(manifest.maps[0].status, 'failed');
  assert.equal(manifest.maps[0].failure_class, 'host');
  assert.ok(manifest.maps.slice(1).every((m) => m.status === 'not_started' && /fail-fast/.test(m.reason)));
  const r = report(s.outputPath, 'map-00');
  assert.equal(r.lifecycle.thread_ready, 1);
  assert.equal(r.lifecycle.core_sent, false);
  assert.equal(r.lifecycle.terminal_results, 0, 'the prefix handler never received ROOT_CH1_CORE');
  assert.equal(r.bootstrap.type, 'BOOTSTRAP_FAILED');
  assert.equal(fs.existsSync(path.join(s.outputPath, 'map-00.core.json')), false);
});

test('bootstrap failures: missing prefix THREAD_READY and a prefix evaluation throw are preserved', async () => {
  for (const [behavior, pattern] of [['no-ready', /THREAD_READY/], ['eval-throw', /evaluation threw/]]) {
    const fx = makeFixture({ prefixBehavior: behavior });
    const s = stage(fx);
    const result = await runHost(s.args, s.testing);
    assert.equal(result.status, 'failed');
    const r = report(s.outputPath, 'pilot');
    assert.equal(r.status, 'failed');
    assert.match(r.bootstrap.reason, pattern);
    if (behavior === 'eval-throw') assert.deepEqual([r.bootstrap.error.name, r.bootstrap.error.message], ['RangeError', 'synthetic prefix evaluation failure']);
    assert.equal(r.lifecycle.exit_code, 0, 'the worker still exits on its own after reporting');
  }
});

test('duplicate terminal messages fail the map and stop the batch', async () => {
  const fx = makeFixture({ behaviors: { 0: 'duplicate' } });
  const s = stage(fx, { mode: 'remaining21' });
  await runHost(s.args, s.testing);
  const manifest = readJson(path.join(s.outputPath, 'MANIFEST.json'));
  assert.equal(manifest.maps[0].status, 'failed');
  assert.ok(manifest.maps[0].reasons.some((x) => /duplicate terminal|after the terminal/.test(x)));
  assert.equal(manifest.counts.not_started, 20);
});

test('timeout: the parent terminates only its owned worker; pending maps stay enumerated', async () => {
  const fx = makeFixture({ behaviors: { 1: 'hang' } });
  const s = stage(fx, { mode: 'remaining21', workerDeadline: 1500 });
  const result = await runHost(s.args, s.testing);
  assert.equal(result.status, 'failed');
  const manifest = readJson(path.join(s.outputPath, 'MANIFEST.json'));
  assert.deepEqual(manifest.maps.slice(0, 3).map((m) => m.status), ['observed', 'failed', 'not_started']);
  assert.equal(manifest.maps.length, 21);
  assert.equal(manifest.counts.not_started, 19);
  assert.match(manifest.stopped_reason, /map-01/);
  const r = report(s.outputPath, 'map-01');
  assert.equal(r.lifecycle.deadline_expired, true);
  assert.equal(r.lifecycle.terminate_requested, true);
  assert.notEqual(r.lifecycle.exit_code, 0);
  assert.equal(r.lifecycle.positive_exit, false);
  assert.equal(r.lifecycle.core_sent, true);
  assert.equal(r.lifecycle.terminal_results, 0);
  assert.ok(manifest.source_postchecks.every((p) => p.ok), 'posthashes still complete after the stop');
});

test('positive exit: a worker that keeps a handle after closing is a failure, not success', async () => {
  const fx = makeFixture({ behaviors: { pilot: 'leak-timer' } });
  const s = stage(fx, { workerDeadline: 1500 });
  const result = await runHost(s.args, s.testing);
  assert.equal(result.status, 'failed');
  const r = report(s.outputPath, 'pilot');
  assert.equal(r.lifecycle.terminal_results, 1);
  assert.equal(r.lifecycle.closing_summary, true);
  assert.equal(r.lifecycle.deadline_expired, true);
  assert.equal(r.lifecycle.positive_exit, false);
  assert.equal(r.failure_class, 'host', 'a result without a positive exit is not observed');
  assert.ok(fs.existsSync(path.join(s.outputPath, 'pilot.core.json')), 'the partial artifact is still retained');
});

test('genuine exceptions keep their phase/name/message and do not stop the batch', async () => {
  const fx = makeFixture({ behaviors: { 3: 'throw' }, rswFiles: { 7: { gat: 'wrong.gat', gnd: 'syn_07.gnd' } } });
  const s = stage(fx, { mode: 'remaining21' });
  const result = await runHost(s.args, s.testing);
  assert.equal(result.status, 'failed');
  const manifest = readJson(path.join(s.outputPath, 'MANIFEST.json'));
  assert.equal(manifest.counts.observed, 19);
  for (const [i, name, message] of [[3, 'SyntaxError', 'synthetic genuine parser throw'], [7, 'Error', 'embedded terrain names']]) {
    assert.equal(manifest.maps[i].status, 'failed');
    assert.equal(manifest.maps[i].failure_class, 'genuine');
    const core = readJson(path.join(s.outputPath, `map-0${i}.core.json`));
    assert.deepEqual(core.error, { phase: 'RSW', name, message });
    assert.equal(core.observationComplete, false);
  }
});

test('classification: worker PASS-like fields cannot override host evidence', () => {
  const lifecycle = { spawned: true, suffix_installed: true, terminal_results: 1, closing_summary: true, exit_code: 0, positive_exit: true, deadline_expired: false, terminate_requested: false };
  const closing = { post_terminal_script_messages: 0, fetch: { unknown: [], repeated: [], bad_options: [] }, buffers: [], handler_rejections: [] };
  const job = { inputs: [{ kind: 'rsw', url: '/body/rsw', bytes: 1, sha256: 'a' }] };
  const encoded = JSON.stringify({ schema: 'root014004-compiled-core-1', inputs: [{ kind: 'rsw', url: '/body/rsw', bytes: 1, sha256: 'b' }], inputPostchecks: [], error: null, observationComplete: true });
  const v = classifyMap({ lifecycle, closing, anomalies: [], worker_errors: [], encoded }, job);
  assert.equal(v.status, 'failed');
  assert.ok(v.host_failure_reasons.some((x) => /differs from the bound input/.test(x)));
  const tampered = classifyMap({ lifecycle, closing: { ...closing, buffers: [{ url: '/body/rsw', ok: false }] }, anomalies: [], worker_errors: [], encoded: null }, job);
  assert.ok(tampered.host_failure_reasons.some((x) => /constructor buffer/.test(x)));
});
