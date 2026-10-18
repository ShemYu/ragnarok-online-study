"""Tests for yaml_graph_inventory. Run: python3 -I -m unittest discover -s tools/renewal

Fixtures are small authored YAML strings parsed by the real pinned /usr/bin/ruby
Psych adapter; no stock file is copied. Tests named "native" check database.cpp
rules; "policy" tests check the additional bounded parser/cap/path refusals,
which are unsupported states, never native results. Publication tests write
temporary private directories only.

The actual-input test reads the canonical snapshot from the absolute path in
$T06_YAML_SNAPSHOT and is skipped when it is unset or absent. CLI pins, profile
and parser cannot be bypassed.
"""

import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import yaml_graph_inventory as yg  # noqa: E402

TOOL = Path(__file__).resolve().with_name("yaml_graph_inventory.py")
ITEM = ({"database": "ITEM_DB", "path": "db/item_db.yml", "version": 3, "minimum_version": 1},)
TWO = ITEM + ({"database": "MOB_DB", "path": "db/mob_db.yml", "version": 5,
               "minimum_version": 1},)
H = "Header:\n  Type: ITEM_DB\n  Version: 3\n"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def files_of(**named):
    """Keyword names use __ for '/' and _yml suffix for '.yml'; values are text or bytes."""
    out = {}
    for name, body in named.items():
        path = "rathena/" + name.replace("__", "/").replace("_yml", ".yml")
        out[path] = body if isinstance(body, bytes) else body.encode("utf-8")
    return out


def go(files, roots=ITEM, profile=None, limits=None):
    rows = []
    graph = yg.catalog(files, rows.append, roots, profile or yg.PROFILE, limits or yg.LIMITS)
    status = yg.summarize(graph)[0]
    return graph, rows, status


def imports(*entries):
    return "Footer:\n  Imports:\n" + "".join(entries)


def edge(path, mode=None, generator=None):
    text = f"  - Path: {path}\n"
    if mode is not None:
        text += f"    Mode: {mode}\n"
    if generator is not None:
        text += f"    Generator: {generator}\n"
    return text


def body(*rows):
    return "Body:\n" + "".join(rows)


class HeaderTests(unittest.TestCase):
    """native: database.cpp:37-76 and load() order."""

    def check_failure(self, text, detail):
        graph, rows, status = go(files_of(db__item_db_yml=text + body("  - Id: 1\n")))
        self.assertEqual(status, "incomplete")
        self.assertEqual(rows, [])
        self.assertEqual(graph.visits[0]["status"], "known_failure_header")
        self.assertIs(graph.visits[0]["modeled_graph_return"], False)
        self.assertEqual(graph.known_failures[0]["detail"], detail)
        return graph

    def test_missing_wrong_null_type(self):
        self.check_failure("Other: 1\n", "no Header node")
        self.check_failure("Header: {}\n", "no Header node (empty mapping has no children)")
        self.check_failure("Header:\n  Version: 3\n", "missing Type")
        self.check_failure("Header:\n  Type: MOB_DB\n  Version: 3\n", "Type mismatch")
        for null in ("", "~", "null", "Null", "NULL"):
            self.check_failure(f"Header:\n  Type: {null}\n  Version: 3\n", "Type has no value")
        # quoted ~ is text, not null: a supported wrong Type
        self.check_failure("Header:\n  Type: '~'\n  Version: 3\n", "Type mismatch")

    def test_version_rules(self):
        self.check_failure("Header:\n  Type: ITEM_DB\n", "missing Version")
        self.check_failure("Header:\n  Type: ITEM_DB\n  Version:\n", "Version has no value")
        self.check_failure("Header:\n  Type: ITEM_DB\n  Version: 4\n", "Version above current")
        graph = self.check_failure("Header:\n  Type: ITEM_DB\n  Version: 0\n",
                                   "Version below minimum")
        self.assertEqual(graph.visits[0]["header"]["version_value"], 0)

    def test_older_version_warns_and_continues(self):
        text = "Header:\n  Type: ITEM_DB\n  Version: \"02\"\n" + body("  - Id: 1\n")
        graph, rows, status = go(files_of(db__item_db_yml=text))
        self.assertEqual(status, "complete")
        self.assertEqual(len(rows), 1)
        header = graph.visits[0]["header"]
        self.assertEqual(header["compatibility"], "older_warning")
        self.assertEqual(header["version_value"], 2)  # leading zero stays decimal
        self.assertEqual(header["version"]["style"], "double_quoted")
        self.assertEqual(header["version"]["text"], "02")
        self.assertEqual(graph.diagnostics[0]["kind"], "older_version")

    def test_block_control_scalars_are_text(self):
        text = "Header:\n  Type: |-\n    ITEM_DB\n  Version: >-\n    3\n" + body("  - Id: 1\n")
        graph, rows, status = go(files_of(db__item_db_yml=text))
        self.assertEqual(status, "complete")
        self.assertEqual(graph.visits[0]["header"]["type"]["style"], "literal")

    def test_duplicate_header_pair_uses_first(self):
        good_first = "Header:\n  Type: ITEM_DB\n  Type: MOB_DB\n  Version: 3\n"
        self.assertEqual(go(files_of(db__item_db_yml=good_first))[2], "complete")
        self.check_failure("Header:\n  Type: MOB_DB\n  Type: ITEM_DB\n  Version: 3\n",
                           "Type mismatch")

    def test_version_policy_refusals(self):
        """policy: other bases, signs and overflow are unsupported, not native failures."""
        for text in ("0x3", "+3", "70000", "3.0", "''", "abc", "99999999999999999999"):
            graph, rows, status = go(files_of(
                db__item_db_yml=f"Header:\n  Type: ITEM_DB\n  Version: {text}\n"))
            self.assertEqual(status, "unsupported", text)
            self.assertEqual(graph.stop["kind"], "unsupported_version_text")
            self.assertEqual(graph.known_failures, [])

    def test_header_shapes_unsupported(self):
        for text in ("Header: x\n", "Header:\n  - Type\n", "Header:\n  Type: [ITEM_DB]\n",
                     "Header:\n  Type: ITEM_DB\n  Version: {a: 1}\n"):
            graph, rows, status = go(files_of(db__item_db_yml=text))
            self.assertEqual(status, "unsupported", text)
            self.assertEqual(graph.stop["kind"], "unsupported_control_shape")


