#!/usr/bin/env python3
"""Catalog every raw GRF file-table record of the three pinned client archives.

Inputs are the pinned small input directory (exactly DATA.INI and
archive-input-manifest.json, both hash-pinned), the acquired archive root and a
fresh private output directory. The ordered logical archive basenames come from
the pinned input manifest (event.grf -> data0.grf -> data.grf); DATA.INI is only
hash-verified and never parsed, echoed or copied.

Each archive is opened through a no-follow descriptor, size-checked, and then
streamed once: the same pass computes the full SHA-256 and captures the header
and the file-table bytes that are then parsed. Identity (device, inode, size,
mtime, ctime) is compared before and after, and the path must still name the
same regular file. Payload bytes pass through the full-archive hash; they are
never interpreted, extracted, decrypted or decompressed.

The header, table and record rules follow RemoteClient src/grf.rs and the
one-round block transform of src/des.rs at the pinned revision (rules below).
Checks the source itself performs, including surfaced decompression errors and
decoded-size mismatch, are reported as source rejections. Additional complete
zlib framing/no-trailing and work limits are validator policies; source-accepted
variants this child does not implement are refused as unsupported. Failures
remove only verified owned completion files; cleanup failures or foreign
replacements are diagnosed, and the output must be treated as failed.

Output is one JSONL file of raw records per archive in archive/table order, a
manifest and a hash-binding completion record written last. Status complete
means the bounded raw catalog was produced safely; it says nothing about human
filename spelling, key precedence, payload readability, maps or playability.
Standard library only. Output directories are never overwritten.
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

VERSION = "1.0.1"
OUTPUT_MANIFEST = "catalog-manifest.json"
OUTPUT_COMPLETE = "catalog-complete.json"
OUTPUT_FAILED = "catalog-failed.json"
RECORDS_SUFFIX = ".records.jsonl"

INPUT_INI = "DATA.INI"
INPUT_MANIFEST = "archive-input-manifest.json"
INPUT_PINS = {
    INPUT_INI: {"bytes": 453, "sha256":
                "3945c65691a73be5df7e1e46c6125cf37ded6430bf273ec657af0fa368e7912e"},
    INPUT_MANIFEST: {"bytes": 2358, "sha256":
                     "850d833db0795b7fd10694b0cdf80b2dcc813e2669c462d68956295386755e7d"},
}
ARCHIVE_PINS = [
    {"file": "event.grf", "bytes": 5833135, "sha256":
     "7fff4e0eececd10df9a9c4f83b70d78dc4dbb99c5ece64b117df7db8a2f85575"},
    {"file": "data0.grf", "bytes": 2123919641, "sha256":
     "913402ace1d3c67818b4f070650a07eb157a6d62df9e394d596d59b4c7e6678a"},
    {"file": "data.grf", "bytes": 2043560050, "sha256":
     "1c7d68f70714937abbd3741a6b3aea34a7ed9da63428941d5df453efacd1c0ad"},
]

SOURCE = {
    "repository": "RemoteClient",
    "revision": "66ba94e2b84c4092e4b9cc9d0dcc805313438f53",
    "files": {
        "src/grf.rs": "4646514140bc7688bbc91e0bac7d1ee9a83aab5e1e17df20c1eb30668bd5edf5",
        "src/des.rs": "8f0189340eab708993a493ff7300d08e0151a3c8c539a046656f3e350e01856f",
        "src/encoding.rs": "0014c18c2ab7211b68b8dff84c66b5bbd0aa3bb68593bca2bd5e46b28973c9ad",
    },
    "rules": {
        "constants": "grf.rs:17-48 HEADER_SIZE 46, signatures 'Master of Magic'/'Event "
                     "Horizon', table header 8, type bits 1/2/4, biases 715/37579, legacy "
                     "entry data 17, MAX_FILE_UNCOMPRESSED 256MiB, MAX_ENTRIES 500000, "
                     "MAX_FILE_TABLE 512MiB",
        "header": "grf.rs:167-239 bytes[0..15] up to first NUL as Latin-1 must equal a "
                  "signature; version u32@42; 0x1xx and 0x200: offset u32@30+46, count "
                  "max(u32@38-u32@34-7,0); other than 0x200/0x300 unsupported; 0x300: "
                  "high u32@34 >> 8 != 0 -> 0x200 layout and version, else offset "
                  "(high<<32)+low+46, count u32@38",
        "open": "grf.rs:468-557 count > MAX_ENTRIES rejected; 0x300 skips 4 bytes before "
                "the table; legacy table is table_pos..EOF (past EOF, empty, >512MiB "
                "rejected); modern table header compressed/real u32 (zero, real >512MiB, "
                "past EOF rejected), zlib read_to_end, size mismatch rejected",
        "modern_records": "grf.rs:266-313 per declared record: NUL-terminated name, then "
                          "compressed/aligned/real u32, kind u8, offset u32 (0x200) or "
                          "u64 (0x300); end of data or short entry data rejected; "
                          "leftover bytes not checked",
        "kind0_promotion": "grf.rs:322-327 kind 0 with real_size > 0 and compressed == "
                           "real becomes kind 1",
        "legacy_records": "grf.rs:386-455 full u32 block length -> metadata at p+4+len "
                          "(+17 must fit); name length = low byte saturating_sub 6; name "
                          "at p+6 must end by metadata; name runs to first NUL or the whole "
                          "derived length; compressed = u32 - real - 715, aligned = u32 - "
                          "37579 (signed); underflow clears the file bit and clamps to 0; "
                          "else file entries get mixed (2) or header (4) encryption by "
                          "suffix",
        "legacy_name_blocks": "grf.rs:334-344 for each 8-byte block starting before the "
                              "name length and fitting before the metadata: rotate every "
                              "byte by 4 bits, then des::decode_header(block, 8)",
        "encryption_suffix": "grf.rs:351-366 last '.' to end, ASCII case-insensitive "
                             ".gnd/.gat/.act/.str -> header; otherwise or no dot -> mixed",
        "block_transform": "des.rs:100-179,251-256 IP, one round (expansion, 4 S-boxes, "
                           "P transposition, XOR into the left half), FP; decode_header "
                           "transforms min(20, len/8) blocks per call",
        "metadata_filter": "grf.rs:573-579 skip real_size > 256MiB, then skip entries "
                           "without the file bit",
    },
}

HEADER_SIZE = 46
SIGNATURES = (b"Master of Magic", b"Event Horizon")
TABLE_HEADER_SIZE = 8
TYPE_FILE, TYPE_ENCRYPT_MIXED, TYPE_ENCRYPT_HEADER = 0x01, 0x02, 0x04
LEGACY_LENGTH_BIAS = 715
LEGACY_ALIGNED_BIAS = 37579
LEGACY_ENTRY_DATA_SIZE = 17
MAX_FILE_UNCOMPRESSED_BYTES = 256 * 1024 * 1024
MAX_ENTRIES = 500_000
MAX_FILE_TABLE_BYTES = 512 * 1024 * 1024
HEADER_ONLY_SUFFIXES = (b".gnd", b".gat", b".act", b".str")
# This child implements the archives' actual legacy version and the modern layouts.
IMPLEMENTED_LEGACY_VERSIONS = (0x102,)

WORK_LIMITS = {
    "max_entries_per_archive": MAX_ENTRIES,
    "max_table_bytes": MAX_FILE_TABLE_BYTES,
    "max_compressed_table_bytes": MAX_FILE_TABLE_BYTES,
    "max_decompressed_table_bytes": MAX_FILE_TABLE_BYTES,
    "decompression_output_cap": "declared real_size + 1, no flush",
    "max_records_total": 3 * MAX_ENTRIES,
    "max_record_file_bytes": 1 << 30,
    "read_chunk_bytes": 8 << 20,
}

PROFILE = {
    "name": "remoteclient-66ba94e-raw-grf-table",
    "archive_order": "pinned archive-input-manifest data_ini.ordered_basenames",
    "implemented": ["legacy 0x102 (clear table to EOF, obfuscated names)",
                    "0x200 (zlib table, 17-byte entry data)",
                    "0x300 (64-bit table offset, extra 4-byte skip, zlib table, 21-byte "
                    "entry data)",
                    "0x300 header whose high offset word >> 8 != 0, read as 0x200"],
    "unsupported": ["0x1xx versions other than 0x102: source-accepted with the same layout "
                    "but not implemented or verified by this child; refused as unsupported",
                    "INI parsing, ordering or priority beyond the pinned basenames",
                    "filename codecs (CP949/UTF-8/Latin-1), Unicode or path normalisation, "
                    "case folding, .gat stripping, key merging or precedence",
                    "payload interpretation, extraction, decryption, decompression or "
                    "validation (opaque bytes are read for full-archive hashing)"],
    "assumptions": ["The pinned input manifest's order and archive identities are the frozen "
                    "inputs; installed loose files, caches and overrides are separate state.",
                    "Names are raw table bytes; legacy names are the clear bytes after the "
                    "block transform, not a decoded human spelling."],
}

VALIDATOR_POLICY = [
    "Source rejections reproduce checks grf.rs itself makes (signature, version, entry and "
    "table limits, table bounds, zero sizes, final size mismatch, truncated records).",
    "Native decompression errors and a decoded size different from the declared real "
    "size are source rejections (grf.rs:535-548 maps both to CorruptTable); an overlong "
    "stream is stopped early by the output cap and reported as that native mismatch.",
    "Additional strict policy (not performed by the source, whose zlib read_to_end is "
    "unbounded): decompression output is capped at the declared real size plus one byte "
    "with no flush, and a stream that yields exactly the declared bytes must also reach "
    "its end (complete framing and checksum) and leave no trailing compressed bytes. A "
    "failure of these framing rules or of a work limit is a validator refusal, not a "
    "native rejection.",
    "Unsupported: source-accepted variants not implemented here are refused as unsupported.",
    "Leftover bytes after the declared record count are recorded (length and hash), as the "
    "source does not reject them.",
    "On failure, cleanup removes only a verified owned completion file when possible. "
    "Removal failures or foreign replacements are diagnosed; that directory remains "
    "failed despite any marker. Successful completion means only the bounded raw catalog.",
]

EXCLUSIONS = [
    "raw DATA.INI content, host paths or machine identifiers",
    "compressed or decompressed table bodies (only hashes and per-record fields)",
    "payload bytes, decryption, decompression or readability",
    "human filename decoding, Unicode or path normalisation and duplicate-key precedence",
    "installed loose/cache/override state and runtime loading",
    "maps, monsters, story, playability, episode or coverage",
]


class CatalogError(ValueError):
    """Input or output that cannot be catalogued or published without guessing."""
    category = "error"


class InputError(CatalogError):
    category = "input_pin"


class SourceRejection(CatalogError):
    """The pinned source itself rejects this data."""
    category = "source_rejection"


class ValidatorRefusal(CatalogError):
    """Stricter than the source; refused by this validator's policy."""
    category = "validator_refusal"


