// Tests for T06.003.003.007 nested model-texture declaration catalog.
// Run: node --test tools/renewal/test_catalog_model_textures.mjs
// Corpus CLI tests read only the profile-pinned metadata under CANONICAL_ROOT.
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { buildCatalog, deepEqual, hooks, main, Refusal, PROFILE_PATH } from './catalog_model_textures.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const CHECKOUT = path.resolve(HERE, '..', '..');
const MODULE = path.join(HERE, 'catalog_model_textures.mjs');
const OUT_PARENT = path.join(CHECKOUT, '.tools', 'renewal');
const CANONICAL_ROOT = process.env.CANONICAL_ROOT ||
  path.resolve(CHECKOUT, '..', 'reverse-the-Ragnarok-Online-to-play-by-myself');
const PROFILE = JSON.parse(fs.readFileSync(path.join(CHECKOUT, PROFILE_PATH), 'utf8'));
const AUTHORED = JSON.parse(fs.readFileSync(path.join(CHECKOUT, PROFILE.authored.path), 'utf8'));
const sha256 = (buf) => crypto.createHash('sha256').update(buf).digest('hex');
const RUN = `${process.pid}-${Date.now()}`;
let serial = 0;
const freshOut = (label) => path.join(OUT_PARENT, `test-${RUN}-${label}-${serial++}`);

fs.mkdirSync(OUT_PARENT, { recursive: true, mode: 0o700 });

function refusalOf(fn) {
  try { fn(); } catch (error) { return error; }
  return null;
}

function pointer(p) { return p.split('/').slice(1).map((s) => s.replace(/~1/g, '/').replace(/~0/g, '~')); }

function mutate(input, mutations) {
  const copy = structuredClone(input);
  for (const m of mutations) {
    const keys = pointer(m.path);
    let parent = copy;
    for (const key of keys.slice(0, -1)) parent = parent[key];
    const last = keys.at(-1);
    assert.ok(Object.prototype.hasOwnProperty.call(parent, last), `mutation path exists: ${m.path}`);
    if (m.op === 'set') parent[last] = m.value;
    else if (Array.isArray(parent)) parent.splice(Number(last), 1);
    else delete parent[last];
  }
  return copy;
}

function deepFreeze(v) {
  if (v && typeof v === 'object') { Object.freeze(v); for (const k of Object.keys(v)) deepFreeze(v[k]); }
  return v;
}

function captureMain(argv) {
  let text = '';
  const code = main(argv, { stdout: { write: (s) => { text += s; } } });
  assert.equal(text.split('\n').length, 2, 'exactly one stdout line');
  assert.ok(Buffer.byteLength(text) <= 4096);
  return { code, out: JSON.parse(text), text };
}

function openFds() { return fs.readdirSync('/dev/fd').length; }

// Private test input root containing copies of the small pinned files only.
function makeTestRoot() {
  const base = freshOut('root');
  fs.mkdirSync(base, { mode: 0o700 });
  const files = [PROFILE_PATH, PROFILE.authored.path, PROFILE.constructor_profile.path, PROFILE.summary.path,
    ...Object.keys(PROFILE.rule_sources).map((k) => `${PROFILE.client_source_root}/${k}`)];
  for (const rel of files) {
    const src = rel.startsWith(PROFILE.client_source_root) ? path.join(CANONICAL_ROOT, rel) : path.join(CHECKOUT, rel);
    const dst = path.join(base, rel);
    fs.mkdirSync(path.dirname(dst), { recursive: true, mode: 0o700 });
    fs.copyFileSync(src, dst);
    fs.chmodSync(dst, 0o600);
  }
  return base;
}

const fixtureArgs = (root, output) => ['--input-root', root, '--profile', PROFILE_PATH, '--fixtures', PROFILE.authored.path, '--output', output];
const corpusArgs = (root, output) => ['--input-root', root, '--profile', PROFILE_PATH,
  '--report', PROFILE.inputs.report.path, '--jobs', PROFILE.inputs.jobs.path,
  '--manifest', PROFILE.inputs.manifest.path, '--catalog', PROFILE.inputs.catalog.path, '--output', output];

