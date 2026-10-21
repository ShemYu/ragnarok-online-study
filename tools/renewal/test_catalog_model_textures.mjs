// Tests for T06.003.003.007 nested model-texture declaration catalog and the
// T07.007.009 supplementary profile route.
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
import { admitSupplementCorpus, identityOf, NEW_PROFILE_BYTES, NEW_PROFILE_PATH, NEW_PROFILE_SHA256, restoreCleanups, ROUTES, SUPPLEMENT,
  verifiedCleanup } from './catalog_model_textures.mjs';
import { performance } from 'node:perf_hooks';

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

// ------------------------------------------------------------------ T07.007.009 route
// The new corpus route reads only the exact profile-pinned canonical metadata.
// Semantic faults are applied to genuinely read, hash-verified documents or
// through hooks.afterPinnedJson after the CLI's own complete pinned read.

const NEW_PROFILE = JSON.parse(fs.readFileSync(path.join(CHECKOUT, NEW_PROFILE_PATH), 'utf8'));
const newFixtureArgs = (root, output) => ['--input-root', root, '--profile', NEW_PROFILE_PATH, '--fixtures', NEW_PROFILE.authored.path, '--output', output];
const newCorpusArgs = (root, output, inputs = NEW_PROFILE.inputs) => ['--input-root', root, '--profile', NEW_PROFILE_PATH,
  '--report', inputs.report.path, '--jobs', inputs.jobs.path, '--manifest', inputs.manifest.path, '--catalog', inputs.catalog.path, '--output', output];
const lidentity = (abs) => identityOf(fs.lstatSync(abs, { bigint: true }));
const ruleFile = (name) => path.join(CANONICAL_ROOT, NEW_PROFILE.client_source_root, name);

// Every file the new corpus route may open, as canonical absolute paths.
function newCorpusFiles() {
  const p = NEW_PROFILE;
  return [NEW_PROFILE_PATH, p.constructor_profile.path, p.summary.path, p.constructor_producer.program.path, p.constructor_producer.worker.path,
    ...Object.values(p.inputs).map((d) => d.path)].map((rel) => path.join(CANONICAL_ROOT, rel))
    .concat(Object.keys(p.rule_sources).map(ruleFile), [MODULE]);
}
const hashAll = (files) => files.map((f) => ({ f, sha: sha256(fs.readFileSync(f)), id: lidentity(f) }));

// Genuine full pinned read of the canonical documents for API-level faults.
let genuine = null;
function genuineDocs() {
  if (!genuine) {
    const pinned = (rel, pin) => {
      const buf = fs.readFileSync(path.join(CANONICAL_ROOT, rel));
      assert.equal(buf.length, pin.bytes, rel);
      assert.equal(sha256(buf), pin.sha256, rel);
      return buf;
    };
    const p = NEW_PROFILE;
    const jobs = pinned(p.inputs.jobs.path, p.inputs.jobs).toString('utf8');
    assert.ok(jobs.endsWith('\n'));
    genuine = {
      profile: p,
      constructorProfile: JSON.parse(pinned(p.constructor_profile.path, p.constructor_profile)),
      report: JSON.parse(pinned(p.inputs.report.path, p.inputs.report)),
      rows: jobs.slice(0, -1).split('\n').map((line) => JSON.parse(line)),
      manifest: JSON.parse(pinned(p.inputs.manifest.path, p.inputs.manifest)),
      catalog: JSON.parse(pinned(p.inputs.catalog.path, p.inputs.catalog)),
      facts: { inputRoot: CANONICAL_ROOT, identity: {
        constructor_profile: lidentity(path.join(CANONICAL_ROOT, p.constructor_profile.path)),
        summary: lidentity(path.join(CANONICAL_ROOT, p.summary.path)),
        program: lidentity(path.join(CANONICAL_ROOT, p.constructor_producer.program.path)),
        worker: lidentity(path.join(CANONICAL_ROOT, p.constructor_producer.worker.path)),
        manifest: lidentity(path.join(CANONICAL_ROOT, p.inputs.manifest.path)),
        catalog: lidentity(path.join(CANONICAL_ROOT, p.inputs.catalog.path)),
        rules: Object.fromEntries(Object.keys(p.rule_sources).map((name) => [name, lidentity(ruleFile(name))]))
      } }
    };
    deepFreeze(genuine);
  }
  return structuredClone(genuine);
}

// Private root holding copies of only the small files the new fixture route reads.
function makeNewTestRoot() {
  const base = freshOut('newroot');
  fs.mkdirSync(base, { mode: 0o700 });
  const p = NEW_PROFILE;
  for (const rel of [NEW_PROFILE_PATH, p.authored.path, p.constructor_profile.path, p.summary.path,
    ...Object.keys(p.rule_sources).map((k) => `${p.client_source_root}/${k}`)]) {
    const src = rel.startsWith(p.client_source_root) ? path.join(CANONICAL_ROOT, rel) : path.join(CHECKOUT, rel);
    const dst = path.join(base, rel);
    fs.mkdirSync(path.dirname(dst), { recursive: true, mode: 0o700 });
    fs.copyFileSync(src, dst);
    fs.chmodSync(dst, 0o600);
  }
  return base;
}

