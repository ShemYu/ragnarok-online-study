// T07.007.014.021 authored tests for tools/renewal/observe_tga_decode.mjs.
//
//   /usr/bin/perl -e 'alarm shift; exec @ARGV or die "exec: $!"' 60 \
//     node --max-old-space-size=125 --max-semi-space-size=1 tests/tga_decode_observer.test.mjs
//
// Run the file directly (node:test in-process, no runner child). Reads the
// frozen profile metadata, saved source and .020 fixture only; never opens a
// retained body path and never invokes actual mode on the real profile.
// Copied decoder spans execute only on tiny authored raw bodies within the
// .020 caps; larger dimensions and guard faults use handwritten stubs.
import assert from 'node:assert/strict';
import { createHash, randomBytes } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import {
  COUNTS, FIXTURE_PIN, ObserverFailure, ObserverRefusal, PROFILE_BOUNDS, PROFILE_PIN, QUERY_INDICES, SOURCE_PIN, SPANS, TINY_BOUNDS,
  buildScaffold, checkEffectiveHeap, checkLittleEndian, decodeInRealm, extractSpans, identityOf, main, makeDeadline, readHeldInput,
  runObserver, validateProfile,
} from '../tools/renewal/observe_tga_decode.mjs';

const sha256 = (b) => createHash('sha256').update(b).digest('hex');
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PROFILE_REL = '.tools/renewal/t07-014-021-preparation-root-1/PROFILE_ROOT.json';
const ROOT = process.env.T07_021_ROOT
  ?? (fs.existsSync(path.join(REPO, PROFILE_REL)) ? REPO : path.resolve(REPO, '..', 'reverse-the-Ragnarok-Online-to-play-by-myself'));
const PROFILE_PATH = path.join(ROOT, PROFILE_REL);
const FIXTURE_PATH = path.join(REPO, 'docs/project/fixtures/T07.007.014.020-cases.json');
const PREFIX = process.env.T07_021_PRIVATE_PREFIX ?? path.join(REPO, '.tools/renewal/t07-014-021-claude-authored-1');

// Fresh exclusive per-run test directory; earlier captures are never touched.
const TEST_DIR = path.join(PREFIX, `tests-${new Date().toISOString().replace(/[:.]/g, '')}-${randomBytes(3).toString('hex')}`);
fs.mkdirSync(TEST_DIR, { mode: 0o700 });
let seq = 0;
const freshDir = (name) => { const d = path.join(TEST_DIR, `${String(++seq).padStart(2, '0')}-${name}`); fs.mkdirSync(d, { mode: 0o700 }); return d; };
const writeOwned = (file, bytes) => { fs.writeFileSync(file, bytes, { mode: 0o600, flag: 'wx' }); return file; };
const pinOf = (file) => { const b = fs.readFileSync(file); return { bytes: b.length, sha256: sha256(b) }; };
const deadline = (ms = 10000) => makeDeadline(ms);
const failsWith = (fn, code) => assert.throws(fn, (e) => { assert.ok(e instanceof ObserverFailure || e instanceof ObserverRefusal, String(e)); assert.equal(e.code, code, e.message); return true; });

const forever = makeDeadline(10000);
const fixtureHeld = readHeldInput(FIXTURE_PATH, FIXTURE_PIN, 1 << 20, forever, 'fixture');
let fixture;
try { fixture = JSON.parse(fixtureHeld.bytes.toString('utf8')); } finally { fixtureHeld.close(); fixtureHeld.releaseBytes(); }
const profileHeld = readHeldInput(PROFILE_PATH, PROFILE_PIN, 1 << 20, forever, 'profile');
profileHeld.close();
const realProfile = JSON.parse(profileHeld.bytes.toString('utf8'));
const realSourcePath = realProfile.source.path;
const sourceHeld = readHeldInput(realSourcePath, { ...SOURCE_PIN, identity: realProfile.source.identity_decimal }, SOURCE_PIN.bytes, forever, 'source');
sourceHeld.close();
const spanTexts = extractSpans(sourceHeld.bytes);
const SCAFFOLD = buildScaffold(spanTexts);
const caseById = new Map(fixture.cases.map((c) => [c.id, c]));
const RAW_SUPPORTED = ['P01_32bit_origin_TL', 'P01_32bit_origin_TR', 'P01_32bit_origin_BL', 'P01_32bit_origin_BR', 'P02_24bit_magenta_opaque', 'P10_max8x8'];
const FOOTER26 = Buffer.concat([Buffer.alloc(8), Buffer.from('TRUEVISION-XFILE.\0', 'latin1')]);
const expectedSha = (id) => sha256(Uint8Array.from(caseById.get(id).expected.rgba));

