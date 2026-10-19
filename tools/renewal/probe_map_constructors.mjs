#!/usr/bin/env node
// T06.003.003.003 real client core-map constructor runner (parent/CLI).
// Runs the unmodified pinned World/Ground/Altitude constructors, one isolated
// worker per job, and records bounded common summaries. Constructor return is
// an observation only: not format validity, rendering or playable coverage.
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { performance } from 'node:perf_hooks';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { Worker } from 'node:worker_threads';
import { MODULE_KEYS } from './map_constructor_worker.mjs';

export const PROFILE_SHA256 = 'b6635a65db373f5240112734e1f51311851101603323fe1d5300dfaa1c74cf5c';
export const PROFILE_MAX_BYTES = 65536;
export const KINDS = ['rsw', 'gnd', 'gat'];
export const OUTCOMES = ['returned', 'constructor_exception', 'summary_error', 'summary_limit', 'input_refused',
  'environment_failure', 'timeout', 'resource_refusal', 'worker_error', 'unattempted'];
const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, '..', '..');
const WORKER_URL = pathToFileURL(path.join(HERE, 'map_constructor_worker.mjs'));
const OVERRIDES = { '--job-timeout-ms': 'job_timeout_ms', '--run-timeout-ms': 'run_timeout_ms',
  '--rss-limit-bytes': 'rss_limit_bytes', '--max-job-json-bytes': 'max_job_json_bytes' };
const EXIT_GRACE_MS = 2000;
const CLEANUP_WAIT_MS = 10000;
const ROW_SLACK_BYTES = 4096;

export class Refusal extends Error {
  constructor(reason, detail) { super(`${reason}${detail ? ': ' + detail : ''}`); this.reason = reason; }
}

const sha256 = (buf) => crypto.createHash('sha256').update(buf).digest('hex');
const isHex64 = (s) => typeof s === 'string' && /^[0-9a-f]{64}$/.test(s);

export function parseArgs(argv) {
  const opts = { overrides: {} };
  const single = ['--input-root', '--client-source', '--profile', '--fixtures', '--manifest', '--output', '--max-jobs', ...Object.keys(OVERRIDES)];
  for (let i = 0; i < argv.length; i++) {
    const flag = argv[i];
    if (!single.includes(flag)) throw new Refusal('usage', `unknown argument ${String(flag).slice(0, 40)}`);
    const value = argv[++i];
    if (value === undefined || value.startsWith('--')) throw new Refusal('usage', `${flag} needs a value`);
    const key = flag.slice(2).replace(/-/g, '_');
    if (key in opts || key in opts.overrides) throw new Refusal('usage', `${flag} repeated`);
    if (OVERRIDES[flag] || flag === '--max-jobs') {
      if (!/^\d{1,16}$/.test(value)) throw new Refusal('usage', `${flag} must be a non-negative integer`);
      opts.overrides[OVERRIDES[flag] || 'max_jobs'] = Number(value);
    } else opts[key] = value;
  }
  for (const k of ['input_root', 'client_source', 'profile', 'output']) {
    if (!opts[k]) throw new Refusal('usage', `--${k.replace(/_/g, '-')} is required`);
  }
  if (!!opts.fixtures === !!opts.manifest) throw new Refusal('usage', 'exactly one of --fixtures or --manifest is required');
  return opts;
}

// Lower-only policy: every override must be positive and not above the profile.
export function effectivePolicy(profilePolicy, overrides, totalJobs) {
  const policy = { ...profilePolicy, max_jobs: totalJobs };
  for (const [key, value] of Object.entries(overrides)) {
    if (key === 'max_jobs') {
      if (value > totalJobs) throw new Refusal('policy_increase', `max_jobs ${value} exceeds ${totalJobs}`);
    } else {
      if (!(value >= 1)) throw new Refusal('policy_invalid', `${key} must be >= 1`);
      if (value > profilePolicy[key]) throw new Refusal('policy_increase', `${key} ${value} exceeds profile ${profilePolicy[key]}`);
    }
    policy[key] = value;
  }
  return policy;
}

// Absolute path must have no symlink anywhere (resolved == realpath).
export function assertNoLinks(abs, label) {
  let real;
  try { real = fs.realpathSync.native(abs); } catch (e) { throw new Refusal('missing_input', `${label} (${e.code})`); }
  if (real !== abs) throw new Refusal('symlink_refused', `${label} path contains a symbolic link`);
}

