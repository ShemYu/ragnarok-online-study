"""Tests for quoted_source_inventory. Run: python3 -I -B tools/renewal/test_quoted_source_inventory.py

The authored 38-case fixture freezes whole scan_source objects. An independent
byte-at-a-time reference scanner written here (not the module's search-based
loop) is compared against the module on boundary cases, random inputs and every
actual selected source. Deliberate mutations of the real scanner source must be
rejected by the fixture checks. Publication tests use private temporary
directories only (set TMPDIR to a private ignored directory to keep them there).

Actual-input tests read $QUOTED_SOURCE_FROZEN_ROOT, whose children `snapshot`
and `selection` are the absolute CLI inputs; they are skipped when it is unset.
The CLI has no pin, profile or input override; tests never alter the inputs.
"""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import shutil
import stat
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
TOOL = HERE / "quoted_source_inventory.py"
FIXTURE = HERE.parent.parent / "docs/project/fixtures/T06.004.001-authored.json"
FIXTURE_PIN = (16186, "5af44a3358902aa162f7f91812661a57e14f1163cd5cdd3ef09c60d58a56caaa")
FROZEN = os.environ.get("QUOTED_SOURCE_FROZEN_ROOT")


def load_module(source=None, name="quoted_source_inventory_under_test"):
    if source is None:
        spec = importlib.util.spec_from_file_location(name, TOOL)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    module = types.ModuleType(name)
    module.__file__ = str(TOOL)
    exec(compile(source, str(TOOL), "exec"), module.__dict__)
    return module


qi = load_module()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fixture_cases():
    data = FIXTURE.read_bytes()
    assert (len(data), sha(data)) == FIXTURE_PIN, "authored fixture changed"
    doc = json.loads(data)
    assert doc["schema"] == 1 and doc["profile"] == qi.PROFILE
    return doc["cases"]


def reference_scan(raw, max_bytes=8388608, max_occurrences=250000):
    """Independent byte-at-a-time model of the frozen policy."""
    size = len(raw)
    end = min(size, max_bytes)
    eof = end == size
    found = []

    def stop(reason, at):
        return {"occurrences": found, "known_prefix_end": at,
                "gap": {"reason": reason, "span": [at, size]}}

    i = 0
    while i < end:
        b = raw[i]
        two = raw[i + 1] if i + 1 < end else None
        if b == 0x2F and two == 0x2F:
            j = i + 2
            while j < end and raw[j] != 0x0A:
                j += 1
            if j < end:
                i = j + 1
            elif eof:
                i = end
            else:
                return stop("byte_limit", i)
        elif b == 0x2F and two == 0x2A:
            j = i + 2
            while j + 1 < end and not (raw[j] == 0x2A and raw[j + 1] == 0x2F):
                j += 1
            if j + 1 >= end:
                return stop("unterminated_block_comment" if eof else "byte_limit", i)
            i = j + 2
        elif b == 0x22:
            if len(found) >= max_occurrences:
                return stop("occurrence_limit", i)
            j = i + 1
            while True:
                if j >= end:
                    return stop("unterminated_quote" if eof else "byte_limit", i)
                c = raw[j]
                if c == 0x22:
                    found.append({"literal_index": len(found), "span": [i, j + 1],
                                  "content_span": [i + 1, j], "content_hex": raw[i + 1:j].hex()})
                    i = j + 1
                    break
                if c == 0x5C and raw[j - 1] <= 0x7E:
                    if j + 1 >= end:
                        return stop("unterminated_quote" if eof else "byte_limit", i)
                    j += 2
                else:
                    j += 1
        else:
            i += 1
    if not eof:
        return stop("byte_limit", end)
    return {"occurrences": found, "known_prefix_end": size, "gap": None}


def check_invariants(test, raw, result):
    test.assertEqual(set(result), {"occurrences", "known_prefix_end", "gap"})
    for index, item in enumerate(result["occurrences"]):
        test.assertEqual(set(item), {"literal_index", "span", "content_span", "content_hex"})
        start, end = item["span"]
        test.assertEqual(item["literal_index"], index)
        test.assertEqual(item["content_span"], [start + 1, end - 1])
        test.assertEqual(raw[start], 0x22)
        test.assertEqual(raw[end - 1], 0x22)
        test.assertLessEqual(end, result["known_prefix_end"])
        test.assertEqual(item["content_hex"], raw[start + 1:end - 1].hex())
    gap = result["gap"]
    if gap is None:
        test.assertEqual(result["known_prefix_end"], len(raw))
    else:
        test.assertEqual(set(gap), {"reason", "span"})
        test.assertEqual(gap["span"], [result["known_prefix_end"], len(raw)])


def private_dir():
    path = os.path.realpath(tempfile.mkdtemp(prefix="quoted-test-"))
    os.chmod(path, 0o700)
    return path


def open_fds():
    return len(os.listdir("/dev/fd"))


class FixtureTest(unittest.TestCase):
    def test_all_authored_cases(self):
        cases = fixture_cases()
        self.assertEqual(len(cases), 38)
        for case in cases:
            with self.subTest(case["name"]):
                raw = bytes.fromhex(case["raw_hex"])
                kwargs = dict(case["kwargs"])
                result = qi.scan_source(raw, **kwargs)
                self.assertEqual(result, case["expected"])
                self.assertEqual(kwargs, case["kwargs"])
                self.assertEqual(raw.hex(), case["raw_hex"])
                self.assertEqual(reference_scan(raw, **{
                    {"max_bytes": "max_bytes", "max_occurrences": "max_occurrences"}[k]: v
                    for k, v in kwargs.items()}), case["expected"])
                check_invariants(self, raw, result)


