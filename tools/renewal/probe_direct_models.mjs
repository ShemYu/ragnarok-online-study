#!/usr/bin/env node
// T07.007.014.012: finite Node worker_threads host for genuine RSM construction
// and complete nested texture declarations, derived from the pinned
// T07.007.014.009 compiled-core host (b84a9b71…, 56407B).
//
//   node tools/renewal/probe_direct_models.mjs --profile <path> --admission <path>
//
// One fresh sequential Worker per selected logical model evaluates one classic
// script: the complete unchanged compiled prefix followed by the fixed model
// suffix. Before evaluation the Worker imports the exact staged unmodified
// summary module and bridges summarizeModel into the classic scope. The suffix
// calls new RSM(exact standalone ArrayBuffer), then summarizeModel(model). Every
// fetch refuses; there is no FileManager/MapLoader, terrain constructor,
// createInstance, compile/compileAtFrame, image decode or rendering. A result is
// an observation, never qualification: Root qualifies.
//
// Default state is unbound: ROOT_SOURCE_BINDING is null, so the CLI and runHost
// refuse before any file read, output creation or Worker start. Root produces a
// private host by replacing only that line with a frozen binding: execution
// admission, the complete runtime-profile pin and the exact semantic admission
// projection (every admission field except this host's own descriptor). Node,
// suffix and bodies are bound transitively by that profile. A separately frozen
// Root caller pins the final host/admission/profile/guard files and verifies
// live HEAD, fresh output and actual guard execution; this source claims none.
import { createHash, webcrypto } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { performance } from 'node:perf_hooks';
import { fileURLToPath } from 'node:url';
import { inspect, isDeepStrictEqual } from 'node:util';
import vm from 'node:vm';
import { isMainThread, parentPort, Worker, workerData } from 'node:worker_threads';

// Root-only private source binding; null in public source and no CLI switch
// changes it. Shape: { execution_admitted: true, runtime_profile: { bytes, sha256 },
// admission_projection: <admission without host> }. Configuration is not
// qualification: runtime readiness is never claimed by this host.
export const ROOT_SOURCE_BINDING = null;
export const UNBOUND_PROFILE_PIN = Object.freeze({ bytes: 2538357, sha256: 'c7d4f10d593df131ee4e5e39a9d30eb20532888e38b90eeab403309b2f0d279c' });
export const PREFIX_PIN = Object.freeze({ bytes: 624463, sha256: '1501ca10336d91e4f8a0301101c43e5ca1a0ef1aa81212bbffb5690c68c13325' });
export const SUMMARY_PIN = Object.freeze({ bytes: 6452, sha256: 'ec51b8b2b4930db840503601911c1e0e5f6e6b4db641fa7ae1f85fdf6de13d5c' });
export const DONOR_HOST_PIN = Object.freeze({ bytes: 56407, sha256: 'b84a9b71cd75b5515b6ace1996120b74d095a2883a030138291f397cd478c7e3' });
export const UNBOUND_PROFILE_SCHEMA = 'root-remaining-model-constructor-declarations-preparation-v1';
export const PROFILE_SCHEMA = 'root-direct-model-constructor-runtime-v1';
export const ADMISSION_SCHEMA = 'root-direct-model-constructor-admission-v1';
export const PILOT_AUDIT_SCHEMA = 'root-direct-model-pilot-audit-v1';
export const GUARD_QUALIFICATION_SCHEMA = 'root-outer-guard-qualification-v1';
export const MANIFEST_SCHEMA = 't07-007-014-012-model-host-manifest-v1';
export const MODEL_REPORT_SCHEMA = 't07-007-014-012-model-report-v1';
export const NESTED_SCHEMA = 't07-007-014-012-nested-targets-v1';
export const RESULT_SCHEMA = 't07-007-014-012-model-result-v1';
export const IDENTITY_FIELDS = Object.freeze(['st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_mode', 'st_nlink', 'st_uid']);
export const IDENTITY_ENCODING = 'exact decimal strings; full st_mode; use fs bigint stats';
export const LIMITS = Object.freeze({
  all_run_deadline_ms: 1240000, inner_diagnostic_deadline_ms: 48000, input_body_bytes: 1048576,
  model_result_bytes: 8388608, outer_sampled_rss_bytes: 1610612736, stderr_bytes: 1048576, stdout_bytes: 1048576,
  total_retained_result_bytes: 185597952, worker_deadline_ms: 55000, worker_heap_mb: 1024,
  summary_per_model: Object.freeze({ node_slots: 262144, nodes: 65536, numeric_visits: 4194304, string_code_units: 1048576, textures: 65536 }),
  declaration_reducer_global: Object.freeze({ declarations: 65536, json_depth: 64, node_slots: 262144, nodes: 65536, string_code_units: 1048576 })
});
export const DOMAIN = Object.freeze({ models: 936, relations: 1649, maps: 21, case_groups: 3, case_rows: 6 });
export const TEXTURE_PREFIX = 'data\\texture\\';
export const CONSTRUCTION_LIMIT = 'construction and declarations only; uninstanced compile is excluded (vacuous zero meshes); no placement geometry, image decode or rendering';
const ADMISSION_KEYS = ['consumed_pilot', 'execution_admitted', 'guard_qualification', 'host', 'mode', 'output_path', 'profile_sha256', 'required_head', 'root_bound', 'schema', 'selected_model_indices'];
const PROJECTION_KEYS = ADMISSION_KEYS.filter((k) => k !== 'host');
const ADMISSION_MAX_BYTES = 65536;
const SUFFIX_MAX_BYTES = 65536;
const PILOT_SOURCE_MAX_BYTES = 1 << 26;
const WORKER_SCHEMA = 't07-007-014-012-worker-v1';
const HEX40 = /^[0-9a-f]{40}$/;
const HEX64 = /^[0-9a-f]{64}$/;
const DECIMAL = /^(0|[1-9][0-9]*)$/;
const S_IFMT = 0o170000n;
const S_IFREG = 0o100000n;
const S_IFDIR = 0o040000n;

export class Refusal extends Error {
  constructor(code, message) { super(message); this.name = 'Refusal'; this.code = code; }
}
const refuse = (code, message) => { throw new Refusal(code, message); };
const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex');
const errorRecord = (e, phase) => ({
  phase, name: String(e?.name ?? typeof e), message: String(e?.message ?? e),
  code: e?.code === undefined ? null : String(e.code), stack: typeof e?.stack === 'string' ? e.stack : null
});

// ---------------------------------------------------------------- arguments

export function parseArgs(argv) {
  const seen = new Map();
  for (let i = 0; i < argv.length; i += 2) {
    const flag = argv[i];
    if (flag !== '--profile' && flag !== '--admission') refuse('usage', `unknown argument: ${JSON.stringify(flag)}`);
    if (seen.has(flag)) refuse('usage', `duplicate argument: ${flag}`);
    const value = argv[i + 1];
    if (value === undefined || value === '' || value.startsWith('--')) refuse('usage', `missing value for ${flag}`);
    seen.set(flag, value);
  }
  for (const flag of ['--profile', '--admission']) if (!seen.has(flag)) refuse('usage', `missing argument: ${flag}`);
  return { profile: seen.get('--profile'), admission: seen.get('--admission') };
}

// ---------------------------------------------------------------- identity (donor .009 84-165, unchanged)

// Exact decimal strings straight from bigint stats; never Number().
export function identityOf(stat) {
  if (typeof stat.ino !== 'bigint') refuse('identity', 'bigint stat required');
  return [stat.dev, stat.ino, stat.size, stat.mtimeNs, stat.ctimeNs, stat.mode, stat.nlink, stat.uid].map((v) => v.toString());
}
export function sameIdentity(a, b) {
  return Array.isArray(a) && Array.isArray(b) && a.length === 8 && b.length === 8 && a.every((v, i) => typeof v === 'string' && v === b[i]);
}
const dirIdentity = (stat) => [stat.dev, stat.ino, stat.mode, stat.uid].map((v) => v.toString());

function checkDescriptor(desc, label, maxBytes) {
  if (!desc || typeof desc !== 'object' || Array.isArray(desc)) refuse('profile', `${label}: descriptor object required`);
  const keys = Object.keys(desc).sort().join(',');
  if (keys !== 'bytes,identity,path,sha256') refuse('profile', `${label}: descriptor keys ${keys}`);
  if (typeof desc.path !== 'string' || !path.isAbsolute(desc.path) || path.normalize(desc.path) !== desc.path) refuse('profile', `${label}: absolute normalized path required`);
  if (!Number.isSafeInteger(desc.bytes) || desc.bytes < 0 || (maxBytes !== undefined && desc.bytes > maxBytes)) refuse('profile', `${label}: bytes out of bound`);
  if (typeof desc.sha256 !== 'string' || !HEX64.test(desc.sha256)) refuse('profile', `${label}: sha256`);
  if (!Array.isArray(desc.identity) || desc.identity.length !== 8 || !desc.identity.every((v) => typeof v === 'string' && DECIMAL.test(v))) refuse('profile', `${label}: identity must be eight decimal strings`);
  if (desc.identity[2] !== String(desc.bytes)) refuse('profile', `${label}: identity st_size differs from bytes`);
  if ((BigInt(desc.identity[5]) & S_IFMT) !== S_IFREG) refuse('profile', `${label}: identity st_mode is not a regular file`);
  if (desc.identity[6] !== '1') refuse('profile', `${label}: identity must be single-link`);
}

