"""Tests for npc_plaintext_package (T05.006). Six groups, G01-G06.

    T05_006_INPUT_ROOT=<frozen input root> \
        python3 -I -B -m unittest -v tools/renewal/test_npc_plaintext_package.py

G01 and the real-package half of G02/G06 need the frozen read-only input root
(the directory holding frozen-inputs.json); without it they are reported as
skipped, never passed. Everything else runs on tiny authored fixtures under
T05_006_WORK (default: .tools/renewal/T05.006/test-work in this checkout).
The production dictionary is only streamed/hashed/copied here, never decoded.
G06 checks a source-profile model of supported staging (upstream mods.rs,
assets.rs, PluginManager.js); no JS, stock or native staging is executed.
"""

import copy
import errno
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import npc_plaintext_package as pkg  # noqa: E402

GENERATOR = HERE / "npc_plaintext_package.py"
INPUT_ROOT = os.environ.get("T05_006_INPUT_ROOT")
WORK = Path(os.environ.get("T05_006_WORK") or HERE.parent.parent / ".tools/renewal/T05.006/test-work")
FROZEN_SHA = "480d7e5b7edadf59cbb79b9e0be15674e1e48d344b4ce75f91c16c031a6151b5"
PROFILE_SHA = "53f3ea8b754f8604062bedb19a79c71f36b3dea5d6a47c1c39d14b97b5dc98da"
REAL = {
    "loader": "tools/renewal/dictionary_loader.mjs",
    "core": "tools/renewal/npc_plaintext_adapter.mjs",
    "dictionary": ".tools/renewal/translation-source-preparation/source/plugin/npc-live-translate/dict.json",
}
NAME = "npc-plaintext-zh-tw"
FIVE = sorted([
    NAME + "/client/dict.json",
    NAME + "/client/dictionary_loader.mjs",
    NAME + "/client/index.js",
    NAME + "/client/npc_plaintext_adapter.mjs",
    NAME + "/mod.json",
])
ENTRY = b"export { default } from './dictionary_loader.mjs';\n"

FIX_LOADER = b"// fixture loader, not the qualified loader\nexport default function () {}\n"
FIX_CORE = b"// fixture core\nexport default function () {}\n"
FIX_DICT = b'{"fixture": "\xe5\xad\x97\xe5\x85\xb8", "pad": "' + b"x" * 300 + b'"}\n'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def stream_sha(path):
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
            size += len(chunk)
    return size, digest.hexdigest()


def fixture_profile(loader=FIX_LOADER, core=FIX_CORE, dictionary=FIX_DICT):
    profile = copy.deepcopy(pkg.PROFILE)
    for role, data in (("loader", loader), ("core", core), ("dictionary", dictionary)):
        profile["sources"][role]["bytes"] = len(data)
        profile["sources"][role]["sha256"] = sha(data)
    return profile


def open_fds():
    return set(os.listdir("/dev/fd"))


def snapshot(path):
    """Byte/identity snapshot of a source file (dictionary streamed)."""
    st = os.lstat(path)
    return (st.st_ino, st.st_size, st.st_mtime_ns, stream_sha(path))


class Work(unittest.TestCase):
    """Fresh private directory per test; fixture sources written there."""

    def setUp(self):
        WORK.mkdir(parents=True, exist_ok=True)
        self.dir = Path(tempfile.mkdtemp(prefix="t-", dir=os.path.realpath(WORK)))
        os.chmod(self.dir, 0o700)
        self.src = self.dir / "src"
        self.src.mkdir()
        self.loader = self.src / "dictionary_loader.mjs"
        self.core = self.src / "npc_plaintext_adapter.mjs"
        self.dictionary = self.src / "dict.json"
        self.loader.write_bytes(FIX_LOADER)
        self.core.write_bytes(FIX_CORE)
        self.dictionary.write_bytes(FIX_DICT)
        self.profile = fixture_profile()
        self.out = self.dir / "out"
        self.fds = open_fds()

    def tearDown(self):
        for root, dirs, _ in os.walk(self.dir):
            for d in dirs:
                p = os.path.join(root, d)
                if not os.path.islink(p):
                    os.chmod(p, 0o700)
        shutil.rmtree(self.dir)

    def build(self, out=None, loader=None, core=None, dictionary=None, profile=None):
        return pkg.build(str(loader or self.loader), str(core or self.core),
                         str(dictionary or self.dictionary), str(out or self.out),
                         profile=profile or self.profile)

    def refused(self, *args, out=None, **kwargs):
        """Expect a PackageError, no new output, sources unchanged."""
        target = Path(out or self.out)
        before = {p: snapshot(p) for p in (self.loader, self.core, self.dictionary)}
        existed = os.path.lexists(target)
        with self.assertRaises(pkg.PackageError) as caught:
            self.build(*args, out=out, **kwargs)
        if not existed:
            self.assertFalse(os.path.lexists(target), "refusal left an output entry")
        for p, snap in before.items():
            self.assertEqual(snapshot(p), snap, "a source changed")
        self.assertEqual(open_fds(), self.fds, "descriptor leaked")
        message = str(caught.exception)
        self.assertNotIn(str(self.dir), message, "diagnosis carries a private path")
        return message

    def failed(self, out=None):
        """After a mid-run failure: owned output gone, no descriptor leaked."""
        self.assertFalse(os.path.lexists(out or self.out), "owned output was not removed")
        self.assertEqual(open_fds(), self.fds, "descriptor leaked")


