// T05.008: scoped navigation filesystem-cache audit/removal and narrow HTTP
// refresh for the fixed local game origin. See NAVIGATION_BROWSER_VERIFIER.md.
//
// The generator copies these bytes verbatim to T05_008-cache.mjs, which the
// generated T05_008-cache.html loads with browser-enforced SRI. Importing this
// module anywhere else (Node, tests, another page) starts nothing: the browser
// binding runs only inside a document marked data-t05008="cache" that holds
// the report element. createVerifier() is a side-effect-free core over
// injected adapters; bindBrowser() wires it to the real browser APIs with the
// fixed pins below. There is no path, host, digest or URL input.
//
// Scope: the six exact TEMPORARY-filesystem copies and their six HTTP
// aliases, nothing else. No create:true, directory enumeration/removal,
// recursive removal, PERSISTENT filesystem, IndexedDB, CacheStorage, cookies,
// storage writes or external URL. WebStorage is only read, and only a
// count+SHA-256 of each area is reported, never a key or value.

export const TASK = 'T05.008';
export const PROFILE_NAME = 'fixed-navigation-browser-verifier-v1';
export const ORIGIN = 'http://127.0.0.1:3338';

export const TARGETS = Object.freeze([
	Object.freeze({ path: 'data/luafiles514/lua files/navigation/navi_map_krpri.lub', bytes: 67328, sha256: 'e7c8d566b5883df68d01830f0ce4ec385fc8ac084a1a8f6944bd517d89a046dc' }),
	Object.freeze({ path: 'data/luafiles514/lua files/navigation/navi_mob_krpri.lub', bytes: 396243, sha256: '02aeb90a6df4af8f2e4fc8adf5a88f70b5ac1c48e32373a7cba57439a776c3c7' }),
	Object.freeze({ path: 'data/luafiles514/lua files/navigation/navi_npc_krpri.lub', bytes: 1025994, sha256: '7b760b652d8ce5a6353811aa57d433848b056f6bdc99a3ddbb585f88bb44b528' }),
	Object.freeze({ path: 'data/luafiles514/lua files/navigation/navi_link_krpri.lub', bytes: 594363, sha256: 'f6526637f8cfc8755b92fad9e496f7c97439715db34a6efd430dfb870b62ff10' }),
	Object.freeze({ path: 'data/luafiles514/lua files/navigation/navi_linkdistance_krpri.lub', bytes: 1556072, sha256: '26cea879a399a1362a02deecf0ef3b07c7d4bfcdf01938f08f98338e5f05c193' }),
	Object.freeze({ path: 'data/luafiles514/lua files/navigation/navi_npcdistance_krpri.lub', bytes: 3840599, sha256: '3e896b2ba29de46f40ab36e43917359b376612ef00b3b4c0e2eb0cc81cb95471' })
]);

export const BUNDLES = Object.freeze({
	original: Object.freeze({ bytes: 13166284, sha256: '80f4371cc8da2bb54432e46e7e34dfaf7acc56444b28c6fbc6a99c6ba22933ea' }),
	repaired: Object.freeze({ bytes: 13172839, sha256: '6ba854cb67b1306cadb905b1b89a7a1eac98cd7e5c912196e6f87df41a5c4c2f' })
});

export const IDS = Object.freeze({
	report: 'T05_008-cache-report',
	inspect: 'inspect-cache',
	remove: 'remove-verified-cache',
	original: 'refresh-http-original',
	repaired: 'refresh-http-repaired'
});

// Finite result vocabulary. Reports carry only these codes, fixed paths,
// numbers and hashes; never an exception message, stack or storage content.
export const CODES = Object.freeze([
	'busy', 'mutation-locked', 'callback-pending', 'origin-refused', 'unsupported',
	'storage-unavailable', 'storage-unstable', 'storage-changed',
	'filesystem-unavailable', 'timeout', 'read-error', 'type-mismatch', 'directory',
	'identity-mismatch', 'size-mismatch', 'content-mismatch', 'lookup-error',
	'precondition-failed', 'changed-before-delete', 'remove-error', 'still-present',
	'filesystem-not-absent', 'bundle-stage-mismatch', 'fetch-error', 'redirected',
	'foreign-response', 'unexpected-status', 'stale-default-response', 'body-too-large',
	'bad-mode', 'internal-error'
]);

