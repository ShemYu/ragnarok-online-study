#!/usr/bin/env python3
"""Tests for zero_sum_normal_repair (T07.007.011.002).

Pure tests need no assets. Actual-input tests read only ThreadEventHandler.js and
Online.js from RO_NORMAL_FIX_INPUT_ROOT and are skipped (with the reason
reported) when it is unset. Generated files go only under the candidate-local
.tools/renewal/t07-007-011-002-candidate-1 directory (0700/0600).

Method controls extract ONLY the original and patched class-method texts and
run them in a closed node:vm context; no bundle is imported or evaluated.

Run: python3 -I tools/renewal/test_zero_sum_normal_repair.py -v
"""

import hashlib
import json
import os
import struct
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import zero_sum_normal_repair as zr  # noqa: E402

REPO = os.path.dirname(os.path.dirname(HERE))
OUT_BASE = os.path.join(REPO, ".tools", "renewal", "t07-007-011-002-candidate-1")
TOOL = os.path.join(HERE, "zero_sum_normal_repair.py")
INPUT_ROOT = os.environ.get("RO_NORMAL_FIX_INPUT_ROOT")
SKIP_REASON = "RO_NORMAL_FIX_INPUT_ROOT unset; actual-input test skipped"

POS_ZERO = 0x00000000


def sha(data):
    return hashlib.sha256(data).hexdigest()


def private_dir(*parts):
    """Create (0700) a fresh owned directory under OUT_BASE."""
    os.makedirs(OUT_BASE, mode=0o700, exist_ok=True)
    os.chmod(OUT_BASE, 0o700)
    path = OUT_BASE
    for part in parts:
        path = os.path.join(path, part)
        if not os.path.isdir(path):
            os.mkdir(path, 0o700)
    return path


def run_id():
    return "run-%d-%d" % (os.getpid(), int.from_bytes(os.urandom(4), "big"))


def read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def read_json(path):
    with open(path, "rb") as fh:
        return json.loads(fh.read())


def is_nan_word(word):
    return (word & 0x7F800000) == 0x7F800000 and (word & 0x007FFFFF) != 0


# --------------------------------------------------------------------------
# Closed-context evaluation of one extracted method text.
HARNESS = r"""
const vm = require('node:vm');
const req = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const dec = (v) => v === 'NaN' ? NaN : v === 'Infinity' ? Infinity :
  v === '-Infinity' ? -Infinity : v === '-0' ? -0 : v;
const ctx = vm.createContext(Object.create(null));
const Klass = vm.runInContext('(class Probe {\n' + req.method + '\n})', ctx,
  { timeout: 2000 });
const fn = Klass.prototype.calcNormal_SMOOTH;
const out = [];
for (const fx of req.fixtures) {
  const self = { vertices: new Array(fx.size).fill(null), faces: fx.faces };
  const normal = new Float32Array(fx.normal.map(dec));
  const used = fx.groupUsed;
  const group = [];
  fn.call(self, normal, used, group);
  const res = { keys: Object.keys(group).map(Number), groups: {} };
  for (const j of res.keys) {
    const g = group[j];
    res.groups[j] = {
      type: Object.prototype.toString.call(g),
      words: Array.from(new Uint32Array(g.buffer, g.byteOffset, g.length)),
    };
  }
  out.push(res);
}
process.stdout.write(JSON.stringify(out));
"""


def eval_method(method_text, fixtures):
    proc = subprocess.run(
        ["node", "-e", HARNESS],
        input=json.dumps({"method": method_text, "fixtures": fixtures}).encode(),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60,
    )
    if proc.returncode != 0:
        raise AssertionError("node harness failed: %s" % proc.stderr.decode()[-2000:])
    return json.loads(proc.stdout)


def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def face(a, b, c, g):
    return {"vertidx": [a, b, c], "smoothGroup": g}


def used(*groups):
    flags = [False] * 32
    for g in groups:
        flags[g] = True
    return flags


