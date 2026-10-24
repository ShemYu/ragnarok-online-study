#!/usr/bin/env node
// T07.007.014.021: finite pure decoder observer for the 25 retained TGA bodies.
//
//   /usr/bin/perl -e 'alarm shift; exec @ARGV or die "exec: $!"' 15 \
//     node --max-old-space-size=125 --max-semi-space-size=1 \
//     tools/renewal/observe_tga_decode.mjs --actual \
//     --profile <absolute PROFILE_ROOT.json> --private-prefix <absolute ignored dir>
//
// Root alone decides when to invoke --actual; the profile's
// profile_admits_execution:false grants nothing and no test runs it. The perl
// alarm is the real finite external guard: SIGALRM terminates the process even
// inside synchronous IO/VM/host work, which the in-process deadline cannot
// interrupt. The effective V8 heap is checked (heap_size_limit), never flag
// membership; it is not an RSS or external-memory cap.
//
// Mechanism: exact argv only; heap and endianness are refused before any IO.
// Profile and source are read once through held O_NOFOLLOW descriptors with
// pinned size/SHA and lossless BigInt C8 identities rechecked through final
// use. The whole profile schema, closed 25-row order and resource totals are
// validated before any body is opened. Three whole LF spans (checkHeader,
// decodeRLE, Targa assignment) are reconstructed byte-identically from the
// inert source; the bundle and its initializer graph are never evaluated. Each
// body is pinned (SHA/C8/header18/footer26), header-parsed independently and
// copied with the host intrinsic typed-array setter into a Uint8Array created
// inside one fresh realm per body. Only the copied definitions plus
// Targa.load/getImageData run there. The returned RGBA is brand/length/extent
// checked and hashed outside the VM. Outputs go to a fresh exclusive 0700 run
// directory as 0600 files; PASS is published only by linking a bounded
// candidate after every pin, identity and deadline check succeeded.
import { createHash, randomBytes } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { performance } from 'node:perf_hooks';
import { pathToFileURL } from 'node:url';
import { types } from 'node:util';
import v8 from 'node:v8';
import vm from 'node:vm';

export const TASK = 'T07.007.014.021';
export const PROFILE_SCHEMA = 't07-014-021-retained-tga-decode-profile-v1';
export const RESULT_SCHEMA = 't07-014-021-retained-tga-decode-observation-v1';
const sha256 = (b) => createHash('sha256').update(b).digest('hex');

export const PROFILE_PIN = Object.freeze({ bytes: 37776, sha256: '91006dc3379de4341858e804297d382a9af95cbb10e1515b21556265963961fe' });
export const SOURCE_PIN = Object.freeze({ bytes: 13174290, sha256: '50b724b708393d7bb6d71b4f5102e62b16e340eb1bb54f05b1c8613af4116418' });
export const FIXTURE_PIN = Object.freeze({ bytes: 26646, sha256: '4bbabdb5ceae3dfb6192bf883348415fe6d3a7d6e4674d5a023fdb97964c1fd1' });
const span = (id, start_line, end_line, byte_offset, byte_length, sha) =>
  Object.freeze({ id, start_line, end_line, byte_offset, byte_length, sha256: sha });
export const SPANS = Object.freeze([
  span('checkHeader', 79207, 79214, 3637537, 751, '6bac6e2ffe5c379fc4badabf2dec88a39a3703ef368ba575d8f452885ea790eb'),
  span('decodeRLE', 79223, 79243, 3638470, 544, 'b959a77b6cdcd566bfc6b0490456f543141acf9c62d069226f156e59e3d192fb'),
  span('Targa_assignment', 79246, 79462, 3639060, 7029, '8441ff82a462a2c98c53417f94bea51e4470d2d1bf462889e29c84869645471f'),
]);
export const IDENTITY_FIELDS = Object.freeze(['st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_mode', 'st_nlink', 'st_uid']);
export const QUERY_INDICES = Object.freeze([0, 12, 21, 24, 36, 40, 69, 72, 73, 84, 85, 111, 114, 115, 116, 120, 121, 123, 416, 433, 442, 454, 569, 837, 839]);
export const COUNTS = Object.freeze({ queries: 25, body_bytes: 17695820, rgba_bytes: 17842176 });
export const PROFILE_BOUNDS = Object.freeze({
  max_body_bytes: 8388608, max_width: 1024, max_height: 1024, max_pixels: 1048576, max_rgba_bytes: 4194304,
  max_body_total_bytes: 33554432, max_rgba_total_bytes: 33554432, per_vm_timeout_ms: 500,
  overall_command_ms: 10000, max_effective_v8_heap_bytes: 134217728, max_result_bytes: 1048576,
});
// .020 authored caps; tests may only execute copied source within these.
export const TINY_BOUNDS = Object.freeze({
  ...PROFILE_BOUNDS, max_body_bytes: 4096, max_width: 8, max_height: 8, max_pixels: 64, max_rgba_bytes: 256,
  max_body_total_bytes: 25 * 4096, max_rgba_total_bytes: 25 * 256, per_vm_timeout_ms: 100,
});
const HEADER_BYTES = 18;
const FOOTER_BYTES = 26;
const FOOTER_SIGNATURE = Buffer.from('TRUEVISION-XFILE.\0', 'latin1');
const MAX_FAILURE_TEXT = 2000;

export class ObserverRefusal extends Error {
  constructor(code, detail) { super(`${code}: ${detail}`); this.code = code; }
}
export class ObserverFailure extends Error {
  constructor(code, detail, stage) { super(`${code}: ${detail}`); this.code = code; this.stage = stage; }
}
const fail = (code, detail, stage) => { throw new ObserverFailure(code, detail, stage); };