MUTATIONS = {
    "unconditional_escape": ("if raw[k - 1] <= ESCAPE_MAX:", "if True:"),
    "quote_in_comment": ("OUTSIDE = re.compile(rb'[\"/]')", "OUTSIDE = re.compile(rb'[\"]')"),
    "deduplicate": (
        "                occurrences.append({\n",
        "                if raw[start + 1:k].hex() in [o['content_hex'] for o in occurrences]:\n"
        "                    pos = k + 1\n"
        "                    break\n"
        "                occurrences.append({\n"),
    "ignore_byte_budget": ("limit = min(size, max_bytes)", "limit = size"),
    "nesting_block_comment": ("raw.find(BLOCK_CLOSE, start + 2, limit)",
                              "raw.rfind(BLOCK_CLOSE, start + 2, limit)"),
}


class MutationTest(unittest.TestCase):
    def test_fixture_rejects_real_scanner_mutations(self):
        source = TOOL.read_text(encoding="ascii")
        cases = fixture_cases()
        for label, (old, new) in MUTATIONS.items():
            with self.subTest(label):
                self.assertEqual(source.count(old), 1, f"mutation site for {label} not unique")
                mutant = load_module(source.replace(old, new), f"mutant_{label}")
                failed = [c["name"] for c in cases
                          if mutant.scan_source(bytes.fromhex(c["raw_hex"]), **c["kwargs"])
                          != c["expected"]]
                self.assertTrue(failed, f"mutation {label} was not detected")


class ScannerTest(unittest.TestCase):
    def scan(self, raw, **kwargs):
        result = qi.scan_source(raw, **kwargs)
        self.assertEqual(result, reference_scan(raw, **kwargs))
        check_invariants(self, raw, result)
        return result

    def contents(self, raw, **kwargs):
        return [bytes.fromhex(o["content_hex"]) for o in self.scan(raw, **kwargs)["occurrences"]]

    def test_invalid_input_and_limit_types(self):
        class Bytes(bytes):
            pass

        class Int(int):
            pass

        for raw in (bytearray(b'"a"'), memoryview(b'"a"'), '"a"', None, Bytes(b'"a"'), [34]):
            with self.subTest(raw=type(raw).__name__):
                with self.assertRaises(qi.InventoryError):
                    qi.scan_source(raw)
        for name, default in (("max_bytes", 8388608), ("max_occurrences", 250000)):
            for value in (True, False, 1.0, -1, default + 1, "1", None, Int(1)):
                with self.subTest(name=name, value=value):
                    with self.assertRaises(qi.InventoryError):
                        qi.scan_source(b"", **{name: value})
            self.assertEqual(qi.scan_source(b'"x"', **{name: default})["gap"], None)
            self.assertEqual(qi.scan_source(b"", **{name: 0})["gap"], None)
        with self.assertRaises(TypeError):
            qi.scan_source(b"", 1)
        with self.assertRaises(TypeError):
            qi.scan_source(b"", max_lines=1)

    def test_result_is_fresh_and_input_unchanged(self):
        raw = b'a "b" c'
        first = qi.scan_source(raw)
        first["occurrences"].clear()
        self.assertEqual(len(qi.scan_source(raw)["occurrences"]), 1)
        self.assertEqual(raw, b'a "b" c')

    def test_escape_eligibility_uses_preceding_raw_byte(self):
        self.assertEqual(self.contents(b'"\\\\"'), [b"\\\\"])
        # 5c5c pair, then 5c (preceded by raw 5c) shields the quote at 4.
        self.assertEqual(self.contents(b'"\\\\\\""'), [b'\\\\\\"'])
        # Big5 trail byte 0x5c after a high lead byte is never an escape.
        self.assertEqual(self.contents(b'"\xa5\\" "x"'), [b"\xa5\\", b"x"])
        self.assertEqual(self.contents(b'"\xff\\"'), [b"\xff\\"])
        self.assertEqual(self.contents(b'"\x7e\\"x"'), [b'\x7e\\"x'])
        self.assertEqual(self.contents(b'"\\n\\t\\u0041"'), [b"\\n\\t\\u0041"])
        # Shielded bytes may be comment openers, CR or NUL; nothing is decoded.
        self.assertEqual(self.contents(b'"\\/\\*\\\r\\\x00"'), [b"\\/\\*\\\r\\\x00"])

    def test_comment_and_quote_distinctions(self):
        self.assertEqual(self.contents(b'/* "a" */ "b" // "c"\n"d"'), [b"b", b"d"])
        self.assertEqual(self.contents(b'"/* x */" "// y"'), [b"/* x */", b"// y"])
        self.assertEqual(self.contents(b'/ "a" /x "b" */ "c"'), [b"a", b"b", b"c"])
        self.assertEqual(self.contents(b'//x\r\n"a"'), [b"a"])
        self.assertEqual(self.contents(b'/**/"a"'), [b"a"])
        self.assertEqual(self.contents(b'/***/"a"'), [b"a"])
        self.assertEqual(self.scan(b'/*/"a"')["gap"],
                         {"reason": "unterminated_block_comment", "span": [0, 6]})
        self.assertEqual(self.contents(b'"a"//\n'), [b"a"])
        self.assertEqual(self.contents(b"'\"' \"x"), [b"' "])

    def test_raw_bytes_newlines_nul_bom_high(self):
        raw = b'\xef\xbb\xbf"\xef\xbb\xbf"\x00"\x00"\r"\r\n"\xe4\xb8\xad"\xb0\x5c"'
        self.assertEqual(self.contents(raw),
                         [b"\xef\xbb\xbf", b"\x00", b"\r\n", b"\xb0\x5c"])
        self.assertIsNone(self.scan(raw)["gap"])
        self.assertEqual(self.scan(raw + b'"\\')["gap"],
                         {"reason": "unterminated_quote", "span": [len(raw), len(raw) + 2]})

    def test_header_distinctions(self):
        quoted = b'prontera,150,150,4\tscript\t"Quoted#1"\t4_M_01,{\n\tmes "Hi";\n}\n'
        self.assertEqual(self.contents(quoted), [b"Quoted#1", b"Hi"])
        # An unquoted header containing // suppresses later quotes on that line only.
        header = b'prontera,1,1,4\tscript\tA//B\t4_M_01,{ mes "hidden";\nmes "seen"; }\n'
        self.assertEqual(self.contents(header), [b"seen"])
        # A quote can span a native newline; the policy keeps it as one occurrence.
        self.assertEqual(self.contents(b'mes "a\nb";'), [b"a\nb"])

    def test_byte_boundaries(self):
        raw = b'"a"//c\n/*d*/"e"'
        for limit in range(len(raw) + 1):
            with self.subTest(limit=limit):
                result = self.scan(raw, max_bytes=limit)
                if limit < len(raw):
                    self.assertEqual(result["gap"]["reason"], "byte_limit")
        # Closed exactly at the boundary belongs to the known prefix.
        self.assertEqual(self.scan(b'"ab"zz', max_bytes=4)["known_prefix_end"], 4)
        self.assertEqual(self.scan(b'//a\nzz', max_bytes=4)["known_prefix_end"], 4)
        self.assertEqual(self.scan(b'/*a*/zz', max_bytes=5)["known_prefix_end"], 5)
        # Closer split by the boundary leaves the comment open.
        self.assertEqual(self.scan(b'x/*a*/', max_bytes=5)["gap"],
                         {"reason": "byte_limit", "span": [1, 6]})
        # Budget equal to the size is a full scan with EOF rules.
        self.assertEqual(self.scan(b'"ab', max_bytes=3)["gap"]["reason"], "unterminated_quote")
        self.assertEqual(self.scan(b'//ab', max_bytes=4)["gap"], None)
        self.assertEqual(self.scan(b'/*ab', max_bytes=4)["gap"]["reason"],
                         "unterminated_block_comment")
        # Split openers are plain bytes at the boundary, whatever follows.
        for raw in (b"a/x", b"a//", b"a/*"):
            self.assertEqual(self.scan(raw, max_bytes=2)["gap"],
                             {"reason": "byte_limit", "span": [2, 3]})
        self.assertEqual(self.scan(b"", max_bytes=0, max_occurrences=0),
                         {"occurrences": [], "known_prefix_end": 0, "gap": None})

    def test_occurrence_limit_boundaries(self):
        raw = b'"a" // "x"\n "b" "c"'
        self.assertEqual(self.scan(raw, max_occurrences=2)["gap"],
                         {"reason": "occurrence_limit", "span": [16, len(raw)]})
        self.assertEqual(self.scan(raw, max_occurrences=0)["gap"],
                         {"reason": "occurrence_limit", "span": [0, len(raw)]})
        self.assertEqual(self.scan(raw, max_occurrences=3)["gap"], None)
        self.assertEqual(self.scan(b'"a" /* "b" */ // "c"', max_occurrences=1)["gap"], None)
        # Coinciding limits: the byte boundary is reached first and wins.
        self.assertEqual(self.scan(b'"a""b"', max_bytes=3, max_occurrences=1)["gap"],
                         {"reason": "byte_limit", "span": [3, 6]})
        self.assertEqual(self.scan(b'"a""b"', max_bytes=4, max_occurrences=1)["gap"],
                         {"reason": "occurrence_limit", "span": [3, 6]})
        self.assertEqual(self.scan(b'"a"', max_bytes=0, max_occurrences=0)["gap"]["reason"],
                         "byte_limit")

    def test_random_against_reference(self):
        rng = random.Random(4001)
        alphabet = b'"\\/*\n\r\x00\x7e\x7f\x80\xa5a '
        for _ in range(4000):
            raw = bytes(rng.choice(alphabet) for _ in range(rng.randrange(0, 40)))
            kwargs = {}
            if rng.random() < 0.4:
                kwargs["max_bytes"] = rng.randrange(0, len(raw) + 2)
            if rng.random() < 0.4:
                kwargs["max_occurrences"] = rng.randrange(0, 5)
            with self.subTest(raw=raw.hex(), **kwargs):
                self.scan(raw, **kwargs)


