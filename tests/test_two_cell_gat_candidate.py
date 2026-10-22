#!/usr/bin/env python3
"""Authored controls for two_cell_gat_candidate (T07.007.013.002).

Retains the T07.007.013.001 A01..A09 regressions (minus its two close-fault
tests, superseded by C02/C03) and adds finite close-policy controls C01..C06.
Only the owned module, the standard library and authored synthetic fixtures
run here; no real game body, acquired source, network or native action.

* PRIVATE-LAYOUT positives call ``_normalize_layout`` (no hash admission).
* PUBLIC negatives call the unmodified ``normalize_bytes`` and expect the fixed
  SHA refusal; no digest is ever mocked.
* WRITER-UNIT controls replace only the ``normalize_bytes`` return with a
  fixture-tagged stub; the actual-input receipt is never produced.
* LEDGER-UNIT controls drive the private ledger with a fake close on
  non-descriptor integers; they are not writer attempts.

Uncertainty-producing writer cases (C02 x6 incl. C06, C03, C04, C05) never run
in the ordinary suite. Each is selected alone by TWO_CELL_CASE=<id> in a fresh
interpreter, is that interpreter's only and last writer attempt, measures the
live residual before and at exit, and performs NO harness close or repair.
Retirement of that interpreter must be observed by Root's separately bound
caller; this file implements no process supervision.

Fixtures live only under the pre-created private 0700 base
.tools/renewal/t07-007-013-002-claude-a1-fixture-1 (no temp fallback).

Run: /usr/bin/python3 -I -B tests/test_two_cell_gat_candidate.py -v
Case: TWO_CELL_CASE=C02_source /usr/bin/python3 -I -B tests/test_two_cell_gat_candidate.py
"""

import atexit
import ast
import errno
import hashlib
import importlib.util
import inspect
import json
import os
import pathlib
import resource
import stat
import struct
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
MODULE_PATH = os.path.join(REPO, "tools", "renewal", "two_cell_gat_candidate.py")
BASE = os.path.join(REPO, ".tools", "renewal",
                    "t07-007-013-002-claude-a1-fixture-1")
AUTHORED_CAP = 33554432
CASE = os.environ.get("TWO_CELL_CASE")
CASE_IDS = ("C02_source", "C02_directory", "C02_binary_write",
            "C02_binary_readback", "C02_receipt_write", "C02_receipt_readback",
            "C03_after_close", "C04_same_fd_sentinel", "C05_primary_two_cleanup")

_spec = importlib.util.spec_from_file_location("two_cell_gat_candidate", MODULE_PATH)
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)
ROLES = m.ROLES

# Count writer attempts so an uncertainty case can prove it is the first,
# only and last attempt in its interpreter. Behaviour is unchanged.
_REAL_WRITE = m.write_candidate
ATTEMPTS = {"n": 0, "sealed": False}


def _counted_write(source_path, output_dir):
    if ATTEMPTS["sealed"]:
        raise RuntimeError("writer sealed after uncertainty case")
    ATTEMPTS["n"] += 1
    return _REAL_WRITE(source_path, output_dir)


m.write_candidate = _counted_write

N = 3200014
T1, T2 = 1667570, 1810170
KNOWN = list(range(7)) + [0x80000000 + k for k in range(10)]
UNKNOWN = [0xFFFFFFFF, 0x40000002, 0x40000007, 0x40000100, 0xC0000000]
# Neighbors of both targets first, then far cells.
SPECIAL_INDEXES = [83376, 83378, 82977, 83777, 90506, 90508, 90107, 90907,
                   0, 1, 399, 400, 79999, 80000, 120000, 120001, 159599,
                   159600, 159998, 159999, 42, 4242]
ORIG = {}
FIX = {}
STATS = {"peak_authored_bytes": 0}


def module_text():
    with open(MODULE_PATH) as fh:
        return fh.read()


def type_offset(index):
    return 14 + index * 20 + 16


def build_fixture():
    buf = bytearray(N)
    buf[0:4] = b"GRAT"
    buf[4:6] = b"\x01\x03"
    struct.pack_into("<II", buf, 6, 400, 400)
    for i in range(160000):
        o = 14 + i * 20
        struct.pack_into("<IIIII", buf, o, i, i ^ 0x5A5A5A5A,
                         (~i) & 0xFFFFFFFF, (i * 2654435761) & 0xFFFFFFFF,
                         0)
    for index, word in zip(SPECIAL_INDEXES, KNOWN + UNKNOWN):
        struct.pack_into("<I", buf, type_offset(index), word)
    struct.pack_into("<I", buf, T1, 0x40000000)
    struct.pack_into("<I", buf, T2, 0x40000001)
    return bytes(buf)


def authored_bytes():
    total = 0
    for root, _, files in os.walk(BASE):
        for f in files:
            total += os.lstat(os.path.join(root, f)).st_size
    STATS["peak_authored_bytes"] = max(STATS["peak_authored_bytes"], total)
    return total


def open_fds():
    return len(os.listdir("/dev/fd"))


def write_exclusive(path, payload, mode):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(payload)
    os.chmod(path, mode)


def setUpModule():
    st = os.lstat(BASE)
    if not stat.S_ISDIR(st.st_mode) or stat.S_IMODE(st.st_mode) != 0o700:
        raise RuntimeError("private fixture base must be a 0700 directory")
    if CASE is not None and CASE not in CASE_IDS:
        raise RuntimeError("unknown TWO_CELL_CASE")
    if authored_bytes() + 2 * N + 65536 > AUTHORED_CAP:
        raise RuntimeError("authored-file cap would be exceeded")
    ORIG["run"] = pathlib.Path(tempfile.mkdtemp(prefix="run-", dir=BASE))
    data = build_fixture()
    FIX["data"] = data
    FIX["out"] = m._normalize_layout(data)
    FIX["src_sha"] = hashlib.sha256(data).hexdigest()
    if CASE is None:
        src = ORIG["run"] / "source.gat"
        write_exclusive(src, data, 0o400)
    else:
        # Case interpreters share one read-only source to stay within the
        # authored-file cap; it is verified, never modified.
        src = pathlib.Path(BASE) / "uncertainty-source.gat"
        if not os.path.lexists(src):
            write_exclusive(src, data, 0o400)
        sst = os.lstat(src)
        if (not stat.S_ISREG(sst.st_mode) or sst.st_nlink != 1
                or stat.S_IMODE(sst.st_mode) != 0o400):
            raise RuntimeError("shared source shape")
        with open(src, "rb") as fh:
            if hashlib.sha256(fh.read()).hexdigest() != FIX["src_sha"]:
                raise RuntimeError("shared source bytes")
    FIX["src"] = src


