#!/usr/bin/env python3
"""Reconcile the ordered stock map selection with rAthena's map index and map cache.

Inputs are the canonical T06.001 snapshot directory and the canonical T06.002.001
selection directory. The snapshot is verified in full by the unmodified
`server_selection.read_snapshot()` (manifest pin, exact file set, every size and
hash). The selection directory must hold exactly its two pinned regular files,
whose completion record binds the manifest hash and whose manifest names this
snapshot, the pinned generator and an explicit Renewal profile.

The model replays, on the verified bytes only, the parts of map-server startup
at the pinned source revision that decide which configured map occurrences stay
in the map list when GRF reading is off (use_grf 0):

- `mapindex_init` (mapindex.cpp:131-178): `db_path/map_index.txt` then
  `db_path/import/map_index.txt`, fgets(1024) chunks, `%11s\\t%d`, implicit and
  special -1 IDs, coupled numeric slots and reverse name->ID mapping.
- `map_readallmaps` (map.cpp:3927-4012): the hardcoded cache files
  db/import -> db/re -> db/map_cache.dat, first exact name match per file,
  dimension checks with fall-through to the next file, then the index lookup
  (normalising the stored name again) and the duplicate-index check.

Cache payloads are decoded one record at a time with bounded zlib output under a
strict validator policy that is stricter than the C++ code (which ignores the
decoder status). Any record or file the policy cannot vouch for leaves affected
candidates unresolved and the result incomplete; it is never reported as a
native discard or fallback.

The result is a per-occurrence source-profile disposition only. Nothing is built
or executed; it says nothing about runtime loading, rendering, playability or the
episode. Standard library only. Output directories are never overwritten.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import server_selection  # noqa: E402  (canonical snapshot verifier, used unmodified)

VERSION = "1.0.0"
OUTPUT_MANIFEST = "map-cache-manifest.json"
OUTPUT_COMPLETE = "map-cache-complete.json"
SNAPSHOT_SERVER_ROOT = "rathena/"

SELECTION_MANIFEST = "selection-manifest.json"
SELECTION_COMPLETE = "selection-complete.json"
SELECTION_PINS = {
    SELECTION_MANIFEST: {"bytes": 953299, "sha256":
                         "d62e31fd601a879a9020eb0cbc79273cdaa38f11d6119af056b36727631aec9a"},
    SELECTION_COMPLETE: {"bytes": 185, "sha256":
                         "26b9e804bd613fbf4ed1886d69ca8cf08ffc9c8b559db56b52c8bedd95ebb197"},
}
SELECTION_GENERATOR = {"tool": "tools/renewal/server_selection.py", "version": "1.0.1",
                       "source_sha256":
                       "22a3f4c8016e4e38608039084eb762440f9c56dd611e2af44be151fdf3c24417"}
SELECTION_PROFILE_NAME = "rathena-0693b8c-renewal-default-cli"

SOURCE = {
    "repository": "rathena",
    "revision": "0693b8c69911d5ca42269684aa036b67d67f4d3e",
    "files": {
        "src/map/map.cpp": "2ec53a19360b2363d6bcb1401f71bfdf130d72e74a624676e4a25f17de21a189",
        "src/map/map.hpp": "3214f2dcccec3dc97b89625ffa166afb6c0b7711faa48b5e2d7e6d586892c34b",
        "src/common/mapindex.cpp":
            "8880bee464c148248ddeb9efe32c8a12cc16589a24c7e3a457a4d93f592f6dce",
        "src/common/mapindex.hpp":
            "78d9ae9cc6f94648ca06ccb9ed6adce7338696060f452fb7a2e7516a72ab304a",
        "src/common/mmo.hpp": "883ec2048b726d51f897218989ca66c476bcdbc969d683025fe09a0bf280fa6d",
        "src/common/db.hpp": "db8a413ca97f8110191baba4a26436cf6e323ff7e30b312c9b089697dd888540",
        "src/common/grfio.cpp": "6cae30137b0f00e0208fb45b5cf129509025ee0701fe1dd27c51be082d9dc0b7",
        "src/config/const.hpp":
            "eec729d3651087279dc710f69d7d396e720c1a12a5eecd76e7c9c3fcdc9dfa1d",
    },
    "rules": {
        "index_files": "mapindex.cpp:138-158 db_path/map_index.txt (missing: fatal), then "
                       "db_path/import/map_index.txt (missing: warning, break)",
        "index_lines": "mapindex.cpp:160-175 fgets(line, 1024); skip line[0..1]=='//'; "
                       "sscanf '%11s\\t%d': 1 -> last_index+1, 2 -> scanned; "
                       "last_index = requested",
        "index_add": "mapindex.cpp:74-108, db.hpp:981 -1 -> ARR_FIND(1, max_index) empty slot; "
                     "range 0..MAX_MAPINDEX-1; empty name rejected; overwrite removes old "
                     "reverse key; strdb_iput; max_index grows on insert only",
        "index_lookup": "mapindex.cpp:110-121 mapindex_getmapname again, then strdb_iget; "
                        "0 is false",
        "name_normalise": "mapindex.cpp:24-41 strnlen 16 (16 -> 15), stricmp tail '.gat', "
                          "clip 11",
        "limits": "mapindex.hpp:10 MAX_MAPINDEX 2000; mmo.hpp:163-164 MAP_NAME_LENGTH 12/16; "
                  "map.hpp:82 MAX_MAP_SIZE 512*512",
        "reverse_map": "db.hpp:705 strdb_alloc(DB_OPT_DUP_KEY, MAP_NAME_LENGTH), "
                       "db.hpp:633,665 strdb_iget/strdb_iput (case-sensitive string keys)",
        "cache_paths": "map.cpp:3935-3960 'db/' DBIMPORT, 'db/' DBPATH, 'db/' map_cache.dat; "
                       "const.hpp:38,43 DBPATH 're/' (RENEWAL), DBIMPORT 'import'; "
                       "fopen failure logs and continues; init failure exits",
        "cache_layout": "map.cpp:169-180 map_cache_main_header {uint32 file_size; uint16 "
                        "map_count}; map_cache_map_info {char name[12]; int16 xs, ys; "
                        "int32 len}",
        "cache_read": "map.cpp:3688-3731 strcmp first match per file; xs<=0||ys<=0 -> 0; "
                      "xs*ys > MAX_MAP_SIZE -> 0; decode_zip status/size ignored",
        "decode": "grfio.cpp:245-248 decode_zip = zlib uncompress",
        "cell_types": "map.cpp:3296-3314 map_gat2cell 0..6; default warns, zero flags",
        "reconcile": "map.cpp:3970-4009 cache attempts in file order, then "
                     "!(idx = mapindex_name2id(name)) || !success -> remove; "
                     "index already loaded -> remove; map_delmapid compacts",
    },
}

PROFILE = {
    "name": "rathena-0693b8c-renewal-use_grf-off",
    "renewal": True,
    "required_db_path": "db",
    "required_use_grf": 0,
    "index_files": ["map_index.txt", "import/map_index.txt"],
    "cache_files": ["db/import/map_cache.dat", "db/re/map_cache.dat", "db/map_cache.dat"],
    "max_mapindex": 2000,
    "map_name_length": 12,
    "map_name_length_ext": 16,
    "max_map_size": 512 * 512,
    "cache_layout": {"byte_order": "little-endian", "alignment": "native (x86-64/arm64)",
                     "main_header": "<IH2x (8 bytes)", "entry_header": "<12shhi (20 bytes)"},
}
MAX_MAPINDEX = PROFILE["max_mapindex"]
MAP_NAME_LEN = PROFILE["map_name_length"]
MAP_NAME_LEN_EXT = PROFILE["map_name_length_ext"]
MAX_MAP_SIZE = PROFILE["max_map_size"]
MAIN_HEADER = struct.Struct("<IH2x")
ENTRY_HEADER = struct.Struct("<12shhi")
FGETS_MAX = 1023             # fgets(line, 1024): at most 1023 bytes including '\n'
INT32_MIN, INT32_MAX = -(1 << 31), (1 << 31) - 1
C_SPACE = b" \t\n\v\f\r"     # isspace() in the C locale
INDEX_ALLOWED_CONTROLS = frozenset(C_SPACE)
KNOWN_CELLS = range(7)

WORK_LIMITS = {
    "max_index_chunks": 1 << 16,
    "max_cache_records_per_file": 65535,
    "max_cache_records_total": 1 << 16,
    "max_decoded_bytes_total": 512 << 20,
    "max_decoded_bytes_per_record": MAX_MAP_SIZE + 1,
    "max_candidates": 1 << 16,
}

VALIDATOR_POLICY = [
    "Native source checks modelled exactly: first exact case-sensitive name match per cache "
    "file; nonpositive dimensions or a product above 262144 make that file's lookup fail "
    "and the next cache file is tried.",
    "Additional strict policy (not performed by the C++ code): the main header must fit, its "
    "file_size field must equal the file length and its two padding bytes must be zero; "
    "every entry header and payload must lie inside the file; len must be non-negative; "
    "each 12-byte name must contain a NUL, be printable ASCII and be zero padded after the "
    "NUL; the last entry must end exactly at end of file.",
    "A cache file that breaks any structural rule is unsafe. A candidate whose cache "
    "attempt reaches an unsafe file, or an unsafe name before its match, is unresolved.",
    "Every entry with valid dimensions is decoded, used or not, with output capped at "
    "xs*ys+1 bytes and no flush. The stream must end (checksum verified), consume all "
    "input, leave no trailing data and produce exactly xs*ys bytes. A failure is unsafe "
    "data: a candidate matching it is unresolved, never a native fallback or discard.",
    "Raw cell values 0..6 are recognised; other values are counted as unknown (the source "
    "warns and uses zero flags) and do not fail the record.",
    "Status complete means every rule above held and every candidate has a modelled "
    "disposition. It does not mean every candidate was retained.",
]

NOT_CHECKED = [
    "runtime map-server loading, logs or the installed binary's compile options and layout",
    "client map files, rendering and walkability in game",
    "NPCs, monsters, warps, quests or other map content",
    "playability, episode scope or coverage",
    "use_grf on (GRF reading) and other db_path/profile variants",
    "installed configuration overlays and app-generated files",
]


class InventoryError(ValueError):
    """Input that cannot be modelled without guessing, or output that cannot be published."""


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def text(raw):
    """Bytes to a JSON-safe string; non-ASCII is escaped, never decoded by guess."""
    return raw.decode("ascii", "backslashreplace")


# --- Map name normalisation (mapindex.cpp:24-41) -----------------------------------

def getmapname(raw):
    """mapindex_getmapname on a C string (bytes without NUL). Returns (name, flags)."""
    flags = []
    length = min(len(raw), MAP_NAME_LEN_EXT)
    if length == MAP_NAME_LEN_EXT:
        flags.append("too_long_warning")
        length -= 1
    # stricmp(&string[len-4], ".gat") compares the whole remaining C string.
    if length >= 4 and raw[length - 4:].lower() == b".gat":
        length -= 4
        flags.append("gat_stripped")
    if length > MAP_NAME_LEN - 1:
        flags.append("clipped")
        length = MAP_NAME_LEN - 1
    return raw[:length], flags


# --- map_index.txt reading (mapindex.cpp:131-178) ----------------------------------

def fgets_chunks(data, where):
    """Yield (physical line, chunk number within it, byte offset, chunk) as fgets(1024)."""
    if b"\0" in data:
        raise InventoryError(f"{where}: NUL byte; unsupported input")
    bad = sorted({b for b in data if b >= 0x80 or (b < 0x20 and b not in INDEX_ALLOWED_CONTROLS)
                  or b == 0x7f})
    if bad:
        raise InventoryError(f"{where}: non-ASCII or control byte(s) "
                             f"{[hex(b) for b in bad[:8]]}; unsupported input")
    line, chunk, start = 1, 0, 0
    while start < len(data):
        newline = data.find(b"\n", start, start + FGETS_MAX)
        end = newline + 1 if newline >= 0 else min(len(data), start + FGETS_MAX)
        yield line, chunk, start, data[start:end]
        if newline >= 0:
            line, chunk = line + 1, 0
        else:
            chunk += 1
        start = end


def scan_index_line(chunk):
    """sscanf(chunk, "%11s\\t%d"): return (conversions, name bytes, integer or None).

    conversions is -1 (input failure before the first conversion), 1 or 2. An integer
    outside int32 is refused rather than given an invented native value.
    """
    i, n = 0, len(chunk)
    while i < n and chunk[i] in C_SPACE:
        i += 1
    if i == n:
        return -1, None, None
    start = i
    while i < n and i - start < MAP_NAME_LEN - 1 and chunk[i] not in C_SPACE:
        i += 1
    name = chunk[start:i]
    # The '\t' directive matches any run of white space, including none; %d then
    # skips white space too.
    while i < n and chunk[i] in C_SPACE:
        i += 1
    j = i
    if j < n and chunk[j] in b"+-":
        j += 1
    digits = j
    while j < n and 0x30 <= chunk[j] <= 0x39:
        j += 1
    if j == digits:
        return 1, name, None
    value = int(chunk[i:j])
    if not INT32_MIN <= value <= INT32_MAX:
        raise InventoryError(f"index value {text(chunk[i:j])} is outside int32; the native "
                             "conversion is undefined and not modelled")
    return 2, name, value


class MapIndex:
    """indexes[] forward slots, the strdb reverse mapping and max_index."""

    def __init__(self):
        self.forward = {}        # id -> name bytes (non-empty slots only)
        self.reverse = {}        # name bytes -> id
        self.max_index = 0
        self.last_index = -1
        self.events = []
        self.reads = []
        self.diagnostics = []

    def addmap(self, requested, raw_name):
        """mapindex_addmap. Return the event fields (resolved id and result)."""
        resolved = requested
        if requested == -1:
            resolved = 1
            while resolved < self.max_index and resolved in self.forward:
                resolved += 1
        event = {"requested": requested, "resolved": resolved}
        if resolved < 0 or resolved >= MAX_MAPINDEX:
            event["result"] = "rejected_out_of_range"
            return event
        name, flags = getmapname(raw_name)
        event["name"] = text(name)
        if flags:
            event["name_flags"] = flags
        if not name:
            event["result"] = "rejected_empty_name"
            return event
        old = self.forward.get(resolved)
        if old is not None:
            event["replaced"] = text(old)
            event["reverse_removed"] = old in self.reverse
            self.reverse.pop(old, None)
        self.forward[resolved] = name
        if name in self.reverse and self.reverse[name] != resolved:
            event["reverse_reassigned_from"] = self.reverse[name]
        self.reverse[name] = resolved
        if self.max_index <= resolved:
            self.max_index = resolved + 1
        event["result"] = "stored"
        return event

    def read_file(self, path, data):
        """Process one present index file in order."""
        stats = {"path": path, "present": True, "bytes": len(data), "sha256": sha256(data),
                 "chunks": 0, "comments": 0, "no_conversion": 0, "records": 0}
        for line, chunk_no, offset, chunk in fgets_chunks(data, path):
            stats["chunks"] += 1
            if sum(r["chunks"] for r in self.reads) + stats["chunks"] > \
                    WORK_LIMITS["max_index_chunks"]:
                raise InventoryError(f"more than {WORK_LIMITS['max_index_chunks']} index "
                                     "chunks; refused")
            if chunk[:2] == b"//":
                stats["comments"] += 1
                continue
            conversions, name, value = scan_index_line(chunk)
            if conversions < 1:
                stats["no_conversion"] += 1
                continue
            if conversions == 1:
                if self.last_index == INT32_MAX:
                    raise InventoryError(f"{path}:{line}: implicit index after {INT32_MAX} "
                                         "overflows int32; not modelled")
                requested = self.last_index + 1
            else:
                requested = value
            event = {"seq": len(self.events), "file": path, "line": line, "chunk": chunk_no,
                     "offset": offset, "conversions": conversions, "scanned": text(name)}
            event.update(self.addmap(requested, name))
            self.last_index = requested
            event["last_index"] = self.last_index
            event["max_index"] = self.max_index
            self.events.append(event)
            stats["records"] += 1
            if event["result"] != "stored":
                self.diagnostics.append({"kind": "index_" + event["result"], "file": path,
                                         "line": line, "requested": requested,
                                         "resolved": event["resolved"]})
        self.reads.append(stats)

    def lookup(self, name):
        """mapindex_name2idx: normalise again, strdb_iget; returns (normalised, id or None)."""
        normalised, _ = getmapname(name)
        return normalised, self.reverse.get(normalised)

    def state(self):
        return {
            "last_index": self.last_index,
            "max_index": self.max_index,
            "forward": [{"id": i, "name": text(self.forward[i])} for i in sorted(self.forward)],
            "reverse": [{"name": text(n), "id": i} for n, i in sorted(self.reverse.items())],
            "forward_count": len(self.forward),
            "reverse_count": len(self.reverse),
        }


def build_index(files, db_path):
    """Read db_path/map_index.txt then db_path/import/map_index.txt from {path: bytes}."""
    index = MapIndex()
    for number, rel in enumerate(PROFILE["index_files"]):
        path = f"{db_path}/{rel}"
        data = files.get(path)
        if data is None:
            if number == 0:
                raise InventoryError(f"main index {path} is missing; the server exits "
                                     "(fatal), nothing to model")
            index.reads.append({"path": path, "present": False})
            index.diagnostics.append({"kind": "index_import_missing_warning", "file": path})
            break
        index.read_file(path, data)
    return index


# --- Map cache catalog (map.cpp:3656-3731) ------------------------------------------

def decode_record(payload, cells, budget):
    """Strict bounded decode. Return (record fields, problem or None)."""
    if budget["decoded"] + cells > WORK_LIMITS["max_decoded_bytes_total"]:
        raise InventoryError(f"aggregate decoded size above "
                             f"{WORK_LIMITS['max_decoded_bytes_total']} bytes; refused")
    decoder = zlib.decompressobj()
    try:
        out = decoder.decompress(payload, cells + 1)
    except zlib.error as exc:
        return {}, f"zlib_error: {exc}"
    budget["decoded"] += len(out)
    fields = {"decoded_bytes": len(out)}
    if len(out) > cells:
        return fields, "decoded_longer_than_expected"
    if not decoder.eof:
        return fields, ("unconsumed_compressed_input" if decoder.unconsumed_tail
                        else "truncated_stream")
    if decoder.unused_data:
        return fields, "trailing_data_after_stream"
    if len(out) != cells:
        return fields, "decoded_shorter_than_expected"
    counts = [0] * 256
    for value in set(out):
        counts[value] = out.count(value)
    unknown = {str(v): counts[v] for v in range(7, 256) if counts[v]}
    fields.update({
        "decoded_sha256": sha256(out),
        "cell_histogram": {str(v): counts[v] for v in KNOWN_CELLS if counts[v]},
        "unknown_cells": sum(unknown.values()),
    })
    if unknown:
        fields["unknown_cell_values"] = unknown
    return fields, None


def name_field(raw):
    """Return (name bytes or None, problem or None) for a 12-byte entry name."""
    end = raw.find(b"\0")
    if end < 0:
        return None, "name_missing_nul"
    name = raw[:end]
    if any(b < 0x20 or b > 0x7e for b in name):
        return None, "unsupported_name_encoding"
    if any(raw[end:]):
        return name, "name_padding_nonzero"
    return name, None


def catalog_cache(path, data, budget):
    """Catalog every reachable record of one present cache file in file order."""
    record = {"path": path, "present": True, "bytes": len(data), "sha256": sha256(data),
              "entries": [], "problems": []}
    if len(data) < MAIN_HEADER.size:
        record["problems"].append({"kind": "main_header_truncated"})
        record["status"] = "unsafe"
        return record
    file_size, count = MAIN_HEADER.unpack_from(data, 0)
    record["header"] = {"file_size": file_size, "map_count": count,
                        "sha256": sha256(data[:MAIN_HEADER.size])}
    if file_size != len(data):
        record["problems"].append({"kind": "header_file_size_mismatch", "policy": "strict"})
    if any(data[6:8]):
        record["problems"].append({"kind": "header_padding_nonzero", "policy": "strict"})
    if count > WORK_LIMITS["max_cache_records_per_file"]:
        raise InventoryError(f"{path}: map_count {count} above the record limit; refused")
    offset = MAIN_HEADER.size
    for ordinal in range(count):
        budget["records"] += 1
        if budget["records"] > WORK_LIMITS["max_cache_records_total"]:
            raise InventoryError("more cache records than the aggregate limit; refused")
        if offset + ENTRY_HEADER.size > len(data):
            record["problems"].append({"kind": "entry_header_truncated", "ordinal": ordinal,
                                       "offset": offset})
            break
        raw_name, xs, ys, length = ENTRY_HEADER.unpack_from(data, offset)
        entry = {"ordinal": ordinal, "offset": offset, "xs": xs, "ys": ys, "len": length,
                 "header_sha256": sha256(data[offset:offset + ENTRY_HEADER.size])}
        name, problem = name_field(raw_name)
        entry["name"] = text(name if name is not None else raw_name.rstrip(b"\0"))
        record["entries"].append(entry)
        if problem:
            entry["name_problem"] = problem
            record["problems"].append({"kind": problem, "ordinal": ordinal, "offset": offset,
                                       "policy": "strict"})
        if length < 0:
            record["problems"].append({"kind": "negative_length", "ordinal": ordinal,
                                       "offset": offset})
            entry["structure"] = "unsafe"
            break
        start = offset + ENTRY_HEADER.size
        if start + length > len(data):
            record["problems"].append({"kind": "payload_truncated", "ordinal": ordinal,
                                       "offset": offset})
            entry["structure"] = "unsafe"
            break
        payload = data[start:start + length]
        entry["payload_sha256"] = sha256(payload)
        offset = start + length
        if xs <= 0 or ys <= 0:
            entry["dimensions"] = "nonpositive"
        elif xs * ys > MAX_MAP_SIZE:
            entry["dimensions"] = "exceeds_max_map_size"
        else:
            entry["dimensions"] = "valid"
            entry["cells"] = xs * ys
            fields, problem = decode_record(payload, xs * ys, budget)
            entry.update(fields)
            entry["decode"] = "ok" if problem is None else "unsafe"
            if problem:
                entry["decode_problem"] = problem
    else:
        if offset != len(data):
            record["problems"].append({"kind": "trailing_bytes_after_last_entry",
                                       "offset": offset, "bytes": len(data) - offset,
                                       "policy": "strict"})
    record["catalogued_entries"] = len(record["entries"])
    record["status"] = "unsafe" if record["problems"] else "safe"
    return record


def build_caches(files):
    """Catalog the hardcoded cache files in source order from {path: bytes}."""
    budget = {"records": 0, "decoded": 0}
    caches, diagnostics = [], []
    for path in PROFILE["cache_files"]:
        data = files.get(path)
        if data is None:
            caches.append({"path": path, "present": False})
            diagnostics.append({"kind": "cache_file_missing_logged", "file": path})
            continue
        caches.append(catalog_cache(path, data, budget))
    return caches, diagnostics, budget


def cache_attempt(cache, name):
    """map_readfromcache on one catalogued file. Return the attempt record."""
    attempt = {"file": cache["path"]}
    for entry in cache["entries"]:
        if entry.get("name_problem") in ("name_missing_nul", "unsupported_name_encoding"):
            attempt.update(outcome="unresolved_unsafe_name", ordinal=entry["ordinal"])
            return attempt
        if entry["name"] != name:
            if entry.get("structure") == "unsafe":
                break
            continue
        attempt["ordinal"] = entry["ordinal"]
        if cache["status"] != "safe":
            attempt["outcome"] = "unresolved_unsafe_file"
        elif entry["dimensions"] == "nonpositive":
            attempt["outcome"] = "invalid_dimensions"
        elif entry["dimensions"] == "exceeds_max_map_size":
            attempt["outcome"] = "exceeds_max_map_size"
        elif entry["decode"] != "ok":
            attempt["outcome"] = "unresolved_unsafe_payload"
        else:
            attempt["outcome"] = "read"
        return attempt
    attempt["outcome"] = "unresolved_unsafe_file" if cache["status"] != "safe" else "not_found"
    return attempt


# --- Ordered reconciliation (map.cpp:3970-4009) -------------------------------------

def reconcile(candidates, index, caches):
    """Walk the configured occurrences in order. Return the list of dispositions."""
    if len(candidates) > WORK_LIMITS["max_candidates"]:
        raise InventoryError("more candidates than the work limit; refused")
    present = [c for c in caches if c.get("present")]
    loaded = {}
    results = []
    for ordinal, candidate in enumerate(candidates):
        name = candidate["name"].encode("ascii")
        attempts = []
        success = None
        for cache in present:
            attempt = cache_attempt(cache, candidate["name"])
            attempts.append(attempt)
            if attempt["outcome"] == "read" or attempt["outcome"].startswith("unresolved"):
                success = attempt
                break
        normalised, idx = index.lookup(name)
        result = {"ordinal": ordinal, "name": candidate["name"], "raw": candidate.get("raw"),
                  "config_file": candidate.get("file"), "config_line": candidate.get("line"),
                  "attempts": attempts,
                  "index_lookup": {"normalised": text(normalised), "id": idx}}
        if success is not None and success["outcome"].startswith("unresolved"):
            result["disposition"] = "unresolved_unsafe"
        elif not idx or success is None:
            reasons = []
            if idx is None:
                reasons.append("index_missing")
            elif idx == 0:
                reasons.append("index_zero")
            if success is None:
                reasons.append("cache_not_read")
            result["disposition"] = "discarded_not_found"
            result["reasons"] = reasons
        elif idx in loaded:
            result["disposition"] = "discarded_duplicate_index"
            result["duplicate_of_ordinal"] = loaded[idx]
            result["cache"] = {"file": success["file"], "ordinal": success["ordinal"]}
        else:
            loaded[idx] = ordinal
            result["disposition"] = "retained"
            result["slot"] = sum(1 for r in results if r["disposition"] == "retained")
            result["cache"] = {"file": success["file"], "ordinal": success["ordinal"]}
            result["index_id"] = idx
        results.append(result)
    return results


# --- Selection verification --------------------------------------------------------

def read_selection_dir(root):
    """Return {name: bytes} for exactly the two regular, non-link selection files."""
    try:
        info = os.lstat(root)
    except OSError as exc:
        raise InventoryError(f"selection root: {exc}") from None
    if not stat.S_ISDIR(info.st_mode):
        raise InventoryError(f"selection root is not a directory (or is a link): {root}")
    fd = os.open(root, server_selection.DIR_FLAGS)
    try:
        names = sorted(os.listdir(fd))
        if names != sorted(SELECTION_PINS):
            raise InventoryError(f"selection directory must hold exactly {sorted(SELECTION_PINS)}, "
                                 f"found {names}")
        found = {}
        for name in names:
            if not stat.S_ISREG(os.stat(name, dir_fd=fd, follow_symlinks=False).st_mode):
                raise InventoryError(f"selection {name} is not a regular file; links are "
                                     "never followed")
            try:
                found[name] = server_selection._read_at(fd, name, 16 << 20, f"selection {name}")
            except server_selection.SelectionError as exc:
                raise InventoryError(str(exc)) from None
    finally:
        os.close(fd)
    return found


def _json(data, what):
    try:
        return server_selection._load_json(data, what)
    except server_selection.SelectionError as exc:
        raise InventoryError(str(exc)) from None


def verify_selection(found, snapshot_sha256, snapshot_counts, pins=SELECTION_PINS):
    """Check pins, the completion binding and the selection's identity. Return manifest."""
    for name, pin in pins.items():
        body = found[name]
        if len(body) != pin["bytes"] or sha256(body) != pin["sha256"]:
            raise InventoryError(f"selection {name} ({len(body)} bytes, {sha256(body)}) is not "
                                 f"the pinned {pin['bytes']} bytes/{pin['sha256']}")
    manifest_bytes = found[SELECTION_MANIFEST]
    complete = _json(found[SELECTION_COMPLETE], SELECTION_COMPLETE)
    expected = {"generator_version": SELECTION_GENERATOR["version"],
                "selection_manifest": SELECTION_MANIFEST,
                "selection_manifest_sha256": sha256(manifest_bytes)}
    if complete != expected:
        raise InventoryError("selection completion record does not bind the manifest")
    manifest = _json(manifest_bytes, SELECTION_MANIFEST)
    if manifest.get("status") != "complete":
        raise InventoryError("selection manifest status is not complete")
    if manifest.get("generator") != SELECTION_GENERATOR:
        raise InventoryError("selection manifest generator is not the pinned 1.0.1 source")
    expect_input = {"snapshot_manifest_sha256": snapshot_sha256, **snapshot_counts}
    if manifest.get("input") != expect_input:
        raise InventoryError("selection manifest names a different snapshot")
    profile = manifest.get("profile") or {}
    if profile.get("name") != SELECTION_PROFILE_NAME or profile.get("renewal") is not True:
        raise InventoryError("selection profile is not the explicit Renewal default profile")
    maps = manifest.get("maps") or {}
    candidates = maps.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != maps.get("candidate_count"):
        raise InventoryError("selection map candidate list is malformed")
    for c in candidates:
        if (not isinstance(c, dict) or not isinstance(c.get("name"), str)
                or not c["name"].isascii()):
            raise InventoryError("selection map candidate has no ASCII name")
    return manifest


