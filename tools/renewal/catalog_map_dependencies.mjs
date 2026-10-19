#!/usr/bin/env node
// T06.003.003.004 first-level map dependency request catalog.
// Projects declared RSW model filenames and GND ground-texture table entries
// into FileManager relative HTTP strings. A target is a constructed string,
// not a GET, archive winner, browser URL or playable map.
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const PROFILE_SHA256 = '304e9da6ad4369ba96f30f71229de56581aedf6ee0789cc3d6261beb7e219df4';
export const PROFILE_BYTES = 3379;
const CLIENT_SOURCE_RELATIVE = '.tools/renewal/client-source';
const RULE_KEYS = ['src/Loaders/MapLoader.js', 'src/Core/FileManager.js', 'src/Loaders/Ground.js'];
const KINDS = ['rsw', 'gnd', 'gat'];
const MODEL_PREFIX = 'data\\model\\';
const TEXTURE_PREFIX = 'data\\texture\\';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, '..', '..');
const MAX_STDOUT_BYTES = 4096;

const READ_FLAGS = fs.constants.O_RDONLY | fs.constants.O_NONBLOCK | (fs.constants.O_NOFOLLOW || 0);
const WRITE_FLAGS = fs.constants.O_WRONLY | fs.constants.O_CREAT | fs.constants.O_EXCL | (fs.constants.O_NOFOLLOW || 0);

function fail(reason) {
  const error = new Error(reason);
  error.reason = reason;
  return error;
}

const sha256 = (buf) => crypto.createHash('sha256').update(buf).digest('hex');
const isHex64 = (s) => typeof s === 'string' && /^[0-9a-f]{64}$/.test(s);
const own = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);

export function safeJoin(root, rel, label) {
  if (typeof rel !== 'string' || rel.length === 0 || rel.length > 4096 || rel.includes('\0') || rel.includes('\\') ||
      path.isAbsolute(rel) || rel.split('/').some((part) => part === '..' || part === '.' || part === '')) {
    throw fail(`path_refused:${label}`);
  }
  const abs = path.resolve(root, rel);
  if (abs !== root && !abs.startsWith(root + path.sep)) throw fail(`path_refused:${label}`);
  return abs;
}

function reasonOf(error) {
  const reason = error && typeof error.reason === 'string' ? error.reason.split(':')[0] : '';
  return /^[a-z][a-z0-9_]*$/.test(reason) ? reason : 'error';
}

function say(stdout, obj) {
  let line = JSON.stringify(obj);
  if (Buffer.byteLength(line) > MAX_STDOUT_BYTES) {
    line = JSON.stringify({ status: obj.status === 'complete' ? 'error' : (obj.status || 'error'), reason: 'summary_limit', output_created: !!obj.output_created });
  }
  stdout.write(line + '\n');
}

export function identityOf(st) {
  return { dev: String(st.dev), ino: String(st.ino), size: String(st.size), mtime_ns: String(st.mtimeNs), ctime_ns: String(st.ctimeNs) };
}

function sameIdentity(a, b) {
  return a.dev === b.dev && a.ino === b.ino && a.size === b.size && a.mtime_ns === b.mtime_ns && a.ctime_ns === b.ctime_ns;
}

// Every existing path component must be a real directory or, at the leaf, the file about to be opened.
function assertLinkFree(abs) {
  const parts = abs.split(path.sep).filter((part) => part.length > 0);
  let cur = path.sep;
  for (let i = 0; i < parts.length; i++) {
    cur = i === 0 ? path.join(path.sep, parts[0]) : path.join(cur, parts[i]);
    let st;
    try { st = fs.lstatSync(cur); }
    catch (error) { throw fail(error.code === 'ENOENT' ? 'missing_input' : 'input_io_error'); }
    if (st.isSymbolicLink()) throw fail('symlink_refused');
  }
}

