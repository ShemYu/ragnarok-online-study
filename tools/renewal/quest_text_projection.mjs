// T10.004: pure projection of existing quest text from T10.002 typed records.
// No codec, I/O, or clue search. Root supplies decode(Uint8Array, charset) and
// sha256(Uint8Array). Row-table depth 1; a table nested 32 levels is accepted.

export class ProjectionError extends Error {
    constructor(code, message) {
        super(message);
        this.name = "ProjectionError";
        this.code = code;
    }
}

const INPUT_LIMIT = 1024 * 1024;
const RESULT_LIMIT = 16 * 1024 * 1024;
const STRING_LIMIT = 256 * 1024;
const RAW_LIMIT = 64 * 1024;
const MAX_MATCHES = 256;
const MAX_FIELDS = 4096;
const MAX_TABLE_DEPTH = 32;
const MAX_JSON_DEPTH = 2048;
const SCHEMA = "quest-text-projection-1";
const NEG_ZERO = "0000000000000080";
const FROZEN_CLUES = Object.freeze([
    "ch1_",
    "ygg_roots",
    "ygg_fruit",
    "ygg_edge",
    "mu_fild01",
    "prt_fild05",
    "pay_fild01",
]);
const FIELD_HEX = Object.freeze({
    Title: "5469746c65",
    Summary: "53756d6d617279",
    Description: "4465736372697074696f6e",
    IconName: "49636f6e4e616d65",
    NpcSpr: "4e7063537072",
    NpcNavi: "4e70634e617669",
});
const encoder = new TextEncoder();

function refuse(code, detail) {
    throw new ProjectionError(code, code + ": " + detail);
}

function jsonUtf8Bytes(value) {
    return encoder.encode(JSON.stringify(value)).length;
}

function addBudget(budget, n) {
    budget.n += n;
    if (budget.n > INPUT_LIMIT) refuse("limit", "input");
}

function measureString(budget, text) {
    addBudget(budget, encoder.encode(JSON.stringify(text)).length);
}

function measureNumber(budget, value) {
    addBudget(budget, encoder.encode(JSON.stringify(value)).length);
}

function assertArrayShape(arr) {
    if (Object.getPrototypeOf(arr) !== Array.prototype) refuse("input", "shape");
    if (Object.getOwnPropertySymbols(arr).length !== 0) refuse("input", "shape");
    const lenDesc = Object.getOwnPropertyDescriptor(arr, "length");
    if (!lenDesc || !Object.prototype.hasOwnProperty.call(lenDesc, "value")) refuse("input", "shape");
    const len = lenDesc.value;
    if (typeof len !== "number" || !Number.isInteger(len) || len < 0) refuse("input", "shape");
    const names = Object.getOwnPropertyNames(arr);
    const seen = new Set();
    for (let i = 0; i < names.length; i++) {
        const name = names[i];
        if (name === "length") continue;
        if (!/^(0|[1-9][0-9]*)$/.test(name)) refuse("input", "shape");
        const idx = Number(name);
        if (!Number.isSafeInteger(idx) || idx < 0 || idx >= len) refuse("input", "shape");
        const desc = Object.getOwnPropertyDescriptor(arr, name);
        if (!desc || !Object.prototype.hasOwnProperty.call(desc, "value")) refuse("input", "shape");
        if (desc.get || desc.set || !desc.enumerable) refuse("input", "shape");
        if (desc.value === undefined || typeof desc.value === "function") refuse("input", "shape");
        seen.add(idx);
    }
    if (seen.size !== len) refuse("input", "shape");
    return len;
}

function assertObjectShape(obj) {
    if (Object.getPrototypeOf(obj) !== Object.prototype) refuse("input", "shape");
    if (Object.getOwnPropertySymbols(obj).length !== 0) refuse("input", "shape");
    const names = Object.getOwnPropertyNames(obj);
    for (let i = 0; i < names.length; i++) {
        const name = names[i];
        if (name === "toJSON") refuse("input", "shape");
        const desc = Object.getOwnPropertyDescriptor(obj, name);
        if (!desc || !Object.prototype.hasOwnProperty.call(desc, "value")) refuse("input", "shape");
        if (desc.get || desc.set || !desc.enumerable) refuse("input", "shape");
        if (desc.value === undefined || typeof desc.value === "function") refuse("input", "shape");
    }
}

