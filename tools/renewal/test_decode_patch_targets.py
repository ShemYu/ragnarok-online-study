"""Tests for decode_patch_targets. Run: python3 -I -m unittest discover -s tools/renewal -p 'test_decode_patch_targets.py'

Cipher tests use the pinned authored literal vectors from the checkout (not
self-roundtrips only). End-to-end tests build a small synthetic GPF, five
synthetic source files and a synthetic contract in a temporary directory; the
synthetic contract is private to these tests and the public consumer must
reject its output. The real-patch test runs only when $PATCH_DECODER_SOURCE_ROOT
and $PATCH_DECODER_PATCH name the admitted inputs.

Chapter1Rsw* tests exercise the fixed one-record --chapter1-rsw route (T07.007.014.001)
with the same built-in route descriptor and a private synthetic profile/patch;
they never read a real archive or body. RemainingRsw* tests do the same for the
fixed seventeen-record --remaining-rsw route (T07.007.014.006).
"""

import hashlib
import errno
import json
import os
from pathlib import Path
import random
import shutil
import stat
import sys
import tempfile
import unittest
from unittest import mock
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent))
import decode_patch_targets as dpt  # noqa: E402

VECTORS = json.loads((dpt.REPO / dpt.VECTORS_PATH).read_bytes())
PROFILE = json.loads((dpt.REPO / dpt.PROFILE_PATH).read_bytes())


def sha(data):
    return hashlib.sha256(data).hexdigest()


# Test-side encryptor: the block transform is self-inverse, the shuffle is not.
_ENC_DEST = (3, 4, 6, 0, 1, 2, 5)


def shuffle_enc(block):
    out = bytearray(8)
    for i in range(7):
        out[_ENC_DEST[i]] = block[i]
    out[7] = dpt._SHUFFLE_TABLE[block[7]]
    return bytes(out)


def encrypt(plain, kind, compressed_size):
    data = bytearray(plain)
    blocks = len(data) // 8
    if kind & dpt.KIND_MIXED:
        cycle = dpt.mixed_cycle(compressed_size)
        j = -1
        for i in range(blocks):
            at = 8 * i
            if i < 20 or i % cycle == 0:
                data[at:at + 8] = dpt.transform_block(bytes(data[at:at + 8]))
                continue
            j += 1
            if j and j % 7 == 0:
                data[at:at + 8] = shuffle_enc(bytes(data[at:at + 8]))
    elif kind & dpt.KIND_HEADER:
        for i in range(min(20, blocks)):
            data[8 * i:8 * i + 8] = dpt.transform_block(bytes(data[8 * i:8 * i + 8]))
    return bytes(data)


class CipherTests(unittest.TestCase):
    def test_fixed_block_and_shuffle_anchors(self):
        for row in VECTORS["fixed_block_vectors"]:
            self.assertEqual(dpt.transform_block(bytes.fromhex(row["input_hex"])).hex(),
                             row["output_hex"])
        for row in VECTORS["fixed_shuffle_vectors"]:
            self.assertEqual(dpt.unshuffle_block(bytes.fromhex(row["input_hex"])).hex(),
                             row["output_hex"])
        self.assertEqual(len(VECTORS["fixed_block_vectors"]), 2)

    def test_all_authored_cipher_vectors(self):
        self.assertEqual(dpt.check_vectors(VECTORS), 252)
        kinds = {(r["kind"], r["length"]) for r in VECTORS["cipher_vectors"]}
        self.assertIn((7, 513), kinds)  # mixed+header bits, partial tail
        self.assertIn((3, 161), kinds)

    def test_mutated_vector_is_refused(self):
        bad = json.loads(json.dumps(VECTORS))
        row = next(r for r in bad["cipher_vectors"] if r["length"] == 264 and r["kind"] == 3)
        row["output_sha256"] = "0" * 64
        with self.assertRaises(dpt.Refusal) as cm:
            dpt.check_vectors(bad)
        self.assertEqual(cm.exception.code, "vector-cipher-mismatch")
        bad = json.loads(json.dumps(VECTORS))
        bad["fixed_shuffle_vectors"][1]["output_hex"] = "0304060001020507"
        with self.assertRaises(dpt.Refusal):
            dpt.check_vectors(bad)

    def test_cycle_digit_boundaries(self):
        expected = {0: 1, 9: 1, 99: 1, 100: 4, 9999: 5, 10000: 14, 999999: 15,
                    1000000: 22, 9999999: 22, 10000000: 23, 1000000000: 25}
        for size, cycle in expected.items():
            self.assertEqual(dpt.mixed_cycle(size), cycle, size)
        with self.assertRaises(ValueError):
            dpt.mixed_cycle(True)

    def test_eighth_non_des_block_is_the_first_shuffled(self):
        # cycle 22: block 22 is DES; non-DES blocks 20,21,23..28 get j=0..7.
        plain = bytes(range(256)) * 2  # 64 blocks
        out = dpt.decrypt(plain, 3, 1234567)
        self.assertEqual(dpt.mixed_cycle(1234567), 22)
        blk = lambda b, i: b[8 * i:8 * i + 8]  # noqa: E731
        for i in (20, 21, 23, 24, 25, 26, 27):
            self.assertEqual(blk(out, i), blk(plain, i), i)
        self.assertEqual(blk(out, 22), dpt.transform_block(blk(plain, 22)))
        self.assertEqual(blk(out, 28), dpt.unshuffle_block(blk(plain, 28)))
        self.assertEqual(blk(out, 44), dpt.transform_block(blk(plain, 44)))
        # j=14 is the next shuffle: non-DES 29..35 -> j 8..14, so block 35.
        self.assertEqual(blk(out, 35), dpt.unshuffle_block(blk(plain, 35)))
        self.assertEqual(blk(out, 34), blk(plain, 34))

    def test_partial_tail_preserved_and_mixed_wins(self):
        plain = bytes((i * 31 + 7) & 0xFF for i in range(8 * 40 + 5))
        for kind in (3, 5, 7):
            out = dpt.decrypt(plain, kind, 100)
            self.assertEqual(out[-5:], plain[-5:])
            self.assertEqual(len(out), len(plain))
        self.assertEqual(dpt.decrypt(plain, 7, 100), dpt.decrypt(plain, 3, 100))
        self.assertNotEqual(dpt.decrypt(plain, 7, 100), dpt.decrypt(plain, 5, 100))
        header = dpt.decrypt(plain, 5, 100)
        self.assertEqual(header[160:], plain[160:])
        self.assertEqual(dpt.decrypt(plain, 1, 100), plain)  # no filename nibble codec

    def test_test_encryptor_inverts_decoder(self):
        rnd = random.Random(5)
        plain = bytes(rnd.randrange(256) for _ in range(8 * 300 + 3))
        for kind, size in ((3, 50), (3, 5000), (3, 50000), (5, 50000), (7, 2000000)):
            self.assertEqual(dpt.decrypt(encrypt(plain, kind, size), kind, size), plain)


class FramingTests(unittest.TestCase):
    def setUp(self):
        self.body = b"GRAT\x01\x02" + bytes(range(256)) * 40
        self.z = zlib.compress(self.body, 9)

    def test_stored_and_zlib_positive_with_arbitrary_padding(self):
        framing, out = dpt.frame(self.body + b"\xff\x01\x99", len(self.body), len(self.body))
        self.assertEqual((framing, out), ("stored", self.body))
        framing, out = dpt.frame(self.z + b"\xde\xad\xbe\xef\x07", len(self.z), len(self.body))
        self.assertEqual((framing, out), ("zlib", self.body))

    def refuse(self, data, compressed, real, code):
        with self.assertRaises(dpt.Refusal) as cm:
            dpt.frame(data, compressed, real)
        self.assertEqual(cm.exception.code, code)

    def test_strict_refusals(self):
        n, z = len(self.body), self.z
        self.refuse(z, len(z), n - 1, "zlib-overlong")      # capped at real+1
        self.refuse(z, len(z), n + 5, "zlib-short")
        self.refuse(z, len(z) - 3, n, "zlib-truncated")
        bad = bytearray(z)
        bad[-1] ^= 1
        self.refuse(bytes(bad), len(z), n, "zlib-invalid-stream")  # adler32
        self.refuse(z + b"\x00", len(z) + 1, n, "zlib-trailing-data")
        two = z + zlib.compress(b"x")
        self.refuse(two, len(two), n, "zlib-trailing-data")  # concatenated stream
        self.refuse(b"\x00" * 16, 16, 100, "zlib-invalid-stream")

    def test_padding_is_not_fed_to_the_stream(self):
        # Garbage in padding beyond compressed_size must not matter.
        self.assertEqual(dpt.frame(self.z + zlib.compress(b"y"), len(self.z), len(self.body))[1],
                         self.body)


# ---------------------------------------------------------------------------
# Synthetic world.

SOURCE_RELS = [p["path"] for p in PROFILE["source_pins"]]
LABELS = ("gat", "gnd", "rsw")


# Seventeen synthetic remaining-route bodies; compressed sizes span 2-5 decimal digits.
REMAINING_SIZES = [3000, 900, 20000, 5000, 300, 150000, 1200, 50, 9000, 64000, 700, 400,
                   2500, 12000, 30000, 800, 6000]