export function identityOf(st) {
  return { dev: String(st.dev), ino: String(st.ino), size: String(st.size), mtime_ns: String(st.mtimeNs), ctime_ns: String(st.ctimeNs) };
}
const sameIdentity = (a, b) => ['dev', 'ino', 'size', 'mtime_ns', 'ctime_ns'].every((k) => a[k] === b[k]);

// Bounded full read of a regular, link-free file with unchanged identity.
export function readPinnedFile(abs, { label, maxBytes, expectBytes, expectSha }) {
  assertNoLinks(abs, label);
  const before = fs.lstatSync(abs, { bigint: true });
  if (before.isSymbolicLink()) throw new Refusal('symlink_refused', label);
  if (!before.isFile()) throw new Refusal('special_file_refused', label);
  if (before.size > BigInt(maxBytes)) throw new Refusal('size_limit', `${label} exceeds ${maxBytes} bytes`);
  if (expectBytes !== undefined && before.size !== BigInt(expectBytes)) throw new Refusal('pin_mismatch', `${label} size`);
  const fd = fs.openSync(abs, fs.constants.O_RDONLY | (fs.constants.O_NOFOLLOW || 0));
  let buf, opened, after;
  try {
    opened = fs.fstatSync(fd, { bigint: true });
    if (!opened.isFile() || opened.ino !== before.ino || opened.dev !== before.dev) throw new Refusal('identity_changed', label);
    const size = Number(opened.size);
    buf = Buffer.alloc(size);
    let off = 0;
    while (off < size) {
      const n = fs.readSync(fd, buf, off, size - off, off);
      if (n === 0) throw new Refusal('identity_changed', `${label} shrank`);
      off += n;
    }
    if (fs.readSync(fd, Buffer.alloc(1), 0, 1, size) !== 0) throw new Refusal('identity_changed', `${label} grew`);
    after = fs.fstatSync(fd, { bigint: true });
  } finally { fs.closeSync(fd); }
  const relinked = fs.lstatSync(abs, { bigint: true });
  const id0 = identityOf(before);
  if (!sameIdentity(id0, identityOf(opened)) || !sameIdentity(id0, identityOf(after)) || !sameIdentity(id0, identityOf(relinked))) {
    throw new Refusal('identity_changed', label);
  }
  const digest = sha256(buf);
  if (expectSha !== undefined && digest !== expectSha) throw new Refusal('pin_mismatch', `${label} sha256`);
  return { buffer: buf, bytes: buf.length, sha256: digest, identity: id0 };
}

// Relative, non-escaping path below root.
export function safeJoin(root, rel, label) {
  if (typeof rel !== 'string' || rel.length === 0 || rel.length > 4096 || rel.includes('\0') || rel.includes('\\') ||
      path.isAbsolute(rel) || rel.split('/').some((p) => p === '..' || p === '.' || p === '')) {
    throw new Refusal('path_refused', `${label} is not a plain relative path`);
  }
  const abs = path.resolve(root, rel);
  if (!abs.startsWith(root + path.sep)) throw new Refusal('path_refused', `${label} escapes root`);
  return abs;
}

function readJson(buffer, label) {
  try { return JSON.parse(buffer.toString('utf8')); } catch { throw new Refusal('invalid_json', label); }
}

export function validateProfile(profile) {
  const fail = (d) => { throw new Refusal('profile_invalid', d); };
  if (!profile || profile.schema !== 'T06-map-constructor-profile-1' || profile.task !== 'T06.003.003.003') fail('schema');
  const keys = Object.keys(profile.sources || {});
  if (keys.length !== MODULE_KEYS.length || !MODULE_KEYS.every((k) => keys.includes(k))) fail('sources');
  for (const k of keys) {
    const s = profile.sources[k];
    if (!Number.isSafeInteger(s.bytes) || !isHex64(s.sha256)) fail(`source ${k}`);
  }
  for (const k of ['summary', 'authored', 'manifest']) {
    const s = profile[k];
    if (!s || typeof s.path !== 'string' || !Number.isSafeInteger(s.bytes) || !isHex64(s.sha256)) fail(k);
  }
  const p = profile.policy || {};
  for (const k of ['max_body_bytes', 'max_manifest_bytes', 'max_fixture_bytes', 'worker_heap_mib', 'rss_limit_bytes', 'rss_sample_ms',
    'job_timeout_ms', 'module_timeout_ms', 'constructor_timeout_ms', 'run_timeout_ms', 'max_job_json_bytes', 'max_jobs_jsonl_bytes',
    'max_report_json_bytes', 'max_job_log_bytes', 'max_total_log_bytes', 'max_exception_message_chars', 'max_active_workers']) {
    if (!Number.isSafeInteger(p[k]) || p[k] < 1) fail(`policy ${k}`);
  }
  if (p.max_active_workers !== 1) fail('max_active_workers');
  return profile;
}