export const DEFAULT_CALLBACK_TIMEOUT_MS = 30000;
export const DEFAULT_FETCH_TIMEOUT_MS = 120000;
const ERROR_BODY_CAP = 65536;

// FileManager.getHTTP: remoteClient '/' plus each path segment URI-encoded.
export function aliasUrl(path, origin = ORIGIN) {
	return origin + '/' + path.split('/').map(encodeURIComponent).join('/');
}

// A modern NotFoundError (DOMException code 8, or the legacy code 1), or a
// legacy FileError NOT_FOUND_ERR (code 1) with no conflicting name. Anything
// else, including SecurityError/NotReadableError, is a failure, not "missing".
export function isGenuineNotFound(error) {
	if (!error || typeof error !== 'object') {
		return false;
	}
	const name = error.name;
	const code = error.code;
	if (name === 'NotFoundError') {
		return code === undefined || code === 8 || code === 1;
	}
	if (name === undefined || name === '' || name === 'FileError' || name === 'NOT_FOUND_ERR') {
		return code === 1;
	}
	return false;
}

class Stop extends Error {
	constructor(code, extra) {
		super(code);
		this.code = code;
		this.extra = extra || null;
	}
}

const hex = buffer => Array.from(new Uint8Array(buffer), b => (b + 256).toString(16).slice(1)).join('');

function sameUrlOrigin(url, origin) {
	try {
		return new URL(url).origin === origin;
	} catch {
		return false;
	}
}

/**
 * The testable core. `adapters` supplies every browser capability; nothing
 * here touches a global. `pins` exists only as an authored test seam; the
 * browser binding never passes it.
 */
