// T07.007.014.020 controls for the bounded authored pure TGA decoder fixture.
// Uses only the frozen authored corpus, the pinned saved bundle (read as bytes)
// and safe authored mutations within the same caps. Decoding runs in-process.
// One high-heap Node refusal control exits before source IO/evaluation.
// No browser, Worker, network, canvas or GL. Requires the bundle path:
//
//   TGA_DECODER_BUNDLE=<abs saved Online.js> perl -e 'alarm shift; exec @ARGV' 120 \
//     node --max-old-space-size=125 --max-semi-space-size=1 tests/tga_decoder_fixture.test.mjs
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import v8 from 'node:v8';
import {spawnSync} from 'node:child_process';
import test from 'node:test';
import {
  BOUNDS, CASES_PATH, CASE_IDS, PINS, PRIVATE_PREFIX, Refusal, admitCase, buildScaffold, compareOutcome, extractSpans,
  harnessCall, main, parseArgs, readPinned, runCaseInRealm, runFixture, validateCorpus, vmEvaluationCount,
  heapLimitOk
} from '../tools/renewal/run_tga_decoder_fixture.mjs';

const sha = (b) => createHash('sha256').update(b).digest('hex');
const BUNDLE = process.env.TGA_DECODER_BUNDLE;
assert.ok(BUNDLE, 'TGA_DECODER_BUNDLE must name the pinned saved Online.js');
const SOURCE = readPinned(BUNDLE, PINS.source, 'source');
const CASES = readPinned(CASES_PATH, PINS.cases, 'cases');
const CORPUS = JSON.parse(CASES.toString('utf8'));
const SPANS = extractSpans(SOURCE, CORPUS.source_spans);
const SCAFFOLD = buildScaffold(SPANS);
const caseById = (id) => structuredClone(CORPUS.cases.find((c) => c.id === id));
const refusal = (code) => (e) => e instanceof Refusal && e.code === code;
// Re-serialize a mutated corpus and pin it so only the schema/domain check can refuse.
const mutatedCorpus = (fn) => {
  const c = structuredClone(CORPUS);
  fn(c);
  const bytes = Buffer.from(JSON.stringify(c));
  return { casesBytes: bytes, pins: { source: PINS.source, cases: { bytes: bytes.length, sha256: sha(bytes) } } };
};
const noEvaluation = (fn, code) => {
  const before = vmEvaluationCount();
  assert.throws(fn, refusal(code));
  assert.equal(vmEvaluationCount(), before, `${code} must refuse before any VM evaluation`);
};

// Root regressions use owned source copies and handwritten VM stubs only.
const ownControl = () => {
  fs.mkdirSync(PRIVATE_PREFIX,{recursive:true,mode:0o700});
  const dir=fs.mkdtempSync(path.join(PRIVATE_PREFIX,'control-'));
  const file=path.join(dir,'source.js');fs.writeFileSync(file,SOURCE,{mode:0o600,flag:'wx'});
  return {dir,file};
};

test('direct execution enforces input and timeout ceilings before creating a realm',()=>{
  const before=vmEvaluationCount();
  const stub='var Targa=class {load(){} getImageData(){return {width:1,height:1,data:[1,2,3,4]};}};';
  const refused=runCaseInRealm(stub,caseById('F02_width9_never_evaluated'));
  assert.equal(refused.status,'host_refused');assert.equal(refused.evaluations,0);
  for(const perVmMs of [0,101,150,Infinity,NaN]) {
    const r=runCaseInRealm(stub,caseById('P05_8bit_grey'),{perVmMs});
    assert.equal(r.status,'fixture_failure');assert.equal(r.reason,'vm_timeout_bounds');assert.equal(r.evaluations,0);
  }
  assert.equal(vmEvaluationCount(),before);
});

test('effective heap is enforced at every execution entry, independently of flags',()=>{
  assert.equal(heapLimitOk(),true);
  const original=v8.getHeapStatistics;
  try {
    v8.getHeapStatistics=()=>({heap_size_limit:129*1024*1024});
    noEvaluation(()=>runFixture({sourceBytes:SOURCE,casesBytes:CASES}),'heap_limit');
    noEvaluation(()=>runCaseInRealm('for(;;){}',caseById('P05_8bit_grey')),'heap_limit');
  } finally {v8.getHeapStatistics=original;}
  // The oversized-heap child loads only our module and refuses before source IO/evaluation.
  const child=spawnSync(process.execPath,['--max-old-space-size=128',path.resolve('tools/renewal/run_tga_decoder_fixture.mjs'),'--bundle',BUNDLE,'--mode','authored-cases'],{encoding:'utf8',timeout:5000});
  assert.equal(child.status,2);assert.equal(JSON.parse(child.stdout).refused,'heap_limit');
});