class ClearTests(unittest.TestCase):
    """native: database.cpp:132-138, 253-277."""

    def clear_result(self, value):
        text = f"Header:\n  Type: ITEM_DB\n  Version: 3\n  Clear: {value}\n" + body("  - Id: 1\n")
        graph, rows, status = go(files_of(db__item_db_yml=text))
        return graph, rows, status

    def test_valid_true_and_false(self):
        for value in ("true", "TRUE", "True", "'tRuE'", "\"true\"", "|-\n    true"):
            graph, rows, status = self.clear_result(value)
            self.assertEqual(status, "complete", value)
            self.assertEqual(graph.visits[0]["clear"]["result"], "clear_event", value)
            self.assertEqual(rows[0]["epoch"], 1)
            self.assertEqual(len(graph.clears), 1)
        for value in ("false", "FALSE", "'False'"):
            graph, rows, _ = self.clear_result(value)
            self.assertEqual(graph.visits[0]["clear"]["result"], "false_no_clear")
            self.assertEqual(rows[0]["epoch"], 0)

    def test_invalid_and_null_warn_and_continue(self):
        for value in ("yes", "1", "' true'", "'true '", "~", "", "null", "|\n    true"):
            graph, rows, status = self.clear_result(value)
            self.assertEqual(status, "complete", value)
            self.assertEqual(graph.visits[0]["clear"]["result"], "invalid_no_clear", value)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["epoch"], 0)
            self.assertEqual(graph.diagnostics[-1]["kind"], "clear_invalid")
        graph, _, _ = self.clear_result("'~'")
        self.assertEqual(graph.diagnostics[-1]["reason"], "unknown_boolean_text")

    def test_non_ascii_lowering_is_not_applied(self):
        graph, _, _ = self.clear_result("\"truİ\"")
        self.assertEqual(graph.visits[0]["clear"]["result"], "invalid_no_clear")

    def test_container_clear_unsupported(self):
        graph, rows, status = self.clear_result("[true]")
        self.assertEqual(status, "unsupported")
        self.assertEqual(rows, [])

    def test_clear_in_import_keeps_history(self):
        files = files_of(
            db__item_db_yml=H + body("  - Id: 1\n") + imports(edge("db/b.yml")),
            db__b_yml="Header:\n  Type: ITEM_DB\n  Version: 3\n  Clear: true\n"
                      + body("  - Id: 1\n"))
        graph, rows, status = go(files)
        self.assertEqual(status, "complete")
        self.assertEqual([(r["epoch"], r["file"]) for r in rows],
                         [(0, "db/item_db.yml"), (1, "db/b.yml")])
        self.assertEqual(graph.clears[0]["visit"], 1)


