// Unrun T10.005 controls. Root runs this file later under the guarded harness.
// Each case executes an extracted production fragment with controlled
// dependencies. strictJSON here is only a parse dependency. Sequence numbers
// are not seeded; shutdownSequence starts at 0 and the fragments increment it.
// The existing controller regression groups are not copied.

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import test from 'node:test';
import vm from 'node:vm';

// Root binds these three metadata lines in a fresh private driver copy.
const ROOT_BOUND = false;
const FRAGMENTS_PATH = null;
const FRAGMENTS_PIN = null;
assert.equal(ROOT_BOUND, true, 'Root must bind the reviewed production-fragment input');
assert.equal(typeof FRAGMENTS_PATH, 'string');
assert.equal(typeof FRAGMENTS_PIN?.sha256, 'string');
assert.ok(Number.isSafeInteger(FRAGMENTS_PIN.bytes) && FRAGMENTS_PIN.bytes > 0 && FRAGMENTS_PIN.bytes <= 131072);
const fragmentBytes = readFileSync(FRAGMENTS_PATH);
assert.equal(fragmentBytes.length, FRAGMENTS_PIN.bytes);
assert.equal(createHash('sha256').update(fragmentBytes).digest('hex'), FRAGMENTS_PIN.sha256);
const fragmentInput = JSON.parse(fragmentBytes);
assert.equal(fragmentInput.schema, 'T10.005-root-production-control-fragments.v1');
const FRAGMENTS = fragmentInput.fragments;

const ORIGIN = 'https://fixture.invalid';
const PATH = '/native/SystemEN/OngoingQuests.lub';
const URL_OK = ORIGIN + PATH;
const FAILURE = "Can't get file";

function flush(times = 30) {
  let chain = Promise.resolve();
  for (let index = 0; index < times; index += 1) chain = chain.then(() => {});
  return chain;
}

function run(context, source) {
  return vm.runInContext(source, context);
}

test('extracted fragments name the production helpers', () => {
  assert.match(FRAGMENTS['drain-methods'], /static drainAdmittedOptionalNative404/);
  assert.match(FRAGMENTS['drain-methods'], /FAILURE_LIMIT_MS = 5 \* 1000/);
  assert.match(FRAGMENTS['drain-methods'], /traceIsGrant: false/);
  assert.match(FRAGMENTS['fetch-branch'], /FileManager\.admitsOptionalNative404/);
  assert.doesNotMatch(FRAGMENTS['fetch-branch'], /saveFile/);
  assert.match(FRAGMENTS['success-tail'], /callback\(buffer\);\s*FileSystem\.saveFile\(filename, buffer\);/);
  assert.match(FRAGMENTS['success-tail'], /callback\(null, "Can't get file"\)/);
  assert.equal(FRAGMENTS['success-tail'].includes('XMLHttpRequest'), false);
  assert.match(FRAGMENTS.listeners, /function onControllerSocketError/);
  assert.match(FRAGMENTS.listeners, /function onControllerSocketClose/);
  assert.match(FRAGMENTS.message, /function onControllerSocketMessage/);
  assert.match(FRAGMENTS.call, /browserCloseSend/);
  assert.match(FRAGMENTS.clock, /at>=lastClock/);
  assert.match(FRAGMENTS.expression, /traceIsGrant/);
  assert.match(FRAGMENTS.helpers, /function classifyOwnedShutdown/);
  assert.match(FRAGMENTS['completion-gate'], /readDrainWitness/);
});

function project(snapshot, missing = false) {
  const context = vm.createContext({
    self: missing ? {} : {
      __ROOT011Trace: {
        snapshot() {
          if (snapshot && snapshot.throws) throw new Error('snapshot failed');
          return snapshot;
        }
      }
    }
  });
  return JSON.parse(JSON.stringify(run(context, FRAGMENTS.expression)));
}

function successSnapshot(extraRows = []) {
  return {
    observerIntegrity: true,
    observerFaults: 0,
    droppedRecords: 0,
    snapshotFailed: false,
    rows: [
      {
        kind: 'admitted-negative-drain',
        metadata: {
          schema: 't10.005.admitted-negative-drain.v1', filename: 'SystemEN/OngoingQuests.lub',
          code: 'uncancelled-eof', contentLength: '14',
          outcome: 'eof', uncancelledEof: true, total: 14, saved: false, discarded: true,
          status: 404, manifestPath: PATH, traceIsGrant: false,
          callbackContract: 'original-false-once'
        }
      },
      {
        kind: 'FileManager.getHTTP.callback',
        metadata: {
          filename: 'SystemEN\\OngoingQuests.lub',
          values: [
            { type: 'null', present: false, id: null },
            { type: 'string', present: true, string: FAILURE }
          ]
        }
      },
      ...extraRows
    ]
  };
}

test('drain expression accepts one uncancelled 14-byte witness and nothing else', () => {
  const value = project(successSnapshot([{ kind: 'fetch.return', metadata: { url: 'kept-out' } }]));
  assert.deepEqual(value, {
    ok: true, code: 'uncancelled-eof', total: 14, status: 404,
    manifestPath: PATH, callbackOnce: true, saved: false
  });
  assert.equal(JSON.stringify(value).includes('http'), false);
  assert.equal(JSON.stringify(value).includes('kept-out'), false);
  assert.equal(project(null, true).code, 'missing-trace');
  assert.equal(project({ throws: true }).code, 'observer-fault');
  assert.equal(project({ ...successSnapshot(), observerIntegrity: false }).code, 'observer-fault');
  assert.equal(project({ ...successSnapshot(), observerFaults: 1 }).code, 'observer-fault');
  assert.equal(project({ ...successSnapshot(), droppedRecords: 1 }).code, 'observer-fault');
  assert.equal(project({ ...successSnapshot(), snapshotFailed: true }).code, 'observer-fault');
  assert.equal(project({ ...successSnapshot(), rows: [{ kind: 1 }] }).code, 'malformed');
  const missing = successSnapshot();
  missing.rows = missing.rows.filter(row => row.kind !== 'admitted-negative-drain');
  assert.equal(project(missing).code, 'missing-witness');
  const duplicate = successSnapshot();
  duplicate.rows.push(duplicate.rows[0]);
  assert.equal(project(duplicate).code, 'duplicate-witness');
  const badCallback = successSnapshot();
  badCallback.rows[1].metadata.values = [{ type: 'null', present: true }, { type: 'string', string: FAILURE }];
  assert.equal(project(badCallback).code, 'malformed');
  const noCallback = successSnapshot();
  noCallback.rows.splice(1, 1);
  assert.equal(project(noCallback).code, 'callback-witness');
  assert.equal(project(successSnapshot([{
    kind: 'FileSystem.saveFile.call',
    metadata: { filename: 'SystemEN/OngoingQuests.lub' }
  }])).code, 'save-witness');
  const failed = successSnapshot();
  failed.rows[0].metadata.outcome = 'failed';
  assert.equal(project(failed).code, 'failed-witness');
});

