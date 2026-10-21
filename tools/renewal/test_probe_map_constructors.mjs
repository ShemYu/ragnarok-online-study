// Runner controls for T06.003.003.003. Run with:
//   T06_INPUT_ROOT=/canonical/repository node --experimental-vm-modules --test tools/renewal/test_probe_map_constructors.mjs
// Uses only the frozen authored fixtures and synthetic temp files; never opens retained game bodies.
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { EventEmitter } from 'node:events';
import vm from 'node:vm';
import { main, writeAll, boundedRow, corpusRoots, effectivePolicy, manifestJobs, profileEntryFor, PROFILE_ALLOWLIST, readJobBody, readPinnedFile, Refusal, runWorkerJob, safeJoin, validateProfile } from './probe_map_constructors.mjs';
import { createRealm, MODULE_KEYS, resolveSpecifier } from './map_constructor_worker.mjs';

process.umask(0o077);
const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, '..', '..');
const INPUT_ROOT = process.env.T06_INPUT_ROOT ||
  path.resolve(REPO, '..', 'reverse-the-Ragnarok-Online-to-play-by-myself');
const CLIENT = path.join(INPUT_ROOT, '.tools', 'renewal', 'client-source');
const PROFILE = path.join(REPO, 'docs/project/fixtures/T06.003.003.003-profile.json');
const NEW_PROFILE = path.join(REPO, 'docs/project/fixtures/T07.007.004-profile.json');
const FIXTURES = path.join(REPO, 'docs/project/fixtures/T06.003.003.003-authored.json');
const NEW_MANIFEST = path.join(INPUT_ROOT, '.tools/renewal/t07-007-004-constructor-input-1/input-manifest.json');
const SCRIPT = path.join(HERE, 'probe_map_constructors.mjs');
const profile = JSON.parse(fs.readFileSync(PROFILE, 'utf8'));
const newProfile = JSON.parse(fs.readFileSync(NEW_PROFILE, 'utf8'));
const authored = JSON.parse(fs.readFileSync(FIXTURES, 'utf8'));
// Private temp state stays below this checkout's ignored .tools/renewal (0700).
const PRIVATE = path.join(REPO, '.tools', 'renewal', 't06-constructor-candidate-1');
fs.mkdirSync(PRIVATE, { recursive: true, mode: 0o700 });
const TMP = fs.mkdtempSync(path.join(fs.realpathSync(PRIVATE), 'test-tmp-'));
test.after(() => fs.rmSync(TMP, { recursive: true, force: true }));
let seq = 0;
const freshOut = () => path.join(TMP, `out-${++seq}`);

function cli(extra, { profile: prof = PROFILE, client = CLIENT, output = freshOut(), mode = ['--fixtures', FIXTURES] } = {}) {
  const r = spawnSync(process.execPath, ['--experimental-vm-modules', '--no-warnings', SCRIPT, '--input-root', INPUT_ROOT,
    '--client-source', client, '--profile', prof, ...mode, '--output', output, ...extra], { encoding: 'utf8', timeout: 120000 });
  const lines = r.stdout.trim().split('\n');
  assert.equal(lines.length, 1, 'stdout is one bounded summary line');
  assert.ok(r.stdout.length <= 4097);
  return { code: r.status, summary: JSON.parse(lines[0]), output };
}
const rows = (out) => fs.readFileSync(path.join(out, 'jobs.jsonl'), 'utf8').trim().split('\n').map((l) => JSON.parse(l));
const report = (out) => JSON.parse(fs.readFileSync(path.join(out, 'report.json'), 'utf8'));
const ROW_KEYS = ['id', 'kind', 'complete_sha256', 'input_bytes', 'header_version_bytes', 'outcome', 'constructor_returned', 'elapsed_ms', 'cleanup'];

test('fresh fixture CLI: all 26 outcomes and full common-summary dictionaries match authored values', () => {
  const r = cli([]);
  assert.equal(r.code, 0);
  assert.equal(r.summary.status, 'complete');
  const got = rows(r.output);
  assert.equal(got.length, 26);
  let returned = 0, exceptions = 0;
  authored.cases.forEach((c, i) => {
    const row = got[i];
    for (const k of ROW_KEYS) assert.ok(k in row, `${c.id} has ${k}`);
    assert.equal(row.id, c.id);
    const bytes = Buffer.from(c.hex, 'hex');
    assert.equal(row.complete_sha256, crypto.createHash('sha256').update(bytes).digest('hex'));
    assert.equal(row.input_bytes, bytes.length);
    assert.equal(row.outcome, c.expected.outcome, c.id);
    assert.equal(row.worker_started, true);
    assert.equal(row.cleanup.exit_observed, true);
    if (c.expected.outcome === 'returned') {
      returned++;
      assert.equal(row.constructor_returned, true);
      assert.deepStrictEqual(row.summary, c.expected.summary, c.id);
    } else {
      exceptions++;
      assert.equal(row.constructor_returned, false);
      assert.equal(row.exception.phase, 'constructor');
      assert.equal(row.exception.name, c.expected.exception_name, c.id);
      assert.ok(!('summary' in row));
    }
  });
  assert.deepEqual([returned, exceptions], [17, 9]);
  const rep = report(r.output);
  assert.equal(rep.schema, 'T06-map-constructor-report-1');
  assert.equal(rep.task, 'T06.003.003.003');
  assert.equal(Object.hasOwn(rep, 'worker'), false);
  assert.equal(rep.mode, 'fixtures');
  assert.deepEqual(rep.roots, []);
  assert.equal(rep.profile_sha256, 'b6635a65db373f5240112734e1f51311851101603323fe1d5300dfaa1c74cf5c');
  assert.equal(rep.summary_sha256, profile.summary.sha256);
  assert.equal(rep.client_source.sources.length, 9);
  assert.ok(rep.client_source.sources.every((s) => s.verified && s.sha256 === profile.sources[s.path].sha256));
  assert.equal(rep.authored_comparison.matched, 26);
  assert.equal(rep.cleanup.verified, true);
  assert.equal(rep.counts.job_outcomes.returned, 17);
  const jobsBuf = fs.readFileSync(path.join(r.output, 'jobs.jsonl'));
  assert.equal(rep.jobs_file.bytes, jobsBuf.length);
  assert.equal(rep.jobs_file.sha256, crypto.createHash('sha256').update(jobsBuf).digest('hex'));
  assert.equal(fs.statSync(r.output).mode & 0o777, 0o700);
  for (const f of fs.readdirSync(r.output)) assert.equal(fs.statSync(path.join(r.output, f)).mode & 0o777, 0o600, f);
  assert.ok(rep.rss_sampling.samples >= 26 && rep.rss_sampling.peak_rss_bytes > 0);
  for (const forbidden of ['playable', 'format_valid', 'episode_complete']) assert.ok(!(forbidden in rep));
});

