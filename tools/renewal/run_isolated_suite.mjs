#!/usr/bin/env node
// T00.006 self-isolating runner for checked-in mutation suites.
//
// A registered suite never runs in a source checkout. The runner copies the
// suite's whole mutable source/fixture closure into a fresh private tree as
// ordinary files (new inodes, no hardlinks or symlinks), runs the unchanged test
// there in its own process group, and snapshots every protected canonical path
// (content SHA-256 plus type/dev/ino/size/mode/nlink/mtime_ns/ctime_ns) before
// and after. SIGINT/SIGTERM/SIGHUP stop the owned process group and every
// observed descendant, then the after-snapshot still runs.
//
//   node tools/renewal/run_isolated_suite.mjs --list
//   node tools/renewal/run_isolated_suite.mjs --suite model-constructors \
//     --corpus /abs/canonical/read-only/checkout [--work-root DIR] [--grace-ms N]
//
// Private inputs are used only when --corpus names them explicitly; a missing
// selection or missing pinned input refuses (exit 2) before any copy or run.
// Exit codes: 0 suite passed and canonical preserved; 1 suite failed; 2 refused;
// 3 canonical identity/content changed; 4 descendant cleanup failed;
// 128+signal when interrupted with cleanup and preservation intact.
import { spawn, spawnSync } from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const CHECKOUT = path.resolve(HERE, '..', '..');
const SIGNAL_CODES = { SIGHUP: 129, SIGINT: 130, SIGTERM: 143 };
const MAX_HASH_BYTES = 64 * 1024 * 1024;

export class Refusal extends Error {
  constructor(reason, detail) { super(`${reason}: ${detail}`); this.reason = reason; this.detail = detail; }
}

const sha256 = (buffer) => crypto.createHash('sha256').update(buffer).digest('hex');
const readJson = (abs) => JSON.parse(fs.readFileSync(abs, 'utf8'));

// ---------------------------------------------------------------------------
// Registered suites. `sources` is the complete copied closure, relative to the
// source checkout. `corpus(root)` lists private read-only inputs relative to the
// explicit corpus; `required` ones must exist before anything runs.
const MODEL_SOURCES = [
  'tools/renewal/probe_model_constructors.mjs',
  'tools/renewal/test_probe_model_constructors.mjs',
  'tools/renewal/model_constructor_worker.mjs',
  'tools/renewal/model_constructor_summary.mjs',
  'tools/renewal/MODEL_CONSTRUCTOR_PROBE.md',
  'docs/project/fixtures/T06.003.003.006-profile.json',
  'docs/project/fixtures/T06.003.003.006-authored.json',
  'docs/project/fixtures/T07.007.008-profile.json',
  'docs/project/fixtures/T07.007.008-baseline.json'
];

function modelCorpus(sourceRoot, corpusRoot) {
  const oldProfile = readJson(path.join(sourceRoot, 'docs/project/fixtures/T06.003.003.006-profile.json'));
  const newProfile = readJson(path.join(sourceRoot, 'docs/project/fixtures/T07.007.008-profile.json'));
  const client = newProfile.client_source_relative || '.tools/renewal/client-source';
  const required = new Set();
  const optional = new Set();
  for (const key of Object.keys(newProfile.sources)) required.add(path.posix.join(client, key));
  for (const key of Object.keys(newProfile.rule_sources)) required.add(path.posix.join(client, key));
  required.add(newProfile.manifest.path);
  for (const pin of Object.values(newProfile.availability)) required.add(pin.path);
  // The supplement manifest names the 273 retained bodies the suite admits.
  const manifestAbs = path.join(corpusRoot, newProfile.manifest.path);
  if (fs.existsSync(manifestAbs)) {
    const manifest = readJson(manifestAbs);
    for (const target of manifest.targets || []) if (target.body && target.body.path) required.add(target.body.path);
    const ledger = manifest.world_gap_ledger_reference && manifest.world_gap_ledger_reference.profile;
    if (ledger && ledger.path) required.add(ledger.path);
  }
  // Historical world-route inputs are only referenced by refusal controls.
  optional.add(oldProfile.manifest.path);
  for (const pin of Object.values(oldProfile.availability)) optional.add(pin.path);
  // A direct run inside the corpus checkout would rewrite these same paths.
  for (const rel of MODEL_SOURCES) required.add(rel);
  for (const rel of required) optional.delete(rel);
  return { required: [...required].sort(), optional: [...optional].sort() };
}