def tearDownModule():
    authored_bytes()
    if CASE is None:
        # Passing ordinary runs leave no artifacts; case runs keep evidence.
        for root, dirs, files in os.walk(ORIG["run"], topdown=False):
            for f in files:
                os.unlink(os.path.join(root, f))
            for d in dirs:
                os.rmdir(os.path.join(root, d))
        os.rmdir(ORIG["run"])
    usage = resource.getrusage(resource.RUSAGE_SELF)
    sys.stderr.write("OBS peak_authored_bytes=%d ru_maxrss=%d\n"
                     % (STATS["peak_authored_bytes"], usage.ru_maxrss))


def load_tests(loader, tests, pattern):
    if CASE is None:
        return tests
    return unittest.TestSuite([UncertaintyCases("test_" + CASE)])


def fixture_stub(note=None, receipt=None):
    """Writer-unit stub: fixture-tagged return only, never digest admission."""
    def stub(data):
        out = m._normalize_layout(data)
        r = receipt if receipt is not None else {
            "schema": m.FIXTURE_STUB_SCHEMA,
            "status": m.FIXTURE_STUB_STATUS,
            "fixture_only": True,
            "candidate": {"bytes": len(out),
                          "sha256": hashlib.sha256(out).hexdigest()},
        }
        if note is not None:
            r = dict(r, note=note)
        return out, r
    return stub


class Patch:
    def __init__(self, **values):
        self.values = values

    def __enter__(self):
        self.saved = {k: getattr(m, k) for k in self.values}
        for k, v in self.values.items():
            setattr(m, k, v)

    def __exit__(self, *exc):
        for k, v in self.saved.items():
            setattr(m, k, v)


class Base(unittest.TestCase):
    def setUp(self):
        if CASE is not None:
            self.skipTest("uncertainty case interpreter")
        self.fds = open_fds()
        self.src_ident = m._identity(os.lstat(FIX["src"]))
        self.dir = pathlib.Path(tempfile.mkdtemp(prefix="case-", dir=ORIG["run"]))
        self.out = self.dir / "out"

    def tearDown(self):
        authored_bytes()
        self.assertEqual(open_fds(), self.fds, "descriptor leak")
        for root, dirs, files in os.walk(self.dir, topdown=False):
            for f in files:
                os.unlink(os.path.join(root, f))
            for d in dirs:
                p = os.path.join(root, d)
                (os.unlink if os.path.islink(p) else os.rmdir)(p)
        os.rmdir(self.dir)

    def assert_source_untouched(self):
        st = os.lstat(FIX["src"])
        self.assertEqual(m._identity(st), self.src_ident)
        with open(FIX["src"], "rb") as fh:
            self.assertEqual(hashlib.sha256(fh.read()).hexdigest(), FIX["src_sha"])

    def refuse(self, code, src=None, out=None, **patches):
        patches.setdefault("normalize_bytes", fixture_stub())
        with Patch(**patches):
            with self.assertRaises(m.CandidateError) as cm:
                m.write_candidate(src or FIX["src"], out or self.out)
        self.assertEqual(cm.exception.code, code)
        self.assert_source_untouched()

    def write_ok(self, **patches):
        patches.setdefault("normalize_bytes", fixture_stub())
        with Patch(**patches):
            result = m.write_candidate(FIX["src"], self.out)
        self.assert_source_untouched()
        return result


class A01PrivateLayout(unittest.TestCase):
    def test_private_positive_and_public_rejects(self):
        data, out = FIX["data"], FIX["out"]
        self.assertIsNot(out, data)
        self.assertIs(type(out), bytes)
        diff = [i for i in range(N) if data[i] != out[i]]
        self.assertEqual(diff, [1667573, 1810173])
        self.assertEqual([(data[i], out[i]) for i in diff], [(0x40, 0), (0x40, 0)])
        self.assertEqual(struct.unpack_from("<I", out, T1)[0], 0)
        self.assertEqual(struct.unpack_from("<I", out, T2)[0], 1)
        with self.assertRaises(m.CandidateError) as cm:
            m.normalize_bytes(data)
        self.assertEqual(cm.exception.code, "input_sha256_mismatch")

    def test_cell_constants_match_formula(self):
        for c in m.CELLS:
            self.assertEqual(c["index"], c["y"] * 400 + c["x"])
            self.assertEqual(c["type_word_offset"], type_offset(c["index"]))
            self.assertEqual(c["type_word_offset"], 14 + c["decoded_float_flag_slot"] * 4)
            self.assertEqual(c["differing_byte_offset"], c["type_word_offset"] + 3)
            self.assertEqual(struct.pack("<I", c["original_uint32"]).hex(), c["original_le_hex"])
            self.assertEqual(struct.pack("<I", c["candidate_uint32"]).hex(), c["candidate_le_hex"])
        self.assertNotIn(10, [c["candidate_uint32"] for c in m.CELLS])


class A02NontargetWords(unittest.TestCase):
    def test_known_and_unknown_words_preserved(self):
        data, out = FIX["data"], FIX["out"]
        for index, word in zip(SPECIAL_INDEXES, KNOWN + UNKNOWN):
            o = type_offset(index)
            self.assertEqual(struct.unpack_from("<I", out, o)[0], word)
            self.assertEqual(out[o:o + 4], data[o:o + 4])
        self.assertEqual(len(KNOWN), 17)


class A03Inverse(unittest.TestCase):
    def test_whole_word_inverse_and_preservation(self):
        data, out = FIX["data"], FIX["out"]
        inv = bytearray(out)
        inv[T1:T1 + 4] = data[T1:T1 + 4]
        inv[T2:T2 + 4] = data[T2:T2 + 4]
        self.assertEqual(bytes(inv), data)
        self.assertEqual(out[:14], data[:14])
        self.assertEqual(out[4:6], b"\x01\x03")
        for i in range(160000):
            o = 14 + i * 20
            if out[o:o + 16] != data[o:o + 16]:
                self.fail("height bytes changed at %d" % i)
        addressed = list(range(T1, T1 + 4)) + list(range(T2, T2 + 4))
        self.assertEqual(len(addressed), 8)
        self.assertEqual(sum(data[i] != out[i] for i in addressed), 2)