test('existing output is refused and left unchanged', () => {
  const out = freshOut();
  fs.mkdirSync(out); fs.writeFileSync(path.join(out, 'keep'), 'sentinel');
  const r = cli([], { output: out });
  assert.equal(r.code, 2);
  assert.equal(r.summary.reason, 'output_exists');
  assert.deepEqual(fs.readdirSync(out), ['keep']);
  assert.equal(fs.readFileSync(path.join(out, 'keep'), 'utf8'), 'sentinel');
});

test('profile pin mismatch and symlinked profile refuse before creating output', () => {
  const changed = path.join(TMP, 'profile-changed.json');
  fs.writeFileSync(changed, fs.readFileSync(PROFILE, 'utf8') + ' ');
  let r = cli([], { profile: changed });
  assert.equal(r.code, 2); assert.equal(r.summary.reason, 'pin_mismatch'); assert.ok(!fs.existsSync(r.output));
  const link = path.join(TMP, 'profile-link.json');
  fs.symlinkSync(PROFILE, link);
  r = cli([], { profile: link });
  assert.equal(r.code, 2); assert.equal(r.summary.reason, 'symlink_refused'); assert.ok(!fs.existsSync(r.output));
});

test('symlinked client-source module is refused (no link following)', () => {
  const fake = path.join(TMP, 'client-links');
  for (const key of MODULE_KEYS) {
    fs.mkdirSync(path.dirname(path.join(fake, key)), { recursive: true });
    fs.symlinkSync(path.join(CLIENT, key), path.join(fake, key));
  }
  const r = cli([], { client: fake });
  assert.equal(r.code, 2); assert.equal(r.summary.reason, 'symlink_refused'); assert.ok(!fs.existsSync(r.output));
});

test('mode selection and lower-only caps', () => {
  let r = cli(['--job-timeout-ms', '20001']);
  assert.equal(r.code, 2); assert.equal(r.summary.reason, 'policy_increase');
  r = cli(['--max-jobs', '27']);
  assert.equal(r.code, 2); assert.equal(r.summary.reason, 'policy_increase');
  r = cli(['--rss-limit-bytes', '0']);
  assert.equal(r.code, 2); assert.equal(r.summary.reason, 'policy_invalid');
  r = cli([], { mode: [] });
  assert.equal(r.code, 2); assert.equal(r.summary.reason, 'usage');
  r = cli(['--manifest', FIXTURES]);
  assert.equal(r.code, 2); assert.equal(r.summary.reason, 'usage');
  assert.throws(() => effectivePolicy(profile.policy, { run_timeout_ms: profile.policy.run_timeout_ms + 1 }, 5), Refusal);
  assert.equal(effectivePolicy(profile.policy, { run_timeout_ms: 5 }, 5).run_timeout_ms, 5);
});

test('--max-jobs truncation records explicit unattempted rows and exits nonzero', () => {
  const r = cli(['--max-jobs', '3']);
  assert.equal(r.code, 1);
  const got = rows(r.output);
  assert.equal(got.length, 26);
  assert.ok(got.slice(0, 3).every((x) => x.worker_started && x.cleanup.exit_observed === true));
  for (const x of got.slice(3)) {
    assert.equal(x.outcome, 'unattempted'); assert.equal(x.reason, 'max_jobs');
    assert.equal(x.worker_started, false); assert.equal(x.cleanup.exit_observed, null); assert.equal(x.constructor_returned, null);
  }
  assert.equal(report(r.output).counts.job_outcomes.unattempted, 23);
});

test('real job timeout terminates the worker and positively observes exit before the next job', () => {
  const r = cli(['--job-timeout-ms', '1', '--max-jobs', '2']);
  assert.equal(r.code, 1);
  const got = rows(r.output);
  for (const x of got.slice(0, 2)) {
    assert.equal(x.outcome, 'timeout'); assert.equal(x.reason, 'job_timeout');
    assert.equal(x.cleanup.terminated_by_parent, true); assert.equal(x.cleanup.exit_observed, true);
    assert.ok(!('summary' in x));
  }
  assert.equal(report(r.output).cleanup.verified, true);
});

test('run deadline halts with explicit unattempted rows', () => {
  const r = cli(['--run-timeout-ms', '1']);
  assert.equal(r.code, 1);
  const got = rows(r.output);
  assert.equal(got.length, 26);
  assert.ok(['timeout', 'unattempted'].includes(got[0].outcome));
  for (const x of got.slice(1)) { assert.equal(x.outcome, 'unattempted'); assert.equal(x.reason, 'run_deadline'); }
});

test('RSS refusal terminates and observes exit; lowered JSON cap yields summary_limit without summaries', () => {
  let r = cli(['--rss-limit-bytes', '1', '--max-jobs', '1']);
  assert.equal(r.code, 1);
  let got = rows(r.output);
  assert.equal(got[0].outcome, 'resource_refusal'); assert.equal(got[0].reason, 'rss_limit');
  assert.equal(got[0].cleanup.exit_observed, true);
  r = cli(['--max-job-json-bytes', '10']);
  assert.equal(r.code, 2); assert.equal(r.summary.reason, 'output_budget');
  assert.equal(fs.existsSync(r.output), false, 'impossible accounting cap refuses before output');
  r = cli(['--max-job-json-bytes', '1595']);
  assert.equal(r.code, 1); got = rows(r.output);
  const lines = fs.readFileSync(path.join(r.output, 'jobs.jsonl')).toString('utf8').trimEnd().split('\n');
  assert.equal(lines.length, 26); assert.ok(lines.every(x => Buffer.byteLength(x) <= 1595));
  assert.ok(got.some(x => x.outcome === 'summary_limit'));
  authored.cases.forEach((c, i) => {
    const x = got[i];
    assert.equal(x.id, c.id); assert.equal(x.cleanup.exit_observed, true);
    if (x.outcome === 'returned') assert.deepEqual(x.summary, c.expected.summary);
    else {
      assert.ok(!('summary' in x));
      assert.equal(x.outcome, c.expected.outcome === 'returned' ? 'summary_limit' : 'constructor_exception');
    }
  });
});

test('real pinned constructors: cross-realm refusal, offset-view hazard, exact same-realm copy succeeds', async () => {
  const sources = {};
  for (const key of MODULE_KEYS) {
    const pin = profile.sources[key];
    sources[key] = readPinnedFile(path.join(CLIENT, key), { label: key, maxBytes: pin.bytes, expectBytes: pin.bytes, expectSha: pin.sha256 }).buffer.toString('utf8');
  }
  const { summarizeConstructor } = await import('./map_constructor_summary.mjs');
  const realm = await createRealm(sources);
  assert.equal(realm.loaded.length, 9);
  assert.deepEqual([...realm.seekGlobals], [1, 2, 3]);
  const vm = await import('node:vm');
  assert.equal(vm.runInContext('typeof process + typeof require + typeof Buffer + typeof fetch', realm.context),
    'undefinedundefinedundefinedundefined');
  for (const id of ['gat-valid', 'gnd-valid', 'rsw27-model']) {
    const c = authored.cases.find((x) => x.id === id);
    const bytes = Buffer.from(c.hex, 'hex');
    const name = { rsw: 'World', gnd: 'Ground', gat: 'Altitude' }[c.kind];
    // Host-realm ArrayBuffer fails the VM-realm instanceof check: a source hazard, not bad content.
    assert.throws(() => realm.construct(name, new Uint8Array(bytes).buffer, 1000), (e) => /Undefined buffer type/.test(e.message));
    // A same-realm view with a byteOffset is read from the underlying buffer start.
    const view = realm.offsetView(bytes, 7, 0x41);
    let viewResult;
    try { viewResult = JSON.stringify(summarizeConstructor(c.kind, realm.construct(name, view, 1000))); } catch (e) { viewResult = e.name; }
    assert.equal(viewResult, 'Error', `${id} offset view reads padding as the header`);
    const exact = realm.construct(name, realm.exactBuffer(bytes), 1000);
    assert.deepStrictEqual(JSON.parse(JSON.stringify(summarizeConstructor(c.kind, exact))), c.expected.summary);
  }
});

