#!/usr/bin/env node
// T07.007.014.009: finite Node worker_threads host for the unchanged compiled
// RSW/GAT/GND worker prefix plus the existing fixed diagnostic suffix.
//
//   node tools/renewal/probe_remaining_compiled_core.mjs --profile <path> --admission <path>
//
// One fresh sequential Worker per map evaluates one classic script: the
// complete unchanged prefix followed by the suffix (pilot: unchanged; each
// remaining map: only CH1_INPUTS and the embedded-terrain-name assertion are
// projected). The suffix fetches /body/{rsw,gat,gnd} from a fixed in-memory
// adapter; there is no HTTP, browser, CDP, MapLoader, FileManager or texture/
// model/water acquisition. Diagnostic RSW.compile runs before any texture load,
// unlike production MapLoader. A result is an observation, never qualification:
// Root qualifies. The admission convention is not an adversarial sandbox.
import { createHash, webcrypto } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { performance } from 'node:perf_hooks';
import { fileURLToPath } from 'node:url';
import { inspect } from 'node:util';
import vm from 'node:vm';
import { isMainThread, parentPort, Worker, workerData } from 'node:worker_threads';

export const PROFILE_PIN = Object.freeze({ bytes: 51941, sha256: 'c4cb8628fa565cded251fe32b6dcfeb90a74ff25c72c8b01938451d7b73aa620' });
export const PREFIX_PIN = Object.freeze({ bytes: 624463, sha256: '1501ca10336d91e4f8a0301101c43e5ca1a0ef1aa81212bbffb5690c68c13325' });
export const SUFFIX_PIN = Object.freeze({ bytes: 7310, sha256: '27d77dbd4fa206db9c9eb99bd15d691e73a207875f510b4f7518eedefeb33a91' });
export const PROFILE_SCHEMA = 'root-remaining-compiled-core-runtime-v1';
export const ADMISSION_SCHEMA = 'root-remaining-compiled-core-admission-v1';
export const MANIFEST_SCHEMA = 't07-007-014-009-compiled-core-host-manifest-v1';
export const MAP_REPORT_SCHEMA = 't07-007-014-009-compiled-core-map-report-v1';
export const CORE_SCHEMA = 'root014004-compiled-core-1';
export const IDENTITY_FIELDS = Object.freeze(['st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_mode', 'st_nlink', 'st_uid']);
export const IDENTITY_ENCODING = 'exact decimal strings; full st_mode; use fs bigint stats';
export const LIMITS = Object.freeze({
  all_run_deadline_ms: 1240000, inner_diagnostic_deadline_ms: 48000, input_body_bytes: 16777216,
  main_unique_body_bytes: 103067388, map_result_bytes: 8388608, outer_sampled_rss_bytes: 1610612736,
  pilot_unique_body_bytes: 4255734, stderr_bytes: 1048576, stdout_bytes: 1048576,
  total_retained_result_bytes: 185597952, worker_deadline_ms: 55000, worker_heap_mb: 1024
});
export const KIND_ORDER = Object.freeze(['rsw', 'gat', 'gnd']);
export const MAP_COUNT = 21;
export const BODY_COUNT = 55;
export const DIAGNOSTIC_ORDER_LIMIT = 'diagnostic RSW.compile runs before texture loading (no textures are loaded); production MapLoader order differs';
const ADMISSION_KEYS = ['execution_admitted', 'host', 'mode', 'output_path', 'profile_sha256', 'root_bound', 'schema'];
const ADMISSION_MAX_BYTES = 65536;
const WORKER_SCHEMA = 't07-007-014-009-worker-v1';
const HEX64 = /^[0-9a-f]{64}$/;
const DECIMAL = /^(0|[1-9][0-9]*)$/;
const S_IFMT = 0o170000n;
const S_IFREG = 0o100000n;
const S_IFDIR = 0o040000n;

export class Refusal extends Error {
  constructor(code, message) { super(message); this.name = 'Refusal'; this.code = code; }
}
const refuse = (code, message) => { throw new Refusal(code, message); };
const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex');
const errorRecord = (e, phase) => ({
  phase, name: String(e?.name ?? typeof e), message: String(e?.message ?? e),
  code: e?.code === undefined ? null : String(e.code), stack: typeof e?.stack === 'string' ? e.stack : null
});

// ---------------------------------------------------------------- arguments

export function parseArgs(argv) {
  const seen = new Map();
  for (let i = 0; i < argv.length; i += 2) {
    const flag = argv[i];
    if (flag !== '--profile' && flag !== '--admission') refuse('usage', `unknown argument: ${JSON.stringify(flag)}`);
    if (seen.has(flag)) refuse('usage', `duplicate argument: ${flag}`);
    const value = argv[i + 1];
    if (value === undefined || value === '' || value.startsWith('--')) refuse('usage', `missing value for ${flag}`);
    seen.set(flag, value);
  }
  for (const flag of ['--profile', '--admission']) if (!seen.has(flag)) refuse('usage', `missing argument: ${flag}`);
  return { profile: seen.get('--profile'), admission: seen.get('--admission') };
}

// ---------------------------------------------------------------- identity

// Exact decimal strings straight from bigint stats; never Number().
export function identityOf(stat) {
  if (typeof stat.ino !== 'bigint') refuse('identity', 'bigint stat required');
  return [stat.dev, stat.ino, stat.size, stat.mtimeNs, stat.ctimeNs, stat.mode, stat.nlink, stat.uid].map((v) => v.toString());
}
export function sameIdentity(a, b) {
  return Array.isArray(a) && Array.isArray(b) && a.length === 8 && b.length === 8 && a.every((v, i) => typeof v === 'string' && v === b[i]);
}
const dirIdentity = (stat) => [stat.dev, stat.ino, stat.mode, stat.uid].map((v) => v.toString());

function checkDescriptor(desc, label, maxBytes) {
  if (!desc || typeof desc !== 'object' || Array.isArray(desc)) refuse('profile', `${label}: descriptor object required`);
  const keys = Object.keys(desc).sort().join(',');
  if (keys !== 'bytes,identity,path,sha256') refuse('profile', `${label}: descriptor keys ${keys}`);
  if (typeof desc.path !== 'string' || !path.isAbsolute(desc.path) || path.normalize(desc.path) !== desc.path) refuse('profile', `${label}: absolute normalized path required`);
  if (!Number.isSafeInteger(desc.bytes) || desc.bytes < 0 || (maxBytes !== undefined && desc.bytes > maxBytes)) refuse('profile', `${label}: bytes out of bound`);
  if (typeof desc.sha256 !== 'string' || !HEX64.test(desc.sha256)) refuse('profile', `${label}: sha256`);
  if (!Array.isArray(desc.identity) || desc.identity.length !== 8 || !desc.identity.every((v) => typeof v === 'string' && DECIMAL.test(v))) refuse('profile', `${label}: identity must be eight decimal strings`);
  if (desc.identity[2] !== String(desc.bytes)) refuse('profile', `${label}: identity st_size differs from bytes`);
  if ((BigInt(desc.identity[5]) & S_IFMT) !== S_IFREG) refuse('profile', `${label}: identity st_mode is not a regular file`);
  if (desc.identity[6] !== '1') refuse('profile', `${label}: identity must be single-link`);
}