// Opens one exact regular single-link file with O_NOFOLLOW, reads it to EOF into
// a standalone ArrayBuffer and checks size/hash plus stable FD/path/parent
// identities. When `desc` is null the identity is recorded, not compared.
export function readPinnedFile(filePath, { desc = null, pin = null, maxBytes, label }) {
  if (typeof filePath !== 'string' || !path.isAbsolute(filePath)) refuse('input', `${label}: absolute path required`);
  const parent = path.dirname(filePath);
  const parentBefore = fs.lstatSync(parent, { bigint: true });
  if ((parentBefore.mode & S_IFMT) !== S_IFDIR) refuse('input', `${label}: parent is not a directory`);
  if (fs.realpathSync(filePath) !== filePath) refuse('input', `${label}: path is not canonical (symlinked component)`);
  const pathBefore = fs.lstatSync(filePath, { bigint: true });
  if (!pathBefore.isFile()) refuse('input', `${label}: not a regular file`);
  const fd = fs.openSync(filePath, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW);
  try {
    const fdBefore = fs.fstatSync(fd, { bigint: true });
    const identity = identityOf(fdBefore);
    if (!fdBefore.isFile() || fdBefore.nlink !== 1n) refuse('input', `${label}: not a regular single-link file`);
    if (!sameIdentity(identity, identityOf(pathBefore))) refuse('input', `${label}: path and descriptor identities differ`);
    if (desc && !sameIdentity(identity, desc.identity)) refuse('input', `${label}: identity differs from pinned decimal identity`);
    if (fdBefore.size > BigInt(maxBytes)) refuse('input', `${label}: ${fdBefore.size} bytes exceeds ${maxBytes}`);
    const size = Number(fdBefore.size);
    const buffer = new ArrayBuffer(size);
    const view = new Uint8Array(buffer);
    let offset = 0;
    while (offset < size) {
      const n = fs.readSync(fd, view, offset, size - offset, offset);
      if (n === 0) refuse('input', `${label}: short read at ${offset}/${size}`);
      offset += n;
    }
    if (fs.readSync(fd, new Uint8Array(1), 0, 1, size) !== 0) refuse('input', `${label}: bytes beyond recorded size`);
    const digest = sha256(view);
    const expected = desc ?? pin;
    if (expected && (size !== expected.bytes || digest !== expected.sha256)) refuse('input', `${label}: bytes/sha256 differ from pin`);
    if (!sameIdentity(identityOf(fs.fstatSync(fd, { bigint: true })), identity)) refuse('input', `${label}: descriptor identity changed during read`);
    if (!sameIdentity(identityOf(fs.lstatSync(filePath, { bigint: true })), identity)) refuse('input', `${label}: path identity changed during read`);
    const parentAfter = fs.lstatSync(parent, { bigint: true });
    if (dirIdentity(parentAfter).join() !== dirIdentity(parentBefore).join()) refuse('input', `${label}: parent identity changed during read`);
    return { label, path: filePath, fd, buffer, bytes: size, sha256: digest, identity, parent_identity: dirIdentity(parentBefore) };
  } catch (e) {
    // Partial-open path: the read failure stays primary; a failed close is
    // appended, never retried and never hides the original error. The thrown
    // error carries the literal open and its single close outcome for FD
    // accounting; a non-object throw cannot carry them (callers mark unknown).
    const closeError = closeFd(fd);
    if (e !== null && typeof e === 'object') Object.assign(e, { fd_opened: true, fd_close_error: closeError });
    if (closeError && e instanceof Error) e.message += `; descriptor close after failure also failed: ${closeError.message}`;
    throw e;
  }
}

// Literal open/close outcome of a failed readPinnedFile: { fd_opened, fd_close_error },
// or null when the thrown value cannot carry it.
export function partialOpenOf(e) {
  if (e === null || typeof e !== 'object') return null;
  return e.fd_opened === true ? { fd_opened: true, fd_close_error: e.fd_close_error ?? null } : { fd_opened: false, fd_close_error: null };
}

// One close attempt per descriptor; an ambiguous close is reported, not retried.
export function closeFd(fd) {
  try { fs.closeSync(fd); return null; } catch (e) { return errorRecord(e, 'close'); }
}

// Post-check: held descriptor, path and parent unchanged; a fresh nofollow full
// reread and the staged in-memory buffer both still match.
// The reread holds a second descriptor for the same file while the original is
// still open; `reread_opened`/`reread_fd_closed` feed literal FD accounting,
// including a reread that opened and then failed (null = unknowable).
export function postcheckPinnedFile(held) {
  const out = { label: held.label, path: held.path, bytes: held.bytes, sha256: held.sha256, failures: [], reread_opened: false, reread_fd_closed: false };
  let rereadAttempted = false;
  try {
    if (!sameIdentity(identityOf(fs.fstatSync(held.fd, { bigint: true })), held.identity)) out.failures.push('held descriptor identity changed');
    rereadAttempted = true;
    const again = readPinnedFile(held.path, { desc: { bytes: held.bytes, sha256: held.sha256, identity: held.identity }, maxBytes: held.bytes, label: held.label });
    out.reread_opened = true;
    const closeError = closeFd(again.fd);
    out.reread_fd_closed = closeError === null;
    if (closeError) out.failures.push(`reread descriptor close failed: ${closeError.message}`);
    if (again.parent_identity.join() !== held.parent_identity.join()) out.failures.push('parent identity changed');
  } catch (e) {
    out.failures.push(`reread: ${e?.message}`);
    if (rereadAttempted && !out.reread_opened) {
      const opened = partialOpenOf(e);
      if (opened === null) Object.assign(out, { reread_opened: null, reread_fd_closed: null });
      else if (opened.fd_opened) Object.assign(out, { reread_opened: true, reread_fd_closed: opened.fd_close_error === null });
    }
  }
  if (held.buffer.byteLength !== held.bytes || sha256(new Uint8Array(held.buffer)) !== held.sha256) out.failures.push('staged buffer changed');
  out.ok = out.failures.length === 0;
  return out;
}

// Closes each held descriptor at most once and returns every outcome.
function closeHeld(held) {
  const outcomes = [];
  for (const h of held) {
    if (h.close_attempted) continue;
    h.close_attempted = true;
    const error = closeFd(h.fd);
    outcomes.push({ label: h.label, path: h.path, closed: error === null, error });
  }
  return outcomes;
}

// ---------------------------------------------------------------- domain

const isObj = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
const isIndex = (v, n) => Number.isSafeInteger(v) && v >= 0 && v < n;
const ascendingUnique = (list) => list.every((v, i) => i === 0 || v > list[i - 1]);

// Validates the frozen unbound projection: every typed model/relation/map/case
// join. Global query indices stay distinct from model indices; case rows are
// potential groups only and never merge logical rows.
export function validateUnboundDomain(unbound, domain = DOMAIN) {
  if (!isObj(unbound) || unbound.schema !== UNBOUND_PROFILE_SCHEMA) refuse('profile', 'unbound profile schema');
  if (unbound.execution_admitted !== false || unbound.root_bound !== false || unbound.limits_admitted !== false) refuse('profile', 'unbound profile must keep every admission flag false');
  const { models, model_group_relations: relations, maps, case_alias_groups: cases } = unbound;
  if (!Array.isArray(models) || models.length !== domain.models) refuse('profile', `${domain.models} logical models required`);
  if (!Array.isArray(relations) || relations.length !== domain.relations) refuse('profile', `${domain.relations} model-group relations required`);
  if (!Array.isArray(maps) || maps.length !== domain.maps) refuse('profile', `${domain.maps} maps required`);
  if (!Array.isArray(cases) || cases.length !== domain.case_groups) refuse('profile', `${domain.case_groups} case groups required`);
  const queries = new Set();
  models.forEach((m, i) => {
    if (!isObj(m) || m.model_index !== i) refuse('profile', `models[${i}]: model_index`);
    if (m.execution_admitted !== false) refuse('profile', `models[${i}]: execution_admitted must stay false`);
    const q = m.original_query;
    if (!isObj(q) || !Number.isSafeInteger(q.query_index) || q.query_index !== m.original_query_index) refuse('profile', `models[${i}]: original query index`);
    if (queries.has(q.query_index)) refuse('profile', `models[${i}]: duplicate global query index`);
    queries.add(q.query_index);
    if (typeof m.logical_request_latin1 !== 'string' || typeof m.wire_target !== 'string' || !m.wire_target.startsWith('/')) refuse('profile', `models[${i}]: request/wire target`);
    if (!Array.isArray(m.model_relation_indices) || !Array.isArray(m.map_indices)) refuse('profile', `models[${i}]: relation/map indices`);
  });
  const byModel = models.map(() => []), byMap = maps.map(() => []);
  relations.forEach((r, i) => {
    if (!isObj(r) || r.model_relation_index !== i || !isIndex(r.model_index, models.length)) refuse('profile', `relations[${i}]: indices`);
    const o = r.original_relation;
    if (!isObj(o) || !isIndex(o.map_index, maps.length) || o.query_index !== models[r.model_index].original_query_index) refuse('profile', `relations[${i}]: original relation join`);
    if (o.map_name !== maps[o.map_index].map_name) refuse('profile', `relations[${i}]: map name join`);
    if (typeof r.core_group_pointer !== 'string' || r.core_group_occurrences_pointer !== `${r.core_group_pointer}/occurrences`) refuse('profile', `relations[${i}]: core group pointers`);
    byModel[r.model_index].push(i);
    byMap[o.map_index].push(i);
  });
  models.forEach((m, i) => {
    if (!isDeepStrictEqual(m.model_relation_indices, byModel[i]) || byModel[i].length === 0) refuse('profile', `models[${i}]: relation indices differ from the relation table`);
    const mapsOf = [...new Set(byModel[i].map((r) => relations[r].original_relation.map_index))];
    if (!isDeepStrictEqual(m.map_indices, mapsOf)) refuse('profile', `models[${i}]: map indices differ from the relation table`);
    // Original relation indices carried by the record join the relation table exactly.
    const originals = byModel[i].map((r) => relations[r].original_relation.relation_index);
    if (!isDeepStrictEqual(m.source_relation_indices, originals) || !isDeepStrictEqual(m.original_query.relation_indices, originals) ||
      m.original_query.first_relation_index !== originals[0]) refuse('profile', `models[${i}]: original relation indices differ from the relation table`);
  });
  let mapTotal = 0;
  maps.forEach((m, i) => {
    if (!isObj(m) || m.map_index !== i || typeof m.map_name !== 'string') refuse('profile', `maps[${i}]: map_index/name`);
    if (!isDeepStrictEqual(m.model_relation_indices, byMap[i])) refuse('profile', `maps[${i}]: relation indices differ`);
    if (!isDeepStrictEqual(m.model_indices, byMap[i].map((r) => relations[r].model_index))) refuse('profile', `maps[${i}]: model indices differ`);
    if (!isDeepStrictEqual(m.original_relation_indices, byMap[i].map((r) => relations[r].original_relation.relation_index))) refuse('profile', `maps[${i}]: original relation indices differ`);
    mapTotal += byMap[i].length;
  });
  if (mapTotal !== relations.length) refuse('profile', 'map relation counts do not sum to the relation table');
  let rows = 0;
  const grouped = new Map();
  cases.forEach((g, i) => {
    if (!isObj(g) || g.alias_group_index !== i || !Array.isArray(g.model_indices) || !Array.isArray(g.query_indices) || g.model_indices.length !== g.query_indices.length) refuse('profile', `case group ${i}: shape`);
    if (g.actual_asset_alias_verified !== false || g.merge_logical_constructor_rows !== false || g.expected_shared_sha256 !== null) refuse('profile', `case group ${i}: potential case group must stay unverified/unmerged/unhashed`);
    g.model_indices.forEach((mi, k) => {
      if (!isIndex(mi, models.length) || models[mi].physical_input_alias_group !== i || models[mi].original_query_index !== g.query_indices[k]) refuse('profile', `case group ${i}: row ${k} join`);
      if (grouped.has(mi)) refuse('profile', `case group ${i}: model ${mi} repeated`);
      grouped.set(mi, i);
      rows++;
    });
    if (new Set(g.requested_wire_targets).size !== g.model_indices.length) refuse('profile', `case group ${i}: requested targets must stay case-distinct`);
  });
  if (rows !== domain.case_rows) refuse('profile', `${domain.case_rows} case rows required`);
  models.forEach((m, i) => {
    if ((m.physical_input_alias_group ?? null) !== (grouped.has(i) ? grouped.get(i) : null)) refuse('profile', `models[${i}]: physical_input_alias_group differs from case groups`);
  });
  return { models, relations, maps, cases };
}

