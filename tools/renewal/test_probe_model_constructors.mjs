// Runner controls for T06.003.003.006. Fixture execution only.
// T07.007.008 supplement-route controls below also read the frozen canonical
// four-root manifest/availability pins and run its 273 pure constructor jobs.
//   T06_INPUT_ROOT=/canonical/repository node --experimental-vm-modules --test tools/renewal/test_probe_model_constructors.mjs
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import crypto from 'node:crypto';
import { EventEmitter } from 'node:events';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { Worker } from 'node:worker_threads';
import { fileURLToPath, pathToFileURL } from 'node:url';
import {
  ARTIFACT_AUDIT_EXPECTED, EXECUTION_BINDING_EXPECTED, PROFILE_SHA256, ROUTES, Refusal, SUPPLEMENT_PROFILE_SHA256, admitModelCorpus,
  assertExactDecimalIdentity, boundedRow, compareAuthored,
  effectivePolicy, expandTargetOutcomes, fixtureJobs, hooks, identityOf, main, parseArgs, readPinnedFile,
  runWorkerJob, safeJoin, selectModelTargets, unattemptedRow, validateExecutionReceipt, validateProfile, writeAll
} from './probe_model_constructors.mjs';
import { ENTRY_SOURCE, MODULE_KEYS, RULE_KEYS, createRealm, outcomeForSummaryThrow, resolveSpecifier } from './model_constructor_worker.mjs';
import { SummaryLimitError, summarizeModel } from './model_constructor_summary.mjs';

process.umask(0o077);
const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, '..', '..');
const INPUT_ROOT = process.env.T06_INPUT_ROOT || path.resolve(REPO, '..', 'reverse-the-Ragnarok-Online-to-play-by-myself');
const CLIENT = path.join(INPUT_ROOT, '.tools', 'renewal', 'client-source');
const PROFILE = path.join(REPO, 'docs/project/fixtures/T06.003.003.006-profile.json');
const FIXTURES = path.join(REPO, 'docs/project/fixtures/T06.003.003.006-authored.json');
const SCRIPT = path.join(HERE, 'probe_model_constructors.mjs');
const profile = JSON.parse(fs.readFileSync(PROFILE, 'utf8'));
const authored = JSON.parse(fs.readFileSync(FIXTURES, 'utf8'));
const PRIVATE = path.join(REPO, '.tools', 'renewal', 't06-model-constructor-candidate-1');
fs.mkdirSync(PRIVATE, { recursive: true, mode: 0o700 });
fs.chmodSync(PRIVATE, 0o700);
const TMP = fs.mkdtempSync(path.join(fs.realpathSync(PRIVATE), 'test-tmp-'));
fs.chmodSync(TMP, 0o700);
test.after(() => fs.rmSync(TMP, { recursive: true, force: true }));
let seq = 0;
let chain = Promise.resolve();
const serial = (name, fn) => test(name, () => {
  const run = chain.then(() => fn());
  chain = run.then(() => {}, () => {});
  return run;
});
// Existing positive stand-ins now model real readable EOF before exit.
// This changes their lifecycle fidelity, not their packet or failure assertions.
const endStandInStreamsOnExit = (worker) => worker.on('exit', () => {
  worker.stdout.emit('end'); worker.stderr.emit('end');
});
const freshOut = () => path.join(TMP, `out-${++seq}`);
const cli = (extra, { prof = PROFILE, client = CLIENT, output = freshOut(), mode = ['--fixtures', FIXTURES] } = {}) => {
  const r = spawnSync(process.execPath, ['--experimental-vm-modules', '--no-warnings', SCRIPT, '--input-root', INPUT_ROOT,
    '--client-source', client, '--profile', prof, ...mode, '--output', output, ...extra], { encoding: 'utf8', timeout: 180000 });
  assert.equal(r.error, undefined, r.error && r.error.message);
  const lines = r.stdout.trim().split('\n').filter(Boolean);
  assert.equal(lines.length, 1, `stdout lines ${lines.length}: ${r.stdout.slice(0, 300)} stderr ${r.stderr.slice(0, 300)}`);
  assert.ok(Buffer.byteLength(r.stdout) <= 4096);
  assert.equal(r.stdout.includes('/Users'), false);
  return { code: r.status, summary: JSON.parse(lines[0]), output, stderr: r.stderr };
};
const rows = (out) => fs.readFileSync(path.join(out, 'jobs.jsonl'), 'utf8').trim().split('\n').map((line) => JSON.parse(line));
const reportOf = (out) => JSON.parse(fs.readFileSync(path.join(out, 'report.json'), 'utf8'));

serial('importing the parent does not run the CLI or start a worker', () => {
  const href = pathToFileURL(SCRIPT).href;
  const r = spawnSync(process.execPath, ['--experimental-vm-modules', '--input-type=module', '-e', `await import(${JSON.stringify(href)})`], { encoding: 'utf8', timeout: 15000 });
  assert.equal(r.status, 0);
  assert.equal(r.stdout, '');
});

serial('fresh fixture CLI matches all 13 outcomes, summaries and exception names', () => {
  const r = cli([]);
  assert.equal(r.code, 0, JSON.stringify(r.summary));
  assert.equal(r.summary.status, 'complete');
  assert.equal(r.summary.authored_matched, 13);
  const got = rows(r.output);
  assert.equal(got.length, 13);
  let returned = 0;
  let exceptions = 0;
  authored.cases.forEach((entry, index) => {
    const row = got[index];
    assert.equal(row.id, entry.id);
    assert.equal(row.job_id, entry.id);
    assert.equal(row.kind, 'model');
    assert.equal(row.complete_sha256, entry.complete_sha256);
    assert.equal(row.input_bytes, entry.input_bytes);
    assert.equal(row.header_version_bytes, entry.header_version_bytes);
    assert.equal(row.outcome, entry.expected_outcome, entry.id);
    assert.equal(row.worker_started, true);
    assert.equal(row.cleanup.exit_observed, true);
    assert.equal(row.cleanup.exit_code, 0);
    assert.equal(row.cleanup.terminated_by_parent, false);
    assert.deepEqual(row.seek_globals, [1, 2, 3]);
    assert.equal(row.loaded_module_keys.length, 7);
    assert.deepEqual(row.dynamic_import_refusals, []);
    if (entry.expected_outcome === 'returned') {
      returned++;
      assert.equal(row.constructor_returned, true);
      assert.deepStrictEqual(row.summary, entry.expected_summary, entry.id);
    } else {
      exceptions++;
      assert.equal(row.constructor_returned, false);
      assert.equal(row.exception.phase, 'constructor');
      assert.equal(row.exception.name, entry.expected_exception_name, entry.id);
      assert.equal('summary' in row, false);
    }
  });
  assert.deepEqual([returned, exceptions], [9, 4]);
  const rep = reportOf(r.output);
  assert.equal(rep.schema, 'T06-model-constructor-report-1');
  assert.equal(rep.qualified, true);
  assert.equal(rep.mode, 'fixtures');
  assert.deepEqual(rep.roots, []);
  assert.deepEqual(rep.targets, []);
  assert.deepEqual(rep.remaining_gap_root_ordinals, []);
  assert.deepEqual(rep.prior_first_level_gaps, []);
  assert.equal(rep.profile_sha256, PROFILE_SHA256);
  assert.equal(rep.summary_sha256, profile.summary.sha256);
  assert.equal(rep.preserved_counts.model_targets, 8194);
  assert.equal(rep.preserved_counts.constructor_jobs, 8166);
  assert.equal(rep.preserved_counts.model_referrers, 48980);
  assert.equal(rep.preserved_counts.roots, 1296);
  assert.equal(rep.preserved_counts.remaining_core_gap_roots, 82);
  assert.equal(rep.preserved_counts.all_catalog_referrers, 63557);
  assert.equal(rep.header_prefix_counts_are_observations, true);
  assert.equal(rep.client_source.sources.length, 7);
  assert.equal(rep.client_source.rule_sources.length, 3);
  assert.equal(rep.own_sources.length, 2);
  assert.equal(rep.authored_comparison.matched, 13);
  assert.equal(rep.cleanup.verified, true);
  assert.equal(rep.counts.job_outcomes.returned, 9);
  assert.equal(rep.counts.job_outcomes.constructor_exception, 4);
  assert.equal(rep.counts.expected_targets, 0);
  const jobsBuf = fs.readFileSync(path.join(r.output, 'jobs.jsonl'));
  assert.equal(rep.jobs_file.bytes, jobsBuf.length);
  assert.equal(rep.jobs_file.sha256, crypto.createHash('sha256').update(jobsBuf).digest('hex'));
  assert.equal(rep.jobs_file.records, 13);
  assert.equal(fs.statSync(r.output).mode & 0o777, 0o700);
  assert.deepEqual(fs.readdirSync(r.output).sort(), ['jobs.jsonl', 'report.json']);
  for (const name of fs.readdirSync(r.output)) assert.equal(fs.statSync(path.join(r.output, name)).mode & 0o777, 0o600, name);
  assert.ok(rep.rss_sampling.samples >= 1 && rep.rss_sampling.peak_rss_bytes > 0);
  for (const forbidden of ['playable', 'format_valid', 'rendered']) assert.equal(forbidden in rep, false);
});

serial('existing output, profile pin, symlink and special file refuse before output', () => {
  const out = freshOut();
  fs.mkdirSync(out, { mode: 0o700 });
  fs.writeFileSync(path.join(out, 'keep'), 'sentinel', { mode: 0o600 });
  let r = cli([], { output: out });
  assert.equal(r.code, 2);
  assert.equal(r.summary.reason, 'output_exists');
  assert.equal(fs.readFileSync(path.join(out, 'keep'), 'utf8'), 'sentinel');
  const changed = path.join(TMP, 'profile-changed.json');
  fs.writeFileSync(changed, `${fs.readFileSync(PROFILE, 'utf8')} `, { mode: 0o600 });
  r = cli([], { prof: changed });
  assert.equal(r.code, 2);
  assert.equal(r.summary.reason, 'pin_mismatch');
  assert.equal(fs.existsSync(r.output), false);
  const link = path.join(TMP, 'profile-link.json');
  fs.symlinkSync(PROFILE, link);
  r = cli([], { prof: link });
  assert.equal(r.code, 2);
  assert.equal(r.summary.reason, 'symlink_refused');
  const fifo = path.join(TMP, 'profile.fifo');
  spawnSync('mkfifo', [fifo]);
  r = cli([], { prof: fifo });
  assert.equal(r.code, 2);
  assert.equal(r.summary.reason, 'special_file_refused');
  assert.equal(r.summary.output_created, false);
});

serial('symlinked client module and output ancestor are refused', () => {
  const fake = path.join(TMP, 'client-links');
  for (const key of [...MODULE_KEYS, ...RULE_KEYS]) {
    fs.mkdirSync(path.dirname(path.join(fake, key)), { recursive: true });
    fs.symlinkSync(path.join(CLIENT, key), path.join(fake, key));
  }
  let r = cli([], { client: fake });
  assert.equal(r.code, 2);
  assert.equal(r.summary.reason, 'symlink_refused');
  assert.equal(fs.existsSync(r.output), false);
  const realDir = path.join(TMP, 'ancestor-real');
  const alias = path.join(TMP, 'ancestor-alias');
  fs.mkdirSync(realDir, { mode: 0o700 });
  fs.writeFileSync(path.join(realDir, 'sentinel'), 'preserve', { mode: 0o600 });
  fs.symlinkSync(realDir, alias);
  r = cli(['--max-jobs', '0'], { output: path.join(alias, 'new', 'output') });
  assert.equal(r.code, 2);
  assert.equal(r.summary.output_created, false);
  assert.equal(fs.readFileSync(path.join(realDir, 'sentinel'), 'utf8'), 'preserve');
});

serial('mode, duplicate flags and lower-only caps refuse increases', () => {
  let r = cli(['--job-timeout-ms', String(profile.policy.job_timeout_ms + 1)]);
  assert.equal(r.code, 2);
  assert.equal(r.summary.reason, 'policy_increase');
  r = cli(['--max-jobs', '14']);
  assert.equal(r.code, 2);
  assert.equal(r.summary.reason, 'policy_increase');
  r = cli(['--rss-limit-bytes', '0']);
  assert.equal(r.code, 2);
  assert.equal(r.summary.reason, 'policy_invalid');
  r = cli(['--fixtures', FIXTURES], { mode: ['--manifest', FIXTURES] });
  assert.equal(r.code, 2);
  assert.equal(r.summary.reason, 'usage');
  r = cli([], { mode: [] });
  assert.equal(r.code, 2);
  assert.equal(r.summary.reason, 'usage');
  r = cli(['--nope', '1']);
  assert.equal(r.code, 2);
  assert.equal(r.summary.reason, 'usage');
  r = cli([], { mode: ['--manifest', path.join(TMP, 'not-the-manifest.json')] });
  assert.equal(r.code, 2);
  assert.equal(r.summary.reason, 'path_refused');
  assert.equal(fs.existsSync(r.output), false);
  assert.throws(() => parseArgs(['--profile', 'a', '--profile', 'b']), Refusal);
  assert.equal(effectivePolicy(profile.policy, { job_timeout_ms: 5 }, 13).job_timeout_ms, 5);
  assert.equal(effectivePolicy(profile.policy, { max_jobs: 0 }, 13).max_jobs, 0);
  assert.equal(profile.policy.result_exit_grace_ms, 2000);
  assert.equal(profile.policy.cleanup_wait_ms, 10000);
  assert.equal(profile.policy.max_active_workers, 1);
});

serial('fixture mode does not open retained bodies, the manifest, or the catalog', async () => {
  const output = freshOut();
  const opened = [];
  const real = fs.openSync;
  fs.openSync = (target, ...args) => {
    if (typeof target === 'string') opened.push(target);
    return real(target, ...args);
  };
  try {
    const code = await main(['--input-root', INPUT_ROOT, '--client-source', CLIENT, '--profile', PROFILE,
      '--fixtures', FIXTURES, '--output', output, '--max-jobs', '0'], { stdout: { write() {} } });
    assert.equal(code, 1);
  } finally { fs.openSync = real; }
  const joined = opened.join('\n');
  for (const forbidden of ['root-model006-input-preparation-1', 'catalog-input.json', 't06-map-dependencies-actual-1/report.json', '/000001']) {
    assert.equal(joined.includes(forbidden), false, forbidden);
  }
  const got = rows(output);
  assert.equal(got.length, 13);
  assert.ok(got.every((row) => row.outcome === 'unattempted' && row.reason === 'max_jobs' && row.worker_started === false && row.cleanup.exit_observed === null && row.constructor_returned === null));
  assert.deepEqual(got.map((row) => row.id), authored.cases.map((entry) => entry.id));
});

serial('--max-jobs keeps the unattempted suffix and a real timeout observes exit', () => {
  let r = cli(['--max-jobs', '2']);
  assert.equal(r.code, 1);
  let got = rows(r.output);
  assert.equal(got.length, 13);
  assert.ok(got.slice(0, 2).every((row) => row.worker_started && row.cleanup.exit_observed === true && row.cleanup.exit_code === 0));
  for (const row of got.slice(2)) {
    assert.equal(row.outcome, 'unattempted');
    assert.equal(row.reason, 'max_jobs');
    assert.equal(row.worker_started, false);
    assert.equal(row.cleanup.exit_observed, null);
  }
  r = cli(['--job-timeout-ms', '1', '--max-jobs', '1']);
  assert.equal(r.code, 1);
  got = rows(r.output);
  assert.equal(got[0].outcome, 'timeout');
  assert.equal(got[0].cleanup.terminated_by_parent, true);
  assert.equal(got[0].cleanup.exit_observed, true);
  assert.equal('summary' in got[0], false);
  assert.equal(got[0].constructor_returned, null);
  assert.ok(got.slice(1).every((row) => row.outcome === 'unattempted'));
  assert.equal(reportOf(r.output).cleanup.verified, true);
});

