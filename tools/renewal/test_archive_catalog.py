"""Tests for archive_catalog. Run: python3 -I -m unittest discover -s tools/renewal

Archives are small authored in-memory synthetic fixtures; only the pin,
publication and CLI tests write temporary directories. Tests marked "native"
check grf.rs behaviour (source rejections); "strict" tests check the additional
validator policy; "unsupported" tests check source-accepted variants this child
refuses. The block transform is checked against literal vectors and an
independent bit-loop reimplementation of des.rs, not only by round trip.

The actual-input test reads the pinned inputs from the absolute paths in
$T06_CLIENT_INPUTS and $T06_ARCHIVE_ROOT and is skipped when they are unset or
absent. There is no way to bypass the CLI pins.
"""

import hashlib
import json
import os
from pathlib import Path
import random
import stat
import struct
import sys
import tempfile
import unittest
from unittest import mock
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent))
import archive_catalog as ac  # noqa: E402


def sha(data):
    return hashlib.sha256(data).hexdigest()


# --- Independent bit-loop reference of des.rs decrypt_block -----------------------------

MASK = (0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0x01)


def ref_permute(src, table):
    out = bytearray(8)
    for i in range(64):
        j = table[i] - 1
        if src[(j >> 3) & 7] & MASK[j & 7]:
            out[(i >> 3) & 7] |= MASK[i & 7]
    return bytes(out)


def ref_block(block):
    b = bytearray(ref_permute(block, ac._IP))
    s = b
    e = [((s[7] << 5) | (s[4] >> 3)) & 0x3f, ((s[4] << 1) | (s[5] >> 7)) & 0x3f,
         ((s[4] << 5) | (s[5] >> 3)) & 0x3f, ((s[5] << 1) | (s[6] >> 7)) & 0x3f,
         ((s[5] << 5) | (s[6] >> 3)) & 0x3f, ((s[6] << 1) | (s[7] >> 7)) & 0x3f,
         ((s[6] << 5) | (s[7] >> 3)) & 0x3f, ((s[7] << 1) | (s[4] >> 7)) & 0x3f]
    sub = [(ac._SBOX[i][e[2 * i]] & 0xf0) | (ac._SBOX[i][e[2 * i + 1]] & 0x0f)
           for i in range(4)]
    tp = bytearray(8)
    for i in range(32):
        j = ac._TP[i] - 1
        if sub[j >> 3] & MASK[j & 7]:
            tp[(i >> 3) + 4] |= MASK[i & 7]
    for k in range(4):
        b[k] ^= tp[k + 4]
    return ref_permute(bytes(b), ac._FP)


def encode_name_region(clear, name_len):
    """Inverse of the legacy name decode: per transformed block T then nibble swap."""
    out = bytearray(clear)
    at = 0
    while at < name_len and at + 8 <= len(out):
        block = ref_block(bytes(out[at:at + 8]))
        out[at:at + 8] = bytes(((b << 4) | (b >> 4)) & 0xff for b in block)
        at += 8
    return bytes(out)


# --- Fixture builders --------------------------------------------------------------------

def header(signature=b"Master of Magic", version=0x102, f30=0, f34=0, f38=7, sig_byte15=0):
    field = signature.ljust(15, b"\0")[:15] + bytes([sig_byte15])
    return field + b"K" * 14 + struct.pack("<IIII", f30, f34, f38, version)


def legacy_entry(clear, size_field=715 + 10, aligned_field=37579 + 16, real=0, kind=1,
                 offset=0, region_extra=4, block_len=None, raw_region=None):
    """One 0x1xx record. `clear` is the clear name field of the derived length.

    By default the block length is the region length + 2, so its low byte gives
    name length len(clear) (region_extra 4), as in the actual archives. A raw region
    and explicit full block length exercise other low-byte/full-length pairs.
    """
    region = raw_region
    if region is None:
        region = encode_name_region(clear + b"\xee" * region_extra, len(clear))
    if block_len is None:
        block_len = len(region) + 2
    body = struct.pack("<I", block_len) + b"\x00\x00" + region
    assert len(body) == 4 + block_len, "region must fill the declared block"
    return body + struct.pack("<IIIBI", size_field, aligned_field, real, kind, offset)


def legacy_archive(entries, count=None, payload=b"P" * 64, trailing=b"", f34=3,
                   version=0x102):
    table = b"".join(entries) + trailing
    n = len(entries) if count is None else count
    return header(b"Master of Magic", version, len(payload), f34, n + f34 + 7) + payload + table


def modern_entry(name, compressed=10, aligned=16, real=10, kind=1, offset=0, version=0x300):
    tail = struct.pack("<IIIB", compressed, aligned, real, kind)
    tail += struct.pack("<Q", offset) if version == 0x300 else struct.pack("<I", offset)
    return name + b"\0" + tail


def modern_archive(entries, count=None, version=0x300, trailing=b"", stream=None,
                   real=None, compressed_size=None, payload=b"P" * 32, high=0,
                   signature=b"Event Horizon\0c\0"):
    table = b"".join(entries) + trailing
    blob = zlib.compress(table) if stream is None else stream
    n = len(entries) if count is None else count
    real = len(table) if real is None else real
    csize = len(blob) if compressed_size is None else compressed_size
    if version == 0x300:
        head = header(signature, 0x300, len(payload), high, n)
        skip = b"\xab\xcd\xef\x01"
    else:
        head = header(signature, 0x200, len(payload), 0, n + 7)
        skip = b""
    return head + payload + skip + struct.pack("<II", csize, real) + blob


