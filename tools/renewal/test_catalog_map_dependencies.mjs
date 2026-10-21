// Controls for T06.003.003.004 and the T07.007.005 bridge route. Run from the child checkout:
//   node --test tools/renewal/test_catalog_map_dependencies.mjs
// Fixture mode reads the pinned profile, summary and three rule sources (plus the
// worker/producer text pins on the new route). It does not open the production
// jobs, report or manifest. Corpus tests read the canonical T07.007.004 metadata
// (report, jobs, input manifest) and source texts only; they skip when it is absent.
// Temp directories under .tools/renewal/T07.007.005 are removed after the file finishes.
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { admitConstructorBridge, buildCatalog, main, parseJobsJsonl, safeJoin, writeAll } from './catalog_map_dependencies.mjs';

process.umask(0o077);
const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, '..', '..');
const INPUT_ROOT = process.env.T06_INPUT_ROOT || path.resolve(REPO, '..', 'reverse-the-Ragnarok-Online-to-play-by-myself');
const PROFILE = path.join(REPO, 'docs/project/fixtures/T06.003.003.004-profile.json');
const FIXTURES = path.join(REPO, 'docs/project/fixtures/T06.003.003.004-authored.json');
const NEW_PROFILE = path.join(REPO, 'docs/project/fixtures/T07.007.005-profile.json');
const SCRIPT = path.join(HERE, 'catalog_map_dependencies.mjs');
const profile = JSON.parse(fs.readFileSync(PROFILE, 'utf8'));
const newProfile = JSON.parse(fs.readFileSync(NEW_PROFILE, 'utf8'));
const authored = JSON.parse(fs.readFileSync(FIXTURES, 'utf8'));
const NEW_REPORT = path.join(INPUT_ROOT, newProfile.inputs['report.json'].path);
const NEW_JOBS = path.join(INPUT_ROOT, newProfile.inputs['jobs.jsonl'].path);
const NEW_MANIFEST = path.join(INPUT_ROOT, newProfile.constructor_manifest.path);
const HAVE_CORPUS = [NEW_REPORT, NEW_JOBS, NEW_MANIFEST].every((file) => fs.existsSync(file));
const corpusOnly = { skip: HAVE_CORPUS ? false : 'canonical T07.007.004 metadata unavailable' };
const PRIVATE = path.join(REPO, '.tools', 'renewal', 'T07.007.005');
fs.mkdirSync(PRIVATE, { recursive: true, mode: 0o700 });
fs.chmodSync(PRIVATE, 0o700);
const TMP = fs.mkdtempSync(path.join(fs.realpathSync(PRIVATE), 'test-tmp-'));
fs.chmodSync(TMP, 0o700);
test.after(() => fs.rmSync(TMP, { recursive: true, force: true }));
let seq = 0;
const freshOut = () => path.join(TMP, `out-${++seq}`);

function deepFreeze(value) {
  if (!value || typeof value !== 'object' || Object.isFrozen(value)) return value;
  for (const key of Object.keys(value)) deepFreeze(value[key]);
  return Object.freeze(value);
}

function run(argv) {
  let out = '';
  let err = '';
  const stdout = { write(s) { out += s; return true; } };
  const code = main(argv, { stdout });
  return { code, out, err, summary: out.trim() ? JSON.parse(out.trim()) : null };
}

function fixtureArgs(output, extra = []) {
  return ['--input-root', INPUT_ROOT, '--profile', PROFILE, '--fixtures', FIXTURES, '--output', output, ...extra];
}

test('buildCatalog matches every authored field and leaves the caller unchanged', () => {
  const before = structuredClone(authored.input);
  const frozen = deepFreeze(structuredClone(authored.input));
  const got = buildCatalog(frozen);
  assert.deepEqual(got, authored.expected);
  assert.deepEqual(authored.input, before);
  got.roots[0].name = 'mutated';
  got.remaining_gap_root_ordinals.push(9);
  got.jobs[0].header_version_bytes[0] = 9;
  got.jobs[1].occurrence_loader_indexes.push(9);
  assert.equal(frozen.roots[0].name, authored.input.roots[0].name);
  assert.deepEqual(frozen.remaining_gap_root_ordinals, authored.input.remaining_gap_root_ordinals);
  assert.deepEqual(frozen.rows[0].header_version_bytes, authored.input.rows[0].header_version_bytes);
  assert.deepEqual(frozen.rows[1].summary.texture_indexes, authored.input.rows[1].summary.texture_indexes);
});

test('extra constructor summary and row fields stay out of the payload', () => {
  const input = structuredClone(authored.input);
  input.rows[0].elapsed_ms = 12;
  input.rows[0].summary.water = { level: 1 };
  input.rows[0].summary.files = ['ignored'];
  input.rows[1].summary.cursor = { trailing_bytes: 4 };
  input.rows[2].summary.version = { major: 1 };
  input.note = 'ignored';
  assert.deepEqual(buildCatalog(input), authored.expected);
});

test('fourteen frozen refusals keep their reasons and inputs', () => {
  assert.equal(authored.refusal_cases.length, 14);
  for (const item of authored.refusal_cases) {
    const before = structuredClone(item.input);
    assert.throws(() => buildCatalog(item.input), (error) => error instanceof Error && error.reason === item.reason && !String(error.message).includes('\uD800'));
    assert.deepEqual(item.input, before);
  }
});

test('jobs JSONL requires a final LF, nonempty rows and the row cap', () => {
  const one = Buffer.from('{"id":"a"}\n', 'utf8');
  assert.equal(parseJobsJsonl(one, { maxRowBytes: 100, maxTotalBytes: 100 }).length, 1);
  assert.throws(() => parseJobsJsonl(Buffer.from('{"id":"a"}', 'utf8'), { maxRowBytes: 100, maxTotalBytes: 100 }),
    (error) => error.reason === 'invalid_json');
  assert.throws(() => parseJobsJsonl(Buffer.from('{"id":"a"}\n\n', 'utf8'), { maxRowBytes: 100, maxTotalBytes: 100 }),
    (error) => error.reason === 'invalid_json');
  const big = Buffer.from(`${'x'.repeat(20)}\n`, 'utf8');
  assert.throws(() => parseJobsJsonl(big, { maxRowBytes: 10, maxTotalBytes: 100 }), (error) => error.reason === 'size_limit');
  assert.throws(() => safeJoin('/tmp/root', '../outside', 'sample'), (error) => error.reason.startsWith('path_refused'));
  assert.throws(() => safeJoin('/tmp/root', '/abs', 'sample'), (error) => error.reason.startsWith('path_refused'));
});