function resetHooks() { for (const key of Object.keys(hooks)) hooks[key] = null; }

// ------------------------------------------------------------------ core

test('complete literal payload equals expected and caller input is unchanged', () => {
  const input = structuredClone(AUTHORED.input);
  const snapshot = JSON.stringify(input);
  const out = buildCatalog(input);
  assert.ok(deepEqual(out, AUTHORED.expected));
  assert.equal(JSON.stringify(out), JSON.stringify(AUTHORED.expected));
  assert.equal(JSON.stringify(input), snapshot);
  // Frozen caller input also works: no in-place mutation is attempted.
  const frozen = buildCatalog(deepFreeze(structuredClone(AUTHORED.input)));
  assert.ok(deepEqual(frozen, AUTHORED.expected));
  // Output does not alias input objects.
  out.roots[0].name = 'changed';
  assert.equal(input.roots[0].name, 'authored_a');
});

test('opaque own __proto__ metadata survives copying without prototype changes', () => {
  const input = structuredClone(AUTHORED.input);
  const opaque = JSON.parse('{"__proto__":{"retained":7},"constructor":{"marker":"data"},"nested":[{"__proto__":null}]}');
  input.roots[0].opaque = opaque;
  input.model_targets[0].opaque = structuredClone(opaque);
  input.model_rows[2].exception.opaque = structuredClone(opaque);
  const before = JSON.stringify(input);
  const out = buildCatalog(deepFreeze(input));
  const retained = [out.roots[0].opaque, out.model_targets[0].opaque, out.jobs[2].exception.opaque];
  for (const value of retained) {
    assert.deepEqual(value, opaque);
    assert.ok(Object.hasOwn(value, '__proto__'));
    assert.equal(Object.getPrototypeOf(value), Object.prototype);
    assert.equal(Object.getPrototypeOf(value.nested[0]), Object.prototype);
    assert.ok(Object.hasOwn(value.nested[0], '__proto__'));
    assert.equal(JSON.stringify(value), JSON.stringify(opaque));
    assert.notEqual(value, opaque);
    assert.notEqual(value.__proto__, opaque.__proto__);
  }
  out.roots[0].opaque.__proto__.retained = 9;
  assert.equal(input.roots[0].opaque.__proto__.retained, 7);
  assert.equal(JSON.stringify(input), before);
});

test('all ten path-stage cases', () => {
  assert.equal(AUTHORED.stage_cases.length, 10);
  for (const c of AUTHORED.stage_cases) {
    const input = structuredClone(AUTHORED.stage_input);
    input.model_rows[0].summary.textures = [c.raw_name];
    input.model_rows[0].summary.texture_declarations = [c.expected];
    const out = buildCatalog(input);
    assert.deepEqual(out.jobs[0].declarations, [{ ...c.expected, nested_target_index: 0, node_links: [] }], c.id);
    assert.deepEqual(out.nested_targets, [{ index: 0, http_path: c.expected.http_path, referrers: [{ job_index: 0, texture_index: 0 }] }], c.id);
  }
});

test('all twenty actual refusal mutations throw Refusal', () => {
  assert.equal(AUTHORED.refusal_cases.length, 20);
  for (const c of AUTHORED.refusal_cases) {
    const error = refusalOf(() => buildCatalog(mutate(AUTHORED.input, c.mutations)));
    assert.ok(error instanceof Refusal, c.id);
    if (c.expected_reason) assert.equal(error.reason, c.expected_reason, c.id);
    else assert.notEqual(error.reason, 'uri_encoding_unsupported', c.id);
  }
});

