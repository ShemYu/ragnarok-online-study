"""Tests for monster_projection. Run: python3 -I -m unittest discover -s tools/renewal

Fixtures are small authored YAML strings. Their raw catalogs are produced by the
unchanged selected yaml_graph_inventory (real pinned /usr/bin/ruby Psych adapter)
and then projected; no stock file is copied. Tests named "native" check the
mob.cpp/database.cpp prefix rules; "policy" tests check projection gaps and
refusals, which are never native results. Publication tests write temporary
private directories only.

The actual-input test reads the canonical snapshot and raw catalog from the
absolute paths in $T06_MONSTER_SNAPSHOT and $T06_MONSTER_RAW_CATALOG and is
skipped when either is unset or absent. CLI pins, profile and parser cannot be
bypassed.
"""

import hashlib
import errno
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
import monster_projection as mp  # noqa: E402

TOOL = Path(__file__).resolve().with_name("monster_projection.py")
yg, _TOOLS = mp.selected()
VERSIONS = yg.check_parser()
PARSER = mp.expected_parser(yg, VERSIONS)
ITEM = {"database": "ITEM_DB", "path": "db/item_db.yml", "version": 3, "minimum_version": 1}
MOB = {"database": "MOB_DB", "path": "db/mob_db.yml", "version": 5, "minimum_version": 1}
ROOTS = (ITEM, MOB)
PROFILE = dict(yg.PROFILE, name="fixture-item-mob", roots=[dict(r) for r in ROOTS])
FRESH = {"snapshot_manifest_sha256": "f" * 64, "files": 0, "bytes": 0,
         "verification": {"reader": "fixture", "reader_sha256": "e" * 64}}
MH = "Header:\n  Type: MOB_DB\n  Version: 5\n"
IH = "Header:\n  Type: ITEM_DB\n  Version: 3\n"
BASE = "    AegisName: A\n    Name: N\n"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def files_of(mob_body="", item="", extra=None, mob_header=MH):
    files = {"rathena/db/item_db.yml": (IH + "Body:\n  - Id: 501\n" + item).encode("utf-8"),
             "rathena/db/mob_db.yml": (mob_header + mob_body).encode("utf-8")}
    for path, text in (extra or {}).items():
        files["rathena/" + path] = text if isinstance(text, bytes) else text.encode("utf-8")
    return files


def rows(*texts):
    return "Body:\n" + "".join(texts)


class Fixture:
    """A real selected raw catalog over fixture files plus its exact pins."""

    def __init__(self, tmp, files, name="cat"):
        self.tmp, self.files = Path(tmp), files
        self.fresh = dict(FRESH, files=len(files), bytes=sum(len(b) for b in files.values()))
        self.dir = self.tmp / name
        provenance = {"generator": dict(mp.SELECTED_GENERATOR), "input": self.fresh,
                      "parser": PARSER}
        _t, self.catalog_manifest, _h = yg.publish(self.dir, files, provenance, roots=ROOTS,
                                                   profile=PROFILE)
        self.pins = self.pin()

    def pin(self):
        out = {}
        for key, name in (("manifest", "yaml-graph-manifest.json"),
                          ("complete", "yaml-graph-complete.json"),
                          ("records", "raw-declarations.jsonl")):
            data = (self.dir / name).read_bytes()
            out[key] = {"name": name, "bytes": len(data), "sha256": sha(data)}
        out["records"]["lines"] = (self.dir / "raw-declarations.jsonl").read_bytes().count(b"\n")
        return out

    def lines(self):
        return (self.dir / "raw-declarations.jsonl").read_bytes().splitlines(keepends=True)

    def rewrite(self, lines=None, manifest=None, complete=None, relink=True):
        """Tamper while (optionally) keeping hashes/relationships consistent, then re-pin."""
        os.chmod(self.dir, 0o700)
        rec = self.dir / "raw-declarations.jsonl"
        if lines is not None:
            rec.write_bytes(b"".join(lines))
        data = rec.read_bytes()
        man = json.loads((self.dir / "yaml-graph-manifest.json").read_text())
        if relink:
            man["records_file"].update(bytes=len(data), lines=data.count(b"\n"),
                                       sha256=sha(data))
        if manifest:
            manifest(man)
        man_bytes = mp.render(man)
        (self.dir / "yaml-graph-manifest.json").write_bytes(man_bytes)
        comp = json.loads((self.dir / "yaml-graph-complete.json").read_text())
        if relink:
            comp.update(manifest_sha256=sha(man_bytes), records_sha256=sha(data))
        if complete:
            complete(comp)
        (self.dir / "yaml-graph-complete.json").write_bytes(mp.render(comp))
        self.pins = self.pin()

    def project(self, name="out", **kw):
        kw.setdefault("pins", self.pins)
        kw.setdefault("expected", None)
        kw.setdefault("file_pins", None)
        kw.setdefault("profile", PROFILE)
        return mp.execute(self.files, self.fresh, self.dir, self.tmp / name, **kw)


def records(target, name=mp.OUTPUT_DECLARATIONS):
    return [json.loads(line) for line in (Path(target) / name).read_bytes().splitlines()]


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        os.chmod(self.tmp, 0o700)

    def tearDown(self):
        for root, dirs, _files in os.walk(self.tmp):
            for d in dirs:
                try:
                    os.chmod(os.path.join(root, d), 0o700)
                except OSError:
                    pass
        self._tmp.cleanup()

    def run_fixture(self, mob_body, **kw):
        fx = Fixture(self.tmp, files_of(mob_body, **kw))
        target, manifest, hashes = fx.project()
        return fx, target, manifest, records(target)

    @staticmethod
    def field(record, name):
        return record["fields"][mp.FIELDS.index(name)]

    @staticmethod
    def op(record, branch, field):
        return next(o for o in record["branches"][branch]["operations"]
                    if o.get("field") == field)


class DecimalPolicyTests(unittest.TestCase):
    """policy: bounded ASCII decimal subset; everything else is a gap, never native."""

    def test_widths_zero_and_leading_zero(self):
        u16, u32, u64 = mp.NUMERIC["Level"][1], mp.NUMERIC["Id"][1], mp.NUMERIC["BaseExp"][1]
        self.assertEqual(mp.decimal_value("65535", u16), (65535, None))
        self.assertEqual(mp.decimal_value("65536", u16), (None, "decimal_overflow"))
        self.assertEqual(mp.decimal_value("4294967295", u32), (4294967295, None))
        self.assertEqual(mp.decimal_value("4294967296", u32), (None, "decimal_overflow"))
        self.assertEqual(mp.decimal_value("18446744073709551615", u64), (2 ** 64 - 1, None))
        self.assertEqual(mp.decimal_value("18446744073709551616", u64),
                         (None, "decimal_overflow"))
        self.assertEqual(mp.decimal_value("0", u16), (0, None))
        self.assertEqual(mp.decimal_value("0" * 5000, u16), (0, None))
        self.assertEqual(mp.decimal_value("0" * 4000 + "65535", u16), (65535, None))
        self.assertEqual(mp.decimal_value("010", u32), (10, None))

    def test_unbounded_text_is_never_converted(self):
        with mock.patch("builtins.int", side_effect=AssertionError("int called")):
            self.assertEqual(mp.decimal_value("9" * 100000, "65535"), (None, "decimal_overflow"))

    def test_gap_reasons(self):
        cases = {"": "empty_text", " 1": "whitespace", "1 ": "whitespace", "1\n": "whitespace",
                 "1 2": "whitespace", "+1": "sign", "-1": "sign", "0x10": "base_prefix",
                 "0b1": "base_prefix", "0o7": "base_prefix", "١٢": "non_ascii_digit",
                 "²": "non_ascii_digit", "１": "non_ascii_digit", "1.0": "other_text",
                 "1e3": "other_text", "true": "other_text"}
        for text, reason in cases.items():
            self.assertEqual(mp.decimal_value(text, "4294967295"), (None, reason), text)


