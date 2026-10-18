// T05.008: Node built-in tests for navigation_browser_cache.mjs and the two
// generated inline loaders (entry expression and cache-page loader).
//
// Everything is an authored double: a legacy TEMPORARY filesystem, WebStorage
// areas, fetch/Response/stream doubles and a minimal DOM for the loaders.
// Node's WebCrypto is used as-is. The cache core runs with tiny authored pins
// through its internal test seam; the production pins are compared with the
// generator's embedded profile. No browser, listener, real cache, network,
// bootstrap or game code runs: native SRI enforcement, the legacy filesystem
// API and HTTP-cache behavior are root's browser checks, reported NOT RUN.
//
//   node --test tools/renewal/test_navigation_browser_cache.mjs

import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createHash, webcrypto } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import vm from 'node:vm';
import { fileURLToPath, pathToFileURL } from 'node:url';

import {
	ORIGIN, TARGETS, BUNDLES, IDS, CODES, PROFILE_NAME, TASK,
	aliasUrl, bindBrowser, createVerifier, isGenuineNotFound
} from './navigation_browser_cache.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const modulePath = path.join(here, 'navigation_browser_cache.mjs');
const generator = path.join(here, 'navigation_browser_verifier.py');
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const sri = hex => 'sha256-' + Buffer.from(hex, 'hex').toString('base64');
const encode = text => new TextEncoder().encode(text);

// ------------------------------------------------------------ authored pins

const BYTES = TARGETS.map((t, i) => encode('authored navigation stand-in ' + i + ' ' + 'x'.repeat(i * 7)));
const PINS_TARGETS = TARGETS.map((t, i) => ({ path: t.path, bytes: BYTES[i].length, sha256: sha(BYTES[i]) }));
const ORIGINAL_JS = encode('export const stage = "original";\n');
const REPAIRED_JS = encode('export const stage = "repaired-stage";\n');
const PINS_BUNDLES = {
	original: { bytes: ORIGINAL_JS.length, sha256: sha(ORIGINAL_JS) },
	repaired: { bytes: REPAIRED_JS.length, sha256: sha(REPAIRED_JS) }
};
const ONLINE_BASE = ORIGIN + '/Online.js';
const SECRET_KEY = 'session-token-key';
const SECRET_VALUE = 'very-private-credential-value';

// ------------------------------------------------------------ filesystem double

function domError(name, code) {
	const e = new Error('authored ' + name + ' message must never be reported');
	e.name = name;
	if (code !== undefined) {
		e.code = code;
	}
	return e;
}

// files: Map path -> { bytes, isFile, isDirectory, fullPath, name, lookupError, readError, removeError }
function makeFs(files, options = {}) {
	const log = [];
	const delay = options.delay || 0;
	const later = fn => (delay ? setTimeout(fn, delay) : queueMicrotask(fn));
	const hooks = options.hooks || {};
	const entryFor = (p, spec) => ({
		isFile: spec.isFile !== undefined ? spec.isFile : !spec.isDirectory,
		isDirectory: !!spec.isDirectory,
		fullPath: spec.fullPath !== undefined ? spec.fullPath : '/' + p,
		name: spec.name !== undefined ? spec.name : p.slice(p.lastIndexOf('/') + 1),
		file(ok, fail) {
			log.push({ op: 'file', path: p });
			if (hooks.file) {
				hooks.file(p, spec);
			}
			const current = files.get(p) || spec;
			later(() => {
				if (current.readError) {
					fail(current.readError);
					return;
				}
				const bytes = current.bytes;
				ok({ size: current.size !== undefined ? current.size : bytes.length, arrayBuffer: async () => bytes.slice().buffer });
			});
		},
		remove(ok, fail) {
			log.push({ op: 'remove', path: p });
			if (spec.removeNever) {
				spec.removeLater = () => { files.delete(p); ok(); };
				return;
			}
			later(() => {
				if (spec.removeError) {
					fail(spec.removeError);
					return;
				}
				files.delete(p);
				if (hooks.removed) {
					hooks.removed(p);
				}
				ok();
			});
		}
	});
	const root = new Proxy({
		getFile(p, opts, ok, fail) {
			log.push({ op: 'getFile', path: p, create: opts && opts.create });
			if (hooks.getFile) {
				hooks.getFile(p);
			}
			const spec = files.get(p);
			if (spec && spec.lookupNever) {
				spec.lookupLater = () => fail(domError('NotFoundError', 8));
				return;
			}
			later(() => {
				if (!spec) {
					fail(options.notFound ? options.notFound() : domError('NotFoundError', 8));
					return;
				}
				if (spec.lookupError) {
					fail(spec.lookupError);
					return;
				}
				ok(entryFor(p, spec));
			});
		}
	}, {
		get(target, prop) {
			if (prop !== 'getFile') {
				log.push({ op: 'root-access', prop: String(prop) });
			}
			return target[prop];
		}
	});
	const requestFileSystem = (type, size, ok, fail) => {
		log.push({ op: 'requestFileSystem', type, size });
		later(() => ok({ name: 'temporary', root }));
	};
	return { files, log, requestFileSystem };
}

const matchingFiles = () => new Map(PINS_TARGETS.map((t, i) => [t.path, { bytes: BYTES[i] }]));

// ------------------------------------------------------------ storage double

class Area {
	constructor(entries = {}) {
		this.map = new Map(Object.entries(entries));
		this.reads = 0;
		this.writes = 0;
	}
	get length() {
		return this.map.size;
	}
	key(i) {
		this.reads += 1;
		return [...this.map.keys()][i] ?? null;
	}
	getItem(k) {
		this.reads += 1;
		return this.map.has(k) ? this.map.get(k) : null;
	}
	setItem() {
		this.writes += 1;
		throw new Error('the verifier must never write storage');
	}
	removeItem() {
		this.writes += 1;
		throw new Error('the verifier must never write storage');
	}
	clear() {
		this.writes += 1;
		throw new Error('the verifier must never write storage');
	}
}

// ------------------------------------------------------------ fetch double

function streamOf(bytes, chunk = 5) {
	let offset = 0;
	return {
		getReader() {
			return {
				async read() {
					if (offset >= bytes.length) {
						return { done: true, value: undefined };
					}
					const value = bytes.slice(offset, offset + chunk);
					offset += chunk;
					return { done: false, value };
				},
				cancel() {}
			};
		}
	};
}

function response(url, status, bytes, extra = {}) {
	return { status, ok: status >= 200 && status < 300, url, redirected: false, type: 'basic', body: streamOf(bytes || new Uint8Array(0)), ...extra };
}

// route(url, init, phaseIndex) -> response | Promise | throws
function makeFetch(route) {
	const log = [];
	const fetchFn = async (url, init) => {
		log.push({ url, init: { ...init, signal: undefined }, hasSignal: !!(init && init.signal) });
		return route(url, init, log.length - 1);
	};
	return { log, fetch: fetchFn };
}

function serverRoute(mode, overrides = {}) {
	return (url, init) => {
		if (overrides[url + '|' + init.cache]) {
			return overrides[url + '|' + init.cache](url, init);
		}
		if (url.startsWith(ONLINE_BASE + '?')) {
			return response(url, 200, mode === 'repaired' ? REPAIRED_JS : ORIGINAL_JS);
		}
		const i = PINS_TARGETS.findIndex(t => aliasUrl(t.path) === url);
		if (i < 0) {
			throw new Error('unexpected URL');
		}
		return mode === 'repaired' ? response(url, 200, BYTES[i]) : response(url, 404, encode('Not Found'));
	};
}