function cliRun(argv) {
  const r = spawnSync(process.execPath, [MODULE, ...argv], { encoding: 'utf8', maxBuffer: 1 << 20 });
  const lines = r.stdout.split('\n');
  assert.equal(lines.length, 2, r.stdout + r.stderr);
  assert.ok(Buffer.byteLength(r.stdout) <= 4096 && !r.stdout.includes(CANONICAL_ROOT));
  return { status: r.status, out: JSON.parse(lines[0]) };
}

test('T07.007.009 exactly two frozen routes and pre-change baseline pins', () => {
  assert.deepEqual(Object.keys(ROUTES), [PROFILE_PATH, NEW_PROFILE_PATH]);
  assert.deepEqual({ ...ROUTES[NEW_PROFILE_PATH] }, { name: 'supplement', task: 'T07.007.009', path: NEW_PROFILE_PATH, bytes: 4711,
    sha256: 'c8e0a1aa853afa34088c4abca193addc5e8e66db0621fd950733b9d3339a7787' });
  assert.deepEqual({ ...ROUTES[PROFILE_PATH] }, { name: 'catalog', task: 'T06.003.003.007', path: PROFILE_PATH, bytes: 4231,
    sha256: '432354b127890ca3b37432c61949f88a41439c6cdeb3cfbe21d27adc621b0c68' });
  const newBytes = fs.readFileSync(path.join(CHECKOUT, NEW_PROFILE_PATH));
  assert.deepEqual([newBytes.length, sha256(newBytes)], [NEW_PROFILE_BYTES, NEW_PROFILE_SHA256]);
  assert.deepEqual(NEW_PROFILE.constructor_producer, SUPPLEMENT.constructor_producer);
  assert.deepEqual(NEW_PROFILE.rule_sources, PROFILE.rule_sources);
  assert.deepEqual(NEW_PROFILE.policy, PROFILE.policy);
  assert.deepEqual(NEW_PROFILE.limitations, PROFILE.limitations);
  const baseline = fs.readFileSync(path.join(CHECKOUT, 'docs/project/fixtures/T07.007.009-baseline.json'));
  assert.equal(sha256(baseline), '3a4b2018d0111f94acf61520f3f8aeb20b97c28ee0e44a692453735667971219');
  const pins = JSON.parse(baseline).source_pins;
  // Unedited inputs still match; the two owned sources are pre-change provenance only.
  for (const pin of pins.filter((p) => !p.path.startsWith('tools/renewal/'))) {
    assert.equal(sha256(fs.readFileSync(path.join(CHECKOUT, pin.path))), pin.sha256, pin.path);
  }
});

test('new fixture CLI changes only task/profile/constructor pins and reads no corpus or producer file', () => {
  const root = makeNewTestRoot();
  const oldRoot = makeTestRoot();
  const opened = [];
  const realOpen = fs.openSync;
  const outputs = [freshOut('newfx'), freshOut('newfx')];
  const before = openFds();
  let codes;
  try {
    fs.openSync = (p, ...rest) => { opened.push(String(p)); return realOpen(p, ...rest); };
    codes = outputs.map((output) => captureMain(newFixtureArgs(root, output)).code);
  } finally { fs.openSync = realOpen; }
  assert.deepEqual(codes, [0, 0]);
  assert.equal(openFds(), before, 'no leaked descriptor');
  const allowed = new Set([NEW_PROFILE_PATH, NEW_PROFILE.authored.path, NEW_PROFILE.constructor_profile.path, NEW_PROFILE.summary.path,
    ...Object.keys(NEW_PROFILE.rule_sources).map((k) => `${NEW_PROFILE.client_source_root}/${k}`)].map((rel) => path.join(root, rel)));
  const reads = opened.filter((p) => !p.startsWith(OUT_PARENT + path.sep + 'test-') || p.startsWith(root));
  for (const p of reads) assert.ok(allowed.has(p) || p === MODULE, `unexpected open ${p}`);
  assert.ok(allowed.size === 8 && [...allowed].every((p) => opened.includes(p)), 'every fixture input opened');
  for (const rel of [...Object.values(NEW_PROFILE.inputs).map((d) => d.path), NEW_PROFILE.constructor_producer.program.path,
    NEW_PROFILE.constructor_producer.worker.path]) assert.ok(!opened.some((p) => p.endsWith(rel)), `sentinel ${rel}`);
  const bodies = outputs.map((o) => fs.readFileSync(path.join(o, 'catalog.json')));
  assert.ok(bodies[0].equals(bodies[1]));
  const oldOut = freshOut('oldfx');
  assert.equal(captureMain(fixtureArgs(oldRoot, oldOut)).code, 0);
  const doc = JSON.parse(bodies[0]);
  const old = JSON.parse(fs.readFileSync(path.join(oldOut, 'catalog.json')));
  assert.deepEqual(Object.keys(doc), Object.keys(old));
  assert.deepEqual({ task: doc.task, profile_sha256: doc.profile_sha256, constructor_profile_sha256: doc.constructor_profile_sha256 },
    { task: 'T07.007.009', profile_sha256: NEW_PROFILE_SHA256, constructor_profile_sha256: SUPPLEMENT.constructor_profile.sha256 });
  for (const key of Object.keys(old)) if (!['task', 'profile_sha256', 'constructor_profile_sha256'].includes(key)) assert.deepEqual(doc[key], old[key], key);
  assert.equal(old.task, 'T06.003.003.007');
  assert.deepEqual(doc.input_pins, { authored: NEW_PROFILE.authored });
  for (const job of doc.jobs) assert.deepEqual(Object.keys(job.cleanup), ['exit_observed', 'exit_code', 'terminated_by_parent']);
  for (const key of ['root_model_references', 'carried_ground_targets', 'world_gap_ledger_reference', 'constructor_producer']) assert.ok(!(key in doc));
});