class NameByteTests(unittest.TestCase):
    """native: resize(NAME_LENGTH) of the UTF-8 bytes, NUL padding, no clip at 23."""

    def test_lengths(self):
        empty = mp.name_bytes("")
        self.assertEqual(empty["stored_bytes_hex"], "00" * 24)
        self.assertEqual((empty["utf8_length"], empty["truncated"]), (0, False))
        short = mp.name_bytes("Poring")
        self.assertEqual(short["stored_bytes_hex"], b"Poring".hex() + "00" * 18)
        exact = mp.name_bytes("x" * 24)
        self.assertEqual(exact["stored_bytes_hex"], b"x".hex() * 24)
        self.assertEqual((exact["truncated"], exact["warning"], exact["nul_padding_bytes"]),
                         (False, False, 0))
        over = mp.name_bytes("y" * 25)
        self.assertEqual(over["stored_bytes_hex"], b"y".hex() * 24)
        self.assertEqual((over["utf8_length"], over["truncated"], over["warning"]),
                         (25, True, True))

    def test_multibyte_split_and_no_normalization(self):
        split = mp.name_bytes("a" * 23 + "é")
        self.assertEqual(split["stored_bytes_hex"], b"a".hex() * 23 + "c3")
        self.assertTrue(split["multibyte_split_at_limit"])
        composed, decomposed = mp.name_bytes("é"), mp.name_bytes("é")
        self.assertEqual(composed["stored_bytes_hex"][:4], "c3a9")
        self.assertEqual(decomposed["stored_bytes_hex"][:6], "65cc81")
        self.assertNotEqual(composed["utf8_length"], decomposed["utf8_length"])
        nul = mp.name_bytes("a\0b")
        self.assertEqual(nul["stored_bytes_hex"], "610062" + "00" * 21)
        self.assertTrue(nul["embedded_nul_in_text"])
        self.assertIsNone(mp.name_bytes("\ud800"))


class IdGateTests(Base):
    """native: mob.cpp:5025-5031 strict ranges, asUInt32 null/missing return 0."""

    def test_boundaries(self):
        ids = (1000, 1001, 3998, 3999, 20020, 20021, 31998, 31999)
        _fx, _t, manifest, recs = self.run_fixture(rows(*(f"  - Id: {i}\n" + BASE
                                                          for i in ids)))
        outcomes = [r["id_stage"]["outcome"] for r in recs]
        self.assertEqual(outcomes, ["known_range_failure", "gate_passed", "gate_passed",
                                    "known_range_failure", "known_range_failure",
                                    "gate_passed", "gate_passed", "known_range_failure"])
        failed = recs[0]
        for branch in failed["branches"].values():
            self.assertEqual(branch["outcome"], "not_reached_id_stage")
            self.assertTrue(all(o["reachability"] == "not_reached_id_stage"
                                for o in branch["operations"]))
            self.assertNotIn("writes_before_later_parser", branch)
        history = records(_t, mp.OUTPUT_HISTORY)
        self.assertEqual([h["id"] for h in history], sorted(ids))
        self.assertEqual({h["id"]: h["source_gate"] for h in history}[3999], "out_of_range")
        self.assertEqual(manifest["status"], "complete")

    def test_missing_null_and_unsupported(self):
        body = rows("  - AegisName: A\n    Name: N\n", "  - Id: ~\n" + BASE,
                    "  - Id: '0x3E9'\n" + BASE, "  - Id: [1001]\n" + BASE,
                    "  - id: 1001\n" + BASE, "  - Id: \"null\"\n" + BASE)
        _fx, target, manifest, recs = self.run_fixture(body)
        stages = [(r["id_stage"]["outcome"], r["projection_status"]) for r in recs]
        self.assertEqual(stages, [("known_return0", "modelled"), ("known_return0", "modelled"),
                                  ("unresolved", "gap"), ("unresolved", "gap"),
                                  ("known_return0", "modelled"), ("unresolved", "gap")])
        self.assertEqual(recs[2]["id_stage"]["reason"], "projection_policy_gap:base_prefix")
        self.assertEqual(recs[3]["id_stage"]["reason"], "selected_container_extraction_gap")
        self.assertEqual(self.field(recs[4], "Id")["case_variant_keys"],
                         [{"field_ordinal": 0, "key_text": "id"}])
        self.assertFalse(self.field(recs[4], "Id")["present"])
        self.assertEqual(records(target, mp.OUTPUT_HISTORY), [])
        self.assertEqual(manifest["status"], "qualified")
        self.assertFalse((target / mp.OUTPUT_COMPLETE).exists())
        self.assertEqual(manifest["counts"]["id_stage_outcomes"],
                         {"known_return0": 3, "unresolved": 3})

    def test_quoted_and_leading_zero_ids_keep_full_text(self):
        _fx, target, _m, recs = self.run_fixture(rows("  - Id: '0001001'\n" + BASE,
                                                      "  - Id: \"00000000001002\"\n" + BASE))
        self.assertEqual([r["id_stage"]["id"] for r in recs], [1001, 1002])
        occ = self.field(recs[0], "Id")["occurrences"][0]["value"]
        self.assertEqual((occ["text"], occ["style"]), ("0001001", "single_quoted"))
        self.assertEqual(records(target, mp.OUTPUT_HISTORY)[0]["declarations"][0]["id_text"],
                         "0001001")