# Each fixture declares, by hand, which (group, vertex) sums are exactly zero.
FIXTURES = [
    {   # one zero face normal: original 1/sqrt(0)*0 = NaN
        "id": "zero-face",
        "size": 3, "faces": [face(0, 1, 2, 0)], "normal": [0, 0, 0],
        "groupUsed": used(0), "zero": {0: [0, 1, 2]},
    },
    {   # signed zero components; 0 + -0 is +0, still an exact-zero sum
        "id": "signed-zero",
        "size": 4,
        "faces": [face(0, 1, 2, 0), face(1, 2, 3, 0)],
        "normal": ["-0", "-0", "-0", "-0", 0, "-0"],
        "groupUsed": used(0), "zero": {0: [0, 1, 2, 3]},
    },
    {   # nonzero x with -0 y/z keeps original arithmetic (-0 * len = -0)
        "id": "signed-zero-nonzero-sum",
        "size": 3, "faces": [face(0, 1, 2, 0)], "normal": [-2, "-0", "-0"],
        "groupUsed": used(0), "zero": {},
    },
    {   # opposite faces cancel exactly on shared vertices 1,2
        "id": "opposite-cancel",
        "size": 4,
        "faces": [face(0, 1, 2, 5), face(1, 2, 3, 5)],
        "normal": [0, 0, 1, 0, 0, -1],
        "groupUsed": used(5), "zero": {5: [1, 2]},
    },
    {   # near-cancellation leaves a tiny nonzero sum: no guard
        "id": "near-cancel",
        "size": 3,
        "faces": [face(0, 1, 2, 0), face(0, 1, 2, 0)],
        "normal": [1, 0, 0, -f32(1 - 2 ** -24), 0, 0],
        "groupUsed": used(0), "zero": {},
    },
    {   # ordinary finite data across groups 0, 3 and 31
        "id": "multi-face-multi-group",
        "size": 6,
        "faces": [face(0, 1, 2, 0), face(2, 3, 4, 0), face(1, 3, 5, 3),
                  face(0, 4, 5, 3), face(0, 1, 5, 31)],
        "normal": [0.3, 0.4, 0.5, -0.1, 0.9, 0.2, 0.7, -0.7, 0.1,
                   0.0, 0.6, -0.8, 0.25, 0.5, 0.75],
        "groupUsed": used(0, 3, 31),
        "zero": {0: [5], 3: [2], 31: [2, 3, 4]},
    },
    {   # repeated vertex reference in one face counts the face once
        "id": "repeated-ref",
        "size": 3,
        "faces": [face(1, 1, 0, 2), face(1, 0, 0, 2)],
        "normal": [0.6, 0.0, 0.8, 0.0, 1.0, 0.0],
        "groupUsed": used(2), "zero": {2: [2]},
    },
    {   # used group with no faces; unused group with faces is not generated
        "id": "unused-vertices-groups",
        "size": 5,
        "faces": [face(0, 1, 2, 1), face(0, 1, 2, 4)],
        "normal": [0, 1, 0, 1, 0, 0],
        "groupUsed": used(1, 7), "zero": {1: [3, 4], 7: [0, 1, 2, 3, 4]},
    },
    {   # nonfinite inputs stay nonfinite: no scrub or concealment
        "id": "nan-infinity",
        "size": 6,
        "faces": [face(0, 1, 2, 0), face(3, 4, 5, 0), face(0, 3, 4, 1)],
        "normal": ["NaN", 0, 0, "Infinity", 1, 0, "-Infinity", 0, 0],
        "groupUsed": used(0, 1), "zero": {1: [1, 2, 5]},
    },
    {   # subnormal / large finite components: original arithmetic
        "id": "tiny-huge",
        "size": 3,
        "faces": [face(0, 1, 2, 0), face(0, 1, 2, 9)],
        "normal": [1e-45, 0, 0, 3e38, 3e38, 0],
        "groupUsed": used(0, 9), "zero": {},
    },
]


class PureTests(unittest.TestCase):
    """No assets required."""

    def synthetic(self, indent=b"\t"):
        li = indent + b"\t\t\t"
        body = b"\n".join(li + line for line in (zr.LEN_LINE,) + zr.MULTIPLY_LINES)
        return (b"prefix\n" + indent + zr.METHOD_HEADER + b"\n" + li + b"x = 0;\n"
                + body + b"\n" + indent + b"}\n" + b"function calcNormal_SMOOTH(node) {\n"
                + li + zr.LEN_LINE + b"\n}\ninit();\n")

    def test_selector_and_type_refusals(self):
        with self.assertRaises(zr.PatchError):
            zr.patch_bundle(b"", "rsm")
        with self.assertRaises(TypeError):
            zr.patch_bundle(b"", b"worker")
        for bad in (bytearray(b"x"), memoryview(b"x"), "x", None):
            with self.assertRaises(TypeError):
                zr.patch_bundle(bad, "worker")

    def test_unpinned_bytes_refused(self):
        for bundle in ("worker", "online"):
            with self.assertRaises(zr.PatchError):
                zr.patch_bundle(self.synthetic(zr.PINS[bundle]["method_indent"]), bundle)

    def test_transform_single_insertion(self):
        data = self.synthetic()
        out = zr.transform(data, b"\t")
        _, at, _, li = zr.locate(data, b"\t")
        guard = zr.guard_text(li)
        self.assertEqual(out, data[:at] + guard + data[at:])
        self.assertEqual(out.count(zr.LEN_LINE), data.count(zr.LEN_LINE))
        with self.assertRaises(zr.AlreadyPatchedError):
            zr.transform(out, b"\t")

    def test_missing_or_duplicate_anchor(self):
        data = self.synthetic()
        with self.assertRaises(zr.PatchError):
            zr.locate(data.replace(zr.METHOD_HEADER, b"other() {"), b"\t")
        with self.assertRaises(zr.PatchError):
            zr.locate(data + data, b"\t")
        with self.assertRaises(zr.PatchError):
            zr.locate(data.replace(b"norm[l + 2] = z * len;", b"norm[l + 2] = z;", 1), b"\t")

    def test_guard_text_shape(self):
        g = zr.guard_text(b"\t\t\t\t")
        self.assertEqual(g.count(b"\n"), 6)
        self.assertIn(b"if (x === 0 && y === 0 && z === 0) {", g)
        self.assertNotIn(b"isFinite", g)
        self.assertNotIn(b"Math", g)


