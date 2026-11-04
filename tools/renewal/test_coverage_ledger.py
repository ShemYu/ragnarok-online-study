#!/usr/bin/env python3
"""Authored controls for coverage_ledger (T06.005.001).

Materializes the public synthetic fixture docs/project/fixtures/T06.005.001-cases.json
into a fresh temporary root, then checks the valid ledger and every negative
case (duplicate/missing root IDs, pin drift, unsupported verification
promotion, count reconciliation, provenance drift). No private input, real
asset, network, browser or runtime action is used.

Run: /usr/bin/python3 -I -B tools/renewal/test_coverage_ledger.py -v
"""

import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import coverage_ledger as cl  # noqa: E402

REPO = HERE.parents[1]
CASES = json.loads((REPO / "docs/project/fixtures/T06.005.001-cases.json").read_text())
PIN_ORDER = list(json.loads(
    (REPO / "docs/project/fixtures/T06.005.001-inputs.json").read_text())["inputs"])


def _parts(pointer):
    return [p.replace("~1", "/").replace("~0", "~") for p in pointer.strip("/").split("/")]


def _apply(doc, op, pointer, value=None):
    parts = _parts(pointer)
    parent = doc
    for part in parts[:-1]:
        parent = parent[int(part)] if isinstance(parent, list) else parent[part]
    last = parts[-1]
    key = int(last) if isinstance(parent, list) else last
    if op == "set":
        parent[key] = copy.deepcopy(value)
    elif op == "delete":
        del parent[key]
    elif op == "duplicate":
        parent.insert(key + 1, copy.deepcopy(parent[key]))
    else:
        raise ValueError(op)