test('writeAll finishes a short write and stops on zero progress', () => {
  const file = path.join(TMP, 'write-all.bin');
  const fd = fs.openSync(file, 'wx', 0o600);
  const real = fs.writeSync;
  const payload = Buffer.from('catalog\n', 'utf8');
  let calls = 0;
  try {
    fs.writeSync = function (target, buffer, offset, length, position) {
      if (target !== fd) return real(target, buffer, offset, length, position);
      calls += 1;
      return real(target, buffer, offset, Math.min(3, length), position);
    };
    writeAll(fd, payload);
    assert.ok(calls > 1);
    assert.deepEqual(fs.readFileSync(file), payload);
    fs.ftruncateSync(fd, 0);
    calls = 0;
    fs.writeSync = function (target, ...args) {
      if (target !== fd) return real(target, ...args);
      calls += 1;
      if (calls > 1) throw new Error('retried after zero progress');
      return 0;
    };
    assert.throws(() => writeAll(fd, payload), (error) => error.reason === 'output_io_error');
    assert.equal(calls, 1);
    assert.equal(fs.statSync(file).size, 0);
  } finally {
    fs.writeSync = real;
    fs.closeSync(fd);
  }
});

test('fixture CLI publishes one deterministic catalog without production names or inputs', () => {
  const opened = [];
  const realOpen = fs.openSync;
  fs.openSync = function (target, ...args) {
    opened.push(typeof target === 'string' ? path.resolve(target) : '');
    return realOpen(target, ...args);
  };
  const first = freshOut();
  const second = freshOut();
  let a;
  let b;
  try {
    a = run(fixtureArgs(first));
    b = run(fixtureArgs(second));
  } finally { fs.openSync = realOpen; }
  assert.equal(a.code, 0);
  assert.equal(b.code, 0);
  assert.equal(a.out.split('\n').filter(Boolean).length, 1);
  assert.equal(a.err, '');
  assert.ok(Buffer.byteLength(a.out) <= 4096);
  assert.equal(a.summary.status, 'complete');
  assert.equal(a.summary.mode, 'fixtures');
  assert.equal(a.summary.output_created, true);
  assert.deepEqual(a.summary.counts, authored.expected.counts);
  assert.equal(a.out.includes('A.rsm'), false);
  assert.equal(a.out.includes('.bmp'), false);
  const forbidden = ['jobs.jsonl', 'report.json', path.join('src', 'Loaders', 'World.js')];
  assert.equal(opened.some((item) => forbidden.some((name) => item.endsWith(name))), false);
  const bytesA = fs.readFileSync(path.join(first, 'catalog.json'));
  const bytesB = fs.readFileSync(path.join(second, 'catalog.json'));
  assert.deepEqual(bytesA, bytesB);
  assert.equal(bytesA[bytesA.length - 1], 0x0a);
  assert.equal(fs.statSync(first).mode & 0o777, 0o700);
  assert.equal(fs.statSync(path.join(first, 'catalog.json')).mode & 0o777, 0o600);
  const catalog = JSON.parse(bytesA.toString('utf8'));
  assert.deepEqual(Object.keys(catalog), [
    'schema', 'task', 'mode', 'profile_sha256', 'input_pins', 'constructor_profile_sha256', 'summary_sha256',
    'rule_sources', 'counts', 'roots', 'remaining_gap_root_ordinals', 'jobs', 'targets', 'limitations'
  ]);
  assert.equal(catalog.schema, 'T06-map-dependency-catalog-1');
  assert.equal(catalog.task, 'T06.003.003.004');
  assert.equal(catalog.mode, 'fixtures');
  assert.equal(catalog.profile_sha256, crypto.createHash('sha256').update(fs.readFileSync(PROFILE)).digest('hex'));
  assert.deepEqual(catalog.input_pins, { authored: profile.authored });
  assert.equal(catalog.constructor_profile_sha256, profile.constructor_profile.sha256);
  assert.equal(catalog.summary_sha256, profile.summary.sha256);
  assert.deepEqual(catalog.rule_sources, profile.rule_sources);
  assert.deepEqual(catalog.limitations, profile.limitations);
  assert.deepEqual({
    counts: catalog.counts, roots: catalog.roots, remaining_gap_root_ordinals: catalog.remaining_gap_root_ordinals,
    jobs: catalog.jobs, targets: catalog.targets
  }, authored.expected);
});

test('existing output, a low cap and a raised cap refuse before publication', () => {
  const existing = freshOut();
  fs.mkdirSync(existing, { mode: 0o700 });
  fs.writeFileSync(path.join(existing, 'keep.txt'), 'preserve', { mode: 0o600 });
  const kept = run(fixtureArgs(existing));
  assert.equal(kept.code, 2);
  assert.equal(kept.summary.status, 'refused');
  assert.equal(kept.summary.reason, 'output_exists');
  assert.equal(kept.summary.output_created, false);
  assert.equal(fs.readFileSync(path.join(existing, 'keep.txt'), 'utf8'), 'preserve');
  assert.equal(fs.existsSync(path.join(existing, 'catalog.json')), false);

  const low = freshOut();
  const capped = run(fixtureArgs(low, ['--max-output-bytes', '32']));
  assert.equal(capped.code, 2);
  assert.equal(capped.summary.reason, 'output_budget');
  assert.equal(capped.summary.output_created, false);
  assert.equal(fs.existsSync(low), false);

  const raised = run(fixtureArgs(freshOut(), ['--max-output-bytes', String(profile.policy.max_catalog_bytes + 1)]));
  assert.equal(raised.code, 2);
  assert.equal(raised.summary.reason, 'policy_increase');
  assert.equal(raised.summary.output_created, false);
});

