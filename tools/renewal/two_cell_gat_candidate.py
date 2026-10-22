"""T07.007.013.001/.002 offline two-cell ygg_roots GAT client candidate.

Unselected hypothesis only, never a production mapping. The public pure entry
``normalize_bytes(data)`` admits exactly one fixed retained body (3200014 bytes,
built-in SHA-256, GRAT 400x400, 14-byte header, 20-byte records) and rewrites
two raw little-endian uint32 type words:

* index 83377 (177,208) at offset 1667570: 0x40000000 -> 0
* index 90507 (107,226) at offset 1810170: 0x40000001 -> 1

The pinned loader table predicts client masks 10 and 1 for raw 0 and 1; mask 10
is never stored. Eight word bytes are addressed but exactly two bytes differ
(1667573 and 1810173, 0x40 -> 0x00). Version bytes, every height byte and every
other type word are preserved; nothing is parsed as float or rescaled.

``write_candidate(source_path, output_dir)`` is an explicit call that admits a
private read-only source and creates a fresh 0700 directory holding exclusive
0600 ``ygg_roots.candidate.gat`` and ``candidate-receipt.json``. There is no
CLI and import performs no I/O. The admission SHA/profile is not configurable.

``_normalize_layout`` is the Root-approved private fixed-layout seam for
authored fixtures; it performs no hash admission and is not a public entry.
The writer also accepts a receipt tagged ``FIXTURE_STUB_SCHEMA`` so that writer
unit tests can stub the normalizer return; real ``normalize_bytes`` never
produces it. Original flagged 0 skips full-raw-zero server water conversion;
the candidate's raw 0 could enter it, so never feed it to a server/cache build.

Close policy (T07.007.013.002). Every successful open becomes one acquisition
in a per-call ledger: a monotonic token 1..6 and a fixed role. Its state moves
open -> closing immediately before exactly one close attempt, then closed on
normal return or uncertain on any ordinary exception. Cleanup visits each
still-open acquisition once, continues after failures and never retries a
closing/closed/uncertain record, so a replacement descriptor is never closed.
Once anything was acquired, a failure raises ``CandidateIOError`` holding the
exact first failure plus every close error. An uncertain close may leave the
original descriptor live: this function does NOT guarantee same-process
release on failure. Output is acceptable only after a successful return AND
separately observed retirement of the owning disposable process AND
independent audits; none of that is decided here.
"""

import hashlib
import json
import os
import pathlib
import stat
import struct

EXPECTED_BYTES = 3200014
EXPECTED_SHA256 = "758ceb1b32e059c9e70bcc55ce917c630b4d67d25b73ec677167af27a3a35ed5"
MAGIC = b"GRAT"
HEADER_BYTES = 14
WIDTH = 400
HEIGHT = 400
CELL_BYTES = 20
TYPE_OFFSET_IN_CELL = 16
READ_LIMIT = EXPECTED_BYTES + 1
BINARY_NAME = "ygg_roots.candidate.gat"
RECEIPT_NAME = "candidate-receipt.json"
RECEIPT_MAX_BYTES = 16384
SCHEMA = "root013-two-cell-gat-candidate-1"
STATUS = "offline_candidate_hypothesis"
FIXTURE_STUB_SCHEMA = "fixture-stub-two-cell-writer-unit-1"
FIXTURE_STUB_STATUS = "fixture_stub_not_actual_admission"

# Frozen profile hypothesis.cells, in order.
CELLS = (
    {
        "index": 83377,
        "x": 177,
        "y": 208,
        "decoded_float_flag_slot": 416889,
        "type_word_offset": 1667570,
        "original_uint32": 1073741824,
        "original_le_hex": "00000040",
        "candidate_uint32": 0,
        "candidate_le_hex": "00000000",
        "predicted_client_mask": 10,
        "differing_byte_offset": 1667573,
    },
    {
        "index": 90507,
        "x": 107,
        "y": 226,
        "decoded_float_flag_slot": 452539,
        "type_word_offset": 1810170,
        "original_uint32": 1073741825,
        "original_le_hex": "01000040",
        "candidate_uint32": 1,
        "candidate_le_hex": "01000000",
        "predicted_client_mask": 1,
        "differing_byte_offset": 1810173,
    },
)
DIFFERING_OFFSETS = (1667573, 1810173)
_WORDS = tuple(
    (c["type_word_offset"], struct.pack("<I", c["original_uint32"]),
     struct.pack("<I", c["candidate_uint32"]))
    for c in CELLS
)

# OS indirection used only so authored unit tests can inject I/O faults.
_open = os.open
_read = os.read
_write = os.write
_fsync = os.fsync
_close = os.close
_fstat = os.fstat


