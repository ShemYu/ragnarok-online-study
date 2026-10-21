#!/usr/bin/env node
// T06.003.003.007 nested model-texture declaration catalog.
// Links declared Model texture tables to their original models, RSW parents
// and placements from qualified .004/.006 metadata. No asset/body read, fetch,
// compile, constructor run or render; a declaration is not an availability fact.
// T07.007.009 adds one second exact profile route over the qualified .008
// four-root supplement; see TARGET_MODEL_TEXTURES.md.
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { performance } from 'node:perf_hooks';
import { fileURLToPath } from 'node:url';

export const PROFILE_SHA256 = '432354b127890ca3b37432c61949f88a41439c6cdeb3cfbe21d27adc621b0c68';
export const PROFILE_BYTES = 4231;
export const PROFILE_PATH = 'docs/project/fixtures/T06.003.003.007-profile.json';
export const SCHEMA = 'T06-model-texture-catalog-1';
export const TASK = 'T06.003.003.007';
const MODEL_PREFIX = 'data\\model\\';
const TEXTURE_PREFIX = 'data\\texture\\';
export const NEW_PROFILE_SHA256 = 'c8e0a1aa853afa34088c4abca193addc5e8e66db0621fd950733b9d3339a7787';
export const NEW_PROFILE_BYTES = 4711;
export const NEW_PROFILE_PATH = 'docs/project/fixtures/T07.007.009-profile.json';
export const NEW_TASK = 'T07.007.009';
const DEPENDENCY_POINTER = '/summary/model_dependencies';
const SELF = fileURLToPath(import.meta.url);
const CHECKOUT = path.resolve(path.dirname(SELF), '..', '..');
const OUTPUT_PARENT = path.join(CHECKOUT, '.tools', 'renewal');
const READ_FLAGS = fs.constants.O_RDONLY | fs.constants.O_NONBLOCK | (fs.constants.O_NOFOLLOW || 0);
const WRITE_FLAGS = fs.constants.O_WRONLY | fs.constants.O_CREAT | fs.constants.O_EXCL | (fs.constants.O_NOFOLLOW || 0);

export const LIMITS = Object.freeze([
  'All tables are conservative declarations. No actual fetch/compile/render result is predicted.',
  'Static unlinked global slots stay inventoried; zero-face linked slots are not filtered.',
  'Animated true is a node-key fact; hook/placement/cache/GL predicates remain unobserved.',
  'Original loader names remain distinct even when trimmed HTTP paths or body jobs coincide.',
  'Node numeric markers and diagnostics are preserved, not repaired or a format-validity verdict.',
  'All carried core and ground gaps stay explicit; declarations cover returned tables, while exceptions retain unknown tables.'
]);

// Mirrors the pinned profile policy; the CLI requires exact equality.
export const DEFAULT_POLICY = Object.freeze({
  max_report_bytes: 67108864, max_jobs_jsonl_bytes: 67108864, max_row_json_bytes: 4194304,
  max_manifest_bytes: 67108864, max_source_catalog_bytes: 67108864, max_fixture_bytes: 1048576,
  max_catalog_bytes: 134217728, max_stdout_bytes: 4096, max_roots: 4096, max_jobs: 16384,
  max_model_targets: 16384, max_parent_links: 262144, max_placement_occurrences: 2097152,
  max_declarations: 65536, max_nodes: 65536, max_node_slots: 262144, max_string_code_units: 1048576,
  max_json_depth: 64, run_timeout_ms: 120000
});

// In-process seams for tests. The CLI never sets these. afterPinnedJson
// (role, value) runs on the new route only after a complete pinned read/hash/
// parse and returns the value to admit; afterBuild receives the pin roles.
export const hooks = {
  writeSync: null,
  closeSync: null,
  afterBuild: null,
  afterPublish: null,
  ownSourcePath: null,
  afterPinnedJson: null
};

// detail is a private diagnostic for tests; stdout carries only reason.
export class Refusal extends Error {
  constructor(reason, detail = null) {
    super(reason);
    this.name = 'Refusal';
    this.reason = reason;
    this.detail = detail;
  }
}

const refuse = (reason = 'invalid_input', detail = null) => new Refusal(reason, detail);
function need(condition, reason, detail) { if (!condition) throw refuse(reason, detail); }
const own = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);
const isObj = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
const nonneg = (v) => Number.isSafeInteger(v) && v >= 0;
const isHex = (v, n) => typeof v === 'string' && v.length === n && /^[0-9a-f]+$/.test(v);
const sha256 = (buf) => crypto.createHash('sha256').update(buf).digest('hex');

function exactKeys(obj, keys) {
  const actual = Object.keys(obj);
  return actual.length === keys.length && keys.every((key) => own(obj, key));
}

// Object key order is not significant; array order and typed values are.
export function deepEqual(a, b) {
  if (a === b) return true;
  if (typeof a !== typeof b || a === null || b === null || typeof a !== 'object') return false;
  if (Array.isArray(a) !== Array.isArray(b)) return false;
  if (Array.isArray(a)) return a.length === b.length && a.every((v, i) => deepEqual(v, b[i]));
  const ka = Object.keys(a);
  return ka.length === Object.keys(b).length && ka.every((k) => own(b, k) && deepEqual(a[k], b[k]));
}

// Ordinary JSON data only: finite numbers, plain objects/dense arrays, no
// cycles/accessors/symbols/undefined/functions/BigInt. Explicit marker objects
// are ordinary data. Lone surrogates are legitimate strings here.
export function assertJsonData(root, policy = DEFAULT_POLICY) {
  const ancestors = new Set();
  const visit = (v, depth) => {
    if (depth > policy.max_json_depth) throw refuse('depth_limit');
    if (v === null || typeof v === 'boolean') return;
    if (typeof v === 'number') { need(Number.isFinite(v)); return; }
    if (typeof v === 'string') { need(v.length <= policy.max_string_code_units, 'string_limit'); return; }
    need(typeof v === 'object');
    need(!ancestors.has(v));
    ancestors.add(v);
    const keys = Reflect.ownKeys(v);
    if (Array.isArray(v)) {
      need(Object.getPrototypeOf(v) === Array.prototype && keys.length === v.length + 1);
      for (let i = 0; i < v.length; i++) {
        const d = Object.getOwnPropertyDescriptor(v, i);
        need(d && own(d, 'value'));
        visit(d.value, depth + 1);
      }
    } else {
      const proto = Object.getPrototypeOf(v);
      need(proto === Object.prototype || proto === null);
      for (const key of keys) {
        need(typeof key === 'string');
        const d = Object.getOwnPropertyDescriptor(v, key);
        need(own(d, 'value') && d.enumerable);
        visit(d.value, depth + 1);
      }
    }
    ancestors.delete(v);
  };
  visit(root, 0);
}

function clone(v) {
  if (v === null || typeof v !== 'object') return v;
  if (Array.isArray(v)) return v.map(clone);
  const out = {};
  for (const key of Object.keys(v)) {
    // JSON keys such as __proto__ are data, including on nested metadata.
    Object.defineProperty(out, key, { value: clone(v[key]), enumerable: true, writable: true, configurable: true });
  }
  return out;
}

// FileManager stages: prefix once, ECMAScript trim of the whole name, then
// backslash→slash and per-segment encodeURIComponent. Never pre-decodes.
export function stagesOf(prefix, raw) {
  const logical_name = prefix + raw;
  const filemanager_name = logical_name.trim();
  let http_path;
  try { http_path = filemanager_name.replace(/\\/g, '/').split('/').map(encodeURIComponent).join('/'); }
  catch (error) {
    if (error instanceof URIError) throw refuse('uri_encoding_unsupported');
    throw error;
  }
  return { logical_name, filemanager_name, http_path };
}

const isUndefinedMarker = (v) => isObj(v) && exactKeys(v, ['special']) && v.special === 'undefined';
const keyCount = (v) => nonneg(v) || isUndefinedMarker(v);

function checkNumericFields(nf) {
  need(isObj(nf));
  for (const key of ['finite', 'nan', 'positive_infinity', 'negative_infinity', 'undefined', 'null', 'exceptional_locations_omitted']) {
    need(nonneg(nf[key]));
  }
  for (const key of ['min', 'max']) need(nf[key] === null || typeof nf[key] === 'number');
  need(Array.isArray(nf.exceptional_locations));
  for (const e of nf.exceptional_locations) need(isObj(e) && typeof e.location === 'string' && typeof e.category === 'string');
}

function checkRow(row) {
  need(isObj(row));
  need(typeof row.id === 'string' && row.id === row.job_id && row.kind === 'model');
  need(nonneg(row.input_bytes) && isHex(row.complete_sha256, 64) && isHex(row.header_version_bytes, 12));
  need(row.worker_started === true);
  need(isObj(row.cleanup) && exactKeys(row.cleanup, ['exit_observed', 'exit_code', 'terminated_by_parent']) &&
    row.cleanup.exit_observed === true && row.cleanup.exit_code === 0 && row.cleanup.terminated_by_parent === false);
  if (row.outcome === 'returned') {
    need(row.constructor_returned === true && isObj(row.summary) && !own(row, 'exception'));
  } else {
    need(row.outcome === 'constructor_exception' && row.constructor_returned === false && !own(row, 'summary'));
    need(isObj(row.exception) && row.exception.phase === 'constructor');
  }
}

