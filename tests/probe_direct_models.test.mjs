// T07.007.014.012 synthetic controls for tools/renewal/probe_direct_models.mjs.
// Only authored tiny prefix/summary/suffix/body bytes run here. No real compiled
// prefix, summary module, model body, core, archive or catalog is read or run.
//
//   node --test tests/probe_direct_models.test.mjs
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import {
  ADMISSION_SCHEMA, DOMAIN, GUARD_QUALIFICATION_SCHEMA, IDENTITY_ENCODING, IDENTITY_FIELDS, LIMITS, MANIFEST_SCHEMA,
  PILOT_AUDIT_SCHEMA, PROFILE_SCHEMA, ROOT_SOURCE_BINDING, UNBOUND_PROFILE_SCHEMA, Refusal,
  checkSuffix, hostDescriptor, newReducerTotals, readPinnedFile, reduceModel, runHost, stagesOf, validateBinding, validateProfile, validateUnboundDomain
} from '../tools/renewal/probe_direct_models.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const HOST = path.join(ROOT, 'tools/renewal/probe_direct_models.mjs');
const SUFFIX = path.join(ROOT, 'tools/renewal/direct_model_probe_suffix.js');
const PRIVATE = path.join(ROOT, '.tools/renewal/t07-014-012-repair-2');
const sha = (b) => createHash('sha256').update(b).digest('hex');
const clone = (v) => JSON.parse(JSON.stringify(v));

fs.mkdirSync(PRIVATE, { recursive: true, mode: 0o700 });
fs.chmodSync(PRIVATE, 0o700);
const RUNS = fs.realpathSync(fs.mkdtempSync(path.join(PRIVATE, 'run-')));
fs.chmodSync(RUNS, 0o700);
let seq = 0;
const freshDir = () => { const d = path.join(RUNS, `d${seq++}`); fs.mkdirSync(d, { mode: 0o700 }); return d; };

function writeFile(dir, name, data) {
  const p = path.join(dir, name);
  fs.writeFileSync(p, data, { mode: 0o600 });
  return p;
}
function descriptor(p) {
  const st = fs.lstatSync(p, { bigint: true });
  const bytes = fs.readFileSync(p);
  return { path: p, bytes: bytes.length, sha256: sha(bytes),
    identity: [st.dev, st.ino, st.size, st.mtimeNs, st.ctimeNs, st.mode, st.nlink, st.uid].map(String) };
}
const pinOf = (p) => { const b = fs.readFileSync(p); return { bytes: b.length, sha256: sha(b) }; };

// ---------------------------------------------------------------- authored sources

// Classic prefix: installs its own handler, posts THREAD_READY, then defines a
// tiny authored RSM that reads 'GRSM' + JSON. Variants exercise lifecycle faults.
const PREFIX = (variant = '') => `
self.onmessage = function prefixHandler() {};
${variant === 'no-ready' ? '' : "postMessage({ type: 'THREAD_READY' });"}
${variant === 'double-ready' ? "postMessage({ type: 'THREAD_READY' });" : ''}
${variant === 'early-result' ? "postMessage({ type: 'ROOT_MODEL_RESULT', encoded: '{}' });" : ''}
${variant === 'async-throw' ? "setTimeout(() => { throw new Error('authored async fault'); }, 0);" : ''}
${variant === 'chatty' ? "console.log('x'.repeat(4096));" : ''}
${variant === 'double-result' ? "{ const o = postMessage; postMessage = (m) => { o(m); if (m.type === 'ROOT_MODEL_RESULT') o(m); }; }" : ''}
${variant === 'no-result' ? "{ const o = postMessage; postMessage = (m) => { if (m.type !== 'ROOT_MODEL_RESULT') o(m); }; }" : ''}
${variant === 'late-clock' ? "{ const real = performance; let skew = 0; self.rootSkew = (v) => { skew = v; }; performance = { now: () => real.now() + skew }; }" : ''}
var RSM = class RSM {
  constructor(data) {
    const u = new Uint8Array(data);
    const header = String.fromCharCode(u[0], u[1], u[2], u[3]);
    if (header === 'THRW') throw new Error('authored constructor throw');
    if (header === 'MUTA') { u[4] = 0; }
    if (header === 'FETC') { fetch('/data/texture/x.bmp').catch(() => {}); }
    if (header === 'LATE') { self.rootSkew(1e6); }
    if (header !== 'GRSM' && header !== 'MUTA' && header !== 'FETC' && header !== 'LATE') throw new Error('RSM::load() - Incorrect header');
    let text = ''; for (let i = 4; i < u.length; i++) text += String.fromCharCode(u[i]);
    Object.assign(this, JSON.parse(header === 'MUTA' || header === 'LATE' ? '{"textures":[],"nodes":[]}' : text));
  }
};
`;

// Authored stand-in for the summary module: same declaration rule, explicit
// slot states, plus authored failure switches and one complete-shape sentinel.
// The sentinel mirrors every field of the pinned summary's return shape:
// explicit special-number markers, versions/keyframes, node transforms/boxes,
// animation flag, marker slots, numeric statistics and all declarations.
const SENTINEL = {
  version: { special: 'NaN' }, animLen: 300, shadeType: 2, alpha: { special: 'undefined' }, frameRatePerSecond: { special: '+Infinity' },
  textures: ['Sky\\A B.bmp', 'unlinked.tga'], main_node_index: 0, instances: 0,
  global_position_keys: { special: 'undefined' }, volume_boxes: 2,
  box: { min: [-1, -2, -3], max: [1, 2, 3], offset: [0, 0, 0], range: [1, 2, 3], center: [0, 0, 0] },
  nodes: [
    { node_index: 0, name: 'root', parentname: '', is_only: false, textures: [0, { special: 'undefined' }, 7],
      texture_references: [{ slot_index: 0, table_index: 0, state: 'resolved' }, { slot_index: 1, table_index: null, state: 'unresolved' },
        { slot_index: 2, table_index: null, state: 'unresolved' }],
      transform: { mat3: [1, 0, 0, 0, 1, 0, 0, 0, 1], offset: [0.5, 0, 0], pos: [0, 0, 0], rotangle: 0.25, rotaxis: [0, 1, 0], scale: [1, 1, 1],
        flip: [1, 1, 1], matrix: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1] },
      box: { min: [0, 0, 0], max: [1, 1, 1], offset: [0, 0, 0], range: [0.5, 0.5, 0.5], center: [0.5, 0.5, 0.5] },
      vertex_count: 3, tvertex_components: 6, face_count: 1,
      keyframe_counts: { rotation: 2, position: 0, scale: { special: 'undefined' }, texture_groups: 1 },
      numeric_fields: { finite: 60, nan: 1, positive_infinity: 0, negative_infinity: 1, undefined: 1, null: 0, min: -1e30, max: 1e30,
        exceptional_locations: [{ location: 'vertices[1][0]', category: 'nan' }, { location: 'textures[1]', category: 'undefined' },
          { location: 'rotKeyframes[0].q[3]', category: 'negative_infinity' }], exceptional_locations_omitted: 0 } },
    { node_index: 1, name: 'child', parentname: 'root', is_only: false, textures: [0],
      texture_references: [{ slot_index: 0, table_index: 0, state: 'resolved' }],
      transform: { mat3: [1, 0, 0, 0, 1, 0, 0, 0, 1], offset: [0, 0, 0], pos: [0, 1, 0], rotangle: 0, rotaxis: [0, 0, 1], scale: [2, 2, 2],
        flip: [1, 1, 1], matrix: [2, 0, 0, 0, 0, 2, 0, 0, 0, 0, 2, 0, 0, 1, 0, 1] },
      box: { min: [0, 0, 0], max: [0, 0, 0], offset: [0, 0, 0], range: [0, 0, 0], center: [0, 0, 0] },
      vertex_count: 0, tvertex_components: 0, face_count: 0,
      keyframe_counts: { rotation: 0, position: { special: 'undefined' }, scale: 0, texture_groups: 0 },
      numeric_fields: { finite: 40, nan: 0, positive_infinity: 0, negative_infinity: 0, undefined: 1, null: 0, min: 0, max: 2,
        exceptional_locations: [{ location: 'posKeyframes', category: 'undefined' }], exceptional_locations_omitted: 0 } }
  ],
  texture_declarations: [
    { texture_index: 0, constructor_pointer: '/textures/0', raw_name: 'Sky\\A B.bmp', logical_name: 'data\\texture\\Sky\\A B.bmp',
      filemanager_name: 'data\\texture\\Sky\\A B.bmp', http_path: 'data/texture/Sky/A%20B.bmp' },
    { texture_index: 1, constructor_pointer: '/textures/1', raw_name: 'unlinked.tga', logical_name: 'data\\texture\\unlinked.tga',
      filemanager_name: 'data\\texture\\unlinked.tga', http_path: 'data/texture/unlinked.tga' }
  ],
  animation_by_node_keys: true,
  numeric_fields: { finite: 20, nan: 1, positive_infinity: 1, negative_infinity: 0, undefined: 2, null: 0, min: -3, max: 300,
    exceptional_locations: [{ location: 'version', category: 'nan' }, { location: 'alpha', category: 'undefined' },
      { location: 'frameRatePerSecond', category: 'positive_infinity' }, { location: 'posKeyframes', category: 'undefined' }], exceptional_locations_omitted: 0 },
  cursor: { state: 'not_observable_from_unchanged_constructor', remaining_bytes: null }
};