def effective_profile(settings):
    """Final effective db_path and use_grf. Raise unless db/0 (the only modelled branch)."""
    db = (settings.get("db_path") or [None])[-1]
    grf = (settings.get("use_grf") or [None])[-1]
    if not db or db.get("effective") != "db" or db.get("truncated"):
        raise InventoryError(f"unsupported profile: final effective db_path is "
                             f"{db and db.get('effective')!r}, only 'db' is modelled")
    value = grf and grf.get("effective")
    if grf is None or type(value) is not int:
        raise InventoryError("unsupported profile: final use_grf is not a numeric switch value")
    if value != 0:
        raise InventoryError(f"unsupported profile: use_grf {value} selects GRF reading "
                             "(map_readgat), which is not modelled; caches are not applied")
    return {"db_path": db, "use_grf": grf}


# --- Inventory --------------------------------------------------------------------

def build_inventory(server_files, candidates, db_path="db"):
    """Pure model over {server-relative path: bytes} and candidate dicts."""
    index = build_index(server_files, db_path)
    caches, cache_diagnostics, budget = build_caches(server_files)
    results = reconcile(candidates, index, caches)
    return index, caches, cache_diagnostics, budget, results


def summarise(index, caches, results):
    dispositions = {}
    for r in results:
        dispositions[r["disposition"]] = dispositions.get(r["disposition"], 0) + 1
    entries = [e for c in caches if c.get("present") for e in c["entries"]]
    stored = sum(1 for e in index.events if e["result"] == "stored")
    return {
        "index_records": len(index.events),
        "index_stored": stored,
        "index_rejected": len(index.events) - stored,
        "index_replacements": sum(1 for e in index.events if "replaced" in e),
        "index_forward_slots": len(index.forward),
        "index_reverse_names": len(index.reverse),
        "cache_files_present": sum(1 for c in caches if c.get("present")),
        "cache_files_unsafe": sum(1 for c in caches if c.get("status") == "unsafe"),
        "cache_entries": len(entries),
        "cache_entries_decoded_ok": sum(1 for e in entries if e.get("decode") == "ok"),
        "cache_entries_decode_unsafe": sum(1 for e in entries if e.get("decode") == "unsafe"),
        "cache_entries_invalid_dimensions": sum(1 for e in entries
                                                if e.get("dimensions") not in (None, "valid")),
        "cache_distinct_names": len({e["name"] for e in entries}),
        "cache_decoded_bytes": sum(e.get("decoded_bytes", 0) for e in entries
                                   if e.get("decode") == "ok"),
        "cache_unknown_cells": sum(e.get("unknown_cells", 0) for e in entries),
        "candidates": len(results),
        "dispositions": dispositions,
        "retained": dispositions.get("retained", 0),
    }