class FieldOccurrenceTests(Base):
    """native lookup: first exact key (find_child); later duplicates are history only."""

    def test_duplicates_first_lookup(self):
        body = rows("  - Id: 1001\n    Id: abc\n" + BASE + "    Level: 3\n    Level: [x]\n",
                    "  - Id: abc\n    Id: 1002\n" + BASE,
                    "  - Id: 1003\n    AegisName: A\n    Name: First\n    Name: ~\n")
        _fx, _t, manifest, recs = self.run_fixture(body)
        self.assertEqual(recs[0]["projection_status"], "modelled")
        ident = self.field(recs[0], "Id")
        self.assertEqual([o["role"] for o in ident["occurrences"]],
                         ["selected_first", "ignored_duplicate"])
        self.assertEqual(ident["occurrences"][1]["value"]["text"], "abc")
        level = self.field(recs[0], "Level")
        self.assertEqual((level["occurrence_count"], level["ignored_duplicates"]), (2, 1))
        self.assertEqual(level["occurrences"][1]["value"]["kind"], "sequence")
        self.assertIn("fingerprint_sha256", level["occurrences"][1]["value"])
        self.assertEqual(self.op(recs[0], "if_fresh", "Level")["effect"]["assigned_value"], 3)
        self.assertEqual(recs[1]["id_stage"]["outcome"], "unresolved")  # not rescued
        self.assertEqual(self.op(recs[2], "if_fresh", "Name")["effect"]["stored_bytes_hex"],
                         b"First".hex() + "00" * 19)
        self.assertEqual(manifest["counts"]["fields"]["Level"]["rows_with_ignored_duplicates"],
                         1)

    def test_all_ten_histories_and_fixed_parser_order(self):
        body = rows("  - MvpExp: 9\n    JobExp: 8\n    BaseExp: 7\n    Sp: 6\n    Hp: 5\n"
                    "    Level: 4\n    JapaneseName: J\n    Name: N\n    AegisName: A\n"
                    "    Id: 1001\n    Attack: 1\n")
        _fx, _t, _m, recs = self.run_fixture(body)
        rec = recs[0]
        self.assertEqual([f["field"] for f in rec["fields"]], list(mp.FIELDS))
        self.assertEqual([f["occurrences"][0]["field_ordinal"] for f in rec["fields"]],
                         list(range(9, -1, -1)))
        ops = [o.get("field") for o in rec["branches"]["if_fresh"]["operations"]]
        self.assertEqual(ops, [None, None] + list(mp.FIELDS[1:]) + [None, None])
        self.assertEqual([o["op"] for o in rec["branches"]["if_fresh"]["operations"]][-2:],
                         ["later_parser", "put"])

    def test_scalar_forms_and_containers(self):
        body = rows("  - Id: 1001\n" + BASE + "    Hp: |-\n      12\n    Sp: \"0007\"\n",
                    "  - Id: 1002\n" + BASE + "    Hp: |\n      12\n",
                    "  - Id: 1003\n" + BASE + "    Level: {a: 1}\n",
                    "  - Id: 1004\n    AegisName: \"null\"\n    Name: ''\n    Level:\n",
                    "  - Id: 1005\n" + BASE + "    Level: ''\n")
        _fx, _t, manifest, recs = self.run_fixture(body)
        self.assertEqual(self.op(recs[0], "if_existing", "Hp")["effect"]["assigned_value"], 12)
        self.assertEqual(self.op(recs[0], "if_existing", "Sp")["effect"]["assigned_value"], 7)
        self.assertEqual(self.field(recs[0], "Sp")["occurrences"][0]["value"]["text"], "0007")
        self.assertEqual(self.field(recs[1], "Hp")["selected"]["reason"], "whitespace")
        self.assertEqual(recs[1]["branches"]["if_fresh"]["outcome"], "unresolved_projection_gap")
        self.assertEqual(self.field(recs[2], "Level")["selected"],
                         {"status": "container", "kind": "mapping"})
        # Quoted "null" is text; plain '' (null) Level returns 0 after earlier name writes.
        self.assertEqual(self.op(recs[3], "if_fresh", "AegisName")["effect"]["stored_bytes_hex"],
                         b"null".hex() + "00" * 20)
        self.assertEqual(self.field(recs[3], "Name")["selected"]["status"], "supported")
        self.assertEqual(self.field(recs[3], "Name")["selected"]["utf8_length"], 0)
        self.assertEqual(self.field(recs[3], "Level")["selected"]["status"], "null")
        self.assertEqual(recs[3]["branches"]["if_existing"]["outcome"], "known_prefix_return0")
        self.assertEqual(self.field(recs[4], "Level")["selected"]["reason"], "empty_text")
        self.assertEqual(manifest["status"], "qualified")

    def test_unicode_crlf_spans_and_escaped_nul(self):
        text = (MH + "Body:\n  - Id: 1001\n    AegisName: \"A\\0B\"\n    Name: ポリ\n"
                "    Level: 1\n").replace("\n", "\r\n")
        fx = Fixture(self.tmp, dict(files_of(), **{"rathena/db/mob_db.yml":
                                                   text.encode("utf-8")}))
        target, _m, _h = fx.project()
        rec = records(target)[0]
        data = fx.files["rathena/db/mob_db.yml"]
        name = self.field(rec, "Name")["occurrences"][0]
        begin, end = name["value"]["byte_span"]
        self.assertEqual(data[begin:end], "ポリ".encode("utf-8"))
        self.assertEqual(name["value"]["span_sha256"], sha(data[begin:end]))
        kb, ke = name["key"]["byte_span"]
        self.assertEqual(data[kb:ke], b"Name")
        self.assertEqual(self.field(rec, "Name")["selected"]["stored_bytes_hex"],
                         "ポリ".encode("utf-8").hex() + "00" * 18)
        aegis = self.field(rec, "AegisName")
        self.assertEqual(aegis["occurrences"][0]["value"]["text"], "A\0B")
        self.assertEqual(aegis["selected"]["stored_bytes_hex"], "410042" + "00" * 21)
        rb, re_ = rec["raw_declaration"]["byte_span"]
        self.assertEqual(rec["raw_declaration"]["span_sha256"], sha(data[rb:re_]))


class BranchTests(Base):
    """native: fixed operation order, fresh/existing conditional prefixes (mob.cpp:5033-5141)."""

    def test_fresh_mandatory_before_any_write_existing_not_required(self):
        _fx, _t, _m, recs = self.run_fixture(rows("  - Id: 1001\n    Name: N\n    Level: 2\n"))
        fresh, existing = recs[0]["branches"]["if_fresh"], recs[0]["branches"]["if_existing"]
        self.assertEqual(fresh["outcome"], "known_prefix_return0")
        self.assertEqual(fresh["operations"][0]["missing"], ["AegisName"])
        self.assertEqual(fresh["insertion"], "not_reached_no_object_constructed")
        self.assertEqual(fresh["later_parser"], "later_parser_not_reached")
        self.assertTrue(all(o["reachability"] == "not_reached_after_return0"
                            for o in fresh["operations"][1:]))
        self.assertNotIn("effect", fresh["operations"][3])
        self.assertEqual(existing["outcome"], "prefix_modelled")
        self.assertEqual(self.op(recs[0], "if_existing", "AegisName")["effect"],
                         {"target": "sprite", "prior_value_retained": True})
        self.assertEqual(recs[0]["projection_status"], "modelled")

    def test_presence_does_not_imply_conversion(self):
        _fx, _t, _m, recs = self.run_fixture(rows("  - Id: 1001\n    AegisName: ~\n    Name: N\n"))
        fresh = recs[0]["branches"]["if_fresh"]
        self.assertEqual(fresh["operations"][0]["result"], "present")
        self.assertEqual(fresh["stop"]["field"], "AegisName")
        self.assertEqual(fresh["insertion"], "not_reached_temporary_object_discarded")

    def test_japanese_name_copy_versus_retention(self):
        _fx, _t, _m, recs = self.run_fixture(rows("  - Id: 1001\n    AegisName: A\n"
                                                  "    Name: Changed\n"))
        copy = self.op(recs[0], "if_fresh", "JapaneseName")
        self.assertEqual(copy["op"], "copy_name_to_jname")
        self.assertEqual(copy["effect"]["stored_bytes_hex"], b"Changed".hex() + "00" * 17)
        keep = self.op(recs[0], "if_existing", "JapaneseName")
        self.assertEqual(keep["effect"], {"target": "jname", "prior_value_retained": True})

    def test_earlier_existing_writes_survive_later_null_and_gap(self):
        body = rows("  - Id: 1001\n" + BASE + "    Level: 5\n    Hp: ~\n    Sp: 3\n",
                    "  - Id: 1002\n" + BASE + "    Level: 5\n    Hp: -1\n    Sp: 3\n")
        _fx, _t, manifest, recs = self.run_fixture(body)
        existing = recs[0]["branches"]["if_existing"]
        self.assertEqual(existing["outcome"], "known_prefix_return0")
        self.assertEqual([w["field"] for w in existing["earlier_writes_survive"]],
                         ["AegisName", "Name", "Level"])
        self.assertEqual(self.op(recs[0], "if_existing", "Sp")["reachability"],
                         "not_reached_after_return0")
        self.assertEqual(recs[0]["branches"]["if_fresh"]["insertion"],
                         "not_reached_temporary_object_discarded")
        self.assertEqual(recs[0]["projection_status"], "modelled")
        gap = recs[1]["branches"]["if_existing"]
        self.assertEqual(gap["outcome"], "unresolved_projection_gap")
        self.assertEqual(gap["stop"]["reason"], "projection_policy_gap:sign")
        self.assertEqual([w["field"] for w in gap["earlier_writes_survive"]],
                         ["AegisName", "Name", "Level"])
        self.assertEqual(self.op(recs[1], "if_existing", "Sp")["reachability"],
                         "unresolved_after_gap")
        self.assertEqual(recs[1]["branches"]["if_fresh"]["insertion"], "unresolved")
        self.assertEqual(manifest["status"], "qualified")
        self.assertEqual(len(recs[1]["projection_gaps"]), 2)

    def test_absent_default_retain_zero_and_exp(self):
        body = rows("  - Id: 1001\n" + BASE + "    Hp: 0\n    BaseExp: 18446744073709551615\n")
        _fx, _t, _m, recs = self.run_fixture(body)
        rec = recs[0]
        self.assertEqual(self.op(rec, "if_fresh", "Hp")["effect"]["assigned_value"], 0)
        self.assertEqual(self.op(rec, "if_fresh", "Level")["effect"],
                         {"target": "lv", "constructor_value_retained": 1})
        self.assertEqual(self.op(rec, "if_existing", "Level")["effect"],
                         {"target": "lv", "prior_value_retained": True})
        self.assertEqual(self.op(rec, "if_fresh", "MvpExp")["effect"],
                         {"target": "mexp", "constructor_value_retained": 0})
        exp = self.op(rec, "if_fresh", "BaseExp")
        self.assertEqual(exp["result"], "rate_dependent_assignment")
        self.assertEqual(exp["effect"]["declared_uint64"], 2 ** 64 - 1)
        self.assertNotIn("assigned_value", exp["effect"])
        self.assertTrue(exp["effect"]["stored_value"].startswith("not computed"))
        self.assertEqual(self.field(rec, "Level")["selected"], {"status": "absent"})
        self.assertEqual(rec["excluded_by_design"]["exp_runtime_value"],
                         "not_computed_rate_dependent")

    def test_malformed_later_field_stays_unchecked(self):
        body = rows("  - Id: 1001\n" + BASE + "    Attack: [not, a, number]\n"
                    "    Drops: oops\n")
        _fx, target, manifest, recs = self.run_fixture(body)
        for name, branch in recs[0]["branches"].items():
            self.assertEqual(branch["later_parser"], "later_parser_unchecked")
            self.assertEqual(branch["operations"][-2 if name == "if_fresh" else -1]["result"],
                             "later_parser_unchecked")
        self.assertEqual(recs[0]["branches"]["if_fresh"]["insertion"],
                         "conditional_on_later_parser")
        self.assertIn("unresolved_by_design", recs[0]["excluded_by_design"]["membership"])
        self.assertEqual(manifest["status"], "complete")
        self.assertTrue((target / mp.OUTPUT_COMPLETE).exists())
        text = (target / mp.OUTPUT_MANIFEST).read_text()
        for word in ("accepted_monsters", "effective_monsters"):
            self.assertNotIn(word, text)


