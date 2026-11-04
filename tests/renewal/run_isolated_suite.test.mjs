// T00.006 focused checks for tools/renewal/run_isolated_suite.mjs.
//
// Public part (no assets): an authored synthetic "mutation suite" rewrites its
// sibling file with identical bytes, starts descendants (one ignores SIGTERM,
// one escapes into its own process group) and then passes, fails or hangs.
//   node --test tests/renewal/run_isolated_suite.test.mjs
// Private part runs only when T00_006_CORPUS explicitly names the canonical
// read-only corpus; it interrupts the real model-constructor suite with SIGINT
// and SIGTERM after the runner observes the copied worker being rewritten.
//   T00_006_CORPUS=/abs/canonical node --test tests/renewal/run_isolated_suite.test.mjs
// All temporary state lives under this checkout's ignored .tools/renewal.
import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { EventEmitter } from 'node:events';
import { compareSnapshots, hooks, main, snapshot } from '../../tools/renewal/run_isolated_suite.mjs';

process.umask(0o077);
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const RUNNER = path.join(REPO, 'tools/renewal/run_isolated_suite.mjs');
const PRIVATE = path.join(REPO, '.tools', 'renewal', 't00-006-runner-checks');
fs.mkdirSync(PRIVATE, { recursive: true, mode: 0o700 });
const TMP = fs.mkdtempSync(path.join(fs.realpathSync(PRIVATE), 'run-'));
const CORPUS = process.env.T00_006_CORPUS || null;
let seq = 0;

const SUITE = `import test from 'node:test';
import fs from 'node:fs';
import { spawn } from 'node:child_process';
const worker = new URL('./lib/worker.txt', import.meta.url);
test('rewrites its sibling with identical bytes', async () => {
  const before = fs.readFileSync(worker);
  fs.writeFileSync(worker, before);
  const mode = process.env.SYN_MODE;
  if (mode === 'fail') throw new Error('authored failure');
  if (mode === 'hang' || mode === 'leak') {
    const stubborn = spawn(process.execPath, ['-e', "process.on('SIGTERM',()=>{});setInterval(()=>{},1000)"], { stdio: 'ignore' });
    const escaped = spawn(process.execPath, ['-e', 'setInterval(()=>{},1000)'], { stdio: 'ignore', detached: true });
    escaped.unref(); stubborn.unref();
    await new Promise((resolve) => setTimeout(resolve, 300));
    fs.writeFileSync(new URL('./lib/ready.json', import.meta.url), JSON.stringify({ pids: [process.pid, stubborn.pid, escaped.pid] }));
    if (mode === 'hang') await new Promise(() => {});
  }
});
`;

function fixture(mode) {
  const root = path.join(TMP, `src-${++seq}`);
  fs.mkdirSync(path.join(root, 'lib'), { recursive: true, mode: 0o700 });
  fs.writeFileSync(path.join(root, 'suite.test.mjs'), SUITE, { mode: 0o600 });
  fs.writeFileSync(path.join(root, 'lib/worker.txt'), 'pinned worker bytes\n', { mode: 0o600 });
  const def = path.join(TMP, `def-${seq}.json`);
  fs.writeFileSync(def, JSON.stringify({
    name: `syn-${mode}`, source_root: path.relative(TMP, root), sources: ['suite.test.mjs', 'lib/worker.txt'],
    entry: 'suite.test.mjs', node_args: ['--test'], env: { SYN_MODE: mode }, witness: 'lib/worker.txt'
  }));
  const entries = ['suite.test.mjs', 'lib/worker.txt'].map((rel) => ({ label: rel, abs: path.join(root, rel) }));
  return { root, def, entries, work: path.join(TMP, `work-${seq}`) };
}