// Opens one exact regular single-link file with O_NOFOLLOW, reads it to EOF into
// a standalone ArrayBuffer and checks size/hash plus stable FD/path/parent
// identities. When `desc` is null the identity is recorded, not compared.
export function readPinnedFile(filePath, { desc = null, pin = null, maxBytes, label }) {
  if (typeof filePath !== 'string' || !path.isAbsolute(filePath)) refuse('input', `${label}: absolute path required`);
  const parent = path.dirname(filePath);
  const parentBefore = fs.lstatSync(parent, { bigint: true });
  if ((parentBefore.mode & S_IFMT) !== S_IFDIR) refuse('input', `${label}: parent is not a directory`);
  if (fs.realpathSync(filePath) !== filePath) refuse('input', `${label}: path is not canonical (symlinked component)`);
  const pathBefore = fs.lstatSync(filePath, { bigint: true });
  if (!pathBefore.isFile()) refuse('input', `${label}: not a regular file`);
  const fd = fs.openSync(filePath, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW);
  let keep = false;
  try {
    const fdBefore = fs.fstatSync(fd, { bigint: true });
    const identity = identityOf(fdBefore);
    if (!fdBefore.isFile() || fdBefore.nlink !== 1n) refuse('input', `${label}: not a regular single-link file`);
    if (!sameIdentity(identity, identityOf(pathBefore))) refuse('input', `${label}: path and descriptor identities differ`);
    if (desc && !sameIdentity(identity, desc.identity)) refuse('input', `${label}: identity differs from pinned decimal identity`);
    if (fdBefore.size > BigInt(maxBytes)) refuse('input', `${label}: ${fdBefore.size} bytes exceeds ${maxBytes}`);
    const size = Number(fdBefore.size);
    const buffer = new ArrayBuffer(size);
    const view = new Uint8Array(buffer);
    let offset = 0;
    while (offset < size) {
      const n = fs.readSync(fd, view, offset, size - offset, offset);
      if (n === 0) refuse('input', `${label}: short read at ${offset}/${size}`);
      offset += n;
    }
    if (fs.readSync(fd, new Uint8Array(1), 0, 1, size) !== 0) refuse('input', `${label}: bytes beyond recorded size`);
    const digest = sha256(view);
    const expected = desc ?? pin;
    if (expected && (size !== expected.bytes || digest !== expected.sha256)) refuse('input', `${label}: bytes/sha256 differ from pin`);
    if (!sameIdentity(identityOf(fs.fstatSync(fd, { bigint: true })), identity)) refuse('input', `${label}: descriptor identity changed during read`);
    if (!sameIdentity(identityOf(fs.lstatSync(filePath, { bigint: true })), identity)) refuse('input', `${label}: path identity changed during read`);
    const parentAfter = fs.lstatSync(parent, { bigint: true });
    if (dirIdentity(parentAfter).join() !== dirIdentity(parentBefore).join()) refuse('input', `${label}: parent identity changed during read`);
    keep = true;
    return { label, path: filePath, fd, buffer, bytes: size, sha256: digest, identity, parent_identity: dirIdentity(parentBefore) };
  } finally {
    if (!keep) fs.closeSync(fd);
  }
}

// Post-check: held descriptor, path and parent unchanged; a fresh nofollow full
// reread and the staged in-memory buffer both still match.
export function postcheckPinnedFile(held) {
  const out = { label: held.label, path: held.path, bytes: held.bytes, sha256: held.sha256, failures: [] };
  try {
    if (!sameIdentity(identityOf(fs.fstatSync(held.fd, { bigint: true })), held.identity)) out.failures.push('held descriptor identity changed');
    const again = readPinnedFile(held.path, { desc: { bytes: held.bytes, sha256: held.sha256, identity: held.identity }, maxBytes: held.bytes, label: held.label });
    fs.closeSync(again.fd);
    if (again.parent_identity.join() !== held.parent_identity.join()) out.failures.push('parent identity changed');
  } catch (e) { out.failures.push(`reread: ${e.message}`); }
  if (held.buffer.byteLength !== held.bytes || sha256(new Uint8Array(held.buffer)) !== held.sha256) out.failures.push('staged buffer changed');
  out.ok = out.failures.length === 0;
  return out;
}

function closeHeld(held) {
  for (const h of held) { try { fs.closeSync(h.fd); } catch { /* already closed */ } }
}

// ---------------------------------------------------------------- profile

const latin1FromHex = (hex) => {
  if (typeof hex !== 'string' || hex.length % 2 || !/^[0-9a-f]*$/.test(hex)) refuse('profile', 'raw hex string required');
  return Buffer.from(hex, 'hex').toString('latin1');
};