class A04Rejections(unittest.TestCase):
    def private_rejects(self, data, code):
        with self.assertRaises(m.CandidateError) as cm:
            m._normalize_layout(data)
        self.assertEqual(cm.exception.code, code)

    def test_lengths(self):
        d = FIX["data"]
        for bad in (d[:-1], d + b"\0", b""):
            self.private_rejects(bad, "input_length")
            with self.assertRaises(m.CandidateError) as cm:
                m.normalize_bytes(bad)
            self.assertEqual(cm.exception.code, "input_length")

    def test_header_and_targets(self):
        d = FIX["data"]
        cases = [
            (b"GRAX" + d[4:], "input_magic"),
            (d[:6] + struct.pack("<I", 401) + d[10:], "input_dimensions"),
            (d[:10] + struct.pack("<I", 399) + d[14:], "input_dimensions"),
        ]
        o1 = d[T1:T1 + 4]
        o2 = d[T2:T2 + 4]
        swapped = bytearray(d)
        swapped[T1:T1 + 4], swapped[T2:T2 + 4] = o2, o1
        cases.append((bytes(swapped), "input_target_word"))
        cases.append((FIX["out"], "input_target_word"))
        for off, word in ((T1, 0), (T1, 0x40000001), (T2, 0x40000000), (T2, 1),
                          (T1, 10), (T2, 0xFFFFFFFF)):
            b = bytearray(d)
            struct.pack_into("<I", b, off, word)
            cases.append((bytes(b), "input_target_word"))
        for bad, code in cases:
            self.private_rejects(bad, code)
            with self.assertRaises(m.CandidateError) as cm:
                m.normalize_bytes(bad)
            self.assertEqual(cm.exception.code, "input_sha256_mismatch")

    def test_buffer_types_rejected_without_mutation(self):
        for kind in (bytearray, memoryview):
            src = bytearray(FIX["data"])
            arg = kind(src)
            for fn in (m.normalize_bytes, m._normalize_layout):
                with self.assertRaises(TypeError):
                    fn(arg)
            self.assertEqual(bytes(src), FIX["data"])

    def test_public_one_byte_corruption_anywhere(self):
        d = FIX["data"]
        for off in (0, 5, 6, 14, 29, T1 - 1, T1 + 3, T2, 2000000, N - 1):
            b = bytearray(d)
            b[off] ^= 0x01
            with self.assertRaises(m.CandidateError) as cm:
                m.normalize_bytes(bytes(b))
            self.assertEqual(cm.exception.code, "input_sha256_mismatch")

    def test_private_ignores_height_semantics(self):
        b = bytearray(FIX["data"])
        b[14:30] = b"\xff\xff\xc0\x7f" * 4  # NaN floats stay raw bytes.
        out = m._normalize_layout(bytes(b))
        self.assertEqual(out[14:30], bytes(b[14:30]))

    def test_no_override_surface(self):
        self.assertEqual(list(inspect.signature(m.normalize_bytes).parameters), ["data"])
        self.assertEqual(list(inspect.signature(m._normalize_layout).parameters), ["data"])
        self.assertEqual(list(inspect.signature(_REAL_WRITE).parameters),
                         ["source_path", "output_dir"])
        self.assertEqual(m.EXPECTED_SHA256,
                         "758ceb1b32e059c9e70bcc55ce917c630b4d67d25b73ec677167af27a3a35ed5")


class A05SourceAdmission(Base):
    def small(self, name, mode, size=8):
        p = self.dir / name
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.write(fd, b"\0" * size)
        os.close(fd)
        os.chmod(p, mode)
        return p

    def test_short_reads_succeed(self):
        def short_read(fd, n):
            return os.read(fd, min(n, 65521))
        self.write_ok(_read=short_read)
        self.assertEqual((self.out / m.BINARY_NAME).read_bytes(), FIX["out"])

    def test_growth_extra_byte(self):
        state = {"eof": False}

        def grow(fd, n):
            chunk = os.read(fd, n)
            if not chunk and not state["eof"]:
                state["eof"] = True
                return b"\0"
            return chunk
        self.refuse("read_exceeds_limit", _read=grow)
        self.assertFalse(os.path.lexists(self.out))

    def test_early_eof(self):
        state = {"n": 0}

        def early(fd, n):
            state["n"] += 1
            return os.read(fd, n) if state["n"] == 1 else b""
        self.refuse("source_eof", _read=lambda fd, n: early(fd, min(n, 4096)))
        self.assertFalse(os.path.lexists(self.out))

    def test_read_failure(self):
        state = {"n": 0}

        def fail(fd, n):
            state["n"] += 1
            if state["n"] == 2:
                raise OSError(errno.EIO, "injected")
            return os.read(fd, n)
        self.refuse("source_read", _read=fail)
        self.assertFalse(os.path.lexists(self.out))

    def test_identity_change_during_read(self):
        def touch(fd, n):
            chunk = os.read(fd, n)
            st = os.fstat(fd)
            os.utime(FIX["src"], ns=(st.st_atime_ns, st.st_mtime_ns + 1000))
            return chunk
        with self.assertRaises(m.CandidateError) as cm:
            with Patch(_read=touch, normalize_bytes=fixture_stub()):
                m.write_candidate(FIX["src"], self.out)
        self.assertEqual(cm.exception.code, "source_identity_after")
        self.assertFalse(os.path.lexists(self.out))
        with open(FIX["src"], "rb") as fh:
            self.assertEqual(hashlib.sha256(fh.read()).hexdigest(), FIX["src_sha"])

    def test_path_swap_after_open(self):
        aside = self.dir / "aside"

        def swap(path, flags, *a, **k):
            fd = os.open(path, flags, *a, **k)
            os.rename(FIX["src"], aside)
            self.small("swap", 0o400)
            os.rename(self.dir / "swap", FIX["src"])
            return fd
        try:
            with self.assertRaises(m.CandidateError) as cm:
                with Patch(_open=swap, normalize_bytes=fixture_stub()):
                    m.write_candidate(FIX["src"], self.out)
        finally:
            os.rename(aside, FIX["src"])
        # APFS rename may update ctime, so the swap is caught at the first
        # identity comparison that observes it.
        self.assertIn(cm.exception.code, ("source_identity_opened",
                                          "source_identity_after",
                                          "source_identity_path"))
        self.assertFalse(os.path.lexists(self.out))
        self.src_ident = m._identity(os.lstat(FIX["src"]))
        self.assert_source_untouched()

    def test_shape_and_mode_rejections(self):
        d = self.dir / "dir"
        os.mkdir(d, 0o700)
        self.refuse("source_not_regular", src=d)
        link = self.dir / "link"
        os.symlink(FIX["src"], link)
        self.refuse("source_symlink", src=link)
        for mode in (0o644, 0o640, 0o604, 0o700, 0o444, 0o200):
            self.refuse("source_mode", src=self.small("m%o" % mode, mode))
        self.refuse("source_size", src=self.small("short", 0o400))
        hard = self.dir / "hard"
        os.link(FIX["src"], hard)
        try:
            self.src_ident = m._identity(os.lstat(FIX["src"]))
            self.refuse("source_link_count")
        finally:
            os.unlink(hard)
        self.src_ident = m._identity(os.lstat(FIX["src"]))
        self.assertFalse(os.path.lexists(self.out))