test('closed linker resolves only the nine pinned modules', () => {
  assert.equal(resolveSpecifier('Utils/BinaryReader.js', 'src/Loaders/World.js'), 'src/Utils/BinaryReader.js');
  assert.equal(resolveSpecifier('./Struct.js', 'src/Utils/BinaryReader.js'), 'src/Utils/Struct.js');
  for (const bad of ['Loaders/GameFile.js', 'node:fs', 'fs', '../../etc/passwd', 'Utils/../../x.js', 'https://x/y.js']) {
    assert.throws(() => resolveSpecifier(bad, 'src/Loaders/World.js'), bad);
  }
});

test('corpus helpers: body pins, traversal/symlink/special refusal and edge parse_outcome mapping (synthetic)', () => {
  const root = path.join(TMP, 'corpus'); fs.mkdirSync(path.join(root, 'b'), { recursive: true });
  const body = Buffer.from('GRAT synthetic');
  fs.writeFileSync(path.join(root, 'b', 'ok.bin'), body);
  fs.symlinkSync(path.join(root, 'b', 'ok.bin'), path.join(root, 'b', 'link.bin'));
  const sha = crypto.createHash('sha256').update(body).digest('hex');
  const pol = profile.policy;
  const job = (p, extra = {}) => ({ body_path: p, input_bytes: body.length, complete_sha256: sha, ...extra });
  assert.equal(readJobBody(root, job('b/ok.bin'), pol).sha256, sha);
  const reason = (j) => { try { readJobBody(root, j, pol); return 'accepted'; } catch (e) { return e.reason; } };
  assert.equal(reason(job('../x')), 'path_refused');
  assert.equal(reason(job('/etc/hosts')), 'path_refused');
  assert.equal(reason(job('b/./ok.bin')), 'path_refused');
  assert.equal(reason(job('b/link.bin')), 'symlink_refused');
  assert.equal(reason(job('b')), 'special_file_refused');
  assert.equal(reason(job('b/ok.bin', { input_bytes: body.length + 1 })), 'pin_mismatch');
  assert.equal(reason(job('b/ok.bin', { complete_sha256: '0'.repeat(64) })), 'pin_mismatch');
  assert.equal(reason(job('b/ok.bin', { input_bytes: pol.max_body_bytes + 1 })), 'size_limit');
  assert.throws(() => safeJoin(root, 'a\\b', 'x'), Refusal);
  const mk = (id, kind) => ({ job_id: id, kind, complete_sha256: (kind === 'rsw' ? 'a' : 'b').repeat(64), bytes: 1, body_path: 'b/ok.bin', header: { version_bytes: [2, 1] } });
  const roots = [{ ordinal: 0, name: 'm', extra: { keep: 1 }, edges: { rsw: { job_id: 'j1', parse_status: 'not_run' }, gnd: { job_id: null, parse_status: 'x' }, gat: { job_id: 'j2' } } }];
  const prof = { counts: { jobs: 2, roots: 1, edge_references: 2 } };
  const doc = { schema: 'T06-map-constructor-input-1', jobs: [mk('j1', 'rsw'), mk('j2', 'gat')], roots };
  assert.deepEqual(manifestJobs(doc, prof).map((j) => j.header_version_bytes), [[2, 1], [2, 1]]);
  assert.throws(() => manifestJobs({ ...doc, jobs: [mk('j1', 'rsw'), mk('j1', 'gat')] }, prof), Refusal);
  assert.throws(() => manifestJobs({ ...doc, roots: [{ ...roots[0], edges: { ...roots[0].edges, gat: { job_id: 'j1' } } }] }, prof), Refusal);
  const mapped = corpusRoots(doc, new Map([['j1', 'returned'], ['j2', 'constructor_exception']]));
  assert.equal(mapped[0].edges.rsw.parse_outcome, 'returned');
  assert.equal(mapped[0].edges.rsw.parse_status, 'not_run');
  assert.equal(mapped[0].edges.gnd.parse_outcome, 'unavailable_from_observation');
  assert.equal(mapped[0].edges.gat.parse_outcome, 'constructor_exception');
  assert.deepEqual(mapped[0].extra, { keep: 1 });
  assert.ok(!('parse_outcome' in roots[0].edges.rsw), 'input roots are not mutated');
});

// Root regressions for independently reproduced raw-runner failures.
test('opened input growth is refused before allocation/read and closes the fd', () => {
  const file = path.join(TMP, 'growth-at-open.bin'), initial = Buffer.from('0123456789abcdef');
  const tail = Buffer.from('x'.repeat(48)), cap = 32;
  fs.writeFileSync(file, initial, { mode: 0o600, flag: 'wx' });
  const options = { label: 'authored growth', maxBytes: cap, expectBytes: initial.length,
    expectSha: crypto.createHash('sha256').update(initial).digest('hex') };
  assert.equal(readPinnedFile(file, options).bytes, initial.length);
  const real = { open: fs.openSync, close: fs.closeSync, read: fs.readSync,
    append: fs.appendFileSync, alloc: Buffer.alloc };
  let armed = true, injection = 0, fd = null, closed = false, overCap = 0, reads = 0, caught;
  fs.openSync = function (p, ...args) {
    if (typeof p === 'string' && path.resolve(p) === file && armed) {
      armed = false; injection++; real.append(file, tail); // Before delegating; same inode.
      fd = real.open(p, ...args); return fd;
    }
    return real.open(p, ...args);
  };
  fs.closeSync = function (n) { const r = real.close(n); if (n === fd) closed = true; return r; };
  fs.readSync = function (n, ...args) { if (n === fd) reads++; return real.read(n, ...args); };
  Buffer.alloc = function (n, ...args) { if (n > cap) overCap++; return real.alloc(n, ...args); };
  try { readPinnedFile(file, options); } catch (e) { caught = e; }
  finally {
    fs.openSync = real.open; fs.closeSync = real.close; fs.readSync = real.read; Buffer.alloc = real.alloc;
    if (fd !== null && !closed) real.close(fd); // Harness action, never candidate credit.
  }
  assert.ok(caught instanceof Refusal); assert.equal(injection, 1); assert.notEqual(fd, null);
  assert.equal(overCap, 0); assert.equal(reads, 0); assert.equal(closed, true);
});

