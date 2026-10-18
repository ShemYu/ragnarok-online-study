// T05.005: client API 1 loader for the Traditional Chinese NPC dictionary.
//
// One fixed same-origin GET of the dict.json beside this module, read into one
// exactly sized buffer, identified by its full SHA-256 before one fatal UTF-8
// decode and one JSON.parse. The parsed object is handed, unchanged and
// unscanned, to the unchanged NPC plain-text core; the wrapper is ready only
// once that core reports ready. One total deadline, one terminal state and one
// owned status node. The logical deadline cannot interrupt a synchronous
// decode/parse or a native digest. See DICTIONARY_LOADER.md.

import initializeNpcCore from './npc_plaintext_adapter.mjs';

const PRODUCTION = Object.freeze({
    bytes: 19706353,
    sha256: 'be3825ca74db764f8d9ffbea9ba8f15ac17b1fd5bde49975d4b36c59ba704fc2',
});
const PRODUCTION_TIMEOUT_MS = 30000;
// Zero-delay macrotask checkpoints after the dictionary handoff.
const ACTIVATION_CHECKPOINTS = 8;
const OWNER_ATTRIBUTE = 'data-t05-dictionary-loader';
const SHA256 = /^[0-9a-f]{64}$/;
const CORE_STATES = new Set(['loading', 'ready', 'failed', 'disposed']);

// The only values ready can reject with (as error.code) or errorCode can hold.
export const ERROR_CODES = Object.freeze([
    'API',        // api.cleanup threw while registering
    'STATUS',     // status factory/handle/update failed
    'CORE',       // core init threw, bad handle, or not ready after activation
    'FETCH',      // fetch threw or rejected (network, CORS, redirect:'error', abort)
    'HTTP_STATUS',// status other than 200
    'REDIRECT',   // redirected, or final URL differs from the request
    'MEDIA_TYPE', // not application/json with at most charset=utf-8
    'BODY',       // no readable stream, getReader failed, or buffer allocation failed
    'READ',       // read() threw/rejected or returned a malformed result
    'CHUNK',      // chunk not a plain Uint8Array, or zero length
    'OVERSIZE',   // a chunk would pass the expected size
    'TRUNCATED',  // EOF before the expected size
    'DIGEST',     // digest threw/rejected or was not 32 bytes
    'IDENTITY',   // SHA-256 differs from the pin
    'DECODE',     // fatal UTF-8 decode failed
    'PARSE',      // parse threw
    'CONTAINER',  // parsed value is not a plain non-array object
    'TIMEOUT',    // total deadline passed
    'DISPOSED',   // ready only: disposed before ready
    'DISPOSE',    // diagnostics only: a disposer threw while disposing
]);

export const STATUS_TEXT = Object.freeze({
    loading: '繁體中文 NPC 字典載入中…',
    ready: '繁體中文 NPC 純文字翻譯已就緒',
    failed: code => `字典載入失敗（${code}）`,
});

class DictionaryLoaderError extends Error {
    constructor(code) {
        super(code);
        this.name = 'DictionaryLoaderError';
        this.code = code;
    }
}

const noop = () => {};
const STOP = Symbol('stop');

class Stage extends Error {
    constructor(code) { super(code); this.code = code; }
}

function absoluteURL(value, what) {
    if (typeof value !== 'string') throw new TypeError(`dictionary loader: ${what} must be an absolute URL string`);
    try { return new URL(value); } catch { throw new TypeError(`dictionary loader: ${what} must be an absolute URL string`); }
}

// application/json, optionally one charset=utf-8 (name case-insensitive,
// value case-insensitive and optionally quoted). Anything else is refused.
export function jsonMediaType(value) {
    if (typeof value !== 'string') return false;
    const parts = value.split(';');
    if (parts[0].trim().toLowerCase() !== 'application/json') return false;
    if (parts.length === 1) return true;
    if (parts.length !== 2) return false;
    const parameter = parts[1].trim();
    const equals = parameter.indexOf('=');
    if (equals < 0 || parameter.slice(0, equals).trim().toLowerCase() !== 'charset') return false;
    let charset = parameter.slice(equals + 1).trim();
    if (charset.length >= 2 && charset.startsWith('"') && charset.endsWith('"')) charset = charset.slice(1, -1);
    return charset.toLowerCase() === 'utf-8';
}

