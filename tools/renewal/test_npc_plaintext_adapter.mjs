// T05.004: Node built-in tests for npc_plaintext_adapter.mjs.
//
// Everything here is an authored double: a small DOM with shadow roots and
// bubbling events, a MutationObserver double with microtask delivery and
// disconnect-drops-queue semantics, native-shape NpcBox/NpcMenu/InputBox
// renderers and the client API 1 lifecycle (fresh frozen descriptors,
// microtask replay from the current registry, removal emitted while still
// connected). Doubles do not establish browser MutationObserver behaviour;
// the generated fixture (npc_plaintext_fixture.py) is where the root checks
// native DOM. No stock module is imported or executed.
//
//   node --test tools/renewal/test_npc_plaintext_adapter.mjs

import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath, pathToFileURL } from 'node:url';

import initialize, { LIMITS, translateText, createCounts } from './npc_plaintext_adapter.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const thisFile = fileURLToPath(import.meta.url);
const adapterPath = path.join(here, 'npc_plaintext_adapter.mjs');
const builder = path.join(here, 'npc_plaintext_fixture.py');
const settle = () => new Promise(resolve => setTimeout(resolve, 0));

// --- MutationObserver double ---------------------------------------------------

const observers = new Set();
let deliveries = 0;

class MutationObserverDouble {
    constructor(callback) { this.callback = callback; this.targets = new Map(); this.queue = []; this.scheduled = false; }
    observe(target, options) { this.targets.set(target, { ...options }); observers.add(this); }
    disconnect() { this.targets.clear(); this.queue = []; observers.delete(this); }
    takeRecords() { return this.queue.splice(0); }
    enqueue(record) {
        this.queue.push(record);
        if (this.scheduled) return;
        this.scheduled = true;
        queueMicrotask(() => {
            this.scheduled = false;
            const records = this.queue.splice(0);
            if (!records.length) return;
            deliveries++;
            this.callback(records, this);
        });
    }
}

function notify(type, target) {
    for (const observer of [...observers]) {
        for (const [observed, options] of observer.targets) {
            if (!options[type]) continue;
            let node = target;
            while (node && node !== observed) node = options.subtree ? node.parentNode : null;
            if (node === observed) { observer.enqueue({ type, target }); break; }
        }
    }
}

// --- DOM double -----------------------------------------------------------------

class Node {
    constructor(nodeType) { this.nodeType = nodeType; this.parentNode = null; this.listeners = new Map(); }
    get isConnected() {
        let node = this;
        while (node.parentNode || node.host) node = node.parentNode || node.host;
        return Boolean(node.isDocument);
    }
    remove() { this.parentNode?.removeChild(this); }
    addEventListener(type, fn) {
        if (!this.listeners.has(type)) this.listeners.set(type, []);
        this.listeners.get(type).push(fn);
    }
    dispatchEvent(event) {
        event.target ??= this;
        let stopped = false;
        event.stopImmediatePropagation = () => { stopped = true; };
        for (let node = this; node && !stopped; node = node.parentNode) {
            for (const fn of node.listeners.get(event.type) || []) { fn(event); if (stopped) break; }
        }
        return true;
    }
}

class Text extends Node {
    constructor(data) { super(3); this._data = String(data); }
    get data() { return this._data; }
    set data(value) { this._data = String(value); notify('characterData', this); }
    get nodeValue() { return this._data; }
    get textContent() { return this._data; }
}

class Comment extends Node {
    constructor(data) { super(8); this.data = data; }
    get textContent() { return this.data; }
}

class ParentNode extends Node {
    constructor(nodeType) { super(nodeType); this.childNodes = []; }
    appendChild(child) { return this.insertBefore(child, null); }
    insertBefore(child, before) {
        child.parentNode?.removeChild(child);
        const i = before ? this.childNodes.indexOf(before) : this.childNodes.length;
        this.childNodes.splice(i, 0, child);
        child.parentNode = this;
        notify('childList', this);
        return child;
    }
    removeChild(child) {
        const i = this.childNodes.indexOf(child);
        if (i < 0) throw new Error('not a child');
        this.childNodes.splice(i, 1);
        child.parentNode = null;
        notify('childList', this);
        return child;
    }
    replaceChild(next, old) { this.insertBefore(next, old); this.removeChild(old); return old; }
    get textContent() { return this.childNodes.map(node => node.nodeType === 8 ? '' : node.textContent).join(''); }
    set textContent(value) {
        for (const child of [...this.childNodes]) this.removeChild(child);
        if (value !== '') this.appendChild(new Text(value));
    }
    *elements() {
        for (const child of this.childNodes) {
            if (child.nodeType !== 1) continue;
            yield child;
            yield* child.elements();
        }
    }
    querySelector(selector) {
        assert.match(selector, /^\.[a-z-]+$/, 'double supports class selectors only');
        const name = selector.slice(1);
        for (const element of this.elements()) if (element.classList.contains(name)) return element;
        return null;
    }
}

class Element extends ParentNode {
    constructor(localName) {
        super(1);
        this.localName = localName;
        this.attributes = new Map();
        const element = this;
        this.classList = {
            contains: name => (element.getAttribute('class') || '').split(/\s+/).includes(name),
            add: name => { if (!element.classList.contains(name)) element.setAttribute('class', `${element.getAttribute('class') || ''} ${name}`.trim()); },
            remove: name => element.setAttribute('class', (element.getAttribute('class') || '').split(/\s+/).filter(n => n && n !== name).join(' ')),
        };
    }
    getAttribute(name) { return this.attributes.has(name) ? this.attributes.get(name) : null; }
    hasAttribute(name) { return this.attributes.has(name); }
    setAttribute(name, value) { this.attributes.set(name, String(value)); }
    removeAttribute(name) { this.attributes.delete(name); }
    get isContentEditable() {
        for (let node = this; node && node.nodeType === 1; node = node.parentNode) {
            const value = node.getAttribute('contenteditable');
            if (value === '' || value === 'true' || value === 'plaintext-only') return true;
            if (value === 'false') return false;
        }
        return false;
    }
    closestIndexed() {
        for (let node = this; node && node.nodeType === 1; node = node.parentNode) {
            if (node.localName === 'div' && node.hasAttribute('data-index')) return node;
        }
        return null;
    }
}

class ShadowRoot extends ParentNode {
    constructor(host) { super(11); this.host = host; }
}

class Document extends ParentNode {
    constructor() { super(9); this.isDocument = true; this.body = this.appendChild(new Element('body')); }
}

function el(name, className, ...children) {
    const element = new Element(name);
    if (className) element.setAttribute('class', className);
    for (const child of children) element.appendChild(typeof child === 'string' ? new Text(child) : child);
    return element;
}

// --- authored native-shape components --------------------------------------------

const doc = new Document();

// NpcBox: setText appends one direct DIV under .content; next/close buttons
// own one listener each. Rows are given as Text data or authored nodes.
function createNpcBox(name = 'NpcBox') {
    const host = el('div', 'host');
    const root = new ShadowRoot(host);
    const content = el('div', 'content');
    const next = el('button', 'btn next', 'Next');
    const close = el('button', 'btn close', 'Close');
    root.appendChild(el('div', 'ui-component-root', el('div', 'border', content, el('div', 'btns', close, next))));
    const box = { name, host, root, content, next, close, ownerID: 0, presses: [], needCleanUp: false };
    next.addEventListener('click', () => { box.needCleanUp = true; box.presses.push(['next', box.ownerID]); });
    close.addEventListener('click', () => { box.needCleanUp = true; box.presses.push(['close', box.ownerID]); });
    box.setText = (parts, gid) => {
        box.ownerID = gid;
        if (box.needCleanUp) { box.needCleanUp = false; content.textContent = ''; }
        const row = el('div', null);
        for (const part of [].concat(parts)) row.appendChild(typeof part === 'string' ? new Text(part) : part);
        content.appendChild(row);
        return row;
    };
    box.onRemove = () => { content.textContent = ''; box.ownerID = 0; };
    return box;
}