// Host intrinsics captured before any realm exists; none are passed into it.
const TypedArrayProto = Object.getPrototypeOf(Uint8Array.prototype);
const callBound = (fn) => Function.prototype.call.bind(fn);
const taSet = callBound(TypedArrayProto.set);
const taLength = callBound(Object.getOwnPropertyDescriptor(TypedArrayProto, 'length').get);
const taByteOffset = callBound(Object.getOwnPropertyDescriptor(TypedArrayProto, 'byteOffset').get);
const taBuffer = callBound(Object.getOwnPropertyDescriptor(TypedArrayProto, 'buffer').get);
const abByteLength = callBound(Object.getOwnPropertyDescriptor(ArrayBuffer.prototype, 'byteLength').get);

// ---------------------------------------------------------------- guards

export function checkEffectiveHeap(stats = v8.getHeapStatistics(), max = PROFILE_BOUNDS.max_effective_v8_heap_bytes) {
  const limit = stats?.heap_size_limit;
  if (!Number.isSafeInteger(limit) || limit <= 0) throw new ObserverRefusal('effective_heap_unknown', String(limit));
  if (limit > max) throw new ObserverRefusal('effective_heap_exceeded', `${limit} > ${max}`);
  return limit;
}

export function checkLittleEndian(endianness = os.endianness()) {
  if (endianness !== 'LE') throw new ObserverRefusal('not_little_endian', String(endianness));
}

export function checkBoundsWithin(limits) {
  const keys = Object.keys(PROFILE_BOUNDS);
  if (!limits || Object.keys(limits).length !== keys.length) throw new ObserverRefusal('bad_limits', 'keys');
  for (const k of keys) {
    if (!Number.isSafeInteger(limits[k]) || limits[k] <= 0 || limits[k] > PROFILE_BOUNDS[k]) throw new ObserverRefusal('bad_limits', k);
  }
  return limits;
}

export function makeDeadline(totalMs, clock = () => performance.now()) {
  const start = clock();
  const end = start + totalMs;
  return {
    clock,
    start,
    elapsed: () => clock() - start,
    remaining: () => end - clock(),
    check(stage) {
      const left = end - clock();
      if (!(left > 0)) fail('deadline_exceeded', `command deadline ${totalMs}ms passed`, stage);
      return left;
    },
  };
}

// ---------------------------------------------------------------- held inputs

export const identityOf = (st) => [st.dev, st.ino, st.size, st.mtimeNs, st.ctimeNs, st.mode, st.nlink, st.uid].map((v) => v.toString(10));
const sameIdentity = (a, b) => a.length === b.length && a.every((v, i) => v === b[i]);
function parentPins(file) {
  const pins=[];
  for(let p=path.dirname(file);;p=path.dirname(p)) {
    const st=fs.lstatSync(p,{bigint:true});
    if(!st.isDirectory() || st.isSymbolicLink()) fail('input_ancestor','non-directory/symlink ancestor','identity');
    pins.push({path:p,identity:[st.dev,st.ino,st.mode,st.uid].map(String)});
    if(p===path.dirname(p))break;
  }
  return pins;
}
function checkParents(pins) {
  for(const pin of pins) {
    const st=fs.lstatSync(pin.path,{bigint:true});
    if(!st.isDirectory() || !sameIdentity(pin.identity,[st.dev,st.ino,st.mode,st.uid].map(String)))fail('input_ancestor','ancestor changed','identity');
  }
}


// Reads one regular single-link file through a held O_NOFOLLOW descriptor.
// expect = { bytes, sha256, identity?: 8 canonical decimal strings }.
export function readHeldInput(file, expect, maxBytes, deadline, stage) {
  if (typeof file !== 'string' || !path.isAbsolute(file) || path.normalize(file) !== file) fail('bad_path', 'absolute normalized path required', stage);
  if (!Number.isSafeInteger(expect.bytes) || expect.bytes < 0 || expect.bytes > maxBytes) fail('input_over_cap', `${expect.bytes} > ${maxBytes}`, stage);
  deadline.check(stage);
  const parents=parentPins(file);
  const pre = fs.lstatSync(file, { bigint: true });
  if (pre.isSymbolicLink()) fail('symlink', 'leaf symlink refused', stage);
  if (!pre.isFile()) fail('not_regular', 'regular file required', stage);
  if (pre.nlink !== 1n) fail('link_count', `nlink ${pre.nlink}`, stage);
  const literal = identityOf(pre);
  if (expect.identity && !sameIdentity(literal, expect.identity)) fail('identity_mismatch', 'path identity differs from pin', stage);
  if (pre.size !== BigInt(expect.bytes)) fail('size_mismatch', `${pre.size} != ${expect.bytes}`, stage);
  const fd = fs.openSync(file, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW);
  let open = true;
  const descriptorIdentity = () => identityOf(fs.fstatSync(fd, { bigint: true }));
  const verifyLiteral=(when)=>{
    checkParents(parents);
    const now=fs.lstatSync(file,{bigint:true});
    if(now.isSymbolicLink() || !sameIdentity(identityOf(now),literal))fail('identity_changed',`path ${when}`,stage);
  };
  const verify = (when) => {
    if (!open) fail('descriptor_closed', when, stage);
    if (!sameIdentity(descriptorIdentity(), literal)) fail('identity_changed', `descriptor ${when}`, stage);
    verifyLiteral(when);
  };
  try {
    verify('before_read');
    let bytes = Buffer.alloc(expect.bytes);
    let got = 0;
    while (got < expect.bytes) {
      deadline.check(stage);
      const n = fs.readSync(fd, bytes, got, Math.min(65536,expect.bytes - got), got);
      if (n === 0) fail('short_read', `${got} < ${expect.bytes}`, stage);
      got += n;
    }
    if (fs.readSync(fd, Buffer.alloc(1), 0, 1, got) !== 0) fail('extra_bytes', `more than ${expect.bytes}`, stage);
    const digest = sha256(bytes);
    if (digest !== expect.sha256) fail('sha_mismatch', digest, stage);
    verify('after_read');
    deadline.check(stage);
    return {
      bytes,
      identity: literal,
      sha256: digest,
      recheck: (when) => verify(when),
      literalRecheck: (when) => verifyLiteral(when),
      releaseBytes() { bytes=null;this.bytes=null; },
      close() { if (open) { open = false; fs.closeSync(fd); } },
    };
  } catch (e) {
    open = false;
    fs.closeSync(fd);
    throw e;
  }
}