class A06Output(Base):
    def test_fresh_private_output(self):
        result = self.write_ok()
        self.assertEqual(result["schema"], m.FIXTURE_STUB_SCHEMA)
        self.assertTrue(result["fixture_only"])
        st = os.lstat(self.out)
        self.assertEqual(stat.S_IMODE(st.st_mode), 0o700)
        self.assertEqual(sorted(os.listdir(self.out)), sorted([m.BINARY_NAME, m.RECEIPT_NAME]))
        for name in os.listdir(self.out):
            fst = os.lstat(self.out / name)
            self.assertTrue(stat.S_ISREG(fst.st_mode))
            self.assertEqual(stat.S_IMODE(fst.st_mode), 0o600)
        self.assertEqual((self.out / m.BINARY_NAME).read_bytes(), FIX["out"])
        raw = (self.out / m.RECEIPT_NAME).read_bytes()
        self.assertLessEqual(len(raw), 16384)
        self.assertNotIn(b"\n", raw)
        self.assertEqual(json.loads(raw), result)

    def test_preexisting_targets_preserved(self):
        os.mkdir(self.out, 0o700)
        self.refuse("output_exists")
        os.rmdir(self.out)
        self.out.write_bytes(b"prior")
        os.chmod(self.out, 0o640)
        self.refuse("output_exists")
        self.assertEqual(self.out.read_bytes(), b"prior")
        self.assertEqual(stat.S_IMODE(os.lstat(self.out).st_mode), 0o640)
        os.unlink(self.out)
        target = self.dir / "elsewhere"
        os.symlink(target, self.out)
        self.refuse("output_exists")
        self.assertTrue(os.path.islink(self.out))
        self.assertFalse(os.path.lexists(target))

    def test_nonprivate_parent(self):
        parent = self.dir / "open"
        os.mkdir(parent, 0o755)
        self.refuse("output_parent", out=parent / "out")
        self.assertEqual(os.listdir(parent), [])

    def collide(self, name):
        def opener(path, flags, *a, **k):
            if path == name and flags & os.O_CREAT:
                pre = os.open(path, os.O_WRONLY | os.O_CREAT, 0o640, dir_fd=k["dir_fd"])
                os.write(pre, b"planted")
                os.close(pre)
            return os.open(path, flags, *a, **k)
        return opener

    def test_injected_binary_collision(self):
        self.refuse("output_collision", _open=self.collide(m.BINARY_NAME))
        self.assertEqual((self.out / m.BINARY_NAME).read_bytes(), b"planted")
        self.assertEqual(stat.S_IMODE(os.lstat(self.out / m.BINARY_NAME).st_mode), 0o640)
        self.assertFalse((self.out / m.RECEIPT_NAME).exists())

    def test_injected_receipt_collision(self):
        self.refuse("output_collision", _open=self.collide(m.RECEIPT_NAME))
        self.assertEqual((self.out / m.RECEIPT_NAME).read_bytes(), b"planted")
        self.assertEqual((self.out / m.BINARY_NAME).read_bytes(), FIX["out"])

    def test_no_umask_or_settings_calls(self):
        tree = ast.parse(module_text())
        names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)
                 and isinstance(n.value, ast.Name) and n.value.id == "os"}
        for bad in ("umask", "environ", "putenv", "system", "popen", "remove",
                    "unlink", "rmdir", "rename", "replace", "truncate"):
            self.assertNotIn(bad, names)


