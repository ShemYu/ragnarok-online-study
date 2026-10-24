#!/usr/bin/env node
// T07.007.014.016: build the tiny authored image-consumer fixture.
//
//   node tools/renewal/build_image_consumer_fixture.mjs \
//     --source <absolute saved .014 Online.js> \
//     --metadata <absolute .014 Claude OUTPUT_PINS.json> \
//     --out <absolute fresh private directory>
//
// Reads the saved source and metadata as bytes only; nothing is evaluated,
// imported or followed. Copies byte-identical executable slices S01-S08 of the
// qualified .014 table (independently recomputed LF/byte/SHA coordinates), adds
// separately pinned scaffolding plus the three checked S09 ground assignments,
// authors tiny BMP/JPEG fixtures, copies the pinned browser driver and writes
// a closed MANIFEST.json. Every check runs before the exclusive output
// directory is created; a later failure removes only paths this run created.
// No server, browser, Worker, network or native action is started here. Root
// serves the generated directory on its own loopback port and drives it.
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const TASK = 'T07.007.014.016';
export const MANIFEST_SCHEMA = 't07.007.014.016/manifest-v1';
export const FIXTURES_SCHEMA = 't07.007.014.016/fixtures-v1';
export const LIMITS = Object.freeze({ maxEncodedBytes: 4096, maxDimension: 32, groundAtlas: 512 });
const sha256 = (b) => createHash('sha256').update(b).digest('hex');
const HERE = path.dirname(fileURLToPath(import.meta.url));
export const DRIVER_PATH = path.join(HERE, 'image_consumer_fixture_driver.js');

// Qualified .014 table rows (Root-selected Claude closure, OUTPUT_PINS.json).
const row = (slice, use, lf_start, lf_end, byte_offset, byte_length, sha, first, last) =>
  Object.freeze({ slice, use, lf_start, lf_end, byte_offset, byte_length, sha256: sha, first, last });
export const DEFAULT_PROFILE = Object.freeze({
  source: Object.freeze({ bytes: 13174290, sha256: '50b724b708393d7bb6d71b4f5102e62b16e340eb1bb54f05b1c8613af4116418' }),
  metadata: Object.freeze({ bytes: 9591, sha256: '18bcc860754a9950409de19bf0b4f076621c18484f5f698cf5adbaf452ba53d7' }),
  driver: Object.freeze({ bytes: 51040, sha256: '77c9ec52a34c28db83089256d3958662ad7707962aaae630e7c673e5689cbc3c' }),
  slices: Object.freeze([
    row('S01_esmMin', 'exec', 14, 21, 488, 155, 'fcb8c98ab83e7629818b16a96125464da5abeea6b79a11fcd1445380a4aa0983', 'var __esmMin = (fn, res, err) => () => {', '};'),
    row('S02_Configs_region', 'exec', 10982, 11036, 424633, 1145, 'd9b38ed479e72c4a0484ceb7393c4b903a2e97f35a108f97c47933deffc9ae0b', '//#region src/Core/Configs.js', '//#endregion'),
    row('S03_Targa_region', 'exec', 79200, 79464, 3637394, 8713, 'afde667e87c66eb9a7ac98a9a2665709953292f2b2f0e5fa2b3710f8cb46fabd', '//#region src/Loaders/Targa.js', '//#endregion'),
    row('S04_libgif_region', 'exec', 83783, 84435, 3763010, 19899, 'cb5de7553120cf181ed465a54ba25c345311e3ace1a96ab492c9ec68b8d4a67b', '//#region src/Vendors/libgif.js', '//#endregion'),
    row('S05_Texture_region', 'exec', 84436, 84560, 3782909, 4124, '7ff1c597eaf7851d53c2d107eeb4c1e18f1b9bac8a3534c33e5e35600c739215', '//#region src/Utils/Texture.js', '//#endregion'),
    row('S06_WebGL_region', 'exec', 84561, 84749, 3787033, 6177, 'c6cce317ff50a5b1ca9489d12a819164147e55d97f2d2333a9a9c3e8457a14ef', '//#region src/Utils/WebGL.js', '//#endregion'),
    row('S07_Ground_initTextures', 'exec', 209382, 209403, 6372495, 940, '716b3d97ebb37f0fca2f496ecb40b0a3e5f32cd284010a012c176be8b2dd90c4', 'function initTextures(gl, textures) {', '}'),
    row('S08_Ground_onTextureAtlasComplete', 'exec', 209410, 209417, 6373538, 432, '6ae525074a8bacf21e27b20d8658c6cea5ebc107c4b111f38a95a2b293cbe0b4', 'function onTextureAtlasComplete(gl, atlas) {', '}'),
    row('S09_Ground_vars_and_init_REFERENCE', 'ref', 209521, 209551, 6376862, 822, '012cb7a1659f6ef352295415bae9b38787d62167008c31ed1893e34ec1887082', 'var procCanvas$2, procCtx$2, _program$28, _buffer$21, _lightmap, _tileColor, _textureAtlas', '}));')
  ]),
  // Exact S09 lines reproduced as checked scaffolding, in source order.
  groundAssignments: Object.freeze([
    '\tprocCanvas$2 = document.createElement("canvas");',
    '\tprocCtx$2 = procCanvas$2.getContext("2d", { willReadFrequently: true });',
    '\t_textureAtlas = null;'
  ]),
  exposure: 'S09_Ground_vars_and_init_REFERENCE'
});
const EXEC_IDS = ['S01_esmMin', 'S02_Configs_region', 'S03_Targa_region', 'S04_libgif_region', 'S05_Texture_region',
  'S06_WebGL_region', 'S07_Ground_initTextures', 'S08_Ground_onTextureAtlasComplete'];