test('owned input identity change during bounded read refuses before evaluation',()=>{
  const {file}=ownControl();const open=fs.openSync,read=fs.readSync;let target,changed=false;
  fs.openSync=function(p,...args){const fd=open.call(this,p,...args);if(p===file)target=fd;return fd;};
  fs.readSync=function(fd,...args){const n=read.call(this,fd,...args);if(fd===target&&n&&!changed){changed=true;fs.chmodSync(file,0o640);}return n;};
  try {noEvaluation(()=>main(['--bundle',file,'--mode','authored-cases'],{write:false}),'input_identity');}
  finally {fs.openSync=open;fs.readSync=read;}
  assert.equal(changed,true);
});

test('same-content pathname replacement and symlink leaves refuse',()=>{
  const {dir,file}=ownControl(), replacement=path.join(dir,'replacement.js');fs.writeFileSync(replacement,SOURCE,{mode:0o600});
  const open=fs.openSync,read=fs.readSync;let target,changed=false;
  fs.openSync=function(p,...args){const fd=open.call(this,p,...args);if(p===file)target=fd;return fd;};
  fs.readSync=function(fd,...args){const n=read.call(this,fd,...args);if(fd===target&&n&&!changed){changed=true;fs.renameSync(file,path.join(dir,'original.js'));fs.renameSync(replacement,file);}return n;};
  try {noEvaluation(()=>main(['--bundle',file,'--mode','authored-cases'],{write:false}),'input_identity');}
  finally {fs.openSync=open;fs.readSync=read;}
  const link=path.join(dir,'link.js');fs.symlinkSync(file,link);
  noEvaluation(()=>main(['--bundle',link,'--mode','authored-cases'],{write:false}),'source_pin');
  assert.equal(changed,true);
});

test('whole command deadline includes input reads before any copied evaluation',()=>{
  const {file}=ownControl(),read=fs.readSync;let jump=0;
  fs.readSync=function(...args){const n=read.apply(this,args);jump=10001;return n;};
  try {noEvaluation(()=>main(['--bundle',file,'--mode','authored-cases'],{write:false,now:()=>performance.now()+jump}),'overall_deadline');}
  finally {fs.readSync=read;}
});

test('deadline during publication invalidates the current result and preserves older captures',()=>{
  const {file}=ownControl();
  const older=main(['--bundle',file,'--mode','authored-cases']);const oldPath=path.resolve(older.capture_dir,'RESULT.json');const oldBytes=fs.readFileSync(oldPath);
  const open=fs.openSync,write=fs.writeSync;let target,dir,jump=0;
  fs.openSync=function(p,...args){const fd=open.call(this,p,...args);if(typeof p==='string'&&p.endsWith('/RESULT.json')){target=fd;dir=path.dirname(p);}return fd;};
  fs.writeSync=function(fd,...args){const n=write.call(this,fd,...args);if(fd===target)jump=10001;return n;};
  try {assert.throws(()=>main(['--bundle',file,'--mode','authored-cases'],{now:()=>performance.now()+jump}),refusal('overall_deadline'));}
  finally {fs.openSync=open;fs.writeSync=write;}
  assert.ok(dir);assert.equal(fs.existsSync(path.join(dir,'RESULT.json')),false);
  assert.equal(fs.existsSync(path.join(dir,'RESULT.unqualified.json')),true);
  assert.equal(JSON.parse(fs.readFileSync(path.join(dir,'FAILURE.json'))).ok,false);
  assert.deepEqual(fs.readFileSync(oldPath),oldBytes);
});

test('exclusive output refuses symlink leaves without changing their target',()=>{
  const {dir:control,file}=ownControl();const target=path.join(control,'sentinel');fs.writeFileSync(target,'unchanged');
  const mkdtemp=fs.mkdtempSync;let capture;
  fs.mkdtempSync=function(...args){const d=mkdtemp.apply(this,args);if(args[0]===path.join(PRIVATE_PREFIX,'run-')){capture=d;fs.symlinkSync(target,path.join(d,'MANIFEST.json'));}return d;};
  try {assert.throws(()=>main(['--bundle',file,'--mode','authored-cases']),e=>e.code==='EEXIST');}
  finally {fs.mkdtempSync=mkdtemp;}
  assert.equal(fs.readFileSync(target,'utf8'),'unchanged');assert.ok(capture);
  assert.equal(fs.existsSync(path.join(capture,'RESULT.json')),false);
  assert.equal(JSON.parse(fs.readFileSync(path.join(capture,'FAILURE.json'))).ok,false);
});