export function readPinnedFile(abs, { maxBytes, expectBytes, expectSha }) {
  if (!fs.constants.O_NOFOLLOW) throw fail('environment');
  assertLinkFree(abs);
  const before = fs.lstatSync(abs, { bigint: true });
  if (before.isSymbolicLink()) throw fail('symlink_refused');
  if (!before.isFile()) throw fail('special_file_refused');
  if (before.size > BigInt(maxBytes)) throw fail('size_limit');
  if (expectBytes !== undefined && before.size !== BigInt(expectBytes)) throw fail('pin_mismatch');
  const fd = fs.openSync(abs, READ_FLAGS);
  let opened, after, buf;
  try {
    opened = fs.fstatSync(fd, { bigint: true });
    if (!opened.isFile() || !sameIdentity(identityOf(opened), identityOf(before))) throw fail('identity_changed');
    if (opened.size > BigInt(maxBytes)) throw fail('size_limit');
    if (expectBytes !== undefined && opened.size !== BigInt(expectBytes)) throw fail('pin_mismatch');
    const size = Number(opened.size);
    buf = Buffer.alloc(size);
    let off = 0;
    while (off < size) {
      const n = fs.readSync(fd, buf, off, size - off, off);
      if (n < 1) throw fail('identity_changed');
      off += n;
    }
    if (fs.readSync(fd, Buffer.alloc(1), 0, 1, size) !== 0) throw fail('identity_changed');
    after = fs.fstatSync(fd, { bigint: true });
  } finally { fs.closeSync(fd); }
  const relinked = fs.lstatSync(abs, { bigint: true });
  const id0 = identityOf(before);
  if (!sameIdentity(id0, identityOf(opened)) || !sameIdentity(id0, identityOf(after)) || !sameIdentity(id0, identityOf(relinked))) {
    throw fail('identity_changed');
  }
  const digest = sha256(buf);
  if (expectSha !== undefined && digest !== expectSha) throw fail('pin_mismatch');
  return { buffer: buf, bytes: buf.length, sha256: digest, identity: id0, abs };
}

function recheckIdentity(pin) {
  let st;
  try { st = fs.lstatSync(pin.abs, { bigint: true }); }
  catch { return false; }
  if (st.isSymbolicLink() || !st.isFile()) return false;
  return sameIdentity(pin.identity, identityOf(st));
}

// Checked full-progress write. A zero-length result throws before another attempt.
export function writeAll(fd, buffer, position = 0) {
  let off = 0;
  while (off < buffer.length) {
    const n = fs.writeSync(fd, buffer, off, buffer.length - off, position + off);
    if (!Number.isInteger(n) || n < 1 || n > buffer.length - off) throw fail('output_io_error');
    off += n;
  }
}

function writeExclusive(file, buffer) {
  const fd = fs.openSync(file, WRITE_FLAGS, 0o600);
  try {
    fs.fchmodSync(fd, 0o600);
    writeAll(fd, buffer, 0);
    fs.fsyncSync(fd);
  } finally { fs.closeSync(fd); }
}

function assertOutputAncestors(output) {
  for (let cur = path.dirname(output); ; cur = path.dirname(cur)) {
    try {
      const st = fs.lstatSync(cur);
      if (st.isSymbolicLink()) throw fail('symlink_refused');
      if (!st.isDirectory()) throw fail('path_refused');
    } catch (error) {
      if (error.reason) throw error;
      if (error.code !== 'ENOENT') throw fail('input_io_error');
    }
    if (cur === path.dirname(cur)) break;
  }
}

function nodeExists(target) {
  try { fs.lstatSync(target); return true; }
  catch (error) { if (error.code === 'ENOENT') return false; throw error; }
}

function esTrim(value) {
  return value.replace(/^\s+|\s+$/g, '');
}

function toHttp(filemanagerName) {
  const slashed = filemanagerName.replace(/\\/g, '/');
  try {
    return slashed.replace(/[^/]+/g, (segment) => encodeURIComponent(segment));
  } catch (error) {
    if (error instanceof URIError) throw fail('uri_encoding_unsupported');
    throw error;
  }
}

function requireSafeCount(value) {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) throw fail('invalid_catalog_input');
}

function requireHeader(value) {
  if (!Array.isArray(value) || value.length !== 2 ||
      !value.every((n) => typeof n === 'number' && Number.isInteger(n) && n >= 0 && n <= 255)) {
    throw fail('invalid_catalog_input');
  }
}