def assert_package(test, root, profile, generator_path):
    """G02 oracle: exact tree, modes, bytes, JSON keys/order and bindings."""
    root = Path(root)
    files, dirs = [], []
    for current, subdirs, names in os.walk(root):
        rel = os.path.relpath(current, root)
        dirs.append(rel)
        for name in names:
            files.append(os.path.normpath(os.path.join(rel, name)))
        for d in subdirs:
            test.assertFalse(os.path.islink(os.path.join(current, d)))
    test.assertEqual(sorted(dirs), [".", NAME, NAME + "/client"])
    test.assertEqual(sorted(files), sorted(FIVE + ["COMPLETE.json", "package-manifest.json"]))
    for d in dirs:
        st = os.lstat(root / d)
        test.assertTrue(stat.S_ISDIR(st.st_mode))
        test.assertEqual(stat.S_IMODE(st.st_mode), 0o700, d)
    for f in files:
        st = os.lstat(root / f)
        test.assertTrue(stat.S_ISREG(st.st_mode), f)
        test.assertEqual(stat.S_IMODE(st.st_mode), 0o600, f)

    client = root / NAME / "client"
    test.assertEqual((client / "index.js").read_bytes(), ENTRY)
    test.assertEqual((client / "index.js").read_bytes(), profile["entry_utf8"].encode("utf-8"))
    mod = (root / NAME / "mod.json").read_bytes()
    test.assertEqual(mod, (json.dumps(profile["mod_json"], ensure_ascii=False, sort_keys=True,
                                      indent=2) + "\n").encode("utf-8"))
    test.assertFalse(mod.startswith(b"\xef\xbb\xbf"))
    for role in ("loader", "core", "dictionary"):
        pin = profile["sources"][role]
        test.assertEqual(stream_sha(client / pin["file"]), (pin["bytes"], pin["sha256"]))

    manifest_bytes = (root / "package-manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    test.assertEqual(manifest_bytes, pkg.canonical(manifest), "manifest is not canonical")
    test.assertEqual(list(manifest), sorted(["schema", "task", "profile", "generator", "package",
                                             "acquisition", "sources", "entry", "directories",
                                             "files"]))
    test.assertEqual((manifest["schema"], manifest["task"], manifest["profile"]),
                     (1, "T05.006", "npc-plaintext-package-v1"))
    gen = Path(generator_path).read_bytes()
    test.assertEqual(manifest["generator"], {"file": "npc_plaintext_package.py",
                                             "bytes": len(gen), "sha256": sha(gen)})
    test.assertEqual(manifest["package"], profile["package"])
    test.assertEqual(manifest["acquisition"], profile["acquisition"])
    test.assertEqual(manifest["sources"], profile["sources"])
    test.assertEqual(manifest["entry"], profile["entry"])
    test.assertEqual(manifest["directories"], [
        {"path": ".", "mode": "0700"}, {"path": NAME, "mode": "0700"},
        {"path": NAME + "/client", "mode": "0700"}])
    test.assertEqual([r["path"] for r in manifest["files"]], FIVE)
    for record in manifest["files"]:
        test.assertEqual(sorted(record), ["bytes", "mode", "path", "sha256"])
        test.assertEqual(record["mode"], "0600")
        test.assertEqual(stream_sha(root / record["path"]), (record["bytes"], record["sha256"]))
    test.assertNotIn(b"/Users/", manifest_bytes)
    test.assertNotIn(b"/private/", manifest_bytes)

    complete_bytes = (root / "COMPLETE.json").read_bytes()
    complete = json.loads(complete_bytes)
    test.assertEqual(complete_bytes, pkg.canonical(complete))
    test.assertEqual(complete, {
        "schema": 1, "task": "T05.006", "profile": "npc-plaintext-package-v1",
        "state": "complete", "files": 5,
        "manifest": {"file": "package-manifest.json", "bytes": len(manifest_bytes),
                     "sha256": sha(manifest_bytes)}})
    return manifest


# ------------------------------------------------------------------ G01


@unittest.skipUnless(INPUT_ROOT, "G01 needs T05_006_INPUT_ROOT (frozen input root); unrun")
class G01PinnedGeneration(Work):
    """Actual CLI on the pinned loader/core/dictionary; unchanged sources; repeatable."""

    def real(self, role):
        return os.path.join(INPUT_ROOT, REAL[role])

    def test_frozen_manifest_and_profile_match_generator_constants(self):
        self.assertEqual(sha(Path(INPUT_ROOT, "frozen-inputs.json").read_bytes()), FROZEN_SHA)
        raw = Path(INPUT_ROOT, ".tools/renewal/t05-package-candidates/package-profile.json").read_bytes()
        self.assertEqual((len(raw), sha(raw)), (1531, PROFILE_SHA))
        self.assertEqual(json.loads(raw), pkg.PROFILE)

    def run_cli(self, out, cwd=None):
        """Absolute sources, or (with cwd=INPUT_ROOT) ordinary relative ones."""
        args = [REAL[r] if cwd else self.real(r) for r in ("loader", "core", "dictionary")]
        return subprocess.run([sys.executable, "-I", "-B", str(GENERATOR), *args, str(out)],
                              cwd=cwd, capture_output=True, timeout=300)

    def test_cli_generation_is_pinned_unchanged_and_deterministic(self):
        sources = [self.real(r) for r in ("loader", "core", "dictionary")]
        before = [snapshot(p) for p in sources]
        first = self.run_cli(self.dir / "first")
        second = self.run_cli(self.dir / "second", cwd=INPUT_ROOT)
        for result, name in ((first, "first"), (second, "second")):
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, b"")
            self.assertTrue(result.stdout.endswith(b"\n"))
            self.assertEqual(result.stdout.count(b"\n"), 1)
            value = json.loads(result.stdout)
            manifest = (self.dir / name / "package-manifest.json").read_bytes()
            self.assertEqual(value, {"task": "T05.006", "state": "complete", "output": name,
                                     "package": NAME, "files": 5, "manifest_sha256": sha(manifest)})
            assert_package(self, self.dir / name, pkg.PROFILE, GENERATOR)
        for rel in FIVE + ["package-manifest.json", "COMPLETE.json"]:
            self.assertEqual(stream_sha(self.dir / "first" / rel), stream_sha(self.dir / "second" / rel), rel)
        self.assertEqual([snapshot(p) for p in sources], before)
        for role, path in zip(("loader", "core", "dictionary"), sources):
            pin = pkg.PROFILE["sources"][role]
            self.assertEqual(before[sources.index(path)][3], (pin["bytes"], pin["sha256"]))
        # Only the generator identity is provider-specific; everything else equals the profile.
        manifest = json.loads((self.dir / "first" / "package-manifest.json").read_bytes())
        self.assertEqual(manifest["generator"]["file"], "npc_plaintext_package.py")

    def test_production_stream_is_bounded_and_never_parsed(self):
        reads = []
        real_read = os.read

        def read(fd, n):
            reads.append(n)
            return real_read(fd, n)

        def no_parse(*a, **k):
            raise AssertionError("dictionary must not be parsed")

        with mock.patch.object(pkg.os, "read", read), \
                mock.patch.object(pkg.json, "loads", no_parse), \
                mock.patch.object(pkg.json, "load", no_parse):
            pkg.build(self.real("loader"), self.real("core"), self.real("dictionary"), str(self.out))
        self.assertLessEqual(max(reads), pkg.SMALL_CAP + 1)
        self.assertGreaterEqual(sum(1 for n in reads if n == pkg.CHUNK), 18)
        assert_package(self, self.out, pkg.PROFILE, GENERATOR)