class CandidateError(Exception):
    """Refusal with a short stable ``code``; never a partial success."""

    def __init__(self, code, detail=""):
        super().__init__(code if not detail else "%s: %s" % (code, detail))
        self.code = code


ROLES = ("source", "directory", "binary_write", "binary_readback",
         "receipt_write", "receipt_readback")


class CloseError(tuple):
    """Immutable record of one ordinary close exception; release unknown."""

    __slots__ = ()
    _fields = ("acquisition", "role", "operation", "error", "release_state")

    def __new__(cls, acquisition, role, error):
        return tuple.__new__(cls, (acquisition, role, "close", error,
                                   "unknown"))

    acquisition = property(lambda self: self[0])
    role = property(lambda self: self[1])
    operation = property(lambda self: self[2])
    error = property(lambda self: self[3])
    release_state = property(lambda self: self[4])


class Ownership(tuple):
    """Immutable snapshot of one acquisition; carries no descriptor."""

    __slots__ = ()
    _fields = ("acquisition", "role", "state", "close_attempts")

    def __new__(cls, acquisition, role, state, close_attempts):
        return tuple.__new__(cls, (acquisition, role, state, close_attempts))

    acquisition = property(lambda self: self[0])
    role = property(lambda self: self[1])
    state = property(lambda self: self[2])
    close_attempts = property(lambda self: self[3])


class CandidateIOError(CandidateError):
    """Failure after acquisition: exact primary plus every close error."""

    def __init__(self, code, primary_error, close_errors, ownership):
        super().__init__(code, "%s; close_errors=%d" % (
            type(primary_error).__name__, len(close_errors)))
        self.primary_error = primary_error
        self.close_errors = tuple(close_errors)
        self.ownership = tuple(ownership)
        self.__cause__ = primary_error


class _Acquisition:
    __slots__ = ("token", "role", "fd", "state", "close_attempts")


class _Ledger:
    """Per-call record of every successful open; never closes by bare FD."""

    def __init__(self):
        self.records = []
        self.close_errors = []
        self.stage = "source"
        self.primary_code_hint = None

    def acquire(self, role, fd):
        rec = _Acquisition()
        rec.token = len(self.records) + 1
        rec.role, rec.fd, rec.state, rec.close_attempts = role, fd, "open", 0
        self.records.append(rec)
        return rec

    def close(self, rec):
        if rec.state != "open" or rec.close_attempts:
            raise CandidateError("ledger_close_state", rec.role)
        rec.state = "closing"
        rec.close_attempts = 1
        try:
            _close(rec.fd)
        except Exception as exc:
            rec.state = "uncertain"
            self.close_errors.append(CloseError(rec.token, rec.role, exc))
            raise
        rec.state = "closed"

    def cleanup(self):
        for rec in reversed(self.records):
            if rec.state == "open":
                try:
                    self.close(rec)
                except Exception:
                    pass  # Retained in close_errors; continue.

    def snapshot(self):
        return tuple(Ownership(r.token, r.role, r.state, r.close_attempts)
                     for r in self.records)

    def failure_code(self, primary):
        if self.primary_code_hint is not None:
            return self.primary_code_hint
        if isinstance(primary, CandidateError):
            return primary.code
        if any(e.error is primary for e in self.close_errors):
            return self.stage + "_close"
        return self.stage + "_error"


def _check_layout(data):
    if type(data) is not bytes:
        raise TypeError("data must be built-in bytes")
    if len(data) != EXPECTED_BYTES:
        raise CandidateError("input_length", str(len(data)))
    if data[:4] != MAGIC:
        raise CandidateError("input_magic")
    if struct.unpack_from("<II", data, 6) != (WIDTH, HEIGHT):
        raise CandidateError("input_dimensions")
    for offset, original, _ in _WORDS:
        if data[offset:offset + 4] != original:
            raise CandidateError("input_target_word", str(offset))