test('input change during descriptor close prevents terminal success',()=>{
  const {file}=ownControl();const open=fs.openSync,close=fs.closeSync;let target,changed=false;
  fs.openSync=function(p,...args){const fd=open.call(this,p,...args);if(p===file)target=fd;return fd;};
  fs.closeSync=function(fd){const result=close.call(this,fd);if(fd===target&&!changed){changed=true;fs.chmodSync(file,0o640);}return result;};
  try {assert.throws(()=>main(['--bundle',file,'--mode','authored-cases'],{write:false}),refusal('input_identity'));}
  finally {fs.openSync=open;fs.closeSync=close;}
  assert.equal(changed,true);
});

test('output literal replacement during close prevents terminal success',()=>{
  const {file}=ownControl();const open=fs.openSync,close=fs.closeSync;let target,output,changed=false;
  fs.openSync=function(p,...args){const fd=open.call(this,p,...args);if(typeof p==='string'&&p.endsWith('/checkHeader.span.js.txt')){target=fd;output=p;}return fd;};
  fs.closeSync=function(fd){const result=close.call(this,fd);if(fd===target&&!changed){changed=true;const b=fs.readFileSync(output);b[0]^=1;fs.renameSync(output,output+'.original');fs.writeFileSync(output,b,{mode:0o600});}return result;};
  try {assert.throws(()=>main(['--bundle',file,'--mode','authored-cases']),refusal('output_identity'));}
  finally {fs.openSync=open;fs.closeSync=close;}
  assert.equal(changed,true);
});

test('full authored run: all 32 ids in order pass with full comparisons and pre/post pins', () => {
  const r = runFixture({ sourceBytes: SOURCE, casesBytes: CASES });
  assert.deepEqual(r.results.map((x) => [x.id, x.category]), CASE_IDS.map((c) => [c.id, c.category]));
  for (const x of r.results) assert.ok(x.pass, `${x.id}: ${x.diffs.join('; ')}`);
  assert.equal(r.passed, 32);
  assert.equal(r.ok, true);
  assert.deepEqual(r.pre, r.post);
  assert.deepEqual(r.pre.source, { bytes: PINS.source.bytes, sha256: PINS.source.sha256 });
  assert.deepEqual(r.pre.cases, { bytes: PINS.cases.bytes, sha256: PINS.cases.sha256 });
  for (const x of r.results) {
    if (x.category === 'host_refusal') {
      assert.equal(x.admitted, false);
      assert.equal(x.actual.evaluations, 0, `${x.id} evaluated source`);
    } else {
      assert.equal(x.actual.evaluations, 4);
      assert.deepEqual(x.actual.realm.probe, { absent: [], littleEndian: true, evalBlocked: true, functionBlocked: true });
      assert.deepEqual(x.actual.realm.methods, ['load', 'getImageData', 'open', 'getCanvas', 'getDataURL']);
    }
    if (x.expected.status === 'pixels') assert.deepEqual(x.actual.rgba, x.expected.rgba);
  }
  assert.equal(r.evaluations, 29 * 4);
  assert.ok(r.within_deadline);
});

test('spans are the byte-identical source slices at the pinned coordinates', () => {
  for (const [i, s] of SPANS.entries()) {
    const pin = CORPUS.source_spans[i];
    const slice = SOURCE.subarray(pin.byte_offset, pin.byte_offset + pin.byte_length);
    assert.ok(Buffer.from(s.text, 'utf8').equals(slice));
    assert.equal(sha(slice), pin.sha256);
    assert.equal(SOURCE[pin.byte_offset - 1], 10);
    assert.equal(slice[slice.length - 1], 10);
  }
  assert.ok(SCAFFOLD.startsWith('var Targa;\n'));
  assert.equal(SCAFFOLD, 'var Targa;\n' + SPANS.map((s) => s.text).join(''));
  assert.ok(!SCAFFOLD.includes('init_Targa') && !SCAFFOLD.includes('__esmMin'));
});

