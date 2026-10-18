#!/usr/bin/env python3
"""Authored tests for static_spawn_references.py (T06.002.003.005.002).

Run: python3 -I -B tools/renewal/test_static_spawn_references.py
Optional real-input checks: set STATIC_SPAWN_REFERENCE_FROZEN_ROOT to the immutable
frozen input root (with raw/, map/ and monster/ beneath it); they are skipped, and
reported as skipped, without it. That variable is read only by these tests, never
by the production CLI.

Families F01-F10 from the frozen brief. Core tests call the real join_events on
the checked-in authored fixture and small in-memory events; these are
post-admission semantics, never a production admission path. Fault checks replace
the producer's raw OS operation attributes; negative controls replace real
producer functions and require the affected golden check to fail.
"""

import copy
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("static_spawn_references",
                                              HERE / "static_spawn_references.py")
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)

FROZEN = os.environ.get("STATIC_SPAWN_REFERENCE_FROZEN_ROOT")
FIXTURE_PATH = HERE.parent.parent / "docs/project/fixtures/T06.002.003.005.002-authored.json"
FIXTURE_PIN = {"bytes": 38291,
               "sha256": "8af733caa674c9e950ca27bd906bb279f0752fff2a4c0fff93d3226ca1ae6f72"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def strict_load(data):
    def unique(pairs):
        keys = [k for k, _ in pairs]
        assert len(keys) == len(set(keys)), "duplicate key"
        return dict(pairs)
    return json.loads(data, object_pairs_hook=unique)


FIXTURE_BYTES = FIXTURE_PATH.read_bytes()
FIXTURE = strict_load(FIXTURE_BYTES)
CASE = FIXTURE["cases"][0]


def typed(value):
    """Type-tagged structure so 1 != True != 1.0 in comparisons."""
    if isinstance(value, dict):
        return ("dict", tuple(sorted((k, typed(v)) for k, v in value.items())))
    if isinstance(value, list):
        return ("list", tuple(typed(v) for v in value))
    return (type(value).__name__, value)


def join_case(case=CASE, limits=None):
    return P.join_events(case["events"], case["reverse"], case["candidates"],
                         case["histories"], limits)


# --- Small in-memory event builders -------------------------------------------------

class Stream:
    """Adjacent per-source events with contiguous global event indexes."""

    def __init__(self):
        self.events = []
        self.cursor = {}

    def _add(self, source, kind, payload, detail_fn):
        start = self.cursor.get(source, 0)
        end = start + len(payload)
        self.cursor[source] = end
        event = {"schema": 1, "source_index": source, "event_index": len(self.events),
                 "span": [start, end], "sha256": sha(payload), "kind": kind,
                 "detail": detail_fn(start, end)}
        self.events.append(event)
        return event

    def simple(self, kind="whitespace", payload=b"\n", source=0):
        return self._add(source, kind, payload, lambda s, e: None)

    def static(self, map_text=b"Foo", sprite=1002, source=0, keyword=b"monster"):
        sprite_text = str(sprite).encode()
        words = (map_text, keyword, b"N", sprite_text + b",1")
        payload = b"\t".join(words) + b"\n"

        def detail(start, end):
            spans, pos = [], start
            for word in words:
                spans.append([pos, pos + len(word)])
                pos += len(word) + 1
            default = lambda v: {"origin": "default", "span": None, "value": v}  # noqa: E731
            sprite_span = [spans[3][0], spans[3][0] + len(sprite_text)]
            return {"fields": [{"name": f"w{i + 1}", "raw_hex": w.hex(), "span": s}
                               for i, (w, s) in enumerate(zip(words, spans))],
                    "gaps": [], "keyword": keyword.decode(), "projection_state": "supported",
                    "tabs": 3,
                    "values": {"amount": {"origin": "declared", "span": [sprite_span[1] + 1,
                                                                           sprite_span[1] + 2],
                                          "value": 1},
                               "delay": default(5000),
                               "event": {"origin": "absent", "span": None, "value": None},
                               "map": {"origin": "declared", "span": spans[0],
                                       "value": map_text.hex()},
                               "name": {"origin": "declared", "span": spans[2], "value": "4e"},
                               "sprite": {"origin": "declared", "span": sprite_span,
                                          "value": sprite},
                               "variance": default(0), "x": default(0), "xs": default(0),
                               "y": default(0), "ys": default(0)}}
        return self._add(source, "static", payload, detail)

    def gap(self, map_text=b"Foo", source=0):
        payload = map_text + b"\tmonster\tN\t1002,1,\n"

        def detail(start, end):
            return {"fields": [{"name": "w1", "raw_hex": map_text.hex(),
                                "span": [start, start + len(map_text)]}],
                    "gaps": [{"code": "delay_form", "span": [end - 1, end - 1]}],
                    "keyword": "monster", "projection_state": "gap", "tabs": 3,
                    "values": None}
        return self._add(source, "static", payload, detail)

    def opaque(self, body=b"monster \"Foo\",0,0,\"N\",1002,1;", source=0):
        header = b"-\tscript\tS\t-1,"
        payload = header + b"{" + body + b"}"

        def detail(start, end):
            a = start + len(header)
            parts = {"header": [start, a], "open": [a, a + 1], "body": [a + 1, end - 1],
                     "close": [end - 1, end]}
            return {k: {"sha256": sha(payload[s - start:e - start]), "span": [s, e]}
                    for k, (s, e) in parts.items()}
        return self._add(source, "opaque", payload, detail)

    def suffix(self, payload=b"Foo\tmonster\tN\t1002,1 junk", source=0, reason="unsupported_construct"):
        return self._add(source, "suffix", payload,
                         lambda s, e: {"fault_offset": s, "reason": reason})


def reverse_rows(**names):
    return [{"id": i, "name": n} for n, i in sorted(names.items())]


def candidate(ordinal, name, index_id, disposition="retained", raw=None, **extra):
    base = {"attempts": [{"file": "unit.dat", "ordinal": ordinal, "outcome": "read"}],
            "config_file": "unit.conf", "config_line": ordinal + 1,
            "disposition": disposition, "index_lookup": {"id": index_id, "normalised": name},
            "name": name, "ordinal": ordinal, "raw": raw if raw is not None else name}
    fields = {"retained": {"cache": {"file": "unit.dat", "ordinal": ordinal},
                           "index_id": index_id, "slot": ordinal},
              "discarded_duplicate_index": {"cache": {"file": "unit.dat", "ordinal": ordinal},
                                            "duplicate_of_ordinal": 0},
              "discarded_not_found": {"reasons": ["cache_not_read"]},
              "unresolved_unsafe": {"uncertainty_since_ordinal": ordinal},
              "unresolved_due_to_prior_candidate": {"uncertainty_since_ordinal": 0}}
    base.update(fields[disposition])
    base.update(extra)
    return base


def reference(projection_ordinal, visit=4, epoch=0, id_text="1002", span=(11, 15)):
    return {"database": "MOB_DB", "database_ordinal": projection_ordinal, "epoch": epoch,
            "file": "db/unit.yml", "file_sha256": "1" * 64, "fingerprint_sha256": "4" * 64,
            "global_ordinal": 100 + projection_ordinal, "id_byte_span": list(span),
            "id_span_sha256": "5" * 64, "id_style": "plain", "id_text": id_text,
            "local_ordinal": projection_ordinal, "projection_ordinal": projection_ordinal,
            "projection_status": "modelled", "row_byte_span": [10, 20],
            "row_span_sha256": "2" * 64, "visit": visit}


def history(hid, refs, gate="in_range"):
    return {"declaration_count": len(refs), "declarations": refs, "id": hid,
            "id_decimal": str(hid), "meaning": "declared-Id history index, not one accepted entity",
            "source_gate": gate}


def conservation(test, result):
    """All fifteen occurrence-counter rules recomputed from the rows."""
    rows, c = result["rows"], result["counters"]
    test.assertEqual(sorted(c), sorted(P.COUNTER_KEYS))
    test.assertEqual(len(c), 15)
    test.assertEqual(c["events"], len(rows))
    test.assertEqual(c["events"], c["static_supported"] + c["static_gap"] + c["opaque"]
                     + c["suffix"] + c["not_static"])
    supported = [r for r in rows if r["unjoined"] is None]
    test.assertEqual(c["static_supported"], len(supported))
    codes = [r["unjoined"]["code"] for r in rows if r["unjoined"] is not None]
    test.assertEqual(c["static_gap"], codes.count("static_projection_gap"))
    test.assertEqual(c["opaque"], codes.count("opaque_script"))
    test.assertEqual(c["suffix"], codes.count("uncertified_suffix"))
    test.assertEqual(c["not_static"], codes.count("not_static"))
    states = [r["map"]["index"]["state"] for r in supported]
    test.assertEqual(c["map_index_missing"] + c["map_index_zero"] + c["map_index_nonzero"],
                     len(supported))
    for state in ("missing", "zero", "nonzero"):
        test.assertEqual(c["map_index_" + state], states.count(state))
    cstates = [r["map"]["candidate_state"] for r in supported
               if r["map"]["index"]["state"] == "nonzero"]
    test.assertEqual(c["map_candidate_none"] + c["map_candidate_present"], c["map_index_nonzero"])
    test.assertEqual(c["map_candidate_none"], cstates.count("none"))
    test.assertEqual(c["map_candidate_present"], cstates.count("present"))
    test.assertEqual(c["map_candidate_occurrences"],
                     sum(len(r["map"]["candidates"]) for r in supported))
    present = [r for r in supported if r["monster"]["state"] == "declared_history"]
    test.assertEqual(c["monster_history_present"] + c["monster_history_missing"], len(supported))
    test.assertEqual(c["monster_history_present"], len(present))
    test.assertEqual(c["monster_declaration_occurrences"],
                     sum(len(r["monster"]["history"]["declarations"]) for r in present))
    for row in rows:
        if row["unjoined"] is not None:
            test.assertIsNone(row["map"])
            test.assertIsNone(row["monster"])


def golden_check(test):
    """The authored whole-object golden (used by baseline and negative controls)."""
    result = join_case()
    test.assertEqual(typed(result), typed(CASE["expected"]))


# --- F01 ------------------------------------------------------------------------------

class F01AuthoredFixture(unittest.TestCase):
    def test_fixture_pin_and_api(self):
        self.assertEqual({"bytes": len(FIXTURE_BYTES), "sha256": sha(FIXTURE_BYTES)}, FIXTURE_PIN)
        self.assertTrue(issubclass(P.ReferenceError, Exception))
        self.assertEqual(P.LIMITS, {"completion_bytes": 65536, "events": 8192,
                                    "history_references": 20000, "history_rows": 10000,
                                    "input_total_bytes": 67108864, "jsonl_bytes": 16777216,
                                    "manifest_bytes": 1048576, "map_candidates": 10000,
                                    "map_reverse_rows": 2000})

    def test_whole_objects_and_counters(self):
        golden_check(self)
        result = join_case()
        self.assertEqual(set(result), {"rows", "counters"})
        self.assertEqual(typed(result["counters"]), typed(CASE["expected"]["counters"]))
        self.assertEqual(typed(join_case(limits=dict(P.LIMITS))), typed(result))
        conservation(self, result)

    def test_input_immutability_and_no_aliasing(self):
        before = copy.deepcopy(CASE)
        result = join_case()
        self.assertEqual(typed(CASE), typed(before))
        attached = result["rows"][0]["map"]["candidates"][0]
        attached["disposition"] = "mutated"
        result["rows"][0]["monster"]["history"]["declarations"].clear()
        result["rows"][4]["unjoined"]["detail"].clear()
        self.assertEqual(typed(CASE), typed(before))

    def test_five_normalisation_cases(self):
        self.assertEqual(len(FIXTURE["normalisation_cases"]), 5)
        for case in FIXTURE["normalisation_cases"]:
            got = P.normalise_map(case["raw_hex"])
            self.assertIs(type(got), str)
            self.assertEqual(got, case["expected"])

    def test_strict_numeric_types_are_distinguished(self):
        expected = copy.deepcopy(CASE["expected"])
        expected["rows"][0]["source_index"] = False
        self.assertNotEqual(typed(join_case()), typed(expected))
        self.assertEqual(join_case(), expected)  # plain == would wrongly accept this


# --- F02 ------------------------------------------------------------------------------

class F02MapNormalisation(unittest.TestCase):
    def one(self, map_text, reverse, candidates=()):
        s = Stream()
        s.static(map_text)
        return P.join_events(s.events, reverse, list(candidates), [])["rows"][0]["map"]

    def test_reverse_not_forward(self):
        # Native A/1, A/2, B/1: forward slot 1 = B, slot 2 = A; reverse A -> 2, B -> 1.
        reverse = reverse_rows(A=2, B=1)
        cands = [candidate(0, "B", 1), candidate(1, "A", 2)]
        a = self.one(b"A", reverse, cands)
        self.assertEqual(a["index"], {"state": "nonzero", "id": 2})
        self.assertEqual([c["name"] for c in a["candidates"]], ["A"])
        b = self.one(b"B", reverse, cands)
        self.assertEqual(b["index"], {"state": "nonzero", "id": 1})
        self.assertEqual([c["name"] for c in b["candidates"]], ["B"])

    def test_case_sensitive_lookup(self):
        reverse = reverse_rows(Foo=7)
        self.assertEqual(self.one(b"Foo", reverse)["index"]["state"], "nonzero")
        for text in (b"foo", b"FOO", b"fOO.gat"):
            ref = self.one(text, reverse)
            self.assertEqual(ref["index"], {"state": "missing", "id": None})
            self.assertEqual(ref["normalised"], text[:3].decode())

    def test_eleven_byte_base_with_upper_gat(self):
        raw = b"abcdefghijk.GAT"
        ref = self.one(raw, reverse_rows(abcdefghijk=5))
        self.assertEqual(ref["raw_hex"], raw.hex())
        self.assertEqual(ref["normalised"], "abcdefghijk")
        self.assertEqual(ref["index"], {"state": "nonzero", "id": 5})
        self.assertEqual(ref["candidate_state"], "none")

    def test_missing_zero_nonzero_none_present(self):
        reverse = reverse_rows(Z=0, N=3, P=4)
        cands = [candidate(0, "P", 4)]
        self.assertEqual(self.one(b"M", reverse, cands)["candidate_state"], "not_applicable")
        zero = self.one(b"Z", reverse, cands)
        self.assertEqual((zero["index"], zero["candidate_state"], zero["candidates"]),
                         ({"state": "zero", "id": 0}, "not_applicable", []))
        self.assertEqual(self.one(b"N", reverse, cands)["candidate_state"], "none")
        self.assertEqual(self.one(b"P", reverse, cands)["candidate_state"], "present")

    def test_configured_double_normalisation_attaches_by_id(self):
        cands = [candidate(0, "Foo.gat", 7, raw="Foo.gat.gat", disposition="retained")]
        cands[0]["index_lookup"]["normalised"] = "Foo"
        ref = self.one(b"Foo", reverse_rows(Foo=7), cands)
        self.assertEqual(typed(ref["candidates"]), typed(cands))

    def test_invalid_raw_hex_refused(self):
        bad = ["", "466F6F", "466f6", " 466f6f", "466f6f\n", "466f6f20", "2e676174",
               "466f6f2e6761742e676174", (b"a" * 12).hex(), (b"a" * 11 + b".gatx").hex(),
               "e4b8ad", 466, None, b"466f6f".decode().encode()]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(P.ReferenceError):
                P.normalise_map(value)


# --- F03 ------------------------------------------------------------------------------

class F03MapCandidates(unittest.TestCase):
    def test_all_occurrences_dispositions_in_order(self):
        cands = [candidate(0, "Foo", 7), candidate(1, "Bar", 8),
                 candidate(2, "Foo", 7, "discarded_duplicate_index"),
                 candidate(3, "Foo", None, "discarded_not_found"),
                 candidate(4, "Foo", 7, "unresolved_unsafe"),
                 candidate(5, "Foo", 7, "unresolved_due_to_prior_candidate"),
                 candidate(6, "Foo", 7, "discarded_not_found")]
        s = Stream()
        s.static(b"Foo")
        s.static(b"Foo.gat")
        before = copy.deepcopy(cands)
        result = P.join_events(s.events, reverse_rows(Foo=7, Bar=8), cands, [])
        for row in result["rows"]:
            got = row["map"]["candidates"]
            self.assertEqual([c["ordinal"] for c in got], [0, 2, 4, 5, 6])
            self.assertEqual(typed(got), typed([before[i] for i in (0, 2, 4, 5, 6)]))
        self.assertEqual(result["counters"]["map_candidate_occurrences"], 10)
        self.assertEqual(typed(cands), typed(before))
        conservation(self, result)

    def test_fixture_unsafe_and_duplicate_evidence_retained(self):
        row = join_case()["rows"][0]
        self.assertEqual([c["disposition"] for c in row["map"]["candidates"]],
                         ["retained", "discarded_duplicate_index", "unresolved_unsafe"])
        self.assertEqual(typed(row["map"]["candidates"]), typed(CASE["candidates"]))

    def test_candidate_type_and_order_errors(self):
        def mutate(fn):
            cands = [candidate(0, "Foo", 7), candidate(1, "Foo", 7, "discarded_not_found")]
            fn(cands)
            return cands
        cases = {
            "ordinal_bool": lambda c: c[0].update(ordinal=False),
            "ordinal_float": lambda c: c[1].update(ordinal=1.0),
            "ordinal_str": lambda c: c[1].update(ordinal="1"),
            "ordinal_negative": lambda c: c[0].update(ordinal=-1),
            "ordinal_duplicate": lambda c: c[1].update(ordinal=0),
            "ordinal_decreasing": lambda c: c.reverse(),
            "lookup_id_bool": lambda c: c[0]["index_lookup"].update(id=True),
            "lookup_id_float": lambda c: c[0]["index_lookup"].update(id=7.0),
            "lookup_extra": lambda c: c[0]["index_lookup"].update(extra=1),
            "config_line_bool": lambda c: c[0].update(config_line=True),
            "slot_float": lambda c: c[0].update(slot=0.0),
            "index_id_str": lambda c: c[0].update(index_id="7"),
            "unknown_disposition": lambda c: c[0].update(disposition="accepted"),
            "missing_conditional": lambda c: c[0].pop("slot"),
            "extra_key": lambda c: c[0].update(effective=True),
            "attempt_ordinal_bool": lambda c: c[0]["attempts"][0].update(ordinal=True),
            "attempt_empty_outcome": lambda c: c[0]["attempts"][0].update(outcome=""),
            "reasons_not_strings": lambda c: c[1].update(reasons=[1]),
            "cache_shape": lambda c: c[0].update(cache={"file": "x"}),
            "not_object": lambda c: c.append(["Foo"]),
        }
        s = Stream()
        s.static(b"Foo")
        P.join_events(s.events, reverse_rows(Foo=7), mutate(lambda c: None), [])
        for name, fn in cases.items():
            with self.subTest(name), self.assertRaises(P.ReferenceError):
                P.join_events(s.events, reverse_rows(Foo=7), mutate(fn), [])

    def test_reverse_errors(self):
        s = Stream()
        s.static(b"Foo")
        bad = [[{"id": 1, "name": "Foo"}, {"id": 2, "name": "Foo"}],
               [{"id": True, "name": "Foo"}], [{"id": 1.0, "name": "Foo"}],
               [{"id": -1, "name": "Foo"}], [{"id": 1, "name": "Foo", "x": 0}],
               [{"id": 1, "name": b"Foo"}], [["Foo", 1]], {"Foo": 1}]
        for reverse in bad:
            with self.subTest(reverse=reverse), self.assertRaises(P.ReferenceError):
                P.join_events(s.events, reverse, [], [])


# --- F04 ------------------------------------------------------------------------------

class F04MonsterHistory(unittest.TestCase):
    def test_all_references_across_visits_epochs_and_clear(self):
        refs = [reference(0, visit=4, epoch=0, id_text="001002"),
                reference(1, visit=4, epoch=0, id_text="1002"),
                reference(2, visit=5, epoch=1, id_text="1002"),  # after a Clear epoch
                reference(3, visit=6, epoch=1, id_text="01002")]
        refs[3]["projection_status"] = "gap"
        rows = [history(1002, refs, gate="in_range"), history(5000000, [reference(4)],
                                                              gate="out_of_range")]
        s = Stream()
        s.static(b"Foo", 1002)
        s.static(b"Foo", 1002)
        before = copy.deepcopy(rows)
        result = P.join_events(s.events, [], [], rows)
        for row in result["rows"]:
            self.assertEqual(typed(row["monster"]["history"]), typed(before[0]))
            self.assertEqual([d["id_text"] for d in row["monster"]["history"]["declarations"]],
                             ["001002", "1002", "1002", "01002"])
        self.assertEqual(result["counters"]["monster_declaration_occurrences"], 8)
        conservation(self, result)

    def test_sprite_zero_and_out_of_range_gate(self):
        row = join_case()["rows"][2]
        self.assertEqual(row["monster"]["sprite"], 0)
        self.assertEqual(row["monster"]["state"], "declared_history")
        self.assertEqual(row["monster"]["history"]["source_gate"], "out_of_range")
        self.assertEqual(row["map"]["index"]["state"], "missing")

    def test_map_and_monster_independent(self):
        s = Stream()
        s.static(b"Gone", 1002)
        s.static(b"Foo", 999)
        result = P.join_events(s.events, reverse_rows(Foo=7), [candidate(0, "Foo", 7)],
                               [history(1002, [reference(0)])])
        first, second = result["rows"]
        self.assertEqual(first["map"]["index"]["state"], "missing")
        self.assertEqual(first["monster"]["state"], "declared_history")
        self.assertEqual(second["map"]["candidate_state"], "present")
        self.assertEqual(second["monster"],
                         {"sprite": 999, "state": "no_declared_history", "history": None})

    def test_history_errors(self):
        def rows(fn):
            value = [history(0, [reference(0)]), history(1002, [reference(1), reference(2)])]
            fn(value)
            return value
        cases = {
            "duplicate_id": lambda h: h[1].update(id=0, id_decimal="0"),
            "decreasing": lambda h: h.reverse(),
            "count_mismatch": lambda h: h[1].update(declaration_count=1),
            "count_bool": lambda h: h[0].update(declaration_count=True),
            "id_bool": lambda h: h[0].update(id=False),
            "id_float": lambda h: h[1].update(id=1002.0),
            "id_decimal_leading_zero": lambda h: h[1].update(id_decimal="01002"),
            "id_decimal_int": lambda h: h[1].update(id_decimal=1002),
            "unknown_gate": lambda h: h[0].update(source_gate="maybe"),
            "missing_key": lambda h: h[0].pop("meaning"),
            "extra_key": lambda h: h[0].update(effective=True),
            "ref_ordinal_bool": lambda h: h[1]["declarations"][0].update(visit=True),
            "ref_ordinal_float": lambda h: h[1]["declarations"][0].update(epoch=0.0),
            "ref_span_float": lambda h: h[1]["declarations"][0].update(id_byte_span=[11.0, 15]),
            "ref_span_reversed": lambda h: h[1]["declarations"][0].update(row_byte_span=[20, 10]),
            "ref_sha_upper": lambda h: h[1]["declarations"][0].update(file_sha256="A" * 64),
            "ref_status": lambda h: h[1]["declarations"][0].update(projection_status="ok"),
            "ref_missing": lambda h: h[1]["declarations"][0].pop("visit"),
            "ref_extra": lambda h: h[1]["declarations"][0].update(effective=True),
        }
        s = Stream()
        s.static(b"Foo", 1002)
        P.join_events(s.events, [], [], rows(lambda h: None))
        for name, fn in cases.items():
            with self.subTest(name), self.assertRaises(P.ReferenceError):
                P.join_events(s.events, [], [], rows(fn))


# --- F05 ------------------------------------------------------------------------------

class F05Unjoined(unittest.TestCase):
    def test_reasons_and_no_partial_recovery(self):
        s = Stream()
        gap = s.gap(b"Foo")
        s.opaque()
        s.simple("line_comment", b"//Foo\tmonster\tN\t1002,1\n")
        s.simple("block_comment", b"/*Foo\tmonster\tN\t1002,1*/")
        s.simple("whitespace", b" \n")
        s.suffix()
        s.static(b"Foo", 1002, source=1)
        reverse, cands = reverse_rows(Foo=7), [candidate(0, "Foo", 7)]
        hist = [history(1002, [reference(0)])]
        result = P.join_events(s.events, reverse, cands, hist)
        reasons = [r["unjoined"] for r in result["rows"]]
        self.assertEqual(typed(reasons), typed([
            {"code": "static_projection_gap", "detail": gap["detail"]["gaps"]},
            {"code": "opaque_script", "detail": None},
            {"code": "not_static", "detail": None},
            {"code": "not_static", "detail": None},
            {"code": "not_static", "detail": None},
            {"code": "uncertified_suffix",
             "detail": {"fault_offset": s.events[5]["span"][0],
                        "reason": "unsupported_construct"}},
            None]))
        for row in result["rows"][:6]:
            self.assertIsNone(row["map"])
            self.assertIsNone(row["monster"])
        self.assertEqual(result["counters"]["map_candidate_occurrences"], 1)
        self.assertEqual([r["raw"]["kind"] for r in result["rows"]],
                         ["static", "opaque", "line_comment", "block_comment", "whitespace",
                          "suffix", "static"])
        self.assertEqual(len(result["rows"]), len(s.events))
        conservation(self, result)

    def test_malformed_event_shapes_are_fatal(self):
        def stream():
            s = Stream()
            s.static(b"Foo", 1002)
            s.gap()
            s.opaque()
            s.simple()
            s.suffix()
            return s.events

        def values(e):
            return e[0]["detail"]["values"]
        cases = {
            "unknown_kind": lambda e: e[3].update(kind="static_like"),
            "kind_not_str": lambda e: e[3].update(kind=1),
            "supported_null_values": lambda e: e[0]["detail"].update(values=None),
            "supported_with_gaps": lambda e: e[0]["detail"].update(gaps=[{"code": "x",
                                                                          "span": [0, 0]}]),
            "gap_with_values": lambda e: e[1]["detail"].update(values=values(e)),
            "gap_without_gaps": lambda e: e[1]["detail"].update(gaps=[]),
            "unknown_projection_state": lambda e: e[0]["detail"].update(projection_state="ok"),
            "detail_extra": lambda e: e[0]["detail"].update(extra=1),
            "opaque_detail_null": lambda e: e[2].update(detail=None),
            "whitespace_detail": lambda e: e[3].update(detail={}),
            "suffix_detail_shape": lambda e: e[4].update(detail={"reason": "x"}),
            "map_origin_default": lambda e: values(e)["map"].update(origin="default"),
            "map_span_null": lambda e: values(e)["map"].update(span=None),
            "map_span_length": lambda e: values(e)["map"]["span"].__setitem__(1, 2),
            "map_outside_event": lambda e: values(e)["map"].update(span=[-1, 2]),
            "map_upper_hex": lambda e: values(e)["map"].update(value="466F6F"),
            "map_value_null": lambda e: values(e)["map"].update(value=None),
            "sprite_bool": lambda e: values(e)["sprite"].update(value=True),
            "sprite_float": lambda e: values(e)["sprite"].update(value=1002.0),
            "sprite_str": lambda e: values(e)["sprite"].update(value="1002"),
            "sprite_negative": lambda e: values(e)["sprite"].update(value=-1),
            "sprite_too_large": lambda e: values(e)["sprite"].update(value=2147483648),
            "sprite_span_length": lambda e: values(e)["sprite"]["span"].__setitem__(1, 99),
            "slot_extra_key": lambda e: values(e)["sprite"].update(extra=1),
            "missing_map_slot": lambda e: values(e).pop("map"),
            "event_extra_key": lambda e: e[0].update(extra=1),
            "schema_bool": lambda e: e[0].update(schema=True),
            "sha_upper": lambda e: e[0].update(sha256=e[0]["sha256"].upper()),
        }
        P.join_events(stream(), [], [], [])
        for name, fn in cases.items():
            events = stream()
            fn(events)
            with self.subTest(name), self.assertRaises(P.ReferenceError):
                P.join_events(events, [], [], [])

    def test_ordering_rules(self):
        def stream():
            s = Stream()
            s.simple(source=0)
            s.simple(source=0)
            s.simple(source=1)
            return s.events
        P.join_events(stream(), [], [], [])
        only_second = Stream()
        only_second.simple(source=1)
        self.assertEqual(len(P.join_events(only_second.events, [], [], [])["rows"]), 1)
        cases = {
            "index_gap": lambda e: e[1].update(event_index=2),
            "index_from_one": lambda e: [x.update(event_index=x["event_index"] + 1) for x in e],
            "index_bool": lambda e: e[0].update(event_index=False),
            "source_two": lambda e: e[2].update(source_index=2),
            "source_bool": lambda e: e[0].update(source_index=False),
            "source_decreasing": lambda e: e[1].update(source_index=1) or e[2].update(source_index=0),
            "not_adjacent": lambda e: e[1].update(span=[2, 3]),
            "zero_length": lambda e: e[1].update(span=[1, 1]),
            "second_source_not_zero": lambda e: e[2].update(span=[1, 2]),
            "span_float": lambda e: e[0].update(span=[0.0, 1]),
            "span_three": lambda e: e[0].update(span=[0, 1, 2]),
        }
        for name, fn in cases.items():
            events = stream()
            fn(events)
            with self.subTest(name), self.assertRaises(P.ReferenceError):
                P.join_events(events, [], [], [])

    def test_no_event_after_suffix_in_same_source(self):
        s = Stream()
        s.suffix()
        s.simple(source=1)
        P.join_events(s.events, [], [], [])
        s.simple(source=1)
        P.join_events(s.events, [], [], [])
        bad = Stream()
        bad.suffix()
        bad.simple(source=0)
        with self.assertRaises(P.ReferenceError):
            P.join_events(bad.events, [], [], [])


# --- F06 ------------------------------------------------------------------------------

def lowered(**changes):
    limits = dict(P.LIMITS)
    limits.update(changes)
    return limits


class F06BoundsCountersJson(unittest.TestCase):
    def test_bounds_at_and_over(self):
        size = sum(len(P.render(r)) for r in CASE["expected"]["rows"])
        refs = sum(len(h["declarations"]) for h in CASE["histories"])
        at = {"events": len(CASE["events"]), "map_reverse_rows": len(CASE["reverse"]),
              "map_candidates": len(CASE["candidates"]), "history_rows": len(CASE["histories"]),
              "history_references": refs, "jsonl_bytes": size}
        result = join_case(limits=lowered(**at))
        self.assertEqual(typed(result), typed(CASE["expected"]))
        for key, value in at.items():
            with self.subTest(key), self.assertRaises(P.ReferenceError):
                join_case(limits=lowered(**{key: value - 1}))
        # Publication-only keys are validated but have no core accounting.
        join_case(limits=lowered(completion_bytes=0, manifest_bytes=0, input_total_bytes=0))

    def test_limit_mapping_validation(self):
        bad = [{}, {k: v for k, v in P.LIMITS.items() if k != "events"},
               lowered(extra=1), lowered(events=8193), lowered(events=-1),
               lowered(events=True), lowered(events=10.0), lowered(events="1"), [1], 0]
        for limits in bad:
            with self.subTest(limits=limits), self.assertRaises(P.ReferenceError):
                P.join_events([], [], [], [], limits)

    def test_empty_inputs(self):
        zero = dict.fromkeys(P.LIMITS, 0)
        for limits in (None, zero):
            result = P.join_events([], [], [], [], limits)
            self.assertEqual(typed(result), typed({"rows": [],
                                                   "counters": dict.fromkeys(P.COUNTER_KEYS, 0)}))
        with self.assertRaises(P.ReferenceError):
            P.join_events([], [{"id": 1, "name": "A"}], [], [], zero)
        with self.assertRaises(P.ReferenceError):
            P.join_events([], [], [], [history(1, [])], zero)

    def test_no_silent_suffix_or_truncation(self):
        s = Stream()
        for _ in range(5):
            s.simple()
        with self.assertRaises(P.ReferenceError):
            P.join_events(s.events, [], [], [], lowered(events=4))
        one = len(P.render(P.join_events(s.events[:1], [], [], [])["rows"][0]))
        with self.assertRaises(P.ReferenceError):
            P.join_events(s.events, [], [], [], lowered(jsonl_bytes=one * 5 - 1))
        self.assertEqual(len(P.join_events(s.events, [], [], [],
                                           lowered(jsonl_bytes=one * 5))["rows"]), 5)

    def test_counter_conservation_mixed(self):
        s = Stream()
        s.static(b"Foo", 1)
        s.static(b"Zero", 2)
        s.static(b"Empty", 1)
        s.static(b"None", 3)
        s.gap()
        s.opaque()
        s.simple()
        s.suffix()
        result = P.join_events(s.events, reverse_rows(Foo=7, Zero=0, Empty=9),
                               [candidate(0, "Foo", 7), candidate(1, "Foo", 7)],
                               [history(1, [reference(0), reference(1)])])
        conservation(self, result)
        self.assertEqual(result["counters"]["map_candidate_occurrences"], 2)
        self.assertEqual(result["counters"]["monster_declaration_occurrences"], 4)

    def test_strict_json(self):
        good = P.strict_json(b'{"a":[1,2.5,true,null],"t":1.5e3}', "x")
        self.assertIs(type(good["a"][0]), int)
        self.assertIs(type(good["a"][2]), bool)
        for data in (b'{"a":1,"a":2}', b'{"a":{"b":1,"b":1}}', b'[NaN]', b'[Infinity]',
                     b'[-Infinity]', b'[1e309]', b'{"a":[{"b":-1e400}]}', b'{"a":1', b'\xff',
                     b''):
            with self.subTest(data=data), self.assertRaises(P.ReferenceError):
                P.strict_json(data, "x")
        self.assertEqual(P.strict_json(b"[1e-400]", "x"), [0.0])

    def test_jsonl_helpers(self):
        self.assertEqual(P.jsonl_count(b"{}\n{}\n", "x"), 2)
        for data in (b"{}", b"{}\n\n", b"\n"):
            with self.assertRaises(P.ReferenceError):
                P.jsonl_count(data, "x")
        with self.assertRaises(P.ReferenceError):
            P.strict_jsonl(b"[]\n", "x")


# --- Publication helpers --------------------------------------------------------------

def private_tmp():
    return os.path.realpath(tempfile.mkdtemp(prefix="t06ref-"))


def unit_built():
    result = join_case()
    stream = b"".join(P.render(r) for r in result["rows"])
    manifest = {"output": {"file": P.OUTPUT_ROWS, "bytes": len(stream), "sha256": sha(stream),
                           "rows": len(result["rows"])}, "unit": True}
    return {"stream": stream, "manifest": manifest, "manifest_bytes": P.render(manifest)}


class Recorder:
    """Track descriptors opened by the producer so liveness is checked before cleanup."""

    def __init__(self):
        self.fds = []

    def open(self, *args, **kwargs):
        fd = REAL["open"](*args, **kwargs)
        self.fds.append(fd)
        return fd


REAL = {"open": os.open, "read": os.read, "write": os.write, "fsync": os.fsync,
        "close": os.close, "mkdir": os.mkdir, "unlink": os.unlink}


def fd_closed(fd):
    try:
        os.fstat(fd)
    except OSError as exc:
        return exc.errno == errno.EBADF
    return False


class TempCase(unittest.TestCase):
    def setUp(self):
        self.tmp = private_tmp()
        self.rec = Recorder()
        self.saved = {name: getattr(P, "_os_" + name) for name in REAL}
        P._os_open = self.rec.open

    def tearDown(self):
        for name, fn in self.saved.items():
            setattr(P, "_os_" + name, fn)
        for root, dirs, _ in os.walk(self.tmp):
            for d in dirs:
                os.chmod(os.path.join(root, d), 0o700)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def assert_owned_closed(self, keep=()):
        """Every producer-opened descriptor is released (observed before fixture cleanup)."""
        for fd in self.rec.fds:
            if fd in keep:
                continue
            self.assertTrue(fd_closed(fd), f"descriptor {fd} still open")

    def target(self, name="out"):
        return os.path.join(self.tmp, name)

    def assert_failed_publication(self, target):
        self.assertFalse(os.path.lexists(os.path.join(target, P.OUTPUT_COMPLETE)))
        self.assertFalse(os.path.lexists(os.path.join(target, P.OUTPUT_MANIFEST)))


# --- F09 ------------------------------------------------------------------------------

class F09Publication(TempCase):
    def test_success_modes_and_entries(self):
        built, target = unit_built(), self.target()
        P.publish(target, built)
        self.assert_owned_closed()
        self.assertEqual(stat.S_IMODE(os.lstat(target).st_mode), 0o700)
        self.assertEqual(sorted(os.listdir(target)),
                         sorted([P.OUTPUT_ROWS, P.OUTPUT_MANIFEST, P.OUTPUT_COMPLETE]))
        for name in os.listdir(target):
            info = os.lstat(os.path.join(target, name))
            self.assertTrue(stat.S_ISREG(info.st_mode))
            self.assertEqual(stat.S_IMODE(info.st_mode), 0o600)
        marker = strict_load(Path(target, P.OUTPUT_COMPLETE).read_bytes())
        manifest_bytes = Path(target, P.OUTPUT_MANIFEST).read_bytes()
        self.assertEqual(marker, {"schema": 1, "task": P.TASK, "profile": P.PROFILE_NAME,
                                  "state": "complete",
                                  "manifest": {"bytes": len(manifest_bytes),
                                               "sha256": sha(manifest_bytes)},
                                  "output": built["manifest"]["output"]})
        self.assertEqual(Path(target, P.OUTPUT_ROWS).read_bytes(), built["stream"])

    def test_short_writes_complete(self):
        P._os_write = lambda fd, data: REAL["write"](fd, bytes(data[:7]))
        P.publish(self.target(), unit_built())
        self.assertEqual(Path(self.target(), P.OUTPUT_ROWS).read_bytes(), unit_built()["stream"])
        self.assert_owned_closed()

    def fail(self, expect=None, keep=()):
        target = self.target()
        with self.assertRaises(P.ReferenceError) as ctx:
            P.publish(target, unit_built())
        self.assert_owned_closed(keep)
        self.assert_failed_publication(target)
        if expect:
            self.assertIn(expect, str(ctx.exception))
        return target, str(ctx.exception)

    def test_zero_write(self):
        P._os_write = lambda fd, data: 0
        self.fail("no progress")

    def test_write_error(self):
        def write(fd, data):
            raise OSError(errno.EIO, "injected")
        P._os_write = write
        self.fail("write/fsync failed")

    def test_file_fsync_failure(self):
        def fsync(fd):
            if stat.S_ISREG(os.fstat(fd).st_mode):
                raise OSError(errno.EIO, "injected")
            return REAL["fsync"](fd)
        P._os_fsync = fsync
        self.fail("write/fsync failed")

    def test_directory_fsync_failure(self):
        def fsync(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                raise OSError(errno.EIO, "injected")
            return REAL["fsync"](fd)
        P._os_fsync = fsync
        target, _ = self.fail()
        self.assertTrue(os.path.exists(os.path.join(target, P.OUTPUT_ROWS)))

    def test_marker_open_failure(self):
        def opener(name, flags, *args, **kwargs):
            if name == P.OUTPUT_COMPLETE:
                raise OSError(errno.EACCES, "injected")
            return self.rec.open(name, flags, *args, **kwargs)
        P._os_open = opener
        self.fail("cannot create exclusively")

    def test_readback_corruption(self):
        def read(fd, n):
            data = REAL["read"](fd, n)
            return data[:-1] + b"X" if data else data
        P._os_read = read
        self.fail("differs")

    def test_readback_mode_change(self):
        def fsync(fd):
            REAL["fsync"](fd)
            if stat.S_ISREG(os.fstat(fd).st_mode):
                os.fchmod(fd, 0o644)
        P._os_fsync = fsync
        self.fail("not mode 0600")

    def close_fault(self, before_real, match):
        state = {"done": False}

        def close(fd):
            info = os.fstat(fd)
            if not state["done"] and match(info):
                state["done"] = True
                if not before_real:
                    REAL["close"](fd)
                raise OSError(errno.EIO, "injected close")
            return REAL["close"](fd)
        P._os_close = close
        return state

    def test_file_close_before_and_after_real_close(self):
        for before in (True, False):
            with self.subTest(before_real=before):
                self.tmp2 = self.tmp
                self.close_fault(before, lambda i: stat.S_ISREG(i.st_mode))
                target = os.path.join(self.tmp, f"out-{before}")
                with self.assertRaises(P.ReferenceError) as ctx:
                    P.publish(target, unit_built())
                self.assert_owned_closed()
                self.assert_failed_publication(target)
                self.assertIn("close failed", str(ctx.exception))
                self.assertIn("descriptor release observed" if not before else
                              "descriptor release observed", str(ctx.exception))

    def test_final_directory_close_before_and_after_real_close(self):
        for before in (True, False):
            with self.subTest(before_real=before):
                target = os.path.join(self.tmp, f"dir-{before}")
                state = {"armed": True}

                def close(fd, before=before):
                    info = os.fstat(fd)
                    if state["armed"] and stat.S_ISDIR(info.st_mode) and \
                            os.path.exists(os.path.join(target, P.OUTPUT_COMPLETE)):
                        state["armed"] = False
                        if not before:
                            REAL["close"](fd)
                        raise OSError(errno.EIO, "injected dir close")
                    return REAL["close"](fd)
                P._os_close = close
                with self.assertRaises(P.ReferenceError) as ctx:
                    P.publish(target, unit_built())
                self.assert_owned_closed()
                self.assert_failed_publication(target)
                self.assertIn("output directory close failed", str(ctx.exception))
                P._os_close = REAL["close"]

    def test_after_real_close_different_inode_reuse_untouched(self):
        foreign_path = os.path.join(self.tmp, "foreign")
        Path(foreign_path).write_bytes(b"foreign bytes")
        held = {}

        def close(fd):
            info = os.fstat(fd)
            if not held and stat.S_ISREG(info.st_mode):
                REAL["close"](fd)
                reused = os.open(foreign_path, os.O_RDONLY)
                held["fd"] = reused
                raise OSError(errno.EIO, "injected close after reuse")
            return REAL["close"](fd)
        P._os_close = close
        target = self.target()
        try:
            with self.assertRaises(P.ReferenceError) as ctx:
                P.publish(target, unit_built())
            fd = held["fd"]
            self.assertFalse(fd_closed(fd))
            self.assertEqual(os.pread(fd, 100, 0), b"foreign bytes")
            self.assert_owned_closed(keep=(fd,))
            self.assert_failed_publication(target)
            self.assertIn("foreign descriptor left untouched", str(ctx.exception))
        finally:
            if "fd" in held:
                os.close(held["fd"])

    def test_foreign_replacement_untouched_on_late_failure(self):
        target = self.target()

        def fsync(fd):
            REAL["fsync"](fd)
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                manifest = os.path.join(target, P.OUTPUT_MANIFEST)
                os.unlink(manifest)
                Path(manifest).write_bytes(b"foreign")
                raise OSError(errno.EIO, "injected")
        P._os_fsync = fsync
        with self.assertRaises(P.ReferenceError) as ctx:
            P.publish(target, unit_built())
        self.assert_owned_closed()
        self.assertFalse(os.path.lexists(os.path.join(target, P.OUTPUT_COMPLETE)))
        self.assertEqual(Path(target, P.OUTPUT_MANIFEST).read_bytes(), b"foreign")
        self.assertIn("foreign file, left untouched", str(ctx.exception))

    def test_unexpected_entry_refused(self):
        target = self.target()

        def fsync(fd):
            REAL["fsync"](fd)
            if os.path.exists(os.path.join(target, P.OUTPUT_COMPLETE)) and \
                    not os.path.exists(os.path.join(target, "intruder")):
                Path(target, "intruder").write_bytes(b"x")
        P._os_fsync = fsync
        with self.assertRaises(P.ReferenceError):
            P.publish(target, unit_built())
        self.assert_failed_publication(target)
        self.assertTrue(os.path.exists(os.path.join(target, "intruder")))

    def test_existing_output_and_links_untouched(self):
        existing = self.target("exists")
        os.mkdir(existing, 0o700)
        Path(existing, "sentinel").write_bytes(b"keep")
        before = os.lstat(os.path.join(existing, "sentinel"))
        link = self.target("link")
        os.symlink(existing, link)
        dangling = self.target("dangling")
        os.symlink(os.path.join(self.tmp, "nowhere"), dangling)
        for path in (existing, link, dangling):
            with self.subTest(path=path), self.assertRaises(P.ReferenceError):
                P.output_target(path)
        with self.assertRaises(P.ReferenceError):
            P.publish(existing, unit_built())
        after = os.lstat(os.path.join(existing, "sentinel"))
        self.assertEqual((before.st_ino, before.st_mode, before.st_size),
                         (after.st_ino, after.st_mode, after.st_size))
        self.assertEqual(Path(existing, "sentinel").read_bytes(), b"keep")
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "nowhere")))

    def test_output_parent_and_input_collision(self):
        with self.assertRaises(P.ReferenceError):
            P.output_target("relative/out")
        shared = self.target("shared")
        os.mkdir(shared, 0o770)
        os.chmod(shared, 0o770)
        with self.assertRaises(P.ReferenceError):
            P.output_target(os.path.join(shared, "out"))
        root = self.target("inputs")
        os.mkdir(root, 0o700)
        with self.assertRaises(P.ReferenceError):
            P.output_target(os.path.join(root, "out"), (root,))
        P.output_target(self.target("fresh"), (root,))

    def test_fifo_and_special_reads_do_not_hang(self):
        fifo = self.target("fifo")
        os.mkfifo(fifo, 0o600)
        with self.assertRaises(P.ReferenceError) as ctx:
            P.read_regular(fifo, 100, "fifo")
        self.assertIn("not a regular file", str(ctx.exception))
        self.assert_owned_closed()
        with self.assertRaises(P.ReferenceError):
            P.read_regular(self.tmp, 100, "directory")
        self.assert_owned_closed()

    def test_read_close_failures_are_fatal(self):
        path = self.target("file")
        Path(path).write_bytes(b"data")
        for before in (True, False):
            with self.subTest(before_real=before):
                self.close_fault(before, lambda i: stat.S_ISREG(i.st_mode))
                with self.assertRaises(P.ReferenceError) as ctx:
                    P.read_regular(path, 100, "unit read")
                self.assertIn("close failed", str(ctx.exception))
                self.assertIn("descriptor release observed", str(ctx.exception))
                self.assert_owned_closed()
                P._os_close = REAL["close"]

    def test_read_and_close_both_fail(self):
        path = self.target("file")
        Path(path).write_bytes(b"data")

        def read(fd, n):
            raise OSError(errno.EIO, "injected read")
        P._os_read = read
        self.close_fault(True, lambda i: stat.S_ISREG(i.st_mode))
        with self.assertRaises(P.ReferenceError) as ctx:
            P.read_regular(path, 100, "unit read")
        message = str(ctx.exception)
        self.assertIn("read failed", message)
        self.assertIn("cleanup close also failed", message)
        self.assert_owned_closed()


