"""Tests for map_cache_inventory. Run: python3 -I -m unittest discover -s tools/renewal

Index files, cache files and candidates are small in-memory synthetic fixtures;
only the verification and publication tests write temporary directories. Tests
marked "native" check the modelled C++ behaviour; tests marked "strict" check the
additional validator policy, which refuses data the C++ code would read anyway.
The pinned-input test reads the canonical inputs from the absolute paths in
$MAP_CACHE_SNAPSHOT and $MAP_CACHE_SELECTION and is skipped when they are unset
or absent. There is no way to bypass the CLI pins.
"""

import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import sys
import tempfile
import unittest
from unittest import mock
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent))
import map_cache_inventory as mci  # noqa: E402


def sha(data):
    return hashlib.sha256(data).hexdigest()


def entry(name, xs, ys, cells=None, payload=None, raw_name=None, length=None):
    """One cache record: 20-byte header plus payload (default: zlib of the cells)."""
    if payload is None:
        if cells is None:
            cells = bytes([0]) * max(xs * ys, 0)
        payload = zlib.compress(cells)
    name_field = raw_name if raw_name is not None else name.encode().ljust(12, b"\0")
    return struct.pack("<12shhi", name_field, xs, ys,
                       len(payload) if length is None else length) + payload


def cache(*entries, count=None, file_size=None, padding=b"\0\0", trailing=b""):
    body = b"".join(entries) + trailing
    size = 8 + len(body) if file_size is None else file_size
    return struct.pack("<IH", size, len(entries) if count is None else count) + padding + body


def scan(chunk):
    return mci.scan_index_line(chunk)


def index_of(main, imp=None):
    files = {"db/map_index.txt": main}
    if imp is not None:
        files["db/import/map_index.txt"] = imp
    return mci.build_index(files, "db")


def candidates(*names):
    return [{"name": n, "raw": n, "file": "conf/maps_athena.conf", "line": i + 1}
            for i, n in enumerate(names)]


def inventory(main, caches, names, imp=b""):
    """Run the pure model. caches: {path: bytes}. Returns (index, caches, results)."""
    files = {"db/map_index.txt": main, "db/import/map_index.txt": imp, **caches}
    index, catalog, _, _, results = mci.build_inventory(files, candidates(*names))
    return index, catalog, results


def disposition(results):
    return [r["disposition"] for r in results]


MAIN = "db/map_cache.dat"
RE = "db/re/map_cache.dat"
IMPORT = "db/import/map_cache.dat"


class ScannerTests(unittest.TestCase):
    """native: sscanf("%11s\\t%d") and fgets(1024) on map_index.txt."""

    def test_eleven_byte_name_then_digits(self):
        self.assertEqual(scan(b"abcdefghijk7\n"), (2, b"abcdefghijk", 7))
        self.assertEqual(scan(b"abcdefghijkl 7\n"), (1, b"abcdefghijk", None))

    def test_short_token_is_one_conversion(self):
        self.assertEqual(scan(b"x010\n"), (1, b"x010", None))

    def test_decimal_prefix_and_junk(self):
        self.assertEqual(scan(b"x 010\n"), (2, b"x", 10))
        self.assertEqual(scan(b"x 0x10\n"), (2, b"x", 0))
        self.assertEqual(scan(b"x\t+5junk\n"), (2, b"x", 5))
        self.assertEqual(scan(b"x -12\n"), (2, b"x", -12))
        self.assertEqual(scan(b"x -\n"), (1, b"x", None))
        self.assertEqual(scan(b"x junk 5\n"), (1, b"x", None))

    def test_whitespace(self):
        self.assertEqual(scan(b"   \t\r\n"), (-1, None, None))
        self.assertEqual(scan(b" \tx  \t  7"), (2, b"x", 7))
        self.assertEqual(scan(b"x\v\f7\n"), (2, b"x", 7))   # VT/FF are C white space
        self.assertEqual(scan(b"x\r\n"), (1, b"x", None))

    def test_int32_bounds(self):
        self.assertEqual(scan(b"x -2147483648")[2], mci.INT32_MIN)
        self.assertEqual(scan(b"x 2147483647")[2], mci.INT32_MAX)
        with self.assertRaises(mci.InventoryError):
            scan(b"x 2147483648")
        with self.assertRaises(mci.InventoryError):
            scan(b"x -2147483649")

    def test_comments_only_at_column_zero(self):
        index = index_of(b"//a 5\n //b 6\nc 7 // trailing\n")
        self.assertEqual([(e["scanned"], e["requested"]) for e in index.events],
                         [("//b", 6), ("c", 7)])
        self.assertEqual(index.reads[0]["comments"], 1)

    def test_fgets_chunks_split_overlong_lines(self):
        line = b"a" * 1022 + b"\n"                  # exactly 1023 bytes incl. newline
        self.assertEqual([c[3] for c in mci.fgets_chunks(line, "f")], [line])
        long = b"a" * 1023 + b"\n"
        self.assertEqual([c[3] for c in mci.fgets_chunks(long, "f")], [b"a" * 1023, b"\n"])
        # Continuation chunks are read as new "lines": one starting with // is skipped,
        # one holding "b 5" becomes a record on the same physical line.
        data = b"x" * 1023 + b"//c 9\n" + b" " * 1023 + b"b 5\n"
        index = index_of(data)
        self.assertEqual([(e["scanned"], e["requested"], e["line"], e["chunk"])
                          for e in index.events],
                         [("xxxxxxxxxxx", 0, 1, 0), ("b", 5, 2, 1)])
        self.assertEqual(index.reads[0]["comments"], 1)

    def test_unsupported_bytes_refused(self):
        for bad in (b"a\0 1\n", b"\xe5 1\n", b"a\x01 1\n", b"a\x7f 1\n"):
            with self.assertRaises(mci.InventoryError):
                index_of(bad)