// Validates the Root runtime projection against the pinned unbound profile:
// the four domain tables are deep-equal, each model record is unchanged apart
// from one added `body` descriptor (or null) and no body path is shared.
export function validateProfile(profile, unbound, { limits = LIMITS, prefixPin = PREFIX_PIN, summaryPin = SUMMARY_PIN, unboundPin = UNBOUND_PROFILE_PIN, domain = DOMAIN } = {}) {
  if (!isObj(profile)) refuse('profile', 'profile object required');
  if (profile.schema !== PROFILE_SCHEMA) refuse('profile', 'profile schema');
  if (profile.execution_admitted !== false) refuse('profile', 'runtime profile must keep execution_admitted:false; admission is separate');
  if (JSON.stringify(profile.identity_fields) !== JSON.stringify(IDENTITY_FIELDS)) refuse('profile', 'identity field order');
  if (profile.identity_encoding !== IDENTITY_ENCODING) refuse('profile', 'identity encoding');
  if (!isDeepStrictEqual(profile.limits, JSON.parse(JSON.stringify(limits)))) refuse('profile', 'limits differ from the frozen caps');
  checkDescriptor(profile.unbound_profile, 'unbound_profile');
  if (profile.unbound_profile.bytes !== unboundPin.bytes || profile.unbound_profile.sha256 !== unboundPin.sha256) refuse('profile', 'unbound_profile differs from fixed pin');
  for (const [name, pin] of [['compiled_prefix', prefixPin], ['summary_module', summaryPin]]) {
    checkDescriptor(profile[name], name);
    if (profile[name].bytes !== pin.bytes || profile[name].sha256 !== pin.sha256) refuse('profile', `${name} differs from fixed pin`);
  }
  checkDescriptor(profile.model_suffix, 'model_suffix', SUFFIX_MAX_BYTES);
  checkDescriptor(profile.node, 'node');
  const d = validateUnboundDomain(unbound, domain);
  for (const key of ['model_group_relations', 'maps', 'case_alias_groups']) {
    if (!isDeepStrictEqual(profile[key], unbound[key])) refuse('profile', `${key} differ from the unbound profile`);
  }
  if (!Array.isArray(profile.models) || profile.models.length !== d.models.length) refuse('profile', 'model count differs from the unbound profile');
  const paths = new Map();
  const bodies = profile.models.map((m, i) => {
    if (!isObj(m) || !Object.hasOwn(m, 'body')) refuse('profile', `models[${i}]: body slot required (descriptor or null)`);
    const { body, ...record } = m;
    if (!isDeepStrictEqual(record, d.models[i])) refuse('profile', `models[${i}]: typed source record differs from the unbound profile`);
    if (body === null) return null;
    checkDescriptor(body, `models[${i}].body`, limits.input_body_bytes);
    if (paths.has(body.path)) refuse('profile', `models[${i}]: body path shared with model ${paths.get(body.path)}; actual case/path sharing is Root-bound`);
    paths.set(body.path, i);
    const expected = record.expected_retained_body;
    if (expected !== null && (expected.bytes !== body.bytes || expected.sha256 !== body.sha256)) refuse('profile', `models[${i}]: body differs from the known retained pin`);
    return body;
  });
  return { ...d, records: d.models, bodies };
}

// ---------------------------------------------------------------- suffix

const occurrences = (text, needle) => { let n = 0; for (let i = text.indexOf(needle); i !== -1; i = text.indexOf(needle, i + 1)) n++; return n; };

// The model suffix is used unchanged; check the fixed bounds and protocol it embeds.
export function checkSuffix(suffixText, limits = LIMITS) {
  if (occurrences(suffixText, `performance.now() + ${limits.inner_diagnostic_deadline_ms}`) !== 1) refuse('suffix', 'inner diagnostic deadline differs');
  if (limits.model_result_bytes !== 8 * 1024 * 1024 || occurrences(suffixText, 'const ROOT_MODEL_LIMIT = 8 * 1024 * 1024;') !== 1) refuse('suffix', 'suffix result bound differs');
  for (const needle of ["'ROOT_MODEL_CONSTRUCT'", "type:'ROOT_MODEL_RESULT'", 'new RSM(buffer)', 'ROOT_MODEL_SUMMARIZE(model)']) {
    if (occurrences(suffixText, needle) !== 1) refuse('suffix', `suffix protocol ${needle} must occur exactly once`);
  }
  for (const banned of ['fetch(', '.compile(', '.compileAtFrame(', '.createInstance(', 'MapLoader.', 'FileManager.']) {
    if (suffixText.includes(banned)) refuse('suffix', `suffix must not reference ${banned}`);
  }
}

// ---------------------------------------------------------------- admission

const normalizedAbsolute = (p) => typeof p === 'string' && path.isAbsolute(p) && path.normalize(p) === p && !p.endsWith(path.sep);

// The source binding is checked before any file read. Its projection is the
// exact admission minus `host`: pinning the whole admission here would be a
// circular self-hash because the admission names this host.
export function validateBinding(binding) {
  if (binding === null) refuse('unbound', 'source binding is unbound; Root binds the runtime profile and approved admission projection');
  if (!isObj(binding) || Object.keys(binding).sort().join(',') !== 'admission_projection,execution_admitted,runtime_profile') refuse('binding', 'source binding keys');
  if (binding.execution_admitted !== true) refuse('binding', 'source binding execution_admitted:true required');
  const p = binding.runtime_profile;
  if (!isObj(p) || Object.keys(p).sort().join(',') !== 'bytes,sha256' || !Number.isSafeInteger(p.bytes) || p.bytes <= 0 || !HEX64.test(p.sha256)) refuse('binding', 'source binding runtime_profile pin');
  const a = binding.admission_projection;
  if (!isObj(a) || Object.keys(a).sort().join(',') !== PROJECTION_KEYS.join(',')) refuse('binding', `admission projection keys must be exactly ${PROJECTION_KEYS.join(',')}`);
  if (a.profile_sha256 !== p.sha256) refuse('binding', 'admission projection names a different runtime profile');
  return binding;
}

// Everything except the host self-descriptor must equal the source-bound projection.
export function checkAdmissionProjection(admission, binding) {
  if (!isObj(admission)) refuse('admission', 'admission object required');
  const { host, ...projection } = admission;
  void host;
  if (!isDeepStrictEqual(projection, binding.admission_projection)) refuse('admission', 'admission differs from the source-bound approved projection');
}

export function validateAdmission(admission, { hostDescriptor, profileSha256, bound, limits = LIMITS }) {
  if (!isObj(admission)) refuse('admission', 'admission object required');
  const keys = Object.keys(admission).sort();
  if (keys.join(',') !== ADMISSION_KEYS.join(',')) refuse('admission', `admission keys must be exactly ${ADMISSION_KEYS.join(',')}`);
  if (admission.schema !== ADMISSION_SCHEMA) refuse('admission', 'admission schema');
  if (admission.root_bound !== true) refuse('admission', 'root_bound:true required');
  if (admission.execution_admitted !== true) refuse('admission', 'execution_admitted:true required');
  if (admission.mode !== 'pilot' && admission.mode !== 'remainder') refuse('admission', 'mode must be pilot or remainder');
  if (admission.profile_sha256 !== profileSha256) refuse('admission', 'profile_sha256 differs from the pinned profile');
  if (typeof admission.required_head !== 'string' || !HEX40.test(admission.required_head)) refuse('admission', 'required_head must be a full 40-hex commit (live HEAD is verified by the Root caller)');
  // Approved prior guard qualification; this future run's guard receipt is the caller's.
  const g = admission.guard_qualification;
  if (!isObj(g) || Object.keys(g).sort().join(',') !== 'receipt_sha256,sampled_rss_bytes,schema' || g.schema !== GUARD_QUALIFICATION_SCHEMA ||
    g.sampled_rss_bytes !== limits.outer_sampled_rss_bytes || !HEX64.test(g.receipt_sha256)) refuse('admission', 'guard_qualification must name the approved prior guard qualification receipt and sampled RSS cap');
  if (!normalizedAbsolute(admission.output_path)) refuse('admission', 'output_path must be an absolute normalized path');
  try { checkDescriptor(admission.host, 'host'); } catch (e) { refuse('admission', e.message); }
  const h = admission.host;
  if (h.path !== hostDescriptor.path || h.bytes !== hostDescriptor.bytes || h.sha256 !== hostDescriptor.sha256 || !sameIdentity(h.identity, hostDescriptor.identity)) {
    refuse('admission', 'host descriptor differs from the running source');
  }
  const selected = admission.selected_model_indices;
  if (!Array.isArray(selected) || selected.length === 0 || !selected.every((v) => isIndex(v, bound.records.length)) || !ascendingUnique(selected)) {
    refuse('admission', 'selected_model_indices must be non-empty strictly ascending model indices');
  }
  // One complete runtime profile, frozen before the pilot, serves pilot and remainder.
  const unboundBody = bound.bodies.findIndex((b) => b === null);
  if (unboundBody !== -1) refuse('admission', `model ${unboundBody} has no bound body descriptor; the runtime profile must bind every logical model`);
  let consumed = null;
  if (admission.mode === 'pilot') {
    if (admission.consumed_pilot !== null) refuse('admission', 'pilot mode takes consumed_pilot:null');
  } else {
    const c = admission.consumed_pilot;
    if (!isObj(c) || Object.keys(c).sort().join(',') !== 'audit,indices,manifest') refuse('admission', 'remainder requires consumed_pilot {audit,indices,manifest}');
    if (!Array.isArray(c.indices) || c.indices.length === 0 || !c.indices.every((v) => isIndex(v, bound.records.length)) || !ascendingUnique(c.indices)) refuse('admission', 'consumed_pilot.indices');
    const pilot = new Set(c.indices);
    if (selected.some((i) => pilot.has(i))) refuse('admission', 'remainder must be disjoint from the consumed pilot');
    const complement = bound.records.map((r) => r.model_index).filter((i) => !pilot.has(i));
    if (!isDeepStrictEqual(selected, complement)) refuse('admission', 'remainder must equal the complete logical domain minus the consumed pilot');
    try { checkDescriptor(c.manifest, 'consumed_pilot.manifest', PILOT_SOURCE_MAX_BYTES); checkDescriptor(c.audit, 'consumed_pilot.audit', PILOT_SOURCE_MAX_BYTES); } catch (e) { refuse('admission', e.message); }
    consumed = c;
  }
  return { mode: admission.mode, output_path: admission.output_path, selected, consumed, required_head: admission.required_head, guard_qualification: g };
}