test('wrong channel, origin and single pixel results are discriminated', () => {
  const tl = caseById('P01_32bit_origin_TL');
  const actual = runCaseInRealm(SCAFFOLD, tl);
  assert.ok(compareOutcome(tl.expected, actual).pass);
  // Swap R and B in the expectation.
  const swapped = structuredClone(tl.expected);
  for (let i = 0; i < swapped.rgba.length; i += 4) [swapped.rgba[i], swapped.rgba[i + 2]] = [swapped.rgba[i + 2], swapped.rgba[i]];
  assert.equal(compareOutcome(swapped, actual).pass, false);
  // Every other origin's expectation fails against the TL decode.
  for (const id of ['P01_32bit_origin_TR', 'P01_32bit_origin_BL', 'P01_32bit_origin_BR'])
    assert.equal(compareOutcome(caseById(id).expected, actual).pass, false, id);
  // Changing only the origin flags in authored bytes changes the decoded layout.
  const flagged = structuredClone(tl);
  flagged.bytes[17] = 48;
  const tr = runCaseInRealm(SCAFFOLD, flagged);
  assert.equal(compareOutcome(tl.expected, tr).pass, false);
  assert.ok(compareOutcome(caseById('P01_32bit_origin_TR').expected, tr).pass);
  // One byte of the last pixel in the 8x8 case.
  const big = caseById('P10_max8x8');
  const bigActual = runCaseInRealm(SCAFFOLD, big);
  assert.ok(compareOutcome(big.expected, bigActual).pass);
  const off = structuredClone(big.expected);
  off.rgba[255] = 254;
  assert.deepEqual(compareOutcome(off, bigActual).diffs, ['rgba[255] 255 != 254']);
  // Dimensions and status.
  assert.equal(compareOutcome({ ...tl.expected, width: 4, height: 1 }, actual).pass, false);
  assert.equal(compareOutcome({ status: 'decoder_error', name: 'Error', message_contains: 'x' }, actual).pass, false);
});

test('decoder errors compare name and message fragment exactly', () => {
  const e09 = caseById('E09_rgb8_no_palette');
  const a = runCaseInRealm(SCAFFOLD, e09);
  assert.equal(a.status, 'decoder_error');
  assert.ok(compareOutcome(e09.expected, a).pass);
  assert.equal(compareOutcome({ ...e09.expected, name: 'Error' }, a).pass, false);
  assert.equal(compareOutcome({ ...e09.expected, message_contains: 'Invalid' }, a).pass, false);
  const c03 = caseById('C03_run_packet_overrun_throws');
  const b = runCaseInRealm(SCAFFOLD, c03);
  assert.equal(b.name, 'RangeError');
  assert.ok(compareOutcome(c03.expected, b).pass);
  assert.equal(compareOutcome({ status: 'pixels', width: 1, height: 1, rgba: [0, 0, 0, 0] }, b).pass, false);
});

test('a timeout is a fixture failure, never an expected decoder error', () => {
  const looping = 'var Targa = class { load() { for (;;) {} } getImageData() {} };';
  const t = performance.now();
  const a = runCaseInRealm(looping, caseById('E01_short17'));
  assert.ok(performance.now() - t < 2000);
  assert.equal(a.status, 'fixture_failure');
  assert.equal(a.reason, 'vm_timeout');
  assert.equal(compareOutcome(caseById('E01_short17').expected, a).pass, false);
  // Overall deadline: a clock that jumps past 10 s fails the remaining cases.
  let clock = 0;
  const r = runFixture({ sourceBytes: SOURCE, casesBytes: CASES, now: () => (clock += 400) });
  assert.equal(r.ok, false);
  const late = r.results.filter((x) => x.actual.reason === 'overall_deadline');
  assert.ok(late.length > 0);
  for (const x of late) assert.equal(x.pass, false);
});

test('realm exposes no host globals and the harness never calls open/getCanvas/getDataURL', () => {
  const stub = `var Targa = class {
    load() {} open() { globalThis.hit = 'open'; } getCanvas() { globalThis.hit = 'getCanvas'; } getDataURL() { globalThis.hit = 'getDataURL'; }
    getImageData() { return { width: 1, height: 1, data: [globalThis.hit === undefined ? 1 : 0, typeof require === 'undefined' ? 1 : 0,
      typeof process === 'undefined' ? 1 : 0, typeof setTimeout === 'undefined' ? 1 : 0] }; } };`;
  const a = runCaseInRealm(stub, caseById('P05_8bit_grey'));
  assert.deepEqual(a.rgba, [1, 1, 1, 1]);
  assert.deepEqual(a.realm.methods, ['load', 'getImageData', 'open', 'getCanvas', 'getDataURL']);
  // Fresh realm per case: state from one case is not visible in the next.
  const leak = 'var Targa = class { load() { globalThis.mark = (globalThis.mark || 0) + 1; } getImageData() { return { width: 1, height: 1, data: [globalThis.mark] }; } };';
  assert.deepEqual(runCaseInRealm(leak, caseById('P05_8bit_grey')).rgba, [1]);
  assert.deepEqual(runCaseInRealm(leak, caseById('P05_8bit_grey')).rgba, [1]);
});

