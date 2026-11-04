"""Focused tests for prepare_source.py (T10.010.003).

  python3 -I -B tools/renewal/native_capacity/test_prepare_source.py

Synthetic local repositories (file:// URLs, no network) exercise the safe
failures: bad revision/tree/app-semantics pins, wrong prepared digest or
native pin, rejected/unallowlisted-fuzz/stale-allowlist patches, existing or
partially prepared output and dirty prepared trees. A static check binds the
real manifest to the existing nine-pin oracle. The real pinned preparation is
run separately through the CLI (see the T10.010.003 review).
"""

import copy
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prepare_source as ps  # noqa: E402

A_CPP = "".join(f"line {i}\n" for i in range(1, 21))
PATCH_OK = """--- a/src/map/a.cpp
+++ b/src/map/a.cpp
@@ -4,6 +4,7 @@
 line 4
 line 5
 line 6
+added by patch
 line 7
 line 8
 line 9
"""
# Last trailing context line is wrong: needs fuzz 1 (like the real pc.cpp hunk).
PATCH_FUZZ = """--- a/src/map/a.cpp
+++ b/src/map/a.cpp
@@ -14,6 +14,7 @@
 line 14
 line 15
 line 16
+fuzzed add
 line 17
 line 18
 not line 19
"""
PATCH_REJECT = """--- a/src/map/a.cpp
+++ b/src/map/a.cpp
@@ -4,3 +4,4 @@
 nothing
 like
 this
+x
"""
T1 = """import sys
from pathlib import Path
p = Path(sys.argv[1]) / "src/common/core.cpp"
p.write_text(p.read_text() + "// hooked\\n")
"""


def run(*cmd, cwd=None):
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True,
                   env=dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1"))


def make_repo(root, files):
    root.mkdir(parents=True)
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    run("git", "init", "-q", cwd=root)
    run("git", "add", "-A", cwd=root)
    run("git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "fixture",
        cwd=root)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True).stdout.strip()
    tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=root, capture_output=True,
                          text=True).stdout.strip()
    return head, tree


def blob(repo, rel):
    return subprocess.run(["git", "rev-parse", f"HEAD:{rel}"], cwd=repo, capture_output=True,
                          text=True).stdout.strip()