// Handwritten stub scaffolds (guard faults only, never decoder results).
const stub = (load, image) => `"use strict";\nvar Targa = class { load(input) { this.input = input; ${load} } getImageData() { ${image} } };\n`;
const zeros = (w, h) => `return { width: ${w}, height: ${h}, data: new Uint8ClampedArray(${w * h * 4}) };`;
const rawHeader = (w, h, depth = 32, flags = 8) => Buffer.from([0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, w & 255, w >> 8, h & 255, h >> 8, depth, flags]);
const rawBody = (w, h, depth = 32, flags = 8) => Buffer.concat([rawHeader(w, h, depth, flags), Buffer.alloc(w * h * (depth >> 3)), FOOTER26]);

test('effective heap is measured, not inferred from flags', () => {
  assert.ok(checkEffectiveHeap() <= 134217728, 'run this file with --max-old-space-size=125 --max-semi-space-size=1');
  failsWith(() => checkEffectiveHeap({ heap_size_limit: 335544320 }), 'effective_heap_exceeded');
  failsWith(() => checkEffectiveHeap({ heap_size_limit: 134217729 }), 'effective_heap_exceeded');
  failsWith(() => checkEffectiveHeap({}), 'effective_heap_unknown');
  failsWith(() => checkLittleEndian('BE'), 'not_little_endian');
});

test('CLI refuses default/odd argv and excess heap before any IO or write', () => {
  const before = fs.readdirSync(PREFIX).sort();
  failsWith(() => main([]), 'usage');
  failsWith(() => main(['--actual']), 'usage');
  failsWith(() => main(['--actual', '--profile', PROFILE_PATH, '--private-prefix', PREFIX, '--extra']), 'usage');
  failsWith(() => main(['--profile', PROFILE_PATH, '--actual', '--private-prefix', PREFIX]), 'usage');
  // Nonexistent paths prove the heap refusal happens before IO.
  const missing = path.join(TEST_DIR, 'missing');
  failsWith(() => main(['--actual', '--profile', `${missing}/p.json`, '--private-prefix', missing], { heapStats: { heap_size_limit: 335544320 } }), 'effective_heap_exceeded');
  assert.deepEqual(fs.readdirSync(PREFIX).sort(), before);
  assert.equal(fs.existsSync(missing), false);
});

test('frozen pins agree across fixture, profile and source', () => {
  assert.deepEqual(fixture.source_pin, { ...SOURCE_PIN });
  assert.deepEqual(fixture.source_spans, SPANS.map((s) => ({ ...s })));
  assert.deepEqual(realProfile.source_spans, SPANS.map((s) => ({ ...s })));
  assert.deepEqual(identityOf(fs.lstatSync(realSourcePath, { bigint: true })), realProfile.source.identity_decimal);
  for (const [i, t] of spanTexts.entries()) {
    const want = SPANS[i];
    assert.equal(sha256(Buffer.from(t.text, 'utf8')), want.sha256);
    assert.equal(Buffer.byteLength(t.text), want.byte_length);
    assert.deepEqual(Buffer.from(t.text), sourceHeld.bytes.subarray(want.byte_offset, want.byte_offset + want.byte_length));
  }
  assert.ok(spanTexts[2].text.includes('getDataURL(type)') && spanTexts[2].text.includes('open(path, callback)'), 'unused methods retained');
  assert.equal(SCAFFOLD, `"use strict";\nvar Targa;\n${spanTexts.map((t) => t.text).join('')}`);
});

test('real profile metadata validates completely without opening bodies', () => {
  const v = validateProfile(realProfile);
  assert.equal(v.rows.length, 25);
  assert.deepEqual(v.rows.map((r) => r.query_index), [...QUERY_INDICES]);
  assert.deepEqual(v.counts, { ...COUNTS });
  assert.equal(Math.max(...v.rows.map((r) => r.footprint.rgba_bytes)), 4194304);
  for (const r of v.rows) assert.equal(r.identity.length, 8);
  // Real rows exceed the tiny authored caps, so they can never be admitted by tests.
  failsWith(() => validateProfile(realProfile, { limits: TINY_BOUNDS }), 'over_cap');
});

