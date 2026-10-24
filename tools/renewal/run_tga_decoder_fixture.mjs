#!/usr/bin/env node
// T07.007.014.020: bounded authored pure TGA decoder fixture.
//
//   perl -e 'alarm shift; exec @ARGV' 15 \
//     node --max-old-space-size=125 --max-semi-space-size=1 tools/renewal/run_tga_decoder_fixture.mjs \
//       --bundle <absolute saved Online.js> --mode authored-cases
//
// Reads the pinned bundle once as inert bytes and the Root-authored frozen case
// corpus (fixed checkout path), checks both whole pins, independently
// re-locates the three LF spans (checkHeader, decodeRLE, complete Targa class
// assignment) and compares offset/length/LF lines/SHA with the corpus pins.
// Every case is bounds-checked before any VM evaluation; F01-F03 are host
// refusals and evaluate zero source. Each admitted case gets a fresh
// node:vm realm with no host objects, dynamic code generation disabled, a
// separate `var Targa;` scaffold plus the byte-identical copied spans, and a
// literal-built Uint8Array; only Targa#load and Targa#getImageData are
// called and results are serialized inside the realm. The bundle and its
// initializer graph are never evaluated. node:vm bounds this known copied
// code only; it is not a sandbox for hostile code. No image body, canvas,
// Worker, browser, network, GL or native action exists here. Captures go
// only under the ignored private prefix; no args or other args refuse
// without reading, evaluating or writing anything.
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import v8 from 'node:v8';
import vm from 'node:vm';

export const TASK = 'T07.007.014.020';
export const RESULT_SCHEMA = 't07.007.014.020/result-v1';
const sha256 = (b) => createHash('sha256').update(b).digest('hex');
const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..');
export const CASES_PATH = path.join(ROOT, 'docs/project/fixtures/T07.007.014.020-cases.json');
export const PRIVATE_PREFIX = path.join(ROOT, '.tools/renewal/t07-014-020-root-authored-1');

export const PINS = Object.freeze({
  source: Object.freeze({ bytes: 13174290, sha256: '50b724b708393d7bb6d71b4f5102e62b16e340eb1bb54f05b1c8613af4116418' }),
  cases: Object.freeze({ bytes: 26646, sha256: '4bbabdb5ceae3dfb6192bf883348415fe6d3a7d6e4674d5a023fdb97964c1fd1' })
});
export const SCHEMA = 't07-014-020-authored-tga-cases-v1';
export const EVIDENCE_BOUNDARY = 'Authored pure decoder only; no real body, Worker/routing, canvas/GPU, gameplay or content claim.';
export const BOUNDS = Object.freeze({
  max_encoded_bytes: 4096, max_width: 8, max_height: 8, max_pixels: 64,
  max_rle_output_bytes: 256, max_rgba_bytes: 256, per_vm_timeout_ms: 100, overall_deadline_ms: 10000
});
// Span anchors: a unique line-start opening and the first closing line after it.
export const SPAN_ANCHORS = Object.freeze([
  Object.freeze({ id: 'checkHeader', open: 'function checkHeader(header) {\n', close: '\n}\n' }),
  Object.freeze({ id: 'decodeRLE', open: 'function decodeRLE(data, offset, pixelSize, outputSize) {\n', close: '\n}\n' }),
  Object.freeze({ id: 'Targa_assignment', open: '\tTarga = class Targa {\n', close: '\n\t};\n' })
]);
// Closed case list: exact ids, order and categories.
export const CASE_IDS = Object.freeze([
  ['P01_32bit_origin_TL', 'supported'], ['P01_32bit_origin_TR', 'supported'], ['P01_32bit_origin_BL', 'supported'],
  ['P01_32bit_origin_BR', 'supported'], ['P02_24bit_magenta_opaque', 'supported'], ['P03_16bit_rgb_alpha', 'supported'],
  ['P04_16bit_grey_alpha', 'supported'], ['P05_8bit_grey', 'supported'], ['P06_palette_two_entries', 'supported'],
  ['P07_rle_run', 'supported'], ['P08_rle_raw', 'supported'], ['P09_rle_mixed', 'supported'], ['P10_max8x8', 'supported'],
  ['E01_short17', 'decoder_reject'], ['E02_type0', 'decoder_reject'], ['E03_zero_width', 'decoder_reject'],
  ['E04_zero_height', 'decoder_reject'], ['E05_depth15', 'decoder_reject'], ['E06_indexed_palette_depth16', 'decoder_reject'],
  ['E07_rgb_with_colormap', 'decoder_reject'], ['E08_header_only', 'decoder_reject'], ['E09_rgb8_no_palette', 'decoder_reject'],
  ['C01_truncated_raw_preserves_prefix', 'current_permissive'], ['C02_raw_packet_overrun_prefix', 'current_permissive'],
  ['C03_run_packet_overrun_throws', 'current_permissive'], ['C04_unknown_type33', 'current_permissive'],
  ['C05_palette_origin_ignored', 'current_permissive'], ['C06_palette_index_outside_length', 'current_permissive'],
  ['C07_truncated_rle_preserves_prefix', 'current_permissive'],
  ['F01_huge_header_never_evaluated', 'host_refusal'], ['F02_width9_never_evaluated', 'host_refusal'],
  ['F03_height9_never_evaluated', 'host_refusal']
].map(([id, category]) => Object.freeze({ id, category })));
export const ZERO_DIMENSION_IDS = Object.freeze(['E03_zero_width', 'E04_zero_height']);
const STATUS_BY_CATEGORY = Object.freeze({
  supported: ['pixels'], decoder_reject: ['decoder_error'],
  current_permissive: ['pixels', 'decoder_error'], host_refusal: ['host_refused']
});
const ERROR_NAMES = Object.freeze(['Error', 'TypeError', 'RangeError']);
// Never-present globals asserted inside each realm.
export const ABSENT_GLOBALS = Object.freeze(['require', 'process', 'module', 'Buffer', 'fetch', 'XMLHttpRequest',
  'document', 'window', 'Image', 'Worker', 'setTimeout', 'setInterval', 'queueMicrotask', 'structuredClone']);