class Unsupported(CatalogError):
    """Accepted by the source but not implemented by this child."""
    category = "unsupported"


class OutputError(CatalogError):
    category = "output"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def u32(data, at):
    return struct.unpack_from("<I", data, at)[0]


# --- One-round block transform (des.rs:11-179) -------------------------------------

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
    bytes.fromhex("ef0341fdd8741e4726effb22b3d8841e39aca76062c1cdba5c969059053b7a85"
                  "40fd1ec8e78a8b21da43649f2d14b172f55bc8b69c3776ec39a0a305526e0fd9"),
    bytes.fromhex("a7dd0d789e0be3956036364ff9605aa31124d287c85275ecbbc14cba24fe8f19"
                  "da1366af49d090068c6afb91378d0d78bf4911f423e5ce3b55bca257e82274ce"),
    bytes.fromhex("2ceac1bf4a241fc27947a27cb6d9681580565d0133fdf4aede30079be5839b68"
                  "49b42e831fc2b57ca219d8e57c2f83daf76b90fec4015a9761a63d400b58e63d"),
    bytes.fromhex("4dd1b20f28bde478f64a0f938b17d1a43aecc93593567ecb5520a0fe6c891762"
                  "17624bb1b4ded187c9143c4a7ea8e27da09ff65c6a098df00fe35325953628cb"),
)


def _bit_tables(table, in_bytes, out_bits):
    """Per input byte position and value, the output bits it sets (MSB-first numbering).

    Bit k of a block (k = 0 is the MSB of byte 0) maps to integer bit out_bits-1-k, so
    the permutation output for output index i taking source bit table[i]-1 is a pure
    lookup OR. This is the same mapping as the source's MASK loops.
    """
    out = [[0] * 256 for _ in range(in_bytes)]
    for i, src in enumerate(table):
        j = src - 1
        byte, bit = j >> 3, 7 - (j & 7)
        for value in range(256):
            if value >> bit & 1:
                out[byte][value] |= 1 << (out_bits - 1 - i)
    return out