// The consumed pilot must be an observed pilot manifest of this same profile,
// with every pilot job returned, plus an independent Root PASS audit of it.
export function checkConsumedPilot(manifest, audit, { consumed, profileSha256, manifestSha256 }) {
  if (!isObj(manifest) || manifest.schema !== MANIFEST_SCHEMA || manifest.mode !== 'pilot' || manifest.status !== 'observed') refuse('pilot', 'consumed pilot manifest is not an observed pilot');
  if (manifest.profile?.sha256 !== profileSha256) refuse('pilot', 'consumed pilot used a different runtime profile');
  if (!isDeepStrictEqual(manifest.selected_model_indices, consumed.indices)) refuse('pilot', 'consumed pilot indices differ from its manifest');
  for (const i of consumed.indices) if (manifest.jobs?.[i]?.status !== 'returned') refuse('pilot', `consumed pilot model ${i} did not return`);
  if (!isObj(audit) || audit.schema !== PILOT_AUDIT_SCHEMA || audit.result !== 'PASS' || audit.root_bound !== true) refuse('pilot', 'independent Root pilot audit PASS required');
  if (audit.pilot_manifest_sha256 !== manifestSha256 || !isDeepStrictEqual(audit.pilot_model_indices, consumed.indices)) refuse('pilot', 'Root pilot audit does not bind this manifest');
}

export function describeFile(filePath, label, maxBytes = 1 << 26) {
  const held = readPinnedFile(filePath, { maxBytes, label });
  const closeError = closeFd(held.fd);
  if (closeError) refuse('input', `${label}: descriptor close failed: ${closeError.message}`);
  return { path: filePath, bytes: held.bytes, sha256: held.sha256, identity: held.identity };
}

// ---------------------------------------------------------------- output (donor .009 327-370, unchanged)

function createOutputDir(out) {
  const parent = path.dirname(out);
  const st = fs.lstatSync(parent, { bigint: true });
  if (!st.isDirectory() || fs.realpathSync(parent) !== parent) refuse('output', 'output parent must be an existing canonical directory');
  fs.mkdirSync(out, { mode: 0o700 }); // EEXIST refuses a reused directory
  fs.chmodSync(out, 0o700);
  const own = fs.lstatSync(out, { bigint: true });
  if (!own.isDirectory() || (own.mode & 0o777n) !== 0o700n) refuse('output', 'output directory mode');
}

class Retained {
  constructor(dir, cap) { this.dir = dir; this.cap = cap; this.total = 0; this.files = []; }
  write(name, data, perFileCap) {
    const bytes = typeof data === 'string' ? Buffer.from(data, 'utf8') : data;
    if (perFileCap !== undefined && bytes.length > perFileCap) refuse('output', `${name}: ${bytes.length} bytes exceeds ${perFileCap}`);
    if (this.total + bytes.length > this.cap) refuse('output', `aggregate retained bytes would exceed ${this.cap}`);
    const target = path.join(this.dir, name);
    const fd = fs.openSync(target, fs.constants.O_WRONLY | fs.constants.O_CREAT | fs.constants.O_EXCL | fs.constants.O_NOFOLLOW, 0o600);
    try {
      fs.fchmodSync(fd, 0o600);
      let off = 0;
      while (off < bytes.length) off += fs.writeSync(fd, bytes, off, bytes.length - off);
      fs.fsyncSync(fd);
    } finally { fs.closeSync(fd); }
    const st = fs.lstatSync(target, { bigint: true });
    if (!st.isFile() || (st.mode & 0o777n) !== 0o600n || st.size !== BigInt(bytes.length)) refuse('output', `${name}: written file mode/size`);
    this.total += bytes.length;
    const entry = { name, bytes: bytes.length, sha256: sha256(bytes) };
    this.files.push(entry);
    return entry;
  }
}

class StreamBudget {
  constructor(limits) { this.caps = { stdout: limits.stdout_bytes, stderr: limits.stderr_bytes }; this.used = { stdout: 0, stderr: 0 }; this.overflow = { stdout: false, stderr: false }; }
  // Returns the admitted prefix of `chunk`; overflow is recorded, never hidden.
  admit(stream, chunk) {
    const room = this.caps[stream] - this.used[stream];
    if (chunk.length > room) this.overflow[stream] = true;
    const kept = chunk.subarray(0, Math.max(0, room));
    this.used[stream] += kept.length;
    return kept;
  }
}

// ---------------------------------------------------------------- per-model worker lifecycle

const describeMessage = (message) => {
  try { return { json: JSON.stringify(message) ?? null }; } catch (e) { return { inspect: inspect(message, { depth: 6, maxArrayLength: 64 }), json_error: String(e?.message ?? e) }; }
};

export function runModelWorker(job, ctx) {
  const rec = {
    lifecycle: {
      spawned: false, online: false, thread_ready: 0, suffix_installed: false, construct_sent: false,
      terminal_results: 0, close_sent: false, closing_summary: false, deadline_expired: false,
      terminate_requested: false, terminate_reason: null, exit_code: null, positive_exit: false,
      effective_deadline_ms: null, exit_elapsed_ms: null, elapsed_ms: null, streams_drained: false
    },
    bootstrap: null, closing: null, handler: [], script_messages: [], anomalies: [], worker_errors: [],
    streams: { stdout: '', stderr: '', stdout_overflow: false, stderr_overflow: false }, encoded: null
  };
  return new Promise((resolve) => {
    // Actual time is measured from launch through exit and stream drain against
    // the effective deadline fixed here; a delivered timer is not required.
    const started = performance.now();
    const deadline = Math.min(ctx.limits.worker_deadline_ms, Math.max(0, ctx.runDeadlineAt - started));
    rec.lifecycle.effective_deadline_ms = deadline;
    let worker;
    try {
      worker = new Worker(new URL(import.meta.url), {
        workerData: {
          schema: WORKER_SCHEMA, label: job.label, prefix: job.prefix, suffix: job.suffix, summary: job.summary,
          prefixPin: job.prefixPin, suffixPin: job.suffixPin, summaryPin: job.summaryPin,
          job: { model_index: job.model_index, bytes: job.body.bytes, sha256: job.body.sha256 }, body: job.body.buffer.slice(0)
        },
        env: {}, argv: [], execArgv: [], stdout: true, stderr: true,
        resourceLimits: { maxOldGenerationSizeMb: ctx.limits.worker_heap_mb }
      });
    } catch (e) {
      rec.worker_errors.push(errorRecord(e, 'spawn'));
      resolve(rec);
      return;
    }
    rec.lifecycle.spawned = true;
    ctx.current = { terminate: (reason) => terminate(reason) };
    const terminate = (reason) => {
      if (rec.lifecycle.terminate_requested) return;
      rec.lifecycle.terminate_requested = true;
      rec.lifecycle.terminate_reason = reason;
      worker.terminate().catch((e) => rec.worker_errors.push(errorRecord(e, 'terminate')));
    };
    const ended = { stdout: false, stderr: false };
    let exited = false, settled = false;
    // Resolves once: after exit plus both stream ends, or when the deadline
    // passes after exit with a stream still open (recorded as undrained).
    const settle = () => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      rec.lifecycle.streams_drained = ended.stdout && ended.stderr;
      rec.lifecycle.elapsed_ms = performance.now() - started;
      resolve(rec);
    };
    const timer = setTimeout(() => {
      rec.lifecycle.deadline_expired = true;
      if (exited) settle(); else terminate('worker deadline');
    }, deadline);
    for (const stream of ['stdout', 'stderr']) {
      worker[stream].on('data', (chunk) => {
        const kept = ctx.streams.admit(stream, chunk);
        rec.streams[stream] += kept.toString('utf8');
        if (kept.length < chunk.length) { rec.streams[`${stream}_overflow`] = true; rec.anomalies.push(`worker ${stream} exceeded the ${stream} cap`); }
      });
      worker[stream].on('end', () => { ended[stream] = true; if (exited && ended.stdout && ended.stderr) settle(); });
    }
    worker.on('online', () => { rec.lifecycle.online = true; });
    worker.on('error', (e) => rec.worker_errors.push(errorRecord(e, 'worker-error')));
    worker.on('messageerror', (e) => rec.worker_errors.push(errorRecord(e, 'messageerror')));
    worker.on('message', (m) => {
      if (m?.channel === 'script') {
        const message = m.message, type = typeof message?.type === 'string' ? message.type : null;
        if (type === 'ROOT_MODEL_RESULT') {
          rec.lifecycle.terminal_results++;
          const encoded = message.encoded;
          const entry = { seq: m.seq, type, encoded_type: typeof encoded };
          if (typeof encoded === 'string') Object.assign(entry, { encoded_bytes: Buffer.byteLength(encoded, 'utf8'), encoded_sha256: sha256(Buffer.from(encoded, 'utf8')) });
          rec.script_messages.push(entry);
          if (!rec.lifecycle.construct_sent) rec.anomalies.push('terminal result before ROOT_MODEL_CONSTRUCT was sent');
          if (rec.lifecycle.terminal_results > 1) { rec.anomalies.push('duplicate terminal ROOT_MODEL_RESULT'); return; }
          if (typeof encoded !== 'string') rec.anomalies.push('terminal result has no encoded string');
          else rec.encoded = encoded;
          rec.lifecycle.close_sent = true;
          worker.postMessage({ host: 'CLOSE' });
        } else {
          if (type === 'THREAD_READY') {
            rec.lifecycle.thread_ready++;
            if (rec.lifecycle.suffix_installed) rec.anomalies.push('THREAD_READY after suffix installation');
          }
          rec.script_messages.push({ seq: m.seq, type, ...describeMessage(message), ...(m.clone_error ? { clone_error: m.clone_error } : {}) });
        }
      } else if (m?.channel === 'host') {
        if (m.type === 'SUFFIX_INSTALLED') {
          rec.bootstrap = m;
          // The prefix's immediate THREAD_READY is not readiness: require the
          // distinct post-evaluation handshake naming a new current handler.
          if (rec.lifecycle.suffix_installed || rec.lifecycle.construct_sent) { rec.anomalies.push('duplicate SUFFIX_INSTALLED'); return; }
          if (rec.lifecycle.thread_ready !== 1 || m.evidence?.thread_ready !== 1) { rec.anomalies.push('exactly one prefix THREAD_READY must precede suffix installation'); terminate('bootstrap evidence'); return; }
          rec.lifecycle.suffix_installed = true;
          rec.lifecycle.construct_sent = true;
          worker.postMessage({ host: 'CONSTRUCT' });
        } else if (m.type === 'BOOTSTRAP_FAILED') {
          rec.bootstrap = m;
          rec.anomalies.push(`bootstrap failed: ${m.reason}`);
        } else if (m.type === 'HANDLER') {
          rec.handler.push(m);
        } else if (m.type === 'CLOSING') {
          if (rec.lifecycle.closing_summary) rec.anomalies.push('duplicate CLOSING');
          rec.lifecycle.closing_summary = true;
          rec.closing = m;
        } else rec.anomalies.push(`unknown host message ${JSON.stringify(m.type)}`);
      } else rec.anomalies.push('message outside the bridge channels');
    });
    worker.on('exit', (code) => {
      exited = true;
      ctx.current = null;
      rec.lifecycle.exit_code = code;
      rec.lifecycle.exit_elapsed_ms = performance.now() - started;
      rec.lifecycle.positive_exit = code === 0 && !rec.lifecycle.terminate_requested && rec.lifecycle.closing_summary && rec.worker_errors.length === 0;
      // The deadline timer keeps running until both streams have drained.
      if (ended.stdout && ended.stderr) settle();
      else if (rec.lifecycle.deadline_expired) setImmediate(settle);
    });
  });
}

