#!/usr/bin/env python3
"""Raw static-spawn declaration pilot for exactly two selected Renewal NPC sources.

T06.002.003.005.001 (profile static-spawn-raw-v1). The input is the canonical
T06.001 snapshot and the T06.002 selection (both pinned). The unchanged
`server_selection.py` reader is hash-checked and its `read_snapshot` admits the
whole snapshot with its default pins; only the verified in-memory bytes are used.
Exactly two selected occurrences are scanned, AntHell (selection index 691) then
Prontera (772); the other 837 selected indices are listed as unscanned.

Each source becomes a lossless physical-line inventory and a byte partition into
whitespace, comment, `monster`/`boss_monster` static declaration, admitted opaque
`-<TAB>script` block and cutoff suffix events. Static declarations get a bounded
declared/default/absent projection or exactly one gap. Nothing is decoded,
compiled, executed, normalized or joined: map-cache and monster-history joins are
`not_performed`. The result is source evidence only, never native acceptance,
effective population, map/cell eligibility, rendered names or game readiness.

Exit 0 complete (marker written), 1 qualified (cutoff or projection gap, no
marker), 2 fatal (no usable output). Standard library only. Output directories
are never overwritten.
"""

import argparse
import bisect
import errno
import hashlib
import json
import math
import os
import re
import stat
import sys
import types

TASK = "T06.002.003.005.001"
PROFILE_NAME = "static-spawn-raw-v1"
PRODUCER_FILE = "tools/renewal/static_spawn_pilot.py"
READER_NAME = "server_selection.py"
READER_PIN = {"bytes": 36455,
              "sha256": "22a3f4c8016e4e38608039084eb762440f9c56dd611e2af44be151fdf3c24417"}
READER_TOOL = "tools/renewal/server_selection.py"
READER_VERSION = "1.0.1"
SNAPSHOT_MANIFEST_PIN = {"bytes": 810498,
                         "sha256": "79ee4eff2ed1621aa3be6247d0aedefc5f44abd65025617de652f41644c1dbd0"}
SNAPSHOT_COUNTS = {"files": 1683, "bytes": 68752782}
SELECTION_MANIFEST = "selection-manifest.json"
SELECTION_COMPLETE = "selection-complete.json"
SELECTION_MANIFEST_PIN = {"bytes": 953299,
                          "sha256": "d62e31fd601a879a9020eb0cbc79273cdaa38f11d6119af056b36727631aec9a"}
SELECTION_COMPLETE_PIN = {"bytes": 185,
                          "sha256": "26b9e804bd613fbf4ed1886d69ca8cf08ffc9c8b559db56b52c8bedd95ebb197"}
SELECTION_COUNT = 839
CONFIG_FILE = "npc/re/scripts_monsters.conf"
CONFIG_KEY = "rathena/" + CONFIG_FILE
CONFIG_PIN = {"bytes": 4089,
              "sha256": "c9d9e809d97cecb7c53a5826a3464293ac63f7f297b0acdc56de23ba4f8a8a74"}
PILOT = (
    {"selection_index": 691, "source": "npc/re/mobs/dungeons/anthell.txt", "line": 21,
     "bytes": 7584, "sha256": "eecbdcc7fd3b6588d7a82da381e5bd5ba0d3b0a3d5f30e1e5e14ea1b6fd83ecf"},
    {"selection_index": 772, "source": "npc/re/mobs/fields/prontera.txt", "line": 104,
     "bytes": 6648, "sha256": "607211e984c3aaa9c8e5b51b304d5c2cd61b300464de7eb81aeb901195f47922"},
)
LIMITS = {"completion_bytes": 1048576, "each_jsonl_bytes": 8388608, "framing_events": 8192,
          "manifest_bytes": 4194304, "nesting": 64, "raw_lines": 8192,
          "scanner_line_payload_bytes": 65536, "source_file_bytes": 262144,
          "source_total_bytes": 524288, "static_declarations": 4096}
LINES_OUT = "source-lines.jsonl"
EVENTS_OUT = "static-spawn-pilot.jsonl"
MANIFEST_OUT = "static-spawn-pilot-manifest.json"
COMPLETE_OUT = "static-spawn-pilot-complete.json"
COLUMN_MAX = 2047
COUNTER_KEYS = ("raw_bytes", "raw_lines", "framing_events", "static_declared", "static_supported",
                "static_gap", "opaque_blocks", "suffix_events", "certified_bytes", "unknown_bytes")
VALUE_KEYS = ("map", "name", "x", "y", "xs", "ys", "sprite", "amount", "delay", "variance", "event")

DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
READ_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
WRITE_FLAGS = (os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
               | getattr(os, "O_CLOEXEC", 0))

# Raw OS operations used by the owned I/O paths. Authored tests replace these
# module attributes to inject faults; the CLI and environment expose no seam.
_os_open = os.open
_os_read = os.read
_os_write = os.write
_os_fsync = os.fsync
_os_close = os.close
_os_mkdir = os.mkdir
_os_unlink = os.unlink


class PilotError(Exception):
    """A fatal prerequisite, admission, cap or publication failure (exit 2)."""


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def pin(data):
    return {"bytes": len(data), "sha256": sha256(data)}


