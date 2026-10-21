#!/usr/bin/env node
// T06.003.003.004 first-level map dependency request catalog.
// Projects declared RSW model filenames and GND ground-texture table entries
// into FileManager relative HTTP strings. A target is a constructed string,
// not a GET, archive winner, browser URL or playable map.
// T07.007.005 adds one trusted profile route that admits the integrated
// T07.007.004 constructor report/jobs through its frozen input manifest.
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const PROFILE_SHA256 = '304e9da6ad4369ba96f30f71229de56581aedf6ee0789cc3d6261beb7e219df4';
export const PROFILE_BYTES = 3379;
const CLIENT_SOURCE_RELATIVE = '.tools/renewal/client-source';

// Trusted profile descriptors, selected by exact size and full SHA before any
// profile field is believed. The bridge descriptor fixes every pin it binds.
const LEGACY_ROUTE = Object.freeze({
  bytes: PROFILE_BYTES, sha256: PROFILE_SHA256, task: 'T06.003.003.004', report_task: 'T06.003.003.003', bridge: false
});
const BRIDGE_ROUTE = deepFreeze({
  bytes: 4649,
  sha256: 'c0dccf5d0f74eecbcf772c560820dc3e0b4e5b26986243255085701136117034',
  task: 'T07.007.005',
  report_task: 'T07.007.004',
  bridge: true,
  constructor_task: 'T07.007.004',
  source_count: 9,
  constructor_counts: { roots: 4, observed: 4, unavailable_roots: 0, jobs: 12, edge_references: 12 },
  pins: {
    inputs: {
      'report.json': {
        path: '.tools/renewal/t07-007-004-integrated-root-qualification-1/output-1/report.json',
        bytes: 8112, sha256: '8ed966871049c55a1f556556814ec8fcdaa1d28b094013257aedebcdd5d69116'
      },
      'jobs.jsonl': {
        path: '.tools/renewal/t07-007-004-integrated-root-qualification-1/output-1/jobs.jsonl',
        bytes: 405225, sha256: '28dc69cfd7025f02b35e3071eb8a6a84bfd37c6e1a4a32011c155e468a525e94'
      }
    },
    authored: {
      path: 'docs/project/fixtures/T06.003.003.004-authored.json',
      bytes: 165420, sha256: '3848febb48ca112029024d9885498236037e94d436cf372d6a38d0d8e20cf24f'
    },
    constructor_profile: {
      path: 'docs/project/fixtures/T07.007.004-profile.json',
      bytes: 3924, sha256: 'f4ed366d2da83eec2aed5a25178ce826d15b43bb7a8b6c583e023c616b47e56e'
    },
    summary: {
      path: 'tools/renewal/map_constructor_summary.mjs',
      bytes: 5052, sha256: '33cdb4ce770b32cdbe061f4f2415e8b5808e3f02d0e7f870250f11f486b3ddf1'
    },
    rule_sources: {
      'src/Loaders/MapLoader.js': { bytes: 14466, sha256: 'c71b01f300f62bbc6e7432444e2521d713473dc47c9c6e25a54a832d5c92a705' },
      'src/Core/FileManager.js': { bytes: 11279, sha256: '75c37d192bf21e7b40817a6f2fe27ef536601515c07fe20c7ce8346d50376cd7' },
      'src/Loaders/Ground.js': { bytes: 20029, sha256: '8b82cf7321123054cf2bbeff1816931c7f3fc7833ae7af916077691d871f2db0' }
    },
    constructor_task: 'T07.007.004',
    constructor_manifest: {
      path: '.tools/renewal/t07-007-004-constructor-input-1/input-manifest.json',
      bytes: 10338, sha256: '37f038082891a626ab1251fd3bd697d73a867f9dca90ba89288f5b18e6be2161'
    },
    constructor_worker: {
      path: 'tools/renewal/map_constructor_worker.mjs',
      bytes: 9132, sha256: '1a7bdf5693364800b23c2ba2a4eb052c0521527b89732e857d55ea406e0ec395'
    },
    constructor_producer: {
      commit: '68ec8ac9fbddac3dff273460498df36a9bcfc60a',
      path: 'tools/renewal/probe_map_constructors.mjs',
      bytes: 44087, sha256: 'ec581316ad7220956613322f598310b91d2e1d455a0949edb7539c230fc8c961'
    }
  }
});
const PROFILE_ROUTES = [LEGACY_ROUTE, BRIDGE_ROUTE];
const MAX_PROFILE_BYTES = Math.max(...PROFILE_ROUTES.map((route) => route.bytes));
const INPUT_MANIFEST_KEYS = [
  'schema', 'status', 'counts', 'inputs', 'overlay', 'job_order', 'remaining_gap_root_ordinals',
  'qualification_limits', 'parser_execution_performed_in_input'
];
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
const isObject = (value) => !!value && typeof value === 'object' && !Array.isArray(value);