// Host/bootstrap/lifecycle failures are class `host`. A genuine outcome keeps
// its own class: constructor, summary, limit or preservation.
export function classifyModel(rec, job, limits = LIMITS) {
  const reasons = [...rec.anomalies];
  const lc = rec.lifecycle;
  if (!lc.spawned) reasons.push('worker not spawned');
  if (rec.worker_errors.length) reasons.push(`${rec.worker_errors.length} worker error(s)`);
  if (lc.deadline_expired) reasons.push('worker deadline expired; owned worker terminated');
  if (lc.terminate_requested && !lc.deadline_expired) reasons.push(`owned worker terminated: ${lc.terminate_reason}`);
  if (!lc.suffix_installed) reasons.push('suffix installation handshake not observed');
  if (lc.terminal_results !== 1) reasons.push(`expected exactly one terminal result, saw ${lc.terminal_results}`);
  if (!lc.closing_summary) reasons.push('closing summary not observed');
  if (lc.exit_code !== 0) reasons.push(`worker exit code ${lc.exit_code}`);
  if (!lc.positive_exit) reasons.push('no positive worker exit');
  const elapsed = lc.elapsed_ms, limit = lc.effective_deadline_ms;
  if (!Number.isFinite(elapsed) || !Number.isFinite(limit) || elapsed < 0 || limit < 0) reasons.push('actual worker elapsed time or effective deadline not recorded');
  else if (elapsed > limit) reasons.push(`worker actual elapsed ${elapsed}ms exceeds effective deadline ${limit}ms`);
  if (lc.streams_drained !== true) reasons.push('worker stdout/stderr not drained');
  const closing = rec.closing;
  if (closing) {
    if (closing.post_terminal_script_messages) reasons.push(`${closing.post_terminal_script_messages} script message(s) after the terminal result`);
    if (closing.fetch.length) reasons.push(`${closing.fetch.length} fetch call(s) attempted; every fetch is refused`);
    if (closing.body_handouts !== 1) reasons.push(`expected exactly one body handout, saw ${closing.body_handouts}`);
    if (closing.handler_rejections.length) reasons.push('suffix handler rejected');
    if (!closing.handler_settled.includes('fulfilled')) reasons.push('suffix handler did not settle');
  }
  let result = null, limitReason = null;
  if (rec.encoded !== null) {
    const bytes = Buffer.byteLength(rec.encoded, 'utf8');
    if (bytes > limits.model_result_bytes) limitReason = `encoded result ${bytes}B exceeds ${limits.model_result_bytes}B`;
    else {
      try { result = JSON.parse(rec.encoded); } catch (e) { reasons.push(`encoded result is not JSON: ${e.message}`); }
    }
  }
  if (result) {
    if (result.schema !== RESULT_SCHEMA) reasons.push('model result schema');
    if (result.model_index !== job.model_index) reasons.push('model result names a different model');
    if (result.qualification !== false) reasons.push('model result claims qualification');
  }
  const bufferChanged = closing?.buffers?.some((b) => !b.ok) === true;
  let status = 'failed', failureClass, outcome = result?.outcome ?? null;
  if (reasons.length) failureClass = 'host';
  else if (limitReason) { failureClass = 'limit'; reasons.push(limitReason); }
  else if (!result) { failureClass = 'host'; reasons.push('no model result'); }
  else if (result.outcome === 'input_failure') { failureClass = 'host'; reasons.push('worker body input check failed'); }
  else if (result.outcome === 'constructor_exception') failureClass = 'constructor';
  else if (result.outcome === 'summary_error' || result.outcome === 'summary_limit') failureClass = 'summary';
  else if (result.outcome === 'result_limit' || result.outcome === 'timeout') failureClass = 'limit';
  else if (result.outcome !== 'returned') { failureClass = 'host'; reasons.push(`unknown outcome ${JSON.stringify(result.outcome)}`); }
  else if (bufferChanged || result.postcheck_error !== null || result.input_postcheck?.sha256 !== job.body.sha256) { failureClass = 'preservation'; reasons.push('constructor input buffer not preserved'); }
  else if (result.constructor_returned !== true || result.observation_complete !== true || !isObj(result.summary)) { failureClass = 'host'; reasons.push('returned result is incomplete'); }
  else { status = 'returned'; failureClass = null; }
  return { status, failure_class: failureClass, outcome, reasons, result };
}

// ---------------------------------------------------------------- reducer

// FileManager stages, identical to the summary and the catalog rule reference:
// prefix once, whole-name ECMAScript trim, backslash->slash, encodeURIComponent
// per segment. No lowercasing, decoding or basename inference.
export function stagesOf(raw) {
  const logical_name = TEXTURE_PREFIX + raw;
  const filemanager_name = logical_name.trim();
  const http_path = filemanager_name.replace(/\\/g, '/').split('/').map(encodeURIComponent).join('/');
  return { logical_name, filemanager_name, http_path };
}

export class ReducerLimitError extends Error {
  constructor(limit) { super(`reducer limit ${limit}`); this.name = 'ReducerLimitError'; this.limit = limit; }
}
const rneed = (v, m) => { if (!v) throw new Error(`reducer: ${m}`); };

// One walk over the complete unchanged summary: JSON depth, plus the UTF-16
// .length of every string VALUE occurrence (object keys excluded, no
// deduplication), accumulated in `totals` across the jobs of one invocation.
function walkSummary(value, totals, caps) {
  const stack = [[value, 1]];
  while (stack.length) {
    const [v, d] = stack.pop();
    if (typeof v === 'string') {
      if ((totals.string_code_units += v.length) > caps.string_code_units) throw new ReducerLimitError('string_code_units');
      continue;
    }
    if (v === null || typeof v !== 'object') continue;
    if (d > caps.json_depth) throw new ReducerLimitError('json_depth');
    for (const k of Object.keys(v)) stack.push([v[k], d + 1]);
  }
}

export function newReducerTotals() { return { nodes: 0, declarations: 0, node_slots: 0, string_code_units: 0 }; }

// Reduces one unchanged summary into declarations with node/slot links and the
// model's original links. `totals` is reducer-global and enforces caps.
export function reduceModel(summary, record, relations, totals, caps = LIMITS.declaration_reducer_global) {
  walkSummary(summary, totals, caps);
  rneed(isObj(summary) && Array.isArray(summary.textures) && Array.isArray(summary.texture_declarations) && Array.isArray(summary.nodes), 'summary tables');
  const { textures, texture_declarations: decl, nodes } = summary;
  rneed(decl.length === textures.length, 'declaration count differs from texture table');
  if ((totals.nodes += nodes.length) > caps.nodes) throw new ReducerLimitError('nodes');
  if ((totals.declarations += textures.length) > caps.declarations) throw new ReducerLimitError('declarations');
  const declarations = textures.map((raw, texture_index) => {
    rneed(typeof raw === 'string', `texture ${texture_index} raw string`);
    const stages = stagesOf(raw);
    const d = decl[texture_index];
    rneed(isObj(d) && Object.keys(d).sort().join(',') === 'constructor_pointer,filemanager_name,http_path,logical_name,raw_name,texture_index', `declaration ${texture_index} keys`);
    rneed(d.texture_index === texture_index && d.constructor_pointer === `/textures/${texture_index}` && d.raw_name === raw, `declaration ${texture_index} identity`);
    rneed(d.logical_name === stages.logical_name && d.filemanager_name === stages.filemanager_name && d.http_path === stages.http_path, `declaration ${texture_index} differs from the fixed stage rule`);
    return { model_index: record.model_index, texture_index, constructor_pointer: d.constructor_pointer, raw_name: raw,
      logical_name: d.logical_name, filemanager_name: d.filemanager_name, http_path: d.http_path, wire_target: `/${d.http_path}`,
      node_links: [], zero_face_node_links: 0 };
  });
  const unresolved = [];
  let resolved = 0;
  nodes.forEach((node, node_index) => {
    rneed(isObj(node) && node.node_index === node_index && Array.isArray(node.textures) && Array.isArray(node.texture_references), `node ${node_index} shape`);
    rneed(node.texture_references.length === node.textures.length, `node ${node_index} reference count`);
    if ((totals.node_slots += node.textures.length) > caps.node_slots) throw new ReducerLimitError('node_slots');
    node.textures.forEach((slot, slot_index) => {
      const ref = node.texture_references[slot_index];
      const hit = typeof slot === 'number' && Number.isInteger(slot) && slot >= 0 && slot < textures.length;
      rneed(isObj(ref) && ref.slot_index === slot_index && ref.table_index === (hit ? slot : null) && ref.state === (hit ? 'resolved' : 'unresolved'), `node ${node_index} slot ${slot_index} reference`);
      if (hit) {
        resolved++;
        declarations[slot].node_links.push({ node_index, slot_index });
        if (node.face_count === 0) declarations[slot].zero_face_node_links++;
      } else unresolved.push({ node_index, slot_index, slot });
    });
  });
  const source_links = record.model_relation_indices.map((r) => ({
    model_relation_index: r, map_index: relations[r].original_relation.map_index, map_name: relations[r].original_relation.map_name,
    original_relation_index: relations[r].original_relation.relation_index, core_group_pointer: relations[r].core_group_pointer
  }));
  return {
    model_index: record.model_index, original_query_index: record.original_query_index, wire_target: record.wire_target,
    physical_input_alias_group: record.physical_input_alias_group, source_links, declarations, unresolved_slots: unresolved,
    counts: { nodes: nodes.length, declarations: declarations.length, resolved_slots: resolved, unresolved_slots: unresolved.length,
      unlinked_declarations: declarations.filter((d) => d.node_links.length === 0).length }
  };
}