// Validates one returned summary and projects nodes/declarations.
function projectSummary(summary, totals, policy) {
  const textures = summary.textures;
  need(Array.isArray(textures) && Array.isArray(summary.texture_declarations) && Array.isArray(summary.nodes));
  need(typeof summary.animation_by_node_keys === 'boolean' && keyCount(summary.global_position_keys));
  checkNumericFields(summary.numeric_fields);
  need((totals.declarations += textures.length) <= policy.max_declarations, 'declaration_limit');
  need((totals.nodes += summary.nodes.length) <= policy.max_nodes, 'node_limit');
  need(summary.texture_declarations.length === textures.length);
  const declarations = textures.map((raw, index) => {
    need(typeof raw === 'string');
    const stages = stagesOf(TEXTURE_PREFIX, raw); // before comparing supplied stages
    const d = summary.texture_declarations[index];
    need(isObj(d) && exactKeys(d, ['texture_index', 'constructor_pointer', 'raw_name', 'logical_name', 'filemanager_name', 'http_path']));
    need(d.texture_index === index && d.constructor_pointer === `/textures/${index}` && d.raw_name === raw);
    need(d.logical_name === stages.logical_name && d.filemanager_name === stages.filemanager_name && d.http_path === stages.http_path);
    return { texture_index: index, constructor_pointer: d.constructor_pointer, raw_name: raw,
      logical_name: d.logical_name, filemanager_name: d.filemanager_name, http_path: d.http_path,
      nested_target_index: null, node_links: [] };
  });
  let animated = false;
  let resolved = 0;
  let unresolved = 0;
  const nodes = summary.nodes.map((node, node_index) => {
    need(isObj(node) && node.node_index === node_index && Array.isArray(node.textures) && Array.isArray(node.texture_references));
    need(node.texture_references.length === node.textures.length);
    need((totals.slots += node.textures.length) <= policy.max_node_slots, 'node_slot_limit');
    need(nonneg(node.face_count));
    const k = node.keyframe_counts;
    need(isObj(k) && exactKeys(k, ['rotation', 'position', 'scale', 'texture_groups']));
    for (const key of ['rotation', 'position', 'scale', 'texture_groups']) need(keyCount(k[key]));
    if ([k.rotation, k.position, k.scale].some((c) => typeof c === 'number' && c > 0)) animated = true;
    checkNumericFields(node.numeric_fields);
    node.textures.forEach((slot, slot_index) => {
      const ref = node.texture_references[slot_index];
      const hit = typeof slot === 'number' && Number.isInteger(slot) && slot >= 0 && slot < textures.length;
      need(isObj(ref) && exactKeys(ref, ['slot_index', 'table_index', 'state']) && ref.slot_index === slot_index);
      need(ref.table_index === (hit ? slot : null) && ref.state === (hit ? 'resolved' : 'unresolved'));
      if (hit) {
        resolved++;
        declarations[slot].node_links.push({ node_index, slot_index });
      } else unresolved++;
    });
    return { node_index, textures: clone(node.textures), texture_references: clone(node.texture_references),
      face_count: node.face_count, keyframe_counts: clone(k), numeric_fields: clone(node.numeric_fields) };
  });
  need(animated === summary.animation_by_node_keys);
  return { nodes, declarations, animated, resolved, unresolved };
}

// Pure core: no I/O, no caller mutation. Throws Refusal on malformed input.
export function buildCatalog(input, policy = DEFAULT_POLICY) {
  assertJsonData(input, policy);
  need(isObj(input) && exactKeys(input, ['roots', 'remaining_gap_root_ordinals', 'prior_first_level_gaps',
    'first_level_model_jobs', 'model_targets', 'model_rows']));
  const { roots, remaining_gap_root_ordinals: gaps, prior_first_level_gaps: priorGaps,
    first_level_model_jobs: sourceJobs, model_targets: targets, model_rows: rows } = input;
  need(Array.isArray(roots) && Array.isArray(gaps) && Array.isArray(priorGaps) && Array.isArray(sourceJobs) &&
    Array.isArray(targets) && Array.isArray(rows));
  need(roots.length <= policy.max_roots, 'root_limit');
  need(rows.length <= policy.max_jobs, 'job_limit');
  need(targets.length <= policy.max_model_targets, 'model_target_limit');

  // Roots and carried RSW gaps.
  const rootsByRsw = new Map();
  const expectedGaps = [];
  roots.forEach((root, ordinal) => {
    need(isObj(root) && root.ordinal === ordinal && isObj(root.edges) && isObj(root.edges.rsw) && own(root.edges.rsw, 'job_id'));
    const jobId = root.edges.rsw.job_id;
    if (jobId === null) expectedGaps.push(ordinal);
    else {
      need(typeof jobId === 'string');
      if (!rootsByRsw.has(jobId)) rootsByRsw.set(jobId, []);
      rootsByRsw.get(jobId).push({ root_ordinal: ordinal, edge_kind: 'rsw' });
    }
  });
  need(deepEqual(gaps, expectedGaps));

  // Source RSW model jobs and their original loader entries.
  const sourceByIndex = new Map();
  const sourceIds = new Set();
  let parentEntries = 0;
  let placementTotal = 0;
  for (const job of sourceJobs) {
    need(isObj(job) && job.kind === 'rsw' && job.role === 'model' && typeof job.id === 'string' && nonneg(job.source_job_index));
    need(!sourceIds.has(job.id) && !sourceByIndex.has(job.source_job_index));
    need(!own(job, 'occurrence_summary_pointer') || job.occurrence_summary_pointer === DEPENDENCY_POINTER);
    need(deepEqual(job.root_references, rootsByRsw.get(job.id) || []));
    need(Array.isArray(job.occurrence_loader_indexes) && Array.isArray(job.loader_entries));
    need((placementTotal += job.occurrence_loader_indexes.length) <= policy.max_placement_occurrences, 'placement_limit');
    need((parentEntries += job.loader_entries.length) <= policy.max_parent_links, 'parent_link_limit');
    const placements = job.loader_entries.map(() => []);
    let next = 0;
    job.occurrence_loader_indexes.forEach((loaderIndex, occurrence) => {
      need(Number.isInteger(loaderIndex) && loaderIndex >= 0 && loaderIndex < job.loader_entries.length && loaderIndex <= next);
      if (loaderIndex === next) next++;
      placements[loaderIndex].push(occurrence);
    });
    need(next === job.loader_entries.length);
    job.loader_entries.forEach((entry, index) => {
      need(isObj(entry) && entry.index === index && typeof entry.raw_name === 'string' && nonneg(entry.target_index));
      const stages = stagesOf(MODEL_PREFIX, entry.raw_name);
      need(entry.source_name_pointer === `${DEPENDENCY_POINTER}/${placements[index][0]}/filename`);
      need(entry.logical_name === stages.logical_name && entry.filemanager_name === stages.filemanager_name &&
        entry.http_path === stages.http_path);
    });
    sourceIds.add(job.id);
    sourceByIndex.set(job.source_job_index, { job, placements, used: job.loader_entries.map(() => false) });
  }
  for (const jobId of rootsByRsw.keys()) need(sourceIds.has(jobId));

  // Physical constructor rows.
  const rowById = new Map();
  rows.forEach((row, index) => {
    checkRow(row);
    need(!rowById.has(row.id));
    rowById.set(row.id, index);
  });

  // Original targets and the complete parent bijection.
  const rowTargets = rows.map(() => []);
  const targetIndexes = new Set();
  const parentLinks = [];
  let placementOccurrences = 0;
  let rootExpanded = 0;
  targets.forEach((target, ordinal) => {
    need(isObj(target) && target.model_ordinal === ordinal && nonneg(target.target_index) && !targetIndexes.has(target.target_index));
    targetIndexes.add(target.target_index);
    need(typeof target.job_id === 'string' && rowById.has(target.job_id) && typeof target.http_path === 'string');
    const rowIndex = rowById.get(target.job_id);
    const row = rows[rowIndex];
    need(isObj(target.body) && target.body.bytes === row.input_bytes && target.body.sha256 === row.complete_sha256);
    rowTargets[rowIndex].push(ordinal);
    need(Array.isArray(target.referrers) && target.referrers.length > 0);
    for (const referrer of target.referrers) {
      need(isObj(referrer) && exactKeys(referrer, ['job_index', 'loader_index', 'role']) && referrer.role === 'model');
      need(nonneg(referrer.job_index) && nonneg(referrer.loader_index) && sourceByIndex.has(referrer.job_index));
      const source = sourceByIndex.get(referrer.job_index);
      const entry = source.job.loader_entries[referrer.loader_index];
      need(entry !== undefined && !source.used[referrer.loader_index]);
      need(entry.target_index === target.target_index && entry.http_path === target.http_path);
      source.used[referrer.loader_index] = true;
      const placement_indexes = source.placements[referrer.loader_index];
      placementOccurrences += placement_indexes.length;
      rootExpanded += placement_indexes.length * source.job.root_references.length;
      parentLinks.push({
        model_ordinal: ordinal,
        catalog_target_index: target.target_index,
        referrer: clone(referrer),
        source_job_id: source.job.id,
        loader_entry: clone(entry),
        root_references: clone(source.job.root_references),
        placement_indexes: placement_indexes.slice(),
        placement_pointers: placement_indexes.map((p) => `${DEPENDENCY_POINTER}/${p}`)
      });
    }
  });
  for (const { used } of sourceByIndex.values()) need(used.every(Boolean));
  need(rowTargets.every((list) => list.length > 0));

  // Constructor jobs, declarations and nested targets.
  const totals = { declarations: 0, nodes: 0, slots: 0 };
  const counts = { returned: 0, exceptions: 0, empty: 0, nonempty: 0, globalDecl: 0, expandedDecl: 0,
    resolved: 0, unresolved: 0, animTrue: 0, animFalse: 0 };
  const nestedByPath = new Map();
  const nested = [];
  const jobs = rows.map((row, job_index) => {
    const base = {
      source_row_index: job_index, id: row.id, job_id: row.job_id, kind: row.kind, input_bytes: row.input_bytes,
      complete_sha256: row.complete_sha256, header_version_bytes: row.header_version_bytes, outcome: row.outcome,
      constructor_returned: row.constructor_returned, worker_started: row.worker_started, cleanup: clone(row.cleanup),
      target_model_ordinals: rowTargets[job_index]
    };
    if (row.outcome === 'constructor_exception') {
      counts.exceptions++;
      return { ...base, exception: clone(row.exception), animation_by_node_keys: null, numeric_fields: null,
        nodes: null, declarations: null };
    }
    const p = projectSummary(row.summary, totals, policy);
    counts.returned++;
    if (p.declarations.length === 0) counts.empty++; else counts.nonempty++;
    counts.globalDecl += p.declarations.length;
    counts.expandedDecl += p.declarations.length * rowTargets[job_index].length;
    counts.resolved += p.resolved;
    counts.unresolved += p.unresolved;
    if (p.animated) counts.animTrue++; else counts.animFalse++;
    for (const d of p.declarations) {
      let target = nestedByPath.get(d.http_path);
      if (!target) {
        target = { index: nested.length, http_path: d.http_path, referrers: [] };
        nestedByPath.set(d.http_path, target);
        nested.push(target);
      }
      target.referrers.push({ job_index, texture_index: d.texture_index });
      d.nested_target_index = target.index;
    }
    return { ...base, exception: null, animation_by_node_keys: p.animated, numeric_fields: clone(row.summary.numeric_fields),
      nodes: p.nodes, declarations: p.declarations };
  });

  return {
    counts: {
      roots: roots.length,
      constructor_jobs: rows.length,
      model_targets: targets.length,
      returned_jobs: counts.returned,
      constructor_exception_jobs: counts.exceptions,
      global_declarations: counts.globalDecl,
      target_expanded_declarations: counts.expandedDecl,
      nested_targets: nested.length,
      model_parent_links: parentLinks.length,
      model_placement_occurrences: placementOccurrences,
      root_expanded_model_placements: rootExpanded,
      resolved_node_slots: counts.resolved,
      unresolved_node_slots: counts.unresolved,
      animation_jobs: { true: counts.animTrue, false: counts.animFalse, unknown: counts.exceptions },
      remaining_core_gap_roots: gaps.length,
      prior_first_level_gaps: priorGaps.length,
      returned_empty_jobs: counts.empty,
      returned_nonempty_jobs: counts.nonempty
    },
    roots: clone(roots),
    remaining_gap_root_ordinals: clone(gaps),
    prior_first_level_gaps: clone(priorGaps),
    model_targets: clone(targets),
    model_parent_links: parentLinks,
    jobs,
    nested_targets: nested,
    limits: LIMITS.slice()
  };
}

