// T10.004 authored controls. Expected hashes and code points are specified here.
// They are not produced by calling projectQuestText.

import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import test from "node:test";

import { ProjectionError, projectQuestText } from "../../tools/renewal/quest_text_projection.mjs";

const encoder = new TextEncoder();
const POS0 = "0000000000000000";
const NEG0 = "0000000000000080";

function asciiHex(text) {
    let hex = "";
    for (let i = 0; i < text.length; i++) {
        const code = text.charCodeAt(i);
        assert.ok(code < 128);
        hex += code.toString(16).padStart(2, "0");
    }
    return hex;
}

function hexOf(bytes) {
    let hex = "";
    for (let i = 0; i < bytes.length; i++) hex += bytes[i].toString(16).padStart(2, "0");
    return hex;
}

function f64le(number) {
    const bytes = new Uint8Array(8);
    new DataView(bytes.buffer).setFloat64(0, number, true);
    return hexOf(bytes);
}

function sha256Bytes(bytes) {
    return createHash("sha256").update(bytes).digest("hex");
}

function sha256Text(text) {
    return sha256Bytes(encoder.encode(text));
}

function sha256Json(value) {
    return sha256Text(JSON.stringify(value));
}

function codepointsOf(text) {
    const out = [];
    for (const ch of text) out.push(ch.codePointAt(0));
    return out;
}

function replacementsOf(codepoints) {
    const out = [];
    for (let i = 0; i < codepoints.length; i++) if (codepoints[i] === 0xFFFD) out.push(i);
    return out;
}

function decodedExpect(charset, text, firstNul, prefix) {
    const codepoints = codepointsOf(text);
    return {
        charset,
        text,
        codepoints,
        utf8_sha256: sha256Text(text),
        replacements: replacementsOf(codepoints),
        first_nul: firstNul,
        prefix,
    };
}

function prefixExpect(hex, text) {
    const codepoints = codepointsOf(text);
    return {
        raw_hex: hex,
        text,
        codepoints,
        utf8_sha256: sha256Text(text),
        replacements: replacementsOf(codepoints),
    };
}

function source(fill = "ab") {
    assert.equal(fill.length, 2);
    return {
        input_sha256: fill.repeat(32),
        inventory_sha256: "cd".repeat(32),
        root_sha256: "ef".repeat(32),
    };
}

function hit(path, valueHex, clue, offsets) {
    return { path, value_hex: valueHex, clue, offsets };
}

function matchOf(key, record, clues, hits) {
    return { key, record, clues, hits };
}

function envelope(matches, src = source()) {
    return { source: src, matches };
}

function ch1Hit(valueHex = "6368315f", path = []) {
    return hit(path, valueHex, "ch1_", [0]);
}

function callbacks(map, behavior = {}) {
    const calls = [];
    return {
        calls,
        decode(bytes, charset) {
            const hex = hexOf(bytes);
            calls.push({ op: "decode", charset, hex, bytes });
            if (behavior.mutate === "decode") bytes[0] ^= 0xff;
            if (behavior.throwDecode) throw new Error("decode failed");
            if (behavior.badType) return 7;
            if (behavior.unicode) return "\uD800x";
            if (behavior.huge) return behavior.huge;
            const key = (charset === null ? "null" : String(charset)) + ":" + hex;
            assert.ok(Object.prototype.hasOwnProperty.call(map, key), key);
            return map[key];
        },
        sha256(bytes) {
            calls.push({ op: "sha256", bytes });
            if (behavior.mutate === "sha256") bytes[0] ^= 0xff;
            if (behavior.throwSha) throw new Error("sha failed");
            if (behavior.badHash) return behavior.badHash;
            return sha256Bytes(bytes);
        },
    };
}

function run(input, map = {}, behavior = {}) {
    const cbs = callbacks(map, behavior);
    return { out: projectQuestText(input, cbs), calls: cbs.calls };
}

function throws(input, code, detail, map = {}, behavior = {}) {
    assert.throws(
        () => projectQuestText(input, callbacks(map, behavior)),
        (err) => {
            assert.ok(err instanceof ProjectionError);
            assert.equal(err.name, "ProjectionError");
            assert.equal(err.code, code);
            if (detail) assert.equal(err.message, code + ": " + detail);
            return true;
        },
    );
}

function byCanon(left, right) {
    const a = JSON.stringify(left[0]);
    const b = JSON.stringify(right[0]);
    if (a < b) return -1;
    if (a > b) return 1;
    return 0;
}