const runSync = (args) => {
  const r = spawnSync(process.execPath, [RUNNER, ...args], { encoding: 'utf8', timeout: 120000 });
  const lines = r.stdout.trim().split('\n').filter(Boolean);
  return { code: r.status, out: JSON.parse(lines.at(-1)), stderr: r.stderr };
};
const runDirOf = (out) => path.join(REPO, out.run_dir);
const readResult = (out) => JSON.parse(fs.readFileSync(path.join(runDirOf(out), 'result.json'), 'utf8'));
const alive = (pid) => { try { process.kill(pid, 0); return true; } catch (error) { return error.code === 'EPERM'; } };
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function runAndSignal(args, work, ready, signal, timeoutMs = 120000) {
  const child = spawn(process.execPath, [RUNNER, ...args], { stdio: ['ignore', 'pipe', 'pipe'] });
  let stdout = '';
  child.stdout.on('data', (chunk) => { stdout += chunk; });
  const exited = new Promise((resolve) => child.on('exit', (code, sig) => resolve({ code, sig })));
  const deadline = Date.now() + timeoutMs;
  let readyInfo = null;
  try {
    while (!readyInfo) {
      assert.ok(Date.now() < deadline, 'ready condition not reached');
      readyInfo = ready();
      if (!readyInfo) await sleep(50);
    }
  } finally { child.kill(signal); }
  const status = await exited;
  return { ...status, out: JSON.parse(stdout.trim().split('\n').at(-1)), readyInfo };
}

const findRun = (work) => {
  if (!fs.existsSync(work)) return null;
  const dirs = fs.readdirSync(work);
  return dirs.length === 1 ? path.join(work, dirs[0]) : null;
};

test('list and help are public and read no assets', () => {
  const r = runSync(['--list']);
  assert.equal(r.code, 0);
  assert.deepEqual(r.out.suites.map((s) => s.name), ['model-constructors']);
  const h = spawnSync(process.execPath, [RUNNER, '--help'], { encoding: 'utf8' });
  assert.equal(h.status, 0);
  assert.match(h.stdout, /--corpus/);
});

test('private suite refuses without an explicit, present corpus and creates no run state', () => {
  const work = path.join(TMP, 'never-created');
  let r = runSync(['--suite', 'model-constructors', '--work-root', work]);
  assert.deepEqual([r.code, r.out.status, r.out.reason], [2, 'refused', 'private_input_required']);
  r = runSync(['--suite', 'model-constructors', '--corpus', path.join(TMP, 'absent'), '--work-root', work]);
  assert.deepEqual([r.code, r.out.reason], [2, 'private_input_missing']);
  r = runSync(['--suite', 'model-constructors', '--corpus', 'relative/corpus', '--work-root', work]);
  assert.deepEqual([r.code, r.out.reason], [2, 'usage']);
  const empty = fs.mkdtempSync(path.join(TMP, 'empty-'));
  r = runSync(['--suite', 'model-constructors', '--corpus', empty, '--work-root', work]);
  assert.deepEqual([r.code, r.out.reason], [2, 'private_input_missing']);
  const link = path.join(TMP, `corpus-link-${++seq}`);
  fs.symlinkSync(empty, link);
  r = runSync(['--suite', 'model-constructors', '--corpus', link, '--work-root', work]);
  assert.deepEqual([r.code, r.out.reason], [2, 'symlink_refused']);
  r = runSync(['--suite', 'nope']);
  assert.deepEqual([r.code, r.out.reason], [2, 'usage']);
  assert.equal(fs.existsSync(work), false);
});

test('control: a direct in-place rewrite with identical bytes changes ctime and is detected', () => {
  const f = fixture('ok');
  const before = snapshot(f.entries);
  const worker = path.join(f.root, 'lib/worker.txt');
  fs.writeFileSync(worker, fs.readFileSync(worker));
  const changed = compareSnapshots(before, snapshot(f.entries));
  assert.equal(changed.length, 1);
  assert.equal(changed[0].key, 'lib/worker.txt');
  assert.ok(changed[0].fields.includes('ctime_ns'));
  assert.equal(changed[0].fields.includes('sha256'), false);
});

