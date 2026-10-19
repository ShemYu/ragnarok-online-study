#!/usr/bin/env python3
"""Catalog raw double-quoted byte occurrences in every selected T06 NPC source (T06.004.001).

Inputs are the canonical T06.001 snapshot directory and the T06.002.001 selection
directory (`selection-manifest.json` plus `selection-complete.json`). Both are
pinned; the snapshot is verified in full by the qualified `server_selection.py`
reader, whose own bytes are verified before it is loaded. Every one of the 839
ordered `npc_sources.files` entries is scanned under one deliberate byte policy
(see `scan_source`) and the result is published as two JSONL streams, a manifest
and a completion marker written last.

This is a raw source inventory, not dialogue extraction or a native parser: it
does not say what rAthena frames, compiles, loads or displays, which text is
reachable in a story, or anything about translation. Standard library only.
Nothing is built or executed and output directories are never overwritten.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import types

TASK = "T06.004.001"
PROFILE = "raw-quoted-byte-policy-v1"
SCHEMA = 1
PRODUCER_FILE = "tools/renewal/quoted_source_inventory.py"

MAX_SOURCE_BYTES = 8388608
MAX_SOURCE_OCCURRENCES = 250000
MAX_TOTAL_OCCURRENCES = 2000000
MAX_OUTPUT_BYTES = 536870912
LIMITS = {
    "source_bytes": MAX_SOURCE_BYTES,
    "source_occurrences": MAX_SOURCE_OCCURRENCES,
    "total_occurrences": MAX_TOTAL_OCCURRENCES,
    "output_bytes": MAX_OUTPUT_BYTES,
}
CLAIMS = {
    "native_parse": "not_checked",
    "display": "not_checked",
    "encoding": "raw_bytes_only",
    "story_reachability": "not_checked",
    "translation_quality": "not_checked",
}

# Pinned inputs (no CLI, configuration or environment override exists).
SNAPSHOT_MANIFEST = "snapshot-manifest.json"
SELECTION_MANIFEST = "selection-manifest.json"
SELECTION_COMPLETE = "selection-complete.json"
PIN_SNAPSHOT_MANIFEST = {"bytes": 810498,
                         "sha256": "79ee4eff2ed1621aa3be6247d0aedefc5f44abd65025617de652f41644c1dbd0"}
PIN_SELECTION_MANIFEST = {"bytes": 953299,
                          "sha256": "d62e31fd601a879a9020eb0cbc79273cdaa38f11d6119af056b36727631aec9a"}
PIN_SELECTION_COMPLETE = {"bytes": 185,
                          "sha256": "26b9e804bd613fbf4ed1886d69ca8cf08ffc9c8b559db56b52c8bedd95ebb197"}
PIN_READER = {"bytes": 36455,
              "sha256": "22a3f4c8016e4e38608039084eb762440f9c56dd611e2af44be151fdf3c24417"}
READER_NAME = "server_selection.py"
SELECTION_PROFILE = "rathena-0693b8c-renewal-default-cli"
SELECTED_SOURCES = 839
ENTRY_KEYS = ("bytes", "file", "line", "manifest_path", "phase", "sha256", "source")

OUT_SOURCES = "quoted-sources.jsonl"
OUT_OCCURRENCES = "quoted-occurrences.jsonl"
OUT_MANIFEST = "quoted-manifest.json"
OUT_COMPLETE = "quoted-complete.json"

DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
READ_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
WRITE_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class InventoryError(Exception):
    """Invalid scanner arguments, refused input, a global cap, or failed publication."""


# --- Scanner core ------------------------------------------------------------------

QUOTE = 0x22
SLASH = 0x2F
STAR = 0x2A
BACKSLASH = 0x5C
LF = b"\n"
BLOCK_CLOSE = b"*/"
ESCAPE_MAX = 0x7E           # a backslash shields only when its preceding raw byte is <= this
OUTSIDE = re.compile(rb'["/]')
INSIDE = re.compile(rb'["\\]')


def _limit(value, name, default):
    if type(value) is not int or not 0 <= value <= default:
        raise InventoryError(f"{name} must be an int from 0 through {default}")
    return value


def scan_source(raw, *, max_bytes=MAX_SOURCE_BYTES, max_occurrences=MAX_SOURCE_OCCURRENCES):
    """Return {occurrences, known_prefix_end, gap} for raw double-quoted spans in `raw`.

    Policy (frozen, deliberately not native): outside quotes `//` runs through LF or
    actual EOF and `/*` through the first `*/` (no nesting); 0x22 opens and closes a
    quote; inside a quote 0x5c shields the next byte only when the raw byte before
    the backslash is <= 0x7e. Everything else, including CR, LF, NUL, BOM and high
    bytes, is plain data. Only raw[:max_bytes] is examined.
    """
    if type(raw) is not bytes:
        raise InventoryError("raw must be bytes")
    _limit(max_bytes, "max_bytes", MAX_SOURCE_BYTES)
    _limit(max_occurrences, "max_occurrences", MAX_SOURCE_OCCURRENCES)
    size = len(raw)
    limit = min(size, max_bytes)
    at_eof = limit == size          # the scanned prefix ends at the actual end of file
    occurrences = []
    gap = None
    pos = 0
    while gap is None:
        found = OUTSIDE.search(raw, pos, limit)
        if found is None:
            pos = limit
            break
        start = found.start()
        if raw[start] == SLASH:
            if start + 1 >= limit:          # opener split by the boundary: plain slash
                pos = limit
                break
            nxt = raw[start + 1]
            if nxt == SLASH:
                end = raw.find(LF, start + 2, limit)
                if end >= 0:
                    pos = end + 1
                elif at_eof:
                    pos = limit
                else:
                    gap = ("byte_limit", start)
            elif nxt == STAR:
                end = raw.find(BLOCK_CLOSE, start + 2, limit)
                if end >= 0:
                    pos = end + 2
                else:
                    gap = ("unterminated_block_comment" if at_eof else "byte_limit", start)
            else:
                pos = start + 1
            continue
        if len(occurrences) >= max_occurrences:
            gap = ("occurrence_limit", start)
            break
        cursor = start + 1
        while True:
            hit = INSIDE.search(raw, cursor, limit)
            if hit is None:
                gap = ("unterminated_quote" if at_eof else "byte_limit", start)
                break
            k = hit.start()
            if raw[k] == QUOTE:
                occurrences.append({
                    "literal_index": len(occurrences),
                    "span": [start, k + 1],
                    "content_span": [start + 1, k],
                    "content_hex": raw[start + 1:k].hex(),
                })
                pos = k + 1
                break
            if raw[k - 1] <= ESCAPE_MAX:   # shielding backslash: consume the pair once
                if k + 1 >= limit:
                    gap = ("unterminated_quote" if at_eof else "byte_limit", start)
                    break
                cursor = k + 2
            else:
                cursor = k + 1
    if gap is None and not at_eof:
        gap = ("byte_limit", pos)
    if gap is None:
        return {"occurrences": occurrences, "known_prefix_end": size, "gap": None}
    reason, begin = gap
    return {"occurrences": occurrences, "known_prefix_end": begin,
            "gap": {"reason": reason, "span": [begin, size]}}


# --- Bounded no-follow reads and JSON ----------------------------------------------

def sha256(data):
    return hashlib.sha256(data).hexdigest()


def dumps(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False) + "\n"


def read_regular(name, limit, where, dir_fd=None):
    """Read one regular file through a no-follow, nonblocking descriptor (at most limit bytes)."""
    try:
        fd = os.open(name, READ_FLAGS, dir_fd=dir_fd)
    except OSError as exc:
        raise InventoryError(f"{where}: cannot open without following links: {exc}") from None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise InventoryError(f"{where}: not a regular file")
        if info.st_size > limit:
            raise InventoryError(f"{where}: larger than {limit} bytes")
        chunks, total = [], 0
        while total <= limit:
            chunk = os.read(fd, limit + 1 - total)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
    except OSError as exc:
        raise InventoryError(f"{where}: read failed: {exc}") from None
    finally:
        os.close(fd)
    data = b"".join(chunks)
    if len(data) != info.st_size:
        raise InventoryError(f"{where}: changed size while being read")
    return data


def pinned(data, pin, where):
    if len(data) != pin["bytes"] or sha256(data) != pin["sha256"]:
        raise InventoryError(f"{where}: {len(data)} bytes/{sha256(data)} is not the pinned "
                             f"{pin['bytes']} bytes/{pin['sha256']}")
    return data


def load_json(data, where):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise InventoryError(f"{where}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    def constant(name):
        raise InventoryError(f"{where}: non-finite JSON constant {name}")

    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=unique,
                          parse_constant=constant)
    except InventoryError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise InventoryError(f"{where}: invalid JSON: {exc}") from None


def canonical_dir(path, what):
    """Require an absolute canonical path (no link anywhere) naming a real directory."""
    text = str(path)
    if not os.path.isabs(text) or os.path.normpath(text) != text or os.path.realpath(text) != text:
        raise InventoryError(f"{what} must be an absolute canonical path without links: {text}")
    try:
        info = os.lstat(text)
    except OSError as exc:
        raise InventoryError(f"{what}: {exc}") from None
    if not stat.S_ISDIR(info.st_mode):
        raise InventoryError(f"{what} is not a directory: {text}")
    return text


def load_reader(path):
    """Verify the qualified reader's exact bytes, then load a module from those bytes only."""
    data = pinned(read_regular(str(path), PIN_READER["bytes"], "reader"), PIN_READER, "reader")
    module = types.ModuleType("quoted_inventory_server_selection")
    module.__file__ = str(path)
    exec(compile(data, str(path), "exec"), module.__dict__)  # noqa: S102 - pinned bytes
    return module, data