// NpcMenu: split on ':', omit empty options, zero-based data-index, mousedown
// selects with parseInt, OK/double-click submit owner and index+1, cancel 255.
function createNpcMenu(name = 'NpcMenu') {
    const host = el('div', 'host');
    const root = new ShadowRoot(host);
    const content = el('div', 'content');
    const ok = el('button', 'btn ok', 'OK');
    const cancel = el('button', 'btn cancel', 'Cancel');
    root.appendChild(el('div', 'ui-component-root', el('div', 'middle', el('span', 'title'), content), cancel, ok));
    const menu = { name, host, root, content, ok, cancel, index: 0, owner: 0, submitted: [] };
    const validate = () => menu.submitted.push([menu.owner, menu.index + 1]);
    ok.addEventListener('click', validate);
    cancel.addEventListener('click', () => menu.submitted.push([menu.owner, 255]));
    content.addEventListener('mousedown', event => {
        const row = event.target.closestIndexed?.();
        if (row && row.parentNode === content) {
            for (const other of content.childNodes) other.classList?.remove('selected');
            row.classList.add('selected');
            menu.index = parseInt(row.getAttribute('data-index'), 10);
        }
        event.stopImmediatePropagation();
    });
    content.addEventListener('dblclick', event => { if (event.target.closestIndexed?.()) validate(); });
    menu.setMenu = (text, gid) => {
        menu.owner = gid;
        menu.index = 0;
        content.textContent = '';
        let j = 0;
        for (const option of text.split(':')) {
            if (!option.length) continue;
            const row = el('div', null, option);
            row.setAttribute('data-index', String(j++));
            content.appendChild(row);
        }
        content.childNodes[0]?.classList.add('selected');
    };
    menu.onRemove = () => { content.textContent = ''; };
    return menu;
}

// InputBox: never allowlisted. Number mode submits parseInt(value, 10) | 0.
function createInputBox() {
    const host = el('div', 'host');
    const root = new ShadowRoot(host);
    const label = el('div', 'text', 'Input number');
    const input = el('input', null);
    input.value = '';
    const button = el('button', 'ok', 'OK');
    const inner = el('div', 'inputbox', el('div', 'border', label, input, button));
    root.appendChild(el('div', 'ui-component-root', inner));
    const box = { name: 'InputBox', host, root, label, input, button, submitted: [] };
    box.setType = (type, value) => {
        if (type === 'number') inner.classList.add('number'); else inner.classList.remove('number');
        input.value = value;
    };
    button.addEventListener('click', () => {
        let text = input.value;
        if (inner.classList.contains('number')) text = parseInt(text, 10) | 0;
        box.submitted.push(text);
    });
    return box;
}

// --- client API 1 double ---------------------------------------------------------

