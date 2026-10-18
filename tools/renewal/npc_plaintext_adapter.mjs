// T05.004: client API 1 core that translates exact plain-text NPC lines.
//
// The packaged engine appends NpcBox/NpcMenu *before* setText/setMenu, so an
// append-only pass never sees ordinary dialogue. This core owns each
// allowlisted component's stable root, observes only its first `.content`
// node with a native MutationObserver, and rewrites the data of plain Text
// children of direct row DIVs whose logical lines are exact own keys of a
// caller-supplied dictionary. Misses, unsupported lines and every other node
// are left alone. Dictionary loading is a future wrapper's job: this module
// fetches, stores and caches nothing. See NPC_PLAINTEXT_ADAPTER.md.

const COMPONENTS = new Set(['NpcBox', 'NpcMenu']);
export const LIMITS = Object.freeze({
    roots: 8,          // active owned component roots
    contentNodes: 256, // direct content.childNodes per scan, every node type
    rowNodes: 32,      // childNodes per row
    textUnits: 8192,   // UTF-16 units per input Text, target and output Text
    lines: 256,        // logical lines per Text (CRLF counts once)
});
const ELEMENT = 1;
const TEXT = 3;
const MAX_ANCESTORS = 64;
const OBSERVE = Object.freeze({ childList: true, characterData: true, subtree: true });
// Colour codes, angle brackets, numbered placeholders and U+FFFD are formatting
// or damage this core does not reproduce; lone surrogates are not scalar text.
const MARKUP = /\^[0-9A-Fa-f]{6}|[<>�]|\{\d+\}/;
const LONE_SURROGATE = /[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/;
const BLANK = /^\s*$/;
const NEWLINE = /[\r\n]/;

export const createCounts = () => ({ hits: 0, misses: 0, unsupported: 0, overflow: 0, errors: 0, stale: 0, ignored: 0 });
function bump(counts, name) {
    if (counts[name] < Number.MAX_SAFE_INTEGER) counts[name]++;
}

// A borrowed JSON object: ordinary Object or null prototype, not an array.
function plainObject(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
    const proto = Object.getPrototypeOf(value);
    return proto === Object.prototype || proto === null;
}

// A function-valued own `then` makes it a thenable, never parsed JSON.
function jsonDictionary(value) {
    return plainObject(value) && typeof ownData(value, 'then') !== 'function';
}

function ownData(object, key) {
    if (!plainObject(object)) return undefined;
    const entry = Object.getOwnPropertyDescriptor(object, key);
    return entry && 'value' in entry ? entry.value : undefined;
}

const unsupported = text => MARKUP.test(text) || LONE_SURROGATE.test(text);

// One logical line -> its target, or null to keep the line exactly.
function translateLine(dictionary, line, counts) {
    if (BLANK.test(line)) return null;
    if (unsupported(line)) { bump(counts, 'unsupported'); return null; }
    // Own data properties only: inherited names and accessors never match.
    const entry = Object.getOwnPropertyDescriptor(dictionary, line);
    if (!entry) { bump(counts, 'misses'); return null; }
    const target = entry.value;
    if (!('value' in entry) || typeof target !== 'string') { bump(counts, 'unsupported'); return null; }
    if (target.length > LIMITS.textUnits) { bump(counts, 'overflow'); return null; }
    if (BLANK.test(target) || NEWLINE.test(target) || unsupported(target)) { bump(counts, 'unsupported'); return null; }
    bump(counts, 'hits');
    return target;
}

// Whole Text data -> translated data, or null to leave the node untouched.
// Delimiters (CRLF/CR/LF) and untranslated lines are kept byte for byte.
export function translateText(dictionary, data, counts = createCounts()) {
    if (typeof data !== 'string' || !plainObject(dictionary)) return null;
    if (data.length > LIMITS.textUnits) { bump(counts, 'overflow'); return null; }
    let lines = 1;
    for (let i = 0; i < data.length; i++) {
        const c = data.charCodeAt(i);
        if (c !== 13 && c !== 10) continue;
        if (c === 13 && data.charCodeAt(i + 1) === 10) i++;
        if (++lines > LIMITS.lines) { bump(counts, 'overflow'); return null; }
    }
    let output = '';
    let changed = false;
    for (let start = 0, i = 0; i <= data.length; i++) {
        const c = i < data.length ? data.charCodeAt(i) : -1;
        if (c !== 13 && c !== 10 && c !== -1) continue;
        const end = c === -1 ? i : c === 13 && data.charCodeAt(i + 1) === 10 ? i + 2 : i + 1;
        const line = data.slice(start, i);
        const delimiter = data.slice(i, end);
        const target = translateLine(dictionary, line, counts);
        const piece = target === null ? line : target;
        // Too long once assembled: keep the whole original Text.
        if (output.length + piece.length + delimiter.length > LIMITS.textUnits) { bump(counts, 'overflow'); return null; }
        output += piece + delimiter;
        if (piece !== line) changed = true;
        if (c === -1) break;
        start = end;
        i = end - 1;
    }
    return changed ? output : null;
}

function selectContent(root) {
    const content = root.querySelector('.content');
    return content && content.nodeType === ELEMENT ? content : null;
}

function parseDescriptor(descriptor) {
    if (!descriptor || typeof descriptor !== 'object') return null;
    const { name, root, host } = descriptor;
    if (typeof name !== 'string' || !COMPONENTS.has(name)) return null;
    if (!root || typeof root !== 'object' || typeof root.querySelector !== 'function') return null;
    if (!host || (typeof host !== 'object' && typeof host !== 'function')) return null;
    return { name, root, host };
}

export default function initialize(parameters, api) {
    if (!api || typeof api !== 'object' || api.version !== 1) throw new TypeError('npc-plaintext requires client API 1');
    if (typeof api.on !== 'function' || typeof api.cleanup !== 'function') throw new TypeError('npc-plaintext requires api.on and api.cleanup');
    const Observer = globalThis.MutationObserver;
    if (typeof Observer !== 'function') throw new TypeError('npc-plaintext requires MutationObserver');

    const ready = ownData(parameters, 'dictionaryReady');
    let dictionary = null;
    let state;
    if (ready instanceof Promise) state = 'loading';
    else if (jsonDictionary(ready)) { state = 'ready'; dictionary = ready; }
    else state = 'failed';

    const counts = createCounts();
    // root -> owner. An owner is one ownership generation of one root; it is
    // replaced (never mutated back to life) on removal or new content.
    const owners = new Map();
    const offs = [];

    const current = owner => state === 'ready' && !owner.retired && owners.get(owner.root) === owner;
    const contentCurrent = owner => selectContent(owner.root) === owner.content;

    function stopObserving(owner) {
        const observer = owner.observer;
        owner.observer = null;
        if (observer) observer.disconnect();
    }

    // A content-only observer cannot see its own content being replaced; the
    // next supported trigger notices and stops using it.
    function retire(owner) {
        owner.retired = true;
        stopObserving(owner);
        bump(counts, 'stale');
    }

    function release(owner) {
        if (owners.get(owner.root) === owner) owners.delete(owner.root);
        owner.retired = true;
        stopObserving(owner);
        owner.root = owner.host = owner.content = null;
        owner.memo = null;
    }

    function adopt(descriptor, content) {
        const owner = {
            name: descriptor.name, root: descriptor.root, host: descriptor.host, content,
            observer: null, retired: false,
            // Text -> the data this core last wrote there. Weak, so replaced
            // rows are not retained; whole-Text comparison only.
            memo: new WeakMap(),
        };
        owners.set(descriptor.root, owner);
        return owner;
    }

    function editable(owner, row) {
        if (row.isContentEditable === true) return true;
        let node = row;
        for (let depth = 0; node && node !== owner.root && depth < MAX_ANCESTORS; depth++, node = node.parentNode) {
            if (node.nodeType === ELEMENT && node.hasAttribute('contenteditable')) return true;
        }
        return node !== owner.root;
    }

    // 'ok', 'overflow' or 'skip'. Called again before every write.
    function rowStatus(owner, row) {
        if (!row || row.nodeType !== ELEMENT || row.localName !== 'div' || row.parentNode !== owner.content) return 'skip';
        if (owner.name === 'NpcMenu' && !row.hasAttribute('data-index')) return 'skip';
        const children = row.childNodes;
        if (children.length > LIMITS.rowNodes) return 'overflow';
        for (let i = 0; i < children.length; i++) if (children[i].nodeType !== TEXT) return 'skip';
        return editable(owner, row) ? 'skip' : 'ok';
    }

    function writable(owner, row, text, data) {
        return current(owner) && contentCurrent(owner) && row.parentNode === owner.content
            && text.parentNode === row && text.data === data && rowStatus(owner, row) === 'ok';
    }

    function translateNode(owner, row, text) {
        const data = text.data;
        if (typeof data !== 'string' || owner.memo.get(text) === data) return;
        const output = translateText(dictionary, data, counts);
        if (output === null) return;
        if (!writable(owner, row, text, data)) { bump(counts, 'stale'); return; }
        text.data = output;
        owner.memo.set(text, output);
    }

    function scan(owner) {
        if (!current(owner)) return;
        if (!contentCurrent(owner)) { retire(owner); return; }
        const nodes = owner.content.childNodes;
        if (nodes.length > LIMITS.contentNodes) { bump(counts, 'overflow'); return; }
        for (const row of Array.from(nodes)) {
            if (!current(owner)) return;
            const status = rowStatus(owner, row);
            if (status === 'overflow') { bump(counts, 'overflow'); continue; }
            if (status !== 'ok') {
                if (row.nodeType === ELEMENT) bump(counts, 'unsupported');
                continue;
            }
            for (const text of Array.from(row.childNodes)) translateNode(owner, row, text);
        }
    }

    function guarded(fn) {
        try { fn(); } catch { bump(counts, 'errors'); }
    }

    function watch(owner) {
        if (owner.observer || !current(owner)) return;
        const observer = new Observer(() => {
            if (owner.observer !== observer || !current(owner)) { observer.disconnect(); return; }
            guarded(() => scan(owner));
        });
        owner.observer = observer;
        observer.observe(owner.content, OBSERVE);
    }

    function append(descriptor) {
        if (state === 'disposed' || state === 'failed') return;
        const parsed = parseDescriptor(descriptor);
        if (!parsed) { bump(counts, 'ignored'); return; }
        guarded(() => {
            let owner = owners.get(parsed.root);
            if (owner && (owner.name !== parsed.name || owner.host !== parsed.host)) { bump(counts, 'ignored'); return; }
            if (!owner && owners.size >= LIMITS.roots) { bump(counts, 'overflow'); return; }
            const content = selectContent(parsed.root);
            if (owner && (owner.retired || content !== owner.content)) {
                // Only a fresh append may adopt new content, as a new generation.
                if (!owner.retired) retire(owner);
                release(owner);
                owner = null;
            }
            if (!content) { bump(counts, 'ignored'); return; }
            if (!owner) owner = adopt(parsed, content);
            if (state !== 'ready') return;
            watch(owner);
            scan(owner);
        });
    }

    function remove(descriptor) {
        if (state === 'disposed') return;
        const parsed = parseDescriptor(descriptor);
        const owner = parsed && owners.get(parsed.root);
        if (!owner || owner.name !== parsed.name || owner.host !== parsed.host) return;
        release(owner);
    }

    function unsubscribe() {
        for (const off of offs.splice(0)) {
            try { if (typeof off === 'function') off(); } catch { bump(counts, 'errors'); }
        }
    }

    function releaseAll() {
        for (const owner of [...owners.values()]) release(owner);
        owners.clear();
    }

    function fail() {
        state = 'failed';
        dictionary = null;
        releaseAll();
        unsubscribe();
    }

    function settle(value) {
        if (state !== 'loading') return;
        if (!jsonDictionary(value)) { fail(); return; }
        dictionary = value;
        state = 'ready';
        // Foreign text written while loading is ordinary current input.
        for (const owner of [...owners.values()]) {
            guarded(() => {
                if (!contentCurrent(owner)) { retire(owner); return; }
                watch(owner);
                scan(owner);
            });
        }
    }

    function dispose() {
        if (state === 'disposed') return;
        state = 'disposed';
        dictionary = null;
        unsubscribe();
        releaseAll();
    }

    const diagnostics = () => Object.freeze({ state, activeRoots: owners.size, ...counts });
    const handle = Object.freeze({ dispose, diagnostics });

    // Registered before any subscription, so a loader that never adopts the
    // returned handle (or adopts it after the scope is gone) still cleans up.
    api.cleanup(dispose);
    if (state === 'disposed') return handle;
    if (state !== 'failed') {
        try {
            offs.push(api.on('ui:append', append, { replay: true }));
            offs.push(api.on('ui:remove', remove, { replay: false }));
        } catch (error) {
            dispose();
            throw error;
        }
    }
    if (state === 'loading') {
        Promise.prototype.then.call(ready,
            value => guarded(() => settle(value)),
            () => guarded(() => { if (state === 'loading') fail(); }));
    }
    return handle;
}