class A07WriteFaults(Base):
    def fail_write(self, fn, code="write_progress"):
        self.refuse(code, _write=fn)
        self.assertTrue(os.path.isdir(self.out))

    def test_short_positive_writes(self):
        self.write_ok(_write=lambda fd, b: os.write(fd, b[:4097]))
        self.assertEqual((self.out / m.BINARY_NAME).read_bytes(), FIX["out"])

    def test_bad_progress(self):
        for fake in (lambda fd, b: 0, lambda fd, b: -1, lambda fd, b: len(b) + 1,
                     lambda fd, b: True, lambda fd, b: 1.0):
            self.fail_write(fake)
            self.assertEqual(os.listdir(self.out), [m.BINARY_NAME])
            os.unlink(self.out / m.BINARY_NAME)
            os.rmdir(self.out)

    def test_overreport_after_partial(self):
        # An in-bounds overreport cannot be seen by progress accounting; the
        # full readback comparison must refuse it before any receipt.
        def fake(fd, b):
            os.write(fd, b[:10])
            return 11 if len(b) > 1000 else os.write(fd, b[10:]) + 10
        self.fail_write(fake, "readback_mismatch")
        self.assertNotEqual((self.out / m.BINARY_NAME).read_bytes(), FIX["out"])
        self.assertFalse((self.out / m.RECEIPT_NAME).exists())

    def stage_fault(self, attr, nth, code="output_error"):
        # Non-close action faults only: every acquisition still closes.
        real = getattr(m, attr)
        state = {"n": 0, "err": None}

        def fake(*a, **k):
            state["n"] += 1
            if state["n"] == nth:
                state["err"] = OSError(errno.EIO, "injected")
                raise state["err"]
            return real(*a, **k)
        patches = {attr: fake, "normalize_bytes": fixture_stub()}
        with Patch(**patches):
            with self.assertRaises(m.CandidateIOError) as cm:
                m.write_candidate(FIX["src"], self.out)
        exc = cm.exception
        self.assertEqual(exc.code, code)
        self.assertIs(exc.primary_error, state["err"])
        self.assertIs(exc.__cause__, state["err"])
        self.assertEqual(exc.close_errors, ())
        self.assertTrue(all(o.state == "closed" and o.close_attempts == 1
                            for o in exc.ownership))
        self.assert_source_untouched()
        return exc

    def test_fsync_faults(self):
        self.stage_fault("_fsync", 1)
        self.assertEqual((self.out / m.BINARY_NAME).read_bytes(), FIX["out"])
        self.assertFalse((self.out / m.RECEIPT_NAME).exists())

    def test_receipt_fsync_and_dir_fsync_faults(self):
        for nth in (2, 3):
            self.stage_fault("_fsync", nth)
            self.assertEqual((self.out / m.BINARY_NAME).read_bytes(), FIX["out"])
            self.assertTrue((self.out / m.RECEIPT_NAME).exists())
            for name in os.listdir(self.out):
                os.unlink(self.out / name)
            os.rmdir(self.out)

    def test_binary_readback_corruption(self):
        real = os.read
        state = {"n": 0}

        def fake(fd, n):
            chunk = real(fd, n)
            state["n"] += 1
            if state["n"] == 6 and chunk:
                return b"\x00" + chunk[1:]
            return chunk
        # Reads: source chunks 1..4 (1 MiB each), EOF 5, then binary readback.
        self.refuse("readback_mismatch", _read=fake)
        self.assertEqual((self.out / m.BINARY_NAME).read_bytes(), FIX["out"])
        self.assertFalse((self.out / m.RECEIPT_NAME).exists())

    def test_readback_read_error(self):
        self.stage_fault("_read", 6)
        self.assertTrue((self.out / m.BINARY_NAME).exists())
        self.assertFalse((self.out / m.RECEIPT_NAME).exists())


class A08WriterFixtureStub(Base):
    def test_stub_positive_is_not_actual_admission(self):
        result = self.write_ok()
        self.assertEqual(result["status"], m.FIXTURE_STUB_STATUS)
        self.assertNotEqual(result.get("schema"), m.SCHEMA)
        self.assertNotIn("input", result)
        self.assertEqual(result["candidate"]["sha256"], hashlib.sha256(FIX["out"]).hexdigest())

    def test_unstubbed_writer_rejects_fixture_by_sha(self):
        with self.assertRaises(m.CandidateError) as cm:
            m.write_candidate(FIX["src"], self.out)
        self.assertEqual(cm.exception.code, "input_sha256_mismatch")
        self.assertFalse(os.path.lexists(self.out))
        self.assert_source_untouched()

    def test_real_schema_cannot_be_promoted(self):
        out = FIX["out"]
        real = m._build_receipt("0103", hashlib.sha256(out).hexdigest())
        m._validate_real_receipt(real)
        self.refuse("input_sha256_mismatch", normalize_bytes=lambda d: (out, real))
        self.assertFalse(os.path.lexists(self.out))

    def test_real_receipt_closed_validation(self):
        good = m._build_receipt("0103", "a" * 64)
        m._validate_real_receipt(good)
        raw = m._encode_receipt(good)
        self.assertLessEqual(len(raw), 16384)
        self.assertEqual(m._decode_receipt(raw), good)
        bad = []
        for path, value in ((("policy", "bit30_meaning_known"), 0),
                            (("change_audit", "differing_bytes"), 8),
                            (("format", "version_hex"), "01033"),
                            (("candidate", "sha256"), "A" * 64),
                            (("input", "sha256"), "0" * 64)):
            r = json.loads(json.dumps(good))
            r[path[0]][path[1]] = value
            bad.append(r)
        r = json.loads(json.dumps(good))
        r["cells"][0]["candidate_uint32"] = 10
        bad.append(r)
        r = json.loads(json.dumps(good))
        r["extra"] = 1
        bad.append(r)
        r = json.loads(json.dumps(good))
        r["cells"].reverse()
        bad.append(r)
        for r in bad:
            with self.assertRaises(m.CandidateError):
                m._validate_real_receipt(r)
        for text in (b'{"a":1,"a":1}', b'{"a":NaN}', b'{"a": 1}', b'{"a":1}\n'):
            with self.assertRaises(m.CandidateError):
                m._decode_receipt(text)


