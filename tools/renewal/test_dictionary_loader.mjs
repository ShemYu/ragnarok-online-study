// T05.005: Node built-in tests for dictionary_loader.mjs and its fixture builder.
//
// Everything is an authored double over tiny authored bytes: an API 1 scope,
// fetch/Response/stream doubles, a scripted core double, a status double and,
// for the unchanged core integration, a minimal MutationObserver stand-in.
// Node's WebCrypto/TextDecoder/JSON.parse are used as-is. No stock module,
// browser, listener or network is used, and the production dictionary is
// never read: D09 (native full body) is the root's browser run and is
// reported here as NOT RUN, never as a pass.
//
//   node --test tools/renewal/test_dictionary_loader.mjs

import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createHash, webcrypto } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath, pathToFileURL } from 'node:url';

import initializeNpcCore from './npc_plaintext_adapter.mjs';
import initialize, { createInitializer, createOwnedStatus, ERROR_CODES, STATUS_TEXT, jsonMediaType } from './dictionary_loader.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const loaderPath = path.join(here, 'dictionary_loader.mjs');
const corePath = path.join(here, 'npc_plaintext_adapter.mjs');
const builder = path.join(here, 'dictionary_loader_fixture.py');
const CORE_PIN = { bytes: 14236, sha256: '0dc77140f921925f7079dfdeaf6f674931f66a726f97b41bfab5f6b8e7f0089c' };
const DICTIONARY_BYTES = 19706353;
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const settle = () => sleep(0);
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const encode = text => new TextEncoder().encode(text);
const pinOf = bytes => ({ bytes: bytes.length, sha256: sha(bytes) });

const unhandled = [];
process.on('unhandledRejection', error => unhandled.push(error));

const TINY = encode(JSON.stringify({ Hello: '哈囉', Goodbye: '再會' }));
const ORIGIN = 'http://127.0.0.1:9';
const MODULE = `${ORIGIN}/case/x/dictionary_loader.mjs`;
const DICT = `${ORIGIN}/case/x/dict.json`;
const PAGE = `${ORIGIN}/pages/run/index.html?mode=a#b`;

// --- doubles -----------------------------------------------------------------

function scope({ dead = false, cleanupThrows = false } = {}) {
    const cleanups = [];
    let disposed = dead;
    const counts = { on: 0, cleanup: 0 };
    const api = {
        version: 1,
        on() { counts.on++; if (disposed) throw new Error('disposed'); return () => {}; },
        cleanup(fn) {
            counts.cleanup++;
            if (cleanupThrows) throw new Error('cleanup registration');
            if (disposed) { fn(); return; }
            cleanups.push(fn);
        },
    };
    return { api, counts, dispose() { if (disposed) return; disposed = true; for (const fn of cleanups.splice(0).reverse()) fn(); } };
}

function coreDouble(behaviour = 'follow', { onInit } = {}) {
    const log = { inits: 0, received: [], rejected: 0, disposed: 0, diagnostics: 0 };
    function initializeCore(parameters, api) {
        log.inits++;
        if (onInit) onInit();
        if (behaviour === 'throw-init') throw new Error('core init');
        if (behaviour === 'bad-handle') return { dispose() { log.disposed++; } };
        let state = 'loading';
        let ticks = 0;
        api.cleanup(() => { state = 'disposed'; });
        Promise.prototype.then.call(parameters.dictionaryReady, value => {
            log.received.push(value);
            if (state === 'loading' && behaviour === 'follow') state = 'ready';
            if (state === 'loading' && behaviour === 'fail-on-ready') state = 'failed';
        }, () => { log.rejected++; if (state === 'loading') state = 'failed'; });
        return Object.freeze({
            dispose() { log.disposed++; state = 'disposed'; },
            diagnostics() {
                log.diagnostics++;
                if (behaviour === 'throw-diagnostics') throw new Error('diag');
                if (behaviour === 'malformed') return 'ready';
                const after = /^after:(\d+)$/.exec(behaviour);
                if (after && state === 'loading' && log.received.length && ++ticks >= Number(after[1])) state = 'ready';
                return Object.freeze({ state });
            },
        });
    }
    return { initializeCore, log };
}

function body(steps, { stuckCancel = false } = {}) {
    const log = { reads: 0, cancels: 0, pending: [] };
    let index = 0;
    const cancel = () => { log.cancels++; return stuckCancel ? new Promise(() => {}) : Promise.resolve(); };
    const reader = {
        read() {
            log.reads++;
            const step = steps[index++] || { done: true };
            if (step.reject) return Promise.reject(new Error('read'));
            if (step.pending) return new Promise((resolve, reject) => log.pending.push({ resolve, reject }));
            if (step.malformed) return Promise.resolve(42);
            if (step.done) return Promise.resolve({ done: true, value: undefined });
            return Promise.resolve({ done: false, value: 'chunk' in step ? step.chunk : step.value });
        },
        cancel,
    };
    return { log, stream: { getReader() { return reader; }, cancel } };
}

const chunks = (bytes, ...sizes) => {
    const out = [];
    let at = 0;
    for (const size of sizes) { if (at < bytes.length) out.push({ chunk: bytes.slice(at, at + size) }); at += size; }
    if (at < bytes.length) out.push({ chunk: bytes.slice(at) });
    return out;
};

function response({ status = 200, redirected = false, url = DICT, type = 'application/json; charset=utf-8', contentLength = null, stream = null } = {}) {
    const log = { bypass: 0 };
    const headers = new Map([['content-type', type]]);
    if (contentLength !== null) headers.set('content-length', String(contentLength));
    const bypass = () => { log.bypass++; throw new Error('bypass'); };
    return { log, value: { status, redirected, url, body: stream, headers: { get: name => headers.get(name.toLowerCase()) ?? null },
        text: bypass, json: bypass, arrayBuffer: bypass, blob: bypass, clone: bypass } };
}

function statusDouble({ throwOn = null, disposeThrows = false } = {}) {
    const log = { created: 0, updates: [], disposed: 0 };
    const factory = () => {
        log.created++;
        if (throwOn === 'create') throw new Error('status create');
        return {
            update(state, code) { log.updates.push(code ? `${state}:${code}` : state); if (throwOn === state) throw new Error('status update'); },
            dispose() { log.disposed++; if (disposeThrows) throw new Error('status dispose'); },
        };
    };
    return { factory, log };
}