// Validates the frozen runtime profile and returns the normalized map/body
// bindings. Paths stay distinct even when hashes coincide.
export function validateProfile(profile, { limits = LIMITS, prefixPin = PREFIX_PIN, suffixPin = SUFFIX_PIN } = {}) {
  if (!profile || typeof profile !== 'object') refuse('profile', 'profile object required');
  if (profile.schema !== PROFILE_SCHEMA) refuse('profile', 'profile schema');
  if (profile.execution_admitted !== false) refuse('profile', 'frozen profile must keep execution_admitted:false; admission is separate');
  if (JSON.stringify(profile.identity_fields) !== JSON.stringify(IDENTITY_FIELDS)) refuse('profile', 'identity field order');
  if (profile.identity_encoding !== IDENTITY_ENCODING) refuse('profile', 'identity encoding');
  for (const [k, v] of Object.entries(LIMITS)) if (profile.limits?.[k] !== v) refuse('profile', `limit ${k} differs from frozen cap`);
  if (Object.keys(profile.limits).length !== Object.keys(LIMITS).length) refuse('profile', 'unexpected limit keys');
  for (const [name, pin] of [['compiled_prefix', prefixPin], ['pilot_suffix', suffixPin]]) {
    checkDescriptor(profile[name], name);
    if (profile[name].bytes !== pin.bytes || profile[name].sha256 !== pin.sha256) refuse('profile', `${name} differs from fixed pin`);
  }
  checkDescriptor(profile.node, 'node');
  const bodyList = (list, label, count) => {
    if (!Array.isArray(list) || list.length !== count) refuse('profile', `${label}: ${count} bodies required`);
    const paths = new Set();
    return list.map((b, i) => {
      if (b?.body_index !== i) refuse('profile', `${label}[${i}]: body_index`);
      if (!KIND_ORDER.includes(b.kind)) refuse('profile', `${label}[${i}]: kind`);
      if (typeof b.logical_path !== 'string' || !b.logical_path.startsWith('data/') || !b.logical_path.endsWith(`.${b.kind}`)) refuse('profile', `${label}[${i}]: logical_path`);
      checkDescriptor(b.source, `${label}[${i}].source`, limits.input_body_bytes);
      if (paths.has(b.source.path)) refuse('profile', `${label}[${i}]: duplicate body path`);
      paths.add(b.source.path);
      return { body_index: i, kind: b.kind, logical_path: b.logical_path, source: b.source };
    });
  };
  const bindMap = (m, bodies, label) => {
    if (typeof m?.map_name !== 'string' || !/^[0-9A-Za-z@_]+$/.test(m.map_name)) refuse('profile', `${label}: map_name`);
    const indices = m.body_indices;
    if (!indices || Object.keys(indices).sort().join(',') !== 'gat,gnd,rsw') refuse('profile', `${label}: body_indices keys`);
    const inputs = KIND_ORDER.map((kind) => {
      const body = bodies[indices[kind]];
      if (!Number.isInteger(indices[kind]) || !body || body.kind !== kind) refuse('profile', `${label}: ${kind} index binds a non-${kind} body`);
      return { kind, url: `/body/${kind}`, bytes: body.source.bytes, sha256: body.source.sha256, body_index: body.body_index, logical_path: body.logical_path, path: body.source.path };
    });
    if (inputs[0].logical_path !== `data/${m.map_name}.rsw`) refuse('profile', `${label}: RSW logical path is not data/${m.map_name}.rsw`);
    const hex = m.expected_world_files_raw_hex;
    if (!hex || Object.keys(hex).sort().join(',') !== 'gat,gnd,ini') refuse('profile', `${label}: expected_world_files_raw_hex keys`);
    const expected = { gat: latin1FromHex(hex.gat), gnd: latin1FromHex(hex.gnd), ini: latin1FromHex(hex.ini) };
    for (const kind of ['gat', 'gnd']) {
      const declared = inputs[KIND_ORDER.indexOf(kind)].logical_path.slice('data/'.length);
      if (expected[kind] !== declared) refuse('profile', `${label}: embedded ${kind} name ${JSON.stringify(expected[kind])} does not bind ${JSON.stringify(declared)}`);
    }
    const terrainStem = expected.gnd.replace(/\.gnd$/, '');
    if (expected.gat.replace(/\.gat$/, '') !== terrainStem) refuse('profile', `${label}: GAT/GND stems differ`);
    return {
      map_index: m.map_index, map_name: m.map_name, inputs, expected_world_files: expected,
      expected_world_files_raw_hex: { ...hex }, terrain_alias: terrainStem !== m.map_name ? terrainStem : null
    };
  };
  const bodies = bodyList(profile.bodies, 'bodies', BODY_COUNT);
  if (!Array.isArray(profile.maps) || profile.maps.length !== MAP_COUNT) refuse('profile', `${MAP_COUNT} maps required`);
  const names = new Set(), rswUse = new Set(), used = new Set();
  const maps = profile.maps.map((m, i) => {
    if (m?.map_index !== i) refuse('profile', `maps[${i}]: map_index`);
    if (names.has(m.map_name)) refuse('profile', `maps[${i}]: duplicate map_name`);
    names.add(m.map_name);
    const bound = bindMap(m, bodies, `maps[${i}]`);
    if (rswUse.has(bound.inputs[0].body_index)) refuse('profile', `maps[${i}]: RSW body reused`);
    rswUse.add(bound.inputs[0].body_index);
    for (const input of bound.inputs) used.add(input.body_index);
    return bound;
  });
  if (used.size !== bodies.length) refuse('profile', 'every staged body must bind to a map');
  const mainBytes = bodies.reduce((n, b) => n + b.source.bytes, 0);
  if (mainBytes !== limits.main_unique_body_bytes) refuse('profile', `main body bytes ${mainBytes} differ from ${limits.main_unique_body_bytes}`);
  const p = profile.pilot;
  if (!p || p.map_index !== -1) refuse('profile', 'pilot map_index -1 required');
  const pilotBodies = bodyList(p.bodies, 'pilot.bodies', 3);
  const pilot = bindMap(p, pilotBodies, 'pilot');
  const pilotBytes = pilotBodies.reduce((n, b) => n + b.source.bytes, 0);
  if (pilotBytes !== limits.pilot_unique_body_bytes) refuse('profile', `pilot body bytes ${pilotBytes} differ from ${limits.pilot_unique_body_bytes}`);
  return { bodies, maps, pilot, pilotBodies, aliases: maps.filter((m) => m.terrain_alias).map((m) => ({ map_name: m.map_name, terrain: m.terrain_alias })) };
}

// ---------------------------------------------------------------- suffix projection

const jsString = (s) => `'${Array.from(s, (c) => (/[0-9A-Za-z@_.\-]/.test(c) ? c : `\\x${c.charCodeAt(0).toString(16).padStart(2, '0')}`)).join('')}'`;
export const renderInputs = (inputs) => `const CH1_INPUTS = [\n${inputs.map((p) => `  {kind:'${p.kind}',url:'${p.url}',bytes:${p.bytes},sha256:'${p.sha256}'}`).join(',\n')}\n];\n`;
export const renderAssertion = (files) => `need(world.files.gat===${jsString(files.gat)}&&world.files.gnd===${jsString(files.gnd)},'embedded terrain names');`;
const occurrences = (text, needle) => { let n = 0; for (let i = text.indexOf(needle); i !== -1; i = text.indexOf(needle, i + 1)) n++; return n; };

// Locates both pilot-bound regions in the unchanged suffix (proving the
// template reproduces them exactly), checks the fixed limits it embeds, and
// returns the two old regions with their offsets.
export function suffixTemplate(suffixText, pilot, limits = LIMITS) {
  const oldInputs = renderInputs(pilot.inputs), oldAssertion = renderAssertion(pilot.expected_world_files);
  for (const [label, needle] of [['CH1_INPUTS', oldInputs], ['assertion', oldAssertion]]) {
    if (occurrences(suffixText, needle) !== 1) refuse('suffix', `pilot ${label} region must occur exactly once`);
  }
  if (occurrences(suffixText, 'const CH1_INPUTS') !== 1 || occurrences(suffixText, 'world.files.gat') !== 1 || occurrences(suffixText, 'world.files.gnd') !== 1) refuse('suffix', 'projected identifiers must occur exactly once');
  if (occurrences(suffixText, `performance.now() + ${limits.inner_diagnostic_deadline_ms}`) !== 1) refuse('suffix', 'inner diagnostic deadline differs');
  if (limits.map_result_bytes !== 8 * 1024 * 1024 || occurrences(suffixText, 'const CH1_LIMIT = 8 * 1024 * 1024;') !== 1) refuse('suffix', 'suffix result bound differs');
  const inputsOffset = suffixText.indexOf(oldInputs), assertionOffset = suffixText.indexOf(oldAssertion);
  if (!(inputsOffset + oldInputs.length <= assertionOffset)) refuse('suffix', 'region order');
  return { oldInputs, oldAssertion, inputsOffset, assertionOffset };
}

export function projectSuffix(suffixText, template, map) {
  const { oldInputs, oldAssertion, inputsOffset, assertionOffset } = template;
  const newInputs = renderInputs(map.inputs), newAssertion = renderAssertion(map.expected_world_files);
  const head = suffixText.slice(0, inputsOffset);
  const middle = suffixText.slice(inputsOffset + oldInputs.length, assertionOffset);
  const tail = suffixText.slice(assertionOffset + oldAssertion.length);
  const projected = head + newInputs + middle + newAssertion + tail;
  const newAssertionOffset = inputsOffset + newInputs.length + middle.length;
  // Complete inverse reconstruction from the projected text and recorded offsets.
  if (projected.slice(inputsOffset, inputsOffset + newInputs.length) !== newInputs || projected.slice(newAssertionOffset, newAssertionOffset + newAssertion.length) !== newAssertion) refuse('suffix', 'projection offsets');
  const inverse = projected.slice(0, inputsOffset) + oldInputs + projected.slice(inputsOffset + newInputs.length, newAssertionOffset) + oldAssertion + projected.slice(newAssertionOffset + newAssertion.length);
  if (inverse !== suffixText) refuse('suffix', 'inverse reconstruction differs');
  const bytes = Buffer.from(projected, 'utf8');
  return {
    text: projected, bytes: bytes.length, sha256: sha256(bytes),
    replacements: [
      { region: 'CH1_INPUTS', old_offset: inputsOffset, new_offset: inputsOffset, old: oldInputs, new: newInputs },
      { region: 'embedded-terrain-name-assertion', old_offset: assertionOffset, new_offset: newAssertionOffset, old: oldAssertion, new: newAssertion }
    ],
    preserved_bytes: Buffer.byteLength(head + middle + tail, 'utf8'),
    inverse: { bytes: Buffer.byteLength(inverse, 'utf8'), sha256: sha256(Buffer.from(inverse, 'utf8')), equals_original: true }
  };
}