def read_selection(root):
    """Return (manifest bytes, completion bytes) after binding both to their pins."""
    root = canonical_dir(root, "selection directory")
    try:
        fd = os.open(root, DIR_FLAGS)
    except OSError as exc:
        raise InventoryError(f"selection directory: {exc}") from None
    try:
        names = sorted(os.listdir(fd))
        if names != sorted((SELECTION_MANIFEST, SELECTION_COMPLETE)):
            raise InventoryError(f"selection directory must hold exactly {SELECTION_MANIFEST} "
                                 f"and {SELECTION_COMPLETE}, found {names[:6]}")
        out = {}
        for name, pin in ((SELECTION_MANIFEST, PIN_SELECTION_MANIFEST),
                          (SELECTION_COMPLETE, PIN_SELECTION_COMPLETE)):
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode):
                raise InventoryError(f"selection {name}: not a regular file (links are refused)")
            out[name] = pinned(read_regular(name, pin["bytes"], f"selection {name}", fd),
                               pin, f"selection {name}")
    except OSError as exc:
        raise InventoryError(f"selection directory: {exc}") from None
    finally:
        os.close(fd)
    return out[SELECTION_MANIFEST], out[SELECTION_COMPLETE]


def _uint(value):
    return type(value) is int and value >= 0