def _audit_pair(data, out):
    """Verify ``out`` is exactly the two-word candidate of ``data``."""
    if type(out) is not bytes or len(out) != len(data):
        raise CandidateError("audit_length")
    (o1, a1, b1), (o2, a2, b2) = _WORDS
    if (out[:o1] != data[:o1] or out[o1 + 4:o2] != data[o1 + 4:o2]
            or out[o2 + 4:] != data[o2 + 4:]):
        raise CandidateError("audit_outside_target_words")
    if out[o1:o1 + 4] != b1 or out[o2:o2 + 4] != b2:
        raise CandidateError("audit_candidate_words")
    diff = [o + k for o, _, _ in _WORDS for k in range(4)
            if out[o + k] != data[o + k]]
    if tuple(diff) != DIFFERING_OFFSETS:
        raise CandidateError("audit_differing_bytes", repr(diff))
    for off in diff:
        if (data[off], out[off]) != (0x40, 0x00):
            raise CandidateError("audit_byte_transition", str(off))
    for o, _, _ in _WORDS:
        if (o - HEADER_BYTES) % CELL_BYTES != TYPE_OFFSET_IN_CELL:
            raise CandidateError("audit_word_alignment", str(o))
        if out[o - 16:o] != data[o - 16:o]:
            raise CandidateError("audit_heights")
    if out[:HEADER_BYTES] != data[:HEADER_BYTES]:
        raise CandidateError("audit_header")
    inverse = bytearray(out)
    for o, a, _ in _WORDS:
        inverse[o:o + 4] = a
    if bytes(inverse) != data:
        raise CandidateError("audit_inverse")


def _normalize_layout(data):
    """Private fixture seam: fixed layout/target checks, no hash admission."""
    _check_layout(data)
    buf = bytearray(data)
    for offset, _, candidate in _WORDS:
        buf[offset:offset + 4] = candidate
    out = bytes(buf)
    _audit_pair(data, out)
    return out


def _build_receipt(version_hex, candidate_sha256):
    return {
        "schema": SCHEMA,
        "status": STATUS,
        "input": {"bytes": EXPECTED_BYTES, "sha256": EXPECTED_SHA256},
        "candidate": {"bytes": EXPECTED_BYTES, "sha256": candidate_sha256},
        "format": {
            "magic": "GRAT",
            "version_hex": version_hex,
            "width": WIDTH,
            "height": HEIGHT,
            "header_bytes": HEADER_BYTES,
            "cell_bytes": CELL_BYTES,
            "type_word_offset_within_cell": TYPE_OFFSET_IN_CELL,
            "endian": "little",
        },
        "cells": [dict(c) for c in CELLS],
        "change_audit": {
            "addressed_word_bytes": 8,
            "differing_bytes": 2,
            "differing_byte_offsets": list(DIFFERING_OFFSETS),
            "header_unchanged": True,
            "all_height_bytes_unchanged": True,
            "outside_target_words_unchanged": True,
            "inverse_restores_original": True,
            "inverse_sha256": EXPECTED_SHA256,
        },
        "policy": {
            "production_mapping_selected": False,
            "server_agreement_verified": False,
            "normal_runtime_verified": False,
            "bit30_meaning_known": False,
            "server_cache_generation_permitted": False,
        },
    }


def _is_lower_hex(value, length):
    return (type(value) is str and len(value) == length
            and all(ch in "0123456789abcdef" for ch in value))


def _strict_equal(a, b):
    if type(a) is not type(b):
        return False
    if type(a) is dict:
        return (list(a) == list(b)
                and all(_strict_equal(a[k], b[k]) for k in a))
    if type(a) is list:
        return len(a) == len(b) and all(map(_strict_equal, a, b))
    return a == b


def _validate_real_receipt(receipt):
    """Closed check of the actual-input receipt contract."""
    if type(receipt) is not dict:
        raise CandidateError("receipt_type")
    try:
        version_hex = receipt["format"]["version_hex"]
        candidate_sha = receipt["candidate"]["sha256"]
    except (KeyError, TypeError):
        raise CandidateError("receipt_closed_fields")
    if not _is_lower_hex(version_hex, 4) or not _is_lower_hex(candidate_sha, 64):
        raise CandidateError("receipt_hex_fields")
    if not _strict_equal(receipt, _build_receipt(version_hex, candidate_sha)):
        raise CandidateError("receipt_closed_fields")