// ---------------------------------------------------------------- admission

export function validateAdmission(admission, { hostDescriptor, profileSha256 }) {
  if (!admission || typeof admission !== 'object' || Array.isArray(admission)) refuse('admission', 'admission object required');
  const keys = Object.keys(admission).sort();
  if (keys.join(',') !== ADMISSION_KEYS.join(',')) refuse('admission', `admission keys must be exactly ${ADMISSION_KEYS.join(',')}`);
  if (admission.schema !== ADMISSION_SCHEMA) refuse('admission', 'admission schema');
  if (admission.root_bound !== true) refuse('admission', 'root_bound:true required');
  if (admission.execution_admitted !== true) refuse('admission', 'execution_admitted:true required');
  if (admission.mode !== 'pilot' && admission.mode !== 'remaining21') refuse('admission', 'mode must be pilot or remaining21');
  if (admission.profile_sha256 !== profileSha256) refuse('admission', 'profile_sha256 differs from the pinned profile');
  const out = admission.output_path;
  if (typeof out !== 'string' || !path.isAbsolute(out) || path.normalize(out) !== out || out.endsWith(path.sep)) refuse('admission', 'output_path must be an absolute normalized path');
  try { checkDescriptor(admission.host, 'host'); } catch (e) { refuse('admission', e.message); }
  const h = admission.host;
  if (h.path !== hostDescriptor.path || h.bytes !== hostDescriptor.bytes || h.sha256 !== hostDescriptor.sha256 || !sameIdentity(h.identity, hostDescriptor.identity)) {
    refuse('admission', 'host descriptor differs from the running source');
  }
  return { mode: admission.mode, output_path: out };
}

export function describeFile(filePath, label, maxBytes = 1 << 26) {
  const held = readPinnedFile(filePath, { maxBytes, label });
  fs.closeSync(held.fd);
  return { path: filePath, bytes: held.bytes, sha256: held.sha256, identity: held.identity };
}

// ---------------------------------------------------------------- output

function createOutputDir(out) {
  const parent = path.dirname(out);
  const st = fs.lstatSync(parent, { bigint: true });
  if (!st.isDirectory() || fs.realpathSync(parent) !== parent) refuse('output', 'output parent must be an existing canonical directory');
  fs.mkdirSync(out, { mode: 0o700 }); // EEXIST refuses a reused directory
  fs.chmodSync(out, 0o700);
  const own = fs.lstatSync(out, { bigint: true });
  if (!own.isDirectory() || (own.mode & 0o777n) !== 0o700n) refuse('output', 'output directory mode');
}

class Retained {
  constructor(dir, cap) { this.dir = dir; this.cap = cap; this.total = 0; this.files = []; }
  write(name, data, perFileCap) {
    const bytes = typeof data === 'string' ? Buffer.from(data, 'utf8') : data;
    if (perFileCap !== undefined && bytes.length > perFileCap) refuse('output', `${name}: ${bytes.length} bytes exceeds ${perFileCap}`);
    if (this.total + bytes.length > this.cap) refuse('output', `aggregate retained bytes would exceed ${this.cap}`);
    const target = path.join(this.dir, name);
    const fd = fs.openSync(target, fs.constants.O_WRONLY | fs.constants.O_CREAT | fs.constants.O_EXCL | fs.constants.O_NOFOLLOW, 0o600);
    try {
      fs.fchmodSync(fd, 0o600);
      let off = 0;
      while (off < bytes.length) off += fs.writeSync(fd, bytes, off, bytes.length - off);
      fs.fsyncSync(fd);
    } finally { fs.closeSync(fd); }
    const st = fs.lstatSync(target, { bigint: true });
    if (!st.isFile() || (st.mode & 0o777n) !== 0o600n || st.size !== BigInt(bytes.length)) refuse('output', `${name}: written file mode/size`);
    this.total += bytes.length;
    const entry = { name, bytes: bytes.length, sha256: sha256(bytes) };
    this.files.push(entry);
    return entry;
  }
}

class StreamBudget {
  constructor(limits) { this.caps = { stdout: limits.stdout_bytes, stderr: limits.stderr_bytes }; this.used = { stdout: 0, stderr: 0 }; this.overflow = { stdout: false, stderr: false }; }
  // Returns the admitted prefix of `chunk`; overflow is recorded, never hidden.
  admit(stream, chunk) {
    const room = this.caps[stream] - this.used[stream];
    if (chunk.length > room) this.overflow[stream] = true;
    const kept = chunk.subarray(0, Math.max(0, room));
    this.used[stream] += kept.length;
    return kept;
  }
}

// ---------------------------------------------------------------- per-map worker lifecycle

const describeMessage = (message) => {
  try { return { json: JSON.stringify(message) ?? null }; } catch (e) { return { inspect: inspect(message, { depth: 6, maxArrayLength: 64 }), json_error: String(e?.message ?? e) }; }
};