export class Refusal extends Error {
  constructor(code, detail) { super(`${code}: ${detail}`); this.name = 'Refusal'; this.code = code; }
}
const refuse = (code, detail) => { throw new Refusal(code, detail); };
const isInt = (v, lo, hi) => Number.isInteger(v) && v >= lo && v <= hi;
const exactKeys = (obj, keys, where) => {
  if (obj === null || typeof obj !== 'object' || Array.isArray(obj)) refuse('corpus_schema', `${where} is not an object`);
  const have = Object.keys(obj).sort().join(',');
  if (have !== [...keys].sort().join(',')) refuse('corpus_schema', `${where} keys ${have}`);
};

// ---- Pins ----
export function verifyPin(bytes, pin, what) {
  if (!(bytes instanceof Uint8Array)) refuse(`${what}_pin`, 'not bytes');
  if (bytes.length !== pin.bytes) refuse(`${what}_pin`, `size ${bytes.length} != ${pin.bytes}`);
  const digest = sha256(bytes);
  if (digest !== pin.sha256) refuse(`${what}_pin`, `sha256 ${digest} != ${pin.sha256}`);
  return { bytes: bytes.length, sha256: digest };
}

// Lossless C8 authority remains held through command publication.
const identity = (s) => [s.dev,s.ino,s.size,s.mtimeNs,s.ctimeNs,s.mode,s.nlink,s.uid].map(String);
const sameIdentity = (a,b) => JSON.stringify(a) === JSON.stringify(b);
function parentAuthority(file) {
  const rows=[];
  for(let dir=path.dirname(file);;dir=path.dirname(dir)) {
    const s=fs.lstatSync(dir,{bigint:true});
    if(!s.isDirectory() || s.isSymbolicLink()) refuse('input_identity','unsafe parent');
    rows.push({dir,id:[s.dev,s.ino,s.mode,s.uid].map(String)});
    if(dir===path.dirname(dir)) break;
  }
  return rows;
}
function checkParents(rows) {
  for(const row of rows) {
    const s=fs.lstatSync(row.dir,{bigint:true});
    if(!s.isDirectory() || !sameIdentity(row.id,[s.dev,s.ino,s.mode,s.uid].map(String)))
      refuse('input_identity','parent changed');
  }
}
export function openPinned(file,pin,what,guard=()=>{}) {
  guard();
  if(typeof file!=='string' || !path.isAbsolute(file)) refuse('usage',`${what} path must be absolute`);
  const parents=parentAuthority(file), st=fs.lstatSync(file,{bigint:true});
  if(!st.isFile() || st.isSymbolicLink() || st.nlink!==1n || st.size!==BigInt(pin.bytes)) refuse(`${what}_pin`,'unsafe type/link/size');
  const id=identity(st),fd=fs.openSync(file,fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW);
  try {
    if(!sameIdentity(id,identity(fs.fstatSync(fd,{bigint:true})))) refuse('input_identity','open changed input');
    guard();
    const bytes=Buffer.alloc(pin.bytes);let off=0;
    while(off<pin.bytes) {
      guard();const n=fs.readSync(fd,bytes,off,Math.min(65536,pin.bytes-off),off);
      if(!n) refuse(`${what}_pin`,'short read'); off+=n;
    }
    if(fs.readSync(fd,Buffer.alloc(1),0,1,off)!==0) refuse(`${what}_pin`,'extra bytes');
    const h={file,fd,bytes,pin,what,id,parents}; checkPinned(h,guard); return h;
  } catch(e) { fs.closeSync(fd);throw e; }
}
export function checkPinned(h,guard=()=>{}) {
  guard();checkParents(h.parents);
  if(!sameIdentity(h.id,identity(fs.fstatSync(h.fd,{bigint:true}))) ||
     !sameIdentity(h.id,identity(fs.lstatSync(h.file,{bigint:true})))) refuse('input_identity','input changed');
  verifyPin(h.bytes,h.pin,h.what);guard();
  return {identity_decimal:[...h.id],...h.pin};
}
export function readPinned(file,pin,what) {
  const h=openPinned(file,pin,what);
  try { return h.bytes; } finally {fs.closeSync(h.fd);}
}