class IndexTests(unittest.TestCase):
    """native: mapindex_addmap state."""

    def test_special_minus_one_and_last_index(self):
        index = index_of(b"a\t-1\nb\nc\n")
        self.assertEqual([e["resolved"] for e in index.events], [1, 0, 1])
        self.assertEqual([e["last_index"] for e in index.events], [-1, 0, 1])
        self.assertEqual(index.forward, {0: b"b", 1: b"c"})
        self.assertEqual(index.reverse, {b"b": 0, b"c": 1})
        self.assertEqual(index.events[2]["replaced"], "a")
        self.assertEqual(index.max_index, 2)

    def test_special_finds_first_gap_or_loop_end(self):
        index = index_of(b"a 1\nb 3\nc -1\nd -1\n")
        self.assertEqual([e["resolved"] for e in index.events], [1, 3, 2, 4])

    def test_coupled_forward_reverse_overwrite(self):
        index = index_of(b"A 1\nA 2\nB 1\n")
        self.assertEqual(index.forward, {1: b"B", 2: b"A"})
        self.assertEqual(index.reverse, {b"B": 1})
        self.assertEqual(index.lookup(b"A"), (b"A", None))
        self.assertEqual(index.events[1]["reverse_reassigned_from"], 1)

    def test_implicit_ids_continue_across_files(self):
        index = index_of(b"x 10\n", b"y\n// z\nw 3\nv\n")
        self.assertEqual([(e["file"], e["resolved"]) for e in index.events],
                         [("db/map_index.txt", 10), ("db/import/map_index.txt", 11),
                          ("db/import/map_index.txt", 3), ("db/import/map_index.txt", 4)])
        self.assertEqual(index.max_index, 12)   # an upper bound, not the entry count
        self.assertEqual(len(index.forward), 4)

    def test_rejected_ids_still_update_last_index(self):
        index = index_of(b"a 1999\nb 2000\nc\nd -5\ne\n")
        self.assertEqual([e["result"] for e in index.events],
                         ["stored", "rejected_out_of_range", "rejected_out_of_range",
                          "rejected_out_of_range", "rejected_out_of_range"])
        self.assertEqual([e["last_index"] for e in index.events], [1999, 2000, 2001, -5, -4])
        self.assertEqual(index.max_index, 2000)
        self.assertEqual(index.forward, {1999: b"a"})

    def test_empty_name_rejected_after_range(self):
        index = index_of(b".gat 3\n.GAT 2500\n")
        self.assertEqual([e["result"] for e in index.events],
                         ["rejected_empty_name", "rejected_out_of_range"])
        self.assertEqual(index.max_index, 0)

    def test_implicit_overflow_refused(self):
        with self.assertRaises(mci.InventoryError):
            index_of(b"a 2147483647\nb\n")

    def test_zero_is_stored_but_lookup_is_false(self):
        index = index_of(b"z 0\n")
        self.assertEqual(index.forward, {0: b"z"})
        _, _, results = inventory(b"z 0\n", {MAIN: cache(entry("z", 2, 2))}, ["z"])
        self.assertEqual(results[0]["disposition"], "discarded_not_found")
        self.assertEqual(results[0]["reasons"], ["index_zero"])

    def test_name_normalisation(self):
        self.assertEqual(mci.getmapname(b"Foo.GaT")[0], b"Foo")
        self.assertEqual(mci.getmapname(b"abcdefghijk.gat")[0], b"abcdefghijk")
        # 16 bytes: the strnlen bound gives 15, ".ga" + "t" is not a suffix.
        self.assertEqual(mci.getmapname(b"abcdefghijkl.gat"),
                         (b"abcdefghijk", ["too_long_warning", "clipped"]))
        self.assertEqual(mci.getmapname(b"Foo.gat.gat")[0], b"Foo.gat")
        index = index_of(b"Foo.GAT 3\nfoo 4\n")
        self.assertEqual(index.reverse, {b"Foo": 3, b"foo": 4})   # case-sensitive keys

    def test_main_missing_fatal_import_missing_warns(self):
        with self.assertRaises(mci.InventoryError):
            mci.build_index({"db/import/map_index.txt": b"a 1\n"}, "db")
        index = mci.build_index({"db/map_index.txt": b"a 1\n"}, "db")
        self.assertEqual(index.reads[1], {"path": "db/import/map_index.txt", "present": False})
        self.assertEqual(index.diagnostics[0]["kind"], "index_import_missing_warning")

    def test_db_path_is_configurable_for_index_only(self):
        files = {"db2/map_index.txt": b"a 1\n", MAIN: cache(entry("a", 1, 1))}
        index, catalog, _, _, results = mci.build_inventory(files, candidates("a"), "db2")
        self.assertEqual(index.reverse, {b"a": 1})
        self.assertEqual(results[0]["disposition"], "retained")