function failedSnapshot(code = 'timeout', total = 0) {
  const snapshot = successSnapshot();
  Object.assign(snapshot.rows[0].metadata, {
    outcome: 'failed', uncancelledEof: false, code, total
  });
  return snapshot;
}

test('drain expression preserves a bounded authentic negative outcome', () => {
  for (const code of ['timeout', 'null-body', 'missing-length', 'false-length', 'read-error', 'over-cap', 'short', 'invalid-chunk', 'zero-progress', 'invalid-read-result', 'invalid-eof']) {
    const value = project(failedSnapshot(code, 3));
    assert.deepEqual(value, {
      ok: false, code, total: 3, status: 404,
      manifestPath: PATH, callbackOnce: true, saved: false
    });
  }
  assert.equal(project(failedSnapshot('unrecognized')).code, 'failed-witness');
  assert.equal(project(failedSnapshot('timeout', 15)).code, 'malformed');
});

function bootDrain() {
  const harness = { now: 0, timers: [] };
  const trace = {
    rows: [],
    faults: [],
    keep: true,
    record(kind, metadata) {
      this.rows.push({ kind, metadata: JSON.parse(JSON.stringify(metadata)) });
      return this.keep;
    },
    fault(error) { this.faults.push(String(error)); }
  };
  const context = vm.createContext({ harness, trace, URL });
  context.performance = { now() { return harness.now; } };
  context.self = {
    location: { href: ORIGIN + '/viewer_QUEST.html', origin: ORIGIN },
    __ROOT011Trace: trace
  };
  run(context, `
    function setTimeout(fn, ms) {
      const timer = { fn, ms, cleared: false };
      harness.timers.push(timer);
      return timer;
    }
    function clearTimeout(timer) { if (timer) timer.cleared = true; }
    function makeReader(steps) {
      let index = 0;
      const reader = {
        cancels: 0, released: false, pending: null, onCancel: null, neverSettleCancel: false,
        read() {
          const step = steps[index++];
          if (!step) return Promise.resolve({ done: true });
          if (step.throw) throw step.throw;
          if (step.reject) return Promise.reject(step.reject);
          if (step.pending) return new Promise(resolve => { reader.pending = resolve; });
          if (step.advance !== undefined) harness.now = step.advance;
          if (Object.hasOwn(step, 'rawResult')) return Promise.resolve(step.rawResult);
          let value = step.value;
          if (Object.hasOwn(step, 'bytes')) {
            const offset = step.byteOffset ?? 0;
            if (!Number.isSafeInteger(step.bytes) || step.bytes < 0 || step.bytes > 64 ||
                !Number.isSafeInteger(offset) || offset < 0 || offset > 32) throw new Error('authored byte-step bound');
            value = new Uint8Array(step.bytes + offset).subarray(offset);
          }
          return Promise.resolve({ done: step.done, value });
        },
        cancel() {
          reader.cancels += 1;
          if (reader.onCancel) reader.onCancel();
          if (reader.neverSettleCancel) return new Promise(() => {});
          return Promise.resolve();
        },
        releaseLock() { reader.released = true; }
      };
      return reader;
    }
    function makeResponse(reader, header) {
      return {
        url: "https://fixture.invalid/native/SystemEN/OngoingQuests.lub",
        redirected: false,
        body: header && header.nullBody ? null : { getReader() {
          if (header && header.readerThrow) throw header.readerThrow;
          return reader;
        } },
        headers: { get() {
          if (header && header.throw) throw header.throw;
          return header ? header.value : null;
        } }
      };
    }
    class FileManager {
    ${FRAGMENTS['drain-methods']}
    }
    globalThis.FileManager = FileManager;
    globalThis.makeReader = makeReader;
    globalThis.makeResponse = makeResponse;
  `);
  return { context, harness, trace };
}

async function drain(header, steps, prepare) {
  const boot = bootDrain();
  boot.context.steps = steps;
  const reader = run(boot.context, 'makeReader(steps)');
  if (prepare) prepare(reader, boot);
  boot.context.reader = reader;
  boot.context.header = header;
  const response = run(boot.context, 'makeResponse(reader, header)');
  boot.context.response = response;
  const promise = run(boot.context, 'FileManager.drainAdmittedOptionalNative404(response)');
  return { ...boot, reader, promise };
}

test('admitted native 404 filename and same-origin path', () => {
  const { context } = bootDrain();
  const admit = (filename, url, status = 404, responseURL = URL_OK, redirected = false) => run(
    context,
    `FileManager.admitsOptionalNative404(${JSON.stringify(filename)}, ${JSON.stringify(url)}, {status:${status},url:${JSON.stringify(responseURL)},redirected:${JSON.stringify(redirected)}})`
  );
  assert.equal(admit('SystemEN/OngoingQuests.lub', URL_OK), true);
  assert.equal(admit('SystemEN/OngoingQuests.lub', PATH), true);
  assert.equal(admit('SystemEN/OngoingQuests.lub', URL_OK + '?x=1'), false);
  assert.equal(admit('SystemEN/OngoingQuests.lub', URL_OK + '#part'), false);
  assert.equal(admit('SystemEN/OngoingQuests.lub', 'https://elsewhere.invalid' + PATH), false);
  assert.equal(admit('SystemEN/Other.lub', URL_OK), false);
  assert.equal(admit('SystemEN\\OngoingQuests.lub', URL_OK), false);
  assert.equal(admit('SystemEN/OngoingQuests.lub', URL_OK, 200), false);
  for (const finalURL of [
    'https://elsewhere.invalid' + PATH,
    ORIGIN + '/native/SystemEN/Other.lub',
    URL_OK + '?x=1',
    URL_OK + '#part',
    ''
  ]) assert.equal(admit('SystemEN/OngoingQuests.lub', URL_OK, 404, finalURL), false);
  assert.equal(admit('SystemEN/OngoingQuests.lub', URL_OK, 404, URL_OK, true), false);
  assert.equal(admit('SystemEN/OngoingQuests.lub', URL_OK, 404, URL_OK, null), false);
  assert.equal(run(context,
    `FileManager.admitsOptionalNative404('SystemEN/OngoingQuests.lub', ${JSON.stringify(URL_OK)}, {status:404,url:${JSON.stringify(URL_OK)}})`), false);
  assert.equal(run(context,
    `FileManager.admitsOptionalNative404('SystemEN/OngoingQuests.lub', ${JSON.stringify(URL_OK)}, {status:404,redirected:false})`), false);
});