export function fixtureJobs(doc, policy) {
  const fail = (d) => { throw new Refusal('fixtures_invalid', d); };
  if (!doc || doc.schema !== 'T06-map-constructor-authored-1' || !Array.isArray(doc.cases) || doc.cases.length === 0) fail('schema');
  const ids = new Set();
  return doc.cases.map((c, i) => {
    if (!c || typeof c.id !== 'string' || !/^[A-Za-z0-9._-]{1,128}$/.test(c.id) || ids.has(c.id)) fail(`case ${i} id`);
    ids.add(c.id);
    if (!KINDS.includes(c.kind)) fail(`case ${c.id} kind`);
    if (typeof c.hex !== 'string' || !/^(?:[0-9a-f]{2})*$/.test(c.hex) || c.hex.length / 2 > policy.max_body_bytes) fail(`case ${c.id} hex`);
    const bytes = Buffer.from(c.hex, 'hex');
    return { id: c.id, kind: c.kind, complete_sha256: sha256(bytes), input_bytes: bytes.length,
      header_version_bytes: bytes.length >= 6 ? [bytes[4], bytes[5]] : null, fixture_bytes: bytes, expected: c.expected };
  });
}

export function manifestJobs(doc, profile) {
  const fail = (d) => { throw new Refusal('manifest_invalid', d); };
  if (!doc || doc.schema !== 'T06-map-constructor-input-1' || !Array.isArray(doc.jobs) || !Array.isArray(doc.roots)) fail('schema');
  const c = profile.counts || {};
  if (doc.jobs.length !== c.jobs || doc.roots.length !== c.roots) fail('job/root counts differ from profile');
  const byId = new Map(); const keys = new Set();
  const jobs = doc.jobs.map((j, i) => {
    if (!j || typeof j.job_id !== 'string' || !/^[A-Za-z0-9._:-]{1,128}$/.test(j.job_id) || byId.has(j.job_id)) fail(`job ${i} id`);
    if (!KINDS.includes(j.kind) || !isHex64(j.complete_sha256) || !Number.isSafeInteger(j.bytes) || j.bytes < 0) fail(`job ${j.job_id} fields`);
    if (typeof j.body_path !== 'string') fail(`job ${j.job_id} body_path`);
    const key = `${j.kind}:${j.complete_sha256}`;
    if (keys.has(key)) fail(`job ${j.job_id} duplicate (kind,sha)`);
    keys.add(key);
    const vb = j.header && j.header.version_bytes;
    const job = { id: j.job_id, kind: j.kind, complete_sha256: j.complete_sha256, input_bytes: j.bytes,
      header_version_bytes: Array.isArray(vb) && vb.length === 2 && vb.every((n) => Number.isInteger(n) && n >= 0 && n < 256) ? [vb[0], vb[1]] : null,
      body_path: j.body_path };
    byId.set(j.job_id, job);
    return job;
  });
  let refs = 0;
  for (const r of doc.roots) {
    if (!r || !r.edges || typeof r.edges !== 'object') fail('root edges');
    for (const kind of KINDS) {
      const e = r.edges[kind];
      if (!e || typeof e !== 'object' || !('job_id' in e)) fail(`root ${r.ordinal} edge ${kind}`);
      if (e.job_id === null) continue;
      const job = byId.get(e.job_id);
      if (!job || job.kind !== kind) fail(`root ${r.ordinal} edge ${kind} references unknown job`);
      refs++;
    }
  }
  if (refs !== c.edge_references) fail('edge reference count differs from profile');
  return jobs;
}

// Read one retained body under input-root with exact pins (corpus mode only).
export function readJobBody(inputRoot, job, policy) {
  const abs = safeJoin(inputRoot, job.body_path, 'body_path');
  if (job.input_bytes > policy.max_body_bytes) throw new Refusal('size_limit', 'body exceeds max_body_bytes');
  return readPinnedFile(abs, { label: 'body', maxBytes: policy.max_body_bytes, expectBytes: job.input_bytes, expectSha: job.complete_sha256 });
}

