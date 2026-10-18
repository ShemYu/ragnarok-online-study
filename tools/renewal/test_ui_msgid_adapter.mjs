// T05.003: Node built-in tests for ui_msgid_adapter.mjs.
//
// Everything here is an authored double: a tiny DOM, an element that mirrors
// the reviewed ui-text behaviour, and the client API 1 lifecycle (fresh frozen
// descriptors, microtask replay from the current registry, removal while still
// connected). Doubles do not establish browser custom-element reactions; the
// generated fixture (ui_msgid_fixture.py) is where the real class runs.
//
//   node --test tools/renewal/test_ui_msgid_adapter.mjs
//
// Set T05_UITEXT_SOURCE to the pinned UIText.js to also build and inspect a
// fresh fixture (its generated code is read, never executed).

import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

import initialize, { createMsgidAdapter } from './ui_msgid_adapter.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const builder = path.join(here, 'ui_msgid_fixture.py');

// --- DOM double -------------------------------------------------------------

class Node {
    constructor(nodeType) { this.nodeType = nodeType; this.parentNode = null; }
    get isConnected() {
        let node = this;
        while (node.parentNode) node = node.parentNode;
        return node.host ? node.host.isConnected : Boolean(node.isDocument);
    }
}

class Text extends Node {
    constructor(data) { super(3); this.data = String(data); }
    get textContent() { return this.data; }
}

class ParentNode extends Node {
    constructor(nodeType) { super(nodeType); this.childNodes = []; }
    appendChild(child) {
        child.parentNode?.removeChild(child);
        this.childNodes.push(child);
        child.parentNode = this;
        return child;
    }
    removeChild(child) {
        const i = this.childNodes.indexOf(child);
        if (i < 0) throw new Error('not a child');
        this.childNodes.splice(i, 1);
        child.parentNode = null;
        return child;
    }
    replaceChildren(...nodes) {
        for (const child of [...this.childNodes]) this.removeChild(child);
        for (const node of nodes) this.appendChild(node);
    }
    get textContent() { return this.childNodes.map(node => node.textContent).join(''); }
    set textContent(value) {
        this.replaceChildren(...(value === '' ? [] : [new Text(value)]));
    }
    *descendants() {
        for (const child of this.childNodes) {
            if (child.nodeType !== 1) continue;
            yield child;
            yield* child.descendants();
        }
    }
    querySelectorAll(selector) {
        return [...this.descendants()].filter(element => element.localName === selector);
    }
}

class Element extends ParentNode {
    constructor(localName) { super(1); this.localName = localName; this.attributes = new Map(); }
    getAttribute(name) { return this.attributes.has(name) ? this.attributes.get(name) : null; }
    hasAttribute(name) { return this.attributes.has(name); }
    setAttribute(name, value) {
        const old = this.getAttribute(name);
        this.attributes.set(name, String(value));
        this.reaction(name, old, String(value));
    }
    removeAttribute(name) {
        if (!this.attributes.has(name)) return;
        const old = this.getAttribute(name);
        this.attributes.delete(name);
        this.reaction(name, old, null);
    }
    reaction() {}
}

class ShadowRoot extends ParentNode {
    constructor(host) { super(11); this.host = host; }
}

class Document extends ParentNode {
    constructor() { super(9); this.isDocument = true; this.body = this.appendChild(new Element('body')); }
}

// --- ui-text double: the reviewed class behaviour, authored ------------------

function createDb(entries) {
    const table = new Map(Object.entries(entries));
    const calls = [];
    return {
        table, calls,
        getMessage(id, fallback) {
            calls.push(String(id));
            if (!table.has(String(id))) return fallback !== undefined ? fallback : `NO MSG ${id}`;
            return table.get(String(id));
        },
    };
}

class UIText extends Element {
    constructor(db) { super('ui-text'); this.db = db; }
    connected() {
        if (this._initialized) return;
        this._initialized = true;
        const id = this.getAttribute('msg');
        if (id) { const text = this.db.getMessage(id, ''); if (text) this.textContent = text; }
    }
    reaction(name, old, value) {
        if (name === 'msg' && value) { const text = this.db.getMessage(value, ''); if (text) this.textContent = text; }
    }
}