// ---------------------------------------------------------------- file I/O

export function identityOf(st) {
  return { dev: String(st.dev), ino: String(st.ino), size: String(st.size), mtime_ns: String(st.mtimeNs), ctime_ns: String(st.ctimeNs) };
}
const sameIdentity = (a, b) => ['dev', 'ino', 'size', 'mtime_ns', 'ctime_ns'].every((key) => a[key] === b[key]);

function assertLinkFree(abs) {
  const parts = abs.split(path.sep).filter(Boolean);
  let cur = path.sep;
  for (const part of parts) {
    cur = path.join(cur, part);
    let st;
    try { st = fs.lstatSync(cur); } catch (error) { throw refuse(error.code === 'ENOENT' ? 'missing_input' : 'input_io_error'); }
    if (st.isSymbolicLink()) throw refuse('symlink_refused');
  }
}

export function safeJoin(root, rel) {
  if (typeof rel !== 'string' || rel.length === 0 || rel.length > 4096 || rel.includes('\0') || rel.includes('\\') ||
      path.isAbsolute(rel) || rel.split('/').some((part) => part === '..' || part === '.' || part === '')) {
    throw refuse('path_refused');
  }
  const abs = path.resolve(root, rel);
  if (!abs.startsWith(root + path.sep)) throw refuse('path_refused');
  return abs;
}

// lstat → open(O_NOFOLLOW|O_NONBLOCK) → fstat → size check before allocation
// → full bounded read → close → re-lstat; identity must hold throughout.
export function readPinnedFile(abs, { maxBytes, expectBytes, expectSha }) {
  if (!fs.constants.O_NOFOLLOW) throw refuse('environment');
  assertLinkFree(abs);
  const before = fs.lstatSync(abs, { bigint: true });
  if (before.isSymbolicLink()) throw refuse('symlink_refused');
  if (!before.isFile()) throw refuse('special_file_refused');
  if (before.nlink !== 1n) throw refuse('link_refused');
  if (before.size > BigInt(maxBytes)) throw refuse('size_limit');
  if (expectBytes !== undefined && before.size !== BigInt(expectBytes)) throw refuse('pin_mismatch');
  let fd;
  try { fd = fs.openSync(abs, READ_FLAGS); } catch { throw refuse('input_io_error'); }
  let opened, after, buf;
  try {
    opened = fs.fstatSync(fd, { bigint: true });
    if (!opened.isFile() || opened.nlink !== 1n || !sameIdentity(identityOf(opened), identityOf(before))) throw refuse('identity_changed');
    if (opened.size > BigInt(maxBytes)) throw refuse('size_limit');
    const size = Number(opened.size);
    buf = Buffer.alloc(size);
    let off = 0;
    while (off < size) {
      const n = fs.readSync(fd, buf, off, size - off, off);
      if (n < 1) throw refuse('identity_changed');
      off += n;
    }
    if (fs.readSync(fd, Buffer.alloc(1), 0, 1, size) !== 0) throw refuse('identity_changed');
    after = fs.fstatSync(fd, { bigint: true });
  } finally { fs.closeSync(fd); }
  const relinked = fs.lstatSync(abs, { bigint: true });
  const id0 = identityOf(before);
  if (!sameIdentity(id0, identityOf(after)) || !sameIdentity(id0, identityOf(relinked))) throw refuse('identity_changed');
  const digest = sha256(buf);
  if (expectSha !== undefined && digest !== expectSha) throw refuse('pin_mismatch');
  return { abs, buffer: buf, bytes: buf.length, sha256: digest, identity: id0, maxBytes };
}

// Full re-read and hash, not identity alone.
function recheckPins(pins) {
  for (const pin of pins) {
    let again;
    try { again = readPinnedFile(pin.abs, { maxBytes: pin.maxBytes, expectBytes: pin.bytes, expectSha: pin.sha256 }); }
    catch { return false; }
    if (!sameIdentity(again.identity, pin.identity)) return false;
  }
  return true;
}

function parseJson(buffer) {
  let text;
  try { text = new TextDecoder('utf-8', { fatal: true }).decode(buffer); } catch { throw refuse('invalid_json'); }
  try { return JSON.parse(text); } catch { throw refuse('invalid_json'); }
}

// One JSON row per LF line: final LF, no blank line, no suffix, row cap excludes LF.
export function parseJsonl(buffer, maxRowBytes) {
  if (buffer.length === 0) return [];
  need(buffer[buffer.length - 1] === 0x0a, 'invalid_jsonl');
  const rows = [];
  let start = 0;
  while (start < buffer.length) {
    const end = buffer.indexOf(0x0a, start);
    need(end > start, 'invalid_jsonl');
    need(end - start <= maxRowBytes, 'row_limit');
    rows.push(parseJson(buffer.subarray(start, end)));
    start = end + 1;
  }
  return rows;
}

// ---------------------------------------------------------------- admission

function validateProfile(profile, route = ROUTES[PROFILE_PATH]) {
  need(isObj(profile) && profile.schema === 'T06-model-texture-catalog-profile-1' && profile.task === route.task, 'profile_invalid');
  need(deepEqual(profile.policy, DEFAULT_POLICY) && deepEqual(profile.limitations, LIMITS), 'profile_invalid');
  const pin = (p, withPath = true) => isObj(p) && nonneg(p.bytes) && isHex(p.sha256, 64) && (!withPath || typeof p.path === 'string');
  need(pin(profile.constructor_profile) && pin(profile.summary) && pin(profile.authored), 'profile_invalid');
  need(isObj(profile.inputs) && exactKeys(profile.inputs, ['report', 'jobs', 'manifest', 'catalog']), 'profile_invalid');
  for (const key of Object.keys(profile.inputs)) need(pin(profile.inputs[key]), 'profile_invalid');
  need(isObj(profile.rule_sources) && Object.keys(profile.rule_sources).length === 4, 'profile_invalid');
  for (const key of Object.keys(profile.rule_sources)) need(pin(profile.rule_sources[key], false), 'profile_invalid');
  need(typeof profile.client_source_root === 'string' && isObj(profile.expected_counts), 'profile_invalid');
  if (route.name === 'supplement') validateSupplementProfile(profile);
}

const omit = (obj, keys) => Object.fromEntries(Object.keys(obj).filter((k) => !keys.includes(k)).map((k) => [k, obj[k]]));