function baseRow(job) {
  return { id: job.id, kind: job.kind, complete_sha256: job.complete_sha256, input_bytes: job.input_bytes,
    header_version_bytes: job.header_version_bytes };
}
export function unattemptedRow(job, reason) {
  return { ...baseRow(job), outcome: 'unattempted', reason, constructor_returned: null, elapsed_ms: 0,
    worker_started: false, cleanup: { exit_observed: null } };
}

// Run one job in a fresh worker; resolves only after exit is observed or cleanup is declared unverified.
export function runWorkerJob(job, bytes, ctx) {
  const { policy, sources, summaryText, runDeadline, rss } = ctx;
  return new Promise((resolve) => {
    const t0 = performance.now();
    const jobDeadline = Math.min(Date.now() + policy.job_timeout_ms, runDeadline);
    const ab = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
    let worker;
    const st = { phase: 'starting', result: null, refusal: null, error: null, exitCode: null, exited: false,
      terminated: false, stderr: '', settled: false, timers: [] };
    const finish = (exitObserved) => {
      if (st.settled) return;
      st.settled = true;
      st.timers.forEach(clearTimeout);
      rss.active = null;
      resolve(buildRow(job, st, exitObserved, performance.now() - t0, jobDeadline === runDeadline));
    };
    const terminate = () => {
      if (st.terminated || st.exited) return;
      st.terminated = true;
      worker.terminate().catch(() => {});
      st.timers.push(setTimeout(() => finish(false), CLEANUP_WAIT_MS));
    };
    try {
      worker = new Worker(WORKER_URL, {
        workerData: { role: 't06-constructor-job', kind: job.kind, body: ab, sources, summary_text: summaryText,
          policy, deadline_epoch_ms: jobDeadline },
        transferList: [ab], execArgv: ['--experimental-vm-modules', '--no-warnings'], env: {}, stdout: true, stderr: true,
        resourceLimits: { maxOldGenerationSizeMb: policy.worker_heap_mib }
      });
    } catch (error) {
      st.error = error; st.phase = 'not_started';
      resolve({ ...baseRow(job), outcome: 'environment_failure', constructor_returned: false, elapsed_ms: performance.now() - t0,
        worker_started: false, cleanup: { exit_observed: null }, exception: exceptionInfo(error, 'worker_start', policy) });
      return;
    }
    worker.stdout.resume();
    worker.stderr.on('data', (d) => { if (st.stderr.length < policy.max_job_log_bytes) st.stderr += String(d).slice(0, policy.max_job_log_bytes); });
    worker.on('message', (m) => {
      if (!m || typeof m !== 'object') return;
      if (m.type === 'phase') st.phase = m.phase;
      else if (m.type === 'result' && !st.result) {
        st.result = m;
        st.timers.push(setTimeout(terminate, EXIT_GRACE_MS));
      }
    });
    worker.on('error', (error) => { st.error = error; });
    worker.on('exit', (code) => { st.exited = true; st.exitCode = code; finish(true); });
    rss.active = () => { if (!st.result && !st.refusal) { st.refusal = { outcome: 'resource_refusal', reason: 'rss_limit' }; terminate(); } };
    rss.sample();
    const wall = Math.max(0, jobDeadline - Date.now());
    st.timers.push(setTimeout(() => {
      if (!st.result && !st.refusal) st.refusal = { outcome: 'timeout', reason: jobDeadline === runDeadline ? 'run_deadline' : 'job_timeout' };
      terminate();
    }, wall));
  });
}

function exceptionInfo(error, phase, policy) {
  const message = String(error && error.message || error);
  return { phase, name: String(error && error.name || 'Error').slice(0, 64), message: message.slice(0, policy.max_exception_message_chars),
    message_truncated: message.length > policy.max_exception_message_chars, code: error && typeof error.code === 'string' ? error.code : null };
}