export function createVerifier(adapters, pins = {}) {
	const origin = pins.origin || ORIGIN;
	const targets = pins.targets || TARGETS;
	const bundles = pins.bundles || BUNDLES;
	const callbackTimeoutMs = pins.callbackTimeoutMs || DEFAULT_CALLBACK_TIMEOUT_MS;
	const fetchTimeoutMs = pins.fetchTimeoutMs || DEFAULT_FETCH_TIMEOUT_MS;
	const a = adapters || {};
	const setT = a.setTimeout;
	const clearT = a.clearTimeout;

	// Outstanding timed-out callbacks/promises. While any remain, no mutation
	// may start and no inspection can unlock.
	const pending = new Set();
	let busy = false;
	let locked = false;
	let sequence = 0;

	const notify = () => {
		if (typeof a.onChange === 'function') {
			try {
				a.onChange(status());
			} catch {
				// a rendering failure must not change verifier state
			}
		}
	};

	function status() {
		return {
			busy,
			pending: pending.size,
			mutation_locked: locked,
			can_mutate: !busy && !locked && pending.size === 0
		};
	}

	// Await a callback-style API exactly once. A timeout resolves as
	// 'timeout' and leaves a pending token until the real callback arrives.
	function callbackOp(start) {
		return new Promise(resolve => {
			let settled = false;
			let timedOut = false;
			const token = {};
			const timer = setT(() => {
				if (settled) {
					return;
				}
				timedOut = true;
				pending.add(token);
				resolve({ outcome: 'timeout' });
			}, callbackTimeoutMs);
			const finish = result => {
				if (settled) {
					return;
				}
				settled = true;
				clearT(timer);
				if (timedOut) {
					pending.delete(token);
					notify();
					return;
				}
				resolve(result);
			};
			try {
				start(value => finish({ outcome: 'ok', value }), error => finish({ outcome: 'error', error }));
			} catch (error) {
				finish({ outcome: 'error', error });
			}
		});
	}

	// Same contract for promise-returning APIs, with an explicit bound and an
	// optional abort hook. The token stays pending until the promise settles.
	function timedPromise(factory, timeoutMs, onTimeout) {
		return new Promise(resolve => {
			let settled = false;
			let timedOut = false;
			const token = {};
			const timer = setT(() => {
				if (settled) {
					return;
				}
				timedOut = true;
				pending.add(token);
				if (onTimeout) {
					try {
						onTimeout();
					} catch {
						// abort is best effort; the token stays until settlement
					}
				}
				resolve({ outcome: 'timeout' });
			}, timeoutMs);
			const finish = result => {
				if (settled) {
					return;
				}
				settled = true;
				clearT(timer);
				if (timedOut) {
					pending.delete(token);
					notify();
					return;
				}
				resolve(result);
			};
			let promise;
			try {
				promise = Promise.resolve(factory());
			} catch (error) {
				finish({ outcome: 'error', error });
				return;
			}
			promise.then(value => finish({ outcome: 'ok', value }), error => finish({ outcome: 'error', error }));
		});
	}

	async function sha256(bytes) {
		if (!a.subtle || typeof a.subtle.digest !== 'function') {
			throw new Stop('unsupported');
		}
		const r = await timedPromise(() => a.subtle.digest('SHA-256', bytes), callbackTimeoutMs);
		if (r.outcome === 'timeout') {
			throw new Stop('timeout');
		}
		if (r.outcome !== 'ok') {
			throw new Stop('internal-error');
		}
		return hex(r.value);
	}

	// ---- WebStorage snapshot (read-only; reports count + SHA-256 only) ----

	function readArea(getter) {
		let storage;
		try {
			storage = getter();
		} catch {
			throw new Stop('storage-unavailable');
		}
		if (!storage) {
			throw new Stop('storage-unavailable');
		}
		try {
			const n = storage.length;
			if (!Number.isInteger(n) || n < 0) {
				throw new Stop('storage-unavailable');
			}
			const pairs = [];
			for (let i = 0; i < n; ++i) {
				const key = storage.key(i);
				if (typeof key !== 'string') {
					throw new Stop('storage-unstable');
				}
				const value = storage.getItem(key);
				if (typeof value !== 'string') {
					throw new Stop('storage-unstable');
				}
				pairs.push([key, value]);
			}
			if (storage.length !== n) {
				throw new Stop('storage-unstable');
			}
			pairs.sort((x, y) => (x[0] < y[0] ? -1 : x[0] > y[0] ? 1 : 0));
			for (let i = 1; i < pairs.length; ++i) {
				if (pairs[i][0] === pairs[i - 1][0]) {
					throw new Stop('storage-unstable');
				}
			}
			// JSON of [[key, value], ...] is an unambiguous serialization.
			return JSON.stringify(pairs);
		} catch (error) {
			throw error instanceof Stop ? error : new Stop('storage-unavailable');
		}
	}

	async function snapshotArea(getter) {
		const first = readArea(getter);
		const second = readArea(getter);
		if (first !== second) {
			throw new Stop('storage-unstable');
		}
		const count = JSON.parse(first).length;
		return { count, sha256: await sha256(new TextEncoder().encode(first)) };
	}

	async function snapshot() {
		const s = a.storages || {};
		if (typeof s.local !== 'function' || typeof s.session !== 'function') {
			throw new Stop('storage-unavailable');
		}
		return { local: await snapshotArea(s.local), session: await snapshotArea(s.session) };
	}

	const sameSnapshot = (x, y) => !!x && !!y
		&& x.local.count === y.local.count && x.local.sha256 === y.local.sha256
		&& x.session.count === y.session.count && x.session.sha256 === y.session.sha256;

	// ---- TEMPORARY filesystem, six exact paths, create:false only ----

	async function openFilesystem() {
		if (typeof a.requestFileSystem !== 'function' || typeof a.temporaryType !== 'number') {
			throw new Stop('unsupported');
		}
		const r = await callbackOp((ok, fail) => a.requestFileSystem(a.temporaryType, 0, ok, fail));
		if (r.outcome === 'timeout') {
			throw new Stop('timeout');
		}
		if (r.outcome !== 'ok' || !r.value || !r.value.root || typeof r.value.root.getFile !== 'function') {
			throw new Stop('filesystem-unavailable');
		}
		return r.value;
	}

	// Classify one target. Returns { path, state, code, entry? } where state is
	// missing | match | mismatch | failure. Never creates or normalizes.
	async function examine(fs, target) {
		const base = { path: target.path };
		const r = await callbackOp((ok, fail) => fs.root.getFile(target.path, { create: false }, ok, fail));
		if (r.outcome === 'timeout') {
			return { ...base, state: 'failure', code: 'timeout' };
		}
		if (r.outcome === 'error') {
			if (isGenuineNotFound(r.error)) {
				return { ...base, state: 'missing', code: null };
			}
			if (r.error && r.error.name === 'TypeMismatchError') {
				return { ...base, state: 'failure', code: 'type-mismatch' };
			}
			return { ...base, state: 'failure', code: 'lookup-error' };
		}
		const entry = r.value;
		if (!entry || typeof entry !== 'object') {
			return { ...base, state: 'failure', code: 'lookup-error' };
		}
		if (entry.isDirectory === true) {
			return { ...base, state: 'failure', code: 'directory' };
		}
		const name = target.path.slice(target.path.lastIndexOf('/') + 1);
		if (entry.isFile !== true || entry.isDirectory !== false || entry.fullPath !== '/' + target.path || entry.name !== name) {
			return { ...base, state: 'mismatch', code: 'identity-mismatch' };
		}
		if (typeof entry.file !== 'function') {
			return { ...base, state: 'failure', code: 'unsupported' };
		}
		const f = await callbackOp((ok, fail) => entry.file(ok, fail));
		if (f.outcome === 'timeout') {
			return { ...base, state: 'failure', code: 'timeout' };
		}
		if (f.outcome !== 'ok' || !f.value) {
			return { ...base, state: 'failure', code: 'read-error' };
		}
		const file = f.value;
		if (file.size !== target.bytes) {
			return { ...base, state: 'mismatch', code: 'size-mismatch' };
		}
		if (typeof file.arrayBuffer !== 'function') {
			return { ...base, state: 'failure', code: 'unsupported' };
		}
		const b = await timedPromise(() => file.arrayBuffer(), callbackTimeoutMs);
		if (b.outcome === 'timeout') {
			return { ...base, state: 'failure', code: 'timeout' };
		}
		if (b.outcome !== 'ok' || !(b.value instanceof ArrayBuffer)) {
			return { ...base, state: 'failure', code: 'read-error' };
		}
		if (b.value.byteLength !== target.bytes) {
			return { ...base, state: 'mismatch', code: 'size-mismatch' };
		}
		let digest;
		try {
			digest = await sha256(b.value);
		} catch (error) {
			return { ...base, state: 'failure', code: error instanceof Stop ? error.code : 'internal-error' };
		}
		if (digest !== target.sha256) {
			return { ...base, state: 'mismatch', code: 'content-mismatch' };
		}
		return { ...base, state: 'match', code: null, entry };
	}

	async function examineAll(fs) {
		const out = [];
		for (const target of targets) {
			out.push(await examine(fs, target));
		}
		return out;
	}

	const publicTarget = t => ({ path: t.path, state: t.state, code: t.code });
	const counts = list => {
		const c = { missing: 0, match: 0, mismatch: 0, failure: 0 };
		for (const t of list) {
			c[t.state] += 1;
		}
		return c;
	};

	// ---- HTTP (same origin, redirect:'error', bounded bodies) ----

	async function fetchBounded(url, cacheMode, expect) {
		const record = { url, cache: cacheMode, status: null, bytes: null, content: null, code: null };
		if (typeof a.fetch !== 'function' || typeof a.AbortController !== 'function') {
			return { ...record, code: 'unsupported' };
		}
		if (!sameUrlOrigin(url, origin)) {
			return { ...record, code: 'foreign-response' };
		}
		const controller = new a.AbortController();
		const r = await timedPromise(() => a.fetch(url, {
			method: 'GET',
			cache: cacheMode,
			redirect: 'error',
			credentials: 'same-origin',
			signal: controller.signal
		}), fetchTimeoutMs, () => controller.abort());
		if (r.outcome === 'timeout') {
			return { ...record, code: 'timeout' };
		}
		if (r.outcome !== 'ok' || !r.value) {
			return { ...record, code: 'fetch-error' };
		}
		const res = r.value;
		record.status = typeof res.status === 'number' ? res.status : null;
		if (res.redirected !== false || res.url !== url) {
			return { ...record, code: 'redirected' };
		}
		if (res.type !== 'basic') {
			return { ...record, code: 'foreign-response' };
		}
		const okStatus = res.status === expect.status;
		const cap = expect.status === 200 ? expect.bytes : ERROR_BODY_CAP;
		const reader = res.body && typeof res.body.getReader === 'function' ? res.body.getReader() : null;
		if (!reader) {
			return { ...record, code: 'unsupported' };
		}
		const chunks = [];
		let total = 0;
		for (;;) {
			const step = await timedPromise(() => reader.read(), fetchTimeoutMs, () => controller.abort());
			if (step.outcome === 'timeout') {
				return { ...record, code: 'timeout' };
			}
			if (step.outcome !== 'ok' || !step.value) {
				return { ...record, code: 'fetch-error' };
			}
			if (step.value.done) {
				break;
			}
			const chunk = step.value.value;
			if (!(chunk instanceof Uint8Array)) {
				return { ...record, code: 'fetch-error' };
			}
			total += chunk.byteLength;
			if (total > cap) {
				try {
					reader.cancel();
				} catch {
					// cancellation is best effort; the read already failed
				}
				return { ...record, bytes: total, code: 'body-too-large' };
			}
			if (okStatus && expect.status === 200) {
				chunks.push(chunk);
			}
		}
		record.bytes = total;
		if (!okStatus) {
			const stale = expect.status === 404 && res.status === 200 && cacheMode === 'default';
			return { ...record, code: stale ? 'stale-default-response' : 'unexpected-status' };
		}
		if (expect.status === 200) {
			if (total !== expect.bytes) {
				return { ...record, content: 'mismatch', code: 'size-mismatch' };
			}
			const body = new Uint8Array(total);
			let offset = 0;
			for (const chunk of chunks) {
				body.set(chunk, offset);
				offset += chunk.byteLength;
			}
			let digest;
			try {
				digest = await sha256(body);
			} catch (error) {
				return { ...record, code: error instanceof Stop ? error.code : 'internal-error' };
			}
			if (digest !== expect.sha256) {
				return { ...record, content: 'mismatch', code: 'content-mismatch' };
			}
			record.content = 'match';
		}
		return record;
	}

	function nonce() {
		if (typeof a.getRandomValues !== 'function') {
			throw new Stop('unsupported');
		}
		const raw = new Uint8Array(16);
		a.getRandomValues(raw);
		return hex(raw.buffer);
	}

	function preflightUrl() {
		const base = a.onlineBase;
		let parsed;
		try {
			parsed = new URL(base);
		} catch {
			throw new Stop('unsupported');
		}
		if (parsed.origin !== origin || !parsed.pathname.endsWith('/Online.js') || parsed.search || parsed.hash) {
			throw new Stop('origin-refused');
		}
		return parsed.href + '?t05_008_preflight=' + nonce();
	}

	// ---- action runner ----

	async function run(action, mutating, body) {
		const seq = ++sequence;
		const report = {
			task: TASK,
			profile: PROFILE_NAME,
			action,
			sequence: seq,
			state: 'failed',
			code: null,
			storage: { before: null, after: null, unchanged: false }
		};
		if (busy) {
			return { ...report, state: 'refused', code: 'busy', lock: status() };
		}
		if (a.origin !== origin) {
			return { ...report, state: 'refused', code: 'origin-refused', lock: status() };
		}
		if (mutating && pending.size > 0) {
			return { ...report, state: 'refused', code: 'callback-pending', lock: status() };
		}
		if (mutating && locked) {
			return { ...report, state: 'refused', code: 'mutation-locked', lock: status() };
		}
		if (typeof setT !== 'function' || typeof clearT !== 'function') {
			return { ...report, state: 'refused', code: 'unsupported', lock: status() };
		}
		busy = true;
		notify();
		const ctx = { mutated: false, uncertain: false };
		try {
			report.storage.before = await snapshot();
			const outcome = await body(report, ctx);
			report.storage.after = await snapshot();
			report.storage.unchanged = sameSnapshot(report.storage.before, report.storage.after);
			if (!report.storage.unchanged) {
				throw new Stop('storage-changed');
			}
			report.state = outcome;
		} catch (error) {
			const code = error instanceof Stop ? error.code : 'internal-error';
			report.code = code;
			if (report.storage.before && !report.storage.after) {
				try {
					report.storage.after = await snapshot();
					report.storage.unchanged = sameSnapshot(report.storage.before, report.storage.after);
				} catch {
					report.storage.unchanged = false;
				}
			}
			if (ctx.uncertain || code === 'timeout') {
				report.state = 'uncertain';
			} else if (mutating && !ctx.mutated && code !== 'storage-changed' && report.storage.unchanged) {
				report.state = 'refused';
			} else {
				report.state = 'failed';
			}
			if (ctx.mutated) {
				locked = true;
			}
		} finally {
			busy = false;
		}
		report.lock = status();
		notify();
		return report;
	}

	function inspect() {
		const startedClear = pending.size === 0;
		return run('inspect-cache', false, async (report, ctx) => {
			const fs = await openFilesystem();
			const list = await examineAll(fs);
			report.targets = list.map(publicTarget);
			report.counts = counts(list);
			report.removal_eligible = list.every(t => t.state === 'missing' || t.state === 'match');
			report.all_absent = list.every(t => t.state === 'missing');
			if (list.some(t => t.state === 'failure')) {
				const first = list.find(t => t.state === 'failure');
				throw new Stop(first.code || 'lookup-error');
			}
			return 'inspected';
		}).then(report => {
			// Only a complete, clean inspection that began and ended with no
			// outstanding callback may release an earlier uncertain mutation.
			if (locked && startedClear && pending.size === 0 && report.state === 'inspected'
				&& report.removal_eligible && report.storage.unchanged) {
				locked = false;
				report.lock = status();
				report.released_lock = true;
				notify();
			}
			return report;
		});
	}

	function remove() {
		return run('remove-verified-cache', true, async (report, ctx) => {
			const fs = await openFilesystem();
			const fresh = await examineAll(fs);
			report.targets = fresh.map(publicTarget);
			report.precheck = counts(fresh);
			report.removed = 0;
			if (!fresh.every(t => t.state === 'missing' || t.state === 'match')) {
				throw new Stop('precondition-failed');
			}
			const steps = [];
			report.steps = steps;
			for (let i = 0; i < targets.length; ++i) {
				if (fresh[i].state !== 'match') {
					continue;
				}
				const again = await examine(fs, targets[i]);
				if (again.state !== 'match') {
					steps.push({ path: targets[i].path, step: 'revalidate', state: again.state, code: again.code });
					throw new Stop(again.state === 'failure' && again.code === 'timeout' ? 'timeout' : 'changed-before-delete');
				}
				if (typeof again.entry.remove !== 'function') {
					throw new Stop('unsupported');
				}
				ctx.mutated = true;
				const r = await callbackOp((ok, fail) => again.entry.remove(ok, fail));
				if (r.outcome === 'timeout') {
					ctx.uncertain = true;
					steps.push({ path: targets[i].path, step: 'remove', state: 'uncertain', code: 'timeout' });
					throw new Stop('timeout');
				}
				if (r.outcome !== 'ok') {
					ctx.uncertain = true;
					steps.push({ path: targets[i].path, step: 'remove', state: 'failed', code: 'remove-error' });
					throw new Stop('remove-error');
				}
				steps.push({ path: targets[i].path, step: 'remove', state: 'removed', code: null });
				report.removed += 1;
			}
			// Independent reopen of all six: every one must be genuinely absent.
			const post = await examineAll(fs);
			report.postcheck = post.map(publicTarget);
			if (!post.every(t => t.state === 'missing')) {
				const failure = post.find(t => t.state === 'failure');
				throw new Stop(failure && failure.code === 'timeout' ? 'timeout' : 'still-present');
			}
			return 'removed-verified';
		});
	}

	function refresh(mode) {
		const action = mode === 'original' ? 'refresh-http-original' : mode === 'repaired' ? 'refresh-http-repaired' : 'refresh-http';
		if (mode !== 'original' && mode !== 'repaired') {
			return Promise.resolve({ task: TASK, profile: PROFILE_NAME, action, sequence: ++sequence, state: 'refused', code: 'bad-mode', lock: status() });
		}
		const bundle = bundles[mode];
		return run(action, true, async (report, ctx) => {
			report.mode = mode;
			const fs = await openFilesystem();
			const pre = await examineAll(fs);
			report.targets = pre.map(publicTarget);
			if (!pre.every(t => t.state === 'missing')) {
				const failure = pre.find(t => t.state === 'failure');
				throw new Stop(failure && failure.code === 'timeout' ? 'timeout' : 'filesystem-not-absent');
			}
			// Current server bundle bytes only; this is not execution evidence.
			const preflight = await fetchBounded(preflightUrl(), 'no-store', { status: 200, bytes: bundle.bytes, sha256: bundle.sha256 });
			report.preflight = { ...preflight, url: 'Online.js' };
			if (preflight.code) {
				throw new Stop(preflight.code === 'timeout' ? 'timeout' : 'bundle-stage-mismatch');
			}
			const expectFor = target => (mode === 'original' ? { status: 404 } : { status: 200, bytes: target.bytes, sha256: target.sha256 });
			const http = [];
			report.http = http;
			for (const phase of ['reload', 'default']) {
				for (const target of targets) {
					if (phase === 'reload') {
						ctx.mutated = true;
					}
					const result = await fetchBounded(aliasUrl(target.path, origin), phase, expectFor(target));
					http.push({ path: target.path, phase, status: result.status, bytes: result.bytes, content: result.content, code: result.code });
					if (result.code) {
						if (result.code === 'timeout') {
							ctx.uncertain = true;
						}
						throw new Stop(result.code);
					}
				}
			}
			const post = await examineAll(fs);
			report.postcheck = post.map(publicTarget);
			if (!post.every(t => t.state === 'missing')) {
				const failure = post.find(t => t.state === 'failure');
				throw new Stop(failure && failure.code === 'timeout' ? 'timeout' : 'still-present');
			}
			return 'refreshed-verified';
		});
	}

	return { inspect, remove, refresh, status };
}