function measure(value, stack, budget, depth) {
    if (depth > MAX_JSON_DEPTH) refuse("limit", "nesting");
    if (value === null) {
        addBudget(budget, 4);
        return;
    }
    const kind = typeof value;
    if (kind === "boolean") {
        addBudget(budget, value ? 4 : 5);
        return;
    }
    if (kind === "number") {
        if (!Number.isFinite(value)) refuse("input", "shape");
        measureNumber(budget, value);
        return;
    }
    if (kind === "string") {
        measureString(budget, value);
        return;
    }
    if (kind !== "object") refuse("input", "shape");
    if (stack.has(value)) refuse("input", "cycle");
    if (Array.isArray(value)) {
        const len = assertArrayShape(value);
        stack.add(value);
        addBudget(budget, 1);
        for (let i = 0; i < len; i++) {
            if (i) addBudget(budget, 1);
            const desc = Object.getOwnPropertyDescriptor(value, String(i));
            measure(desc.value, stack, budget, depth + 1);
        }
        addBudget(budget, 1);
        stack.delete(value);
        return;
    }
    assertObjectShape(value);
    stack.add(value);
    addBudget(budget, 1);
    const keys = Object.keys(value);
    for (let i = 0; i < keys.length; i++) {
        if (i) addBudget(budget, 1);
        measureString(budget, keys[i]);
        addBudget(budget, 1);
        const desc = Object.getOwnPropertyDescriptor(value, keys[i]);
        measure(desc.value, stack, budget, depth + 1);
    }
    addBudget(budget, 1);
    stack.delete(value);
}

function assertPlainAndSized(input) {
    const budget = { n: 0 };
    measure(input, new Set(), budget, 0);
}

function exactKeys(obj, expected) {
    const keys = Object.keys(obj);
    if (keys.length !== expected.length) refuse("input", "shape");
    const seen = new Set(keys);
    if (seen.size !== expected.length) refuse("input", "shape");
    for (let i = 0; i < expected.length; i++) {
        if (!seen.has(expected[i])) refuse("input", "shape");
    }
}

function isEvenHex(text, exact) {
    if (typeof text !== "string") return false;
    if (exact == null) {
        if (text.length % 2 !== 0) return false;
    } else if (text.length !== exact) {
        return false;
    }
    return /^[0-9a-f]*$/.test(text);
}

function finiteLittleEndian(hex) {
    const bytes = new Uint8Array(8);
    for (let i = 0; i < 8; i++) bytes[i] = Number.parseInt(hex.slice(i * 2, i * 2 + 2), 16);
    return Number.isFinite(new DataView(bytes.buffer).getFloat64(0, true));
}

function validateTyped(node, tableDepth, asKey) {
    if (!Array.isArray(node) || node.length === 0 || typeof node[0] !== "string") refuse("input", "typed");
    const tag = node[0];
    if (tag === "nil") {
        if (asKey || node.length !== 1) refuse("input", "typed");
        return;
    }
    if (tag === "bool") {
        if (node.length !== 2 || typeof node[1] !== "boolean") refuse("input", "typed");
        return;
    }
    if (tag === "number") {
        if (node.length !== 2 || !isEvenHex(node[1], 16) || !finiteLittleEndian(node[1])) refuse("input", "typed");
        if (asKey && node[1] === NEG_ZERO) refuse("input", "typed");
        return;
    }
    if (tag === "bytes") {
        if (node.length !== 2 || !isEvenHex(node[1], null)) refuse("input", "typed");
        return;
    }
    if (tag === "table") {
        if (asKey || node.length !== 2 || !Array.isArray(node[1])) refuse("input", "typed");
        const depth = tableDepth + 1;
        if (depth > MAX_TABLE_DEPTH) refuse("limit", "depth");
        let previous = null;
        const entries = node[1];
        for (let i = 0; i < entries.length; i++) {
            const entry = entries[i];
            if (!Array.isArray(entry) || entry.length !== 2) refuse("input", "typed");
            validateTyped(entry[0], depth, true);
            const canon = JSON.stringify(entry[0]);
            if (previous !== null && canon <= previous) refuse("input", "order");
            previous = canon;
            validateTyped(entry[1], depth, false);
        }
        return;
    }
    refuse("input", "typed");
}