def records(blob):
    return [json.loads(line) for line in ac.catalog_archive_bytes(blob)[3]]


# --- Transform ---------------------------------------------------------------------------

class TransformTests(unittest.TestCase):

    def test_literal_goldens(self):
        self.assertEqual(ac.transform_block(bytes(8)).hex(), "0404015555015455")
        self.assertEqual(ac.decode_name_block(bytes(8)).hex(), "0404015555015455")
        raw = bytes.fromhex("0123456789abcdef")
        self.assertEqual(ac.transform_block(raw).hex(), "5176057698ead9eb")
        self.assertEqual(ac.decode_name_block(raw).hex(), "4067146789fbc8fa")

    def test_matches_independent_bit_loop_reference(self):
        rng = random.Random(1234)
        for _ in range(500):
            block = bytes(rng.randrange(256) for _ in range(8))
            self.assertEqual(ac.transform_block(block), ref_block(block))
            self.assertEqual(ac.transform_block(ac.transform_block(block)), block)

    def test_decode_header_stops_after_20_blocks(self):
        data = bytes(range(256)) * 1
        out = ac.decode_header(data, len(data))
        self.assertNotEqual(out[:8], data[:8])
        self.assertEqual(out[160:], data[160:])

    def test_filename_decode_transforms_every_fitting_block(self):
        clear = bytes((i * 7 + 1) % 255 + 1 for i in range(200))  # 25 blocks, no NUL
        region = encode_name_region(clear, 200)
        out, blocks = ac.decode_filename(region, 200)
        self.assertEqual(blocks, 25)
        self.assertEqual(out, clear)
        # A whole-name decode_header would leave blocks 20..24 encoded.
        self.assertNotEqual(ac.decode_header(bytes(ac._nibble_swap(region)), 200), clear)

    def test_partial_boundary_and_block_past_name_length(self):
        region = bytes(range(1, 14))  # 13 bytes, name length 13: one block fits
        out, blocks = ac.decode_filename(region, 13)
        self.assertEqual(blocks, 1)
        self.assertEqual(out[8:], region[8:])
        region = bytes(range(1, 18))  # 17 bytes: second block starts at 8 < 13 and fits
        out, blocks = ac.decode_filename(region, 13)
        self.assertEqual(blocks, 2)
        self.assertEqual(out[8:16], ac.decode_name_block(region[8:16]))
        self.assertEqual(out[16:], region[16:])
        out, blocks = ac.decode_filename(region, 8)  # block at 8 does not start before 8
        self.assertEqual(blocks, 1)


# --- Header ------------------------------------------------------------------------------

class HeaderTests(unittest.TestCase):

    def test_signatures(self):
        self.assertEqual(ac.parse_header(header(b"Master of Magic", sig_byte15=0x41))
                         ["signature"], "Master of Magic")
        h = ac.parse_header(header(b"Event Horizon\0c", 0x200, f38=7))
        self.assertEqual(h["signature"], "Event Horizon")
        self.assertEqual(h["signature_field_hex"][-4:], "0063")
        ac.parse_header(header(b"Event Horizon\0RL", 0x200, f38=7))
        for bad in (b"Event HorizonXY", b"Master of Magi", b"master of magic", b"",
                    b"Event Horizo\0n"):
            with self.subTest(bad=bad), self.assertRaises(ac.SourceRejection):
                ac.parse_header(header(bad))
        with self.assertRaises(ac.SourceRejection):
            ac.parse_header(header()[:45])

    def test_native_count_arithmetic_and_clamp(self):
        h = ac.parse_header(header(f30=100, f34=5, f38=20))
        self.assertEqual((h["table_offset"], h["record_count"], h["table_skip"]), (146, 8, 0))
        self.assertEqual(ac.parse_header(header(f34=5, f38=11))["record_count"], 0)
        self.assertEqual(ac.parse_header(header(f34=0, f38=0))["record_count"], 0)
        self.assertEqual(ac.parse_header(header(f34=0, f38=500007))["record_count"], 500000)
        with self.assertRaises(ac.SourceRejection):
            ac.parse_header(header(f34=0, f38=500008))

    def test_0x300_layout_and_fallback_boundary(self):
        h = ac.parse_header(header(b"Event Horizon", 0x300, 10, 0xff, 9))
        self.assertEqual((h["effective_version"], h["layout"]), (0x300, "0x300"))
        self.assertEqual(h["table_offset"], (0xff << 32) + 10 + 46)
        self.assertEqual((h["record_count"], h["table_skip"]), (9, 4))
        self.assertEqual(h["table_pos"], h["table_offset"] + 4)
        h = ac.parse_header(header(b"Event Horizon", 0x300, 10, 0x100, 300))
        self.assertEqual((h["declared_version"], h["effective_version"]), (0x300, 0x200))
        self.assertEqual((h["table_offset"], h["record_count"], h["table_skip"]),
                         (56, 300 - 0x100 - 7, 0))
        self.assertIn("read as 0x200", h["version_provenance"])
        with self.assertRaises(ac.SourceRejection):
            ac.parse_header(header(b"Event Horizon", 0x300, 0, 0, 500001))

    def test_versions(self):
        for version in (0x100, 0x101, 0x103, 0x1ff):
            with self.subTest(v=version), self.assertRaises(ac.Unsupported):
                ac.parse_header(header(version=version))
        for version in (0x0ff, 0x201, 0x2ff, 0x301, 0x400, 0):
            with self.subTest(v=version), self.assertRaises(ac.SourceRejection):
                ac.parse_header(header(version=version))

    def test_native_table_bounds(self):
        h = ac.parse_header(header(f30=100, f38=7))
        with self.assertRaises(ac.SourceRejection):
            ac.plan_table(h, 145)                         # starts past EOF
        with self.assertRaises(ac.SourceRejection):
            ac.plan_table(h, 146)                         # empty table
        with self.assertRaises(ac.SourceRejection):
            ac.plan_table(h, 146 + ac.MAX_FILE_TABLE_BYTES + 1)
        self.assertEqual(ac.plan_table(h, 146 + ac.MAX_FILE_TABLE_BYTES)["stored_bytes"],
                         ac.MAX_FILE_TABLE_BYTES)
        m = ac.parse_header(header(b"Event Horizon", 0x300, 0, 0, 1))
        pos = m["table_pos"]
        for th, size, label in ((None, pos + 7, "header past EOF"),
                                (struct.pack("<II", 0, 5), pos + 100, "zero compressed"),
                                (struct.pack("<II", 5, 0), pos + 100, "zero real"),
                                (struct.pack("<II", 5, ac.MAX_FILE_TABLE_BYTES + 1), pos + 100,
                                 "real too large"),
                                (struct.pack("<II", 93, 5), pos + 100, "past EOF")):
            with self.subTest(label), self.assertRaises(ac.SourceRejection):
                ac.plan_table(m, size, th)
        self.assertEqual(ac.plan_table(m, pos + 100, struct.pack("<II", 92, 5))["stored_end"],
                         pos + 100)