// Report (never repair) manifest-pinned corpus identities that already differ
// from the live files; the suite's own admission still decides the outcome.
function modelCorpusDrift(sourceRoot, corpusRoot) {
  const newProfile = readJson(path.join(sourceRoot, 'docs/project/fixtures/T07.007.008-profile.json'));
  const manifest = readJson(path.join(corpusRoot, newProfile.manifest.path));
  const drift = [];
  let checked = 0;
  const visit = (value) => {
    if (Array.isArray(value)) { value.forEach(visit); return; }
    if (!value || typeof value !== 'object') return;
    if (typeof value.path === 'string' && value.identity && typeof value.identity === 'object' && !Array.isArray(value.identity)) {
      checked++;
      const live = statIdentity(path.join(corpusRoot, value.path), { hash: false });
      const fields = ['dev', 'ino', 'size', 'mtime_ns', 'ctime_ns'].filter((key) => String(value.identity[key]) !== live[key]);
      if (fields.length) drift.push({ path: value.path, fields });
    }
    for (const child of Object.values(value)) visit(child);
  };
  visit(manifest);
  return { checked, drift };
}

function modelPins(treeRoot) {
  // Fail on drift instead of weakening admission: the copied closure must match
  // the frozen profile and baseline pins exactly before the suite starts.
  const baseline = readJson(path.join(treeRoot, 'docs/project/fixtures/T07.007.008-baseline.json'));
  const newProfile = readJson(path.join(treeRoot, 'docs/project/fixtures/T07.007.008-profile.json'));
  const pins = [
    { path: newProfile.worker.path, bytes: newProfile.worker.bytes, sha256: newProfile.worker.sha256 },
    { path: newProfile.summary.path, bytes: newProfile.summary.bytes, sha256: newProfile.summary.sha256 },
    { path: baseline.profile.path, bytes: baseline.profile.bytes, sha256: baseline.profile.sha256 },
    ...baseline.baseline_sources.filter((pin) => !pin.path.startsWith('.tools/') &&
      !pin.path.startsWith('tools/renewal/probe_') && !pin.path.startsWith('tools/renewal/test_'))
  ];
  return pins;
}

export const SUITES = Object.freeze({
  'model-constructors': Object.freeze({
    description: 'tools/renewal/test_probe_model_constructors.mjs (T06.003.003.006 + T07.007.008); rewrites its sibling worker',
    privateInput: 'explicit --corpus: canonical read-only checkout holding .tools/renewal client-source and T07.007.008 inputs',
    sources: MODEL_SOURCES,
    entry: 'tools/renewal/test_probe_model_constructors.mjs',
    nodeArgs: ['--experimental-vm-modules', '--no-warnings', '--test'],
    env: (corpus) => ({ T06_INPUT_ROOT: corpus }),
    corpus: modelCorpus,
    pins: modelPins,
    corpusDrift: modelCorpusDrift,
    witness: 'tools/renewal/model_constructor_worker.mjs'
  })
});

// Authored definitions (used by the public focused checks) take the same shape
// from a JSON file; they may not name a corpus.
function loadDefinition(file) {
  const raw = readJson(file);
  const keys = ['name', 'source_root', 'sources', 'entry', 'node_args', 'env', 'witness'];
  for (const key of Object.keys(raw)) if (!keys.includes(key)) throw new Refusal('usage', `definition key ${key}`);
  if (!Array.isArray(raw.sources) || !raw.sources.includes(raw.entry)) throw new Refusal('usage', 'definition entry must be in sources');
  return {
    name: String(raw.name), description: 'authored definition', sourceRoot: path.resolve(path.dirname(file), raw.source_root),
    sources: raw.sources, entry: raw.entry, nodeArgs: raw.node_args || ['--test'], env: () => ({ ...(raw.env || {}) }),
    corpus: null, pins: null, corpusDrift: null, witness: raw.witness || null
  };
}

// ---------------------------------------------------------------------------
// Identity snapshots.
function assertRealPath(abs, label) {
  let real;
  try { real = fs.realpathSync.native(abs); } catch (error) { throw new Refusal('private_input_missing', `${label} (${error.code})`); }
  if (real !== abs) throw new Refusal('symlink_refused', label);
}