test('profile schema/order/sums/header/identity mutations are rejected', () => {
  const clone = () => structuredClone(realProfile);
  const cases = {
    schema: (p) => { p.schema += 'x'; },
    extra_key: (p) => { p.extra = 1; },
    missing_key: (p) => { delete p.evidence_boundary; },
    admits_true: (p) => { p.profile_admits_execution = true; },
    row_order: (p) => { [p.rows[0], p.rows[1]] = [p.rows[1], p.rows[0]]; },
    query_domain: (p) => { p.query_indices[3] = 25; },
    rows_short: (p) => { p.rows.pop(); },
    counts_body: (p) => { p.counts.body_bytes += 1; },
    counts_rgba: (p) => { p.counts.rgba_bytes -= 4; },
    bounds: (p) => { p.bounds.per_vm_timeout_ms = 501; },
    span_sha: (p) => { p.source_spans[1].sha256 = '0'.repeat(64); },
    source_sha: (p) => { p.source.sha256 = 'f'.repeat(64); },
    source_identity_number: (p) => { p.source.identity_decimal[3] = 1792636173902459306; },
    identity_noncanonical: (p) => { p.rows[4].retained_body.identity_decimal[1] = `0${p.rows[4].retained_body.identity_decimal[1]}`; },
    identity_size: (p) => { p.rows[4].retained_body.identity_decimal[2] = '1'; },
    identity_fields: (p) => { p.identity_fields.reverse(); },
    header_width: (p) => { p.rows[2].header.width = 64; },
    header18_width: (p) => { p.rows[2].header18_hex = p.rows[2].header18_hex.slice(0, 24) + '4000' + p.rows[2].header18_hex.slice(28); },
    header18_rle: (p) => { p.rows[2].header18_hex = '00000a' + p.rows[2].header18_hex.slice(6); p.rows[2].header.image_type = 10; },
    header18_palette: (p) => { p.rows[2].header18_hex = '0001' + p.rows[2].header18_hex.slice(4); p.rows[2].header.color_map_type = 1; },
    id_length: (p) => { p.rows[2].header18_hex = '01' + p.rows[2].header18_hex.slice(2); p.rows[2].header.id_length = 1; },
    footprint: (p) => { p.rows[0].footprint.trailing_bytes = 0; },
    body_bytes: (p) => { p.rows[0].retained_body.bytes += 1; },
    footer_signature: (p) => { p.rows[0].footer26_hex = p.rows[0].footer26_hex.replace(/2e00$/, '2e01'); },
    wire_target: (p) => { p.rows[0].wire_target = '/data/texture/../x.tga'; },
    batch: (p) => { p.rows[0].source_batch = 'other'; },
    duplicate_path: (p) => { p.rows[1].retained_body.path = p.rows[0].retained_body.path; },
    basename: (p) => { p.rows[1].retained_body.path = p.rows[1].retained_body.path.replace('body-0012', 'body-0013'); },
    relative_path: (p) => { p.rows[1].retained_body.path = 'body-0012.bin'; },
  };
  for (const [name, mutate] of Object.entries(cases)) {
    const p = clone();
    mutate(p);
    assert.throws(() => validateProfile(p), (e) => e instanceof ObserverFailure, name);
  }
  assert.doesNotThrow(() => validateProfile(clone()));
});

test('span reconstruction rejects shifted pins and changed source bytes', () => {
  const bad = (k, v) => SPANS.map((s, i) => (i === 1 ? { ...s, [k]: v } : s));
  failsWith(() => extractSpans(sourceHeld.bytes, bad('byte_offset', SPANS[1].byte_offset + 1)), 'span_sha');
  failsWith(() => extractSpans(sourceHeld.bytes, bad('start_line', SPANS[1].start_line + 1)), 'span_lines');
  failsWith(() => extractSpans(sourceHeld.bytes, bad('end_line', SPANS[1].end_line - 1)), 'span_lines');
  const copy = Buffer.from(sourceHeld.bytes);
  copy[SPANS[2].byte_offset + 100] ^= 1;
  failsWith(() => extractSpans(copy), 'span_sha');
});

test('copied decoder reproduces full handwritten .020 RGBA on raw tiny cases', () => {
  for (const id of RAW_SUPPORTED) {
    const c = caseById.get(id);
    assert.equal(c.category, 'supported');
    const body = Uint8Array.from(c.bytes);
    for (const bytes of [body, Buffer.concat([body, FOOTER26])]) {
      const out = decodeInRealm(SCAFFOLD, bytes, TINY_BOUNDS, deadline());
      assert.equal(out.width, c.expected.width, id);
      assert.equal(out.height, c.expected.height, id);
      assert.equal(out.rgba_bytes, c.expected.rgba.length, id);
      assert.equal(out.rgba_sha256, expectedSha(id), id);
      assert.equal(out.rgba_last_byte, c.expected.rgba.at(-1), id);
    }
  }
});