test('cross-profile substitutions, unknown profiles and input aliases refuse before output', () => {
  const root = makeNewTestRoot();
  const expect = (argv, reason) => {
    const { code, out } = captureMain(argv);
    assert.deepEqual([code, out.reason, out.output_created], [2, reason, false], JSON.stringify(argv.slice(2, 4)));
  };
  // Old path carrying new bytes, and new path carrying old bytes.
  const swapped = makeNewTestRoot();
  fs.mkdirSync(path.dirname(path.join(swapped, PROFILE_PATH)), { recursive: true });
  fs.copyFileSync(path.join(CHECKOUT, NEW_PROFILE_PATH), path.join(swapped, PROFILE_PATH));
  fs.chmodSync(path.join(swapped, PROFILE_PATH), 0o600);
  expect(fixtureArgs(swapped, freshOut('x')), 'size_limit'); // larger than the old route's exact cap
  fs.copyFileSync(path.join(CHECKOUT, PROFILE_PATH), path.join(swapped, NEW_PROFILE_PATH));
  fs.chmodSync(path.join(swapped, NEW_PROFILE_PATH), 0o600);
  expect(newFixtureArgs(swapped, freshOut('x')), 'pin_mismatch');
  for (const profile of ['docs/project/fixtures/T07.007.008-profile.json', 'docs/project/fixtures/T07.007.009-baseline.json', '__proto__', 'constructor',
    './' + NEW_PROFILE_PATH, NEW_PROFILE_PATH + '/']) {
    expect(['--input-root', root, '--profile', profile, '--fixtures', NEW_PROFILE.authored.path, '--output', freshOut('x')], 'path_refused');
  }
  // New profile with old corpus inputs and old profile with new corpus inputs.
  expect(newCorpusArgs(CANONICAL_ROOT, freshOut('x'), PROFILE.inputs), 'path_refused');
  expect(corpusArgs(CANONICAL_ROOT, freshOut('x')).map((a) => a === PROFILE.inputs.report.path ? NEW_PROFILE.inputs.report.path : a), 'path_refused');
  // Child/reference aliases of the exact inputs.
  const alias = { ...NEW_PROFILE.inputs, report: { path: NEW_PROFILE.inputs.report.path.replace('/output/', '/output/./') } };
  expect(newCorpusArgs(CANONICAL_ROOT, freshOut('x'), alias), 'path_refused');
  const child = { ...NEW_PROFILE.inputs, jobs: { path: NEW_PROFILE.inputs.jobs.path.replace('corpus/output', 'corpus/output/reference') } };
  expect(newCorpusArgs(CANONICAL_ROOT, freshOut('x'), child), 'path_refused');
  // New corpus fails closed on a non-canonical root without its metadata.
  expect(newCorpusArgs(root, freshOut('x')), 'missing_input');
  // Mixed and duplicate flags.
  for (const argv of [[...newFixtureArgs(root, freshOut('x')), '--jobs', NEW_PROFILE.inputs.jobs.path],
    [...newCorpusArgs(CANONICAL_ROOT, freshOut('x')), '--profile', NEW_PROFILE_PATH],
    [...newCorpusArgs(CANONICAL_ROOT, freshOut('x')), '--producer', 'x']]) {
    expect(argv, 'usage');
  }
});