class A09RepeatAndReceipt(Base):
    def test_repeated_attempt_refused(self):
        self.write_ok()
        before = {n: (self.out / n).read_bytes() for n in os.listdir(self.out)}
        self.refuse("output_exists")
        self.assertEqual({n: (self.out / n).read_bytes() for n in os.listdir(self.out)}, before)

    def test_invalid_receipts_refused_before_output(self):
        cases = [
            (fixture_stub(note=float("nan")), "receipt_not_strict_json"),
            (fixture_stub(note="x" * 16384), "receipt_oversize"),
            (fixture_stub(receipt={"schema": "anything", "candidate": {}}),
             "receipt_candidate_mismatch"),
        ]
        out = FIX["out"]
        cand = {"bytes": N, "sha256": hashlib.sha256(out).hexdigest()}
        cases.append((lambda d: (out, {"schema": "anything", "candidate": cand}),
                      "receipt_schema"))
        cases.append((lambda d: (out, {"schema": m.FIXTURE_STUB_SCHEMA,
                                       "status": m.FIXTURE_STUB_STATUS,
                                       "fixture_only": 1, "candidate": cand}),
                      "receipt_fixture_tag"))
        cases.append((lambda d: (out[:-1], {}), "candidate_length"))
        cases.append((lambda d: (FIX["data"], {"schema": m.FIXTURE_STUB_SCHEMA,
                                               "status": m.FIXTURE_STUB_STATUS,
                                               "fixture_only": True,
                                               "candidate": {"bytes": N, "sha256": FIX["src_sha"]}}),
                      "audit_candidate_words"))
        for stub, code in cases:
            self.refuse(code, normalize_bytes=stub)
            self.assertFalse(os.path.lexists(self.out))

    def test_import_is_inert(self):
        probe = self.dir / "probe"
        os.mkdir(probe, 0o700)
        code = ("import importlib.util,sys;s=importlib.util.spec_from_file_location"
                "('c',sys.argv[1]);mod=importlib.util.module_from_spec(s);"
                "s.loader.exec_module(mod)")
        proc = subprocess.run([sys.executable, "-I", "-B", "-c", code, MODULE_PATH],
                              cwd=probe, capture_output=True, timeout=30)
        self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (0, b"", b""))
        self.assertEqual(os.listdir(probe), [])
        tree = ast.parse(module_text())
        allowed = (ast.Import, ast.ImportFrom, ast.Assign, ast.FunctionDef,
                   ast.ClassDef, ast.Expr)
        for node in tree.body:
            self.assertIsInstance(node, allowed)
            if isinstance(node, ast.Expr):
                self.assertIsInstance(node.value, ast.Constant)
        imports = {a.name for n in tree.body if isinstance(n, ast.Import) for a in n.names}
        self.assertEqual(imports, {"hashlib", "json", "os", "pathlib", "stat", "struct"})
        self.assertNotIn("__main__", module_text())



class Recorder:
    """Harness view of writer opens/closes with optional injected faults.

    faults maps generation -> (mode, errno); mode "before" raises without a
    real close, "after" really closes then raises, "sentinel" really closes,
    reopens the same file as a harness sentinel, then raises. The harness
    never closes a writer descriptor itself.
    """

    def __init__(self, faults=None, sentinel_path=None):
        self.faults = faults or {}
        self.sentinel_path = sentinel_path
        self.gens = []
        self.closes = []
        self.hits = []
        self.sentinel = None
        self.ebadf_after_close = None

    def open(self, path, flags, *a, **k):
        fd = os.open(path, flags, *a, **k)
        st = os.fstat(fd)
        self.gens.append({"gen": len(self.gens) + 1, "fd": fd,
                          "identity": (st.st_dev, st.st_ino), "live": True,
                          "close_calls": 0, "real_close_calls": 0})
        return fd

    def close(self, fd):
        live = [g for g in self.gens if g["fd"] == fd and g["live"]]
        self.closes.append((fd, live[-1]["gen"] if live else None))
        if not live:
            raise AssertionError("close of unknown/foreign fd %d" % fd)
        g = live[-1]
        g["close_calls"] += 1
        mode, err = self.faults.get(g["gen"], (None, None))
        if mode != "before":
            os.close(fd)
            g["real_close_calls"] += 1
            g["live"] = False
        if mode is None:
            return None
        self.hits.append((g["gen"], mode))
        if mode == "after":
            try:
                os.fstat(fd)
            except OSError as exc:
                self.ebadf_after_close = exc.errno == errno.EBADF
        elif mode == "sentinel":
            sfd = os.open(self.sentinel_path, os.O_RDONLY | os.O_CLOEXEC)
            st = os.fstat(sfd)
            self.sentinel = {"fd": sfd, "same_fd": sfd == fd,
                             "identity": (st.st_dev, st.st_ino),
                             "same_identity": (st.st_dev, st.st_ino)
                             == g["identity"],
                             "closes_before": len(self.closes)}
        raise OSError(err, "injected %s close fault" % mode)

    def residual(self):
        """Read-only check of every writer generation not really closed."""
        out = []
        for g in self.gens:
            if g["live"]:
                try:
                    st = os.fstat(g["fd"])
                    same = (st.st_dev, st.st_ino) == g["identity"]
                except OSError:
                    same = False
                out.append({"gen": g["gen"], "fd": g["fd"], "live": same})
        return out


def expected_receipt(version_hex, candidate_sha):
    """Independent transcription of the frozen closed success receipt."""
    cells = [
        {"index": 83377, "x": 177, "y": 208, "decoded_float_flag_slot": 416889,
         "type_word_offset": 1667570, "original_uint32": 1073741824,
         "original_le_hex": "00000040", "candidate_uint32": 0,
         "candidate_le_hex": "00000000", "predicted_client_mask": 10,
         "differing_byte_offset": 1667573},
        {"index": 90507, "x": 107, "y": 226, "decoded_float_flag_slot": 452539,
         "type_word_offset": 1810170, "original_uint32": 1073741825,
         "original_le_hex": "01000040", "candidate_uint32": 1,
         "candidate_le_hex": "01000000", "predicted_client_mask": 1,
         "differing_byte_offset": 1810173},
    ]
    sha = "758ceb1b32e059c9e70bcc55ce917c630b4d67d25b73ec677167af27a3a35ed5"
    return {
        "schema": "root013-two-cell-gat-candidate-1",
        "status": "offline_candidate_hypothesis",
        "input": {"bytes": N, "sha256": sha},
        "candidate": {"bytes": N, "sha256": candidate_sha},
        "format": {"magic": "GRAT", "version_hex": version_hex, "width": 400,
                   "height": 400, "header_bytes": 14, "cell_bytes": 20,
                   "type_word_offset_within_cell": 16, "endian": "little"},
        "cells": cells,
        "change_audit": {"addressed_word_bytes": 8, "differing_bytes": 2,
                         "differing_byte_offsets": [1667573, 1810173],
                         "header_unchanged": True,
                         "all_height_bytes_unchanged": True,
                         "outside_target_words_unchanged": True,
                         "inverse_restores_original": True,
                         "inverse_sha256": sha},
        "policy": {"production_mapping_selected": False,
                   "server_agreement_verified": False,
                   "normal_runtime_verified": False,
                   "bit30_meaning_known": False,
                   "server_cache_generation_permitted": False},
    }


