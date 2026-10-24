#!/usr/bin/env node
// T07.007.014.023: finite static CPU geometry observer for model702/map17/
// group37/placement50 (one unchanged RSM constructor/createInstance/compile).
//
//   /usr/bin/perl -e 'alarm shift; exec @ARGV or die "exec: $!"' 15 \
//     node --max-old-space-size=125 --max-semi-space-size=1 \
//     tools/renewal/observe_model_geometry.mjs --actual \
//     --profile <absolute PROFILE_ROOT.json> --private-prefix <absolute ignored dir>
//
// Root alone decides when to invoke --actual; profile_admits_execution:false
// grants nothing and no author test runs it. The perl alarm is the real finite
// external kill/wait guard: SIGALRM terminates the process even inside
// synchronous IO/VM/host work, which the in-process deadline cannot interrupt.
// The effective V8 heap is measured (heap_size_limit), never inferred from
// flags; it is not an RSS, external-memory or address-space cap.
//
// Mechanism: exact argv only; heap and endianness are refused before any IO.
// Profile, source, inventory, declared fixture and body are each read once
// through held O_NOFOLLOW descriptors with pinned size/SHA and lossless BigInt C8
// identities rechecked through final use (finite lifecycle pattern reused from
// the qualified T07.007.014.021 TGA observer). The closed profile schema,
// exact model/placement/structure and resource totals are validated before
// the body is opened. Five whole ASCII LF regions are reconstructed from the
// inert source and verified against the pinned inventory; no bundle
// initializer or provenance-only span executes. The body and placement are
// independently preflighted (strict static RSM2.3 subset, ported from the
// Root-authored Python reader; dense finite placement triples; Float32
// rounded-column admission) before any realm exists. One fresh
// DONT_CONTEXTIFY realm (no string/wasm codegen, console deleted, realm-owned
// self) evaluates the copied definitions, receives the body through a realm
// Uint8Array filled by the captured host intrinsic setter and constructs the
// unchanged Model once. A bounded primitive structure string (with observed
// primary smooth groups) is matched to the host preflight BEFORE the unchanged
// hasAnimation/createInstance/compile run on that same realm-owned model and
// return one bounded primitive mesh string. The host validates and hashes
// every mesh byte. Outputs go to a fresh exclusive 0700 run directory as 0600
// files; PASS is published only by linking a bounded candidate after every
// pin/identity/deadline check. Run-directory ownership is deadline-independent
// and gates every write, including failure publication and alias retirement.
//
// Exports and shapes (all throw ObserverRefusal{code} before IO or
// ObserverFailure{code,stage} afterwards; detail text is in message):
//   preflightModel(body, placement, ground, limits) -> frozen
//     {version, animLen, shadeType, alpha, frameRatePerSecond,
//      unused_global_names, volume_boxes, consumed_bytes, textures (global
//      deduped names), nodes[{node_index,name,parentname,textures,mat3,offset,
//      vertices,uvs,faces,primary_smooth_groups,key_counts,global_texture_keys,
//      mesh_float_count,mesh_bytes,mesh_layout[[key,floats]],raw}],
//      resources{mesh_bytes,principal_typed_bytes,
//      principal_typed_bytes_if32groups,smooth_face_visits,result_estimate_bytes},
//      placement, ground}
//     Failure code 'preflight_refused'; message detail equals the
//     independent reader's error label where one exists.
//   extractSpans(source) -> frozen [{id,LF_start,LF_end,offset,bytes,sha256,text}]
//   buildScaffold(spans) -> string (authored prelude + ordered region bytes)
//   compileInRealm(scaffold, body, placement, ground, limits, deadline, opts?)
//     -> {preflight, copy_sha256, structure (validated constructed structure),
//        textures, meshes[{node_index,texture_key,float_count,byte_length,
//        float32_le_hex,sha256}], observed_emitted_bounds, timing}
//   runObserver(options) -> {status:'PASS',dir,result{file,bytes,sha256},elapsed_ms}
//     | {status:'FAIL',code,stage,dir,timeout,retirement,failure{file,bytes,sha256}}
//     | {status:'FAIL',...,ownership_lost?:true,failure_write_error,failure_summary}
//   Errors may carry non-enumerable closeDiagnostics[{during,code,message}]:
//   close faults never replace a primary error and join failure close_errors.
//   main(argv) -> runObserver result; refuses (throws) on any other argv.
import { createHash, randomBytes } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { performance } from 'node:perf_hooks';
import { pathToFileURL } from 'node:url';
import { types } from 'node:util';
import v8 from 'node:v8';
import vm from 'node:vm';

export const TASK = 'T07.007.014.023';
export const PROFILE_SCHEMA = 't07-014-023-model702-geometry-profile-v1';
export const RESULT_SCHEMA = 't07-014-023-model702-geometry-observation-v1';
const sha256 = (b) => createHash('sha256').update(b).digest('hex');

export const PROFILE_PIN = Object.freeze({ bytes: 5839, sha256: '1b80888abc5123ba73fb402f92f75e662a82aee4fffdc207ec62fa4c0d25b8c6' });
export const SOURCE_PIN = Object.freeze({ bytes: 624463, sha256: '1501ca10336d91e4f8a0301101c43e5ca1a0ef1aa81212bbffb5690c68c13325', lf_count: 19549 });
export const INVENTORY_PIN = Object.freeze({ bytes: 24463, sha256: 'd613403980de902611a83815ef56ccd040aadfdab0475c8e25348b7dd4687007' });
export const FIXTURE_PIN = Object.freeze({ bytes: 148023, sha256: 'c3ad8c64e43fca88d0ec01971a910940ddc612cbe2ca9902afc6b3d9fe99f838' });
export const CLOSURE_PIN = Object.freeze({ bytes: 122567, sha256: 'a69e2472aa5103c7c976fd5eaf9bd5600d1cf2838fb906e57c25b6f28e2c66e0' });
const region = (id, LF_start, LF_end, offset, bytes, sha) => Object.freeze({ id, LF_start, LF_end, offset, bytes, sha256: sha });
export const SPANS = Object.freeze([
  region('X01_global_seek', 11254, 11257, 410946, 125, 'b61f2979872651475fd521fe6e6ab19d329d4c251b17377e3bc2fde9a309d950'),
  region('X02_BinaryReader', 11258, 11488, 411071, 6550, '938d4538c4706ee29641355f4ef2e876dfb543f602995f7cc89fc2a5dfb4c2fb'),
  region('X03_glmatrix_vendor', 12551, 15752, 437664, 82079, '131ed85ee2aa5018d754fd0846cf70167548dd8304c16f3c7f599c3a7379f083'),
  region('X04_glmatrix_utils', 15755, 16088, 519789, 7502, '2bdd7682f40a7e3f112ff526dacd10e207783e6871fa8c4f028799d92002aec3'),
  region('X05_model_region', 16877, 17771, 550770, 26311, '6ea0385b3cfb5212a96bb0f98f6fd464f8ba281d3bc755454b30930e2e4950d9'),
]);
export const IDENTITY_FIELDS = Object.freeze(['st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_mode', 'st_nlink', 'st_uid']);
export const PROFILE_BOUNDS = Object.freeze({
  max_body_bytes: 65536, max_nodes: 4, max_vertices_per_node: 512, max_uvs_per_node: 512, max_faces_per_node: 512,
  max_texture_names: 8, max_string_bytes: 256, max_face_record_bytes: 64, max_primary_smooth_group: 31,
  max_abs_raw_scalar: 1000000, max_abs_placement_scalar: 1000000, max_ground_dimension: 4096,
  max_principal_typed_bytes: 196608, max_smooth_face_visits: 2000000, max_mesh_bytes: 131072,
  per_vm_timeout_ms: 500, total_timeout_ms: 10000, max_effective_v8_heap_bytes: 134217728, max_result_bytes: 1048576,
});
// Authored caps; author tests may only execute copied source within these.
export const TINY_BOUNDS = Object.freeze({
  ...PROFILE_BOUNDS, max_body_bytes: 4096, max_nodes: 2, max_vertices_per_node: 8, max_uvs_per_node: 8, max_faces_per_node: 8,
  max_string_bytes: 64, max_mesh_bytes: 2048, per_vm_timeout_ms: 100,
});
// Lower bounds for bounds that may legitimately be zero.
const BOUND_MIN = Object.freeze({ max_primary_smooth_group: 0, max_ground_dimension: 0 });

const NODE_STRUCTURE = (node_index, name, texture, vertices, uvs, faces, groups, key, floats) => Object.freeze({
  node_index, name, parentname: '', textures: [texture], mat3: [1, 0, 0, 0, 1, 0, 0, 0, 1], offset: [0, 0, 0],
  vertices, uvs, faces, primary_smooth_groups: groups, key_counts: [0, 0, 0, 0], global_texture_keys: [key],
  mesh_float_count: floats, mesh_bytes: floats * 4,
});
// Exact frozen actual expectations (equal to the pinned profile content).
export const FROZEN = Object.freeze({
  model_index: 702, original_query_index: 911, map_index: 17, group_index: 37, placement_index: 50,
  body: Object.freeze({ bytes: 19113, sha256: '3a84cdc3c4923f605ec5f5c48a68baf71408b3438e35afb2a61972bf0b00054d' }),
  placement: Object.freeze({
    position: [63.42008666992187, 1.9469152450561524, -63.43079833984375],
    rotation: [-0, 131.99996948242188, 0],
    scale: [-0.09600000381469727, 0.09600000381469727, -0.09600000381469727],
  }),
  ground: Object.freeze({ width: 200, height: 200 }),
  expected_static_structure: Object.freeze({
    version: 2.3, animLen: 170, shadeType: 2, alpha: 1, frameRatePerSecond: 30, unused_global_names: ['campfire_j_01', 'object'],
    volume_boxes: 0, consumed_bytes: 19113,
    nodes: [
      NODE_STRUCTURE(0, 'campfire_j_01', 'graywolf\\gray_j_05.bmp', 96, 146, 132, [1, 2, 3, 4, 5], 0, 3564),
      NODE_STRUCTURE(1, 'object', 'graywolf\\gray_j_08.bmp', 177, 222, 265, [1, 2, 3, 4, 5, 6, 7, 8], 1, 7155),
    ],
  }),
  resource_expected: Object.freeze({ mesh_bytes: 42876, principal_typed_bytes: 73668, principal_typed_bytes_if32groups: 155748, smooth_face_visits: 438600 }),
  independent_preflight_provenance: Object.freeze({ bytes: 353543, sha256: 'fe18ec2d7a198c6d80993b2e5377a54bd729f03cb1ab839638da1e0291fedf8f' }),
});
const MAX_FAILURE_TEXT = 2000;
const F32_MAX = 3.4028234663852886e38;

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