// ---------------------------------------------------------------- profile

const DECIMAL = /^(0|[1-9][0-9]*)$/;
const HEX64 = /^[0-9a-f]{64}$/;
const WIRE = /^\/data\/texture\/(?:[A-Za-z0-9_-]+\/)*[A-Za-z0-9_-]+\.(?:tga|TGA)$/;
const MAX_U64 = (1n << 64n) - 1n;

function exactKeys(obj, keys, where) {
  if (!obj || typeof obj !== 'object' || Array.isArray(obj)) fail('profile_schema', `${where} not object`, 'profile');
  const got = Object.keys(obj);
  if (got.length !== keys.length || keys.some((k, i) => got[i] !== k)) fail('profile_schema', `${where} keys ${got.join(',')}`, 'profile');
}
const intIn = (v, lo, hi, where) => { if (!Number.isSafeInteger(v) || v < lo || v > hi) fail('profile_schema', `${where}=${v}`, 'profile'); return v; };
const eq = (v, want, where) => { if (v !== want) fail('profile_schema', `${where}=${JSON.stringify(v)}`, 'profile'); };
function identityStrings(v, size, where) {
  if (!Array.isArray(v) || v.length !== 8) fail('profile_schema', `${where} length`, 'profile');
  for (const s of v) if (typeof s !== 'string' || !DECIMAL.test(s) || BigInt(s) > MAX_U64) fail('profile_schema', `${where} not canonical decimal`, 'profile');
  if (v[2] !== String(size)) fail('profile_schema', `${where} size`, 'profile');
  if (v[6] !== '1') fail('profile_schema', `${where} nlink`, 'profile');
  return Object.freeze([...v]);
}
function absPath(v, where) {
  if (typeof v !== 'string' || !path.isAbsolute(v) || path.normalize(v) !== v || v.includes('\0')) fail('profile_schema', `${where} path`, 'profile');
  return v;
}

// Independent raw TGA header parse (no decoder code involved).
export function parseRawHeader(bytes) {
  if (bytes.length < HEADER_BYTES) return null;
  const u16 = (o) => bytes[o] | (bytes[o + 1] << 8);
  return {
    id_length: bytes[0], color_map_type: bytes[1], image_type: bytes[2], color_map_index: u16(3),
    color_map_length: u16(5), color_map_depth: bytes[7], x_origin: u16(8), y_origin: u16(10),
    width: u16(12), height: u16(14), pixel_depth: bytes[16], flags: bytes[17],
  };
}

// Supported subset: raw type 2, no ID/palette, 24/32bit, positive bounded
// dimensions and a complete pixel interval. Returns the footprint.
export function checkRawHeader(h, limits, where) {
  if (!h) fail('header_short', where, 'header');
  if (h.id_length !== 0 || h.color_map_type !== 0 || h.color_map_index !== 0 || h.color_map_length !== 0 || h.color_map_depth !== 0) fail('header_unsupported', `${where} id/palette`, 'header');
  if (h.image_type !== 2) fail('header_unsupported', `${where} type ${h.image_type}`, 'header');
  if (h.pixel_depth !== 24 && h.pixel_depth !== 32) fail('header_unsupported', `${where} depth ${h.pixel_depth}`, 'header');
  const alphaBits = h.flags & 15;
  const alphaOk = h.pixel_depth === 32 ? alphaBits === 0 || alphaBits === 8 : alphaBits === 0;
  if ((h.flags & 0xc0) !== 0 || !alphaOk) fail('header_unsupported', `${where} flags ${h.flags}`, 'header');
  if (h.width <= 0 || h.height <= 0) fail('header_dimensions', `${where} zero dimension`, 'header');
  if (h.width > limits.max_width || h.height > limits.max_height) fail('over_cap', `${where} ${h.width}x${h.height}`, 'header');
  const pixels = h.width * h.height;
  if (pixels > limits.max_pixels) fail('over_cap', `${where} pixels ${pixels}`, 'header');
  const rgba = pixels * 4;
  if (rgba > limits.max_rgba_bytes) fail('over_cap', `${where} rgba ${rgba}`, 'header');
  const raw = pixels * (h.pixel_depth >> 3);
  return { pixels, raw_pixel_bytes: raw, rgba_bytes: rgba, header_plus_id_palette_bytes: HEADER_BYTES, raw_expected_end: HEADER_BYTES + raw, origin: (h.flags & 48) >> 4, alpha_bits: alphaBits };
}