test('success mutates only ordinary private copies and preserves canonical identities', () => {
  const f = fixture('ok');
  const before = snapshot(f.entries);
  const r = runSync(['--definition', f.def, '--work-root', f.work]);
  assert.equal(r.code, 0, JSON.stringify(r.out));
  assert.equal(r.out.status, 'passed');
  assert.equal(r.out.mutation_observed_in_copy, true);
  assert.equal(r.out.preservation_changed, 0);
  assert.deepEqual(compareSnapshots(before, snapshot(f.entries)), []);
  const copies = JSON.parse(fs.readFileSync(path.join(runDirOf(r.out), 'copies.json'), 'utf8'));
  assert.equal(copies.length, 2);
  for (const c of copies) {
    const copyAbs = path.join(runDirOf(r.out), 'tree', c.path);
    const st = fs.lstatSync(copyAbs, { bigint: true });
    const src = fs.lstatSync(path.join(f.root, c.path), { bigint: true });
    assert.ok(st.isFile() && !st.isSymbolicLink());
    assert.equal(st.nlink, 1n);
    assert.notEqual(st.ino, src.ino);
    assert.equal(c.ordinary_private_copy, true);
  }
  const copyWorker = fs.lstatSync(path.join(runDirOf(r.out), 'tree/lib/worker.txt'), { bigint: true });
  const srcWorker = fs.lstatSync(path.join(f.root, 'lib/worker.txt'), { bigint: true });
  assert.ok(copyWorker.ctimeNs > srcWorker.ctimeNs, 'copy was rewritten after the canonical was last changed');
  assert.equal(r.out.tap.pass, 1);
});

test('a hardlinked source is still copied to a separate single-link inode', () => {
  const f = fixture('ok');
  fs.linkSync(path.join(f.root, 'lib/worker.txt'), path.join(f.root, 'lib/worker-alias.txt'));
  const r = runSync(['--definition', f.def, '--work-root', f.work]);
  assert.equal(r.code, 0, JSON.stringify(r.out));
  const copies = JSON.parse(fs.readFileSync(path.join(runDirOf(r.out), 'copies.json'), 'utf8'));
  const w = copies.find((c) => c.path === 'lib/worker.txt');
  assert.equal(w.copy_nlink, '1');
  assert.notEqual(w.copy_ino, w.source_ino);
  assert.equal(fs.lstatSync(path.join(f.root, 'lib/worker.txt')).nlink, 2);
});

test('a symlinked source and a work root inside the source tree are refused', () => {
  let f = fixture('ok');
  const worker = path.join(f.root, 'lib/worker.txt');
  fs.renameSync(worker, path.join(f.root, 'lib/real.txt'));
  fs.symlinkSync('real.txt', worker);
  let r = runSync(['--definition', f.def, '--work-root', f.work]);
  assert.deepEqual([r.code, r.out.status, r.out.reason], [2, 'refused', 'symlink_refused']);
  f = fixture('ok');
  r = runSync(['--definition', f.def, '--work-root', path.join(f.root, 'lib', 'runs')]);
  assert.deepEqual([r.code, r.out.reason], [2, 'path_refused']);
});

test('a failing suite exits 1 and still preserves canonical identities', () => {
  const f = fixture('fail');
  const before = snapshot(f.entries);
  const r = runSync(['--definition', f.def, '--work-root', f.work]);
  assert.deepEqual([r.code, r.out.status], [1, 'suite_failed']);
  assert.equal(r.out.mutation_observed_in_copy, true);
  assert.deepEqual(compareSnapshots(before, snapshot(f.entries)), []);
});

test('descendants left after a passing suite are stopped, including an escaped group', () => {
  const f = fixture('leak');
  const r = runSync(['--definition', f.def, '--work-root', f.work, '--grace-ms', '500']);
  assert.equal(r.code, 0, JSON.stringify(r.out));
  const ready = JSON.parse(fs.readFileSync(path.join(runDirOf(r.out), 'tree/lib/ready.json'), 'utf8'));
  for (const pid of ready.pids) assert.equal(alive(pid), false, `pid ${pid} still alive`);
  assert.equal(r.out.leaked, 0);
  assert.ok(r.out.signals_sent.some((a) => a.signal === 'SIGKILL'), JSON.stringify(r.out.signals_sent));
});