test('output ancestor link is refused without writing through it', () => {
  const realDir = path.join(TMP, 'ancestor-real'), alias = path.join(TMP, 'ancestor-alias');
  fs.mkdirSync(realDir, { mode: 0o700 });
  const sentinel = path.join(realDir, 'sentinel'); fs.writeFileSync(sentinel, 'preserve', { mode: 0o600, flag: 'wx' });
  const before = fs.statSync(sentinel).mode;
  fs.symlinkSync(realDir, alias);
  const r = cli(['--max-jobs', '0'], { output: path.join(alias, 'new', 'output') });
  assert.notEqual(r.code, 0); assert.equal(r.summary.status, 'refused');
  assert.equal(r.summary.output_created, false);
  assert.deepEqual(fs.readdirSync(realDir), ['sentinel']);
  assert.equal(fs.readFileSync(sentinel, 'utf8'), 'preserve');
  assert.equal(fs.statSync(sentinel).mode, before); assert.equal(fs.readlinkSync(alias), realDir);
});

test('writeAll retries positive short writes and refuses zero progress immediately', () => {
  const file = path.join(TMP, 'write-all.bin'), fd = fs.openSync(file, 'wx+', 0o600);
  const realWrite = fs.writeSync, payload = Buffer.from('許 authored\n', 'utf8');
  let calls = 0;
  try {
    fs.writeSync = function (n, buffer, offset, length, position) {
      if (n !== fd) return realWrite(n, buffer, offset, length, position);
      calls++; return realWrite(n, buffer, offset, Math.min(3, length), position);
    };
    writeAll(fd, payload); assert.ok(calls > 1);
    assert.deepEqual(fs.readFileSync(file), payload);
    fs.ftruncateSync(fd, 0); calls = 0;
    fs.writeSync = function (n, ...args) {
      if (n !== fd) return realWrite(n, ...args);
      if (++calls > 1) throw Error('safety guard: retried after zero progress');
      return 0; // A broken loop fails on attempt two rather than hanging this test process.
    };
    assert.throws(() => writeAll(fd, payload), Refusal);
    assert.equal(calls, 1); assert.equal(fs.statSync(file).size, 0);
  } finally { fs.writeSync = realWrite; fs.closeSync(fd); }
});

test('boundedRow limits the full envelope without mutating or truncating the summary', () => {
  const row = { id: 'authored-cap', kind: 'gnd', complete_sha256: '0'.repeat(64), input_bytes: 1,
    header_version_bytes: [1, 7], outcome: 'returned', constructor_returned: true, elapsed_ms: 0,
    worker_started: true, cleanup: { exit_observed: true }, _log: '',
    _summary_json: JSON.stringify({ declared_textures: ['許'.repeat(1000)] }) };
  const before = JSON.stringify(row), cap = 700;
  const got = boundedRow(row, { ...profile.policy, max_job_json_bytes: cap }, 0);
  assert.ok(Buffer.byteLength(got.line, 'utf8') <= cap);
  assert.deepEqual(JSON.parse(got.line), got.row); assert.equal(got.row.outcome, 'summary_limit');
  assert.equal(got.row.constructor_returned, true); assert.ok(!('summary' in got.row));
  assert.equal(got.logBytes, 0); assert.equal(JSON.stringify(row), before);
});

for (const fault of ['jobs:fchmod', 'jobs:fsync', 'jobs:write', 'report:fchmod', 'report:fsync', 'report:write']) {
  test(`main releases owned fds/sampler after one ${fault} EIO`, async () => {
    const output = freshOut(), [kind, operation] = fault.split(':');
    const targets = new Map([[path.join(output, 'jobs.jsonl'), 'jobs'], [path.join(output, 'report.json'), 'report']]);
    const real = { open: fs.openSync, close: fs.closeSync, stat: fs.fstatSync, chmod: fs.fchmodSync,
      sync: fs.fsyncSync, write: fs.writeSync, interval: globalThis.setInterval, clear: globalThis.clearInterval };
    const fds = new Map(), timers = new Set();
    let injected = 0, timersCreated = 0, code, error, stdout = '', before, foreign = 0;
    const identity = n => { const s = real.stat(n, { bigint: true }); return { dev: s.dev, ino: s.ino }; };
    const same = (n, own) => { try { const s = identity(n); return s.dev === own.dev && s.ino === own.ino; } catch { return false; } };
    const inject = (op, n) => {
      const own = fds.get(n);
      if (!injected && op === operation && own?.kind === kind && same(n, own)) {
        injected++; const e = Error(`authored ${fault} EIO`); e.code = 'EIO'; throw e;
      }
    };
    fs.openSync = function (p, ...args) {
      const n = real.open(p, ...args), k = typeof p === 'string' ? targets.get(path.resolve(p)) : null;
      if (k) fds.set(n, { ...identity(n), kind: k });
      return n;
    };
    fs.closeSync = function (n) {
      const own = fds.get(n); if (own && !same(n, own)) foreign++;
      const r = real.close(n); fds.delete(n); return r;
    };
    fs.fchmodSync = function (n, ...args) { inject('fchmod', n); return real.chmod(n, ...args); };
    fs.fsyncSync = function (n, ...args) { inject('fsync', n); return real.sync(n, ...args); };
    fs.writeSync = function (n, ...args) { inject('write', n); return real.write(n, ...args); };
    globalThis.setInterval = function (fn, ms, ...args) {
      const h = real.interval(fn, ms, ...args); timers.add(h); timersCreated++; return h;
    };
    globalThis.clearInterval = function (h) { const r = real.clear(h); timers.delete(h); return r; };
    try {
      // Only transient jobs-write needs one real authored worker; all other faults need none.
      code = await main(['--input-root', INPUT_ROOT, '--client-source', CLIENT, '--profile', PROFILE,
        '--fixtures', FIXTURES, '--output', output, '--max-jobs', fault === 'jobs:write' ? '1' : '0'],
      { stdout: { write: s => { stdout += String(s); } } });
    } catch (e) { error = e; }
    finally {
      // Freeze observations before harness cleanup. Never credit the operations below to main.
      before = { open: [...fds].filter(([n, own]) => same(n, own)).length, tracked: fds.size, timers: timers.size };
      try {
        for (const h of timers) real.clear(h);
        for (const [n, own] of fds) if (same(n, own)) real.close(n);
      } finally {
        fs.openSync = real.open; fs.closeSync = real.close; fs.fchmodSync = real.chmod;
        fs.fsyncSync = real.sync; fs.writeSync = real.write;
        globalThis.setInterval = real.interval; globalThis.clearInterval = real.clear;
      }
    }
    assert.equal(injected, 1); assert.equal(foreign, 0);
    assert.deepEqual(before, { open: 0, tracked: 0, timers: 0 });
    if (fault !== 'jobs:fchmod') assert.ok(timersCreated > 0, 'sampler observation was exercised');
    assert.ok(!stdout.split('\n').filter(Boolean).some(s => JSON.parse(s).status === 'complete'));
    if (fault === 'jobs:write') {
      assert.equal(error, undefined); assert.equal(code, 1);
      const got = rows(output), rep = report(output), bytes = fs.readFileSync(path.join(output, 'jobs.jsonl'));
      assert.equal(got.length, authored.cases.length); assert.equal(got[0].outcome, 'environment_failure');
      assert.equal(got[0].reason, 'output_io_error'); assert.ok(!('summary' in got[0]));
      assert.equal(got[0].worker_started, true); assert.equal(got[0].cleanup.exit_observed, true);
      assert.ok(got.slice(1).every(x => x.outcome === 'unattempted'));
      assert.equal(rep.cleanup.halted, 'output_io_error'); assert.equal(rep.cleanup.verified, true);
      assert.equal(rep.jobs_file.records, got.length); assert.equal(rep.jobs_file.bytes, bytes.length);
      assert.equal(rep.jobs_file.sha256, crypto.createHash('sha256').update(bytes).digest('hex'));
    } else {
      // --max-jobs 0 alone is nonzero: actual EIO rejection proves this fault was not a false pass.
      assert.equal(error?.code, 'EIO'); assert.equal(code, undefined);
    }
  });
}