const SUMMARY = `
export class SummaryLimitError extends Error { constructor() { super('model summary limit'); this.name = 'SummaryLimitError'; } }
const SENTINEL = ${JSON.stringify(SENTINEL)};
export function summarizeModel(m) {
  if (m.sentinel) return SENTINEL;
  if (m.limit) throw new SummaryLimitError();
  if (m.broken) throw new TypeError('authored summary failure');
  const n = m.textures.length;
  const out = { version: m.version ?? null, textures: m.textures,
    nodes: m.nodes.map((node, node_index) => ({ node_index, name: node.name, textures: node.textures,
      texture_references: node.textures.map((slot, slot_index) => ({ slot_index,
        table_index: Number.isInteger(slot) && slot >= 0 && slot < n ? slot : null,
        state: Number.isInteger(slot) && slot >= 0 && slot < n ? 'resolved' : 'unresolved' })),
      face_count: node.faces })),
    texture_declarations: m.textures.map((raw_name, texture_index) => {
      const logical_name = 'data\\\\texture\\\\' + raw_name, filemanager_name = logical_name.trim();
      const http_path = filemanager_name.replace(/\\\\/g, '/').split('/').map(encodeURIComponent).join('/');
      return { texture_index, constructor_pointer: '/textures/' + texture_index, raw_name, logical_name, filemanager_name,
        http_path: m.skew ? http_path.toLowerCase() : http_path };
    }) };
  if (m.huge) out.padding = 'p'.repeat(9 * 1024 * 1024);
  return out;
}
`;

const ownSuffix = fs.readFileSync(SUFFIX, 'utf8');
const SUFFIX_VARIANTS = {
  'double-result': ownSuffix.replace("postMessage({type:'ROOT_MODEL_RESULT',encoded});", "postMessage({type:'ROOT_MODEL_RESULT',encoded});postMessage({type:'ROOT_MODEL_RESULT',encoded});"),
  'no-result': ownSuffix.replace("postMessage({type:'ROOT_MODEL_RESULT',encoded});", 'void encoded;')
};

const body = (model) => Buffer.from('GRSM' + JSON.stringify(model), 'latin1');
const DEFAULT_BODY = body({ textures: [], nodes: [] });

// Authored models. Model 3: path stages, unresolved slots, zero-face link and an
// unlinked declaration. Models 10/20 are case rows with identical bytes at
// different paths (never merged). Model 5 shares 'shared.bmp' with model 3.
// Every other logical model gets the default empty body: the runtime profile
// binds all models before any pilot.
const MODELS = {
  3: { version: 1.4, textures: [' Foo\\Bar Baz.bmp ', 'shared.bmp', 'Ç®a.bmp', 'unlinked.tga'],
    nodes: [{ name: 'main', textures: [0, 1, -1, 99, 1.5], faces: 2 }, { name: 'empty', textures: [2], faces: 0 }] },
  5: { version: 1.5, textures: ['shared.bmp', 'A.BMP', 'a.bmp'], nodes: [{ name: 'n', textures: [0, 1, 2], faces: 1 }] },
  10: { version: 1.4, textures: ['case.bmp'], nodes: [{ name: 'n', textures: [0], faces: 1 }] },
  20: { version: 1.4, textures: ['case.bmp'], nodes: [{ name: 'n', textures: [0], faces: 1 }] }
};

// ---------------------------------------------------------------- authored domain