for (const [signal, code] of [['SIGINT', 130], ['SIGTERM', 143]]) {
  test(`${signal} after mutation stops every owned descendant and preserves canonical identities`, async () => {
    const f = fixture('hang');
    const before = snapshot(f.entries);
    const r = await runAndSignal(['--definition', f.def, '--work-root', f.work, '--grace-ms', '500'], f.work, () => {
      const run = findRun(f.work);
      if (!run) return null;
      const readyFile = path.join(run, 'tree/lib/ready.json');
      const events = path.join(run, 'events.jsonl');
      if (!fs.existsSync(readyFile) || !fs.existsSync(events) || !fs.readFileSync(events, 'utf8').includes('mutation_observed')) return null;
      try { return JSON.parse(fs.readFileSync(readyFile, 'utf8')); } catch { return null; }
    }, signal);
    assert.equal(r.code, code, JSON.stringify(r.out));
    assert.equal(r.out.status, 'interrupted');
    assert.equal(r.out.interrupted, signal);
    assert.equal(r.out.mutation_observed_in_copy, true);
    assert.equal(r.out.leaked, 0);
    assert.equal(r.out.preservation_changed, 0);
    assert.deepEqual(r.out.signals_sent.map((a) => a.signal), ['SIGTERM', 'SIGKILL']);
    for (const pid of r.readyInfo.pids) assert.equal(alive(pid), false, `pid ${pid} still alive`);
    assert.deepEqual(compareSnapshots(before, snapshot(f.entries)), []);
    assert.ok(readResult(r.out).cleanup.descendants_observed >= 4);
  });
}

// Post-spawn failures: faults are injected through the runner's in-process
// hooks (never set by the CLI) while the suite runs; the outer lifecycle
// finally must still stop every owned descendant and run the after-snapshot.
const groupMembers = (pgid) => {
  const r = spawnSync('/bin/ps', ['-A', '-o', 'pid=,pgid='], { encoding: 'utf8' });
  return r.stdout.split('\n').map((line) => line.trim().split(/\s+/).map(Number)).filter(([, g]) => g === pgid).map(([p]) => p);
};
async function inProcess(f, extra = []) {
  let text = '';
  const signals = new EventEmitter();
  const code = await main(['--definition', f.def, '--work-root', f.work, '--grace-ms', '500', ...extra],
    { stdout: { write: (chunk) => { text += chunk; } }, signals });
  return { code, out: JSON.parse(text.trim().split('\n').at(-1)), signals };
}
const eio = (what) => Object.assign(new Error(`injected EIO writing ${what}`), { code: 'EIO' });

test('post-spawn: an evidence-write failure on the started event still kills the suite group and preserves canonical', async () => {
  const f = fixture('hang');
  const before = snapshot(f.entries);
  let pgid = null;
  hooks.beforeEvent = (value) => { if (value.event === 'started') { pgid = value.pgid; throw eio('started'); } };
  let r;
  try { r = await inProcess(f); } finally { hooks.beforeEvent = null; }
  assert.equal(r.code, 5, JSON.stringify(r.out));
  assert.equal(r.out.status, 'runner_error');
  assert.match(r.out.runner_error, /injected EIO writing started/);
  assert.ok(Number.isSafeInteger(pgid));
  await sleep(200);
  assert.equal(alive(pgid), false, 'suite leader still alive');
  assert.deepEqual(groupMembers(pgid), []);
  assert.equal(r.out.leaked, 0);
  assert.equal(r.out.preservation_changed, 0);
  assert.ok(fs.existsSync(path.join(runDirOf(r.out), 'after.json')));
  assert.deepEqual(compareSnapshots(before, snapshot(f.entries)), []);
  assert.equal(readResult(r.out).status, 'runner_error');
});

test('post-spawn: an error inside the poll loop with live stubborn and escaped descendants still cleans up', async () => {
  const f = fixture('hang');
  const before = snapshot(f.entries);
  let ready = null;
  hooks.afterPoll = (tracker, tree) => {
    const file = path.join(tree, 'lib/ready.json');
    if (!fs.existsSync(file)) return;
    try { ready = JSON.parse(fs.readFileSync(file, 'utf8')); } catch { return; }
    throw new Error('injected poll-loop failure');
  };
  let r;
  try { r = await inProcess(f); } finally { hooks.afterPoll = null; }
  assert.equal(r.code, 5, JSON.stringify(r.out));
  assert.equal(r.out.status, 'runner_error');
  assert.ok(ready, 'descendants were live when the fault fired');
  assert.equal(r.out.mutation_observed_in_copy, true);
  assert.deepEqual(r.out.signals_sent.map((a) => a.signal), ['SIGTERM', 'SIGKILL']);
  for (const pid of ready.pids) assert.equal(alive(pid), false, `pid ${pid} still alive`);
  assert.equal(r.out.leaked, 0);
  assert.equal(r.out.preservation_changed, 0);
  assert.deepEqual(compareSnapshots(before, snapshot(f.entries)), []);
});

