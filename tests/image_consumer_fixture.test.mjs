// T07.007.014.016 authored controls for the image-consumer fixture builder and
// the pure parts of its browser driver. Synthetic sources/doubles only, plus
// optional byte-level checks of the saved .014 source when both env paths are
// given. Nothing here decodes images, renders, uses GL or certifies browser,
// native or GPU behaviour; Root drives the generated page in the Orca browser.
//
//   node --test tests/image_consumer_fixture.test.mjs
//   IMAGE_CONSUMER_SOURCE=<abs Online.js> IMAGE_CONSUMER_METADATA=<abs OUTPUT_PINS.json> \
//     node --test tests/image_consumer_fixture.test.mjs
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import {
  DEFAULT_PROFILE, DRIVER_PATH, LIMITS, Refusal, assembleProduction, authorFixtures, buildFixture, checkFixtureLimits,
  parseArgs, publish, verifyMetadata, verifySource
} from '../tools/renewal/build_image_consumer_fixture.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const BUILDER = path.join(ROOT, 'tools/renewal/build_image_consumer_fixture.mjs');
const PRIVATE = path.join(ROOT, '.tools/renewal/t07-014-016-claude-followup-1/test-runs');
const sha = (b) => createHash('sha256').update(b).digest('hex');
const driver = createRequire(import.meta.url)(DRIVER_PATH);

fs.mkdirSync(PRIVATE, { recursive: true, mode: 0o700 });
const RUNS = fs.realpathSync(fs.mkdtempSync(path.join(PRIVATE, 'run-')));
let seq = 0;
const freshDir = () => { const d = path.join(RUNS, `d${seq++}`); fs.mkdirSync(d, { mode: 0o700 }); return d; };
const refusal = (code) => (e) => e instanceof Refusal && e.code === code;

// ---- Synthetic source with the same slice ids and checked S09 assignments ----
const SLICE_TEXT = {
  S01_esmMin: 'var __esmMin = (fn, res) => () => (fn && (res = fn(fn = 0)), res);\n};\n',
  S02_Configs_region: '//#region src/Core/Configs.js\nvar Configs;\n//#endregion\n',
  S03_Targa_region: '//#region src/Loaders/Targa.js\nvar Targa;\n//#endregion\n',
  S04_libgif_region: '//#region src/Vendors/libgif.js\nvar SuperGif;\n\t\t\t\tif (!initialized) init();\n//#endregion\n',
  S05_Texture_region: '//#region src/Utils/Texture.js\nvar Texture, procCanvas$3;\n//#endregion\n',
  S06_WebGL_region: '//#region src/Utils/WebGL.js\nvar WebGL_default;\n//#endregion\n',
  S07_Ground_initTextures: 'function initTextures(gl, textures) {\n\treturn textures;\n}\n',
  S08_Ground_onTextureAtlasComplete: 'function onTextureAtlasComplete(gl, atlas) {\n\treturn atlas;\n}\n',
  S09_Ground_vars_and_init_REFERENCE: [
    'var procCanvas$2, procCtx$2, _program$28, _buffer$21, _lightmap, _tileColor, _textureAtlas, more;',
    'var init_Ground = __esmMin((() => {', ...DEFAULT_PROFILE.groundAssignments, '}));', ''
  ].join('\n')
};
function synthetic(sliceText = SLICE_TEXT) {
  const parts = ['// synthetic header\n'];
  const slices = [];
  let offset = parts[0].length;
  let line = 2;
  for (const pin of DEFAULT_PROFILE.slices) {
    const filler = `// filler before ${pin.slice}\n`;
    parts.push(filler); offset += filler.length; line += 1;
    const text = sliceText[pin.slice];
    const lines = text.split('\n').length - 1;
    const all = text.slice(0, -1).split('\n');
    slices.push({ ...pin, lf_start: line, lf_end: line + lines - 1, byte_offset: offset, byte_length: Buffer.byteLength(text), sha256: sha(Buffer.from(text)), first: all[0], last: all[all.length - 1] });
    parts.push(text); offset += Buffer.byteLength(text); line += lines;
  }
  parts.push('// synthetic trailer\n');
  const src = Buffer.from(parts.join(''));
  const driverBytes = fs.readFileSync(DRIVER_PATH);
  const profile = {
    ...DEFAULT_PROFILE, slices,
    source: { bytes: src.length, sha256: sha(src) },
    driver: { bytes: driverBytes.length, sha256: sha(driverBytes) }
  };
  const meta = Buffer.from(JSON.stringify({ slices }));
  profile.metadata = { bytes: meta.length, sha256: sha(meta) };
  const dir = freshDir();
  const sourcePath = path.join(dir, 'Online.js');
  const metadataPath = path.join(dir, 'OUTPUT_PINS.json');
  fs.writeFileSync(sourcePath, src, { mode: 0o600 });
  fs.writeFileSync(metadataPath, meta, { mode: 0o600 });
  return { src, meta, profile, sourcePath, metadataPath };
}
const outIn = () => path.join(freshDir(), 'fixture');

test('fresh publication: closed manifest, exact files/modes, byte-identical production spans', () => {
  const s = synthetic();
  const outPath = outIn();
  const { manifest } = buildFixture({ sourcePath: s.sourcePath, metadataPath: s.metadataPath, outPath }, s.profile);
  const names = fs.readdirSync(outPath).sort();
  assert.deepEqual(names, ['MANIFEST.json', 'driver.js', 'fixtures.js', 'index.html', 'production.js', 'realm.html']);
  assert.equal(fs.statSync(outPath).mode & 0o777, 0o700);
  const disk = JSON.parse(fs.readFileSync(path.join(outPath, 'MANIFEST.json')));
  assert.deepEqual(disk.files.map((f) => f.name).sort(), names.filter((n) => n !== 'MANIFEST.json'));
  for (const f of disk.files) {
    const b = fs.readFileSync(path.join(outPath, f.name));
    assert.equal(b.length, f.bytes); assert.equal(sha(b), f.sha256);
    assert.equal(fs.statSync(path.join(outPath, f.name)).mode & 0o777, 0o600);
  }
  const prod = fs.readFileSync(path.join(outPath, 'production.js'));
  let at = 0;
  for (const span of disk.production.spans) {
    assert.equal(span.offset, at, 'spans are contiguous');
    const got = prod.subarray(span.offset, span.offset + span.length);
    assert.equal(sha(got), span.sha256);
    if (span.kind === 'production') assert.ok(got.equals(s.src.subarray(span.source_offset, span.source_offset + span.length)), span.id);
    at += span.length;
  }
  assert.equal(at, prod.length, 'spans cover production.js exactly');
  assert.deepEqual(disk.production.spans.filter((x) => x.kind === 'production').map((x) => x.id), DEFAULT_PROFILE.slices.filter((x) => x.use === 'exec').map((x) => x.slice));
  const assign = disk.production.spans.find((x) => x.id === 'S09_checked_ground_assignments');
  assert.equal(prod.subarray(assign.offset, assign.offset + assign.length).toString(), DEFAULT_PROFILE.groundAssignments.join('\n') + '\n');
  assert.deepEqual(disk.inputs.pre, disk.inputs.post);
  assert.equal(disk.inputs.metadata_rows_checked, 9);
  assert.ok(fs.readFileSync(path.join(outPath, 'driver.js')).equals(fs.readFileSync(DRIVER_PATH)));
  assert.equal(manifest.production.sha256, sha(prod));
});

test('existing output, wrong whole source, slice tamper, driver tamper and metadata mismatch refuse before publication', () => {
  const s = synthetic();
  const existing = freshDir();
  fs.writeFileSync(path.join(existing, 'keep'), 'x');
  assert.throws(() => buildFixture({ sourcePath: s.sourcePath, outPath: existing }, s.profile), refusal('output_exists'));
  assert.deepEqual(fs.readdirSync(existing), ['keep']);
  const empty = freshDir();
  assert.throws(() => buildFixture({ sourcePath: s.sourcePath, outPath: empty }, s.profile), refusal('output_exists'));

  const tryBuild = (profile, code, extra = {}) => {
    const outPath = outIn();
    assert.throws(() => buildFixture({ sourcePath: s.sourcePath, outPath, ...extra }, profile), refusal(code));
    assert.equal(fs.existsSync(outPath), false, `${code} must not publish`);
  };
  const flipped = Buffer.from(s.src); flipped[3] ^= 1;
  const flippedPath = path.join(path.dirname(s.sourcePath), 'Flipped.js');
  fs.writeFileSync(flippedPath, flipped);
  assert.throws(() => buildFixture({ sourcePath: flippedPath, outPath: outIn() }, s.profile), refusal('source_pin_mismatch'));
  const withSlice = (i, patch) => ({ ...s.profile, slices: s.profile.slices.map((p, j) => (j === i ? { ...p, ...patch } : p)) });
  tryBuild(withSlice(4, { sha256: '0'.repeat(64) }), 'slice_sha_mismatch');
  tryBuild(withSlice(4, { byte_offset: s.profile.slices[4].byte_offset + 1 }), 'slice_not_line_start');
  tryBuild(withSlice(4, { lf_start: s.profile.slices[4].lf_start + 1 }), 'slice_lf_mismatch');
  tryBuild(withSlice(4, { byte_length: s.profile.slices[4].byte_length - 1 }), 'slice_not_lf_terminated');
  tryBuild(withSlice(6, { last: '};' }), 'slice_boundary_text_mismatch');
  tryBuild({ ...s.profile, driver: { ...s.profile.driver, sha256: '1'.repeat(64) } }, 'driver_pin_mismatch');
  const tamperedDriver = path.join(path.dirname(s.sourcePath), 'driver.js');
  fs.writeFileSync(tamperedDriver, Buffer.concat([fs.readFileSync(DRIVER_PATH), Buffer.from('//')]));
  tryBuild(s.profile, 'driver_pin_mismatch', { driverPath: tamperedDriver });
  tryBuild({ ...s.profile, metadata: { ...s.profile.metadata, bytes: 1 } }, 'metadata_pin_mismatch', { metadataPath: s.metadataPath });
  const badMeta = Buffer.from(JSON.stringify({ slices: s.profile.slices.map((p, j) => (j === 2 ? { ...p, byte_length: 1 } : p)) }));
  assert.throws(() => verifyMetadata(badMeta, { ...s.profile, metadata: { bytes: badMeta.length, sha256: sha(badMeta) } }), refusal('metadata_row_mismatch'));
});