test('lone surrogate refuses even when every supplied stage is self-consistent', () => {
  const input = structuredClone(AUTHORED.stage_input);
  input.model_rows[0].summary.textures = ['\ud800'];
  input.model_rows[0].summary.texture_declarations = [{ texture_index: 0, constructor_pointer: '/textures/0', raw_name: '\ud800',
    logical_name: 'data\\texture\\\ud800', filemanager_name: 'data\\texture\\\ud800', http_path: 'data/texture/' }];
  assert.equal(refusalOf(() => buildCatalog(input)).reason, 'uri_encoding_unsupported');
  // A lone surrogate in opaque metadata is ordinary data, not a scalar refusal.
  const opaque = structuredClone(AUTHORED.input);
  opaque.roots[0].name = '\udc00';
  assert.equal(buildCatalog(opaque).roots[0].name, '\udc00');
});

test('bool/null/marker slots stay visible and unresolved; numbers resolve only when in range', () => {
  const out = buildCatalog(structuredClone(AUTHORED.input));
  const node = out.jobs[0].nodes[0];
  assert.deepEqual(node.textures, [0, 2, true, null, { special: 'undefined' }, -1, 1.25, { special: 'NaN' }, 99]);
  assert.deepEqual(node.texture_references.map((r) => r.state),
    ['resolved', 'resolved', 'unresolved', 'unresolved', 'unresolved', 'unresolved', 'unresolved', 'unresolved', 'unresolved']);
  assert.deepEqual(out.jobs[0].declarations[3].node_links, []);
  assert.equal(out.jobs[2].declarations, null);
  assert.equal(out.jobs[2].exception.message, AUTHORED.input.model_rows[2].exception.message);
  // A legitimate unresolved claim on a numeric slot stays admissible; a false resolved claim refuses.
  const wrong = structuredClone(AUTHORED.input);
  wrong.model_rows[0].summary.nodes[0].texture_references[8] = { slot_index: 8, table_index: 99, state: 'resolved' };
  assert.ok(refusalOf(() => buildCatalog(wrong)) instanceof Refusal);
  const falseZero = structuredClone(AUTHORED.input);
  falseZero.model_rows[0].summary.nodes[0].texture_references[0] = { slot_index: 0, table_index: null, state: 'unresolved' };
  assert.ok(refusalOf(() => buildCatalog(falseZero)) instanceof Refusal);
});

test('animation ignores global-position and texture-group counts', () => {
  const input = structuredClone(AUTHORED.input);
  input.model_rows[3].summary.global_position_keys = 5;
  input.model_rows[0].summary.nodes[1].keyframe_counts.texture_groups = 7;
  const out = buildCatalog(input);
  assert.equal(out.jobs[3].animation_by_node_keys, false);
  assert.equal(out.jobs[0].animation_by_node_keys, false);
  const scale = structuredClone(AUTHORED.input);
  scale.model_rows[0].summary.nodes[1].keyframe_counts.scale = 2;
  assert.ok(refusalOf(() => buildCatalog(scale)) instanceof Refusal);
  scale.model_rows[0].summary.animation_by_node_keys = true;
  assert.equal(buildCatalog(scale).counts.animation_jobs.true, 2);
});

test('raw nonfinite, cycles, sparse arrays and non-data values refuse; markers are data', () => {
  const cases = [
    (i) => { i.model_rows[0].summary.numeric_fields.min = NaN; },
    (i) => { i.model_rows[0].summary.nodes[0].textures[6] = Infinity; },
    (i) => { i.model_rows[0].summary.numeric_fields.max = -Infinity; },
    (i) => { i.roots[0].self = i.roots[0]; },
    (i) => { i.prior_first_level_gaps = [1, , 3]; }, // eslint-disable-line no-sparse-arrays
    (i) => { i.roots[0].extra = undefined; },
    (i) => { i.roots[0].fn = () => 1; },
    (i) => { i.roots[0][Symbol('s')] = 1; },
    (i) => { i.roots[0].big = 1n; },
    (i) => { i.roots[0].when = new Date(0); },
    (i) => { Object.defineProperty(i.roots[0], 'getter', { get: () => 1, enumerable: true }); },
    (i) => { let deep = {}; const top = deep; for (let d = 0; d < 70; d++) { deep.x = {}; deep = deep.x; } i.roots[0].deep = top; }
  ];
  for (const [index, change] of cases.entries()) {
    const input = structuredClone(AUTHORED.input);
    change(input);
    assert.ok(refusalOf(() => buildCatalog(input)) instanceof Refusal, `case ${index}`);
  }
  assert.ok(refusalOf(() => buildCatalog(null)) instanceof Refusal);
  assert.ok(refusalOf(() => buildCatalog({ ...structuredClone(AUTHORED.input), extra: 1 })) instanceof Refusal);
});