# --- F08 (structural; no frozen input needed) ------------------------------------------

def fake_bundle(root, bundle, skip=(), extra=()):
    os.mkdir(root, 0o700)
    for name in P.PINS[bundle]:
        if name not in skip:
            Path(root, name).write_bytes(b"{}")
    for name in extra:
        Path(root, name).write_bytes(b"{}")
    return root


class F08Structural(TempCase):
    def test_missing_extra_link_special_and_relative(self):
        cases = {}
        cases["missing"] = fake_bundle(self.target("missing"), "map", skip=(P.MAP_COMPLETE,))
        cases["extra"] = fake_bundle(self.target("extra"), "map", extra=("other.json",))
        link_root = fake_bundle(self.target("linkfile"), "map", skip=(P.MAP_COMPLETE,))
        os.symlink(os.path.join(link_root, P.MAP_MANIFEST), os.path.join(link_root, P.MAP_COMPLETE))
        cases["linked_artifact"] = link_root
        fifo_root = fake_bundle(self.target("fifo"), "map", skip=(P.MAP_COMPLETE,))
        os.mkfifo(os.path.join(fifo_root, P.MAP_COMPLETE), 0o600)
        cases["special_artifact"] = fifo_root
        sub_root = fake_bundle(self.target("subdir"), "map", skip=(P.MAP_COMPLETE,))
        os.mkdir(os.path.join(sub_root, P.MAP_COMPLETE))
        cases["directory_artifact"] = sub_root
        real = fake_bundle(self.target("real"), "map")
        os.symlink(real, self.target("rootlink"))
        cases["linked_root"] = self.target("rootlink")
        cases["wrong_bytes"] = real
        cases["relative"] = os.path.relpath(real)
        cases["absent"] = self.target("absent")
        for name, root in cases.items():
            with self.subTest(name), self.assertRaises(P.ReferenceError) as ctx:
                P.read_bundle(root, "map")
            self.assert_owned_closed()
            if name == "wrong_bytes":
                self.assertIn("is not the pinned", str(ctx.exception))

    def test_cli_refuses_relative_and_has_no_bypass(self):
        source = (HERE / "static_spawn_references.py").read_text()
        self.assertNotIn("os.environ", source)
        self.assertNotIn("getenv", source)
        self.assertNotIn("subprocess", source)
        self.assertNotIn("import static_spawn_pilot", source)
        self.assertEqual(P.main(["--raw-dir", "raw", "--map-dir", "/m", "--monster-dir", "/x",
                                 "--output", self.target("o")]), 2)
        self.assertFalse(os.path.exists(self.target("o")))
        proc = subprocess.run([sys.executable, "-I", "-B", str(HERE / "static_spawn_references.py"),
                               "--help"], capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0)
        for flag in ("--limit", "--pin", "--config", "--force", "--overwrite"):
            self.assertNotIn(flag, proc.stdout)