test('channel/origin/alpha/last-byte mutations are discriminated by full hashes', () => {
  const c = caseById.get('P01_32bit_origin_TL');
  const observed = decodeInRealm(SCAFFOLD, Uint8Array.from(c.bytes), TINY_BOUNDS, deadline()).rgba_sha256;
  const rgba = c.expected.rgba;
  const swapRB = rgba.map((v, i) => (i % 4 === 0 ? rgba[i + 2] : i % 4 === 2 ? rgba[i - 2] : v));
  const alpha = rgba.map((v, i) => (i === 7 ? 255 : v));
  const last = rgba.map((v, i) => (i === rgba.length - 1 ? v ^ 1 : v));
  for (const [name, m] of Object.entries({ swapRB, alpha, last })) assert.notEqual(sha256(Uint8Array.from(m)), observed, name);
  // Origin flag change in the body (TL -> BL) changes the decoded hash.
  const flipped = Uint8Array.from(c.bytes);
  flipped[17] = 0;
  assert.equal(decodeInRealm(SCAFFOLD, flipped, TINY_BOUNDS, deadline()).rgba_sha256, expectedSha('P01_32bit_origin_BL'));
  assert.notEqual(expectedSha('P01_32bit_origin_BL'), observed);
  // The last pixel is BGRA magenta, which the decoder maps to zero; an alpha
  // change alone keeps that quirk, while a green change reaches the last byte.
  const alphaOnly = Uint8Array.from(c.bytes);
  alphaOnly[alphaOnly.length - 1] = 0x7f;
  assert.equal(decodeInRealm(SCAFFOLD, alphaOnly, TINY_BOUNDS, deadline()).rgba_sha256, observed);
  const lastPixel = Uint8Array.from(c.bytes);
  lastPixel[lastPixel.length - 3] = 0x7f;
  const out = decodeInRealm(SCAFFOLD, lastPixel, TINY_BOUNDS, deadline());
  assert.notEqual(out.rgba_sha256, observed);
  assert.notEqual(out.rgba_last_byte, rgba.at(-1));
});

test('unsupported .020 inputs are host-refused before any evaluation', () => {
  const explode = '"use strict"; throw new Error("evaluated");';
  for (const c of fixture.cases) {
    if (RAW_SUPPORTED.includes(c.id)) continue;
    assert.throws(() => decodeInRealm(explode, Uint8Array.from(c.bytes), TINY_BOUNDS, deadline()),
      (e) => e instanceof ObserverFailure && ['header_short', 'header_unsupported', 'header_dimensions', 'over_cap', 'short_pixels'].includes(e.code), c.id);
  }
});

test('direct helper enforces caps before evaluating a handwritten stub', () => {
  const spin = '"use strict"; for (;;) {}';
  const t0 = Date.now();
  failsWith(() => decodeInRealm(spin, rawBody(9, 1), TINY_BOUNDS, deadline()), 'over_cap');
  failsWith(() => decodeInRealm(spin, rawBody(1, 9), TINY_BOUNDS, deadline()), 'over_cap');
  failsWith(() => decodeInRealm(spin, Buffer.concat([rawBody(1, 1), Buffer.alloc(4096)]), TINY_BOUNDS, deadline()), 'over_cap');
  failsWith(() => decodeInRealm(spin, rawBody(1, 1), TINY_BOUNDS, deadline(), 150), 'over_cap');
  failsWith(() => decodeInRealm(spin, rawBody(1, 1), { ...TINY_BOUNDS, max_width: 2048 }, deadline()), 'bad_limits');
  failsWith(() => decodeInRealm(spin, rawBody(1025, 1), PROFILE_BOUNDS, deadline()), 'over_cap');
  failsWith(() => decodeInRealm(spin, rawHeader(1024, 1024), PROFILE_BOUNDS, deadline()), 'short_pixels');
  failsWith(() => decodeInRealm(spin, rawHeader(2, 2), TINY_BOUNDS, deadline()), 'short_pixels');
  failsWith(() => decodeInRealm(spin, rawBody(1, 1, 16), TINY_BOUNDS, deadline()), 'header_unsupported');
  failsWith(() => decodeInRealm(spin, rawBody(0, 1), TINY_BOUNDS, deadline()), 'header_dimensions');
  failsWith(() => decodeInRealm(spin, rawBody(1, 1), TINY_BOUNDS, makeDeadline(10000, (() => { let n = 0; return () => (n++ ? 1e9 : 0); })())), 'deadline_exceeded');
  assert.ok(Date.now() - t0 < 100, 'no stub evaluation ran');
  // A larger-dimension stub is allowed under profile bounds; real decoding of it is not.
  const big = decodeInRealm(stub('', zeros(16, 16)), rawBody(16, 16), PROFILE_BOUNDS, deadline());
  assert.equal(big.rgba_sha256, sha256(Buffer.alloc(1024)));
});

test('timeouts are observer failures distinct from decoder errors', () => {
  const body = rawBody(1, 1);
  const t0 = Date.now();
  assert.throws(() => decodeInRealm(stub('for (;;) {}', zeros(1, 1)), body, TINY_BOUNDS, deadline()), (e) => e.code === 'vm_timeout' && e.stage === 'decode');
  assert.throws(() => decodeInRealm('"use strict"; for (;;) {}', body, TINY_BOUNDS, deadline()), (e) => e.code === 'vm_timeout' && e.stage === 'definitions');
  assert.ok(Date.now() - t0 < 1000);
  // Remaining command deadline shortens the per-VM timeout.
  const t1 = Date.now();
  assert.throws(() => decodeInRealm(stub('for (;;) {}', zeros(1, 1)), body, TINY_BOUNDS, makeDeadline(30)), (e) => e.code === 'vm_timeout' || e.code === 'deadline_exceeded');
  assert.ok(Date.now() - t1 < 90);
  assert.throws(() => decodeInRealm(stub('throw new RangeError("bad");', zeros(1, 1)), body, TINY_BOUNDS, deadline()), (e) => e.code === 'decoder_error' && /RangeError/.test(e.message));
});

