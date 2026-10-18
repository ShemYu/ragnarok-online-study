#!/usr/bin/env python3
"""T05.004: build the detached native-DOM fixture for the NPC plain-text core.

    python3 -I tools/renewal/npc_plaintext_fixture.py ADAPTER_SOURCE OUTPUT

ADAPTER_SOURCE is the authored npc_plaintext_adapter.mjs (read as a regular,
non-linked file of at most 1 MiB). It is copied beside entirely authored
modules: a client API 1 double, native-shape NpcBox/NpcMenu/InputBox
stand-ins, a tiny authored dictionary, an aggregate reporter, a 13-group
browser harness with six ?mode= reporter faults and an interactive demo. The
page's CSP allows only its own scripts and styles. OUTPUT must not exist; it
is created 0700 with 0600 files and a provenance record of every byte.

No stock component, client, plugin or dictionary content is read or written.
This only writes files. It never opens a browser or listens on a port;
serving and viewing the page is the root's step (see NPC_PLAINTEXT_ADAPTER.md).
"""
import hashlib
import json
import os
import shutil
import stat
import sys
from pathlib import Path

READ_LIMIT = 1024 * 1024
ADAPTER_AS = 'npc_plaintext_adapter.js'
EXPECTED_GROUPS = 13
MODES = ['api-append-error', 'api-replay-error', 'api-cleanup-error', 'zero-assertions',
         'unhandled-rejection', 'csp-inline']
CSP = '; '.join([
    "default-src 'none'", "script-src 'self'", "style-src 'self'", "img-src 'none'",
    "font-src 'none'", "connect-src 'none'", "media-src 'none'", "object-src 'none'",
    "frame-src 'none'", "child-src 'none'", "worker-src 'none'", "manifest-src 'none'",
    "base-uri 'none'", "form-action 'none'",
])


class Refused(Exception):
    pass


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def checked_path(path, what, missing_leaf=False):
    """Reject linked components without resolving them away before checking."""
    absolute = Path(path)
    if not absolute.is_absolute():
        absolute = Path.cwd() / absolute
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


def read_regular(path, what):
    """A regular file, read in chunks that never exceed READ_LIMIT + 1 bytes."""
    path = checked_path(path, what)
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode):
        raise Refused(f'{what}: not a regular file')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NONBLOCK', 0))
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or (before.st_dev, before.st_ino) != (info.st_dev, info.st_ino):
            raise Refused(f'{what}: regular file identity changed')
        if before.st_size > READ_LIMIT:
            raise Refused(f'{what}: size exceeds read limit')
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
        identity = lambda value: (value.st_dev, value.st_ino, value.st_size,
                                  value.st_mtime_ns, value.st_ctime_ns)
        if identity(before) != identity(after) or total != before.st_size:
            raise Refused(f'{what}: file changed while reading')
        return b''.join(chunks)
    finally:
        os.close(fd)


# --- authored fixture files ---------------------------------------------------

# Authored entries only. Bad* values are deliberately unsupported mappings.
DICTIONARY = {
    'Hello': '哈囉',
    'Goodbye': '再會',
    'Welcome to Prontera.': '歡迎光臨普隆德拉。',
    'Next line': '下一行',
    'Prontera 普隆德拉 gate': '普隆德拉城門',
    'Yes': '是',
    'No': '否',
    'Buy': '購買：道具',
    'Sell': '賣出: 物品',
    'Next': '下一步',
    'Close': '關上',
    'OK': '確定',
    'Cancel': '取消選擇',
    'Input number': '輸入數字',
    '0007': '七',
    'Ancient': '古代𠀋文字',
    'Quote "&" test': '引號「&」測試 "ok"',
    'Punct': '「哈囉」，『再會』！？：；…',
    'Amp': '&amp; &lt;b&gt; A & B',
    'A': 'B',
    'B': 'C',
    'Click': '點擊',
    ' ': '空白',
    '': '空',
    '__proto__': '原型',
    '^00FF00Hello': '綠色',
    'Bad number': 42,
    'Bad null': None,
    'Bad object': {},
    'Bad empty': '',
    'Bad space': ' 　 ',
    'Bad CR': 'a\rb',
    'Bad LF': 'a\nb',
    'Bad colour': '^ff0000紅',
    'Bad angle': '<b>粗</b>',
    'Bad placeholder': '{0} 個',
    'Bad replacement': '壞�',
    'Bad surrogate': '\ud800x',
}
# Long targets are built at parse time so the module stays small.
REPEATED = {'Edge target': ('字', 8192), 'Long target': ('字', 8193), 'Half target': ('字', 4096)}


def dictionary_js():
    # ASCII-only JSON text inside a JS string literal: parsed fresh per call.
    text = json.dumps(DICTIONARY, ensure_ascii=True, separators=(',', ':'))
    repeated = ''.join(f'\tdictionary[{json.dumps(key)}] = {json.dumps(unit)}.repeat({count});\n'
                       for key, (unit, count) in REPEATED.items())
    return ('// Authored tiny dictionary for the fixture: no real dictionary content.\n'
            '// Parsed from JSON text on every call, so each core gets a plain object.\n'
            f'const SOURCE = {json.dumps(text)};\n'
            'export function createDictionary() {\n'
            '\tconst dictionary = JSON.parse(SOURCE);\n'
            f'{repeated}'
            '\treturn dictionary;\n'
            '}\n'
            f'export const ENTRY_COUNT = {len(DICTIONARY) + len(REPEATED)};\n')


BOOT = r'''// Classic script, runs before the module graph: records load, CSP and
// runtime errors so none of them can end in PASS.
(function () {
	'use strict';
	var boot = { errors: [], finished: false };
	window.__t05Boot = boot;
	function show() {
		var status = document.getElementById('status');
		if (status) { status.dataset.state = 'fail'; status.textContent = 'FAIL — ' + boot.errors[0] + (boot.errors.length > 1 ? ' (+' + (boot.errors.length - 1) + ' more)' : ''); }
		var errors = document.getElementById('errors');
		if (errors) errors.textContent = boot.errors.join('\n');
		document.title = 'FAIL — T05.004 fixture';
	}
	boot.fail = function (text) { boot.errors.push(String(text)); show(); };
	window.addEventListener('error', function (event) {
		var target = event.target;
		if (target && target !== window && target.tagName) boot.fail('load error: ' + target.tagName.toLowerCase() + ' ' + (target.src || target.href || ''));
		else boot.fail('error: ' + (event.message || event.error));
	}, true);
	window.addEventListener('unhandledrejection', function (event) {
		var reason = event.reason;
		boot.fail('unhandled rejection: ' + (reason && reason.message ? reason.message : String(reason)));
	});
	document.addEventListener('securitypolicyviolation', function (event) {
		boot.fail('CSP violation: ' + event.effectiveDirective + ' ' + event.blockedURI);
	});
	setTimeout(function () { if (!boot.finished) boot.fail('watchdog: harness did not complete within 30 s'); }, 30000);
})();
'''

REPORTER = r'''// Authored aggregate reporter. PASS only when every expected group ran
// exactly once with at least one assertion and no errors, no unexpected
// group ran, and no failure was ever recorded. A failure is never cleared.
// This literal manifest is independent of harness registrations, including G13.
export const BASELINE_GROUPS = Object.freeze([
	'G1 Plain dialogue before/after append; duplicate append and replay',
	'G2 Multiline hit/miss, mixed CJK, CRLF/CR/LF and whitespace',
	'G3 Adjacent Text never joins; own keys only',
	'G4 Native-shape menu: omitted options, indexes, mousedown, OK/double-click, cancel 255',
	'G5 Next/Close and unrelated controls keep identity, values and one action',
	'G6 InputBox excluded: exact text, parseInt|0 number, value untouched',
	'G7 Whole-row skips: colours, ITEM/NAVI, comments, controls, editable',
	'G8 Unsafe/nonstring/oversized mappings; scalar punctuation; HTML-like targets',
	'G9 Dictionary readiness: pending, late, rejected, malformed, removed and disposed',
	'G10 Lifecycle: queued current-registry replay, early removal, loader adoption, reappend, mismatches',
	'G11 Native MutationObserver: changes, replacement, output-as-key, queued callbacks, stale content',
	'G12 Component/row negatives, every numeric bound and diagnostics',
	'G13 Reporter controls and aggregate accounting',
]);
export function createReporter(expected) {
	const want = Object.freeze([...expected]);
	const results = new Map();
	const failures = [];
	return {
		expected: want,
		record(name, assertions, errors) {
			if (results.has(name)) failures.push('group ran twice: ' + name);
			results.set(name, { assertions, errors: [...errors] });
		},
		fail(text) { failures.push(String(text)); },
		summary() {
			let executed = 0, passed = 0, failed = 0, assertions = 0;
			const groups = [];
			for (const name of want) {
				const result = results.get(name);
				if (!result) { groups.push({ name, state: 'not run', assertions: 0, errors: [] }); continue; }
				executed++;
				assertions += result.assertions;
				const ok = result.errors.length === 0 && result.assertions > 0;
				if (ok) passed++; else failed++;
				const errors = result.assertions > 0 ? result.errors : ['zero assertions', ...result.errors];
				groups.push({ name, state: ok ? 'pass' : 'fail', assertions: result.assertions, errors });
			}
			const unexpected = [...results.keys()].filter(name => !want.includes(name));
			const state = want.length > 0 && passed === want.length && !failures.length && !unexpected.length ? 'pass' : 'fail';
			return { state, expected: want.length, executed, passed, failed, assertions, failures: [...failures], unexpected, groups };
		},
	};
}

// A mode label is never evidence that its injection reached the actual sink.
// Missing evidence fails distinctly; it must not be credited as an observed
// API/rejection/CSP/zero-assertion fault by a root verifier.
export function requireObservedFault(reporter, mode, errors) {
	if (mode === 'baseline') return 'not-applicable';
	const messages = {
		'api-append-error': 'API double: injected append listener error',
		'api-replay-error': 'API double: injected replay listener error',
		'api-cleanup-error': 'API double: injected cleanup error',
		'unhandled-rejection': 'unhandled rejection: injected unhandled rejection',
	};
	const observed = mode === 'zero-assertions'
		? reporter.summary().groups.some(group => group.name === 'fault: zero assertions' && group.state === 'fail' && group.assertions === 0)
		: mode === 'csp-inline'
			? errors.some(error => /^CSP violation: script-src(?:-elem)? inline$/.test(error))
			: Object.hasOwn(messages, mode) && errors.includes(messages[mode]);
	if (!observed) reporter.fail('fault injection NOT OBSERVED: ' + mode);
	return observed ? 'observed' : 'not-observed';
}
'''