class BodyTests(unittest.TestCase):

    def test_script_fake_footer_creates_no_edge(self):
        row = ("  - Id: 1\n    Script: |\n      Footer:\n        Imports:\n"
               "        - Path: db/x.yml\n")
        graph, rows, status = go(files_of(db__item_db_yml=H + body(row)))
        self.assertEqual(status, "complete")
        self.assertEqual(graph.edges, [])
        self.assertEqual([f["key"] for f in rows[0]["fields"]], ["Id", "Script"])

    def test_raw_ids(self):
        rows_text = ("  - Id: 0x10\n"
                     "  - Name: none\n"
                     "  - Id: 1\n    Id: '010'\n"
                     "  - Id: [1]\n"
                     "  - Id:\n")
        graph, rows, status = go(files_of(db__item_db_yml=H + body(rows_text)))
        self.assertEqual(status, "complete")
        self.assertEqual(rows[0]["raw_ids"][0]["text"], "0x10")
        self.assertEqual(rows[1]["raw_ids"], [])
        ids = rows[2]["raw_ids"]
        self.assertEqual([(i["field_ordinal"], i["text"], i["style"]) for i in ids],
                         [(0, "1", "plain"), (1, "010", "single_quoted")])
        self.assertEqual(rows[3]["raw_ids"][0]["kind"], "sequence")
        self.assertTrue(rows[4]["raw_ids"][0]["null"])
        stats = graph.id_stats["ITEM_DB"]
        self.assertEqual(stats, {"occurrences": 5, "rows_without_id": 1,
                                 "rows_with_several_ids": 1, "non_scalar_ids": 1})

    def test_duplicate_keys_retained(self):
        once = H + body("  - Id: 1\n    Trade: {A: 1}\n")
        twice = H + body("  - Id: 1\n    Trade: {A: 1}\n    Trade: {B: 2}\n")
        nested = H + body("  - Id: 1\n    Trade: {A: 1, A: 2}\n")
        rows = [go(files_of(db__item_db_yml=t))[1][0] for t in (once, twice, nested)]
        self.assertEqual([f["key"] for f in rows[1]["fields"]], ["Id", "Trade", "Trade"])
        self.assertEqual(len({r["fingerprint_sha256"] for r in rows}), 3)
        graph = go(files_of(db__item_db_yml=nested))[0]
        self.assertEqual(graph.visits[0]["duplicate_key_sites"]["count"], 1)

    def test_fingerprint_encoding_and_independence_from_positions(self):
        a = go(files_of(db__item_db_yml=H + body("  - Id: 1\n    N: yes\n")))[1][0]
        b = go(files_of(db__item_db_yml=H + "\n\n" + body("  -   Id: 1\n      N: yes\n")))[1][0]
        c = go(files_of(db__item_db_yml=H + body("  - Id: 1\n    N: 'yes'\n")))[1][0]
        self.assertEqual(a["fingerprint_sha256"], b["fingerprint_sha256"])
        self.assertNotEqual(a["span_sha256"], b["span_sha256"])
        self.assertNotEqual(a["fingerprint_sha256"], c["fingerprint_sha256"])
        expected = json.dumps({"k": "m", "c": [{"k": "s", "t": "Id", "y": 1},
                                               {"k": "s", "t": "1", "y": 1},
                                               {"k": "s", "t": "N", "y": 1},
                                               {"k": "s", "t": "yes", "y": 1}]},
                              sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        self.assertEqual(a["fingerprint_sha256"], sha(expected.encode()))
        self.assertEqual(a["node_count"], 5)

    def test_unicode_crlf_byte_spans(self):
        text = (H + body("  - Id: 7\n    Name: \"é漢字😀\"\n  - Id: 8\n")).replace("\n", "\r\n")
        data = text.encode("utf-8")
        graph, rows, status = go(files_of(db__item_db_yml=data))
        self.assertEqual(status, "complete")
        first = rows[0]
        start, end = first["byte_span"]
        self.assertEqual(start, data.index(b"Id: 7"))
        self.assertEqual(end, data.index(b"Id: 8") - 2)  # mapping ends at the next '- '
        self.assertEqual(first["span_sha256"], sha(data[start:end]))
        self.assertIn("\"é漢字😀\"\r\n".encode(), data[start:end])
        rid = rows[1]["raw_ids"][0]
        self.assertEqual(data[rid["byte_span"][0]:rid["byte_span"][1]], b"8")
        name = data.index("é".encode()) - 1
        self.assertEqual(first["fields"][1]["key"], "Name")
        self.assertGreater(name, start)

    def test_body_shapes_unsupported(self):
        for text, prefix in (("Body: x\n", 0), ("Body:\n  a: 1\n", 0),
                             ("Body:\n  - Id: 1\n  - x\n", 1), ("Body:\n", 0)):
            graph, rows, status = go(files_of(db__item_db_yml=H + text))
            self.assertEqual(status, "unsupported", text)
            self.assertEqual(len(rows), prefix)  # qualified prefix kept
            self.assertEqual(graph.stop["kind"], "unsupported_control_shape")

    def test_empty_flow_body(self):
        graph, rows, status = go(files_of(db__item_db_yml=H + "Body: []\n"))
        self.assertEqual((status, rows), ("complete", []))


class ImportTests(unittest.TestCase):
    """native: database.cpp:176-228, plus literal-path/cycle policy."""

    def test_mode_exact(self):
        files = files_of(
            db__item_db_yml=H + imports(edge("db/a.yml", "Renewal"), edge("db/b.yml", "renewal"),
                                        edge("db/c.yml", "Prerenewal"), edge("db/d.yml", "~"),
                                        edge("db/e.yml", ">-\n      null")),
            db__a_yml=H)
        graph, rows, status = go(files)
        self.assertEqual(status, "complete")
        self.assertEqual([(e["decision"], e.get("skip_reason")) for e in graph.edges],
                         [("load", None), ("skip", "mode_mismatch"), ("skip", "mode_mismatch"),
                          ("skip", "mode_null"), ("skip", "mode_mismatch")])
        self.assertEqual(graph.edges[4]["mode"]["style"], "folded")
        self.assertFalse(graph.edges[4]["mode"]["null"])
        self.assertEqual(sorted(graph.reads), ["db/a.yml", "db/item_db.yml"])

    def test_renewal_without_aspd_job_aspd(self):
        profile = dict(yg.PROFILE, renewal_aspd=False)
        entries = imports(edge("db/re/job_aspd.yml", "Prerenewal"),
                          edge("db/re/Job_Aspd.yml", "Prerenewal"),
                          edge("db/re/job_aspd.yml", "Renewal"),
                          edge("db/a.yml", "Renewal"))
        files = files_of(db__item_db_yml=H + entries, db__re__job_aspd_yml=H,
                         db__re__Job_Aspd_yml=H, db__a_yml=H)
        graph, _, status = go(files, profile=profile)
        self.assertEqual([e["decision"] for e in graph.edges], ["load", "skip", "skip", "load"])
        self.assertEqual(graph.edges[0]["compiled_mode"], "Prerenewal")
        self.assertEqual(graph.edges[1]["compiled_mode"], "Renewal")
        aspd = go(files)[0]  # stock profile keeps Renewal for job_aspd.yml
        self.assertEqual([e["decision"] for e in aspd.edges], ["skip", "skip", "load", "load"])
        pre = go(files, profile=dict(yg.PROFILE, renewal=False))[0]
        self.assertEqual([e["decision"] for e in pre.edges], ["load", "load", "skip", "skip"])

    def test_generator(self):
        entries = imports(edge("db/a.yml"), edge("db/b.yml", generator="true"),
                          edge("db/c.yml", generator="false"), edge("db/d.yml", generator="maybe"),
                          edge("db/e.yml", generator="~"))
        files = files_of(db__item_db_yml=H + entries, db__a_yml=H, db__b_yml=H, db__c_yml=H)
        graph, _, status = go(files)
        self.assertEqual(status, "complete")
        self.assertEqual([(e["decision"], e.get("skip_reason")) for e in graph.edges],
                         [("load", None), ("skip", "generator_not_enabled"),
                          ("skip", "generator_false"),
                          ("skip", "generator_unknown_boolean_text"),
                          ("skip", "generator_null")])
        self.assertEqual(graph.edges[0]["generator"], "absent")
        self.assertEqual(sorted(graph.reads), ["db/a.yml", "db/item_db.yml"])
        on = go(files, profile=dict(yg.PROFILE, should_load_generator=True))[0]
        self.assertEqual([e["decision"] for e in on.edges],
                         ["load", "load", "skip", "skip", "skip"])

    def test_generator_container_unsupported(self):
        files = files_of(db__item_db_yml=H + imports(edge("db/a.yml", generator="[true]")),
                         db__a_yml=H)
        graph, _, status = go(files)
        self.assertEqual(status, "unsupported")
        self.assertNotIn("db/a.yml", graph.reads)

    def test_path_missing_null_skip(self):
        files = files_of(db__item_db_yml=H + imports("  - Mode: Renewal\n", "  - {}\n",
                                                     "  - Path:\n", "  - Path: '~'\n"))
        graph, _, status = go(files)
        self.assertEqual([e.get("skip_reason") for e in graph.edges[:3]],
                         ["path_missing", "path_missing", "path_null"])
        self.assertEqual(graph.edges[3]["decision"], "load")  # quoted '~' is a path text
        self.assertEqual(status, "unsupported")  # '~' is not under a scope directory

    def test_repeated_imports_and_literal_root_paths(self):
        files = files_of(
            db__item_db_yml=H + imports(edge("db/re/x.yml"), edge("db/re/x.yml")),
            db__re__x_yml=H + body("  - Id: 9\n") + imports(edge("db/leaf.yml")),
            db__leaf_yml=H + body("  - Id: 10\n"),
            db__re__db__leaf_yml=H + body("  - Id: 99\n"))
        graph, rows, status = go(files)
        self.assertEqual(status, "complete")
        self.assertEqual([(r["visit"], r["raw_ids"][0]["text"]) for r in rows],
                         [(1, "9"), (2, "10"), (3, "9"), (4, "10")])
        self.assertEqual(graph.reads["db/re/x.yml"]["visits"], [1, 3])
        self.assertNotIn("db/re/db/leaf.yml", graph.reads)
        self.assertEqual([r["global_ordinal"] for r in rows], [0, 1, 2, 3])

    def test_known_failure_then_sibling(self):
        files = files_of(
            db__item_db_yml=H + imports(edge("db/missing.yml"), edge("db/bad.yml"),
                                        edge("db/ok.yml")),
            db__bad_yml="Header:\n  Type: MOB_DB\n  Version: 5\n" + body("  - Id: 1\n"),
            db__ok_yml=H + body("  - Id: 2\n"))
        graph, rows, status = go(files)
        self.assertEqual(status, "incomplete")
        self.assertEqual([r["raw_ids"][0]["text"] for r in rows], ["2"])
        self.assertEqual([v["status"] for v in graph.visits],
                         ["read_compatible", "known_failure_missing_file",
                          "known_failure_header", "read_compatible"])
        self.assertEqual([v["modeled_graph_return"] for v in graph.visits],
                         [True, False, False, True])
        self.assertEqual([e["child_return_ignored"] for e in graph.edges], [False, False, True])
        self.assertNotIn("db/missing.yml", graph.reads)
        self.assertEqual(graph.unresolved, [])

    def test_missing_root_then_next_root(self):
        files = files_of(db__mob_db_yml="Header:\n  Type: MOB_DB\n  Version: 5\n"
                         + body("  - Id: 1\n"))
        graph, rows, status = go(files, roots=TWO)
        self.assertEqual(status, "incomplete")
        self.assertEqual(len(rows), 1)
        self.assertEqual(graph.db["ITEM_DB"]["root_return"], False)

    def test_cycle_stops_with_unresolved_suffix(self):
        files = files_of(
            db__item_db_yml=H + imports(edge("db/a.yml"), edge("db/z.yml")),
            db__a_yml=H + body("  - Id: 1\n") + imports(edge("db/item_db.yml")),
            db__z_yml=H + body("  - Id: 2\n"),
            db__mob_db_yml="Header:\n  Type: MOB_DB\n  Version: 5\n")
        graph, rows, status = go(files, roots=TWO)
        self.assertEqual(status, "unsupported")
        self.assertEqual(graph.stop["kind"], "import_cycle")
        self.assertEqual([r["raw_ids"][0]["text"] for r in rows], ["1"])
        kinds = [u["kind"] for u in graph.unresolved]
        self.assertEqual(kinds, ["import_siblings_not_traversed", "root_not_started"])
        self.assertEqual(graph.unresolved[0]["from_edge"], 1)
        self.assertEqual(graph.visits[0]["traversal"],
                         "stopped by an unsupported state in its imports")
        self.assertIsNone(graph.visits[0]["modeled_graph_return"])
        self.assertNotIn("db/z.yml", graph.reads)

    def test_path_policy(self):
        for path in ("/etc/x.yml", "db/../db/a.yml", "db//a.yml", "./db/a.yml", "db\\a.yml",
                     "item_db.yml", "db/re", "db/é.yml", "'db/a.yml\\0'", '"db/a.yml\\0"'):
            files = files_of(db__item_db_yml=H + imports(edge(path)), db__re__a_yml=H)
            graph, _, status = go(files)
            self.assertEqual(status, "unsupported", path)
            self.assertEqual(graph.stop["kind"], "unsupported_path", path)

    def test_footer_shapes_unsupported(self):
        for text in ("Footer: x\n", "Footer:\n  Imports: x\n", "Footer:\n  Imports:\n    a: 1\n",
                     "Footer:\n  Imports:\n  - db/a.yml\n", "Footer:\n  Imports:\n  - Path: [a]\n"):
            graph, _, status = go(files_of(db__item_db_yml=H + text))
            self.assertEqual(status, "unsupported", text)

    def test_skipped_edge_shape_not_inspected(self):
        files = files_of(db__item_db_yml=H + imports("  - Path:\n    Mode: [x]\n"))
        self.assertEqual(go(files)[2], "complete")


class SyntaxPolicyTests(unittest.TestCase):
    """policy: constructs outside the bounded profile are unsupported, never native."""

    def refuse(self, data, kind):
        graph, rows, status = go(files_of(db__item_db_yml=data))
        self.assertEqual(status, "unsupported", data)
        self.assertEqual(graph.stop["kind"], kind, data)
        self.assertEqual(rows, [])
        self.assertEqual(graph.known_failures, [])
        return graph

    def test_constructs(self):
        base = H + body("  - Id: 1\n")
        self.refuse(base + "X: !tag 1\n", "unsupported_syntax")
        self.refuse(base + "X: &a 1\nY: *a\n", "unsupported_syntax")
        self.refuse(base + "X: {<<: {a: 1}}\n", "unsupported_syntax")
        self.refuse(base + "? [a]\n: 1\n", "unsupported_syntax")
        self.refuse(base + "---\nA: 1\n", "unsupported_syntax")
        self.refuse("%YAML 1.1\n---\n" + base, "unsupported_syntax")
        self.refuse("- a\n", "unsupported_syntax")
        self.refuse("", "unsupported_syntax")
        graph = self.refuse(base + "X: [\n", "parser_refusal")
        self.assertIn("problem", graph.stop["psych"])
        # quoted "<<" is an ordinary key
        self.assertEqual(go(files_of(db__item_db_yml=base + "'<<': 1\n"))[2], "complete")

    def test_bytes(self):
        base = (H + body("  - Id: 1\n")).encode()
        self.refuse(base + b"X: \x00\n", "unsupported_input")
        self.refuse(base + b"X: \xff\n", "unsupported_input")
        self.refuse(b"\xef\xbb\xbf" + base, "unsupported_input")
        self.refuse(base + b"X: 1\rY: 2\n", "unsupported_input")
        self.refuse(base + "X: a b\n".encode(), "unsupported_input")
        self.refuse(base + "X: a\u0085b\n".encode(), "unsupported_input")

    def test_marks_are_validated(self):
        lines = yg.LineIndex("ab\r\né\n".encode())
        self.assertEqual(lines.offset((0, 2)), 2)
        self.assertEqual(lines.offset((1, 1)), 6)
        self.assertEqual(lines.offset((2, 0)), 7)
        for mark in ((0, 3), (1, 2), (3, 0)):
            with self.assertRaises(yg.Stop):
                lines.offset(mark)


class LimitTests(unittest.TestCase):
    """policy: caps are unsupported states and charge the failed work."""

    def limited(self, data, **caps):
        limits = dict(yg.LIMITS, **caps)
        return go(files_of(db__item_db_yml=data), limits=limits)

    def test_work_caps(self):
        base = H + body("  - Id: 1\n    A: [[[1]]]\n  - Id: 2\n")
        for caps, name in (({"max_input_bytes": 10}, "max_input_bytes"),
                           ({"max_nodes_per_file": 5}, "max_nodes_per_file"),
                           ({"max_depth": 4}, "max_depth"),
                           ({"max_scalar_bytes": 3}, "max_scalar_bytes"),
                           ({"max_rows_total": 1}, "max_rows_total"),
                           ({"max_nodes_total": 10}, "max_nodes_total")):
            graph, rows, status = self.limited(base, **caps)
            self.assertEqual(status, "unsupported", name)
            self.assertEqual(graph.stop["kind"], "work_limit", name)
            self.assertEqual(graph.stop["detail"], name)
            self.assertEqual(graph.reads["db/item_db.yml"]["visits"], [0])
        graph, rows, _ = self.limited(base, max_rows_total=1)
        self.assertEqual(len(rows), 1)

    def test_graph_caps(self):
        chain = files_of(db__item_db_yml=H + imports(edge("db/a.yml"), edge("db/a.yml")),
                         db__a_yml=H + imports(edge("db/b.yml")), db__b_yml=H)
        for caps, name in (({"max_visits": 3}, "max_visits"), ({"max_edges": 2}, "max_edges"),
                           ({"max_import_depth": 1}, "max_import_depth")):
            graph, _, status = go(chain, limits=dict(yg.LIMITS, **caps))
            self.assertEqual((status, graph.stop["detail"]), ("unsupported", name))

    def test_subprocess_caps(self):
        limits = dict(yg.LIMITS, wall_seconds=1, cpu_seconds=20)
        code, _, _, failure = yg.run_child([], b"", limits, script="sleep 5")
        self.assertEqual(failure, "wall_timeout")
        limits = dict(yg.LIMITS, max_stdout_bytes=1000)
        _, _, _, failure = yg.run_child([], b"", limits, script="$stdout.write('x' * 5000)")
        self.assertEqual(failure, "stdout_cap")
        limits = dict(yg.LIMITS, max_stderr_bytes=100)
        _, _, _, failure = yg.run_child([], b"", limits, script="$stderr.write('x' * 5000)")
        self.assertEqual(failure, "stderr_cap")
        limits = dict(yg.LIMITS, cpu_seconds=1, wall_seconds=20)
        _, _, _, failure = yg.run_child([], b"", limits, script="loop { }")
        self.assertEqual(failure, "cpu_limit")
        big = b"x" * (1 << 20)
        code, out, _, failure = yg.run_child([], big, yg.LIMITS,
                                             script="$stdout.write($stdin.read.size.to_s)")
        self.assertEqual((code, out, failure), (0, b"1048576", None))

    def test_parser_failures_are_unsupported(self):
        with mock.patch.object(yg, "run_child", return_value=(0, b"{}", b"", None)):
            with self.assertRaises(yg.Stop) as caught:
                yg.parse_yaml(b"a: 1\n")
        self.assertEqual(caught.exception.record["kind"], "parser_failure")
        with mock.patch.object(yg, "run_child", return_value=(None, b"", b"", "wall_timeout")):
            graph, _, status = go(files_of(db__item_db_yml=H))
        self.assertEqual((status, graph.stop["kind"]), ("unsupported", "parser_limit"))

    def test_parser_identity(self):
        self.assertEqual(yg.check_parser(), yg.PARSER_PINS)
        with self.assertRaises(yg.InputError):
            yg.check_parser(ruby="/nonexistent/ruby")


class PublicationTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.chmod(self.tmp.name, 0o700)
        self.parent = Path(self.tmp.name)
        self.files = files_of(db__item_db_yml=H + body("  - Id: 1\n  - Id: 2\n"))
        self.provenance = {"generator": {"tool": "test"}}

    def tearDown(self):
        self.tmp.cleanup()

    def publish(self, name="out", files=None, **kw):
        return yg.publish(self.parent / name, files or self.files, self.provenance,
                          roots=ITEM, **kw)

    def test_complete_private_deterministic(self):
        target, manifest, hashes = self.publish("a")
        self.publish("b")
        self.assertEqual(manifest["status"], "complete")
        self.assertEqual(stat.S_IMODE(os.stat(target).st_mode), 0o700)
        names = sorted(os.listdir(target))
        self.assertEqual(names, [yg.OUTPUT_RECORDS, yg.OUTPUT_COMPLETE, yg.OUTPUT_MANIFEST])
        for name in names:
            self.assertEqual(stat.S_IMODE(os.stat(target / name).st_mode), 0o600)
            self.assertEqual((target / name).read_bytes(), (self.parent / "b" / name).read_bytes())
        records = (target / yg.OUTPUT_RECORDS).read_bytes()
        data = (target / yg.OUTPUT_MANIFEST).read_bytes()
        complete = json.loads((target / yg.OUTPUT_COMPLETE).read_bytes())
        self.assertEqual(complete["manifest_sha256"], sha(data))
        self.assertEqual(complete["records_sha256"], sha(records))
        self.assertEqual(json.loads(data)["records_file"]["sha256"], sha(records))
        self.assertEqual(len(records.splitlines()), 2)
        self.assertNotIn(str(self.parent).encode(), data + records)

    def test_incomplete_has_no_marker(self):
        files = files_of(db__item_db_yml=H + body("  - Id: 1\n  - x\n"))
        target, manifest, _ = self.publish("u", files)
        self.assertEqual(manifest["status"], "unsupported")
        self.assertEqual(sorted(os.listdir(target)), [yg.OUTPUT_RECORDS, yg.OUTPUT_MANIFEST])
        self.assertEqual(len((target / yg.OUTPUT_RECORDS).read_bytes().splitlines()), 1)

    def test_existing_and_link_targets_refused(self):
        (self.parent / "exists").mkdir()
        (self.parent / "file").write_bytes(b"x")
        os.symlink(self.parent / "exists", self.parent / "link")
        os.symlink(self.parent / "nowhere", self.parent / "dangling")
        for name in ("exists", "file", "link", "dangling"):
            with self.assertRaises(yg.OutputError):
                self.publish(name)
        self.assertFalse((self.parent / "nowhere").exists())
        self.assertEqual(os.listdir(self.parent / "exists"), [])
        shared = self.parent / "shared"
        shared.mkdir(mode=0o777)
        os.chmod(shared, 0o777)
        with self.assertRaises(yg.OutputError):
            yg.publish(shared / "out", self.files, self.provenance, roots=ITEM)

    def test_readback_tamper_fails_without_marker(self):
        real = yg._verify_published

        def tampering(dir_fd, name, size, digest, identity):
            if name == yg.OUTPUT_MANIFEST:
                with open(os.open(name, os.O_WRONLY | os.O_APPEND, dir_fd=dir_fd), "ab") as h:
                    h.write(b"x")
            return real(dir_fd, name, size, digest, identity)

        with mock.patch.object(yg, "_verify_published", tampering):
            with self.assertRaises(yg.OutputError):
                self.publish("t")
        self.assertNotIn(yg.OUTPUT_COMPLETE, os.listdir(self.parent / "t"))

    def test_failure_after_marker_removes_owned_marker(self):
        with mock.patch.object(yg.os, "listdir", side_effect=OSError("boom")):
            with self.assertRaises(yg.OutputError) as caught:
                self.publish("m")
        self.assertIn("partial output remains", str(caught.exception))
        self.assertEqual(sorted(os.listdir(self.parent / "m")),
                         [yg.OUTPUT_RECORDS, yg.OUTPUT_MANIFEST])

    def test_final_close_failure_removes_marker(self):
        real_close = os.close
        calls = {"n": 0}
        target = self.parent / "c"

        def failing_close(fd):
            is_directory = stat.S_ISDIR(os.fstat(fd).st_mode)
            real_close(fd)
            if (is_directory and calls["n"] == 0
                    and os.path.exists(target / yg.OUTPUT_COMPLETE)):
                calls["n"] += 1
                raise OSError("close failed")

        with mock.patch.object(yg.os, "close", failing_close):
            with self.assertRaises(yg.OutputError):
                self.publish("c")
        self.assertNotIn(yg.OUTPUT_COMPLETE, os.listdir(target))
        self.assertEqual(calls["n"], 1, "the actual output directory close was injected")

    def test_foreign_marker_replacement_preserved_and_reported(self):
        target = self.parent / "f"

        def replace_then_fail(fd):
            # Keep the owned inode allocated so replacement cannot reuse its inode.
            original = os.stat(yg.OUTPUT_COMPLETE, dir_fd=fd, follow_symlinks=False)
            os.rename(yg.OUTPUT_COMPLETE, "owned-marker-held", src_dir_fd=fd, dst_dir_fd=fd)
            with open(os.open(yg.OUTPUT_COMPLETE, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                              0o600, dir_fd=fd),
                      "wb") as h:
                h.write(b"foreign")
            replacement = os.stat(yg.OUTPUT_COMPLETE, dir_fd=fd, follow_symlinks=False)
            self.assertNotEqual((original.st_dev, original.st_ino),
                                (replacement.st_dev, replacement.st_ino))
            raise OSError("listing failed")

        with mock.patch.object(yg.os, "listdir", replace_then_fail):
            with self.assertRaises(yg.OutputError) as caught:
                self.publish("f")
        self.assertIn("could not remove", str(caught.exception))
        self.assertEqual((target / yg.OUTPUT_COMPLETE).read_bytes(), b"foreign")

    def test_cleanup_failure_reported(self):
        real_unlink = os.unlink

        def failing_unlink(name, *a, **kw):
            if name == yg.OUTPUT_COMPLETE:
                raise PermissionError("denied")
            return real_unlink(name, *a, **kw)

        with mock.patch.object(yg.os, "listdir", side_effect=OSError("boom")), \
                mock.patch.object(yg.os, "unlink", failing_unlink):
            with self.assertRaises(yg.OutputError) as caught:
                self.publish("x")
        self.assertIn("treat this output as failed", str(caught.exception))

    def test_write_failure_and_unexpected_errors(self):
        with mock.patch.object(yg, "render", side_effect=RuntimeError("bug")):
            with self.assertRaises(yg.OutputError) as caught:
                self.publish("w")
        self.assertIn("unexpected", str(caught.exception))
        self.assertNotIn(yg.OUTPUT_COMPLETE, os.listdir(self.parent / "w"))

    def test_record_file_cap(self):
        target, manifest, _ = self.publish("r", limits=dict(yg.LIMITS, max_record_file_bytes=10))
        self.assertEqual(manifest["status"], "unsupported")
        self.assertEqual(manifest["stop"]["detail"], "max_record_file_bytes")
        self.assertEqual(manifest["counts"]["raw_rows"], 0)
        self.assertEqual(manifest["counts"]["raw_id_occurrences"], 0)


class CoordinatorRegressionTests(unittest.TestCase):
    """Coordinator corrections: authored fixtures only, no snapshot/CLI dependency."""

    def test_full_raw_id_text_and_duplicates(self):
        text = "x" * 1025 + "繁體中文"
        graph, rows, status = go(files_of(db__item_db_yml=H + body(
            "  - Id: '" + text + "'\n    Id: \"" + text + "\"\n")))
        self.assertEqual(status, "complete")
        self.assertEqual([r["text"] for r in rows[0]["raw_ids"]], [text, text])
        self.assertTrue(all("text_truncated_from_chars" not in r
                            for r in rows[0]["raw_ids"]))
        self.assertEqual(graph.id_stats["ITEM_DB"]["occurrences"], 2)

    def test_leading_zero_versions_preserve_full_text(self):
        for quote in ("", "'", '"'):
            text = "0" * 1025 + "3"
            data = "Header:\n  Type: ITEM_DB\n  Version: " + quote + text + quote + "\n"
            graph, _, status = go(files_of(db__item_db_yml=data))
            self.assertEqual(status, "complete")
            record = graph.visits[0]["header"]["version"]
            self.assertEqual(record["text"], text)
            self.assertNotIn("text_truncated_from_chars", record)
            self.assertEqual(graph.visits[0]["header"]["version_value"], 3)
        graph, _, status = go(files_of(db__item_db_yml=H.replace("Version: 3", "Version: " + "0" * 200)))
        self.assertEqual(status, "incomplete")  # decimal zero is below the minimum, not unsupported
        self.assertEqual(graph.visits[0]["header"]["version_value"], 0)

    def test_long_version_range_and_nondecimal_refusals(self):
        for text in ("0" * 100 + "65536", "+3", "0x03", "0o3", "３"):
            graph, _, status = go(files_of(db__item_db_yml=H.replace("Version: 3", "Version: '" + text + "'")))
            self.assertEqual((status, graph.stop["kind"]),
                             ("unsupported", "unsupported_version_text"))

    def child_failure(self, setup, expected=yg.ChildFailure, script="sleep 30"):
        real_popen = subprocess.Popen
        children = []

        def spawn(*args, **kw):
            child = real_popen(*args, **kw)
            children.append(child)
            return child

        try:
            with mock.patch.object(yg.subprocess, "Popen", spawn), setup:
                with self.assertRaises(expected):
                    yg.run_child([], b"", yg.LIMITS, script=script)
            self.assertEqual(len(children), 1)
            self.assertIsNotNone(children[0].poll(), "owned child must be reaped")
            self.assertTrue(all(h.closed for h in (children[0].stdin, children[0].stdout,
                                                   children[0].stderr)))
        finally:
            # Test owns this child even if a proposed implementation regresses.
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=2)
                for handle in (child.stdin, child.stdout, child.stderr):
                    handle.close()

    def test_selector_construction_failure_reaps_child(self):
        self.child_failure(mock.patch.object(yg.selectors, "DefaultSelector",
                                              side_effect=OSError("selector setup")))

    def test_nonblocking_setup_failure_reaps_child(self):
        self.child_failure(mock.patch.object(yg.os, "set_blocking",
                                              side_effect=OSError("nonblocking setup")))

    def test_selector_registration_failure_reaps_child(self):
        selector = yg.selectors.DefaultSelector()
        with mock.patch.object(selector, "register", side_effect=RuntimeError("registration")):
            self.child_failure(mock.patch.object(yg.selectors, "DefaultSelector",
                                                  return_value=selector))
        self.assertIsNone(selector.get_map())

    def test_unexpected_io_failure_reaps_child(self):
        real_read = os.read

        def broken_read(fd, size):
            # Popen's own error-pipe read uses another size and must remain intact.
            if size == 1 << 16:
                raise OSError("read failed")
            return real_read(fd, size)

        self.child_failure(mock.patch.object(yg.os, "read", broken_read),
                           script="$stdout.write('x'); $stdout.flush; sleep 30")

    def test_selector_finalization_failure_still_reaps_child(self):
        selector = yg.selectors.DefaultSelector()
        close = selector.close

        def broken_close():
            close()
            raise OSError("selector close")

        # Force select to fail immediately, then also fail selector close.
        with mock.patch.object(selector, "select", side_effect=RuntimeError("select")), \
                mock.patch.object(selector, "close", broken_close):
            self.child_failure(mock.patch.object(yg.selectors, "DefaultSelector",
                                                  return_value=selector))

    def test_interrupt_after_spawn_cleans_up_and_propagates(self):
        self.child_failure(mock.patch.object(yg.selectors, "DefaultSelector",
                                              side_effect=KeyboardInterrupt()), KeyboardInterrupt)

    def test_malformed_protocol_stops_certain_suffix(self):
        packets = [b"[]", b"null", b'"text"',
                   json.dumps({**yg.PARSER_PINS, "outcome": "ok"}).encode(),
                   json.dumps({**yg.PARSER_PINS, "outcome": "ok", "nodes": [[[], 0, 0, 0, 0]]}).encode(),
                   json.dumps({**yg.PARSER_PINS, "outcome": "ok", "nodes": [
                       ["T", 0, 0, 0, 0, 1], ["S", 0, 0, 0, 0, "x", 1, None, None]]}).encode(),
                   json.dumps({**yg.PARSER_PINS, "outcome": "budget", "budget": "max_depth"}).encode()]
        for packet in packets:
            with self.subTest(packet=packet[:100]), \
                    mock.patch.object(yg, "run_child", return_value=(0, packet, b"", None)):
                graph, rows, status = go(files_of(db__item_db_yml=H), roots=TWO)
            self.assertEqual((status, graph.stop["kind"]), ("unsupported", "parser_failure"))
            self.assertEqual(rows, [])
            self.assertEqual(len(graph.visits), 1)
            self.assertEqual(graph.unresolved[0]["kind"], "root_not_started")
            self.assertEqual(graph.usage["adapter_stdout_bytes"], len(packet))
            self.assertEqual(graph.usage["unknown_node_count_attempts"], 1)
            self.assertIsNone(yg.build_manifest(graph, {}, {})["counts"]["ast_nodes"])

    def test_malformed_node_metadata_is_qualified_stop(self):
        _, out, _, failure = yg.run_child(["1000", "64"], H.encode(), yg.LIMITS)
        self.assertIsNone(failure)
        original = json.loads(out)
        for kind, index, value in (("S", 6, 99), ("S", 7, []), ("M", 6, []),
                                    ("D", 8, "true")):
            packet = json.loads(out)
            next(n for n in packet["nodes"] if n[0] == kind)[index] = value
            with mock.patch.object(yg, "run_child", return_value=(0, json.dumps(packet).encode(), b"", None)):
                graph, _, status = go(files_of(db__item_db_yml=H))
            self.assertEqual((status, graph.stop["kind"]), ("unsupported", "parser_failure"))
        self.assertEqual(original["outcome"], "ok")

    def test_malformed_nesting_after_valid_document_is_qualified_stop(self):
        _, out, _, _ = yg.run_child(["1000", "64"], H.encode(), yg.LIMITS)
        for kind, index, value in (("M", 5, 1), ("D", 5, 0)):
            packet = json.loads(out)
            next(n for n in packet["nodes"] if n[0] == kind)[index] = value
            with mock.patch.object(yg, "run_child", return_value=(0, json.dumps(packet).encode(), b"", None)):
                graph, _, status = go(files_of(db__item_db_yml=H))
            self.assertEqual((status, graph.stop["kind"]), ("unsupported", "parser_failure"))

    def test_scalar_refusal_accounts_full_validated_ast_and_bytes(self):
        files = files_of(db__item_db_yml=H + body("  - Id: 12345\n"))
        normal, _, _ = go(files)
        graph, rows, status = go(files, limits=dict(yg.LIMITS, max_scalar_bytes=3))
        self.assertEqual((status, graph.stop["detail"]), ("unsupported", "max_scalar_bytes"))
        self.assertEqual(rows, [])
        self.assertEqual(graph.usage["nodes"], normal.usage["nodes"])
        self.assertGreater(graph.usage["nodes"], 0)
        self.assertGreater(graph.usage["adapter_stdout_bytes"], 0)
        self.assertEqual(graph.usage["unknown_node_count_attempts"], 0)
        self.assertEqual(graph.stop["adapter"]["node_total"], normal.usage["nodes"])

    def test_node_depth_and_syntax_refusals_have_unknown_totals(self):
        data = H + body("  - Id: 1\n    A: [[[1]]]\n")
        for caps in ({"max_nodes_per_file": 5}, {"max_depth": 3}):
            graph, _, status = go(files_of(db__item_db_yml=data), limits=dict(yg.LIMITS, **caps))
            self.assertEqual(status, "unsupported")
            self.assertGreater(graph.usage["nodes"], 0)
            self.assertGreater(graph.usage["adapter_stdout_bytes"], 0)
            self.assertEqual(graph.usage["unknown_node_count_attempts"], 1)
            self.assertIsNone(graph.visits[0]["parser_attempt"]["node_total"])
        graph, _, _ = go(files_of(db__item_db_yml="Body: [\n"))
        self.assertEqual(graph.stop["kind"], "parser_refusal")
        self.assertGreater(graph.usage["adapter_stdout_bytes"], 0)
        self.assertEqual(graph.usage["unknown_node_count_attempts"], 1)

    def test_cap_crossing_capture_distinguishes_observed_bytes(self):
        stats = {}
        _, out, _, failure = yg.run_child([], b"", dict(yg.LIMITS, max_stdout_bytes=10),
                                          script="$stdout.write('x' * 100)", stats=stats)
        self.assertEqual((failure, len(out)), ("stdout_cap", 10))
        self.assertGreater(stats["stdout_observed_bytes"], len(out))
        self.assertFalse(stats["stdout_complete"])

    def test_setup_error_becomes_accounted_parser_stop(self):
        with mock.patch.object(yg.selectors, "DefaultSelector", side_effect=OSError("setup")):
            graph, _, status = go(files_of(db__item_db_yml=H))
        self.assertEqual((status, graph.stop["kind"]), ("unsupported", "parser_failure"))
        self.assertEqual(graph.usage["parser_attempts"], 1)
        self.assertEqual(graph.usage["unknown_node_count_attempts"], 1)
        self.assertIn("adapter", graph.stop)

    def test_failed_input_bytes_and_emitted_row_statistics(self):
        data = H + body("  - Id: 1\n")
        graph, _, _ = go(files_of(db__item_db_yml=data), limits=dict(yg.LIMITS, max_input_bytes=10))
        self.assertEqual(graph.usage["input_bytes_examined"], len(data.encode()))
        self.assertEqual(graph.usage["input_bytes_parsed"], len(data.encode()))
        self.assertEqual(graph.usage["parser_attempts"], 1)

        def refuse(_row):
            raise yg.Stop("work_limit", "authored writer refusal")

        graph = yg.catalog(files_of(db__item_db_yml=data), refuse, ITEM)
        self.assertEqual(graph.rows, 0)
        self.assertEqual(graph.id_stats, {})