function hexToBytes(hex) {
    const out = new Uint8Array(hex.length / 2);
    for (let i = 0; i < out.length; i++) out[i] = Number.parseInt(hex.slice(i * 2, i * 2 + 2), 16);
    return out;
}

function validateHit(hit) {
    if (hit === null || typeof hit !== "object" || Array.isArray(hit)) refuse("input", "hit");
    exactKeys(hit, ["path", "value_hex", "clue", "offsets"]);
    if (!Array.isArray(hit.path)) refuse("input", "hit");
    for (let i = 0; i < hit.path.length; i++) validateTyped(hit.path[i], 0, true);
    if (typeof hit.clue !== "string" || FROZEN_CLUES.indexOf(hit.clue) < 0) refuse("input", "hit");
    if (!isEvenHex(hit.value_hex, null)) refuse("input", "hit");
    const byteLength = hit.value_hex.length / 2;
    if (!Array.isArray(hit.offsets) || hit.offsets.length === 0) refuse("input", "hit");
    let previous = -1;
    for (let i = 0; i < hit.offsets.length; i++) {
        const offset = hit.offsets[i];
        if (typeof offset !== "number" || !Number.isInteger(offset) || Object.is(offset, -0)) refuse("input", "hit");
        if (offset < 0 || offset >= byteLength || offset <= previous) refuse("input", "hit");
        previous = offset;
    }
}

function validateClues(clues, hits) {
    if (!Array.isArray(clues) || clues.length === 0) refuse("input", "clues");
    let last = -1;
    for (let i = 0; i < clues.length; i++) {
        const idx = FROZEN_CLUES.indexOf(clues[i]);
        if (typeof clues[i] !== "string" || idx < 0 || idx <= last) refuse("input", "clues");
        last = idx;
    }
    const present = new Set();
    for (let i = 0; i < hits.length; i++) present.add(hits[i].clue);
    const expected = [];
    for (let i = 0; i < FROZEN_CLUES.length; i++) {
        if (present.has(FROZEN_CLUES[i])) expected.push(FROZEN_CLUES[i]);
    }
    if (expected.length !== clues.length) refuse("input", "clues");
    for (let i = 0; i < expected.length; i++) {
        if (expected[i] !== clues[i]) refuse("input", "clues");
    }
}

function validateMatch(match) {
    if (match === null || typeof match !== "object" || Array.isArray(match)) refuse("input", "match");
    exactKeys(match, ["key", "record", "clues", "hits"]);
    validateTyped(match.key, 0, true);
    validateTyped(match.record, 0, false);
    if (!Array.isArray(match.hits) || match.hits.length === 0) refuse("input", "hit");
    for (let i = 0; i < match.hits.length; i++) validateHit(match.hits[i]);
    validateClues(match.clues, match.hits);
}