test('real uncancelled 14-byte EOF discards the body', async () => {
  const marker = { done: false, bytes: 14, marker: 'File not found' };
  const seen = await drain({ value: '14' }, [marker, { done: true }]);
  await flush();
  const row = await seen.promise;
  assert.equal(row.code, 'uncancelled-eof');
  assert.equal(row.uncancelledEof, true);
  assert.equal(row.total, 14);
  assert.equal(row.saved, false);
  assert.equal(row.discarded, true);
  assert.equal(row.traceIsGrant, false);
  assert.equal(row.manifestPath, PATH);
  assert.equal(seen.reader.cancels, 0);
  assert.equal(seen.reader.released, true);
  assert.equal(seen.harness.timers[0].ms, 5000);
  assert.equal(seen.harness.timers[0].cleared, true);
  const recorded = seen.trace.rows[0];
  assert.equal(recorded.kind, 'admitted-negative-drain');
  assert.equal(recorded.metadata.outcome, 'eof');
  assert.equal(JSON.stringify(recorded).includes('File not found'), false);
});

test('fourteen bytes split across chunks still reaches uncancelled EOF', async () => {
  const seen = await drain({ value: '14' }, [
    { done: false, bytes: 10, marker: 'part' },
    { done: false, bytes: 4, marker: 'rest' },
    { done: true }
  ]);
  await flush();
  const row = await seen.promise;
  assert.equal(row.code, 'uncancelled-eof');
  assert.equal(row.total, 14);
  assert.equal(seen.reader.cancels, 0);
});

test('clock boundaries around the 5000ms failure limit', async () => {
  const open = await drain({ value: '14' }, [
    { advance: 4999, done: false, bytes: 14, marker: 'edge' },
    { done: true }
  ]);
  await flush();
  assert.equal((await open.promise).code, 'uncancelled-eof');
  const closed = await drain({ value: '14' }, [
    { done: false, bytes: 14, marker: 'late' },
    { advance: 5000, done: true }
  ]);
  await flush();
  const row = await closed.promise;
  assert.equal(row.code, 'timeout');
  assert.equal(row.uncancelledEof, false);
  assert.equal(closed.harness.timers[0].cleared, true);
});

test('timeout latches failure before cancel and does not accept the later EOF', async () => {
  const seen = await drain({ value: '14' }, [{ pending: true }], reader => {
    reader.onCancel = () => reader.pending({ done: true });
  });
  await flush();
  assert.equal(seen.harness.timers.length, 1);
  seen.harness.timers[0].fn();
  await flush();
  const row = await seen.promise;
  assert.equal(row.code, 'timeout');
  assert.equal(row.uncancelledEof, false);
  assert.equal(seen.reader.cancels, 1);
  assert.equal(seen.trace.rows[0].metadata.outcome, 'failed');
});

test('a never-settling cancel does not block the failure witness', async () => {
  const seen = await drain({ value: '14' }, [{ reject: new Error('read failed') }], reader => {
    reader.neverSettleCancel = true;
  });
  let settled = false;
  seen.promise.then(() => { settled = true; }, () => { settled = true; });
  await flush();
  assert.equal(settled, true);
  assert.equal(seen.trace.rows[0].metadata.code, 'read-error');
  assert.equal(seen.reader.cancels, 1);
});

test('negative drain refusals keep one failed witness and discard bytes', async () => {
  const cases = [
    [{ value: null }, [], 'missing-length'],
    [{ value: '15' }, [], 'false-length'],
    [{ value: '014' }, [], 'false-length'],
    [{ value: '' }, [], 'false-length'],
    [{ value: 14 }, [], 'false-length'],
    [{ throw: new Error('header') }, [], 'missing-length'],
    [{ nullBody: true, value: '14' }, [], 'null-body'],
    [{ value: '14', readerThrow: new Error('no reader') }, [], 'read-error'],
    [{ value: '14' }, [{ done: false, bytes: 10, marker: 'short-body' }, { done: true }], 'short'],
    [{ value: '14' }, [{ done: false, bytes: 15, marker: 'TOO-BIG' }], 'over-cap'],
    [{ value: '14' }, [{ done: false, bytes: 10, marker: 'TEN' }, { done: false, bytes: 5, marker: 'FIVE' }], 'over-cap'],
    [{ value: '14' }, [{ done: false, bytes: 0, marker: 'zero' }], 'zero-progress'],
    [{ value: '14' }, [{ done: false, value: null }], 'invalid-chunk'],
    [{ value: '14' }, [{ done: false, value: { byteLength: 1.5 } }], 'invalid-chunk'],
    [{ value: '14' }, [{ done: false, value: { byteLength: 14 } }, { done: true }], 'invalid-chunk'],
    [{ value: '14' }, [{ done: false, value: new ArrayBuffer(14) }], 'invalid-chunk'],
    [{ value: '14' }, [{ done: false, value: new DataView(new ArrayBuffer(14)) }], 'invalid-chunk'],
    [{ value: '14' }, [{ done: false, value: new Uint16Array(7) }], 'invalid-chunk'],
    [{ value: '14' }, [{ done: false, value: new Uint8ClampedArray(14) }], 'invalid-chunk'],
    [{ value: '14' }, [{ reject: new Error('rejected') }], 'read-error'],
    [{ value: '14' }, [{ throw: new Error('thrown') }], 'read-error']
  ];
  for (const [header, steps, code] of cases) {
    const seen = await drain(header, steps);
    await flush();
    const row = await seen.promise;
    assert.equal(row.code, code, code);
    assert.equal(row.uncancelledEof, false);
    assert.equal(row.saved, false);
    const text = JSON.stringify(seen.trace.rows[0]);
    assert.equal(text.includes('short-body'), false);
    assert.equal(text.includes('TOO-BIG'), false);
    assert.equal(text.includes('TEN'), false);
    assert.equal(text.includes('"15"'), false);
  }
});

test('a dropped trace record faults and is not treated as a grant', async () => {
  const seen = await drain({ value: '14' }, [{ done: false, bytes: 14 }, { done: true }], (_reader, boot) => {
    boot.trace.keep = false;
  });
  await flush();
  const row = await seen.promise;
  assert.equal(row.traceIsGrant, false);
  assert.equal(seen.trace.faults.length, 1);
});

test('same-Worker-realm Uint8Array subarray keeps exact fourteen bytes', async () => {
  const seen = await drain({ value: '14' }, [
    { done: false, bytes: 14, byteOffset: 3 },
    { done: true, value: undefined }
  ]);
  await flush();
  const row = await seen.promise;
  assert.equal(row.code, 'uncancelled-eof');
  assert.equal(row.total, 14);
  assert.equal(seen.reader.cancels, 0);
  assert.equal(seen.reader.released, true);
});

