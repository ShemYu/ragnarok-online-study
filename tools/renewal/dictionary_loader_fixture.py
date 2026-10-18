#!/usr/bin/env python3
"""T05.005: build the detached native fixture for the dictionary loader.

    python3 -I tools/renewal/dictionary_loader_fixture.py LOADER_SOURCE CORE_SOURCE OUTPUT \\
        [--dictionary-source PATH]

LOADER_SOURCE is the authored dictionary_loader.mjs and CORE_SOURCE the
root-qualified npc_plaintext_adapter.mjs (exact pin below). Both are read as
regular, non-linked files of at most 1 MiB and copied as bytes, never
imported. They sit beside entirely authored modules: an API 1 / plugin
manager / core / status / Response double set, a classic boot reporter, a
fixed D01-D10 group manifest and a fixed ten-mode actual-fault ledger, tiny
authored dictionaries with their pins, a nested page whose document base
differs from both the page and the module directory, and a stdlib loopback
server script with a fixed file allowlist and finite case endpoints.

--dictionary-source streams the production dict.json (exact size/SHA-256
below) into full/ beside byte-identical loader/core copies, hashing as it
copies. It is never decoded, parsed or enumerated here. This is detached
fixture data for the root's D09 run, not a package, mod or staging output.

OUTPUT must not exist; it is created 0700 with 0600 files. On any refusal the
new OUTPUT this run created is removed and nothing is reported as built.
This only writes files: it never opens a browser, binds a port or runs the
generated server (see DICTIONARY_LOADER.md).
"""
import hashlib
import json
import os
import re
import shutil
import stat
import sys
from pathlib import Path

READ_LIMIT = 1024 * 1024
COPY_CHUNK = 1024 * 1024
CORE_PIN = {'bytes': 14236, 'sha256': '0dc77140f921925f7079dfdeaf6f674931f66a726f97b41bfab5f6b8e7f0089c'}
DICTIONARY_PIN = {'bytes': 19706353, 'sha256': 'be3825ca74db764f8d9ffbea9ba8f15ac17b1fd5bde49975d4b36c59ba704fc2'}
LOADER_NAME = 'dictionary_loader.mjs'
CORE_NAME = 'npc_plaintext_adapter.mjs'
CORE_SPECIFIER = './' + CORE_NAME
GROUPS = [
    ('D01', 'Synchronous lifecycle'),
    ('D02', 'Module-relative request'),
    ('D03', 'Verified bounded pipeline'),
    ('D04', 'Transport/body/identity failures'),
    ('D05', 'Decode/parse/container'),
    ('D06', 'Deadline/dispose/late outcomes'),
    ('D07', 'Owned status/diagnostics/costs'),
    ('D08', 'Fixture provenance/negatives'),
    ('D09', 'Root native full-body and costs'),
    ('D10', 'Reporter/fault controls'),
]
MODES = ['missing-loader', 'missing-core', 'csp-inline', 'loader-reject', 'loader-timeout',
         'api-error', 'cleanup-error', 'unhandled-rejection', 'zero-assertions', 'omitted-group']
CSP = '; '.join([
    "default-src 'none'", "script-src 'self'", "style-src 'self'", "connect-src 'self'",
    "img-src 'none'", "font-src 'none'", "media-src 'none'", "object-src 'none'",
    "frame-src 'none'", "child-src 'none'", "worker-src 'none'", "manifest-src 'none'",
    "base-uri 'self'", "form-action 'none'",
])
PAGE = 'pages/run/index.html'
PAGE_BASE = '../../decoy/'


class Refused(Exception):
    pass


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def checked_path(path, what, missing_leaf=False):
    """Reject linked components without resolving them away before checking."""
    absolute = Path(path)
    if not absolute.is_absolute():
        absolute = Path.cwd() / absolute
    if any(part in ('..', '.') for part in absolute.parts):
        raise Refused(f'{what}: path must not contain . or .. components')
    current = Path(absolute.anchor)
    parts = absolute.parts[1:]
    for index, part in enumerate(parts):
        current = current / part
        last = index == len(parts) - 1
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            if missing_leaf and last:
                return str(absolute)
            raise Refused(f'{what}: path component not found')
        if stat.S_ISLNK(info.st_mode):
            raise Refused(f'{what}: symbolic link component')
        if not last and not stat.S_ISDIR(info.st_mode):
            raise Refused(f'{what}: parent component is not a directory')
    return str(absolute)


def open_regular(path, what):
    """(fd, lstat) for a regular, non-linked file whose identity holds."""
    path = checked_path(path, what)
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode):
        raise Refused(f'{what}: not a regular file')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NONBLOCK', 0))
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            raise Refused(f'{what}: regular file identity changed')
    except BaseException:
        os.close(fd)
        raise
    return fd, opened