test('usage, symlink profile and symlink output ancestor are refused', () => {
  const both = run(['--input-root', INPUT_ROOT, '--profile', PROFILE, '--fixtures', FIXTURES, '--report', FIXTURES,
    '--jobs', FIXTURES, '--output', freshOut()]);
  assert.equal(both.code, 2);
  assert.equal(both.summary.reason, 'usage');
  const missing = run(['--input-root', INPUT_ROOT, '--profile', PROFILE, '--output', freshOut()]);
  assert.equal(missing.summary.reason, 'usage');

  const linkedProfile = path.join(TMP, 'profile-link.json');
  fs.symlinkSync(PROFILE, linkedProfile);
  const profileLink = run(fixtureArgs(freshOut()).map((arg) => arg === PROFILE ? linkedProfile : arg));
  assert.equal(profileLink.code, 2);
  assert.equal(profileLink.summary.reason, 'symlink_refused');
  assert.equal(profileLink.summary.output_created, false);

  const realDir = path.join(TMP, 'ancestor-real');
  const alias = path.join(TMP, 'ancestor-alias');
  fs.mkdirSync(realDir, { mode: 0o700 });
  fs.writeFileSync(path.join(realDir, 'sentinel'), 'preserve', { mode: 0o600 });
  fs.symlinkSync(realDir, alias);
  const ancestor = run(fixtureArgs(path.join(alias, 'new-output')));
  assert.equal(ancestor.code, 2);
  assert.equal(ancestor.summary.status, 'refused');
  assert.equal(ancestor.summary.output_created, false);
  assert.deepEqual(fs.readdirSync(realDir), ['sentinel']);
  assert.equal(fs.readFileSync(path.join(realDir, 'sentinel'), 'utf8'), 'preserve');
});

test('a changed profile pin is refused', () => {
  const copy = path.join(TMP, 'profile-bad.json');
  const bytes = Buffer.from(fs.readFileSync(PROFILE));
  bytes[bytes.length - 2] ^= 1;
  fs.writeFileSync(copy, bytes, { mode: 0o600 });
  const result = run(fixtureArgs(freshOut()).map((arg) => arg === PROFILE ? copy : arg));
  assert.equal(result.code, 2);
  assert.equal(result.summary.reason, 'pin_mismatch');
  assert.equal(result.summary.output_created, false);
});

test('a zero-progress catalog write closes its descriptor and does not complete', () => {
  const output = freshOut();
  const real = { open: fs.openSync, close: fs.closeSync, write: fs.writeSync };
  let owned = null;
  let calls = 0;
  fs.openSync = function (target, ...args) {
    const fd = real.open(target, ...args);
    if (typeof target === 'string' && path.basename(target) === 'catalog.json') owned = fd;
    return fd;
  };
  fs.closeSync = function (fd) {
    const result = real.close(fd);
    if (fd === owned) owned = null;
    return result;
  };
  fs.writeSync = function (fd, ...args) {
    if (fd !== owned) return real.write(fd, ...args);
    calls += 1;
    if (calls > 2) throw new Error('write loop did not stop');
    return 0;
  };
  let result;
  try { result = run(fixtureArgs(output)); }
  finally {
    fs.openSync = real.open;
    fs.closeSync = real.close;
    fs.writeSync = real.write;
    if (owned !== null) real.close(owned);
  }
  assert.equal(calls, 1);
  assert.equal(owned, null);
  assert.equal(result.code, 1);
  assert.equal(result.summary.status, 'error');
  assert.equal(result.summary.reason, 'output_io_error');
  assert.equal(result.summary.output_created, true);
  assert.notEqual(result.summary.status, 'complete');
});

test('a short catalog write still publishes the exact fixture bytes', () => {
  const output = freshOut();
  const real = { open: fs.openSync, close: fs.closeSync, write: fs.writeSync };
  let owned = null;
  let injected = 0;
  fs.openSync = function (target, ...args) {
    const fd = real.open(target, ...args);
    if (typeof target === 'string' && path.basename(target) === 'catalog.json') owned = fd;
    return fd;
  };
  fs.closeSync = function (fd) {
    const result = real.close(fd);
    if (fd === owned) owned = null;
    return result;
  };
  fs.writeSync = function (fd, buffer, offset, length, position) {
    if (fd === owned && injected === 0) {
      injected += 1;
      return real.write(fd, buffer, offset, 1, position);
    }
    return real.write(fd, buffer, offset, length, position);
  };
  let result;
  try { result = run(fixtureArgs(output)); }
  finally {
    fs.openSync = real.open;
    fs.closeSync = real.close;
    fs.writeSync = real.write;
    if (owned !== null) real.close(owned);
  }
  assert.equal(injected, 1);
  assert.equal(owned, null);
  assert.equal(result.code, 0);
  const catalog = JSON.parse(fs.readFileSync(path.join(output, 'catalog.json'), 'utf8'));
  assert.deepEqual(catalog.jobs, authored.expected.jobs);
  assert.deepEqual(catalog.targets, authored.expected.targets);
});

test('the executable entry returns the fixture status on stdout only', () => {
  const output = freshOut();
  const child = spawnSync(process.execPath, [SCRIPT, ...fixtureArgs(output)], { encoding: 'utf8', timeout: 60000 });
  assert.equal(child.status, 0);
  assert.equal(child.stderr, '');
  assert.equal(JSON.parse(child.stdout).status, 'complete');
  assert.equal(fs.existsSync(path.join(output, 'catalog.json')), true);
});

// ---- T07.007.005 bridge route ----

function corpusArgs(output, extra = [], { root = INPUT_ROOT, prof = NEW_PROFILE } = {}) {
  const report = path.join(root, newProfile.inputs['report.json'].path);
  const jobs = path.join(root, newProfile.inputs['jobs.jsonl'].path);
  return ['--input-root', root, '--profile', prof, '--report', report, '--jobs', jobs, '--output', output, ...extra];
}

function newFixtureArgs(output, extra = []) {
  return ['--input-root', INPUT_ROOT, '--profile', NEW_PROFILE, '--fixtures', FIXTURES, '--output', output, ...extra];
}

function assertRefused(result, reason) {
  assert.equal(result.code, 2);
  assert.equal(result.summary.status, 'refused');
  assert.equal(result.summary.reason, reason);
  assert.equal(result.summary.output_created, false);
}