serial('run deadline and RSS refusal keep explicit suffixes', () => {
  let r = cli(['--run-timeout-ms', '1']);
  assert.equal(r.code, 1);
  let got = rows(r.output);
  assert.equal(got.length, 13);
  assert.ok(got.every((row) => row.outcome === 'timeout' || row.outcome === 'unattempted'));
  const rest = got[0].outcome === 'unattempted' ? got : got.slice(1);
  assert.ok(rest.every((row) => row.outcome === 'unattempted' && row.reason === 'run_deadline'));
  r = cli(['--rss-limit-bytes', '1', '--max-jobs', '1']);
  assert.equal(r.code, 1);
  got = rows(r.output);
  assert.equal(got[0].outcome, 'resource_refusal');
  assert.equal(got[0].reason, 'rss_limit');
  assert.equal(got[0].cleanup.exit_observed, true);
  assert.ok(got.slice(1).every((row) => row.outcome === 'unattempted' && row.reason === 'rss_limit'));
});

serial('job JSON caps refuse an impossible budget and suppress complete summaries', () => {
  let r = cli(['--max-job-json-bytes', '32']);
  assert.equal(r.code, 2);
  assert.equal(r.summary.reason, 'output_budget');
  assert.equal(fs.existsSync(r.output), false);
  r = cli(['--max-job-json-bytes', '2500']);
  assert.equal(r.code, 1);
  const got = rows(r.output);
  const lines = fs.readFileSync(path.join(r.output, 'jobs.jsonl'), 'utf8').trim().split('\n');
  assert.equal(lines.length, 13);
  assert.ok(lines.every((line) => Buffer.byteLength(line) <= 2500));
  assert.ok(got.some((row) => row.outcome === 'summary_limit'));
  for (const row of got) assert.equal('summary' in row, false);
  authored.cases.forEach((entry, index) => {
    const row = got[index];
    assert.equal(row.id, entry.id);
    if (entry.expected_outcome === 'constructor_exception') assert.equal(row.exception.name, entry.expected_exception_name);
  });
});

serial('source drift after a clean observation is not qualified', async () => {
  const output = freshOut();
  const worker = path.join(HERE, 'model_constructor_worker.mjs');
  const before = fs.readFileSync(worker);
  hooks.beforeIdentityRecheck = () => fs.writeFileSync(worker, before);
  try {
    const code = await main(['--input-root', INPUT_ROOT, '--client-source', CLIENT, '--profile', PROFILE,
      '--fixtures', FIXTURES, '--output', output, '--max-jobs', '1'], { stdout: { write() {} } });
    assert.equal(code, 1);
    assert.equal(reportOf(output).pinned_inputs_identity_unchanged_after_run, false);
    assert.equal(reportOf(output).qualified, false);
    assert.equal(rows(output)[0].cleanup.exit_observed, true);
  } finally {
    hooks.beforeIdentityRecheck = null;
    fs.writeFileSync(worker, before);
  }
});

serial('same-realm copy matches; cross-realm and offset-view are adapter hazards', async () => {
  const sources = {};
  for (const key of MODULE_KEYS) {
    const pin = profile.sources[key];
    sources[key] = readPinnedFile(path.join(CLIENT, key), { label: key, maxBytes: pin.bytes, expectBytes: pin.bytes, expectSha: pin.sha256 }).buffer.toString('utf8');
  }
  const realm = await createRealm(sources);
  assert.equal(realm.loaded.length, 7);
  assert.deepEqual([...realm.seekGlobals], [1, 2, 3]);
  const machine = await import('node:vm');
  assert.equal(machine.runInContext('typeof process + typeof require + typeof Buffer + typeof fetch + typeof document', realm.context),
    'undefinedundefinedundefinedundefinedundefined');
  const entry = authored.cases[0];
  const bytes = Buffer.from(entry.body_hex, 'hex');
  assert.throws(() => realm.construct(new Uint8Array(bytes).buffer, 2000), (error) => /Undefined buffer type/.test(error.message) && error.name === 'Error');
  const view = realm.offsetView(bytes, 7, 0x41);
  assert.throws(() => realm.construct(view, 2000), (error) => error.name === 'Error' && /header/.test(error.message));
  const value = realm.construct(realm.exactBuffer(bytes), 2000);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(summarizeModel(value))), entry.expected_summary);
  assert.throws(() => summarizeModel({ nodes: new Array(65537), textures: [] }), SummaryLimitError);
  assert.equal(outcomeForSummaryThrow(new SummaryLimitError()), 'summary_limit');
  assert.equal(outcomeForSummaryThrow(new TypeError('model array expected')), 'summary_error');
});

serial('closed linker accepts only the seven-module Model entry', () => {
  assert.equal(ENTRY_SOURCE.includes('Model'), true);
  assert.equal(ENTRY_SOURCE.includes('World'), false);
  assert.equal(resolveSpecifier('Loaders/Model.js', ENTRY_SOURCE), 'src/Loaders/Model.js');
  assert.equal(resolveSpecifier('Utils/BinaryReader.js', 'src/Loaders/Model.js'), 'src/Utils/BinaryReader.js');
  assert.equal(resolveSpecifier('./Struct.js', 'src/Utils/BinaryReader.js'), 'src/Utils/Struct.js');
  for (const bad of ['Loaders/World.js', 'node:fs', 'fs', '../../etc/passwd', 'Utils/../../x.js', 'https://x/y.js']) {
    assert.throws(() => resolveSpecifier(bad, 'src/Loaders/Model.js'), bad);
  }
  assert.deepEqual(RULE_KEYS, ['src/Loaders/MapLoader.js', 'src/Core/FileManager.js', 'src/Renderer/Map/AnimatedModels.js']);
});

serial('identity strings keep nanoseconds and corpus admission is exact', () => {
  assert.equal(identityOf({ dev: 1n, ino: 2n, size: 3n, mtimeNs: 9007199254740993n, ctimeNs: 9007199254740993n }).mtime_ns, '9007199254740993');
  const body = Buffer.from('4752534d0104aa', 'hex');
  const digest = crypto.createHash('sha256').update(body).digest('hex');
  const identity = { dev: '7', ino: '9', size: String(body.length), mtime_ns: '9007199254740993', ctime_ns: '9007199254740993' };
  const referrer = (n) => ({ job_index: n, loader_index: 0, role: 'model' });
  const catalogTarget = (index, http, referrers) => ({ index, http_path: http, referrers });
  const reportTarget = (index, http, file) => ({
    target_index: index, attempted: true, request_index: index + 1, http_status: 200, wire_target: `/${http}`,
    stored: { file, bytes: body.length, complete: true, error: null, sha256: digest },
    signature: { kind: index === 1 ? 'bmp' : 'model', state: 'match', prefix_hex: index === 1 ? '424d' : '4752534d0104' }
  });
  reportTarget(1, 'data/texture/x.bmp', '000002').signature.kind = 'bmp';
  const bmp = reportTarget(1, 'data/texture/x.bmp', '000002');
  bmp.signature = { kind: 'bmp', state: 'match', prefix_hex: '424d' };
  bmp.stored.sha256 = 'b'.repeat(64);
  const report = {
    schema: 'T06-map-dependency-observation-1', task: 'T06.003.003.005', all_targets_attempted: true,
    records_complete: true, acquisition_and_cleanup_valid: true,
    catalog_refs: { targets: 3, gap_root_ordinals: [4] },
    targets: [reportTarget(0, 'data/model/a.rsm', '000001'), bmp, reportTarget(2, 'data/model/b.rsm', '000003')]
  };
  const catalog = {
    schema: 'T06-map-dependency-catalog-1',
    roots: [{ ordinal: 0, name: 'keep', edges: { rsw: { parse_status: 'not_run' } } }],
    remaining_gap_root_ordinals: [4],
    targets: [catalogTarget(0, 'data/model/a.rsm', [referrer(1)]), catalogTarget(1, 'data/texture/x.bmp', [referrer(2)]), catalogTarget(2, 'data/model/b.rsm', [referrer(3)])]
  };
  const audit = {
    schema: 'root005-independent-actual-audit-1', availability_audit_qualified: true, target_records: 3, all_roots: 1,
    referrers: 3, remaining_core_gap_roots: 1, first_level_gaps: [{ target_index: 9, kind: 'bmp' }],
    coverage: { signature: { 'model:match': 2 } }
  };
  const counts = {
    model_targets: 2, constructor_jobs: 1, model_referrers: 2, roots: 1, remaining_core_gap_roots: 1,
    all_catalog_referrers: 3, target_body_bytes: body.length * 2, distinct_job_bytes: body.length
  };
  const synthetic = {
    counts,
    header_prefix_counts: { '4752534d0104': 2 },
    availability: { report: { path: '.tools/renewal/corpus/report.json' } }
  };
  const selected = selectModelTargets(report, catalog, audit, synthetic);
  assert.equal(selected.length, 2);
  assert.equal(selected[0].model_ordinal, 0);
  assert.equal(selected[1].target_index, 2);
  assert.notEqual(selected[1].model_ordinal, selected[1].target_index);
  assert.deepEqual(selected[0].referrers, [referrer(1)]);
  const manifestTarget = (ordinal, index, file) => ({
    model_ordinal: ordinal, target_index: index, request_index: index + 1,
    report_pointer: `/targets/${index}`, catalog_pointer: `/targets/${index}`,
    http_path: selected[ordinal].http_path, referrers: selected[ordinal].referrers,
    body: { path: `.tools/renewal/corpus/${file}`, bytes: body.length, sha256: digest, identity },
    job_id: 'model-000000'
  });
  const manifest = {
    schema: 'T06-model-constructor-input-1', task: 'T06.003.003.006', counts, header_prefix_counts: { '4752534d0104': 2 },
    roots: catalog.roots, remaining_gap_root_ordinals: [4], prior_first_level_gaps: audit.first_level_gaps,
    targets: [manifestTarget(0, 0, '000001'), manifestTarget(1, 2, '000003')],
    jobs: [{
      job_id: 'model-000000', representative_model_ordinal: 0, body_path: '.tools/renewal/corpus/000001',
      input_bytes: body.length, complete_sha256: digest, header_version_bytes: '4752534d0104', target_model_ordinals: [0, 1]
    }]
  };
  let reads = 0;
  const readBody = (target) => {
    reads++;
    assert.equal(reads < 3 || target.body.path.endsWith('000003') || target.body.path.endsWith('000001'), true);
    return { buffer: Buffer.from(body), identity };
  };
  const jobs = admitModelCorpus({ manifest, report, catalog, audit, profile: synthetic, readBody });
  assert.equal(jobs.length, 1);
  assert.deepEqual(jobs[0].target_model_ordinals, [0, 1]);
  assert.ok(reads >= 3);
  const bad = structuredClone(manifest);
  bad.targets[1].body.identity = { ...identity, mtime_ns: '9007199254740992' };
  assert.throws(() => admitModelCorpus({ manifest: bad, report, catalog, audit, profile: synthetic, readBody }), (error) => error.reason === 'admission_discrepancy');
  const dropped = structuredClone(manifest);
  dropped.targets = dropped.targets.slice(0, 1);
  assert.throws(() => admitModelCorpus({ manifest: dropped, report, catalog, audit, profile: synthetic, readBody }), Refusal);
  const expanded = expandTargetOutcomes(manifest.targets, new Map([['model-000000', 'returned']]));
  assert.equal(expanded.counts.returned, 2);
  assert.equal(expanded.targets[0].constructor_outcome, 'returned');
  assert.equal(expanded.targets[0].referrers[0].role, 'model');
  assert.equal(manifest.targets[0].constructor_outcome, undefined);
});

serial('representative drift is input_refused and traversal never opens a body', () => {
  const root = path.join(TMP, 'bodies');
  fs.mkdirSync(root, { mode: 0o700 });
  const body = Buffer.from('4752534d0104zz');
  const file = path.join(root, '000001');
  fs.writeFileSync(file, body, { mode: 0o600 });
  fs.chmodSync(file, 0o600);
  const digest = crypto.createHash('sha256').update(body).digest('hex');
  const st = fs.lstatSync(file, { bigint: true });
  const job = { body_path: '000001', input_bytes: body.length, complete_sha256: digest, body: { path: '000001', bytes: body.length, sha256: digest, identity: identityOf(st) } };
  const read = readPinnedFile(file, { label: 'body', maxBytes: profile.policy.max_body_bytes, expectBytes: body.length, expectSha: digest, expectIdentity: identityOf(st), requireMode: 0o600, requireNlink: 1 });
  assert.equal(read.sha256, digest);
  fs.writeFileSync(file, Buffer.from('drifted-body!!'), { mode: 0o600 });
  assert.throws(() => readPinnedFile(file, { label: 'body', maxBytes: 1000, expectBytes: body.length, expectSha: digest, requireMode: 0o600 }), (error) => error instanceof Refusal);
  assert.throws(() => safeJoin(root, '../x', 'body'), Refusal);
  assert.throws(() => safeJoin(root, 'a/../../etc/passwd', 'body'), Refusal);
  fs.symlinkSync(file, path.join(root, 'link.bin'));
  assert.throws(() => readPinnedFile(path.join(root, 'link.bin'), { label: 'body', maxBytes: 1000 }), (error) => error.reason === 'symlink_refused');
  const wide = path.join(root, 'wide');
  fs.writeFileSync(wide, body, { mode: 0o600 });
  fs.chmodSync(wide, 0o644);
  assert.throws(() => readPinnedFile(wide, { label: 'body', maxBytes: 1000, requireMode: 0o600 }), (error) => error.reason === 'mode_refused');
  void job;
});

serial('worker lifecycle keeps a result from repairing nonzero, missing, or late exits', async () => {
  const message = {
    type: 'result', outcome: 'returned', constructor_returned: true, summary_json: '{"ok":1}', summary_json_bytes: 8,
    log: { text: '', dropped: 0 }, loaded_module_keys: MODULE_KEYS, seek_globals: [1, 2, 3], dynamic_imports: []
  };
  const policy = { ...profile.policy, job_timeout_ms: 1000, result_exit_grace_ms: 30, cleanup_wait_ms: 200 };
  const cases = [
    ['nonzero', 'worker_error'],
    ['never-exit', 'worker_error'],
    ['error', 'worker_error'],
    ['late', 'timeout'],
    ['clean', 'returned']
  ];
  let current = null;
  const rss = { active: null, over: 0, sample() {} };
  hooks.createWorker = () => {
    const worker = new EventEmitter();
    worker.stdout = new EventEmitter();
    worker.stderr = new EventEmitter();
    worker.stdout.resume = () => {};
    worker.stderr.resume = () => {};
    endStandInStreamsOnExit(worker);
    worker.terminate = () => { worker.terminated = true; setImmediate(() => worker.emit('exit', 1)); return Promise.resolve(1); };
    setImmediate(() => {
      worker.emit('message', { type: 'phase', phase: 'constructor' });
      if (current === 'late') return;
      worker.emit('message', message);
      if (current === 'nonzero') worker.emit('exit', 1);
      else if (current === 'error') worker.emit('error', Object.assign(new Error('authored worker failure'), { code: 'ERR_TEST' }));
      else if (current === 'clean') worker.emit('exit', 0);
    });
    return worker;
  };
  try {
    for (const [id, expected] of cases) {
      current = id;
      const job = { id, job_id: id, kind: 'model', complete_sha256: 'a'.repeat(64), input_bytes: 2, header_version_bytes: '00' };
      const row = await runWorkerJob(job, Buffer.from([0, 1]), {
        policy: { ...policy, job_timeout_ms: id === 'late' ? 20 : 1000 },
        sources: {}, summaryText: 'export function summarizeModel(){ return {}; }\n',
        runDeadline: performance.now() + 5000, rss
      });
      assert.equal(row.outcome, expected, id);
      assert.equal(row.cleanup.exit_observed, true, id);
      assert.equal(row._summary_json, id === 'clean' ? '{"ok":1}' : null, id);
      if (id === 'nonzero' || id === 'never-exit') {
        assert.equal(row.prior_result.outcome, 'returned');
        assert.equal(row.constructor_returned, true);
        assert.equal('summary' in row, false);
      }
      if (id === 'late') assert.equal(row.constructor_returned, null);
      if (id === 'clean') {
        assert.equal(row.cleanup.exit_code, 0);
        assert.equal(row.cleanup.terminated_by_parent, false);
      }
    }
  } finally { hooks.createWorker = null; }
});