// Fault-injection observation: realms created by compileInRealm in this process.
export const realmStats = { created: 0, definitions: 0, structure: 0, lifecycle: 0 };

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

// Limits may only tighten the frozen profile bounds, never loosen them.
export function checkBoundsWithin(limits) {
  const keys = Object.keys(PROFILE_BOUNDS);
  if (!limits || typeof limits !== 'object' || Object.keys(limits).length !== keys.length) throw new ObserverRefusal('bad_limits', 'keys');
  for (const k of keys) {
    const lo = BOUND_MIN[k] ?? 1;
    if (!Number.isSafeInteger(limits[k]) || limits[k] < lo || limits[k] > PROFILE_BOUNDS[k]) throw new ObserverRefusal('bad_limits', k);
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
  const pins = [];
  for (let p = path.dirname(file); ; p = path.dirname(p)) {
    const st = fs.lstatSync(p, { bigint: true });
    if (!st.isDirectory() || st.isSymbolicLink()) fail('input_ancestor', 'non-directory/symlink ancestor', 'identity');
    pins.push({ path: p, identity: [st.dev, st.ino, st.mode, st.uid].map(String) });
    if (p === path.dirname(p)) break;
  }
  return pins;
}
function checkParents(pins) {
  for (const pin of pins) {
    const st = fs.lstatSync(pin.path, { bigint: true });
    if (!st.isDirectory() || !sameIdentity(pin.identity, [st.dev, st.ino, st.mode, st.uid].map(String))) fail('input_ancestor', 'ancestor changed', 'identity');
  }
}

// Reads one regular single-link file through a held O_NOFOLLOW descriptor.
// expect = { bytes, sha256, identity?: 8 canonical decimal strings }.
export function readHeldInput(file, expect, maxBytes, deadline, stage) {
  if (typeof file !== 'string' || !path.isAbsolute(file) || path.normalize(file) !== file) fail('bad_path', 'absolute normalized path required', stage);
  if (!Number.isSafeInteger(expect.bytes) || expect.bytes < 0 || expect.bytes > maxBytes) fail('input_over_cap', `${expect.bytes} > ${maxBytes}`, stage);
  deadline.check(stage);
  const parents = parentPins(file);
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
  const verifyLiteral = (when) => {
    checkParents(parents);
    const now = fs.lstatSync(file, { bigint: true });
    if (now.isSymbolicLink() || !sameIdentity(identityOf(now), literal)) fail('identity_changed', `path ${when}`, stage);
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
      const n = fs.readSync(fd, bytes, got, Math.min(65536, expect.bytes - got), got);
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
      releaseBytes() { bytes = null; this.bytes = null; },
      close() { if (open) { open = false; fs.closeSync(fd); } },
    };
  } catch (e) {
    open = false;
    closeKeepingPrimary(fd, e, `${stage} read`);
    throw e;
  }
}

// A close diagnostic never replaces the primary error; it is attached to it
// (sticky) and later merged into the failure record's close_errors.
const diagnostic = (e, during) => ({ during, code: e?.code ?? 'close_error', message: String(e?.message ?? e).slice(0, 200) });
export function attachDiagnostic(primary, diag) {
  if (primary === null || typeof primary !== 'object') return;
  if (!Object.hasOwn(primary, 'closeDiagnostics')) Object.defineProperty(primary, 'closeDiagnostics', { value: [], enumerable: false });
  primary.closeDiagnostics.push(diag);
}
function closeKeepingPrimary(fd, primary, during) {
  try { fs.closeSync(fd); } catch (ce) { attachDiagnostic(primary, diagnostic(ce, during)); }
}
// Runs body() on an open fd, then always closes it. A primary error keeps any
// close error as a diagnostic; a close error alone is an explicit failure.
function withFd(fd, during, stage, body) {
  let result;
  try { result = body(); } catch (e) { closeKeepingPrimary(fd, e, during); throw e; }
  try { fs.closeSync(fd); } catch (ce) {
    const e = new ObserverFailure('output_close', `${during}: ${ce?.code ?? ce}`, stage);
    attachDiagnostic(e, diagnostic(ce, during));
    throw e;
  }
  return result;
}

// ---------------------------------------------------------------- preflight

// Strict static RSM2.3 subset (port of the Root-authored Python reader plus
// this task's finite restrictions). No acquired code is involved. Counts are
// checked before any list allocation; every interval is bounds-checked.
const refuse = (detail) => fail('preflight_refused', detail, 'preflight');
const isIdentity3 = (m) => m.every((v, i) => Object.is(v, i % 4 === 0 ? 1 : 0));

// Independently authored finite admission arithmetic (adapted from Root's
// qualified ROUNDED_COLUMNS.mjs 3235B/648dfd4b…; not a geometry oracle). It
// replays the static2.3 Z, X, Y rotations with Float32 destination stores
// (operands stay binary64 until each store), rounded scale and the [1,-1,1]
// flip, then requires finite nonzero squared column lengths and finite
// normalizations. Valid only for the identity-mat3/zero-offset/root subset.
// No epsilon, scale floor or mesh tolerance is involved.
export class ColumnAdmissionError extends Error {
  constructor(code, detail) { super(`${code}: ${detail}`); this.name = 'ColumnAdmissionError'; this.code = code; }
}
export function checkRoundedColumns(rotation, scale) {
  const f = Math.fround;
  const reject = (code, detail) => { throw new ColumnAdmissionError(code, detail); };
  const triple = (a, label) => {
    if (!Array.isArray(a) || a.length !== 3) reject('invalid_vector', label);
    const out = [];
    for (let i = 0; i < 3; ++i) {
      if (!Object.hasOwn(a, i)) reject('invalid_lane', `${label}[${i}] missing`);
      const x = a[i];
      if (typeof x !== 'number' || !Number.isFinite(x) || Math.abs(x) > 1e6) reject('invalid_lane', `${label}[${i}]`);
      out.push(x);
    }
    return out;
  };
  const r = triple(rotation, 'rotation');
  const s = triple(scale, 'scale');
  for (let j = 0; j < 3; ++j) if (s[j] === 0) reject('zero_scale', `scale[${j}]`);
  let a = [1, 0, 0], b = [0, 1, 0], c = [0, 0, 1];
  let angle = r[2] / 180 * Math.PI;
  let sn = Math.sin(angle), cs = Math.cos(angle);
  let oldA = a, oldB = b;
  a = [0, 1, 2].map((i) => f(oldA[i] * cs + oldB[i] * sn));
  b = [0, 1, 2].map((i) => f(oldB[i] * cs - oldA[i] * sn));
  angle = r[0] / 180 * Math.PI;
  sn = Math.sin(angle); cs = Math.cos(angle);
  oldB = b; const oldC = c;
  b = [0, 1, 2].map((i) => f(oldB[i] * cs + oldC[i] * sn));
  c = [0, 1, 2].map((i) => f(oldC[i] * cs - oldB[i] * sn));
  angle = r[1] / 180 * Math.PI;
  sn = Math.sin(angle); cs = Math.cos(angle);
  oldA = a; const beforeYC = c;
  a = [0, 1, 2].map((i) => f(oldA[i] * cs - beforeYC[i] * sn));
  c = [0, 1, 2].map((i) => f(oldA[i] * sn + beforeYC[i] * cs));
  const columns = [a, b, c].map((v, j) => {
    const flip = j === 1 ? -1 : 1;
    return Object.freeze(v.map((x) => f(x * s[j])).map((x) => f(x * flip)));
  });
  const squaredLengths = []; const normalizedColumns = [];
  for (let j = 0; j < 3; ++j) {
    const [x, y, z] = columns[j];
    if (![x, y, z].every(Number.isFinite)) reject('nonfinite_column', String(j));
    const square = x * x + y * y + z * z;
    if (!(square > 0) || !Number.isFinite(square)) reject('degenerate_column', String(j));
    const inverseLength = 1 / Math.sqrt(square);
    const normalized = [f(x * inverseLength), f(y * inverseLength), f(z * inverseLength)];
    if (!Number.isFinite(inverseLength) || !normalized.every(Number.isFinite)) reject('nonfinite_normalization', String(j));
    squaredLengths.push(square);
    normalizedColumns.push(Object.freeze(normalized));
  }
  return Object.freeze({
    purpose: 'admission arithmetic only; not mesh or geometry-reference evidence',
    columns: Object.freeze(columns), squared_lengths: Object.freeze(squaredLengths), normalized_columns: Object.freeze(normalizedColumns),
  });
}

// Dense own finite data lanes only: holes, getters and inherited lanes refuse.
function placementTriple(v, k, limits) {
  if (!Array.isArray(v) || types.isProxy(v) || v.length !== 3) refuse(`placement ${k} shape`);
  const out = [];
  for (let i = 0; i < 3; i++) {
    const d = Object.getOwnPropertyDescriptor(v, i);
    if (!d || !('value' in d)) refuse(`placement ${k} sparse lane`);
    const x = d.value;
    if (typeof x !== 'number') refuse(`placement ${k} non-number scalar`);
    if (!Number.isFinite(x)) refuse('nonfinite placement');
    if (Math.abs(x) > limits.max_abs_placement_scalar) refuse('excess placement scalar');
    out.push(x);
  }
  return out;
}

function checkPlacement(placement, ground, limits) {
  if (!placement || typeof placement !== 'object' || types.isProxy(placement)) refuse('placement shape');
  const out = {};
  for (const k of ['position', 'rotation', 'scale']) out[k] = placementTriple(placement[k], k, limits);
  if (out.scale.some((x) => x === 0)) refuse('zero placement scale');
  try { checkRoundedColumns(out.rotation, out.scale); } catch (e) {
    if (e instanceof ColumnAdmissionError) refuse(`transform column ${e.message}`);
    throw e;
  }
  if (!ground || typeof ground !== 'object' || types.isProxy(ground)) refuse('ground shape');
  const g = {};
  for (const k of ['width', 'height']) {
    if (!Number.isSafeInteger(ground[k]) || ground[k] < 0 || ground[k] > limits.max_ground_dimension) refuse(`ground ${k}`);
    g[k] = ground[k];
  }
  return { placement: Object.freeze({ position: Object.freeze(out.position), rotation: Object.freeze(out.rotation), scale: Object.freeze(out.scale) }), ground: Object.freeze(g) };
}

