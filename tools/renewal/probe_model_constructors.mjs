#!/usr/bin/env node
// T06.003.003.006 unchanged Model constructor runner (parent/CLI).
// Observes new Model(buffer) and the frozen summarizeModel projection.
// A constructor return is not rendering, nested fetch, or playable coverage.
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { performance } from 'node:perf_hooks';
import { StringDecoder } from 'node:string_decoder';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { Worker } from 'node:worker_threads';
import { MODULE_KEYS, ROLE, RULE_KEYS } from './model_constructor_worker.mjs';

export const PROFILE_SHA256 = '9ad903297104cd6f9a03d74196d5db7a4091ee07da4d2b73b4b4f61027b2140d';
export const PROFILE_BYTES = 4855;
const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, '..', '..');
const WORKER_URL = pathToFileURL(path.join(HERE, 'model_constructor_worker.mjs'));
const OWN_SOURCES = ['probe_model_constructors.mjs', 'model_constructor_worker.mjs'];
const OVERRIDES = {
  '--job-timeout-ms': 'job_timeout_ms',
  '--run-timeout-ms': 'run_timeout_ms',
  '--rss-limit-bytes': 'rss_limit_bytes',
  '--max-job-json-bytes': 'max_job_json_bytes'
};
const ROW_SLACK_BYTES = 4096;
export const OUTCOMES = ['returned', 'constructor_exception', 'summary_error', 'summary_limit', 'input_refused',
  'environment_failure', 'timeout', 'resource_refusal', 'worker_error', 'unattempted'];

// In-process seams for tests. The CLI never sets these.
export const hooks = {
  createWorker: null,
  beforeIdentityRecheck: null,
  beforeRepresentativeReread: null
};

export class Refusal extends Error {
  constructor(reason, detail) {
    super(`${reason}${detail ? `: ${detail}` : ''}`);
    this.reason = reason;
  }
}

const sha256 = (buf) => crypto.createHash('sha256').update(buf).digest('hex');
const isHex64 = (value) => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value);
const decimal = (value) => typeof value === 'string' && /^[0-9]+$/.test(value);

export function parseArgs(argv) {
  const opts = { overrides: {} };
  const single = ['--input-root', '--client-source', '--profile', '--fixtures', '--manifest', '--output', '--max-jobs', ...Object.keys(OVERRIDES)];
  const seen = new Set();
  for (let i = 0; i < argv.length; i++) {
    const flag = argv[i];
    if (!single.includes(flag)) throw new Refusal('usage', `unknown argument ${String(flag).slice(0, 40)}`);
    if (seen.has(flag)) throw new Refusal('usage', `${flag} repeated`);
    seen.add(flag);
    const value = argv[++i];
    if (value === undefined || String(value).startsWith('--')) throw new Refusal('usage', `${flag} needs a value`);
    if (OVERRIDES[flag] || flag === '--max-jobs') {
      if (!/^\d{1,16}$/.test(value)) throw new Refusal('usage', `${flag} must be a non-negative integer`);
      opts.overrides[OVERRIDES[flag] || 'max_jobs'] = Number(value);
    } else opts[flag.slice(2).replace(/-/g, '_')] = value;
  }
  for (const key of ['input_root', 'client_source', 'profile', 'output']) {
    if (!opts[key]) throw new Refusal('usage', `--${key.replace(/_/g, '-')} is required`);
  }
  if (!!opts.fixtures === !!opts.manifest) throw new Refusal('usage', 'exactly one of --fixtures or --manifest is required');
  return opts;
}

// Lower-only. max_jobs may be 0. Nothing else may exceed the profile or be 0.
export function effectivePolicy(profilePolicy, overrides, totalJobs) {
  const policy = { ...profilePolicy, max_jobs: totalJobs };
  for (const [key, value] of Object.entries(overrides)) {
    if (key === 'max_jobs') {
      if (value > totalJobs) throw new Refusal('policy_increase', `max_jobs ${value} exceeds ${totalJobs}`);
    } else if (!(value >= 1)) throw new Refusal('policy_invalid', `${key} must be >= 1`);
    else if (value > profilePolicy[key]) throw new Refusal('policy_increase', `${key} ${value} exceeds profile ${profilePolicy[key]}`);
    policy[key] = value;
  }
  return policy;
}

export function assertNoLinks(abs, label) {
  let real;
  try { real = fs.realpathSync.native(abs); } catch (error) { throw new Refusal('missing_input', `${label} (${error.code || 'stat'})`); }
  if (real !== abs) throw new Refusal('symlink_refused', label);
}

export function identityOf(st) {
  return {
    dev: String(st.dev),
    ino: String(st.ino),
    size: String(st.size),
    mtime_ns: String(st.mtimeNs),
    ctime_ns: String(st.ctimeNs)
  };
}
const sameIdentity = (a, b) => a && b && ['dev', 'ino', 'size', 'mtime_ns', 'ctime_ns'].every((key) => a[key] === b[key]);