serial('short writes complete and zero-progress publication fails closed', async () => {
  const output = freshOut();
  const realWrite = fs.writeSync;
  let shorts = 0;
  fs.writeSync = (fd, buffer, offset, length, position) => {
    if (!shorts && length > 8) {
      shorts++;
      return realWrite(fd, buffer, offset, Math.max(1, Math.floor(length / 2)), position);
    }
    return realWrite(fd, buffer, offset, length, position);
  };
  try {
    const code = await main(['--input-root', INPUT_ROOT, '--client-source', CLIENT, '--profile', PROFILE,
      '--fixtures', FIXTURES, '--output', output, '--max-jobs', '0'], { stdout: { write() {} } });
    assert.equal(shorts, 1);
    assert.equal(code, 1);
    assert.equal(rows(output).length, 13);
    assert.equal(reportOf(output).jobs_file.records, 13);
    assert.equal(fs.readdirSync(output).some((name) => name.includes('.tmp')), false);
  } finally { fs.writeSync = realWrite; }

  const blocked = freshOut();
  let calls = 0;
  let owned = null;
  const realOpen = fs.openSync;
  const realClose = fs.closeSync;
  fs.openSync = (target, ...args) => {
    const fd = realOpen(target, ...args);
    if (typeof target === 'string' && target.endsWith('jobs.jsonl')) owned = fd;
    return fd;
  };
  fs.closeSync = (fd) => { const result = realClose(fd); if (fd === owned) owned = null; return result; };
  fs.writeSync = (fd, ...args) => {
    if (fd === owned) {
      if (++calls > 6) throw new Error('write loop did not stop');
      return 0;
    }
    return realWrite(fd, ...args);
  };
  let code;
  try {
    code = await main(['--input-root', INPUT_ROOT, '--client-source', CLIENT, '--profile', PROFILE,
      '--fixtures', FIXTURES, '--output', blocked, '--max-jobs', '0'], { stdout: { write() {} } });
  } finally {
    fs.openSync = realOpen;
    fs.closeSync = realClose;
    fs.writeSync = realWrite;
    if (owned !== null) try { realClose(owned); } catch { /* test cleanup only */ }
  }
  assert.equal(code, 1);
  assert.ok(calls >= 2 && calls <= 6);
  assert.equal(owned, null);
});

serial('opened growth is refused before the payload read and the fd is closed', () => {
  const file = path.join(TMP, 'growth.bin');
  const initial = Buffer.from('0123456789abcdef');
  fs.writeFileSync(file, initial, { mode: 0o600 });
  const options = { label: 'growth', maxBytes: 32, expectBytes: initial.length, expectSha: crypto.createHash('sha256').update(initial).digest('hex') };
  assert.equal(readPinnedFile(file, options).bytes, initial.length);
  const real = { open: fs.openSync, close: fs.closeSync, read: fs.readSync, append: fs.appendFileSync, alloc: Buffer.alloc };
  let armed = true;
  let fd = null;
  let closed = false;
  let reads = 0;
  let caught;
  fs.openSync = (target, ...args) => {
    if (armed && path.resolve(String(target)) === file) {
      armed = false;
      real.append(file, Buffer.from('x'.repeat(40)));
      fd = real.open(target, ...args);
      return fd;
    }
    return real.open(target, ...args);
  };
  fs.closeSync = (n) => { const result = real.close(n); if (n === fd) closed = true; return result; };
  fs.readSync = (n, ...args) => { if (n === fd) reads++; return real.read(n, ...args); };
  Buffer.alloc = (n, ...args) => real.alloc(n, ...args);
  try { readPinnedFile(file, options); } catch (error) { caught = error; }
  finally {
    fs.openSync = real.open; fs.closeSync = real.close; fs.readSync = real.read; Buffer.alloc = real.alloc;
    if (fd !== null && !closed) real.close(fd);
  }
  assert.ok(caught instanceof Refusal);
  assert.equal(closed, true);
  assert.equal(reads, 0);
});

serial('boundedRow does not keep a partial summary when the envelope is too small', () => {
  const row = {
    ...unattemptedRow({ id: 'cap', job_id: 'cap', kind: 'model', input_bytes: 1, complete_sha256: '0'.repeat(64), header_version_bytes: '00' }, 'none'),
    outcome: 'returned', constructor_returned: true, worker_started: true, cleanup: { exit_observed: true, exit_code: 0, terminated_by_parent: false },
    _log: '', _summary_json: JSON.stringify({ textures: ['許'.repeat(400)] })
  };
  const before = JSON.stringify(row);
  const got = boundedRow(row, { ...profile.policy, max_job_json_bytes: 700 }, 0);
  assert.ok(Buffer.byteLength(got.line) <= 700);
  assert.equal(got.row.outcome, 'summary_limit');
  assert.equal('summary' in got.row, false);
  assert.equal(JSON.stringify(row), before);
  const jobs = fixtureJobs(authored, profile.policy);
  assert.equal(jobs.length, 13);
  assert.equal(compareAuthored(jobs[0], { outcome: 'returned', summary: authored.cases[0].expected_summary }), true);
});

serial('writeAll retries a positive short write and stops on zero progress', () => {
  const file = path.join(TMP, 'write-all.bin');
  const fd = fs.openSync(file, 'wx', 0o600);
  const real = fs.writeSync;
  const payload = Buffer.from('許 model\n', 'utf8');
  let calls = 0;
  try {
    fs.writeSync = (n, buffer, offset, length, position) => {
      if (n !== fd) return real(n, buffer, offset, length, position);
      calls++;
      return real(n, buffer, offset, Math.min(3, length), position);
    };
    writeAll(fd, payload);
    assert.ok(calls > 1);
    assert.equal(fs.readFileSync(file).equals(payload), true);
  } finally { fs.writeSync = real; fs.closeSync(fd); }
  const zero = fs.openSync(path.join(TMP, 'zero.bin'), 'wx', 0o600);
  let zeros = 0;
  try {
    fs.writeSync = (n, ...args) => {
      if (n !== zero) return real(n, ...args);
      if (++zeros > 1) throw new Error('retried after zero');
      return 0;
    };
    assert.throws(() => writeAll(zero, payload), Refusal);
    assert.equal(zeros, 1);
  } finally { fs.writeSync = real; fs.closeSync(zero); }
});

// Root regressions after unchanged Grok integration. The I/O controls below
// use literal authored worker messages, not client/constructor observations.
const rootFixtureArgs = (output, ...extra) => ['--input-root', INPUT_ROOT, '--client-source', CLIENT,
  '--profile', PROFILE, '--fixtures', FIXTURES, '--output', output, ...extra];
const rootExpectedIds = () => authored.cases.map((entry) => entry.id);
const rootEio = () => Object.assign(new Error('authored root I/O fault'), { code: 'EIO' });
const rootPacket = (entry) => ({
  type: 'result', outcome: entry.expected_outcome,
  constructor_returned: entry.expected_outcome === 'returned', constructor_ms: 0,
  ...(entry.expected_outcome === 'returned'
    ? { summary_json: JSON.stringify(entry.expected_summary), summary_json_bytes: Buffer.byteLength(JSON.stringify(entry.expected_summary)) }
    : { exception: { phase: 'constructor', name: entry.expected_exception_name, message: 'authored exception' } }),
  log: { text: '', dropped: 0 }, loaded_module_keys: [...MODULE_KEYS], seek_globals: [1, 2, 3], dynamic_imports: []
});
const rootFakeWorkerFactory = (state) => () => {
  const entry = authored.cases[state.started++];
  assert.ok(entry, 'no extra authored worker');
  const worker = new EventEmitter();
  worker.stdout = new EventEmitter(); worker.stderr = new EventEmitter();
  worker.stdout.resume = worker.stderr.resume = () => {};
    endStandInStreamsOnExit(worker);
  worker.terminate = () => {
    state.terminated++;
    setImmediate(() => worker.emit('exit', 1));
    return Promise.resolve(1);
  };
  setImmediate(() => {
    worker.emit('message', { type: 'phase', phase: 'constructor' });
    worker.emit('message', rootPacket(entry));
    worker.emit('exit', 0);
  });
  return worker;
};

serial('root lower healthy job budgets retain every literal fixture result', () => {
  for (const cap of [1000, 10000]) {
    const r = cli(['--job-timeout-ms', String(cap)]);
    assert.equal(r.code, 0, `cap ${cap}: ${JSON.stringify(r.summary)}`);
    const got = rows(r.output);
    assert.deepEqual(got.map((row) => row.id), rootExpectedIds());
    authored.cases.forEach((entry, index) => {
      const row = got[index];
      assert.equal(row.outcome, entry.expected_outcome, `${cap}/${entry.id}`);
      assert.equal(row.constructor_returned, entry.expected_outcome === 'returned');
      assert.deepEqual(row.cleanup, { exit_observed: true, exit_code: 0, terminated_by_parent: false });
      if (entry.expected_outcome === 'returned') assert.deepStrictEqual(row.summary, entry.expected_summary);
      else {
        assert.equal(row.exception.phase, 'constructor');
        assert.equal(row.exception.name, entry.expected_exception_name);
        assert.equal('summary' in row, false);
      }
    });
    const rep = reportOf(r.output);
    assert.equal(rep.qualified, true);
    assert.equal(rep.authored_comparison.matched, 13);
    assert.equal(rep.effective_policy.job_timeout_ms, cap);
    assert.deepEqual([rep.counts.job_outcomes.returned, rep.counts.job_outcomes.constructor_exception], [9, 4]);
  }
});

serial('root timely result followed by stalled late exit0 is timeout with prior result', async () => {
  for (const outcome of ['returned', 'constructor_exception']) {
    const entry = authored.cases.find((item) => item.expected_outcome === outcome);
    const packet = rootPacket(entry);
    const state = { terminations: 0, messageAt: null, exitAt: null };
    const policy = { ...profile.policy, job_timeout_ms: 100, cleanup_wait_ms: 200 };
    const workerFactory = () => {
      const worker = new EventEmitter();
      worker.stdout = new EventEmitter(); worker.stderr = new EventEmitter();
      worker.stdout.resume = worker.stderr.resume = () => {};
    endStandInStreamsOnExit(worker);
      worker.terminate = () => {
        state.terminations++;
        setImmediate(() => worker.emit('exit', 1));
        return Promise.resolve(1);
      };
      setImmediate(() => {
        state.messageAt = performance.now();
        worker.emit('message', { type: 'phase', phase: 'constructor' });
        worker.emit('message', packet);
        // Deliberately block this same callback: the overdue timer cannot run
        // before exit0, so exit settlement itself must check the deadline.
        const until = performance.now() + policy.job_timeout_ms + 25;
        while (performance.now() < until) { /* finite authored event-loop stall */ }
        state.exitAt = performance.now();
        worker.emit('exit', 0);
      });
      return worker;
    };
    const row = await runWorkerJob({ id: entry.id, job_id: entry.id, kind: 'model',
      complete_sha256: entry.complete_sha256, input_bytes: entry.input_bytes,
      header_version_bytes: entry.header_version_bytes }, Buffer.from([0, 1]), {
      policy, sources: {}, summaryText: '', runDeadline: performance.now() + 5000,
      rss: { active: null, over: 0, sample() {} }, workerFactory
    });
    assert.ok(state.exitAt - state.messageAt >= policy.job_timeout_ms);
    assert.equal(row.outcome, 'timeout', outcome);
    assert.deepEqual(row.prior_result, { outcome, constructor_returned: outcome === 'returned' });
    assert.equal(row.constructor_returned, outcome === 'returned');
    assert.deepEqual(row.cleanup, { exit_observed: true, exit_code: 0, terminated_by_parent: false });
    assert.equal(state.terminations, 0);
    assert.equal(row._summary_json, null);
  }
});

serial('root final pin checks fully reread every fixture/source/rule/own file', async () => {
  const output = freshOut();
  const paths = [PROFILE, FIXTURES, path.join(REPO, profile.summary.path),
    ...MODULE_KEYS.map((key) => path.join(CLIENT, key)), ...RULE_KEYS.map((key) => path.join(CLIENT, key)),
    SCRIPT, path.join(HERE, 'model_constructor_worker.mjs')];
  const expected = new Map(paths.map((file) => [path.resolve(file), fs.readFileSync(file)]));
  const active = new Map(); const observed = [];
  const real = { open: fs.openSync, read: fs.readSync, close: fs.closeSync };
  let finalPhase = false;
  fs.openSync = (target, ...args) => {
    const fd = real.open(target, ...args);
    const file = typeof target === 'string' ? path.resolve(target) : null;
    if (expected.has(file)) active.set(fd, { file, finalPhase, chunks: [], bytes: 0, ordered: true, eof: false });
    return fd;
  };
  fs.readSync = (fd, buffer, offset, length, position) => {
    const n = real.read(fd, buffer, offset, length, position);
    const read = active.get(fd);
    if (read) {
      if (n > 0) {
        read.ordered &&= position === read.bytes;
        read.chunks.push(Buffer.from(buffer.subarray(offset, offset + n)));
        read.bytes += n;
      } else read.eof = true;
    }
    return n;
  };
  fs.closeSync = (fd) => {
    const result = real.close(fd);
    if (active.has(fd)) { observed.push(active.get(fd)); active.delete(fd); }
    return result;
  };
  hooks.beforeIdentityRecheck = () => { finalPhase = true; };
  let code;
  try { code = await main(rootFixtureArgs(output, '--max-jobs', '0'), { stdout: { write() {} } }); }
  finally {
    fs.openSync = real.open; fs.readSync = real.read; fs.closeSync = real.close;
    hooks.beforeIdentityRecheck = null;
  }
  assert.equal(code, 1);
  assert.equal(active.size, 0);
  assert.equal(expected.size, 15);
  for (const [file, body] of expected) {
    for (const phase of [false, true]) {
      const reads = observed.filter((item) => item.file === file && item.finalPhase === phase);
      assert.ok(reads.length >= 1, `${path.basename(file)}: ${phase ? 'final' : 'admission'} full read`);
      assert.ok(reads.some((item) => item.eof && item.ordered && item.bytes === body.length &&
        crypto.createHash('sha256').update(Buffer.concat(item.chunks)).digest('hex') === crypto.createHash('sha256').update(body).digest('hex')),
      `${path.basename(file)}: complete unchanged bytes`);
    }
  }
  const rep = reportOf(output);
  for (const group of [rep.client_source.sources, rep.client_source.rule_sources]) {
    for (const pin of group) assert.deepEqual(pin.identity, identityOf(fs.lstatSync(path.join(CLIENT, pin.path), { bigint: true })));
  }
});