test('actual new metadata corpus CLI: exact counts, joins, provenance, restored cleanup and preserved inputs', { timeout: 120000 }, () => {
  const files = newCorpusFiles();
  const before = hashAll(files);
  const outputs = [freshOut('newcorpus'), freshOut('newcorpus')];
  const bodies = outputs.map((output) => {
    const { status, out } = cliRun(newCorpusArgs(CANONICAL_ROOT, output));
    assert.equal(status, 0, JSON.stringify(out));
    assert.deepEqual(out.counts, NEW_PROFILE.expected_counts);
    assert.equal(fs.statSync(output).mode & 0o777, 0o700);
    assert.deepEqual(fs.readdirSync(output), ['catalog.json']);
    assert.equal(fs.statSync(path.join(output, 'catalog.json')).mode & 0o777, 0o600);
    const body = fs.readFileSync(path.join(output, 'catalog.json'));
    assert.equal(out.catalog.sha256, sha256(body));
    return body;
  });
  assert.ok(bodies[0].equals(bodies[1]), 'byte-identical repeat');
  assert.deepEqual(hashAll(files), before, 'inputs, producer and sources unchanged');
  const doc = JSON.parse(bodies[0]);
  const g = genuineDocs();
  assert.deepEqual(Object.keys(doc), ['schema', 'task', 'mode', 'profile_sha256', 'constructor_profile_sha256', 'summary_sha256', 'input_pins',
    'rule_sources', 'counts', 'roots', 'remaining_gap_root_ordinals', 'prior_first_level_gaps', 'model_targets', 'model_parent_links', 'jobs',
    'nested_targets', 'limits', 'root_model_references', 'carried_ground_targets', 'world_gap_ledger_reference', 'constructor_producer']);
  assert.deepEqual([doc.schema, doc.task, doc.mode, doc.profile_sha256, doc.constructor_profile_sha256, doc.summary_sha256],
    ['T06-model-texture-catalog-1', 'T07.007.009', 'corpus', NEW_PROFILE_SHA256, NEW_PROFILE.constructor_profile.sha256, NEW_PROFILE.summary.sha256]);
  assert.deepEqual(doc.input_pins, NEW_PROFILE.inputs);
  assert.deepEqual(doc.rule_sources, NEW_PROFILE.rule_sources);
  assert.deepEqual(doc.constructor_producer, NEW_PROFILE.constructor_producer);
  assert.deepEqual(doc.root_model_references, g.manifest.root_model_references);
  assert.deepEqual(doc.carried_ground_targets, g.manifest.carried_ground_targets);
  assert.deepEqual(doc.world_gap_ledger_reference, g.manifest.world_gap_ledger_reference);
  assert.deepEqual(doc.limits, NEW_PROFILE.limitations);
  // Full 273-target, 297-parent and 4922-placement joins.
  assert.deepEqual(doc.model_targets, g.manifest.targets);
  assert.equal(doc.model_parent_links.length, 297);
  assert.equal(doc.model_parent_links.reduce((n, l) => n + l.placement_indexes.length, 0), 4922);
  doc.model_parent_links.forEach((link, i) => {
    const ref = doc.root_model_references[i];
    assert.deepEqual([link.model_ordinal, link.catalog_target_index, link.referrer.job_index, link.referrer.loader_index, link.source_job_id,
      link.root_references], [ref.model_ordinal, ref.target_index, ref.catalog_job_index, ref.loader_index, ref.catalog_job_id,
      [{ root_ordinal: ref.root_ordinal, edge_kind: ref.edge_kind }]]);
    assert.deepEqual(link.placement_indexes, ref.occurrence_indexes);
  });
  // Every job keeps the exact original five cleanup facts by source row AND job id.
  assert.equal(doc.jobs.length, 273);
  doc.jobs.forEach((job, i) => {
    assert.equal(job.source_row_index, i);
    assert.equal(job.job_id, g.rows[i].job_id);
    assert.deepEqual(job.cleanup, g.rows[i].cleanup);
    assert.deepEqual(Object.keys(job.cleanup), ['exit_observed', 'exit_code', 'terminated_by_parent', 'stdout_eof_observed', 'stderr_eof_observed']);
  });
  // Declarations, nested targets and slots.
  assert.equal(doc.jobs.reduce((n, j) => n + j.declarations.length, 0), 397);
  assert.equal(doc.nested_targets.length, 178);
  assert.equal(new Set(doc.nested_targets.map((t) => t.http_path)).size, 178);
  for (const t of doc.nested_targets) for (const r of t.referrers) assert.equal(doc.jobs[r.job_index].declarations[r.texture_index].nested_target_index, t.index);
  // Carried BMPs stay separate from jobs and declarations; world gaps stay open.
  assert.equal(doc.carried_ground_targets.length, 38);
  assert.equal(doc.carried_ground_targets.reduce((n, c) => n + c.catalog_target.referrers.length, 0), 40);
  const carriedIdx = new Set(doc.carried_ground_targets.map((c) => c.target_index));
  assert.ok(doc.model_targets.every((t) => !carriedIdx.has(t.target_index)));
  assert.deepEqual([doc.world_gap_ledger_reference.roots, doc.world_gap_ledger_reference.remaining_core_gap_roots,
    doc.world_gap_ledger_reference.reconciled_by_this_subset], [1296, 82, false]);
  assert.deepEqual([doc.remaining_gap_root_ordinals, doc.prior_first_level_gaps], [[], []]);
  assert.ok(doc.roots.every((r) => r.original_gap_root_ordinal === null && r.ordinal_scope === 'four-target-subset-only'));
  // In-process run: same bytes, owned descriptors closed, all pins rechecked.
  const fdBefore = openFds();
  const output = freshOut('newcorpus-inproc');
  let roles = null;
  try {
    hooks.afterBuild = (r) => { roles = r; };
    assert.equal(captureMain(newCorpusArgs(CANONICAL_ROOT, output)).code, 0);
  } finally { resetHooks(); }
  assert.equal(openFds(), fdBefore);
  assert.ok(fs.readFileSync(path.join(output, 'catalog.json')).equals(bodies[0]));
  assert.deepEqual(new Set(roles), new Set(['profile', 'constructor_profile', 'summary', ...Object.keys(NEW_PROFILE.rule_sources).map((k) => `rule:${k}`),
    'implementation', 'report', 'jobs', 'manifest', 'catalog', 'producer_program', 'producer_worker']));
  assert.equal(roles.length, 14);
});