test('malformed read-result shape never becomes native EOF', async () => {
  const inherited = Object.create({ done: false });
  inherited.value = { byteLength: 14 };
  for (const rawResult of [
    null, undefined, [], 14, false, 'not a read result', () => {}, {},
    { value: { byteLength: 14 } }, inherited,
    { done: null }, { done: 0 }, { done: 1 }, { done: 'false' }
  ]) {
    const seen = await drain({ value: '14' }, [{ rawResult }]);
    await flush();
    const row = await seen.promise;
    assert.equal(row.code, 'invalid-read-result');
    assert.equal(row.outcome, 'failed');
    assert.equal(row.uncancelledEof, false);
    assert.equal(row.saved, false);
    assert.equal(seen.reader.cancels, 1);
    assert.equal(seen.reader.released, true);
    assert.equal(seen.trace.rows.length, 1);
    assert.equal(seen.harness.timers[0].cleared, true);
  }
});

test('native EOF cannot silently carry an extra value', async () => {
  for (const eof of [
    { done: true, value: null },
    { done: true, bytes: 0 },
    { done: true, bytes: 1 }
  ]) {
    const seen = await drain({ value: '14' }, [{ done: false, bytes: 14 }, eof]);
    await flush();
    const row = await seen.promise;
    assert.equal(row.code, 'invalid-eof');
    assert.equal(row.outcome, 'failed');
    assert.equal(row.total, 14);
    assert.equal(row.uncancelledEof, false);
    assert.equal(row.saved, false);
    assert.equal(seen.reader.cancels, 1);
    assert.equal(seen.reader.released, true);
    assert.equal(seen.trace.rows.length, 1);
    assert.equal(seen.harness.timers[0].cleared, true);
  }
});

function bootContinuation(options = {}) {
  const boot = bootDrain();
  boot.harness.callbacks = [];
  boot.harness.saves = [];
  boot.harness.throwOnCallback = options.throwOnCallback === true;
  run(boot.context, `
    function callback() {
      harness.callbacks.push(Array.from(arguments));
      if (harness.throwOnCallback && harness.callbacks.length === 1) throw new Error('consumer threw');
    }
    const FileSystem = { saveFile(filename, buffer) { harness.saves.push({ filename, buffer }); } };
    function run(response, filename, url) {
      function fetch() { return Promise.resolve(response); }
      if (typeof fetch !== "undefined") {
        fetch(url).then(function(response) {
${FRAGMENTS['fetch-branch']}${FRAGMENTS['success-tail']}
    }
  `);
  return boot;
}

async function continueWith(response, filename = 'SystemEN/OngoingQuests.lub', options) {
  const boot = bootContinuation(options);
  boot.context.response = response;
  run(boot.context, `run(response, ${JSON.stringify(filename)}, ${JSON.stringify(URL_OK)})`);
  await flush();
  return boot;
}

function okResponse(body, contentType = 'application/octet-stream') {
  return {
    ok: true,
    status: 200,
    headers: { get() { return contentType; } },
    arrayBuffer() { return Promise.resolve(body); }
  };
}

test('successful 200 callback and save stay on the original tail', async () => {
  const body = new Uint8Array([9, 8, 7]).buffer;
  const boot = await continueWith(okResponse(body));
  assert.equal(boot.harness.callbacks.length, 1);
  assert.equal(boot.harness.callbacks[0][0], body);
  assert.equal(boot.harness.saves.length, 1);
  assert.equal(boot.harness.saves[0].filename, 'SystemEN/OngoingQuests.lub');
  assert.equal(boot.harness.saves[0].buffer, body);
  assert.equal(boot.trace.rows.length, 0);
});

test('a throwing 200 callback still reaches the original catch', async () => {
  const boot = await continueWith(okResponse(new ArrayBuffer(1)), 'SystemEN/OngoingQuests.lub', { throwOnCallback: true });
  assert.equal(boot.harness.callbacks.length, 2);
  assert.deepEqual(Array.from(boot.harness.callbacks[1]), [null, FAILURE]);
  assert.equal(boot.harness.saves.length, 0);
});

test('admitted 404 drain still uses the original false callback once and does not save', async () => {
  const boot = bootContinuation();
  const response = run(boot.context, 'makeResponse(makeReader([{done:false,bytes:14},{done:true}]), {value:"14"})');
  response.ok = false;
  response.status = 404;
  boot.context.response = response;
  run(boot.context, `run(response, ${JSON.stringify('SystemEN/OngoingQuests.lub')}, ${JSON.stringify(URL_OK)})`);
  await flush();
  assert.equal(boot.harness.callbacks.length, 1);
  assert.deepEqual(Array.from(boot.harness.callbacks[0]), [null, FAILURE]);
  assert.equal(boot.harness.saves.length, 0);
  assert.equal(boot.trace.rows[0].metadata.code, 'uncancelled-eof');
});

test('a non-admitted negative response keeps the original catch and skips the drain', async () => {
  const response = { ok: false, status: 404, headers: { get() { return null; } } };
  const boot = await continueWith(response, 'SystemEN/Other.lub');
  assert.equal(boot.harness.callbacks.length, 1);
  assert.deepEqual(Array.from(boot.harness.callbacks[0]), [null, FAILURE]);
  assert.equal(boot.harness.saves.length, 0);
  assert.equal(boot.trace.rows.length, 0);
});

test('an admitted null body fails the drain and calls back once without saving', async () => {
  const boot = bootContinuation();
  const response = run(boot.context, 'makeResponse(null, {nullBody:true, value:"14"})');
  response.ok = false;
  response.status = 404;
  boot.context.response = response;
  run(boot.context, `run(response, ${JSON.stringify('SystemEN/OngoingQuests.lub')}, ${JSON.stringify(URL_OK)})`);
  await flush();
  assert.equal(boot.harness.callbacks.length, 1);
  assert.deepEqual(Array.from(boot.harness.callbacks[0]), [null, FAILURE]);
  assert.equal(boot.harness.saves.length, 0);
  assert.equal(boot.trace.rows[0].metadata.code, 'null-body');
});