// Faults affect only fresh output descriptors owned by this test. Hooks are
// restored before assertions/readback; any observed leak is recorded first,
// then only the exact still-owned fixture descriptor is closed for cleanup.
async function rootPublicationFault(mode) {
  const output = freshOut();
  const state = { started: 0, terminated: 0, injected: 0, partialBytes: 0,
    rollbackCalls: 0, rollbackFailed: false, writesAfterFailedRollback: 0, leaked: [] };
  const real = { open: fs.openSync, write: fs.writeSync, truncate: fs.ftruncateSync,
    close: fs.closeSync, rename: fs.renameSync };
  const owned = new Map();
  let jobsPhase = 0;
  const isJobs = (fd) => owned.get(fd)?.name === 'jobs.jsonl';
  const sameOwned = (fd, item) => {
    try {
      const now = fs.fstatSync(fd, { bigint: true });
      return now.dev === item.dev && now.ino === item.ino;
    } catch { return false; }
  };
  fs.openSync = (target, ...args) => {
    const fd = real.open(target, ...args);
    if (typeof target === 'string' && path.resolve(target).startsWith(output + path.sep)) {
      const stat = fs.fstatSync(fd, { bigint: true });
      owned.set(fd, { name: path.basename(target), dev: stat.dev, ino: stat.ino });
    }
    return fd;
  };
  fs.writeSync = (fd, buffer, offset, length, position) => {
    const name = owned.get(fd)?.name || '';
    if (mode === 'initial-checkpoint' && !state.injected && name.startsWith('.report.checkpoint.json.')) {
      state.injected++; throw rootEio();
    }
    if ((mode === 'partial-write' || mode === 'rollback-failure') && isJobs(fd)) {
      if (state.rollbackFailed) state.writesAfterFailedRollback++;
      if (jobsPhase === 0) {
        jobsPhase = 1;
        const n = real.write(fd, buffer, offset, Math.max(1, Math.floor(length / 2)), position);
        state.partialBytes += n;
        return n;
      }
      if (jobsPhase === 1) { jobsPhase = 2; state.injected++; throw rootEio(); }
    }
    return real.write(fd, buffer, offset, length, position);
  };
  fs.ftruncateSync = (fd, ...args) => {
    if (isJobs(fd)) {
      state.rollbackCalls++;
      if (mode === 'rollback-failure' && !state.rollbackFailed) {
        state.rollbackFailed = true;
        throw rootEio();
      }
    }
    return real.truncate(fd, ...args);
  };
  fs.closeSync = (fd) => {
    const name = owned.get(fd)?.name || '';
    const result = real.close(fd);
    owned.delete(fd);
    if (mode === 'final-close' && !state.injected && name.startsWith('.report.json.')) {
      state.injected++; throw rootEio(); // real release precedes the reported error
    }
    return result;
  };
  fs.renameSync = (from, to) => {
    if (mode === 'final-rename' && !state.injected && path.resolve(String(to)) === path.join(output, 'report.json')) {
      state.injected++; throw rootEio();
    }
    return real.rename(from, to);
  };
  hooks.createWorker = rootFakeWorkerFactory(state);
  let code;
  try { code = await main(rootFixtureArgs(output), { stdout: { write() {} } }); }
  finally {
    fs.openSync = real.open; fs.writeSync = real.write; fs.ftruncateSync = real.truncate;
    fs.closeSync = real.close; fs.renameSync = real.rename; hooks.createWorker = null;
    for (const [fd, item] of owned) {
      if (sameOwned(fd, item)) {
        state.leaked.push(item.name);
        real.close(fd); // fixture cleanup after leak observation, never an unknown fd
      }
    }
  }
  return { output, code, state };
}

function rootAssertRetainedAccounting(result) {
  const { output, code, state } = result;
  assert.equal(code, 1);
  assert.equal(state.injected, 1, 'the intended production fault was reached once');
  assert.deepEqual(state.leaked, [], 'no output fd leaked before fixture cleanup');
  assert.equal(state.terminated, 0);
  const reportFile = path.join(output, 'report.json');
  const checkpointFile = path.join(output, 'report.checkpoint.json');
  assert.ok(fs.existsSync(reportFile) || fs.existsSync(checkpointFile), 'accounting survives publication failure');
  const rep = JSON.parse(fs.readFileSync(fs.existsSync(reportFile) ? reportFile : checkpointFile, 'utf8'));
  assert.equal(rep.qualified, false);
  assert.deepEqual(rep.expected_job_ids || rep.job_ids, rootExpectedIds());
  if (rep.job_accounting) {
    assert.deepEqual(rep.job_accounting.map((row) => row.job_id), rootExpectedIds());
    rep.job_accounting.forEach((row, index) => {
      const entry = authored.cases[index];
      assert.equal(row.id, entry.id);
      assert.equal(row.kind, 'model');
      assert.equal(row.input_bytes, entry.input_bytes);
      assert.equal(row.complete_sha256, entry.complete_sha256);
      assert.equal(row.header_version_bytes, entry.header_version_bytes);
      assert.equal('summary' in row, false);
      assert.equal('log' in row, false);
    });
  }
  if (rep.counts) {
    assert.equal(rep.counts.expected_jobs, 13);
    assert.equal(Object.values(rep.counts.job_outcomes).reduce((sum, n) => sum + n, 0), 13);
    assert.equal(rep.counts.attempted, 13 - rep.counts.job_outcomes.unattempted);
    assert.equal(rep.cleanup.workers_started, state.started);
    assert.equal(rep.cleanup.exits_observed, state.started);
    assert.deepEqual(rep.cleanup.unverified, []);
  }
  return rep;
}

function rootAssertKnownJobsFile(output, rep) {
  const body = fs.readFileSync(path.join(output, 'jobs.jsonl'));
  assert.equal(body.at(-1), 10);
  const got = rows(output);
  assert.deepEqual(got.map((row) => row.job_id), rootExpectedIds());
  assert.equal(rep.counts.records, 13);
  assert.equal(rep.jobs_file.records, 13);
  assert.equal(rep.jobs_file.bytes, body.length);
  assert.equal(rep.jobs_file.sha256, crypto.createHash('sha256').update(body).digest('hex'));
}

serial('root initial checkpoint EIO starts no workers and retains all13 unattempted IDs', async () => {
  const result = await rootPublicationFault('initial-checkpoint');
  const rep = rootAssertRetainedAccounting(result);
  assert.equal(result.state.started, 0);
  assert.equal(rep.counts.attempted, 0);
  assert.equal(rep.counts.job_outcomes.unattempted, 13);
  assert.equal(rep.job_accounting.length, 13);
  assert.ok(rep.job_accounting.every((row) => row.outcome === 'unattempted' && row.worker_started === false && row.cleanup.exit_observed === null));
  rootAssertKnownJobsFile(result.output, rep);
});

serial('root jobs partial-EIO rollback preserves known bytes and every suffix ID', async () => {
  const result = await rootPublicationFault('partial-write');
  const rep = rootAssertRetainedAccounting(result);
  assert.ok(result.state.partialBytes > 0);
  assert.ok(result.state.rollbackCalls >= 1);
  assert.equal(result.state.rollbackFailed, false);
  assert.equal(result.state.started, 1);
  assert.equal(rep.counts.attempted, 1);
  assert.equal(rep.storage.jobs_tail_uncertain, false);
  rootAssertKnownJobsFile(result.output, rep);
});

serial('root failed jobs rollback stops writes and reports an uncertain tail without losing IDs', async () => {
  const result = await rootPublicationFault('rollback-failure');
  const rep = rootAssertRetainedAccounting(result);
  assert.ok(result.state.partialBytes > 0);
  assert.equal(result.state.rollbackFailed, true);
  assert.equal(result.state.writesAfterFailedRollback, 0);
  assert.equal(result.state.started, 1);
  assert.equal(rep.storage.jobs_tail_uncertain, true);
  assert.equal(rep.jobs_file.bytes, null);
  assert.equal(rep.jobs_file.sha256, null);
  assert.deepEqual(rep.jobs_file.confirmed_prefix, {
    bytes: 0, sha256: crypto.createHash('sha256').update(Buffer.alloc(0)).digest('hex'), records: 0
  });
  assert.equal(rep.job_accounting.length, 13);
  assert.equal(rep.counts.records, 0);
  const physical = fs.readFileSync(path.join(result.output, 'jobs.jsonl'));
  assert.equal(physical.length, result.state.partialBytes);
});

for (const mode of ['final-close', 'final-rename']) {
  serial(`root ${mode} publication failure refuses qualification and retains all IDs`, async () => {
    const result = await rootPublicationFault(mode);
    const rep = rootAssertRetainedAccounting(result);
    assert.equal(result.state.started, 13);
    const got = rows(result.output);
    assert.deepEqual(got.map((row) => row.job_id), rootExpectedIds());
    authored.cases.forEach((entry, index) => {
      assert.equal(got[index].outcome, entry.expected_outcome);
      if (entry.expected_outcome === 'returned') assert.deepStrictEqual(got[index].summary, entry.expected_summary);
      else assert.equal(got[index].exception.name, entry.expected_exception_name);
    });
    if (rep.jobs_file) rootAssertKnownJobsFile(result.output, rep);
  });
}

serial('root oversized final report cannot bypass the cap through failure retry', async () => {
  const output = freshOut();
  const real = JSON.stringify;
  const oversized = ' '.repeat(profile.policy.max_report_json_bytes + 1);
  const state = { started: 0, terminated: 0, replacements: 0 };
  JSON.stringify = (value, ...args) => {
    if (value?.schema === 'T06-model-constructor-report-1' && !value.checkpoint) {
      state.replacements++;
      return oversized; // finite serializer fault; never allowed onto disk
    }
    return real(value, ...args);
  };
  hooks.createWorker = rootFakeWorkerFactory(state);
  let code;
  try { code = await main(rootFixtureArgs(output), { stdout: { write() {} } }); }
  finally { JSON.stringify = real; hooks.createWorker = null; }
  assert.equal(code, 1);
  assert.ok(state.replacements >= 3, 'initial, compacted and retry paths reached');
  assert.equal(state.started, 13);
  assert.equal(state.terminated, 0);
  assert.deepEqual(fs.readdirSync(output).sort(), ['jobs.jsonl', 'report.checkpoint.json']);
  const checkpoint = JSON.parse(fs.readFileSync(path.join(output, 'report.checkpoint.json'), 'utf8'));
  assert.equal(checkpoint.qualified, false);
  assert.deepEqual(checkpoint.job_ids, rootExpectedIds());
  assert.deepEqual(rows(output).map((row) => row.job_id), rootExpectedIds());
});

serial('root whole-run deadline includes admission before any worker starts', async () => {
  const output = freshOut();
  const realOpen = fs.openSync;
  const state = { started: 0, terminated: 0, delays: 0 };
  fs.openSync = (target, ...args) => {
    if (typeof target === 'string' && path.resolve(target) === PROFILE && state.delays === 0) {
      state.delays++;
      Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 125);
    }
    return realOpen(target, ...args);
  };
  hooks.createWorker = rootFakeWorkerFactory(state);
  let code;
  try { code = await main(rootFixtureArgs(output, '--run-timeout-ms', '100'), { stdout: { write() {} } }); }
  finally { fs.openSync = realOpen; hooks.createWorker = null; }
  assert.equal(state.delays, 1);
  assert.equal(state.started, 0);
  assert.equal(code, 1);
  const rep = reportOf(output);
  assert.equal(rep.qualified, false);
  assert.ok(rep.elapsed_ms >= 125);
  assert.equal(rep.counts.attempted, 0);
  assert.equal(rep.counts.job_outcomes.unattempted, 13);
  assert.ok(rows(output).every((row) => row.outcome === 'unattempted' && row.reason === 'run_deadline'));
});

// Logging controls use authored stream events/console calls. Fake result
// packets here are not additional constructor or retained-corpus evidence.
async function rootLogStreamRow(chunks, { captureCap = 4096, consoleText = '', droppedEntries = 0 } = {}) {
  const entry = authored.cases[0];
  let terminations = 0;
  const workerFactory = () => {
    const worker = new EventEmitter();
    worker.stdout = new EventEmitter(); worker.stderr = new EventEmitter();
    worker.stdout.resume = worker.stderr.resume = () => {};
    endStandInStreamsOnExit(worker);
    worker.terminate = () => {
      terminations++;
      setImmediate(() => worker.emit('exit', 1));
      return Promise.resolve(1);
    };
    setImmediate(() => {
      for (const [channel, bytes] of chunks) worker[channel].emit('data', Buffer.from(bytes));
      // Exercise stream-end flushing as well as the subsequent settlement.
      worker.stdout.emit('end'); worker.stderr.emit('end');
      worker.emit('message', { type: 'phase', phase: 'constructor' });
      worker.emit('message', { ...rootPacket(entry), log: { text: consoleText, dropped: droppedEntries } });
      worker.emit('exit', 0);
    });
    return worker;
  };
  const row = await runWorkerJob({ id: entry.id, job_id: entry.id, kind: 'model',
    complete_sha256: entry.complete_sha256, input_bytes: entry.input_bytes,
    header_version_bytes: entry.header_version_bytes }, Buffer.from([0, 1]), {
    policy: { ...profile.policy, max_job_log_bytes: captureCap }, sources: {}, summaryText: '',
    runDeadline: performance.now() + 5000, rss: { active: null, over: 0, sample() {} }, workerFactory
  });
  assert.equal(row.outcome, 'returned');
  assert.equal(row.cleanup.exit_observed, true);
  assert.equal(terminations, 0);
  return row;
}

function rootLoggingInput(text, extra = {}) {
  return {
    ...unattemptedRow({ id: 'authored-log', job_id: 'authored-log', kind: 'model', input_bytes: 2,
      complete_sha256: '0'.repeat(64), header_version_bytes: '4752' }, 'authored'),
    outcome: 'returned', constructor_returned: true, worker_started: true,
    cleanup: { exit_observed: true, exit_code: 0, terminated_by_parent: false },
    _summary_json: '{}', _log: text, _log_dropped_entries: 0, _stdio_dropped_utf8_bytes: 0, ...extra
  };
}

function rootAssertLog(formatted, { text, entries = 0, stdio = 0, formatter = 0, truncated = false, omitted } = {}) {
  const row = formatted.row;
  assert.equal(row.log || '', text);
  assert.equal(formatted.logBytes, Buffer.byteLength(text));
  assert.equal('log_dropped' in row, false, 'no ambiguous entry-plus-byte unit');
  for (const [key, count] of [['log_dropped_entries', entries], ['stdio_dropped_utf8_bytes', stdio]]) {
    if (count) assert.equal(row[key], count, key);
    else assert.equal(key in row, false, `${key} is positive-only`);
  }
  assert.equal(row.log_dropped_utf8_bytes || 0, formatter);
  assert.equal(Boolean(row.log_truncated), truncated);
  if (omitted !== undefined) assert.equal(Boolean(row.log_omitted), omitted);
  assert.equal('_log' in row, false);
  assert.equal('_log_dropped_entries' in row, false);
  assert.equal('_stdio_dropped_utf8_bytes' in row, false);
}