def render(obj):
    """Sorted-key compact ASCII-escaped JSON plus LF."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii") + b"\n"


def _err(exc):
    """Bounded OSError text without file names."""
    if isinstance(exc, OSError):
        return f"{type(exc).__name__} errno {exc.errno}: {exc.strerror}"
    return type(exc).__name__


def _is_u(value):
    return type(value) is int and value >= 0


# --- Bounded regular-file reads --------------------------------------------------

def _fd_identity(fd):
    info = os.fstat(fd)
    return info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode)


def _close_state(fd, identity):
    """Observe the retained slot before another open can reuse its number."""
    try:
        current = _fd_identity(fd)
    except OSError as exc:
        return "released" if exc.errno == errno.EBADF else "unknown"
    if identity is None:
        return "unknown"
    return "owned" if current == identity else "foreign"


def _close_after(fd, what, primary, recover=True):
    """Keep close errors fatal; recover a still-owned serial FD at most once.

    Identity checks distinguish the controlled before/after-close cases and
    different-inode reuse. They are not FD-generation proof against arbitrary
    concurrent/reentrant same-inode reuse. Unknown/foreign slots are preserved.
    """
    try:
        identity = _fd_identity(fd)
    except OSError:
        identity = None
    try:
        _os_close(fd)
    except OSError as exc:
        failure = (f"{what}: close failed ({_err(exc)})" if primary is None else
                   f"{primary}; cleanup close also failed ({_err(exc)})")
        state = _close_state(fd, identity)
        if state == "owned" and recover:
            try:
                _os_close(fd)
            except OSError as cleanup:
                failure += f"; guarded cleanup close failed ({_err(cleanup)})"
            state = _close_state(fd, identity)
        note = {"released": "descriptor release observed",
                "foreign": "foreign descriptor left untouched",
                "owned": "owned descriptor remains; cleanup unresolved",
                "unknown": "descriptor ownership unknown; cleanup unresolved"}[state]
        raise PilotError(f"{failure}; {note}") from None
    if primary is not None:
        raise PilotError(primary)


def read_regular(name, limit, what, dir_fd=None):
    """Read a bounded regular non-link file; close errors remain fatal."""
    try:
        fd = _os_open(name, READ_FLAGS, dir_fd=dir_fd)
    except OSError as exc:
        raise PilotError(f"{what}: cannot open without following links ({_err(exc)})") from None
    primary, chunks = None, []
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            primary = f"{what}: not a regular file"
        elif info.st_size > limit:
            primary = f"{what}: larger than {limit} bytes"
        else:
            total = 0
            while True:
                chunk = _os_read(fd, min(1 << 20, limit + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > limit:
                    primary = f"{what}: grew beyond {limit} bytes while being read"
                    break
            if primary is None and total != info.st_size:
                primary = f"{what}: changed size while being read"
    except OSError as exc:
        primary = f"{what}: read failed ({_err(exc)})"
    _close_after(fd, what, primary)
    return b"".join(chunks)


def read_pinned(name, expect, what, dir_fd=None):
    data = read_regular(name, expect["bytes"], what, dir_fd=dir_fd)
    if pin(data) != expect:
        raise PilotError(f"{what}: {len(data)} bytes/{sha256(data)} is not the pinned "
                         f"{expect['bytes']}/{expect['sha256']}")
    return data


def _reject_constant(value):
    raise PilotError(f"nonfinite JSON constant {value}")


def _finite_float(token):
    value = float(token)
    if not math.isfinite(value):
        raise PilotError("nonfinite JSON number")
    return value


def strict_json(data, what):
    """Decode UTF-8 JSON refusing duplicate keys and nonfinite numbers."""
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise PilotError(f"{what}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=unique,
                          parse_constant=_reject_constant, parse_float=_finite_float)
    except PilotError as exc:
        raise PilotError(f"{what}: {exc}") from None
    except (UnicodeDecodeError, ValueError) as exc:
        raise PilotError(f"{what}: invalid JSON ({type(exc).__name__})") from None


# --- Prerequisite bridge -----------------------------------------------------------

def load_reader(path):
    """Hash/size-check the unchanged reader and load it from those verified bytes."""
    data = read_pinned(path, READER_PIN, "reader " + READER_NAME)
    module = types.ModuleType("server_selection")
    module.__file__ = path
    exec(compile(data, READER_TOOL, "exec"), module.__dict__)
    return module, data


def _canon(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _expected_entry(spec):
    return {"bytes": spec["bytes"], "file": CONFIG_FILE, "line": spec["line"],
            "manifest_path": "rathena/" + spec["source"], "phase": "npc_config",
            "sha256": spec["sha256"], "source": spec["source"]}


ENTRY_TYPES = {"bytes": "u", "file": str, "line": "u", "manifest_path": str, "phase": str,
               "sha256": str, "source": str}


def _check_entry_shape(entry, index):
    if type(entry) is not dict or set(entry) != set(ENTRY_TYPES):
        raise PilotError(f"selection npc_sources.files[{index}] has unexpected keys")
    for key, kind in ENTRY_TYPES.items():
        ok = _is_u(entry[key]) if kind == "u" else type(entry[key]) is kind
        if not ok:
            raise PilotError(f"selection npc_sources.files[{index}].{key} has the wrong type")


def _ascii_path(value, what):
    try:
        raw = value.encode("ascii")
    except UnicodeEncodeError:
        raise PilotError(f"{what} is not ASCII") from None
    if not raw or len(raw) > 255:
        raise PilotError(f"{what} is empty or longer than 255 bytes")


def bind_selection(reader, snapshot_sha, manifest, complete):
    """Check selection/completion relationships; return the 839 selected entries."""
    if type(complete) is not dict or complete != {
            "generator_version": READER_VERSION, "selection_manifest": SELECTION_MANIFEST,
            "selection_manifest_sha256": SELECTION_MANIFEST_PIN["sha256"]}:
        raise PilotError("selection completion record does not bind the pinned manifest")
    if type(manifest) is not dict:
        raise PilotError("selection manifest is not an object")
    generator = manifest.get("generator")
    if (type(generator) is not dict
            or _canon(generator) != _canon({"tool": READER_TOOL, "version": READER_VERSION,
                                            "source_sha256": READER_PIN["sha256"]})):
        raise PilotError("selection generator is not the unchanged reader")
    if _canon(manifest.get("source")) != _canon(reader.SOURCE):
        raise PilotError("selection source differs from the reader's pinned SOURCE")
    if _canon(manifest.get("profile")) != _canon(reader.PROFILE):
        raise PilotError("selection profile differs from the reader's pinned PROFILE")
    if _canon(manifest.get("input")) != _canon({"snapshot_manifest_sha256": snapshot_sha,
                                               "files": SNAPSHOT_COUNTS["files"],
                                               "bytes": SNAPSHOT_COUNTS["bytes"]}):
        raise PilotError("selection input does not bind the verified snapshot")
    if manifest.get("status") != "complete":
        raise PilotError("selection status is not complete")
    npc = manifest.get("npc_sources")
    files = npc.get("files") if type(npc) is dict else None
    if (type(files) is not list or type(npc.get("count")) is not int
            or npc["count"] != SELECTION_COUNT or len(files) != SELECTION_COUNT):
        raise PilotError(f"selection npc_sources is not exactly {SELECTION_COUNT} files")
    for index, entry in enumerate(files):
        _check_entry_shape(entry, index)
    for spec in PILOT:
        where = [i for i, e in enumerate(files) if e["source"] == spec["source"]]
        where_key = [i for i, e in enumerate(files)
                     if e["manifest_path"] == "rathena/" + spec["source"]]
        if where != [spec["selection_index"]] or where_key != where:
            raise PilotError(f"selection occurrence of {spec['source']} is missing, duplicated "
                             "or not at its pinned index")
        if _canon(files[spec["selection_index"]]) != _canon(_expected_entry(spec)):
            raise PilotError(f"selection entry {spec['selection_index']} differs from its pin")
    return files


def load_production(snapshot_root, selection_root, reader_path):
    """Return the verified production context for the fixed two-file profile."""
    reader, reader_bytes = load_reader(reader_path)
    try:
        snap_bytes, files = reader.read_snapshot(snapshot_root)
    except reader.SelectionError as exc:
        raise PilotError(f"snapshot admission failed: {exc}") from None
    if pin(snap_bytes) != SNAPSHOT_MANIFEST_PIN:
        raise PilotError("verified snapshot manifest is not the pinned manifest")
    if len(files) != SNAPSHOT_COUNTS["files"] or \
            sum(len(b) for b in files.values()) != SNAPSHOT_COUNTS["bytes"]:
        raise PilotError("verified snapshot is not the pinned 1683 files")
    try:
        info = os.lstat(selection_root)
    except OSError as exc:
        raise PilotError(f"selection root: {_err(exc)}") from None
    if not stat.S_ISDIR(info.st_mode):
        raise PilotError("selection root is not a directory (or is a link)")
    try:
        dir_fd = _os_open(selection_root, DIR_FLAGS)
    except OSError as exc:
        raise PilotError(f"selection root: {_err(exc)}") from None
    primary = None
    try:
        sel_bytes = read_pinned(SELECTION_MANIFEST, SELECTION_MANIFEST_PIN,
                                "selection manifest", dir_fd)
        done_bytes = read_pinned(SELECTION_COMPLETE, SELECTION_COMPLETE_PIN,
                                 "selection completion", dir_fd)
    except PilotError as exc:
        primary = str(exc)
    _close_after(dir_fd, "selection root", primary)
    selected = bind_selection(reader, sha256(snap_bytes),
                              strict_json(sel_bytes, "selection manifest"),
                              strict_json(done_bytes, "selection completion"))
    config = files.get(CONFIG_KEY)
    if config is None or pin(config) != CONFIG_PIN:
        raise PilotError("config snapshot file is missing or not its pin")
    config_lines = config.split(b"\n")
    entries = []
    for spec in PILOT:
        entry = selected[spec["selection_index"]]
        _ascii_path(entry["source"], "source path")
        _ascii_path(entry["manifest_path"], "manifest key")
        line = config_lines[spec["line"] - 1] if spec["line"] <= len(config_lines) else b""
        if line.rstrip(b"\r") != b"npc: " + spec["source"].encode("ascii"):
            raise PilotError(f"config line {spec['line']} does not select {spec['source']}")
        data = files.get(entry["manifest_path"])
        if data is None or pin(data) != {"bytes": spec["bytes"], "sha256": spec["sha256"]} \
                or pin(data) != {"bytes": entry["bytes"], "sha256": entry["sha256"]}:
            raise PilotError(f"source {spec['source']} is missing or differs from its pins")
        entries.append({"selection_index": spec["selection_index"], "entry": entry, "data": data})
    skip = {spec["selection_index"] for spec in PILOT}
    return {
        "producer": producer_pin(),
        "inputs": {"reader": pin(reader_bytes), "snapshot_manifest": pin(snap_bytes),
                   "selection_manifest": pin(sel_bytes), "selection_complete": pin(done_bytes)},
        "sources": entries,
        "unscanned": [i for i in range(SELECTION_COUNT) if i not in skip],
    }


def producer_pin():
    data = read_regular(os.path.abspath(__file__), 1 << 22, "producer")
    return {"file": PRODUCER_FILE, "bytes": len(data), "sha256": sha256(data)}


# --- Physical lines ---------------------------------------------------------------

def physical_lines(data):
    """Return [(start, end, payload_end, terminator)] with the terminator inside the row."""
    rows, start, size = [], 0, len(data)
    while start < size:
        lf = data.find(b"\n", start)
        if lf < 0:
            rows.append((start, size, size, "none"))
            break
        if lf > start and data[lf - 1] == 0x0D:
            rows.append((start, lf + 1, lf - 1, "crlf"))
        else:
            rows.append((start, lf + 1, lf, "lf"))
        start = lf + 1
    return rows


def preflight(data):
    """Earliest global hazard (reason, offset): initial UTF-8 BOM, NUL or bare CR."""
    if data[:3] == b"\xef\xbb\xbf":
        return "bom", 0
    found = []
    nul = data.find(b"\0")
    if nul >= 0:
        found.append((nul, "nul"))
    cr = data.find(b"\r")
    while cr >= 0:
        if data[cr + 1:cr + 2] != b"\n":
            found.append((cr, "bare_cr"))
            break
        cr = data.find(b"\r", cr + 1)
    if found:
        offset, reason = min(found)
        return reason, offset
    return None


# --- Framing ------------------------------------------------------------------------

WS_RUN = re.compile(rb"[\t\n\v\f\r ]+")
WS = frozenset(b"\t\n\v\f\r ")
OPAQUE_NAME = re.compile(rb"[A-Za-z_][A-Za-z0-9_]{0,48}")
MAP_TOKEN = re.compile(rb"[A-Za-z0-9_]{1,11}(?:\.[Gg][Aa][Tt])?")
SIGNED = re.compile(rb"0|-?[1-9][0-9]*")
UNSIGNED = re.compile(rb"0|[1-9][0-9]*")
TOKEN_FORBIDDEN = frozenset(b",\t\r\n\0")


class _Stop(Exception):
    def __init__(self, reason, fault):
        super().__init__(reason)
        self.reason, self.fault = reason, fault


class _Geometry:
    """Physical-row lookups for one source, built once."""

    def __init__(self, data, rows, width):
        self.size = len(data)
        self.width = width
        self.starts = [r[0] for r in rows]
        self.over = [r[0] for r in rows if r[2] - r[0] > width]

    def overlong_at(self, pos):
        row = bisect.bisect_right(self.starts, pos) - 1
        start = self.starts[row]
        i = bisect.bisect_left(self.over, start)
        return i < len(self.over) and self.over[i] == start, start

    def barrier(self, pos):
        """Start of the first overlong row after `pos`, or None."""
        i = bisect.bisect_right(self.over, pos)
        return self.over[i] if i < len(self.over) else None


def _block_end(data, start, barrier, width):
    """End of the nonnested block comment opened at `start`; raise _Stop on failure."""
    close = data.find(b"*/", start + 2)
    if close < 0:
        if barrier is not None:
            raise _Stop("line_width", barrier + width)
        raise _Stop("unterminated_comment", len(data))
    end = close + 2
    if barrier is not None and end > barrier:
        raise _Stop("line_width", barrier + width)
    return end


def _opaque_close(data, opener, barrier, width, nesting):
    """Offset of the matching close brace for the opener; follows npc_skip_script."""
    size, depth, i = len(data), 1, opener + 1
    while True:
        if barrier is not None and i >= barrier:
            raise _Stop("line_width", barrier + width)
        if i >= size:
            raise _Stop("unterminated_brace", size)
        b = data[i]
        if b == 0x7B:
            depth += 1
            if depth > nesting:
                raise _Stop("nesting_cap", i)
            i += 1
        elif b == 0x7D:
            depth -= 1
            if depth == 0:
                return i
            i += 1
        elif b == 0x22:
            j = i + 1
            while True:
                if barrier is not None and j >= barrier:
                    raise _Stop("line_width", barrier + width)
                if j >= size:
                    raise _Stop("unterminated_string", size)
                c = data[j]
                if c == 0x22:
                    break
                if c == 0x5C and data[j - 1] <= 0x7E:
                    k = j + 1
                    if k >= size:
                        raise _Stop("escape_boundary", size)
                    if data[k] == 0x0A:
                        raise _Stop("escape_boundary", k)
                    j = k + 1
                elif c == 0x0A:
                    raise _Stop("string_linebreak", j)
                else:
                    j += 1
            i = j + 1
        elif b == 0x2F and data[i + 1:i + 2] == b"/":
            lf = data.find(b"\n", i)
            i = size if lf < 0 else lf
        elif b == 0x2F and data[i + 1:i + 2] == b"*":
            i = _block_end(data, i, barrier, width)
        else:
            i += 1


def _candidate(data, pos, geo, limits):
    """Classify the candidate at `pos`: (kind, end, detail) or raise _Stop."""
    width = limits["scanner_line_payload_bytes"]
    over, row_start = geo.overlong_at(pos)
    if over:
        raise _Stop("line_width", row_start + width)
    barrier = geo.barrier(pos)
    if data[pos] in WS:
        end = WS_RUN.match(data, pos).end()
        if barrier is not None and end > barrier:
            end = barrier
        return "whitespace", end, None
    if data[pos:pos + 2] == b"//":
        lf = data.find(b"\n", pos)
        return "line_comment", (len(data) if lf < 0 else lf), None
    if data[pos:pos + 2] == b"/*":
        return "block_comment", _block_end(data, pos, barrier, width), None
    lf = data.find(b"\n", pos)
    if lf < 0:
        payload_end = end = len(data)
    else:
        end = lf + 1
        payload_end = lf - 1 if lf > pos and data[lf - 1] == 0x0D else lf
    tabs = []
    t = data.find(b"\t", pos, payload_end)
    while t >= 0 and len(tabs) < 3:
        tabs.append(t)
        t = data.find(b"\t", t + 1, payload_end)
    if len(tabs) < 3:
        raise _Stop("malformed_columns", pos)
    fields = ((pos, tabs[0]), (tabs[0] + 1, tabs[1]), (tabs[1] + 1, tabs[2]),
              (tabs[2] + 1, payload_end))
    for start, stop in fields:
        if stop - start > COLUMN_MAX:
            raise _Stop("column_width", start + COLUMN_MAX)
    w1, w2, w3, w4 = (data[a:b] for a, b in fields)
    keyword = w2.lower()
    if keyword in (b"monster", b"boss_monster"):
        return "static", end, _static_detail(data, keyword.decode("ascii"), fields,
                                             data.count(b"\t", pos, payload_end))
    if (w1 == b"-" and keyword == b"script" and OPAQUE_NAME.fullmatch(w3)
            and w4.startswith(b"-1,{")):
        opener = fields[3][0] + 3
        close = _opaque_close(data, opener, barrier, width, limits["nesting"])
        parts = ((pos, opener), (opener, opener + 1), (opener + 1, close), (close, close + 1))
        detail = {name: {"span": [a, b], "sha256": sha256(data[a:b])}
                  for name, (a, b) in zip(("header", "open", "body", "close"), parts)}
        return "opaque", close + 1, detail
    raise _Stop("unsupported_construct", pos)


# --- Declared-field projection ------------------------------------------------------

def _tokens(data, start, stop):
    out, s = [], start
    while True:
        c = data.find(b",", s, stop)
        if c < 0:
            out.append((s, stop))
            return out
        out.append((s, c))
        s = c + 1


def _number(token, pattern, max_len, low, high):
    if len(token) > max_len or not pattern.fullmatch(token):
        return None
    value = int(token)
    return value if low <= value <= high else None


def _name_ok(token):
    """Raw-byte name rule: 1..23 bytes, no comma/TAB/CR/LF/NUL; never decoded."""
    return 1 <= len(token) <= 23 and not TOKEN_FORBIDDEN.intersection(token)


def _slot(value, origin, span):
    return {"value": value, "origin": origin, "span": None if span is None else list(span)}


def _declared_token(data, span, kind):
    """Return the parsed value or None for one w4 component token."""
    token = data[span[0]:span[1]]
    if kind == "sprite":
        return _number(token, UNSIGNED, 23, 0, 2147483647)
    if kind == "amount":
        return _number(token, SIGNED, 11, -2147483648, 2147483647)
    if kind in ("delay", "variance"):
        return _number(token, UNSIGNED, 11, 0, 2147483647)
    if 1 <= len(token) <= 76 and not TOKEN_FORBIDDEN.intersection(token):
        return token.hex()
    return None


def project(data, fields):
    """Return (values, gaps): supported Values with [] or None with exactly one Gap."""
    w1, _, w3, w4 = fields

    def gap(code, span):
        return None, [{"code": code, "span": list(span)}]

    values = {}
    parts = _tokens(data, *w1)
    if len(parts) not in (1, 3, 5):
        return gap("map_form", w1)
    map_token = data[parts[0][0]:parts[0][1]]
    if len(map_token) > 15 or not MAP_TOKEN.fullmatch(map_token):
        return gap("map_form", w1)
    values["map"] = _slot(map_token.hex(), "declared", parts[0])
    for key, span in zip(("x", "y", "xs", "ys"), parts[1:] + [None] * (5 - len(parts))):
        if span is None:
            values[key] = _slot(0, "default", None)
            continue
        number = _number(data[span[0]:span[1]], SIGNED, 6, -32768, 32767)
        if number is None:
            return gap("map_form", w1)
        values[key] = _slot(number, "declared", span)
    name = data[w3[0]:w3[1]]
    if not _name_ok(name):
        return gap("name_form", w3)
    values["name"] = _slot(name.hex(), "declared", w3)
    if data.find(b"\t", w4[0], w4[1]) >= 0:
        return gap("w4_form", w4)
    parts = _tokens(data, *w4)
    if not 2 <= len(parts) <= 5:
        return gap("w4_form", w4)
    defaults = {"delay": 5000, "variance": 0}
    for kind, span in zip(("sprite", "amount", "delay", "variance", "event"),
                          parts + [None] * (5 - len(parts))):
        if span is None:
            values[kind] = (_slot(None, "absent", None) if kind == "event"
                            else _slot(defaults[kind], "default", None))
            continue
        value = _declared_token(data, span, kind)
        if value is None:
            return gap(kind + "_form", span)
        values[kind] = _slot(value, "declared", span)
    return values, []


def _static_detail(data, keyword, fields, tabs):
    values, gaps = project(data, fields)
    return {"keyword": keyword, "tabs": tabs,
            "fields": [{"name": f"w{i + 1}", "span": [a, b], "raw_hex": data[a:b].hex()}
                       for i, (a, b) in enumerate(fields)],
            "projection_state": "supported" if values is not None else "gap",
            "values": values, "gaps": gaps}


# --- Scanner -------------------------------------------------------------------------

def scan(datas, limits, rows=None):
    """Partition every nonempty source into events under the shared caps."""
    rows = rows if rows is not None else [physical_lines(d) for d in datas]
    events, info = [], []
    cap = limits["framing_events"]
    nonempty = [bool(d) for d in datas]
    statics = 0

    def emit(si, start, end, kind, detail):
        events.append({"schema": 1, "source_index": si, "event_index": len(events),
                       "span": [start, end], "sha256": sha256(datas[si][start:end]),
                       "kind": kind, "detail": detail})

    for si, data in enumerate(datas):
        size = len(data)
        later = sum(nonempty[si + 1:])
        suffix = None
        hazard = preflight(data) if size else None
        if hazard is not None:
            suffix = (0, hazard[0], hazard[1])
        pos, ordinary = 0, 0
        if size and suffix is None:
            geo = _Geometry(data, rows[si], limits["scanner_line_payload_bytes"])
        while size and suffix is None and pos < size:
            try:
                kind, end, detail = _candidate(data, pos, geo, limits)
            except _Stop as stop:
                suffix = (pos, stop.reason, stop.fault)
                break
            if kind == "static" and statics >= limits["static_declarations"]:
                suffix = (pos, "static_cap", pos)
                break
            remaining = (1 if end < size else 0) + later
            if len(events) + 1 + remaining > cap:
                suffix = (pos, "event_cap", pos) if ordinary else (0, "not_scanned", 0)
                break
            emit(si, pos, end, kind, detail)
            ordinary += 1
            statics += kind == "static"
            pos = end
        if suffix is not None:
            emit(si, suffix[0], size, "suffix", {"reason": suffix[1], "fault_offset": suffix[2]})
        info.append({"certified_offset": size if suffix is None else suffix[0],
                     "framing": "complete" if suffix is None else "cutoff"})
    return events, info


# --- Build -------------------------------------------------------------------------

def _check_limits(limits):
    if type(limits) is not dict or set(limits) != set(LIMITS) or \
            not all(_is_u(v) for v in limits.values()):
        raise PilotError("limits do not have the exact unsigned keys")
    if limits["framing_events"] < 2:
        raise PilotError("framing event cap is below 2")


def _counters(lines, events):
    c = dict.fromkeys(COUNTER_KEYS, 0)
    c["raw_lines"] = len(lines)
    c["raw_bytes"] = sum(r["span"][1] - r["span"][0] for r in lines)
    for e in events:
        length = e["span"][1] - e["span"][0]
        c["framing_events"] += 1
        if e["kind"] == "suffix":
            c["suffix_events"] += 1
            c["unknown_bytes"] += length
            continue
        c["certified_bytes"] += length
        if e["kind"] == "opaque":
            c["opaque_blocks"] += 1
        elif e["kind"] == "static":
            c["static_declared"] += 1
            c["static_supported" if e["detail"]["projection_state"] == "supported"
              else "static_gap"] += 1
    return c


def _verify_partition(data, lines, events):
    """Both exact reconstructions: lines rebuild the bytes; events tile them once."""
    if b"".join(bytes.fromhex(r["raw_hex"]) for r in lines) != data:
        raise PilotError("physical lines do not reconstruct the source")
    cursor = 0
    for e in events:
        a, b = e["span"]
        if a != cursor or b <= a or e["sha256"] != sha256(data[a:b]):
            raise PilotError("events do not partition the source")
        if e["kind"] == "opaque":
            parts = [e["detail"][k]["span"] for k in ("header", "open", "body", "close")]
            if parts[0][0] != a or parts[-1][1] != b or \
                    any(p[1] != q[0] for p, q in zip(parts, parts[1:])):
                raise PilotError("opaque parts do not partition the event")
        cursor = b
    if cursor != len(data):
        raise PilotError("events do not cover the source")


def build(context, limits):
    """Scan the context's sources and return the in-memory publication set."""
    _check_limits(limits)
    datas = [s["data"] for s in context["sources"]]
    if any(len(d) > limits["source_file_bytes"] for d in datas):
        raise PilotError("a pilot source exceeds the source file byte limit")
    if sum(len(d) for d in datas) > limits["source_total_bytes"]:
        raise PilotError("pilot sources exceed the total source byte limit")
    rows = [physical_lines(d) for d in datas]
    if sum(len(r) for r in rows) > limits["raw_lines"]:
        raise PilotError("pilot sources exceed the raw physical line limit")
    lines = [{"schema": 1, "source_index": si, "line": n + 1, "span": [a, b],
              "terminator": term, "raw_hex": datas[si][a:b].hex(),
              "sha256": sha256(datas[si][a:b])}
             for si, rs in enumerate(rows) for n, (a, b, _, term) in enumerate(rs)]
    events, info = scan(datas, limits, rows)
    lines_bytes = b"".join(render(r) for r in lines)
    events_bytes = b"".join(render(e) for e in events)
    for name, data in ((LINES_OUT, lines_bytes), (EVENTS_OUT, events_bytes)):
        if len(data) > limits["each_jsonl_bytes"]:
            raise PilotError(f"{name} would exceed its output byte cap")
    sources, complete = [], True
    for si, src in enumerate(context["sources"]):
        data = datas[si]
        own_lines = [r for r in lines if r["source_index"] == si]
        own_events = [e for e in events if e["source_index"] == si]
        _verify_partition(data, own_lines, own_events)
        counters = _counters(own_lines, own_events)
        framing = info[si]["framing"]
        projection = ("incomplete" if framing == "cutoff"
                      else "gapped" if counters["static_gap"] else "complete")
        complete = complete and projection == "complete"
        entry = src["entry"]
        sources.append({
            "source_index": si, "selection_index": src["selection_index"],
            "selection_entry": entry, "source_path": entry["source"],
            "manifest_key": entry["manifest_path"], "bytes": len(data), "sha256": sha256(data),
            "reconstructed_sha256": sha256(b"".join(bytes.fromhex(r["raw_hex"])
                                                    for r in own_lines)),
            "certified_offset": info[si]["certified_offset"], "framing": framing,
            "projection": projection, "counters": counters})
    totals = {k: sum(s["counters"][k] for s in sources) for k in COUNTER_KEYS}
    if totals != _counters(lines, events):
        raise PilotError("global counters differ from the per-source sums")
    outputs = {LINES_OUT: dict(pin(lines_bytes), rows=len(lines)),
               EVENTS_OUT: dict(pin(events_bytes), rows=len(events))}
    manifest = {
        "schema": 1, "task": TASK, "profile": PROFILE_NAME,
        "state": "complete" if complete else "qualified",
        "producer": context["producer"], "inputs": context["inputs"], "sources": sources,
        "unscanned_selection_indices": list(context["unscanned"]),
        "deferred_joins": {"map_cache": "not_performed", "monster_history": "not_performed"},
        "outputs": outputs, "counters": totals, "limits": dict(limits),
    }
    manifest_bytes = render(manifest)
    if len(manifest_bytes) > limits["manifest_bytes"]:
        raise PilotError("manifest would exceed its output byte cap")
    return {"lines": lines, "events": events, "lines_bytes": lines_bytes,
            "events_bytes": events_bytes, "manifest": manifest,
            "manifest_bytes": manifest_bytes, "complete": complete, "limits": dict(limits)}