// ------------------------------------------------------------ verifier factory

function setup({ files = new Map(), fsOptions = {}, route = serverRoute('original'), local, session, adapters = {}, pins = {} } = {}) {
	const fsd = makeFs(files, fsOptions);
	const f = makeFetch(route);
	const areas = {
		local: local || new Area({ [SECRET_KEY]: SECRET_VALUE, lang: 'zh-TW' }),
		session: session || new Area({ s: SECRET_VALUE })
	};
	const changes = [];
	const aborts = [];
	class Abort {
		constructor() {
			this.signal = { aborted: false };
		}
		abort() {
			this.signal.aborted = true;
			aborts.push(true);
		}
	}
	const verifier = createVerifier({
		origin: ORIGIN,
		requestFileSystem: fsd.requestFileSystem,
		temporaryType: 0,
		storages: { local: () => areas.local, session: () => areas.session },
		fetch: f.fetch,
		AbortController: Abort,
		subtle: webcrypto.subtle,
		getRandomValues: a => webcrypto.getRandomValues(a),
		setTimeout,
		clearTimeout,
		onlineBase: ONLINE_BASE,
		onChange: st => changes.push(st),
		...adapters
	}, { targets: PINS_TARGETS, bundles: PINS_BUNDLES, callbackTimeoutMs: 200, fetchTimeoutMs: 200, ...pins });
	return { verifier, fsd, fetchLog: f.log, areas, changes, aborts };
}

const ops = (log, op) => log.filter(e => e.op === op);
const targetPaths = new Set(PINS_TARGETS.map(t => t.path));

function assertScoped(fsd, fetchLog = []) {
	for (const e of fsd.log) {
		assert.notEqual(e.op, 'root-access', 'root.' + e.prop + ' must not be used');
		if (e.path !== undefined) {
			assert.ok(targetPaths.has(e.path), 'non-target filesystem operation: ' + e.path);
		}
		if (e.op === 'getFile') {
			assert.equal(e.create, false);
		}
		if (e.op === 'requestFileSystem') {
			assert.equal(e.type, 0);
		}
	}
	const allowed = new Set(PINS_TARGETS.map(t => aliasUrl(t.path)));
	for (const e of fetchLog) {
		assert.equal(e.init.redirect, 'error');
		assert.equal(e.init.method, 'GET');
		assert.ok(e.hasSignal);
		assert.ok(allowed.has(e.url) || e.url.startsWith(ONLINE_BASE + '?t05_008_preflight='), 'unexpected URL ' + e.url);
	}
}

function assertPrivate(report, areas) {
	const text = JSON.stringify(report);
	assert.ok(!text.includes(SECRET_KEY) && !text.includes(SECRET_VALUE) && !text.includes('zh-TW'));
	assert.ok(!text.includes('authored') && !text.includes('message must never'), 'exception text leaked');
	assert.ok(!/stack|Error:/.test(text));
	assert.equal(areas.local.writes, 0);
	assert.equal(areas.session.writes, 0);
	if (report.code !== null && report.code !== undefined) {
		assert.ok(CODES.includes(report.code), 'unknown code ' + report.code);
	}
}

// ======================================================== module and pins

test('C01 importing the module starts nothing and binds nothing without the cache document', () => {
	const probe = `
		const hit = [];
		globalThis.fetch = () => { hit.push('fetch'); throw new Error('x'); };
		globalThis.webkitRequestFileSystem = () => hit.push('fs');
		globalThis.window = globalThis;
		globalThis.document = { documentElement: { getAttribute: () => null }, getElementById: () => { hit.push('dom'); return null; } };
		Object.defineProperty(globalThis, 'localStorage', { get() { hit.push('storage'); return null; } });
		await import(${JSON.stringify(pathToFileURL(modulePath).href)});
		process.stdout.write(JSON.stringify(hit));`;
	const r = spawnSync(process.execPath, ['--input-type=module', '-e', probe], { encoding: 'utf8' });
	assert.equal(r.status, 0, r.stderr);
	assert.deepEqual(JSON.parse(r.stdout), []);
});

test('C02 production pins equal the generator profile; alias URLs follow FileManager encoding', () => {
	const r = spawnSync('python3', ['-I', '-B', '-c',
		'import sys, json; sys.path.insert(0, sys.argv[1]); import navigation_browser_verifier as g; sys.stdout.write(json.dumps(g.PROFILE))', here], { encoding: 'utf8' });
	assert.equal(r.status, 0, r.stderr);
	const profile = JSON.parse(r.stdout);
	assert.equal(TASK, profile.task);
	assert.equal(PROFILE_NAME, profile.profile);
	assert.equal(ORIGIN, profile.origin);
	assert.deepEqual(TARGETS.map(t => ({ ...t })), profile.targets);
	assert.deepEqual({ original: { ...BUNDLES.original }, repaired: { ...BUNDLES.repaired } }, profile.bundles);
	assert.deepEqual(Object.values(IDS).sort(), profile.element_ids.filter(id => id !== 'T05_008-entry-status').sort());
	assert.equal(aliasUrl(TARGETS[0].path), 'http://127.0.0.1:3338/data/luafiles514/lua%20files/navigation/navi_map_krpri.lub');
	for (const t of TARGETS) {
		const fm = '/' + t.path.replace(/[^/]+/g, s => encodeURIComponent(s));
		assert.equal(aliasUrl(t.path), ORIGIN + fm);
	}
});