serial('root logs decode split UTF8 independently per channel and retain genuine U+FFFD', async () => {
  const emoji = Buffer.from([0xf0, 0x9f, 0x98, 0x80]);
  const han = Buffer.from([0xe8, 0xa8, 0xb1]);
  for (const split of [1, 2, 3]) {
    const row = await rootLogStreamRow([
      ['stdout', emoji.subarray(0, split)], ['stderr', han.subarray(0, 2)],
      ['stdout', emoji.subarray(split)], ['stderr', han.subarray(2)],
      ['stdout', Buffer.from([0xef, 0xbf, 0xbd])]
    ]);
    assert.equal(row._log, '😀許�');
    rootAssertLog(boundedRow(row, profile.policy, 4096), { text: '😀許�', omitted: false });
  }
  const unfinished = await rootLogStreamRow([['stdout', Buffer.from([0xf0, 0x9f])]]);
  assert.equal(unfinished._log, '�', 'decoder end plus settlement flushes an unfinished sequence once');
  rootAssertLog(boundedRow(unfinished, profile.policy, 4096), { text: '�', omitted: false });
});

serial('root capture byte boundaries keep a valid prefix then stop retaining after truncation', async () => {
  const cases = [
    ['AAAAAAAA', '許', 'AAAAAAAA', 4], ['AAAAAAA', '許', 'AAAAAAA', 4],
    ['AAAAAA', '許', 'AAAAAA', 4], ['AAAAA', '許', 'AAAAA許', 1],
    ['AAAAAAAA', '😀', 'AAAAAAAA', 5], ['AAAAAAA', '😀', 'AAAAAAA', 5],
    ['AAAAAA', '😀', 'AAAAAA', 5], ['AAAAA', '😀', 'AAAAA', 5],
    ['AAAA', '😀', 'AAAA😀', 1]
  ];
  for (const [prefix, character, expected, lost] of cases) {
    const row = await rootLogStreamRow([
      ['stdout', Buffer.from(prefix)], ['stdout', Buffer.from(character)], ['stderr', Buffer.from('B')]
    ], { captureCap: 8 });
    assert.equal(row._log, expected);
    assert.equal(row._stdio_dropped_utf8_bytes, lost);
    rootAssertLog(boundedRow(row, { ...profile.policy, max_job_log_bytes: 8 }, 8),
      { text: expected, stdio: lost, truncated: true, omitted: false });
  }
  const onlyDrops = rootLoggingInput('', { _log_dropped_entries: 2, _stdio_dropped_utf8_bytes: 10 });
  rootAssertLog(boundedRow(onlyDrops, profile.policy, 4096), { text: '', entries: 2, stdio: 10, truncated: true });
});

serial('root log accounting keeps console entries separate from dropped stdio bytes', async () => {
  const row = await rootLogStreamRow([
    ['stdout', Buffer.from('A'.repeat(4096))], ['stderr', Buffer.from('B'.repeat(10))]
  ], { droppedEntries: 2 });
  assert.equal(row._log_dropped_entries, 2);
  assert.equal(row._stdio_dropped_utf8_bytes, 10);
  rootAssertLog(boundedRow(row, profile.policy, 4096),
    { text: 'A'.repeat(4096), entries: 2, stdio: 10, truncated: true, omitted: false });
});

serial('root formatter loss remains exact through zero budget, omission and compact rows', () => {
  // Literal UTF8 lengths: "log: 許"=8, newline=1, emoji=4, U+FFFD=3; total16.
  const input = rootLoggingInput('log: 許\n😀�', { _log_dropped_entries: 2, _stdio_dropped_utf8_bytes: 4 });
  const before = JSON.stringify(input);
  for (const [budget, text, formatter, omitted] of [
    [16, 'log: 許\n😀�', 0, false], [13, 'log: 許\n😀', 3, false],
    [12, 'log: 許\n', 7, false], [0, '', 16, true]
  ]) {
    rootAssertLog(boundedRow(input, profile.policy, budget),
      { text, formatter, entries: 2, stdio: 4, truncated: true, omitted });
    assert.equal(JSON.stringify(input), before);
  }
  const omitted = boundedRow(input, profile.policy, 16, true);
  rootAssertLog(omitted, { text: '', entries: 2, stdio: 4, formatter: 16, truncated: true, omitted: true });
  assert.equal(omitted.row.outcome, 'summary_limit');
  for (const compact of [false, true]) {
    const crowded = { ...input, _summary_json: JSON.stringify({ authored: 'x'.repeat(4000) }),
      ...(compact ? { authored_extra_diagnostic: 'x'.repeat(4000) } : {}) };
    const snapshot = JSON.stringify(crowded);
    const got = boundedRow(crowded, { ...profile.policy, max_job_json_bytes: 1000 }, 16);
    assert.ok(Buffer.byteLength(got.line) <= 1000);
    rootAssertLog(got, { text: '', entries: 2, stdio: 4, formatter: 16, truncated: true, omitted: true });
    assert.equal('summary' in got.row, false);
    assert.equal('authored_extra_diagnostic' in got.row, false);
    assert.equal(JSON.stringify(crowded), snapshot);
    assert.deepEqual(boundedRow(crowded, { ...profile.policy, max_job_json_bytes: 1000 }, 16), got);
  }
  assert.equal(JSON.stringify(input), before);
});

serial('root recovered jobs EIO reports omitted log bytes without crediting durable log text', async () => {
  const output = freshOut();
  const real = { open: fs.openSync, close: fs.closeSync, write: fs.writeSync };
  const state = { started: 0, terminated: 0, injected: 0 };
  const factory = rootFakeWorkerFactory(state);
  let jobsFd = null; let jobsIdentity = null; let leaked = false;
  fs.openSync = (target, ...args) => {
    const fd = real.open(target, ...args);
    if (typeof target === 'string' && path.resolve(target) === path.join(output, 'jobs.jsonl')) {
      jobsFd = fd; jobsIdentity = fs.fstatSync(fd, { bigint: true });
    }
    return fd;
  };
  fs.closeSync = (fd) => {
    const result = real.close(fd);
    if (fd === jobsFd) jobsFd = null;
    return result;
  };
  fs.writeSync = (fd, ...args) => {
    if (fd === jobsFd && state.injected === 0) { state.injected++; throw rootEio(); }
    return real.write(fd, ...args);
  };
  hooks.createWorker = (...args) => {
    const first = state.started === 0;
    const worker = factory(...args);
    const emit = worker.emit.bind(worker);
    worker.emit = (event, packet, ...rest) => {
      if (first && event === 'message' && packet?.type === 'result') {
        worker.stdout.emit('data', Buffer.from('ABC'));
        return emit(event, { ...packet, log: { text: 'log: 許😀', dropped: 2 } }, ...rest);
      }
      return emit(event, packet, ...rest);
    };
    return worker;
  };
  let code;
  try { code = await main(rootFixtureArgs(output), { stdout: { write() {} } }); }
  finally {
    fs.openSync = real.open; fs.closeSync = real.close; fs.writeSync = real.write; hooks.createWorker = null;
    if (jobsFd !== null) {
      const current = fs.fstatSync(jobsFd, { bigint: true });
      if (current.dev === jobsIdentity.dev && current.ino === jobsIdentity.ino) {
        leaked = true; real.close(jobsFd); // observe first, clean only the fixture's owned fd
      }
    }
  }
  assert.equal(code, 1);
  assert.equal(state.injected, 1);
  assert.equal(state.started, 1);
  assert.equal(state.terminated, 0);
  assert.equal(leaked, false);
  const rep = reportOf(output);
  rootAssertKnownJobsFile(output, rep);
  const first = rows(output)[0];
  assert.equal(first.outcome, 'environment_failure');
  rootAssertLog({ row: first, logBytes: 0 },
    { text: '', entries: 2, formatter: 16, truncated: true, omitted: true });
  assert.equal(rep.logs.bytes, 0);
});

serial('root realm console budgets astral UTF8 as4bytes with its declared newline reserve', async () => {
  const sources = {};
  for (const key of MODULE_KEYS) {
    const pin = profile.sources[key];
    sources[key] = readPinnedFile(path.join(CLIENT, key),
      { label: key, maxBytes: pin.bytes, expectBytes: pin.bytes, expectSha: pin.sha256 }).buffer.toString('utf8');
  }
  const realm = await createRealm(sources, { maxLogBytes: 4096 });
  const machine = await import('node:vm');
  assert.equal(realm.logs().text, '');
  machine.runInContext("console.log('A'.repeat(4086) + '😀')", realm.context);
  const expected = 'log: ' + 'A'.repeat(4086) + '😀'; //4095bytes plus the reserved newline fits
  assert.equal(Buffer.byteLength(expected), 4095);
  assert.equal(realm.logs().text, expected);
  assert.equal(realm.logs().dropped, 0);
  machine.runInContext("console.log('B')", realm.context);
  assert.equal(realm.logs().text, expected);
  assert.equal(realm.logs().dropped, 1);
});

serial('root600-byte CLI cap refuses mandatory log-loss accounting before output or workers', async () => {
  const output = freshOut();
  let started = 0;
  const stdout = [];
  hooks.createWorker = () => { started++; throw new Error('authored preflight must not launch a worker'); };
  let code;
  try {
    code = await main(rootFixtureArgs(output, '--max-job-json-bytes', '600'),
      { stdout: { write(chunk) { stdout.push(Buffer.from(chunk)); } } });
  } finally { hooks.createWorker = null; }
  assert.equal(code, 2);
  assert.equal(started, 0);
  assert.equal(fs.existsSync(output), false);
  const text = Buffer.concat(stdout).toString('utf8');
  assert.ok(Buffer.byteLength(text) <= 4096);
  const receipt = JSON.parse(text);
  assert.equal(receipt.reason, 'output_budget');
  assert.equal(receipt.output_created, false);
});

// T07.007.008 exact supplement route. Negative JSON semantics use the bounded
// afterPinnedJson hook, which runs only after a complete pinned read and hash;
// canonical inputs are never written. --max-jobs controls are not corpus evidence.
const NEW_PROFILE = path.join(REPO, 'docs/project/fixtures/T07.007.008-profile.json');
const BASELINE = JSON.parse(fs.readFileSync(path.join(REPO, 'docs/project/fixtures/T07.007.008-baseline.json'), 'utf8'));
const newProfile = JSON.parse(fs.readFileSync(NEW_PROFILE, 'utf8'));
const MANIFEST = path.join(INPUT_ROOT, newProfile.manifest.path);
const OLD_MANIFEST = path.join(INPUT_ROOT, profile.manifest.path);
const WORKER = path.join(HERE, 'model_constructor_worker.mjs');
const sha256Of = (buf) => crypto.createHash('sha256').update(buf).digest('hex');
const supplementArgs = (output, ...extra) => ['--input-root', INPUT_ROOT, '--client-source', CLIENT,
  '--profile', NEW_PROFILE, '--manifest', MANIFEST, '--output', output, ...extra];
const supplementFixtureArgs = (output, ...extra) => ['--input-root', INPUT_ROOT, '--client-source', CLIENT,
  '--profile', NEW_PROFILE, '--fixtures', FIXTURES, '--output', output, ...extra];
const supplementManifest = () => JSON.parse(fs.readFileSync(MANIFEST, 'utf8'));
async function mainCapture(args) {
  const chunks = [];
  const code = await main(args, { stdout: { write(chunk) { chunks.push(Buffer.from(chunk)); } } });
  const text = Buffer.concat(chunks).toString('utf8');
  assert.ok(Buffer.byteLength(text) <= 4096);
  assert.equal(text.includes('/Users'), false);
  return { code, summary: JSON.parse(text) };
}
async function withPinnedJson(mutations, args) {
  const seen = [];
  hooks.afterPinnedJson = (role, value) => {
    seen.push(role);
    if (!mutations[role]) return value;
    const copy = structuredClone(value);
    const replaced = mutations[role](copy);
    return replaced === undefined ? copy : replaced;
  };
  try { return { ...(await mainCapture(args)), seen }; } finally { hooks.afterPinnedJson = null; }
}
const supplementPacket = () => ({
  type: 'result', outcome: 'returned', constructor_returned: true, constructor_ms: 0,
  summary_json: '{"authored":true}', summary_json_bytes: 17,
  log: { text: '', dropped: 0 }, loaded_module_keys: [...MODULE_KEYS], seek_globals: [1, 2, 3], dynamic_imports: []
});
// Authored worker events: plan[i] is 'clean', 'nonzero', 'silent' (no result) or 'lost' (terminate never exits).
const supplementFakeWorkers = (plan, state) => () => {
  const kind = plan[state.started++] || 'clean';
  const worker = new EventEmitter();
  worker.stdout = new EventEmitter(); worker.stderr = new EventEmitter();
  worker.stdout.resume = worker.stderr.resume = () => {};
    endStandInStreamsOnExit(worker);
  worker.terminate = () => {
    state.terminated++;
    if (kind !== 'lost') setImmediate(() => worker.emit('exit', 1));
    return Promise.resolve(1);
  };
  setImmediate(() => {
    worker.emit('message', { type: 'phase', phase: 'constructor' });
    if (kind === 'silent' || kind === 'lost') return;
    worker.emit('message', supplementPacket());
    worker.emit('exit', kind === 'nonzero' ? 1 : 0);
  });
  return worker;
};

serial('T07 exact profile pins select their own routes and match the frozen baseline', () => {
  const bytes = fs.readFileSync(NEW_PROFILE);
  assert.equal(sha256Of(bytes), SUPPLEMENT_PROFILE_SHA256);
  assert.equal(bytes.length, BASELINE.profile.bytes);
  assert.equal(SUPPLEMENT_PROFILE_SHA256, BASELINE.profile.sha256);
  assert.equal(ROUTES[PROFILE_SHA256].task, 'T06.003.003.006');
  assert.equal(ROUTES[SUPPLEMENT_PROFILE_SHA256].task, 'T07.007.008');
  assert.deepStrictEqual(structuredClone(EXECUTION_BINDING_EXPECTED), BASELINE.execution_binding_expected);
  assert.deepStrictEqual(structuredClone(ARTIFACT_AUDIT_EXPECTED), BASELINE.artifact_audit_expected);
  assert.deepStrictEqual(newProfile.policy, BASELINE.old_profile_policy_unchanged);
  assert.deepStrictEqual(profile.policy, BASELINE.old_profile_policy_unchanged);
  assert.deepStrictEqual(newProfile.summary_limits, BASELINE.old_summary_limits_unchanged);
  assert.deepStrictEqual(newProfile.counts, BASELINE.new_counts);
  assert.deepStrictEqual(newProfile.header_prefix_counts, BASELINE.new_header_observations);
  assert.deepStrictEqual(newProfile.availability, BASELINE.availability);
  assert.deepStrictEqual(newProfile.manifest, BASELINE.manifest);
  for (const pin of BASELINE.baseline_sources.filter((item) => !item.path.startsWith('tools/renewal/probe_') && !item.path.startsWith('tools/renewal/test_'))) {
    const abs = pin.path.startsWith('.tools/') ? path.join(INPUT_ROOT, pin.path) : path.join(REPO, pin.path);
    const body = fs.readFileSync(abs);
    assert.deepEqual([body.length, sha256Of(body)], [pin.bytes, pin.sha256], pin.path);
  }
  const route = ROUTES[SUPPLEMENT_PROFILE_SHA256];
  assert.equal(validateProfile(structuredClone(newProfile), route).task, 'T07.007.008');
  assert.throws(() => validateProfile(structuredClone(newProfile)), (error) => error.reason === 'profile_invalid');
  assert.throws(() => validateProfile(structuredClone(profile), route), (error) => error.reason === 'profile_invalid');
  const bad = [
    (p) => { p.policy.job_timeout_ms = '20000'; },
    (p) => { p.policy.rss_limit_bytes = true; },
    (p) => { p.policy.run_timeout_ms = 900000.5; },
    (p) => { p.policy.cleanup_wait_ms = 2 ** 53; },
    (p) => { p.counts.model_targets = 273.5; },
    (p) => { p.counts.roots = '4'; },
    (p) => { p.counts.remaining_core_gap_roots = false; },
    (p) => { delete p.availability.execution; },
    (p) => { p.availability.extra = p.availability.report; },
    (p) => { p.availability.execution.bytes = '5454'; },
    (p) => { delete p.worker; },
    (p) => { p.worker.sha256 = 'x'; },
    (p) => { p.header_prefix_counts['4752534d0203'] = 167; },
    (p) => { p.header_prefix_counts['4752534d0203'] = true; },
    (p) => { p.summary_limits.nodes = 0; }
  ];
  for (const mutate of bad) {
    const copy = structuredClone(newProfile);
    mutate(copy);
    assert.throws(() => validateProfile(copy, route), (error) => error.reason === 'profile_invalid', mutate.toString());
  }
  assert.throws(() => assertExactDecimalIdentity({ dev: 1, ino: '2', size: '3', mtime_ns: '4', ctime_ns: '5' }, 'x'), (error) => error.reason === 'identity_precision');
  assert.throws(() => assertExactDecimalIdentity({ dev: '1', ino: '2', size: '3', mtime_ns: '4', ctime_ns: '5', extra: '6' }, 'x'), (error) => error.reason === 'identity_precision');
  assert.throws(() => assertExactDecimalIdentity({ dev: '01', ino: '2', size: '3', mtime_ns: '4', ctime_ns: '5' }, 'x'), (error) => error.reason === 'identity_precision');
  assert.throws(() => assertExactDecimalIdentity({ dev: '1', ino: '2', size: '3', mtime_ns: '4', ctime_ns: '5' }, 'x', 4), (error) => error.reason === 'identity_precision');
  assertExactDecimalIdentity({ dev: '1', ino: '2', size: '3', mtime_ns: '9007199254740993', ctime_ns: '5' }, 'x', 3);
});