function validateGround(summary) {
  if (!summary || typeof summary !== 'object' || Array.isArray(summary)) throw fail('invalid_catalog_input');
  const textures = summary.textures;
  const indexes = summary.texture_indexes;
  if (!Array.isArray(textures) || !Array.isArray(indexes)) throw fail('invalid_catalog_input');
  const names = new Set();
  for (const name of textures) {
    if (typeof name !== 'string' || names.has(name)) throw fail('invalid_catalog_input');
    names.add(name);
  }
  const seen = new Set();
  let next = 0;
  for (const value of indexes) {
    if (typeof value !== 'number' || !Number.isInteger(value) || value < 0 || value >= textures.length) {
      throw fail('invalid_catalog_input');
    }
    if (!seen.has(value)) {
      if (value !== next) throw fail('invalid_catalog_input');
      seen.add(value);
      next += 1;
    }
  }
  if (next !== textures.length) throw fail('invalid_catalog_input');
  return { textures, indexes };
}

function validateModels(summary) {
  if (!summary || typeof summary !== 'object' || Array.isArray(summary)) throw fail('invalid_catalog_input');
  const deps = summary.model_dependencies;
  if (!Array.isArray(deps)) throw fail('invalid_catalog_input');
  deps.forEach((item, index) => {
    if (!item || typeof item !== 'object' || Array.isArray(item)) throw fail('invalid_catalog_input');
    if (item.object_index !== index || typeof item.filename !== 'string' || typeof item.nodename !== 'string') {
      throw fail('invalid_catalog_input');
    }
  });
  return deps;
}

function blankCounts() {
  return {
    roots: 0, jobs: 0, job_kinds: { rsw: 0, gnd: 0, gat: 0 }, core_chain_roots: 0, remaining_gap_roots: 0,
    root_edge_references: 0, occurrences: { model: 0, ground_texture: 0 },
    loader_entries: { model: 0, ground_texture: 0 },
    root_expanded_occurrences: { model: 0, ground_texture: 0 },
    root_expanded_loader_entries: { model: 0, ground_texture: 0 },
    distinct_names_by_role: {
      model: { raw: 0, logical: 0, filemanager: 0, http: 0 },
      ground_texture: { raw: 0, logical: 0, filemanager: 0, http: 0 }
    },
    http_targets: 0
  };
}