// Initializers and consumers the fixture must never contain or call.
// The final game initializer is a column-0 `init();` line; libgif's indented
// internal init() calls are part of the copied S04 region.
const FORBIDDEN = [/init_Ground\(/, /init_Water\(/, /init\$12\(/, /init\$13\(/, /init_Map\(/, /Water_default/, /Ground_default/, /^init\(\);$/m];

export class Refusal extends Error {
  constructor(code, detail) { super(`${code}: ${detail}`); this.code = code; }
}
const refuse = (code, detail) => { throw new Refusal(code, detail); };

export function descriptor(p) {
  const st = fs.lstatSync(p);
  if (!st.isFile()) refuse('input_not_regular_file', p);
  const bytes = fs.readFileSync(p);
  return { bytes, pin: { path: p, bytes: bytes.length, mtime_ms: st.mtimeMs, mode: (st.mode & 0o7777).toString(8), sha256: sha256(bytes) } };
}

const lineAt = (buf, start) => { const end = buf.indexOf(10, start); return buf.subarray(start, end < 0 ? buf.length : end).toString('utf8'); };

// Independently recompute every coordinate of one pinned slice.
export function verifySlice(src, pin) {
  const { byte_offset: off, byte_length: len } = pin;
  if (!Number.isInteger(off) || !Number.isInteger(len) || off < 0 || len <= 0 || off + len > src.length) refuse('slice_out_of_range', pin.slice);
  if (off > 0 && src[off - 1] !== 10) refuse('slice_not_line_start', pin.slice);
  const bytes = src.subarray(off, off + len);
  if (bytes[len - 1] !== 10) refuse('slice_not_lf_terminated', pin.slice);
  let lf = 1;
  for (let i = 0; i < off; i++) if (src[i] === 10) lf++;
  let lines = 0;
  for (let i = 0; i < len; i++) if (bytes[i] === 10) lines++;
  if (lf !== pin.lf_start || lf + lines - 1 !== pin.lf_end) refuse('slice_lf_mismatch', `${pin.slice} ${lf}-${lf + lines - 1}`);
  if (sha256(bytes) !== pin.sha256) refuse('slice_sha_mismatch', pin.slice);
  const text = bytes.toString('utf8');
  const all = text.slice(0, -1).split('\n'); // .014 'first' values are line prefixes
  if (!all[0].startsWith(pin.first) || all[all.length - 1] !== pin.last) refuse('slice_boundary_text_mismatch', pin.slice);
  return { bytes, recomputed: { lf_start: lf, lf_end: lf + lines - 1, byte_offset: off, byte_length: len, sha256: sha256(bytes) } };
}

export function verifySource(src, profile) {
  if (src.length !== profile.source.bytes || sha256(src) !== profile.source.sha256) refuse('source_pin_mismatch', `${src.length}`);
  const ids = profile.slices.map((s) => s.slice);
  const exec = profile.slices.filter((s) => s.use === 'exec').map((s) => s.slice);
  if (JSON.stringify(exec) !== JSON.stringify(EXEC_IDS) || !ids.includes(profile.exposure) || ids.length !== EXEC_IDS.length + 1) refuse('unexpected_slice_scope', ids.join(','));
  const out = new Map();
  for (const pin of profile.slices) out.set(pin.slice, verifySlice(src, pin));
  // S09 must contain the three ground assignments as exact whole lines, in order.
  const refLines = out.get(profile.exposure).bytes.toString('utf8').split('\n');
  let at = -1;
  for (const want of profile.groundAssignments) {
    const i = refLines.indexOf(want, at + 1);
    if (i < 0) refuse('ground_assignment_not_in_S09', want);
    at = i;
  }
  return out;
}

// Optional explicit .014 metadata: rows must equal this builder's pinned table.
export function verifyMetadata(buf, profile) {
  if (buf.length !== profile.metadata.bytes || sha256(buf) !== profile.metadata.sha256) refuse('metadata_pin_mismatch', `${buf.length}`);
  const meta = JSON.parse(buf.toString('utf8'));
  for (const pin of profile.slices) {
    const m = (meta.slices || []).find((s) => s.slice === pin.slice);
    if (!m) refuse('metadata_row_missing', pin.slice);
    for (const k of ['use', 'lf_start', 'lf_end', 'byte_offset', 'byte_length', 'sha256', 'first', 'last']) {
      if (m[k] !== pin[k]) refuse('metadata_row_mismatch', `${pin.slice}.${k}`);
    }
  }
  return { rows_checked: profile.slices.length };
}

// Assemble production.js: pinned scaffold spans around byte-identical slices.
export function assembleProduction(slices, profile) {
  const spans = [];
  const parts = [];
  let offset = 0;
  const push = (kind, id, bytes, extra = {}) => {
    spans.push({ kind, id, offset, length: bytes.length, sha256: sha256(bytes), ...extra });
    parts.push(bytes);
    offset += bytes.length;
  };
  push('scaffold', 'prelude', Buffer.from([
    `// ${TASK} fixture realm. Scaffold spans and production slices are pinned in MANIFEST.json.`,
    '// Production bytes below are unchanged copies; only scaffold spans are authored.',
    'window.__imageConsumerFixtureRealm = (function imageConsumerFixtureRealm() {',
    'var procCanvas$2, procCtx$2, _textureAtlas;',
    ''
  ].join('\n')));
  for (const id of EXEC_IDS) {
    const pin = profile.slices.find((s) => s.slice === id);
    push('production', id, slices.get(id).bytes, { source_offset: pin.byte_offset, source_lf_start: pin.lf_start });
  }
  push('scaffold', 'init_WebGL_only', Buffer.from('init_WebGL();\n'));
  push('scaffold', 'S09_checked_ground_assignments', Buffer.from(profile.groundAssignments.join('\n') + '\n'),
    { checked_against: profile.exposure });
  push('scaffold', 'accessors', Buffer.from([
    'return Object.freeze({',
    '\twebgl: () => WebGL_default,',
    '\ttexture: () => Texture,',
    '\tconfigs: () => Configs,',
    '\tinitTextures: initTextures,',
    '\tprocCanvas3: () => procCanvas$3,',
    '\tgroundCanvas: () => procCanvas$2,',
    '\tgroundContext: () => procCtx$2,',
    '\tgroundAtlasTexture: () => _textureAtlas',
    '});',
    '})();',
    ''
  ].join('\n')));
  const production = Buffer.concat(parts);
  const scaffoldText = spans.filter((s) => s.kind === 'scaffold').map((s) => production.subarray(s.offset, s.offset + s.length).toString('utf8')).join('');
  const allText = production.toString('utf8');
  for (const token of FORBIDDEN) if (token.test(allText)) refuse('forbidden_initializer_in_fixture', String(token));
  if (/\b(fetch|XMLHttpRequest|import\()/.test(scaffoldText)) refuse('unexpected_scaffold_scope', 'network-capable token');
  return { production, spans };
}

// ---- Authored tiny images and independently specified expectations ----

export function encodeBmp24(width, height, rgbRows) {
  const stride = Math.ceil((width * 3) / 4) * 4;
  const size = 54 + stride * height;
  const b = Buffer.alloc(size);
  b.write('BM', 0, 'latin1');
  b.writeUInt32LE(size, 2);
  b.writeUInt32LE(54, 10);
  b.writeUInt32LE(40, 14);
  b.writeInt32LE(width, 18);
  b.writeInt32LE(height, 22); // positive: bottom-up rows
  b.writeUInt16LE(1, 26);
  b.writeUInt16LE(24, 28);
  b.writeUInt32LE(0, 30); // BI_RGB
  b.writeUInt32LE(stride * height, 34);
  b.writeInt32LE(2835, 38);
  b.writeInt32LE(2835, 42);
  for (let y = 0; y < height; y++) {
    const at = 54 + (height - 1 - y) * stride;
    for (let x = 0; x < width; x++) {
      const [r, g, bl] = rgbRows[y][x];
      b[at + x * 3] = bl; b[at + x * 3 + 1] = g; b[at + x * 3 + 2] = r;
    }
  }
  return b;
}

// Hand-built baseline JPEG: one 8x8 YCbCr MCU (1x1 sampling), unit quantizers,
// DC-only coefficients, tiny custom Huffman tables. Each plane is solid.
export function encodeSolidJpeg8({ y, cb, cr }) {
  const dcSymbols = [0, 9, 10];
  const category = (v) => (v === 0 ? 0 : Math.floor(Math.log2(Math.abs(v))) + 1);
  const dcCode = { 0: '00', 9: '01', 10: '10' };
  let bits = '';
  for (const level of [y, cb, cr]) {
    const diff = (level - 128) * 8; // DC = 8 * (sample - 128) for a flat block, Q = 1
    const s = category(diff);
    if (!dcSymbols.includes(s)) throw new Error(`unsupported DC category ${s}`);
    bits += dcCode[s];
    if (s) bits += (diff >= 0 ? diff : diff + (1 << s) - 1).toString(2).padStart(s, '0');
    bits += '0'; // AC EOB
  }
  while (bits.length % 8) bits += '1';
  const scan = [];
  for (let i = 0; i < bits.length; i += 8) {
    const v = parseInt(bits.slice(i, i + 8), 2);
    scan.push(v);
    if (v === 0xff) scan.push(0);
  }
  const seg = (marker, body) => [0xff, marker, (body.length + 2) >> 8, (body.length + 2) & 255, ...body];
  const dcBits = Array(16).fill(0); dcBits[1] = 3;
  const acBits = Array(16).fill(0); acBits[0] = 1;
  return Buffer.from([
    0xff, 0xd8,
    ...seg(0xe0, [0x4a, 0x46, 0x49, 0x46, 0, 1, 1, 0, 0, 1, 0, 1, 0, 0]),
    ...seg(0xdb, [0, ...Array(64).fill(1)]),
    ...seg(0xc0, [8, 0, 8, 0, 8, 3, 1, 0x11, 0, 2, 0x11, 0, 3, 0x11, 0]),
    ...seg(0xc4, [0x00, ...dcBits, ...dcSymbols, 0x10, ...acBits, 0]),
    ...seg(0xda, [3, 1, 0, 2, 0, 3, 0, 0, 63, 0]),
    ...scan,
    0xff, 0xd9
  ]);
}

const T = [0, 0, 0, 0];
const px = (x, y, rgba, tol) => ({ x, y, rgba, tol });
const opaque = ([r, g, b]) => [r, g, b, 255];

export function authorFixtures() {
  // Quadrant BMP 2x2: TL/TR/BL/BR distinct, none magenta.
  const Q = { tl: [200, 30, 40], tr: [20, 180, 60], bl: [40, 50, 220], br: [250, 250, 250] };
  const quadrant = encodeBmp24(2, 2, [[Q.tl, Q.tr], [Q.bl, Q.br]]);
  // Magenta 4x1 threshold row: (255,0,255) and (231,19,231) clear; (230,0,255) and (255,20,255) remain.
  const M = [[255, 0, 255], [231, 19, 231], [230, 0, 255], [255, 20, 255]];
  const magenta = encodeBmp24(4, 1, [M]);
  // NPOT 3x5: distinct corners, neutral interior.
  const N = { tl: [200, 40, 40], tr: [40, 200, 40], bl: [40, 40, 200], br: [220, 220, 40], m: [90, 90, 90] };
  const npotRows = Array.from({ length: 5 }, (_, y) => Array.from({ length: 3 }, (_, x) =>
    (y === 0 && x === 0 ? N.tl : y === 0 && x === 2 ? N.tr : y === 4 && x === 0 ? N.bl : y === 4 && x === 2 ? N.br : N.m)));
  const npot = encodeBmp24(3, 5, npotRows);
  // Solid baseline JPEG Y=96 Cb=128 Cr=200 -> JFIF RGB ~ (197, 45, 96); tolerance 6.
  const jpeg = encodeSolidJpeg8({ y: 96, cb: 128, cr: 200 });
  const J = [197, 45, 96];
  // Truncated BMP signature with no info header: authored malformed bytes.
  const malformed = Buffer.from('424d0e000000000000000e000000', 'hex');

  const img = (id, mime, bytes, width, height, note) => ({ id, mime, bytes: bytes.length, sha256: sha256(bytes), width, height, base64: bytes.toString('base64'), note });
  const images = [
    img('bmp_quadrant_2x2', 'image/bmp', quadrant, 2, 2, '24-bit BI_RGB bottom-up'),
    img('bmp_magenta_4x1', 'image/bmp', magenta, 4, 1, '24-bit BI_RGB bottom-up'),
    img('bmp_npot_3x5', 'image/bmp', npot, 3, 5, '24-bit BI_RGB bottom-up'),
    img('jpeg_solid_8x8', 'image/jpeg', jpeg, 8, 8, 'baseline SOF0, 3 components 1x1, DC-only'),
    img('malformed_bmp_14b', 'image/bmp', malformed, null, null, 'BM signature, no info header')
  ];

  // Ground atlas: one texture -> 512x512; 258x258 stretch at (0,0), 256x256 at (1,1).
  // Probes sit in edge-clamped regions or uniform neighbourhoods so bilinear
  // stretch cannot blend distinct authored colors.
  const quadrantExpect = {
    completion: { width: 2, height: 2, pixels: [px(0, 0, opaque(Q.tl), 2), px(1, 0, opaque(Q.tr), 2), px(0, 1, opaque(Q.bl), 2), px(1, 1, opaque(Q.br), 2)] },
    water: { upload: { width: 2, height: 2 }, pixels: [px(0, 0, opaque(Q.tl), 2), px(1, 0, opaque(Q.tr), 2), px(0, 1, opaque(Q.bl), 2), px(1, 1, opaque(Q.br), 2)] },
    ground: { upload: { width: 512, height: 512 }, pixels: [
      px(17, 17, opaque(Q.tl), 2), px(241, 17, opaque(Q.tr), 2), px(17, 241, opaque(Q.bl), 2), px(241, 241, opaque(Q.br), 2),
      px(0, 0, opaque(Q.tl), 2), px(257, 0, opaque(Q.tr), 2), px(0, 257, opaque(Q.bl), 2), px(257, 257, opaque(Q.br), 2),
      px(258, 0, T, 0), px(0, 258, T, 0), px(400, 400, T, 0)] }
  };
  const magentaExpect = {
    completion: { width: 4, height: 1, pixels: [px(0, 0, T, 0), px(1, 0, T, 0), px(2, 0, opaque(M[2]), 2), px(3, 0, opaque(M[3]), 2)] },
    preMagenta: { width: 4, height: 1, pixels: M.map((c, x) => px(x, 0, opaque(c), 2)) },
    water: { upload: { width: 4, height: 1 }, pixels: [px(0, 0, T, 0), px(1, 0, T, 0), px(2, 0, opaque(M[2]), 2), px(3, 0, opaque(M[3]), 2)] },
    ground: { upload: { width: 512, height: 512 }, pixels: [
      px(17, 129, T, 0), px(96, 129, T, 0), px(161, 129, opaque(M[2]), 3), px(241, 129, opaque(M[3]), 2),
      px(0, 129, T, 0), px(257, 129, opaque(M[3]), 2), px(258, 129, T, 0)] }
  };
  const npotExpect = {
    completion: { width: 3, height: 5, pixels: npotRows.flatMap((r, y) => r.map((c, x) => px(x, y, opaque(c), 2))) },
    water: { upload: { width: 4, height: 8 }, pixels: [
      px(0, 0, opaque(N.tl), 2), px(3, 0, opaque(N.tr), 2), px(0, 7, opaque(N.bl), 2), px(3, 7, opaque(N.br), 2),
      px(1, 3, opaque(N.m), 2), px(2, 4, opaque(N.m), 2)] },
    ground: { upload: { width: 512, height: 512 }, pixels: [
      px(6, 6, opaque(N.tl), 2), px(251, 6, opaque(N.tr), 2), px(6, 251, opaque(N.bl), 2), px(251, 251, opaque(N.br), 2),
      px(129, 129, opaque(N.m), 2), px(0, 0, opaque(N.tl), 2), px(257, 0, opaque(N.tr), 2), px(0, 257, opaque(N.bl), 2),
      px(257, 257, opaque(N.br), 2), px(258, 0, T, 0), px(0, 258, T, 0)] }
  };
  const jpegExpect = {
    completion: { width: 8, height: 8, pixels: [px(0, 0, opaque(J), 6), px(7, 0, opaque(J), 6), px(0, 7, opaque(J), 6), px(7, 7, opaque(J), 6), px(4, 4, opaque(J), 6)] },
    water: { upload: { width: 8, height: 8 }, pixels: [px(0, 0, opaque(J), 6), px(7, 7, opaque(J), 6), px(3, 4, opaque(J), 6)] },
    ground: { upload: { width: 512, height: 512 }, pixels: [px(129, 129, opaque(J), 6), px(0, 0, opaque(J), 6), px(257, 257, opaque(J), 6), px(258, 258, T, 0)] }
  };
  const blankGround = { upload: { width: 512, height: 512 }, pixels: [px(0, 0, T, 0), px(129, 129, T, 0), px(511, 511, T, 0)] };

  const C = (id, kind, image, expect, extra = {}) => ({ id, kind, image, consumers: ['ground', 'water'], enableMipmap: false, url: 'page', expect, ...extra });
  const controls = [
    C('C1a-bmp-quadrant', 'valid', 'bmp_quadrant_2x2', quadrantExpect),
    C('C1b-jpeg-solid', 'valid', 'jpeg_solid_8x8', jpegExpect),
    C('C2-magenta-threshold', 'valid', 'bmp_magenta_4x1', magentaExpect),
    C('C3-npot-resize', 'valid', 'bmp_npot_3x5', npotExpect),
    C('C4-null-input', 'null', null, { ground: blankGround, water: null }),
    C('C5-malformed-timeout', 'malformed', 'malformed_bmp_14b', null, { timeoutMs: 1200 }),
    C('C6a-native-lose-context', 'lose_context', 'bmp_quadrant_2x2', quadrantExpect),
    C('C6b-observer-injected-gl-error', 'injected_gl_error', 'bmp_quadrant_2x2', quadrantExpect),
    C('C7-closed-late-completion', 'closed_late', 'bmp_quadrant_2x2', quadrantExpect, { lateWindowMs: 1500 }),
    C('C8a-mipmap-false', 'valid', 'bmp_quadrant_2x2', quadrantExpect, { enableMipmap: false, mipmapControl: true }),
    C('C8b-mipmap-true', 'valid', 'bmp_quadrant_2x2', quadrantExpect, { enableMipmap: true, mipmapControl: true }),
    C('C8c-worker-blob-url', 'valid', 'bmp_quadrant_2x2', quadrantExpect, { url: 'worker' })
  ];
  return { schema: FIXTURES_SCHEMA, limits: LIMITS, images, controls };
}

export function checkFixtureLimits(fixtures) {
  for (const im of fixtures.images) {
    const bytes = Buffer.from(im.base64, 'base64');
    if (bytes.length > LIMITS.maxEncodedBytes || bytes.length !== im.bytes || sha256(bytes) !== im.sha256) refuse('fixture_image_limit', im.id);
    if (im.width !== null && (im.width > LIMITS.maxDimension || im.height > LIMITS.maxDimension || im.width < 1 || im.height < 1)) refuse('fixture_dimension_limit', im.id);
  }
  return true;
}

// ---- Publication ----

export function parseArgs(argv) {
  const allowed = new Set(['--source', '--metadata', '--out']);
  const opts = {};
  for (let i = 0; i < argv.length; i += 2) {
    const k = argv[i];
    const v = argv[i + 1];
    if (!allowed.has(k) || v === undefined || k in opts) refuse('unexpected_argument', String(k));
    opts[k] = v;
  }
  if (!opts['--source'] || !opts['--out']) refuse('missing_argument', '--source and --out are required');
  return { sourcePath: opts['--source'], metadataPath: opts['--metadata'] || null, outPath: opts['--out'] };
}

function checkScope({ sourcePath, metadataPath, outPath }) {
  for (const p of [sourcePath, metadataPath, outPath]) {
    if (p === null) continue;
    if (!path.isAbsolute(p) || path.normalize(p) !== p || p.endsWith(path.sep)) refuse('path_not_absolute_normal', p);
  }
  if (fs.existsSync(outPath) || isSymlink(outPath)) refuse('output_exists', outPath);
  const parent = path.dirname(outPath);
  if (!fs.existsSync(parent) || !fs.lstatSync(parent).isDirectory()) refuse('output_parent_missing', parent);
  for (const input of [sourcePath, metadataPath]) {
    if (input === null) continue;
    const rel = path.relative(path.dirname(input), outPath);
    if (!rel.startsWith('..') && !path.isAbsolute(rel)) refuse('output_inside_input_directory', outPath);
  }
}
const isSymlink = (p) => { try { return fs.lstatSync(p).isSymbolicLink(); } catch { return false; } };

// Publication: exclusive directory, exclusive files, cleanup of own paths only.
export function publish(outPath, files) {
  const created = [];
  try {
    fs.mkdirSync(outPath, { mode: 0o700 });
    created.push(outPath);
    for (const [name, b] of files) {
      const p = path.join(outPath, name);
      fs.writeFileSync(p, b, { flag: 'wx', mode: 0o600 });
      created.push(p);
    }
    const listed = fs.readdirSync(outPath).sort();
    if (JSON.stringify(listed) !== JSON.stringify([...files.keys()].sort())) refuse('unexpected_output_entries', listed.join(','));
    for (const [name, b] of files) if (!fs.readFileSync(path.join(outPath, name)).equals(b)) refuse('published_bytes_mismatch', name);
  } catch (e) {
    for (const p of created.slice().reverse()) {
      try { if (p === outPath) fs.rmdirSync(p); else fs.unlinkSync(p); } catch { /* keep going: only own paths */ }
    }
    throw e;
  }
  return created;
}

export function buildFixture({ sourcePath, metadataPath = null, outPath, driverPath = DRIVER_PATH }, profile = DEFAULT_PROFILE) {
  checkScope({ sourcePath, metadataPath, outPath });
  const pre = { source: descriptor(sourcePath), metadata: metadataPath ? descriptor(metadataPath) : null };
  const slices = verifySource(pre.source.bytes, profile);
  const metadataCheck = pre.metadata ? verifyMetadata(pre.metadata.bytes, profile) : null;
  const driver = fs.readFileSync(driverPath);
  if (driver.length !== profile.driver.bytes || sha256(driver) !== profile.driver.sha256) refuse('driver_pin_mismatch', `${driver.length} ${sha256(driver)}`);
  const { production, spans } = assembleProduction(slices, profile);
  for (const s of spans) {
    const got = production.subarray(s.offset, s.offset + s.length);
    if (sha256(got) !== s.sha256) refuse('assembled_span_mismatch', s.id);
    if (s.kind === 'production' && !got.equals(pre.source.bytes.subarray(s.source_offset, s.source_offset + s.length))) refuse('assembled_production_not_source', s.id);
  }
  const fixtures = authorFixtures();
  checkFixtureLimits(fixtures);
  const fixturesJs = Buffer.from(`// ${TASK} authored tiny fixtures; expectations are independent constants.\nwindow.__IMAGE_CONSUMER_FIXTURES = ${JSON.stringify(fixtures, null, 1)};\n`);
  const realmHtml = Buffer.from('<!doctype html>\n<html><head><meta charset="utf-8"><title>fixture realm</title></head><body></body></html>\n');
  const indexHtml = Buffer.from([
    '<!doctype html>',
    '<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">',
    `<title>${TASK} image consumer fixture</title>`,
    '<style>body{font:14px system-ui,sans-serif;margin:16px;background:#fff;color:#111}button{margin:3px;padding:6px 10px;font-size:14px}',
    'pre{white-space:pre-wrap;word-break:break-all;background:#f4f4f4;padding:8px;max-height:60vh;overflow:auto}#realms{position:absolute;left:-9999px;top:0}</style>',
    '</head><body>',
    `<h1>${TASK} authored image-consumer fixture</h1>`,
    '<p>Authored tiny images only. One control runs at a time in a fresh iframe realm. Records are JSON below and in <code>window.__imageConsumerFixtureRecords</code>.</p>',
    '<div id="status" data-state="loading">loading</div>',
    '<div id="controls"></div>',
    '<h2>Summary</h2><pre id="summary">[]</pre>',
    '<h2>Records</h2><pre id="records">[]</pre>',
    '<div id="realms" aria-hidden="true"></div>',
    '<script src="fixtures.js"></script>',
    '<script src="driver.js"></script>',
    '</body></html>',
    ''
  ].join('\n'));

  const files = new Map([
    ['index.html', indexHtml], ['realm.html', realmHtml], ['production.js', production],
    ['fixtures.js', fixturesJs], ['driver.js', driver]
  ]);
  const postSource = descriptor(sourcePath);
  const postMeta = metadataPath ? descriptor(metadataPath) : null;
  const pinOf = (d) => d && { path: d.pin.path, bytes: d.pin.bytes, mtime_ms: d.pin.mtime_ms, mode: d.pin.mode, sha256: d.pin.sha256 };
  if (JSON.stringify(pinOf(postSource)) !== JSON.stringify(pinOf(pre.source)) || JSON.stringify(pinOf(postMeta)) !== JSON.stringify(pinOf(pre.metadata))) refuse('input_changed_during_build', sourcePath);
  const manifest = {
    schema: MANIFEST_SCHEMA,
    task: TASK,
    inputs: { pre: { source: pinOf(pre.source), metadata: pinOf(pre.metadata) }, post: { source: pinOf(postSource), metadata: pinOf(postMeta) }, metadata_rows_checked: metadataCheck && metadataCheck.rows_checked },
    slices: profile.slices.map((p) => ({ ...p, recomputed: slices.get(p.slice).recomputed })),
    production: { bytes: production.length, sha256: sha256(production), spans },
    driver: { bytes: driver.length, sha256: sha256(driver) },
    fixture_images: fixtures.images.map(({ id, mime, bytes, sha256: h, width, height }) => ({ id, mime, bytes, sha256: h, width, height })),
    files: [...files].map(([name, b]) => ({ name, bytes: b.length, sha256: sha256(b) })),
    limits: LIMITS
  };
  files.set('MANIFEST.json', Buffer.from(JSON.stringify(manifest, null, 1) + '\n'));

  publish(outPath, files);
  return { outPath, manifest };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const { manifest, outPath } = buildFixture(parseArgs(process.argv.slice(2)));
    const mf = fs.readFileSync(path.join(outPath, 'MANIFEST.json'));
    process.stdout.write(JSON.stringify({ ok: true, out: outPath, manifest_sha256: sha256(mf), manifest_bytes: mf.length, production: { bytes: manifest.production.bytes, sha256: manifest.production.sha256 }, files: manifest.files }, null, 1) + '\n');
  } catch (e) {
    process.stderr.write(JSON.stringify({ ok: false, code: e.code || 'error', message: e.message }) + '\n');
    process.exit(2);
  }
}