test('realm has no host globals and code generation is disabled', () => {
  const body = rawBody(1, 1);
  const noHost = stub('if (typeof process !== "undefined" || typeof require !== "undefined" || typeof Buffer !== "undefined" || typeof setTimeout !== "undefined") throw new Error("host");', zeros(1, 1));
  assert.equal(decodeInRealm(noHost, body, TINY_BOUNDS, deadline()).rgba_sha256, sha256(Buffer.alloc(4)));
  assert.throws(() => decodeInRealm(stub('(0, eval)("1");', zeros(1, 1)), body, TINY_BOUNDS, deadline()), (e) => e.code === 'decoder_error' && /EvalError/.test(e.message));
  assert.throws(() => decodeInRealm(stub('new Function("1");', zeros(1, 1)), body, TINY_BOUNDS, deadline()), (e) => e.code === 'decoder_error');
  const inputBrand = stub('if (!(input instanceof Uint8Array) || input.length !== 26 + 18 + 4 || input[16] !== 32) throw new Error("input");', zeros(1, 1));
  decodeInRealm(inputBrand, body, TINY_BOUNDS, deadline());
});

test('returned image brand/length/extent/shape mutations are rejected', () => {
  const body = rawBody(2, 1);
  const cases = {
    image_brand: 'return { width: 2, height: 1, data: new Uint8Array(8) };',
    image_length: 'return { width: 2, height: 1, data: new Uint8ClampedArray(7) };',
    image_length_extent: 'return { width: 2, height: 1, data: new Uint8ClampedArray(new ArrayBuffer(12), 0, 8) };',
    image_length_offset: 'return { width: 2, height: 1, data: new Uint8ClampedArray(new ArrayBuffer(12), 4, 8) };',
    image_length_shared: 'return { width: 2, height: 1, data: new Uint8ClampedArray(new SharedArrayBuffer(8)) };',
    image_dimensions: 'return { width: 1, height: 2, data: new Uint8ClampedArray(8) };',
    image_shape_accessor: 'return { get width() { return 2; }, height: 1, data: new Uint8ClampedArray(8) };',
    image_shape_extra: 'return { width: 2, height: 1, data: new Uint8ClampedArray(8), extra: 1 };',
    image_shape_proxy: 'return new Proxy({ width: 2, height: 1, data: new Uint8ClampedArray(8) }, {});',
    image_brand_proxy: 'return { width: 2, height: 1, data: new Proxy(new Uint8ClampedArray(8), {}) };',
    image_shape_null: 'return null;',
  };
  for (const [name, image] of Object.entries(cases)) {
    const code = name.replace(/^(image_[a-z]+).*$/, '$1');
    assert.throws(() => decodeInRealm(stub('', image), body, TINY_BOUNDS, deadline()), (e) => e instanceof ObserverFailure && e.code === code, name);
  }
  const lastByte = decodeInRealm(stub('', 'const d = new Uint8ClampedArray(8); d[7] = 1; return { width: 2, height: 1, data: d };'), body, TINY_BOUNDS, deadline());
  assert.notEqual(lastByte.rgba_sha256, sha256(Buffer.alloc(8)));
  assert.equal(lastByte.rgba_last_byte, 1);
});

test('held reads reject short/extra/symlink/hardlink/identity/content faults', () => {
  const d = freshDir('held');
  const f = writeOwned(path.join(d, 'a.bin'), Buffer.from('abcdef'));
  const pin = pinOf(f);
  const id = identityOf(fs.lstatSync(f, { bigint: true }));
  const ok = readHeldInput(f, { ...pin, identity: id }, 4096, deadline(), 't');
  assert.equal(ok.bytes.toString(), 'abcdef');
  ok.recheck('use');
  ok.close();
  failsWith(() => readHeldInput(f, { ...pin, bytes: 7 }, 4096, deadline(), 't'), 'size_mismatch');
  failsWith(() => readHeldInput(f, { ...pin, bytes: 5 }, 4096, deadline(), 't'), 'size_mismatch');
  failsWith(() => readHeldInput(f, { ...pin, sha256: '0'.repeat(64) }, 4096, deadline(), 't'), 'sha_mismatch');
  failsWith(() => readHeldInput(f, pin, 5, deadline(), 't'), 'input_over_cap');
  failsWith(() => readHeldInput(`${d}/./a.bin`, pin, 4096, deadline(), 't'), 'bad_path');
  failsWith(() => readHeldInput(d, pin, 4096, deadline(), 't'), 'not_regular');
  fs.symlinkSync(f, path.join(d, 'link.bin'));
  failsWith(() => readHeldInput(path.join(d, 'link.bin'), pin, 4096, deadline(), 't'), 'symlink');
  // Nanosecond-only identity change is caught losslessly.
  const nsOff = [...id];
  nsOff[3] = (BigInt(id[3]) + 1n).toString();
  failsWith(() => readHeldInput(f, { ...pin, identity: nsOff }, 4096, deadline(), 't'), 'identity_mismatch');
  // Identity change after read is caught at final use.
  const held = readHeldInput(f, { ...pin, identity: id }, 4096, deadline(), 't');
  fs.utimesSync(f, new Date(2001, 1, 1), new Date(2001, 1, 1));
  failsWith(() => held.recheck('final_use'), 'identity_changed');
  held.close();
  failsWith(() => readHeldInput(f, { ...pin, identity: id }, 4096, deadline(), 't'), 'identity_mismatch');
  // Same-size content change.
  const g = writeOwned(path.join(d, 'b.bin'), Buffer.from('abcdef'));
  const gpin = pinOf(g);
  fs.writeFileSync(g, 'abcdeg');
  failsWith(() => readHeldInput(g, gpin, 4096, deadline(), 't'), 'sha_mismatch');
  fs.linkSync(g, path.join(d, 'hard.bin'));
  failsWith(() => readHeldInput(g, { bytes: 6, sha256: sha256(Buffer.from('abcdeg')) }, 4096, deadline(), 't'), 'link_count');
});