// Pure projection. Throws Error with reason invalid_catalog_input or uri_encoding_unsupported.
export function buildCatalog(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw fail('invalid_catalog_input');
  const rows = input.rows;
  const rootsIn = input.roots;
  const gapIn = input.remaining_gap_root_ordinals;
  if (!Array.isArray(rows) || !Array.isArray(rootsIn) || !Array.isArray(gapIn)) throw fail('invalid_catalog_input');

  const byId = new Map();
  rows.forEach((row, index) => {
    if (!row || typeof row !== 'object' || Array.isArray(row)) throw fail('invalid_catalog_input');
    if (typeof row.id !== 'string' || row.id.length === 0 || byId.has(row.id)) throw fail('invalid_catalog_input');
    if (row.kind !== 'rsw' && row.kind !== 'gnd' && row.kind !== 'gat') throw fail('invalid_catalog_input');
    if (!isHex64(row.complete_sha256)) throw fail('invalid_catalog_input');
    requireSafeCount(row.input_bytes);
    requireHeader(row.header_version_bytes);
    if (row.outcome !== 'returned' || row.constructor_returned !== true || row.worker_started !== true) {
      throw fail('invalid_catalog_input');
    }
    if (!row.cleanup || typeof row.cleanup !== 'object' || row.cleanup.exit_observed !== true) throw fail('invalid_catalog_input');
    if (row.kind === 'rsw') validateModels(row.summary);
    else if (row.kind === 'gnd') validateGround(row.summary);
    byId.set(row.id, index);
  });

  const references = rows.map(() => []);
  const ordinals = new Set();
  const derivedGaps = [];
  let core = 0;
  let edgeRefs = 0;
  for (const root of rootsIn) {
    if (!root || typeof root !== 'object' || Array.isArray(root)) throw fail('invalid_catalog_input');
    if (typeof root.ordinal !== 'number' || !Number.isSafeInteger(root.ordinal) || root.ordinal < 0 || ordinals.has(root.ordinal)) {
      throw fail('invalid_catalog_input');
    }
    ordinals.add(root.ordinal);
    if (!root.edges || typeof root.edges !== 'object' || Array.isArray(root.edges)) throw fail('invalid_catalog_input');
    let present = 0;
    for (const kind of KINDS) {
      const edge = root.edges[kind];
      if (!edge || typeof edge !== 'object' || Array.isArray(edge) || !own(edge, 'job_id')) throw fail('invalid_catalog_input');
      if (edge.job_id === null) continue;
      if (typeof edge.job_id !== 'string') throw fail('invalid_catalog_input');
      const rowIndex = byId.get(edge.job_id);
      if (rowIndex === undefined || rows[rowIndex].kind !== kind) throw fail('invalid_catalog_input');
      references[rowIndex].push({ root_ordinal: root.ordinal, edge_kind: kind });
      present += 1;
      edgeRefs += 1;
    }
    if (root.edges.rsw.job_id === null) derivedGaps.push(root.ordinal);
    if (present === 3) core += 1;
  }
  if (references.some((list) => list.length === 0)) throw fail('invalid_catalog_input');
  if (derivedGaps.length !== gapIn.length || derivedGaps.some((ordinal, index) => ordinal !== gapIn[index])) {
    throw fail('invalid_catalog_input');
  }

  const targets = [];
  const targetByHttp = new Map();
  const distinct = {
    model: { raw: new Set(), logical: new Set(), filemanager: new Set(), http: new Set() },
    ground_texture: { raw: new Set(), logical: new Set(), filemanager: new Set(), http: new Set() }
  };
  const counts = blankCounts();
  counts.roots = rootsIn.length;
  counts.jobs = rows.length;
  counts.core_chain_roots = core;
  counts.remaining_gap_roots = gapIn.length;
  counts.root_edge_references = edgeRefs;

  const jobs = rows.map((row, jobIndex) => {
    counts.job_kinds[row.kind] += 1;
    const refs = references[jobIndex];
    const base = {
      source_row_index: jobIndex,
      id: row.id,
      kind: row.kind,
      complete_sha256: row.complete_sha256,
      input_bytes: row.input_bytes,
      header_version_bytes: [row.header_version_bytes[0], row.header_version_bytes[1]],
      outcome: row.outcome,
      constructor_returned: row.constructor_returned,
      root_references: refs.map((ref) => ({ root_ordinal: ref.root_ordinal, edge_kind: ref.edge_kind }))
    };
    if (row.kind === 'gat') {
      return { ...base, role: null, occurrence_summary_pointer: null, occurrence_loader_indexes: null, loader_entries: null };
    }
    const role = row.kind === 'rsw' ? 'model' : 'ground_texture';
    let occurrenceIndexes;
    let pending;
    if (role === 'model') {
      const deps = row.summary.model_dependencies;
      const first = new Map();
      pending = [];
      occurrenceIndexes = deps.map((item) => {
        const logical = MODEL_PREFIX + item.filename;
        let loaderIndex = first.get(logical);
        if (loaderIndex === undefined) {
          loaderIndex = pending.length;
          first.set(logical, loaderIndex);
          pending.push({
            index: loaderIndex,
            source_name_pointer: `/summary/model_dependencies/${item.object_index}/filename`,
            raw_name: item.filename,
            logical_name: logical
          });
        }
        return loaderIndex;
      });
    } else {
      const { textures, indexes } = validateGround(row.summary);
      occurrenceIndexes = indexes.slice();
      pending = textures.map((raw, index) => ({
        index,
        source_name_pointer: `/summary/textures/${index}`,
        raw_name: raw,
        logical_name: TEXTURE_PREFIX + raw
      }));
    }
    const names = distinct[role];
    const loaderEntries = pending.map((entry) => {
      const filemanagerName = esTrim(entry.logical_name);
      const httpPath = toHttp(filemanagerName);
      let targetIndex = targetByHttp.get(httpPath);
      if (targetIndex === undefined) {
        targetIndex = targets.length;
        targetByHttp.set(httpPath, targetIndex);
        targets.push({ index: targetIndex, http_path: httpPath, referrers: [] });
      }
      targets[targetIndex].referrers.push({ job_index: jobIndex, loader_index: entry.index, role });
      names.raw.add(entry.raw_name);
      names.logical.add(entry.logical_name);
      names.filemanager.add(filemanagerName);
      names.http.add(httpPath);
      return { ...entry, filemanager_name: filemanagerName, http_path: httpPath, target_index: targetIndex };
    });
    const occ = occurrenceIndexes.length;
    const loaders = loaderEntries.length;
    counts.occurrences[role] += occ;
    counts.loader_entries[role] += loaders;
    counts.root_expanded_occurrences[role] += occ * refs.length;
    counts.root_expanded_loader_entries[role] += loaders * refs.length;
    return {
      ...base,
      role,
      occurrence_summary_pointer: role === 'model' ? '/summary/model_dependencies' : '/summary/texture_indexes',
      occurrence_loader_indexes: occurrenceIndexes,
      loader_entries: loaderEntries
    };
  });
  counts.distinct_names_by_role = {
    model: { raw: distinct.model.raw.size, logical: distinct.model.logical.size, filemanager: distinct.model.filemanager.size, http: distinct.model.http.size },
    ground_texture: {
      raw: distinct.ground_texture.raw.size, logical: distinct.ground_texture.logical.size,
      filemanager: distinct.ground_texture.filemanager.size, http: distinct.ground_texture.http.size
    }
  };
  counts.http_targets = targets.length;
  return {
    counts,
    roots: structuredClone(rootsIn),
    remaining_gap_root_ordinals: gapIn.slice(),
    jobs,
    targets
  };
}