API_DOUBLE = r'''// Authored client API 1 double: the lifecycle parts the core uses. A fresh
// frozen descriptor per append, microtask replay from the current registry,
// removal emitted before the caller detaches, scoped idempotent cleanup.
// Every listener, replay and cleanup error goes to a visible sink.
export function createRuntime(onError) {
	if (typeof onError !== 'function') throw new TypeError('API double needs a visible error sink');
	const listeners = new Map();
	const components = new Map();
	function report(error) { onError(error); }
	function emit(event, value) {
		for (const listener of [...(listeners.get(event) || [])]) {
			try { listener(value); } catch (error) { report(error); }
		}
	}
	function scope(name = 'npc-plaintext') {
		const cleanups = new Set();
		let disposed = false;
		const cleanup = fn => {
			if (typeof fn !== 'function') throw new TypeError('Cleanup must be a function');
			let done = false;
			const once = () => {
				if (done) return;
				done = true; cleanups.delete(once);
				try { Promise.resolve(fn()).catch(report); } catch (error) { report(error); }
			};
			if (disposed) once(); else cleanups.add(once);
			return once;
		};
		const on = (event, listener, { replay = true } = {}) => {
			if (disposed) throw new Error(`Plugin ${name} is disposed`);
			if (!['ui:append', 'ui:remove'].includes(event) || typeof listener !== 'function') throw new TypeError('Unsupported client event');
			if (!listeners.has(event)) listeners.set(event, new Set());
			listeners.get(event).add(listener);
			const off = cleanup(() => listeners.get(event)?.delete(listener));
			if (replay) queueMicrotask(() => {
				if (disposed || !listeners.get(event)?.has(listener)) return;
				const values = event === 'ui:append' ? [...components.values()] : [];
				for (const value of values) { try { listener(value); } catch (error) { report(error); } }
			});
			return off;
		};
		const api = Object.freeze({ version: 1, name, cleanup, on });
		return { api, dispose() {
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
		// Hand-made descriptors for mismatch and malformed-shape cases.
		emit,
		listenerCount: () => [...listeners.values()].reduce((n, set) => n + set.size, 0),
	};
}
'''

COMPONENTS = r'''// Authored native-shape stand-ins for NpcBox, NpcMenu and InputBox: the DOM
// shapes and callback order of the reviewed client source, written from
// scratch. No stock component, template, stylesheet or engine code.
function make(tag, className, text) {
	const node = document.createElement(tag);
	if (className) node.className = className;
	if (text !== undefined) node.appendChild(document.createTextNode(text));
	return node;
}

function shell(name) {
	const host = make('div', 'component-host');
	host.dataset.component = name;
	const root = host.attachShadow({ mode: 'open' });
	const sheet = document.createElement('link');
	sheet.rel = 'stylesheet';
	sheet.href = 'shadow.css';
	root.appendChild(sheet);
	const container = make('div', 'ui-component-root');
	root.appendChild(container);
	return { host, root, container };
}

// Row parts: a string is one authored Text node (exact data, no HTML parsing);
// objects build the shapes the reviewed renderer makes for colours and links.
export function part(spec) {
	if (typeof spec === 'string') return document.createTextNode(spec);
	if (spec instanceof Node) return spec;
	if (spec.color) { const span = make('span', null, spec.text); span.style.color = spec.color; return span; }
	if (spec.item) { const span = make('span', 'item-link', spec.text); span.dataset.itemId = spec.item; return span; }
	if (spec.navi) { const span = make('span', 'navi-link', spec.text); span.dataset.naviInfo = spec.navi; span.dataset.naviName = spec.text; return span; }
	if (spec.comment) return document.createComment(spec.comment);
	throw new TypeError('unknown row part');
}

// NpcBox: setText appends one direct DIV under .content (clearing first after
// Next/Close); Next/Close each own one listener; links are delegated on root.
export function createNpcBox(name = 'NpcBox') {
	const { host, root, container } = shell(name);
	const content = make('div', 'content');
	const close = make('button', 'btn close', 'Close');
	const next = make('button', 'btn next', 'Next');
	close.type = next.type = 'button';
	close.hidden = next.hidden = true;
	const btns = make('div', 'btns');
	btns.append(close, next);
	const border = make('div', 'border');
	border.append(content, btns);
	const box = make('div', 'npcbox');
	box.appendChild(border);
	container.appendChild(box);
	let needCleanUp = false;
	const component = {
		name, host, root, container, content, next, close, ownerID: 0, log: [], links: [],
		onNextPressed() {}, onClosePressed() {},
	};
	next.addEventListener('click', () => {
		needCleanUp = true;
		next.hidden = true;
		component.log.push(['next', component.ownerID]);
		component.onNextPressed(component.ownerID);
	});
	close.addEventListener('click', () => {
		needCleanUp = true;
		close.hidden = true;
		component.log.push(['close', component.ownerID]);
		component.onClosePressed(component.ownerID);
	});
	content.addEventListener('mousedown', event => event.stopImmediatePropagation());
	root.addEventListener('click', event => {
		const link = event.target.closest && event.target.closest('.item-link, .navi-link');
		if (link) component.links.push(link.dataset.itemId || link.dataset.naviInfo);
	});
	component.setText = (parts, gid) => {
		component.ownerID = gid;
		if (needCleanUp) { needCleanUp = false; content.textContent = ''; }
		const row = document.createElement('div');
		for (const spec of [].concat(parts)) row.appendChild(part(spec));
		content.appendChild(row);
		return row;
	};
	component.addNext = gid => { component.ownerID = gid; next.hidden = false; };
	component.addClose = gid => { component.ownerID = gid; close.hidden = false; };
	component.onRemove = () => {
		next.hidden = close.hidden = true;
		content.textContent = '';
		needCleanUp = false;
		component.ownerID = 0;
	};
	return component;
}

// NpcMenu: split on ':', omit empty options, zero-based data-index; mousedown
// selects with parseInt; OK and double-click submit owner and index + 1;
// cancel submits 255.
export function createNpcMenu(name = 'NpcMenu') {
	const { host, root, container } = shell(name);
	const content = make('div', 'content');
	const middle = make('div', 'middle');
	middle.append(make('span', 'title'), content);
	const cancel = make('button', 'btn cancel', 'Cancel');
	const ok = make('button', 'btn ok', 'OK');
	cancel.type = ok.type = 'button';
	const box = make('div', 'npcmenu');
	box.append(middle, cancel, ok);
	container.appendChild(box);
	let index = 0;
	let owner = 0;
	const component = { name, host, root, container, content, ok, cancel, onSelectMenu() {} };
	const validate = () => component.onSelectMenu(owner, index + 1);
	ok.addEventListener('click', validate);
	cancel.addEventListener('click', () => component.onSelectMenu(owner, 255));
	content.addEventListener('mousedown', event => {
		const row = event.target.closest && event.target.closest('div[data-index]');
		if (row && content.contains(row)) {
			for (const other of content.querySelectorAll('div[data-index]')) other.classList.remove('selected');
			row.classList.add('selected');
			index = parseInt(row.dataset.index, 10);
		}
		event.stopImmediatePropagation();
	});
	content.addEventListener('dblclick', event => {
		const row = event.target.closest && event.target.closest('div[data-index]');
		if (row && content.contains(row)) validate();
	});
	component.setMenu = (menu, gid) => {
		const list = menu.split(':');
		owner = gid;
		index = 0;
		content.textContent = '';
		let j = 0;
		for (const option of list) {
			if (!option.length) continue;
			const row = document.createElement('div');
			row.appendChild(document.createTextNode(option));
			row.dataset.index = j++;
			content.appendChild(row);
		}
		const first = content.querySelector('div[data-index]');
		if (first) first.classList.add('selected');
	};
	component.selected = () => index;
	component.onRemove = () => { content.textContent = ''; };
	return component;
}

// InputBox: never allowlisted by the core. Number mode submits
// parseInt(value, 10) | 0; the input's own value is never rewritten.
export function createInputBox() {
	const { host, root, container } = shell('InputBox');
	const inner = make('div', 'inputbox');
	const border = make('div', 'border');
	const label = make('div', 'text', 'Input number');
	const input = document.createElement('input');
	input.type = 'text';
	const button = make('button', 'ok', 'OK');
	button.type = 'button';
	border.append(label, input, button);
	inner.appendChild(border);
	container.appendChild(inner);
	const component = { name: 'InputBox', host, root, container, label, input, button, onSubmitRequest() {} };
	const validate = () => {
		let text = input.value;
		if (inner.classList.contains('number')) text = parseInt(text, 10) | 0;
		component.onSubmitRequest(text);
	};
	button.addEventListener('click', validate);
	input.addEventListener('keydown', event => { if (event.key === 'Enter') validate(); });
	component.setType = (type, value) => {
		if (type === 'number') { inner.classList.add('number'); label.textContent = 'Input number'; }
		else { inner.classList.remove('number'); label.textContent = ''; }
		if (value !== undefined) input.value = value;
	};
	component.onRemove = () => { input.value = ''; label.textContent = ''; };
	return component;
}

// GUIComponent order: attach the host, then emit a fresh descriptor (every
// append, even when already attached). Removal emits first, then onRemove,
// then detaches.
export function mount(runtime, component, parent) {
	if (component.host.parentNode !== parent) parent.appendChild(component.host);
	return runtime.append(component);
}

export function unmount(runtime, component) {
	runtime.remove(component);
	component.onRemove();
	component.host.remove();
}
'''

