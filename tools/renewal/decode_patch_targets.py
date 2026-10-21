#!/usr/bin/env python3
"""Decode the twelve admitted target payloads of official patch 9298 (T07.007.003).

Usage: python3 tools/renewal/decode_patch_targets.py SOURCE_ROOT PATCH_9298 FRESH_OUTPUT

The fixed profile and authored known-answer vectors are read from this checkout
(docs/project/fixtures/T07.007.003-*.json) and pinned below by exact length and
SHA-256. The profile admits exactly one GPF (index 9298, full length/SHA and a
46-byte header pin), its table boundary and twelve entry metadata rows, and five
primary-source files. SOURCE_ROOT only supplies those five fixed relative paths;
nothing else there is opened or listed. No pin, target or limit can be changed
from the command line.

Payload decryption is an independent standard-library implementation of the
behaviour in the pinned RemoteClient source (66ba94e2):

- grf.rs read_entry (632-682): read `length_aligned` bytes at offset+46; the
  mixed bit (0x02) wins over the header bit (0x04); decrypt the whole aligned
  buffer with `compressed_size` as the mixed-cycle input.
- des.rs decode_full/decode_header: one-round block transform on the first 20
  whole 8-byte blocks; in mixed mode every later block whose index is a multiple
  of the cycle (from the decimal digit count of compressed_size) is transformed
  and every 7th other block after the first is de-shuffled. A partial tail is
  left alone. Legacy 0x1xx filename nibble rotation is not part of this.

The literal permutation, transposition, S-box and shuffle tables are transcribed
from des.rs (itself a port of the reference loader's des.ts); the bit/index code
is this file's own and is checked against the authored vectors before any body
is read.

Framing is a validator policy that is stricter than the native reader (which
truncates stored entries and otherwise runs uncapped zlib over the whole aligned
buffer without checking the decoded size): real == compressed is stored;
otherwise only the first compressed_size decrypted bytes are inflated with a
real_size + 1 output cap and must end exactly at the declared size, at stream
EOF with a valid checksum and nothing left over. Bytes past compressed_size are
alignment padding: their length and raw/decrypted hashes are recorded, their
values are not constrained. These refusals are policy, not native rejections.
The first four decoded bytes must match the loader signature for the target
kind (World.js GRSW, Ground.js GRGN, Altitude.js GRAT); the next two version
bytes are only observed.

Output: target-000.body .. target-011.body, payload-manifest.json and, last,
payload-complete.json in a fresh 0700 directory of 0600 single-link files.
payload-failed.json overrides completion. verify_payloads(output) is the
read-only consumer. Nothing here claims native parity, dependency closure,
supported terrain versions, constructor/render/travel/save success or game
content acceptance.
"""

import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import zlib

VERSION = "1.0.0"
TASK = "T07.007.003"
REPO = Path(__file__).resolve().parents[2]
GENERATOR_PATH = "tools/renewal/decode_patch_targets.py"
PROFILE_PATH = "docs/project/fixtures/T07.007.003-profile.json"
VECTORS_PATH = "docs/project/fixtures/T07.007.003-authored.json"
PROFILE_PIN = {"bytes": 8474, "sha256":
               "06805b0a28fef87b53d6e2f87e50079e14a3b7181a44e541b6b0c0aa268ead2a"}
VECTORS_PIN = {"bytes": 49381, "sha256":
               "d7011b6b49a8ed311c73625afe4111ad5abcac2e9dd771407e567a4f5d249a04"}
# Repeated from the pinned profile so a profile/code mismatch is caught twice.
PATCH_PIN = {"index": 9298, "bytes": 306097616, "sha256":
             "70725f6624f947c3096066cc66a07fcd2440adf94137b79561ed2d67843f9f0e"}
SOURCE_REVISION = "66ba94e2b84c4092e4b9cc9d0dcc805313438f53"
# Version word of the pinned header (0x1xx: grf.rs parse_header uses the 0x200
# field layout for it). Only header fields are used; the table is not parsed.
PATCH_HEADER_VERSION = 0x102

PROFILE_SCHEMA = "ro-twelve-patch-payload-profile/1"
VECTORS_SCHEMA = "root-grf-body-oracle-vectors/1"
MANIFEST_SCHEMA = "ro-twelve-patch-payload-manifest/1"
COMPLETE_SCHEMA = "ro-twelve-patch-payload-complete/1"
FAILED_SCHEMA = "ro-twelve-patch-payload-failed/1"
PRODUCTION = "production"

MANIFEST = "payload-manifest.json"
COMPLETE = "payload-complete.json"
FAILED = "payload-failed.json"
TARGET_COUNT = 12
BODY_NAMES = tuple("target-%03d.body" % i for i in range(TARGET_COUNT))
HEADER_SIZE = 46

KIND_FILE = 0x01
KIND_MIXED = 0x02
KIND_HEADER = 0x04
# Primary-loader signatures by target kind; versions are observed only.
MAGIC = {"gat": b"GRAT", "gnd": b"GRGN", "rsw": b"GRSW"}

PATCH_STABLE = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_nlink")