def build_manifest(server_files, selection, provenance):
    """Return the deterministic map-cache manifest dict."""
    profile = effective_profile(selection["settings"])
    candidates = selection["maps"]["candidates"]
    index, caches, cache_diagnostics, budget, results = build_inventory(server_files, candidates)
    entries_unsafe = any(e.get("decode") == "unsafe"
                         for c in caches if c.get("present") for e in c["entries"])
    files_unsafe = any(c.get("status") == "unsafe" for c in caches)
    unresolved = any(r["disposition"] == "unresolved_unsafe" for r in results)
    status = "incomplete" if (entries_unsafe or files_unsafe or unresolved) else "complete"
    reads = index.reads + [{k: c[k] for k in ("path", "present", "bytes", "sha256") if k in c}
                           for c in caches]
    return {
        "generator": provenance["generator"],
        "inputs": provenance["inputs"],
        "source": SOURCE,
        "profile": PROFILE,
        "effective_settings": profile,
        "status": status,
        "status_meaning": ("every defined input was modelled safely under the validator "
                           "policy; dispositions are source-profile results, not runtime "
                           "loads" if status == "complete" else
                           "some cache data could not be vouched for; see caches and "
                           "unresolved candidates"),
        "reads": reads,
        "index": {"events": index.events, "state": index.state()},
        "caches": caches,
        "candidates": results,
        "summary": summarise(index, caches, results),
        "diagnostics": index.diagnostics + cache_diagnostics,
        "validator_policy": VALIDATOR_POLICY,
        "work_limits": WORK_LIMITS,
        "work_used": budget,
        "not_checked": NOT_CHECKED,
    }


