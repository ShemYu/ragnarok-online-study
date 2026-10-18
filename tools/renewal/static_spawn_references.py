#!/usr/bin/env python3
"""Declared map/monster reference sidecar for the qualified two-file raw spawn pilot.

T06.002.003.005.002 (profile static-spawn-declared-reference-v1). Inputs are three
immutable bundles of exactly ten pinned artifacts: the complete raw pilot
(T06.002.003.005.001), the complete map-cache inventory and the complete monster
projection. Every framed raw event receives one row: supported static
declarations get the declared map reference (one mapindex_getmapname operation,
the exact final reverse-index ID and every map candidate occurrence with that
ID) and the declared sprite's whole qualified Id history; every other event is
unjoined with an exact reason. Occurrences are copied, never deduplicated,
filtered or resolved to a native, effective or last-wins result.

The 40 MB declaration stream is hashed and counted only; references come from the
already-qualified history stream. Nothing is scanned, parsed from YAML, executed
or decoded beyond the pinned JSON. Not native membership, effective population,
map cells, world coverage, localisation or story/solo evidence.

Exit 0 after a complete private publication, 2 on any failure (no usable owned
manifest or completion record). Standard library only. Output directories are
never overwritten. The CLI has no environment, pin, limit or config override.
"""

import argparse
import copy
import errno
import hashlib
import json
import math
import os
import re
import stat
import sys

TASK = "T06.002.003.005.002"
PROFILE_NAME = "static-spawn-declared-reference-v1"
PRODUCER_FILE = "tools/renewal/static_spawn_references.py"
PRODUCER_CAP = 1 << 20

RAW_TASK = "T06.002.003.005.001"
RAW_PROFILE = "static-spawn-raw-v1"
RAW_PRODUCER = {"bytes": 46367, "file": "tools/renewal/static_spawn_pilot.py",
                "sha256": "14690614311ee805c3aa2906a15a77efe6885d51bf68a9cea50bc6bd5b581cbd"}
MAP_GENERATOR = {"source_sha256": "996a0cb8c6001150931b4cfa7e4e098fc4f2b7f10551b7ed428b98d51f08b56d",
                 "tool": "tools/renewal/map_cache_inventory.py", "version": "1.0.1"}
MONSTER_GENERATOR = {"source_sha256": "45272a3660ff459a56b8f0ea7d30b0facef0e9f83fed13e981655dcc758e64d9",
                     "tool": "tools/renewal/monster_projection.py", "version": "1.0.1"}
RATHENA_REVISION = "0693b8c69911d5ca42269684aa036b67d67f4d3e"
SNAPSHOT_MANIFEST_SHA = "79ee4eff2ed1621aa3be6247d0aedefc5f44abd65025617de652f41644c1dbd0"
READER_SHA = "22a3f4c8016e4e38608039084eb762440f9c56dd611e2af44be151fdf3c24417"
SELECTION_MANIFEST = {"bytes": 953299,
                      "sha256": "d62e31fd601a879a9020eb0cbc79273cdaa38f11d6119af056b36727631aec9a"}
SELECTION_COMPLETE = {"bytes": 185,
                      "sha256": "26b9e804bd613fbf4ed1886d69ca8cf08ffc9c8b559db56b52c8bedd95ebb197"}
YAML_PREREQUISITE_SHA = "60fc99c4259743170e2239648539e1bc1757299f4168484b96ac7c736b76f98a"
MAP_PROFILE_NAME = "rathena-0693b8c-renewal-use_grf-off"
MONSTER_PROFILE_NAME = "rathena-0693b8c-stock-renewal-yaml-four-roots"
RAW_SELECTION_COUNT = 839
RAW_SELECTION_INDICES = (691, 772)
RAW_COUNTS = {"raw_lines": 311, "framing_events": 354, "static_declared": 192,
              "static_supported": 192, "static_gap": 0, "suffix_events": 0}
MONSTER_ROWS = 2699

RAW_LINES = "source-lines.jsonl"
RAW_EVENTS = "static-spawn-pilot.jsonl"
RAW_MANIFEST = "static-spawn-pilot-manifest.json"
RAW_COMPLETE = "static-spawn-pilot-complete.json"
MAP_MANIFEST = "map-cache-manifest.json"
MAP_COMPLETE = "map-cache-complete.json"
MON_MANIFEST = "monster-projection-manifest.json"
MON_COMPLETE = "monster-projection-complete.json"
MON_DECLARATIONS = "monster-declarations.jsonl"
MON_HISTORY = "monster-id-history.jsonl"

# Exact artifact pins (bundle -> file -> bytes/sha256). Relocation is allowed;
# names, sizes and hashes are not.
PINS = {
    "raw": {
        RAW_LINES: {"bytes": 80085,
                    "sha256": "c09c1b7ede612d6bad9ac914a906bbe60440491310918538be00f6aef641c6dd"},
        RAW_EVENTS: {"bytes": 260948,
                     "sha256": "a624cf9833e9e4cf096c04f45e8782f21d2792a3446ec3c911a0406d855e4e9a"},
        RAW_MANIFEST: {"bytes": 6543,
                       "sha256": "4fcf34b5076c79590e54850ba729941e920219c078c5c30d607b7c8211e5b1c5"},
        RAW_COMPLETE: {"bytes": 462,
                       "sha256": "4bef03ad0af29edb14b7c12bf90ed2f2b8f537ee17b2e25ec3b1e3a01e10e4aa"},
    },
    "map": {
        MAP_MANIFEST: {"bytes": 2109200,
                       "sha256": "fd49368cc132ad7a1303d1eba8705b89da1548b293265094b69dc7e80ea240f5"},
        MAP_COMPLETE: {"bytes": 205,
                       "sha256": "d8afaebd76958d8213347fd4f765cd2a226bcd0d0761c2c2e6d4db85c6742a11"},
    },
    "monster": {
        MON_MANIFEST: {"bytes": 20320,
                       "sha256": "71220de66e81869cb955fb0b2ad47775b79a10953d866ab8ad70189aa77b3ce1"},
        MON_COMPLETE: {"bytes": 601,
                       "sha256": "8cee77900a4832cadad00f509e0b6b37ad48c6e649e8af36fa5777642386d1de"},
        MON_DECLARATIONS: {"bytes": 40733741,
                           "sha256": "32e88cbf8111be5be17739ca7170bd8f1568b6bba0edbb14c84582c73ceebcb4"},
        MON_HISTORY: {"bytes": 2135829,
                      "sha256": "def51761c55bdcaa68e9b9b30eeeead37d23d74e682dedfa9e6fb89399be9075"},
    },
}
BUNDLES = ("raw", "map", "monster")

LIMITS = {"completion_bytes": 65536, "events": 8192, "history_references": 20000,
          "history_rows": 10000, "input_total_bytes": 67108864, "jsonl_bytes": 16777216,
          "manifest_bytes": 1048576, "map_candidates": 10000, "map_reverse_rows": 2000}