def _encode_receipt(receipt):
    try:
        text = json.dumps(receipt, ensure_ascii=True, allow_nan=False,
                          separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise CandidateError("receipt_not_strict_json", type(exc).__name__)
    raw = text.encode("ascii")
    if len(raw) > RECEIPT_MAX_BYTES:
        raise CandidateError("receipt_oversize", str(len(raw)))
    return raw


def _reject_constant(name):
    raise CandidateError("receipt_nonfinite", name)


def _unique_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise CandidateError("receipt_duplicate_key", key)
        out[key] = value
    return out


def _decode_receipt(raw):
    try:
        text = raw.decode("ascii")
        value = json.loads(text, object_pairs_hook=_unique_pairs,
                           parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError) as exc:
        raise CandidateError("receipt_decode", type(exc).__name__)
    if _encode_receipt(value) != raw:
        raise CandidateError("receipt_not_canonical")
    return value


def normalize_bytes(data):
    """Return (candidate_bytes, receipt) for the fixed retained body only."""
    if type(data) is not bytes:
        raise TypeError("data must be built-in bytes")
    if len(data) != EXPECTED_BYTES:
        raise CandidateError("input_length", str(len(data)))
    if hashlib.sha256(data).hexdigest() != EXPECTED_SHA256:
        raise CandidateError("input_sha256_mismatch")
    out = _normalize_layout(data)
    inverse = bytearray(out)
    for offset, original, _ in _WORDS:
        inverse[offset:offset + 4] = original
    if hashlib.sha256(bytes(inverse)).hexdigest() != EXPECTED_SHA256:
        raise CandidateError("inverse_sha256_mismatch")
    receipt = _build_receipt(data[4:6].hex(), hashlib.sha256(out).hexdigest())
    _validate_real_receipt(receipt)
    _encode_receipt(receipt)
    return out, receipt


def _check_writer_result(data, data_sha, out, receipt):
    """Validation before any output is created."""
    if type(out) is not bytes or len(out) != EXPECTED_BYTES:
        raise CandidateError("candidate_length")
    raw = _encode_receipt(receipt)
    if type(receipt) is not dict:
        raise CandidateError("receipt_type")
    cand = {"bytes": len(out), "sha256": hashlib.sha256(out).hexdigest()}
    if not _strict_equal(receipt.get("candidate"), cand):
        raise CandidateError("receipt_candidate_mismatch")
    schema = receipt.get("schema")
    if schema == SCHEMA:
        _validate_real_receipt(receipt)
        if data_sha != EXPECTED_SHA256:
            raise CandidateError("input_sha256_mismatch")
        if receipt["format"]["version_hex"] != data[4:6].hex():
            raise CandidateError("receipt_version_mismatch")
    elif schema == FIXTURE_STUB_SCHEMA:
        if (receipt.get("status") != FIXTURE_STUB_STATUS
                or receipt.get("fixture_only") is not True
                or not set(receipt) <= {"schema", "status", "fixture_only",
                                        "candidate", "note"}):
            raise CandidateError("receipt_fixture_tag")
    else:
        raise CandidateError("receipt_schema")
    _audit_pair(data, out)
    return raw


def _identity(st):
    return (st.st_dev, st.st_ino, st.st_mode, st.st_nlink, st.st_uid,
            st.st_gid, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def _check_source_stat(st):
    if stat.S_ISLNK(st.st_mode):
        raise CandidateError("source_symlink")
    if not stat.S_ISREG(st.st_mode):
        raise CandidateError("source_not_regular")
    if st.st_nlink != 1:
        raise CandidateError("source_link_count")
    if st.st_uid != os.getuid():
        raise CandidateError("source_owner")
    if stat.S_IMODE(st.st_mode) not in (0o400, 0o600):
        raise CandidateError("source_mode", oct(stat.S_IMODE(st.st_mode)))
    if st.st_size != EXPECTED_BYTES:
        raise CandidateError("source_size")


def _read_bounded(fd, limit):
    chunks = []
    total = 0
    while True:
        chunk = _read(fd, min(1048576, limit + 1 - total))
        if type(chunk) is not bytes:
            raise CandidateError("read_type")
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise CandidateError("read_exceeds_limit")
        chunks.append(chunk)
    return b"".join(chunks)


def _read_source(ledger, path):
    pre = os.lstat(path)
    _check_source_stat(pre)
    fd = _open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NOCTTY)
    source = ledger.acquire("source", fd)
    opened = _fstat(fd)
    if _identity(opened) != _identity(pre):
        raise CandidateError("source_identity_opened")
    try:
        data = _read_bounded(fd, EXPECTED_BYTES)
    except OSError:
        ledger.primary_code_hint = "source_read"
        raise
    if len(data) != EXPECTED_BYTES:
        raise CandidateError("source_eof", str(len(data)))
    if _identity(_fstat(fd)) != _identity(pre):
        raise CandidateError("source_identity_after")
    ledger.close(source)
    if _identity(os.lstat(path)) != _identity(pre):
        raise CandidateError("source_identity_path")
    return data, _identity(pre)


def _check_output_target(output_dir):
    name = output_dir.name
    if name in ("", ".", "..") or output_dir.parent == output_dir:
        raise CandidateError("output_name")
    try:
        os.lstat(output_dir)
    except FileNotFoundError:
        pass
    else:
        raise CandidateError("output_exists")
    parent = os.lstat(output_dir.parent)
    if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.getuid()
            or stat.S_IMODE(parent.st_mode) != 0o700):
        raise CandidateError("output_parent")