function bootController() {
  const harness = {
    now: 100, finish: [], finalize: [], eventsSeen: 0,
    evaluate: null, poison: null, endingDuringRead: false,
    evaluations: 0, holdEvaluation: false, heldReply: null,
    snapshot: successSnapshot()
  };
  const context = vm.createContext({ harness });
  context.performance = { now() { return harness.now; } };
  context.Buffer = Buffer;
  run(context, `
    var ending = false, finalized = false, grantVerified = true;
    var browserCloseAcknowledged = false, browserCloseAttempted = false;
    var cleanupAck = false, workerDetached = false, pageDetached = false, pageClosed = false;
    var workerDestroyed = false, pageDestroyed = false, pageCleanupFailed = false;
    var cleanupDeadline = 0, lastClock = 0, nextId = 0, shutdownSequence = 0;
    var drainWitnessGate = false, drainWitnessPending = false, drainWitnessStarted = false, drainWitnessRequestCount = null;
    var pageSessionId = 'page-session', expectedTargetId = 'page-target';
    var worker = { sessionId: 'worker-session', targetId: 'worker-target' };
    var receivedBytes = 0, messages = 0, eventBytes = 0;
    var navigationAck = true, pageReady = true, workerReady = true, workerResumeAcknowledged = true;
    var discoveryAttempted = true, pageCloseRequested = false;
    var pageAttachStarted = false, pageAttachEvent = null, navigationIssued = true;
    var bootstrapKey = 'bootstrap', bootstrapWorkerKey = null;
    var workerURL = ${JSON.stringify(ORIGIN + '/ThreadEventHandler.js')};
    var cfg = { fixtureOrigin: ${JSON.stringify(ORIGIN)}, requestManifest: { length: 9 } };
    var routes = new Map([[${JSON.stringify(PATH)}, { method: 'GET', sessions: ['worker'], statuses: [200, 404] }]]);
    var fixedPOST = new Set(['/_viewer/report', '/_viewer/failure']);
    var requests = new Map([
      ['budget', { url: cfg.fixtureOrigin + '/_root/budget', sid: pageSessionId, role: 'page', method: 'GET' }],
      ['report', { url: cfg.fixtureOrigin + '/_viewer/report', sid: pageSessionId, role: 'page', method: 'POST' }],
      ['wasm', { url: cfg.fixtureOrigin + '/liblua5.1.wasm', sid: pageSessionId, role: 'page', method: 'GET' }],
      ['bootstrap', { url: workerURL, sid: pageSessionId, role: 'page', method: 'GET' }],
      [JSON.stringify([worker.sessionId, 'native']), { url: cfg.fixtureOrigin + ${JSON.stringify(PATH)}, sid: worker.sessionId, role: 'worker', method: 'GET', statuses: [200, 404] }]
    ]);
    var terminals = new Set(requests.keys());
    var terminalMethods = new Map([...requests.keys()].map(key => [key, 'Network.loadingFinished']));
    var responseStatuses = new Map([...requests.keys()].map(key => [key, key === JSON.stringify([worker.sessionId, 'native']) ? 404 : 200]));
    var responses = new Set(requests.keys());
    const WebSocket = { OPEN: 1 };
    const LIMIT = { commands: 512, requests: 2048, events: 8192, eventBytes: 16 << 20, messageBytes: 32 << 20, wireBytes: 64 << 20, wireMessages: 65536 };
    const result = {
      events: [], errors: [], commands: [], completionFence: false, foreignDiscoveryEvents: 0,
      ownedShutdownAllowsCompletion: false, ownedAbnormalCloseCandidate: false,
      shutdownInterleaved: false, shutdownDuplicateError: false, websocketError: null,
      browserCloseSend: null, browserCloseAck: null, ownedAbnormalClose: null, websocketClose: null,
      nativeWorkerBootstrapQualified: true,
      lastState: { done: true, publicationAttempted: true, acknowledgmentVerified: true, budgetVerified: true,
        stage: 'published', diagnosticComplete: true, failurePresent: false, preservationFailurePresent: false }
    };
    const pending = new Map();
    const ws = {
      readyState: 1, sent: null,
      send(payload) {
        this.sent = payload;
        const command = JSON.parse(payload);
        if (command.method === 'Runtime.evaluate') { harness.evaluations++; harness.deliverEvaluate(command); }
      },
      addEventListener() {}, close() {}
    };
    const need = (value, why) => { if (!value) { const error = new Error(why); error.validationCode = why; throw error; } };
    const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
    const keys = (value, names) => object(value) && Object.keys(value).sort().join(',') === names.slice().sort().join(',');
    const safeId = value => typeof value === 'string' && value.length > 0 && value.length <= 256;
    const allowedURL = value => typeof value === 'string' && value.startsWith(cfg.fixtureOrigin) && routes.has(value.slice(cfg.fixtureOrigin.length));
    function controlCheck() { need(!ending && !finalized, 'control ended'); }
    function retain(row) { harness.eventsSeen++; result.events.push(row); }
    function firstValidation(error) { result.firstValidationCode = error && error.validationCode || 'DIAGNOSTIC_FAILURE'; }
    function finish(reason) {
      harness.finish.push(reason);
      if (reason) result.errors.push(reason);
      ending = true;
    }
    function finalize(reason) {
      harness.finalize.push(reason);
      if (reason) result.errors.push(reason);
      finalized = true;
    }
    function strictJSON(input, cap) {
      const text = String(input);
      if (Buffer.byteLength(text) > cap) throw new Error('JSON cap');
      return { value: JSON.parse(text), text };
    }
    ${FRAGMENTS.clock}
    ${FRAGMENTS.helpers}
    ${FRAGMENTS.call}
    ${FRAGMENTS.message}
    ${FRAGMENTS.listeners}
    ${FRAGMENTS['all-ended']}
    ${FRAGMENTS['main-finished']}
    ${FRAGMENTS['completion-check']}
    ${FRAGMENTS.event}
    function armOwned() {
      ending = true;
      result.completionFence = true;
      cleanupAck = true; workerDetached = true; pageDetached = true; pageClosed = true;
      workerDestroyed = true; pageDestroyed = true; pageCleanupFailed = false;
      browserCloseAttempted = true;
      cleanupDeadline = harness.now + 1800;
      pending.clear();
    }
    harness.api = {
      armOwned, completionCheck,
      closeSend() { return call('Browser.close', {}, undefined, 'browser'); },
      message(data) { onControllerSocketMessage({ data }); },
      error() { onControllerSocketError({ type: 'error' }); },
      close(fields) { onControllerSocketClose(Object.assign({ code: 1006, reason: '', wasClean: false }, fields || {})); },
      missing() { noteMissingShutdownClose(); },
      classify(state) { return classifyOwnedShutdown(state); },
      retain() { retainIncompleteChains(); },
      nativeTerminal(present) {
        const key = JSON.stringify([worker.sessionId, 'native']);
        if (present) { terminals.add(key); terminalMethods.set(key, 'Network.loadingFinished'); }
        else { terminals.delete(key); terminalMethods.delete(key); }
      },
      publication(field, value) { result.lastState[field] = value; },
      state() {
        return {
          ending, finalized, browserCloseAcknowledged, shutdownSequence, pending: pending.size,
          send: result.browserCloseSend, ack: result.browserCloseAck, error: result.websocketError,
          close: result.websocketClose, candidate: result.ownedAbnormalCloseCandidate,
          allows: result.ownedShutdownAllowsCompletion, decision: result.ownedAbnormalClose,
          duplicate: result.shutdownDuplicateError, interleaved: result.shutdownInterleaved,
          errors: result.errors.slice(), fence: result.completionFence, gate: drainWitnessGate,
          witness: result.drainWitness || null, sent: ws.sent,
          witnessStarted: drainWitnessStarted, witnessPending: drainWitnessPending,
          witnessRequestCount: drainWitnessRequestCount, requestCount: requests.size,
          firstValidationCode: result.firstValidationCode || null
        };
      },
      breakSend() { ws.send = () => { throw new Error('down'); }; },
      set(name, value) { if (name === 'workerDestroyed') workerDestroyed = value; if (name === 'fence') result.completionFence = value; if (name === 'pending') pending.set(value, { row: {} }); if (name === 'foreign') result.foreignDiscoveryEvents += value; if (name === 'errorText') result.errors.push(value); if (name === 'ending') ending = value; if (name === 'finalized') finalized = value; if (name === 'deadline') cleanupDeadline = value; },
      configureChains(spec) {
        globalThis.cfg = spec.cfg; globalThis.routes = spec.routes; globalThis.requests = spec.requests;
        globalThis.terminals = spec.terminals; globalThis.terminalMethods = spec.terminalMethods;
        globalThis.responseStatuses = spec.responseStatuses;
      }
    };
  `);
  const rawApi = harness.api;
  // Normalize data crossing the vm realm, not controller predicates or sequence state.
  const api = { ...rawApi, state() { return JSON.parse(JSON.stringify(rawApi.state())); } };
  harness.evaluate = expression => {
    assert.equal(expression.trim(), FRAGMENTS.expression.trim());
    return project(harness.snapshot);
  };
  harness.deliverEvaluate = command => {
    // A protocol peer dependency: all replies still pass production pending-ID/session validation.
    Promise.resolve().then(() => {
      if (harness.endingDuringRead) api.set('ending', true);
      const reply = harness.poison || { result: { type: 'object', value: harness.evaluate(command.params.expression) } };
      const envelope = { id: command.id, sessionId: command.sessionId, result: reply };
      if (harness.holdEvaluation) harness.heldReply = envelope;
      else api.message(JSON.stringify(envelope));
    });
  };
  api.releaseEvaluate = () => {
    assert.notEqual(harness.heldReply, null);
    const reply = harness.heldReply;
    harness.heldReply = null;
    api.message(JSON.stringify(reply));
  };
  return { context, harness, api };
}

