#!/usr/bin/env python3
"""Convert the pinned Taiwan modern `iteminfo_new.lub` into a UTF-8 source mod.

The input is a compiled Lua 5.1 chunk. It is never executed: a bounded reader
checks the chunk layout, then only the top-level literal-construction
instructions are interpreted (layout and opcodes per lua.org/source/5.1
lundump.c and lopcodes.h). Anything else -- calls, jumps, upvalues, arithmetic,
dynamic counts -- is rejected rather than guessed.

The final global `tbl` is written as `System/itemInfo.lua` of a client-only
mod, as plain UTF-8 Lua source with actual non-ASCII bytes, so roBrowser's
whole-file UTF-8 detection (DBManager.js isUtf8Table) selects its UTF-8 path.
The written source is parsed back and compared with the reconstructed table
before anything is published.

Standard library only. Output directories are never overwritten.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import struct
import sys
import tempfile

VERSION = "1.0.1"
PINNED_SHA256 = "0c70abe66e6978c55886b9e4acf8a491028f3c439abc1324cef183577a3e2f19"
# Consistency checks for the pinned input only (T04.002 diagnosis).
PINNED_EXPECT = {"entries": 20442, "root_overwrites": 277, "utf8_strings": 440663}
MOD_NAME = "tw-iteminfo-utf8"
MOD_JSON = {
    "name": MOD_NAME,
    "version": VERSION,
    "author": "local converter",
    "description": "Taiwan client item names, descriptions and art from its modern "
                   "item table, rewritten as UTF-8 source. Client tables only.",
    "requires": {"app": ">=1.6.3", "era": "renewal", "client": "twRO"},
}

HEADER = bytes.fromhex("1b4c7561" "51" "00" "01" "04" "04" "04" "08" "00")
OPNAMES = ("MOVE LOADK LOADBOOL LOADNIL GETUPVAL GETGLOBAL GETTABLE SETGLOBAL "
           "SETUPVAL SETTABLE NEWTABLE SELF ADD SUB MUL DIV MOD POW UNM NOT LEN "
           "CONCAT JMP EQ LT LE TEST TESTSET CALL TAILCALL RETURN FORLOOP FORPREP "
           "TFORLOOP SETLIST CLOSE CLOSURE VARARG").split()
FIELDS_PER_FLUSH = 50
MAX_PROTO_DEPTH = 64
MAX_TABLE_DEPTH = 32
LUA_KEYWORDS = set("and break do else elseif end false for function if in local "
                   "nil not or repeat return then true until while goto".split())
IDENT = re.compile(rb"[A-Za-z_][A-Za-z0-9_]*\Z")


class ConvertError(ValueError):
    """Input or output that cannot be converted without guessing."""


class Closure:
    """An unexecuted function prototype; never a valid table value."""

    def __init__(self, index):
        self.index = index


class LuaTable:
    """A Lua table. Keys are tagged so True, 1 and 1.0 behave as in Lua."""

    def __init__(self):
        self.items = {}

    def set(self, key, value):
        if value is None:
            self.items.pop(key, None)
        else:
            self.items[key] = value

    def get(self, key):
        return self.items.get(key)


def lua_key(value, where):
    """Tag a Lua value for use as a table key, rejecting what Lua rejects."""
    if isinstance(value, bool):
        return ("b", value)
    if isinstance(value, float):
        if math.isnan(value):
            raise ConvertError(f"{where}: NaN table key")
        if math.isinf(value):
            return ("n", value)
        return ("n", int(value) if value == int(value) else value)
    if isinstance(value, bytes):
        return ("s", value)
    if value is None:
        raise ConvertError(f"{where}: nil table key")
    raise ConvertError(f"{where}: unsupported table key type {type(value).__name__}")


# --- Bounded Lua 5.1 chunk reader -----------------------------------------

class Reader:
    def __init__(self, data):
        if not isinstance(data, (bytes, bytearray)):
            raise ConvertError("input must be bytes")
        if data[:len(HEADER)] != HEADER:
            raise ConvertError("not a little-endian Lua 5.1 chunk with 4-byte int/size_t/"
                               "instruction and 8-byte double numbers")
        self.data, self.pos = bytes(data), len(HEADER)

    def take(self, size):
        if size < 0 or self.pos + size > len(self.data):
            raise ConvertError(f"truncated input at byte {self.pos} (need {size})")
        value = self.data[self.pos:self.pos + size]
        self.pos += size
        return value

    def uint(self):
        return struct.unpack("<I", self.take(4))[0]

    def count(self, min_size, what):
        n = self.uint()
        if n * min_size > len(self.data) - self.pos:
            raise ConvertError(f"{what} count {n} exceeds remaining input at byte {self.pos}")
        return n

    def string(self):
        size = self.count(1, "string")
        if size == 0:
            return None
        value = self.take(size)
        if value[-1] != 0:
            raise ConvertError(f"string without terminating NUL ending at byte {self.pos}")
        return value[:-1]

    def proto(self, depth=0):
        if depth > MAX_PROTO_DEPTH:
            raise ConvertError("function prototypes nested too deeply")
        self.string()  # source name
        self.uint(), self.uint()  # line defined, last line defined
        nups, numparams, is_vararg, maxstack = self.take(4)
        code = [self.uint() for _ in range(self.count(4, "instruction"))]
        constants = []
        for _ in range(self.count(1, "constant")):
            kind = self.take(1)[0]
            if kind == 0:
                constants.append(None)
            elif kind == 1:
                flag = self.take(1)[0]
                if flag > 1:
                    raise ConvertError(f"invalid boolean constant {flag}")
                constants.append(bool(flag))
            elif kind == 3:
                constants.append(struct.unpack("<d", self.take(8))[0])
            elif kind == 4:
                value = self.string()
                if value is None:
                    raise ConvertError("null string constant")
                constants.append(value)
            else:
                raise ConvertError(f"unsupported constant type {kind}")
        children = [self.proto(depth + 1) for _ in range(self.count(12, "prototype"))]
        lines = [self.uint() for _ in range(self.count(4, "line info"))]
        if lines and len(lines) != len(code):
            raise ConvertError("line info does not match instruction count")
        for _ in range(self.count(12, "local")):
            self.string(), self.uint(), self.uint()
        upvalue_names = [self.string() for _ in range(self.count(4, "upvalue name"))]
        if upvalue_names and len(upvalue_names) != nups:
            raise ConvertError("upvalue names do not match upvalue count")
        return dict(nups=nups, numparams=numparams, is_vararg=is_vararg,
                    maxstack=maxstack, code=code, constants=constants,
                    children=children)


def read_chunk(data):
    reader = Reader(data)
    proto = reader.proto()
    if reader.pos != len(reader.data):
        raise ConvertError(f"{len(reader.data) - reader.pos} trailing bytes after chunk")
    return proto


# --- Literal-construction interpreter ---------------------------------------

def reconstruct(proto):
    """Return (globals, stats) built by the main chunk's literal instructions."""
    if proto["nups"] or proto["numparams"]:
        raise ConvertError("main chunk must have no upvalues or parameters")
    code, constants = proto["code"], proto["constants"]
    regs = [None] * proto["maxstack"]
    globals_ = {}
    stats = {"root_overwrites": 0, "writes": 0}
    root_counts = {}
    pc = 0
    saw_terminal_return = False

    def reg(n, i):
        if n >= len(regs):
            raise ConvertError(f"pc {i + 1}: register {n} beyond stack size {len(regs)}")
        return n

    def const(n, i):
        if n >= len(constants):
            raise ConvertError(f"pc {i + 1}: constant {n} out of range")
        return constants[n]

    def rk(n, i):
        return const(n & 255, i) if n & 256 else regs[reg(n, i)]

    def put(table, key, value, i):
        where = f"pc {i + 1}"
        if not isinstance(table, LuaTable):
            raise ConvertError(f"{where}: assignment into a non-table value")
        if isinstance(value, Closure):
            raise ConvertError(f"{where}: function stored in a table")
        if isinstance(value, float) and not math.isfinite(value):
            raise ConvertError(f"{where}: non-finite number value")
        tagged = lua_key(key, where)
        table.set(tagged, value)
        stats["writes"] += 1
        seen = root_counts.setdefault(id(table), {})
        seen[tagged] = seen.get(tagged, 0) + 1

    while pc < len(code):
        i, word = pc, code[pc]
        pc += 1
        op = word & 63
        a, c, b, bx = word >> 6 & 255, word >> 14 & 511, word >> 23 & 511, word >> 14
        name = OPNAMES[op] if op < len(OPNAMES) else f"op{op}"
        if name == "MOVE":
            regs[reg(a, i)] = regs[reg(b, i)]
        elif name == "LOADK":
            regs[reg(a, i)] = const(bx, i)
        elif name == "LOADBOOL":
            if c:
                raise ConvertError(f"pc {i + 1}: LOADBOOL skip is control flow")
            regs[reg(a, i)] = bool(b)
        elif name == "LOADNIL":
            for r in range(reg(a, i), reg(b, i) + 1):
                regs[r] = None
        elif name == "NEWTABLE":
            regs[reg(a, i)] = LuaTable()
        elif name == "SETTABLE":
            put(regs[reg(a, i)], rk(b, i), rk(c, i), i)
        elif name == "SETLIST":
            if b == 0:
                raise ConvertError(f"pc {i + 1}: open-ended SETLIST is unsupported")
            if c == 0:
                if pc >= len(code):
                    raise ConvertError(f"pc {i + 1}: SETLIST block number missing")
                c, pc = code[pc], pc + 1
            if c == 0:
                raise ConvertError(f"pc {i + 1}: SETLIST block number zero")
            reg(a + b, i)
            for j in range(1, b + 1):
                put(regs[a], float((c - 1) * FIELDS_PER_FLUSH + j), regs[a + j], i)
        elif name == "SETGLOBAL":
            key = const(bx, i)
            if not isinstance(key, bytes):
                raise ConvertError(f"pc {i + 1}: non-string global name")
            globals_[key] = regs[reg(a, i)]
        elif name == "CLOSURE":
            if bx >= len(proto["children"]):
                raise ConvertError(f"pc {i + 1}: closure prototype out of range")
            if proto["children"][bx]["nups"]:
                raise ConvertError(f"pc {i + 1}: closure upvalue binding is unsupported")
            regs[reg(a, i)] = Closure(bx)
        elif name == "RETURN":
            if b != 1 or pc != len(code):
                raise ConvertError(f"pc {i + 1}: only a terminal no-value RETURN is accepted")
            saw_terminal_return = True
        else:
            raise ConvertError(f"pc {i + 1}: unsupported instruction {name}")
    if not saw_terminal_return:
        raise ConvertError("main chunk has no terminal no-value RETURN")
    tbl = globals_.get(b"tbl")
    if tbl is not None and id(tbl) in root_counts:
        stats["root_overwrites"] = sum(n - 1 for n in root_counts[id(tbl)].values())
    return globals_, stats