// Synthetic domain; full size by default: 936 models, 1649 relations, 21 maps,
// 3 case groups/6 rows. Global query index = 2*model+5, never the model index.
const SMALL = Object.freeze({ models: 8, relations: 11, maps: 3, case_groups: 3, case_rows: 6 });
function unboundDomain(domain = DOMAIN) {
  const k = domain.relations - domain.models;
  const relations = [];
  for (let r = 0; r < domain.relations; r++) {
    const model_index = r < 2 * k ? Math.floor(r / 2) : r - k, map_index = r % domain.maps;
    relations.push({ core_group_occurrences_pointer: `/modelGroups/${r}/occurrences`, core_group_pointer: `/modelGroups/${r}`,
      model_index, model_relation_index: r, original_relation: { expected_name_hex: '00', map_index, map_name: `map${map_index}`,
        query_index: 2 * model_index + 5, relation_index: 3 * r + 1, role: 'model', source_field_pointer: `/modelGroups/${r}/request`, source_index: r },
      source_relation_pointer: `/relations/${3 * r + 1}` });
  }
  const cases = domain.models > 60 ? [[10, 20], [30, 40], [50, 60]] : [[1, 2], [3, 4], [5, 6]];
  const groupOf = new Map(cases.flatMap((g, i) => g.map((m) => [m, i])));
  const models = Array.from({ length: domain.models }, (_, i) => {
    const rel = relations.filter((r) => r.model_index === i).map((r) => r.model_relation_index);
    const g = groupOf.get(i);
    const wire = g !== undefined ? `/data/model/case/${cases[g][0] === i ? 'AB' : 'Ab'}${g}.rsm` : `/data/model/m${i}.rsm`;
    return { catalog_current_candidate_refs: [`/queries/${2 * i + 5}/full_path_occurrences/0`], encoded_http_path: wire.slice(1), execution_admitted: false,
      expected_retained_body: i === 1 ? { bytes: DEFAULT_BODY.length, sha256: sha(DEFAULT_BODY), wire_target: wire } : null, future_011_delivery_evidence: null,
      logical_request_latin1: wire.slice(1).replace(/\//g, '\\'), map_indices: [...new Set(rel.map((r) => relations[r].original_relation.map_index))],
      metadata_bytes: 100, metadata_bytes_range: [100, 100], model_index: i, model_relation_indices: rel,
      original_query: { expected_name_hex: '00', first_relation_index: 3 * rel[0] + 1, query_index: 2 * i + 5, relation_indices: rel.map((r) => 3 * r + 1), role: 'model' },
      original_query_index: 2 * i + 5, physical_input_alias_group: g !== undefined ? g : null,
      root_observed_current_source: { bytes: null, identity: null, path: null, sha256: null }, root_observed_pin_available: false,
      root_receipt_source_pointer: null, source_holds: [], source_query_pointer: `/queries/${2 * i + 5}/query`,
      source_relation_indices: rel.map((r) => 3 * r + 1), wire_target: wire };
  });
  const maps = Array.from({ length: domain.maps }, (_, m) => {
    const rel = relations.filter((r) => r.original_relation.map_index === m);
    return { map_index: m, map_name: `map${m}`, model_indices: rel.map((r) => r.model_index), model_relation_indices: rel.map((r) => r.model_relation_index),
      original_relation_indices: rel.map((r) => r.original_relation.relation_index) };
  });
  const case_alias_groups = cases.map((g, i) => ({ actual_asset_alias_verified: false, actual_source_pins: null, alias_group_index: i,
    expected_shared_sha256: null, merge_logical_constructor_rows: false, model_indices: g, query_indices: g.map((m) => 2 * m + 5),
    requested_wire_targets: g.map((m) => models[m].wire_target), same_current_catalog_record: true }));
  return { schema: UNBOUND_PROFILE_SCHEMA, execution_admitted: false, root_bound: false, limits_admitted: false,
    models, model_group_relations: relations, maps, case_alias_groups };
}

const NODE = descriptor(process.execPath);
const HOST_DESC = hostDescriptor();

// One shared directory of default bodies per domain size (distinct paths per model).
const commonBodies = new Map();
function defaultBodyDescriptors(domain) {
  if (!commonBodies.has(domain.models)) {
    const d = freshDir();
    commonBodies.set(domain.models, Array.from({ length: domain.models }, (_, i) => descriptor(writeFile(d, `default${i}.rsm`, DEFAULT_BODY))));
  }
  return commonBodies.get(domain.models);
}

const projectionOf = (admission) => { const { host, ...rest } = admission; void host; return rest; };

// Builds one complete authored fixture world and returns paths/pins/helpers.
function fixture({ prefixVariant = '', suffixText = ownSuffix, bodies = MODELS, limits = LIMITS, domain = DOMAIN, nullBodies = [], mutateProfile } = {}) {
  const dir = freshDir();
  const unbound = unboundDomain(domain);
  const unboundPath = writeFile(dir, 'unbound.json', JSON.stringify(unbound));
  const prefix = writeFile(dir, 'prefix.js', PREFIX(prefixVariant));
  const summary = writeFile(dir, 'summary.mjs', SUMMARY);
  const suffix = writeFile(dir, 'suffix.js', suffixText);
  const bodyDir = path.join(dir, 'bodies'); fs.mkdirSync(bodyDir, { mode: 0o700 });
  const bodyPaths = {};
  for (const [i, m] of Object.entries(bodies)) bodyPaths[i] = writeFile(bodyDir, `b${i}.rsm`, Buffer.isBuffer(m) ? m : body(m));
  const defaults = defaultBodyDescriptors(domain);
  const profile = { schema: PROFILE_SCHEMA, execution_admitted: false, identity_fields: IDENTITY_FIELDS, identity_encoding: IDENTITY_ENCODING,
    limits: clone(limits), unbound_profile: descriptor(unboundPath), compiled_prefix: descriptor(prefix), summary_module: descriptor(summary),
    model_suffix: descriptor(suffix), node: NODE,
    model_group_relations: unbound.model_group_relations, maps: unbound.maps, case_alias_groups: unbound.case_alias_groups,
    models: unbound.models.map((m) => ({ ...m, body: nullBodies.includes(m.model_index) ? null
      : bodyPaths[m.model_index] ? descriptor(bodyPaths[m.model_index]) : defaults[m.model_index] })) };
  mutateProfile?.(profile);
  const profilePath = writeFile(dir, 'profile.json', JSON.stringify(profile));
  const profilePin = pinOf(profilePath);
  const testing = { unboundPin: pinOf(unboundPath), prefixPin: pinOf(prefix), summaryPin: pinOf(summary),
    limits: limits === LIMITS ? undefined : limits, domain: domain === DOMAIN ? undefined : domain, log: () => {} };
  const base = (over) => ({ schema: ADMISSION_SCHEMA, root_bound: true, execution_admitted: true, mode: 'pilot', profile_sha256: profilePin.sha256,
    host: HOST_DESC, output_path: path.join(dir, `out${seq++}`), required_head: 'a'.repeat(40),
    guard_qualification: { schema: GUARD_QUALIFICATION_SCHEMA, sampled_rss_bytes: LIMITS.outer_sampled_rss_bytes, receipt_sha256: 'b'.repeat(64) },
    selected_model_indices: [3], consumed_pilot: null, ...over });
  // The approved source binding is the projection of `approved`; the admission
  // file is `approved` with `tampered` applied (equal unless tampering).
  const admit = (over = {}, tampered = {}) => {
    const approved = base(over);
    const a = { ...approved, ...tampered };
    const binding = { execution_admitted: true, runtime_profile: profilePin, admission_projection: projectionOf(approved) };
    return { path: writeFile(dir, `admission${seq++}.json`, JSON.stringify(a)), output: a.output_path, admission: a, binding,
      testing: { ...testing, binding } };
  };
  const run = (a) => runHost({ profile: profilePath, admission: a.path }, a.testing);
  return { dir, unbound, profile, profilePath, profilePin, testing, admit, run, bodyPaths, prefix, summary, unboundPath };
}

const readOut = (out, name) => JSON.parse(fs.readFileSync(path.join(out, name), 'utf8'));
const fdCount = () => fs.readdirSync('/dev/fd').length;

// Authored close fault: the first descriptor opened for each target path throws
// EIO on its first close and stays open (no retry); the test closes it after.
function injectCloseFailure(targets) {
  const realOpen = fs.openSync, realClose = fs.closeSync;
  const fds = new Map(), injected = [];
  fs.openSync = function openSync(p, ...rest) { const fd = realOpen.call(fs, p, ...rest); if (targets.includes(p) && !fds.has(p)) fds.set(p, fd); return fd; };
  fs.closeSync = function closeSync(fd) {
    if ([...fds.values()].includes(fd) && !injected.includes(fd)) { injected.push(fd); const e = new Error('authored close failure'); e.code = 'EIO'; throw e; }
    return realClose.call(fs, fd);
  };
  return { injected, restore() { fs.openSync = realOpen; fs.closeSync = realClose; for (const fd of injected) realClose.call(fs, fd); } };
}

// Authored partial-open fault: the nth descriptor opened for `target` throws EIO
// on its first read and (optionally) on its only close, staying open; the test
// closes only that owned descriptor after restore.
function injectPartialOpen(target, nth, { closeFails = true, raw = false } = {}) {
  const realOpen = fs.openSync, realRead = fs.readSync, realClose = fs.closeSync;
  let opens = 0, victim = null, closeCalls = 0, readCalls = 0;
  fs.openSync = function openSync(p, ...rest) { const fd = realOpen.call(fs, p, ...rest); if (p === target && ++opens === nth) victim = fd; return fd; };
  fs.readSync = function readSync(fd, ...rest) {
    if (fd === victim && readCalls === 0) { readCalls++; if (raw) throw 'authored raw read fault'; const e = new Error('authored read failure'); e.code = 'EIO'; throw e; }
    return realRead.call(fs, fd, ...rest);
  };
  fs.closeSync = function closeSync(fd) {
    if (fd === victim && closeFails && closeCalls === 0) { closeCalls++; const e = new Error('authored close failure'); e.code = 'EIO'; throw e; }
    return realClose.call(fs, fd);
  };
  return { get victim() { return victim; }, get readCalls() { return readCalls; }, get closeCalls() { return closeCalls; },
    restore() { fs.openSync = realOpen; fs.readSync = realRead; fs.closeSync = realClose; if (victim !== null && closeCalls > 0) realClose.call(fs, victim); } };
}

// ---------------------------------------------------------------- controls

test('default import and CLI refuse before any I/O; the source binding stays null', async () => {
  assert.equal(ROOT_SOURCE_BINDING, null);
  const dir = freshDir();
  const missing = { profile: path.join(dir, 'nope.json'), admission: path.join(dir, 'nope2.json') };
  await assert.rejects(runHost(missing), (e) => e instanceof Refusal && e.code === 'unbound');
  await assert.rejects(runHost(missing, { log: () => {} }), (e) => e instanceof Refusal && e.code === 'unbound');
  const r = spawnSync(process.execPath, [HOST, '--profile', missing.profile, '--admission', missing.admission], { encoding: 'utf8' });
  assert.equal(r.status, 2);
  assert.match(r.stderr, /refused: source binding is unbound/);
  assert.equal(r.stdout, '');
  const bare = spawnSync(process.execPath, [HOST], { encoding: 'utf8' });
  assert.equal(bare.status, 2);
  assert.deepEqual(fs.readdirSync(dir), []);
});

test('typed logical/global/case joins and complete source records', () => {
  const f = fixture();
  const bound = validateProfile(f.profile, f.unbound, { prefixPin: f.testing.prefixPin, summaryPin: f.testing.summaryPin, unboundPin: f.testing.unboundPin });
  assert.equal(bound.records.length, 936);
  assert.equal(bound.relations.length, 1649);
  assert.equal(bound.maps.length, 21);
  assert.deepEqual(bound.cases.map((g) => g.model_indices), [[10, 20], [30, 40], [50, 60]]);
  assert.equal(bound.records[3].original_query_index, 11);
  assert.equal(bound.bodies.filter(Boolean).length, 936);
  const opts = { prefixPin: f.testing.prefixPin, summaryPin: f.testing.summaryPin, unboundPin: f.testing.unboundPin };
  const bad = (mut, re) => { const p = clone(f.profile), u = clone(f.unbound); mut(p, u); assert.throws(() => validateProfile(p, u, opts), re); };
  bad((p, u) => { u.model_group_relations[7].original_relation.query_index = 3; p.model_group_relations = u.model_group_relations; }, /original relation join/);
  bad((p, u) => { u.case_alias_groups[0].merge_logical_constructor_rows = true; p.case_alias_groups = u.case_alias_groups; }, /potential case group/);
  bad((p, u) => { u.case_alias_groups[1].expected_shared_sha256 = 'c'.repeat(64); p.case_alias_groups = u.case_alias_groups; }, /potential case group/);
  bad((p) => { p.models[20].wire_target = p.models[20].wire_target.toLowerCase(); }, /typed source record differs/);
  bad((p) => { p.models[3].original_query_index = 3; }, /typed source record differs/);
  bad((p) => { p.models[3].nulls_removed = true; }, /typed source record differs/);
  bad((p) => { delete p.models[3].body; }, /body slot required/);
  bad((p) => { p.models[20].body = p.models[10].body; }, /body path shared/);
  bad((p) => { p.models[1].body = p.models[5].body; p.models[5].body = null; }, /known retained pin/);
  bad((p, u) => { u.models.pop(); p.models.pop(); }, /936 logical models/);
  bad((p, u) => { u.maps[2].model_indices[0] = 0; p.maps = u.maps; }, /model indices differ/);
  // Metadata-only clones with a broken original-relation join (unbound and runtime records equal).
  for (const mut of [(m) => { m.source_relation_indices[0] = 99999999; }, (m) => { m.original_query.relation_indices[1] = 99999999; },
    (m) => { m.original_query.first_relation_index = 99999999; }]) {
    bad((p, u) => { mut(u.models[0]); mut(p.models[0]); }, /models\[0\]: original relation indices differ from the relation table/);
  }
  bad((p, u) => { u.models[30].physical_input_alias_group = null; p.models[30].physical_input_alias_group = null; }, /case group 1: row 0 join/);
  bad((p) => { p.models[3].body = { ...p.models[3].body, bytes: LIMITS.input_body_bytes + 1 }; }, /bytes out of bound/);
  bad((p) => { p.limits = { ...p.limits, worker_heap_mb: 2048 }; }, /limits differ/);
  assert.throws(() => validateUnboundDomain({ ...f.unbound, execution_admitted: true }), /admission flag/);
});

test('fixed path stages, slots, unlinked and zero-face declarations (literal expectations)', () => {
  assert.deepEqual(stagesOf(' Foo\\Bar Baz.bmp '), { logical_name: 'data\\texture\\ Foo\\Bar Baz.bmp ',
    filemanager_name: 'data\\texture\\ Foo\\Bar Baz.bmp', http_path: 'data/texture/%20Foo/Bar%20Baz.bmp' });
  assert.equal(stagesOf('Ç®a.bmp').http_path, 'data/texture/%C3%87%C2%AEa.bmp');
  assert.equal(stagesOf('A.BMP').http_path, 'data/texture/A.BMP');
  assert.equal(stagesOf('\t x.bmp　').filemanager_name, 'data\\texture\\\t x.bmp');
  checkSuffix(ownSuffix);
  assert.throws(() => checkSuffix(ownSuffix.replace('performance.now() + 48000', 'performance.now() + 47000')), /inner diagnostic deadline/);
  assert.throws(() => checkSuffix(ownSuffix.replace('const ROOT_MODEL_LIMIT = 8 * 1024 * 1024;', 'const ROOT_MODEL_LIMIT = 9e9;')), /result bound/);
  assert.throws(() => checkSuffix(`${ownSuffix}\nfetch('/x');`), /must not reference fetch/);
});

test('pilot: genuine authored constructions, exact nested targets, literal FD accounting, pinned-profile domain retention', async () => {
  const f = fixture();
  const a = f.admit({ selected_model_indices: [3, 5, 10, 20] });
  const before = fdCount();
  const r = await f.run(a);
  assert.equal(fdCount(), before);
  assert.equal(r.status, 'observed', JSON.stringify(r));
  assert.deepEqual(r.counts, { outside_batch: 932, not_started: 0, started: 0, failed: 0, returned: 4 });
  const manifest = readOut(a.output, 'MANIFEST.json');
  // One logical body staged at a time; its postcheck reread is a second literal FD.
  assert.deepEqual(manifest.body_fds, { max_staged_bodies: 1, max_open_body_fds: 2, close_failures: 0 });
  assert.equal(manifest.first_failure, null);
  assert.ok(manifest.source_postchecks.every((p) => p.ok));
  assert.deepEqual(manifest.held_closes.map((c) => [c.label, c.closed]), [['profile', true], ['admission', true], ['unbound_profile', true],
    ['compiled_prefix', true], ['summary_module', true], ['model_suffix', true]]);
  assert.deepEqual(manifest.body_final_rereads.map((x) => [x.model_index, x.ok]), [[3, true], [5, true], [10, true], [20, true]]);
  assert.equal(manifest.required_head.verified_by_host, false);
  assert.equal(manifest.guard_qualification.this_run_guard_verified_by_host, false);
  assert.equal(manifest.claims.qualification, false);
  assert.equal(manifest.claims.runtime_ready, false);
  assert.equal(fs.statSync(a.output).mode & 0o777, 0o700);
  for (const name of fs.readdirSync(a.output)) assert.equal(fs.statSync(path.join(a.output, name)).mode & 0o777, 0o600);
  const res3 = readOut(a.output, 'model-0003.result.json');
  assert.equal(res3.outcome, 'returned');
  assert.equal(res3.constructor_returned, true);
  assert.deepEqual(res3.summary.textures, [' Foo\\Bar Baz.bmp ', 'shared.bmp', 'Ç®a.bmp', 'unlinked.tga']);
  assert.deepEqual(res3.summary.nodes[0].texture_references.map((x) => x.state), ['resolved', 'resolved', 'unresolved', 'unresolved', 'unresolved']);
  const host3 = readOut(a.output, 'model-0003.host.json');
  assert.equal(host3.lifecycle.positive_exit, true);
  assert.equal(host3.lifecycle.streams_drained, true);
  assert.equal(host3.lifecycle.thread_ready, 1);
  assert.equal(host3.closing.body_handouts, 1);
  assert.deepEqual(host3.closing.fetch, []);
  assert.equal(host3.body.fd_closed, true);
  assert.equal(host3.body.close_error, null);
  assert.equal(host3.source_record.original_query_index, 11);
  const red = host3.reduced;
  assert.deepEqual(red.unresolved_slots, [{ node_index: 0, slot_index: 2, slot: -1 }, { node_index: 0, slot_index: 3, slot: 99 }, { node_index: 0, slot_index: 4, slot: 1.5 }]);
  assert.deepEqual(red.declarations.map((d) => [d.http_path, d.node_links, d.zero_face_node_links]), [
    ['data/texture/%20Foo/Bar%20Baz.bmp', [{ node_index: 0, slot_index: 0 }], 0],
    ['data/texture/shared.bmp', [{ node_index: 0, slot_index: 1 }], 0],
    ['data/texture/%C3%87%C2%AEa.bmp', [{ node_index: 1, slot_index: 0 }], 1],
    ['data/texture/unlinked.tga', [], 0]]);
  assert.deepEqual(red.counts, { nodes: 2, declarations: 4, resolved_slots: 3, unresolved_slots: 3, unlinked_declarations: 1 });
  assert.deepEqual(red.source_links.map((l) => [l.model_relation_index, l.map_index, l.core_group_pointer]), [[6, 6, '/modelGroups/6'], [7, 7, '/modelGroups/7']]);
  const nested = readOut(a.output, 'NESTED_TARGETS.json');
  assert.equal(nested.complete, true);
  assert.deepEqual(nested.targets.map((t) => [t.http_path, t.declarations.map((d) => `${d.model_index}:${d.texture_index}`)]), [
    ['data/texture/%20Foo/Bar%20Baz.bmp', ['3:0']], ['data/texture/shared.bmp', ['3:1', '5:0']],
    ['data/texture/%C3%87%C2%AEa.bmp', ['3:2']], ['data/texture/unlinked.tga', ['3:3']],
    ['data/texture/A.BMP', ['5:1']], ['data/texture/a.bmp', ['5:2']], ['data/texture/case.bmp', ['10:0', '20:0']]]);
  assert.deepEqual({ ...nested.totals, string_code_units: 0 }, { nodes: 5, declarations: 9, node_slots: 11, string_code_units: 0, nested_targets: 7 });
  // Case rows 10/20: identical bytes at distinct paths stay two logical jobs.
  const h10 = readOut(a.output, 'model-0010.host.json'), h20 = readOut(a.output, 'model-0020.host.json');
  assert.equal(h10.body.sha256, h20.body.sha256);
  assert.notEqual(h10.body.path, h20.body.path);
  assert.equal(manifest.jobs[10].status, 'returned');
  assert.equal(manifest.jobs[20].status, 'returned');

  // Consumer reconstruction from the declared artifact set only: the output
  // directory holds exactly the declared files plus MANIFEST.json, each with its
  // recorded hash, and every table/pointer comes from the pinned profile.
  assert.deepEqual(fs.readdirSync(a.output).sort(), [...manifest.files.map((x) => x.name), 'MANIFEST.json'].sort());
  for (const x of manifest.files) assert.equal(sha(fs.readFileSync(path.join(a.output, x.name))), x.sha256);
  const dr = manifest.domain_retention;
  assert.equal(dr.mode, 'pinned-runtime-profile-plus-job-pointers');
  assert.deepEqual(dr.counts, { models: 936, relations: 1649, maps: 21, case_groups: 3, case_rows: 6 });
  const profileBytes = fs.readFileSync(dr.profile.path);
  assert.equal(sha(profileBytes), dr.profile.sha256);
  assert.equal(dr.profile.sha256, f.profilePin.sha256);
  const prof = JSON.parse(profileBytes.toString('utf8'));
  assert.deepEqual([prof.models.length, prof.model_group_relations.length, prof.maps.length, prof.case_alias_groups.flatMap((g) => g.model_indices).length], [936, 1649, 21, 6]);
  assert.equal(manifest.jobs.length, 936);
  manifest.jobs.forEach((j, i) => {
    assert.equal(j.model_index, i);
    assert.equal(j.profile_pointer, `/models/${i}`);
    const { body: _b, ...record } = prof.models[i];
    assert.deepEqual(record, f.unbound.models[i]);
    if (j.status === 'returned') assert.deepEqual(readOut(a.output, j.report).source_record, record);
  });
  for (const l of red.source_links) {
    const rel = prof.model_group_relations[l.model_relation_index];
    assert.deepEqual([rel.model_index, rel.original_relation.map_index, rel.core_group_pointer, rel.original_relation.relation_index], [3, l.map_index, l.core_group_pointer, l.original_relation_index]);
  }
});

test('complete summary sentinel is retained unchanged (deep equality of the whole summary)', async () => {
  const f = fixture({ bodies: { 3: { sentinel: true, textures: [], nodes: [] } } });
  const a = f.admit({ selected_model_indices: [3] });
  const r = await f.run(a);
  assert.equal(r.status, 'observed', JSON.stringify(r));
  const res = readOut(a.output, 'model-0003.result.json');
  assert.deepEqual(res.summary, clone(SENTINEL));
  assert.deepEqual(res.summary.version, { special: 'NaN' });
  assert.deepEqual(res.summary.nodes[0].keyframe_counts.scale, { special: 'undefined' });
  assert.deepEqual(res.summary.nodes[0].textures[1], { special: 'undefined' });
  const red = readOut(a.output, 'model-0003.host.json').reduced;
  assert.deepEqual(red.unresolved_slots, [{ node_index: 0, slot_index: 1, slot: { special: 'undefined' } }, { node_index: 0, slot_index: 2, slot: 7 }]);
  assert.deepEqual(red.declarations.map((d) => [d.http_path, d.node_links.length, d.zero_face_node_links]), [['data/texture/Sky/A%20B.bmp', 2, 1], ['data/texture/unlinked.tga', 0, 0]]);
  assert.deepEqual(readOut(a.output, 'NESTED_TARGETS.json').models[0].declarations[1].node_links, []);
});

test('constructor throw is retained evidence; later jobs are not_started; first failure sticky', async () => {
  const f = fixture({ bodies: { ...MODELS, 4: Buffer.from('THRWxx', 'latin1') } });
  const a = f.admit({ selected_model_indices: [3, 4, 5] });
  const r = await f.run(a);
  assert.equal(r.status, 'failed');
  assert.deepEqual(r.first_failure, { phase: 'job', model_index: 4, failure_class: 'constructor', outcome: 'constructor_exception', message: null });
  const m = readOut(a.output, 'MANIFEST.json');
  assert.deepEqual([3, 4, 5].map((i) => m.jobs[i].status), ['returned', 'failed', 'not_started']);
  assert.match(m.jobs[5].reason, /fail-fast after model-0004 constructor failure/);
  const h4 = readOut(a.output, 'model-0004.host.json');
  assert.equal(h4.constructor_returned, false);
  assert.equal(h4.exception.message, 'authored constructor throw');
  assert.equal(h4.reduced, null);
  assert.equal(h4.lifecycle.positive_exit, true);
  const nested = readOut(a.output, 'NESTED_TARGETS.json');
  assert.equal(nested.complete, false);
  assert.equal(nested.targets, null);
  assert.deepEqual(nested.unknown_model_indices, [4, 5]);
});

test('late-returning constructor: timeout keeps constructor_returned:true; summary failure keeps it too', async () => {
  const f = fixture({ prefixVariant: 'late-clock', bodies: { 3: Buffer.from('LATExx', 'latin1') } });
  const a = f.admit({ selected_model_indices: [3] });
  const r = await f.run(a);
  assert.equal(r.status, 'failed');
  assert.equal(r.first_failure.failure_class, 'limit');
  assert.equal(r.first_failure.outcome, 'timeout');
  const res = readOut(a.output, 'model-0003.result.json');
  assert.equal(res.constructor_returned, true);
  assert.equal(res.outcome, 'timeout');
  assert.deepEqual([res.exception.phase, res.exception.message], ['constructor', 'worker deadline']);
  assert.deepEqual(res.stages, ['input']);
  const g = fixture({ bodies: { 3: { ...MODELS[3], broken: true } } });
  const b = g.admit({ selected_model_indices: [3] });
  await g.run(b);
  const h = readOut(b.output, 'model-0003.host.json');
  assert.deepEqual([h.outcome, h.constructor_returned], ['summary_error', true]);
});

test('summary error, summary limit, reducer mismatch and result limit are distinct classes', async () => {
  const cases = [
    [{ ...MODELS[3], broken: true }, 'summary', 'summary_error'],
    [{ ...MODELS[3], limit: true }, 'summary', 'summary_limit'],
    [{ ...MODELS[3], skew: true }, 'reducer', 'returned'],
    [{ ...MODELS[3], huge: true }, 'limit', 'result_limit'],
    [Buffer.from('MUTAxxxx', 'latin1'), 'preservation', 'returned']
  ];
  for (const [model, cls, outcome] of cases) {
    const f = fixture({ bodies: { 3: model, 5: MODELS[5] } });
    const a = f.admit({ selected_model_indices: [3, 5] });
    const r = await f.run(a);
    assert.equal(r.status, 'failed', cls);
    assert.equal(r.first_failure.failure_class, cls, JSON.stringify(r.first_failure));
    assert.equal(r.first_failure.outcome, outcome);
    const m = readOut(a.output, 'MANIFEST.json');
    assert.equal(m.jobs[5].status, 'not_started');
    assert.equal(m.counts.outside_batch, 934);
  }
});

test('string accounting: every summary string value, UTF-16 units, repeats, surrogates, keys excluded, across jobs', async () => {
  const record = { model_index: 0, model_relation_indices: [] };
  // Hand-counted literal: '😀' 2 (texture) + 'ab' 2 (name) + 'ab' 2 (parentname)
  // + 'NaN' 3 (marker slot) + 'resolved' 8 + 'unresolved' 10 + '/textures/0' 11
  // + raw '😀' 2 + logical 15 + filemanager 15 + http 25 + cursor 'x' 1 = 96.
  // Keys such as 'state', 'special' and 'parentname' are not counted.
  const summary = { textures: ['😀'], cursor: { state: 'x' },
    nodes: [{ node_index: 0, name: 'ab', parentname: 'ab', textures: [0, { special: 'NaN' }], face_count: 1,
      texture_references: [{ slot_index: 0, table_index: 0, state: 'resolved' }, { slot_index: 1, table_index: null, state: 'unresolved' }] }],
    texture_declarations: [{ texture_index: 0, constructor_pointer: '/textures/0', raw_name: '😀', logical_name: 'data\\texture\\😀',
      filemanager_name: 'data\\texture\\😀', http_path: 'data/texture/%F0%9F%98%80' }] };
  const totals = newReducerTotals();
  reduceModel(summary, record, [], totals);
  assert.equal(totals.string_code_units, 96);
  reduceModel(summary, record, [], totals);
  assert.equal(totals.string_code_units, 192);
  const caps = (n) => ({ ...LIMITS.declaration_reducer_global, string_code_units: n });
  const exact = newReducerTotals();
  reduceModel(summary, record, [], exact, caps(192));
  reduceModel(summary, record, [], exact, caps(192));
  assert.equal(exact.string_code_units, 192);
  const over = newReducerTotals();
  reduceModel(summary, record, [], over, caps(191));
  assert.throws(() => reduceModel(summary, record, [], over, caps(191)), /reducer limit string_code_units/);
  // Two 600000-unit node names: each under the per-string summary bound, the
  // aggregate over the unchanged 1048576 reducer-global cap.
  const big = (name) => ({ textures: [], texture_declarations: [], nodes: [{ node_index: 0, name, textures: [], texture_references: [] }] });
  const t2 = newReducerTotals();
  reduceModel(big('x'.repeat(600000)), record, [], t2);
  assert.throws(() => reduceModel(big('y'.repeat(600000)), record, [], t2), /reducer limit string_code_units/);
  const t3 = newReducerTotals();
  assert.throws(() => reduceModel({ textures: [], texture_declarations: [], nodes: [{ node_index: 0, name: 'x'.repeat(600000), parentname: 'y'.repeat(600000), textures: [], texture_references: [] }] }, record, [], t3), /string_code_units/);
  // Accumulation across jobs of one host invocation: model 3's summary carries
  // 505 units and model 5's 275, so a 600 cap admits 3 and refuses 5 (780).
  const limits = { ...LIMITS, declaration_reducer_global: { ...LIMITS.declaration_reducer_global, string_code_units: 600 } };
  const f = fixture({ limits });
  const a = f.admit({ selected_model_indices: [3, 5] });
  const r = await f.run(a);
  assert.deepEqual([r.first_failure.model_index, r.first_failure.failure_class, r.first_failure.message], [5, 'limit', 'reducer limit string_code_units']);
  assert.equal(readOut(a.output, 'MANIFEST.json').jobs[3].status, 'returned');
});

test('reducer-global caps fail with partial evidence, never truncation', async () => {
  const limits = { ...LIMITS, declaration_reducer_global: { ...LIMITS.declaration_reducer_global, declarations: 5 } };
  const f = fixture({ limits });
  const a = f.admit({ selected_model_indices: [3, 5] });
  const r = await f.run(a);
  assert.equal(r.first_failure.model_index, 5);
  assert.equal(r.first_failure.failure_class, 'limit');
  const nested = readOut(a.output, 'NESTED_TARGETS.json');
  assert.deepEqual(nested.returned_model_indices, [3]);
  assert.equal(nested.targets, null);
  const totals = newReducerTotals();
  assert.throws(() => reduceModel({ textures: [], texture_declarations: [], nodes: [{ a: [[[[[[1]]]]]] }] }, { model_index: 0, model_relation_indices: [] }, [], totals,
    { ...LIMITS.declaration_reducer_global, json_depth: 4 }), /json_depth/);
});

test('lifecycle: missing/double THREAD_READY, early/duplicate/missing result, async fault, stream cap', async () => {
  const runs = [
    [{ prefixVariant: 'no-ready' }, /bootstrap failed: suffix handler not installed/],
    [{ prefixVariant: 'double-ready' }, /bootstrap failed: suffix handler not installed/],
    [{ prefixVariant: 'early-result' }, /terminal result before ROOT_MODEL_CONSTRUCT/],
    [{ prefixVariant: 'double-result' }, /duplicate terminal ROOT_MODEL_RESULT/],
    [{ prefixVariant: 'no-result', limits: { ...LIMITS, worker_deadline_ms: 1500 } }, /worker deadline expired/],
    [{ prefixVariant: 'async-throw' }, /worker error|worker exit code 1/],
    [{ prefixVariant: 'chatty', limits: { ...LIMITS, stdout_bytes: 64 } }, /stdout exceeded/],
    [{ bodies: { 3: Buffer.from('FETC{"textures":[],"nodes":[]}', 'latin1') } }, /fetch call\(s\) attempted/]
  ];
  for (const [opts, re] of runs) {
    const f = fixture({ bodies: { 3: MODELS[3] }, ...opts });
    const a = f.admit({ selected_model_indices: [3] });
    const r = await f.run(a);
    assert.equal(r.status, 'failed');
    assert.equal(r.first_failure.failure_class, 'host', `${re}`);
    const h = readOut(a.output, 'model-0003.host.json');
    assert.match(h.reasons.join('\n'), re);
    assert.equal(readOut(a.output, 'MANIFEST.json').body_final_rereads[0].ok, true);
  }
  // A changed suffix protocol is refused before any Worker starts.
  for (const text of Object.values(SUFFIX_VARIANTS)) {
    const f = fixture({ bodies: { 3: MODELS[3] }, suffixText: text });
    const a = f.admit({ selected_model_indices: [3] });
    const r = await f.run(a);
    assert.equal(r.first_failure.phase, 'execute');
    assert.match(r.first_failure.message, /suffix protocol/);
    assert.equal(readOut(a.output, 'MANIFEST.json').jobs[3].status, 'not_started');
  }
});

test('close outcomes: body close error fails the batch; no fd_closed:true; later jobs never start', async () => {
  const f = fixture();
  const a = f.admit({ selected_model_indices: [3, 5] });
  const fault = injectCloseFailure([f.bodyPaths[3]]);
  let r;
  try { r = await f.run(a); } finally { fault.restore(); }
  assert.equal(fault.injected.length, 1);
  assert.equal(r.status, 'failed');
  assert.deepEqual(r.first_failure, { phase: 'job', model_index: 3, failure_class: 'host', outcome: 'returned', message: 'body descriptor close failed: authored close failure' });
  const m = readOut(a.output, 'MANIFEST.json');
  assert.equal(m.status, 'failed');
  assert.deepEqual([m.jobs[3].status, m.jobs[5].status], ['failed', 'not_started']);
  assert.equal(m.body_fds.close_failures, 1);
  const h3 = readOut(a.output, 'model-0003.host.json');
  assert.equal(h3.body.fd_closed, false);
  assert.equal(h3.body.close_error.code, 'EIO');
  assert.equal(h3.body.postcheck.ok, true);
  assert.equal(readOut(a.output, 'NESTED_TARGETS.json').complete, false);
});

test('close outcomes: held-source close error fails before terminal publication', async () => {
  const f = fixture();
  const a = f.admit({ selected_model_indices: [3] });
  const fault = injectCloseFailure([a.path]);
  let r;
  try { r = await f.run(a); } finally { fault.restore(); }
  assert.equal(fault.injected.length, 1);
  assert.equal(r.status, 'failed');
  assert.deepEqual([r.first_failure.phase, r.first_failure.failure_class, r.first_failure.message], ['held-close', 'host', 'admission: authored close failure']);
  // The published manifest already contains the close outcome: closure preceded publication.
  const m = readOut(a.output, 'MANIFEST.json');
  assert.equal(m.status, 'failed');
  assert.equal(m.jobs[3].status, 'returned');
  assert.deepEqual(m.held_closes.find((c) => c.label === 'admission'), { label: 'admission', path: a.path, closed: false, error: m.held_closes.find((c) => c.label === 'admission').error });
  assert.equal(m.held_closes.find((c) => c.label === 'admission').error.code, 'EIO');
  assert.ok(m.held_closes.filter((c) => c.label !== 'admission').every((c) => c.closed));
});

test('close outcomes: earlier constructor failure stays primary; cleanup failures appended; partial-open path keeps both errors', async () => {
  const f = fixture({ bodies: { ...MODELS, 4: Buffer.from('THRWxx', 'latin1') } });
  const a = f.admit({ selected_model_indices: [4, 5] });
  const fault = injectCloseFailure([f.bodyPaths[4], a.path]);
  let r;
  try { r = await f.run(a); } finally { fault.restore(); }
  assert.equal(fault.injected.length, 2);
  assert.deepEqual([r.first_failure.phase, r.first_failure.failure_class, r.first_failure.model_index], ['job', 'constructor', 4]);
  const m = readOut(a.output, 'MANIFEST.json');
  assert.deepEqual(m.later_failures.map((x) => [x.phase, x.model_index, x.failure_class]), [['body-close', 4, 'host'], ['held-close', null, 'host']]);
  assert.equal(m.jobs[5].status, 'not_started');
  assert.equal(readOut(a.output, 'model-0004.host.json').body.fd_closed, false);
  // Partial-open/exception path: a read failure keeps its message; the failed close is appended.
  const target = f.bodyPaths[3];
  const g = injectCloseFailure([target]);
  try {
    assert.throws(() => readPinnedFile(target, { pin: { bytes: 1, sha256: '0'.repeat(64) }, maxBytes: 1 << 20, label: 'partial' }),
      /bytes\/sha256 differ from pin; descriptor close after failure also failed: authored close failure/);
  } finally { g.restore(); }
  assert.equal(g.injected.length, 1);
});

test('combined fault: returned constructor + body-close EIO + reducer overflow keeps close primary and skips the reducer', async () => {
  // Model 3 declares 4 textures; a 1-declaration reducer cap would overflow.
  const limits = { ...LIMITS, declaration_reducer_global: { ...LIMITS.declaration_reducer_global, declarations: 1 } };
  const f = fixture({ limits });
  const a = f.admit({ selected_model_indices: [3, 5] });
  const fault = injectCloseFailure([f.bodyPaths[3]]);
  let r;
  try { r = await f.run(a); } finally { fault.restore(); }
  assert.equal(fault.injected.length, 1);
  assert.deepEqual(r.first_failure, { phase: 'job', model_index: 3, failure_class: 'host', outcome: 'returned', message: 'body descriptor close failed: authored close failure' });
  const m = readOut(a.output, 'MANIFEST.json');
  assert.deepEqual(m.later_failures, []);
  assert.deepEqual([m.jobs[3].status, m.jobs[5].status], ['failed', 'not_started']);
  const h3 = readOut(a.output, 'model-0003.host.json');
  assert.equal(h3.reduced, null);
  assert.equal(h3.constructor_returned, true);
  assert.deepEqual(h3.reasons, ['body descriptor close failed: authored close failure', 'reducer skipped after body preservation/close failure']);
  assert.ok(!h3.reasons.some((x) => /reducer limit/.test(x)));
  assert.equal(typeof h3.result_file.name, 'string');
  assert.deepEqual(m.body_fds, { max_staged_bodies: 1, max_open_body_fds: 2, close_failures: 1 });
  // Earlier constructor throw stays primary; close is appended; no reducer work.
  const g = fixture({ limits, bodies: { ...MODELS, 4: Buffer.from('THRWxx', 'latin1') } });
  const b = g.admit({ selected_model_indices: [4, 5] });
  const fault2 = injectCloseFailure([g.bodyPaths[4]]);
  let r2;
  try { r2 = await g.run(b); } finally { fault2.restore(); }
  assert.deepEqual([r2.first_failure.phase, r2.first_failure.failure_class, r2.first_failure.model_index], ['job', 'constructor', 4]);
  const m2 = readOut(b.output, 'MANIFEST.json');
  assert.deepEqual(m2.later_failures.map((x) => [x.phase, x.model_index, x.failure_class, x.message]), [['body-close', 4, 'host', 'authored close failure']]);
  assert.ok(!readOut(b.output, 'model-0004.host.json').reasons.some((x) => /reducer/.test(x)));
  assert.equal(m2.jobs[5].status, 'not_started');
});

test('combined fault: failed postcheck reread close plus reducer overflow keeps preservation primary', async () => {
  const limits = { ...LIMITS, declaration_reducer_global: { ...LIMITS.declaration_reducer_global, declarations: 1 } };
  const f = fixture({ limits });
  const a = f.admit({ selected_model_indices: [3, 5] });
  // Open 1 = staging, open 2 = postcheck reread (read EIO, close EIO).
  const fault = injectPartialOpen(f.bodyPaths[3], 2);
  let r;
  try { r = await f.run(a); } finally { fault.restore(); }
  assert.deepEqual([fault.readCalls, fault.closeCalls], [1, 1]);
  assert.deepEqual([r.first_failure.phase, r.first_failure.failure_class, r.first_failure.model_index], ['job', 'preservation', 3]);
  assert.match(r.first_failure.message, /^body postcheck: reread: authored read failure; descriptor close after failure also failed: authored close failure$/);
  const m = readOut(a.output, 'MANIFEST.json');
  assert.deepEqual(m.later_failures, []);
  const h3 = readOut(a.output, 'model-0003.host.json');
  assert.equal(h3.reduced, null);
  assert.ok(!h3.reasons.some((x) => /reducer limit/.test(x)));
  assert.deepEqual([h3.body.postcheck.reread_opened, h3.body.postcheck.reread_fd_closed, h3.body.fd_closed], [true, false, true]);
  // Staging FD + leaked reread FD = 2; the leaked one is never counted closed.
  assert.deepEqual(m.body_fds, { max_staged_bodies: 1, max_open_body_fds: 2, close_failures: 1 });
  assert.equal(m.jobs[5].status, 'not_started');
});

test('partial open: staging read EIO + close EIO retains both errors and literal FD accounting', async () => {
  const f = fixture();
  const a = f.admit({ selected_model_indices: [3, 5] });
  const fault = injectPartialOpen(f.bodyPaths[3], 1);
  let r;
  try { r = await f.run(a); } finally { fault.restore(); }
  assert.deepEqual([fault.readCalls, fault.closeCalls], [1, 1]);
  assert.deepEqual(r.first_failure, { phase: 'body-staging', model_index: 3, failure_class: 'host',
    message: 'authored read failure; descriptor close after failure also failed: authored close failure' });
  const m = readOut(a.output, 'MANIFEST.json');
  // The leaked staging FD stays counted open, so the final reread is a second literal FD.
  assert.deepEqual(m.body_fds, { max_staged_bodies: 0, max_open_body_fds: 2, close_failures: 1 });
  assert.deepEqual([m.jobs[3].status, m.jobs[5].status], ['failed', 'not_started']);
  // Final-reread partial open: opens 1 staging, 2 postcheck, 3 final reread.
  const g = fixture();
  const b = g.admit({ selected_model_indices: [3] });
  const fault2 = injectPartialOpen(g.bodyPaths[3], 3);
  let r2;
  try { r2 = await g.run(b); } finally { fault2.restore(); }
  assert.deepEqual([fault2.readCalls, fault2.closeCalls], [1, 1]);
  assert.deepEqual([r2.first_failure.phase, r2.first_failure.failure_class, r2.first_failure.model_index], ['body-final-reread', 'preservation', 3]);
  const m2 = readOut(b.output, 'MANIFEST.json');
  assert.match(m2.body_final_rereads[0].failure, /authored read failure; descriptor close after failure also failed: authored close failure/);
  assert.deepEqual(m2.body_fds, { max_staged_bodies: 1, max_open_body_fds: 2, close_failures: 1 });
  // Partial open whose close succeeds: counted opened and closed, no failure.
  const h = fixture();
  const c = h.admit({ selected_model_indices: [3] });
  const fault3 = injectPartialOpen(h.bodyPaths[3], 1, { closeFails: false });
  try { await h.run(c); } finally { fault3.restore(); }
  assert.deepEqual(readOut(c.output, 'MANIFEST.json').body_fds, { max_staged_bodies: 0, max_open_body_fds: 1, close_failures: 0 });
});

test('partial open: a non-object read fault marks literal FD accounting unknown, never zero', async () => {
  const f = fixture();
  const a = f.admit({ selected_model_indices: [3] });
  const fault = injectPartialOpen(f.bodyPaths[3], 1, { closeFails: false, raw: true });
  let r;
  try { r = await f.run(a); } finally { fault.restore(); }
  assert.equal(r.first_failure.phase, 'body-staging');
  const m = readOut(a.output, 'MANIFEST.json');
  assert.equal(m.status, 'failed');
  assert.deepEqual(m.body_fds, { max_staged_bodies: 0, max_open_body_fds: null, close_failures: null,
    literal_accounting: 'unknown: a failed body read could not carry its descriptor outcome' });
});

test('body change after admission: staging refusal, sticky first failure plus later preservation error', async () => {
  const f = fixture();
  const a = f.admit({ selected_model_indices: [3, 5, 10] });
  a.testing.log = (line) => { if (line === 'model-0003: started') fs.appendFileSync(f.bodyPaths[5], ' '); };
  const r = await f.run(a);
  assert.equal(r.status, 'failed');
  assert.equal(r.first_failure.phase, 'body-staging');
  assert.equal(r.first_failure.model_index, 5);
  const m = readOut(a.output, 'MANIFEST.json');
  assert.deepEqual([3, 5, 10].map((i) => m.jobs[i].status), ['returned', 'failed', 'not_started']);
  assert.ok(m.later_failures.some((x) => x.phase === 'body-final-reread' && x.model_index === 5 && x.failure_class === 'preservation'));
  assert.equal(m.first_failure.model_index, 5);
});

test('publication: reused output refuses before workers; retained cap fails with partial evidence', async () => {
  const f = fixture();
  const a = f.admit({ selected_model_indices: [3] });
  fs.mkdirSync(a.output, { mode: 0o700 });
  await assert.rejects(f.run(a), /EEXIST/);
  assert.deepEqual(fs.readdirSync(a.output), []);
  const g = fixture({ limits: { ...LIMITS, total_retained_result_bytes: 1500 } });
  const b = g.admit({ selected_model_indices: [3, 5] });
  const r = await g.run(b);
  assert.equal(r.status, 'failed');
  assert.equal(r.first_failure.model_index, 3);
  assert.equal(r.first_failure.failure_class, 'limit');
});

test('semantic authority: source binding shape, exact projection mutations and host self-descriptor, all before output', async () => {
  const f = fixture();
  const ok = f.admit();
  assert.throws(() => validateBinding(null), (e) => e.code === 'unbound');
  for (const [b, re] of [
    [{ ...ok.binding, execution_admitted: false }, /execution_admitted:true/],
    [{ ...ok.binding, runtime_ready: true }, /source binding keys/],
    [{ ...ok.binding, admission_projection: { ...ok.binding.admission_projection, host: HOST_DESC } }, /projection keys/],
    [{ ...ok.binding, runtime_profile: { ...f.profilePin, sha256: 'e'.repeat(64) } }, /different runtime profile/]]) {
    assert.throws(() => validateBinding(b), re);
    await assert.rejects(runHost({ profile: f.profilePath, admission: ok.path }, { ...f.testing, binding: b }), re);
    assert.equal(fs.existsSync(ok.output), false);
  }
  // Each approved field mutated in the admission file alone is refused.
  const mutations = {
    schema: 'other', root_bound: false, execution_admitted: false, mode: 'remainder', profile_sha256: 'e'.repeat(64),
    required_head: 'c'.repeat(40), output_path: path.join(f.dir, 'elsewhere'), selected_model_indices: [3, 5],
    guard_qualification: { schema: GUARD_QUALIFICATION_SCHEMA, sampled_rss_bytes: LIMITS.outer_sampled_rss_bytes, receipt_sha256: 'd'.repeat(64) },
    consumed_pilot: { indices: [3], manifest: null, audit: null }, self_admit: true
  };
  for (const [k, v] of Object.entries(mutations)) {
    const a = f.admit({}, { [k]: v });
    await assert.rejects(f.run(a), /source-bound approved projection/, k);
    assert.equal(fs.existsSync(a.output), false);
    assert.equal(fs.existsSync(path.join(f.dir, 'elsewhere')), false);
  }
  // The host self-descriptor is the one excluded field; it is checked against the running source.
  const h = f.admit({}, { host: { ...HOST_DESC, sha256: 'd'.repeat(64) } });
  await assert.rejects(f.run(h), /host descriptor differs/);
  // Consistent but structurally invalid approvals are still refused.
  for (const [over, re] of [[{ root_bound: false }, /root_bound/], [{ mode: 'all' }, /mode/], [{ selected_model_indices: [5, 3] }, /strictly ascending/],
    [{ required_head: 'HEAD' }, /required_head/], [{ guard_qualification: null }, /guard_qualification/],
    [{ consumed_pilot: { indices: [3], manifest: null, audit: null } }, /pilot mode takes consumed_pilot:null/]]) {
    const a = f.admit(over);
    await assert.rejects(f.run(a), re);
    assert.equal(fs.existsSync(a.output), false);
  }
  // The runtime profile must bind every logical model before a pilot.
  const n = fixture({ nullBodies: [7] });
  const na = n.admit();
  await assert.rejects(n.run(na), /model 7 has no bound body descriptor/);
  assert.equal(fs.existsSync(na.output), false);
});

test('remainder: exact complement of the audited pilot; omitted or overlapping members refused', async () => {
  const pilotThenRemainder = async (f, pilot) => {
    const p = f.admit({ selected_model_indices: pilot });
    assert.equal((await f.run(p)).status, 'observed');
    const manifestPath = path.join(p.output, 'MANIFEST.json');
    const audit = (over = {}) => writeFile(f.dir, `audit${seq++}.json`, JSON.stringify({ schema: PILOT_AUDIT_SCHEMA, result: 'PASS', root_bound: true,
      pilot_manifest_sha256: pinOf(manifestPath).sha256, pilot_model_indices: pilot, ...over }));
    const remainder = (selected, auditPath = audit()) => f.admit({ mode: 'remainder', selected_model_indices: selected,
      consumed_pilot: { indices: pilot, manifest: descriptor(manifestPath), audit: descriptor(auditPath) } });
    return { remainder, audit };
  };
  const big = fixture();
  const R = await pilotThenRemainder(big, [3]);
  const complement = Array.from({ length: 936 }, (_, i) => i).filter((i) => i !== 3);
  for (const [selected, re] of [
    [complement.filter((i) => i !== 935), /complete logical domain minus the consumed pilot/],
    [complement.filter((i) => i !== 500), /complete logical domain minus the consumed pilot/],
    [[5, 10, 20], /complete logical domain minus the consumed pilot/],
    [Array.from({ length: 936 }, (_, i) => i), /disjoint/]]) {
    const ad = R.remainder(selected);
    await assert.rejects(big.run(ad), re);
    assert.equal(fs.existsSync(ad.output), false);
  }
  for (const [aud, re] of [[{ result: 'FAIL' }, /audit PASS required/], [{ pilot_manifest_sha256: 'f'.repeat(64) }, /does not bind/]]) {
    const ad = R.remainder(complement, R.audit(aud));
    await assert.rejects(big.run(ad), re);
    assert.equal(fs.existsSync(ad.output), false);
  }
  // Genuine pilot then complete remainder on a small authored domain.
  const small = fixture({ domain: SMALL, bodies: {} });
  const S = await pilotThenRemainder(small, [3]);
  const ok = S.remainder([0, 1, 2, 4, 5, 6, 7]);
  const r = await small.run(ok);
  assert.equal(r.status, 'observed', JSON.stringify(r));
  const m = readOut(ok.output, 'MANIFEST.json');
  assert.deepEqual(m.consumed_pilot.indices, [3]);
  assert.equal(m.jobs[3].status, 'outside_batch');
  assert.deepEqual(m.counts, { outside_batch: 1, not_started: 0, started: 0, failed: 0, returned: 7 });
  assert.equal(m.schema, MANIFEST_SCHEMA);
});

test('private Root source binding executes genuinely through the CLI (authored pins substituted)', () => {
  const f = fixture();
  const text = fs.readFileSync(HOST, 'utf8');
  const lines = {
    'export const ROOT_SOURCE_BINDING = null;': null,
    "export const UNBOUND_PROFILE_PIN = Object.freeze({ bytes: 2538357, sha256: 'c7d4f10d593df131ee4e5e39a9d30eb20532888e38b90eeab403309b2f0d279c' });": `export const UNBOUND_PROFILE_PIN = Object.freeze(${JSON.stringify(f.testing.unboundPin)});`,
    "export const PREFIX_PIN = Object.freeze({ bytes: 624463, sha256: '1501ca10336d91e4f8a0301101c43e5ca1a0ef1aa81212bbffb5690c68c13325' });": `export const PREFIX_PIN = Object.freeze(${JSON.stringify(f.testing.prefixPin)});`,
    "export const SUMMARY_PIN = Object.freeze({ bytes: 6452, sha256: 'ec51b8b2b4930db840503601911c1e0e5f6e6b4db641fa7ae1f85fdf6de13d5c' });": `export const SUMMARY_PIN = Object.freeze(${JSON.stringify(f.testing.summaryPin)});`
  };
  for (const line of Object.keys(lines)) assert.equal(text.split(line).length, 2, line);
  // The binding names everything but the host; the host is described after it is written.
  const approved = f.admit({ selected_model_indices: [3, 5] });
  let privateText = text;
  for (const [line, replacement] of Object.entries(lines)) {
    privateText = privateText.replace(line, replacement ?? `export const ROOT_SOURCE_BINDING = Object.freeze(${JSON.stringify(approved.binding)});`);
  }
  const privateHost = writeFile(f.dir, 'private_host.mjs', privateText);
  const admissionPath = writeFile(f.dir, 'private_admission.json', JSON.stringify({ ...approved.admission, host: descriptor(privateHost) }));
  const r = spawnSync(process.execPath, [privateHost, '--profile', f.profilePath, '--admission', admissionPath], { encoding: 'utf8', env: {} });
  assert.equal(r.status, 0, r.stderr);
  assert.equal(JSON.parse(r.stdout).status, 'observed');
  const m = readOut(approved.output, 'MANIFEST.json');
  assert.equal(m.host.sha256, descriptor(privateHost).sha256);
  assert.deepEqual([m.jobs[3].status, m.jobs[5].status], ['returned', 'returned']);
  // The same private host refuses an admission differing from its bound projection.
  const tampered = writeFile(f.dir, 'private_tampered.json', JSON.stringify({ ...approved.admission, output_path: path.join(f.dir, 'other'), host: descriptor(privateHost) }));
  const t = spawnSync(process.execPath, [privateHost, '--profile', f.profilePath, '--admission', tampered], { encoding: 'utf8', env: {} });
  assert.equal(t.status, 2);
  assert.match(t.stderr, /source-bound approved projection/);
  assert.equal(fs.existsSync(path.join(f.dir, 'other')), false);
});