// [label, document key, mutate(doc, docs), expected detail]
const eofRow = 5;
const setCleanup = (fn) => (d, all) => { fn(all.rows[eofRow].cleanup); fn(all.report.job_accounting[eofRow].cleanup); };
const ADMISSION_FAULTS = [
  ['stdout EOF missing', setCleanup((c) => { delete c.stdout_eof_observed; }), `row ${eofRow} cleanup`],
  ['stderr EOF missing', setCleanup((c) => { delete c.stderr_eof_observed; }), `row ${eofRow} cleanup`],
  ['stdout EOF false', setCleanup((c) => { c.stdout_eof_observed = false; }), `row ${eofRow} cleanup`],
  ['stderr EOF string', setCleanup((c) => { c.stderr_eof_observed = 'true'; }), `row ${eofRow} cleanup`],
  ['stdout EOF null', setCleanup((c) => { c.stdout_eof_observed = null; }), `row ${eofRow} cleanup`],
  ['stderr EOF number 1', setCleanup((c) => { c.stderr_eof_observed = 1; }), `row ${eofRow} cleanup`],
  ['historical three-key cleanup only', setCleanup((c) => { delete c.stdout_eof_observed; delete c.stderr_eof_observed; }), `row ${eofRow} cleanup`],
  ['nonzero exit', setCleanup((c) => { c.exit_code = 1; }), `row ${eofRow} cleanup`],
  ['unknown exit code', setCleanup((c) => { c.exit_code = null; }), `row ${eofRow} cleanup`],
  ['exit not observed', setCleanup((c) => { c.exit_observed = false; }), `row ${eofRow} cleanup`],
  ['parent terminated', setCleanup((c) => { c.terminated_by_parent = true; }), `row ${eofRow} cleanup`],
  ['extra cleanup fact', setCleanup((c) => { c.uncertainty = 'x'; }), `row ${eofRow} cleanup`],
  ['accounting drift only', (d, a) => { a.report.job_accounting[eofRow].elapsed_ms += 1; }, `row ${eofRow} accounting`],
  ['accounting marker missing', (d, a) => { delete a.report.job_accounting[eofRow].summary_payload_in_jsonl_only; }, `row ${eofRow} accounting`],
  ['extra row field', (d, a) => { a.rows[eofRow].reason = 'x'; a.report.job_accounting[eofRow].reason = 'x'; }, `row ${eofRow} keys`],
  ['row outcome', (d, a) => { a.rows[eofRow].phase = 'constructor'; a.report.job_accounting[eofRow].phase = 'constructor'; }, `row ${eofRow} outcome`],
  ['row realm seek', (d, a) => { a.rows[eofRow].seek_globals = [1, 2]; a.report.job_accounting[eofRow].seek_globals = [1, 2]; }, `row ${eofRow} realm`],
  ['row realm module duplicate', (d, a) => { const k = a.rows[eofRow].loaded_module_keys; k[1] = k[0]; a.report.job_accounting[eofRow].loaded_module_keys = [...k]; }, `row ${eofRow} realm`],
  ['row summary bytes', (d, a) => { a.rows[eofRow].summary_json_bytes++; a.report.job_accounting[eofRow].summary_json_bytes++; }, `row ${eofRow} summary bytes`],
  ['row order swap', (d, a) => { [a.rows[0], a.rows[1]] = [a.rows[1], a.rows[0]]; }, 'row 0 job'],
  ['duplicate row', (d, a) => { a.rows[1] = structuredClone(a.rows[0]); }, 'row 1 job'],
  ['missing row', (d, a) => { a.rows.pop(); }, 'row count'],
  ['extra row', (d, a) => { a.rows.push(structuredClone(a.rows[0])); }, 'row count'],
  ['report not qualified', (d, a) => { a.report.qualified = false; }, 'report schema'],
  ['report qualified string', (d, a) => { a.report.qualified = 'true'; }, 'report schema'],
  ['report extra key', (d, a) => { a.report.report_limit = {}; }, 'report schema'],
  ['report source postchecks 18', (d, a) => { a.report.source_postchecks.expected = 18; }, 'report source postchecks'],
  ['report source postcheck failure', (d, a) => { a.report.source_postchecks.failed = ['worker']; }, 'report source postchecks'],
  ['report identity claim', (d, a) => { a.report.pinned_inputs_identity_unchanged_after_run = false; }, 'report source postchecks'],
  ['report body postchecks', (d, a) => { a.report.postchecks.ok = false; }, 'report body postchecks'],
  ['report cleanup unverified', (d, a) => { a.report.cleanup.unverified = ['model-000005']; }, 'report cleanup'],
  ['report cleanup halted', (d, a) => { a.report.cleanup.halted = 'source_drift'; }, 'report cleanup'],
  ['storage close', (d, a) => { a.report.storage.jobs_close_verified = false; }, 'report storage'],
  ['storage tail', (d, a) => { a.report.storage.jobs_tail_uncertain = true; }, 'report storage'],
  ['jobs file sha', (d, a) => { a.report.jobs_file.sha256 = '0'.repeat(64); }, 'report jobs file'],
  ['jobs file incomplete', (d, a) => { a.report.jobs_file.complete = false; }, 'report jobs file'],
  ['job outcomes', (d, a) => { a.report.counts.job_outcomes.returned = 272; a.report.counts.job_outcomes.timeout = 1; }, 'report counts'],
  ['target outcomes', (d, a) => { a.report.counts.target_outcomes.unattempted = 1; }, 'report counts'],
  ['report target outcome', (d, a) => { a.report.targets[3].constructor_outcome = 'timeout'; }, 'report target 3'],
  ['functional flag', (d, a) => { a.report.functional.all_model_constructors_returned = false; }, 'report functional'],
  ['functional open failure', (d, a) => { a.report.functional.open_failures = [{ job_id: 'model-000001' }]; }, 'report functional'],
  ['pinned role missing', (d, a) => { a.report.pinned_inputs.splice(5, 1); }, 'report pinned inputs'],
  ['pinned role duplicate', (d, a) => { a.report.pinned_inputs[5] = structuredClone(a.report.pinned_inputs[4]); }, 'report pinned inputs'],
  ['pinned role extra', (d, a) => { a.report.pinned_inputs.push({ ...a.report.pinned_inputs[0], role: 'extra' }); }, 'report pinned inputs'],
  ['pinned worker sha', (d, a) => { a.report.pinned_inputs[1].sha256 = '0'.repeat(64); }, 'report pinned inputs'],
  ['pinned profile substituted', (d, a) => { a.report.pinned_inputs[0].sha256 = PROFILE.constructor_profile.sha256; }, 'report pinned inputs'],
  ['pinned ledger identity', (d, a) => { a.report.pinned_inputs[7].identity.ino = '1'; }, 'report pinned inputs'],
  ['producer worker sha', (d, a) => { a.report.own_sources[1].sha256 = '0'.repeat(64); }, 'report producer'],
  ['producer program identity decimal', (d, a) => { a.report.own_sources[0].identity.ino = Number(a.report.own_sources[0].identity.ino); }, 'report producer'],
  ['producer actual identity drift', (d, a) => { a.facts.identity.program.mtime_ns = '1'; }, 'report producer'],
  ['worker actual identity drift', (d, a) => { a.facts.identity.worker.ino = '1'; }, 'report producer'],
  ['summary identity', (d, a) => { a.report.common_summary.identity.ctime_ns = '1'; }, 'report summary'],
  ['summary revision', (d, a) => { a.report.summary_sha256 = PROFILE.constructor_profile.sha256; }, 'report pins'],
  ['client rule identity', (d, a) => { a.report.client_source.rule_sources[0].identity.ino = '1'; }, 'report rule_sources src/Loaders/MapLoader.js identity'],
  ['client module unverified', (d, a) => { a.report.client_source.sources[3].verified = false; }, 'report sources src/Utils/CodepageManager.js'],
  ['manifest input identity', (d, a) => { a.facts.identity.manifest.size = '1'; }, 'report input'],
  ['report provenance', (d, a) => { a.report.root_model_references.pop(); }, 'report supplement provenance'],
  ['availability placements', (d, a) => { a.report.availability_admission.placement_occurrences = 4921; }, 'report availability admission'],
  ['manifest reference occurrence', (d, a) => { a.manifest.root_model_references[7].occurrence_indexes.pop(); }, 'root model references'],
  ['manifest reference source row', (d, a) => { a.manifest.root_model_references[7].catalog_source_row_index = 3; }, 'root model references'],
  ['manifest target referrer', (d, a) => { a.manifest.targets[2].referrers[0].loader_index++; }, 'manifest target 2'],
  ['manifest target ordinal collapse', (d, a) => { a.manifest.targets[2].model_ordinal = a.manifest.targets[2].target_index; }, 'manifest target 2'],
  ['manifest body path', (d, a) => { a.manifest.targets[2].body.path += '.ref'; }, 'manifest target 2 body'],
  ['manifest job header', (d, a) => { a.manifest.jobs[4].header_version_bytes = '4752534d0105'; }, 'manifest jobs'],
  ['carried dropped', (d, a) => { a.manifest.carried_ground_targets.pop(); }, 'carried count'],
  ['carried as model', (d, a) => { a.manifest.carried_ground_targets[0].availability_record.signature.kind = 'model'; }, 'carried 0 availability'],
  ['world ledger reconciled', (d, a) => { a.manifest.world_gap_ledger_reference.reconciled_by_this_subset = true; }, 'world ledger'],
  ['world ledger gaps', (d, a) => { a.manifest.world_gap_ledger_reference.remaining_core_gap_roots = 0; }, 'world ledger'],
  ['guessed world ordinal', (d, a) => { a.catalog.roots[1].original_gap_root_ordinal = 7; a.manifest.roots[1].original_gap_root_ordinal = 7; }, 'catalog root 1'],
  ['manifest catalog identity', (d, a) => { a.manifest.availability.catalog.identity.ino = '1'; }, 'manifest catalog identity'],
  ['manifest availability descriptor', (d, a) => { a.manifest.availability.root_audit.sha256 = '0'.repeat(64); }, 'manifest availability root_audit'],
  ['catalog duplicate referrer', (d, a) => { a.catalog.targets[30].referrers.push(structuredClone(a.catalog.targets[30].referrers[0])); }, 'catalog target 30 duplicate referrer'],
  ['catalog task', (d, a) => { a.catalog.task = 'T06.003.003.004'; }, 'catalog schema'],
  ['constructor profile task', (d, a) => { a.constructorProfile.task = 'T06.003.003.006'; }, 'constructor profile']
];

