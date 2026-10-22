"""Authored synthetic controls for quest_table_inventory (T10.002).

Run: python3 -m unittest discover -s tests/renewal -v
Chunks are hand-assembled here; no acquired asset is read. Expected typed
values, hex and canonical bytes are written literally, not produced by the
serializer under test.
"""

import hashlib
import json
from pathlib import Path
import struct
import sys
import unittest
from unittest import mock

TOOLS = Path(__file__).resolve().parents[2] / "tools" / "renewal"
sys.path.insert(0, str(TOOLS))
import quest_table_inventory as qti  # noqa: E402

HEADER = bytes.fromhex("1b4c75615100010404040800")
OP = {"MOVE": 0, "LOADK": 1, "LOADBOOL": 2, "LOADNIL": 3, "GETGLOBAL": 5,
      "SETGLOBAL": 7, "SETTABLE": 9, "NEWTABLE": 10, "JMP": 22, "CALL": 28,
      "RETURN": 30, "SETLIST": 34, "CLOSURE": 36}
QIL = b"QuestInfoList"
QIL_HEX = "5175657374496e666f4c697374"
ONE, TWO, THREE, SEVEN = "000000000000f03f", "0000000000000040", "0000000000000840", "0000000000001c40"
ZERO, NEG_ZERO = "0000000000000000", "0000000000000080"
CLUE_NAMES = ["ch1_", "ygg_roots", "ygg_fruit", "ygg_edge", "mu_fild01", "prt_fild05", "pay_fild01"]


def abc(op, a, b=0, c=0):
    return OP[op] | a << 6 | c << 14 | b << 23


def abx(op, a, bx):
    return OP[op] | a << 6 | bx << 14


def lstr(value):
    return struct.pack("<I", len(value) + 1) + value + b"\0"


def proto(code, constants, maxstack=8, nups=0, children=(), ncode=None):
    out = lstr(b"@t") + struct.pack("<II", 0, 0) + bytes([nups, 0, 2, maxstack])
    out += struct.pack("<I", len(code) if ncode is None else ncode)
    out += b"".join(struct.pack("<I", w) for w in code)
    out += struct.pack("<I", len(constants))
    for value in constants:
        if value is None:
            out += b"\0"
        elif isinstance(value, bool):
            out += b"\1" + bytes([value])
        elif isinstance(value, float):
            out += b"\3" + struct.pack("<d", value)
        else:
            out += b"\4" + lstr(value)
    out += struct.pack("<I", len(children)) + b"".join(children)
    return out + struct.pack("<III", 0, 0, 0)


class R(int):
    """A register operand."""


class Asm:
    """Tiny assembler; constants are identified by exact type and bits."""

    def __init__(self):
        self.code, self.consts, self.ids = [], [], []

    def k(self, value):
        ident = (type(value), struct.pack("<d", value) if isinstance(value, float) else value)
        if ident not in self.ids:
            self.ids.append(ident)
            self.consts.append(value)
        return self.ids.index(ident)

    def rk(self, value):
        return int(value) if isinstance(value, R) else 256 + self.k(value)

    def emit(self, *words):
        self.code.extend(words)
        return self

    def new(self, a):
        return self.emit(abc("NEWTABLE", a))

    def set(self, a, key, value):
        return self.emit(abc("SETTABLE", a, self.rk(key), self.rk(value)))

    def loadk(self, a, value):
        return self.emit(abx("LOADK", a, self.k(value)))

    def glob(self, a, name):
        return self.emit(abx("SETGLOBAL", a, self.k(name)))

    def pc(self):
        """One-based pc of the next emitted instruction."""
        return len(self.code) + 1

    def chunk(self, ret=True, **kw):
        code = self.code + ([abc("RETURN", 0, 1)] if ret else [])
        return HEADER + proto(code, self.consts, **kw)


def b(text):
    return ["bytes", text.hex()]


def sha(canonical_bytes):
    return hashlib.sha256(canonical_bytes).hexdigest()


def chain(nested):
    """QuestInfoList plus `nested` tables below it (root is depth 1)."""
    a = Asm()
    for r in range(nested + 1):
        a.new(r)
    for r in range(nested):
        a.set(r, b"n", R(r + 1))
    return a.glob(0, QIL).chunk(maxstack=40)