/**
 * Production binding for the generated T05_008-cache.html. Uses the actual
 * browser APIs and the fixed pins; no test seam is reachable from here.
 */
export function bindBrowser(win) {
	const doc = win.document;
	const report = doc.getElementById(IDS.report);
	const buttons = {
		inspect: doc.getElementById(IDS.inspect),
		remove: doc.getElementById(IDS.remove),
		original: doc.getElementById(IDS.original),
		repaired: doc.getElementById(IDS.repaired)
	};
	report.setAttribute('data-bound', '1');
	const render = value => {
		report.textContent = JSON.stringify(value, null, 2);
	};
	const all = Object.values(buttons);
	all.forEach(b => {
		if (b) {
			b.disabled = true;
		}
	});
	if (all.some(b => !b)) {
		render({ task: TASK, state: 'refused', code: 'unsupported' });
		return null;
	}
	if (win.location.origin !== ORIGIN) {
		render({ task: TASK, state: 'refused', code: 'origin-refused' });
		return null;
	}
	let verifier = null;
	let latest = 0;
	let running = false;
	const sync = st => {
		const s = st || (verifier ? verifier.status() : null);
		const idle = !!s && !s.busy && !running;
		buttons.inspect.disabled = !idle;
		const mutable = idle && s.can_mutate;
		buttons.remove.disabled = !mutable;
		buttons.original.disabled = !mutable;
		buttons.repaired.disabled = !mutable;
	};
	const rfs = win.requestFileSystem || win.webkitRequestFileSystem;
	const crypto = win.crypto;
	verifier = createVerifier({
		origin: win.location.origin,
		requestFileSystem: typeof rfs === 'function' ? (type, size, ok, fail) => rfs.call(win, type, size, ok, fail) : null,
		temporaryType: win.TEMPORARY,
		storages: { local: () => win.localStorage, session: () => win.sessionStorage },
		fetch: typeof win.fetch === 'function' ? (url, init) => win.fetch(url, init) : null,
		AbortController: win.AbortController,
		subtle: crypto && crypto.subtle,
		getRandomValues: crypto && typeof crypto.getRandomValues === 'function' ? array => crypto.getRandomValues(array) : null,
		setTimeout: (fn, ms) => win.setTimeout(fn, ms),
		clearTimeout: id => win.clearTimeout(id),
		onlineBase: new URL('Online.js', doc.baseURI).href,
		onChange: st => sync(st)
	});
	const start = (action, call) => () => {
		if (running) {
			return;
		}
		running = true;
		const mine = ++latest;
		sync();
		render({ task: TASK, action, state: 'running' });
		call().then(result => {
			if (mine === latest) {
				render(result);
			}
		}, () => {
			if (mine === latest) {
				render({ task: TASK, action, state: 'failed', code: 'internal-error', lock: verifier.status() });
			}
		}).then(() => {
			running = false;
			sync();
		});
	};
	buttons.inspect.addEventListener('click', start('inspect-cache', () => verifier.inspect()));
	buttons.remove.addEventListener('click', start('remove-verified-cache', () => verifier.remove()));
	buttons.original.addEventListener('click', start('refresh-http-original', () => verifier.refresh('original')));
	buttons.repaired.addEventListener('click', start('refresh-http-repaired', () => verifier.refresh('repaired')));
	render({ task: TASK, profile: PROFILE_NAME, state: 'ready', note: 'No action has run. Inspection is read-only; nothing runs automatically.', lock: verifier.status() });
	sync();
	return verifier;
}

if (typeof window !== 'undefined' && typeof document !== 'undefined' && document.documentElement
	&& document.documentElement.getAttribute('data-t05008') === 'cache' && document.getElementById(IDS.report)) {
	bindBrowser(window);
}