# --- Modern records ----------------------------------------------------------------------

class ModernTests(unittest.TestCase):

    def test_0x300_21_byte_records_promotion_duplicates_trailing(self):
        entries = [
            modern_entry(b"data\\a.bmp", 7, 8, 7, 0, offset=(1 << 32) + 5),  # promoted
            modern_entry(b"data\\dir", 0, 0, 0, 0),                           # directory
            modern_entry(b"data\\b", 3, 8, 7, 0),                              # kind 0 packed
            modern_entry(b"data\\a.bmp", 3, 8, 9, 5),                          # duplicate
            modern_entry(b"", 1, 1, 1, 2),
        ]
        header_, table, counts, lines = ac.catalog_archive_bytes(
            modern_archive(entries, trailing=b"XYZ"))
        recs = [json.loads(x) for x in lines]
        self.assertEqual([r["ordinal"] for r in recs], list(range(5)))
        self.assertEqual(recs[0]["payload_offset_field"], (1 << 32) + 5)
        self.assertEqual(recs[0]["record_bytes"], len(entries[0]))
        self.assertEqual((recs[0]["original_kind"], recs[0]["effective_kind"],
                          recs[0]["kind_promotion"]), (0, 1, "kind0_stored_file_to_file"))
        self.assertEqual((recs[1]["effective_kind"], recs[1]["kind_promotion"],
                          recs[1]["metadata_filter"]), (0, None, "file_bit_absent"))
        self.assertEqual((recs[2]["effective_kind"], recs[2]["metadata_filter"]),
                         (0, "file_bit_absent"))
        self.assertEqual((recs[3]["effective_kind"], recs[3]["metadata_filter"]),
                         (5, "eligible"))
        self.assertEqual(recs[4]["metadata_filter"], "file_bit_absent")
        self.assertEqual(recs[4]["name_hex"], "")
        self.assertEqual(recs[1]["table_offset"], len(entries[0]))
        self.assertEqual((table["trailing_bytes"], table["trailing_sha256"]), (3, sha(b"XYZ")))
        self.assertEqual(counts["raw_records"], 5)
        self.assertEqual(counts["duplicate_raw_names"], 1)
        self.assertEqual(counts["kind0_promotions"], 1)
        self.assertEqual(counts["metadata_eligible"], 2)
        self.assertEqual(counts["empty_names"], 1)

    def test_0x200_17_byte_records_and_fallback_uses_them(self):
        entries = [modern_entry(b"x.txt", offset=77, version=0x200),
                   modern_entry(b"y", version=0x200)]
        recs = records(modern_archive(entries, version=0x200))
        self.assertEqual([r["record_bytes"] for r in recs], [6 + 17, 2 + 17])
        self.assertEqual(recs[0]["payload_offset_field"], 77)
        # A 0x300 header with high>>8 != 0 is read with the 0x200 layout and no skip.
        table = b"".join(entries)
        blob = zlib.compress(table)
        payload = b"P" * 32
        high = 0x100
        blob_archive = header(b"Event Horizon", 0x300, len(payload), high, 2 + high + 7) + \
            payload + struct.pack("<II", len(blob), len(table)) + blob
        recs = records(blob_archive)
        self.assertEqual([r["name_hex"] for r in recs], [b"x.txt".hex(), b"y".hex()])

    def test_high_and_invalid_name_bytes_preserved(self):
        name = bytes([0xff, 0x80, 0x01, 0x7f, 0xb0, 0xa1, 0x5c, 0x2f])
        rec = records(modern_archive([modern_entry(name)]))[0]
        self.assertEqual(rec["name_hex"], name.hex())
        rec = records(modern_archive([modern_entry(b"Data\\MAP.GAT")]))[0]
        self.assertEqual(rec["name_hex"], b"Data\\MAP.GAT".hex())  # no normalisation

    def test_native_missing_nul_and_truncated_records(self):
        table = modern_entry(b"ok")[:-3]
        with self.assertRaises(ac.SourceRejection):
            ac.catalog_archive_bytes(modern_archive([table]))
        with self.assertRaisesRegex(ac.SourceRejection, "no NUL"):
            ac.catalog_archive_bytes(modern_archive([b"name-without-terminator"], count=1))
        with self.assertRaisesRegex(ac.SourceRejection, "unexpected end"):
            ac.catalog_archive_bytes(modern_archive([modern_entry(b"a")], count=2))
        # 0x200 entry data is too short for the 21-byte 0x300 layout.
        with self.assertRaises(ac.SourceRejection):
            ac.catalog_archive_bytes(modern_archive([modern_entry(b"a", version=0x200)]))

    def test_filter_precedence_oversize_before_file_bit(self):
        limit = ac.MAX_FILE_UNCOMPRESSED_BYTES
        recs = records(modern_archive([
            modern_entry(b"a", 1, 1, limit + 1, 0),
            modern_entry(b"b", 1, 1, limit + 1, 1),
            modern_entry(b"c", 1, 1, limit, 1),
            modern_entry(b"d", limit + 1, 1, limit + 1, 0),  # promoted, still oversize
        ]))
        self.assertEqual([r["metadata_filter"] for r in recs],
                         ["real_size_over_256MiB", "real_size_over_256MiB", "eligible",
                          "real_size_over_256MiB"])
        self.assertEqual(recs[3]["kind_promotion"], "kind0_stored_file_to_file")

    def test_zero_count_keeps_whole_table_as_trailing(self):
        _, table, counts, lines = ac.catalog_archive_bytes(
            modern_archive([], count=0, trailing=b"abc"))
        self.assertEqual((counts["raw_records"], table["trailing_bytes"]), (0, 3))