def render(manifest):
    return (json.dumps(manifest, ensure_ascii=True, indent=1, sort_keys=True)
            + "\n").encode("ascii")


# --- Publication ------------------------------------------------------------------

DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def trusted_target(out_dir):
    """Return the absolute target below an existing parent owned by you and not shared."""
    out_dir = Path(os.path.abspath(out_dir))
    if out_dir.name in ("", ".", ".."):
        raise InventoryError(f"invalid output directory name: {out_dir}")
    parent = out_dir.parent
    try:
        info = os.lstat(parent)
    except FileNotFoundError:
        raise InventoryError(f"output parent does not exist: {parent}") from None
    if not stat.S_ISDIR(info.st_mode):
        raise InventoryError(f"output parent is not a directory (or is a link): {parent}")
    if info.st_uid != os.geteuid() or info.st_mode & 0o022:
        raise InventoryError(f"output parent must be owned by you and not group/world "
                             f"writable: {parent}")
    return out_dir


def _write_new(dir_fd, name, data, created=None):
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600,
                 dir_fd=dir_fd)
    if created is not None:
        created.append(name)  # this run owns the file from here on
    with os.fdopen(fd, "wb") as handle:
        os.fchmod(handle.fileno(), 0o600)
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _read_back(dir_fd, name, expect):
    try:
        data = server_selection._read_at(dir_fd, name, len(expect), f"published {name}")
    except server_selection.SelectionError as exc:
        raise InventoryError(str(exc)) from None
    info = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
    if data != expect or stat.S_IMODE(info.st_mode) != 0o600:
        raise InventoryError(f"published {name} differs from the generated bytes or mode")