// Exact parent with only Worker replaced; these exits test event ordering only.
// Actual Worker cleanup remains covered by the independent fixture/timeout tests.
test('worker failures stay latched after late results, errors, RSS and nonzero exits', async () => {
  let current;
  const workerURL = pathToFileURL(path.join(HERE, 'map_constructor_worker.mjs'));
  const parentURL = pathToFileURL(SCRIPT);
  const message = { type: 'result', outcome: 'returned', constructor_returned: true,
    summary_json: '{}', summary_json_bytes: 2, log: { text: '', dropped: 0 } };
  class FakeWorker extends EventEmitter {
    constructor(url, options) {
      super(); assert.equal(String(url), workerURL.href);
      const deadline = options.workerData.deadline_epoch_ms;
      this.case = current; this.exited = false;
      this.stdout = { resume() {} }; this.stderr = new EventEmitter();
      queueMicrotask(() => {
        this.emit('message', { type: 'phase', phase: 'constructor' });
        if (this.case.id === 'timeout') return;
        if (this.case.id === 'overdue-message') {
          const guard = performance.now() + 50;
          while (Date.now() < deadline && performance.now() < guard) { /* finite authored event-loop delay */ }
          assert.ok(Date.now() >= deadline);
        }
        this.emit('message', message);
        if (this.case.id === 'overdue-message') this.exit(0);
        else if (this.case.id === 'error') { this.emit('error', Error('authored worker failure')); this.exit(1); }
        else if (this.case.id === 'rss') { this.case.rss.active(); this.exit(0); }
        else this.exit(1);
      });
    }
    exit(code) { if (!this.exited) { this.exited = true; this.emit('exit', code); } }
    terminate() {
      this.case.terminations++;
      queueMicrotask(() => {
        if (this.exited) return;
        if (this.case.id === 'timeout') this.emit('message', message);
        this.exit(1);
      });
      return Promise.resolve(1);
    }
  }
  const context = vm.createContext({ process, Buffer, performance, setTimeout, clearTimeout,
    setInterval, clearInterval, queueMicrotask, console });
  const module = new vm.SourceTextModule(fs.readFileSync(SCRIPT, 'utf8'), {
    context, identifier: parentURL.href, initializeImportMeta(meta) { meta.url = parentURL.href; }
  });
  const allowed = new Set(['node:crypto', 'node:fs', 'node:path', 'node:vm', 'node:perf_hooks', 'node:url', 'node:worker_threads']);
  await module.link(async spec => {
    assert.ok(spec === './map_constructor_worker.mjs' || allowed.has(spec));
    const ns = await import(spec === './map_constructor_worker.mjs' ? workerURL.href : spec);
    return new vm.SyntheticModule(Object.keys(ns), function () {
      for (const k of Object.keys(ns)) this.setExport(k, spec === 'node:worker_threads' && k === 'Worker' ? FakeWorker : ns[k]);
    }, { context, identifier: spec });
  });
  await module.evaluate({ timeout: 1000 });
  for (const [id, expected] of [['timeout', 'timeout'], ['overdue-message', 'timeout'], ['error', 'worker_error'], ['rss', 'resource_refusal'], ['exit', 'worker_error']]) {
    current = { id, terminations: 0, rss: { active: null, sample() {} } };
    const job = { id, kind: 'gat', complete_sha256: '0'.repeat(64), input_bytes: 2, header_version_bytes: [0, 1] };
    const row = await module.namespace.runWorkerJob(job, Buffer.from([0, 1]), {
      policy: { ...profile.policy, job_timeout_ms: ['timeout', 'overdue-message'].includes(id) ? 2 : 1000 },
      sources: {}, summaryText: 'not executed', runDeadline: Date.now() + 5000, rss: current.rss
    });
    assert.equal(row.outcome, expected, id); assert.equal(row._summary_json, null, id);
    assert.equal(row.cleanup.exit_observed, true, 'mock exit observed');
    assert.equal(current.rss.active, null);
    assert.equal(row.constructor_returned, ['timeout', 'overdue-message'].includes(id) ? null : true);
  }
});

for (const filename of ['jobs.jsonl', 'report.json']) {
  test(`main completes a positive short ${filename} write without corrupting output`, async () => {
    const output = freshOut(), target = path.join(output, filename);
    const realOpen = fs.openSync, realClose = fs.closeSync, realWrite = fs.writeSync;
    let owned = null, injection = 0, code;
    fs.openSync = function (p, ...args) {
      const fd = realOpen(p, ...args);
      if (typeof p === 'string' && path.resolve(p) === target) owned = fd;
      return fd;
    };
    fs.closeSync = function (fd) { const r = realClose(fd); if (fd === owned) owned = null; return r; };
    fs.writeSync = function (fd, buffer, offset, length, position) {
      if (fd === owned && !injection) {
        injection++;
        return realWrite(fd, buffer, offset, Math.max(1, Math.floor(length / 2)), position);
      }
      return realWrite(fd, buffer, offset, length, position);
    };
    try {
      code = await main(['--input-root', INPUT_ROOT, '--client-source', CLIENT, '--profile', PROFILE,
        '--fixtures', FIXTURES, '--output', output], { stdout: { write() {} } });
      assert.equal(owned, null, 'candidate closed target before harness cleanup');
    } finally {
      fs.openSync = realOpen; fs.closeSync = realClose; fs.writeSync = realWrite;
      if (owned !== null) realClose(owned);
    }
    assert.equal(injection, 1); assert.equal(code, 0);
    const got = rows(output), rep = report(output), bytes = fs.readFileSync(path.join(output, 'jobs.jsonl'));
    assert.equal(got.length, 26); assert.equal(rep.authored_comparison.matched, 26);
    assert.equal(rep.jobs_file.bytes, bytes.length);
    assert.equal(rep.jobs_file.sha256, crypto.createHash('sha256').update(bytes).digest('hex'));
  });
}