# ------------------------------------------------------------------ G02


class G02PackageEvidence(Work):
    """Exact tree/files/JSON/modes/bindings on a fixture build; no extras."""

    def test_exact_package_and_evidence(self):
        result = self.build()
        manifest = assert_package(self, self.out, self.profile, GENERATOR)
        self.assertEqual(result, {"task": "T05.006", "state": "complete", "output": "out",
                                  "package": NAME, "files": 5,
                                  "manifest_sha256": sha((self.out / "package-manifest.json").read_bytes())})
        self.assertEqual(manifest["sources"], self.profile["sources"])

    def test_restrictive_and_permissive_umask(self):
        for mask, name in ((0o777, "tight"), (0o000, "open")):
            old = os.umask(mask)
            try:
                self.build(out=self.dir / name)
            finally:
                os.umask(old)
            assert_package(self, self.dir / name, self.profile, GENERATOR)

    def test_literal_default_reexport_not_export_star(self):
        self.build()
        entry = (self.out / NAME / "client/index.js").read_bytes()
        self.assertEqual(entry, ENTRY)
        self.assertNotIn(b"export *", entry)
        self.assertNotIn(b"import.meta", entry)

    def test_production_cli_has_no_bypass(self):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "stdout", out), mock.patch.object(sys, "stderr", err):
            self.assertEqual(pkg.main(["--profile", "x", "a", "b", "c"]), 2)
            self.assertEqual(pkg.main(["a", "b", "c"]), 2)
            self.assertEqual(pkg.main(["a", "b", "c", "d", "e"]), 2)
        self.assertEqual(out.getvalue(), "")

    def test_fixture_pins_refused_by_production_cli(self):
        result = subprocess.run([sys.executable, "-I", "-B", str(GENERATOR), str(self.loader),
                                 str(self.core), str(self.dictionary), str(self.out)],
                                capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b"")
        self.assertNotIn(b"Traceback", result.stderr)
        self.assertNotIn(str(self.dir).encode(), result.stderr)
        self.assertFalse(self.out.exists())