// Independent restatement of the projection rules over the admitted rows.
function expectedFromRows(rows, roots) {
  const targets = [];
  const byHttp = new Map();
  const jobs = rows.map((row, jobIndex) => {
    if (row.kind === 'gat') return { role: null, occ: null, entries: null };
    let entries;
    let occ;
    if (row.kind === 'rsw') {
      const first = new Map();
      entries = [];
      occ = row.summary.model_dependencies.map((item, objectIndex) => {
        const logical = 'data\\model\\' + item.filename;
        if (!first.has(logical)) {
          first.set(logical, entries.length);
          entries.push({ pointer: `/summary/model_dependencies/${objectIndex}/filename`, raw: item.filename, logical });
        }
        return first.get(logical);
      });
    } else {
      occ = row.summary.texture_indexes.slice();
      entries = row.summary.textures.map((raw, index) => ({ pointer: `/summary/textures/${index}`, raw, logical: 'data\\texture\\' + raw }));
    }
    const role = row.kind === 'rsw' ? 'model' : 'ground_texture';
    entries = entries.map((entry, loaderIndex) => {
      const fm = entry.logical.trim();
      const http = fm.replace(/\\/g, '/').split('/').map((seg) => seg === '' ? seg : encodeURIComponent(seg)).join('/');
      if (!byHttp.has(http)) {
        byHttp.set(http, targets.length);
        targets.push({ index: targets.length, http_path: http, referrers: [] });
      }
      const targetIndex = byHttp.get(http);
      targets[targetIndex].referrers.push({ job_index: jobIndex, loader_index: loaderIndex, role });
      return {
        index: loaderIndex, source_name_pointer: entry.pointer, raw_name: entry.raw, logical_name: entry.logical,
        filemanager_name: fm, http_path: http, target_index: targetIndex
      };
    });
    return { role, occ, entries };
  });
  const refs = rows.map((row) => roots.flatMap((root) => ['rsw', 'gnd', 'gat']
    .filter((kind) => root.edges[kind].job_id === row.id).map((kind) => ({ root_ordinal: root.ordinal, edge_kind: kind }))));
  return {
    jobs: rows.map((row, index) => ({
      source_row_index: index, id: row.id, kind: row.kind, complete_sha256: row.complete_sha256, input_bytes: row.input_bytes,
      header_version_bytes: row.header_version_bytes, outcome: row.outcome, constructor_returned: row.constructor_returned,
      root_references: refs[index], role: jobs[index].role,
      occurrence_summary_pointer: jobs[index].role === null ? null
        : (jobs[index].role === 'model' ? '/summary/model_dependencies' : '/summary/texture_indexes'),
      occurrence_loader_indexes: jobs[index].occ, loader_entries: jobs[index].entries
    })),
    targets
  };
}

function loadCanonical() {
  const report = JSON.parse(fs.readFileSync(NEW_REPORT, 'utf8'));
  const manifest = JSON.parse(fs.readFileSync(NEW_MANIFEST, 'utf8'));
  const jobsBuffer = fs.readFileSync(NEW_JOBS);
  const rows = parseJobsJsonl(jobsBuffer, { maxRowBytes: 4194304, maxTotalBytes: 134217728 });
  const constructorProfile = JSON.parse(fs.readFileSync(path.join(REPO, newProfile.constructor_profile.path), 'utf8'));
  const hash = (buf) => crypto.createHash('sha256').update(buf).digest('hex');
  const manifestBuffer = fs.readFileSync(NEW_MANIFEST);
  const bind = {
    manifest: { abs: NEW_MANIFEST, bytes: manifestBuffer.length, sha256: hash(manifestBuffer) },
    jobs: { abs: NEW_JOBS, bytes: jobsBuffer.length, sha256: hash(jobsBuffer) },
    report_abs: NEW_REPORT,
    constructor_profile_sha256: newProfile.constructor_profile.sha256,
    summary_sha256: newProfile.summary.sha256,
    worker: newProfile.constructor_worker,
    client_source_root: path.join(INPUT_ROOT, '.tools/renewal/client-source')
  };
  return { report, manifest, rows, constructorProfile, bind };
}

test('new profile fixture route publishes the authored payload under a T07.007.005 envelope without corpus reads', () => {
  const opened = [];
  const realOpen = fs.openSync;
  fs.openSync = function (target, ...args) {
    opened.push(typeof target === 'string' ? path.resolve(target) : '');
    return realOpen(target, ...args);
  };
  const first = freshOut();
  const second = freshOut();
  let a;
  let b;
  try {
    a = run(newFixtureArgs(first));
    b = run(newFixtureArgs(second));
  } finally { fs.openSync = realOpen; }
  assert.equal(a.code, 0);
  assert.equal(b.code, 0);
  assert.equal(a.summary.mode, 'fixtures');
  const forbidden = ['jobs.jsonl', 'report.json', 'input-manifest.json', path.join('src', 'Loaders', 'World.js')];
  assert.equal(opened.some((item) => forbidden.some((name) => item.endsWith(name))), false);
  assert.equal(opened.filter((item) => item.endsWith(newProfile.constructor_worker.path)).length, 2);
  assert.equal(opened.filter((item) => item.endsWith(newProfile.constructor_producer.path)).length, 2);
  const bytesA = fs.readFileSync(path.join(first, 'catalog.json'));
  assert.deepEqual(bytesA, fs.readFileSync(path.join(second, 'catalog.json')));
  const catalog = JSON.parse(bytesA.toString('utf8'));
  assert.deepEqual(Object.keys(catalog), [
    'schema', 'task', 'mode', 'profile_sha256', 'input_pins', 'constructor_profile_sha256', 'summary_sha256',
    'constructor_task', 'constructor_worker', 'constructor_producer',
    'rule_sources', 'counts', 'roots', 'remaining_gap_root_ordinals', 'jobs', 'targets', 'limitations'
  ]);
  assert.equal(catalog.schema, 'T06-map-dependency-catalog-1');
  assert.equal(catalog.task, 'T07.007.005');
  assert.equal(catalog.profile_sha256, 'c0dccf5d0f74eecbcf772c560820dc3e0b4e5b26986243255085701136117034');
  assert.deepEqual(catalog.input_pins, { authored: newProfile.authored });
  assert.equal(catalog.constructor_profile_sha256, newProfile.constructor_profile.sha256);
  assert.equal(catalog.constructor_task, 'T07.007.004');
  assert.deepEqual(catalog.constructor_worker, newProfile.constructor_worker);
  assert.deepEqual(catalog.constructor_producer, newProfile.constructor_producer);
  assert.deepEqual(catalog.rule_sources, newProfile.rule_sources);
  assert.deepEqual(catalog.limitations, newProfile.limitations);
  assert.deepEqual({
    counts: catalog.counts, roots: catalog.roots, remaining_gap_root_ordinals: catalog.remaining_gap_root_ordinals,
    jobs: catalog.jobs, targets: catalog.targets
  }, authored.expected);
});