test('unexpected scope refuses: arguments, paths, slice set, S09 assignment, forbidden initializer', () => {
  const s = synthetic();
  assert.throws(() => parseArgs(['--source', '/a', '--out', '/b', '--serve', '1']), refusal('unexpected_argument'));
  assert.throws(() => parseArgs(['--source', '/a']), refusal('missing_argument'));
  assert.throws(() => parseArgs(['--source', '/a', '--source', '/c', '--out', '/b']), refusal('unexpected_argument'));
  assert.throws(() => buildFixture({ sourcePath: s.sourcePath, outPath: 'relative/out' }, s.profile), refusal('path_not_absolute_normal'));
  assert.throws(() => buildFixture({ sourcePath: s.sourcePath, outPath: path.join(path.dirname(s.sourcePath), 'out') }, s.profile), refusal('output_inside_input_directory'));
  assert.throws(() => buildFixture({ sourcePath: s.sourcePath, outPath: path.join(RUNS, 'missing-parent', 'out') }, s.profile), refusal('output_parent_missing'));
  assert.throws(() => verifySource(s.src, { ...s.profile, slices: s.profile.slices.filter((p) => p.slice !== 'S04_libgif_region') }), refusal('unexpected_slice_scope'));
  const noAssign = synthetic({ ...SLICE_TEXT, S09_Ground_vars_and_init_REFERENCE: SLICE_TEXT.S09_Ground_vars_and_init_REFERENCE.replace('\t_textureAtlas = null;\n', '') });
  assert.throws(() => verifySource(noAssign.src, noAssign.profile), refusal('ground_assignment_not_in_S09'));
  const swapped = synthetic({ ...SLICE_TEXT, S09_Ground_vars_and_init_REFERENCE: SLICE_TEXT.S09_Ground_vars_and_init_REFERENCE.replace(DEFAULT_PROFILE.groundAssignments[0] + '\n', '').replace('}));', DEFAULT_PROFILE.groundAssignments[0] + '\n}));') });
  assert.throws(() => verifySource(swapped.src, swapped.profile), refusal('ground_assignment_not_in_S09'));
  const forbidden = synthetic({ ...SLICE_TEXT, S07_Ground_initTextures: 'function initTextures(gl, textures) {\n\tinit_Ground();\n}\n' });
  assert.throws(() => assembleProduction(verifySource(forbidden.src, forbidden.profile), forbidden.profile), refusal('forbidden_initializer_in_fixture'));
  const topInit = synthetic({ ...SLICE_TEXT, S06_WebGL_region: '//#region src/Utils/WebGL.js\ninit();\n//#endregion\n' });
  assert.throws(() => assembleProduction(verifySource(topInit.src, topInit.profile), topInit.profile), refusal('forbidden_initializer_in_fixture'));
});

test('publication failure removes only its own created paths', () => {
  const parent = freshDir();
  fs.writeFileSync(path.join(parent, 'sibling'), 'keep');
  const outPath = path.join(parent, 'fixture');
  assert.throws(() => publish(outPath, new Map([['a.txt', Buffer.from('a')], ['missing-dir/b.txt', Buffer.from('b')]])), /ENOENT/);
  assert.deepEqual(fs.readdirSync(parent), ['sibling']);
  assert.equal(fs.readFileSync(path.join(parent, 'sibling'), 'utf8'), 'keep');
  fs.mkdirSync(outPath);
  assert.throws(() => publish(outPath, new Map([['a.txt', Buffer.from('a')]])), /EEXIST/);
  assert.deepEqual(fs.readdirSync(outPath), [], 'pre-existing directory is not removed or written');
});

test('CLI refuses wrong source pin with a JSON refusal and no output', () => {
  const s = synthetic();
  const outPath = outIn();
  const r = spawnSync(process.execPath, [BUILDER, '--source', s.sourcePath, '--out', outPath], { encoding: 'utf8' });
  assert.equal(r.status, 2);
  assert.equal(JSON.parse(r.stderr).code, 'source_pin_mismatch');
  assert.equal(fs.existsSync(outPath), false);
});

// ---- Authored fixture limits and independently specified expectations ----
function parseBmp(b) {
  assert.equal(b.toString('latin1', 0, 2), 'BM');
  const off = b.readUInt32LE(10), w = b.readInt32LE(18), h = b.readInt32LE(22);
  assert.equal(b.readUInt32LE(14), 40); assert.equal(b.readUInt16LE(28), 24); assert.equal(b.readUInt32LE(30), 0);
  assert.equal(b.readUInt32LE(2), b.length);
  const stride = Math.ceil(w * 3 / 4) * 4;
  const px = (x, y) => { const at = off + (h - 1 - y) * stride + x * 3; return [b[at + 2], b[at + 1], b[at], 255]; };
  return { w, h, px };
}
function jpegInfo(b) {
  assert.equal(b.readUInt16BE(0), 0xffd8); assert.equal(b.readUInt16BE(b.length - 2), 0xffd9);
  const markers = [];
  let i = 2, sof = null;
  while (i < b.length) {
    assert.equal(b[i], 0xff);
    const m = b[i + 1]; markers.push(m);
    const len = b.readUInt16BE(i + 2);
    if (m === 0xc0) sof = { precision: b[i + 4], h: b.readUInt16BE(i + 5), w: b.readUInt16BE(i + 7), comps: b[i + 9], sampling: [b[i + 11], b[i + 14], b[i + 17]] };
    if (m === 0xda) break;
    i += 2 + len;
  }
  return { markers, sof };
}

test('authored images are tiny, supported BMP/JPEG variants and match their declared expectations', () => {
  const f = authorFixtures();
  assert.ok(checkFixtureLimits(f));
  const byId = Object.fromEntries(f.images.map((im) => [im.id, Buffer.from(im.base64, 'base64')]));
  for (const im of f.images) {
    assert.ok(byId[im.id].length <= 4096 && byId[im.id].length === im.bytes && sha(byId[im.id]) === im.sha256, im.id);
  }
  for (const id of ['bmp_quadrant_2x2', 'bmp_magenta_4x1', 'bmp_npot_3x5']) {
    const im = f.images.find((x) => x.id === id);
    const bmp = parseBmp(byId[id]);
    assert.deepEqual([bmp.w, bmp.h], [im.width, im.height]);
    assert.ok(bmp.w <= LIMITS.maxDimension && bmp.h <= LIMITS.maxDimension);
  }
  const jpg = jpegInfo(byId.jpeg_solid_8x8);
  assert.deepEqual(jpg.sof, { precision: 8, h: 8, w: 8, comps: 3, sampling: [0x11, 0x11, 0x11] });
  assert.ok(!jpg.markers.some((m) => m >= 0xc1 && m <= 0xcf && m !== 0xc4 && m !== 0xc8 && m !== 0xcc), 'baseline only');
  const ctl = Object.fromEntries(f.controls.map((c) => [c.id, c]));
  // Completion expectations for non-magenta BMPs equal the authored pixels.
  for (const [id, img] of [['C1a-bmp-quadrant', 'bmp_quadrant_2x2'], ['C3-npot-resize', 'bmp_npot_3x5']]) {
    const bmp = parseBmp(byId[img]);
    for (const p of ctl[id].expect.completion.pixels) assert.deepEqual(p.rgba, bmp.px(p.x, p.y), `${id} ${p.x},${p.y}`);
    assert.equal(ctl[id].expect.completion.pixels.length, bmp.w * bmp.h);
  }
  // Brief's literal magenta threshold cases.
  const mag = parseBmp(byId.bmp_magenta_4x1);
  assert.deepEqual([0, 1, 2, 3].map((x) => mag.px(x, 0).slice(0, 3)), [[255, 0, 255], [231, 19, 231], [230, 0, 255], [255, 20, 255]]);
  const mc = ctl['C2-magenta-threshold'].expect;
  assert.deepEqual(mc.completion.pixels.map((p) => p.rgba), [[0, 0, 0, 0], [0, 0, 0, 0], [230, 0, 255, 255], [255, 20, 255, 255]]);
  assert.deepEqual(mc.preMagenta.pixels.map((p) => p.rgba), [0, 1, 2, 3].map((x) => mag.px(x, 0)));
  assert.deepEqual(mc.water.pixels.map((p) => p.rgba), mc.completion.pixels.map((p) => p.rgba));
  // JPEG: JFIF conversion of the authored Y/Cb/Cr with explicit tolerance 6.
  const [Y, Cb, Cr] = [96, 128, 200];
  const jfif = [Y + 1.402 * (Cr - 128), Y - 0.344136 * (Cb - 128) - 0.714136 * (Cr - 128), Y + 1.772 * (Cb - 128)].map(Math.round);
  for (const p of ctl['C1b-jpeg-solid'].expect.completion.pixels) { assert.deepEqual(p.rgba, [...jfif, 255]); assert.equal(p.tol, 6); }
});