export function preflightModel(body, placement, ground, limits) {
  checkBoundsWithin(limits);
  if (!(body instanceof Uint8Array) || types.isProxy(body)) refuse('encoded cap/type');
  const len = body.length;
  if (!(len > 0 && len <= limits.max_body_bytes)) refuse('encoded cap/type');
  const pg = checkPlacement(placement, ground, limits);
  const view = new DataView(body.buffer, body.byteOffset, len);
  let at = 0;
  const need = (n) => { if (!Number.isSafeInteger(n) || n < 0 || n > len - at) refuse('short interval'); };
  const raw = (n) => { need(n); const b = body.subarray(at, at + n); at += n; return b; };
  const i32 = () => { need(4); const v = view.getInt32(at, true); at += 4; return v; };
  const u16 = () => { need(2); const v = view.getUint16(at, true); at += 2; return v; };
  const u8 = () => { need(1); return view.getUint8(at++); };
  const count = (cap, label) => { const n = i32(); if (!(n >= 0 && n <= cap)) refuse(`count ${label}`); return n; };
  const floats = (n) => {
    need(4 * n);
    const out = new Array(n);
    for (let i = 0; i < n; i++) { out[i] = view.getFloat32(at, true); at += 4; }
    if (!out.every(Number.isFinite)) refuse('nonfinite raw float');
    if (out.some((v) => Math.abs(v) > limits.max_abs_raw_scalar)) refuse('excess raw scalar');
    return out;
  };
  const string = () => {
    const b = raw(count(limits.max_string_bytes, 'string'));
    let end = b.indexOf(0);
    if (end < 0) end = b.length;
    let s = '';
    for (let i = 0; i < end; i++) s += String.fromCharCode(b[i]);
    return s;
  };
  const magic = raw(4);
  const tag = String.fromCharCode(...magic);
  if (tag !== 'GRSM' && tag !== 'GRSX') refuse('signature/version');
  const ver = raw(2);
  if (ver[0] !== 2 || ver[1] !== 3) refuse('signature/version');
  const animLen = i32();
  const shadeType = i32();
  const alpha = u8() / 255;
  const frameRatePerSecond = floats(1)[0];
  if (animLen < 0 || ![0, 1, 2].includes(shadeType) || !(frameRatePerSecond > 0)) refuse('model header');
  if (shadeType !== 2) refuse('unsupported shadeType');
  const nGlobal = count(limits.max_texture_names, 'global texture strings');
  const unused_global_names = [];
  for (let i = 0; i < nGlobal; i++) unused_global_names.push(string());
  const nNodes = count(limits.max_nodes, 'nodes');
  const nodes = [];
  for (let ni = 0; ni < nNodes; ni++) {
    const name = string();
    const parentname = string();
    const nTex = count(limits.max_texture_names, 'node textures');
    const textures = [];
    for (let i = 0; i < nTex; i++) textures.push(string());
    if (!textures.length || new Set(textures).size !== textures.length) refuse('empty/duplicate node texture key');
    const mat3 = floats(9);
    const offset = floats(3);
    const nV = count(limits.max_vertices_per_node, 'vertices');
    const vertices = [];
    for (let i = 0; i < nV; i++) vertices.push(floats(3));
    if (!vertices.length) refuse('no vertices');
    const nUV = count(limits.max_uvs_per_node, 'uvs');
    const uvs = [];
    for (let i = 0; i < nUV; i++) { const color = [...raw(4)]; uvs.push({ color, uv: floats(2) }); }
    const nF = count(limits.max_faces_per_node, 'faces');
    const faces = [];
    for (let i = 0; i < nF; i++) {
      const n = i32();
      if (!(n === 24 || n === 28 || n === 32 || (n > 32 && n <= 64 && n % 4 === 0))) refuse('face record length');
      if (n > limits.max_face_record_bytes) refuse('face record length');
      const end = at + n;
      const vertidx = [u16(), u16(), u16()];
      const tvertidx = [u16(), u16(), u16()];
      const texid = u16();
      const padding = u16();
      const twoSide = i32();
      const smoothGroup = i32();
      const extra = [];
      if (n > 24) extra.push(i32());
      if (n > 28) extra.push(i32());
      const remainder = raw(Math.max(0, n - 32));
      if (at !== end) refuse('face consumed interval');
      if (vertidx.some((v) => v >= vertices.length) || tvertidx.some((v) => v >= uvs.length) || texid >= textures.length) refuse('face index');
      if (!(smoothGroup >= 0 && smoothGroup < 32)) refuse('smooth group outside compiled32');
      if (smoothGroup > limits.max_primary_smooth_group) refuse('smooth group over profile cap');
      faces.push({ vertidx, tvertidx, texid, padding, twoSide, smoothGroup, extra_smooth_groups: extra, record_bytes: n, uninterpreted_extra_hex: Buffer.from(remainder).toString('hex') });
    }
    if (!faces.length) refuse('no faces');
    for (const label of ['scale keys', 'rotation keys', 'position keys', 'texture key groups']) count(0, label);
    nodes.push({ name, parentname, textures, mat3, offset, vertices, uvs, faces });
  }
  if (!nodes.length) refuse('no nodes');
  const volume_boxes = at === len ? 0 : count(0, 'volume boxes');
  if (at !== len) refuse('trailing bytes');
  // Finite subset: unique nonempty unparented names, identity mat3, zero offsets.
  const names = nodes.map((n) => n.name);
  if (names.some((n) => n === '') || new Set(names).size !== names.length) refuse('empty/duplicate node name');
  if (nodes.some((n) => n.parentname !== '')) refuse('parented node');
  if (nodes.some((n) => !isIdentity3(n.mat3))) refuse('non-identity mat3');
  if (nodes.some((n) => !n.offset.every((v) => Object.is(v, 0)))) refuse('nonzero offset');
  // Global texture dedupe in the client's order (main node first, then nodes).
  const textures = [];
  for (const n of nodes) for (const t of n.textures) if (!textures.includes(t)) textures.push(t);
  let mesh = 0; let principal = 0; let principal32 = 0; let work = 0;
  const out = nodes.map((n, node_index) => {
    const V = n.vertices.length; const F = n.faces.length;
    const groups = [...new Set(n.faces.map((f) => f.smoothGroup))].sort((a, b) => a - b);
    const G = groups.length;
    const keys = n.textures.map((t) => textures.indexOf(t));
    const perKey = new Map(keys.map((k) => [k, 0]));
    for (const f of n.faces) perKey.set(keys[f.texid], perKey.get(keys[f.texid]) + 27);
    const mesh_layout = [...perKey.entries()].sort((a, b) => a[0] - b[0]).map(([k, floats]) => Object.freeze([String(k), floats]));
    mesh += 108 * F; principal += 120 * F + 12 * V + 12 * G * V; principal32 += 120 * F + 12 * V + 12 * 32 * V; work += G * V * F;
    return Object.freeze({
      node_index, name: n.name, parentname: n.parentname, textures: Object.freeze([...n.textures]), mat3: Object.freeze(n.mat3), offset: Object.freeze(n.offset),
      vertices: V, uvs: n.uvs.length, faces: F, primary_smooth_groups: Object.freeze(groups), key_counts: Object.freeze([0, 0, 0, 0]),
      global_texture_keys: Object.freeze(keys), mesh_float_count: 27 * F, mesh_bytes: 108 * F, mesh_layout: Object.freeze(mesh_layout),
      raw: Object.freeze({ vertices: n.vertices, uvs: n.uvs, faces: n.faces }),
    });
  });
  if (principal > limits.max_principal_typed_bytes) refuse('principal typed budget');
  if (work > limits.max_smooth_face_visits) refuse('smooth face visit budget');
  if (mesh > limits.max_mesh_bytes) refuse('mesh budget');
  // Hex bridge doubles mesh bytes; 4096B covers names/metadata framing.
  const result_estimate_bytes = 2 * mesh + 4096 + textures.reduce((a, t) => a + 6 * t.length + 8, 0) + 2 * names.reduce((a, t) => a + 6 * t.length + 8, 0);
  if (result_estimate_bytes > limits.max_result_bytes) refuse('result budget');
  // Conservative overflow bound: identity mat3/zero offsets keep box and local
  // coordinates within R; instance/placement terms are bounded by P, ground and
  // the 2R box translations. All products stay far below Float32 max.
  const R = limits.max_abs_raw_scalar; const P = limits.max_abs_placement_scalar; const Gd = limits.max_ground_dimension;
  const coord = (P + Gd) + 3 * P * (P + 4 * R) * 4;
  const normal = 3 * (8 * R * R) * limits.max_faces_per_node;
  if (!(coord < F32_MAX / 1e6) || !(normal < F32_MAX / 1e6)) refuse('arithmetic overflow bound');
  return Object.freeze({
    version: 2.3, animLen, shadeType, alpha, frameRatePerSecond, unused_global_names: Object.freeze(unused_global_names), volume_boxes, consumed_bytes: at,
    textures: Object.freeze(textures), nodes: Object.freeze(out),
    resources: Object.freeze({ mesh_bytes: mesh, principal_typed_bytes: principal, principal_typed_bytes_if32groups: principal32, smooth_face_visits: work, result_estimate_bytes }),
    placement: pg.placement, ground: pg.ground,
  });
}

// ---------------------------------------------------------------- source closure

// Reconstructs the five whole ASCII LF regions; verifies offsets, line numbers,
// per-region and ordered concatenation SHA. Every copied byte is retained.
export function extractSpans(source, spans = SPANS, closure = CLOSURE_PIN) {
  if (!(source instanceof Uint8Array)) fail('source_type', 'bytes required', 'source');
  let lf = 0; const lineStarts = [0];
  for (let i = source.indexOf(10); i !== -1; i = source.indexOf(10, i + 1)) { lf++; lineStarts.push(i + 1); }
  if (spans === SPANS && (source.length !== SOURCE_PIN.bytes || lf !== SOURCE_PIN.lf_count)) fail('source_shape', `${source.length}/${lf}`, 'source');
  let prevEnd = 0;
  const out = spans.map((s) => {
    const end = s.offset + s.bytes;
    if (!(s.offset > 0) || end > source.length || s.offset < prevEnd) fail('span_bounds', s.id, 'source');
    prevEnd = end;
    if (lineStarts[s.LF_start - 1] !== s.offset || lineStarts[s.LF_end] !== end) fail('span_lines', s.id, 'source');
    const bytes = source.subarray(s.offset, end);
    if (source[s.offset - 1] !== 10 || bytes[bytes.length - 1] !== 10) fail('span_not_whole_lines', s.id, 'source');
    for (const b of bytes) if (b > 0x7f) fail('span_not_ascii', s.id, 'source');
    if (sha256(bytes) !== s.sha256) fail('span_sha', s.id, 'source');
    const text = Buffer.from(bytes).toString('latin1');
    return Object.freeze({ ...s, text });
  });
  const concat = Buffer.from(out.map((s) => s.text).join(''), 'latin1');
  if (concat.length !== closure.bytes || sha256(concat) !== closure.sha256) fail('closure_sha', `${concat.length}`, 'source');
  return Object.freeze(out);
}

