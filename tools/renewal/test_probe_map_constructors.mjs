// Runner controls for T06.003.003.003. Run with:
//   T06_INPUT_ROOT=/canonical/repository node --experimental-vm-modules --test tools/renewal/test_probe_map_constructors.mjs
// Uses only the frozen authored fixtures and synthetic temp files; never opens retained game bodies.
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { corpusRoots, effectivePolicy, manifestJobs, readJobBody, readPinnedFile, Refusal, safeJoin } from './probe_map_constructors.mjs';
import { createRealm, MODULE_KEYS, resolveSpecifier } from './map_constructor_worker.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, '..', '..');
const INPUT_ROOT = process.env.T06_INPUT_ROOT ||
  path.resolve(REPO, '..', 'reverse-the-Ragnarok-Online-to-play-by-myself');
const CLIENT = path.join(INPUT_ROOT, '.tools', 'renewal', 'client-source');
const PROFILE = path.join(REPO, 'docs/project/fixtures/T06.003.003.003-profile.json');
const FIXTURES = path.join(REPO, 'docs/project/fixtures/T06.003.003.003-authored.json');
const SCRIPT = path.join(HERE, 'probe_map_constructors.mjs');
const profile = JSON.parse(fs.readFileSync(PROFILE, 'utf8'));
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
  assert.equal(r.code, 1);
  got = rows(r.output);
  authored.cases.forEach((c, i) => {
    const x = got[i];
    assert.equal(x.outcome, c.expected.outcome === 'returned' ? 'summary_limit' : 'constructor_exception', c.id);
    assert.ok(!('summary' in x));
    if (x.outcome === 'summary_limit') { assert.equal(x.constructor_returned, true); assert.ok(x.summary_json_bytes > 10); }
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