def selected_entries(selection, completion, snapshot_manifest_bytes, manifest_bytes, files):
    """Check the upstream fields and every entry's snapshot bytes. Return the entry list."""
    if not isinstance(selection, dict) or not isinstance(completion, dict):
        raise InventoryError("selection manifest and completion must be JSON objects")
    if selection.get("status") != "complete":
        raise InventoryError(f"selection status is {selection.get('status')!r}, not 'complete'")
    profile = selection.get("profile")
    if not isinstance(profile, dict) or profile.get("name") != SELECTION_PROFILE:
        raise InventoryError(f"selection profile is not {SELECTION_PROFILE}")
    upstream = selection.get("input")
    if (not isinstance(upstream, dict)
            or upstream.get("snapshot_manifest_sha256") != sha256(snapshot_manifest_bytes)):
        raise InventoryError("selection input.snapshot_manifest_sha256 does not match the snapshot")
    if (completion.get("selection_manifest") != SELECTION_MANIFEST
            or completion.get("selection_manifest_sha256") != sha256(manifest_bytes)):
        raise InventoryError("selection completion does not bind this selection manifest")
    sources = selection.get("npc_sources")
    entries = sources.get("files") if isinstance(sources, dict) else None
    if not isinstance(entries, list) or len(entries) != SELECTED_SOURCES:
        raise InventoryError(f"npc_sources.files must list exactly {SELECTED_SOURCES} entries")
    for index, entry in enumerate(entries):
        where = f"npc_sources.files[{index}]"
        if not isinstance(entry, dict) or tuple(sorted(entry)) != ENTRY_KEYS:
            raise InventoryError(f"{where} must have exactly the keys {', '.join(ENTRY_KEYS)}")
        if (not _uint(entry["bytes"]) or not _uint(entry["line"])
                or not all(isinstance(entry[k], str)
                           for k in ("file", "manifest_path", "phase", "source"))
                or not isinstance(entry["sha256"], str) or not HEX64.match(entry["sha256"])):
            raise InventoryError(f"{where} has a malformed field")
        body = files.get(entry["manifest_path"])
        if body is None:
            raise InventoryError(f"{where}: {entry['manifest_path']!r} is not in the snapshot")
        if len(body) != entry["bytes"] or sha256(body) != entry["sha256"]:
            raise InventoryError(f"{where}: snapshot bytes differ from the selection record")
    return entries