class Refusal(Exception):
    """A path-free refusal code; never carries names, paths or bodies."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def sha256(data):
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Cipher. Literal tables transcribed from des.rs at 66ba94e2 (attribution: the
# RemoteClient port of the reference loader's des.ts). Bit numbering: position
# p (0..63) is byte p // 8, bit 0x80 >> (p % 8), i.e. MSB-first big-endian.

_IP = (58, 50, 42, 34, 26, 18, 10, 2, 60, 52, 44, 36, 28, 20, 12, 4,
       62, 54, 46, 38, 30, 22, 14, 6, 64, 56, 48, 40, 32, 24, 16, 8,
       57, 49, 41, 33, 25, 17, 9, 1, 59, 51, 43, 35, 27, 19, 11, 3,
       61, 53, 45, 37, 29, 21, 13, 5, 63, 55, 47, 39, 31, 23, 15, 7)
_FP = (40, 8, 48, 16, 56, 24, 64, 32, 39, 7, 47, 15, 55, 23, 63, 31,
       38, 6, 46, 14, 54, 22, 62, 30, 37, 5, 45, 13, 53, 21, 61, 29,
       36, 4, 44, 12, 52, 20, 60, 28, 35, 3, 43, 11, 51, 19, 59, 27,
       34, 2, 42, 10, 50, 18, 58, 26, 33, 1, 41, 9, 49, 17, 57, 25)
_TP = (16, 7, 20, 21, 29, 12, 28, 17, 1, 15, 23, 26, 5, 18, 31, 10,
       2, 8, 24, 14, 32, 27, 3, 9, 19, 13, 30, 6, 22, 11, 4, 25)
_SBOX = (
    bytes.fromhex(
        "ef0341fdd8741e4726effb22b3d8841e39aca76062c1cdba5c969059053b7a85"
        "40fd1ec8e78a8b21da43649f2d14b172f55bc8b69c3776ec39a0a305526e0fd9"),
    bytes.fromhex(
        "a7dd0d789e0be3956036364ff9605aa31124d287c85275ecbbc14cba24fe8f19"
        "da1366af49d090068c6afb91378d0d78bf4911f423e5ce3b55bca257e82274ce"),
    bytes.fromhex(
        "2ceac1bf4a241fc27947a27cb6d9681580565d0133fdf4aede30079be5839b68"
        "49b42e831fc2b57ca219d8e57c2f83daf76b90fec4015a9761a63d400b58e63d"),
    bytes.fromhex(
        "4dd1b20f28bde478f64a0f938b17d1a43aecc93593567ecb5520a0fe6c891762"
        "17624bb1b4ded187c9143c4a7ea8e27da09ff65c6a098df00fe35325953628cb"),
)
_SHUFFLE_SWAPS = bytes.fromhex("002b6c800168487760ffb9c0feeb")
_SHUFFLE_SOURCE = (3, 4, 6, 0, 1, 2, 5)


def _permutation_tables(table, width):
    """Byte-indexed lookup tables: out = OR of tab[k][byte k of input]."""
    nbytes = width // 8
    tabs = [[0] * 256 for _ in range(nbytes)]
    for out_pos, one_based in enumerate(table):
        src = one_based - 1
        k, bit = divmod(src, 8)
        out_mask = 1 << (len(table) - 1 - out_pos)
        for value in range(256):
            if value & (0x80 >> bit):
                tabs[k][value] |= out_mask
    return tuple(tuple(t) for t in tabs)


_IP_TABS = _permutation_tables(_IP, 64)
_FP_TABS = _permutation_tables(_FP, 64)
_TP_TABS = _permutation_tables(_TP, 32)


def _shuffle_table():
    out = bytearray(range(256))
    for a, b in zip(_SHUFFLE_SWAPS[0::2], _SHUFFLE_SWAPS[1::2]):
        out[a], out[b] = b, a
    return bytes(out)


_SHUFFLE_TABLE = _shuffle_table()


def _permute(value_bytes, tabs):
    acc = 0
    for k, tab in enumerate(tabs):
        acc |= tab[value_bytes[k]]
    return acc


def _round(right):
    """Mangled one-round F over the 32-bit right half; returns the XOR mask."""
    r = right.to_bytes(4, "big")
    # Six-bit expansion groups exactly as des.rs expansion(): 8 values.
    six = (
        ((r[3] << 5) | (r[0] >> 3)) & 0x3F,
        ((r[0] << 1) | (r[1] >> 7)) & 0x3F,
        ((r[0] << 5) | (r[1] >> 3)) & 0x3F,
        ((r[1] << 1) | (r[2] >> 7)) & 0x3F,
        ((r[1] << 5) | (r[2] >> 3)) & 0x3F,
        ((r[2] << 1) | (r[3] >> 7)) & 0x3F,
        ((r[2] << 5) | (r[3] >> 3)) & 0x3F,
        ((r[3] << 1) | (r[0] >> 7)) & 0x3F,
    )
    sub = bytes((_SBOX[i][six[2 * i]] & 0xF0) | (_SBOX[i][six[2 * i + 1]] & 0x0F)
                for i in range(4))
    return _permute(sub, _TP_TABS)


def transform_block(block):
    """The self-inverse block transform (IP, one F round on the left half, FP)."""
    if len(block) != 8:
        raise ValueError("block must be 8 bytes")
    v = _permute(block, _IP_TABS)
    left, right = v >> 32, v & 0xFFFFFFFF
    left ^= _round(right)
    return _permute(((left << 32) | right).to_bytes(8, "big"), _FP_TABS).to_bytes(8, "big")


def unshuffle_block(block):
    if len(block) != 8:
        raise ValueError("block must be 8 bytes")
    return bytes(block[s] for s in _SHUFFLE_SOURCE) + bytes((_SHUFFLE_TABLE[block[7]],))


def mixed_cycle(compressed_size):
    if type(compressed_size) is not int or compressed_size < 0:
        raise ValueError("compressed_size must be a non-negative int")
    digits = len(str(compressed_size))
    if digits < 3:
        return 1
    if digits < 5:
        return digits + 1
    if digits < 7:
        return digits + 9
    return digits + 15


def decrypt(buffer, kind, compressed_size):
    """Decrypt a whole aligned payload buffer; returns new bytes."""
    data = bytearray(buffer)
    blocks = len(data) // 8
    if kind & KIND_MIXED:
        cycle = mixed_cycle(compressed_size)
        nondes = -1
        for i in range(blocks):
            at = 8 * i
            if i < 20 or i % cycle == 0:
                data[at:at + 8] = transform_block(data[at:at + 8])
                continue
            nondes += 1
            if nondes and nondes % 7 == 0:
                data[at:at + 8] = unshuffle_block(data[at:at + 8])
    elif kind & KIND_HEADER:
        for i in range(min(20, blocks)):
            at = 8 * i
            data[at:at + 8] = transform_block(data[at:at + 8])
    return bytes(data)


def vector_input(length):
    """Input pattern of the authored cipher vectors: byte i = (73 * i + 19) mod 256."""
    return bytes((73 * i + 19) & 0xFF for i in range(length))


def check_vectors(vectors):
    """Run every authored literal answer; raise Refusal on any mismatch."""
    try:
        for row in vectors["fixed_block_vectors"]:
            if transform_block(bytes.fromhex(row["input_hex"])).hex() != row["output_hex"]:
                raise Refusal("vector-block-mismatch")
        for row in vectors["fixed_shuffle_vectors"]:
            if unshuffle_block(bytes.fromhex(row["input_hex"])).hex() != row["output_hex"]:
                raise Refusal("vector-shuffle-mismatch")
        rows = vectors["cipher_vectors"]
        if len(rows) != vectors["cipher_vector_count"] or not rows:
            raise Refusal("vector-count-mismatch")
        for row in rows:
            if mixed_cycle(row["compressed_size"]) != row["cycle"]:
                raise Refusal("vector-cycle-mismatch")
            out = decrypt(vector_input(row["length"]), row["kind"], row["compressed_size"])
            if sha256(out) != row["output_sha256"]:
                raise Refusal("vector-cipher-mismatch")
    except (KeyError, TypeError, ValueError):
        raise Refusal("vector-malformed")
    return len(rows)


# ---------------------------------------------------------------------------
# Strict framing.

def frame(decrypted, compressed_size, real_size):
    """Return (framing, decoded) under the strict validator policy."""
    if real_size == compressed_size:
        return "stored", decrypted[:real_size]
    stream = decrypted[:compressed_size]
    inflater = zlib.decompressobj()
    try:
        out = inflater.decompress(stream, real_size + 1)
    except zlib.error:
        raise Refusal("zlib-invalid-stream")
    if len(out) > real_size:
        raise Refusal("zlib-overlong")
    if inflater.unconsumed_tail:
        raise Refusal("zlib-unconsumed-tail")
    if not inflater.eof:
        raise Refusal("zlib-truncated")
    if inflater.unused_data:
        raise Refusal("zlib-trailing-data")
    if len(out) != real_size:
        raise Refusal("zlib-short")
    return "zlib", out


# ---------------------------------------------------------------------------
# Strict JSON and the fixed contract.

def _no_duplicates(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise Refusal("json-duplicate-key")
        out[k] = v
    return out


def _parse_json(data, code):
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=_no_duplicates,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except Refusal:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise Refusal(code)


def canonical(obj):
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("ascii")


def _is_int(v, low=0, high=None):
    return type(v) is int and v >= low and (high is None or v <= high)


def _is_hex(v, nbytes=None):
    if type(v) is not str or len(v) % 2 or (nbytes is not None and len(v) != 2 * nbytes):
        return False
    return all(c in "0123456789abcdef" for c in v)


def _keys(obj, keys, code):
    if type(obj) is not dict or set(obj) != set(keys):
        raise Refusal(code)


def _safe_relative(path):
    if type(path) is not str or not path or path.startswith("/") or "\\" in path:
        return False
    parts = path.split("/")
    return all(p not in ("", ".", "..") for p in parts) and "\0" not in path


PROFILE_KEYS = ("authored", "not_claimed", "patch", "schema", "source_pins",
                "source_revision", "strict_policy", "targets", "task", "work_limits")
PATCH_KEYS = ("bytes", "file", "header_bytes", "header_sha256", "index", "record_count",
              "sha256", "table_start")
TARGET_KEYS = ("compressed_size", "effective_kind", "expected_magic_hex", "kind_label",
               "length_aligned", "metadata_filter", "name_hex", "ordinal", "output_file",
               "payload_offset_field", "physical_body_range", "real_size")
LIMIT_KEYS = ("expected_aligned_bytes_total", "expected_decoded_bytes_total",
              "max_aligned_bytes_per_target", "max_decoded_bytes_per_target",
              "max_decoded_bytes_total", "max_output_bytes", "read_chunk_bytes")
POLICY_KEYS = ("decrypt_span", "magic", "not_native", "padding", "stored", "zlib")


def validate_profile(profile, vectors_pin):
    """Typed check of the whole profile; returns it unchanged."""
    _keys(profile, PROFILE_KEYS, "profile-keys")
    if profile["schema"] != PROFILE_SCHEMA or profile["task"] != TASK:
        raise Refusal("profile-schema")
    authored = profile["authored"]
    _keys(authored, ("bytes", "path", "sha256"), "profile-authored")
    if authored != {"bytes": vectors_pin["bytes"], "path": VECTORS_PATH,
                    "sha256": vectors_pin["sha256"]}:
        raise Refusal("profile-authored")
    if not _is_hex(profile["source_revision"], 20):
        raise Refusal("profile-revision")
    nc = profile["not_claimed"]
    if type(nc) is not list or not nc or not all(type(x) is str and x for x in nc):
        raise Refusal("profile-not-claimed")
    policy = profile["strict_policy"]
    _keys(policy, POLICY_KEYS, "profile-policy")
    if not all(type(v) is str and v for v in policy.values()):
        raise Refusal("profile-policy")

    patch = profile["patch"]
    _keys(patch, PATCH_KEYS, "profile-patch")
    if not (_is_int(patch["index"], 1) and _is_int(patch["bytes"], HEADER_SIZE + 1)
            and patch["header_bytes"] == HEADER_SIZE and _is_hex(patch["sha256"], 32)
            and _is_hex(patch["header_sha256"], 32) and _is_int(patch["record_count"], 1)
            and _is_int(patch["table_start"], HEADER_SIZE + 1)
            and patch["table_start"] < patch["bytes"]
            and type(patch["file"]) is str and _safe_relative(patch["file"])
            and "/" not in patch["file"]):
        raise Refusal("profile-patch")

    pins = profile["source_pins"]
    if type(pins) is not list or len(pins) != 5:
        raise Refusal("profile-sources")
    seen = set()
    for pin in pins:
        _keys(pin, ("bytes", "path", "sha256"), "profile-sources")
        if not (_safe_relative(pin["path"]) and _is_int(pin["bytes"], 1)
                and _is_hex(pin["sha256"], 32)) or pin["path"] in seen:
            raise Refusal("profile-sources")
        seen.add(pin["path"])

    limits = profile["work_limits"]
    _keys(limits, LIMIT_KEYS, "profile-limits")
    if not all(_is_int(v, 1) for v in limits.values()):
        raise Refusal("profile-limits")
    if (limits["max_aligned_bytes_per_target"] > 1 << 28
            or limits["max_decoded_bytes_per_target"] > 1 << 28
            or limits["max_decoded_bytes_total"] > 1 << 30
            or limits["max_output_bytes"] > 1 << 30
            or limits["read_chunk_bytes"] > 1 << 24
            or limits["expected_decoded_bytes_total"] > limits["max_decoded_bytes_total"]
            or limits["expected_decoded_bytes_total"] > limits["max_output_bytes"]):
        raise Refusal("profile-limits")

    targets = profile["targets"]
    if type(targets) is not list or len(targets) != TARGET_COUNT:
        raise Refusal("profile-targets")
    aligned_total = decoded_total = 0
    last_end = HEADER_SIZE
    ordinals = set()
    for i, t in enumerate(targets):
        _keys(t, TARGET_KEYS, "profile-target-keys")
        label = t["kind_label"]
        ints_ok = (_is_int(t["compressed_size"], 1, 0xFFFFFFFF)
                   and _is_int(t["length_aligned"], 1, 0xFFFFFFFF)
                   and _is_int(t["real_size"], 1, 0xFFFFFFFF)
                   and _is_int(t["payload_offset_field"], 0, 0xFFFFFFFF)
                   and _is_int(t["ordinal"], 0, patch["record_count"] - 1)
                   and _is_int(t["effective_kind"], 0, 0xFF))
        if not ints_ok or t["output_file"] != BODY_NAMES[i] or t["metadata_filter"] != "eligible":
            raise Refusal("profile-target-fields")
        if t["ordinal"] in ordinals:
            raise Refusal("profile-target-ordinal")
        ordinals.add(t["ordinal"])
        if label not in MAGIC or t["expected_magic_hex"] != MAGIC[label].hex():
            raise Refusal("profile-target-magic")
        if not _is_hex(t["name_hex"]) or not bytes.fromhex(t["name_hex"]).lower().endswith(
                b"." + label.encode("ascii")):
            raise Refusal("profile-target-name")
        kind = t["effective_kind"]
        if not kind & KIND_FILE or kind & ~(KIND_FILE | KIND_MIXED | KIND_HEADER):
            raise Refusal("profile-target-kind")
        if t["compressed_size"] > t["length_aligned"]:
            raise Refusal("profile-target-sizes")
        if (t["length_aligned"] > limits["max_aligned_bytes_per_target"]
                or t["real_size"] > limits["max_decoded_bytes_per_target"]):
            raise Refusal("profile-target-budget")
        start = t["payload_offset_field"] + HEADER_SIZE
        end = start + t["length_aligned"]
        rng = t["physical_body_range"]
        if (type(rng) is not list or len(rng) != 2 or not all(_is_int(x) for x in rng)
                or rng != [start, end]):
            raise Refusal("profile-target-range")
        if start < last_end or end > patch["table_start"]:
            raise Refusal("profile-target-range")
        last_end = end
        aligned_total += t["length_aligned"]
        decoded_total += t["real_size"]
    if (aligned_total != limits["expected_aligned_bytes_total"]
            or decoded_total != limits["expected_decoded_bytes_total"]):
        raise Refusal("profile-totals")
    return profile


def validate_vectors(vectors):
    _keys(vectors, ("cipher_vector_count", "cipher_vectors", "fixed_block_vectors",
                    "fixed_shuffle_vectors", "limits", "oracle_limits", "primary_sources",
                    "schema", "source_revision"), "vectors-keys")
    if vectors["schema"] != VECTORS_SCHEMA:
        raise Refusal("vectors-schema")
    return vectors


class Contract:
    """Fixed inputs a run is bound to. Only _production_contract() is public-facing."""

    def __init__(self, kind, repo, profile_bytes, vectors_bytes, profile_pin, vectors_pin,
                 patch_pin, source_revision, header_version):
        self.kind = kind
        self.header_version = header_version
        self.repo = Path(repo)
        self.profile_bytes = profile_bytes
        self.vectors_bytes = vectors_bytes
        self.profile_pin = dict(profile_pin)
        self.vectors_pin = dict(vectors_pin)
        for data, pin, code in ((profile_bytes, profile_pin, "profile-pin"),
                                (vectors_bytes, vectors_pin, "vectors-pin")):
            if len(data) != pin["bytes"] or sha256(data) != pin["sha256"]:
                raise Refusal(code)
        self.vectors = validate_vectors(_parse_json(vectors_bytes, "vectors-json"))
        self.profile = validate_profile(_parse_json(profile_bytes, "profile-json"), vectors_pin)
        patch = self.profile["patch"]
        if (patch["index"] != patch_pin["index"] or patch["bytes"] != patch_pin["bytes"]
                or patch["sha256"] != patch_pin["sha256"]
                or self.profile["source_revision"] != source_revision
                or self.vectors["source_revision"] != source_revision):
            raise Refusal("profile-pin-cross-check")
        vector_sources = self.vectors["primary_sources"]
        if type(vector_sources) is not list or not all(
                p in self.profile["source_pins"] for p in vector_sources):
            raise Refusal("vectors-sources")
        self.vector_count = check_vectors(self.vectors)

    def generator_pin(self):
        data = _read_regular(self.repo / GENERATOR_PATH, "generator-unreadable")
        return {"bytes": len(data), "path": GENERATOR_PATH, "sha256": sha256(data)}

    def recheck_checkout(self):
        for rel, pin, code in ((PROFILE_PATH, self.profile_pin, "profile-drift"),
                               (VECTORS_PATH, self.vectors_pin, "vectors-drift")):
            data = _read_regular(self.repo / rel, code)
            if len(data) != pin["bytes"] or sha256(data) != pin["sha256"]:
                raise Refusal(code)


def _read_regular(path, code):
    try:
        fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    except OSError:
        raise Refusal(code)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise Refusal(code)
        return _read_all(fd, st.st_size, code)
    finally:
        os.close(fd)


def _read_all(fd, size, code):
    chunks = []
    remaining = size
    offset = 0
    while remaining:
        try:
            chunk = os.pread(fd, min(remaining, 1 << 20), offset)
        except OSError:
            raise Refusal(code)
        if not chunk:
            raise Refusal(code)
        chunks.append(chunk)
        offset += len(chunk)
        remaining -= len(chunk)
    try:
        if os.pread(fd, 1, offset):
            raise Refusal(code)
    except OSError:
        raise Refusal(code)
    return b"".join(chunks)


def _production_contract():
    repo = REPO
    profile = _read_regular(repo / PROFILE_PATH, "profile-unreadable")
    vectors = _read_regular(repo / VECTORS_PATH, "vectors-unreadable")
    return Contract(PRODUCTION, repo, profile, vectors, PROFILE_PIN, VECTORS_PIN,
                    PATCH_PIN, SOURCE_REVISION, PATCH_HEADER_VERSION)


# ---------------------------------------------------------------------------
# Inputs.

def _open_source(root_fd, rel):
    """Open one fixed relative path below SOURCE_ROOT without following links."""
    parts = rel.split("/")
    fds = []
    try:
        cur = root_fd
        for part in parts[:-1]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                          dir_fd=cur)
            fds.append(nxt)
            cur = nxt
        return os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                       dir_fd=cur)
    finally:
        for fd in fds:
            os.close(fd)


def check_sources(source_root, pins):
    """Hash exactly the five pinned files; returns their pins as recorded."""
    try:
        root_fd = os.open(str(source_root), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                          | os.O_CLOEXEC)
    except OSError:
        raise Refusal("source-root")
    try:
        for pin in pins:
            try:
                fd = _open_source(root_fd, pin["path"])
            except OSError:
                raise Refusal("source-unreadable")
            try:
                st = os.fstat(fd)
                if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
                    raise Refusal("source-not-regular")
                if st.st_size != pin["bytes"]:
                    raise Refusal("source-pin")
                if sha256(_read_all(fd, st.st_size, "source-unreadable")) != pin["sha256"]:
                    raise Refusal("source-pin")
            finally:
                os.close(fd)
    finally:
        os.close(root_fd)
    return [dict(p) for p in pins]


def _stable(st):
    return tuple(getattr(st, k) for k in PATCH_STABLE)


class Patch:
    """The single admitted GPF, read only through one retained descriptor."""

    def __init__(self, path, pin, targets, chunk):
        self.path = str(path)
        self.pin = pin
        self.fd = None
        try:
            self.fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
                              | os.O_CLOEXEC)
        except OSError:
            raise Refusal("patch-unopenable")
        st = os.fstat(self.fd)
        if not stat.S_ISREG(st.st_mode):
            raise Refusal("patch-not-regular")
        if st.st_nlink != 1:
            raise Refusal("patch-hardlinked")
        if st.st_size != pin["bytes"]:
            raise Refusal("patch-size")
        self.identity = _stable(st)
        self._check_path()
        self.range_hashes = self._hash_all(targets, chunk)
        self.recheck()

    def _check_path(self):
        try:
            lst = os.lstat(self.path)
        except OSError:
            raise Refusal("patch-path-drift")
        if (not stat.S_ISREG(lst.st_mode) or (lst.st_dev, lst.st_ino)
                != (self.identity[0], self.identity[1])):
            raise Refusal("patch-path-drift")

    def recheck(self):
        if self.fd is None or _stable(os.fstat(self.fd)) != self.identity:
            raise Refusal("patch-drift")
        self._check_path()

    def _hash_all(self, targets, chunk):
        """Full SHA-256 in one pass, also hashing each admitted range as streamed."""
        full = hashlib.sha256()
        header = b""
        ranges = [(t["physical_body_range"][0], t["physical_body_range"][1], hashlib.sha256())
                  for t in targets]
        offset = 0
        size = self.pin["bytes"]
        while offset < size:
            try:
                data = os.pread(self.fd, min(chunk, size - offset), offset)
            except OSError:
                raise Refusal("patch-read")
            if not data:
                raise Refusal("patch-short")
            end = offset + len(data)
            full.update(data)
            if offset < HEADER_SIZE:
                header += data[:HEADER_SIZE - offset]
            for lo, hi, h in ranges:
                if lo < end and hi > offset:
                    h.update(data[max(lo, offset) - offset:min(hi, end) - offset])
            offset = end
        if os.pread(self.fd, 1, offset):
            raise Refusal("patch-size")
        if full.hexdigest() != self.pin["sha256"]:
            raise Refusal("patch-sha256")
        self.header = header
        return [h.hexdigest() for _, _, h in ranges]

    def read(self, offset, length):
        out = bytearray()
        while len(out) < length:
            try:
                data = os.pread(self.fd, length - len(out), offset + len(out))
            except OSError:
                raise Refusal("patch-read")
            if not data:
                raise Refusal("patch-short")
            out += data
        return bytes(out)

    def close(self):
        if self.fd is not None:
            fd, self.fd = self.fd, None
            os.close(fd)


def check_header(header, patch_profile, expected_version):
    """Exact header pin plus a cross-check of the table boundary and record count."""
    if len(header) != HEADER_SIZE or sha256(header) != patch_profile["header_sha256"]:
        raise Refusal("patch-header-pin")
    sig = header[:15].split(b"\0", 1)[0]
    version = int.from_bytes(header[42:46], "little")
    offset = int.from_bytes(header[30:34], "little")
    seed = int.from_bytes(header[34:38], "little")
    count = int.from_bytes(header[38:42], "little") - seed - 7
    if (sig not in (b"Master of Magic", b"Event Horizon") or version != expected_version
            or not (version >> 8 == 0x01 or version == 0x200)
            or offset + HEADER_SIZE != patch_profile["table_start"]
            or count != patch_profile["record_count"]):
        raise Refusal("patch-header-fields")
    return "%08x" % version


# ---------------------------------------------------------------------------
# Output publication.

class FileOps:
    """Thin checked wrappers over os.* so tests can inject write/flush/close faults."""

    def write(self, fd, data):
        return os.write(fd, data)

    def fsync(self, fd):
        os.fsync(fd)

    def close(self, fd):
        os.close(fd)

    def read_back(self, dir_fd, name):
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=dir_fd)
        try:
            st = os.fstat(fd)
            return st, _read_all(fd, st.st_size, "output-readback")
        finally:
            os.close(fd)


class Output:
    def __init__(self, path, ops):
        self.path = str(path)
        self.ops = ops
        self.created = {}
        self.dir_fd = None
        self.identity = None
        parent = os.path.dirname(os.path.abspath(self.path)) or "/"
        try:
            pst = os.stat(parent)
        except OSError:
            raise Refusal("output-parent")
        if not stat.S_ISDIR(pst.st_mode):
            raise Refusal("output-parent")
        if os.path.lexists(self.path):
            raise Refusal("output-exists")

    def create(self):
        try:
            os.mkdir(self.path, 0o700)
        except OSError:
            raise Refusal("output-exists")
        try:
            fd = os.open(self.path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        except OSError:
            raise Refusal("output-foreign")
        self.dir_fd = fd
        os.fchmod(fd, 0o700)
        st = os.fstat(fd)
        self.identity = (st.st_dev, st.st_ino)
        self.check_dir()

    def check_dir(self):
        try:
            lst = os.lstat(self.path)
        except OSError:
            raise Refusal("output-foreign")
        if (not stat.S_ISDIR(lst.st_mode) or (lst.st_dev, lst.st_ino) != self.identity
                or stat.S_IMODE(lst.st_mode) != 0o700 or lst.st_uid != os.getuid()):
            raise Refusal("output-foreign")
        fst = os.fstat(self.dir_fd)
        if (fst.st_dev, fst.st_ino) != self.identity:
            raise Refusal("output-foreign")

    def publish(self, name, data):
        try:
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
                         | os.O_CLOEXEC, 0o600, dir_fd=self.dir_fd)
        except OSError:
            raise Refusal("output-create")
        st = os.fstat(fd)
        self.created[name] = (st.st_dev, st.st_ino)
        try:
            os.fchmod(fd, 0o600)
            view = memoryview(data)
            done = 0
            while done < len(data):
                n = self.ops.write(fd, view[done:done + (1 << 20)])
                if type(n) is not int or n <= 0 or n > len(data) - done:
                    raise Refusal("output-write")
                done += n
            self.ops.fsync(fd)
        except Refusal:
            os.close(fd)
            raise
        except OSError:
            os.close(fd)
            raise Refusal("output-flush")
        try:
            self.ops.close(fd)
        except OSError:
            raise Refusal("output-close")
        self.check_file(name, data)

    def check_file(self, name, data):
        try:
            st, back = self.ops.read_back(self.dir_fd, name)
        except (OSError, Refusal):
            raise Refusal("output-readback")
        if ((st.st_dev, st.st_ino) != self.created.get(name) or not stat.S_ISREG(st.st_mode)
                or st.st_nlink != 1 or stat.S_IMODE(st.st_mode) != 0o600
                or back != data):
            raise Refusal("output-readback")

    def check_set(self, names):
        self.check_dir()
        if set(os.listdir(self.dir_fd)) != set(names):
            raise Refusal("output-set")
        for name in names:
            st = os.stat(name, dir_fd=self.dir_fd, follow_symlinks=False)
            if ((st.st_dev, st.st_ino) != self.created.get(name) or st.st_nlink != 1
                    or stat.S_IMODE(st.st_mode) != 0o600 or not stat.S_ISREG(st.st_mode)):
                raise Refusal("output-identity")

    def sync_dir(self):
        try:
            os.fsync(self.dir_fd)
        except OSError:
            raise Refusal("output-flush")

    def fail(self):
        """Invalidate an owned completion and publish a failure marker if safe."""
        if self.dir_fd is None:
            return False
        try:
            self.check_dir()
        except (Refusal, OSError):
            return False
        try:
            st = os.stat(COMPLETE, dir_fd=self.dir_fd, follow_symlinks=False)
            if (st.st_dev, st.st_ino) == self.created.get(COMPLETE):
                os.unlink(COMPLETE, dir_fd=self.dir_fd)
        except FileNotFoundError:
            pass
        except OSError:
            return False
        return True

    def close(self):
        if self.dir_fd is not None:
            fd, self.dir_fd = self.dir_fd, None
            os.close(fd)


# ---------------------------------------------------------------------------
# Producer.

def _decode_targets(patch, profile, limits):
    rows = []
    bodies = []
    aligned_read = decoded_total = 0
    for t, streamed in zip(profile["targets"], patch.range_hashes):
        start, end = t["physical_body_range"]
        aligned, compressed, real = t["length_aligned"], t["compressed_size"], t["real_size"]
        if not (HEADER_SIZE <= start < end <= profile["patch"]["table_start"]
                and end - start == aligned and compressed <= aligned):
            raise Refusal("target-range")
        if (aligned_read + aligned > limits["expected_aligned_bytes_total"]
                or decoded_total + real > limits["max_decoded_bytes_total"]):
            raise Refusal("budget-cumulative")
        raw = patch.read(start, aligned)
        aligned_read += aligned
        if sha256(raw) != streamed:
            raise Refusal("patch-range-drift")
        kind = t["effective_kind"]
        dec = decrypt(raw, kind, compressed)
        framing, body = frame(dec, compressed, real)
        if len(body) != real:
            raise Refusal("decoded-size")
        decoded_total += real
        if body[:4] != bytes.fromhex(t["expected_magic_hex"]):
            raise Refusal("decoded-magic")
        enc = "mixed" if kind & KIND_MIXED else "header" if kind & KIND_HEADER else "none"
        row = dict(t)
        row.update({
            "compressed_sha256": sha256(dec[:compressed]),
            "cycle": mixed_cycle(compressed) if enc == "mixed" else None,
            "decoded_bytes": real,
            "decoded_sha256": sha256(body),
            "decrypted_padding_sha256": sha256(dec[compressed:]),
            "decrypted_range_sha256": sha256(dec),
            "encryption": enc,
            "framing": framing,
            "magic_hex": body[:4].hex(),
            "padding_bytes": aligned - compressed,
            "raw_padding_sha256": sha256(raw[compressed:]),
            "raw_range_sha256": streamed,
            "version_prefix_hex": body[4:6].hex(),
        })
        rows.append(row)
        bodies.append(body)
    return rows, bodies, aligned_read, decoded_total


def build_manifest(contract, generator, sources, header_version, rows, aligned_read,
                   decoded_total):
    profile = contract.profile
    patch = dict(profile["patch"])
    patch["header_version_hex"] = header_version
    return {
        "contract_kind": contract.kind,
        "generator": dict(generator, version=VERSION),
        "not_claimed": list(profile["not_claimed"]),
        "patch": patch,
        "profile": {"bytes": contract.profile_pin["bytes"], "path": PROFILE_PATH,
                    "schema": profile["schema"], "sha256": contract.profile_pin["sha256"]},
        "schema": MANIFEST_SCHEMA,
        "source_revision": profile["source_revision"],
        "sources": sources,
        "strict_policy": dict(profile["strict_policy"]),
        "targets": rows,
        "task": TASK,
        "usage": {"aligned_bytes_read": aligned_read, "decoded_bytes": decoded_total,
                  "output_body_bytes": decoded_total, "patch_bytes_hashed": profile["patch"]["bytes"],
                  "target_count": len(rows)},
        "vectors": {"bytes": contract.vectors_pin["bytes"], "cipher_vector_count":
                    contract.vector_count, "path": VECTORS_PATH, "schema": VECTORS_SCHEMA,
                    "self_check": "passed", "sha256": contract.vectors_pin["sha256"]},
        "work_limits": dict(profile["work_limits"]),
    }


def _run(source_root, patch_path, output_path, contract, ops=None, consumer=None):
    """Producer body. Returns the manifest SHA on success; raises Refusal."""
    out = Output(output_path, ops or FileOps())
    patch = None
    try:
        profile = contract.profile
        limits = profile["work_limits"]
        generator = contract.generator_pin()
        sources = check_sources(source_root, profile["source_pins"])
        patch = Patch(patch_path, profile["patch"], profile["targets"], limits["read_chunk_bytes"])
        header_version = check_header(patch.header, profile["patch"], contract.header_version)
        out.create()
        rows, bodies, aligned_read, decoded_total = _decode_targets(patch, profile, limits)
        if decoded_total > limits["max_output_bytes"]:
            raise Refusal("budget-output")
        for row, body in zip(rows, bodies):
            out.publish(row["output_file"], body)
        del bodies
        manifest = canonical(build_manifest(contract, generator, sources, header_version, rows,
                                            aligned_read, decoded_total))
        out.publish(MANIFEST, manifest)
        out.sync_dir()
        # Final input rechecks, then release the patch before completion.
        patch.recheck()
        patch.close()
        check_sources(source_root, profile["source_pins"])
        contract.recheck_checkout()
        if contract.generator_pin() != generator:
            raise Refusal("generator-drift")
        out.check_set(BODY_NAMES + (MANIFEST,))
        marker = canonical({"manifest_bytes": len(manifest), "manifest_sha256": sha256(manifest),
                            "schema": COMPLETE_SCHEMA, "status": "complete",
                            "target_count": TARGET_COUNT})
        out.publish(COMPLETE, marker)
        out.sync_dir()
        out.check_set(BODY_NAMES + (MANIFEST, COMPLETE))
        (consumer or (lambda path: _verify_payloads(path, contract)))(output_path)
        out.check_set(BODY_NAMES + (MANIFEST, COMPLETE))
        return sha256(manifest), decoded_total
    except BaseException as exc:
        code = exc.code if isinstance(exc, Refusal) else "internal-error"
        if patch is not None:
            try:
                patch.close()
            except OSError:
                pass
        if out.fail():
            try:
                out.publish(FAILED, canonical({"reason": code, "schema": FAILED_SCHEMA,
                                               "status": "failed"}))
                out.sync_dir()
            except (Refusal, OSError):
                pass
        if isinstance(exc, Refusal):
            raise
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        raise Refusal(code) from exc
    finally:
        out.close()


# ---------------------------------------------------------------------------
# Read-only consumer.

ROW_KEYS = TARGET_KEYS + ("compressed_sha256", "cycle", "decoded_bytes", "decoded_sha256",
                          "decrypted_padding_sha256", "decrypted_range_sha256", "encryption",
                          "framing", "magic_hex", "padding_bytes", "raw_padding_sha256",
                          "raw_range_sha256", "version_prefix_hex")
HASH_FIELDS = ("compressed_sha256", "decoded_sha256", "decrypted_padding_sha256",
               "decrypted_range_sha256", "raw_padding_sha256", "raw_range_sha256")


def _consumer_read(dir_fd, name):
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                     dir_fd=dir_fd)
    except OSError:
        raise Refusal("consumer-unreadable")
    try:
        st = os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_uid != os.getuid()
                or stat.S_IMODE(st.st_mode) != 0o600):
            raise Refusal("consumer-file-privacy")
        return _read_all(fd, st.st_size, "consumer-unreadable")
    finally:
        os.close(fd)


def _check_row(expected, row):
    _keys(row, ROW_KEYS, "consumer-row-keys")
    for k in TARGET_KEYS:
        if row[k] != expected[k] or type(row[k]) is not type(expected[k]):
            raise Refusal("consumer-row-contract")
    if not all(_is_hex(row[k], 32) for k in HASH_FIELDS):
        raise Refusal("consumer-row-hash")
    kind = row["effective_kind"]
    enc = "mixed" if kind & KIND_MIXED else "header" if kind & KIND_HEADER else "none"
    cycle = mixed_cycle(row["compressed_size"]) if enc == "mixed" else None
    framing = "stored" if row["real_size"] == row["compressed_size"] else "zlib"
    if (row["encryption"] != enc or row["cycle"] != cycle or type(row["cycle"]) is not type(cycle)
            or row["framing"] != framing or row["decoded_bytes"] != row["real_size"]
            or type(row["decoded_bytes"]) is not int
            or row["padding_bytes"] != row["length_aligned"] - row["compressed_size"]
            or type(row["padding_bytes"]) is not int
            or row["magic_hex"] != row["expected_magic_hex"]
            or not _is_hex(row["version_prefix_hex"], 2)):
        raise Refusal("consumer-row-derived")


def _verify_payloads(output, contract):
    try:
        dir_fd = os.open(str(output), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError:
        raise Refusal("consumer-output")
    try:
        st = os.fstat(dir_fd)
        if stat.S_IMODE(st.st_mode) != 0o700 or st.st_uid != os.getuid():
            raise Refusal("consumer-output-privacy")
        names = set(os.listdir(dir_fd))
        if FAILED in names:
            raise Refusal("consumer-failed-marker")
        if names != set(BODY_NAMES + (MANIFEST, COMPLETE)):
            raise Refusal("consumer-file-set")
        marker_bytes = _consumer_read(dir_fd, COMPLETE)
        manifest_bytes = _consumer_read(dir_fd, MANIFEST)
        marker = _parse_json(marker_bytes, "consumer-marker-json")
        if canonical(marker) != marker_bytes or marker != {
                "manifest_bytes": len(manifest_bytes), "manifest_sha256": sha256(manifest_bytes),
                "schema": COMPLETE_SCHEMA, "status": "complete", "target_count": TARGET_COUNT}:
            raise Refusal("consumer-marker")
        manifest = _parse_json(manifest_bytes, "consumer-manifest-json")
        if canonical(manifest) != manifest_bytes:
            raise Refusal("consumer-manifest-canonical")
        _keys(manifest, ("contract_kind", "generator", "not_claimed", "patch", "profile",
                         "schema", "source_revision", "sources", "strict_policy", "targets",
                         "task", "usage", "vectors", "work_limits"), "consumer-manifest-keys")
        profile = contract.profile
        fixed = build_manifest(contract, contract.generator_pin(),
                               [dict(p) for p in profile["source_pins"]],
                               "%08x" % contract.header_version, [], 0, 0)
        for key in ("contract_kind", "generator", "not_claimed", "patch", "profile", "schema",
                    "source_revision", "sources", "strict_policy", "task", "vectors",
                    "work_limits"):
            if manifest[key] != fixed[key]:
                raise Refusal("consumer-contract")
        rows = manifest["targets"]
        if type(rows) is not list or len(rows) != TARGET_COUNT:
            raise Refusal("consumer-targets")
        total = 0
        for expected, row in zip(profile["targets"], rows):
            _check_row(expected, row)
            body = _consumer_read(dir_fd, row["output_file"])
            if (len(body) != row["decoded_bytes"] or sha256(body) != row["decoded_sha256"]
                    or body[:4].hex() != row["magic_hex"]
                    or body[4:6].hex() != row["version_prefix_hex"]):
                raise Refusal("consumer-body")
            total += len(body)
        limits = profile["work_limits"]
        if manifest["usage"] != {"aligned_bytes_read": limits["expected_aligned_bytes_total"],
                                 "decoded_bytes": total, "output_body_bytes": total,
                                 "patch_bytes_hashed": profile["patch"]["bytes"],
                                 "target_count": TARGET_COUNT} \
                or total != limits["expected_decoded_bytes_total"]:
            raise Refusal("consumer-usage")
        if set(os.listdir(dir_fd)) != names or (os.fstat(dir_fd).st_dev, os.fstat(dir_fd).st_ino) \
                != (st.st_dev, st.st_ino):
            raise Refusal("consumer-drift")
        return {"targets": TARGET_COUNT, "decoded_bytes": total,
                "manifest_sha256": sha256(manifest_bytes)}
    finally:
        os.close(dir_fd)


def verify_payloads(output):
    """Read-only production consumer; raises Refusal unless the output is complete."""
    return _verify_payloads(output, _production_contract())


# ---------------------------------------------------------------------------

def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 3:
        sys.stderr.write(json.dumps({"status": "usage", "reason": "expected 3 arguments"}) + "\n")
        return 64
    try:
        contract = _production_contract()
        manifest_sha, decoded = _run(argv[0], argv[1], argv[2], contract)
    except Refusal as exc:
        sys.stderr.write(json.dumps({"status": "refused", "reason": exc.code}) + "\n")
        return 2
    sys.stdout.write(json.dumps({"status": "complete", "targets": TARGET_COUNT,
                                 "decoded_bytes": decoded,
                                 "manifest_sha256": manifest_sha}) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