// ---- Corpus schema/domain ----
export function validateCorpus(corpus) {
  exactKeys(corpus, ['schema', 'source_pin', 'source_spans', 'bounds', 'requires_little_endian', 'cases', 'evidence_boundary'], 'corpus');
  if (corpus.schema !== SCHEMA) refuse('corpus_schema', `schema ${corpus.schema}`);
  if (corpus.evidence_boundary !== EVIDENCE_BOUNDARY) refuse('corpus_schema', 'evidence_boundary');
  if (corpus.requires_little_endian !== true) refuse('corpus_schema', 'requires_little_endian');
  exactKeys(corpus.source_pin, ['bytes', 'sha256'], 'source_pin');
  if (corpus.source_pin.bytes !== PINS.source.bytes || corpus.source_pin.sha256 !== PINS.source.sha256) refuse('corpus_schema', 'source_pin');
  exactKeys(corpus.bounds, Object.keys(BOUNDS), 'bounds');
  for (const [k, v] of Object.entries(BOUNDS)) if (corpus.bounds[k] !== v) refuse('corpus_schema', `bounds.${k}`);
  if (!Array.isArray(corpus.source_spans) || corpus.source_spans.length !== SPAN_ANCHORS.length) refuse('corpus_schema', 'source_spans');
  corpus.source_spans.forEach((s, i) => {
    exactKeys(s, ['id', 'start_line', 'end_line', 'byte_offset', 'byte_length', 'sha256'], `source_spans[${i}]`);
    if (s.id !== SPAN_ANCHORS[i].id) refuse('corpus_schema', `span ${i} id ${s.id}`);
    for (const k of ['start_line', 'end_line', 'byte_offset', 'byte_length'])
      if (!isInt(s[k], 1, PINS.source.bytes)) refuse('corpus_schema', `span ${s.id}.${k}`);
    if (!/^[0-9a-f]{64}$/.test(s.sha256)) refuse('corpus_schema', `span ${s.id}.sha256`);
  });
  if (!Array.isArray(corpus.cases) || corpus.cases.length !== CASE_IDS.length) refuse('corpus_schema', 'case count');
  corpus.cases.forEach((c, i) => {
    const where = `cases[${i}]`;
    const zero = ZERO_DIMENSION_IDS.includes(CASE_IDS[i].id);
    exactKeys(c, zero ? ['id', 'category', 'bytes', 'expected', 'allow_zero_dimension'] : ['id', 'category', 'bytes', 'expected'], where);
    if (c.id !== CASE_IDS[i].id || c.category !== CASE_IDS[i].category) refuse('corpus_schema', `${where} id/category ${c.id}/${c.category}`);
    if (zero && c.allow_zero_dimension !== true) refuse('corpus_schema', `${where} allow_zero_dimension`);
    if (!Array.isArray(c.bytes) || c.bytes.length === 0) refuse('corpus_schema', `${where}.bytes`);
    const e = c.expected;
    if (e === null || typeof e !== 'object' || !STATUS_BY_CATEGORY[c.category].includes(e.status)) refuse('corpus_schema', `${where}.expected.status`);
    if (e.status === 'pixels') {
      exactKeys(e, ['status', 'width', 'height', 'rgba'], `${where}.expected`);
      if (!isInt(e.width, 1, BOUNDS.max_width) || !isInt(e.height, 1, BOUNDS.max_height)) refuse('corpus_schema', `${where} dims`);
      if (!Array.isArray(e.rgba) || e.rgba.length !== e.width * e.height * 4 || !e.rgba.every((v) => isInt(v, 0, 255)))
        refuse('corpus_schema', `${where}.expected.rgba`);
    } else if (e.status === 'decoder_error') {
      exactKeys(e, ['status', 'name', 'message_contains'], `${where}.expected`);
      if (!ERROR_NAMES.includes(e.name) || typeof e.message_contains !== 'string' || !e.message_contains) refuse('corpus_schema', `${where} error`);
    } else {
      exactKeys(e, ['status', 'code'], `${where}.expected`);
      if (e.code !== 'authored_input_bounds') refuse('corpus_schema', `${where}.expected.code`);
    }
  });
  return corpus;
}