def completion_record(manifest_bytes, outputs):
    return {"schema": 1, "task": TASK, "profile": PROFILE_NAME, "state": "complete",
            "manifest": pin(manifest_bytes), "outputs": outputs}


# --- Publication -------------------------------------------------------------------

def _inside(path, root):
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def output_target(out_dir, input_roots=()):
    """Validate a fresh output path beneath a private trusted parent."""
    if not os.path.isabs(out_dir):
        raise PilotError("output must be an absolute path")
    out_dir = os.path.normpath(out_dir)
    name = os.path.basename(out_dir)
    if name in ("", ".", ".."):
        raise PilotError("invalid output directory name")
    parent = os.path.realpath(os.path.dirname(out_dir))
    try:
        info = os.lstat(parent)
    except OSError as exc:
        raise PilotError(f"output parent: {_err(exc)}") from None
    if not stat.S_ISDIR(info.st_mode):
        raise PilotError("output parent is not a directory")
    if info.st_uid != os.geteuid() or info.st_mode & 0o022:
        raise PilotError("output parent must be yours and not group/world writable")
    target = os.path.join(parent, name)
    if os.path.lexists(target):
        raise PilotError("output already exists; refusing to overwrite")
    for root in input_roots:
        if _inside(target, os.path.realpath(root)):
            raise PilotError("output collides with an input root")
    return target