class CacheTests(unittest.TestCase):

    def test_native_precedence_and_first_match(self):
        caches = {IMPORT: cache(entry("a", 1, 1)), RE: cache(entry("a", 2, 2)),
                  MAIN: cache(entry("a", 3, 3), entry("a", 4, 4))}
        _, _, results = inventory(b"a 1\n", caches, ["a"])
        self.assertEqual(results[0]["cache"], {"file": IMPORT, "ordinal": 0})
        self.assertEqual([a["outcome"] for a in results[0]["attempts"]], ["read"])

    def test_native_case_sensitive_and_no_gat_strip(self):
        caches = {MAIN: cache(entry("Prontera", 1, 1), entry("a.gat", 1, 1))}
        _, _, results = inventory(b"prontera 1\na 2\n", caches, ["prontera", "a"])
        self.assertEqual(disposition(results), ["discarded_not_found"] * 2)
        self.assertEqual(results[0]["reasons"], ["cache_not_read"])

    def test_native_invalid_first_match_falls_to_next_file(self):
        caches = {IMPORT: cache(entry("a", 0, 5, payload=b""), entry("a", 2, 2)),
                  RE: cache(entry("a", 513, 513, payload=b"")),
                  MAIN: cache(entry("a", 3, 3))}
        _, _, results = inventory(b"a 1\n", caches, ["a"])
        self.assertEqual([(a["file"], a["outcome"], a["ordinal"])
                          for a in results[0]["attempts"]],
                         [(IMPORT, "invalid_dimensions", 0),
                          (RE, "exceeds_max_map_size", 0), (MAIN, "read", 0)])
        self.assertEqual(results[0]["cache"], {"file": MAIN, "ordinal": 0})

    def test_native_invalid_everywhere_is_discard(self):
        caches = {MAIN: cache(entry("a", -1, 4, payload=b""), entry("a", 1, 1))}
        _, _, results = inventory(b"a 1\n", caches, ["a"])
        self.assertEqual(results[0]["disposition"], "discarded_not_found")
        self.assertEqual(results[0]["reasons"], ["cache_not_read"])

    def test_native_dimension_product_limit(self):
        caches = {MAIN: cache(entry("wide", 1, 1024), entry("max", 512, 512),
                              entry("over", 16, 16385, payload=b"x"))}
        _, catalog, results = inventory(b"wide 1\nmax 2\nover 3\n", caches,
                                        ["wide", "max", "over"])
        self.assertEqual(disposition(results), ["retained", "retained", "discarded_not_found"])
        self.assertEqual([e["dimensions"] for e in catalog[2]["entries"]],
                         ["valid", "valid", "exceeds_max_map_size"])

    def test_native_cell_types_and_unknown_values(self):
        cells = bytes([0, 1, 2, 3, 4, 5, 6, 7, 200, 2])
        _, catalog, results = inventory(b"a 1\n", {MAIN: cache(entry("a", 10, 1, cells))}, ["a"])
        record = catalog[2]["entries"][0]
        self.assertEqual(record["decode"], "ok")
        self.assertEqual(record["cell_histogram"],
                         {"0": 1, "1": 1, "2": 2, "3": 1, "4": 1, "5": 1, "6": 1})
        self.assertEqual(record["unknown_cell_values"], {"7": 1, "200": 1})
        self.assertEqual(record["decoded_sha256"], sha(cells))
        self.assertEqual(results[0]["disposition"], "retained")
        # 2/4/6 share flags but stay distinct bytes and hashes.
        two = inventory(b"a 1\n", {MAIN: cache(entry("a", 1, 1, b"\x02"))}, ["a"])[1]
        six = inventory(b"a 1\n", {MAIN: cache(entry("a", 1, 1, b"\x06"))}, ["a"])[1]
        self.assertNotEqual(two[2]["entries"][0]["decoded_sha256"],
                            six[2]["entries"][0]["decoded_sha256"])

    def test_missing_cache_file_logged_and_skipped(self):
        files = {"db/map_index.txt": b"a 1\n", MAIN: cache(entry("a", 1, 1))}
        _, catalog, diagnostics, _, results = mci.build_inventory(files, candidates("a"))
        self.assertEqual([c["present"] for c in catalog], [False, False, True])
        self.assertEqual(len(diagnostics), 2)
        self.assertEqual([a["file"] for a in results[0]["attempts"]], [MAIN])

    def test_empty_cache_file_finds_nothing(self):
        _, catalog, results = inventory(b"a 1\n", {MAIN: cache()}, ["a"])
        self.assertEqual(catalog[2]["status"], "safe")
        self.assertEqual(results[0]["disposition"], "discarded_not_found")