const HEADER_KEYS = ['id_length', 'color_map_type', 'image_type', 'color_map_index', 'color_map_length', 'color_map_depth', 'x_origin', 'y_origin', 'width', 'height', 'pixel_depth', 'flags'];
const FOOTPRINT_KEYS = ['pixels', 'raw_pixel_bytes', 'rgba_bytes', 'header_plus_id_palette_bytes', 'raw_expected_end', 'trailing_bytes'];

// Validates the complete profile before any body is opened.
export function validateProfile(profile, { limits = PROFILE_BOUNDS, counts = COUNTS } = {}) {
  exactKeys(profile, ['schema', 'task', 'profile_admits_execution', 'input_provenance', 'source', 'source_spans', 'identity_fields', 'identity_encoding', 'bounds', 'query_indices', 'rows', 'counts', 'evidence_boundary'], 'profile');
  eq(profile.schema, PROFILE_SCHEMA, 'schema');
  eq(profile.task, TASK, 'task');
  eq(profile.profile_admits_execution, false, 'profile_admits_execution');
  const prov = profile.input_provenance;
  exactKeys(prov, ['headers', 'delivery_task', 'all_bodies_consumed_GETs'], 'input_provenance');
  exactKeys(prov.headers, ['bytes', 'sha256'], 'input_provenance.headers');
  intIn(prov.headers.bytes, 1, 1 << 30, 'headers.bytes');
  if (!HEX64.test(prov.headers.sha256)) fail('profile_schema', 'headers.sha256', 'profile');
  eq(prov.delivery_task, 'T07.007.014.017', 'delivery_task');
  eq(prov.all_bodies_consumed_GETs, true, 'all_bodies_consumed_GETs');
  const src = profile.source;
  exactKeys(src, ['path', 'bytes', 'sha256', 'identity_decimal'], 'source');
  absPath(src.path, 'source');
  eq(src.bytes, SOURCE_PIN.bytes, 'source.bytes');
  eq(src.sha256, SOURCE_PIN.sha256, 'source.sha256');
  identityStrings(src.identity_decimal, src.bytes, 'source.identity_decimal');
  if (!Array.isArray(profile.source_spans) || profile.source_spans.length !== SPANS.length) fail('profile_schema', 'source_spans', 'profile');
  SPANS.forEach((want, i) => {
    const got = profile.source_spans[i];
    exactKeys(got, Object.keys(want), `source_spans[${i}]`);
    for (const k of Object.keys(want)) eq(got[k], want[k], `source_spans[${i}].${k}`);
  });
  if (!Array.isArray(profile.identity_fields) || profile.identity_fields.join() !== IDENTITY_FIELDS.join() || profile.identity_fields.length !== 8) fail('profile_schema', 'identity_fields', 'profile');
  if (typeof profile.identity_encoding !== 'string' || !profile.identity_encoding.includes('decimal')) fail('profile_schema', 'identity_encoding', 'profile');
  exactKeys(profile.bounds, Object.keys(PROFILE_BOUNDS), 'bounds');
  for (const k of Object.keys(PROFILE_BOUNDS)) eq(profile.bounds[k], PROFILE_BOUNDS[k], `bounds.${k}`);
  if (!Array.isArray(profile.query_indices) || profile.query_indices.length !== QUERY_INDICES.length || QUERY_INDICES.some((q, i) => profile.query_indices[i] !== q)) fail('profile_schema', 'query_indices', 'profile');
  if (!Array.isArray(profile.rows) || profile.rows.length !== QUERY_INDICES.length) fail('profile_schema', 'rows length', 'profile');
  const seen = new Set();
  let bodyTotal = 0;
  let rgbaTotal = 0;
  const rows = profile.rows.map((r, i) => {
    const where = `rows[${i}]`;
    exactKeys(r, ['query_index', 'wire_target', 'source_batch', 'retained_body', 'header18_hex', 'header', 'footprint', 'footer26_hex'], where);
    eq(r.query_index, QUERY_INDICES[i], `${where}.query_index`);
    if (typeof r.wire_target !== 'string' || !WIRE.test(r.wire_target)) fail('profile_schema', `${where}.wire_target`, 'profile');
    if (r.source_batch !== 'pilot' && r.source_batch !== 'remainder') fail('profile_schema', `${where}.source_batch`, 'profile');
    const body = r.retained_body;
    exactKeys(body, ['path', 'bytes', 'sha256', 'identity_decimal'], `${where}.retained_body`);
    absPath(body.path, where);
    if (path.basename(body.path) !== `body-${String(r.query_index).padStart(4, '0')}.bin` || seen.has(body.path) || body.path === src.path) fail('profile_schema', `${where}.path name`, 'profile');
    seen.add(body.path);
    intIn(body.bytes, HEADER_BYTES + FOOTER_BYTES + 1, PROFILE_BOUNDS.max_body_bytes, `${where}.bytes`);
    if (body.bytes > limits.max_body_bytes) fail('over_cap', `${where}.bytes ${body.bytes}`, 'profile');
    if (!HEX64.test(body.sha256)) fail('profile_schema', `${where}.sha256`, 'profile');
    const identity = identityStrings(body.identity_decimal, body.bytes, `${where}.identity_decimal`);
    if (typeof r.header18_hex !== 'string' || !/^[0-9a-f]{36}$/.test(r.header18_hex)) fail('profile_schema', `${where}.header18_hex`, 'profile');
    const header18 = Buffer.from(r.header18_hex, 'hex');
    const parsed = parseRawHeader(header18);
    exactKeys(r.header, HEADER_KEYS, `${where}.header`);
    for (const k of HEADER_KEYS) eq(r.header[k], parsed[k], `${where}.header.${k}`);
    const fp = checkRawHeader(parsed, limits, where);
    exactKeys(r.footprint, FOOTPRINT_KEYS, `${where}.footprint`);
    const want = { ...fp, trailing_bytes: FOOTER_BYTES };
    for (const k of FOOTPRINT_KEYS) eq(r.footprint[k], want[k], `${where}.footprint.${k}`);
    if (fp.raw_expected_end + FOOTER_BYTES !== body.bytes) fail('profile_schema', `${where} exact interval`, 'profile');
    if (typeof r.footer26_hex !== 'string' || !/^[0-9a-f]{52}$/.test(r.footer26_hex)) fail('profile_schema', `${where}.footer26_hex`, 'profile');
    const footer26 = Buffer.from(r.footer26_hex, 'hex');
    if (!footer26.subarray(8).equals(FOOTER_SIGNATURE)) fail('profile_schema', `${where} footer signature`, 'profile');
    bodyTotal += body.bytes;
    rgbaTotal += fp.rgba_bytes;
    return Object.freeze({ query_index: r.query_index, wire_target: r.wire_target, source_batch: r.source_batch, path: body.path, bytes: body.bytes, sha256: body.sha256, identity, header18, footer26, header: Object.freeze({ ...parsed }), footprint: Object.freeze(fp) });
  });
  if (bodyTotal > limits.max_body_total_bytes || rgbaTotal > limits.max_rgba_total_bytes) fail('over_cap', `totals ${bodyTotal}/${rgbaTotal}`, 'profile');
  exactKeys(profile.counts, ['queries', 'body_bytes', 'rgba_bytes'], 'counts');
  const computed = { queries: rows.length, body_bytes: bodyTotal, rgba_bytes: rgbaTotal };
  for (const k of Object.keys(computed)) {
    eq(profile.counts[k], computed[k], `counts.${k}`);
    eq(computed[k], counts[k], `pinned counts.${k}`);
  }
  if (typeof profile.evidence_boundary !== 'string' || profile.evidence_boundary.length === 0) fail('profile_schema', 'evidence_boundary', 'profile');
  return Object.freeze({ source: Object.freeze({ path: src.path, bytes: src.bytes, sha256: src.sha256, identity: identityStrings(src.identity_decimal, src.bytes, 'source') }), rows: Object.freeze(rows), counts: Object.freeze(computed) });
}