# --- Real frozen inputs ------------------------------------------------------------------

def real_datas():
    return {bundle: {name: Path(FROZEN, bundle, name).read_bytes() for name in P.PINS[bundle]}
            for bundle in P.BUNDLES}


def run_cli(raw, map_dir, monster, output):
    return subprocess.run([sys.executable, "-I", "-B", str(HERE / "static_spawn_references.py"),
                           "--raw-dir", raw, "--map-dir", map_dir, "--monster-dir", monster,
                           "--output", output], capture_output=True, text=True, timeout=600)


def independent_rows(datas):
    """Recompute every expected row from the raw artifacts without producer functions."""
    events = [json.loads(l) for l in datas["raw"][P.RAW_EVENTS].splitlines()]
    mapm = json.loads(datas["map"][P.MAP_MANIFEST])
    reverse = {r["name"]: r["id"] for r in mapm["index"]["state"]["reverse"]}
    hist = {}
    for line in datas["monster"][P.MON_HISTORY].splitlines():
        h = json.loads(line)
        hist[h["id"]] = h
    rows = []
    for e in events:
        row = {"schema": 1, "source_index": e["source_index"], "event_index": e["event_index"],
               "raw": {"kind": e["kind"], "span": e["span"], "sha256": e["sha256"]},
               "map": None, "monster": None, "unjoined": None}
        if e["kind"] == "static" and e["detail"]["projection_state"] == "supported":
            raw_hex = e["detail"]["values"]["map"]["value"]
            name = bytes.fromhex(raw_hex).decode()
            if name.lower().endswith(".gat"):
                name = name[:-4]
            idx = reverse.get(name)
            if idx is None:
                index, cs, cands = {"state": "missing", "id": None}, "not_applicable", []
            elif idx == 0:
                index, cs, cands = {"state": "zero", "id": 0}, "not_applicable", []
            else:
                cands = [c for c in mapm["candidates"] if c["index_lookup"]["id"] == idx]
                index, cs = {"state": "nonzero", "id": idx}, ("present" if cands else "none")
            row["map"] = {"raw_hex": raw_hex, "normalised": name, "index": index,
                          "candidate_state": cs, "candidates": cands}
            sprite = e["detail"]["values"]["sprite"]["value"]
            h = hist.get(sprite)
            row["monster"] = {"sprite": sprite,
                              "state": "declared_history" if h else "no_declared_history",
                              "history": h}
        elif e["kind"] == "opaque":
            row["unjoined"] = {"code": "opaque_script", "detail": None}
        else:
            row["unjoined"] = {"code": "not_static", "detail": None}
        rows.append(row)
    return rows