class ZlibTableTests(unittest.TestCase):
    """Native: zlib errors and size mismatch (grf.rs:535-548). Strict: framing."""

    table = modern_entry(b"one") + modern_entry(b"two")

    def archive(self, stream, real=None):
        return modern_archive([self.table], count=2, stream=stream, real=real)

    def test_valid(self):
        self.assertEqual(len(records(self.archive(zlib.compress(self.table)))), 2)

    def test_native_bad_checksum_and_garbage(self):
        good = bytearray(zlib.compress(self.table))
        good[-1] ^= 0xff
        with self.assertRaisesRegex(ac.SourceRejection, "decompress"):
            ac.catalog_archive_bytes(self.archive(bytes(good)))
        with self.assertRaises(ac.SourceRejection):
            ac.catalog_archive_bytes(self.archive(b"\x00\x01garbage!"))

    def test_native_short_and_long(self):
        stream = zlib.compress(self.table)
        with self.assertRaisesRegex(ac.SourceRejection, "size mismatch"):
            ac.catalog_archive_bytes(self.archive(stream, real=len(self.table) + 1))
        with self.assertRaisesRegex(ac.SourceRejection, "size mismatch"):
            ac.catalog_archive_bytes(self.archive(stream, real=len(self.table) - 1))
        with self.assertRaisesRegex(ac.SourceRejection, "size mismatch"):
            ac.catalog_archive_bytes(self.archive(stream[:len(stream) // 2]))

    def test_strict_trailing_and_truncated_framing(self):
        stream = zlib.compress(self.table)
        with self.assertRaisesRegex(ac.ValidatorRefusal, "trailing"):
            ac.catalog_archive_bytes(self.archive(stream + b"\0junk"))
        with self.assertRaisesRegex(ac.ValidatorRefusal, "end"):
            ac.catalog_archive_bytes(self.archive(stream[:-4]))  # checksum missing

    def test_bomb_is_capped(self):
        bomb = zlib.compress(b"\0" * (64 << 20), 9)
        real_decompress = zlib.decompressobj
        caps = []

        class Spy:
            def __init__(self):
                self.inner = real_decompress()

            def decompress(self, data, cap=0):
                caps.append(cap)
                return self.inner.decompress(data, cap)

            def __getattr__(self, name):
                return getattr(self.inner, name)

        with mock.patch.object(ac.zlib, "decompressobj", Spy):
            with self.assertRaisesRegex(ac.SourceRejection, "bounded cap"):
                ac.inflate_table(bomb, 1000)
        self.assertEqual(caps, [1001])


# --- Legacy records ----------------------------------------------------------------------

class LegacyTests(unittest.TestCase):

    def test_round_trip_names_and_suffix_flags(self):
        names = [b"data\\map.gat", b"data\\x.GND", b"a.Act", b"s.str", b"t.bmp", b"noext",
                 b"x.gat.bak", b"dir.gat\\file", b"a.gatx"]
        entries = [legacy_entry(n + b"\0\0\0") for n in names]
        recs = records(legacy_archive(entries))
        self.assertEqual([bytes.fromhex(r["name_hex"]) for r in recs], names)
        self.assertEqual([r["header_encryption_flag"] for r in recs],
                         ["header", "header", "header", "header", "mixed", "mixed", "mixed",
                          "mixed", "mixed"])
        self.assertEqual([r["effective_kind"] for r in recs], [5, 5, 5, 5, 3, 3, 3, 3, 3])
        self.assertTrue(all(r["name_terminated"] for r in recs))

    def test_literal_golden_names_without_nul_use_whole_range(self):
        region = bytes.fromhex("0123456789abcdef") + bytes(8) + b"\x11\x22\x33\x44"
        entry = legacy_entry(b"", raw_region=region)  # block 22 -> name length 16
        rec = records(legacy_archive([entry]))[0]
        self.assertEqual(rec["name_hex"], "4067146789fbc8fa0404015555015455")
        self.assertFalse(rec["name_terminated"])
        self.assertEqual((rec["derived_name_length"], rec["transformed_blocks"]), (16, 2))
        self.assertEqual(rec["encoded_region_bytes"], 20)
        self.assertEqual(rec["encoded_name_sha256"], sha(region[:16]))
        self.assertEqual(rec["encoded_region_sha256"], sha(region))

    def test_name_cut_at_first_nul_inside_derived_length(self):
        rec = records(legacy_archive([legacy_entry(b"ab\0cdefghijk")]))[0]
        self.assertEqual(rec["name_hex"], b"ab".hex())
        self.assertTrue(rec["name_terminated"])
        self.assertEqual(rec["derived_name_length"], 12)

    def test_low_byte_versus_full_block_length(self):
        clear = b"data\\file.txt\0\0\0"  # 16
        region = encode_name_region(clear + b"\xee" * (0x114 - 16), 16)
        # Full block 0x116 places metadata 4 + 0x116 bytes on; its low byte 0x16 = 22
        # gives a name length of 16. Only blocks starting below 16 are transformed.
        entry = legacy_entry(b"", raw_region=region, block_len=0x116)
        nxt = legacy_entry(b"next\0\0")
        recs = records(legacy_archive([entry, nxt]))
        self.assertEqual(recs[0]["block_length"], 0x116)
        self.assertEqual(recs[0]["block_low_byte"], 0x16)
        self.assertEqual(recs[0]["derived_name_length"], 16)
        self.assertEqual(recs[0]["metadata_offset"], 4 + 0x116)
        self.assertEqual(bytes.fromhex(recs[0]["name_hex"]), b"data\\file.txt")
        self.assertEqual(recs[0]["transformed_blocks"], 2)
        self.assertEqual(recs[0]["encoded_region_bytes"], 0x114)
        self.assertEqual(bytes.fromhex(recs[1]["name_hex"]), b"next")
        self.assertEqual(recs[1]["table_offset"], len(entry))

    def test_names_beyond_20_blocks(self):
        long_name = (b"data\\" + b"k" * 190 + b".spr\0")[:200]
        recs = records(legacy_archive([legacy_entry(long_name)]))
        self.assertEqual(recs[0]["transformed_blocks"], 25)
        self.assertEqual(bytes.fromhex(recs[0]["name_hex"]), long_name.rstrip(b"\0"))

    def test_partial_trailing_block_left_unchanged(self):
        # Region 13 bytes -> block 15 -> name length 9: the block at 8 starts before 9
        # but does not fit before the metadata, so name byte 8 stays as stored.
        clear = b"abcdefgh"
        region = encode_name_region(clear, 8) + b"Zxyz\x01"
        rec = records(legacy_archive([legacy_entry(b"", raw_region=region)]))[0]
        self.assertEqual((rec["derived_name_length"], rec["transformed_blocks"],
                          rec["untransformed_name_bytes"]), (9, 1, 1))
        self.assertEqual(bytes.fromhex(rec["name_hex"]), b"abcdefghZ")
        self.assertFalse(rec["name_terminated"])

    def test_zero_name_length_and_runs_past_entry(self):
        rec = records(legacy_archive([legacy_entry(b"", raw_region=b"\x01\x02\x03")]))[0]
        self.assertEqual((rec["block_length"], rec["derived_name_length"], rec["name_hex"]),
                         (5, 0, ""))
        self.assertEqual(rec["header_encryption_flag"], "mixed")  # no dot
        for block_len in (0, 1):
            entry = struct.pack("<I", block_len) + b"\0" * block_len + \
                struct.pack("<IIIBI", 725, 37595, 0, 1, 0) + b"\0" * 8
            with self.subTest(block_len), \
                    self.assertRaisesRegex(ac.SourceRejection, "runs past"):
                ac.catalog_archive_bytes(legacy_archive([entry], count=1))

    def test_native_truncation(self):
        entry = legacy_entry(b"abc\0\0\0")
        with self.assertRaisesRegex(ac.SourceRejection, "incomplete entry"):
            ac.catalog_archive_bytes(legacy_archive([entry[:-1]], count=1))
        with self.assertRaisesRegex(ac.SourceRejection, "unexpected end"):
            ac.catalog_archive_bytes(legacy_archive([entry, b"\x01\x02\x03"], count=2))
        huge = struct.pack("<I", 0xffffff0a) + b"\0\0" + b"x" * 30
        with self.assertRaisesRegex(ac.SourceRejection, "incomplete entry"):
            ac.catalog_archive_bytes(legacy_archive([huge], count=1))

    def test_bias_underflow_clears_file_bit_and_keeps_name(self):
        recs = records(legacy_archive([
            legacy_entry(b"a.gat\0", size_field=715 + 99, real=100, kind=1),   # -1
            legacy_entry(b"b.gat\0", aligned_field=37578, kind=3),             # -1
            legacy_entry(b"c.gat\0", size_field=715 + 50, real=50, aligned_field=37579),
            legacy_entry(b"d.bmp\0", size_field=0, real=0xffffffff, kind=0x41),
        ]))
        self.assertEqual((recs[0]["derived_compressed_size"], recs[0]["compressed_size"],
                          recs[0]["compressed_underflow"], recs[0]["effective_kind"],
                          recs[0]["header_encryption_flag"]), (-1, 0, True, 0, None))
        self.assertEqual(bytes.fromhex(recs[0]["name_hex"]), b"a.gat")
        self.assertEqual((recs[1]["derived_length_aligned"], recs[1]["length_aligned"],
                          recs[1]["aligned_underflow"], recs[1]["effective_kind"]),
                         (-1, 0, True, 2))
        self.assertEqual((recs[2]["compressed_size"], recs[2]["length_aligned"],
                          recs[2]["effective_kind"]), (0, 0, 5))  # zero is not underflow
        self.assertEqual(recs[3]["derived_compressed_size"], -(0xffffffff + 715))
        self.assertEqual((recs[3]["effective_kind"], recs[3]["metadata_filter"]),
                         (0x40, "real_size_over_256MiB"))
        _, _, counts, _ = ac.catalog_archive_bytes(legacy_archive([
            legacy_entry(b"a\0", size_field=0), legacy_entry(b"b\0", aligned_field=0)]))
        self.assertEqual(counts["length_bias_underflows"],
                         {"compressed": 1, "aligned": 1, "any": 2})

    def test_no_file_bit_gets_no_encryption_flag(self):
        rec = records(legacy_archive([legacy_entry(b"dir\0", kind=0)]))[0]
        self.assertEqual((rec["effective_kind"], rec["header_encryption_flag"],
                          rec["metadata_filter"]), (0, None, "file_bit_absent"))

    def test_high_bytes_duplicates_trailing_and_offsets(self):
        name = b"\xb0\xa1\xff\x80\\\x01.spr\0"
        entries = [legacy_entry(name, offset=12), legacy_entry(name)]
        blob = legacy_archive(entries, trailing=b"\x00tail")
        header_, table, counts, lines = ac.catalog_archive_bytes(blob)
        recs = [json.loads(x) for x in lines]
        self.assertEqual(recs[0]["name_hex"], name[:-1].hex())
        self.assertEqual(counts["duplicate_raw_names"], 1)
        self.assertEqual(counts["names_with_high_bytes"], 2)
        self.assertEqual(table["trailing_bytes"], 5)
        self.assertEqual(recs[0]["archive_offset"], header_["table_pos"])
        self.assertEqual(recs[0]["payload_offset_field"], 12)
        self.assertEqual(recs[0]["diagnostic_body_range"], [58, 58 + 16])
        self.assertEqual(recs[0]["archive_sha256"], sha(blob))


# --- Pins, publication and CLI -----------------------------------------------------------

class Fixture:
    """Synthetic pinned input directory, archive root and matching pins."""

    def __init__(self, base):
        self.base = Path(base)
        self.inputs = self.base / "inputs"
        self.root = self.base / "root"
        self.inputs.mkdir()
        self.root.mkdir()
        archives = {
            "event.grf": legacy_archive([legacy_entry(b"data\\a.gat\0\0"),
                                         legacy_entry(b"data\\b.bmp\0\0")]),
            "data0.grf": legacy_archive([legacy_entry(b"x\xb0\xa1.txt\0")]),
            "data.grf": modern_archive([modern_entry(b"data\\c.bmp", 5, 8, 5, 0),
                                        modern_entry(b"data\\d")]),
        }
        ini = b"[Data]\n1=event.grf\n2=data0.grf\n3=data.grf\n"
        self.archive_pins = []
        listed = []
        for name, blob in archives.items():
            (self.root / name).write_bytes(blob)
            self.archive_pins.append({"file": name, "bytes": len(blob), "sha256": sha(blob)})
            h = ac.parse_header(blob[:46])
            listed.append({"file": name, "bytes": len(blob), "sha256": sha(blob),
                           "signature": h["signature"], "header_sha256": h["header_sha256"],
                           "header_version": h["declared_version"],
                           "effective_version": h["effective_version"],
                           "header_record_count": h["record_count"],
                           "table_start": h["table_pos"]})
        manifest = {"archives": listed,
                    "data_ini": {"bytes": len(ini), "sha256": sha(ini),
                                 "ordered_basenames": list(archives)},
                    "ini_bindings": [{"file": n, "same_acquired_archive_file": True}
                                     for n in archives]}
        self.write_inputs(ini, manifest)

    def write_inputs(self, ini, manifest):
        mbytes = json.dumps(manifest).encode()
        (self.inputs / ac.INPUT_INI).write_bytes(ini)
        (self.inputs / ac.INPUT_MANIFEST).write_bytes(mbytes)
        self.input_pins = {ac.INPUT_INI: {"bytes": len(ini), "sha256": sha(ini)},
                           ac.INPUT_MANIFEST: {"bytes": len(mbytes), "sha256": sha(mbytes)}}
        self.manifest = manifest
        self.ini = ini

    def run(self, out="out"):
        return ac.run(self.inputs, self.root, self.base / out, self.archive_pins,
                      self.input_pins)


class PublicationTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.chmod(self.tmp.name, 0o700)
        self.fx = Fixture(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def files(self, out="out"):
        target = self.fx.base / out
        return {p.name: p.read_bytes() for p in sorted(target.iterdir())}

    def test_complete_output_modes_bindings_and_determinism(self):
        target, manifest, hashes = self.fx.run()
        first = self.files()
        self.assertEqual(sorted(first), ["catalog-complete.json", "catalog-manifest.json",
                                         "data.grf.records.jsonl", "data0.grf.records.jsonl",
                                         "event.grf.records.jsonl"])
        self.assertEqual(stat.S_IMODE(os.lstat(target).st_mode), 0o700)
        for name in first:
            self.assertEqual(stat.S_IMODE(os.lstat(target / name).st_mode), 0o600)
        complete = json.loads(first["catalog-complete.json"])
        self.assertEqual(complete["catalog_manifest_sha256"],
                         sha(first["catalog-manifest.json"]))
        for archive in manifest["archives"]:
            rf = archive["records_file"]
            self.assertEqual(sha(first[rf["file"]]), rf["sha256"])
            self.assertEqual(complete["record_files"][rf["file"]], rf["sha256"])
        self.assertEqual([a["file"] for a in manifest["archives"]],
                         ["event.grf", "data0.grf", "data.grf"])
        self.assertEqual(manifest["totals"]["raw_records"], 5)
        self.assertEqual(manifest["totals"]["kind0_promotions"], 1)
        text = first["catalog-manifest.json"].decode()
        self.assertNotIn(str(self.fx.base), text)
        for blob in first.values():
            self.assertNotIn(self.fx.ini, blob)
            self.assertNotIn(str(self.fx.base).encode(), blob)
        self.fx.run("out2")
        second = self.files("out2")
        for name in first:
            if name != "catalog-manifest.json":
                self.assertEqual(first[name], second[name], name)
        self.assertEqual(first["catalog-manifest.json"], second["catalog-manifest.json"])

    def test_existing_targets_unchanged(self):
        base = self.fx.base
        (base / "file").write_bytes(b"keep")
        (base / "dir").mkdir()
        (base / "dir" / "x").write_bytes(b"keep")
        os.symlink(base / "dir", base / "live")
        os.symlink(base / "missing", base / "dangling")
        for name in ("file", "dir", "live", "dangling"):
            with self.subTest(name), self.assertRaises(ac.OutputError):
                self.fx.run(name)
        self.assertEqual((base / "file").read_bytes(), b"keep")
        self.assertEqual(os.listdir(base / "dir"), ["x"])
        self.assertFalse(os.path.lexists(base / "missing"))

    def test_untrusted_parent_refused(self):
        shared = self.fx.base / "shared"
        shared.mkdir()
        os.chmod(shared, 0o777)
        with self.assertRaises(ac.OutputError):
            self.fx.run("shared/out")
        with self.assertRaises(ac.OutputError):
            self.fx.run("absent/out")

    def assert_failed(self, out="out"):
        names = os.listdir(self.fx.base / out)
        self.assertNotIn(ac.OUTPUT_COMPLETE, names)
        return names

    def test_tampered_archive_refused_without_completion(self):
        path = self.fx.root / "data.grf"
        blob = bytearray(path.read_bytes())
        blob[-1] ^= 1
        path.write_bytes(bytes(blob))
        with self.assertRaisesRegex(ac.InputError, "SHA-256"):
            self.fx.run()
        names = self.assert_failed()
        self.assertIn(ac.OUTPUT_FAILED, names)
        marker = json.loads((self.fx.base / "out" / ac.OUTPUT_FAILED).read_bytes())
        self.assertEqual((marker["status"], marker["category"]), ("failed", "input_pin"))

    def test_size_link_and_missing_archive_refused(self):
        path = self.fx.root / "event.grf"
        original = path.read_bytes()
        path.write_bytes(original + b"x")
        with self.assertRaisesRegex(ac.InputError, "pinned"):
            self.fx.run("o1")
        path.unlink()
        with self.assertRaises(ac.InputError):
            self.fx.run("o2")
        (self.fx.base / "real.grf").write_bytes(original)
        os.symlink(self.fx.base / "real.grf", path)
        with self.assertRaisesRegex(ac.InputError, "links"):
            self.fx.run("o3")
        path.unlink()
        path.mkdir()
        with self.assertRaises(ac.InputError):
            self.fx.run("o4")

    def test_linked_roots_refused(self):
        os.symlink(self.fx.root, self.fx.base / "rootlink")
        with self.assertRaises(ac.InputError):
            ac.run(self.fx.inputs, self.fx.base / "rootlink", self.fx.base / "o",
                   self.fx.archive_pins, self.fx.input_pins)
        os.symlink(self.fx.inputs, self.fx.base / "inlink")
        with self.assertRaises(ac.InputError):
            ac.run(self.fx.base / "inlink", self.fx.root, self.fx.base / "o2",
                   self.fx.archive_pins, self.fx.input_pins)
        self.assertFalse(os.path.lexists(self.fx.base / "o2"))

    def test_input_shape_and_pins(self):
        (self.fx.inputs / "extra").write_bytes(b"")
        with self.assertRaisesRegex(ac.InputError, "exactly"):
            self.fx.run()
        (self.fx.inputs / "extra").unlink()
        pins = dict(self.fx.input_pins)
        pins[ac.INPUT_INI] = {"bytes": len(self.fx.ini), "sha256": "0" * 64}
        with self.assertRaisesRegex(ac.InputError, "pin"):
            ac.run(self.fx.inputs, self.fx.root, self.fx.base / "o", self.fx.archive_pins,
                   pins)
        self.assertFalse(os.path.lexists(self.fx.base / "o"))

    def test_input_manifest_relationships(self):
        bad_order = json.loads(json.dumps(self.fx.manifest))
        bad_order["data_ini"]["ordered_basenames"].reverse()
        bad_ini = json.loads(json.dumps(self.fx.manifest))
        bad_ini["data_ini"]["sha256"] = "1" * 64
        bad_archive = json.loads(json.dumps(self.fx.manifest))
        bad_archive["archives"][1]["sha256"] = "2" * 64
        bad_fact = json.loads(json.dumps(self.fx.manifest))
        bad_fact["archives"][2]["table_start"] += 1
        for i, manifest in enumerate((bad_order, bad_ini, bad_archive, bad_fact)):
            with self.subTest(i):
                self.fx.write_inputs(self.fx.ini, manifest)
                with self.assertRaises(ac.InputError):
                    self.fx.run(f"o{i}")
                if os.path.lexists(self.fx.base / f"o{i}"):
                    self.assert_failed(f"o{i}")

    def test_unsupported_and_rejected_archive_leave_no_completion(self):
        path = self.fx.root / "data0.grf"
        blob = bytearray(path.read_bytes())
        blob[42:46] = struct.pack("<I", 0x103)
        path.write_bytes(bytes(blob))
        self.fx.archive_pins[1]["sha256"] = sha(bytes(blob))
        self.fx.manifest["archives"][1]["sha256"] = sha(bytes(blob))
        self.fx.write_inputs(self.fx.ini, self.fx.manifest)
        with self.assertRaises(ac.Unsupported):
            self.fx.run()
        names = self.assert_failed()
        self.assertIn("event.grf.records.jsonl", names)  # partial output stays, marked

    def test_completion_readback_failure_removes_completion(self):
        real = ac._verify_published

        def failing(dir_fd, name, size, digest):
            if name == ac.OUTPUT_COMPLETE:
                raise ac.OutputError("simulated readback mismatch")
            return real(dir_fd, name, size, digest)

        with mock.patch.object(ac, "_verify_published", failing):
            with self.assertRaisesRegex(ac.OutputError, "readback"):
                self.fx.run()
        self.assert_failed()

    def test_unexpected_exception_after_completion_cleans_up(self):
        # Inputs are pre-verified here so the only directory listing is the final
        # output check, which runs after the completion record was written.
        real = os.listdir

        def boom(arg="."):
            if isinstance(arg, int):
                raise RuntimeError("simulated ordinary bug")
            return real(arg)

        verified = (self.fx.manifest, {ac.INPUT_INI: self.fx.ini})
        with mock.patch.object(ac, "read_inputs", lambda d, p: verified), \
                mock.patch.object(ac.os, "listdir", boom):
            with self.assertRaisesRegex(ac.OutputError, "unexpected: simulated"):
                self.fx.run()
        names = self.assert_failed()
        self.assertIn(ac.OUTPUT_FAILED, names)

    def test_foreign_file_in_output_detected(self):
        real = ac._write_new

        def plant(dir_fd, name, data, created):
            real(dir_fd, name, data, created)
            if name == ac.OUTPUT_MANIFEST:
                fd = os.open("foreign", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600,
                             dir_fd=dir_fd)
                os.close(fd)

        with mock.patch.object(ac, "_write_new", plant):
            with self.assertRaisesRegex(ac.OutputError, "did not write"):
                self.fx.run()
        names = self.assert_failed()
        self.assertIn("foreign", names)  # preserved

    def test_cli_pins_cannot_be_bypassed(self):
        out = self.fx.base / "cli"
        with mock.patch("sys.stderr"):
            code = ac.main([str(self.fx.inputs), str(self.fx.root), str(out)])
        self.assertEqual(code, 2)
        self.assertFalse(os.path.lexists(out))


@unittest.skipUnless(
    os.path.isabs(os.environ.get("T06_CLIENT_INPUTS", "x")) and
    os.path.isabs(os.environ.get("T06_ARCHIVE_ROOT", "x")) and
    os.path.isdir(os.environ.get("T06_CLIENT_INPUTS", "")) and
    os.path.isdir(os.environ.get("T06_ARCHIVE_ROOT", "")),
    "set absolute T06_CLIENT_INPUTS and T06_ARCHIVE_ROOT to run the pinned-input test")
class ActualInputTests(unittest.TestCase):

    def test_pinned_cli_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.chmod(tmp, 0o700)
            out = Path(tmp) / "catalog"
            with mock.patch("sys.stdout"):
                code = ac.main([os.environ["T06_CLIENT_INPUTS"],
                                os.environ["T06_ARCHIVE_ROOT"], str(out)])
            self.assertEqual(code, 0)
            manifest = json.loads((out / ac.OUTPUT_MANIFEST).read_bytes())
            self.assertEqual([a["file"] for a in manifest["archives"]],
                             ["event.grf", "data0.grf", "data.grf"])
            self.assertEqual([a["header"]["layout"] for a in manifest["archives"]],
                             ["legacy", "legacy", "0x300"])
            for archive in manifest["archives"]:
                rf = archive["records_file"]
                self.assertEqual(rf["lines"], archive["header"]["record_count"])
                self.assertEqual(rf["lines"], archive["counts"]["raw_records"])
                ordinals = 0
                with open(out / rf["file"], "rb") as handle:
                    for line in handle:
                        rec = json.loads(line)
                        self.assertEqual(rec["ordinal"], ordinals)
                        ordinals += 1
                self.assertEqual(ordinals, rf["lines"])


if __name__ == "__main__":
    unittest.main()