test('new admission validates EOF, accounting, report, producer, source, pin, storage and join facts before projection', () => {
  const ok = admitSupplementCorpus(genuineDocs());
  assert.equal(ok.input.model_rows.length, 273);
  assert.equal(ADMISSION_FAULTS.length, 74);
  for (const [label, mutate, detail] of ADMISSION_FAULTS) {
    const docs = genuineDocs();
    mutate(null, docs);
    const error = refusalOf(() => admitSupplementCorpus(docs));
    assert.ok(error instanceof Refusal, label);
    assert.deepEqual([error.reason, error.detail], ['admission_discrepancy', detail], label);
  }
});

test('CLI applies semantic faults only after complete pinned reads and refuses before output', { timeout: 120000 }, () => {
  const cases = [
    ['jobs', (rows) => { delete rows[0].cleanup.stdout_eof_observed; return rows; }],
    ['jobs', (rows) => { rows[9].cleanup.stderr_eof_observed = false; return rows; }],
    ['report', (r) => { r.storage.jobs_close_verified = false; return r; }],
    ['report', (r) => { r.own_sources[1].sha256 = '0'.repeat(64); return r; }],
    ['manifest', (m) => { m.world_gap_ledger_reference.reconciled_by_this_subset = true; return m; }],
    ['catalog', (c) => { c.roots[0].original_gap_root_ordinal = 0; return c; }],
    ['constructor_profile', (p) => { p.worker.sha256 = '0'.repeat(64); return p; }]
  ];
  for (const [role, fault] of cases) {
    const seen = [];
    const output = freshOut('newfault');
    const fdBefore = openFds();
    let result;
    try {
      hooks.afterPinnedJson = (r, value) => { seen.push(r); return r === role ? fault(value) : value; };
      result = captureMain(newCorpusArgs(CANONICAL_ROOT, output));
    } finally { resetHooks(); }
    assert.deepEqual(seen, ['constructor_profile', 'report', 'jobs', 'manifest', 'catalog'], 'hook activated after every pinned read');
    assert.deepEqual([result.code, result.out.reason, result.out.output_created], [2, 'admission_discrepancy', false], role);
    assert.ok(!fs.existsSync(output));
    assert.equal(openFds(), fdBefore);
  }
});

