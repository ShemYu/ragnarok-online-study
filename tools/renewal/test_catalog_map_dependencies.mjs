// Controls for T06.003.003.004. Run from the child checkout:
//   node --test tools/renewal/test_catalog_map_dependencies.mjs
// Fixture mode reads the pinned profile, summary and three rule sources.
// It does not open the production jobs or report. Temp directories under
// .tools/renewal/t06-004-candidate-1 are removed after the file finishes.
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { buildCatalog, main, parseJobsJsonl, safeJoin, writeAll } from './catalog_map_dependencies.mjs';

process.umask(0o077);
const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, '..', '..');
const INPUT_ROOT = process.env.T06_INPUT_ROOT || path.resolve(REPO, '..', 'reverse-the-Ragnarok-Online-to-play-by-myself');
const PROFILE = path.join(REPO, 'docs/project/fixtures/T06.003.003.004-profile.json');
const FIXTURES = path.join(REPO, 'docs/project/fixtures/T06.003.003.004-authored.json');
const SCRIPT = path.join(HERE, 'catalog_map_dependencies.mjs');
const profile = JSON.parse(fs.readFileSync(PROFILE, 'utf8'));
const authored = JSON.parse(fs.readFileSync(FIXTURES, 'utf8'));
const PRIVATE = path.join(REPO, '.tools', 'renewal', 't06-004-candidate-1');
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