test('control matrix is finite, complete and uses fixed POT/atlas expectations with discriminating probes', () => {
  const f = authorFixtures();
  assert.deepEqual(f.controls.map((c) => c.id), ['C1a-bmp-quadrant', 'C1b-jpeg-solid', 'C2-magenta-threshold', 'C3-npot-resize', 'C4-null-input',
    'C5-malformed-timeout', 'C6a-native-lose-context', 'C6b-observer-injected-gl-error', 'C7-closed-late-completion', 'C8a-mipmap-false', 'C8b-mipmap-true', 'C8c-worker-blob-url']);
  for (const c of f.controls) assert.deepEqual(c.consumers, ['ground', 'water']);
  const ctl = Object.fromEntries(f.controls.map((c) => [c.id, c]));
  assert.ok(ctl['C5-malformed-timeout'].timeoutMs <= 2000 && ctl['C7-closed-late-completion'].lateWindowMs <= 2000);
  assert.equal(ctl['C4-null-input'].image, null);
  assert.equal(ctl['C4-null-input'].expect.water, null);
  assert.equal(ctl['C8c-worker-blob-url'].url, 'worker');
  assert.deepEqual([ctl['C8a-mipmap-false'].enableMipmap, ctl['C8b-mipmap-true'].enableMipmap], [false, true]);
  for (const c of f.controls) if (c.expect && c.expect.ground) assert.deepEqual(c.expect.ground.upload, { width: 512, height: 512 });
  const npot = ctl['C3-npot-resize'].expect;
  assert.deepEqual(npot.water.upload, { width: 4, height: 8 });
  const at = (list, x, y) => list.find((p) => p.x === x && p.y === y);
  // Water: far corner exists only after a 4x8 stretch, and carries the BR source color.
  assert.deepEqual(at(npot.water.pixels, 3, 7).rgba, at(npot.completion.pixels, 2, 4).rgba);
  assert.deepEqual(at(npot.water.pixels, 3, 0).rgba, at(npot.completion.pixels, 2, 0).rgba);
  // Ground: 258 border vs 256 interior, transparent just outside 258.
  assert.deepEqual(at(npot.ground.pixels, 257, 257).rgba, at(npot.completion.pixels, 2, 4).rgba);
  assert.deepEqual(at(npot.ground.pixels, 251, 251).rgba, at(npot.completion.pixels, 2, 4).rgba);
  assert.deepEqual(at(npot.ground.pixels, 258, 0).rgba, [0, 0, 0, 0]);
  assert.deepEqual(at(npot.ground.pixels, 129, 129).rgba, [90, 90, 90, 255]);
  const colors = new Set(npot.completion.pixels.filter((p) => (p.x === 0 || p.x === 2) && (p.y === 0 || p.y === 4)).map((p) => p.rgba.join()));
  assert.equal(colors.size, 4, 'NPOT corners are distinct');
  const dsrc = fs.readFileSync(DRIVER_PATH, 'utf8');
  assert.ok(!/location\.(search|hash)|URLSearchParams/.test(dsrc), 'driver accepts no URL parameters');
});

// ---- Driver doubles: observer/adapter/judge separation ----
const clockFrom = () => { let t = 0; return () => ++t; };

test('completion observer preserves this/arguments, forwards once while open, records late and duplicate', () => {
  const gate = driver.makeGate(clockFrom());
  const seen = [];
  let pending = null;
  const receiver = { tag: 'TextureObject' };
  const original = function (data, cb, idx) { seen.push({ self: this, args: Array.from(arguments) }); pending = cb; return 'orig-ret'; };
  const wrapped = driver.observeTextureLoad(original, gate, (c) => (c ? { width: c.width, height: c.height } : null));
  const userCb = function () { userCalls.push({ self: this, args: Array.from(arguments) }); return 'user-ret'; };
  const userCalls = [];
  assert.equal(wrapped.call(receiver, 'blob:x', userCb, 7, 'extra'), 'orig-ret');
  assert.equal(seen[0].self, receiver);
  assert.deepEqual(seen[0].args.filter((_, i) => i !== 1), ['blob:x', 7, 'extra']);
  assert.notEqual(seen[0].args[1], userCb);
  const canvas = { width: 3, height: 5 };
  assert.equal(pending.call(canvas, true, 7, 'extra'), 'user-ret');
  assert.equal(userCalls.length, 1);
  assert.equal(userCalls[0].self, canvas);
  assert.deepEqual(userCalls[0].args, [true, 7, 'extra']);
  assert.deepEqual(gate.events[0].canvas, { width: 3, height: 5 });
  assert.equal(gate.forward_count, 1);
  pending.call(canvas, true, 7);
  assert.equal(userCalls.length, 1, 'duplicate not forwarded');
  assert.equal(gate.duplicates.length, 1);
  gate.open = false;
  const settles = [];
  gate.onSettle = (k) => settles.push(k);
  pending.call(canvas, true, 7);
  assert.equal(userCalls.length, 1, 'late not forwarded');
  assert.equal(gate.late[0].reason, 'control_closed');
  assert.deepEqual(settles, ['late']);
});

test('completion observer records a forwarded exception and rethrows it unchanged', () => {
  const gate = driver.makeGate(clockFrom());
  let cb = null;
  const wrapped = driver.observeTextureLoad(function (d, c) { cb = c; }, gate, () => null);
  const boom = new Error('canvas exception after revoke');
  wrapped(null, () => { throw boom; });
  const settles = [];
  gate.onSettle = (k) => settles.push(k);
  assert.throws(() => cb.call(null, false), (e) => e === boom);
  assert.equal(gate.events[0].forward_threw, 'canvas exception after revoke');
  assert.equal(gate.forward_count, 1);
  assert.deepEqual(settles, ['forwarded']);
});

test('texImage2D adapter forwards the real receiver/arguments, records source size, and labels an injected fault', () => {
  const calls = [];
  const proto = {
    texImage2D: function () { calls.push({ self: this, args: arguments }); return 'native-ret'; },
    getParameter: function (p) { this.queue.push(0x0500); return null; },
    isContextLost: () => false
  };
  const gl = Object.create(proto); gl.queue = [];
  gl.getError = () => (gl.queue.length ? gl.queue.shift() : 0);
  const log = [];
  const fault = driver.injectedFault('owned_observer_injected_invalid_enum_after_texImage2D');
  driver.installForwardingAdapter(gl, 'texImage2D', proto.texImage2D, driver.recordTexImage2D(gl, log, clockFrom()), fault.after);
  const src = { width: 4, height: 8, constructor: { name: 'HTMLCanvasElement' } };
  assert.equal(gl.texImage2D(0x0de1, 0, 0x1908, 0x1908, 0x1401, src), 'native-ret');
  assert.equal(calls[0].self, gl);
  assert.deepEqual(Array.from(calls[0].args), [0x0de1, 0, 0x1908, 0x1908, 0x1401, src]);
  assert.deepEqual([log[0].source_width, log[0].source_height, log[0].arg_count, log[0].receiver_is_owned_context], [4, 8, 6, true]);
  assert.equal(log[0].injected_fault_after, 'owned_observer_injected_invalid_enum_after_texImage2D');
  gl.texImage2D(0x0de1, 0, 0x1908, 0x1908, 0x1401, src);
  assert.equal(log.length, 2);
  assert.equal(log[1].injected_fault_after, undefined, 'fault fires once');
  assert.deepEqual(driver.drainGlErrors(gl), { errors: [0x0500], exhausted: false });
  assert.ok(!Object.prototype.hasOwnProperty.call(proto, 'queue') && Object.getPrototypeOf(gl).texImage2D === proto.texImage2D, 'prototype untouched');
});

