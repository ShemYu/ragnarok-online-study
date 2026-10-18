#!/usr/bin/env python3
"""Model rAthena's ordered stock map/NPC configuration selection from the pinned snapshot.

The input is the canonical T06.001 snapshot directory (`snapshot-manifest.json`
plus `rathena/{conf,db,npc,sql-files}`). The manifest must have the pinned
SHA-256, and every listed file must exist as a regular file with its recorded
size and hash; nothing else may be present. All bytes are read once into memory
through no-follow descriptors and the model runs on those verified bytes only.

The model replays the two startup passes of the map server at the pinned source
revision (Renewal profile): `map_config_read("conf/map_athena.conf")` and then
`map_reloadnpc(false)`, which reads `npc/re/scripts_main.conf` without clearing
the NPC source list first. Line handling follows the C parsers byte for byte
(fgets/strstr/sscanf/trailing-space strip, case-insensitive keys) and the map
and NPC list operations follow map_addmap/map_delmap, mapindex_getmapname and
npc_addsrcfile/npc_delsrcfile. Nothing is built or executed.

The result is a configuration selection only: it does not say which maps load,
which NPCs, spawns, monsters or quests exist, or what is visible in game.
Standard library only. Output directories are never overwritten.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile

VERSION = "1.0.0"
PINNED_MANIFEST_SHA256 = "79ee4eff2ed1621aa3be6247d0aedefc5f44abd65025617de652f41644c1dbd0"
PINNED_COUNTS = {"files": 1683, "bytes": 68752782}
SNAPSHOT_MANIFEST = "snapshot-manifest.json"
SERVER_ROOT = "rathena"
SCOPE_DIRS = ("conf", "db", "npc", "sql-files")
OUTPUT_MANIFEST = "selection-manifest.json"
OUTPUT_COMPLETE = "selection-complete.json"
MAX_MANIFEST = 16 << 20
MAX_FILE = 1 << 30

SOURCE = {
    "repository": "rathena",
    "revision": "0693b8c69911d5ca42269684aa036b67d67f4d3e",
    "files": {
        "src/map/map.cpp": "2ec53a19360b2363d6bcb1401f71bfdf130d72e74a624676e4a25f17de21a189",
        "src/map/npc.cpp": "0c2b46a9bc6639dcf7afdf0ab7189edda0ce9a863515afbf3fab5f40483958dd",
        "src/common/mapindex.cpp": "8880bee464c148248ddeb9efe32c8a12cc16589a24c7e3a457a4d93f592f6dce",
        "src/common/mmo.hpp": "883ec2048b726d51f897218989ca66c476bcdbc969d683025fe09a0bf280fa6d",
        "src/common/utils.cpp": "7beea5afdfb66a4cde768683f6c44e91d742fe4f55b20978abe30774f50024cc",
        "src/common/cli.cpp": "f21db15851a903e31b12dc1378667b7f2c60b54baf8ce0818c16bca661a095c7",
    },
    # Also consulted (worker-hashed, not in the root-hashed list).
    "supplementary_files": {
        "src/common/core.cpp": "e64fc8fc0c6bb1a025ebf6ac9c80cf026dfdb1a386eb3d1d7c678d4ca782a117",
        "src/common/strlib.cpp": "e0c198ad92d701a9d12dbf5507a449a94dee953629f3e0b0764b15a61ba7be66",
        "src/common/utilities.hpp": "6ac23dafce88e301a759ee65fc63c95aa8ad70cee62242e30ac466ebf67c8746",
    },
    "rules": {
        "startup": "map.cpp:5414 map_config_read(MAP_CONF_NAME); map.cpp:5420 map_reloadnpc(false)",
        "map_conf_name": "cli.cpp:24 conf/map_athena.conf",
        "map_parser": "map.cpp:4130-4230 line[1024], w1[32], w2[1024]; '%31[^:]: %1023[^\\t\\r\\n]'",
        "npc_parser": "map.cpp:4232-4271 line[1024], w1[1024], w2[1024]; '%1023[^:]: %1023[^\\t\\r\\n]'",
        "npc_root": "map.cpp:4274-4284 RENEWAL -> npc/re/scripts_main.conf",
        "map_add": "map.cpp:3735-3753 map_addmap (clear, MAX_MAP_PER_SERVER - 1 slots)",
        "map_del": "map.cpp:3762-3778 map_delmap (all, first exact normalized match)",
        "map_name": "mapindex.cpp:24-42 mapindex_getmapname; mmo.hpp:42,163-164",
        "npc_sources": "npc.cpp:3674-3709 npc_addsrcfile/npc_delsrcfile; utils.cpp:182-196 check_filepath",
        "db_path": "core.cpp:50 db_path[12] via safestrncpy (11 bytes kept)",
        "use_grf": "strlib.cpp:239-247 config_switch",
        "npc_list_ops": "utilities.hpp:211-251 vector_exists / vector_erase_if_exists (first match)",
    },
}
PROFILE = {
    "name": "rathena-0693b8c-renewal-default-cli",
    "renewal": True,
    "map_conf": "conf/map_athena.conf",
    "npc_root": "npc/re/scripts_main.conf",
    "server_working_root": SERVER_ROOT + "/",
    "filesystem": "case-sensitive (Linux), paths resolved against exact snapshot keys",
    "max_map_per_server": 1500,
    "map_slots": 1499,
    "map_name_length": 12,
    "map_name_length_ext": 16,
    "db_path_bytes": 11,
}
MAP_SLOTS = PROFILE["map_slots"]
MAP_NAME_LEN = PROFILE["map_name_length"]
MAP_NAME_LEN_EXT = PROFILE["map_name_length_ext"]
LINE_MAX = 1023          # fgets(line, 1024): at most 1023 bytes per read
MAX_DEPTH = 32
MAX_VISITS = 4096
MAX_EVENTS = 1 << 18

# Keys map_config_read recognizes but whose values are irrelevant here. They are
# recorded by key and location only, never by value (userid/passwd are credentials).
MAP_IGNORED_KEYS = frozenset(k.encode() for k in (
    "timestamp_format", "stdout_with_ansisequence", "console_silent", "userid", "passwd",
    "char_ip", "char_port", "map_ip", "bind_ip", "map_port", "autosave_time",
    "minsave_time", "save_settings", "motd_txt", "charhelp_txt", "channel_conf",
    "console", "enable_spy", "console_msg_log", "console_log_filepath"))
CONTROL = frozenset(set(range(0x00, 0x09)) | {0x0b, 0x0c} | set(range(0x0e, 0x20)) | {0x7f})
C_SPACE = b" \t\n\v\f\r"

ASSUMPTIONS = (
    "Map server started from the server working root rathena/ with no --map-config "
    "override; this models the source profile, not the installed binary's compile options.",
    "RENEWAL is defined, so map_reloadnpc reads npc/re/scripts_main.conf.",
    "Paths resolve case-sensitively, as on the Linux container, against the exact snapshot "
    "keys. Files outside rathena/{conf,db,npc,sql-files} are not in the snapshot and are "
    "reported as outside_snapshot_scope, not as missing.",
    "fopen of a directory succeeds on Linux and then reads nothing; such config imports "
    "are recorded as unsupported directory references and the result is incomplete.",
)
LIMITS = (
    "This is the ordered stock configuration selection only. It is not runtime-loaded, "
    "visible or playable content, and does not include the installed Chinese pilot or "
    "app-generated configuration.",
    "Selected NPC source file counts are not NPC entity, spawn, monster, quest, warp, "
    "map-loaded or coverage totals. NPC script bodies are never parsed or copied.",
    "Map entries are configuration candidates. map_index, map cache/GRF lookup and "
    "successful map loading are not checked; duplicates are kept as the server keeps them.",
    "OnInit effects, script visibility, YAML database definitions and import YAML merges "
    "are outside this model.",
    "Configuration lines longer than 1023 bytes, NUL and other control bytes (except tab, "
    "CR and LF) in a visited config file, and non-ASCII bytes in a recorded value are "
    "refused rather than modelled.",
    "Absolute paths, '..' components and backslashes in import/npc paths are refused. "
    "Import cycles, nesting deeper than %d and more than %d visits are refused." % (
        MAX_DEPTH, MAX_VISITS),
    "Values of settings other than map, delmap, npc, delnpc, import, db_path and use_grf "
    "are never recorded; only the key, count and locations are.",
    "Publication reserves the destination with an exclusive mkdir and writes the "
    "completion record last. A concurrent writer running as the same user could interfere "
    "between steps; without selection-complete.json the output is incomplete.",
)


class SelectionError(ValueError):
    """Input that cannot be modelled without guessing, or output that cannot be published."""


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def text(raw):
    """Bytes to a JSON-safe string; non-ASCII is escaped, never decoded by guess."""
    return raw.decode("ascii", "backslashreplace")


# --- Snapshot verification --------------------------------------------------------

DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK


def _read_at(dir_fd, name, limit, where):
    try:
        fd = os.open(name, FILE_FLAGS, dir_fd=dir_fd)
    except OSError as exc:
        raise SelectionError(f"{where}: cannot open without following links: {exc}") from None
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise SelectionError(f"{where}: not a regular file")
        if info.st_size > limit:
            raise SelectionError(f"{where}: larger than {limit} bytes")
        data = handle.read(limit + 1)
    if len(data) != info.st_size:
        raise SelectionError(f"{where}: changed size while being read")
    return data


def _load_json(data, what):
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise SelectionError(f"{what}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=unique_pairs)
    except SelectionError:
        raise
    except (UnicodeDecodeError, ValueError) as exc:
        raise SelectionError(f"{what}: invalid JSON: {exc}") from None


def _walk(dir_fd, prefix, found):
    """Collect {relative path: bytes} of every regular file; refuse anything else."""
    for name in sorted(os.listdir(dir_fd)):
        path = prefix + name
        try:
            info = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
        except OSError as exc:
            raise SelectionError(f"snapshot: cannot stat {path!r}: {exc}") from None
        if stat.S_ISDIR(info.st_mode):
            try:
                child = os.open(name, DIR_FLAGS, dir_fd=dir_fd)
            except OSError as exc:
                raise SelectionError(f"snapshot: cannot open directory {path!r}: {exc}") from None
            try:
                _walk(child, path + "/", found)
            finally:
                os.close(child)
        elif stat.S_ISREG(info.st_mode):
            found[path] = _read_at(dir_fd, name, MAX_FILE, f"snapshot {path!r}")
        else:
            kind = "symlink" if stat.S_ISLNK(info.st_mode) else "special file"
            raise SelectionError(f"snapshot: unsupported {kind} {path!r}; links are never followed")


def verify_manifest(manifest_bytes, files, pin=PINNED_MANIFEST_SHA256, counts=PINNED_COUNTS):
    """Check manifest pin and the exact {path: bytes} set. Return the manifest dict."""
    digest = sha256(manifest_bytes)
    if pin is not None and digest != pin:
        raise SelectionError(f"snapshot manifest SHA-256 {digest} is not the pinned {pin}")
    manifest = _load_json(manifest_bytes, SNAPSHOT_MANIFEST)
    records = manifest.get("files") if isinstance(manifest, dict) else None
    if not isinstance(records, list):
        raise SelectionError("snapshot manifest has no file list")
    listed = {}
    for record in records:
        if (not isinstance(record, dict) or not isinstance(record.get("path"), str)
                or not isinstance(record.get("bytes"), int)
                or not isinstance(record.get("sha256"), str)):
            raise SelectionError("snapshot manifest has a malformed file record")
        path = record["path"]
        if path in listed or path == SNAPSHOT_MANIFEST:
            raise SelectionError(f"snapshot manifest lists {path!r} twice or reserved")
        listed[path] = record
    total = sum(r["bytes"] for r in listed.values())
    if counts is not None and (len(listed) != counts["files"] or total != counts["bytes"]):
        raise SelectionError(f"snapshot manifest lists {len(listed)} files/{total} bytes, "
                             f"pinned {counts['files']}/{counts['bytes']}")
    extra = sorted(set(files) - set(listed))
    missing = sorted(set(listed) - set(files))
    if extra or missing:
        raise SelectionError(f"snapshot file set differs from manifest: "
                             f"unexpected {extra[:5]}, missing {missing[:5]}")
    for path, record in listed.items():
        body = files[path]
        if len(body) != record["bytes"] or sha256(body) != record["sha256"]:
            raise SelectionError(f"snapshot file {path!r} differs from its manifest record")
    return manifest


def read_snapshot(root, pin=PINNED_MANIFEST_SHA256, counts=PINNED_COUNTS):
    """Return (manifest bytes, {path: bytes}) after verifying the whole snapshot."""
    try:
        info = os.lstat(root)
    except OSError as exc:
        raise SelectionError(f"snapshot root: {exc}") from None
    if not stat.S_ISDIR(info.st_mode):
        raise SelectionError(f"snapshot root is not a directory (or is a link): {root}")
    try:
        fd = os.open(root, DIR_FLAGS)
    except OSError as exc:
        raise SelectionError(f"snapshot root: {exc}") from None
    try:
        found = {}
        _walk(fd, "", found)
    finally:
        os.close(fd)
    manifest_bytes = found.pop(SNAPSHOT_MANIFEST, None)
    if manifest_bytes is None:
        raise SelectionError(f"snapshot has no {SNAPSHOT_MANIFEST}")
    verify_manifest(manifest_bytes, found, pin, counts)
    return manifest_bytes, found


# --- Line parsing (map.cpp map_config_read / map_reloadnpc_sub) -------------------

def split_lines(data, where):
    """Yield (line number, bytes incl. newline) as fgets(1024) would, refusing overlong lines."""
    if b"\0" in data:
        raise SelectionError(f"{where}: NUL byte; unsupported input")
    bad = sorted({b for b in data if b in CONTROL})
    if bad:
        raise SelectionError(f"{where}: control byte(s) {[hex(b) for b in bad]}; unsupported input")
    number, start = 0, 0
    while start < len(data):
        end = data.find(b"\n", start)
        end = len(data) if end < 0 else end + 1
        number += 1
        line = data[start:end]
        if len(line.rstrip(b"\n")) > LINE_MAX:
            raise SelectionError(f"{where}:{number}: line longer than {LINE_MAX} bytes would be "
                                 "split by fgets; unsupported input")
        yield number, line
        start = end


def parse_line(line, key_width):
    """Return ('comment'|'blank'|'key_overflow'|'pair', w1, w2) following the C code."""
    if line[:2] == b"//":
        return "comment", None, None
    cut = line.find(b"//")
    if cut >= 0:
        line = line[:cut] + b"\n" + line[cut + 1:]
    i = 0
    while i < len(line) and i < key_width and line[i] != 0x3A:
        i += 1
    if i == 0:
        return "blank", None, None
    w1 = line[:i]
    if i >= len(line) or line[i] != 0x3A:
        # %W[^:] stopped at the width or end of input without a ':'.
        return ("key_overflow" if i == key_width and i < len(line) else "blank"), w1, None
    i += 1
    while i < len(line) and line[i] in C_SPACE:
        i += 1
    j = i
    while j < len(line) and j - i < 1023 and line[j] not in b"\t\r\n":
        j += 1
    if j == i:
        return "blank", w1, None
    return "pair", w1, line[i:j].rstrip(b" ")


def config_switch(value):
    low = value.lower()
    if low in (b"on", b"yes", b"oui", b"ja", b"si", b"sim"):
        return 1
    if low in (b"off", b"no", b"non", b"nein", b"nao"):
        return 0
    return None  # strtol(str, nullptr, 0) is not modelled; raw value is recorded


def map_name(raw):
    """mapindex_getmapname: (name bytes, flags)."""
    flags = []
    length = min(len(raw), MAP_NAME_LEN_EXT)
    if length == MAP_NAME_LEN_EXT:
        flags.append("too_long_warning")
        length -= 1
    if length >= 4 and raw[length - 4:length].lower() == b".gat":
        length -= 4
        flags.append("gat_stripped")
    if length > MAP_NAME_LEN - 1:
        flags.append("clipped")
        length = MAP_NAME_LEN - 1
    if length == 0:
        flags.append("empty_name")
    return raw[:length], flags


# --- Path resolution --------------------------------------------------------------

def logical_path(raw, where):
    """Safe server-root-relative path for raw config text, or raise. Returns (path, trailing_slash)."""
    if any(b >= 0x80 for b in raw):
        raise SelectionError(f"{where}: non-ASCII path {text(raw)!r}; unsupported input")
    value = raw.decode("ascii")
    if value.startswith("/"):
        raise SelectionError(f"{where}: absolute path {value!r} leaves the server root; refused")
    if "\\" in value:
        raise SelectionError(f"{where}: backslash in path {value!r}; unsupported input")
    parts = value.split("/")
    if ".." in parts:
        raise SelectionError(f"{where}: '..' in path {value!r}; refused")
    trailing = value.endswith("/")
    parts = [p for p in parts if p not in ("", ".")]
    return "/".join(parts), trailing


class Tree:
    """Exact-key view of the verified snapshot below the server working root."""

    def __init__(self, files):
        prefix = SERVER_ROOT + "/"
        self.files = {p[len(prefix):]: body for p, body in files.items() if p.startswith(prefix)}
        self.dirs = {""}
        for path in self.files:
            parts = path.split("/")
            for depth in range(1, len(parts)):
                self.dirs.add("/".join(parts[:depth]))
        self.fold = {}
        for path in list(self.files) + list(self.dirs):
            self.fold.setdefault(path.casefold(), []).append(path)

    def lookup(self, path, trailing):
        """Return (kind, detail): file, directory, missing, case_mismatch, outside_snapshot_scope."""
        if path in self.files:
            return ("missing", "trailing slash on a regular file") if trailing else ("file", None)
        if path in self.dirs:
            return "directory", None
        if path.casefold() in self.fold:
            return "case_mismatch", sorted(SERVER_ROOT + "/" + p for p in self.fold[path.casefold()])
        if path.split("/")[0] not in SCOPE_DIRS:
            return "outside_snapshot_scope", None
        return "missing", None


# --- Startup model ----------------------------------------------------------------

class Model:
    def __init__(self, tree):
        self.tree = tree
        self.visits, self.events, self.diagnostics = [], [], []
        self.maps, self.map_rejected = [], []
        self.npcs = []
        self.settings = {}
        self.ignored = {}
        self.stack = []

    def _event(self, **event):
        if len(self.events) >= MAX_EVENTS:
            raise SelectionError(f"more than {MAX_EVENTS} configuration events; refused")
        event["seq"] = len(self.events)
        self.events.append(event)
        return event

    def _diag(self, kind, where, **detail):
        self.diagnostics.append(dict(kind=kind, phase=where[0], file=where[1], line=where[2],
                                     **detail))

    def visit(self, phase, raw, origin):
        """Read one config file at its position. origin: (phase, file, line) or None."""
        where = origin or (phase, None, None)
        label = f"{origin[1]}:{origin[2]}" if origin else "startup"
        path, trailing = logical_path(raw, f"{label}: import {text(raw)!r}")
        kind, detail = self.tree.lookup(path, trailing)
        index = len(self.visits)
        record = {"index": index, "phase": phase, "raw": text(raw), "path": path,
                  "depth": len(self.stack), "status": kind,
                  "from": None if origin is None else {"file": origin[1], "line": origin[2],
                                                       "visit": self.stack[-1]}}
        if kind != "file":
            record["detail"] = detail
            self.visits.append(record)
            self._event(phase=phase, file=where[1], line=where[2],
                        op="import" if origin else "startup_read", raw=text(raw),
                        result=kind, visit=index)
            self._diag("unsupported_directory_import" if kind == "directory" else
                       f"import_{kind}", where, raw=text(raw), path=path, detail=detail)
            return
        if path in [self.visits[i]["path"] for i in self.stack]:
            chain = [self.visits[i]["path"] for i in self.stack] + [path]
            raise SelectionError(f"{label}: import cycle {' -> '.join(chain)}; refused")
        if len(self.stack) >= MAX_DEPTH:
            raise SelectionError(f"{label}: import nesting deeper than {MAX_DEPTH}; refused")
        if index >= MAX_VISITS:
            raise SelectionError(f"more than {MAX_VISITS} config visits; refused")
        data = self.tree.files[path]
        record.update(manifest_path=SERVER_ROOT + "/" + path, sha256=sha256(data),
                      bytes=len(data))
        self.visits.append(record)
        self._event(phase=phase, file=where[1], line=where[2],
                    op="import" if origin else "startup_read", raw=text(raw),
                    result="visit", visit=index)
        self.stack.append(index)
        lines = {"total": 0, "comment": 0, "blank_or_unmatched": 0, "key_overflow": 0,
                 "pairs": 0}
        width = 31 if phase == "map_config" else 1023
        for number, line in split_lines(data, f"{phase} {path}"):
            lines["total"] += 1
            form, w1, w2 = parse_line(line, width)
            if form == "key_overflow":
                lines["key_overflow"] += 1
                self._event(phase=phase, file=path, line=number, op="ignored_key_overflow")
                continue
            if form != "pair":
                lines["comment" if form == "comment" else "blank_or_unmatched"] += 1
                continue
            lines["pairs"] += 1
            self.setting(phase, (phase, path, number), w1, w2)
        self.stack.pop()
        record["lines"] = lines

    def setting(self, phase, where, w1, w2):
        _, path, number = where
        key = w1.lower()
        label = f"{path}:{number}"
        if key in (b"map", b"delmap") and phase == "map_config":
            self._ascii(w2, label)
            (self.add_map if key == b"map" else self.del_map)(where, w2)
        elif key == b"npc":
            self.add_npc(where, w2)
        elif key == b"delnpc":
            self._ascii(w2, label)
            self.del_npc(where, w2)
        elif key == b"import":
            self.visit(phase, w2, where)
        elif key in (b"db_path", b"use_grf") and phase == "map_config":
            self._ascii(w2, label)
            name = key.decode()
            value = {"raw": text(w2), "file": path, "line": number}
            if key == b"db_path":
                value["effective"] = text(w2[:PROFILE["db_path_bytes"]])
                value["truncated"] = len(w2) > PROFILE["db_path_bytes"]
            else:
                value["effective"] = config_switch(w2)
            self.settings.setdefault(name, []).append(value)
            self._event(phase=phase, file=path, line=number, op=name, raw=text(w2))
        else:
            known = phase == "map_config" and key in MAP_IGNORED_KEYS
            name = text(w1)
            entry = self.ignored.setdefault((phase, name), {
                "phase": phase, "key": name, "recognized_by_parser": known,
                "count": 0, "locations": []})
            entry["count"] += 1
            entry["locations"].append({"file": path, "line": number})
            self._event(phase=phase, file=path, line=number,
                        op="ignored_setting" if known else "unknown_setting", key=name)

    @staticmethod
    def _ascii(value, label):
        if any(b >= 0x80 for b in value):
            raise SelectionError(f"{label}: non-ASCII value {text(value)!r}; unsupported input")

    def add_map(self, where, raw):
        phase, path, number = where
        if raw.lower() == b"clear":
            self._event(phase=phase, file=path, line=number, op="map_clear",
                        removed=len(self.maps))
            self.maps.clear()
            return
        if len(self.maps) >= MAP_SLOTS:
            self.map_rejected.append({"raw": text(raw), "file": path, "line": number})
            self._event(phase=phase, file=path, line=number, op="map_rejected_capacity",
                        raw=text(raw))
            self._diag("map_rejected_capacity", where, raw=text(raw))
            return
        name, flags = map_name(raw)
        entry = {"name": text(name), "raw": text(raw), "file": path, "line": number}
        if flags:
            entry["flags"] = flags
        self.maps.append(entry)
        self._event(phase=phase, file=path, line=number, op="map_add", raw=text(raw),
                    name=text(name), slot=len(self.maps) - 1)

    def del_map(self, where, raw):
        phase, path, number = where
        if raw.lower() == b"all":
            self._event(phase=phase, file=path, line=number, op="map_delete_all",
                        removed=len(self.maps))
            self.maps.clear()
            return
        name = text(map_name(raw)[0])
        for slot, entry in enumerate(self.maps):
            if entry["name"] == name:
                del self.maps[slot]
                self._event(phase=phase, file=path, line=number, op="map_delete",
                            raw=text(raw), name=name, slot=slot)
                return
        self._event(phase=phase, file=path, line=number, op="map_delete_none",
                    raw=text(raw), name=name)

    def add_npc(self, where, raw):
        phase, path, number = where
        if raw.lower() == b"clear":
            self._event(phase=phase, file=path, line=number, op="npc_clear",
                        removed=len(self.npcs))
            self.npcs.clear()
            return
        target, trailing = logical_path(raw, f"{path}:{number}: npc {text(raw)!r}")
        kind, detail = self.tree.lookup(target, trailing)
        source = raw.decode("ascii")
        if kind != "file":
            self._event(phase=phase, file=path, line=number, op="npc_not_added",
                        raw=source, result=kind)
            self._diag(f"npc_{kind}", where, raw=source, path=target, detail=detail)
            return
        if any(entry["source"] == source for entry in self.npcs):
            self._event(phase=phase, file=path, line=number, op="npc_duplicate", raw=source)
            return
        body = self.tree.files[target]
        self.npcs.append({"source": source, "manifest_path": SERVER_ROOT + "/" + target,
                          "sha256": sha256(body), "bytes": len(body),
                          "phase": phase, "file": path, "line": number})
        self._event(phase=phase, file=path, line=number, op="npc_add", raw=source,
                    position=len(self.npcs) - 1)

    def del_npc(self, where, raw):
        phase, path, number = where
        if raw.lower() == b"all":
            self._event(phase=phase, file=path, line=number, op="npc_delete_all",
                        removed=len(self.npcs))
            self.npcs.clear()
            return
        source = raw.decode("ascii")
        for position, entry in enumerate(self.npcs):
            if entry["source"] == source:
                del self.npcs[position]
                self._event(phase=phase, file=path, line=number, op="npc_delete",
                            raw=source, position=position)
                return
        self._event(phase=phase, file=path, line=number, op="npc_delete_none", raw=source)


def model_startup(files):
    """Run both startup passes over {snapshot path: bytes}. Return the Model."""
    model = Model(Tree(files))
    model.visit("map_config", PROFILE["map_conf"].encode(), None)
    model.visit("npc_config", PROFILE["npc_root"].encode(), None)  # map_reloadnpc(false): no clear
    return model


def build_selection(files, snapshot_sha256, generator_sha256=None):
    """Return the deterministic selection manifest dict."""
    model = model_startup(files)
    names, seen = [], set()
    for entry in model.maps:
        if entry["name"] not in seen:
            seen.add(entry["name"])
            names.append(entry["name"])
    by_file = {}
    for entry in model.npcs:
        by_file.setdefault(entry["manifest_path"], []).append(entry["source"])
    aliases = [{"manifest_path": p, "sources": s} for p, s in sorted(by_file.items()) if len(s) > 1]
    incomplete = [d for d in model.diagnostics if d["kind"] != "map_rejected_capacity"]
    status = "incomplete" if incomplete else "complete"
    npc_list = "".join(f"{e['sha256']}  {e['source']}\n" for e in model.npcs).encode()
    map_list = "".join(f"{e['name']}\n" for e in model.maps).encode()
    return {
        "generator": {"tool": "tools/renewal/server_selection.py", "version": VERSION,
                      "source_sha256": generator_sha256},
        "input": {"snapshot_manifest_sha256": snapshot_sha256,
                  "files": len(files), "bytes": sum(len(b) for b in files.values())},
        "source": SOURCE,
        "profile": PROFILE,
        "assumptions": list(ASSUMPTIONS),
        "status": status,
        "status_reason": ("every referenced config and NPC source path resolved in the snapshot"
                          if status == "complete" else
                          "some references were missing, outside the snapshot scope, "
                          "case-mismatched or unsupported; see diagnostics"),
        "visits": model.visits,
        "events": model.events,
        "maps": {
            "candidates": model.maps,
            "candidate_count": len(model.maps),
            "distinct_names": names,
            "distinct_count": len(names),
            "rejected_capacity": model.map_rejected,
            "list_sha256": sha256(map_list),
            "note": "configuration candidates only; no map_index, cache or load result",
        },
        "npc_sources": {
            "files": model.npcs,
            "count": len(model.npcs),
            "distinct_manifest_paths": len(by_file),
            "same_file_aliases": aliases,
            "list_sha256": sha256(npc_list),
            "note": "selected source files only; not NPC, spawn, monster, quest or coverage counts",
        },
        "settings": model.settings,
        "ignored_settings": [model.ignored[k] for k in sorted(model.ignored)],
        "diagnostics": model.diagnostics,
        "counts": {
            "visits": len(model.visits),
            "visited_files": sum(1 for v in model.visits if v["status"] == "file"),
            "events": len(model.events),
            "map_candidates": len(model.maps),
            "map_distinct_names": len(names),
            "map_rejected_capacity": len(model.map_rejected),
            "npc_source_files": len(model.npcs),
            "diagnostics": len(model.diagnostics),
        },
        "outside_this_child": [
            "NPC script parsing and entity/spawn/warp/shop counts",
            "OnInit effects and NPC visibility",
            "map_index, map cache and GRF validation; successful map loading",
            "YAML database definitions and import merges",
            "installed modifications, the Chinese pilot and app-generated configuration",
            "loaded or exercised runtime content",
        ],
        "limits": list(LIMITS),
    }


def render(manifest):
    return (json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode("ascii")


# --- Publication ------------------------------------------------------------------

def trusted_parent(out_dir):
    out_dir = Path(os.path.abspath(out_dir))
    if out_dir.name in ("", ".", ".."):
        raise SelectionError(f"invalid output directory name: {out_dir}")
    parent = Path(os.path.realpath(out_dir.parent))
    try:
        info = os.lstat(parent)
    except FileNotFoundError:
        raise SelectionError(f"output parent does not exist: {parent}") from None
    if not stat.S_ISDIR(info.st_mode):
        raise SelectionError(f"output parent is not a directory: {parent}")
    if info.st_uid != os.geteuid() or info.st_mode & 0o022:
        raise SelectionError(f"output parent must be owned by you and not group/world "
                             f"writable: {parent}")
    return parent / out_dir.name


def _write_new(dir_fd, name, data):
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=dir_fd)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)


def _read_back(dir_fd, name, expect):
    if _read_at(dir_fd, name, len(expect), f"published {name}") != expect:
        raise SelectionError(f"published {name} differs from the generated bytes")


def write_output(out_dir, manifest_bytes):
    """Publish the manifest and then the completion record into a new directory."""
    target = trusted_parent(out_dir)
    if os.path.lexists(target):
        raise SelectionError(f"output already exists, refusing to overwrite: {target}")
    complete = render({"selection_manifest": OUTPUT_MANIFEST,
                       "selection_manifest_sha256": sha256(manifest_bytes),
                       "generator_version": VERSION})
    staging = tempfile.mkdtemp(prefix=".selection-staging-", dir=target.parent)
    reserved, stage_fd, out_fd = False, None, None
    try:
        stage_fd = os.open(staging, DIR_FLAGS)
        _write_new(stage_fd, OUTPUT_MANIFEST, manifest_bytes)
        _read_back(stage_fd, OUTPUT_MANIFEST, manifest_bytes)
        os.mkdir(target, 0o700)  # exclusive: refuses any file, dir or (dangling) symlink
        reserved = True
        out_fd = os.open(target, DIR_FLAGS)
        info = os.fstat(out_fd)
        if info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise SelectionError("reserved output directory is not private to you")
        os.rename(OUTPUT_MANIFEST, OUTPUT_MANIFEST, src_dir_fd=stage_fd, dst_dir_fd=out_fd)
        _read_back(out_fd, OUTPUT_MANIFEST, manifest_bytes)
        _write_new(out_fd, OUTPUT_COMPLETE, complete)
        _read_back(out_fd, OUTPUT_COMPLETE, complete)
    except (OSError, SelectionError) as exc:
        note = ("; incomplete output without selection-complete.json may remain, inspect it "
                "before retrying" if reserved else "")
        raise SelectionError(f"could not publish output to {target}: {exc}{note}") from None
    finally:
        for fd in (stage_fd, out_fd):
            if fd is not None:
                os.close(fd)
        # Only this run's own staging entries are removed.
        try:
            os.unlink(os.path.join(staging, OUTPUT_MANIFEST))
        except FileNotFoundError:
            pass
        os.rmdir(staging)
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("snapshot", type=Path, help="canonical T06.001 snapshot directory (read-only)")
    parser.add_argument("output", type=Path, help="new output directory (must not exist)")
    args = parser.parse_args(argv)
    try:
        target = trusted_parent(args.output)
        if os.path.lexists(target):
            raise SelectionError(f"output already exists, refusing to overwrite: {target}")
        manifest_bytes, files = read_snapshot(args.snapshot)
        generator = sha256(Path(__file__).read_bytes())
        selection = build_selection(files, sha256(manifest_bytes), generator)
        data = render(selection)
        target = write_output(target, data)
    except (SelectionError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"output": str(target), "selection_manifest_sha256": sha256(data),
                      "status": selection["status"], "counts": selection["counts"]},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