async function handshake(api) {
  const promise = api.closeSend();
  const sent = api.state().sent;
  const id = JSON.parse(sent).id;
  api.message(JSON.stringify({ id, result: {} }));
  const mid = api.state();
  assert.equal(mid.browserCloseAcknowledged, true);
  assert.equal(mid.ack.kind, 'ack');
  assert.equal(mid.send.kind, 'send');
  assert.equal(mid.ack.at, mid.send.at);
  assert.equal(mid.ack.sequence, mid.send.sequence + 1);
  await promise;
  return mid;
}

test('Browser.close send and validated ACK stamp in order before resolve', async () => {
  const { api, harness } = bootController();
  api.armOwned();
  const mid = await handshake(api);
  assert.equal(mid.send.sequence, 1);
  assert.equal(mid.pending, 0);
  assert.equal(harness.finish.length, 0);
});

test('a failed Browser.close send does not stamp a sequence', async () => {
  const { api } = bootController();
  api.armOwned();
  api.breakSend();
  await assert.rejects(api.closeSend(), /command send failed/);
  assert.equal(api.state().send, null);
  assert.equal(api.state().shutdownSequence, 0);
});

test('equal-time post-ACK 1006 is narrow and launcher exit stays vetoed', async () => {
  const { api, harness } = bootController();
  harness.launcherExit = 0;
  api.armOwned();
  await handshake(api);
  api.error();
  const afterError = api.state();
  assert.equal(afterError.candidate, true);
  assert.equal(afterError.errors.length, 0);
  assert.equal(afterError.error.sequence, afterError.ack.sequence + 1);
  assert.equal(afterError.error.at, afterError.ack.at);
  api.close({ code: 1006, reason: '', wasClean: false });
  const done = api.state();
  assert.equal(done.decision.ok, true);
  assert.equal(done.decision.code, 'owned-post-ack-abnormal-1006');
  assert.equal(done.decision.trialPassed, false);
  assert.equal(done.decision.launcherJoin, 'independent-required');
  assert.equal(done.allows, true);
  assert.equal(done.errors.length, 0);
  assert.equal(done.close.sequence, done.error.sequence + 1);
  assert.equal(done.close.at, done.send.at);
  assert.equal(done.close.code, 1006);
  assert.equal(done.close.wasClean, false);
  assert.equal(done.close.reason, '');
});

test('equal-time error before ACK stays fatal after a later ACK', async () => {
  const { api } = bootController();
  api.armOwned();
  const promise = api.closeSend();
  api.error();
  const afterError = api.state();
  assert.equal(afterError.candidate, false);
  assert.equal(afterError.finalized, true);
  assert.deepEqual(afterError.errors, ['websocket transport error']);
  assert.equal(afterError.ack, null);
  const sent = afterError.sent;
  let settled = false;
  promise.then(() => { settled = true; }, () => { settled = true; });
  api.message(JSON.stringify({ id: JSON.parse(sent).id, result: {} }));
  await flush();
  const afterAck = api.state();
  assert.equal(afterAck.ack, null);
  assert.equal(afterAck.allows, false);
  assert.equal(afterAck.browserCloseAcknowledged, false);
  assert.equal(settled, false);
});

test('normal close without an error uses the existing ACK and deadline check', async () => {
  const { api } = bootController();
  api.armOwned();
  await handshake(api);
  api.close({ code: 1000, reason: '', wasClean: true });
  const done = api.state();
  assert.equal(done.decision, null);
  assert.equal(done.allows, true);
  assert.deepEqual(done.errors, []);
  assert.equal(api.state().close.code, 1000);
});