def _write_new(dir_fd, name, data, owned):
    """Create `name` exclusively (0600), write fully, fsync and close; record its inode."""
    try:
        fd = _os_open(name, WRITE_FLAGS, 0o600, dir_fd=dir_fd)
    except OSError as exc:
        raise PilotError(f"{name}: cannot create exclusively ({_err(exc)})") from None
    primary = None
    try:
        info = os.fstat(fd)
        owned[name] = (info.st_dev, info.st_ino)
        if stat.S_IMODE(info.st_mode) != 0o600:
            os.fchmod(fd, 0o600)
        view, offset = memoryview(data), 0
        while offset < len(data):
            written = _os_write(fd, view[offset:])
            if not written or written < 0:
                primary = f"{name}: write made no progress"
                break
            offset += written
        if primary is None:
            _os_fsync(fd)
    except OSError as exc:
        primary = f"{name}: write/fsync failed ({_err(exc)})"
    _close_after(fd, name, primary)


def _check_written(dir_fd, name, identity):
    info = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
    if not stat.S_ISREG(info.st_mode) or (info.st_dev, info.st_ino) != identity:
        raise PilotError(f"published {name} is not the owned regular file")
    if stat.S_IMODE(info.st_mode) != 0o600:
        raise PilotError(f"published {name} is not mode 0600")