test('GL error drain is bounded and the upload judge never accepts a callback/texture alone', () => {
  const endless = { getError: () => 0x0502 };
  assert.deepEqual(driver.drainGlErrors(endless, 16), { errors: Array(16).fill(0x0502), exhausted: true });
  const clean = { upload_calls: 1, consumer_errors: { errors: [], exhausted: false }, context_lost: false, texture_present: true, fbo_status: 0x8cd5,
    readback: { readback_ok: true }, diagnostic_errors: { errors: [], exhausted: false } };
  assert.equal(driver.judgeUpload({ ...clean, readback: { readback_ok: false } }).upload_verified, false, 'no positive readback');
  assert.equal(driver.judgeUpload({ ...clean, readback: null }).upload_verified, false);
  assert.equal(driver.judgeUpload({ ...clean, diagnostic_errors: { errors: [0x0502], exhausted: false } }).upload_verified, false);
  assert.equal(driver.judgeUpload({ ...clean, diagnostic_errors: { errors: [], exhausted: true } }).upload_verified, false);
  assert.equal(driver.judgeUpload({ ...clean, diagnostic_errors: null }).upload_verified, false);
  assert.equal(driver.judgeUpload(clean).upload_verified, true);
  assert.equal(driver.judgeUpload({ ...clean, consumer_errors: { errors: [0x0500], exhausted: false } }).upload_verified, false);
  assert.equal(driver.judgeUpload({ ...clean, context_lost: true }).upload_verified, false);
  assert.equal(driver.judgeUpload({ ...clean, fbo_status: 0x8cd6 }).upload_verified, false);
  const none = driver.judgeUpload({ ...clean, upload_calls: 0 });
  assert.deepEqual([none.upload_attempted, none.upload_verified], [false, false]);
  assert.equal(driver.judgeUpload({ ...clean, consumer_errors: { errors: [], exhausted: true } }).upload_verified, false);
});

function baseRecord(consumer, over = {}) {
  return {
    consumer,
    completion: { submissions: [], events: [], forward_count: 0, late: [], duplicates: [], ...over.completion },
    decode: { image_constructed: 1, native_load_events: 1, ...over.decode },
    upload: { calls: [], generate_mipmap_calls: 0, injected_fault: null, ...over.upload },
    water_user_callback: { count: 0, texture_non_null: false, ...over.water_user_callback },
    gl: { consumer_errors: { errors: [], exhausted: false }, texture_present: false, context_lost_before_submit: false, ...over.gl },
    judge: over.judge || { upload_verified: false, reasons: [] },
    probes: over.probes || {}, revokes: over.revokes || [], realm: { configs_enableMipmap: false },
    terminal: { state: 'forwarded', at: 5, rewrites_refused: 0, ...over.terminal },
    timing: { submit_returned_at: 2, elapsed_ms: 50, ...over.timing }
  };
}
const fx = authorFixtures();
const control = (id) => fx.controls.find((c) => c.id === id);

test('expectation evaluation keeps injected-fault, closed/late and null/malformed outcomes separate', () => {
  const evt = { at: 3, seq: 4, success: true, this_null: false, forwarded: true, canvas: { width: 2, height: 2 } };
  const injected = control('C6b-observer-injected-gl-error');
  const injRec = baseRecord('water', {
    completion: { events: [evt], forward_count: 1 }, upload: { calls: [{ source_width: 2, source_height: 2 }], injected_fault: { fired: true } },
    water_user_callback: { count: 1, texture_non_null: true }, gl: { consumer_errors: { errors: [0x0500], exhausted: false }, texture_present: true },
    judge: driver.judgeUpload({ upload_calls: 1, consumer_errors: { errors: [0x0500], exhausted: false }, context_lost: false, texture_present: true, fbo_status: 0x8cd5, readback: { readback_ok: true }, diagnostic_errors: { errors: [], exhausted: false } })
  });
  assert.equal(driver.evaluateControl(injRec, injected).result, 'PASS');
  const silent = { ...injRec, gl: { ...injRec.gl, consumer_errors: { errors: [], exhausted: false } }, judge: { upload_verified: true, reasons: [] } };
  assert.equal(driver.evaluateControl(silent, injected).result, 'FAIL', 'checker must reject, not accept, the apparent success');

  const closed = control('C7-closed-late-completion');
  const lateEvt = { ...evt, at: 9, forwarded: false, reason: 'control_closed' };
  const closedRec = baseRecord('ground', { completion: { late: [lateEvt] }, terminal: { state: 'closed_unknown', at: 2, closed_at: 2, rewrites_refused: 1 } });
  assert.equal(driver.evaluateControl(closedRec, closed).result, 'PASS');
  assert.equal(driver.evaluateControl({ ...closedRec, completion: { ...closedRec.completion, late: [] } }, closed).result, 'FAIL', 'late completion must be observed');
  assert.equal(driver.evaluateControl({ ...closedRec, completion: { ...closedRec.completion, forward_count: 1 } }, closed).result, 'FAIL');
  assert.equal(driver.evaluateControl({ ...closedRec, upload: { ...closedRec.upload, calls: [{}] } }, closed).result, 'FAIL');

  const nul = control('C4-null-input');
  const nullEvt = { at: 1, seq: 1, success: false, this_null: true, forwarded: true, canvas: null };
  const waterNull = baseRecord('water', { decode: { image_constructed: 0, native_load_events: 0 }, completion: { events: [nullEvt], forward_count: 1 } });
  assert.equal(driver.evaluateControl(waterNull, nul).result, 'PASS');
  assert.equal(driver.evaluateControl({ ...waterNull, water_user_callback: { count: 1, texture_non_null: true } }, nul).result, 'FAIL');
  assert.equal(driver.evaluateControl({ ...waterNull, decode: { image_constructed: 1, native_load_events: 0 } }, nul).result, 'FAIL');

  const mal = control('C5-malformed-timeout');
  const malRec = baseRecord('ground', { decode: { native_load_events: 0 }, terminal: { state: 'timeout_unknown_decode' }, timing: { elapsed_ms: 1600 } });
  assert.equal(driver.evaluateControl(malRec, mal).result, 'PASS');
  assert.equal(driver.evaluateControl({ ...malRec, timing: { elapsed_ms: 2500 } }, mal).result, 'FAIL');
  assert.equal(driver.evaluateControl({ ...malRec, timing: { elapsed_ms: null } }, mal).result, 'FAIL', 'missing elapsed never passes a deadline');
  assert.equal(driver.evaluateControl({ ...malRec, decode: { native_load_events: 1 } }, mal).result, 'FAIL', 'native load is not unknown decode');
  assert.equal(driver.evaluateControl({ ...malRec, realm_errors: [{ message: 'x' }] }, mal).result, 'FAIL', 'realm error is sticky');

  const valid = control('C1a-bmp-quadrant');
  const cbOnly = baseRecord('water', { completion: { events: [evt], forward_count: 1 }, upload: { calls: [{ source_width: 2, source_height: 2, receiver_is_owned_context: true }] },
    water_user_callback: { count: 1, texture_non_null: true }, revokes: [{ seq: 1 }], judge: { upload_verified: false, reasons: ['gl_errors:0x502'] },
    probes: { completion: { all_ok: true }, gpu: { all_ok: true }, upload_source: { all_ok: true } } });
  const res = driver.evaluateControl(cbOnly, valid);
  assert.equal(res.result, 'FAIL', 'callback with a non-null texture never suffices');
  assert.deepEqual(res.checks.filter((x) => !x.ok).map((x) => x.name), ['upload_verified']);
});

const SRC = process.env.IMAGE_CONSUMER_SOURCE;
const META = process.env.IMAGE_CONSUMER_METADATA;
test('saved .014 source: pinned slices recompute and assemble byte-identically (bytes only, never evaluated)', { skip: !(SRC && META) && 'set IMAGE_CONSUMER_SOURCE and IMAGE_CONSUMER_METADATA' }, () => {
  const src = fs.readFileSync(SRC);
  const slices = verifySource(src, DEFAULT_PROFILE);
  assert.deepEqual(verifyMetadata(fs.readFileSync(META), DEFAULT_PROFILE), { rows_checked: 9 });
  const { production, spans } = assembleProduction(slices, DEFAULT_PROFILE);
  for (const s of spans.filter((x) => x.kind === 'production')) {
    assert.ok(production.subarray(s.offset, s.offset + s.length).equals(src.subarray(s.source_offset, s.source_offset + s.length)), s.id);
  }
  const drv = fs.readFileSync(DRIVER_PATH);
  assert.deepEqual({ bytes: drv.length, sha256: sha(drv) }, { bytes: DEFAULT_PROFILE.driver.bytes, sha256: DEFAULT_PROFILE.driver.sha256 });
});

// ---- Authored runner doubles: the real driver runner (createRealm ->
// observeTextureLoad -> gate -> projected record -> evaluateControl -> cleanup)
// against authored page/realm/2D/GL/Image doubles. The doubles are written from
// the brief's specified contract, not copied from production, and certify no
// real browser, decode, canvas, GL or cleanup behaviour.
const GLC = { TEXTURE_2D: 0x0de1, RGBA: 0x1908, UNSIGNED_BYTE: 0x1401, FRAMEBUFFER: 0x8d40, COLOR_ATTACHMENT0: 0x8ce0,
  TEXTURE_MIN_FILTER: 0x2801, TEXTURE_MAG_FILTER: 0x2800, TEXTURE_WRAP_S: 0x2802, TEXTURE_WRAP_T: 0x2803, CLAMP_TO_EDGE: 0x812f,
  LINEAR: 0x2601, LINEAR_MIPMAP_LINEAR: 0x2703 };