function buildRow(job, st, exitObserved, elapsed, deadlineIsRun) {
  const row = { ...baseRow(job) };
  const r = st.result;
  let outcome, returned;
  if (r) { outcome = r.outcome; returned = r.constructor_returned; }
  else if (st.refusal) outcome = st.refusal.outcome;
  else if (st.error && st.error.code === 'ERR_WORKER_OUT_OF_MEMORY') outcome = 'resource_refusal';
  else outcome = 'worker_error';
  if (!OUTCOMES.includes(outcome)) outcome = 'worker_error';
  if (returned === undefined) returned = st.phase === 'summary' ? true : st.phase === 'constructor' ? null : false;
  Object.assign(row, { outcome, constructor_returned: returned, elapsed_ms: Math.round(elapsed * 1000) / 1000, worker_started: true,
    phase_reached: st.phase,
    cleanup: { exit_observed: exitObserved, exit_code: st.exitCode, terminated_by_parent: st.terminated } });
  if (!exitObserved) row.cleanup.uncertainty = 'worker exit was not observed within the cleanup wait';
  if (!r && st.refusal) row.reason = st.refusal.reason;
  if (!r && !st.refusal && st.error) row.exception = { phase: 'worker', name: String(st.error.name).slice(0, 64),
    message: String(st.error.message).slice(0, 512), code: typeof st.error.code === 'string' ? st.error.code : null };
  if (r) {
    if (r.exception) row.exception = r.exception;
    if (r.constructor_ms !== undefined) row.constructor_ms = Math.round(r.constructor_ms * 1000) / 1000;
    if (r.summary_json_bytes !== undefined) row.summary_json_bytes = r.summary_json_bytes;
    if (r.limit) row.limit = r.limit;
    if (r.dynamic_imports && r.dynamic_imports.length) row.dynamic_import_refusals = r.dynamic_imports.length;
    if (outcome === 'timeout') row.reason = 'vm_timeout';
  }
  const log = [r && r.log && r.log.text, st.stderr].filter(Boolean).join('\n');
  row._log = log; row._log_dropped = r && r.log ? r.log.dropped : 0;
  row._summary_json = outcome === 'returned' && r ? r.summary_json : null;
  void deadlineIsRun;
  return row;
}

function deepEqual(a, b) {
  if (a === b) return true;
  if (typeof a !== typeof b || a === null || b === null || typeof a !== 'object') return false;
  if (Array.isArray(a) !== Array.isArray(b)) return false;
  const ka = Object.keys(a), kb = Object.keys(b);
  return ka.length === kb.length && ka.every((k) => Object.prototype.hasOwnProperty.call(b, k) && deepEqual(a[k], b[k]));
}

export function compareAuthored(job, row) {
  const e = job.expected || {};
  if (row.outcome !== e.outcome) return false;
  if (e.outcome === 'returned') return deepEqual(row.summary, e.summary);
  if (e.outcome === 'constructor_exception') return !!row.exception && row.exception.name === e.exception_name;
  return true;
}

export function corpusRoots(manifest, outcomeById) {
  return manifest.roots.map((root) => {
    const copy = structuredClone(root);
    for (const kind of KINDS) {
      const e = copy.edges[kind];
      e.parse_outcome = e.job_id === null ? 'unavailable_from_observation' : (outcomeById.get(e.job_id) || 'unattempted');
    }
    return copy;
  });
}

class Output {
  constructor(dir, policy) {
    this.dir = dir; this.policy = policy;
    this.jobsPath = path.join(dir, 'jobs.jsonl');
    this.fd = fs.openSync(this.jobsPath, 'wx', 0o600);
    fs.fchmodSync(this.fd, 0o600);
    this.hash = crypto.createHash('sha256'); this.bytes = 0; this.records = 0; this.logBytes = 0;
  }
  write(line) {
    const buf = Buffer.from(line + '\n', 'utf8');
    let off = 0;
    while (off < buf.length) off += fs.writeSync(this.fd, buf, off, buf.length - off);
    this.hash.update(buf); this.bytes += buf.length; this.records++;
  }
  close() { fs.fsyncSync(this.fd); fs.closeSync(this.fd); }
}

function serializeRow(row, out, includeLog) {
  const { _log, _log_dropped, _summary_json, ...clean } = row;
  if (includeLog && _log) {
    const limit = Math.min(out.policy.max_job_log_bytes, out.policy.max_total_log_bytes - out.logBytes);
    const buf = Buffer.from(_log, 'utf8');
    if (limit <= 0) clean.log_omitted = true;
    else {
      const text = buf.subarray(0, limit).toString('utf8').replace(/�$/, '');
      clean.log = text; clean.log_truncated = buf.length > limit || _log_dropped > 0;
      out.logBytes += Buffer.byteLength(text, 'utf8');
    }
  } else if (_log) clean.log_omitted = true;
  let line = JSON.stringify(clean);
  if (_summary_json) line = line.slice(0, -1) + ',"summary":' + _summary_json + '}';
  return line;
}