test('old profile envelope stays byte-identical to the preserved T06.003.003.004 fixture catalog', () => {
  const output = freshOut();
  const result = run(fixtureArgs(output));
  assert.equal(result.code, 0);
  const digest = crypto.createHash('sha256').update(fs.readFileSync(path.join(output, 'catalog.json'))).digest('hex');
  assert.equal(digest, 'd124ea94302768657d4ce06db0e8d674603691e1cecebbfe840e7a7d6e766b5f');
});

test('unknown, tampered, oversized and special profiles are refused before any input is trusted', () => {
  const flipped = path.join(TMP, 'new-profile-flipped.json');
  const bytes = Buffer.from(fs.readFileSync(NEW_PROFILE));
  bytes[bytes.indexOf('T07.007.005') + 10] ^= 1;
  fs.writeFileSync(flipped, bytes, { mode: 0o600 });
  assertRefused(run(newFixtureArgs(freshOut()).map((arg) => arg === NEW_PROFILE ? flipped : arg)), 'pin_mismatch');

  const reshaped = path.join(TMP, 'new-profile-reshaped.json');
  fs.writeFileSync(reshaped, JSON.stringify(newProfile), { mode: 0o600 });
  assertRefused(run(newFixtureArgs(freshOut()).map((arg) => arg === NEW_PROFILE ? reshaped : arg)), 'pin_mismatch');

  const oversized = path.join(TMP, 'new-profile-big.json');
  fs.writeFileSync(oversized, Buffer.concat([fs.readFileSync(NEW_PROFILE), Buffer.from(' ')]), { mode: 0o600 });
  assertRefused(run(newFixtureArgs(freshOut()).map((arg) => arg === NEW_PROFILE ? oversized : arg)), 'size_limit');

  const dir = path.join(TMP, 'profile-dir');
  fs.mkdirSync(dir, { mode: 0o700 });
  assertRefused(run(newFixtureArgs(freshOut()).map((arg) => arg === NEW_PROFILE ? dir : arg)), 'special_file_refused');

  const linked = path.join(TMP, 'new-profile-link.json');
  fs.symlinkSync(NEW_PROFILE, linked);
  assertRefused(run(newFixtureArgs(freshOut()).map((arg) => arg === NEW_PROFILE ? linked : arg)), 'symlink_refused');
});

test('actual new corpus publishes the full independently restated payload and repeats byte-identically', corpusOnly, () => {
  const first = freshOut();
  const second = freshOut();
  const a = run(corpusArgs(first));
  const b = run(corpusArgs(second));
  assert.equal(a.code, 0, a.out);
  assert.equal(b.code, 0, b.out);
  assert.equal(a.summary.status, 'complete');
  assert.equal(a.summary.mode, 'corpus');
  assert.deepEqual(a.summary.counts, newProfile.expected_counts);
  assert.ok(Buffer.byteLength(a.out) <= 4096);
  const bytesA = fs.readFileSync(path.join(first, 'catalog.json'));
  assert.deepEqual(bytesA, fs.readFileSync(path.join(second, 'catalog.json')));
  assert.equal(fs.statSync(first).mode & 0o777, 0o700);
  assert.equal(fs.statSync(path.join(first, 'catalog.json')).mode & 0o777, 0o600);
  const catalog = JSON.parse(bytesA.toString('utf8'));
  const { report, manifest, rows } = loadCanonical();
  assert.equal(catalog.task, 'T07.007.005');
  assert.equal(catalog.mode, 'corpus');
  assert.deepEqual(catalog.input_pins, { ...newProfile.inputs, constructor_manifest: newProfile.constructor_manifest });
  assert.deepEqual(catalog.counts, newProfile.expected_counts);
  assert.deepEqual(catalog.roots, report.roots);
  assert.deepEqual(catalog.remaining_gap_root_ordinals, manifest.remaining_gap_root_ordinals);
  const expected = expectedFromRows(rows, report.roots);
  assert.deepEqual(catalog.jobs, expected.jobs);
  assert.deepEqual(catalog.targets, expected.targets);
  for (const job of catalog.jobs.filter((item) => item.kind === 'gat')) {
    assert.equal(job.role, null);
    assert.equal(job.loader_entries, null);
  }
  // Generic stdout: no raw, logical or HTTP name reaches it.
  const names = catalog.jobs.flatMap((job) => (job.loader_entries || []).flatMap((entry) => [entry.raw_name, entry.http_path]));
  assert.equal(names.some((name) => name.length > 3 && a.out.includes(name)), false);
  assert.equal(a.out.includes(manifest.roots[0].name), false);
});

test('bridge admission accepts the canonical metadata and leaves the caller unchanged', corpusOnly, () => {
  const input = loadCanonical();
  const before = structuredClone(input);
  const got = admitConstructorBridge(input);
  assert.deepEqual(input, before);
  assert.equal(got.rows.length, 12);
  assert.deepEqual(got.roots, input.report.roots);
  assert.deepEqual(got.remaining_gap_root_ordinals, []);
  assert.deepEqual(buildCatalog(got).counts, newProfile.expected_counts);
});