ENTRY = {"bytes": 0, "file": "npc/scripts.conf", "line": 1, "manifest_path": "",
         "phase": "npc_config", "sha256": "", "source": ""}


def synthetic(bodies):
    entries, files = [], {}
    for index, body in enumerate(bodies):
        path = f"rathena/npc/s{index % 2}.txt"
        files[path] = body
        entries.append(dict(ENTRY, bytes=len(body), sha256=sha(body), manifest_path=path,
                            source=path[len("rathena/"):], line=index + 1))
    return entries, files


def selection_doc(entries, snapshot_sha):
    return {"status": "complete", "profile": {"name": qi.SELECTION_PROFILE},
            "input": {"snapshot_manifest_sha256": snapshot_sha},
            "npc_sources": {"files": entries}}


class ProducerTest(unittest.TestCase):
    def test_streams_lines_indices_and_counts(self):
        bodies = [b'a\n"x\ny"\r\n"z"', b'"open', b'\n\n"q"']
        entries, files = synthetic(bodies)
        files["rathena/npc/s0.txt"] = bodies[2]      # aliasing paths: last body wins per path
        entries[0] = dict(entries[0], bytes=len(bodies[2]), sha256=sha(bodies[2]))
        sources, occurrences, counts = qi.build_streams(entries, files)
        srows = [json.loads(line) for line in sources.decode().splitlines()]
        orows = [json.loads(line) for line in occurrences.decode().splitlines()]
        self.assertEqual(counts, {"sources": 3, "complete_sources": 2,
                                  "incomplete_sources": 1, "occurrences": 2})
        self.assertEqual([r["selection"] for r in srows], entries)
        self.assertEqual([r["occurrence_count"] for r in srows], [1, 0, 1])
        self.assertEqual(srows[1]["gap"], {"reason": "unterminated_quote", "span": [0, 5]})
        self.assertEqual([(r["occurrence_index"], r["source_index"], r["literal_index"])
                          for r in orows], [(0, 0, 0), (1, 2, 0)])
        self.assertEqual([(r["start_line"], r["end_line"]) for r in orows], [(3, 3), (3, 3)])
        for row in srows + orows:
            self.assertNotIn(b" ", dumps_bytes(row))
        self.assertTrue(sources.endswith(b"\n") and occurrences.endswith(b"\n"))
        self.assertEqual(sources, b"".join(dumps_bytes(r) for r in srows))

        entries, files = synthetic([b'a\n"x\ny\n"\r\n"z"'])
        _, occurrences, _ = qi.build_streams(entries, files)
        lines = [(r["start_line"], r["end_line"])
                 for r in map(json.loads, occurrences.decode().splitlines())]
        self.assertEqual(lines, [(2, 4), (5, 5)])

    def test_documents(self):
        entries, files = synthetic([b'"a"', b'"b'])
        sources, occurrences, counts = qi.build_streams(entries, files)
        producer = {"file": qi.PRODUCER_FILE, "bytes": 1, "sha256": "0" * 64}
        inputs = {k: {"bytes": 1, "sha256": "1" * 64} for k in
                  ("snapshot_manifest", "selection_manifest", "selection_complete", "reader")}
        manifest, complete = qi.build_documents(sources, occurrences, counts, producer, inputs)
        doc, marker = json.loads(manifest), json.loads(complete)
        self.assertEqual(sorted(doc), sorted(["schema", "task", "profile", "state", "producer",
                                              "inputs", "outputs", "counts", "limits", "claims"]))
        self.assertEqual(doc["state"], "incomplete")
        self.assertEqual(doc["limits"], {"source_bytes": 8388608, "source_occurrences": 250000,
                                         "total_occurrences": 2000000,
                                         "output_bytes": 536870912})
        self.assertEqual(doc["claims"]["encoding"], "raw_bytes_only")
        self.assertEqual(doc["outputs"]["sources"], {"file": "quoted-sources.jsonl",
                                                     "bytes": len(sources),
                                                     "sha256": sha(sources), "rows": 2})
        self.assertEqual(sorted(marker), sorted(["schema", "task", "profile", "state",
                                                 "manifest", "outputs"]))
        self.assertEqual(marker["manifest"], {"bytes": len(manifest), "sha256": sha(manifest)})
        self.assertEqual(marker["outputs"], doc["outputs"])
        self.assertEqual(marker["state"], "incomplete")
        self.assertEqual(manifest, dumps_bytes(doc))
        entries, files = synthetic([b'"a"'])
        manifest, _ = qi.build_documents(*qi.build_streams(entries, files), producer, inputs)
        self.assertEqual(json.loads(manifest)["state"], "complete")

    def test_global_caps_are_fatal(self):
        entries, files = synthetic([b'"a""b"', b'"c"'])
        with mock.patch.object(qi, "MAX_TOTAL_OCCURRENCES", 2):
            with self.assertRaisesRegex(qi.InventoryError, "total occurrences"):
                qi.build_streams(entries, files)
        with mock.patch.object(qi, "MAX_OUTPUT_BYTES", 100):
            with self.assertRaisesRegex(qi.InventoryError, "exceed"):
                qi.build_streams(entries, files)

    def test_selection_field_checks(self):
        snap = b"{}"
        entries, files = synthetic([b"x"] * qi.SELECTED_SOURCES)
        files = {e["manifest_path"]: b"x" for e in entries}
        manifest_bytes = b"m"
        completion = {"selection_manifest": qi.SELECTION_MANIFEST,
                      "selection_manifest_sha256": sha(manifest_bytes)}

        def check(selection, comp=completion, fs=files):
            return qi.selected_entries(selection, comp, snap, manifest_bytes, fs)

        good = selection_doc(entries, sha(snap))
        self.assertIs(check(good), entries)
        bad = [
            dict(good, status="incomplete"),
            dict(good, profile={"name": "other"}),
            dict(good, profile=None),
            dict(good, input={"snapshot_manifest_sha256": "0" * 64}),
            dict(good, npc_sources={"files": entries[:-1]}),
            dict(good, npc_sources={"files": entries + entries[:1]}),
            dict(good, npc_sources=[]),
        ]
        for field, value in (("bytes", True), ("bytes", -1), ("line", "1"), ("file", 1),
                             ("sha256", "A" * 64), ("sha256", "0" * 63),
                             ("manifest_path", "rathena/missing.txt"), ("bytes", 2),
                             ("sha256", "0" * 64)):
            changed = list(entries)
            changed[5] = dict(entries[5], **{field: value})
            bad.append(dict(good, npc_sources={"files": changed}))
        extra = list(entries)
        extra[3] = dict(entries[3], extra=1)
        bad.append(dict(good, npc_sources={"files": extra}))
        missing = list(entries)
        missing[3] = {k: v for k, v in entries[3].items() if k != "phase"}
        bad.append(dict(good, npc_sources={"files": missing}))
        for index, selection in enumerate(bad):
            with self.subTest(index=index):
                with self.assertRaises(qi.InventoryError):
                    check(selection)
        for comp in ({"selection_manifest": "other.json",
                      "selection_manifest_sha256": sha(manifest_bytes)},
                     {"selection_manifest": qi.SELECTION_MANIFEST,
                      "selection_manifest_sha256": sha(b"other")}, []):
            with self.assertRaises(qi.InventoryError):
                check(good, comp)

    def test_json_strictness(self):
        for data in (b'{"a":1,"a":2}', b'{"a":NaN}', b"\xff", b"{", b'{"a":Infinity}'):
            with self.assertRaises(qi.InventoryError):
                qi.load_json(data, "x")

    def test_reader_pin(self):
        root = private_dir()
        try:
            data = (HERE / qi.READER_NAME).read_bytes()
            tampered = Path(root, qi.READER_NAME)
            tampered.write_bytes(data.replace(b'VERSION = "1.0.1"', b'VERSION = "1.0.2"'))
            with self.assertRaisesRegex(qi.InventoryError, "pinned"):
                qi.load_reader(tampered)
            link = Path(root, "link.py")
            link.symlink_to(HERE / qi.READER_NAME)
            with self.assertRaises(qi.InventoryError):
                qi.load_reader(link)
            module, loaded = qi.load_reader(HERE / qi.READER_NAME)
            self.assertEqual(loaded, data)
            self.assertTrue(callable(module.read_snapshot))
        finally:
            shutil.rmtree(root)

    def test_selection_directory_refusals(self):
        root = private_dir()
        try:
            def make(name, files):
                path = Path(root, name)
                path.mkdir(mode=0o700)
                for child, body in files.items():
                    if isinstance(body, Path):
                        (path / child).symlink_to(body)
                    elif body is None:
                        os.mkfifo(path / child)
                    else:
                        (path / child).write_bytes(body)
                return str(path)

            m, c = qi.SELECTION_MANIFEST, qi.SELECTION_COMPLETE
            target = Path(root, "real.json")
            target.write_bytes(b"{}")
            cases = {
                "missing": make("missing", {m: b"{}"}),
                "extra": make("extra", {m: b"{}", c: b"{}", ".DS_Store": b""}),
                "pin": make("pin", {m: b"{}", c: b"{}"}),
                "link_file": make("link_file", {m: b"{}", c: target}),
                "fifo": make("fifo", {m: None, c: b"{}"}),
                "relative": "selection",
                "dotted": root + "/pin/../pin",
                "absent": root + "/absent",
            }
            Path(root, "linked").symlink_to(Path(root, "pin"))
            cases["linked_root"] = root + "/linked"
            for label, path in cases.items():
                with self.subTest(label):
                    before = open_fds()
                    with self.assertRaises(qi.InventoryError):
                        qi.read_selection(path)
                    self.assertEqual(open_fds(), before)
        finally:
            shutil.rmtree(root)

    def test_bounded_read_closes_descriptors(self):
        root = private_dir()
        try:
            Path(root, "big").write_bytes(b"x" * 10)
            before = open_fds()
            with self.assertRaisesRegex(qi.InventoryError, "larger"):
                qi.read_regular(root + "/big", 9, "big")
            with self.assertRaisesRegex(qi.InventoryError, "regular"):
                qi.read_regular(root, 9, "dir")
            self.assertEqual(qi.read_regular(root + "/big", 10, "big"), b"x" * 10)
            self.assertEqual(open_fds(), before)
        finally:
            shutil.rmtree(root)