test('shutdown refusals stay fatal', async () => {
  async function prepared(mutate) {
    const boot = bootController();
    boot.api.armOwned();
    await handshake(boot.api);
    if (mutate) mutate(boot);
    return boot;
  }
  {
    const { api } = await prepared(boot => boot.api.set('fence', false));
    api.error();
    assert.equal(api.state().candidate, false);
    assert.deepEqual(api.state().errors, ['websocket transport error']);
  }
  {
    const { api } = await prepared(boot => boot.api.set('workerDestroyed', false));
    api.error();
    assert.equal(api.state().candidate, false);
    assert.equal(api.state().finalized, true);
  }
  {
    const { api } = await prepared(boot => boot.api.set('pending', 7));
    api.error();
    assert.equal(api.state().candidate, false);
  }
  {
    const { api } = await prepared(boot => boot.api.set('errorText', 'earlier cutoff'));
    api.error();
    assert.equal(api.state().candidate, false);
    assert.equal(api.state().errors.includes('websocket transport error'), true);
  }
  {
    const { api } = await prepared();
    api.error();
    api.error();
    const done = api.state();
    assert.equal(done.duplicate, true);
    assert.equal(done.candidate, false);
    assert.equal(done.finalized, true);
    api.close();
    assert.equal(api.state().allows, false);
    assert.equal(api.state().close.code, 1006);
    assert.equal(api.state().decision, null);
  }
  {
    const { api } = await prepared();
    api.error();
    api.message(JSON.stringify({ method: 'Runtime.executionContextsCleared', params: {}, sessionId: 'page-session' }));
    api.close();
    assert.equal(api.state().interleaved, true);
    assert.equal(api.state().decision.code, 'interleaved');
    assert.equal(api.state().allows, false);
  }
  {
    const { api } = await prepared();
    api.error();
    api.set('foreign', 1);
    api.close();
    assert.equal(api.state().decision.code, 'foreign');
  }
  {
    const { api } = await prepared();
    api.error();
    api.set('errorText', 'worker detach');
    api.close();
    assert.equal(api.state().decision.code, 'crash-or-detach');
  }
  for (const fields of [
    { code: 1005, reason: '', wasClean: false },
    { code: '1006', reason: '', wasClean: false },
    { code: 1006, reason: '', wasClean: true },
    { code: 1006, reason: 'reset', wasClean: false },
    { code: 1006, reason: 'x'.repeat(300), wasClean: false }
  ]) {
    const { api } = await prepared();
    api.error();
    api.close(fields);
    assert.equal(api.state().decision.ok, false);
    assert.equal(api.state().allows, false);
    assert.notEqual(api.state().decision.code, 'owned-post-ack-abnormal-1006');
  }
  {
    const { api, harness } = await prepared();
    api.error();
    harness.now = api.state().error.prerequisites.cleanupDeadline;
    api.close();
    assert.equal(api.state().decision.code, 'late-close');
    assert.equal(api.state().allows, false);
  }
  {
    const { api } = await prepared();
    api.error();
    api.missing();
    assert.equal(api.state().decision.code, 'missing-close');
    assert.equal(api.state().allows, false);
    assert.equal(api.state().close, null);
  }
  {
    const { api } = bootController();
    api.close();
    assert.deepEqual(api.state().errors, ['unexpected socket close']);
    assert.equal(api.state().allows, false);
  }
});

test('classifyOwnedShutdown ignores launcher exit and rejects equal sequences', () => {
  const { api } = bootController();
  const good = {
    ending: true, completionFence: true, priorFatal: false, priorValidation: false,
    cleanupComplete: true, pending: 0, browserCloseAttempted: true, browserCloseAcknowledged: true,
    sendSequence: 1, ackSequence: 2, errorSequence: 3, closeSequence: 4,
    closeAt: 100, cleanupDeadline: 1900, code: 1006, wasClean: false, reason: '',
    reasonTruncated: false, interleaved: false, duplicateError: false, crashOrDetach: false,
    foreign: false, errorsNow: 0, validationNow: false, closePresent: true, launcherExit: 0
  };
  const allowed = api.classify(good);
  assert.equal(allowed.ok, true);
  assert.equal(allowed.trialPassed, false);
  assert.equal(allowed.launcherJoin, 'independent-required');
  const vetoed = api.classify({ ...good, launcherExit: 1 });
  assert.equal(vetoed.ok, true);
  assert.equal(vetoed.trialPassed, false);
  assert.equal(api.classify({ ...good, ackSequence: 3, errorSequence: 3 }).code, 'sequence-order');
  assert.equal(api.classify({ ...good, closePresent: false }).code, 'missing-close');
});

test('incomplete chains keep manifest paths inside the existing event budget', () => {
  const { api, context } = bootController();
  const origin = ORIGIN;
  const routes = new Map([[PATH, true], ['/native/Other.lub', true]]);
  const requests = new Map([
    ['open', { url: origin + PATH, role: 'worker' }],
    ['query', { url: origin + PATH + '?token=secret', role: 'page' }],
    ['foreign', { url: 'https://elsewhere.invalid/raw', role: 'page' }],
    ['done', { url: origin + '/native/Other.lub', role: 'page' }]
  ]);
  api.configureChains({
    cfg: { fixtureOrigin: origin, requestManifest: { length: 9 } },
    routes, requests,
    terminals: new Set(['done', 'open']),
    terminalMethods: new Map([['done', 'Network.loadingFinished'], ['open', 'Network.loadingFailed']]),
    responseStatuses: new Map([['open', 404], ['done', 200]])
  });
  api.retain();
  const state = run(context, '({events:result.events.slice(), flag:result.incompleteChainWitness, bytes:eventBytes})');
  assert.equal(state.flag, true);
  assert.equal(state.events.length, 1);
  assert.equal(state.events[0].method, 'Observer.incompleteChains');
  assert.equal(state.events[0].open, 3);
  assert.equal(state.events[0].capped, true);
  assert.deepEqual(JSON.parse(JSON.stringify(state.events[0].rows)), [{ path: PATH, role: 'worker', status: 404, terminal: 'Network.loadingFailed' }]);
  assert.equal(JSON.stringify(state.events[0]).includes('token'), false);
  assert.equal(JSON.stringify(state.events[0]).includes('elsewhere'), false);
  const quiet = bootController();
  quiet.api.configureChains({
    cfg: { fixtureOrigin: origin, requestManifest: { length: 9 } },
    routes, requests: new Map([['done', requests.get('done')]]),
    terminals: new Set(['done']),
    terminalMethods: new Map([['done', 'Network.loadingFinished']]),
    responseStatuses: new Map([['done', 200]])
  });
  quiet.api.retain();
  assert.equal(run(quiet.context, 'result.events.length'), 0);
});