function plainContainer(value) {
    if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
    const proto = Object.getPrototypeOf(value);
    return proto === Object.prototype || proto === null;
}

function hex(buffer) {
    const bytes = new Uint8Array(buffer);
    let out = '';
    for (let i = 0; i < bytes.length; i++) out += bytes[i].toString(16).padStart(2, '0');
    return out;
}

function requireFacilities() {
    const g = globalThis;
    if (typeof g.URL !== 'function' || typeof g.Uint8Array !== 'function' || typeof g.AbortController !== 'function'
        || typeof g.Promise !== 'function' || typeof g.setTimeout !== 'function' || typeof g.clearTimeout !== 'function') {
        throw new TypeError('dictionary loader requires URL, Uint8Array, AbortController, Promise and timers');
    }
    if (!g.performance || typeof g.performance.now !== 'function') throw new TypeError('dictionary loader requires performance.now');
    let fatal = false;
    try { fatal = typeof g.TextDecoder === 'function' && new g.TextDecoder('utf-8', { fatal: true }).fatal === true; } catch { fatal = false; }
    if (!fatal) throw new TypeError('dictionary loader requires a fatal UTF-8 TextDecoder');
}

function requireApi(api) {
    if (!api || typeof api !== 'object' || api.version !== 1) throw new TypeError('dictionary loader requires client API 1');
    if (typeof api.on !== 'function' || typeof api.cleanup !== 'function') throw new TypeError('dictionary loader requires api.on and api.cleanup');
}

export function createInitializer({
    initializeCore, moduleURL, pageURL, expected, timeoutMs,
    fetchImpl, digestImpl, parseImpl, statusFactory,
} = {}) {
    for (const [name, fn] of Object.entries({ initializeCore, fetchImpl, digestImpl, parseImpl, statusFactory })) {
        if (typeof fn !== 'function') throw new TypeError(`dictionary loader: ${name} must be a function`);
    }
    if (!expected || typeof expected !== 'object' || !Number.isSafeInteger(expected.bytes) || expected.bytes <= 0
        || typeof expected.sha256 !== 'string' || !SHA256.test(expected.sha256)) {
        throw new TypeError('dictionary loader: expected must be {bytes, sha256}');
    }
    if (!Number.isSafeInteger(timeoutMs) || timeoutMs <= 0) throw new TypeError('dictionary loader: timeoutMs must be a positive integer');
    const module = absoluteURL(moduleURL, 'moduleURL');
    const page = absoluteURL(pageURL, 'pageURL');
    if (module.protocol !== 'http:' && module.protocol !== 'https:') throw new TypeError('dictionary loader: module must be served over HTTP(S)');
    if (module.username || module.password || module.search || module.hash) throw new TypeError('dictionary loader: module URL has credentials, query or fragment');
    const target = new URL('./dict.json', module);
    if (target.username || target.password || target.search || target.hash) throw new TypeError('dictionary loader: dictionary URL has credentials, query or fragment');
    if (target.origin !== page.origin) throw new TypeError('dictionary loader: dictionary must be same-origin with the page');
    const url = target.href;
    const pin = Object.freeze({ bytes: expected.bytes, sha256: expected.sha256 });

    // `parameters` carries no URL, pin, deadline or dependency: ignored.
    return function initialize(parameters, api) {
        requireApi(api);
        requireFacilities();
        return load(api, { initializeCore, url, pin, timeoutMs, fetchImpl, digestImpl, parseImpl, statusFactory });
    };
}