// ---------------------------------------------------------------- authored 25-row run

function authoredProfile(dir, edit = () => {}) {
  const rows = QUERY_INDICES.map((q, i) => {
    const id = RAW_SUPPORTED[i % RAW_SUPPORTED.length];
    const bytes = Buffer.concat([Buffer.from(caseById.get(id).bytes), FOOTER26]);
    const file = writeOwned(path.join(dir, `body-${String(q).padStart(4, '0')}.bin`), bytes);
    const h = bytes.subarray(0, 18);
    const u16 = (o) => h[o] | (h[o + 1] << 8);
    const header = { id_length: 0, color_map_type: 0, image_type: 2, color_map_index: 0, color_map_length: 0, color_map_depth: 0, x_origin: u16(8), y_origin: u16(10), width: u16(12), height: u16(14), pixel_depth: h[16], flags: h[17] };
    const pixels = header.width * header.height;
    const raw = pixels * (header.pixel_depth >> 3);
    return {
      caseId: id,
      row: {
        query_index: q, wire_target: `/data/texture/authored/case_${q}.tga`, source_batch: i % 2 ? 'remainder' : 'pilot',
        retained_body: { path: file, bytes: bytes.length, sha256: sha256(bytes), identity_decimal: identityOf(fs.lstatSync(file, { bigint: true })) },
        header18_hex: h.toString('hex'), header,
        footprint: { pixels, raw_pixel_bytes: raw, rgba_bytes: pixels * 4, header_plus_id_palette_bytes: 18, raw_expected_end: 18 + raw, trailing_bytes: 26 },
        footer26_hex: FOOTER26.toString('hex'),
      },
    };
  });
  const profile = structuredClone(realProfile);
  profile.rows = rows.map((r) => r.row);
  profile.counts = { queries: 25, body_bytes: rows.reduce((a, r) => a + r.row.retained_body.bytes, 0), rgba_bytes: rows.reduce((a, r) => a + r.row.footprint.rgba_bytes, 0) };
  edit(profile, dir);
  const file = writeOwned(path.join(dir, 'PROFILE_AUTHORED.json'), `${JSON.stringify(profile, null, 1)}\n`);
  return { file, pins: { profile: pinOf(file), counts: profile.counts }, cases: rows.map((r) => r.caseId) };
}
const runAuthored = (a, extra = {}) => runObserver({ profilePath: a.file, prefix: extra.prefix ?? path.dirname(a.file), pins: a.pins, limits: TINY_BOUNDS, ...extra });

test('authored 25-row run publishes PASS with exact hashes, pins and private modes', () => {
  const d = freshDir('pass');
  const a = authoredProfile(d);
  const out = runAuthored(a);
  assert.equal(out.status, 'PASS', JSON.stringify(out));
  assert.equal(fs.statSync(out.dir).mode & 0o777, 0o700);
  const resultPath = path.join(out.dir, 'result.json');
  assert.equal(fs.statSync(resultPath).mode & 0o777, 0o600);
  const text = fs.readFileSync(resultPath);
  assert.equal(sha256(text), out.result.sha256);
  assert.ok(text.length <= PROFILE_BOUNDS.max_result_bytes);
  const r = JSON.parse(text);
  assert.equal(r.status, 'PASS');
  assert.equal(r.rows.length, 25);
  assert.deepEqual(r.rows.map((x) => x.query_index), [...QUERY_INDICES]);
  r.rows.forEach((row, i) => {
    const c = caseById.get(a.cases[i]);
    assert.equal(row.rgba_sha256, expectedSha(a.cases[i]), row.query_index);
    assert.equal(row.width, c.expected.width);
    assert.equal(row.rgba_bytes, c.expected.rgba.length);
    assert.equal(row.body.identity_post_matches, true);
  });
  assert.deepEqual(r.spans, SPANS.map((s) => ({ ...s })));
  assert.equal(r.source.sha256, SOURCE_PIN.sha256);
  assert.equal(r.profile.sha256, a.pins.profile.sha256);
  assert.equal(r.scaffold.sha256, sha256(SCAFFOLD));
  assert.equal(sha256(fs.readFileSync(path.join(out.dir, 'scaffold.js'))), sha256(SCAFFOLD));
  assert.ok(!JSON.stringify(r).includes('"rgba":'), 'no pixel arrays published');
});