class ProvenanceTests(Base):
    """Identity bridge: MOB-only global order, repeated visits, Clear epochs, unchanged rows."""

    def test_repeated_visit_occurrences_reserve_each_emission(self):
        files = files_of(extra={"db/import/mob_db.yml": MH + rows("  - Id: 1001\n" + BASE)})
        files["rathena/db/mob_db.yml"] = (MH +
            "Footer:\n  Imports:\n    - Path: db/import/mob_db.yml\n"
            "    - Path: db/import/mob_db.yml\n").encode("utf-8")
        fx = Fixture(self.tmp, files)
        target, manifest, _h = fx.project(caps=dict(mp.CAPS, max_target_occurrences=5))
        self.assertEqual(manifest["status"], "unsupported")
        self.assertEqual(manifest["stop"]["detail"], "max_target_occurrences")
        self.assertEqual(len(records(target)), 1)
        self.assertEqual(manifest["work_usage"]["target_occurrences"], 3)
        self.assertEqual(len(manifest["parser_attempts"]), 2)  # root + once-parsed repeated leaf
        self.assertEqual(manifest["unresolved"][0]["rows"], 1)
        self.assertFalse((target / mp.OUTPUT_COMPLETE).exists())
        exact, boundary, _h = fx.project("exact-cap", caps=dict(mp.CAPS, max_target_occurrences=6))
        self.assertEqual(boundary["status"], "complete")
        self.assertEqual(boundary["work_usage"]["target_occurrences"], 6)
        self.assertEqual(len(records(exact)), 2)

    def test_last_visit_keeps_its_unfinished_current_suffix(self):
        fx = Fixture(self.tmp, files_of(rows("  - Id: 1001\n" + BASE,
                                           "  - Id: 1002\n" + BASE)))
        target, manifest, _h = fx.project(caps=dict(mp.CAPS, max_declarations=1))
        self.assertEqual(manifest["status"], "unsupported")
        self.assertEqual(len(records(target)), 1)
        self.assertEqual(manifest["unresolved"], [{
            "kind": "visit_suffix_not_projected", "visit": 1, "path": "db/mob_db.yml",
            "first_local_ordinal": 1, "first_global_ordinal": 2, "rows": 1}])
        self.assertFalse((target / mp.OUTPUT_COMPLETE).exists())

    def test_raw_numeric_metadata_refuses_boolean_aliases(self):
        for key, replacement in (("epoch", False), ("local_ordinal", False),
                                 ("database_ordinal", False), ("root_order", True),
                                 ("global_ordinal", True)):
            with self.subTest(key=key):
                fx = Fixture(self.tmp, files_of(rows("  - Id: 1001\n" + BASE)), name="cat-" + key)
                lines = fx.lines()
                row = json.loads(lines[-1])
                self.assertEqual(row[key], int(replacement))  # demonstrates Python equality trap
                row[key] = replacement
                lines[-1] = mp.render_row(row)
                fx.rewrite(lines)  # coherent fixture pins/marker do not rescue a wrong JSON type
                with self.assertRaises(mp.InputError):
                    fx.project("out-" + key)
                self.assertFalse((self.tmp / ("out-" + key)).exists())

    def test_nested_raw_boolean_is_not_reconstructed_integer(self):
        fx = Fixture(self.tmp, files_of(rows("  - Id: 1001\n" + BASE)))
        lines = fx.lines()
        row = json.loads(lines[-1])
        self.assertEqual(row["raw_ids"][0]["field_ordinal"], 0)
        row["raw_ids"][0]["field_ordinal"] = False
        lines[-1] = mp.render_row(row)
        fx.rewrite(lines)
        target, manifest, _h = fx.project()
        self.assertEqual(manifest["status"], "unsupported")
        self.assertEqual(manifest["stop"]["kind"], "provenance_mismatch")
        self.assertEqual(records(target), [])
        self.assertEqual(manifest["unresolved"][0]["rows"], 1)
        self.assertFalse((target / mp.OUTPUT_COMPLETE).exists())

    def repeated(self):
        root = MH + rows("  - Id: 1001\n" + BASE + "    Level: 1\n") + \
            "Footer:\n  Imports:\n    - Path: db/import/mob_db.yml\n" \
            "    - Path: db/clear_mob.yml\n    - Path: db/import/mob_db.yml\n"
        imp = MH + rows("  - Id: 1001\n    Level: 2\n", "  - Id: 1002\n" + BASE)
        clear = MH.replace("Version: 5\n", "Version: 5\n  Clear: true\n") + \
            rows("  - Id: 1001\n" + BASE + "    Level: 3\n")
        files = files_of(item="  - Id: 502\n", extra={"db/import/mob_db.yml": imp,
                                                       "db/clear_mob.yml": clear})
        files["rathena/db/mob_db.yml"] = root.encode("utf-8")
        return Fixture(self.tmp, files)

    def test_repeated_same_id_across_visits_and_epochs(self):
        fx = self.repeated()
        target, manifest, _h = fx.project()
        recs = records(target)
        catalog = [json.loads(line) for line in fx.lines()]
        mob = [r for r in catalog if r["database"] == "MOB_DB"]
        self.assertEqual([r["raw_declaration"] for r in recs], mob)
        self.assertEqual([r["projection_ordinal"] for r in recs], list(range(len(mob))))
        self.assertEqual(recs[0]["raw_declaration"]["global_ordinal"], 2)
        history = records(target, mp.OUTPUT_HISTORY)
        first = history[0]
        self.assertEqual(first["id"], 1001)
        self.assertEqual([(d["visit"], d["epoch"]) for d in first["declarations"]],
                         [(1, 0), (2, 0), (3, 1), (4, 1)])
        self.assertEqual(first["declaration_count"], 4)
        for rec in recs:  # no membership/branch inference from earlier declarations
            self.assertEqual(set(rec["branches"]), {"if_existing", "if_fresh"})
        self.assertEqual(recs[1]["branches"]["if_fresh"]["outcome"], "known_prefix_return0")
        self.assertEqual(recs[1]["branches"]["if_existing"]["outcome"], "prefix_modelled")
        self.assertEqual(len(manifest["parser_attempts"]), 3)  # the repeated file parsed once
        self.assertEqual(manifest["mob_selection"]["clear_history"][0]["epoch_after"], 1)
        self.assertEqual(manifest["mob_selection"]["visits"], [1, 2, 3, 4])
        self.assertEqual(manifest["status"], "complete")
        complete = json.loads((target / mp.OUTPUT_COMPLETE).read_text())
        self.assertEqual(complete["manifest_sha256"],
                         sha((target / mp.OUTPUT_MANIFEST).read_bytes()))
        self.assertEqual(complete["declarations_sha256"],
                         sha((target / mp.OUTPUT_DECLARATIONS).read_bytes()))
        self.assertEqual(complete["history_sha256"],
                         sha((target / mp.OUTPUT_HISTORY).read_bytes()))
        self.assertEqual(manifest["prerequisite"]["records"]["sha256"], fx.pins["records"]["sha256"])

    def test_nested_duplicate_retained_through_row_identity(self):
        _fx, _t, _m, recs = self.run_fixture(rows("  - Id: 1001\n" + BASE +
                                                  "    Modes:\n      A: true\n      A: false\n"))
        self.assertEqual(recs[0]["projection_status"], "modelled")

    def test_tampered_row_is_detected_as_provenance_stop(self):
        fx = Fixture(self.tmp, files_of(rows("  - Id: 1001\n" + BASE, "  - Id: 1002\n" + BASE)))
        lines = fx.lines()
        row = json.loads(lines[-1])
        row["fingerprint_sha256"] = "0" * 64
        lines[-1] = mp.render_row(row)
        fx.rewrite(lines)
        target, manifest, _h = fx.project()
        self.assertEqual(manifest["status"], "unsupported")
        self.assertEqual(manifest["stop"]["kind"], "provenance_mismatch")
        self.assertEqual(manifest["stop"]["global_ordinal"], 2)
        self.assertEqual(len(records(target)), 1)
        self.assertEqual(manifest["counts"]["raw_declarations"], 1)
        self.assertFalse((target / mp.OUTPUT_COMPLETE).exists())

    def refused(self, fx, pattern, **kw):
        with self.assertRaisesRegex(mp.InputError, pattern):
            fx.project(**kw)
        self.assertFalse((self.tmp / "out").exists())

    def test_relationship_tamper_refused(self):
        body = rows("  - Id: 1001\n" + BASE, "  - Id: 1002\n" + BASE)
        cases = [
            ("swap", lambda fx: fx.rewrite(fx.lines()[:1] + fx.lines()[2:] + fx.lines()[1:2]),
             "global_ordinal|outside"),
            ("drop", lambda fx: fx.rewrite(fx.lines()[:-1]), "raw_rows|declares"),
            ("encoding", lambda fx: fx.rewrite(fx.lines()[:-1] + [
                json.dumps(json.loads(fx.lines()[-1])).encode("ascii") + b"\n"]), "canonical"),
            ("extra", lambda fx: fx.rewrite(fx.lines() + fx.lines()[-1:]), "raw_rows|outside"),
            ("marker-manifest", lambda fx: fx.rewrite(complete=lambda c: c.update(
                manifest_sha256="0" * 64)), "manifest_sha256"),
            ("marker-status", lambda fx: fx.rewrite(complete=lambda c: c.update(
                status="incomplete")), "status"),
            ("records-binding", lambda fx: fx.rewrite(manifest=lambda m: m["records_file"]
                                                      .update(sha256="0" * 64)),
             "records_sha256|records_file"),
            ("generator", lambda fx: fx.rewrite(manifest=lambda m: m["generator"].update(
                source_sha256="0" * 64)), "generator"),
            ("adapter", lambda fx: fx.rewrite(manifest=lambda m: m["parser"].update(
                adapter_sha256="0" * 64)), "parser"),
            ("profile", lambda fx: fx.rewrite(manifest=lambda m: m["profile"].update(
                renewal=False)), "profile"),
            ("snapshot", lambda fx: fx.rewrite(manifest=lambda m: m["input"].update(
                snapshot_manifest_sha256="0" * 64)), "input"),
            ("reader", lambda fx: fx.rewrite(manifest=lambda m: m["input"]["verification"]
                                             .update(reader_sha256="0" * 64)), "input"),
            ("visit-file", lambda fx: fx.rewrite(manifest=lambda m: m["visits"][1].update(
                sha256="0" * 64)), "does not match the snapshot|file_sha256"),
            ("visit-epoch", lambda fx: fx.rewrite(manifest=lambda m: m["visits"][1]["body"]
                                                  .update(epoch=1)), "epoch"),
        ]
        for name, tamper, pattern in cases:
            with self.subTest(name):
                sub = self.tmp / name
                sub.mkdir(mode=0o700)
                fx = Fixture(sub, files_of(body))
                tamper(fx)
                with self.assertRaisesRegex(mp.InputError, pattern):
                    fx.project()
                self.assertFalse((sub / "out").exists())

    def test_wrong_pins_canonical_expectation_and_missing_marker(self):
        fx = Fixture(self.tmp, files_of(rows("  - Id: 1001\n" + BASE)))
        for key in ("manifest", "complete", "records"):
            bad = json.loads(json.dumps(fx.pins))
            bad[key]["sha256"] = "0" * 64
            self.refused(fx, "pinned|records_sha256", pins=bad)
            bad = json.loads(json.dumps(fx.pins))
            bad[key]["bytes"] += 1
            self.refused(fx, "pinned", pins=bad)
        self.refused(fx, "canonical", expected=mp.CANONICAL_MOB)
        self.refused(fx, "pinned MOB source", file_pins=mp.MOB_FILE_PINS)
        self.refused(fx, "profile", profile=yg.PROFILE)
        os.chmod(fx.dir, 0o700)
        (fx.dir / "stray.json").write_text("{}")
        self.refused(fx, "holds")
        (fx.dir / "stray.json").unlink()
        (fx.dir / "yaml-graph-complete.json").unlink()
        self.refused(fx, "cannot open")

    def test_strict_json_and_non_regular_inputs(self):
        with self.assertRaisesRegex(mp.InputError, "duplicate"):
            mp.strict_json(b'{"a":1,"a":2}', "x")
        with self.assertRaisesRegex(mp.InputError, "non-finite"):
            mp.strict_json(b'{"a":NaN}', "x")
        fx = Fixture(self.tmp, files_of(rows("  - Id: 1001\n" + BASE)))
        os.chmod(fx.dir, 0o700)
        rec = fx.dir / "raw-declarations.jsonl"
        real = self.tmp / "real.jsonl"
        os.rename(rec, real)
        os.symlink(real, rec)
        self.refused(fx, "cannot open without following links")
        rec.unlink()
        os.mkfifo(rec)  # nonblocking open: refused as non-regular, never blocks
        self.refused(fx, "not a regular file")
        rec.unlink()
        os.rename(real, rec)
        link = self.tmp / "catlink"
        os.symlink(fx.dir, link)
        with self.assertRaisesRegex(mp.InputError, "not a directory"):
            mp.execute(fx.files, fx.fresh, link, self.tmp / "out2", pins=fx.pins, expected=None,
                       file_pins=None, profile=PROFILE)

    def test_line_cap(self):
        fx = Fixture(self.tmp, files_of(rows("  - Id: 1001\n" + BASE)))
        caps = dict(mp.CAPS, max_raw_line_bytes=64)
        self.refused(fx, "exceeds 64 bytes", caps=caps)