function load(api, { initializeCore, url, pin, timeoutMs, fetchImpl, digestImpl, parseImpl, statusFactory }) {
    const now = () => performance.now();
    const started = now();
    let state = 'loading';
    let phase = 'init';
    let errorCode = null;
    let receivedBytes = 0;
    let coreState = null;
    const timings = { requestMs: null, readMs: null, digestMs: null, decodeMs: null, parseMs: null, activateMs: null, totalMs: null };
    const STAGE_TIMING = { request: 'requestMs', read: 'readMs', digest: 'digestMs', decode: 'decodeMs', parse: 'parseMs', activate: 'activateMs' };
    let stageStarted = started;

    let core = null;
    let status = null;
    let controller = null;
    let deadline = null;
    let tick = null;
    let body = null;     // the response's stream, until a reader owns it
    let reader = null;
    let handedOff = false;

    // Controlled promises; both are always handled internally.
    let resolveDictionary, rejectDictionary, resolveReady, rejectReady;
    const dictionaryReady = new Promise((resolve, reject) => { resolveDictionary = resolve; rejectDictionary = reject; });
    dictionaryReady.then(undefined, noop);
    const ready = new Promise((resolve, reject) => { resolveReady = resolve; rejectReady = reject; });
    ready.then(undefined, noop);
    let signalStop;
    const halted = new Promise(resolve => { signalStop = resolve; }).then(() => { throw STOP; });
    halted.then(undefined, noop);

    const elapsed = since => Math.max(0, now() - since);
    function enter(next) { phase = next; stageStarted = now(); }
    function finishStage() {
        const key = STAGE_TIMING[phase];
        if (key && timings[key] === null) timings[key] = elapsed(stageStarted);
    }
    function live() { return state === 'loading'; }
    function overdue() { return elapsed(started) >= timeoutMs; }
    function check() {
        if (!live()) throw STOP;
        if (overdue()) throw new Stage('TIMEOUT');
    }
    // A pending native/trusted wait, bounded by the terminal signal. Late
    // outcomes of `promise` are consumed by the race itself.
    function wait(promise) { return Promise.race([promise, halted]); }

    function readCoreState() {
        if (!core) return;
        try {
            const value = core.diagnostics();
            if (value && typeof value === 'object' && CORE_STATES.has(value.state)) coreState = value.state;
        } catch { /* keep the last observed state */ }
    }

    // Stop everything owned without awaiting stuck cancellation.
    function release() {
        if (deadline !== null) { clearTimeout(deadline); deadline = null; }
        if (tick !== null) { clearTimeout(tick); tick = null; }
        signalStop();
        if (controller) { try { controller.abort(); } catch { /* ignored */ } }
        const stream = reader || body;
        reader = body = null;
        if (stream) {
            try { Promise.resolve(stream.cancel()).then(undefined, noop); } catch { /* ignored */ }
        }
        rejectDictionary(new DictionaryLoaderError('DISPOSED'));
    }

    function disposeCore() {
        const handle = core;
        if (!handle) return true;
        let ok = true;
        try { handle.dispose(); } catch { ok = false; }
        readCoreState();
        core = null;
        return ok;
    }

    function fail(code) {
        if (!live()) return;
        state = 'failed';
        errorCode = code;
        finishStage();
        timings.totalMs = elapsed(started);
        release();
        // Before handoff the rejected dictionary fails the core; after it the
        // core is disposed. Either way it stops observing.
        if (handedOff) disposeCore(); else readCoreState();
        if (status) {
            try { status.update('failed', code); } catch { /* cannot paint its own failure */ }
        }
        rejectReady(new DictionaryLoaderError(code));
    }

    function dispose() {
        if (state === 'disposed') return;
        const wasLoading = state === 'loading';
        state = 'disposed';
        if (wasLoading) {
            finishStage();
            timings.totalMs = elapsed(started);
        }
        release();
        let ok = disposeCore();
        const owned = status;
        status = null;
        if (owned) {
            try { owned.dispose(); } catch { ok = false; }
        }
        if (!ok) errorCode = 'DISPOSE';
        rejectReady(new DictionaryLoaderError('DISPOSED'));
    }

    const diagnostics = () => Object.freeze({
        state, phase, errorCode, receivedBytes, expectedBytes: pin.bytes,
        coreState: (readCoreState(), coreState), ...timings,
    });
    const handle = Object.freeze({ dispose, ready, diagnostics });

    try {
        api.cleanup(dispose);
    } catch {
        fail('API');
        return handle;
    }
    if (!live()) return handle;

    controller = new AbortController();
    // A timer may fire marginally early; TIMEOUT only once the monotonic
    // clock has actually passed the budget.
    const arm = ms => {
        deadline = setTimeout(() => {
            deadline = null;
            if (!live()) return;
            if (overdue()) fail('TIMEOUT');
            else arm(Math.max(1, Math.ceil(timeoutMs - elapsed(started))));
        }, ms);
    };
    arm(timeoutMs);

    let candidate;
    try {
        candidate = initializeCore({ dictionaryReady }, api);
    } catch {
        fail('CORE');
        return handle;
    }
    if (!candidate || typeof candidate !== 'object' || typeof candidate.dispose !== 'function' || typeof candidate.diagnostics !== 'function') {
        try { if (candidate && typeof candidate.dispose === 'function') candidate.dispose(); } catch { /* ignored */ }
        fail('CORE');
        return handle;
    }
    if (!live()) {
        // Disposed reentrantly while the core initialized.
        try { candidate.dispose(); } catch { if (state === 'disposed') errorCode = 'DISPOSE'; }
        return handle;
    }
    core = candidate;

    try {
        const made = statusFactory();
        if (!made || typeof made !== 'object' || typeof made.update !== 'function' || typeof made.dispose !== 'function') throw new TypeError('status');
        if (!live()) {
            try { made.dispose(); } catch { if (state === 'disposed') errorCode = 'DISPOSE'; }
            return handle;
        }
        status = made;
        status.update('loading', null);
    } catch {
        fail('STATUS');
        return handle;
    }
    if (!live()) return handle;

    run().catch(error => {
        if (error === STOP) return;
        fail(error instanceof Stage ? error.code : 'CORE');
    });
    return handle;

    async function run() {
        enter('request');
        let response;
        try {
            response = await wait(fetchImpl(url, {
                method: 'GET', mode: 'same-origin', credentials: 'omit',
                redirect: 'error', cache: 'no-store', signal: controller.signal,
            }));
        } catch (error) {
            if (error === STOP) throw STOP;
            throw new Stage('FETCH');
        }
        check();
        if (!response || typeof response !== 'object') throw new Stage('FETCH');
        // Own the body first so every early refusal can cancel it.
        const stream = response.body;
        if (stream && typeof stream === 'object' && typeof stream.cancel === 'function') body = stream;
        if (response.status !== 200) throw new Stage('HTTP_STATUS');
        if (response.redirected !== false || response.url !== url) throw new Stage('REDIRECT');
        let type = null;
        try { type = response.headers.get('content-type'); } catch { type = null; }
        if (!jsonMediaType(type)) throw new Stage('MEDIA_TYPE');
        if (!body || typeof body.getReader !== 'function') throw new Stage('BODY');
        finishStage();

        enter('read');
        try { reader = body.getReader(); } catch { throw new Stage('BODY'); }
        body = null;
        let bytes;
        try { bytes = new Uint8Array(pin.bytes); } catch { throw new Stage('BODY'); }
        for (;;) {
            check();
            let result;
            try { result = await wait(reader.read()); } catch (error) {
                if (error === STOP) throw STOP;
                throw new Stage('READ');
            }
            check();
            if (!result || typeof result !== 'object') throw new Stage('READ');
            if (result.done === true) break;
            const chunk = result.value;
            if (!(chunk instanceof Uint8Array) || Object.getPrototypeOf(chunk) !== Uint8Array.prototype) throw new Stage('CHUNK');
            if (chunk.byteLength === 0) throw new Stage('CHUNK');
            if (chunk.byteLength > pin.bytes - receivedBytes) throw new Stage('OVERSIZE');
            bytes.set(chunk, receivedBytes);
            receivedBytes += chunk.byteLength;
            check();
        }
        if (receivedBytes !== pin.bytes) throw new Stage('TRUNCATED');
        reader = null;
        finishStage();

        enter('digest');
        check();
        let digest;
        try { digest = await wait(digestImpl(bytes)); } catch (error) {
            if (error === STOP) throw STOP;
            throw new Stage('DIGEST');
        }
        check();
        if (!(digest instanceof ArrayBuffer) || digest.byteLength !== 32) throw new Stage('DIGEST');
        if (hex(digest) !== pin.sha256) throw new Stage('IDENTITY');
        finishStage();

        enter('decode');
        let text;
        try { text = new TextDecoder('utf-8', { fatal: true }).decode(bytes); } catch { throw new Stage('DECODE'); }
        bytes = null;
        finishStage();
        check();

        enter('parse');
        let value;
        try { value = parseImpl(text); } catch { throw new Stage('PARSE'); }
        text = null;
        finishStage();
        check();
        if (!plainContainer(value)) throw new Stage('CONTAINER');

        enter('activate');
        handedOff = true;
        resolveDictionary(value);
        value = null;
        for (let i = 0; i < ACTIVATION_CHECKPOINTS; i++) {
            await wait(new Promise(resolve => { tick = setTimeout(() => { tick = null; resolve(); }, 0); }));
            check();
            let snapshot;
            try { snapshot = core.diagnostics(); } catch { throw new Stage('CORE'); }
            if (!snapshot || typeof snapshot !== 'object' || !CORE_STATES.has(snapshot.state)) throw new Stage('CORE');
            coreState = snapshot.state;
            if (coreState === 'ready') break;
            if (coreState !== 'loading') throw new Stage('CORE');
        }
        if (coreState !== 'ready') throw new Stage('CORE');
        check();
        try { status.update('ready', null); } catch { throw new Stage('STATUS'); }
        check();
        finishStage();
        phase = 'ready';
        state = 'ready';
        timings.totalMs = elapsed(started);
        clearTimeout(deadline);
        deadline = null;
        signalStop();
        resolveReady('ready');
    }
}