def dumps_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode() + b"\n"


DOCS = [("quoted-sources.jsonl", b"s\n"), ("quoted-occurrences.jsonl", b"o\n"),
        ("quoted-manifest.json", b"{}\n"), ("quoted-complete.json", b"{}\n")]


class PublicationTest(unittest.TestCase):
    def setUp(self):
        self.root = private_dir()
        self.addCleanup(shutil.rmtree, self.root)

    def test_output_target_refusals(self):
        root = self.root
        os.mkdir(root + "/open", 0o755)
        os.chmod(root + "/open", 0o755)
        os.mkdir(root + "/exists", 0o700)
        os.symlink(root + "/nowhere", root + "/dangling")
        os.symlink(root, root + "/alias")
        os.mkdir(root + "/input", 0o700)
        for label, path in {
            "relative": "out", "unnormalized": root + "/./out", "dotdot": root + "/x/..",
            "absent_parent": root + "/absent/out", "public_parent": root + "/open/out",
            "exists": root + "/exists", "dangling": root + "/dangling",
            "linked_parent": root + "/alias/out", "inside_input": root + "/input/out",
            "is_input": root + "/input", "trailing": root + "/out/",
        }.items():
            with self.subTest(label):
                with self.assertRaises(qi.InventoryError):
                    qi.output_target(path, (root + "/input",))
        self.assertEqual(qi.output_target(root + "/out", (root + "/input",)), root + "/out")
        self.assertEqual(os.readlink(root + "/dangling"), root + "/nowhere")

    def test_publish_success_modes_and_order(self):
        target = self.root + "/out"
        order = []
        real = qi._write_file

        def record(fd, name, data, owned):
            order.append(name)
            return real(fd, name, data, owned)

        old = os.umask(0)
        try:
            with mock.patch.object(qi, "_write_file", record):
                qi.publish(target, DOCS)
        finally:
            os.umask(old)
        self.assertEqual(order, [name for name, _ in DOCS])
        self.assertEqual(stat.S_IMODE(os.lstat(target).st_mode), 0o700)
        self.assertEqual(sorted(os.listdir(target)), sorted(name for name, _ in DOCS))
        for name, data in DOCS:
            self.assertEqual(stat.S_IMODE(os.lstat(f"{target}/{name}").st_mode), 0o600)
            self.assertEqual(Path(target, name).read_bytes(), data)
        with self.assertRaises(FileExistsError):
            qi.publish(target, DOCS)

    def test_write_failure_removes_owned_artifacts(self):
        target = self.root + "/out"
        real = qi._write_file

        def failing(fd, name, data, owned):
            if name == "quoted-manifest.json":
                raise OSError(28, "No space left on device")
            return real(fd, name, data, owned)

        with mock.patch.object(qi, "_write_file", failing):
            with self.assertRaisesRegex(qi.InventoryError, "No space"):
                qi.publish(target, DOCS)
        self.assertFalse(os.path.lexists(target))

    def test_read_back_mismatch_and_foreign_data_preserved(self):
        target = self.root + "/out"
        real = qi._read_back

        def corrupt(dir_fd, name, data, owned):
            real(dir_fd, name, data, owned)
            if name == "quoted-complete.json":
                with open(f"{target}/foreign.txt", "wb") as handle:
                    handle.write(b"keep")
                raise qi.InventoryError("injected readback differs")

        with mock.patch.object(qi, "_read_back", corrupt):
            with self.assertRaisesRegex(qi.InventoryError, "differs|inspect"):
                qi.publish(target, DOCS)
        self.assertEqual(os.listdir(target), ["foreign.txt"])
        self.assertFalse(os.path.lexists(f"{target}/quoted-complete.json"))

    def test_replaced_artifact_is_not_removed(self):
        target = self.root + "/out"
        real = qi._write_file
        guard = []

        def swap(fd, name, data, owned):
            real(fd, name, data, owned)
            if name == "quoted-occurrences.jsonl":
                guard.append(os.open(f"{target}/quoted-sources.jsonl", os.O_RDONLY))
                old = os.fstat(guard[0])
                os.unlink(f"{target}/quoted-sources.jsonl")
                Path(target, "quoted-sources.jsonl").write_bytes(b"foreign")
                new = os.lstat(f"{target}/quoted-sources.jsonl")
                self.assertNotEqual((old.st_dev, old.st_ino), (new.st_dev, new.st_ino))
                raise OSError(5, "I/O error")

        try:
            with mock.patch.object(qi, "_write_file", swap):
                with self.assertRaisesRegex(qi.InventoryError, "inspect"):
                    qi.publish(target, DOCS)
        finally:
            for fd in guard:
                os.close(fd)
        self.assertEqual(os.listdir(target), ["quoted-sources.jsonl"])
        self.assertEqual(Path(target, "quoted-sources.jsonl").read_bytes(), b"foreign")

    def test_zero_progress_refuses_and_short_positive_writes_finish(self):
        target = self.root + "/zero"
        calls = []

        def zero(fd, data):
            calls.append(fd)
            if len(calls) == 1:
                return 0
            raise OSError(5, "bounded repeated-zero sentinel")

        with mock.patch.object(qi.os, "write", zero):
            with self.assertRaisesRegex(qi.InventoryError, "no write progress"):
                qi.publish(target, DOCS)
        self.assertEqual(len(calls), 1)
        self.assertFalse(os.path.lexists(target))
        real_write = os.write
        target = self.root + "/short"
        with mock.patch.object(qi.os, "write", lambda fd, data: real_write(fd, data[:1])):
            qi.publish(target, DOCS)
        for name, data in DOCS:
            self.assertEqual(Path(target, name).read_bytes(), data)

    def test_final_directory_close_failure_is_cleaned_and_main_returns_two(self):
        target = self.root + "/out"
        real_close = os.close
        fired = []

        def close(fd):
            info = os.fstat(fd)
            if stat.S_ISDIR(info.st_mode) and not fired:
                fired.append(fd)
                real_close(fd)
                raise OSError(5, "final directory close control")
            return real_close(fd)

        def run(*args):
            qi.publish(target, DOCS)
            return {}

        with mock.patch.object(qi.os, "close", close), mock.patch.object(qi, "run", run):
            with mock.patch.object(sys, "stderr", __import__("io").StringIO()) as err:
                code = qi.main(["--snapshot", "/synthetic", "--selection-dir", "/selection",
                                "--output", target])
        self.assertEqual(code, 2)
        self.assertEqual(len(fired), 1)
        self.assertIn("final directory close control", err.getvalue())
        self.assertFalse(os.path.lexists(target))

    def test_close_before_real_close_does_not_retry_uncertain_integer(self):
        target = self.root + "/out"
        real_close = os.close
        uncertain, attempts = [], []

        def close(fd):
            info = os.fstat(fd)
            if stat.S_ISDIR(info.st_mode):
                attempts.append(fd)
                if not uncertain:
                    uncertain.append((fd, info.st_dev, info.st_ino))
                    raise OSError(5, "before real close control")
            return real_close(fd)

        try:
            with mock.patch.object(qi.os, "close", close):
                with self.assertRaisesRegex(qi.InventoryError, "before real close"):
                    qi.publish(target, DOCS)
            self.assertEqual(attempts.count(uncertain[0][0]), 1)
            self.assertFalse(os.path.lexists(target))
        finally:
            # The fixture knows this injected close did not occur. Production does
            # not retry an uncertain descriptor; the CLI's process exit releases it.
            if uncertain:
                fd, dev, ino = uncertain[0]
                current = os.fstat(fd)
                self.assertEqual((current.st_dev, current.st_ino), (dev, ino))
                real_close(fd)

    def test_each_fsync_and_marker_file_close_failure_removes_owned_marker(self):
        real_fsync, real_close = os.fsync, os.close
        for name in [n for n, _ in DOCS] + ["directory", "marker_close"]:
            with self.subTest(name=name):
                target = self.root + "/" + name.replace(".", "_")
                fired = []

                def matching(fd):
                    info = os.fstat(fd)
                    if name == "directory":
                        return stat.S_ISDIR(info.st_mode)
                    path = Path(target, "quoted-complete.json" if name == "marker_close" else name)
                    if not path.exists():
                        return False
                    current = path.stat()
                    return (info.st_dev, info.st_ino) == (current.st_dev, current.st_ino)

                def fsync(fd):
                    if name != "marker_close" and not fired and matching(fd):
                        fired.append(True)
                        raise OSError(5, "fsync control")
                    return real_fsync(fd)

                def close(fd):
                    if name == "marker_close" and not fired and matching(fd):
                        fired.append(True)
                        real_close(fd)
                        raise OSError(5, "marker close control")
                    return real_close(fd)

                with mock.patch.object(qi.os, "fsync", fsync), mock.patch.object(qi.os, "close", close):
                    with self.assertRaises(qi.InventoryError):
                        qi.publish(target, DOCS)
                self.assertEqual(fired, [True])
                self.assertFalse(os.path.lexists(target))

    def test_final_fsync_mode_drift_is_refused(self):
        real_fsync = os.fsync
        for name in ("quoted-sources.jsonl", "directory"):
            with self.subTest(name=name):
                target = self.root + "/" + name.replace(".", "_")

                def fsync(fd):
                    if stat.S_ISDIR(os.fstat(fd).st_mode):
                        path = target if name == "directory" else str(Path(target, name))
                        os.chmod(path, 0o755 if name == "directory" else 0o644)
                    return real_fsync(fd)

                with mock.patch.object(qi.os, "fsync", fsync):
                    with self.assertRaisesRegex(qi.InventoryError, "mode"):
                        qi.publish(target, DOCS)
                self.assertFalse(os.path.lexists(target))

    def test_same_inode_corrupted_readback_is_refused(self):
        target = self.root + "/out"
        real_write = qi._write_file

        def corrupt(fd, name, data, owned):
            real_write(fd, name, data, owned)
            if name == "quoted-complete.json":
                with open(Path(target, name), "r+b") as handle:
                    handle.write(b"X")

        with mock.patch.object(qi, "_write_file", corrupt):
            with self.assertRaisesRegex(qi.InventoryError, "differs"):
                qi.publish(target, DOCS)
        self.assertFalse(os.path.lexists(target))

    def test_identical_foreign_replacement_is_refused_and_preserved(self):
        target = self.root + "/out"
        real_write = qi._write_file
        guard = []

        def replace(fd, name, data, owned):
            real_write(fd, name, data, owned)
            if name == "quoted-sources.jsonl":
                path = Path(target, name)
                guard.append(os.open(path, os.O_RDONLY | os.O_NOFOLLOW))
                old = os.fstat(guard[0])
                path.unlink()
                newfd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                try:
                    with os.fdopen(newfd, "wb", closefd=False) as handle:
                        handle.write(data)
                    new = os.fstat(newfd)
                    self.assertNotEqual((old.st_dev, old.st_ino), (new.st_dev, new.st_ino))
                finally:
                    os.close(newfd)

        try:
            with mock.patch.object(qi, "_write_file", replace):
                with self.assertRaisesRegex(qi.InventoryError, "identity"):
                    qi.publish(target, DOCS)
            self.assertEqual(os.listdir(target), ["quoted-sources.jsonl"])
            self.assertEqual(Path(target, "quoted-sources.jsonl").read_bytes(), DOCS[0][1])
        finally:
            for fd in guard:
                os.close(fd)