// ---- Span reconstruction from the actual source ----
const lineOf = (buf, offset) => { let n = 1; for (let i = buf.indexOf(10); i !== -1 && i < offset; i = buf.indexOf(10, i + 1)) n++; return n; };
export function extractSpans(sourceBytes, pinnedSpans) {
  const src = Buffer.from(sourceBytes.buffer, sourceBytes.byteOffset, sourceBytes.length);
  return SPAN_ANCHORS.map((a, i) => {
    const open = Buffer.from(a.open, 'utf8');
    const start = src.indexOf(open);
    if (start === -1 || src.indexOf(open, start + 1) !== -1) refuse('span_pin', `${a.id} anchor not unique`);
    if (start > 0 && src[start - 1] !== 10) refuse('span_pin', `${a.id} not at line start`);
    const closeAt = src.indexOf(Buffer.from(a.close, 'utf8'), start + open.length - 1);
    if (closeAt === -1) refuse('span_pin', `${a.id} no close`);
    const end = closeAt + Buffer.byteLength(a.close);
    const bytes = src.subarray(start, end);
    const text = bytes.toString('utf8');
    if (!Buffer.from(text, 'utf8').equals(bytes)) refuse('span_pin', `${a.id} not byte-identical utf8`);
    const got = {
      id: a.id, start_line: lineOf(src, start), end_line: lineOf(src, end - 1),
      byte_offset: start, byte_length: bytes.length, sha256: sha256(bytes)
    };
    const pin = pinnedSpans[i];
    for (const k of Object.keys(got)) if (got[k] !== pin[k]) refuse('span_pin', `${a.id}.${k} ${got[k]} != ${pin[k]}`);
    return { ...got, text };
  });
}

// Separately pinned scaffold around the copied spans; declares Targa only.
export const SCAFFOLD_HEAD = 'var Targa;\n';
export function buildScaffold(spans) {
  return SCAFFOLD_HEAD + spans.map((s) => s.text).join('');
}