export function statIdentity(abs, { hash = true } = {}) {
  let st;
  try { st = fs.lstatSync(abs, { bigint: true }); } catch (error) {
    if (error.code === 'ENOENT') return { absent: true };
    throw error;
  }
  const type = st.isFile() ? 'file' : st.isDirectory() ? 'dir' : st.isSymbolicLink() ? 'symlink' : 'other';
  const identity = {
    type, dev: String(st.dev), ino: String(st.ino), size: String(st.size), mode: (Number(st.mode) & 0o7777).toString(8),
    nlink: String(st.nlink), mtime_ns: String(st.mtimeNs), ctime_ns: String(st.ctimeNs)
  };
  if (hash && type === 'file') {
    if (st.size > BigInt(MAX_HASH_BYTES)) throw new Refusal('input_too_large', abs);
    const fd = fs.openSync(abs, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW);
    try { identity.sha256 = sha256(fs.readFileSync(fd)); } finally { fs.closeSync(fd); }
  }
  return identity;
}

const IDENTITY_KEYS = ['absent', 'type', 'dev', 'ino', 'size', 'mode', 'nlink', 'mtime_ns', 'ctime_ns', 'sha256'];

export function snapshot(entries) {
  // entries: [{ label, abs }]. Parent directories are recorded too (without
  // hashing), so a created/renamed sibling in a protected directory is visible.
  const out = {};
  const dirs = new Set();
  for (const { label, abs } of entries) {
    out[label] = statIdentity(abs);
    dirs.add(path.dirname(abs));
  }
  for (const dir of [...dirs].sort()) out[`dir:${dir}`] = statIdentity(dir, { hash: false });
  return out;
}

export function compareSnapshots(before, after) {
  const changed = [];
  for (const key of new Set([...Object.keys(before), ...Object.keys(after)])) {
    const a = before[key] || { absent: true };
    const b = after[key] || { absent: true };
    const fields = IDENTITY_KEYS.filter((field) => a[field] !== b[field]);
    if (fields.length) changed.push({ key, fields });
  }
  return changed;
}

// ---------------------------------------------------------------------------
// Ordinary private copies.
function copyOrdinary(srcAbs, destAbs) {
  const sfd = fs.openSync(srcAbs, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW);
  let body;
  let sst;
  try {
    sst = fs.fstatSync(sfd, { bigint: true });
    if (!sst.isFile()) throw new Refusal('special_file_refused', srcAbs);
    body = fs.readFileSync(sfd);
  } finally { fs.closeSync(sfd); }
  fs.mkdirSync(path.dirname(destAbs), { recursive: true, mode: 0o700 });
  const dfd = fs.openSync(destAbs, fs.constants.O_WRONLY | fs.constants.O_CREAT | fs.constants.O_EXCL | fs.constants.O_NOFOLLOW, 0o600);
  try {
    let offset = 0;
    while (offset < body.length) offset += fs.writeSync(dfd, body, offset, body.length - offset);
    fs.fsyncSync(dfd);
  } finally { fs.closeSync(dfd); }
  const dst = fs.lstatSync(destAbs, { bigint: true });
  return { body, sst, dst };
}

export function makePrivateTree(definition, sourceRoot, treeRoot, protectedInodes) {
  const copies = [];
  for (const rel of definition.sources) {
    if (path.isAbsolute(rel) || rel.split('/').includes('..')) throw new Refusal('usage', `source ${rel}`);
    const srcAbs = path.join(sourceRoot, rel);
    assertRealPath(srcAbs, `source ${rel}`);
    const destAbs = path.join(treeRoot, rel);
    const { body, sst, dst } = copyOrdinary(srcAbs, destAbs);
    const copySha = sha256(fs.readFileSync(destAbs));
    const record = {
      path: rel, bytes: body.length, sha256: sha256(body), source_ino: String(sst.ino), copy_ino: String(dst.ino),
      copy_dev: String(dst.dev), copy_type: dst.isFile() && !dst.isSymbolicLink() ? 'file' : 'other', copy_nlink: String(dst.nlink),
      copy_mode: (Number(dst.mode) & 0o7777).toString(8)
    };
    record.ordinary_private_copy = record.copy_type === 'file' && dst.nlink === 1n && copySha === record.sha256 &&
      !(dst.dev === sst.dev && dst.ino === sst.ino) && !protectedInodes.has(`${dst.dev}:${dst.ino}`);
    if (!record.ordinary_private_copy) throw new Refusal('copy_not_isolated', rel);
    copies.push(record);
  }
  return copies;
}