OUTPUT_ROWS = "static-spawn-references.jsonl"
OUTPUT_MANIFEST = "static-spawn-references-manifest.json"
OUTPUT_COMPLETE = "static-spawn-references-complete.json"

COUNTER_KEYS = ("events", "map_candidate_none", "map_candidate_occurrences",
                "map_candidate_present", "map_index_missing", "map_index_nonzero",
                "map_index_zero", "monster_declaration_occurrences", "monster_history_missing",
                "monster_history_present", "not_static", "opaque", "static_gap",
                "static_supported", "suffix")
CLAIMS = {"map_cells": "not_checked", "native_membership": "not_checked",
          "effective_population": "not_checked", "world_coverage": "not_checked",
          "localisation": "not_checked", "story_solo": "not_checked"}

EVENT_KEYS = frozenset(("schema", "source_index", "event_index", "span", "sha256", "kind",
                        "detail"))
NOT_STATIC = frozenset(("whitespace", "line_comment", "block_comment"))
STATIC_DETAIL_KEYS = frozenset(("fields", "gaps", "keyword", "projection_state", "tabs",
                                "values"))
OPAQUE_PARTS = frozenset(("header", "open", "body", "close"))
SLOT_KEYS = frozenset(("value", "origin", "span"))
SPRITE_MAX = 2147483647
MAP_TOKEN = re.compile(rb"[A-Za-z0-9_]{1,11}(?:\.[Gg][Aa][Tt])?")
HEX = re.compile(r"(?:[0-9a-f]{2})+")
SHA = re.compile(r"[0-9a-f]{64}")

CANDIDATE_BASE = frozenset(("attempts", "config_file", "config_line", "disposition",
                            "index_lookup", "name", "ordinal", "raw"))
# The five recognised map dispositions and their conditional fields.
DISPOSITION_FIELDS = {
    "retained": frozenset(("cache", "index_id", "slot")),
    "discarded_duplicate_index": frozenset(("cache", "duplicate_of_ordinal")),
    "discarded_not_found": frozenset(("reasons",)),
    "unresolved_unsafe": frozenset(("uncertainty_since_ordinal",)),
    "unresolved_due_to_prior_candidate": frozenset(("uncertainty_since_ordinal",)),
}
HISTORY_KEYS = frozenset(("declaration_count", "declarations", "id", "id_decimal", "meaning",
                          "source_gate"))
SOURCE_GATES = frozenset(("in_range", "out_of_range"))
REFERENCE_TYPES = {
    "database": "s", "database_ordinal": "u", "epoch": "u", "file": "s", "file_sha256": "h",
    "fingerprint_sha256": "h", "global_ordinal": "u", "id_byte_span": "span",
    "id_span_sha256": "h", "id_style": "s", "id_text": "s", "local_ordinal": "u",
    "projection_ordinal": "u", "projection_status": "status", "row_byte_span": "span",
    "row_span_sha256": "h", "visit": "u",
}

DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
READ_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
WRITE_FLAGS = (os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
               | getattr(os, "O_CLOEXEC", 0))

# Raw OS operations used by the owned I/O paths. Authored tests replace these
# module attributes to inject faults; the CLI and environment expose no seam.
_os_open = os.open
_os_read = os.read
_os_write = os.write
_os_fsync = os.fsync
_os_close = os.close
_os_mkdir = os.mkdir
_os_unlink = os.unlink


class ReferenceError(Exception):  # noqa: A001 - the frozen API name
    """A fatal input, type, order, bound, admission or publication failure (exit 2)."""


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def pin(data):
    return {"bytes": len(data), "sha256": sha256(data)}