function createRuntime() {
    const listeners = new Map();
    const components = new Map();
    const reports = [];
    function emit(event, value) {
        for (const listener of [...(listeners.get(event) || [])]) {
            try { listener(value); } catch (error) { reports.push(error); }
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
                try { Promise.resolve(fn()).catch(error => reports.push(error)); } catch (error) { reports.push(error); }
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
        return { api, cleanups, dispose() {
            if (disposed) return;
            disposed = true;
            for (const fn of [...cleanups].reverse()) fn();
        } };
    }
    return {
        scope, reports, components,
        // Like GUIComponent.append: attach, then emit a fresh descriptor every time.
        append(component) {
            if (!component.host.parentNode) doc.body.appendChild(component.host);
            const item = Object.freeze({ name: component.name, root: component.root, host: component.host });
            components.set(component, item); emit('ui:append', item);
            return item;
        },
        // Like GUIComponent.remove: emit while connected, then onRemove, then detach.
        remove(component) {
            const item = components.get(component);
            if (item) { components.delete(component); emit('ui:remove', item); }
            component.onRemove?.();
            component.host.remove();
        },
        // ui:remove only: the host and its rows stay connected and populated.
        removeConnected(component) {
            const item = components.get(component);
            if (item) { components.delete(component); emit('ui:remove', item); }
        },
        // A hand-made descriptor, for mismatch and malformed-shape cases.
        emit,
        listenerCount: () => [...listeners.values()].reduce((n, set) => n + set.size, 0),
    };
}

// PluginLoader shape: initialize, then adopt a returned dispose asynchronously.
function load(runtime, parameters, name) {
    const scope = runtime.scope(name);
    const core = initialize(parameters, scope.api);
    const adopted = Promise.resolve(core).then(result => {
        if (typeof result?.dispose === 'function') scope.api.cleanup(() => result.dispose());
    });
    return { scope, core, adopted };
}

const DICT = Object.freeze({
    Hello: '哈囉',
    Goodbye: '再會',
    'Welcome to Prontera.': '歡迎光臨普隆德拉。',
    'Next line': '下一行',
    'Prontera 普隆德拉 gate': '普隆德拉城門',
    Yes: '是',
    No: '否',
    Buy: '購買：道具',
    Sell: '賣出: 物品',
    Next: '下一步',
    'Input number': '輸入數字',
    '0007': '七',
    Ancient: '古代𠀋文字',
    'Quote "&" test': '引號「&」測試 "ok"',
    A: 'B',
    B: 'C',
    Click: '點擊',
    ' ': '空白',
    '': '空',
});
const dict = (extra = {}) => ({ ...DICT, ...extra });
const ready = (extra) => ({ dictionaryReady: dict(extra) });

function texts(row) { return row.childNodes.map(node => node.data); }

test.beforeEach(() => { globalThis.MutationObserver = MutationObserverDouble; });
test.afterEach(() => { observers.clear(); });

// --- API gate and lifecycle ---------------------------------------------------------

test('rejects anything but client API 1 or missing facilities before subscribing', () => {
    const runtime = createRuntime();
    const base = runtime.scope('gate').api;
    const variants = [
        undefined, null, {}, { ...base, version: '1' }, { ...base, version: 2 }, { ...base, version: 1.0000001 },
        { version: 1, on: base.on }, { version: 1, cleanup: base.cleanup }, { ...base, on: 'x' },
    ];
    for (const api of variants) assert.throws(() => initialize(ready(), api), TypeError);
    globalThis.MutationObserver = undefined;
    const scope = runtime.scope('no-mo');
    assert.throws(() => initialize(ready(), scope.api), /MutationObserver/);
    assert.equal(runtime.listenerCount(), 0);
    assert.equal(scope.cleanups.size, 0);
});

test('synchronous initialize returns idempotent dispose and frozen primitive diagnostics', () => {
    const runtime = createRuntime();
    const scope = runtime.scope();
    const core = initialize(ready(), scope.api);
    assert.ok(Object.isFrozen(core));
    assert.equal(typeof core.dispose, 'function');
    assert.ok(scope.cleanups.size >= 1, 'own dispose registered synchronously');
    const before = core.diagnostics();
    assert.ok(Object.isFrozen(before));
    for (const [key, value] of Object.entries(before)) {
        if (key === 'state') assert.equal(value, 'ready');
        else assert.ok(Number.isFinite(value) && value >= 0, key);
    }
    core.dispose();
    core.dispose();
    scope.dispose();
    assert.equal(core.diagnostics().state, 'disposed');
    assert.equal(runtime.listenerCount(), 0);
    assert.equal(before.state, 'ready', 'earlier snapshot is immutable');
});

// Group 1
test('preexisting dialogue and rows added after append; duplicate append and replay are idempotent', async () => {
    const runtime = createRuntime();
    const box = createNpcBox();
    const first = box.setText('Hello', 1);
    runtime.append(box);
    const { core, scope } = load(runtime, ready());
    await settle();
    assert.deepEqual(texts(first), ['哈囉'], 'replay translates text present before initialization');
    const node = first.childNodes[0];
    runtime.append(box); // engine appends again before each setText
    const second = box.setText('Welcome to Prontera.', 1);
    assert.deepEqual(texts(second), ['Welcome to Prontera.'], 'setText lands after append');
    const deliveriesBefore = deliveries;
    await settle();
    assert.deepEqual(texts(second), ['歡迎光臨普隆德拉。']);
    assert.equal(first.childNodes[0], node, 'same Text node identity');
    assert.ok(deliveries - deliveriesBefore <= 2, 'one mutation pass plus own-write delivery settle');
    runtime.append(box);
    runtime.append(box);
    await settle();
    assert.deepEqual([texts(first), texts(second)], [['哈囉'], ['歡迎光臨普隆德拉。']]);
    assert.equal(core.diagnostics().activeRoots, 1);
    scope.dispose();
});

// Group 2
test('exact per-line matching keeps delimiters, whitespace and misses', () => {
    const d = dict();
    const counts = createCounts();
    assert.equal(translateText(d, 'Hello\nUnknown line\r\nGoodbye', counts), '哈囉\nUnknown line\r\n再會');
    assert.ok(counts.hits === 2 && counts.misses === 1);
    assert.equal(translateText(d, 'Hello\rGoodbye\r\n\n'), '哈囉\r再會\r\n\n');
    assert.equal(translateText(d, 'Hello\n \n\t\nGoodbye\n'), '哈囉\n \n\t\n再會\n', 'whitespace lines kept even when a key matches');
    assert.equal(translateText(d, ' Hello'), null, 'no trimming');
    assert.equal(translateText(d, 'Hello '), null);
    assert.equal(translateText(d, 'hello'), null, 'case-sensitive');
    assert.equal(translateText(d, 'Hello '), null, 'no normalization');
    assert.equal(translateText(d, 'Prontera 普隆德拉 gate'), '普隆德拉城門', 'exact mixed-CJK key');
    assert.equal(translateText(d, 'Prontera 普隆德拉'), null, 'no substring match');
    assert.equal(translateText(d, '哈囉'), null, 'already Chinese misses');
    assert.equal(translateText(d, ''), null);
    assert.equal(translateText(d, '\r\n'), null);
});

// Group 3
test('adjacent Text nodes never join; only own data keys match', async () => {
    const proto = Object.create({ Inherited: '繼承' });
    proto.Own = '自有';
    assert.equal(translateText({ ...proto }, 'Own'), '自有');
    for (const key of ['toString', 'constructor', 'hasOwnProperty', '__proto__', 'valueOf']) {
        assert.equal(translateText(dict(), key), null, key);
    }
    const nullProto = Object.assign(Object.create(null), { Hello: '哈囉' });
    assert.equal(translateText(nullProto, 'Hello'), '哈囉');
    assert.equal(translateText(JSON.parse('{"__proto__":"原型"}'), '__proto__'), '原型', 'own JSON __proto__ key');
    const accessor = Object.defineProperty({}, 'Hello', { get() { throw new Error('accessor read'); }, enumerable: true });
    assert.equal(translateText(accessor, 'Hello'), null);
    assert.equal(translateText(Object.create({ Hello: '哈囉' }), 'Hello'), null, 'non-plain container rejected');

    const runtime = createRuntime();
    const box = createNpcBox();
    const { scope } = load(runtime, ready());
    runtime.append(box);
    const row = box.setText([new Text('Hel'), new Text('lo'), new Text('Goodbye')], 1);
    await settle();
    assert.deepEqual(texts(row), ['Hel', 'lo', '再會']);
    scope.dispose();
});

// Group 4
test('native-shape menu keeps omitted options, indexes, owner, OK/double-click and cancel 255', async () => {
    const runtime = createRuntime();
    const menu = createNpcMenu();
    const { scope } = load(runtime, ready());
    runtime.append(menu);
    menu.setMenu('Yes::Buy:Unknown:Sell:', 4242);
    await settle();
    const rows = menu.content.childNodes;
    assert.deepEqual(rows.map(r => r.getAttribute('data-index')), ['0', '1', '2', '3']);
    assert.deepEqual(rows.map(r => r.textContent), ['是', '購買：道具', 'Unknown', '賣出: 物品']);
    assert.equal(rows[0].getAttribute('class'), 'selected');
    rows[3].dispatchEvent({ type: 'mousedown' });
    menu.ok.dispatchEvent({ type: 'click' });
    rows[1].dispatchEvent({ type: 'mousedown' });
    rows[1].dispatchEvent({ type: 'dblclick' });
    menu.cancel.dispatchEvent({ type: 'click' });
    assert.deepEqual(menu.submitted, [[4242, 4], [4242, 2], [4242, 255]]);
    assert.equal(rows.length, 4, 'translated colon is not reparsed into options');
    scope.dispose();
});

// Group 5
test('Next/Close and unrelated controls keep identity, values and one listener action', async () => {
    const runtime = createRuntime();
    const box = createNpcBox();
    const { scope } = load(runtime, ready());
    runtime.append(box);
    const field = el('input', null);
    field.value = 'Hello';
    const nested = el('div', null, 'Click', el('button', null, 'Next'));
    box.content.appendChild(nested);
    box.content.appendChild(field);
    const row = box.setText('Hello', 9);
    await settle();
    const nextText = box.next.childNodes[0];
    assert.deepEqual([box.next.textContent, box.close.textContent], ['Next', 'Close']);
    assert.equal(box.next.childNodes[0], nextText);
    assert.equal(field.value, 'Hello');
    assert.equal(nested.textContent, 'ClickNext', 'row with a control is skipped whole');
    assert.deepEqual(texts(row), ['哈囉']);
    box.next.dispatchEvent({ type: 'click' });
    box.close.dispatchEvent({ type: 'click' });
    assert.deepEqual(box.presses, [['next', 9], ['close', 9]]);
    scope.dispose();
});

// Group 6
test('InputBox is excluded: text returns the exact string, number parseInt|0, value untouched', async () => {
    const runtime = createRuntime();
    const input = createInputBox();
    const { scope, core } = load(runtime, ready());
    runtime.append(input);
    await settle();
    assert.equal(input.label.textContent, 'Input number');
    input.setType('number', '0007');
    input.button.dispatchEvent({ type: 'click' });
    assert.equal(input.input.value, '0007');
    input.setType('text', '0007');
    input.button.dispatchEvent({ type: 'click' });
    input.setType('text', '哈囉𠀋「」');
    input.button.dispatchEvent({ type: 'click' });
    input.setType('number', '12abc');
    input.button.dispatchEvent({ type: 'click' });
    input.setType('number', '99999999999');
    input.button.dispatchEvent({ type: 'click' });
    assert.deepEqual(input.submitted, [7, '0007', '哈囉𠀋「」', 12, 99999999999 | 0]);
    assert.equal(input.input.value, '99999999999');
    assert.equal(core.diagnostics().activeRoots, 0);
    scope.dispose();
});

// Group 7
test('rows with spans, comments, controls or editable content are skipped whole; siblings translate', async () => {
    const runtime = createRuntime();
    const box = createNpcBox();
    const { scope } = load(runtime, ready());
    runtime.append(box);
    const coloured = el('span', null, 'Goodbye');
    coloured.style = { color: '#ff0000' };
    const item = el('span', 'item-link', 'Hello');
    item.setAttribute('data-item-id', '501');
    let itemClicks = 0;
    item.addEventListener('click', () => itemClicks++);
    const navi = el('span', 'navi-link', 'Hello');
    navi.setAttribute('data-navi-info', 'prontera,150,150');
    const rows = [
        box.setText(['Hello', coloured], 1),
        box.setText(['Hello ', item], 1),
        box.setText([navi], 1),
        box.setText(['Hello', new Comment('x')], 1),
        box.setText(['Hello'], 1),
    ];
    const editable = box.setText('Hello', 1);
    editable.setAttribute('contenteditable', 'false');
    const editableParent = el('div', null, 'Hello');
    editableParent.setAttribute('contenteditable', '');
    box.content.appendChild(editableParent);
    const plain = box.setText('Goodbye', 1);
    await settle();
    assert.deepEqual(rows.map(r => r.textContent), ['HelloGoodbye', 'Hello Hello', 'Hello', 'Hello', '哈囉']);
    assert.equal(item.getAttribute('data-item-id'), '501');
    assert.equal(navi.getAttribute('data-navi-info'), 'prontera,150,150');
    item.dispatchEvent({ type: 'click' });
    assert.equal(itemClicks, 1);
    assert.equal(editable.textContent, 'Hello', 'any contenteditable attribute excludes');
    assert.equal(editableParent.textContent, 'Hello');
    assert.deepEqual(texts(plain), ['再會']);

    // An editable ancestor up to the root excludes every row below it.
    const box2 = createNpcBox();
    box2.root.childNodes[0].setAttribute('contenteditable', 'true');
    runtime.append(box2);
    const blocked = box2.setText('Hello', 1);
    await settle();
    assert.deepEqual(texts(blocked), ['Hello']);
    scope.dispose();
});

// Group 8
test('unsafe, nonstring and oversized mappings are skipped independently; scalar punctuation passes', () => {
    const bad = {
        Num: 42, Nil: null, Obj: {}, Arr: ['x'], Empty: '', Space: ' 　 ', CR: 'a\rb', LF: 'a\nb',
        Colour: '^ff0000紅', Angle: '<b>粗</b>', Gt: 'a > b', Place: '{0} 個', Repl: '壞�',
        Lone: '\uD800x', LoneLow: 'x\uDC00', Long: 'x'.repeat(LIMITS.textUnits + 1),
        Edge: '字'.repeat(LIMITS.textUnits), Punct: '「哈囉」，『再會』！？：；…', Wide: '𠀋𠀌𡈽',
        Amp: 'A & B "quoted" \'single\' a: b', Hello: '哈囉',
    };
    const counts = createCounts();
    for (const key of ['Num', 'Nil', 'Obj', 'Arr', 'Empty', 'Space', 'CR', 'LF', 'Colour', 'Angle', 'Gt', 'Place', 'Repl', 'Lone', 'LoneLow']) {
        assert.equal(translateText(bad, `${key}\nHello`, counts), `${key}\n哈囉`, key);
    }
    assert.equal(counts.unsupported, 15);
    assert.equal(translateText(bad, 'Long\nHello', counts), 'Long\n哈囉', 'oversized target keeps its line only');
    assert.ok(counts.overflow >= 1);
    assert.equal(translateText(bad, 'Edge'), bad.Edge, 'target at the limit');
    assert.equal(translateText(bad, 'Punct\nWide\nAmp'), [bad.Punct, bad.Wide, bad.Amp].join('\n'));
    for (const source of ['^00FF00Hello', 'Hello <b>', '{1} Hello', '�Hello', '\uDBFFHello']) {
        assert.equal(translateText({ [source]: '好' }, source), null, `unsupported source ${JSON.stringify(source)}`);
    }
    assert.equal(translateText({ '^00FF0': '好' }, '^00FF0'), '好', 'five hex digits are ordinary text');
    assert.equal(translateText({ '{x}': '好' }, '{x}'), '好', 'only numbered placeholders are unsupported');
});

test('HTML-like targets never create elements in a live row', async () => {
    const runtime = createRuntime();
    const box = createNpcBox();
    const { scope } = load(runtime, ready({ Bold: '<b>粗</b>', Amp: '&amp; &lt;b&gt;' }));
    runtime.append(box);
    const row = box.setText('Bold\nAmp\nHello', 1);
    await settle();
    assert.deepEqual(texts(row), ['Bold\n&amp; &lt;b&gt;\n哈囉']);
    assert.ok(row.childNodes.every(n => n.nodeType === 3));
    scope.dispose();
});

// Group 9
test('pending dictionary: loading, then readiness translates current foreign text', async () => {
    const runtime = createRuntime();
    const box = createNpcBox();
    let resolve;
    const { core, scope } = load(runtime, { dictionaryReady: new Promise(r => { resolve = r; }) });
    assert.equal(core.diagnostics().state, 'loading');
    runtime.append(box);
    const row = box.setText('Hello', 1);
    await settle();
    assert.deepEqual(texts(row), ['Hello'], 'no writes while loading');
    assert.equal(core.diagnostics().activeRoots, 1);
    row.childNodes[0].data = 'Goodbye'; // foreign update before readiness
    resolve(dict());
    await settle();
    assert.equal(core.diagnostics().state, 'ready');
    assert.deepEqual(texts(row), ['再會']);
    const later = box.setText('Hello', 1);
    await settle();
    assert.deepEqual(texts(later), ['哈囉'], 'observer attached at readiness');
    scope.dispose();
});

test('rejected or malformed dictionaries fail inert without unhandled rejections', async () => {
    const unhandled = [];
    const onUnhandled = reason => unhandled.push(reason);
    process.on('unhandledRejection', onUnhandled);
    try {
        const thenable = { then(fn) { fn(dict()); } };
        const malformed = [undefined, null, 'x', 42, [], new Map([['Hello', '哈囉']]), thenable, Object.create({ Hello: '哈囉' })];
        for (const value of malformed) {
            const runtime = createRuntime();
            const box = createNpcBox();
            const { core, scope } = load(runtime, { dictionaryReady: value });
            assert.equal(core.diagnostics().state, 'failed', String(value));
            runtime.append(box);
            const row = box.setText('Hello', 1);
            await settle();
            assert.deepEqual(texts(row), ['Hello']);
            assert.equal(runtime.listenerCount(), 0, 'failed core holds no subscriptions');
            scope.dispose();
        }
        for (const settleWith of [r => r.reject(new Error('load failed')), r => r.resolve([]), r => r.resolve('dict'), r => r.resolve(null)]) {
            const runtime = createRuntime();
            const box = createNpcBox();
            const hooks = {};
            const promise = new Promise((resolve, reject) => Object.assign(hooks, { resolve, reject }));
            const { core, scope } = load(runtime, { dictionaryReady: promise });
            runtime.append(box);
            const row = box.setText('Hello', 1);
            settleWith(hooks);
            await settle();
            assert.equal(core.diagnostics().state, 'failed');
            assert.equal(core.diagnostics().activeRoots, 0);
            box.setText('Goodbye', 1);
            await settle();
            assert.deepEqual(box.content.childNodes.map(r => r.textContent), ['Hello', 'Goodbye']);
            assert.equal(runtime.listenerCount(), 0);
            assert.equal(observers.size, 0, 'no observer work after failure');
            scope.dispose();
        }
        // Parameters: missing, accessor-valued or nonplain containers fail inert.
        const runtime = createRuntime();
        const getter = Object.defineProperty({}, 'dictionaryReady', { get: () => dict(), enumerable: true });
        for (const parameters of [undefined, null, getter, Object.assign(Object.create({}), { dictionaryReady: dict() })]) {
            const scope = runtime.scope();
            assert.equal(initialize(parameters, scope.api).diagnostics().state, 'failed');
            scope.dispose();
        }
        await settle();
        assert.deepEqual(unhandled, []);
    } finally {
        process.off('unhandledRejection', onUnhandled);
    }
});

test('a malformed own mapping fails only its line', async () => {
    const runtime = createRuntime();
    const box = createNpcBox();
    const { core, scope } = load(runtime, ready({ Broken: 7, Hollow: '' }));
    runtime.append(box);
    const row = box.setText('Broken\nHello\nHollow\nGoodbye', 1);
    await settle();
    assert.deepEqual(texts(row), ['Broken\n哈囉\nHollow\n再會']);
    assert.equal(core.diagnostics().state, 'ready');
    scope.dispose();
});

test('removed or disposed before readiness: late resolve or reject writes nothing', async () => {
    const unhandled = [];
    const onUnhandled = reason => unhandled.push(reason);
    process.on('unhandledRejection', onUnhandled);
    try {
        const runtime = createRuntime();
        const removed = createNpcBox();
        const kept = createNpcBox();
        const hooks = {};
        const { core, scope } = load(runtime, { dictionaryReady: new Promise(r => { hooks.resolve = r; }) });
        runtime.append(removed);
        runtime.append(kept);
        const removedRow = removed.setText('Hello', 1);
        const keptRow = kept.setText('Hello', 1);
        runtime.removeConnected(removed); // emitted while connected; rows stay
        assert.ok(removed.host.isConnected);
        hooks.resolve(dict());
        await settle();
        assert.deepEqual(texts(keptRow), ['哈囉']);
        assert.deepEqual(texts(removedRow), ['Hello'], 'removed root inert while connected');
        scope.dispose();

        for (const late of ['resolve', 'reject']) {
            const rt = createRuntime();
            const box = createNpcBox();
            const h = {};
            const p = new Promise((resolve, reject) => Object.assign(h, { resolve, reject }));
            const loaded = load(rt, { dictionaryReady: p });
            rt.append(box);
            const row = box.setText('Hello', 1);
            await settle();
            loaded.core.dispose();
            if (late === 'resolve') h.resolve(dict()); else h.reject(new Error('late'));
            await settle();
            box.setText('Goodbye', 1);
            await settle();
            assert.deepEqual(texts(row), ['Hello']);
            assert.equal(loaded.core.diagnostics().state, 'disposed');
            loaded.scope.dispose();
        }
        await settle();
        assert.deepEqual(unhandled, []);
        assert.equal(core.diagnostics().state, 'disposed');
    } finally {
        process.off('unhandledRejection', onUnhandled);
    }
});

// Group 10
test('queued replay reads the current registry; immediate append and early removal', async () => {
    const runtime = createRuntime();
    const before = createNpcBox();
    const gone = createNpcBox();
    before.setText('Hello', 1);
    gone.setText('Hello', 1);
    runtime.append(before);
    runtime.append(gone);
    const { scope } = load(runtime, ready());
    const immediate = createNpcMenu();
    runtime.append(immediate); // delivered live before the replay microtask
    immediate.setMenu('Yes:No', 2);
    runtime.remove(gone); // removed before the replay runs
    const late = createNpcBox();
    runtime.append(late); // joins the registry before replay reads it
    late.setText('Goodbye', 3);
    await settle();
    assert.equal(before.content.textContent, '哈囉');
    assert.equal(gone.content.textContent, '', 'native onRemove cleared it; nothing written');
    assert.deepEqual(immediate.content.childNodes.map(r => r.textContent), ['是', '否']);
    assert.equal(late.content.textContent, '再會');
    scope.dispose();
});

test('scope cleanup before loader adoption, and loader re-registration, are safe', async () => {
    const runtime = createRuntime();
    const box = createNpcBox();
    runtime.append(box);
    const { scope, core, adopted } = load(runtime, ready());
    scope.dispose(); // generation changed before the loader adopts the handle
    await adopted;
    await settle();
    box.setText('Hello', 1);
    await settle();
    assert.equal(box.content.textContent, 'Hello');
    assert.equal(core.diagnostics().state, 'disposed');
    assert.equal(runtime.listenerCount(), 0);
    assert.deepEqual(runtime.reports, []);

    // Initialized on an already-disposed scope: cleanup runs at once, no throw.
    const dead = runtime.scope('dead');
    dead.dispose();
    const late = initialize(ready(), dead.api);
    assert.equal(late.diagnostics().state, 'disposed');
});

test('remove while connected, detach/reappend, and name/host mismatches', async () => {
    const runtime = createRuntime();
    const box = createNpcBox();
    const { core, scope } = load(runtime, ready());
    const descriptor = runtime.append(box);
    box.setText('Hello', 1);
    await settle();
    // Same root under another name or host: ignored, and cannot release it.
    const impostor = Object.freeze({ name: 'NpcMenu', root: box.root, host: box.host });
    const otherHost = Object.freeze({ name: 'NpcBox', root: box.root, host: el('div', null) });
    for (const fake of [impostor, otherHost]) {
        runtime.emit('ui:append', fake);
        runtime.emit('ui:remove', fake);
    }
    const impostorRow = box.setText('Yes', 1);
    await settle();
    assert.deepEqual(texts(impostorRow), ['是'], 'original owner still active');
    assert.equal(core.diagnostics().activeRoots, 1, 'mismatched removes did not release');
    assert.ok(Object.isFrozen(descriptor));
    // Removal emitted while connected; the content stays physically connected.
    const kept = box.content.childNodes[0];
    runtime.removeConnected(box);
    assert.ok(box.host.isConnected);
    const after = box.setText('Goodbye', 1);
    await settle();
    assert.deepEqual(texts(after), ['Goodbye'], 'removed root is inert while connected');
    assert.equal(kept.textContent, '哈囉', 'no blanket restoration');
    assert.equal(core.diagnostics().activeRoots, 0);
    // A fresh append starts a new generation.
    runtime.append(box);
    await settle();
    assert.deepEqual(texts(after), ['再會']);
    const again = box.setText('Hello', 1);
    await settle();
    assert.deepEqual(texts(again), ['哈囉']);
    scope.dispose();
});

// Group 11
test('MutationObserver: foreign data changes, row replacement and output-as-key chains', async () => {
    const runtime = createRuntime();
    const box = createNpcBox();
    const { scope } = load(runtime, ready());
    runtime.append(box);
    const row = box.setText('A', 1);
    await settle();
    await settle();
    assert.deepEqual(texts(row), ['B'], 'output B is never re-read as key B');
    const text = row.childNodes[0];
    text.data = 'Hello'; // distinguishably new foreign value
    await settle();
    assert.equal(text.data, '哈囉');
    text.data = '自訂文字'; // foreign Chinese stays
    await settle();
    assert.equal(text.data, '自訂文字');
    text.data = 'A';
    await settle();
    assert.equal(text.data, 'B');
    // Partial foreign multiline edit re-evaluates the whole Text.
    const multi = box.setText('Hello\nGoodbye', 1);
    await settle();
    multi.childNodes[0].data = '哈囉\nYes';
    await settle();
    assert.equal(multi.childNodes[0].data, '哈囉\n是');
    // Row replacement and foreign element insertion.
    const replacement = el('div', null, 'Goodbye');
    box.content.replaceChild(replacement, row);
    const span = el('span', null, 'Hello');
    multi.appendChild(span);
    await settle();
    assert.deepEqual(texts(replacement), ['再會']);
    assert.equal(span.textContent, 'Hello', 'row turned unsupported; nothing touched');
    box.content.removeChild(replacement);
    await settle();
    const quiet = deliveries;
    await settle();
    await settle();
    assert.equal(deliveries, quiet, 'own-write deliveries settle');
    scope.dispose();
});

test('queued observer callbacks after remove or dispose write nothing', async () => {
    for (const end of ['remove', 'dispose']) {
        const runtime = createRuntime();
        const box = createNpcBox();
        const { scope, core } = load(runtime, ready());
        runtime.append(box);
        await settle();
        const row = el('div', null, 'Hello');
        box.content.appendChild(row); // record queued
        if (end === 'remove') runtime.removeConnected(box);
        else core.dispose();
        await settle();
        assert.deepEqual(texts(row), ['Hello'], end);
        scope.dispose();
    }
});

test('stale content replacement is retired; only a fresh append adopts new content', async () => {
    const runtime = createRuntime();
    const box = createNpcBox();
    const { core, scope } = load(runtime, ready());
    runtime.append(box);
    await settle();
    const old = box.content;
    const fresh = el('div', 'content');
    old.parentNode.insertBefore(fresh, old); // first .content is now the new node
    const oldRow = el('div', null, 'Hello');
    old.appendChild(oldRow); // the old observer still fires
    const newRow = el('div', null, 'Hello');
    fresh.appendChild(newRow);
    await settle();
    assert.deepEqual(texts(oldRow), ['Hello'], 'stale content is not written');
    assert.deepEqual(texts(newRow), ['Hello'], 'new content waits for a fresh append');
    assert.ok(core.diagnostics().stale >= 1);
    // A same-name descriptor from another host cannot adopt the new content.
    runtime.emit('ui:append', Object.freeze({ name: 'NpcBox', root: box.root, host: el('div', null) }));
    runtime.emit('ui:append', Object.freeze({ name: 'NpcMenu', root: box.root, host: box.host }));
    await settle();
    assert.deepEqual(texts(newRow), ['Hello'], 'mismatched host/name cannot adopt');
    runtime.append(box);
    await settle();
    assert.deepEqual(texts(newRow), ['哈囉']);
    old.appendChild(el('div', null, 'Hello'));
    await settle();
    assert.equal(old.childNodes[1].textContent, 'Hello', 'old content stays unobserved');
    assert.equal(core.diagnostics().activeRoots, 1);
    scope.dispose();
});

// Group 12
test('component allowlist and row shape negatives', async () => {
    const runtime = createRuntime();
    const { core, scope } = load(runtime, ready());
    for (const name of ['npcbox', 'NpcBox ', 'NpcMenuV2', 'ChatBox', 'InputBox', '']) {
        const box = createNpcBox(name);
        box.setText('Hello', 1);
        runtime.append(box);
        await settle();
        assert.equal(box.content.textContent, 'Hello', name);
    }
    const orphan = createNpcBox();
    orphan.setText('Hello', 1);
    for (const bad of [null, 1, 'NpcBox', { name: 'NpcBox' }, { name: 'NpcBox', root: {}, host: {} },
        { name: 'NpcBox', root: orphan.root, host: null }, { name: ['NpcBox'], root: orphan.root, host: orphan.host }]) {
        runtime.emit('ui:append', bad);
        runtime.emit('ui:remove', bad);
    }
    await settle();
    assert.equal(orphan.content.textContent, 'Hello', 'malformed descriptors ignored');
    assert.ok(core.diagnostics().ignored >= 1);
    const menu = createNpcMenu();
    runtime.append(menu);
    const unindexed = el('div', null, 'Yes');
    const deep = el('p', null, 'Yes');
    menu.content.appendChild(unindexed);
    menu.content.appendChild(deep);
    menu.content.appendChild(new Text('Yes'));
    const nested = el('div', null, el('div', null, 'Yes'));
    nested.setAttribute('data-index', '0');
    menu.content.appendChild(nested);
    await settle();
    assert.equal(unindexed.textContent, 'Yes', 'NpcMenu rows need data-index');
    assert.equal(deep.textContent, 'Yes');
    assert.equal(menu.content.childNodes[2].data, 'Yes', 'bare content Text is not a row');
    assert.equal(nested.textContent, 'Yes', 'nested rows are not walked');
    assert.equal(core.diagnostics().activeRoots, 1);
    scope.dispose();
});

test('root bound: eight active roots, the ninth waits for a later append', async () => {
    const runtime = createRuntime();
    const { core, scope } = load(runtime, ready());
    const boxes = Array.from({ length: LIMITS.roots + 1 }, () => createNpcBox());
    for (const box of boxes) { runtime.append(box); box.setText('Hello', 1); }
    await settle();
    assert.equal(core.diagnostics().activeRoots, LIMITS.roots);
    assert.equal(boxes[LIMITS.roots].content.textContent, 'Hello');
    assert.ok(core.diagnostics().overflow >= 1);
    runtime.remove(boxes[0]);
    await settle();
    assert.equal(boxes[LIMITS.roots].content.textContent, 'Hello', 'not adopted without a fresh append');
    runtime.append(boxes[LIMITS.roots]);
    await settle();
    assert.equal(boxes[LIMITS.roots].content.textContent, '哈囉');
    scope.dispose();
    assert.equal(core.diagnostics().activeRoots, 0);
});

test('content and row node bounds at limit and overflow', async () => {
    const runtime = createRuntime();
    const { scope } = load(runtime, ready());
    const box = createNpcBox();
    runtime.append(box);
    for (let i = 0; i < LIMITS.contentNodes - 1; i++) box.content.appendChild(new Comment('pad'));
    const last = box.setText('Hello', 1);
    await settle();
    assert.equal(box.content.childNodes.length, LIMITS.contentNodes);
    assert.deepEqual(texts(last), ['哈囉'], '256 direct nodes still scan');
    box.content.appendChild(new Comment('over'));
    const over = el('div', null, 'Goodbye');
    box.content.appendChild(over);
    await settle();
    assert.deepEqual(texts(over), ['Goodbye'], 'more than 256 nodes: no new writes');
    assert.deepEqual(texts(last), ['哈囉'], 'earlier translation is not undone');

    const box2 = createNpcBox();
    runtime.append(box2);
    const full = box2.setText(Array.from({ length: LIMITS.rowNodes }, () => new Text('Hello')), 1);
    const tooMany = box2.setText(Array.from({ length: LIMITS.rowNodes + 1 }, () => new Text('Hello')), 1);
    const sibling = box2.setText('Goodbye', 1);
    await settle();
    assert.ok(texts(full).every(t => t === '哈囉'), '32 row children translate');
    assert.ok(texts(tooMany).every(t => t === 'Hello'), '33 row children skip the row');
    assert.deepEqual(texts(sibling), ['再會']);
    scope.dispose();
});

test('text, line, target and assembled-output bounds', () => {
    const d = dict({ Edge: '字'.repeat(LIMITS.textUnits), Over: '字'.repeat(LIMITS.textUnits + 1), Half: '字'.repeat(4096) });
    const atLimit = 'Hello' + ' '.repeat(LIMITS.textUnits - 5);
    assert.equal(atLimit.length, LIMITS.textUnits);
    assert.equal(translateText(d, atLimit), null, 'whole-line miss');
    const sized = 'Hello\n' + 'x'.repeat(LIMITS.textUnits - 6);
    assert.equal(sized.length, LIMITS.textUnits);
    assert.equal(translateText(d, sized), '哈囉\n' + 'x'.repeat(LIMITS.textUnits - 6), '8192 units translate');
    const counts = createCounts();
    assert.equal(translateText(d, sized + 'x', counts), null, '8193 units skip before parsing');
    assert.deepEqual([counts.overflow, counts.hits, counts.misses], [1, 0, 0]);

    const lines = n => Array.from({ length: n }, () => 'Hello').join('\n');
    assert.equal(translateText(d, lines(LIMITS.lines)), Array.from({ length: LIMITS.lines }, () => '哈囉').join('\n'));
    assert.equal(translateText(d, lines(LIMITS.lines + 1)), null, '257 lines skip');
    const crlf = Array.from({ length: LIMITS.lines }, () => 'Hello').join('\r\n');
    assert.ok(translateText(d, crlf), 'CRLF counts once: 256 lines');
    assert.equal(translateText(d, lines(LIMITS.lines) + '\n'), null, 'a trailing empty line counts');
    assert.ok(translateText(d, lines(LIMITS.lines - 1) + '\n'), '255 lines plus trailing empty is 256');

    assert.equal(translateText(d, 'Edge'), d.Edge);
    assert.equal(translateText(d, 'Over\nHello'), 'Over\n哈囉', 'oversized target keeps its line');
    const whole = createCounts();
    assert.equal(translateText(d, 'Edge\nHello', whole), null, 'assembled output over 8192 keeps the whole Text');
    assert.equal(translateText(d, 'Half\nHalf'), null, '4096+1+4096 is over the limit');
    assert.ok(whole.overflow >= 1);
});

test('oversized live Text is skipped whole and never retried endlessly', async () => {
    const runtime = createRuntime();
    const { core, scope } = load(runtime, ready({ Edge: '字'.repeat(LIMITS.textUnits) }));
    const box = createNpcBox();
    runtime.append(box);
    const row = box.setText(['Edge\nHello', 'Hello'], 1);
    await settle();
    assert.deepEqual(texts(row), ['Edge\nHello', '哈囉'], 'independent Text in the same row continues');
    const quiet = deliveries;
    await settle();
    await settle();
    assert.equal(deliveries, quiet);
    assert.ok(core.diagnostics().overflow >= 1);
    scope.dispose();
});

test('diagnostics hold no text, references or growing arrays', async () => {
    const runtime = createRuntime();
    const { core, scope } = load(runtime, ready());
    const box = createNpcBox();
    runtime.append(box);
    box.setText('Hello\nSecret miss', 1);
    await settle();
    const snapshot = core.diagnostics();
    assert.deepEqual(Object.keys(snapshot).sort(), ['activeRoots', 'errors', 'hits', 'ignored', 'misses', 'overflow', 'stale', 'state', 'unsupported']);
    assert.ok(Object.values(snapshot).every(v => typeof v === 'number' || ['loading', 'ready', 'failed', 'disposed'].includes(v)));
    assert.ok(!JSON.stringify(snapshot).includes('Secret'));
    assert.ok(snapshot.hits >= 1 && snapshot.misses >= 1);
    scope.dispose();
});

test('the borrowed dictionary is not mutated, cloned or iterated per scan', async () => {
    const reads = [];
    const target = dict();
    const watched = new Proxy(target, {
        ownKeys(t) { reads.push('ownKeys'); return Reflect.ownKeys(t); },
        getOwnPropertyDescriptor(t, key) { reads.push(key); return Reflect.getOwnPropertyDescriptor(t, key); },
        set() { throw new Error('mutation'); },
        defineProperty() { throw new Error('mutation'); },
        deleteProperty() { throw new Error('mutation'); },
    });
    const runtime = createRuntime();
    const { scope } = load(runtime, { dictionaryReady: watched });
    const box = createNpcBox();
    runtime.append(box);
    box.setText('Hello\nGoodbye\nMiss', 1);
    await settle();
    // One thenable probe at readiness, then exactly one own-key read per line.
    assert.deepEqual(reads, ['then', 'Hello', 'Goodbye', 'Miss']);
    assert.equal(box.content.textContent, '哈囉\n再會\nMiss');
    scope.dispose();
});

test('every write rechecks ownership, row, node and value after lookup', async () => {
    // Test-only lookup trap standing in for anything that runs mid-scan.
    for (const interfere of ['detach-row', 'change-data', 'move-text', 'dispose', 'remove', 'add-element']) {
        const runtime = createRuntime();
        const box = createNpcBox();
        let armed = false;
        let core;
        const action = {
            'detach-row': row => row.remove(),
            'change-data': row => { row.childNodes[0]._data = 'Hello!'; },
            'move-text': row => { el('div', null).appendChild(row.childNodes[0]); },
            dispose: () => core.dispose(),
            remove: () => runtime.removeConnected(box),
            'add-element': row => row.appendChild(el('span', null, 'x')),
        }[interfere];
        let target;
        const trapped = new Proxy(dict(), {
            getOwnPropertyDescriptor(t, key) {
                if (armed && key === 'Hello') { armed = false; action(target); }
                return Reflect.getOwnPropertyDescriptor(t, key);
            },
        });
        const loaded = load(runtime, { dictionaryReady: trapped });
        core = loaded.core;
        runtime.append(box);
        await settle();
        target = el('div', null, 'Hello');
        const text = target.childNodes[0];
        armed = true;
        box.content.appendChild(target);
        await settle();
        assert.notEqual(text.data, '哈囉', interfere);
        loaded.scope.dispose();
    }
});

test('adapter source: no fetch, storage, timers, globals beyond MutationObserver, or DOM replacement', () => {
    const source = fs.readFileSync(adapterPath, 'utf8');
    const code = source.replace(/\/\/.*$/gm, '');
    for (const banned of [/\bfetch\b/, /XMLHttpRequest/, /localStorage|sessionStorage|indexedDB/, /\bimport\s*\(/, /^\s*import\s/m,
        /setTimeout|setInterval|requestAnimationFrame/, /innerHTML|outerHTML|textContent\s*=|insertAdjacent|replaceWith|replaceChild/,
        /\beval\b|new Function/, /document\b/, /window\b/, /\.prototype\.\w+\s*=/, /addEventListener/]) {
        assert.doesNotMatch(code, banned, String(banned));
    }
    assert.match(code, /globalThis\.MutationObserver/);
    assert.match(code, /memo: new WeakMap\(\)/);
});

// Weak node memo: run only in a child with --expose-gc so it is never skipped.
const gcChild = process.env.T05_NPC_GC_CHILD === '1' && typeof globalThis.gc === 'function';
if (gcChild) {
    test('weak memo: replaced rows are collectable', async () => {
        const runtime = createRuntime();
        const { scope } = load(runtime, ready());
        const box = createNpcBox();
        runtime.append(box);
        let collected = 0;
        const registry = new FinalizationRegistry(() => { collected++; });
        for (let round = 0; round < 200; round++) {
            box.content.textContent = '';
            const row = box.setText('Hello', 1);
            registry.register(row.childNodes[0], round);
            await settle();
            assert.equal(row.childNodes[0].data, '哈囉');
        }
        box.content.textContent = '';
        for (let i = 0; i < 10 && collected < 150; i++) { await settle(); globalThis.gc(); await settle(); }
        assert.ok(collected >= 150, `collected ${collected} of 200 departed translated Text nodes`);
        scope.dispose();
    });
} else {
    test('weak memo is checked in an --expose-gc child', () => {
        const env = { ...process.env, T05_NPC_GC_CHILD: '1' };
        delete env.NODE_TEST_CONTEXT; // report to stdout, not to this runner
        const result = spawnSync(process.execPath, ['--expose-gc', '--test', '--test-reporter=tap', thisFile], {
            encoding: 'utf8', timeout: 60000, env,
        });
        assert.equal(result.status, 0, result.stdout + result.stderr);
        assert.match(result.stdout, /^ok \d+ - weak memo: replaced rows are collectable$/m);
        assert.match(result.stdout, /^# fail 0$/m);
        assert.match(result.stdout, /^# skipped 0$/m);
    });
}

// --- fixture builder --------------------------------------------------------------------

const sha256 = data => createHash('sha256').update(data).digest('hex');
// Real path: on macOS the temp directory sits under a linked /var.
const tempRoot = () => fs.mkdtempSync(path.join(fs.realpathSync(os.tmpdir()), 't05-004-'));
const build = (...args) => spawnSync('python3', ['-I', builder, ...args], { encoding: 'utf8', timeout: 30000 });

if (!gcChild) {
    test('builder creates a private, provenance-bound, self-only fixture', async () => {
        const dir = tempRoot();
        try {
            const output = path.join(dir, 'fixture');
            const result = build(adapterPath, output);
            assert.equal(result.status, 0, result.stderr);
            const summary = JSON.parse(result.stdout);
            assert.ok(!result.stdout.includes(dir) && !result.stdout.includes(os.homedir()), 'no absolute path in summary');
            assert.equal(summary.expected_groups, 13);
            assert.equal(fs.statSync(output).mode & 0o777, 0o700);
            const provenance = JSON.parse(fs.readFileSync(path.join(output, 'provenance.json'), 'utf8'));
            assert.equal(sha256(fs.readFileSync(path.join(output, 'provenance.json'))), summary.provenance_sha256);
            assert.equal(provenance.adapter.sha256, sha256(fs.readFileSync(adapterPath)));
            assert.equal(provenance.generator.sha256, sha256(fs.readFileSync(builder)));
            assert.ok(!JSON.stringify(provenance).includes(dir));
            const names = fs.readdirSync(output).sort();
            assert.deepEqual(names, [...provenance.files.map(f => f.name), 'provenance.json'].sort());
            for (const file of provenance.files) {
                const full = path.join(output, file.name);
                assert.equal(fs.statSync(full).mode & 0o777, 0o600, file.name);
                const bytes = fs.readFileSync(full);
                assert.equal(sha256(bytes), file.sha256, file.name);
                assert.equal(bytes.length, file.bytes);
            }
            assert.equal(sha256(fs.readFileSync(path.join(output, 'npc_plaintext_adapter.js'))), provenance.adapter.sha256);

            const html = fs.readFileSync(path.join(output, 'index.html'), 'utf8');
            const csp = html.match(/http-equiv="Content-Security-Policy" content="([^"]+)"/)[1];
            assert.equal(csp, provenance.csp);
            for (const directive of ["default-src 'none'", "script-src 'self'", "style-src 'self'", "img-src 'none'", "connect-src 'none'",
                "frame-src 'none'", "object-src 'none'", "worker-src 'none'"]) assert.ok(csp.split('; ').includes(directive), directive);
            assert.doesNotMatch(csp, /unsafe|data:|blob:|http/);
            assert.doesNotMatch(html, /<script(?![^>]*\bsrc=)[^>]*>/, 'no inline scripts');
            assert.doesNotMatch(html, /\son[a-z]+=|\sstyle=|<style/i, 'no inline handlers or styles');
            assert.match(html, /NOT RUN/);
            assert.match(html, /data-expected="13"/);

            const scripts = names.filter(n => n.endsWith('.js'));
            const local = new Set(names);
            for (const name of scripts) {
                const code = fs.readFileSync(path.join(output, name), 'utf8');
                for (const match of code.matchAll(/^\s*import\s[^'"]*['"]([^'"]+)['"]/gm)) {
                    assert.match(match[1], /^\.\/[a-z_-]+\.js$/, `${name} imports ${match[1]}`);
                    assert.ok(local.has(match[1].slice(2)), `${name} import exists`);
                }
                assert.doesNotMatch(code, /\bfetch\s*\(|XMLHttpRequest|WebSocket|EventSource|sendBeacon|localStorage|sessionStorage|indexedDB|\bimport\s*\(|https?:\/\/(?!www\.w3\.org)/, name);
                assert.doesNotMatch(code, /innerHTML|outerHTML|insertAdjacentHTML|document\.write|setAttribute\(\s*['"]style/, name);
            }
            for (const name of names.filter(n => n.endsWith('.css'))) {
                assert.doesNotMatch(fs.readFileSync(path.join(output, name), 'utf8'), /url\(|@import/i, name);
            }
            const dictionaryJs = fs.readFileSync(path.join(output, 'dictionary.js'), 'utf8');
            assert.ok(dictionaryJs.length < 64 * 1024, 'tiny authored dictionary');
            const harness = fs.readFileSync(path.join(output, 'harness.js'), 'utf8');
            for (const mode of ['api-append-error', 'api-replay-error', 'api-cleanup-error', 'zero-assertions', 'unhandled-rejection', 'csp-inline']) {
                assert.ok(harness.includes(`'${mode}'`), mode);
            }
            assert.equal((harness.match(/^\s*group\(\d+, '/gm) || []).length, 13, 'thirteen baseline groups');

            // The generated reporter and API double are authored; exercise them here.
            const reporter = await import(pathToFileURL(path.join(output, 'reporter.js')).href);
            const passing = reporter.createReporter(['a', 'b']);
            passing.record('a', 2, []); passing.record('b', 1, []);
            assert.equal(passing.summary().state, 'pass');
            const zero = reporter.createReporter(['a', 'b']);
            zero.record('a', 1, []); zero.record('b', 0, []);
            assert.equal(zero.summary().state, 'fail', 'zero assertions');
            const missing = reporter.createReporter(['a', 'b']);
            missing.record('a', 1, []);
            assert.equal(missing.summary().state, 'fail', 'omitted group');
            const sticky = reporter.createReporter(['a']);
            sticky.fail('boom'); sticky.record('a', 3, []);
            assert.equal(sticky.summary().state, 'fail', 'failure is sticky');
            const unexpected = reporter.createReporter(['a']);
            unexpected.record('a', 1, []); unexpected.record('zzz', 1, []);
            assert.equal(unexpected.summary().state, 'fail', 'unexpected group');
            const failed = reporter.createReporter(['a']);
            failed.record('a', 4, ['bad']);
            assert.equal(failed.summary().state, 'fail');

            const { createRuntime: fixtureRuntime } = await import(pathToFileURL(path.join(output, 'api-double.js')).href);
            assert.throws(() => fixtureRuntime(), /error sink/);
            const errors = [];
            const rt = fixtureRuntime(error => errors.push(String(error.message)));
            const component = { name: 'NpcBox', root: { querySelector: () => null }, host: {} };
            const s = rt.scope('fault');
            s.api.on('ui:append', () => { throw new Error('append fault'); }, { replay: false });
            rt.append(component);
            s.api.on('ui:append', () => { throw new Error('replay fault'); });
            await settle();
            s.api.cleanup(() => { throw new Error('cleanup fault'); });
            s.dispose();
            assert.deepEqual(errors, ['append fault', 'replay fault', 'cleanup fault']);
            const appended = rt.append(component);
            assert.ok(Object.isFrozen(appended));
            assert.notEqual(rt.append(component), appended, 'fresh descriptor per append');
        } finally {
            fs.rmSync(dir, { recursive: true, force: true });
        }
    });

    test('builder refuses existing output, links, oversize, non-regular and missing sources', () => {
        const dir = tempRoot();
        try {
            const exists = path.join(dir, 'exists');
            fs.mkdirSync(exists);
            let result = build(adapterPath, exists);
            assert.equal(result.status, 1);
            assert.match(result.stderr, /already exists/);

            const link = path.join(dir, 'adapter-link.mjs');
            fs.symlinkSync(adapterPath, link);
            result = build(link, path.join(dir, 'a'));
            assert.match(result.stderr, /symbolic link/);
            assert.ok(!fs.existsSync(path.join(dir, 'a')));

            const realDir = path.join(dir, 'real');
            fs.mkdirSync(realDir);
            fs.copyFileSync(adapterPath, path.join(realDir, 'adapter.mjs'));
            fs.symlinkSync(realDir, path.join(dir, 'linked'));
            result = build(path.join(dir, 'linked', 'adapter.mjs'), path.join(dir, 'b'));
            assert.match(result.stderr, /symbolic link/, 'linked source ancestor');
            result = build(adapterPath, path.join(dir, 'linked', 'out'));
            assert.match(result.stderr, /symbolic link/, 'linked output ancestor');
            assert.ok(!fs.existsSync(path.join(realDir, 'out')));
            fs.symlinkSync(path.join(dir, 'nowhere'), path.join(dir, 'dangling'));
            result = build(adapterPath, path.join(dir, 'dangling'));
            assert.match(result.stderr, /already exists/, 'dangling output link');

            const big = path.join(dir, 'big.mjs');
            fs.writeFileSync(big, Buffer.alloc(1024 * 1024 + 1, 0x20));
            result = build(big, path.join(dir, 'c'));
            assert.match(result.stderr, /read limit/);
            result = build(path.join(dir, 'missing.mjs'), path.join(dir, 'd'));
            assert.match(result.stderr, /not found/);
            result = build(realDir, path.join(dir, 'e'));
            assert.match(result.stderr, /not a regular file/);
            result = build(adapterPath, path.join(dir, 'missing-parent', 'f'));
            assert.equal(result.status, 1);
            result = build(adapterPath);
            assert.equal(result.status, 2);
            for (const name of ['a', 'b', 'c', 'd', 'e']) assert.ok(!fs.existsSync(path.join(dir, name)), name);
        } finally {
            fs.rmSync(dir, { recursive: true, force: true });
        }
    });

    test('builder bounds reads even when a file grows after its size check', () => {
        const dir = tempRoot();
        try {
            const grown = path.join(dir, 'grown.mjs');
            fs.writeFileSync(grown, Buffer.alloc(3 * 1024 * 1024, 0x20));
            // Pretend fstat saw a small file; the chunked read must still stop at cap + 1.
            const probe = [
                'import importlib.util, os, sys',
                'spec = importlib.util.spec_from_file_location("b", sys.argv[1]); b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)',
                'real_fstat, real_read, total = os.fstat, os.read, [0]',
                'class Small:',
                '    def __init__(s, v): s.v = v',
                '    def __getattr__(s, k): return 10 if k == "st_size" else getattr(s.v, k)',
                'os.fstat = lambda fd: Small(real_fstat(fd))',
                'def counted(fd, n):',
                '    data = real_read(fd, n); total[0] += len(data); return data',
                'os.read = counted',
                'try:',
                '    b.read_regular(sys.argv[2], "probe")',
                '    print("read"); sys.exit(1)',
                'except b.Refused as e:',
                '    print(e, total[0])',
                '    sys.exit(0 if total[0] <= b.READ_LIMIT + 1 else 1)',
            ].join('\n');
            const result = spawnSync('python3', ['-I', '-B', '-c', probe, builder, grown], { encoding: 'utf8', timeout: 10000 });
            assert.equal(result.status, 0, result.stdout + result.stderr);
            assert.match(result.stdout, /read limit exceeded/);
        } finally {
            fs.rmSync(dir, { recursive: true, force: true });
        }
    });
}
