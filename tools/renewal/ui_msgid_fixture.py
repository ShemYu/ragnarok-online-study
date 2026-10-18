#!/usr/bin/env python3
"""T05.003: build the detached real-custom-element fixture for the msgid adapter.

    python3 -I tools/renewal/ui_msgid_fixture.py UITEXT_SOURCE OUTPUT

UITEXT_SOURCE must be the exact pinned 796-byte UI/Elements/UIText.js. Its one
DB import is redirected to an authored stub; every other byte, CRLF included,
is kept. The sibling ui_msgid_adapter.mjs is copied beside it with an authored
API 1 double, a browser harness and a page whose CSP allows only its own
scripts. OUTPUT must not exist; it is created 0700 with 0600 files.

This only writes files. It never runs the stock class, opens a browser or
listens on a port; serving and viewing the page is the root's step (see
UI_MSGID_ADAPTER.md).
"""
import hashlib
import json
import os
import shutil
import stat
import sys
from pathlib import Path

SOURCE_BYTES = 796
SOURCE_SHA256 = '8b93dde4d26829fbe5dc9ce18170dbdd7c6f236bd165ec6695556f4564531d8f'
DB_IMPORT = b"import DB from 'DB/DBManager.js';"
STUB_IMPORT = b"import DB from './db-stub.js';"
ADAPTER = 'ui_msgid_adapter.mjs'
EXPECTED_CASES = 25
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


def read_regular(path, what):
    """Bytes of a regular, non-link file, read without following a final link."""
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        raise Refused(f'{what}: not found')
    if stat.S_ISLNK(info.st_mode):
        raise Refused(f'{what}: is a symbolic link')
    if not stat.S_ISREG(info.st_mode):
        raise Refused(f'{what}: not a regular file')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NONBLOCK', 0))
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise Refused(f'{what}: not a regular file')
        chunks = []
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
        return b''.join(chunks)
    finally:
        os.close(fd)


def transform(source):
    if len(source) != SOURCE_BYTES:
        raise Refused(f'UITEXT_SOURCE: size {len(source)}, expected {SOURCE_BYTES}')
    if sha256(source) != SOURCE_SHA256:
        raise Refused('UITEXT_SOURCE: sha256 mismatch')
    if source.count(DB_IMPORT) != 1:
        raise Refused('UITEXT_SOURCE: expected exactly one DB import')
    offset = source.index(DB_IMPORT)
    return source.replace(DB_IMPORT, STUB_IMPORT, 1), offset


# --- authored fixture files ---------------------------------------------------

DB_STUB = r'''// Authored stand-in for DB/DBManager.js: only getMessage, with the same
// missing-id semantics. No tables, storage or network.
export const messages = new Map();
export const calls = [];
export function reset(entries = {}) {
	messages.clear();
	calls.length = 0;
	for (const [id, text] of Object.entries(entries)) messages.set(String(id), text);
}
export default {
	getMessage(id, defaultText) {
		calls.push(String(id));
		if (!messages.has(String(id))) return defaultText !== undefined ? defaultText : 'NO MSG ' + id;
		return messages.get(String(id));
	},
};
'''

API_DOUBLE = r'''// Authored client API 1 double: the lifecycle parts the adapter uses.
// Fresh frozen descriptor per append, microtask replay from the current
// registry, removal emitted before detachment, scoped idempotent cleanup.
export function createRuntime() {
	const listeners = new Map();
	const components = new Map();
	const reports = [];
	function emit(event, value) {
		for (const listener of [...(listeners.get(event) || [])]) {
			try { listener(value); } catch (error) { reports.push(error); }
		}
	}
	function scope(name = 'ui-msgid') {
		const cleanups = new Set();
		let disposed = false;
		const cleanup = fn => {
			if (typeof fn !== 'function') throw new TypeError('Cleanup must be a function');
			let done = false;
			const once = () => {
				if (done) return;
				done = true; cleanups.delete(once);
				try { fn(); } catch (error) { reports.push(error); }
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
				for (const value of values) { try { listener(value); } catch (error) { reports.push(error); } }
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
		scope, reports,
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
'''