class C01Baseline(Base):
    def test_six_generations_close_once(self):
        with self.assertRaises(m.CandidateError) as cm:
            m.normalize_bytes(FIX["data"])
        self.assertEqual(cm.exception.code, "input_sha256_mismatch")
        rec = Recorder()
        result = self.write_ok(_open=rec.open, _close=rec.close)
        self.assertEqual(len(rec.gens), 6)
        self.assertEqual([c[1] for c in rec.closes], [1, 3, 4, 5, 6, 2])
        for g in rec.gens:
            self.assertEqual((g["close_calls"], g["real_close_calls"],
                              g["live"]), (1, 1, False))
        self.assertEqual(rec.residual(), [])
        self.assertEqual((self.out / m.BINARY_NAME).read_bytes(), FIX["out"])
        self.assertEqual((self.out / m.RECEIPT_NAME).read_bytes(),
                         m._encode_receipt(result))
        exp = expected_receipt("0103", "a" * 64)
        got = m._build_receipt("0103", "a" * 64)
        self.assertTrue(m._strict_equal(got, exp))
        self.assertEqual(json.dumps(got), json.dumps(exp))


class LedgerUnit(unittest.TestCase):
    """Private ledger with a fake close on non-descriptor integers."""

    def ledger(self, fail=()):
        calls = []

        def fake_close(fd):
            calls.append(fd)
            for key, exc in fail:
                if key == fd:
                    raise exc
        return m._Ledger(), calls, fake_close

    def test_tokens_distinct_for_repeated_integer(self):
        led, calls, fake = self.ledger()
        with Patch(_close=fake):
            a = led.acquire("binary_write", -7)
            led.close(a)
            b = led.acquire("binary_readback", -7)
            led.close(b)
        self.assertEqual((a.token, b.token), (1, 2))
        self.assertEqual(led.snapshot(), (
            (1, "binary_write", "closed", 1), (2, "binary_readback", "closed", 1)))
        self.assertEqual(calls, [-7, -7])

    def test_uncertain_never_retried(self):
        err = OSError(errno.EIO, "x")
        led, calls, fake = self.ledger([(-1, err)])
        with Patch(_close=fake):
            a = led.acquire("source", -1)
            with self.assertRaises(OSError) as cm:
                led.close(a)
            self.assertIs(cm.exception, err)
            with self.assertRaises(m.CandidateError) as cm:
                led.close(a)
            self.assertEqual(cm.exception.code, "ledger_close_state")
            led.cleanup()
        self.assertEqual(calls, [-1])
        self.assertEqual(led.close_errors, [(1, "source", "close", err, "unknown")])
        self.assertEqual(led.snapshot(), ((1, "source", "uncertain", 1),))

    def test_cleanup_continues_and_skips_resolved(self):
        e1, e2 = OSError(errno.EIO, "a"), ValueError("b")
        led, calls, fake = self.ledger([(-4, e1), (-2, e2)])
        with Patch(_close=fake):
            recs = [led.acquire(r, -(i + 1)) for i, r in enumerate(ROLES[:5])]
            led.close(recs[0])
            recs[2].state = "closing"  # Interrupted attempt is never retried.
            led.cleanup()
            led.cleanup()
        self.assertEqual(calls, [-1, -5, -4, -2])
        self.assertEqual([(e.acquisition, e.error) for e in led.close_errors],
                         [(4, e1), (2, e2)])
        self.assertEqual([o.state for o in led.snapshot()],
                         ["closed", "uncertain", "closing", "uncertain", "closed"])

    def test_records_immutable_and_error_shape(self):
        err = OSError(errno.EPIPE, "p")
        ce = m.CloseError(2, "directory", err)
        own = m.Ownership(2, "directory", "uncertain", 1)
        for obj, field in ((ce, "error"), (own, "state")):
            with self.assertRaises(AttributeError):
                setattr(obj, field, None)
            with self.assertRaises(AttributeError):
                obj.extra = 1
        self.assertEqual((ce.operation, ce.release_state, ce.error.errno),
                         ("close", "unknown", errno.EPIPE))
        exc = m.CandidateIOError("output_error", err, [ce], [own])
        self.assertIsInstance(exc, m.CandidateError)
        self.assertIs(exc.primary_error, err)
        self.assertIs(exc.__cause__, err)
        self.assertEqual((type(exc.close_errors), type(exc.ownership)),
                         (tuple, tuple))
        self.assertEqual(m.ROLES, ("source", "directory", "binary_write",
                                   "binary_readback", "receipt_write",
                                   "receipt_readback"))

    def test_case_table_is_finite_and_selectable(self):
        self.assertEqual(len(CASE_IDS), 9)
        for cid in CASE_IDS:
            self.assertTrue(callable(getattr(UncertaintyCases, "test_" + cid)))
        src = module_text()
        for bad in ("fstat(rec", "dup", "errno", "__del__", "weakref"):
            self.assertNotIn(bad, src[src.index("class _Ledger"):
                                      src.index("def _check_layout")])


EXPECT = {
    # case id: (injected close faults, acquired generations, output files)
    "C02_source": ({1: ("before", errno.EIO)}, 1, 0),
    "C02_directory": ({2: ("before", errno.EIO)}, 6, 2),
    "C02_binary_write": ({3: ("before", errno.EIO)}, 3, 1),
    "C02_binary_readback": ({4: ("before", errno.EIO)}, 4, 1),
    "C02_receipt_write": ({5: ("before", errno.EIO)}, 5, 2),
    "C02_receipt_readback": ({6: ("before", errno.EIO)}, 6, 2),
    "C03_after_close": ({3: ("after", errno.EIO)}, 3, 1),
    "C04_same_fd_sentinel": ({4: ("sentinel", errno.EIO)}, 4, 1),
    "C05_primary_two_cleanup": ({3: ("before", errno.EIO),
                                 2: ("before", errno.ENOSPC)}, 3, 1),
}