// ---------------------------------------------------------------- source spans

// Reconstructs each whole-LF span from the inert source bytes; returns texts.
export function extractSpans(source, spans = SPANS) {
  const lineOf = (offset) => {
    let line = 1;
    for (let i = source.indexOf(10); i !== -1 && i < offset; i = source.indexOf(10, i + 1)) line++;
    return line;
  };
  const decoder = new TextDecoder('utf-8', { fatal: true });
  return spans.map((s) => {
    const end = s.byte_offset + s.byte_length;
    if (end > source.length || s.byte_offset <= 0) fail('span_bounds', s.id, 'source');
    const bytes = source.subarray(s.byte_offset, end);
    if (sha256(bytes) !== s.sha256) fail('span_sha', s.id, 'source');
    if (source[s.byte_offset - 1] !== 10 || bytes[bytes.length - 1] !== 10) fail('span_not_whole_lines', s.id, 'source');
    let lfs = 0;
    for (let i = bytes.indexOf(10); i !== -1; i = bytes.indexOf(10, i + 1)) lfs++;
    const start = lineOf(s.byte_offset);
    if (start !== s.start_line || start + lfs - 1 !== s.end_line) fail('span_lines', `${s.id} ${start}+${lfs}`, 'source');
    const text = decoder.decode(bytes);
    if (!Buffer.from(text, 'utf8').equals(bytes)) fail('span_not_identical', s.id, 'source');
    return Object.freeze({ id: s.id, start_line: start, end_line: start + lfs - 1, byte_offset: s.byte_offset, byte_length: bytes.length, sha256: s.sha256, text });
  });
}

// Separately pinned scaffold: declares Targa, then the byte-identical spans.
export const buildScaffold = (texts) => `"use strict";\nvar Targa;\n${texts.map((t) => t.text).join('')}`;

// ---------------------------------------------------------------- one realm