serial('T07 historical receipt integer tuple is admitted typed, never as decimal strings', () => {
  const receipt = JSON.parse(fs.readFileSync(path.join(INPUT_ROOT, newProfile.availability.execution.path), 'utf8'));
  const identity = receipt.guard_result.driver_pin.identity;
  assert.equal(identity.length, 5);
  assert.ok(identity.every((item) => Number.isInteger(item)));
  assert.equal(Number.isSafeInteger(identity[3]), false, 'nanosecond member exceeds the safe range');
  validateExecutionReceipt(receipt);
  const stringly = structuredClone(receipt);
  stringly.guard_result.driver_pin.identity = identity.map(String);
  assert.throws(() => validateExecutionReceipt(stringly), (error) => error.reason === 'admission_discrepancy');
  const decimalObject = structuredClone(receipt);
  decimalObject.guard_result.driver_pin.identity = { dev: '1', ino: '2', size: '112136', mtime_ns: '3', ctime_ns: '4' };
  assert.throws(() => validateExecutionReceipt(decimalObject), (error) => error.reason === 'admission_discrepancy');
});

serial('T07 fixture CLI keeps all 13 literal results under the new task', () => {
  const r = cli([], { prof: NEW_PROFILE });
  assert.equal(r.code, 0, JSON.stringify(r.summary));
  assert.equal(r.summary.authored_matched, 13);
  const got = rows(r.output);
  assert.deepEqual(got.map((row) => row.id), authored.cases.map((entry) => entry.id));
  authored.cases.forEach((entry, index) => {
    const row = got[index];
    assert.equal(row.outcome, entry.expected_outcome, entry.id);
    assert.deepEqual(row.cleanup, { exit_observed: true, exit_code: 0, terminated_by_parent: false, stdout_eof_observed: true, stderr_eof_observed: true });
    assert.deepEqual(row.seek_globals, [1, 2, 3]);
    assert.deepEqual(row.dynamic_import_refusals, []);
    if (entry.expected_outcome === 'returned') {
      assert.equal(row.constructor_returned, true);
      assert.deepStrictEqual(row.summary, entry.expected_summary, entry.id);
    } else {
      assert.equal(row.constructor_returned, false);
      assert.equal(row.exception.phase, 'constructor');
      assert.equal(row.exception.name, entry.expected_exception_name);
      assert.equal('summary' in row, false);
    }
  });
  const rep = reportOf(r.output);
  assert.equal(rep.schema, 'T06-model-constructor-report-1');
  assert.equal(rep.task, 'T07.007.008');
  assert.equal(rep.qualified, true);
  assert.equal(rep.profile_sha256, SUPPLEMENT_PROFILE_SHA256);
  assert.deepEqual(rep.preserved_counts, newProfile.counts);
  assert.deepEqual(rep.pinned_inputs.map((pin) => pin.role), ['profile', 'worker', 'summary', 'fixtures']);
  assert.equal(rep.authored_comparison.matched, 13);
  assert.deepEqual([rep.counts.job_outcomes.returned, rep.counts.job_outcomes.constructor_exception], [9, 4]);
  assert.equal('functional' in rep, false);
  const old = cli([]);
  assert.equal(old.code, 0);
  assert.equal(reportOf(old.output).task, 'T06.003.003.006');
  assert.deepEqual(reportOf(old.output).pinned_inputs.map((pin) => pin.role), ['profile', 'summary', 'fixtures']);
});

serial('T07 fixture mode never opens the manifest, availability inputs, ledger profile or bodies', async () => {
  const output = freshOut();
  const opened = [];
  const real = fs.openSync;
  fs.openSync = (target, ...args) => {
    if (typeof target === 'string') opened.push(path.resolve(target));
    return real(target, ...args);
  };
  let result;
  try { result = await mainCapture(supplementFixtureArgs(output, '--max-jobs', '0')); } finally { fs.openSync = real; }
  assert.equal(result.code, 1);
  const forbidden = [MANIFEST, ...Object.values(newProfile.availability).map((pin) => path.join(INPUT_ROOT, pin.path)),
    path.join(INPUT_ROOT, 'docs/project/fixtures/T06.003.003.006-profile.json'), path.join(INPUT_ROOT, '.tools/renewal/t07-007-006-integrated-actual-1/output')];
  for (const item of forbidden) assert.equal(opened.some((file) => file.startsWith(item)), false, item);
  assert.ok(opened.includes(WORKER));
  assert.ok(rows(output).every((row) => row.outcome === 'unattempted' && row.reason === 'max_jobs'));
});

serial('T07 cross-route substitutions refuse before output', async () => {
  let r = cli([], { mode: ['--manifest', MANIFEST] });
  assert.equal(r.code, 2);
  assert.equal(r.summary.reason, 'path_refused');
  r = cli([], { prof: NEW_PROFILE, mode: ['--manifest', OLD_MANIFEST] });
  assert.equal(r.code, 2);
  assert.equal(r.summary.reason, 'path_refused');
  const elsewhere = freshOut();
  let result = await mainCapture(['--input-root', REPO, '--client-source', CLIENT, '--profile', NEW_PROFILE,
    '--manifest', path.join(REPO, newProfile.manifest.path), '--output', elsewhere]);
  assert.equal(result.code, 2);
  assert.equal(result.summary.reason, 'path_refused');
  assert.equal(fs.existsSync(elsewhere), false);
  const oldDoc = structuredClone(profile);
  const cases = [
    [{ profile: () => oldDoc }, 'profile_invalid'],
    [{ profile: (p) => { p.task = 'T06.003.003.006'; } }, 'profile_invalid'],
    [{ manifest: (m) => { m.task = 'T06.003.003.006'; } }, 'admission_discrepancy'],
    [{ manifest: (m) => { m.availability.root_audit = { ...m.availability.root_audit, path: profile.availability.root_audit.path, bytes: profile.availability.root_audit.bytes, sha256: profile.availability.root_audit.sha256 }; } }, 'admission_discrepancy'],
    [{ manifest: (m) => { m.world_gap_ledger_reference.profile.sha256 = SUPPLEMENT_PROFILE_SHA256; } }, 'admission_discrepancy']
  ];
  for (const [mutations, reason] of cases) {
    const output = freshOut();
    result = await withPinnedJson(mutations, supplementArgs(output));
    assert.equal(result.code, 2, JSON.stringify(result.summary));
    assert.equal(result.summary.reason, reason, Object.keys(mutations).join());
    assert.ok(Object.keys(mutations).every((role) => result.seen.includes(role)));
    assert.equal(fs.existsSync(output), false);
  }
});

serial('T07 positive admission fully hashes every pinned input and all 273 bodies with a zero-job suffix', async () => {
  const output = freshOut();
  const result = await withPinnedJson({}, supplementArgs(output, '--max-jobs', '0'));
  assert.equal(result.code, 1);
  assert.deepEqual(result.seen, ['profile', 'manifest', 'report', 'catalog', 'root_audit', 'execution', 'world_ledger_profile']);
  const rep = reportOf(output);
  assert.equal(rep.task, 'T07.007.008');
  assert.equal(rep.qualified, false);
  const byRole = Object.fromEntries(rep.pinned_inputs.map((pin) => [pin.role, pin]));
  for (const [role, key] of [['availability_report', 'report'], ['catalog', 'catalog'], ['root_audit', 'root_audit'], ['execution_receipt', 'execution']]) {
    const body = fs.readFileSync(path.join(INPUT_ROOT, BASELINE.availability[key].path));
    assert.deepEqual([byRole[role].bytes, byRole[role].sha256], [BASELINE.availability[key].bytes, BASELINE.availability[key].sha256]);
    assert.equal(sha256Of(body), byRole[role].sha256);
  }
  assert.deepEqual([byRole.corpus.bytes, byRole.corpus.sha256], [BASELINE.manifest.bytes, BASELINE.manifest.sha256]);
  assert.deepEqual([byRole.worker.bytes, byRole.worker.sha256], [11388, 'c1eee8dabacf3e69bb2fbe7fde8ed4e5fbd386a4a3ac768936484beceb22a3f4']);
  assert.deepEqual([byRole.world_ledger_profile.bytes, byRole.world_ledger_profile.sha256], [4855, PROFILE_SHA256]);
  assert.deepEqual(rep.postchecks, { checked: 273, ok: true });
  assert.equal(rep.source_postchecks.ok, true);
  assert.equal(rep.counts.job_outcomes.unattempted, 273);
  assert.equal(rep.functional.all_model_constructors_returned, false);
  assert.equal(rep.functional.open_failures.length, 273);
  assert.deepEqual(rep.availability_admission, {
    report_task: 'T07.007.006', catalog_task: 'T07.007.005', root_audit_status: 'complete_observation_artifacts_consistent',
    request_records: 314, request_wire_bytes: 7575826, request_stored_bytes: 7575826, target_body_bytes: 7575328,
    model_targets: 273, carried_bmp_targets: 38, ground_referrers: 40, model_referrers: 297, placement_occurrences: 4922,
    execution_receipt_executed: false, native_inputs_reopened: false
  });
  assert.ok(rows(output).every((row) => row.outcome === 'unattempted' && row.reason === 'max_jobs' && row.worker_started === false));
});