_IP_T = _bit_tables(_IP, 8, 64)
_FP_T = _bit_tables(_FP, 8, 64)
_TP_T = _bit_tables(_TP, 4, 32)


def _permute(tables, block):
    value = 0
    for position, byte in enumerate(block):
        value |= tables[position][byte]
    return value


def transform_block(block):
    """des::decrypt_block on 8 bytes: IP, one round, FP. Its own inverse."""
    if len(block) != 8:
        raise ValueError("block transform needs exactly 8 bytes")
    b = _permute(_IP_T, block).to_bytes(8, "big")
    s4, s5, s6, s7 = b[4], b[5], b[6], b[7]
    e = (((s7 << 5) | (s4 >> 3)) & 0x3f, ((s4 << 1) | (s5 >> 7)) & 0x3f,
         ((s4 << 5) | (s5 >> 3)) & 0x3f, ((s5 << 1) | (s6 >> 7)) & 0x3f,
         ((s5 << 5) | (s6 >> 3)) & 0x3f, ((s6 << 1) | (s7 >> 7)) & 0x3f,
         ((s6 << 5) | (s7 >> 3)) & 0x3f, ((s7 << 1) | (s4 >> 7)) & 0x3f)
    sub = bytes((_SBOX[i][e[2 * i]] & 0xf0) | (_SBOX[i][e[2 * i + 1]] & 0x0f)
                for i in range(4))
    f = _permute(_TP_T, sub)  # lands in bytes 4..7 of the source's tmp block
    left = int.from_bytes(b[:4], "big") ^ f
    mixed = left.to_bytes(4, "big") + b[4:]
    return _permute(_FP_T, mixed).to_bytes(8, "big")


def decode_header(data, length):
    """des::decode_header: transform min(20, min(length, len)/8) leading blocks."""
    out = bytearray(data)
    for i in range(min(20, min(length, len(out)) >> 3)):
        out[i * 8:i * 8 + 8] = transform_block(bytes(out[i * 8:i * 8 + 8]))
    return bytes(out)


def _nibble_swap(block):
    return bytes(((b << 4) | (b >> 4)) & 0xff for b in block)


_NAME_BLOCK_CACHE = {}
_NAME_BLOCK_CACHE_MAX = 1 << 18


def decode_name_block(block):
    """One legacy filename block: nibble swap, then a fresh decode_header(block, 8)."""
    cached = _NAME_BLOCK_CACHE.get(block)
    if cached is None:
        cached = transform_block(_nibble_swap(block))
        if len(_NAME_BLOCK_CACHE) >= _NAME_BLOCK_CACHE_MAX:
            _NAME_BLOCK_CACHE.clear()
        _NAME_BLOCK_CACHE[block] = cached
    return cached


def decode_filename(region, name_len):
    """grf.rs:334-344 over region = table[name_start..meta]. Return (bytes, blocks)."""
    out = bytearray(region)
    at = blocks = 0
    while at < name_len and at + 8 <= len(out):
        out[at:at + 8] = decode_name_block(bytes(out[at:at + 8]))
        at += 8
        blocks += 1
    return bytes(out), blocks


# --- Header (grf.rs:167-239, 473-482) ------------------------------------------------

def parse_header(header):
    """Return header fields with declared/effective version and provenance."""
    if len(header) < HEADER_SIZE:
        raise SourceRejection("header too small (<46 bytes)")
    field = header[0:15]
    nul = field.find(b"\0")
    signature = field if nul < 0 else field[:nul]
    if signature not in SIGNATURES:
        raise SourceRejection(f"invalid signature {signature.decode('latin-1')!r}")
    declared = u32(header, 42)
    low, high, count_field = u32(header, 30), u32(header, 34), u32(header, 38)
    fields = {
        "signature": signature.decode("ascii"),
        "signature_field_hex": field.hex(),
        "header_sha256": sha256(header[:HEADER_SIZE]),
        "declared_version": declared,
        "field_u32_30": low, "field_u32_34": high, "field_u32_38": count_field,
    }

    def legacy_200():
        return low + HEADER_SIZE, max(count_field - high - 7, 0)

    if declared >> 8 == 0x01:
        if declared not in IMPLEMENTED_LEGACY_VERSIONS:
            raise Unsupported(f"version 0x{declared:x} is source-accepted 0x1xx but only "
                              f"0x102 is implemented by this catalog")
        offset, count = legacy_200()
        fields.update(effective_version=declared, layout="legacy",
                      version_provenance="header", count_rule="u32@38-u32@34-7 clamped")
    elif declared not in (0x200, 0x300):
        raise SourceRejection(f"version 0x{declared:x} is not supported by the source "
                              "(expected 0x1xx, 0x200 or 0x300)")
    elif declared == 0x200:
        offset, count = legacy_200()
        fields.update(effective_version=0x200, layout="0x200",
                      version_provenance="header", count_rule="u32@38-u32@34-7 clamped")
    elif high >> 8 != 0:
        offset, count = legacy_200()
        fields.update(effective_version=0x200, layout="0x200",
                      version_provenance="0x300 high offset word >> 8 != 0, read as 0x200",
                      count_rule="u32@38-u32@34-7 clamped")
    else:
        offset, count = (high << 32) + low + HEADER_SIZE, count_field
        fields.update(effective_version=0x300, layout="0x300",
                      version_provenance="header", count_rule="u32@38 direct")
    if count > MAX_ENTRIES:
        raise SourceRejection(f"file count {count} exceeds source limit {MAX_ENTRIES}")
    skip = 4 if fields["effective_version"] == 0x300 else 0
    fields.update(table_offset=offset, record_count=count, table_skip=skip,
                  table_pos=offset + skip)
    return fields