HARNESS = r'''// Authored browser harness: the core under the API 1 double with native DOM,
// shadow roots and the browser's own MutationObserver. Thirteen baseline
// groups run automatically; ?mode= adds exactly one authored reporter fault.
import initialize, { LIMITS } from './npc_plaintext_adapter.js';
import { BASELINE_GROUPS, createReporter, requireObservedFault } from './reporter.js';
import { createRuntime } from './api-double.js';
import { createDictionary, ENTRY_COUNT } from './dictionary.js';
import * as C from './components.js';
import { startDemo } from './demo.js';

const boot = window.__t05Boot;
const CSP = __CSP__;
const FAULT_MODES = __MODES__;
const mode = new URLSearchParams(location.search).get('mode') || 'baseline';
const groups = [];
function group(number, name, fn) { groups.push({ number, name: `G${number} ${name}`, fn }); }

const settle = () => new Promise(resolve => setTimeout(resolve, 0));
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const texts = row => Array.from(row.childNodes, node => node.data);
const show = value => { const text = JSON.stringify(value); return text && text.length > 160 ? text.slice(0, 157) + '...' : text; };
const codepoints = text => Array.from(text, ch => 'U+' + ch.codePointAt(0).toString(16).toUpperCase().padStart(4, '0')).join(' ');
const onApiError = error => boot.fail('API double: ' + String(error && error.message || error));

function createAssert() {
	const t = { count: 0, errors: [] };
	t.ok = (condition, message) => { t.count++; if (!condition) t.errors.push(message); };
	t.equal = (actual, expected, message) => t.ok(Object.is(actual, expected), `${message}: got ${show(actual)}, expected ${show(expected)}`);
	t.same = (actual, expected, message) => t.ok(JSON.stringify(actual) === JSON.stringify(expected), `${message}: got ${show(actual)}, expected ${show(expected)}`);
	return t;
}

// A second native observer on the same content: counts what the core wrote.
function spy(target) {
	const seen = { childList: 0, characterData: 0 };
	const observer = new MutationObserver(records => { for (const record of records) seen[record.type]++; });
	observer.observe(target, { childList: true, characterData: true, subtree: true });
	return { seen, stop: () => observer.disconnect() };
}

function environment(area) {
	const scopes = [];
	const env = {
		area,
		runtime: createRuntime(onApiError),
		newRuntime: () => createRuntime(onApiError),
		// PluginLoader shape: initialize synchronously, adopt dispose later.
		load(dictionaryReady, runtime = env.runtime, name = 'npc-plaintext') {
			const scope = runtime.scope(name);
			scopes.push(scope);
			const core = initialize({ dictionaryReady }, scope.api);
			const adopted = Promise.resolve(core).then(result => {
				if (typeof result?.dispose === 'function') scope.api.cleanup(() => result.dispose());
			});
			return { scope, core, adopted };
		},
		cleanup() { for (const scope of scopes) scope.dispose(); },
	};
	return env;
}

group(1, 'Plain dialogue before/after append; duplicate append and replay', async (t, env) => {
	const box = C.createNpcBox();
	const first = box.setText('Hello', 1);
	C.mount(env.runtime, box, env.area);
	const { core } = env.load(createDictionary());
	t.same(texts(first), ['Hello'], 'replay is queued, not synchronous');
	await settle();
	t.same(texts(first), ['哈囉'], 'queued replay translates preexisting text');
	const node = first.firstChild;
	const watch = spy(box.content);
	C.mount(env.runtime, box, env.area); // the engine appends before every setText
	const second = box.setText('Welcome to Prontera.', 1);
	t.same(texts(second), ['Welcome to Prontera.'], 'setText lands after append');
	await settle();
	t.same(texts(second), ['歡迎光臨普隆德拉。'], 'native observer translates rows added after append');
	t.equal(first.firstChild, node, 'Text node identity kept');
	t.equal(watch.seen.characterData, 1, 'exactly one write for the new row');
	C.mount(env.runtime, box, env.area);
	C.mount(env.runtime, box, env.area);
	await settle();
	await settle();
	t.equal(watch.seen.characterData, 1, 'duplicate appends write nothing');
	t.same([texts(first), texts(second)], [['哈囉'], ['歡迎光臨普隆德拉。']], 'texts unchanged by duplicates');
	t.equal(core.diagnostics().activeRoots, 1, 'one ownership for the root');
	t.equal(core.diagnostics().state, 'ready', 'state ready');
	watch.stop();
});

group(2, 'Multiline hit/miss, mixed CJK, CRLF/CR/LF and whitespace', async (t, env) => {
	const box = C.createNpcBox();
	C.mount(env.runtime, box, env.area);
	env.load(createDictionary());
	const cases = [
		['Hello\nUnknown line\r\nGoodbye', '哈囉\nUnknown line\r\n再會'],
		['Hello\rGoodbye\r\n\n', '哈囉\r再會\r\n\n'],
		['Hello\n \n\t\nGoodbye\n', '哈囉\n \n\t\n再會\n'],
		['Ancient\r\nNext line', '古代𠀋文字\r\n下一行'],
		[' Hello', ' Hello'], ['Hello ', 'Hello '], ['hello', 'hello'], ['Hello ', 'Hello '],
		['Prontera 普隆德拉 gate', '普隆德拉城門'], ['Prontera 普隆德拉', 'Prontera 普隆德拉'], ['哈囉', '哈囉'],
		[' ', ' '], ['', ''], ['\r\n', '\r\n'],
	];
	const rows = cases.map(([source]) => box.setText(source, 1));
	const nodes = rows.map(row => row.firstChild);
	await settle();
	cases.forEach(([source, expected], i) => {
		t.same(texts(rows[i]), [expected], `row ${i} ${show(source)}`);
		t.equal(rows[i].firstChild, nodes[i], `row ${i} same node`);
	});
	t.equal(codepoints(rows[3].firstChild.data), codepoints('古代𠀋文字\r\n下一行'), 'non-BMP and CRLF code points exact');
});

group(3, 'Adjacent Text never joins; own keys only', async (t, env) => {
	const box = C.createNpcBox();
	C.mount(env.runtime, box, env.area);
	env.load(createDictionary());
	const joined = box.setText(['Hel', 'lo', 'Goodbye'], 1);
	const split = box.setText(['Good', 'bye'], 1);
	const inherited = ['toString', 'constructor', 'hasOwnProperty', 'valueOf', 'isPrototypeOf'].map(key => box.setText(key, 1));
	const own = box.setText('__proto__', 1);
	await settle();
	t.same(texts(joined), ['Hel', 'lo', '再會'], 'adjacent Texts evaluated separately');
	t.same(texts(split), ['Good', 'bye'], 'no joined key match');
	t.same(inherited.map(row => row.textContent), ['toString', 'constructor', 'hasOwnProperty', 'valueOf', 'isPrototypeOf'], 'inherited names unchanged');
	t.same(texts(own), ['原型'], 'own JSON __proto__ key matches');

	const nullRuntime = env.newRuntime();
	const nullBox = C.createNpcBox();
	C.mount(nullRuntime, nullBox, env.area);
	const nullDict = Object.assign(Object.create(null), createDictionary());
	const { core: nullCore } = env.load(nullDict, nullRuntime);
	const nullRow = nullBox.setText('Hello', 1);
	await settle();
	t.equal(nullCore.diagnostics().state, 'ready', 'null-prototype dictionary accepted');
	t.same(texts(nullRow), ['哈囉'], 'null-prototype hit');

	const derivedRuntime = env.newRuntime();
	const derivedBox = C.createNpcBox();
	C.mount(derivedRuntime, derivedBox, env.area);
	const { core: derivedCore } = env.load(Object.create(createDictionary()), derivedRuntime);
	const derivedRow = derivedBox.setText('Hello', 1);
	await settle();
	t.equal(derivedCore.diagnostics().state, 'failed', 'inheriting container is not plain JSON');
	t.same(texts(derivedRow), ['Hello'], 'no inherited-key translation');
});

group(4, 'Native-shape menu: omitted options, indexes, mousedown, OK/double-click, cancel 255', async (t, env) => {
	const menu = C.createNpcMenu();
	const submitted = [];
	menu.onSelectMenu = (owner, index) => submitted.push([owner, index]);
	C.mount(env.runtime, menu, env.area);
	env.load(createDictionary());
	menu.setMenu('Yes::Buy:Unknown:Sell:', 4242);
	const rows = Array.from(menu.content.children);
	const nodes = rows.map(row => row.firstChild);
	await settle();
	t.same(rows.map(row => row.dataset.index), ['0', '1', '2', '3'], 'empty options omitted, zero-based indexes');
	t.same(rows.map(row => row.textContent), ['是', '購買：道具', 'Unknown', '賣出: 物品'], 'hits translated, miss kept');
	t.ok(rows.every((row, i) => row.firstChild === nodes[i] && row.childNodes.length === 1), 'same Text nodes');
	t.equal(menu.content.children.length, 4, 'translated colons are not reparsed');
	t.ok(rows[0].classList.contains('selected'), 'first row selected natively');
	rows[3].dispatchEvent(new MouseEvent('mousedown', { bubbles: true, composed: true }));
	t.ok(rows[3].classList.contains('selected') && !rows[0].classList.contains('selected'), 'native mousedown selection');
	t.equal(menu.selected(), 3, 'parseInt of original data-index');
	menu.ok.click();
	rows[1].dispatchEvent(new MouseEvent('mousedown', { bubbles: true, composed: true }));
	rows[1].dispatchEvent(new MouseEvent('dblclick', { bubbles: true, composed: true }));
	menu.cancel.click();
	t.same(submitted, [[4242, 4], [4242, 2], [4242, 255]], 'owner with index+1, double-click, cancel 255');
	t.same(rows.map(row => row.dataset.index), ['0', '1', '2', '3'], 'indexes unchanged after interaction');
	t.equal(menu.ok.textContent + menu.cancel.textContent, 'OKCancel', 'menu buttons untouched');
});

group(5, 'Next/Close and unrelated controls keep identity, values and one action', async (t, env) => {
	const box = C.createNpcBox();
	C.mount(env.runtime, box, env.area);
	env.load(createDictionary());
	const outside = document.createElement('input');
	outside.value = 'Hello';
	env.area.appendChild(outside);
	const field = document.createElement('input');
	field.value = 'Hello';
	const inner = document.createElement('button');
	inner.type = 'button';
	inner.textContent = 'Next';
	let innerClicks = 0;
	inner.addEventListener('click', () => innerClicks++);
	const controlRow = box.setText(['Click', field, inner], 9);
	const row = box.setText('Hello', 9);
	box.addNext(9);
	box.addClose(9);
	const nextNode = box.next.firstChild;
	const closeNode = box.close.firstChild;
	await settle();
	t.same(texts(row), ['哈囉'], 'plain row translates');
	t.equal(controlRow.firstChild.data, 'Click', 'row holding controls skipped whole');
	t.equal(field.value, 'Hello', 'row input value kept');
	t.equal(inner.textContent, 'Next', 'row button label kept');
	t.equal(outside.value, 'Hello', 'unrelated input kept');
	t.equal(box.next.firstChild, nextNode, 'Next label node identity');
	t.equal(box.close.firstChild, closeNode, 'Close label node identity');
	t.same([box.next.textContent, box.close.textContent], ['Next', 'Close'], 'Next/Close labels untouched');
	box.next.click();
	box.close.click();
	inner.click();
	t.same(box.log, [['next', 9], ['close', 9]], 'one local action per button');
	t.equal(innerClicks, 1, 'row control listener ran once');
});

group(6, 'InputBox excluded: exact text, parseInt|0 number, value untouched', async (t, env) => {
	const input = C.createInputBox();
	const submitted = [];
	input.onSubmitRequest = value => submitted.push(value);
	C.mount(env.runtime, input, env.area);
	const { core } = env.load(createDictionary());
	input.setType('number', '0007');
	await settle();
	t.equal(input.label.textContent, 'Input number', 'InputBox label not translated');
	input.button.click();
	t.equal(input.input.value, '0007', 'number mode leaves input.value exact');
	input.setType('text', '0007');
	input.button.click();
	input.setType('text', '哈囉𠀋「」');
	input.button.click();
	input.setType('number', '12abc');
	input.button.click();
	input.setType('number', '99999999999');
	input.button.click();
	t.same(submitted.slice(0, 2), [7, '0007'], 'number 7 versus string "0007"');
	t.equal(typeof submitted[0], 'number', 'number mode submits a number');
	t.equal(codepoints(submitted[2]), codepoints('哈囉𠀋「」'), 'Chinese and non-BMP submit exactly');
	t.same(submitted.slice(3), [12, 99999999999 | 0], 'parseInt(value, 10) | 0');
	t.equal(input.input.value, '99999999999', 'input value never rewritten');
	t.equal(core.diagnostics().activeRoots, 0, 'InputBox not owned');
});

group(7, 'Whole-row skips: colours, ITEM/NAVI, comments, controls, editable', async (t, env) => {
	const box = C.createNpcBox();
	C.mount(env.runtime, box, env.area);
	env.load(createDictionary());
	const rows = [
		box.setText(['Hello', { color: '#ff0000', text: 'Goodbye' }], 1),
		box.setText(['Hello ', { item: '501', text: 'Hello' }], 1),
		box.setText([{ navi: 'prontera,150,150', text: 'Hello' }], 1),
		box.setText(['Hello', { comment: 'x' }], 1),
	];
	const editable = box.setText('Hello', 1);
	editable.setAttribute('contenteditable', 'false');
	const plain = box.setText('Goodbye', 1);
	await settle();
	t.same(rows.map(row => row.textContent), ['HelloGoodbye', 'Hello Hello', 'Hello', 'Hello'], 'unsupported rows untouched');
	t.equal(rows[0].lastChild.style.color, 'rgb(255, 0, 0)', 'colour span kept');
	t.equal(rows[1].lastChild.dataset.itemId, '501', 'ITEM metadata kept');
	t.equal(rows[2].firstChild.dataset.naviInfo, 'prontera,150,150', 'NAVI metadata kept');
	t.equal(editable.textContent, 'Hello', 'any contenteditable attribute excludes');
	t.same(texts(plain), ['再會'], 'independent safe sibling translates');
	rows[1].lastChild.click();
	rows[2].firstChild.click();
	t.same(box.links, ['501', 'prontera,150,150'], 'link listeners still work once each');

	const box2 = C.createNpcBox();
	box2.container.setAttribute('contenteditable', 'true');
	C.mount(env.runtime, box2, env.area);
	const blocked = box2.setText('Hello', 1);
	await settle();
	t.ok(blocked.isContentEditable, 'native isContentEditable via ancestor');
	t.same(texts(blocked), ['Hello'], 'editable ancestor up to the root excludes');
	box2.container.removeAttribute('contenteditable');

	// Descriptor.root may itself be an Element, not just a ShadowRoot. Its
	// attribute presence excludes even contenteditable="false".
	for (const value of ['false', '']) {
		const root = document.createElement('div');
		root.setAttribute('contenteditable', value);
		const content = document.createElement('div');
		content.className = 'content';
		const row = document.createElement('div');
		const text = document.createTextNode('Hello');
		row.appendChild(text); content.appendChild(row); root.appendChild(content);
		env.area.appendChild(root);
		const component = { name: 'NpcBox', root, host: root };
		env.runtime.append(component);
		await settle();
		t.equal(text.data, 'Hello', `Element root attribute ${show(value)} blocks initial scan`);
		text.data = 'Goodbye';
		await settle();
		t.equal(text.data, 'Goodbye', 'Element root mark blocks native observer writes');
		t.equal(row.firstChild, text, 'editable Text identity preserved');
		root.removeAttribute('contenteditable');
		env.runtime.append(component);
		await settle();
		t.equal(text.data, '再會', 'fresh append works after editable mark removed');
		env.runtime.remove(component); root.remove();
	}
});

group(8, 'Unsafe/nonstring/oversized mappings; scalar punctuation; HTML-like targets', async (t, env) => {
	const box = C.createNpcBox();
	C.mount(env.runtime, box, env.area);
	env.load(createDictionary());
	const bad = ['Bad number', 'Bad null', 'Bad object', 'Bad empty', 'Bad space', 'Bad CR', 'Bad LF', 'Bad colour',
		'Bad angle', 'Bad placeholder', 'Bad replacement', 'Bad surrogate', 'Long target', '^00FF00Hello', 'Missing key'];
	const rows = bad.map(key => box.setText(`${key}\nHello`, 1));
	const edge = box.setText('Edge target', 1);
	const good = box.setText('Punct\nQuote "&" test\nAncient\nAmp', 1);
	await settle();
	bad.forEach((key, i) => t.same(texts(rows[i]), [`${key}\n哈囉`], `${key}: only the good line translates`));
	t.equal(edge.firstChild.data.length, LIMITS.textUnits, 'target at the 8192 limit');
	t.equal(good.firstChild.data, '「哈囉」，『再會』！？：；…\n引號「&」測試 "ok"\n古代𠀋文字\n&amp; &lt;b&gt; A & B', 'punctuation, quotes, ampersands, non-BMP');
	t.ok([...rows, edge, good].every(row => row.children.length === 0 && row.childNodes.length === 1), 'no elements created');
	t.equal(good.firstChild.data.includes('<'), false, 'no angle bracket written');
});

group(9, 'Dictionary readiness: pending, late, rejected, malformed, removed and disposed', async (t, env) => {
	// Pending, then foreign text before readiness.
	let resolve;
	const box = C.createNpcBox();
	C.mount(env.runtime, box, env.area);
	const { core } = env.load(new Promise(r => { resolve = r; }));
	t.equal(core.diagnostics().state, 'loading', 'pending promise is loading');
	const row = box.setText('Hello', 1);
	await settle();
	t.same(texts(row), ['Hello'], 'no writes while loading');
	row.firstChild.data = 'Goodbye';
	resolve(createDictionary());
	await settle();
	t.equal(core.diagnostics().state, 'ready', 'ready after resolve');
	t.same(texts(row), ['再會'], 'fresh foreign text translated at readiness');
	const later = box.setText('Hello', 1);
	await settle();
	t.same(texts(later), ['哈囉'], 'observer active after readiness');

	// Rejected, resolved malformed, synchronous malformed and thenables.
	const outcomes = [];
	for (const [label, make] of [
		['rejected', () => Promise.reject(new Error('authored load failure'))],
		['resolved array', () => Promise.resolve([])],
		['resolved string', () => Promise.resolve('dictionary')],
		['sync null', () => null], ['sync string', () => 'x'], ['sync array', () => []],
		['thenable', () => ({ then(fn) { fn(createDictionary()); } })],
	]) {
		const rt = env.newRuntime();
		const b = C.createNpcBox();
		C.mount(rt, b, env.area);
		const loaded = env.load(make(), rt);
		const r = b.setText('Hello', 1);
		await settle();
		outcomes.push([label, loaded.core.diagnostics().state, r.firstChild.data, rt.listenerCount()]);
	}
	outcomes.forEach(([label, state, data, listeners]) => {
		t.equal(state, 'failed', `${label} fails`);
		t.equal(data, 'Hello', `${label} writes nothing`);
		t.equal(listeners, 0, `${label} keeps no subscriptions`);
	});

	// Removed before readiness, while still connected.
	let resolveRemoved;
	const rtRemoved = env.newRuntime();
	const removed = C.createNpcBox();
	const removedCore = env.load(new Promise(r => { resolveRemoved = r; }), rtRemoved).core;
	C.mount(rtRemoved, removed, env.area); // owned while loading
	const removedRow = removed.setText('Hello', 1);
	t.equal(removedCore.diagnostics().activeRoots, 1, 'owned while loading');
	rtRemoved.remove(removed);
	resolveRemoved(createDictionary());
	await settle();
	t.ok(removed.host.isConnected, 'removed host still connected');
	t.same(texts(removedRow), ['Hello'], 'removed before readiness stays untouched');
	t.equal(removedCore.diagnostics().activeRoots, 0, 'released');

	// Disposed before a late resolve or a late rejection.
	for (const late of ['resolve', 'reject']) {
		const hooks = {};
		const rt = env.newRuntime();
		const b = C.createNpcBox();
		C.mount(rt, b, env.area);
		const loaded = env.load(new Promise((res, rej) => Object.assign(hooks, { res, rej })), rt);
		const r = b.setText('Hello', 1);
		loaded.core.dispose();
		if (late === 'resolve') hooks.res(createDictionary()); else hooks.rej(new Error('authored late failure'));
		await settle();
		b.setText('Goodbye', 1);
		await settle();
		t.equal(loaded.core.diagnostics().state, 'disposed', `disposed stays terminal after late ${late}`);
		t.same([r.textContent, b.content.lastChild.textContent], ['Hello', 'Goodbye'], `no writes after late ${late}`);
	}
	// Cleanup can run synchronously during initialize for an already-dead API
	// scope. It must still consume a late rejection without subscribing.
	for (const late of ['resolve', 'reject']) {
		const rt = env.newRuntime();
		const scope = rt.scope('already-disposed');
		scope.dispose();
		let resolve, reject, subscriptions = 0;
		const dictionaryReady = new Promise((res, rej) => { resolve = res; reject = rej; });
		const api = { ...scope.api, on(...args) { subscriptions++; return scope.api.on(...args); } };
		const disposed = initialize({ dictionaryReady }, api);
		if (late === 'resolve') resolve(createDictionary()); else reject(new Error('authored immediate-cleanup late rejection'));
		await settle(); await settle();
		t.equal(disposed.diagnostics().state, 'disposed', `immediate cleanup stays terminal after ${late}`);
		t.equal(disposed.diagnostics().activeRoots, 0, 'immediately disposed roots released');
		t.equal(subscriptions, 0, 'no subscription attempted after synchronous disposal');
		disposed.dispose();
	}

	// A readiness trigger may retire replaced loading content, but only a fresh
	// matching append may adopt the replacement.
	let resolveReplacement;
	const rtReplacement = env.newRuntime();
	const loading = env.load(new Promise(resolve => { resolveReplacement = resolve; }), rtReplacement).core;
	const replaced = C.createNpcBox();
	C.mount(rtReplacement, replaced, env.area);
	const oldRow = replaced.setText('Hello', 1);
	await settle(); await settle(); // finish registry replay while still loading
	const replacement = document.createElement('div');
	replacement.className = 'content';
	const replacementRow = document.createElement('div');
	const replacementText = document.createTextNode('Goodbye');
	replacementRow.appendChild(replacementText); replacement.appendChild(replacementRow);
	replaced.content.parentNode.replaceChild(replacement, replaced.content);
	resolveReplacement(createDictionary());
	await settle(); await settle();
	t.equal(loading.diagnostics().state, 'ready', 'dictionary ready with replaced loading content');
	t.equal(oldRow.firstChild.data, 'Hello', 'retired loading content remains untouched');
	t.equal(replacementText.data, 'Goodbye', 'readiness alone does not adopt replacement');
	rtReplacement.append(replaced);
	await settle();
	t.equal(replacementText.data, '再會', 'fresh append adopts replacement after readiness');
	t.equal(oldRow.firstChild.data, 'Hello', 'old loading content stays inert after fresh adoption');
	// Any unhandled rejection above would reach the boot reporter and fail the page.
	await pause(50);
	t.equal(boot.errors.length, 0, 'no unhandled rejection or error so far');
});

group(10, 'Lifecycle: queued current-registry replay, early removal, loader adoption, reappend, mismatches', async (t, env) => {
	const before = C.createNpcBox();
	const gone = C.createNpcBox();
	before.setText('Hello', 1);
	gone.setText('Hello', 1);
	C.mount(env.runtime, before, env.area);
	C.mount(env.runtime, gone, env.area);
	const { core } = env.load(createDictionary());
	const immediate = C.createNpcMenu();
	C.mount(env.runtime, immediate, env.area); // live append before the replay microtask
	immediate.setMenu('Yes:No', 2);
	C.unmount(env.runtime, gone); // removed before replay runs
	const late = C.createNpcBox();
	C.mount(env.runtime, late, env.area); // in the registry when replay reads it
	late.setText('Goodbye', 3);
	await settle();
	t.equal(before.content.textContent, '哈囉', 'replayed preexisting component');
	t.equal(gone.content.textContent, '', 'removed before replay: nothing written, native clear');
	t.same(Array.from(immediate.content.children, r => r.textContent), ['是', '否'], 'immediate append translated once');
	t.equal(late.content.textContent, '再會', 'current registry read at replay time');
	t.equal(core.diagnostics().activeRoots, 3, 'three owned roots');

	// Scope cleanup before the loader adopts the returned handle.
	const rt = env.newRuntime();
	const early = C.createNpcBox();
	C.mount(rt, early, env.area);
	const loaded = env.load(createDictionary(), rt);
	loaded.scope.dispose();
	await loaded.adopted;
	await settle();
	early.setText('Hello', 1);
	await settle();
	t.equal(early.content.textContent, 'Hello', 'no writes after scope cleanup');
	t.equal(loaded.core.diagnostics().state, 'disposed', 'disposed via scope');
	t.equal(rt.listenerCount(), 0, 'subscriptions released');
	loaded.core.dispose();
	t.equal(loaded.core.diagnostics().state, 'disposed', 'second dispose is harmless');

	// Name/host mismatch on an owned root, then removal while connected.
	const owned = C.createNpcBox();
	const descriptor = C.mount(env.runtime, owned, env.area);
	const first = owned.setText('Hello', 1);
	await settle();
	for (const fake of [
		Object.freeze({ name: 'NpcMenu', root: owned.root, host: owned.host }),
		Object.freeze({ name: 'NpcBox', root: owned.root, host: document.createElement('div') }),
	]) { env.runtime.emit('ui:append', fake); env.runtime.emit('ui:remove', fake); }
	const stillOwned = owned.setText('Yes', 1);
	await settle();
	t.same(texts(stillOwned), ['是'], 'mismatched descriptors neither take over nor release');
	t.ok(Object.isFrozen(descriptor), 'descriptor is frozen');
	env.runtime.remove(owned); // emitted while connected; host and rows stay
	const after = owned.setText('Goodbye', 1);
	await settle();
	t.ok(owned.host.isConnected, 'host still connected after ui:remove');
	t.same(texts(after), ['Goodbye'], 'removed root inert while connected');
	t.same(texts(first), ['哈囉'], 'no blanket restoration');
	C.mount(env.runtime, owned, env.area); // fresh append, new generation
	await settle();
	t.same(texts(after), ['再會'], 'reappend translates current text');
	C.unmount(env.runtime, owned);
	C.mount(env.runtime, owned, env.area); // detach and reappend
	const again = owned.setText('Hello', 1);
	await settle();
	t.same(texts(again), ['哈囉'], 'detach/reappend works');
});

group(11, 'Native MutationObserver: changes, replacement, output-as-key, queued callbacks, stale content', async (t, env) => {
	const box = C.createNpcBox();
	C.mount(env.runtime, box, env.area);
	const { core } = env.load(createDictionary());
	const watch = spy(box.content);
	const row = box.setText('A', 1);
	await settle();
	await settle();
	t.same(texts(row), ['B'], 'output B is not chained through key B');
	const text = row.firstChild;
	text.data = 'Hello';
	await settle();
	t.equal(text.data, '哈囉', 'later foreign English change translated');
	text.data = '自訂文字';
	await settle();
	t.equal(text.data, '自訂文字', 'foreign Chinese kept');
	text.data = 'A';
	await settle();
	t.equal(text.data, 'B', 'distinguishably new value is current input');
	const multi = box.setText('Hello\nGoodbye', 1);
	await settle();
	multi.firstChild.data = '哈囉\nYes';
	await settle();
	t.equal(multi.firstChild.data, '哈囉\n是', 'partial multiline edit re-evaluates the whole Text');
	const replacement = document.createElement('div');
	replacement.textContent = 'Goodbye';
	box.content.replaceChild(replacement, row);
	const span = document.createElement('span');
	span.textContent = 'Hello';
	multi.appendChild(span);
	await settle();
	t.same(texts(replacement), ['再會'], 'replacement row translated');
	t.equal(span.textContent, 'Hello', 'foreign element insertion makes the row unsupported');
	box.content.removeChild(replacement);
	await settle();
	const writes = watch.seen.characterData;
	await settle();
	await settle();
	t.equal(watch.seen.characterData, writes, 'own-write deliveries settle');
	watch.stop();

	// Queued callbacks after remove and after dispose.
	for (const end of ['remove', 'dispose']) {
		const rt = env.newRuntime();
		const b = C.createNpcBox();
		C.mount(rt, b, env.area);
		const loaded = env.load(createDictionary(), rt);
		await settle();
		const r = b.setText('Hello', 1); // record queued for the core's observer
		if (end === 'remove') rt.remove(b); else loaded.core.dispose();
		await settle();
		t.same(texts(r), ['Hello'], `queued callback after ${end} writes nothing`);
	}

	// Stale content: a new first .content is not observed until a fresh append.
	const old = box.content;
	const fresh = document.createElement('div');
	fresh.className = 'content';
	old.before(fresh);
	const oldRow = document.createElement('div');
	oldRow.textContent = 'Hello';
	old.appendChild(oldRow);
	const newRow = document.createElement('div');
	newRow.textContent = 'Hello';
	fresh.appendChild(newRow);
	await settle();
	t.same(texts(oldRow), ['Hello'], 'stale content not written');
	t.same(texts(newRow), ['Hello'], 'new content waits for a fresh append');
	t.ok(core.diagnostics().stale >= 1, 'stale content diagnosed');
	env.runtime.emit('ui:append', Object.freeze({ name: 'NpcBox', root: box.root, host: document.createElement('div') }));
	env.runtime.emit('ui:append', Object.freeze({ name: 'NpcMenu', root: box.root, host: box.host }));
	await settle();
	t.same(texts(newRow), ['Hello'], 'mismatched host/name cannot adopt new content');
	C.mount(env.runtime, box, env.area);
	await settle();
	t.same(texts(newRow), ['哈囉'], 'fresh append adopts new content');
	const oldLater = document.createElement('div');
	oldLater.textContent = 'Hello';
	old.appendChild(oldLater);
	await settle();
	t.same(texts(oldLater), ['Hello'], 'old content stays unobserved');
	fresh.remove();
});

group(12, 'Component/row negatives, every numeric bound and diagnostics', async (t, env) => {
	const { core } = env.load(createDictionary());
	for (const name of ['npcbox', 'NpcBox ', 'NpcMenuV2', 'ChatBox', 'InputBox', '']) {
		const b = C.createNpcBox(name);
		b.setText('Hello', 1);
		C.mount(env.runtime, b, env.area);
		await settle();
		t.equal(b.content.textContent, 'Hello', `component ${show(name)} not allowlisted`);
	}
	const orphan = C.createNpcBox();
	orphan.setText('Hello', 1);
	env.area.appendChild(orphan.host);
	for (const bad of [null, 1, 'NpcBox', { name: 'NpcBox' }, { name: 'NpcBox', root: {}, host: {} },
		{ name: 'NpcBox', root: orphan.root, host: null }, { name: ['NpcBox'], root: orphan.root, host: orphan.host }]) {
		env.runtime.emit('ui:append', bad);
		env.runtime.emit('ui:remove', bad);
	}
	await settle();
	t.equal(orphan.content.textContent, 'Hello', 'malformed descriptors ignored');
	t.equal(core.diagnostics().activeRoots, 0, 'nothing owned yet');

	const menu = C.createNpcMenu();
	C.mount(env.runtime, menu, env.area);
	const unindexed = document.createElement('div');
	unindexed.textContent = 'Yes';
	const para = document.createElement('p');
	para.textContent = 'Yes';
	const nested = document.createElement('div');
	nested.dataset.index = '0';
	nested.appendChild(document.createElement('div')).textContent = 'Yes';
	menu.content.append(unindexed, para, document.createTextNode('Yes'), nested);
	await settle();
	t.equal(unindexed.textContent, 'Yes', 'NpcMenu rows need data-index');
	t.equal(para.textContent, 'Yes', 'only DIV rows');
	t.equal(menu.content.childNodes[2].data, 'Yes', 'bare content Text is not a row');
	t.equal(nested.textContent, 'Yes', 'nested rows not walked');
	C.unmount(env.runtime, menu);

	// Eight roots; the ninth waits for a later append once capacity frees.
	const boxes = Array.from({ length: LIMITS.roots + 1 }, () => C.createNpcBox());
	for (const b of boxes) { C.mount(env.runtime, b, env.area); b.setText('Hello', 1); }
	await settle();
	t.equal(core.diagnostics().activeRoots, LIMITS.roots, '8 active roots');
	t.equal(boxes[LIMITS.roots].content.textContent, 'Hello', 'ninth root untouched');
	C.unmount(env.runtime, boxes[0]);
	await settle();
	t.equal(boxes[LIMITS.roots].content.textContent, 'Hello', 'not adopted without a fresh append');
	C.mount(env.runtime, boxes[LIMITS.roots], env.area);
	await settle();
	t.equal(boxes[LIMITS.roots].content.textContent, '哈囉', 'adopted on a later append');
	for (const b of boxes.slice(1)) C.unmount(env.runtime, b);
	t.equal(core.diagnostics().activeRoots, 0, 'all released');

	// 256 direct content nodes scan; 257+ writes nothing new.
	const wide = C.createNpcBox();
	C.mount(env.runtime, wide, env.area);
	for (let i = 0; i < LIMITS.contentNodes - 1; i++) wide.content.appendChild(document.createComment('pad'));
	const last = wide.setText('Hello', 1);
	await settle();
	t.equal(wide.content.childNodes.length, LIMITS.contentNodes, '256 nodes present');
	t.same(texts(last), ['哈囉'], '256 direct nodes still scan');
	wide.content.appendChild(document.createComment('over'));
	const over = wide.setText('Goodbye', 1);
	await settle();
	t.same(texts(over), ['Goodbye'], 'over 256 nodes: no new writes');
	t.same(texts(last), ['哈囉'], 'earlier translation not undone');
	C.unmount(env.runtime, wide);

	// 32 row children translate; 33 skip the whole row.
	const rows = C.createNpcBox();
	C.mount(env.runtime, rows, env.area);
	const full = rows.setText(Array.from({ length: LIMITS.rowNodes }, () => 'Hello'), 1);
	const tooMany = rows.setText(Array.from({ length: LIMITS.rowNodes + 1 }, () => 'Hello'), 1);
	const lines = n => Array.from({ length: n }, () => 'Hello').join('\n');
	const sized = 'Hello\n' + 'x'.repeat(LIMITS.textUnits - 6);
	const cases = [
		[lines(LIMITS.lines), Array.from({ length: LIMITS.lines }, () => '哈囉').join('\n'), '256 lines translate'],
		[lines(LIMITS.lines + 1), null, '257 lines skip'],
		[Array.from({ length: LIMITS.lines }, () => 'Hello').join('\r\n'), Array.from({ length: LIMITS.lines }, () => '哈囉').join('\r\n'), 'CRLF counts once'],
		[lines(LIMITS.lines) + '\n', null, 'trailing empty line counts'],
		[sized, '哈囉\n' + 'x'.repeat(LIMITS.textUnits - 6), '8192-unit Text translates'],
		[sized + 'x', null, '8193-unit Text skipped before parsing'],
		['Long target\nHello', 'Long target\n哈囉', 'oversized target keeps its line'],
		['Edge target\nHello', null, 'assembled output over 8192 keeps the whole Text'],
		['Half target\nHalf target', null, '4096+1+4096 keeps the whole Text'],
	];
	const caseRows = cases.map(([source]) => rows.setText(source, 1));
	const sibling = rows.setText('Goodbye', 1);
	await settle();
	t.ok(texts(full).every(x => x === '哈囉'), '32 row children translate');
	t.ok(texts(tooMany).every(x => x === 'Hello'), '33 row children skip the row');
	cases.forEach(([source, expected, label], i) => t.equal(caseRows[i].firstChild.data, expected === null ? source : expected, label));
	t.same(texts(sibling), ['再會'], 'independent row continues');

	const snapshot = core.diagnostics();
	t.ok(Object.isFrozen(snapshot), 'diagnostics frozen');
	t.same(Object.keys(snapshot).sort(), ['activeRoots', 'errors', 'hits', 'ignored', 'misses', 'overflow', 'stale', 'state', 'unsupported'], 'diagnostic keys');
	t.ok(Object.entries(snapshot).every(([k, v]) => k === 'state' ? v === 'ready' : Number.isFinite(v) && v >= 0), 'primitive nonnegative counters');
	t.ok(snapshot.overflow >= 5 && snapshot.ignored >= 1, 'overflow and ignored visible');
	t.ok(!JSON.stringify(snapshot).includes('Hello'), 'no raw text');
});

group(13, 'Reporter controls and aggregate accounting', async (t) => {
	const pass = createReporter(['a', 'b']);
	pass.record('a', 2, []); pass.record('b', 1, []);
	t.equal(pass.summary().state, 'pass', 'all groups pass');
	const zero = createReporter(['a', 'b']);
	zero.record('a', 1, []); zero.record('b', 0, []);
	t.equal(zero.summary().state, 'fail', 'zero assertions fail');
	const omitted = createReporter(['a', 'b']);
	omitted.record('a', 1, []);
	t.equal(omitted.summary().state, 'fail', 'omitted group fails');
	const sticky = createReporter(['a']);
	sticky.fail('earlier error'); sticky.record('a', 3, []);
	t.equal(sticky.summary().state, 'fail', 'failure cannot be overwritten by PASS');
	const extra = createReporter(['a']);
	extra.record('a', 1, []); extra.record('z', 1, []);
	t.equal(extra.summary().state, 'fail', 'unexpected group fails');
	const twice = createReporter(['a']);
	twice.record('a', 1, []); twice.record('a', 1, []);
	t.equal(twice.summary().state, 'fail', 'duplicate group fails');
	t.equal(createReporter([]).summary().state, 'fail', 'empty expectation fails');
	const missingLast = createReporter(BASELINE_GROUPS);
	for (const name of BASELINE_GROUPS.slice(0, -1)) missingLast.record(name, 1, []);
	t.equal(missingLast.summary().expected, 13, 'literal baseline denominator independent of registrations');
	t.equal(missingLast.summary().state, 'fail', 'omitting G13 still fails outside its own checks');
	const suppressed = createReporter(['a']);
	suppressed.record('a', 1, []);
	t.equal(requireObservedFault(suppressed, 'csp-inline', []), 'not-observed', 'mode label is not a CSP observation');
	t.ok(suppressed.summary().failures.some(text => text.includes('NOT OBSERVED')), 'missing fault evidence diagnosed separately');
	t.equal(groups.length, 13, 'thirteen baseline groups registered');
	t.same(groups.map(g => g.number), [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13], 'groups in order');
	t.same(FAULT_MODES, ['api-append-error', 'api-replay-error', 'api-cleanup-error', 'zero-assertions', 'unhandled-rejection', 'csp-inline'], 'six fault modes');
	t.equal(document.querySelector('meta[http-equiv="Content-Security-Policy"]').content, CSP, 'CSP meta exact');
	t.ok(typeof boot.fail === 'function' && Array.isArray(boot.errors), 'boot reporter installed');
	t.ok(ENTRY_COUNT > 0 && ENTRY_COUNT < 100, 'tiny authored dictionary');
	t.equal(typeof MutationObserver, 'function', 'native MutationObserver present');
	t.ok(!/MutationObserverDouble/.test(MutationObserver.toString()) && /native code/.test(MutationObserver.toString()), 'observer is the browser native');
});

// --- reporter faults ----------------------------------------------------------

async function injectFault(reporter, area) {
	if (mode === 'baseline') return;
	note(`fault mode ${mode}: this page must stay FAIL`);
	const runtime = createRuntime(onApiError);
	const box = C.createNpcBox();
	switch (mode) {
	case 'api-append-error': {
		C.mount(runtime, box, area);
		const scope = runtime.scope('fault');
		initialize({ dictionaryReady: createDictionary() }, runtime.scope('core').api);
		scope.api.on('ui:append', () => { throw new Error('injected append listener error'); }, { replay: false });
		C.mount(runtime, box, area);
		const row = box.setText('Hello', 1);
		await settle();
		note(`normal callback still ran before the fault: ${row.textContent}`);
		break;
	}
	case 'api-replay-error': {
		C.mount(runtime, box, area);
		runtime.scope('fault').api.on('ui:append', () => { throw new Error('injected replay listener error'); });
		await settle();
		break;
	}
	case 'api-cleanup-error': {
		const scope = runtime.scope('fault');
		scope.api.cleanup(() => { throw new Error('injected cleanup error'); });
		scope.dispose();
		break;
	}
	case 'zero-assertions':
		reporter.record('fault: zero assertions', 0, []);
		break;
	case 'unhandled-rejection':
		Promise.reject(new Error('injected unhandled rejection'));
		break;
	case 'csp-inline': {
		const script = document.createElement('script');
		script.textContent = 'window.__t05InlineRan = true;';
		document.head.appendChild(script);
		break;
	}
	default:
		boot.fail('unknown mode: ' + mode);
	}
	await pause(300);
}

// --- rendering ----------------------------------------------------------------

const statusEl = document.getElementById('status');
const totalsEl = document.getElementById('totals');
const listEl = document.getElementById('cases');
const notesEl = document.getElementById('notes');
const stage = document.getElementById('stage');
function note(text) { notesEl.textContent += text + '\n'; }

function render(reporter, final) {
	const summary = reporter.summary();
	totalsEl.textContent = `mode ${mode} · executed ${summary.executed} / ${summary.expected} groups · passed ${summary.passed} · failed ${summary.failed} · assertions ${summary.assertions}`;
	listEl.textContent = '';
	for (const g of summary.groups) {
		const item = document.createElement('li');
		item.dataset.state = g.state;
		item.textContent = `${g.state.toUpperCase()} — ${g.name} (${g.assertions} assertions)` + (g.errors.length ? '\n  ' + g.errors.join('\n  ') : '');
		listEl.appendChild(item);
	}
	if (boot.errors.length) return; // boot already shows FAIL; never overwrite it
	if (!final) {
		statusEl.dataset.state = 'running';
		statusEl.textContent = `RUNNING — ${summary.executed} / ${summary.expected} groups`;
		return;
	}
	const pass = summary.state === 'pass';
	statusEl.dataset.state = pass ? 'pass' : 'fail';
	const reason = summary.failures[0] || summary.groups.find(g => g.state !== 'pass')?.name || 'aggregate';
	statusEl.textContent = pass
		? `PASS — ${summary.passed} / ${summary.expected} groups, ${summary.assertions} assertions`
		: `FAIL — ${reason}`;
	document.title = (pass ? 'PASS' : 'FAIL') + ' — T05.004 fixture';
}

async function main() {
	const known = mode === 'baseline' || FAULT_MODES.includes(mode);
	const expected = BASELINE_GROUPS.concat(mode === 'zero-assertions' ? ['fault: zero assertions'] : []);
	const reporter = createReporter(expected);
	if (!known) reporter.fail('unknown mode: ' + mode);
	render(reporter, false);
	for (const { name, fn } of groups) {
		const t = createAssert();
		const area = document.createElement('div');
		area.className = 'group-stage';
		stage.appendChild(area);
		const env = environment(area);
		try { await fn(t, env); } catch (error) { t.errors.push('threw: ' + (error && error.stack || error)); }
		try { env.cleanup(); } catch (error) { t.errors.push('cleanup threw: ' + error); }
		area.remove();
		reporter.record(name, t.count, t.errors);
		render(reporter, false);
	}
	const faultArea = document.createElement('div');
	faultArea.className = 'group-stage';
	stage.appendChild(faultArea);
	await injectFault(reporter, faultArea);
	await pause(100);
	const observation = requireObservedFault(reporter, mode, boot.errors);
	statusEl.dataset.fault = observation;
	note(`fault observation ${mode}: ${observation.toUpperCase()}`);
	boot.finished = true;
	render(reporter, true);
	startDemo({ onApiError, note });
}

main().catch(error => boot.fail('harness: ' + (error && error.stack || error)));
'''