def write_output(out_dir, manifest_bytes, status):
    """Publish the manifest, then the hash-binding completion record, into a new directory."""
    target = trusted_target(out_dir)
    complete = render({"generator_version": VERSION, "map_cache_manifest": OUTPUT_MANIFEST,
                       "map_cache_manifest_sha256": sha256(manifest_bytes), "status": status})
    try:
        os.mkdir(target, 0o700)  # exclusive: refuses any file, dir or (dangling) symlink
    except OSError as exc:
        raise InventoryError(f"output exists or cannot be created, refusing: {target}: "
                             f"{exc}") from None
    out_fd, created = None, []
    try:
        out_fd = os.open(target, DIR_FLAGS)
        info = os.fstat(out_fd)
        if info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise InventoryError("reserved output directory is not private to you")
        _write_new(out_fd, OUTPUT_MANIFEST, manifest_bytes)
        _read_back(out_fd, OUTPUT_MANIFEST, manifest_bytes)
        _write_new(out_fd, OUTPUT_COMPLETE, complete, created)
        _read_back(out_fd, OUTPUT_COMPLETE, complete)
        if sorted(os.listdir(out_fd)) != sorted((OUTPUT_MANIFEST, OUTPUT_COMPLETE)):
            raise InventoryError("output directory holds files this run did not write")
    except (OSError, InventoryError) as exc:
        note = "; incomplete output without a completion record remains, inspect it " \
               "before deleting or retrying"
        if OUTPUT_COMPLETE in created:
            try:
                os.unlink(OUTPUT_COMPLETE, dir_fd=out_fd)
            except FileNotFoundError:
                pass
            except OSError as cleanup:
                note = (f"; could not remove {OUTPUT_COMPLETE} ({cleanup}); treat this output "
                        "as failed and incomplete despite the record")
        raise InventoryError(f"could not publish output to {target}: {exc}{note}") from None
    finally:
        if out_fd is not None:
            os.close(out_fd)
    return target, sha256(complete)