// Authored prelude: realm-owned self, console removed, realm intrinsics
// captured before any copied definition runs, realm little-endian check.
export const PRELUDE = `var self = globalThis;
delete globalThis.console;
if (typeof console !== "undefined") throw new Error("console present");
if (new Uint8Array(new Uint32Array([1]).buffer)[0] !== 1) throw new Error("realm not little endian");
var __geomK = (function () {
  var TA = Object.getPrototypeOf(Uint8Array.prototype);
  var call = Function.prototype.call;
  var bind = function (f) { return call.bind(f); };
  var hex = [];
  for (var i = 0; i < 256; i++) hex.push((i < 16 ? "0" : "") + i.toString(16));
  return Object.freeze({
    tag: bind(Object.getOwnPropertyDescriptor(TA, Symbol.toStringTag).get),
    len: bind(Object.getOwnPropertyDescriptor(TA, "length").get),
    off: bind(Object.getOwnPropertyDescriptor(TA, "byteOffset").get),
    buf: bind(Object.getOwnPropertyDescriptor(TA, "buffer").get),
    abLen: bind(Object.getOwnPropertyDescriptor(ArrayBuffer.prototype, "byteLength").get),
    keys: Object.keys, isArray: Array.isArray, hasOwn: Object.prototype.hasOwnProperty.call.bind(Object.prototype.hasOwnProperty),
    stringify: JSON.stringify, U8: Uint8Array, isFinite: Number.isFinite, getProto: Object.getPrototypeOf,
    hex: Object.freeze(hex), join: call.bind(Array.prototype.join), push: call.bind(Array.prototype.push),
  });
})();
`;
export const buildScaffold = (spans) => PRELUDE + spans.map((s) => s.text).join('');

const numLit = (v) => {
  if (typeof v !== 'number' || !Number.isFinite(v)) fail('bad_literal', String(v), 'admission');
  return Object.is(v, -0) ? '-0' : String(v);
};

// Bounded bootstrap/structure/call/serialize. Only validated primitives are
// embedded. Phase one constructs the unchanged Model exactly once, retains it
// only as realm-owned state and returns a bounded primitive structure string
// (including each node's sorted distinct observed primary smooth groups). The
// host validates it against the independent preflight before phase two runs
// the unchanged hasAnimation/createInstance/compile calls on that same model.
export function buildStructureScript(limits) {
  return `(function () {
"use strict";
var K = __geomK;
var input = globalThis.__geomInput;
globalThis.__geomInput = undefined;
delete globalThis.__geomInput;
var num = function (v) { if (typeof v !== "number") throw new Error("non-number"); return Object.is(v, -0) ? "-0" : String(v); };
var nums = function (a) { var o = []; for (var i = 0; i < a.length; i++) K.push(o, num(a[i])); return o; };
var lenOrNull = function (a) { return a === undefined ? null : a.length; };
var model = new RSM(input);
input = undefined;
if (K.getProto(model) !== RSM.prototype || K.hasOwn(model, "createInstance") || K.hasOwn(model, "compile") || K.hasOwn(model, "hasAnimation")) throw new Error("model methods shadowed");
var nodes = model.nodes;
if (!K.isArray(nodes) || nodes.length < 1 || nodes.length > ${numLit(limits.max_nodes)}) throw new Error("node count bound");
var structure = {
  version: num(model.version), animLen: num(model.animLen), shadeType: num(model.shadeType), alpha: num(model.alpha),
  frameRatePerSecond: num(model.frameRatePerSecond), textures: model.textures.slice(), volume_boxes: model.volumebox.length,
  main_is_first: model.main_node === nodes[0], posKeyframes: model.posKeyframes.length, nodes: []
};
for (var n = 0; n < nodes.length; n++) {
  var node = nodes[n], faces = node.faces;
  if (!K.isArray(faces) || faces.length < 1 || faces.length > ${numLit(limits.max_faces_per_node)}) throw new Error("face count bound");
  var used = [];
  for (var g = 0; g < 32; g++) K.push(used, false);
  for (var f = 0; f < faces.length; f++) {
    var face = faces[f];
    if (face === null || typeof face !== "object") throw new Error("face shape");
    var group = face.smoothGroup;
    if (typeof group !== "number" || !(group >= 0 && group <= 31) || (group | 0) !== group) throw new Error("primary group bound");
    used[group] = true;
  }
  var groups = [];
  for (var h = 0; h < 32; h++) if (used[h] === true) K.push(groups, h);
  K.push(structure.nodes, { name: node.name, parentname: node.parentname, textures: nums(node.textures), mat3: nums(node.mat3),
    offset: nums(node.offset), vertices: node.vertices.length, tvertices: node.tvertices.length, faces: faces.length,
    primary_smooth_groups: groups,
    keys: [lenOrNull(node.scaleKeyFrames), lenOrNull(node.rotKeyframes), lenOrNull(node.posKeyframes), lenOrNull(node.textureKeyFrameGroup)],
    is_only: node.is_only });
}
var text = K.stringify(structure);
globalThis.__geomState = model;
return text;
})();
`;
}

export function buildLifecycleScript(placement, ground, meshByteCap) {
  const arr = (a) => `[${a.map(numLit).join(', ')}]`;
  return `(function () {
"use strict";
var K = __geomK;
var model = globalThis.__geomState;
globalThis.__geomState = undefined;
delete globalThis.__geomState;
if (model === undefined || K.getProto(model) !== RSM.prototype) throw new Error("retained model missing");
var placement = { position: ${arr(placement.position)}, rotation: ${arr(placement.rotation)}, scale: ${arr(placement.scale)} };
var ground = { width: ${numLit(ground.width)}, height: ${numLit(ground.height)} };
var hasAnimation = model.hasAnimation();
if (hasAnimation !== false) throw new Error("hasAnimation not false");
var instancesBefore = model.instances.length;
if (instancesBefore !== 0) throw new Error("instances before");
model.createInstance(placement, ground.width, ground.height);
var instancesAfter = model.instances.length;
if (instancesAfter !== 1) throw new Error("instances after");
var compiled = model.compile();
model = undefined;
if (compiled === null || typeof compiled !== "object" || !K.isArray(compiled.meshes)) throw new Error("compile shape");
var meshes = compiled.meshes, total = 0, checked = [];
for (var m = 0; m < meshes.length; m++) {
  var mesh = meshes[m];
  if (mesh === null || typeof mesh !== "object") throw new Error("mesh shape");
  var keys = K.keys(mesh), entries = [];
  for (var k = 0; k < keys.length; k++) {
    var a = mesh[keys[k]];
    if (K.tag(a) !== "Float32Array") throw new Error("mesh brand");
    var length = K.len(a), buffer = K.buf(a);
    if (K.off(a) !== 0 || K.abLen(buffer) !== length * 4 || length % 9 !== 0) throw new Error("mesh extent");
    for (var j = 0; j < length; j++) { var x = a[j]; if (!K.isFinite(x)) throw new Error("mesh nonfinite"); }
    total += length * 4;
    if (total > ${numLit(meshByteCap)}) throw new Error("mesh byte cap");
    K.push(entries, [keys[k], length, buffer]);
  }
  K.push(checked, entries);
}
var out = [];
for (var c = 0; c < checked.length; c++) {
  var row = [];
  for (var e = 0; e < checked[c].length; e++) {
    var ent = checked[c][e], bytes = new K.U8(ent[2], 0, ent[1] * 4), parts = [];
    for (var b = 0; b < bytes.length; b++) K.push(parts, K.hex[bytes[b]]);
    K.push(row, [ent[0], ent[1], K.join(parts, "")]);
  }
  K.push(out, row);
}
var textures = compiled.textures;
if (!K.isArray(textures)) throw new Error("textures shape");
return K.stringify({ v: 1, hasAnimation: hasAnimation, instances_before: instancesBefore,
  instances_after: instancesAfter, textures: textures.slice(), meshes: out });
})();
`;
}
// Drops every retained realm reference; run on every compileInRealm path.
const CLEANUP_SCRIPT = `globalThis.__geomState = undefined; delete globalThis.__geomState;
globalThis.__geomInput = undefined; delete globalThis.__geomInput; void 0;
`;

// ---------------------------------------------------------------- bridge

const HEX = /^[0-9a-f]*$/;
function exactObject(o, keys, where) {
  if (o === null || typeof o !== 'object' || Array.isArray(o)) fail('bridge_shape', `${where} not object`, 'validate');
  const got = Object.keys(o);
  if (got.length !== keys.length || keys.some((k, i) => got[i] !== k)) fail('bridge_shape', `${where} keys`, 'validate');
}
const parseNum = (s, where) => {
  if (typeof s !== 'string' || !/^-?(0|[1-9][0-9]*)(\.[0-9]+)?(e[+-][0-9]+)?$/.test(s)) fail('bridge_shape', `${where} number`, 'validate');
  return s === '-0' ? -0 : Number(s);
};
const sameNums = (a, b) => Array.isArray(a) && a.length === b.length && a.every((v, i) => Object.is(v, b[i]));
const sameStrings = (a, b) => Array.isArray(a) && a.length === b.length && a.every((v, i) => v === b[i]);
const parseBridge = (text, limits, stage) => {
  if (typeof text !== 'string') fail('bridge_type', typeof text, stage);
  if (text.length > limits.max_result_bytes) fail('result_over_cap', String(text.length), stage);
  try { return JSON.parse(text); } catch { return fail('bridge_json', 'invalid JSON', stage); }
};