// Binds report/jobs/manifest/catalog to the qualified upstream premises and
// returns the six-field core input. Consumes metadata only.
export function admitCorpus({ profile, constructorProfile, report, rows, manifest, catalog }) {
  const ok = (condition) => need(condition, 'admission_discrepancy');
  const cp = constructorProfile;
  ok(isObj(cp) && cp.schema === 'T06-model-constructor-profile-1' && cp.task === 'T06.003.003.006' && isObj(cp.counts));
  const nJobs = cp.counts.constructor_jobs;
  const nTargets = cp.counts.model_targets;
  // Report premises.
  ok(isObj(report) && report.schema === 'T06-model-constructor-report-1' && report.task === 'T06.003.003.006');
  ok(report.mode === 'corpus' && report.qualified === true);
  ok(report.profile_sha256 === profile.constructor_profile.sha256 && report.summary_sha256 === profile.summary.sha256);
  ok(isObj(report.common_summary) && report.common_summary.sha256 === profile.summary.sha256 && report.common_summary.bytes === profile.summary.bytes);
  ok(isObj(report.input) && report.input.sha256 === profile.inputs.manifest.sha256 && report.input.bytes === profile.inputs.manifest.bytes);
  const pinned = Array.isArray(report.pinned_inputs) ? report.pinned_inputs : [];
  const role = (r) => pinned.find((p) => isObj(p) && p.role === r);
  ok(role('corpus') && role('corpus').sha256 === profile.inputs.manifest.sha256);
  ok(role('catalog') && role('catalog').sha256 === profile.inputs.catalog.sha256);
  ok(role('profile') && role('profile').sha256 === profile.constructor_profile.sha256);
  ok(role('summary') && role('summary').sha256 === profile.summary.sha256);
  ok(deepEqual(report.preserved_counts, cp.counts));
  const sp = report.source_postchecks;
  ok(isObj(sp) && sp.ok === true && sp.expected === 18 && sp.checked === 18 && deepEqual(sp.failed, []));
  ok(report.pinned_inputs_identity_unchanged_after_run === true);
  ok(isObj(report.postchecks) && report.postchecks.ok === true && report.postchecks.checked === nTargets);
  const c = report.cleanup;
  ok(isObj(c) && c.workers_started === nJobs && c.exits_observed === nJobs && deepEqual(c.unverified, []) && c.halted === null && c.verified === true);
  const st = report.storage;
  ok(isObj(st) && st.publication_failed === false && st.jobs_tail_uncertain === false && st.jobs_close_verified === true);
  const jf = report.jobs_file;
  ok(isObj(jf) && jf.path === 'jobs.jsonl' && jf.bytes === profile.inputs.jobs.bytes && jf.sha256 === profile.inputs.jobs.sha256 &&
    jf.records === nJobs && jf.complete === true);
  ok(rows.length === nJobs && Array.isArray(report.job_accounting) && report.job_accounting.length === nJobs);
  const rc = report.counts;
  ok(isObj(rc) && isObj(rc.job_outcomes) && isObj(rc.target_outcomes));
  const outcomeCounts = {};
  for (const key of Object.keys(rc.job_outcomes)) outcomeCounts[key] = 0;
  for (const row of rows) ok(isObj(row) && own(outcomeCounts, row.outcome) && ++outcomeCounts[row.outcome] > 0);
  ok(outcomeCounts.returned + outcomeCounts.constructor_exception === nJobs);
  ok(rc.expected_jobs === nJobs && rc.records === nJobs && rc.attempted === nJobs && rc.expected_targets === nTargets);
  ok(deepEqual(rc.job_outcomes, outcomeCounts));
  // Manifest premises.
  ok(isObj(manifest) && manifest.schema === 'T06-model-constructor-input-1' && manifest.task === 'T06.003.003.006');
  ok(deepEqual(manifest.counts, cp.counts));
  ok(isObj(manifest.availability) && isObj(manifest.availability.catalog) && manifest.availability.catalog.sha256 === profile.inputs.catalog.sha256);
  ok(Array.isArray(manifest.jobs) && manifest.jobs.length === nJobs && Array.isArray(manifest.targets) && manifest.targets.length === nTargets);
  ok(Array.isArray(manifest.roots) && manifest.roots.length === cp.counts.roots);
  ok(Array.isArray(manifest.remaining_gap_root_ordinals) && manifest.remaining_gap_root_ordinals.length === cp.counts.remaining_core_gap_roots);
  ok(deepEqual(report.expected_job_ids, manifest.jobs.map((j) => j.job_id)));
  ok(deepEqual(report.expected_target_ids, manifest.targets.map((t) => t.model_ordinal)));
  ok(deepEqual(report.roots, manifest.roots) && deepEqual(report.remaining_gap_root_ordinals, manifest.remaining_gap_root_ordinals));
  ok(deepEqual(report.prior_first_level_gaps, manifest.prior_first_level_gaps));
  // Catalog premises.
  ok(isObj(catalog) && catalog.schema === 'T06-map-dependency-catalog-1' && catalog.task === 'T06.003.003.004' && catalog.mode === 'corpus');
  ok(Array.isArray(catalog.jobs) && Array.isArray(catalog.targets));
  ok(deepEqual(manifest.roots, catalog.roots) && deepEqual(manifest.remaining_gap_root_ordinals, catalog.remaining_gap_root_ordinals));
  // Rows ↔ manifest jobs ↔ report accounting.
  const outcomeById = new Map();
  rows.forEach((row, i) => {
    const job = manifest.jobs[i];
    ok(isObj(job) && row.id === job.job_id && row.job_id === job.job_id && row.input_bytes === job.input_bytes &&
      row.complete_sha256 === job.complete_sha256 && row.header_version_bytes === job.header_version_bytes);
    ok(Array.isArray(job.target_model_ordinals) && job.target_model_ordinals.length > 0);
    for (const ordinal of job.target_model_ordinals) ok(isObj(manifest.targets[ordinal]) && manifest.targets[ordinal].job_id === job.job_id);
    ok(deepEqual(report.job_accounting[i], { ...omit(row, ['summary', 'log']), summary_payload_in_jsonl_only: true }));
    outcomeById.set(row.job_id, row.outcome);
  });
  // Targets ↔ report targets ↔ catalog targets.
  ok(Array.isArray(report.targets) && report.targets.length === nTargets);
  const targetOutcomes = {};
  for (const key of Object.keys(rc.target_outcomes)) targetOutcomes[key] = 0;
  let catalogModelTargets = 0;
  for (const t of catalog.targets) if (isObj(t) && Array.isArray(t.referrers) && t.referrers.some((r) => isObj(r) && r.role === 'model')) catalogModelTargets++;
  ok(catalogModelTargets === nTargets);
  manifest.targets.forEach((target, i) => {
    ok(isObj(target) && outcomeById.has(target.job_id));
    const outcome = outcomeById.get(target.job_id);
    ok(deepEqual(report.targets[i], { ...target, constructor_outcome: outcome }));
    ok(own(targetOutcomes, outcome) && ++targetOutcomes[outcome] > 0);
    ok(nonneg(target.target_index) && target.catalog_pointer === `/targets/${target.target_index}`);
    const ct = catalog.targets[target.target_index];
    ok(isObj(ct) && ct.index === target.target_index && ct.http_path === target.http_path && deepEqual(ct.referrers, target.referrers));
  });
  ok(deepEqual(rc.target_outcomes, targetOutcomes));
  const first_level_model_jobs = [];
  catalog.jobs.forEach((job, index) => {
    if (isObj(job) && job.kind === 'rsw' && job.role === 'model') first_level_model_jobs.push({ ...job, source_job_index: index });
  });
  return {
    roots: manifest.roots,
    remaining_gap_root_ordinals: manifest.remaining_gap_root_ordinals,
    prior_first_level_gaps: manifest.prior_first_level_gaps,
    first_level_model_jobs,
    model_targets: manifest.targets,
    model_rows: rows
  };
}

// ---------------------------------------------------------------- T07.007.009 route

// Exactly two profile routes: exact path first, then exact bytes/SHA before parse.
export const ROUTES = Object.freeze({
  [PROFILE_PATH]: Object.freeze({ name: 'catalog', task: TASK, path: PROFILE_PATH, bytes: PROFILE_BYTES, sha256: PROFILE_SHA256 }),
  [NEW_PROFILE_PATH]: Object.freeze({ name: 'supplement', task: NEW_TASK, path: NEW_PROFILE_PATH, bytes: NEW_PROFILE_BYTES, sha256: NEW_PROFILE_SHA256 })
});

const freezeDeep = (v) => { if (v && typeof v === 'object') { for (const k of Object.keys(v)) freezeDeep(v[k]); Object.freeze(v); } return v; };

// Frozen premises of the qualified .008 four-root supplement. The world ledger
// profile and availability totals are compared as declared, never opened.
export const SUPPLEMENT = freezeDeep({
  constructor_profile: { path: 'docs/project/fixtures/T07.007.008-profile.json', bytes: 4168,
    sha256: 'cc53e3455c1117c5fc29431c342f925d4d58d5334bbe5d0c29f67d8489050dea' },
  constructor_producer: {
    task: 'T07.007.008',
    commit: '31e16bf669cd67a0a0f114d1abc02a753c38868e',
    program: { path: 'tools/renewal/probe_model_constructors.mjs', bytes: 105504,
      sha256: '02079022287d188486c90cfb8380a22fa4f04a636c27bbca9606d569fdfb5d23' },
    worker: { path: 'tools/renewal/model_constructor_worker.mjs', bytes: 11388,
      sha256: 'c1eee8dabacf3e69bb2fbe7fde8ed4e5fbd386a4a3ac768936484beceb22a3f4' }
  },
  rule_sources: {
    'src/Loaders/Model.js': { bytes: 30922, sha256: 'd4643fc9a1a95747b41ee55537fe3159c2927e9840630291cce9d55bea20fe57' },
    'src/Loaders/MapLoader.js': { bytes: 14466, sha256: 'c71b01f300f62bbc6e7432444e2521d713473dc47c9c6e25a54a832d5c92a705' },
    'src/Core/FileManager.js': { bytes: 11279, sha256: '75c37d192bf21e7b40817a6f2fe27ef536601515c07fe20c7ce8346d50376cd7' },
    'src/Renderer/Map/AnimatedModels.js': { bytes: 23493, sha256: 'b993b685426e01cb40d5fe357e06dac5e5cddb10808a10095d30e4069bc7818f' }
  },
  world_ledger_profile: { path: 'docs/project/fixtures/T06.003.003.006-profile.json', bytes: 4855,
    sha256: '9ad903297104cd6f9a03d74196d5db7a4091ee07da4d2b73b4b4f61027b2140d' },
  world_ledger: { roots: 1296, remaining_core_gap_roots: 82 },
  availability: { report_task: 'T07.007.006', root_audit_status: 'complete_observation_artifacts_consistent',
    request_records: 314, request_wire_bytes: 7575826, request_stored_bytes: 7575826, target_body_bytes: 7575328 },
  carried_bmp_targets: 38,
  ground_referrers: 40
});

const NEW_PROFILE_KEYS = ['schema', 'task', 'source_revision', 'client_source_root', 'constructor_profile', 'summary', 'rule_sources',
  'authored', 'inputs', 'expected_counts', 'policy', 'limitations', 'constructor_producer'];
const EXPECTED_COUNT_KEYS = ['roots', 'constructor_jobs', 'model_targets', 'returned_jobs', 'returned_empty_jobs', 'returned_nonempty_jobs',
  'constructor_exception_jobs', 'global_declarations', 'target_expanded_declarations', 'nested_targets', 'model_parent_links',
  'model_placement_occurrences', 'root_expanded_model_placements', 'resolved_node_slots', 'unresolved_node_slots', 'animation_jobs',
  'remaining_core_gap_roots', 'prior_first_level_gaps'];
const OUTCOMES = ['returned', 'constructor_exception', 'summary_error', 'summary_limit', 'input_refused',
  'environment_failure', 'timeout', 'resource_refusal', 'worker_error', 'unattempted'];
const REPORT_KEYS = ['schema', 'task', 'qualified', 'mode', 'expected_job_ids', 'expected_target_ids', 'job_accounting', 'input',
  'profile_sha256', 'summary_sha256', 'common_summary', 'client_source', 'own_sources', 'pinned_inputs', 'source_postchecks',
  'pinned_inputs_identity_unchanged_after_run', 'preserved_counts', 'header_prefix_counts', 'header_prefix_counts_are_observations',
  'effective_policy', 'counts', 'rss_sampling', 'cleanup', 'postchecks', 'elapsed_ms', 'jobs_file', 'storage', 'logs', 'roots',
  'targets', 'remaining_gap_root_ordinals', 'prior_first_level_gaps', 'limitations', 'input_manifest', 'root_model_references',
  'carried_ground_targets', 'world_gap_ledger_reference', 'availability_admission', 'functional'];
const MANIFEST_KEYS = ['schema', 'task', 'availability', 'counts', 'header_prefix_counts', 'roots', 'remaining_gap_root_ordinals',
  'prior_first_level_gaps', 'targets', 'jobs', 'root_model_references', 'carried_ground_targets', 'world_gap_ledger_reference', 'limitations'];
const TARGET_KEYS = ['model_ordinal', 'target_index', 'request_index', 'report_pointer', 'catalog_pointer', 'http_path', 'referrers',
  'availability_record', 'body', 'job_id'];