test('bridge admission refuses every report, manifest, row and link fault', corpusOnly, () => {
  const swap = (list, i, j) => { [list[i], list[j]] = [list[j], list[i]]; };
  const cases = [
    ['report task', 'report_invalid', (x) => { x.report.task = 'T06.003.003.003'; }],
    ['report schema', 'report_invalid', (x) => { x.report.schema = 'T06-map-constructor-report-2'; }],
    ['report mode', 'report_invalid', (x) => { x.report.mode = 'fixtures'; }],
    ['manifest path', 'report_invalid', (x) => { x.report.input.path += '.other'; }],
    ['manifest bytes', 'report_invalid', (x) => { x.report.input.bytes += 1; }],
    ['manifest sha', 'report_invalid', (x) => { x.bind.manifest.sha256 = '0'.repeat(64); }],
    ['constructor profile sha', 'report_invalid', (x) => { x.report.profile_sha256 = '0'.repeat(64); }],
    ['summary sha', 'report_invalid', (x) => { x.report.summary_sha256 = '0'.repeat(64); }],
    ['worker sha', 'report_invalid', (x) => { x.report.worker.sha256 = '0'.repeat(64); }],
    ['worker path', 'report_invalid', (x) => { x.report.worker.path = 'tools/renewal/other.mjs'; }],
    ['worker unverified', 'report_invalid', (x) => { x.report.worker.verified = false; }],
    ['source dropped', 'report_invalid', (x) => { x.report.client_source.sources.pop(); }],
    ['source duplicated', 'report_invalid', (x) => { x.report.client_source.sources[8] = structuredClone(x.report.client_source.sources[0]); }],
    ['source sha', 'report_invalid', (x) => { x.report.client_source.sources[3].sha256 = '0'.repeat(64); }],
    ['source unverified', 'report_invalid', (x) => { x.report.client_source.sources[2].verified = false; }],
    ['source root', 'report_invalid', (x) => { x.report.client_source.root = '/elsewhere'; }],
    ['preservation', 'report_invalid', (x) => { x.report.pinned_inputs_identity_unchanged_after_run = false; }],
    ['cleanup unverified', 'report_invalid', (x) => { x.report.cleanup.verified = false; }],
    ['cleanup leftover', 'report_invalid', (x) => { x.report.cleanup.unverified.push(1); }],
    ['cleanup halted', 'report_invalid', (x) => { x.report.cleanup.halted = 'timeout'; }],
    ['workers started', 'report_invalid', (x) => { x.report.cleanup.workers_started = 11; }],
    ['exits observed', 'report_invalid', (x) => { x.report.cleanup.exits_observed = 11; }],
    ['records', 'report_invalid', (x) => { x.report.counts.records = 11; }],
    ['attempted', 'report_invalid', (x) => { x.report.counts.attempted = 11; }],
    ['other outcome', 'report_invalid', (x) => { x.report.counts.job_outcomes.timeout = 1; }],
    ['jobs file sha', 'report_invalid', (x) => { x.report.jobs_file.sha256 = '0'.repeat(64); }],
    ['jobs file path', 'report_invalid', (x) => { x.report.jobs_file.path = 'other.jsonl'; }],
    ['jobs file records', 'report_invalid', (x) => { x.report.jobs_file.records = 11; }],
    ['raw manifest roots as report roots', 'report_invalid', (x) => { x.report.roots = structuredClone(x.manifest.roots); }],
    ['wrong parse outcome', 'report_invalid', (x) => { x.report.roots[1].edges.gnd.parse_outcome = 'timeout'; }],
    ['changed root scope', 'report_invalid', (x) => { x.report.roots[0].ordinal_scope = 'world'; }],
    ['invented world ordinal', 'report_invalid', (x) => { x.report.roots[2].original_gap_root_ordinal = 7; }],
    ['changed parse status', 'report_invalid', (x) => { x.report.roots[3].edges.rsw.parse_status = 'returned'; }],
    ['parser flag mapping', 'report_invalid', (x) => { x.report.input_manifest.parser_execution_performed_in_input = true; }],
    ['extra preserved key', 'report_invalid', (x) => { x.report.input_manifest.extra = 1; }],
    ['changed preserved limits', 'report_invalid', (x) => { x.report.input_manifest.qualification_limits.pop(); }],
    ['changed preserved inputs', 'report_invalid', (x) => { x.report.input_manifest.inputs.patch_sha256 = '0'.repeat(64); }],
    ['manifest task', 'manifest_invalid', (x) => { x.manifest.task = 'T07.007.003'; }],
    ['manifest schema', 'manifest_invalid', (x) => { x.manifest.schema = 'other'; }],
    ['manifest counts', 'manifest_invalid', (x) => { x.manifest.counts.edge_references = 11; }],
    ['manifest job order', 'manifest_invalid', (x) => { swap(x.manifest.jobs, 0, 1); }],
    ['duplicate job id', 'manifest_invalid', (x) => { x.manifest.jobs[3].job_id = x.manifest.jobs[0].job_id; }],
    ['orphan job', 'manifest_invalid', (x) => { x.manifest.roots[1].edges.gat.job_id = x.manifest.roots[0].edges.gat.job_id; }],
    ['wrong-kind link', 'manifest_invalid', (x) => { x.manifest.roots[0].edges.rsw.job_id = x.manifest.roots[0].edges.gnd.job_id; }],
    ['missing link', 'manifest_invalid', (x) => { x.manifest.roots[0].edges.gat.job_id = 'target-999:gat'; }],
    ['bad header', 'manifest_invalid', (x) => { x.manifest.jobs[0].header.version_bytes = [1]; }],
    ['gap list', 'manifest_invalid', (x) => { x.manifest.remaining_gap_root_ordinals = [0]; }],
    ['row order', 'jobs_mismatch', (x) => { swap(x.rows, 0, 1); }],
    ['row dropped', 'jobs_mismatch', (x) => { x.rows.pop(); }],
    ['row added', 'jobs_mismatch', (x) => { x.rows.push(structuredClone(x.rows[0])); }],
    ['row sha', 'jobs_mismatch', (x) => { x.rows[4].complete_sha256 = '0'.repeat(64); }],
    ['row bytes', 'jobs_mismatch', (x) => { x.rows[5].input_bytes += 1; }],
    ['row header', 'jobs_mismatch', (x) => { x.rows[6].header_version_bytes = [1, 2]; }],
    ['row kind', 'jobs_mismatch', (x) => { x.rows[7].kind = 'rsw'; }],
    ['row id', 'jobs_mismatch', (x) => { x.rows[8].id = 'target-008:gnd'; }]
  ];
  const base = loadCanonical();
  for (const [label, reason, mutate] of cases) {
    const input = structuredClone(base);
    mutate(input);
    assert.throws(() => admitConstructorBridge(input), (error) => error.reason === reason, label);
  }
  // Row semantics masked by the immutable jobs pin are still enforced by buildCatalog.
  const input = structuredClone(base);
  input.rows[2].outcome = 'timeout';
  input.report.roots[0].edges.rsw.parse_outcome = 'timeout';
  input.report.counts.job_outcomes.returned = 12;
  assert.throws(() => buildCatalog(admitConstructorBridge(input)), (error) => error.reason === 'invalid_catalog_input');
});