class UncertaintyCases(unittest.TestCase):
    """One writer attempt per fresh interpreter; no harness repair."""

    def run_case(self, cid):
        if CASE != cid:
            self.skipTest("select alone: TWO_CELL_CASE=%s fresh interpreter" % cid)
        self.assertEqual(ATTEMPTS["n"], 0)
        faults, gens, files = EXPECT[cid]
        case_dir = pathlib.Path(tempfile.mkdtemp(prefix=cid + "-",
                                                 dir=ORIG["run"]))
        out = case_dir / "out"
        with self.assertRaises(m.CandidateError) as cm:
            m.normalize_bytes(FIX["data"])
        self.assertEqual(cm.exception.code, "input_sha256_mismatch")
        rec = Recorder(faults, out / m.BINARY_NAME)
        patches = {"_open": rec.open, "_close": rec.close,
                   "normalize_bytes": fixture_stub()}
        primary = []
        if cid.startswith("C05"):
            def epipe(fd, b):
                primary.append(OSError(errno.EPIPE, "injected primary"))
                raise primary[-1]
            patches["_write"] = epipe
        returned, exc = None, None
        with Patch(**patches):
            try:
                returned = m.write_candidate(FIX["src"], out)
            except Exception as e:
                exc = e
        ATTEMPTS["sealed"] = True
        residual = rec.residual()  # Before any other action; nothing repaired.
        listing = sorted(os.listdir(out)) if os.path.isdir(out) else []
        diag = {
            "case": cid, "attempts": ATTEMPTS["n"], "returned": returned is not None,
            "error_type": type(exc).__name__,
            "code": getattr(exc, "code", None),
            "primary": [type(getattr(exc, "primary_error", None)).__name__,
                        getattr(getattr(exc, "primary_error", None), "errno", None)],
            "cause_is_primary": exc is not None and exc.__cause__ is getattr(
                exc, "primary_error", object()),
            "close_errors": [[e.acquisition, e.role, e.operation,
                              type(e.error).__name__, e.error.errno,
                              e.release_state]
                             for e in getattr(exc, "close_errors", ())],
            "ownership": [list(o) for o in getattr(exc, "ownership", ())],
            "fault_hits": rec.hits,
            "generations": [[g["gen"], g["close_calls"], g["real_close_calls"]]
                            for g in rec.gens],
            "close_calls": [c[1] for c in rec.closes],
            "residual_before_exit": residual,
            "ebadf_after_close": rec.ebadf_after_close,
            "sentinel": rec.sentinel and {k: v for k, v in rec.sentinel.items()
                                          if k != "identity"},
            "outputs": [[n, os.lstat(out / n).st_size,
                         oct(stat.S_IMODE(os.lstat(out / n).st_mode))]
                        for n in listing],
            "harness_close_interventions": 0,
            "real_body_read": False, "real_candidate_written": False,
            "fixture_stub_only": True,
        }
        text = json.dumps(diag, sort_keys=True, separators=(",", ":"))
        write_exclusive(case_dir / "DIAGNOSTIC.json", text.encode("ascii"), 0o600)
        sys.stdout.write("DIAG %s\n" % text)
        sys.stdout.flush()

        def pre_exit():
            sys.stdout.write("PRE_EXIT_RESIDUAL %s\n" % json.dumps(
                rec.residual(), sort_keys=True, separators=(",", ":")))
            sys.stdout.flush()
        atexit.register(pre_exit)

        # Assertions: refusal, exact ledger, residual, preservation.
        self.assertIsNone(returned)
        self.assertIsInstance(exc, m.CandidateIOError)
        self.assertEqual(ATTEMPTS["n"], 1)
        self.assertEqual(len(rec.gens), gens)
        self.assertTrue(all(g["close_calls"] == 1 for g in rec.gens))
        self.assertEqual(sorted(h[0] for h in rec.hits), sorted(faults))
        self.assertIs(exc.__cause__, exc.primary_error)
        self.assertNotIn(None, [c[1] for c in rec.closes])
        own = {o.acquisition: o for o in exc.ownership}
        self.assertEqual(sorted(own), list(range(1, gens + 1)))
        for o in exc.ownership:
            self.assertEqual(o.role, ROLES[o.acquisition - 1])
            self.assertEqual(o.close_attempts, 1)
            self.assertEqual(o.state, "uncertain" if o.acquisition in faults
                             else "closed")
        if cid.startswith("C05"):
            self.assertEqual(exc.code, "output_error")
            self.assertIs(exc.primary_error, primary[0])
            self.assertEqual(len(primary), 1)
            self.assertEqual([(e.acquisition, e.role, e.error.errno)
                              for e in exc.close_errors],
                             [(3, "binary_write", errno.EIO),
                              (2, "directory", errno.ENOSPC)])
        else:
            (gen,) = faults
            self.assertEqual(exc.code, "source_close" if gen == 1
                             else "output_close")
            self.assertEqual(exc.close_errors, (
                (gen, ROLES[gen - 1], "close", exc.primary_error, "unknown"),))
            self.assertEqual(exc.primary_error.errno, errno.EIO)
        before = sorted(g for g, (mode, _) in faults.items() if mode == "before")
        self.assertEqual([r["gen"] for r in residual], before)
        self.assertTrue(all(r["live"] for r in residual))
        for g in rec.gens:
            self.assertEqual(g["real_close_calls"], 0 if g["gen"] in before else 1)
        self.assertEqual(len(listing), files)
        if files and not cid.startswith("C05"):
            self.assertEqual((out / m.BINARY_NAME).read_bytes(), FIX["out"])
        if files == 2:
            # C06: both files look complete yet the API failed.
            raw = (out / m.RECEIPT_NAME).read_bytes()
            self.assertEqual(json.loads(raw)["schema"], m.FIXTURE_STUB_SCHEMA)
        if cid.startswith("C05"):  # Empty binary from the failed first write.
            self.assertEqual(os.lstat(out / m.BINARY_NAME).st_size, 0)
        if cid.startswith("C03"):
            self.assertTrue(rec.ebadf_after_close)
        if cid.startswith("C04"):
            sen = rec.sentinel
            if not (sen and sen["same_fd"] and sen["same_identity"]):
                self.skipTest("UNEXERCISED: same-fd/inode reuse not obtained")
            st = os.fstat(sen["fd"])
            self.assertEqual((st.st_dev, st.st_ino), sen["identity"])
            later = [c[0] for c in rec.closes[sen["closes_before"]:]]
            self.assertNotIn(sen["fd"], later)
        with open(FIX["src"], "rb") as fh:
            self.assertEqual(hashlib.sha256(fh.read()).hexdigest(), FIX["src_sha"])


for _cid in CASE_IDS:
    setattr(UncertaintyCases, "test_" + _cid,
            lambda self, _c=_cid: self.run_case(_c))


if __name__ == "__main__":
    unittest.main()