// ---- Admission before any VM evaluation ----
export function admitCase(c) {
  const b = c.bytes;
  if (!Array.isArray(b) || b.length > BOUNDS.max_encoded_bytes) return { admitted: false, reason: 'encoded_bytes' };
  if (!b.every((v) => isInt(v, 0, 255))) return { admitted: false, reason: 'byte_domain' };
  if (b.length < 18) return { admitted: true, header: null };
  const width = b[12] | (b[13] << 8);
  const height = b[14] | (b[15] << 8);
  const pixelSize = b[16] >> 3;
  const header = { width, height, pixelDepth: b[16] };
  if (width > BOUNDS.max_width || height > BOUNDS.max_height) return { admitted: false, reason: 'dimensions', header };
  if ((width === 0 || height === 0) && !(ZERO_DIMENSION_IDS.includes(c.id) && c.allow_zero_dimension === true))
    return { admitted: false, reason: 'zero_dimension', header };
  const pixels = width * height;
  if (pixels > BOUNDS.max_pixels) return { admitted: false, reason: 'pixels', header };
  if (pixels * pixelSize > BOUNDS.max_rle_output_bytes) return { admitted: false, reason: 'rle_output', header };
  if (pixels * 4 > BOUNDS.max_rgba_bytes) return { admitted: false, reason: 'rgba', header };
  return { admitted: true, header };
}

// ---- Realm execution ----
export function hostLittleEndian() { return os.endianness() === 'LE'; }

const PROBE = `JSON.stringify({ absent: ${JSON.stringify(ABSENT_GLOBALS)}.filter((n) => typeof globalThis[n] !== 'undefined'),
  littleEndian: new Uint8Array(new Uint32Array([0x01020304]).buffer)[0] === 4,
  evalBlocked: (() => { try { eval('1'); return false; } catch (e) { return e instanceof EvalError; } })(),
  functionBlocked: (() => { try { Function('return 1'); return false; } catch (e) { return e instanceof EvalError; } })() })`;
const SURFACE = `JSON.stringify(['load', 'getImageData', 'open', 'getCanvas', 'getDataURL'].filter((m) => typeof Targa.prototype[m] === 'function'))`;
// Bytes enter as validated integer literals; everything returned is a JSON string.
export function harnessCall(bytes) {
  return `(() => { const data = new Uint8Array([${bytes.join(',')}]); let stage = 'load';
  try { const tga = new Targa(); tga.load(data); stage = 'getImageData'; const img = tga.getImageData();
    return JSON.stringify({ status: 'pixels', width: img.width, height: img.height, rgba: Array.from(img.data) });
  } catch (e) { return JSON.stringify({ status: 'decoder_error', stage, name: String(e && e.name), message: String(e && e.message) }); } })()`;
}

// Process-wide count of VM evaluations, so refusals can prove none happened.
let totalEvaluations = 0;
export const vmEvaluationCount = () => totalEvaluations;
// Runs one evaluation; timeouts become fixture failures, never decoder results.
function evaluate(ctx, code, ms, counter) {
  counter.evaluations++;
  totalEvaluations++;
  try {
    const out = vm.runInContext(code, ctx, { timeout: ms, breakOnSigint: false });
    if (typeof out !== 'string' || out.length > 65536) return { fixtureFailure: 'non_string_result' };
    return { value: JSON.parse(out) };
  } catch (e) {
    if (e && e.code === 'ERR_SCRIPT_EXECUTION_TIMEOUT') return { fixtureFailure: 'vm_timeout' };
    return { fixtureFailure: 'uncaught', detail: String(e && e.message).slice(0, 200) };
  }
}

export function runCaseInRealm(scaffold, c, { perVmMs = BOUNDS.per_vm_timeout_ms, remainingMs = () => Infinity } = {}) {
  if(!heapLimitOk()) refuse('heap_limit','effective V8 heap exceeds128MiB');
  const admission=admitCase(c);
  if(!admission.admitted) return {status:'host_refused',code:'authored_input_bounds',reason:admission.reason,evaluations:0};
  if(!Number.isInteger(perVmMs) || perVmMs<1 || perVmMs>100 || typeof remainingMs!=='function')
    return {status:'fixture_failure',reason:'vm_timeout_bounds',evaluations:0};
  const counter = { evaluations: 0 };
  const ctx = vm.createContext(undefined, { codeGeneration: { strings: false, wasm: false }, microtaskMode: 'afterEvaluate' });
  const steps = [['probe', PROBE], ['scaffold', scaffold + ';"null"'], ['surface', SURFACE], ['call', harnessCall(c.bytes)]];
  const realm = {};
  for (const [name, code] of steps) {
    const ms = Math.min(perVmMs, Math.floor(remainingMs()));
    if (!(ms > 0)) return { status: 'fixture_failure', reason: 'overall_deadline', step: name, evaluations: counter.evaluations, realm };
    const r = evaluate(ctx, code, ms, counter);
    if (r.fixtureFailure) return { status: 'fixture_failure', reason: r.fixtureFailure, detail: r.detail, step: name, evaluations: counter.evaluations, realm };
    if (name === 'probe') {
      realm.probe = r.value;
      if (r.value.absent.length || !r.value.evalBlocked || !r.value.functionBlocked)
        return { status: 'fixture_failure', reason: 'realm_isolation', step: name, evaluations: counter.evaluations, realm };
      if (!r.value.littleEndian) return { status: 'fixture_failure', reason: 'not_little_endian', step: name, evaluations: counter.evaluations, realm };
    } else if (name === 'surface') {
      realm.methods = r.value;
    } else if (name === 'call') {
      return { ...r.value, evaluations: counter.evaluations, realm };
    }
  }
  return { status: 'fixture_failure', reason: 'unreachable', evaluations: counter.evaluations, realm };
}