@unittest.skipUnless(FROZEN, "STATIC_SPAWN_REFERENCE_FROZEN_ROOT not set")
class F07RealInputs(TempCase):
    def roots(self, base=None):
        base = base or FROZEN
        return [os.path.join(base, b) for b in P.BUNDLES]

    def test_production_cli_publication(self):
        target = self.target()
        proc = run_cli(*self.roots(), target)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn(FROZEN, proc.stdout + proc.stderr)
        self.assertEqual(stat.S_IMODE(os.lstat(target).st_mode), 0o700)
        names = sorted(os.listdir(target))
        self.assertEqual(names, sorted([P.OUTPUT_ROWS, P.OUTPUT_MANIFEST, P.OUTPUT_COMPLETE]))
        for name in names:
            info = os.lstat(os.path.join(target, name))
            self.assertTrue(stat.S_ISREG(info.st_mode))
            self.assertEqual(stat.S_IMODE(info.st_mode), 0o600)
        stream = Path(target, P.OUTPUT_ROWS).read_bytes()
        manifest_bytes = Path(target, P.OUTPUT_MANIFEST).read_bytes()
        manifest = strict_load(manifest_bytes)
        marker = strict_load(Path(target, P.OUTPUT_COMPLETE).read_bytes())
        datas = real_datas()
        rows = [strict_load(l) for l in stream.splitlines()]
        self.assertEqual(len(rows), 354)
        self.assertEqual(stream, b"".join(P.render(r) for r in rows))
        self.assertEqual(manifest_bytes, P.render(manifest))
        self.assertEqual(typed(rows), typed(independent_rows(datas)))
        result = {"rows": rows, "counters": manifest["counters"]}
        conservation(self, result)
        producer = (HERE / "static_spawn_references.py").read_bytes()
        raw_manifest = json.loads(datas["raw"][P.RAW_MANIFEST])
        expected_manifest = {
            "schema": 1, "task": "T06.002.003.005.002",
            "profile": "static-spawn-declared-reference-v1", "state": "complete",
            "producer": {"file": "tools/renewal/static_spawn_references.py",
                         "bytes": len(producer), "sha256": sha(producer)},
            "dependencies": [],
            "inputs": {f"{b}/{n}": {"bytes": len(d), "sha256": sha(d)}
                       for b in datas for n, d in datas[b].items()},
            "provenance": {
                "rathena_revision": "0693b8c69911d5ca42269684aa036b67d67f4d3e",
                "snapshot_manifest_sha256":
                    "79ee4eff2ed1621aa3be6247d0aedefc5f44abd65025617de652f41644c1dbd0",
                "selection_manifest_sha256":
                    "d62e31fd601a879a9020eb0cbc79273cdaa38f11d6119af056b36727631aec9a",
                "raw_producer_sha256":
                    "14690614311ee805c3aa2906a15a77efe6885d51bf68a9cea50bc6bd5b581cbd",
                "map_producer_sha256":
                    "996a0cb8c6001150931b4cfa7e4e098fc4f2b7f10551b7ed428b98d51f08b56d",
                "monster_producer_sha256":
                    "45272a3660ff459a56b8f0ea7d30b0facef0e9f83fed13e981655dcc758e64d9"},
            "raw_scope": {"sources": raw_manifest["sources"],
                          "unscanned_selection_indices":
                              raw_manifest["unscanned_selection_indices"]},
            "output": {"file": "static-spawn-references.jsonl", "bytes": len(stream),
                       "sha256": sha(stream), "rows": 354},
            "counters": manifest["counters"], "limits": P.LIMITS,
            "claims": {"map_cells": "not_checked", "native_membership": "not_checked",
                       "effective_population": "not_checked", "world_coverage": "not_checked",
                       "localisation": "not_checked", "story_solo": "not_checked"}}
        self.assertEqual(typed(manifest), typed(expected_manifest))
        self.assertEqual(sum(v["bytes"] for v in manifest["inputs"].values()), 45347934)
        for key, value in manifest["inputs"].items():
            bundle, name = key.split("/")
            self.assertEqual(value, P.PINS[bundle][name])
        self.assertEqual(len(manifest["raw_scope"]["unscanned_selection_indices"]), 837)
        self.assertEqual(typed(marker), typed({
            "schema": 1, "task": "T06.002.003.005.002",
            "profile": "static-spawn-declared-reference-v1", "state": "complete",
            "manifest": {"bytes": len(manifest_bytes), "sha256": sha(manifest_bytes)},
            "output": manifest["output"]}))
        self.assertEqual(manifest["counters"]["events"], 354)
        self.assertEqual(manifest["counters"]["static_supported"], 192)
        text = (stream + manifest_bytes).decode("ascii")
        self.assertNotIn(FROZEN, text)
        self.assertNotIn(os.path.expanduser("~"), text)
        again = self.target("again")
        self.assertEqual(run_cli(*self.roots(), again).returncode, 0)
        for name in names:
            self.assertEqual(Path(target, name).read_bytes(), Path(again, name).read_bytes())

    def test_late_failure_on_real_run_leaves_no_completion(self):
        def fsync(fd):
            REAL["fsync"](fd)
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                raise OSError(errno.EIO, "injected")
        P._os_fsync = fsync
        target = self.target()
        with self.assertRaises(P.ReferenceError):
            P.run(*self.roots(), target)
        self.assert_owned_closed()
        self.assert_failed_publication(target)