test('persistent zero-progress jobs writes fail promptly and release owned resources', async () => {
  const output = freshOut(), target = path.join(output, 'jobs.jsonl');
  const real = { open: fs.openSync, close: fs.closeSync, write: fs.writeSync,
    interval: globalThis.setInterval, clear: globalThis.clearInterval };
  let owned = null, calls = 0, error, observed;
  const timers = new Set();
  fs.openSync = function (p, ...args) {
    const fd = real.open(p, ...args);
    if (typeof p === 'string' && path.resolve(p) === target) owned = fd;
    return fd;
  };
  fs.closeSync = function (fd) { const r = real.close(fd); if (fd === owned) owned = null; return r; };
  fs.writeSync = function (fd, ...args) {
    if (fd !== owned) return real.write(fd, ...args);
    if (++calls > 3) throw Error('authored safety guard: write loop did not stop');
    return 0;
  };
  globalThis.setInterval = function (fn, ms, ...args) { const h = real.interval(fn, ms, ...args); timers.add(h); return h; };
  globalThis.clearInterval = function (h) { timers.delete(h); return real.clear(h); };
  try {
    await main(['--input-root', INPUT_ROOT, '--client-source', CLIENT, '--profile', PROFILE,
      '--fixtures', FIXTURES, '--output', output, '--max-jobs', '0'], { stdout: { write() {} } });
  } catch (e) { error = e; }
  finally {
    observed = { fd: owned, timers: timers.size };
    fs.openSync = real.open; fs.closeSync = real.close; fs.writeSync = real.write;
    globalThis.setInterval = real.interval; globalThis.clearInterval = real.clear;
    for (const h of timers) real.clear(h);
    if (owned !== null) real.close(owned);
  }
  assert.equal(error?.reason, 'output_io_error'); assert.equal(calls, 2);
  assert.deepEqual(observed, { fd: null, timers: 0 });
  assert.equal(fs.existsSync(path.join(output, 'report.json')), false);
});

test('whole-run deadline remains enforced after final report publication', async () => {
  // Actual authored workers; only the final parent clock observation is advanced.
  // This is a policy-order control, separate from the real 1ms timeout tests.
  const output = freshOut(), target = path.join(output, 'report.json');
  const realOpen = fs.openSync, realClose = fs.closeSync, realWrite = fs.writeSync, realNow = Date.now;
  let owned = null, injected = 0, stdout = '', code;
  fs.openSync = function (p, ...args) {
    const fd = realOpen(p, ...args);
    if (typeof p === 'string' && path.resolve(p) === target) owned = fd;
    return fd;
  };
  fs.closeSync = function (fd) { const r = realClose(fd); if (fd === owned) owned = null; return r; };
  fs.writeSync = function (fd, ...args) {
    const n = realWrite(fd, ...args);
    if (fd === owned && !injected) { injected++; Date.now = () => realNow() + profile.policy.run_timeout_ms + 100; }
    return n;
  };
  try {
    code = await main(['--input-root', INPUT_ROOT, '--client-source', CLIENT, '--profile', PROFILE,
      '--fixtures', FIXTURES, '--output', output], { stdout: { write: s => { stdout += s; } } });
    assert.equal(owned, null);
  } finally {
    fs.openSync = realOpen; fs.closeSync = realClose; fs.writeSync = realWrite; Date.now = realNow;
    if (owned !== null) realClose(owned);
  }
  assert.equal(injected, 1); assert.equal(code, 1);
  const summary = JSON.parse(stdout.trim());
  assert.equal(summary.status, 'incomplete'); assert.equal(summary.halted, 'run_deadline_after_publication');
  assert.equal(report(output).authored_comparison.matched, 26);
  assert.equal(report(output).task, 'T06.003.003.003');
});

const fileSha = (p) => crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');

test('T07.007.004 profile allowlist admits only its exact pair', () => {
  assert.equal(PROFILE_ALLOWLIST.length, 2);
  assert.equal(PROFILE_ALLOWLIST[0].task, 'T06.003.003.003');
  assert.equal(PROFILE_ALLOWLIST[0].worker, null);
  assert.equal(PROFILE_ALLOWLIST[1].task, 'T07.007.004');
  assert.equal(fileSha(PROFILE), PROFILE_ALLOWLIST[0].sha256);
  assert.equal(fs.statSync(PROFILE).size, PROFILE_ALLOWLIST[0].bytes);
  assert.equal(fileSha(NEW_PROFILE), PROFILE_ALLOWLIST[1].sha256);
  assert.equal(fs.statSync(NEW_PROFILE).size, PROFILE_ALLOWLIST[1].bytes);
  assert.equal(profileEntryFor(PROFILE_ALLOWLIST[1].sha256).manifest.sha256, newProfile.manifest.sha256);
  assert.equal(profileEntryFor('ab'.repeat(32)), null);
  assert.deepEqual(newProfile.counts, { roots: 4, observed: 4, unavailable_roots: 0, jobs: 12, edge_references: 12 });
  assert.equal(Object.keys(newProfile.sources).length, 9);
  validateProfile(profile, PROFILE_ALLOWLIST[0]);
  validateProfile(newProfile, PROFILE_ALLOWLIST[1]);
  assert.throws(() => validateProfile(newProfile, PROFILE_ALLOWLIST[0]), Refusal);
  assert.throws(() => validateProfile(profile, PROFILE_ALLOWLIST[1]), Refusal);
  const swapped = structuredClone(newProfile); swapped.task = 'T06.003.003.003';
  assert.throws(() => validateProfile(swapped), Refusal);
  const unknown = structuredClone(newProfile); unknown.task = 'T07.007.005';
  assert.throws(() => validateProfile(unknown), Refusal);
  const badWorker = structuredClone(newProfile); badWorker.worker = { ...badWorker.worker, sha256: '0'.repeat(64) };
  assert.throws(() => validateProfile(badWorker), (e) => e instanceof Refusal && e.reason === 'profile_invalid');
  const badCount = structuredClone(newProfile); badCount.counts = { ...badCount.counts, jobs: 11 };
  assert.throws(() => validateProfile(badCount), Refusal);
  const badManifest = structuredClone(newProfile); badManifest.manifest = { ...badManifest.manifest, bytes: 1 };
  assert.throws(() => validateProfile(badManifest), Refusal);
  const changed = path.join(TMP, 'new-profile-changed.json');
  fs.writeFileSync(changed, fs.readFileSync(NEW_PROFILE)); fs.appendFileSync(changed, '\n');
  const r = cli([], { profile: changed });
  assert.equal(r.code, 2); assert.equal(r.summary.reason, 'pin_mismatch'); assert.ok(!fs.existsSync(r.output));
});