DEMO = r'''// Authored interactive demo for the root: the core translating native-shape
// components under the API 1 double. Every count shown is a local callback
// log — nothing here is a packet, IME, storage or network action.
import initialize from './npc_plaintext_adapter.js';
import { createRuntime } from './api-double.js';
import { createDictionary } from './dictionary.js';
import * as C from './components.js';

const SCRIPT = [
	['Hello', 'plain hit'],
	['Welcome to Prontera.\r\nUnknown line\r\nGoodbye', 'CRLF hit/miss/hit'],
	[['Hello ', { color: '#0000ff', text: 'Goodbye' }], 'coloured row (skipped whole)'],
	[['Hello ', { item: '501', text: 'Hello' }], 'ITEM link row (skipped whole)'],
	['Ancient\nPunct', 'non-BMP and punctuation'],
	['A', 'output-as-key: A shows B, never C'],
];

export function startDemo({ onApiError, note }) {
	const area = document.getElementById('demo-stage');
	const logEl = document.getElementById('demo-log');
	const diagEl = document.getElementById('demo-diagnostics');
	const runtime = createRuntime(onApiError);
	const scope = runtime.scope('npc-plaintext-demo');
	const core = initialize({ dictionaryReady: createDictionary() }, scope.api);
	const box = C.createNpcBox();
	const menu = C.createNpcMenu();
	const input = C.createInputBox();
	let line = 0;
	const owner = 110001;
	function log(text) {
		const item = document.createElement('li');
		item.textContent = text;
		logEl.appendChild(item);
	}
	const diagnostics = () => { diagEl.textContent = JSON.stringify(core.diagnostics()); };
	box.onNextPressed = gid => log(`local next callback owner=${gid}`);
	box.onClosePressed = gid => { log(`local close callback owner=${gid}`); C.unmount(runtime, box); };
	menu.onSelectMenu = (gid, index) => {
		log(`local menu callback owner=${gid} index=${index}` + (index === 255 ? ' (cancel)' : ''));
		C.unmount(runtime, menu);
		if (index === 255) C.unmount(runtime, box);
		diagnostics();
	};
	input.onSubmitRequest = value => {
		const kind = typeof value;
		log(`local input callback ${kind} ${JSON.stringify(value)}` + (kind === 'string' ? ` [${Array.from(value, ch => 'U+' + ch.codePointAt(0).toString(16).toUpperCase().padStart(4, '0')).join(' ')}]` : '') + ` · input.value ${JSON.stringify(input.input.value)}`);
		C.unmount(runtime, input);
		diagnostics();
	};
	const actions = {
		say() {
			const [parts, label] = SCRIPT[line++ % SCRIPT.length];
			C.mount(runtime, box, area);
			box.setText(parts, owner);
			log(`setText after append: ${label}`);
		},
		next() { C.mount(runtime, box, area); box.addNext(owner); },
		close() { C.mount(runtime, box, area); box.addClose(owner); },
		menu() { C.mount(runtime, menu, area); menu.setMenu('Yes::Buy:Unknown:Sell:', owner); log('setMenu "Yes::Buy:Unknown:Sell:"'); },
		number() { C.mount(runtime, input, area); input.setType('number', '0007'); log('InputBox number, default "0007"'); },
		text() { C.mount(runtime, input, area); input.setType('text', '哈囉𠀋'); log('InputBox text, default "哈囉𠀋"'); },
		remove() { for (const c of [menu, input, box]) C.unmount(runtime, c); log('removed all (ui:remove then native clear)'); },
	};
	for (const button of document.querySelectorAll('#demo-controls button[data-action]')) {
		button.disabled = false;
		button.addEventListener('click', () => { actions[button.dataset.action](); setTimeout(diagnostics, 0); });
	}
	diagnostics();
	note('interactive demo ready: local callbacks only');
}
'''