// Groups exact HTTP nested targets (exact string identity; case-distinct) with
// every declaration and source link. Unknown models stay listed as unknown.
export function nestedTargets(reduced) {
  const table = new Map();
  for (const model of reduced) {
    for (const d of model.declarations) {
      if (!table.has(d.http_path)) table.set(d.http_path, { http_path: d.http_path, wire_target: d.wire_target, declarations: [], source_links: [] });
      const t = table.get(d.http_path);
      t.declarations.push({ model_index: d.model_index, texture_index: d.texture_index, raw_name: d.raw_name, linked: d.node_links.length > 0 });
      for (const link of model.source_links) t.source_links.push({ model_index: model.model_index, ...link });
    }
  }
  return [...table.values()].map((t, target_index) => ({ target_index, ...t }));
}

// ---------------------------------------------------------------- run

export function hostDescriptor() {
  return describeFile(fileURLToPath(import.meta.url), 'host');
}

const jobLabel = (i) => `model-${String(i).padStart(4, '0')}`;

// `testing` exists for synthetic controls only; the CLI never passes it.
export async function runHost(args, testing = null) {
  // Unbound default: refuse before any file read, output creation or Worker start.
  const binding = validateBinding(testing?.binding ?? ROOT_SOURCE_BINDING);
  const pins = { profile: binding.runtime_profile, unbound: testing?.unboundPin ?? UNBOUND_PROFILE_PIN, prefix: testing?.prefixPin ?? PREFIX_PIN, summary: testing?.summaryPin ?? SUMMARY_PIN };
  const limits = testing?.limits ? { ...LIMITS, ...testing.limits } : LIMITS;
  const domain = testing?.domain ?? DOMAIN;
  const log = testing?.log ?? (() => {});
  const runStarted = performance.now();
  // 1. Pinned profile, unbound projection and separate Root admission before any target read.
  const profileHeld = readPinnedFile(path.resolve(args.profile), { pin: pins.profile, maxBytes: pins.profile.bytes, label: 'profile' });
  const held = [profileHeld];
  let result;
  try {
    const profile = JSON.parse(Buffer.from(profileHeld.buffer).toString('utf8'));
    const host = hostDescriptor();
    const admissionHeld = readPinnedFile(path.resolve(args.admission), { maxBytes: ADMISSION_MAX_BYTES, label: 'admission' });
    held.push(admissionHeld);
    let admissionJson;
    try { admissionJson = JSON.parse(Buffer.from(admissionHeld.buffer).toString('utf8')); } catch (e) { refuse('admission', `admission is not JSON: ${e.message}`); }
    checkAdmissionProjection(admissionJson, binding);
    if (!isObj(profile.unbound_profile) || typeof profile.unbound_profile.path !== 'string') refuse('profile', 'unbound_profile descriptor required');
    checkDescriptor(profile.unbound_profile, 'unbound_profile');
    const unboundHeld = readPinnedFile(profile.unbound_profile.path, { desc: profile.unbound_profile, maxBytes: pins.unbound.bytes, label: 'unbound_profile' });
    held.push(unboundHeld);
    if (unboundHeld.bytes !== pins.unbound.bytes || unboundHeld.sha256 !== pins.unbound.sha256) refuse('profile', 'unbound profile differs from fixed pin');
    const unbound = JSON.parse(Buffer.from(unboundHeld.buffer).toString('utf8'));
    const bound = validateProfile(profile, unbound, { limits, prefixPin: pins.prefix, summaryPin: pins.summary, unboundPin: pins.unbound, domain });
    const admission = validateAdmission(admissionJson, { hostDescriptor: host, profileSha256: pins.profile.sha256, bound, limits });
    const pilotHeld = [];
    if (admission.consumed) {
      const m = readPinnedFile(admission.consumed.manifest.path, { desc: admission.consumed.manifest, maxBytes: PILOT_SOURCE_MAX_BYTES, label: 'consumed_pilot.manifest' });
      held.push(m); pilotHeld.push(m);
      const a = readPinnedFile(admission.consumed.audit.path, { desc: admission.consumed.audit, maxBytes: PILOT_SOURCE_MAX_BYTES, label: 'consumed_pilot.audit' });
      held.push(a); pilotHeld.push(a);
      const parse = (h) => { try { return JSON.parse(Buffer.from(h.buffer).toString('utf8')); } catch (e) { refuse('pilot', `${h.label} is not JSON: ${e.message}`); } };
      checkConsumedPilot(parse(m), parse(a), { consumed: admission.consumed, profileSha256: pins.profile.sha256, manifestSha256: m.sha256 });
    }
    // The exact Node binary named by the runtime profile (full hash, not retained).
    if (process.execPath !== profile.node.path) refuse('runtime', 'running Node binary differs from the runtime profile');
    const nodeHeld = readPinnedFile(process.execPath, { desc: profile.node, maxBytes: profile.node.bytes, label: 'node' });
    const nodeClose = closeFd(nodeHeld.fd);
    if (nodeClose) refuse('runtime', `node descriptor close failed: ${nodeClose.message}`);
    host.node = { path: nodeHeld.path, bytes: nodeHeld.bytes, sha256: nodeHeld.sha256, identity: nodeHeld.identity, version: process.version };
    // 2. Fresh exclusive private output directory.
    createOutputDir(admission.output_path);
    const retained = new Retained(admission.output_path, limits.total_retained_result_bytes);
    result = await execute({ profile, bound, admission, host, retained, held, limits, pins, log, runStarted, admissionHeld, profileHeld, unboundHeld, pilotHeld });
  } catch (e) {
    // The earlier failure stays primary; held close failures are appended.
    const failed = closeHeld(held).filter((c) => !c.closed);
    if (failed.length && e instanceof Error) e.message += `; held descriptor close failed: ${failed.map((c) => `${c.label}: ${c.error.message}`).join('; ')}`;
    throw e;
  }
  // execute closes every held descriptor before publication; anything left is a failure.
  const late = closeHeld(held).filter((c) => !c.closed);
  if (late.length) { result.status = 'failed'; result.errors.push(...late.map((c) => `held descriptor close failed after publication: ${c.label}: ${c.error.message}`)); }
  return result;
}