function field(path, role, status, raw, decoded) {
    return { path, role, status, raw_value: raw, decoded };
}

function parentPath(name) {
    return [["bytes", asciiHex(name)]];
}

function freeze(value, seen = new Set()) {
    if (value === null || typeof value !== "object" || seen.has(value)) return;
    seen.add(value);
    if (Array.isArray(value)) {
        for (let i = 0; i < value.length; i++) freeze(value[i], seen);
    } else {
        for (const key of Object.keys(value)) freeze(value[key], seen);
    }
    Object.freeze(value);
}

const TITLE = "Title";
const SUMMARY = "Summary";
const DESCRIPTION = "Description";
const ICON = "IconName";
const SPR = "NpcSpr";
const NAVI = "NpcNavi";

test("projects a nested row with independent hashes, paths and profiles", () => {
    const titleHex = asciiHex("ch1_head");
    const summaryHex = asciiHex("ygg_roots");
    const childHex = asciiHex("child");
    const deepHex = "7a";
    const one = f64le(1);
    assert.equal(one, "000000000000f03f");
    const titleText = "Head<NAVI>Name<INFO>prt_fild05,10,20</INFO></NAVI>\n^FF0000";
    const summaryText = "乙\uFFFD";
    const childText = "a\u0301\u{1F600}\uFFFD";
    const memberIconText = "mem";
    const iconText = "icon.png";
    assert.deepEqual(codepointsOf(childText), [0x61, 0x0301, 0x1f600, 0xfffd]);
    assert.deepEqual(replacementsOf(codepointsOf(childText)), [3]);
    assert.deepEqual(codepointsOf(summaryText), [0x4e59, 0xfffd]);

    const members = [
        [["bool", false], ["nil"]],
        [["bytes", "31"], ["bytes", childHex]],
        [["bytes", asciiHex(ICON)], ["bytes", "5a"]],
        [["number", POS0], ["table", [[["bytes", asciiHex(TITLE)], ["bytes", deepHex]]]]],
    ];
    assert.deepEqual(members.slice().sort(byCanon), members);
    const description = ["table", members];
    const recordEntries = [
        [["bytes", asciiHex(DESCRIPTION)], description],
        [["bytes", asciiHex(ICON)], ["bytes", asciiHex("icon")]],
        [["bytes", asciiHex(NAVI)], ["nil"]],
        [["bytes", asciiHex("Reward")], ["number", one]],
        [["bytes", asciiHex(SUMMARY)], ["bytes", summaryHex]],
        [["bytes", asciiHex(TITLE)], ["bytes", titleHex]],
    ];
    assert.deepEqual(recordEntries.slice().sort(byCanon), recordEntries);
    const record = ["table", recordEntries];
    const clues = ["ch1_", "ygg_roots"];
    const hits = [
        hit([["bytes", asciiHex(TITLE)]], titleHex, "ch1_", [0]),
        hit([["bytes", asciiHex(SUMMARY)]], summaryHex, "ygg_roots", [0]),
    ];
    const key = ["number", one];
    const input = envelope([matchOf(key, record, clues, hits)]);
    const before = JSON.stringify(input);
    const map = {
        ["big5:" + titleHex]: titleText,
        ["big5:" + summaryHex]: summaryText,
        ["big5:" + childHex]: childText,
        ["big5:5a"]: memberIconText,
        ["null:" + asciiHex("icon")]: iconText,
    };
    const { out, calls } = run(input, map);
    assert.equal(JSON.stringify(input), before);
    assert.equal(typeof out.then, "undefined");

    const expected = {
        schema: "quest-text-projection-1",
        source: {
            input_sha256: input.source.input_sha256,
            inventory_sha256: input.source.inventory_sha256,
            root_sha256: input.source.root_sha256,
        },
        rows: [
            {
                key,
                record,
                clues,
                hits,
                record_sha256: sha256Json(record),
                fields: [
                    field(parentPath(TITLE), TITLE, "decoded", ["bytes", titleHex], decodedExpect("big5", titleText, null, null)),
                    field(parentPath(SUMMARY), SUMMARY, "decoded", ["bytes", summaryHex], decodedExpect("big5", summaryText, null, null)),
                    field(parentPath(DESCRIPTION), DESCRIPTION, "container", description, null),
                    field([parentPath(DESCRIPTION)[0], ["bool", false]], DESCRIPTION, "nonbytes", ["nil"], null),
                    field(
                        [parentPath(DESCRIPTION)[0], ["bytes", "31"]],
                        DESCRIPTION,
                        "decoded",
                        ["bytes", childHex],
                        decodedExpect("big5", childText, null, null),
                    ),
                    field(
                        [parentPath(DESCRIPTION)[0], ["bytes", asciiHex(ICON)]],
                        DESCRIPTION,
                        "decoded",
                        ["bytes", "5a"],
                        decodedExpect("big5", memberIconText, null, null),
                    ),
                    field(
                        [parentPath(DESCRIPTION)[0], ["number", POS0]],
                        DESCRIPTION,
                        "nonbytes",
                        ["table", [[["bytes", asciiHex(TITLE)], ["bytes", deepHex]]]],
                        null,
                    ),
                    field(parentPath(ICON), ICON, "decoded", ["bytes", asciiHex("icon")], decodedExpect("windows-1252", iconText, null, null)),
                    field(parentPath(SPR), SPR, "absent", null, null),
                    field(parentPath(NAVI), NAVI, "nonbytes", ["nil"], null),
                ],
            },
        ],
    };
    assert.deepEqual(out, expected);
    assert.deepEqual(Object.keys(out), ["schema", "source", "rows"]);
    assert.deepEqual(Object.keys(out.rows[0]), ["key", "record", "clues", "hits", "record_sha256", "fields"]);
    assert.deepEqual(Object.keys(out.rows[0].fields[0]), ["path", "role", "status", "raw_value", "decoded"]);
    assert.deepEqual(Object.keys(out.rows[0].fields[0].decoded), [
        "charset",
        "text",
        "codepoints",
        "utf8_sha256",
        "replacements",
        "first_nul",
        "prefix",
    ]);
    assert.equal(out.rows[0].fields[0].decoded.text.includes("<NAVI>"), true);
    assert.equal(out.rows[0].fields[0].decoded.text.includes("^FF0000"), true);
    assert.equal(out.rows[0].fields[0].decoded.text.includes("\n"), true);
    assert.deepEqual(
        out.rows[0].fields.map((item) => item.role + ":" + item.status),
        [
            "Title:decoded",
            "Summary:decoded",
            "Description:container",
            "Description:nonbytes",
            "Description:decoded",
            "Description:decoded",
            "Description:nonbytes",
            "IconName:decoded",
            "NpcSpr:absent",
            "NpcNavi:nonbytes",
        ],
    );

    const decodes = calls.filter((call) => call.op === "decode");
    assert.deepEqual(
        decodes.map((call) => [call.charset, call.hex]),
        [
            ["big5", titleHex],
            ["big5", summaryHex],
            ["big5", childHex],
            ["big5", "5a"],
            [null, asciiHex("icon")],
        ],
    );
    assert.equal(decodes.some((call) => call.hex === deepHex), false);
    assert.equal(calls[0].op, "sha256");
    assert.equal(hexOf(calls[0].bytes), hexOf(encoder.encode(JSON.stringify(record))));
    assert.equal(out.rows[0].record_sha256, sha256Json(record));
    assert.notStrictEqual(out.source, input.source);
    assert.notStrictEqual(out.rows[0].record, input.matches[0].record);
    assert.notStrictEqual(out.rows[0].fields[0].raw_value, input.matches[0].record[1][5][1]);
    assert.notStrictEqual(out.rows[0].fields[2].raw_value, description);
    assert.notStrictEqual(out.rows[0].fields[2].raw_value[1], description[1]);
    assert.notStrictEqual(out.rows[0].fields[4].raw_value, out.rows[0].fields[2].raw_value[1][1][1]);
    const recordJson = JSON.stringify(out.rows[0].record);
    out.rows[0].fields[0].raw_value[1] = "00";
    out.rows[0].fields[4].decoded.text = "changed";
    assert.equal(JSON.stringify(out.rows[0].record), recordJson);
    assert.equal(JSON.stringify(input), before);
});