def refuses(test, data, code):
    with test.assertRaises(qti.InventoryError) as ctx:
        qti.inventory_bytes(data)
    test.assertEqual(ctx.exception.code, code, str(ctx.exception))
    test.assertIsInstance(ctx.exception, ValueError)
    return str(ctx.exception)


class ValidInventory(unittest.TestCase):
    def test_minimal_full_result(self):
        asm = Asm().new(0).new(1).set(1, b"Title", b"ch1_a").set(0, 7.0, R(1)).glob(0, QIL)
        data = asm.chunk()
        self.assertEqual(asm.consts, [b"Title", b"ch1_a", 7.0, QIL])
        row = b'["table",[[["bytes","5469746c65"],["bytes","6368315f61"]]]]'
        root = b'["table",[[["number","0000000000001c40"],' + row + b"]]]"
        record = ["table", [[["bytes", "5469746c65"], ["bytes", "6368315f61"]]]]
        expected = {
            "schema": "T10.002-raw-quest-inventory-1",
            "input": {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                      "header_hex": "1b4c75615100010404040800"},
            "prototype": {"instructions": 6, "constants": 4, "children": 0},
            "globals": [QIL_HEX],
            "root": {"global_hex": QIL_HEX, "table_ordinal": 1, "row_count": 1, "sha256": sha(root)},
            "rows": [{"key": ["number", SEVEN], "kind": "table", "sha256": sha(row),
                      "fields": [{"key": ["bytes", "5469746c65"], "kind": "bytes"}]}],
            "matches": [{"key": ["number", SEVEN], "record": record, "clues": ["ch1_"],
                         "hits": [{"path": [["bytes", "5469746c65"]], "value_hex": "6368315f61",
                                   "clue": "ch1_", "offsets": [0]}]}],
            "negatives": CLUE_NAMES[1:],
            "provenance": {"tables_created": 2, "writes": 2, "repeated_writes": [], "nil_writes": [],
                           "global_assignments": [{"pc": 5, "name_hex": QIL_HEX, "existed": False,
                                                   "before": ["absent"], "after": ["table-ref", 1]}]},
        }
        result = qti.inventory_bytes(data)
        self.assertEqual(result, expected)
        self.assertEqual(qti.inventory_bytes(bytearray(data)), expected)
        json.dumps(result, allow_nan=False)  # plain JSON types only

    def nested(self):
        a = Asm().new(0).new(1)
        a.set(1, b"Title", b"Roots").set(1, b"Map", b"ygg_roots").new(2)
        a.loadk(3, b"go to ch1_ygg_edge").loadk(4, b"x").emit(abc("SETLIST", 2, 2, 1))
        a.set(1, b"Description", R(2)).new(2).new(3).set(3, b"ItemID", 2.0).set(3, b"Count", 1.0)
        a.emit(abc("SETLIST", 2, 1, 1)).set(1, b"RewardItemList", R(2)).set(0, 1.0, R(1))
        a.set(0, 2.0, b"ch1_ch1_").new(1).set(1, b"Note", b"CH1_ no").set(1, b"ch1_key", b"plain")
        a.set(0, 3.0, R(1)).glob(0, QIL)
        return qti.inventory_bytes(a.chunk())

    def test_nested_rows_fields_and_canonical_order(self):
        result = self.nested()
        # Canonical key bytes order: 2.0 < 3.0 < 1.0 as little-endian hex strings.
        self.assertEqual([r["key"] for r in result["rows"]],
                         [["number", TWO], ["number", THREE], ["number", ONE]])
        self.assertEqual(result["rows"][0], {"key": ["number", TWO], "kind": "bytes", "fields": None,
                                             "sha256": sha(b'["bytes","6368315f6368315f"]')})
        self.assertEqual(result["rows"][1]["fields"], [{"key": b(b"Note"), "kind": "bytes"},
                                                       {"key": b(b"ch1_key"), "kind": "bytes"}])
        self.assertEqual(result["rows"][2]["fields"], [
            {"key": b(b"Description"), "kind": "table"}, {"key": b(b"Map"), "kind": "bytes"},
            {"key": b(b"RewardItemList"), "kind": "table"}, {"key": b(b"Title"), "kind": "bytes"}])
        self.assertEqual(result["root"]["row_count"], 3)
        self.assertEqual(result["provenance"]["tables_created"], 6)
        self.assertEqual(result["provenance"]["writes"], 14)

    def test_nested_matches_hits_and_negatives(self):
        result = self.nested()
        desc = b(b"go to ch1_ygg_edge")
        record = ["table", [
            [b(b"Description"), ["table", [[["number", TWO], b(b"x")], [["number", ONE], desc]]]],
            [b(b"Map"), b(b"ygg_roots")],
            [b(b"RewardItemList"), ["table", [[["number", ONE], ["table", [
                [b(b"Count"), ["number", ONE]], [b(b"ItemID"), ["number", TWO]]]]]]]],
            [b(b"Title"), b(b"Roots")]]]
        self.assertEqual(result["matches"], [
            {"key": ["number", TWO], "record": b(b"ch1_ch1_"), "clues": ["ch1_"],
             "hits": [{"path": [], "value_hex": b"ch1_ch1_".hex(), "clue": "ch1_", "offsets": [0, 4]}]},
            {"key": ["number", ONE], "record": record, "clues": ["ch1_", "ygg_roots", "ygg_edge"],
             "hits": [
                 {"path": [b(b"Description"), ["number", ONE]], "value_hex": desc[1],
                  "clue": "ch1_", "offsets": [6]},
                 {"path": [b(b"Description"), ["number", ONE]], "value_hex": desc[1],
                  "clue": "ygg_edge", "offsets": [10]},
                 {"path": [b(b"Map")], "value_hex": b"ygg_roots".hex(), "clue": "ygg_roots",
                  "offsets": [0]}]}])
        self.assertEqual(result["negatives"], ["ygg_fruit", "mu_fild01", "prt_fild05", "pay_fild01"])

    def test_bool_number_string_keys_stay_distinct(self):
        a = Asm().new(0).set(0, True, b"t").set(0, 1.0, b"n").set(0, b"1", b"s").set(0, False, b"f")
        result = qti.inventory_bytes(a.glob(0, QIL).chunk())
        self.assertEqual([(r["key"], r["kind"]) for r in result["rows"]], [
            (["bool", False], "bytes"), (["bool", True], "bytes"),
            (["bytes", "31"], "bytes"), (["number", ONE], "bytes")])
        self.assertEqual(result["provenance"]["repeated_writes"], [])

    def test_zero_signed_zero_and_setlist_key_coalescing(self):
        a = Asm().new(0).set(0, -0.0, -0.0)
        second = a.pc()
        a.set(0, 0.0, 1.0).set(0, 2.0, -0.0).loadk(1, b"list")
        third = a.pc()
        a.emit(abc("SETLIST", 0, 1, 1))
        fourth = a.pc()
        a.set(0, 1.0, b"const").glob(0, QIL)
        result = qti.inventory_bytes(a.chunk())
        self.assertEqual([r["key"] for r in result["rows"]],
                         [["number", ZERO], ["number", TWO], ["number", ONE]])
        self.assertEqual(result["rows"][0]["sha256"], sha(b'["number","000000000000f03f"]'))
        self.assertEqual(result["rows"][1]["sha256"], sha(b'["number","0000000000000080"]'))
        self.assertEqual(result["provenance"]["repeated_writes"], [
            {"pc": second, "table": 1, "key": ["number", ZERO], "existed": True,
             "before": ["number", NEG_ZERO], "after": ["number", ONE]},
            {"pc": fourth, "table": 1, "key": ["number", ONE], "existed": True,
             "before": b(b"list"), "after": b(b"const")}])
        self.assertEqual(third, fourth - 1)

    def test_repeated_id_and_field_last_write(self):
        a = Asm().new(0).new(1).set(1, b"A", b"x")
        field = a.pc()
        a.set(1, b"A", b"y").set(0, 5.0, R(1)).new(1).set(1, b"B", b"z")
        row = a.pc()
        a.set(0, 5.0, R(1)).glob(0, QIL)
        result = qti.inventory_bytes(a.chunk())
        self.assertEqual(result["provenance"]["repeated_writes"], [
            {"pc": field, "table": 2, "key": b(b"A"), "existed": True,
             "before": b(b"x"), "after": b(b"y")},
            {"pc": row, "table": 1, "key": ["number", "0000000000001440"], "existed": True,
             "before": ["table-ref", 2], "after": ["table-ref", 3]}])
        self.assertEqual(result["rows"][0]["fields"], [{"key": b(b"B"), "kind": "bytes"}])
        self.assertEqual(result["rows"][0]["sha256"],
                         sha(b'["table",[[["bytes","42"],["bytes","7a"]]]]'))

    def test_nil_deletion_and_repeated_deletion(self):
        a = Asm().new(0).new(1).set(0, 1.0, R(1)).set(0, 2.0, b"k").emit(abc("LOADNIL", 5, 5))
        first = a.pc()
        a.set(0, 1.0, R(5))
        again = a.pc()
        a.set(0, 1.0, None)  # nil constant
        fresh = a.pc()
        a.set(0, 9.0, R(5)).glob(0, QIL)
        result = qti.inventory_bytes(a.chunk())
        e1 = {"pc": first, "table": 1, "key": ["number", ONE], "existed": True,
              "before": ["table-ref", 2], "after": ["nil"]}
        e2 = {"pc": again, "table": 1, "key": ["number", ONE], "existed": False,
              "before": ["absent"], "after": ["nil"]}
        e3 = {"pc": fresh, "table": 1, "key": ["number", "0000000000002240"], "existed": False,
              "before": ["absent"], "after": ["nil"]}
        self.assertEqual(result["provenance"]["nil_writes"], [e1, e2, e3])
        self.assertEqual(result["provenance"]["repeated_writes"], [e1, e2])
        self.assertEqual([r["key"] for r in result["rows"]], [["number", TWO]])
        self.assertEqual(result["provenance"]["writes"], 5)

    def test_whole_global_replacement_and_global_nil(self):
        a = Asm().new(0).set(0, 1.0, b"old")
        g1 = a.pc()
        a.glob(0, QIL).new(0).set(0, 1.0, b"new")
        g2 = a.pc()
        a.glob(0, QIL).loadk(1, 1.0)
        g3 = a.pc()
        a.glob(1, b"X").emit(abc("LOADNIL", 1, 1))
        g4 = a.pc()
        a.glob(1, b"X")
        result = qti.inventory_bytes(a.chunk())
        self.assertEqual(result["provenance"]["global_assignments"], [
            {"pc": g1, "name_hex": QIL_HEX, "existed": False, "before": ["absent"], "after": ["table-ref", 1]},
            {"pc": g2, "name_hex": QIL_HEX, "existed": True, "before": ["table-ref", 1],
             "after": ["table-ref", 2]},
            {"pc": g3, "name_hex": "58", "existed": False, "before": ["absent"], "after": ["number", ONE]},
            {"pc": g4, "name_hex": "58", "existed": True, "before": ["number", ONE], "after": ["nil"]}])
        self.assertEqual(result["globals"], [QIL_HEX])
        self.assertEqual(result["root"]["table_ordinal"], 2)
        self.assertEqual(result["provenance"]["repeated_writes"], [])
        self.assertEqual(result["matches"], [])

    def test_nul_and_non_utf8_bytes_preserved(self):
        raw = b"\x00ch1_\xff\xfe"
        a = Asm().new(0).new(1).set(1, b"\xb0\xa1", raw).set(0, 1.0, R(1)).glob(0, QIL)
        result = qti.inventory_bytes(a.chunk())
        self.assertEqual(result["rows"][0]["fields"], [{"key": ["bytes", "b0a1"], "kind": "bytes"}])
        self.assertEqual(result["matches"][0]["hits"], [
            {"path": [["bytes", "b0a1"]], "value_hex": raw.hex(),
             "clue": "ch1_", "offsets": [1]}])

    def test_empty_root_and_extra_globals_with_closure(self):
        child = proto([abc("RETURN", 0, 1)], [])
        a = Asm().new(0).glob(0, QIL).emit(abx("CLOSURE", 1, 0))
        pc = a.pc()
        a.glob(1, b"f").new(2).set(2, b"fn", R(1)).glob(2, b"G")
        result = qti.inventory_bytes(a.chunk(children=[child]))
        self.assertEqual(result["prototype"], {"instructions": 8, "constants": 4, "children": 1})
        self.assertEqual(result["globals"], ["47", QIL_HEX, "66"])
        self.assertEqual(result["provenance"]["global_assignments"][1],
                         {"pc": pc, "name_hex": "66", "existed": False, "before": ["absent"],
                          "after": ["closure-ref", 0]})
        self.assertEqual(result["root"]["row_count"], 0)
        self.assertEqual(result["root"]["sha256"], sha(b'["table",[]]'))
        self.assertEqual(result["negatives"], CLUE_NAMES)

    def test_table_shared_outside_selection_is_allowed(self):
        a = Asm().new(0).new(1).set(0, b"a", R(1)).glob(1, b"Other").glob(0, QIL)
        self.assertEqual(qti.inventory_bytes(a.chunk())["root"]["row_count"], 1)

    def test_depth_limit_32_accepted(self):
        self.assertEqual(qti.inventory_bytes(chain(31))["provenance"]["tables_created"], 32)

    def test_deterministic(self):
        self.assertEqual(json.dumps(self.nested(), sort_keys=True), json.dumps(self.nested(), sort_keys=True))