# --- Validation ---------------------------------------------------------------

def validate_item_table(tbl):
    """Check the root shape and strict UTF-8; return counts. Rejects shared/cyclic tables."""
    if not isinstance(tbl, LuaTable):
        raise ConvertError("global tbl is missing or not a table")
    if not tbl.items:
        raise ConvertError("global tbl is empty")
    counts = {"entries": 0, "item_fields": 0, "utf8_strings": 0, "nested_tables": 0,
              "missing_identifiedDisplayName": 0, "field_presence": {},
              "non_string_field_keys": []}
    seen = set()

    def walk(value, depth, path):
        if isinstance(value, bytes):
            try:
                value.decode("utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                raise ConvertError(f"{path}: invalid UTF-8 ({exc.reason})") from None
            counts["utf8_strings"] += 1
        elif isinstance(value, LuaTable):
            if id(value) in seen:
                raise ConvertError(f"{path}: shared or cyclic table reference")
            if depth > MAX_TABLE_DEPTH:
                raise ConvertError(f"{path}: tables nested too deeply")
            seen.add(id(value))
            counts["nested_tables"] += 1
            for (tag, key), sub in value.items.items():
                if tag == "s":
                    walk(key, depth + 1, path)
                walk(sub, depth + 1, f"{path}[{key!r}]")
        elif isinstance(value, float):
            if not math.isfinite(value):
                raise ConvertError(f"{path}: non-finite number")
        elif not isinstance(value, bool):
            raise ConvertError(f"{path}: unexpected value type {type(value).__name__}")

    seen.add(id(tbl))
    for (tag, ident), item in tbl.items.items():
        if tag != "n" or not isinstance(ident, int) or ident <= 0:
            raise ConvertError(f"tbl key {ident!r} is not a positive integer item ID")
        if not isinstance(item, LuaTable):
            raise ConvertError(f"tbl[{ident}] is not a table")
        counts["entries"] += 1
        for (ktag, key) in item.items:
            if ktag != "s":
                # Kept as data (e.g. a stray positional string); reported, not dropped.
                counts["non_string_field_keys"].append({"id": ident, "key": repr(key)})
                name = f"<{ktag}:{key!r}>"
            else:
                name = key.decode("utf-8", errors="replace")
            counts["field_presence"][name] = counts["field_presence"].get(name, 0) + 1
            counts["item_fields"] += 1
        if ("s", b"identifiedDisplayName") not in item.items:
            counts["missing_identifiedDisplayName"] += 1
        walk(item, 1, f"tbl[{ident}]")
    counts["field_presence"] = dict(sorted(counts["field_presence"].items()))
    return counts


# --- Serialization -------------------------------------------------------------

ESCAPES = {0x5c: b"\\\\", 0x22: b'\\"', 0x0a: b"\\n", 0x0d: b"\\r", 0x09: b"\\t",
           0x07: b"\\a", 0x08: b"\\b", 0x0c: b"\\f", 0x0b: b"\\v"}


def lua_string(value):
    out = bytearray(b'"')
    for byte in value:
        if byte in ESCAPES:
            out += ESCAPES[byte]
        elif byte < 0x20 or byte == 0x7f:
            out += b"\\%03d" % byte
        else:
            out.append(byte)  # printable ASCII and raw UTF-8 bytes
    out += b'"'
    return bytes(out)


def lua_number(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ConvertError("non-finite number cannot be written")
    if isinstance(value, int) or (value == int(value) and abs(value) < 2 ** 53):
        if value == 0 and math.copysign(1.0, value) < 0:
            return b"-0.0"
        return str(int(value)).encode()
    return repr(float(value)).encode()


def serialize_value(value, indent):
    if isinstance(value, bool):
        return b"true" if value else b"false"
    if isinstance(value, (int, float)):
        return lua_number(value)
    if isinstance(value, bytes):
        return lua_string(value)
    if isinstance(value, LuaTable):
        return serialize_table(value, indent)
    raise ConvertError(f"cannot write value of type {type(value).__name__}")


def serialize_table(table, indent):
    if not table.items:
        return b"{}"
    pad, inner = b"\t" * indent, b"\t" * (indent + 1)
    keys = list(table.items)
    sequence = all(tag == "n" for tag, _ in keys) and \
        sorted(k for _, k in keys) == list(range(1, len(keys) + 1))
    parts = []
    if sequence:
        for n in range(1, len(keys) + 1):
            parts.append(inner + serialize_value(table.items[("n", n)], indent + 1))
    else:
        # Numeric-only tables (the root) sorted by key; otherwise the final
        # insertion order, which is deterministic for a given input.
        ordered = sorted(k for _, k in keys) if all(t == "n" for t, _ in keys) else None
        ordered = [("n", k) for k in ordered] if ordered is not None else keys
        for tagged in ordered:
            tag, key = tagged
            if tag == "s" and IDENT.match(key) and key.decode() not in LUA_KEYWORDS:
                head = key
            elif tag == "s":
                head = b"[" + lua_string(key) + b"]"
            elif tag == "b":
                head = b"[true]" if key else b"[false]"
            else:
                head = b"[" + lua_number(key) + b"]"
            parts.append(inner + head + b" = " + serialize_value(table.items[tagged], indent + 1))
    return b"{\n" + b",\n".join(parts) + b"\n" + pad + b"}"


def render_item_info(tbl, input_sha256):
    head = (b"-- Generated by tools/renewal/tw_iteminfo_utf8.py " + VERSION.encode() +
            b" from iteminfo_new.lub sha256 " + input_sha256.encode() + b".\n"
            b"-- UTF-8 Lua source of the final `tbl`. Do not edit by hand; regenerate.\n")
    return head + b"tbl = " + serialize_table(tbl, 0) + b"\n"


# --- Read-back of the emitted subset -------------------------------------------

class SourceReader:
    """Parse exactly the Lua subset render_item_info writes, back into LuaTables."""

    TOKEN = re.compile(rb"""\s+|--[^\n]*|(?P<str>"(?:[^"\\\n]|\\.)*")|(?P<num>-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)"""
                       rb"""|(?P<name>[A-Za-z_][A-Za-z0-9_]*)|(?P<sym>[{}\[\]=,])""", re.S)
    UNESCAPE = {b"\\": 0x5c, b'"': 0x22, b"n": 0x0a, b"r": 0x0d, b"t": 0x09,
                b"a": 0x07, b"b": 0x08, b"f": 0x0c, b"v": 0x0b}

    def __init__(self, source):
        self.tokens, pos = [], 0
        while pos < len(source):
            m = self.TOKEN.match(source, pos)
            if not m:
                raise ConvertError(f"read-back: unexpected source at byte {pos}")
            pos = m.end()
            if m.lastgroup:
                self.tokens.append((m.lastgroup, m.group(m.lastgroup)))
        self.i = 0

    def next(self, kind=None, text=None):
        if self.i >= len(self.tokens):
            raise ConvertError("read-back: unexpected end of source")
        tok = self.tokens[self.i]
        if (kind and tok[0] != kind) or (text is not None and tok[1] != text):
            raise ConvertError(f"read-back: expected {text or kind}, got {tok[1][:20]!r}")
        self.i += 1
        return tok

    def peek(self):
        return self.tokens[self.i] if self.i < len(self.tokens) else (None, None)

    def string(self, raw):
        out, body, j = bytearray(), raw[1:-1], 0
        while j < len(body):
            if body[j:j + 1] == b"\\":
                nxt = body[j + 1:j + 2]
                if nxt.isdigit():
                    out.append(int(body[j + 1:j + 4]))
                    j += 4
                else:
                    out.append(self.UNESCAPE[nxt])
                    j += 2
            else:
                out.append(body[j])
                j += 1
        return bytes(out)

    def value(self):
        kind, text = self.next()
        if kind == "str":
            return self.string(text)
        if kind == "num":
            return float(text)
        if kind == "name" and text in (b"true", b"false"):
            return text == b"true"
        if kind == "sym" and text == b"{":
            return self.table()
        raise ConvertError(f"read-back: unexpected value {text[:20]!r}")

    def table(self):
        table, n = LuaTable(), 0
        while self.peek() != ("sym", b"}"):
            kind, text = self.peek()
            if kind == "sym" and text == b"[":
                self.next()
                key = self.value()
                self.next("sym", b"]")
                self.next("sym", b"=")
                table.set(lua_key(key, "read-back"), self.value())
            elif kind == "name" and self.tokens[self.i + 1] == ("sym", b"="):
                self.next()
                self.next()
                table.set(("s", text), self.value())
            else:
                n += 1
                table.set(("n", n), self.value())
            if self.peek() == ("sym", b","):
                self.next()
        self.next("sym", b"}")
        return table

    def chunk(self):
        self.next("name", b"tbl")
        self.next("sym", b"=")
        self.next("sym", b"{")
        tbl = self.table()
        if self.i != len(self.tokens):
            raise ConvertError("read-back: trailing source")
        return tbl


def normalized(value):
    if isinstance(value, LuaTable):
        return {k: normalized(v) for k, v in value.items.items()}
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return ("num", float(value).hex())  # retain the sign of zero too
    return value


# --- Conversion and output -------------------------------------------------------

def convert_bytes(data, expected_sha256=PINNED_SHA256, expect=None):
    """Return (item_info_source_bytes, metadata) for validated input bytes."""
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256:
        raise ConvertError(f"input SHA-256 {digest} is not the pinned modern table {expected_sha256}")
    globals_, stats = reconstruct(read_chunk(data))
    tbl = globals_.get(b"tbl")
    counts = validate_item_table(tbl)
    counts["root_overwrites"] = stats["root_overwrites"]
    for key, want in (expect or {}).items():
        if counts[key] != want:
            raise ConvertError(f"pinned-input check failed: {key} is {counts[key]}, expected {want}")
    source = render_item_info(tbl, digest)
    source.decode("utf-8", errors="strict")
    if not any(byte > 0x7f for byte in source):
        raise ConvertError("output has no non-ASCII bytes; the client would not pick UTF-8")
    if normalized(SourceReader(source).chunk()) != normalized(tbl):
        raise ConvertError("read-back of the written source differs from the input table")
    metadata = {
        "converter": "tools/renewal/tw_iteminfo_utf8.py", "converter_version": VERSION,
        "input": {"sha256": digest, "bytes": len(data)},
        "ignored_globals": sorted(k.decode("utf-8", "replace") for k in globals_ if k != b"tbl"),
        "table": counts, "readback_equal": True,
    }
    return source, metadata


def write_output(out_dir, source, metadata):
    out_dir = Path(out_dir)
    if out_dir.exists() or out_dir.is_symlink():
        raise ConvertError(f"output directory already exists, refusing to overwrite: {out_dir}")
    parent = out_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=parent))
    mod_json = (json.dumps(MOD_JSON, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    metadata = dict(metadata, output={
        "layout": f"{MOD_NAME}/System/itemInfo.lua",
        "itemInfo.lua": {"sha256": hashlib.sha256(source).hexdigest(), "bytes": len(source)},
        "mod.json": {"sha256": hashlib.sha256(mod_json).hexdigest(), "bytes": len(mod_json)},
    })
    try:
        mod_dir = staging / MOD_NAME
        (mod_dir / "System").mkdir(parents=True)
        (mod_dir / "System" / "itemInfo.lua").write_bytes(source)
        (mod_dir / "mod.json").write_bytes(mod_json)
        (staging / "conversion-manifest.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        # copytree's exclusive destination mkdir refuses even an empty directory
        # or dangling symlink created after the initial check. Never replace it.
        shutil.copytree(staging, out_dir, dirs_exist_ok=False)
    except OSError as exc:
        raise ConvertError(f"could not publish output to {out_dir}: {exc}; "
                           "incomplete output may remain; inspect it before retrying") from None
    finally:
        shutil.rmtree(staging)
    return metadata


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", type=Path, help="pinned modern iteminfo_new.lub (read-only)")
    parser.add_argument("output", type=Path, help="new output directory (must not exist)")
    args = parser.parse_args(argv)
    try:
        if args.output.exists() or args.output.is_symlink():
            raise ConvertError(f"output directory already exists, refusing to overwrite: {args.output}")
        source, metadata = convert_bytes(args.input.read_bytes(), PINNED_SHA256, PINNED_EXPECT)
        metadata = write_output(args.output, source, metadata)
    except (ConvertError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"output": str(args.output), "entries": metadata["table"]["entries"],
                      "itemInfo.lua sha256": metadata["output"]["itemInfo.lua"]["sha256"]},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