test('cross-substituted profile, report and jobs paths are refused', corpusOnly, () => {
  const report = path.join(INPUT_ROOT, newProfile.inputs['report.json'].path);
  const jobs = path.join(INPUT_ROOT, newProfile.inputs['jobs.jsonl'].path);
  const swapped = corpusArgs(freshOut()).map((arg) => arg === report ? jobs : (arg === jobs ? report : arg));
  assertRefused(run(swapped), 'path_refused');
  assertRefused(run(corpusArgs(freshOut(), [], { prof: PROFILE })), 'path_refused');
  const oldReport = path.join(INPUT_ROOT, profile.inputs['report.json'].path);
  const oldJobs = path.join(INPUT_ROOT, profile.inputs['jobs.jsonl'].path);
  assertRefused(run(corpusArgs(freshOut()).map((arg) => arg === report ? oldReport : (arg === jobs ? oldJobs : arg))), 'path_refused');
  // A dot-dot spelling resolves to the same admitted file and is accepted; any other file is refused.
  const dotted = path.join(path.dirname(report), '..', 'output-1', 'report.json');
  const traversal = run(corpusArgs(freshOut()).map((arg) => arg === report ? dotted : arg));
  assert.equal(traversal.code, 0);
  const manifestAsReport = run(corpusArgs(freshOut()).map((arg) => arg === report ? NEW_MANIFEST : arg));
  assertRefused(manifestAsReport, 'path_refused');
});

// A private copy of the admitted metadata and source texts under TMP. The report still
// names the canonical manifest and client-source root, so an intact copy stops at report_invalid.
function makeShadowRoot() {
  const root = fs.mkdtempSync(path.join(TMP, 'shadow-'));
  const copy = (rel) => {
    const dest = path.join(root, rel);
    fs.mkdirSync(path.dirname(dest), { recursive: true, mode: 0o700 });
    fs.copyFileSync(path.join(INPUT_ROOT, rel), dest);
    fs.chmodSync(dest, 0o600);
  };
  const constructorProfile = JSON.parse(fs.readFileSync(path.join(REPO, newProfile.constructor_profile.path), 'utf8'));
  const sources = new Set([...Object.keys(newProfile.rule_sources), ...Object.keys(constructorProfile.sources)]);
  for (const key of sources) copy(path.join('.tools/renewal/client-source', key));
  copy(newProfile.inputs['report.json'].path);
  copy(newProfile.inputs['jobs.jsonl'].path);
  copy(newProfile.constructor_manifest.path);
  return root;
}

test('symlinked, special, resized, rehashed and missing corpus inputs are refused before publication', corpusOnly, () => {
  const intact = makeShadowRoot();
  assertRefused(run(corpusArgs(freshOut(), [], { root: intact })), 'report_invalid');

  const linked = makeShadowRoot();
  const linkedReport = path.join(linked, newProfile.inputs['report.json'].path);
  fs.rmSync(linkedReport);
  fs.symlinkSync(NEW_REPORT, linkedReport);
  assertRefused(run(corpusArgs(freshOut(), [], { root: linked })), 'symlink_refused');

  const ancestor = makeShadowRoot();
  const manifestDir = path.join(ancestor, path.dirname(newProfile.constructor_manifest.path));
  fs.renameSync(manifestDir, manifestDir + '-real');
  fs.symlinkSync(manifestDir + '-real', manifestDir);
  assertRefused(run(corpusArgs(freshOut(), [], { root: ancestor })), 'symlink_refused');

  const special = makeShadowRoot();
  const specialJobs = path.join(special, newProfile.inputs['jobs.jsonl'].path);
  fs.rmSync(specialJobs);
  fs.mkdirSync(specialJobs, { mode: 0o700 });
  assertRefused(run(corpusArgs(freshOut(), [], { root: special })), 'special_file_refused');

  const resized = makeShadowRoot();
  fs.appendFileSync(path.join(resized, newProfile.inputs['jobs.jsonl'].path), '\n');
  assertRefused(run(corpusArgs(freshOut(), [], { root: resized })), 'pin_mismatch');

  const rehashed = makeShadowRoot();
  const manifestCopy = path.join(rehashed, newProfile.constructor_manifest.path);
  const bytes = fs.readFileSync(manifestCopy);
  bytes[bytes.indexOf('T07.007.004') + 10] ^= 1;
  fs.writeFileSync(manifestCopy, bytes);
  assertRefused(run(corpusArgs(freshOut(), [], { root: rehashed })), 'pin_mismatch');

  const sourceHash = makeShadowRoot();
  const iconv = path.join(sourceHash, '.tools/renewal/client-source/src/Vendors/iconv-lite.js');
  const iconvBytes = fs.readFileSync(iconv);
  iconvBytes[0] ^= 1;
  fs.writeFileSync(iconv, iconvBytes);
  assertRefused(run(corpusArgs(freshOut(), [], { root: sourceHash })), 'pin_mismatch');

  const missing = makeShadowRoot();
  fs.rmSync(path.join(missing, newProfile.constructor_manifest.path));
  assertRefused(run(corpusArgs(freshOut(), [], { root: missing })), 'missing_input');
});

// Narrow lstat injection: once `armed()` is true, bigint lstat of `target` reports another inode.
function withDrift(target, armed, fn) {
  const real = fs.lstatSync;
  fs.lstatSync = function (file, options) {
    const st = real(file, options);
    if (options && options.bigint && path.resolve(String(file)) === target && armed()) {
      const fake = Object.create(st);
      Object.defineProperty(fake, 'ino', { value: st.ino + 1n });
      return fake;
    }
    return st;
  };
  try { return fn(); }
  finally { fs.lstatSync = real; }
}

