"""Tests for archive_inventory_october. Run: python3 -I -m unittest discover -s tools/renewal

Archives are small authored synthetic fixtures (one 0x300 data.grf and two legacy
0x102 archives) built with the April test builders. Each fixture writes its own
extracted-tree manifest and a synthetic profile pinned by its own hash, and runs
through the private test contract; the production entry points and CLI accept no
pins. The core file is always the real, unchanged tools/renewal/archive_catalog.py.

The production test runs only when $T07_EXTRACTED_MANIFEST and $T07_ARCHIVE_ROOT
name the admitted inputs; it writes a fresh output below $T07_OUTPUT_PARENT.
"""

import errno
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import archive_inventory_october as inv  # noqa: E402
import test_archive_catalog as tac  # noqa: E402  (April fixture builders, unchanged)

CORE_PATH = HERE / "archive_catalog.py"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_core():
    return inv._load_core(inv.PRODUCTION)[0]


CORE = load_core()

DATA_GRF = tac.modern_archive([tac.modern_entry(b"data\\c.bmp", 5, 8, 5, 0),
                               tac.modern_entry(b"data\\d"),
                               tac.modern_entry(b"data\\d", 3, 4, 9, 1, 7)])
DATA0_GRF = tac.legacy_archive([tac.legacy_entry(b"data\\c.bmp\0\0"),
                                tac.legacy_entry(b"x\xb0\xa1.txt\0")])
EVENT_GRF = tac.legacy_archive([tac.legacy_entry(b"data\\a.gat\0\0"),
                                tac.legacy_entry(b"data\\b.bmp\0\0")])
ARCHIVES = {"data.grf": DATA_GRF, "data0.grf": DATA0_GRF, "event.grf": EVENT_GRF}
OTHER_FILES = {"AI/AI.lua": b"-- ai\n", "client.ini": b"[x]\n"}


def raw_modern_entry(name, blob):
    """Profile facts of a 0x300 archive whose header the core rejects (limits tests)."""
    u32 = lambda at: struct.unpack_from("<I", blob, at)[0]  # noqa: E731
    offset = u32(30) + 46
    csize, real = struct.unpack_from("<II", blob, offset + 4)
    return {"bytes": len(blob), "declared_version": 0x300, "effective_version": 0x300,
            "extracted_path": "app/" + name, "file": name, "header_sha256": sha(blob[:46]),
            "layout": "0x300", "record_count": u32(38), "sha256": sha(blob),
            "signature": "Event Horizon", "stored_end": offset + 12 + csize,
            "stored_start": offset + 12, "table_compressed_size": csize,
            "table_offset": offset, "table_pos": offset + 4, "table_real_size": real,
            "table_skip": 4}


def profile_entry(name, blob):
    try:
        header = CORE.parse_header(blob[:46])
    except CORE.SourceRejection:
        return raw_modern_entry(name, blob)
    pos = header["table_pos"]
    plan = CORE.plan_table(header, len(blob), blob[pos:pos + 8]
                           if header["layout"] != "legacy" else None)
    modern = header["layout"] != "legacy"
    return {"bytes": len(blob), "declared_version": header["declared_version"],
            "effective_version": header["effective_version"],
            "extracted_path": "app/" + name, "file": name,
            "header_sha256": header["header_sha256"], "layout": header["layout"],
            "record_count": header["record_count"], "sha256": sha(blob),
            "signature": header["signature"], "stored_end": plan["stored_end"],
            "stored_start": plan["stored_start"] + (8 if modern else 0),
            "table_compressed_size": plan.get("compressed_size"),
            "table_offset": header["table_offset"], "table_pos": header["table_pos"],
            "table_real_size": plan.get("real_size"), "table_skip": header["table_skip"]}


def manifest_entries(archives, others):
    entries = [{"path": "app", "kind": "dir", "mode": "0700"},
               {"path": "app/AI", "kind": "dir", "mode": "0700"},
               {"path": "tmp", "kind": "dir", "mode": "0700"}]
    files = dict(("app/" + k, v) for k, v in others.items())
    files.update(("app/" + k, v) for k, v in archives.items())
    for path, body in files.items():
        digest = sha(body)
        entries.append({"path": path, "kind": "file", "bytes": len(body), "sha256": digest,
                        "reported_SHA256_prefix": digest[:40],
                        "prefix_matches_final_output": True, "mode": "0600",
                        "single_link": True})
    for e in entries:
        e["path_raw_hex"] = e["path"].encode().hex()
    return sorted(entries, key=lambda e: e["path"])


class Fixture:
    """Synthetic extracted tree, manifest, pinned synthetic profile and contract."""

    def __init__(self, base, archives=None):
        self.base = Path(base)
        self.root = self.base / "tree" / "app"
        (self.root / "AI").mkdir(parents=True)
        (self.base / "tree" / "tmp").mkdir()
        self.archives = dict(archives or ARCHIVES)
        for name, blob in self.archives.items():
            (self.root / name).write_bytes(blob)
        for name, body in OTHER_FILES.items():
            (self.root / name).write_bytes(body)
        self.manifest_path = self.base / "inner-manifest.json"
        self.write_manifest(manifest_entries(self.archives, OTHER_FILES))

    def write_manifest(self, entries, profile_changes=None):
        data = json.dumps(entries, indent=2).encode()
        self.manifest_path.write_bytes(data)
        self.entries = entries
        self.write_profile(data, profile_changes)

    def write_profile(self, manifest_bytes=None, changes=None):
        if manifest_bytes is None:
            manifest_bytes = self.manifest_path.read_bytes()
        archives = [profile_entry(n, self.archives[n]) for n in inv.ENUMERATION_ORDER]
        profile = {
            "archives": archives,
            "core": {"bytes": inv.PRODUCTION.core_pin["bytes"], "path": inv.CORE_REL,
                     "sha256": inv.PRODUCTION.core_pin["sha256"]},
            "enumeration_basis": "root-declared ASCII basename order; physical records only",
            "enumeration_order": list(inv.ENUMERATION_ORDER),
            "exclusions": ["client lookup winner or deduplication"],
            "extracted_manifest": {
                "bytes": len(manifest_bytes), "sha256": sha(manifest_bytes),
                "files": sum(1 for e in self.entries if e["kind"] == "file"),
                "directories": sum(1 for e in self.entries if e["kind"] == "dir"),
                "grf_paths": [a["extracted_path"] for a in archives],
                "schema": "complete extracted tree: list of path/kind entries"},
            "lookup_priority": None, "priority_status": "not_established",
            "schema": inv.PROFILE_SCHEMA,
            "source_preflight": {"bytes": 1, "sha256": "0" * 64},
            "task": inv.TASK,
            "total_header_records": sum(a["record_count"] for a in archives),
        }
        for change in changes or ():
            change(profile)
        data = json.dumps(profile, indent=2, sort_keys=True).encode()
        self.profile_path = self.base / "profile.json"
        self.profile_path.write_bytes(data)
        self.profile = profile
        self.contract = inv._Contract(self.profile_path, len(data), sha(data), CORE_PATH,
                                      inv.PRODUCTION.core_pin["bytes"],
                                      inv.PRODUCTION.core_pin["sha256"],
                                      inv.PRODUCTION.generator_path)

    def run(self, out="out", contract=None):
        return inv._run(contract or self.contract, self.manifest_path, self.root,
                        self.base / out)

    def verify(self, out="out"):
        return inv._verify_inventory(self.base / out, self.contract)