// ---- Comparison with handwritten expectations ----
export function compareOutcome(expected, actual) {
  const diffs = [];
  if (actual.status !== expected.status) diffs.push(`status ${actual.status} != ${expected.status}`);
  else if (expected.status === 'pixels') {
    if (actual.width !== expected.width) diffs.push(`width ${actual.width} != ${expected.width}`);
    if (actual.height !== expected.height) diffs.push(`height ${actual.height} != ${expected.height}`);
    if (!Array.isArray(actual.rgba) || actual.rgba.length !== expected.rgba.length) diffs.push(`rgba length ${actual.rgba && actual.rgba.length} != ${expected.rgba.length}`);
    else expected.rgba.forEach((v, i) => { if (actual.rgba[i] !== v) diffs.push(`rgba[${i}] ${actual.rgba[i]} != ${v}`); });
  } else if (expected.status === 'decoder_error') {
    if (actual.name !== expected.name) diffs.push(`name ${actual.name} != ${expected.name}`);
    if (typeof actual.message !== 'string' || !actual.message.includes(expected.message_contains)) diffs.push(`message lacks ${JSON.stringify(expected.message_contains)}`);
  } else if (actual.code !== expected.code) diffs.push(`code ${actual.code} != ${expected.code}`);
  return { pass: diffs.length === 0, diffs };
}

// ---- Whole fixture ----
export function runFixture({ sourceBytes, casesBytes, littleEndian = hostLittleEndian(), now = () => performance.now(),
  pins = PINS, deadlineMs = BOUNDS.overall_deadline_ms, startedAt } = {}) {
  if(!heapLimitOk()) refuse('heap_limit','effective V8 heap exceeds128MiB');
  if(!Number.isFinite(deadlineMs) || deadlineMs<=0 || deadlineMs>10000) refuse('overall_deadline','invalid deadline');
  const t0 = startedAt ?? now();
  const pre = { source: verifyPin(sourceBytes, pins.source, 'source'), cases: verifyPin(casesBytes, pins.cases, 'cases') };
  let corpus;
  try { corpus = JSON.parse(Buffer.from(casesBytes).toString('utf8')); } catch { refuse('corpus_schema', 'not JSON'); }
  validateCorpus(corpus);
  if (!littleEndian) refuse('not_little_endian', 'host is not little-endian; refusing byte-level RGBA comparisons');
  const spans = extractSpans(sourceBytes, corpus.source_spans);
  const scaffold = buildScaffold(spans);
  // Every case is admitted or refused before the first VM evaluation.
  const admissions = corpus.cases.map(admitCase);
  let evaluations = 0;
  const remainingMs = () => deadlineMs - (now() - t0);
  const results = corpus.cases.map((c, i) => {
    const adm = admissions[i];
    const t = now();
    const actual = adm.admitted
      ? runCaseInRealm(scaffold, c, { remainingMs })
      : { status: 'host_refused', code: 'authored_input_bounds', reason: adm.reason, evaluations: 0 };
    evaluations += actual.evaluations;
    const cmp = compareOutcome(c.expected, actual);
    return { id: c.id, category: c.category, admitted: adm.admitted, header: adm.header, expected: c.expected, actual,
      pass: cmp.pass, diffs: cmp.diffs, ms: Math.round((now() - t) * 1000) / 1000 };
  });
  const post = { source: verifyPin(sourceBytes, pins.source, 'source'), cases: verifyPin(casesBytes, pins.cases, 'cases') };
  const elapsed = now() - t0;
  const passed = results.filter((r) => r.pass).length;
  return {
    schema: RESULT_SCHEMA, task: TASK, pre, post,
    spans: spans.map(({ text, ...s }) => s),
    scaffold: { head_sha256: sha256(SCAFFOLD_HEAD), bytes: Buffer.byteLength(scaffold), sha256: sha256(scaffold) },
    evaluations, elapsed_ms: Math.round(elapsed), within_deadline: elapsed <= deadlineMs,
    total: results.length, passed, failed: results.length - passed,
    ok: passed === CASE_IDS.length && elapsed <= deadlineMs,
    results, _spanTexts: spans.map((s) => ({ id: s.id, text: s.text }))
  };
}