# ------------------------------------------------------------------ G03


class G03Refusals(Work):
    """Ordinary refusals before publication: nothing created, overwritten or deleted."""

    def test_existing_output_kinds(self):
        (self.dir / "file").write_bytes(b"keep")
        full = self.dir / "full"
        full.mkdir()
        (full / "keep").write_bytes(b"keep")
        (self.dir / "empty").mkdir()
        os.symlink(self.dir / "missing", self.dir / "dangling")
        os.mkfifo(self.dir / "fifo")
        for name in ("file", "full", "empty", "dangling", "fifo"):
            self.assertIn("exists", self.refused(out=self.dir / name))
        self.assertEqual((self.dir / "file").read_bytes(), b"keep")
        self.assertEqual(os.listdir(full), ["keep"])
        self.assertEqual(os.listdir(self.dir / "empty"), [])
        self.assertTrue(os.path.islink(self.dir / "dangling"))
        self.assertTrue(stat.S_ISFIFO(os.lstat(self.dir / "fifo").st_mode))

    def test_output_parent_and_lexical_components(self):
        (self.dir / "plain").write_bytes(b"x")
        os.symlink(self.dir, self.dir / "link")
        for out in (self.dir / "nope" / "out", self.dir / "plain" / "out",
                    str(self.dir) + "/./out", str(self.dir) + "/src/../out",
                    str(self.dir) + "//out", str(self.dir) + "/out/", self.dir / "link" / "out", "/"):
            self.refused(out=out)
        with self.assertRaises(pkg.PackageError):
            pkg.build(str(self.loader), str(self.core), str(self.dictionary), "", profile=self.profile)
        self.assertFalse(self.out.exists())

    def test_source_symlinks_and_nonregular(self):
        os.symlink(self.loader, self.dir / "loader-link")
        os.symlink(self.src, self.dir / "src-link")
        (self.dir / "a-dir").mkdir()
        self.assertIn("symbolic", self.refused(loader=self.dir / "loader-link"))
        self.assertIn("symbolic", self.refused(core=self.dir / "src-link" / self.core.name))
        self.assertIn("regular", self.refused(dictionary=self.dir / "a-dir"))
        self.refused(core=self.dir / "absent")
        self.refused(loader=str(self.src) + "/./" + self.loader.name)

    def test_fifo_source_does_not_hang(self):
        os.mkfifo(self.dir / "fifo")
        result = subprocess.run([sys.executable, "-I", "-B", str(GENERATOR), str(self.loader),
                                 str(self.core), str(self.dir / "fifo"), str(self.out)],
                                capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"regular", result.stderr)
        self.assertFalse(self.out.exists())

    def test_oversize_wrong_length_and_wrong_hash(self):
        big = self.dir / "big.mjs"
        big.write_bytes(FIX_LOADER + b"x")
        self.assertIn("pinned length", self.refused(loader=big))
        short = self.dir / "short.json"
        short.write_bytes(FIX_DICT[:-1])
        self.assertIn("pinned length", self.refused(dictionary=short))
        flipped = self.dir / "flip.mjs"
        flipped.write_bytes(FIX_CORE[:-2] + b"X\n")
        self.assertIn("SHA-256", self.refused(core=flipped))
        # A loader pin above the 1 MiB cap is refused before reading.
        capped = fixture_profile(loader=b"x" * (pkg.SMALL_CAP + 1))
        cap_file = self.dir / "cap.mjs"
        cap_file.write_bytes(b"x" * (pkg.SMALL_CAP + 1))
        self.assertIn("1 MiB", self.refused(loader=cap_file, profile=capped))

    def test_path_overlap(self):
        self.assertIn("overlap", self.refused(core=self.loader))
        os.link(self.loader, self.dir / "hard.mjs")
        both = fixture_profile(core=FIX_LOADER)
        self.assertIn("overlap", self.refused(core=self.dir / "hard.mjs", profile=both))
        self.refused(out=self.dictionary)                 # exists
        self.refused(out=self.loader / "inside")          # parent is a source file

    def test_relative_paths_and_dot_tools_name(self):
        dot = self.dir / ".tools"
        dot.mkdir()
        cwd = os.getcwd()
        os.chdir(self.dir)
        try:
            pkg.build("src/" + self.loader.name, "src/" + self.core.name, "src/" + self.dictionary.name,
                      ".tools/out", profile=self.profile)
        finally:
            os.chdir(cwd)
        assert_package(self, dot / "out", self.profile, GENERATOR)