test('whole-input caps refuse instead of truncating', () => {
  const policy = { ...JSON.parse(JSON.stringify(PROFILE.policy)) };
  for (const [key, value] of [['max_declarations', 6], ['max_nodes', 2], ['max_node_slots', 10], ['max_parent_links', 5],
    ['max_placement_occurrences', 6], ['max_roots', 3], ['max_jobs', 3], ['max_model_targets', 4], ['max_string_code_units', 10]]) {
    const error = refusalOf(() => buildCatalog(structuredClone(AUTHORED.input), { ...policy, [key]: value }));
    assert.ok(error instanceof Refusal, key);
  }
  assert.ok(deepEqual(buildCatalog(structuredClone(AUTHORED.input), { ...policy, max_declarations: 7, max_nodes: 3,
    max_node_slots: 11, max_parent_links: 6, max_placement_occurrences: 7 }), AUTHORED.expected));
});

test('importing the module performs no file I/O and runs no CLI', () => {
  const script = `
    import fs from 'node:fs';
    let calls = 0;
    for (const k of Object.keys(fs)) if (typeof fs[k] === 'function' && /Sync$|^open|^read|^write|^mkdir|^stat|^lstat/.test(k)) {
      // Count only calls made from module code frames, not the ESM loader reading the file.
      const orig = fs[k]; fs[k] = (...a) => { if (/catalog_model_textures\\.mjs:\\d+/.test(new Error().stack)) calls++; return orig(...a); };
    }
    const mod = await import(${JSON.stringify(pathToFileURL(MODULE).href)});
    const importCalls = calls;
    mod.main(['--input-root', '/nonexistent-root', '--profile', ${JSON.stringify(PROFILE_PATH)}, '--fixtures', 'x', '--output', '/x'], { stdout: { write() {} } });
    process.stdout.write(JSON.stringify({ calls: importCalls, counterWorks: calls > importCalls, exitCode: process.exitCode ?? null, hasMain: typeof mod.main }));`;
  const r = spawnSync(process.execPath, ['--input-type=module', '-e', script], { encoding: 'utf8' });
  assert.equal(r.status, 0, r.stderr);
  assert.deepEqual(JSON.parse(r.stdout), { calls: 0, counterWorks: true, exitCode: null, hasMain: 'function' });
});

// ------------------------------------------------------------------ CLI