# --- Inventory ---------------------------------------------------------------------

def build_streams(entries, files):
    """Scan every entry in order; return (sources bytes, occurrences bytes, counts)."""
    source_rows, occurrence_rows = [], []
    total = out_bytes = complete = 0
    for source_index, entry in enumerate(entries):
        raw = files[entry["manifest_path"]]
        result = scan_source(raw)
        found = result["occurrences"]
        if total + len(found) > MAX_TOTAL_OCCURRENCES:
            raise InventoryError(f"more than {MAX_TOTAL_OCCURRENCES} total occurrences")
        row = dumps({"source_index": source_index, "selection": entry,
                     "known_prefix_end": result["known_prefix_end"], "gap": result["gap"],
                     "occurrence_count": len(found)})
        source_rows.append(row)
        out_bytes += len(row)
        complete += result["gap"] is None
        lines, seen = 1, 0
        for item in found:
            start, end = item["span"]
            lines += raw.count(LF, seen, start)
            start_line = lines
            lines += raw.count(LF, start, end - 1)
            seen = end - 1
            row = dumps({"occurrence_index": total, "source_index": source_index,
                         "literal_index": item["literal_index"], "span": item["span"],
                         "content_span": item["content_span"],
                         "content_hex": item["content_hex"],
                         "start_line": start_line, "end_line": lines})
            occurrence_rows.append(row)
            out_bytes += len(row)
            total += 1
        if out_bytes > MAX_OUTPUT_BYTES:
            raise InventoryError(f"output streams exceed {MAX_OUTPUT_BYTES} bytes")
    counts = {"sources": len(entries), "complete_sources": complete,
              "incomplete_sources": len(entries) - complete, "occurrences": total}
    return ("".join(source_rows).encode("ascii"), "".join(occurrence_rows).encode("ascii"),
            counts)


def build_documents(sources, occurrences, counts, producer, inputs):
    """Return (manifest bytes, completion bytes) for the two streams."""
    state = "complete" if counts["incomplete_sources"] == 0 else "incomplete"
    outputs = {
        "sources": {"file": OUT_SOURCES, "bytes": len(sources), "sha256": sha256(sources),
                    "rows": counts["sources"]},
        "occurrences": {"file": OUT_OCCURRENCES, "bytes": len(occurrences),
                        "sha256": sha256(occurrences), "rows": counts["occurrences"]},
    }
    manifest = dumps({"schema": SCHEMA, "task": TASK, "profile": PROFILE, "state": state,
                      "producer": producer, "inputs": inputs, "outputs": outputs,
                      "counts": counts, "limits": LIMITS, "claims": CLAIMS}).encode("ascii")
    complete = dumps({"schema": SCHEMA, "task": TASK, "profile": PROFILE, "state": state,
                      "manifest": {"bytes": len(manifest), "sha256": sha256(manifest)},
                      "outputs": outputs}).encode("ascii")
    return manifest, complete


# --- Publication -------------------------------------------------------------------

def _inside(path, root):
    return os.path.commonpath([path, root]) == root


def output_target(output, input_roots):
    """Validate the requested new output path and its private parent; return it."""
    text = str(output)
    if not os.path.isabs(text) or os.path.normpath(text) != text:
        raise InventoryError(f"output must be an absolute normalized path: {text}")
    parent, name = os.path.split(text)
    if name in ("", ".", ".."):
        raise InventoryError(f"invalid output directory name: {text}")
    if os.path.realpath(parent) != parent:
        raise InventoryError(f"output parent must be canonical without links: {parent}")
    try:
        info = os.lstat(parent)
    except OSError as exc:
        raise InventoryError(f"output parent: {exc}") from None
    if not stat.S_ISDIR(info.st_mode):
        raise InventoryError(f"output parent is not a directory: {parent}")
    if info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise InventoryError(f"output parent must be owned by you and private (0700): {parent}")
    for root in input_roots:
        if _inside(text, root) or _inside(root, text):
            raise InventoryError(f"output must be outside the inputs: {text}")
    if os.path.lexists(text):
        raise InventoryError(f"output already exists, refusing to overwrite: {text}")
    return text


def _write_file(dir_fd, name, data, owned):
    """Create one new 0600 file, record its identity in `owned`, write, fsync and close it."""
    fd = os.open(name, WRITE_FLAGS, 0o600, dir_fd=dir_fd)
    try:
        info = os.fstat(fd)
        owned.append((name, (info.st_dev, info.st_ino)))
        os.fchmod(fd, 0o600)
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)