// Validates the constructed-structure bridge against the independent host
// preflight. Observed fields come only from the realm string.
export function validateStructure(text, pre, limits) {
  const s = parseBridge(text, limits, 'structure');
  exactObject(s, ['version', 'animLen', 'shadeType', 'alpha', 'frameRatePerSecond', 'textures', 'volume_boxes', 'main_is_first', 'posKeyframes', 'nodes'], 'structure');
  // Constructor computes version as 2 + 3/10 in binary64.
  if (!Object.is(parseNum(s.version, 'version'), 2 + 3 / 10) || parseNum(s.animLen, 'animLen') !== pre.animLen || parseNum(s.shadeType, 'shadeType') !== pre.shadeType
    || !Object.is(parseNum(s.alpha, 'alpha'), pre.alpha) || !Object.is(parseNum(s.frameRatePerSecond, 'fps'), pre.frameRatePerSecond)
    || s.volume_boxes !== pre.volume_boxes || s.main_is_first !== true || s.posKeyframes !== 0) fail('structure_mismatch', 'model header', 'structure');
  if (!sameStrings(s.textures, pre.textures)) fail('structure_mismatch', 'textures', 'structure');
  if (!Array.isArray(s.nodes) || s.nodes.length !== pre.nodes.length) fail('structure_mismatch', 'node count', 'structure');
  s.nodes.forEach((n, i) => {
    const p = pre.nodes[i];
    exactObject(n, ['name', 'parentname', 'textures', 'mat3', 'offset', 'vertices', 'tvertices', 'faces', 'primary_smooth_groups', 'keys', 'is_only'], `nodes[${i}]`);
    const nn = (a, w) => { if (!Array.isArray(a)) fail('bridge_shape', w, 'structure'); return a.map((x) => parseNum(x, w)); };
    if (n.name !== p.name || n.parentname !== p.parentname || !sameNums(nn(n.textures, 'textures'), p.global_texture_keys)
      || !sameNums(nn(n.mat3, 'mat3'), p.mat3) || !sameNums(nn(n.offset, 'offset'), p.offset) || n.vertices !== p.vertices
      || n.tvertices !== 6 * p.uvs || n.faces !== p.faces || !sameNums(n.keys, [0, 0, 0, 0]) || n.is_only !== (pre.nodes.length === 1)) fail('structure_mismatch', `node ${i}`, 'structure');
    if (!sameNums(n.primary_smooth_groups, p.primary_smooth_groups)) fail('structure_mismatch', `node ${i} primary smooth groups`, 'structure');
  });
  return s;
}

// Validates the lifecycle/mesh bridge, decodes every mesh byte outside the VM
// and hashes it.
export function validateBridge(text, pre, limits) {
  const o = parseBridge(text, limits, 'validate');
  exactObject(o, ['v', 'hasAnimation', 'instances_before', 'instances_after', 'textures', 'meshes'], 'bridge');
  if (o.v !== 1 || o.hasAnimation !== false || o.instances_before !== 0 || o.instances_after !== 1) fail('bridge_lifecycle', 'animation/instance gates', 'validate');
  if (!sameStrings(o.textures, pre.textures)) fail('structure_mismatch', 'textures', 'validate');
  if (!Array.isArray(o.meshes) || o.meshes.length !== pre.nodes.length) fail('mesh_shape', 'mesh count', 'validate');
  const meshes = []; const bounds = [];
  let total = 0;
  o.meshes.forEach((row, i) => {
    const want = pre.nodes[i].mesh_layout;
    if (!Array.isArray(row) || row.length !== want.length) fail('mesh_shape', `node ${i} keys`, 'validate');
    const min = [Infinity, Infinity, Infinity]; const max = [-Infinity, -Infinity, -Infinity];
    row.forEach((ent, j) => {
      if (!Array.isArray(ent) || ent.length !== 3) fail('mesh_shape', `node ${i} entry`, 'validate');
      const [key, floats, hex] = ent;
      if (key !== want[j][0] || floats !== want[j][1]) fail('mesh_shape', `node ${i} key/count`, 'validate');
      if (typeof hex !== 'string' || hex.length !== floats * 8 || !HEX.test(hex)) fail('mesh_bytes', `node ${i} hex`, 'validate');
      const bytes = Buffer.from(hex, 'hex');
      if (bytes.length !== floats * 4) fail('mesh_bytes', `node ${i} length`, 'validate');
      total += bytes.length;
      if (total > limits.max_mesh_bytes) fail('mesh_bytes', 'mesh cap', 'validate');
      const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.length);
      for (let f = 0; f < floats; f++) {
        const x = dv.getFloat32(f * 4, true);
        if (!Number.isFinite(x)) fail('mesh_nonfinite', `node ${i} lane ${f}`, 'validate');
        const lane = f % 9;
        if (lane < 3) { min[lane] = Math.min(min[lane], x); max[lane] = Math.max(max[lane], x); }
      }
      meshes.push({ node_index: i, texture_key: key, float_count: floats, byte_length: bytes.length, float32_le_hex: hex, sha256: sha256(bytes) });
    });
    bounds.push({ node_index: i, basis: 'observed from emitted mesh positions (face-referenced vertices only)', min, max });
  });
  if (total !== pre.resources.mesh_bytes) fail('mesh_bytes', `total ${total}`, 'validate');
  return { textures: o.textures, meshes, observed_emitted_bounds: bounds };
}

// ---------------------------------------------------------------- one realm

// Compiles one admitted body in one fresh realm. scaffold is the qualified
// scaffold in actual mode; tests may pass handwritten stubs. The complete
// preflight and every cap run before any realm allocation, even for a stub.
export function compileInRealm(scaffold, body, placement, ground, limits, deadline, opts = {}) {
  const pre = preflightModel(body, placement, ground, limits);
  if (typeof scaffold !== 'string') fail('bad_scaffold', typeof scaffold, 'admission');
  const timeoutMs = opts.timeoutMs ?? limits.per_vm_timeout_ms;
  if (!Number.isSafeInteger(timeoutMs) || timeoutMs <= 0 || timeoutMs > limits.per_vm_timeout_ms) fail('over_cap', `timeout ${timeoutMs}`, 'admission');
  checkLittleEndian(opts.endianness);
  checkEffectiveHeap(opts.heapStats, limits.max_effective_v8_heap_bytes);
  const length = body.length;
  const structureText = buildStructureScript(limits);
  const callText = buildLifecycleScript(pre.placement, pre.ground, limits.max_mesh_bytes);
  const timing = {};
  let context;
  const run = (script, stage) => {
    const left = deadline.check(stage);
    const t0 = performance.now();
    try {
      return script.runInContext(context, { timeout: Math.max(1, Math.min(timeoutMs, Math.floor(left))), breakOnSigint: false });
    } catch (e) {
      if (e?.code === 'ERR_SCRIPT_EXECUTION_TIMEOUT') fail('vm_timeout', `${stage} exceeded ${timeoutMs}ms`, stage);
      fail(stage === 'compile' ? 'compile_error' : 'vm_error', `${e?.name}: ${String(e?.message).slice(0, 300)}`, stage);
    } finally {
      timing[`${stage}_ms`] = performance.now() - t0;
    }
  };
  deadline.check('realm');
  realmStats.created++;
  context = vm.createContext(vm.constants.DONT_CONTEXTIFY, { codeGeneration: { strings: false, wasm: false }, microtaskMode: 'afterEvaluate' });
  let primary = null;
  try {
    realmStats.definitions++;
    run(new vm.Script(scaffold, { filename: 'model-geometry-scaffold.js' }), 'definitions');
    let input = run(new vm.Script(`globalThis.__geomInput = new Uint8Array(${numLit(length)}); globalThis.__geomInput;`), 'allocate');
    if (!types.isUint8Array(input) || types.isProxy(input) || taLength(input) !== length || taByteOffset(input) !== 0 || abByteLength(taBuffer(input)) !== length) fail('realm_input', 'allocation brand/length', 'allocate');
    deadline.check('copy');
    taSet(input, body, 0);
    // Encoded-copy SHA joins the body SHA only (never mesh bytes).
    const copy_sha256 = sha256(new Uint8Array(taBuffer(input), 0, length));
    input = null;
    if (copy_sha256 !== sha256(body)) fail('realm_copy', 'copied bytes differ from body', 'copy');
    realmStats.structure++;
    const structureBridge = run(new vm.Script(structureText, { filename: 'model-geometry-structure.js' }), 'structure');
    deadline.check('structure');
    const structure = validateStructure(structureBridge, pre, limits);
    deadline.check('structure');
    realmStats.lifecycle++;
    const text = run(new vm.Script(callText, { filename: 'model-geometry-lifecycle.js' }), 'compile');
    deadline.check('validate');
    const t0 = performance.now();
    const out = validateBridge(text, pre, limits);
    timing.validate_hash_ms = performance.now() - t0;
    deadline.check('validate');
    return { preflight: pre, copy_sha256, structure, ...out, timing };
  } catch (e) {
    primary = e;
    throw e;
  } finally {
    // Clear retained realm references on every path; a cleanup fault never
    // replaces a primary error and is explicit when there is none.
    try {
      new vm.Script(CLEANUP_SCRIPT, { filename: 'model-geometry-cleanup.js' }).runInContext(context, { timeout: Math.max(1, Math.min(timeoutMs, 50)), breakOnSigint: false });
    } catch (ce) {
      if (primary) attachDiagnostic(primary, diagnostic(ce, 'realm cleanup'));
      else { context = null; fail('realm_cleanup', String(ce?.message ?? ce).slice(0, 200), 'cleanup'); }
    }
    context = null;
    // Successful cleanup is part of this exported helper's command deadline.
    // Expired/failed paths still clean up and retain their original error.
    if (!primary) deadline.check('cleanup');
  }
}

// ---------------------------------------------------------------- profile