def plan_table(header, size, table_header=None):
    """Byte range of the stored table. Modern layouts need the 8-byte table header."""
    pos = header["table_pos"]
    if header["layout"] == "legacy":
        if pos > size:
            raise SourceRejection(f"file table starts past the end of the archive (at {pos})")
        length = size - pos
        if length == 0:
            raise SourceRejection("empty file table")
        if length > MAX_FILE_TABLE_BYTES:
            raise SourceRejection(f"uncompressed file table too large ({length} bytes)")
        return {"stored_start": pos, "stored_end": size, "stored_bytes": length}
    if table_header is None or len(table_header) < TABLE_HEADER_SIZE or \
            pos + TABLE_HEADER_SIZE > size:
        raise SourceRejection(f"file table header at {pos} is past the end of the archive")
    compressed, real = u32(table_header, 0), u32(table_header, 4)
    if compressed == 0 or real == 0:
        raise SourceRejection("invalid file table sizes (0)")
    if real > MAX_FILE_TABLE_BYTES:
        raise SourceRejection(f"uncompressed file table too large ({real} bytes)")
    if pos + TABLE_HEADER_SIZE + compressed > size:
        raise SourceRejection(f"file table runs past the end of the archive "
                              f"({compressed} bytes at {pos})")
    if compressed > WORK_LIMITS["max_compressed_table_bytes"]:
        raise ValidatorRefusal(f"compressed file table above "
                               f"{WORK_LIMITS['max_compressed_table_bytes']} bytes")
    return {"stored_start": pos, "stored_end": pos + TABLE_HEADER_SIZE + compressed,
            "stored_bytes": TABLE_HEADER_SIZE + compressed,
            "compressed_size": compressed, "real_size": real}


def inflate_table(compressed, real_size):
    """Bounded strict zlib decode of a modern table (output cap real_size + 1, no flush).

    grf.rs:535-548 surfaces decompression errors and a final size mismatch as native
    CorruptTable, so those are source rejections (an overlong stream is detected early
    under the cap but would fail the same native size check). Only the stronger framing
    rules (stream end reached with exactly the declared bytes, no trailing input) are
    validator-policy refusals.
    """
    if real_size > WORK_LIMITS["max_decompressed_table_bytes"]:
        raise ValidatorRefusal("declared table size above the decompression work limit")
    decoder = zlib.decompressobj()
    try:
        out = decoder.decompress(compressed, real_size + 1)
    except zlib.error as exc:
        raise SourceRejection(f"failed to decompress file table: {exc}") from None
    if len(out) > real_size:
        raise SourceRejection(f"file table size mismatch: decompresses past its declared "
                              f"{real_size} bytes (stopped at the bounded cap)")
    if len(out) != real_size:
        raise SourceRejection(f"file table size mismatch: expected {real_size}, "
                              f"got {len(out)}" + ("" if decoder.eof else
                                                   " before the stream ended"))
    if not decoder.eof:
        raise ValidatorRefusal("table zlib stream yields the declared bytes but does not "
                               "reach its end (truncated framing/checksum)")
    if decoder.unused_data:
        raise ValidatorRefusal(f"{len(decoder.unused_data)} trailing bytes after the table "
                               "zlib stream")
    return out


# --- Records (grf.rs:266-455, 573-579) ------------------------------------------------

def metadata_filter(real_size, kind):
    if real_size > MAX_FILE_UNCOMPRESSED_BYTES:
        return "real_size_over_256MiB"
    if not kind & TYPE_FILE:
        return "file_bit_absent"
    return "eligible"


def _payload_fields(rec, offset, aligned, archive_size):
    rec["payload_offset_field"] = offset
    start = offset + HEADER_SIZE
    rec["diagnostic_body_range"] = [start, start + aligned]
    if archive_size is not None:
        rec["diagnostic_body_range_within_archive"] = start + aligned <= archive_size


def modern_records(data, count, version, archive_size=None):
    """Yield one record per declared entry; return leftover via the final StopIteration."""
    size = 21 if version == 0x300 else 17
    p = 0
    for i in range(count):
        if p >= len(data):
            raise SourceRejection(f"unexpected end of file table at entry {i}")
        end = data.find(b"\0", p)
        if end < 0:
            end = len(data)
        name = data[p:end]
        meta = end + 1
        if meta + size > len(data):
            raise SourceRejection(f"incomplete entry data at entry {i}" +
                                  ("" if end < len(data) else " (name has no NUL)"))
        compressed, aligned, real = struct.unpack_from("<III", data, meta)
        kind = data[meta + 12]
        if version == 0x300:
            offset = u32(data, meta + 13) + (u32(data, meta + 17) << 32)
        else:
            offset = u32(data, meta + 13)
        effective = kind
        promotion = None
        if kind == 0 and real > 0 and compressed == real:
            effective, promotion = TYPE_FILE, "kind0_stored_file_to_file"
        rec = {
            "ordinal": i, "table_offset": p, "record_bytes": meta + size - p,
            "name_hex": name.hex(), "name_length": len(name), "name_terminated": True,
            "compressed_size": compressed, "length_aligned": aligned, "real_size": real,
            "original_kind": kind, "effective_kind": effective, "kind_promotion": promotion,
            "metadata_filter": metadata_filter(real, effective),
        }
        _payload_fields(rec, offset, aligned, archive_size)
        yield rec
        p = meta + size
    return p


def header_encryption(name):
    """grf.rs:351-366: TYPE_ENCRYPT_HEADER for the four suffixes, else MIXED."""
    dot = name.rfind(b".")
    if dot >= 0 and name[dot:].lower() in HEADER_ONLY_SUFFIXES:
        return TYPE_ENCRYPT_HEADER
    return TYPE_ENCRYPT_MIXED