// ---- CLI ----
export function parseArgs(argv) {
  if (argv.length !== 4) refuse('usage', 'expected exactly --bundle <absolute path> --mode authored-cases');
  const opts = {};
  for (let i = 0; i < argv.length; i += 2) {
    const [k, v] = [argv[i], argv[i + 1]];
    if (k === '--bundle' && opts.bundle === undefined) opts.bundle = v;
    else if (k === '--mode' && opts.mode === undefined) opts.mode = v;
    else refuse('usage', `unexpected argument ${k}`);
  }
  if (opts.mode !== 'authored-cases') refuse('usage', 'only --mode authored-cases is supported');
  if (typeof opts.bundle !== 'string' || !path.isAbsolute(opts.bundle)) refuse('usage', '--bundle must be an absolute path');
  return opts;
}

export function heapLimitOk() {
  const limit=v8.getHeapStatistics().heap_size_limit;
  return Number.isSafeInteger(limit) && limit>0 && limit<=128*1024*1024;
}

function privateRun() {
  // Existing ancestor identities are checked; create only this task's prefix.
  parentAuthority(PRIVATE_PREFIX);
  try {fs.mkdirSync(PRIVATE_PREFIX,{mode:0o700});} catch(e) {if(e.code!=='EEXIST')throw e;}
  const s=fs.lstatSync(PRIVATE_PREFIX);
  if(!s.isDirectory() || s.isSymbolicLink() || (s.mode&0o777)!==0o700) refuse('private_path','unsafe prefix');
  const dir=fs.mkdtempSync(path.join(PRIVATE_PREFIX,'run-'));fs.chmodSync(dir,0o700);return dir;
}
function exclusiveWrite(dir,name,data,guard) {
  const b=Buffer.from(data);if(b.length>1024*1024)refuse('output_bound','capture exceeds1MiB');
  guard();const file=path.join(dir,name),parents=parentAuthority(file);
  const fd=fs.openSync(file,fs.constants.O_RDWR|fs.constants.O_CREAT|fs.constants.O_EXCL|fs.constants.O_NOFOLLOW,0o600);
  let id;
  try {
    let off=0;while(off<b.length){guard();const n=fs.writeSync(fd,b,off,Math.min(65536,b.length-off),off);if(!n)refuse('output_write','short write');off+=n;}
    const st=fs.fstatSync(fd);if(!st.isFile()||st.nlink!==1||(st.mode&0o777)!==0o600||st.size!==b.length)refuse('output_write','capture identity');
    const got=Buffer.alloc(b.length);off=0;
    while(off<b.length){guard();const n=fs.readSync(fd,got,off,Math.min(65536,b.length-off),off);if(!n)refuse('output_write','short readback');off+=n;}
    if(!got.equals(b))refuse('output_write','capture mismatch');
    id=identity(fs.fstatSync(fd,{bigint:true}));guard();
  } finally {fs.closeSync(fd);}
  const output={file,parents,id,bytes:b.length,sha256:sha256(b)};
  checkOutput(output);guard();return output;
}
function checkOutput(output) {
  checkParents(output.parents);
  if(!sameIdentity(output.id,identity(fs.lstatSync(output.file,{bigint:true}))))refuse('output_identity','capture literal changed');
}