class FakeCanvas {
  constructor() { this._w = 300; this._h = 150; this.data = new Uint8ClampedArray(this._w * this._h * 4); this._ctx = null; }
  get width() { return this._w; } set width(v) { this._w = v; this.data = new Uint8ClampedArray(v * this._h * 4); }
  get height() { return this._h; } set height(v) { this._h = v; this.data = new Uint8ClampedArray(this._w * v * 4); }
  getContext(kind) { return kind === '2d' ? (this._ctx || (this._ctx = new FakeCtx2D(this))) : null; }
}
class FakeCtx2D {
  constructor(canvas) { this.canvas = canvas; }
  clearRect() { this.canvas.data.fill(0); }
  getImageData(x, y, w, h) {
    if (!(w > 0 && h > 0)) throw new Error('IndexSizeError: zero-sized getImageData');
    const c = this.canvas, data = new Uint8ClampedArray(w * h * 4);
    for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) for (let k = 0; k < 4; k++) data[(j * w + i) * 4 + k] = c.data[((y + j) * c.width + x + i) * 4 + k];
    return { data, width: w, height: h };
  }
  putImageData(img) { this.canvas.data.set(img.data); }
}
// Nearest-neighbour stretch; probes sit in uniform regions so filtering is irrelevant.
FakeCtx2D.prototype.drawImage = function (src, dx, dy, dw = src.width, dh = src.height) {
  const c = this.canvas;
  if (FakeCtx2D.throwOn && FakeCtx2D.throwOn(arguments)) throw new Error('native drawImage threw');
  for (let y = Math.max(0, dy); y < Math.min(c.height, dy + dh); y++) for (let x = Math.max(0, dx); x < Math.min(c.width, dx + dw); x++) {
    const sx = Math.min(src.width - 1, Math.floor((x - dx) * src.width / dw)), sy = Math.min(src.height - 1, Math.floor((y - dy) * src.height / dh));
    for (let k = 0; k < 4; k++) c.data[(y * c.width + x) * 4 + k] = src.data[(sy * src.width + sx) * 4 + k];
  }
};

function fakeEnv(opts = {}) {
  const env = { fbos: new Set(), revoked: [], blobs: new Map(), removed: false, deletedTextures: 0, timerIds: [], clearAttempts: [] };
  FakeCtx2D.throwOn = opts.drawThrowOn || null;
  const errors = [];
  let lost = false, boundTex = null, boundFbo = null, texSeq = 0;
  const glProto = {
    ...GLC,
    getError: () => (opts.endlessError ? 0x0502 : errors.length ? errors.shift() : 0),
    isContextLost: () => lost,
    getExtension: (n) => (n === 'WEBGL_lose_context' ? { loseContext() { if (opts.loseThrows) throw new Error('loseContext threw'); lost = true; } } : null),
    createTexture: () => (lost ? null : { id: ++texSeq, data: null, w: 0, h: 0, params: {} }),
    bindTexture: (t, tex) => { boundTex = tex; },
    texImage2D(...a) { if (lost) return; const s = a[a.length - 1]; boundTex.data = Uint8ClampedArray.from(s.data); boundTex.w = s.width; boundTex.h = s.height; },
    texParameteri: (t, p, v) => { if (boundTex) boundTex.params[p] = v; },
    getTexParameter: (t, p) => (boundTex ? boundTex.params[p] : null),
    generateMipmap() {},
    getParameter: (p) => { if (p === 0) errors.push(0x0500); return null; },
    createFramebuffer: () => { const f = { att: null }; env.fbos.add(f); return f; },
    bindFramebuffer: (t, f) => { boundFbo = f; },
    framebufferTexture2D: (t, a, tt, tex) => { boundFbo.att = tex; },
    checkFramebufferStatus: () => { if (opts.statusThrows) throw new Error('status threw'); return boundFbo && boundFbo.att && boundFbo.att.data ? 0x8cd5 : 0x8cd6; },
    readPixels(x, y, w, h, f, t, buf) {
      if (opts.readPixels) return opts.readPixels(buf, errors);
      const tex = boundFbo.att;
      for (let k = 0; k < 4; k++) buf[k] = tex.data[(y * tex.w + x) * 4 + k];
    },
    deleteFramebuffer: (f) => { if (opts.deleteFboThrows) throw new Error('deleteFramebuffer threw'); env.fbos.delete(f); },
    deleteTexture: () => { if (opts.deleteTextureThrows) throw new Error('deleteTexture threw'); env.deletedTextures++; }
  };
  const gl = Object.create(glProto);
  env.gl = gl;
  const listeners = { error: [], unhandledrejection: [] };
  const realmWin = {
    console: { error() {}, warn() {} },
    addEventListener: (t, f) => listeners[t].push(f),
    dispatchError: (e) => listeners.error.forEach((f) => f({ message: String(e && e.message || e), error: e })),
    Blob: class { constructor(parts, o) { this.parts = parts; this.type = o.type; } },
    URL: {
      createObjectURL: (b) => { const u = 'blob:fake/' + env.blobs.size; env.blobs.set(u, b); return u; },
      // revokeThrows faults only the fixture's cleanup revoke, after the consumer's own revoke.
      revokeObjectURL: (u) => { if (opts.revokeThrows && env.revoked.length > 0) throw new Error('revoke threw'); env.revoked.push(u); }
    }
  };
  // Authored owned-Worker double: 'make' creates a realm Blob URL, 'revoke'
  // records the URL; workerMakeSilent/workerRevokeSilent never reply.
  env.worker = { made: [], revoked: [], terminated: 0, scripts: [] };
  realmWin.Worker = class FakeWorker {
    constructor(url) { env.worker.scripts.push(url); this.onmessage = null; }
    postMessage(msg) {
      setImmediate(() => {
        if (msg.op === 'make') {
          if (opts.workerMakeSilent) return;
          const u = realmWin.URL.createObjectURL(new realmWin.Blob([msg.bytes], { type: msg.mime }));
          env.worker.made.push(u);
          if (this.onmessage) this.onmessage({ data: { op: 'made', url: u } });
        } else if (msg.op === 'revoke') {
          env.worker.revoked.push(msg.url);
          if (!opts.workerRevokeSilent && this.onmessage) this.onmessage({ data: { op: 'revoked' } });
        }
      });
    }
    terminate() { if (opts.terminateThrows) throw new Error('terminate threw'); env.worker.terminated++; }
  };
  realmWin.Image = class FakeImage {
    constructor() { this.listeners = { load: [], error: [] }; this.onload = null; this.width = 0; this.height = 0; }
    addEventListener(t, f) { this.listeners[t].push(f); }
    set src(u) {
      this._src = u;
      setImmediate(() => {
        const blob = env.blobs.get(u);
        let bmp = null;
        try { bmp = parseBmp(Buffer.from(blob.parts[0])); } catch { bmp = null; }
        if (!bmp && !opts.malformedLoads) { this.listeners.error.forEach((f) => f()); return; }
        this.width = bmp ? bmp.w : 0; this.height = bmp ? bmp.h : 0;
        this.data = new Uint8ClampedArray(this.width * this.height * 4);
        for (let y = 0; y < this.height; y++) for (let x = 0; x < this.width; x++) this.data.set(bmp.px(x, y), (y * this.width + x) * 4);
        this.listeners.load.forEach((f) => f());
        try { if (this.onload) this.onload(); } catch (e) { realmWin.dispatchError(e); }
        if (opts.realmErrorAfterLoad) realmWin.dispatchError(new Error('unrelated realm script error'));
      });
    }
  };
  realmWin.document = {
    createElement: (k) => (k === 'canvas' ? new FakeCanvas() : {}),
    head: { appendChild: (s) => setImmediate(() => {
      if (opts.scriptError) return s.onerror();
      if (opts.scriptNoLoad) return undefined;
      realmWin.__imageConsumerFixtureRealm = api;
      return s.onload();
    }) }
  };
  // Authored realm API with the specified Texture.load / ground / water behaviour.
  const procCanvas3 = new FakeCanvas();
  const groundCanvas = new FakeCanvas();
  const groundCtx = groundCanvas.getContext('2d');
  env.groundCtx = groundCtx;
  let atlas = null;
  const Texture = {
    load(data, oncomplete) {
      const args = Array.prototype.slice.call(arguments, 2);
      if (!data) { args.unshift(false); oncomplete.apply(null, args); return; }
      const img = new realmWin.Image();
      img.src = data;
      img.onload = function () {
        if (/^blob:/.test(data)) realmWin.URL.revokeObjectURL(data);
        const canvas = new FakeCanvas();
        canvas.width = this.width; canvas.height = this.height;
        canvas.getContext('2d').drawImage(this, 0, 0, this.width, this.height);
        procCanvas3.width = canvas.width; procCanvas3.height = canvas.height;
        procCanvas3.getContext('2d').drawImage(canvas, 0, 0);
        const im = procCanvas3.getContext('2d').getImageData(0, 0, canvas.width, canvas.height);
        for (let i = 0; i < im.data.length; i += 4) if (im.data[i] > 230 && im.data[i + 1] < 20 && im.data[i + 2] > 230) im.data.fill(0, i, i + 4);
        canvas.getContext('2d').putImageData(im, 0, 0);
        args.unshift(true);
        oncomplete.apply(canvas, args);
      };
    }
  };
  const defaultDraw = (ctx, src) => { ctx.drawImage(src, 0, 0, 258, 258); ctx.drawImage(src, 1, 1, 256, 256); };
  const pot = (n) => 2 ** Math.ceil(Math.log2(n));
  const api = {
    webgl: () => ({
      getContext: () => gl,
      texture(g, url, callback) {
        const rest = Array.prototype.slice.call(arguments, 3);
        Texture.load(url, function (success) {
          if (!success || g.isContextLost()) return;
          const c = new FakeCanvas();
          c.width = pot(this.width); c.height = pot(this.height);
          c.getContext('2d').drawImage(this, 0, 0, c.width, c.height);
          const t = g.createTexture();
          g.bindTexture(g.TEXTURE_2D, t);
          g.texImage2D(g.TEXTURE_2D, 0, g.RGBA, g.RGBA, g.UNSIGNED_BYTE, c);
          g.texParameteri(g.TEXTURE_2D, g.TEXTURE_MIN_FILTER, g.LINEAR);
          callback.apply(null, [t, ...rest]);
        });
      }
    }),
    texture: () => Texture,
    configs: () => ({ get: () => false }),
    initTextures(g, textures) {
      groundCanvas.width = 512; groundCanvas.height = 512;
      groundCtx.clearRect(0, 0, 512, 512);
      let loaded = 0;
      const onDone = function (success) {
        if (success) (opts.groundDraw || defaultDraw)(groundCtx, this);
        if (++loaded === textures.length) {
          if (!atlas) atlas = g.createTexture();
          g.bindTexture(g.TEXTURE_2D, atlas);
          g.texImage2D(g.TEXTURE_2D, 0, g.RGBA, g.RGBA, g.UNSIGNED_BYTE, groundCanvas);
          if (opts.throwAfterUpload) throw new Error('callback threw after apparent upload');
        }
      };
      for (let i = 0; i < textures.length; ++i) Texture.load(textures[i], onDone, i);
    },
    procCanvas3: () => procCanvas3,
    groundCanvas: () => groundCanvas,
    groundContext: () => groundCtx,
    groundAtlasTexture: () => { env.atlasReads = (env.atlasReads || 0) + 1; if (opts.atlasThrowAfter !== undefined && env.atlasReads > opts.atlasThrowAfter) throw new Error('atlas accessor threw'); return atlas; }
  };
  const win = {
    performance, atob, crypto: globalThis.crypto,
    // Timer double: ids are recorded in creation order; clearThrows(index)
    // faults that timer's release (the native timer then still fires).
    setTimeout: (f, ms) => { const id = setTimeout(f, ms); env.timerIds.push(id); return id; },
    clearTimeout: (id) => { env.clearAttempts.push(env.timerIds.indexOf(id)); if (opts.clearThrows && opts.clearThrows(env.timerIds.indexOf(id))) throw new Error('clearTimeout threw'); clearTimeout(id); },
    document: {
      createElement: () => ({ contentWindow: realmWin, remove() { if (opts.removeThrows) throw new Error('remove threw'); env.removed = true; } }),
      getElementById: () => ({ appendChild: (el) => { if (!opts.iframeNoLoad) setImmediate(() => el.onload()); } })
    }
  };
  const images = Object.fromEntries(fx.images.map((im) => [im.id, im]));
  env.ctx = { win, images, manifest: { production: { sha256: 'p' }, driver: { sha256: 'd' } }, manifestSha: 'm', records: [], busy: false, limits: { realmSetupMs: 150 } };
  return env;
}
const runWith = (opts, id, consumer, over = {}) => { const env = fakeEnv(opts); return driver.runControl(env.ctx, { ...control(id), ...over }, consumer).then((rec) => ({ env, rec })); };
const failed = (rec) => rec.expectation.checks.filter((x) => !x.ok).map((x) => x.name);
const ownDraw = (env) => Object.prototype.hasOwnProperty.call(env.groundCtx, 'drawImage');