// ---------------------------------------------------------------------------
// Process tracking: every 100 ms the full process table is read and every
// descendant of the suite (by parent chain) or member of its group is kept,
// keyed by pid and start time so a reused pid is never mistaken for it.
function processTable() {
  const r = spawnSync('/bin/ps', ['-A', '-o', 'pid=,ppid=,pgid=,lstart='], { encoding: 'utf8', timeout: 5000 });
  if (r.status !== 0) return null;
  const rows = [];
  for (const line of r.stdout.split('\n')) {
    const m = line.trim().match(/^(\d+)\s+(\d+)\s+(\d+)\s+(.+)$/);
    if (m) rows.push({ pid: Number(m[1]), ppid: Number(m[2]), pgid: Number(m[3]), start: m[4].trim() });
  }
  return rows;
}

export class Tracker {
  constructor(rootPid, pgid) { this.rootPid = rootPid; this.pgid = pgid; this.seen = new Map(); this.polls = 0; }
  poll() {
    const table = processTable();
    if (!table) return null;
    this.polls++;
    const children = new Map();
    for (const row of table) {
      if (!children.has(row.ppid)) children.set(row.ppid, []);
      children.get(row.ppid).push(row);
    }
    const live = new Map();
    const stack = table.filter((row) => row.pid === this.rootPid || row.pgid === this.pgid);
    // Previously seen processes keep their own descendants in scope after
    // a middle process exits and they are reparented.
    for (const row of table) if (this.seen.has(row.pid) && this.seen.get(row.pid).start === row.start) stack.push(row);
    while (stack.length) {
      const row = stack.pop();
      if (live.has(row.pid)) continue;
      live.set(row.pid, row);
      for (const child of children.get(row.pid) || []) stack.push(child);
    }
    for (const row of live.values()) if (!this.seen.has(row.pid)) this.seen.set(row.pid, row);
    return [...live.values()];
  }
  alive() {
    const table = processTable();
    if (!table) return null;
    const out = [];
    for (const row of table) {
      const seen = this.seen.get(row.pid);
      if ((seen && seen.start === row.start) || row.pgid === this.pgid) out.push(row);
    }
    return out;
  }
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function signalAll(tracker, signal) {
  try { process.kill(-tracker.pgid, signal); } catch (error) { if (error.code !== 'ESRCH') throw error; }
  for (const row of tracker.alive() || []) {
    try { process.kill(row.pid, signal); } catch (error) { if (error.code !== 'ESRCH') throw error; }
  }
}

async function waitGone(tracker, ms) {
  const deadline = Date.now() + ms;
  for (;;) {
    tracker.poll();
    const alive = tracker.alive();
    if (alive && alive.length === 0) return [];
    if (Date.now() >= deadline) return alive || [{ pid: -1, start: 'process table unavailable' }];
    await sleep(50);
  }
}

export async function stopOwned(tracker, graceMs) {
  const actions = [];
  let alive = await waitGone(tracker, 0);
  if (alive.length) {
    actions.push({ signal: 'SIGTERM', targets: alive.length });
    signalAll(tracker, 'SIGTERM');
    alive = await waitGone(tracker, graceMs);
  }
  if (alive.length) {
    actions.push({ signal: 'SIGKILL', targets: alive.length });
    signalAll(tracker, 'SIGKILL');
    alive = await waitGone(tracker, 3000);
  }
  return { actions, leaked: alive.map((row) => ({ pid: row.pid, pgid: row.pgid })) };
}

// ---------------------------------------------------------------------------
function parseArgs(argv) {
  const opts = { graceMs: 5000, exclude: [] };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    const value = () => { if (i + 1 >= argv.length) throw new Refusal('usage', `${arg} needs a value`); return argv[++i]; };
    if (arg === '--list') opts.list = true;
    else if (arg === '--suite') opts.suite = value();
    else if (arg === '--definition') opts.definition = path.resolve(value());
    else if (arg === '--corpus') opts.corpus = value();
    else if (arg === '--work-root') opts.workRoot = path.resolve(value());
    else if (arg === '--exclude-test') opts.exclude.push(value());
    else if (arg === '--grace-ms') {
      opts.graceMs = Number(value());
      if (!Number.isSafeInteger(opts.graceMs) || opts.graceMs < 0 || opts.graceMs > 60000) throw new Refusal('usage', '--grace-ms');
    } else if (arg === '--help' || arg === '-h') opts.help = true;
    else throw new Refusal('usage', `unknown argument ${arg}`);
  }
  return opts;
}