BOOT = r'''// Classic script, runs before the module graph: records load, CSP and
// runtime errors so none of them can end in PASS.
(function () {
	'use strict';
	var boot = { errors: [], notes: [], finished: false };
	window.__t05Boot = boot;
	function fail(text) {
		boot.errors.push(text);
		var status = document.getElementById('status');
		if (status) { status.dataset.state = 'fail'; status.textContent = 'FAIL — ' + text; }
		var errors = document.getElementById('errors');
		if (errors) errors.textContent = boot.errors.join('\n');
	}
	boot.fail = fail;
	window.addEventListener('error', function (event) {
		var target = event.target;
		if (target && target !== window && target.tagName) fail('load error: ' + target.tagName.toLowerCase() + ' ' + (target.src || target.href || ''));
		else fail('error: ' + (event.message || event.error));
	}, true);
	window.addEventListener('unhandledrejection', function (event) { fail('unhandled rejection: ' + event.reason); });
	document.addEventListener('securitypolicyviolation', function (event) {
		var text = 'CSP violation: ' + event.effectiveDirective + ' ' + event.blockedURI;
		// The browser's own favicon request is blocked by img-src 'none' too;
		// it is shown, not hidden, and every other violation fails the page.
		if (event.effectiveDirective === 'img-src' && /^https?:\/\/[^/]+\/favicon\.ico$/.test(event.blockedURI)) {
			boot.notes.push(text + ' (browser favicon request, blocked; not fixture code)');
			var notes = document.getElementById('notes');
			if (notes) notes.textContent = boot.notes.join('\n');
			return;
		}
		fail(text);
	});
	setTimeout(function () { if (!boot.finished) fail('harness did not complete within 20 s'); }, 20000);
})();
'''