const DECIMAL = /^(0|[1-9][0-9]*)$/;
const HEX64 = /^[0-9a-f]{64}$/;
const MAX_U64 = (1n << 64n) - 1n;
const pfail = (detail) => fail('profile_schema', detail, 'profile');
function exactKeys(obj, keys, where) {
  if (!obj || typeof obj !== 'object' || Array.isArray(obj)) pfail(`${where} not object`);
  const got = Object.keys(obj);
  if (got.length !== keys.length || keys.some((k, i) => got[i] !== k)) pfail(`${where} keys ${got.join(',')}`);
}
const eq = (v, want, where) => { if (!Object.is(v, want)) pfail(`${where}=${JSON.stringify(v)}`); };
function identityStrings(v, size, where) {
  if (!Array.isArray(v) || v.length !== 8) pfail(`${where} length`);
  for (const s of v) if (typeof s !== 'string' || !DECIMAL.test(s) || BigInt(s) > MAX_U64) pfail(`${where} not canonical decimal`);
  if (v[2] !== String(size)) pfail(`${where} size`);
  if (v[6] !== '1') pfail(`${where} nlink`);
  return Object.freeze([...v]);
}
function absPath(v, where) {
  if (typeof v !== 'string' || !path.isAbsolute(v) || path.normalize(v) !== v || v.includes('\0')) pfail(`${where} path`);
  return v;
}
function pinned(o, keys, where, want, withIdentity) {
  exactKeys(o, keys, where);
  absPath(o.path, where);
  eq(o.bytes, want.bytes, `${where}.bytes`);
  eq(o.sha256, want.sha256, `${where}.sha256`);
  return Object.freeze({ path: o.path, bytes: o.bytes, sha256: o.sha256, identity: withIdentity ? identityStrings(o.identity, o.bytes, `${where}.identity`) : null });
}
// Plain numbers everywhere; {"number":"-0"} only at rotation lane 0.
function placementScalar(v, where, tagAllowed) {
  if (typeof v === 'number') return v;
  if (tagAllowed && v && typeof v === 'object' && !Array.isArray(v) && Object.keys(v).length === 1 && v.number === '-0') return -0;
  pfail(`${where} object-valued scalar`);
}
function deepSame(a, b, where) {
  if (Array.isArray(b)) {
    if (!Array.isArray(a) || a.length !== b.length) pfail(`${where} length`);
    b.forEach((x, i) => deepSame(a[i], x, `${where}[${i}]`));
  } else if (b && typeof b === 'object') {
    exactKeys(a, Object.keys(b), where);
    for (const k of Object.keys(b)) deepSame(a[k], b[k], `${where}.${k}`);
  } else eq(a, b, where);
}
const PROFILE_KEYS = ['schema', 'task', 'profile_admits_execution', 'identity_fields', 'identity_encoding', 'source', 'inventory', 'source_closure_bytes',
  'source_closure_sha256', 'fixture', 'model_index', 'original_query_index', 'map_index', 'group_index', 'placement_index', 'body', 'placement', 'ground',
  'expected_static_structure', 'resource_expected', 'bounds', 'independent_preflight_provenance', 'evidence_boundary'];
const NODE_KEYS = ['node_index', 'name', 'parentname', 'textures', 'mat3', 'offset', 'vertices', 'uvs', 'faces', 'primary_smooth_groups', 'key_counts', 'global_texture_keys', 'mesh_float_count', 'mesh_bytes'];
const STRUCTURE_KEYS = ['version', 'animLen', 'shadeType', 'alpha', 'frameRatePerSecond', 'unused_global_names', 'volume_boxes', 'consumed_bytes', 'nodes'];

// Validates the complete profile and its resource totals before any body is
// opened. frozen exists so tests can bind an authored tiny model.
export function validateProfile(profile, { limits = PROFILE_BOUNDS, frozen = FROZEN } = {}) {
  checkBoundsWithin(limits);
  exactKeys(profile, PROFILE_KEYS, 'profile');
  eq(profile.schema, PROFILE_SCHEMA, 'schema');
  eq(profile.task, TASK, 'task');
  eq(profile.profile_admits_execution, false, 'profile_admits_execution');
  if (!Array.isArray(profile.identity_fields) || profile.identity_fields.join() !== IDENTITY_FIELDS.join()) pfail('identity_fields');
  eq(profile.identity_encoding, 'lossless canonical decimal strings in identity_fields order', 'identity_encoding');
  const source = pinned(profile.source, ['path', 'bytes', 'sha256', 'identity'], 'source', SOURCE_PIN, true);
  const inventory = pinned(profile.inventory, ['path', 'bytes', 'sha256', 'identity'], 'inventory', INVENTORY_PIN, true);
  eq(profile.source_closure_bytes, CLOSURE_PIN.bytes, 'source_closure_bytes');
  eq(profile.source_closure_sha256, CLOSURE_PIN.sha256, 'source_closure_sha256');
  const fixture = pinned(profile.fixture, ['path', 'bytes', 'sha256'], 'fixture', FIXTURE_PIN, false);
  for (const k of ['model_index', 'original_query_index', 'map_index', 'group_index', 'placement_index']) eq(profile[k], frozen[k], k);
  const body = pinned(profile.body, ['path', 'bytes', 'sha256', 'identity'], 'body', frozen.body, true);
  if (path.basename(body.path) !== `body-${String(frozen.original_query_index).padStart(4, '0')}.bin`) pfail('body path name');
  if (new Set([source.path, inventory.path, fixture.path, body.path]).size !== 4) pfail('input paths not distinct');
  if (body.bytes > limits.max_body_bytes || body.bytes <= 0) fail('over_cap', `body ${body.bytes}`, 'profile');
  const pl = profile.placement;
  exactKeys(pl, ['position', 'rotation', 'scale'], 'placement');
  const placement = {};
  for (const k of ['position', 'rotation', 'scale']) {
    if (!Array.isArray(pl[k]) || pl[k].length !== 3) pfail(`placement.${k}`);
    placement[k] = [0, 1, 2].map((i) => {
      if (!Object.hasOwn(pl[k], i)) pfail(`placement.${k}[${i}] sparse`);
      return placementScalar(pl[k][i], `placement.${k}[${i}]`, k === 'rotation' && i === 0);
    });
    placement[k].forEach((v, i) => eq(v, frozen.placement[k][i], `placement.${k}[${i}]`));
  }
  exactKeys(profile.ground, ['width', 'height'], 'ground');
  eq(profile.ground.width, frozen.ground.width, 'ground.width');
  eq(profile.ground.height, frozen.ground.height, 'ground.height');
  const st = profile.expected_static_structure;
  exactKeys(st, STRUCTURE_KEYS, 'expected_static_structure');
  if (!Array.isArray(st.nodes)) pfail('nodes');
  st.nodes.forEach((n, i) => exactKeys(n, NODE_KEYS, `nodes[${i}]`));
  // JSON 1.0/30.0 parse to 1/30; deepSame compares with Object.is.
  deepSame(st, frozen.expected_static_structure, 'expected_static_structure');
  if (st.consumed_bytes !== body.bytes) pfail('consumed_bytes');
  if (st.nodes.length < 1 || st.nodes.length > limits.max_nodes) fail('over_cap', 'nodes', 'profile');
  let mesh = 0; let principal = 0; let principal32 = 0; let work = 0;
  st.nodes.forEach((n, i) => {
    const V = n.vertices; const F = n.faces; const G = n.primary_smooth_groups.length;
    if (n.node_index !== i || V < 1 || F < 1 || V > limits.max_vertices_per_node || n.uvs > limits.max_uvs_per_node || F > limits.max_faces_per_node) fail('over_cap', `node ${i} counts`, 'profile');
    if (n.primary_smooth_groups.some((g, j) => !Number.isSafeInteger(g) || g < 0 || g > limits.max_primary_smooth_group || (j && g <= n.primary_smooth_groups[j - 1]))) pfail(`node ${i} groups`);
    if (n.mesh_float_count !== 27 * F || n.mesh_bytes !== 108 * F) pfail(`node ${i} mesh`);
    mesh += 108 * F; principal += 120 * F + 12 * V + 12 * G * V; principal32 += 120 * F + 12 * V + 384 * V; work += G * V * F;
  });
  const computed = { mesh_bytes: mesh, principal_typed_bytes: principal, principal_typed_bytes_if32groups: principal32, smooth_face_visits: work };
  exactKeys(profile.resource_expected, Object.keys(computed), 'resource_expected');
  for (const k of Object.keys(computed)) { eq(profile.resource_expected[k], computed[k], `resource_expected.${k}`); eq(computed[k], frozen.resource_expected[k], `frozen ${k}`); }
  if (principal > limits.max_principal_typed_bytes || work > limits.max_smooth_face_visits || mesh > limits.max_mesh_bytes) fail('over_cap', `resources ${principal}/${work}/${mesh}`, 'profile');
  exactKeys(profile.bounds, Object.keys(PROFILE_BOUNDS), 'bounds');
  for (const k of Object.keys(PROFILE_BOUNDS)) eq(profile.bounds[k], PROFILE_BOUNDS[k], `bounds.${k}`);
  exactKeys(profile.independent_preflight_provenance, ['bytes', 'sha256'], 'independent_preflight_provenance');
  deepSame(profile.independent_preflight_provenance, frozen.independent_preflight_provenance, 'independent_preflight_provenance');
  if (!HEX64.test(profile.independent_preflight_provenance.sha256)) pfail('provenance sha');
  if (typeof profile.evidence_boundary !== 'string' || profile.evidence_boundary.length === 0) pfail('evidence_boundary');
  return Object.freeze({ source, inventory, fixture, body, placement: Object.freeze(placement), ground: Object.freeze({ ...profile.ground }), expected: st, resources: Object.freeze(computed) });
}

// Binds the inventory's executable closure to the pinned regions.
export function validateInventory(inv) {
  if (!inv || typeof inv !== 'object') fail('inventory_schema', 'not object', 'inventory');
  if (inv.worker?.bytes !== SOURCE_PIN.bytes || inv.worker?.sha256 !== SOURCE_PIN.sha256 || inv.worker?.LF_count !== SOURCE_PIN.lf_count) fail('inventory_schema', 'worker pin', 'inventory');
  if (inv.closure_executable_bytes !== CLOSURE_PIN.bytes || inv.closure_sha256_concat_in_order !== CLOSURE_PIN.sha256) fail('inventory_schema', 'closure pin', 'inventory');
  if (!Array.isArray(inv.executable_closure_order) || inv.executable_closure_order.join() !== SPANS.map((s) => s.id).join()) fail('inventory_schema', 'closure order', 'inventory');
  if (!Array.isArray(inv.executable_closure) || inv.executable_closure.length !== SPANS.length) fail('inventory_schema', 'closure rows', 'inventory');
  SPANS.forEach((s, i) => {
    const r = inv.executable_closure[i];
    for (const k of Object.keys(s)) if (r?.[k] !== s[k]) fail('inventory_schema', `closure ${s.id}.${k}`, 'inventory');
  });
}

// ---------------------------------------------------------------- outputs