test('C03 source scan: no forbidden API in executable module code', () => {
	const code = fs.readFileSync(modulePath, 'utf8').split('\n').filter(line => !/^\s*\/\//.test(line)).join('\n');
	for (const bad of ['createReader', 'removeRecursively', 'getDirectory', 'indexedDB', 'caches', 'cookie', 'PERSISTENT',
		'setItem', 'removeItem', '.clear(', 'eval(', 'new Function', 'create: true', 'innerHTML', 'Blob', 'import(', 'sendBeacon',
		'XMLHttpRequest', 'postMessage', 'https://', 'localStorage.', 'sessionStorage.']) {
		assert.ok(!code.includes(bad), 'forbidden token in module: ' + bad);
	}
	assert.ok(code.includes("{ create: false }"));
	assert.equal((code.match(/redirect: 'error'/g) || []).length, 1, 'the single fetch call site uses redirect:error');
	assert.equal((code.match(/a\.fetch\(/g) || []).length, 1);
	assert.equal((code.match(/\.remove\(ok, fail\)/g) || []).length, 1, 'one file-only remove call site');
});

test('C04 genuine not-found classification', () => {
	assert.ok(isGenuineNotFound(domError('NotFoundError', 8)));
	assert.ok(isGenuineNotFound(domError('NotFoundError')));
	assert.ok(isGenuineNotFound({ code: 1 }));
	assert.ok(isGenuineNotFound({ name: 'FileError', code: 1 }));
	assert.ok(!isGenuineNotFound(domError('SecurityError', 1)));
	assert.ok(!isGenuineNotFound(domError('SecurityError', 18)));
	assert.ok(!isGenuineNotFound(domError('NotReadableError', 1)));
	assert.ok(!isGenuineNotFound({ code: 2 }));
	assert.ok(!isGenuineNotFound(domError('NotFoundError', 2)));
	assert.ok(!isGenuineNotFound(null));
	assert.ok(!isGenuineNotFound('NotFoundError'));
});

// ======================================================== inspection

test('C05 inspect: all six missing is read-only and private', async () => {
	const s = setup();
	const r = await s.verifier.inspect();
	assert.equal(r.state, 'inspected');
	assert.equal(r.code, null);
	assert.equal(r.all_absent, true);
	assert.equal(r.removal_eligible, true);
	assert.deepEqual(r.counts, { missing: 6, match: 0, mismatch: 0, failure: 0 });
	assert.equal(r.storage.unchanged, true);
	assert.equal(r.storage.before.local.count, 2);
	assert.match(r.storage.before.local.sha256, /^[0-9a-f]{64}$/);
	assert.equal(ops(s.fsd.log, 'remove').length, 0);
	assert.equal(s.fetchLog.length, 0);
	assertScoped(s.fsd);
	assertPrivate(r, s.areas);
});

test('C06 inspect: all six exact matching files', async () => {
	const s = setup({ files: matchingFiles() });
	const r = await s.verifier.inspect();
	assert.equal(r.state, 'inspected');
	assert.deepEqual(r.counts, { missing: 0, match: 6, mismatch: 0, failure: 0 });
	assert.equal(r.removal_eligible, true);
	assert.equal(r.all_absent, false);
	assert.equal(ops(s.fsd.log, 'remove').length, 0);
	assert.equal(s.fsd.files.size, 6);
	assertScoped(s.fsd);
});

test('C07 storage snapshot is order independent and unambiguous', async () => {
	const a = setup({ local: new Area({ a: '1', b: '2' }), session: new Area({}) });
	const b = setup({ local: new Area({ b: '2', a: '1' }), session: new Area({}) });
	const c = setup({ local: new Area({ 'a","b': '' }), session: new Area({}) });
	const d = setup({ local: new Area({ a: '","b' }), session: new Area({}) });
	const [ra, rb, rc, rd] = await Promise.all([a, b, c, d].map(s => s.verifier.inspect()));
	assert.equal(ra.storage.before.local.sha256, rb.storage.before.local.sha256);
	assert.notEqual(rc.storage.before.local.sha256, rd.storage.before.local.sha256);
	assert.equal(ra.storage.before.session.count, 0);
});

const variants = {
	'wrong hash': (spec, i) => ({ bytes: (() => { const b = BYTES[i].slice(); b[0] ^= 1; return b; })() }),
	'wrong size': (spec, i) => ({ bytes: BYTES[i].slice(1) }),
	'wrong reported size': (spec, i) => ({ bytes: BYTES[i], size: BYTES[i].length + 1 }),
	'not a file': (spec, i) => ({ bytes: BYTES[i], isFile: false }),
	'wrong full path': (spec, i) => ({ bytes: BYTES[i], fullPath: '/DATA/' + PINS_TARGETS[i].path }),
	'wrong name': (spec, i) => ({ bytes: BYTES[i], name: 'other.lub' })
};
const expectedCode = {
	'wrong hash': 'content-mismatch', 'wrong size': 'size-mismatch', 'wrong reported size': 'size-mismatch',
	'not a file': 'identity-mismatch', 'wrong full path': 'identity-mismatch', 'wrong name': 'identity-mismatch'
};

for (const [label, make] of Object.entries(variants)) {
	test('C08 one target with ' + label + ' is a mismatch and refuses removal before any delete', async () => {
		const files = matchingFiles();
		files.set(PINS_TARGETS[3].path, make(null, 3));
		const s = setup({ files });
		const r = await s.verifier.inspect();
		assert.equal(r.state, 'inspected');
		assert.equal(r.removal_eligible, false);
		assert.deepEqual(r.targets[3], { path: PINS_TARGETS[3].path, state: 'mismatch', code: expectedCode[label] });
		const rm = await s.verifier.remove();
		assert.equal(rm.state, 'refused');
		assert.equal(rm.code, 'precondition-failed');
		assert.equal(rm.removed, 0);
		assert.equal(ops(s.fsd.log, 'remove').length, 0);
		assert.equal(s.fsd.files.size, 6);
		assert.equal(rm.lock.mutation_locked, false);
		assertScoped(s.fsd);
		assertPrivate(rm, s.areas);
	});
}

test('C09 a directory at a target path (entry or TypeMismatchError) is a failure and refuses removal', async () => {
	for (const spec of [{ isDirectory: true, bytes: new Uint8Array(0) }, { lookupError: domError('TypeMismatchError', 11) }]) {
		const files = matchingFiles();
		files.set(PINS_TARGETS[1].path, spec);
		const s = setup({ files });
		const r = await s.verifier.inspect();
		assert.equal(r.state, 'failed');
		assert.equal(r.targets[1].state, 'failure');
		assert.ok(['directory', 'type-mismatch'].includes(r.targets[1].code));
		const rm = await s.verifier.remove();
		assert.equal(rm.state, 'refused');
		assert.equal(rm.code, 'precondition-failed');
		assert.equal(ops(s.fsd.log, 'remove').length, 0);
		assertScoped(s.fsd);
	}
});

test('C10 genuine missing versus security/read errors', async () => {
	const legacy = setup({ fsOptions: { notFound: () => ({ code: 1 }) } });
	assert.equal((await legacy.verifier.inspect()).all_absent, true);

	const security = setup({ fsOptions: { notFound: () => domError('SecurityError', 1) } });
	const rs = await security.verifier.inspect();
	assert.equal(rs.state, 'failed');
	assert.equal(rs.code, 'lookup-error');
	assert.equal(rs.removal_eligible, false);
	assertPrivate(rs, security.areas);
	const rsm = await security.verifier.remove();
	assert.equal(rsm.code, 'precondition-failed');
	assert.equal((await security.verifier.refresh('original')).code, 'filesystem-not-absent');
	assert.equal(security.fetchLog.length, 0);

	const files = matchingFiles();
	files.set(PINS_TARGETS[5].path, { bytes: BYTES[5], readError: domError('NotReadableError', 1) });
	const read = setup({ files });
	const rr = await read.verifier.inspect();
	assert.deepEqual(rr.targets[5], { path: PINS_TARGETS[5].path, state: 'failure', code: 'read-error' });
	assert.equal((await read.verifier.remove()).code, 'precondition-failed');
	assert.equal(ops(read.fsd.log, 'remove').length, 0);
});

test('C11 unsupported filesystem API fails visibly with no other action', async () => {
	for (const adapters of [{ requestFileSystem: null }, { temporaryType: undefined }]) {
		const s = setup({ files: matchingFiles(), adapters });
		for (const r of [await s.verifier.inspect(), await s.verifier.remove(), await s.verifier.refresh('original')]) {
			assert.equal(r.code, 'unsupported');
			assert.notEqual(r.state, 'inspected');
		}
		assert.equal(s.fetchLog.length, 0);
		assert.equal(s.fsd.log.length, 0);
	}
	const noCrypto = setup({ adapters: { subtle: null } });
	const r = await noCrypto.verifier.inspect();
	assert.equal(r.code, 'unsupported');
	assert.equal(noCrypto.fsd.log.length, 0);
});

test('C12 wrong origin is refused before any read', async () => {
	const s = setup({ files: matchingFiles(), adapters: { origin: 'http://localhost:3338' } });
	for (const r of [await s.verifier.inspect(), await s.verifier.remove(), await s.verifier.refresh('repaired')]) {
		assert.equal(r.state, 'refused');
		assert.equal(r.code, 'origin-refused');
	}
	assert.equal(s.fsd.log.length, 0);
	assert.equal(s.fetchLog.length, 0);
	assert.equal(s.areas.local.reads, 0);
});

test('C13 WebStorage unavailable, unstable or changed is never a success', async () => {
	const throwing = setup({ adapters: { storages: { local: () => { throw domError('SecurityError', 18); }, session: () => new Area() } } });
	const r1 = await throwing.verifier.inspect();
	assert.equal(r1.code, 'storage-unavailable');
	assert.equal(throwing.fsd.log.length, 0);
	assertPrivate(r1, throwing.areas);

	const flaky = new Area({ k: 'v' });
	let n = 0;
	flaky.getItem = () => String(n++);
	const unstable = setup({ local: flaky });
	assert.equal((await unstable.verifier.inspect()).code, 'storage-unstable');

	const local = new Area({ [SECRET_KEY]: SECRET_VALUE });
	const changing = setup({ files: matchingFiles(), local, fsOptions: { hooks: { getFile: () => local.map.set('added', SECRET_VALUE) } } });
	const r3 = await changing.verifier.inspect();
	assert.equal(r3.state, 'failed');
	assert.equal(r3.code, 'storage-changed');
	assert.equal(r3.storage.unchanged, false);
	assertPrivate(r3, changing.areas);
});

// ======================================================== removal

test('C14 remove: all six verified copies removed, independently reopened and absent', async () => {
	const s = setup({ files: matchingFiles() });
	const r = await s.verifier.remove();
	assert.equal(r.state, 'removed-verified');
	assert.equal(r.code, null);
	assert.equal(r.removed, 6);
	assert.equal(s.fsd.files.size, 0);
	assert.deepEqual(r.postcheck.map(t => t.state), Array(6).fill('missing'));
	assert.equal(r.storage.unchanged, true);
	assert.equal(r.lock.mutation_locked, false);
	// Each removal is preceded by its own fresh revalidation (lookup + read).
	const seq = s.fsd.log.filter(e => e.op === 'getFile' || e.op === 'remove').map(e => e.op + ':' + PINS_TARGETS.findIndex(t => t.path === e.path));
	assert.deepEqual(seq.slice(0, 6), [0, 1, 2, 3, 4, 5].map(i => 'getFile:' + i));
	for (let i = 0; i < 6; ++i) {
		assert.deepEqual(seq.slice(6 + 2 * i, 8 + 2 * i), ['getFile:' + i, 'remove:' + i]);
	}
	assert.deepEqual(seq.slice(18), [0, 1, 2, 3, 4, 5].map(i => 'getFile:' + i));
	assertScoped(s.fsd);
	assertPrivate(r, s.areas);
});

test('C15 remove: missing targets are neither created nor deleted', async () => {
	const files = matchingFiles();
	files.delete(PINS_TARGETS[0].path);
	files.delete(PINS_TARGETS[4].path);
	const s = setup({ files });
	const r = await s.verifier.remove();
	assert.equal(r.state, 'removed-verified');
	assert.equal(r.removed, 4);
	assert.deepEqual(ops(s.fsd.log, 'remove').map(e => e.path).sort(), [1, 2, 3, 5].map(i => PINS_TARGETS[i].path).sort());
	const none = setup();
	const rn = await none.verifier.remove();
	assert.equal(rn.state, 'removed-verified');
	assert.equal(rn.removed, 0);
	assert.equal(ops(none.fsd.log, 'remove').length, 0);
});

test('C16 remove: target changed after validation but before its delete stops before that delete', async () => {
	// The first matching target is replaced between the full precheck and its revalidation.
	let reads = 0;
	const files = matchingFiles();
	const s = setup({ files, fsOptions: { hooks: { file: p => { if (p === PINS_TARGETS[0].path && ++reads === 2) { files.set(p, { bytes: encode('replaced') }); } } } } });
	const r = await s.verifier.remove();
	assert.equal(r.state, 'refused');
	assert.equal(r.code, 'changed-before-delete');
	assert.equal(ops(s.fsd.log, 'remove').length, 0);
	assert.equal(r.lock.mutation_locked, false);

	// A later target changes after earlier deletes: failure, locked, nothing more removed.
	let reads2 = 0;
	const files2 = matchingFiles();
	const s2 = setup({ files: files2, fsOptions: { hooks: { file: p => { if (p === PINS_TARGETS[3].path && ++reads2 === 2) { files2.set(p, { bytes: BYTES[2] }); } } } } });
	const r2 = await s2.verifier.remove();
	assert.equal(r2.state, 'failed');
	assert.equal(r2.code, 'changed-before-delete');
	assert.equal(r2.removed, 3);
	assert.deepEqual(ops(s2.fsd.log, 'remove').map(e => e.path), [0, 1, 2].map(i => PINS_TARGETS[i].path));
	assert.equal(r2.lock.mutation_locked, true);
	assert.equal((await s2.verifier.remove()).code, 'mutation-locked');
	assertScoped(s2.fsd);
});

test('C17 remove: delayed asynchronous callbacks are awaited', async () => {
	const s = setup({ files: matchingFiles(), fsOptions: { delay: 15 } });
	const r = await s.verifier.remove();
	assert.equal(r.state, 'removed-verified');
	assert.equal(s.fsd.files.size, 0);
});

test('C18 remove: partial removal error is visible, locks mutation, fresh inspection unlocks', async () => {
	const files = matchingFiles();
	files.get(PINS_TARGETS[2].path).removeError = domError('InvalidModificationError', 9);
	const s = setup({ files });
	const r = await s.verifier.remove();
	assert.equal(r.state, 'uncertain');
	assert.equal(r.code, 'remove-error');
	assert.equal(r.removed, 2);
	assert.deepEqual(r.steps.at(-1), { path: PINS_TARGETS[2].path, step: 'remove', state: 'failed', code: 'remove-error' });
	assert.equal(ops(s.fsd.log, 'remove').length, 3, 'no blind retry and no further deletes');
	assert.equal(r.lock.mutation_locked, true);
	assertPrivate(r, s.areas);
	assert.equal((await s.verifier.remove()).code, 'mutation-locked');
	assert.equal((await s.verifier.refresh('original')).code, 'mutation-locked');
	delete files.get(PINS_TARGETS[2].path).removeError;
	const i = await s.verifier.inspect();
	assert.equal(i.state, 'inspected');
	assert.equal(i.released_lock, true);
	assert.equal(i.lock.can_mutate, true);
	assert.equal((await s.verifier.remove()).state, 'removed-verified');
});

test('C19 remove: timed-out callback stays locked until settled AND freshly inspected', async () => {
	const files = matchingFiles();
	files.get(PINS_TARGETS[1].path).removeNever = true;
	const s = setup({ files, pins: { callbackTimeoutMs: 40 } });
	const r = await s.verifier.remove();
	assert.equal(r.state, 'uncertain');
	assert.equal(r.code, 'timeout');
	assert.equal(r.lock.pending, 1);
	assert.equal(r.lock.mutation_locked, true);
	assert.equal(ops(s.fsd.log, 'remove').length, 2);
	// Inspection while the callback is unresolved cannot unlock.
	const i1 = await s.verifier.inspect();
	assert.equal(i1.state, 'inspected');
	assert.equal(i1.released_lock, undefined);
	assert.equal(i1.lock.can_mutate, false);
	assert.equal((await s.verifier.remove()).code, 'callback-pending');
	assert.equal((await s.verifier.refresh('original')).code, 'callback-pending');
	// Late settlement clears pending but not the lock.
	files.get(PINS_TARGETS[1].path).removeLater();
	await sleep(5);
	assert.equal(s.verifier.status().pending, 0);
	assert.equal(s.verifier.status().mutation_locked, true);
	assert.ok(s.changes.some(c => c.pending === 0 && c.mutation_locked));
	assert.equal((await s.verifier.remove()).code, 'mutation-locked');
	const i2 = await s.verifier.inspect();
	assert.equal(i2.released_lock, true);
	assert.equal((await s.verifier.remove()).state, 'removed-verified');
});

test('C20 a lookup callback that never settles keeps every mutation disabled', async () => {
	const files = matchingFiles();
	files.get(PINS_TARGETS[4].path).lookupNever = true;
	const s = setup({ files, pins: { callbackTimeoutMs: 30 } });
	const r = await s.verifier.inspect();
	assert.equal(r.state, 'uncertain');
	assert.equal(r.code, 'timeout');
	assert.equal(r.lock.pending, 1);
	assert.equal((await s.verifier.remove()).code, 'callback-pending');
	assert.equal(ops(s.fsd.log, 'remove').length, 0);
});

test('C21 remove: a target reappearing after removal is still-present, failed and locked', async () => {
	const files = matchingFiles();
	const s = setup({ files, fsOptions: { hooks: { removed: p => { if (p === PINS_TARGETS[5].path) { files.set(p, { bytes: BYTES[5] }); } } } } });
	const r = await s.verifier.remove();
	assert.equal(r.removed, 6);
	assert.equal(r.state, 'failed');
	assert.equal(r.code, 'still-present');
	assert.equal(r.postcheck[5].state, 'match');
	assert.equal(r.lock.mutation_locked, true);
});

test('C22 remove: WebStorage change during removal is never success', async () => {
	const local = new Area({ [SECRET_KEY]: SECRET_VALUE });
	const s = setup({ files: matchingFiles(), local, fsOptions: { hooks: { removed: () => local.map.set(SECRET_KEY, 'changed') } } });
	const r = await s.verifier.remove();
	assert.equal(r.state, 'failed');
	assert.equal(r.code, 'storage-changed');
	assert.equal(r.lock.mutation_locked, true);
	assertPrivate(r, s.areas);
});

test('C23 concurrent actions are refused while one runs', async () => {
	const s = setup({ files: matchingFiles(), fsOptions: { delay: 10 } });
	const first = s.verifier.remove();
	const second = await s.verifier.inspect();
	const third = await s.verifier.refresh('original');
	assert.equal(second.code, 'busy');
	assert.equal(third.code, 'busy');
	assert.equal((await first).state, 'removed-verified');
	assert.ok(s.changes.some(c => c.busy));
});

// Root regression controls for mutations after asynchronous preflight work.
test('R01 storage changed during full precheck or first revalidation prevents every delete', async () => {
	for (const changeAt of [6, 7]) {
		const local = new Area({ [SECRET_KEY]: SECRET_VALUE });
		let opens = 0;
		const s = setup({ files: matchingFiles(), local, fsOptions: { hooks: { getFile: () => {
			if (++opens === changeAt) { local.map.set(SECRET_KEY, 'changed'); }
		} } } });
		const r = await s.verifier.remove();
		assert.equal(r.code, 'storage-changed');
		assert.equal(r.state, 'failed');
		assert.equal(ops(s.fsd.log, 'remove').length, 0);
		assert.equal(s.fsd.files.size, 6);
		assertPrivate(r, s.areas);
	}
});

test('R02 storage changed during bundle preflight prevents every alias request', async () => {
	const local = new Area({ [SECRET_KEY]: SECRET_VALUE });
	const route = serverRoute('original');
	const s = setup({ local, route: (u, init) => {
		if (init.cache === 'no-store') { local.map.set(SECRET_KEY, 'changed'); }
		return route(u, init);
	} });
	const r = await s.verifier.refresh('original');
	assert.equal(r.code, 'storage-changed');
	assert.equal(r.state, 'failed');
	assert.equal(s.fetchLog.length, 1);
	assert.equal(r.http.length, 0);
	assertPrivate(r, s.areas);
});

test('R03 storage changed after one alias request prevents the next request and locks', async () => {
	const local = new Area({ [SECRET_KEY]: SECRET_VALUE });
	const route = serverRoute('original');
	const s = setup({ local, route: (u, init) => {
		if (init.cache === 'reload') { local.map.set(SECRET_KEY, 'changed'); }
		return route(u, init);
	} });
	const r = await s.verifier.refresh('original');
	assert.equal(r.code, 'storage-changed');
	assert.equal(s.fetchLog.length, 2);
	assert.equal(r.lock.mutation_locked, true);
	assertPrivate(r, s.areas);
});

test('R04 overflow cancellation rejection is handled without leaking its error', async () => {
	let cancels = 0;
	const url = aliasUrl(PINS_TARGETS[0].path);
	const body = { getReader: () => ({
		read: async () => ({ done: false, value: new Uint8Array(PINS_TARGETS[0].bytes + 1) }),
		cancel: () => { cancels += 1; return Promise.reject(new Error(SECRET_VALUE)); }
	}) };
	const s = setup({ route: serverRoute('repaired', { [url + '|reload']: u => response(u, 200, null, { body }) }) });
	const r = await s.verifier.refresh('repaired');
	await sleep(5); // node:test also fails if a rejection escapes this action.
	assert.equal(r.code, 'body-too-large');
	assert.equal(r.state, 'failed');
	assert.equal(cancels, 1);
	assertPrivate(r, s.areas);
});

test('R05 unsettled overflow cancellation requires settlement and a later clean inspection', async () => {
	let release;
	const url = aliasUrl(PINS_TARGETS[0].path);
	const body = { getReader: () => ({
		read: async () => ({ done: false, value: new Uint8Array(PINS_TARGETS[0].bytes + 1) }),
		cancel: () => new Promise(resolve => { release = resolve; })
	}) };
	const s = setup({ pins: { fetchTimeoutMs: 40 }, route: serverRoute('repaired', { [url + '|reload']: u => response(u, 200, null, { body }) }) });
	const r = await s.verifier.refresh('repaired');
	assert.equal(r.state, 'uncertain');
	assert.equal(r.code, 'timeout');
	assert.equal(r.lock.pending, 1);
	const pendingInspection = await s.verifier.inspect();
	assert.equal(pendingInspection.released_lock, undefined);
	assert.equal(pendingInspection.lock.can_mutate, false);
	release();
	await sleep(5);
	assert.equal(s.verifier.status().pending, 0);
	assert.equal(s.verifier.status().mutation_locked, true);
	assert.equal((await s.verifier.inspect()).released_lock, true);
	assertPrivate(r, s.areas);
});

// ======================================================== HTTP refresh

test('C24 refresh original: preflight then six reload and six default 404s', async () => {
	const s = setup();
	const r = await s.verifier.refresh('original');
	assert.equal(r.state, 'refreshed-verified');
	assert.equal(r.code, null);
	assert.equal(s.fetchLog.length, 13);
	assert.equal(s.fetchLog[0].init.cache, 'no-store');
	assert.match(s.fetchLog[0].url, /^http:\/\/127\.0\.0\.1:3338\/Online\.js\?t05_008_preflight=[0-9a-f]{32}$/);
	assert.deepEqual(s.fetchLog.slice(1, 7).map(e => [e.url, e.init.cache]), PINS_TARGETS.map(t => [aliasUrl(t.path), 'reload']));
	assert.deepEqual(s.fetchLog.slice(7).map(e => [e.url, e.init.cache]), PINS_TARGETS.map(t => [aliasUrl(t.path), 'default']));
	assert.ok(r.http.every(h => h.status === 404 && h.code === null));
	assert.equal(r.preflight.content, 'match');
	assert.deepEqual(r.postcheck.map(t => t.state), Array(6).fill('missing'));
	assert.ok(!JSON.stringify(r).includes('Not Found'), 'no response body exposed');
	assertScoped(s.fsd, s.fetchLog);
	assertPrivate(r, s.areas);
	// The preflight nonce is fresh per action.
	await s.verifier.refresh('original');
	assert.notEqual(s.fetchLog[13].url, s.fetchLog[0].url);
});

test('C25 refresh repaired: six exact 200 bodies in both phases', async () => {
	const s = setup({ route: serverRoute('repaired') });
	const r = await s.verifier.refresh('repaired');
	assert.equal(r.state, 'refreshed-verified');
	assert.ok(r.http.every(h => h.status === 200 && h.content === 'match'));
	assert.deepEqual(r.http.map(h => h.bytes), [...PINS_TARGETS, ...PINS_TARGETS].map(t => t.bytes));
	assertScoped(s.fsd, s.fetchLog);
});

test('C26 refresh: wrong bundle stage stops before any alias request', async () => {
	for (const [mode, server] of [['original', 'repaired'], ['repaired', 'original']]) {
		const s = setup({ route: serverRoute(server) });
		const r = await s.verifier.refresh(mode);
		assert.equal(r.state, 'refused');
		assert.equal(r.code, 'bundle-stage-mismatch');
		assert.ok(['size-mismatch', 'body-too-large'].includes(r.preflight.code));
		assert.equal(s.fetchLog.length, 1);
		assert.equal(r.lock.mutation_locked, false);
	}
	const sameSize = encode('export const stage = "Original";\n');
	const s = setup({ route: (url, init) => response(url, 200, sameSize) });
	const r = await s.verifier.refresh('original');
	assert.equal(r.code, 'bundle-stage-mismatch');
	assert.equal(r.preflight.code, 'content-mismatch');
	assert.equal(s.fetchLog.length, 1);
});

test('C27 refresh: requires all six filesystem copies absent', async () => {
	const files = new Map([[PINS_TARGETS[2].path, { bytes: BYTES[2] }]]);
	const s = setup({ files });
	const r = await s.verifier.refresh('repaired');
	assert.equal(r.state, 'refused');
	assert.equal(r.code, 'filesystem-not-absent');
	assert.equal(s.fetchLog.length, 0);
	assert.equal(ops(s.fsd.log, 'remove').length, 0);
});

test('C28 refresh original: a stale default 200 is failure and locks', async () => {
	const url = aliasUrl(PINS_TARGETS[3].path);
	const s = setup({ route: serverRoute('original', { [url + '|default']: u => response(u, 200, BYTES[3]) }) });
	const r = await s.verifier.refresh('original');
	assert.equal(r.state, 'failed');
	assert.equal(r.code, 'stale-default-response');
	assert.equal(r.http.at(-1).phase, 'default');
	assert.equal(r.lock.mutation_locked, true);
	assert.equal((await s.verifier.refresh('original')).code, 'mutation-locked');
});

test('C29 refresh repaired: wrong status or content is failure', async () => {
	const url = aliasUrl(PINS_TARGETS[0].path);
	const wrong = setup({ route: serverRoute('repaired', { [url + '|reload']: u => response(u, 200, BYTES[1]) }) });
	const r1 = await wrong.verifier.refresh('repaired');
	assert.equal(r1.state, 'failed');
	assert.ok(['body-too-large', 'size-mismatch'].includes(r1.code));
	assert.equal(r1.http[0].content, null, 'an oversized body is not hashed or exposed');
	const missing = setup({ route: serverRoute('repaired', { [url + '|default']: u => response(u, 404, encode('x')) }) });
	const r2 = await missing.verifier.refresh('repaired');
	assert.equal(r2.code, 'unexpected-status');
	const flipped = BYTES[0].slice();
	flipped[2] ^= 4;
	const content = setup({ route: serverRoute('repaired', { [url + '|reload']: u => response(u, 200, flipped) }) });
	assert.equal((await content.verifier.refresh('repaired')).code, 'content-mismatch');
});

test('C30 refresh: redirect, foreign response, fetch error and oversized body are failures', async () => {
	const url = aliasUrl(PINS_TARGETS[1].path);
	const cases = [
		[{ [url + '|reload']: u => response(u, 404, null, { redirected: true }) }, 'redirected'],
		[{ [url + '|reload']: u => response(ORIGIN + '/elsewhere', 404, null) }, 'redirected'],
		[{ [url + '|reload']: u => response(u, 404, null, { type: 'opaque' }) }, 'foreign-response'],
		[{ [url + '|reload']: () => { throw new TypeError('redirect mode is error'); } }, 'fetch-error'],
		[{ [url + '|default']: u => response(u, 404, new Uint8Array(70000)) }, 'body-too-large']
	];
	for (const [overrides, code] of cases) {
		const s = setup({ route: serverRoute('original', overrides) });
		const r = await s.verifier.refresh('original');
		assert.equal(r.state, 'failed', code);
		assert.equal(r.code, code);
		assert.equal(r.lock.mutation_locked, true, code);
		assertPrivate(r, s.areas);
		assertScoped(s.fsd, s.fetchLog);
	}
	const pre = setup({ route: (u, init) => response(u, 200, ORIGINAL_JS, { redirected: true }) });
	const rp = await pre.verifier.refresh('original');
	assert.equal(rp.code, 'bundle-stage-mismatch');
	assert.equal(rp.preflight.code, 'redirected');
	assert.equal(pre.fetchLog.length, 1);
});

test('C31 refresh: changed storage and reappearing filesystem target are failures', async () => {
	const local = new Area({ [SECRET_KEY]: SECRET_VALUE });
	let calls = 0;
	const s = setup({ local, route: (u, init) => { if (++calls === 4) { local.map.set('x', 'y'); } return serverRoute('original')(u, init); } });
	const r = await s.verifier.refresh('original');
	assert.equal(r.state, 'failed');
	assert.equal(r.code, 'storage-changed');
	assertPrivate(r, s.areas);

	const files = new Map();
	let n = 0;
	const s2 = setup({ files, route: (u, init) => { if (++n === 13) { files.set(PINS_TARGETS[0].path, { bytes: BYTES[0] }); } return serverRoute('original')(u, init); } });
	const r2 = await s2.verifier.refresh('original');
	assert.equal(r2.state, 'failed');
	assert.equal(r2.code, 'still-present');
	assert.equal(r2.lock.mutation_locked, true);
});

test('C32 refresh: a timed-out fetch is aborted, uncertain and stays pending until settled', async () => {
	let release;
	const url = aliasUrl(PINS_TARGETS[2].path);
	const s = setup({
		pins: { fetchTimeoutMs: 30 },
		route: serverRoute('original', { [url + '|reload']: () => new Promise((_, reject) => { release = () => reject(domError('AbortError', 20)); }) })
	});
	const r = await s.verifier.refresh('original');
	assert.equal(r.state, 'uncertain');
	assert.equal(r.code, 'timeout');
	assert.equal(s.aborts.length, 1);
	assert.equal(r.lock.pending, 1);
	assert.equal((await s.verifier.inspect()).released_lock, undefined);
	release();
	await sleep(5);
	assert.equal(s.verifier.status().pending, 0);
	assert.equal(s.verifier.status().mutation_locked, true);
	assert.equal((await s.verifier.inspect()).released_lock, true);
});

test('C33 refresh: unknown mode and missing fetch support are refused', async () => {
	const s = setup();
	const r = await s.verifier.refresh('both');
	assert.equal(r.state, 'refused');
	assert.equal(r.code, 'bad-mode');
	const nf = setup({ adapters: { fetch: null } });
	const r2 = await nf.verifier.refresh('original');
	assert.equal(r2.code, 'bundle-stage-mismatch');
	assert.equal(r2.preflight.code, 'unsupported');
	const bad = setup({ adapters: { onlineBase: 'http://example.invalid/Online.js' } });
	const r3 = await bad.verifier.refresh('original');
	assert.equal(r3.code, 'origin-refused');
	assert.equal(bad.fetchLog.length, 0);
});

// ======================================================== generated loaders

function generated(fn, arg) {
	const r = spawnSync('python3', ['-I', '-B', '-c',
		'import sys; sys.path.insert(0, sys.argv[1]); import navigation_browser_verifier as g\n'
		+ 'out = g.entry_expression(sys.argv[3]) if sys.argv[2] == "entry" else g.cache_inline_script(g.cache_page(open(sys.argv[3], "rb").read()))\n'
		+ 'sys.stdout.write(out)', here, fn, arg], { encoding: 'utf8' });
	assert.equal(r.status, 0, r.stderr);
	return r.stdout;
}

function fakeDom({ origin = ORIGIN, href = ORIGIN + '/T05_008-original-entry.html?app=ONLINE', crypto = true, integrity = true, existing = {} } = {}) {
	const order = [];
	const byId = new Map(Object.entries(existing));
	const winListeners = {};
	const makeEl = tag => {
		const el = {
			tagName: tag.toUpperCase(),
			listeners: {},
			attributes: {},
			textContent: '',
			setAttribute(k, v) { this.attributes[k] = String(v); },
			getAttribute(k) { return k in this.attributes ? this.attributes[k] : null; },
			addEventListener(type, fn) { order.push('listen:' + type); this.listeners[type] = fn; },
			fire(type) { this.listeners[type] && this.listeners[type]({ type }); }
		};
		return el;
	};
	const appended = [];
	const document = {
		getElementById: id => byId.get(id) || null,
		createElement: makeEl,
		body: { appendChild(el) { if (el.id) { byId.set(el.id, el); } order.push('body-append'); return el; } },
		head: { appendChild(el) { order.push('head-append'); appended.push(el); return el; } }
	};
	function HTMLScriptElement() {}
	if (integrity) {
		HTMLScriptElement.prototype.integrity = '';
	}
	const win = {
		document,
		location: { origin, href },
		crypto: crypto ? { getRandomValues: a => webcrypto.getRandomValues(a) } : undefined,
		addEventListener(type, fn) { order.push('window-listen:' + type); winListeners[type] = fn; },
		removeEventListener(type) { delete winListeners[type]; },
		HTMLScriptElement,
		URL,
		Promise,
		JSON,
		Uint8Array,
		Array,
		Error
	};
	win.window = win;
	const ctx = vm.createContext(win);
	return { ctx, win, order, byId, appended, winListeners };
}

const entryStatus = dom => JSON.parse(dom.byId.get('T05_008-entry-status').textContent);

test('C34 entry expression: one SRI-pinned module script, listeners first, no early success', async () => {
	for (const stage of ['original', 'repaired']) {
		const expr = generated('entry', stage);
		assert.ok(!expr.includes('import('));
		const dom = fakeDom();
		const promise = vm.runInContext('var scriptFile = "Online.js";\n' + expr, dom.ctx);
		assert.equal(typeof promise.then, 'function');
		let settled = null;
		promise.then(() => { settled = 'resolved'; }, () => { settled = 'rejected'; });
		await sleep(1);
		assert.equal(settled, null, 'nothing settles before load');
		assert.equal(dom.appended.length, 1);
		const s = dom.appended[0];
		assert.equal(s.type, 'module');
		assert.equal(s.integrity, sri(BUNDLES[stage].sha256));
		assert.equal(s.crossOrigin, 'anonymous');
		const url = new URL(s.src);
		assert.equal(url.origin + url.pathname, ORIGIN + '/Online.js');
		assert.equal(url.searchParams.get('t05_008_sha256'), BUNDLES[stage].sha256);
		assert.match(url.searchParams.get('t05_008_nonce'), /^[0-9a-f]{32}$/);
		const head = dom.order.indexOf('head-append');
		assert.ok(dom.order.indexOf('listen:load') < head && dom.order.indexOf('listen:error') < head);
		const pending = entryStatus(dom);
		assert.equal(pending.state, 'pending');
		assert.equal(pending.stage, stage);
		assert.equal(pending.module_url, s.src);
		assert.equal(pending.expected_sha256, BUNDLES[stage].sha256);
		assert.equal(pending.integrity, s.integrity);
		s.fire('load');
		await sleep(1);
		assert.equal(settled, 'resolved');
		assert.equal(entryStatus(dom).state, 'loaded');
	}
	// Two loads use different nonces (fresh module-map keys).
	const expr = generated('entry', 'original');
	const a = fakeDom();
	const b = fakeDom();
	vm.runInContext('var scriptFile = "Online.js";\n' + expr, a.ctx);
	vm.runInContext('var scriptFile = "Online.js";\n' + expr, b.ctx);
	assert.notEqual(a.appended[0].src, b.appended[0].src);
});

test('C35 entry expression: load error and evaluation error reject visibly, never loaded', async () => {
	const expr = generated('entry', 'repaired');
	const dom = fakeDom();
	const promise = vm.runInContext('var scriptFile = "Online.js";\n' + expr, dom.ctx);
	dom.appended[0].fire('error');
	await assert.rejects(promise);
	assert.equal(entryStatus(dom).state, 'failed');
	assert.equal(entryStatus(dom).reason, 'load-or-integrity-error');
	dom.appended[0].fire('load');
	await sleep(1);
	assert.equal(entryStatus(dom).state, 'failed', 'a later load cannot turn failure into success');

	const ev = fakeDom();
	const p2 = vm.runInContext('var scriptFile = "Online.js";\n' + expr, ev.ctx);
	ev.winListeners.error({ filename: ORIGIN + '/other.js' });
	assert.equal(entryStatus(ev).state, 'pending');
	ev.winListeners.error({ filename: ev.appended[0].src });
	ev.appended[0].fire('load');
	await assert.rejects(p2);
	assert.equal(entryStatus(ev).reason, 'evaluation-error');
});

test('C36 entry expression: other script, wrong origin, missing crypto/SRI and duplicates are refused', async () => {
	const expr = generated('entry', 'original');
	const cases = [
		[{}, 'MapViewer.js', 'script-refused'],
		[{ origin: 'http://localhost:3338', href: 'http://localhost:3338/x.html' }, 'Online.js', 'origin-refused'],
		[{ crypto: false }, 'Online.js', 'crypto-unavailable'],
		[{ integrity: false }, 'Online.js', 'integrity-unsupported']
	];
	for (const [opts, file, reason] of cases) {
		const dom = fakeDom(opts);
		const p = vm.runInContext('var scriptFile = ' + JSON.stringify(file) + ';\n' + expr, dom.ctx);
		await assert.rejects(p);
		assert.equal(dom.appended.length, 0);
		assert.equal(entryStatus(dom).state, 'failed');
		assert.equal(entryStatus(dom).reason, reason);
	}
	const dom = fakeDom();
	vm.runInContext('var scriptFile = "Online.js";\n' + expr, dom.ctx);
	const again = vm.runInContext('var scriptFile = "Online.js";\n' + expr, dom.ctx);
	await assert.rejects(again);
	assert.equal(dom.appended.length, 1);
	assert.equal(entryStatus(dom).reason, 'duplicate-entry');
});

test('C37 cache page loader: authored-byte SRI module URL; error or unbound load fails visibly', async () => {
	const script = generated('cache', modulePath);
	const moduleSha = sha(fs.readFileSync(modulePath));
	const report = () => ({ id: IDS.report, textContent: '', attributes: {}, getAttribute(k) { return this.attributes[k] ?? null; }, setAttribute(k, v) { this.attributes[k] = v; } });

	const ok = fakeDom({ href: ORIGIN + '/T05_008-cache.html', existing: { [IDS.report]: report() } });
	vm.runInContext(script, ok.ctx);
	assert.equal(ok.appended.length, 1);
	const s = ok.appended[0];
	assert.equal(s.type, 'module');
	assert.equal(s.integrity, sri(moduleSha));
	assert.equal(s.crossOrigin, 'anonymous');
	const url = new URL(s.src);
	assert.equal(url.origin + url.pathname, ORIGIN + '/T05_008-cache.mjs');
	assert.equal(url.searchParams.get('t05_008_sha256'), moduleSha);
	assert.match(url.searchParams.get('t05_008_nonce'), /^[0-9a-f]{32}$/);
	assert.equal(JSON.parse(ok.byId.get(IDS.report).textContent).state, 'loading-module');
	ok.byId.get(IDS.report).setAttribute('data-bound', '1');
	ok.byId.get(IDS.report).textContent = '{"state":"ready"}';
	s.fire('load');
	assert.equal(JSON.parse(ok.byId.get(IDS.report).textContent).state, 'ready');

	const err = fakeDom({ href: ORIGIN + '/T05_008-cache.html', existing: { [IDS.report]: report() } });
	vm.runInContext(script, err.ctx);
	err.appended[0].fire('error');
	assert.deepEqual([JSON.parse(err.byId.get(IDS.report).textContent).state, JSON.parse(err.byId.get(IDS.report).textContent).code], ['failed', 'module-load-or-integrity-error']);

	const unbound = fakeDom({ href: ORIGIN + '/T05_008-cache.html', existing: { [IDS.report]: report() } });
	vm.runInContext(script, unbound.ctx);
	unbound.appended[0].fire('load');
	assert.equal(JSON.parse(unbound.byId.get(IDS.report).textContent).code, 'module-not-bound');

	const foreign = fakeDom({ origin: 'http://localhost:3338', href: 'http://localhost:3338/T05_008-cache.html', existing: { [IDS.report]: report() } });
	vm.runInContext(script, foreign.ctx);
	assert.equal(foreign.appended.length, 0);
	assert.equal(JSON.parse(foreign.byId.get(IDS.report).textContent).code, 'origin-refused');
});

test('C38 browser binding: fixed origin, controls locked while running, no automatic action', async () => {
	const make = origin => {
		const els = {};
		for (const id of Object.values(IDS)) {
			els[id] = { id, disabled: false, textContent: '', attributes: {}, handlers: {},
				setAttribute(k, v) { this.attributes[k] = v; }, addEventListener(t, fn) { this.handlers[t] = fn; } };
		}
		const fsd = makeFs(new Map(), { delay: 5 });
		const win = {
			document: { getElementById: id => els[id] || null, baseURI: origin + '/T05_008-cache.html?x=1' },
			location: { origin },
			webkitRequestFileSystem: fsd.requestFileSystem,
			TEMPORARY: 0,
			localStorage: new Area({ [SECRET_KEY]: SECRET_VALUE }),
			sessionStorage: new Area(),
			fetch: () => { throw new Error('no fetch expected'); },
			AbortController,
			crypto: webcrypto,
			setTimeout,
			clearTimeout
		};
		return { els, fsd, win };
	};
	const foreign = make('http://localhost:3338');
	assert.equal(bindBrowser(foreign.win), null);
	assert.equal(JSON.parse(foreign.els[IDS.report].textContent).code, 'origin-refused');
	assert.ok([IDS.inspect, IDS.remove, IDS.original, IDS.repaired].every(id => foreign.els[id].disabled));
	assert.equal(foreign.fsd.log.length, 0);

	const page = make(ORIGIN);
	assert.ok(bindBrowser(page.win));
	const report = () => JSON.parse(page.els[IDS.report].textContent);
	assert.equal(report().state, 'ready');
	assert.equal(page.fsd.log.length, 0, 'binding runs no action by itself');
	assert.ok([IDS.inspect, IDS.remove, IDS.original, IDS.repaired].every(id => !page.els[id].disabled));
	page.els[IDS.inspect].handlers.click();
	assert.equal(report().state, 'running');
	assert.ok([IDS.inspect, IDS.remove, IDS.original, IDS.repaired].every(id => page.els[id].disabled));
	page.els[IDS.remove].handlers.click();
	await sleep(150);
	const done = report();
	assert.equal(done.state, 'inspected');
	assert.equal(done.all_absent, true);
	assert.equal(ops(page.fsd.log, 'remove').length, 0, 'a click while running is ignored');
	assert.ok(!page.els[IDS.report].textContent.includes(SECRET_VALUE));
	assert.ok(!page.els[IDS.remove].disabled);
	assertScoped({ log: page.fsd.log.map(e => (e.path ? { ...e, path: PINS_TARGETS[TARGETS.findIndex(t => t.path === e.path)].path } : e)) });
});