def _read_back(dir_fd, name, data):
    back = read_regular(name, len(data), f"published {name}", dir_fd)
    if len(back) != len(data) or sha256(back) != sha256(data):
        raise InventoryError(f"published {name} differs from the generated bytes")


def publish(target, documents):
    """Publish [(name, bytes), ...] into the new directory `target`; the last is the marker."""
    os.mkdir(target, 0o700)                       # exclusive: refuses files, dirs and links
    owned, fd, dir_id = [], None, None
    try:
        made = os.lstat(target)
        dir_id = (made.st_dev, made.st_ino)
        fd = os.open(target, DIR_FLAGS)
        info = os.fstat(fd)
        if (info.st_dev, info.st_ino) != dir_id or info.st_uid != os.geteuid():
            raise InventoryError("created output directory changed identity")
        os.fchmod(fd, 0o700)
        for name, data in documents:
            _write_file(fd, name, data, owned)
            _read_back(fd, name, data)
        os.fsync(fd)
    except (OSError, InventoryError) as exc:
        note = _cleanup(target, fd, dir_id, owned)
        raise InventoryError(f"could not publish {target}: {exc}{note}") from None
    finally:
        if fd is not None:
            os.close(fd)


def _cleanup(target, fd, dir_id, owned):
    """Remove only artifacts this run created whose identity is still proven (marker first)."""
    kept = []
    for name, ident in reversed(owned):
        try:
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if (info.st_dev, info.st_ino) == ident:
                os.unlink(name, dir_fd=fd)
            else:
                kept.append(name)
        except FileNotFoundError:
            pass
        except OSError:
            kept.append(name)
    try:
        info = os.lstat(target)
        if dir_id is not None and (info.st_dev, info.st_ino) == dir_id and not kept:
            os.rmdir(target)                      # fails, and keeps it, if foreign data is inside
    except OSError:
        pass
    if kept or os.path.lexists(target):
        return "; output left in place without a usable marker, inspect it before retrying"
    return ""


# --- CLI ---------------------------------------------------------------------------

def run(snapshot, selection_dir, output):
    snapshot = canonical_dir(snapshot, "snapshot")
    selection_dir = canonical_dir(selection_dir, "selection directory")
    target = output_target(output, (snapshot, selection_dir))
    here = Path(__file__).resolve().parent
    producer_bytes = read_regular(str(here / Path(PRODUCER_FILE).name), 16 << 20, "producer")
    reader, reader_bytes = load_reader(here / READER_NAME)
    manifest_bytes, complete_bytes = read_selection(selection_dir)
    try:
        snapshot_bytes, files = reader.read_snapshot(snapshot)
    except reader.SelectionError as exc:
        raise InventoryError(f"snapshot: {exc}") from None
    pinned(snapshot_bytes, PIN_SNAPSHOT_MANIFEST, "snapshot manifest")
    entries = selected_entries(load_json(manifest_bytes, SELECTION_MANIFEST),
                               load_json(complete_bytes, SELECTION_COMPLETE),
                               snapshot_bytes, manifest_bytes, files)
    sources, occurrences, counts = build_streams(entries, files)
    inputs = {name: {"bytes": len(data), "sha256": sha256(data)} for name, data in (
        ("snapshot_manifest", snapshot_bytes), ("selection_manifest", manifest_bytes),
        ("selection_complete", complete_bytes), ("reader", reader_bytes))}
    producer = {"file": PRODUCER_FILE, "bytes": len(producer_bytes),
                "sha256": sha256(producer_bytes)}
    manifest, complete = build_documents(sources, occurrences, counts, producer, inputs)
    publish(target, [(OUT_SOURCES, sources), (OUT_OCCURRENCES, occurrences),
                     (OUT_MANIFEST, manifest), (OUT_COMPLETE, complete)])
    return {"state": load_json(manifest, OUT_MANIFEST)["state"], "counts": counts,
            "manifest_sha256": sha256(manifest)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--snapshot", required=True, help="absolute canonical T06.001 snapshot")
    parser.add_argument("--selection-dir", required=True,
                        help="absolute canonical T06.002.001 selection directory")
    parser.add_argument("--output", required=True,
                        help="absolute new output directory under a private parent")
    args = parser.parse_args(argv)
    try:
        summary = run(args.snapshot, args.selection_dir, args.output)
    except (InventoryError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(dumps(summary), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