function deepFreeze(value) {
  if (!value || typeof value !== 'object' || Object.isFrozen(value)) return value;
  for (const key of Object.keys(value)) deepFreeze(value[key]);
  return Object.freeze(value);
}

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

function samePin(a, b) {
  return isObject(a) && isObject(b) && a.path === b.path && a.bytes === b.bytes && a.sha256 === b.sha256;
}

// Chooses the trusted descriptor from the file's size and full SHA alone.
function readProfile(abs) {
  assertLinkFree(abs);
  const st = fs.lstatSync(abs);
  let route = LEGACY_ROUTE;
  if (st.isFile()) {
    if (st.size > MAX_PROFILE_BYTES) throw fail('size_limit');
    route = PROFILE_ROUTES.find((item) => item.bytes === st.size);
    if (!route) throw fail('pin_mismatch');
  }
  const file = readPinnedFile(abs, { maxBytes: route.bytes, expectBytes: route.bytes, expectSha: route.sha256 });
  return { route, file };
}

function validateProfile(profile, route) {
  if (!profile || profile.schema !== 'T06-map-dependency-profile-1' || profile.task !== route.task) throw fail('profile_invalid');
  if (route.bridge) {
    for (const [key, pin] of Object.entries(route.pins)) {
      if (!deepEqual(profile[key], pin)) throw fail('profile_invalid');
    }
    const max = profile.policy && profile.policy.max_manifest_bytes;
    if (!Number.isSafeInteger(max) || max < 1) throw fail('profile_invalid');
    if (!profile.expected_counts || profile.expected_counts.jobs !== route.constructor_counts.jobs ||
        profile.expected_counts.roots !== route.constructor_counts.roots) throw fail('profile_invalid');
  }
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

// Binds the constructor profile's task, manifest, worker, summary and source pins
// to the admitted bridge profile and its trusted descriptor.
function validateConstructorProfile(constructorProfile, profile, route) {
  const cp = constructorProfile;
  if (!isObject(cp) || cp.schema !== 'T06-map-constructor-profile-1' || cp.task !== route.constructor_task ||
      cp.task !== profile.constructor_task || cp.client_source_relative !== CLIENT_SOURCE_RELATIVE ||
      typeof cp.client_source_revision !== 'string') {
    throw fail('profile_invalid');
  }
  if (!samePin(cp.manifest, profile.constructor_manifest) || !samePin(cp.worker, profile.constructor_worker) ||
      !samePin(cp.summary, profile.summary) || !deepEqual(cp.counts, route.constructor_counts)) {
    throw fail('profile_invalid');
  }
  const sources = cp.sources;
  if (!isObject(sources) || Object.keys(sources).length !== route.source_count) throw fail('profile_invalid');
  for (const key of Object.keys(sources)) {
    const spec = sources[key];
    if (!isObject(spec) || !Number.isSafeInteger(spec.bytes) || spec.bytes < 0 || !isHex64(spec.sha256)) throw fail('profile_invalid');
    const rule = profile.rule_sources[key];
    if (rule && (rule.bytes !== spec.bytes || rule.sha256 !== spec.sha256)) throw fail('profile_invalid');
  }
  return cp;
}

function requireManifestJob(job) {
  if (!isObject(job) || typeof job.job_id !== 'string' || job.job_id.length === 0 || !KINDS.includes(job.kind) ||
      !isHex64(job.complete_sha256) || !Number.isSafeInteger(job.bytes) || job.bytes < 0 || !isObject(job.header)) {
    throw fail('manifest_invalid');
  }
  const header = job.header.version_bytes;
  if (!Array.isArray(header) || header.length !== 2 ||
      !header.every((n) => typeof n === 'number' && Number.isInteger(n) && n >= 0 && n <= 255)) {
    throw fail('manifest_invalid');
  }
}

// Pure T07.007.004 metadata bridge. Validates the frozen input manifest, binds each
// physical jobs row to manifest.jobs[i], and checks the report against both. Returns
// the buildCatalog input. `bind` carries the admitted absolute paths and file pins.
export function admitConstructorBridge({ report, manifest, rows, constructorProfile, bind }) {
  const counts = constructorProfile.counts;
  const n = counts.jobs;

  if (!isObject(manifest) || manifest.schema !== 'T06-map-constructor-input-1' || manifest.task !== constructorProfile.task ||
      !deepEqual(manifest.counts, counts) || !Array.isArray(manifest.roots) || !Array.isArray(manifest.jobs) ||
      manifest.roots.length !== counts.roots || manifest.jobs.length !== n ||
      !Array.isArray(manifest.remaining_gap_root_ordinals) || typeof manifest.parser_execution_performed !== 'boolean') {
    throw fail('manifest_invalid');
  }
  const links = new Map();
  manifest.jobs.forEach((job) => {
    requireManifestJob(job);
    if (links.has(job.job_id)) throw fail('manifest_invalid');
    links.set(job.job_id, { kind: job.kind, refs: 0 });
  });
  const ordinals = new Set();
  const order = [];
  const gaps = [];
  let edgeRefs = 0;
  let unavailable = 0;
  for (const root of manifest.roots) {
    if (!isObject(root) || !Number.isSafeInteger(root.ordinal) || root.ordinal < 0 || ordinals.has(root.ordinal) ||
        !isObject(root.edges)) {
      throw fail('manifest_invalid');
    }
    ordinals.add(root.ordinal);
    let present = 0;
    for (const kind of ['gat', 'gnd', 'rsw']) {
      const edge = root.edges[kind];
      if (!isObject(edge) || !own(edge, 'job_id')) throw fail('manifest_invalid');
      if (edge.job_id === null) continue;
      const link = typeof edge.job_id === 'string' ? links.get(edge.job_id) : undefined;
      if (!link || link.kind !== kind) throw fail('manifest_invalid');
      if (link.refs === 0) order.push(edge.job_id);
      link.refs += 1;
      edgeRefs += 1;
      present += 1;
    }
    if (present === 0) unavailable += 1;
    if (root.edges.rsw.job_id === null) gaps.push(root.ordinal);
  }
  if ([...links.values()].some((link) => link.refs === 0) || edgeRefs !== counts.edge_references ||
      unavailable !== counts.unavailable_roots || manifest.roots.length - unavailable !== counts.observed ||
      !deepEqual(order, manifest.jobs.map((job) => job.job_id)) || !deepEqual(gaps, manifest.remaining_gap_root_ordinals)) {
    throw fail('manifest_invalid');
  }

  if (!Array.isArray(rows) || rows.length !== n) throw fail('jobs_mismatch');
  rows.forEach((row, index) => {
    const job = manifest.jobs[index];
    if (!isObject(row) || row.id !== job.job_id || row.kind !== job.kind || row.complete_sha256 !== job.complete_sha256 ||
        row.input_bytes !== job.bytes || !deepEqual(row.header_version_bytes, job.header.version_bytes)) {
      throw fail('jobs_mismatch');
    }
  });

  if (!isObject(report) || report.schema !== 'T06-map-constructor-report-1' || report.task !== constructorProfile.task ||
      report.mode !== 'corpus') {
    throw fail('report_invalid');
  }
  const input = report.input;
  if (!isObject(input) || input.path !== bind.manifest.abs || input.bytes !== bind.manifest.bytes ||
      input.sha256 !== bind.manifest.sha256) {
    throw fail('report_invalid');
  }
  if (report.profile_sha256 !== bind.constructor_profile_sha256 || report.summary_sha256 !== bind.summary_sha256) {
    throw fail('report_invalid');
  }
  const worker = report.worker;
  if (!samePin(worker, bind.worker) || worker.verified !== true) throw fail('report_invalid');
  const client = report.client_source;
  const profileSources = constructorProfile.sources;
  if (!isObject(client) || client.root !== bind.client_source_root ||
      client.profile_revision !== constructorProfile.client_source_revision || !Array.isArray(client.sources) ||
      client.sources.length !== Object.keys(profileSources).length) {
    throw fail('report_invalid');
  }
  const seen = new Set();
  for (const source of client.sources) {
    if (!isObject(source) || source.verified !== true || typeof source.path !== 'string' || seen.has(source.path) ||
        !own(profileSources, source.path)) {
      throw fail('report_invalid');
    }
    seen.add(source.path);
    const spec = profileSources[source.path];
    if (spec.bytes !== source.bytes || spec.sha256 !== source.sha256) throw fail('report_invalid');
  }
  if (report.pinned_inputs_identity_unchanged_after_run !== true) throw fail('report_invalid');
  const cleanup = report.cleanup;
  if (!isObject(cleanup) || cleanup.verified !== true || !Array.isArray(cleanup.unverified) || cleanup.unverified.length !== 0 ||
      cleanup.halted !== null || cleanup.workers_started !== n || cleanup.exits_observed !== n) {
    throw fail('report_invalid');
  }
  const reportCounts = report.counts;
  const outcomes = isObject(reportCounts) ? reportCounts.job_outcomes : null;
  if (!isObject(outcomes) || reportCounts.expected_jobs !== n || reportCounts.records !== n || reportCounts.attempted !== n ||
      outcomes.returned !== n || Object.keys(outcomes).some((key) => key !== 'returned' && outcomes[key] !== 0)) {
    throw fail('report_invalid');
  }
  const jobsMeta = report.jobs_file;
  if (!isObject(jobsMeta) || typeof jobsMeta.path !== 'string' ||
      path.resolve(path.dirname(bind.report_abs), jobsMeta.path) !== bind.jobs.abs ||
      jobsMeta.bytes !== bind.jobs.bytes || jobsMeta.sha256 !== bind.jobs.sha256 || jobsMeta.records !== n) {
    throw fail('report_invalid');
  }

  // Expected report roots: the manifest roots plus each linked row's outcome.
  const rowIndex = new Map(rows.map((row, index) => [row.id, index]));
  const expectedRoots = structuredClone(manifest.roots);
  for (const root of expectedRoots) {
    for (const kind of KINDS) {
      const edge = root.edges[kind];
      if (edge.job_id !== null) edge.parse_outcome = rows[rowIndex.get(edge.job_id)].outcome;
    }
  }
  if (!Array.isArray(report.roots) || !deepEqual(expectedRoots, report.roots)) throw fail('report_invalid');

  const preserved = report.input_manifest;
  if (!isObject(preserved) || Object.keys(preserved).length !== INPUT_MANIFEST_KEYS.length ||
      INPUT_MANIFEST_KEYS.some((key) => !own(preserved, key)) ||
      preserved.parser_execution_performed_in_input !== manifest.parser_execution_performed ||
      INPUT_MANIFEST_KEYS.some((key) => key !== 'parser_execution_performed_in_input' && !deepEqual(preserved[key], manifest[key]))) {
    throw fail('report_invalid');
  }
  return { rows, roots: report.roots, remaining_gap_root_ordinals: manifest.remaining_gap_root_ordinals };
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
    const { route, file: profileFile } = readProfile(path.resolve(opts.profile));
    const profile = validateProfile(readJson(profileFile.buffer), route);
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
    if (route.bridge) validateConstructorProfile(constructorProfile, profile, route);
    const summaryAbs = safeJoin(REPO_ROOT, profile.summary.path, 'summary');
    const summaryFile = readPinnedFile(summaryAbs, {
      maxBytes: profile.summary.bytes, expectBytes: profile.summary.bytes, expectSha: profile.summary.sha256
    });
    pins.push(summaryFile);
    if (route.bridge) {
      // Worker and producer are pinned as text only; neither is imported or run.
      for (const [key, label] of [['constructor_worker', 'worker'], ['constructor_producer', 'producer']]) {
        const spec = profile[key];
        pins.push(readPinnedFile(safeJoin(REPO_ROOT, spec.path, label), {
          maxBytes: spec.bytes, expectBytes: spec.bytes, expectSha: spec.sha256
        }));
      }
    }
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
    } else if (route.bridge) {
      const reportSpec = profile.inputs['report.json'];
      const jobsSpec = profile.inputs['jobs.jsonl'];
      const manifestSpec = profile.constructor_manifest;
      const reportAbs = path.resolve(opts.report);
      const jobsAbs = path.resolve(opts.jobs);
      if (reportAbs !== safeJoin(inputRoot, reportSpec.path, 'report') || jobsAbs !== safeJoin(inputRoot, jobsSpec.path, 'jobs')) {
        throw fail('path_refused');
      }
      const manifestAbs = safeJoin(inputRoot, manifestSpec.path, 'manifest');
      const reportFile = readPinnedFile(reportAbs, {
        maxBytes: policy.max_report_bytes, expectBytes: reportSpec.bytes, expectSha: reportSpec.sha256
      });
      const jobsFile = readPinnedFile(jobsAbs, {
        maxBytes: policy.max_jobs_bytes, expectBytes: jobsSpec.bytes, expectSha: jobsSpec.sha256
      });
      // The manifest is read as metadata; its body and reference paths are never followed.
      const manifestFile = readPinnedFile(manifestAbs, {
        maxBytes: policy.max_manifest_bytes, expectBytes: manifestSpec.bytes, expectSha: manifestSpec.sha256
      });
      pins.push(reportFile, jobsFile, manifestFile);
      for (const [key, spec] of Object.entries(constructorProfile.sources)) {
        pins.push(readPinnedFile(safeJoin(clientSource, key, 'client_source'), {
          maxBytes: spec.bytes, expectBytes: spec.bytes, expectSha: spec.sha256
        }));
      }
      const report = readJson(reportFile.buffer);
      const manifest = readJson(manifestFile.buffer);
      const rows = parseJobsJsonl(jobsFile.buffer, { maxRowBytes: policy.max_job_row_bytes, maxTotalBytes: policy.max_jobs_bytes });
      catalogInput = admitConstructorBridge({
        report, manifest, rows, constructorProfile,
        bind: {
          manifest: { abs: manifestAbs, bytes: manifestFile.bytes, sha256: manifestFile.sha256 },
          jobs: { abs: jobsAbs, bytes: jobsFile.bytes, sha256: jobsFile.sha256 },
          report_abs: reportAbs,
          constructor_profile_sha256: constructorFile.sha256,
          summary_sha256: summaryFile.sha256,
          worker: profile.constructor_worker,
          client_source_root: clientSource
        }
      });
      inputPins = { ...structuredClone(profile.inputs), constructor_manifest: structuredClone(manifestSpec) };
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
    const bridgePins = route.bridge ? {
      constructor_task: profile.constructor_task,
      constructor_worker: structuredClone(profile.constructor_worker),
      constructor_producer: structuredClone(profile.constructor_producer)
    } : {};
    const envelope = {
      schema: 'T06-map-dependency-catalog-1',
      task: route.task,
      mode: opts.mode,
      profile_sha256: profileFile.sha256,
      input_pins: inputPins,
      constructor_profile_sha256: constructorFile.sha256,
      summary_sha256: summaryFile.sha256,
      ...bridgePins,
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