const within = (child, parent) => child === parent || child.startsWith(parent + path.sep);

function emit(stdout, value) { stdout.write(`${JSON.stringify(value)}\n`); }

export async function main(argv, { stdout = process.stdout, signals = process } = {}) {
  let opts;
  try { opts = parseArgs(argv); } catch (error) {
    emit(stdout, { status: 'refused', reason: error.reason || 'usage', detail: error.detail || error.message });
    return 2;
  }
  if (opts.help) { stdout.write(fs.readFileSync(fileURLToPath(import.meta.url), 'utf8').split('\nimport ')[0].replace(/^\/\/ ?/gm, '') + '\n'); return 0; }
  if (opts.list) {
    emit(stdout, { suites: Object.entries(SUITES).map(([name, s]) => ({ name, description: s.description, private_input: s.privateInput })) });
    return 0;
  }
  const started = Date.now();
  let definition;
  let sourceRoot;
  let corpus = null;
  let corpusPaths = { required: [], optional: [] };
  try {
    if (Boolean(opts.suite) === Boolean(opts.definition)) throw new Refusal('usage', 'select exactly one of --suite or --definition');
    if (opts.suite) {
      if (!Object.hasOwn(SUITES, opts.suite)) throw new Refusal('usage', `unknown suite ${opts.suite}`);
      definition = { name: opts.suite, ...SUITES[opts.suite] };
      sourceRoot = CHECKOUT;
      if (!opts.corpus) throw new Refusal('private_input_required', `suite ${opts.suite} needs explicit --corpus (${definition.privateInput})`);
      if (!path.isAbsolute(opts.corpus)) throw new Refusal('usage', '--corpus must be absolute');
      corpus = path.resolve(opts.corpus);
      assertRealPath(corpus, 'corpus');
      if (!fs.statSync(corpus).isDirectory()) throw new Refusal('private_input_missing', 'corpus is not a directory');
      corpusPaths = definition.corpus(sourceRoot, corpus);
      const missing = corpusPaths.required.filter((rel) => {
        try { const st = fs.lstatSync(path.join(corpus, rel)); return !st.isFile(); } catch { return true; }
      });
      if (missing.length) throw new Refusal('private_input_missing', `${missing.length} required corpus file(s), first ${missing[0]}`);
    } else {
      if (opts.corpus) throw new Refusal('usage', 'authored definitions take no --corpus');
      definition = loadDefinition(opts.definition);
      sourceRoot = definition.sourceRoot;
    }
  } catch (error) {
    if (!(error instanceof Refusal)) throw error;
    emit(stdout, { status: 'refused', reason: error.reason, detail: error.detail });
    return 2;
  }

  const workRoot = opts.workRoot || path.join(CHECKOUT, '.tools', 'renewal', 'isolated-runs');
  // Decide on the real location before creating anything, so a refused work
  // root never adds a directory inside a protected tree.
  let existing = workRoot;
  while (!fs.existsSync(existing)) existing = path.dirname(existing);
  const workReal = path.join(fs.realpathSync.native(existing), path.relative(existing, workRoot));
  if (corpus && within(workReal, corpus)) { emit(stdout, { status: 'refused', reason: 'path_refused', detail: 'work root inside corpus' }); return 2; }
  if (within(workReal, sourceRoot) && !within(workReal, path.join(sourceRoot, '.tools'))) {
    emit(stdout, { status: 'refused', reason: 'path_refused', detail: 'work root must be outside the source tree or under its ignored .tools' });
    return 2;
  }
  fs.mkdirSync(workReal, { recursive: true, mode: 0o700 });
  if (fs.realpathSync.native(workReal) !== workReal) { emit(stdout, { status: 'refused', reason: 'symlink_refused', detail: 'work root' }); return 2; }
  const runDir = fs.mkdtempSync(path.join(workReal, `${definition.name}-`));
  fs.chmodSync(runDir, 0o700);
  const treeRoot = path.join(runDir, 'tree');
  const tmpDir = path.join(runDir, 'tmp');
  fs.mkdirSync(treeRoot, { mode: 0o700 });
  fs.mkdirSync(tmpDir, { mode: 0o700 });
  const eventsFile = path.join(runDir, 'events.jsonl');
  const event = (value) => fs.appendFileSync(eventsFile, `${JSON.stringify({ t_ms: Date.now() - started, ...value })}\n`, { mode: 0o600 });
  const relRun = path.relative(CHECKOUT, runDir);
  const result = { schema: 'T00.006-isolated-run-1', suite: definition.name, run_dir: within(runDir, CHECKOUT) ? relRun : '<work-root>/' + path.basename(runDir) };

  // Protected canonical set: the source closure plus, when selected, the corpus.
  const protectedEntries = [];
  const protectedSeen = new Set();
  const protect = (label, abs) => { if (!protectedSeen.has(abs)) { protectedSeen.add(abs); protectedEntries.push({ label, abs }); } };
  for (const rel of definition.sources) protect(`source:${rel}`, path.join(sourceRoot, rel));
  if (corpus) {
    for (const rel of corpusPaths.required) protect(`corpus:${rel}`, path.join(corpus, rel));
    for (const rel of corpusPaths.optional) protect(`corpus-optional:${rel}`, path.join(corpus, rel));
  }
  const before = snapshot(protectedEntries);
  const protectedInodes = new Set(Object.values(before).filter((v) => !v.absent).map((v) => `${v.dev}:${v.ino}`));
  result.protected = { entries: Object.keys(before).length, files: protectedEntries.length,
    corpus_required: corpusPaths.required.length, corpus_optional_present: corpusPaths.optional.filter((rel) => fs.existsSync(path.join(corpus, rel))).length };
  fs.writeFileSync(path.join(runDir, 'before.json'), JSON.stringify(before, null, 1), { mode: 0o600 });

  let copies;
  try {
    copies = makePrivateTree(definition, sourceRoot, treeRoot, protectedInodes);
    if (definition.pins) {
      const drift = definition.pins(treeRoot).filter((pin) => {
        const body = fs.readFileSync(path.join(treeRoot, pin.path));
        return body.length !== pin.bytes || sha256(body) !== pin.sha256;
      });
      if (drift.length) throw new Refusal('pin_drift', drift.map((pin) => pin.path).join(','));
    }
  } catch (error) {
    if (!(error instanceof Refusal)) throw error;
    result.status = 'refused'; result.reason = error.reason; result.detail = error.detail;
    result.preservation = { changed: compareSnapshots(before, snapshot(protectedEntries)) };
    fs.writeFileSync(path.join(runDir, 'result.json'), JSON.stringify(result, null, 1), { mode: 0o600 });
    emit(stdout, result);
    return result.preservation.changed.length ? 3 : 2;
  }
  result.copies = { count: copies.length, all_ordinary_private: copies.every((c) => c.ordinary_private_copy) };
  if (corpus && definition.corpusDrift) result.corpus_identity_preflight = definition.corpusDrift(sourceRoot, corpus);
  result.excluded_tests = opts.exclude;
  fs.writeFileSync(path.join(runDir, 'copies.json'), JSON.stringify(copies, null, 1), { mode: 0o600 });
  const witnessAbs = definition.witness ? path.join(treeRoot, definition.witness) : null;
  const witnessBefore = witnessAbs ? statIdentity(witnessAbs, { hash: false }) : null;

  const env = {
    PATH: '/usr/bin:/bin:/usr/sbin:/sbin', TMPDIR: tmpDir, LANG: 'C', NO_COLOR: '1',
    ...definition.env(corpus)
  };
  const log = fs.openSync(path.join(runDir, 'suite.log'), 'wx', 0o600);
  // Exclusions are exact test names, passed to node:test as anchored skip
  // patterns; any exclusion makes a pass a labeled subset, never a full pass.
  const skipArgs = opts.exclude.map((name) => `--test-skip-pattern=^${name.replace(/[.*+?^${}()|[\]\\/]/g, '\\$&')}$`);
  const child = spawn(process.execPath, [...definition.nodeArgs, ...skipArgs, path.join(treeRoot, definition.entry)], {
    cwd: treeRoot, env, detached: true, stdio: ['ignore', log, log]
  });
  fs.closeSync(log);
  const tracker = new Tracker(child.pid, child.pid);
  event({ event: 'started', pid: child.pid, pgid: child.pid });

  let interrupted = null;
  let exit = null;
  const exited = new Promise((resolve) => child.on('exit', (code, signal) => { exit = { code, signal }; resolve(); }));
  const onSignal = (name) => { if (!interrupted) { interrupted = name; event({ event: 'signal', name }); } };
  const handlers = Object.keys(SIGNAL_CODES).map((name) => [name, () => onSignal(name)]);
  for (const [name, fn] of handlers) signals.on(name, fn);
  let mutationObserved = false;
  try {
    while (!exit && !interrupted) {
      tracker.poll();
      if (witnessAbs && !mutationObserved) {
        const now = statIdentity(witnessAbs, { hash: false });
        if (now.ctime_ns !== witnessBefore.ctime_ns || now.ino !== witnessBefore.ino) { mutationObserved = true; event({ event: 'mutation_observed', path: definition.witness }); }
      }
      await Promise.race([exited, sleep(100)]);
    }
    const cleanup = await stopOwned(tracker, interrupted ? opts.graceMs : Math.min(opts.graceMs, 2000));
    await Promise.race([exited, sleep(1000)]);
    if (witnessAbs && !mutationObserved) {
      const now = statIdentity(witnessAbs, { hash: false });
      mutationObserved = now.ctime_ns !== witnessBefore.ctime_ns || now.ino !== witnessBefore.ino;
    }
    result.cleanup = { ...cleanup, descendants_observed: tracker.seen.size, polls: tracker.polls };
  } finally {
    for (const [name, fn] of handlers) signals.removeListener(name, fn);
  }
  const after = snapshot(protectedEntries);
  fs.writeFileSync(path.join(runDir, 'after.json'), JSON.stringify(after, null, 1), { mode: 0o600 });
  const changed = compareSnapshots(before, after);
  result.suite_exit = exit;
  result.interrupted = interrupted;
  result.mutation_observed_in_copy = witnessAbs ? mutationObserved : null;
  result.preservation = { compared: Object.keys(before).length, changed };
  result.elapsed_ms = Date.now() - started;
  result.tap = summarizeTap(path.join(runDir, 'suite.log'));
  let code;
  if (changed.length) { result.status = 'canonical_changed'; code = 3; }
  else if (result.cleanup.leaked.length) { result.status = 'cleanup_failed'; code = 4; }
  else if (interrupted) { result.status = 'interrupted'; code = SIGNAL_CODES[interrupted]; }
  else if (exit && exit.code === 0) { result.status = opts.exclude.length ? 'passed_subset' : 'passed'; code = 0; }
  else { result.status = 'suite_failed'; code = 1; }
  event({ event: 'finished', status: result.status, code });
  fs.writeFileSync(path.join(runDir, 'result.json'), JSON.stringify(result, null, 1), { mode: 0o600 });
  emit(stdout, { status: result.status, suite: result.suite, run_dir: result.run_dir, suite_exit: exit, interrupted,
    mutation_observed_in_copy: result.mutation_observed_in_copy, copies: result.copies, preservation_changed: changed.length,
    protected_entries: result.preservation.compared, leaked: result.cleanup.leaked.length, signals_sent: result.cleanup.actions,
    tap: result.tap, excluded_tests: opts.exclude.length,
    corpus_identity_drift: result.corpus_identity_preflight ? result.corpus_identity_preflight.drift.length : null, elapsed_ms: result.elapsed_ms });
  return code;
}

function summarizeTap(file) {
  const text = fs.readFileSync(file, 'utf8');
  const out = {};
  for (const key of ['tests', 'suites', 'pass', 'fail', 'cancelled', 'skipped', 'todo']) {
    const m = text.match(new RegExp(`^(?:#|\u2139) ${key} (\\d+)$`, 'm'));
    out[key] = m ? Number(m[1]) : null;
  }
  return out;
}

const invokedDirectly = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (invokedDirectly) {
  process.umask(0o077);
  main(process.argv.slice(2)).then((code) => { process.exitCode = code; }, (error) => {
    process.stdout.write(`${JSON.stringify({ status: 'runner_error', detail: String(error && error.message) })}\n`);
    process.exitCode = 1;
  });
}