function runMapWorker(job, ctx) {
  const rec = {
    lifecycle: {
      spawned: false, online: false, thread_ready: 0, suffix_installed: false, core_sent: false,
      terminal_results: 0, close_sent: false, closing_summary: false, deadline_expired: false,
      terminate_requested: false, terminate_reason: null, exit_code: null, positive_exit: false,
      effective_deadline_ms: null, exit_elapsed_ms: null, elapsed_ms: null, streams_drained: false
    },
    bootstrap: null, closing: null, handler: [], script_messages: [], anomalies: [], worker_errors: [],
    streams: { stdout: '', stderr: '', stdout_overflow: false, stderr_overflow: false }, encoded: null
  };
  return new Promise((resolve) => {
    // Actual time is measured from launch through exit and stream drain against
    // the effective deadline fixed here; a delivered timer is not required.
    const started = performance.now();
    const deadline = Math.min(ctx.limits.worker_deadline_ms, Math.max(0, ctx.runDeadlineAt - started));
    rec.lifecycle.effective_deadline_ms = deadline;
    let worker;
    try {
      worker = new Worker(new URL(import.meta.url), {
        workerData: {
          schema: WORKER_SCHEMA, label: job.label, prefix: job.prefix, suffix: job.suffix,
          prefixPin: job.prefixPin, suffixPin: job.suffixPin,
          bodies: job.inputs.map((i) => ({ kind: i.kind, url: i.url, bytes: i.bytes, sha256: i.sha256, buffer: i.buffer.slice(0) }))
        },
        env: {}, argv: [], execArgv: [], stdout: true, stderr: true,
        resourceLimits: { maxOldGenerationSizeMb: ctx.limits.worker_heap_mb }
      });
    } catch (e) {
      rec.worker_errors.push(errorRecord(e, 'spawn'));
      resolve(rec);
      return;
    }
    rec.lifecycle.spawned = true;
    ctx.current = { terminate: (reason) => terminate(reason) };
    const terminate = (reason) => {
      if (rec.lifecycle.terminate_requested) return;
      rec.lifecycle.terminate_requested = true;
      rec.lifecycle.terminate_reason = reason;
      worker.terminate().catch((e) => rec.worker_errors.push(errorRecord(e, 'terminate')));
    };
    const ended = { stdout: false, stderr: false };
    let exited = false, settled = false;
    // Resolves once: after exit plus both stream ends, or when the deadline
    // passes after exit with a stream still open (recorded as undrained).
    const settle = () => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      rec.lifecycle.streams_drained = ended.stdout && ended.stderr;
      rec.lifecycle.elapsed_ms = performance.now() - started;
      resolve(rec);
    };
    const timer = setTimeout(() => {
      rec.lifecycle.deadline_expired = true;
      if (exited) settle(); else terminate('worker deadline');
    }, deadline);
    for (const stream of ['stdout', 'stderr']) {
      worker[stream].on('data', (chunk) => {
        const kept = ctx.streams.admit(stream, chunk);
        rec.streams[stream] += kept.toString('utf8');
        if (kept.length < chunk.length) { rec.streams[`${stream}_overflow`] = true; rec.anomalies.push(`worker ${stream} exceeded the ${stream} cap`); }
      });
      worker[stream].on('end', () => { ended[stream] = true; if (exited && ended.stdout && ended.stderr) settle(); });
    }
    worker.on('online', () => { rec.lifecycle.online = true; });
    worker.on('error', (e) => rec.worker_errors.push(errorRecord(e, 'worker-error')));
    worker.on('messageerror', (e) => rec.worker_errors.push(errorRecord(e, 'messageerror')));
    worker.on('message', (m) => {
      if (m?.channel === 'script') {
        const message = m.message, type = typeof message?.type === 'string' ? message.type : null;
        if (type === 'ROOT_CH1_RESULT') {
          rec.lifecycle.terminal_results++;
          const encoded = message.encoded;
          const entry = { seq: m.seq, type, encoded_type: typeof encoded };
          if (typeof encoded === 'string') Object.assign(entry, { encoded_bytes: Buffer.byteLength(encoded, 'utf8'), encoded_sha256: sha256(Buffer.from(encoded, 'utf8')) });
          rec.script_messages.push(entry);
          if (!rec.lifecycle.core_sent) rec.anomalies.push('terminal result before ROOT_CH1_CORE was sent');
          if (rec.lifecycle.terminal_results > 1) { rec.anomalies.push('duplicate terminal ROOT_CH1_RESULT'); return; }
          if (typeof encoded !== 'string') rec.anomalies.push('terminal result has no encoded string');
          else rec.encoded = encoded;
          rec.lifecycle.close_sent = true;
          worker.postMessage({ host: 'CLOSE' });
        } else {
          if (type === 'THREAD_READY') {
            rec.lifecycle.thread_ready++;
            if (rec.lifecycle.suffix_installed) rec.anomalies.push('THREAD_READY after suffix installation');
          }
          rec.script_messages.push({ seq: m.seq, type, ...describeMessage(message), ...(m.clone_error ? { clone_error: m.clone_error } : {}) });
        }
      } else if (m?.channel === 'host') {
        if (m.type === 'SUFFIX_INSTALLED') {
          rec.bootstrap = m;
          // The prefix's immediate THREAD_READY is not readiness: require the
          // distinct post-evaluation handshake naming a new current handler.
          if (rec.lifecycle.suffix_installed || rec.lifecycle.core_sent) { rec.anomalies.push('duplicate SUFFIX_INSTALLED'); return; }
          if (rec.lifecycle.thread_ready !== 1 || m.evidence?.thread_ready !== 1) { rec.anomalies.push('exactly one prefix THREAD_READY must precede suffix installation'); terminate('bootstrap evidence'); return; }
          rec.lifecycle.suffix_installed = true;
          rec.lifecycle.core_sent = true;
          worker.postMessage({ host: 'CORE' });
        } else if (m.type === 'BOOTSTRAP_FAILED') {
          rec.bootstrap = m;
          rec.anomalies.push(`bootstrap failed: ${m.reason}`);
        } else if (m.type === 'HANDLER') {
          rec.handler.push(m);
        } else if (m.type === 'CLOSING') {
          if (rec.lifecycle.closing_summary) rec.anomalies.push('duplicate CLOSING');
          rec.lifecycle.closing_summary = true;
          rec.closing = m;
        } else rec.anomalies.push(`unknown host message ${JSON.stringify(m.type)}`);
      } else rec.anomalies.push('message outside the bridge channels');
    });
    worker.on('exit', (code) => {
      exited = true;
      ctx.current = null;
      rec.lifecycle.exit_code = code;
      rec.lifecycle.exit_elapsed_ms = performance.now() - started;
      rec.lifecycle.positive_exit = code === 0 && !rec.lifecycle.terminate_requested && rec.lifecycle.closing_summary && rec.worker_errors.length === 0;
      // The deadline timer keeps running until both streams have drained.
      if (ended.stdout && ended.stderr) settle();
      else if (rec.lifecycle.deadline_expired) setImmediate(settle);
    });
  });
}

// Classifies one map. Host-lifecycle failures stop the batch; a genuine
// diagnostic exception is preserved and the batch continues.
export function classifyMap(rec, job) {
  const reasons = [...rec.anomalies];
  const lc = rec.lifecycle;
  if (!lc.spawned) reasons.push('worker not spawned');
  if (rec.worker_errors.length) reasons.push(`${rec.worker_errors.length} worker error(s)`);
  if (lc.deadline_expired) reasons.push('worker deadline expired; owned worker terminated');
  if (lc.terminate_requested && !lc.deadline_expired) reasons.push(`owned worker terminated: ${lc.terminate_reason}`);
  if (!lc.suffix_installed) reasons.push('suffix installation handshake not observed');
  if (lc.terminal_results !== 1) reasons.push(`expected exactly one terminal result, saw ${lc.terminal_results}`);
  if (!lc.closing_summary) reasons.push('closing summary not observed');
  if (lc.exit_code !== 0) reasons.push(`worker exit code ${lc.exit_code}`);
  if (!lc.positive_exit) reasons.push('no positive worker exit');
  // Timely completion needs recorded actual time through exit and drain.
  const elapsed = lc.elapsed_ms, limit = lc.effective_deadline_ms;
  if (!Number.isFinite(elapsed) || !Number.isFinite(limit) || elapsed < 0 || limit < 0) reasons.push('actual worker elapsed time or effective deadline not recorded');
  else if (elapsed > limit) reasons.push(`worker actual elapsed ${elapsed}ms exceeds effective deadline ${limit}ms`);
  if (lc.streams_drained !== true) reasons.push('worker stdout/stderr not drained');
  const closing = rec.closing;
  if (closing) {
    if (closing.post_terminal_script_messages) reasons.push(`${closing.post_terminal_script_messages} script message(s) after the terminal result`);
    if (closing.fetch.unknown.length) reasons.push('fetch outside /body/{rsw,gat,gnd}');
    if (closing.fetch.repeated.length) reasons.push('repeated fetch of one body');
    if (closing.fetch.bad_options.length) reasons.push('fetch options differ from the suffix contract');
    for (const b of closing.buffers) if (!b.ok) reasons.push(`constructor buffer ${b.url} changed`);
    if (closing.handler_rejections.length) reasons.push('suffix handler rejected');
  }
  let core = null, coreError = null;
  if (rec.encoded !== null) {
    try { core = JSON.parse(rec.encoded); } catch (e) { coreError = `encoded result is not JSON: ${e.message}`; reasons.push(coreError); }
  }
  if (core) {
    if (core.schema !== CORE_SCHEMA) reasons.push('core result schema');
    if (Array.isArray(core.inputs)) {
      core.inputs.forEach((input, i) => {
        const want = job.inputs[i];
        if (!want || input.kind !== want.kind || input.url !== want.url || input.bytes !== want.bytes || input.sha256 !== want.sha256) reasons.push(`core input ${i} differs from the bound input`);
      });
    }
  }
  const hostFailure = reasons.length > 0;
  const genuine = core && !hostFailure ? {
    error: core.error ?? null, postcheck_error: core.postcheckError ?? null,
    observation_complete: core.observationComplete === true,
    input_postchecks_complete: Array.isArray(core.inputPostchecks) && Array.isArray(core.inputs) && core.inputPostchecks.length === core.inputs.length &&
      core.inputPostchecks.every((p, i) => p.bytes === core.inputs[i].bytes && p.sha256 === core.inputs[i].sha256)
  } : null;
  let status, failureClass = null;
  if (hostFailure) { status = 'failed'; failureClass = 'host'; } else if (genuine.error === null && genuine.postcheck_error === null && genuine.observation_complete && genuine.input_postchecks_complete && core.inputs.length === 3) {
    status = 'observed';
  } else { status = 'failed'; failureClass = 'genuine'; }
  return {
    status, failure_class: failureClass, host_failure_reasons: reasons,
    core_summary: core ? {
      schema: core.schema ?? null, stages: core.stages ?? null, error: core.error ?? null, postcheck_error: core.postcheckError ?? null,
      observation_complete: core.observationComplete ?? null, numeric_anomalies: core.numericAnomalies ?? null,
      dependency_counts: core.dependencyCounts ?? null, water_from_ground: core.waterFromGround ?? null,
      qualification_policy_flag: core.qualification ?? null
    } : null
  };
}