const AVAILABILITY_KEYS = ['report', 'catalog', 'root_audit', 'execution'];
const ROW_KEYS = ['id', 'job_id', 'kind', 'input_bytes', 'complete_sha256', 'header_version_bytes', 'outcome', 'constructor_returned',
  'elapsed_ms', 'worker_started', 'phase', 'cleanup', 'constructor_ms', 'summary_json_bytes', 'loaded_module_keys', 'seek_globals',
  'dynamic_import_refusals', 'summary'];
const HISTORICAL_CLEANUP_KEYS = ['exit_observed', 'exit_code', 'terminated_by_parent'];
const CLEANUP_KEYS = [...HISTORICAL_CLEANUP_KEYS, 'stdout_eof_observed', 'stderr_eof_observed'];
const IDENTITY_KEYS = ['dev', 'ino', 'size', 'mtime_ns', 'ctime_ns'];
const DESCRIPTOR_KEYS = ['path', 'bytes', 'sha256', 'identity'];

const decimalIdentity = (id, bytes) => isObj(id) && exactKeys(id, IDENTITY_KEYS) &&
  IDENTITY_KEYS.every((key) => typeof id[key] === 'string' && /^(?:0|[1-9][0-9]*)$/.test(id[key])) && id.size === String(bytes);
const boundedNumber = (v, max) => typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= max;

// The original verified cleanup: exactly five typed facts. No exit0→EOF inference.
export function verifiedCleanup(c) {
  return isObj(c) && exactKeys(c, CLEANUP_KEYS) && c.exit_observed === true && Object.is(c.exit_code, 0) &&
    c.terminated_by_parent === false && c.stdout_eof_observed === true && c.stderr_eof_observed === true;
}

function validateSupplementProfile(profile) {
  need(exactKeys(profile, NEW_PROFILE_KEYS) && typeof profile.source_revision === 'string' && /^[0-9a-f]{40}$/.test(profile.source_revision), 'profile_invalid');
  need(deepEqual(profile.constructor_profile, SUPPLEMENT.constructor_profile) && deepEqual(profile.constructor_producer, SUPPLEMENT.constructor_producer) &&
    deepEqual(profile.rule_sources, SUPPLEMENT.rule_sources), 'profile_invalid');
  need(exactKeys(profile.expected_counts, EXPECTED_COUNT_KEYS) && isObj(profile.expected_counts.animation_jobs) &&
    exactKeys(profile.expected_counts.animation_jobs, ['true', 'false', 'unknown']), 'profile_invalid');
  for (const key of ['report', 'jobs', 'manifest', 'catalog']) need(exactKeys(profile.inputs[key], ['path', 'bytes', 'sha256']), 'profile_invalid');
}