test("classifies absent, nil, scalar, byte and deeper description shapes", () => {
    const shapes = [];

    const absentRecord = ["table", [[["bytes", asciiHex(TITLE)], ["bytes", "41"]]]];
    shapes.push({
        record: absentRecord,
        map: { "big5:41": "A" },
        assertRow(row, calls) {
            assert.equal(row.fields[2].status, "absent");
            assert.equal(row.fields[2].raw_value, null);
            assert.equal(row.fields.length, 6);
            assert.equal(calls.filter((call) => call.op === "decode").length, 1);
        },
    });

    const nilRecord = ["table", [[["bytes", asciiHex(DESCRIPTION)], ["nil"]]]];
    shapes.push({
        record: nilRecord,
        map: {},
        assertRow(row, calls) {
            assert.deepEqual(row.fields[2], field(parentPath(DESCRIPTION), DESCRIPTION, "nonbytes", ["nil"], null));
            assert.equal(row.fields.length, 6);
            assert.equal(calls.some((call) => call.op === "decode"), false);
        },
    });

    const byteRecord = ["table", [[["bytes", asciiHex(DESCRIPTION)], ["bytes", "4142"]]]];
    shapes.push({
        record: byteRecord,
        map: { "big5:4142": "should-not-decode" },
        assertRow(row, calls) {
            assert.equal(row.fields[2].status, "nonbytes");
            assert.deepEqual(row.fields[2].raw_value, ["bytes", "4142"]);
            assert.equal(row.fields[2].decoded, null);
            assert.equal(calls.some((call) => call.op === "decode"), false);
        },
    });

    const numberRecord = ["table", [[["bytes", asciiHex(DESCRIPTION)], ["number", NEG0]]]];
    shapes.push({
        record: numberRecord,
        map: {},
        assertRow(row) {
            assert.equal(row.fields[2].status, "nonbytes");
            assert.deepEqual(row.fields[2].raw_value, ["number", NEG0]);
        },
    });

    const grandchild = ["bytes", "7a7a"];
    const inner = ["table", [[["bytes", "32"], grandchild]]];
    const nestedRecord = ["table", [[["bytes", asciiHex(DESCRIPTION)], ["table", [[["bytes", "31"], inner]]]]]];
    shapes.push({
        record: nestedRecord,
        map: { "big5:7a7a": "nope" },
        assertRow(row, calls) {
            assert.equal(row.fields.length, 7);
            assert.equal(row.fields[2].status, "container");
            assert.equal(row.fields[3].status, "nonbytes");
            assert.equal(row.fields[3].role, DESCRIPTION);
            assert.deepEqual(row.fields[3].path[1], ["bytes", "31"]);
            assert.deepEqual(row.fields[3].raw_value, inner);
            assert.equal(calls.some((call) => call.op === "decode"), false);
            assert.notStrictEqual(row.fields[3].raw_value, row.fields[2].raw_value[1][0][1]);
        },
    });

    for (const shape of shapes) {
        const input = envelope([
            matchOf(["bytes", "01"], shape.record, ["ch1_"], [ch1Hit()]),
        ]);
        const { out, calls } = run(input, shape.map);
        assert.equal(out.rows.length, 1);
        assert.equal(out.rows[0].record_sha256, sha256Json(shape.record));
        shape.assertRow(out.rows[0], calls);
    }

    for (const record of [["nil"], ["bool", true], ["number", POS0], ["bytes", "00ff"]]) {
        const input = envelope([matchOf(["bytes", "02"], record, ["pay_fild01"], [hit([], "7061795f66696c643031", "pay_fild01", [0])])]);
        const { out, calls } = run(input, {});
        assert.equal(calls.some((call) => call.op === "decode"), false);
        assert.deepEqual(
            out.rows[0].fields,
            [TITLE, SUMMARY, DESCRIPTION, ICON, SPR, NAVI].map((name) => field(parentPath(name), name, "row-not-table", null, null)),
        );
        assert.equal(out.rows[0].record_sha256, sha256Json(record));
    }
});