async function execute({ profile, bound, admission, host, retained, held, limits, pins, log, runStarted, admissionHeld, profileHeld, unboundHeld, pilotHeld }) {
  const selected = admission.selected;
  const selectedSet = new Set(selected);
  const jobs = bound.records.map((r) => ({ model_index: r.model_index, label: jobLabel(r.model_index), profile_pointer: `/models/${r.model_index}`,
    status: selectedSet.has(r.model_index) ? 'not_started' : 'outside_batch' }));
  const describe = (h) => ({ path: h.path, bytes: h.bytes, sha256: h.sha256, identity: h.identity });
  const manifest = {
    schema: MANIFEST_SCHEMA, task: 'T07.007.014.012', mode: admission.mode, status: 'incomplete',
    claims: { qualification: false, runtime_ready: false, note: 'host observation only; Root qualifies. Not texture acquisition, image decode, compile, rendering, travel, story or save.' },
    construction_limit: CONSTRUCTION_LIMIT,
    host: { path: host.path, bytes: host.bytes, sha256: host.sha256, identity: host.identity }, node: host.node,
    profile: describe(profileHeld), unbound_profile: describe(unboundHeld), admission: describe(admissionHeld),
    // Full domain retention is the pinned runtime profile plus per-job pointers,
    // not a self-contained copy: every table is recovered from `profile`.
    domain_retention: { mode: 'pinned-runtime-profile-plus-job-pointers', profile: describe(profileHeld), unbound_profile: describe(unboundHeld),
      job_pointer: '/models/{model_index}', tables: ['/models', '/model_group_relations', '/maps', '/case_alias_groups'],
      counts: { models: bound.records.length, relations: bound.relations.length, maps: bound.maps.length, case_groups: bound.cases.length,
        case_rows: bound.cases.reduce((n, g) => n + g.model_indices.length, 0) } },
    required_head: { value: admission.required_head, verified_by_host: false, live_head_verified_by: 'Root caller' },
    guard_qualification: { ...admission.guard_qualification, meaning: 'approved prior guard qualification; not this run\'s receipt',
      this_run_guard_verified_by_host: false, containment_by_host: false },
    consumed_pilot: admission.consumed ? { indices: admission.consumed.indices, manifest: describe(pilotHeld[0]), audit: describe(pilotHeld[1]) } : null,
    limits, selected_model_indices: selected,
    source_prechecks: [], source_postchecks: [], body_final_rereads: [], held_closes: [],
    // Logical staging (one body at a time) is distinct from literal body FDs:
    // a postcheck or final reread can temporarily add a descriptor.
    body_fds: { max_staged_bodies: 0, max_open_body_fds: 0, close_failures: 0 },
    jobs, first_failure: null, later_failures: [], files: retained.files, errors: [], stopped_reason: null, nested_targets_file: null
  };
  const fail = (record) => { if (manifest.first_failure === null) manifest.first_failure = record; else manifest.later_failures.push(record); };
  const ctx = { limits, runDeadlineAt: runStarted + limits.all_run_deadline_ms, current: null, streams: new StreamBudget(limits) };
  const runTimer = setTimeout(() => { ctx.runExpired = true; ctx.current?.terminate('entire host deadline'); }, Math.max(0, ctx.runDeadlineAt - performance.now()));
  const staged = [];
  const reduced = [];
  const totals = newReducerTotals();
  let stagedBodies = 0, openBodyFds = 0;
  const bodyFdOpened = () => { manifest.body_fds.max_open_body_fds = Math.max(manifest.body_fds.max_open_body_fds, ++openBodyFds); };
  const bodyFdClosed = (error) => { if (error === null) openBodyFds--; else manifest.body_fds.close_failures++; };
  let fdAccountingUnknown = false;
  const recordPostcheckFd = (pc) => {
    if (pc.reread_opened === null) fdAccountingUnknown = true;
    else if (pc.reread_opened) { bodyFdOpened(); bodyFdClosed(pc.reread_fd_closed ? null : 'failed'); }
  };
  // A failed body read that opened its descriptor still counts that literal FD and
  // its close outcome; a failed close is never inferred closed.
  const recordPartialOpen = (e) => {
    const opened = partialOpenOf(e);
    if (opened === null) fdAccountingUnknown = true;
    else if (opened.fd_opened) { bodyFdOpened(); bodyFdClosed(opened.fd_close_error); }
  };
  try {
    // 3. Stage only the fixed prefix/summary/suffix; bodies are staged one per job.
    const prefix = readPinnedFile(profile.compiled_prefix.path, { desc: profile.compiled_prefix, maxBytes: pins.prefix.bytes, label: 'compiled_prefix' });
    held.push(prefix); staged.push(prefix);
    const summary = readPinnedFile(profile.summary_module.path, { desc: profile.summary_module, maxBytes: pins.summary.bytes, label: 'summary_module' });
    held.push(summary); staged.push(summary);
    const suffix = readPinnedFile(profile.model_suffix.path, { desc: profile.model_suffix, maxBytes: SUFFIX_MAX_BYTES, label: 'model_suffix' });
    held.push(suffix); staged.push(suffix);
    const decoder = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true });
    checkSuffix(decoder.decode(new Uint8Array(suffix.buffer)), limits);
    decoder.decode(new Uint8Array(summary.buffer));
    for (const h of staged) manifest.source_prechecks.push({ label: h.label, ...describe(h), parent_identity: h.parent_identity });

    // 4. One fresh sequential worker per selected logical model; stop on a failed job.
    let stop = null;
    for (const model_index of selected) {
      const entry = jobs[model_index];
      if (stop) { entry.reason = stop; continue; }
      if (ctx.runExpired || performance.now() >= ctx.runDeadlineAt) { stop = 'entire host deadline'; entry.reason = stop; continue; }
      const hostNow = describeFile(host.path, 'host');
      if (hostNow.sha256 !== host.sha256 || !sameIdentity(hostNow.identity, host.identity)) { stop = 'host source changed'; entry.reason = stop; fail({ phase: 'host', model_index, failure_class: 'host', message: stop }); continue; }
      const record = bound.records[model_index];
      let body;
      try {
        body = readPinnedFile(bound.bodies[model_index].path, { desc: bound.bodies[model_index], maxBytes: limits.input_body_bytes, label: `${entry.label}.body` });
      } catch (e) {
        recordPartialOpen(e);
        Object.assign(entry, { status: 'failed', failure_class: 'host', reasons: [`body staging: ${e?.message}`] });
        fail({ phase: 'body-staging', model_index, failure_class: 'host', message: e?.message });
        stop = `fail-fast after ${entry.label} body staging failure`;
        continue;
      }
      stagedBodies++;
      manifest.body_fds.max_staged_bodies = Math.max(manifest.body_fds.max_staged_bodies, stagedBodies);
      bodyFdOpened();
      entry.status = 'started';
      log(`${entry.label}: started`);
      const job = {
        label: entry.label, model_index, prefix: prefix.buffer.slice(0), suffix: suffix.buffer.slice(0), summary: summary.buffer.slice(0),
        prefixPin: { bytes: prefix.bytes, sha256: prefix.sha256 }, suffixPin: { bytes: suffix.bytes, sha256: suffix.sha256 },
        summaryPin: { bytes: summary.bytes, sha256: summary.sha256 }, body
      };
      let rec, verdict, postcheck, bodyClose;
      try {
        rec = await runModelWorker(job, ctx);
        verdict = classifyModel(rec, job, limits);
      } finally {
        // Postcheck and close this body's FD after its owned Worker; one close
        // attempt, its outcome retained.
        postcheck = postcheckPinnedFile(body);
        recordPostcheckFd(postcheck);
        bodyClose = closeFd(body.fd);
        bodyFdClosed(bodyClose);
        stagedBodies--;
        if (bodyClose) entry.body_close_error = bodyClose;
      }
      const verdictReturned = verdict.status === 'returned';
      if (!postcheck.ok && verdict.status === 'returned') { verdict.status = 'failed'; verdict.failure_class = 'preservation'; }
      if (!postcheck.ok) verdict.reasons.push(...postcheck.failures.map((f) => `body postcheck: ${f}`));
      // A body close error fails the job; an earlier job failure stays primary.
      const closeIsPrimary = bodyClose !== null && verdict.status === 'returned';
      if (closeIsPrimary) { verdict.status = 'failed'; verdict.failure_class = 'host'; }
      if (bodyClose) verdict.reasons.push(`body descriptor close failed: ${bodyClose.message}`);
      // Already-observed preservation/close failures apply before reduction; no
      // reducer work follows them. The bounded returned result is still retained.
      let reducedModel = null;
      if (verdict.status === 'returned') {
        try {
          reducedModel = reduceModel(verdict.result.summary, record, bound.relations, totals, limits.declaration_reducer_global);
        } catch (e) {
          verdict.status = 'failed';
          verdict.failure_class = e instanceof ReducerLimitError ? 'limit' : 'reducer';
          verdict.reasons.push(e.message);
        }
      } else if (verdictReturned) verdict.reasons.push('reducer skipped after body preservation/close failure');
      const report = {
        schema: MODEL_REPORT_SCHEMA, label: entry.label, model_index, status: verdict.status, failure_class: verdict.failure_class,
        outcome: verdict.outcome, reasons: verdict.reasons, construction_limit: CONSTRUCTION_LIMIT,
        source_record: record, profile_pointer: entry.profile_pointer,
        body: { path: body.path, bytes: body.bytes, sha256: body.sha256, identity: body.identity, postcheck, fd_closed: bodyClose === null, close_error: bodyClose },
        prefix: { unchanged: true, bytes: prefix.bytes, sha256: prefix.sha256 }, summary_module: { unchanged: true, bytes: summary.bytes, sha256: summary.sha256 },
        suffix: { unchanged: true, bytes: suffix.bytes, sha256: suffix.sha256 },
        lifecycle: rec.lifecycle, bootstrap: rec.bootstrap, handler: rec.handler, closing: rec.closing,
        script_messages: rec.script_messages, worker_errors: rec.worker_errors, streams: rec.streams,
        exception: verdict.result?.exception ?? null, constructor_returned: verdict.result?.constructor_returned ?? null,
        reduced: reducedModel, result_file: null
      };
      try {
        if (rec.encoded !== null) report.result_file = retained.write(`${entry.label}.result.json`, rec.encoded, limits.model_result_bytes);
        const reportEntry = retained.write(`${entry.label}.host.json`, `${JSON.stringify(report, null, 1)}\n`, limits.model_result_bytes);
        Object.assign(entry, { status: report.status, failure_class: report.failure_class, outcome: report.outcome, report: reportEntry.name, result: report.result_file?.name ?? null, reasons: verdict.reasons });
      } catch (e) {
        manifest.errors.push(errorRecord(e, `${entry.label}-retention`));
        Object.assign(entry, { status: 'failed', failure_class: verdict.status === 'returned' ? 'limit' : verdict.failure_class,
          outcome: verdict.outcome, reasons: [...verdict.reasons, `retention: ${e.message}`] });
      }
      if (entry.status === 'returned') reduced.push(reducedModel);
      log(`${entry.label}: ${entry.status}${entry.failure_class ? ` (${entry.failure_class})` : ''}`);
      if (entry.status === 'failed') {
        fail({ phase: 'job', model_index, failure_class: entry.failure_class, outcome: entry.outcome ?? null, message: entry.reasons[0] ?? null });
        if (bodyClose && !closeIsPrimary) fail({ phase: 'body-close', model_index, failure_class: 'host', message: bodyClose.message });
        entry.body_close_recorded = bodyClose !== null;
        stop = `fail-fast after ${entry.label} ${entry.failure_class} failure`;
      }
    }
    manifest.stopped_reason = stop;
  } catch (e) {
    manifest.errors.push(errorRecord(e, 'execute'));
    fail({ phase: 'execute', model_index: null, failure_class: 'host', message: e.message });
    for (const j of jobs) if (j.body_close_error && !j.body_close_recorded) fail({ phase: 'body-close', model_index: j.model_index, failure_class: 'host', message: j.body_close_error.message });
    for (const i of selected) if (jobs[i].status === 'not_started') jobs[i].reason ??= 'run stopped before start';
  } finally {
    clearTimeout(runTimer);
  }
  // 5. Complete nested-target table only when every selected job returned.
  const allReturned = selected.every((i) => jobs[i].status === 'returned');
  const nested = {
    schema: NESTED_SCHEMA, complete: allReturned, selected_model_indices: selected,
    returned_model_indices: reduced.map((r) => r.model_index),
    unknown_model_indices: selected.filter((i) => jobs[i].status !== 'returned'),
    totals: allReturned ? { ...totals, nested_targets: null } : null,
    targets: allReturned ? nestedTargets(reduced) : null, models: reduced
  };
  if (nested.totals) nested.totals.nested_targets = nested.targets.length;
  try { manifest.nested_targets_file = retained.write('NESTED_TARGETS.json', `${JSON.stringify(nested, null, 1)}\n`); }
  catch (e) { manifest.errors.push(errorRecord(e, 'nested-retention')); fail({ phase: 'nested-retention', model_index: null, failure_class: 'limit', message: e.message }); }
  // 6. Post-checks of fixed sources, profile/admission/pilot and host, then a
  // final one-at-a-time reread of every selected body.
  for (const h of staged) manifest.source_postchecks.push(postcheckPinnedFile(h));
  for (const h of [profileHeld, unboundHeld, admissionHeld, ...pilotHeld]) manifest.source_postchecks.push(postcheckPinnedFile(h));
  try {
    const hostAfter = describeFile(host.path, 'host');
    manifest.source_postchecks.push({ label: 'host', path: host.path, ok: hostAfter.sha256 === host.sha256 && sameIdentity(hostAfter.identity, host.identity), failures: [] });
  } catch (e) { manifest.source_postchecks.push({ label: 'host', path: host.path, ok: false, failures: [e.message] }); }
  for (const i of selected) {
    const desc = bound.bodies[i];
    try {
      let again;
      try { again = readPinnedFile(desc.path, { desc, maxBytes: limits.input_body_bytes, label: `${jobLabel(i)}.body` }); }
      catch (e) { recordPartialOpen(e); throw e; }
      bodyFdOpened();
      const closeError = closeFd(again.fd);
      bodyFdClosed(closeError);
      if (closeError) refuse('input', `descriptor close failed: ${closeError.message}`);
      manifest.body_final_rereads.push({ model_index: i, path: desc.path, bytes: again.bytes, sha256: again.sha256, ok: true });
    } catch (e) {
      manifest.body_final_rereads.push({ model_index: i, path: desc.path, ok: false, failure: e?.message });
    }
  }
  for (const p of manifest.source_postchecks) if (!p.ok) fail({ phase: 'source-postcheck', model_index: null, failure_class: 'preservation', message: `${p.label}: ${p.failures.join('; ')}` });
  for (const r of manifest.body_final_rereads) if (!r.ok) fail({ phase: 'body-final-reread', model_index: r.model_index, failure_class: 'preservation', message: r.failure });
  // Every held source/admission/pilot descriptor closes before terminal publication.
  manifest.held_closes = closeHeld(held);
  for (const c of manifest.held_closes) if (!c.closed) fail({ phase: 'held-close', model_index: null, failure_class: 'host', message: `${c.label}: ${c.error.message}` });
  // Never publish a definitive literal maximum/close count that excludes a path.
  if (fdAccountingUnknown) Object.assign(manifest.body_fds, { max_open_body_fds: null, close_failures: null, literal_accounting: 'unknown: a failed body read could not carry its descriptor outcome' });
  const runCheck = (phase) => {
    const elapsed = performance.now() - runStarted;
    const check = { phase, elapsed_ms: elapsed, limit_ms: limits.all_run_deadline_ms, ok: elapsed <= limits.all_run_deadline_ms };
    if (!check.ok) manifest.errors.push({ phase: 'run-deadline', name: 'Deadline', message: `entire host elapsed ${elapsed}ms exceeds ${limits.all_run_deadline_ms}ms ${phase}`, code: null, stack: null });
    return check;
  };
  manifest.run_deadline = { limit_ms: limits.all_run_deadline_ms, run_timer_expired: ctx.runExpired === true, after_postchecks: runCheck('after final postchecks') };
  manifest.streams = { used: ctx.streams.used, overflow: ctx.streams.overflow };
  manifest.counts = Object.fromEntries(['outside_batch', 'not_started', 'started', 'failed', 'returned'].map((s) => [s, jobs.filter((j) => j.status === s).length]));
  manifest.status = allReturned && manifest.first_failure === null && manifest.errors.length === 0 ? 'observed' : 'failed';
  manifest.elapsed_ms = performance.now() - runStarted;
  manifest.retained_bytes_before_manifest = retained.total;
  let status = manifest.status;
  try { retained.write('MANIFEST.json', `${JSON.stringify(manifest, null, 1)}\n`); }
  catch (e) { status = 'failed'; manifest.errors.push(errorRecord(e, 'manifest-retention')); }
  // Publication itself must also finish in time; a late publication adds one
  // exclusive deadline record and never rewrites the manifest.
  const published = runCheck('after manifest publication');
  if (!published.ok) {
    status = 'failed';
    try {
      retained.write('RUN_DEADLINE.json', `${JSON.stringify({ schema: MANIFEST_SCHEMA, record: 'run-deadline', status, manifest_status: manifest.status, check: published }, null, 1)}\n`);
    } catch (e) { manifest.errors.push(errorRecord(e, 'run-deadline-retention')); }
  }
  return { status, output_path: admission.output_path, counts: manifest.counts, stopped_reason: manifest.stopped_reason,
    first_failure: manifest.first_failure, later_failures: manifest.later_failures.length, errors: manifest.errors.map((e) => e.message) };
}