STYLE = r'''body { font: 14px/1.4 system-ui, sans-serif; margin: 16px; color: #111; background: #fafafa; }
#status { font-weight: 700; padding: 8px; border: 2px solid #888; }
#status[data-state="pass"] { border-color: #1a7f37; color: #1a7f37; }
#status[data-state="fail"] { border-color: #c62828; color: #c62828; }
#status[data-state="running"] { border-color: #8a6d00; color: #8a6d00; }
#cases li { white-space: pre-wrap; }
#cases li[data-state="fail"], #cases li[data-state="not run"] { color: #c62828; }
#errors { color: #c62828; white-space: pre-wrap; }
#notes { color: #555; white-space: pre-wrap; }
.group-stage { position: absolute; left: -10000px; top: 0; width: 600px; }
#demo { border-top: 1px solid #ccc; margin-top: 16px; padding-top: 8px; }
#demo-controls button { margin: 2px; }
#demo-stage { min-height: 120px; }
#demo-stage .component-host { display: inline-block; vertical-align: top; margin: 4px; }
#demo-log { font-family: ui-monospace, monospace; font-size: 12px; }
#modes a { margin-right: 8px; }
'''

SHADOW = r'''.ui-component-root { font: 13px/1.5 system-ui, sans-serif; border: 1px solid #999; background: #fff; padding: 6px; min-width: 260px; }
.content { white-space: pre-wrap; min-height: 2em; }
.content div[data-index] { cursor: pointer; padding: 1px 4px; }
.content div[data-index].selected { background: #cde; }
.btns, .npcmenu { margin-top: 4px; }
.btn[hidden] { display: none; }
'''