def render(obj):
    """Sorted-key compact ASCII-escaped JSON plus LF."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii") + b"\n"


def _err(exc):
    """Bounded OSError text without file names."""
    if isinstance(exc, OSError):
        return f"{type(exc).__name__} errno {exc.errno}: {exc.strerror}"
    return type(exc).__name__


def _is_u(value):
    return type(value) is int and value >= 0


def _is_str(value):
    return type(value) is str and value != ""


def _is_sha(value):
    return type(value) is str and SHA.fullmatch(value) is not None


def _is_span(value, ordered=True):
    return (type(value) is list and len(value) == 2 and _is_u(value[0]) and _is_u(value[1])
            and (not ordered or value[0] <= value[1]))


def _need(condition, message):
    if not condition:
        raise ReferenceError(message)


# --- Core: limits and normalisation ---------------------------------------------------

def _check_limits(limits):
    """Validate a whole exact limit mapping (None selects the defaults)."""
    if limits is None:
        return dict(LIMITS)
    _need(type(limits) is dict, "limits must be a dict")
    _need(set(limits) == set(LIMITS), "limits must have exactly the LIMITS keys")
    for key, value in limits.items():
        _need(_is_u(value) and value <= LIMITS[key],
              f"limit {key} must be a nonnegative integer no greater than {LIMITS[key]}")
    return dict(limits)


def _decode_map_hex(raw_hex):
    _need(type(raw_hex) is str and HEX.fullmatch(raw_hex) is not None,
          "map value must be nonempty even-length lowercase hexadecimal")
    raw = bytes.fromhex(raw_hex)
    _need(len(raw) <= 15 and MAP_TOKEN.fullmatch(raw) is not None,
          "map value is outside the raw spawn map grammar")
    return raw


def normalise_map(raw_hex):
    """One mapindex_getmapname operation: drop one terminal case-insensitive `.gat`.

    Base case is kept; nothing is trimmed, lowercased, aliased or clipped (the
    accepted subset is at most 11 base bytes, so the native clip never applies).
    """
    raw = _decode_map_hex(raw_hex)
    if len(raw) >= 4 and raw[-4:].lower() == b".gat":
        raw = raw[:-4]
    return raw.decode("ascii")


# --- Core: reference tables -----------------------------------------------------------

def _reverse_table(reverse, limits):
    _need(type(reverse) is list, "reverse must be a list")
    _need(len(reverse) <= limits["map_reverse_rows"], "reverse rows exceed map_reverse_rows")
    table = {}
    for row in reverse:
        _need(type(row) is dict and set(row) == {"id", "name"},
              "reverse row must be exactly {id, name}")
        _need(_is_u(row["id"]), "reverse id must be a nonnegative integer")
        _need(type(row["name"]) is str, "reverse name must be a string")
        _need(row["name"] not in table, f"duplicate reverse name {row['name']!r}")
        table[row["name"]] = row["id"]
    return table


def _check_attempt(attempt):
    _need(type(attempt) is dict and set(attempt) in ({"file", "outcome"},
                                                     {"file", "ordinal", "outcome"}),
          "candidate attempt has an unexpected shape")
    _need(_is_str(attempt["file"]) and _is_str(attempt["outcome"]),
          "candidate attempt file/outcome must be nonempty strings")
    _need("ordinal" not in attempt or _is_u(attempt["ordinal"]),
          "candidate attempt ordinal must be a nonnegative integer")


def _check_candidate(candidate):
    _need(type(candidate) is dict, "map candidate must be an object")
    disposition = candidate.get("disposition")
    _need(type(disposition) is str and disposition in DISPOSITION_FIELDS,
          "map candidate has an unrecognised disposition")
    _need(set(candidate) == CANDIDATE_BASE | DISPOSITION_FIELDS[disposition],
          f"map candidate keys do not match disposition {disposition}")
    _need(_is_u(candidate["ordinal"]), "candidate ordinal must be a nonnegative integer")
    _need(type(candidate["name"]) is str, "candidate name must be a string")
    _need(candidate["raw"] is None or type(candidate["raw"]) is str,
          "candidate raw must be a string or null")
    _need(candidate["config_file"] is None or type(candidate["config_file"]) is str,
          "candidate config_file must be a string or null")
    _need(candidate["config_line"] is None or _is_u(candidate["config_line"]),
          "candidate config_line must be a nonnegative integer or null")
    _need(type(candidate["attempts"]) is list, "candidate attempts must be a list")
    for attempt in candidate["attempts"]:
        _check_attempt(attempt)
    lookup = candidate["index_lookup"]
    _need(type(lookup) is dict and set(lookup) == {"id", "normalised"},
          "candidate index_lookup must be exactly {id, normalised}")
    _need(lookup["id"] is None or _is_u(lookup["id"]),
          "candidate index_lookup.id must be a nonnegative integer or null")
    _need(type(lookup["normalised"]) is str, "candidate index_lookup.normalised must be a string")
    if "cache" in candidate:
        cache = candidate["cache"]
        _need(type(cache) is dict and set(cache) == {"file", "ordinal"}
              and _is_str(cache["file"]) and _is_u(cache["ordinal"]),
              "candidate cache must be {file, ordinal}")
    for key in ("index_id", "slot", "duplicate_of_ordinal", "uncertainty_since_ordinal"):
        if key in candidate:
            _need(_is_u(candidate[key]), f"candidate {key} must be a nonnegative integer")
    if "reasons" in candidate:
        _need(type(candidate["reasons"]) is list
              and all(_is_str(r) for r in candidate["reasons"]),
              "candidate reasons must be a list of nonempty strings")


def _candidate_table(candidates, limits):
    """Validate candidates; return {index_lookup.id: [candidates in ordinal order]}."""
    _need(type(candidates) is list, "candidates must be a list")
    _need(len(candidates) <= limits["map_candidates"], "map candidates exceed map_candidates")
    table, previous = {}, None
    for candidate in candidates:
        _check_candidate(candidate)
        _need(previous is None or candidate["ordinal"] > previous,
              "map candidate ordinals must be unique and strictly increasing")
        previous = candidate["ordinal"]
        index_id = candidate["index_lookup"]["id"]
        if index_id is not None:  # null IDs are never collected by null equality
            table.setdefault(index_id, []).append(candidate)
    return table


def _check_reference(reference):
    _need(type(reference) is dict and set(reference) == set(REFERENCE_TYPES),
          "history declaration reference has an unexpected shape")
    for key, kind in REFERENCE_TYPES.items():
        value = reference[key]
        ok = {"u": _is_u, "s": _is_str, "h": _is_sha,
              "span": _is_span,
              "status": lambda v: v in ("modelled", "gap") and type(v) is str}[kind](value)
        _need(ok, f"history declaration {key} has an invalid value")


def _history_table(histories, limits):
    _need(type(histories) is list, "histories must be a list")
    _need(len(histories) <= limits["history_rows"], "history rows exceed history_rows")
    table, previous, references = {}, None, 0
    for history in histories:
        _need(type(history) is dict and set(history) == HISTORY_KEYS,
              "history row has an unexpected shape")
        hid = history["id"]
        _need(_is_u(hid), "history id must be a nonnegative integer")
        _need(previous is None or hid > previous,
              "history ids must be unique and strictly increasing")
        previous = hid
        _need(history["id_decimal"] == str(hid) and type(history["id_decimal"]) is str,
              "history id_decimal must be the canonical decimal id")
        _need(type(history["source_gate"]) is str and history["source_gate"] in SOURCE_GATES,
              "history source_gate is not recognised")
        _need(_is_str(history["meaning"]), "history meaning must be a nonempty string")
        declarations = history["declarations"]
        _need(type(declarations) is list, "history declarations must be a list")
        _need(_is_u(history["declaration_count"])
              and history["declaration_count"] == len(declarations),
              "history declaration_count must equal its declarations")
        references += len(declarations)
        _need(references <= limits["history_references"],
              "history references exceed history_references")
        for reference in declarations:
            _check_reference(reference)
        table[hid] = history
    return table


# --- Core: event annotation ----------------------------------------------------------

def _check_slot(slot, start, end, what):
    _need(type(slot) is dict and set(slot) == SLOT_KEYS, f"{what} slot has an unexpected shape")
    _need(slot["origin"] == "declared", f"{what} slot must be declared")
    span = slot["span"]
    _need(_is_span(span) and span[0] < span[1] and start <= span[0] and span[1] <= end,
          f"{what} slot span must be positive and inside the event")
    return span[1] - span[0]


def _static_values(detail, start, end):
    """Validate a supported static detail; return (map raw_hex, sprite)."""
    _need(detail["gaps"] == [] and type(detail["gaps"]) is list,
          "supported static projection must have no gaps")
    values = detail["values"]
    _need(type(values) is dict and "map" in values and "sprite" in values,
          "supported static projection must have map and sprite slots")
    map_slot, sprite_slot = values["map"], values["sprite"]
    width = _check_slot(map_slot, start, end, "map")
    raw = _decode_map_hex(map_slot["value"])
    _need(width == len(raw), "map slot span length differs from its decoded bytes")
    width = _check_slot(sprite_slot, start, end, "sprite")
    sprite = sprite_slot["value"]
    _need(_is_u(sprite) and sprite <= SPRITE_MAX, "sprite must be an integer 0..2147483647")
    _need(width == len(str(sprite)), "sprite slot span length differs from its decimal text")
    return map_slot["value"], sprite


def _check_gaps(gaps, start, end):
    _need(type(gaps) is list and gaps, "static gap projection must list its gaps")
    for gap in gaps:
        _need(type(gap) is dict and set(gap) == {"code", "span"} and _is_str(gap["code"]),
              "static gap has an unexpected shape")
        span = gap["span"]
        _need(_is_span(span) and start <= span[0] and span[1] <= end,
              "static gap span must lie inside the event")


def _classify(event, start, end):
    """Return ('supported', map_hex, sprite) or ('unjoined', reason)."""
    kind, detail = event["kind"], event["detail"]
    if kind in NOT_STATIC:
        _need(detail is None, f"{kind} event detail must be null")
        return "unjoined", {"code": "not_static", "detail": None}
    if kind == "opaque":
        _need(type(detail) is dict and set(detail) == OPAQUE_PARTS,
              "opaque event detail has an unexpected shape")
        for part in detail.values():
            _need(type(part) is dict and set(part) == {"sha256", "span"}
                  and _is_sha(part["sha256"]) and _is_span(part["span"]),
                  "opaque part has an unexpected shape")
        return "unjoined", {"code": "opaque_script", "detail": None}
    if kind == "suffix":
        _need(type(detail) is dict and set(detail) == {"fault_offset", "reason"}
              and _is_u(detail["fault_offset"]) and _is_str(detail["reason"]),
              "suffix event detail has an unexpected shape")
        _need(start <= detail["fault_offset"] <= end, "suffix fault_offset outside its event")
        return "unjoined", {"code": "uncertified_suffix", "detail": copy.deepcopy(detail)}
    _need(kind == "static", f"unknown event kind {kind!r}")
    _need(type(detail) is dict and set(detail) == STATIC_DETAIL_KEYS,
          "static event detail has an unexpected shape")
    _need(type(detail["fields"]) is list and _is_u(detail["tabs"]) and _is_str(detail["keyword"]),
          "static event fields/tabs/keyword have unexpected types")
    state = detail["projection_state"]
    if state == "supported":
        return ("supported",) + _static_values(detail, start, end)
    _need(state == "gap", "static projection_state must be supported or gap")
    _need(detail["values"] is None, "static gap projection must have null values")
    _check_gaps(detail["gaps"], start, end)
    return "unjoined", {"code": "static_projection_gap", "detail": copy.deepcopy(detail["gaps"])}


class _Order:
    """Global contiguity, nondecreasing sources, adjacent spans and suffix finality."""

    def __init__(self):
        self.source = None
        self.cursor = 0
        self.closed = False

    def admit(self, event, position):
        _need(type(event) is dict and set(event) == EVENT_KEYS, "raw event has an unexpected shape")
        _need(event["schema"] == 1 and type(event["schema"]) is int, "raw event schema must be 1")
        _need(_is_u(event["event_index"]) and event["event_index"] == position,
              "event_index must be globally contiguous from 0")
        source = event["source_index"]
        _need(type(source) is int and source in (0, 1), "source_index must be 0 or 1")
        _need(self.source is None or source >= self.source, "source_index must not decrease")
        if source != self.source:
            self.source, self.cursor, self.closed = source, 0, False
        _need(not self.closed, "no event may follow a suffix in the same source")
        span = event["span"]
        _need(_is_span(span) and span[0] < span[1], "event span must have positive length")
        _need(span[0] == self.cursor, "event spans must start at 0 and be adjacent")
        _need(_is_sha(event["sha256"]), "event sha256 must be lowercase 64-hex")
        _need(type(event["kind"]) is str, "event kind must be a string")
        self.cursor = span[1]
        self.closed = event["kind"] == "suffix"
        return span[0], span[1]


def _map_reference(raw_hex, names, by_id, counters):
    normalised = normalise_map(raw_hex)
    index_id = names.get(normalised)
    if index_id is None:
        counters["map_index_missing"] += 1
        index, state, attached = {"state": "missing", "id": None}, "not_applicable", []
    elif index_id == 0:
        counters["map_index_zero"] += 1
        index, state, attached = {"state": "zero", "id": 0}, "not_applicable", []
    else:
        counters["map_index_nonzero"] += 1
        attached = [copy.deepcopy(c) for c in by_id.get(index_id, ())]
        state = "present" if attached else "none"
        counters["map_candidate_" + state] += 1
        index = {"state": "nonzero", "id": index_id}
    counters["map_candidate_occurrences"] += len(attached)
    return {"raw_hex": raw_hex, "normalised": normalised, "index": index,
            "candidate_state": state, "candidates": attached}


def _monster_reference(sprite, histories, counters):
    history = histories.get(sprite)
    if history is None:
        counters["monster_history_missing"] += 1
        return {"sprite": sprite, "state": "no_declared_history", "history": None}
    counters["monster_history_present"] += 1
    counters["monster_declaration_occurrences"] += len(history["declarations"])
    return {"sprite": sprite, "state": "declared_history", "history": copy.deepcopy(history)}


UNJOINED_COUNTER = {"static_projection_gap": "static_gap", "opaque_script": "opaque",
                    "uncertified_suffix": "suffix", "not_static": "not_static"}


def join_events(events, reverse, candidates, histories, limits=None):
    """Annotate every raw event; return exactly {rows, counters}. Inputs are not mutated."""
    limits = _check_limits(limits)
    _need(type(events) is list, "events must be a list")
    _need(len(events) <= limits["events"], "raw events exceed the events limit")
    names = _reverse_table(reverse, limits)
    by_id = _candidate_table(candidates, limits)
    by_sprite = _history_table(histories, limits)
    counters = dict.fromkeys(COUNTER_KEYS, 0)
    order, rows, used = _Order(), [], 0
    for position, event in enumerate(events):
        start, end = order.admit(event, position)
        result = _classify(event, start, end)
        row = {"schema": 1, "source_index": event["source_index"],
               "event_index": event["event_index"],
               "raw": {"kind": event["kind"], "span": [start, end], "sha256": event["sha256"]},
               "map": None, "monster": None, "unjoined": None}
        if result[0] == "supported":
            counters["static_supported"] += 1
            row["map"] = _map_reference(result[1], names, by_id, counters)
            row["monster"] = _monster_reference(result[2], by_sprite, counters)
        else:
            row["unjoined"] = result[1]
            counters[UNJOINED_COUNTER[result[1]["code"]]] += 1
        counters["events"] += 1
        used += len(render(row))
        _need(used <= limits["jsonl_bytes"], "output rows exceed jsonl_bytes")
        rows.append(row)
    return {"rows": rows, "counters": counters}


# --- Bounded regular-file reads --------------------------------------------------

def _fd_identity(fd):
    info = os.fstat(fd)
    return info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode)


def _close_state(fd, identity):
    """Observe the retained slot before another open can reuse its number."""
    try:
        current = _fd_identity(fd)
    except OSError as exc:
        return "released" if exc.errno == errno.EBADF else "unknown"
    if identity is None:
        return "unknown"
    return "owned" if current == identity else "foreign"


def _close_after(fd, what, primary, recover=True):
    """Keep close errors fatal; recover a still-owned serial FD at most once.

    Identity checks distinguish the controlled before/after-close cases and
    different-inode reuse. They are not FD-generation proof against arbitrary
    concurrent/reentrant same-inode reuse. Unknown/foreign slots are preserved.
    """
    try:
        identity = _fd_identity(fd)
    except OSError:
        identity = None
    try:
        _os_close(fd)
    except OSError as exc:
        failure = (f"{what}: close failed ({_err(exc)})" if primary is None else
                   f"{primary}; cleanup close also failed ({_err(exc)})")
        state = _close_state(fd, identity)
        if state == "owned" and recover:
            try:
                _os_close(fd)
            except OSError as cleanup:
                failure += f"; guarded cleanup close failed ({_err(cleanup)})"
            state = _close_state(fd, identity)
        note = {"released": "descriptor release observed",
                "foreign": "foreign descriptor left untouched",
                "owned": "owned descriptor remains; cleanup unresolved",
                "unknown": "descriptor ownership unknown; cleanup unresolved"}[state]
        raise ReferenceError(f"{failure}; {note}") from None
    if primary is not None:
        raise ReferenceError(primary)


def read_regular(name, limit, what, dir_fd=None):
    """Read a bounded regular non-link file without blocking; close errors stay fatal."""
    try:
        fd = _os_open(name, READ_FLAGS, dir_fd=dir_fd)
    except OSError as exc:
        raise ReferenceError(f"{what}: cannot open without following links ({_err(exc)})") from None
    primary, chunks = None, []
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            primary = f"{what}: not a regular file"
        elif info.st_size > limit:
            primary = f"{what}: larger than {limit} bytes"
        else:
            total = 0
            while True:
                chunk = _os_read(fd, min(1 << 20, limit + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > limit:
                    primary = f"{what}: grew beyond {limit} bytes while being read"
                    break
            if primary is None and total != info.st_size:
                primary = f"{what}: changed size while being read"
    except OSError as exc:
        primary = f"{what}: read failed ({_err(exc)})"
    _close_after(fd, what, primary)
    return b"".join(chunks)


def _reject_constant(value):
    raise ReferenceError(f"nonfinite JSON constant {value}")


def _finite_float(token):
    value = float(token)
    if not math.isfinite(value):
        raise ReferenceError("nonfinite JSON number")
    return value


def strict_json(data, what):
    """Decode UTF-8 JSON refusing duplicate keys and nonfinite numbers/constants."""
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ReferenceError(f"duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=unique,
                          parse_constant=_reject_constant, parse_float=_finite_float)
    except ReferenceError as exc:
        raise ReferenceError(f"{what}: {exc}") from None
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise ReferenceError(f"{what}: invalid JSON ({type(exc).__name__})") from None


def jsonl_count(data, what):
    """Count LF-terminated rows without decoding them."""
    _need(data == b"" or data.endswith(b"\n"), f"{what}: final row lacks LF")
    _need(b"\n\n" not in data and not data.startswith(b"\n"), f"{what}: empty row")
    return data.count(b"\n")


def strict_jsonl(data, what):
    count = jsonl_count(data, what)
    rows = [strict_json(line, f"{what} row {n}") for n, line in
            enumerate(data.split(b"\n")[:count])]
    for row in rows:
        _need(type(row) is dict, f"{what}: every row must be an object")
    return rows


# --- Admission (production CLI only) --------------------------------------------------

def _linked(path):
    return os.path.realpath(path) != os.path.normpath(path)


def read_bundle(root, bundle):
    """Read exactly the pinned regular files of one bundle; verify bytes before decoding."""
    expected = PINS[bundle]
    _need(os.path.isabs(root), f"{bundle} root must be an absolute path")
    try:
        info = os.lstat(root)
    except OSError as exc:
        raise ReferenceError(f"{bundle} root: {_err(exc)}") from None
    _need(not stat.S_ISLNK(info.st_mode) and not _linked(root),
          f"{bundle} root must not be or pass through a link")
    _need(stat.S_ISDIR(info.st_mode), f"{bundle} root is not a directory")
    try:
        dir_fd = _os_open(root, DIR_FLAGS)
    except OSError as exc:
        raise ReferenceError(f"{bundle} root: cannot open ({_err(exc)})") from None
    datas, primary = {}, None
    try:
        opened = os.fstat(dir_fd)
        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            raise ReferenceError(f"{bundle} root changed while opening")
        entries = set(os.listdir(dir_fd))
        if entries != set(expected):
            raise ReferenceError(f"{bundle} bundle entries differ from the pinned file set "
                                 f"(missing {sorted(set(expected) - entries)}, "
                                 f"extra {len(entries - set(expected))})")
        sizes = {}
        for name in sorted(expected):
            entry = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
            if not stat.S_ISREG(entry.st_mode):
                raise ReferenceError(f"{bundle}/{name}: not a regular non-link file")
            sizes[name] = entry.st_size
        for name in sorted(expected):
            what = f"{bundle}/{name}"
            datas[name] = read_regular(name, expected[name]["bytes"], what, dir_fd)
            if pin(datas[name]) != expected[name]:
                raise ReferenceError(f"{what}: {len(datas[name])} bytes/{sha256(datas[name])} "
                                     f"is not the pinned {expected[name]['bytes']}/"
                                     f"{expected[name]['sha256']}")
    except ReferenceError as exc:
        primary = str(exc)
    except OSError as exc:
        primary = f"{bundle} root: {_err(exc)}"
    _close_after(dir_fd, f"{bundle} root", primary)
    return datas


def _binds(obj, data, what):
    _need(type(obj) is dict and obj.get("bytes") == len(data) and type(obj.get("bytes")) is int
          and obj.get("sha256") == sha256(data), f"{what} does not bind the actual bytes")


def _admit_raw(datas):
    manifest = strict_json(datas[RAW_MANIFEST], "raw manifest")
    marker = strict_json(datas[RAW_COMPLETE], "raw completion")
    _need(type(manifest) is dict and type(marker) is dict, "raw manifest/marker must be objects")
    for obj, what in ((manifest, "raw manifest"), (marker, "raw completion")):
        _need(obj.get("schema") == 1 and type(obj.get("schema")) is int
              and obj.get("task") == RAW_TASK and obj.get("profile") == RAW_PROFILE
              and obj.get("state") == "complete", f"{what} is not the complete raw profile")
    _need(set(marker) == {"schema", "task", "profile", "state", "manifest", "outputs"},
          "raw completion keys are not the qualified schema")
    _binds(marker["manifest"], datas[RAW_MANIFEST], "raw completion manifest")
    events = strict_jsonl(datas[RAW_EVENTS], "raw events")
    lines = jsonl_count(datas[RAW_LINES], "raw source lines")
    outputs = {RAW_LINES: {"bytes": len(datas[RAW_LINES]), "rows": lines,
                           "sha256": sha256(datas[RAW_LINES])},
               RAW_EVENTS: {"bytes": len(datas[RAW_EVENTS]), "rows": len(events),
                            "sha256": sha256(datas[RAW_EVENTS])}}
    _need(marker["outputs"] == outputs and manifest.get("outputs") == outputs,
          "raw marker/manifest outputs do not bind both actual streams")
    _need(manifest.get("producer") == RAW_PRODUCER, "raw producer is not the qualified pilot")
    inputs = manifest.get("inputs")
    _need(type(inputs) is dict, "raw inputs missing")
    _need(type(inputs.get("reader")) is dict and inputs["reader"].get("sha256") == READER_SHA,
          "raw reader is not the selected snapshot reader")
    _need(type(inputs.get("snapshot_manifest")) is dict
          and inputs["snapshot_manifest"].get("sha256") == SNAPSHOT_MANIFEST_SHA,
          "raw snapshot manifest identity differs")
    _need(inputs.get("selection_manifest") == SELECTION_MANIFEST
          and inputs.get("selection_complete") == SELECTION_COMPLETE,
          "raw selection identity differs")
    counters = manifest.get("counters")
    _need(type(counters) is dict and all(counters.get(k) == v and type(counters.get(k)) is int
                                         for k, v in RAW_COUNTS.items()),
          "raw counters are not the qualified complete pilot")
    _need(lines == RAW_COUNTS["raw_lines"] and len(events) == RAW_COUNTS["framing_events"],
          "raw stream row counts differ from the qualified pilot")
    sources = manifest.get("sources")
    _need(type(sources) is list and len(sources) == 2, "raw manifest must have two sources")
    for position, source in enumerate(sources):
        _need(type(source) is dict and source.get("source_index") == position
              and type(source.get("source_index")) is int
              and source.get("selection_index") == RAW_SELECTION_INDICES[position]
              and source.get("framing") == "complete" and source.get("projection") == "complete",
              f"raw source {position} is not complete framing/projection")
        size = source.get("bytes")
        _need(_is_u(size) and source.get("certified_offset") == size,
              f"raw source {position} is not certified to its end")
        mine = [e for e in events if e.get("source_index") == position]
        source_counters = source.get("counters")
        _need(type(source_counters) is dict
              and source_counters.get("framing_events") == len(mine)
              and type(source_counters.get("framing_events")) is int,
              f"raw source {position} event count differs from the stream")
        last = mine[-1].get("span") if mine else None
        terminal = last[1] if type(last) is list and len(last) == 2 else 0
        _need(terminal == size, f"raw source {position} terminal offset differs from its bytes")
    unscanned = manifest.get("unscanned_selection_indices")
    excluded = [i for i in range(RAW_SELECTION_COUNT) if i not in RAW_SELECTION_INDICES]
    _need(type(unscanned) is list and all(type(i) is int for i in unscanned)
          and unscanned == excluded, "raw unscanned selection indices are not the 837 others")
    return manifest, events


def _admit_map(datas):
    manifest = strict_json(datas[MAP_MANIFEST], "map manifest")
    marker = strict_json(datas[MAP_COMPLETE], "map completion")
    _need(type(manifest) is dict and type(marker) is dict, "map manifest/marker must be objects")
    _need(marker == {"generator_version": MAP_GENERATOR["version"],
                     "map_cache_manifest": MAP_MANIFEST,
                     "map_cache_manifest_sha256": sha256(datas[MAP_MANIFEST]),
                     "status": "complete"}, "map completion does not bind the actual manifest")
    _need(manifest.get("status") == "complete", "map inventory is not complete")
    generator = manifest.get("generator")
    _need(type(generator) is dict and {k: generator.get(k) for k in MAP_GENERATOR} == MAP_GENERATOR,
          "map generator is not the qualified inventory")
    verifier = generator.get("snapshot_verifier")
    _need(type(verifier) is dict and verifier.get("source_sha256") == READER_SHA,
          "map snapshot verifier differs")
    inputs = manifest.get("inputs")
    _need(type(inputs) is dict and type(inputs.get("snapshot")) is dict
          and inputs["snapshot"].get("manifest_sha256") == SNAPSHOT_MANIFEST_SHA,
          "map snapshot identity differs")
    selection = inputs.get("selection")
    _need(type(selection) is dict
          and selection.get("selection-manifest.json") == SELECTION_MANIFEST
          and selection.get("selection-complete.json") == SELECTION_COMPLETE,
          "map selection identity differs")
    source = manifest.get("source")
    _need(type(source) is dict and source.get("revision") == RATHENA_REVISION,
          "map rAthena revision differs")
    profile = manifest.get("profile")
    _need(type(profile) is dict and profile.get("name") == MAP_PROFILE_NAME
          and profile.get("renewal") is True
          and type(profile.get("required_use_grf")) is int and profile["required_use_grf"] == 0
          and profile.get("required_db_path") == "db"
          and type(profile.get("map_name_length")) is int and profile["map_name_length"] == 12
          and type(profile.get("map_name_length_ext")) is int
          and profile["map_name_length_ext"] == 16
          and type(profile.get("max_mapindex")) is int and profile["max_mapindex"] == 2000,
          "map profile is not the exact Renewal use_grf 0 profile")
    index = manifest.get("index")
    state = index.get("state") if type(index) is dict else None
    _need(type(state) is dict and type(state.get("reverse")) is list
          and state.get("reverse_count") == len(state["reverse"]),
          "map index reverse state missing")
    candidates = manifest.get("candidates")
    _need(type(candidates) is list, "map candidates missing")
    _need(all(type(c) is dict and not str(c.get("disposition")).startswith("unresolved")
              for c in candidates), "complete map inventory has unresolved candidates")
    return manifest, state["reverse"], candidates


def _admit_monster(datas):
    manifest = strict_json(datas[MON_MANIFEST], "monster manifest")
    marker = strict_json(datas[MON_COMPLETE], "monster completion")
    _need(type(manifest) is dict and type(marker) is dict,
          "monster manifest/marker must be objects")
    _need(set(marker) == {"declarations_file", "declarations_sha256", "generator_version",
                          "history_file", "history_sha256", "manifest", "manifest_sha256",
                          "relationship", "status"}
          and marker["status"] == "complete"
          and marker["generator_version"] == MONSTER_GENERATOR["version"]
          and marker["manifest"] == MON_MANIFEST
          and marker["manifest_sha256"] == sha256(datas[MON_MANIFEST])
          and marker["declarations_file"] == MON_DECLARATIONS
          and marker["declarations_sha256"] == sha256(datas[MON_DECLARATIONS])
          and marker["history_file"] == MON_HISTORY
          and marker["history_sha256"] == sha256(datas[MON_HISTORY]),
          "monster completion does not bind the actual manifest and streams")
    _need(manifest.get("status") == "complete" and "stop" in manifest
          and manifest["stop"] is None and manifest.get("unresolved") == [],
          "monster projection is not complete")
    declarations = jsonl_count(datas[MON_DECLARATIONS], "monster declarations")
    histories = strict_jsonl(datas[MON_HISTORY], "monster history")
    for key, name, rows in (("records_file", MON_DECLARATIONS, declarations),
                            ("history_file", MON_HISTORY, len(histories))):
        bound = manifest.get(key)
        _need(type(bound) is dict and bound.get("file") == name
              and type(bound.get("lines")) is int and bound["lines"] == rows == MONSTER_ROWS,
              f"monster {key} does not bind {MONSTER_ROWS} actual rows")
        _binds(bound, datas[name], f"monster {key}")
    generator = manifest.get("generator")
    _need(generator == MONSTER_GENERATOR, "monster generator is not the qualified projection")
    profile = manifest.get("profile")
    _need(type(profile) is dict and profile.get("name") == MONSTER_PROFILE_NAME
          and profile.get("renewal") is True and profile.get("db_path") == "db"
          and profile.get("item_monster_sql_branch") is False
          and profile.get("should_load_generator") is False,
          "monster profile is not the exact stock Renewal YAML profile")
    inputs = manifest.get("input")
    verification = inputs.get("verification") if type(inputs) is dict else None
    _need(type(verification) is dict
          and inputs.get("snapshot_manifest_sha256") == SNAPSHOT_MANIFEST_SHA
          and verification.get("reader_sha256") == READER_SHA,
          "monster snapshot/reader identity differs")
    source = manifest.get("source")
    _need(type(source) is dict and source.get("revision") == RATHENA_REVISION,
          "monster rAthena revision differs")
    prerequisite = manifest.get("prerequisite")
    prereq_manifest = prerequisite.get("manifest") if type(prerequisite) is dict else None
    _need(type(prereq_manifest) is dict
          and prereq_manifest.get("sha256") == YAML_PREREQUISITE_SHA,
          "monster YAML prerequisite identity differs")
    return manifest, histories


def admit(raw_dir, map_dir, monster_dir):
    """Read and admit the ten artifacts; return the admitted context."""
    roots = {"raw": raw_dir, "map": map_dir, "monster": monster_dir}
    for bundle in BUNDLES:
        _need(os.path.isabs(roots[bundle]), f"{bundle} root must be an absolute path")
    real = [os.path.realpath(roots[b]) for b in BUNDLES]
    _need(len(set(real)) == 3, "the three bundle roots must be distinct")
    total = 0
    for bundle in BUNDLES:
        for name in PINS[bundle]:
            try:
                total += os.lstat(os.path.join(roots[bundle], name)).st_size
            except OSError:
                pass  # a missing entry is refused by the exact bundle check
    _need(total <= LIMITS["input_total_bytes"], "input artifacts exceed input_total_bytes")
    datas = {bundle: read_bundle(roots[bundle], bundle) for bundle in BUNDLES}
    actual_total = sum(len(d) for bundle in BUNDLES for d in datas[bundle].values())
    _need(actual_total <= LIMITS["input_total_bytes"], "input artifacts exceed input_total_bytes")
    raw_manifest, events = _admit_raw(datas["raw"])
    _, reverse, candidates = _admit_map(datas["map"])
    _, histories = _admit_monster(datas["monster"])
    inputs = {f"{bundle}/{name}": pin(datas[bundle][name])
              for bundle in BUNDLES for name in sorted(PINS[bundle])}
    return {"inputs": inputs, "raw_manifest": raw_manifest, "events": events,
            "reverse": reverse, "candidates": candidates, "histories": histories}


def producer_pin():
    path = os.path.abspath(__file__)
    data = read_regular(path, PRODUCER_CAP, "producer source")
    return {"file": PRODUCER_FILE, **pin(data)}


def build(context, producer):
    """Join, cross-check against the bound raw sources and render the publication bytes."""
    result = join_events(context["events"], context["reverse"], context["candidates"],
                         context["histories"], LIMITS)
    raw = context["raw_manifest"]
    counters = result["counters"]
    _need(counters["events"] == RAW_COUNTS["framing_events"]
          and counters["static_supported"] == RAW_COUNTS["static_supported"]
          and counters["static_gap"] == 0 and counters["suffix"] == 0,
          "joined counters disagree with the bound raw counters")
    stream = b"".join(render(row) for row in result["rows"])
    manifest = {
        "schema": 1, "task": TASK, "profile": PROFILE_NAME, "state": "complete",
        "producer": producer, "dependencies": [], "inputs": context["inputs"],
        "provenance": {"rathena_revision": RATHENA_REVISION,
                       "snapshot_manifest_sha256": SNAPSHOT_MANIFEST_SHA,
                       "selection_manifest_sha256": SELECTION_MANIFEST["sha256"],
                       "raw_producer_sha256": RAW_PRODUCER["sha256"],
                       "map_producer_sha256": MAP_GENERATOR["source_sha256"],
                       "monster_producer_sha256": MONSTER_GENERATOR["source_sha256"]},
        "raw_scope": {"sources": copy.deepcopy(raw["sources"]),
                      "unscanned_selection_indices": list(raw["unscanned_selection_indices"])},
        "output": {"file": OUTPUT_ROWS, "bytes": len(stream), "sha256": sha256(stream),
                   "rows": len(result["rows"])},
        "counters": counters, "limits": dict(LIMITS), "claims": dict(CLAIMS),
    }
    manifest_bytes = render(manifest)
    _need(len(manifest_bytes) <= LIMITS["manifest_bytes"], "manifest exceeds manifest_bytes")
    return {"stream": stream, "manifest": manifest, "manifest_bytes": manifest_bytes}


def completion_record(manifest_bytes, output):
    return {"schema": 1, "task": TASK, "profile": PROFILE_NAME, "state": "complete",
            "manifest": pin(manifest_bytes), "output": output}


# --- Publication -------------------------------------------------------------------

def _inside(path, root):
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def output_target(out_dir, input_roots=()):
    """Validate a fresh output path beneath a private trusted parent."""
    _need(os.path.isabs(out_dir), "output must be an absolute path")
    out_dir = os.path.normpath(out_dir)
    name = os.path.basename(out_dir)
    _need(name not in ("", ".", ".."), "invalid output directory name")
    parent = os.path.realpath(os.path.dirname(out_dir))
    try:
        info = os.lstat(parent)
    except OSError as exc:
        raise ReferenceError(f"output parent: {_err(exc)}") from None
    _need(stat.S_ISDIR(info.st_mode), "output parent is not a directory")
    _need(info.st_uid == os.geteuid() and not info.st_mode & 0o022,
          "output parent must be yours and not group/world writable")
    target = os.path.join(parent, name)
    _need(not os.path.lexists(target), "output already exists; refusing to overwrite")
    for root in input_roots:
        _need(not _inside(target, os.path.realpath(root)), "output collides with an input root")
    return target


def _write_new(dir_fd, name, data, owned):
    """Create `name` exclusively (0600), write fully, fsync and close; record its inode."""
    try:
        fd = _os_open(name, WRITE_FLAGS, 0o600, dir_fd=dir_fd)
    except OSError as exc:
        raise ReferenceError(f"{name}: cannot create exclusively ({_err(exc)})") from None
    primary = None
    try:
        info = os.fstat(fd)
        owned[name] = (info.st_dev, info.st_ino)
        if stat.S_IMODE(info.st_mode) != 0o600:
            os.fchmod(fd, 0o600)
        view, offset = memoryview(data), 0
        while offset < len(data):
            written = _os_write(fd, view[offset:])
            if not written or written < 0:
                primary = f"{name}: write made no progress"
                break
            offset += written
        if primary is None:
            _os_fsync(fd)
    except OSError as exc:
        primary = f"{name}: write/fsync failed ({_err(exc)})"
    _close_after(fd, name, primary)


def _check_written(dir_fd, name, identity):
    info = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
    _need(stat.S_ISREG(info.st_mode) and (info.st_dev, info.st_ino) == identity,
          f"published {name} is not the owned regular file")
    _need(stat.S_IMODE(info.st_mode) == 0o600, f"published {name} is not mode 0600")


def _read_back(dir_fd, name, expect, owned):
    _check_written(dir_fd, name, owned[name])
    data = read_regular(name, len(expect), f"published {name}", dir_fd)
    _check_written(dir_fd, name, owned[name])
    _need(data == expect, f"published {name} differs from the generated bytes")
    return data


def _revoke(dir_fd, owned, names):
    """Unlink owned files by verified inode; foreign replacements stay untouched."""
    problems = []
    for name in names:
        if name not in owned:
            continue
        try:
            info = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
        except FileNotFoundError:
            continue
        except OSError as exc:
            problems.append(f"{name}: {_err(exc)}")
            continue
        if (info.st_dev, info.st_ino) != owned[name]:
            problems.append(f"{name}: replaced by a foreign file, left untouched")
            continue
        try:
            _os_unlink(name, dir_fd=dir_fd)
        except OSError as exc:
            problems.append(f"{name}: {_err(exc)}")
    return problems


def publish(target, built):
    """Write rows, manifest and the completion record last into a fresh `target`."""
    try:
        _os_mkdir(target, 0o700)
    except OSError as exc:
        raise ReferenceError(f"output: cannot create exclusively ({_err(exc)})") from None
    try:
        made = os.lstat(target)
    except OSError as exc:
        raise ReferenceError(f"output: {_err(exc)}") from None
    identity = (made.st_dev, made.st_ino)
    try:
        dir_fd = _os_open(target, DIR_FLAGS)
    except OSError as exc:
        raise ReferenceError(f"output: cannot open created directory ({_err(exc)})") from None
    owned, dir_open, failure = {}, True, None
    close_failed, problems = False, []
    try:
        info = os.fstat(dir_fd)
        _need((info.st_dev, info.st_ino) == identity and info.st_uid == os.geteuid()
              and stat.S_IMODE(info.st_mode) == 0o700,
              "output directory is not the private directory just created")
        _write_new(dir_fd, OUTPUT_ROWS, built["stream"], owned)
        _read_back(dir_fd, OUTPUT_ROWS, built["stream"], owned)
        _write_new(dir_fd, OUTPUT_MANIFEST, built["manifest_bytes"], owned)
        manifest_back = _read_back(dir_fd, OUTPUT_MANIFEST, built["manifest_bytes"], owned)
        marker = render(completion_record(manifest_back, built["manifest"]["output"]))
        _need(len(marker) <= LIMITS["completion_bytes"], "completion exceeds completion_bytes")
        _write_new(dir_fd, OUTPUT_COMPLETE, marker, owned)
        _read_back(dir_fd, OUTPUT_COMPLETE, marker, owned)
        info = os.fstat(dir_fd)
        _need((info.st_dev, info.st_ino) == identity and stat.S_ISDIR(info.st_mode)
              and info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == 0o700,
              "output directory is no longer the owned private directory")
        _need(set(os.listdir(dir_fd)) == set(owned) == {OUTPUT_ROWS, OUTPUT_MANIFEST,
                                                        OUTPUT_COMPLETE},
              "output directory entries are not exactly the three owned files")
        for name in owned:
            _check_written(dir_fd, name, owned[name])
        _os_fsync(dir_fd)
        try:
            _os_close(dir_fd)
        except OSError as exc:
            close_failed = True
            state = _close_state(dir_fd, (*identity, stat.S_IFDIR))
            dir_open = state == "owned"
            if state in ("unknown", "foreign"):
                problems.append(f"original directory descriptor {state}; left untouched")
            raise ReferenceError(f"output directory close failed ({_err(exc)})") from None
        else:
            dir_open = False
    except (OSError, ReferenceError) as exc:
        failure = str(exc) if isinstance(exc, ReferenceError) else f"output: {_err(exc)}"
    if failure is None:
        return
    # Revoke only owned completion (marker, then manifest) by verified inode.
    revoke_fd, reopened = dir_fd if dir_open else None, False
    if revoke_fd is not None and _close_state(revoke_fd, (*identity, stat.S_IFDIR)) != "owned":
        problems.append("retained directory descriptor ownership lost; left untouched")
        revoke_fd = None
    if revoke_fd is None:
        try:
            revoke_fd = _os_open(target, DIR_FLAGS)
            reopened = True
        except OSError as exc:
            problems.append(f"cannot reopen output to revoke ({_err(exc)})")
        if revoke_fd is not None:
            try:
                info = os.fstat(revoke_fd)
                same = (info.st_dev, info.st_ino) == identity
            except OSError:
                same = False
            if not same:
                problems.append("output directory was replaced; nothing revoked")
                fd, revoke_fd = revoke_fd, None
                try:
                    _close_after(fd, "reopened output directory", None)
                except ReferenceError as exc:
                    problems.append(str(exc))
    if revoke_fd is not None:
        problems += _revoke(revoke_fd, owned, (OUTPUT_COMPLETE, OUTPUT_MANIFEST))
        try:
            _close_after(revoke_fd, "output directory", None,
                         recover=reopened or not close_failed)
        except ReferenceError as exc:
            problems.append(str(exc))
    note = f"; revocation: {'; '.join(problems)}" if problems else ""
    raise ReferenceError(f"publication failed: {failure}{note}")


def run(raw_dir, map_dir, monster_dir, output):
    """Admit, join and publish; return the built manifest."""
    roots = (raw_dir, map_dir, monster_dir)
    target = output_target(output, roots)
    context = admit(raw_dir, map_dir, monster_dir)
    built = build(context, producer_pin())
    publish(target, built)
    return built["manifest"]


# --- CLI ---------------------------------------------------------------------------

def _redact(message, roots):
    for root in sorted({r for r in roots if r}, key=len, reverse=True):
        message = message.replace(root, "<root>")
    home = os.path.expanduser("~")
    if home and home != "~":
        message = message.replace(home, "~")
    return message[:400]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw-dir", required=True, help="absolute raw pilot bundle")
    parser.add_argument("--map-dir", required=True, help="absolute map inventory bundle")
    parser.add_argument("--monster-dir", required=True, help="absolute monster projection bundle")
    parser.add_argument("--output", required=True, help="fresh private output directory")
    args = parser.parse_args(argv)
    roots = (args.raw_dir, args.map_dir, args.monster_dir, args.output)
    try:
        manifest = run(args.raw_dir, args.map_dir, args.monster_dir, args.output)
    except ReferenceError as exc:
        print(f"error: {_redact(str(exc), roots)}", file=sys.stderr)
        return 2
    except Exception as exc:  # any unexpected failure is fatal, never a partial success
        print(f"error: unexpected {type(exc).__name__}", file=sys.stderr)
        return 2
    print(render({"state": manifest["state"], "output": manifest["output"],
                  "counters": manifest["counters"]}).decode("ascii"), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
