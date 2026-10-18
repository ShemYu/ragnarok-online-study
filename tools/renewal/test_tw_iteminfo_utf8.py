"""Synthetic tests for tw_iteminfo_utf8. Run: python3 -m unittest discover tools/renewal"""

import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tw_iteminfo_utf8 as conv  # noqa: E402

OP = {name: n for n, name in enumerate(conv.OPNAMES)}
K = 256  # RK constant flag


def abc(op, a, b=0, c=0):
    return OP[op] | a << 6 | c << 14 | b << 23


def abx(op, a, bx):
    return OP[op] | a << 6 | bx << 14


def lstr(value):
    if value is None:
        return struct.pack("<I", 0)
    return struct.pack("<I", len(value) + 1) + value + b"\0"


def proto(code, constants, maxstack=8, nups=0, children=()):
    out = lstr(b"@t") + struct.pack("<II", 0, 0) + bytes([nups, 0, 2, maxstack])
    out += struct.pack("<I", len(code)) + b"".join(struct.pack("<I", w) for w in code)
    out += struct.pack("<I", len(constants))
    for value in constants:
        if value is None:
            out += b"\0"
        elif isinstance(value, bool):
            out += b"\1" + bytes([value])
        elif isinstance(value, (int, float)):
            out += b"\3" + struct.pack("<d", value)
        else:
            out += b"\4" + lstr(value)
    out += struct.pack("<I", len(children)) + b"".join(children)
    return out + struct.pack("<III", 0, 0, 0)


def chunk(code, constants, **kw):
    return conv.HEADER + proto(code, constants, **kw)


def item_chunk(items, extra_code=()):
    """tbl = { [id] = { field = value, ... }, ... } assembled as SETTABLEs."""
    constants, code = [b"tbl"], [abc("NEWTABLE", 0)]

    def k(value):
        if value not in constants or isinstance(value, bool):
            constants.append(value)
            return len(constants) - 1
        return constants.index(value)

    for ident, fields in items:
        code.append(abc("NEWTABLE", 1))
        for key, value in fields:
            if isinstance(value, list):
                code.append(abc("NEWTABLE", 2))
                for j, line in enumerate(value, 1):
                    code.append(abx("LOADK", 2 + j, k(line)))
                code.append(abc("SETLIST", 2, len(value), 1))
                code.append(abc("SETTABLE", 1, K | k(key), 2))
            elif value is None:
                code.append(abc("LOADNIL", 2, 2))
                code.append(abc("SETTABLE", 1, K | k(key), 2))
            else:
                code.append(abc("SETTABLE", 1, K | k(key), K | k(value)))
        code.append(abc("SETTABLE", 0, K | k(float(ident)), 1))
    code += list(extra_code)
    code += [abx("SETGLOBAL", 0, 0), abc("RETURN", 0, 1)]
    return chunk(code, constants, maxstack=60)


def convert(data):
    return conv.convert_bytes(data, hashlib.sha256(data).hexdigest())