class StrictPayloadTests(unittest.TestCase):
    """strict: decoder failures are unsafe, never a native fallback or discard."""

    def decode(self, payload, xs=2, ys=2, name="a"):
        _, catalog, results = inventory(b"a 1\n", {MAIN: cache(entry(name, xs, ys,
                                                                      payload=payload))}, ["a"])
        return catalog[2]["entries"][0], results[0]

    def test_valid(self):
        record, result = self.decode(zlib.compress(b"\0" * 4))
        self.assertEqual((record["decode"], result["disposition"]), ("ok", "retained"))

    def test_corrupt_checksum(self):
        good = bytearray(zlib.compress(b"\0" * 4))
        good[-1] ^= 1
        record, result = self.decode(bytes(good))
        self.assertTrue(record["decode_problem"].startswith("zlib_error"))
        self.assertEqual(result["disposition"], "unresolved_unsafe")
        self.assertEqual(result["attempts"][0]["outcome"], "unresolved_unsafe_payload")

    def test_short_long_truncated_trailing_empty(self):
        cases = {
            "decoded_shorter_than_expected": zlib.compress(b"\0" * 3),
            "decoded_longer_than_expected": zlib.compress(b"\0" * 5),
            "truncated_stream": zlib.compress(b"\0" * 4)[:-3],
            "trailing_data_after_stream": zlib.compress(b"\0" * 4) + b"x",
        }
        for problem, payload in cases.items():
            with self.subTest(problem):
                record, result = self.decode(payload)
                self.assertEqual(record["decode_problem"], problem)
                self.assertEqual(result["disposition"], "unresolved_unsafe")
        record, _ = self.decode(b"")
        self.assertEqual(record["decode_problem"], "truncated_stream")

    def test_bomb_is_bounded(self):
        payload = zlib.compress(b"\0" * (64 << 20), 9)
        record, result = self.decode(payload, 1, 1)
        self.assertEqual(record["decode_problem"], "decoded_longer_than_expected")
        self.assertEqual(record["decoded_bytes"], 2)
        self.assertEqual(result["disposition"], "unresolved_unsafe")

    def test_aggregate_limit(self):
        with mock.patch.dict(mci.WORK_LIMITS, {"max_decoded_bytes_total": 7}):
            with self.assertRaises(mci.InventoryError):
                inventory(b"", {MAIN: cache(entry("a", 2, 2), entry("b", 2, 2))}, [])

    def test_error_and_lookahead_work_is_reserved_before_inflate(self):
        good = zlib.compress(bytes(4))
        checksum_bad = good[:-1] + bytes([good[-1] ^ 1])
        for payload in (checksum_bad, zlib.compress(bytes(5))):
            with self.subTest(payload=payload):
                budget = {"decoded": 0}
                real = mci.zlib.decompressobj
                with mock.patch.dict(mci.WORK_LIMITS, {"max_decoded_bytes_total": 9}), \
                        mock.patch.object(mci.zlib, "decompressobj", wraps=real) as factory:
                    _, problem = mci.decode_record(payload, 4, budget)
                    self.assertIsNotNone(problem)
                    self.assertEqual(budget["decoded"], 5)
                    with self.assertRaises(mci.InventoryError):
                        mci.decode_record(payload, 4, budget)
                    self.assertEqual(factory.call_count, 1)
                    self.assertEqual(budget["decoded"], 5)

    def test_exact_reservation_boundary(self):
        payload = zlib.compress(bytes(4))
        with mock.patch.dict(mci.WORK_LIMITS, {"max_decoded_bytes_total": 5}):
            budget = {"decoded": 0}
            fields, problem = mci.decode_record(payload, 4, budget)
            self.assertIsNone(problem)
            self.assertEqual(fields["decoded_bytes"], 4)
            self.assertEqual(budget["decoded"], 5)
        with mock.patch.dict(mci.WORK_LIMITS, {"max_decoded_bytes_total": 4}), \
                mock.patch.object(mci.zlib, "decompressobj") as factory:
            with self.assertRaises(mci.InventoryError):
                mci.decode_record(payload, 4, {"decoded": 0})
            factory.assert_not_called()

    def test_prior_unsafe_candidate_invalidates_later_occupancy_and_slots(self):
        good = zlib.compress(bytes(4))
        bad = good[:-1] + bytes([good[-1] ^ 1])
        files = {"db/map_index.txt": b"before 3\nA 1\nB 2\n",
                 MAIN: cache(entry("before", 1, 1), entry("A.gat", 2, 2, payload=bad),
                             entry("A", 2, 2), entry("B", 1, 1))}
        names = ["before", "A.gat", "A", "B", "missing"]
        manifest = mci.build_manifest(files, selection_doc(names), PROVENANCE)
        rows = manifest["candidates"]
        self.assertEqual(manifest["status"], "incomplete")
        self.assertEqual(disposition(rows), ["retained", "unresolved_unsafe"]
                         + ["unresolved_due_to_prior_candidate"] * 3)
        self.assertEqual(rows[0]["slot"], 0)
        for row in rows[1:]:
            self.assertNotIn("slot", row)
            self.assertNotIn("index_id", row)
            self.assertEqual(row["uncertainty_since_ordinal"], 1)
        self.assertEqual(rows[2]["index_lookup"]["id"], 1)
        self.assertEqual(rows[3]["index_lookup"]["id"], 2)
        self.assertEqual(rows[2]["attempts"][-1]["outcome"], "read")
        self.assertEqual(rows[4]["attempts"][-1]["outcome"], "not_found")
        self.assertEqual(rows[3]["config_line"], 4)

    def test_unsafe_attempt_precedes_index_check(self):
        """An unindexed candidate whose cache record is corrupt is unresolved, not discarded."""
        caches = {MAIN: cache(entry("a", 2, 2, payload=b"junk"))}
        _, _, results = inventory(b"", caches, ["a"])
        self.assertEqual(results[0]["disposition"], "unresolved_unsafe")
        self.assertIsNone(results[0]["index_lookup"]["id"])

    def test_unused_unsafe_record_makes_result_incomplete(self):
        files = {"db/map_index.txt": b"a 1\n",
                 MAIN: cache(entry("a", 1, 1), entry("unused", 2, 2, payload=b"junk"))}
        manifest = mci.build_manifest(files, selection_doc(["a"]), PROVENANCE)
        self.assertEqual(manifest["status"], "incomplete")
        self.assertEqual(manifest["summary"]["dispositions"], {"retained": 1})
        self.assertEqual(manifest["summary"]["cache_entries_decode_unsafe"], 1)