// One configured loader run over doubles; every dependency is recorded.
function harness({ bytes = TINY, pin = pinOf(bytes), steps, res, fetchImpl, core = 'follow', status = {}, timeoutMs = 2000, digestImpl, parseImpl, api } = {}) {
    const order = [];
    const fetches = [];
    const parses = [];
    const digests = [];
    const doubleBody = res ? null : body(steps || chunks(bytes, 3, 5));
    const doubleResponse = res || response({ stream: doubleBody.stream });
    const coreD = typeof core === 'string' ? coreDouble(core) : core;
    const statusD = statusDouble(status);
    const scopeD = api || scope();
    const init = createInitializer({
        initializeCore: coreD.initializeCore, moduleURL: MODULE, pageURL: PAGE, expected: pin, timeoutMs,
        fetchImpl: fetchImpl || ((url, options) => { fetches.push({ url, options }); order.push('fetch'); return Promise.resolve(doubleResponse.value); }),
        digestImpl: digestImpl || (b => { order.push('digest'); digests.push(b); return webcrypto.subtle.digest('SHA-256', b); }),
        parseImpl: parseImpl || (text => { order.push('parse'); const value = JSON.parse(text); parses.push(value); return value; }),
        statusFactory: statusD.factory,
    });
    const handle = init({ url: 'http://evil.invalid/dict.json', expected: { bytes: 1 }, timeoutMs: 1 }, scopeD.api);
    return { handle, order, fetches, parses, digests, body: doubleBody, res: doubleResponse, core: coreD, status: statusD, scope: scopeD };
}

async function outcome(handle) {
    try { return await handle.ready; } catch (error) { return error.code; }
}

const PRIMITIVE_KEYS = 'state,phase,errorCode,receivedBytes,expectedBytes,coreState,requestMs,readMs,digestMs,decodeMs,parseMs,activateMs,totalMs';

// --- D01 synchronous lifecycle -------------------------------------------------

test('D01 gates reject synchronously before any work', () => {
    const core = coreDouble();
    const status = statusDouble();
    let fetched = 0;
    const good = { initializeCore: core.initializeCore, moduleURL: MODULE, pageURL: PAGE, expected: pinOf(TINY), timeoutMs: 100,
        fetchImpl: () => { fetched++; }, digestImpl: () => {}, parseImpl: JSON.parse, statusFactory: status.factory };
    const bad = {
        'no options': [undefined],
        'core missing': [{ ...good, initializeCore: 1 }],
        'parse missing': [{ ...good, parseImpl: undefined }],
        'status missing': [{ ...good, statusFactory: {} }],
        'bytes 0': [{ ...good, expected: { bytes: 0, sha256: sha(TINY) } }],
        'bytes unsafe': [{ ...good, expected: { bytes: 2 ** 53, sha256: sha(TINY) } }],
        'sha short': [{ ...good, expected: { bytes: 3, sha256: 'ab' } }],
        'sha upper': [{ ...good, expected: { bytes: 3, sha256: sha(TINY).toUpperCase() } }],
        'timeout 0': [{ ...good, timeoutMs: 0 }],
        'timeout NaN': [{ ...good, timeoutMs: NaN }],
        'timeout Infinity': [{ ...good, timeoutMs: Infinity }],
        'relative module': [{ ...good, moduleURL: '/case/x/m.mjs' }],
        'module not string': [{ ...good, moduleURL: new URL(MODULE) }],
        'file module': [{ ...good, moduleURL: 'file:///tmp/m.mjs' }],
        'module query': [{ ...good, moduleURL: MODULE + '?v=2' }],
        'module fragment': [{ ...good, moduleURL: MODULE + '#x' }],
        'module credentials': [{ ...good, moduleURL: 'http://u:p@127.0.0.1:9/m.mjs' }],
        'cross origin': [{ ...good, moduleURL: 'http://127.0.0.2:9/m.mjs' }],
        'cross port': [{ ...good, moduleURL: 'http://127.0.0.1:10/m.mjs' }],
    };
    for (const [label, args] of Object.entries(bad)) assert.throws(() => createInitializer(...args), TypeError, label);
    const init = createInitializer(good);
    for (const api of [null, {}, { version: '1', on() {}, cleanup() {} }, { version: 1, cleanup() {} }, { version: 1, on() {} }]) {
        assert.throws(() => init(null, api), TypeError);
    }
    const saved = globalThis.TextDecoder;
    globalThis.TextDecoder = class { constructor() { this.fatal = false; } };
    try { assert.throws(() => init(null, scope().api), /fatal UTF-8/); } finally { globalThis.TextDecoder = saved; }
    assert.equal(fetched + core.log.inits + status.log.created, 0);
    // Page query/fragment are allowed; https works too.
    assert.equal(typeof createInitializer({ ...good, pageURL: PAGE }), 'function');
    assert.equal(typeof createInitializer({ ...good, moduleURL: 'https://a.test/m.mjs', pageURL: 'https://a.test/p?q#f' }), 'function');
    // The contract gives timeout a finite integer, unlike safe-integer bytes.
    // Factory construction starts no timer, including for this large value.
    assert.equal(typeof createInitializer({ ...good, timeoutMs: Number.MAX_SAFE_INTEGER + 1 }), 'function');
});

test('D01 returns a frozen non-thenable handle synchronously while loading', async () => {
    let release;
    const run = harness({ fetchImpl: () => new Promise(resolve => { release = resolve; }) });
    assert.ok(Object.isFrozen(run.handle));
    assert.deepEqual(Object.keys(run.handle).sort(), ['diagnostics', 'dispose', 'ready']);
    assert.equal('then' in run.handle, false);
    assert.ok(run.handle.ready instanceof Promise);
    assert.equal(run.handle.diagnostics().state, 'loading');
    assert.deepEqual(run.status.log.updates, ['loading']);
    // A next "plugin" runs now, before the dictionary resolves.
    const sentinel = run.handle.diagnostics().state;
    assert.equal(sentinel, 'loading');
    release(response({ stream: body(chunks(TINY, 4)).stream }).value);
    assert.equal(await run.handle.ready, 'ready');
    run.handle.dispose();
});

test('D01 already-dead scope: disposed handle, no core/status/fetch/timer', async () => {
    const run = harness({ api: scope({ dead: true }) });
    assert.equal(run.handle.diagnostics().state, 'disposed');
    assert.equal(await outcome(run.handle), 'DISPOSED');
    await sleep(10);
    assert.equal(run.fetches.length + run.core.log.inits + run.status.log.created, 0);
    assert.equal(run.scope.counts.on, 0);
});

test('D01 reentrant disposal during core init or status creation stops further work', async () => {
    let target;
    const core = coreDouble('follow', { onInit: () => target.dispose() });
    const lazy = scope();
    target = lazy;
    const run = harness({ core, api: lazy });
    assert.equal(run.handle.diagnostics().state, 'disposed');
    assert.equal(run.core.log.disposed, 1, 'late core handle disposed');
    assert.equal(run.status.log.created + run.fetches.length, 0);
    assert.equal(await outcome(run.handle), 'DISPOSED');
});