// ---------------------------------------------------------------- run

export function hostDescriptor() {
  return describeFile(fileURLToPath(import.meta.url), 'host');
}

// `testing` exists for synthetic controls only; the CLI never passes it.
export async function runHost(args, testing = null) {
  const pins = { profile: testing?.profilePin ?? PROFILE_PIN, prefix: testing?.prefixPin ?? PREFIX_PIN, suffix: testing?.suffixPin ?? SUFFIX_PIN };
  const limits = { ...LIMITS, ...(testing?.limits ?? {}) };
  const log = testing?.log ?? (() => {});
  const runStarted = performance.now();
  // 1. Pinned profile and separate Root admission before any target read.
  const profileHeld = readPinnedFile(path.resolve(args.profile), { pin: pins.profile, maxBytes: pins.profile.bytes, label: 'profile' });
  const held = [profileHeld];
  try {
    const profile = JSON.parse(Buffer.from(profileHeld.buffer).toString('utf8'));
    const host = hostDescriptor();
    const admissionHeld = readPinnedFile(path.resolve(args.admission), { maxBytes: ADMISSION_MAX_BYTES, label: 'admission' });
    held.push(admissionHeld);
    let admissionJson;
    try { admissionJson = JSON.parse(Buffer.from(admissionHeld.buffer).toString('utf8')); } catch (e) { refuse('admission', `admission is not JSON: ${e.message}`); }
    const admission = validateAdmission(admissionJson, { hostDescriptor: host, profileSha256: pins.profile.sha256 });
    const bound = validateProfile(profile, { limits, prefixPin: pins.prefix, suffixPin: pins.suffix });
    // The exact Node binary named by the runtime profile (full hash, not retained).
    if (process.execPath !== profile.node.path) refuse('runtime', 'running Node binary differs from the runtime profile');
    const nodeHeld = readPinnedFile(process.execPath, { desc: profile.node, maxBytes: profile.node.bytes, label: 'node' });
    fs.closeSync(nodeHeld.fd);
    host.node = { path: nodeHeld.path, bytes: nodeHeld.bytes, sha256: nodeHeld.sha256, identity: nodeHeld.identity, version: process.version };
    // 2. Fresh exclusive private output directory.
    createOutputDir(admission.output_path);
    const retained = new Retained(admission.output_path, limits.total_retained_result_bytes);
    return await execute({ profile, bound, admission, host, retained, held, limits, pins, log, runStarted, admissionHeld, profileHeld });
  } finally {
    closeHeld(held);
  }
}