test('runner flow: real observer/gate records project to the canonical schema and PASS valid ground/water controls', async () => {
  for (const [id, consumer] of [['C3-npot-resize', 'ground'], ['C3-npot-resize', 'water'], ['C1a-bmp-quadrant', 'ground'], ['C2-magenta-threshold', 'water']]) {
    const { env, rec } = await runWith({}, id, consumer);
    assert.equal(rec.exception, null, `${id}/${consumer} ${rec.exception}`);
    assert.deepEqual(failed(rec), [], `${id}/${consumer}`);
    assert.equal(rec.expectation.result, 'PASS');
    assert.ok(Object.isFrozen(rec.completion) && Object.isFrozen(rec.completion.events));
    assert.deepEqual(Object.keys(rec.completion), ['submissions', 'events', 'forward_count', 'late', 'duplicates']);
    assert.equal(rec.completion.forward_count, 1);
    assert.ok(rec.judge.upload_verified && rec.gl.readback_ok);
    assert.equal(env.fbos.size, 0, 'owned FBO released');
    assert.ok(env.removed && rec.cleanup.realm_removed && rec.cleanup.failures.length === 0);
    assert.equal(ownDraw(env), false, 'own drawImage observer restored');
    if (consumer === 'ground') {
      assert.deepEqual(rec.ground_draws.map((d) => [d.args, d.arg_count, d.source_receiver_index, d.receiver_is_owned_context, d.returned]),
        [[[0, 0, 258, 258], 5, 0, true, true], [[1, 1, 256, 256], 5, 0, true, true]]);
      assert.ok(rec.ground_draws[1].seq < rec.upload.calls[0].seq);
    }
  }
  const { rec } = await runWith({}, 'C4-null-input', 'ground');
  assert.deepEqual(failed(rec), []);
  assert.deepEqual(rec.ground_draws, []);
  // An old-schema (gate-shaped) record is a FAIL, not a post-cleanup throw.
  const legacy = { ...rec, completion: { completions: [], forwardCount: 1 } };
  assert.deepEqual(failed({ ...legacy, expectation: driver.evaluateControl(legacy, control('C4-null-input')) }), ['completion_schema']);
  assert.throws(() => driver.projectCompletion({ completions: [], forwardCount: 1 }), /completion schema/);
});

test('ground 258/256 call evidence rejects omission, order, inset, source, receiver and native throw that pixels alone miss', async () => {
  const other = new FakeCanvas(); other.width = 3; other.height = 5;
  const cases = [
    ['omit_second', (ctx, s) => { ctx.drawImage(s, 0, 0, 258, 258); }, 'draw_count:1'],
    ['swapped_order', (ctx, s) => { ctx.drawImage(s, 1, 1, 256, 256); ctx.drawImage(s, 0, 0, 258, 258); }, 'draw0_args:1,1,256,256'],
    ['wrong_inset', (ctx, s) => { ctx.drawImage(s, 0, 0, 258, 258); ctx.drawImage(s, 2, 2, 256, 256); }, 'draw1_args:2,2,256,256'],
    ['wrong_source', (ctx, s) => { other.data.set(s.data); ctx.drawImage(s, 0, 0, 258, 258); ctx.drawImage(other, 1, 1, 256, 256); }, 'draw1_source_not_completion_canvas'],
    ['wrong_receiver', (ctx, s) => { ctx.drawImage(s, 0, 0, 258, 258); ctx.drawImage.call(other.getContext('2d'), s, 1, 1, 256, 256); }, 'draw1_receiver_not_owned_context'],
    ['extra_args', (ctx, s) => { ctx.drawImage(s, 0, 0, 258, 258); ctx.drawImage(s, 1, 1, 256, 256, 0); }, 'draw1_arg_count:6']
  ];
  for (const [name, groundDraw, reason] of cases) {
    const { env, rec } = await runWith({ groundDraw }, 'C3-npot-resize', 'ground');
    assert.ok(rec.ground_draw_judge.reasons.includes(reason), `${name}: ${rec.ground_draw_judge.reasons}`);
    assert.ok(failed(rec).includes('ground_258_256_draw_calls'), name);
    assert.equal(rec.expectation.result, 'FAIL', name);
    assert.equal(ownDraw(env), false, `${name} restored`);
  }
  // Omission keeps every clamped/uniform pixel probe green: call evidence is what rejects it.
  const { rec: omit } = await runWith({ groundDraw: cases[0][1] }, 'C3-npot-resize', 'ground');
  assert.deepEqual(failed(omit), ['ground_258_256_draw_calls']);
  // Native throw inside the second draw: recorded, rethrown, sticky.
  const { env, rec } = await runWith({ drawThrowOn: (a) => a[1] === 1 }, 'C3-npot-resize', 'ground');
  assert.equal(rec.ground_draws[1].threw, 'native drawImage threw');
  assert.ok(rec.ground_draw_judge.reasons.includes('draw1_not_returned_normally'));
  assert.ok(rec.expectation.checks.find((x) => x.name === 'no_sticky_failures').detail.includes('ground_draw_threw'));
  assert.equal(rec.expectation.result, 'FAIL');
  assert.equal(ownDraw(env), false);
  const j = driver.judgeGroundDraws([{ seq: 5, returned: true, threw: null, receiver_is_owned_context: true, arg_count: 5, source_receiver_index: 0, args: [0, 0, 258, 258] },
    { seq: 6, returned: true, threw: null, receiver_is_owned_context: true, arg_count: 5, source_receiver_index: 0, args: [1, 1, 256, 256] }], [{ seq: 4, source_width: 512, source_height: 512 }]);
  assert.deepEqual(j.reasons, ['draw_not_before_upload']);
});