class ParserAndLimitTests(Base):
    """policy: parser refusals/budgets are qualified stops with exact or unknown work."""

    def test_parser_stop_preserves_prefix_and_unresolved_suffix(self):
        root = MH + rows("  - Id: 1001\n" + BASE) + \
            "Footer:\n  Imports:\n    - Path: db/import/mob_db.yml\n"
        files = files_of(extra={"db/import/mob_db.yml": MH + rows("  - Id: 1002\n" + BASE)})
        files["rathena/db/mob_db.yml"] = root.encode("utf-8")
        fx = Fixture(self.tmp, files)
        real = yg.parse_yaml
        calls = []

        def flaky(data, limits, ruby):
            calls.append(len(data))
            if len(calls) == 2:
                raise yg.Stop("parser_limit", "wall_timeout",
                              adapter={"input_bytes": len(data), "stdout_bytes": 7,
                                       "stderr_bytes": 0, "stdout_observed_bytes": 9,
                                       "stderr_observed_bytes": 0, "stdout_complete": False,
                                       "stderr_complete": False, "exit": -9,
                                       "node_total": None, "node_count_lower_bound": 0})
            return real(data, limits, ruby)
        with mock.patch.object(yg, "parse_yaml", flaky):
            target, manifest, _h = fx.project()
        self.assertEqual(manifest["status"], "unsupported")
        self.assertEqual(manifest["stop"]["kind"], "parser_parser_limit")
        self.assertEqual(len(records(target)), 1)
        self.assertEqual(manifest["work_usage"]["unknown_node_count_attempts"], 1)
        self.assertEqual(manifest["work_usage"]["adapter_stdout_observed_bytes"] -
                         manifest["parser_attempts"][0]["parser_attempt"]["stdout_observed_bytes"],
                         9)
        self.assertEqual(len(calls), 2)  # no retry after unknown work
        self.assertEqual(manifest["unresolved"][0]["visit"], 2)
        self.assertEqual(manifest["unresolved"][0]["first_local_ordinal"], 0)
        self.assertEqual(manifest["unresolved"][0]["rows"], 1)
        self.assertFalse((target / mp.OUTPUT_COMPLETE).exists())

    def test_node_budget_and_projection_caps(self):
        fx = Fixture(self.tmp, files_of(rows("  - Id: 1001\n" + BASE, "  - Id: 1002\n" + BASE)))
        limits = dict(yg.LIMITS, max_nodes_per_file=5)
        target, manifest, _h = fx.project(limits=limits)
        self.assertEqual(manifest["stop"]["kind"], "parser_work_limit")
        self.assertIsNone(manifest["parser_attempts"][0]["parser_attempt"]["node_total"])
        for cap, value, name in (("max_declarations", 1, "max_declarations"),
                                 ("max_target_occurrences", 4, "max_target_occurrences"),
                                 ("max_declaration_file_bytes", 100,
                                  "max_declaration_file_bytes")):
            with self.subTest(cap):
                caps = dict(mp.CAPS, **{cap: value})
                target, manifest, _h = fx.project(name="cap-" + cap, caps=caps)
                self.assertEqual((manifest["status"], manifest["stop"]["detail"]),
                                 ("unsupported", name))
                self.assertEqual(manifest["counts"]["raw_declarations"], len(records(target)))
                self.assertFalse((target / mp.OUTPUT_COMPLETE).exists())

    def test_child_setup_failure_is_reaped_and_qualified(self):
        fx = Fixture(self.tmp, files_of(rows("  - Id: 1001\n" + BASE)))
        real, calls = yg.selectors.DefaultSelector, []

        def failing():  # the identity check succeeds; the parse child's setup fails
            calls.append(1)
            if len(calls) > 1:
                raise OSError("boom")
            return real()
        with mock.patch.object(yg.selectors, "DefaultSelector", failing):
            target, manifest, _h = fx.project()
        self.assertEqual(manifest["stop"]["kind"], "parser_parser_failure")
        attempt = manifest["parser_attempts"][0]["parser_attempt"]
        self.assertIsNotNone(attempt["exit"])  # killed and reaped
        self.assertIsNone(attempt["node_total"])

    def test_parser_identity_refused_before_output(self):
        fx = Fixture(self.tmp, files_of(rows("  - Id: 1001\n" + BASE)))
        with mock.patch.object(yg, "check_parser", side_effect=yg.InputError("identity")):
            with self.assertRaisesRegex(mp.InputError, "identity"):
                fx.project()
        self.assertFalse((self.tmp / "out").exists())

    def test_selected_tool_bytes_checked(self):
        other = self.tmp / "tools"
        other.mkdir()
        here = TOOL.parent
        (other / "server_selection.py").write_bytes((here / "server_selection.py").read_bytes())
        (other / "yaml_graph_inventory.py").write_bytes(
            (here / "yaml_graph_inventory.py").read_bytes() + b"\n")
        with self.assertRaisesRegex(mp.InputError, "pinned"):
            mp.selected(other)