async function execute({ profile, bound, admission, host, retained, held, limits, pins, log, runStarted, admissionHeld, profileHeld }) {
  const mode = admission.mode;
  const selected = mode === 'pilot' ? [{ ...bound.pilot, label: 'pilot' }] : bound.maps.map((m) => ({ ...m, label: `map-${String(m.map_index).padStart(2, '0')}` }));
  const manifest = {
    schema: MANIFEST_SCHEMA, task: 'T07.007.014.009', mode, status: 'incomplete',
    claims: { qualification: false, note: 'host observation only; Root qualifies. Not file-format validity, production LOAD_MAP, rendering, travel, story or save.' },
    diagnostic_order_limit: DIAGNOSTIC_ORDER_LIMIT,
    host: { path: host.path, bytes: host.bytes, sha256: host.sha256, identity: host.identity }, node: host.node,
    profile: { path: profileHeld.path, bytes: profileHeld.bytes, sha256: profileHeld.sha256, identity: profileHeld.identity },
    admission: { path: admissionHeld.path, bytes: admissionHeld.bytes, sha256: admissionHeld.sha256, identity: admissionHeld.identity },
    limits, terrain_aliases: mode === 'pilot' ? [] : bound.aliases,
    source_prechecks: [], source_postchecks: [], maps: selected.map((m) => ({ label: m.label, map_index: m.map_index, map_name: m.map_name, status: 'not_started' })),
    files: retained.files, errors: [], stopped_reason: null
  };
  const ctx = { limits, runDeadlineAt: runStarted + limits.all_run_deadline_ms, current: null, streams: new StreamBudget(limits) };
  const runTimer = setTimeout(() => { ctx.runExpired = true; ctx.current?.terminate('entire host deadline'); }, Math.max(0, ctx.runDeadlineAt - performance.now()));
  const staged = [];
  try {
    // 3. Read and stage only the selected mode's bodies plus the fixed prefix/suffix.
    const prefix = readPinnedFile(profile.compiled_prefix.path, { desc: profile.compiled_prefix, maxBytes: pins.prefix.bytes, label: 'compiled_prefix' });
    held.push(prefix); staged.push(prefix);
    const suffix = readPinnedFile(profile.pilot_suffix.path, { desc: profile.pilot_suffix, maxBytes: pins.suffix.bytes, label: 'pilot_suffix' });
    held.push(suffix); staged.push(suffix);
    const suffixText = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(new Uint8Array(suffix.buffer));
    const template = suffixTemplate(suffixText, bound.pilot, limits);
    const bodyList = mode === 'pilot' ? bound.pilotBodies : bound.bodies;
    const bodies = new Map();
    for (const b of bodyList) {
      const h = readPinnedFile(b.source.path, { desc: b.source, maxBytes: limits.input_body_bytes, label: `${mode === 'pilot' ? 'pilot.' : ''}body[${b.body_index}]` });
      held.push(h); staged.push(h); bodies.set(b.body_index, h);
    }
    for (const h of staged) manifest.source_prechecks.push({ label: h.label, path: h.path, bytes: h.bytes, sha256: h.sha256, identity: h.identity, parent_identity: h.parent_identity });

    // 4. One fresh sequential worker per selected map.
    let stop = null;
    for (let i = 0; i < selected.length; i++) {
      const map = selected[i];
      const entry = manifest.maps[i];
      if (stop) { entry.status = 'not_started'; entry.reason = stop; continue; }
      if (ctx.runExpired || performance.now() >= ctx.runDeadlineAt) { stop = 'entire host deadline'; entry.status = 'not_started'; entry.reason = stop; continue; }
      const hostNow = describeFile(host.path, 'host');
      if (hostNow.sha256 !== host.sha256 || !sameIdentity(hostNow.identity, host.identity)) { stop = 'host source changed'; entry.status = 'not_started'; entry.reason = stop; continue; }
      const projection = mode === 'pilot' ? null : projectSuffix(suffixText, template, map);
      const suffixBytes = projection ? Buffer.from(projection.text, 'utf8') : new Uint8Array(suffix.buffer);
      const job = {
        label: map.label, prefix: prefix.buffer.slice(0), suffix: new Uint8Array(suffixBytes).buffer.slice(0),
        prefixPin: { bytes: prefix.bytes, sha256: prefix.sha256 },
        suffixPin: projection ? { bytes: projection.bytes, sha256: projection.sha256 } : { bytes: suffix.bytes, sha256: suffix.sha256 },
        inputs: map.inputs.map((input) => ({ ...input, buffer: bodies.get(input.body_index).buffer }))
      };
      entry.status = 'started';
      log(`${map.label} ${map.map_name}: started`);
      const rec = await runMapWorker(job, ctx);
      const verdict = classifyMap(rec, job);
      const report = {
        schema: MAP_REPORT_SCHEMA, label: map.label, map_index: map.map_index, map_name: map.map_name,
        status: verdict.status, failure_class: verdict.failure_class, host_failure_reasons: verdict.host_failure_reasons,
        diagnostic_order_limit: DIAGNOSTIC_ORDER_LIMIT,
        bindings: map.inputs.map(({ kind, url, bytes, sha256: s, body_index: bi, logical_path: lp, path: p }) => ({ kind, url, bytes, sha256: s, body_index: bi, logical_path: lp, path: p })),
        expected_world_files_raw_hex: map.expected_world_files_raw_hex, terrain_alias: map.terrain_alias ?? null,
        suffix: projection
          ? { unchanged: false, bytes: projection.bytes, sha256: projection.sha256, replacements: projection.replacements, preserved_bytes: projection.preserved_bytes, inverse: projection.inverse, original: { bytes: suffix.bytes, sha256: suffix.sha256 } }
          : { unchanged: true, bytes: suffix.bytes, sha256: suffix.sha256 },
        prefix: { unchanged: true, bytes: prefix.bytes, sha256: prefix.sha256 },
        lifecycle: rec.lifecycle, bootstrap: rec.bootstrap, handler: rec.handler, closing: rec.closing,
        script_messages: rec.script_messages, worker_errors: rec.worker_errors, streams: rec.streams,
        core_summary: verdict.core_summary, core_file: null
      };
      // Retain the exact encoded diagnostic string, then the projection, then the report.
      try {
        if (rec.encoded !== null) report.core_file = retained.write(`${map.label}.core.json`, rec.encoded, limits.map_result_bytes);
        if (projection) report.suffix.file = retained.write(`${map.label}.suffix.js`, projection.text, limits.map_result_bytes);
        const reportEntry = retained.write(`${map.label}.host.json`, `${JSON.stringify(report, null, 1)}\n`, limits.map_result_bytes);
        Object.assign(entry, { status: report.status, failure_class: report.failure_class, report: reportEntry.name, core: report.core_file?.name ?? null, reasons: verdict.host_failure_reasons });
      } catch (e) {
        Object.assign(entry, { status: 'failed', failure_class: 'host', reasons: [...verdict.host_failure_reasons, `retention: ${e.message}`] });
        manifest.errors.push(errorRecord(e, `${map.label}-retention`));
      }
      log(`${map.label} ${map.map_name}: ${entry.status}${entry.failure_class ? ` (${entry.failure_class})` : ''}`);
      if (entry.status === 'failed' && entry.failure_class === 'host') stop = `fail-fast after ${map.label} host failure`;
    }
    manifest.stopped_reason = stop;
  } catch (e) {
    manifest.errors.push(errorRecord(e, 'execute'));
    for (const m of manifest.maps) if (m.status === 'not_started') m.reason ??= 'run stopped before start';
  } finally {
    clearTimeout(runTimer);
  }
  // 5. Post-checks of every staged source/body, profile, admission and host.
  for (const h of staged) manifest.source_postchecks.push(postcheckPinnedFile(h));
  for (const h of [profileHeld, admissionHeld]) manifest.source_postchecks.push(postcheckPinnedFile(h));
  try {
    const hostAfter = describeFile(host.path, 'host');
    manifest.source_postchecks.push({ label: 'host', path: host.path, ok: hostAfter.sha256 === host.sha256 && sameIdentity(hostAfter.identity, host.identity), failures: [] });
  } catch (e) { manifest.source_postchecks.push({ label: 'host', path: host.path, ok: false, failures: [e.message] }); }
  // Actual whole-run time after the final synchronous postchecks; the run timer
  // only interrupts a running worker and is not evidence of timely completion.
  const runCheck = (phase) => {
    const elapsed = performance.now() - runStarted;
    const check = { phase, elapsed_ms: elapsed, limit_ms: limits.all_run_deadline_ms, ok: elapsed <= limits.all_run_deadline_ms };
    if (!check.ok) manifest.errors.push({ phase: 'run-deadline', name: 'Deadline', message: `entire host elapsed ${elapsed}ms exceeds ${limits.all_run_deadline_ms}ms ${phase}`, code: null, stack: null });
    return check;
  };
  manifest.run_deadline = { limit_ms: limits.all_run_deadline_ms, run_timer_expired: ctx.runExpired === true, after_postchecks: runCheck('after final postchecks') };
  const allObserved = manifest.maps.every((m) => m.status === 'observed');
  const postOk = manifest.source_postchecks.every((p) => p.ok) && manifest.source_prechecks.length === staged.length && staged.length > 0;
  manifest.streams = { used: ctx.streams.used, overflow: ctx.streams.overflow };
  manifest.counts = Object.fromEntries(['not_started', 'started', 'failed', 'observed'].map((s) => [s, manifest.maps.filter((m) => m.status === s).length]));
  manifest.status = allObserved && postOk && manifest.errors.length === 0 ? 'observed' : 'failed';
  manifest.elapsed_ms = performance.now() - runStarted;
  manifest.retained_bytes_before_manifest = retained.total;
  retained.write('MANIFEST.json', `${JSON.stringify(manifest, null, 1)}\n`);
  // Publication itself must also finish in time. The manifest is exclusive and
  // never rewritten, so a late publication adds one exclusive deadline record.
  let status = manifest.status;
  const published = runCheck('after manifest publication');
  if (!published.ok) {
    status = 'failed';
    try {
      retained.write('RUN_DEADLINE.json', `${JSON.stringify({ schema: MANIFEST_SCHEMA, record: 'run-deadline', status, manifest_status: manifest.status, check: published }, null, 1)}\n`);
    } catch (e) { manifest.errors.push(errorRecord(e, 'run-deadline-retention')); }
  }
  return { status, output_path: admission.output_path, counts: manifest.counts, stopped_reason: manifest.stopped_reason, errors: manifest.errors.map((e) => e.message) };
}

// ---------------------------------------------------------------- worker side