@unittest.skipUnless(INPUT_ROOT, SKIP_REASON)
class ActualInputTests(unittest.TestCase):
    """Uses the exact private inputs; reads only the two pinned bundles."""

    @classmethod
    def setUpClass(cls):
        cls.src, cls.ident, cls.out = {}, {}, {}
        for bundle in ("worker", "online"):
            path = os.path.join(INPUT_ROOT, zr.PINS[bundle]["name"])
            cls.src[bundle], cls.ident[bundle] = zr.read_source(path)
            cls.out[bundle] = zr.patch_bundle(cls.src[bundle], bundle)
        cls.work = private_dir(run_id())

    @classmethod
    def tearDownClass(cls):
        for bundle in ("worker", "online"):
            path = os.path.join(INPUT_ROOT, zr.PINS[bundle]["name"])
            data, ident = zr.read_source(path)
            assert ident == cls.ident[bundle], "source identity changed"
            assert sha(data) == zr.PINS[bundle]["sha256"], "source hash changed"

    def test_source_pins(self):
        for bundle in ("worker", "online"):
            pin = zr.PINS[bundle]
            self.assertEqual(len(self.src[bundle]), pin["bytes"])
            self.assertEqual(sha(self.src[bundle]), pin["sha256"])

    def test_exact_single_hunk(self):
        for bundle in ("worker", "online"):
            pin, d, o = zr.PINS[bundle], self.src[bundle], self.out[bundle]
            guard = zr.guard_text(pin["method_indent"] + b"\t\t\t")
            at = pin["insert_offset"]
            self.assertEqual(len(o), len(d) + len(guard))
            self.assertEqual(o[:at], d[:at])
            self.assertEqual(o[at:at + len(guard)], guard)
            self.assertEqual(o[at + len(guard):], d[at:])
            self.assertTrue(o.startswith(d[:at]) and o.endswith(d[at:]))
            # Insertion lands right before the original len line, inside the method.
            self.assertTrue(o[at + len(guard):].startswith(
                pin["method_indent"] + b"\t\t\t" + zr.LEN_LINE))
            self.assertTrue(pin["header_offset"] < at < pin["method_end"])
            self.assertEqual(o.count(zr.GUARD_CONDITION), 1)
            self.assertEqual(o.count(b"\r"), d.count(b"\r"))
            self.assertEqual(o[-200:], d[-200:])
            self.assertEqual(sha(o), pin["output_sha256"])

    def test_tail_and_free_helper_untouched(self):
        self.assertTrue(self.out["online"].endswith(b"init();\n//#endregion\n"))
        self.assertTrue(self.out["worker"].endswith(
            b'postMessage({ type: "THREAD_READY" });\n//#endregion\n'))
        d, o = self.src["online"], self.out["online"]
        hdr = b"function calcNormal_SMOOTH(node, normal, groupUsed, group) {"
        self.assertEqual(d.count(hdr), 1)
        start = d.index(hdr)
        end = d.index(b"\n}\n", start) + 3
        helper = d[start:end]
        self.assertIn(b"if (!isFinite(len)) len = 1;", helper)
        self.assertGreater(start, zr.PINS["online"]["insert_offset"])
        self.assertEqual(o.count(helper), 1)
        self.assertEqual(o.count(b"if (!isFinite(len)) len = 1;"),
                         d.count(b"if (!isFinite(len)) len = 1;"))
        self.assertEqual(o.count(b"Math.sqrt("), d.count(b"Math.sqrt("))

    def test_refusals_on_real_bytes(self):
        for bundle in ("worker", "online"):
            d = self.src[bundle]
            other = "online" if bundle == "worker" else "worker"
            with self.assertRaises(zr.AlreadyPatchedError):
                zr.patch_bundle(self.out[bundle], bundle)
            with self.assertRaises(zr.PatchError):
                zr.patch_bundle(d[:-1], bundle)
            flipped = bytearray(d)
            flipped[len(d) // 2] ^= 0x01
            with self.assertRaises(zr.PatchError):
                zr.patch_bundle(bytes(flipped), bundle)
            with self.assertRaises(zr.PatchError):
                zr.patch_bundle(d, other)
            with self.assertRaises(TypeError):
                zr.patch_bundle(bytearray(d), bundle)
        self.assertEqual(zr.patch_bundle(self.src["worker"], "worker"), self.out["worker"])

    def test_generated_syntax(self):
        for bundle in ("worker", "online"):
            name = zr.PINS[bundle]["name"]
            for label, data in (("orig", self.src[bundle]), ("patched", self.out[bundle])):
                d = private_dir(os.path.basename(self.work), "syntax-" + label)
                path = os.path.join(d, name)
                zr.write_exclusive(path, data)
                proc = subprocess.run(["node", "--check", path], stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, timeout=120)
                self.assertEqual(proc.returncode, 0, "%s %s: %s" % (
                    label, name, proc.stderr.decode()[-1000:]))

    def method_texts(self, bundle):
        pin = zr.PINS[bundle]
        guard = zr.guard_text(pin["method_indent"] + b"\t\t\t")
        orig = self.src[bundle][pin["header_offset"]:pin["method_end"]]
        patched = self.out[bundle][pin["header_offset"]:pin["method_end"] + len(guard)]
        self.assertEqual(sha(orig), pin["method_sha256"])
        self.assertEqual(sha(patched), pin["patched_method_sha256"])
        self.assertTrue(orig.startswith(zr.METHOD_HEADER))
        return orig.decode("utf-8"), patched.decode("utf-8")

    def test_extracted_methods(self):
        evidence = {}
        for bundle in ("worker", "online"):
            orig_text, patched_text = self.method_texts(bundle)
            orig = eval_method(orig_text, FIXTURES)
            patched = eval_method(patched_text, FIXTURES)
            evidence[bundle] = {"fixtures": len(FIXTURES), "zeroed_words": 0,
                                "preserved_words": 0, "nan_preserved_words": 0}
            for fx, o, p in zip(FIXTURES, orig, patched):
                with self.subTest(bundle=bundle, fixture=fx["id"]):
                    self.check_fixture(fx, o, p, evidence[bundle])
        # Every fixture class contributes; exact zeros were exercised.
        for bundle in evidence:
            self.assertGreater(evidence[bundle]["zeroed_words"], 0)
            self.assertGreater(evidence[bundle]["nan_preserved_words"], 0)
        path = os.path.join(self.work, "method-evidence.json")
        zr.write_exclusive(path, (json.dumps(evidence, indent=2, sort_keys=True) + "\n").encode())

    def check_fixture(self, fx, o, p, ev):
        expected_keys = [j for j in range(32) if fx["groupUsed"][j]]
        self.assertEqual(o["keys"], expected_keys)
        self.assertEqual(p["keys"], expected_keys)
        for j in expected_keys:
            ow, pw = o["groups"][str(j)]["words"], p["groups"][str(j)]["words"]
            self.assertEqual(o["groups"][str(j)]["type"], "[object Float32Array]")
            self.assertEqual(p["groups"][str(j)]["type"], "[object Float32Array]")
            self.assertEqual(len(ow), fx["size"] * 3)
            self.assertEqual(len(pw), fx["size"] * 3)
            zero_vertices = set(fx["zero"].get(j, []))
            for v in range(fx["size"]):
                for c in range(3):
                    a, b = ow[v * 3 + c], pw[v * 3 + c]
                    if v in zero_vertices:
                        # Original: 0 * (1/sqrt(0)) = NaN; patched: +0 exactly.
                        self.assertTrue(is_nan_word(a), (fx["id"], j, v, c, hex(a)))
                        self.assertEqual(b, POS_ZERO, (fx["id"], j, v, c, hex(b)))
                        ev["zeroed_words"] += 1
                    elif is_nan_word(a):
                        self.assertTrue(is_nan_word(b), (fx["id"], j, v, c, hex(b)))
                        ev["nan_preserved_words"] += 1
                    else:
                        self.assertEqual(a, b, (fx["id"], j, v, c))
                        ev["preserved_words"] += 1


@unittest.skipUnless(INPUT_ROOT, SKIP_REASON)
class CliTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.work = private_dir(run_id())
        cls.before = {}
        for bundle in ("worker", "online"):
            cls.before[bundle] = zr.read_source(
                os.path.join(INPUT_ROOT, zr.PINS[bundle]["name"]))

    @classmethod
    def tearDownClass(cls):
        for bundle in ("worker", "online"):
            now = zr.read_source(os.path.join(INPUT_ROOT, zr.PINS[bundle]["name"]))
            assert now[1] == cls.before[bundle][1], "source identity changed"
            assert sha(now[0]) == zr.PINS[bundle]["sha256"], "source hash changed"

    def cli(self, input_root, output_dir):
        return subprocess.run([sys.executable, "-I", TOOL, "--input-root", input_root,
                               "--output-dir", output_dir],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)

    def copy_root(self, label):
        """Candidate-local private copy of the pinned inputs for refusal cases."""
        root = private_dir(os.path.basename(self.work), label)
        for bundle in ("worker", "online"):
            zr.write_exclusive(os.path.join(root, zr.PINS[bundle]["name"]),
                               self.before[bundle][0])
        return root

    def test_success_and_manifest(self):
        out = os.path.join(self.work, "out")
        proc = self.cli(INPUT_ROOT, out)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        self.assertEqual(sorted(os.listdir(out)),
                         sorted(["ThreadEventHandler.js", "Online.js", "manifest.json"]))
        self.assertEqual(os.stat(out).st_mode & 0o777, 0o700)
        for name in os.listdir(out):
            self.assertEqual(os.stat(os.path.join(out, name)).st_mode & 0o777, 0o600)
        manifest = read_json(os.path.join(out, "manifest.json"))
        self.assertEqual(manifest["patch_id"], zr.PATCH_ID)
        self.assertEqual(manifest["patch_version"], zr.PATCH_VERSION)
        for item in manifest["files"]:
            pin = zr.PINS[item["bundle"]]
            data = read_bytes(os.path.join(out, item["name"]))
            self.assertEqual(item["input"], {"bytes": pin["bytes"], "sha256": pin["sha256"]})
            self.assertEqual(item["output"], {"bytes": len(data), "sha256": sha(data)})
            self.assertEqual(sha(data), pin["output_sha256"])
            self.assertEqual(len(item["hunks"]), 1)
            self.assertEqual(item["hunks"][0]["offset"], pin["insert_offset"])
            receipt = manifest["runtime_receipts"]["sources"][item["name"]]
            self.assertEqual(receipt["source_sha256_before"], pin["sha256"])
            self.assertEqual(receipt["source_sha256_after"], pin["sha256"])
        # Determinism apart from runtime receipts.
        out2 = os.path.join(self.work, "out2")
        self.assertEqual(self.cli(INPUT_ROOT, out2).returncode, 0)
        m2 = read_json(os.path.join(out2, "manifest.json"))
        manifest.pop("runtime_receipts")
        m2.pop("runtime_receipts")
        self.assertEqual(manifest, m2)
        for name in ("ThreadEventHandler.js", "Online.js"):
            self.assertEqual(read_bytes(os.path.join(out, name)),
                             read_bytes(os.path.join(out2, name)))

    def test_existing_output_refused(self):
        out = private_dir(os.path.basename(self.work), "existing")
        marker = os.path.join(out, "keep.txt")
        zr.write_exclusive(marker, b"keep\n")
        proc = self.cli(INPUT_ROOT, out)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(os.listdir(out), ["keep.txt"])
        self.assertEqual(read_bytes(marker), b"keep\n")
        link = os.path.join(self.work, "dangling-out")
        os.symlink(os.path.join(self.work, "nowhere"), link)
        self.assertNotEqual(self.cli(INPUT_ROOT, link).returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(self.work, "nowhere")))

    def test_wrong_bytes_refused_without_output(self):
        root = self.copy_root("wrong-bytes")
        path = os.path.join(root, "Online.js")
        data = bytearray(read_bytes(path))
        data[1000] ^= 0x20
        os.chmod(path, 0o600)
        with open(path, "r+b") as fh:
            fh.write(bytes(data))
        out = os.path.join(self.work, "out-wrong")
        proc = self.cli(root, out)
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(os.path.lexists(out))

    def test_already_patched_refused(self):
        root = private_dir(os.path.basename(self.work), "already")
        for bundle in ("worker", "online"):
            zr.write_exclusive(os.path.join(root, zr.PINS[bundle]["name"]),
                               zr.patch_bundle(self.before[bundle][0], bundle))
        out = os.path.join(self.work, "out-already")
        proc = self.cli(root, out)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn(b"already patched", proc.stderr)
        self.assertFalse(os.path.lexists(out))

    def test_linked_and_nonregular_refused(self):
        root = self.copy_root("symlink")
        target = os.path.join(root, "Online.js")
        moved = os.path.join(root, "real-Online.js")
        os.rename(target, moved)
        os.symlink(moved, target)
        out = os.path.join(self.work, "out-symlink")
        self.assertNotEqual(self.cli(root, out).returncode, 0)
        self.assertFalse(os.path.lexists(out))

        root = self.copy_root("hardlink")
        os.link(os.path.join(root, "Online.js"), os.path.join(root, "second-link"))
        out = os.path.join(self.work, "out-hardlink")
        self.assertNotEqual(self.cli(root, out).returncode, 0)
        self.assertFalse(os.path.lexists(out))

        root = private_dir(os.path.basename(self.work), "dir-input")
        os.mkdir(os.path.join(root, "ThreadEventHandler.js"), 0o700)
        out = os.path.join(self.work, "out-dir")
        self.assertNotEqual(self.cli(root, out).returncode, 0)
        self.assertFalse(os.path.lexists(out))

        out = os.path.join(self.work, "out-missing")
        self.assertNotEqual(self.cli(os.path.join(self.work, "absent"), out).returncode, 0)
        self.assertFalse(os.path.lexists(out))