test('every command-deadline point fails without publishing a PASS', () => {
  const d = freshDir('deadline');
  const a = authoredProfile(d);
  let calls = 0;
  const counted = runAuthored(a, { clock: () => { calls++; return 0; } });
  assert.equal(counted.status, 'PASS');
  const total = calls;
  const points = new Set([1, 2, 3, 5, 8, Math.floor(total / 2), total - 3, total - 2]);
  for (const k of points) {
    let n = 0;
    const out = runAuthored(a, { clock: () => (++n > k ? 20000 : 0) });
    assert.equal(out.status, 'FAIL', `k=${k}/${total}`);
    assert.equal(out.code, 'deadline_exceeded', `k=${k}`);
    assert.equal(fs.existsSync(path.join(out.dir, 'result.json')), false, `k=${k}`);
    const f = JSON.parse(fs.readFileSync(path.join(out.dir, 'failure.json')));
    assert.equal(f.timeout, true);
  }
  // Expiry at the terminal elapsed reading must also invalidate publication.
  let m = 0;
  assert.equal(runAuthored(a, { clock: () => (++m > total - 1 ? 20000 : 0) }).status, 'FAIL');
  // The earlier PASS directory is untouched by later failures.
  assert.equal(sha256(fs.readFileSync(path.join(counted.dir, 'result.json'))), counted.result.sha256);
});

test('body/profile pin faults fail with preserved evidence and no stale PASS', () => {
  const failing = (name, edit, code, after = () => {}) => {
    const d = freshDir(name);
    const a = authoredProfile(d, edit);
    after(d, a);
    const out = runAuthored(a);
    assert.equal(out.status, 'FAIL', name);
    assert.equal(out.code, code, `${name}: ${JSON.stringify(out)}`);
    assert.equal(fs.existsSync(path.join(out.dir, 'result.json')), false);
    return JSON.parse(fs.readFileSync(path.join(out.dir, 'failure.json')));
  };
  const f1 = failing('identity', (p) => { p.rows[3].retained_body.identity_decimal[1] = '1'; }, 'identity_mismatch');
  assert.equal(f1.completed_rows.length, 3);
  assert.equal(f1.stage, 'row_24');
  // Rewriting content also changes mtime/ctime, so identity fails first.
  failing('content', () => {}, 'identity_mismatch', (d) => { const f = path.join(d, 'body-0036.bin'); const b = fs.readFileSync(f); b[20] ^= 1; fs.writeFileSync(f, b); });
  failing('body_sha_pin', (p) => { p.rows[4].retained_body.sha256 = '0'.repeat(64); }, 'sha_mismatch');
  failing('header18', (p) => {
    const r = p.rows[5];
    const body = fs.readFileSync(r.retained_body.path);
    body[17] ^= 0x10; // origin flag differs from the profile's header18
    fs.rmSync(r.retained_body.path);
    writeOwned(r.retained_body.path, body);
    r.retained_body.sha256 = sha256(body);
    r.retained_body.identity_decimal = identityOf(fs.lstatSync(r.retained_body.path, { bigint: true }));
  }, 'header18_mismatch');
  failing('footer26', (p) => {
    const r = p.rows[6];
    const body = fs.readFileSync(r.retained_body.path);
    body[body.length - 2] = 0x21;
    fs.rmSync(r.retained_body.path);
    writeOwned(r.retained_body.path, body);
    r.retained_body.sha256 = sha256(body);
    r.retained_body.identity_decimal = identityOf(fs.lstatSync(r.retained_body.path, { bigint: true }));
  }, 'footer26_mismatch');
  failing('symlink_body', () => {}, 'symlink', (d) => {
    const f = path.join(d, 'body-0040.bin');
    fs.renameSync(f, path.join(d, 'moved.bin'));
    fs.symlinkSync(path.join(d, 'moved.bin'), f);
  });
  const f2 = failing('profile_bytes', () => {}, 'sha_mismatch', (d, a) => { const b = fs.readFileSync(a.file); b[b.length - 2] = 0x20; fs.writeFileSync(a.file, b); });
  assert.equal(f2.stage, 'profile');
  assert.equal(f2.completed_rows.length, 0);
  failing('schema', (p) => { p.rows.reverse(); }, 'profile_schema');
  failing('sums', (p) => { p.counts.rgba_bytes += 4; }, 'profile_schema');
});