class StrictStructureTests(unittest.TestCase):
    """strict: structural rules; 'native' would read these, the policy refuses them."""

    def catalog(self, data, names=("a",), index=b"a 1\n"):
        _, catalog, results = inventory(index, {MAIN: data}, list(names))
        return catalog[2], results

    def assert_unsafe(self, data, kind, outcome="unresolved_unsafe_file"):
        record, results = self.catalog(data)
        self.assertEqual(record["status"], "unsafe")
        self.assertIn(kind, [p["kind"] for p in record["problems"]])
        self.assertEqual(results[0]["disposition"], "unresolved_unsafe")
        self.assertEqual(results[0]["attempts"][0]["outcome"], outcome)
        return record

    def test_negative_length(self):
        record = self.assert_unsafe(cache(entry("b", 1, 1, payload=b"", length=-20),
                                          entry("a", 1, 1)), "negative_length")
        self.assertEqual(record["catalogued_entries"], 1)

    def test_truncated_headers_and_payload(self):
        self.assert_unsafe(b"\x08\0\0", "main_header_truncated")
        self.assert_unsafe(cache(count=1, file_size=8), "entry_header_truncated")
        self.assert_unsafe(cache(entry("b", 1, 1, payload=b"", length=50)), "payload_truncated")

    def test_name_rules(self):
        self.assert_unsafe(cache(entry("", 1, 1, raw_name=b"abcdefghijkl")), "name_missing_nul",
                           "unresolved_unsafe_name")
        self.assert_unsafe(cache(entry("", 1, 1, raw_name=b"\xe5\0" + b"\0" * 10)),
                           "unsupported_name_encoding", "unresolved_unsafe_name")
        self.assert_unsafe(cache(entry("", 1, 1, raw_name=b"a\0x" + b"\0" * 9)),
                           "name_padding_nonzero")

    def test_header_policy(self):
        self.assert_unsafe(cache(entry("a", 1, 1), file_size=99), "header_file_size_mismatch")
        self.assert_unsafe(cache(entry("a", 1, 1), padding=b"\0\1"), "header_padding_nonzero")
        self.assert_unsafe(cache(entry("a", 1, 1), trailing=b"\0"),
                           "trailing_bytes_after_last_entry")

    def test_unsafe_file_blocks_fallback(self):
        caches = {IMPORT: cache(entry("a", 1, 1), trailing=b"x"), MAIN: cache(entry("a", 1, 1))}
        _, _, results = inventory(b"a 1\n", caches, ["a"])
        self.assertEqual([a["outcome"] for a in results[0]["attempts"]],
                         ["unresolved_unsafe_file"])

    def test_unsafe_name_makes_whole_file_unresolved(self):
        """strict: natively "a" matches before the bad name, but the file is refused."""
        data = cache(entry("a", 1, 1), entry("", 1, 1, raw_name=b"x" * 12))
        _, catalog, results = inventory(b"a 1\nb 2\n", {RE: data, MAIN: cache(entry("b", 1, 1))},
                                        ["a", "b"])
        self.assertEqual(disposition(results), ["unresolved_unsafe", "unresolved_unsafe"])
        self.assertEqual(results[1]["attempts"][0]["outcome"], "unresolved_unsafe_name")


class ReconcileTests(unittest.TestCase):
    """native: ordered retention in map_readallmaps."""

    def test_second_lookup_normalisation(self):
        # Selection stored "Foo.gat" for raw "Foo.gat.gat"; the cache compares it raw,
        # mapindex_name2idx strips .gat again.
        caches = {MAIN: cache(entry("Foo.gat", 1, 1), entry("Foo", 1, 1))}
        _, _, results = inventory(b"Foo 1\n", caches, ["Foo.gat"])
        self.assertEqual(results[0]["disposition"], "retained")
        self.assertEqual(results[0]["cache"], {"file": MAIN, "ordinal": 0})
        self.assertEqual(results[0]["index_lookup"], {"normalised": "Foo", "id": 1})

    def test_duplicate_index_and_compaction(self):
        caches = {MAIN: cache(entry("a", 1, 1), entry("a.gat", 1, 1), entry("c", 1, 1),
                              entry("d", 1, 1))}
        _, _, results = inventory(b"a 1\nc 2\nd 3\n", caches,
                                  ["a", "gone", "a.gat", "c", "a", "d"])
        self.assertEqual(disposition(results),
                         ["retained", "discarded_not_found", "discarded_duplicate_index",
                          "retained", "discarded_duplicate_index", "retained"])
        self.assertEqual([r.get("slot") for r in results], [0, None, None, 1, None, 2])
        self.assertEqual(results[2]["duplicate_of_ordinal"], 0)
        self.assertEqual(results[1]["reasons"], ["index_missing", "cache_not_read"])
        self.assertEqual([(r["ordinal"], r["config_line"]) for r in results],
                         [(i, i + 1) for i in range(6)])

    def test_cache_read_but_unindexed(self):
        _, _, results = inventory(b"", {MAIN: cache(entry("a", 1, 1))}, ["a"])
        self.assertEqual(results[0]["reasons"], ["index_missing"])
        self.assertEqual(results[0]["attempts"][0]["outcome"], "read")


# --- Selection, profile and publication -------------------------------------------

PROVENANCE = {"generator": {"tool": "test"}, "inputs": {"test": True}}


def selection_doc(names, db_path="db", use_grf=0, **overrides):
    doc = {
        "status": "complete",
        "generator": dict(mci.SELECTION_GENERATOR),
        "input": {"snapshot_manifest_sha256": "f" * 64, "files": 2, "bytes": 3},
        "profile": {"name": mci.SELECTION_PROFILE_NAME, "renewal": True},
        "settings": {"db_path": [{"effective": db_path, "raw": db_path, "truncated": False}],
                     "use_grf": [{"effective": use_grf, "raw": "x"}]},
        "maps": {"candidates": candidates(*names), "candidate_count": len(names)},
    }
    doc.update(overrides)
    return doc