def _read_back(dir_fd, name, expect, owned):
    _check_written(dir_fd, name, owned[name])
    data = read_regular(name, len(expect), f"published {name}", dir_fd)
    _check_written(dir_fd, name, owned[name])
    if data != expect:
        raise PilotError(f"published {name} differs from the generated bytes")
    return data


def _revoke(dir_fd, owned, names):
    """Unlink owned files by verified inode; foreign replacements stay untouched."""
    problems = []
    for name in names:
        if name not in owned:
            continue
        try:
            info = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
        except FileNotFoundError:
            continue
        except OSError as exc:
            problems.append(f"{name}: {_err(exc)}")
            continue
        if (info.st_dev, info.st_ino) != owned[name]:
            problems.append(f"{name}: replaced by a foreign file, left untouched")
            continue
        try:
            _os_unlink(name, dir_fd=dir_fd)
        except OSError as exc:
            problems.append(f"{name}: {_err(exc)}")
    return problems


def publish(target, result):
    """Write streams, manifest and (complete runs only) the marker last into `target`."""
    limits = result["limits"]
    try:
        _os_mkdir(target, 0o700)
    except OSError as exc:
        raise PilotError(f"output: cannot create exclusively ({_err(exc)})") from None
    try:
        made = os.lstat(target)
    except OSError as exc:
        raise PilotError(f"output: {_err(exc)}") from None
    identity = (made.st_dev, made.st_ino)
    try:
        dir_fd = _os_open(target, DIR_FLAGS)
    except OSError as exc:
        raise PilotError(f"output: cannot open created directory ({_err(exc)})") from None
    owned, dir_open, failure = {}, True, None
    close_failed, problems = False, []
    try:
        info = os.fstat(dir_fd)
        if (info.st_dev, info.st_ino) != identity or info.st_uid != os.geteuid() \
                or stat.S_IMODE(info.st_mode) != 0o700:
            raise PilotError("output directory is not the private directory just created")
        _write_new(dir_fd, LINES_OUT, result["lines_bytes"], owned)
        _read_back(dir_fd, LINES_OUT, result["lines_bytes"], owned)
        _write_new(dir_fd, EVENTS_OUT, result["events_bytes"], owned)
        _read_back(dir_fd, EVENTS_OUT, result["events_bytes"], owned)
        _write_new(dir_fd, MANIFEST_OUT, result["manifest_bytes"], owned)
        manifest_back = _read_back(dir_fd, MANIFEST_OUT, result["manifest_bytes"], owned)
        if result["complete"]:
            marker = render(completion_record(manifest_back, result["manifest"]["outputs"]))
            if len(marker) > limits["completion_bytes"]:
                raise PilotError("completion record would exceed its output byte cap")
            _write_new(dir_fd, COMPLETE_OUT, marker, owned)
            _read_back(dir_fd, COMPLETE_OUT, marker, owned)
        info = os.fstat(dir_fd)
        if (info.st_dev, info.st_ino) != identity or not stat.S_ISDIR(info.st_mode) \
                or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise PilotError("output directory is no longer the owned private directory")
        if set(os.listdir(dir_fd)) != set(owned):
            raise PilotError("output directory contains an unexpected entry")
        for name in owned:
            _check_written(dir_fd, name, owned[name])
        _os_fsync(dir_fd)
        try:
            _os_close(dir_fd)
        except OSError as exc:
            close_failed = True
            state = _close_state(dir_fd, (*identity, stat.S_IFDIR))
            dir_open = state == "owned"
            if state in ("unknown", "foreign"):
                problems.append(f"original directory descriptor {state}; left untouched")
            raise PilotError(f"output directory close failed ({_err(exc)})") from None
        else:
            dir_open = False
    except (OSError, PilotError) as exc:
        failure = str(exc) if isinstance(exc, PilotError) else f"output: {_err(exc)}"
    if failure is None:
        return
    # Revoke only owned completion (marker, then manifest) by verified inode.
    revoke_fd, reopened = dir_fd if dir_open else None, False
    if revoke_fd is not None and _close_state(revoke_fd, (*identity, stat.S_IFDIR)) != "owned":
        problems.append("retained directory descriptor ownership lost; left untouched")
        revoke_fd = None
    if revoke_fd is None:
        try:
            revoke_fd = _os_open(target, DIR_FLAGS)
            reopened = True
        except OSError as exc:
            problems.append(f"cannot reopen output to revoke ({_err(exc)})")
        if revoke_fd is not None:
            try:
                info = os.fstat(revoke_fd)
                same = (info.st_dev, info.st_ino) == identity
            except OSError:
                same = False
            if not same:
                problems.append("output directory was replaced; nothing revoked")
                fd, revoke_fd = revoke_fd, None
                try:
                    _close_after(fd, "reopened output directory", None)
                except PilotError as exc:
                    problems.append(str(exc))
    if revoke_fd is not None:
        problems += _revoke(revoke_fd, owned, (COMPLETE_OUT, MANIFEST_OUT))
        try:
            _close_after(revoke_fd, "output directory", None,
                         recover=reopened or not close_failed)
        except PilotError as exc:
            problems.append(str(exc))
    note = f"; revocation: {'; '.join(problems)}" if problems else ""
    raise PilotError(f"publication failed: {failure}{note}")