export function assertCatalogLinks(payload) {
  const { counts, jobs, targets } = payload;
  if (counts.jobs !== jobs.length || counts.http_targets !== targets.length || counts.roots !== payload.roots.length) {
    throw fail('invariant_failed');
  }
  const seenHttp = new Set();
  let referrers = 0;
  let loaders = 0;
  for (const target of targets) {
    if (seenHttp.has(target.http_path)) throw fail('invariant_failed');
    seenHttp.add(target.http_path);
    referrers += target.referrers.length;
  }
  for (let jobIndex = 0; jobIndex < jobs.length; jobIndex++) {
    const job = jobs[jobIndex];
    if (job.role === null) {
      if (job.loader_entries !== null || job.occurrence_loader_indexes !== null) throw fail('invariant_failed');
      continue;
    }
    loaders += job.loader_entries.length;
    for (const occurrence of job.occurrence_loader_indexes) {
      if (!Number.isInteger(occurrence) || occurrence < 0 || occurrence >= job.loader_entries.length) throw fail('invariant_failed');
    }
    for (const entry of job.loader_entries) {
      const target = targets[entry.target_index];
      if (!target || target.http_path !== entry.http_path) throw fail('invariant_failed');
      const hit = target.referrers.filter((ref) => ref.job_index === jobIndex && ref.loader_index === entry.index && ref.role === job.role);
      if (hit.length !== 1) throw fail('invariant_failed');
    }
  }
  if (referrers !== loaders) throw fail('invariant_failed');
}

function deepEqual(a, b) {
  if (a === b) return true;
  if (typeof a !== typeof b || a === null || b === null || typeof a !== 'object') return false;
  if (Array.isArray(a) !== Array.isArray(b)) return false;
  if (Array.isArray(a)) return a.length === b.length && a.every((value, index) => deepEqual(value, b[index]));
  const keys = Object.keys(a);
  return keys.length === Object.keys(b).length && keys.every((key) => own(b, key) && deepEqual(a[key], b[key]));
}

function readJson(buffer) {
  try { return JSON.parse(buffer.toString('utf8')); }
  catch { throw fail('invalid_json'); }
}

function pinBytes(spec) {
  if (!spec || !Number.isSafeInteger(spec.bytes) || spec.bytes < 0 || !isHex64(spec.sha256)) throw fail('profile_invalid');
  return spec;
}

function pinRecord(spec) {
  if (!spec || typeof spec.path !== 'string') throw fail('profile_invalid');
  return pinBytes(spec);
}