// Runs inside each fresh Worker. Host bindings stay in this module scope; the
// classic script sees only the explicit globals installed below.
async function workerMain(data) {
  // Bind the host's own runtime helpers before the classic script can redeclare globals.
  const HeadersCtor = Headers, defer = setImmediate, now = () => performance.now();
  const post = (m) => parentPort.postMessage({ channel: 'host', ...m });
  const fail = (reason, extra = {}) => { post({ type: 'BOOTSTRAP_FAILED', reason, ...extra }); parentPort.close(); };
  const check = (buffer, pin) => buffer.byteLength === pin.bytes && sha256(new Uint8Array(buffer)) === pin.sha256;
  if (!check(data.prefix, data.prefixPin) || !check(data.suffix, data.suffixPin)) return fail('prefix/suffix payload differs from its pin');
  for (const b of data.bodies) if (!check(b.buffer, b)) return fail(`body payload ${b.url} differs from its pin`);
  let source;
  try {
    const decoder = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true });
    source = decoder.decode(new Uint8Array(data.prefix)) + decoder.decode(new Uint8Array(data.suffix));
  } catch (e) { return fail('script is not UTF-8', { error: errorRecord(e, 'decode') }); }

  let seq = 0, threadReady = 0, terminal = 0, postTerminal = 0, handler = null, handlerAtThreadReady;
  const assignments = [];
  Object.defineProperty(globalThis, 'onmessage', {
    configurable: false, enumerable: true,
    get: () => handler,
    set: (value) => { assignments.push({ seq: seq++, type: typeof value, after_thread_ready: threadReady > 0 }); handler = value; }
  });
  const scriptPostMessage = function postMessage(message) {
    const s = seq++;
    if (terminal) postTerminal++;
    if (message?.type === 'THREAD_READY') { threadReady++; handlerAtThreadReady = handler; }
    if (message?.type === 'ROOT_CH1_RESULT') terminal++;
    try { parentPort.postMessage({ channel: 'script', seq: s, message }); } catch (e) {
      parentPort.postMessage({ channel: 'script', seq: s, message: { type: typeof message?.type === 'string' ? message.type : null }, clone_error: String(e?.message ?? e) });
    }
  };
  // Fixed in-memory fetch: only the three body URLs, each once, full bytes in a
  // standalone same-realm ArrayBuffer; every handed buffer is post-checked.
  const fetchLog = [], handed = [], seen = new Set(), unknown = [], repeated = [], badOptions = [];
  const byUrl = new Map(data.bodies.map((b) => [b.url, b]));
  const memoryFetch = async function fetch(url, options) {
    fetchLog.push({ url: String(url), options: describeMessage(options).json ?? null });
    const body = typeof url === 'string' ? byUrl.get(url) : undefined;
    if (!body) { unknown.push(String(url)); throw new TypeError('fetch failed: no fixed in-memory body'); }
    if (seen.has(url)) repeated.push(url);
    seen.add(url);
    if (options?.cache !== 'no-store' || options?.redirect !== 'error' || Object.keys(options).length !== 2) badOptions.push(url);
    const headers = new HeadersCtor({ 'content-length': String(body.bytes) });
    let used = false;
    return {
      status: 200, ok: true, url, redirected: false, headers,
      arrayBuffer: async () => {
        if (used) throw new TypeError('Body is unusable: Body has already been read');
        used = true;
        const out = body.buffer.slice(0);
        handed.push({ url, buffer: out, pin: body });
        return out;
      }
    };
  };
  const globals = {
    self: globalThis, postMessage: scriptPostMessage, fetch: memoryFetch,
    performance, crypto: webcrypto, TextEncoder, TextDecoder
  };
  for (const [name, value] of Object.entries(globals)) Object.defineProperty(globalThis, name, { value, writable: true, configurable: true, enumerable: name !== 'self' });
  const supplied = Object.keys(globals);

  const handlerSettled = [], handlerRejections = [];
  parentPort.on('message', (m) => {
    if (m?.host === 'CORE') {
      const current = handler;
      post({ type: 'HANDLER', event: 'dispatch', current_is_suffix: current !== handlerAtThreadReady, at: now() });
      Promise.resolve().then(() => current.call(globalThis, { data: { type: 'ROOT_CH1_CORE' } })).then(
        () => { handlerSettled.push('fulfilled'); post({ type: 'HANDLER', event: 'fulfilled', at: now() }); },
        (e) => { const r = errorRecord(e, 'handler'); handlerRejections.push(r); post({ type: 'HANDLER', event: 'rejected', error: r }); }
      );
    } else if (m?.host === 'CLOSE') {
      defer(() => {
        const buffers = handed.map(({ url, buffer, pin }) => {
          const bytes = buffer.byteLength, digest = sha256(new Uint8Array(buffer));
          return { url, bytes, sha256: digest, ok: bytes === pin.bytes && digest === pin.sha256 };
        });
        post({
          type: 'CLOSING', terminal_results: terminal, post_terminal_script_messages: postTerminal,
          handler_settled: handlerSettled, handler_rejections: handlerRejections,
          fetch: { calls: fetchLog, unknown, repeated, bad_options: badOptions }, buffers
        });
        parentPort.close();
      });
    }
  });

  const evaluationStarted = performance.now();
  try {
    vm.runInThisContext(source, { filename: `compiled-core-${data.label}.js` });
  } catch (e) {
    return fail('classic script evaluation threw', { error: errorRecord(e, 'evaluate'), assignments, thread_ready: threadReady });
  }
  const evidence = {
    supplied_globals: supplied, thread_ready: threadReady, onmessage_assignments: assignments,
    handler_is_function: typeof handler === 'function', handler_changed_after_thread_ready: handler !== handlerAtThreadReady,
    last_assignment_after_thread_ready: assignments.at(-1)?.after_thread_ready === true,
    script: { bytes: data.prefix.byteLength + data.suffix.byteLength, prefix_sha256: data.prefixPin.sha256, suffix_sha256: data.suffixPin.sha256 },
    evaluation_ms: performance.now() - evaluationStarted
  };
  if (!evidence.handler_is_function || !evidence.handler_changed_after_thread_ready || !evidence.last_assignment_after_thread_ready || threadReady !== 1) {
    return fail('suffix handler not installed after the prefix THREAD_READY', { evidence });
  }
  post({ type: 'SUFFIX_INSTALLED', evidence });
}

// ---------------------------------------------------------------- entry

async function cli() {
  const out = (s) => process.stdout.write(`${s}\n`.slice(0, LIMITS.stdout_bytes));
  const err = (s) => process.stderr.write(`${s}\n`.slice(0, LIMITS.stderr_bytes));
  let args;
  try {
    if (process.execArgv.length || process.env.NODE_OPTIONS) refuse('runtime', 'no Node execArgv/NODE_OPTIONS are admitted');
    args = parseArgs(process.argv.slice(2));
  } catch (e) {
    err(`refused: ${e.message}`);
    return 2;
  }
  try {
    const result = await runHost(args);
    out(JSON.stringify(result));
    return result.status === 'observed' ? 0 : 1;
  } catch (e) {
    err(`${e instanceof Refusal ? 'refused' : 'error'}: ${e.message}`);
    return e instanceof Refusal ? 2 : 1;
  }
}

if (!isMainThread && workerData?.schema === WORKER_SCHEMA) {
  workerMain(workerData).catch((e) => { parentPort.postMessage({ channel: 'host', type: 'BOOTSTRAP_FAILED', reason: 'worker bootstrap threw', error: errorRecord(e, 'bootstrap') }); parentPort.close(); });
} else if (isMainThread && process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  cli().then((code) => { process.exitCode = code; });
}
