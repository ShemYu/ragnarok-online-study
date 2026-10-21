"""Tests for archive_inventory_patches (T07.007.007).

Run: python3 -I -B -W error::ResourceWarning -m unittest discover -s tools/renewal \
       -p test_archive_inventory_patches.py

Synthetic legacy 0x102 GPF archives are authored here from literal specs and
encoded with an independent bit-loop reference of the one-round block
transform written from literal tables; expected records come from literal
dictionaries and an independent reference model of the legacy table rules,
never from the production parser. Each synthetic run builds a private checkout
(exact core bytes, this generator's bytes and a synthetic 59-row profile) and an
input root below .tools/renewal/T07.007.007/ of this checkout (0700/0600).
Non-selected ledger files exist with mode 000, so any attempt to open one fails.

Fault controls use the private test contract hooks (core os boundary on a
private module instance, phase hooks) and this module's own I/O indirections.
The production contract and CLI have no such hooks.

The actual-input test runs only when T07_007_007_INPUT_MANIFEST,
T07_007_007_INPUT_ROOT and T07_007_007_OUTPUT_PARENT are set; otherwise it is
reported as skipped.
"""

import errno
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import archive_inventory_patches as aip  # noqa: E402

HERE = Path(os.path.realpath(__file__)).parent
CHECKOUT = HERE.parents[1]
PRIVATE = CHECKOUT / ".tools" / "renewal" / "T07.007.007"


def sha(data):
    return hashlib.sha256(data).hexdigest()


# --- Independent bit-loop reference of the one-round block transform -----------------------
# Literal des.rs tables (IP, FP, P and the four packed S-box rows).

IP = (58, 50, 42, 34, 26, 18, 10, 2, 60, 52, 44, 36, 28, 20, 12, 4,
      62, 54, 46, 38, 30, 22, 14, 6, 64, 56, 48, 40, 32, 24, 16, 8,
      57, 49, 41, 33, 25, 17, 9, 1, 59, 51, 43, 35, 27, 19, 11, 3,
      61, 53, 45, 37, 29, 21, 13, 5, 63, 55, 47, 39, 31, 23, 15, 7)
FP = (40, 8, 48, 16, 56, 24, 64, 32, 39, 7, 47, 15, 55, 23, 63, 31,
      38, 6, 46, 14, 54, 22, 62, 30, 37, 5, 45, 13, 53, 21, 61, 29,
      36, 4, 44, 12, 52, 20, 60, 28, 35, 3, 43, 11, 51, 19, 59, 27,
      34, 2, 42, 10, 50, 18, 58, 26, 33, 1, 41, 9, 49, 17, 57, 25)
TP = (16, 7, 20, 21, 29, 12, 28, 17, 1, 15, 23, 26, 5, 18, 31, 10,
      2, 8, 24, 14, 32, 27, 3, 9, 19, 13, 30, 6, 22, 11, 4, 25)
SBOX = [bytes.fromhex(h) for h in (
    "ef0341fdd8741e4726effb22b3d8841e39aca76062c1cdba5c969059053b7a85"
    "40fd1ec8e78a8b21da43649f2d14b172f55bc8b69c3776ec39a0a305526e0fd9",
    "a7dd0d789e0be3956036364ff9605aa31124d287c85275ecbbc14cba24fe8f19"
    "da1366af49d090068c6afb91378d0d78bf4911f423e5ce3b55bca257e82274ce",
    "2ceac1bf4a241fc27947a27cb6d9681580565d0133fdf4aede30079be5839b68"
    "49b42e831fc2b57ca219d8e57c2f83daf76b90fec4015a9761a63d400b58e63d",
    "4dd1b20f28bde478f64a0f938b17d1a43aecc93593567ecb5520a0fe6c891762"
    "17624bb1b4ded187c9143c4a7ea8e27da09ff65c6a098df00fe35325953628cb")]


def bits(data):
    return [(byte >> (7 - k)) & 1 for byte in data for k in range(8)]


