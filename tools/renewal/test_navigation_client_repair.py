"""Tests for navigation_client_repair (T05.007). Five groups, G01-G05.

    T05_007_INPUT_ROOT=<frozen input root> \
        python3 -I -B -m unittest -v tools/renewal/test_navigation_client_repair.py

G01 needs the frozen read-only input root (the directory holding
frozen-inputs.json); without it its tests are reported as skipped, never
passed. Everything else runs on tiny authored fixtures under T05_007_WORK
(default: .tools/renewal/T05.007/test-work in this checkout). The stock chunks
are only streamed/hashed/copied, never decoded. JavaScript is only parsed
(`node --check`), never executed; without node those checks are skipped.
No Lua, WASM, browser or game code runs here.
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
import navigation_client_repair as gen  # noqa: E402

GENERATOR = HERE / "navigation_client_repair.py"
INPUT_ROOT = os.environ.get("T05_007_INPUT_ROOT")
WORK = Path(os.environ.get("T05_007_WORK") or HERE.parent.parent / ".tools/renewal/T05.007/test-work")
NODE = shutil.which("node")
FROZEN_SHA = "3870f637728ad03aaa026956e8b20b3f52a1c2516f46a2a0528757efb39427db"
PACKAGE = "tw-navigation-request-compat"
NAV_DIR = PACKAGE + "/data/luafiles514/lua files/navigation"
ROLES = ("map", "mob", "npc", "link", "linkdistance", "npcdistance")
EIGHT = sorted(["Online.js", PACKAGE + "/mod.json"]
               + [NAV_DIR + "/navi_%s_krpri.lub" % role for role in ROLES])
DIRS = [".", PACKAGE, PACKAGE + "/data", PACKAGE + "/data/luafiles514",
        PACKAGE + "/data/luafiles514/lua files", NAV_DIR]

# An authored stand-in for the loader window: the same signature, anchors and
# legacy callback shape, small enough to rebuild per test. Not the real bundle.
FIX_WINDOW = (
    b"function loadLuaValue(file_path, variable_name, callback, onEnd) {\n"
    b"\ttry {\n"
    b"\t\tClient.loadFile(file_path, async function(file) {\n"
    b"\t\t\ttry {\n"
    b"\t\t\t\tawait lua.doFile(file_path);\n"
    b"\t\t\t\tconst ctx = lua.ctx;\n"
    b"\t\t\t\tlet result = null;\n"
    b"\t\t\t\tctx.extractValue = (value) => {\n"
    b"\t\t\t\t\tresult = JSON.parse(userStringDecoder.decode(value, userCharpage));\n"
    b"\t\t\t\t};\n"
    b"\t\t\t\tlua.doStringSync(String.raw`extractValue(to_json(${variable_name}))`);\n"
    b"\t\t\t\tlua.unmountFile(file_path);\n"
    b"\t\t\t\tcallback.call(null, result);\n"
    b"\t\t\t} catch (hException) {\n"
    b"\t\t\t\tcallback.call(null, null);\n"
    b"\t\t\t} finally {\n"
    b"\t\t\t\tif (onEnd) onEnd.call();\n"
    b"\t\t\t}\n"
    b"\t\t}, function() {});\n"
    b"\t} catch (e) {\n"
    b"\t\tif (onEnd) onEnd.call();\n"
    b"\t}\n"
    b"}")
FIX_QUEUE = b"let fixtureQueue = [];\n"
FIX_LOADER_HEAD = b"function navigationServerLinks(v) { return \"\"; }\nfunction navigationNameSwap(v) { return \"\"; }\n"
FIX_ENTRY = b"function fixtureEntry() { return 6; }\n"
FIX_TAIL = b"\n/**\n* Loads System/mapInfo.lub\n*/\n"
FIX_HEAD = (b"// authored fixture bundle, not Online.js\nvar lua, userStringDecoder, userCharpage, Client;\n"
            + FIX_QUEUE)
FIX_BUNDLE = FIX_HEAD + FIX_LOADER_HEAD + FIX_WINDOW + FIX_TAIL + FIX_ENTRY
# Opaque authored chunk bytes; one larger than any streaming chunk used below.
FIX_CHUNKS = {role: (b"\x1bLuaQ\x00 fixture " + role.encode() + b" \xb3\x5c u005c \\ \x00")
              * (40 if role == "npcdistance" else 3) for role in ROLES}


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


def fixture_profile(bundle=FIX_BUNDLE, chunks=None, window=FIX_WINDOW):
    """The production profile with only the pins/offsets moved to the fixtures."""
    chunks = FIX_CHUNKS if chunks is None else chunks
    profile = copy.deepcopy(gen.PROFILE)
    for pin in profile["inputs"]:
        data = bundle if pin["role"] == "bundle" else chunks[pin["role"]]
        pin["bytes"], pin["sha256"] = len(data), sha(data)
    start = bundle.index(window)
    end = start + len(window)
    win = profile["window"]
    win.update(start_byte=start, end_byte_exclusive=end, sha256=sha(bundle[start:end]),
               prefix_sha256=sha(bundle[:start]), suffix_sha256=sha(bundle[end:]))

    def region(name, first, after):
        profile[name] = {"start_byte": first, "end_byte_exclusive": after, "sha256": sha(bundle[first:after])}
    q = bundle.index(FIX_QUEUE)
    region("queue_extraction", q, q + len(FIX_QUEUE))
    region("loader_extraction", bundle.index(FIX_LOADER_HEAD), end)
    e = bundle.index(FIX_ENTRY)
    region("entry_extraction", e, e + len(FIX_ENTRY))
    return profile


def open_fds():
    return set(os.listdir("/dev/fd"))


def snapshot(path):
    st = os.lstat(path)
    return (st.st_ino, st.st_size, st.st_mtime_ns, stream_sha(path))


def node_check(test, data, name):
    """Parse-only check of generated JavaScript as an ES module."""
    if not NODE:
        test.skipTest("node is unavailable; parse-only check unrun")
    target = Path(test.dir) / name
    target.write_bytes(data)
    run = subprocess.run([NODE, "--check", str(target)], capture_output=True, timeout=120)
    test.assertEqual(run.returncode, 0, run.stderr.decode("utf-8", "replace")[:400])


def strip_repair(window, profile):
    """Undo the three insertions; what remains must be the original window."""
    helpers = gen.navigation_helpers(profile)
    head = profile["window"]["start_marker"].encode() + b"\n"
    assert window.startswith(head + helpers)
    rest = head + window[len(head) + len(helpers):]
    assert rest.count(gen.BRANCH_OPEN) == 1 and rest.count(gen.BRANCH_CLOSE + gen.BRANCH_CLOSE_AT) == 1
    rest = rest.replace(gen.BRANCH_OPEN, b"", 1)
    return rest.replace(gen.BRANCH_CLOSE + gen.BRANCH_CLOSE_AT, gen.BRANCH_CLOSE_AT, 1)


class Work(unittest.TestCase):
    """Fresh private directory per test; fixture inputs written there."""

    def setUp(self):
        WORK.mkdir(parents=True, exist_ok=True)
        self.dir = Path(tempfile.mkdtemp(prefix="t-", dir=os.path.realpath(WORK)))
        os.chmod(self.dir, 0o700)
        self.bundle = self.dir / "Online.js"
        self.bundle.write_bytes(FIX_BUNDLE)
        self.tables = self.dir / "navigation"
        self.tables.mkdir()
        for pin in gen.PROFILE["inputs"]:
            if pin["role"] != "bundle":
                (self.tables / pin["file"]).write_bytes(FIX_CHUNKS[pin["role"]])
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

    def table(self, role):
        return self.tables / ("navi_%s_tw.lub" % role)

    def sources(self):
        return [self.bundle] + [self.table(role) for role in ROLES]

    def build(self, out=None, bundle=None, tables=None, profile=None):
        return gen.build(str(bundle or self.bundle), str(tables or self.tables),
                         str(out or self.out), profile=profile or self.profile)

    def refused(self, out=None, **kwargs):
        """Expect a RepairError, no new output, sources unchanged, no leak."""
        target = Path(out or self.out)
        before = {p: snapshot(p) for p in self.sources() if os.path.lexists(p) and not os.path.islink(p)
                  and stat.S_ISREG(os.lstat(p).st_mode)}
        existed = os.path.lexists(target)
        with self.assertRaises(gen.RepairError) as caught:
            self.build(out=out, **kwargs)
        if not existed:
            self.assertFalse(os.path.lexists(target), "refusal left an output entry")
        self.assertEqual({p: snapshot(p) for p in before}, before, "a source changed")
        self.assertEqual(open_fds(), self.fds, "descriptor leaked")
        self.assertNotIn(str(self.dir), str(caught.exception), "diagnosis carries a private path")
        return str(caught.exception)

    def fail_build(self, **kwargs):
        with self.assertRaises(gen.RepairError) as caught:
            self.build(**kwargs)
        self.assertNotIn(str(self.dir), str(caught.exception))
        return str(caught.exception)

    def failed(self, out=None):
        """After a mid-run failure: owned output gone, no descriptor leaked."""
        self.assertFalse(os.path.lexists(out or self.out), "owned output was not removed")
        self.assertEqual(open_fds(), self.fds, "descriptor leaked")

    def nth(self, name, n, action):
        """Patch os.<name> so its n-th call (1-based) runs action(real, *args)."""
        real = getattr(os, name)
        state = {"calls": 0}

        def wrapper(*args, **kwargs):
            state["calls"] += 1
            if state["calls"] == n:
                return action(real, *args, **kwargs)
            return real(*args, **kwargs)
        return mock.patch.object(gen.os, name, wrapper)

    @staticmethod
    def eio(*_a, **_k):
        raise OSError(errno.EIO, os.strerror(errno.EIO))


def assert_output(test, root, profile, bundle_bytes, chunk_bytes, generator_path=GENERATOR):
    """Exact ten-file tree, modes, bytes, JSON schema and bindings."""
    root = Path(root)
    files, dirs = [], []
    for current, subdirs, names in os.walk(root):
        rel = os.path.normpath(os.path.relpath(current, root))
        dirs.append(rel)
        for name in names:
            files.append(os.path.normpath(os.path.join(rel, name)))
        for d in subdirs:
            test.assertFalse(os.path.islink(os.path.join(current, d)))
    test.assertEqual(sorted(dirs), sorted(DIRS))
    test.assertEqual(sorted(files), sorted(EIGHT + ["COMPLETE.json", "repair-manifest.json"]))
    for d in dirs:
        st = os.lstat(root / d)
        test.assertTrue(stat.S_ISDIR(st.st_mode))
        test.assertEqual(stat.S_IMODE(st.st_mode), 0o700, d)
    for f in files:
        st = os.lstat(root / f)
        test.assertTrue(stat.S_ISREG(st.st_mode), f)
        test.assertEqual(stat.S_IMODE(st.st_mode), 0o600, f)

    mod = (root / PACKAGE / "mod.json").read_bytes()
    test.assertEqual(mod, (json.dumps(profile["package"], ensure_ascii=False, sort_keys=True,
                                      indent=2) + "\n").encode("utf-8"))
    test.assertEqual((len(mod), sha(mod)), (278, "f207ec962995a4f9d5bc09b71d93ecea8528ca44ed90ec359c6188c86471c336"))
    test.assertFalse(mod.startswith(b"\xef\xbb\xbf"))
    for request in profile["requests"]:
        test.assertEqual((root / request["target"]).read_bytes(), chunk_bytes[request["role"]])

    repaired = (root / "Online.js").read_bytes()
    win = profile["window"]
    start, end = win["start_byte"], win["end_byte_exclusive"]
    test.assertEqual(repaired[:start], bundle_bytes[:start])
    test.assertTrue(repaired.endswith(bundle_bytes[end:]))
    new_window = repaired[start:len(repaired) - (len(bundle_bytes) - end)]
    test.assertEqual(strip_repair(new_window, profile), bundle_bytes[start:end])

    manifest_bytes = (root / "repair-manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    test.assertEqual(manifest_bytes, gen.canonical(manifest), "manifest is not canonical")
    test.assertEqual(sorted(manifest), ["files", "generator", "inputs", "package", "profile", "schema", "task"])
    test.assertEqual((manifest["schema"], manifest["task"], manifest["profile"]),
                     (1, "T05.007", "tw-navigation-repair-v1"))
    source = Path(generator_path).read_bytes()
    test.assertEqual(manifest["generator"], {"file": "navigation_client_repair.py",
                                             "bytes": len(source), "sha256": sha(source)})
    test.assertEqual(manifest["inputs"], profile["inputs"])
    test.assertEqual(manifest["package"], profile["package"])
    test.assertEqual([r["path"] for r in manifest["files"]], EIGHT)
    for record in manifest["files"]:
        test.assertEqual(sorted(record), ["bytes", "mode", "path", "sha256"])
        test.assertEqual(record["mode"], "0600")
        test.assertEqual(stream_sha(root / record["path"]), (record["bytes"], record["sha256"]))
    for private in (b"/Users/", b"/private/", b"/tmp/", b"/home/"):
        test.assertNotIn(private, manifest_bytes)

    complete_bytes = (root / "COMPLETE.json").read_bytes()
    complete = json.loads(complete_bytes)
    test.assertEqual(complete_bytes, gen.canonical(complete))
    test.assertEqual(complete, {
        "schema": 1, "task": "T05.007", "profile": "tw-navigation-repair-v1",
        "state": "complete", "files": 8,
        "manifest": {"file": "repair-manifest.json", "bytes": len(manifest_bytes),
                     "sha256": sha(manifest_bytes)}})
    return manifest, new_window


def tree_bytes(root):
    root = Path(root)
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


# ------------------------------------------------------------------ G01


@unittest.skipUnless(INPUT_ROOT, "G01 needs T05_007_INPUT_ROOT (frozen input root); unrun")
class G01PinnedGeneration(Work):
    """Actual CLI on the pinned bundle and six chunks; unchanged inputs; repeatable."""

    def real(self, name):
        return os.path.join(INPUT_ROOT, name)

    def test_frozen_manifest_and_profile_match_generator(self):
        frozen = Path(self.real("frozen-inputs.json")).read_bytes()
        self.assertEqual((len(frozen), sha(frozen)), (3790, FROZEN_SHA))
        listed = {f["file"]: f for f in json.loads(frozen)["files"]}
        self.assertEqual(len(listed), 23)
        for name, record in listed.items():
            path = self.real(name)
            st = os.lstat(path)
            self.assertTrue(stat.S_ISREG(st.st_mode), name)
            self.assertEqual(stat.S_IMODE(st.st_mode), 0o400, name)
            self.assertEqual(stream_sha(path), (record["bytes"], record["sha256"]), name)
        profile = Path(self.real("profile.json")).read_bytes()
        self.assertEqual(profile, gen.PROFILE_TEXT.encode("utf-8"))
        self.assertEqual(sha(profile), gen.PROFILE_SHA256)
        for pin in gen.PROFILE["inputs"]:
            name = pin["file"] if pin["role"] == "bundle" else "navigation/" + pin["file"]
            self.assertEqual((listed[name]["bytes"], listed[name]["sha256"]), (pin["bytes"], pin["sha256"]))

    def test_cli_generation_exact_unchanged_and_deterministic(self):
        bundle, tables = self.real("Online.js"), self.real("navigation")
        before = {p: snapshot(p) for p in [bundle] + [os.path.join(tables, n) for n in os.listdir(tables)]}
        outputs = []
        for name in ("run-1", "run-2"):
            run = subprocess.run([sys.executable, "-I", "-B", str(GENERATOR), bundle, tables,
                                  str(self.dir / name)], capture_output=True, timeout=600)
            self.assertEqual(run.returncode, 0, run.stderr[:400])
            self.assertEqual(run.stderr, b"")
            value = json.loads(run.stdout)
            self.assertTrue(run.stdout.endswith(b"\n") and run.stdout.count(b"\n") == 1)
            self.assertEqual(sorted(value), ["files", "manifest_sha256", "output", "state", "task"])
            manifest = (self.dir / name / "repair-manifest.json").read_bytes()
            self.assertEqual(value, {"task": "T05.007", "state": "complete", "output": name,
                                     "files": 8, "manifest_sha256": sha(manifest)})
            outputs.append(tree_bytes(self.dir / name))
        self.assertEqual(outputs[0], outputs[1], "repeated generation differs")
        self.assertEqual({p: snapshot(p) for p in before}, before, "an input changed")
        original = Path(bundle).read_bytes()
        chunks = {r["role"]: Path(tables, gen.PROFILE["inputs"][i + 1]["file"]).read_bytes()
                  for i, r in enumerate(gen.PROFILE["requests"])}
        _, window = assert_output(self, self.dir / "run-1", gen.PROFILE, original, chunks)
        self.assertIn(original[10728454:10730646], window, "legacy conversion is not byte-identical")
        repaired = outputs[0]["Online.js"]
        node_check(self, repaired[10727952:10727952 + len(window)] + b"\n", "window.mjs")
        node_check(self, repaired, "bundle.mjs")

    def test_real_window_shape(self):
        original = Path(self.real("Online.js")).read_bytes()
        win = gen.PROFILE["window"]
        window = gen.repair_window(original[win["start_byte"]:win["end_byte_exclusive"]], gen.PROFILE)
        self.assertEqual(strip_repair(window, gen.PROFILE), original[win["start_byte"]:win["end_byte_exclusive"]])
        # The six request sites, helpers and queue are outside the window and unchanged.
        repaired = gen.repair_bundle(original, gen.PROFILE)
        shift = len(repaired) - len(original)
        for call in (b'loadLuaValue(DB.LUA_PATH + "navigation/navi_%s_krpri.lub"' % r.encode() for r in ROLES):
            self.assertEqual(original.count(call), 1)
            self.assertEqual(repaired.find(call), original.find(call) + shift)
        for helper in (b"function navigationNamesTurn()", b"function navigationServerLinks(variableName)",
                       b"function navigationNameSwap(variableName)", b"const NAVIGATION_NAME_COLUMNS = {"):
            self.assertEqual(repaired.find(helper), original.find(helper))

    def test_production_refuses_a_wrong_bundle(self):
        # Fixture bytes at the pinned names: the production pins refuse them.
        with self.assertRaises(gen.RepairError) as caught:
            gen.build(str(self.bundle), self.real("navigation"), str(self.out))
        self.assertIn("size differs", str(caught.exception))
        self.failed()


# ------------------------------------------------------------------ G02


class G02RepairShape(Work):
    """The repaired window: bounded insertions, exact guard, unchanged legacy path."""

    def window(self, profile=None):
        profile = profile or self.profile
        out = gen.repair_bundle(FIX_BUNDLE, profile)
        start = profile["window"]["start_byte"]
        return out[start:len(out) - (len(FIX_BUNDLE) - profile["window"]["end_byte_exclusive"])], out

    def test_insertions_are_the_only_change(self):
        window, out = self.window()
        self.assertEqual(strip_repair(window, self.profile), FIX_WINDOW)
        legacy = FIX_WINDOW[FIX_WINDOW.index(gen.BRANCH_OPEN_AT):FIX_WINDOW.index(gen.BRANCH_CLOSE_AT)]
        self.assertIn(gen.BRANCH_OPEN + legacy + gen.BRANCH_CLOSE + gen.BRANCH_CLOSE_AT, window)
        self.assertTrue(out.startswith(FIX_HEAD + FIX_LOADER_HEAD))
        self.assertTrue(out.endswith(FIX_TAIL + FIX_ENTRY))

    def test_guard_is_six_exact_path_global_pairs(self):
        helpers = gen.navigation_helpers(gen.PROFILE).decode("utf-8")
        body = helpers[helpers.index("const navigationRequests = {") + len("const navigationRequests = "):]
        body = body[:body.index("};") + 1]
        self.assertEqual(json.loads(body), {r["global"]: r["path"] for r in gen.PROFILE["requests"]})
        self.assertEqual(len(json.loads(body)), 6)
        self.assertIn("Object.prototype.hasOwnProperty.call(navigationRequests, variable_name) "
                      "&& navigationRequests[variable_name] === file_path", helpers)
        self.assertEqual(helpers.count("navigationTransport"), 1)
        self.assertEqual(gen.BRANCH_OPEN.count(b"navigationTransport"), 1)

    def test_lua_template_is_plain_and_bounded(self):
        helpers = gen.navigation_helpers(gen.PROFILE).decode("utf-8")
        lua = helpers[helpers.index("lua.doStringSync(`") + len("lua.doStringSync(`"):]
        lua = lua[:lua.index("`);")]
        self.assertNotIn("\\", lua, "a backslash would be a JS escape in this template")
        self.assertNotIn("`", lua)
        self.assertEqual(sorted(set(part.split("}")[0] for part in lua.split("${")[1:])),
                         ["navigationNameSwap(variable_name)", "navigationServerLinks(variable_name)",
                          "variable_name"])
        # Every string and string key leaves Lua as hex of its raw bytes.
        self.assertIn('return \'"\' .. (value:gsub(".", hex)) .. \'"\'', lua)
        self.assertIn('return "s" .. (k:gsub(".", hex))', lua)
        self.assertIn('format("%.17g", value)', lua)
        self.assertIn('fail("${variable_name} is not a table")', lua)
        self.assertLess(lua.index("${navigationServerLinks"), lua.index("pcall(function()"))
        self.assertIn('if ok then extractValue(result) else extractValue("!" .. tostring(result)) end', lua)
        self.assertEqual(lua.count("extractValue("), 2)
        self.assertIn('if (json.charAt(0) === "!") throw new Error(', helpers)

    def test_no_forbidden_mechanisms(self):
        helpers = gen.navigation_helpers(gen.PROFILE).decode("utf-8")
        # Comments may explain the defect; code lines may not use these.
        code = "\n".join(l for l in helpers.splitlines() if not l.strip().startswith("//"))
        for forbidden in ("u005c", "replace(", "String.prototype", "JSON.parse =", "setCharset",
                          "iconv", "console.", "normalize(", "import(", "require(", "window.",
                          "globalThis", "catch", "Navi_Data", "localStorage", "setTimeout",
                          "await", "async", "unmountFile", "callback", "onEnd"):
            self.assertNotIn(forbidden, code, forbidden)
        self.assertNotIn(b"\r", gen.navigation_helpers(gen.PROFILE))

    def test_decoding_is_per_string_with_user_charpage(self):
        helpers = gen.navigation_helpers(gen.PROFILE).decode("utf-8")
        self.assertEqual(helpers.count("userStringDecoder.decode(bytes, userCharpage)"), 1)
        self.assertEqual(helpers.count("userStringDecoder"), 1)
        self.assertIn("chunk[j] < 32 || chunk[j] > 126", helpers)

    def test_fixture_bundle_parses(self):
        _, out = self.window()
        node_check(self, out, "fixture-bundle.mjs")

    def test_delimiter_refusals(self):
        renamed = FIX_WINDOW.replace(b"ctx.extractValue = (value) => {\n", b"ctx.other = (value) => {\n")
        doubled = FIX_WINDOW.replace(gen.BRANCH_CLOSE_AT, gen.BRANCH_CLOSE_AT * 2)
        for broken, window, why in (
                (FIX_BUNDLE.replace(FIX_WINDOW, renamed), renamed, "conversion callback"),
                (FIX_BUNDLE.replace(FIX_WINDOW, doubled), doubled, "unmount/callback"),
                (FIX_BUNDLE.replace(FIX_TAIL, FIX_TAIL + FIX_TAIL), FIX_WINDOW, "mapInfo comment"),
                (FIX_BUNDLE.replace(FIX_ENTRY, FIX_ENTRY + b"function loadLuaValue(file_path, variable_name, "
                                    b"callback, onEnd) {\n}\n"), FIX_WINDOW, "loadLuaValue signature")):
            with self.subTest(why=why):
                with self.assertRaises(gen.RepairError) as caught:
                    gen.repair_bundle(broken, fixture_profile(bundle=broken, window=window))
                self.assertIn("unique delimiter", str(caught.exception))
                self.assertIn(why, str(caught.exception))

    def test_region_and_window_pins(self):
        for name in ("queue_extraction", "loader_extraction", "entry_extraction"):
            profile = copy.deepcopy(self.profile)
            profile[name]["sha256"] = "0" * 64
            with self.subTest(region=name), self.assertRaises(gen.RepairError):
                gen.repair_bundle(FIX_BUNDLE, profile)
        for field in ("sha256", "prefix_sha256", "suffix_sha256"):
            profile = copy.deepcopy(self.profile)
            profile["window"][field] = "0" * 64
            with self.subTest(window=field), self.assertRaises(gen.RepairError):
                gen.repair_bundle(FIX_BUNDLE, profile)
        profile = copy.deepcopy(self.profile)
        profile["window"]["start_byte"] += 1
        with self.assertRaises(gen.RepairError):
            gen.repair_bundle(FIX_BUNDLE, profile)


# ------------------------------------------------------------------ G03


class G03Refusals(Work):
    """Inputs and OUTPUT are refused before anything is written."""

    def test_fixture_generation_exact_and_deterministic(self):
        value = self.build()
        manifest = (self.out / "repair-manifest.json").read_bytes()
        self.assertEqual(value, {"task": "T05.007", "state": "complete", "output": "out",
                                 "files": 8, "manifest_sha256": sha(manifest)})
        assert_output(self, self.out, self.profile, FIX_BUNDLE, FIX_CHUNKS)
        self.build(out=self.dir / "again")
        self.assertEqual(tree_bytes(self.out), tree_bytes(self.dir / "again"))
        self.assertEqual(open_fds(), self.fds)

    def test_restrictive_and_permissive_umask(self):
        for mask in (0o777, 0o000):
            old = os.umask(mask)
            try:
                self.build(out=self.dir / ("umask-%03o" % mask))
            finally:
                os.umask(old)
            assert_output(self, self.dir / ("umask-%03o" % mask), self.profile, FIX_BUNDLE, FIX_CHUNKS)

    def test_existing_output_kinds(self):
        self.out.mkdir()
        self.assertIn("already exists", self.refused())
        self.out.rmdir()
        self.out.write_bytes(b"x")
        self.assertIn("already exists", self.refused())
        self.out.unlink()
        os.symlink(self.dir / "missing", self.out)
        self.assertIn("already exists", self.refused())
        self.assertTrue(os.path.islink(self.out))

    def test_output_parent_and_lexical_components(self):
        self.assertIn("does not exist", self.refused(out=self.dir / "no" / "out"))
        (self.dir / "file").write_bytes(b"")
        self.assertIn("not a directory", self.refused(out=self.dir / "file" / "out"))
        for bad in (str(self.dir) + "/./out", str(self.dir) + "/x/../out", str(self.dir) + "//out",
                    str(self.dir) + "/out/"):
            self.assertIn("component", self.refused(out=bad))
        self.assertIn("component", self.refused(bundle=str(self.dir) + "/./Online.js"))
        self.assertIn("component", self.refused(tables=str(self.dir) + "/navigation/../navigation"))
        os.symlink(self.dir, self.dir / "link")
        self.assertIn("symbolic link", self.refused(out=self.dir / "link" / "out"))

    def test_source_symlinks_and_nonregular(self):
        os.symlink(self.bundle, self.dir / "bundle-link")
        self.assertIn("symbolic link", self.refused(bundle=self.dir / "bundle-link"))
        os.symlink(self.tables, self.dir / "tables-link")
        self.assertIn("symbolic link", self.refused(tables=self.dir / "tables-link"))
        target = self.table("mob")
        moved = self.dir / "mob.lub"
        os.rename(target, moved)
        os.symlink(moved, target)
        self.assertIn("symbolic link", self.refused())
        target.unlink()
        os.rename(moved, target)
        self.assertIn("not a regular file", self.refused(bundle=self.tables))
        self.assertIn("not a directory", self.refused(tables=self.bundle))
        self.table("npc").unlink()
        self.table("npc").mkdir()
        self.assertIn("not a regular file", self.refused())

    def test_fifo_and_missing_table_do_not_hang(self):
        self.table("link").unlink()
        self.assertIn("does not exist", self.refused())
        os.mkfifo(self.table("link"))
        self.assertIn("not a regular file", self.refused())
        # A FIFO that slips past path inspection: the non-blocking descriptor
        # is opened without waiting for a writer and refused by fstat.
        with mock.patch.object(gen, "_resolve_source", gen._components):
            with self.assertRaises(gen.RepairError) as caught:
                self.build()
        self.assertIn("descriptor is not a regular file", str(caught.exception))
        self.failed()

    def test_wrong_size_and_hash_per_role(self):
        for pin in self.profile["inputs"]:
            path = self.bundle if pin["role"] == "bundle" else self.tables / pin["file"]
            original = path.read_bytes()
            for mutated, why in ((original + b"!", "size differs"),
                                 (original[:-1] + bytes([original[-1] ^ 1]), "SHA-256 differs")):
                path.write_bytes(mutated)
                with self.subTest(role=pin["role"], why=why):
                    self.assertIn(why, self.refused())
            path.write_bytes(original)

    def test_path_overlap(self):
        self.assertIn("overlap", self.refused(out=self.tables / "out"))
        self.assertIn("already exists", self.refused(out=self.bundle))
        hard = self.tables / "navi_map_tw.lub"
        hard.unlink()
        os.link(self.table("mob"), hard)
        self.assertIn("same file", self.refused(profile=fixture_profile(
            chunks=dict(FIX_CHUNKS, map=FIX_CHUNKS["mob"]))))

    def test_production_cli_has_no_bypass(self):
        run = subprocess.run([sys.executable, "-I", "-B", str(GENERATOR), str(self.bundle),
                              str(self.tables), str(self.out)], capture_output=True, timeout=60,
                             env={"PATH": os.environ.get("PATH", ""), "T05_007_PROFILE": "x"})
        self.assertEqual(run.returncode, 1)
        self.assertEqual(run.stdout, b"")
        self.assertIn(b"size differs", run.stderr)
        self.assertNotIn(b"Traceback", run.stderr)
        self.assertFalse(self.out.exists())
        for args in ([], [str(self.bundle)], [str(self.bundle), str(self.tables), str(self.out), "x"],
                     ["--profile", str(self.tables), str(self.out)]):
            run = subprocess.run([sys.executable, "-I", "-B", str(GENERATOR)] + args,
                                 capture_output=True, timeout=60)
            self.assertEqual(run.returncode, 2, args)
            self.assertEqual(run.stdout, b"")
            self.assertIn(b"usage:", run.stderr)
        self.assertFalse(self.out.exists())

    def test_relative_paths(self):
        cwd = os.getcwd()
        os.chdir(self.dir)
        try:
            gen.build("Online.js", "navigation", "rel-out", profile=self.profile)
        finally:
            os.chdir(cwd)
        assert_output(self, self.dir / "rel-out", self.profile, FIX_BUNDLE, FIX_CHUNKS)


# ------------------------------------------------------------------ G04


class G04PublicationFailures(Work):
    """Real ordinary I/O failures: no success, owned entries removed, foreign kept."""

    def test_short_writes_complete(self):
        real_write = os.write
        with mock.patch.object(gen.os, "write", lambda fd, d: real_write(fd, bytes(d[:7]))):
            self.build()
        assert_output(self, self.out, self.profile, FIX_BUNDLE, FIX_CHUNKS)

    def test_zero_and_failing_write(self):
        with mock.patch.object(gen.os, "write", lambda fd, d: 0):
            self.assertIn("no valid progress", self.fail_build())
        self.failed()
        with mock.patch.object(gen.os, "write", lambda fd, d: len(d) + 1):
            self.assertIn("no valid progress", self.fail_build())
        self.failed()
        for n in (1, 3):  # bundle first, then an alias
            with self.subTest(write=n), self.nth("write", n, lambda real, fd, d: self.eio()):
                self.assertIn("write failed", self.fail_build())
            self.failed()

    def test_fsync_failure_each_file(self):
        # Ten fsyncs: bundle, mod.json, six aliases, manifest, completion partial.
        for n in range(1, 11):
            with self.subTest(fsync=n), self.nth("fsync", n, lambda real, fd: self.eio()):
                self.assertIn("fsync failed", self.fail_build())
            self.failed()

    def test_alias_truncated_or_changed_during_stream(self):
        target = self.table("npcdistance")
        size = len(FIX_CHUNKS["npcdistance"])
        real_read = os.read
        cases = {
            "truncated": (lambda: os.truncate(target, size // 2), "truncated"),
            "later bytes changed": (lambda: target.write_bytes(FIX_CHUNKS["npcdistance"][:-1] + b"?"),
                                    "SHA-256 differs"),
            "consumed prefix changed": (lambda: target.write_bytes(b"?" + FIX_CHUNKS["npcdistance"][1:]),
                                        "changed during the run"),
        }
        for name, (mutate, why) in cases.items():
            state = {"fd": None, "done": False}
            real_open = os.open

            def open_(path, flags, *a, **k):
                fd = real_open(path, flags, *a, **k)
                if str(path) == str(target):
                    state["fd"] = fd
                return fd

            def read(fd, n):
                data = real_read(fd, n)
                if fd == state["fd"] and data and not state["done"] and n < size:
                    state["done"] = True
                    mutate()
                return data
            with self.subTest(case=name), mock.patch.object(gen, "CHUNK", 64), \
                    mock.patch.object(gen.os, "open", open_), mock.patch.object(gen.os, "read", read):
                self.assertIn(why, self.fail_build())
            self.assertTrue(state["done"], name)
            self.failed()
            target.write_bytes(FIX_CHUNKS["npcdistance"])

    def test_bundle_changed_after_read(self):
        real_repair = gen.repair_bundle

        def repair(data, profile):
            self.bundle.write_bytes(FIX_BUNDLE)  # same bytes, new metadata
            return real_repair(data, profile)
        with mock.patch.object(gen, "repair_bundle", repair):
            self.assertIn("changed during the run", self.fail_build())
        self.failed()

    def test_output_corruption_detected_by_readback(self):
        for victim in ("Online.js", NAV_DIR + "/navi_link_krpri.lub", "repair-manifest.json"):
            real_read_back = gen.Output.read_back

            def read_back(output, relative, size, sha256, victim=victim):
                if relative == victim:
                    with open(output.path(relative), "r+b") as fh:
                        first = fh.read(1)
                        fh.seek(0)
                        fh.write(bytes([first[0] ^ 1]))
                return real_read_back(output, relative, size, sha256)
            with self.subTest(victim=victim), mock.patch.object(gen.Output, "read_back", read_back):
                self.assertIn("does not match", self.fail_build())
            self.failed()

    def test_readback_read_failure(self):
        real_open, real_read = os.open, os.read
        state = {"fd": None}

        def open_(path, flags, *a, **k):
            fd = real_open(path, flags, *a, **k)
            if str(path).endswith("/Online.js") and str(self.out) in str(path) and not flags & os.O_CREAT:
                state["fd"] = fd
            return fd

        def read(fd, n):
            if fd == state["fd"]:
                raise OSError(errno.EIO, os.strerror(errno.EIO))
            return real_read(fd, n)
        with mock.patch.object(gen.os, "open", open_), mock.patch.object(gen.os, "read", read):
            self.assertIn("read-back", self.fail_build())
        self.failed()

    def test_close_failure_after_real_close(self):
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
        with mock.patch.object(gen.os, "fsync", fsync_arm), mock.patch.object(gen.os, "close", close):
            self.assertIn("close failed", self.fail_build())
        self.failed()

    def test_final_complete_readback_close_eio_after_real_close(self):
        real_open, real_close = os.open, os.close
        state = {"fd": None, "hit": False}

        def open_(path, flags, *a, **k):
            fd = real_open(path, flags, *a, **k)
            if str(path).endswith("/COMPLETE.json") and not flags & os.O_CREAT:
                state["fd"] = fd
            return fd

        def close(fd):
            if fd == state["fd"]:
                state["fd"], state["hit"] = None, True
                real_close(fd)
                self.eio()
            return real_close(fd)
        with mock.patch.object(gen.os, "open", open_), mock.patch.object(gen.os, "close", close):
            self.assertIn("read-back close failed for COMPLETE.json", self.fail_build())
        self.assertTrue(state["hit"])
        self.failed()

    def test_completion_link_and_readback_failures(self):
        with mock.patch.object(gen.os, "link", self.eio):
            self.assertIn("finalize completion", self.fail_build())
        self.failed()
        real_open = os.open

        def open_(path, flags, *a, **k):
            if str(path).endswith("/COMPLETE.json") and not flags & os.O_CREAT:
                raise OSError(errno.EIO, os.strerror(errno.EIO))
            return real_open(path, flags, *a, **k)
        with mock.patch.object(gen.os, "open", open_):
            self.assertIn("read-back", self.fail_build())
        self.failed()

    def test_partial_source_descriptor_cleanup(self):
        real_open = os.open
        for role in ("bundle", "npc", "npcdistance"):
            path = self.bundle if role == "bundle" else self.table(role)

            def open_(p, flags, *a, path=path, **k):
                if str(p) == str(path):
                    raise OSError(errno.EMFILE, os.strerror(errno.EMFILE))
                return real_open(p, flags, *a, **k)
            with self.subTest(role=role), mock.patch.object(gen.os, "open", open_):
                self.assertIn("cannot open", self.fail_build())
            self.failed()

    def test_source_close_failure_is_reported(self):
        real_close = os.close
        state = {"fd": None}
        real_open = os.open

        def open_(path, flags, *a, **k):
            fd = real_open(path, flags, *a, **k)
            if str(path) == str(self.table("map")):
                state["fd"] = fd
            return fd

        def close(fd):
            if fd == state["fd"]:
                state["fd"] = None
                real_close(fd)
                self.eio()
            return real_close(fd)
        with mock.patch.object(gen.os, "open", open_), mock.patch.object(gen.os, "close", close):
            self.assertIn("map: close failed", self.fail_build())
        self.failed()

    def test_post_mkdir_inspection_reports_unverified_root(self):
        real_mkdir, real_lstat = os.mkdir, os.lstat
        state = {"created": False, "injected": False}

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
        with mock.patch.object(gen.os, "mkdir", mkdir), mock.patch.object(gen.os, "lstat", lstat):
            message = self.fail_build()
        self.assertIn("unverified", message)
        self.assertTrue(self.out.is_dir())
        self.assertEqual(os.listdir(self.out), [])
        self.assertEqual(open_fds(), self.fds)

    def test_interrupt_mid_copy_cleans_and_reraises(self):
        with self.nth("fsync", 4, lambda real, fd: (_ for _ in ()).throw(KeyboardInterrupt())):
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
        with self.nth("fsync", 9, replace_root):
            message = self.fail_build()
        self.assertIn("foreign", message)
        self.assertEqual(os.listdir(self.out), ["foreign"])
        self.assertEqual((self.out / "foreign").read_bytes(), b"foreign")
        self.assertFalse((self.out / "COMPLETE.json").exists())
        self.assertEqual(open_fds(), self.fds)

    def test_foreign_entry_inside_owned_tree_is_kept_and_reported(self):
        def plant(real, fd):
            (self.out / NAV_DIR / "planted").write_bytes(b"foreign")
            self.eio()
        with self.nth("fsync", 4, plant):
            message = self.fail_build()
        self.assertIn("cleanup", message)
        self.assertEqual((self.out / NAV_DIR / "planted").read_bytes(), b"foreign")
        self.assertFalse((self.out / "Online.js").exists())
        self.assertFalse((self.out / "COMPLETE.json").exists())

    def test_extra_entry_fails_tree_check(self):
        real_write_bytes = gen.Output.write_bytes

        def write_bytes(output, relative, data):
            if relative == gen.MANIFEST:
                (Path(output.root) / PACKAGE / "README").write_bytes(b"extra")
            return real_write_bytes(output, relative, data)
        with mock.patch.object(gen.Output, "write_bytes", write_bytes):
            self.assertIn("output tree", self.fail_build())
        self.assertEqual(os.listdir(self.out / PACKAGE), ["README"])

    def test_cli_failure_has_no_success_or_traceback(self):
        original = gen.build
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(gen, "build", lambda *a, **k: original(*a, profile=self.profile, **k)), \
                self.nth("fsync", 5, lambda real, fd: self.eio()), \
                mock.patch.object(sys, "stdout", out), mock.patch.object(sys, "stderr", err):
            code = gen.main([str(self.bundle), str(self.tables), str(self.out)])
        self.assertEqual(code, 1)
        self.assertEqual(out.getvalue(), "")
        self.assertNotIn("Traceback", err.getvalue())
        self.assertNotIn(str(self.dir), err.getvalue())
        self.assertLessEqual(len(err.getvalue()), 400)
        self.failed()
        with mock.patch.object(gen, "build", lambda *a, **k: (_ for _ in ()).throw(ValueError("x"))), \
                mock.patch.object(sys, "stdout", out), mock.patch.object(sys, "stderr", err):
            self.assertEqual(gen.main(["a", "b", "c"]), 1)
        self.assertIn("internal ValueError", err.getvalue())
        self.assertEqual(out.getvalue(), "")

    def check_cli_stdout_failure(self, phase):
        class Sink:
            def __init__(self):
                self.writes = 0
                self.flushes = 0
                self.accepted = ""

            def write(self, text):
                self.writes += 1
                if phase == "write":
                    raise OSError(errno.EIO, "stdout write")
                if phase == "short":
                    self.accepted += text[:-1]
                    return len(text) - 1
                self.accepted += text
                return len(text)

            def flush(self):
                self.flushes += 1
                if phase == "flush":
                    raise OSError(errno.EIO, "stdout flush")

        original = gen.build
        sink, err = Sink(), io.StringIO()
        before = {path: snapshot(path) for path in self.sources()}
        with mock.patch.object(gen, "build", lambda *a, **k: original(*a, profile=self.profile, **k)), \
                mock.patch.object(sys, "stdout", sink), mock.patch.object(sys, "stderr", err):
            code = gen.main([str(self.bundle), str(self.tables), str(self.out)])
        self.assertEqual(sink.writes, 1, "stdout fault was not reached")
        self.assertEqual(sink.flushes, 1 if phase == "flush" else 0)
        self.assertEqual(code, 1)
        self.assertNotIn("Traceback", err.getvalue())
        self.assertNotIn(str(self.dir), err.getvalue())
        self.assertLessEqual(len(err.getvalue()), 400)
        if phase == "write":
            self.assertEqual(sink.accepted, "")
        self.assertEqual({path: snapshot(path) for path in self.sources()}, before)
        self.failed()

    def test_cli_stdout_write_failure_removes_owned_completion(self):
        self.check_cli_stdout_failure("write")

    def test_cli_stdout_flush_failure_removes_owned_completion(self):
        self.check_cli_stdout_failure("flush")

    def test_cli_stdout_short_write_removes_owned_completion(self):
        self.check_cli_stdout_failure("short")


# ------------------------------------------------------------------ G05


class G05Runbook(unittest.TestCase):
    """The runbook keeps delivery, installation, preservation and rollback apart."""

    def test_runbook_sections_and_limits(self):
        text = (HERE / "NAVIGATION_CLIENT_REPAIR.md").read_text(encoding="utf-8")
        for heading in ("## Bundle delivery", "## Alias mod installation", "## Preservation",
                        "## Rollback", "## Limits"):
            self.assertIn(heading, text)
        self.assertIn("plan-only", text)
        self.assertIn("RAGNAROKMAC_ROOT", text)
        self.assertIn("python3 -I -B tools/renewal/navigation_client_repair.py BUNDLE_SOURCE TAIWAN_TABLE_DIR OUTPUT",
                      text)


if __name__ == "__main__":
    unittest.main()
