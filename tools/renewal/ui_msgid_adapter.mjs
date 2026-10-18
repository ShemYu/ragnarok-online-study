// T05.003: client API 1 adapter for the two packaged <ui-text msgid> sites.
//
// The packaged ui-text element looks up and observes only `msg`; SkillListV2
// and QuestV1 write their title id as `msgid`, so it never reaches the lookup.
// This sets `msg` from the allowlisted `msgid` through the element's ordinary
// observed-attribute reaction, and nothing else. See UI_MSGID_ADAPTER.md.

// Component name -> the one message id its title slot carries.
const TARGETS = new Map([
    ['SkillListV2', '283'],
    ['QuestV1', '1317'],
]);
const TEXT_NODE = 3;

// A slot is eligible only while it is still exactly what the template wrote:
// the allowlisted msgid, no msg at all (an existing msg, even empty, wins) and
// text-only content, so a control nested in it is never replaced.
function eligible(element, id) {
    if (element.localName !== 'ui-text') return false;
    if (element.getAttribute('msgid') !== id || element.hasAttribute('msg')) return false;
    return [...element.childNodes].every(node => node.nodeType === TEXT_NODE);
}

const sameNodes = (a, b) => a.length === b.length && a.every((node, i) => node === b[i]);

export function createMsgidAdapter(api) {
    if (!api || api.version !== 1) throw new Error('ui-msgid adapter requires client API 1');
    // root -> (component name -> (element -> slot)). Keyed by the component's
    // stable root: every append hands over a freshly allocated descriptor.
    const roots = new Map();
    let disposed = false;

    // Returns the slot only when msg was observably set to the id. A failing
    // element reaction does not lose track of an attribute that did change.
    function apply(element, id) {
        const before = [...element.childNodes];
        try { element.setAttribute('msg', id); } catch { /* checked below */ }
        if (element.getAttribute('msg') !== id) return null;
        return {
            id,
            before,
            beforeData: before.map(node => node.data),
            fallback: before.map(node => node.data).join(''),
            after: [...element.childNodes],
            afterText: element.textContent,
        };
    }

    // Undo only what is still observably this adapter's: the msg value it
    // wrote, and the lookup's text while the children, text and source msgid
    // are exactly as it left them. Later foreign changes are kept.
    function restore(element, slot) {
        if (element.getAttribute('msg') === slot.id) element.removeAttribute('msg');
        if (sameNodes(slot.after, slot.before)) return;
        if (element.getAttribute('msgid') !== slot.id) return;
        if (!sameNodes([...element.childNodes], slot.after) || element.textContent !== slot.afterText) return;
        const reusable = slot.before.every((node, i) => node.parentNode === null && node.data === slot.beforeData[i]);
        if (reusable) element.replaceChildren(...slot.before);
        else element.textContent = slot.fallback;
    }

    function release(slots) {
        for (const [element, slot] of slots) {
            try { restore(element, slot); } catch { /* keep releasing the rest */ }
        }
        slots.clear();
    }

    function append(descriptor) {
        if (disposed || !descriptor || typeof descriptor !== 'object') return;
        const { name, root } = descriptor;
        const id = typeof name === 'string' ? TARGETS.get(name) : undefined;
        if (!id || !root || typeof root.querySelectorAll !== 'function') return;
        let byName = roots.get(root);
        if (!byName) roots.set(root, byName = new Map());
        let slots = byName.get(name);
        if (!slots) byName.set(name, slots = new Map());
        for (const element of root.querySelectorAll('ui-text')) {
            // Already handled for this mount: never re-apply over a foreign change.
            if (slots.has(element) || !eligible(element, id)) continue;
            const slot = apply(element, id);
            if (slot) slots.set(element, slot);
        }
        if (!slots.size) byName.delete(name);
        if (!byName.size) roots.delete(root);
    }

    // The client emits ui:remove before detaching, so restoration happens
    // while the elements are still connected. A later append re-applies.
    function remove(descriptor) {
        if (disposed || !descriptor || typeof descriptor !== 'object') return;
        const byName = roots.get(descriptor.root);
        const slots = byName?.get(descriptor.name);
        if (!slots) return;
        release(slots);
        byName.delete(descriptor.name);
        if (!byName.size) roots.delete(descriptor.root);
    }

    const offAppend = api.on('ui:append', append, { replay: true });
    const offRemove = api.on('ui:remove', remove, { replay: false });

    function dispose() {
        if (disposed) return;
        disposed = true;
        offAppend();
        offRemove();
        for (const byName of roots.values()) for (const slots of byName.values()) release(slots);
        roots.clear();
    }
    api.cleanup(dispose);

    return Object.freeze({
        dispose,
        // Owned slot count, for tests: zero after every removal or disposal.
        tracked: () => [...roots.values()].reduce((sum, byName) =>
            sum + [...byName.values()].reduce((n, slots) => n + slots.size, 0), 0),
    });
}

// Plugin entry: module.default(parameters, api). Cleanup is registered with
// api.cleanup, so nothing is returned for the loader to register twice.
export default function initialize(parameters, api) {
    createMsgidAdapter(api);
}