serial('T07 admission refuses typed semantic drift after full pinned reads', async () => {
  const manifest = supplementManifest();
  const receiptSha = BASELINE.availability.execution.sha256;
  const A = 'admission_discrepancy';
  const cases = [
    ['manifest', (m) => { m.counts.model_targets = '273'; }, A],
    ['manifest', (m) => { m.counts.constructor_jobs = 273.5; }, A],
    ['manifest', (m) => { m.extra = true; }, A],
    ['manifest', (m) => { [m.targets[0], m.targets[1]] = [m.targets[1], m.targets[0]]; }, A],
    ['manifest', (m) => { m.targets[5].target_index += 1; }, A],
    ['manifest', (m) => { m.targets[5].model_ordinal = m.targets[5].target_index; }, A],
    ['manifest', (m) => { m.targets[5].request_index = m.targets[5].target_index; }, A],
    ['manifest', (m) => { m.targets[3].referrers = []; }, A],
    ['manifest', (m) => { m.targets[3].availability_record.wire_bytes += 1; }, A],
    ['manifest', (m) => { m.targets[3].http_path = m.targets[3].http_path.toUpperCase(); }, A],
    ['manifest', (m) => { m.targets[3].body.identity.mtime_ns = Number(m.targets[3].body.identity.mtime_ns); }, 'identity_precision'],
    ['manifest', (m) => { m.targets[3].body.identity.extra = '1'; }, 'identity_precision'],
    ['manifest', (m) => { m.targets[3].body.identity.ino = String(BigInt(m.targets[3].body.identity.ino) + 1n); }, 'identity_changed'],
    ['manifest', (m) => { m.targets[3].body.sha256 = 'f'.repeat(64); }, A],
    ['manifest', (m) => { m.targets[3].job_id = 'model-000004'; }, A],
    ['manifest', (m) => { m.jobs[0].header_version_bytes = '4752534d0104'; }, A],
    ['manifest', (m) => { m.jobs.reverse(); }, A],
    ['manifest', (m) => { m.jobs[0].target_model_ordinals = [0, 1]; }, A],
    ['manifest', (m) => { m.jobs[0].input_bytes = String(m.jobs[0].input_bytes); }, A],
    ['manifest', (m) => { m.root_model_references[10].occurrence_indexes.pop(); }, A],
    ['manifest', (m) => { m.root_model_references[10].root_ordinal = (m.root_model_references[10].root_ordinal + 1) % 4; }, A],
    ['manifest', (m) => { m.root_model_references[10].loader_index += 1; }, A],
    ['manifest', (m) => { m.root_model_references.pop(); }, A],
    ['manifest', (m) => { m.carried_ground_targets.pop(); }, A],
    ['manifest', (m) => { m.carried_ground_targets[0].catalog_target.referrers.pop(); }, A],
    ['manifest', (m) => { m.remaining_gap_root_ordinals = [0]; }, A],
    ['manifest', (m) => { m.prior_first_level_gaps = [{ target_index: 0 }]; }, A],
    ['manifest', (m) => { m.world_gap_ledger_reference.reconciled_by_this_subset = true; }, A],
    ['manifest', (m) => { m.world_gap_ledger_reference.roots = '1296'; }, A],
    ['manifest', (m) => { m.world_gap_ledger_reference.profile.identity.ino = 19645439; }, 'identity_precision'],
    ['manifest', (m) => { m.availability.execution.sha256 = ARTIFACT_AUDIT_EXPECTED.guard_receipt_sha256; }, A],
    ['manifest', (m) => { m.availability.report.identity.dev = '1'; }, 'identity_changed'],
    ['manifest', (m) => { m.roots[0].edges.rsw.parse_status = 'returned'; }, A],
    ['manifest', (m) => { m.limitations.pop(); }, A],
    ['report', (r) => { r.task = 'T06.003.003.005'; }, A],
    ['report', (r) => { r.records_complete = 1; }, A],
    ['report', (r) => { r.acquisition_and_cleanup_valid = 'true'; }, A],
    ['report', (r) => { r.targets[7].request_index += 1; }, A],
    ['report', (r) => { r.targets[7].wire_target = '/data/other'; }, A],
    ['report', (r) => { r.targets[7].stored.error = 'short'; }, A],
    ['report', (r) => { r.targets[7].signature.kind = 'gat'; }, A],
    ['report', (r) => { r.targets[7].http_status = 206; }, A],
    ['report', (r) => { r.targets.pop(); }, A],
    ['report', (r) => { r.totals.wire_bytes = 7575328; }, A],
    ['report', (r) => { r.catalog_pin.sha256 = receiptSha; }, A],
    ['report', (r) => { r.catalog_refs.referrers = 336; }, A],
    ['catalog', (c) => { c.task = 'T07.007.004'; }, A],
    ['catalog', (c) => { c.targets[26].referrers[0].loader_index += 1; }, A],
    ['catalog', (c) => { c.roots[0].edges.rsw.job_id = 'target-005:rsw'; }, A],
    ['catalog', (c) => { c.jobs[2].occurrence_loader_indexes[0] = 9999; }, A],
    ['catalog', (c) => { c.jobs[2].loader_entries[0].target_index = 27; }, A],
    ['root_audit', (a) => { a.status = 'complete'; }, A],
    ['root_audit', (a) => { a.guard_receipt_sha256 = receiptSha; }, A],
    ['root_audit', (a) => { a.observations.http_404 = false; }, A],
    ['root_audit', (a) => { a.targets = '311'; }, A],
    ['root_audit', (a) => { a.full_game_acceptance = true; }, A],
    ['root_audit', (a) => { a.report_sha256 = BASELINE.availability.catalog.sha256; }, A],
    ['root_audit', (a) => { a.wire_bytes = 7575328; }, A],
    ['execution', (e) => { e.schema = 'root005-two-group-external-guard-1'; }, A],
    ['execution', (e) => { e.root_execution_gate_valid = 1; }, A],
    ['execution', (e) => { e.independent_inputs_equal = 'true'; }, A],
    ['execution', (e) => { e.first_failure = 'x'; }, A],
    ['execution', (e) => { e.later_errors = ['x']; }, A],
    ['execution', (e) => { e.availability_or_full_output_or_game_qualification = true; }, A],
    ['execution', (e) => { e.binding.argv[3] = '/tmp/observe_map_dependencies.py'; }, A],
    ['execution', (e) => { e.binding.driver_pin = [112136, 'a'.repeat(64)]; }, A],
    ['execution', (e) => { e.binding.driver_pin = { bytes: 112136, sha256: e.binding.driver_pin[1] }; }, A],
    ['execution', (e) => { e.binding.metadata_count = '44'; }, A],
    ['execution', (e) => { e.binding.HOME_present = 0; }, A],
    ['execution', (e) => { e.binding.cwd = REPO; }, A],
    ['execution', (e) => { e.binding.child_environment.HOME = '/tmp'; }, A],
    ['execution', (e) => { e.guard_result.schema = 'root005-independent-actual-audit-1'; }, A],
    ['execution', (e) => { e.guard_result.external_guard_valid = 'true'; }, A],
    ['execution', (e) => { e.guard_result.driver_exit = '0'; }, A],
    ['execution', (e) => { e.guard_result.driver_exit = 1; }, A],
    ['execution', (e) => { e.guard_result.guard_action = 'kill'; }, A],
    ['execution', (e) => { delete e.guard_result.native; }, A],
    ['execution', (e) => { e.guard_result.groups_after[Object.keys(e.guard_result.groups_after)[0]] = [1]; }, A],
    ['execution', (e) => { e.guard_result.groups_after = {}; }, A],
    ['execution', (e) => { e.guard_result.work_seconds = 1801; }, A],
    ['execution', (e) => { e.guard_result.rss_limit_bytes = 2147483647; }, A],
    ['execution', (e) => { e.guard_result.cleanup_grace_seconds = 6; }, A],
    ['execution', (e) => { e.guard_result.driver_pin = [112136, e.guard_result.driver_pin.sha256]; }, A],
    ['execution', (e) => { e.guard_result.driver_pin.identity = e.guard_result.driver_pin.identity.map(String); }, A],
    ['execution', (e) => { e.guard_result.driver_pin.identity = e.guard_result.driver_pin.identity.slice(0, 4); }, A],
    ['execution', (e) => { e.guard_result.driver_pin.identity[0] = 1.5; }, A],
    ['execution', (e) => { e.guard_result.driver_pin.bytes = 112137; }, A],
    ['world_ledger_profile', (p) => { p.counts.roots = 1295; }, A],
    ['profile', (p) => { p.policy.job_timeout_ms = '20000'; }, 'profile_invalid'],
    ['profile', (p) => { p.policy.rss_limit_bytes = true; }, 'profile_invalid'],
    ['profile', (p) => { p.counts.model_targets = 273.5; }, 'profile_invalid'],
    ['profile', (p) => { p.counts.roots = 2 ** 53; }, 'profile_invalid'],
    ['profile', (p) => { delete p.availability.execution; }, 'profile_invalid'],
    ['profile', (p) => { p.worker.sha256 = 'a'.repeat(64); }, 'pin_mismatch'],
    ['profile', (p) => { p.manifest.sha256 = 'a'.repeat(64); }, 'pin_mismatch']
  ];
  assert.ok(manifest.targets[3].body.identity.ino);
  for (const [role, mutate, reason] of cases) {
    const output = freshOut();
    const result = await withPinnedJson({ [role]: mutate }, supplementArgs(output, '--max-jobs', '0'));
    assert.equal(result.code, 2, `${role} ${mutate}: ${JSON.stringify(result.summary)}`);
    assert.equal(result.summary.reason, reason, `${role} ${mutate}`);
    assert.ok(result.seen.includes(role), `${role} hook activated`);
    assert.equal(fs.existsSync(output), false);
  }
  // A coherent header change in both report and manifest still disagrees with the body bytes.
  const output = freshOut();
  const result = await withPinnedJson({
    report: (r) => { r.targets[26].signature.prefix_hex = '4752534d0104'; },
    manifest: (m) => { m.targets[0].availability_record.signature.prefix_hex = '4752534d0104'; }
  }, supplementArgs(output, '--max-jobs', '0'));
  assert.equal(result.code, 2);
  assert.equal(result.summary.reason, A);
});

serial('T07 lower-only limits keep the unattempted suffix and still full-hash it', async () => {
  let r = await mainCapture(supplementArgs(freshOut(), '--max-jobs', '274'));
  assert.equal(r.summary.reason, 'policy_increase');
  r = await mainCapture(supplementArgs(freshOut(), '--job-timeout-ms', '20001'));
  assert.equal(r.summary.reason, 'policy_increase');
  const output = freshOut();
  r = await mainCapture(supplementArgs(output, '--max-jobs', '2'));
  assert.equal(r.code, 1);
  const got = rows(output);
  const manifest = supplementManifest();
  assert.deepEqual(got.map((row) => row.job_id), manifest.jobs.map((job) => job.job_id));
  for (const row of got.slice(0, 2)) {
    assert.equal(row.outcome, 'returned');
    assert.deepEqual(row.cleanup, { exit_observed: true, exit_code: 0, terminated_by_parent: false, stdout_eof_observed: true, stderr_eof_observed: true });
  }
  assert.ok(got.slice(2).every((row) => row.outcome === 'unattempted' && row.reason === 'max_jobs'));
  const rep = reportOf(output);
  assert.deepEqual(rep.postchecks, { checked: 273, ok: true });
  assert.equal(rep.qualified, false);
  assert.equal(rep.functional.returned_constructors, 2);
  assert.equal(rep.functional.open_failures.length, 271);
  assert.equal(rep.counts.target_outcomes.unattempted, 271);
});

serial('T07 worker nonzero, timeout and lost exits stay visible and halt on unknown cleanup', async () => {
  const output = freshOut();
  const state = { started: 0, terminated: 0 };
  hooks.createWorker = supplementFakeWorkers(['nonzero', 'clean', 'silent', 'lost'], state);
  let result;
  try { result = await mainCapture(supplementArgs(output, '--job-timeout-ms', '300')); }
  finally { hooks.createWorker = null; }
  assert.equal(result.code, 1);
  assert.equal(state.started, 4);
  const got = rows(output);
  assert.equal(got.length, 273);
  assert.equal(got[0].outcome, 'worker_error');
  assert.equal(got[0].reason, 'nonzero_exit_after_result');
  assert.deepEqual(got[0].prior_result, { outcome: 'returned', constructor_returned: true });
  assert.equal('summary' in got[0], false);
  assert.equal(got[1].outcome, 'returned');
  assert.deepEqual(got[1].summary, { authored: true });
  assert.equal(got[2].outcome, 'timeout');
  assert.deepEqual(got[2].cleanup, { exit_observed: true, exit_code: 1, terminated_by_parent: true, stdout_eof_observed: true, stderr_eof_observed: true });
  assert.equal(got[3].outcome, 'timeout');
  assert.equal(got[3].cleanup.exit_observed, false);
  assert.ok(got.slice(4).every((row) => row.outcome === 'unattempted' && row.reason === 'cleanup_unverified'));
  const rep = reportOf(output);
  assert.equal(rep.qualified, false);
  assert.equal(rep.cleanup.verified, false);
  assert.deepEqual(rep.cleanup.unverified, [got[3].job_id]);
  assert.equal(rep.functional.all_model_constructors_returned, false);
  assert.deepEqual(rep.functional.open_failures.slice(0, 3).map((item) => item.outcome), ['worker_error', 'timeout', 'timeout']);
  assert.equal(rep.functional.open_failures.length, 272);
});

serial('T07 storage failures keep every job id and never qualify', async () => {
  const output = freshOut();
  const state = { started: 0, terminated: 0 };
  const real = { open: fs.openSync, write: fs.writeSync, rename: fs.renameSync };
  let jobsFd = null;
  let jobsWrites = 0;
  let renames = 0;
  fs.openSync = (target, ...args) => {
    const fd = real.open(target, ...args);
    if (typeof target === 'string' && path.resolve(target) === path.join(output, 'jobs.jsonl')) jobsFd = fd;
    return fd;
  };
  fs.writeSync = (fd, ...args) => {
    if (fd === jobsFd && ++jobsWrites === 2) throw Object.assign(new Error('authored EIO'), { code: 'EIO' });
    return real.write(fd, ...args);
  };
  fs.renameSync = (from, to) => {
    if (path.resolve(String(to)) === path.join(output, 'report.json') && ++renames === 1) throw Object.assign(new Error('authored EIO'), { code: 'EIO' });
    return real.rename(from, to);
  };
  hooks.createWorker = supplementFakeWorkers([], state);
  let result;
  try { result = await mainCapture(supplementArgs(output)); }
  finally { fs.openSync = real.open; fs.writeSync = real.write; fs.renameSync = real.rename; hooks.createWorker = null; }
  assert.equal(result.code, 1);
  assert.equal(state.started, 2);
  const got = rows(output);
  assert.equal(got.length, 273);
  assert.equal(got[0].outcome, 'returned');
  assert.equal(got[1].outcome, 'environment_failure');
  assert.deepEqual(got[1].prior_result, { outcome: 'returned', constructor_returned: true });
  assert.ok(got.slice(2).every((row) => row.outcome === 'unattempted' && row.reason === 'output_io_error'));
  const rep = reportOf(output);
  assert.equal(rep.qualified, false);
  assert.equal(rep.storage.publication_failed, true);
  assert.equal(rep.functional.all_model_constructors_returned, false);
  assert.equal(rep.job_accounting.length, 273);
});

serial('T07 worker pin before creation, body reread and final preservation drift stay visible', async () => {
  const before = fs.readFileSync(WORKER);
  let output = freshOut();
  hooks.beforeRepresentativeReread = (item) => { if (item.job_id === 'model-000001') fs.writeFileSync(WORKER, before); };
  let result;
  try { result = await mainCapture(supplementArgs(output, '--max-jobs', '3')); }
  finally { hooks.beforeRepresentativeReread = null; fs.writeFileSync(WORKER, before); }
  assert.equal(result.code, 1);
  let got = rows(output);
  assert.equal(got[0].outcome, 'returned');
  assert.equal(got[1].outcome, 'environment_failure');
  assert.equal(got[1].reason, 'worker_pin');
  assert.equal(got[1].worker_started, false);
  assert.ok(got.slice(2).every((row) => row.outcome === 'unattempted' && row.reason === 'source_drift'));
  let rep = reportOf(output);
  assert.equal(rep.pinned_inputs_identity_unchanged_after_run, false);
  assert.ok(rep.source_postchecks.failed.some((item) => item.role === 'worker'));

  output = freshOut();
  hooks.beforeRepresentativeReread = (item) => {
    if (item.job_id === 'model-000000' || item.model_ordinal === 272) throw new Refusal('identity_changed', 'authored drift');
  };
  try { result = await mainCapture(supplementArgs(output, '--max-jobs', '1')); }
  finally { hooks.beforeRepresentativeReread = null; }
  assert.equal(result.code, 1);
  got = rows(output);
  assert.equal(got[0].outcome, 'input_refused');
  assert.equal(got[0].reason, 'identity_changed');
  rep = reportOf(output);
  assert.equal(rep.postchecks.ok, false);
  assert.equal(rep.postchecks.reason, 'identity_changed');
  assert.equal(rep.qualified, false);

  output = freshOut();
  hooks.beforeIdentityRecheck = () => fs.writeFileSync(WORKER, before);
  try { result = await mainCapture(supplementArgs(output, '--max-jobs', '1')); }
  finally { hooks.beforeIdentityRecheck = null; fs.writeFileSync(WORKER, before); }
  assert.equal(result.code, 1);
  rep = reportOf(output);
  assert.equal(rows(output)[0].outcome, 'returned');
  assert.equal(rep.pinned_inputs_identity_unchanged_after_run, false);
  assert.ok(rep.source_postchecks.failed.some((item) => item.role === 'worker'));
  assert.equal(rep.functional.all_model_constructors_returned, false);
});

serial('T07 actual 273-job CLI preserves every typed row, target, reference and carried record', () => {
  const r = cli([], { prof: NEW_PROFILE, mode: ['--manifest', MANIFEST] });
  assert.equal(r.code, 0, JSON.stringify(r.summary));
  const manifest = supplementManifest();
  const got = rows(r.output);
  assert.equal(got.length, 273);
  got.forEach((row, index) => {
    const job = manifest.jobs[index];
    assert.equal(row.job_id, job.job_id);
    assert.equal(row.complete_sha256, job.complete_sha256);
    assert.equal(row.input_bytes, job.input_bytes);
    assert.equal(row.header_version_bytes, job.header_version_bytes);
    assert.equal(row.outcome === 'returned' || row.outcome === 'constructor_exception', true, job.job_id);
    assert.equal(row.constructor_returned, row.outcome === 'returned');
    if (row.outcome === 'returned') assert.equal(typeof row.summary, 'object');
    else assert.equal(row.exception.phase, 'constructor');
    assert.deepEqual(row.cleanup, { exit_observed: true, exit_code: 0, terminated_by_parent: false, stdout_eof_observed: true, stderr_eof_observed: true });
    assert.deepEqual(row.seek_globals, [1, 2, 3]);
    assert.deepEqual(row.dynamic_import_refusals, []);
    assert.equal(row.loaded_module_keys.length, 7);
  });
  const rep = reportOf(r.output);
  assert.equal(rep.task, 'T07.007.008');
  assert.equal(rep.qualified, true);
  assert.equal(rep.cleanup.verified, true);
  assert.equal(rep.cleanup.workers_started, 273);
  assert.deepEqual(rep.postchecks, { checked: 273, ok: true });
  assert.equal(rep.source_postchecks.ok, true);
  assert.deepEqual(rep.roots, manifest.roots);
  assert.deepEqual(rep.root_model_references, manifest.root_model_references);
  assert.deepEqual(rep.carried_ground_targets, manifest.carried_ground_targets);
  assert.deepEqual(rep.world_gap_ledger_reference, manifest.world_gap_ledger_reference);
  const outcome = new Map(got.map((row) => [row.job_id, row.outcome]));
  assert.deepEqual(rep.targets, manifest.targets.map((target) => ({ ...target, constructor_outcome: outcome.get(target.job_id) })));
  const returned = got.filter((row) => row.outcome === 'returned').length;
  assert.equal(rep.functional.returned_constructors, returned);
  assert.equal(rep.functional.all_model_constructors_returned, returned === 273);
  const jobsBuf = fs.readFileSync(path.join(r.output, 'jobs.jsonl'));
  assert.equal(rep.jobs_file.sha256, sha256Of(jobsBuf));
  assert.equal(rep.jobs_file.complete, true);
  assert.deepEqual(fs.readdirSync(r.output).sort(), ['jobs.jsonl', 'report.json']);
  for (const name of fs.readdirSync(r.output)) assert.equal(fs.statSync(path.join(r.output, name)).mode & 0o777, 0o600);
});