test('fresh fixture CLI publishes exact envelope, modes and repeatable bytes', () => {
  const outputs = [freshOut('fixture'), freshOut('fixture')];
  const bodies = outputs.map((output) => {
    const r = spawnSync(process.execPath, [MODULE, ...fixtureArgs(CANONICAL_ROOT, output)], { encoding: 'utf8' });
    assert.equal(r.status, 0, r.stdout);
    const line = JSON.parse(r.stdout);
    assert.equal(line.status, 'complete');
    assert.ok(!r.stdout.includes(CANONICAL_ROOT) && !r.stdout.includes('bark'));
    assert.equal(fs.statSync(output).mode & 0o777, 0o700);
    assert.deepEqual(fs.readdirSync(output), ['catalog.json']);
    const file = path.join(output, 'catalog.json');
    assert.equal(fs.statSync(file).mode & 0o777, 0o600);
    const body = fs.readFileSync(file);
    assert.equal(line.catalog.sha256, sha256(body));
    return body;
  });
  assert.ok(bodies[0].equals(bodies[1]), 'byte-identical repeat');
  const text = bodies[0].toString('utf8');
  assert.ok(text.endsWith('}\n') && !text.slice(0, -1).includes('\n'));
  const doc = JSON.parse(text);
  const { schema, task, mode, profile_sha256, constructor_profile_sha256, summary_sha256, input_pins, rule_sources, ...core } = doc;
  assert.deepEqual({ schema, task, mode, profile_sha256, constructor_profile_sha256, summary_sha256 }, {
    schema: 'T06-model-texture-catalog-1', task: 'T06.003.003.007', mode: 'fixtures',
    profile_sha256: '432354b127890ca3b37432c61949f88a41439c6cdeb3cfbe21d27adc621b0c68',
    constructor_profile_sha256: PROFILE.constructor_profile.sha256, summary_sha256: PROFILE.summary.sha256 });
  assert.deepEqual(input_pins, { authored: PROFILE.authored });
  assert.deepEqual(rule_sources, PROFILE.rule_sources);
  assert.ok(deepEqual(core, AUTHORED.expected));
});

test('fresh full pinned corpus CLI matches every profile count and repeats byte-identically', { timeout: 120000 }, () => {
  const outputs = [freshOut('corpus'), freshOut('corpus')];
  const results = outputs.map((output) => {
    const r = spawnSync(process.execPath, [MODULE, ...corpusArgs(CANONICAL_ROOT, output)], { encoding: 'utf8', maxBuffer: 1 << 20 });
    assert.equal(r.status, 0, r.stdout + r.stderr);
    const line = JSON.parse(r.stdout);
    assert.deepEqual(line.counts, PROFILE.expected_counts);
    return { line, body: fs.readFileSync(path.join(output, 'catalog.json')) };
  });
  assert.ok(results[0].body.equals(results[1].body), 'byte-identical corpus repeat');
  const doc = JSON.parse(results[0].body.toString('utf8'));
  assert.equal(doc.mode, 'corpus');
  assert.deepEqual(doc.input_pins, PROFILE.inputs);
  assert.deepEqual(doc.limits, PROFILE.limitations);
  assert.equal(doc.jobs.length, 8166);
  assert.equal(doc.model_parent_links.length, 48980);
  const exception = doc.jobs.filter((j) => j.outcome === 'constructor_exception');
  assert.equal(exception.length, 1);
  assert.equal(exception[0].declarations, null);
  assert.ok(exception[0].exception && exception[0].exception.phase === 'constructor');
  // Every nested referrer resolves back to its declaration.
  for (const t of doc.nested_targets) for (const r of t.referrers) {
    assert.equal(doc.jobs[r.job_index].declarations[r.texture_index].nested_target_index, t.index);
  }
});

test('strict flags and lower-only limits refuse before output', () => {
  const root = makeTestRoot();
  const output = freshOut('flags');
  const bad = [
    [],
    [...fixtureArgs(root, output), '--unknown', 'x'],
    [...fixtureArgs(root, output), '--output', output],
    ['--input-root', root, '--profile', PROFILE_PATH, '--fixtures', PROFILE.authored.path],
    [...fixtureArgs(root, output), '--report', PROFILE.inputs.report.path],
    corpusArgs(root, output).filter((_, i, a) => a[i] !== '--catalog' && a[i - 1] !== '--catalog'),
    [...fixtureArgs(root, output).slice(0, -1)],
    [...fixtureArgs(root, output), '--max-output-bytes', '134217729'],
    [...fixtureArgs(root, output), '--max-output-bytes', '-1'],
    [...fixtureArgs(root, output), '--run-timeout-ms', '0'],
    [...fixtureArgs(root, output), '--run-timeout-ms', '120001'],
    [...fixtureArgs(root, output), '--run-timeout-ms', '1e3']
  ];
  for (const argv of bad) {
    const { code, out } = captureMain(argv);
    assert.equal(code, 2, JSON.stringify(argv));
    assert.equal(out.output_created, false);
  }
  assert.equal(captureMain([...fixtureArgs(root, output), '--max-output-bytes', '100']).out.reason, 'output_limit');
  assert.equal(captureMain([...fixtureArgs(root, output), '--run-timeout-ms', '1']).out.reason, 'run_deadline');
  assert.ok(!fs.existsSync(output));
  const ok = captureMain([...fixtureArgs(root, output), '--max-output-bytes', '134217728', '--run-timeout-ms', '120000']);
  assert.equal(ok.code, 0);
});

