#!/usr/bin/env python3
"""Inventory every physical GRF table record of the three October client archives.

Inputs are the complete extracted-tree metadata manifest, the extracted archive
root (the directory holding data.grf, data0.grf and event.grf) and a fresh
private output directory. The fixed public profile
docs/project/fixtures/T07.007.001-profile.json is resolved relative to this
checkout and must match its pin before anything else is read; it pins the
manifest, the three archives (size, hash and header/table facts) and the
unchanged core tools/renewal/archive_catalog.py.

The core is not imported by name: its exact bytes are read through a no-follow
descriptor, checked against the profile pin and executed into a private module
instance. Only its lower-level pieces are reused (read_archive, catalog_table,
render, trusted_target, _verify_published, descriptor flags and limits). Its
INI-oriented run/build_manifest are never called and no DATA.INI is fabricated.

Enumeration is the profile's fixed basename order data.grf, data0.grf,
event.grf. It is NOT a client lookup priority: lookup_priority is null, no
winning archive is chosen, duplicates within and across archives are kept in
physical table order, and names stay raw table bytes (no alias, codec or Unicode
normalisation). The reconciled tree has no loose DATA.INI; that does not mean
all client configuration is absent.

Profile range semantics: the profile's modern stored_start is the start of the
compressed table bytes, eight bytes after table_pos (the compressed/real u32
table header). The core plan's stored_start includes that header and equals
table_pos. Legacy tables have stored_start == table_pos in both. stored_end is
the same in both.

Output: one unchanged-schema <archive>.records.jsonl per archive (core
render_record lines), inventory-manifest.json and inventory-complete.json last.
verify_inventory(output) is the read-only consumer gate. Standard library only.
"""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import posixpath
import stat
import sys
import types

VERSION = "1.0.1"
TASK = "T07.007.001"
MANIFEST_SCHEMA = "ro-october-raw-inventory/1"
COMPLETE_SCHEMA = "ro-october-raw-inventory-complete/1"
FAILED_SCHEMA = "ro-october-raw-inventory-failed/1"
PROFILE_SCHEMA = "ro-october-raw-inventory-profile/1"
OUTPUT_MANIFEST = "inventory-manifest.json"
OUTPUT_COMPLETE = "inventory-complete.json"
OUTPUT_FAILED = "inventory-failed.json"
RECORDS_SUFFIX = ".records.jsonl"

ENUMERATION_ORDER = ("data.grf", "data0.grf", "event.grf")
CHECKOUT = Path(os.path.realpath(__file__)).parents[2]
GENERATOR_REL = "tools/renewal/archive_inventory_october.py"
CORE_REL = "tools/renewal/archive_catalog.py"
PROFILE_REL = "docs/project/fixtures/T07.007.001-profile.json"
MAX_DIAGNOSTIC_CHARS = 1000
MAX_MANIFEST_DOCUMENT_BYTES = 16 << 20
MAX_COMPLETE_DOCUMENT_BYTES = 64 << 10
WRITE_BUFFER_BYTES = 1 << 20

PROFILE_KEYS = {"archives", "core", "enumeration_basis", "enumeration_order", "exclusions",
                "extracted_manifest", "lookup_priority", "priority_status", "schema",
                "source_preflight", "task", "total_header_records"}
PROFILE_ARCHIVE_KEYS = {"bytes", "declared_version", "effective_version", "extracted_path",
                        "file", "header_sha256", "layout", "record_count", "sha256",
                        "signature", "stored_end", "stored_start", "table_compressed_size",
                        "table_offset", "table_pos", "table_real_size", "table_skip"}
PROFILE_MANIFEST_KEYS = {"bytes", "directories", "files", "grf_paths", "schema", "sha256"}
DIR_ENTRY_KEYS = {"kind", "mode", "path", "path_raw_hex"}
FILE_ENTRY_KEYS = DIR_ENTRY_KEYS | {"bytes", "sha256", "reported_SHA256_prefix",
                                    "prefix_matches_final_output", "single_link"}

SEMANTICS = {
    "enumeration_order": list(ENUMERATION_ORDER),
    "enumeration_meaning": "fixed ASCII basename order of the frozen profile; physical "
                           "records only; not a client lookup priority",
    "lookup_priority": None,
    "priority_status": "not_established",
    "winning_archive": None,
    "duplicates": "kept: every physical record within and across archives in table order",
    "names": "raw table bytes as hex; no alias, filename codec, case folding or Unicode "
             "normalisation",
    "loose_data_ini": "absent from the reconciled extracted tree; not evidence that all "
                      "client configuration is absent",
}

INPUT_RULES = [
    "The public profile is resolved relative to the checkout and must match its fixed "
    "byte/hash pin and typed contract before the manifest, archives or output are touched.",
    "Core bytes are read no-follow, checked against the profile pin and executed from "
    "those exact bytes into a private module; run/build_manifest are not used.",
    "The extracted manifest must match its profile pin, list unique safe relative paths "
    "with the profile's file/directory counts and hold exactly the three profile GRF "
    "files with matching sizes and hashes. Other file bodies are not read or rehashed.",
    "The archive root listing must equal the manifest's entries directly below the "
    "archive directory (kind and file size by lstat), with no extra .grf of any case.",
    "Each archive must be a regular single-link file; it is read no-follow through the "
    "core read_archive (full SHA-256, same-descriptor header/table capture, identity "
    "before/after) and every frozen header/table fact is compared with the parsed one.",
    "Profile, core, manifest, archive root and archive identities are rechecked before "
    "the completion record is written; no archive descriptor is open at completion.",
]

PUBLICATION_RULES = [
    "Fresh exclusive 0700 output below a parent owned by you and not group/world "
    "writable, never inside the archive root.",
    "Every file is created exclusively no-follow 0600, written with checked "
    "progress, fsynced, closed with error checking and read back (size, hash, mode, "
    "identity) before the next step.",
    "inventory-complete.json is written last and binds the manifest and record-file "
    "hashes; the output set must equal the files this run created and the output path "
    "must still name the reserved directory.",
    "On failure only a verified run-owned completion record is removed, foreign "
    "replacements are preserved and a path-free inventory-failed.json is written when "
    "the reserved directory is still verifiable. A failed marker overrides any "
    "completion record.",
]

EXCLUSIONS = [
    "client lookup winner, deduplication or precedence",
    "filename codec, aliases or normalised keys",
    "payload bytes, decompression, decryption or readability",
    "configuration semantics beyond the observed absence of a loose DATA.INI",
    "installed state, maps, render, playability or full-game coverage",
    "host paths, device/inode numbers or machine identifiers",
]


class InventoryError(ValueError):
    """Input or output that cannot be inventoried or published without guessing."""
    category = "error"


class InputError(InventoryError):
    category = "input_pin"


class OutputError(InventoryError):
    category = "output"


class VerificationError(InventoryError):
    category = "verification"


class _Contract:
    """Fixed identities of one inventory run. Production uses PRODUCTION only; tests
    construct their own instance (synthetic profile) through the private entry points."""

    def __init__(self, profile_path, profile_bytes, profile_sha256, core_path, core_bytes,
                 core_sha256, generator_path):
        self.profile_path = Path(profile_path)
        self.profile_pin = {"bytes": profile_bytes, "sha256": profile_sha256}
        self.core_path = Path(core_path)
        self.core_pin = {"bytes": core_bytes, "sha256": core_sha256}
        self.generator_path = Path(generator_path)


PRODUCTION = _Contract(
    CHECKOUT / PROFILE_REL, 3180,
    "fa3e869d8f835b1cd7ea8a9c7bca8519b3c3e22a909a104576a2becfca2072a4",
    CHECKOUT / CORE_REL, 54783,
    "f785ced6006741de0bc8dbab4354d6ee5ab15fb750ddd95111fc16a2cdf15cda",
    CHECKOUT / GENERATOR_REL)

FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns,
            stat.S_IFMT(info.st_mode))


def _is_int(value):
    return type(value) is int and value >= 0


def _is_hex64(value):
    return isinstance(value, str) and len(value) == 64 and \
        all(c in "0123456789abcdef" for c in value)


def _same(left, right):
    """JSON equality that never equates booleans/floats with integer fields."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_same(v, right[k])
                                                   for k, v in left.items())
    if isinstance(left, list):
        return len(left) == len(right) and all(_same(a, b) for a, b in zip(left, right))
    return left == right


def _json(data, what, error=InputError):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    def constant(_value):
        raise ValueError("nonfinite constant")

    def floating(text):
        value = float(text)
        if not math.isfinite(value):
            raise ValueError("nonfinite number")
        return value

    try:
        return json.loads(data, object_pairs_hook=pairs, parse_constant=constant,
                          parse_float=floating)
    except (ValueError, RecursionError):
        raise error(f"{what} is not unambiguous finite JSON") from None


# --- Pinned small files -------------------------------------------------------------------

def _read_regular(path, what, limit, error=InputError):
    """Read one regular single-link file of at most limit bytes without following links.
    Return (bytes, identity); the path must still name the same file afterwards."""
    try:
        fd = os.open(path, FILE_FLAGS)
    except OSError as exc:
        raise error(f"{what} cannot be opened without following links: "
                    f"{exc.strerror}") from None
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise error(f"{what} is not a regular single-link file")
        if before.st_size > limit:
            raise error(f"{what} is {before.st_size} bytes, above {limit}")
        chunks, total = [], 0
        while total <= before.st_size:
            chunk = os.read(fd, min(8 << 20, before.st_size + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    try:
        current = os.stat(path, follow_symlinks=False)
    except OSError:
        current = None
    if total != before.st_size or _identity(before) != _identity(after) or \
            current is None or _identity(current) != _identity(before):
        raise error(f"{what} changed or was replaced while read")
    return b"".join(chunks), _identity(before)


def _read_pinned_file(path, pin, what, error=InputError):
    """Read a pinned file; return (bytes, identity) only if size and hash match."""
    data, identity = _read_regular(path, what, pin["bytes"], error)
    if len(data) != pin["bytes"] or sha256(data) != pin["sha256"]:
        raise error(f"{what} does not match its pin")
    return data, identity


def _read_generator(contract):
    """The generator describes itself: its identity is its own current bytes."""
    data, identity = _read_regular(contract.generator_path, "generator source", 4 << 20)
    return {"bytes": len(data), "sha256": sha256(data)}, identity


def _load_core(contract):
    """Execute the pinned core bytes into a private module. Return (module, identity)."""
    data, identity = _read_pinned_file(contract.core_path, contract.core_pin, "core")
    module = types.ModuleType("archive_catalog_pinned_core")
    module.__file__ = str(contract.core_path)
    exec(compile(data, str(contract.core_path), "exec"), module.__dict__)
    return module, identity


def _read_profile(contract):
    data, identity = _read_pinned_file(contract.profile_path, contract.profile_pin, "profile")
    try:
        profile = _json(data.decode("ascii"), "profile")
    except ValueError:
        raise InputError("profile is not ASCII JSON") from None
    validate_profile(profile, contract)
    return profile, identity


def validate_profile(profile, contract):
    """Typed contract of the frozen profile; refuse anything else."""
    def need(ok, why):
        if not ok:
            raise InputError(f"profile contract: {why}")

    need(isinstance(profile, dict) and set(profile) == PROFILE_KEYS, "top-level keys")
    need(profile["schema"] == PROFILE_SCHEMA and profile["task"] == TASK, "schema/task")
    need(profile["enumeration_order"] == list(ENUMERATION_ORDER), "enumeration order")
    need(profile["lookup_priority"] is None and
         profile["priority_status"] == "not_established", "priority must be unestablished")
    need(isinstance(profile["enumeration_basis"], str), "enumeration basis")
    need(isinstance(profile["exclusions"], list) and
         all(isinstance(x, str) for x in profile["exclusions"]), "exclusions")
    need(_same(profile["core"], {"path": CORE_REL, **contract.core_pin}), "core pin")
    pre = profile["source_preflight"]
    need(isinstance(pre, dict) and set(pre) == {"bytes", "sha256"} and
         _is_int(pre["bytes"]) and _is_hex64(pre["sha256"]), "source preflight")
    archives = profile["archives"]
    need(isinstance(archives, list) and len(archives) == len(ENUMERATION_ORDER), "archives")
    dirs = set()
    for name, entry in zip(ENUMERATION_ORDER, archives):
        need(isinstance(entry, dict) and set(entry) == PROFILE_ARCHIVE_KEYS,
             f"{name} keys")
        need(entry["file"] == name, "archive order")
        path = entry["extracted_path"]
        need(isinstance(path, str) and posixpath.basename(path) == name and
             _safe_relative(path), f"{name} extracted path")
        dirs.add(posixpath.dirname(path))
        for key in ("bytes", "declared_version", "effective_version", "record_count",
                    "stored_end", "stored_start", "table_offset", "table_pos", "table_skip"):
            need(_is_int(entry[key]), f"{name} {key}")
        need(_is_hex64(entry["sha256"]) and _is_hex64(entry["header_sha256"]),
             f"{name} hashes")
        need(entry["signature"] in ("Master of Magic", "Event Horizon"), f"{name} signature")
        modern = entry["layout"] in ("0x200", "0x300")
        need(modern or entry["layout"] == "legacy", f"{name} layout")
        for key in ("table_compressed_size", "table_real_size"):
            need(_is_int(entry[key]) if modern else entry[key] is None, f"{name} {key}")
        need(entry["table_pos"] == entry["table_offset"] + entry["table_skip"] and
             entry["stored_start"] == entry["table_pos"] + (8 if modern else 0) and
             entry["stored_start"] <= entry["stored_end"] <= entry["bytes"],
             f"{name} table range")
    need(len(dirs) == 1 and "" not in dirs, "archives must share one extracted directory")
    em = profile["extracted_manifest"]
    need(isinstance(em, dict) and set(em) == PROFILE_MANIFEST_KEYS, "manifest keys")
    need(all(_is_int(em[k]) for k in ("bytes", "directories", "files")) and
         _is_hex64(em["sha256"]) and isinstance(em["schema"], str), "manifest pin")
    need(em["grf_paths"] == [a["extracted_path"] for a in archives], "manifest GRF paths")
    need(_is_int(profile["total_header_records"]) and profile["total_header_records"] ==
         sum(a["record_count"] for a in archives), "total header records")


# --- Extracted metadata manifest ----------------------------------------------------------

def _safe_relative(path):
    if not path or path.startswith("/") or "\\" in path or "\0" in path:
        return False
    return all(part not in ("", ".", "..") for part in path.split("/"))


def validate_extracted_manifest(entries, profile):
    """Check the complete-tree metadata list; return facts used by the inventory."""
    em = profile["extracted_manifest"]
    if not isinstance(entries, list) or len(entries) != em["files"] + em["directories"]:
        raise InputError("extracted manifest is not a list of the profile's entry count")
    kinds, seen = {}, set()
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("kind") not in ("file", "dir"):
            raise InputError("extracted manifest entry is not a file/dir record")
        keys = FILE_ENTRY_KEYS if entry["kind"] == "file" else DIR_ENTRY_KEYS
        path = entry.get("path")
        if set(entry) != keys or not isinstance(path, str) or not _safe_relative(path):
            raise InputError("extracted manifest entry has wrong keys or an unsafe path")
        try:
            raw_ok = bytes.fromhex(entry["path_raw_hex"]).decode("utf-8") == path
        except (TypeError, ValueError):
            raw_ok = False
        if not raw_ok:
            raise InputError("extracted manifest raw path differs from its path")
        if path in seen:
            raise InputError("extracted manifest repeats a path")
        seen.add(path)
        kinds[path] = entry
        if entry["kind"] == "file" and not (
                _is_int(entry["bytes"]) and _is_hex64(entry["sha256"]) and
                isinstance(entry["reported_SHA256_prefix"], str) and
                isinstance(entry["single_link"], bool) and
                isinstance(entry["prefix_matches_final_output"], bool)):
            raise InputError("extracted manifest file entry has wrong field types")
    files = sum(1 for e in entries if e["kind"] == "file")
    if files != em["files"] or len(entries) - files != em["directories"]:
        raise InputError("extracted manifest file/directory counts differ from the profile")
    for path in seen:
        parent = posixpath.dirname(path)
        if parent and kinds.get(parent, {}).get("kind") != "dir":
            raise InputError("extracted manifest entry has no directory parent")
    grf = sorted(p for p in seen if p.lower().endswith(".grf"))
    if grf != sorted(em["grf_paths"]):
        raise InputError(f"extracted manifest holds {len(grf)} .grf paths, not exactly the "
                         "three profile archives")
    for pin in profile["archives"]:
        entry = kinds[pin["extracted_path"]]
        if entry["kind"] != "file" or entry["bytes"] != pin["bytes"] or \
                entry["sha256"] != pin["sha256"] or entry["single_link"] is not True or \
                entry["prefix_matches_final_output"] is not True or \
                not pin["sha256"].startswith(entry["reported_SHA256_prefix"]) or \
                not entry["reported_SHA256_prefix"]:
            raise InputError(f"extracted manifest entry for {pin['file']} differs from its pin")
    archive_dir = posixpath.dirname(profile["archives"][0]["extracted_path"])
    if kinds.get(archive_dir, {}).get("kind") != "dir":
        raise InputError("extracted manifest has no archive directory entry")
    children = {posixpath.basename(p): kinds[p] for p in seen
                if posixpath.dirname(p) == archive_dir}
    loose_ini = sorted(p for p in seen if posixpath.basename(p).upper() == "DATA.INI")
    return {"archive_dir": archive_dir, "children": children,
            "entries": len(entries), "files": files, "directories": len(entries) - files,
            "loose_data_ini_entries": len(loose_ini)}


def check_archive_root(root_fd, facts, profile):
    """Metadata-only reconciliation of the archive root with the manifest."""
    names = os.listdir(root_fd)
    expected = {a["file"] for a in profile["archives"]}
    grf = [n for n in names if n.lower().endswith(".grf")]
    if sorted(grf) != sorted(expected):
        raise InputError(f"archive root holds {len(grf)} .grf entries, not exactly "
                         f"{', '.join(ENUMERATION_ORDER)}")
    if sorted(names) != sorted(facts["children"]):
        raise InputError("archive root listing differs from the extracted manifest")
    for name in names:
        entry = facts["children"][name]
        info = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
        if entry["kind"] == "dir":
            ok = stat.S_ISDIR(info.st_mode)
        else:
            ok = stat.S_ISREG(info.st_mode) and info.st_size == entry["bytes"]
        if not ok:
            raise InputError("archive root entry kind or size differs from the manifest")
    return len(names)


def _archive_lstat(root_fd, name, size):
    try:
        info = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
    except OSError as exc:
        raise InputError(f"archive {name} cannot be examined: {exc.strerror}") from None
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != size:
        raise InputError(f"archive {name} is not a regular single-link file of its pinned size")
    return info


def compare_with_profile(pin, header, plan):
    """Every frozen header/table-range fact against the same-descriptor parsed data."""
    modern = header["layout"] != "legacy"
    actual = {
        "signature": header["signature"], "header_sha256": header["header_sha256"],
        "declared_version": header["declared_version"],
        "effective_version": header["effective_version"], "layout": header["layout"],
        "record_count": header["record_count"], "table_offset": header["table_offset"],
        "table_pos": header["table_pos"], "table_skip": header["table_skip"],
        # Profile stored_start is the compressed byte start for modern tables.
        "stored_start": plan["stored_start"] + (8 if modern else 0),
        "stored_end": plan["stored_end"],
        "table_compressed_size": plan.get("compressed_size"),
        "table_real_size": plan.get("real_size"),
    }
    differs = sorted(k for k, v in actual.items() if pin[k] != v)
    if differs:
        raise InputError(f"archive {pin['file']} header/table facts disagree with the "
                         f"frozen profile: {differs}")
    return {k: True for k in sorted(actual)}


# --- Checked publication ------------------------------------------------------------------
# Indirections exist so tests can inject write/fsync/close faults without patching os.

def _write_chunk(fd, view):
    return os.write(fd, view)


def _fsync(fd):
    os.fsync(fd)


def _close_fd(fd):
    os.close(fd)


class CheckedFile:
    """Exclusive, no-follow 0600 writer with checked progress, fsync and close."""

    def __init__(self, dir_fd, name, created, limit):
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600,
                     dir_fd=dir_fd)
        created[name] = None  # never unlink before ownership is verified
        self.fd, self.name, self.limit = fd, name, limit
        try:
            info = os.fstat(fd)
            created[name] = (info.st_dev, info.st_ino)
            os.fchmod(fd, 0o600)
            self.digest = hashlib.sha256()
            self.buffer = bytearray()
            self.bytes = self.lines = 0
        except BaseException:
            # A partially constructed writer never reaches its caller's abort().
            self.abort()
            raise

    def write(self, data):
        if self.bytes + len(data) > self.limit:
            raise OutputError(f"output file {self.name} above its {self.limit}-byte limit")
        self.buffer += data
        self.digest.update(data)
        self.bytes += len(data)
        self.lines += data.count(b"\n")
        if len(self.buffer) >= WRITE_BUFFER_BYTES:
            self.flush()

    def flush(self):
        view = memoryview(self.buffer)
        try:
            while view:
                written = _write_chunk(self.fd, view)
                if not isinstance(written, int) or written <= 0 or written > len(view):
                    raise OutputError(f"write of {self.name} made no valid progress")
                view = view[written:]
        finally:
            view.release()
        self.buffer = bytearray()

    def close(self):
        self.flush()
        _fsync(self.fd)
        closing, self.fd = self.fd, None
        _close_fd(closing)
        return {"file": self.name, "bytes": self.bytes, "lines": self.lines,
                "sha256": self.digest.hexdigest()}

    def abort(self):
        if self.fd is not None:
            closing, self.fd = self.fd, None
            try:
                os.close(closing)
            except OSError:
                pass


def _publish_document(core, dir_fd, name, data, created):
    writer = CheckedFile(dir_fd, name, created, len(data))
    try:
        writer.write(data)
        result = writer.close()
    except BaseException:
        writer.abort()
        raise
    core._verify_published(dir_fd, name, result["bytes"], result["sha256"], created[name])
    return result


# --- Inventory ----------------------------------------------------------------------------

class _RecordSink:
    """Write rendered core lines and track ordinals and raw names for cross-archive counts."""

    def __init__(self, writer, archive):
        self.writer, self.archive = writer, archive
        self.names = set()
        self.ordinal = 0

    def __call__(self, line):
        rec = json.loads(line)
        if rec["ordinal"] != self.ordinal or rec["archive"] != self.archive:
            raise InventoryError("core emitted records out of physical order")
        self.ordinal += 1
        self.names.add(rec["name_hex"])
        self.writer.write(line)


def _totals(archives, name_sets):
    totals = {key: sum(a["counts"][key] for a in archives)
              for key in ("raw_records", "metadata_eligible", "kind0_promotions",
                          "names_without_nul", "duplicate_raw_names")}
    totals["length_bias_underflows"] = sum(a["counts"]["length_bias_underflows"]["any"]
                                           for a in archives)
    totals["header_records"] = sum(a["header"]["record_count"] for a in archives)
    seen = {}
    for names in name_sets:
        for name in names:
            seen[name] = seen.get(name, 0) + 1
    shared = {name for name, n in seen.items() if n > 1}
    totals["unique_raw_names_across_archives"] = len(seen)
    totals["cross_archive_shared_raw_names"] = len(shared)
    totals["per_archive_shared_name_presence"] = {
        a["file"]: len(names & shared) for a, names in zip(archives, name_sets)}
    return totals


def _sanitize(message, paths):
    text = str(message)
    for path, label in paths:
        for form in {str(path), os.path.abspath(str(path)), os.path.realpath(str(path))}:
            if form and form not in ("/", "."):
                text = text.replace(form, label)
    return text[:MAX_DIAGNOSTIC_CHARS]


def run(extracted_manifest, archive_root, output):
    """Production inventory under the fixed public profile. Return (target, manifest,
    hashes). There are no pin parameters."""
    return _run(PRODUCTION, extracted_manifest, archive_root, output)


def _run(contract, extracted_manifest, archive_root, output):
    profile, profile_identity = _read_profile(contract)
    core, core_identity = _load_core(contract)
    generator, generator_identity = _read_generator(contract)
    em_pin = {"bytes": profile["extracted_manifest"]["bytes"],
              "sha256": profile["extracted_manifest"]["sha256"]}
    manifest_bytes_in, manifest_identity = _read_pinned_file(
        extracted_manifest, em_pin, "extracted manifest")
    try:
        entries = _json(manifest_bytes_in.decode("utf-8"), "extracted manifest")
    except ValueError:
        raise InputError("extracted manifest is not UTF-8 JSON") from None
    facts = validate_extracted_manifest(entries, profile)
    del entries

    try:
        target = core.trusted_target(output)
    except core.CatalogError:
        raise OutputError("output parent must exist, be a real directory owned by you and "
                          "not group/world writable") from None
    if os.path.lexists(target):
        raise OutputError("output already exists, refusing to overwrite")
    root_real = os.path.realpath(archive_root)
    parent_real = os.path.realpath(target.parent)
    if os.path.commonpath([root_real, parent_real]) == root_real:
        raise OutputError("output must not be inside the archive root")
    try:
        root_fd = os.open(archive_root, DIR_FLAGS)
    except OSError as exc:
        raise InputError(f"archive root is missing, not a directory or a link: "
                         f"{exc.strerror}") from None
    try:
        root_info = os.fstat(root_fd)
        root_entries = check_archive_root(root_fd, facts, profile)
        pre = {pin["file"]: _archive_lstat(root_fd, pin["file"], pin["bytes"])
               for pin in profile["archives"]}
        os.mkdir(target, 0o700)  # exclusive: refuses any file, dir or (dangling) symlink
    except FileExistsError:
        os.close(root_fd)
        raise OutputError("output exists, refusing") from None
    except BaseException:
        os.close(root_fd)
        raise

    out_fd, identity, created = None, None, {}
    usage = {"archive_bytes_hashed": 0, "table_bytes_captured": 0, "records": 0,
             "record_file_bytes": 0, "extracted_manifest_bytes_read": len(manifest_bytes_in),
             "archive_root_entries_examined": root_entries}
    limits = core.WORK_LIMITS
    try:
        out_fd = os.open(target, DIR_FLAGS)
        info = os.fstat(out_fd)
        identity = (info.st_dev, info.st_ino)
        if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise OutputError("reserved output directory is not private to you")
        archives, name_sets, retained = [], [], {}
        for position, pin in enumerate(profile["archives"]):
            name = pin["file"]
            core_pin = {"file": name, "bytes": pin["bytes"], "sha256": pin["sha256"]}
            header, plan, stored, size = core.read_archive(root_fd, core_pin, usage)
            after = _archive_lstat(root_fd, name, pin["bytes"])
            if _identity(after) != _identity(pre[name]):
                raise InputError(f"archive {name} identity changed between examination "
                                 "and read")
            retained[name] = _identity(after)
            agreement = compare_with_profile(pin, header, plan)
            writer = CheckedFile(out_fd, name + RECORDS_SUFFIX, created,
                                 limits["max_record_file_bytes"])
            sink = _RecordSink(writer, name)
            try:
                table, counts = core.catalog_table(header, plan, stored, size, name, sink,
                                                   pin["sha256"])
                del stored
                record_file = writer.close()
            except BaseException:
                writer.abort()
                raise
            core._verify_published(out_fd, record_file["file"], record_file["bytes"],
                                   record_file["sha256"], created[record_file["file"]])
            if counts["raw_records"] != pin["record_count"] or \
                    record_file["lines"] != pin["record_count"]:
                raise InventoryError(f"archive {name} record count differs from its header")
            usage["records"] += counts["raw_records"]
            usage["record_file_bytes"] += record_file["bytes"]
            if usage["records"] > limits["max_records_total"]:
                raise core.ValidatorRefusal("total records above the work limit")
            name_sets.append(sink.names)
            archives.append({
                "order": position, "file": name, "extracted_path": pin["extracted_path"],
                "bytes": size, "sha256": pin["sha256"],
                "input_checks": {"regular_single_link": True, "no_follow_read": True,
                                 "full_sha256": True, "identity_stable": True,
                                 "manifest_entry_matches": True},
                "header": header, "table": table, "profile_agreement": agreement,
                "counts": counts, "records_file": record_file})
        # All archive reads are finished; close the root inside the transaction so a
        # close error fails before any completion record exists.
        closing_root, root_fd = root_fd, None
        os.close(closing_root)
        totals = _totals(archives, name_sets)
        del name_sets
        if totals["raw_records"] != profile["total_header_records"]:
            raise InventoryError("parsed record total differs from the profile total")
        manifest = _build_manifest(contract, profile, core, generator, facts, archives,
                                   totals, usage)
        manifest_bytes = core.render(manifest)
        if len(manifest_bytes) > MAX_MANIFEST_DOCUMENT_BYTES:
            raise OutputError("inventory manifest above its size limit")
        _publish_document(core, out_fd, OUTPUT_MANIFEST, manifest_bytes, created)
        complete = core.render(_complete_document(manifest, manifest_bytes))
        hashes = {"manifest_sha256": sha256(manifest_bytes),
                  "manifest_bytes": len(manifest_bytes), "complete_sha256": sha256(complete)}

        # Recheck every retained input identity immediately before completion.
        _recheck_inputs(contract, profile_identity, core_identity, extracted_manifest,
                        em_pin, manifest_identity, archive_root, root_info, retained,
                        profile, generator, generator_identity)
        _check_target(target, identity)
        _publish_document(core, out_fd, OUTPUT_COMPLETE, complete, created)
        if sorted(os.listdir(out_fd)) != sorted(created):
            raise OutputError("output directory holds files this run did not write")
        _check_target(target, identity)
        _verify_inventory(target, contract, expect_identity=identity)
        # The consumer is not an ownership oracle for this run. It may have read
        # byte-identical foreign files or an old directory after a path swap.
        _recheck_inputs(contract, profile_identity, core_identity, extracted_manifest,
                        em_pin, manifest_identity, archive_root, root_info, retained,
                        profile, generator, generator_identity)
        expected_files = {a["records_file"]["file"]: a["records_file"] for a in archives}
        expected_files[OUTPUT_MANIFEST] = {"bytes": len(manifest_bytes),
                                           "sha256": hashes["manifest_sha256"]}
        expected_files[OUTPUT_COMPLETE] = {"bytes": len(complete),
                                           "sha256": hashes["complete_sha256"]}
        if sorted(os.listdir(out_fd)) != sorted(created):
            raise OutputError("output directory holds files this run did not write")
        for name, expected in expected_files.items():
            _private_file(os.stat(name, dir_fd=out_fd, follow_symlinks=False), name,
                          OutputError)
            core._verify_published(out_fd, name, expected["bytes"], expected["sha256"],
                                   created[name])
        _check_target(target, identity)
        closing_fd, out_fd = out_fd, None
        _close_fd(closing_fd)
        _check_target(target, identity)
    except Exception as exc:
        _fail_publication(core, exc, target, identity, out_fd, created)
    finally:
        if root_fd is not None:
            try:
                os.close(root_fd)
            except OSError:
                pass  # failure already reported, before completion publication
        if out_fd is not None:
            try:
                os.close(out_fd)
            except OSError:
                pass  # failure already reported; never mask its cleanup outcome
    return target, manifest, hashes


def _check_target(target, identity):
    try:
        info = os.stat(target, follow_symlinks=False)
    except OSError:
        raise OutputError("reserved output directory is no longer at its path") from None
    if not stat.S_ISDIR(info.st_mode) or (info.st_dev, info.st_ino) != identity:
        raise OutputError("reserved output directory was replaced")
    if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise OutputError("reserved output directory is not private to you")


def _recheck_inputs(contract, profile_identity, core_identity, extracted_manifest, em_pin,
                    manifest_identity, archive_root, root_info, retained, profile, generator,
                    generator_identity=None):
    manifest_data = None
    for path, pin, what, before in (
            (contract.profile_path, contract.profile_pin, "profile", profile_identity),
            (contract.core_path, contract.core_pin, "core", core_identity),
            (extracted_manifest, em_pin, "extracted manifest", manifest_identity),
            (contract.generator_path, generator, "generator source", generator_identity)):
        data, now = _read_pinned_file(path, pin, what)
        if what == "extracted manifest":
            manifest_data = data
        if before is not None and now != before:
            raise InputError(f"{what} identity changed during the run")
    try:
        fd = os.open(archive_root, DIR_FLAGS)
    except OSError:
        raise InputError("archive root disappeared during the run") from None
    try:
        if _identity(os.fstat(fd))[:2] != _identity(root_info)[:2]:
            raise InputError("archive root was replaced during the run")
        facts = validate_extracted_manifest(_json(manifest_data, "extracted manifest"),
                                            profile)
        check_archive_root(fd, facts, profile)
        for pin in profile["archives"]:
            info = _archive_lstat(fd, pin["file"], pin["bytes"])
            if _identity(info) != retained[pin["file"]]:
                raise InputError(f"archive {pin['file']} changed after it was read")
        current = os.stat(archive_root, follow_symlinks=False)
        if not stat.S_ISDIR(current.st_mode) or \
                _identity(current)[:2] != _identity(root_info)[:2]:
            raise InputError("archive root was replaced during the recheck")
    finally:
        os.close(fd)


def _build_manifest(contract, profile, core, generator, facts, archives, totals, usage):
    em = profile["extracted_manifest"]
    return {
        "schema": MANIFEST_SCHEMA,
        "task": TASK,
        "kind": "raw physical GRF table inventory of the three October archives",
        "status": "complete",
        "status_meaning": "every declared physical record of every profile archive was "
                          "inventoried under the bounded core policy; not a lookup "
                          "priority, filename codec, payload, map, render, playability or "
                          "coverage result",
        "generator": {"tool": GENERATOR_REL, "version": VERSION, **generator},
        "core": {"path": CORE_REL, **contract.core_pin, "version": core.VERSION,
                 "reused": ["read_archive", "catalog_table", "render", "trusted_target",
                            "_verify_published", "WORK_LIMITS"],
                 "not_used": ["run", "build_manifest", "read_inputs",
                              "verify_input_manifest", "input_manifest_agreement"]},
        "profile": {"path": PROFILE_REL, **contract.profile_pin, "schema": profile["schema"],
                    "source_preflight": profile["source_preflight"]},
        "extracted_manifest": {"bytes": em["bytes"], "sha256": em["sha256"],
                               "schema": em["schema"], "entries": facts["entries"],
                               "files": facts["files"], "directories": facts["directories"],
                               "grf_paths": em["grf_paths"],
                               "archive_directory": facts["archive_dir"],
                               "archive_directory_entries": len(facts["children"]),
                               "loose_data_ini_entries": facts["loose_data_ini_entries"],
                               "other_bodies_read": False},
        "enumeration_basis": profile["enumeration_basis"],
        "enumeration_order": list(ENUMERATION_ORDER),
        "lookup_priority": None,
        "priority_status": "not_established",
        "semantics": SEMANTICS,
        "source_rules": {"source": core.SOURCE, "validator_policy": core.VALIDATOR_POLICY,
                         "input_rules": INPUT_RULES, "publication_rules": PUBLICATION_RULES,
                         "profile_range_semantics":
                             "profile modern stored_start = core stored_start + 8 "
                             "(compressed bytes after the u32 size header); legacy equal"},
        "archives": archives,
        "totals": totals,
        "work_limits": core.WORK_LIMITS,
        "work_usage": usage,
        "exclusions": profile["exclusions"] + EXCLUSIONS,
    }


def _complete_document(manifest, manifest_bytes):
    return {
        "schema": COMPLETE_SCHEMA, "task": TASK, "generator_version": VERSION,
        "status": manifest["status"], "inventory_manifest": OUTPUT_MANIFEST,
        "inventory_manifest_bytes": len(manifest_bytes),
        "inventory_manifest_sha256": sha256(manifest_bytes),
        "record_files": {a["records_file"]["file"]: a["records_file"]["sha256"]
                         for a in manifest["archives"]},
    }


def _fail_publication(core, exc, target, identity, out_fd, created):
    """Remove only a verified owned completion record, write a path-free failure marker
    when the reserved directory is verifiable, and raise a categorized error."""
    note = "; partial output remains (failed); inspect it before deleting or retrying"
    cleanup_fd, reopened = out_fd, False
    try:
        if cleanup_fd is None and identity is not None:
            # Reopen only the directory this run reserved, never a replacement.
            cleanup_fd = os.open(target, DIR_FLAGS)
            reopened = True
            current = os.fstat(cleanup_fd)
            if (current.st_dev, current.st_ino) != identity:
                os.close(cleanup_fd)
                cleanup_fd, reopened = None, False
                raise OutputError("reserved output directory was replaced")
    except Exception as problem:
        note += f"; reserved directory not verifiable ({type(problem).__name__})"
        cleanup_fd = None
    if OUTPUT_COMPLETE in created and cleanup_fd is not None:
        try:
            marker = os.stat(OUTPUT_COMPLETE, dir_fd=cleanup_fd, follow_symlinks=False)
            if not stat.S_ISREG(marker.st_mode) or \
                    (marker.st_dev, marker.st_ino) != created[OUTPUT_COMPLETE]:
                raise OutputError("completion was replaced; foreign file preserved")
            os.unlink(OUTPUT_COMPLETE, dir_fd=cleanup_fd)
        except FileNotFoundError:
            pass
        except Exception as cleanup:
            note += (f"; could not remove {OUTPUT_COMPLETE} ({type(cleanup).__name__}); "
                     "treat this output as failed despite the record")
    elif OUTPUT_COMPLETE in created:
        note += f"; {OUTPUT_COMPLETE} could not be verified for removal; treat as failed"
    if isinstance(exc, (InventoryError, core.CatalogError)):
        category, detail = exc.category, str(exc)
    elif isinstance(exc, OSError):
        # strerror only: OSError text can carry file names.
        category, detail = "output", f"{type(exc).__name__}: {exc.strerror or exc.errno}"
    else:
        category, detail = "unexpected", type(exc).__name__
    if cleanup_fd is not None and OUTPUT_FAILED not in created:
        try:
            _publish_document(core, cleanup_fd, OUTPUT_FAILED, core.render({
                "schema": FAILED_SCHEMA, "task": TASK, "generator_version": VERSION,
                "status": "failed", "category": category,
                "files_written_by_run": sorted(set(created) - {OUTPUT_COMPLETE}),
                "meaning": "failed publication; this marker overrides any completion "
                           "record; do not use this directory as an inventory"}), created)
        except Exception as marker:
            note += f"; failure marker not written ({type(marker).__name__})"
    if reopened:
        try:
            os.close(cleanup_fd)
        except OSError:
            pass  # preserve the publication diagnostic
    error = type(exc) if isinstance(exc, InventoryError) else OutputError
    prefix = "unexpected: " if category == "unexpected" else ""
    failure = error(f"{prefix}{detail}{note}")
    failure.category = category
    raise failure from None


# --- Consumer gate ------------------------------------------------------------------------

def verify_inventory(output):
    """Read-only consumer gate under the production contract. Return the validated
    manifest or raise VerificationError. Finding a completion record is not enough."""
    return _verify_inventory(output, PRODUCTION)


def _private_file(info, name, error=VerificationError):
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or \
            stat.S_IMODE(info.st_mode) != 0o600 or info.st_uid != os.geteuid():
        raise error(f"{name} is not a private single-link regular file")


def _remember_file(dir_fd, name, before, after, identities):
    _private_file(after, name)
    current = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
    _private_file(current, name)
    if _identity(before) != _identity(after) or _identity(current) != _identity(before):
        raise VerificationError(f"{name} changed or was replaced while read")
    if identities is not None:
        identities[name] = _identity(before)


def _read_output_file(dir_fd, name, limit, identities=None):
    fd = os.open(name, FILE_FLAGS, dir_fd=dir_fd)
    try:
        before = os.fstat(fd)
        _private_file(before, name)
        if before.st_size > limit:
            raise VerificationError(f"{name} is above its document limit")
        chunks, total = [], 0
        while total <= before.st_size:
            chunk = os.read(fd, min(8 << 20, before.st_size + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    _remember_file(dir_fd, name, before, after, identities)
    if total != before.st_size:
        raise VerificationError(f"{name} changed while read")
    return b"".join(chunks)


def _canonical_json(data, name):
    try:
        doc = _json(data.decode("ascii"), name, VerificationError)
    except UnicodeError:
        raise VerificationError(f"{name} is not ASCII JSON") from None
    if (json.dumps(doc, ensure_ascii=True, indent=1, sort_keys=True) + "\n").encode() != data:
        raise VerificationError(f"{name} is not in canonical form")
    return doc


def _verify_inventory(output, contract, expect_identity=None):
    try:
        return _verify_tree(output, contract, expect_identity)
    except VerificationError:
        raise
    except (ValueError, OSError, KeyError, TypeError, AttributeError, IndexError,
            OverflowError, RecursionError):
        raise VerificationError("inventory refused: malformed, changed or unreadable "
                                "inventory contract") from None


def _need(ok, why):
    if not ok:
        raise VerificationError(f"inventory refused: {why}")


def _header_contract(header, pin, core):
    # Validate the reported raw u32 fields using the unchanged core, without
    # rereading any archive or reconstructing/claiming its unreported header bytes.
    keys = {"signature", "signature_field_hex", "header_sha256", "declared_version",
            "field_u32_30", "field_u32_34", "field_u32_38", "effective_version", "layout",
            "version_provenance", "count_rule", "table_offset", "record_count",
            "table_skip", "table_pos"}
    _need(isinstance(header, dict) and set(header) == keys, "header keys")
    _need(all(_is_int(header[k]) for k in
              ("declared_version", "field_u32_30", "field_u32_34", "field_u32_38",
               "effective_version", "table_offset", "record_count", "table_skip",
               "table_pos")), "header integer types")
    field = header["signature_field_hex"]
    _need(isinstance(field, str) and len(field) == 30 and
          all(c in "0123456789abcdef" for c in field), "signature field")
    signature = bytes.fromhex(field)
    probe = bytearray(46)
    probe[:15] = signature
    for offset, key in ((30, "field_u32_30"), (34, "field_u32_34"),
                        (38, "field_u32_38"), (42, "declared_version")):
        _need(header[key] < 1 << 32, "header u32 range")
        probe[offset:offset + 4] = header[key].to_bytes(4, "little")
    expected = core.parse_header(probe)
    # The actual 46-byte hash is frozen by the profile; probe is only a field
    # consistency check, not an independently reconstructed header/hash proof.
    expected["header_sha256"] = pin["header_sha256"]
    _need(_same(header, expected), "source-derived header fields")
    plan = {"stored_start": pin["table_pos"], "stored_end": pin["stored_end"]}
    if pin["layout"] != "legacy":
        plan.update(compressed_size=pin["table_compressed_size"],
                    real_size=pin["table_real_size"])
    return compare_with_profile(pin, header, plan)


_RECORD_BASE = {
    "archive", "archive_sha256", "ordinal", "table_offset", "record_bytes", "name_hex",
    "name_length", "name_terminated", "compressed_size", "length_aligned", "real_size",
    "original_kind", "effective_kind", "metadata_filter", "payload_offset_field",
    "diagnostic_body_range", "diagnostic_body_range_within_archive",
}
_RECORD_LEGACY = {
    "block_length", "block_low_byte", "derived_name_length", "name_start", "metadata_offset",
    "encoded_region_bytes", "encoded_region_sha256", "encoded_name_sha256",
    "transformed_blocks", "untransformed_name_bytes", "size_field", "aligned_field",
    "derived_compressed_size", "derived_length_aligned", "compressed_underflow",
    "aligned_underflow", "header_encryption_flag", "archive_offset",
}


def _record_contract(rec, pin, ordinal, consumed, core):
    """Literal typed fields/relations of core modern_records/legacy_records.

    No table/body is reopened and no codec is inferred. Opaque encoded-region
    hashes remain bound observations, not a claim to authenticate rewritten rows.
    """
    legacy = pin["layout"] == "legacy"
    expected_keys = _RECORD_BASE | (_RECORD_LEGACY if legacy else {"kind_promotion"})
    _need(isinstance(rec, dict) and set(rec) == expected_keys, "record keys")
    integer_keys = {"ordinal", "table_offset", "record_bytes", "name_length",
                    "compressed_size", "length_aligned", "real_size", "original_kind",
                    "effective_kind", "payload_offset_field"}
    if legacy:
        integer_keys |= _RECORD_LEGACY - {
            "encoded_region_sha256", "encoded_name_sha256", "derived_compressed_size",
            "derived_length_aligned", "compressed_underflow", "aligned_underflow",
            "header_encryption_flag"}
    _need(all(_is_int(rec[k]) for k in integer_keys), "record integer types")
    _need(rec["ordinal"] == ordinal and rec["table_offset"] == consumed and
          rec["archive"] == pin["file"] and rec["archive_sha256"] == pin["sha256"],
          "record identity/order")
    text = rec["name_hex"]
    _need(isinstance(text, str) and len(text) == 2 * rec["name_length"] and
          all(c in "0123456789abcdef" for c in text), "record raw name hex")
    raw = bytes.fromhex(text)
    _need(b"\0" not in raw and type(rec["name_terminated"]) is bool,
          "record name termination")
    _need(all(rec[k] < 1 << 32 for k in
              ("real_size", "original_kind", "compressed_size", "length_aligned")) and
          rec["original_kind"] < 256 and rec["effective_kind"] < 256,
          "record source integer ranges")
    effective = rec["original_kind"]
    if legacy:
        _need(all(type(rec[k]) is int for k in
                  ("derived_compressed_size", "derived_length_aligned")),
              "legacy signed integer types")
        block = rec["block_length"]
        derived = max((block & 255) - 6, 0)
        region = block - 2
        _need(block < 1 << 32 and region >= 0 and 6 + derived <= 4 + block,
              "legacy name region")
        blocks = min((derived + 7) // 8, region // 8)
        fields = {"block_low_byte": block & 255, "derived_name_length": derived,
                  "name_start": 6, "metadata_offset": 4 + block,
                  "encoded_region_bytes": region, "transformed_blocks": blocks,
                  "untransformed_name_bytes": max(derived - 8 * blocks, 0),
                  "record_bytes": 4 + block + 17,
                  "archive_offset": pin["table_pos"] + consumed}
        _need(all(_same(rec[k], v) for k, v in fields.items()), "legacy field relations")
        _need(rec["name_length"] < derived if rec["name_terminated"] else
              rec["name_length"] == derived, "legacy name length")
        _need(_is_hex64(rec["encoded_region_sha256"]) and
              _is_hex64(rec["encoded_name_sha256"]), "legacy encoded hashes")
        _need(all(rec[k] < 1 << 32 for k in ("size_field", "aligned_field")),
              "legacy stored size ranges")
        compressed = rec["size_field"] - rec["real_size"] - core.LEGACY_LENGTH_BIAS
        aligned = rec["aligned_field"] - core.LEGACY_ALIGNED_BIAS
        _need(_same(rec["derived_compressed_size"], compressed) and
              _same(rec["derived_length_aligned"], aligned) and
              _same(rec["compressed_underflow"], compressed < 0) and
              _same(rec["aligned_underflow"], aligned < 0) and
              rec["compressed_size"] == max(compressed, 0) and
              rec["length_aligned"] == max(aligned, 0), "legacy length biases")
        encryption = None
        if compressed < 0 or aligned < 0:
            effective &= ~core.TYPE_FILE & 255
        elif effective & core.TYPE_FILE:
            bit = core.header_encryption(raw)
            effective |= bit
            encryption = "header" if bit == core.TYPE_ENCRYPT_HEADER else "mixed"
        _need(rec["header_encryption_flag"] == encryption, "legacy encryption flag")
    else:
        promotion = None
        if effective == 0 and rec["real_size"] > 0 and \
                rec["compressed_size"] == rec["real_size"]:
            effective, promotion = core.TYPE_FILE, "kind0_stored_file_to_file"
        _need(rec["kind_promotion"] == promotion and rec["name_terminated"] is True and
              rec["record_bytes"] == rec["name_length"] + 1 +
              (21 if pin["effective_version"] == 0x300 else 17), "modern field relations")
    _need(rec["effective_kind"] == effective and rec["metadata_filter"] ==
          core.metadata_filter(rec["real_size"], effective), "record effective metadata")
    offset = rec["payload_offset_field"]
    _need(offset < 1 << (64 if pin["effective_version"] == 0x300 else 32),
          "payload offset range")
    body = [offset + core.HEADER_SIZE, offset + core.HEADER_SIZE + rec["length_aligned"]]
    _need(_same(rec["diagnostic_body_range"], body) and
          _same(rec["diagnostic_body_range_within_archive"], body[1] <= pin["bytes"]),
          "diagnostic range relation")
    return raw


def _table_contract(table, pin, consumed):
    modern = pin["layout"] != "legacy"
    keys = {"stored_offset", "stored_bytes", "stored_sha256", "form", "table_bytes",
            "table_sha256", "consumed_bytes", "trailing_bytes", "trailing_sha256"}
    if modern:
        keys |= {"compressed_size", "real_size", "compressed_sha256"}
    _need(isinstance(table, dict) and set(table) == keys, "table keys")
    length = pin["table_real_size"] if modern else pin["stored_end"] - pin["table_pos"]
    fields = {"stored_offset": pin["table_pos"],
              "stored_bytes": pin["stored_end"] - pin["table_pos"],
              "form": "zlib table behind compressed/real u32 sizes" if modern else
                      "clear legacy table to EOF",
              "table_bytes": length, "consumed_bytes": consumed,
              "trailing_bytes": length - consumed}
    if modern:
        fields.update(compressed_size=pin["table_compressed_size"], real_size=length)
    _need(0 <= consumed <= length and all(_same(table[k], v) for k, v in fields.items()),
          "table ranges/consumption")
    _need(all(_is_hex64(table[k]) for k in keys if k.endswith("sha256")), "table hashes")
    _need(modern or table["stored_sha256"] == table["table_sha256"], "legacy table hash")
    if consumed == length:
        _need(table["trailing_sha256"] == sha256(b""), "empty trailing hash")


def _verify_records(dir_fd, rf, archive, archive_sha256, limit, *, pin, core,
                    identities=None):
    _need(isinstance(rf, dict) and set(rf) == {"file", "bytes", "lines", "sha256"} and
          rf["file"] == archive + RECORDS_SUFFIX and _is_int(rf["bytes"]) and
          _is_int(rf["lines"]) and _is_hex64(rf["sha256"]), "record-file contract")
    name = rf["file"]
    fd = os.open(name, FILE_FLAGS, dir_fd=dir_fd)
    try:
        before = os.fstat(fd)
        _private_file(before, name)
        _need(before.st_size == rf["bytes"] <= limit and rf["lines"] == pin["record_count"],
              "record-file size/lines")
        digest = hashlib.sha256()
        pending, ordinal, total, consumed = b"", 0, 0, 0
        summary = core.Summary()
        names = set()
        while total <= before.st_size:
            chunk = os.read(fd, min(core.WORK_LIMITS["read_chunk_bytes"],
                                    before.st_size + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            _need(total <= before.st_size, "record-file growth")
            digest.update(chunk)
            lines = (pending + chunk).split(b"\n")
            pending = lines.pop()
            for line in lines:
                _need(ordinal < pin["record_count"], "extra record")
                try:
                    rec = _json(line.decode("ascii"), "record", VerificationError)
                except UnicodeError:
                    raise VerificationError("inventory refused: non-ASCII record") from None
                _need(json.dumps(rec, ensure_ascii=True, sort_keys=True,
                                 separators=(",", ":")).encode() == line,
                      "noncanonical record")
                raw = _record_contract(rec, pin, ordinal, consumed, core)
                consumed += rec["record_bytes"]
                table_size = pin["table_real_size"] if pin["layout"] != "legacy" else \
                    pin["stored_end"] - pin["table_pos"]
                _need(consumed <= table_size, "record table bounds")
                names.add(raw.hex())
                summary.add(rec)
                ordinal += 1
        after = os.fstat(fd)
    finally:
        os.close(fd)
    _remember_file(dir_fd, name, before, after, identities)
    _need(not pending and total == rf["bytes"] and digest.hexdigest() == rf["sha256"] and
          ordinal == rf["lines"], "record-file hash or line binding")
    return summary.result(), names, consumed


def _verify_tree(output, contract, expect_identity):
    profile, profile_identity = _read_profile(contract)
    core, core_identity = _load_core(contract)
    generator, generator_identity = _read_generator(contract)
    names = [a["file"] for a in profile["archives"]]
    record_names = [n + RECORDS_SUFFIX for n in names]
    identities = {}
    dir_fd = os.open(output, DIR_FLAGS)
    try:
        info = os.fstat(dir_fd)
        identity = (info.st_dev, info.st_ino)
        _need(expect_identity is None or identity == expect_identity,
              "directory is not the expected one")
        _check_target(output, identity)
        _need(info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == 0o700,
              "directory owner/mode")
        listing = sorted(os.listdir(dir_fd))
        _need(listing == sorted(record_names + [OUTPUT_MANIFEST, OUTPUT_COMPLETE]),
              "failed, missing or extra files")
        complete = _canonical_json(_read_output_file(dir_fd, OUTPUT_COMPLETE,
                                                     MAX_COMPLETE_DOCUMENT_BYTES, identities),
                                   OUTPUT_COMPLETE)
        manifest_bytes = _read_output_file(dir_fd, OUTPUT_MANIFEST,
                                           MAX_MANIFEST_DOCUMENT_BYTES, identities)
        manifest = _canonical_json(manifest_bytes, OUTPUT_MANIFEST)
        _need(isinstance(manifest, dict), "manifest shape")
        _need(isinstance(complete, dict) and set(complete) == {
            "schema", "task", "generator_version", "status", "inventory_manifest",
            "inventory_manifest_bytes", "inventory_manifest_sha256", "record_files"},
            "completion keys")
        _need(complete["schema"] == COMPLETE_SCHEMA and complete["task"] == TASK and
              complete["generator_version"] == VERSION and complete["status"] == "complete"
              and complete["inventory_manifest"] == OUTPUT_MANIFEST and
              _is_int(complete["inventory_manifest_bytes"]) and
              complete["inventory_manifest_bytes"] == len(manifest_bytes) and
              complete["inventory_manifest_sha256"] == sha256(manifest_bytes),
              "completion/manifest binding")
        _need(isinstance(complete["record_files"], dict) and
              set(complete["record_files"]) == set(record_names) and
              all(_is_hex64(v) for v in complete["record_files"].values()),
              "completion record-file set")
        # Validate all observed per-archive fields, recomputing row summaries while
        # streaming every line. Hash consistency alone cannot establish this contract.
        archives = manifest.get("archives")
        _need(isinstance(archives, list) and len(archives) == len(names), "archive list")
        name_sets = []
        for position, (pin, entry) in enumerate(zip(profile["archives"], archives)):
            _need(isinstance(entry, dict) and set(entry) == {
                "order", "file", "extracted_path", "bytes", "sha256", "input_checks",
                "header", "table", "profile_agreement", "counts", "records_file"},
                "archive keys")
            for key, expected in (("order", position), ("file", pin["file"]),
                                  ("extracted_path", pin["extracted_path"]),
                                  ("bytes", pin["bytes"]), ("sha256", pin["sha256"])):
                _need(_same(entry[key], expected), "archive identity")
            _need(_same(entry["input_checks"], dict.fromkeys(
                ("regular_single_link", "no_follow_read", "full_sha256", "identity_stable",
                 "manifest_entry_matches"), True)), "input checks")
            agreement = _header_contract(entry["header"], pin, core)
            _need(_same(entry["profile_agreement"], agreement), "profile agreement")
            counts, raw_names, consumed = _verify_records(
                dir_fd, entry["records_file"], pin["file"], pin["sha256"],
                core.WORK_LIMITS["max_record_file_bytes"], pin=pin, core=core,
                identities=identities)
            _need(_same(entry["counts"], counts), "record summaries")
            _table_contract(entry["table"], pin, consumed)
            name_sets.append(raw_names)
        em = manifest.get("extracted_manifest")
        _need(isinstance(em, dict), "extracted manifest shape")
        children = em.get("archive_directory_entries")
        _need(_is_int(children) and len(names) <= children <=
              profile["extracted_manifest"]["files"] +
              profile["extracted_manifest"]["directories"], "root metadata count")
        facts = {"archive_dir": posixpath.dirname(profile["archives"][0]["extracted_path"]),
                 "children": dict.fromkeys(range(children)),
                 "entries": profile["extracted_manifest"]["files"] +
                            profile["extracted_manifest"]["directories"],
                 "files": profile["extracted_manifest"]["files"],
                 "directories": profile["extracted_manifest"]["directories"],
                 "loose_data_ini_entries": 0}
        usage = {"archive_bytes_hashed": sum(a["bytes"] for a in profile["archives"]),
                 "table_bytes_captured": sum(a["table"]["stored_bytes"] for a in archives),
                 "records": sum(a["records_file"]["lines"] for a in archives),
                 "record_file_bytes": sum(a["records_file"]["bytes"] for a in archives),
                 "extracted_manifest_bytes_read": profile["extracted_manifest"]["bytes"],
                 "archive_root_entries_examined": children}
        _need(usage["records"] <= core.WORK_LIMITS["max_records_total"], "record work limit")
        expected = _build_manifest(contract, profile, core, generator, facts, archives,
                                   _totals(archives, name_sets), usage)
        _need(_same(manifest, expected), "complete manifest/source/profile/usage contract")
        _need(_same(complete, _complete_document(manifest, manifest_bytes)),
              "complete marker binding")
        # Fresh exact source reads, then final observed file/directory bindings.
        for path, pin, what, original in (
                (contract.profile_path, contract.profile_pin, "profile", profile_identity),
                (contract.core_path, contract.core_pin, "core", core_identity),
                (contract.generator_path, generator, "generator source", generator_identity)):
            _, current = _read_pinned_file(path, pin, what)
            _need(current == original, "source identity changed during verification")
        for name, original in identities.items():
            current = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
            _private_file(current, name)
            _need(_identity(current) == original, "checked file was replaced or changed")
        _need(sorted(os.listdir(dir_fd)) == listing, "directory entries changed")
        current = os.fstat(dir_fd)
        _need((current.st_dev, current.st_ino) == identity and
              current.st_uid == os.geteuid() and stat.S_IMODE(current.st_mode) == 0o700,
              "directory binding/mode changed")
        _check_target(output, identity)
    finally:
        os.close(dir_fd)
    _check_target(output, identity)
    return manifest


# --- CLI ----------------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("extracted_manifest", help="complete extracted-tree manifest "
                        "(read-only)")
    parser.add_argument("archive_root", help="extracted archive directory (read-only)")
    parser.add_argument("output", help="new private output directory")
    args = parser.parse_args(argv)
    paths = [(args.output, "<output>"), (args.archive_root, "<archive_root>"),
             (args.extracted_manifest, "<extracted_manifest>"), (str(CHECKOUT), "<checkout>")]
    try:
        _target, manifest, hashes = run(args.extracted_manifest, args.archive_root,
                                         args.output)
    except Exception as exc:  # every failure is a bounded, path-free nonzero result
        category = getattr(exc, "category", None)
        if not isinstance(exc, (InventoryError, OSError)) and category is None:
            category, message = "unexpected", type(exc).__name__
        else:
            category = category or "os_error"
            message = exc.strerror if isinstance(exc, OSError) and exc.strerror else exc
        print(f"error [{category}]: {_sanitize(message, paths)}", file=sys.stderr)
        return 2
    print(json.dumps({"status": manifest["status"], "totals": manifest["totals"],
                      "record_files": {a["file"]: a["records_file"]
                                       for a in manifest["archives"]}, **hashes},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