def unbits(values):
    return bytes(sum(values[i * 8 + k] << (7 - k) for k in range(8))
                 for i in range(len(values) // 8))


def ref_block(block):
    b = [bits(block)[i - 1] for i in IP]
    s = unbits(b)
    e = [((s[7] << 5) | (s[4] >> 3)) & 63, ((s[4] << 1) | (s[5] >> 7)) & 63,
         ((s[4] << 5) | (s[5] >> 3)) & 63, ((s[5] << 1) | (s[6] >> 7)) & 63,
         ((s[5] << 5) | (s[6] >> 3)) & 63, ((s[6] << 1) | (s[7] >> 7)) & 63,
         ((s[6] << 5) | (s[7] >> 3)) & 63, ((s[7] << 1) | (s[4] >> 7)) & 63]
    sub = bits(bytes((SBOX[i][e[2 * i]] & 0xf0) | (SBOX[i][e[2 * i + 1]] & 0x0f)
                     for i in range(4)))
    f = [sub[i - 1] for i in TP]
    mixed = [b[i] ^ f[i] for i in range(32)] + b[32:]
    return unbits([mixed[i - 1] for i in FP])


def swap(block):
    return bytes(((x << 4) | (x >> 4)) & 0xff for x in block)


def ref_decode_block(block):
    return ref_block(swap(block))


def ref_encode_region(clear, name_len):
    out = bytearray(clear)
    at = 0
    while at < name_len and at + 8 <= len(out):
        out[at:at + 8] = swap(ref_block(bytes(out[at:at + 8])))
        at += 8
    return bytes(out)


def ref_decode_region(region, name_len):
    out = bytearray(region)
    at = blocks = 0
    while at < name_len and at + 8 <= len(out):
        out[at:at + 8] = ref_decode_block(bytes(out[at:at + 8]))
        at += 8
        blocks += 1
    return bytes(out), blocks


# --- Literal authored archives ---------------------------------------------------------------

def entry(clear=b"", size_field=725, aligned_field=37595, real=0, kind=1, offset=0,
          region_extra=4, raw_region=None, block_len=None):
    """One literal legacy record spec: clear name field of the derived length."""
    if raw_region is None:
        raw_region = ref_encode_region(clear + b"\xee" * region_extra, len(clear))
    if block_len is None:
        block_len = len(raw_region) + 2
    body = struct.pack("<I", block_len) + b"\0\0" + raw_region
    assert len(body) == 4 + block_len
    return body + struct.pack("<IIIBI", size_field, aligned_field, real, kind, offset)


def archive(entries, payload=b"P" * 64, subtract=3, trailing=b"", version=0x102,
            count=None, signature=b"Master of Magic"):
    n = len(entries) if count is None else count
    head = signature.ljust(16, b"\0") + b"K" * 14 + \
        struct.pack("<IIII", len(payload), subtract, n + subtract + 7, version)
    return head + payload + b"".join(entries) + trailing


def ref_records(blob, name):
    """Independent reference model of the legacy table rules for an authored archive."""
    count = struct.unpack_from("<I", blob, 38)[0] - struct.unpack_from("<I", blob, 34)[0] - 7
    table_pos = struct.unpack_from("<I", blob, 30)[0] + 46
    table = blob[table_pos:]
    p, out = 0, []
    for i in range(max(count, 0)):
        block = struct.unpack_from("<I", table, p)[0]
        derived = max(table[p] - 6, 0)
        meta = p + 4 + block
        region = table[p + 6:meta]
        clear, blocks = ref_decode_region(region, derived)
        field = clear[:derived]
        name = field.split(b"\0")[0]
        if meta + 17 > len(table):
            break  # authored truncation: the source rejects this record
        size_field, aligned_field, real, kind, offset = struct.unpack_from("<IIIBI", table,
                                                                           meta)
        comp, alig = size_field - real - 715, aligned_field - 37579
        eff, enc = kind, None
        if comp < 0 or alig < 0:
            eff = kind & 0xfe
        elif kind & 1:
            dot = name.rfind(b".")
            header_only = dot >= 0 and name[dot:].lower() in (b".gnd", b".gat", b".act",
                                                               b".str")
            eff = kind | (4 if header_only else 2)
            enc = "header" if header_only else "mixed"
        length = max(alig, 0)
        out.append({
            "ordinal": i, "table_offset": p, "record_bytes": 4 + block + 17,
            "block_length": block, "block_low_byte": table[p],
            "derived_name_length": derived, "name_start": 6, "metadata_offset": 4 + block,
            "encoded_region_bytes": len(region), "encoded_region_sha256": sha(region),
            "encoded_name_sha256": sha(region[:derived]), "transformed_blocks": blocks,
            "untransformed_name_bytes": max(derived - 8 * blocks, 0),
            "name_hex": name.hex(), "name_length": len(name),
            "name_terminated": b"\0" in field,
            "size_field": size_field, "aligned_field": aligned_field, "real_size": real,
            "derived_compressed_size": comp, "derived_length_aligned": alig,
            "compressed_size": max(comp, 0), "length_aligned": length,
            "compressed_underflow": comp < 0, "aligned_underflow": alig < 0,
            "original_kind": kind, "effective_kind": eff, "header_encryption_flag": enc,
            "metadata_filter": "real_size_over_256MiB" if real > 256 << 20 else
                               ("file_bit_absent" if not eff & 1 else "eligible"),
            "archive_offset": table_pos + p, "payload_offset_field": offset,
            "diagnostic_body_range": [offset + 46, offset + 46 + length],
            "diagnostic_body_range_within_archive": offset + 46 + length <= len(blob),
        })
        p = meta + 17
    return out, p, table_pos


def ref_counts(recs):
    def tally(key):
        out = {}
        for r in recs:
            out[str(r[key])] = out.get(str(r[key]), 0) + 1
        return dict(sorted(out.items(), key=lambda kv: int(kv[0])))
    filters = {}
    for r in recs:
        filters[r["metadata_filter"]] = filters.get(r["metadata_filter"], 0) + 1
    names = [bytes.fromhex(r["name_hex"]) for r in recs]
    return {
        "raw_records": len(recs), "metadata_eligible": filters.get("eligible", 0),
        "metadata_filter": dict(sorted(filters.items())),
        "original_kind": tally("original_kind"), "effective_kind": tally("effective_kind"),
        "effective_flags": {"file": sum(1 for r in recs if r["effective_kind"] & 1),
                            "encrypt_mixed": sum(1 for r in recs if r["effective_kind"] & 2),
                            "encrypt_header": sum(1 for r in recs
                                                  if r["effective_kind"] & 4)},
        "kind0_promotions": 0,
        "length_bias_underflows": {
            "compressed": sum(r["compressed_underflow"] for r in recs),
            "aligned": sum(r["aligned_underflow"] for r in recs),
            "any": sum(r["compressed_underflow"] or r["aligned_underflow"] for r in recs)},
        "names_without_nul": sum(not r["name_terminated"] for r in recs),
        "empty_names": sum(not n for n in names),
        "names_with_high_bytes": sum(any(b > 127 for b in n) for n in names),
        "duplicate_raw_names": len(names) - len(set(names)),
        "unique_raw_names": len(set(names)),
        "diagnostic_body_ranges_outside_archive":
            sum(not r["diagnostic_body_range_within_archive"] for r in recs),
    }


GOLDEN_REGION = bytes.fromhex("0123456789abcdef") + bytes(8) + b"\x11\x22\x33\x44"
SHARED = b"data\\shared\\common.txt\0\0"


def authored_archives():
    """28 literal archives covering the physical cases; each is a list of entry bytes."""
    specs = [
        [entry(raw_region=GOLDEN_REGION),                     # unterminated literal golden
         entry(b"data\\a.gat\0\0"),                           # header suffix
         entry(b"data\\dir\0", kind=0)],                      # file bit absent
        [entry(b"a.gat\0", size_field=715 + 99, real=100),     # compressed underflow
         entry(b"b.GND\0", aligned_field=37578, kind=3),       # aligned underflow
         entry(b"big.bin\0", size_field=0x10000001 + 715 + 5, real=0x10000001)],
        [entry(raw_region=b"\x01\x02\x03"),                   # empty name (derived 0)
         entry(b"\xb0\xa1\xff\x80\\x.spr\0"),                  # high bytes
         entry(b"\xb0\xa1\xff\x80\\x.spr\0", offset=7)],       # within-archive duplicate
        [entry(raw_region=ref_encode_region(b"abcdefgh", 8) + b"Zxyz\x01"),  # partial block
         entry((b"data\\" + b"k" * 190 + b".spr\0")[:200]),    # beyond 20 blocks
         entry(b"far.act\0", offset=0xfffff000)],              # range outside archive
    ]
    for i in range(4, 28):
        names = [b"data\\p%02d\\file%02d.str\0" % (i, i), b"ITEM%02d.Act\0\0" % i]
        if i in (4, 5, 6):
            names.append(SHARED)
        if i in (7, 8):
            names.append(b"data\\a.gat\0\0")                  # shared with archive 0
        specs.append([entry(n, kind=1 if i % 3 else 0x41) for n in names])
    return specs


class Env:
    """A private synthetic checkout, input root and output parent."""

    def __init__(self, test, mutate_profile=None, archives=None, core_os=None,
                 consumer_hook=None, phase_hook=None):
        PRIVATE.mkdir(parents=True, exist_ok=True)
        os.chmod(PRIVATE, 0o700)
        self.base = Path(os.path.realpath(tempfile.mkdtemp(prefix="t-", dir=PRIVATE)))
        test.addCleanup(self.cleanup)
        self.checkout = self.base / "checkout"
        for rel in ("docs/project/fixtures", "tools/renewal"):
            (self.checkout / rel).mkdir(parents=True)
        shutil.copyfile(HERE / "archive_catalog.py",
                        self.checkout / "tools/renewal/archive_catalog.py")
        shutil.copyfile(HERE / "archive_inventory_patches.py",
                        self.checkout / "tools/renewal/archive_inventory_patches.py")
        self.root = self.base / "root"
        (self.root / "acq").mkdir(parents=True)
        (self.root / "reused").mkdir()
        self.out_parent = self.base / "out"
        self.out_parent.mkdir(mode=0o700)
        os.chmod(self.out_parent, 0o700)
        self.output = self.out_parent / "inventory"
        self.blobs = {}
        self.build(archives or [archive(e) for e in authored_archives()], mutate_profile)
        self.core_os, self.consumer_hook, self.phase_hook = core_os, consumer_hook, phase_hook

    def build(self, blobs, mutate_profile):
        ledger, selected_expected, order = [], [], []
        dispositions = (["already"] * 2 + ["selected", "rgz"] * 28 + ["rgz"])[:59]
        sel = 0
        for ordinal, kind in enumerate(dispositions):
            index = 9000 + ordinal
            if kind == "rgz":
                file = f"synthetic_{index}.rgz"
                path = f"acq/{ordinal:02d}_{index}_{file}.body"
                data = b"\x1f\x8b\x08\x00" + bytes([ordinal]) * 20
                row = {"acquisition_status": "verified_new", "bytes": len(data),
                       "disposition": "unresolved_rgz_not_read", "family": "gzip_prefix",
                       "file": file, "index": index, "lf": 100 + ordinal,
                       "observed_gzip_prefix": {"compression_method": 8, "flags": 0,
                                                "hex": "1f8b08",
                                                "inner_grammar": "unresolved"},
                       "path": path, "sha256": sha(data), "source_ordinal": ordinal,
                       "url": f"https://example.invalid/patch/{file}"}
                self.write_locked(path, data)
            else:
                file = f"synthetic_{index}.gpf"
                if kind == "already":
                    data = archive([entry(b"old\0\0")])
                    path = f"reused/{file}"
                else:
                    data = blobs[sel]
                    path = f"acq/{ordinal:02d}_{index}_{file}.body"
                head = self.header_row(data)
                row = {"acquisition_status": "verified_reused" if kind == "already"
                       else "verified_new", "bytes": len(data),
                       "disposition": "already_inventoried_not_read" if kind == "already"
                       else "selected_for_inventory", "family": "grf_signature",
                       "file": file, "header": head, "index": index, "lf": 100 + ordinal,
                       "path": path, "sha256": sha(data), "source_ordinal": ordinal,
                       "url": f"https://example.invalid/patch/{file}"}
                if kind == "already":
                    self.write_locked(path, data)
                else:
                    self.write_archive(path, data)
                    self.blobs[index] = data
                    recs, consumed, table_pos = ref_records(data, file)
                    selected_expected.append({
                        "index": index, "counts": ref_counts(recs),
                        "header": {"declared_version": 258, "effective_version": 258,
                                   "header46_sha256": sha(data[:46]), "layout": "legacy",
                                   "raw_count_word": head["count_word"],
                                   "record_count": head["record_count"],
                                   "signature": "Master of Magic",
                                   "subtract_word": head["subtract_word"],
                                   "table_bytes": len(data) - table_pos,
                                   "table_end": len(data),
                                   "table_form": "clear legacy table to EOF",
                                   "table_start": table_pos},
                        "table": {"consumed_bytes": len(data) - table_pos,
                                  "stored_sha256": sha(data[table_pos:]),
                                  "trailing_bytes": 0, "trailing_sha256": sha(b"")}})
                    order.append(index)
                    sel += 1
            ledger.append(row)
        self.ledger = ledger
        selected = [r for r in ledger if r["disposition"] == "selected_for_inventory"]
        names = [{n for n in (r2["name_hex"] for r2 in ref_records(self.blobs[r["index"]],
                                                                   r["file"])[0])}
                 for r in selected]
        seen = {}
        for s in names:
            for n in s:
                seen[n] = seen.get(n, 0) + 1
        self.expected_shared = sum(1 for v in seen.values() if v > 1)
        self.expected_distinct = len(seen)
        real = json.loads((HERE.parents[1] / aip.PROFILE_REL).read_text())
        manifest = {"schema": "ro-patch-acquisition-ledger/1", "task": "T07.007.007",
                    "enumeration_basis": real["enumeration_basis"], "lookup_priority": None,
                    "priority_status": "not_established",
                    "source_evidence": real["source_evidence"], "ledger": ledger}
        self.manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
        self.manifest_path = self.root / "frozen" / "input-manifest.json"
        self.manifest_path.parent.mkdir()
        self.manifest_path.write_bytes(self.manifest_bytes)
        os.chmod(self.manifest_path, 0o600)
        core = (HERE / "archive_catalog.py").read_bytes()
        profile = dict(real)
        profile.update(
            core={"path": aip.CORE_REL, "bytes": len(core), "sha256": sha(core)},
            ledger=ledger, enumeration_order=order,
            already_inventoried_indices=[r["index"] for r in ledger
                                         if r["disposition"].startswith("already")],
            unresolved_rgz_indices=[r["index"] for r in ledger if r["family"] ==
                                    "gzip_prefix"],
            selected_expected=selected_expected,
            input_manifest=dict(real["input_manifest"], bytes=len(self.manifest_bytes),
                                sha256=sha(self.manifest_bytes)),
            output=dict(real["output"], records=[f"{i}.records.jsonl" for i in order]),
            totals={"already_inventoried_gpf_objects": 2, "gpf_objects": 30,
                    "ledger_bytes": sum(r["bytes"] for r in ledger), "ledger_objects": 59,
                    "selected_archive_bytes": sum(r["bytes"] for r in selected),
                    "selected_cross_archive_shared_raw_names": self.expected_shared,
                    "selected_distinct_raw_names": self.expected_distinct,
                    "selected_gpf_objects": 28,
                    "selected_raw_records": sum(r["header"]["record_count"]
                                                for r in selected),
                    "selected_table_bytes": sum(r["header"]["table_bytes"] for r in selected),
                    "selected_unused_tail_bytes": 0, "unresolved_rgz_objects": 29})
        if mutate_profile:
            mutate_profile(profile)
        self.profile = profile
        self.profile_bytes = (json.dumps(profile, indent=2, sort_keys=True) + "\n").encode()
        (self.checkout / aip.PROFILE_REL).write_bytes(self.profile_bytes)
        self.core_bytes = core

    @staticmethod
    def header_row(data):
        f30, f34, f38, version = struct.unpack_from("<IIII", data, 30)
        return {"count_word": f38, "header46_sha256": sha(data[:46]), "offset_word": f30,
                "record_count": max(f38 - f34 - 7, 0), "subtract_word": f34,
                "table_bytes": len(data) - f30 - 46, "table_start": f30 + 46,
                "version": version}

    def write_archive(self, rel, data):
        path = self.root / rel
        path.write_bytes(data)
        os.chmod(path, 0o600)

    def write_locked(self, rel, data):
        path = self.root / rel
        path.write_bytes(data)
        os.chmod(path, 0)  # never readable: proves the row is not opened

    def contract(self, **overrides):
        args = dict(core_os=self.core_os, consumer_hook=self.consumer_hook,
                    phase_hook=self.phase_hook)
        args.update(overrides)
        return aip._Contract(self.checkout, len(self.profile_bytes), sha(self.profile_bytes),
                             len(self.core_bytes), sha(self.core_bytes), **args)

    def run(self, **overrides):
        return aip._run(self.contract(**overrides), str(self.manifest_path), str(self.root),
                        str(self.output))

    def verify(self, output=None, **overrides):
        return aip._verify_inventory(str(output or self.output), self.contract(**overrides))

    def selected(self):
        return [r for r in self.ledger if r["disposition"] == "selected_for_inventory"]

    def cleanup(self):
        for dirpath, dirnames, filenames in os.walk(self.base):
            for name in dirnames + filenames:
                try:
                    os.chmod(os.path.join(dirpath, name), 0o700, follow_symlinks=False)
                except (OSError, NotImplementedError):
                    pass
        shutil.rmtree(self.base, ignore_errors=True)


def open_fds():
    return len(os.listdir("/dev/fd"))


class CoreOs:
    """Private fault boundary for a test-only core module instance."""

    def __init__(self, pread=None):
        self._pread = pread
        self.calls = 0

    def __getattr__(self, name):
        return getattr(os, name)

    def pread(self, fd, size, offset):
        self.calls += 1
        if self._pread is None:
            return os.pread(fd, size, offset)
        return self._pread(fd, size, offset, self.calls)


# --- Transform vectors ------------------------------------------------------------------------

class TransformVectorTests(unittest.TestCase):

    def test_literal_vectors_and_core_agreement(self):
        self.assertEqual(ref_block(bytes(8)).hex(), "0404015555015455")
        self.assertEqual(ref_block(bytes.fromhex("0123456789abcdef")).hex(),
                         "5176057698ead9eb")
        self.assertEqual(ref_decode_block(bytes.fromhex("0123456789abcdef")).hex(),
                         "4067146789fbc8fa")
        fds = aip._Fds()
        core, _ = aip._load_core(fds, aip.PRODUCTION)
        fds.close_quietly()
        for seed in range(300):
            block = hashlib.sha256(bytes([seed % 256, seed // 256])).digest()[:8]
            self.assertEqual(core.decode_name_block(block), ref_decode_block(block))
            self.assertEqual(ref_block(ref_block(block)), block)


# --- Successful synthetic inventory --------------------------------------------------------

class SuccessTests(unittest.TestCase):

    def test_complete_inventory_records_manifest_and_consumer(self):
        env = Env(self)
        before = open_fds()
        target, manifest, hashes = env.run()
        self.assertEqual(open_fds(), before, "descriptor leak")
        names = sorted(os.listdir(target))
        expected = sorted([f"{r['index']}.records.jsonl" for r in env.selected()] +
                          ["inventory-manifest.json", "inventory-complete.json"])
        self.assertEqual(names, expected)
        self.assertEqual(len(names), 30)
        self.assertEqual(stat.S_IMODE(os.stat(target).st_mode), 0o700)
        for name in names:
            info = os.stat(target / name)
            self.assertEqual((stat.S_IMODE(info.st_mode), info.st_nlink), (0o600, 1))
        # Records equal the independent reference model, byte for byte as canonical JSONL.
        for row in env.selected():
            recs, consumed, _ = ref_records(env.blobs[row["index"]], row["file"])
            lines = (target / f"{row['index']}.records.jsonl").read_bytes().splitlines(True)
            self.assertEqual(len(lines), len(recs))
            for line, ref in zip(lines, recs):
                ref = dict(ref, archive=row["file"], archive_sha256=row["sha256"])
                self.assertEqual(line, (json.dumps(ref, sort_keys=True, separators=(",", ":"))
                                        + "\n").encode("ascii"))
        totals = manifest["totals"]
        self.assertEqual(totals["selected_distinct_raw_names"], env.expected_distinct)
        self.assertEqual(totals["selected_cross_archive_shared_raw_names"], 2)
        self.assertEqual(env.expected_shared, 2)
        self.assertEqual(totals["selected_raw_records"],
                         sum(len(ref_records(env.blobs[r["index"]], "")[0])
                             for r in env.selected()))
        self.assertEqual(totals["selected_unused_tail_bytes"], 0)
        self.assertIsNone(manifest["lookup_priority"])
        self.assertEqual(manifest["priority_status"], "not_established")
        self.assertFalse(manifest["helper"]["executed"])
        self.assertTrue(manifest["core"]["executed"])
        self.assertEqual(len(manifest["ledger"]), 59)
        self.assertEqual(manifest["dispositions"]["unresolved_rgz_not_read"]["opened"], False)
        self.assertEqual(len(manifest["dispositions"]["unresolved_rgz_not_read"]["indices"]),
                         29)
        # Storage basename and original name are kept separate.
        first = manifest["archives"][0]
        self.assertTrue(first["storage_basename"].endswith(first["file"] + ".body"))
        rec = json.loads((target / f"{first['index']}.records.jsonl").read_bytes()
                         .splitlines()[0])
        self.assertEqual(rec["archive"], first["file"])
        complete = json.loads((target / "inventory-complete.json").read_bytes())
        self.assertEqual(complete["inventory_manifest_sha256"], hashes["manifest_sha256"])
        verified = env.verify()
        self.assertEqual(verified, manifest)
        self.assertEqual(open_fds(), before, "consumer descriptor leak")

    def test_literal_full_records(self):
        env = Env(self)
        target, _, _ = env.run()
        row = env.selected()[0]
        blob = env.blobs[row["index"]]
        table_pos = 46 + 64
        lines = [json.loads(x) for x in
                 (target / f"{row['index']}.records.jsonl").read_bytes().splitlines()]
        self.assertEqual(lines[0], {
            "aligned_field": 37595, "aligned_underflow": False, "archive": row["file"],
            "archive_offset": table_pos, "archive_sha256": sha(blob), "block_length": 22,
            "block_low_byte": 22, "compressed_size": 10, "compressed_underflow": False,
            "derived_compressed_size": 10, "derived_length_aligned": 16,
            "derived_name_length": 16, "diagnostic_body_range": [46, 62],
            "diagnostic_body_range_within_archive": True, "effective_kind": 3,
            "encoded_name_sha256": sha(GOLDEN_REGION[:16]), "encoded_region_bytes": 20,
            "encoded_region_sha256": sha(GOLDEN_REGION), "header_encryption_flag": "mixed",
            "length_aligned": 16, "metadata_filter": "eligible", "metadata_offset": 26,
            "name_hex": "4067146789fbc8fa0404015555015455", "name_length": 16,
            "name_start": 6, "name_terminated": False, "ordinal": 0, "original_kind": 1,
            "payload_offset_field": 0, "real_size": 0, "record_bytes": 43, "size_field": 725,
            "table_offset": 0, "transformed_blocks": 2, "untransformed_name_bytes": 0})
        self.assertEqual(bytes.fromhex(lines[1]["name_hex"]), b"data\\a.gat")
        self.assertEqual((lines[1]["header_encryption_flag"], lines[1]["effective_kind"],
                          lines[1]["table_offset"], lines[1]["derived_name_length"]),
                         ("header", 5, 43, 12))
        self.assertEqual((lines[2]["effective_kind"], lines[2]["metadata_filter"],
                          lines[2]["header_encryption_flag"]), (0, "file_bit_absent", None))
        under = [json.loads(x) for x in (target / f"{env.selected()[1]['index']}"
                                         ".records.jsonl").read_bytes().splitlines()]
        self.assertEqual((under[0]["derived_compressed_size"], under[0]["compressed_size"],
                          under[0]["compressed_underflow"], under[0]["effective_kind"],
                          under[0]["header_encryption_flag"], under[0]["metadata_filter"]),
                         (-1, 0, True, 0, None, "file_bit_absent"))
        self.assertEqual((under[1]["derived_length_aligned"], under[1]["length_aligned"],
                          under[1]["aligned_underflow"], under[1]["effective_kind"]),
                         (-1, 0, True, 2))
        self.assertEqual(under[2]["metadata_filter"], "real_size_over_256MiB")
        odd = [json.loads(x) for x in (target / f"{env.selected()[2]['index']}"
                                       ".records.jsonl").read_bytes().splitlines()]
        self.assertEqual((odd[0]["name_hex"], odd[0]["derived_name_length"],
                          odd[0]["encoded_name_sha256"]), ("", 0, sha(b"")))
        self.assertEqual(odd[1]["name_hex"], odd[2]["name_hex"])
        self.assertEqual(bytes.fromhex(odd[1]["name_hex"]), b"\xb0\xa1\xff\x80\\x.spr")
        part = [json.loads(x) for x in (target / f"{env.selected()[3]['index']}"
                                        ".records.jsonl").read_bytes().splitlines()]
        self.assertEqual((part[0]["derived_name_length"], part[0]["transformed_blocks"],
                          part[0]["untransformed_name_bytes"], part[0]["name_terminated"],
                          bytes.fromhex(part[0]["name_hex"])), (9, 1, 1, False, b"abcdefghZ"))
        self.assertEqual(part[1]["transformed_blocks"], 25)
        self.assertFalse(part[2]["diagnostic_body_range_within_archive"])

    def test_cumulative_record_bound_is_not_multiplied(self):
        env = Env(self)
        first_three = sum(len(ref_records(env.blobs[r["index"]], "")[0])
                          for r in env.selected()[:3])
        with mock.patch.object(aip, "MAX_RECORDS_TOTAL", first_three):
            with self.assertRaises(aip.InventoryError) as cm:
                env.run()
        self.assertEqual(cm.exception.category, "resource_limit")
        self.assertIn("inventory-failed.json", os.listdir(env.output))
        self.assertNotIn("inventory-complete.json", os.listdir(env.output))
        self.assertIn(f"{env.selected()[3]['index']}.records.jsonl", os.listdir(env.output))

    def test_aggregate_output_and_line_bounds(self):
        env = Env(self)
        with mock.patch.object(aip, "MAX_OUTPUT_BYTES_TOTAL", 4000):
            with self.assertRaises(aip.InventoryError) as cm:
                env.run()
        self.assertEqual(cm.exception.category, "resource_limit")
        env2 = Env(self)
        with mock.patch.object(aip, "MAX_JSON_LINE_BYTES", 900):
            with self.assertRaises(aip.InventoryError) as cm:
                env2.run()
        self.assertEqual(cm.exception.category, "resource_limit")


# --- Admission refusals before archive reads or output creation ----------------------------

class AdmissionTests(unittest.TestCase):

    def refuse(self, env, category, **overrides):
        reads = []
        hook = lambda phase, **info: reads.append(phase)  # noqa: E731
        with self.assertRaises(aip.InventoryError) as cm:
            aip._run(env.contract(phase_hook=hook, **overrides), str(env.manifest_path),
                     str(env.root), str(env.output))
        self.assertEqual(cm.exception.category, category, str(cm.exception))
        self.assertNotIn("archive_read", reads)
        self.assertFalse(os.path.lexists(env.output))
        return cm.exception

    def test_wrong_profile_core_and_generator_pins(self):
        env = Env(self)
        c = env.contract()
        bad = aip._Contract(env.checkout, len(env.profile_bytes), "0" * 64,
                            len(env.core_bytes), sha(env.core_bytes))
        with self.assertRaises(aip.InputError):
            aip._run(bad, str(env.manifest_path), str(env.root), str(env.output))
        bad = aip._Contract(env.checkout, len(env.profile_bytes), sha(env.profile_bytes),
                            len(env.core_bytes), "1" * 64)
        with self.assertRaises(aip.InputError):  # profile core pin differs from contract
            aip._run(bad, str(env.manifest_path), str(env.root), str(env.output))
        core_path = env.checkout / aip.CORE_REL
        core_path.write_bytes(env.core_bytes.replace(b"VERSION = ", b"VERSION= ", 1))
        self.refuse(env, "input_pin")
        core_path.write_bytes(env.core_bytes)
        self.assertTrue(c.core_path.exists())
        self.assertFalse(os.path.lexists(env.output))

    def test_production_profile_refuses_synthetic_manifest_before_output(self):
        env = Env(self)
        with self.assertRaises(aip.InputError):
            aip.run(str(env.manifest_path), str(env.root), str(env.output))
        self.assertFalse(os.path.lexists(env.output))

    def test_manifest_variants_refused(self):
        env = Env(self)
        doc = json.loads(env.manifest_bytes)

        def install(data):
            os.chmod(env.manifest_path, 0o600)
            env.manifest_path.write_bytes(data)
            env.profile["input_manifest"].update(bytes=len(data), sha256=sha(data))
            env.profile_bytes = (json.dumps(env.profile, indent=2, sort_keys=True) +
                                 "\n").encode()
            (env.checkout / aip.PROFILE_REL).write_bytes(env.profile_bytes)

        variants = []
        d = json.loads(env.manifest_bytes)
        d["ledger"][5]["bytes"] = float(d["ledger"][5]["bytes"])
        variants.append(json.dumps(d).encode())
        d = json.loads(env.manifest_bytes)
        d["ledger"][0]["lf"] = d["ledger"][0]["lf"] == d["ledger"][0]["lf"]  # bool, not int
        variants.append(json.dumps(d).encode())
        d = json.loads(env.manifest_bytes)
        d["extra"] = 1
        variants.append(json.dumps(d).encode())
        d = json.loads(env.manifest_bytes)
        del d["ledger"][-1]
        variants.append(json.dumps(d).encode())
        d = json.loads(env.manifest_bytes)
        d["ledger"][2]["disposition"] = "already_inventoried_not_read"  # selection change
        variants.append(json.dumps(d).encode())
        d = json.loads(env.manifest_bytes)
        d["ledger"][4]["host"] = "machine"
        variants.append(json.dumps(d).encode())
        variants.append(env.manifest_bytes[:-2] + b', "task": "T07.007.007"}\n')  # duplicate
        variants.append(env.manifest_bytes.replace(b'"lookup_priority": null',
                                                   b'"lookup_priority": NaN'))
        for data in variants:
            with self.subTest(data=data[:40]):
                install(data)
                self.refuse(env, "input_pin")
        install(env.manifest_bytes)
        self.assertEqual(json.loads(env.manifest_bytes), doc)

    def test_profile_selection_and_versions_refused(self):
        def select_rgz(profile):
            row = next(r for r in profile["ledger"] if r["family"] == "gzip_prefix")
            row["disposition"] = "selected_for_inventory"

        def bump_version(profile):
            profile["selected_expected"][0]["header"]["declared_version"] = 0x103

        def nonzero_tail(profile):
            profile["selected_expected"][0]["table"]["trailing_bytes"] = 1

        def escape(profile):
            profile["ledger"][2]["path"] = "../escape/x.gpf.body"

        def bool_index(profile):
            profile["ledger"][0]["index"] = True

        def reorder(profile):
            profile["enumeration_order"] = list(reversed(profile["enumeration_order"]))

        for mutate in (select_rgz, bump_version, nonzero_tail, escape, bool_index, reorder):
            with self.subTest(mutate.__name__):
                env = Env(self, mutate_profile=mutate)
                self.refuse(env, "input_pin")

    def test_path_refusals(self):
        env = Env(self)
        link = env.base / "rootlink"
        os.symlink(env.root, link)
        with self.assertRaises(aip.InputError):
            aip._run(env.contract(), str(env.manifest_path), str(link), str(env.output))
        with self.assertRaises(aip.InputError):
            aip._run(env.contract(), str(env.manifest_path), "relative/root", str(env.output))
        with self.assertRaises(aip.InputError):
            aip._run(env.contract(), str(env.manifest_path), str(env.root) + "/../root",
                     str(env.output))
        self.assertFalse(os.path.lexists(env.output))
        row = env.selected()[5]
        path = env.root / row["path"]
        data = path.read_bytes()
        for kind in ("symlink", "hardlink", "fifo", "directory"):
            with self.subTest(kind):
                os.unlink(path) if not path.is_dir() or path.is_symlink() else os.rmdir(path)
                spare = env.base / f"spare-{kind}"
                if kind == "symlink":
                    spare.write_bytes(data)
                    os.symlink(spare, path)
                elif kind == "hardlink":
                    spare.write_bytes(data)
                    os.link(spare, path)
                elif kind == "fifo":
                    os.mkfifo(path)
                else:
                    os.mkdir(path)
                self.refuse(env, "input_pin")
                os.unlink(path) if not path.is_dir() or path.is_symlink() else os.rmdir(path)
                path.write_bytes(data)
        parent_link = env.root / "acq-moved"
        os.rename(env.root / "acq", parent_link)
        os.symlink(parent_link, env.root / "acq")
        self.refuse(env, "input_pin")

    def test_output_exists_inside_root_and_untrusted_parent(self):
        env = Env(self)
        env.output.mkdir(mode=0o700)
        (env.output / "keep").write_bytes(b"x")
        with self.assertRaises(aip.OutputError):
            env.run()
        self.assertEqual(os.listdir(env.output), ["keep"])
        with self.assertRaises(aip.OutputError):
            aip._run(env.contract(), str(env.manifest_path), str(env.root),
                     str(env.root / "inside"))
        self.assertFalse(os.path.lexists(env.root / "inside"))
        loose = env.base / "loose"
        loose.mkdir()
        os.chmod(loose, 0o777)
        with self.assertRaises(aip.OutputError):
            aip._run(env.contract(), str(env.manifest_path), str(env.root),
                     str(loose / "out"))
        self.assertFalse(os.path.lexists(loose / "out"))


# --- Archive changes, profile mismatches and source rejections -----------------------------

class ArchiveFailureTests(unittest.TestCase):

    def assert_failed(self, env, category):
        with self.assertRaises(aip.InventoryError) as cm:
            env.run()
        self.assertEqual(cm.exception.category, category, str(cm.exception))
        listing = os.listdir(env.output)
        self.assertIn("inventory-failed.json", listing)
        self.assertNotIn("inventory-complete.json", listing)
        marker = json.loads((env.output / "inventory-failed.json").read_bytes())
        self.assertEqual((marker["status"], marker["category"]), ("failed", category))
        with self.assertRaises(aip.VerificationError):
            env.verify()
        return cm.exception

    def test_changed_full_hash(self):
        env = Env(self)
        row = env.selected()[6]
        path = env.root / row["path"]
        data = bytearray(path.read_bytes())
        data[50] ^= 0xff  # payload byte only: header/table unchanged, full hash differs
        path.write_bytes(bytes(data))
        self.assert_failed(env, "input_pin")

    def test_archive_replaced_after_admission(self):
        env = Env(self)
        row = env.selected()[4]

        def hook(phase, **info):
            if phase == "archive_read" and info["index"] == row["index"]:
                path = env.root / row["path"]
                data = path.read_bytes()
                os.unlink(path)
                path.write_bytes(data)  # identical bytes, different file
        env.phase_hook = hook
        self.assert_failed(env, "input_pin")

    def test_archive_modified_before_completion_fails_rehash(self):
        env = Env(self)
        row = env.selected()[9]

        def hook(phase, **info):
            if phase == "records_written":
                path = env.root / row["path"]
                fd = os.open(path, os.O_WRONLY)
                os.pwrite(fd, b"Q", 60)
                os.close(fd)
        env.phase_hook = hook
        self.assert_failed(env, "input_pin")

    def test_header_profile_mismatch_and_nonzero_tail(self):
        blobs = [archive(e) for e in authored_archives()]
        env = Env(self, archives=blobs,
                  mutate_profile=lambda p: p["selected_expected"][3]["header"].update(
                      signature="Event Horizon"))
        self.assert_failed(env, "profile_mismatch")
        tail = list(blobs)
        tail[2] = archive(authored_archives()[2], trailing=b"\0tail")
        env = Env(self, archives=tail)  # the profile still requires the frozen zero tail
        exc = self.assert_failed(env, "profile_mismatch")
        self.assertIn("trailing", str(exc))

    def test_unsupported_version_and_source_rejection(self):
        blobs = [archive(e) for e in authored_archives()]
        blobs[1] = archive(authored_archives()[1], version=0x103)

        def keep_legacy(profile):
            for row in profile["ledger"]:
                if row.get("header", {}).get("version") == 0x103:
                    row["header"]["version"] = 0x102
        env = Env(self, archives=blobs, mutate_profile=keep_legacy)
        # The ledger/profile still claims 0x102; the manifest carries the true version, so
        # the pins disagree before reading. Rebuild the manifest from the profile ledger.
        data = json.loads(env.manifest_bytes)
        data["ledger"] = env.profile["ledger"]
        raw = (json.dumps(data, indent=2, sort_keys=True) + "\n").encode()
        env.manifest_path.write_bytes(raw)
        env.profile["input_manifest"].update(bytes=len(raw), sha256=sha(raw))
        env.profile_bytes = (json.dumps(env.profile, indent=2, sort_keys=True) + "\n").encode()
        (env.checkout / aip.PROFILE_REL).write_bytes(env.profile_bytes)
        self.assert_failed(env, "unsupported")
        bad = [archive(e) for e in authored_archives()]
        specs = authored_archives()
        bad[7] = archive(specs[7][:-1] + [specs[7][-1][:-3]])  # truncated last record
        def declared(profile):  # the frozen header still declares the truncated record
            profile["selected_expected"][7]["counts"]["raw_records"] += 1
        env = Env(self, archives=bad, mutate_profile=declared)
        self.assert_failed(env, "source_rejection")


# --- Real I/O fault controls ---------------------------------------------------------------

class IoFaultTests(unittest.TestCase):

    def failed(self, env, category=None):
        with self.assertRaises(aip.InventoryError) as cm:
            env.run()
        if category:
            self.assertEqual(cm.exception.category, category, str(cm.exception))
        if os.path.lexists(env.output):
            self.assertNotIn("inventory-complete.json", os.listdir(env.output))
        return cm.exception

    def test_short_initial_header_read_keeps_honest_refusal(self):
        def pread(fd, size, offset, calls):
            data = os.pread(fd, size, offset)
            return data[:20] if offset == 0 and size == 46 else data
        env = Env(self, core_os=CoreOs(pread))
        self.failed(env, "source_rejection")
        self.assertIn("inventory-failed.json", os.listdir(env.output))

    def test_zero_read_and_persistent_interrupt_in_stream_fail(self):
        def zero(fd, size, offset, calls):  # the streamed pass ends early
            return b"" if size == 8 << 20 else os.pread(fd, size, offset)
        env = Env(self, core_os=CoreOs(zero))
        self.failed(env, "input_pin")

        def interrupted(fd, size, offset, calls):
            if size == 8 << 20:
                raise InterruptedError(errno.EINTR, "interrupted")
            return os.pread(fd, size, offset)
        env = Env(self, core_os=CoreOs(interrupted))
        self.failed(env, "os_error")

    def test_positive_short_reads_succeed(self):
        def short(fd, size, offset, calls):
            return os.pread(fd, 37, offset) if size == 8 << 20 else os.pread(fd, size, offset)
        core_os = CoreOs(short)
        env = Env(self, core_os=core_os)
        with mock.patch.object(aip, "_read_chunk",
                               lambda fd, n: os.read(fd, max(1, min(n, 1000)))):
            env.run()
        self.assertGreater(core_os.calls, 28 * 5)  # many legal positive short reads
        env.verify(core_os=None)

    def test_own_reads_zero_and_interrupt(self):
        env = Env(self)
        with mock.patch.object(aip, "_read_chunk", lambda fd, n: b""):
            with self.assertRaises(aip.InputError):
                env.run()
        self.assertFalse(os.path.lexists(env.output))

        def always(fd, n):
            raise InterruptedError(errno.EINTR, "interrupted")
        with mock.patch.object(aip, "_read_chunk", always):
            with self.assertRaises(aip.InputError):
                env.run()
        calls = {"n": 0}

        def transient(fd, n):
            calls["n"] += 1
            if calls["n"] % 3 == 1:
                raise InterruptedError(errno.EINTR, "interrupted")
            return os.read(fd, n)
        with mock.patch.object(aip, "_read_chunk", transient):
            env.run()
        env.verify()

    def test_short_zero_interrupted_and_failed_writes(self):
        env = Env(self)
        with mock.patch.object(aip, "_write_chunk",
                               lambda fd, view: os.write(fd, view[:max(1, len(view) // 3)])):
            env.run()
        env.verify()
        for name, writer in (
                ("zero", lambda fd, view: 0),
                ("negative", lambda fd, view: -1),
                ("bool", lambda fd, view: True),
                ("error", lambda fd, view: (_ for _ in ()).throw(OSError(errno.EIO, "io"))),
                ("eintr", lambda fd, view: (_ for _ in ()).throw(
                    InterruptedError(errno.EINTR, "intr")))):
            with self.subTest(name):
                env = Env(self)
                with mock.patch.object(aip, "_write_chunk", writer):
                    exc = self.failed(env)
                # Every write fails, so the failure marker cannot be published either; an
                # empty owned marker may remain and still signals failure.
                self.assertIn("failure marker not written", str(exc))
                with self.assertRaises(aip.VerificationError):
                    env.verify()

    def test_fsync_close_and_readback_failures(self):
        def bad_fsync(fd):
            raise OSError(errno.EIO, "fsync")
        env = Env(self)
        with mock.patch.object(aip, "_fsync", bad_fsync):
            self.failed(env, "os_error")
        real_close = os.close
        armed = {"on": False}

        def bad_close(fd):
            real_close(fd)
            if armed["on"]:
                raise OSError(errno.EIO, "close")

        def arm(phase, **info):
            if phase == "output_reserved":
                armed["on"] = True
        env = Env(self, phase_hook=arm)
        before = open_fds()
        with mock.patch.object(aip, "_close_fd", bad_close):
            self.failed(env, "os_error")
        self.assertEqual(open_fds(), before)

        def growing_fsync(fd):
            os.write(fd, b"!")  # bytes appear that the run did not generate
            os.fsync(fd)
        env = Env(self)
        with mock.patch.object(aip, "_fsync", growing_fsync):
            self.failed(env, "output")
        self.assertIn("inventory-failed.json", os.listdir(env.output))

    def test_failure_marker_publication_failure(self):
        env = Env(self)
        calls = {"n": 0}

        def boom(phase, **info):
            if phase == "before_completion":
                raise RuntimeError("synthetic")
        real = aip._write_chunk

        def writer(fd, view):
            if b'"status": "failed"' in bytes(view):
                raise OSError(errno.ENOSPC, "full")
            calls["n"] += 1
            return real(fd, view)
        env.phase_hook = boom
        with mock.patch.object(aip, "_write_chunk", writer):
            exc = self.failed(env, "unexpected")
        self.assertIn("failure marker not written", str(exc))
        listing = os.listdir(env.output)
        self.assertNotIn("inventory-complete.json", listing)
        self.assertEqual((env.output / "inventory-failed.json").read_bytes(), b"")

    def test_unexpected_after_completion_removes_owned_marker(self):
        env = Env(self)

        def boom(phase, **info):
            if phase == "after_completion":
                raise RuntimeError("synthetic")
        env.phase_hook = boom
        before = open_fds()
        exc = self.failed(env, "unexpected")
        self.assertEqual(open_fds(), before)
        listing = os.listdir(env.output)
        self.assertIn("inventory-failed.json", listing)
        self.assertNotIn("inventory-complete.json", listing)
        self.assertNotIn("synthetic", str(exc))

    def test_foreign_completion_and_files_preserved(self):
        env = Env(self)

        def swap_marker(phase, **info):
            if phase == "after_completion":
                path = env.output / "inventory-complete.json"
                data = path.read_bytes()
                os.unlink(path)
                path.write_bytes(data)
                os.chmod(path, 0o600)
        env.phase_hook = swap_marker
        with self.assertRaises(aip.InventoryError) as cm:
            env.run()
        self.assertEqual(cm.exception.category, "output")
        self.assertIn("could not remove inventory-complete.json", str(cm.exception))
        self.assertIn("inventory-complete.json", os.listdir(env.output))  # foreign kept
        self.assertIn("inventory-failed.json", os.listdir(env.output))
        with self.assertRaises(aip.VerificationError):
            env.verify()
        env = Env(self)

        def extra(phase, **info):
            if phase == "before_completion":
                (env.output / "intruder").write_bytes(b"foreign")
        env.phase_hook = extra
        self.failed(env, "output")
        self.assertEqual((env.output / "intruder").read_bytes(), b"foreign")

    def test_directory_replaced_and_record_file_replaced(self):
        env = Env(self)
        moved = env.out_parent / "moved"

        def swap_dir(phase, **info):
            if phase == "before_completion":
                os.rename(env.output, moved)
                os.mkdir(env.output, 0o700)
                (env.output / "foreign").write_bytes(b"f")
        env.phase_hook = swap_dir
        exc = self.failed(env, "output")
        self.assertIn("not verifiable", str(exc))
        self.assertEqual(os.listdir(env.output), ["foreign"])
        self.assertNotIn("inventory-complete.json", os.listdir(moved))
        env = Env(self)
        row = env.selected()[0]

        def swap_records(phase, **info):
            if phase == "before_completion":
                path = env.output / f"{row['index']}.records.jsonl"
                data = path.read_bytes()
                os.unlink(path)
                path.write_bytes(data)
                os.chmod(path, 0o600)
        env.phase_hook = swap_records
        self.failed(env, "output")
        self.assertIn("inventory-failed.json", os.listdir(env.output))


# --- Consumer gate -----------------------------------------------------------------------------

def rewrite(output, records=None, manifest=None, complete=True):
    """Rewrite record/manifest bytes and rehash the full chain consistently."""
    output = Path(output)
    doc = json.loads((output / "inventory-manifest.json").read_bytes())
    for index, fn in (records or {}).items():
        path = output / f"{index}.records.jsonl"
        lines = [json.loads(x) for x in path.read_bytes().splitlines()]
        lines = fn(lines)
        data = b"".join((json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n").encode()
                        for r in lines)
        os.chmod(path, 0o600)
        path.write_bytes(data)
        for entry in doc["archives"]:
            if entry["index"] == index:
                entry["records_file"].update(bytes=len(data), lines=len(lines),
                                             sha256=sha(data))
    if manifest:
        manifest(doc)
    raw = (json.dumps(doc, ensure_ascii=True, indent=1, sort_keys=True) + "\n").encode()
    (output / "inventory-manifest.json").write_bytes(raw)
    if complete:
        path = output / "inventory-complete.json"
        comp = json.loads(path.read_bytes())
        comp["inventory_manifest_bytes"] = len(raw)
        comp["inventory_manifest_sha256"] = sha(raw)
        comp["record_files"] = {e["records_file"]["file"]: e["records_file"]["sha256"]
                                for e in doc["archives"]}
        path.write_bytes((json.dumps(comp, ensure_ascii=True, indent=1, sort_keys=True) +
                          "\n").encode())


class ConsumerTests(unittest.TestCase):

    def fresh(self):
        env = Env(self)
        env.run()
        copy = env.out_parent / "copy"
        shutil.copytree(env.output, copy)
        os.chmod(copy, 0o700)
        for name in os.listdir(copy):
            os.chmod(copy / name, 0o600)
        env.verify(copy)
        return env, copy

    def refused(self, env, output):
        with self.assertRaises(aip.VerificationError):
            env.verify(output)

    def test_rehashed_semantic_forgeries_refused(self):
        env, _ = self.fresh()
        first = env.selected()[0]["index"]
        second = env.selected()[1]["index"]

        def typed(lines):
            lines[0]["real_size"] = True if lines[0]["real_size"] == 1 else 1.0
            return lines

        def kind(lines):
            lines[1]["effective_kind"] = 3
            return lines

        def source(lines):
            lines[0]["archive_sha256"] = "0" * 64
            return lines

        def name(lines):
            lines[0]["name_hex"] = "41" * lines[0]["name_length"]
            return lines

        def reorder(lines):
            return [lines[1], lines[0]] + lines[2:]

        def drop(lines):
            return lines[:-1]

        def duplicate(lines):
            return lines + [lines[-1]]

        def bias(lines):
            lines[0]["derived_compressed_size"] = 11
            lines[0]["compressed_size"] = 11
            return lines

        def extra_key(lines):
            lines[0]["row"] = 0
            return lines

        cases = [{first: f} for f in (typed, kind, source, name, reorder, drop, duplicate,
                                      bias, extra_key)]
        for case in cases:
            with self.subTest(list(case.values())[0].__name__):
                copy = self.copy_of(env)
                rewrite(copy, records=case)
                self.refused(env, copy)

        def summary(doc):
            doc["archives"][1]["counts"]["names_with_high_bytes"] += 1

        def totals(doc):
            doc["totals"]["selected_distinct_raw_names"] += 1

        def association(doc):
            doc["archives"][0]["storage_path"] = doc["archives"][1]["storage_path"]

        def priority(doc):
            doc["lookup_priority"] = [first, second]

        def ledger(doc):
            doc["ledger"][0]["bytes"] = doc["ledger"][0]["bytes"] + 1

        def helper(doc):
            doc["helper"]["executed"] = True

        for mutate in (summary, totals, association, priority, ledger, helper):
            with self.subTest(mutate.__name__):
                copy = self.copy_of(env)
                rewrite(copy, manifest=mutate)
                self.refused(env, copy)

    def test_zero_block_complete_encoded_name_hash_relation(self):
        # Two independent 139-byte literals: block8, region6, derived2, zero
        # transformed blocks. Encoded-name hashes cover exactly TWO bytes.
        cases = [
            ("last_nul", b"A\0xxxx", "41", True,
             "e61c21ca716b3b1aefb7d1198f83679c4ca4d596e5792275dd6203b49216237d",
             "8fa7ed3638737a3191a1779a329ecaf8907fe4ac4593dbf0fb7760abe8e5dec1",
             "5dd0617aa72533439a31d6b6eead2011126458799ca857832c5737210699e837",
             "4d6173746572206f66204d61676963004b4b4b4b4b4b4b4b4b4b4b4b4b4b40000000"
             "030000000b0000000201000050505050505050505050505050505050505050505050"
             "50505050505050505050505050505050505050505050505050505050505050505050"
             "5050505050505050080000000000410078787878d5020000db920000000000000100"
             "000000"),
            ("unterminated", b"ABxxxx", "4142", False,
             "38164fbd17603d73f696b8b4d72664d735bb6a7c88577687fd2ae33fd6964153",
             "5ffb4ea50d12d9bcd2c5b27a13a69df43442173bbb7ff71ba324edb8e7eb1e25",
             "25bdd0996b29bd6da640f1c2e83c38805343dc17433ee327a290ffe4ac658ddf",
             "4d6173746572206f66204d61676963004b4b4b4b4b4b4b4b4b4b4b4b4b4b40000000"
             "030000000b0000000201000050505050505050505050505050505050505050505050"
             "50505050505050505050505050505050505050505050505050505050505050505050"
             "5050505050505050080000000000414278787878d5020000db920000000000000100"
             "000000")]
        for name, region, name_hex, terminated, encoded_sha, region_sha, blob_sha, literal_hex in cases:
            with self.subTest(name):
                literal = bytes.fromhex(literal_hex)
                self.assertEqual((len(literal), sha(literal)), (139, blob_sha))
                self.assertEqual(sha(region[:2]), encoded_sha)
                self.assertEqual(sha(region), region_sha)
                blob = archive([entry(raw_region=region, block_len=8)])
                self.assertEqual(blob, literal)  # Fixture encoder cannot supply its own oracle.
                env = Env(self, archives=[blob] * 28)
                descriptors = sorted(os.listdir("/dev/fd"))
                target, manifest, _ = env.run()
                self.assertEqual(env.verify(), manifest)  # Full 28-archive positive baseline.
                self.assertEqual(len(manifest["archives"]), 28)
                files = sorted(os.listdir(target))
                self.assertEqual(len(files), 30)
                first = env.selected()[0]["index"]
                record_path = target / f"{first}.records.jsonl"
                record = json.loads(record_path.read_bytes())
                expected = {"block_length": 8, "encoded_region_bytes": 6,
                            "derived_name_length": 2, "transformed_blocks": 0,
                            "untransformed_name_bytes": 2, "name_hex": name_hex,
                            "name_terminated": terminated, "encoded_name_sha256": encoded_sha,
                            "encoded_region_sha256": region_sha}
                self.assertEqual({k: record[k] for k in expected}, expected)
                hits = []
                def corrupt(records):
                    self.assertEqual(len(records), 1)
                    self.assertEqual(records[0]["encoded_name_sha256"], encoded_sha)
                    records[0]["encoded_name_sha256"] = "0" * 64
                    hits.append(True)
                    return records
                rewrite(target, records={first: corrupt})
                self.assertEqual(hits, [True])
                changed_record = record_path.read_bytes()
                self.assertEqual(json.loads(changed_record)["encoded_name_sha256"], "0" * 64)
                manifest_bytes = (target / "inventory-manifest.json").read_bytes()
                changed_manifest = json.loads(manifest_bytes)
                complete = json.loads((target / "inventory-complete.json").read_bytes())
                self.assertEqual(changed_manifest["archives"][0]["records_file"]["sha256"], sha(changed_record))
                self.assertEqual(complete["record_files"][record_path.name], sha(changed_record))
                self.assertEqual((complete["inventory_manifest_bytes"], complete["inventory_manifest_sha256"]),
                                 (len(manifest_bytes), sha(manifest_bytes)))
                before = {f: (target / f).read_bytes() for f in files}
                with self.assertRaises(aip.VerificationError):
                    env.verify()
                self.assertEqual({f: (target / f).read_bytes() for f in files}, before)
                self.assertEqual(sorted(os.listdir(target)), files)
                self.assertEqual(sorted(os.listdir("/dev/fd")), descriptors)

    def copy_of(self, env):
        src = env.output
        n = len([p for p in os.listdir(env.out_parent) if p.startswith("c")])
        copy = env.out_parent / f"c{n}"
        shutil.copytree(src, copy)
        os.chmod(copy, 0o700)
        for name in os.listdir(copy):
            os.chmod(copy / name, 0o600)
        return copy

    def test_tree_shape_and_mode_refusals(self):
        env, _ = self.fresh()
        cases = []
        copy = self.copy_of(env)
        (copy / "inventory-failed.json").write_bytes(b"{}\n")
        os.chmod(copy / "inventory-failed.json", 0o600)
        cases.append(copy)
        copy = self.copy_of(env)
        (copy / "extra").write_bytes(b"")
        cases.append(copy)
        copy = self.copy_of(env)
        os.unlink(copy / "inventory-complete.json")
        cases.append(copy)
        copy = self.copy_of(env)
        os.chmod(copy / "inventory-manifest.json", 0o644)
        cases.append(copy)
        copy = self.copy_of(env)
        os.chmod(copy, 0o755)
        cases.append(copy)
        copy = self.copy_of(env)
        name = f"{env.selected()[2]['index']}.records.jsonl"
        os.link(copy / name, env.base / "hard")
        cases.append(copy)
        copy = self.copy_of(env)
        name = f"{env.selected()[3]['index']}.records.jsonl"
        os.rename(copy / name, env.base / "moved-records")
        os.symlink(env.base / "moved-records", copy / name)
        cases.append(copy)
        copy = self.copy_of(env)
        raw = (copy / "inventory-manifest.json").read_bytes()
        (copy / "inventory-manifest.json").write_bytes(raw[:-2] + b',\n "task": "T07.007.007"\n}\n')
        cases.append(copy)
        copy = self.copy_of(env)
        rewrite(copy, complete=False)  # unchanged content but stale binding? recanonicalised
        cases_ok = copy
        link = env.out_parent / "linkdir"
        os.symlink(self.copy_of(env), link)
        cases.append(link)
        for case in cases:
            with self.subTest(str(case.name)):
                self.refused(env, case)
        env.verify(cases_ok)  # canonical rewrite of identical content stays valid

    def test_changed_source_profile_and_mutation_during_read(self):
        env, copy = self.fresh()
        other = aip._Contract(env.checkout, len(env.profile_bytes), "2" * 64,
                              len(env.core_bytes), sha(env.core_bytes))
        with self.assertRaises(aip.VerificationError):
            aip._verify_inventory(str(copy), other)
        gen = env.checkout / aip.GENERATOR_REL
        original = gen.read_bytes()
        gen.write_bytes(original + b"\n# changed\n")
        self.refused(env, copy)
        gen.write_bytes(original)
        env.verify(copy)

        def mutate(output):
            path = Path(output) / f"{env.selected()[0]['index']}.records.jsonl"
            data = path.read_bytes()
            os.unlink(path)
            path.write_bytes(data)
            os.chmod(path, 0o600)
        with self.assertRaises(aip.VerificationError):
            env.verify(copy, consumer_hook=mutate)

        def touch_profile(output):
            path = env.checkout / aip.PROFILE_REL
            data = path.read_bytes()
            os.unlink(path)
            path.write_bytes(data)
        copy2 = self.copy_of(env)
        with self.assertRaises(aip.VerificationError):
            env.verify(copy2, consumer_hook=touch_profile)

    def test_consumer_is_read_only(self):
        env, copy = self.fresh()
        before = {n: (os.stat(copy / n).st_mtime_ns, (copy / n).read_bytes())
                  for n in os.listdir(copy)}
        env.verify(copy)
        after = {n: (os.stat(copy / n).st_mtime_ns, (copy / n).read_bytes())
                 for n in os.listdir(copy)}
        self.assertEqual(before, after)


# --- CLI ----------------------------------------------------------------------------------------

class CliTests(unittest.TestCase):

    def test_cli_has_no_overrides_and_failures_are_path_free(self):
        env = Env(self)
        secret = str(env.base)
        proc = subprocess.run([sys.executable, "-I", "-B", str(HERE / "archive_inventory_patches.py"),
                               str(env.manifest_path), str(env.root), str(env.output)],
                              capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertIn("error [input_pin]", proc.stderr)
        self.assertNotIn(secret, proc.stderr)
        self.assertLessEqual(len(proc.stderr), 1100)
        self.assertFalse(os.path.lexists(env.output))
        proc = subprocess.run([sys.executable, "-I", "-B",
                               str(HERE / "archive_inventory_patches.py"), "--profile", "x",
                               "a", "b", "c"], capture_output=True, text=True, timeout=60)
        self.assertNotEqual(proc.returncode, 0)


# --- Actual input (gated) ----------------------------------------------------------------------

class ActualInputTests(unittest.TestCase):

    def test_actual_inventory(self):
        manifest = os.environ.get("T07_007_007_INPUT_MANIFEST")
        root = os.environ.get("T07_007_007_INPUT_ROOT")
        parent = os.environ.get("T07_007_007_OUTPUT_PARENT")
        if not (manifest and root and parent):
            self.skipTest("actual inputs not supplied (T07_007_007_* unset)")
        output = Path(tempfile.mkdtemp(dir=parent)) / "inventory"
        _target, result, _ = aip.run(manifest, root, str(output))
        self.assertEqual(result["totals"]["selected_raw_records"], 5742)
        self.assertEqual(aip.verify_inventory(str(output)), result)


if __name__ == "__main__":
    unittest.main()