# --- CLI ----------------------------------------------------------------------------

def run(snapshot, selection_dir, output):
    """Verify both canonical inputs, model, publish. Return (target, manifest, hashes)."""
    target = trusted_target(output)
    if os.path.lexists(target):
        raise InventoryError(f"output already exists, refusing to overwrite: {target}")
    try:
        snapshot_bytes, files = server_selection.read_snapshot(snapshot)
    except server_selection.SelectionError as exc:
        raise InventoryError(f"snapshot: {exc}") from None
    snapshot_sha = sha256(snapshot_bytes)
    found = read_selection_dir(selection_dir)
    selection = verify_selection(found, snapshot_sha, server_selection.PINNED_COUNTS)
    server_files = {p[len(SNAPSHOT_SERVER_ROOT):]: b for p, b in files.items()
                    if p.startswith(SNAPSHOT_SERVER_ROOT)}
    provenance = {
        "generator": {"tool": "tools/renewal/map_cache_inventory.py", "version": VERSION,
                      "source_sha256": sha256(Path(__file__).read_bytes()),
                      "snapshot_verifier": {"tool": "tools/renewal/server_selection.py",
                                            "source_sha256": sha256(
                                                Path(server_selection.__file__).read_bytes())}},
        "inputs": {
            "snapshot": {"manifest_sha256": snapshot_sha, "files": len(files),
                         "bytes": sum(len(b) for b in files.values())},
            "selection": {name: {"bytes": len(found[name]), "sha256": sha256(found[name])}
                          for name in sorted(found)},
            "selection_generator": SELECTION_GENERATOR,
            "selection_profile": SELECTION_PROFILE_NAME,
        },
    }
    manifest = build_manifest(server_files, selection, provenance)
    data = render(manifest)
    target, complete_sha = write_output(target, data, manifest["status"])
    return target, manifest, {"manifest_sha256": sha256(data), "manifest_bytes": len(data),
                              "complete_sha256": complete_sha}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("snapshot", type=Path, help="canonical T06.001 snapshot (read-only)")
    parser.add_argument("selection", type=Path,
                        help="canonical T06.002.001 selection directory (read-only)")
    parser.add_argument("output", type=Path, help="new private output directory")
    args = parser.parse_args(argv)
    try:
        target, manifest, hashes = run(args.snapshot, args.selection, args.output)
    except (InventoryError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"output": str(target), "status": manifest["status"],
                      "summary": manifest["summary"], **hashes}, sort_keys=True))
    return 0 if manifest["status"] == "complete" else 1


if __name__ == "__main__":
    sys.exit(main())