test("preserves NUL prefixes and full text on both charset routes", () => {
    const titleHex = "004100";
    const summaryHex = "410042";
    const iconHex = "414200";
    const record = ["table", [
        [["bytes", asciiHex(ICON)], ["bytes", iconHex]],
        [["bytes", asciiHex(SUMMARY)], ["bytes", summaryHex]],
        [["bytes", asciiHex(TITLE)], ["bytes", titleHex]],
    ].sort(byCanon)];
    const input = envelope([matchOf(["bytes", "0a"], record, ["mu_fild01"], [hit([], "6d755f66696c643031", "mu_fild01", [0, 3])])]);
    const map = {
        ["big5:" + titleHex]: "FULL-START",
        "big5:": "EMPTY-PREFIX",
        ["big5:" + summaryHex]: "A\u0000B",
        "big5:41": "A",
        ["null:" + iconHex]: "END\n<NAVI>x<INFO>y</INFO></NAVI>",
        "null:4142": "EN",
    };
    const { out, calls } = run(input, map);
    const title = out.rows[0].fields[0];
    const summary = out.rows[0].fields[1];
    const icon = out.rows[0].fields[3];
    assert.deepEqual(title.decoded, decodedExpect("big5", "FULL-START", 0, prefixExpect("", "EMPTY-PREFIX")));
    assert.deepEqual(summary.decoded, decodedExpect("big5", "A\u0000B", 1, prefixExpect("41", "A")));
    assert.equal(summary.decoded.text, "A\u0000B");
    assert.notEqual(summary.decoded.text, summary.decoded.prefix.text);
    assert.deepEqual(
        icon.decoded,
        decodedExpect("windows-1252", "END\n<NAVI>x<INFO>y</INFO></NAVI>", 2, prefixExpect("4142", "EN")),
    );
    assert.equal(icon.decoded.charset, "windows-1252");
    assert.deepEqual(
        calls.filter((call) => call.op === "decode").map((call) => [call.charset, call.hex]),
        [
            ["big5", titleHex],
            ["big5", ""],
            ["big5", summaryHex],
            ["big5", "41"],
            [null, iconHex],
            [null, "4142"],
        ],
    );
    assert.equal(calls.filter((call) => call.op === "decode").every((call) => call.bytes instanceof Uint8Array), true);
    assert.notStrictEqual(calls[1].bytes, calls[2].bytes);
});