class PublicationTests(Base):
    def fixture(self):
        return Fixture(self.tmp, files_of(rows("  - Id: 1001\n" + BASE)))

    def assert_fd_closed(self, fd):
        with self.assertRaises(OSError) as caught:
            os.fstat(fd)
        self.assertEqual(caught.exception.errno, errno.EBADF)

    @staticmethod
    def close_held_test_fd(fd, expected, close):
        """Test-owned fallback only; a reused unrelated descriptor is preserved."""
        if fd is not None:
            try:
                info = os.fstat(fd)
            except OSError as exc:
                if exc.errno != errno.EBADF:
                    raise
            else:
                if (info.st_dev, info.st_ino) == expected:
                    close(fd)

    def fdopen_refusal(self, wanted, output):
        fx = self.fixture()
        target = self.tmp / output
        state = {"directory": None, "fd": None, "identity": None, "guard": None, "hits": 0}
        real_open, real_fdopen, real_close = os.open, os.fdopen, os.close
        held = []

        def tracking_open(path, flags, *a, **k):
            fd = real_open(path, flags, *a, **k)
            if flags == mp.DIR_FLAGS and Path(path) == target:
                state["directory"] = fd
            elif path == wanted and k.get("dir_fd") == state["directory"] and \
                    flags & os.O_CREAT and flags & os.O_EXCL:
                info = os.fstat(fd)
                state.update(fd=fd, identity=(info.st_dev, info.st_ino), guard=os.dup(fd))
            return fd

        def failing_fdopen(fd, *a, **k):
            if fd == state["fd"] and not state["hits"]:
                state["hits"] += 1
                raise OSError(errno.EIO, "controlled fdopen failure")
            return real_fdopen(fd, *a, **k)
        try:
            with mock.patch.object(mp.os, "open", tracking_open), \
                    mock.patch.object(mp.os, "fdopen", failing_fdopen):
                try:
                    fx.project(output)
                except mp.OutputError as exc:
                    held.append(exc)  # retain the actual exception until checks/cleanup finish
            self.assertEqual(state["hits"], 1)
            self.assertEqual(len(held), 1)
            self.assertIn("controlled fdopen failure", str(held[0]))
            self.assert_fd_closed(state["fd"])
            self.assert_fd_closed(state["directory"])
            self.assertFalse((target / mp.OUTPUT_COMPLETE).exists())
        finally:
            self.close_held_test_fd(state["fd"], state["identity"], real_close)
            if state["guard"] is not None:
                real_close(state["guard"])

    def test_record_fdopen_setup_failure_closes_raw_descriptor(self):
        self.fdopen_refusal(mp.OUTPUT_DECLARATIONS, "record-setup")

    def test_write_new_fdopen_setup_failure_closes_raw_descriptor(self):
        for wanted in (mp.OUTPUT_MANIFEST, mp.OUTPUT_COMPLETE):
            with self.subTest(file=wanted):
                # Each helper builds a fresh raw catalog under this private parent.
                with tempfile.TemporaryDirectory(dir=self.tmp) as child:
                    original = self.tmp
                    self.tmp = Path(child)
                    try:
                        self.fdopen_refusal(wanted, "new-setup")
                    finally:
                        self.tmp = original

    def test_final_directory_close_before_release_is_retried_and_closed(self):
        fx = self.fixture()
        target = self.tmp / "before-close"
        state = {"fd": None, "identity": None, "guard": None, "hits": 0}
        real_open, real_close = os.open, os.close
        held = []

        def tracking_open(path, flags, *a, **k):
            fd = real_open(path, flags, *a, **k)
            if flags == mp.DIR_FLAGS and Path(path) == target and state["fd"] is None:
                info = os.fstat(fd)
                state.update(fd=fd, identity=(info.st_dev, info.st_ino), guard=os.dup(fd))
            return fd

        def failing_close(fd):
            if fd == state["fd"] and not state["hits"] and (target / mp.OUTPUT_COMPLETE).exists():
                state["hits"] += 1
                raise OSError(errno.EIO, "controlled before-close failure")
            return real_close(fd)
        try:
            with mock.patch.object(mp.os, "open", tracking_open), \
                    mock.patch.object(mp.os, "close", failing_close):
                try:
                    fx.project("before-close")
                except mp.OutputError as exc:
                    held.append(exc)
            self.assertEqual((state["hits"], len(held)), (1, 1))
            self.assert_fd_closed(state["fd"])
            self.assertFalse((target / mp.OUTPUT_COMPLETE).exists())
        finally:
            self.close_held_test_fd(state["fd"], state["identity"], real_close)
            if state["guard"] is not None:
                real_close(state["guard"])

    def test_after_close_reused_foreign_descriptor_is_preserved(self):
        fx = self.fixture()
        target, foreign = self.tmp / "reused-close", self.tmp / "foreign.bin"
        foreign.write_bytes(b"foreign resource")
        pin = os.stat(foreign)
        foreign_identity = (pin.st_dev, pin.st_ino)
        state = {"fd": None, "identity": None, "guard": None, "foreign_fd": None, "hits": 0}
        real_open, real_close = os.open, os.close
        held = []

        def tracking_open(path, flags, *a, **k):
            fd = real_open(path, flags, *a, **k)
            if flags == mp.DIR_FLAGS and Path(path) == target and state["fd"] is None:
                info = os.fstat(fd)
                state.update(fd=fd, identity=(info.st_dev, info.st_ino), guard=os.dup(fd))
            return fd

        def failing_close(fd):
            if fd == state["fd"] and not state["hits"] and (target / mp.OUTPUT_COMPLETE).exists():
                state["hits"] += 1
                real_close(fd)
                self.assert_fd_closed(fd)
                replacement = real_open(foreign, os.O_RDONLY | os.O_NOFOLLOW)
                state["foreign_fd"] = replacement
                if replacement != fd:
                    self.assert_fd_closed(fd)
                    os.dup2(replacement, fd, inheritable=False)
                    real_close(replacement)
                    state["foreign_fd"] = fd
                raise OSError(errno.EIO, "controlled after-close failure with foreign reuse")
            return real_close(fd)
        try:
            with mock.patch.object(mp.os, "open", tracking_open), \
                    mock.patch.object(mp.os, "close", failing_close):
                try:
                    fx.project("reused-close")
                except mp.OutputError as exc:
                    held.append(exc)
            self.assertEqual((state["hits"], len(held)), (1, 1))
            info = os.fstat(state["foreign_fd"])
            self.assertEqual((info.st_dev, info.st_ino), foreign_identity)
            self.assertEqual(os.pread(state["foreign_fd"], 64, 0), b"foreign resource")
            self.assertEqual(foreign.read_bytes(), b"foreign resource")
            self.assertFalse((target / mp.OUTPUT_COMPLETE).exists())
        finally:
            self.close_held_test_fd(state["foreign_fd"], foreign_identity, real_close)
            self.close_held_test_fd(state["fd"], state["identity"], real_close)
            if state["guard"] is not None:
                real_close(state["guard"])

    def test_private_complete_and_deterministic_records(self):
        fx = self.fixture()
        a, ma, ha = fx.project("a")
        b, mb, hb = fx.project("b")
        self.assertEqual(stat.S_IMODE(os.stat(a).st_mode), 0o700)
        self.assertEqual(sorted(os.listdir(a)), sorted([mp.OUTPUT_COMPLETE, mp.OUTPUT_MANIFEST,
                                                        mp.OUTPUT_DECLARATIONS,
                                                        mp.OUTPUT_HISTORY]))
        for name in os.listdir(a):
            self.assertEqual(stat.S_IMODE(os.stat(a / name).st_mode), 0o600)
        self.assertEqual((ha["declarations_sha256"], ha["history_sha256"]),
                         (hb["declarations_sha256"], hb["history_sha256"]))
        ma.pop("timings_seconds"), mb.pop("timings_seconds")
        self.assertEqual(ma, mb)
        self.assertEqual(ma["records_file"]["readback"],
                         "verified size, SHA-256, private mode and identity")

    def test_existing_destinations_preserved(self):
        fx = self.fixture()
        (self.tmp / "file").write_text("keep")
        (self.tmp / "dir").mkdir()
        os.symlink(self.tmp / "missing", self.tmp / "dangling")
        os.mkfifo(self.tmp / "fifo")
        for name in ("file", "dir", "dangling", "fifo"):
            with self.assertRaises(mp.OutputError):
                fx.project(name)
        self.assertEqual((self.tmp / "file").read_text(), "keep")
        self.assertEqual(os.listdir(self.tmp / "dir"), [])
        self.assertTrue(os.path.islink(self.tmp / "dangling"))
        os.chmod(self.tmp, 0o770)
        with self.assertRaisesRegex(mp.OutputError, "group/world"):
            fx.project("x")
        os.chmod(self.tmp, 0o700)

    def test_readback_tamper_fails_without_marker(self):
        fx = self.fixture()
        real = mp.verify_published

        def tamper(dir_fd, name, size, digest, identity):
            if name == mp.OUTPUT_HISTORY:
                fd = os.open(name, os.O_WRONLY | os.O_APPEND, dir_fd=dir_fd)
                os.write(fd, b"x")
                os.close(fd)
            return real(dir_fd, name, size, digest, identity)
        with mock.patch.object(mp, "verify_published", tamper):
            with self.assertRaisesRegex(mp.OutputError, "not the owned private|differs"):
                fx.project()
        self.assertFalse((self.tmp / "out" / mp.OUTPUT_COMPLETE).exists())

    def test_final_directory_close_failure_removes_owned_marker(self):
        fx = self.fixture()
        real_close, closed = os.close, []
        state = {"dir_fd": None}
        real_open = os.open

        def tracking_open(path, flags, *a, **k):
            fd = real_open(path, flags, *a, **k)
            if flags == mp.DIR_FLAGS and str(path).endswith("out") and state["dir_fd"] is None:
                state["dir_fd"] = fd
            return fd

        def failing_close(fd):
            if fd == state["dir_fd"] and not closed:
                closed.append(fd)
                real_close(fd)  # actually closed, then reported as a failure
                raise OSError(5, "simulated close failure")
            return real_close(fd)
        with mock.patch.object(mp.os, "open", tracking_open), \
                mock.patch.object(mp.os, "close", failing_close):
            with self.assertRaisesRegex(mp.OutputError, "simulated close failure"):
                fx.project()
        self.assertEqual(closed, [state["dir_fd"]])
        with self.assertRaises(OSError):  # the directory descriptor really was closed
            os.fstat(state["dir_fd"])
        self.assertFalse((self.tmp / "out" / mp.OUTPUT_COMPLETE).exists())
        self.assertTrue((self.tmp / "out" / mp.OUTPUT_MANIFEST).exists())

    def test_foreign_marker_replacement_preserved(self):
        fx = self.fixture()
        real = mp.verify_published
        keep = []

        def swap(dir_fd, name, size, digest, identity):
            real(dir_fd, name, size, digest, identity)
            if name == mp.OUTPUT_COMPLETE:
                keep.append(os.open(name, os.O_RDONLY, dir_fd=dir_fd))  # old inode stays alive
                os.unlink(name, dir_fd=dir_fd)
                fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=dir_fd)
                os.write(fd, b"foreign")
                os.close(fd)
                raise OSError(5, "after marker")
        try:
            with mock.patch.object(mp, "verify_published", swap):
                with self.assertRaisesRegex(mp.OutputError, "foreign file preserved"):
                    fx.project()
            self.assertEqual((self.tmp / "out" / mp.OUTPUT_COMPLETE).read_bytes(), b"foreign")
            self.assertNotEqual(os.fstat(keep[0]).st_ino,
                                os.stat(self.tmp / "out" / mp.OUTPUT_COMPLETE).st_ino)
        finally:
            for fd in keep:
                os.close(fd)

    def test_owned_marker_removed_and_cleanup_failure_reported(self):
        fx = self.fixture()
        real = os.listdir

        def failing(target):  # the prerequisite listing works; the final output listing fails
            if not failing.calls:
                failing.calls.append(1)
                return real(target)
            raise OSError(5, "listing failed")
        failing.calls = []
        with mock.patch.object(mp.os, "listdir", failing):
            with self.assertRaisesRegex(mp.OutputError, "listing failed"):
                fx.project("a")
        self.assertFalse((self.tmp / "a" / mp.OUTPUT_COMPLETE).exists())
        self.assertTrue((self.tmp / "a" / mp.OUTPUT_MANIFEST).exists())
        failing.calls = []
        with mock.patch.object(mp.os, "listdir", failing), \
                mock.patch.object(mp.os, "unlink", side_effect=OSError(1, "unlink denied")):
            with self.assertRaisesRegex(mp.OutputError, "could not remove .*unlink denied"):
                fx.project("b")
        self.assertTrue((self.tmp / "b" / mp.OUTPUT_COMPLETE).exists())

    def test_unexpected_error_is_reported_as_publication_failure(self):
        fx = self.fixture()
        with mock.patch.object(mp, "build_manifest", side_effect=KeyError("x")):
            with self.assertRaisesRegex(mp.OutputError, "unexpected"):
                fx.project()
        self.assertFalse((self.tmp / "out" / mp.OUTPUT_COMPLETE).exists())