test('historical core stays three-key; restore is a pure exact source-row and job-id join', () => {
  const docs = deepFreeze(genuineDocs());
  const admitted = admitSupplementCorpus(docs);
  // Core rows are fresh three-key copies; the parsed rows keep their five facts.
  admitted.input.model_rows.forEach((row, i) => {
    assert.deepEqual(row.cleanup, { exit_observed: true, exit_code: 0, terminated_by_parent: false });
    assert.notEqual(row, docs.rows[i]);
    assert.ok(verifiedCleanup(docs.rows[i].cleanup));
  });
  // The unchanged core refuses unprojected five-key rows.
  assert.ok(refusalOf(() => buildCatalog({ ...admitted.input, model_rows: docs.rows })) instanceof Refusal);
  const core = deepFreeze(buildCatalog(admitted.input));
  assert.deepEqual(core.counts, NEW_PROFILE.expected_counts);
  const snapshot = JSON.stringify(core);
  const restored = restoreCleanups(core, admitted.cleanups);
  assert.equal(JSON.stringify(core), snapshot, 'core unchanged');
  restored.jobs.forEach((job, i) => assert.deepEqual(job.cleanup, docs.rows[i].cleanup));
  assert.deepEqual({ ...restored, jobs: null }, { ...core, jobs: null });
  const bad = [
    (c) => { [c[0], c[1]] = [c[1], c[0]]; },
    (c) => { c[3] = { source_row_index: 3, cleanup: c[3].cleanup }; },
    (c) => { c[3].job_id = c[4].job_id; },
    (c) => { c[3].source_row_index = 4; },
    (c) => { c[3].cleanup.stdout_eof_observed = false; },
    (c) => { delete c[3].cleanup.stderr_eof_observed; },
    (c) => { c[3].cleanup.exit_code = 1; },
    (c) => { c.pop(); }
  ];
  for (const [i, change] of bad.entries()) {
    const cleanups = structuredClone(admitted.cleanups);
    change(cleanups);
    assert.equal(refusalOf(() => restoreCleanups(core, cleanups))?.reason, 'restore_mismatch', `case ${i}`);
  }
  // A historical core cleanup that disagrees with the original refuses too.
  const drifted = structuredClone(core);
  drifted.jobs[2].cleanup.exit_code = 1;
  assert.equal(refusalOf(() => restoreCleanups(drifted, admitted.cleanups))?.reason, 'restore_mismatch');
  // Authored fixtures keep three-key cleanup through the core.
  for (const job of buildCatalog(structuredClone(AUTHORED.input)).jobs) assert.equal(Object.keys(job.cleanup).length, 3);
});