serial('repair semantic policy and summary equality after genuine pinned admission', async () => {
  for (const group of ['policy', 'summary_limits']) {
    for (const key of Object.keys(newProfile[group])) {
      for (const value of [newProfile[group][key] + 1, newProfile[group][key] - 1, String(newProfile[group][key])]) {
        const output = freshOut();
        const r = await withPinnedJson({ profile(p) { p[group][key] = value; } }, supplementFixtureArgs(output));
        assert.deepEqual(r.seen, ['profile']);
        assert.equal(r.code, 2, `${group}.${key}=${value}`);
        assert.equal(r.summary.reason, 'profile_invalid');
        assert.equal(fs.existsSync(output), false);
      }
    }
    for (const mutate of [(p) => { delete p[group][Object.keys(p[group])[0]]; }, (p) => { p[group].extra = 1; }]) {
      const r = await withPinnedJson({ profile: mutate }, supplementFixtureArgs(freshOut()));
      assert.equal(r.code, 2);
      assert.equal(r.summary.reason, 'profile_invalid');
    }
  }
  const reordered = structuredClone(newProfile);
  reordered.policy = Object.fromEntries(Object.entries(reordered.policy).reverse());
  assert.equal(validateProfile(reordered, ROUTES[SUPPLEMENT_PROFILE_SHA256]), reordered);
});

// Actual owned Worker with authored result/module/SEEK/summary values: this
// tests parent lifecycle only, never Model correctness. Both underlying stream
// EOF events and actual thread exit are independently recorded before forwarding.
function repairRealFactory(state, { hidden = null, delay = 0, exitDelay = 0, code = 0, outcome = 'returned', hold = false } = {}) {
  return (_url, options) => {
    const packet = outcome === 'constructor_exception'
      ? rootPacket(authored.cases.find((entry) => entry.expected_outcome === outcome)) : supplementPacket();
    const real = new Worker(`const { parentPort, workerData } = require('node:worker_threads');
      process.stdout.write('real stdout'); process.stderr.write('real stderr');
      parentPort.postMessage({ type: 'phase', phase: 'constructor' });
      parentPort.postMessage(workerData.packet);
      process.exitCode = workerData.code;
      if (workerData.hold) setInterval(() => {}, 1000);`,
    { ...options, eval: true, transferList: [], workerData: { packet, code, hold } });
    const forwarded = new EventEmitter();
    forwarded.stdout = new EventEmitter(); forwarded.stderr = new EventEmitter();
    forwarded.stdout.resume = forwarded.stderr.resume = () => {};
    for (const channel of ['stdout', 'stderr']) {
      real[channel].on('data', (bytes) => forwarded[channel].emit('data', bytes));
      real[channel].on('end', () => {
        state[channel] = true;
        if (hidden === channel) return;
        const deliver = () => { state[`${channel}ForwardedAt`] = performance.now(); forwarded[channel].emit('end'); };
        if (delay && channel === 'stderr') setTimeout(deliver, delay); else deliver();
      });
    }
    real.on('message', (msg) => forwarded.emit('message', msg));
    real.on('error', (err) => forwarded.emit('error', err));
    real.on('exit', (value) => {
      state.realExit = value; state.realExitAt = performance.now();
      const deliver = () => { state.exitForwardedAt = performance.now(); forwarded.emit('exit', value); };
      if (hidden === 'exit') return;
      if (exitDelay) setTimeout(deliver, exitDelay); else deliver();
    });
    forwarded.terminate = () => { state.terminated++; return real.terminate(); };
    return forwarded;
  };
}
async function repairRealRow(options = {}, policyOverrides = {}, runMs = 3000) {
  const state = { terminated: 0 };
  const row = await runWorkerJob({ id: 'real-lifecycle', job_id: 'real-lifecycle', kind: 'model', input_bytes: 2,
    complete_sha256: 'a'.repeat(64), header_version_bytes: '0001' }, Buffer.from([0, 1]), {
    policy: { ...profile.policy, job_timeout_ms: 1500, cleanup_wait_ms: 250, ...policyOverrides },
    sources: {}, summaryText: '', runDeadline: performance.now() + runMs,
    rss: { active: null, sample() {} }, observeEof: true, workerFactory: repairRealFactory(state, options)
  });
  state.settledAt = performance.now();
  assert.equal(state.stdout, true); assert.equal(state.stderr, true);
  assert.ok(Number.isInteger(state.realExit));
  return { row, state };
}

serial('repair real normal, delayed EOF and EOF-before-exit obey observation ordering', async () => {
  for (const outcome of ['returned', 'constructor_exception']) {
    for (const opts of [{}, { delay: 100 }, { exitDelay: 100 }]) {
      const { row, state } = await repairRealRow({ ...opts, outcome });
      assert.equal(row.outcome, outcome);
      assert.equal(state.terminated, 0);
      assert.ok(state.settledAt >= state.stderrForwardedAt);
      assert.ok(state.settledAt >= state.stdoutForwardedAt);
      assert.ok(state.settledAt >= state.exitForwardedAt);
      if (opts.delay) assert.ok(state.stderrForwardedAt > state.realExitAt);
      if (opts.exitDelay) assert.ok(state.exitForwardedAt > state.stderrForwardedAt);
      assert.deepEqual(row.cleanup, { exit_observed: true, exit_code: 0, terminated_by_parent: false,
        stdout_eof_observed: true, stderr_eof_observed: true });
    }
  }
});

serial('repair real missing EOF settles bounded after exit without terminating exited worker', async () => {
  for (const hidden of ['stdout', 'stderr']) {
    const { row, state } = await repairRealRow({ hidden });
    assert.equal(state.terminated, 0);
    assert.equal(row.outcome, 'worker_error');
    assert.equal(row.reason, 'stream_eof_unobserved');
    assert.equal(row.constructor_returned, true);
    assert.deepEqual(row.prior_result, { outcome: 'returned', constructor_returned: true });
    assert.equal(row.cleanup[`${hidden}_eof_observed`], false);
    assert.equal(row.cleanup.exit_observed, true);
    assert.ok(state.settledAt - state.realExitAt >= 240);
    assert.ok(state.settledAt - state.realExitAt < 1500);
    assert.equal(row._summary_json, null);
  }
});

serial('repair delayed EOF cannot evade job or command deadline at final completion', async () => {
  for (const outcome of ['returned', 'constructor_exception']) {
    for (const command of [false, true]) {
      const { row, state } = await repairRealRow({ delay: 220, outcome },
        { job_timeout_ms: command ? 1500 : 180, cleanup_wait_ms: 500 }, command ? 180 : 3000);
      assert.equal(row.outcome, 'timeout');
      assert.equal(row.reason, command ? 'run_deadline' : 'job_timeout');
      assert.equal(state.terminated, 0);
      assert.equal(row.cleanup.stderr_eof_observed, true);
      assert.deepEqual(row.prior_result, { outcome, constructor_returned: outcome === 'returned' });
      assert.ok(state.settledAt >= state.stderrForwardedAt);
    }
  }
});

serial('repair real nonzero and unknown exit preserve original facts through missing cleanup', async () => {
  const nonzero = await repairRealRow({ code: 7, hidden: 'stderr', outcome: 'constructor_exception' });
  assert.equal(nonzero.row.reason, 'nonzero_exit_after_result');
  assert.equal(nonzero.row.exception.phase, 'constructor');
  assert.equal(nonzero.row.constructor_returned, false);
  assert.equal(nonzero.row.prior_result.outcome, 'constructor_exception');
  assert.equal(nonzero.row.cleanup.stderr_eof_observed, false);
  const unknown = await repairRealRow({ hidden: 'exit', hold: true }, { result_exit_grace_ms: 100 });
  assert.equal(unknown.row.outcome, 'worker_error');
  assert.equal(unknown.row.reason, 'terminated_after_result');
  assert.equal(unknown.row.cleanup.exit_observed, false);
  assert.equal(unknown.state.terminated, 1);
  assert.equal(unknown.row.constructor_returned, true);
});

serial('repair EOF failure halts new-route suffix and survives publication failure', async () => {
  for (const storageFault of [false, true]) {
    const output = freshOut(); const state = { terminated: 0 }; let starts = 0;
    const factory = repairRealFactory(state, { hidden: 'stderr', code: 7 });
    hooks.createWorker = (...args) => { starts++; return factory(...args); };
    const realOpen = fs.openSync; const realWrite = fs.writeSync; let jobsFd;
    fs.openSync = (file, ...args) => { const fd = realOpen(file, ...args); if (file === path.join(output, 'jobs.jsonl')) jobsFd = fd; return fd; };
    let faulted = false;
    fs.writeSync = (fd, ...args) => {
      if (storageFault && fd === jobsFd && !faulted) { faulted = true; throw rootEio(); }
      return realWrite(fd, ...args);
    };
    let r;
    try { r = await mainCapture(supplementFixtureArgs(output, '--job-timeout-ms', '300')); }
    finally { hooks.createWorker = null; fs.openSync = realOpen; fs.writeSync = realWrite; }
    assert.equal(r.code, 1);
    assert.equal(starts, 1);
    const got = rows(output); const report = reportOf(output);
    assert.equal(got.length, 13);
    assert.equal(got[0].reason, 'nonzero_exit_after_result');
    assert.equal(got[0].outcome, 'worker_error');
    assert.equal(got[0].prior_result.outcome, 'returned');
    assert.equal(got[0].constructor_returned, true);
    assert.equal(got[0].cleanup.stderr_eof_observed, false);
    if (storageFault) { assert.equal(faulted, true); assert.equal(got[0].publication_failure.reason, 'output_io_error'); }
    assert.ok(got.slice(1).every((row) => row.outcome === 'unattempted' && !Object.hasOwn(row.cleanup, 'stdout_eof_observed')));
    assert.equal(report.cleanup.verified, false);
    assert.equal(report.qualified, false);
    assert.deepEqual(report.cleanup.unverified, [got[0].id]);
  }
});

serial('repair primary exception, decoder tail and cleanup bound survive later events', async () => {
  for (const kind of ['close', 'error', 'terminate-throw', 'late-eof', 'unknown-code', 'late-exit']) {
    const entry = authored.cases.find((item) => item.expected_outcome === 'constructor_exception');
    const packet = rootPacket(entry); let terminations = 0; let exitedAt;
    const workerFactory = () => {
      const worker = new EventEmitter();
      worker.stdout = new EventEmitter(); worker.stderr = new EventEmitter();
      worker.stdout.resume = worker.stderr.resume = () => {};
      worker.terminate = () => {
        terminations++;
        if (kind === 'terminate-throw') throw new Error('later termination failure');
        return Promise.resolve(1);
      };
      setImmediate(() => {
        worker.emit('message', packet);
        worker.stderr.emit('data', Buffer.from([0xe2, 0x82]));
        worker.stdout.emit('end');
        if (kind === 'error' || kind === 'terminate-throw') worker.emit('error', new Error('later worker error'));
        if (kind === 'close') worker.stderr.emit('close');
        if (kind === 'late-exit') {
          const until = performance.now() + 80;
          while (performance.now() < until) { /* delayed result grace timer */ }
        }
        exitedAt = performance.now();
        worker.emit('exit', kind === 'unknown-code' ? undefined : 0);
        if (kind === 'late-eof') {
          // An overdue cleanup timer must not lose to a delayed end event.
          const until = performance.now() + 90;
          while (performance.now() < until) { /* finite authored stall */ }
          worker.stderr.emit('end');
        } else if (kind === 'unknown-code' || kind === 'late-exit') worker.stderr.emit('end');
        else {
          // Repeated close/error notifications must not restart cleanup.
          setTimeout(() => worker.stderr.emit('close'), 20);
          setTimeout(() => worker.emit('error', new Error('still later error')), 30);
        }
      });
      return worker;
    };
    const row = await runWorkerJob({ id: kind, job_id: kind, kind: 'model', input_bytes: 2,
      complete_sha256: 'a'.repeat(64), header_version_bytes: '0001' }, Buffer.from([0, 1]), {
      policy: { ...profile.policy, job_timeout_ms: 1000, cleanup_wait_ms: 60, result_exit_grace_ms: kind === 'late-exit' ? 40 : 500 },
      sources: {}, summaryText: '', runDeadline: performance.now() + 3000,
      rss: { active: null, sample() {} }, observeEof: true, workerFactory
    });
    assert.equal(row.outcome, 'worker_error', kind);
    assert.equal(row.constructor_returned, false);
    assert.deepEqual(row.prior_result, { outcome: 'constructor_exception', constructor_returned: false });
    assert.deepEqual(row.exception, packet.exception);
    assert.equal(row._log, '\ufffd', 'incomplete UTF8 flushed once, including duplicate events');
    assert.equal(row._summary_json, null);
    assert.ok(performance.now() - exitedAt < 400, 'cleanup bound never resets');
    if (kind === 'close') assert.equal(row.reason, 'stream_closed_without_eof');
    if (kind === 'error' || kind === 'terminate-throw') assert.equal(row.reason, 'worker_error');
    if (kind === 'late-eof') assert.equal(row.reason, 'stream_eof_unobserved');
    if (kind === 'unknown-code') { assert.equal(row.reason, 'nonzero_exit_after_result'); assert.equal(row.cleanup.exit_code, null); }
    if (kind === 'late-exit') { assert.equal(row.reason, 'result_exit_grace'); assert.equal(terminations, 0); }
  }
});

serial('repair compact failure keeps EOF, original result, publication and log-loss facts', () => {
  const row = { ...unattemptedRow(fixtureJobs(authored, profile.policy)[0], 'nonzero_exit_after_result'),
    outcome: 'worker_error', constructor_returned: false, worker_started: true,
    cleanup: { exit_observed: true, exit_code: 7, terminated_by_parent: false, stdout_eof_observed: true, stderr_eof_observed: false },
    prior_result: { outcome: 'constructor_exception', constructor_returned: false },
    publication_failure: { outcome: 'environment_failure', reason: 'output_io_error' },
    exception: { phase: 'constructor', name: 'Error', message: 'large'.repeat(400) },
    loaded_module_keys: Array(1000).fill('stand-in'), _log: 'lost log', _log_dropped_entries: 2, _stdio_dropped_utf8_bytes: 3 };
  const got = boundedRow(row, { ...profile.policy, max_job_json_bytes: 1024 }, 0);
  assert.ok(Buffer.byteLength(got.line) <= 1024);
  assert.equal('loaded_module_keys' in got.row, false, 'exercise compact fallback');
  assert.deepEqual(got.row.cleanup, row.cleanup);
  assert.deepEqual(got.row.prior_result, row.prior_result);
  assert.deepEqual(got.row.publication_failure, row.publication_failure);
  assert.equal(got.row.reason, row.reason);
  assert.equal(got.row.exception.phase, 'constructor');
  assert.equal(got.row.log_dropped_entries, 2);
  assert.equal(got.row.stdio_dropped_utf8_bytes, 3);
  assert.equal(got.row.log_dropped_utf8_bytes, 8);
});