def legacy_records(data, count, archive_size=None, table_file_offset=None):
    """Yield one record per declared 0x1xx entry; return consumed length at the end."""
    p = 0
    n = len(data)
    for i in range(count):
        if p + 4 > n:
            raise SourceRejection(f"unexpected end of file table at entry {i}")
        block_len = u32(data, p)
        low_byte = data[p]
        name_len = max(low_byte - 6, 0)
        meta = p + 4 + block_len
        if meta + LEGACY_ENTRY_DATA_SIZE > n:
            raise SourceRejection(f"incomplete entry data at entry {i}")
        name_start = p + 6
        if name_start + name_len > meta:
            raise SourceRejection(f"filename runs past its own entry at entry {i}")
        encoded = bytes(data[name_start:meta])
        clear, blocks = decode_filename(encoded, name_len)
        derived = clear[:name_len]
        nul = derived.find(b"\0")
        name = derived if nul < 0 else derived[:nul]
        size_field, aligned_field, real = struct.unpack_from("<III", data, meta)
        kind = data[meta + 12]
        offset = u32(data, meta + 13)
        compressed = size_field - real - LEGACY_LENGTH_BIAS
        aligned = aligned_field - LEGACY_ALIGNED_BIAS
        effective = kind
        encryption = None
        underflow = compressed < 0 or aligned < 0
        if underflow:
            effective &= ~TYPE_FILE & 0xff
        elif kind & TYPE_FILE:
            flag = header_encryption(name)
            effective |= flag
            encryption = "header" if flag == TYPE_ENCRYPT_HEADER else "mixed"
        rec = {
            "ordinal": i, "table_offset": p, "record_bytes": meta + LEGACY_ENTRY_DATA_SIZE - p,
            "block_length": block_len, "block_low_byte": low_byte,
            "derived_name_length": name_len, "name_start": name_start - p,
            "metadata_offset": meta - p,
            "encoded_region_bytes": len(encoded),
            "encoded_region_sha256": sha256(encoded),
            "encoded_name_sha256": sha256(encoded[:name_len]),
            "transformed_blocks": blocks,
            "untransformed_name_bytes": max(name_len - 8 * blocks, 0),
            "name_hex": name.hex(), "name_length": len(name), "name_terminated": nul >= 0,
            "size_field": size_field, "aligned_field": aligned_field, "real_size": real,
            "derived_compressed_size": compressed, "derived_length_aligned": aligned,
            "compressed_size": max(compressed, 0), "length_aligned": max(aligned, 0),
            "compressed_underflow": compressed < 0, "aligned_underflow": aligned < 0,
            "original_kind": kind, "effective_kind": effective,
            "header_encryption_flag": encryption,
            "metadata_filter": metadata_filter(real, effective),
        }
        if table_file_offset is not None:
            rec["archive_offset"] = table_file_offset + p
        _payload_fields(rec, offset, max(aligned, 0), archive_size)
        yield rec
        p = meta + LEGACY_ENTRY_DATA_SIZE
    return p


class Summary:
    """Counts over the records of one archive."""

    def __init__(self):
        self.raw = 0
        self.filters = {}
        self.original_kinds = {}
        self.effective_kinds = {}
        self.flags = {"file": 0, "encrypt_mixed": 0, "encrypt_header": 0}
        self.promotions = 0
        self.underflow = {"compressed": 0, "aligned": 0, "any": 0}
        self.unterminated = self.empty = self.high_byte = self.duplicates = 0
        self.body_outside = 0
        self._names = set()

    def add(self, rec):
        self.raw += 1
        reason = rec["metadata_filter"]
        self.filters[reason] = self.filters.get(reason, 0) + 1
        for counts, key in ((self.original_kinds, "original_kind"),
                            (self.effective_kinds, "effective_kind")):
            counts[str(rec[key])] = counts.get(str(rec[key]), 0) + 1
        kind = rec["effective_kind"]
        for name, bit in (("file", TYPE_FILE), ("encrypt_mixed", TYPE_ENCRYPT_MIXED),
                          ("encrypt_header", TYPE_ENCRYPT_HEADER)):
            if kind & bit:
                self.flags[name] += 1
        if rec.get("kind_promotion"):
            self.promotions += 1
        if rec.get("compressed_underflow"):
            self.underflow["compressed"] += 1
        if rec.get("aligned_underflow"):
            self.underflow["aligned"] += 1
        if rec.get("compressed_underflow") or rec.get("aligned_underflow"):
            self.underflow["any"] += 1
        if not rec["name_terminated"]:
            self.unterminated += 1
        name = bytes.fromhex(rec["name_hex"])
        if not name:
            self.empty += 1
        if any(b > 0x7f for b in name):
            self.high_byte += 1
        if name in self._names:
            self.duplicates += 1
        else:
            self._names.add(name)
        if rec.get("diagnostic_body_range_within_archive") is False:
            self.body_outside += 1

    def result(self):
        return {
            "raw_records": self.raw,
            "metadata_eligible": self.filters.get("eligible", 0),
            "metadata_filter": dict(sorted(self.filters.items())),
            "original_kind": dict(sorted(self.original_kinds.items(), key=lambda x: int(x[0]))),
            "effective_kind": dict(sorted(self.effective_kinds.items(),
                                          key=lambda x: int(x[0]))),
            "effective_flags": self.flags,
            "kind0_promotions": self.promotions,
            "length_bias_underflows": self.underflow,
            "names_without_nul": self.unterminated,
            "empty_names": self.empty,
            "names_with_high_bytes": self.high_byte,
            "duplicate_raw_names": self.duplicates,
            "unique_raw_names": len(self._names),
            "diagnostic_body_ranges_outside_archive": self.body_outside,
        }