test('post-spawn: a failed signal-event write neither crashes the runner nor skips cleanup', async () => {
  const f = fixture('hang');
  const before = snapshot(f.entries);
  let ready = null;
  let sent = false;
  hooks.beforeEvent = (value) => { if (value.event === 'signal') throw eio('signal'); };
  hooks.afterPoll = (tracker, tree) => {
    const file = path.join(tree, 'lib/ready.json');
    if (sent || !fs.existsSync(file)) return;
    try { ready = JSON.parse(fs.readFileSync(file, 'utf8')); } catch { return; }
    sent = true;
    setImmediate(() => signalsRef.emit('SIGINT'));
  };
  let signalsRef = null;
  let text = '';
  signalsRef = new EventEmitter();
  let code;
  try {
    code = await main(['--definition', f.def, '--work-root', f.work, '--grace-ms', '500'],
      { stdout: { write: (chunk) => { text += chunk; } }, signals: signalsRef });
  } finally { hooks.beforeEvent = null; hooks.afterPoll = null; }
  const out = JSON.parse(text.trim().split('\n').at(-1));
  assert.equal(code, 130, JSON.stringify(out));
  assert.equal(out.status, 'interrupted');
  assert.ok(out.evidence_errors.some((e) => e.includes('injected EIO writing signal')));
  for (const pid of ready.pids) assert.equal(alive(pid), false, `pid ${pid} still alive`);
  assert.equal(out.leaked, 0);
  assert.equal(out.preservation_changed, 0);
  assert.deepEqual(compareSnapshots(before, snapshot(f.entries)), []);
});

// Evidence publication: a lost finished event, after.json or result.json must
// never leave a passing status or exit 0, while cleanup and the protected
// comparison still run and higher-priority statuses keep their codes.
async function withFault(f, { event: badEvent = null, write: badWrite = null } = {}) {
  hooks.beforeEvent = badEvent ? (value) => { if (value.event === badEvent) throw eio(`${badEvent} event`); } : null;
  hooks.beforeWrite = badWrite ? (name) => { if (name === badWrite) throw eio(badWrite); } : null;
  try { return await inProcess(f); } finally { hooks.beforeEvent = null; hooks.beforeWrite = null; }
}
const eventsOf = (out) => fs.readFileSync(path.join(runDirOf(out), 'events.jsonl'), 'utf8').trim().split('\n').map((l) => JSON.parse(l));

test('evidence: a failed finished-event write turns a passing suite into evidence_failed (exit 6)', async () => {
  const f = fixture('ok');
  const before = snapshot(f.entries);
  const r = await withFault(f, { event: 'finished' });
  assert.equal(r.code, 6, JSON.stringify(r.out));
  assert.equal(r.out.status, 'evidence_failed');
  assert.deepEqual(r.out.suite_exit, { code: 0, signal: null });
  assert.ok(r.out.evidence_errors.some((e) => e.startsWith('finished event:')));
  assert.equal(readResult(r.out).status, 'evidence_failed');
  assert.equal(r.out.leaked, 0);
  assert.equal(r.out.preservation_changed, 0);
  assert.deepEqual(compareSnapshots(before, snapshot(f.entries)), []);
});

test('evidence: a failed after.json write still compares canonical and is evidence_failed (exit 6)', async () => {
  const f = fixture('ok');
  const before = snapshot(f.entries);
  const r = await withFault(f, { write: 'after.json' });
  assert.equal(r.code, 6, JSON.stringify(r.out));
  assert.equal(r.out.status, 'evidence_failed');
  assert.ok(r.out.evidence_errors.some((e) => e.startsWith('after.json:')));
  assert.equal(fs.existsSync(path.join(runDirOf(r.out), 'after.json')), false);
  const result = readResult(r.out);
  assert.equal(result.status, 'evidence_failed');
  assert.ok(result.preservation.compared > 0);
  assert.deepEqual(result.preservation.changed, []);
  assert.equal(eventsOf(r.out).at(-1).code, 6);
  assert.deepEqual(compareSnapshots(before, snapshot(f.entries)), []);
});