def selection_files(doc, binding=None):
    manifest = json.dumps(doc).encode()
    complete = json.dumps({"generator_version": "1.0.1",
                           "selection_manifest": "selection-manifest.json",
                           "selection_manifest_sha256": binding or sha(manifest)}).encode()
    found = {"selection-manifest.json": manifest, "selection-complete.json": complete}
    pins = {k: {"bytes": len(v), "sha256": sha(v)} for k, v in found.items()}
    return found, pins


class ProfileTests(unittest.TestCase):

    def test_supported_profile_uses_final_values(self):
        settings = {"db_path": [{"effective": "db2"}, {"effective": "db", "truncated": False}],
                    "use_grf": [{"effective": 1}, {"effective": 0}]}
        self.assertEqual(mci.effective_profile(settings)["use_grf"], {"effective": 0})

    def test_refusals(self):
        bad = [
            {"db_path": [{"effective": "db2"}], "use_grf": [{"effective": 0}]},
            {"db_path": [{"effective": "db", "truncated": True}], "use_grf": [{"effective": 0}]},
            {"use_grf": [{"effective": 0}]},
            {"db_path": [{"effective": "db"}], "use_grf": [{"effective": 1}]},
            {"db_path": [{"effective": "db"}], "use_grf": [{"effective": -1}]},
            {"db_path": [{"effective": "db"}], "use_grf": [{"effective": None}]},
            {"db_path": [{"effective": "db"}], "use_grf": [{"effective": False}]},
            {"db_path": [{"effective": "db"}]},
        ]
        for settings in bad:
            with self.subTest(settings=settings), self.assertRaises(mci.InventoryError):
                mci.effective_profile(settings)

    def test_nonzero_use_grf_applies_no_cache(self):
        files = {"db/map_index.txt": b"a 1\n", MAIN: cache(entry("a", 1, 1))}
        with self.assertRaisesRegex(mci.InventoryError, "GRF"):
            mci.build_manifest(files, selection_doc(["a"], use_grf=1), PROVENANCE)


class SelectionTests(unittest.TestCase):

    def verify(self, found, pins, sha_="f" * 64):
        return mci.verify_selection(found, sha_, {"files": 2, "bytes": 3}, pins)

    def test_accepts_bound_selection(self):
        found, pins = selection_files(selection_doc(["a"]))
        self.assertEqual(self.verify(found, pins)["status"], "complete")

    def test_default_pins_refuse_synthetic_input(self):
        found, _ = selection_files(selection_doc(["a"]))
        with self.assertRaisesRegex(mci.InventoryError, "pinned"):
            self.verify(found, mci.SELECTION_PINS)

    def test_refusals(self):
        cases = {
            "tampered": None,
            "unbound": dict(binding="0" * 64),
            "status": dict(doc=selection_doc(["a"], status="incomplete")),
            "generator": dict(doc=selection_doc(["a"], generator={"version": "1.0.0"})),
            "snapshot": dict(sha_="e" * 64),
            "profile": dict(doc=selection_doc(["a"], profile={"name": mci.SELECTION_PROFILE_NAME,
                                                              "renewal": False})),
            "count": dict(doc=selection_doc(["a"], maps={"candidates": candidates("a"),
                                                         "candidate_count": 2})),
        }
        for label, case in cases.items():
            with self.subTest(label):
                case = case or {}
                found, pins = selection_files(case.get("doc", selection_doc(["a"])),
                                              case.get("binding"))
                if label == "tampered":
                    found["selection-manifest.json"] += b" "
                with self.assertRaises(mci.InventoryError):
                    self.verify(found, pins, case.get("sha_", "f" * 64))

    def test_directory_shape_and_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp, "sel")
            root.mkdir()
            found, _ = selection_files(selection_doc(["a"]))
            for name, body in found.items():
                Path(root, name).write_bytes(body)
            self.assertEqual(mci.read_selection_dir(root), found)
            link = Path(tmp, "link")
            link.symlink_to(root)
            with self.assertRaises(mci.InventoryError):
                mci.read_selection_dir(link)
            Path(root, "extra").write_bytes(b"")
            with self.assertRaises(mci.InventoryError):
                mci.read_selection_dir(root)
            Path(root, "extra").unlink()
            Path(root, "selection-complete.json").unlink()
            Path(root, "selection-complete.json").symlink_to(Path(tmp, "elsewhere"))
            with self.assertRaises(mci.InventoryError):
                mci.read_selection_dir(root)

    def test_cli_refuses_unpinned_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            snap = Path(tmp, "snap")
            snap.mkdir()
            Path(snap, "snapshot-manifest.json").write_bytes(b'{"files": []}')
            os.chmod(tmp, 0o700)
            with self.assertRaisesRegex(mci.InventoryError, "snapshot"):
                mci.run(snap, Path(tmp, "sel"), Path(tmp, "out"))
            self.assertFalse(Path(tmp, "out").exists())


def sample_manifest():
    files = {"db/map_index.txt": b"a 1\nb\n",
             MAIN: cache(entry("a", 1, 1), entry("b", 2, 1, b"\x01\x05"))}
    return mci.build_manifest(files, selection_doc(["a", "b", "x"]), PROVENANCE)


class OutputTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.parent = Path(self.tmp.name)
        os.chmod(self.parent, 0o700)

    def tearDown(self):
        self.tmp.cleanup()

    def test_deterministic_and_private(self):
        one, two = mci.render(sample_manifest()), mci.render(sample_manifest())
        self.assertEqual(one, two)
        manifest = sample_manifest()
        self.assertEqual(manifest["status"], "complete")
        self.assertEqual(manifest["summary"]["dispositions"],
                         {"retained": 2, "discarded_not_found": 1})
        target, complete_sha = mci.write_output(self.parent / "out", one, "complete")
        self.assertEqual(stat.S_IMODE(os.lstat(target).st_mode), 0o700)
        self.assertEqual(sorted(os.listdir(target)),
                         ["map-cache-complete.json", "map-cache-manifest.json"])
        for name in os.listdir(target):
            self.assertEqual(stat.S_IMODE(os.lstat(target / name).st_mode), 0o600)
        self.assertEqual((target / "map-cache-manifest.json").read_bytes(), one)
        complete = json.loads((target / "map-cache-complete.json").read_bytes())
        self.assertEqual(complete["map_cache_manifest_sha256"], sha(one))
        self.assertEqual(sha((target / "map-cache-complete.json").read_bytes()), complete_sha)
        text = one.decode()
        self.assertNotIn(self.parent.as_posix(), text)
        self.assertNotIn("/Users/", text)

    def test_existing_targets_preserved(self):
        data = mci.render(sample_manifest())
        existing = self.parent / "file"
        existing.write_bytes(b"keep")
        directory = self.parent / "dir"
        directory.mkdir()
        (directory / "x").write_bytes(b"keep")
        live = self.parent / "live"
        live.symlink_to(directory)
        dangling = self.parent / "dangling"
        dangling.symlink_to(self.parent / "nowhere")
        for target in (existing, directory, live, dangling):
            with self.subTest(target.name), self.assertRaises(mci.InventoryError):
                mci.write_output(target, data, "complete")
        self.assertEqual(existing.read_bytes(), b"keep")
        self.assertEqual(os.listdir(directory), ["x"])
        self.assertFalse((self.parent / "nowhere").exists())
        self.assertTrue(os.path.islink(live) and os.path.islink(dangling))

    def test_untrusted_parent_refused(self):
        shared = self.parent / "shared"
        shared.mkdir()
        os.chmod(shared, 0o777)
        with self.assertRaises(mci.InventoryError):
            mci.write_output(shared / "out", b"{}", "complete")
        link = self.parent / "linkparent"
        link.symlink_to(self.parent)
        with self.assertRaises(mci.InventoryError):
            mci.write_output(link / "out", b"{}", "complete")

    def test_completion_readback_failure_removes_completion(self):
        real = mci._read_back

        def fail_on_complete(dir_fd, name, expect):
            if name == mci.OUTPUT_COMPLETE:
                raise mci.InventoryError("simulated readback mismatch")
            return real(dir_fd, name, expect)

        with mock.patch.object(mci, "_read_back", fail_on_complete):
            with self.assertRaisesRegex(mci.InventoryError, "without a completion record"):
                mci.write_output(self.parent / "out", b"{}\n", "complete")
        self.assertEqual(os.listdir(self.parent / "out"), ["map-cache-manifest.json"])

    def test_unexpected_post_readback_failures_remove_owned_completion(self):
        real = mci._read_back
        for number, exception in enumerate((RuntimeError, MemoryError)):
            with self.subTest(exception=exception.__name__):
                def fail_after_readback(fd, name, expect):
                    real(fd, name, expect)
                    if name == mci.OUTPUT_COMPLETE:
                        raise exception("injected after actual readback")

                target = self.parent / str(number)
                with mock.patch.object(mci, "_read_back", fail_after_readback):
                    with self.assertRaisesRegex(mci.InventoryError, "without a completion record"):
                        mci.write_output(target, b'{"status":"complete"}\n', "complete")
                self.assertEqual(os.listdir(target), [mci.OUTPUT_MANIFEST])

    def test_unexpected_marker_cleanup_failure_is_explicit(self):
        real = mci._read_back

        def fail(fd, name, expect):
            real(fd, name, expect)
            if name == mci.OUTPUT_COMPLETE:
                raise RuntimeError("readback failure")

        with mock.patch.object(mci, "_read_back", fail), \
                mock.patch.object(mci.os, "unlink", side_effect=RuntimeError("cleanup failure")):
            with self.assertRaisesRegex(mci.InventoryError, "could not remove.*cleanup failure"):
                mci.write_output(self.parent / "out", b"{}\n", "complete")

    def test_final_directory_close_failure_removes_owned_marker(self):
        real_read, real_close = mci._read_back, mci.os.close
        for number, exception in enumerate((OSError, RuntimeError, MemoryError)):
            seen = []

            def capture(fd, name, expect):
                real_read(fd, name, expect)
                if name == mci.OUTPUT_COMPLETE:
                    seen.append(fd)

            def close_then_fail(fd):
                real_close(fd)
                if seen and fd == seen[0]:
                    raise exception("injected final directory close")

            target = self.parent / f"close-{number}"
            with self.subTest(exception=exception.__name__), \
                    mock.patch.object(mci, "_read_back", capture), \
                    mock.patch.object(mci.os, "close", close_then_fail):
                with self.assertRaisesRegex(mci.InventoryError, "without a completion record"):
                    mci.write_output(target, b"{}\n", "complete")
            self.assertEqual(os.listdir(target), [mci.OUTPUT_MANIFEST])

    def test_close_failure_cleanup_refuses_replacement_directory(self):
        target, moved = self.parent / "out", self.parent / "moved"
        real_read, real_close = mci._read_back, mci.os.close
        seen = []

        def capture(fd, name, expect):
            real_read(fd, name, expect)
            if name == mci.OUTPUT_COMPLETE:
                seen.append(fd)

        def replace_then_fail(fd):
            real_close(fd)
            if seen and fd == seen.pop():
                target.rename(moved)
                target.mkdir(mode=0o700)
                (target / mci.OUTPUT_COMPLETE).write_bytes(b"foreign")
                raise OSError("injected final close and replacement")

        with mock.patch.object(mci, "_read_back", capture), \
                mock.patch.object(mci.os, "close", replace_then_fail):
            with self.assertRaisesRegex(mci.InventoryError, "could not remove.*directory was replaced"):
                mci.write_output(target, b"{}\n", "complete")
        self.assertEqual((target / mci.OUTPUT_COMPLETE).read_bytes(), b"foreign")
        self.assertTrue((moved / mci.OUTPUT_COMPLETE).is_file())

    def test_failure_close_does_not_mask_marker_cleanup_error(self):
        real_read, real_close = mci._read_back, mci.os.close
        seen = []

        def fail_readback(fd, name, expect):
            real_read(fd, name, expect)
            if name == mci.OUTPUT_COMPLETE:
                seen.append(fd)
                raise RuntimeError("injected readback")

        def close_then_fail(fd):
            real_close(fd)
            if seen and fd == seen[0]:
                raise OSError("injected failure close")

        with mock.patch.object(mci, "_read_back", fail_readback), \
                mock.patch.object(mci.os, "close", close_then_fail), \
                mock.patch.object(mci.os, "unlink", side_effect=PermissionError("unlink denied")):
            with self.assertRaisesRegex(mci.InventoryError, "could not remove.*unlink denied"):
                mci.write_output(self.parent / "out", b"{}\n", "complete")

    def test_manifest_write_failure_leaves_no_completion(self):
        def fail(*args, **kwargs):
            raise OSError(28, "simulated no space")

        with mock.patch.object(mci, "_write_new", fail):
            with self.assertRaises(mci.InventoryError):
                mci.write_output(self.parent / "out", b"{}\n", "complete")
        self.assertEqual(os.listdir(self.parent / "out"), [])

    def test_cleanup_failure_is_explained(self):
        real_read = mci._read_back

        def fail_on_complete(dir_fd, name, expect):
            if name == mci.OUTPUT_COMPLETE:
                raise mci.InventoryError("simulated readback mismatch")
            return real_read(dir_fd, name, expect)

        def no_unlink(*args, **kwargs):
            raise PermissionError(1, "simulated")

        with mock.patch.object(mci, "_read_back", fail_on_complete), \
                mock.patch.object(mci.os, "unlink", no_unlink):
            with self.assertRaisesRegex(mci.InventoryError, "could not remove"):
                mci.write_output(self.parent / "out", b"{}\n", "complete")

    def test_foreign_completion_is_not_removed(self):
        """A completion file this run did not create (O_EXCL failed) is left alone."""
        real_write = mci._write_new

        def plant(dir_fd, name, data, created=None):
            if name == mci.OUTPUT_COMPLETE:
                fd = os.open(name, os.O_WRONLY | os.O_CREAT, 0o600, dir_fd=dir_fd)
                os.write(fd, b"foreign")
                os.close(fd)
            return real_write(dir_fd, name, data, created)

        with mock.patch.object(mci, "_write_new", plant):
            with self.assertRaises(mci.InventoryError):
                mci.write_output(self.parent / "out", b"{}\n", "complete")
        self.assertEqual((self.parent / "out" / mci.OUTPUT_COMPLETE).read_bytes(), b"foreign")