function validateEnvelope(input) {
    if (input === null || typeof input !== "object" || Array.isArray(input)) refuse("input", "shape");
    exactKeys(input, ["source", "matches"]);
    const source = input.source;
    if (source === null || typeof source !== "object" || Array.isArray(source)) refuse("input", "source");
    exactKeys(source, ["input_sha256", "inventory_sha256", "root_sha256"]);
    if (!isEvenHex(source.input_sha256, 64)) refuse("input", "source");
    if (!isEvenHex(source.inventory_sha256, 64)) refuse("input", "source");
    if (!isEvenHex(source.root_sha256, 64)) refuse("input", "source");
    if (!Array.isArray(input.matches)) refuse("input", "matches");
    if (input.matches.length > MAX_MATCHES) refuse("limit", "matches");
    let previous = null;
    for (let i = 0; i < input.matches.length; i++) {
        const match = input.matches[i];
        validateMatch(match);
        const canon = JSON.stringify(match.key);
        if (previous !== null && canon <= previous) refuse("input", "order");
        previous = canon;
    }
}

function deepCopy(value) {
    if (value === null || typeof value !== "object") return value;
    if (Array.isArray(value)) {
        const out = new Array(value.length);
        for (let i = 0; i < value.length; i++) out[i] = deepCopy(value[i]);
        return out;
    }
    const out = {};
    const keys = Object.keys(value);
    for (let i = 0; i < keys.length; i++) out[keys[i]] = deepCopy(value[keys[i]]);
    return out;
}

function byteKey(hex) {
    return ["bytes", hex];
}

function findEntry(entries, hex) {
    for (let i = 0; i < entries.length; i++) {
        const key = entries[i][0];
        if (key[0] === "bytes" && key[1] === hex) return entries[i];
    }
    return null;
}

function isBytes(node) {
    return Array.isArray(node) && node[0] === "bytes";
}

function isTable(node) {
    return Array.isArray(node) && node[0] === "table";
}

function planScalar(entries, name, charsetArg, charsetName, fields, counter) {
    if (++counter.n > MAX_FIELDS) refuse("limit", "fields");
    const path = [byteKey(FIELD_HEX[name])];
    const found = findEntry(entries, FIELD_HEX[name]);
    if (!found) {
        fields.push({ path, role: name, status: "absent", raw: null, decode: null });
        return;
    }
    const value = found[1];
    if (!isBytes(value)) {
        fields.push({ path, role: name, status: "nonbytes", raw: deepCopy(value), decode: null });
        return;
    }
    const bytes = hexToBytes(value[1]);
    if (bytes.length > RAW_LIMIT) refuse("limit", "raw value");
    fields.push({
        path,
        role: name,
        status: "decoded",
        raw: ["bytes", value[1]],
        decode: { bytes, charsetArg, charsetName },
    });
}

function planDescription(entries, fields, counter) {
    if (++counter.n > MAX_FIELDS) refuse("limit", "fields");
    const path = [byteKey(FIELD_HEX.Description)];
    const found = findEntry(entries, FIELD_HEX.Description);
    if (!found) {
        fields.push({ path, role: "Description", status: "absent", raw: null, decode: null });
        return;
    }
    const value = found[1];
    if (!isTable(value)) {
        fields.push({ path, role: "Description", status: "nonbytes", raw: deepCopy(value), decode: null });
        return;
    }
    fields.push({ path, role: "Description", status: "container", raw: deepCopy(value), decode: null });
    const members = value[1];
    for (let i = 0; i < members.length; i++) {
        if (++counter.n > MAX_FIELDS) refuse("limit", "fields");
        const member = members[i];
        const memberPath = [byteKey(FIELD_HEX.Description), deepCopy(member[0])];
        if (!isBytes(member[1])) {
            fields.push({
                path: memberPath,
                role: "Description",
                status: "nonbytes",
                raw: deepCopy(member[1]),
                decode: null,
            });
            continue;
        }
        const bytes = hexToBytes(member[1][1]);
        if (bytes.length > RAW_LIMIT) refuse("limit", "raw value");
        fields.push({
            path: memberPath,
            role: "Description",
            status: "decoded",
            raw: ["bytes", member[1][1]],
            decode: { bytes, charsetArg: "big5", charsetName: "big5" },
        });
    }
}