test('sticky failures: forwarded throw after apparent upload, realm error and malformed native load + exception never PASS', async () => {
  const { rec: thrown } = await runWith({ throwAfterUpload: true }, 'C3-npot-resize', 'ground');
  assert.equal(thrown.upload.calls.length, 1, 'observed upload fact retained');
  assert.equal(thrown.completion.events[0].forward_threw, 'callback threw after apparent upload');
  assert.equal(thrown.realm_errors.length, 1);
  assert.equal(thrown.expectation.result, 'FAIL');
  assert.deepEqual(thrown.expectation.checks.find((x) => x.name === 'no_sticky_failures').detail, ['realm_errors:1', 'forward_threw']);
  const { rec: realmErr } = await runWith({ realmErrorAfterLoad: true }, 'C1a-bmp-quadrant', 'water');
  assert.deepEqual(failed(realmErr), ['no_sticky_failures']);
  const { rec: mal } = await runWith({}, 'C5-malformed-timeout', 'ground', { timeoutMs: 100 });
  assert.deepEqual(failed(mal), [], 'genuine unknown decode (native error event only) is the expected control');
  assert.equal(mal.decode.state, 'native_error_event_observed_consumer_has_no_onerror');
  const { rec: malLoad } = await runWith({ malformedLoads: true }, 'C5-malformed-timeout', 'water', { timeoutMs: 100 });
  assert.equal(malLoad.decode.native_load_events, 1);
  assert.equal(malLoad.realm_errors.length, 1);
  assert.equal(malLoad.terminal.state, 'timeout_unknown_decode');
  assert.ok(failed(malLoad).includes('no_native_load_event') && failed(malLoad).includes('no_sticky_failures'));
  // The labelled injected GL fault stays an explicit expected control, not a sticky failure.
  const { rec: inj } = await runWith({}, 'C6b-observer-injected-gl-error', 'ground');
  assert.deepEqual(failed(inj), []);
  assert.equal(inj.judge.upload_verified, false);
  assert.ok(inj.judge.reasons.some((r) => r.startsWith('gl_errors:0x500')));
});

test('GPU readback needs positive successful reads: untouched/stale buffers, GL errors, exhaustion and throws fail and FBOs are released', () => {
  const tex = { data: new Uint8ClampedArray(16), w: 2, h: 2 };
  const pts = [{ x: 0, y: 0, rgba: [0, 0, 0, 0], tol: 0 }, { x: 1, y: 1, rgba: [0, 0, 0, 0], tol: 0 }];
  const probe = (opts) => { const env = fakeEnv(opts); const out = driver.readTextureProbes(env.gl, tex, { width: 2, height: 2 }, pts); return { env, out }; };
  const ok = probe({});
  assert.equal(ok.out.readback_ok, true, ok.out.failures.join());
  assert.equal(ok.env.fbos.size, 0);
  const zeroBuf = probe({ readPixels: () => {} });
  assert.equal(zeroBuf.out.readback_ok, false, 'untouched buffer never passes a blank probe');
  assert.ok(zeroBuf.out.failures[0].startsWith('readPixels_buffer_untouched'));
  // First read writes real zeros, later reads silently write nothing (buffer would hold stale bytes).
  let wrote = false;
  const staleBuf = probe({ readPixels: (buf) => { if (!wrote) { buf.fill(0); wrote = true; } } });
  assert.equal(staleBuf.out.readback_ok, false, 'stale bytes from an earlier read do not pass');
  const glErr = probe({ readPixels: (buf, errors) => { buf.fill(0); errors.push(0x0502); } });
  assert.ok(!glErr.out.readback_ok && glErr.out.failures[0].startsWith('readPixels_gl_error:1282'));
  const exhausted = probe({ endlessError: true });
  assert.ok(!exhausted.out.readback_ok && exhausted.out.failures.includes('pre_probe_gl_errors'));
  const thrown = probe({ readPixels: () => { throw new Error('native readPixels threw'); } });
  assert.ok(!thrown.out.readback_ok && thrown.out.failures[0].startsWith('readPixels_threw:native readPixels threw'));
  for (const p of [zeroBuf, staleBuf, glErr, exhausted, thrown]) { assert.equal(p.env.fbos.size, 0, 'FBO always released'); assert.equal(p.out.fbo_deleted, true); }
  const statusThrow = fakeEnv({});
  statusThrow.gl.checkFramebufferStatus = () => { throw new Error('status threw'); };
  const st = driver.readTextureProbes(statusThrow.gl, tex, { width: 2, height: 2 }, pts);
  assert.ok(!st.readback_ok && st.failures[0] === 'probe_exception:status threw' && statusThrow.fbos.size === 0);
});

test('null ground blank-atlas control fails when readPixels leaves the zeroed buffer untouched', async () => {
  const { rec } = await runWith({ readPixels: () => {} }, 'C4-null-input', 'ground');
  assert.equal(rec.gl.readback_ok, false);
  assert.ok(failed(rec).includes('blank_gpu_probes') && failed(rec).includes('upload_verified'));
});

test('realm setup reject/missing load and combined cleanup faults: owned release attempted, terminal published, FAIL', async () => {
  for (const opts of [{ scriptError: true }, { scriptNoLoad: true }, { iframeNoLoad: true }]) {
    const { env, rec } = await runWith(opts, 'C1a-bmp-quadrant', 'water');
    assert.ok(rec.exception && /production\.js failed|realm setup exceeded/.test(rec.exception), JSON.stringify(opts));
    assert.equal(rec.terminal.state, 'driver_exception');
    assert.ok(env.removed && rec.cleanup.realm_removed, 'iframe owned before the first await is removed');
    assert.equal(rec.cleanup.timers_cleared, 0, 'setup timer already settled');
    assert.equal(rec.expectation.result, 'FAIL');
    assert.equal(typeof rec.timing.elapsed_ms, 'number');
  }
  const { env, rec } = await runWith({ revokeThrows: true, deleteTextureThrows: true, loseThrows: true }, 'C1a-bmp-quadrant', 'water');
  assert.deepEqual(rec.cleanup.failures.map((f) => f.step), ['revoke_own_url', 'delete_texture', 'lose_own_context']);
  assert.ok(env.removed && rec.cleanup.realm_removed, 'later steps still ran');
  assert.deepEqual(rec.cleanup.observers_restored.sort(), ['Image', 'Texture.load', 'revokeObjectURL']);
  assert.ok(rec.expectation.checks.find((x) => x.name === 'no_sticky_failures').detail.includes('cleanup_failures:3'));
  assert.equal(rec.expectation.result, 'FAIL');
  const { env: e2, rec: r2 } = await runWith({ removeThrows: true }, 'C3-npot-resize', 'ground');
  assert.deepEqual(r2.cleanup.failures.map((f) => f.step), ['remove_realm']);
  assert.equal(ownDraw(e2), false, 'drawImage restored before the failing realm removal');
  assert.equal(r2.expectation.result, 'FAIL');
});

test('runner restores busy/buttons/status in finally and the matrix gate is meaningful', async () => {
  const ctx = { manifest: {}, busy: false, records: [] };
  const calls = [];
  const ui = { setDisabled: (v) => calls.push(['disabled', v]), setStatus: (s) => calls.push(['status', s]), render: () => { calls.push(['render']); throw new Error('render threw'); } };
  const runOne = driver.makeRunner(ctx, ui, async () => { throw new Error('run threw'); });
  const rec = await runOne({ id: 'C1a-bmp-quadrant', kind: 'valid' }, 'water');
  assert.equal(rec.terminal.state, 'runner_exception');
  assert.equal(rec.expectation.result, 'FAIL');
  assert.equal(ctx.busy, false);
  assert.deepEqual(calls.slice(-3), [['render'], ['disabled', false], ['status', 'ready']]);
  assert.equal(ctx.records.length, 1);
  assert.equal(driver.summarizeMatrix([{ expectation: { result: 'PASS' } }], 61000).result, 'FAIL');
  assert.equal(driver.summarizeMatrix([{ expectation: { result: 'PASS' } }], null).result, 'FAIL');
  assert.equal(driver.summarizeMatrix([{ expectation: { result: 'PASS' } }], 1000).result, 'PASS');
  assert.equal(driver.summarizeMatrix([], 1000).result, 'FAIL');
});

// ---- T07.007.014.016.001.001 follow-up: combined diagnostic, cleanup and
// setup faults, plus the existing C8c owned-Worker lifecycle. Authored doubles only.
const stickyOf = (rec) => rec.expectation.checks.find((x) => x.name === 'no_sticky_failures').detail;
const bounded = (p, ms = 4000) => Promise.race([p, new Promise((_, rej) => setTimeout(() => rej(new Error('promise hung')), ms).unref())]);