// ---------------------------------------------------------------- worker side

// Runs inside each fresh Worker. Host bindings stay in this module scope; the
// classic script sees only the explicit globals installed below.
async function workerMain(data) {
  const defer = setImmediate, now = () => performance.now();
  const post = (m) => parentPort.postMessage({ channel: 'host', ...m });
  const fail = (reason, extra = {}) => { post({ type: 'BOOTSTRAP_FAILED', reason, ...extra }); parentPort.close(); };
  const check = (buffer, pin) => buffer.byteLength === pin.bytes && sha256(new Uint8Array(buffer)) === pin.sha256;
  if (!check(data.prefix, data.prefixPin) || !check(data.suffix, data.suffixPin) || !check(data.summary, data.summaryPin)) return fail('prefix/suffix/summary payload differs from its pin');
  if (!check(data.body, data.job)) return fail('body payload differs from its pin');
  let source, summarizeModel;
  try {
    const decoder = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true });
    source = decoder.decode(new Uint8Array(data.prefix)) + decoder.decode(new Uint8Array(data.suffix));
    decoder.decode(new Uint8Array(data.summary));
  } catch (e) { return fail('script is not UTF-8', { error: errorRecord(e, 'decode') }); }
  // Import the exact staged summary bytes, unmodified, before classic evaluation.
  try {
    const summaryModule = await import(`data:text/javascript;base64,${Buffer.from(data.summary).toString('base64')}`);
    summarizeModel = summaryModule.summarizeModel;
    if (typeof summarizeModel !== 'function') throw new Error('summarizeModel export missing');
  } catch (e) { return fail('summary module import failed', { error: errorRecord(e, 'summary-import') }); }

  let seq = 0, threadReady = 0, terminal = 0, postTerminal = 0, handler = null, handlerAtThreadReady;
  const assignments = [];
  Object.defineProperty(globalThis, 'onmessage', {
    configurable: false, enumerable: true,
    get: () => handler,
    set: (value) => { assignments.push({ seq: seq++, type: typeof value, after_thread_ready: threadReady > 0 }); handler = value; }
  });
  const scriptPostMessage = function postMessage(message) {
    const s = seq++;
    if (terminal) postTerminal++;
    if (message?.type === 'THREAD_READY') { threadReady++; handlerAtThreadReady = handler; }
    if (message?.type === 'ROOT_MODEL_RESULT') terminal++;
    try { parentPort.postMessage({ channel: 'script', seq: s, message }); } catch (e) {
      parentPort.postMessage({ channel: 'script', seq: s, message: { type: typeof message?.type === 'string' ? message.type : null }, clone_error: String(e?.message ?? e) });
    }
  };
  // Every fetch refuses; attempts are recorded for the parent.
  const fetchLog = [];
  const refusingFetch = async function fetch(url) {
    fetchLog.push({ url: String(url).slice(0, 512) });
    throw new TypeError('fetch refused: model construction has no network or file adapter');
  };
  // One exact standalone copy of the pinned body; any later request throws.
  const handed = [];
  let handouts = 0;
  const takeBody = () => {
    handouts++;
    if (handouts > 1) throw new Error('body already handed out');
    const out = data.body.slice(0);
    handed.push(out);
    return out;
  };
  const hostBridge = Object.freeze({ job: Object.freeze({ ...data.job }), summarizeModel, takeBody });
  Object.defineProperty(globalThis, 'ROOT_MODEL_HOST', { value: hostBridge, writable: false, configurable: false, enumerable: false });
  const globals = {
    self: globalThis, postMessage: scriptPostMessage, fetch: refusingFetch,
    performance, crypto: webcrypto, TextEncoder, TextDecoder
  };
  for (const [name, value] of Object.entries(globals)) Object.defineProperty(globalThis, name, { value, writable: true, configurable: true, enumerable: name !== 'self' });
  const supplied = [...Object.keys(globals), 'ROOT_MODEL_HOST'];

  const handlerSettled = [], handlerRejections = [];
  parentPort.on('message', (m) => {
    if (m?.host === 'CONSTRUCT') {
      const current = handler;
      post({ type: 'HANDLER', event: 'dispatch', current_is_suffix: current !== handlerAtThreadReady, at: now() });
      Promise.resolve().then(() => current.call(globalThis, { data: { type: 'ROOT_MODEL_CONSTRUCT' } })).then(
        () => { handlerSettled.push('fulfilled'); post({ type: 'HANDLER', event: 'fulfilled', at: now() }); },
        (e) => { const r = errorRecord(e, 'handler'); handlerRejections.push(r); post({ type: 'HANDLER', event: 'rejected', error: r }); }
      );
    } else if (m?.host === 'CLOSE') {
      defer(() => {
        const buffers = handed.map((buffer) => {
          const bytes = buffer.byteLength, digest = sha256(new Uint8Array(buffer));
          return { bytes, sha256: digest, ok: bytes === data.job.bytes && digest === data.job.sha256 };
        });
        post({
          type: 'CLOSING', terminal_results: terminal, post_terminal_script_messages: postTerminal,
          handler_settled: handlerSettled, handler_rejections: handlerRejections,
          fetch: fetchLog, body_handouts: handouts, buffers
        });
        parentPort.close();
      });
    }
  });

  const evaluationStarted = performance.now();
  try {
    vm.runInThisContext(source, { filename: `model-${data.label}.js` });
  } catch (e) {
    return fail('classic script evaluation threw', { error: errorRecord(e, 'evaluate'), assignments, thread_ready: threadReady });
  }
  const evidence = {
    supplied_globals: supplied, thread_ready: threadReady, onmessage_assignments: assignments,
    handler_is_function: typeof handler === 'function', handler_changed_after_thread_ready: handler !== handlerAtThreadReady,
    last_assignment_after_thread_ready: assignments.at(-1)?.after_thread_ready === true,
    script: { bytes: data.prefix.byteLength + data.suffix.byteLength, prefix_sha256: data.prefixPin.sha256, suffix_sha256: data.suffixPin.sha256, summary_sha256: data.summaryPin.sha256 },
    evaluation_ms: performance.now() - evaluationStarted
  };
  if (!evidence.handler_is_function || !evidence.handler_changed_after_thread_ready || !evidence.last_assignment_after_thread_ready || threadReady !== 1) {
    return fail('suffix handler not installed after the prefix THREAD_READY', { evidence });
  }
  post({ type: 'SUFFIX_INSTALLED', evidence });
}

// ---------------------------------------------------------------- entry

async function cli() {
  const out = (s) => process.stdout.write(`${s}\n`.slice(0, LIMITS.stdout_bytes));
  const err = (s) => process.stderr.write(`${s}\n`.slice(0, LIMITS.stderr_bytes));
  let args;
  try {
    validateBinding(ROOT_SOURCE_BINDING);
    if (process.execArgv.length || process.env.NODE_OPTIONS) refuse('runtime', 'no Node execArgv/NODE_OPTIONS are admitted');
    args = parseArgs(process.argv.slice(2));
  } catch (e) {
    err(`refused: ${e.message}`);
    return 2;
  }
  try {
    const result = await runHost(args);
    out(JSON.stringify(result));
    return result.status === 'observed' ? 0 : 1;
  } catch (e) {
    err(`${e instanceof Refusal ? 'refused' : 'error'}: ${e.message}`);
    return e instanceof Refusal ? 2 : 1;
  }
}

if (!isMainThread && workerData?.schema === WORKER_SCHEMA) {
  workerMain(workerData).catch((e) => { parentPort.postMessage({ channel: 'host', type: 'BOOTSTRAP_FAILED', reason: 'worker bootstrap threw', error: errorRecord(e, 'bootstrap') }); parentPort.close(); });
} else if (isMainThread && process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  cli().then((code) => { process.exitCode = code; });
}