class Base(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.chmod(self.tmp.name, 0o700)
        self.fx = Fixture(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def out(self, name="out"):
        return self.fx.base / name

    def files(self, name="out"):
        return {p.name: p.read_bytes() for p in sorted(self.out(name).iterdir())}

    def assert_refused_early(self, call, error=inv.InputError, pattern=None):
        """Refused before any archive body open and before output creation."""
        opened = []
        real_open = os.open

        def track(path, flags, *args, **kwargs):
            opened.append(os.path.basename(str(path)))
            return real_open(path, flags, *args, **kwargs)

        with mock.patch.object(inv.os, "open", track):
            if pattern:
                with self.assertRaisesRegex(error, pattern):
                    call()
            else:
                with self.assertRaises(error):
                    call()
        self.assertFalse(os.path.lexists(self.out()))
        self.assertFalse(set(opened) & set(inv.ENUMERATION_ORDER), opened)
        return opened

    def assert_failed(self, name="out"):
        listing = sorted(os.listdir(self.out(name)))
        self.assertIn(inv.OUTPUT_FAILED, listing)
        failed = json.loads((self.out(name) / inv.OUTPUT_FAILED).read_bytes())
        self.assertEqual(failed["status"], "failed")
        self.assertNotIn(str(self.fx.base), json.dumps(failed))
        with self.assertRaises(inv.VerificationError):
            self.fx.verify(name)
        return listing, failed


class InventoryTests(Base):

    def test_literal_raw_records_all_archives_no_winner(self):
        target, manifest, hashes = self.fx.run()
        lines = {n: [json.loads(x) for x in (target / (n + ".records.jsonl")).read_text()
                     .splitlines()] for n in inv.ENUMERATION_ORDER}
        self.assertEqual([len(lines[n]) for n in inv.ENUMERATION_ORDER], [3, 2, 2])
        self.assertEqual(lines["data.grf"][0], {
            "ordinal": 0, "table_offset": 0, "record_bytes": 32,
            "name_hex": "646174615c632e626d70", "name_length": 10, "name_terminated": True,
            "compressed_size": 5, "length_aligned": 8, "real_size": 5, "original_kind": 0,
            "effective_kind": 1, "kind_promotion": "kind0_stored_file_to_file",
            "metadata_filter": "eligible", "payload_offset_field": 0,
            "diagnostic_body_range": [46, 54], "diagnostic_body_range_within_archive": True,
            "archive": "data.grf", "archive_sha256": sha(DATA_GRF)})
        third = lines["data.grf"][2]
        self.assertEqual((third["name_hex"], third["real_size"], third["payload_offset_field"],
                          third["diagnostic_body_range"]), ("646174615c64", 9, 7, [53, 57]))
        event = lines["event.grf"][0]
        expected = {"ordinal": 0, "table_offset": 0, "record_bytes": 39, "block_length": 18,
                    "block_low_byte": 18, "derived_name_length": 12, "name_start": 6,
                    "metadata_offset": 22, "encoded_region_bytes": 16,
                    "transformed_blocks": 2, "untransformed_name_bytes": 0,
                    "name_hex": "646174615c612e676174", "name_length": 10,
                    "name_terminated": True, "size_field": 725, "aligned_field": 37595,
                    "real_size": 0, "derived_compressed_size": 10,
                    "derived_length_aligned": 16, "compressed_size": 10,
                    "length_aligned": 16, "compressed_underflow": False,
                    "aligned_underflow": False, "original_kind": 1, "effective_kind": 5,
                    "header_encryption_flag": "header", "metadata_filter": "eligible",
                    "archive_offset": 110, "payload_offset_field": 0,
                    "diagnostic_body_range": [46, 62],
                    "diagnostic_body_range_within_archive": True, "archive": "event.grf"}
        self.assertEqual({k: event[k] for k in expected}, expected)
        self.assertEqual(lines["data0.grf"][1]["name_hex"], "78b0a12e747874")
        self.assertEqual(lines["data0.grf"][1]["header_encryption_flag"], "mixed")
        # Cross-archive duplicate kept in both archives; within-archive duplicate kept.
        self.assertEqual(lines["data0.grf"][0]["name_hex"], lines["data.grf"][0]["name_hex"])
        self.assertEqual(manifest["archives"][0]["counts"]["duplicate_raw_names"], 1)
        totals = manifest["totals"]
        self.assertEqual(totals["raw_records"], 7)
        self.assertEqual(totals["header_records"], 7)
        self.assertEqual(totals["cross_archive_shared_raw_names"], 1)
        self.assertEqual(totals["per_archive_shared_name_presence"],
                         {"data.grf": 1, "data0.grf": 1, "event.grf": 0})
        self.assertEqual(totals["unique_raw_names_across_archives"], 5)
        self.assertEqual([a["file"] for a in manifest["archives"]],
                         list(inv.ENUMERATION_ORDER))
        self.assertIsNone(manifest["lookup_priority"])
        self.assertEqual(manifest["priority_status"], "not_established")
        self.assertIsNone(manifest["semantics"]["winning_archive"])
        self.assertEqual(manifest["extracted_manifest"]["loose_data_ini_entries"], 0)
        self.assertEqual(self.fx.verify(), manifest)

    def test_provenance_usage_and_no_april_ini_inheritance(self):
        _, manifest, hashes = self.fx.run()
        self.assertEqual(manifest["core"]["sha256"], sha(CORE_PATH.read_bytes()))
        self.assertEqual(manifest["profile"]["sha256"], self.fx.contract.profile_pin["sha256"])
        self.assertEqual(manifest["extracted_manifest"]["sha256"],
                         sha(self.fx.manifest_path.read_bytes()))
        self.assertEqual(manifest["generator"]["sha256"],
                         sha((HERE / "archive_inventory_october.py").read_bytes()))
        usage = manifest["work_usage"]
        self.assertEqual(usage["archive_bytes_hashed"], sum(map(len, ARCHIVES.values())))
        self.assertEqual(usage["table_bytes_captured"],
                         sum(a["table"]["stored_bytes"] for a in manifest["archives"]))
        self.assertEqual(usage["records"], 7)
        self.assertEqual(usage["record_file_bytes"],
                         sum(a["records_file"]["bytes"] for a in manifest["archives"]))
        self.assertEqual(usage["extracted_manifest_bytes_read"],
                         len(self.fx.manifest_path.read_bytes()))
        self.assertEqual(manifest["work_limits"], CORE.WORK_LIMITS)
        text = json.dumps(manifest)
        for april in ("ini_handling", "pinned_files", "input_manifest_agreement",
                      "ordered_basenames", str(self.fx.base)):
                self.assertFalse(april in json.dumps(dict(manifest, core=None)), april)
        for a in manifest["archives"]:
            self.assertTrue(all(a["profile_agreement"].values()))
        self.assertTrue(text.isascii())

    def test_complete_last_modes_and_determinism(self):
        self.fx.run()
        self.fx.run("out2")
        first, second = self.files(), self.files("out2")
        self.assertEqual(first, second)
        self.assertEqual(sorted(first), sorted(
            [n + ".records.jsonl" for n in inv.ENUMERATION_ORDER] +
            [inv.OUTPUT_MANIFEST, inv.OUTPUT_COMPLETE]))
        self.assertEqual(os.stat(self.out()).st_mode & 0o777, 0o700)
        for name in first:
            self.assertEqual(os.stat(self.out() / name).st_mode & 0o777, 0o600)
        complete = json.loads(first[inv.OUTPUT_COMPLETE])
        self.assertEqual(complete["inventory_manifest_sha256"],
                         sha(first[inv.OUTPUT_MANIFEST]))
        mtimes = {n: os.stat(self.out() / n).st_mtime_ns for n in first}
        self.assertEqual(max(mtimes, key=mtimes.get), inv.OUTPUT_COMPLETE)

    def test_short_writes_are_completed_and_verified(self):
        real = inv._write_chunk
        with mock.patch.object(inv, "_write_chunk", lambda fd, view: real(fd, view[:7])):
            self.fx.run()
        self.fx.run("out2")
        self.assertEqual(self.files(), self.files("out2"))


class ProfileCoreManifestTests(Base):

    def test_profile_pin_and_link(self):
        data = self.fx.profile_path.read_bytes()
        self.fx.profile_path.write_bytes(data.replace(b"physical", b"Physical"))
        self.assert_refused_early(self.fx.run, pattern="profile does not match its pin")
        self.fx.profile_path.write_bytes(data)
        link = self.fx.base / "profile-link.json"
        link.symlink_to(self.fx.profile_path)
        bad = inv._Contract(link, *self.fx.contract.profile_pin.values(), CORE_PATH,
                            *inv.PRODUCTION.core_pin.values(), inv.PRODUCTION.generator_path)
        self.assert_refused_early(lambda: self.fx.run(contract=bad),
                                  pattern="profile cannot be opened")

    def test_profile_typed_contract(self):
        cases = {
            "priority": lambda p: p.update(lookup_priority=["data.grf"]),
            "status": lambda p: p.update(priority_status="established"),
            "order": lambda p: p.update(enumeration_order=["event.grf", "data0.grf",
                                                           "data.grf"]),
            "core": lambda p: p["core"].update(sha256="1" * 64),
            "bool": lambda p: p["archives"][1].update(record_count=True),
            "range": lambda p: p["archives"][0].update(stored_start=p["archives"][0]
                                                       ["table_pos"]),
            "extra": lambda p: p.update(winner="data.grf"),
            "total": lambda p: p.update(total_header_records=8),
            "grf": lambda p: p["extracted_manifest"].update(grf_paths=["app/data.grf"]),
        }
        for label, change in cases.items():
            with self.subTest(label):
                self.fx.write_profile(changes=[change])
                self.assert_refused_early(self.fx.run, pattern="profile contract")

    def test_core_mismatch_refused_before_execution(self):
        core = CORE_PATH.read_bytes()
        first, rest = core.split(b"\n", 1)
        poisoned = b"raise SystemExit(97)".ljust(len(first), b"#") + b"\n" + rest
        self.assertEqual(len(poisoned), len(core))
        copy = self.fx.base / "core.py"
        copy.write_bytes(poisoned)
        bad = inv._Contract(self.fx.profile_path, *self.fx.contract.profile_pin.values(),
                            copy, *inv.PRODUCTION.core_pin.values(),
                            inv.PRODUCTION.generator_path)
        self.assert_refused_early(lambda: self.fx.run(contract=bad),
                                  pattern="core does not match its pin")
        copy.unlink()
        copy.symlink_to(CORE_PATH)
        self.assert_refused_early(lambda: self.fx.run(contract=bad),
                                  pattern="core cannot be opened")
        copy.unlink()
        os.link(CORE_PATH, copy)
        try:
            self.assert_refused_early(lambda: self.fx.run(contract=bad),
                                      pattern="core is not a regular single-link")
        finally:
            copy.unlink()

    def test_manifest_pin_and_shape(self):
        data = self.fx.manifest_path.read_bytes()
        self.fx.manifest_path.write_bytes(data.replace(b"0700", b"0750", 1))
        self.assert_refused_early(self.fx.run, pattern="extracted manifest does not match")
        entries = manifest_entries(ARCHIVES, OTHER_FILES)

        def extra_grf(es):
            es.append(dict(es[-1], path="app/AI/more.GRF",
                           path_raw_hex=b"app/AI/more.GRF".hex()))

        def escape(es):
            es.append(dict(es[-1], path="app/../x", path_raw_hex=b"app/../x".hex()))

        def dup(es):
            es.append(dict(es[-1]))

        def hexdiff(es):
            es[-1]["path_raw_hex"] = "00"

        def grf_hash(es):
            for e in es:
                if e["path"] == "app/data0.grf":
                    e["sha256"] = "2" * 64

        def no_link(es):
            for e in es:
                if e["path"] == "app/event.grf":
                    e["single_link"] = False

        def orphan(es):
            es.append(dict(es[-1], path="gone/x", path_raw_hex=b"gone/x".hex()))

        def missing_grf(es):
            es[:] = [e for e in es if e["path"] != "app/event.grf"]
            es.append(dict(es[-1], path="app/event.bin",
                           path_raw_hex=b"app/event.bin".hex()))

        for label, change in (("extra grf", extra_grf), ("escape", escape), ("dup", dup),
                              ("hex", hexdiff), ("grf hash", grf_hash), ("link", no_link),
                              ("orphan", orphan), ("missing grf", missing_grf)):
            with self.subTest(label):
                es = [dict(e) for e in entries]
                change(es)
                self.fx.write_manifest(es)
                self.assert_refused_early(self.fx.run, pattern="extracted manifest")
        with self.subTest("count"):
            self.fx.write_manifest(entries, [lambda p: p["extracted_manifest"].update(
                files=p["extracted_manifest"]["files"] - 1,
                directories=p["extracted_manifest"]["directories"] + 1)])
            self.assert_refused_early(self.fx.run, pattern="counts differ")

    def test_manifest_and_root_links_refused(self):
        link = self.fx.base / "manifest-link.json"
        link.symlink_to(self.fx.manifest_path)
        self.assert_refused_early(lambda: inv._run(self.fx.contract, link, self.fx.root,
                                                   self.out()),
                                  pattern="cannot be opened without following")
        root_link = self.fx.base / "root-link"
        root_link.symlink_to(self.fx.root)
        self.assert_refused_early(lambda: inv._run(self.fx.contract, self.fx.manifest_path,
                                                   root_link, self.out()),
                                  pattern="archive root is missing")


class ArchiveRootTests(Base):

    def test_extra_grf_and_mixed_tree(self):
        extra = self.fx.root / "patch.Grf"
        extra.write_bytes(b"x")
        self.assert_refused_early(self.fx.run, pattern="3 \\.grf|4 \\.grf entries")
        extra.unlink()
        (self.fx.root / "patch.grf").mkdir()
        self.assert_refused_early(self.fx.run, pattern=".grf entries")
        (self.fx.root / "patch.grf").rmdir()
        (self.fx.root / "unlisted.txt").write_bytes(b"x")
        self.assert_refused_early(self.fx.run, pattern="listing differs")
        (self.fx.root / "unlisted.txt").unlink()
        (self.fx.root / "client.ini").write_bytes(b"[changed size]\n")
        self.assert_refused_early(self.fx.run, pattern="kind or size")

    def test_symlink_hardlink_fifo_archives(self):
        target = self.fx.root / "data0.grf"
        moved = self.fx.base / "data0-real.grf"
        target.rename(moved)
        target.symlink_to(moved)
        self.assert_refused_early(self.fx.run, pattern="kind or size")
        target.unlink()
        moved.rename(target)
        os.link(target, self.fx.base / "data0-second-link")
        self.assert_refused_early(self.fx.run, pattern="single-link")
        os.unlink(self.fx.base / "data0-second-link")
        event = self.fx.root / "event.grf"
        event.unlink()
        os.mkfifo(event, 0o600)
        self.assert_refused_early(self.fx.run, pattern="kind or size")

    def test_output_escape_untrusted_and_existing(self):
        inside = self.fx.root / "AI"
        with self.assertRaisesRegex(inv.OutputError, "inside the archive root"):
            inv._run(self.fx.contract, self.fx.manifest_path, self.fx.root, inside / "o")
        self.assertFalse(os.path.lexists(inside / "o"))
        shared = self.fx.base / "shared"
        shared.mkdir(mode=0o777)
        os.chmod(shared, 0o777)
        with self.assertRaisesRegex(inv.OutputError, "not group/world writable"):
            self.fx.run("shared/o")
        self.assertFalse(os.path.lexists(shared / "o"))
        for kind in ("dir", "file", "dangling"):
            with self.subTest(kind):
                path = self.out("exists-" + kind)
                if kind == "dir":
                    path.mkdir()
                elif kind == "file":
                    path.write_bytes(b"keep")
                else:
                    path.symlink_to(self.fx.base / "nowhere")
                with self.assertRaisesRegex(inv.OutputError, "already exists"):
                    self.fx.run(path.name)
                if kind == "dir":
                    self.assertEqual(os.listdir(path), [])
                elif kind == "file":
                    self.assertEqual(path.read_bytes(), b"keep")
                else:
                    self.assertTrue(path.is_symlink())


class ArchiveFaultTests(Base):

    def test_corrupted_archive_same_size(self):
        blob = bytearray(DATA_GRF)
        blob[50] ^= 0xff  # payload byte: only the full hash notices
        (self.fx.root / "data.grf").write_bytes(bytes(blob))
        with self.assertRaisesRegex(inv.InventoryError, "data.grf SHA-256 differs") as cm:
            self.fx.run()
        self.assertEqual(cm.exception.category, "input_pin")
        listing, failed = self.assert_failed()
        self.assertEqual(listing, [inv.OUTPUT_FAILED])
        self.assertNotIn("c.bmp", str(cm.exception))

    def test_frozen_header_fact_disagreement(self):
        self.fx.write_profile(changes=[lambda p: p["archives"][2].update(
            header_sha256="3" * 64)])
        with self.assertRaisesRegex(inv.InputError, "event.grf header/table facts.*"
                                    "header_sha256"):
            self.fx.run()
        listing, _ = self.assert_failed()
        self.assertNotIn(inv.OUTPUT_COMPLETE, listing)
        self.assertIn("data.grf.records.jsonl", listing)

    def test_drift_between_examination_and_read(self):
        real = inv._archive_lstat
        state = {"done": False}

        def drift(root_fd, name, size):
            info = real(root_fd, name, size)
            if name == "data0.grf" and not state["done"]:
                state["done"] = True
                os.utime(self.fx.root / name, ns=(1, 1))
            return info

        with mock.patch.object(inv, "_archive_lstat", drift):
            with self.assertRaisesRegex(inv.InputError, "data0.grf identity changed"):
                self.fx.run()
        self.assert_failed()

    def test_drift_after_read_blocks_completion(self):
        real = inv._totals

        def drift(*args):
            os.utime(self.fx.root / "event.grf", ns=(2, 2))
            return real(*args)

        with mock.patch.object(inv, "_totals", drift):
            with self.assertRaisesRegex(inv.InputError, "event.grf changed after"):
                self.fx.run()
        listing, _ = self.assert_failed()
        self.assertIn(inv.OUTPUT_MANIFEST, listing)
        self.assertNotIn(inv.OUTPUT_COMPLETE, listing)

    def test_profile_or_manifest_change_after_read_blocks_completion(self):
        for label, path in (("profile", self.fx.profile_path),
                            ("extracted manifest", self.fx.manifest_path)):
            with self.subTest(label):
                real = inv._totals

                def touch(*args, path=path):
                    os.utime(path, ns=(3, 3))
                    return real(*args)

                out = "out-" + label.replace(" ", "-")
                with mock.patch.object(inv, "_totals", touch):
                    with self.assertRaisesRegex(inv.InputError, f"{label} identity changed"):
                        self.fx.run(out)
                self.assert_failed(out)

    def test_source_rejection_and_limits(self):
        # Header count above the source's 500000 limit (0x300 reads u32@38 directly).
        big = tac.modern_archive([tac.modern_entry(b"a")], count=500_001)
        fx = Fixture(Path(self.tmp.name) / "big", dict(ARCHIVES, **{"data.grf": big}))
        with self.assertRaisesRegex(inv.InventoryError, "exceeds source limit") as cm:
            fx.run()
        self.assertEqual(cm.exception.category, "source_rejection")
        self.assertIn(inv.OUTPUT_FAILED, os.listdir(fx.base / "out"))
        # Truncated legacy table: the core's native record check.
        short = tac.legacy_archive([tac.legacy_entry(b"a.txt\0")], count=2)
        fx2 = Fixture(Path(self.tmp.name) / "short", dict(ARCHIVES, **{"event.grf": short}))
        with self.assertRaisesRegex(inv.InventoryError, "unexpected end of file table"):
            fx2.run()
        self.assertNotIn(inv.OUTPUT_COMPLETE, os.listdir(fx2.base / "out"))

    def test_record_file_byte_limit(self):
        real = inv._load_core

        def limited(contract):
            core, identity = real(contract)
            core.WORK_LIMITS["max_record_file_bytes"] = 200
            return core, identity

        with mock.patch.object(inv, "_load_core", limited):
            with self.assertRaisesRegex(inv.OutputError, "above its 200-byte limit"):
                self.fx.run()
        self.assert_failed()
        self.assertEqual(load_core().WORK_LIMITS["max_record_file_bytes"], 1 << 30)


class PublicationFaultTests(Base):

    def fault(self, name, patch_target, make):
        with mock.patch.object(inv, patch_target, make()):
            with self.assertRaises(inv.InventoryError) as cm:
                self.fx.run(name)
        listing, failed = self.assert_failed(name)
        self.assertNotIn(inv.OUTPUT_COMPLETE, listing)
        return cm.exception, listing, failed

    def test_write_flush_fsync_close_and_readback_faults(self):
        real_write, real_fsync, real_close = inv._write_chunk, inv._fsync, inv._close_fd

        def on_nth(real, n, action):
            # The fault fires on the n-th write/fsync/close call of the run only.
            calls = {"n": 0}

            def wrapped(fd, *args):
                calls["n"] += 1
                if calls["n"] == n:
                    return action(real, fd, *args)
                return real(fd, *args)
            return lambda: wrapped

        def raise_eio(real, fd, *args):
            raise OSError(errno.EIO, "injected")

        def zero(real, fd, *args):
            return 0

        def corrupt(real, fd, view):
            data = bytes(view)
            real(fd, data[:-2] + b"!\n")
            return len(data)

        def close_then_fail(real, fd):
            real(fd)
            raise OSError(errno.EIO, "injected close")

        cases = [("write-error", "_write_chunk", on_nth(real_write, 1, raise_eio), "output"),
                 ("no-progress", "_write_chunk", on_nth(real_write, 2, zero), "output"),
                 ("readback", "_write_chunk", on_nth(real_write, 1, corrupt), "output"),
                 ("fsync", "_fsync", on_nth(real_fsync, 3, raise_eio), "output"),
                 ("manifest-close", "_close_fd", on_nth(real_close, 4, close_then_fail),
                  "output")]
        for name, target, make, category in cases:
            with self.subTest(name):
                exc, listing, failed = self.fault(name, target, make)
                self.assertEqual(exc.category, category, str(exc))
                self.assertEqual(failed["category"], category)
                self.assertNotIn(str(self.fx.base), str(exc))

    def test_unexpected_exception_after_completion_removes_owned_marker(self):
        def boom(*args, **kwargs):
            self.assertTrue((self.out() / inv.OUTPUT_COMPLETE).exists())
            raise RuntimeError("secret data\\c.bmp")

        with mock.patch.object(inv, "_verify_inventory", boom):
            with self.assertRaises(inv.InventoryError) as cm:
                self.fx.run()
        self.assertEqual(cm.exception.category, "unexpected")
        self.assertNotIn("c.bmp", str(cm.exception))
        listing, failed = self.assert_failed()
        self.assertNotIn(inv.OUTPUT_COMPLETE, listing)
        self.assertEqual(failed["category"], "unexpected")

    def test_foreign_completion_preserved_and_failure_overrides(self):
        def replace(*args, **kwargs):
            marker = self.out() / inv.OUTPUT_COMPLETE
            data = marker.read_bytes()
            retained = self.fx.base / "retained-owned-marker"
            old = marker.stat().st_ino
            marker.rename(retained)  # keep old inode live; forbid reuse ambiguity
            marker.write_bytes(data)
            self.assertNotEqual(marker.stat().st_ino, old)
            os.chmod(marker, 0o600)
            raise RuntimeError("after foreign replacement")

        with mock.patch.object(inv, "_verify_inventory", replace):
            with self.assertRaisesRegex(inv.InventoryError, "foreign file preserved|"
                                        "could not remove"):
                self.fx.run()
        listing, _ = self.assert_failed()
        self.assertIn(inv.OUTPUT_COMPLETE, listing)  # preserved, overridden by the marker

    def test_output_directory_replaced_before_completion(self):
        real = inv._recheck_inputs
        moved = self.out("moved")

        def swap(*args):
            self.out().rename(moved)
            self.out().mkdir(mode=0o700)
            return real(*args)

        with mock.patch.object(inv, "_recheck_inputs", swap):
            with self.assertRaisesRegex(inv.OutputError, "was replaced"):
                self.fx.run()
        self.assertEqual(os.listdir(self.out()), [])  # replacement untouched
        listing, _ = self.assert_failed("moved")
        self.assertNotIn(inv.OUTPUT_COMPLETE, listing)

    def test_output_directory_close_error_after_completion(self):
        real = inv._close_fd
        state = {"n": 0, "complete_seen": False}

        def fail_last(fd):
            real(fd)
            state["n"] += 1
            if state["n"] == 6:  # 3 record files, manifest, completion, then the dir
                state["complete_seen"] = (self.out() / inv.OUTPUT_COMPLETE).exists()
                raise OSError(errno.EIO, "injected directory close")

        with mock.patch.object(inv, "_close_fd", fail_last):
            with self.assertRaises(inv.InventoryError):
                self.fx.run()
        self.assertTrue(state["complete_seen"])
        listing, _ = self.assert_failed()
        self.assertNotIn(inv.OUTPUT_COMPLETE, listing)

    def test_foreign_file_in_output_detected(self):
        real = inv._recheck_inputs

        def plant(*args):
            (self.out() / "planted.txt").write_bytes(b"x")
            return real(*args)

        with mock.patch.object(inv, "_recheck_inputs", plant):
            with self.assertRaisesRegex(inv.OutputError, "did not write"):
                self.fx.run()
        listing, _ = self.assert_failed()
        self.assertIn("planted.txt", listing)
        self.assertNotIn(inv.OUTPUT_COMPLETE, listing)


class ConsumerTests(Base):

    def setUp(self):
        super().setUp()
        self.fx.run()
        self.good = self.files()

    def rebind(self, out, manifest_change=None, record_change=None):
        """Mutate consistently: rehash record files, manifest and completion."""
        mpath, cpath = out / inv.OUTPUT_MANIFEST, out / inv.OUTPUT_COMPLETE
        manifest = json.loads(mpath.read_bytes())
        record_files = {a["records_file"]["file"]: a["records_file"]["sha256"]
                        for a in manifest["archives"]}
        if record_change:
            name, mutate = record_change
            rpath = out / name
            data = mutate(rpath.read_bytes())
            rpath.write_bytes(data)
            for a in manifest["archives"]:
                if a["records_file"]["file"] == name:
                    a["records_file"].update(bytes=len(data), sha256=sha(data))
                    record_files[name] = sha(data)
        if manifest_change:
            manifest_change(manifest)
        mbytes = CORE.render(manifest)
        mpath.write_bytes(mbytes)
        complete = json.loads(cpath.read_bytes())
        complete.update(inventory_manifest_bytes=len(mbytes),
                        inventory_manifest_sha256=sha(mbytes), record_files=record_files)
        cpath.write_bytes(CORE.render(complete))

    def mutated(self, label, mutate):
        out = self.out("m-" + label)
        shutil.copytree(self.out(), out)
        os.chmod(out, 0o700)
        mutate(out)
        with self.assertRaises(inv.VerificationError, msg=label):
            inv._verify_inventory(out, self.fx.contract)

    def test_consumer_refuses_mutations(self):
        recs = "data0.grf.records.jsonl"

        def swap_lines(data):
            a, b = data.splitlines(keepends=True)
            return b + a

        cases = {
            "missing": lambda o: (o / recs).unlink(),
            "appended": lambda o: (o / recs).write_bytes((o / recs).read_bytes() + b"\n"),
            "extra": lambda o: (o / "note.txt").write_bytes(b"x"),
            "failed-marker": lambda o: (o / inv.OUTPUT_FAILED).write_bytes(b"{}"),
            "no-complete": lambda o: (o / inv.OUTPUT_COMPLETE).unlink(),
            "reformatted": lambda o: (o / inv.OUTPUT_MANIFEST).write_bytes(json.dumps(
                json.loads((o / inv.OUTPUT_MANIFEST).read_bytes())).encode()),
            "mode": lambda o: os.chmod(o / recs, 0o644),
            "hardlink": lambda o: os.link(o / recs, self.fx.base / ("hl-" + o.name)),
            "symlink": lambda o: ((o / recs).unlink(), (o / recs).symlink_to(
                self.out() / recs)),
            "complete-status": lambda o: (o / inv.OUTPUT_COMPLETE).write_bytes(
                CORE.render(dict(json.loads((o / inv.OUTPUT_COMPLETE).read_bytes()),
                                 status="failed"))),
            "swapped-records": lambda o: self.rebind(o, record_change=(recs, swap_lines)),
            "priority": lambda o: self.rebind(o, lambda m: m.update(
                lookup_priority=["data.grf"])),
            "winner": lambda o: self.rebind(o, lambda m: m["semantics"].update(
                winning_archive="data.grf")),
            "core": lambda o: self.rebind(o, lambda m: m["core"].update(sha256="4" * 64)),
            "profile": lambda o: self.rebind(o, lambda m: m["profile"].update(bytes=1)),
            "generator": lambda o: self.rebind(o, lambda m: m["generator"].update(
                version="0")),
            "archive-pin": lambda o: self.rebind(o, lambda m: m["archives"][1].update(
                sha256="5" * 64)),
            "order": lambda o: self.rebind(o, lambda m: m["archives"].reverse()),
            "wrong-schema": lambda o: self.rebind(o, lambda m: m.update(schema="x/1")),
            "malformed": lambda o: self.rebind(o, lambda m: m.update(archives=[1, 2, 3])),
            "totals": lambda o: self.rebind(o, lambda m: m["totals"].update(raw_records=1)),
        }
        for label, mutate in cases.items():
            with self.subTest(label):
                self.mutated(label, mutate)
        with self.assertRaises(inv.VerificationError):
            inv._verify_inventory(self.out("absent"), self.fx.contract)
        # The untouched original still passes and nothing was written by the gate.
        self.assertEqual(inv._verify_inventory(self.out(), self.fx.contract)["status"],
                         "complete")
        self.assertEqual(self.files(), self.good)

    def test_production_gate_refuses_synthetic_tree(self):
        with self.assertRaises(inv.VerificationError):
            inv.verify_inventory(self.out())


class RootCorrectionTests(Base):
    """Root-authored real-file regressions; not provider benchmark credit."""

    rebind = ConsumerTests.rebind

    def test_zero_record_file_and_nonempty_baselines(self):
        self.fx.run()
        self.assertEqual(self.fx.verify()["totals"]["raw_records"], 7)
        zero = tac.legacy_archive([], trailing=b"abc")
        fx = Fixture(self.fx.base / "zero", dict(ARCHIVES, **{"event.grf": zero}))
        target, manifest, _ = fx.run()
        self.assertEqual((target / "event.grf.records.jsonl").read_bytes(), b"")
        self.assertEqual(manifest["archives"][2]["records_file"], {
            "file": "event.grf.records.jsonl", "bytes": 0, "lines": 0, "sha256": sha(b"")})
        self.assertEqual(fx.verify(), manifest)

    def test_full_frozen_manifest_contract_after_hash_rebinding(self):
        self.fx.run()
        changes = {
            "declared-version": lambda m: m["archives"][0]["header"].update(
                declared_version=512),
            "table-range": lambda m: m["archives"][0]["table"].update(stored_offset=1),
            "table-hash-type": lambda m: m["archives"][0]["table"].update(
                stored_sha256=False),
            "raw-header-field": lambda m: m["archives"][0]["header"].update(
                field_u32_38=1),
            "agreement": lambda m: m["archives"][0].update(profile_agreement={"invented": True}),
            "limit": lambda m: m["work_limits"].update(max_record_file_bytes=(1 << 30) + 1),
            "source": lambda m: m["source_rules"]["source"].update(revision="invented"),
            "validator-policy": lambda m: m["source_rules"].update(validator_policy=[]),
            "input-check": lambda m: m["archives"][0]["input_checks"].update(full_sha256=1),
            "header-bool": lambda m: m["archives"][0]["header"].update(table_skip=True),
            "order-bool": lambda m: m["archives"][0].update(order=False),
            "bytes-float": lambda m: m["archives"][0].update(bytes=float(len(DATA_GRF))),
            "usage-bool": lambda m: m["work_usage"].update(records=True),
            "usage-total": lambda m: m["work_usage"].update(archive_bytes_hashed=0),
            "counts": lambda m: m["archives"][0]["counts"].update(duplicate_raw_names=0),
            "source-preflight": lambda m: m["profile"]["source_preflight"].update(bytes=2),
            "metadata-entries": lambda m: m["extracted_manifest"].update(entries=0),
            "exclusions": lambda m: m.update(exclusions=[]),
            "extra": lambda m: m.update(unknown=True),
        }
        for label, change in changes.items():
            with self.subTest(label):
                out = self.out("contract-" + label)
                shutil.copytree(self.out(), out)
                self.rebind(out, change)
                with self.assertRaises(inv.VerificationError):
                    inv._verify_inventory(out, self.fx.contract)
        self.assertEqual(self.fx.verify()["totals"]["raw_records"], 7)

    def test_typed_all_record_fields_after_hash_rebinding(self):
        self.fx.run()
        changes = {
            "missing-name": ("data.grf", 1, lambda r: r.pop("name_hex")),
            "ordinal-bool": ("data.grf", 0, lambda r: r.update(ordinal=False)),
            "size-float": ("data.grf", 1, lambda r: r.update(real_size=float(r["real_size"]))),
            "range-bool": ("data.grf", 0, lambda r: r.update(diagnostic_body_range=[False, 54])),
            "promotion": ("data.grf", 0, lambda r: r.update(kind_promotion=None)),
            "table-order": ("data.grf", 1, lambda r: r.update(table_offset=0)),
            "legacy-signed": ("data0.grf", 1, lambda r: r.update(
                derived_compressed_size=float(r["derived_compressed_size"]))),
            "legacy-kind": ("data0.grf", 1, lambda r: r.update(effective_kind=1)),
            "legacy-hash": ("data0.grf", 1, lambda r: r.update(encoded_name_sha256="x")),
            "extra-key": ("event.grf", 1, lambda r: r.update(invented=True)),
        }
        for label, (archive, index, change) in changes.items():
            with self.subTest(label):
                out = self.out("row-" + label)
                shutil.copytree(self.out(), out)

                def mutate(data):
                    rows = [json.loads(line) for line in data.splitlines()]
                    change(rows[index])
                    return b"".join(CORE.render_record(archive, sha(ARCHIVES[archive]), r)
                                    for r in rows)

                self.rebind(out, record_change=(archive + inv.RECORDS_SUFFIX, mutate))
                with self.assertRaises(inv.VerificationError):
                    inv._verify_inventory(out, self.fx.contract)

    def test_consumer_directory_mode_is_rechecked_at_return(self):
        self.fx.run()
        real = inv._verify_records
        fired = []

        def change(*args, **kwargs):
            result = real(*args, **kwargs)
            if not fired:
                self.out().chmod(0o777)
                fired.append(True)
            return result

        try:
            with mock.patch.object(inv, "_verify_records", change):
                with self.assertRaises(inv.VerificationError):
                    self.fx.verify()
            self.assertEqual(fired, [True])
        finally:
            self.out().chmod(0o700)
        self.assertEqual(self.fx.verify()["status"], "complete")

    def test_consumer_late_directory_swap_preserves_foreign_tree(self):
        self.fx.run()
        real = inv._verify_records
        held = self.out("consumer-held")
        old = self.out().stat().st_ino
        fired = []

        def swap(*args, **kwargs):
            if not fired:
                self.out().rename(held)
                self.out().mkdir(mode=0o700)
                (self.out() / "FOREIGN").write_bytes(b"preserve")
                self.assertNotEqual(self.out().stat().st_ino, old)
                fired.append(True)
            return real(*args, **kwargs)

        with mock.patch.object(inv, "_verify_records", swap):
            with self.assertRaises(inv.VerificationError):
                self.fx.verify()
        self.assertEqual(fired, [True])
        self.assertEqual(list(self.out().iterdir()), [self.out() / "FOREIGN"])
        self.assertEqual((self.out() / "FOREIGN").read_bytes(), b"preserve")
        self.assertEqual(self.fx.verify("consumer-held")["status"], "complete")

    def test_producer_directory_swap_during_and_after_consumer(self):
        for phase in ("during", "after"):
            with self.subTest(phase):
                fx = Fixture(self.fx.base / phase)
                out = fx.base / "out"
                held = fx.base / "held"
                fired = []
                method = "_verify_records" if phase == "during" else "_verify_inventory"
                real = getattr(inv, method)

                def swap(*args, **kwargs):
                    result = real(*args, **kwargs) if phase == "after" else None
                    if not fired:
                        old = out.stat().st_ino
                        out.rename(held)
                        out.mkdir(mode=0o700)
                        (out / "FOREIGN").write_bytes(b"preserve")
                        self.assertNotEqual(out.stat().st_ino, old)
                        fired.append(True)
                    return result if phase == "after" else real(*args, **kwargs)

                with mock.patch.object(inv, method, swap):
                    with self.assertRaises(inv.InventoryError):
                        fx.run()
                self.assertEqual(fired, [True])
                self.assertEqual((out / "FOREIGN").read_bytes(), b"preserve")
                self.assertEqual(sorted(os.listdir(out)), ["FOREIGN"])
                self.assertIn(inv.OUTPUT_FAILED, os.listdir(held))
                self.assertNotIn(inv.OUTPUT_COMPLETE, os.listdir(held))

    def test_final_exact_archive_set_refuses_late_extra_grf(self):
        real = inv._recheck_inputs
        fired = []

        def plant(*args, **kwargs):
            if not fired:
                (self.fx.root / "extra.GRF").write_bytes(b"owned test")
                fired.append(True)
            return real(*args, **kwargs)

        with mock.patch.object(inv, "_recheck_inputs", plant):
            with self.assertRaises(inv.InventoryError):
                self.fx.run()
        self.assertEqual(fired, [True])
        self.assertEqual((self.fx.root / "extra.GRF").read_bytes(), b"owned test")
        self.assertNotIn(inv.OUTPUT_COMPLETE, self.assert_failed()[0])

    def test_identical_foreign_completion_swap_is_refused_and_preserved(self):
        real = inv._publish_document
        held = self.fx.base / "retained-owned-marker"
        fired = []

        def replace(*args, **kwargs):
            result = real(*args, **kwargs)
            if args[2] == inv.OUTPUT_COMPLETE:
                marker = self.out() / inv.OUTPUT_COMPLETE
                body = marker.read_bytes()
                old = marker.stat().st_ino
                marker.rename(held)
                marker.write_bytes(body)
                marker.chmod(0o600)
                self.assertNotEqual(marker.stat().st_ino, old)
                fired.append((marker.stat().st_dev, marker.stat().st_ino))
            return result

        with mock.patch.object(inv, "_publish_document", replace):
            with self.assertRaises(inv.InventoryError):
                self.fx.run()
        self.assertEqual(len(fired), 1)
        marker = self.out() / inv.OUTPUT_COMPLETE
        self.assertEqual(marker.read_bytes(), held.read_bytes())
        self.assertEqual((marker.stat().st_dev, marker.stat().st_ino), fired[0])
        self.assertIn(inv.OUTPUT_FAILED, self.assert_failed()[0])

    def test_consumer_rechecks_previously_read_file_binding(self):
        self.fx.run()
        real = inv._verify_records
        held = self.fx.base / "retained-owned-manifest"
        fired = []

        def replace(*args, **kwargs):
            if not fired:
                path = self.out() / inv.OUTPUT_MANIFEST
                body = path.read_bytes()
                old = path.stat().st_ino
                path.rename(held)
                path.write_bytes(body)
                path.chmod(0o600)
                self.assertNotEqual(path.stat().st_ino, old)
                fired.append(True)
            return real(*args, **kwargs)

        with mock.patch.object(inv, "_verify_records", replace):
            with self.assertRaises(inv.VerificationError):
                self.fx.verify()
        self.assertEqual(fired, [True])
        self.assertEqual((self.out() / inv.OUTPUT_MANIFEST).read_bytes(), held.read_bytes())
        self.assertNotIn(inv.OUTPUT_FAILED, os.listdir(self.out()))  # read-only gate

    def test_consumer_fresh_core_pin_and_late_source_identity(self):
        core_copy = self.fx.base / "owned-core-copy.py"
        body = CORE_PATH.read_bytes()
        core_copy.write_bytes(body)
        self.fx.contract.core_path = core_copy
        self.fx.run()
        core_copy.write_bytes(body + b"\n")
        with self.assertRaises(inv.VerificationError):
            self.fx.verify()
        core_copy.write_bytes(body)
        self.assertEqual(self.fx.verify()["status"], "complete")
        real = inv._verify_records
        fired = []

        def drift(*args, **kwargs):
            result = real(*args, **kwargs)
            if not fired:
                os.utime(core_copy, ns=(6, 6))
                fired.append(True)
            return result

        with mock.patch.object(inv, "_verify_records", drift):
            with self.assertRaises(inv.VerificationError):
                self.fx.verify()
        self.assertEqual(fired, [True])

    def test_producer_rechecks_file_modes_and_inputs_after_consumer(self):
        for label in ("record-mode", "profile", "core", "metadata", "generator"):
            with self.subTest(label):
                fx = Fixture(self.fx.base / label)
                # Only owned byte-identical source copies may be mutated in tests.
                core_copy, gen_copy = fx.base / "core.py", fx.base / "generator.py"
                core_copy.write_bytes(CORE_PATH.read_bytes())
                gen_copy.write_bytes(inv.PRODUCTION.generator_path.read_bytes())
                fx.contract.core_path, fx.contract.generator_path = core_copy, gen_copy
                targets = {"profile": fx.profile_path, "core": core_copy,
                           "metadata": fx.manifest_path, "generator": gen_copy}
                real = inv._verify_inventory
                fired = []

                def change(*args, **kwargs):
                    result = real(*args, **kwargs)
                    if label == "record-mode":
                        (fx.base / "out/data.grf.records.jsonl").chmod(0o644)
                    else:
                        os.utime(targets[label], ns=(5, 5))
                    fired.append(True)
                    return result

                with mock.patch.object(inv, "_verify_inventory", change):
                    with self.assertRaises(inv.InventoryError):
                        fx.run()
                self.assertEqual(fired, [True])
                self.assertNotIn(inv.OUTPUT_COMPLETE, os.listdir(fx.base / "out"))
                self.assertIn(inv.OUTPUT_FAILED, os.listdir(fx.base / "out"))

    def test_constructor_fstat_and_fchmod_failure_release_exact_owned_fd(self):
        real_open, real_fstat, real_close = os.open, os.fstat, os.close
        for fail in ("fstat", "fchmod"):
            with self.subTest(fail):
                directory = self.fx.base / ("constructor-" + fail)
                directory.mkdir(mode=0o700)
                dir_fd = real_open(directory, inv.DIR_FLAGS)
                tracked = []

                def opened(path, flags, *args, **kwargs):
                    fd = real_open(path, flags, *args, **kwargs)
                    if flags & os.O_CREAT:
                        info = real_fstat(fd)
                        tracked.append((fd, info.st_dev, info.st_ino))
                    return fd

                def stat_fault(fd):
                    if tracked and fd == tracked[0][0]:
                        raise OSError(errno.EIO, "authored constructor fstat")
                    return real_fstat(fd)

                def mode_fault(fd, mode):
                    raise OSError(errno.EIO, "authored constructor fchmod")

                try:
                    with mock.patch.object(inv.os, "open", opened), \
                            mock.patch.object(inv.os, fail,
                                              stat_fault if fail == "fstat" else mode_fault):
                        with self.assertRaises(OSError):
                            inv.CheckedFile(dir_fd, "owned", {}, 100)
                    self.assertEqual(len(tracked), 1)
                    fd, dev, ino = tracked[0]
                    try:
                        info = real_fstat(fd)
                    except OSError as exc:
                        self.assertEqual(exc.errno, errno.EBADF)
                    else:
                        # Observe first, then release ONLY the fixture's exact inode.
                        if (info.st_dev, info.st_ino) == (dev, ino):
                            real_close(fd)
                        self.fail("constructor leaked its owned descriptor")
                finally:
                    real_close(dir_fd)


class CliAndCoreTests(Base):

    def test_core_and_profile_unchanged(self):
        core = CORE_PATH.read_bytes()
        self.assertEqual((len(core), sha(core)), (54783, inv.PRODUCTION.core_pin["sha256"]))
        prof = (HERE.parents[1] / inv.PROFILE_REL).read_bytes()
        self.assertEqual((len(prof), sha(prof)), (3180, inv.PRODUCTION.profile_pin["sha256"]))
        profile = json.loads(prof)
        inv.validate_profile(profile, inv.PRODUCTION)
        self.assertEqual(profile["total_header_records"], 248908)
        self.assertEqual((profile["extracted_manifest"]["files"],
                          profile["extracted_manifest"]["directories"]), (4976, 115))

    def test_cli_has_no_pin_override_and_bounded_path_free_errors(self):
        script = HERE / "archive_inventory_october.py"
        result = subprocess.run(
            [sys.executable, "-I", "-B", str(script), str(self.fx.manifest_path),
             str(self.fx.root), str(self.out())],
            capture_output=True, timeout=60, check=False, cwd=self.fx.base)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        err = result.stderr.decode()
        self.assertIn("extracted manifest", err)
        self.assertNotIn(str(self.fx.base), err)
        self.assertLess(len(err), inv.MAX_DIAGNOSTIC_CHARS + 100)
        self.assertFalse(os.path.lexists(self.out()))
        extra = subprocess.run(
            [sys.executable, "-I", "-B", str(script), "--profile", "x", "a", "b", "c"],
            capture_output=True, timeout=60, check=False)
        self.assertEqual(extra.returncode, 2)
        self.assertIn(b"unrecognized arguments", extra.stderr)


@unittest.skipUnless(os.environ.get("T07_EXTRACTED_MANIFEST") and
                     os.environ.get("T07_ARCHIVE_ROOT") and
                     os.environ.get("T07_OUTPUT_PARENT"), "production inputs not supplied")
class ProductionTests(unittest.TestCase):

    def test_production_cli(self):
        parent = Path(os.environ["T07_OUTPUT_PARENT"])
        out = Path(tempfile.mkdtemp(dir=parent)) / "inventory"
        result = subprocess.run(
            [sys.executable, "-I", "-B", str(HERE / "archive_inventory_october.py"),
             os.environ["T07_EXTRACTED_MANIFEST"], os.environ["T07_ARCHIVE_ROOT"], str(out)],
            capture_output=True, timeout=1200, check=False)
        self.assertEqual(result.returncode, 0, result.stderr.decode()[:1000])
        manifest = inv.verify_inventory(out)
        self.assertEqual(manifest["totals"]["raw_records"], 248908)


if __name__ == "__main__":
    unittest.main()