test('completion reads the production Worker expression once before the fence', async () => {
  const boot = bootController();
  boot.api.completionCheck();
  boot.api.completionCheck();
  await flush();
  const done = boot.api.state();
  assert.equal(boot.harness.evaluations, 1);
  assert.equal(done.pending, 0);
  assert.equal(done.fence, true);
  assert.equal(done.gate, true);
  assert.equal(done.witness.ok, true);
  assert.equal(done.witness.saved, false);
  assert.equal(done.ending, true);
  assert.deepEqual(boot.harness.finish, [null]);
});

test('no speculative evaluation precedes authenticated publication done and ACK', async () => {
  for (const field of ['done', 'publicationAttempted', 'acknowledgmentVerified', 'budgetVerified']) {
    const boot = bootController();
    boot.api.publication(field, false);
    boot.api.completionCheck();
    await flush();
    assert.equal(boot.harness.evaluations, 0, field);
    assert.equal(boot.api.state().fence, false);
  }
});

test('missing terminal retains a positive outcome but cannot complete', async () => {
  const boot = bootController();
  boot.api.nativeTerminal(false);
  boot.api.completionCheck();
  await flush();
  let state = boot.api.state();
  assert.equal(boot.harness.evaluations, 1);
  assert.equal(state.witness.code, 'uncancelled-eof');
  assert.equal(state.gate, true);
  assert.equal(state.fence, false);
  assert.equal(state.ending, false);
  boot.api.completionCheck();
  await flush();
  assert.equal(boot.harness.evaluations, 1);
  // Only the terminal fixture changes: this is not a claim of a genuine runtime terminal.
  boot.api.nativeTerminal(true);
  boot.api.completionCheck();
  state = boot.api.state();
  assert.equal(state.fence, true);
  assert.equal(state.requestCount, state.witnessRequestCount);
});

test('validated failed drain is retained and fatal even with no terminal', async () => {
  const boot = bootController();
  boot.harness.snapshot = failedSnapshot('timeout', 3);
  boot.api.nativeTerminal(false);
  boot.api.completionCheck();
  await flush();
  const state = boot.api.state();
  assert.equal(boot.harness.evaluations, 1);
  assert.deepEqual(state.witness, { ok: false, code: 'timeout', total: 3, status: 404, manifestPath: PATH, callbackOnce: true, saved: false });
  assert.equal(state.fence, false);
  assert.equal(state.gate, false);
  assert.equal(state.ending, true);
  assert.deepEqual(boot.harness.finish, ['admitted negative drain witness refused']);
});

function anotherNativeRequest(api, requestId) {
  api.message(JSON.stringify({
    method: 'Network.requestWillBeSent', sessionId: 'worker-session',
    params: { requestId, timestamp: 100, request: { url: URL_OK, method: 'GET' } }
  }));
}

test('a new request during evaluation refuses the retained stale witness', async () => {
  const boot = bootController();
  boot.harness.holdEvaluation = true;
  boot.api.completionCheck();
  await flush();
  assert.equal(boot.api.state().witnessPending, true);
  const before = boot.api.state().requestCount;
  anotherNativeRequest(boot.api, 'extra-during');
  assert.equal(boot.api.state().requestCount, before + 1);
  boot.api.releaseEvaluate();
  await flush();
  const state = boot.api.state();
  assert.equal(state.witness.ok, true);
  assert.equal(state.firstValidationCode, 'drain witness request set changed');
  assert.equal(state.fence, false);
  assert.equal(state.ending, true);
  assert.equal(boot.harness.evaluations, 1);
});

test('a new request after retrieval refuses the cached witness', async () => {
  const boot = bootController();
  boot.api.nativeTerminal(false);
  boot.api.completionCheck();
  await flush();
  assert.equal(boot.api.state().gate, true);
  assert.equal(boot.api.state().ending, false);
  anotherNativeRequest(boot.api, 'extra-after');
  await flush();
  const state = boot.api.state();
  assert.equal(state.firstValidationCode, 'drain witness request set changed');
  assert.equal(state.fence, false);
  assert.equal(state.ending, true);
  assert.equal(boot.harness.evaluations, 1);
});

test('late or malformed evaluation cannot resurrect completion', async () => {
  for (const stop of ['ending', 'finalized']) {
    const boot = bootController();
    boot.harness.holdEvaluation = true;
    boot.api.completionCheck();
    await flush();
    boot.api.set(stop, true);
    boot.api.releaseEvaluate();
    await flush();
    assert.equal(boot.api.state().fence, false);
    assert.equal(boot.harness.finish.length, 0);
    assert.equal(boot.harness.evaluations, 1);
  }
  const malformed = bootController();
  malformed.harness.poison = { result: { type: 'object', value: { ok: true } } };
  malformed.api.completionCheck();
  await flush();
  assert.equal(malformed.api.state().fence, false);
  assert.equal(malformed.api.state().witness, null);
  assert.deepEqual(malformed.harness.finish, ['admitted negative drain witness refused']);
});

const postAckMessages = [
  { method: 'Inspector.detached', sessionId: 'page-session', params: { reason: 'controlled-unexpected' } },
  { method: 'Target.targetCreated', params: { targetInfo: { targetId: 'foreign-target', type: 'page' } } }
];

test('ACK then Inspector or foreign message vetoes subsequent error and 1006', async () => {
  for (const message of postAckMessages) {
    const { api } = bootController();
    api.armOwned();
    await handshake(api);
    assert.equal(api.state().interleaved, false);
    api.message(JSON.stringify(message));
    assert.equal(api.state().interleaved, true);
    api.error();
    const prior = api.state();
    assert.equal(prior.candidate, false);
    assert.equal(prior.finalized, true);
    assert.equal(prior.allows, false);
    assert.deepEqual(prior.errors, ['websocket transport error']);
    api.close();
    const done = api.state();
    assert.equal(done.close.code, 1006);
    assert.equal(done.close.wasClean, false);
    assert.equal(done.allows, false);
    assert.equal(done.ack.sequence < done.error.sequence, true);
    assert.equal(done.error.sequence < done.close.sequence, true);
  }
});

test('no-error close retains the original ACK/deadline behavior', async () => {
  for (const message of postAckMessages) {
    const { api } = bootController();
    api.armOwned();
    await handshake(api);
    api.message(JSON.stringify(message));
    api.close({ code: 1000, reason: '', wasClean: true });
    assert.equal(api.state().interleaved, true);
    assert.equal(api.state().allows, true);
    assert.equal(api.state().errors.length, 0);
  }
});

test('permitted foreign discovery before ACK is not a new global ban', async () => {
  const { api } = bootController();
  api.armOwned();
  api.message(JSON.stringify(postAckMessages[1]));
  assert.equal(api.state().interleaved, false);
  await handshake(api);
  api.error();
  api.close();
  assert.equal(api.state().decision.ok, true);
  assert.equal(api.state().allows, true);
});