def cli(*args, env=None):
    return subprocess.run([sys.executable, "-I", "-B", str(TOOL), *args],
                          capture_output=True, text=True, env=env, timeout=600)


@unittest.skipUnless(FROZEN, "QUOTED_SOURCE_FROZEN_ROOT is not set")
class ActualDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = os.path.join(FROZEN, "snapshot")
        cls.selection = os.path.join(FROZEN, "selection")
        cls.root = private_dir()
        cls.out = cls.root + "/actual"
        cls.result = cli("--snapshot", cls.snapshot, "--selection-dir", cls.selection,
                         "--output", cls.out)
        cls.selection_doc = json.loads(Path(cls.selection, "selection-manifest.json").read_bytes())

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root)

    def args(self, output, snapshot=None, selection=None):
        return ("--snapshot", snapshot or self.snapshot,
                "--selection-dir", selection or self.selection, "--output", output)

    def test_full_inventory(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr)
        summary = json.loads(self.result.stdout)
        out = Path(self.out)
        self.assertEqual(stat.S_IMODE(os.lstat(out).st_mode), 0o700)
        self.assertEqual(sorted(os.listdir(out)), sorted(name for name, _ in DOCS))
        blobs = {}
        for name in os.listdir(out):
            self.assertEqual(stat.S_IMODE(os.lstat(out / name).st_mode), 0o600)
            blobs[name] = (out / name).read_bytes()
        manifest = json.loads(blobs["quoted-manifest.json"])
        marker = json.loads(blobs["quoted-complete.json"])
        self.assertEqual(blobs["quoted-manifest.json"], dumps_bytes(manifest))
        self.assertEqual(blobs["quoted-complete.json"], dumps_bytes(marker))
        self.assertEqual(marker["manifest"], {"bytes": len(blobs["quoted-manifest.json"]),
                                              "sha256": sha(blobs["quoted-manifest.json"])})
        self.assertEqual(marker["outputs"], manifest["outputs"])
        self.assertEqual((manifest["schema"], manifest["task"], manifest["profile"]),
                         (1, "T06.004.001", "raw-quoted-byte-policy-v1"))
        self.assertEqual(manifest["producer"], {"file": "tools/renewal/quoted_source_inventory.py",
                                                "bytes": len(TOOL.read_bytes()),
                                                "sha256": sha(TOOL.read_bytes())})
        self.assertEqual(manifest["inputs"], {
            "snapshot_manifest": {"bytes": 810498, "sha256": qi.PIN_SNAPSHOT_MANIFEST["sha256"]},
            "selection_manifest": {"bytes": 953299,
                                   "sha256": qi.PIN_SELECTION_MANIFEST["sha256"]},
            "selection_complete": {"bytes": 185, "sha256": qi.PIN_SELECTION_COMPLETE["sha256"]},
            "reader": {"bytes": 36455, "sha256": qi.PIN_READER["sha256"]}})
        for key, name in (("sources", "quoted-sources.jsonl"),
                          ("occurrences", "quoted-occurrences.jsonl")):
            data = blobs[name]
            self.assertEqual(manifest["outputs"][key],
                             {"file": name, "bytes": len(data), "sha256": sha(data),
                              "rows": data.count(b"\n")})
        text = b"".join(blobs.values())
        self.assertNotIn(FROZEN.encode(), text)
        self.assertNotIn(self.root.encode(), text)

        entries = self.selection_doc["npc_sources"]["files"]
        self.assertEqual(len(entries), 839)
        sources = [json.loads(line) for line in blobs["quoted-sources.jsonl"].splitlines()]
        occurrences = blobs["quoted-occurrences.jsonl"].splitlines()
        self.assertEqual([s["selection"] for s in sources], entries)
        self.assertEqual([s["source_index"] for s in sources], list(range(839)))
        complete = sum(s["gap"] is None for s in sources)
        counts = {"sources": 839, "complete_sources": complete,
                  "incomplete_sources": 839 - complete, "occurrences": len(occurrences)}
        self.assertEqual(manifest["counts"], counts)
        self.assertEqual(summary["counts"], counts)
        self.assertEqual(manifest["state"], "complete" if complete == 839 else "incomplete")
        self.assertEqual(summary["state"], manifest["state"])
        self.assertEqual(sum(s["occurrence_count"] for s in sources), len(occurrences))

        cursor = 0
        snapshot = Path(self.snapshot)
        for source in sources:
            raw = (snapshot / source["selection"]["manifest_path"]).read_bytes()
            self.assertEqual(sha(raw), source["selection"]["sha256"])
            expected = reference_scan(raw)
            self.assertEqual((source["known_prefix_end"], source["gap"]),
                             (expected["known_prefix_end"], expected["gap"]))
            self.assertEqual(source["occurrence_count"], len(expected["occurrences"]))
            for item in expected["occurrences"]:
                row = json.loads(occurrences[cursor])
                start, end = item["span"]
                self.assertEqual(row, dict(item, occurrence_index=cursor,
                                           source_index=source["source_index"],
                                           start_line=raw.count(b"\n", 0, start) + 1,
                                           end_line=raw.count(b"\n", 0, end - 1) + 1))
                cursor += 1
        self.assertEqual(cursor, len(occurrences))

    def test_deterministic_rerun(self):
        out = self.root + "/again"
        result = cli(*self.args(out))
        self.assertEqual(result.returncode, 0, result.stderr)
        for name, _ in DOCS:
            self.assertEqual(Path(out, name).read_bytes(), Path(self.out, name).read_bytes())
        shutil.rmtree(out)

    def test_cli_refusals_leave_no_marker(self):
        root = self.root
        os.mkdir(root + "/existing", 0o700)
        Path(root, "existing/keep").write_bytes(b"keep")
        os.symlink(self.snapshot, root + "/snapshot-link")
        os.symlink(self.selection, root + "/selection-link")
        tampered = root + "/selection-tampered"
        os.mkdir(tampered, 0o700)
        for name in ("selection-manifest.json", "selection-complete.json"):
            shutil.copyfile(Path(self.selection, name), Path(tampered, name))
        data = bytearray(Path(tampered, "selection-complete.json").read_bytes())
        data[-2] ^= 1
        Path(tampered, "selection-complete.json").write_bytes(bytes(data))
        linked_member = root + "/selection-linked-member"
        os.mkdir(linked_member, 0o700)
        shutil.copyfile(Path(self.selection, "selection-manifest.json"),
                        Path(linked_member, "selection-manifest.json"))
        os.symlink(Path(self.selection, "selection-complete.json"),
                   Path(linked_member, "selection-complete.json"))
        extra = root + "/selection-extra"
        shutil.copytree(self.selection, extra)
        os.chmod(extra, 0o700)
        Path(extra, ".DS_Store").write_bytes(b"")
        fake_snapshot = root + "/fake-snapshot"
        os.mkdir(fake_snapshot, 0o700)
        Path(fake_snapshot, "snapshot-manifest.json").write_bytes(b'{"files":[]}')
        cases = {
            "existing": self.args(root + "/existing"),
            "relative_output": self.args("relative-out"),
            "relative_snapshot": self.args(root + "/o1", snapshot="snapshot"),
            "linked_snapshot": self.args(root + "/o2", snapshot=root + "/snapshot-link"),
            "linked_selection": self.args(root + "/o3", selection=root + "/selection-link"),
            "tampered_selection": self.args(root + "/o4", selection=tampered),
            "linked_member": self.args(root + "/o5", selection=linked_member),
            "extra_member": self.args(root + "/o6", selection=extra),
            "fake_snapshot": self.args(root + "/o7", snapshot=fake_snapshot),
            "swapped_inputs": self.args(root + "/o8", snapshot=self.selection,
                                        selection=self.snapshot),
            "inside_input": self.args(self.snapshot + "/out"),
        }
        for label, args in cases.items():
            with self.subTest(label):
                result = cli(*args)
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn("error:", result.stderr)
                self.assertEqual(result.stdout, "")
        self.assertEqual(os.listdir(root + "/existing"), ["keep"])
        for n in range(1, 9):
            self.assertFalse(os.path.lexists(f"{root}/o{n}"))
        self.assertFalse(os.path.lexists(self.snapshot + "/out"))

    def test_actual_write_failure(self):
        out = self.root + "/fail"
        real = qi._write_file

        def failing(fd, name, data, owned):
            if name == "quoted-complete.json":
                raise OSError(28, "No space left on device")
            return real(fd, name, data, owned)

        with mock.patch.object(qi, "_write_file", failing):
            with self.assertRaises(qi.InventoryError):
                qi.run(self.snapshot, self.selection, out)
        self.assertFalse(os.path.lexists(out))

    def test_mutants_differ_on_actual_sources(self):
        source = TOOL.read_text(encoding="ascii")
        entries = self.selection_doc["npc_sources"]["files"]
        bodies = [(Path(self.snapshot) / e["manifest_path"]).read_bytes() for e in entries]
        # The escape-eligibility mutant is caught by the fixture only: no actual quoted
        # content has a backslash after a byte > 0x7e, so it changes no actual result.
        for label in ("quote_in_comment", "deduplicate"):
            old, new = MUTATIONS[label]
            mutant = load_module(source.replace(old, new), f"actual_{label}")
            with self.subTest(label):
                self.assertTrue(any(mutant.scan_source(b) != qi.scan_source(b) for b in bodies))


if __name__ == "__main__":
    unittest.main()