# ------------------------------------------------------------------ G04


class G04StreamReadback(Work):
    """Truncated/extra/changed input and output mismatch never complete."""

    def dict_reads(self, transform):
        """Patch os.read only for reads of the dictionary source descriptor."""
        real_read = os.read
        ino = os.lstat(self.dictionary).st_ino

        def read(fd, n):
            data = real_read(fd, n)
            st = os.fstat(fd)
            if st.st_ino == ino and stat.S_ISREG(st.st_mode):
                return transform(fd, n, data)
            return data
        return mock.patch.object(pkg.os, "read", read)

    def test_truncated_stream(self):
        state = {"calls": 0}

        def cut(fd, n, data):
            state["calls"] += 1
            return b"" if state["calls"] > 2 else data
        with self.dict_reads(cut), mock.patch.object(pkg, "CHUNK", 64):
            self.assertIn("truncated", str(self.assertRaisesPkg()))
        self.failed()

    def assertRaisesPkg(self):
        with self.assertRaises(pkg.PackageError) as caught:
            self.build()
        return caught.exception

    def test_extra_byte_at_eof_probe(self):
        with self.dict_reads(lambda fd, n, d: d if d else b"!"):
            self.assertIn("more bytes", str(self.assertRaisesPkg()))
        self.failed()

    def test_actual_append_during_stream(self):
        state = {"done": False}

        def grow(fd, n, data):
            if not state["done"]:
                state["done"] = True
                with open(self.dictionary, "ab") as fh:
                    fh.write(b"appended")
            return data
        with self.dict_reads(grow), mock.patch.object(pkg, "CHUNK", 64):
            error = self.assertRaisesPkg()
        self.assertTrue("more bytes" in str(error) or "changed" in str(error), error)
        self.failed()

    def test_changed_content_same_length(self):
        with self.dict_reads(lambda fd, n, d: (b"Z" + d[1:]) if d else d):
            self.assertIn("SHA-256", str(self.assertRaisesPkg()))
        self.failed()

    def test_source_path_replaced_mid_run(self):
        state = {"done": False}
        other = self.dir / "other.json"
        other.write_bytes(FIX_DICT)

        def swap(fd, n, data):
            if not state["done"]:
                state["done"] = True
                os.rename(other, self.dictionary)
            return data
        with self.dict_reads(swap):
            self.assertIn("identity", str(self.assertRaisesPkg()))
        self.failed()

    def test_output_mismatch_detected_by_readback(self):
        real_write = os.write

        def corrupt(fd, data):
            data = bytes(data)
            if data and data.startswith(b"// fixture core"):
                data = b"#" + data[1:]
            return real_write(fd, data)
        with mock.patch.object(pkg.os, "write", corrupt):
            self.assertIn("read-back", str(self.assertRaisesPkg()))
        self.failed()

    def test_bounded_streaming_reads_and_writes(self):
        reads, writes = [], []
        real_read, real_write = os.read, os.write
        ino = os.lstat(self.dictionary).st_ino

        def read(fd, n):
            if os.fstat(fd).st_ino == ino:
                reads.append(n)
            return real_read(fd, n)

        def write(fd, data):
            writes.append(len(data))
            return real_write(fd, data)

        def no_parse(*a, **k):
            raise AssertionError("dictionary must not be parsed")
        with mock.patch.object(pkg, "CHUNK", 32), mock.patch.object(pkg.os, "read", read), \
                mock.patch.object(pkg.os, "write", write), \
                mock.patch.object(pkg.json, "loads", no_parse):
            self.build()
        self.assertLessEqual(max(reads), 32)
        self.assertGreaterEqual(len(reads), len(FIX_DICT) // 32)
        self.assertEqual(reads[-1], 1)                    # the EOF probe
        assert_package(self, self.out, self.profile, GENERATOR)


# ------------------------------------------------------------------ G05


class G05PublicationFailures(Work):
    """Short writes complete; fsync/close/completion failures invalidate owned output."""

    def test_short_writes_complete(self):
        real_write = os.write
        with mock.patch.object(pkg.os, "write", lambda fd, d: real_write(fd, bytes(d[:3]))):
            self.build()
        assert_package(self, self.out, self.profile, GENERATOR)

    def test_zero_and_failing_write(self):
        with mock.patch.object(pkg.os, "write", lambda fd, d: 0):
            self.assertIn("no valid progress", str(self.fail_build()))
        self.failed()

        def nospace(fd, d):
            raise OSError(errno.ENOSPC, os.strerror(errno.ENOSPC))
        with mock.patch.object(pkg.os, "write", nospace):
            self.assertIn("write failed", str(self.fail_build()))
        self.failed()

    def fail_build(self):
        with self.assertRaises(pkg.PackageError) as caught:
            self.build()
        self.assertNotIn(str(self.dir), str(caught.exception))
        return caught.exception

    def nth(self, name, n, action):
        """Patch os.<name> so its n-th call (1-based) runs action(real, *args)."""
        real = getattr(os, name)
        state = {"calls": 0}

        def wrapper(*args, **kwargs):
            state["calls"] += 1
            if state["calls"] == n:
                return action(real, *args, **kwargs)
            return real(*args, **kwargs)
        return mock.patch.object(pkg.os, name, wrapper)

    @staticmethod
    def eio(*_a, **_k):
        raise OSError(errno.EIO, os.strerror(errno.EIO))

    def test_fsync_failure_each_file(self):
        # Seven fsyncs: five package files, the manifest, the completion.
        for n in range(1, 8):
            with self.subTest(fsync=n), self.nth("fsync", n, lambda real, fd: self.eio()):
                self.assertIn("fsync failed", str(self.fail_build()))
            self.failed()

    def test_close_failure_after_real_close(self):
        # The first close after a successful fsync really closes, then reports EIO.
        real_fsync, real_close = os.fsync, os.close
        state = {"armed": False}

        def close(fd):
            if state["armed"]:
                state["armed"] = False
                real_close(fd)
                self.eio()
            return real_close(fd)

        def fsync_arm(fd):
            real_fsync(fd)
            state["armed"] = True
        with mock.patch.object(pkg.os, "fsync", fsync_arm), mock.patch.object(pkg.os, "close", close):
            self.assertIn("close failed", str(self.fail_build()))
        self.failed()

    def test_completion_link_failure(self):
        with mock.patch.object(pkg.os, "link", self.eio):
            self.assertIn("finalize completion", str(self.fail_build()))
        self.failed()

    def test_completion_readback_failure(self):
        real_open = os.open

        def open_(path, flags, *a, **k):
            if str(path).endswith("/COMPLETE.json") and not flags & os.O_CREAT:
                raise OSError(errno.EIO, os.strerror(errno.EIO))
            return real_open(path, flags, *a, **k)
        with mock.patch.object(pkg.os, "open", open_):
            self.assertIn("read-back", str(self.fail_build()))
        self.failed()

    def test_readback_read_failure(self):
        # A read error while reading back the manifest (opened read-only after writing).
        real_read = os.read
        state = {"armed": False}
        real_open = os.open

        def open_(path, flags, *a, **k):
            fd = real_open(path, flags, *a, **k)
            if str(path).endswith("/package-manifest.json") and not flags & os.O_CREAT:
                state["armed"] = fd
            return fd

        def read(fd, n):
            if state["armed"] is not False and fd == state["armed"]:
                raise OSError(errno.EIO, os.strerror(errno.EIO))
            return real_read(fd, n)
        with mock.patch.object(pkg.os, "open", open_), mock.patch.object(pkg.os, "read", read):
            self.assertIn("read-back", str(self.fail_build()))
        self.failed()

    def test_partial_source_descriptor_cleanup(self):
        real_open = os.open

        def open_(path, flags, *a, **k):
            if str(path) == str(self.core):
                raise OSError(errno.EMFILE, os.strerror(errno.EMFILE))
            return real_open(path, flags, *a, **k)
        with mock.patch.object(pkg.os, "open", open_):
            self.assertIn("cannot open", str(self.fail_build()))
        self.failed()

    def test_post_mkdir_inspection_reports_unverified_root(self):
        real_mkdir, real_lstat = os.mkdir, os.lstat
        state = {"created": False, "injected": False}
        before = {p: snapshot(p) for p in (self.loader, self.core, self.dictionary)}

        def mkdir(path, *args, **kwargs):
            result = real_mkdir(path, *args, **kwargs)
            if str(path) == str(self.out):
                state["created"] = True
            return result

        def lstat(path, *args, **kwargs):
            if str(path) == str(self.out) and state["created"] and not state["injected"]:
                state["injected"] = True
                raise OSError(errno.EIO, os.strerror(errno.EIO))
            return real_lstat(path, *args, **kwargs)

        with mock.patch.object(pkg.os, "mkdir", mkdir), mock.patch.object(pkg.os, "lstat", lstat):
            message = str(self.fail_build())
        self.assertTrue(state["injected"])
        self.assertIn("cleanup", message)
        self.assertIn("unverified", message)
        # Successful creation alone is insufficient ownership proof for removal.
        self.assertTrue(self.out.is_dir())
        self.assertEqual(os.listdir(self.out), [])
        self.assertFalse((self.out / "COMPLETE.json").exists())
        self.assertEqual(open_fds(), self.fds)
        self.assertEqual(before, {p: snapshot(p) for p in before})

    def test_interrupt_mid_copy_cleans_and_reraises(self):
        with self.nth("fsync", 5, lambda real, fd: (_ for _ in ()).throw(KeyboardInterrupt())):
            with self.assertRaises(KeyboardInterrupt):
                self.build()
        self.failed()

    def test_foreign_root_replacement_preserved(self):
        moved = self.dir / "moved-owned"

        def replace_root(real, fd):
            os.rename(self.out, moved)
            os.mkdir(self.out)
            (self.out / "foreign").write_bytes(b"foreign")
            self.eio()
        with self.nth("fsync", 3, replace_root):
            message = str(self.fail_build())
        self.assertIn("cleanup", message)
        self.assertIn("foreign", message)
        self.assertEqual(os.listdir(self.out), ["foreign"])
        self.assertEqual((self.out / "foreign").read_bytes(), b"foreign")
        self.assertEqual(open_fds(), self.fds)

    def test_foreign_entry_inside_owned_tree_is_kept_and_reported(self):
        def plant(real, fd):
            (self.out / NAME / "client" / "planted").write_bytes(b"foreign")
            self.eio()
        with self.nth("fsync", 2, plant):
            message = str(self.fail_build())
        self.assertIn("cleanup", message)
        self.assertEqual((self.out / NAME / "client" / "planted").read_bytes(), b"foreign")
        self.assertFalse((self.out / NAME / "mod.json").exists())

    def test_cli_failure_has_no_success_or_traceback(self):
        original = pkg.build
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(pkg, "build", lambda *a: original(*a, profile=self.profile)), \
                self.nth("fsync", 4, lambda real, fd: self.eio()), \
                mock.patch.object(sys, "stdout", out), mock.patch.object(sys, "stderr", err):
            code = pkg.main([str(self.loader), str(self.core), str(self.dictionary), str(self.out)])
        self.assertEqual(code, 1)
        self.assertEqual(out.getvalue(), "")
        self.assertNotIn("Traceback", err.getvalue())
        self.assertNotIn(str(self.dir), err.getvalue())
        self.assertLessEqual(len(err.getvalue()), 400)
        self.failed()


# ------------------------------------------------------------------ G06
#
# Source-profile model of supported staging, from the pinned primary sources:
#   mods.rs read_manifest/scan: <mod>/mod.json at the folder root; folder name
#     is identity; "default":"off" is Off unless explicitly enabled; requires
#     keys limited to app/era/mods/client; "=1.6.3" is an exact app rule.
#   assets.rs overlay_mods: only when <root>/client/index.js is a file, the
#     client/ tree is copied to plugins/<name>/ and the config entry is
#     {path:'plugins/<name>/index', pars:{...}}.
#   PluginManager.js: the path resolves against document.baseURI and gains
#     '.js'; the module default export is the initializer.
# Labelled model only: nothing here executes JS, stock code or native staging.


def staging_model(mod_dir, name):
    """Return (staged {server path: source file}, config entry) or (None, None)."""
    mod_dir = Path(mod_dir)
    client = mod_dir / "client"
    if not (client / "index.js").is_file():
        return None, None
    staged = {}
    for current, _, names in os.walk(client):
        for n in names:
            rel = os.path.relpath(os.path.join(current, n), client)
            staged["plugins/%s/%s" % (name, rel)] = Path(current, n)
    return staged, {"path": "plugins/%s/index" % name}


def validate_handoff(test, mod_dir, profile):
    """Five package files valid; four client resources staged; mod.json not staged."""
    mod_dir = Path(mod_dir)
    name = mod_dir.name
    test.assertEqual(name, profile["package"]["name"])
    manifest = json.loads((mod_dir / "mod.json").read_bytes())
    test.assertEqual(manifest, profile["mod_json"])
    test.assertEqual(manifest["name"], name)
    test.assertEqual(manifest["default"], "off")
    test.assertTrue(set(manifest["requires"]) <= {"app", "era", "mods", "client"})
    test.assertEqual(manifest["requires"], {"app": "=1.6.3", "era": "renewal"})
    staged, config = staging_model(mod_dir, name)
    test.assertIsNotNone(staged, "client/index.js missing: supported staging would skip the plugin")
    entry = (mod_dir / "client" / "index.js").read_bytes()
    test.assertEqual(entry, profile["entry_utf8"].encode("utf-8"), "not the literal default re-export")
    prefix = profile["entry"]["stage_prefix"]
    test.assertEqual(sorted(staged), sorted(prefix + "/" + f for f in (
        "index.js", "dictionary_loader.mjs", "npc_plaintext_adapter.mjs", "dict.json")))
    test.assertNotIn(prefix + "/mod.json", staged)
    test.assertEqual(config["path"], profile["entry"]["config_path"])
    test.assertIn(config["path"] + ".js", staged)
    loader_url = prefix + "/" + profile["entry"]["default_export"][2:]
    test.assertIn(loader_url, staged)
    for rel in (profile["entry"]["core_relative"], profile["entry"]["dictionary_relative"]):
        test.assertIn(os.path.normpath(os.path.join(os.path.dirname(loader_url), rel)), staged)
    for role in ("loader", "core", "dictionary"):
        pin = profile["sources"][role]
        test.assertEqual(stream_sha(staged[prefix + "/" + pin["file"]]), (pin["bytes"], pin["sha256"]))
    return staged


class G06HandoffStagingProfile(Work):
    """Source-profile handoff checks (labelled model; no JS/native staging run)."""

    def test_fixture_package_maps_four_client_resources(self):
        self.build()
        staged = validate_handoff(self, self.out / NAME, self.profile)
        self.assertEqual(len(staged), 4)

    @unittest.skipUnless(INPUT_ROOT, "real-package handoff needs T05_006_INPUT_ROOT; unrun")
    def test_real_package_maps_four_client_resources(self):
        pkg.build(*(os.path.join(INPUT_ROOT, REAL[r]) for r in ("loader", "core", "dictionary")),
                  str(self.out))
        staged = validate_handoff(self, self.out / NAME, pkg.PROFILE)
        self.assertEqual(len(staged), 4)

    def mutate(self, change):
        self.build()
        mod_dir = self.out / NAME
        os.chmod(mod_dir / "client", 0o700)
        change(mod_dir)
        with self.assertRaises(AssertionError):
            validate_handoff(self, mod_dir, self.profile)

    def test_negative_missing_index(self):
        self.mutate(lambda d: os.unlink(d / "client" / "index.js"))
        self.assertEqual(staging_model(self.out / NAME, NAME), (None, None))

    def test_negative_non_default_entries(self):
        for body in (b"export * from './dictionary_loader.mjs';\n",
                     b"export { default } from './dictionary_loader.mjs';",
                     b"import init from './dictionary_loader.mjs';\nexport default init;\n",
                     b"export { default } from '/plugins/npc-plaintext-zh-tw/dictionary_loader.mjs';\n"):
            with self.subTest(body=body):
                shutil.rmtree(self.out, ignore_errors=True)
                self.mutate(lambda d: (d / "client" / "index.js").write_bytes(body))

    def test_negative_extra_client_resource_and_staged_manifest(self):
        self.mutate(lambda d: (d / "client" / "extra.js").write_bytes(b"x"))
        shutil.rmtree(self.out)
        self.mutate(lambda d: shutil.copy(d / "mod.json", d / "client" / "mod.json"))

    def test_negative_default_on_and_wrong_folder_name(self):
        def default_on(d):
            data = json.loads((d / "mod.json").read_bytes())
            data["default"] = "on"
            (d / "mod.json").write_bytes(pkg.canonical(data))
        self.mutate(default_on)
        shutil.rmtree(self.out)
        self.build()
        renamed = self.out / "npc-plaintext"
        os.rename(self.out / NAME, renamed)
        with self.assertRaises(AssertionError):
            validate_handoff(self, renamed, self.profile)


if __name__ == "__main__":
    unittest.main()