export function main(argv, { write = true, now = () => performance.now() } = {}) {
  const startedAt=now(), opts=parseArgs(argv);
  if(!heapLimitOk()) refuse('heap_limit','effective V8 heap exceeds128MiB');
  const deadline=()=>{if(now()-startedAt>BOUNDS.overall_deadline_ms)refuse('overall_deadline','command exceeds10000ms');};
  const handles=[],outputs=[];let dir,summary,error,terminalElapsed;
  const authority=()=>{deadline();for(const h of handles)checkPinned(h,deadline);deadline();};
  try {
    const source=openPinned(opts.bundle,PINS.source,'source',deadline);handles.push(source);
    const cases=openPinned(CASES_PATH,PINS.cases,'cases',deadline);handles.push(cases);
    const result=runFixture({sourceBytes:source.bytes,casesBytes:cases.bytes,now,startedAt});
    const {_spanTexts,...rest}=result;summary=rest;
    authority();
    summary.heap_size_limit_bytes=v8.getHeapStatistics().heap_size_limit;
    summary.node=process.version;
    summary.input_authority=handles.map(h=>({input:h.what,identity_decimal:[...h.id],...h.pin}));
    if(write) {
      dir=privateRun();authority();
      const manifest=[];
      for(const s of _spanTexts){const name=`${s.id}.span.js.txt`;outputs.push(exclusiveWrite(dir,name,s.text,authority));manifest.push({file:name,bytes:Buffer.byteLength(s.text),sha256:sha256(s.text)});}
      outputs.push(exclusiveWrite(dir,'MANIFEST.json',JSON.stringify({task:TASK,spans:summary.spans,files:manifest,scaffold:summary.scaffold},null,2)+'\n',authority));
      summary.capture_dir=path.relative(ROOT,dir);
      summary.capture_started_elapsed_ms=now()-startedAt;
      outputs.push(exclusiveWrite(dir,'RESULT.json',JSON.stringify(summary,null,2)+'\n',authority));
    }
    authority();
  } catch(e) {error=e;}
  finally {for(const h of handles){try{fs.closeSync(h.fd);}catch(e){error??=e;}}}
  try {
    for(const h of handles) {
      checkParents(h.parents);
      if(!sameIdentity(h.id,identity(fs.lstatSync(h.file,{bigint:true}))))refuse('input_identity','input changed during close');
    }
    for(const output of outputs)checkOutput(output);
    terminalElapsed=now()-startedAt;
    if(terminalElapsed>BOUNDS.overall_deadline_ms)refuse('overall_deadline','command exceeds10000ms');
  }catch(e){error??=e;}
  if(error) {
    if(dir) {
      // Keep the complete failed run, but remove its terminal PASS filename.
      try {fs.renameSync(path.join(dir,'RESULT.json'),path.join(dir,'RESULT.unqualified.json'));}catch(e){if(e.code!=='ENOENT')error=e;}
      try {exclusiveWrite(dir,'FAILURE.json',JSON.stringify({task:TASK,ok:false,reason:error.code||'error'})+'\n',()=>{});}catch{}
    }
    throw error;
  }
  summary.command_elapsed_ms=terminalElapsed;
  return summary;
}

if (process.argv[1] && fs.realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const summary = main(process.argv.slice(2));
    process.stdout.write(JSON.stringify({ ok: summary.ok, total: summary.total, passed: summary.passed, failed: summary.failed,
      evaluations: summary.evaluations, elapsed_ms: summary.elapsed_ms, pre: summary.pre, post: summary.post,
      command_elapsed_ms: summary.command_elapsed_ms, heap_size_limit_bytes: summary.heap_size_limit_bytes,
      capture_dir: summary.capture_dir, outcomes: summary.results.map((r) => `${r.id}:${r.pass ? 'PASS' : 'FAIL'}:${r.actual.status}:eval=${r.actual.evaluations}`) }, null, 2) + '\n');
    process.exitCode = summary.ok ? 0 : 1;
  } catch (e) {
    process.stdout.write(JSON.stringify({ ok: false, refused: e instanceof Refusal ? e.code : 'error', detail: String(e.message).slice(0, 300) }) + '\n');
    process.exitCode = 2;
  }
}