test('source pin and span changes refuse before any VM evaluation', () => {
  const flipped = Buffer.from(SOURCE);
  flipped[10] ^= 1;
  noEvaluation(() => runFixture({ sourceBytes: flipped, casesBytes: CASES }), 'source_pin');
  noEvaluation(() => runFixture({ sourceBytes: SOURCE.subarray(1), casesBytes: CASES }), 'source_pin');
  // A byte flipped inside the Targa span: a re-pinned whole source is still refused
  // because the corpus pins the original, and the span pin alone also catches it.
  const inSpan = Buffer.from(SOURCE);
  inSpan[CORPUS.source_spans[2].byte_offset + 100] ^= 1;
  const repinned = { bytes: inSpan.length, sha256: sha(inSpan) };
  const m = mutatedCorpus((c) => { c.source_pin = { ...repinned }; });
  noEvaluation(() => runFixture({ sourceBytes: inSpan, casesBytes: m.casesBytes, pins: { ...m.pins, source: repinned } }), 'corpus_schema');
  const before = vmEvaluationCount();
  assert.throws(() => extractSpans(inSpan, CORPUS.source_spans), refusal('span_pin'));
  assert.equal(vmEvaluationCount(), before);
  for (const [k, v] of [['byte_offset', 1], ['byte_length', 1], ['start_line', 1], ['end_line', -1]]) {
    const s = mutatedCorpus((c) => { c.source_spans[1][k] += v; });
    noEvaluation(() => runFixture({ sourceBytes: SOURCE, casesBytes: s.casesBytes, pins: s.pins }), 'span_pin');
  }
  const h = mutatedCorpus((c) => { c.source_spans[0].sha256 = '0'.repeat(64); });
  noEvaluation(() => runFixture({ sourceBytes: SOURCE, casesBytes: h.casesBytes, pins: h.pins }), 'span_pin');
});

test('corpus pin, schema and domain changes refuse before any VM evaluation', () => {
  const edited = Buffer.from(CASES);
  edited[edited.indexOf('"bytes"') + 10] ^= 1;
  noEvaluation(() => runFixture({ sourceBytes: SOURCE, casesBytes: edited }), 'cases_pin');
  const mutations = {
    reordered: (c) => { [c.cases[0], c.cases[1]] = [c.cases[1], c.cases[0]]; },
    dropped: (c) => { c.cases.pop(); },
    extra_case: (c) => { c.cases.push(structuredClone(c.cases[0])); },
    category: (c) => { c.cases[22].category = 'supported'; },
    status_domain: (c) => { c.cases[13].expected.status = 'pixels'; },
    extra_key: (c) => { c.cases[0].note = 'x'; },
    byte_range: (c) => { c.cases[0].bytes = 'abc'; },
    rgba_length: (c) => { c.cases[0].expected.rgba.pop(); },
    rgba_domain: (c) => { c.cases[0].expected.rgba[0] = 256; },
    error_name: (c) => { c.cases[13].expected.name = 'SyntaxError'; },
    zero_flag_removed: (c) => { delete c.cases[15].allow_zero_dimension; },
    zero_flag_added: (c) => { c.cases[0].allow_zero_dimension = true; },
    refusal_code: (c) => { c.cases[29].expected.code = 'other'; },
    bound: (c) => { c.bounds.max_width = 9; },
    timeout: (c) => { c.bounds.per_vm_timeout_ms = 1000; },
    endianness: (c) => { c.requires_little_endian = false; },
    boundary: (c) => { c.evidence_boundary = 'x'; },
    span_id: (c) => { c.source_spans[0].id = 'other'; }
  };
  for (const [name, fn] of Object.entries(mutations)) {
    const m = mutatedCorpus(fn);
    const before = vmEvaluationCount();
    assert.throws(() => runFixture({ sourceBytes: SOURCE, casesBytes: m.casesBytes, pins: m.pins }), refusal('corpus_schema'), name);
    assert.equal(vmEvaluationCount(), before, name);
  }
  // Unchanged re-serialization with matching pins still passes, so refusals above are the mutations.
  const same = mutatedCorpus(() => {});
  assert.equal(runFixture({ sourceBytes: SOURCE, casesBytes: same.casesBytes, pins: same.pins }).ok, true);
});