// Decodes one admitted raw body in one fresh realm. scaffoldText is the
// qualified scaffold in actual mode; tests may pass handwritten stubs. Every
// cap is enforced before any evaluation, even for a stub.
export function decodeInRealm(scaffoldText, body, limits, deadline, timeoutMs = limits.per_vm_timeout_ms) {
  checkBoundsWithin(limits);
  if (!(body instanceof Uint8Array) || types.isProxy(body)) fail('bad_body', 'host Uint8Array required', 'admission');
  if (typeof scaffoldText !== 'string') fail('bad_scaffold', typeof scaffoldText, 'admission');
  if (!Number.isSafeInteger(timeoutMs) || timeoutMs <= 0 || timeoutMs > limits.per_vm_timeout_ms) fail('over_cap', `timeout ${timeoutMs}`, 'admission');
  const length = body.length;
  if (length > limits.max_body_bytes) fail('over_cap', `encoded ${length}`, 'admission');
  const header = parseRawHeader(body);
  const fp = checkRawHeader(header, limits, 'body');
  if (length < fp.raw_expected_end) fail('short_pixels', `${length} < ${fp.raw_expected_end}`, 'admission');
  checkLittleEndian();
  const timing = {};
  const run = (script, stage) => {
    const left = deadline.check(stage);
    const t0 = performance.now();
    try {
      return script.runInContext(context, { timeout: Math.max(1, Math.min(timeoutMs, Math.floor(left))), breakOnSigint: false });
    } catch (e) {
      if (e?.code === 'ERR_SCRIPT_EXECUTION_TIMEOUT') fail('vm_timeout', `${stage} exceeded ${timeoutMs}ms`, stage);
      fail(stage === 'decode' ? 'decoder_error' : 'vm_error', `${e?.name}: ${String(e?.message).slice(0, 300)}`, stage);
    } finally {
      timing[`${stage}_ms`] = performance.now() - t0;
    }
  };
  deadline.check('realm');
  let context = vm.createContext(vm.constants.DONT_CONTEXTIFY, { codeGeneration: { strings: false, wasm: false }, microtaskMode: 'afterEvaluate' });
  try {
    run(new vm.Script(scaffoldText, { filename: 'tga-observer-scaffold.js' }), 'definitions');
    let input = run(new vm.Script(`globalThis.__observerInput = new Uint8Array(${length}); globalThis.__observerInput;`), 'allocate');
    if (!types.isUint8Array(input) || types.isProxy(input) || taLength(input) !== length || taByteOffset(input) !== 0 || abByteLength(taBuffer(input)) !== length) fail('realm_input', 'allocation brand/length', 'allocate');
    deadline.check('copy');
    taSet(input, body, 0);
    input = null;
    const image = run(new vm.Script('(() => { const input = globalThis.__observerInput; globalThis.__observerInput = undefined; const tga = new Targa(); tga.load(input); return tga.getImageData(); })()'), 'decode');
    deadline.check('validate');
    const t0 = performance.now();
    const out = validateImage(image, header.width, header.height);
    timing.validate_hash_ms = performance.now() - t0;
    return { width: header.width, height: header.height, ...out, timing };
  } finally {
    context = null;
  }
}

// Validates a realm-returned image without running realm code, then hashes all
// RGBA bytes outside the VM. Returns only primitives.
export function validateImage(image, width, height) {
  const want = width * height * 4;
  if (image === null || typeof image !== 'object' || types.isProxy(image)) fail('image_shape', 'not a plain object', 'validate');
  const keys = Reflect.ownKeys(image);
  if (keys.length !== 3 || !['width', 'height', 'data'].every((k) => keys.includes(k))) fail('image_shape', `keys ${String(keys.length)}`, 'validate');
  const field = (k) => {
    const d = Reflect.getOwnPropertyDescriptor(image, k);
    if (!d || !('value' in d)) fail('image_shape', `${k} accessor`, 'validate');
    return d.value;
  };
  if (field('width') !== width || field('height') !== height) fail('image_dimensions', 'returned dimensions differ', 'validate');
  const data = field('data');
  if (!types.isUint8ClampedArray(data) || types.isProxy(data)) fail('image_brand', 'Uint8ClampedArray required', 'validate');
  const buffer = taBuffer(data);
  if (!types.isArrayBuffer(buffer) || taLength(data) !== want || taByteOffset(data) !== 0 || abByteLength(buffer) !== want) fail('image_length', `backing differs from ${want} bytes`, 'validate');
  const view = new Uint8Array(buffer, 0, want);
  return { rgba_bytes: want, rgba_sha256: sha256(view), rgba_last_byte: view[want - 1] };
}

// ---------------------------------------------------------------- outputs

// Fresh exclusive 0700 run directory under an existing real (non-symlink) prefix.
function createRunDirectory(prefix) {
  if (typeof prefix !== 'string' || !path.isAbsolute(prefix) || path.normalize(prefix) !== prefix) throw new ObserverRefusal('bad_prefix', 'absolute normalized prefix required');
  const st = fs.lstatSync(prefix);
  if (!st.isDirectory() || st.isSymbolicLink() || fs.realpathSync(prefix) !== prefix) throw new ObserverRefusal('bad_prefix', 'real directory required');
  if ((st.mode & 0o077) !== 0) throw new ObserverRefusal('bad_prefix', 'private 0700 prefix required');
  const dir = path.join(prefix, `run-${new Date().toISOString().replace(/[:.]/g, '')}-${process.pid}-${randomBytes(4).toString('hex')}`);
  fs.mkdirSync(dir, { mode: 0o700 });
  const made = fs.lstatSync(dir);
  if (!made.isDirectory() || (made.mode & 0o777) !== 0o700) throw new ObserverRefusal('bad_prefix', 'run directory mode');
  // Retain ownership before any input read or first output can replace it.
  const parents = parentPins(path.join(dir, 'owned-output'));
  return { dir, parents };
}
export const makeRunDir = (prefix) => createRunDirectory(prefix).dir;