class Refusals(unittest.TestCase):
    def ok_prefix(self):
        return Asm().new(0).glob(0, QIL)

    def test_missing_and_wrong_root(self):
        refuses(self, Asm().new(0).glob(0, b"questinfolist").chunk(), "root-missing")
        refuses(self, Asm().loadk(0, b"x").glob(0, QIL).chunk(), "root-kind")
        refuses(self, Asm().new(0).glob(0, QIL).emit(abc("LOADNIL", 0, 0)).glob(0, QIL).chunk(),
                "root-missing")
        refuses(self, Asm().chunk(), "root-missing")

    def test_input_type_size_header_eof(self):
        refuses(self, "text", "input-type")
        refuses(self, b"\x1b" * (3 * 1024 * 1024 + 1), "input-size")
        good = self.ok_prefix().chunk()
        refuses(self, b"\x1bLuaQ\x00\x01\x04\x04\x04\x08\x01" + good[12:], "chunk")
        self.assertIn("truncated", refuses(self, good[:-1], "chunk"))
        self.assertIn("trailing", refuses(self, good + b"\0", "chunk"))
        bad = HEADER + proto([abc("RETURN", 0, 1)], [], ncode=0xFFFFFFFF)
        self.assertIn("exceeds remaining", refuses(self, bad, "chunk"))

    def test_registers_and_constants(self):
        refuses(self, Asm().new(8).chunk(maxstack=8), "register")
        refuses(self, Asm().emit(abx("LOADK", 0, 3)).chunk(), "constant")
        refuses(self, Asm().loadk(0, b"s").set(0, b"a", b"b").chunk(), "non-table")

    def test_reversed_loadnil(self):
        msg = refuses(self, self.ok_prefix().emit(abc("LOADNIL", 3, 1)).chunk(), "loadnil")
        self.assertIn("reversed", msg)
        qti.inventory_bytes(self.ok_prefix().emit(abc("LOADNIL", 1, 3)).chunk())

    def test_unsupported_instructions(self):
        for word in (abc("CALL", 0, 1, 1), abx("JMP", 0, 131071), abx("GETGLOBAL", 0, 0),
                     abc("LOADBOOL", 0, 1, 1), 50):
            refuses(self, self.ok_prefix().emit(word).chunk(), "unsupported")

    def test_setlist_forms(self):
        refuses(self, self.ok_prefix().emit(abc("SETLIST", 0, 0, 1)).chunk(), "setlist")
        refuses(self, self.ok_prefix().emit(abc("SETLIST", 0, 1, 0), 0).chunk(), "setlist")
        refuses(self, self.ok_prefix().emit(abc("SETLIST", 0, 1, 0)).chunk(ret=False), "setlist")
        a = Asm().new(0).loadk(1, b"v").emit(abc("SETLIST", 0, 1, 0), 2).glob(0, QIL)
        result = qti.inventory_bytes(a.chunk())  # block 2 -> key 51
        self.assertEqual(result["rows"][0]["key"], ["number", "0000000000804940"])

    def test_return_and_main_chunk(self):
        refuses(self, self.ok_prefix().chunk(ret=False), "return")
        refuses(self, self.ok_prefix().emit(abc("RETURN", 0, 1)).new(1).chunk(), "return")
        refuses(self, self.ok_prefix().emit(abc("RETURN", 0, 2)).chunk(ret=False), "return")
        refuses(self, self.ok_prefix().chunk(nups=1), "main-chunk")

    def test_keys_and_values(self):
        inf, nan = float("inf"), float("nan")
        refuses(self, Asm().new(0).set(0, nan, b"v").chunk(), "key")
        refuses(self, Asm().new(0).set(0, inf, b"v").chunk(), "key")
        refuses(self, Asm().new(0).set(0, None, b"v").chunk(), "key")
        refuses(self, Asm().new(0).new(1).set(0, R(1), b"v").chunk(), "key")
        refuses(self, Asm().new(0).set(0, b"v", -inf).chunk(), "value")
        refuses(self, Asm().loadk(0, inf).glob(0, b"X").chunk(), "value")
        refuses(self, Asm().loadk(1, 1.0).emit(abx("SETGLOBAL", 1, 0)).chunk(), "global")

    def test_closures(self):
        child = proto([abc("RETURN", 0, 1)], [])
        a = Asm().new(0).emit(abx("CLOSURE", 1, 0)).set(0, b"f", R(1)).glob(0, QIL)
        refuses(self, a.chunk(children=[child]), "selected-closure")
        refuses(self, Asm().emit(abx("CLOSURE", 1, 1)).chunk(children=[child]), "closure")
        upv = proto([abc("RETURN", 0, 1)], [], nups=1)
        refuses(self, Asm().emit(abx("CLOSURE", 1, 0)).chunk(children=[upv]), "closure")

    def test_shared_cyclic_depth(self):
        refuses(self, Asm().new(0).new(1).set(0, b"a", R(1)).set(0, b"b", R(1)).glob(0, QIL).chunk(),
                "selected-shared")
        refuses(self, Asm().new(0).set(0, b"self", R(0)).glob(0, QIL).chunk(), "selected-cyclic")
        refuses(self, chain(32), "selected-depth")

    def test_selected_and_result_size(self):
        big = b"ch1_" + b"a" * (1024 * 1024)
        a = Asm().new(0).loadk(1, big)
        for n in range(17):  # 17 * ~2 MiB of hex > 32 MiB
            a.set(0, float(n + 1), R(1))
        refuses(self, a.glob(0, QIL).chunk(), "selected-size")
        a = Asm().new(0).loadk(1, big)
        for n in range(5):  # ~10 MiB selected (accepted) but the records exceed 8 MiB
            a.set(0, float(n + 1), R(1))
        refuses(self, a.glob(0, QIL).chunk(), "result-size")
        a = Asm().new(0).new(2).loadk(1, big)
        for n in range(4):  # provenance budget refuses during replay
            a.set(2, b"k", R(1))
        refuses(self, a.glob(0, QIL).chunk(), "result-size")

    def test_programming_failure_is_not_a_refusal(self):
        a = Asm().new(0).set(0, 1.0, b"v").glob(0, QIL)
        with mock.patch.object(qti, "_typed_scalar", side_effect=RuntimeError("bug")):
            with self.assertRaises(RuntimeError):
                qti.inventory_bytes(a.chunk())

    def test_reader_source_pinned(self):
        source = (TOOLS / "tw_iteminfo_utf8.py").read_bytes()
        self.assertEqual(hashlib.sha256(source).hexdigest(),
                         "6155b81377c20a9b028e64ec82548ca5f611563734b156dded8fd4937e70343d")
        self.assertEqual(qti.READER_SHA256, hashlib.sha256(source).hexdigest())


if __name__ == "__main__":
    unittest.main()