test('C6b injected consumer error stays expected while unrelated readPixels/status/deleteFramebuffer failures are sticky', async () => {
  const faults = [
    [{ readPixels: () => { throw new Error('native readPixels threw'); } }, 'readPixels_threw:native readPixels threw@'],
    [{ statusThrows: true }, 'probe_exception:status threw'],
    [{ deleteFboThrows: true }, 'deleteFramebuffer_exception:deleteFramebuffer threw']
  ];
  for (const consumer of ['ground', 'water']) {
    const { rec: plain } = await runWith({}, 'C6b-observer-injected-gl-error', consumer);
    assert.deepEqual(failed(plain), [], `ordinary C6b/${consumer} stays PASS`);
    for (const [opts, reason] of faults) {
      const { env, rec } = await runWith(opts, 'C6b-observer-injected-gl-error', consumer);
      const tag = `${consumer} ${reason}`;
      assert.equal(rec.exception, null, tag);
      assert.deepEqual(failed(rec), ['no_sticky_failures'], tag);
      assert.equal(rec.expectation.result, 'FAIL', tag);
      assert.ok(stickyOf(rec).some((s) => s.startsWith('diagnostic_readback_failures:')), tag);
      assert.ok(rec.gl.gpu_failures.some((f) => f.startsWith(reason)), `${tag}: ${rec.gl.gpu_failures}`);
      // Intended consumer error, injected-fault and observed callback/upload facts are retained separately.
      assert.deepEqual(rec.gl.consumer_errors, { errors: [0x0500], exhausted: false }, tag);
      assert.equal(rec.upload.injected_fault.fired, true, tag);
      assert.equal(rec.upload.calls.length, 1, tag);
      assert.equal(rec.gl.texture_present, true, tag);
      if (consumer === 'water') assert.equal(rec.water_user_callback.count, 1, tag);
      assert.equal(rec.judge.upload_verified, false, tag);
      if (opts.deleteFboThrows) assert.equal(env.fbos.size, 1, 'failed FBO release is not reported as released');
      else assert.equal(env.fbos.size, 0, tag);
    }
  }
  // A post-probe diagnostic GL error is sticky too; the consumer drain is not.
  const base = { gl: { gpu_failures: [], diagnostic_errors: { errors: [0x0502], exhausted: false }, consumer_errors: { errors: [0x0500], exhausted: false } } };
  assert.deepEqual(driver.stickyFailures(base), ['diagnostic_gl_errors']);
  assert.deepEqual(driver.stickyFailures({ gl: { ...base.gl, diagnostic_errors: { errors: [], exhausted: false } } }), []);
});

test('cleanup continues past a throwing texture accessor and releases every timer independently with truthful bookkeeping', async () => {
  const { env, rec } = await runWith({ atlasThrowAfter: 1 }, 'C3-npot-resize', 'ground');
  assert.equal(rec.exception, null);
  assert.equal(env.atlasReads, 2, 'run read succeeded; cleanup enumeration threw');
  assert.deepEqual(rec.cleanup.failures.map((f) => f.step), ['enumerate_texture_ground_atlas']);
  assert.equal(rec.cleanup.textures_deleted, 0);
  assert.equal(rec.cleanup.context_lost_by_fixture, true, 'context release still attempted');
  assert.deepEqual(rec.cleanup.observers_restored.sort(), ['Image', 'Texture.load', 'ground_drawImage', 'revokeObjectURL']);
  assert.ok(env.removed && rec.cleanup.realm_removed && rec.cleanup.timers_unreleased === 0);
  assert.deepEqual(failed(rec), ['no_sticky_failures']);
  assert.ok(stickyOf(rec).includes('cleanup_failures:1'));
  // Direct cleanup: first accessor and first timer release throw; later ones are still attempted.
  const e2 = fakeEnv({ clearThrows: (i) => i === 0 });
  const timers = new Set([0, 1, 2].map(() => e2.ctx.win.setTimeout(() => {}, 10000)));
  const ids = Array.from(timers);
  const restored = [];
  const tex = { id: 'water' };
  const r = { cleanup: { failures: [] } };
  await driver.cleanupOwned(e2.ctx, r, {
    urls: [], worker: null, workerScriptUrl: null, gl: e2.gl, iframe: { remove() { r.removed = true; } },
    textures: [['ground_atlas', () => { throw new Error('accessor threw'); }], ['water', () => tex]],
    restores: [['x', () => { restored.push('x'); return true; }]]
  }, timers);
  clearTimeout(ids[0]);
  assert.deepEqual(r.cleanup.failures.map((f) => f.step), ['enumerate_texture_ground_atlas', 'clear_timer']);
  assert.equal(r.cleanup.failures[1].error, 'clearTimeout threw');
  assert.equal(r.cleanup.textures_deleted, 1, 'later texture still deleted');
  assert.deepEqual(e2.clearAttempts, [0, 1, 2], 'every timer release attempted');
  assert.deepEqual({ a: r.cleanup.timers_attempted, c: r.cleanup.timers_cleared, u: r.cleanup.timers_unreleased }, { a: 3, c: 2, u: 1 });
  assert.deepEqual(Array.from(timers), [ids[0]], 'failed release keeps its bookkeeping');
  assert.ok(r.cleanup.context_lost_by_fixture && restored.length === 1 && r.removed);
});

test('realm setup settles exactly once when its timer release throws, with a sticky failure and no PASS', async () => {
  const clearThrows = (i) => i === 0;
  const ok = await bounded(runWith({ clearThrows }, 'C1a-bmp-quadrant', 'water'));
  assert.equal(ok.rec.exception, null, 'successful setup still resolved');
  assert.equal(ok.rec.upload.calls.length, 1);
  assert.deepEqual(failed(ok.rec), ['no_sticky_failures']);
  assert.ok(stickyOf(ok.rec).includes('setup_timer_release'));
  // Cleanup retries the unreleased setup timer and reports it truthfully.
  assert.deepEqual(ok.rec.cleanup.failures.map((f) => f.step), ['clear_timer']);
  assert.deepEqual({ a: ok.rec.cleanup.timers_attempted, u: ok.rec.cleanup.timers_unreleased }, { a: 1, u: 1 });
  const bad = await bounded(runWith({ clearThrows, scriptError: true }, 'C1a-bmp-quadrant', 'water'));
  assert.match(bad.rec.exception, /production\.js failed/, 'rejected setup still rejected');
  assert.equal(bad.rec.terminal.state, 'driver_exception');
  assert.ok(bad.env.removed && bad.rec.cleanup.realm_removed);
  assert.equal(bad.rec.expectation.result, 'FAIL');
  // The uncleared native setup timer fires later; finish refuses it silently.
  await new Promise((r) => setTimeout(r, 250));
  for (const { rec } of [ok, bad]) {
    assert.equal(rec.failures.filter((f) => f.kind === 'setup_timer_release').length, 1);
    assert.equal(rec.realm_errors.length, 0);
  }
});

test('C8c owned-Worker path: normal completion, make timeout, revoke timeout and terminate throw keep later cleanup', async () => {
  for (const consumer of ['ground', 'water']) {
    const { env, rec } = await runWith({}, 'C8c-worker-blob-url', consumer);
    assert.deepEqual(failed(rec), [], `C8c/${consumer}`);
    assert.equal(env.worker.made.length, 1);
    assert.ok(rec.revokes.some((r) => r.own_url), 'consumer revoked the Worker-created URL');
    assert.deepEqual(env.worker.revoked, env.worker.made, 'fixture asked the Worker to revoke its URL');
    assert.equal(env.worker.terminated, 1);
    assert.ok(rec.cleanup.worker_url_revoke_ack && rec.cleanup.worker_terminated && rec.cleanup.worker_script_url_revoked);
    assert.ok(env.revoked.includes(env.worker.scripts[0]), 'worker script URL revoked natively');
    assert.ok(env.removed && rec.cleanup.timers_unreleased === 0);
  }
  const later = (rec, env) => {
    assert.equal(rec.cleanup.worker_script_url_revoked, true);
    assert.equal(rec.cleanup.context_lost_by_fixture, true);
    assert.ok(rec.cleanup.observers_restored.includes('Image') && rec.cleanup.observers_restored.includes('revokeObjectURL'));
    assert.equal(rec.cleanup.timers_unreleased, 0);
    assert.ok(env.removed && rec.cleanup.realm_removed);
    assert.equal(rec.expectation.result, 'FAIL');
  };
  const make = await runWith({ workerMakeSilent: true }, 'C8c-worker-blob-url', 'water');
  assert.match(make.rec.exception, /owned worker did not create a Blob URL/);
  assert.equal(make.rec.completion.submissions.length, 0, 'nothing submitted');
  assert.deepEqual(make.rec.cleanup.failures, [], 'no URL to revoke; terminate still ran');
  assert.equal(make.rec.cleanup.worker_terminated, true);
  later(make.rec, make.env);
  const rev = await runWith({ workerRevokeSilent: true }, 'C8c-worker-blob-url', 'ground');
  assert.equal(rev.rec.exception, null);
  assert.deepEqual(rev.rec.cleanup.failures.map((f) => f.step), ['worker_url_revoke_ack']);
  assert.equal(rev.rec.cleanup.worker_terminated, true);
  assert.ok(rev.rec.cleanup.observers_restored.includes('Texture.load') && rev.rec.cleanup.observers_restored.includes('ground_drawImage'));
  assert.deepEqual(failed(rev.rec), ['no_sticky_failures']);
  later(rev.rec, rev.env);
  const term = await runWith({ terminateThrows: true }, 'C8c-worker-blob-url', 'water');
  assert.deepEqual(term.rec.cleanup.failures.map((f) => f.step), ['worker_terminate']);
  assert.equal(term.rec.cleanup.worker_terminated, undefined, 'failed terminate not reported as terminated');
  assert.deepEqual(failed(term.rec), ['no_sticky_failures']);
  later(term.rec, term.env);
});