function validateProfile(profile) {
  if (!profile || profile.schema !== 'T06-map-dependency-profile-1' || profile.task !== 'T06.003.003.004') throw fail('profile_invalid');
  pinRecord(profile.inputs && profile.inputs['report.json']);
  pinRecord(profile.inputs && profile.inputs['jobs.jsonl']);
  pinRecord(profile.authored);
  pinRecord(profile.constructor_profile);
  pinRecord(profile.summary);
  const rules = profile.rule_sources;
  if (!rules || typeof rules !== 'object' || Array.isArray(rules)) throw fail('profile_invalid');
  if (Object.keys(rules).length !== RULE_KEYS.length || RULE_KEYS.some((key) => !pinBytes(rules[key]))) throw fail('profile_invalid');
  const policy = profile.policy || {};
  for (const key of ['max_jobs_bytes', 'max_job_row_bytes', 'max_report_bytes', 'max_fixture_bytes', 'max_catalog_bytes', 'max_stdout_bytes']) {
    if (!Number.isSafeInteger(policy[key]) || policy[key] < 1) throw fail('profile_invalid');
  }
  if (!Array.isArray(profile.limitations) || profile.limitations.some((item) => typeof item !== 'string')) throw fail('profile_invalid');
  if (!profile.expected_counts || typeof profile.expected_counts !== 'object') throw fail('profile_invalid');
  return profile;
}

export function parseJobsJsonl(buffer, { maxRowBytes, maxTotalBytes }) {
  if (!Buffer.isBuffer(buffer)) throw fail('invalid_json');
  if (buffer.length > maxTotalBytes) throw fail('size_limit');
  if (buffer.length === 0 || buffer[buffer.length - 1] !== 0x0a) throw fail('invalid_json');
  const rows = [];
  let start = 0;
  for (let i = 0; i < buffer.length; i++) {
    if (buffer[i] !== 0x0a) continue;
    const line = buffer.subarray(start, i);
    if (line.length === 0 || line.length > maxRowBytes) throw fail(line.length === 0 ? 'invalid_json' : 'size_limit');
    let row;
    try { row = JSON.parse(line.toString('utf8')); }
    catch { throw fail('invalid_json'); }
    if (!row || typeof row !== 'object' || Array.isArray(row)) throw fail('invalid_json');
    rows.push(row);
    start = i + 1;
  }
  if (start !== buffer.length) throw fail('invalid_json');
  return rows;
}

function parseArgs(argv) {
  const opts = {};
  const flags = new Set(['--input-root', '--profile', '--fixtures', '--report', '--jobs', '--output', '--max-output-bytes']);
  for (let i = 0; i < argv.length; i++) {
    const flag = argv[i];
    if (!flags.has(flag)) throw fail('usage');
    const value = argv[++i];
    if (value === undefined || value.startsWith('--')) throw fail('usage');
    const key = flag.slice(2).replace(/-/g, '_');
    if (own(opts, key)) throw fail('usage');
    opts[key] = value;
  }
  if (!opts.input_root || !opts.profile || !opts.output) throw fail('usage');
  const fixtureMode = own(opts, 'fixtures');
  const corpusMode = own(opts, 'report') || own(opts, 'jobs');
  if (fixtureMode === corpusMode || (corpusMode && (!opts.report || !opts.jobs))) throw fail('usage');
  if (own(opts, 'max_output_bytes') && !/^\d{1,16}$/.test(opts.max_output_bytes)) throw fail('usage');
  opts.mode = fixtureMode ? 'fixtures' : 'corpus';
  return opts;
}

function prepareOutput(output) {
  const privateRoot = path.join(REPO_ROOT, '.tools', 'renewal');
  const resolved = path.resolve(output);
  if (resolved !== privateRoot && !resolved.startsWith(privateRoot + path.sep)) throw fail('path_refused');
  if (resolved === privateRoot) throw fail('path_refused');
  assertOutputAncestors(resolved);
  if (nodeExists(resolved)) throw fail('output_exists');
  return resolved;
}

function createOutput(output, created) {
  assertOutputAncestors(output);
  fs.mkdirSync(path.dirname(output), { recursive: true, mode: 0o700 });
  assertOutputAncestors(output);
  if (nodeExists(output)) throw fail('output_exists');
  try { fs.mkdirSync(output, { mode: 0o700 }); }
  catch (error) {
    if (error.code === 'EEXIST') throw fail('output_exists');
    throw fail('output_io_error');
  }
  created.value = true;
  fs.chmodSync(output, 0o700);
}