HARNESS = r'''// Authored harness: the pinned UIText class (DB import redirected to the
// stub) registered normally, the adapter under the API 1 double, and tiny
// authored markup in the two template shapes. Local stubs only.
import UIText from './UIText.js';
import DB, { reset, calls } from './db-stub.js';
import { createRuntime } from './api-double.js';
import initialize, { createMsgidAdapter } from './ui_msgid_adapter.js';

const boot = window.__t05Boot;
const statusEl = document.getElementById('status');
const totalsEl = document.getElementById('totals');
const listEl = document.getElementById('cases');
const stage = document.getElementById('stage');
const expected = Number(statusEl.dataset.expected);
const cases = [];
const test = (id, fn) => cases.push({ id, fn });
const flush = () => new Promise(resolve => setTimeout(resolve, 0));

const SKILL_ZH = '技能樹';
const QUEST_ZH = '任務視窗：「進行中」，完成！…𠀋';
const SKILL_ESCAPED = '技能樹';
const QUEST_ESCAPED = '任務視窗：「進行中」，完成！…\u{2000b}';
const TABLE = { 283: SKILL_ZH, 1317: QUEST_ZH };

const SKILL_MARKUP = '<div class="titlebar"><button type="button" class="base">b</button>' +
	'<ui-text class="text" msgid="283">Skill Tree</ui-text></div>' +
	'<input type="checkbox" class="view_skill_info"><input type="text" class="note" value="abc">';
const QUEST_MARKUP = '<div class="titlebar"><ui-text class="title" msgid="1317"></ui-text></div>';

// Mirrors the client's prepare/append: markup parsed into a shadow root,
// connected once (upgrade + connectedCallback), detached, then mounted.
function makeComponent(name, markup) {
	const host = document.createElement('div');
	const root = host.attachShadow({ mode: 'open' });
	const container = document.createElement('div');
	root.appendChild(container);
	container.innerHTML = markup;
	stage.appendChild(host);
	host.remove();
	return { name, host, root, mount() { stage.appendChild(host); }, unmount() { host.remove(); } };
}
const slotOf = comp => comp.root.querySelector('ui-text');

function setup(entries = TABLE) {
	reset(entries);
	const runtime = createRuntime();
	const scope = runtime.scope();
	return { runtime, scope };
}

function checker() {
	const t = { count: 0 };
	t.ok = (value, message) => { t.count++; if (!value) throw new Error(message || 'expected truthy'); };
	t.equal = (actual, wanted, message) => {
		t.count++;
		if (!Object.is(actual, wanted)) throw new Error(`${message || 'equal'}: got ${JSON.stringify(actual)}, expected ${JSON.stringify(wanted)}`);
	};
	t.same = (actual, wanted, message) => {
		t.count++;
		if (actual.length !== wanted.length || actual.some((v, i) => v !== wanted[i])) throw new Error(`${message || 'same'}: differs`);
	};
	return t;
}

test('real class registered and upgraded', async t => {
	setup();
	t.equal(customElements.get('ui-text'), UIText, 'registered class');
	const comp = makeComponent('SkillListV2', SKILL_MARKUP);
	const slot = slotOf(comp);
	t.ok(slot instanceof UIText, 'upgraded instance');
	t.equal(slot._initialized, true, 'connectedCallback ran');
	t.same(calls, [], 'msgid alone performs no lookup');
});

test('connectedCallback reads an existing msg', async t => {
	setup();
	const comp = makeComponent('Other', '<ui-text msg="283">x</ui-text>');
	t.equal(slotOf(comp).textContent, SKILL_ZH, 'lookup on connect');
	t.same(calls, ['283'], 'one lookup');
});

test('SkillListV2/283 reacts through attributeChangedCallback', async t => {
	const { runtime, scope } = setup();
	createMsgidAdapter(scope.api);
	const comp = makeComponent('SkillListV2', SKILL_MARKUP);
	comp.mount();
	runtime.append(comp);
	const slot = slotOf(comp);
	t.equal(slot.getAttribute('msg'), '283', 'msg set');
	t.equal(slot.getAttribute('msgid'), '283', 'msgid kept');
	t.same(calls, ['283'], 'real reaction looked up 283');
	t.equal(slot.textContent, SKILL_ZH, 'Chinese text');
	runtime.remove(comp);
	t.equal(slot.textContent, 'Skill Tree', 'fallback restored');
	scope.dispose();
});

test('QuestV1/1317 empty slot', async t => {
	const { runtime, scope } = setup();
	createMsgidAdapter(scope.api);
	const comp = makeComponent('QuestV1', QUEST_MARKUP);
	comp.mount();
	runtime.append(comp);
	const slot = slotOf(comp);
	t.equal(slot.getAttribute('msg'), '1317', 'msg set');
	t.equal(slot.textContent, QUEST_ZH, 'Chinese punctuation text');
	runtime.remove(comp);
	t.equal(slot.childNodes.length, 0, 'empty again');
	t.equal(slot.hasAttribute('msg'), false, 'msg removed');
	scope.dispose();
});

test('UTF-8 decoding, punctuation and non-BMP sentinel', async t => {
	const { runtime, scope } = setup();
	createMsgidAdapter(scope.api);
	const a = makeComponent('SkillListV2', SKILL_MARKUP);
	const b = makeComponent('QuestV1', QUEST_MARKUP);
	a.mount(); b.mount();
	runtime.append(a); runtime.append(b);
	t.equal(slotOf(a).textContent, SKILL_ESCAPED, 'UTF-8 module text equals escapes');
	const text = slotOf(b).textContent;
	t.equal(text, QUEST_ESCAPED, 'punctuation equals escapes');
	t.equal([...text].length, text.length - 1, 'exactly one surrogate pair');
	t.equal(text.codePointAt(text.length - 2), 0x2000b, 'non-BMP sentinel intact');
	scope.dispose();
});

for (const [label, entries] of [['missing', {}], ['empty', { 283: '' }]]) {
	test(`${label} message keeps fallback`, async t => {
		const { runtime, scope } = setup(entries);
		const adapter = createMsgidAdapter(scope.api);
		const comp = makeComponent('SkillListV2', SKILL_MARKUP);
		const slot = slotOf(comp);
		const original = slot.firstChild;
		comp.mount(); runtime.append(comp);
		t.equal(slot.getAttribute('msg'), '283', 'msg set');
		t.same(calls, ['283'], 'lookup attempted');
		t.equal(slot.firstChild, original, 'fallback node untouched');
		t.equal(slot.textContent, 'Skill Tree', 'fallback text');
		t.equal(adapter.tracked(), 1, 'owned');
		runtime.remove(comp);
		t.equal(slot.hasAttribute('msg'), false, 'released');
		scope.dispose();
	});
}

for (const msg of ['999', '']) {
	test(`existing msg ${JSON.stringify(msg)} wins`, async t => {
		const { runtime, scope } = setup({ ...TABLE, 999: 'Theirs' });
		createMsgidAdapter(scope.api);
		const comp = makeComponent('SkillListV2', `<ui-text msgid="283" msg="${msg}">Kept</ui-text>`);
		const slot = slotOf(comp);
		const before = slot.textContent;
		calls.length = 0;
		comp.mount(); runtime.append(comp); await flush();
		t.equal(slot.getAttribute('msg'), msg, 'msg unchanged');
		t.equal(slot.textContent, before, 'text unchanged');
		t.same(calls, [], 'no lookup');
		runtime.remove(comp);
		t.equal(slot.getAttribute('msg'), msg, 'not removed');
		scope.dispose();
	});
}

test('empty, malformed and other ids unchanged', async t => {
	const { runtime, scope } = setup({ ...TABLE, '0283': 'z', 284: 'w' });
	const adapter = createMsgidAdapter(scope.api);
	for (const msgid of ['', ' 283', '283 ', '0283', '283.0', '２８３', '1317', '284']) {
		const comp = makeComponent('SkillListV2', `<ui-text msgid="${msgid}">F</ui-text>`);
		comp.mount(); runtime.append(comp);
		t.equal(slotOf(comp).hasAttribute('msg'), false, JSON.stringify(msgid));
		t.equal(slotOf(comp).textContent, 'F', 'fallback');
	}
	const bare = makeComponent('SkillListV2', '<ui-text>F</ui-text>');
	bare.mount(); runtime.append(bare);
	t.equal(slotOf(bare).hasAttribute('msg'), false, 'no msgid');
	await flush();
	t.same(calls, [], 'no lookups');
	t.equal(adapter.tracked(), 0, 'nothing owned');
	scope.dispose();
});

test('components outside the allowlist ignored', async t => {
	const { runtime, scope } = setup();
	createMsgidAdapter(scope.api);
	for (const name of ['SkillList', 'Quest', 'skilllistv2', 'QuestV1 ', '__proto__', 'constructor']) {
		const comp = makeComponent(name, SKILL_MARKUP);
		comp.mount(); runtime.append(comp);
		t.equal(slotOf(comp).hasAttribute('msg'), false, name);
	}
	const crossed = makeComponent('QuestV1', SKILL_MARKUP);
	crossed.mount(); runtime.append(crossed);
	t.equal(slotOf(crossed).hasAttribute('msg'), false, 'QuestV1 does not take 283');
	await flush();
	t.same(calls, [], 'no lookups');
	t.equal(runtime.reports.length, 0, 'no listener errors');
	scope.dispose();
});

test('slot with element child skipped', async t => {
	const { runtime, scope } = setup();
	createMsgidAdapter(scope.api);
	const comp = makeComponent('SkillListV2', '<ui-text msgid="283"><b>keep</b></ui-text>');
	const child = slotOf(comp).firstChild;
	comp.mount(); runtime.append(comp);
	t.equal(slotOf(comp).hasAttribute('msg'), false, 'not eligible');
	t.equal(slotOf(comp).firstChild, child, 'child identity');
	scope.dispose();
});

test('immediate append plus queued replay is idempotent', async t => {
	const { runtime, scope } = setup();
	const adapter = createMsgidAdapter(scope.api);
	const comp = makeComponent('SkillListV2', SKILL_MARKUP);
	comp.mount(); runtime.append(comp);
	t.same(calls, ['283'], 'immediate');
	await flush();
	runtime.append(comp);
	await flush();
	t.same(calls, ['283'], 'no repeat after replay or re-append');
	t.equal(adapter.tracked(), 1, 'one slot');
	scope.dispose();
});

test('replay delivers components mounted before init', async t => {
	const { runtime, scope } = setup();
	const a = makeComponent('SkillListV2', SKILL_MARKUP);
	const b = makeComponent('QuestV1', QUEST_MARKUP);
	a.mount(); b.mount(); runtime.append(a); runtime.append(b);
	createMsgidAdapter(scope.api);
	t.equal(slotOf(a).hasAttribute('msg'), false, 'not before replay');
	await flush();
	t.equal(slotOf(a).textContent, SKILL_ZH, 'SkillListV2 replayed');
	t.equal(slotOf(b).textContent, QUEST_ZH, 'QuestV1 replayed');
	scope.dispose();
	t.equal(slotOf(a).textContent, 'Skill Tree', 'restored on dispose');
});

test('removal before queued replay', async t => {
	const { runtime, scope } = setup();
	const adapter = createMsgidAdapter(scope.api);
	const comp = makeComponent('SkillListV2', SKILL_MARKUP);
	comp.mount(); runtime.append(comp);
	t.equal(comp.host.isConnected, true, 'connected at removal');
	runtime.remove(comp);
	comp.unmount();
	await flush();
	t.equal(slotOf(comp).hasAttribute('msg'), false, 'not re-applied');
	t.equal(slotOf(comp).textContent, 'Skill Tree', 'fallback');
	t.equal(adapter.tracked(), 0, 'released');
	scope.dispose();
});

test('disposal before queued replay', async t => {
	const { runtime, scope } = setup();
	const comp = makeComponent('SkillListV2', SKILL_MARKUP);
	comp.mount(); runtime.append(comp);
	initialize(null, scope.api);
	scope.dispose();
	await flush();
	t.equal(slotOf(comp).hasAttribute('msg'), false, 'nothing applied');
	t.same(calls, [], 'no lookup');
	t.equal(runtime.listenerCount(), 0, 'unsubscribed');
});

test('detach and reappend with fresh descriptors', async t => {
	const { runtime, scope } = setup();
	const adapter = createMsgidAdapter(scope.api);
	const comp = makeComponent('SkillListV2', SKILL_MARKUP);
	comp.mount();
	const first = runtime.append(comp);
	runtime.remove(comp); comp.unmount();
	comp.mount();
	const second = runtime.append(comp);
	t.ok(first !== second && first.root === second.root, 'fresh descriptor, same root');
	runtime.append(comp);
	await flush();
	t.equal(slotOf(comp).textContent, SKILL_ZH, 're-applied');
	t.same(calls, ['283', '283'], 'once per mount');
	t.equal(adapter.tracked(), 1, 'one slot');
	scope.dispose();
	t.equal(slotOf(comp).textContent, 'Skill Tree', 'restored');
});

test('descriptors sharing one root released separately', async t => {
	const { runtime, scope } = setup();
	const adapter = createMsgidAdapter(scope.api);
	const comp = makeComponent('SkillListV2', SKILL_MARKUP + QUEST_MARKUP);
	const [skill, quest] = comp.root.querySelectorAll('ui-text');
	comp.mount();
	const other = { name: 'QuestV1', root: comp.root, host: comp.host };
	runtime.append(comp); runtime.append(other);
	t.equal(adapter.tracked(), 2, 'two slots');
	runtime.remove(other);
	t.equal(quest.hasAttribute('msg'), false, 'QuestV1 released');
	t.equal(skill.getAttribute('msg'), '283', 'SkillListV2 kept');
	runtime.remove(comp);
	t.equal(skill.hasAttribute('msg'), false, 'SkillListV2 released');
	scope.dispose();
});

function foreign(label, change, check) {
	test(`foreign ${label} preserved`, async t => {
		const { runtime, scope } = setup({ ...TABLE, 1318: 'Other' });
		createMsgidAdapter(scope.api);
		const comp = makeComponent('SkillListV2', SKILL_MARKUP);
		const slot = slotOf(comp);
		comp.mount(); runtime.append(comp);
		change(slot);
		const nodes = [...slot.childNodes];
		runtime.remove(comp);
		t.same([...slot.childNodes], nodes, 'children kept');
		check(t, slot);
		scope.dispose();
	});
}
foreign('msg', slot => slot.setAttribute('msg', '1318'), (t, slot) => {
	t.equal(slot.getAttribute('msg'), '1318', 'foreign msg kept');
	t.equal(slot.textContent, 'Other', 'real reaction text kept');
});
foreign('text', slot => { slot.textContent = 'Theirs'; }, (t, slot) => {
	t.equal(slot.hasAttribute('msg'), false, 'own msg removed');
	t.equal(slot.textContent, 'Theirs', 'foreign text kept');
});
foreign('child', slot => slot.appendChild(document.createElement('i')), (t, slot) => {
	t.ok(slot.lastChild.localName === 'i', 'foreign child kept');
});
foreign('msgid', slot => slot.setAttribute('msgid', '284'), (t, slot) => {
	t.equal(slot.getAttribute('msgid'), '284', 'foreign msgid kept');
	t.equal(slot.textContent, SKILL_ZH, 'text not restored under a new msgid');
});

test('unrelated controls keep identity, value and listeners', async t => {
	const { runtime, scope } = setup();
	createMsgidAdapter(scope.api);
	const comp = makeComponent('SkillListV2', SKILL_MARKUP);
	const root = comp.root;
	const button = root.querySelector('button');
	const checkbox = root.querySelector('.view_skill_info');
	const note = root.querySelector('.note');
	const counts = { click: 0, change: 0, input: 0 };
	button.addEventListener('click', () => counts.click++);
	checkbox.addEventListener('change', () => counts.change++);
	note.addEventListener('input', () => counts.input++);
	comp.mount();
	checkbox.click();
	note.value = 'typed';
	runtime.append(comp); await flush();
	runtime.remove(comp);
	runtime.append(comp);
	scope.dispose();
	t.equal(root.querySelector('button'), button, 'button identity');
	t.equal(root.querySelector('.view_skill_info'), checkbox, 'checkbox identity');
	t.equal(root.querySelector('.note'), note, 'input identity');
	t.equal(checkbox.checked, true, 'checkbox value');
	t.equal(note.value, 'typed', 'input value');
	button.click(); checkbox.click();
	note.dispatchEvent(new Event('input'));
	t.equal(counts.click, 1, 'one click listener');
	t.equal(counts.change, 2, 'one change listener');
	t.equal(counts.input, 1, 'one input listener');
	t.equal(button.getAttribute('type'), 'button', 'attributes kept');
});

test('cleanup twice; nothing after disposal', async t => {
	const { runtime, scope } = setup();
	const adapter = createMsgidAdapter(scope.api);
	const comp = makeComponent('SkillListV2', SKILL_MARKUP);
	comp.mount(); runtime.append(comp);
	adapter.dispose(); adapter.dispose(); scope.dispose(); scope.dispose();
	t.equal(runtime.listenerCount(), 0, 'no listeners');
	t.equal(slotOf(comp).hasAttribute('msg'), false, 'restored');
	const late = makeComponent('QuestV1', QUEST_MARKUP);
	late.mount(); runtime.append(late); await flush();
	t.equal(slotOf(late).hasAttribute('msg'), false, 'no work after disposal');
	t.same(calls, ['283'], 'single lookup overall');
});

test('API version gate', async t => {
	const runtime = createRuntime();
	let threw = 0;
	for (const api of [undefined, {}, { version: 2 }, { version: '1' }]) {
		try { initialize(null, api); } catch { threw++; }
	}
	t.equal(threw, 4, 'all refused');
	t.equal(runtime.listenerCount(), 0, 'nothing subscribed');
});

function render() {
	const done = cases.filter(c => c.result);
	const passed = done.filter(c => c.result === 'PASS').length;
	const assertions = done.reduce((n, c) => n + (c.count || 0), 0);
	totalsEl.textContent = `executed ${done.length} / ${expected} · passed ${passed} · failed ${done.length - passed} · assertions ${assertions}`;
	return { done: done.length, passed, assertions };
}

async function run() {
	if (!boot.errors.length) {
		statusEl.dataset.state = 'running';
		statusEl.textContent = `RUNNING — ${expected} cases expected`;
	}
	if (cases.length !== expected) boot.fail(`defined ${cases.length} cases, page expects ${expected}`);
	for (const c of cases) {
		const li = document.createElement('li');
		li.dataset.case = c.id;
		li.dataset.result = 'NOT RUN';
		li.textContent = `NOT RUN ${c.id}`;
		listEl.appendChild(li);
		const t = checker();
		const errorsBefore = boot.errors.length;
		try {
			await Promise.race([c.fn(t), new Promise((_, reject) => setTimeout(() => reject(new Error('case timed out')), 3000))]);
			await flush();
			if (t.count === 0) throw new Error('no assertions executed');
			if (boot.errors.length !== errorsBefore) throw new Error('page error during case');
			c.result = 'PASS';
		} catch (error) {
			c.result = 'FAIL';
			c.error = String(error && error.message || error);
		}
		c.count = t.count;
		stage.replaceChildren();
		li.dataset.result = c.result;
		li.textContent = `${c.result} ${c.id} (${t.count} assertions)${c.error ? ' — ' + c.error : ''}`;
		render();
	}
	const { done, passed, assertions } = render();
	const ok = boot.errors.length === 0 && cases.length === expected && done === expected && passed === expected && assertions > 0;
	boot.finished = true;
	if (ok) {
		statusEl.dataset.state = 'pass';
		statusEl.textContent = `PASS — ${passed}/${expected} cases, ${assertions} assertions`;
	} else {
		boot.fail(`${passed}/${expected} cases passed, ${done} executed, ${assertions} assertions`);
	}
	document.title = `${statusEl.dataset.state.toUpperCase()} — T05.003 fixture`;
}

run().catch(error => boot.fail('harness: ' + error));
'''

