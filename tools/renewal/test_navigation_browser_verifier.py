"""Tests for navigation_browser_verifier (T05.008). Three groups, G01-G03.

    T05_008_INPUT_ROOT=<frozen input root> \\
        python3 -I -B tools/renewal/test_navigation_browser_verifier.py -v

G01 needs the frozen read-only input root (the directory holding
frozen-inputs.json); without it its tests are reported as skipped, never
passed. G02/G03 run on tiny authored fixtures under T05_008_WORK (default:
.tools/renewal/T05.008/test-work in this checkout). JavaScript is only parsed
(`node --check`), never executed here; without node those checks are skipped.
The pinned bootstrap is read as bytes and never executed. The generated
loaders' behavior is covered by test_navigation_browser_cache.mjs; native SRI
enforcement and every browser/cache action are root-owned and NOT RUN here.
"""

import copy
import hashlib
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
import navigation_browser_verifier as gen  # noqa: E402

GENERATOR = HERE / "navigation_browser_verifier.py"
MODULE = HERE / "navigation_browser_cache.mjs"
INPUT_ROOT = os.environ.get("T05_008_INPUT_ROOT")
WORK = Path(os.environ.get("T05_008_WORK") or HERE.parent.parent / ".tools/renewal/T05.008/test-work")
NODE = shutil.which("node")
FROZEN_SHA = "f0607e20948fb7d9b8115234c469aa4b91376d769b5678d1c718b16c9687d6da"
FIVE = ["T05_008-cache.html", "T05_008-cache.mjs", "T05_008-original-entry.html",
        "T05_008-repaired-entry.html", "verification-manifest.json"]
MARKER = b"import('./' + scriptFile)"


def sha(data):
    return hashlib.sha256(data).hexdigest()


# An authored stand-in bootstrap: same marker and the bootstrap's then/catch
# shape, small enough to build per test. Not the pinned api.html.
FIX_API = (
    b"<!DOCTYPE html>    \n<html><body>    \n<script>    \n"
    b"function loadApp(appName) {    \n"
    b"    var scriptFile = 'Online.js';    \n"
    b"    import('./' + scriptFile).then(function() {    \n"
    b"        document.title = 'ok';    \n"
    b"    }).catch(function(err) { console.error('Failed to load app:', scriptFile, err); });    \n"
    b"}    \n</script>    \n</body></html>    \n"
)


def fixture_profile(api=FIX_API):
    profile = copy.deepcopy(gen.PROFILE)
    profile["api_html"]["bytes"] = len(api)
    profile["api_html"]["sha256"] = sha(api)
    return profile