test('pin, path, special-file and existing-output controls refuse', () => {
  const root = makeTestRoot();
  const authored = path.join(root, PROFILE.authored.path);
  const expectRefusal = (argv, reason) => {
    const { code, out } = captureMain(argv);
    assert.equal(code, 2);
    assert.equal(out.output_created, false);
    if (reason) assert.equal(out.reason, reason);
  };
  const out = () => freshOut('pins');
  expectRefusal(['--input-root', 'relative/root', '--profile', PROFILE_PATH, '--fixtures', PROFILE.authored.path, '--output', out()], 'path_refused');
  expectRefusal(['--input-root', root, '--profile', PROFILE_PATH, '--fixtures', '../' + PROFILE.authored.path, '--output', out()], 'path_refused');
  expectRefusal(['--input-root', root, '--profile', PROFILE_PATH, '--fixtures', PROFILE.inputs.report.path, '--output', out()], 'path_refused');
  expectRefusal(['--input-root', root, '--profile', PROFILE_PATH, '--fixtures', PROFILE.authored.path, '--output', path.join(CHECKOUT, 'outside')], 'output_refused');
  expectRefusal(['--input-root', root, '--profile', PROFILE_PATH, '--fixtures', PROFILE.authored.path, '--output', OUT_PARENT + '/a/b'], 'output_refused');
  const existing = out();
  fs.mkdirSync(existing, { mode: 0o700 });
  expectRefusal(fixtureArgs(root, existing), 'output_exists');
  assert.deepEqual(fs.readdirSync(existing), []);
  // Symlinked ancestor of the input root.
  const linkRoot = out();
  fs.symlinkSync(root, linkRoot);
  expectRefusal(fixtureArgs(linkRoot, out()), 'symlink_refused');
  const original = fs.readFileSync(authored);
  // Content drift with same size.
  const changed = Buffer.from(original); changed[10] ^= 1;
  fs.writeFileSync(authored, changed);
  expectRefusal(fixtureArgs(root, out()), 'pin_mismatch');
  // Symlinked leaf.
  fs.rmSync(authored); fs.writeFileSync(path.join(root, 'real.json'), original);
  fs.symlinkSync(path.join(root, 'real.json'), authored);
  expectRefusal(fixtureArgs(root, out()), 'symlink_refused');
  // Hard link (two names for one inode).
  fs.rmSync(authored); fs.linkSync(path.join(root, 'real.json'), authored);
  expectRefusal(fixtureArgs(root, out()), 'link_refused');
  // FIFO special file: refused from lstat, never opened.
  fs.rmSync(authored);
  assert.equal(spawnSync('mkfifo', [authored]).status, 0);
  expectRefusal(fixtureArgs(root, out()), 'special_file_refused');
  fs.rmSync(authored); fs.writeFileSync(authored, original);
  assert.equal(captureMain(fixtureArgs(root, out())).code, 0);
});