def _dump(doc):
    return (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode()


def materialize(root, files):
    """Write fixture files, resolving @sha/@pin/@profile-gap placeholders."""
    pending = copy.deepcopy(files)
    written = {}

    def resolve(node, profile):
        if isinstance(node, dict):
            if set(node) == {"@sha"}:
                if node["@sha"] not in written:
                    raise KeyError(node["@sha"])
                return written[node["@sha"]]["sha256"]
            if set(node) == {"@pin"}:
                if node["@pin"] not in written:
                    raise KeyError(node["@pin"])
                w = written[node["@pin"]]
                return {"path": node["@pin"], "bytes": w["bytes"], "sha256": w["sha256"]}
            return {k: resolve(v, profile) for k, v in node.items()}
        if isinstance(node, list):
            return [resolve(v, profile) for v in node]
        if isinstance(node, str) and node.startswith("@profile-gap:"):
            if profile is None:
                raise KeyError("profile")
            return copy.deepcopy(profile["gaps"][int(node.split(":")[1])])
        return node

    while pending:
        progressed = False
        for rel in list(pending):
            profile = written.get("docs/project/fixtures/T07.007.014-profile.json", {}).get("doc")
            try:
                doc = resolve(pending[rel], profile)
            except KeyError:
                continue
            data = _dump(doc)
            path = Path(root) / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            written[rel] = {"doc": doc, "bytes": len(data),
                            "sha256": hashlib.sha256(data).hexdigest()}
            del pending[rel]
            progressed = True
        if not progressed:
            raise RuntimeError(f"unresolvable placeholders in {sorted(pending)}")
    return written


def pins_for(written):
    return {"schema": cl.INPUTS_SCHEMA, "task": "T06.005.001", "source_commit": "synthetic",
            "input_boundary": "synthetic fixture",
            "inputs": [{"path": e["path"], "bytes": written[e["path"]]["bytes"],
                        "sha256": written[e["path"]]["sha256"],
                        "role": "qualified_metadata_only"} for e in PIN_ORDER]}


class Harness:
    def __init__(self, files=None):
        self.tmp = tempfile.TemporaryDirectory(prefix="t06-005-001-")
        self.root = os.path.join(self.tmp.name, "root")
        os.mkdir(self.root)
        self.written = materialize(self.root, files or CASES["files"])
        self.pins = pins_for(self.written)
        self.pins_path = os.path.join(self.tmp.name, "pins.json")
        self.write_pins()

    def write_pins(self):
        Path(self.pins_path).write_text(json.dumps(self.pins))

    def close(self):
        self.tmp.cleanup()


class CoverageLedgerTests(unittest.TestCase):
    def test_fixture_pins_match_frozen_pin_paths(self):
        self.assertEqual(sorted(CASES["files"]), sorted(e["path"] for e in PIN_ORDER))

    def test_valid_synthetic_ledger(self):
        h = Harness()
        try:
            ledger = cl.generate(h.pins_path, h.root)
            self.assertTrue(cl.validate_ledger(ledger))
            summary = ledger["gap_summary"]
            for key, want in CASES["expect_valid"].items():
                self.assertEqual(summary[key], want, key)
            self.assertEqual([r["root_ordinal"] for r in ledger["gap_roots"]], [5, 9, 11])
            self.assertEqual(ledger["gap_roots"][1]["pointers"]["gap_extract"], "/gaps/2")
            for cat in cl.CATEGORIES:
                self.assertTrue(any(f["state"] == "unknown" for f in ledger["categories"][cat]))
            states = {r["functional_gap"] for r in ledger["gap_roots"]}
            self.assertEqual(states, {"open"})
            self.assertEqual(cl.dump(ledger), cl.dump(cl.generate(h.pins_path, h.root)))
        finally:
            h.close()

    def test_cli_generate_check_validate(self):
        h = Harness()
        try:
            out = os.path.join(h.tmp.name, "ledger.json")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cl.main(["generate", "--inputs", h.pins_path,
                                          "--root", h.root, "--out", out]), 0)
                self.assertEqual(cl.main(["check", "--inputs", h.pins_path,
                                          "--root", h.root, "--ledger", out]), 0)
                self.assertEqual(cl.main(["validate", "--ledger", out]), 0)
            with open(out, "ab") as handle:
                handle.write(b" ")
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(cl.main(["check", "--inputs", h.pins_path,
                                          "--root", h.root, "--ledger", out]), 2)
            self.assertIn("LEDGER_DRIFT", err.getvalue())
        finally:
            h.close()

    def test_negative_cases(self):
        seen = set()
        for case in CASES["negative_cases"]:
            with self.subTest(case=case["id"]):
                self.assertNotIn(case["id"], seen)
                seen.add(case["id"])
                self.assertEqual(self._run_case(case), case["expect"])

    def _run_case(self, case):
        stage = case["stage"]
        files = copy.deepcopy(CASES["files"])
        if stage == "fixture":
            _apply(files[case["file"]], case["op"], case["pointer"], case.get("value"))
        h = Harness(files)
        try:
            root = h.root
            if stage == "materialized":
                path = Path(h.root) / case["file"]
                if case["op"] == "append_bytes":
                    with open(path, "ab") as handle:
                        handle.write(case["value"].encode())
                elif case["op"] == "remove_file":
                    path.unlink()
            elif stage == "pins":
                _apply(h.pins, case["op"], case["pointer"], case.get("value"))
                h.write_pins()
            elif stage == "root":
                root = case["value"]
            try:
                ledger = cl.generate(h.pins_path, root)
            except cl.Refusal as refusal:
                if stage == "ledger":
                    self.fail(f"valid base refused: {refusal}")
                return refusal.code
            if stage != "ledger":
                return "ACCEPTED"
            _apply(ledger, case["op"], case["pointer"], case.get("value"))
            try:
                cl.validate_ledger(ledger)
            except cl.Refusal as refusal:
                return refusal.code
            return "ACCEPTED"
        finally:
            h.close()

    def test_every_required_negative_class_present(self):
        codes = {c["expect"] for c in CASES["negative_cases"]}
        for required in ("DUPLICATE_ROOT_ID", "MISSING_ROOT_ID", "PIN_DRIFT",
                         "UNSUPPORTED_PROMOTION", "COUNT_MISMATCH"):
            self.assertIn(required, codes)

    def test_committed_public_ledger_is_valid(self):
        path = REPO / "docs/project/fixtures/T06.005.001-ledger.json"
        if not path.exists():
            self.skipTest("public ledger not generated yet")
        ledger = json.loads(path.read_text())
        self.assertTrue(cl.validate_ledger(ledger))
        self.assertEqual(len(ledger["gap_roots"]), 82)
        text = path.read_text()
        self.assertNotIn("/Users/", text)


if __name__ == "__main__":
    unittest.main()