def _env_path(name):
    value = os.environ.get(name)
    return Path(value) if value and os.path.isabs(value) else None


@unittest.skipUnless(_env_path("MAP_CACHE_SNAPSHOT") and _env_path("MAP_CACHE_SELECTION")
                     and _env_path("MAP_CACHE_SNAPSHOT").is_dir()
                     and _env_path("MAP_CACHE_SELECTION").is_dir(),
                     "canonical inputs absent: set absolute $MAP_CACHE_SNAPSHOT and "
                     "$MAP_CACHE_SELECTION")
class PinnedInputTests(unittest.TestCase):

    def test_pinned_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.chmod(tmp, 0o700)
            target, manifest, hashes = mci.run(_env_path("MAP_CACHE_SNAPSHOT"),
                                               _env_path("MAP_CACHE_SELECTION"),
                                               Path(tmp, "out"))
            data = (target / mci.OUTPUT_MANIFEST).read_bytes()
        self.assertEqual(sha(data), hashes["manifest_sha256"])
        self.assertEqual(manifest["inputs"]["snapshot"]["manifest_sha256"],
                         "79ee4eff2ed1621aa3be6247d0aedefc5f44abd65025617de652f41644c1dbd0")
        summary = manifest["summary"]
        self.assertEqual(summary["candidates"], sum(summary["dispositions"].values()))
        self.assertEqual(summary["index_records"], len(manifest["index"]["events"]))
        retained = [r for r in manifest["candidates"] if r["disposition"] == "retained"]
        self.assertEqual([r["slot"] for r in retained], list(range(len(retained))))
        self.assertEqual(manifest["status"] == "complete",
                         "unresolved_unsafe" not in summary["dispositions"]
                         and summary["cache_files_unsafe"] == 0
                         and summary["cache_entries_decode_unsafe"] == 0)


if __name__ == "__main__":
    unittest.main()