// Validates the complete unmodified qualified .008 production report, its
// JSONL rows, the constructor manifest and the .005 catalog BEFORE projection.
// facts carries the actual identities of files this process fully read.
// Returns the six-field core input with fresh historical three-key cleanup
// rows, the verified original cleanups and the corpus-only provenance.
export function admitSupplementCorpus({ profile, constructorProfile: cp, report, rows, manifest, catalog, facts }) {
  const ok = (condition, detail) => need(condition, 'admission_discrepancy', detail);
  const S = SUPPLEMENT;
  ok(isObj(profile) && profile.task === NEW_TASK && isObj(profile.expected_counts) && isObj(profile.inputs), 'profile');
  ok(isObj(facts) && typeof facts.inputRoot === 'string' && path.isAbsolute(facts.inputRoot) && isObj(facts.identity) &&
    isObj(facts.identity.rules), 'facts');
  const id = facts.identity;
  const abs = (rel) => path.join(facts.inputRoot, rel);
  const producer = profile.constructor_producer;
  const ec = profile.expected_counts;

  // Constructor profile ↔ texture profile.
  ok(isObj(cp) && cp.schema === 'T06-model-constructor-profile-1' && cp.task === S.constructor_producer.task, 'constructor profile');
  ok(isObj(cp.sources) && isObj(cp.rule_sources) && isObj(cp.counts) && isObj(cp.policy) && isObj(cp.availability) &&
    isObj(cp.header_prefix_counts) && Array.isArray(cp.limitations), 'constructor profile shape');
  ok(deepEqual(cp.summary, profile.summary) && deepEqual(cp.manifest, profile.inputs.manifest) && deepEqual(cp.worker, producer.worker) &&
    exactKeys(cp.availability, AVAILABILITY_KEYS) && deepEqual(cp.availability.catalog, profile.inputs.catalog), 'constructor profile pins');
  ok(cp.client_source_revision === profile.source_revision && cp.client_source_relative === profile.client_source_root, 'client source');
  ok(Object.keys(cp.rule_sources).length === 3, 'constructor rule sources');
  for (const [name, pin] of Object.entries(profile.rule_sources)) {
    const declared = name === 'src/Loaders/Model.js' ? cp.sources[name] : cp.rule_sources[name];
    ok(deepEqual(declared, pin) && isObj(id.rules[name]), `rule ${name}`);
  }
  const counts = cp.counts;
  ok(counts.roots === ec.roots && counts.constructor_jobs === ec.constructor_jobs && counts.model_targets === ec.model_targets &&
    counts.model_referrers === ec.model_parent_links && counts.remaining_core_gap_roots === ec.remaining_core_gap_roots &&
    ec.prior_first_level_gaps === 0, 'constructor counts');
  const nJobs = counts.constructor_jobs;
  const nTargets = counts.model_targets;

  // Catalog: dense jobs, root edges and every referrer joined exactly once.
  ok(isObj(catalog) && catalog.schema === 'T06-map-dependency-catalog-1' && catalog.task === 'T07.007.005' && catalog.mode === 'corpus', 'catalog schema');
  ok(Array.isArray(catalog.roots) && Array.isArray(catalog.jobs) && Array.isArray(catalog.targets) &&
    Array.isArray(catalog.remaining_gap_root_ordinals), 'catalog shape');
  ok(catalog.roots.length === counts.roots && catalog.remaining_gap_root_ordinals.length === counts.remaining_core_gap_roots, 'catalog roots');
  const jobById = new Map();
  let loaderEntries = 0;
  catalog.jobs.forEach((job, index) => {
    ok(isObj(job) && job.source_row_index === index && typeof job.id === 'string' && !jobById.has(job.id) &&
      Array.isArray(job.root_references) && job.root_references.length === 1, `catalog job ${index}`);
    jobById.set(job.id, index);
    const ref = job.root_references[0];
    ok(isObj(ref) && exactKeys(ref, ['root_ordinal', 'edge_kind']) && nonneg(ref.root_ordinal) && ref.root_ordinal < catalog.roots.length &&
      ref.edge_kind === job.kind, `catalog job ${index} root reference`);
    if (job.loader_entries === null) {
      ok(job.role === null && job.occurrence_loader_indexes === null, `catalog job ${index} role`);
      return;
    }
    ok(typeof job.role === 'string' && Array.isArray(job.loader_entries) && Array.isArray(job.occurrence_loader_indexes), `catalog job ${index} loader`);
    job.loader_entries.forEach((entry, loader) => ok(isObj(entry) && entry.index === loader && nonneg(entry.target_index) &&
      typeof entry.http_path === 'string', `catalog job ${index} loader ${loader}`));
    ok(job.occurrence_loader_indexes.every((v) => Number.isSafeInteger(v) && v >= 0 && v < job.loader_entries.length), `catalog job ${index} occurrences`);
    loaderEntries += job.loader_entries.length;
  });
  catalog.roots.forEach((root, ordinal) => {
    // Subset roots keep unknown world ordinals as null, never a guessed ordinal.
    ok(isObj(root) && root.ordinal === ordinal && root.ordinal_scope === 'four-target-subset-only' &&
      own(root, 'original_gap_root_ordinal') && root.original_gap_root_ordinal === null &&
      root.original_gap_root_ordinal_status === 'unknown_in_admitted_reference_metadata' &&
      isObj(root.edges) && exactKeys(root.edges, ['rsw', 'gnd', 'gat']), `catalog root ${ordinal}`);
    for (const kind of ['rsw', 'gnd', 'gat']) {
      const edge = root.edges[kind];
      const index = isObj(edge) ? jobById.get(edge.job_id) : undefined;
      ok(index !== undefined && catalog.jobs[index].kind === kind &&
        deepEqual(catalog.jobs[index].root_references, [{ root_ordinal: ordinal, edge_kind: kind }]), `catalog root ${ordinal} ${kind}`);
    }
  });
  const joined = new Set();
  const modelIndexes = [];
  const carriedIndexes = [];
  let referrers = 0;
  catalog.targets.forEach((target, index) => {
    ok(isObj(target) && exactKeys(target, ['index', 'http_path', 'referrers']) && target.index === index &&
      typeof target.http_path === 'string' && Array.isArray(target.referrers) && target.referrers.length > 0, `catalog target ${index}`);
    const roles = new Set();
    for (const r of target.referrers) {
      ok(isObj(r) && exactKeys(r, ['job_index', 'loader_index', 'role']) && nonneg(r.job_index) && nonneg(r.loader_index), `catalog target ${index} referrer`);
      const job = catalog.jobs[r.job_index];
      const entry = isObj(job) && Array.isArray(job.loader_entries) ? job.loader_entries[r.loader_index] : undefined;
      ok(entry !== undefined && job.role === r.role && entry.target_index === index && entry.http_path === target.http_path, `catalog target ${index} join`);
      const key = `${r.job_index}:${r.loader_index}`;
      ok(!joined.has(key), `catalog target ${index} duplicate referrer`);
      joined.add(key);
      roles.add(r.role);
      referrers++;
    }
    ok(roles.size === 1 && (roles.has('model') || roles.has('ground_texture')), `catalog target ${index} roles`);
    (roles.has('model') ? modelIndexes : carriedIndexes).push(index);
  });
  ok(referrers === counts.all_catalog_referrers && loaderEntries === referrers, 'catalog referrer total');
  ok(modelIndexes.length === nTargets && carriedIndexes.length === S.carried_bmp_targets, 'catalog target partition');

  // Manifest: availability/ledger descriptors and full re-derivation from the catalog.
  ok(isObj(manifest) && exactKeys(manifest, MANIFEST_KEYS) && manifest.schema === 'T06-model-constructor-input-1' &&
    manifest.task === S.constructor_producer.task, 'manifest schema');
  ok(deepEqual(manifest.counts, counts) && deepEqual(manifest.header_prefix_counts, cp.header_prefix_counts) &&
    deepEqual(manifest.limitations, cp.limitations), 'manifest counts');
  ok(deepEqual(manifest.roots, catalog.roots) && deepEqual(manifest.remaining_gap_root_ordinals, catalog.remaining_gap_root_ordinals) &&
    deepEqual(manifest.prior_first_level_gaps, []), 'manifest roots');
  const av = manifest.availability;
  ok(isObj(av) && exactKeys(av, AVAILABILITY_KEYS), 'manifest availability');
  for (const key of AVAILABILITY_KEYS) {
    const d = av[key];
    const pin = cp.availability[key];
    ok(isObj(d) && isObj(pin) && exactKeys(d, DESCRIPTOR_KEYS) && d.path === pin.path && d.bytes === pin.bytes && d.sha256 === pin.sha256 &&
      decimalIdentity(d.identity, d.bytes), `manifest availability ${key}`);
  }
  ok(deepEqual(av.catalog.identity, id.catalog), 'manifest catalog identity');
  const ledger = manifest.world_gap_ledger_reference;
  ok(isObj(ledger) && exactKeys(ledger, ['profile', 'roots', 'remaining_core_gap_roots', 'reconciled_by_this_subset']) &&
    isObj(ledger.profile) && exactKeys(ledger.profile, DESCRIPTOR_KEYS) && ledger.profile.path === S.world_ledger_profile.path &&
    ledger.profile.bytes === S.world_ledger_profile.bytes && ledger.profile.sha256 === S.world_ledger_profile.sha256 &&
    decimalIdentity(ledger.profile.identity, ledger.profile.bytes) && ledger.roots === S.world_ledger.roots &&
    ledger.remaining_core_gap_roots === S.world_ledger.remaining_core_gap_roots && ledger.reconciled_by_this_subset === false, 'world ledger');
  ok(Array.isArray(manifest.targets) && manifest.targets.length === nTargets && Array.isArray(manifest.jobs) && manifest.jobs.length === nJobs &&
    Array.isArray(manifest.carried_ground_targets) && Array.isArray(manifest.root_model_references), 'manifest arrays');
  const bodyDirectory = cp.availability.report.path.split('/').slice(0, -1).join('/');
  const histogram = {};
  const groups = new Map();
  const derivedJobs = [];
  let targetBytes = 0;
  modelIndexes.forEach((targetIndex, ordinal) => {
    const t = manifest.targets[ordinal];
    const ct = catalog.targets[targetIndex];
    ok(isObj(t) && exactKeys(t, TARGET_KEYS) && t.model_ordinal === ordinal && t.target_index === targetIndex &&
      t.report_pointer === `/targets/${targetIndex}` && t.catalog_pointer === `/targets/${targetIndex}` &&
      t.http_path === ct.http_path && deepEqual(t.referrers, ct.referrers), `manifest target ${ordinal}`);
    const rec = t.availability_record;
    ok(isObj(rec) && rec.target_index === targetIndex && rec.request_index === t.request_index && nonneg(t.request_index) &&
      rec.wire_target === `/${ct.http_path}` && isObj(rec.signature) && rec.signature.kind === 'model' &&
      typeof rec.signature.prefix_hex === 'string' && /^(?:[0-9a-f]{2}){1,6}$/.test(rec.signature.prefix_hex) &&
      isObj(rec.stored) && rec.stored.complete === true && typeof rec.stored.file === 'string', `manifest target ${ordinal} availability`);
    const b = t.body;
    ok(isObj(b) && exactKeys(b, DESCRIPTOR_KEYS) && b.path === `${bodyDirectory}/${rec.stored.file}` && nonneg(b.bytes) &&
      b.bytes === rec.stored.bytes && isHex(b.sha256, 64) && b.sha256 === rec.stored.sha256 && decimalIdentity(b.identity, b.bytes),
    `manifest target ${ordinal} body`);
    const header = rec.signature.prefix_hex;
    histogram[header] = (histogram[header] || 0) + 1;
    targetBytes += b.bytes;
    let job = groups.get(b.sha256);
    if (!job) {
      const jobId = `model-${String(derivedJobs.length).padStart(6, '0')}`;
      job = { id: jobId, job_id: jobId, kind: 'model', representative_model_ordinal: ordinal, body_path: b.path, input_bytes: b.bytes,
        complete_sha256: b.sha256, header_version_bytes: header, target_model_ordinals: [] };
      groups.set(b.sha256, job);
      derivedJobs.push(job);
    } else ok(job.input_bytes === b.bytes && job.header_version_bytes === header, `manifest target ${ordinal} shared body`);
    job.target_model_ordinals.push(ordinal);
    ok(t.job_id === job.job_id, `manifest target ${ordinal} job`);
  });
  ok(deepEqual(manifest.jobs, derivedJobs), 'manifest jobs');
  ok(deepEqual(histogram, cp.header_prefix_counts) && targetBytes === counts.target_body_bytes &&
    derivedJobs.reduce((sum, job) => sum + job.input_bytes, 0) === counts.distinct_job_bytes, 'manifest body totals');
  ok(nTargets < 2 || manifest.targets.some((t) => t.model_ordinal !== t.target_index), 'dense ordinals');
  // Carried BMP ground targets: full catalog/report pairs, not jobs or declarations.
  ok(manifest.carried_ground_targets.length === carriedIndexes.length, 'carried count');
  let groundReferrers = 0;
  let carriedBytes = 0;
  carriedIndexes.forEach((targetIndex, k) => {
    const c = manifest.carried_ground_targets[k];
    const ct = catalog.targets[targetIndex];
    ok(isObj(c) && exactKeys(c, ['target_index', 'catalog_target', 'availability_record']) && c.target_index === targetIndex &&
      deepEqual(c.catalog_target, ct), `carried ${k}`);
    const rec = c.availability_record;
    ok(isObj(rec) && rec.target_index === targetIndex && rec.wire_target === `/${ct.http_path}` && isObj(rec.signature) &&
      rec.signature.kind !== 'model' && isObj(rec.stored) && rec.stored.complete === true && nonneg(rec.stored.bytes), `carried ${k} availability`);
    groundReferrers += ct.referrers.length;
    carriedBytes += rec.stored.bytes;
  });
  ok(groundReferrers === S.ground_referrers && targetBytes + carriedBytes === S.availability.target_body_bytes, 'carried totals');
  // Root model references: sparse catalog job/source-row/loader/root/edge/pointer/occurrence joins.
  const references = [];
  for (const t of manifest.targets) {
    for (const r of t.referrers) {
      const job = catalog.jobs[r.job_index];
      const occurrence_indexes = [];
      job.occurrence_loader_indexes.forEach((loader, index) => { if (loader === r.loader_index) occurrence_indexes.push(index); });
      references.push({ model_ordinal: t.model_ordinal, target_index: t.target_index, catalog_job_index: r.job_index,
        catalog_job_id: job.id, catalog_source_row_index: job.source_row_index, loader_index: r.loader_index, role: r.role,
        root_ordinal: job.root_references[0].root_ordinal, edge_kind: job.root_references[0].edge_kind,
        occurrence_summary_pointer: job.occurrence_summary_pointer, occurrence_indexes });
    }
  }
  ok(references.length === counts.model_referrers && deepEqual(manifest.root_model_references, references), 'root model references');
  const placements = references.reduce((sum, r) => sum + r.occurrence_indexes.length, 0);
  ok(placements === ec.model_placement_occurrences, 'placement occurrences');

  // Report: complete qualified production document, not trusted on qualified alone.
  ok(isObj(report) && exactKeys(report, REPORT_KEYS) && report.schema === 'T06-model-constructor-report-1' &&
    report.task === S.constructor_producer.task && report.mode === 'corpus' && report.qualified === true, 'report schema');
  ok(report.profile_sha256 === profile.constructor_profile.sha256 && report.summary_sha256 === profile.summary.sha256, 'report pins');
  const descriptor = (pin, identity) => ({ bytes: pin.bytes, sha256: pin.sha256, identity });
  ok(deepEqual(report.input, { path: abs(profile.inputs.manifest.path), ...descriptor(profile.inputs.manifest, id.manifest) }), 'report input');
  ok(deepEqual(report.common_summary, { path: profile.summary.path, ...descriptor(profile.summary, id.summary) }), 'report summary');
  ok(deepEqual(report.own_sources, [
    { path: producer.program.path, ...descriptor(producer.program, id.program) },
    { path: producer.worker.path, ...descriptor(producer.worker, id.worker) }
  ]), 'report producer');
  const cs = report.client_source;
  ok(isObj(cs) && exactKeys(cs, ['root', 'profile_revision', 'revision_checked', 'sources', 'rule_sources']) &&
    cs.root === abs(cp.client_source_relative) && cs.profile_revision === cp.client_source_revision && cs.revision_checked === false, 'report client source');
  for (const [key, declared] of [['sources', cp.sources], ['rule_sources', cp.rule_sources]]) {
    const names = Object.keys(declared);
    ok(Array.isArray(cs[key]) && cs[key].length === names.length, `report ${key}`);
    names.forEach((name, i) => {
      const s = cs[key][i];
      ok(isObj(s) && exactKeys(s, ['path', 'bytes', 'sha256', 'verified', 'identity']) && s.path === name && isObj(declared[name]) &&
        s.bytes === declared[name].bytes && s.sha256 === declared[name].sha256 && s.verified === true && decimalIdentity(s.identity, s.bytes), `report ${key} ${name}`);
      if (own(id.rules, name)) ok(deepEqual(s.identity, id.rules[name]), `report ${key} ${name} identity`);
      else ok(key === 'sources', `report ${key} ${name} opened`);
    });
  }
  const role = (name, rel, pin, identity) => ({ role: name, path: abs(rel), ...descriptor(pin, identity) });
  const expectedPins = [
    role('profile', profile.constructor_profile.path, profile.constructor_profile, id.constructor_profile),
    role('worker', producer.worker.path, producer.worker, id.worker),
    role('summary', profile.summary.path, profile.summary, id.summary),
    role('availability_report', av.report.path, av.report, av.report.identity),
    role('catalog', profile.inputs.catalog.path, profile.inputs.catalog, id.catalog),
    role('root_audit', av.root_audit.path, av.root_audit, av.root_audit.identity),
    role('execution_receipt', av.execution.path, av.execution, av.execution.identity),
    role('world_ledger_profile', ledger.profile.path, ledger.profile, ledger.profile.identity),
    role('corpus', profile.inputs.manifest.path, profile.inputs.manifest, id.manifest)
  ];
  ok(new Set(expectedPins.map((p) => p.role)).size === 9 && deepEqual(report.pinned_inputs, expectedPins), 'report pinned inputs');
  ok(deepEqual(report.source_postchecks, { method: 'full_read_hash_and_identity', expected: 21, checked: 21, failed: [], ok: true }) &&
    report.pinned_inputs_identity_unchanged_after_run === true, 'report source postchecks');
  ok(deepEqual(report.postchecks, { checked: nTargets, ok: true }), 'report body postchecks');
  ok(deepEqual(report.preserved_counts, counts) && deepEqual(report.header_prefix_counts, cp.header_prefix_counts) &&
    report.header_prefix_counts_are_observations === true, 'report preserved counts');
  ok(deepEqual(report.effective_policy, { ...cp.policy, max_jobs: nJobs }), 'report policy');
  const rss = report.rss_sampling;
  ok(isObj(rss) && exactKeys(rss, ['sample_ms', 'samples', 'peak_rss_bytes', 'limit_bytes', 'over_limit_samples', 'scope']) &&
    rss.sample_ms === cp.policy.rss_sample_ms && rss.limit_bytes === cp.policy.rss_limit_bytes && nonneg(rss.samples) &&
    nonneg(rss.peak_rss_bytes) && rss.peak_rss_bytes <= rss.limit_bytes && rss.over_limit_samples === 0 && typeof rss.scope === 'string', 'report rss');
  ok(deepEqual(report.cleanup, { workers_started: nJobs, exits_observed: nJobs, unverified: [], halted: null, verified: true }), 'report cleanup');
  ok(nonneg(report.elapsed_ms) && report.elapsed_ms <= cp.policy.run_timeout_ms, 'report elapsed');
  ok(deepEqual(report.jobs_file, { path: 'jobs.jsonl', bytes: profile.inputs.jobs.bytes, sha256: profile.inputs.jobs.sha256, records: nJobs, complete: true }), 'report jobs file');
  ok(deepEqual(report.storage, { publication_failed: false, jobs_tail_uncertain: false, jobs_close_verified: true }), 'report storage');
  ok(isObj(report.logs) && exactKeys(report.logs, ['bytes', 'limit_bytes']) && report.logs.limit_bytes === cp.policy.max_total_log_bytes &&
    nonneg(report.logs.bytes) && report.logs.bytes <= report.logs.limit_bytes, 'report logs');
  ok(deepEqual(report.expected_job_ids, manifest.jobs.map((j) => j.job_id)) &&
    deepEqual(report.expected_target_ids, manifest.targets.map((t) => t.model_ordinal)), 'report expected ids');
  ok(deepEqual(report.roots, manifest.roots) && deepEqual(report.remaining_gap_root_ordinals, manifest.remaining_gap_root_ordinals) &&
    deepEqual(report.prior_first_level_gaps, manifest.prior_first_level_gaps) && deepEqual(report.limitations, cp.limitations), 'report roots');
  ok(deepEqual(report.input_manifest, { schema: manifest.schema, counts: manifest.counts, limitations: manifest.limitations, task: manifest.task }), 'report input manifest');
  ok(deepEqual(report.root_model_references, manifest.root_model_references) && deepEqual(report.carried_ground_targets, manifest.carried_ground_targets) &&
    deepEqual(report.world_gap_ledger_reference, manifest.world_gap_ledger_reference), 'report supplement provenance');
  ok(deepEqual(report.availability_admission, {
    report_task: S.availability.report_task, catalog_task: catalog.task, root_audit_status: S.availability.root_audit_status,
    request_records: S.availability.request_records, request_wire_bytes: S.availability.request_wire_bytes,
    request_stored_bytes: S.availability.request_stored_bytes, target_body_bytes: targetBytes + carriedBytes,
    model_targets: nTargets, carried_bmp_targets: carriedIndexes.length, ground_referrers: groundReferrers,
    model_referrers: references.length, placement_occurrences: placements, execution_receipt_executed: false, native_inputs_reopened: false
  }), 'report availability admission');
  ok(deepEqual(report.functional, { required_returned_constructors: nJobs, returned_constructors: nJobs,
    all_model_constructors_returned: true, open_failures: [] }), 'report functional');

  // Physical rows ↔ manifest jobs ↔ report accounting. Every original row must
  // carry its complete five-key cleanup BEFORE any historical projection.
  ok(Array.isArray(rows) && rows.length === nJobs && Array.isArray(report.job_accounting) && report.job_accounting.length === nJobs, 'row count');
  const moduleKeys = Object.keys(cp.sources);
  const outcomeById = new Map();
  rows.forEach((row, i) => {
    const job = manifest.jobs[i];
    ok(isObj(row) && (exactKeys(row, ROW_KEYS) || exactKeys(row, [...ROW_KEYS, 'log'])), `row ${i} keys`);
    ok(verifiedCleanup(row.cleanup), `row ${i} cleanup`);
    ok(row.id === job.job_id && row.job_id === job.job_id && !outcomeById.has(row.job_id) && row.kind === 'model' &&
      row.input_bytes === job.input_bytes && row.complete_sha256 === job.complete_sha256 && row.header_version_bytes === job.header_version_bytes, `row ${i} job`);
    ok(row.outcome === 'returned' && row.constructor_returned === true && row.worker_started === true && row.phase === 'summary' &&
      isObj(row.summary), `row ${i} outcome`);
    ok(boundedNumber(row.elapsed_ms, cp.policy.job_timeout_ms) && boundedNumber(row.constructor_ms, cp.policy.constructor_timeout_ms), `row ${i} timing`);
    ok(nonneg(row.summary_json_bytes) && row.summary_json_bytes <= cp.policy.max_job_json_bytes &&
      row.summary_json_bytes === Buffer.byteLength(JSON.stringify(row.summary)), `row ${i} summary bytes`);
    const keys = row.loaded_module_keys;
    ok(Array.isArray(keys) && keys.length === moduleKeys.length && new Set(keys).size === keys.length && moduleKeys.every((k) => keys.includes(k)) &&
      deepEqual(row.seek_globals, [1, 2, 3]) && deepEqual(row.dynamic_import_refusals, []), `row ${i} realm`);
    ok(deepEqual(report.job_accounting[i], { ...omit(row, ['summary', 'log']), summary_payload_in_jsonl_only: true }), `row ${i} accounting`);
    outcomeById.set(row.job_id, row.outcome);
  });
  const jobOutcomes = Object.fromEntries(OUTCOMES.map((o) => [o, 0]));
  for (const row of rows) jobOutcomes[row.outcome]++;
  const targetOutcomes = Object.fromEntries(OUTCOMES.map((o) => [o, 0]));
  ok(Array.isArray(report.targets) && report.targets.length === nTargets, 'report targets');
  manifest.targets.forEach((t, i) => {
    const outcome = outcomeById.get(t.job_id);
    ok(outcome !== undefined && deepEqual(report.targets[i], { ...t, constructor_outcome: outcome }), `report target ${i}`);
    targetOutcomes[outcome]++;
  });
  ok(deepEqual(report.counts, { expected_jobs: nJobs, expected_targets: nTargets, records: nJobs, attempted: nJobs,
    job_outcomes: jobOutcomes, target_outcomes: targetOutcomes }), 'report counts');

  const first_level_model_jobs = [];
  catalog.jobs.forEach((job, index) => {
    if (job.kind === 'rsw' && job.role === 'model') first_level_model_jobs.push({ ...job, source_job_index: index });
  });
  return {
    input: {
      roots: manifest.roots,
      remaining_gap_root_ordinals: manifest.remaining_gap_root_ordinals,
      prior_first_level_gaps: manifest.prior_first_level_gaps,
      first_level_model_jobs,
      model_targets: manifest.targets,
      // Fresh core-only copies with exactly the three historical facts.
      model_rows: rows.map((row) => ({ ...row, cleanup: Object.fromEntries(HISTORICAL_CLEANUP_KEYS.map((k) => [k, row.cleanup[k]])) }))
    },
    cleanups: rows.map((row, source_row_index) => ({ source_row_index, job_id: row.job_id, cleanup: clone(row.cleanup) })),
    provenance: {
      root_model_references: manifest.root_model_references,
      carried_ground_targets: manifest.carried_ground_targets,
      world_gap_ledger_reference: manifest.world_gap_ledger_reference
    }
  };
}