// Fresh exclusive 0700 run directory under an existing real (non-symlink)
// prefix. Creation ownership joins three observations: the prefix ancestry
// captured before mkdir, the first post-create lstat of the new directory, and
// a provisional full namespace captured afterwards; the provisional namespace
// must equal both and is rechecked (plus emptiness) before it becomes the
// trusted run authority. Boundary: path-only mkdir/lstat cannot exclude a
// replacement made between mkdir and that first lstat; a replacement after the
// first lstat refuses here before any write into it.
const pinIdentity = (st) => [st.dev, st.ino, st.mode, st.uid].map(String);
function createRunDirectory(prefix) {
  if (typeof prefix !== 'string' || !path.isAbsolute(prefix) || path.normalize(prefix) !== prefix) throw new ObserverRefusal('bad_prefix', 'absolute normalized prefix required');
  const st = fs.lstatSync(prefix, { bigint: true });
  if (!st.isDirectory() || st.isSymbolicLink() || fs.realpathSync(prefix) !== prefix) throw new ObserverRefusal('bad_prefix', 'real directory required');
  if ((st.mode & 0o077n) !== 0n) throw new ObserverRefusal('bad_prefix', 'private 0700 prefix required');
  const lost = (detail) => { throw new ObserverRefusal('run_directory_ownership', detail); };
  let ancestry;
  try { ancestry = parentPins(path.join(prefix, 'run-')); } catch { lost('prefix ancestry'); }
  if (ancestry[0].path !== prefix || !sameIdentity(ancestry[0].identity, pinIdentity(st))) lost('prefix changed before create');
  const dir = path.join(prefix, `run-${new Date().toISOString().replace(/[:.]/g, '')}-${process.pid}-${randomBytes(4).toString('hex')}`);
  fs.mkdirSync(dir, { mode: 0o700 });
  const made = fs.lstatSync(dir, { bigint: true });
  if (!made.isDirectory() || (made.mode & 0o777n) !== 0o700n) throw new ObserverRefusal('bad_prefix', 'run directory mode');
  if (typeof process.getuid === 'function' && made.uid !== BigInt(process.getuid())) lost('run directory owner');
  const first = pinIdentity(made);
  let provisional;
  try { provisional = parentPins(path.join(dir, 'owned-output')); } catch { lost('namespace capture'); }
  const joins = () => provisional.length === ancestry.length + 1 && provisional[0].path === dir && sameIdentity(provisional[0].identity, first)
    && ancestry.every((p, i) => provisional[i + 1].path === p.path && sameIdentity(provisional[i + 1].identity, p.identity));
  if (!joins()) lost('run directory or ancestry replaced after first observation');
  try { checkParents(provisional); } catch { lost('namespace recheck'); }
  if (!sameIdentity(pinIdentity(fs.lstatSync(dir, { bigint: true })), first) || fs.readdirSync(dir).length !== 0) lost('run directory changed before authority');
  return { dir, parents: provisional };
}

const OUTPUT_PIN = Symbol('output authority');
function sealOutput(dir, record, guard = () => {}) {
  guard(); const a = record[OUTPUT_PIN]; checkParents(a.parents);
  const file = path.join(dir, record.file); const pre = fs.lstatSync(file, { bigint: true });
  if (!sameIdentity(identityOf(pre), a.identity)) fail('output_identity', 'output literal changed', 'publication');
  const fd = fs.openSync(file, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW);
  withFd(fd, `readback ${record.file}`, 'publication', () => {
    if (!sameIdentity(identityOf(fs.fstatSync(fd, { bigint: true })), a.identity)) fail('output_identity', 'output FD changed', 'publication');
    const b = Buffer.alloc(record.bytes); let off = 0;
    while (off < b.length) { guard(); const n = fs.readSync(fd, b, off, Math.min(65536, b.length - off), off); if (!n) fail('output_readback', 'short output', 'publication'); off += n; }
    if (fs.readSync(fd, Buffer.alloc(1), 0, 1, off) !== 0 || sha256(b) !== record.sha256) fail('output_readback', 'output bytes mismatch', 'publication');
    if (!sameIdentity(identityOf(fs.fstatSync(fd, { bigint: true })), a.identity)) fail('output_identity', 'output changed while reading', 'publication');
  });
  checkParents(a.parents);
  if (!sameIdentity(identityOf(fs.lstatSync(file, { bigint: true })), a.identity)) fail('output_identity', 'output changed while closing', 'publication'); guard();
}
// parents: the trusted run-directory namespace. When given, it is rechecked
// instead of adopting whatever namespace the path names now; null captures a
// fresh namespace (standalone use only, never inside runObserver).
export function writeExclusive(dir, name, data, guard = () => {}, parents = null) {
  guard(); const bytes = Buffer.from(data); if (bytes.length > PROFILE_BOUNDS.max_result_bytes) fail('result_over_cap', 'capture exceeds1MiB', 'publication');
  const file = path.join(dir, name);
  if (parents) checkParents(parents); else parents = parentPins(file);
  const fd = fs.openSync(file, fs.constants.O_RDWR | fs.constants.O_CREAT | fs.constants.O_EXCL | fs.constants.O_NOFOLLOW, 0o600);
  const identity = withFd(fd, `write ${name}`, 'publication', () => {
    fs.writeFileSync(fd, bytes); fs.fsyncSync(fd); const st = fs.fstatSync(fd, { bigint: true });
    if (!st.isFile() || st.nlink !== 1n || (st.mode & 511n) !== 384n || st.size !== BigInt(bytes.length)) fail('output_identity', 'unsafe output', 'publication');
    return identityOf(st);
  });
  const record = { file: name, bytes: bytes.length, sha256: sha256(bytes) }; Object.defineProperty(record, OUTPUT_PIN, { value: { identity, parents } }); sealOutput(dir, record, guard); return record;
}
function linkedOutput(dir, candidate, guard) {
  sealOutput(dir, candidate, guard); fs.linkSync(path.join(dir, candidate.file), path.join(dir, 'result.json'));
  candidate[OUTPUT_PIN].linked = true;
  const now = identityOf(fs.lstatSync(path.join(dir, candidate.file), { bigint: true })); const old = candidate[OUTPUT_PIN].identity;
  if (now[6] !== '2' || [0, 1, 2, 3, 5, 7].some((i) => now[i] !== old[i])) fail('output_identity', 'unexpected link transition', 'publication');
  candidate[OUTPUT_PIN].identity = now;
  const final = { file: 'result.json', bytes: candidate.bytes, sha256: candidate.sha256 }; Object.defineProperty(final, OUTPUT_PIN, { value: { identity: now, parents: candidate[OUTPUT_PIN].parents } });
  sealOutput(dir, candidate, guard); sealOutput(dir, final, guard); return final;
}

// ---------------------------------------------------------------- observer

// Retires only this call's positively identified PASS alias. Preservation is
// exclusive (link to a free name; occupied files/directories are never
// overwritten), ownership is rechecked before each mutation, a foreign final
// is left untouched and every IO failure is reported, never as retirement.
// The candidate file keeps the published bytes whatever happens here.
const UNQUALIFIED = ['result.unqualified.json', ...[1, 2, 3, 4, 5, 6, 7].map((i) => `result.unqualified-${i}.json`)];
function retireAlias(dir, candidate, ownership) {
  const id = candidate[OUTPUT_PIN].identity;
  const final = path.join(dir, 'result.json');
  const ours = (p) => { const st = fs.lstatSync(p, { bigint: true }); return st.isFile() && String(st.dev) === id[0] && String(st.ino) === id[1]; };
  const r = { status: 'failed', preserved_as: null, occupied: [], errors: [] };
  const step = (what, fn) => { try { ownership(); } catch (e) { r.status = 'ownership_lost'; r.errors.push(diagnostic(e, `ownership before ${what}`)); return false; } try { fn(); return true; } catch (e) { r.errors.push(diagnostic(e, what)); return false; } };
  let present = true;
  if (!step('inspect final', () => {
    try { if (!ours(final)) { r.status = 'foreign_final_untouched'; present = false; } } catch (e) { if (e.code !== 'ENOENT') throw e; r.status = 'absent'; present = false; }
  })) return r;
  if (!present) return r;
  for (const name of UNQUALIFIED) {
    let occupied = false;
    const ok = step(`preserve ${name}`, () => {
      try { fs.linkSync(final, path.join(dir, name)); } catch (e) { if (e.code === 'EEXIST') { occupied = true; return; } throw e; }
      if (!ours(path.join(dir, name))) fail('output_identity', `${name} not this run's alias`, 'retirement');
      r.preserved_as = name;
    });
    if (occupied) { r.occupied.push(name); continue; }
    if (!ok) return r;
    break;
  }
  if (!step('unlink final', () => { if (!ours(final)) fail('output_identity', 'final changed before retirement', 'retirement'); fs.unlinkSync(final); })) return r;
  if (!step('confirm retired', () => { try { fs.lstatSync(final); } catch (e) { if (e.code === 'ENOENT') return; throw e; } fail('output_identity', 'final still present', 'retirement'); })) return r;
  r.status = 'retired';
  return r;
}