test('evidence: an unpublishable result.json still yields a useful nonzero status on stdout and in events', async () => {
  const f = fixture('ok');
  const before = snapshot(f.entries);
  const r = await withFault(f, { write: 'result.json' });
  assert.equal(r.code, 6, JSON.stringify(r.out));
  assert.equal(r.out.status, 'evidence_failed');
  assert.ok(r.out.evidence_errors.some((e) => e.startsWith('result.json:')));
  assert.equal(r.out.preservation_changed, 0);
  assert.equal(r.out.mutation_observed_in_copy, true);
  assert.equal(r.out.leaked, 0);
  assert.equal(fs.existsSync(path.join(runDirOf(r.out), 'result.json')), false);
  const last = eventsOf(r.out).at(-1);
  assert.deepEqual([last.event, last.status, last.code], ['publication_failed', 'evidence_failed', 6]);
  assert.deepEqual(compareSnapshots(before, snapshot(f.entries)), []);
});

test('evidence: lost evidence overrides suite_failed but keeps the suite exit visible', async () => {
  const f = fixture('fail');
  const r = await withFault(f, { event: 'finished', write: 'result.json' });
  assert.equal(r.code, 6, JSON.stringify(r.out));
  assert.equal(r.out.status, 'evidence_failed');
  assert.deepEqual(r.out.suite_exit, { code: 1, signal: null });
  assert.equal(r.out.evidence_errors.length, 2);
});

test('evidence: an interruption keeps its signal code when its evidence is also lost', async () => {
  const f = fixture('hang');
  const signals = new EventEmitter();
  let ready = null;
  let sent = false;
  hooks.beforeEvent = (value) => { if (value.event === 'finished') throw eio('finished event'); };
  hooks.beforeWrite = (name) => { if (name === 'result.json') throw eio('result.json'); };
  hooks.afterPoll = (tracker, tree) => {
    const file = path.join(tree, 'lib/ready.json');
    if (sent || !fs.existsSync(file)) return;
    try { ready = JSON.parse(fs.readFileSync(file, 'utf8')); } catch { return; }
    sent = true;
    setImmediate(() => signals.emit('SIGTERM'));
  };
  let text = '';
  let code;
  try {
    code = await main(['--definition', f.def, '--work-root', f.work, '--grace-ms', '500'],
      { stdout: { write: (chunk) => { text += chunk; } }, signals });
  } finally { hooks.beforeEvent = null; hooks.beforeWrite = null; hooks.afterPoll = null; }
  const out = JSON.parse(text.trim().split('\n').at(-1));
  assert.equal(code, 143, JSON.stringify(out));
  assert.equal(out.status, 'interrupted');
  assert.equal(out.evidence_errors.length, 2);
  for (const pid of ready.pids) assert.equal(alive(pid), false, `pid ${pid} still alive`);
  assert.equal(out.leaked, 0);
});

for (const [signal, code] of [['SIGINT', 130], ['SIGTERM', 143]]) {
  test(`private: ${signal} interrupts the real model suite after its copied worker is rewritten`,
    { skip: CORPUS ? false : 'T00_006_CORPUS not set: private interruption not run' }, async () => {
      const work = path.join(TMP, `model-${signal}-${++seq}`);
      const r = await runAndSignal(['--suite', 'model-constructors', '--corpus', CORPUS, '--work-root', work], work, () => {
        const run = findRun(work);
        if (!run) return null;
        const events = path.join(run, 'events.jsonl');
        return fs.existsSync(events) && fs.readFileSync(events, 'utf8').includes('mutation_observed') ? { run } : null;
      }, signal, 300000);
      assert.equal(r.code, code, JSON.stringify(r.out));
      assert.deepEqual([r.out.status, r.out.interrupted, r.out.mutation_observed_in_copy], ['interrupted', signal, true]);
      assert.equal(r.out.leaked, 0);
      assert.equal(r.out.preservation_changed, 0);
      assert.ok(r.out.protected_entries > 300);
      const result = JSON.parse(fs.readFileSync(path.join(r.readyInfo.run, 'result.json'), 'utf8'));
      assert.ok(result.cleanup.descendants_observed >= 2, JSON.stringify(result.cleanup));
      assert.equal(result.copies.all_ordinary_private, true);
    });
}