test('T07.007.004 manifest task, counts, ids, kinds, roots and synthetic body refusal', () => {
  const manifest = JSON.parse(fs.readFileSync(NEW_MANIFEST, 'utf8'));
  const jobs = manifestJobs(manifest, newProfile);
  assert.equal(jobs.length, 12);
  assert.deepEqual(jobs.map((j) => [j.id, j.kind]), [
    ['target-000:gat', 'gat'], ['target-001:gnd', 'gnd'], ['target-002:rsw', 'rsw'],
    ['target-003:gat', 'gat'], ['target-004:gnd', 'gnd'], ['target-005:rsw', 'rsw'],
    ['target-006:gat', 'gat'], ['target-007:gnd', 'gnd'], ['target-008:rsw', 'rsw'],
    ['target-009:gat', 'gat'], ['target-010:gnd', 'gnd'], ['target-011:rsw', 'rsw']
  ]);
  assert.deepEqual(manifest.roots.map((r) => [r.ordinal, r.name, r.original_gap_root_ordinal]), [
    [0, 'mu_fild01', null], [1, 'ygg_edge', null], [2, 'ygg_fruit', null], [3, 'ygg_roots', null]
  ]);
  const wrongTask = structuredClone(manifest); wrongTask.task = 'T06.003.003.003';
  assert.throws(() => manifestJobs(wrongTask, newProfile), Refusal);
  const inferred = structuredClone(manifest); inferred.roots[3].original_gap_root_ordinal = 81;
  assert.throws(() => manifestJobs(inferred, newProfile), Refusal);
  const relinked = structuredClone(manifest); relinked.roots[1].edges.gat.job_id = 'target-000:gat';
  assert.throws(() => manifestJobs(relinked, newProfile), Refusal);
  const renamed = structuredClone(manifest); renamed.roots[0].name = 'prt_fild08';
  assert.throws(() => manifestJobs(renamed, newProfile), Refusal);
  const rekind = structuredClone(manifest); rekind.jobs[2].kind = 'gat';
  assert.throws(() => manifestJobs(rekind, newProfile), Refusal);
  const root = path.join(TMP, 't07-synthetic'); fs.mkdirSync(path.join(root, 'b'), { recursive: true });
  const body = Buffer.from('GRAT synthetic');
  fs.writeFileSync(path.join(root, 'b', 'ok.bin'), body);
  fs.symlinkSync(path.join(root, 'b', 'ok.bin'), path.join(root, 'b', 'link.bin'));
  const sha = fileSha(path.join(root, 'b', 'ok.bin'));
  const pol = newProfile.policy;
  const job = (p, extra = {}) => ({ body_path: p, input_bytes: body.length, complete_sha256: sha, ...extra });
  assert.equal(readJobBody(root, job('b/ok.bin'), pol).sha256, sha);
  const reason = (j) => { try { readJobBody(root, j, pol); return 'accepted'; } catch (e) { return e.reason; } };
  assert.equal(reason(job('../escape.bin')), 'path_refused');
  assert.equal(reason(job('b/./ok.bin')), 'path_refused');
  assert.equal(reason(job('b/link.bin')), 'symlink_refused');
  assert.equal(reason(job('b/ok.bin', { input_bytes: body.length + 1 })), 'pin_mismatch');
  assert.equal(reason(job('b/ok.bin', { complete_sha256: '0'.repeat(64) })), 'pin_mismatch');
  assert.equal(reason(job('b/missing.bin', { input_bytes: pol.max_body_bytes + 1 })), 'size_limit');
});

test('old and new profiles refuse each other\'s manifest and do not open it', async () => {
  const oldManifest = path.join(INPUT_ROOT, profile.manifest.path);
  const realOpen = fs.openSync;
  const opened = [];
  fs.openSync = function (p, ...args) {
    if (typeof p === 'string') opened.push(path.resolve(p));
    return realOpen(p, ...args);
  };
  const runOnce = async (argv) => {
    opened.length = 0;
    let stdout = '';
    const code = await main(argv, { stdout: { write: (s) => { stdout += s; } } });
    return { code, summary: JSON.parse(stdout.trim()), opened: [...opened] };
  };
  try {
    const outputA = freshOut();
    const swappedNew = await runOnce(['--input-root', INPUT_ROOT, '--client-source', CLIENT, '--profile', PROFILE,
      '--manifest', NEW_MANIFEST, '--output', outputA]);
    assert.equal(swappedNew.code, 2);
    assert.equal(swappedNew.summary.reason, 'path_refused');
    assert.equal(swappedNew.summary.output_created, false);
    assert.ok(!fs.existsSync(outputA));
    assert.ok(!swappedNew.opened.includes(path.resolve(NEW_MANIFEST)));
    assert.ok(!swappedNew.opened.some((p) => p.includes(`${path.sep}t07-007-003-root-actual-reference-1${path.sep}`)));
    const outputB = freshOut();
    const swappedOld = await runOnce(['--input-root', INPUT_ROOT, '--client-source', CLIENT, '--profile', NEW_PROFILE,
      '--manifest', oldManifest, '--output', outputB]);
    assert.equal(swappedOld.code, 2);
    assert.equal(swappedOld.summary.reason, 'path_refused');
    assert.equal(swappedOld.summary.output_created, false);
    assert.ok(!fs.existsSync(outputB));
    assert.ok(!swappedOld.opened.includes(path.resolve(oldManifest)));
    assert.ok(swappedOld.opened.some((p) => p.endsWith(`${path.sep}map_constructor_worker.mjs`)));
    assert.ok(!swappedOld.opened.some((p) => p.endsWith('.body')));
  } finally { fs.openSync = realOpen; }
});