class Fixture:
    """A temporary repo copy, source root, synthetic patch and synthetic contract."""

    def __init__(self, base, stored_index=None, header_version=0x102, route=dpt.LEGACY_ROUTE,
                 mangle=None, sizes=None):
        self.base = Path(base)
        self.route = route
        chapter = route is not dpt.LEGACY_ROUTE
        rnd = random.Random(1234)
        self.repo = self.base / "repo"
        (self.repo / "tools/renewal").mkdir(parents=True)
        (self.repo / "docs/project/fixtures").mkdir(parents=True)
        shutil.copyfile(dpt.REPO / dpt.GENERATOR_PATH, self.repo / dpt.GENERATOR_PATH)
        self.source_root = self.base / "src"
        pins = []
        for i, rel in enumerate(SOURCE_RELS):
            p = self.source_root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            data = ("synthetic source %d\n" % i).encode() * (i + 1)
            p.write_bytes(data)
            pins.append({"bytes": len(data), "path": rel, "sha256": sha(data)})
        vectors = json.loads(json.dumps(VECTORS))
        vectors["primary_sources"] = pins[:2]
        self.vectors_bytes = json.dumps(vectors, indent=2).encode()
        (self.repo / dpt.VECTORS_PATH).write_bytes(self.vectors_bytes)
        vpin = {"bytes": len(self.vectors_bytes), "sha256": sha(self.vectors_bytes)}

        # Body sizes chosen so mixed compressed sizes cross cycle digit boundaries.
        if sizes is None:
            sizes = ([150000] if route is dpt.CHAPTER1_RSW_ROUTE else REMAINING_SIZES if chapter else
                     [3000, 900, 20000, 5000, 300, 140000, 1200, 50, 9000, 64000, 700, 400])
        # The chapter body is more compressible so it fits the fixed 64 KiB aligned cap.
        noisy = 4 if chapter else 2
        body = bytearray()
        offset = dpt.HEADER_SIZE
        targets = []
        self.bodies = []
        for i, size in enumerate(sizes):
            label = "rsw" if chapter else LABELS[i % 3]
            kind = 3 if label == "rsw" or i in (1, 7) else 5
            if i == 10:
                kind = 7
            payload = dpt.MAGIC[label] + bytes((2, i)) + bytes(
                rnd.randrange(256) if (j // 64) % noisy == 1 else j & 7 for j in range(size))
            if i == stored_index:
                comp = payload
            else:
                comp = zlib.compress(payload, 6)
            real = len(payload)
            if mangle is not None:
                comp, real = mangle(comp, payload)
            aligned = (len(comp) + 7) // 8 * 8 + (8 if i % 4 == 0 else 0)
            pad = bytes(rnd.randrange(1, 256) for _ in range(aligned - len(comp)))
            raw = encrypt(comp + pad, kind, len(comp))
            targets.append({
                "compressed_size": len(comp), "effective_kind": kind,
                "expected_magic_hex": dpt.MAGIC[label].hex(), "kind_label": label,
                "length_aligned": aligned, "metadata_filter": "eligible",
                "name_hex": ("data\\synthetic%02d.%s" % (i, label)).encode().hex(),
                "ordinal": (23 if route is dpt.CHAPTER1_RSW_ROUTE else 10 + i),
                "output_file": route.body_names[i],
                "payload_offset_field": offset - dpt.HEADER_SIZE,
                "physical_body_range": [offset, offset + aligned], "real_size": real})
            self.bodies.append(payload)
            body += raw
            gap = 0 if i % 2 else 16
            body += bytes(rnd.randrange(256) for _ in range(gap))
            offset += aligned + gap
        table_start = offset
        record_count = 40
        seed = 77
        header = (b"Master of Magic" + b"\x01" * 15 + (table_start - 46).to_bytes(4, "little")
                  + seed.to_bytes(4, "little") + (record_count + seed + 7).to_bytes(4, "little")
                  + header_version.to_bytes(4, "little"))
        self.patch_bytes = header + bytes(body) + b"TABLE" * 50
        self.patch = self.base / "inputs" / "synthetic.gpf"
        self.patch.parent.mkdir()
        self.patch.write_bytes(self.patch_bytes)
        self.header_version = header_version
        aligned_total = sum(t["length_aligned"] for t in targets)
        decoded_total = sum(t["real_size"] for t in targets)
        limits = (dict(route.limit_caps) if chapter else
                  {"max_aligned_bytes_per_target": 1 << 20, "max_decoded_bytes_per_target": 1 << 20,
                   "max_decoded_bytes_total": 1 << 22, "max_output_bytes": 1 << 22,
                   "read_chunk_bytes": 4096})
        limits.update(expected_aligned_bytes_total=aligned_total,
                      expected_decoded_bytes_total=decoded_total)
        self.profile = {
            "authored": {"bytes": vpin["bytes"], "path": dpt.VECTORS_PATH, "sha256": vpin["sha256"]},
            "not_claimed": ["synthetic"],
            "patch": {"bytes": len(self.patch_bytes), "file": "synthetic.gpf", "header_bytes": 46,
                      "header_sha256": sha(header), "index": 1, "record_count": record_count,
                      "sha256": sha(self.patch_bytes), "table_start": table_start},
            "schema": route.profile_schema, "source_pins": pins,
            "source_revision": dpt.SOURCE_REVISION, "strict_policy": dict(PROFILE["strict_policy"]),
            "targets": targets, "task": route.task, "work_limits": limits,
        }
        self.vpin = vpin
        self.write_profile()
        self.out_parent = self.base / "out"
        self.out_parent.mkdir(mode=0o700)
        self.out = self.out_parent / "run"

    def write_profile(self):
        self.profile_bytes = json.dumps(self.profile, indent=2, sort_keys=True).encode()
        (self.repo / self.route.profile_path).write_bytes(self.profile_bytes)

    def contract(self):
        p = self.profile["patch"]
        return dpt.Contract("synthetic-test", self.repo, self.profile_bytes, self.vectors_bytes,
                            {"bytes": len(self.profile_bytes), "sha256": sha(self.profile_bytes)},
                            self.vpin, {"index": p["index"], "bytes": p["bytes"],
                                        "sha256": p["sha256"]}, dpt.SOURCE_REVISION, self.header_version,
                            route=self.route)

    def run(self, **kw):
        return dpt._run(self.source_root, self.patch, self.out, self.contract(), **kw)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.chmod(self.tmp.name, 0o700)
        self.fx = Fixture(self.tmp.name)

    def tearDown(self):
        for root, dirs, _ in os.walk(self.tmp.name):
            for d in dirs:
                p = os.path.join(root, d)
                if not os.path.islink(p):
                    os.chmod(p, 0o700)
        self.tmp.cleanup()

    def refuse(self, code, fn, *args, **kw):
        with self.assertRaises(dpt.Refusal) as cm:
            fn(*args, **kw)
        self.assertEqual(cm.exception.code, code)

    def names(self, path=None):
        return sorted(os.listdir(path or self.fx.out))


class EndToEndTests(Base):
    def test_synthetic_publication_and_consumer(self):
        manifest_sha, total = self.fx.run()
        self.assertEqual(total, sum(len(b) for b in self.fx.bodies))
        self.assertEqual(self.names(), sorted(dpt.BODY_NAMES + (dpt.MANIFEST, dpt.COMPLETE)))
        self.assertEqual(stat.S_IMODE(os.lstat(self.fx.out).st_mode), 0o700)
        for i, body in enumerate(self.fx.bodies):
            p = self.fx.out / dpt.BODY_NAMES[i]
            self.assertEqual(p.read_bytes(), body)
            st = os.lstat(p)
            self.assertEqual((stat.S_IMODE(st.st_mode), st.st_nlink), (0o600, 1))
        result = dpt._verify_payloads(self.fx.out, self.fx.contract())
        self.assertEqual(result["manifest_sha256"], manifest_sha)
        manifest = json.loads((self.fx.out / dpt.MANIFEST).read_bytes())
        rows = manifest["targets"]
        self.assertEqual({r["encryption"] for r in rows}, {"mixed", "header"})
        self.assertEqual(sorted({r["cycle"] for r in rows if r["cycle"]}), [1, 4, 5, 14])
        self.assertTrue(any(r["padding_bytes"] > 7 for r in rows))
        self.assertEqual(manifest["contract_kind"], "synthetic-test")
        self.assertEqual(manifest["patch"]["header_version_hex"], "00000102")
        # The public consumer has no synthetic bypass.
        self.refuse("consumer-contract", dpt.verify_payloads, self.fx.out)

    def test_stored_target(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        fx = Fixture(tmp.name, stored_index=4, header_version=0x200)
        fx.run()
        rows = json.loads((fx.out / dpt.MANIFEST).read_bytes())["targets"]
        self.assertEqual(rows[4]["framing"], "stored")
        self.assertEqual((fx.out / "target-004.body").read_bytes(), fx.bodies[4])

    def test_no_output_on_stdout_paths(self):
        out = tempfile.TemporaryFile("w+")
        err = tempfile.TemporaryFile("w+")
        self.addCleanup(out.close)
        self.addCleanup(err.close)
        with mock.patch.object(sys, "stdout", out), mock.patch.object(sys, "stderr", err):
            code = dpt.main([str(self.fx.source_root), str(self.fx.patch), str(self.fx.out)])
            usage = dpt.main(["only-one"])
        out.seek(0)
        err.seek(0)
        text = out.read() + err.read()
        self.assertEqual((code, usage), (2, 64))
        self.assertNotIn(self.tmp.name, text)
        # Production pins refuse the synthetic patch before any output exists.
        self.assertIn('"reason": "source-pin"', text)
        self.assertFalse(os.path.lexists(self.fx.out))


class ProfileTests(Base):
    def mutate(self, code, fn):
        prof = json.loads(json.dumps(self.fx.profile))
        fn(prof)
        self.refuse(code, dpt.validate_profile, prof, self.fx.vpin)

    def test_production_contract_and_pins(self):
        c = dpt._production_contract()
        self.assertEqual(c.profile["patch"]["sha256"], dpt.PATCH_PIN["sha256"])
        self.assertEqual(c.vector_count, 252)
        prof = (dpt.REPO / dpt.PROFILE_PATH).read_bytes()
        vec = (dpt.REPO / dpt.VECTORS_PATH).read_bytes()
        self.refuse("profile-pin", dpt.Contract, "production", dpt.REPO, prof + b" ", vec,
                    dpt.PROFILE_PIN, dpt.VECTORS_PIN, dpt.PATCH_PIN, dpt.SOURCE_REVISION, 0x102)
        self.refuse("profile-pin-cross-check", dpt.Contract, "production", dpt.REPO, prof, vec,
                    dpt.PROFILE_PIN, dpt.VECTORS_PIN, dict(dpt.PATCH_PIN, index=9297),
                    dpt.SOURCE_REVISION, 0x102)

    def test_malformed_profiles(self):
        def t(i, **kw):
            return lambda p: p["targets"][i].update(kw)
        self.mutate("profile-keys", lambda p: p.update(extra=1))
        self.mutate("profile-target-fields", t(0, compressed_size=True))
        self.mutate("profile-target-fields", t(3, output_file="../x"))
        self.mutate("profile-target-sizes", lambda p: p["targets"][0].update(
            compressed_size=p["targets"][0]["length_aligned"] + 1))
        self.mutate("profile-target-range", lambda p: p["targets"][2].update(
            physical_body_range=[1, 2]))
        self.mutate("profile-target-kind", t(1, effective_kind=4))
        self.mutate("profile-target-kind", t(1, effective_kind=0x13))
        self.mutate("profile-target-magic", t(0, expected_magic_hex="47524e47"))
        self.mutate("profile-target-name", t(0, name_hex=b"x.rsw".hex()))
        self.mutate("profile-target-budget", t(5, length_aligned=1 << 21, compressed_size=1))
        self.mutate("profile-totals", lambda p: p["work_limits"].update(
            expected_decoded_bytes_total=p["work_limits"]["expected_decoded_bytes_total"] + 1))
        self.mutate("profile-target-ordinal", t(1, ordinal=10))
        self.mutate("profile-sources", lambda p: p["source_pins"][0].update(path="/abs"))
        self.mutate("profile-sources", lambda p: p["source_pins"][0].update(path="a/../b"))
        self.mutate("profile-targets", lambda p: p["targets"].pop())
        self.mutate("profile-limits", lambda p: p["work_limits"].update(max_output_bytes=0))

        def overlap(p):
            a = p["targets"][1]
            a["payload_offset_field"] -= 24  # 16-byte gap after target 0, then 8 inside it
            a["physical_body_range"] = [a["payload_offset_field"] + 46,
                                        a["payload_offset_field"] + 46 + a["length_aligned"]]
        self.mutate("profile-target-range", overlap)

        def past_table(p):
            p["patch"]["table_start"] = p["targets"][-1]["physical_body_range"][1] - 1
        self.mutate("profile-target-range", past_table)

    def test_duplicate_json_keys(self):
        self.refuse("json-duplicate-key", dpt._parse_json, b'{"a": 1, "a": 2}', "x")
        self.refuse("x", dpt._parse_json, b'{"a": NaN}', "x")


class InputTests(Base):
    def test_patch_symlink_hardlink_special_and_pins(self):
        real = self.fx.patch
        link = real.with_name("link.gpf")
        os.symlink(real, link)
        self.fx.patch = link
        self.refuse("patch-unopenable", self.fx.run)
        os.unlink(link)
        os.link(real, link)
        self.fx.patch = real
        self.refuse("patch-hardlinked", self.fx.run)
        os.unlink(link)
        fifo = real.with_name("fifo.gpf")
        os.mkfifo(fifo)
        self.fx.patch = fifo
        self.refuse("patch-not-regular", self.fx.run)
        self.fx.patch = real
        real.write_bytes(self.fx.patch_bytes + b"x")
        self.refuse("patch-size", self.fx.run)
        bad = bytearray(self.fx.patch_bytes)
        bad[-1] ^= 1
        real.write_bytes(bytes(bad))
        self.refuse("patch-sha256", self.fx.run)
        self.assertFalse(os.path.lexists(self.fx.out))  # no output before body reads

    def test_header_pin_and_fields(self):
        self.fx.profile["patch"]["header_sha256"] = "0" * 64
        self.fx.write_profile()
        self.refuse("patch-header-pin", self.fx.run)
        self.fx.profile["patch"]["header_sha256"] = sha(self.fx.patch_bytes[:46])
        self.fx.profile["patch"]["record_count"] = 41
        self.fx.write_profile()
        self.refuse("patch-header-fields", self.fx.run)
        self.assertFalse(os.path.lexists(self.fx.out))

    def test_source_checks(self):
        rel = SOURCE_RELS[2]
        p = self.fx.source_root / rel
        data = p.read_bytes()
        p.write_bytes(data[:-1] + b"?")
        self.refuse("source-pin", self.fx.run)
        p.unlink()
        self.refuse("source-unreadable", self.fx.run)
        alt = self.fx.base / "alt"
        alt.write_bytes(data)
        os.symlink(alt, p)
        self.refuse("source-unreadable", self.fx.run)
        p.unlink()
        # A symlinked intermediate directory is not followed either.
        d = (self.fx.source_root / rel).parent
        moved = self.fx.base / "moved"
        os.rename(d, moved)
        os.symlink(moved, d)
        p_target = moved / Path(rel).name
        p_target.write_bytes(data)
        self.refuse("source-unreadable", self.fx.run)
        self.assertFalse(os.path.lexists(self.fx.out))

    def test_patch_drift_after_hash(self):
        orig = dpt.Patch.read

        def drifting(patch, offset, length):
            data = orig(patch, offset, length)
            return data[:-1] + bytes((data[-1] ^ 1,))
        with mock.patch.object(dpt.Patch, "read", drifting):
            self.refuse("patch-range-drift", self.fx.run)
        self.assertIn(dpt.FAILED, self.names())
        self.assertNotIn(dpt.COMPLETE, self.names())

    def test_patch_identity_drift_before_completion(self):
        # A metadata change after hashing is caught by the recheck before completion.
        def fsync(ops, fd):
            os.utime(self.fx.patch, ns=(1, 1))
            os.fsync(fd)
        with mock.patch.object(dpt.FileOps, "fsync", fsync):
            self.refuse("patch-drift", self.fx.run)
        self.assertNotIn(dpt.COMPLETE, self.names())
        self.assertIn(dpt.FAILED, self.names())

    def test_fresh_output_required(self):
        self.fx.out.mkdir()
        self.refuse("output-exists", self.fx.run)
        self.assertEqual(self.names(), [])
        self.fx.out = self.fx.base / "missing" / "run"
        self.refuse("output-parent", self.fx.run)

    def test_bad_vectors_refused_before_output(self):
        bad = json.loads(self.fx.vectors_bytes)
        bad["fixed_block_vectors"][0]["output_hex"] = "00" * 8
        self.fx.vectors_bytes = json.dumps(bad).encode()
        self.fx.vpin = {"bytes": len(self.fx.vectors_bytes), "sha256": sha(self.fx.vectors_bytes)}
        self.fx.profile["authored"].update(self.fx.vpin)
        self.fx.write_profile()
        self.refuse("vector-block-mismatch", self.fx.contract)

    def test_bad_decoded_magic(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        fx = Fixture(tmp.name)
        fx.profile["targets"][0]["kind_label"] = "gnd"
        fx.profile["targets"][0]["expected_magic_hex"] = dpt.MAGIC["gnd"].hex()
        fx.profile["targets"][0]["name_hex"] = b"x.gnd".hex()
        fx.write_profile()
        self.refuse("decoded-magic", fx.run)
        self.assertEqual(sorted(os.listdir(fx.out)), [dpt.FAILED])


class FaultOps(dpt.FileOps):
    def __init__(self, mode, at=3):
        self.mode, self.at, self.n = mode, at, 0

    def write(self, fd, data):
        self.n += 1
        if self.n == self.at:
            if self.mode == "zero":
                return 0
            if self.mode == "over":
                return len(data) + 1
            if self.mode == "raise":
                raise OSError(5, "io")
        if self.mode == "short":
            return os.write(fd, bytes(data[:max(1, len(data) // 3)]))
        return os.write(fd, data)

    def fsync(self, fd):
        if self.mode == "fsync" and self.n >= self.at:
            raise OSError(5, "io")
        os.fsync(fd)

    def close(self, fd):
        os.close(fd)
        if self.mode == "close" and self.n >= self.at:
            raise OSError(5, "io")

    def read_back(self, dir_fd, name):
        st, data = super().read_back(dir_fd, name)
        if self.mode == "readback" and name == "target-002.body":
            data = data[:-1] + b"\0"
        return st, data


class PublicationTests(Base):
    def check_failed(self, code):
        names = self.names()
        self.assertIn(dpt.FAILED, names)
        self.assertNotIn(dpt.COMPLETE, names)
        marker = json.loads((self.fx.out / dpt.FAILED).read_bytes())
        self.assertEqual(marker, {"reason": code, "schema": dpt.FAILED_SCHEMA, "status": "failed"})
        self.refuse("consumer-failed-marker", dpt._verify_payloads, self.fx.out, self.fx.contract())

    def fresh(self):
        shutil.rmtree(self.fx.out)

    def test_write_faults(self):
        for mode, code in (("zero", "output-write"), ("over", "output-write"),
                           ("raise", "output-flush"), ("fsync", "output-flush"),
                           ("close", "output-close"), ("readback", "output-readback")):
            with self.subTest(mode=mode):
                self.refuse(code, self.fx.run, ops=FaultOps(mode))
                self.check_failed(code)
                self.assertIn("target-000.body", self.names())  # partials preserved
                self.fresh()

    def test_short_positive_writes_complete(self):
        self.fx.run(ops=FaultOps("short"))
        dpt._verify_payloads(self.fx.out, self.fx.contract())

    def test_final_foreign_directory_replacement(self):
        moved = self.fx.out_parent / "moved"

        def swap(path):
            os.rename(path, moved)
            os.mkdir(path, 0o700)
        self.refuse("output-foreign", self.fx.run, consumer=swap)
        self.assertEqual(self.names(), [])  # nothing written into the foreign directory
        self.assertNotIn(dpt.COMPLETE, self.names(moved))  # retained owned FD revokes its marker
        self.assertIn(dpt.FAILED, self.names(moved))

    def test_identical_marker_replacement_is_not_success(self):
        def replace(path):
            p = Path(path) / dpt.COMPLETE
            data = p.read_bytes()
            p.unlink()
            fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.write(fd, data)
            os.close(fd)
            self.replaced = (data, os.lstat(p).st_ino)
        self.refuse("output-identity", self.fx.run, consumer=replace)
        p = self.fx.out / dpt.COMPLETE
        self.assertEqual((p.read_bytes(), os.lstat(p).st_ino), self.replaced)  # foreign kept
        self.assertIn(dpt.FAILED, self.names())
        self.refuse("consumer-failed-marker", dpt._verify_payloads, self.fx.out, self.fx.contract())

    def test_owned_completion_invalidated_on_late_refusal(self):
        def boom(path):
            raise dpt.Refusal("consumer-body")
        self.refuse("consumer-body", self.fx.run, consumer=boom)
        self.check_failed("consumer-body")

    def test_failure_marker_precedence_over_existing_completion(self):
        self.fx.run()
        fd = os.open(self.fx.out / dpt.FAILED, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        self.refuse("consumer-failed-marker", dpt._verify_payloads, self.fx.out, self.fx.contract())

    def test_unexpected_error_is_refusal_not_success(self):
        with mock.patch.object(dpt, "build_manifest", side_effect=RuntimeError("x")):
            self.refuse("internal-error", self.fx.run)
        self.check_failed("internal-error")


class ConsumerTests(Base):
    def setUp(self):
        super().setUp()
        self.fx.run()
        self.contract = self.fx.contract()

    def verify(self):
        return dpt._verify_payloads(self.fx.out, self.contract)

    def rewrite(self, name, data):
        p = self.fx.out / name
        os.chmod(p, 0o600)
        p.write_bytes(data)

    def rebind(self, manifest):
        data = dpt.canonical(manifest)
        self.rewrite(dpt.MANIFEST, data)
        self.rewrite(dpt.COMPLETE, dpt.canonical({
            "manifest_bytes": len(data), "manifest_sha256": sha(data),
            "schema": dpt.COMPLETE_SCHEMA, "status": "complete", "target_count": 12}))

    def manifest(self):
        return json.loads((self.fx.out / dpt.MANIFEST).read_bytes())

    def test_positive(self):
        self.assertEqual(self.verify()["targets"], 12)

    def test_body_mutation(self):
        p = self.fx.out / "target-005.body"
        data = bytearray(p.read_bytes())
        data[100] ^= 1
        self.rewrite("target-005.body", bytes(data))
        self.refuse("consumer-body", self.verify)

    def test_privacy_and_file_set(self):
        os.chmod(self.fx.out / "target-001.body", 0o644)
        self.refuse("consumer-file-privacy", self.verify)
        os.chmod(self.fx.out / "target-001.body", 0o600)
        os.link(self.fx.out / "target-001.body", self.fx.out_parent / "hl")
        self.refuse("consumer-file-privacy", self.verify)
        os.unlink(self.fx.out_parent / "hl")
        (self.fx.out / "extra").write_bytes(b"")
        self.refuse("consumer-file-set", self.verify)
        os.unlink(self.fx.out / "extra")
        os.chmod(self.fx.out, 0o755)
        self.refuse("consumer-output-privacy", self.verify)
        os.chmod(self.fx.out, 0o700)
        self.verify()

    def test_marker_alone_is_not_success(self):
        for name in dpt.BODY_NAMES + (dpt.MANIFEST,):
            os.unlink(self.fx.out / name)
        self.refuse("consumer-file-set", self.verify)

    def test_hash_rebinding_cannot_bless_changed_contract(self):
        cases = [
            ("consumer-contract", lambda m: m["work_limits"].update(max_output_bytes=1 << 30)),
            ("consumer-contract", lambda m: m["strict_policy"].update(zlib="uncapped")),
            ("consumer-contract", lambda m: m["profile"].update(sha256="0" * 64)),
            ("consumer-contract", lambda m: m["generator"].update(sha256="0" * 64)),
            ("consumer-contract", lambda m: m["sources"][0].update(bytes=1)),
            ("consumer-contract", lambda m: m.update(contract_kind="production")),
            ("consumer-row-contract", lambda m: m["targets"][3].update(real_size=1)),
            ("consumer-row-contract", lambda m: m["targets"][3].update(ordinal=99)),
            ("consumer-row-derived", lambda m: m["targets"][3].update(framing="stored")),
            ("consumer-row-derived", lambda m: m["targets"][3].update(cycle=4)),
            ("consumer-row-hash", lambda m: m["targets"][3].update(raw_range_sha256="x")),
            ("consumer-row-keys", lambda m: m["targets"][3].pop("padding_bytes")),
            ("consumer-targets", lambda m: m["targets"].pop()),
            ("consumer-usage", lambda m: m["usage"].update(decoded_bytes=1)),
            ("consumer-manifest-keys", lambda m: m.update(bonus=True)),
        ]
        original = self.manifest()
        for code, fn in cases:
            with self.subTest(code=code):
                m = json.loads(json.dumps(original))
                fn(m)
                self.rebind(m)
                self.refuse(code, self.verify)
        self.rebind(original)
        self.verify()

    def test_unrebound_manifest_change_and_noncanonical(self):
        data = (self.fx.out / dpt.MANIFEST).read_bytes()
        self.rewrite(dpt.MANIFEST, data.replace(b"\n", b"\r\n", 1))
        self.refuse("consumer-marker", self.verify)


class RootCorrectionTests(Base):
    """Root-authored finite real-file controls; no production asset qualification."""

    def test_final_directory_close_error_revokes_owned_completion(self):
        original = dpt.Output.close
        hits = []
        def close_then_error(output):
            had_fd = output.dir_fd is not None
            original(output)
            if had_fd and not hits:
                hits.append(True)
                raise OSError("injected after actual final directory close")
        with mock.patch.object(dpt.Output, "close", close_then_error):
            self.refuse("output-close", self.fx.run)
        self.assertEqual(hits, [True])
        self.assertFalse((self.fx.out / dpt.COMPLETE).exists())
        self.assertTrue((self.fx.out / dpt.FAILED).is_file())
        self.refuse("consumer-failed-marker", dpt._verify_payloads,
                    self.fx.out, self.fx.contract())

    def test_readback_refuses_growth_before_allocation(self):
        self.fx.run()
        p = self.fx.out / dpt.BODY_NAMES[0]
        with p.open("r+b") as f:
            f.truncate(dpt.MAX_CHECKOUT_BYTES + 1)
        directory = os.open(self.fx.out, os.O_RDONLY | os.O_DIRECTORY)
        try:
            with mock.patch.object(dpt, "_read_all", side_effect=AssertionError("unbounded allocation")):
                self.refuse("output-readback", dpt.FileOps().read_back,
                            directory, dpt.BODY_NAMES[0])
        finally:
            os.close(directory)

    def manifest(self):
        return json.loads((self.fx.out / dpt.MANIFEST).read_bytes())

    def rebind(self, manifest):
        data = dpt.canonical(manifest)
        (self.fx.out / dpt.MANIFEST).write_bytes(data)
        (self.fx.out / dpt.COMPLETE).write_bytes(dpt.canonical({
            "manifest_bytes": len(data), "manifest_sha256": sha(data),
            "schema": dpt.COMPLETE_SCHEMA, "status": "complete", "target_count": 12}))

    def test_fixed_source_float_rebound_refused(self):
        self.fx.run()
        m = self.manifest()
        m["sources"][0]["bytes"] = float(m["sources"][0]["bytes"])
        self.rebind(m)
        self.refuse("consumer-contract", dpt._verify_payloads, self.fx.out, self.fx.contract())

    def test_fixed_source_bool_rebound_refused(self):
        pin = self.fx.profile["source_pins"][0]
        (self.fx.source_root / pin["path"]).write_bytes(b"x")
        pin.update(bytes=1, sha256=sha(b"x"))
        vectors = json.loads(self.fx.vectors_bytes)
        vectors["primary_sources"] = self.fx.profile["source_pins"][:2]
        self.fx.vectors_bytes = json.dumps(vectors).encode()
        (self.fx.repo / dpt.VECTORS_PATH).write_bytes(self.fx.vectors_bytes)
        self.fx.vpin = {"bytes": len(self.fx.vectors_bytes), "sha256": sha(self.fx.vectors_bytes)}
        self.fx.profile["authored"].update(self.fx.vpin)
        self.fx.write_profile()
        self.fx.run()  # one-byte source is a valid private baseline
        m = self.manifest()
        m["sources"][0]["bytes"] = True
        self.rebind(m)
        self.refuse("consumer-contract", dpt._verify_payloads, self.fx.out, self.fx.contract())

    def test_deep_target_usage_marker_types(self):
        self.fx.run()
        original = self.manifest()
        for section in ("range", "usage", "limit"):
            with self.subTest(section=section):
                m = json.loads(json.dumps(original))
                if section == "range":
                    m["targets"][0]["physical_body_range"][0] = float(m["targets"][0]["physical_body_range"][0])
                elif section == "usage":
                    m["usage"]["target_count"] = 12.0
                else:
                    m["work_limits"]["max_output_bytes"] = float(m["work_limits"]["max_output_bytes"])
                self.rebind(m)
                with self.assertRaises(dpt.Refusal):
                    dpt._verify_payloads(self.fx.out, self.fx.contract())
        self.rebind(original)
        marker = json.loads((self.fx.out / dpt.COMPLETE).read_bytes())
        marker["target_count"] = 12.0
        (self.fx.out / dpt.COMPLETE).write_bytes(dpt.canonical(marker))
        self.refuse("consumer-marker", dpt._verify_payloads, self.fx.out, self.fx.contract())

    def test_consumer_final_directory_swap(self):
        self.fx.run()
        foreign = self.fx.base / "foreign"
        shutil.copytree(self.fx.out, foreign)
        foreign_id = (foreign.stat().st_dev, foreign.stat().st_ino)
        foreign_bytes = {p.name: p.read_bytes() for p in foreign.iterdir()}
        retained = self.fx.base / "retained"
        original = dpt._consumer_read
        hits = []
        def read(fd, name, **kw):
            data = original(fd, name, **kw)
            if name == dpt.BODY_NAMES[-1] and not hits:
                self.fx.out.rename(retained)
                foreign.rename(self.fx.out)
                hits.append(name)
            return data
        with mock.patch.object(dpt, "_consumer_read", read), self.assertRaises(dpt.Refusal):
            dpt._verify_payloads(self.fx.out, self.fx.contract())
        self.assertEqual(len(hits), 1)
        self.assertEqual((self.fx.out.stat().st_dev, self.fx.out.stat().st_ino), foreign_id)
        self.assertEqual({p.name: p.read_bytes() for p in self.fx.out.iterdir()}, foreign_bytes)
        self.assertTrue((retained / dpt.COMPLETE).exists())  # read-only consumer never deletes

    def test_consumer_identical_foreign_marker(self):
        self.fx.run()
        original = dpt._consumer_read
        saved = self.fx.base / "old-marker"
        hits = []
        def read(fd, name, **kw):
            data = original(fd, name, **kw)
            if name == dpt.COMPLETE and not hits:
                p = self.fx.out / name
                p.rename(saved)  # keep original inode live, preventing inode reuse
                with p.open("xb") as f:
                    f.write(data)
                os.chmod(p, 0o600)
                hits.append((p.stat().st_dev, p.stat().st_ino, data))
                self.assertNotEqual(hits[0][:2], (saved.stat().st_dev, saved.stat().st_ino))
            return data
        with mock.patch.object(dpt, "_consumer_read", read), self.assertRaises(dpt.Refusal):
            dpt._verify_payloads(self.fx.out, self.fx.contract())
        p = self.fx.out / dpt.COMPLETE
        self.assertEqual((p.stat().st_dev, p.stat().st_ino, p.read_bytes()), hits[0])

    def test_consumer_already_read_body_mutation(self):
        self.fx.run()
        original = dpt._consumer_read
        hits = []
        def read(fd, name, **kw):
            data = original(fd, name, **kw)
            if name == dpt.BODY_NAMES[0] and not hits:
                p = self.fx.out / name
                before = p.stat()
                changed = data[:-1] + bytes((data[-1] ^ 1,))
                p.write_bytes(changed)
                self.assertEqual((p.stat().st_dev, p.stat().st_ino), (before.st_dev, before.st_ino))
                hits.append(name)
            return data
        with mock.patch.object(dpt, "_consumer_read", read), self.assertRaises(dpt.Refusal):
            dpt._verify_payloads(self.fx.out, self.fx.contract())
        self.assertEqual(len(hits), 1)

    def test_producer_after_consumer_rechecks_all_bindings(self):
        for target in ("source", "generator", "profile", "vectors", "body"):
            with self.subTest(target=target):
                with tempfile.TemporaryDirectory() as tmp:
                    fx = Fixture(tmp)
                    contract = fx.contract()
                    hits = []
                    def consumer(path):
                        self.assertEqual(dpt._verify_payloads(path, contract)["targets"], 12)
                        p = (fx.source_root / fx.profile["source_pins"][0]["path"] if target == "source"
                             else fx.out / dpt.BODY_NAMES[0] if target == "body"
                             else fx.repo / {"generator": dpt.GENERATOR_PATH,
                                             "profile": dpt.PROFILE_PATH,
                                             "vectors": dpt.VECTORS_PATH}[target])
                        data = p.read_bytes()
                        before = p.stat()
                        p.write_bytes(data[:-1] + bytes((data[-1] ^ 1,)))
                        self.assertEqual((p.stat().st_dev, p.stat().st_ino), (before.st_dev, before.st_ino))
                        hits.append(target)
                    with self.assertRaises(dpt.Refusal):
                        dpt._run(fx.source_root, fx.patch, fx.out, contract, consumer=consumer)
                    self.assertEqual(hits, [target])
                    self.assertFalse((fx.out / dpt.COMPLETE).exists())
                    self.assertTrue((fx.out / dpt.FAILED).is_file())

    def test_patch_constructor_refusals_close_exact_owned_fd(self):
        for target in ("size", "hardlink", "hash"):
            with self.subTest(target=target):
                p = self.fx.base / (target + ".gpf")
                p.write_bytes(b"x")
                if target == "hardlink":
                    os.link(p, self.fx.base / "retained-link")
                pin = {"bytes": 2 if target == "size" else 1, "sha256": "0" * 64}
                real_open, real_close = os.open, os.close
                opened = []
                def track(path, flags, *args, **kwargs):
                    fd = real_open(path, flags, *args, **kwargs)
                    if os.fspath(path) == str(p):
                        st = os.fstat(fd)
                        opened.append((fd, st.st_dev, st.st_ino))
                    return fd
                leaked = []
                try:
                    with mock.patch.object(dpt.os, "open", track), self.assertRaises(dpt.Refusal):
                        dpt.Patch(p, pin, [], 64)
                    self.assertEqual(len(opened), 1)
                    for fd, dev, ino in opened:
                        try:
                            st = os.fstat(fd)
                            if (st.st_dev, st.st_ino) == (dev, ino):
                                leaked.append(fd)
                        except OSError as exc:
                            self.assertEqual(exc.errno, errno.EBADF)
                    self.assertEqual(leaked, [], "owned FD still live before fixture cleanup")
                finally:
                    # Observe first, then close only the exact fixture-owned identity if leaked.
                    for fd, dev, ino in opened:
                        try:
                            st = os.fstat(fd)
                        except OSError:
                            continue
                        if (st.st_dev, st.st_ino) == (dev, ino):
                            real_close(fd)

    def test_bounded_consumer_reads_before_body_allocation(self):
        self.fx.run()
        p = self.fx.out / dpt.BODY_NAMES[0]
        with p.open("ab") as f:
            f.write(b"x")
        target = (p.stat().st_dev, p.stat().st_ino)
        actual = dpt._read_all
        reads = []
        def read(fd, size, code):
            st = os.fstat(fd)
            if (st.st_dev, st.st_ino) == target:
                reads.append(size)
            return actual(fd, size, code)
        with mock.patch.object(dpt, "_read_all", read):
            self.refuse("consumer-size", dpt._verify_payloads, self.fx.out, self.fx.contract())
        self.assertEqual(reads, [])
        (self.fx.out / dpt.COMPLETE).write_bytes(b"x" * ((1 << 16) + 1))
        self.refuse("consumer-size", dpt._verify_payloads, self.fx.out, self.fx.contract())

    def test_source_and_checkout_mutations_during_read_refuse(self):
        for which in ("source", "checkout"):
            with self.subTest(which=which):
                p = (self.fx.source_root / self.fx.profile["source_pins"][0]["path"]
                     if which == "source" else self.fx.repo / dpt.PROFILE_PATH)
                data = p.read_bytes()
                target = (p.stat().st_dev, p.stat().st_ino)
                original = dpt._read_all
                hits = []
                def read(fd, size, code):
                    result = original(fd, size, code)
                    st = os.fstat(fd)
                    if (st.st_dev, st.st_ino) == target and not hits:
                        p.write_bytes(data[:-1] + bytes((data[-1] ^ 1,)))
                        hits.append(which)
                    return result
                with mock.patch.object(dpt, "_read_all", read), self.assertRaises(dpt.Refusal):
                    if which == "source":
                        dpt.check_sources(self.fx.source_root, self.fx.profile["source_pins"])
                    else:
                        self.fx.contract().recheck_checkout()
                self.assertEqual(hits, [which])
                p.write_bytes(data)

    def test_chunk_overcount_refused(self):
        out = dpt.Output(self.fx.out, FaultOps("over", at=1))
        out.create()
        try:
            self.refuse("output-write", out.publish, "large", b"x" * ((1 << 20) + 9))
        finally:
            out.close()

    def test_nonfinite_json_refused(self):
        for token in (b"1e309", b"-1e309", b"NaN"):
            self.refuse("json", dpt._parse_json, b'{"n":' + token + b'}', "json")


# ---------------------------------------------------------------------------
# Fixed one-record --chapter1-rsw route (T07.007.014.001), synthetic only.

CH1 = dpt.CHAPTER1_RSW_ROUTE
CH1_PROFILE_BYTES = (dpt.REPO / CH1.profile_path).read_bytes()


class ChapterBase(Base):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.chmod(self.tmp.name, 0o700)
        self.fx = Fixture(self.tmp.name, route=CH1)

    def fixture(self, **kw):
        tmp = tempfile.TemporaryDirectory()
        os.chmod(tmp.name, 0o700)
        self.addCleanup(tmp.cleanup)
        return Fixture(tmp.name, route=CH1, **kw)

    def check_failed(self, fx, code, consumer=True):
        self.assertIn(dpt.FAILED, sorted(os.listdir(fx.out)))
        self.assertNotIn(dpt.COMPLETE, sorted(os.listdir(fx.out)))
        marker = json.loads((fx.out / dpt.FAILED).read_bytes())
        self.assertEqual(marker, {"reason": code, "schema": "ro-patch-payload-failed/2",
                                  "status": "failed"})
        if consumer:  # a drifted checkout refuses earlier in the consumer, by design
            self.refuse("consumer-failed-marker", dpt._verify_payloads, fx.out, fx.contract())


class Chapter1RswRouteTests(ChapterBase):
    def test_descriptor_is_fixed(self):
        self.assertEqual(CH1.task, "T07.007.014.001")
        self.assertEqual(CH1.body_names, ("target-000.body",))
        self.assertEqual(CH1.target_count, 1)
        self.assertEqual((CH1.profile_schema, CH1.manifest_schema, CH1.complete_schema,
                          CH1.failed_schema),
                         tuple("ro-patch-payload-%s/2" % k
                               for k in ("profile", "manifest", "complete", "failed")))
        self.assertEqual(CH1.profile_pin, (len(CH1_PROFILE_BYTES), sha(CH1_PROFILE_BYTES)))
        self.assertEqual(dpt.LEGACY_ROUTE.target_count, 12)
        self.assertEqual(dpt.LEGACY_ROUTE.body_names, dpt.BODY_NAMES)
        with self.assertRaises(AttributeError):
            CH1.task = "x"

    def test_production_contract_from_frozen_profile(self):
        c = dpt._production_contract(CH1)
        self.assertEqual((c.kind, c.route, c.vector_count), (dpt.PRODUCTION, CH1, 252))
        t = c.profile["targets"]
        self.assertEqual([(x["ordinal"], x["kind_label"], x["output_file"], x["real_size"],
                           x["length_aligned"], x["compressed_size"]) for x in t],
                         [(23, "rsw", "target-000.body", 182666, 28696, 28693)])
        self.assertEqual(c.profile["patch"]["sha256"], dpt.PATCH_PIN["sha256"])
        self.assertEqual(dpt._production_contract().route, dpt.LEGACY_ROUTE)

    def test_unknown_or_forged_route_refused(self):
        forged = CH1._replace(profile_pin=(1, "0" * 64))
        for route in (forged, tuple(CH1), "chapter1-rsw", None,
                      CH1._replace(body_names=("target-000.body", "target-001.body"))):
            with self.subTest(route=type(route).__name__):
                self.refuse("route-unknown", dpt._production_contract, route)
                self.refuse("route-unknown", dpt.validate_profile, self.fx.profile, self.fx.vpin,
                            route)
                self.refuse("route-unknown", dpt.Contract, "synthetic-test", self.fx.repo,
                            self.fx.profile_bytes, self.fx.vectors_bytes,
                            {"bytes": len(self.fx.profile_bytes),
                             "sha256": sha(self.fx.profile_bytes)}, self.fx.vpin,
                            {"index": 1, "bytes": 1, "sha256": "0" * 64}, dpt.SOURCE_REVISION,
                            0x102, route=route)

    def test_production_profile_cross_substitution(self):
        old = (dpt.REPO / dpt.PROFILE_PATH).read_bytes()
        vec = (dpt.REPO / dpt.VECTORS_PATH).read_bytes()
        args = (dpt.VECTORS_PIN, dpt.PATCH_PIN, dpt.SOURCE_REVISION, 0x102)
        # The route binds its own profile pin before parsing either profile.
        self.refuse("profile-pin", dpt.Contract, dpt.PRODUCTION, dpt.REPO, old, vec,
                    dpt.PROFILE_PIN, *args, route=CH1)
        self.refuse("profile-pin", dpt.Contract, dpt.PRODUCTION, dpt.REPO, CH1_PROFILE_BYTES, vec,
                    {"bytes": CH1.profile_pin[0], "sha256": CH1.profile_pin[1]}, *args,
                    route=dpt.LEGACY_ROUTE)
        self.refuse("profile-pin", dpt.Contract, dpt.PRODUCTION, dpt.REPO, old, vec,
                    {"bytes": CH1.profile_pin[0], "sha256": CH1.profile_pin[1]}, *args, route=CH1)
        # Synthetic provenance cannot claim the production kind.
        self.refuse("profile-pin", dpt.Contract, dpt.PRODUCTION, dpt.REPO, self.fx.profile_bytes,
                    self.fx.vectors_bytes, {"bytes": len(self.fx.profile_bytes),
                                            "sha256": sha(self.fx.profile_bytes)},
                    self.fx.vpin, dpt.PATCH_PIN, dpt.SOURCE_REVISION, 0x102, route=CH1)
        self.refuse("contract-kind", dpt.Contract, dpt.PRODUCTION, self.fx.repo,
                    CH1_PROFILE_BYTES, vec,
                    {"bytes": CH1.profile_pin[0], "sha256": CH1.profile_pin[1]}, *args, route=CH1)
        self.refuse("profile-pin-cross-check", dpt.Contract, dpt.PRODUCTION, dpt.REPO,
                    CH1_PROFILE_BYTES, vec,
                    {"bytes": CH1.profile_pin[0], "sha256": CH1.profile_pin[1]},
                    dpt.VECTORS_PIN, dict(dpt.PATCH_PIN, index=9297), dpt.SOURCE_REVISION, 0x102,
                    route=CH1)

    def mutate(self, code, fn, route=CH1):
        prof = json.loads(json.dumps(self.fx.profile))
        fn(prof)
        self.refuse(code, dpt.validate_profile, prof, self.fx.vpin, route)

    def test_profile_route_binding(self):
        legacy = json.loads(json.dumps(self.fx.profile))
        self.assertIs(dpt.validate_profile(legacy, self.fx.vpin, CH1), legacy)
        # Old/new schema, task and count cross-substitution.
        self.mutate("profile-schema", lambda p: p.update(schema=dpt.PROFILE_SCHEMA))
        self.mutate("profile-schema", lambda p: p.update(task=dpt.TASK))
        self.mutate("profile-schema", lambda p: None, route=dpt.LEGACY_ROUTE)
        self.mutate("profile-targets", lambda p: p["targets"].append(dict(p["targets"][0])))
        self.mutate("profile-targets", lambda p: p["targets"].clear())
        # Wrong row fields.
        t = lambda **kw: lambda p: p["targets"][0].update(kw)  # noqa: E731
        self.mutate("profile-target-fields", t(output_file="target-001.body"))
        self.mutate("profile-target-fields", t(metadata_filter="excluded"))
        self.mutate("profile-target-fields", t(ordinal=40))
        self.mutate("profile-target-name", t(name_hex=b"data\\ch1_que01.gnd".hex()))
        self.mutate("profile-target-label", t(kind_label="gnd", expected_magic_hex="4752474e",
                                              name_hex=b"x.gnd".hex()))
        self.mutate("profile-target-magic", t(expected_magic_hex="47524e47"))
        self.mutate("profile-target-kind", t(effective_kind=4))
        self.mutate("profile-target-range", t(physical_body_range=[46, 54]))
        self.mutate("profile-target-sizes", lambda p: p["targets"][0].update(
            compressed_size=p["targets"][0]["length_aligned"] + 1))
        # Fixed caps cannot be widened or narrowed by the profile.
        for key, value in CH1.limit_caps:
            with self.subTest(key=key):
                self.mutate("profile-limits", lambda p, k=key, v=value:
                            p["work_limits"].update({k: v + 1}))
                self.mutate("profile-limits", lambda p, k=key, v=value:
                            p["work_limits"].update({k: float(v)}))
        self.mutate("profile-target-budget", t(real_size=262145))
        self.mutate("profile-totals", lambda p: p["work_limits"].update(
            expected_aligned_bytes_total=p["work_limits"]["expected_aligned_bytes_total"] + 8))

    def test_legacy_profile_shape_refused_by_new_synthetic_contract(self):
        self.fx.profile["schema"] = dpt.PROFILE_SCHEMA
        self.fx.write_profile()
        self.refuse("profile-schema", self.fx.contract)
        self.assertFalse(os.path.lexists(self.fx.out))


class Chapter1RswEndToEndTests(ChapterBase):
    def test_one_record_producer_and_consumer(self):
        manifest_sha, total = self.fx.run()
        self.assertEqual(total, len(self.fx.bodies[0]))
        self.assertEqual(self.names(), sorted(("target-000.body", dpt.MANIFEST, dpt.COMPLETE)))
        self.assertEqual(stat.S_IMODE(os.lstat(self.fx.out).st_mode), 0o700)
        body = self.fx.out / "target-000.body"
        self.assertEqual(body.read_bytes(), self.fx.bodies[0])
        st = os.lstat(body)
        self.assertEqual((stat.S_IMODE(st.st_mode), st.st_nlink), (0o600, 1))
        result = dpt._verify_payloads(self.fx.out, self.fx.contract())
        self.assertEqual(result, {"targets": 1, "decoded_bytes": total,
                                  "manifest_sha256": manifest_sha})
        manifest = json.loads((self.fx.out / dpt.MANIFEST).read_bytes())
        self.assertEqual((manifest["schema"], manifest["task"], manifest["profile"]["path"],
                          manifest["profile"]["schema"], manifest["usage"]["target_count"],
                          manifest["generator"]["version"]),
                         ("ro-patch-payload-manifest/2", "T07.007.014.001", CH1.profile_path,
                          "ro-patch-payload-profile/2", 1, dpt.VERSION))
        row = manifest["targets"][0]
        self.assertEqual((row["encryption"], row["framing"], row["magic_hex"], row["cycle"]),
                         ("mixed", "zlib", "47525357", 14))
        self.assertEqual(row["padding_bytes"], row["length_aligned"] - row["compressed_size"])
        self.assertGreater(row["padding_bytes"], 7)
        marker = json.loads((self.fx.out / dpt.COMPLETE).read_bytes())
        self.assertEqual((marker["schema"], marker["target_count"]),
                         ("ro-patch-payload-complete/2", 1))
        # Neither public consumer admits synthetic provenance or the other route.
        self.refuse("consumer-contract", dpt.verify_chapter1_rsw, self.fx.out)
        self.refuse("consumer-file-set", dpt.verify_payloads, self.fx.out)

    def test_stored_and_header_kind(self):
        fx = self.fixture(stored_index=0, sizes=[3000], header_version=0x200)
        fx.run()
        row = json.loads((fx.out / dpt.MANIFEST).read_bytes())["targets"][0]
        self.assertEqual((row["framing"], row["compressed_size"], row["real_size"]),
                         ("stored", 3006, 3006))
        self.assertEqual(row["padding_bytes"], row["length_aligned"] - 3006)
        self.assertGreater(row["padding_bytes"], 7)
        self.assertEqual((fx.out / "target-000.body").read_bytes(), fx.bodies[0])
        dpt._verify_payloads(fx.out, fx.contract())

    def test_strict_framing_refusals(self):
        adler = lambda c, b: (c[:-1] + bytes((c[-1] ^ 1,)), len(b))  # noqa: E731
        cases = (
            ("zlib-invalid-stream", adler),
            ("zlib-trailing-data", lambda c, b: (c + b"\x00", len(b))),
            ("zlib-trailing-data", lambda c, b: (c + zlib.compress(b"x"), len(b))),
            ("zlib-overlong", lambda c, b: (c, len(b) - 1)),
            ("zlib-short", lambda c, b: (c, len(b) + 1)),
            ("zlib-truncated", lambda c, b: (c[:-3], len(b))),
        )
        for code, mangle in cases:
            with self.subTest(code=code):
                fx = self.fixture(mangle=mangle)
                self.refuse(code, fx.run)
                self.check_failed(fx, code)
                self.assertEqual(sorted(os.listdir(fx.out)), [dpt.FAILED])

    def test_wrong_kind_and_range_reach_their_gates(self):
        fx = self.fixture()
        fx.profile["targets"][0]["effective_kind"] = 5  # header-only decrypt of a mixed body
        fx.write_profile()
        self.refuse("zlib-invalid-stream", fx.run)
        self.check_failed(fx, "zlib-invalid-stream")
        fx = self.fixture()
        t = fx.profile["targets"][0]
        t["payload_offset_field"] += 8  # into the 16-byte gap: consistent profile, wrong bytes
        t["physical_body_range"] = [r + 8 for r in t["physical_body_range"]]
        fx.write_profile()
        self.refuse("zlib-invalid-stream", fx.run)

    def test_existing_output_sentinel_preserved(self):
        self.fx.out.mkdir(mode=0o700)
        (self.fx.out / "sentinel").write_bytes(b"keep")
        self.refuse("output-exists", self.fx.run)
        self.assertEqual(self.names(), ["sentinel"])
        self.assertEqual((self.fx.out / "sentinel").read_bytes(), b"keep")
        os.unlink(self.fx.out / "sentinel")
        os.rmdir(self.fx.out)
        os.symlink(self.fx.out_parent, self.fx.out)
        self.refuse("output-exists", self.fx.run)
        self.assertTrue(os.path.islink(self.fx.out))

    def test_patch_and_source_special_paths(self):
        real = self.fx.patch
        link = real.with_name("link.gpf")
        os.symlink(real, link)
        self.fx.patch = link
        self.refuse("patch-unopenable", self.fx.run)
        os.unlink(link)
        os.link(real, link)
        self.fx.patch = real
        self.refuse("patch-hardlinked", self.fx.run)
        os.unlink(link)
        fifo = real.with_name("fifo.gpf")
        os.mkfifo(fifo)
        self.fx.patch = fifo
        self.refuse("patch-not-regular", self.fx.run)
        self.fx.patch = real
        p = self.fx.source_root / SOURCE_RELS[0]
        alt = self.fx.base / "alt"
        alt.write_bytes(p.read_bytes())
        p.unlink()
        os.symlink(alt, p)
        self.refuse("source-unreadable", self.fx.run)
        p.unlink()
        os.link(alt, p)
        self.refuse("source-not-regular", self.fx.run)
        self.assertFalse(os.path.lexists(self.fx.out))

    def test_late_drift_before_completion(self):
        for target, code in (("profile", "profile-drift"), ("source", "source-pin"),
                             ("generator", "generator-unreadable")):
            with self.subTest(target=target):
                fx = self.fixture()
                path = (fx.repo / CH1.profile_path if target == "profile"
                        else fx.source_root / SOURCE_RELS[0] if target == "source"
                        else fx.repo / dpt.GENERATOR_PATH)

                def fsync(ops, fd, path=path, hits=[]):
                    os.fsync(fd)
                    if os.fstat(fd).st_size and not hits and os.path.lexists(fx.out / dpt.MANIFEST):
                        data = path.read_bytes()
                        path.write_bytes(data[:-1] + bytes((data[-1] ^ 1,)))
                        hits.append(True)
                with mock.patch.object(dpt.FileOps, "fsync", fsync):
                    self.refuse(code, fx.run)
                self.check_failed(fx, code, consumer=target != "profile")

    def test_drift_after_consumer(self):
        for target, code in (("source", "source-pin"), ("generator", "generator-unreadable"),
                             ("profile", "profile-drift"), ("vectors", "vectors-drift"),
                             ("body", "output-readback")):
            with self.subTest(target=target):
                fx = self.fixture()
                contract = fx.contract()
                hits = []

                def consumer(path, fx=fx, target=target):
                    self.assertEqual(dpt._verify_payloads(path, contract)["targets"], 1)
                    p = (fx.source_root / SOURCE_RELS[0] if target == "source"
                         else fx.out / "target-000.body" if target == "body"
                         else fx.repo / {"generator": dpt.GENERATOR_PATH,
                                         "profile": CH1.profile_path,
                                         "vectors": dpt.VECTORS_PATH}[target])
                    data = p.read_bytes()
                    p.write_bytes(data[:-1] + bytes((data[-1] ^ 1,)))
                    hits.append(target)
                self.refuse(code, dpt._run, fx.source_root, fx.patch, fx.out, contract,
                            consumer=consumer)
                self.assertEqual(hits, [target])
                self.check_failed(fx, code, consumer=target not in ("profile", "vectors"))


class Chapter1RswFaultOps(FaultOps):
    def read_back(self, dir_fd, name):
        st, data = dpt.FileOps.read_back(self, dir_fd, name)
        if self.mode == "readback" and name == "target-000.body":
            data = data[:-1] + b"\0"
        return st, data


class Chapter1RswPublicationTests(ChapterBase):
    def test_publication_and_close_faults(self):
        # Writes: 1 body, 2 manifest, 3 completion marker.
        for mode, at, code in (("zero", 1, "output-write"), ("over", 2, "output-write"),
                               ("raise", 3, "output-flush"), ("fsync", 3, "output-flush"),
                               ("close", 2, "output-close"), ("readback", 1, "output-readback")):
            with self.subTest(mode=mode, at=at):
                fx = self.fixture()
                self.refuse(code, fx.run, ops=Chapter1RswFaultOps(mode, at=at))
                self.check_failed(fx, code)
                self.assertIn("target-000.body", sorted(os.listdir(fx.out)))

    def test_final_directory_close_error_revokes_completion(self):
        original = dpt.Output.close
        hits = []

        def close_then_error(output):
            had_fd = output.dir_fd is not None
            original(output)
            if had_fd and not hits:
                hits.append(True)
                raise OSError("injected after final directory close")
        with mock.patch.object(dpt.Output, "close", close_then_error):
            self.refuse("output-close", self.fx.run)
        self.assertEqual(hits, [True])
        self.check_failed(self.fx, "output-close")

    def test_failed_marker_precedence(self):
        self.fx.run()
        fd = os.open(self.fx.out / dpt.FAILED, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        self.refuse("consumer-failed-marker", dpt._verify_payloads, self.fx.out, self.fx.contract())
        self.refuse("consumer-failed-marker", dpt.verify_chapter1_rsw, self.fx.out)

    def test_unexpected_error_is_refusal(self):
        with mock.patch.object(dpt, "build_manifest", side_effect=RuntimeError("x")):
            self.refuse("internal-error", self.fx.run)
        self.check_failed(self.fx, "internal-error")


class Chapter1RswConsumerTests(ChapterBase):
    def setUp(self):
        super().setUp()
        self.fx.run()
        self.contract = self.fx.contract()

    def verify(self):
        return dpt._verify_payloads(self.fx.out, self.contract)

    def rewrite(self, name, data):
        (self.fx.out / name).write_bytes(data)

    def rebind(self, manifest, **marker):
        data = dpt.canonical(manifest)
        self.rewrite(dpt.MANIFEST, data)
        fields = {"manifest_bytes": len(data), "manifest_sha256": sha(data),
                  "schema": CH1.complete_schema, "status": "complete", "target_count": 1}
        fields.update(marker)
        self.rewrite(dpt.COMPLETE, dpt.canonical(fields))

    def test_positive_and_rebound_original(self):
        original = json.loads((self.fx.out / dpt.MANIFEST).read_bytes())
        self.assertEqual(self.verify()["targets"], 1)
        self.rebind(original)
        self.assertEqual(self.verify()["targets"], 1)

    def test_old_new_marker_and_manifest_substitution(self):
        original = json.loads((self.fx.out / dpt.MANIFEST).read_bytes())
        for code, fn, marker in (
                ("consumer-marker", None, {"schema": dpt.COMPLETE_SCHEMA}),
                ("consumer-marker", None, {"target_count": 12}),
                ("consumer-marker", None, {"target_count": 1.0}),
                ("consumer-contract", lambda m: m.update(schema=dpt.MANIFEST_SCHEMA), {}),
                ("consumer-contract", lambda m: m.update(task=dpt.TASK), {}),
                ("consumer-contract", lambda m: m["profile"].update(path=dpt.PROFILE_PATH), {}),
                ("consumer-contract", lambda m: m["profile"].update(schema=dpt.PROFILE_SCHEMA), {}),
                ("consumer-contract", lambda m: m["work_limits"].update(max_output_bytes=1 << 30),
                 {}),
                ("consumer-contract", lambda m: m["generator"].update(version="1.0.1"), {}),
                ("consumer-contract", lambda m: m.update(contract_kind=dpt.PRODUCTION), {}),
                ("consumer-usage", lambda m: m["usage"].update(target_count=12), {}),
                ("consumer-targets", lambda m: m["targets"].append(dict(m["targets"][0])), {}),
                ("consumer-row-contract", lambda m: m["targets"][0].update(ordinal=24), {}),
                ("consumer-row-contract", lambda m: m["targets"][0].update(
                    name_hex=b"data\\ch1_que02.rsw".hex()), {}),
                ("consumer-row-contract", lambda m: m["targets"][0].update(
                    physical_body_range=[46, 54]), {}),
                ("consumer-row-contract", lambda m: m["targets"][0].update(effective_kind=5), {}),
                ("consumer-row-contract", lambda m: m["targets"][0].update(real_size=1), {}),
                ("consumer-row-contract", lambda m: m["targets"][0].update(
                    output_file="target-001.body"), {}),
                ("consumer-row-derived", lambda m: m["targets"][0].update(framing="stored"), {}),
                ("consumer-row-hash", lambda m: m["targets"][0].update(decoded_sha256="x"), {}),
                ("consumer-body", lambda m: m["targets"][0].update(decoded_sha256="0" * 64), {})):
            with self.subTest(code=code, marker=marker):
                m = json.loads(json.dumps(original))
                if fn:
                    fn(m)
                self.rebind(m, **marker)
                self.refuse(code, self.verify)
        self.rebind(original)
        self.verify()

    def test_output_set_and_privacy(self):
        (self.fx.out / "target-001.body").write_bytes(b"")
        self.refuse("consumer-file-set", self.verify)
        os.unlink(self.fx.out / "target-001.body")
        body = self.fx.out / "target-000.body"
        os.link(body, self.fx.out_parent / "hl")
        self.refuse("consumer-file-privacy", self.verify)
        os.unlink(self.fx.out_parent / "hl")
        data = body.read_bytes()
        os.rename(body, self.fx.out_parent / "moved")
        os.symlink(self.fx.out_parent / "moved", body)
        self.refuse("consumer-unreadable", self.verify)  # O_NOFOLLOW
        os.unlink(body)
        self.refuse("consumer-file-set", self.verify)
        body.write_bytes(data[:-1])
        self.refuse("consumer-size", self.verify)
        body.write_bytes(data)
        link = self.fx.out_parent / "dirlink"
        os.symlink(self.fx.out, link)
        self.refuse("consumer-output", dpt._verify_payloads, link, self.contract)
        self.verify()

    def test_legacy_output_refused_by_new_consumers(self):
        tmp = tempfile.TemporaryDirectory()
        os.chmod(tmp.name, 0o700)
        self.addCleanup(tmp.cleanup)
        legacy = Fixture(tmp.name)
        legacy.run()
        self.refuse("consumer-file-set", dpt._verify_payloads, legacy.out, self.contract)
        self.refuse("consumer-file-set", dpt.verify_chapter1_rsw, legacy.out)
        self.refuse("consumer-file-set", dpt._verify_payloads, self.fx.out, legacy.contract())


class Chapter1RswCliTests(ChapterBase):
    def run_main(self, argv):
        out = tempfile.TemporaryFile("w+")
        err = tempfile.TemporaryFile("w+")
        self.addCleanup(out.close)
        self.addCleanup(err.close)
        with mock.patch.object(sys, "stdout", out), mock.patch.object(sys, "stderr", err):
            code = dpt.main(argv)
        out.seek(0)
        err.seek(0)
        return code, out.read(), err.read()

    def test_flag_selects_fixed_route_only_after_positionals(self):
        pos = [str(self.fx.source_root), str(self.fx.patch), str(self.fx.out)]
        seen = []

        def capture(source, patch, output, contract):
            seen.append((contract.kind, contract.route, contract.profile_pin))
            raise dpt.Refusal("captured")
        with mock.patch.object(dpt, "_run", capture):
            self.assertEqual(self.run_main(pos + ["--chapter1-rsw"])[0], 2)
            self.assertEqual(self.run_main(pos)[0], 2)
        self.assertEqual(seen, [
            (dpt.PRODUCTION, CH1, {"bytes": CH1.profile_pin[0], "sha256": CH1.profile_pin[1]}),
            (dpt.PRODUCTION, dpt.LEGACY_ROUTE, dict(dpt.PROFILE_PIN))])
        for argv in (["--chapter1-rsw"] + pos, pos[:2] + ["--chapter1-rsw"],
                     pos + ["--chapter1-rsw", "--chapter1-rsw"], pos + ["--chapter1-rsw=1"],
                     pos + ["--CHAPTER1-RSW"], pos + ["--profile"], pos + ["--chapter1-rsw", "x"],
                     pos + ["chapter1-rsw"], pos[:2] + ["--chapter1-rsw", pos[2]]):
            with self.subTest(argv=argv[-1]):
                with mock.patch.object(dpt, "_production_contract",
                                       side_effect=AssertionError("contract built")):
                    code, out, err = self.run_main(argv)
                self.assertEqual((code, out), (64, ""))
                self.assertIn('"status": "usage"', err)
        self.assertFalse(os.path.lexists(self.fx.out))

    def test_production_route_refuses_synthetic_inputs_before_output(self):
        code, out, err = self.run_main([str(self.fx.source_root), str(self.fx.patch),
                                        str(self.fx.out), "--chapter1-rsw"])
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(json.loads(err), {"status": "refused", "reason": "source-pin"})
        self.assertNotIn(self.tmp.name, err)
        self.assertFalse(os.path.lexists(self.fx.out))


# ---------------------------------------------------------------------------
# Fixed seventeen-record --remaining-rsw route (T07.007.014.006), synthetic only.

REM = dpt.REMAINING_RSW_ROUTE
REM_PROFILE_BYTES = (dpt.REPO / REM.profile_path).read_bytes()
REM_ROOTS = ("1@ch1a", "1@ch1b", "ch1_dw", "ch1_geffen", "ch1_gef_in", "ch1_gfn01", "ch1_gfn03",
             "ch1_sf01", "ch1_sf02", "ch1_sf03", "ch1_vrgef1", "ch1_vrgef2", "hem_dun01",
             "hem_dun02", "hem_fild", "uknw_ruin", "uknw_ruin2")
REM_CAPS = {"max_aligned_bytes_per_target": 131072, "max_decoded_bytes_per_target": 1048576,
            "max_decoded_bytes_total": 8388608, "max_output_bytes": 16777216,
            "read_chunk_bytes": 1048576}
ALL_ROUTES = ((dpt.LEGACY_ROUTE, (dpt.REPO / dpt.PROFILE_PATH).read_bytes()),
              (CH1, CH1_PROFILE_BYTES), (REM, REM_PROFILE_BYTES))


def at_index(index, mangle):
    """Apply a body mangle to one synthetic target only (payload byte 5 is its index)."""
    return lambda c, b: mangle(c, b) if b[5] == index else (c, len(b))


class RemainingBase(Base):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.chmod(self.tmp.name, 0o700)
        self.fx = Fixture(self.tmp.name, route=REM)

    def fixture(self, route=REM, **kw):
        tmp = tempfile.TemporaryDirectory()
        os.chmod(tmp.name, 0o700)
        self.addCleanup(tmp.cleanup)
        return Fixture(tmp.name, route=route, **kw)

    def check_failed(self, fx, code, consumer=True):
        names = sorted(os.listdir(fx.out))
        self.assertIn(dpt.FAILED, names)
        self.assertNotIn(dpt.COMPLETE, names)
        marker = json.loads((fx.out / dpt.FAILED).read_bytes())
        self.assertEqual(marker, {"reason": code, "schema": "ro-patch-payload-failed/2",
                                  "status": "failed"})
        if consumer:
            self.refuse("consumer-failed-marker", dpt._verify_payloads, fx.out, fx.contract())
            self.refuse("consumer-failed-marker", dpt.verify_remaining_rsw, fx.out)
        return names


class RemainingRswRouteTests(RemainingBase):
    def test_descriptor_is_fixed(self):
        self.assertEqual(REM.task, "T07.007.014.006")
        self.assertEqual(REM.body_names, tuple("target-%03d.body" % i for i in range(17)))
        self.assertEqual(REM.target_count, 17)
        self.assertEqual(REM.labels, ("rsw",))
        self.assertEqual(REM.profile_path, "docs/project/fixtures/T07.007.014.006-profile.json")
        self.assertEqual(REM.profile_pin, (10759, "286680e505da618f39f0ba53bd48e198ba6133f19c107"
                                                  "74d34b4d38d29c8c19c"))
        self.assertEqual(REM.profile_pin, (len(REM_PROFILE_BYTES), sha(REM_PROFILE_BYTES)))
        self.assertEqual(dict(REM.limit_caps), REM_CAPS)
        self.assertEqual((REM.profile_schema, REM.manifest_schema, REM.complete_schema,
                          REM.failed_schema),
                         (CH1.profile_schema, CH1.manifest_schema, CH1.complete_schema,
                          CH1.failed_schema))
        # The two older descriptors keep their literal contracts.
        self.assertEqual((dpt.LEGACY_ROUTE.task, dpt.LEGACY_ROUTE.profile_pin,
                          dpt.LEGACY_ROUTE.target_count, dpt.LEGACY_ROUTE.limit_caps),
                         ("T07.007.003", (8474, "06805b0a28fef87b53d6e2f87e50079e14a3b7181a44e541b"
                                                "6b0c0aa268ead2a"), 12, None))
        self.assertEqual((CH1.task, CH1.profile_pin, CH1.target_count, dict(CH1.limit_caps)),
                         ("T07.007.014.001", (3415, "c47c0ebe8c3f6ec5341e92603b7860ffd3aaa3139c736"
                                                    "786584a91f9ea19a8e2"), 1,
                          {"max_aligned_bytes_per_target": 65536,
                           "max_decoded_bytes_per_target": 262144,
                           "max_decoded_bytes_total": 262144, "max_output_bytes": 1048576,
                           "read_chunk_bytes": 1048576}))
        self.assertEqual(dpt._ROUTES, (dpt.LEGACY_ROUTE, CH1, REM))
        self.assertEqual(dpt._FLAG_ROUTES, (("--chapter1-rsw", CH1), ("--remaining-rsw", REM)))
        with self.assertRaises(AttributeError):
            REM.body_names = ()
        # No environment-selected profile, target, count or limit exists.
        self.assertNotIn("environ", (dpt.REPO / dpt.GENERATOR_PATH).read_text())

    def test_production_contract_from_frozen_profile(self):
        c = dpt._production_contract(REM)
        self.assertEqual((c.kind, c.route, c.vector_count), (dpt.PRODUCTION, REM, 252))
        t = c.profile["targets"]
        self.assertEqual([bytes.fromhex(x["name_hex"]) for x in t],
                         [b"data\\" + r.encode() + b".rsw" for r in REM_ROOTS])
        self.assertEqual([x["output_file"] for x in t], list(REM.body_names))
        self.assertEqual([x["ordinal"] for x in t],
                         [2, 4, 9, 12, 15, 18, 21, 26, 29, 32, 34, 36, 43, 46, 49, 5634, 5637])
        self.assertEqual({(x["kind_label"], x["effective_kind"], x["expected_magic_hex"])
                          for x in t}, {("rsw", 3, "47525357")})
        self.assertEqual((sum(x["length_aligned"] for x in t), sum(x["real_size"] for x in t)),
                         (666248, 4806359))
        limits = c.profile["work_limits"]
        self.assertEqual(limits, dict(REM_CAPS, expected_aligned_bytes_total=666248,
                                      expected_decoded_bytes_total=4806359))
        self.assertEqual(c.profile["patch"]["sha256"], dpt.PATCH_PIN["sha256"])
        self.assertEqual(c.profile["source_pins"], dpt._production_contract().profile["source_pins"])
        # Older routes still build from their own frozen profiles.
        self.assertEqual(len(dpt._production_contract().profile["targets"]), 12)
        self.assertEqual(len(dpt._production_contract(CH1).profile["targets"]), 1)

    def test_unknown_or_forged_route_refused(self):
        caps = dict(REM.limit_caps)
        for route in (REM._replace(body_names=REM.body_names[:16]),
                      REM._replace(body_names=REM.body_names + ("target-017.body",)),
                      REM._replace(task="T07.007.014.001"),
                      REM._replace(profile_pin=(10759, "0" * 64)),
                      REM._replace(profile_path=CH1.profile_path),
                      REM._replace(labels=("rsw", "gnd")),
                      REM._replace(limit_caps=tuple(dict(caps, max_output_bytes=1 << 30).items())),
                      REM._replace(limit_caps=CH1.limit_caps), REM._replace(limit_caps=None),
                      tuple(REM), list(REM), "--remaining-rsw", "remaining-rsw", None):
            with self.subTest(route=repr(route)[:60]):
                self.refuse("route-unknown", dpt._production_contract, route)
                self.refuse("route-unknown", dpt.validate_profile, self.fx.profile, self.fx.vpin,
                            route)
                self.refuse("route-unknown", dpt.Contract, "synthetic-test", self.fx.repo,
                            self.fx.profile_bytes, self.fx.vectors_bytes,
                            {"bytes": len(self.fx.profile_bytes),
                             "sha256": sha(self.fx.profile_bytes)}, self.fx.vpin,
                            {"index": 1, "bytes": 1, "sha256": "0" * 64}, dpt.SOURCE_REVISION,
                            0x102, route=route)

    def test_production_profile_cross_substitution_all_routes(self):
        vec = (dpt.REPO / dpt.VECTORS_PATH).read_bytes()
        args = (dpt.VECTORS_PIN, dpt.PATCH_PIN, dpt.SOURCE_REVISION, 0x102)
        for route, _ in ALL_ROUTES:
            for other, data in ALL_ROUTES:
                with self.subTest(route=route.task, profile=other.task):
                    pin = {"bytes": len(data), "sha256": sha(data)}
                    if route is other:
                        c = dpt.Contract(dpt.PRODUCTION, dpt.REPO, data, vec, pin, *args,
                                         route=route)
                        self.assertEqual(len(c.profile["targets"]), route.target_count)
                    else:
                        # The route's own pin is bound before either profile is parsed.
                        self.refuse("profile-pin", dpt.Contract, dpt.PRODUCTION, dpt.REPO, data,
                                    vec, pin, *args, route=route)
                        own = {"bytes": route.profile_pin[0], "sha256": route.profile_pin[1]}
                        self.refuse("profile-pin", dpt.Contract, dpt.PRODUCTION, dpt.REPO, data,
                                    vec, own, *args, route=route)
        # A 16- or 18-target edit of the frozen profile cannot pass the production pin.
        prof = json.loads(REM_PROFILE_BYTES)
        for targets in (prof["targets"][:16], prof["targets"] + prof["targets"][-1:]):
            edited = json.dumps(dict(prof, targets=targets), indent=2, sort_keys=True).encode()
            self.refuse("profile-pin", dpt.Contract, dpt.PRODUCTION, dpt.REPO, edited, vec,
                        {"bytes": len(edited), "sha256": sha(edited)}, *args, route=REM)
        self.refuse("contract-kind", dpt.Contract, dpt.PRODUCTION, self.fx.repo, REM_PROFILE_BYTES,
                    vec, {"bytes": REM.profile_pin[0], "sha256": REM.profile_pin[1]}, *args,
                    route=REM)
        self.refuse("profile-pin-cross-check", dpt.Contract, dpt.PRODUCTION, dpt.REPO,
                    REM_PROFILE_BYTES, vec,
                    {"bytes": REM.profile_pin[0], "sha256": REM.profile_pin[1]},
                    dpt.VECTORS_PIN, dict(dpt.PATCH_PIN, index=9297), dpt.SOURCE_REVISION, 0x102,
                    route=REM)

    def mutate(self, code, fn, route=REM):
        prof = json.loads(json.dumps(self.fx.profile))
        fn(prof)
        self.refuse(code, dpt.validate_profile, prof, self.fx.vpin, route)

    def test_profile_route_binding(self):
        self.assertIs(dpt.validate_profile(self.fx.profile, self.fx.vpin, REM), self.fx.profile)
        # Schema/task substitution across all three routes, in both directions.
        self.mutate("profile-schema", lambda p: p.update(schema=dpt.PROFILE_SCHEMA))
        self.mutate("profile-schema", lambda p: p.update(task=CH1.task))
        self.mutate("profile-schema", lambda p: p.update(task=dpt.TASK))
        self.mutate("profile-schema", lambda p: None, route=CH1)
        self.mutate("profile-schema", lambda p: None, route=dpt.LEGACY_ROUTE)
        ch1 = self.fixture(route=CH1)
        self.refuse("profile-schema", dpt.validate_profile, ch1.profile, ch1.vpin, REM)
        # A chapter profile relabelled as this task still fails at its caps, then its count.
        relabel = json.loads(json.dumps(ch1.profile))
        relabel["task"] = REM.task
        self.refuse("profile-limits", dpt.validate_profile, relabel, ch1.vpin, REM)
        relabel["work_limits"].update(REM_CAPS)
        self.refuse("profile-targets", dpt.validate_profile, relabel, ch1.vpin, REM)
        relabel = json.loads(json.dumps(self.fx.profile))
        relabel["task"] = CH1.task
        self.refuse("profile-limits", dpt.validate_profile, relabel, self.fx.vpin, CH1)
        relabel["work_limits"].update(CH1.limit_caps)
        # Its seventeen-body total exceeds the chapter cap; then only the count remains.
        self.refuse("profile-limits", dpt.validate_profile, relabel, self.fx.vpin, CH1)
        relabel["work_limits"].update(expected_decoded_bytes_total=1)
        self.refuse("profile-targets", dpt.validate_profile, relabel, self.fx.vpin, CH1)
        # 16 and 18 targets, even with consistent totals.
        def drop(p):
            gone = p["targets"].pop()
            p["work_limits"]["expected_aligned_bytes_total"] -= gone["length_aligned"]
            p["work_limits"]["expected_decoded_bytes_total"] -= gone["real_size"]
        self.mutate("profile-targets", drop)
        self.mutate("profile-targets", lambda p: p["targets"].append(dict(p["targets"][-1])))
        self.mutate("profile-targets", lambda p: p["targets"].clear())
        # Row fields, order and labels.
        t = lambda i, **kw: lambda p: p["targets"][i].update(kw)  # noqa: E731
        self.mutate("profile-target-fields", t(16, output_file="target-017.body"))
        self.mutate("profile-target-fields", t(3, output_file="target-004.body"))
        self.mutate("profile-target-fields", t(8, metadata_filter="excluded"))
        self.mutate("profile-target-fields", t(16, ordinal=40))
        self.mutate("profile-target-ordinal", t(16, ordinal=10))
        self.mutate("profile-target-name", t(12, name_hex=b"data\\hem_dun01.gnd".hex()))
        self.mutate("profile-target-label", t(5, kind_label="gat", expected_magic_hex="47524154",
                                              name_hex=b"x.gat".hex()))
        self.mutate("profile-target-magic", t(0, expected_magic_hex="4752474e"))
        self.mutate("profile-target-kind", t(9, effective_kind=4))
        self.mutate("profile-target-range", t(16, physical_body_range=[46, 54]))

        def swap(p):
            a, b = p["targets"][1], p["targets"][2]
            p["targets"][1], p["targets"][2] = dict(b, output_file=a["output_file"]), \
                dict(a, output_file=b["output_file"])
        self.mutate("profile-target-range", swap)
        # Exact caps: neither widened, narrowed nor retyped.
        for key, value in REM.limit_caps:
            with self.subTest(key=key):
                chapter = dict(CH1.limit_caps)[key]
                for bad in (value + 1, value - 1, float(value)) + ((chapter,) * (chapter != value)):
                    self.mutate("profile-limits", lambda p, k=key, v=bad:
                                p["work_limits"].update({k: v}))
        self.mutate("profile-target-budget", t(4, real_size=1048577))
        self.mutate("profile-target-budget", t(4, length_aligned=131080, compressed_size=131073))
        for key in ("expected_aligned_bytes_total", "expected_decoded_bytes_total"):
            with self.subTest(total=key):
                self.mutate("profile-totals", lambda p, k=key: p["work_limits"].update(
                    {k: p["work_limits"][k] + 8}))
                self.mutate("profile-totals", lambda p, k=key: p["work_limits"].update(
                    {k: p["work_limits"][k] - 1}))
        self.mutate("profile-limits", lambda p: p["work_limits"].update(
            expected_decoded_bytes_total=8388609))

    def test_per_target_ceiling_and_six_digit_cycle(self):
        # One target near the 128 KiB aligned ceiling exercises the 6-digit cycle (15).
        sizes = list(REMAINING_SIZES)
        sizes[16] = 430000
        fx = self.fixture(sizes=sizes, stored_index=7)
        fx.run()
        rows = json.loads((fx.out / dpt.MANIFEST).read_bytes())["targets"]
        self.assertLessEqual(max(r["length_aligned"] for r in rows), 131072)
        self.assertGreater(rows[16]["length_aligned"], 100000)
        self.assertEqual(rows[16]["cycle"], 15)
        self.assertEqual({r["cycle"] for r in rows if r["encryption"] == "mixed"}, {1, 4, 5, 14, 15})
        self.assertEqual((rows[7]["framing"], rows[10]["effective_kind"], rows[10]["encryption"]),
                         ("stored", 7, "mixed"))
        self.assertEqual(dpt._verify_payloads(fx.out, fx.contract())["targets"], 17)
        # The same target one aligned block over the fixed cap refuses before output.
        fx = self.fixture(sizes=sizes)
        t = fx.profile["targets"][16]
        self.assertLessEqual(t["length_aligned"], 131072)
        t["length_aligned"] = 131080
        t["physical_body_range"][1] = t["physical_body_range"][0] + 131080
        fx.write_profile()
        self.refuse("profile-target-budget", fx.contract)


class RemainingRswEndToEndTests(RemainingBase):
    def test_seventeen_record_producer_and_consumer(self):
        manifest_sha, total = self.fx.run()
        self.assertEqual(total, sum(len(b) for b in self.fx.bodies))
        self.assertEqual(self.names(), sorted(REM.body_names + (dpt.MANIFEST, dpt.COMPLETE)))
        self.assertEqual(stat.S_IMODE(os.lstat(self.fx.out).st_mode), 0o700)
        for name, body in zip(REM.body_names, self.fx.bodies):
            st = os.lstat(self.fx.out / name)
            self.assertEqual((stat.S_IMODE(st.st_mode), st.st_nlink), (0o600, 1))
            self.assertEqual((self.fx.out / name).read_bytes(), body)
        result = dpt._verify_payloads(self.fx.out, self.fx.contract())
        self.assertEqual(result, {"targets": 17, "decoded_bytes": total,
                                  "manifest_sha256": manifest_sha})
        manifest = json.loads((self.fx.out / dpt.MANIFEST).read_bytes())
        self.assertEqual((manifest["schema"], manifest["task"], manifest["profile"]["path"],
                          manifest["profile"]["schema"], manifest["usage"]["target_count"],
                          manifest["generator"]["version"], manifest["work_limits"]),
                         ("ro-patch-payload-manifest/2", REM.task, REM.profile_path,
                          "ro-patch-payload-profile/2", 17, dpt.VERSION,
                          self.fx.profile["work_limits"]))
        self.assertEqual(manifest["usage"]["aligned_bytes_read"],
                         sum(t["length_aligned"] for t in self.fx.profile["targets"]))
        rows = manifest["targets"]
        self.assertEqual([r["output_file"] for r in rows], list(REM.body_names))
        self.assertEqual({(r["magic_hex"], r["framing"]) for r in rows}, {("47525357", "zlib")})
        self.assertEqual([r["version_prefix_hex"] for r in rows], ["02%02x" % i for i in range(17)])
        self.assertEqual({r["cycle"] for r in rows}, {1, 4, 5, 14})
        marker = json.loads((self.fx.out / dpt.COMPLETE).read_bytes())
        self.assertEqual((marker["schema"], marker["target_count"]),
                         ("ro-patch-payload-complete/2", 17))
        # No public consumer admits synthetic provenance or another route's output.
        self.refuse("consumer-contract", dpt.verify_remaining_rsw, self.fx.out)
        self.refuse("consumer-file-set", dpt.verify_chapter1_rsw, self.fx.out)
        self.refuse("consumer-file-set", dpt.verify_payloads, self.fx.out)

    def test_negatives_reach_their_intended_gate(self):
        flip = lambda c, b: (c[:-1] + bytes((c[-1] ^ 1,)), len(b))  # noqa: E731
        magic = lambda c, b: (zlib.compress(b"GRGN" + b[4:], 6), len(b))  # noqa: E731
        for index, mangle, code in ((16, flip, "zlib-invalid-stream"),
                                    (9, magic, "decoded-magic"),
                                    (0, lambda c, b: (c + b"\0", len(b)), "zlib-trailing-data"),
                                    (12, lambda c, b: (c, len(b) + 1), "zlib-short")):
            with self.subTest(code=code, index=index):
                fx = self.fixture(mangle=at_index(index, mangle))
                calls = []
                original = dpt.frame

                def counting(*args):
                    calls.append(args[1])
                    return original(*args)
                with mock.patch.object(dpt, "frame", counting):
                    self.refuse(code, fx.run)
                # The refusal comes from the intended target, after all earlier ones framed.
                self.assertEqual(len(calls), index + 1)
                self.assertEqual(calls[-1], fx.profile["targets"][index]["compressed_size"])
                self.assertEqual(self.check_failed(fx, code), [dpt.FAILED])

    def test_wrong_kind_and_range_reach_their_gates(self):
        fx = self.fixture()
        fx.profile["targets"][14]["effective_kind"] = 5
        fx.write_profile()
        self.refuse("zlib-invalid-stream", fx.run)
        self.check_failed(fx, "zlib-invalid-stream")
        fx = self.fixture()
        t = fx.profile["targets"][14]  # even index: followed by a 16-byte gap
        t["payload_offset_field"] += 8
        t["physical_body_range"] = [r + 8 for r in t["physical_body_range"]]
        fx.write_profile()
        self.refuse("zlib-invalid-stream", fx.run)
        self.check_failed(fx, "zlib-invalid-stream")

    def test_existing_output_and_special_inputs(self):
        self.fx.out.mkdir(mode=0o700)
        (self.fx.out / "sentinel").write_bytes(b"keep")
        self.refuse("output-exists", self.fx.run)
        self.assertEqual(self.names(), ["sentinel"])
        fx = self.fixture()
        link = fx.patch.with_name("link.gpf")
        os.link(fx.patch, link)
        self.refuse("patch-hardlinked", fx.run)
        self.assertFalse(os.path.lexists(fx.out))

    def test_late_publication_failure_leaves_no_usable_completion(self):
        # After a passing consumer, a changed last body revokes the owned completion.
        fx = self.fixture()
        contract = fx.contract()
        seen = []

        def consumer(path):
            seen.append(dpt._verify_payloads(path, contract)["targets"])
            p = fx.out / "target-016.body"
            data = p.read_bytes()
            p.write_bytes(data[:-1] + bytes((data[-1] ^ 1,)))
        self.refuse("output-readback", dpt._run, fx.source_root, fx.patch, fx.out, contract,
                    consumer=consumer)
        self.assertEqual(seen, [17])
        names = self.check_failed(fx, "output-readback")
        self.assertEqual(names, sorted(REM.body_names + (dpt.MANIFEST, dpt.FAILED)))
        # Writes: 1-17 bodies, 18 manifest, 19 completion marker.
        for mode, at, code in (("zero", 19, "output-write"), ("fsync", 17, "output-flush"),
                               ("close", 18, "output-close"), ("raise", 19, "output-flush")):
            with self.subTest(mode=mode, at=at):
                fx = self.fixture()
                self.refuse(code, fx.run, ops=FaultOps(mode, at=at))
                names = self.check_failed(fx, code)
                self.assertIn("target-016.body" if at >= 17 else "target-000.body", names)
        # Late generator drift before completion.
        fx = self.fixture()

        def fsync(ops, fd, hits=[]):
            os.fsync(fd)
            if not hits and os.path.lexists(fx.out / dpt.MANIFEST):
                p = fx.repo / dpt.GENERATOR_PATH
                p.write_bytes(p.read_bytes() + b"\n")
                hits.append(True)
        with mock.patch.object(dpt.FileOps, "fsync", fsync):
            self.refuse("generator-unreadable", fx.run)
        self.check_failed(fx, "generator-unreadable")

    def test_failed_marker_precedence_and_unexpected_error(self):
        self.fx.run()
        fd = os.open(self.fx.out / dpt.FAILED, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        self.refuse("consumer-failed-marker", dpt._verify_payloads, self.fx.out, self.fx.contract())
        self.refuse("consumer-failed-marker", dpt.verify_remaining_rsw, self.fx.out)
        fx = self.fixture()
        with mock.patch.object(dpt, "build_manifest", side_effect=RuntimeError("x")):
            self.refuse("internal-error", fx.run)
        self.check_failed(fx, "internal-error")


class RemainingRswConsumerTests(RemainingBase):
    def setUp(self):
        super().setUp()
        self.fx.run()
        self.contract = self.fx.contract()

    def verify(self):
        return dpt._verify_payloads(self.fx.out, self.contract)

    def rewrite(self, name, data):
        p = self.fx.out / name
        p.write_bytes(data)
        os.chmod(p, 0o600)

    def rebind(self, manifest, **marker):
        data = dpt.canonical(manifest)
        self.rewrite(dpt.MANIFEST, data)
        fields = {"manifest_bytes": len(data), "manifest_sha256": sha(data),
                  "schema": REM.complete_schema, "status": "complete", "target_count": 17}
        fields.update(marker)
        self.rewrite(dpt.COMPLETE, dpt.canonical(fields))

    def test_marker_and_manifest_substitution(self):
        original = json.loads((self.fx.out / dpt.MANIFEST).read_bytes())
        self.rebind(original)
        self.assertEqual(self.verify()["targets"], 17)

        def rows(fn):
            return lambda m: m.update(targets=fn(m["targets"]))
        for code, fn, marker in (
                ("consumer-marker", None, {"target_count": 1}),
                ("consumer-marker", None, {"target_count": 16}),
                ("consumer-marker", None, {"target_count": 18}),
                ("consumer-marker", None, {"target_count": 17.0}),
                ("consumer-marker", None, {"schema": dpt.COMPLETE_SCHEMA}),
                ("consumer-contract", lambda m: m.update(task=CH1.task), {}),
                ("consumer-contract", lambda m: m.update(schema=dpt.MANIFEST_SCHEMA), {}),
                ("consumer-contract", lambda m: m["profile"].update(path=CH1.profile_path), {}),
                ("consumer-contract", lambda m: m["profile"].update(bytes=CH1.profile_pin[0]), {}),
                ("consumer-contract", lambda m: m["work_limits"].update(CH1.limit_caps), {}),
                ("consumer-contract", lambda m: m["generator"].update(version="1.1.0"), {}),
                ("consumer-contract", lambda m: m.update(contract_kind=dpt.PRODUCTION), {}),
                ("consumer-targets", rows(lambda r: r[:16]), {}),
                ("consumer-targets", rows(lambda r: r + r[-1:]), {}),
                ("consumer-row-contract", rows(lambda r: [r[1], r[0]] + r[2:]), {}),
                ("consumer-row-contract", lambda m: m["targets"][16].update(ordinal=99), {}),
                ("consumer-row-contract", lambda m: m["targets"][16].update(
                    output_file="target-017.body"), {}),
                ("consumer-row-derived", lambda m: m["targets"][8].update(cycle=None), {}),
                ("consumer-usage", lambda m: m["usage"].update(target_count=16), {}),
                ("consumer-body", lambda m: m["targets"][16].update(decoded_sha256="0" * 64),
                 {})):
            with self.subTest(code=code, marker=marker):
                m = json.loads(json.dumps(original))
                if fn:
                    fn(m)
                self.rebind(m, **marker)
                self.refuse(code, self.verify)
        self.rebind(original)
        self.verify()

    def test_mismatched_output_set(self):
        last = self.fx.out / "target-016.body"
        data = last.read_bytes()
        os.rename(last, self.fx.out_parent / "held")
        self.refuse("consumer-file-set", self.verify)
        os.rename(self.fx.out_parent / "held", self.fx.out / "target-017.body")
        self.refuse("consumer-file-set", self.verify)
        os.rename(self.fx.out / "target-017.body", last)
        (self.fx.out / "extra").write_bytes(b"")
        self.refuse("consumer-file-set", self.verify)
        os.unlink(self.fx.out / "extra")
        # Swapping two equal-sized-looking bodies is caught by size/hash.
        a, b = self.fx.out / "target-000.body", self.fx.out / "target-001.body"
        da, db = a.read_bytes(), b.read_bytes()
        self.rewrite("target-000.body", db)
        self.refuse("consumer-size", self.verify)
        self.rewrite("target-000.body", da)
        self.rewrite("target-016.body", data[:-1] + bytes((data[-1] ^ 1,)))
        self.refuse("consumer-body", self.verify)
        self.rewrite("target-016.body", data)
        self.assertEqual(self.verify()["targets"], 17)

    def test_cross_route_outputs(self):
        ch1 = self.fixture(route=CH1)
        ch1.run()
        legacy = self.fixture(route=dpt.LEGACY_ROUTE)
        legacy.run()
        for out in (ch1.out, legacy.out):
            self.refuse("consumer-file-set", dpt._verify_payloads, out, self.contract)
            self.refuse("consumer-file-set", dpt.verify_remaining_rsw, out)
        self.refuse("consumer-file-set", dpt._verify_payloads, self.fx.out, ch1.contract())
        self.refuse("consumer-file-set", dpt._verify_payloads, self.fx.out, legacy.contract())
        # Older routes still pass their own synthetic consumers.
        self.assertEqual(dpt._verify_payloads(ch1.out, ch1.contract())["targets"], 1)
        self.assertEqual(dpt._verify_payloads(legacy.out, legacy.contract())["targets"], 12)


class RemainingRswCliTests(RemainingBase):
    run_main = Chapter1RswCliTests.run_main

    def test_flag_selects_fixed_route_only_after_positionals(self):
        pos = [str(self.fx.source_root), str(self.fx.patch), str(self.fx.out)]
        seen = []

        def capture(source, patch, output, contract):
            seen.append((contract.kind, contract.route, contract.profile_pin))
            raise dpt.Refusal("captured")
        with mock.patch.object(dpt, "_run", capture):
            for argv in (pos + ["--remaining-rsw"], pos + ["--chapter1-rsw"], pos):
                self.assertEqual(self.run_main(argv)[0], 2)
        self.assertEqual(seen, [
            (dpt.PRODUCTION, REM, {"bytes": REM.profile_pin[0], "sha256": REM.profile_pin[1]}),
            (dpt.PRODUCTION, CH1, {"bytes": CH1.profile_pin[0], "sha256": CH1.profile_pin[1]}),
            (dpt.PRODUCTION, dpt.LEGACY_ROUTE, dict(dpt.PROFILE_PIN))])
        for argv in (["--remaining-rsw"] + pos, pos[:2] + ["--remaining-rsw"],
                     pos[:2] + ["--remaining-rsw", pos[2]],
                     pos + ["--remaining-rsw", "--remaining-rsw"],
                     pos + ["--remaining-rsw", "--chapter1-rsw"],
                     pos + ["--chapter1-rsw", "--remaining-rsw"], pos + ["--remaining-rsw=1"],
                     pos + ["--REMAINING-RSW"], pos + ["--remaining"], pos + ["remaining-rsw"],
                     pos + ["--remaining-rsw "], pos + ["--remaining-rsw", "17"],
                     pos + ["--remaining-rsw", "--profile"]):
            with self.subTest(argv=argv[2:]):
                with mock.patch.object(dpt, "_production_contract",
                                       side_effect=AssertionError("contract built")):
                    code, out, err = self.run_main(argv)
                self.assertEqual((code, out), (64, ""))
                self.assertIn('"status": "usage"', err)
        self.assertFalse(os.path.lexists(self.fx.out))

    def test_production_route_refuses_synthetic_inputs_before_output(self):
        code, out, err = self.run_main([str(self.fx.source_root), str(self.fx.patch),
                                        str(self.fx.out), "--remaining-rsw"])
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(json.loads(err), {"status": "refused", "reason": "source-pin"})
        self.assertNotIn(self.tmp.name, err)
        self.assertFalse(os.path.lexists(self.fx.out))


@unittest.skipUnless(os.environ.get("PATCH_DECODER_SOURCE_ROOT")
                     and os.environ.get("PATCH_DECODER_PATCH"), "admitted inputs not supplied")
class AdmittedPatchTest(unittest.TestCase):
    def test_real_patch(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.chmod(tmp, 0o700)
            out = Path(tmp) / "run"
            code = dpt.main([os.environ["PATCH_DECODER_SOURCE_ROOT"],
                             os.environ["PATCH_DECODER_PATCH"], str(out)])
            self.assertEqual(code, 0)
            self.assertEqual(dpt.verify_payloads(out)["decoded_bytes"], 30443934)


if __name__ == "__main__":
    unittest.main()