class CliTests(unittest.TestCase):

    def test_input_refusal_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.chmod(tmp, 0o700)
            empty = Path(tmp) / "snap"
            empty.mkdir()
            result = subprocess.run([sys.executable, "-I", str(TOOL), str(empty),
                                     str(Path(tmp) / "out")], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("error [input]", result.stderr)
            self.assertFalse((Path(tmp) / "out").exists())
            result = subprocess.run([sys.executable, "-I", str(TOOL), str(empty), str(empty)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)

    def test_cli_has_no_bypass_options(self):
        result = subprocess.run([sys.executable, "-I", str(TOOL), "--help"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        options = [w for w in result.stdout.split() if w.startswith("--")]
        self.assertEqual(options, ["--help"])


SNAPSHOT = os.environ.get("T06_YAML_SNAPSHOT", "")


@unittest.skipUnless(SNAPSHOT and os.path.isabs(SNAPSHOT) and os.path.isdir(SNAPSHOT),
                     "set T06_YAML_SNAPSHOT to the absolute canonical snapshot path")
class ActualInputTests(unittest.TestCase):

    def test_actual_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.chmod(tmp, 0o700)
            target, manifest, hashes = yg.run(SNAPSHOT, Path(tmp) / "out")
            self.assertEqual(manifest["status"], "complete")
            self.assertEqual(manifest["input"]["files"], 1683)
            self.assertEqual(manifest["input"]["bytes"], 68752782)
            counts = manifest["counts"]
            self.assertEqual(counts["unresolved"], 0)
            self.assertEqual(counts["known_failures"], 0)
            self.assertEqual(counts["raw_rows"], sum(d["raw_rows"]
                                                     for d in manifest["databases"].values()))
            self.assertEqual(counts["edges_skipped"], counts["skip_reasons"]["mode_mismatch"])
            rows = (target / yg.OUTPUT_RECORDS).read_bytes().splitlines()
            self.assertEqual(len(rows), counts["raw_rows"])
            self.assertEqual([json.loads(r)["global_ordinal"] for r in rows],
                             list(range(len(rows))))
            order = [v["database"] for v in manifest["visits"]]
            self.assertEqual(order, sorted(order, key=["ITEM_DB", "SKILL_DB", "MOB_DB",
                                                        "QUEST_DB"].index))
            # Every row span starts at its first key and hashes to the snapshot bytes.
            reads = {r["path"]: r for r in manifest["exact_reads"]}
            snapshot = Path(SNAPSHOT) / "rathena"
            data = {p: (snapshot / p).read_bytes() for p in reads}
            for line in rows:
                row = json.loads(line)
                blob = data[row["file"]]
                start, end = row["byte_span"]
                self.assertEqual(sha(blob[start:end]), row["span_sha256"])
                self.assertTrue(blob[start:end].startswith(row["fields"][0]["key"].encode()))
                for rid in row["raw_ids"]:
                    s, e = rid["byte_span"]
                    self.assertEqual(blob[s:e].decode(), rid["text"])


if __name__ == "__main__":
    unittest.main()