// The one owned status node: role=status, aria-live=polite, ownership marker.
// Styled through CSSOM only; never replaces or touches stock UI.
export function createOwnedStatus(documentRef) {
    const node = documentRef.createElement('div');
    node.setAttribute('role', 'status');
    node.setAttribute('aria-live', 'polite');
    node.setAttribute(OWNER_ATTRIBUTE, '');
    const style = node.style;
    if (style) {
        style.position = 'fixed'; style.right = '8px'; style.bottom = '8px'; style.zIndex = '2147483647';
        style.padding = '4px 8px'; style.font = '13px/1.4 sans-serif'; style.color = '#fff'; style.background = 'rgba(0,0,0,0.72)';
        style.pointerEvents = 'none';
    }
    const text = documentRef.createTextNode('');
    node.appendChild(text);
    documentRef.body.appendChild(node);
    let gone = false;
    return {
        update(next, code) {
            if (gone) return;
            node.setAttribute('data-state', next);
            text.data = next === 'failed' ? STATUS_TEXT.failed(code) : STATUS_TEXT[next];
        },
        dispose() {
            if (gone) return;
            gone = true;
            if (node.parentNode) node.parentNode.removeChild(node);
        },
    };
}

// Production binding: fixed module-relative dict.json, fixed pin, 30 s, native
// fetch/WebCrypto/JSON.parse and the owned status node. `parameters` ignored.
export default function initialize(parameters, api) {
    requireApi(api);
    const g = globalThis;
    if (typeof g.fetch !== 'function') throw new TypeError('dictionary loader requires fetch');
    if (!g.crypto || !g.crypto.subtle || typeof g.crypto.subtle.digest !== 'function') throw new TypeError('dictionary loader requires WebCrypto');
    if (!g.document || !g.document.body) throw new TypeError('dictionary loader requires document.body');
    if (typeof g.MutationObserver !== 'function') throw new TypeError('dictionary loader requires MutationObserver');
    if (!g.location || typeof g.location.href !== 'string') throw new TypeError('dictionary loader requires location');
    const documentRef = g.document;
    return createInitializer({
        initializeCore: initializeNpcCore,
        moduleURL: import.meta.url,
        pageURL: g.location.href,
        expected: PRODUCTION,
        timeoutMs: PRODUCTION_TIMEOUT_MS,
        fetchImpl: (target, options) => g.fetch(target, options),
        digestImpl: bytes => g.crypto.subtle.digest('SHA-256', bytes),
        parseImpl: text => JSON.parse(text),
        statusFactory: () => createOwnedStatus(documentRef),
    })(parameters, api);
}