class ConvertTests(unittest.TestCase):
    def test_round_trip_escapes_types_utf8(self):
        tricky = 'q"uote\\back\nline\r\t\x01\x7f 放大鏡'.encode()
        data = item_chunk([
            (611, [(b"identifiedDisplayName", tricky), (b"identifiedResourceName", "돋보기".encode()),
                   (b"slotCount", 2.0), (b"weight", 1.5), (b"costume", False),
                   (b"identifiedDescriptionName", [b"a", "多行\n說明".encode()]),
                   (b"end", b"keyword key"), (b"with space", b"x")]),
        ])
        source, meta = convert(data)
        text = source.decode("utf-8")
        self.assertIn("放大鏡", text)  # raw UTF-8, not escaped
        self.assertIn('identifiedResourceName = "돋보기"', text)
        self.assertIn(r'"q\"uote\\back\nline\r\t\001\127 放大鏡"', text)
        self.assertIn('["end"] = "keyword key"', text)
        self.assertIn('["with space"] = "x"', text)
        self.assertIn("slotCount = 2,", text)
        self.assertIn("weight = 1.5,", text)
        self.assertIn("costume = false", text)
        self.assertEqual(meta["table"]["entries"], 1)
        self.assertTrue(meta["readback_equal"])
        self.assertEqual(convert(data)[0], source)  # deterministic

    def test_duplicate_root_and_field_use_last_write_and_nil_deletes(self):
        data = item_chunk([
            (1, [(b"identifiedDisplayName", b"old"), (b"identifiedDisplayName", "新".encode())]),
            (1, [(b"identifiedDisplayName", "最後".encode()), (b"slotCount", 1.0), (b"slotCount", None)]),
            (2, [(b"identifiedDisplayName", "二".encode())]),
        ])
        source, meta = convert(data)
        tbl = conv.SourceReader(source).chunk()
        self.assertEqual(tbl.get(("n", 1)).items, {("s", b"identifiedDisplayName"): "最後".encode()})
        self.assertEqual(meta["table"]["root_overwrites"], 1)
        self.assertNotIn(b"old", source)
        self.assertNotIn(b"slotCount", source)

    def test_numeric_keys_normalize_like_lua(self):
        table = conv.LuaTable()
        table.set(conv.lua_key(1.0, "t"), b"a")
        table.set(conv.lua_key(True, "t"), b"b")
        self.assertEqual(len(table.items), 2)  # true and 1 are distinct keys
        with self.assertRaises(conv.ConvertError):
            conv.lua_key(float("nan"), "t")
        with self.assertRaises(conv.ConvertError):
            conv.lua_key(None, "t")

    def test_hash_guard(self):
        data = item_chunk([(1, [(b"identifiedDisplayName", "一".encode())])])
        with self.assertRaisesRegex(conv.ConvertError, "SHA-256"):
            conv.convert_bytes(data)

    def test_rejects_malformed_input(self):
        good = item_chunk([(1, [(b"identifiedDisplayName", "一".encode())])])
        cases = {
            "bad header": b"\x1bLuaR" + good[5:],
            "truncated": good[:-5],
            "trailing": good + b"\0",
            "huge count": conv.HEADER + lstr(b"@t") + struct.pack("<II", 0, 0) + bytes(4)
            + struct.pack("<I", 0xFFFFFFF0),
            "empty": b"",
        }
        for name, data in cases.items():
            with self.subTest(name), self.assertRaises(conv.ConvertError):
                convert(data)

    def test_rejects_unsupported_code_and_values(self):
        cases = {
            "call": chunk([abc("CALL", 0, 1, 1), abc("RETURN", 0, 1)], []),
            "getglobal": chunk([abx("GETGLOBAL", 0, 0), abc("RETURN", 0, 1)], [b"x"]),
            "jump": chunk([abc("JMP", 0), abc("RETURN", 0, 1)], []),
            "loadbool skip": chunk([abc("LOADBOOL", 0, 1, 1), abc("RETURN", 0, 1)], []),
            "dynamic setlist": chunk([abc("NEWTABLE", 0), abc("SETLIST", 0, 0, 1),
                                      abc("RETURN", 0, 1)], []),
            "register overflow": chunk([abx("LOADK", 9, 0), abc("RETURN", 0, 1)], [1.0], maxstack=2),
            "constant overflow": chunk([abx("LOADK", 0, 5), abc("RETURN", 0, 1)], [1.0]),
            "early return": chunk([abc("RETURN", 0, 1), abc("RETURN", 0, 1)], []),
            "no tbl": chunk([abc("RETURN", 0, 1)], []),
            "invalid utf8": item_chunk([(1, [(b"identifiedDisplayName", b"\xb4\xfa")])]),
            "string root key": chunk([abc("NEWTABLE", 0), abc("NEWTABLE", 1),
                                      abc("SETTABLE", 0, K | 1, 1), abx("SETGLOBAL", 0, 0),
                                      abc("RETURN", 0, 1)], [b"tbl", b"x"]),
            "non-table item": chunk([abc("NEWTABLE", 0), abc("SETTABLE", 0, K | 1, K | 1),
                                     abx("SETGLOBAL", 0, 0), abc("RETURN", 0, 1)], [b"tbl", 5.0]),
            "shared table": chunk([abc("NEWTABLE", 0), abc("NEWTABLE", 1),
                                   abc("SETTABLE", 0, K | 1, 1), abc("SETTABLE", 0, K | 2, 1),
                                   abx("SETGLOBAL", 0, 0), abc("RETURN", 0, 1)],
                                  [b"tbl", 1.0, 2.0]),
            "cyclic table": chunk([abc("NEWTABLE", 0), abc("NEWTABLE", 1),
                                   abc("SETTABLE", 1, K | 2, 1), abc("SETTABLE", 0, K | 1, 1),
                                   abx("SETGLOBAL", 0, 0), abc("RETURN", 0, 1)],
                                  [b"tbl", 1.0, b"self"]),
            "closure value": chunk([abc("NEWTABLE", 0), abx("CLOSURE", 1, 0),
                                    abc("SETTABLE", 0, K | 1, 1), abx("SETGLOBAL", 0, 0),
                                    abc("RETURN", 0, 1)], [b"tbl", 1.0],
                                   children=[proto([abc("RETURN", 0, 1)], [])]),
            "non-finite value": item_chunk([(1, [(b"x", float("inf"))])]),
        }
        for name, data in cases.items():
            with self.subTest(name), self.assertRaises(conv.ConvertError):
                convert(data)

    def test_ignores_unexecuted_function_globals(self):
        data = chunk([abx("CLOSURE", 2, 0), abx("SETGLOBAL", 2, 2),
                      abc("NEWTABLE", 0), abc("NEWTABLE", 1), abc("SETTABLE", 1, K | 3, K | 4),
                      abc("SETTABLE", 0, K | 1, 1), abx("SETGLOBAL", 0, 0), abc("RETURN", 0, 1)],
                     [b"tbl", 7.0, b"main", b"identifiedDisplayName", "七".encode()],
                     children=[proto([abc("CALL", 0, 1, 1), abc("RETURN", 0, 1)], [])])
        source, meta = convert(data)
        self.assertIn("七".encode(), source)
        self.assertEqual(meta["ignored_globals"], ["main"])
        self.assertNotIn(b"main", source)

    def test_write_output_layout_and_no_overwrite(self):
        data = item_chunk([(1, [(b"identifiedDisplayName", "一".encode())])])
        source, meta = convert(data)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            written = conv.write_output(out, source, meta)
            item_info = out / conv.MOD_NAME / "System" / "itemInfo.lua"
            self.assertEqual(item_info.read_bytes(), source)
            mod = json.loads((out / conv.MOD_NAME / "mod.json").read_text("utf-8"))
            self.assertEqual(mod["requires"], {"app": ">=1.6.3", "era": "renewal", "client": "twRO"})
            manifest = json.loads((out / "conversion-manifest.json").read_text("utf-8"))
            self.assertEqual(manifest["output"]["itemInfo.lua"]["sha256"],
                             hashlib.sha256(source).hexdigest())
            self.assertEqual(written["output"], manifest["output"])
            with self.assertRaisesRegex(conv.ConvertError, "refusing to overwrite"):
                conv.write_output(out, b"x", meta)
            self.assertEqual(item_info.read_bytes(), source)
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["out"])

    def test_cli_rejects_wrong_hash_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "iteminfo.lub"
            src.write_bytes(item_chunk([(1, [(b"identifiedDisplayName", "一".encode())])]))
            out = Path(tmp) / "out"
            self.assertEqual(conv.main([str(src), str(out)]), 2)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