// --- client API 1 double ------------------------------------------------------

function createRuntime() {
    const listeners = new Map();
    const components = new Map();
    const reports = [];
    function emit(event, value) {
        for (const listener of [...(listeners.get(event) || [])]) {
            try { listener(value); } catch (error) { reports.push(error); }
        }
    }
    function scope() {
        const cleanups = new Set();
        let disposed = false;
        const cleanup = fn => {
            let done = false;
            const once = () => { if (done) return; done = true; cleanups.delete(once); fn(); };
            if (disposed) once(); else cleanups.add(once);
            return once;
        };
        const on = (event, listener, { replay = true } = {}) => {
            if (disposed) throw new Error('disposed');
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
        const api = Object.freeze({ version: 1, name: 'ui-msgid', cleanup, on });
        return { api, dispose() { if (disposed) return; disposed = true; for (const fn of [...cleanups].reverse()) fn(); } };
    }
    return {
        scope, reports,
        // Fresh frozen descriptor per append, as the packaged GUIComponent does.
        append(component) {
            const item = Object.freeze({ name: component.name, root: component.root, host: component.host });
            components.set(component, item); emit('ui:append', item);
            return item;
        },
        // Emitted before the host is detached.
        remove(component) {
            const item = components.get(component);
            if (item) { components.delete(component); emit('ui:remove', item); }
        },
        listenerCount: () => [...listeners.values()].reduce((n, set) => n + set.size, 0),
    };
}

const flush = () => new Promise(resolve => setTimeout(resolve, 0));

// A component: host + shadow root, mounted in a document like the client does.
function component(document, name, build) {
    const host = new Element('div');
    const root = new ShadowRoot(host);
    host.shadowRoot = root;
    build(root);
    return { name, host, root, mount() { document.body.appendChild(host); }, unmount() { document.body.removeChild(host); } };
}

function uiText(db, attributes, text) {
    const element = new UIText(db);
    for (const [name, value] of Object.entries(attributes)) element.attributes.set(name, value);
    if (text !== undefined && text !== '') element.appendChild(new Text(text));
    element.connected();
    return element;
}

function setup(entries = { 283: '技能樹', 1317: '任務：「進行中」' }) {
    const document = new Document();
    const db = createDb(entries);
    const runtime = createRuntime();
    return { document, db, runtime };
}

function skillList(env, attributes = { msgid: '283' }, text = 'Skill Tree') {
    let slot, checkbox, button;
    const comp = component(env.document, 'SkillListV2', root => {
        const bar = root.appendChild(new Element('div'));
        button = bar.appendChild(new Element('button'));
        slot = bar.appendChild(uiText(env.db, attributes, text));
        checkbox = root.appendChild(new Element('input'));
        checkbox.checked = true;
    });
    return { comp, slot, checkbox, button };
}

function questList(env, attributes = { msgid: '1317' }) {
    let slot;
    const comp = component(env.document, 'QuestV1', root => { slot = root.appendChild(uiText(env.db, attributes, '')); });
    return { comp, slot };
}

// --- adapter lifecycle --------------------------------------------------------

test('refuses anything but client API 1 before subscribing', () => {
    for (const api of [undefined, null, {}, { version: 2, on() { throw new Error('touched'); } }, { version: '1' }]) {
        assert.throws(() => initialize(null, api), /client API 1/);
    }
    const env = setup();
    const scope = env.runtime.scope();
    assert.equal(initialize({}, scope.api), undefined);
    assert.equal(env.runtime.listenerCount(), 2);
    scope.dispose();
    assert.equal(env.runtime.listenerCount(), 0);
});

test('SkillListV2/283: immediate append sets msg and the real lookup text', async () => {
    const env = setup();
    const scope = env.runtime.scope();
    const adapter = createMsgidAdapter(scope.api);
    const { comp, slot } = skillList(env);
    const original = slot.childNodes[0];
    comp.mount();
    env.runtime.append(comp);
    assert.equal(slot.getAttribute('msg'), '283');
    assert.equal(slot.getAttribute('msgid'), '283');
    assert.equal(slot.textContent, '技能樹');
    assert.deepEqual(env.db.calls, ['283']);
    await flush(); // queued replay of the same component
    assert.deepEqual(env.db.calls, ['283'], 'replay is idempotent');
    assert.equal(adapter.tracked(), 1);
    env.runtime.remove(comp);
    assert.equal(slot.hasAttribute('msg'), false);
    assert.equal(slot.childNodes.length, 1);
    assert.equal(slot.childNodes[0], original, 'fallback text node identity restored');
    assert.equal(slot.textContent, 'Skill Tree');
    assert.equal(adapter.tracked(), 0);
    scope.dispose();
});

test('QuestV1/1317: empty slot receives Chinese punctuation text', () => {
    const env = setup({ 1317: '任務：「進行中」…𠀋' });
    const scope = env.runtime.scope();
    createMsgidAdapter(scope.api);
    const { comp, slot } = questList(env);
    comp.mount();
    env.runtime.append(comp);
    assert.equal(slot.getAttribute('msg'), '1317');
    assert.equal(slot.textContent, '任務：「進行中」…\u{2000b}');
    env.runtime.remove(comp);
    assert.equal(slot.childNodes.length, 0);
    assert.equal(slot.hasAttribute('msg'), false);
    scope.dispose();
});

test('replay alone handles components mounted before initialization', async () => {
    const env = setup();
    const a = skillList(env); const b = questList(env);
    a.comp.mount(); b.comp.mount();
    env.runtime.append(a.comp); env.runtime.append(b.comp);
    const scope = env.runtime.scope();
    createMsgidAdapter(scope.api);
    assert.equal(a.slot.hasAttribute('msg'), false, 'nothing before the queued replay');
    await flush();
    assert.equal(a.slot.textContent, '技能樹');
    assert.equal(b.slot.textContent, '任務：「進行中」');
    scope.dispose();
    assert.equal(a.slot.textContent, 'Skill Tree');
    assert.equal(b.slot.textContent, '');
});

test('existing msg wins, including an empty one', async () => {
    const env = setup();
    const scope = env.runtime.scope();
    createMsgidAdapter(scope.api);
    for (const msg of ['999', '']) {
        const { comp, slot } = skillList(env, { msgid: '283', msg }, 'Kept');
        env.db.calls.length = 0; // the double's connect looked up a non-empty msg
        comp.mount(); env.runtime.append(comp); await flush();
        assert.deepEqual(env.db.calls, []);
        assert.equal(slot.getAttribute('msg'), msg);
        assert.equal(slot.textContent, 'Kept');
        env.runtime.remove(comp);
        assert.equal(slot.getAttribute('msg'), msg, 'removal does not touch a msg it did not write');
    }
    scope.dispose();
});

test('empty, malformed and other ids stay unchanged', async () => {
    const env = setup({ 283: 'x', 1317: 'y', '0283': 'z', 284: 'w' });
    const scope = env.runtime.scope();
    const adapter = createMsgidAdapter(scope.api);
    for (const msgid of ['', ' 283', '283 ', '0283', '283.0', '２８３', '1317', '284', '+283']) {
        const { comp, slot } = skillList(env, { msgid }, 'Fallback');
        comp.mount(); env.runtime.append(comp);
        assert.equal(slot.hasAttribute('msg'), false, JSON.stringify(msgid));
        assert.equal(slot.textContent, 'Fallback');
    }
    const quest = questList(env, { msgid: '283' });
    quest.comp.mount(); env.runtime.append(quest.comp);
    assert.equal(quest.slot.hasAttribute('msg'), false);
    const bare = skillList(env, {}, 'No id');
    bare.comp.mount(); env.runtime.append(bare.comp);
    assert.equal(bare.slot.hasAttribute('msg'), false);
    await flush();
    assert.deepEqual(env.db.calls, []);
    assert.equal(adapter.tracked(), 0);
    scope.dispose();
});

test('components outside the allowlist are ignored', async () => {
    const env = setup();
    const scope = env.runtime.scope();
    createMsgidAdapter(scope.api);
    for (const name of ['SkillList', 'Quest', 'skilllistv2', 'SkillListV2 ', 'constructor', '__proto__', 'toString']) {
        const { comp, slot } = skillList(env);
        comp.name = name;
        comp.mount(); env.runtime.append(comp);
        assert.equal(slot.hasAttribute('msg'), false, name);
    }
    // Malformed descriptors are harmless.
    for (const value of [null, undefined, 1, 'SkillListV2', { name: 'SkillListV2' }, { name: 'SkillListV2', root: {} }]) {
        env.runtime.append({ name: value?.name, root: value?.root });
    }
    await flush();
    assert.equal(env.runtime.reports.length, 0);
    scope.dispose();
});

test('missing or empty messages keep the fallback but are still released', () => {
    for (const entries of [{}, { 283: '' }]) {
        const env = setup(entries);
        const scope = env.runtime.scope();
        const adapter = createMsgidAdapter(scope.api);
        const { comp, slot } = skillList(env);
        const original = slot.childNodes[0];
        comp.mount(); env.runtime.append(comp);
        assert.equal(slot.getAttribute('msg'), '283');
        assert.equal(slot.childNodes[0], original);
        assert.equal(slot.textContent, 'Skill Tree');
        assert.equal(adapter.tracked(), 1);
        env.runtime.remove(comp);
        assert.equal(slot.hasAttribute('msg'), false);
        assert.equal(slot.childNodes[0], original);
        scope.dispose();
    }
});

test('slots with element children are skipped, never flattened', () => {
    const env = setup();
    const scope = env.runtime.scope();
    createMsgidAdapter(scope.api);
    const { comp, slot } = skillList(env, { msgid: '283' }, '');
    const bold = slot.appendChild(new Element('b'));
    comp.mount(); env.runtime.append(comp);
    assert.equal(slot.hasAttribute('msg'), false);
    assert.equal(slot.childNodes[0], bold);
    scope.dispose();
});

test('removal and disposal before the queued replay do nothing further', async () => {
    const env = setup();
    const scope = env.runtime.scope();
    const adapter = createMsgidAdapter(scope.api);
    const { comp, slot } = skillList(env);
    comp.mount();
    env.runtime.append(comp);          // immediate delivery
    env.runtime.remove(comp);          // still connected, before replay
    assert.equal(slot.textContent, 'Skill Tree');
    comp.unmount();
    await flush();                     // replay reads the current registry: empty
    assert.equal(slot.hasAttribute('msg'), false);
    assert.equal(adapter.tracked(), 0);
    scope.dispose();

    const env2 = setup();
    const late = skillList(env2);
    late.comp.mount(); env2.runtime.append(late.comp);
    const scope2 = env2.runtime.scope();
    createMsgidAdapter(scope2.api);
    scope2.dispose();                  // before the queued replay
    await flush();
    assert.equal(late.slot.hasAttribute('msg'), false);
    assert.deepEqual(env2.db.calls, []);
    assert.equal(env2.runtime.listenerCount(), 0);
});

test('detach and reappend with a fresh descriptor re-applies once', async () => {
    const env = setup();
    const scope = env.runtime.scope();
    const adapter = createMsgidAdapter(scope.api);
    const { comp, slot } = skillList(env);
    comp.mount();
    const first = env.runtime.append(comp);
    env.runtime.remove(comp); comp.unmount();
    comp.mount();
    const second = env.runtime.append(comp);
    assert.notEqual(first, second);
    assert.equal(first.root, second.root);
    env.runtime.append(comp);          // repeated append, another fresh descriptor
    await flush();
    assert.equal(slot.textContent, '技能樹');
    assert.deepEqual(env.db.calls, ['283', '283']);
    assert.equal(adapter.tracked(), 1);
    env.runtime.remove(comp);
    assert.equal(slot.textContent, 'Skill Tree');
    scope.dispose();
});

test('different descriptors sharing one root are released separately', () => {
    const env = setup();
    const scope = env.runtime.scope();
    const adapter = createMsgidAdapter(scope.api);
    let skill, quest;
    const shared = component(env.document, 'SkillListV2', root => {
        skill = root.appendChild(uiText(env.db, { msgid: '283' }, 'Skill Tree'));
        quest = root.appendChild(uiText(env.db, { msgid: '1317' }, ''));
    });
    shared.mount();
    const other = { name: 'QuestV1', root: shared.root, host: shared.host };
    env.runtime.append(shared); env.runtime.append(other);
    assert.equal(skill.getAttribute('msg'), '283');
    assert.equal(quest.getAttribute('msg'), '1317');
    assert.equal(adapter.tracked(), 2);
    env.runtime.remove(other);
    assert.equal(quest.hasAttribute('msg'), false);
    assert.equal(skill.getAttribute('msg'), '283', 'the other component keeps its slot');
    env.runtime.remove(shared);
    assert.equal(skill.hasAttribute('msg'), false);
    assert.equal(adapter.tracked(), 0);
    scope.dispose();
});

test('foreign attribute, text and child updates are preserved', () => {
    const cases = {
        'foreign msg': slot => slot.setAttribute('msg', '1318'),
        'foreign msg removal and text': slot => { slot.removeAttribute('msg'); slot.textContent = 'Theirs'; },
        'foreign text': slot => { slot.textContent = 'Theirs'; },
        'foreign child': slot => { slot.appendChild(new Element('i')); },
        'foreign msgid': slot => slot.setAttribute('msgid', '284'),
        'foreign same-text replacement': slot => { slot.textContent = '技能樹'; },
    };
    for (const [label, change] of Object.entries(cases)) {
        const env = setup({ 283: '技能樹', 1318: 'Other' });
        const scope = env.runtime.scope();
        createMsgidAdapter(scope.api);
        const { comp, slot } = skillList(env);
        comp.mount(); env.runtime.append(comp);
        change(slot);
        const msg = slot.getAttribute('msg');
        const nodes = [...slot.childNodes];
        env.runtime.remove(comp);
        assert.deepEqual([...slot.childNodes], nodes, `${label}: children kept`);
        if (msg === '283') assert.equal(slot.hasAttribute('msg'), false, `${label}: own msg removed`);
        else assert.equal(slot.getAttribute('msg'), msg, `${label}: foreign msg kept`);
        scope.dispose();
    }
});

test('a later foreign msg removal is not fought on replay', async () => {
    const env = setup();
    const scope = env.runtime.scope();
    createMsgidAdapter(scope.api);
    const { comp, slot } = skillList(env);
    comp.mount(); env.runtime.append(comp);
    slot.removeAttribute('msg');
    env.runtime.append(comp);
    await flush();
    assert.equal(slot.hasAttribute('msg'), false);
    assert.deepEqual(env.db.calls, ['283']);
    scope.dispose();
});

test('unrelated controls keep identity, value and listeners', () => {
    const env = setup();
    const scope = env.runtime.scope();
    createMsgidAdapter(scope.api);
    const { comp, slot, checkbox, button } = skillList(env);
    const bar = slot.parentNode;
    const siblings = [...bar.childNodes];
    comp.mount(); env.runtime.append(comp);
    assert.deepEqual([...bar.childNodes], siblings);
    assert.equal(comp.root.childNodes[1], checkbox);
    assert.equal(checkbox.checked, true);
    assert.equal(button.attributes.size, 0);
    env.runtime.remove(comp);
    scope.dispose();
    assert.deepEqual([...bar.childNodes], siblings);
    assert.equal(checkbox.checked, true);
});

test('disposal restores, unsubscribes and may run twice', async () => {
    const env = setup();
    const scope = env.runtime.scope();
    const adapter = createMsgidAdapter(scope.api);
    const { comp, slot } = skillList(env);
    comp.mount(); env.runtime.append(comp);
    adapter.dispose();
    adapter.dispose();
    scope.dispose();
    assert.equal(env.runtime.listenerCount(), 0);
    assert.equal(slot.textContent, 'Skill Tree');
    assert.equal(slot.hasAttribute('msg'), false);
    const late = skillList(env);
    late.comp.mount(); env.runtime.append(late.comp);
    await flush();
    assert.equal(late.slot.hasAttribute('msg'), false);
    assert.deepEqual(env.db.calls, ['283']);
    assert.equal(adapter.tracked(), 0);
});

test('a throwing element reaction keeps track of the attribute it set', () => {
    const env = setup();
    const scope = env.runtime.scope();
    const adapter = createMsgidAdapter(scope.api);
    const { comp, slot } = skillList(env);
    slot.db = { getMessage() { throw new Error('table'); } };
    comp.mount(); env.runtime.append(comp);
    assert.equal(slot.getAttribute('msg'), '283');
    assert.equal(adapter.tracked(), 1);
    scope.dispose();
    assert.equal(slot.hasAttribute('msg'), false);
    assert.equal(slot.textContent, 'Skill Tree');
});

test('the adapter source uses no globals, storage, network or observers', () => {
    const source = fs.readFileSync(path.join(here, 'ui_msgid_adapter.mjs'), 'utf8');
    const code = source.replace(/\/\/.*$/gm, '');
    for (const word of ['import ', 'document', 'window', 'globalThis', 'localStorage', 'sessionStorage', 'indexedDB',
        'fetch', 'WebSocket', 'XMLHttpRequest', 'MutationObserver', 'setInterval', 'setTimeout', 'prototype',
        'customElements', 'DBManager', 'innerHTML', 'eval', 'Function(', 'preferences']) {
        assert.equal(code.includes(word), false, word);
    }
});

// --- fixture builder -----------------------------------------------------------

function tempDir() { return fs.mkdtempSync(path.join(fs.realpathSync(here), '.test-temp-')); }
function build(source, output) {
    return spawnSync('python3', ['-I', builder, source, output], { encoding: 'utf8' });
}

test('builder refuses wrong bytes, links, missing input and existing output', () => {
    const dir = tempDir();
    try {
        const wrong = path.join(dir, 'UIText.js');
        fs.writeFileSync(wrong, "import DB from 'DB/DBManager.js';\n");
        let result = build(wrong, path.join(dir, 'out1'));
        assert.notEqual(result.status, 0); assert.match(result.stderr, /size|sha256/);
        assert.equal(fs.existsSync(path.join(dir, 'out1')), false);

        const padded = path.join(dir, 'padded.js');
        fs.writeFileSync(padded, Buffer.alloc(796, 0x20));
        result = build(padded, path.join(dir, 'out2'));
        assert.notEqual(result.status, 0); assert.match(result.stderr, /sha256/);

        const link = path.join(dir, 'link.js');
        fs.symlinkSync(padded, link);
        result = build(link, path.join(dir, 'out3'));
        assert.notEqual(result.status, 0); assert.match(result.stderr, /link/);

        result = build(path.join(dir, 'absent.js'), path.join(dir, 'out4'));
        assert.notEqual(result.status, 0);

        fs.mkdirSync(path.join(dir, 'exists'));
        result = build(padded, path.join(dir, 'exists'));
        assert.notEqual(result.status, 0); assert.match(result.stderr, /exists/);

        fs.symlinkSync(path.join(dir, 'nowhere'), path.join(dir, 'dangling'));
        result = build(padded, path.join(dir, 'dangling'));
        assert.notEqual(result.status, 0); assert.match(result.stderr, /exists/);

        result = spawnSync('python3', ['-I', builder, padded], { encoding: 'utf8' });
        assert.notEqual(result.status, 0);
    } finally {
        fs.rmSync(dir, { recursive: true, force: true });
    }
});

const pinned = process.env.T05_UITEXT_SOURCE;
test('fresh fixture from the pinned UIText (inspected, not executed)', { skip: !pinned && 'T05_UITEXT_SOURCE not set' }, () => {
    const dir = tempDir();
    try {
        const output = path.join(dir, 'fixture');
        const result = build(pinned, output);
        assert.equal(result.status, 0, result.stderr);
        assert.equal(result.stdout.includes(dir), false, 'summary has no absolute paths');
        assert.equal(fs.statSync(output).mode & 0o777, 0o700);
        const sha = file => createHash('sha256').update(fs.readFileSync(path.join(output, file))).digest('hex');
        const provenance = JSON.parse(fs.readFileSync(path.join(output, 'provenance.json'), 'utf8'));
        for (const entry of provenance.files) {
            assert.equal(fs.statSync(path.join(output, entry.name)).mode & 0o777, 0o600, entry.name);
            assert.equal(sha(entry.name), entry.sha256, entry.name);
        }
        const original = fs.readFileSync(pinned);
        const transformed = fs.readFileSync(path.join(output, 'UIText.js'));
        assert.equal(provenance.source.sha256, '8b93dde4d26829fbe5dc9ce18170dbdd7c6f236bd165ec6695556f4564531d8f');
        assert.equal(Buffer.compare(
            Buffer.from(original.toString('latin1').replace("import DB from 'DB/DBManager.js';", "import DB from './db-stub.js';"), 'latin1'),
            transformed), 0, 'only the DB import differs; CRLF preserved');
        assert.equal(transformed.includes('\r\n'), true);
        assert.equal(sha('ui_msgid_adapter.js'),
            createHash('sha256').update(fs.readFileSync(path.join(here, 'ui_msgid_adapter.mjs'))).digest('hex'));
        const html = fs.readFileSync(path.join(output, 'index.html'), 'utf8');
        assert.match(html, /default-src 'none'/);
        assert.match(html, /script-src 'self'/);
        assert.match(html, /NOT RUN/);
        assert.match(html, /img-src 'none'/);
        assert.doesNotMatch(html, /rel="icon"|data:image/);
        assert.equal('favicon' in provenance, false);
        for (const file of fs.readdirSync(output).filter(name => name.endsWith('.js'))) {
            const text = fs.readFileSync(path.join(output, file), 'utf8');
            for (const spec of text.matchAll(/^\s*import\s[^'"]*['"]([^'"]+)['"]/gm)) {
                assert.match(spec[1], /^\.\/[A-Za-z_-]+\.js$/, `${file} imports ${spec[1]}`);
            }
            assert.equal(/https?:|wss?:|fetch\(|WebSocket|localStorage|sessionStorage|Online\.js/.test(text), false, file);
        }
    } finally {
        fs.rmSync(dir, { recursive: true, force: true });
    }
});

// --- private correction regressions: authored code only, no UIText execution ---

function authoredLiteral(name) {
    const source = fs.readFileSync(builder, 'utf8');
    const prefix = name + " = r'''";
    const start = source.indexOf(prefix);
    assert.notEqual(start, -1, name);
    assert.equal(source.indexOf(prefix, start + prefix.length), -1, 'unique literal');
    const end = source.indexOf("\n'''", start + prefix.length);
    assert.notEqual(end, -1, name);
    return source.slice(start + prefix.length, end);
}

function bootDouble() {
    const windowListeners = new Map();
    const documentListeners = new Map();
    const elements = new Map(['status', 'errors', 'notes'].map(id => [id, { dataset: {}, textContent: '' }]));
    const window = { addEventListener(name, listener) { windowListeners.set(name, listener); } };
    const document = {
        getElementById(id) { return elements.get(id) || null; },
        addEventListener(name, listener) { documentListeners.set(name, listener); },
    };
    // Only the authored boot literal executes under inert element/event doubles.
    // No generated harness module, pinned UIText, browser, storage or network executes.
    vm.runInNewContext(authoredLiteral('BOOT'), { window, document, setTimeout() { return 1; } });
    return { boot: window.__t05Boot, windowListeners, documentListeners, elements };
}

test('authored API double makes append, replay and cleanup errors visible', async () => {
    const literal = authoredLiteral('API_DOUBLE');
    const { createRuntime: fixtureRuntime } = await import('data:text/javascript;base64,' + Buffer.from(literal).toString('base64'));
    assert.throws(() => fixtureRuntime(), /visible error sink/);
    const state = bootDouble();
    const onError = error => state.boot.fail('API double: ' + error.message);
    const immediate = fixtureRuntime(onError);
    const a = immediate.scope();
    a.api.on('ui:append', () => { throw new Error('append sentinel'); }, { replay: false });
    immediate.append({ name: 'Other', root: {}, host: {} });
    assert.equal(state.boot.errors.length, 1);
    assert.equal(state.elements.get('status').dataset.state, 'fail');

    const replay = fixtureRuntime(onError);
    replay.append({ name: 'Other', root: {}, host: {} });
    const b = replay.scope();
    b.api.on('ui:append', () => { throw new Error('replay sentinel'); });
    await flush();
    assert.equal(state.boot.errors.length, 2);
    b.api.cleanup(() => { throw new Error('cleanup sentinel'); });
    b.dispose();
    assert.equal(state.boot.errors.length, 3);
    assert.match(state.elements.get('errors').textContent, /append sentinel/);
    assert.match(state.elements.get('errors').textContent, /replay sentinel/);
    assert.match(state.elements.get('errors').textContent, /cleanup sentinel/);
    a.dispose();
    assert.equal(immediate.reports.length, 1);
    assert.equal(replay.reports.length, 2);

    const harness = authoredLiteral('HARNESS');
    const constructors = [...harness.matchAll(/\bcreateRuntime\(([^)]*)\)/g)];
    assert.equal(constructors.length, 2);
    assert.equal(constructors.every(match => match[1] === 'onApiError'), true, 'every harness runtime has the visible sink');
    assert.match(harness, /boot\.errors\.length === 0/);
});

test('authored boot treats every CSP violation as failure, including favicon-shaped URLs', () => {
    const state = bootDouble();
    const listener = state.documentListeners.get('securitypolicyviolation');
    assert.equal(typeof listener, 'function');
    const urls = ['https://outside.invalid/favicon.ico', 'http://127.0.0.1:8793/favicon.ico', 'data:blocked-sentinel'];
    for (const blockedURI of urls) listener({ effectiveDirective: 'img-src', blockedURI });
    assert.equal(state.boot.errors.length, urls.length);
    assert.equal(state.elements.get('status').dataset.state, 'fail');
    assert.match(state.elements.get('errors').textContent, /outside\.invalid/);
});

test('builder rejects linked ancestors for source and output before creating files', () => {
    const dir = tempDir();
    try {
        const real = path.join(dir, 'real');
        const nested = path.join(real, 'nested');
        fs.mkdirSync(nested, { recursive: true });
        const padded = path.join(nested, 'UIText.js');
        fs.writeFileSync(padded, Buffer.alloc(796, 0x20));
        const alias = path.join(dir, 'alias');
        fs.symlinkSync(real, alias, 'dir');
        const sourceAlias = path.join(alias, 'nested', 'UIText.js');
        let result = build(sourceAlias, path.join(dir, 'output'));
        assert.notEqual(result.status, 0);
        assert.match(result.stderr, /symbolic link component/);
        assert.equal(fs.existsSync(path.join(dir, 'output')), false);
        result = build(padded, path.join(alias, 'nested', 'output'));
        assert.notEqual(result.status, 0);
        assert.match(result.stderr, /symbolic link component/);
        assert.equal(fs.existsSync(path.join(nested, 'output')), false);
    } finally { fs.rmSync(dir, { recursive: true, force: true }); }
});

test('source exact-size check precedes reads, and reads remain capped on growth', () => {
    const dir = tempDir();
    try {
        const oversized = path.join(dir, 'oversized.js');
        fs.writeFileSync(oversized, Buffer.alloc(797, 0x20));
        const exact = path.join(dir, 'exact.js');
        fs.writeFileSync(exact, Buffer.alloc(796, 0x20));
        const probe = String.raw`
import importlib.util, sys
spec = importlib.util.spec_from_file_location('authored_builder', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
reads = []
def never_read(fd, count):
    reads.append(count)
    raise AssertionError('oversized source reached read')
module.os.read = never_read
try:
    module.read_regular(sys.argv[2], 'UITEXT_SOURCE', expected_size=796)
except module.Refused:
    pass
else:
    raise AssertionError('oversized source accepted')
assert reads == []
def growing(fd, count):
    reads.append(count)
    return b'x' * count
module.os.read = growing
try:
    module.read_regular(sys.argv[3], 'UITEXT_SOURCE', expected_size=796)
except module.Refused:
    pass
else:
    raise AssertionError('unbounded growth accepted')
assert reads == [797], reads
print('bounded authored-reader checks passed')
`;
        const result = spawnSync('python3', ['-I', '-B', '-c', probe, builder, oversized, exact], { encoding: 'utf8', timeout: 10000 });
        assert.equal(result.status, 0, result.stderr);
        assert.match(result.stdout, /bounded authored-reader checks passed/);
        assert.equal(fs.existsSync(path.join(dir, 'output')), false);
    } finally { fs.rmSync(dir, { recursive: true, force: true }); }
});