test('run directory prefix must be a real private directory', () => {
  const d = freshDir('prefix');
  const a = authoredProfile(d);
  const link = path.join(TEST_DIR, `${seq}-link`);
  fs.symlinkSync(d, link);
  failsWith(() => runAuthored(a, { prefix: link }), 'bad_prefix');
  const open = freshDir('open');
  fs.chmodSync(open, 0o755);
  failsWith(() => runAuthored(a, { prefix: open }), 'bad_prefix');
  failsWith(() => runAuthored(a, { prefix: `${d}/` }), 'bad_prefix');
  failsWith(() => runAuthored(a, { heapStats: { heap_size_limit: 335544320 } }), 'effective_heap_exceeded');
});


// Root regressions for the independently reproduced lifecycle holds.
test('candidate replacement after close fails without publishing', () => {
  const a = authoredProfile(freshDir('candidate-replacement'));
  const open = fs.openSync, close = fs.closeSync;
  let fdTarget, candidatePath, changed = false;
  fs.openSync = function(file, ...args) {
    const fd = open.call(this, file, ...args);
    if (typeof file === 'string' && file.endsWith('/result.candidate.json')) { fdTarget = fd; candidatePath = file; }
    return fd;
  };
  fs.closeSync = function(fd) {
    const result = close.call(this, fd);
    if (fd === fdTarget && !changed) {
      changed = true;
      fs.renameSync(candidatePath, candidatePath + '.original');
      writeOwned(candidatePath, '{}\n');
    }
    return result;
  };
  let out;
  try { out = runAuthored(a); } finally { fs.openSync = open; fs.closeSync = close; }
  assert.ok(changed);
  assert.equal(out.status, 'FAIL');
  assert.equal(out.code, 'output_identity');
  assert.equal(fs.existsSync(path.join(out.dir, 'result.json')), false);
});

test('input close failure is sticky and remaining source close is attempted', () => {
  const a = authoredProfile(freshDir('sticky-close'));
  const open = fs.openSync, close = fs.closeSync;
  let profileFd, sourceFd, profileClosed = false, sourceClosed = false;
  fs.openSync = function(file, ...args) {
    const fd = open.call(this, file, ...args);
    if (file === a.file) profileFd = fd;
    if (file === realSourcePath) sourceFd = fd;
    return fd;
  };
  fs.closeSync = function(fd) {
    const result = close.call(this, fd);
    if (fd === profileFd && !profileClosed) { profileClosed = true; throw Object.assign(new Error('owned close fault'), { code: 'EIO' }); }
    if (fd === sourceFd) sourceClosed = true;
    return result;
  };
  let out;
  try { out = runAuthored(a); } finally { fs.openSync = open; fs.closeSync = close; }
  assert.ok(profileClosed && sourceClosed);
  assert.equal(out.status, 'FAIL');
  assert.equal(out.code, 'cleanup_failed');
  assert.equal(fs.existsSync(path.join(out.dir, 'result.json')), false);
});

test('symlinked input ancestor is refused before reading its owned leaf', () => {
  const d = freshDir('ancestor'), real = path.join(d, 'real'), alias = path.join(d, 'alias');
  fs.mkdirSync(real, { mode: 0o700 });
  const file = writeOwned(path.join(real, 'leaf'), 'abcdef');
  fs.symlinkSync(real, alias);
  failsWith(() => readHeldInput(path.join(alias, 'leaf'), pinOf(file), 4096, deadline(), 'ancestor'), 'input_ancestor');
});

test('fresh run directory replacement is refused before first output', () => {
  const a = authoredProfile(freshDir('run-directory-replacement'));
  const mkdir = fs.mkdirSync, open = fs.openSync;
  let runDir, changed = false;
  fs.mkdirSync = function(file, ...args) {
    const result = mkdir.call(this, file, ...args);
    if (typeof file === 'string' && path.basename(file).startsWith('run-')) runDir = file;
    return result;
  };
  fs.openSync = function(file, ...args) {
    if (file === realSourcePath && !changed) {
      assert.ok(runDir);
      fs.renameSync(runDir, runDir + '.original');
      mkdir(runDir, { mode: 0o700 });
      changed = true;
    }
    return open.call(this, file, ...args);
  };
  let out;
  try { out = runAuthored(a); } finally { fs.mkdirSync = mkdir; fs.openSync = open; }
  assert.ok(changed);
  assert.equal(out.status, 'FAIL');
  assert.equal(out.code, 'input_ancestor');
  assert.equal(fs.existsSync(path.join(runDir, 'scaffold.js')), false);
  assert.equal(fs.existsSync(runDir + '.original'), true);
});