@unittest.skipUnless(FROZEN, "STATIC_SPAWN_REFERENCE_FROZEN_ROOT not set")
class F08RealAdmission(TempCase):
    @classmethod
    def setUpClass(cls):
        cls.copy_root = private_tmp()
        for bundle in P.BUNDLES:
            os.mkdir(os.path.join(cls.copy_root, bundle), 0o700)
            for name in P.PINS[bundle]:
                dest = os.path.join(cls.copy_root, bundle, name)
                shutil.copyfile(os.path.join(FROZEN, bundle, name), dest)
                os.chmod(dest, 0o600)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.copy_root, ignore_errors=True)

    def roots(self):
        return [os.path.join(self.copy_root, b) for b in P.BUNDLES]

    def mutate_one_byte(self, bundle, name, offset):
        path = os.path.join(self.copy_root, bundle, name)
        data = bytearray(Path(path).read_bytes())
        original = data[offset]
        data[offset] = ord("0") if original != ord("0") else ord("1")
        Path(path).write_bytes(bytes(data))
        return lambda: Path(path).write_bytes(bytes(data[:offset]) + bytes([original])
                                              + bytes(data[offset + 1:]))

    def test_copy_is_admitted(self):
        context = P.admit(*self.roots())
        self.assertEqual(len(context["events"]), 354)

    def test_same_length_mutation_in_each_bundle(self):
        for bundle, name in (("raw", P.RAW_EVENTS), ("raw", P.RAW_COMPLETE),
                             ("map", P.MAP_MANIFEST), ("monster", P.MON_DECLARATIONS),
                             ("monster", P.MON_HISTORY)):
            size = P.PINS[bundle][name]["bytes"]
            restore = self.mutate_one_byte(bundle, name, size // 2)
            try:
                target = self.target(f"out-{bundle}-{name}")
                proc = run_cli(*self.roots(), target)
                with self.subTest(bundle=bundle, name=name):
                    self.assertEqual(proc.returncode, 2)
                    self.assertIn("is not the pinned", proc.stderr)
                    self.assertFalse(os.path.exists(target))
            finally:
                restore()
        self.assertEqual(len(P.admit(*self.roots())["events"]), 354)

    def test_cli_root_and_output_refusals(self):
        raw, map_dir, monster = self.roots()
        existing = self.target("existing")
        os.mkdir(existing, 0o700)
        Path(existing, "sentinel").write_bytes(b"keep")
        os.symlink(map_dir, self.target("maplink"))
        cases = {"relative_root": (os.path.relpath(raw), map_dir, monster, self.target("a")),
                 "linked_root": (raw, self.target("maplink"), monster, self.target("b")),
                 "swapped_roots": (map_dir, raw, monster, self.target("c")),
                 "same_root": (raw, raw, monster, self.target("d")),
                 "existing_output": (raw, map_dir, monster, existing),
                 "output_inside_input": (raw, map_dir, monster, os.path.join(raw, "out")),
                 "relative_output": (raw, map_dir, monster, "out")}
        for name, args in cases.items():
            with self.subTest(name):
                proc = run_cli(*args)
                self.assertEqual(proc.returncode, 2, proc.stdout)
                self.assertTrue(proc.stderr.startswith("error: "))
        self.assertEqual(os.listdir(existing), ["sentinel"])
        self.assertEqual(Path(existing, "sentinel").read_bytes(), b"keep")
        self.assertEqual(sorted(os.listdir(raw)), sorted(P.PINS["raw"]))

    def test_hash_checked_before_decoding(self):
        path = os.path.join(self.copy_root, "map", P.MAP_COMPLETE)
        original = Path(path).read_bytes()
        Path(path).write_bytes(b"{" * len(original))
        try:
            with self.assertRaises(P.ReferenceError) as ctx:
                P.admit(*self.roots())
            self.assertIn("is not the pinned", str(ctx.exception))
            self.assertNotIn("JSON", str(ctx.exception))
        finally:
            Path(path).write_bytes(original)


def rebind_raw(datas):
    manifest = datas["raw"][P.RAW_MANIFEST]
    marker = json.loads(datas["raw"][P.RAW_COMPLETE])
    marker["manifest"] = {"bytes": len(manifest), "sha256": sha(manifest)}
    datas["raw"][P.RAW_COMPLETE] = json.dumps(marker).encode()


def rebind_map(datas):
    marker = json.loads(datas["map"][P.MAP_COMPLETE])
    marker["map_cache_manifest_sha256"] = sha(datas["map"][P.MAP_MANIFEST])
    datas["map"][P.MAP_COMPLETE] = json.dumps(marker).encode()


def rebind_monster(datas):
    marker = json.loads(datas["monster"][P.MON_COMPLETE])
    marker["manifest_sha256"] = sha(datas["monster"][P.MON_MANIFEST])
    datas["monster"][P.MON_COMPLETE] = json.dumps(marker).encode()


@unittest.skipUnless(FROZEN, "STATIC_SPAWN_REFERENCE_FROZEN_ROOT not set")
class F08PostAdmissionBridgeMutations(unittest.TestCase):
    """AUTHORED POST-ADMISSION BRIDGE MUTATIONS: in-memory copies of the real artifacts
    are mutated and their markers rebound, then passed directly to the admission
    helpers. This exercises the semantic integrity checks behind the byte pins; it is
    NOT a production byte-pin bypass (the CLI refuses all of these at the pin check)."""

    @classmethod
    def setUpClass(cls):
        cls.datas = real_datas()

    def fresh(self):
        return {b: dict(files) for b, files in self.datas.items()}

    def test_baseline_bridges_pass(self):
        datas = self.fresh()
        P._admit_raw(datas["raw"])
        P._admit_map(datas["map"])
        P._admit_monster(datas["monster"])

    def mutated(self, bundle, name, fn, rebind):
        datas = self.fresh()
        obj = json.loads(datas[bundle][name])
        fn(obj)
        datas[bundle][name] = json.dumps(obj).encode()
        if rebind:
            rebind(datas)
        return datas

    def test_raw_mutations(self):
        cases = {
            "state_qualified": lambda m: m.update(state="qualified"),
            "task": lambda m: m.update(task="T06.002.003.005.000"),
            "profile": lambda m: m.update(profile="static-spawn-raw-v2"),
            "schema_bool": lambda m: m.update(schema=True),
            "producer_sha": lambda m: m["producer"].update(sha256="0" * 64),
            "reader_sha": lambda m: m["inputs"]["reader"].update(sha256="0" * 64),
            "snapshot_sha": lambda m: m["inputs"]["snapshot_manifest"].update(sha256="0" * 64),
            "selection_bytes": lambda m: m["inputs"]["selection_manifest"].update(bytes=1),
            "counter_events": lambda m: m["counters"].update(framing_events=353),
            "counter_supported": lambda m: m["counters"].update(static_supported=191),
            "source_framing": lambda m: m["sources"][0].update(framing="qualified"),
            "source_projection": lambda m: m["sources"][1].update(projection="qualified"),
            "source_counts": lambda m: m["sources"][0]["counters"].update(framing_events=158),
            "source_bytes": lambda m: m["sources"][1].update(bytes=6647, certified_offset=6647),
            "unscanned_changed": lambda m: m["unscanned_selection_indices"].pop(),
            "unscanned_includes_pilot": lambda m: m["unscanned_selection_indices"].__setitem__(
                691, 691),
            "outputs_rows": lambda m: m["outputs"]["static-spawn-pilot.jsonl"].update(rows=353),
        }
        for name, fn in cases.items():
            with self.subTest(name), self.assertRaises(P.ReferenceError):
                P._admit_raw(self.mutated("raw", P.RAW_MANIFEST, fn, rebind_raw)["raw"])
        with self.assertRaises(P.ReferenceError):  # unbound manifest change
            P._admit_raw(self.mutated("raw", P.RAW_MANIFEST,
                                      lambda m: m.update(extra=1), None)["raw"])
        with self.assertRaises(P.ReferenceError):
            P._admit_raw(self.mutated("raw", P.RAW_COMPLETE,
                                      lambda m: m.update(state="qualified"), None)["raw"])

    def test_map_mutations(self):
        cases = {
            "status": lambda m: m.update(status="incomplete"),
            "generator_sha": lambda m: m["generator"].update(source_sha256="0" * 64),
            "generator_version": lambda m: m["generator"].update(version="1.0.0"),
            "verifier": lambda m: m["generator"]["snapshot_verifier"].update(source_sha256="0" * 64),
            "snapshot": lambda m: m["inputs"]["snapshot"].update(manifest_sha256="0" * 64),
            "selection": lambda m: m["inputs"]["selection"]["selection-manifest.json"].update(
                bytes=1),
            "revision": lambda m: m["source"].update(revision="0" * 40),
            "profile_name": lambda m: m["profile"].update(name="other"),
            "use_grf_bool": lambda m: m["profile"].update(required_use_grf=False),
            "use_grf_one": lambda m: m["profile"].update(required_use_grf=1),
            "db_path": lambda m: m["profile"].update(required_db_path="db/re"),
            "renewal": lambda m: m["profile"].update(renewal=False),
            "name_length": lambda m: m["profile"].update(map_name_length=12.0),
            "max_index": lambda m: m["profile"].update(max_mapindex=2001),
            "reverse_count": lambda m: m["index"]["state"].update(reverse_count=1),
            "unresolved_candidate": lambda m: m["candidates"][0].update(
                disposition="unresolved_unsafe"),
        }
        for name, fn in cases.items():
            with self.subTest(name), self.assertRaises(P.ReferenceError):
                P._admit_map(self.mutated("map", P.MAP_MANIFEST, fn, rebind_map)["map"])
        with self.assertRaises(P.ReferenceError):
            P._admit_map(self.mutated("map", P.MAP_COMPLETE,
                                      lambda m: m.update(status="incomplete"), None)["map"])

    def test_monster_mutations(self):
        cases = {
            "status": lambda m: m.update(status="incomplete"),
            "stop": lambda m: m.update(stop={"reason": "work_limit"}),
            "stop_missing": lambda m: m.pop("stop"),
            "unresolved": lambda m: m.update(unresolved=[{"id": 1}]),
            "generator": lambda m: m["generator"].update(source_sha256="0" * 64),
            "profile_name": lambda m: m["profile"].update(name="other"),
            "sql_branch": lambda m: m["profile"].update(item_monster_sql_branch=True),
            "generator_load": lambda m: m["profile"].update(should_load_generator=0),
            "renewal": lambda m: m["profile"].update(renewal=1),
            "snapshot": lambda m: m["input"].update(snapshot_manifest_sha256="0" * 64),
            "reader": lambda m: m["input"]["verification"].update(reader_sha256="0" * 64),
            "revision": lambda m: m["source"].update(revision="0" * 40),
            "prerequisite": lambda m: m["prerequisite"]["manifest"].update(sha256="0" * 64),
            "history_lines": lambda m: m["history_file"].update(lines=2698),
            "records_sha": lambda m: m["records_file"].update(sha256="0" * 64),
            "records_bytes_bool": lambda m: m["records_file"].update(bytes=True),
        }
        for name, fn in cases.items():
            with self.subTest(name), self.assertRaises(P.ReferenceError):
                P._admit_monster(self.mutated("monster", P.MON_MANIFEST, fn,
                                              rebind_monster)["monster"])
        with self.assertRaises(P.ReferenceError):
            P._admit_monster(self.mutated("monster", P.MON_COMPLETE,
                                          lambda m: m.update(status="incomplete"),
                                          None)["monster"])


# --- F10 negative controls -------------------------------------------------------------

class F10NegativeControls(unittest.TestCase):
    """Each fault replaces a real producer function; the golden must fail under it."""

    def control(self, attr, replacement, check=golden_check):
        check(self)  # baseline passes
        original = getattr(P, attr)
        setattr(P, attr, replacement(original))
        try:
            with self.assertRaises((AssertionError, P.ReferenceError)):
                check(self)
        finally:
            setattr(P, attr, original)
        check(self)  # passes again on baseline

    def test_base_lowercasing(self):
        self.control("normalise_map", lambda orig: lambda raw_hex: orig(raw_hex).lower())

    def test_last_candidate_selection(self):
        def fault(orig):
            def table(candidates, limits):
                return {k: v[-1:] for k, v in orig(candidates, limits).items()}
            return table
        self.control("_candidate_table", fault)

    def test_retained_only_filter(self):
        def fault(orig):
            def table(candidates, limits):
                return {k: [c for c in v if c["disposition"] == "retained"]
                        for k, v in orig(candidates, limits).items()}
            return table
        self.control("_candidate_table", fault)

    def test_latest_history_declaration(self):
        def fault(orig):
            def monster(sprite, histories, counters):
                ref = orig(sprite, histories, counters)
                if ref["history"] is not None:
                    ref["history"]["declarations"] = ref["history"]["declarations"][-1:]
                return ref
            return monster
        self.control("_monster_reference", fault)

    def test_deduplicated_history_spans(self):
        def fault(orig):
            def monster(sprite, histories, counters):
                ref = orig(sprite, histories, counters)
                if ref["history"] is not None:
                    seen, kept = set(), []
                    for d in ref["history"]["declarations"]:
                        key = (d["file"], tuple(d["id_byte_span"]))
                        if key not in seen:
                            seen.add(key)
                            kept.append(d)
                    ref["history"]["declarations"] = kept
                return ref
            return monster
        self.control("_monster_reference", fault)

    def test_gap_recovery(self):
        def fault(orig):
            def classify(event, start, end):
                detail = event["detail"]
                if event["kind"] == "static" and detail["projection_state"] == "gap":
                    raw = detail["fields"][0]["raw_hex"]
                    return "supported", raw, 1002
                return orig(event, start, end)
            return classify
        self.control("_classify", fault)

    def test_opaque_monster_recovery(self):
        def fault(orig):
            def classify(event, start, end):
                if event["kind"] == "opaque":
                    return "supported", "466f6f", 1002
                return orig(event, start, end)
            return classify
        self.control("_classify", fault)

    def test_sprite_zero_treated_as_sentinel(self):
        def fault(orig):
            def monster(sprite, histories, counters):
                if sprite == 0:
                    counters["monster_history_missing"] += 1
                    return {"sprite": 0, "state": "no_declared_history", "history": None}
                return orig(sprite, histories, counters)
            return monster
        self.control("_monster_reference", fault)

    def test_counter_conservation_detects_fault(self):
        def check(test):
            conservation(test, join_case())

        def fault(orig):
            def map_ref(raw_hex, names, by_id, counters):
                ref = orig(raw_hex, names, by_id, counters)
                counters["map_candidate_occurrences"] += 1
                return ref
            return map_ref
        self.control("_map_reference", fault, check)


if __name__ == "__main__":
    unittest.main(verbosity=2)