test('new route detects post-build and post-publication input and source drift', { timeout: 120000 }, () => {
  const root = makeNewTestRoot();
  const flip = (file) => { const b = fs.readFileSync(file); b[0] ^= 1; fs.writeFileSync(file, b); return () => { b[0] ^= 1; fs.writeFileSync(file, b); }; };
  let fired = 0;
  for (const [stage, rel] of [['afterBuild', NEW_PROFILE.constructor_profile.path], ['afterPublish', NEW_PROFILE.authored.path],
    ['afterBuild', `${NEW_PROFILE.client_source_root}/src/Loaders/Model.js`], ['afterPublish', NEW_PROFILE.summary.path]]) {
    const file = path.join(root, rel);
    const output = freshOut('newdrift');
    let restore;
    try {
      hooks[stage] = () => { fired++; const st = fs.statSync(file); restore = flip(file); fs.utimesSync(file, st.atime, st.mtime); };
      const r = captureMain(newFixtureArgs(root, output));
      assert.deepEqual([r.code, r.out.reason, r.out.output_created], stage === 'afterBuild' ? [2, 'source_drift', false] : [1, 'source_drift', true], rel);
    } finally { resetHooks(); restore(); }
    assert.equal(fs.existsSync(path.join(output, 'catalog.json')), stage === 'afterPublish');
  }
  // Actual corpus route with a private copy of the implementation source.
  const copyDir = freshOut('newown');
  fs.mkdirSync(copyDir, { mode: 0o700 });
  const copy = path.join(copyDir, 'catalog_model_textures.mjs');
  for (const stage of ['afterBuild', 'afterPublish']) {
    fs.copyFileSync(MODULE, copy);
    fs.chmodSync(copy, 0o600);
    const output = freshOut('newcorpusdrift');
    const fdBefore = openFds();
    try {
      hooks.ownSourcePath = copy;
      hooks[stage] = () => { fired++; fs.appendFileSync(copy, '// drift\n'); };
      const r = captureMain(newCorpusArgs(CANONICAL_ROOT, output));
      assert.deepEqual([r.code, r.out.reason], stage === 'afterBuild' ? [2, 'source_drift'] : [1, 'source_drift']);
    } finally { resetHooks(); }
    assert.equal(openFds(), fdBefore);
  }
  assert.equal(fired, 6);
  assert.equal(captureMain(newFixtureArgs(root, freshOut('newafter'))).code, 0);
});

test('new route storage: complete short writes, single-attempt write/close failures, late deadline and FD closure', () => {
  const root = makeNewTestRoot();
  const normal = freshOut('newnormal');
  assert.equal(captureMain(newFixtureArgs(root, normal)).code, 0);
  const short = freshOut('newshort');
  let calls = 0;
  try {
    hooks.writeSync = (fd, buf, off, len, pos) => { calls++; return fs.writeSync(fd, buf, off, Math.min(len, 61), pos); };
    assert.equal(captureMain(newFixtureArgs(root, short)).code, 0);
  } finally { resetHooks(); }
  assert.ok(calls > 200);
  assert.ok(fs.readFileSync(path.join(normal, 'catalog.json')).equals(fs.readFileSync(path.join(short, 'catalog.json'))));
  const fired = {};
  const faults = {
    partialThenZero: () => { let n = 0; hooks.writeSync = (fd, buf, off, len, pos) => { fired.partial = ++n; return n === 1 ? fs.writeSync(fd, buf, off, 10, pos) : 0; }; },
    zero: () => { hooks.writeSync = () => { fired.zero = true; return 0; }; },
    overlong: () => { hooks.writeSync = (fd, buf, off, len) => { fired.overlong = true; return len + 1; }; },
    throw: () => { hooks.writeSync = () => { fired.throw = true; throw Object.assign(new Error('EIO'), { code: 'EIO' }); }; },
    close: () => { hooks.closeSync = (fd) => { fs.closeSync(fd); fired.close = true; throw new Error('close failed'); }; },
    lateDeadline: () => { hooks.afterPublish = () => { fired.late = true; const end = performance.now() + 1200; while (performance.now() < end) { /* spin */ } }; }
  };
  for (const [name, arm] of Object.entries(faults)) {
    const output = freshOut(`newfault-${name}`);
    const before = openFds();
    let result;
    try {
      arm();
      const argv = newFixtureArgs(root, output);
      result = captureMain(name === 'lateDeadline' ? [...argv, '--run-timeout-ms', '1000'] : argv);
    } finally { resetHooks(); }
    assert.deepEqual([result.code, result.out.status, result.out.output_created], [1, 'failed', true], name);
    assert.equal(result.out.reason, name === 'lateDeadline' ? 'run_deadline' : ['close', 'throw'].includes(name) ? 'internal_error' : 'output_io_error', name);
    assert.equal(openFds(), before, `${name}: no leaked descriptor`);
    assert.ok(fs.existsSync(path.join(output, 'catalog.json')), `${name}: failed output retained`);
  }
  assert.deepEqual(Object.keys(fired).sort(), ['close', 'late', 'overlong', 'partial', 'throw', 'zero']);
  assert.equal(fired.partial, 2, 'partial write then zero progress, no retry');
  // Early deadline: refused before any output.
  const early = freshOut('newearly');
  try {
    hooks.afterBuild = () => { const end = performance.now() + 1200; while (performance.now() < end) { /* spin */ } };
    const r = captureMain([...newFixtureArgs(root, early), '--run-timeout-ms', '1000']);
    assert.deepEqual([r.code, r.out.reason, r.out.output_created], [2, 'run_deadline', false]);
  } finally { resetHooks(); }
  assert.ok(!fs.existsSync(early));
});