// pins.frozen/limits/clock/heapStats exist so tests can run an authored tiny
// profile within tiny caps; the CLI always uses the frozen defaults.
//
// Run ownership (the trusted run-directory namespace) is deadline-independent
// and gates every write, including failure publication and retirement after a
// deadline. Success authority additionally requires the deadline and every
// held input. Lost ownership returns bounded failure information here and
// writes nothing into whatever now occupies the run path.
export function runObserver({ profilePath, prefix, pins = { profile: PROFILE_PIN, frozen: FROZEN }, limits = PROFILE_BOUNDS, clock, heapStats } = {}) {
  checkBoundsWithin(limits); const heap = checkEffectiveHeap(heapStats, limits.max_effective_v8_heap_bytes); checkLittleEndian();
  const deadline = makeDeadline(limits.total_timeout_ms, clock);
  const { dir, parents: runParents } = createRunDirectory(prefix);
  const held = []; const outputs = []; const closeErrors = [];
  const record = { schema: RESULT_SCHEMA, task: TASK, status: 'FAIL', effective_v8_heap_bytes: heap, little_endian: true, limits };
  let error; let published; let candidate; let bodyAuthority = null; let observation = null;
  const closeInputs = () => { for (const h of held) { try { h.close(); } catch (e) { closeErrors.push(diagnostic(e, `input close ${h.stage}`)); } } };
  const ownership = () => checkParents(runParents);
  const authority = () => { deadline.check('authority'); ownership(); for (const h of held) h.literalRecheck('publication'); if (bodyAuthority) bodyAuthority('publication'); deadline.check('authority'); };
  const holdJson = (h, code) => { try { return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(h.bytes)); } catch { return fail(code, 'invalid UTF-8 JSON', h.stage); } };
  const hold = (h, stage) => { h.stage = stage; held.push(h); return h; };
  const meta = (p, h) => ({ path: p, bytes: h.bytes.length, sha256: h.sha256, identity_pre: h.identity });
  try {
    const prof = hold(readHeldInput(profilePath, pins.profile, 1 << 20, deadline, 'profile'), 'profile');
    const profile = validateProfile(holdJson(prof, 'profile_json'), { limits, frozen: pins.frozen });
    record.profile = meta(profilePath, prof);
    const src = hold(readHeldInput(profile.source.path, { bytes: SOURCE_PIN.bytes, sha256: SOURCE_PIN.sha256, identity: profile.source.identity }, SOURCE_PIN.bytes, deadline, 'source'), 'source');
    const inv = hold(readHeldInput(profile.inventory.path, { bytes: INVENTORY_PIN.bytes, sha256: INVENTORY_PIN.sha256, identity: profile.inventory.identity }, INVENTORY_PIN.bytes, deadline, 'inventory'), 'inventory');
    validateInventory(holdJson(inv, 'inventory_json'));
    // The declared fixture is read, held and fully hashed once like every
    // other declared input, and rechecked through final authority and close.
    const fix = hold(readHeldInput(profile.fixture.path, { bytes: FIXTURE_PIN.bytes, sha256: FIXTURE_PIN.sha256 }, FIXTURE_PIN.bytes, deadline, 'fixture'), 'fixture');
    const fixJson = holdJson(fix, 'fixture_json');
    if (fixJson?.task !== TASK || fixJson?.actual_execution_admitted !== false) fail('fixture_schema', 'task/admission fields', 'fixture');
    record.fixture = meta(profile.fixture.path, fix);
    const spans = extractSpans(src.bytes); const scaffold = buildScaffold(spans);
    record.source = meta(profile.source.path, src);
    record.inventory = meta(profile.inventory.path, inv);
    record.spans = spans.map(({ text, ...pin }) => pin); record.closure = { ...CLOSURE_PIN };
    record.scaffold = writeExclusive(dir, 'scaffold.js', scaffold, authority, runParents); outputs.push(record.scaffold);
    const body = readHeldInput(profile.body.path, { bytes: profile.body.bytes, sha256: profile.body.sha256, identity: profile.body.identity }, limits.max_body_bytes, deadline, 'body');
    let bodyPrimary = null;
    try {
      const pre = preflightModel(body.bytes, profile.placement, profile.ground, limits);
      checkStructure(pre, profile.expected, profile.resources);
      const out = compileInRealm(scaffold, body.bytes, profile.placement, profile.ground, limits, deadline, { heapStats });
      // Returned evidence is retained before any later check can fail.
      observation = { body: { path: profile.body.path, bytes: body.bytes.length, sha256: body.sha256, identity_pre: body.identity, identity_post_matches: false, encoded_copy_sha256: out.copy_sha256 }, out };
      body.recheck('final_use');
      observation.body.identity_post_matches = true;
      if (out.copy_sha256 !== profile.body.sha256) fail('realm_copy', 'encoded copy SHA differs from body pin', 'copy');
    } catch (e) { bodyPrimary = e; throw e; } finally {
      // A body close fault joins the sticky list; it never replaces a primary
      // error, and alone it is an explicit cleanup failure.
      let closeFailed = false;
      try { body.close(); } catch (ce) { closeErrors.push(diagnostic(ce, 'body close')); closeFailed = true; }
      body.releaseBytes();
      if (closeFailed && !bodyPrimary) fail('cleanup_failed', 'body close failed', 'cleanup'); // eslint-disable-line no-unsafe-finally
    }
    body.literalRecheck('after_close'); bodyAuthority = body.literalRecheck;
    for (const h of held) h.recheck('final_use'); authority(); closeInputs();
    if (closeErrors.length) fail('cleanup_failed', 'input close failed', 'cleanup'); authority();
    for (const k of ['profile', 'source', 'inventory', 'fixture']) record[k].identity_post_matches = true;
    const o = observation.out;
    record.model = { model_index: pins.frozen.model_index, original_query_index: pins.frozen.original_query_index, map_index: pins.frozen.map_index, group_index: pins.frozen.group_index, placement_index: pins.frozen.placement_index };
    record.body = observation.body;
    record.placement = { position: profile.placement.position, rotation: profile.placement.rotation.map((v) => (Object.is(v, -0) ? { number: '-0' } : v)), scale: profile.placement.scale, used_once_no_second_division_by5: true };
    record.ground = profile.ground;
    record.preflight = { resources: o.preflight.resources, consumed_bytes: o.preflight.consumed_bytes, nodes: o.preflight.nodes.map(({ raw, mesh_layout, ...n }) => n) };
    record.constructed_structure = o.structure;
    record.gates = { structure_matched_before_lifecycle: true, hasAnimation: false, instances_before: 0, instances_after: 1, compileAtFrame_used: false, source_methods_patched: false };
    record.textures = o.textures; record.meshes = o.meshes; record.observed_emitted_bounds = o.observed_emitted_bounds;
    record.reference_comparison = 'not performed here: mesh hashes are compared to the Root-owned independently frozen geometry reference; all-vertex bounds stay an independent reference expectation (the unreturned local vert array is not observed)';
    record.timing_ms = o.timing;
    record.status = 'PASS'; record.resource_note = 'Estimates exclude JS/VM/matrices/GC/copies; sampled RSS is not measured or capped here.'; record.elapsed_ms_before_publish = deadline.elapsed();
    const text = JSON.stringify(record, null, 1) + '\n'; if (Buffer.byteLength(text) > limits.max_result_bytes) fail('result_over_cap', String(Buffer.byteLength(text)), 'publish');
    candidate = writeExclusive(dir, 'result.candidate.json', text, authority, runParents); outputs.push(candidate); published = linkedOutput(dir, candidate, authority); outputs.push(published);
    authority(); for (const output of outputs) sealOutput(dir, output, authority);
    const elapsed = deadline.elapsed(); if (!(elapsed < limits.total_timeout_ms)) fail('deadline_exceeded', 'terminal command deadline', 'terminal');
    return { status: 'PASS', dir, result: { file: published.file, bytes: published.bytes, sha256: published.sha256 }, elapsed_ms: elapsed };
  } catch (e) { error = e; } finally { closeInputs(); }
  // Sticky diagnostics carried by the primary error join the run-level list.
  if (error?.closeDiagnostics) closeErrors.unshift(...error.closeDiagnostics);
  // Preserve every failed run and retire only this run's own terminal alias.
  const retirement = candidate?.[OUTPUT_PIN]?.linked ? retireAlias(dir, candidate, ownership) : { status: 'not_published' };
  // Failure evidence keeps full mesh hex when a compile returned, never body bytes.
  const failure = { schema: RESULT_SCHEMA, task: TASK, status: 'FAIL', code: error?.code ?? 'internal_error', stage: error?.stage ?? null, message: String(error?.message ?? error).slice(0, MAX_FAILURE_TEXT), timeout: error?.code === 'vm_timeout' || error?.code === 'deadline_exceeded', profile: record.profile ?? null, source: record.source ?? null, inventory: record.inventory ?? null, fixture: record.fixture ?? null, spans: record.spans ?? null, scaffold: record.scaffold ?? null, body: observation?.body ?? null, structure: observation?.out.structure ?? null, meshes: observation?.out.meshes ?? null, effective_v8_heap_bytes: heap, elapsed_ms: deadline.elapsed(), close_errors: closeErrors, retirement };
  const summary = () => ({ code: failure.code, stage: failure.stage, message: failure.message.slice(0, 500), timeout: failure.timeout, close_errors: closeErrors.slice(0, 16), retirement });
  const base = { status: 'FAIL', code: failure.code, stage: failure.stage, dir, timeout: failure.timeout, retirement: retirement.status };
  try { ownership(); } catch {
    return { ...base, ownership_lost: true, failure_write_error: 'run_directory_ownership_lost', failure_summary: summary() };
  }
  let text = JSON.stringify(failure, null, 1) + '\n'; if (Buffer.byteLength(text) > limits.max_result_bytes) text = JSON.stringify({ ...failure, meshes: 'elided over cap' }) + '\n';
  try { return { ...base, failure: writeExclusive(dir, 'failure.json', text, ownership, runParents) }; } catch (e) {
    // The capture itself failed: preserve its primary and close diagnostics
    // externally without replacing the original observer failure.
    if (e?.closeDiagnostics) closeErrors.push(...e.closeDiagnostics);
    return { ...base, failure_write_error: e.code ?? 'internal_error', failure_summary: { ...summary(), publication_error: diagnostic(e, 'failure publication') } };
  }
}

// Matches the independent body preflight to the profile's exact structure.
export function checkStructure(pre, expected, resources) {
  const mismatch = (w) => fail('structure_mismatch', w, 'preflight');
  for (const k of ['animLen', 'shadeType', 'alpha', 'frameRatePerSecond', 'volume_boxes', 'consumed_bytes']) if (!Object.is(pre[k], expected[k])) mismatch(k);
  if (pre.version !== expected.version) mismatch('version');
  if (pre.unused_global_names.join('\0') !== expected.unused_global_names.join('\0') || pre.unused_global_names.length !== expected.unused_global_names.length) mismatch('unused_global_names');
  if (pre.nodes.length !== expected.nodes.length) mismatch('nodes');
  pre.nodes.forEach((n, i) => {
    const e = expected.nodes[i];
    for (const k of NODE_KEYS) {
      const a = n[k]; const b = e[k];
      if (Array.isArray(b) ? !(a.length === b.length && b.every((x, j) => Object.is(a[j], x))) : !Object.is(a, b)) mismatch(`node ${i}.${k}`);
    }
  });
  for (const k of Object.keys(resources)) if (pre.resources[k] !== resources[k]) mismatch(`resources.${k}`);
}

// ---------------------------------------------------------------- CLI

export function main(argv, deps = {}) {
  if (!Array.isArray(argv) || argv.length !== 5 || argv[0] !== '--actual' || argv[1] !== '--profile' || argv[3] !== '--private-prefix') {
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