test("counts astral, combining and replacement indexes as code points", () => {
    const text = "e\u0301\u{1F4A9}\uFFFD\uFFFD";
    const record = ["table", [[["bytes", asciiHex(TITLE)], ["bytes", "aa"]]]];
    const input = envelope([matchOf(["bytes", "01"], record, ["ygg_edge"], [hit([], "7967675f65646765", "ygg_edge", [0])])]);
    const { out } = run(input, { "big5:aa": text });
    const decoded = out.rows[0].fields[0].decoded;
    assert.deepEqual(decoded.codepoints, [0x65, 0x0301, 0x1f4a9, 0xfffd, 0xfffd]);
    assert.deepEqual(decoded.replacements, [3, 4]);
    assert.equal(decoded.text, text);
    assert.equal(decoded.utf8_sha256, sha256Text(text));
    assert.notEqual(text.indexOf("\uFFFD"), 3);
});

test("accepts canonical order and preserves hit order, shared values and frozen inputs", () => {
    const two = f64le(2);
    const one = f64le(1);
    assert.ok(JSON.stringify(["number", two]) < JSON.stringify(["number", one]));
    assert.ok(JSON.stringify(["bool", true]) < JSON.stringify(["number", one]));
    const shared = ["bytes", "41"];
    const first = matchOf(
        ["number", two],
        ["table", [[["bytes", asciiHex(SUMMARY)], shared], [["bytes", asciiHex(TITLE)], shared]]],
        ["ch1_", "ygg_fruit"],
        [
            hit([["bytes", asciiHex(TITLE)]], "7967675f6672756974", "ygg_fruit", [0]),
            hit([["bytes", asciiHex(SUMMARY)]], "6368315f", "ch1_", [0]),
        ],
    );
    const second = matchOf(
        ["bool", true],
        ["nil"],
        ["prt_fild05"],
        [hit([], "7072745f66696c643035", "prt_fild05", [0])],
    );
    const ordered = [first, second].slice().sort((a, b) => {
        const left = JSON.stringify(a.key);
        const right = JSON.stringify(b.key);
        if (left < right) return -1;
        if (left > right) return 1;
        return 0;
    });
    assert.equal(ordered[0], second);
    const input = envelope(ordered);
    const before = JSON.stringify(input);
    freeze(input);
    const { out, calls } = run(input, { "big5:41": "S", "big5:41:dup": "S" });
    assert.equal(JSON.stringify(input), before);
    assert.equal(out.rows[0].key[0], "bool");
    assert.equal(out.rows[1].key[1], two);
    assert.equal(out.rows[1].hits[0].clue, "ygg_fruit");
    assert.equal(out.rows[1].hits[1].clue, "ch1_");
    assert.deepEqual(out.rows[1].clues, ["ch1_", "ygg_fruit"]);
    const title = out.rows[1].fields[0];
    const summary = out.rows[1].fields[1];
    assert.equal(title.status, "decoded");
    assert.equal(summary.status, "decoded");
    assert.notStrictEqual(title.raw_value, summary.raw_value);
    assert.notStrictEqual(title.raw_value, shared);
    assert.equal(calls.filter((call) => call.op === "decode").length, 2);
    assert.notStrictEqual(calls.filter((call) => call.op === "decode")[0].bytes, calls.filter((call) => call.op === "decode")[1].bytes);

    const reversed = envelope([first, second]);
    throws(reversed, "input", "order");
    const badMembers = ["table", [
        [["bytes", asciiHex(DESCRIPTION)], ["table", [
            [["bytes", "32"], ["nil"]],
            [["bytes", "31"], ["nil"]],
        ]]],
    ]];
    throws(envelope([matchOf(["bytes", "01"], badMembers, ["ch1_"], [ch1Hit()])]), "input", "order");
});