def render_record(archive, archive_sha256, rec):
    rec = dict(rec, archive=archive, archive_sha256=archive_sha256)
    return (json.dumps(rec, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            + "\n").encode("ascii")


def catalog_table(header, plan, stored, archive_size, archive_name, emit,
                  archive_sha256=None):
    """Parse a captured stored table and emit rendered records. Return the table summary.

    `stored` is the bytes of plan's stored range; `emit` receives each JSONL line.
    """
    if len(stored) != plan["stored_bytes"]:
        raise SourceRejection("captured table length differs from its planned range")
    table = {"stored_offset": plan["stored_start"], "stored_bytes": plan["stored_bytes"],
             "stored_sha256": sha256(stored)}
    if header["layout"] == "legacy":
        data = bytes(stored)
        records = legacy_records(data, header["record_count"], archive_size,
                                 plan["stored_start"])
        table.update(form="clear legacy table to EOF", table_bytes=len(data),
                     table_sha256=table["stored_sha256"])
    else:
        compressed = bytes(stored[TABLE_HEADER_SIZE:])
        data = inflate_table(compressed, plan["real_size"])
        records = modern_records(data, header["record_count"], header["effective_version"],
                                 archive_size)
        table.update(form="zlib table behind compressed/real u32 sizes",
                     compressed_size=plan["compressed_size"], real_size=plan["real_size"],
                     compressed_sha256=sha256(compressed), table_bytes=len(data),
                     table_sha256=sha256(data))
    summary = Summary()
    consumed = 0
    while True:
        try:
            rec = next(records)
        except StopIteration as done:
            consumed = done.value
            break
        summary.add(rec)
        emit(render_record(archive_name, archive_sha256, rec))
    leftover = data[consumed:]
    table.update(consumed_bytes=consumed, trailing_bytes=len(leftover),
                 trailing_sha256=sha256(leftover))
    return table, summary.result()


def catalog_archive_bytes(blob, name="archive.grf", emit=None):
    """Pure in-memory catalog of a whole synthetic archive (tests, small fixtures)."""
    header = parse_header(blob[:HEADER_SIZE])
    pos = header["table_pos"]
    plan = plan_table(header, len(blob), blob[pos:pos + TABLE_HEADER_SIZE]
                      if header["layout"] != "legacy" else None)
    lines = []
    table, counts = catalog_table(header, plan, blob[plan["stored_start"]:plan["stored_end"]],
                                  len(blob), name, emit or lines.append, sha256(blob))
    return header, table, counts, lines


# --- Pinned inputs ----------------------------------------------------------------------

DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
# Opening a FIFO must not wait for a writer before fstat can reject it. Regular
# files retain ordinary read semantics with O_NONBLOCK on the supported host.
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK


def _open_dir(path, what):
    try:
        return os.open(path, DIR_FLAGS)
    except OSError as exc:
        raise InputError(f"{what} is missing, not a directory or a link: {exc.strerror}") \
            from None


def _read_pinned(dir_fd, name, pin):
    try:
        fd = os.open(name, FILE_FLAGS, dir_fd=dir_fd)
    except OSError as exc:
        raise InputError(f"input {name} cannot be opened without following links: "
                         f"{exc.strerror}") from None
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size != pin["bytes"]:
            raise InputError(f"input {name} is not a regular file of {pin['bytes']} bytes")
        data = os.pread(fd, pin["bytes"] + 1, 0)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    if len(data) != pin["bytes"] or sha256(data) != pin["sha256"] or \
            _identity(before) != _identity(after):
        raise InputError(f"input {name} does not match its pin or changed while read")
    return data


def read_inputs(input_dir, pins=INPUT_PINS):
    """Verify the exact two pinned files; return (manifest dict, provenance)."""
    dir_fd = _open_dir(input_dir, "pinned input directory")
    try:
        names = sorted(os.listdir(dir_fd))
        if names != sorted(pins):
            raise InputError(f"pinned input directory must hold exactly {sorted(pins)}, "
                             f"found {len(names)} entries")
        found = {name: _read_pinned(dir_fd, name, pins[name]) for name in sorted(pins)}
    finally:
        os.close(dir_fd)
    try:
        manifest = json.loads(found[INPUT_MANIFEST].decode("utf-8"))
    except ValueError as exc:
        raise InputError(f"pinned input manifest is not JSON: {exc}") from None
    return manifest, found


def verify_input_manifest(manifest, ini_bytes, archive_pins=ARCHIVE_PINS):
    """The manifest must bind the INI hash, the exact order and every archive pin."""
    ini = manifest.get("data_ini", {}) if isinstance(manifest, dict) else {}
    expected_order = [a["file"] for a in archive_pins]
    if ini.get("bytes") != len(ini_bytes) or ini.get("sha256") != sha256(ini_bytes):
        raise InputError("input manifest does not bind the pinned DATA.INI bytes/hash")
    if ini.get("ordered_basenames") != expected_order:
        raise InputError("input manifest archive order differs from the pinned order")
    listed = manifest.get("archives")
    if not isinstance(listed, list) or \
            [(a.get("file"), a.get("bytes"), a.get("sha256")) for a in listed] != \
            [(a["file"], a["bytes"], a["sha256"]) for a in archive_pins]:
        raise InputError("input manifest archive identities differ from the pinned archives")
    bindings = manifest.get("ini_bindings")
    if not isinstance(bindings, list) or [b.get("file") for b in bindings] != expected_order \
            or not all(b.get("same_acquired_archive_file") is True for b in bindings):
        raise InputError("input manifest INI bindings do not name the acquired archives")
    return expected_order


def input_manifest_agreement(listed, header):
    """The pinned preparation's header facts must agree with the freshly parsed header."""
    checks = {
        "signature": listed.get("signature") == header["signature"],
        "header_sha256": listed.get("header_sha256") == header["header_sha256"],
        "header_version": listed.get("header_version") == header["declared_version"],
        "effective_version": listed.get("effective_version") == header["effective_version"],
        "header_record_count": listed.get("header_record_count") == header["record_count"],
        "table_start": listed.get("table_start") == header["table_pos"],
    }
    if not all(checks.values()):
        raise InputError(f"pinned input manifest header facts disagree with the archive: "
                         f"{sorted(k for k, ok in checks.items() if not ok)}")
    return checks


# --- Archive streaming --------------------------------------------------------------------

def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns,
            stat.S_IFMT(info.st_mode))


def read_archive(root_fd, pin, usage):
    """Open, stream-hash and capture header/table of one pinned archive.

    Returns (header, plan, stored table bytes, size). Every byte parsed was read in the
    hashed pass from the same no-follow descriptor.
    """
    name = pin["file"]
    try:
        fd = os.open(name, FILE_FLAGS, dir_fd=root_fd)
    except OSError as exc:
        raise InputError(f"archive {name} cannot be opened without following links: "
                         f"{exc.strerror}") from None
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise InputError(f"archive {name} is not a regular file")
        size = before.st_size
        if size != pin["bytes"]:
            raise InputError(f"archive {name} is {size} bytes, pinned {pin['bytes']}")
        head = os.pread(fd, HEADER_SIZE, 0)
        header = parse_header(head)
        table_header = None
        if header["layout"] != "legacy" and header["table_pos"] + TABLE_HEADER_SIZE <= size:
            table_header = os.pread(fd, TABLE_HEADER_SIZE, header["table_pos"])
        plan = plan_table(header, size, table_header)
        start, end = plan["stored_start"], plan["stored_end"]
        digest = hashlib.sha256()
        stored = bytearray()
        streamed_head = bytearray()
        offset = 0
        chunk_size = WORK_LIMITS["read_chunk_bytes"]
        while True:
            chunk = os.pread(fd, chunk_size, offset)
            if not chunk:
                break
            digest.update(chunk)
            chunk_end = offset + len(chunk)
            if offset < HEADER_SIZE:
                streamed_head += chunk[:HEADER_SIZE - offset]
            if chunk_end > start and offset < end:
                stored += chunk[max(start - offset, 0):min(end, chunk_end) - offset]
            offset = chunk_end
        usage["archive_bytes_hashed"] += offset
        usage["table_bytes_captured"] += len(stored)
        after = os.fstat(fd)
        try:
            current = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
        except OSError:
            current = None
    finally:
        os.close(fd)
    if offset != size or _identity(before) != _identity(after) or current is None or \
            _identity(current) != _identity(before):
        raise InputError(f"archive {name} changed, was replaced or ended early while read")
    if digest.hexdigest() != pin["sha256"]:
        raise InputError(f"archive {name} SHA-256 differs from its pin")
    if bytes(streamed_head) != head:
        raise InputError(f"archive {name} header changed between reads")
    if table_header is not None and bytes(stored[:TABLE_HEADER_SIZE]) != table_header:
        raise InputError(f"archive {name} table header changed between reads")
    return header, plan, stored, size