const OUTPUT_PIN=Symbol('output authority');
function sealOutput(dir,record,guard=()=>{}) {
  guard();const a=record[OUTPUT_PIN];checkParents(a.parents);
  const file=path.join(dir,record.file),pre=fs.lstatSync(file,{bigint:true});
  if(!sameIdentity(identityOf(pre),a.identity))fail('output_identity','output literal changed','publication');
  const fd=fs.openSync(file,fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW);
  try {
    if(!sameIdentity(identityOf(fs.fstatSync(fd,{bigint:true})),a.identity))fail('output_identity','output FD changed','publication');
    const b=Buffer.alloc(record.bytes);let off=0;
    while(off<b.length){guard();const n=fs.readSync(fd,b,off,Math.min(65536,b.length-off),off);if(!n)fail('output_readback','short output','publication');off+=n;}
    if(fs.readSync(fd,Buffer.alloc(1),0,1,off)!==0 || sha256(b)!==record.sha256)fail('output_readback','output bytes mismatch','publication');
    if(!sameIdentity(identityOf(fs.fstatSync(fd,{bigint:true})),a.identity))fail('output_identity','output changed while reading','publication');
  } finally {fs.closeSync(fd);}
  checkParents(a.parents);
  if(!sameIdentity(identityOf(fs.lstatSync(file,{bigint:true})),a.identity))fail('output_identity','output changed while closing','publication');guard();
}
export function writeExclusive(dir,name,data,guard=()=>{}) {
  guard();const bytes=Buffer.from(data);if(bytes.length>1048576)fail('result_over_cap','capture exceeds1MiB','publication');
  const file=path.join(dir,name),parents=parentPins(file);
  const fd=fs.openSync(file,fs.constants.O_RDWR|fs.constants.O_CREAT|fs.constants.O_EXCL|fs.constants.O_NOFOLLOW,0o600);let identity;
  try {fs.writeFileSync(fd,bytes);fs.fsyncSync(fd);const st=fs.fstatSync(fd,{bigint:true});
    if(!st.isFile() || st.nlink!==1n || (st.mode&511n)!==384n || st.size!==BigInt(bytes.length))fail('output_identity','unsafe output','publication');identity=identityOf(st);
  } finally {fs.closeSync(fd);}
  const record={file:name,bytes:bytes.length,sha256:sha256(bytes)};Object.defineProperty(record,OUTPUT_PIN,{value:{identity,parents}});sealOutput(dir,record,guard);return record;
}
function linkedOutput(dir,candidate,guard) {
  sealOutput(dir,candidate,guard);fs.linkSync(path.join(dir,candidate.file),path.join(dir,'result.json'));
  const now=identityOf(fs.lstatSync(path.join(dir,candidate.file),{bigint:true})),old=candidate[OUTPUT_PIN].identity;
  if(now[6]!=='2' || [0,1,2,3,5,7].some(i=>now[i]!==old[i]))fail('output_identity','unexpected link transition','publication');
  candidate[OUTPUT_PIN].identity=now;
  const final={file:'result.json',bytes:candidate.bytes,sha256:candidate.sha256};Object.defineProperty(final,OUTPUT_PIN,{value:{identity:now,parents:parentPins(path.join(dir,'result.json'))}});
  sealOutput(dir,candidate,guard);sealOutput(dir,final,guard);return final;
}

// ---------------------------------------------------------------- observer