function planMatch(match) {
    const fields = [];
    const counter = { n: 0 };
    if (!isTable(match.record)) {
        const names = ["Title", "Summary", "Description", "IconName", "NpcSpr", "NpcNavi"];
        for (let i = 0; i < names.length; i++) {
            if (++counter.n > MAX_FIELDS) refuse("limit", "fields");
            fields.push({
                path: [byteKey(FIELD_HEX[names[i]])],
                role: names[i],
                status: "row-not-table",
                raw: null,
                decode: null,
            });
        }
    } else {
        const entries = match.record[1];
        planScalar(entries, "Title", "big5", "big5", fields, counter);
        planScalar(entries, "Summary", "big5", "big5", fields, counter);
        planDescription(entries, fields, counter);
        planScalar(entries, "IconName", null, "windows-1252", fields, counter);
        planScalar(entries, "NpcSpr", null, "windows-1252", fields, counter);
        planScalar(entries, "NpcNavi", null, "windows-1252", fields, counter);
    }
    return {
        key: deepCopy(match.key),
        record: deepCopy(match.record),
        clues: deepCopy(match.clues),
        hits: deepCopy(match.hits),
        fields,
    };
}

function planAll(matches) {
    const plans = [];
    let total = 0;
    for (let i = 0; i < matches.length; i++) {
        const plan = planMatch(matches[i]);
        total += plan.fields.length;
        if (total > MAX_FIELDS) refuse("limit", "fields");
        plans.push(plan);
    }
    return plans;
}

function takeCallbacks(callbacks) {
    if (callbacks === null || typeof callbacks !== "object") refuse("callback", "missing");
    let decode;
    let sha256;
    try {
        decode = callbacks.decode;
        sha256 = callbacks.sha256;
    } catch (error) {
        refuse("callback", "missing");
    }
    if (typeof decode !== "function" || typeof sha256 !== "function") refuse("callback", "missing");
    return { decode, sha256 };
}

function unchanged(fresh, snap) {
    try {
        if (!(fresh instanceof Uint8Array) || fresh.length !== snap.length) return false;
        for (let i = 0; i < snap.length; i++) if (fresh[i] !== snap[i]) return false;
        return true;
    } catch (error) {
        return false;
    }
}

function scalars(text) {
    const out = [];
    for (let i = 0; i < text.length; i++) {
        const unit = text.charCodeAt(i);
        if (unit >= 0xD800 && unit <= 0xDBFF) {
            const next = text.charCodeAt(i + 1);
            if (!(next >= 0xDC00 && next <= 0xDFFF)) refuse("unicode", "unpaired surrogate");
            out.push(((unit - 0xD800) << 10) + (next - 0xDC00) + 0x10000);
            i += 1;
        } else if (unit >= 0xDC00 && unit <= 0xDFFF) {
            refuse("unicode", "unpaired surrogate");
        } else {
            out.push(unit);
        }
    }
    return out;
}

function replacementIndexes(codepoints) {
    const out = [];
    for (let i = 0; i < codepoints.length; i++) if (codepoints[i] === 0xFFFD) out.push(i);
    return out;
}

function callDecode(decode, bytes, charset) {
    const fresh = new Uint8Array(bytes);
    const snap = new Uint8Array(bytes);
    let text;
    try {
        text = decode(fresh, charset);
    } catch (error) {
        refuse("callback", "decode threw");
    }
    if (!unchanged(fresh, snap)) refuse("mutation", "decode bytes");
    if (typeof text !== "string") refuse("callback", "decode result");
    const codepoints = scalars(text);
    const utf8 = encoder.encode(text);
    if (utf8.length > STRING_LIMIT) refuse("limit", "callback string");
    return { text, codepoints, utf8 };
}

function callSha256(sha256, bytes) {
    const fresh = new Uint8Array(bytes);
    const snap = new Uint8Array(bytes);
    let hex;
    try {
        hex = sha256(fresh);
    } catch (error) {
        refuse("callback", "sha256 threw");
    }
    if (!unchanged(fresh, snap)) refuse("mutation", "sha256 bytes");
    if (typeof hex !== "string") refuse("callback", "sha256 result");
    if (encoder.encode(hex).length > STRING_LIMIT) refuse("limit", "callback string");
    if (!/^[0-9a-f]{64}$/.test(hex)) refuse("callback", "sha256 result");
    return hex;
}