// Returns a copy of the core output whose jobs carry the verified original
// five-key cleanup, joined by exact source_row_index AND job_id.
export function restoreCleanups(core, cleanups) {
  need(isObj(core) && Array.isArray(core.jobs) && Array.isArray(cleanups) && core.jobs.length === cleanups.length, 'restore_mismatch');
  const jobs = core.jobs.map((job) => {
    const entry = nonneg(job.source_row_index) ? cleanups[job.source_row_index] : undefined;
    need(isObj(entry) && entry.source_row_index === job.source_row_index && entry.job_id === job.job_id && job.id === job.job_id &&
      verifiedCleanup(entry.cleanup), 'restore_mismatch');
    need(deepEqual(job.cleanup, Object.fromEntries(HISTORICAL_CLEANUP_KEYS.map((k) => [k, entry.cleanup[k]]))), 'restore_mismatch');
    return { ...job, cleanup: clone(entry.cleanup) };
  });
  return { ...core, jobs };
}

// ---------------------------------------------------------------- CLI

const FLAGS = ['--input-root', '--profile', '--fixtures', '--report', '--jobs', '--manifest', '--catalog', '--output',
  '--max-output-bytes', '--run-timeout-ms'];
const CORPUS_FLAGS = ['report', 'jobs', 'manifest', 'catalog'];

export function parseArgs(argv) {
  need(Array.isArray(argv), 'usage');
  const opts = {};
  for (let i = 0; i < argv.length; i += 2) {
    const flag = argv[i];
    need(FLAGS.includes(flag), 'usage');
    const key = flag.slice(2).replace(/-/g, '_');
    need(!own(opts, key), 'usage');
    const value = argv[i + 1];
    need(typeof value === 'string' && value.length > 0 && !value.startsWith('--'), 'usage');
    opts[key] = value;
  }
  for (const key of ['input_root', 'profile', 'output']) need(own(opts, key), 'usage');
  const corpus = CORPUS_FLAGS.filter((key) => own(opts, key)).length;
  if (own(opts, 'fixtures')) { need(corpus === 0, 'usage'); opts.mode = 'fixtures'; }
  else { need(corpus === CORPUS_FLAGS.length, 'usage'); opts.mode = 'corpus'; }
  const limit = (key, min, max) => {
    if (!own(opts, key)) return undefined;
    need(/^[0-9]{1,10}$/.test(opts[key]), 'usage');
    const n = Number(opts[key]);
    need(n >= min && n <= max, 'policy_increase');
    return n;
  };
  opts.maxOutputBytes = limit('max_output_bytes', 0, DEFAULT_POLICY.max_catalog_bytes);
  opts.runTimeoutMs = limit('run_timeout_ms', 1, DEFAULT_POLICY.run_timeout_ms);
  return opts;
}