function writeExclusive(file, text) {
  const fd = fs.openSync(file, 'wx', 0o600);
  try { fs.fchmodSync(fd, 0o600); fs.writeSync(fd, text); fs.fsyncSync(fd); } finally { fs.closeSync(fd); }
}

export async function main(argv, { stdout = process.stdout } = {}) {
  const say = (o) => stdout.write(JSON.stringify(o).slice(0, 4096) + '\n');
  let opts, prepared;
  try {
    opts = parseArgs(argv);
    prepared = prepare(opts);
  } catch (error) {
    if (!(error instanceof Refusal)) throw error;
    say({ status: 'refused', reason: error.reason, detail: error.message.slice(0, 300), output_created: false });
    return 2;
  }
  return run(prepared, say);
}

function prepare(opts) {
  if (typeof vm.SourceTextModule !== 'function') throw new Refusal('environment', 'run node with --experimental-vm-modules');
  const inputRoot = path.resolve(opts.input_root);
  const clientSource = path.resolve(opts.client_source);
  const output = path.resolve(opts.output);
  assertNoLinks(inputRoot, 'input-root'); assertNoLinks(clientSource, 'client-source');
  if (!fs.statSync(inputRoot).isDirectory() || !fs.statSync(clientSource).isDirectory()) throw new Refusal('special_file_refused', 'roots must be directories');
  if (fs.existsSync(output) || isLink(output)) throw new Refusal('output_exists', 'output path already exists');
  if (output === clientSource || output.startsWith(clientSource + path.sep)) throw new Refusal('path_refused', 'output inside client-source');
  const profileFile = readPinnedFile(path.resolve(opts.profile), { label: 'profile', maxBytes: PROFILE_MAX_BYTES, expectSha: PROFILE_SHA256 });
  const profile = validateProfile(readJson(profileFile.buffer, 'profile'));
  const pins = [{ role: 'profile', path: path.resolve(opts.profile), bytes: profileFile.bytes, sha256: profileFile.sha256, identity: profileFile.identity }];
  const summaryAbs = safeJoin(REPO_ROOT, profile.summary.path, 'summary');
  const summary = readPinnedFile(summaryAbs, { label: 'summary', maxBytes: profile.summary.bytes, expectBytes: profile.summary.bytes, expectSha: profile.summary.sha256 });
  pins.push({ role: 'summary', path: summaryAbs, bytes: summary.bytes, sha256: summary.sha256, identity: summary.identity });
  const sources = {}; const sourcePins = [];
  for (const key of MODULE_KEYS) {
    const pin = profile.sources[key];
    const abs = safeJoin(clientSource, key, `source ${key}`);
    const f = readPinnedFile(abs, { label: `source ${key}`, maxBytes: pin.bytes, expectBytes: pin.bytes, expectSha: pin.sha256 });
    sources[key] = f.buffer.toString('utf8');
    sourcePins.push({ path: key, bytes: f.bytes, sha256: f.sha256, verified: true, identity: f.identity, abs });
  }
  const p = profile.policy;
  let mode, inputFile, inputAbs, jobs, manifest = null;
  if (opts.fixtures) {
    mode = 'fixtures';
    inputAbs = path.resolve(opts.fixtures);
    inputFile = readPinnedFile(inputAbs, { label: 'fixtures', maxBytes: p.max_fixture_bytes, expectBytes: profile.authored.bytes, expectSha: profile.authored.sha256 });
    jobs = fixtureJobs(readJson(inputFile.buffer, 'fixtures'), p);
  } else {
    mode = 'corpus';
    inputAbs = path.resolve(opts.manifest);
    if (inputAbs !== safeJoin(inputRoot, profile.manifest.path, 'manifest')) throw new Refusal('path_refused', 'manifest is not the profile manifest under input-root');
    inputFile = readPinnedFile(inputAbs, { label: 'manifest', maxBytes: p.max_manifest_bytes, expectBytes: profile.manifest.bytes, expectSha: profile.manifest.sha256 });
    manifest = readJson(inputFile.buffer, 'manifest');
    jobs = manifestJobs(manifest, profile);
  }
  pins.push({ role: mode === 'fixtures' ? 'fixtures' : 'manifest', path: inputAbs, bytes: inputFile.bytes, sha256: inputFile.sha256, identity: inputFile.identity });
  const policy = effectivePolicy(p, opts.overrides, jobs.length);
  // Reserve accounting room for every job before any execution.
  const reserve = jobs.map((j) => Buffer.byteLength(JSON.stringify(unattemptedRow(j, 'output_limit'))) + 1 + ROW_SLACK_BYTES);
  const suffix = new Array(jobs.length + 1).fill(0);
  for (let i = jobs.length - 1; i >= 0; i--) suffix[i] = suffix[i + 1] + reserve[i];
  if (suffix[0] > policy.max_jobs_jsonl_bytes) throw new Refusal('output_budget', 'jobs.jsonl cannot account for every job');
  return { opts, inputRoot, clientSource, output, profile, profileSha: profileFile.sha256, summary, sources, sourcePins, pins, mode,
    inputAbs, inputFile, jobs, manifest, policy, suffix, summaryText: summary.buffer.toString('utf8') };
}