def execute(context, target, limits):
    """Build and publish; return (exit status 0 complete or 1 qualified, result)."""
    result = build(context, limits)
    publish(target, result)
    return (0 if result["complete"] else 1), result


# --- CLI ---------------------------------------------------------------------------

def _redact(message, roots):
    for root in sorted({r for r in roots if r}, key=len, reverse=True):
        message = message.replace(root, "<root>")
    home = os.path.expanduser("~")
    if home and home != "~":
        message = message.replace(home, "~")
    return message[:400]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--snapshot", required=True, help="absolute canonical snapshot root")
    parser.add_argument("--selection-dir", required=True, help="absolute selection root")
    parser.add_argument("--output", required=True, help="fresh private output directory")
    args = parser.parse_args(argv)
    roots = (args.snapshot, args.selection_dir, args.output)
    try:
        if not (os.path.isabs(args.snapshot) and os.path.isabs(args.selection_dir)):
            raise PilotError("snapshot and selection roots must be absolute paths")
        target = output_target(args.output, (args.snapshot, args.selection_dir))
        reader_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), READER_NAME)
        context = load_production(args.snapshot, args.selection_dir, reader_path)
        status, result = execute(context, target, LIMITS)
    except PilotError as exc:
        print(f"error: {_redact(str(exc), roots)}", file=sys.stderr)
        return 2
    except Exception as exc:  # any unexpected failure is fatal, never exit 1
        print(f"error: unexpected {type(exc).__name__}", file=sys.stderr)
        return 2
    manifest = result["manifest"]
    print(render({"state": manifest["state"], "outputs": manifest["outputs"],
                  "counters": manifest["counters"]}).decode("ascii"), end="")
    return status


if __name__ == "__main__":
    sys.exit(main())