test("decodes an empty byte value and an empty match list without inventing rows", () => {
    const emptyKey = ["bytes", ""];
    const record = ["table", [[["bytes", asciiHex(TITLE)], emptyKey]]];
    const input = envelope([matchOf(["bytes", "01"], record, ["ch1_"], [ch1Hit()])]);
    const { out, calls } = run(input, { "big5:": "" });
    const decoded = out.rows[0].fields[0].decoded;
    assert.equal(decoded.text, "");
    assert.deepEqual(decoded.codepoints, []);
    assert.deepEqual(decoded.replacements, []);
    assert.equal(decoded.first_nul, null);
    assert.equal(decoded.prefix, null);
    assert.equal(decoded.utf8_sha256, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
    assert.equal(calls.filter((call) => call.op === "decode").length, 1);

    let used = false;
    const emptyOut = projectQuestText(envelope([]), {
        decode() {
            used = true;
            return "";
        },
        sha256() {
            used = true;
            return "ab".repeat(32);
        },
    });
    assert.equal(used, false);
    assert.deepEqual(emptyOut.rows, []);
    assert.equal(emptyOut.schema, "quest-text-projection-1");
});

test("refuses malformed structure without calling callbacks", () => {
    const good = envelope([matchOf(["bytes", "01"], ["nil"], ["ch1_"], [ch1Hit()])]);
    const cases = [];

    const extra = envelope([matchOf(["bytes", "01"], ["nil"], ["ch1_"], [ch1Hit()])]);
    extra.extra = 1;
    cases.push(["extra top", extra]);

    const badHash = source();
    badHash.input_sha256 = "AB".repeat(32);
    cases.push(["upper hash", envelope([matchOf(["bytes", "01"], ["nil"], ["ch1_"], [ch1Hit()])], badHash)]);

    const short = source();
    short.root_sha256 = "aa";
    cases.push(["short hash", envelope([matchOf(["bytes", "01"], ["nil"], ["ch1_"], [ch1Hit()])], short)]);

    cases.push(["unknown tag", envelope([matchOf(["bytes", "01"], ["string", "41"], ["ch1_"], [ch1Hit()])])]);
    cases.push(["nil arity", envelope([matchOf(["bytes", "01"], ["nil", 1], ["ch1_"], [ch1Hit()])])]);
    cases.push(["odd bytes", envelope([matchOf(["bytes", "01"], ["table", [[["bytes", asciiHex(TITLE)], ["bytes", "4"]]]], ["ch1_"], [ch1Hit()])])]);
    cases.push(["upper bytes", envelope([matchOf(["bytes", "0A"], ["nil"], ["ch1_"], [ch1Hit()])])]);
    cases.push(["neg zero key", envelope([matchOf(["number", NEG0], ["nil"], ["ch1_"], [ch1Hit()])])]);
    cases.push(["nan", envelope([matchOf(["bytes", "01"], ["number", f64le(Number.NaN)], ["ch1_"], [ch1Hit()])])]);
    cases.push(["infinity", envelope([matchOf(["bytes", "01"], ["number", f64le(Number.POSITIVE_INFINITY)], ["ch1_"], [ch1Hit()])])]);
    cases.push(["empty clues", envelope([matchOf(["bytes", "01"], ["nil"], [], [ch1Hit()])])]);
    cases.push(["clue order", envelope([matchOf(["bytes", "01"], ["nil"], ["ygg_roots", "ch1_"], [
        ch1Hit(),
        hit([], "7967675f726f6f7473", "ygg_roots", [0]),
    ])])]);
    cases.push(["clue mismatch", envelope([matchOf(["bytes", "01"], ["nil"], ["ch1_", "ygg_roots"], [ch1Hit()])])]);
    cases.push(["empty hits", envelope([matchOf(["bytes", "01"], ["nil"], ["ch1_"], [])])]);
    cases.push(["offset length", envelope([matchOf(["bytes", "01"], ["nil"], ["ch1_"], [hit([], "61", "ch1_", [1])])])]);
    cases.push(["duplicate offset", envelope([matchOf(["bytes", "01"], ["nil"], ["ch1_"], [hit([], "6161", "ch1_", [0, 0])])])]);
    cases.push(["float offset", envelope([matchOf(["bytes", "01"], ["nil"], ["ch1_"], [hit([], "6161", "ch1_", [0.5])])])]);
    cases.push(["nil path", envelope([matchOf(["bytes", "01"], ["nil"], ["ch1_"], [hit([["nil"]], "61", "ch1_", [0])])])]);
    cases.push(["table key", envelope([matchOf(["table", []], ["nil"], ["ch1_"], [ch1Hit()])])]);

    const hole = [matchOf(["bytes", "01"], ["nil"], ["ch1_"], [ch1Hit()])];
    hole.length = 2;
    cases.push(["hole", { source: source(), matches: hole }]);

    const cyc = ["table", []];
    cyc[1].push([["bytes", "61"], cyc]);
    cases.push(["cycle", envelope([matchOf(["bytes", "01"], cyc, ["ch1_"], [ch1Hit()])])]);

    let calls = 0;
    const quiet = {
        decode() {
            calls += 1;
            return "";
        },
        sha256() {
            calls += 1;
            return "ab".repeat(32);
        },
    };
    for (const [label, input] of cases) {
        assert.throws(() => projectQuestText(input, quiet), (err) => err instanceof ProjectionError && err.code === "input", label);
    }
    assert.equal(calls, 0);
    assert.equal(JSON.stringify(good.matches[0].record), '["nil"]');

    let got = false;
    const getter = { matches: [] };
    Object.defineProperty(getter, "source", {
        enumerable: true,
        get() {
            got = true;
            return source();
        },
    });
    assert.throws(() => projectQuestText(getter, quiet), (err) => err.code === "input");
    assert.equal(got, false);

    let jsonGot = false;
    const withToJSON = envelope([]);
    withToJSON.toJSON = () => {
        jsonGot = true;
        return {};
    };
    assert.throws(() => projectQuestText(withToJSON, quiet), (err) => err.code === "input");
    assert.equal(jsonGot, false);

    let protoGot = false;
    const proto = {};
    Object.defineProperty(proto, "hidden", {
        enumerable: true,
        get() {
            protoGot = true;
            return 1;
        },
    });
    const custom = Object.create(proto);
    custom.source = source();
    custom.matches = [];
    assert.throws(() => projectQuestText(custom, quiet), (err) => err.code === "input");
    assert.equal(protoGot, false);
});

test("refuses callback, hash, unicode and byte-mutation failures", () => {
    const input = envelope([matchOf(["bytes", "01"], ["table", [[["bytes", asciiHex(TITLE)], ["bytes", "41"]]]], ["ch1_"], [ch1Hit()])]);
    assert.throws(() => projectQuestText(input, null), (err) => err.code === "callback" && err.message === "callback: missing");
    assert.throws(() => projectQuestText(input, { decode: "no", sha256() {} }), (err) => err.code === "callback");
    throws(input, "callback", "decode threw", { "big5:41": "A" }, { throwDecode: true });
    throws(input, "callback", "decode result", { "big5:41": "A" }, { badType: true });
    throws(input, "unicode", "unpaired surrogate", { "big5:41": "A" }, { unicode: true });
    throws(input, "mutation", "decode bytes", { "big5:41": "A" }, { mutate: "decode" });
    throws(input, "callback", "sha256 threw", { "big5:41": "A" }, { throwSha: true });
    throws(input, "callback", "sha256 result", { "big5:41": "A" }, { badHash: "ABCD" });
    throws(input, "callback", "sha256 result", { "big5:41": "A" }, { badHash: "AB".repeat(32) });
    throws(input, "mutation", "sha256 bytes", { "big5:41": "A" }, { mutate: "sha256" });
});

test("enforces depth, match, field, raw, string, input and result caps", () => {
    function nest(levels) {
        let node = ["nil"];
        for (let i = 0; i < levels; i++) node = ["table", [[["number", POS0], node]]];
        return node;
    }
    const deepHit = [ch1Hit()];
    throws(envelope([matchOf(["bytes", "01"], nest(33), ["ch1_"], deepHit)]), "limit", "depth");
    const accepted = run(envelope([matchOf(["bytes", "01"], nest(32), ["ch1_"], deepHit)]));
    assert.equal(accepted.out.rows[0].fields.length, 6);
    assert.equal(accepted.out.rows[0].fields.every((item) => item.status === "absent"), true);
    assert.equal(accepted.calls.some((call) => call.op === "decode"), false);

    function manyMatches(count) {
        const matches = [];
        for (let i = 0; i < count; i++) {
            matches.push(matchOf(["bytes", i.toString(16).padStart(4, "0")], ["nil"], ["ch1_"], [ch1Hit()]));
        }
        return envelope(matches);
    }
    throws(manyMatches(257), "limit", "matches");
    const fullMatches = run(manyMatches(256));
    assert.equal(fullMatches.out.rows.length, 256);
    assert.equal(fullMatches.calls.filter((call) => call.op === "sha256").length, 256);
    assert.equal(fullMatches.calls.some((call) => call.op === "decode"), false);

    function described(count) {
        const members = [];
        for (let i = 0; i < count; i++) members.push([["bytes", i.toString(16).padStart(4, "0")], ["nil"]]);
        const record = ["table", [[["bytes", asciiHex(DESCRIPTION)], ["table", members]]]];
        return envelope([matchOf(["bytes", "01"], record, ["ch1_"], [ch1Hit()])]);
    }
    throws(described(4091), "limit", "fields");
    const fullFields = run(described(4090));
    assert.equal(fullFields.out.rows[0].fields.length, 4096);
    assert.equal(fullFields.out.rows[0].fields[2].status, "container");
    assert.equal(fullFields.calls.some((call) => call.op === "decode"), false);

    const rawOk = "61".repeat(65536);
    const rawOver = "61".repeat(65537);
    const rawInput = (hex) => envelope([
        matchOf(["bytes", "01"], ["table", [[["bytes", asciiHex(TITLE)], ["bytes", hex]]]], ["ch1_"], [ch1Hit()]),
    ]);
    throws(rawInput(rawOver), "limit", "raw value");
    const rawDone = run(rawInput(rawOk), { ["big5:" + rawOk]: "Z" });
    assert.equal(rawDone.out.rows[0].fields[0].status, "decoded");
    assert.equal(rawDone.out.rows[0].fields[0].decoded.text, "Z");
    assert.equal(rawDone.out.rows[0].fields[0].raw_value[1].length, 131072);

    const big = "a".repeat(256 * 1024);
    const bigger = "a".repeat(256 * 1024 + 1);
    const oneTitle = rawInput("62");
    throws(oneTitle, "limit", "callback string", { "big5:62": bigger }, { huge: bigger });
    const exactString = run(oneTitle, { "big5:62": big }, { huge: big });
    assert.equal(exactString.out.rows[0].fields[0].decoded.text.length, 256 * 1024);

    function wide(count) {
        const members = [];
        for (let i = 0; i < count; i++) members.push([["bytes", i.toString(16).padStart(4, "0")], ["bytes", "63"]]);
        const record = ["table", [
            [["bytes", asciiHex(DESCRIPTION)], ["table", members]],
            [["bytes", asciiHex(ICON)], ["bytes", "63"]],
            [["bytes", asciiHex(SUMMARY)], ["bytes", "63"]],
            [["bytes", asciiHex(TITLE)], ["bytes", "63"]],
        ].sort(byCanon)];
        return envelope([matchOf(["bytes", "01"], record, ["ch1_"], [ch1Hit()])]);
    }
    throws(wide(61), "limit", "result", { "big5:63": big, "null:63": big }, { huge: big });

    const pad = envelope([matchOf(
        ["bytes", "01"],
        ["table", [[["bytes", asciiHex(DESCRIPTION)], ["bytes", ""]]]],
        ["ch1_"],
        [ch1Hit()],
    )]);
    const overhead = encoder.encode(JSON.stringify(pad)).length;
    const room = 1024 * 1024 - overhead;
    assert.ok(room > 10 && room % 2 === 0);
    const fitted = "62".repeat(room / 2);
    pad.matches[0].record[1][0][1][1] = fitted;
    assert.equal(encoder.encode(JSON.stringify(pad)).length, 1024 * 1024);
    const fittedOut = run(pad, {});
    assert.equal(fittedOut.out.rows[0].fields[2].status, "nonbytes");
    assert.equal(fittedOut.calls.some((call) => call.op === "decode"), false);
    pad.matches[0].record[1][0][1][1] = fitted + "62";
    assert.ok(encoder.encode(JSON.stringify(pad)).length > 1024 * 1024);
    throws(pad, "limit", "input");
});