class CliTests(Base):
    def test_no_bypass_and_refusals(self):
        out = subprocess.run([sys.executable, "-I", str(TOOL), "--help"], capture_output=True,
                             text=True, check=True).stdout
        for word in ("--pin", "--profile", "--parser", "--source"):
            self.assertNotIn(word, out)
        res = subprocess.run([sys.executable, "-I", str(TOOL), str(self.tmp / "nope"),
                              str(self.tmp / "nope2"), str(self.tmp / "out")],
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 2)
        self.assertIn("error [input]", res.stderr)
        res = subprocess.run([sys.executable, "-I", str(TOOL), "a", "b", "c", "--profile", "x"],
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 2)


SNAPSHOT = os.environ.get("T06_MONSTER_SNAPSHOT", "")
RAW = os.environ.get("T06_MONSTER_RAW_CATALOG", "")


@unittest.skipUnless(os.path.isabs(SNAPSHOT) and os.path.isdir(SNAPSHOT) and
                     os.path.isabs(RAW) and os.path.isdir(RAW),
                     "T06_MONSTER_SNAPSHOT / T06_MONSTER_RAW_CATALOG not set")
class ActualInputTests(unittest.TestCase):
    """Fresh actual CLI; every output declaration is re-derived from the actual inputs."""

    def test_actual_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.chmod(tmp, 0o700)
            target = Path(tmp) / "actual"
            res = subprocess.run([sys.executable, "-I", str(TOOL), SNAPSHOT, RAW, str(target)],
                                 capture_output=True, text=True, timeout=600)
            self.assertIn(res.returncode, (0, 1), res.stderr)
            summary = json.loads(res.stdout)
            manifest = json.loads((target / mp.OUTPUT_MANIFEST).read_bytes())
            self.assertEqual(summary["status"], manifest["status"])
            self.assertEqual(res.returncode == 0, manifest["status"] == "complete")
            self.check(target, manifest)

    def check(self, target, manifest):
        with (Path(RAW) / "raw-declarations.jsonl").open("rb") as stream:
            raw = [json.loads(line) for line in stream if b'"database":"MOB_DB"' in line]
        decls = records(target)
        self.assertEqual(len(decls), len(raw))
        self.assertEqual([d["raw_declaration"] for d in decls], raw)
        sources = {}
        history = {}
        for ordinal, decl in enumerate(decls):
            self.assertEqual(decl["projection_ordinal"], ordinal)
            path = decl["raw_declaration"]["file"]
            if path not in sources:
                sources[path] = (Path(SNAPSHOT) / "rathena" / path).read_bytes()
            data = sources[path]
            keys = [f["key"] for f in decl["raw_declaration"]["fields"]]
            for order, field in enumerate(decl["fields"]):
                name = mp.FIELDS[order]
                self.assertEqual(field["field"], name)
                self.assertEqual(field["occurrence_count"], keys.count(name))
                for occ in field["occurrences"]:
                    self.assertEqual(keys[occ["field_ordinal"]], name)
                    for part in ("key", "value"):
                        b, e = occ[part]["byte_span"]
                        self.assertEqual(sha(data[b:e]), occ[part]["span_sha256"])
                sel = field["selected"]
                if not field["occurrences"]:
                    self.assertEqual(sel, {"status": "absent"})
                    continue
                value = field["occurrences"][0]["value"]
                if value["kind"] == "scalar" and not value["null"] and name in mp.NAMES:
                    stored = value["text"].encode("utf-8")[:24].ljust(24, b"\0")
                    self.assertEqual(sel["stored_bytes_hex"], stored.hex())
                if sel["status"] == "supported" and name in mp.NUMERIC:
                    self.assertEqual(sel["value"], int(value["text"]))
            stage = decl["id_stage"]
            if "id" in stage:
                history.setdefault(stage["id"], []).append(ordinal)
            for branch in decl["branches"].values():
                self.assertIn(branch["later_parser"], ("later_parser_unchecked",
                                                       "later_parser_not_reached",
                                                       "unresolved_not_asserted",
                                                       "not_reached"))
                for op in branch["operations"]:
                    if op.get("result") == "rate_dependent_assignment":
                        self.assertNotIn("assigned_value", op["effect"])
        hist = records(target, mp.OUTPUT_HISTORY)
        self.assertEqual([h["id"] for h in hist], sorted(history))
        for entry in hist:
            self.assertEqual([d["projection_ordinal"] for d in entry["declarations"]],
                             history[entry["id"]])
        self.assertEqual(manifest["counts"]["raw_declarations"], len(decls))
        self.assertEqual(manifest["records_file"]["sha256"],
                         sha((target / mp.OUTPUT_DECLARATIONS).read_bytes()))
        self.assertEqual(manifest["history_file"]["sha256"],
                         sha((target / mp.OUTPUT_HISTORY).read_bytes()))
        if manifest["status"] == "complete":
            complete = json.loads((target / mp.OUTPUT_COMPLETE).read_bytes())
            self.assertEqual(complete["manifest_sha256"],
                             sha((target / mp.OUTPUT_MANIFEST).read_bytes()))


if __name__ == "__main__":
    unittest.main()