# --- Publication ----------------------------------------------------------------------

def render(document):
    return (json.dumps(document, ensure_ascii=True, indent=1, sort_keys=True)
            + "\n").encode("ascii")


def trusted_target(out_dir):
    """Return the absolute target below an existing parent owned by you and not shared."""
    out_dir = Path(os.path.abspath(out_dir))
    if out_dir.name in ("", ".", ".."):
        raise OutputError(f"invalid output directory name: {out_dir}")
    parent = out_dir.parent
    try:
        info = os.lstat(parent)
    except FileNotFoundError:
        raise OutputError(f"output parent does not exist: {parent}") from None
    if not stat.S_ISDIR(info.st_mode):
        raise OutputError(f"output parent is not a directory (or is a link): {parent}")
    if info.st_uid != os.geteuid() or info.st_mode & 0o022:
        raise OutputError(f"output parent must be owned by you and not group/world "
                          f"writable: {parent}")
    return out_dir


class RecordFile:
    """Exclusive, no-follow, 0600 streaming JSONL writer with a running hash."""

    def __init__(self, dir_fd, name, created):
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600,
                     dir_fd=dir_fd)
        created[name] = None
        info = os.fstat(fd)
        created[name] = (info.st_dev, info.st_ino)
        self.name = name
        self.handle = os.fdopen(fd, "wb")
        os.fchmod(self.handle.fileno(), 0o600)
        self.digest = hashlib.sha256()
        self.bytes = self.lines = 0

    def write(self, line):
        if self.bytes + len(line) > WORK_LIMITS["max_record_file_bytes"]:
            raise ValidatorRefusal(f"record file {self.name} above "
                                   f"{WORK_LIMITS['max_record_file_bytes']} bytes")
        self.handle.write(line)
        self.digest.update(line)
        self.bytes += len(line)
        self.lines += 1

    def close(self):
        self.handle.flush()
        os.fsync(self.handle.fileno())
        self.handle.close()
        return {"file": self.name, "bytes": self.bytes, "lines": self.lines,
                "sha256": self.digest.hexdigest()}


def _write_new(dir_fd, name, data, created):
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600,
                 dir_fd=dir_fd)
    # Remember ownership before writing: write/flush/close can fail after the
    # exclusive creation. None means identity capture failed; never unlink an
    # unverified file during cleanup.
    created[name] = None
    with os.fdopen(fd, "wb") as handle:
        info = os.fstat(handle.fileno())
        created[name] = (info.st_dev, info.st_ino)
        os.fchmod(handle.fileno(), 0o600)
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _verify_published(dir_fd, name, size, digest, expected_identity=None):
    """Read back a published file by no-follow descriptor: size, hash and private mode."""
    fd = os.open(name, FILE_FLAGS, dir_fd=dir_fd)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or \
                info.st_uid != os.geteuid() or info.st_size != size or \
                (expected_identity is not None and
                (info.st_dev, info.st_ino) != expected_identity):
            raise OutputError(f"published {name} is not the owned private regular file")
        hasher = hashlib.sha256()
        total = 0
        while total <= size:
            chunk = os.read(fd, min(1 << 20, size + 1 - total))
            if not chunk:
                break
            hasher.update(chunk)
            total += len(chunk)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    if total != size or hasher.hexdigest() != digest or _identity(info) != _identity(after):
        raise OutputError(f"published {name} differs from the generated bytes or mode")


def build_manifest(provenance, archives, usage):
    totals = {key: sum(a["counts"][key] for a in archives)
              for key in ("raw_records", "metadata_eligible", "kind0_promotions",
                          "names_without_nul", "duplicate_raw_names")}
    totals["length_bias_underflows"] = sum(a["counts"]["length_bias_underflows"]["any"]
                                           for a in archives)
    return {
        "kind": "raw GRF table catalog (pinned archives, source-profile records only)",
        "status": "complete",
        "status_meaning": "every declared raw record of every pinned archive was catalogued "
                          "under the bounded policy; not a filename codec, key, payload, "
                          "map, playability or coverage result",
        **provenance,
        "source": SOURCE,
        "profile": PROFILE,
        "validator_policy": VALIDATOR_POLICY,
        "archives": archives,
        "totals": totals,
        "work_limits": WORK_LIMITS,
        "work_usage": usage,
        "exclusions": EXCLUSIONS,
    }