class Fixture:
    def __init__(self, patches):
        self.tmp = Path(tempfile.mkdtemp(prefix="t10-010-003-test-"))
        ra = {"src/map/map.cpp": "map\n", "src/map/a.cpp": A_CPP, "src/common/core.cpp": "core\n"}
        app = {"scripts/t1.py": T1, "files/src/map/new.cpp": "new\n", "files/conf/x.conf": "x\n",
               "Dockerfile": "FROM scratch\n"}
        for name, text in patches.items():
            app[f"patches/{name}"] = text
        self.ra_dir, self.app_dir = self.tmp / "src-ra", self.tmp / "src-app"
        ra_c, ra_t = make_repo(self.ra_dir, ra)
        app_c, app_t = make_repo(self.app_dir, app)
        self.manifest = {
            "schema": "t10.010.003/source-manifest/v1",
            "repositories": {
                "rathena": {"url": self.ra_dir.as_uri(), "commit": ra_c, "tree": ra_t, "files": 3},
                "app": {"url": self.app_dir.as_uri(), "commit": app_c, "tree": app_t},
            },
            "app_semantics_blobs": {"scripts/t1.py": blob(self.app_dir, "scripts/t1.py")},
            "steps": [
                {"id": "hook", "op": "app_python", "script": "scripts/t1.py", "args": ["{tree}"]},
                {"id": "files", "op": "copy_tree", "from": "files", "expect_files": 2},
                {"id": "patches", "op": "patch_series", "glob": "patches/*.patch",
                 "expect_patches": len(patches)},
                {"id": "stamp", "op": "stamp_concat_sha256", "glob": "patches/*.patch", "to": ".stamp"},
                {"id": "df", "op": "copy_file", "from": "Dockerfile", "to": "Dockerfile.x"},
            ],
            "prepared_tree": {"files": 7, "sha256": "0" * 64},
        }
        self.cache = self.tmp / "cache"
        self.out = self.tmp / "work" / "prepared"
        self.pins = {}

    def fetch(self, manifest=None):
        return ps.fetch(self.cache, manifest or self.manifest)

    def discover(self, engine="patch"):
        """Compute the digest once, then pin it (and a native pin) like the real manifest."""
        rec = ps.prepare(self.cache, self.tmp / "disc", self.manifest, engine, allow_unpinned=True, pins={})
        shutil.rmtree(self.tmp / "disc")
        self.manifest["prepared_tree"]["sha256"] = rec["prepared_tree_sha256"]
        return rec

    def close(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class PrepareTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture({"0001-ok.patch": PATCH_OK})
        self.f.fetch()

    def tearDown(self):
        self.f.close()

    def assertFails(self, fn, text):
        with self.assertRaises(ps.PrepError) as cm:
            fn()
        self.assertIn(text, str(cm.exception))

    def assertNoOutput(self):
        self.assertFalse(self.f.out.exists())
        self.assertEqual(ps.leftover_staging(self.f.out), [])

    def prepared(self, engine="patch"):
        self.f.discover(engine)
        a = self.f.tmp / "a.cpp"
        a.write_text(A_CPP.replace("line 6\n", "line 6\nadded by patch\n"))
        self.f.pins = {"src/map/a.cpp": (a.stat().st_size, hashlib.sha256(a.read_bytes()).hexdigest())}
        return ps.prepare(self.f.cache, self.f.out, self.f.manifest, engine, pins=self.f.pins)

    def test_fresh_prepare_verify_and_engines_agree(self):
        rec = self.prepared("patch")
        self.assertEqual(rec["prepared_files"], 7)
        self.assertEqual(rec["footprint"]["added"], [".stamp", "Dockerfile.x", "conf/x.conf", "src/map/new.cpp"])
        self.assertEqual(rec["footprint"]["modified"], ["src/common/core.cpp", "src/map/a.cpp"])
        self.assertEqual(ps.verify(self.f.out, self.f.manifest, pins=self.f.pins)["files"], 7)
        other = ps.prepare(self.f.cache, self.f.tmp / "w2" / "p", self.f.manifest, "git-apply", pins=self.f.pins)
        self.assertEqual(other["prepared_tree_sha256"], rec["prepared_tree_sha256"])

    def test_bad_revision(self):
        m = copy.deepcopy(self.f.manifest)
        m["repositories"]["rathena"]["commit"] = "1" * 40
        self.assertFails(lambda: ps.fetch(self.f.tmp / "cache2", m), "not our ref")
        self.assertFails(lambda: ps.prepare(self.f.cache, self.f.out, m, "patch", True, {}), "bad revision")
        self.assertNoOutput()

    def test_bad_tree_pin(self):
        m = copy.deepcopy(self.f.manifest)
        m["repositories"]["app"]["tree"] = "2" * 40
        self.assertFails(lambda: ps.fetch(self.f.cache, m), "!= pinned")
        self.assertFails(lambda: ps.prepare(self.f.cache, self.f.out, m, "patch", True, {}), "!= pinned")
        self.assertNoOutput()

    def test_app_semantics_change(self):
        m = copy.deepcopy(self.f.manifest)
        m["app_semantics_blobs"]["scripts/t1.py"] = "3" * 40
        self.assertFails(lambda: ps.prepare(self.f.cache, self.f.out, m, "patch", True, {}), "app semantics")
        self.assertNoOutput()

    def test_unpinned_digest_refused(self):
        self.f.manifest["prepared_tree"]["sha256"] = "PENDING"
        self.assertFails(lambda: ps.prepare(self.f.cache, self.f.out, self.f.manifest, "patch", pins={}),
                         "not pinned")

    def test_wrong_prepared_digest(self):
        self.assertFails(lambda: ps.prepare(self.f.cache, self.f.out, self.f.manifest, "patch", pins={}),
                         "digest")
        self.assertNoOutput()

    def test_wrong_native_pin(self):
        self.f.discover()
        bad = {"src/map/a.cpp": (1, "4" * 64)}
        self.assertFails(lambda: ps.prepare(self.f.cache, self.f.out, self.f.manifest, "patch", pins=bad),
                         "pin src/map/a.cpp")
        self.assertNoOutput()

    def test_existing_output_refused(self):
        self.prepared()
        self.assertFails(lambda: ps.prepare(self.f.cache, self.f.out, self.f.manifest, "patch", pins={}),
                         "already exists")

    def test_partial_staging_refused(self):
        self.f.discover()
        self.f.out.parent.mkdir(parents=True)
        (self.f.out.parent / (self.f.out.name + ps.STAGING + "crash")).mkdir()
        self.assertFails(lambda: ps.prepare(self.f.cache, self.f.out, self.f.manifest, "patch", pins={}),
                         "partial preparation")
        self.assertFails(lambda: ps.verify(self.f.out, self.f.manifest, pins={}), "partial preparation")

    def test_dirty_outputs(self):
        self.prepared()
        src = self.f.out / "source"
        cases = [
            ("modify", lambda: (src / "src/map/map.cpp").write_text("changed\n")),
            ("add", lambda: (src / "src/map/extra.o").write_text("x")),
            ("remove", lambda: (src / "conf/x.conf").unlink()),
            ("mode", lambda: os.chmod(src / "src/map/map.cpp", 0o755)),
        ]
        snapshot = self.f.tmp / "snap"
        shutil.copytree(self.f.out, snapshot)
        for name, mutate in cases:
            with self.subTest(name):
                shutil.rmtree(self.f.out)
                shutil.copytree(snapshot, self.f.out)
                mutate()
                self.assertFails(lambda: ps.verify(self.f.out, self.f.manifest, pins=self.f.pins), "dirty")
        shutil.rmtree(self.f.out)
        shutil.copytree(snapshot, self.f.out)
        (self.f.out / ps.MARKER).unlink()
        self.assertFails(lambda: ps.verify(self.f.out, self.f.manifest, pins=self.f.pins), "partial or foreign")
        shutil.copytree(snapshot / "source", self.f.out / "source2")
        (self.f.out / ps.MARKER).write_text((snapshot / ps.MARKER).read_text())
        self.assertFails(lambda: ps.verify(self.f.out, self.f.manifest, pins=self.f.pins), "unexpected entries")


class PatchPolicyTests(unittest.TestCase):
    def run_fixture(self, patches, allow=None, engines=("patch", "git-apply")):
        f = Fixture(patches)
        try:
            f.fetch()
            if allow is not None:
                f.manifest["steps"][2]["fuzz_allowlist"] = allow
            results = {}
            for e in engines:
                try:
                    results[e] = ps.prepare(f.cache, f.tmp / e / "p", f.manifest, e, allow_unpinned=True,
                                            pins={})["prepared_tree_sha256"]
                except ps.PrepError as exc:
                    results[e] = exc
                self.assertEqual(ps.leftover_staging(f.tmp / e / "p"), [])
            return results
        finally:
            f.close()

    def test_reject_fails_both_engines(self):
        for e, r in self.run_fixture({"0001-bad.patch": PATCH_REJECT}).items():
            self.assertIsInstance(r, ps.PrepError, e)
            self.assertIn("not clean", str(r))

    def test_fuzz_without_allowlist_fails(self):
        for e, r in self.run_fixture({"0001-ok.patch": PATCH_OK, "0002-fuzz.patch": PATCH_FUZZ}).items():
            self.assertIsInstance(r, ps.PrepError, e)

    def test_allowlisted_fuzz_pinned_result(self):
        expect = A_CPP.replace("line 6\n", "line 6\nadded by patch\n").replace("line 16\n", "line 16\nfuzzed add\n")
        allow = {"0002-fuzz.patch": {"fuzz": 1, "file": "src/map/a.cpp",
                                     "sha256_after": hashlib.sha256(expect.encode()).hexdigest()}}
        res = self.run_fixture({"0001-ok.patch": PATCH_OK, "0002-fuzz.patch": PATCH_FUZZ}, allow)
        self.assertIsInstance(res["patch"], str)
        self.assertEqual(res["patch"], res["git-apply"])
        allow["0002-fuzz.patch"]["sha256_after"] = "5" * 64
        for e, r in self.run_fixture({"0001-ok.patch": PATCH_OK, "0002-fuzz.patch": PATCH_FUZZ}, allow).items():
            self.assertIn("!= pinned", str(r), e)

    def test_stale_allowlist_fails(self):
        allow = {"0001-ok.patch": {"fuzz": 1, "file": "src/map/a.cpp", "sha256_after": "6" * 64}}
        for e, r in self.run_fixture({"0001-ok.patch": PATCH_OK}, allow).items():
            self.assertIn("stale fuzz allowlist", str(r), e)

    def test_allowlist_for_absent_patch_fails(self):
        allow = {"0009-gone.patch": {"fuzz": 1, "file": "x", "sha256_after": "7" * 64}}
        r = self.run_fixture({"0001-ok.patch": PATCH_OK}, allow, engines=("patch",))["patch"]
        self.assertIn("absent patches", str(r))


class RealManifestTests(unittest.TestCase):
    def test_manifest_binds_oracle_and_brief(self):
        m = ps.load_manifest(ps.MANIFEST)
        r = m["repositories"]
        self.assertEqual(r["rathena"]["commit"], "0693b8c69911d5ca42269684aa036b67d67f4d3e")
        self.assertEqual(r["rathena"]["url"], "https://github.com/rathena/rathena.git")
        self.assertEqual(r["app"]["commit"], "2c3b2612973fb8d0ae6ad366a2b298686f2404cb")
        self.assertEqual(r["app"]["url"], "https://github.com/Flux159/ragnarokoffline.app.git")
        self.assertEqual([s["id"] for s in m["steps"]],
                         ["crash-trace", "population-files", "population-patches", "party-chat-hook",
                          "server-mods-stamp", "build-dockerfile"])
        self.assertEqual(m["steps"][2]["expect_patches"], 36)
        self.assertEqual(len(m["steps"][2]["fuzz_allowlist"]), 1)
        self.assertRegex(m["prepared_tree"]["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(len(ps.load_pins()), 9)


if __name__ == "__main__":
    unittest.main(verbosity=2)