function isLink(p) { try { return fs.lstatSync(p).isSymbolicLink(); } catch { return false; } }

function recheckIdentity(pins) {
  return pins.every((pin) => {
    try { return sameIdentity(pin.identity, identityOf(fs.lstatSync(pin.abs || pin.path, { bigint: true }))); } catch { return false; }
  });
}

async function run(P, say) {
  const { policy, jobs, mode } = P;
  fs.mkdirSync(path.dirname(P.output), { recursive: true, mode: 0o700 });
  try { fs.mkdirSync(P.output, { mode: 0o700 }); } catch (e) {
    say({ status: 'refused', reason: 'output_exists', detail: String(e.code), output_created: false });
    return 2;
  }
  fs.chmodSync(P.output, 0o700);
  const out = new Output(P.output, policy);
  const started = Date.now(); const t0 = performance.now();
  const runDeadline = started + policy.run_timeout_ms;
  const rss = { samples: 0, peak: process.memoryUsage.rss(), over: 0, active: null, first_ms: null, last_ms: null };
  // Sampled at every worker start and then every rss_sample_ms.
  rss.sample = () => {
    const v = process.memoryUsage.rss();
    rss.samples++; rss.peak = Math.max(rss.peak, v);
    const ms = performance.now() - t0; if (rss.first_ms === null) rss.first_ms = ms; rss.last_ms = ms;
    if (v > policy.rss_limit_bytes) { rss.over++; if (rss.active) rss.active(); }
  };
  const sampler = setInterval(rss.sample, policy.rss_sample_ms);
  const counts = Object.fromEntries(OUTCOMES.map((o) => [o, 0]));
  const outcomeById = new Map();
  const cleanup = { workers_started: 0, exits_observed: 0, unverified: [], halted: null };
  const authored = { matched: 0, mismatched: [] };
  let halt = null; let incomplete = false;
  const ctx = { policy, sources: P.sources, summaryText: P.summaryText, runDeadline, rss };
  for (let i = 0; i < jobs.length; i++) {
    const job = jobs[i];
    let row;
    if (halt) row = unattemptedRow(job, halt);
    else if (i >= policy.max_jobs) row = unattemptedRow(job, 'max_jobs');
    else if (Date.now() >= runDeadline) { halt = 'run_deadline'; row = unattemptedRow(job, halt); }
    else {
      let bytes = null;
      if (mode === 'fixtures') bytes = job.fixture_bytes;
      else {
        try { bytes = readJobBody(P.inputRoot, job, policy).buffer; } catch (error) {
          if (!(error instanceof Refusal)) throw error;
          row = { ...baseRow(job), outcome: 'input_refused', reason: error.reason, constructor_returned: false, elapsed_ms: 0,
            worker_started: false, cleanup: { exit_observed: null }, exception: { phase: 'input', name: 'Refusal', message: error.message.slice(0, policy.max_exception_message_chars) } };
        }
      }
      if (!row) {
        row = await runWorkerJob(job, bytes, ctx);
        if (row.worker_started) {
          cleanup.workers_started++;
          if (row.cleanup.exit_observed === true) cleanup.exits_observed++;
          else { cleanup.unverified.push(job.id); halt = 'cleanup_unverified'; }
        }
        if (row.outcome === 'timeout' && row.reason === 'run_deadline') halt = halt || 'run_deadline';
      }
    }
    let line = serializeRow(row, out, true);
    if (out.bytes + Buffer.byteLength(line) + 1 + P.suffix[i + 1] > policy.max_jobs_jsonl_bytes) {
      // No room for the full row: keep explicit accounting without the summary/log.
      row = { ...row, outcome: row.outcome === 'returned' ? 'summary_limit' : row.outcome, limit: 'max_jobs_jsonl_bytes', _summary_json: null, _log: '' };
      line = serializeRow(row, out, false);
      halt = halt || 'output_limit';
    }
    if (mode === 'fixtures' && row.outcome !== 'unattempted') {
      const parsed = row._summary_json ? JSON.parse(row._summary_json) : undefined;
      if (compareAuthored(job, { ...row, summary: parsed })) authored.matched++; else authored.mismatched.push(job.id);
    }
    out.write(line);
    counts[row.outcome]++;
    outcomeById.set(job.id, row.outcome);
    if (!['returned', 'constructor_exception'].includes(row.outcome)) incomplete = true;
  }
  clearInterval(sampler);
  out.close();
  cleanup.halted = halt;
  const identityUnchanged = recheckIdentity([...P.pins, ...P.sourcePins]);
  const report = {
    schema: 'T06-map-constructor-report-1', task: 'T06.003.003.003', mode,
    input: { path: P.inputAbs, bytes: P.inputFile.bytes, sha256: P.inputFile.sha256 },
    profile_sha256: P.profileSha, summary_sha256: P.summary.sha256,
    client_source: { root: P.clientSource, profile_revision: P.profile.client_source_revision, revision_checked: false,
      sources: P.sourcePins.map(({ path: p, bytes, sha256: s, verified }) => ({ path: p, bytes, sha256: s, verified })) },
    pinned_inputs_identity_unchanged_after_run: identityUnchanged,
    effective_policy: policy,
    counts: { expected_jobs: jobs.length, records: out.records, attempted: jobs.length - counts.unattempted, job_outcomes: counts },
    rss_sampling: { sample_ms: policy.rss_sample_ms, samples: rss.samples, peak_rss_bytes: rss.peak, limit_bytes: policy.rss_limit_bytes,
      over_limit_samples: rss.over, scope: 'whole parent process including worker threads; sampled, not a hard bound' },
    cleanup: { ...cleanup, verified: cleanup.unverified.length === 0 && cleanup.workers_started === cleanup.exits_observed },
    elapsed_ms: Math.round(performance.now() - t0),
    jobs_file: { path: 'jobs.jsonl', bytes: out.bytes, sha256: out.hash.digest('hex'), records: out.records },
    logs: { bytes: out.logBytes, limit_bytes: policy.max_total_log_bytes },
    roots: [],
    limitations: P.profile.limits
  };
  if (mode === 'fixtures') report.authored_comparison = authored;
  else {
    const m = P.manifest;
    report.roots = corpusRoots(m, outcomeById);
    report.input_manifest = { schema: m.schema, status: m.status, counts: m.counts, inputs: m.inputs, overlay: m.overlay,
      job_order: m.job_order, remaining_gap_root_ordinals: m.remaining_gap_root_ordinals, qualification_limits: m.qualification_limits,
      parser_execution_performed_in_input: m.parser_execution_performed };
  }
  if (!identityUnchanged) incomplete = true;
  let text = JSON.stringify(report, null, 1);
  if (Buffer.byteLength(text) > policy.max_report_json_bytes) {
    incomplete = true;
    const omitted = report.roots.length;
    report.roots = []; report.report_limit = { limit: 'max_report_json_bytes', roots_omitted: omitted, complete: false };
    text = JSON.stringify(report);
  }
  writeExclusive(path.join(P.output, 'report.json'), text);
  const exitCode = halt || incomplete || !report.cleanup.verified ? 1 : 0;
  say({ status: exitCode === 0 ? 'complete' : 'incomplete', mode, exit_code: exitCode, expected_jobs: jobs.length,
    job_outcomes: Object.fromEntries(Object.entries(counts).filter(([, v]) => v)), halted: halt,
    cleanup_verified: report.cleanup.verified, ...(mode === 'fixtures' ? { authored_matched: authored.matched } : {}) });
  return exitCode;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main(process.argv.slice(2)).then((code) => { process.exitCode = code; }, (error) => {
    process.stdout.write(JSON.stringify({ status: 'error', detail: String(error && error.message).slice(0, 300) }) + '\n');
    process.exitCode = 3;
  });
}
