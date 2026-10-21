#!/usr/bin/env python3
"""Inventory every raw physical file-table record of the 28 selected patch GPFs.

T07.007.007. Inputs are the frozen normalized acquisition ledger
(ro-patch-acquisition-ledger/1), the input root that anchors its relative paths
and a fresh private output directory. The fixed public profile
docs/project/fixtures/T07.007.007-profile.json is found relative to this
checkout and must match the byte/hash descriptor below before its contents may
authorize anything. The manifest must equal the profile's 59-row ledger.

Only the 28 rows with disposition selected_for_inventory are opened. The two
already inventoried GPFs and the 29 unresolved RGZ objects stay visible in the
output manifest through their ledger rows; their files are never opened, read
or examined. No directory is enumerated to select archives.

This is an additive facade over the unchanged core archive_catalog.py, whose
exact bytes are verified and executed into a private module. It reuses
read_archive (same-descriptor full SHA-256 plus header/table capture),
catalog_table (records, render_record lines, summary), render, trusted_target,
_verify_published and parse_header/Summary/metadata_filter/header_encryption
for the consumer. It has no GRF parser of its own, never calls the core's
INI-oriented run/build_manifest/read_inputs and never fabricates a DATA.INI.
Each downloaded .gpf.body is passed to read_archive by its storage basename
through the verified parent descriptor; records carry the original .gpf name.
Payload bytes are only opaque full-hash input; nothing is extracted, decrypted
or decompressed. Standard library only.

Output: 28 <index>.records.jsonl files, inventory-manifest.json and
inventory-complete.json (written last). Status complete means only that the
bounded raw physical inventory was produced safely: it says nothing about RGZ
grammar, publisher application or lookup priority, payload availability, maps,
render, playability or full-game coverage.
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

VERSION = "1.0.0"
TASK = "T07.007.007"
MANIFEST_SCHEMA = "ro-patch-raw-inventory/1"
COMPLETE_SCHEMA = "ro-patch-raw-inventory-complete/1"
FAILED_SCHEMA = "ro-patch-raw-inventory-failed/1"
PROFILE_SCHEMA = "ro-patch-raw-inventory-profile/1"
LEDGER_SCHEMA = "ro-patch-acquisition-ledger/1"
OUTPUT_MANIFEST = "inventory-manifest.json"
OUTPUT_COMPLETE = "inventory-complete.json"
OUTPUT_FAILED = "inventory-failed.json"
RECORDS_SUFFIX = ".records.jsonl"

CHECKOUT = Path(os.path.realpath(__file__)).parents[2]
GENERATOR_REL = "tools/renewal/archive_inventory_patches.py"
CORE_REL = "tools/renewal/archive_catalog.py"
HELPER_REL = "tools/renewal/archive_inventory_october.py"
PROFILE_REL = "docs/project/fixtures/T07.007.007-profile.json"

DISPOSITION_SELECTED = "selected_for_inventory"
DISPOSITION_ALREADY = "already_inventoried_not_read"
DISPOSITION_RGZ = "unresolved_rgz_not_read"
LEDGER_OBJECTS, SELECTED_OBJECTS, ALREADY_OBJECTS, RGZ_OBJECTS = 59, 28, 2, 29

MAX_OUTPUT_BYTES_TOTAL = 2 << 30
MAX_JSON_LINE_BYTES = 4 << 20
MAX_RECORDS_TOTAL = 1_500_000
MAX_RECORD_FILE_BYTES = 1 << 30
MAX_SMALL_INPUT_BYTES = 4 << 20
MAX_MANIFEST_DOCUMENT_BYTES = 64 << 20
MAX_COMPLETE_DOCUMENT_BYTES = 64 << 10
MAX_DIAGNOSTIC_CHARS = 1000
WRITE_BUFFER_BYTES = 1 << 20
READ_CHUNK_BYTES = 8 << 20
MAX_INTERRUPT_RETRIES = 16
WORK_LIMITS = {
    "max_entries_per_archive": 500_000,
    "max_table_bytes_per_archive": 512 << 20,
    "max_records_total": MAX_RECORDS_TOTAL,
    "max_record_file_bytes": MAX_RECORD_FILE_BYTES,
    "max_output_bytes_total": MAX_OUTPUT_BYTES_TOTAL,
    "max_json_line_bytes": MAX_JSON_LINE_BYTES,
    "read_chunk_bytes": READ_CHUNK_BYTES,
    "outer_timeout_seconds": 1200,
    "outer_sampled_combined_rss_bytes": 2 << 30,
    "outer_combined_diagnostics_bytes": 16 << 20,
}

PROFILE_KEYS = {
    "already_inventoried_indices", "basis_revision", "core", "draft", "enumeration_basis",
    "enumeration_order", "exclusions", "freeze_status", "helper_policy", "input_manifest",
    "ledger", "lookup_priority", "optional_executed_helper", "output", "priority_status",
    "publisher_digest_status", "schema", "selected_expected", "source_evidence",
    "source_evidence_access", "source_rules", "task", "totals", "unresolved_rgz_indices",
    "work_limits"}
LEDGER_BASE_KEYS = {"acquisition_status", "bytes", "disposition", "family", "file", "index",
                    "lf", "path", "sha256", "source_ordinal", "url"}
LEDGER_HEADER_KEYS = {"count_word", "header46_sha256", "offset_word", "record_count",
                      "subtract_word", "table_bytes", "table_start", "version"}
GZIP_KEYS = {"compression_method", "flags", "hex", "inner_grammar"}
EXPECTED_HEADER_KEYS = {"declared_version", "effective_version", "header46_sha256", "layout",
                        "raw_count_word", "record_count", "signature", "subtract_word",
                        "table_bytes", "table_end", "table_form", "table_start"}
EXPECTED_TABLE_KEYS = {"consumed_bytes", "stored_sha256", "trailing_bytes", "trailing_sha256"}
COUNT_KEYS = {"diagnostic_body_ranges_outside_archive", "duplicate_raw_names",
              "effective_flags", "effective_kind", "empty_names", "kind0_promotions",
              "length_bias_underflows", "metadata_eligible", "metadata_filter",
              "names_with_high_bytes", "names_without_nul", "original_kind", "raw_records",
              "unique_raw_names"}
TOTAL_KEYS = {"already_inventoried_gpf_objects", "gpf_objects", "ledger_bytes",
              "ledger_objects", "selected_archive_bytes",
              "selected_cross_archive_shared_raw_names", "selected_distinct_raw_names",
              "selected_gpf_objects", "selected_raw_records", "selected_table_bytes",
              "selected_unused_tail_bytes", "unresolved_rgz_objects"}
EVIDENCE_KEYS = {"acquisition_summary", "bounded_header_observations",
                 "root_full_hash_header_admission"}
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()

SEMANTICS = {
    "enumeration_meaning": "receipt-row enumeration of the selected ledger indices; "
                           "physical records in table order only; not publisher "
                           "application order and not a client lookup priority",
    "lookup_priority": None,
    "priority_status": "not_established",
    "winning_archive": None,
    "duplicates": "kept: every physical record within and across archives in table order, "
                  "including metadata-filtered records",
    "names": "raw table bytes as hex after the core legacy block transform; no filename "
             "codec, Unicode, case or path normalisation",
    "diagnostic_ranges": "arithmetic metadata from table fields only; payload presence and "
                         "readability are not established",
    "counts": "per-archive summaries and cross-archive totals derive from emitted rows; "
              "they do not establish payload presence or a lookup winner",
    "not_read": "already inventoried GPF and unresolved RGZ ledger rows are kept as "
                "metadata exclusions; their files were not opened",
}

INPUT_RULES = [
    "The public profile is resolved relative to the checkout, read without following "
    "links and must match the fixed descriptor (length and full SHA-256) before its "
    "typed contract is validated.",
    "Core bytes are read no-follow, checked against the fixed descriptor and the profile "
    "and executed from those exact bytes into a fresh private module; its run, "
    "build_manifest and read_inputs are never used.",
    "The normalized input manifest must match the profile pin, be unambiguous finite "
    "JSON with exactly the required fields and equal the profile ledger and source "
    "evidence with types (a bool is never an integer) before any archive is opened or "
    "output is created.",
    "Input root, manifest and every ancestor are opened component by component without "
    "following links; ledger paths are safe relative paths below the input root.",
    "Only the 28 selected rows are examined and opened: each storage file must be a "
    "regular single-link file of its ledger size; it is read by its storage basename "
    "through the retained parent descriptor with the core read_archive.",
    "Every frozen header, table plan, table, tail and count fact is reconciled with the "
    "parsed data; a nonzero tail is a profile mismatch for this frozen corpus.",
    "Before completion every selected archive is fully rehashed and its path, parent "
    "chain and identity compared with the first read; profile, core, generator and "
    "manifest bytes and identities are rechecked.",
]

PUBLICATION_RULES = [
    "Fresh exclusive 0700 output below a parent owned by you and not group/world "
    "writable, outside the input root; no asset-derived output paths.",
    "Every file is created exclusively no-follow 0600, written with checked progress "
    "(positive short writes loop; zero progress or errors fail), fsynced, closed with "
    "error checking and read back before the next step, under per-file, per-line and "
    "aggregate output bounds accounted before writing.",
    "inventory-complete.json is written last and binds the manifest bytes/hash and "
    "every record-file hash; directory membership, modes, link counts and identities "
    "are audited before and after it is published.",
    "On failure only a verified run-owned completion record is removed, foreign "
    "replacements are preserved and a path-free inventory-failed.json is written when "
    "the reserved directory is still verifiable; it overrides any completion record.",
]

EXCLUSIONS = [
    "host paths, device/inode numbers or machine identifiers",
    "original private receipts, admission, header observations or root oracle contents",
    "installed/live worlds, saves, databases, browsers, network or preferences",
]

CORE_REUSED = ["read_archive", "catalog_table", "render_record", "render", "trusted_target",
               "_verify_published", "parse_header", "Summary", "metadata_filter",
               "header_encryption"]
CORE_NOT_USED = ["run", "build_manifest", "read_inputs", "verify_input_manifest",
                 "input_manifest_agreement", "main"]

FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


class InventoryError(ValueError):
    """Input or output that cannot be inventoried or published without guessing."""
    category = "error"


class InputError(InventoryError):
    category = "input_pin"


class ProfileMismatch(InventoryError):
    """Archive facts that the core accepts but that differ from the frozen profile."""
    category = "profile_mismatch"


class ResourceLimit(InventoryError):
    category = "resource_limit"


class OutputError(InventoryError):
    category = "output"


class VerificationError(InventoryError):
    category = "verification"


class _Contract:
    """Fixed identities of one inventory run. Production uses PRODUCTION only; tests build
    their own instance (synthetic profile, optional private fault hooks) and call the
    private entry points. The CLI never constructs one."""

    def __init__(self, checkout, profile_bytes, profile_sha256, core_bytes, core_sha256,
                 core_os=None, consumer_hook=None, phase_hook=None):
        self.checkout = Path(checkout)
        self.profile_path = self.checkout / PROFILE_REL
        self.profile_pin = {"bytes": profile_bytes, "sha256": profile_sha256}
        self.core_path = self.checkout / CORE_REL
        self.core_pin = {"bytes": core_bytes, "sha256": core_sha256}
        self.generator_path = self.checkout / GENERATOR_REL
        self.core_os = core_os
        self.consumer_hook = consumer_hook
        self.phase_hook = phase_hook

    def phase(self, name, **info):
        if self.phase_hook is not None:
            self.phase_hook(name, **info)


PRODUCTION = _Contract(
    CHECKOUT, 101983, "558363dd2a1f55c85d67c2b23cdafdbbcd8b4ea7022e979218d1b19fff908681",
    54783, "f785ced6006741de0bc8dbab4354d6ee5ab15fb750ddd95111fc16a2cdf15cda")


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


def _json(text, what, error=InputError):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    def constant(_value):
        raise ValueError("nonfinite constant")

    def floating(literal):
        value = float(literal)
        if not math.isfinite(value):
            raise ValueError("nonfinite number")
        return value

    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=constant,
                          parse_float=floating)
    except (ValueError, RecursionError):
        raise error(f"{what} is not unambiguous finite JSON") from None


def _safe_relative(path):
    if not isinstance(path, str) or not path or path.startswith("/") or "\\" in path or \
            "\0" in path:
        return False
    return all(part not in ("", ".", "..") for part in path.split("/"))


# --- Checked low-level I/O ------------------------------------------------------------------
# Indirections exist so tests can inject read/write/fsync/close faults without patching os.

def _read_chunk(fd, size):
    return os.read(fd, size)


def _write_chunk(fd, view):
    return os.write(fd, view)


def _fsync(fd):
    os.fsync(fd)


def _close_fd(fd):
    os.close(fd)


def _interruptible(call, what, error):
    """Run call(); retry a finite number of EINTRs, then fail."""
    for _ in range(MAX_INTERRUPT_RETRIES):
        try:
            return call()
        except InterruptedError:
            continue
    raise error(f"{what} interrupted persistently")


class _Fds:
    """Registry of descriptors this run owns, so success can prove none leaked."""

    def __init__(self):
        self.open_fds = set()

    def open(self, path, flags, dir_fd=None, what="input", error=InputError):
        try:
            fd = os.open(path, flags, dir_fd=dir_fd)
        except OSError as exc:
            raise error(f"{what} cannot be opened without following links: "
                        f"{exc.strerror}") from None
        self.open_fds.add(fd)
        return fd

    def close(self, fd):
        self.open_fds.discard(fd)
        _close_fd(fd)

    def close_quietly(self):
        for fd in sorted(self.open_fds):
            try:
                os.close(fd)
            except OSError:
                pass
        self.open_fds.clear()


def _read_fd(fd, size, what, error):
    """Read exactly size bytes from offset 0 of an open regular file, checking for growth."""
    chunks, total = [], 0
    while total <= size:
        chunk = _interruptible(lambda: _read_chunk(fd, min(READ_CHUNK_BYTES, size + 1 - total)),
                               f"read of {what}", error)
        if not isinstance(chunk, (bytes, bytearray)):
            raise error(f"read of {what} returned no bytes")
        if not chunk:
            break
        chunks.append(bytes(chunk))
        total += len(chunk)
    if total != size:
        raise error(f"{what} ended early or grew while read")
    return b"".join(chunks)


def _walk(fds, path, what, error=InputError):
    """Open every directory of an absolute path without following links.

    Return (fd of the final directory, [(dev, ino) of each component])."""
    text = os.fspath(path)
    if not isinstance(text, str) or not text.startswith("/") or "\0" in text:
        raise error(f"{what} must be an absolute path")
    parts = [p for p in text.split("/") if p]
    if any(p in (".", "..") for p in parts):
        raise error(f"{what} must not contain dot or dot-dot components")
    current = fds.open("/", DIR_FLAGS, what=what, error=error)
    chain = [_dir_identity(current)]
    try:
        for part in parts:
            nxt = fds.open(part, DIR_FLAGS, dir_fd=current, what=what, error=error)
            fds.close(current)
            current = nxt
            chain.append(_dir_identity(current))
    except BaseException:
        fds.close(current)
        raise
    return current, chain


def _walk_relative(fds, base_fd, parts, what, error=InputError):
    current = os.dup(base_fd)
    fds.open_fds.add(current)
    chain = []
    try:
        for part in parts:
            nxt = fds.open(part, DIR_FLAGS, dir_fd=current, what=what, error=error)
            fds.close(current)
            current = nxt
            chain.append(_dir_identity(current))
    except BaseException:
        fds.close(current)
        raise
    return current, chain


def _dir_identity(fd):
    info = os.fstat(fd)
    if not stat.S_ISDIR(info.st_mode):
        raise InputError("path component is not a directory")
    return (info.st_dev, info.st_ino)


def _read_file_at(fds, dir_fd, name, what, limit, pin=None, error=InputError):
    """Read a regular single-link file below dir_fd without following links.

    Return (bytes, identity). The name must still be the same file afterwards."""
    fd = fds.open(name, FILE_FLAGS, dir_fd=dir_fd, what=what, error=error)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise error(f"{what} is not a regular single-link file")
        if before.st_size > limit or (pin is not None and before.st_size != pin["bytes"]):
            raise error(f"{what} size differs from its pin or limit")
        data = _read_fd(fd, before.st_size, what, error)
        after = os.fstat(fd)
    finally:
        fds.close(fd)
    try:
        current = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
    except OSError:
        current = None
    if _identity(before) != _identity(after) or current is None or \
            _identity(current) != _identity(before):
        raise error(f"{what} changed or was replaced while read")
    if pin is not None and sha256(data) != pin["sha256"]:
        raise error(f"{what} does not match its pin")
    return data, _identity(before)


def _read_path(fds, path, what, limit, pin=None, error=InputError):
    """Read an absolute file path through a no-follow ancestor walk.

    Return (bytes, identity, parent chain)."""
    text = os.fspath(path)
    parent, name = posixpath.split(text)
    if not name or name in (".", ".."):
        raise error(f"{what} has no file name")
    dir_fd, chain = _walk(fds, parent or "/", what, error)
    try:
        data, identity = _read_file_at(fds, dir_fd, name, what, limit, pin, error)
    finally:
        fds.close(dir_fd)
    return data, identity, chain


# --- Fixed sources ---------------------------------------------------------------------------

def _read_profile(fds, contract):
    data, identity, chain = _read_path(fds, str(contract.profile_path), "profile",
                                       contract.profile_pin["bytes"], contract.profile_pin)
    try:
        text = data.decode("ascii")
    except UnicodeError:
        raise InputError("profile is not ASCII JSON") from None
    profile = _json(text, "profile")
    validate_profile(profile, contract)
    return profile, (identity, chain)


def _load_core(fds, contract):
    """Execute the pinned core bytes into a fresh private module. Return (module, id)."""
    data, identity, chain = _read_path(fds, str(contract.core_path), "core",
                                       contract.core_pin["bytes"], contract.core_pin)
    module = types.ModuleType("archive_catalog_pinned_t07_007_007")
    module.__file__ = str(contract.core_path)
    exec(compile(data, str(contract.core_path), "exec"), module.__dict__)
    if contract.core_os is not None:
        # Test-only fault boundary on a private module instance; PRODUCTION never sets it.
        module.os = contract.core_os
    return module, (identity, chain)


def _read_generator(fds, contract):
    """The generator describes itself: its identity is its own current bytes."""
    data, identity, chain = _read_path(fds, str(contract.generator_path),
                                       "generator source", MAX_SMALL_INPUT_BYTES)
    return {"bytes": len(data), "sha256": sha256(data)}, (identity, chain)


def _check_core_module(core):
    expected = {"max_entries_per_archive": WORK_LIMITS["max_entries_per_archive"],
                "max_table_bytes": WORK_LIMITS["max_table_bytes_per_archive"],
                "max_records_total": WORK_LIMITS["max_records_total"],
                "max_record_file_bytes": WORK_LIMITS["max_record_file_bytes"],
                "read_chunk_bytes": WORK_LIMITS["read_chunk_bytes"]}
    limits = getattr(core, "WORK_LIMITS", None)
    if not isinstance(limits, dict) or any(limits.get(k) != v for k, v in expected.items()) \
            or core.MAX_ENTRIES != expected["max_entries_per_archive"] or \
            core.MAX_FILE_TABLE_BYTES != expected["max_table_bytes"] or \
            core.HEADER_SIZE != 46 or tuple(core.IMPLEMENTED_LEGACY_VERSIONS) != (0x102,):
        raise InputError("core limits differ from the frozen profile bounds")


def validate_profile(profile, contract):
    """Typed contract of the frozen profile; refuse anything else."""
    def need(ok, why):
        if not ok:
            raise InputError(f"profile contract: {why}")

    need(isinstance(profile, dict) and set(profile) == PROFILE_KEYS, "top-level keys")
    need(profile["schema"] == PROFILE_SCHEMA and profile["task"] == TASK, "schema/task")
    need(profile["draft"] is False and profile["freeze_status"] == "frozen_common_contract",
         "freeze status")
    need(profile["lookup_priority"] is None and
         profile["priority_status"] == "not_established", "priority must be unestablished")
    for key in ("enumeration_basis", "helper_policy", "source_evidence_access",
                "publisher_digest_status", "basis_revision"):
        need(isinstance(profile[key], str) and profile[key], key)
    need(isinstance(profile["exclusions"], list) and profile["exclusions"] and
         all(isinstance(x, str) for x in profile["exclusions"]), "exclusions")
    need(_same(profile["core"], {"path": CORE_REL, **contract.core_pin}), "core pin")
    helper = profile["optional_executed_helper"]
    need(isinstance(helper, dict) and set(helper) == {"path", "bytes", "sha256"} and
         helper["path"] == HELPER_REL and _is_int(helper["bytes"]) and
         _is_hex64(helper["sha256"]), "helper pin")
    need(_same(profile["work_limits"], WORK_LIMITS), "work limits")
    im = profile["input_manifest"]
    need(isinstance(im, dict) and set(im) == {"bytes", "ledger_requirement", "path",
                                              "required_fields", "schema", "sha256"} and
         _is_int(im["bytes"]) and 0 < im["bytes"] <= MAX_SMALL_INPUT_BYTES and
         _is_hex64(im["sha256"]) and _safe_relative(im["path"]) and
         im["schema"] == LEDGER_SCHEMA and isinstance(im["ledger_requirement"], str) and
         _same(im["required_fields"], ["schema", "task", "enumeration_basis",
                                       "lookup_priority", "priority_status",
                                       "source_evidence", "ledger"]), "input manifest pin")
    evidence = profile["source_evidence"]
    need(isinstance(evidence, dict) and set(evidence) == EVIDENCE_KEYS and all(
        isinstance(v, dict) and set(v) == {"bytes", "path", "sha256"} and
        _is_int(v["bytes"]) and _is_hex64(v["sha256"]) and _safe_relative(v["path"])
        for v in evidence.values()), "source evidence pins")
    rules = profile["source_rules"]
    need(isinstance(rules, dict) and set(rules) == {"core_line_rules", "files", "meaning",
                                                    "repository", "revision"}, "source rules")

    ledger = profile["ledger"]
    need(isinstance(ledger, list) and len(ledger) == LEDGER_OBJECTS, "ledger size")
    seen_index, seen_path, seen_ordinal = set(), set(), set()
    by_disposition = {DISPOSITION_SELECTED: [], DISPOSITION_ALREADY: [], DISPOSITION_RGZ: []}
    for row in ledger:
        need(isinstance(row, dict), "ledger row type")
        gpf = row.get("family") == "grf_signature"
        need(set(row) == LEDGER_BASE_KEYS | ({"header"} if gpf else {"observed_gzip_prefix"}),
             "ledger row keys")
        need(all(_is_int(row[k]) for k in ("bytes", "index", "lf", "source_ordinal")),
             "ledger integer fields")
        need(_is_hex64(row["sha256"]) and _safe_relative(row["path"]) and
             isinstance(row["file"], str) and row["file"] and
             posixpath.basename(row["file"]) == row["file"] and
             _safe_relative(row["file"]) and isinstance(row["url"], str) and
             row["url"].endswith("/" + row["file"]) and
             row["acquisition_status"] in ("verified_new", "verified_reused"),
             "ledger row values")
        need(row["index"] not in seen_index and row["path"] not in seen_path and
             row["source_ordinal"] not in seen_ordinal, "ledger duplicates")
        seen_index.add(row["index"])
        seen_path.add(row["path"])
        seen_ordinal.add(row["source_ordinal"])
        need(row["disposition"] in by_disposition, "ledger disposition")
        by_disposition[row["disposition"]].append(row)
        if gpf:
            need(row["file"].endswith(".gpf") and row["disposition"] in (
                DISPOSITION_SELECTED, DISPOSITION_ALREADY), "GPF disposition")
            head = row["header"]
            need(isinstance(head, dict) and set(head) == LEDGER_HEADER_KEYS and
                 all(_is_int(head[k]) for k in LEDGER_HEADER_KEYS - {"header46_sha256"}) and
                 _is_hex64(head["header46_sha256"]), "GPF header row")
        else:
            need(row["family"] == "gzip_prefix" and row["file"].endswith(".rgz") and
                 row["disposition"] == DISPOSITION_RGZ, "RGZ disposition")
            prefix = row["observed_gzip_prefix"]
            need(isinstance(prefix, dict) and set(prefix) == GZIP_KEYS and
                 prefix["hex"] == "1f8b08" and prefix["inner_grammar"] == "unresolved" and
                 _is_int(prefix["compression_method"]) and _is_int(prefix["flags"]),
                 "RGZ prefix row")
    selected = by_disposition[DISPOSITION_SELECTED]
    need(len(selected) == SELECTED_OBJECTS and
         len(by_disposition[DISPOSITION_ALREADY]) == ALREADY_OBJECTS and
         len(by_disposition[DISPOSITION_RGZ]) == RGZ_OBJECTS, "ledger disposition counts")
    need(_same(profile["enumeration_order"], [r["index"] for r in selected]),
         "enumeration order is the selected ledger order")
    need(_same(profile["already_inventoried_indices"],
               [r["index"] for r in by_disposition[DISPOSITION_ALREADY]]), "already indices")
    need(_same(profile["unresolved_rgz_indices"],
               [r["index"] for r in by_disposition[DISPOSITION_RGZ]]), "RGZ indices")
    need(len({posixpath.dirname(r["path"]) for r in selected}) >= 1, "selected parents")
    for row in selected:
        base = posixpath.basename(row["path"])
        need(row["acquisition_status"] == "verified_new" and base != row["file"] and
             base.endswith("_" + row["file"] + ".body"), "selected storage basename")

    output = profile["output"]
    need(isinstance(output, dict) and set(output) == {
        "completion", "failure", "manifest", "record_schema", "records", "schema",
        "source_join", "success_file_count", "tail_policy"}, "output keys")
    need(output["completion"] == OUTPUT_COMPLETE and output["failure"] == OUTPUT_FAILED and
         output["manifest"] == OUTPUT_MANIFEST and output["schema"] == MANIFEST_SCHEMA and
         output["success_file_count"] == SELECTED_OBJECTS + 2 and
         _same(output["records"], [f"{r['index']}{RECORDS_SUFFIX}" for r in selected]) and
         all(isinstance(output[k], str) for k in ("record_schema", "source_join",
                                                 "tail_policy")), "output contract")

    expected = profile["selected_expected"]
    need(isinstance(expected, list) and len(expected) == SELECTED_OBJECTS, "selected expected")
    for row, entry in zip(selected, expected):
        need(isinstance(entry, dict) and set(entry) == {"counts", "header", "index", "table"}
             and entry["index"] == row["index"], "selected expected order")
        head, lh = entry["header"], row["header"]
        need(isinstance(head, dict) and set(head) == EXPECTED_HEADER_KEYS, "expected header")
        need(head["declared_version"] == 0x102 and head["effective_version"] == 0x102 and
             head["layout"] == "legacy" and lh["version"] == 0x102 and
             head["signature"] in ("Master of Magic", "Event Horizon") and
             head["table_form"] == "clear legacy table to EOF", "selected legacy 0x102")
        need(all(_is_int(head[k]) for k in ("raw_count_word", "record_count",
                                             "subtract_word", "table_bytes", "table_end",
                                             "table_start")), "expected header integers")
        need(head["header46_sha256"] == lh["header46_sha256"] and
             head["raw_count_word"] == lh["count_word"] and
             head["subtract_word"] == lh["subtract_word"] and
             head["record_count"] == lh["record_count"] and
             head["table_start"] == lh["table_start"] and
             head["table_bytes"] == lh["table_bytes"], "expected header equals ledger")
        need(lh["table_start"] == lh["offset_word"] + 46 and
             head["table_end"] == row["bytes"] and
             lh["table_start"] + lh["table_bytes"] == row["bytes"] and
             lh["record_count"] == max(lh["count_word"] - lh["subtract_word"] - 7, 0) and
             0 < lh["table_bytes"] <= WORK_LIMITS["max_table_bytes_per_archive"] and
             lh["record_count"] <= WORK_LIMITS["max_entries_per_archive"],
             "expected header arithmetic")
        table = entry["table"]
        need(isinstance(table, dict) and set(table) == EXPECTED_TABLE_KEYS and
             table["consumed_bytes"] == lh["table_bytes"] and table["trailing_bytes"] == 0 and
             table["trailing_sha256"] == EMPTY_SHA256 and _is_hex64(table["stored_sha256"]),
             "expected table (zero tail)")
        counts = entry["counts"]
        need(isinstance(counts, dict) and set(counts) == COUNT_KEYS and
             counts["raw_records"] == lh["record_count"], "expected counts")

    totals = profile["totals"]
    need(isinstance(totals, dict) and set(totals) == TOTAL_KEYS and
         all(_is_int(v) for v in totals.values()), "totals keys")
    derived = {
        "ledger_objects": len(ledger), "gpf_objects": SELECTED_OBJECTS + ALREADY_OBJECTS,
        "selected_gpf_objects": len(selected), "already_inventoried_gpf_objects":
            ALREADY_OBJECTS, "unresolved_rgz_objects": RGZ_OBJECTS,
        "ledger_bytes": sum(r["bytes"] for r in ledger),
        "selected_archive_bytes": sum(r["bytes"] for r in selected),
        "selected_raw_records": sum(r["header"]["record_count"] for r in selected),
        "selected_table_bytes": sum(r["header"]["table_bytes"] for r in selected),
        "selected_unused_tail_bytes": 0}
    need(all(totals[k] == v for k, v in derived.items()), "totals derive from the ledger")
    need(totals["selected_raw_records"] <= WORK_LIMITS["max_records_total"],
         "cumulative record bound")


def validate_input_manifest(document, profile):
    """The normalized ledger must equal the profile exactly, with types."""
    im = profile["input_manifest"]
    if not isinstance(document, dict) or set(document) != set(im["required_fields"]):
        raise InputError("input manifest must hold exactly the required fields")
    expected = {"schema": im["schema"], "task": TASK,
                "enumeration_basis": profile["enumeration_basis"],
                "lookup_priority": None, "priority_status": "not_established",
                "source_evidence": profile["source_evidence"], "ledger": profile["ledger"]}
    differs = sorted(k for k, v in expected.items() if not _same(document[k], v))
    if differs:
        raise InputError(f"input manifest differs from the frozen profile: {differs}")


# --- Admission of the selected archives -----------------------------------------------------

def _selected_rows(profile):
    return [r for r in profile["ledger"] if r["disposition"] == DISPOSITION_SELECTED]


def _archive_lstat(parent_fd, name, size, what):
    try:
        info = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError as exc:
        raise InputError(f"{what} cannot be examined: {exc.strerror}") from None
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != size:
        raise InputError(f"{what} is not a regular single-link file of its ledger size")
    return info


class _Inputs:
    """Retained input descriptors and identities of one run."""

    def __init__(self, fds, root_path, profile):
        self.fds = fds
        self.root_path = root_path
        self.root_fd, self.root_chain = _walk(fds, root_path, "input root")
        self.parents = {}  # relative dir -> (fd, chain)
        self.files = {}    # index -> identity
        self.rows = _selected_rows(profile)
        for row in self.rows:
            rel = posixpath.dirname(row["path"])
            if rel not in self.parents:
                parts = rel.split("/") if rel else []
                self.parents[rel] = _walk_relative(fds, self.root_fd, parts,
                                                   f"archive {row['index']} parent")
        for row in self.rows:
            self.files[row["index"]] = _identity(self._lstat(row))

    def parent_fd(self, row):
        return self.parents[posixpath.dirname(row["path"])][0]

    def _lstat(self, row):
        return _archive_lstat(self.parent_fd(row), posixpath.basename(row["path"]),
                              row["bytes"], f"archive {row['index']}")

    def check_unchanged(self, row):
        if _identity(self._lstat(row)) != self.files[row["index"]]:
            raise InputError(f"archive {row['index']} identity changed after admission")

    def recheck(self, rehash):
        """Re-walk the root and parents by path, compare identities, rehash if asked."""
        fd, chain = _walk(self.fds, self.root_path, "input root")
        try:
            if chain != self.root_chain or _dir_identity(self.root_fd) != chain[-1]:
                raise InputError("input root or an ancestor was replaced during the run")
            for rel, (parent_fd, parent_chain) in self.parents.items():
                pfd, now = _walk_relative(self.fds, fd, rel.split("/") if rel else [],
                                          "archive parent")
                try:
                    if now != parent_chain or _dir_identity(parent_fd) != \
                            (parent_chain[-1] if parent_chain else chain[-1]):
                        raise InputError("archive parent directory was replaced")
                finally:
                    self.fds.close(pfd)
        finally:
            self.fds.close(fd)
        for row in self.rows:
            self.check_unchanged(row)
            if rehash:
                self._rehash(row)

    def _rehash(self, row):
        name = posixpath.basename(row["path"])
        what = f"archive {row['index']}"
        fd = self.fds.open(name, FILE_FLAGS, dir_fd=self.parent_fd(row), what=what)
        try:
            before = os.fstat(fd)
            if _identity(before) != self.files[row["index"]]:
                raise InputError(f"{what} descriptor identity differs from the first read")
            digest, total = hashlib.sha256(), 0
            while True:
                chunk = _interruptible(lambda: _read_chunk(fd, READ_CHUNK_BYTES),
                                       f"rehash of {what}", InputError)
                if not chunk:
                    break
                digest.update(chunk)
                total += len(chunk)
                if total > row["bytes"]:
                    break
            after = os.fstat(fd)
        finally:
            self.fds.close(fd)
        if total != row["bytes"] or digest.hexdigest() != row["sha256"] or \
                _identity(after) != self.files[row["index"]]:
            raise InputError(f"{what} full SHA-256 recheck failed")
        self.check_unchanged(row)

    def close(self):
        for fd, _chain in self.parents.values():
            self.fds.close(fd)
        self.parents = {}
        self.fds.close(self.root_fd)
        self.root_fd = None


def compare_with_profile(row, expected, header, plan):
    """Every frozen header/plan fact against the same-descriptor parsed data."""
    lh, eh = row["header"], expected["header"]
    actual = {
        "signature": (header["signature"], eh["signature"]),
        "header46_sha256": (header["header_sha256"], eh["header46_sha256"]),
        "declared_version": (header["declared_version"], eh["declared_version"]),
        "effective_version": (header["effective_version"], eh["effective_version"]),
        "layout": (header["layout"], eh["layout"]),
        "offset_word": (header["field_u32_30"], lh["offset_word"]),
        "subtract_word": (header["field_u32_34"], eh["subtract_word"]),
        "raw_count_word": (header["field_u32_38"], eh["raw_count_word"]),
        "record_count": (header["record_count"], eh["record_count"]),
        "table_start": (header["table_pos"], eh["table_start"]),
        "table_offset": (header["table_offset"], eh["table_start"]),
        "table_skip": (header["table_skip"], 0),
        "table_end": (plan["stored_end"], eh["table_end"]),
        "table_bytes": (plan["stored_bytes"], eh["table_bytes"]),
        "stored_start": (plan["stored_start"], eh["table_start"]),
    }
    differs = sorted(k for k, (a, b) in actual.items() if not _same(a, b))
    if differs or set(plan) != {"stored_start", "stored_end", "stored_bytes"}:
        raise ProfileMismatch(f"archive {row['index']} header/plan facts disagree with the "
                              f"frozen profile: {differs or ['plan keys']}")
    return {k: True for k in sorted(actual)}


def compare_table(row, expected, table, counts):
    et = expected["table"]
    checks = {
        "stored_sha256": _same(table.get("stored_sha256"), et["stored_sha256"]),
        "table_sha256": _same(table.get("table_sha256"), et["stored_sha256"]),
        "form": table.get("form") == expected["header"]["table_form"],
        "table_bytes": _same(table.get("table_bytes"), expected["header"]["table_bytes"]),
        "consumed_bytes": _same(table.get("consumed_bytes"), et["consumed_bytes"]),
        "trailing_bytes": _same(table.get("trailing_bytes"), et["trailing_bytes"]),
        "trailing_sha256": _same(table.get("trailing_sha256"), et["trailing_sha256"]),
        "counts": _same(counts, expected["counts"]),
    }
    differs = sorted(k for k, ok in checks.items() if not ok)
    if differs:
        raise ProfileMismatch(f"archive {row['index']} table/count facts disagree with the "
                              f"frozen profile: {differs}")
    return {k: True for k in sorted(checks)}


# --- Checked publication --------------------------------------------------------------------

class _Budget:
    def __init__(self, limit=None):
        self.limit, self.used = MAX_OUTPUT_BYTES_TOTAL if limit is None else limit, 0

    def take(self, size, what):
        if self.used + size > self.limit:
            raise ResourceLimit(f"{what} would exceed the {self.limit}-byte aggregate "
                                "output bound")
        self.used += size


class CheckedFile:
    """Exclusive, no-follow 0600 writer with checked progress, fsync and close."""

    def __init__(self, fds, dir_fd, name, created, limit, budget):
        fd = self._create(fds, dir_fd, name)
        created[name] = None  # never unlink before ownership is verified
        self.fds, self.fd, self.name, self.limit, self.budget = fds, fd, name, limit, budget
        try:
            info = os.fstat(fd)
            created[name] = (info.st_dev, info.st_ino)
            os.fchmod(fd, 0o600)
            self.digest = hashlib.sha256()
            self.buffer = bytearray()
            self.bytes = self.lines = 0
        except BaseException:
            self.abort()
            raise

    @staticmethod
    def _create(fds, dir_fd, name):
        try:
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600,
                         dir_fd=dir_fd)
        except OSError as exc:
            raise OutputError(f"output {name} cannot be created exclusively: "
                              f"{exc.strerror}") from None
        fds.open_fds.add(fd)
        return fd

    def write(self, data):
        if self.bytes + len(data) > self.limit:
            raise ResourceLimit(f"output file {self.name} above its {self.limit}-byte limit")
        self.budget.take(len(data), f"output file {self.name}")
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
                written = _interruptible(lambda: _write_chunk(self.fd, view),
                                         f"write of {self.name}", OutputError)
                if type(written) is not int or written <= 0 or written > len(view):
                    raise OutputError(f"write of {self.name} made no valid progress")
                view = view[written:]
        finally:
            view.release()
        self.buffer = bytearray()

    def close(self):
        self.flush()
        _fsync(self.fd)
        closing, self.fd = self.fd, None
        self.fds.close(closing)
        return {"file": self.name, "bytes": self.bytes, "lines": self.lines,
                "sha256": self.digest.hexdigest()}

    def abort(self):
        if self.fd is not None:
            closing, self.fd = self.fd, None
            self.fds.open_fds.discard(closing)
            try:
                os.close(closing)
            except OSError:
                pass


def _max_line(data):
    return max((len(line) + 1 for line in data.split(b"\n")), default=0)


def _publish_document(core, fds, dir_fd, name, data, created, budget):
    if _max_line(data) > MAX_JSON_LINE_BYTES:
        raise ResourceLimit(f"{name} has a line above {MAX_JSON_LINE_BYTES} bytes")
    writer = CheckedFile(fds, dir_fd, name, created, len(data), budget)
    try:
        writer.write(data)
        result = writer.close()
    except BaseException:
        writer.abort()
        raise
    _readback(core, dir_fd, name, result["bytes"], result["sha256"], created[name])
    return result


def _readback(core, dir_fd, name, size, digest, identity):
    try:
        core._verify_published(dir_fd, name, size, digest, identity)
    except core.CatalogError as exc:
        raise OutputError(str(exc)) from None
    except OSError as exc:
        raise OutputError(f"readback of {name} failed: {exc.strerror}") from None


class _RecordSink:
    """Write rendered core lines under the line/record bounds; track names and order."""

    def __init__(self, writer, archive, usage):
        self.writer, self.archive, self.usage = writer, archive, usage
        self.names = set()
        self.ordinal = 0

    def __call__(self, line):
        if len(line) > MAX_JSON_LINE_BYTES:
            raise ResourceLimit("record line above the JSON line bound")
        if self.usage["records"] + 1 > MAX_RECORDS_TOTAL:
            raise ResourceLimit("cumulative records above the 1.5 million bound")
        rec = json.loads(line)
        if rec["ordinal"] != self.ordinal or rec["archive"] != self.archive:
            raise InventoryError("core emitted records out of physical order")
        self.writer.write(line)
        self.usage["records"] += 1
        self.ordinal += 1
        self.names.add(rec["name_hex"])


def _totals(profile, archives, name_sets):
    counts = [a["counts"] for a in archives]
    seen = {}
    for names in name_sets:
        for name in names:
            seen[name] = seen.get(name, 0) + 1
    shared = {name for name, n in seen.items() if n > 1}
    return {
        "ledger_objects": len(profile["ledger"]),
        "gpf_objects": SELECTED_OBJECTS + ALREADY_OBJECTS,
        "selected_gpf_objects": len(archives),
        "already_inventoried_gpf_objects": len(profile["already_inventoried_indices"]),
        "unresolved_rgz_objects": len(profile["unresolved_rgz_indices"]),
        "ledger_bytes": sum(r["bytes"] for r in profile["ledger"]),
        "selected_archive_bytes": sum(a["bytes"] for a in archives),
        "selected_raw_records": sum(c["raw_records"] for c in counts),
        "selected_table_bytes": sum(a["table"]["table_bytes"] for a in archives),
        "selected_unused_tail_bytes": sum(a["table"]["trailing_bytes"] for a in archives),
        "selected_distinct_raw_names": len(seen),
        "selected_cross_archive_shared_raw_names": len(shared),
        "per_archive_cross_shared_name_presence": {
            str(a["index"]): len(names & shared) for a, names in zip(archives, name_sets)},
        "metadata_eligible": sum(c["metadata_eligible"] for c in counts),
        "within_archive_duplicate_raw_names": sum(c["duplicate_raw_names"] for c in counts),
        "names_without_nul": sum(c["names_without_nul"] for c in counts),
        "empty_names": sum(c["empty_names"] for c in counts),
        "names_with_high_bytes": sum(c["names_with_high_bytes"] for c in counts),
        "kind0_promotions": sum(c["kind0_promotions"] for c in counts),
        "length_bias_underflows": sum(c["length_bias_underflows"]["any"] for c in counts),
        "diagnostic_body_ranges_outside_archive":
            sum(c["diagnostic_body_ranges_outside_archive"] for c in counts),
    }


def _check_totals(profile, totals):
    expected = profile["totals"]
    differs = sorted(k for k, v in expected.items() if not _same(totals.get(k), v))
    if differs:
        raise ProfileMismatch(f"derived totals disagree with the frozen profile: {differs}")


def _sanitize(message, paths):
    text = str(message)
    for path, label in paths:
        for form in {str(path), os.path.abspath(str(path)), os.path.realpath(str(path))}:
            if form and form not in ("/", "."):
                text = text.replace(form, label)
    return text[:MAX_DIAGNOSTIC_CHARS]


def run(input_manifest, input_root, output):
    """Production inventory under the fixed public profile. Return (target, manifest,
    hashes). There are no pin, profile or selection parameters."""
    return _run(PRODUCTION, input_manifest, input_root, output)


def _abs(path, what):
    text = os.fspath(path)
    if not isinstance(text, str) or not text or "\0" in text:
        raise InputError(f"{what} is not a usable path")
    if any(p == ".." for p in text.split("/")):
        raise InputError(f"{what} must not contain dot-dot components")
    return os.path.abspath(text)


def _run(contract, input_manifest, input_root, output):
    fds = _Fds()
    try:
        return _run_owned(contract, fds, input_manifest, input_root, output)
    except OSError as exc:
        # Before output reservation; strerror only, as OSError text can carry names.
        failure = InputError(f"{type(exc).__name__}: {exc.strerror or exc.errno}")
        failure.category = "os_error"
        raise failure from None
    finally:
        fds.close_quietly()


def _run_owned(contract, fds, input_manifest, input_root, output):
    profile, profile_id = _read_profile(fds, contract)
    core, core_id = _load_core(fds, contract)
    _check_core_module(core)
    generator, generator_id = _read_generator(fds, contract)
    im_pin = {"bytes": profile["input_manifest"]["bytes"],
              "sha256": profile["input_manifest"]["sha256"]}
    manifest_path = _abs(input_manifest, "input manifest")
    root_path = _abs(input_root, "input root")
    data, manifest_identity, manifest_chain = _read_path(
        fds, manifest_path, "input manifest", im_pin["bytes"], im_pin)
    try:
        text = data.decode("utf-8")
    except UnicodeError:
        raise InputError("input manifest is not UTF-8 JSON") from None
    validate_input_manifest(_json(text, "input manifest"), profile)
    contract.phase("admitted_contract")

    try:
        target = core.trusted_target(output)
    except core.CatalogError:
        raise OutputError("output parent must exist, be a real directory owned by you and "
                          "not group/world writable") from None
    if os.path.lexists(target):
        raise OutputError("output already exists, refusing to overwrite")
    root_real = os.path.realpath(root_path)
    if os.path.commonpath([root_real, os.path.realpath(target.parent)]) == root_real:
        raise OutputError("output must not be inside the input root")

    inputs = _Inputs(fds, root_path, profile)
    try:
        os.mkdir(target, 0o700)  # exclusive: refuses any file, dir or (dangling) symlink
    except OSError as exc:
        inputs.close()
        raise OutputError(f"output exists or cannot be created, refusing: "
                          f"{exc.strerror}") from None
    contract.phase("output_reserved", target=target)

    out_fd, identity, created = None, None, {}
    budget = _Budget()
    usage = {"archive_bytes_hashed": 0, "table_bytes_captured": 0, "records": 0,
             "record_file_bytes": 0, "input_manifest_bytes_read": len(data),
             "recheck_archive_bytes_hashed": 0}
    selected = _selected_rows(profile)
    try:
        out_fd = fds.open(str(target), DIR_FLAGS, what="output directory", error=OutputError)
        info = os.fstat(out_fd)
        identity = (info.st_dev, info.st_ino)
        if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise OutputError("reserved output directory is not private to you")
        archives, name_sets = [], []
        for position, (row, expected) in enumerate(zip(selected,
                                                       profile["selected_expected"])):
            storage = posixpath.basename(row["path"])
            inputs.check_unchanged(row)
            contract.phase("archive_read", index=row["index"], position=position)
            header, plan, stored, size = core.read_archive(
                inputs.parent_fd(row), {"file": storage, "bytes": row["bytes"],
                                        "sha256": row["sha256"]}, usage)
            inputs.check_unchanged(row)
            agreement = compare_with_profile(row, expected, header, plan)
            records_name = f"{row['index']}{RECORDS_SUFFIX}"
            writer = CheckedFile(fds, out_fd, records_name, created, MAX_RECORD_FILE_BYTES,
                                 budget)
            sink = _RecordSink(writer, row["file"], usage)
            try:
                table, counts = core.catalog_table(header, plan, stored, size, row["file"],
                                                   sink, row["sha256"])
                del stored
                record_file = writer.close()
            except BaseException:
                writer.abort()
                raise
            _readback(core, out_fd, records_name, record_file["bytes"], record_file["sha256"],
                      created[records_name])
            if counts["raw_records"] != header["record_count"] or \
                    record_file["lines"] != header["record_count"]:
                raise InventoryError(f"archive {row['index']} record count differs from "
                                     "its header")
            table_agreement = compare_table(row, expected, table, counts)
            usage["record_file_bytes"] += record_file["bytes"]
            name_sets.append(sink.names)
            archives.append(_archive_entry(position, row, header, plan, table, counts,
                                           {**agreement, **table_agreement}, record_file))
        totals = _totals(profile, archives, name_sets)
        del name_sets
        _check_totals(profile, totals)
        contract.phase("records_written")

        # Full input recheck (including opaque full rehash) before any manifest.
        _recheck_sources(fds, contract, profile_id, core_id, generator, generator_id,
                         manifest_path, im_pin, manifest_identity, manifest_chain, profile)
        inputs.recheck(rehash=True)
        usage["recheck_archive_bytes_hashed"] = sum(r["bytes"] for r in selected)

        manifest = _build_manifest(contract, profile, core, generator, archives, totals,
                                   usage)
        manifest_bytes = core.render(manifest)
        if len(manifest_bytes) > MAX_MANIFEST_DOCUMENT_BYTES:
            raise ResourceLimit("inventory manifest above its document bound")
        _publish_document(core, fds, out_fd, OUTPUT_MANIFEST, manifest_bytes, created, budget)
        complete = core.render(_complete_document(manifest, manifest_bytes))
        hashes = {"manifest_sha256": sha256(manifest_bytes),
                  "manifest_bytes": len(manifest_bytes), "complete_sha256": sha256(complete)}
        expected_files = {a["records_file"]["file"]: a["records_file"] for a in archives}
        expected_files[OUTPUT_MANIFEST] = {"bytes": len(manifest_bytes),
                                           "sha256": hashes["manifest_sha256"]}

        contract.phase("before_completion", out_fd=out_fd)
        _recheck_sources(fds, contract, profile_id, core_id, generator, generator_id,
                         manifest_path, im_pin, manifest_identity, manifest_chain, profile)
        inputs.recheck(rehash=False)
        _audit_outputs(core, out_fd, created, expected_files)
        _check_target(target, identity)
        _publish_document(core, fds, out_fd, OUTPUT_COMPLETE, complete, created, budget)
        expected_files[OUTPUT_COMPLETE] = {"bytes": len(complete),
                                           "sha256": hashes["complete_sha256"]}
        contract.phase("after_completion", out_fd=out_fd)
        _audit_outputs(core, out_fd, created, expected_files)
        _check_target(target, identity)
        _verify_inventory(target, contract, expect_identity=identity)
        # The consumer is not an ownership oracle for this run; recheck everything.
        _recheck_sources(fds, contract, profile_id, core_id, generator, generator_id,
                         manifest_path, im_pin, manifest_identity, manifest_chain, profile)
        inputs.recheck(rehash=False)
        inputs.close()
        _audit_outputs(core, out_fd, created, expected_files)
        _check_target(target, identity)
        closing_fd, out_fd = out_fd, None
        fds.close(closing_fd)
        _check_target(target, identity)
        if fds.open_fds:
            raise OutputError("run-owned descriptors remain open at completion")
    except Exception as exc:
        _fail_publication(core, fds, exc, target, identity, out_fd, created, budget)
    return target, manifest, hashes


def _archive_entry(position, row, header, plan, table, counts, agreement, record_file):
    return {
        "position": position, "index": row["index"], "lf": row["lf"],
        "source_ordinal": row["source_ordinal"], "file": row["file"], "url": row["url"],
        "storage_path": row["path"], "storage_basename": posixpath.basename(row["path"]),
        "acquisition_status": row["acquisition_status"], "family": row["family"],
        "bytes": row["bytes"], "sha256": row["sha256"],
        "input_checks": dict.fromkeys(
            ("regular_single_link", "no_follow_parent_walk", "same_descriptor_read",
             "full_sha256", "identity_stable", "full_sha256_recheck",
             "ledger_header_matches"), True),
        "header": header, "plan": plan, "table": table, "profile_agreement": agreement,
        "counts": counts, "records_file": record_file,
    }


def _check_target(target, identity):
    try:
        info = os.stat(target, follow_symlinks=False)
    except OSError:
        raise OutputError("reserved output directory is no longer at its path") from None
    if not stat.S_ISDIR(info.st_mode) or (info.st_dev, info.st_ino) != identity:
        raise OutputError("reserved output directory was replaced")
    if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise OutputError("reserved output directory is not private to you")


def _audit_outputs(core, out_fd, created, expected_files):
    """Exact membership, kind/link/mode/identity and full hash of every owned output."""
    if sorted(os.listdir(out_fd)) != sorted(created) or \
            sorted(created) != sorted(expected_files):
        raise OutputError("output directory membership differs from the files this run "
                          "wrote")
    for name, expected in expected_files.items():
        info = os.stat(name, dir_fd=out_fd, follow_symlinks=False)
        _private_file(info, name, OutputError)
        if (info.st_dev, info.st_ino) != created[name]:
            raise OutputError(f"output {name} was replaced")
        _readback(core, out_fd, name, expected["bytes"], expected["sha256"], created[name])


def _recheck_sources(fds, contract, profile_id, core_id, generator, generator_id,
                     manifest_path, im_pin, manifest_identity, manifest_chain, profile):
    for path, pin, what, before in (
            (str(contract.profile_path), contract.profile_pin, "profile", profile_id),
            (str(contract.core_path), contract.core_pin, "core", core_id),
            (str(contract.generator_path), generator, "generator source", generator_id),
            (manifest_path, im_pin, "input manifest", (manifest_identity, manifest_chain))):
        data, identity, chain = _read_path(fds, path, what, pin["bytes"], pin)
        if (identity, chain) != before:
            raise InputError(f"{what} identity changed during the run")
        if what == "input manifest":
            validate_input_manifest(_json(data.decode("utf-8"), what), profile)


def _build_manifest(contract, profile, core, generator, archives, totals, usage):
    ledger = profile["ledger"]
    im = profile["input_manifest"]
    helper = profile["optional_executed_helper"]
    return {
        "schema": MANIFEST_SCHEMA,
        "task": TASK,
        "kind": "raw physical GRF table inventory of the selected patch GPF archives",
        "status": "complete",
        "status_meaning": "every declared physical record of every selected archive was "
                          "inventoried under the bounded core policy; not RGZ grammar, "
                          "publisher application, lookup priority, filename codec, payload, "
                          "map, render, playability or coverage evidence",
        "generator": {"tool": GENERATOR_REL, "version": VERSION, **generator},
        "core": {"path": CORE_REL, **contract.core_pin, "version": core.VERSION,
                 "executed": True,
                 "execution": "exact verified bytes compiled into a fresh private module",
                 "reused": CORE_REUSED, "not_used": CORE_NOT_USED},
        "helper": {**helper, "executed": False,
                   "meaning": "no October helper code was executed or imported"},
        "profile": {"path": PROFILE_REL, **contract.profile_pin, "schema": profile["schema"],
                    "basis_revision": profile["basis_revision"],
                    "freeze_status": profile["freeze_status"]},
        "input_manifest": {"path": im["path"], "bytes": im["bytes"], "sha256": im["sha256"],
                           "schema": im["schema"], "required_fields": im["required_fields"],
                           "ledger_equals_profile": True},
        "source_evidence": profile["source_evidence"],
        "source_evidence_access": profile["source_evidence_access"],
        "enumeration_basis": profile["enumeration_basis"],
        "enumeration_order": profile["enumeration_order"],
        "lookup_priority": None,
        "priority_status": "not_established",
        "publisher_digest_status": profile["publisher_digest_status"],
        "semantics": SEMANTICS,
        "ledger": ledger,
        "dispositions": {
            DISPOSITION_SELECTED: {"indices": profile["enumeration_order"], "opened": True},
            DISPOSITION_ALREADY: {"indices": profile["already_inventoried_indices"],
                                  "opened": False},
            DISPOSITION_RGZ: {"indices": profile["unresolved_rgz_indices"], "opened": False},
        },
        "source_rules": {"core_source": core.SOURCE, "validator_policy": core.VALIDATOR_POLICY,
                         "profile_source_rules": profile["source_rules"],
                         "input_rules": INPUT_RULES, "publication_rules": PUBLICATION_RULES,
                         "tail_policy": profile["output"]["tail_policy"],
                         "record_schema": profile["output"]["record_schema"],
                         "source_join": profile["output"]["source_join"]},
        "archives": archives,
        "totals": totals,
        "work_limits": {"profile": profile["work_limits"], "core": core.WORK_LIMITS},
        "work_usage": usage,
        "rechecks": {
            "before_manifest": ["profile", "core", "generator", "input_manifest",
                                "input_root_chain", "archive_parents",
                                "archive_identities", "archive_full_sha256"],
            "before_completion": ["profile", "core", "generator", "input_manifest",
                                  "input_root_chain", "archive_parents",
                                  "archive_identities", "output_audit"],
            "after_consumer": ["profile", "core", "generator", "input_manifest",
                               "input_root_chain", "archive_parents", "archive_identities",
                               "output_audit"],
        },
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


def _fail_publication(core, fds, exc, target, identity, out_fd, created, budget):
    """Remove only a verified owned completion record, write a path-free failure marker
    when the reserved directory is verifiable, and raise a categorized error."""
    note = "; partial output remains (failed); inspect it before deleting or retrying"
    cleanup_fd, reopened = out_fd, False
    try:
        if cleanup_fd is not None:
            current = os.fstat(cleanup_fd)
            if (current.st_dev, current.st_ino) != identity:
                raise OutputError("reserved output directory descriptor changed")
            here = os.stat(target, follow_symlinks=False)
            if (here.st_dev, here.st_ino) != identity:
                raise OutputError("reserved output directory was replaced at its path")
        elif identity is not None:
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
            if not stat.S_ISREG(marker.st_mode) or created[OUTPUT_COMPLETE] is None or \
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
        category, detail = "os_error", f"{type(exc).__name__}: {exc.strerror or exc.errno}"
    else:
        category, detail = "unexpected", type(exc).__name__
    if cleanup_fd is not None and OUTPUT_FAILED not in created:
        try:
            # The failure marker is outside the aggregate budget of a refused run.
            _publish_document(core, fds, cleanup_fd, OUTPUT_FAILED, core.render({
                "schema": FAILED_SCHEMA, "task": TASK, "generator_version": VERSION,
                "status": "failed", "category": category,
                "files_written_by_run": sorted(set(created) - {OUTPUT_COMPLETE}),
                "meaning": "failed publication; this marker overrides any completion "
                           "record; do not use this directory as an inventory"}), created,
                _Budget())
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


# --- Consumer gate --------------------------------------------------------------------------

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
    identities[name] = _identity(before)


def _read_output_file(dir_fd, name, limit, identities):
    fd = os.open(name, FILE_FLAGS, dir_fd=dir_fd)
    try:
        before = os.fstat(fd)
        _private_file(before, name)
        if before.st_size > limit:
            raise VerificationError(f"{name} is above its document limit")
        data = _read_fd(fd, before.st_size, name, VerificationError)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    _remember_file(dir_fd, name, before, after, identities)
    return data


def _canonical_json(data, name):
    try:
        doc = _json(data.decode("ascii"), name, VerificationError)
    except UnicodeError:
        raise VerificationError(f"{name} is not ASCII JSON") from None
    if (json.dumps(doc, ensure_ascii=True, indent=1, sort_keys=True) + "\n").encode() != data:
        raise VerificationError(f"{name} is not in canonical form")
    return doc


def _verify_inventory(output, contract, expect_identity=None):
    fds = _Fds()
    try:
        return _verify_tree(fds, output, contract, expect_identity)
    except VerificationError:
        raise
    except InventoryError as exc:
        raise VerificationError(f"inventory refused: sources unavailable ({exc.category})") \
            from None
    except (ValueError, OSError, KeyError, TypeError, AttributeError, IndexError,
            OverflowError, RecursionError):
        raise VerificationError("inventory refused: malformed, changed or unreadable "
                                "inventory contract") from None
    finally:
        fds.close_quietly()


def _need(ok, why):
    if not ok:
        raise VerificationError(f"inventory refused: {why}")


def _header_contract(header, row, expected, core):
    """Recompute the core header dictionary from its reported raw fields; no archive
    is reopened and the 46-byte hash is the frozen profile value."""
    keys = {"signature", "signature_field_hex", "header_sha256", "declared_version",
            "field_u32_30", "field_u32_34", "field_u32_38", "effective_version", "layout",
            "version_provenance", "count_rule", "table_offset", "record_count",
            "table_skip", "table_pos"}
    _need(isinstance(header, dict) and set(header) == keys, "header keys")
    _need(all(_is_int(header[k]) and header[k] < 1 << 32 for k in
              ("declared_version", "field_u32_30", "field_u32_34", "field_u32_38")),
          "header u32 fields")
    field = header["signature_field_hex"]
    _need(isinstance(field, str) and len(field) == 30 and
          all(c in "0123456789abcdef" for c in field), "signature field")
    probe = bytearray(46)
    probe[:15] = bytes.fromhex(field)
    for offset, key in ((30, "field_u32_30"), (34, "field_u32_34"),
                        (38, "field_u32_38"), (42, "declared_version")):
        probe[offset:offset + 4] = header[key].to_bytes(4, "little")
    try:
        recomputed = core.parse_header(bytes(probe))
    except core.CatalogError:
        raise VerificationError("inventory refused: header fields are not source-valid") \
            from None
    recomputed["header_sha256"] = expected["header"]["header46_sha256"]
    _need(_same(header, recomputed), "source-derived header fields")
    plan = {"stored_start": header["table_pos"], "stored_end": row["bytes"],
            "stored_bytes": row["bytes"] - header["table_pos"]}
    try:
        return compare_with_profile(row, expected, header, plan), plan
    except ProfileMismatch:
        raise VerificationError("inventory refused: header differs from the profile") \
            from None


_RECORD_KEYS = {
    "archive", "archive_sha256", "ordinal", "table_offset", "record_bytes", "block_length",
    "block_low_byte", "derived_name_length", "name_start", "metadata_offset",
    "encoded_region_bytes", "encoded_region_sha256", "encoded_name_sha256",
    "transformed_blocks", "untransformed_name_bytes", "name_hex", "name_length",
    "name_terminated", "size_field", "aligned_field", "real_size", "derived_compressed_size",
    "derived_length_aligned", "compressed_size", "length_aligned", "compressed_underflow",
    "aligned_underflow", "original_kind", "effective_kind", "header_encryption_flag",
    "metadata_filter", "archive_offset", "payload_offset_field", "diagnostic_body_range",
    "diagnostic_body_range_within_archive",
}
_RECORD_UNSIGNED = {
    "ordinal", "table_offset", "record_bytes", "block_length", "block_low_byte",
    "derived_name_length", "name_start", "metadata_offset", "encoded_region_bytes",
    "transformed_blocks", "untransformed_name_bytes", "name_length", "size_field",
    "aligned_field", "real_size", "compressed_size", "length_aligned", "original_kind",
    "effective_kind", "archive_offset", "payload_offset_field",
}


def _record_contract(rec, row, header, ordinal, consumed, table_bytes, core):
    """Typed fields and recomputed relations of one core legacy_records row.

    Opaque encoded-region hashes remain bound observations except where the encoded
    range is empty; the original name transformation is not re-proved from hashes."""
    _need(isinstance(rec, dict) and set(rec) == _RECORD_KEYS, "record keys")
    _need(all(_is_int(rec[k]) for k in _RECORD_UNSIGNED), "record unsigned integer types")
    _need(type(rec["derived_compressed_size"]) is int and
          type(rec["derived_length_aligned"]) is int, "record signed integer types")
    _need(all(type(rec[k]) is bool for k in ("name_terminated", "compressed_underflow",
                                              "aligned_underflow",
                                              "diagnostic_body_range_within_archive")),
          "record boolean types")
    _need(rec["ordinal"] == ordinal and rec["table_offset"] == consumed and
          rec["archive"] == row["file"] and rec["archive_sha256"] == row["sha256"],
          "record identity/order/source association")
    text = rec["name_hex"]
    _need(isinstance(text, str) and len(text) == 2 * rec["name_length"] and
          all(c in "0123456789abcdef" for c in text), "record raw name hex")
    raw = bytes.fromhex(text)
    _need(b"\0" not in raw, "record name has no NUL")
    _need(all(rec[k] < 1 << 32 for k in ("block_length", "size_field", "aligned_field",
                                          "real_size", "payload_offset_field")) and
          rec["original_kind"] < 256, "record source integer ranges")
    block = rec["block_length"]
    derived = max((block & 255) - 6, 0)
    region = block - 2
    _need(region >= derived, "legacy name region")
    blocks = min((derived + 7) // 8, region // 8)
    relations = {"block_low_byte": block & 255, "derived_name_length": derived,
                 "name_start": 6, "metadata_offset": 4 + block,
                 "encoded_region_bytes": region, "transformed_blocks": blocks,
                 "untransformed_name_bytes": max(derived - 8 * blocks, 0),
                 "record_bytes": 4 + block + core.LEGACY_ENTRY_DATA_SIZE,
                 "archive_offset": header["table_pos"] + consumed}
    _need(all(_same(rec[k], v) for k, v in relations.items()), "legacy field relations")
    _need(consumed + rec["record_bytes"] <= table_bytes, "record within the table")
    _need(rec["name_length"] < derived if rec["name_terminated"] else
          rec["name_length"] == derived, "legacy name length/termination")
    _need(_is_hex64(rec["encoded_region_sha256"]) and _is_hex64(rec["encoded_name_sha256"]),
          "legacy encoded hashes")
    _need((region > 0 or rec["encoded_region_sha256"] == EMPTY_SHA256) and
          (derived > 0 or rec["encoded_name_sha256"] == EMPTY_SHA256),
          "empty encoded range hashes")
    compressed = rec["size_field"] - rec["real_size"] - core.LEGACY_LENGTH_BIAS
    aligned = rec["aligned_field"] - core.LEGACY_ALIGNED_BIAS
    _need(_same(rec["derived_compressed_size"], compressed) and
          _same(rec["derived_length_aligned"], aligned) and
          _same(rec["compressed_underflow"], compressed < 0) and
          _same(rec["aligned_underflow"], aligned < 0) and
          rec["compressed_size"] == max(compressed, 0) and
          rec["length_aligned"] == max(aligned, 0), "legacy length biases")
    effective, encryption = rec["original_kind"], None
    if compressed < 0 or aligned < 0:
        effective &= ~core.TYPE_FILE & 255
    elif effective & core.TYPE_FILE:
        bit = core.header_encryption(raw)
        effective |= bit
        encryption = "header" if bit == core.TYPE_ENCRYPT_HEADER else "mixed"
    _need(rec["header_encryption_flag"] == encryption and rec["effective_kind"] == effective
          and rec["metadata_filter"] == core.metadata_filter(rec["real_size"], effective),
          "record kind/encryption/filter")
    start = rec["payload_offset_field"] + core.HEADER_SIZE
    body = [start, start + rec["length_aligned"]]
    _need(_same(rec["diagnostic_body_range"], body) and
          _same(rec["diagnostic_body_range_within_archive"], body[1] <= row["bytes"]),
          "diagnostic range relation")
    return raw


def _verify_records(dir_fd, rf, row, header, table_bytes, core, identities):
    name = f"{row['index']}{RECORDS_SUFFIX}"
    _need(isinstance(rf, dict) and set(rf) == {"file", "bytes", "lines", "sha256"} and
          rf["file"] == name and _is_int(rf["bytes"]) and _is_int(rf["lines"]) and
          _is_hex64(rf["sha256"]), "record-file contract")
    fd = os.open(name, FILE_FLAGS, dir_fd=dir_fd)
    try:
        before = os.fstat(fd)
        _private_file(before, name)
        _need(before.st_size == rf["bytes"] <= MAX_RECORD_FILE_BYTES and
              rf["lines"] == header["record_count"], "record-file size/lines")
        digest = hashlib.sha256()
        pending, ordinal, total, consumed = b"", 0, 0, 0
        summary = core.Summary()
        names = set()
        while total <= before.st_size:
            chunk = _interruptible(
                lambda: _read_chunk(fd, min(READ_CHUNK_BYTES, before.st_size + 1 - total)),
                f"read of {name}", VerificationError)
            if not chunk:
                break
            total += len(chunk)
            _need(total <= before.st_size, "record-file growth")
            digest.update(chunk)
            lines = (pending + chunk).split(b"\n")
            pending = lines.pop()
            _need(len(pending) < MAX_JSON_LINE_BYTES, "record line bound")
            for line in lines:
                _need(ordinal < header["record_count"], "extra record")
                _need(len(line) + 1 <= MAX_JSON_LINE_BYTES, "record line bound")
                try:
                    rec = _json(line.decode("ascii"), "record", VerificationError)
                except UnicodeError:
                    raise VerificationError("inventory refused: non-ASCII record") from None
                _need(core.render_record(row["file"], row["sha256"], rec) == line + b"\n",
                      "noncanonical record")
                raw = _record_contract(rec, row, header, ordinal, consumed, table_bytes, core)
                consumed += rec["record_bytes"]
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


def _verify_tree(fds, output, contract, expect_identity):
    profile, profile_id = _read_profile(fds, contract)
    core, core_id = _load_core(fds, contract)
    _check_core_module(core)
    generator, generator_id = _read_generator(fds, contract)
    selected = _selected_rows(profile)
    record_names = [f"{r['index']}{RECORDS_SUFFIX}" for r in selected]
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
        _need(OUTPUT_FAILED not in listing, "failure marker present")
        _need(listing == sorted(record_names + [OUTPUT_MANIFEST, OUTPUT_COMPLETE]) and
              len(listing) == profile["output"]["success_file_count"],
              "missing or extra files")
        complete = _canonical_json(_read_output_file(
            dir_fd, OUTPUT_COMPLETE, MAX_COMPLETE_DOCUMENT_BYTES, identities), OUTPUT_COMPLETE)
        manifest_bytes = _read_output_file(dir_fd, OUTPUT_MANIFEST,
                                           MAX_MANIFEST_DOCUMENT_BYTES, identities)
        manifest = _canonical_json(manifest_bytes, OUTPUT_MANIFEST)
        _need(isinstance(manifest, dict) and isinstance(complete, dict), "document shapes")
        _need(set(complete) == {"schema", "task", "generator_version", "status",
                                "inventory_manifest", "inventory_manifest_bytes",
                                "inventory_manifest_sha256", "record_files"},
              "completion keys")
        _need(complete["schema"] == COMPLETE_SCHEMA and complete["task"] == TASK and
              complete["status"] == "complete" and
              _same(complete["inventory_manifest_bytes"], len(manifest_bytes)) and
              complete["inventory_manifest_sha256"] == sha256(manifest_bytes),
              "completion/manifest binding")
        archives = manifest.get("archives")
        _need(isinstance(archives, list) and len(archives) == len(selected), "archive list")
        entry_keys = set(_archive_entry(0, selected[0], {}, {}, {}, {}, {}, {}))
        name_sets, rebuilt = [], []
        for position, (row, expected, entry) in enumerate(
                zip(selected, profile["selected_expected"], archives)):
            _need(isinstance(entry, dict) and set(entry) == entry_keys, "archive keys")
            agreement, plan = _header_contract(entry["header"], row, expected, core)
            table_bytes = plan["stored_bytes"]
            counts, raw_names, consumed = _verify_records(
                dir_fd, entry["records_file"], row, entry["header"], table_bytes, core,
                identities)
            table = {"stored_offset": plan["stored_start"], "stored_bytes": table_bytes,
                     "stored_sha256": expected["table"]["stored_sha256"],
                     "form": "clear legacy table to EOF", "table_bytes": table_bytes,
                     "table_sha256": expected["table"]["stored_sha256"],
                     "consumed_bytes": consumed, "trailing_bytes": table_bytes - consumed,
                     "trailing_sha256": EMPTY_SHA256 if consumed == table_bytes else
                     entry["table"].get("trailing_sha256")}
            try:
                table_agreement = compare_table(row, expected, table, counts)
            except ProfileMismatch:
                raise VerificationError("inventory refused: records/table differ from the "
                                        "profile") from None
            name_sets.append(raw_names)
            rebuilt.append(_archive_entry(position, row, entry["header"], plan, table,
                                          counts, {**agreement, **table_agreement},
                                          entry["records_file"]))
        totals = _totals(profile, rebuilt, name_sets)
        try:
            _check_totals(profile, totals)
        except ProfileMismatch:
            raise VerificationError("inventory refused: totals differ from the profile") \
                from None
        usage = {"archive_bytes_hashed": sum(r["bytes"] for r in selected),
                 "table_bytes_captured": sum(a["table"]["stored_bytes"] for a in rebuilt),
                 "records": sum(a["records_file"]["lines"] for a in rebuilt),
                 "record_file_bytes": sum(a["records_file"]["bytes"] for a in rebuilt),
                 "input_manifest_bytes_read": profile["input_manifest"]["bytes"],
                 "recheck_archive_bytes_hashed": sum(r["bytes"] for r in selected)}
        expected_manifest = _build_manifest(contract, profile, core, generator, rebuilt,
                                            totals, usage)
        _need(_same(manifest, expected_manifest),
              "complete manifest/source/profile/ledger/usage contract")
        _need(_same(complete, _complete_document(manifest, manifest_bytes)),
              "complete marker binding")
        if contract.consumer_hook is not None:
            contract.consumer_hook(output)
        # Fresh exact source reads, then final observed file/directory bindings.
        for path, pin, what, original in (
                (str(contract.profile_path), contract.profile_pin, "profile", profile_id),
                (str(contract.core_path), contract.core_pin, "core", core_id),
                (str(contract.generator_path), generator, "generator source", generator_id)):
            data, current, chain = _read_path(fds, path, what, pin["bytes"], pin,
                                              VerificationError)
            _need((current, chain) == original, "source identity changed during verification")
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


# --- CLI ------------------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input_manifest", help="frozen normalized input manifest (read-only)")
    parser.add_argument("input_root", help="root anchoring the ledger paths (read-only)")
    parser.add_argument("output", help="new private output directory")
    args = parser.parse_args(argv)
    paths = [(args.output, "<output>"), (args.input_root, "<input_root>"),
             (args.input_manifest, "<input_manifest>"), (str(CHECKOUT), "<checkout>")]
    try:
        _target, manifest, hashes = run(args.input_manifest, args.input_root, args.output)
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
                      "record_files": {a["records_file"]["file"]: a["records_file"]["sha256"]
                                       for a in manifest["archives"]}, **hashes},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