export function main(argv, { stdout = process.stdout } = {}) {
  const created = { value: false };
  try {
    if (!fs.constants.O_NOFOLLOW) throw fail('environment');
    const opts = parseArgs(argv);
    const inputRoot = path.resolve(opts.input_root);
    assertLinkFree(inputRoot);
    const rootStat = fs.lstatSync(inputRoot);
    if (rootStat.isSymbolicLink() || !rootStat.isDirectory()) throw fail('path_refused');
    const output = prepareOutput(opts.output);
    const profileFile = readPinnedFile(path.resolve(opts.profile), {
      maxBytes: PROFILE_BYTES, expectBytes: PROFILE_BYTES, expectSha: PROFILE_SHA256
    });
    const profile = validateProfile(readJson(profileFile.buffer));
    const policy = profile.policy;
    let cap = policy.max_catalog_bytes;
    if (own(opts, 'max_output_bytes')) {
      const requested = Number(opts.max_output_bytes);
      if (requested > policy.max_catalog_bytes) throw fail('policy_increase');
      cap = requested;
    }
    const pins = [profileFile];
    const constructorAbs = safeJoin(REPO_ROOT, profile.constructor_profile.path, 'constructor_profile');
    const constructorFile = readPinnedFile(constructorAbs, {
      maxBytes: profile.constructor_profile.bytes, expectBytes: profile.constructor_profile.bytes, expectSha: profile.constructor_profile.sha256
    });
    pins.push(constructorFile);
    const constructorProfile = readJson(constructorFile.buffer);
    if (!constructorProfile || constructorProfile.client_source_relative !== CLIENT_SOURCE_RELATIVE) throw fail('profile_invalid');
    const summaryAbs = safeJoin(REPO_ROOT, profile.summary.path, 'summary');
    const summaryFile = readPinnedFile(summaryAbs, {
      maxBytes: profile.summary.bytes, expectBytes: profile.summary.bytes, expectSha: profile.summary.sha256
    });
    pins.push(summaryFile);
    const clientSource = safeJoin(inputRoot, CLIENT_SOURCE_RELATIVE, 'client_source');
    for (const key of RULE_KEYS) {
      const spec = profile.rule_sources[key];
      pins.push(readPinnedFile(safeJoin(clientSource, key, 'rule'), {
        maxBytes: spec.bytes, expectBytes: spec.bytes, expectSha: spec.sha256
      }));
    }
    let catalogInput;
    let inputPins;
    if (opts.mode === 'fixtures') {
      const authoredFile = readPinnedFile(path.resolve(opts.fixtures), {
        maxBytes: policy.max_fixture_bytes, expectBytes: profile.authored.bytes, expectSha: profile.authored.sha256
      });
      pins.push(authoredFile);
      const authored = readJson(authoredFile.buffer);
      if (!authored || authored.schema !== 'T06-map-dependency-authored-1' || !authored.input) throw fail('fixtures_invalid');
      catalogInput = authored.input;
      inputPins = { authored: structuredClone(profile.authored) };
    } else {
      const reportAbs = path.resolve(opts.report);
      const jobsAbs = path.resolve(opts.jobs);
      const expectedReport = safeJoin(inputRoot, profile.inputs['report.json'].path, 'report');
      const expectedJobs = safeJoin(inputRoot, profile.inputs['jobs.jsonl'].path, 'jobs');
      if (reportAbs !== expectedReport || jobsAbs !== expectedJobs) throw fail('path_refused');
      const reportSpec = profile.inputs['report.json'];
      const jobsSpec = profile.inputs['jobs.jsonl'];
      const reportFile = readPinnedFile(reportAbs, {
        maxBytes: policy.max_report_bytes, expectBytes: reportSpec.bytes, expectSha: reportSpec.sha256
      });
      const jobsFile = readPinnedFile(jobsAbs, {
        maxBytes: policy.max_jobs_bytes, expectBytes: jobsSpec.bytes, expectSha: jobsSpec.sha256
      });
      pins.push(reportFile, jobsFile);
      const report = readJson(reportFile.buffer);
      if (!report || report.schema !== 'T06-map-constructor-report-1' || report.task !== 'T06.003.003.003' || report.mode !== 'corpus') {
        throw fail('report_invalid');
      }
      if (report.profile_sha256 !== profile.constructor_profile.sha256 || report.summary_sha256 !== profile.summary.sha256) {
        throw fail('report_invalid');
      }
      if (report.pinned_inputs_identity_unchanged_after_run !== true) throw fail('report_invalid');
      const cleanup = report.cleanup || {};
      const expectedJobsCount = profile.expected_counts.jobs;
      if (cleanup.verified !== true || !Array.isArray(cleanup.unverified) || cleanup.unverified.length !== 0 ||
          cleanup.halted !== null || cleanup.workers_started !== expectedJobsCount || cleanup.exits_observed !== expectedJobsCount) {
        throw fail('report_invalid');
      }
      const counts = report.counts || {};
      if (counts.expected_jobs !== expectedJobsCount || counts.records !== expectedJobsCount ||
          !counts.job_outcomes || counts.job_outcomes.returned !== expectedJobsCount) throw fail('report_invalid');
      const jobsMeta = report.jobs_file || {};
      if (jobsMeta.bytes !== jobsFile.bytes || jobsMeta.sha256 !== jobsFile.sha256 || jobsMeta.records !== expectedJobsCount) {
        throw fail('report_invalid');
      }
      const reportedSources = report.client_source && report.client_source.sources;
      const profileSources = constructorProfile.sources;
      if (!profileSources || typeof profileSources !== 'object' || !Array.isArray(reportedSources)) throw fail('report_invalid');
      if (reportedSources.length !== Object.keys(profileSources).length) throw fail('report_invalid');
      const seen = new Set();
      for (const source of reportedSources) {
        if (!source || source.verified !== true || typeof source.path !== 'string' || seen.has(source.path)) throw fail('report_invalid');
        seen.add(source.path);
        const spec = profileSources[source.path];
        if (!spec || spec.bytes !== source.bytes || spec.sha256 !== source.sha256 || !isHex64(source.sha256)) throw fail('report_invalid');
        pins.push(readPinnedFile(safeJoin(clientSource, source.path, 'client_source'), {
          maxBytes: spec.bytes, expectBytes: spec.bytes, expectSha: spec.sha256
        }));
      }
      const rows = parseJobsJsonl(jobsFile.buffer, { maxRowBytes: policy.max_job_row_bytes, maxTotalBytes: policy.max_jobs_bytes });
      if (rows.length !== expectedJobsCount) throw fail('report_invalid');
      const manifest = report.input_manifest || {};
      if (!Array.isArray(report.roots) || !Array.isArray(manifest.remaining_gap_root_ordinals)) throw fail('report_invalid');
      catalogInput = { rows, roots: report.roots, remaining_gap_root_ordinals: manifest.remaining_gap_root_ordinals };
      inputPins = structuredClone(profile.inputs);
    }
    const payload = buildCatalog(catalogInput);
    assertCatalogLinks(payload);
    if (!pins.every(recheckIdentity)) throw fail('identity_changed');
    if (opts.mode === 'corpus' && !deepEqual(payload.counts, profile.expected_counts)) throw fail('counts_mismatch');
    const envelope = {
      schema: 'T06-map-dependency-catalog-1',
      task: 'T06.003.003.004',
      mode: opts.mode,
      profile_sha256: profileFile.sha256,
      input_pins: inputPins,
      constructor_profile_sha256: constructorFile.sha256,
      summary_sha256: summaryFile.sha256,
      rule_sources: structuredClone(profile.rule_sources),
      counts: payload.counts,
      roots: payload.roots,
      remaining_gap_root_ordinals: payload.remaining_gap_root_ordinals,
      jobs: payload.jobs,
      targets: payload.targets,
      limitations: structuredClone(profile.limitations)
    };
    const body = Buffer.from(JSON.stringify(envelope) + '\n', 'utf8');
    if (body.length > cap || body.length > policy.max_catalog_bytes) throw fail('output_budget');
    createOutput(output, created);
    writeExclusive(path.join(output, 'catalog.json'), body);
    if (!pins.every(recheckIdentity)) {
      say(stdout, { status: 'error', reason: 'identity_changed', output_created: true });
      return 1;
    }
    say(stdout, { status: 'complete', mode: opts.mode, counts: payload.counts, output_created: true });
    return 0;
  } catch (error) {
    say(stdout, { status: created.value ? 'error' : 'refused', reason: reasonOf(error), output_created: created.value });
    return created.value ? 1 : 2;
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  Promise.resolve(main(process.argv.slice(2))).then((code) => { process.exitCode = code; }, () => {
    process.stdout.write(JSON.stringify({ status: 'error', reason: 'unhandled', output_created: false }) + '\n');
    process.exitCode = 1;
  });
}