test('T07.007.004 --max-jobs 0 accounts for 12 unattempted rows and opens no body', async () => {
  const output = freshOut();
  const bodyDir = `${path.sep}t07-007-003-root-actual-reference-1${path.sep}`;
  const realOpen = fs.openSync;
  const opened = [];
  fs.openSync = function (p, ...args) {
    if (typeof p === 'string') opened.push(path.resolve(p));
    return realOpen(p, ...args);
  };
  let code, stdout = '';
  try {
    code = await main(['--input-root', INPUT_ROOT, '--client-source', CLIENT, '--profile', NEW_PROFILE,
      '--manifest', NEW_MANIFEST, '--output', output, '--max-jobs', '0'],
    { stdout: { write: (s) => { stdout += s; } } });
  } finally { fs.openSync = realOpen; }
  assert.equal(opened.filter((p) => p.includes(bodyDir)).length, 0);
  assert.ok(opened.some((p) => p === path.resolve(NEW_MANIFEST)));
  assert.equal(code, 1);
  const summary = JSON.parse(stdout.trim());
  assert.equal(summary.status, 'incomplete');
  assert.equal(summary.expected_jobs, 12);
  assert.equal(summary.job_outcomes.unattempted, 12);
  const got = rows(output);
  assert.equal(got.length, 12);
  assert.deepEqual(got.map((x) => x.id), [
    'target-000:gat', 'target-001:gnd', 'target-002:rsw', 'target-003:gat', 'target-004:gnd', 'target-005:rsw',
    'target-006:gat', 'target-007:gnd', 'target-008:rsw', 'target-009:gat', 'target-010:gnd', 'target-011:rsw'
  ]);
  for (const x of got) {
    assert.equal(x.outcome, 'unattempted'); assert.equal(x.reason, 'max_jobs');
    assert.equal(x.worker_started, false); assert.equal(x.constructor_returned, null);
    assert.equal(x.cleanup.exit_observed, null);
  }
  const rep = report(output);
  assert.equal(rep.schema, 'T06-map-constructor-report-1');
  assert.equal(rep.task, 'T07.007.004');
  assert.equal(rep.mode, 'corpus');
  assert.equal(rep.profile_sha256, PROFILE_ALLOWLIST[1].sha256);
  assert.equal(rep.summary_sha256, newProfile.summary.sha256);
  assert.equal(rep.worker.path, 'tools/renewal/map_constructor_worker.mjs');
  assert.equal(rep.worker.bytes, 9132);
  assert.equal(rep.worker.sha256, PROFILE_ALLOWLIST[1].worker.sha256);
  assert.equal(rep.worker.verified, true);
  assert.equal(rep.client_source.sources.length, 9);
  assert.ok(rep.client_source.sources.every((s) => s.verified && !s.path.includes('worker')));
  assert.equal(rep.counts.expected_jobs, 12);
  assert.equal(rep.counts.job_outcomes.unattempted, 12);
  assert.equal(rep.cleanup.workers_started, 0);
  assert.equal(rep.cleanup.verified, true);
  assert.deepEqual(rep.input_manifest.counts, newProfile.counts);
  assert.deepEqual(rep.input_manifest.remaining_gap_root_ordinals, []);
  assert.equal(rep.roots.length, 4);
  assert.deepEqual(rep.roots.map((r) => r.name), ['mu_fild01', 'ygg_edge', 'ygg_fruit', 'ygg_roots']);
  for (const r of rep.roots) {
    assert.equal(r.original_gap_root_ordinal, null);
    assert.equal(r.ordinal_scope, 'four-target-subset-only');
    for (const kind of ['gat', 'gnd', 'rsw']) {
      assert.equal(r.edges[kind].parse_outcome, 'unattempted');
      assert.equal(r.edges[kind].parse_status, 'not_run');
    }
  }
});

test('new profile keeps lower-only bounds, existing output, one authored row and timeout cleanup', () => {
  let r = cli(['--run-timeout-ms', '120001'], { profile: NEW_PROFILE });
  assert.equal(r.code, 2); assert.equal(r.summary.reason, 'policy_increase'); assert.ok(!fs.existsSync(r.output));
  r = cli(['--run-timeout-ms', '900000'], { profile: NEW_PROFILE });
  assert.equal(r.code, 2); assert.equal(r.summary.reason, 'policy_increase');
  assert.throws(() => effectivePolicy(newProfile.policy, { run_timeout_ms: 120001 }, 12), Refusal);
  assert.equal(effectivePolicy(newProfile.policy, { run_timeout_ms: 120000 }, 12).run_timeout_ms, 120000);
  assert.equal(effectivePolicy(profile.policy, { run_timeout_ms: 120001 }, 26).run_timeout_ms, 120001);
  r = cli(['--max-jobs', '13'], { profile: NEW_PROFILE, mode: ['--manifest', NEW_MANIFEST] });
  assert.equal(r.code, 2); assert.equal(r.summary.reason, 'policy_increase'); assert.ok(!fs.existsSync(r.output));
  const out = freshOut();
  fs.mkdirSync(out); fs.writeFileSync(path.join(out, 'keep'), 'sentinel');
  r = cli([], { profile: NEW_PROFILE, output: out });
  assert.equal(r.code, 2); assert.equal(r.summary.reason, 'output_exists');
  assert.equal(fs.readFileSync(path.join(out, 'keep'), 'utf8'), 'sentinel');
  r = cli(['--max-jobs', '1'], { profile: NEW_PROFILE });
  assert.equal(r.code, 1);
  const got = rows(r.output);
  assert.equal(got.length, 26);
  const c = authored.cases[0];
  assert.equal(got[0].id, c.id);
  assert.equal(got[0].outcome, c.expected.outcome);
  assert.equal(got[0].worker_started, true);
  assert.equal(got[0].cleanup.exit_observed, true);
  if (c.expected.outcome === 'returned') assert.deepStrictEqual(got[0].summary, c.expected.summary);
  else assert.equal(got[0].exception.name, c.expected.exception_name);
  assert.ok(got.slice(1).every((x) => x.outcome === 'unattempted' && x.reason === 'max_jobs' && x.worker_started === false));
  const rep = report(r.output);
  assert.equal(rep.task, 'T07.007.004');
  assert.equal(rep.schema, 'T06-map-constructor-report-1');
  assert.equal(rep.mode, 'fixtures');
  assert.equal(rep.worker.verified, true);
  assert.equal(rep.worker.sha256, newProfile.worker.sha256);
  assert.equal(rep.client_source.sources.length, 9);
  assert.ok(!rep.client_source.sources.some((s) => s.path.includes('map_constructor_worker')));
  assert.equal(rep.authored_comparison.matched, 1);
  r = cli(['--job-timeout-ms', '1', '--max-jobs', '1'], { profile: NEW_PROFILE });
  assert.equal(r.code, 1);
  const timed = rows(r.output)[0];
  assert.equal(timed.outcome, 'timeout');
  assert.equal(timed.reason, 'job_timeout');
  assert.equal(timed.cleanup.terminated_by_parent, true);
  assert.equal(timed.cleanup.exit_observed, true);
  assert.equal(report(r.output).cleanup.verified, true);
  assert.equal(report(r.output).cleanup.workers_started, 1);
  assert.equal(report(r.output).task, 'T07.007.004');
});

test('worker pin mismatch refuses before Worker construction and halts later jobs', async () => {
  const job = { id: 'pin', kind: 'gat', complete_sha256: '0'.repeat(64), input_bytes: 1, header_version_bytes: [1, 3] };
  const workerAbs = path.join(HERE, 'map_constructor_worker.mjs');
  const row = await runWorkerJob(job, Buffer.from([0]), {
    policy: { ...profile.policy, job_timeout_ms: 200 }, sources: {}, summaryText: 'not executed',
    runDeadline: Date.now() + 1000, rss: { active: null, sample() {} },
    workerPin: { path: workerAbs, identity: { dev: '0', ino: '0', size: '0', mtime_ns: '0', ctime_ns: '0' } }
  });
  assert.equal(row.outcome, 'environment_failure');
  assert.equal(row.reason, 'identity_changed');
  assert.equal(row.worker_started, false);
  assert.equal(row.cleanup.exit_observed, null);
  assert.equal(row.exception.phase, 'worker_pin');
});