def index_html():
    links = ' '.join(f'<a href="?mode={mode}">{mode}</a>' for mode in MODES)
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="referrer" content="no-referrer">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NOT RUN — T05.004 fixture</title>
<link rel="stylesheet" href="style.css">
<script src="boot.js"></script>
<script type="module" src="harness.js"></script>
</head>
<body>
<h1>T05.004 NPC plain-text core fixture</h1>
<p>Authored detached fixture: native DOM and MutationObserver, authored component stand-ins, API 1 double and a tiny authored dictionary. Not the game, not real packets or IME.</p>
<p id="status" data-state="not-run" data-expected="{EXPECTED_GROUPS}">NOT RUN — {EXPECTED_GROUPS} groups expected</p>
<p id="totals">executed 0 / {EXPECTED_GROUPS} groups · passed 0 · failed 0 · assertions 0</p>
<p id="modes">Fault modes (each must stay FAIL): <a href="?">baseline</a> {links}</p>
<ol id="cases"></ol>
<pre id="errors"></pre>
<pre id="notes"></pre>
<section id="demo">
<h2>Interactive local demo</h2>
<p>Click menu rows, OK, double-click, Cancel (255), Next/Close and the input OK. Logs are local callbacks, not packets.</p>
<p id="demo-controls">
<button type="button" data-action="say" disabled>Say next line</button>
<button type="button" data-action="next" disabled>Show Next</button>
<button type="button" data-action="close" disabled>Show Close</button>
<button type="button" data-action="menu" disabled>Open menu</button>
<button type="button" data-action="number" disabled>Input number</button>
<button type="button" data-action="text" disabled>Input text</button>
<button type="button" data-action="remove" disabled>Remove all</button>
</p>
<div id="demo-stage"></div>
<p>Diagnostics: <code id="demo-diagnostics"></code></p>
<ol id="demo-log"></ol>
</section>
<div id="stage"></div>
</body>
</html>
'''


def write_private(directory, name, data):
    path = os.path.join(directory, name)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
    finally:
        os.close(fd)


def build(adapter_path, output):
    if os.path.lexists(output):
        raise Refused('OUTPUT: already exists')
    output = checked_path(output, 'OUTPUT', missing_leaf=True)
    adapter = read_regular(adapter_path, 'ADAPTER_SOURCE')
    try:
        adapter.decode('utf-8')
    except UnicodeDecodeError:
        raise Refused('ADAPTER_SOURCE: not UTF-8')
    generator = Path(__file__).resolve()
    generator_bytes = read_regular(str(generator), generator.name)
    harness = (HARNESS.replace('__CSP__', json.dumps(CSP))
               .replace('__MODES__', json.dumps(MODES)))
    files = [
        # Served as .js so any static server gives a JavaScript MIME type.
        (ADAPTER_AS, adapter),
        ('boot.js', BOOT.encode('utf-8')),
        ('reporter.js', REPORTER.encode('utf-8')),
        ('api-double.js', API_DOUBLE.encode('utf-8')),
        ('dictionary.js', dictionary_js().encode('utf-8')),
        ('components.js', COMPONENTS.encode('utf-8')),
        ('harness.js', harness.encode('utf-8')),
        ('demo.js', DEMO.encode('utf-8')),
        ('style.css', STYLE.encode('utf-8')),
        ('shadow.css', SHADOW.encode('utf-8')),
        ('index.html', index_html().encode('utf-8')),
    ]
    os.mkdir(output, 0o700)
    try:
        os.chmod(output, 0o700)
        for name, data in files:
            write_private(output, name, data)
        provenance = {
            'task': 'T05.004',
            'schema': 1,
            'adapter': {'name': 'npc_plaintext_adapter.mjs', 'copied_as': ADAPTER_AS,
                        'bytes': len(adapter), 'sha256': sha256(adapter)},
            'generator': {'name': generator.name, 'sha256': sha256(generator_bytes)},
            'authored_only': True,
            'dictionary_entries': len(DICTIONARY) + len(REPEATED),
            'csp': CSP,
            'expected_groups': EXPECTED_GROUPS,
            'fault_modes': MODES,
            'files': [{'name': name, 'bytes': len(data), 'sha256': sha256(data)} for name, data in files],
        }
        record = (json.dumps(provenance, indent=2, ensure_ascii=False) + '\n').encode('utf-8')
        write_private(output, 'provenance.json', record)
    except BaseException:
        shutil.rmtree(output, ignore_errors=True)
        raise
    return {
        'task': 'T05.004',
        'output': os.path.basename(os.path.normpath(output)),
        'adapter_sha256': provenance['adapter']['sha256'],
        'generator_sha256': provenance['generator']['sha256'],
        'provenance_sha256': sha256(record),
        'files': len(files) + 1,
        'expected_groups': EXPECTED_GROUPS,
        'fault_modes': MODES,
    }


def main(argv):
    if len(argv) != 2:
        print('usage: npc_plaintext_fixture.py ADAPTER_SOURCE OUTPUT', file=sys.stderr)
        return 2
    try:
        summary = build(argv[0], argv[1])
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