test('D01 api.cleanup throwing fails API before any core/status/fetch', async () => {
    const run = harness({ api: scope({ cleanupThrows: true }) });
    assert.equal(await outcome(run.handle), 'API');
    assert.equal(run.core.log.inits + run.status.log.created + run.fetches.length, 0);
});

test('D01 later adoption, double dispose and late rejection are harmless', async () => {
    const run = harness();
    assert.equal(await run.handle.ready, 'ready');
    run.scope.dispose();
    run.handle.dispose();
    run.handle.dispose();
    assert.equal(run.handle.diagnostics().state, 'disposed');
    assert.equal(run.status.log.disposed, 1);
    let reject;
    const late = harness({ fetchImpl: () => new Promise((_, r) => { reject = r; }) });
    late.handle.dispose();
    reject(new Error('late'));
    assert.equal(await outcome(late.handle), 'DISPOSED');
    await settle();
});

// --- D02 module-relative request ------------------------------------------------

test('D02 one fixed module-relative GET with fixed options; parameters ignored; no retry', async () => {
    const run = harness();
    assert.equal(await run.handle.ready, 'ready');
    assert.equal(run.fetches.length, 1);
    const { url, options } = run.fetches[0];
    assert.equal(url, DICT);
    assert.deepEqual({ ...options, signal: undefined }, { method: 'GET', mode: 'same-origin', credentials: 'omit', redirect: 'error', cache: 'no-store', signal: undefined });
    assert.ok(options.signal instanceof AbortSignal);
    run.handle.dispose();
    const miss = harness({ res: response({ status: 404, stream: body([]).stream }) });
    assert.equal(await outcome(miss.handle), 'HTTP_STATUS');
    assert.equal(miss.fetches.length, 1, 'no retry/fallback');
    assert.ok(miss.fetches[0].options.signal.aborted);
});

test('D02 production default: import starts nothing; unsupported context throws before work', () => {
    const script = `
        const touched = [];
        globalThis.fetch = () => { touched.push('fetch'); throw new Error('no'); };
        const realTimeout = globalThis.setTimeout;
        globalThis.setTimeout = (...a) => { touched.push('timer'); return realTimeout(...a); };
        const mod = await import(${JSON.stringify(pathToFileURL(loaderPath).href)});
        const afterImport = touched.length;
        const api = { version: 1, on() { touched.push('on'); }, cleanup() { touched.push('cleanup'); } };
        const names = [];
        try { mod.default(null, api); } catch (e) { names.push(e.constructor.name + ':' + /document/.test(e.message)); }
        globalThis.document = { body: {}, createElement() { touched.push('dom'); } };
        globalThis.MutationObserver = class {};
        globalThis.location = { href: 'http://127.0.0.1:9/pages/run/index.html' };
        try { mod.default(null, api); } catch (e) { names.push(e.constructor.name + ':' + /HTTP/.test(e.message)); }
        console.log(JSON.stringify({ afterImport, touched, names }));
    `;
    const result = spawnSync(process.execPath, ['--input-type=module', '-e', script], { encoding: 'utf8' });
    assert.equal(result.status, 0, result.stderr);
    assert.deepEqual(JSON.parse(result.stdout), { afterImport: 0, touched: [], names: ['TypeError:true', 'TypeError:true'] });
});

// --- D03 verified bounded pipeline ----------------------------------------------

test('D03 chunked exact body: one sized buffer, SHA before one parse, same object to core', async () => {
    for (const contentLength of [null, 999999999, 1, TINY.length]) {
        const steps = chunks(TINY, 1, 2, 4, 8);
        const b = body(steps);
        const res = response({ contentLength, stream: b.stream });
        const run = harness({ res });
        assert.equal(await run.handle.ready, 'ready', String(contentLength));
        assert.deepEqual(run.order, ['fetch', 'digest', 'parse']);
        assert.equal(run.digests.length, 1);
        assert.equal(run.digests[0].byteLength, TINY.length);
        assert.equal(run.digests[0].buffer.byteLength, TINY.length, 'one exactly sized backing buffer');
        assert.equal(run.parses.length, 1);
        assert.equal(run.core.log.received[0], run.parses[0], 'identical borrowed object');
        assert.equal(run.res.log.bypass, 0);
        assert.equal(b.log.reads, steps.length + 1);
        const d = run.handle.diagnostics();
        assert.equal(d.receivedBytes, TINY.length);
        assert.equal(d.coreState, 'ready');
        assert.equal(d.phase, 'ready');
        run.handle.dispose();
    }
});

test('D03 unchanged core integration: loader ready only when the real core is ready', async () => {
    const saved = globalThis.MutationObserver;
    globalThis.MutationObserver = class { observe() {} disconnect() {} };
    try {
        const b = body(chunks(TINY, 5));
        const s = statusDouble();
        const api = scope();
        const handle = createInitializer({
            initializeCore: initializeNpcCore, moduleURL: MODULE, pageURL: PAGE, expected: pinOf(TINY), timeoutMs: 2000,
            fetchImpl: () => Promise.resolve(response({ stream: b.stream }).value),
            digestImpl: bytes => webcrypto.subtle.digest('SHA-256', bytes), parseImpl: JSON.parse, statusFactory: s.factory,
        })(null, api.api);
        assert.equal(api.counts.on, 2, 'core subscribed through the same API');
        assert.equal(handle.diagnostics().coreState, 'loading');
        assert.equal(await handle.ready, 'ready');
        assert.equal(handle.diagnostics().coreState, 'ready');
        assert.deepEqual(s.log.updates, ['loading', 'ready']);
        handle.dispose();
        assert.equal(handle.diagnostics().coreState, 'disposed');
    } finally {
        globalThis.MutationObserver = saved;
    }
});

test('D03 media type accepts only application/json with optional charset=utf-8', () => {
    for (const ok of ['application/json', 'Application/JSON', 'application/json;charset=utf-8', 'application/json; charset=UTF-8', 'application/json; Charset="utf-8"']) {
        assert.equal(jsonMediaType(ok), true, ok);
    }
    for (const bad of [null, '', 'text/json', 'application/json; charset=iso-8859-1', 'application/json; charset=utf8', 'application/json;', 'application/json; charset=utf-8; x=1',
        'application/json, text/plain', 'application/json; foo=utf-8', 'application/jsonx', 'application/json; charset="utf-8']) {
        assert.equal(jsonMediaType(bad), false, String(bad));
    }
});

// --- D04 transport/body/identity failures ----------------------------------------