function say(stdout, obj) {
  let line = JSON.stringify(obj);
  if (Buffer.byteLength(line) > DEFAULT_POLICY.max_stdout_bytes) {
    line = JSON.stringify({ status: 'error', reason: 'stdout_limit', exit_code: obj.exit_code, output_created: obj.output_created });
  }
  stdout.write(line + '\n');
}

const reasonOf = (error) => (error instanceof Refusal && /^[a-z][a-z0-9_]*$/.test(error.reason) ? error.reason : 'internal_error');

// Exclusive fresh 0700 directory directly below this checkout's .tools/renewal.
function prepareOutput(output) {
  need(typeof output === 'string' && path.isAbsolute(output) && path.resolve(output) === output, 'output_refused');
  need(path.dirname(output) === OUTPUT_PARENT, 'output_refused');
  try { assertLinkFree(OUTPUT_PARENT); } catch { throw refuse('output_refused'); }
  need(fs.lstatSync(OUTPUT_PARENT).isDirectory(), 'output_refused');
  try { fs.lstatSync(output); } catch (error) {
    if (error.code === 'ENOENT') return;
    throw refuse('output_refused');
  }
  throw refuse('output_exists');
}

function writeAll(fd, buffer) {
  const write = hooks.writeSync || fs.writeSync;
  let off = 0;
  while (off < buffer.length) {
    const n = write(fd, buffer, off, buffer.length - off, off);
    if (!Number.isInteger(n) || n < 1 || n > buffer.length - off) throw refuse('output_io_error');
    off += n;
  }
}

// Single attempt per step; a failed close is not retried.
function publish(output, buffer) {
  const file = path.join(output, 'catalog.json');
  const fd = fs.openSync(file, WRITE_FLAGS, 0o600);
  let closed = false;
  try {
    fs.fchmodSync(fd, 0o600);
    writeAll(fd, buffer);
    fs.fsyncSync(fd);
    closed = true;
    (hooks.closeSync || fs.closeSync)(fd);
  } finally {
    if (!closed) { try { fs.closeSync(fd); } catch { /* original failure reported */ } }
  }
  const dfd = fs.openSync(output, fs.constants.O_RDONLY);
  try { fs.fsyncSync(dfd); } finally { fs.closeSync(dfd); }
  return file;
}

export function main(argv, { stdout = process.stdout } = {}) {
  const started = performance.now();
  let created = false;
  let deadline = started + DEFAULT_POLICY.run_timeout_ms;
  const pins = [];
  const read = (role, abs, opts) => { const f = readPinnedFile(abs, opts); f.role = role; pins.push(f); return f; };
  const inTime = () => performance.now() < deadline;
  try {
    const opts = parseArgs(argv);
    if (opts.runTimeoutMs !== undefined) deadline = started + opts.runTimeoutMs;
    const root = opts.input_root;
    need(path.isAbsolute(root) && path.resolve(root) === root, 'path_refused');
    assertLinkFree(root);
    need(fs.lstatSync(root).isDirectory(), 'path_refused');
    need(own(ROUTES, opts.profile), 'path_refused');
    const route = ROUTES[opts.profile];
    const profileFile = read('profile', safeJoin(root, route.path), { maxBytes: route.bytes, expectBytes: route.bytes, expectSha: route.sha256 });
    const profile = parseJson(profileFile.buffer);
    validateProfile(profile, route);
    const policy = profile.policy;
    const pinOf = (spec) => ({ maxBytes: spec.bytes, expectBytes: spec.bytes, expectSha: spec.sha256 });
    const cpFile = read('constructor_profile', safeJoin(root, profile.constructor_profile.path), pinOf(profile.constructor_profile));
    const summaryFile = read('summary', safeJoin(root, profile.summary.path), pinOf(profile.summary));
    const ruleIdentity = {};
    for (const [key, spec] of Object.entries(profile.rule_sources)) {
      ruleIdentity[key] = read(`rule:${key}`, safeJoin(root, `${profile.client_source_root}/${key}`), pinOf(spec)).identity;
    }
    const selfPath = hooks.ownSourcePath || SELF;
    read('implementation', selfPath, { maxBytes: 1048576 });
    let core;
    let inputPins;
    let supplement = {};
    if (opts.mode === 'fixtures') {
      need(opts.fixtures === profile.authored.path, 'path_refused');
      const spec = profile.authored;
      const authored = parseJson(read('authored', safeJoin(root, spec.path), { maxBytes: policy.max_fixture_bytes, expectBytes: spec.bytes, expectSha: spec.sha256 }).buffer);
      need(isObj(authored) && authored.schema === 'T06-model-texture-catalog-authored-1' && authored.task === TASK, 'fixture_invalid');
      core = buildCatalog(authored.input, policy);
      need(deepEqual(core, authored.expected), 'fixture_mismatch');
      inputPins = { authored: clone(spec) };
    } else {
      const caps = { report: policy.max_report_bytes, jobs: policy.max_jobs_jsonl_bytes, manifest: policy.max_manifest_bytes,
        catalog: policy.max_source_catalog_bytes };
      const files = {};
      for (const key of CORPUS_FLAGS) {
        const spec = profile.inputs[key];
        need(opts[key] === spec.path, 'path_refused');
        files[key] = read(key, safeJoin(root, spec.path), { maxBytes: caps[key], expectBytes: spec.bytes, expectSha: spec.sha256 });
      }
      if (route.name === 'supplement') {
        const producer = profile.constructor_producer;
        const program = read('producer_program', safeJoin(root, producer.program.path), pinOf(producer.program));
        const worker = read('producer_worker', safeJoin(root, producer.worker.path), pinOf(producer.worker));
        // Semantic test faults apply only after a genuine complete pinned read.
        const admit = (role, value) => (hooks.afterPinnedJson ? hooks.afterPinnedJson(role, value) : value);
        const docs = {
          profile,
          constructorProfile: admit('constructor_profile', parseJson(cpFile.buffer)),
          report: admit('report', parseJson(files.report.buffer)),
          rows: admit('jobs', parseJsonl(files.jobs.buffer, policy.max_row_json_bytes)),
          manifest: admit('manifest', parseJson(files.manifest.buffer)),
          catalog: admit('catalog', parseJson(files.catalog.buffer)),
          facts: { inputRoot: root, identity: { constructor_profile: cpFile.identity, summary: summaryFile.identity, program: program.identity,
            worker: worker.identity, manifest: files.manifest.identity, catalog: files.catalog.identity, rules: ruleIdentity } }
        };
        for (const key of CORPUS_FLAGS) files[key].buffer = null;
        for (const key of ['constructorProfile', 'report', 'rows', 'manifest', 'catalog']) assertJsonData(docs[key], policy);
        const admitted = admitSupplementCorpus(docs);
        core = restoreCleanups(buildCatalog(admitted.input, policy), admitted.cleanups);
        need(deepEqual(core.counts, profile.expected_counts), 'count_mismatch');
        inputPins = clone(profile.inputs);
        supplement = {
          root_model_references: clone(admitted.provenance.root_model_references),
          carried_ground_targets: clone(admitted.provenance.carried_ground_targets),
          world_gap_ledger_reference: clone(admitted.provenance.world_gap_ledger_reference),
          constructor_producer: clone(producer)
        };
      } else {
        const docs = {
          profile,
          constructorProfile: parseJson(cpFile.buffer),
          report: parseJson(files.report.buffer),
          rows: parseJsonl(files.jobs.buffer, policy.max_row_json_bytes),
          manifest: parseJson(files.manifest.buffer),
          catalog: parseJson(files.catalog.buffer)
        };
        for (const key of CORPUS_FLAGS) files[key].buffer = null;
        for (const key of ['report', 'manifest', 'catalog']) assertJsonData(docs[key], policy);
        core = buildCatalog(admitCorpus(docs), policy);
        need(deepEqual(core.counts, profile.expected_counts), 'count_mismatch');
        inputPins = clone(profile.inputs);
      }
    }
    for (const pin of pins) pin.buffer = null;
    const envelope = {
      schema: SCHEMA, task: route.task, mode: opts.mode, profile_sha256: route.sha256,
      constructor_profile_sha256: profile.constructor_profile.sha256, summary_sha256: profile.summary.sha256,
      input_pins: inputPins, rule_sources: clone(profile.rule_sources), ...core, ...supplement
    };
    const buffer = Buffer.from(JSON.stringify(envelope) + '\n', 'utf8');
    core = null;
    need(buffer.length <= Math.min(policy.max_catalog_bytes, opts.maxOutputBytes ?? Infinity), 'output_limit');
    if (hooks.afterBuild) hooks.afterBuild(pins.map((pin) => pin.role));
    need(recheckPins(pins), 'source_drift');
    need(inTime(), 'run_deadline');
    prepareOutput(opts.output);
    try { fs.mkdirSync(opts.output, { mode: 0o700 }); } catch { throw refuse('output_exists'); }
    created = true;
    fs.chmodSync(opts.output, 0o700);
    const file = publish(opts.output, buffer);
    if (hooks.afterPublish) hooks.afterPublish();
    const written = readPinnedFile(file, { maxBytes: buffer.length, expectBytes: buffer.length, expectSha: sha256(buffer) });
    need((fs.lstatSync(file).mode & 0o777) === 0o600 && (fs.lstatSync(opts.output).mode & 0o777) === 0o700, 'output_mode');
    need(fs.readdirSync(opts.output).length === 1, 'output_unexpected');
    need(recheckPins(pins), 'source_drift');
    need(inTime(), 'run_deadline');
    say(stdout, { status: 'complete', exit_code: 0, mode: opts.mode, output_created: true,
      catalog: { bytes: written.bytes, sha256: written.sha256 }, counts: envelope.counts });
    return 0;
  } catch (error) {
    const code = created ? 1 : 2;
    say(stdout, { status: created ? 'failed' : 'refused', exit_code: code, reason: reasonOf(error), output_created: created });
    return code;
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === SELF) {
  process.exitCode = main(process.argv.slice(2));
}