function bytesToHex(bytes) {
    let hex = "";
    for (let i = 0; i < bytes.length; i++) hex += bytes[i].toString(16).padStart(2, "0");
    return hex;
}

function firstNul(bytes) {
    for (let i = 0; i < bytes.length; i++) if (bytes[i] === 0) return i;
    return null;
}

function buildDecoded(decode, sha256, spec) {
    const full = callDecode(decode, spec.bytes, spec.charsetArg);
    const utf8Sha = callSha256(sha256, full.utf8);
    const nul = firstNul(spec.bytes);
    let prefix = null;
    if (nul !== null) {
        const prefixBytes = spec.bytes.subarray(0, nul);
        const pre = callDecode(decode, prefixBytes, spec.charsetArg);
        prefix = {
            raw_hex: bytesToHex(prefixBytes),
            text: pre.text,
            codepoints: pre.codepoints,
            utf8_sha256: callSha256(sha256, pre.utf8),
            replacements: replacementIndexes(pre.codepoints),
        };
    }
    return {
        charset: spec.charsetName,
        text: full.text,
        codepoints: full.codepoints,
        utf8_sha256: utf8Sha,
        replacements: replacementIndexes(full.codepoints),
        first_nul: nul,
        prefix,
    };
}

function materializeField(decode, sha256, planned) {
    return {
        path: planned.path,
        role: planned.role,
        status: planned.status,
        raw_value: planned.raw,
        decoded: planned.decode ? buildDecoded(decode, sha256, planned.decode) : null,
    };
}

function emit(source, plans, decode, sha256) {
    const sourceOut = {
        input_sha256: source.input_sha256,
        inventory_sha256: source.inventory_sha256,
        root_sha256: source.root_sha256,
    };
    // `rows` and each row's `fields` are the last keys, so compact JSON grows
    // only inside those arrays. Account that growth before each push.
    const emptyBytes = jsonUtf8Bytes({ schema: SCHEMA, source: sourceOut, rows: [] });
    let rowsInner = 0;
    const rows = [];
    for (let i = 0; i < plans.length; i++) {
        const plan = plans[i];
        const recordSha = callSha256(sha256, encoder.encode(JSON.stringify(plan.record)));
        const shellBytes = jsonUtf8Bytes({
            key: plan.key,
            record: plan.record,
            clues: plan.clues,
            hits: plan.hits,
            record_sha256: recordSha,
            fields: [],
        });
        const fields = [];
        let fieldsInner = 0;
        const rowSep = rows.length > 0 ? 1 : 0;
        for (let f = 0; f < plan.fields.length; f++) {
            const field = materializeField(decode, sha256, plan.fields[f]);
            const fieldSep = fields.length > 0 ? 1 : 0;
            const nextInner = fieldsInner + fieldSep + jsonUtf8Bytes(field);
            const nextRow = shellBytes + nextInner;
            if (emptyBytes + rowsInner + rowSep + nextRow > RESULT_LIMIT) refuse("limit", "result");
            fields.push(field);
            fieldsInner = nextInner;
        }
        rows.push({
            key: plan.key,
            record: plan.record,
            clues: plan.clues,
            hits: plan.hits,
            record_sha256: recordSha,
            fields,
        });
        rowsInner += rowSep + shellBytes + fieldsInner;
    }
    const result = { schema: SCHEMA, source: sourceOut, rows };
    if (jsonUtf8Bytes(result) > RESULT_LIMIT) refuse("limit", "result");
    return result;
}

export function projectQuestText(input, callbacks) {
    const { decode, sha256 } = takeCallbacks(callbacks);
    assertPlainAndSized(input);
    validateEnvelope(input);
    const plans = planAll(input.matches);
    return emit(input.source, plans, decode, sha256);
}