def identity(value):
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def read_regular(path, what):
    """A regular file of at most READ_LIMIT bytes, size-checked before reading."""
    fd, before = open_regular(path, what)
    try:
        if before.st_size > READ_LIMIT:
            raise Refused(f'{what}: size exceeds 1 MiB')
        chunks, total = [], 0
        while total <= READ_LIMIT:
            chunk = os.read(fd, min(65536, READ_LIMIT + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total > READ_LIMIT:
                raise Refused(f'{what}: read limit exceeded')
            chunks.append(chunk)
        after = os.fstat(fd)
        if identity(before) != identity(after) or total != before.st_size:
            raise Refused(f'{what}: file changed while reading')
        return b''.join(chunks), stat.S_IMODE(before.st_mode)
    finally:
        os.close(fd)


STATIC_IMPORT = re.compile(r'''^\s*(?:import|export)\b[^;'"]*?\bfrom\s*(['"])([^'"]+)\1''', re.M)
BARE_IMPORT = re.compile(r'''^\s*import\s*(['"])([^'"]+)\1''', re.M)
DYNAMIC_IMPORT = re.compile(r'\bimport\s*\(')


def imports_of(text):
    found = [m.group(2) for m in STATIC_IMPORT.finditer(text)] + [m.group(2) for m in BARE_IMPORT.finditer(text)]
    return found, bool(DYNAMIC_IMPORT.search(text))


# --- authored dictionaries ----------------------------------------------------

def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


TINY = compact({
    'Hello': '哈囉',
    'Goodbye': '再會',
    'Welcome to Prontera.': '歡迎光臨普隆德拉。',
    'Ancient': '古代𠀋文字',
})
DECOY_PAGE = compact({'Hello': '頁面相對誘餌'})
DECOY_BASE = compact({'Hello': '文件基底誘餌'})
UNSAFE = (b'{"__proto__":{"polluted":"yes"},"constructor":"\xe5\xbb\xba\xe6\xa7\x8b",'
          b'"Hello":"\xe5\x93\x88\xe5\x9b\x89","Bad number":42,"Bad colour":"^ff0000\xe7\xb4\x85"}')
STATIC_CASES = {
    'tiny': TINY,
    'bad-utf8': b'{"Hello":"\xff\xfe"}',
    'bad-json': b'{"Hello":"\xe5\x93\x88\xe5\x9b\x89",',
    'scalar': b'42',
    'array': b'["Hello"]',
    'null': b'null',
    'unsafe': UNSAFE,
}
# Server-generated endpoints; each serves TINY (gzip-encoded for gzip).
SPECIAL_CASES = ['chunked', 'gzip', 'framing-short', 'redirect', 'stall-headers', 'stall-body',
                 'delay', 'wrong-mime', 'other-charset', 'status-500', 'no-store-plain']


def pin(data):
    return {'bytes': len(data), 'sha256': sha256(data)}


def cases_js(full):
    pins = {name: pin(data) for name, data in STATIC_CASES.items()}
    pins['decoyPage'] = pin(DECOY_PAGE)
    pins['decoyBase'] = pin(DECOY_BASE)
    tiny = pin(TINY)
    # Deliberate wrong pins over the same served bytes.
    pins['tinyLong'] = {'bytes': tiny['bytes'] + 10, 'sha256': tiny['sha256']}
    pins['tinyShort'] = {'bytes': tiny['bytes'] - 3, 'sha256': tiny['sha256']}
    pins['tinyWrongHash'] = {'bytes': tiny['bytes'], 'sha256': sha256(b'not the tiny dictionary')}
    return ('// Generated by dictionary_loader_fixture.py: authored case pins only.\n'
            f'export const PINS = Object.freeze({json.dumps(pins, indent=1, sort_keys=True)});\n'
            f'export const SPECIAL_CASES = Object.freeze({json.dumps(SPECIAL_CASES)});\n'
            f'export const CORE_PIN = Object.freeze({json.dumps(CORE_PIN)});\n'
            f'export const DICTIONARY_PIN = Object.freeze({json.dumps(DICTIONARY_PIN)});\n'
            f'export const CSP = {json.dumps(CSP)};\n'
            f'export const PAGE_BASE = {json.dumps(PAGE_BASE)};\n'
            f'export const FULL_AVAILABLE = {"true" if full else "false"};\n')


# --- authored fixture files ---------------------------------------------------

BOOT = r'''// Classic boot reporter: runs before any module import and records module
// load, CSP, runtime and unhandled-rejection errors. Never cleared.
(function () {
	'use strict';
	var params = new URLSearchParams(location.search);
	var boot = { errors: [], finished: false, csp: [], rejections: [] };
	window.__t05Boot = boot;
	function show() {
		var status = document.getElementById('status');
		if (status) { status.dataset.state = 'fail'; status.textContent = 'FAIL — ' + boot.errors[0] + (boot.errors.length > 1 ? ' (+' + (boot.errors.length - 1) + ' more)' : ''); }
		var errors = document.getElementById('errors');
		if (errors) errors.textContent = boot.errors.join('\n');
		document.title = 'FAIL — T05.005 fixture';
	}
	boot.fail = function (text) { boot.errors.push(String(text).slice(0, 300)); show(); };
	window.addEventListener('error', function (event) {
		var target = event.target;
		if (target && target !== window && target.tagName) boot.fail('load error: ' + target.tagName.toLowerCase() + ' ' + (target.src || target.href || ''));
		else boot.fail('error: ' + (event.message || event.error));
	}, true);
	window.addEventListener('unhandledrejection', function (event) {
		var reason = event.reason;
		var text = reason && reason.message ? reason.message : String(reason);
		boot.rejections.push(String(text).slice(0, 200));
		boot.fail('unhandled rejection: ' + text);
	});
	document.addEventListener('securitypolicyviolation', function (event) {
		boot.csp.push({ directive: event.effectiveDirective, blocked: String(event.blockedURI).slice(0, 120) });
		boot.fail('CSP violation: ' + event.effectiveDirective + ' ' + event.blockedURI);
	});
	var limit = params.get('full') === '1' ? 120000 : 60000;
	setTimeout(function () { if (!boot.finished) boot.fail('watchdog: harness did not complete within ' + (limit / 1000) + ' s'); }, limit);
})();
'''

REPORTER = r'''// Authored aggregate reporter and actual-fault ledger. The literal group
// manifest and the mode list are fixed here, independently of the harness's
// case registrations. PASS needs all ten groups (including root-only D09) to
// run once with assertions and no errors, no unexpected group and no recorded
// failure. Failures are never cleared.
export const BASELINE_GROUPS = Object.freeze([
__GROUPS__
]);
export const GROUP_IDS = Object.freeze(BASELINE_GROUPS.map(group => group.id));
export const FAULT_MODES = Object.freeze(__MODES__);
export const ROOT_ONLY = 'D09';

export function createReporter(manifest = BASELINE_GROUPS) {
	const want = Object.freeze(manifest.map(group => group.id));
	const names = new Map(manifest.map(group => [group.id, group.name]));
	const results = new Map();
	const failures = [];
	return {
		expected: want,
		record(id, assertions, errors) {
			if (results.has(id)) failures.push('group ran twice: ' + id);
			results.set(id, { assertions, errors: [...errors] });
		},
		fail(text) { failures.push(String(text).slice(0, 300)); },
		summary() {
			let executed = 0, passed = 0, failed = 0, assertions = 0;
			const groups = [];
			for (const id of want) {
				const result = results.get(id);
				if (!result) { groups.push({ id, name: names.get(id), state: 'not run', assertions: 0, errors: [] }); continue; }
				executed++;
				assertions += result.assertions;
				const ok = result.errors.length === 0 && result.assertions > 0;
				if (ok) passed++; else failed++;
				const errors = result.assertions > 0 ? result.errors : ['zero assertions', ...result.errors];
				groups.push({ id, name: names.get(id), state: ok ? 'pass' : 'fail', assertions: result.assertions, errors });
			}
			const unexpected = [...results.keys()].filter(id => !want.includes(id));
			const missing = groups.filter(group => group.state === 'not run').map(group => group.id);
			const state = want.length === 10 && passed === want.length && !failures.length && !unexpected.length ? 'pass' : 'fail';
			return { state, expected: want.length, executed, passed, failed, assertions, missing, failures: [...failures], unexpected, groups };
		},
	};
}

// Ledger rows come only from concrete sink records written where the fault
// actually happened. The selected mode name is never evidence by itself; a
// mode with no matching sink record is NOT OBSERVED and fails the page.
const CHECKS = {
	'missing-loader': records => records.find(r => r.sink === 'dynamic-import' && r.target === 'absent-loader'
		&& r.rejected === true && r.probeStatus === 404),
	'missing-core': records => records.find(r => r.sink === 'dynamic-import' && r.target === 'broken-loader'
		&& r.rejected === true && r.loaderStatus === 200 && r.coreStatus === 404),
	'csp-inline': records => records.find(r => r.sink === 'csp-violation' && /^script-src(?:-elem)?$/.test(r.directive)
		&& r.blocked === 'inline' && r.ran === false),
	'loader-reject': records => records.find(r => r.sink === 'loader-ready' && r.code === 'HTTP_STATUS'
		&& r.state === 'failed' && r.statusText === r.expectedText),
	'loader-timeout': records => records.find(r => r.sink === 'loader-ready' && r.code === 'TIMEOUT'
		&& r.state === 'failed' && r.elapsedMs >= r.timeoutMs),
	'api-error': records => records.find(r => r.sink === 'api-error-sink' && r.category === 'listener'
		&& r.ordinaryActionDone === true),
	'cleanup-error': records => records.find(r => r.sink === 'api-error-sink' && r.category === 'cleanup'
		&& r.thrown === true && r.rejected === true && r.ordinaryActionDone === true),
	'unhandled-rejection': records => records.find(r => r.sink === 'boot-unhandledrejection' && r.matched === true),
	'zero-assertions': records => records.find(r => r.sink === 'reporter-summary' && r.kind === 'zero'
		&& r.groupState === 'fail' && r.assertions === 0),
	'omitted-group': records => records.find(r => r.sink === 'reporter-summary' && r.kind === 'omitted'
		&& r.groupState === 'not run'),
};

export function ledger(mode, records) {
	return FAULT_MODES.map(name => {
		if (name !== mode) return { mode: name, state: 'NOT RUN', sink: null, evidence: null };
		const hit = CHECKS[name](records.filter(r => r.mode === name));
		if (!hit) return { mode: name, state: 'NOT OBSERVED', sink: null, evidence: 'missing-fault: no sink record for the selected injection' };
		const { mode: _, ...evidence } = hit;
		return { mode: name, state: 'OBSERVED', sink: hit.sink, evidence: JSON.stringify(evidence).slice(0, 300) };
	});
}
'''

DOUBLES = r'''// Authored doubles: client API 1 scopes, a sequential plugin manager, core
// doubles, Response/body doubles and a recording fetch. Written from the
// reviewed source behaviour, not copied from stock code. Every listener,
// replay and cleanup error goes to a visible sink.
export function createRuntime(onError) {
	if (typeof onError !== 'function') throw new TypeError('API double needs a visible error sink');
	const listeners = new Map();
	const components = new Map();
	function emit(event, value) {
		for (const listener of [...(listeners.get(event) || [])]) {
			try { listener(value); } catch (error) { onError('listener', error); }
		}
	}
	function scope(name, { dead = false } = {}) {
		const cleanups = new Set();
		let disposed = dead;
		const counts = { on: 0, cleanup: 0 };
		const cleanup = fn => {
			if (typeof fn !== 'function') throw new TypeError('Cleanup must be a function');
			counts.cleanup++;
			let done = false;
			const once = () => {
				if (done) return;
				done = true; cleanups.delete(once);
				try { Promise.resolve(fn()).catch(error => onError('cleanup', error)); } catch (error) { onError('cleanup', error); }
			};
			if (disposed) once(); else cleanups.add(once);
			return once;
		};
		const on = (event, listener, { replay = true } = {}) => {
			if (disposed) throw new Error(`Plugin ${name} is disposed`);
			if (!['ui:append', 'ui:remove'].includes(event) || typeof listener !== 'function') throw new TypeError('Unsupported client event');
			counts.on++;
			if (!listeners.has(event)) listeners.set(event, new Set());
			listeners.get(event).add(listener);
			const off = cleanup(() => listeners.get(event)?.delete(listener));
			if (replay) queueMicrotask(() => {
				if (disposed || !listeners.get(event)?.has(listener)) return;
				const values = event === 'ui:append' ? [...components.values()] : [];
				for (const value of values) { try { listener(value); } catch (error) { onError('replay', error); } }
			});
			return off;
		};
		const api = Object.freeze({ version: 1, name, cleanup, on });
		return { api, counts, get disposed() { return disposed; }, dispose() {
			if (disposed) return;
			disposed = true;
			for (const fn of [...cleanups].reverse()) fn();
		} };
	}
	return {
		scope,
		append(component) {
			const item = Object.freeze({ name: component.name, root: component.root, host: component.host });
			components.set(component, item); emit('ui:append', item);
			return item;
		},
		remove(component) {
			const item = components.get(component);
			if (item) { components.delete(component); emit('ui:remove', item); }
		},
		listenerCount: () => [...listeners.values()].reduce((n, set) => n + set.size, 0),
	};
}

// Sequential manager with separate deadlines and asynchronous adoption of a
// returned disposer, as in the reviewed PluginLoader. Manager "ready" is the
// initializer's synchronous return, not dictionary readiness.
export function createManager(runtime, timeout = 10000) {
	const deadline = promise => new Promise((resolve, reject) => {
		const timer = setTimeout(() => reject(new Error('Plugin initialization timed out')), timeout);
		Promise.resolve(promise).then(resolve, reject).finally(() => clearTimeout(timer));
	});
	const scopes = [];
	return {
		async init(plugins) {
			const statuses = [];
			for (const [name, init] of plugins) {
				const instance = runtime.scope(name);
				scopes.push(instance);
				try {
					const result = await deadline(Promise.resolve(init(null, instance.api)).then(value => {
						if (typeof value === 'function') instance.api.cleanup(value);
						else if (typeof value?.dispose === 'function') instance.api.cleanup(() => value.dispose());
						return value;
					}));
					statuses.push({ name, status: result === false ? 'failed' : 'ready' });
				} catch (error) {
					instance.dispose();
					statuses.push({ name, status: 'failed', error: String(error && error.message || error).slice(0, 120) });
				}
			}
			return statuses;
		},
		dispose() { for (const instance of scopes.reverse()) instance.dispose(); },
	};
}

// A core double reporting a scripted state through small diagnostics.
// behaviour: 'follow' (ready on resolve), 'stuck', 'fail-on-ready', 'after:N',
// 'throw-diagnostics', 'malformed', 'throw-init', 'bad-handle'.
export function coreDouble(behaviour = 'follow') {
	const log = { inits: 0, received: [], rejected: 0, disposed: 0, diagnostics: 0 };
	function initializeCore(parameters, api) {
		log.inits++;
		if (behaviour === 'throw-init') throw new Error('core double: init');
		if (behaviour === 'bad-handle') return { dispose() { log.disposed++; } };
		let state = 'loading';
		let ticks = 0;
		const ready = parameters && parameters.dictionaryReady;
		api.cleanup(() => dispose());
		Promise.prototype.then.call(ready, value => {
			log.received.push(value);
			if (state !== 'loading') return;
			if (behaviour === 'follow') state = 'ready';
			else if (behaviour === 'fail-on-ready') state = 'failed';
		}, () => { log.rejected++; if (state === 'loading') state = 'failed'; });
		function dispose() { log.disposed++; state = 'disposed'; }
		return Object.freeze({ dispose, diagnostics() {
			log.diagnostics++;
			if (behaviour === 'throw-diagnostics') throw new Error('core double: diagnostics');
			if (behaviour === 'malformed') return 'ready';
			const after = /^after:(\d+)$/.exec(behaviour);
			if (after && state === 'loading' && log.received.length && ++ticks >= Number(after[1])) state = 'ready';
			return Object.freeze({ state });
		} });
	}
	return { initializeCore, log };
}

// steps: {chunk: Uint8Array} | {value: any} | {done: true} | {reject: true} | {pending: true} | {malformed: true}
export function bodyDouble(steps, { stuckCancel = false } = {}) {
	const log = { reads: 0, cancels: 0, readers: 0, pending: [] };
	let index = 0;
	const reader = {
		read() {
			log.reads++;
			const step = steps[index++] || { done: true };
			if (step.reject) return Promise.reject(new Error('body double: read'));
			if (step.pending) return new Promise((resolve, reject) => log.pending.push({ resolve, reject }));
			if (step.malformed) return Promise.resolve(null);
			if (step.done) return Promise.resolve({ done: true, value: undefined });
			return Promise.resolve({ done: false, value: 'chunk' in step ? step.chunk : step.value });
		},
		cancel() { log.cancels++; return stuckCancel ? new Promise(() => {}) : Promise.resolve(); },
		releaseLock() {},
	};
	return { log, body: {
		getReader() { log.readers++; return reader; },
		cancel() { log.cancels++; return stuckCancel ? new Promise(() => {}) : Promise.resolve(); },
	} };
}

export function responseDouble({ url, status = 200, redirected = false, type = 'application/json; charset=utf-8', contentLength = null, body = null }) {
	const log = { bypass: 0 };
	const headers = new Map([['content-type', type]]);
	if (contentLength !== null) headers.set('content-length', String(contentLength));
	const bypass = () => { log.bypass++; throw new Error('response double: whole-body accessor used'); };
	return { log, response: {
		status, redirected, url, body,
		headers: { get: name => (headers.has(String(name).toLowerCase()) ? headers.get(String(name).toLowerCase()) : null) },
		text: bypass, json: bypass, arrayBuffer: bypass, blob: bypass, formData: bypass, clone: bypass,
	} };
}

export function chunksOf(bytes, sizes) {
	const out = [];
	let at = 0;
	for (const size of sizes) { out.push({ chunk: bytes.slice(at, at + size) }); at += size; }
	if (at < bytes.length) out.push({ chunk: bytes.slice(at) });
	return out;
}

// Wraps native fetch (or a scripted answer) and records each call.
export function recordingFetch(answer = (url, options) => fetch(url, options)) {
	const calls = [];
	const impl = (url, options) => { calls.push({ url, options }); return answer(url, options); };
	return { impl, calls };
}
'''

HARNESS = r'''// Authored browser harness for the dictionary loader. Groups are registered
// here, separately from the reporter's literal D01-D10 manifest. Tiny cases
// use the trusted factory over native fetch/WebCrypto/TextDecoder/JSON.parse
// against this fixture's own loopback paths, or Response doubles where a
// header/body shape cannot be produced honestly by HTTP; each is labelled.
// D09 (production default over the full copied body) runs only with ?full=1.
import { BASELINE_GROUPS, FAULT_MODES, ROOT_ONLY, createReporter, ledger } from './reporter.mjs';
import { createRuntime, createManager, coreDouble, bodyDouble, responseDouble, chunksOf, recordingFetch } from './doubles.mjs';
import { PINS, CORE_PIN, DICTIONARY_PIN, CSP, PAGE_BASE, FULL_AVAILABLE } from './cases.mjs';
import initializeNpcCore from '../loader/npc_plaintext_adapter.mjs';
import { createInitializer, createOwnedStatus, STATUS_TEXT, ERROR_CODES, jsonMediaType } from '../loader/dictionary_loader.mjs';

const boot = window.__t05Boot;
const params = new URLSearchParams(location.search);
const mode = params.get('fault') || 'baseline';
const suppress = params.get('suppress') === '1';
const runFull = params.get('full') === '1' && mode === 'baseline';
const faultGroup = params.get('group') || (mode === 'zero-assertions' ? 'D08' : 'D05');
const reporter = createReporter(BASELINE_GROUPS);
const faults = [];
const apiErrors = [];
const notes = [];
const stage = document.getElementById('stage');
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const settle = () => sleep(0);
const ORIGIN = location.origin;
const at = path => new URL(path, ORIGIN).href;
const runtime = createRuntime((category, error) => apiErrors.push({ category, message: String(error && error.message || error).slice(0, 160) }));
const bytesOf = async path => new Uint8Array(await (await fetch(at(path), { cache: 'no-store' })).arrayBuffer());
const hexOf = async bytes => [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(b => b.toString(16).padStart(2, '0')).join('');
try { performance.setResourceTimingBufferSize(2000); } catch { /* optional */ }

function ownedStatusNodes() { return [...document.querySelectorAll('[data-t05-dictionary-loader]')]; }
function noteText(text) { notes.push(String(text).slice(0, 400)); }

// Spies over the native pipeline pieces, preserving call order.
function natives(order = []) {
	const parses = [];
	const digests = [];
	return {
		order, parses, digests,
		digestImpl: bytes => { order.push('digest'); digests.push(bytes); return crypto.subtle.digest('SHA-256', bytes); },
		parseImpl: text => { order.push('parse'); const value = JSON.parse(text); parses.push(value); return value; },
	};
}

async function load(t, { dir, pin = PINS.tiny, timeoutMs = 5000, fetchImpl, core = 'real', statusFactory, scope, wait = true }) {
	const spies = natives();
	const fetcher = fetchImpl ? { impl: fetchImpl, calls: [] } : recordingFetch();
	const doubles = core === 'real' ? null : coreDouble(core);
	const instance = scope || runtime.scope('t05-' + dir);
	const init = createInitializer({
		initializeCore: doubles ? doubles.initializeCore : initializeNpcCore,
		moduleURL: at(`/case/${dir}/dictionary_loader.mjs`), pageURL: location.href,
		expected: pin, timeoutMs, fetchImpl: fetcher.impl,
		digestImpl: spies.digestImpl, parseImpl: spies.parseImpl,
		statusFactory: statusFactory || (() => createOwnedStatus(document)),
	});
	const started = performance.now();
	const handle = init({ url: '/decoy/dict.json', expected: PINS.decoyBase, timeoutMs: 1 }, instance.api);
	const run = { handle, instance, spies, fetcher, doubles, started, outcome: null, code: null };
	if (wait) await finish(run);
	return run;
}

async function finish(run) {
	try { run.outcome = await run.handle.ready; } catch (error) { run.outcome = error; run.code = error && error.code; }
	run.elapsed = performance.now() - run.started;
	return run;
}

function statusText() {
	const nodes = ownedStatusNodes();
	return nodes.length === 1 ? nodes[0].textContent : nodes.length === 0 ? null : 'MULTIPLE:' + nodes.length;
}

function npcBox(lines) {
	const host = document.createElement('section');
	const root = document.createElement('div');
	const content = document.createElement('div');
	content.className = 'content';
	for (const line of lines) { const row = document.createElement('div'); row.append(line); content.append(row); }
	root.append(content);
	host.append(root);
	stage.append(host);
	const component = { name: 'NpcBox', root, host };
	return { component, rows: () => [...content.children].map(row => row.textContent), detach() { runtime.remove(component); host.remove(); } };
}

function expectFailure(t, run, code, label) {
	t.equal(run.code, code, `${label}: ready rejects ${code}`);
	const d = run.handle.diagnostics();
	t.equal(d.state, 'failed', `${label}: diagnostics failed`);
	t.equal(d.errorCode, code, `${label}: errorCode`);
	t.equal(statusText(), STATUS_TEXT.failed(code), `${label}: failed Chinese status persists`);
	t.equal(run.spies.parses.length, 0, `${label}: no parse`);
}

function dispose(run) { run.handle.dispose(); run.instance.dispose(); }

function makeGroup(id, body) {
	return async () => {
		let assertions = 0;
		const errors = [];
		const t = {
			ok(value, message) { assertions++; if (!value) errors.push(String(message)); },
			equal(actual, wanted, message) { assertions++; if (!Object.is(actual, wanted)) errors.push(`${message}: got ${String(actual).slice(0, 80)}, want ${String(wanted).slice(0, 80)}`); },
		};
		try { await body(t); } catch (error) { errors.push('threw: ' + String(error && error.stack || error).slice(0, 300)); }
		if (ownedStatusNodes().length) { errors.push('owned status node left behind'); ownedStatusNodes().forEach(node => node.remove()); }
		reporter.record(id, assertions, errors);
	};
}

// --- D01 ---------------------------------------------------------------------
async function d01(t) {
	const fetches = recordingFetch(() => { throw new Error('must not fetch'); });
	const statusCalls = [];
	const core = coreDouble();
	const good = {
		initializeCore: core.initializeCore, moduleURL: at('/case/tiny/x.mjs'), pageURL: location.href,
		expected: PINS.tiny, timeoutMs: 1000, fetchImpl: fetches.impl, digestImpl: () => null,
		parseImpl: JSON.parse, statusFactory: () => { statusCalls.push(1); return { update() {}, dispose() {} }; },
	};
	const bad = [
		['no factory args', () => createInitializer()],
		['fetch not callable', () => createInitializer({ ...good, fetchImpl: null })],
		['expected bytes 0', () => createInitializer({ ...good, expected: { bytes: 0, sha256: PINS.tiny.sha256 } })],
		['expected uppercase hash', () => createInitializer({ ...good, expected: { bytes: 3, sha256: PINS.tiny.sha256.toUpperCase() } })],
		['timeout 1.5', () => createInitializer({ ...good, timeoutMs: 1.5 })],
		['relative module URL', () => createInitializer({ ...good, moduleURL: '/case/tiny/x.mjs' })],
		['module query', () => createInitializer({ ...good, moduleURL: at('/case/tiny/x.mjs?v=1') })],
		['module fragment', () => createInitializer({ ...good, moduleURL: at('/case/tiny/x.mjs#f') })],
		['module credentials', () => createInitializer({ ...good, moduleURL: ORIGIN.replace('://', '://u:p@') + '/case/tiny/x.mjs' })],
		['cross-origin module', () => createInitializer({ ...good, moduleURL: 'http://example.invalid/x.mjs' })],
		['data module', () => createInitializer({ ...good, moduleURL: 'data:text/javascript,1' })],
		['api missing', () => createInitializer(good)(null, null)],
		['api version 2', () => createInitializer(good)(null, { version: 2, on() {}, cleanup() {} })],
		['api.on missing', () => createInitializer(good)(null, { version: 1, cleanup() {} })],
	];
	for (const [label, fn] of bad) {
		let threw = false;
		try { fn(); } catch (error) { threw = error instanceof TypeError; }
		t.ok(threw, `gate rejects synchronously: ${label}`);
	}
	t.equal(fetches.calls.length + statusCalls.length + core.log.inits, 0, 'gates did no fetch/status/core work');

	// Page query/fragment allowed; returned handle shape.
	const pageQuery = createInitializer({ ...good, pageURL: location.href + '#frag' });
	t.equal(typeof pageQuery, 'function', 'page query/fragment accepted');
	t.equal(fetches.calls.length, 0, 'factory creation started nothing');

	// Next-plugin sentinel while dictionary work is pending (delay endpoint).
	const manager = createManager(runtime);
	let loaderHandle = null;
	const seen = {};
	const statuses = await manager.init([
		['t05-loader', (pars, api) => {
			loaderHandle = createInitializer({ ...good, initializeCore: initializeNpcCore, moduleURL: at('/case/delay/x.mjs'),
				fetchImpl: (u, o) => fetch(u, o), digestImpl: b => crypto.subtle.digest('SHA-256', b),
				statusFactory: () => createOwnedStatus(document), timeoutMs: 5000 })(pars, api);
			return loaderHandle;
		}],
		['next-sentinel', () => { seen.state = loaderHandle.diagnostics().state; seen.text = statusText(); return true; }],
	]);
	t.equal(statuses.map(s => s.status).join(','), 'ready,ready', 'manager reports both plugins ready');
	t.equal(seen.state, 'loading', 'next plugin ran while loader still loading');
	t.equal(seen.text, STATUS_TEXT.loading, 'loading status visible to next plugin');
	t.ok(Object.isFrozen(loaderHandle) && !('then' in loaderHandle), 'frozen non-thenable handle');
	t.equal(Object.keys(loaderHandle).sort().join(','), 'diagnostics,dispose,ready', 'handle is {dispose, ready, diagnostics}');
	t.equal(await loaderHandle.ready, 'ready', 'delayed dictionary becomes ready');
	manager.dispose();
	t.equal(loaderHandle.diagnostics().state, 'disposed', 'adopted disposer ran');
	loaderHandle.dispose();
	t.equal(statusText(), null, 'double dispose harmless; status removed');

	// Already-dead scope: cleanup disposes immediately; nothing afterwards.
	const dead = runtime.scope('t05-dead', { dead: true });
	const deadFetch = recordingFetch();
	const deadCore = coreDouble();
	let deadStatus = 0;
	const handle = createInitializer({ ...good, initializeCore: deadCore.initializeCore, fetchImpl: deadFetch.impl,
		statusFactory: () => { deadStatus++; return { update() {}, dispose() {} }; } })(null, dead.api);
	t.equal(handle.diagnostics().state, 'disposed', 'dead scope returns disposed handle');
	let code = null;
	try { await handle.ready; } catch (error) { code = error.code; }
	t.equal(code, 'DISPOSED', 'dead scope ready rejects DISPOSED (handled)');
	await sleep(20);
	t.equal(deadFetch.calls.length + deadStatus + deadCore.log.inits, 0, 'dead scope: no fetch/status/core');

	// Dispose while fetch pending; late resolution cannot revive.
	let release;
	const pending = await load(t, { dir: 'tiny', core: 'follow', fetchImpl: () => new Promise(resolve => { release = resolve; }), wait: false });
	pending.handle.dispose();
	await finish(pending);
	t.equal(pending.code, 'DISPOSED', 'pending dispose rejects DISPOSED');
	release(responseDouble({ url: at('/case/tiny/dict.json'), body: bodyDouble(chunksOf(new TextEncoder().encode('{}'), [])).body }).response);
	await sleep(20);
	t.equal(pending.handle.diagnostics().state, 'disposed', 'late fetch resolution does not revive');
	t.equal(pending.spies.digests.length, 0, 'no digest after disposal');
	pending.instance.dispose();
}

// --- D02 ---------------------------------------------------------------------
async function d02(t) {
	t.ok(document.baseURI.endsWith('/decoy/'), 'document base differs from page and module');
	t.ok(location.pathname.endsWith('/pages/run/index.html'), 'nested page');
	performance.clearResourceTimings();
	const module = await import('../loader/dictionary_loader.mjs');
	const scope = runtime.scope('t05-default');
	const handle = module.default({ url: '/decoy/dict.json', dictionary: '/pages/run/dict.json' }, scope.api);
	t.equal(handle.diagnostics().state, 'loading', 'production default returns synchronously');
	t.equal(statusText(), STATUS_TEXT.loading, 'production status loading');
	let code = null;
	try { await handle.ready; } catch (error) { code = error.code; }
	t.equal(code, 'TRUNCATED', 'tiny sibling body is not the 19706353-byte pin');
	t.equal(handle.diagnostics().expectedBytes, DICTIONARY_PIN.bytes, 'production pin bytes');
	await sleep(50);
	const dicts = performance.getEntriesByType('resource').map(e => new URL(e.name).pathname).filter(p => p.endsWith('/dict.json'));
	t.equal(dicts.filter(p => p === '/loader/dict.json').length, 1, 'exactly one request beside the imported entry');
	t.equal(dicts.filter(p => p !== '/loader/dict.json').length, 0, 'no page-relative/base-relative/override request');
	handle.dispose(); scope.dispose();
	t.equal(statusText(), null, 'dispose removes owned status');

	// Trusted factory: fixed URL and options; parameters ignored; no retry.
	const run = await load(t, { dir: 'tiny' });
	t.equal(run.outcome, 'ready', 'tiny factory ready');
	t.equal(run.fetcher.calls.length, 1, 'one request');
	const call = run.fetcher.calls[0];
	t.equal(call.url, at('/case/tiny/dict.json'), 'module-relative URL, not page/base');
	const o = call.options;
	t.equal([o.method, o.mode, o.credentials, o.redirect, o.cache].join(','), 'GET,same-origin,omit,error,no-store', 'fixed request options');
	t.ok(o.signal instanceof AbortSignal && !o.signal.aborted, 'owned abort signal');
	dispose(run);
	const miss = await load(t, { dir: 'missing' });
	t.equal(miss.code, 'HTTP_STATUS', '404 fails');
	t.equal(miss.fetcher.calls.length, 1, 'no retry or fallback URL');
	t.ok(miss.fetcher.calls[0].options.signal.aborted, 'request aborted on failure');
	dispose(miss);
}

// --- D03 ---------------------------------------------------------------------
async function d03(t) {
	for (const dir of ['tiny', 'chunked', 'gzip', 'no-store-plain']) {
		performance.clearResourceTimings();
		const box = npcBox(['Hello', 'Unknown line']);
		runtime.append(box.component);
		const run = await load(t, { dir });
		t.equal(run.outcome, 'ready', `${dir}: ready`);
		const d = run.handle.diagnostics();
		t.equal(d.receivedBytes, PINS.tiny.bytes, `${dir}: counted decoded bytes`);
		t.equal(d.coreState, 'ready', `${dir}: core ready`);
		t.equal(run.spies.order.join(','), 'digest,parse', `${dir}: SHA before one parse`);
		t.equal(run.spies.digests[0].byteLength, PINS.tiny.bytes, `${dir}: digest over exactly sized buffer`);
		t.equal(run.spies.digests[0].buffer.byteLength, PINS.tiny.bytes, `${dir}: one exactly sized backing buffer`);
		await settle();
		t.equal(box.rows().join('|'), '哈囉|Unknown line', `${dir}: narrow translation after core ready`);
		t.equal(statusText(), STATUS_TEXT.ready, `${dir}: ready status`);
		const entry = performance.getEntriesByType('resource').find(e => new URL(e.name).pathname === `/case/${dir}/dict.json`);
		if (entry) noteText(`D03 ${dir}: transferSize=${entry.transferSize} encodedBodySize=${entry.encodedBodySize} decodedBodySize=${entry.decodedBodySize} (observation only)`);
		if (dir === 'gzip' && entry) t.equal(entry.decodedBodySize, PINS.tiny.bytes, 'gzip: decoded size equals pin (wire size is a separate observation)');
		box.detach();
		dispose(run);
	}

	// Doubles: absent/misleading Content-Length; chunks; same object to core.
	const tiny = await bytesOf('/case/tiny/dict.json');
	for (const contentLength of [null, 999999999, 1]) {
		const body = bodyDouble(chunksOf(tiny, [1, 2, 5]));
		const response = responseDouble({ url: at('/case/tiny/dict.json'), contentLength, body: body.body });
		const run = await load(t, { dir: 'tiny', core: 'follow', fetchImpl: () => Promise.resolve(response.response) });
		t.equal(run.outcome, 'ready', `double Content-Length ${contentLength}: ready (header ignored)`);
		t.equal(run.spies.parses.length, 1, 'one parse');
		t.ok(run.doubles.log.received[0] === run.spies.parses[0], 'exact parsed object handed to core');
		t.equal(response.log.bypass, 0, 'no text/json/arrayBuffer bypass');
		t.ok(body.log.reads >= 4, 'read one chunk at a time to EOF');
		dispose(run);
	}
	t.equal(jsonMediaType('application/json; charset="UTF-8"'), true, 'quoted UTF-8 charset accepted');
}

// --- D04 ---------------------------------------------------------------------
async function d04(t) {
	const http = [
		['missing', PINS.tiny, 'HTTP_STATUS'], ['status-500', PINS.tiny, 'HTTP_STATUS'],
		['wrong-mime', PINS.tiny, 'MEDIA_TYPE'], ['other-charset', PINS.tiny, 'MEDIA_TYPE'],
		['redirect', PINS.tiny, 'FETCH'], ['tiny', PINS.tinyLong, 'TRUNCATED'],
		['tiny', PINS.tinyShort, 'OVERSIZE'], ['tiny', PINS.tinyWrongHash, 'IDENTITY'],
	];
	for (const [dir, pin, code] of http) {
		const run = await load(t, { dir, pin, core: 'follow' });
		expectFailure(t, run, code, `http ${dir}`);
		await settle();
		t.equal(run.doubles.log.rejected, 1, `http ${dir}: core dictionary rejected, no handoff`);
		t.equal(run.doubles.log.received.length, 0, `http ${dir}: core received nothing`);
		dispose(run);
	}
	// Native framing that lies about length: the transport may reject; any
	// such rejection is not a loader defect and must still never parse.
	const framing = await load(t, { dir: 'framing-short', core: 'follow' });
	t.ok(['READ', 'FETCH', 'TRUNCATED'].includes(framing.code), 'http framing-short: transport/length rejection ' + framing.code);
	t.equal(framing.spies.parses.length, 0, 'http framing-short: no parse');
	dispose(framing);

	const tiny = await bytesOf('/case/tiny/dict.json');
	const url = at('/case/tiny/dict.json');
	const doubles = [
		['redirected flag', { redirected: true }, null, 'REDIRECT'],
		['final URL differs', { url: at('/case/other/dict.json') }, null, 'REDIRECT'],
		['two media types', { type: 'application/json, text/plain' }, null, 'MEDIA_TYPE'],
		['extra parameter', { type: 'application/json; charset=utf-8; q=1' }, null, 'MEDIA_TYPE'],
		['missing body', {}, 'none', 'BODY'],
		['read rejects', {}, [{ reject: true }], 'READ'],
		['malformed read', {}, [{ malformed: true }], 'READ'],
		['zero chunk', {}, [{ chunk: new Uint8Array(0) }], 'CHUNK'],
		['ArrayBuffer chunk', {}, [{ value: tiny.buffer.slice(0) }], 'CHUNK'],
		['truncated', {}, chunksOf(tiny.slice(0, 5), []), 'TRUNCATED'],
		['oversize', {}, [{ chunk: tiny }, { chunk: new Uint8Array([32]) }], 'OVERSIZE'],
	];
	for (const [label, shape, steps, code] of doubles) {
		const body = steps === 'none' ? null : bodyDouble(steps || chunksOf(tiny, []));
		const response = responseDouble({ url, ...shape, body: body ? body.body : null });
		const run = await load(t, { dir: 'tiny', core: 'follow', fetchImpl: () => Promise.resolve(response.response) });
		expectFailure(t, run, code, `double ${label}`);
		if (body && code !== 'TRUNCATED') t.ok(body.log.cancels >= 1, `double ${label}: body cancelled`);
		t.equal(response.log.bypass, 0, `double ${label}: no whole-body accessor`);
		dispose(run);
	}
	for (const [label, digestImpl, code] of [
		['digest rejects', () => Promise.reject(new Error('x')), 'DIGEST'],
		['digest 16 bytes', () => Promise.resolve(new ArrayBuffer(16)), 'DIGEST'],
		['digest wrong', () => Promise.resolve(new ArrayBuffer(32)), 'IDENTITY'],
	]) {
		const spies = natives();
		const core = coreDouble();
		const scope = runtime.scope('t05-digest');
		const handle = createInitializer({ initializeCore: core.initializeCore, moduleURL: at('/case/tiny/x.mjs'), pageURL: location.href,
			expected: PINS.tiny, timeoutMs: 5000, fetchImpl: (u, o) => fetch(u, o), digestImpl, parseImpl: spies.parseImpl,
			statusFactory: () => createOwnedStatus(document) })(null, scope.api);
		let got = null;
		try { await handle.ready; } catch (error) { got = error.code; }
		t.equal(got, code, `double ${label}: ${code}`);
		t.equal(spies.parses.length, 0, `double ${label}: no parse`);
		handle.dispose(); scope.dispose();
	}
}

// --- D05 ---------------------------------------------------------------------
async function d05(t) {
	for (const [dir, code, parses] of [['bad-utf8', 'DECODE', 0], ['bad-json', 'PARSE', 1], ['scalar', 'CONTAINER', 1], ['array', 'CONTAINER', 1], ['null', 'CONTAINER', 1]]) {
		const run = await load(t, { dir, pin: PINS[dir], core: 'follow' });
		t.equal(run.code, code, `${dir}: ${code}`);
		t.equal(run.spies.parses.length + (code === 'PARSE' ? 1 : 0), parses, `${dir}: parse count ${parses}`);
		t.equal(run.spies.order[0], 'digest', `${dir}: identity checked first`);
		t.equal(run.doubles.log.received.length, 0, `${dir}: no handoff`);
		t.equal(statusText(), STATUS_TEXT.failed(code), `${dir}: failed status`);
		dispose(run);
	}
	const box = npcBox(['Hello', 'Bad number', 'Bad colour', 'constructor']);
	runtime.append(box.component);
	const run = await load(t, { dir: 'unsafe', pin: PINS.unsafe });
	t.equal(run.outcome, 'ready', 'unsafe entries: container accepted without entry validation');
	await settle();
	t.equal(box.rows().join('|'), '哈囉|Bad number|Bad colour|建構', 'core per-entry policy: only safe string targets used');
	t.equal(({}).polluted, undefined, 'no prototype pollution');
	t.equal(Object.getPrototypeOf(run.spies.parses[0]), Object.prototype, 'native JSON.parse object, not cloned');
	box.detach();
	dispose(run);
	// Null-prototype container from a trusted parser is accepted.
	const core = coreDouble();
	const scope = runtime.scope('t05-nullproto');
	const handle = createInitializer({ initializeCore: core.initializeCore, moduleURL: at('/case/tiny/x.mjs'), pageURL: location.href,
		expected: PINS.tiny, timeoutMs: 5000, fetchImpl: (u, o) => fetch(u, o), digestImpl: b => crypto.subtle.digest('SHA-256', b),
		parseImpl: text => Object.assign(Object.create(null), JSON.parse(text)), statusFactory: () => createOwnedStatus(document) })(null, scope.api);
	t.equal(await handle.ready, 'ready', 'null-prototype container ready');
	handle.dispose(); scope.dispose();
}

// --- D06 ---------------------------------------------------------------------
async function d06(t) {
	for (const [dir, phase] of [['stall-headers', 'request'], ['stall-body', 'read']]) {
		const run = await load(t, { dir, timeoutMs: 400, core: 'follow' });
		t.equal(run.code, 'TIMEOUT', `http ${dir}: TIMEOUT`);
		t.ok(run.elapsed >= 400, `http ${dir}: real elapsed ${Math.round(run.elapsed)} ms ≥ 400`);
		t.equal(run.handle.diagnostics().phase, phase, `http ${dir}: failed in ${phase}`);
		t.ok(run.fetcher.calls[0].options.signal.aborted, `http ${dir}: request aborted`);
		t.equal(statusText(), STATUS_TEXT.failed('TIMEOUT'), `http ${dir}: failed status`);
		dispose(run);
	}
	// Stalled digest; its late result cannot revive.
	let lateDigest;
	{
		const core = coreDouble();
		const scope = runtime.scope('t05-stall-digest');
		const handle = createInitializer({ initializeCore: core.initializeCore, moduleURL: at('/case/tiny/x.mjs'), pageURL: location.href,
			expected: PINS.tiny, timeoutMs: 300, fetchImpl: (u, o) => fetch(u, o),
			digestImpl: () => new Promise(resolve => { lateDigest = resolve; }), parseImpl: JSON.parse,
			statusFactory: () => createOwnedStatus(document) })(null, scope.api);
		let code = null;
		try { await handle.ready; } catch (error) { code = error.code; }
		t.equal(code, 'TIMEOUT', 'stalled digest: TIMEOUT');
		t.equal(handle.diagnostics().phase, 'digest', 'stalled digest phase');
		lateDigest(await crypto.subtle.digest('SHA-256', await bytesOf('/case/tiny/dict.json')));
		await sleep(30);
		t.equal(handle.diagnostics().state, 'failed', 'late digest does not revive');
		t.equal(core.log.received.length, 0, 'late digest: no handoff');
		handle.dispose(); scope.dispose();
	}
	// Dispose during a pending read with a stuck cancel: synchronous, terminal.
	const tiny = await bytesOf('/case/tiny/dict.json');
	const body = bodyDouble([{ chunk: tiny.slice(0, 4) }, { pending: true }], { stuckCancel: true });
	const response = responseDouble({ url: at('/case/tiny/dict.json'), body: body.body });
	const reading = await load(t, { dir: 'tiny', core: 'follow', fetchImpl: () => Promise.resolve(response.response), wait: false });
	await sleep(20);
	reading.handle.dispose();
	t.equal(reading.handle.diagnostics().state, 'disposed', 'dispose during read is synchronous despite stuck cancel');
	t.ok(body.log.cancels >= 1, 'reader cancel initiated');
	await finish(reading);
	t.equal(reading.code, 'DISPOSED', 'pending read: ready rejects DISPOSED');
	body.log.pending[0].resolve({ done: false, value: tiny.slice(4) });
	await sleep(20);
	t.equal(reading.handle.diagnostics().receivedBytes, 4, 'late chunk not counted');
	t.equal(statusText(), null, 'disposed status not recreated');
	reading.instance.dispose();
	// Activation: stuck/failed/throwing/malformed core diagnostics.
	for (const behaviour of ['stuck', 'fail-on-ready', 'throw-diagnostics', 'malformed']) {
		const run = await load(t, { dir: 'tiny', core: behaviour });
		t.equal(run.code, 'CORE', `core ${behaviour}: CORE`);
		t.equal(run.handle.diagnostics().phase, 'activate', `core ${behaviour}: activation phase`);
		t.ok(run.doubles.log.disposed >= 1, `core ${behaviour}: core disposed after handoff`);
		dispose(run);
	}
	// Synchronous parse beyond the deadline is not interrupted; checked after.
	{
		const core = coreDouble();
		const scope = runtime.scope('t05-slow-parse');
		const handle = createInitializer({ initializeCore: core.initializeCore, moduleURL: at('/case/tiny/x.mjs'), pageURL: location.href,
			expected: PINS.tiny, timeoutMs: 150, fetchImpl: (u, o) => fetch(u, o), digestImpl: b => crypto.subtle.digest('SHA-256', b),
			parseImpl: text => { const until = performance.now() + 200; while (performance.now() < until) { /* busy */ } return JSON.parse(text); },
			statusFactory: () => createOwnedStatus(document) })(null, scope.api);
		let code = null;
		try { await handle.ready; } catch (error) { code = error.code; }
		t.equal(code, 'TIMEOUT', 'slow synchronous parse: TIMEOUT checked after it returns');
		t.ok(handle.diagnostics().parseMs >= 150, 'parse ran to completion (no preemption)');
		t.equal(core.log.received.length, 0, 'no handoff after overdue parse');
		handle.dispose(); scope.dispose();
		noteText('D06: a synchronous parse/decode cannot be preempted by the logical deadline; it is detected after it returns.');
	}
	// Dispose after ready: ready stays resolved; diagnostics authoritative.
	const done = await load(t, { dir: 'tiny', core: 'follow' });
	done.handle.dispose();
	t.equal(await done.handle.ready, 'ready', 'historical ready stays resolved');
	t.equal(done.handle.diagnostics().state, 'disposed', 'diagnostics says disposed');
	t.equal(done.handle.diagnostics().coreState, 'disposed', 'core disposed');
	done.instance.dispose();
}

// --- D07 ---------------------------------------------------------------------
async function d07(t) {
	const late = await load(t, { dir: 'tiny', core: 'after:3', wait: false });
	t.equal(statusText(), STATUS_TEXT.loading, 'loading label');
	await finish(late);
	t.equal(late.outcome, 'ready', 'ready only once core reports ready after checkpoints');
	t.ok(late.doubles.log.diagnostics >= 3, 'core diagnostics polled at checkpoints');
	t.equal(statusText(), STATUS_TEXT.ready, 'ready label');
	const d = late.handle.diagnostics();
	t.ok(Object.isFrozen(d) && d !== late.handle.diagnostics(), 'fresh frozen snapshot');
	t.ok(Object.values(d).every(v => v === null || ['string', 'number'].includes(typeof v)), 'primitive-only snapshot');
	for (const key of ['requestMs', 'readMs', 'digestMs', 'decodeMs', 'parseMs', 'activateMs', 'totalMs']) {
		t.ok(Number.isFinite(d[key]) && d[key] >= 0, `${key} finite nonnegative`);
	}
	t.equal(Object.keys(d).join(','), 'state,phase,errorCode,receivedBytes,expectedBytes,coreState,requestMs,readMs,digestMs,decodeMs,parseMs,activateMs,totalMs', 'documented fields only');
	dispose(late);

	const failed = await load(t, { dir: 'tiny', pin: PINS.tinyWrongHash, core: 'follow' });
	const f = failed.handle.diagnostics();
	t.equal(f.decodeMs, null, 'unreached stages null');
	t.ok(Number.isFinite(f.digestMs), 'failed stage timing retained');
	await sleep(30);
	t.equal(statusText(), STATUS_TEXT.failed('IDENTITY'), 'failure persists');
	const other = document.createElement('div'); other.className = 'foreign'; document.body.append(other);
	failed.handle.dispose(); failed.handle.dispose();
	t.equal(statusText(), null, 'disposal removes the owned node');
	t.ok(other.isConnected, 'foreign node untouched'); other.remove();
	failed.instance.dispose();

	for (const [label, factory, code] of [
		['factory throws', () => { throw new Error('status'); }, 'STATUS'],
		['factory malformed', () => ({ update() {} }), 'STATUS'],
		['update throws on loading', () => ({ update() { throw new Error('u'); }, dispose() {} }), 'STATUS'],
	]) {
		const run = await load(t, { dir: 'tiny', core: 'follow', statusFactory: factory });
		t.equal(run.code, code, `${label}: ${code}`);
		t.equal(run.fetcher.calls.length, 0, `${label}: no request started`);
		dispose(run);
	}
	let updates = 0;
	const readyThrows = await load(t, { dir: 'tiny', core: 'follow', statusFactory: () => ({ update(state) { updates++; if (state === 'ready') throw new Error('r'); }, dispose() {} }) });
	t.equal(readyThrows.code, 'STATUS', 'ready update throws: STATUS');
	t.ok(readyThrows.doubles.log.disposed >= 1, 'core disposed after STATUS at activation');
	dispose(readyThrows);
	const disposeThrows = await load(t, { dir: 'tiny', core: 'follow', statusFactory: () => ({ update() {}, dispose() { throw new Error('d'); } }) });
	disposeThrows.handle.dispose();
	t.equal(disposeThrows.handle.diagnostics().state, 'disposed', 'status dispose error keeps disposed');
	t.equal(disposeThrows.handle.diagnostics().errorCode, 'DISPOSE', 'bounded DISPOSE diagnostic');
	disposeThrows.instance.dispose();

	const s = createOwnedStatus(document);
	s.update('loading', null);
	const owned = ownedStatusNodes()[0];
	t.equal(owned.getAttribute('role') + '/' + owned.getAttribute('aria-live'), 'status/polite', 'role=status aria-live=polite');
	t.equal(owned.childNodes.length === 1 && owned.firstChild.nodeType, 3, 'one native Text');
	s.dispose();
	t.ok(ERROR_CODES.length === 20 && ERROR_CODES.every(c => /^[A-Z_]+$/.test(c)), 'bounded documented codes');
}

// --- D08 ---------------------------------------------------------------------
async function d08(t) {
	const provenance = await (await fetch(at('/provenance.json'), { cache: 'no-store' })).json();
	t.equal(provenance.task, 'T05.005', 'provenance task');
	t.equal(provenance.csp, CSP, 'provenance CSP');
	const meta = document.querySelector('meta[http-equiv="Content-Security-Policy"]');
	t.equal(meta && meta.content, CSP, 'page CSP is the recorded policy');
	const loaderBytes = await bytesOf('/loader/dictionary_loader.mjs');
	const coreBytes = await bytesOf('/loader/npc_plaintext_adapter.mjs');
	t.equal(await hexOf(loaderBytes), provenance.loader.sha256, 'served loader bytes match provenance');
	t.equal(coreBytes.length, CORE_PIN.bytes, 'served core size equals pin');
	t.equal(await hexOf(coreBytes), CORE_PIN.sha256, 'served core SHA equals pin');
	t.equal(await hexOf(await bytesOf('/broken/dictionary_loader.mjs')), provenance.loader.sha256, 'broken/ loader is byte-identical');
	t.equal(provenance.imports.length, 1, 'one relative import recorded');
	t.equal(provenance.imports[0].specifier, './npc_plaintext_adapter.mjs', 'loader imports adjacent core');
	for (const file of provenance.files.filter(f => /\.(?:mjs|js|json|html|css)$/.test(f.path) && !f.path.startsWith('full/') && f.path !== 'provenance.json').slice(0, 64)) {
		t.equal(await hexOf(await bytesOf('/' + file.path)), file.sha256, 'served ' + file.path);
	}
	t.equal(provenance.dictionary.copied === null, !FULL_AVAILABLE, 'full/ presence matches provenance');
	t.ok(provenance.files.every(f => f.mode === '0600'), 'all generated files 0600');
	noteText('D08: builder refusal negatives are run by the Node suite and recorded in the private report, not in the browser.');
}

// --- D09 ---------------------------------------------------------------------
async function d09(t) {
	t.ok(FULL_AVAILABLE, 'full/ production body copied into this fixture');
	if (!FULL_AVAILABLE) return;
	const observation = { longTasks: [], lags: [], memory: null };
	let observer = null;
	if (typeof PerformanceObserver === 'function' && (PerformanceObserver.supportedEntryTypes || []).includes('longtask')) {
		observer = new PerformanceObserver(list => { for (const e of list.getEntries()) observation.longTasks.push(Math.round(e.duration)); });
		observer.observe({ type: 'longtask' });
	}
	let sampling = true;
	let last = performance.now();
	(function sample() { if (!sampling) return; const now = performance.now(); observation.lags.push(now - last - 50); last = now; setTimeout(sample, 50); })();
	const heap = () => (performance.memory && Number.isFinite(performance.memory.usedJSHeapSize) ? performance.memory.usedJSHeapSize : null);
	const heapBefore = heap();
	performance.clearResourceTimings();
	const module = await import('../full/dictionary_loader.mjs');
	const scope = runtime.scope('t05-full');
	const started = performance.now();
	const handle = module.default(null, scope.api);
	const labels = [statusText()];
	let outcome = null;
	try { outcome = await handle.ready; } catch (error) { outcome = 'rejected:' + error.code; }
	const wall = performance.now() - started;
	labels.push(statusText());
	const heapAfter = heap();
	sampling = false;
	if (observer) observer.disconnect();
	const d = handle.diagnostics();
	t.equal(outcome, 'ready', 'production default ready over the full body');
	t.equal(labels[0], STATUS_TEXT.loading, 'loading label first');
	t.equal(labels[1], STATUS_TEXT.ready, 'ready label only after full pipeline');
	t.equal(d.receivedBytes, DICTIONARY_PIN.bytes, 'received exactly 19706353 decoded bytes');
	t.equal(d.coreState, 'ready', 'unchanged core ready');
	for (const key of ['requestMs', 'readMs', 'digestMs', 'decodeMs', 'parseMs', 'activateMs', 'totalMs']) t.ok(Number.isFinite(d[key]), `${key} observed`);
	await sleep(50);
	const entries = performance.getEntriesByType('resource').filter(e => new URL(e.name).pathname === '/full/dict.json');
	t.equal(entries.length, 1, 'one production request beside full/ entry');
	const entry = entries[0];
	if (entry && entry.decodedBodySize) t.equal(entry.decodedBodySize, DICTIONARY_PIN.bytes, 'resource decoded size');
	handle.dispose(); scope.dispose();
	t.equal(handle.diagnostics().state, 'disposed', 'disposed after full run');
	t.equal(statusText(), null, 'status removed');
	const lags = observation.lags.filter(Number.isFinite);
	window.__t05D09 = Object.freeze({
		...d, wallMs: wall,
		resource: entry ? { transferSize: entry.transferSize, encodedBodySize: entry.encodedBodySize, decodedBodySize: entry.decodedBodySize, duration: entry.duration } : 'unobserved',
		longTasks: observer ? observation.longTasks : 'unobserved (longtask unsupported)',
		maxTimerLagMs: lags.length ? Math.max(...lags) : 'unobserved',
		heap: heapBefore === null ? 'unobserved (no performance.memory)' : { before: heapBefore, after: heapAfter, note: 'coarse, non-standard; not peak' },
	});
	noteText('D09: ' + JSON.stringify(window.__t05D09));
}

// --- D10 ---------------------------------------------------------------------
async function d10(t) {
	t.equal(BASELINE_GROUPS.length, 10, 'manifest has ten literal groups');
	t.equal(BASELINE_GROUPS.map(g => g.id).join(','), 'D01,D02,D03,D04,D05,D06,D07,D08,D09,D10', 'fixed identifiers');
	t.equal(FAULT_MODES.length, 10, 'ten actual fault modes');
	const all = r => { for (const g of BASELINE_GROUPS) r.record(g.id, 1, []); return r; };
	t.equal(all(createReporter()).summary().state, 'pass', 'all ten with assertions pass');
	const omitD10 = createReporter(); for (const g of BASELINE_GROUPS.slice(0, 9)) omitD10.record(g.id, 1, []);
	t.equal(omitD10.summary().state, 'fail', 'omitted D10 fails');
	const omitD09 = createReporter(); for (const g of BASELINE_GROUPS) if (g.id !== ROOT_ONLY) omitD09.record(g.id, 1, []);
	t.equal(omitD09.summary().missing.join(','), 'D09', 'unrun D09 is missing, not passed');
	t.equal(omitD09.summary().state, 'fail', 'nine groups never PASS');
	const zero = createReporter(); for (const g of BASELINE_GROUPS) zero.record(g.id, g.id === 'D03' ? 0 : 1, []);
	t.equal(zero.summary().state, 'fail', 'zero assertions fails');
	const lateFail = all(createReporter()); lateFail.fail('late');
	t.equal(lateFail.summary().state, 'fail', 'late failure is sticky');
	const extra = all(createReporter()); extra.record('D11', 1, []);
	t.equal(extra.summary().state, 'fail', 'unexpected group fails');
	const twice = all(createReporter()); twice.record('D01', 1, []);
	t.equal(twice.summary().state, 'fail', 'duplicate group fails');
	const shrunk = createReporter(BASELINE_GROUPS.slice(0, 9)); for (const g of BASELINE_GROUPS.slice(0, 9)) shrunk.record(g.id, 1, []);
	t.equal(shrunk.summary().state, 'fail', 'nine-group denominator cannot pass');
	for (const name of FAULT_MODES) {
		t.equal(ledger(name, [{ mode: name }]).find(r => r.mode === name).state, 'NOT OBSERVED', `mode-only record not observed: ${name}`);
		t.equal(ledger(name, []).filter(r => r.state === 'NOT RUN').length, 9, `other rows NOT RUN: ${name}`);
	}
}

const REGISTRATIONS = [['D01', d01], ['D02', d02], ['D03', d03], ['D04', d04], ['D05', d05], ['D06', d06], ['D07', d07], ['D08', d08], ['D09', d09], ['D10', d10]];

// --- actual fault injections (after ordinary groups) --------------------------
async function inject() {
	if (mode === 'baseline' || suppress) return;
	const record = value => faults.push({ mode, ...value });
	const status = async path => { try { return (await fetch(at(path), { cache: 'no-store' })).status; } catch { return null; } };
	if (mode === 'missing-loader') {
		let rejected = false;
		try { await import('../absent/dictionary_loader.mjs'); } catch { rejected = true; }
		record({ sink: 'dynamic-import', target: 'absent-loader', rejected, probeStatus: await status('/absent/dictionary_loader.mjs') });
	} else if (mode === 'missing-core') {
		let rejected = false;
		try { await import('../broken/dictionary_loader.mjs'); } catch { rejected = true; }
		record({ sink: 'dynamic-import', target: 'broken-loader', rejected, loaderStatus: await status('/broken/dictionary_loader.mjs'), coreStatus: await status('/broken/npc_plaintext_adapter.mjs') });
	} else if (mode === 'csp-inline') {
		window.__t05InlineRan = false;
		const before = boot.csp.length;
		const script = document.createElement('script');
		script.textContent = 'window.__t05InlineRan = true;';
		document.body.append(script);
		await sleep(100);
		for (const v of boot.csp.slice(before)) record({ sink: 'csp-violation', directive: v.directive, blocked: v.blocked, ran: window.__t05InlineRan === true });
	} else if (mode === 'loader-reject' || mode === 'loader-timeout') {
		const timeoutMs = 300;
		const run = await load(null, { dir: mode === 'loader-reject' ? 'missing' : 'stall-headers', timeoutMs });
		const d = run.handle.diagnostics();
		record({ sink: 'loader-ready', code: run.code, state: d.state, elapsedMs: Math.round(run.elapsed), timeoutMs, statusText: statusText(), expectedText: STATUS_TEXT.failed(run.code) });
		dispose(run);
	} else if (mode === 'api-error' || mode === 'cleanup-error') {
		const box = npcBox(['Hello']);
		runtime.append(box.component);
		const run = await load(null, { dir: 'tiny' });
		await settle();
		const ordinaryActionDone = run.outcome === 'ready' && box.rows()[0] === '哈囉';
		const before = apiErrors.length;
		if (mode === 'api-error') {
			run.instance.api.on('ui:append', () => { throw new Error('T05.005 injected listener error'); }, { replay: false });
			const second = npcBox(['Goodbye']);
			runtime.append(second.component);
			await settle();
			second.detach();
			for (const e of apiErrors.slice(before)) record({ sink: 'api-error-sink', category: e.category, message: e.message, ordinaryActionDone });
		} else {
			run.instance.api.cleanup(() => { throw new Error('T05.005 injected cleanup throw'); });
			run.instance.api.cleanup(() => Promise.reject(new Error('T05.005 injected cleanup rejection')));
			run.handle.dispose();
			run.instance.dispose();
			await sleep(20);
			const fresh = apiErrors.slice(before).filter(e => e.category === 'cleanup');
			if (fresh.length) record({ sink: 'api-error-sink', category: 'cleanup', thrown: fresh.some(e => /cleanup throw/.test(e.message)), rejected: fresh.some(e => /cleanup rejection/.test(e.message)), ordinaryActionDone });
		}
		box.detach();
		dispose(run);
	} else if (mode === 'unhandled-rejection') {
		Promise.reject(new Error('T05.005 injected unhandled rejection'));
		await sleep(100);
		if (boot.rejections.includes('T05.005 injected unhandled rejection')) record({ sink: 'boot-unhandledrejection', matched: true });
	}
}

function render(summary, rows, final) {
	const status = document.getElementById('status');
	const totals = document.getElementById('totals');
	const d09 = summary.groups.find(g => g.id === ROOT_ONLY);
	const onlyD09 = summary.missing.length === 1 && summary.missing[0] === ROOT_ONLY && summary.failed === 0 && !summary.failures.length;
	let state, text;
	if (boot.errors.length || summary.failed || summary.failures.length || mode !== 'baseline') { state = 'fail'; text = 'FAIL'; }
	else if (summary.state === 'pass') { state = 'pass'; text = 'PASS — all 10 groups'; }
	else if (onlyD09) { state = 'incomplete'; text = 'INCOMPLETE — D09 NOT RUN (ROOT ONLY); not a baseline PASS'; }
	else { state = 'fail'; text = 'FAIL — groups not run: ' + summary.missing.join(','); }
	if (mode !== 'baseline') text = `FAIL (fault mode ${mode}${suppress ? ', suppressed' : ''}) — ledger: ` + rows.filter(r => r.state !== 'NOT RUN').map(r => r.state).join(',');
	if (boot.errors.length) text += ' — ' + boot.errors[0];
	status.dataset.state = state;
	status.textContent = text;
	document.title = text.split(' — ')[0] + ' — T05.005 fixture';
	totals.textContent = `executed ${summary.executed} / ${summary.expected} groups · passed ${summary.passed} · failed ${summary.failed} · assertions ${summary.assertions}`;
	const list = document.getElementById('cases');
	list.textContent = '';
	for (const g of summary.groups) {
		const li = document.createElement('li');
		li.dataset.state = g.state;
		const unrun = g.state === 'not run' ? (g.id === ROOT_ONLY ? 'NOT RUN — ROOT ONLY' : 'NOT RUN') : g.state.toUpperCase();
		li.textContent = `${g.id} ${g.name}: ${unrun} (${g.assertions} assertions)` + (g.errors.length ? ' — ' + g.errors.join('; ') : '');
		list.append(li);
	}
	const table = document.getElementById('ledger');
	table.textContent = '';
	for (const row of rows) {
		const tr = document.createElement('tr');
		for (const cell of [row.mode, row.state, row.sink || '—', row.evidence || '—']) { const td = document.createElement('td'); td.textContent = cell; tr.append(td); }
		table.append(tr);
	}
	document.getElementById('errors').textContent = [...boot.errors, ...summary.failures].join('\n');
	document.getElementById('notes').textContent = notes.join('\n');
	window.__t05Result = Object.freeze({ mode, suppress, state, summary, ledger: rows, bootErrors: [...boot.errors], final });
}

async function main() {
	if (mode !== 'baseline' && !FAULT_MODES.includes(mode)) reporter.fail('unknown fault mode: ' + mode);
	render(reporter.summary(), ledger(mode, []), false);
	const order = runFull ? [REGISTRATIONS.find(r => r[0] === ROOT_ONLY), ...REGISTRATIONS.filter(r => r[0] !== ROOT_ONLY)] : REGISTRATIONS;
	for (const [id, body] of order) {
		if (id === ROOT_ONLY && !runFull) continue;
		if (!suppress && mode === 'omitted-group' && id === faultGroup) continue;
		if (!suppress && mode === 'zero-assertions' && id === faultGroup) { await makeGroup(id, async () => {})(); continue; }
		await makeGroup(id, body)();
		render(reporter.summary(), ledger(mode, faults), false);
	}
	await inject();
	const summary = reporter.summary();
	if (mode === 'zero-assertions' || mode === 'omitted-group') {
		const g = summary.groups.find(group => group.id === faultGroup);
		if (g && ((mode === 'zero-assertions' && g.state === 'fail' && g.assertions === 0) || (mode === 'omitted-group' && g.state === 'not run'))) {
			faults.push({ mode, sink: 'reporter-summary', kind: mode === 'zero-assertions' ? 'zero' : 'omitted', group: g.id, groupState: g.state, assertions: g.assertions });
		}
	}
	const rows = ledger(mode, faults);
	for (const row of rows) if (row.state === 'NOT OBSERVED') reporter.fail('fault injection NOT OBSERVED: ' + row.mode);
	if (apiErrors.length && mode !== 'api-error' && mode !== 'cleanup-error') reporter.fail('API double errors: ' + apiErrors.map(e => e.category + ':' + e.message).join('; '));
	if (boot.errors.length && mode === 'baseline') reporter.fail('boot errors present');
	boot.finished = true;
	render(reporter.summary(), rows, true);
}

main().catch(error => { boot.fail('harness: ' + String(error && error.stack || error)); });
'''

STYLE = r'''body { font: 14px/1.45 system-ui, sans-serif; margin: 16px; color: #111; background: #fafafa; }
#status { font-weight: 700; padding: 6px 8px; }
#status[data-state="not-run"] { background: #eee; }
#status[data-state="pass"] { background: #c8f0c8; }
#status[data-state="incomplete"] { background: #fff1b8; }
#status[data-state="fail"] { background: #f6c6c6; }
li[data-state="fail"] { color: #a00; }
li[data-state="not run"] { color: #765; }
table { border-collapse: collapse; }
td, th { border: 1px solid #bbb; padding: 2px 6px; font-size: 12px; vertical-align: top; }
pre { white-space: pre-wrap; font-size: 12px; }
#stage { margin-top: 12px; }
'''


def run_page():
    group_items = ''.join(f'<li>{gid} {name}: NOT RUN</li>' for gid, name in GROUPS)
    # Links resolve against the decoy document base, so name the page itself.
    here = '../' + PAGE
    modes = ' '.join(f'<a href="{here}?fault={m}">{m}</a> (<a href="{here}?fault={m}&amp;suppress=1">suppressed</a>)' for m in MODES)
    return f'''<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="referrer" content="no-referrer">
<meta name="viewport" content="width=device-width, initial-scale=1">
<base href="{PAGE_BASE}">
<title>NOT RUN — T05.005 fixture</title>
<link rel="stylesheet" href="../fixture/style.css">
<script src="../boot.js"></script>
<script type="module" src="../fixture/harness.mjs"></script>
</head>
<body>
<h1>T05.005 dictionary loader fixture</h1>
<p>Detached authored fixture on this loopback origin: native fetch/WebCrypto/TextDecoder/JSON.parse/MutationObserver, the unchanged NPC core, tiny authored dictionaries and labelled doubles. Not the game, a package or staging.</p>
<p id="status" data-state="not-run" data-expected="10">NOT RUN — 10 groups expected (D09 is root only: add ?full=1)</p>
<p id="totals">executed 0 / 10 groups · passed 0 · failed 0 · assertions 0</p>
<ol id="cases">{group_items}</ol>
<p>Fault modes (each must stay FAIL with its ledger row OBSERVED; suppressed must show NOT OBSERVED): <a href="{here}">baseline</a> · <a href="{here}?full=1">baseline + D09 full body</a><br>{modes}</p>
<table><thead><tr><th>mode</th><th>state</th><th>sink</th><th>evidence</th></tr></thead><tbody id="ledger"></tbody></table>
<pre id="errors"></pre>
<pre id="notes"></pre>
<div id="stage"></div>
</body>
</html>
'''


def landing_page():
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="referrer" content="no-referrer">
<title>T05.005 fixture</title>
<link rel="stylesheet" href="fixture/style.css">
</head>
<body>
<h1>T05.005 dictionary loader fixture</h1>
<p><a href="{PAGE}">Run the harness</a> (nested page; its document base is /decoy/).</p>
</body>
</html>
'''


SERVER = r'''#!/usr/bin/env python3
"""T05.005 fixture loopback server (generated; stdlib only).

    python3 -I server.py [PORT]

Binds 127.0.0.1 only and serves this directory's fixed allowlist plus finite
case endpoints. Nothing else on disk is reachable. The root starts, observes
and stops it; workers only generate and syntax-check it.
"""
import gzip
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

ROOT = os.path.dirname(os.path.abspath(__file__))
ALLOW = frozenset(__ALLOW__)
TINY = bytes.fromhex(__TINY__)
CSP = __CSP__
TYPES = {'.html': 'text/html; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8',
         '.js': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8',
         '.css': 'text/css; charset=utf-8'}
JSON_TYPE = 'application/json; charset=utf-8'
STALL_SECONDS = 8


class Handler(BaseHTTPRequestHandler):
    server_version = 'T05Fixture'
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *args):
        sys.stderr.write('%s %s\n' % (self.command, self.path[:200]))

    def head(self, status, ctype, length=None, extra=()):
        self.send_response(status)
        self.send_header('Content-Type', ctype)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', CSP)
        if length is not None:
            self.send_header('Content-Length', str(length))
        for name, value in extra:
            self.send_header(name, value)
        self.end_headers()

    def body(self, data):
        if self.command != 'HEAD':
            self.wfile.write(data)

    def plain(self, status, data, ctype):
        self.head(status, ctype, len(data))
        self.body(data)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = urlsplit(self.path).path
        try:
            if path.startswith('/case/') and path.endswith('/dict.json'):
                return self.case(path[len('/case/'):-len('/dict.json')])
            if path == '/':
                path = '/index.html'
            rel = path[1:]
            if rel not in ALLOW:
                return self.plain(404, b'not found\n', 'text/plain; charset=utf-8')
            full = os.path.join(ROOT, *rel.split('/'))
            ctype = TYPES.get(os.path.splitext(rel)[1], 'application/octet-stream')
            size = os.path.getsize(full)
            self.head(200, ctype, size)
            if self.command == 'HEAD':
                return
            with open(full, 'rb') as handle:
                while True:
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def chunk(self, data):
        self.wfile.write(b'%x\r\n%s\r\n' % (len(data), data))
        self.wfile.flush()

    def case(self, name):
        if name in ('tiny', 'bad-utf8', 'bad-json', 'scalar', 'array', 'null', 'unsafe'):
            rel = 'case/%s/dict.json' % name
            with open(os.path.join(ROOT, *rel.split('/')), 'rb') as handle:
                return self.plain(200, handle.read(), JSON_TYPE)
        if name == 'no-store-plain':
            return self.plain(200, TINY, JSON_TYPE)
        if name == 'delay':
            time.sleep(0.3)
            return self.plain(200, TINY, JSON_TYPE)
        if name == 'wrong-mime':
            return self.plain(200, TINY, 'text/plain; charset=utf-8')
        if name == 'other-charset':
            return self.plain(200, TINY, 'application/json; charset=iso-8859-1')
        if name == 'status-500':
            return self.plain(500, TINY, JSON_TYPE)
        if name == 'redirect':
            self.head(302, 'text/plain; charset=utf-8', 0, [('Location', '/case/tiny/dict.json')])
            return
        if name == 'gzip':
            data = gzip.compress(TINY)
            self.head(200, JSON_TYPE, len(data), [('Content-Encoding', 'gzip')])
            return self.body(data)
        if name == 'chunked':
            self.head(200, JSON_TYPE, None, [('Transfer-Encoding', 'chunked')])
            if self.command == 'HEAD':
                return
            third = max(1, len(TINY) // 3)
            for part in (TINY[:third], TINY[third:2 * third], TINY[2 * third:]):
                self.chunk(part)
                time.sleep(0.05)
            self.wfile.write(b'0\r\n\r\n')
            return
        if name == 'framing-short':
            self.head(200, JSON_TYPE, len(TINY) + 20, [('Connection', 'close')])
            self.body(TINY)
            self.close_connection = True
            return
        if name == 'stall-headers':
            time.sleep(STALL_SECONDS)
            self.close_connection = True
            return
        if name == 'stall-body':
            self.head(200, JSON_TYPE, None, [('Transfer-Encoding', 'chunked')])
            self.chunk(TINY[:4])
            time.sleep(STALL_SECONDS)
            self.close_connection = True
            return
        return self.plain(404, b'not found\n', 'text/plain; charset=utf-8')


def main(argv):
    port = int(argv[0]) if argv else 0
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    print('serving http://127.0.0.1:%d/pages/run/index.html' % server.server_address[1], flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
'''


def groups_js():
    return ',\n'.join(f"\tObject.freeze({{ id: '{gid}', name: {json.dumps(name)} }})" for gid, name in GROUPS)


def write_private(directory, name, data):
    parts = name.split('/')
    current = directory
    for part in parts[:-1]:
        current = os.path.join(current, part)
        if not os.path.lexists(current):
            os.mkdir(current, 0o700)
            os.chmod(current, 0o700)
    path = os.path.join(current, parts[-1])
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
    finally:
        os.close(fd)


def copy_dictionary(source, directory, name):
    """Stream-copy and hash the production body; never decode or parse it."""
    fd, before = open_regular(source, '--dictionary-source')
    try:
        if before.st_size != DICTIONARY_PIN['bytes']:
            raise Refused('--dictionary-source: size differs from the pin')
        digest = hashlib.sha256()
        total = 0
        target = os.path.join(directory, *name.split('/'))
        out = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            os.fchmod(out, 0o600)
            while True:
                chunk = os.read(fd, COPY_CHUNK)
                if not chunk:
                    break
                total += len(chunk)
                if total > DICTIONARY_PIN['bytes']:
                    raise Refused('--dictionary-source: grew past the pin while copying')
                digest.update(chunk)
                view = memoryview(chunk)
                while view:
                    view = view[os.write(out, view):]
        finally:
            os.close(out)
        if identity(os.fstat(fd)) != identity(before):
            raise Refused('--dictionary-source: file changed while copying')
    finally:
        os.close(fd)
    if total != DICTIONARY_PIN['bytes'] or digest.hexdigest() != DICTIONARY_PIN['sha256']:
        raise Refused('--dictionary-source: SHA-256 differs from the pin')
    # Re-hash what landed on disk, independently of the copy loop.
    check = hashlib.sha256()
    copied = 0
    with open(target, 'rb') as handle:
        for block in iter(lambda: handle.read(COPY_CHUNK), b''):
            copied += len(block)
            check.update(block)
    if copied != total or check.hexdigest() != DICTIONARY_PIN['sha256']:
        raise Refused('full/dict.json: copied bytes differ from the pin')
    return {'path': name, 'bytes': copied, 'sha256': check.hexdigest()}


def build(loader_path, core_path, output, dictionary_source=None):
    if os.path.lexists(output):
        raise Refused('OUTPUT: already exists')
    output = checked_path(output, 'OUTPUT', missing_leaf=True)
    loader, loader_mode = read_regular(loader_path, 'LOADER_SOURCE')
    core, core_mode = read_regular(core_path, 'CORE_SOURCE')
    if len(core) != CORE_PIN['bytes'] or sha256(core) != CORE_PIN['sha256']:
        raise Refused('CORE_SOURCE: not the root-qualified core pin')
    try:
        loader_text = loader.decode('utf-8')
        core_text = core.decode('utf-8')
    except UnicodeDecodeError:
        raise Refused('LOADER_SOURCE/CORE_SOURCE: not UTF-8')
    loader_imports, loader_dynamic = imports_of(loader_text)
    core_imports, core_dynamic = imports_of(core_text)
    if loader_imports != [CORE_SPECIFIER] or loader_dynamic:
        raise Refused('LOADER_SOURCE: must statically import only ./npc_plaintext_adapter.mjs')
    if core_imports or core_dynamic:
        raise Refused('CORE_SOURCE: must not import')
    if dictionary_source is not None:
        _fd, info = open_regular(dictionary_source, '--dictionary-source')
        os.close(_fd)
        if info.st_size != DICTIONARY_PIN['bytes']:
            raise Refused('--dictionary-source: size differs from the pin')
    generator = Path(__file__).resolve()
    generator_bytes, _ = read_regular(str(generator), generator.name)

    files = [
        ('index.html', landing_page().encode('utf-8')),
        (PAGE, run_page().encode('utf-8')),
        ('boot.js', BOOT.encode('utf-8')),
        ('fixture/reporter.mjs', REPORTER.replace('__GROUPS__', groups_js()).replace('__MODES__', json.dumps(MODES)).encode('utf-8')),
        ('fixture/doubles.mjs', DOUBLES.encode('utf-8')),
        ('fixture/harness.mjs', HARNESS.encode('utf-8')),
        ('fixture/cases.mjs', cases_js(dictionary_source is not None).encode('utf-8')),
        ('fixture/style.css', STYLE.encode('utf-8')),
        ('loader/' + LOADER_NAME, loader),
        ('loader/' + CORE_NAME, core),
        ('loader/dict.json', TINY),
        # A byte-identical loader whose sibling core is deliberately absent.
        ('broken/' + LOADER_NAME, loader),
        ('decoy/dict.json', DECOY_BASE),
        ('pages/run/dict.json', DECOY_PAGE),
    ]
    files += [(f'case/{name}/dict.json', data) for name, data in STATIC_CASES.items()]
    if dictionary_source is not None:
        files += [('full/' + LOADER_NAME, loader), ('full/' + CORE_NAME, core)]
    allow = sorted([name for name, _ in files if not name.startswith('case/')] + ['provenance.json']
                   + (['full/dict.json'] if dictionary_source is not None else []))
    server = (SERVER.replace('__ALLOW__', json.dumps(allow)).replace('__TINY__', json.dumps(TINY.hex()))
              .replace('__CSP__', json.dumps(CSP)))
    files.append(('server.py', server.encode('utf-8')))

    os.mkdir(output, 0o700)
    created = os.lstat(output)
    try:
        os.chmod(output, 0o700)
        for name, data in files:
            write_private(output, name, data)
        copied = None
        if dictionary_source is not None:
            copied = copy_dictionary(dictionary_source, output, 'full/dict.json')
        listing = []
        for name, data in files:
            mode = stat.S_IMODE(os.lstat(os.path.join(output, *name.split('/'))).st_mode)
            listing.append({'path': name, 'bytes': len(data), 'sha256': sha256(data), 'mode': format(mode, '04o')})
        if copied:
            mode = stat.S_IMODE(os.lstat(os.path.join(output, 'full', 'dict.json')).st_mode)
            listing.append({'path': copied['path'], 'bytes': copied['bytes'], 'sha256': copied['sha256'], 'mode': format(mode, '04o')})
        provenance = {
            'task': 'T05.005',
            'schema': 1,
            'loader': {'name': LOADER_NAME, 'bytes': len(loader), 'sha256': sha256(loader), 'source_mode': format(loader_mode, '04o'),
                       'copies': ['loader/' + LOADER_NAME, 'broken/' + LOADER_NAME] + (['full/' + LOADER_NAME] if copied else [])},
            'core': {'name': CORE_NAME, 'bytes': len(core), 'sha256': sha256(core), 'source_mode': format(core_mode, '04o'),
                     'pin': CORE_PIN, 'copies': ['loader/' + CORE_NAME] + (['full/' + CORE_NAME] if copied else [])},
            'imports': [{'from': 'loader/' + LOADER_NAME, 'specifier': CORE_SPECIFIER, 'resolves': 'loader/' + CORE_NAME}],
            'generator': {'name': generator.name, 'sha256': sha256(generator_bytes)},
            'dictionary': {'expected': DICTIONARY_PIN, 'copied': copied,
                           'note': 'exact-byte detached fixture data; never decoded or parsed by the builder'},
            'csp': CSP,
            'page': PAGE, 'page_base': PAGE_BASE,
            'expected_groups': [gid for gid, _ in GROUPS],
            'root_only_groups': ['D09'],
            'fault_modes': MODES,
            'server_allowlist': allow,
            'special_cases': SPECIAL_CASES,
            'files': listing,
        }
        record = (json.dumps(provenance, indent=2, ensure_ascii=False) + '\n').encode('utf-8')
        write_private(output, 'provenance.json', record)
    except BaseException:
        # Remove only the directory this run created, if it is still that one.
        try:
            now = os.lstat(output)
            if stat.S_ISDIR(now.st_mode) and (now.st_dev, now.st_ino) == (created.st_dev, created.st_ino):
                shutil.rmtree(output)
        except OSError:
            pass
        raise
    return {
        'task': 'T05.005',
        'output': os.path.basename(os.path.normpath(output)),
        'loader_sha256': provenance['loader']['sha256'],
        'core_sha256': provenance['core']['sha256'],
        'generator_sha256': provenance['generator']['sha256'],
        'provenance_sha256': sha256(record),
        'files': len(listing) + 1,
        'full_dictionary': copied is not None,
        'expected_groups': provenance['expected_groups'],
        'fault_modes': MODES,
    }


def main(argv):
    args = list(argv)
    dictionary = None
    if '--dictionary-source' in args:
        index = args.index('--dictionary-source')
        if index + 1 >= len(args):
            print('usage: --dictionary-source needs a PATH', file=sys.stderr)
            return 2
        dictionary = args[index + 1]
        del args[index:index + 2]
    if len(args) != 3 or any(a.startswith('--') for a in args):
        print('usage: dictionary_loader_fixture.py LOADER_SOURCE CORE_SOURCE OUTPUT [--dictionary-source PATH]', file=sys.stderr)
        return 2
    try:
        summary = build(args[0], args[1], args[2], dictionary)
    except Refused as error:
        print(f'refused: {error}', file=sys.stderr)
        return 1
    except OSError as error:
        print(f'refused: {error.strerror or error.__class__.__name__}', file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