// pins/limits/clock exist so tests can run an authored 25-row profile within
// tiny caps; the CLI always uses the frozen defaults.
export function runObserver({ profilePath, prefix, pins = { profile: PROFILE_PIN, counts: COUNTS }, limits = PROFILE_BOUNDS, clock, heapStats } = {}) {
  checkBoundsWithin(limits);const heap=checkEffectiveHeap(heapStats);checkLittleEndian();
  const deadline=makeDeadline(limits.overall_command_ms,clock);
  const {dir,parents:runParents}=createRunDirectory(prefix);
  const held=[],bodyAuthorities=[],outputs=[],rows=[],closeErrors=[];
  const record={schema:RESULT_SCHEMA,task:TASK,status:'FAIL',effective_v8_heap_bytes:heap,little_endian:true,limits};
  let error,published,candidate;
  const closeInputs=()=>{for(const h of held){try{h.close();}catch(e){closeErrors.push({code:e.code??'close_error',message:String(e.message).slice(0,200)});}}};
  const authority=()=>{deadline.check('authority');checkParents(runParents);for(const h of held)h.literalRecheck('publication');for(const verify of bodyAuthorities)verify('publication');deadline.check('authority');};
  try {
    const prof=readHeldInput(profilePath,pins.profile,1<<20,deadline,'profile');held.push(prof);
    let parsed;try{parsed=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(prof.bytes));}catch{fail('profile_json','invalid UTF-8 JSON','profile');}
    const profile=validateProfile(parsed,{limits,counts:pins.counts});record.profile={path:profilePath,bytes:prof.bytes.length,sha256:prof.sha256,identity_pre:prof.identity};
    const src=readHeldInput(profile.source.path,{bytes:SOURCE_PIN.bytes,sha256:SOURCE_PIN.sha256,identity:profile.source.identity},SOURCE_PIN.bytes,deadline,'source');held.push(src);
    const texts=extractSpans(src.bytes),scaffold=buildScaffold(texts);record.source={path:profile.source.path,bytes:src.bytes.length,sha256:src.sha256,identity_pre:src.identity};record.spans=texts.map(({text,...pin})=>pin);
    record.scaffold=writeExclusive(dir,'scaffold.js',scaffold,authority);outputs.push(record.scaffold);
    for(const row of profile.rows) {
      const stage=`row_${row.query_index}`,t0=performance.now();
      const body=readHeldInput(row.path,{bytes:row.bytes,sha256:row.sha256,identity:row.identity},limits.max_body_bytes,deadline,stage);let completed;
      try {
        const b=body.bytes;if(!b.subarray(0,18).equals(row.header18))fail('header18_mismatch',stage,stage);if(!b.subarray(b.length-26).equals(row.footer26))fail('footer26_mismatch',stage,stage);
        const h=parseRawHeader(b);for(const k of HEADER_KEYS)if(h[k]!==row.header[k])fail('header_mismatch',`${stage}.${k}`,stage);
        const fp=checkRawHeader(h,limits,stage);if(fp.raw_expected_end+26!==b.length)fail('interval_mismatch',stage,stage);
        const read_ms=performance.now()-t0,out=decodeInRealm(scaffold,b,limits,deadline);body.recheck('final_use');
        completed={query_index:row.query_index,wire_target:row.wire_target,source_batch:row.source_batch,body:{path:row.path,bytes:b.length,sha256:body.sha256,identity_pre:body.identity,identity_post_matches:true},width:out.width,height:out.height,pixel_depth:h.pixel_depth,flags:h.flags,origin:fp.origin,alpha_bits:fp.alpha_bits,rgba_bytes:out.rgba_bytes,rgba_sha256:out.rgba_sha256,timing_ms:{read_check:read_ms,...out.timing,row_total:performance.now()-t0},cleanup:{realm_reference_dropped:true,body_buffer_reference_dropped:true,descriptor_closed:false}};
      } finally {try{body.close();}finally{body.releaseBytes();}}
      body.literalRecheck('after_close');bodyAuthorities.push(body.literalRecheck);completed.cleanup.descriptor_closed=true;rows.push(completed);
    }
    for(const h of held)h.recheck('final_use');authority();closeInputs();
    if(closeErrors.length)fail('cleanup_failed','input close failed','cleanup');authority();
    record.profile.identity_post_matches=true;record.source.identity_post_matches=true;record.rows=rows;
    record.counts={queries:rows.length,body_bytes:rows.reduce((a,r)=>a+r.body.bytes,0),rgba_bytes:rows.reduce((a,r)=>a+r.rgba_bytes,0)};
    if(rows.length!==QUERY_INDICES.length || rows.some((r,i)=>r.query_index!==QUERY_INDICES[i]))fail('incomplete_rows',String(rows.length),'publish');
    record.status='PASS';record.gc_note='References are dropped between rows; this does not prove immediate GC or bound RSS/external memory.';record.elapsed_ms_before_publish=deadline.elapsed();
    const text=JSON.stringify(record,null,1)+'\n';if(Buffer.byteLength(text)>limits.max_result_bytes)fail('result_over_cap',String(Buffer.byteLength(text)),'publish');
    candidate=writeExclusive(dir,'result.candidate.json',text,authority);outputs.push(candidate);published=linkedOutput(dir,candidate,authority);outputs.push(published);
    authority();for(const output of outputs)sealOutput(dir,output,authority);
    const elapsed=deadline.elapsed();if(!(elapsed<limits.overall_command_ms))fail('deadline_exceeded','terminal command deadline','terminal');
    return {status:'PASS',dir,result:{file:published.file,bytes:published.bytes,sha256:published.sha256},elapsed_ms:elapsed};
  } catch(e) {error=e;}
  finally {closeInputs();}
  // Preserve every failed run and remove only this run's own terminal alias.
  if(candidate) {
    try {const final=path.join(dir,'result.json'),st=fs.lstatSync(final,{bigint:true}),id=candidate[OUTPUT_PIN].identity;if(String(st.dev)===id[0]&&String(st.ino)===id[1])fs.renameSync(final,path.join(dir,'result.unqualified.json'));}catch(e){if(e.code!=='ENOENT')closeErrors.push({code:e.code??'publication_cleanup'});}
  }
  const failure={schema:RESULT_SCHEMA,task:TASK,status:'FAIL',code:error?.code??'internal_error',stage:error?.stage??null,message:String(error?.message??error).slice(0,MAX_FAILURE_TEXT),timeout:error?.code==='vm_timeout'||error?.code==='deadline_exceeded',completed_rows:rows.map(({timing_ms,...r})=>r),profile:record.profile??null,source:record.source??null,spans:record.spans??null,scaffold:record.scaffold??null,effective_v8_heap_bytes:heap,elapsed_ms:deadline.elapsed(),close_errors:closeErrors};
  let text=JSON.stringify(failure,null,1)+'\n';if(Buffer.byteLength(text)>limits.max_result_bytes)text=JSON.stringify({...failure,completed_rows:`${rows.length} rows elided`})+'\n';
  try {return {status:'FAIL',code:failure.code,stage:failure.stage,dir,failure:writeExclusive(dir,'failure.json',text)};}catch(e){return {status:'FAIL',code:failure.code,stage:failure.stage,dir,failure_write_error:e.code??'internal_error'};}
}

// ---------------------------------------------------------------- CLI

export function main(argv, deps = {}) {
  if (argv.length !== 5 || argv[0] !== '--actual' || argv[1] !== '--profile' || argv[3] !== '--private-prefix') {
    throw new ObserverRefusal('usage', 'only: --actual --profile <PROFILE_ROOT.json> --private-prefix <dir>');
  }
  checkEffectiveHeap(deps.heapStats);
  checkLittleEndian();
  return runObserver({ profilePath: argv[2], prefix: argv[4], heapStats: deps.heapStats });
}

if (process.argv[1] && import.meta.url === pathToFileURL(fs.realpathSync(process.argv[1])).href) {
  let out;
  try {
    out = main(process.argv.slice(2));
  } catch (e) {
    out = { status: 'REFUSED', code: e?.code ?? 'internal_error', message: String(e?.message ?? e).slice(0, MAX_FAILURE_TEXT) };
  }
  process.stdout.write(`${JSON.stringify(out)}\n`);
  process.exitCode = out.status === 'PASS' ? 0 : out.status === 'REFUSED' ? 2 : 1;
}
