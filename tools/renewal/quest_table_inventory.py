"""Pure raw inventory of the final `QuestInfoList` in a compiled Lua 5.1 chunk (T10.002).

The input is never executed. The authored reader in tw_iteminfo_utf8.py (loaded
from its pinned source bytes) checks the chunk layout; a local copy of its
literal-construction interpreter then replays only the same top-level opcode
boundary, recording table/global write provenance. Anything else -- calls,
jumps, upvalues, dynamic reads, reversed LOADNIL -- is refused, never guessed.

inventory_bytes() returns typed IDs, field presence, canonical hashes, complete
raw records matching fixed ASCII clues, and assignment provenance. It decodes no
text and makes no claim about quest validity, resource winners or story state.

Standard library only. No CLI, file, network or process operation in the API.
"""

import hashlib
import json
import math
from pathlib import Path
import struct
import types

SCHEMA = "T10.002-raw-quest-inventory-1"
READER_SHA256 = "6155b81377c20a9b028e64ec82548ca5f611563734b156dded8fd4937e70343d"
ROOT_NAME = b"QuestInfoList"
CLUES = (b"ch1_", b"ygg_roots", b"ygg_fruit", b"ygg_edge",
         b"mu_fild01", b"prt_fild05", b"pay_fild01")
MAX_INPUT_BYTES = 3 * 1024 * 1024
MAX_SELECTED_DEPTH = 32          # QuestInfoList itself is depth 1
MAX_SELECTED_CANONICAL = 32 * 1024 * 1024
MAX_RESULT_CANONICAL = 8 * 1024 * 1024
ABSENT = ["absent"]


class InventoryError(ValueError):
    """Input refused without guessing. `code` is a stable short identifier."""

    def __init__(self, code, message):
        super().__init__(f"{code}: {message}")
        self.code = code


def _load_reader():
    """Execute exactly the pinned authored reader source as a private module."""
    path = Path(__file__).resolve().with_name("tw_iteminfo_utf8.py")
    source = path.read_bytes()
    digest = hashlib.sha256(source).hexdigest()
    if digest != READER_SHA256:
        raise ImportError(f"{path} SHA-256 {digest} is not the pinned reader {READER_SHA256}")
    module = types.ModuleType("_t10002_tw_iteminfo_utf8")
    module.__file__ = str(path)
    exec(compile(source, str(path), "exec"), module.__dict__)
    return module


_reader = _load_reader()
HEADER = _reader.HEADER
OPNAMES = _reader.OPNAMES
FIELDS_PER_FLUSH = _reader.FIELDS_PER_FLUSH
Closure = _reader.Closure


class QuestTable(_reader.LuaTable):
    """A LuaTable with a NEWTABLE ordinal and every key ever assigned to it."""

    def __init__(self, ordinal):
        super().__init__()
        self.ordinal = ordinal
        self.assigned = set()


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _number_hex(value):
    return struct.pack("<d", value).hex()


# --- Typed values -------------------------------------------------------------