test('boundary admission happens before evaluation and refuses oversized authored inputs', () => {
  const base = caseById('P07_rle_run');
  const at = (patch) => { const c = structuredClone(base); patch(c); return admitCase(c); };
  assert.equal(at(() => {}).admitted, true);
  assert.deepEqual(at((c) => { c.bytes = c.bytes.concat(new Array(4096 - c.bytes.length).fill(0)); }).admitted, true);
  assert.equal(at((c) => { c.bytes = c.bytes.concat(new Array(4097 - c.bytes.length).fill(0)); }).reason, 'encoded_bytes');
  assert.equal(at((c) => { c.bytes[0] = 256; }).reason, 'byte_domain');
  assert.equal(at((c) => { c.bytes[0] = 1.5; }).reason, 'byte_domain');
  assert.equal(at((c) => { c.bytes[12] = 9; }).reason, 'dimensions');
  assert.equal(at((c) => { c.bytes[14] = 9; }).reason, 'dimensions');
  assert.equal(at((c) => { c.bytes[13] = 1; }).reason, 'dimensions');
  assert.equal(at((c) => { c.bytes[12] = 0; }).reason, 'zero_dimension');
  assert.equal(at((c) => { c.bytes[14] = 0; }).reason, 'zero_dimension');
  assert.equal(at((c) => { c.bytes[12] = 8; c.bytes[14] = 8; c.bytes[16] = 40; }).reason, 'rle_output');
  // Short inputs are admitted only under the encoded cap.
  assert.equal(admitCase({ id: 'x', bytes: new Array(17).fill(0) }).admitted, true);
  assert.equal(admitCase({ id: 'x', bytes: new Array(4097).fill(0) }).reason, 'encoded_bytes');
  // Zero dimension is allowed only for the two explicit controls.
  assert.equal(admitCase(caseById('E03_zero_width')).admitted, true);
  assert.equal(admitCase({ ...caseById('E03_zero_width'), id: 'E05_depth15' }).reason, 'zero_dimension');
  for (const id of ['F01_huge_header_never_evaluated', 'F02_width9_never_evaluated', 'F03_height9_never_evaluated'])
    assert.equal(admitCase(caseById(id)).admitted, false, id);
  // A supported case grown to width 9 is host-refused, evaluates nothing, and FAILs its pixel expectation.
  const m = mutatedCorpus((c) => { c.cases[12].bytes[12] = 9; });
  const r = runFixture({ sourceBytes: SOURCE, casesBytes: m.casesBytes, pins: m.pins });
  const p10 = r.results[12];
  assert.equal(p10.actual.status, 'host_refused');
  assert.equal(p10.actual.evaluations, 0);
  assert.equal(p10.pass, false);
  assert.equal(r.ok, false);
  // Bytes reach the realm only as validated integer literals.
  assert.match(harnessCall(base.bytes), /new Uint8Array\(\[[0-9,]+\]\)/);
  assert.equal(BOUNDS.per_vm_timeout_ms, 100);
});

test('little-endian is required before any evaluation', () => {
  noEvaluation(() => runFixture({ sourceBytes: SOURCE, casesBytes: CASES, littleEndian: false }), 'not_little_endian');
});

test('CLI refuses default/other arguments without reading, evaluating or writing', () => {
  const listing = () => (fs.existsSync(PRIVATE_PREFIX) ? fs.readdirSync(PRIVATE_PREFIX).sort() : []);
  const before = listing();
  for (const argv of [[], ['--bundle', BUNDLE], ['--bundle', 'relative/Online.js', '--mode', 'authored-cases'],
    ['--bundle', BUNDLE, '--mode', 'image'], ['--bundle', BUNDLE, '--mode', 'authored-cases', '--width', '9'],
    ['--bundle', BUNDLE, '--bundle', BUNDLE], ['--image', BUNDLE, '--mode', 'authored-cases']])
    noEvaluation(() => main(argv), 'usage');
  assert.deepEqual(listing(), before);
  assert.deepEqual(parseArgs(['--mode', 'authored-cases', '--bundle', BUNDLE]), { mode: 'authored-cases', bundle: BUNDLE });
  noEvaluation(() => readPinned(CASES_PATH, PINS.source, 'source'), 'source_pin');
  assert.throws(() => validateCorpus({}), refusal('corpus_schema'));
});