export function readPinnedFile(abs, { label, maxBytes, expectBytes, expectSha, expectIdentity, requireMode, requireNlink } = {}) {
  assertNoLinks(abs, label);
  const before = fs.lstatSync(abs, { bigint: true });
  if (before.isSymbolicLink()) throw new Refusal('symlink_refused', label);
  if (!before.isFile()) throw new Refusal('special_file_refused', label);
  if (before.nlink !== 1n) throw new Refusal('link_refused', label);
  if (requireMode !== undefined && Number(before.mode & 0o777n) !== requireMode) throw new Refusal('mode_refused', label);
  if (requireNlink !== undefined && before.nlink !== BigInt(requireNlink)) throw new Refusal('link_refused', label);
  if (before.size > BigInt(maxBytes)) throw new Refusal('size_limit', label);
  if (expectBytes !== undefined && before.size !== BigInt(expectBytes)) throw new Refusal('pin_mismatch', `${label} size`);
  const flags = fs.constants.O_RDONLY | fs.constants.O_NONBLOCK | (fs.constants.O_NOFOLLOW || 0);
  const fd = fs.openSync(abs, flags);
  let opened;
  let after;
  let buf;
  try {
    opened = fs.fstatSync(fd, { bigint: true });
    if (!opened.isFile() || opened.nlink !== 1n || !sameIdentity(identityOf(opened), identityOf(before))) {
      throw new Refusal('identity_changed', label);
    }
    if (opened.size > BigInt(maxBytes)) throw new Refusal('size_limit', label);
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
  if (expectIdentity && !sameIdentity(id0, expectIdentity)) throw new Refusal('identity_changed', label);
  const digest = sha256(buf);
  if (expectSha !== undefined && digest !== expectSha) throw new Refusal('pin_mismatch', `${label} sha256`);
  return { buffer: buf, bytes: buf.length, sha256: digest, identity: id0 };
}

export function safeJoin(root, rel, label) {
  if (typeof rel !== 'string' || rel.length === 0 || rel.length > 4096 || rel.includes('\0') || rel.includes('\\') ||
      path.isAbsolute(rel) || rel.split('/').some((part) => part === '..' || part === '.' || part === '')) {
    throw new Refusal('path_refused', label);
  }
  const abs = path.resolve(root, rel);
  if (abs !== root && !abs.startsWith(root + path.sep)) throw new Refusal('path_refused', label);
  return abs;
}

function readJson(buffer, label) {
  try { return JSON.parse(buffer.toString('utf8')); } catch { throw new Refusal('invalid_json', label); }
}

function assertDecimalIdentity(id, label) {
  if (!id || typeof id !== 'object') throw new Refusal('identity_precision', label);
  for (const key of ['dev', 'ino', 'size', 'mtime_ns', 'ctime_ns']) {
    if (!decimal(id[key])) throw new Refusal('identity_precision', `${label} ${key}`);
  }
}

export function validateProfile(profile) {
  const fail = (detail) => { throw new Refusal('profile_invalid', detail); };
  if (!profile || profile.schema !== 'T06-model-constructor-profile-1' || profile.task !== 'T06.003.003.006') fail('schema');
  const keys = Object.keys(profile.sources || {});
  if (keys.length !== MODULE_KEYS.length || MODULE_KEYS.some((key) => !keys.includes(key))) fail('sources');
  for (const key of MODULE_KEYS) {
    const source = profile.sources[key];
    if (!source || !Number.isSafeInteger(source.bytes) || source.bytes < 0 || !isHex64(source.sha256)) fail(key);
  }
  const rules = Object.keys(profile.rule_sources || {});
  if (rules.length !== RULE_KEYS.length || RULE_KEYS.some((key) => !rules.includes(key))) fail('rule_sources');
  for (const key of RULE_KEYS) {
    const source = profile.rule_sources[key];
    if (!source || !Number.isSafeInteger(source.bytes) || !isHex64(source.sha256)) fail(key);
  }
  for (const key of ['summary', 'authored', 'manifest']) {
    const source = profile[key];
    if (!source || typeof source.path !== 'string' || !Number.isSafeInteger(source.bytes) || !isHex64(source.sha256)) fail(key);
  }
  const counts = profile.counts || {};
  for (const key of ['model_targets', 'constructor_jobs', 'model_referrers', 'roots', 'remaining_core_gap_roots', 'all_catalog_referrers', 'target_body_bytes', 'distinct_job_bytes']) {
    if (!Number.isSafeInteger(counts[key]) || counts[key] < 0) fail(`counts ${key}`);
  }
  const policy = profile.policy || {};
  for (const key of ['max_body_bytes', 'max_manifest_bytes', 'max_fixture_bytes', 'max_availability_report_bytes', 'max_catalog_bytes',
    'worker_heap_mib', 'rss_limit_bytes', 'rss_sample_ms', 'job_timeout_ms', 'module_timeout_ms', 'constructor_timeout_ms',
    'run_timeout_ms', 'max_job_json_bytes', 'max_jobs_jsonl_bytes', 'max_report_json_bytes', 'max_job_log_bytes',
    'max_total_log_bytes', 'max_exception_message_chars', 'max_stdout_bytes', 'max_active_workers', 'result_exit_grace_ms', 'cleanup_wait_ms']) {
    if (!Number.isSafeInteger(policy[key]) || policy[key] < 1) fail(`policy ${key}`);
  }
  if (policy.max_active_workers !== 1) fail('max_active_workers');
  if (policy.worker_heap_mib !== 512 || policy.rss_limit_bytes !== 2147483648) fail('memory defaults');
  for (const avail of ['report', 'catalog', 'root_audit']) {
    const source = profile.availability && profile.availability[avail];
    if (!source || typeof source.path !== 'string' || !Number.isSafeInteger(source.bytes) || !isHex64(source.sha256)) fail(`availability ${avail}`);
  }
  return profile;
}

function deepEqual(a, b) {
  if (a === b) return true;
  if (typeof a !== typeof b || a === null || b === null || typeof a !== 'object') return false;
  if (Array.isArray(a) !== Array.isArray(b)) return false;
  const ka = Object.keys(a);
  const kb = Object.keys(b);
  return ka.length === kb.length && ka.every((key) => Object.prototype.hasOwnProperty.call(b, key) && deepEqual(a[key], b[key]));
}

export function fixtureJobs(doc, policy) {
  const fail = (detail) => { throw new Refusal('fixtures_invalid', detail); };
  if (!doc || doc.schema !== 'T06-model-constructor-authored-1' || doc.task !== 'T06.003.003.006' || !Array.isArray(doc.cases)) fail('schema');
  const ids = new Set();
  return doc.cases.map((entry, index) => {
    if (!entry || typeof entry.id !== 'string' || !/^[A-Za-z0-9._-]{1,128}$/.test(entry.id) || ids.has(entry.id)) fail(`case ${index} id`);
    ids.add(entry.id);
    if (entry.kind !== 'model') fail(`${entry.id} kind`);
    if (typeof entry.body_hex !== 'string' || !/^(?:[0-9a-f]{2})*$/.test(entry.body_hex) || entry.body_hex.length / 2 > policy.max_body_bytes) fail(`${entry.id} hex`);
    const bytes = Buffer.from(entry.body_hex, 'hex');
    const digest = sha256(bytes);
    if (entry.input_bytes !== bytes.length || entry.complete_sha256 !== digest) fail(`${entry.id} pin`);
    if (typeof entry.header_version_bytes !== 'string' || !/^(?:[0-9a-f]{2})*$/.test(entry.header_version_bytes)) fail(`${entry.id} header`);
    const header = Buffer.from(entry.header_version_bytes, 'hex');
    if (header.length > bytes.length || !bytes.subarray(0, header.length).equals(header)) fail(`${entry.id} header bytes`);
    if (entry.expected_outcome !== 'returned' && entry.expected_outcome !== 'constructor_exception') fail(`${entry.id} outcome`);
    if (entry.expected_outcome === 'returned' && (entry.expected_summary === undefined || entry.expected_summary === null)) fail(`${entry.id} summary`);
    if (entry.expected_outcome === 'constructor_exception' && typeof entry.expected_exception_name !== 'string') fail(`${entry.id} exception`);
    return {
      id: entry.id,
      job_id: entry.id,
      kind: 'model',
      complete_sha256: digest,
      input_bytes: bytes.length,
      header_version_bytes: entry.header_version_bytes,
      fixture_bytes: bytes,
      expected_outcome: entry.expected_outcome,
      expected_exception_name: entry.expected_exception_name,
      expected_summary: entry.expected_summary
    };
  });
}

export function compareAuthored(job, row) {
  if (row.outcome !== job.expected_outcome) return false;
  if (job.expected_outcome === 'returned') return deepEqual(row.summary, job.expected_summary);
  if (job.expected_outcome === 'constructor_exception') return !!row.exception && row.exception.name === job.expected_exception_name;
  return false;
}

function assertModelPremise(record) {
  const signature = record && record.signature;
  return !!record && record.attempted === true && record.http_status === 200 && record.stored &&
    record.stored.complete === true && record.stored.error === null && signature && signature.kind === 'model' &&
    signature.state === 'match' && typeof signature.prefix_hex === 'string' && /^[0-9a-f]+$/.test(signature.prefix_hex) &&
    Number.isSafeInteger(record.stored.bytes) && record.stored.bytes >= 0 && isHex64(record.stored.sha256) &&
    typeof record.stored.file === 'string' && /^[A-Za-z0-9._-]+$/.test(record.stored.file);
}

// Reproduce model admission from the availability report and catalog referrers.
// Header bytes stay observations. Filename, codec and extension are not keys.
export function selectModelTargets(report, catalog, audit, profile) {
  const fail = (detail) => { throw new Refusal('admission_discrepancy', detail); };
  if (!report || report.schema !== 'T06-map-dependency-observation-1' || report.task !== 'T06.003.003.005') fail('report schema');
  if (report.all_targets_attempted !== true || report.records_complete !== true || report.acquisition_and_cleanup_valid !== true) fail('report qualification');
  if (!catalog || catalog.schema !== 'T06-map-dependency-catalog-1' || !Array.isArray(catalog.targets) || !Array.isArray(catalog.roots)) fail('catalog schema');
  if (!audit || audit.schema !== 'root005-independent-actual-audit-1' || audit.availability_audit_qualified !== true) fail('audit schema');
  const counts = profile.counts;
  if (audit.target_records !== catalog.targets.length || audit.all_roots !== catalog.roots.length) fail('audit counts');
  if (audit.referrers !== counts.all_catalog_referrers || audit.remaining_core_gap_roots !== counts.remaining_core_gap_roots) fail('audit denominators');
  if (!audit.coverage || !audit.coverage.signature || audit.coverage.signature['model:match'] !== counts.model_targets) fail('model prefix count');
  if (!Array.isArray(report.targets) || report.targets.length !== catalog.targets.length) fail('target count');
  if (catalog.roots.length !== counts.roots) fail('root count');
  const bodyDirectory = profile.availability.report.path.split('/').slice(0, -1).join('/');
  let referrers = 0;
  const selected = [];
  for (let index = 0; index < report.targets.length; index++) {
    const record = report.targets[index];
    const catalogTarget = catalog.targets[index];
    if (!catalogTarget || catalogTarget.index !== index || record.target_index !== index) fail(`target ${index} index`);
    if (!Array.isArray(catalogTarget.referrers)) fail(`target ${index} referrers`);
    referrers += catalogTarget.referrers.length;
    if (record.wire_target !== `/${catalogTarget.http_path}`) fail(`target ${index} path`);
    if (!assertModelPremise(record)) continue;
    selected.push({
      model_ordinal: selected.length,
      target_index: index,
      request_index: record.request_index,
      report_pointer: `/targets/${index}`,
      catalog_pointer: `/targets/${index}`,
      http_path: catalogTarget.http_path,
      referrers: catalogTarget.referrers,
      body: {
        path: `${bodyDirectory}/${record.stored.file}`,
        bytes: record.stored.bytes,
        sha256: record.stored.sha256
      },
      signature_prefix: record.signature.prefix_hex
    });
  }
  if (selected.length !== counts.model_targets) fail(`selected ${selected.length} model targets`);
  if (referrers !== counts.all_catalog_referrers) fail('catalog referrers');
  const modelReferrers = selected.reduce((sum, target) => sum + target.referrers.length, 0);
  if (modelReferrers !== counts.model_referrers) fail('model referrers');
  if (counts.model_targets > 1 && !selected.some((target) => target.model_ordinal !== target.target_index)) {
    fail('model_ordinal collapsed onto target_index');
  }
  return selected;
}

export function groupModelJobs(targets, headerByOrdinal) {
  const groups = new Map();
  const jobs = [];
  for (const target of targets) {
    let job = groups.get(target.body.sha256);
    if (!job) {
      const header = headerByOrdinal.get(target.model_ordinal);
      job = {
        id: `model-${String(jobs.length).padStart(6, '0')}`,
        job_id: `model-${String(jobs.length).padStart(6, '0')}`,
        kind: 'model',
        representative_model_ordinal: target.model_ordinal,
        body_path: target.body.path,
        input_bytes: target.body.bytes,
        complete_sha256: target.body.sha256,
        header_version_bytes: header,
        target_model_ordinals: [target.model_ordinal]
      };
      groups.set(target.body.sha256, job);
      jobs.push(job);
    } else {
      if (job.input_bytes !== target.body.bytes) throw new Refusal('admission_discrepancy', 'shared length');
      job.target_model_ordinals.push(target.model_ordinal);
    }
    target.job_id = job.job_id;
  }
  return jobs;
}

// Full-hash every target body before dedup. readBody is called one target at a time.
export function admitModelCorpus({ manifest, report, catalog, audit, profile, readBody }) {
  const fail = (detail) => { throw new Refusal('admission_discrepancy', detail); };
  if (!manifest || manifest.schema !== 'T06-model-constructor-input-1' || manifest.task !== 'T06.003.003.006') fail('manifest schema');
  if (!deepEqual(manifest.counts, profile.counts)) fail('manifest counts');
  if (!Array.isArray(manifest.targets) || !Array.isArray(manifest.jobs) || !Array.isArray(manifest.roots)) fail('manifest shape');
  if (!deepEqual(manifest.roots, catalog.roots)) fail('roots');
  if (!deepEqual(manifest.remaining_gap_root_ordinals, catalog.remaining_gap_root_ordinals)) fail('gaps');
  if (!deepEqual(manifest.remaining_gap_root_ordinals, audit && report.catalog_refs && report.catalog_refs.gap_root_ordinals)) fail('gap ordinals');
  if (manifest.remaining_gap_root_ordinals.length !== profile.counts.remaining_core_gap_roots) fail('gap length');
  if (!deepEqual(manifest.prior_first_level_gaps, audit.first_level_gaps)) fail('prior gaps');
  const selected = selectModelTargets(report, catalog, audit, profile);
  if (manifest.targets.length !== selected.length) fail('manifest target length');
  const headerByOrdinal = new Map();
  const histogram = {};
  let targetBytes = 0;
  for (let i = 0; i < selected.length; i++) {
    const expected = selected[i];
    const declared = manifest.targets[i];
    assertDecimalIdentity(declared.body && declared.body.identity, `target ${i}`);
    if (declared.model_ordinal !== expected.model_ordinal || declared.target_index !== expected.target_index) fail(`target ${i} ordinal`);
    if (declared.http_path !== expected.http_path || declared.request_index !== expected.request_index) fail(`target ${i} binding`);
    if (declared.report_pointer !== expected.report_pointer || declared.catalog_pointer !== expected.catalog_pointer) fail(`target ${i} pointer`);
    if (!deepEqual(declared.referrers, expected.referrers)) fail(`target ${i} referrers`);
    if (declared.body.path !== expected.body.path || declared.body.bytes !== expected.body.bytes || declared.body.sha256 !== expected.body.sha256) {
      fail(`target ${i} body pin`);
    }
    const file = readBody(declared);
    if (!file || !Buffer.isBuffer(file.buffer) || file.buffer.length !== declared.body.bytes || sha256(file.buffer) !== declared.body.sha256) {
      fail(`target ${i} bytes`);
    }
    if (!sameIdentity(file.identity, declared.body.identity)) fail(`target ${i} identity`);
    const header = file.buffer.subarray(0, Math.min(6, file.buffer.length)).toString('hex');
    if (header !== expected.signature_prefix) fail(`target ${i} header observation`);
    headerByOrdinal.set(expected.model_ordinal, header);
    histogram[header] = (histogram[header] || 0) + 1;
    targetBytes += file.buffer.length;
    file.buffer = null;
  }
  if (targetBytes !== profile.counts.target_body_bytes) fail('target bytes');
  if (!deepEqual(histogram, profile.header_prefix_counts) || !deepEqual(histogram, manifest.header_prefix_counts)) fail('header histogram');
  const jobs = groupModelJobs(selected, headerByOrdinal);
  if (jobs.length !== profile.counts.constructor_jobs || manifest.jobs.length !== jobs.length) fail('job count');
  const seen = new Set();
  let distinctBytes = 0;
  const multi = [];
  for (let i = 0; i < jobs.length; i++) {
    const job = jobs[i];
    const declared = manifest.jobs[i];
    if (declared.job_id !== job.job_id || declared.representative_model_ordinal !== job.representative_model_ordinal) fail(`job ${i} id`);
    if (declared.body_path !== job.body_path || declared.input_bytes !== job.input_bytes || declared.complete_sha256 !== job.complete_sha256) fail(`job ${i} body`);
    if (declared.header_version_bytes !== job.header_version_bytes) fail(`job ${i} header`);
    if (!deepEqual(declared.target_model_ordinals, job.target_model_ordinals)) fail(`job ${i} members`);
    if (job.target_model_ordinals.length === 2) multi.push(job);
    else if (job.target_model_ordinals.length !== 1) fail(`job ${i} not a single or a pair`);
    distinctBytes += job.input_bytes;
    for (const ordinal of job.target_model_ordinals) {
      if (seen.has(ordinal)) fail(`target ${ordinal} duplicated`);
      seen.add(ordinal);
      if (manifest.targets[ordinal].job_id !== job.job_id) fail(`target ${ordinal} job link`);
    }
    if (job.target_model_ordinals[0] !== job.representative_model_ordinal) fail(`job ${i} representative`);
  }
  if (seen.size !== selected.length) fail('target membership');
  if (multi.length !== profile.counts.model_targets - profile.counts.constructor_jobs) fail('shared pairs');
  if (distinctBytes !== profile.counts.distinct_job_bytes) fail('distinct bytes');
  for (const job of multi) {
    const representative = manifest.targets[job.representative_model_ordinal];
    const first = readBody(representative);
    for (const ordinal of job.target_model_ordinals.slice(1)) {
      const member = readBody(manifest.targets[ordinal]);
      if (!first.buffer.equals(member.buffer)) fail(`pair ${job.job_id} bytes differ`);
      first.buffer = null;
      member.buffer = null;
    }
  }
  return jobs.map((job) => ({ ...job, kind: 'model' }));
}

function baseRow(job) {
  return {
    id: job.id,
    job_id: job.job_id,
    kind: 'model',
    input_bytes: job.input_bytes,
    complete_sha256: job.complete_sha256,
    header_version_bytes: job.header_version_bytes
  };
}

export function unattemptedRow(job, reason) {
  return {
    ...baseRow(job),
    outcome: 'unattempted',
    reason,
    constructor_returned: null,
    elapsed_ms: 0,
    worker_started: false,
    cleanup: { exit_observed: null, exit_code: null, terminated_by_parent: false }
  };
}

// Keep execution facts even when a physical output row cannot be published.
// Large summaries/logs stay in JSONL; their omission here is explicit.
function accountingRow(row) {
  const { summary, _summary_json, log, _log, _log_dropped_entries, _stdio_dropped_utf8_bytes, ...facts } = row;
  if (_log_dropped_entries) facts.log_dropped_entries = _log_dropped_entries;
  if (_stdio_dropped_utf8_bytes) facts.stdio_dropped_utf8_bytes = _stdio_dropped_utf8_bytes;
  if (_log_dropped_entries || _stdio_dropped_utf8_bytes) facts.log_truncated = true;
  return { ...facts, summary_payload_in_jsonl_only: true };
}

// Input is decoded text. Never split a code point or discard a literal U+FFFD.
function utf8Prefix(text, maxBytes) {
  const bytes = Buffer.from(text, 'utf8');
  let end = Math.min(bytes.length, Math.max(0, Math.floor(maxBytes)));
  if (end < bytes.length) while (end > 0 && (bytes[end] & 0xC0) === 0x80) end--;
  return { text: bytes.subarray(0, end).toString('utf8'), bytes: end, dropped: bytes.length - end };
}

function exceptionInfo(error, phase, policy) {
  const message = String(error && error.message || error);
  return {
    phase,
    name: String(error && error.name || 'Error').slice(0, 64),
    message: message.slice(0, policy.max_exception_message_chars),
    message_truncated: message.length > policy.max_exception_message_chars,
    code: error && typeof error.code === 'string' ? error.code : null
  };
}

function returnedFromPhase(phase) {
  if (phase === 'summary') return true;
  if (phase === 'constructor' || phase === 'module' || phase === 'starting') return null;
  return null;
}

export function runWorkerJob(job, bytes, ctx) {
  const { policy, sources, summaryText, runDeadline, rss } = ctx;
  return new Promise((resolve) => {
    const t0 = performance.now();
    const jobDeadline = Math.min(t0 + policy.job_timeout_ms, runDeadline);
    const budgetMs = Math.max(0, jobDeadline - performance.now());
    const deadlineReason = jobDeadline === runDeadline ? 'run_deadline' : 'job_timeout';
    const copy = Buffer.from(bytes);
    const ab = copy.buffer.slice(copy.byteOffset, copy.byteOffset + copy.byteLength);
    let worker;
    const st = {
      phase: 'starting', result: null, prior: null, refusal: null, error: null, exitCode: null,
      exited: false, terminated: false, stderr: '', stderrBytes: 0, stderrDropped: 0, stderrCapped: false, settled: false, timers: []
    };
    const appendDecoded = (text) => {
      if (!text || st.settled) return;
      if (st.stderrCapped) { st.stderrDropped += Buffer.byteLength(text); return; }
      const piece = utf8Prefix(text, policy.max_job_log_bytes - st.stderrBytes);
      st.stderr += piece.text;
      st.stderrBytes += piece.bytes;
      st.stderrDropped += piece.dropped;
      if (piece.dropped) st.stderrCapped = true;
    };
    // Each channel owns its decoder; bytes from different streams cannot form
    // one character. Settlement flushes pending bytes once without a new wait.
    const decoders = [new StringDecoder('utf8'), new StringDecoder('utf8')];
    const ended = [false, false];
    const flush = (index) => {
      if (ended[index]) return;
      ended[index] = true;
      appendDecoded(decoders[index].end());
    };
    const finish = (exitObserved) => {
      if (st.settled) return;
      flush(0); flush(1);
      st.settled = true;
      for (const timer of st.timers) clearTimeout(timer);
      rss.active = null;
      resolve(buildRow(job, st, exitObserved, performance.now() - t0));
    };
    const terminate = () => {
      if (st.terminated || st.exited) return;
      st.terminated = true;
      worker.terminate().catch(() => {});
      st.timers.push(setTimeout(() => finish(false), policy.cleanup_wait_ms));
    };
    if (budgetMs <= 0 || performance.now() >= runDeadline) {
      resolve({ ...unattemptedRow(job, 'run_deadline'), outcome: 'timeout', reason: 'run_deadline', worker_started: false });
      return;
    }
    try {
      const factory = ctx.workerFactory || hooks.createWorker || ((url, options) => new Worker(url, options));
      worker = factory(WORKER_URL, {
        workerData: {
          role: ROLE,
          body: ab,
          sources,
          summary_text: summaryText,
          policy,
          budget_ms: budgetMs
        },
        transferList: [ab],
        execArgv: ['--experimental-vm-modules', '--no-warnings'],
        env: {},
        stdout: true,
        stderr: true,
        resourceLimits: { maxOldGenerationSizeMb: policy.worker_heap_mib }
      });
    } catch (error) {
      resolve({
        ...baseRow(job),
        outcome: 'environment_failure',
        constructor_returned: null,
        elapsed_ms: Math.round((performance.now() - t0) * 1000) / 1000,
        worker_started: false,
        phase: 'not_started',
        cleanup: { exit_observed: null, exit_code: null, terminated_by_parent: false },
        exception: exceptionInfo(error, 'worker_start', policy)
      });
      return;
    }
    [worker.stdout, worker.stderr].forEach((stream, index) => {
      stream.on('data', (chunk) => {
        if (!ended[index] && !st.settled) appendDecoded(decoders[index].write(Buffer.from(chunk)));
      });
      stream.on('end', () => flush(index));
    });
    worker.stdout.resume();
    worker.stderr.resume();
    worker.on('message', (message) => {
      if (performance.now() >= jobDeadline || performance.now() >= runDeadline) {
        st.refusal ||= { outcome: 'timeout', reason: performance.now() >= runDeadline ? 'run_deadline' : deadlineReason };
        terminate();
        return;
      }
      if (!message || typeof message !== 'object') return;
      if (message.type === 'phase') st.phase = message.phase;
      else if (message.type === 'result' && !st.result && !st.refusal && !st.error) {
        st.result = message;
        st.timers.push(setTimeout(terminate, policy.result_exit_grace_ms));
      }
    });
    worker.on('error', (error) => {
      st.error = error;
      if (st.result) st.prior = { outcome: st.result.outcome, constructor_returned: st.result.constructor_returned };
      st.refusal ||= {
        outcome: error.code === 'ERR_WORKER_OUT_OF_MEMORY' ? 'resource_refusal' : 'worker_error',
        reason: 'worker_error'
      };
      terminate();
    });
    worker.on('exit', (code) => {
      st.exited = true;
      st.exitCode = code;
      // An exit event can arrive before an overdue timer gets its turn.
      if (!st.refusal && performance.now() >= jobDeadline) {
        if (st.result) st.prior = { outcome: st.result.outcome, constructor_returned: st.result.constructor_returned };
        st.refusal = { outcome: 'timeout', reason: performance.now() >= runDeadline ? 'run_deadline' : deadlineReason };
      }
      if (!st.refusal && st.result && (code !== 0 || st.terminated)) {
        st.prior = { outcome: st.result.outcome, constructor_returned: st.result.constructor_returned };
        st.refusal = { outcome: 'worker_error', reason: st.terminated ? 'terminated_after_result' : 'nonzero_exit_after_result' };
      } else if (!st.refusal && code !== 0 && !st.terminated) st.refusal = { outcome: 'worker_error', reason: 'unexpected_worker_exit' };
      finish(true);
    });
    rss.active = () => {
      if (!st.refusal) {
        if (st.result) st.prior = { outcome: st.result.outcome, constructor_returned: st.result.constructor_returned };
        st.refusal = { outcome: 'resource_refusal', reason: 'rss_limit' };
        terminate();
      }
    };
    rss.sample();
    st.timers.push(setTimeout(() => {
      if (!st.refusal) {
        if (st.result) st.prior = { outcome: st.result.outcome, constructor_returned: st.result.constructor_returned };
        st.refusal = { outcome: 'timeout', reason: performance.now() >= runDeadline ? 'run_deadline' : deadlineReason };
      }
      terminate();
    }, Math.max(0, jobDeadline - performance.now())));
  });
}

function realmFactsOk(result) {
  if (!result) return false;
  const keys = result.loaded_module_keys;
  if (!Array.isArray(keys) || keys.length !== MODULE_KEYS.length || MODULE_KEYS.some((key) => !keys.includes(key))) return false;
  const seek = result.seek_globals;
  return Array.isArray(seek) && seek.length === 3 && seek[0] === 1 && seek[1] === 2 && seek[2] === 3;
}

function buildRow(job, st, exitObserved, elapsed) {
  const row = { ...baseRow(job) };
  const result = st.result;
  let outcome;
  if (st.refusal) outcome = st.refusal.outcome;
  else if (result) outcome = result.outcome;
  else if (st.error && st.error.code === 'ERR_WORKER_OUT_OF_MEMORY') outcome = 'resource_refusal';
  else outcome = 'worker_error';
  if (result && !st.refusal && !realmFactsOk(result) && (outcome === 'returned' || outcome === 'constructor_exception')) {
    st.prior = { outcome, constructor_returned: result.constructor_returned };
    outcome = 'environment_failure';
    row.reason = 'realm_pin';
  }
  if (!OUTCOMES.includes(outcome)) outcome = 'worker_error';
  let returned = result ? result.constructor_returned : returnedFromPhase(st.phase);
  if (outcome === 'constructor_exception') returned = false;
  if (outcome === 'returned' || outcome === 'summary_error' || outcome === 'summary_limit') returned = true;
  if (outcome === 'timeout' && result && result.constructor_returned === true) returned = true;
  if (outcome === 'timeout' && !result) returned = returnedFromPhase(st.phase);
  Object.assign(row, {
    outcome,
    constructor_returned: returned,
    elapsed_ms: Math.round(elapsed * 1000) / 1000,
    worker_started: true,
    phase: st.phase,
    cleanup: { exit_observed: exitObserved, exit_code: st.exitCode, terminated_by_parent: st.terminated }
  });
  if (!exitObserved) row.cleanup.uncertainty = 'worker exit was not observed within the cleanup wait';
  if (st.refusal && !row.reason) row.reason = st.refusal.reason;
  if (st.prior) row.prior_result = st.prior;
  if (st.error) row.exception = exceptionInfo(st.error, 'worker', { max_exception_message_chars: 512 });
  if (result && result.exception && !st.error) row.exception = result.exception;
  if (result && result.constructor_ms !== undefined) row.constructor_ms = Math.round(result.constructor_ms * 1000) / 1000;
  if (result && result.summary_json_bytes !== undefined) row.summary_json_bytes = result.summary_json_bytes;
  if (result && result.limit) row.limit = result.limit;
  if (result && Array.isArray(result.loaded_module_keys)) row.loaded_module_keys = result.loaded_module_keys;
  if (result && result.seek_globals) row.seek_globals = result.seek_globals;
  if (result && Array.isArray(result.dynamic_imports)) row.dynamic_import_refusals = result.dynamic_imports;
  const normal = outcome === 'returned' || outcome === 'constructor_exception';
  if (normal && (!exitObserved || st.exitCode !== 0 || st.terminated)) {
    row.prior_result = { outcome, constructor_returned: returned };
    row.outcome = 'worker_error';
    row.reason = row.reason || 'lifecycle';
  }
  const logText = [result && result.log && result.log.text, st.stderr].filter(Boolean).join('\n');
  row._log = logText;
  row._log_dropped_entries = result && result.log ? result.log.dropped : 0;
  row._stdio_dropped_utf8_bytes = st.stderrDropped;
  row._summary_json = row.outcome === 'returned' && result ? result.summary_json : null;
  return row;
}

export function writeAll(fd, buffer, position = 0) {
  let off = 0;
  while (off < buffer.length) {
    const n = fs.writeSync(fd, buffer, off, buffer.length - off, position + off);
    if (!Number.isInteger(n) || n < 1 || n > buffer.length - off) throw new Refusal('output_io_error', 'write made no valid progress');
    off += n;
  }
}

class Output {
  constructor(dir, policy) {
    this.dir = dir;
    this.policy = policy;
    this.jobsPath = path.join(dir, 'jobs.jsonl');
    this.fd = fs.openSync(this.jobsPath, 'wx', 0o600);
    try { fs.fchmodSync(this.fd, 0o600); } catch (error) { fs.closeSync(this.fd); this.fd = null; throw error; }
    this.hash = crypto.createHash('sha256');
    this.bytes = 0;
    this.records = 0;
    this.logBytes = 0;
    this.tailUncertain = false;
    this.closeVerified = false;
  }
  write(line) {
    const buf = Buffer.from(`${line}\n`, 'utf8');
    try { writeAll(this.fd, buf, this.bytes); } catch (error) {
      try {
        fs.ftruncateSync(this.fd, this.bytes);
        if (fs.fstatSync(this.fd).size !== this.bytes) throw new Error('rollback size mismatch');
      } catch {
        this.tailUncertain = true;
        throw new Refusal('output_rollback_unverified', 'partial JSONL tail cannot be trusted');
      }
      throw error;
    }
    this.hash.update(buf);
    this.bytes += buf.length;
    this.records++;
  }
  close() {
    if (this.fd === null) return;
    const fd = this.fd;
    this.fd = null;
    try { fs.fsyncSync(fd); } finally { fs.closeSync(fd); }
    this.closeVerified = true;
  }
}

export function boundedRow(row, policy, logBudget, omitResult = false) {
  const { _log, _log_dropped_entries = 0, _stdio_dropped_utf8_bytes = 0, _summary_json, ...clean } = row;
  const capturedBytes = Buffer.byteLength(_log || '');
  const logFacts = () => {
    const dropped = capturedBytes - Buffer.byteLength(clean.log || '');
    if (_log_dropped_entries) clean.log_dropped_entries = _log_dropped_entries;
    if (_stdio_dropped_utf8_bytes) clean.stdio_dropped_utf8_bytes = _stdio_dropped_utf8_bytes;
    if (dropped) clean.log_dropped_utf8_bytes = dropped;
    if (capturedBytes || _log_dropped_entries || _stdio_dropped_utf8_bytes) {
      clean.log_truncated = !!(dropped || _log_dropped_entries || _stdio_dropped_utf8_bytes);
      if (capturedBytes && !clean.log) clean.log_omitted = true;
    }
  };
  if (_summary_json && !omitResult) clean.summary = JSON.parse(_summary_json);
  if (_log && !omitResult) {
    const limit = Math.min(policy.max_job_log_bytes, Math.max(0, logBudget));
    const piece = utf8Prefix(_log, limit);
    if (piece.bytes) clean.log = piece.text;
  }
  if (omitResult && (clean.outcome === 'returned' || clean.summary)) {
    delete clean.summary;
    delete clean.log;
    if (clean.outcome === 'returned') clean.outcome = 'summary_limit';
    clean.limit = 'max_jobs_jsonl_bytes';
  }
  logFacts();
  let line = JSON.stringify(clean);
  if (Buffer.byteLength(line) > policy.max_job_json_bytes) {
    delete clean.summary;
    delete clean.log;
    logFacts();
    if (clean.outcome === 'returned') clean.outcome = 'summary_limit';
    clean.limit = clean.limit || 'max_job_json_bytes';
    line = JSON.stringify(clean);
  }
  if (Buffer.byteLength(line) > policy.max_job_json_bytes) {
    const compact = {
      ...baseRow(clean),
      outcome: clean.outcome,
      constructor_returned: clean.constructor_returned,
      elapsed_ms: clean.elapsed_ms,
      worker_started: clean.worker_started,
      cleanup: {
        exit_observed: clean.cleanup.exit_observed,
        exit_code: clean.cleanup.exit_code ?? null,
        terminated_by_parent: clean.cleanup.terminated_by_parent ?? false
      }
    };
    for (const key of ['log_truncated', 'log_omitted', 'log_dropped_entries', 'stdio_dropped_utf8_bytes', 'log_dropped_utf8_bytes']) {
      if (Object.hasOwn(clean, key)) compact[key] = clean[key];
    }
    if (clean.reason) compact.reason = String(clean.reason).slice(0, 64);
    if (clean.exception) compact.exception = {
      phase: String(clean.exception.phase).slice(0, 64),
      name: String(clean.exception.name).slice(0, 64),
      message: String(clean.exception.message || '').slice(0, policy.max_exception_message_chars)
    };
    line = JSON.stringify(compact);
    while (Buffer.byteLength(line) > policy.max_job_json_bytes && compact.exception && compact.exception.message.length) {
      compact.exception.message = compact.exception.message.slice(0, -1);
      line = JSON.stringify(compact);
    }
    if (Buffer.byteLength(line) > policy.max_job_json_bytes) throw new Refusal('output_budget', 'mandatory row does not fit');
    return { row: compact, line, logBytes: 0 };
  }
  return { row: clean, line, logBytes: clean.log ? Buffer.byteLength(clean.log) : 0 };
}

export function assertOutputAncestors(output) {
  for (let current = path.dirname(output); ; current = path.dirname(current)) {
    try {
      const st = fs.lstatSync(current);
      if (st.isSymbolicLink()) throw new Refusal('symlink_refused', 'output ancestor');
      if (!st.isDirectory()) throw new Refusal('path_refused', 'output ancestor is not a directory');
    } catch (error) {
      if (error instanceof Refusal) throw error;
      if (error.code !== 'ENOENT') throw error;
    }
    if (current === path.dirname(current)) break;
  }
}

function pathExists(target) {
  try { fs.lstatSync(target); return true; } catch (error) {
    if (error.code === 'ENOENT') return false;
    throw error;
  }
}

function mkdirPrivate(dir, privateRoot) {
  const created = [];
  let current = dir;
  while (current.startsWith(privateRoot) && !pathExists(current)) {
    created.push(current);
    current = path.dirname(current);
  }
  fs.mkdirSync(dir, { recursive: true, mode: 0o700 });
  for (const createdDir of created) {
    try { fs.chmodSync(createdDir, 0o700); } catch { /* mode is also passed to mkdir */ }
  }
}

function publishAtomic(dir, name, text) {
  const finalPath = path.join(dir, name);
  const tmp = path.join(dir, `.${name}.${process.pid}.${crypto.randomBytes(4).toString('hex')}.tmp`);
  const fd = fs.openSync(tmp, 'wx', 0o600);
  try {
    fs.fchmodSync(fd, 0o600);
    writeAll(fd, Buffer.from(text));
    fs.fsyncSync(fd);
  } catch (error) {
    try { fs.closeSync(fd); } catch { /* already failing */ }
    try { fs.unlinkSync(tmp); } catch { /* already failing */ }
    throw error;
  }
  try { fs.closeSync(fd); } catch (error) {
    // Do not retry an ambiguous close; unlink only our exclusive temporary name.
    try { fs.unlinkSync(tmp); } catch { /* qualification already fails */ }
    throw error;
  }
  try { fs.renameSync(tmp, finalPath); } catch (error) {
    try { fs.unlinkSync(tmp); } catch { /* already failing */ }
    throw error;
  }
  try { fs.chmodSync(finalPath, 0o600); } catch { /* exclusive create already requested 0600 */ }
}

function say(stdout, obj, limit = 4096) {
  let line = JSON.stringify(obj);
  let buf = Buffer.from(`${line}\n`);
  if (buf.length > limit) {
    line = JSON.stringify({ status: obj.status || 'incomplete', reason: obj.reason || 'truncated' });
    buf = Buffer.from(`${line}\n`);
    if (buf.length > limit) buf = buf.subarray(0, limit);
  }
  stdout.write(buf);
}

function recheckPins(pins) {
  const result = { method: 'full_read_hash_and_identity', expected: pins.length, checked: 0, failed: [], ok: false };
  for (const pin of pins) {
    try {
      readPinnedFile(pin.abs || pin.path, { label: pin.role || 'pinned input', maxBytes: Math.max(pin.bytes, 1),
        expectBytes: pin.bytes, expectSha: pin.sha256, expectIdentity: pin.identity });
      result.checked++;
    } catch (error) { result.failed.push({ role: pin.role || 'pinned input', reason: error.reason || 'input_io_error' }); }
  }
  result.ok = result.checked === result.expected;
  return result;
}

export function expandTargetOutcomes(targets, outcomeByJobId) {
  const counts = Object.fromEntries(OUTCOMES.map((outcome) => [outcome, 0]));
  const linked = targets.map((target) => {
    const outcome = outcomeByJobId.get(target.job_id) || 'unattempted';
    counts[outcome] = (counts[outcome] || 0) + 1;
    return { ...structuredClone(target), constructor_outcome: outcome };
  });
  return { counts, targets: linked };
}

function prepare(opts) {
  if (typeof vm.SourceTextModule !== 'function') throw new Refusal('environment', 'run node with --experimental-vm-modules');
  const inputRoot = path.resolve(opts.input_root);
  const clientSource = path.resolve(opts.client_source);
  const output = path.resolve(opts.output);
  assertNoLinks(inputRoot, 'input-root');
  assertNoLinks(clientSource, 'client-source');
  if (!fs.statSync(inputRoot).isDirectory() || !fs.statSync(clientSource).isDirectory()) throw new Refusal('special_file_refused', 'roots must be directories');
  assertOutputAncestors(output);
  const privateRoot = path.join(REPO_ROOT, '.tools', 'renewal');
  if (output !== privateRoot && !output.startsWith(privateRoot + path.sep)) throw new Refusal('path_refused', 'output must be below this checkout .tools/renewal');
  if (pathExists(output)) throw new Refusal('output_exists', 'output path already exists');
  if (output === clientSource || output.startsWith(clientSource + path.sep)) throw new Refusal('path_refused', 'output inside client-source');
  const profileFile = readPinnedFile(path.resolve(opts.profile), {
    label: 'profile', maxBytes: 65536, expectBytes: PROFILE_BYTES, expectSha: PROFILE_SHA256
  });
  const profile = validateProfile(readJson(profileFile.buffer, 'profile'));
  const pins = [{ role: 'profile', path: path.resolve(opts.profile), bytes: profileFile.bytes, sha256: profileFile.sha256, identity: profileFile.identity }];
  const summaryAbs = safeJoin(REPO_ROOT, profile.summary.path, 'summary');
  const summary = readPinnedFile(summaryAbs, {
    label: 'summary', maxBytes: profile.summary.bytes, expectBytes: profile.summary.bytes, expectSha: profile.summary.sha256
  });
  pins.push({ role: 'summary', path: summaryAbs, bytes: summary.bytes, sha256: summary.sha256, identity: summary.identity });
  const sources = {};
  const sourcePins = [];
  for (const key of MODULE_KEYS) {
    const pin = profile.sources[key];
    const abs = safeJoin(clientSource, key, `source ${key}`);
    const file = readPinnedFile(abs, { label: `source ${key}`, maxBytes: pin.bytes, expectBytes: pin.bytes, expectSha: pin.sha256 });
    sources[key] = file.buffer.toString('utf8');
    sourcePins.push({ role: 'module', path: key, bytes: file.bytes, sha256: file.sha256, verified: true, identity: file.identity, abs });
  }
  const rulePins = [];
  for (const key of RULE_KEYS) {
    const pin = profile.rule_sources[key];
    const abs = safeJoin(clientSource, key, `rule ${key}`);
    const file = readPinnedFile(abs, { label: `rule ${key}`, maxBytes: pin.bytes, expectBytes: pin.bytes, expectSha: pin.sha256 });
    rulePins.push({ role: 'rule', path: key, bytes: file.bytes, sha256: file.sha256, verified: true, identity: file.identity, abs });
  }
  const ownPins = OWN_SOURCES.map((name) => {
    const abs = path.join(HERE, name);
    const file = readPinnedFile(abs, { label: name, maxBytes: 2 * 1024 * 1024 });
    return { role: 'own', path: `tools/renewal/${name}`, bytes: file.bytes, sha256: file.sha256, identity: file.identity, abs };
  });
  const policySource = profile.policy;
  let mode;
  let inputAbs;
  let inputFile;
  let jobs;
  let manifest = null;
  let corpus = null;
  if (opts.fixtures) {
    mode = 'fixtures';
    inputAbs = path.resolve(opts.fixtures);
    inputFile = readPinnedFile(inputAbs, {
      label: 'fixtures', maxBytes: policySource.max_fixture_bytes, expectBytes: profile.authored.bytes, expectSha: profile.authored.sha256
    });
    jobs = fixtureJobs(readJson(inputFile.buffer, 'fixtures'), policySource);
  } else {
    mode = 'corpus';
    inputAbs = path.resolve(opts.manifest);
    const manifestAbs = safeJoin(inputRoot, profile.manifest.path, 'manifest');
    if (inputAbs !== manifestAbs) throw new Refusal('path_refused', 'manifest is not the profile manifest under input-root');
    inputFile = readPinnedFile(inputAbs, {
      label: 'manifest', maxBytes: policySource.max_manifest_bytes, expectBytes: profile.manifest.bytes, expectSha: profile.manifest.sha256
    });
    manifest = readJson(inputFile.buffer, 'manifest');
    const loadPinned = (rel, maxBytes, expectBytes, expectSha, expectIdentity) => {
      const abs = safeJoin(inputRoot, rel, rel);
      return { abs, ...readPinnedFile(abs, { label: rel, maxBytes, expectBytes, expectSha, expectIdentity }) };
    };
    const availability = manifest.availability || {};
    for (const key of ['report', 'catalog', 'root_audit']) {
      const pinned = profile.availability[key];
      const declared = availability[key];
      if (!declared || declared.path !== pinned.path || declared.bytes !== pinned.bytes || declared.sha256 !== pinned.sha256) {
        throw new Refusal('admission_discrepancy', key);
      }
      assertDecimalIdentity(declared.identity, key);
    }
    const reportFile = loadPinned(profile.availability.report.path, policySource.max_availability_report_bytes, profile.availability.report.bytes, profile.availability.report.sha256, availability.report.identity);
    const catalogFile = loadPinned(profile.availability.catalog.path, policySource.max_catalog_bytes, profile.availability.catalog.bytes, profile.availability.catalog.sha256, availability.catalog.identity);
    const auditFile = loadPinned(profile.availability.root_audit.path, 65536, profile.availability.root_audit.bytes, profile.availability.root_audit.sha256, availability.root_audit.identity);
    const report = readJson(reportFile.buffer, 'availability report');
    const catalog = readJson(catalogFile.buffer, 'catalog');
    const audit = readJson(auditFile.buffer, 'root audit');
    const corpusDir = path.dirname(safeJoin(inputRoot, profile.availability.report.path, 'availability'));
    assertNoLinks(corpusDir, 'corpus root');
    const dirStat = fs.lstatSync(corpusDir);
    if (!dirStat.isDirectory() || dirStat.isSymbolicLink() || (dirStat.mode & 0o777) !== 0o700) throw new Refusal('mode_refused', 'corpus root');
    const readBody = (target) => readPinnedFile(safeJoin(inputRoot, target.body.path, 'body'), {
      label: 'body',
      maxBytes: policySource.max_body_bytes,
      expectBytes: target.body.bytes,
      expectSha: target.body.sha256,
      expectIdentity: target.body.identity,
      requireMode: 0o600,
      requireNlink: 1
    });
    jobs = admitModelCorpus({ manifest, report, catalog, audit, profile, readBody });
    corpus = { report, catalog, audit, reportFile, catalogFile, auditFile, readBody };
    pins.push(
      { role: 'availability_report', path: reportFile.abs, bytes: reportFile.bytes, sha256: reportFile.sha256, identity: reportFile.identity },
      { role: 'catalog', path: catalogFile.abs, bytes: catalogFile.bytes, sha256: catalogFile.sha256, identity: catalogFile.identity },
      { role: 'root_audit', path: auditFile.abs, bytes: auditFile.bytes, sha256: auditFile.sha256, identity: auditFile.identity }
    );
  }
  pins.push({ role: mode, path: inputAbs, bytes: inputFile.bytes, sha256: inputFile.sha256, identity: inputFile.identity });
  const policy = effectivePolicy(policySource, opts.overrides, jobs.length);
  // Reserve a compact failure envelope including all required log-loss facts.
  // Exception text may shrink to empty, but its phase/name and loss units stay.
  const mandatoryBytes = (job) => Buffer.byteLength(JSON.stringify({
    ...baseRow(job), outcome: 'constructor_exception', constructor_returned: false,
    elapsed_ms: Number.MAX_SAFE_INTEGER, worker_started: false,
    cleanup: { exit_observed: false, exit_code: -2147483648, terminated_by_parent: false },
    reason: '\u0800'.repeat(64), exception: { phase: '\u0800'.repeat(64), name: '\u0800'.repeat(64), message: '' },
    log_truncated: true, log_omitted: true, log_dropped_entries: Number.MAX_SAFE_INTEGER,
    stdio_dropped_utf8_bytes: Number.MAX_SAFE_INTEGER, log_dropped_utf8_bytes: policy.max_job_log_bytes * 2 + 1
  })) + 1;
  if (jobs.some((job) => mandatoryBytes(job) > policy.max_job_json_bytes)) {
    throw new Refusal('output_budget', 'job cap cannot hold mandatory accounting');
  }
  const reserve = jobs.map((job) => Buffer.byteLength(JSON.stringify(unattemptedRow(job, 'output_limit'))) + 1 + ROW_SLACK_BYTES);
  const suffix = new Array(jobs.length + 1).fill(0);
  for (let i = jobs.length - 1; i >= 0; i--) suffix[i] = suffix[i + 1] + reserve[i];
  if (suffix[0] > policy.max_jobs_jsonl_bytes) throw new Refusal('output_budget', 'jobs.jsonl cannot account for every job');
  return {
    inputRoot, clientSource, output, profile, profileSha: profileFile.sha256, summary, sources, sourcePins, rulePins, ownPins, pins,
    mode, inputAbs, inputFile, jobs, manifest, corpus, policy, suffix, privateRoot,
    summaryText: summary.buffer.toString('utf8')
  };
}

function corpusPostcheck(P) {
  if (P.mode !== 'corpus') return { checked: 0, ok: true };
  let checked = 0;
  for (const target of P.manifest.targets) {
    if (hooks.beforeRepresentativeReread) hooks.beforeRepresentativeReread(target);
    const file = P.corpus.readBody(target);
    checked++;
    if (sha256(file.buffer) !== target.body.sha256 || !sameIdentity(file.identity, target.body.identity)) {
      throw new Refusal('identity_changed', 'postcheck body');
    }
  }
  return { checked, ok: true };
}

async function run(P, sayLine, started) {
  assertOutputAncestors(P.output);
  mkdirPrivate(path.dirname(P.output), P.privateRoot);
  assertOutputAncestors(P.output);
  try { fs.mkdirSync(P.output, { mode: 0o700 }); } catch (error) {
    sayLine({ status: 'refused', reason: 'output_exists', output_created: false });
    return 2;
  }
  fs.chmodSync(P.output, 0o700);
  let out = null;
  let sampler = null;
  const { policy, jobs, mode } = P;
  const runDeadline = started + policy.run_timeout_ms;
  const rss = { samples: 0, peak: 0, over: 0, active: null };
  rss.sample = () => {
    const value = process.memoryUsage().rss;
    rss.samples++;
    rss.peak = Math.max(rss.peak, value);
    if (value > policy.rss_limit_bytes) {
      rss.over++;
      if (rss.active) rss.active();
    }
  };
  const counts = Object.fromEntries(OUTCOMES.map((outcome) => [outcome, 0]));
  const outcomeById = new Map();
  const accounting = jobs.map((job) => accountingRow(unattemptedRow(job, 'not_started')));
  const cleanup = { workers_started: 0, exits_observed: 0, unverified: [], halted: null };
  const authored = { matched: 0, mismatched: [] };
  let halt = null;
  let incomplete = false;
  let publicationFailed = false;
  try {
    const plan = {
      schema: 'T06-model-constructor-report-1',
      checkpoint: 'admission',
      qualified: false,
      task: 'T06.003.003.006',
      mode,
      job_ids: jobs.map((job) => job.job_id),
      target_ids: mode === 'corpus' ? P.manifest.targets.map((target) => target.model_ordinal) : []
    };
    try { publishAtomic(P.output, 'report.checkpoint.json', JSON.stringify(plan)); }
    catch {
      // Preserve all IDs in the final accounting, but never start a worker
      // when its initial checkpoint was not published.
      publicationFailed = true;
      incomplete = true;
      halt = 'checkpoint_publication_failure';
    }
    out = new Output(P.output, policy);
    sampler = setInterval(rss.sample, policy.rss_sample_ms);
    if (typeof sampler.unref === 'function') sampler.unref();
    const ctx = { policy, sources: P.sources, summaryText: P.summaryText, runDeadline, rss };
    for (let i = 0; i < jobs.length; i++) {
      if (performance.now() >= runDeadline) halt ||= 'run_deadline';
      if (rss.over) halt ||= 'rss_limit';
      const job = jobs[i];
      let row;
      if (halt) row = unattemptedRow(job, halt);
      else if (i >= policy.max_jobs) row = unattemptedRow(job, 'max_jobs');
      else {
        let bytes = null;
        if (mode === 'fixtures') bytes = job.fixture_bytes;
        else {
          try {
            if (hooks.beforeRepresentativeReread) hooks.beforeRepresentativeReread(job);
            const representative = P.manifest.targets[job.representative_model_ordinal];
            bytes = P.corpus.readBody(representative).buffer;
          } catch (error) {
            row = {
              ...baseRow(job),
              outcome: 'input_refused',
              reason: error.reason || 'input_io_error',
              constructor_returned: null,
              elapsed_ms: 0,
              worker_started: false,
              cleanup: { exit_observed: null, exit_code: null, terminated_by_parent: false },
              exception: exceptionInfo(error, 'input', policy)
            };
          }
        }
        if (!row) {
          row = await runWorkerJob(job, bytes, ctx);
          if (performance.now() >= runDeadline && row.outcome === 'returned') {
            row.prior_result = { outcome: row.outcome, constructor_returned: row.constructor_returned };
            row.outcome = 'timeout';
            row.reason = 'run_deadline';
            row._summary_json = null;
          }
          if (row.worker_started) {
            cleanup.workers_started++;
            if (row.cleanup.exit_observed === true) cleanup.exits_observed++;
            else { cleanup.unverified.push(job.id); halt = 'cleanup_unverified'; }
          }
          if ((row.outcome === 'timeout' || row.outcome === 'resource_refusal') && row.cleanup.exit_observed !== true) {
            halt = 'cleanup_unverified';
          } else if (row.outcome === 'timeout' && row.reason === 'run_deadline') halt ||= 'run_deadline';
          else if (row.outcome === 'resource_refusal') halt ||= 'rss_limit';
          else if (row.outcome === 'worker_error' && row.reason === 'lifecycle') halt ||= 'lifecycle';
        }
      }
      accounting[i] = accountingRow(row);
      let selected = boundedRow(row, policy, policy.max_total_log_bytes - out.logBytes);
      if (out.bytes + Buffer.byteLength(selected.line) + 1 + P.suffix[i + 1] > policy.max_jobs_jsonl_bytes) {
        selected = boundedRow(row, policy, 0, true);
        halt ||= 'output_limit';
      }
      try { out.write(selected.line); } catch (error) {
        halt ||= 'output_io_error';
        incomplete = true;
        const failedRow = {
          ...row,
          outcome: 'environment_failure',
          _summary_json: null,
          reason: error.reason || 'output_io_error',
          ...(['returned', 'constructor_exception'].includes(row.outcome) ? {
            prior_result: { outcome: row.outcome, constructor_returned: row.constructor_returned }
          } : {}),
          exception: exceptionInfo(error, 'publication', policy)
        };
        accounting[i] = accountingRow(failedRow);
        if (out.tailUncertain) { publicationFailed = true; break; }
        try {
          selected = boundedRow(failedRow, policy, 0);
          out.write(selected.line);
        } catch (second) {
          publicationFailed = true;
          halt ||= second.reason || 'publication_failure';
          break;
        }
      }
      row = selected.row;
      accounting[i] = accountingRow(row);
      out.logBytes += selected.logBytes;
      if (mode === 'fixtures' && row.outcome !== 'unattempted' && row.worker_started) {
        if (compareAuthored(job, row)) authored.matched++;
        else authored.mismatched.push(job.id);
      }
      if (!OUTCOMES.includes(row.outcome)) row.outcome = 'worker_error';
      if (row.outcome !== 'returned' && row.outcome !== 'constructor_exception') incomplete = true;
      if (authored.mismatched.length) incomplete = true;
    }
  } catch (error) {
    publicationFailed = true;
    halt ||= error.reason || 'publication_failure';
    incomplete = true;
  } finally {
    if (sampler) clearInterval(sampler);
    if (out) {
      try { out.close(); } catch (error) {
        publicationFailed = true;
        halt ||= error.reason || 'publication_failure';
        incomplete = true;
      }
    }
  }
  // Publication can stop physical rows. Account every untouched suffix in the
  // final report without inventing worker starts or discarding an observed job.
  for (let i = 0; i < accounting.length; i++) {
    const row = accounting[i];
    if (row.outcome === 'unattempted' && row.reason === 'not_started') row.reason = halt || 'not_reached';
    counts[row.outcome]++;
    outcomeById.set(row.job_id, row.outcome);
  }
  rss.sample();
  if (rss.over) { halt ||= 'rss_limit'; incomplete = true; }
  let postcheck = mode === 'fixtures' ? { checked: 0, ok: true } : { checked: 0, ok: false, reason: 'not_run_after_publication_failure' };
  if (!publicationFailed && mode === 'corpus') {
    try { postcheck = corpusPostcheck(P); } catch (error) {
      postcheck = { checked: postcheck.checked, ok: false, reason: error.reason || 'identity_changed' };
      incomplete = true;
      halt ||= 'identity_changed';
    }
  }
  if (hooks.beforeIdentityRecheck) hooks.beforeIdentityRecheck(P.pins);
  const pinPostcheck = recheckPins([...P.pins, ...P.sourcePins, ...P.rulePins, ...P.ownPins]);
  const identityUnchanged = pinPostcheck.ok;
  if (!identityUnchanged) { incomplete = true; halt ||= 'source_drift'; }
  if (performance.now() >= runDeadline) { halt ||= 'run_deadline'; incomplete = true; }
  cleanup.halted = halt;
  const qualified = !incomplete && !publicationFailed && !halt && cleanup.unverified.length === 0 &&
    cleanup.workers_started === cleanup.exits_observed && identityUnchanged && postcheck.ok && performance.now() < runDeadline;
  let linked = { counts: Object.fromEntries(OUTCOMES.map((outcome) => [outcome, 0])), targets: [] };
  if (mode === 'corpus') linked = expandTargetOutcomes(P.manifest.targets, outcomeById);
  const jobsDigest = out ? out.hash.digest('hex') : null;
  const report = {
    schema: 'T06-model-constructor-report-1',
    task: 'T06.003.003.006',
    qualified,
    mode,
    expected_job_ids: jobs.map((job) => job.job_id),
    expected_target_ids: mode === 'corpus' ? P.manifest.targets.map((target) => target.model_ordinal) : [],
    job_accounting: accounting,
    input: { path: P.inputAbs, bytes: P.inputFile.bytes, sha256: P.inputFile.sha256, identity: P.inputFile.identity },
    profile_sha256: P.profileSha,
    summary_sha256: P.summary.sha256,
    common_summary: { path: P.profile.summary.path, bytes: P.summary.bytes, sha256: P.summary.sha256, identity: P.summary.identity },
    client_source: {
      root: P.clientSource,
      profile_revision: P.profile.client_source_revision,
      revision_checked: false,
      sources: P.sourcePins.map(({ path: sourcePath, bytes, sha256: digest, verified, identity }) => ({ path: sourcePath, bytes, sha256: digest, verified, identity })),
      rule_sources: P.rulePins.map(({ path: sourcePath, bytes, sha256: digest, verified, identity }) => ({ path: sourcePath, bytes, sha256: digest, verified, identity }))
    },
    own_sources: P.ownPins.map(({ path: sourcePath, bytes, sha256: digest, identity }) => ({ path: sourcePath, bytes, sha256: digest, identity })),
    pinned_inputs: P.pins.map(({ role, path: inputPath, bytes, sha256: digest, identity }) => ({ role, path: inputPath, bytes, sha256: digest, identity })),
    source_postchecks: pinPostcheck,
    pinned_inputs_identity_unchanged_after_run: identityUnchanged,
    preserved_counts: P.profile.counts,
    header_prefix_counts: P.profile.header_prefix_counts,
    header_prefix_counts_are_observations: true,
    effective_policy: policy,
    counts: {
      expected_jobs: jobs.length,
      expected_targets: mode === 'corpus' ? P.manifest.targets.length : 0,
      records: out ? out.records : 0,
      attempted: jobs.length - counts.unattempted,
      job_outcomes: counts,
      target_outcomes: linked.counts
    },
    rss_sampling: {
      sample_ms: policy.rss_sample_ms,
      samples: rss.samples,
      peak_rss_bytes: rss.peak,
      limit_bytes: policy.rss_limit_bytes,
      over_limit_samples: rss.over,
      scope: 'whole parent process including worker threads; sampled, not a hard bound on typed arrays or native allocations'
    },
    cleanup: { ...cleanup, verified: cleanup.unverified.length === 0 && cleanup.workers_started === cleanup.exits_observed },
    postchecks: postcheck,
    elapsed_ms: Math.round(performance.now() - started),
    jobs_file: out ? { path: 'jobs.jsonl', bytes: out.tailUncertain ? null : out.bytes,
      sha256: out.tailUncertain ? null : jobsDigest, records: out.records,
      complete: out.records === jobs.length && !out.tailUncertain && out.closeVerified,
      ...(out.tailUncertain ? { confirmed_prefix: { bytes: out.bytes, sha256: jobsDigest, records: out.records } } : {}) } : null,
    storage: { publication_failed: publicationFailed, jobs_tail_uncertain: out ? out.tailUncertain : false,
      jobs_close_verified: out ? out.closeVerified : null },
    logs: { bytes: out ? out.logBytes : 0, limit_bytes: policy.max_total_log_bytes },
    roots: [],
    targets: [],
    remaining_gap_root_ordinals: [],
    prior_first_level_gaps: [],
    limitations: P.profile.limitations
  };
  if (mode === 'fixtures') report.authored_comparison = authored;
  else {
    report.roots = structuredClone(P.manifest.roots);
    report.remaining_gap_root_ordinals = structuredClone(P.manifest.remaining_gap_root_ordinals);
    report.prior_first_level_gaps = structuredClone(P.manifest.prior_first_level_gaps);
    report.targets = linked.targets;
    report.input_manifest = { schema: P.manifest.schema, counts: P.manifest.counts, limitations: P.manifest.limitations };
  }
  let text = JSON.stringify(report);
  if (Buffer.byteLength(text) > policy.max_report_json_bytes) {
    report.qualified = false;
    report.report_limit = { limit: 'max_report_json_bytes', targets_omitted: report.targets.length, roots_omitted: report.roots.length, complete: false };
    report.targets = [];
    report.roots = [];
    text = JSON.stringify(report);
    incomplete = true;
  }
  let exitCode = qualified && report.qualified !== false ? 0 : 1;
  const publishFinal = () => {
    const boundedText = JSON.stringify(report);
    if (Buffer.byteLength(boundedText) > policy.max_report_json_bytes) throw new Refusal('output_budget', 'report does not fit');
    publishAtomic(P.output, 'report.json', boundedText);
  };
  try {
    publishFinal();
    if (performance.now() >= runDeadline) {
      exitCode = 1;
      halt = halt || 'run_deadline_after_publication';
      report.qualified = false;
      report.deadline_after_publication = true;
      report.cleanup.halted = halt;
      publishFinal();
    }
    try { fs.unlinkSync(path.join(P.output, 'report.checkpoint.json')); }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
    if (exitCode === 0 && performance.now() >= runDeadline) {
      exitCode = 1;
      report.qualified = false;
      report.deadline_after_publication = true;
      report.cleanup.halted = halt = 'run_deadline_after_publication';
      publishFinal();
    }
  } catch (error) {
    exitCode = 1;
    publicationFailed = true;
    report.qualified = false;
    report.storage.publication_failed = true;
    // A one-shot publication failure may recover; persistent failure still
    // returns nonzero and preserves its checkpoint without promising a rewrite.
    try { publishFinal(); } catch { /* already failed */ }
    sayLine({ status: 'incomplete', reason: error.reason || 'publication_failure', mode, output_created: true });
    return exitCode;
  }
  if (exitCode === 0 && (performance.now() >= runDeadline || !identityUnchanged || !report.qualified)) exitCode = 1;
  sayLine({
    status: exitCode === 0 ? 'complete' : 'incomplete',
    reason: halt || (exitCode === 0 ? 'observed' : 'incomplete'),
    mode,
    exit_code: exitCode,
    expected_jobs: jobs.length,
    job_outcomes: Object.fromEntries(Object.entries(counts).filter(([, value]) => value)),
    halted: halt,
    cleanup_verified: report.cleanup.verified,
    ...(mode === 'fixtures' ? { authored_matched: authored.matched, authored_mismatched: authored.mismatched.length } : { targets: linked.targets.length })
  });
  return exitCode;
}

export async function main(argv, { stdout = process.stdout } = {}) {
  const started = performance.now();
  const sayLine = (obj) => say(stdout, obj, 4096);
  let prepared;
  try {
    prepared = prepare(parseArgs(argv));
  } catch (error) {
    if (!(error instanceof Refusal)) throw error;
    sayLine({ status: 'refused', reason: error.reason, output_created: false });
    return 2;
  }
  return run(prepared, sayLine, started);
}

const invokedDirectly = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (invokedDirectly) {
  main(process.argv.slice(2)).then((code) => { process.exitCode = code; }, (error) => {
    process.stdout.write(`${JSON.stringify({ status: 'error', reason: 'unexpected' }).slice(0, 4095)}\n`);
    process.exitCode = error instanceof Refusal ? 1 : 3;
  });
}