# ROOT correction regressions below. Original sixteen test methods unchanged.
import contextlib
import errno
import io
from unittest import mock

_ROOT_OS = {name: getattr(os, name) for name in
            ("open", "write", "fsync", "close", "fstat", "lstat", "rename", "unlink")}


def _root_create(path, data):
    """Only owned fixture files; bypass producer hooks while creating controls."""
    fd = _ROOT_OS["open"](path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        view = memoryview(data)
        while view:
            count = _ROOT_OS["write"](fd, view)
            if count <= 0 or count > len(view):
                raise RuntimeError("fixture write did not progress")
            view = view[count:]
        _ROOT_OS["fsync"](fd)
    finally:
        _ROOT_OS["close"](fd)


class _RootAssertions:
    def assert_owned_fd_closed(self, fd, identity):
        """Observe first, then free ONLY an exact owned leaked inode and fail."""
        try:
            current = _ROOT_OS["fstat"](fd)
        except OSError as exc:
            self.assertEqual(exc.errno, errno.EBADF)
            return
        if (current.st_dev, current.st_ino) == identity[:2]:
            _ROOT_OS["close"](fd)
        self.fail("producer FD remained open (or was reused); observation preceded any fixture cleanup")

    def direct_main(self, root, output):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return zr.main(["--input-root", root, "--output-dir", output])


class RootWriteTests(_RootAssertions, unittest.TestCase):
    def test_zero_progress_refused_before_second_write(self):
        path = os.path.join(private_dir(run_id()), "zero-progress.bin")
        state = {"calls": 0}

        def zero_then_sentinel(fd, data):
            state["calls"] += 1
            state["fd"], state["identity"] = fd, zr._identity(_ROOT_OS["fstat"](fd))
            if state["calls"] == 1:
                return 0
            raise OSError(errno.EIO, "fixture sentinel after retry, preventing hang")

        caught = None
        try:
            with mock.patch.object(zr.os, "write", new=zero_then_sentinel):
                try:
                    zr.write_exclusive(path, b"finite authored bytes")
                except (zr.PatchError, OSError) as exc:
                    caught = exc
        finally:
            if "fd" in state:
                self.assert_owned_fd_closed(state["fd"], state["identity"])
        self.assertEqual(state["calls"], 1)
        self.assertIsInstance(caught, zr.PatchError)
        self.assertEqual(read_bytes(path), b"")

    def test_interrupted_and_real_short_write_complete(self):
        path = os.path.join(private_dir(run_id()), "short-write.bin")
        state = {"calls": 0, "positive": []}
        data = b"literal partial write control"

        def interrupt_then_short(fd, view):
            state["calls"] += 1
            state["fd"], state["identity"] = fd, zr._identity(_ROOT_OS["fstat"](fd))
            if state["calls"] == 1:
                raise InterruptedError(errno.EINTR, "authored interruption")
            count = _ROOT_OS["write"](fd, view[:3] if state["calls"] == 2 else view)
            state["positive"].append(count)
            return count

        try:
            with mock.patch.object(zr.os, "write", new=interrupt_then_short):
                zr.write_exclusive(path, data)
        finally:
            if "fd" in state:
                self.assert_owned_fd_closed(state["fd"], state["identity"])
        self.assertGreaterEqual(state["calls"], 3)
        self.assertTrue(0 < state["positive"][0] <= 3)
        self.assertEqual(sum(state["positive"]), len(data))
        self.assertEqual(read_bytes(path), data)


@unittest.skipUnless(INPUT_ROOT, SKIP_REASON)
class RootDeliveryTests(_RootAssertions, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = private_dir(run_id())
        cls.before = {bundle: zr.read_source(os.path.join(INPUT_ROOT, zr.PINS[bundle]["name"]))
                      for bundle in ("worker", "online")}

    @classmethod
    def tearDownClass(cls):
        for bundle in ("worker", "online"):
            current = zr.read_source(os.path.join(INPUT_ROOT, zr.PINS[bundle]["name"]))
            if current[1] != cls.before[bundle][1] or sha(current[0]) != zr.PINS[bundle]["sha256"]:
                raise AssertionError("canonical source changed")

    def input_copy(self, label):
        case = private_dir(os.path.basename(self.work), label)
        root = os.path.join(case, "input")
        os.mkdir(root, 0o700)
        for bundle in ("worker", "online"):
            _root_create(os.path.join(root, zr.PINS[bundle]["name"]), self.before[bundle][0])
        return case, root, os.path.join(case, "output")

    def test_staged_manifest_fsync_and_real_close_errors(self):
        for fault in ("fsync", "close"):
            with self.subTest(fault=fault):
                _, root, output = self.input_copy("manifest-" + fault)
                partial = os.path.join(output, "manifest.json.partial")
                final = os.path.join(output, "manifest.json")
                state = {"hits": 0}

                def opened(path, flags, *args, **kwargs):
                    fd = _ROOT_OS["open"](path, flags, *args, **kwargs)
                    if os.fspath(path) in (partial, final) and flags & os.O_ACCMODE == os.O_WRONLY:
                        state.update(fd=fd, identity=zr._identity(_ROOT_OS["fstat"](fd)), path=os.fspath(path))
                    return fd

                def complete_bytes():
                    body = read_bytes(state["path"])
                    self.assertEqual(json.loads(body)["schema"], "T07.007.011.002-normal-repair-manifest-1")
                    self.assertEqual(len(body), _ROOT_OS["fstat"](state["fd"]).st_size)
                    state["bytes"] = len(body)

                def fsynced(fd):
                    _ROOT_OS["fsync"](fd)
                    if fault == "fsync" and fd == state.get("fd"):
                        complete_bytes()
                        state["hits"] += 1
                        raise OSError(errno.EIO, "authored error after real manifest fsync")

                def closed(fd):
                    fail = fault == "close" and fd == state.get("fd") and state["hits"] == 0
                    if fail:
                        complete_bytes()
                    _ROOT_OS["close"](fd)
                    if fail:
                        state["hits"] += 1
                        self.assert_owned_fd_closed(fd, state["identity"])
                        raise OSError(errno.EIO, "authored error after real manifest close")

                try:
                    with mock.patch.object(zr.os, "open", new=opened), mock.patch.object(zr.os, "fsync", new=fsynced), mock.patch.object(zr.os, "close", new=closed):
                        code = self.direct_main(root, output)
                finally:
                    if "fd" in state:
                        self.assert_owned_fd_closed(state["fd"], state["identity"])
                self.assertEqual(state["hits"], 1)
                self.assertGreater(state["bytes"], 0)
                self.assertEqual(code, 1)
                self.assertEqual(state["path"], partial)
                self.assertTrue(os.path.isfile(partial))
                self.assertFalse(os.path.lexists(final))

    def test_final_second_and_third_source_eof_path_replacement(self):
        real_read = os.read
        for ordinal in (2, 3):
            with self.subTest(source_open=ordinal):
                case, root, output = self.input_copy("source-eof-%d" % ordinal)
                target, stash = os.path.join(root, "Online.js"), os.path.join(case, "Online-original-stash.js")
                opened_fds, state = {}, {"opens": 0, "hits": 0}

                def opened(path, flags, *args, **kwargs):
                    fd = _ROOT_OS["open"](path, flags, *args, **kwargs)
                    if os.fspath(path) == target and flags & os.O_ACCMODE == os.O_RDONLY:
                        state["opens"] += 1
                        opened_fds[fd] = state["opens"]
                    else:
                        opened_fds[fd] = None
                    return fd

                def at_eof(fd, count):
                    data = real_read(fd, count)
                    if not data and opened_fds.get(fd) == ordinal and state["hits"] == 0:
                        old = zr._identity(_ROOT_OS["fstat"](fd))
                        _ROOT_OS["rename"](target, stash)
                        _root_create(target, self.before["online"][0])
                        replacement = zr._identity(_ROOT_OS["lstat"](target))
                        self.assertNotEqual(old[:2], replacement[:2])
                        self.assertEqual(sha(read_bytes(target)), zr.PINS["online"]["sha256"])
                        state.update(hits=1, fd=fd, identity=old, replacement=replacement)
                        state["staged_at_fault"] = os.path.isfile(os.path.join(output, "manifest.json.partial"))
                    return data

                try:
                    with mock.patch.object(zr.os, "open", new=opened), mock.patch.object(zr.os, "read", new=at_eof):
                        code = self.direct_main(root, output)
                finally:
                    if "fd" in state:
                        self.assert_owned_fd_closed(state["fd"], state["identity"])
                self.assertEqual(state["hits"], 1)
                self.assertEqual(code, 1)
                self.assertEqual(state["staged_at_fault"], ordinal == 3)
                self.assertEqual(zr._identity(_ROOT_OS["lstat"](target)), state["replacement"])
                self.assertEqual(sha(read_bytes(target)), sha(read_bytes(stash)))
                self.assertFalse(os.path.lexists(os.path.join(output, "manifest.json")))

    def test_inserted_manifest_marker_preserved(self):
        _, root, output = self.input_copy("inserted-marker")
        final = os.path.join(output, "manifest.json")
        marker = b"ROOT owned preexisting marker; must survive unchanged\n"
        state = {"hits": 0}

        def opened(path, flags, *args, **kwargs):
            if os.fspath(path) in (final, final + ".partial") and flags & os.O_ACCMODE == os.O_WRONLY and state["hits"] == 0:
                _root_create(final, marker)
                state.update(hits=1, identity=zr._identity(_ROOT_OS["lstat"](final)))
            return _ROOT_OS["open"](path, flags, *args, **kwargs)

        with mock.patch.object(zr.os, "open", new=opened):
            code = self.direct_main(root, output)
        self.assertEqual(state["hits"], 1)
        self.assertEqual(code, 1)
        self.assertEqual(zr._identity(_ROOT_OS["lstat"](final)), state["identity"])
        self.assertEqual(read_bytes(final), marker)

    def test_partial_unlink_failure_revokes_only_owned_final(self):
        for foreign in (False, True):
            with self.subTest(foreign_final=foreign):
                case, root, output = self.input_copy("unlink-foreign-%s" % foreign)
                partial, final = os.path.join(output, "manifest.json.partial"), os.path.join(output, "manifest.json")
                state = {"hits": 0, "real_final_unlinks": 0}
                sentinel = b"ROOT different-inode marker: never delete\n"

                def unlinked(path, *args, **kwargs):
                    if os.fspath(path) == partial and state["hits"] == 0:
                        own = zr._identity(_ROOT_OS["lstat"](partial))
                        self.assertEqual(own[:2], zr._identity(_ROOT_OS["lstat"](final))[:2])
                        self.assertEqual(own[-1], 2)
                        state.update(hits=1, owned=own)
                        if foreign:
                            _ROOT_OS["rename"](final, os.path.join(case, "owned-final-stash.json"))
                            _root_create(final, sentinel)
                            state["foreign_identity"] = zr._identity(_ROOT_OS["lstat"](final))
                            self.assertNotEqual(state["foreign_identity"][:2], own[:2])
                        raise OSError(errno.EIO, "authored partial unlink failure before release")
                    if os.fspath(path) == final:
                        state["real_final_unlinks"] += 1
                    return _ROOT_OS["unlink"](path, *args, **kwargs)

                with mock.patch.object(zr.os, "unlink", new=unlinked):
                    code = self.direct_main(root, output)
                self.assertEqual(state["hits"], 1)
                self.assertEqual(code, 1)
                self.assertEqual(zr._identity(_ROOT_OS["lstat"](partial))[:2], state["owned"][:2])
                self.assertEqual(json.loads(read_bytes(partial))["patch_id"], zr.PATCH_ID)
                if foreign:
                    self.assertEqual(state["real_final_unlinks"], 0)
                    self.assertEqual(zr._identity(_ROOT_OS["lstat"](final)), state["foreign_identity"])
                    self.assertEqual(read_bytes(final), sentinel)
                else:
                    self.assertEqual(state["real_final_unlinks"], 1)
                    self.assertFalse(os.path.lexists(final))


if __name__ == "__main__":
    if not INPUT_ROOT:
        print(SKIP_REASON, file=sys.stderr)
    unittest.main()