def _tag_key(value, where):
    """Tag a key with Lua equality: numbers coalesce (1/1.0, +0/-0 -> +0)."""
    if isinstance(value, bool):
        return ("b", value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise InventoryError("key", f"{where}: non-finite number table key")
        return ("n", 0.0 if value == 0 else value)
    if isinstance(value, bytes):
        return ("s", value)
    if value is None:
        raise InventoryError("key", f"{where}: nil table key")
    raise InventoryError("key", f"{where}: unsupported table key kind {type(value).__name__}")


def _typed_key(tagged):
    tag, value = tagged
    if tag == "b":
        return ["bool", value]
    if tag == "n":
        return ["number", _number_hex(value)]
    return ["bytes", value.hex()]


def _typed_scalar(value):
    if value is None:
        return ["nil"]
    if isinstance(value, bool):
        return ["bool", value]
    if isinstance(value, float):
        return ["number", _number_hex(value)]
    if isinstance(value, bytes):
        return ["bytes", value.hex()]
    raise TypeError(f"not a scalar Lua value: {type(value).__name__}")


def _token(value):
    if isinstance(value, QuestTable):
        return ["table-ref", value.ordinal]
    if isinstance(value, Closure):
        return ["closure-ref", value.index]
    return _typed_scalar(value)


def _scalar_size(typed):
    if typed[0] == "bytes":
        return 12 + len(typed[1])  # ["bytes","<hex>"]
    return len(canonical(typed))


def _check_selected(root):
    """Refuse shared/cyclic/deep/closure/oversized selected data; return C(T) size."""
    seen, active = set(), set()

    def size(value, depth, path):
        if isinstance(value, Closure):
            raise InventoryError("selected-closure", f"{path}: function value in selected table")
        if isinstance(value, float) and not math.isfinite(value):
            raise InventoryError("value", f"{path}: non-finite number")
        if not isinstance(value, QuestTable):
            return _scalar_size(_typed_scalar(value))
        if id(value) in active:
            raise InventoryError("selected-cyclic", f"{path}: cyclic table reference")
        if id(value) in seen:
            raise InventoryError("selected-shared", f"{path}: shared table reference")
        if depth > MAX_SELECTED_DEPTH:
            raise InventoryError("selected-depth", f"{path}: tables nested deeper than "
                                                    f"{MAX_SELECTED_DEPTH}")
        seen.add(id(value))
        active.add(id(value))
        total = 12 + max(0, len(value.items) - 1)  # ["table",[...]] and separators
        for tagged, sub in value.items.items():
            key = _typed_key(tagged)
            total += 3 + _scalar_size(key) + size(sub, depth + 1, f"{path}[{canonical(key).decode()}]")
            if total > MAX_SELECTED_CANONICAL:
                raise InventoryError("selected-size", f"canonical selected table exceeds "
                                                      f"{MAX_SELECTED_CANONICAL} bytes")
        active.discard(id(value))
        return total

    return size(root, 1, "QuestInfoList")


def _typed(value):
    """T(v) of checked selected data; entries sorted by C(T(key)) byte order."""
    if isinstance(value, QuestTable):
        entries = [(canonical(k), k, _typed(v))
                   for k, v in ((_typed_key(t), sub) for t, sub in value.items.items())]
        entries.sort(key=lambda e: e[0])
        return ["table", [[k, v] for _, k, v in entries]]
    return _typed_scalar(value)


# --- Literal-construction interpreter (local copy with provenance) --------------
# Adapted from tw_iteminfo_utf8.reconstruct (same opcode boundary). Corrections:
# reversed LOADNIL refuses (Lua 5.1 would clear R(B)); keys keep binary64 with
# +0 for zero and refuse infinity; nil SETGLOBAL removes the global; closures may
# be stored but refuse later if inside the selected table; writes are recorded.

def _reconstruct(proto):
    if proto["nups"] or proto["numparams"]:
        raise InventoryError("main-chunk", "main chunk must have no upvalues or parameters")
    code, constants, children = proto["code"], proto["constants"], proto["children"]
    regs = [None] * proto["maxstack"]
    globals_, tables = {}, []
    prov = {"writes": 0, "global_assignments": [], "repeated_writes": [], "nil_writes": []}
    budget = [0]
    pc = 0
    saw_terminal_return = False

    def record(name, entry):
        budget[0] += len(canonical(entry)) + 1
        if budget[0] > MAX_RESULT_CANONICAL:
            raise InventoryError("result-size", f"provenance exceeds {MAX_RESULT_CANONICAL} bytes")
        prov[name].append(entry)

    def reg(n, i):
        if n >= len(regs):
            raise InventoryError("register", f"pc {i + 1}: register {n} beyond stack size {len(regs)}")
        return n

    def const(n, i):
        if n >= len(constants):
            raise InventoryError("constant", f"pc {i + 1}: constant {n} out of range")
        return constants[n]

    def rk(n, i):
        return const(n & 255, i) if n & 256 else regs[reg(n, i)]

    def finite(value, where):
        if isinstance(value, float) and not math.isfinite(value):
            raise InventoryError("value", f"{where}: non-finite number value")

    def put(table, key, value, i):
        where = f"pc {i + 1}"
        if not isinstance(table, QuestTable):
            raise InventoryError("non-table", f"{where}: assignment into a non-table value")
        tagged = _tag_key(key, where)
        finite(value, where)
        existed = tagged in table.items
        entry = {"pc": i + 1, "table": table.ordinal, "key": _typed_key(tagged),
                 "existed": existed,
                 "before": _token(table.items[tagged]) if existed else ABSENT,
                 "after": _token(value)}
        if tagged in table.assigned:
            record("repeated_writes", entry)
        if value is None:
            record("nil_writes", dict(entry))
        table.assigned.add(tagged)
        table.set(tagged, value)
        prov["writes"] += 1

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
                raise InventoryError("unsupported", f"pc {i + 1}: LOADBOOL skip is control flow")
            regs[reg(a, i)] = bool(b)
        elif name == "LOADNIL":
            if b < a:
                raise InventoryError("loadnil", f"pc {i + 1}: reversed LOADNIL {a}..{b}")
            for r in range(reg(a, i), reg(b, i) + 1):
                regs[r] = None
        elif name == "NEWTABLE":
            tables.append(QuestTable(len(tables) + 1))
            regs[reg(a, i)] = tables[-1]
        elif name == "SETTABLE":
            put(regs[reg(a, i)], rk(b, i), rk(c, i), i)
        elif name == "SETLIST":
            if b == 0:
                raise InventoryError("setlist", f"pc {i + 1}: open-ended SETLIST is unsupported")
            if c == 0:
                if pc >= len(code):
                    raise InventoryError("setlist", f"pc {i + 1}: SETLIST block number missing")
                c, pc = code[pc], pc + 1
            if c == 0:
                raise InventoryError("setlist", f"pc {i + 1}: SETLIST block number zero")
            reg(a + b, i)
            for j in range(1, b + 1):
                put(regs[a], float((c - 1) * FIELDS_PER_FLUSH + j), regs[a + j], i)
        elif name == "SETGLOBAL":
            key = const(bx, i)
            if not isinstance(key, bytes):
                raise InventoryError("global", f"pc {i + 1}: non-string global name")
            value = regs[reg(a, i)]
            finite(value, f"pc {i + 1}")
            existed = key in globals_
            record("global_assignments", {
                "pc": i + 1, "name_hex": key.hex(), "existed": existed,
                "before": _token(globals_[key]) if existed else ABSENT,
                "after": _token(value)})
            if value is None:
                globals_.pop(key, None)
            else:
                globals_[key] = value
        elif name == "CLOSURE":
            if bx >= len(children):
                raise InventoryError("closure", f"pc {i + 1}: closure prototype out of range")
            if children[bx]["nups"]:
                raise InventoryError("closure", f"pc {i + 1}: closure upvalue binding is unsupported")
            regs[reg(a, i)] = Closure(bx)
        elif name == "RETURN":
            if b != 1 or pc != len(code):
                raise InventoryError("return", f"pc {i + 1}: only a terminal no-value RETURN is accepted")
            saw_terminal_return = True
        else:
            raise InventoryError("unsupported", f"pc {i + 1}: unsupported instruction {name}")
    if not saw_terminal_return:
        raise InventoryError("return", "main chunk has no terminal no-value RETURN")
    prov["tables_created"] = len(tables)
    return globals_, tables, prov


# --- Inventory -----------------------------------------------------------------

def _offsets(data, clue):
    found, at = [], data.find(clue)
    while at != -1:
        found.append(at)
        at = data.find(clue, at + 1)  # overlapping occurrences
    return found


def _hits(typed, path, out):
    """Canonical pre-order traversal of byte-string VALUES; keys are not searched."""
    if typed[0] == "bytes":
        raw = bytes.fromhex(typed[1])
        for clue in CLUES:
            offsets = _offsets(raw, clue)
            if offsets:
                out.append({"path": list(path), "value_hex": typed[1],
                            "clue": clue.decode("ascii"), "offsets": offsets})
    elif typed[0] == "table":
        for key, sub in typed[1]:
            _hits(sub, path + [key], out)


def inventory_bytes(data):
    """Return the T10.002 raw quest inventory for one compiled chunk's bytes."""
    if not isinstance(data, (bytes, bytearray)):
        raise InventoryError("input-type", "input must be bytes")
    data = bytes(data)
    if len(data) > MAX_INPUT_BYTES:
        raise InventoryError("input-size", f"input {len(data)} bytes exceeds {MAX_INPUT_BYTES}")
    try:
        proto = _reader.read_chunk(data)
    except _reader.ConvertError as exc:
        raise InventoryError("chunk", str(exc)) from None
    globals_, tables, prov = _reconstruct(proto)

    root = globals_.get(ROOT_NAME)
    if root is None:
        raise InventoryError("root-missing", "final global QuestInfoList is missing or nil")
    if not isinstance(root, QuestTable):
        raise InventoryError("root-kind", "final global QuestInfoList is not a table")
    predicted = _check_selected(root)
    root_typed = _typed(root)
    root_canonical = canonical(root_typed)
    if len(root_canonical) != predicted:
        raise RuntimeError("canonical size prediction mismatch")  # programming failure

    rows, matches = [], []
    for key, value in root_typed[1]:
        rows.append({"key": key, "kind": value[0], "sha256": _sha(canonical(value)),
                     "fields": [{"key": fk, "kind": fv[0]} for fk, fv in value[1]]
                     if value[0] == "table" else None})
        hits = []
        _hits(value, [], hits)
        if hits:
            present = {hit["clue"] for hit in hits}
            matches.append({"key": key, "record": value,
                            "clues": [c.decode("ascii") for c in CLUES if c.decode("ascii") in present],
                            "hits": hits})
    matched = {clue for m in matches for clue in m["clues"]}

    result = {
        "schema": SCHEMA,
        "input": {"bytes": len(data), "sha256": _sha(data), "header_hex": data[:12].hex()},
        "prototype": {"instructions": len(proto["code"]), "constants": len(proto["constants"]),
                      "children": len(proto["children"])},
        "globals": sorted(name.hex() for name in globals_),
        "root": {"global_hex": ROOT_NAME.hex(), "table_ordinal": root.ordinal,
                 "row_count": len(rows), "sha256": _sha(root_canonical)},
        "rows": rows,
        "matches": matches,
        "negatives": [c.decode("ascii") for c in CLUES if c.decode("ascii") not in matched],
        "provenance": {key: prov[key] for key in ("tables_created", "writes", "global_assignments",
                                                  "repeated_writes", "nil_writes")},
    }
    size = len(canonical(result))
    if size > MAX_RESULT_CANONICAL:
        raise InventoryError("result-size", f"canonical result {size} bytes exceeds "
                                            f"{MAX_RESULT_CANONICAL}")
    return result