def run(input_dir, archive_root, output, archive_pins=ARCHIVE_PINS, input_pins=INPUT_PINS):
    """Verify inputs, catalog every archive into a new directory. Return (target, manifest,
    hashes). The pin arguments exist for the module's own consistency; the CLI never
    changes them."""
    target = trusted_target(output)
    if os.path.lexists(target):
        raise OutputError(f"output already exists, refusing to overwrite: {target}")
    manifest_in, found = read_inputs(input_dir, input_pins)
    order = verify_input_manifest(manifest_in, found[INPUT_INI], archive_pins)
    root_fd = _open_dir(archive_root, "acquired archive root")
    try:
        os.mkdir(target, 0o700)  # exclusive: refuses any file, dir or (dangling) symlink
    except OSError as exc:
        os.close(root_fd)
        raise OutputError(f"output exists or cannot be created, refusing: {target}: "
                          f"{exc.strerror}") from None
    out_fd, identity, created = None, None, {}
    usage = {"archive_bytes_hashed": 0, "table_bytes_captured": 0, "records": 0,
             "record_file_bytes": 0}
    try:
        out_fd = os.open(target, DIR_FLAGS)
        info = os.fstat(out_fd)
        identity = (info.st_dev, info.st_ino)
        if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise OutputError("reserved output directory is not private to you")
        archives = []
        for position, pin in enumerate(archive_pins):
            header, plan, stored, size = read_archive(root_fd, pin, usage)
            agreement = input_manifest_agreement(manifest_in["archives"][position], header)
            writer = RecordFile(out_fd, pin["file"] + RECORDS_SUFFIX, created)
            try:
                table, counts = catalog_table(header, plan, stored, size, pin["file"],
                                              writer.write, pin["sha256"])
            except BaseException:
                writer.handle.close()
                raise
            del stored
            record_file = writer.close()
            _verify_published(out_fd, record_file["file"], record_file["bytes"],
                              record_file["sha256"], created[record_file["file"]])
            usage["records"] += counts["raw_records"]
            usage["record_file_bytes"] += record_file["bytes"]
            if usage["records"] > WORK_LIMITS["max_records_total"]:
                raise ValidatorRefusal("total records above the work limit")
            archives.append({"order": position, "file": pin["file"], "bytes": size,
                             "sha256": pin["sha256"], "header": header, "table": table,
                             "input_manifest_agreement": agreement,
                             "counts": counts, "records_file": record_file})
        # All archive reads are finished. A close error must fail inside the
        # publication transaction, before a success record can exist. Relinquish
        # the descriptor first so a close error cannot trigger a second close.
        closing_root, root_fd = root_fd, None
        os.close(closing_root)
        provenance = {
            "generator": {"tool": "tools/renewal/archive_catalog.py", "version": VERSION,
                          "source_sha256": sha256(Path(__file__).read_bytes())},
            "inputs": {"pinned_files": {n: dict(input_pins[n]) for n in sorted(input_pins)},
                       "ordered_basenames": order,
                       "archive_pins": [dict(p) for p in archive_pins],
                       "ini_handling": "hash-verified only; not parsed, echoed or copied"},
        }
        manifest = build_manifest(provenance, archives, usage)
        manifest_bytes = render(manifest)
        _write_new(out_fd, OUTPUT_MANIFEST, manifest_bytes, created)
        _verify_published(out_fd, OUTPUT_MANIFEST, len(manifest_bytes), sha256(manifest_bytes),
                          created[OUTPUT_MANIFEST])
        complete = render({
            "generator_version": VERSION, "status": manifest["status"],
            "catalog_manifest": OUTPUT_MANIFEST,
            "catalog_manifest_sha256": sha256(manifest_bytes),
            "record_files": {a["records_file"]["file"]: a["records_file"]["sha256"]
                             for a in archives},
        })
        hashes = {"manifest_sha256": sha256(manifest_bytes),
                  "manifest_bytes": len(manifest_bytes),
                  "complete_sha256": sha256(complete)}
        _write_new(out_fd, OUTPUT_COMPLETE, complete, created)
        _verify_published(out_fd, OUTPUT_COMPLETE, len(complete), hashes["complete_sha256"],
                          created[OUTPUT_COMPLETE])
        if sorted(os.listdir(out_fd)) != sorted(created):
            raise OutputError("output directory holds files this run did not write")
        # Close is part of publication, not a finally action allowed to turn a
        # success marker into a failed CLI result without running cleanup.
        closing_fd, out_fd = out_fd, None
        os.close(closing_fd)
    except Exception as exc:
        note = "; partial output remains (failed); inspect it " \
               "before deleting or retrying"
        if OUTPUT_COMPLETE in created:
            cleanup_fd, reopened = out_fd, False
            try:
                if cleanup_fd is None:
                    # Reopen only the directory this run reserved, never a replacement.
                    cleanup_fd = os.open(target, DIR_FLAGS)
                    reopened = True
                    current = os.fstat(cleanup_fd)
                    if (current.st_dev, current.st_ino) != identity:
                        raise OutputError("reserved output directory was replaced")
                marker = os.stat(OUTPUT_COMPLETE, dir_fd=cleanup_fd, follow_symlinks=False)
                if not stat.S_ISREG(marker.st_mode) or \
                        (marker.st_dev, marker.st_ino) != created[OUTPUT_COMPLETE]:
                    raise OutputError("completion was replaced; foreign file preserved")
                os.unlink(OUTPUT_COMPLETE, dir_fd=cleanup_fd)
            except FileNotFoundError:
                pass
            except Exception as cleanup:
                note = (f"; could not remove {OUTPUT_COMPLETE} ({cleanup}); treat this output "
                        "as failed and incomplete despite the record")
            finally:
                if reopened:
                    try:
                        os.close(cleanup_fd)
                    except Exception:
                        pass  # preserve the publication/marker-cleanup diagnostic
        category = exc.category if isinstance(exc, CatalogError) else "unexpected"
        error = type(exc) if isinstance(exc, CatalogError) else OutputError
        if out_fd is not None and OUTPUT_FAILED not in created:
            # Best effort and path-free; a foreign completion may remain, so the
            # diagnostic must not claim that this directory has no such file.
            try:
                _write_new(out_fd, OUTPUT_FAILED, render({
                    "generator_version": VERSION, "status": "failed", "category": category,
                    "files_written_by_run": sorted(set(created) - {OUTPUT_COMPLETE}),
                    "meaning": "failed publication; do not use this directory as a "
                               "completed catalog"}), created)
            except Exception as marker:
                note += f"; failure marker not written ({type(marker).__name__})"
        prefix = "unexpected: " if category == "unexpected" else ""
        raise error(f"{prefix}{exc}{note}") from None
    finally:
        if root_fd is not None:
            try:
                os.close(root_fd)
            except OSError:
                pass  # failure already reported, before completion publication
        if out_fd is not None:
            try:
                os.close(out_fd)
            except Exception:
                pass  # failure already reported; never mask its cleanup outcome
    return target, manifest, hashes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("inputs", type=Path, help="pinned small input directory (read-only)")
    parser.add_argument("archive_root", type=Path, help="acquired archive root (read-only)")
    parser.add_argument("output", type=Path, help="new private output directory")
    args = parser.parse_args(argv)
    try:
        target, manifest, hashes = run(args.inputs, args.archive_root, args.output)
    except (CatalogError, OSError) as exc:
        category = getattr(exc, "category", "os_error")
        print(f"error [{category}]: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"output": str(target), "status": manifest["status"],
                      "totals": manifest["totals"],
                      "record_files": {a["file"]: a["records_file"] for a in
                                       manifest["archives"]}, **hashes}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