test('D04 every transport/body/identity failure: code, failed status, no parse/handoff, cleanup', async () => {
    const wrong = { bytes: TINY.length, sha256: sha(encode('other')) };
    const cases = [
        ['fetch throws', { fetchImpl: () => { throw new Error('x'); } }, 'FETCH'],
        ['fetch rejects', { fetchImpl: () => Promise.reject(new TypeError('network')) }, 'FETCH'],
        ['not a response', { fetchImpl: () => Promise.resolve(null) }, 'FETCH'],
        ['404', { res: response({ status: 404, stream: body([]).stream }) }, 'HTTP_STATUS'],
        ['204', { res: response({ status: 204, stream: body([]).stream }) }, 'HTTP_STATUS'],
        ['redirected', { res: response({ redirected: true, stream: body([]).stream }) }, 'REDIRECT'],
        ['redirected null', { res: response({ redirected: null, stream: body([]).stream }) }, 'REDIRECT'],
        ['final URL', { res: response({ url: `${ORIGIN}/elsewhere/dict.json`, stream: body([]).stream }) }, 'REDIRECT'],
        ['MIME text/plain', { res: response({ type: 'text/plain', stream: body([]).stream }) }, 'MEDIA_TYPE'],
        ['MIME charset', { res: response({ type: 'application/json; charset=latin1', stream: body([]).stream }) }, 'MEDIA_TYPE'],
        ['MIME missing', { res: response({ type: null, stream: body([]).stream }) }, 'MEDIA_TYPE'],
        ['body null', { res: response({ stream: null }) }, 'BODY'],
        ['read rejects', { steps: [{ reject: true }] }, 'READ'],
        ['read malformed', { steps: [{ malformed: true }] }, 'READ'],
        ['zero chunk', { steps: [{ chunk: new Uint8Array(0) }] }, 'CHUNK'],
        ['string chunk', { steps: [{ value: 'abc' }] }, 'CHUNK'],
        ['Buffer chunk', { steps: [{ value: Buffer.from(TINY) }] }, 'CHUNK'],
        ['DataView chunk', { steps: [{ value: new DataView(TINY.buffer.slice(0)) }] }, 'CHUNK'],
        ['truncated', { steps: chunks(TINY.slice(0, 6)) }, 'TRUNCATED'],
        ['oversize single', { steps: [{ chunk: new Uint8Array([...TINY, 32]) }] }, 'OVERSIZE'],
        ['oversize tail', { steps: [{ chunk: TINY }, { chunk: new Uint8Array([32]) }] }, 'OVERSIZE'],
        ['digest throws', { digestImpl: () => { throw new Error('d'); } }, 'DIGEST'],
        ['digest rejects', { digestImpl: () => Promise.reject(new Error('d')) }, 'DIGEST'],
        ['digest short', { digestImpl: () => Promise.resolve(new ArrayBuffer(31)) }, 'DIGEST'],
        ['digest typed array', { digestImpl: () => Promise.resolve(new Uint8Array(32)) }, 'DIGEST'],
        ['wrong SHA', { pin: wrong }, 'IDENTITY'],
    ];
    for (const [label, options, code] of cases) {
        const run = harness(options);
        assert.equal(await outcome(run.handle), code, label);
        await settle();
        const d = run.handle.diagnostics();
        assert.equal(d.state, 'failed', label);
        assert.equal(d.errorCode, code, label);
        assert.equal(run.parses.length, 0, `${label}: no parse`);
        assert.equal(run.core.log.received.length, 0, `${label}: no handoff`);
        assert.equal(run.core.log.rejected, 1, `${label}: core dictionary rejected`);
        assert.equal(run.status.log.updates.at(-1), `failed:${code}`, label);
        if (run.body && !['truncated', 'read rejects'].includes(label) && code !== 'FETCH' && code !== 'DIGEST' && code !== 'IDENTITY') {
            assert.ok(run.body.log.cancels >= 1, `${label}: body cancelled`);
        }
        if (run.fetches[0]) assert.ok(run.fetches[0].options.signal.aborted, `${label}: aborted`);
        assert.equal(run.res.log.bypass, 0);
        run.handle.dispose();
        assert.equal(run.status.log.disposed, 1);
    }
});

// --- D05 decode/parse/container ---------------------------------------------------

test('D05 fatal UTF-8 before parse; one parse; container gate only', async () => {
    const badUtf8 = new Uint8Array([0x7b, 0x22, 0x61, 0x22, 0x3a, 0x22, 0xff, 0x22, 0x7d]);
    const cases = [
        [badUtf8, 'DECODE', 0], [encode('{"a":'), 'PARSE', 1], [encode('42'), 'CONTAINER', 1],
        [encode('[1]'), 'CONTAINER', 1], [encode('null'), 'CONTAINER', 1], [encode('"s"'), 'CONTAINER', 1],
    ];
    for (const [bytes, code, parseCalls] of cases) {
        let calls = 0;
        const run = harness({ bytes, parseImpl: text => { calls++; return JSON.parse(text); } });
        assert.equal(await outcome(run.handle), code);
        assert.equal(calls, parseCalls, code);
        assert.equal(run.core.log.received.length, 0);
        run.handle.dispose();
    }
    const unsafe = encode('{"__proto__":{"x":1},"constructor":"建構","Bad":42}');
    const run = harness({ bytes: unsafe });
    assert.equal(await run.handle.ready, 'ready', 'entries are the core\'s concern');
    assert.equal(({}).x, undefined);
    assert.ok(Object.hasOwn(run.parses[0], '__proto__'));
    run.handle.dispose();
    const nullProto = harness({ parseImpl: text => Object.assign(Object.create(null), JSON.parse(text)) });
    assert.equal(await nullProto.handle.ready, 'ready');
    nullProto.handle.dispose();
    const classy = harness({ parseImpl: () => new Map() });
    assert.equal(await outcome(classy.handle), 'CONTAINER');
});