class Work(unittest.TestCase):
    def setUp(self):
        WORK.mkdir(parents=True, exist_ok=True)
        self.dir = Path(tempfile.mkdtemp(prefix="case-", dir=str(WORK)))
        self.addCleanup(shutil.rmtree, str(self.dir), True)

    def write(self, name, data, mode=0o400):
        path = self.dir / name
        path.write_bytes(data)
        os.chmod(str(path), mode)
        return path

    def check_tree(self, out, api, profile):
        st = os.lstat(str(out))
        self.assertTrue(stat.S_ISDIR(st.st_mode))
        self.assertEqual(stat.S_IMODE(st.st_mode), 0o700)
        self.assertEqual(sorted(os.listdir(str(out))), FIVE)
        files = {}
        for name in FIVE:
            fst = os.lstat(str(out / name))
            self.assertTrue(stat.S_ISREG(fst.st_mode))
            self.assertEqual(stat.S_IMODE(fst.st_mode), 0o600, name)
            files[name] = (out / name).read_bytes()
        module = MODULE.read_bytes()
        self.assertEqual(files["T05_008-cache.mjs"], module)
        raw = files["verification-manifest.json"]
        manifest = json.loads(raw)
        self.assertEqual(gen.canonical(manifest), raw)
        self.assertEqual(manifest["schema"], 1)
        self.assertEqual(manifest["task"], "T05.008")
        self.assertEqual(manifest["profile"], "fixed-navigation-browser-verifier-v1")
        self.assertEqual(manifest["source_api_html"], {"bytes": len(api), "sha256": sha(api)})
        self.assertEqual(manifest["cache_module"]["sha256"], sha(module))
        self.assertEqual(manifest["cache_module"]["bytes"], len(module))
        self.assertEqual(sorted(manifest["artifacts"]), FIVE[:4])
        for name in FIVE[:4]:
            self.assertEqual(manifest["artifacts"][name], {"bytes": len(files[name]), "sha256": sha(files[name])})
        start = api.index(MARKER)
        end = start + len(MARKER)
        for stage, name in (("original", FIVE[2]), ("repaired", FIVE[3])):
            page = files[name]
            # Full unchanged prefix and suffix; only the expression window differs.
            self.assertEqual(page[:start], api[:start])
            self.assertEqual(page[len(page) - (len(api) - end):], api[end:])
            middle = page[start:len(page) - (len(api) - end)].decode("utf-8")
            self.assertEqual(middle, gen.entry_expression(stage, profile))
            pin = profile["bundles"][stage]
            self.assertIn("'%s'" % pin["sha256"], middle)
            self.assertIn("'%s'" % gen.sri(pin["sha256"]), middle)
            other = profile["bundles"]["repaired" if stage == "original" else "original"]["sha256"]
            self.assertNotIn(other, middle)
            self.assertNotIn(MARKER, page)
        cache = files["T05_008-cache.html"].decode("utf-8")
        self.assertIn("'%s'" % gen.sri(sha(module)), cache)
        for element in ("T05_008-cache-report", "inspect-cache", "remove-verified-cache",
                        "refresh-http-original", "refresh-http-repaired"):
            self.assertEqual(cache.count('id="%s"' % element), 1)
        self.assertNotIn("http://", cache.replace(profile["origin"], ""))
        return files

    def node_check(self, source, name):
        if not NODE:
            self.skipTest("node unavailable: parse-only checks not run")
        path = self.dir / name
        path.write_text(source, encoding="utf-8")
        result = subprocess.run([NODE, "--check", str(path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def check_syntax(self, files):
        for name in (FIVE[2], FIVE[3]):
            text = files[name].decode("utf-8")
            scripts = [part.split("</script>", 1)[0] for part in text.split("<script>")[1:]]
            self.assertTrue(scripts)
            for i, script in enumerate(scripts):
                self.node_check(script, "%s.%d.js" % (name, i))
        self.node_check(gen.cache_inline_script(files[FIVE[0]]), "cache-inline.js")
        if NODE:
            result = subprocess.run([NODE, "--check", str(MODULE)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


# ------------------------------------------------------------------ G01


@unittest.skipUnless(INPUT_ROOT, "T05_008_INPUT_ROOT not set: production-input checks not run")
class G01Production(Work):
    def test_frozen_inputs_are_intact_and_unmutated(self):
        root = Path(INPUT_ROOT)
        manifest_path = root / "frozen-inputs.json"
        raw = manifest_path.read_bytes()
        self.assertEqual((len(raw), sha(raw)), (1253, FROZEN_SHA))
        self.assertEqual(stat.S_IMODE(os.lstat(str(root)).st_mode), 0o700)
        manifest = json.loads(raw)
        self.assertEqual(manifest["task"], "T05.008")
        self.assertEqual(len(manifest["files"]), 8)
        for item in manifest["files"]:
            path = root / item["path"]
            st = os.lstat(str(path))
            self.assertTrue(stat.S_ISREG(st.st_mode), item["path"])
            self.assertEqual(stat.S_IMODE(st.st_mode), 0o400, item["path"])
            data = path.read_bytes()
            self.assertEqual((len(data), sha(data)), (item["bytes"], item["sha256"]), item["path"])
            self.assertEqual(stat.S_IMODE(os.lstat(str(path.parent)).st_mode), 0o700)
        profile = (root / "profile.json").read_bytes()
        self.assertEqual(profile, gen.PROFILE_TEXT.encode("utf-8"))

    def test_production_generation(self):
        api_path = Path(INPUT_ROOT) / "api.html"
        api = api_path.read_bytes()
        before = os.lstat(str(api_path))
        out = self.dir / "out"
        result = subprocess.run([sys.executable, "-I", "-B", str(GENERATOR), str(api_path), str(out)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        line = json.loads(result.stdout)
        self.assertEqual(line["state"], "generated")
        self.assertEqual(line["files"], 5)
        self.assertEqual(line["manifest_sha256"], sha((out / FIVE[4]).read_bytes()))
        files = self.check_tree(out, api, gen.PROFILE)
        self.check_syntax(files)
        after = os.lstat(str(api_path))
        self.assertEqual((before.st_mtime_ns, before.st_size, stat.S_IMODE(after.st_mode)),
                         (after.st_mtime_ns, after.st_size, 0o400))
        # Deterministic: a second output holds identical bytes.
        out2 = self.dir / "out2"
        gen.build(str(api_path), str(out2))
        for name in FIVE:
            self.assertEqual((out / name).read_bytes(), (out2 / name).read_bytes(), name)
        # An existing OUTPUT is refused and left untouched.
        again = subprocess.run([sys.executable, "-I", "-B", str(GENERATOR), str(api_path), str(out)],
                               capture_output=True, text=True)
        self.assertEqual(again.returncode, 1)
        self.assertIn("OUTPUT already exists", again.stderr)
        self.assertEqual(sorted(os.listdir(str(out))), FIVE)

    def test_production_bootstrap_window(self):
        api = (Path(INPUT_ROOT) / "api.html").read_bytes()
        self.assertEqual(api.count(MARKER), 1)
        page = gen.entry_page(api, "original")
        self.assertEqual(len(page) - len(api), len(gen.entry_expression("original")) - len(MARKER))


# ------------------------------------------------------------------ G02


class G02Refusals(Work):
    def build(self, api_path, out, profile=None, module=MODULE):
        return gen.build(str(api_path), str(out), profile or fixture_profile(), module)

    def test_fixture_generation_and_syntax(self):
        api = self.write("api.html", FIX_API)
        out = self.dir / "out"
        manifest, digest = self.build(api, out)
        self.assertEqual(digest, sha((out / FIVE[4]).read_bytes()))
        files = self.check_tree(out, FIX_API, fixture_profile())
        self.check_syntax(files)

    def assertRefused(self, message, api_path, out, **kw):
        with self.assertRaises(gen.VerifierError) as caught:
            self.build(api_path, out, **kw)
        self.assertIn(message, str(caught.exception))
        self.assertFalse(os.path.lexists(str(out)) and out.name == "fresh")
        return caught.exception

    def test_wrong_size_hash_or_marker(self):
        out = self.dir / "fresh"
        self.assertRefused("wrong size", self.write("big.html", FIX_API + b" "), out)
        flipped = FIX_API.replace(b"ok", b"no")
        self.assertRefused("not the pinned bootstrap", self.write("hash.html", flipped), out)
        none = FIX_API.replace(MARKER, b"import('./' + scriptFil3)")
        self.assertRefused("exactly one import expression", self.write("none.html", none), out,
                           profile=fixture_profile(none))
        two = FIX_API + MARKER
        self.assertRefused("exactly one import expression", self.write("two.html", two), out,
                           profile=fixture_profile(two))
        self.assertFalse(os.path.lexists(str(out)))

    def test_links_and_specials_refused(self):
        api = self.write("api.html", FIX_API)
        link = self.dir / "link.html"
        os.symlink(str(api), str(link))
        out = self.dir / "fresh"
        self.assertRefused("not a regular file", link, out)
        directory = self.dir / "dir.html"
        directory.mkdir()
        self.assertRefused("not a regular file", directory, out)
        fifo = self.dir / "fifo.html"
        os.mkfifo(str(fifo))
        self.assertRefused("not a regular file", fifo, out)
        self.assertRefused("unavailable", self.dir / "absent.html", out)
        self.assertFalse(os.path.lexists(str(out)))

    def test_existing_output_refused_untouched(self):
        api = self.write("api.html", FIX_API)
        existing = self.dir / "existing"
        existing.mkdir()
        (existing / "keep").write_bytes(b"x")
        self.assertRefused("OUTPUT already exists", api, existing)
        self.assertEqual(os.listdir(str(existing)), ["keep"])
        afile = self.write("afile", b"y", 0o600)
        self.assertRefused("OUTPUT already exists", api, afile)
        self.assertEqual(afile.read_bytes(), b"y")
        dangling = self.dir / "dangling"
        os.symlink(str(self.dir / "nowhere"), str(dangling))
        self.assertRefused("OUTPUT already exists", api, dangling)
        self.assertFalse(os.path.exists(str(self.dir / "nowhere")))
        self.assertRefused("OUTPUT parent unavailable", api, self.dir / "missing" / "out")

    def test_inputs_validated_before_output_created(self):
        out = self.dir / "fresh"
        bad = self.write("bad.html", FIX_API.replace(b"ok", b"no"))
        self.assertRefused("not the pinned bootstrap", bad, out)
        self.assertFalse(os.path.lexists(str(out)))
        api = self.write("api.html", FIX_API)
        module = self.write("module.mjs", MODULE.read_bytes().replace(
            b"3e896b2ba29de46f40ab36e43917359b376612ef00b3b4c0e2eb0cc81cb95471", b"0" * 64))
        self.assertRefused("fixed profile pins", api, out, module=module)
        self.assertFalse(os.path.lexists(str(out)))
        self.assertRefused("unavailable", api, out, module=self.dir / "no-module.mjs")
        self.assertFalse(os.path.lexists(str(out)))

    def test_write_failure_leaves_no_partial_output(self):
        api = self.write("api.html", FIX_API)
        out = self.dir / "fresh"
        real_write = os.write
        calls = {"n": 0}

        def failing(fd, data):
            calls["n"] += 1
            if calls["n"] == 3:
                raise OSError(28, "No space left on device")
            return real_write(fd, data)

        with mock.patch.object(gen.os, "write", failing):
            error = self.assertRefused("writing OUTPUT failed", api, out)
        self.assertIn("No space left", str(error))
        self.assertFalse(os.path.lexists(str(out)))

        def short(fd, data):
            return 0

        with mock.patch.object(gen.os, "write", short):
            self.assertRefused("writing OUTPUT failed", api, out)
        self.assertFalse(os.path.lexists(str(out)))

        real_close = os.close
        state = {"n": 0}

        def failing_close(fd):
            state["n"] += 1
            real_close(fd)
            if state["n"] == state["at"]:
                raise OSError(5, "Input/output error")

        # Closes 1-2 are the two inputs; close 4 is the second output file.
        for failing_at, message in ((1, "API_HTML unreadable"), (2, "module unreadable"), (4, "writing OUTPUT failed")):
            state["n"] = 0
            state["at"] = failing_at
            with mock.patch.object(gen.os, "close", failing_close):
                self.assertRefused(message, api, out)
            self.assertFalse(os.path.lexists(str(out)))

    def test_final_directory_close_is_bounded_and_never_retried(self):
        api = self.write("api.html", FIX_API)
        out = self.dir / "failed-close"
        real_close = os.close
        closes = []

        def fail_directory(fd):
            directory = stat.S_ISDIR(os.fstat(fd).st_mode)
            real_close(fd)
            if directory:
                closes.append(fd)
                raise OSError(5, "Input/output error")

        with mock.patch.object(gen.os, "close", fail_directory):
            with self.assertRaises(gen.VerifierError) as caught:
                self.build(api, out)
        self.assertIn("closing OUTPUT failed", str(caught.exception))
        self.assertEqual(len(closes), 1)
        # A failed output may remain. It is never a completion marker and
        # even a fully written failed tree must not be reused/overwritten.
        self.assertEqual(sorted(p.name for p in out.iterdir()), FIVE)
        self.assertRefused("OUTPUT already exists", api, out)

    def test_cli_usage_and_refusal(self):
        for args in ([], ["one"], ["a", "b", "c"], ["-h", "x"], ["x", "--out"]):
            result = subprocess.run([sys.executable, "-I", "-B", str(GENERATOR)] + args,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, args)
            self.assertIn("usage:", result.stderr)
        api = self.write("api.html", FIX_API)
        result = subprocess.run([sys.executable, "-I", "-B", str(GENERATOR), str(api), str(self.dir / "o")],
                                capture_output=True, text=True)
        # The production CLI has no profile override: the fixture is refused.
        self.assertEqual(result.returncode, 1)
        self.assertIn("not the pinned bootstrap", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotIn(str(self.dir), result.stderr)
        self.assertFalse(os.path.lexists(str(self.dir / "o")))


# ------------------------------------------------------------------ G03


class G03Profile(Work):
    def test_embedded_profile(self):
        data = gen.PROFILE_TEXT.encode("utf-8")
        self.assertEqual((len(data), sha(data)), (2153, gen.PROFILE_SHA256))
        self.assertEqual(gen.canonical(json.loads(data)), data)
        self.assertEqual(gen.PROFILE["origin"], "http://127.0.0.1:3338")
        self.assertEqual(gen.PROFILE["output_files"], FIVE)
        self.assertEqual(len(gen.PROFILE["targets"]), 6)

    def test_sri(self):
        self.assertEqual(gen.sri(gen.PROFILE["bundles"]["original"]["sha256"]),
                         "sha256-gPQ3HMjaK7VEMuRufjTfr3rMVkRLKMb7xqmca6IpM+o=")
        self.assertEqual(gen.sri(gen.PROFILE["bundles"]["repaired"]["sha256"]),
                         "sha256-a6hUy2exMGytuQWxuJp6HqyYzX5ckSGW5vh99BpcTC8=")

    def test_entry_expression_shape(self):
        for stage in ("original", "repaired"):
            expr = gen.entry_expression(stage)
            self.assertTrue(expr.startswith("(function (scriptFile) {"))
            self.assertTrue(expr.endswith("})(scriptFile)"))
            self.assertEqual(expr.count("document.createElement('script')"), 1)
            self.assertEqual(expr.count("script.integrity = INTEGRITY"), 1)
            self.assertIn("script.crossOrigin = 'anonymous'", expr)
            self.assertIn("script.type = 'module'", expr)
            self.assertLess(expr.index("addEventListener('load'"), expr.index("appendChild(script)"))
            self.assertLess(expr.index("addEventListener('error'"), expr.index("appendChild(script)"))
            lowered = expr.lower()
            for bad in ("import(", "eval(", "new function", "blob", "createobjecturl", "</script",
                        "config.local", "localstorage", "preferences", "worker"):
                self.assertNotIn(bad, lowered)
        self.node_check("var scriptFile = 'Online.js';\n" + gen.entry_expression("original") + ";\n", "expr.js")


if __name__ == "__main__":
    unittest.main()