def _write_all(fd, payload):
    view = memoryview(payload)
    done = 0
    while done < len(payload):
        n = _write(fd, view[done:])
        if type(n) is not int or n <= 0 or n > len(payload) - done:
            raise CandidateError("write_progress", repr(n))
        done += n


def _create_verified(ledger, dfd, name, payload, roles):
    flags = (os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
             | os.O_CLOEXEC)
    try:
        fd = _open(name, flags, 0o600, dir_fd=dfd)
    except FileExistsError:
        raise CandidateError("output_collision", name)
    writer = ledger.acquire(roles[0], fd)
    st = _fstat(fd)
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
        raise CandidateError("output_not_regular", name)
    if stat.S_IMODE(st.st_mode) != 0o600:
        os.fchmod(fd, 0o600)
    _write_all(fd, payload)
    _fsync(fd)
    ledger.close(writer)
    fd = _open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=dfd)
    reader = ledger.acquire(roles[1], fd)
    back = _read_bounded(fd, len(payload))
    ledger.close(reader)
    if back != payload:
        raise CandidateError("readback_mismatch", name)
    if hashlib.sha256(back).digest() != hashlib.sha256(payload).digest():
        raise CandidateError("readback_hash", name)
    return back


def _final_audit(output_dir, dfd):
    dst = os.lstat(output_dir)
    if (_identity(dst)[:2] != _identity(_fstat(dfd))[:2]
            or not stat.S_ISDIR(dst.st_mode)
            or stat.S_IMODE(dst.st_mode) != 0o700):
        raise CandidateError("final_directory")
    if sorted(os.listdir(dfd)) != sorted((BINARY_NAME, RECEIPT_NAME)):
        raise CandidateError("final_listing")
    for name, size in ((BINARY_NAME, EXPECTED_BYTES), (RECEIPT_NAME, None)):
        st = os.stat(name, dir_fd=dfd, follow_symlinks=False)
        if (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1
                or stat.S_IMODE(st.st_mode) != 0o600
                or (size is not None and st.st_size != size)):
            raise CandidateError("final_file", name)


def _write_attempt(ledger, source_path, output_dir):
    _check_output_target(output_dir)
    data, source_identity = _read_source(ledger, source_path)
    ledger.stage = "transform"
    data_sha = hashlib.sha256(data).hexdigest()
    out, receipt = normalize_bytes(data)
    raw = _check_writer_result(data, data_sha, out, receipt)
    _check_output_target(output_dir)
    ledger.stage = "output"
    try:
        os.mkdir(output_dir, 0o700)
    except FileExistsError:
        raise CandidateError("output_exists")
    dfd = _open(output_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                | os.O_CLOEXEC)
    directory = ledger.acquire("directory", dfd)
    dst = _fstat(dfd)
    if dst.st_uid != os.getuid() or not stat.S_ISDIR(dst.st_mode):
        raise CandidateError("output_directory")
    if stat.S_IMODE(dst.st_mode) != 0o700:
        os.fchmod(dfd, 0o700)
    _create_verified(ledger, dfd, BINARY_NAME, out,
                     ("binary_write", "binary_readback"))
    back = _create_verified(ledger, dfd, RECEIPT_NAME, raw,
                            ("receipt_write", "receipt_readback"))
    result = _decode_receipt(back)
    if not _strict_equal(result, receipt):
        raise CandidateError("receipt_readback_value")
    _fsync(dfd)
    _final_audit(output_dir, dfd)
    ledger.close(directory)
    if _identity(os.lstat(source_path)) != source_identity:
        raise CandidateError("source_identity_final")
    return result


def write_candidate(source_path, output_dir):
    """Write the candidate and receipt into a fresh private directory."""
    if not isinstance(source_path, pathlib.Path) or not isinstance(
            output_dir, pathlib.Path):
        raise TypeError("paths must be pathlib.Path")
    ledger = _Ledger()
    primary = None
    try:
        result = _write_attempt(ledger, source_path, output_dir)
    except BaseException as exc:
        primary = exc
    else:
        # Success requires every acquisition closed by normal return.
        if not ledger.close_errors and all(
                r.state == "closed" for r in ledger.records):
            return result
        primary = CandidateError("ledger_open_at_return")
    ledger.cleanup()
    if not isinstance(primary, Exception) or not ledger.records:
        raise primary
    raise CandidateIOError(ledger.failure_code(primary), primary,
                           ledger.close_errors, ledger.snapshot()) from primary