test('D05 loader source never enumerates, clones or freezes the dictionary', () => {
    const source = fs.readFileSync(loaderPath, 'utf8').replace(/\/\/.*$/gm, '');
    for (const forbidden of [/Object\.(?:keys|entries|values|freeze)\(\s*value/, /for\s*\(\s*(?:const|let)\s+\w+\s+in\b/, /structuredClone/, /JSON\.stringify/,
        /new Map\(/, /\.text\(\)|\.json\(\)|\.arrayBuffer\(\)/]) {
        assert.equal(forbidden.test(source), false, String(forbidden));
    }
    assert.equal((source.match(/new TextDecoder\('utf-8', \{ fatal: true \}\)\.decode/g) || []).length, 1);
    assert.equal((source.match(/parseImpl\(text\)/g) || []).length, 1);
    assert.equal((source.match(/new Uint8Array\(pin\.bytes\)/g) || []).length, 1);
});

// --- D06 deadline/dispose/late outcomes ---------------------------------------------

test('D06 total deadline over pending fetch, read and digest; late outcomes cannot revive', async () => {
    let lateFetch;
    const a2 = [];
    const a = harness({ timeoutMs: 40, fetchImpl: (url, options) => new Promise(resolve => { lateFetch = resolve; a2.push(options); }) });
    assert.equal(await outcome(a.handle), 'TIMEOUT');
    assert.equal(a.handle.diagnostics().phase, 'request');
    assert.ok(a2[0].signal.aborted);
    lateFetch(response({ stream: body(chunks(TINY)).stream }).value);
    await sleep(10);
    assert.equal(a.handle.diagnostics().state, 'failed');
    assert.deepEqual(a.status.log.updates, ['loading', 'failed:TIMEOUT']);

    const b = harness({ timeoutMs: 40, steps: [{ chunk: TINY.slice(0, 2) }, { pending: true }] });
    assert.equal(await outcome(b.handle), 'TIMEOUT');
    assert.equal(b.handle.diagnostics().phase, 'read');
    assert.ok(b.body.log.cancels >= 1);
    b.body.log.pending[0].resolve({ done: false, value: TINY.slice(2) });
    await sleep(5);
    assert.equal(b.handle.diagnostics().receivedBytes, 2);

    let lateDigest;
    const c = harness({ timeoutMs: 40, digestImpl: () => new Promise(resolve => { lateDigest = resolve; }) });
    assert.equal(await outcome(c.handle), 'TIMEOUT');
    assert.equal(c.handle.diagnostics().phase, 'digest');
    lateDigest(await webcrypto.subtle.digest('SHA-256', TINY));
    await sleep(5);
    assert.equal(c.parses.length, 0);
    assert.equal(c.core.log.received.length, 0);
    for (const run of [a, b, c]) {
        const d = run.handle.diagnostics();
        assert.ok(d.totalMs >= 40, 'real elapsed at least the deadline');
        run.handle.dispose();
    }
});

test('D06 dispose during pending stages with stuck cancel is synchronous and terminal', async () => {
    const run = harness({ steps: [{ chunk: TINY.slice(0, 3) }, { pending: true }] });
    await sleep(5);
    run.handle.dispose();
    assert.ok(run.body.log.cancels >= 1, 'owned reader cancelled');
    const stuck = body([{ chunk: TINY.slice(0, 3) }, { pending: true }], { stuckCancel: true });
    const s = harness({ res: response({ stream: stuck.stream }) });
    await sleep(5);
    s.handle.dispose();
    assert.equal(s.handle.diagnostics().state, 'disposed');
    assert.ok(stuck.log.cancels >= 1);
    assert.equal(await outcome(s.handle), 'DISPOSED');
    stuck.log.pending[0].reject(new Error('late read'));
    await sleep(5);
    assert.equal(s.handle.diagnostics().state, 'disposed');
    assert.equal(s.status.log.updates.length, 1, 'no status after dispose');
    assert.equal(s.status.log.disposed, 1);
});

test('D06 activation: stuck/failed/throwing/malformed core fails CORE within finite checkpoints', async () => {
    for (const behaviour of ['stuck', 'fail-on-ready', 'throw-diagnostics', 'malformed']) {
        const run = harness({ core: behaviour });
        assert.equal(await outcome(run.handle), 'CORE', behaviour);
        const d = run.handle.diagnostics();
        assert.equal(d.phase, 'activate');
        assert.ok(Number.isFinite(d.activateMs));
        assert.ok(run.core.log.disposed >= 1, `${behaviour}: core disposed after handoff`);
        if (behaviour === 'stuck') assert.ok(run.core.log.diagnostics <= 8 + 2, 'finite checkpoints');
    }
    for (const behaviour of ['throw-init', 'bad-handle']) {
        const run = harness({ core: behaviour });
        assert.equal(await outcome(run.handle), 'CORE', behaviour);
        assert.equal(run.fetches.length, 0);
        assert.equal(run.status.log.created, 0);
    }
    const slow = harness({ core: 'after:3' });
    assert.equal(await slow.handle.ready, 'ready');
    slow.handle.dispose();
});

test('D06 synchronous parse is not preempted; the deadline is checked after it', async () => {
    const run = harness({ timeoutMs: 30, parseImpl: text => { const end = performance.now() + 60; while (performance.now() < end) { /* busy */ } return JSON.parse(text); } });
    assert.equal(await outcome(run.handle), 'TIMEOUT');
    const d = run.handle.diagnostics();
    assert.equal(d.phase, 'parse');
    assert.ok(d.parseMs >= 60);
    assert.equal(run.core.log.received.length, 0);
});

test('D06 dispose after ready keeps the historical ready; diagnostics is authoritative', async () => {
    const run = harness();
    assert.equal(await run.handle.ready, 'ready');
    const total = run.handle.diagnostics().totalMs;
    run.handle.dispose();
    assert.equal(await run.handle.ready, 'ready');
    const d = run.handle.diagnostics();
    assert.equal(d.state, 'disposed');
    assert.equal(d.coreState, 'disposed');
    assert.equal(d.totalMs, total);
    assert.equal(d.errorCode, null);
});

// --- D07 status/diagnostics -------------------------------------------------------

test('D07 status: loading until true core ready; failure persists; disposal terminal', async () => {
    const run = harness({ core: 'after:2' });
    assert.deepEqual(run.status.log.updates, ['loading']);
    assert.equal(await run.handle.ready, 'ready');
    assert.deepEqual(run.status.log.updates, ['loading', 'ready']);
    run.handle.dispose();
    run.handle.dispose();
    assert.equal(run.status.log.disposed, 1);
    const failed = harness({ pin: { bytes: TINY.length, sha256: '0'.repeat(64) } });
    await outcome(failed.handle);
    await sleep(5);
    assert.deepEqual(failed.status.log.updates, ['loading', 'failed:IDENTITY']);
    failed.handle.dispose();
    assert.deepEqual(failed.status.log.updates, ['loading', 'failed:IDENTITY']);
});

test('D07 status failures: create/loading/ready update and dispose errors', async () => {
    for (const throwOn of ['create', 'loading']) {
        const run = harness({ status: { throwOn } });
        assert.equal(await outcome(run.handle), 'STATUS', throwOn);
        assert.equal(run.fetches.length, 0, `${throwOn}: no request`);
    }
    const ready = harness({ status: { throwOn: 'ready' } });
    assert.equal(await outcome(ready.handle), 'STATUS');
    assert.ok(ready.core.log.disposed >= 1);
    const bad = createInitializer({ initializeCore: coreDouble().initializeCore, moduleURL: MODULE, pageURL: PAGE, expected: pinOf(TINY), timeoutMs: 100,
        fetchImpl: () => Promise.reject(new Error('x')), digestImpl: () => {}, parseImpl: JSON.parse, statusFactory: () => ({ update() {} }) })(null, scope().api);
    assert.equal(await outcome(bad), 'STATUS');
    const disposing = harness({ status: { disposeThrows: true } });
    await disposing.handle.ready;
    disposing.handle.dispose();
    assert.equal(disposing.handle.diagnostics().state, 'disposed');
    assert.equal(disposing.handle.diagnostics().errorCode, 'DISPOSE');
    assert.equal(disposing.status.log.created, 1, 'never recreated');
});

test('D07 diagnostics: fresh frozen primitive snapshots with documented fields and timings', async () => {
    const run = harness();
    const first = run.handle.diagnostics();
    assert.equal(Object.keys(first).join(','), PRIMITIVE_KEYS);
    assert.ok(Object.isFrozen(first));
    assert.equal(first.totalMs, null);
    assert.equal(first.expectedBytes, TINY.length);
    await run.handle.ready;
    const d = run.handle.diagnostics();
    assert.notEqual(d, run.handle.diagnostics());
    for (const value of Object.values(d)) assert.ok(value === null || typeof value === 'string' || typeof value === 'number');
    for (const key of ['requestMs', 'readMs', 'digestMs', 'decodeMs', 'parseMs', 'activateMs', 'totalMs']) assert.ok(Number.isFinite(d[key]) && d[key] >= 0, key);
    const failed = harness({ steps: [{ reject: true }] });
    await outcome(failed.handle);
    const f = failed.handle.diagnostics();
    assert.ok(Number.isFinite(f.requestMs) && Number.isFinite(f.readMs));
    assert.equal(f.digestMs, null);
    assert.equal(f.parseMs, null);
    assert.equal(JSON.stringify(f).includes('127.0.0.1'), false, 'no URL');
    assert.equal(ERROR_CODES.length, new Set(ERROR_CODES).size);
    assert.ok(Object.isFrozen(ERROR_CODES));
});

test('D07 owned status node: role/aria/marker, Chinese labels, removes only itself', () => {
    const made = [];
    const node = () => {
        const n = { attrs: {}, children: [], parentNode: null, style: {},
            setAttribute(k, v) { this.attrs[k] = String(v); }, appendChild(c) { c.parentNode = this; this.children.push(c); return c; },
            removeChild(c) { this.children.splice(this.children.indexOf(c), 1); c.parentNode = null; } };
        made.push(n);
        return n;
    };
    const documentRef = { body: node(), createElement: () => node(), createTextNode: data => ({ data }) };
    const other = node();
    documentRef.body.appendChild(other);
    const s = createOwnedStatus(documentRef);
    const owned = documentRef.body.children[1];
    assert.equal(owned.attrs.role, 'status');
    assert.equal(owned.attrs['aria-live'], 'polite');
    assert.ok('data-t05-dictionary-loader' in owned.attrs);
    s.update('loading', null);
    assert.equal(owned.children[0].data, '繁體中文 NPC 字典載入中…');
    s.update('ready', null);
    assert.equal(owned.children[0].data, '繁體中文 NPC 純文字翻譯已就緒');
    s.update('failed', 'IDENTITY');
    assert.equal(owned.children[0].data, '字典載入失敗（IDENTITY）');
    s.dispose();
    s.update('ready', null);
    s.dispose();
    assert.deepEqual(documentRef.body.children, [other]);
    assert.equal(STATUS_TEXT.failed('X'), '字典載入失敗（X）');
});

// --- D08 fixture builder provenance/negatives ---------------------------------------

const tmpRoot = fs.mkdtempSync(path.join(fs.realpathSync(os.tmpdir()), 't05-005-'));
test.after(() => fs.rmSync(tmpRoot, { recursive: true, force: true }));
const build = (...args) => spawnSync('python3', ['-I', builder, ...args], { encoding: 'utf8' });

test('D08 builder: fresh private fixture binds exact bytes, imports, CSP and modes', () => {
    const out = path.join(tmpRoot, 'fixture');
    const result = build(loaderPath, corePath, out);
    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stdout.includes(tmpRoot), false, 'public summary has no absolute path');
    const summary = JSON.parse(result.stdout);
    const prov = JSON.parse(fs.readFileSync(path.join(out, 'provenance.json'), 'utf8'));
    assert.equal(summary.provenance_sha256, sha(fs.readFileSync(path.join(out, 'provenance.json'))));
    assert.equal(prov.loader.sha256, sha(fs.readFileSync(loaderPath)));
    assert.deepEqual(prov.core.pin, CORE_PIN);
    assert.equal(prov.core.sha256, CORE_PIN.sha256);
    assert.deepEqual(prov.imports, [{ from: 'loader/dictionary_loader.mjs', specifier: './npc_plaintext_adapter.mjs', resolves: 'loader/npc_plaintext_adapter.mjs' }]);
    assert.deepEqual(prov.expected_groups, ['D01', 'D02', 'D03', 'D04', 'D05', 'D06', 'D07', 'D08', 'D09', 'D10']);
    assert.equal(prov.fault_modes.length, 10);
    assert.equal(prov.dictionary.copied, null);
    assert.ok(/base-uri 'self'/.test(prov.csp) && /connect-src 'self'/.test(prov.csp) && /img-src 'none'/.test(prov.csp) && /worker-src 'none'/.test(prov.csp));
    assert.equal(fs.statSync(out).mode & 0o777, 0o700);
    for (const file of prov.files) {
        const full = path.join(out, file.path);
        assert.equal(fs.lstatSync(full).isFile(), true);
        assert.equal(fs.statSync(full).mode & 0o777, 0o600, file.path);
        assert.equal(file.mode, '0600');
        assert.equal(sha(fs.readFileSync(full)), file.sha256, file.path);
    }
    for (const copy of ['loader', 'broken']) assert.ok(fs.readFileSync(path.join(out, copy, 'dictionary_loader.mjs')).equals(fs.readFileSync(loaderPath)));
    assert.ok(fs.readFileSync(path.join(out, 'loader', 'npc_plaintext_adapter.mjs')).equals(fs.readFileSync(corePath)));
    assert.equal(fs.existsSync(path.join(out, 'broken', 'npc_plaintext_adapter.mjs')), false, 'missing-core fixture');
    assert.equal(fs.existsSync(path.join(out, 'full')), false);
    const page = fs.readFileSync(path.join(out, 'pages', 'run', 'index.html'), 'utf8');
    assert.ok(page.includes(`content="${prov.csp}"`));
    assert.ok(page.indexOf('../boot.js') < page.indexOf('harness.mjs'), 'classic reporter before modules');
    assert.ok(page.includes('<base href="../../decoy/">'));
    assert.ok(!prov.server_allowlist.includes('server.py'));
    // Generated modules/server parse; nothing is executed or served.
    const check = path.join(tmpRoot, 'check.mjs');
    for (const file of prov.files.filter(f => /\.(?:m?js)$/.test(f.path))) {
        fs.copyFileSync(path.join(out, file.path), check);
        const syntax = spawnSync(process.execPath, ['--check', check], { encoding: 'utf8' });
        assert.equal(syntax.status, 0, `${file.path}: ${syntax.stderr}`);
    }
    const py = spawnSync('python3', ['-I', '-c', 'import sys; compile(open(sys.argv[1]).read(), "server.py", "exec")', path.join(out, 'server.py')], { encoding: 'utf8' });
    assert.equal(py.status, 0, py.stderr);
});

test('D08 builder refusals leave no new output and no foreign changes', () => {
    const dir = path.join(tmpRoot, 'neg');
    fs.mkdirSync(dir);
    const refused = (args, pattern, label) => {
        const result = build(...args);
        assert.equal(result.status, 1, `${label}: ${result.stdout}${result.stderr}`);
        assert.match(result.stderr, pattern, label);
        assert.equal(result.stdout, '', `${label}: no success summary`);
    };
    // Existing target, untouched.
    const existing = path.join(dir, 'existing');
    fs.mkdirSync(existing);
    fs.writeFileSync(path.join(existing, 'foreign.txt'), 'keep');
    refused([loaderPath, corePath, existing], /already exists/, 'existing');
    assert.equal(fs.readFileSync(path.join(existing, 'foreign.txt'), 'utf8'), 'keep');
    // Linked source, linked output ancestor, nonregular sources.
    fs.symlinkSync(loaderPath, path.join(dir, 'loader-link.mjs'));
    refused([path.join(dir, 'loader-link.mjs'), corePath, path.join(dir, 'o1')], /symbolic link/, 'linked loader');
    fs.mkdirSync(path.join(dir, 'real'));
    fs.symlinkSync(path.join(dir, 'real'), path.join(dir, 'linked-parent'));
    refused([loaderPath, corePath, path.join(dir, 'linked-parent', 'o2')], /symbolic link/, 'linked ancestor');
    assert.deepEqual(fs.readdirSync(path.join(dir, 'real')), []);
    refused([dir, corePath, path.join(dir, 'o3')], /not a regular file/, 'directory source');
    const fifo = path.join(dir, 'fifo');
    if (spawnSync('mkfifo', [fifo]).status === 0) refused([loaderPath, fifo, path.join(dir, 'o4')], /not a regular file/, 'fifo source');
    // Oversized loader, wrong core pin, extra import.
    const big = path.join(dir, 'big.mjs');
    fs.writeFileSync(big, Buffer.alloc(1024 * 1024 + 1, 0x20));
    refused([big, corePath, path.join(dir, 'o5')], /1 MiB/, 'oversized loader');
    const wrongCore = path.join(dir, 'core.mjs');
    fs.writeFileSync(wrongCore, Buffer.concat([fs.readFileSync(corePath), Buffer.from('\n')]));
    refused([loaderPath, wrongCore, path.join(dir, 'o6')], /core pin/, 'wrong core');
    const extra = path.join(dir, 'extra.mjs');
    fs.writeFileSync(extra, "import x from './other.mjs';\n" + fs.readFileSync(loaderPath, 'utf8'));
    refused([extra, corePath, path.join(dir, 'o7')], /only \.\/npc_plaintext_adapter\.mjs/, 'extra import');
    // Optional dictionary: wrong size (before creating output), linked,
    // correct size but wrong SHA (after copying: owned output removed).
    const small = path.join(dir, 'small.json');
    fs.writeFileSync(small, '{}');
    refused([loaderPath, corePath, path.join(dir, 'o8'), '--dictionary-source', small], /size differs/, 'dictionary size');
    fs.symlinkSync(small, path.join(dir, 'dict-link.json'));
    refused([loaderPath, corePath, path.join(dir, 'o9'), '--dictionary-source', path.join(dir, 'dict-link.json')], /symbolic link/, 'dictionary link');
    const sparse = path.join(dir, 'sparse.json');
    fs.closeSync(fs.openSync(sparse, 'w'));
    fs.truncateSync(sparse, DICTIONARY_BYTES);
    refused([loaderPath, corePath, path.join(dir, 'o10'), '--dictionary-source', sparse], /SHA-256 differs/, 'dictionary hash');
    for (let i = 1; i <= 10; i++) assert.equal(fs.existsSync(path.join(dir, `o${i}`)), false, `o${i} not left behind`);
    const usage = build(loaderPath, corePath);
    assert.equal(usage.status, 2);
});

// --- D09 root-only native full body ---------------------------------------------------

test('D09 Root native full-body and costs', { skip: 'NOT RUN — ROOT ONLY: fresh native browser load of the 19706353-byte body (fixture ?full=1)' }, () => {});

// --- D10 reporter/fault controls --------------------------------------------------------

test('D10 generated reporter: fixed ten groups, no omitted/zero/late/extra PASS, ledger needs sink evidence', async () => {
    const out = path.join(tmpRoot, 'fixture-d10');
    assert.equal(build(loaderPath, corePath, out).status, 0);
    const { BASELINE_GROUPS, FAULT_MODES, createReporter, ledger } = await import(pathToFileURL(path.join(out, 'fixture', 'reporter.mjs')).href);
    assert.deepEqual(BASELINE_GROUPS.map(g => g.id), ['D01', 'D02', 'D03', 'D04', 'D05', 'D06', 'D07', 'D08', 'D09', 'D10']);
    assert.deepEqual([...FAULT_MODES], ['missing-loader', 'missing-core', 'csp-inline', 'loader-reject', 'loader-timeout', 'api-error', 'cleanup-error', 'unhandled-rejection', 'zero-assertions', 'omitted-group']);
    const full = () => { const r = createReporter(); for (const g of BASELINE_GROUPS) r.record(g.id, 1, []); return r; };
    assert.equal(full().summary().state, 'pass');
    const no09 = createReporter(); for (const g of BASELINE_GROUPS) if (g.id !== 'D09') no09.record(g.id, 3, []);
    assert.equal(no09.summary().state, 'fail');
    assert.deepEqual(no09.summary().missing, ['D09']);
    const no10 = createReporter(); for (const g of BASELINE_GROUPS) if (g.id !== 'D10') no10.record(g.id, 3, []);
    assert.equal(no10.summary().state, 'fail');
    const zero = createReporter(); for (const g of BASELINE_GROUPS) zero.record(g.id, g.id === 'D04' ? 0 : 1, []);
    assert.equal(zero.summary().groups.find(g => g.id === 'D04').state, 'fail');
    const late = full(); late.fail('late'); assert.equal(late.summary().state, 'fail');
    const extra = full(); extra.record('D11', 1, []); assert.equal(extra.summary().state, 'fail');
    const nine = createReporter(BASELINE_GROUPS.slice(0, 9)); for (const g of BASELINE_GROUPS.slice(0, 9)) nine.record(g.id, 1, []);
    assert.equal(nine.summary().state, 'fail', 'denominator cannot shrink to nine');
    // Mode name alone, or another mode's evidence, never observes a fault.
    const evidence = {
        'missing-loader': { sink: 'dynamic-import', target: 'absent-loader', rejected: true, probeStatus: 404 },
        'missing-core': { sink: 'dynamic-import', target: 'broken-loader', rejected: true, loaderStatus: 200, coreStatus: 404 },
        'csp-inline': { sink: 'csp-violation', directive: 'script-src-elem', blocked: 'inline', ran: false },
        'loader-reject': { sink: 'loader-ready', code: 'HTTP_STATUS', state: 'failed', statusText: 'a', expectedText: 'a' },
        'loader-timeout': { sink: 'loader-ready', code: 'TIMEOUT', state: 'failed', elapsedMs: 301, timeoutMs: 300 },
        'api-error': { sink: 'api-error-sink', category: 'listener', ordinaryActionDone: true },
        'cleanup-error': { sink: 'api-error-sink', category: 'cleanup', thrown: true, rejected: true, ordinaryActionDone: true },
        'unhandled-rejection': { sink: 'boot-unhandledrejection', matched: true },
        'zero-assertions': { sink: 'reporter-summary', kind: 'zero', groupState: 'fail', assertions: 0 },
        'omitted-group': { sink: 'reporter-summary', kind: 'omitted', groupState: 'not run' },
    };
    for (const mode of FAULT_MODES) {
        const row = rows => rows.find(r => r.mode === mode);
        assert.equal(row(ledger(mode, [{ mode, ...evidence[mode] }])).state, 'OBSERVED', mode);
        assert.equal(row(ledger(mode, [{ mode }])).state, 'NOT OBSERVED', `${mode}: mode only`);
        assert.equal(row(ledger(mode, [])).state, 'NOT OBSERVED', `${mode}: suppressed`);
        const other = FAULT_MODES.find(m => m !== mode && evidence[m].sink !== evidence[mode].sink);
        assert.equal(row(ledger(mode, [{ mode, ...evidence[other] }])).state, 'NOT OBSERVED', `${mode}: other sink`);
        assert.equal(ledger(mode, []).filter(r => r.state === 'NOT RUN').length, 9);
    }
    assert.equal(ledger('loader-timeout', [{ mode: 'loader-timeout', ...evidence['loader-timeout'], elapsedMs: 10 }])[4].state, 'NOT OBSERVED', 'timeout needs real elapsed');
    assert.ok(ledger('baseline', []).every(r => r.state === 'NOT RUN'));
});

test('no unhandled rejections across the suite', async () => {
    await sleep(50);
    assert.deepEqual(unhandled.map(String), []);
});

// Production binding exists and is the default export.
test('production default export is the bound initializer', () => {
    assert.equal(typeof initialize, 'function');
    assert.equal(initialize.length, 2);
});

// Root regressions for observed post-budget setup and per-operation stop handling.
test('D06 setup exhaustion prevents later owned work and requests', async () => {
    const hold = () => { const end = performance.now() + 60; while (performance.now() < end) {} };
    for (const stage of ['cleanup', 'core', 'status-create', 'status-loading']) {
        let coreCalls = 0, statusCreates = 0, requests = 0, removals = 0;
        const cleanups = [];
        const api = { version: 1, on() { return () => {}; }, cleanup(fn) { cleanups.push(fn); if (stage === 'cleanup') hold(); } };
        const init = createInitializer({
            moduleURL: MODULE, pageURL: PAGE, expected: pinOf(TINY), timeoutMs: 25,
            initializeCore({ dictionaryReady }) {
                coreCalls++;
                dictionaryReady.catch(() => {});
                if (stage === 'core') hold();
                return { dispose() {}, diagnostics() { return { state: 'loading' }; } };
            },
            statusFactory() {
                statusCreates++;
                if (stage === 'status-create') hold();
                return { update(state) { if (state === 'loading' && stage === 'status-loading') hold(); }, dispose() { removals++; } };
            },
            fetchImpl() { requests++; return Promise.reject(new Error('post-budget request')); },
            digestImpl() { throw new Error('unreached digest'); }, parseImpl: JSON.parse,
        });
        const handle = init(null, api);
        assert.equal(await outcome(handle), 'TIMEOUT', stage);
        assert.equal(handle.diagnostics().state, 'failed', stage);
        assert.equal(requests, 0, stage);
        assert.ok(handle.diagnostics().totalMs >= 25, stage);
        if (stage === 'cleanup') assert.equal(coreCalls, 0);
        if (stage === 'cleanup' || stage === 'core') assert.equal(statusCreates, 0);
        handle.dispose();
        for (const fn of cleanups.reverse()) fn();
        assert.equal(removals, statusCreates, stage);
    }
});

test('D06 initial timer uses the budget remaining after cleanup registration', async () => {
    // Queue an independent observer first. Timer due-order distinguishes the
    // original total budget from a fresh full budget after the 60ms setup.
    const observe = sleep(140);
    const owned = scope();
    const cleanup = owned.api.cleanup;
    let delayed = false;
    owned.api.cleanup = fn => {
        cleanup(fn);
        if (delayed) return;
        delayed = true;
        const end = performance.now() + 60;
        while (performance.now() < end) {}
    };
    let requests = 0;
    const run = harness({ api: owned, timeoutMs: 120, fetchImpl: () => { requests++; return new Promise(() => {}); } });
    const result = outcome(run.handle);
    try {
        assert.equal(requests, 1, 'setup leaves time for one pending request');
        await observe;
        assert.equal(run.handle.diagnostics().state, 'failed');
        assert.equal(await result, 'TIMEOUT');
    } finally { run.handle.dispose(); owned.dispose(); }
});

test('D06 reentrant disposal still observes the dependency returned afterward', async () => {
    for (const stage of ['fetch', 'read', 'digest']) {
        const owned = scope();
        const before = unhandled.length;
        const rejectAfterDispose = () => { owned.dispose(); return Promise.reject(new Error('late dependency outcome')); };
        const config = { api: owned };
        if (stage === 'fetch') config.fetchImpl = rejectAfterDispose;
        if (stage === 'read') config.res = response({ stream: {
            getReader() { return { read: rejectAfterDispose, cancel() { return Promise.resolve(); } }; },
            cancel() { return Promise.resolve(); },
        } });
        if (stage === 'digest') config.digestImpl = rejectAfterDispose;
        const run = harness(config);
        assert.equal(await outcome(run.handle), 'DISPOSED', stage);
        await sleep(10);
        assert.equal(unhandled.length, before, stage);
        assert.equal(run.handle.diagnostics().state, 'disposed', stage);
        run.handle.dispose(); owned.dispose();
    }
});