test('complete short writes publish identical bytes', () => {
  const root = makeTestRoot();
  const normal = freshOut('normal');
  assert.equal(captureMain(fixtureArgs(root, normal)).code, 0);
  const short = freshOut('short');
  let calls = 0;
  try {
    hooks.writeSync = (fd, buf, off, len, pos) => { calls++; return fs.writeSync(fd, buf, off, Math.min(len, 97), pos); };
    assert.equal(captureMain(fixtureArgs(root, short)).code, 0);
  } finally { resetHooks(); }
  assert.ok(calls > 100, `short write hook fired ${calls} times`);
  assert.ok(fs.readFileSync(path.join(normal, 'catalog.json')).equals(fs.readFileSync(path.join(short, 'catalog.json'))));
});

test('zero-progress, write and close failures exit1 with owned cleanup and kept evidence', () => {
  const root = makeTestRoot();
  const faults = {
    zero: () => { hooks.writeSync = () => 0; },
    throw: () => { hooks.writeSync = () => { throw Object.assign(new Error('EIO'), { code: 'EIO' }); }; },
    close: () => { hooks.closeSync = (fd) => { fs.closeSync(fd); fired.close = true; throw new Error('close failed'); }; }
  };
  const fired = {};
  for (const [name, arm] of Object.entries(faults)) {
    const output = freshOut(`fault-${name}`);
    const before = openFds();
    let result;
    let writes = 0;
    try {
      arm();
      if (hooks.writeSync) { const w = hooks.writeSync; hooks.writeSync = (...a) => { writes++; return w(...a); }; }
      result = captureMain(fixtureArgs(root, output));
    } finally { resetHooks(); }
    if (name !== 'close') assert.equal(writes, 1, `${name} fault fired exactly once (no retry)`);
    else assert.equal(fired.close, true);
    assert.equal(result.code, 1, name);
    assert.equal(result.out.status, 'failed');
    assert.equal(result.out.output_created, true);
    assert.equal(openFds(), before, `${name}: no leaked descriptor`);
    assert.ok(fs.existsSync(path.join(output, 'catalog.json')), `${name}: failed output retained as evidence`);
  }
});

test('input and own-source drift after build or publication is detected by full rechecks', () => {
  const root = makeTestRoot();
  const rule = path.join(root, PROFILE.client_source_root, Object.keys(PROFILE.rule_sources)[0]);
  const flip = (file) => { const b = fs.readFileSync(file); b[0] ^= 1; fs.writeFileSync(file, b); return () => { b[0] ^= 1; fs.writeFileSync(file, b); }; };
  let fired = 0;
  // After build: refusal before output creation.
  let restore;
  let output = freshOut('drift-build');
  try {
    hooks.afterBuild = () => { fired++; restore = flip(rule); };
    const r = captureMain(fixtureArgs(root, output));
    assert.deepEqual([r.code, r.out.reason, r.out.output_created], [2, 'source_drift', false]);
  } finally { resetHooks(); restore(); }
  assert.ok(!fs.existsSync(output));
  // Same-size content drift after publication (identity alone would not be enough if mtime were restored).
  output = freshOut('drift-publish');
  try {
    hooks.afterPublish = () => { fired++; const st = fs.statSync(rule); restore = flip(rule); fs.utimesSync(rule, st.atime, st.mtime); };
    const r = captureMain(fixtureArgs(root, output));
    assert.deepEqual([r.code, r.out.reason], [1, 'source_drift']);
  } finally { resetHooks(); restore(); }
  // Own implementation source snapshot.
  const copy = path.join(freshOut('own'), 'catalog_model_textures.mjs');
  fs.mkdirSync(path.dirname(copy), { mode: 0o700 });
  fs.copyFileSync(MODULE, copy);
  output = freshOut('drift-own');
  try {
    hooks.ownSourcePath = copy;
    hooks.afterPublish = () => { fired++; fs.appendFileSync(copy, '// drift\n'); };
    const r = captureMain(fixtureArgs(root, output));
    assert.deepEqual([r.code, r.out.reason], [1, 'source_drift']);
  } finally { resetHooks(); }
  assert.equal(fired, 3);
  assert.equal(captureMain(fixtureArgs(root, freshOut('after-drift'))).code, 0);
});