test('manifest drift during admission refuses without output', corpusOnly, () => {
  let calls = 0;
  const output = freshOut();
  const result = withDrift(NEW_MANIFEST, () => ++calls > 1, () => run(corpusArgs(output)));
  assertRefused(result, 'identity_changed');
  assert.equal(fs.existsSync(output), false);
});

test('a late preservation failure after publication stays nonzero', corpusOnly, () => {
  const output = freshOut();
  const catalogFile = path.join(output, 'catalog.json');
  const result = withDrift(NEW_REPORT, () => fs.existsSync(catalogFile), () => run(corpusArgs(output)));
  assert.equal(result.code, 1);
  assert.equal(result.summary.status, 'error');
  assert.equal(result.summary.reason, 'identity_changed');
  assert.equal(result.summary.output_created, true);
  assert.equal(fs.existsSync(catalogFile), true);
});

test('new corpus output sentinel, lower and raised budgets', corpusOnly, () => {
  const existing = freshOut();
  fs.mkdirSync(existing, { mode: 0o700 });
  fs.writeFileSync(path.join(existing, 'keep.txt'), 'preserve', { mode: 0o600 });
  assertRefused(run(corpusArgs(existing)), 'output_exists');
  assert.deepEqual(fs.readdirSync(existing), ['keep.txt']);
  assert.equal(fs.readFileSync(path.join(existing, 'keep.txt'), 'utf8'), 'preserve');

  const full = freshOut();
  assert.equal(run(corpusArgs(full)).code, 0);
  const size = fs.statSync(path.join(full, 'catalog.json')).size;
  const low = freshOut();
  assertRefused(run(corpusArgs(low, ['--max-output-bytes', String(size - 1)])), 'output_budget');
  assert.equal(fs.existsSync(low), false);
  const exact = freshOut();
  assert.equal(run(corpusArgs(exact, ['--max-output-bytes', String(size)])).code, 0);
  assert.deepEqual(fs.readFileSync(path.join(exact, 'catalog.json')), fs.readFileSync(path.join(full, 'catalog.json')));
  assertRefused(run(corpusArgs(freshOut(), ['--max-output-bytes', String(newProfile.policy.max_catalog_bytes + 1)])), 'policy_increase');
});

// Wraps fs calls on the catalog.json descriptor only.
function withCatalogFd(hooks, fn) {
  const real = { open: fs.openSync, close: fs.closeSync, write: fs.writeSync, fsync: fs.fsyncSync };
  const state = { fd: null, writes: 0 };
  fs.openSync = function (target, ...args) {
    const fd = real.open(target, ...args);
    if (typeof target === 'string' && path.basename(target) === 'catalog.json') state.fd = fd;
    return fd;
  };
  fs.writeSync = function (fd, buffer, offset, length, position) {
    if (fd !== state.fd || !hooks.write) return real.write(fd, buffer, offset, length, position);
    state.writes += 1;
    return hooks.write(state, () => real.write(fd, buffer, offset, length, position), (n) => real.write(fd, buffer, offset, n, position));
  };
  fs.fsyncSync = function (fd) {
    if (fd === state.fd && hooks.fsync) return hooks.fsync();
    return real.fsync(fd);
  };
  fs.closeSync = function (fd) {
    const result = real.close(fd);
    const mine = fd === state.fd;
    if (mine) state.fd = null;
    if (mine && hooks.close) hooks.close();
    return result;
  };
  try { return { result: fn(), state }; }
  finally {
    Object.assign(fs, { openSync: real.open, closeSync: real.close, writeSync: real.write, fsyncSync: real.fsync });
    if (state.fd !== null) real.close(state.fd);
  }
}

test('new corpus short, zero, fsync and close write faults', corpusOnly, () => {
  const reference = freshOut();
  assert.equal(run(corpusArgs(reference)).code, 0);
  const expected = fs.readFileSync(path.join(reference, 'catalog.json'));

  const shortOut = freshOut();
  const short = withCatalogFd({ write: (s, full, part) => s.writes === 1 ? part(7) : full() }, () => run(corpusArgs(shortOut)));
  assert.equal(short.result.code, 0);
  assert.ok(short.state.writes > 1);
  assert.deepEqual(fs.readFileSync(path.join(shortOut, 'catalog.json')), expected);

  const zero = withCatalogFd({ write: (s) => { if (s.writes > 1) throw new Error('retried'); return 0; } }, () => run(corpusArgs(freshOut())));
  assert.equal(zero.state.writes, 1);
  assert.equal(zero.state.fd, null);
  assert.equal(zero.result.code, 1);
  assert.equal(zero.result.summary.reason, 'output_io_error');
  assert.equal(zero.result.summary.output_created, true);

  const failing = (label) => { const error = new Error(label); error.code = 'EIO'; throw error; };
  const fsync = withCatalogFd({ fsync: () => failing('fsync') }, () => run(corpusArgs(freshOut())));
  assert.equal(fsync.state.fd, null);
  assert.equal(fsync.result.code, 1);
  assert.equal(fsync.result.summary.status, 'error');
  assert.equal(fsync.result.summary.output_created, true);

  const close = withCatalogFd({ close: () => failing('close') }, () => run(corpusArgs(freshOut())));
  assert.equal(close.result.code, 1);
  assert.equal(close.result.summary.status, 'error');
  assert.equal(close.result.summary.output_created, true);
});

test('the executable entry on the new corpus route writes one generic stdout line and no stderr', corpusOnly, () => {
  const output = freshOut();
  const child = spawnSync(process.execPath, [SCRIPT, ...corpusArgs(output)], { encoding: 'utf8', timeout: 60000 });
  assert.equal(child.status, 0);
  assert.equal(child.stderr, '');
  assert.equal(child.stdout.split('\n').filter(Boolean).length, 1);
  assert.ok(Buffer.byteLength(child.stdout) <= 4096);
  assert.equal(JSON.parse(child.stdout).status, 'complete');
  assert.equal(child.stdout.includes('\\'), false);
  assert.equal(child.stdout.includes(INPUT_ROOT), false);
});