STYLE = '''body { font: 14px/1.4 system-ui, sans-serif; margin: 16px; background: #fff; color: #111; }
#status { font-weight: bold; font-size: 18px; }
#status[data-state="pass"] { color: #0a6b2b; }
#status[data-state="fail"] { color: #b00020; }
li[data-result="FAIL"] { color: #b00020; font-weight: bold; }
#errors { color: #b00020; white-space: pre-wrap; }
#stage { position: absolute; left: -10000px; top: 0; }
'''


def index_html():
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="referrer" content="no-referrer">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NOT RUN — T05.003 fixture</title>
<link rel="stylesheet" href="style.css">
<script src="boot.js"></script>
<script type="module" src="harness.js"></script>
</head>
<body>
<h1>T05.003 ui-text msgid fixture</h1>
<p id="status" data-state="not-run" data-expected="{EXPECTED_CASES}">NOT RUN — {EXPECTED_CASES} cases expected</p>
<p id="totals">executed 0 / {EXPECTED_CASES} · passed 0 · failed 0 · assertions 0</p>
<ol id="cases"></ol>
<pre id="errors"></pre>
<pre id="notes"></pre>
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


def build(source_path, output):
    if os.path.lexists(output):
        raise Refused('OUTPUT: already exists')
    parent = os.path.dirname(os.path.abspath(output))
    if os.path.islink(parent) or not os.path.isdir(parent):
        raise Refused('OUTPUT: parent must be an existing, non-link directory')
    source = read_regular(source_path, 'UITEXT_SOURCE')
    transformed, offset = transform(source)
    generator = Path(__file__).resolve()
    adapter = read_regular(str(generator.with_name(ADAPTER)), ADAPTER)
    os.mkdir(output, 0o700)
    try:
        os.chmod(output, 0o700)
        files = [
            ('UIText.js', transformed),
            ('db-stub.js', DB_STUB.encode('utf-8')),
            ('api-double.js', API_DOUBLE.encode('utf-8')),
            # Served as .js so any static server gives a JavaScript MIME type.
            ('ui_msgid_adapter.js', adapter),
            ('boot.js', BOOT.encode('utf-8')),
            ('harness.js', HARNESS.encode('utf-8')),
            ('style.css', STYLE.encode('utf-8')),
            ('index.html', index_html().encode('utf-8')),
        ]
        for name, data in files:
            write_private(output, name, data)
        provenance = {
            'task': 'T05.003',
            'schema': 1,
            'source': {'name': 'UI/Elements/UIText.js', 'bytes': len(source), 'sha256': sha256(source)},
            'transformed': {
                'name': 'UIText.js', 'bytes': len(transformed), 'sha256': sha256(transformed),
                'substitution': {'offset': offset, 'from': DB_IMPORT.decode(), 'to': STUB_IMPORT.decode()},
            },
            'adapter': {'name': ADAPTER, 'copied_as': 'ui_msgid_adapter.js', 'sha256': sha256(adapter)},
            'generator': {'name': generator.name, 'sha256': sha256(read_regular(str(generator), generator.name))},
            'csp': CSP,
            'expected_cases': EXPECTED_CASES,
            'files': [{'name': name, 'bytes': len(data), 'sha256': sha256(data)} for name, data in files],
        }
        record = (json.dumps(provenance, indent=2, ensure_ascii=False) + '\n').encode('utf-8')
        write_private(output, 'provenance.json', record)
    except BaseException:
        shutil.rmtree(output, ignore_errors=True)
        raise
    return {
        'task': 'T05.003',
        'output': os.path.basename(os.path.normpath(output)),
        'source_sha256': provenance['source']['sha256'],
        'transformed_sha256': provenance['transformed']['sha256'],
        'adapter_sha256': provenance['adapter']['sha256'],
        'provenance_sha256': sha256(record),
        'files': len(files) + 1,
        'expected_cases': EXPECTED_CASES,
    }


def main(argv):
    if len(argv) != 2:
        print('usage: ui_msgid_fixture.py UITEXT_SOURCE OUTPUT', file=sys.stderr)
        return 2
    try:
        summary = build(argv[0], argv[1])
    except Refused as error:
        print(f'refused: {error}', file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
