#!/usr/bin/env python3
"""Authored tests for static_spawn_pilot.py (T06.002.003.005.001).

Run: python3 -I -B tools/renewal/test_static_spawn_pilot.py
Optional real-input checks: set STATIC_SPAWN_FROZEN_ROOT to the immutable frozen
input root (with snapshot/ and selection/); they are skipped, and reported as
skipped, without it. That variable is read only by these tests, never by the CLI.

Families F01-F10 from the frozen brief. Unit contexts are tiny verified in-memory
sources with real producer bytes and real-byte input pins; they never enter the
production CLI. Fault checks replace the producer's raw OS operation attributes.
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
SPEC = importlib.util.spec_from_file_location("static_spawn_pilot", HERE / "static_spawn_pilot.py")
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)

FROZEN = os.environ.get("STATIC_SPAWN_FROZEN_ROOT")

GOLDEN_A = r'''{
  "id": "A_grouping_and_admitted_opaque",
  "input_raw_hex": ["20092f2f780d0a2d097363726970740953092d312c7b2f2a7d2a2f227b227d0a",""],
  "unit_limits": {"completion_bytes":1048576,"each_jsonl_bytes":8388608,"framing_events":8192,"manifest_bytes":4194304,"nesting":64,"raw_lines":8192,"scanner_line_payload_bytes":65536,"source_file_bytes":262144,"source_total_bytes":524288,"static_declarations":4096},
  "expected": {
    "source_lines": [
      {"line":1,"raw_hex":"20092f2f780d0a","schema":1,"sha256":"9689a23f45af4065bbb230f604f1f35ce6ea907bba85dbda56cb94d7e522f486","source_index":0,"span":[0,7],"terminator":"crlf"},
      {"line":2,"raw_hex":"2d097363726970740953092d312c7b2f2a7d2a2f227b227d0a","schema":1,"sha256":"974a88449fa497eb49400aba854e2cb84e4020da7889c3d35d29acabddb63351","source_index":0,"span":[7,32],"terminator":"lf"}
    ],
    "events": [
      {"detail":null,"event_index":0,"kind":"whitespace","schema":1,"sha256":"d7b7af63870551553faf46d2286caf4b564ea065b0712440a9d805e2628a4e40","source_index":0,"span":[0,2]},
      {"detail":null,"event_index":1,"kind":"line_comment","schema":1,"sha256":"5d08fda298e30ebaed0b999256eda7a7b6faee81937146f7638229070e1acf5e","source_index":0,"span":[2,6]},
      {"detail":null,"event_index":2,"kind":"whitespace","schema":1,"sha256":"01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b","source_index":0,"span":[6,7]},
      {"detail":{"body":{"sha256":"b9dac12bb0b76ae21f07bb68bc26f024579a0d77495116002785a3f8e9da9157","span":[22,30]},"close":{"sha256":"d10b36aa74a59bcf4a88185837f658afaf3646eff2bb16c3928d0e9335e945d2","span":[30,31]},"header":{"sha256":"5c080112babc284126549826d4c330be3402eecdd8ae172b882c5d9190550db6","span":[7,21]},"open":{"sha256":"021fb596db81e6d02bf3d2586ee3981fe519f275c0ac9ca76bbcf2ebb4097d96","span":[21,22]}},"event_index":3,"kind":"opaque","schema":1,"sha256":"b0a5d5646ce5b2c4370cd36c8c957d439c4568488f156e1228c22f5e90ab6859","source_index":0,"span":[7,31]},
      {"detail":null,"event_index":4,"kind":"whitespace","schema":1,"sha256":"01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b","source_index":0,"span":[31,32]}
    ],
    "sources": [
      {"bytes":32,"certified_offset":32,"counters":{"certified_bytes":32,"framing_events":5,"opaque_blocks":1,"raw_bytes":32,"raw_lines":2,"static_declared":0,"static_gap":0,"static_supported":0,"suffix_events":0,"unknown_bytes":0},"framing":"complete","manifest_key":"rathena/npc/unit/a.txt","projection":"complete","reconstructed_sha256":"d87b2ba05ae5971404c5613cb55fb9cc054698f22a8d52a3beb246e3c1746541","selection_entry":{"bytes":32,"file":"npc/unit.conf","line":1,"manifest_path":"rathena/npc/unit/a.txt","phase":"npc_config","sha256":"d87b2ba05ae5971404c5613cb55fb9cc054698f22a8d52a3beb246e3c1746541","source":"npc/unit/a.txt"},"selection_index":0,"sha256":"d87b2ba05ae5971404c5613cb55fb9cc054698f22a8d52a3beb246e3c1746541","source_index":0,"source_path":"npc/unit/a.txt"},
      {"bytes":0,"certified_offset":0,"counters":{"certified_bytes":0,"framing_events":0,"opaque_blocks":0,"raw_bytes":0,"raw_lines":0,"static_declared":0,"static_gap":0,"static_supported":0,"suffix_events":0,"unknown_bytes":0},"framing":"complete","manifest_key":"rathena/npc/unit/b.txt","projection":"complete","reconstructed_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","selection_entry":{"bytes":0,"file":"npc/unit.conf","line":2,"manifest_path":"rathena/npc/unit/b.txt","phase":"npc_config","sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","source":"npc/unit/b.txt"},"selection_index":1,"sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","source_index":1,"source_path":"npc/unit/b.txt"}
    ],
    "counters": {"certified_bytes":32,"framing_events":5,"opaque_blocks":1,"raw_bytes":32,"raw_lines":2,"static_declared":0,"static_gap":0,"static_supported":0,"suffix_events":0,"unknown_bytes":0},
    "state": "complete",
    "exit_status": 0,
    "completion_allowed": true,
    "unscanned_selection_indices": [],
    "deferred_joins": {"map_cache":"not_performed","monster_history":"not_performed"},
    "outputs": {"source-lines.jsonl":{"bytes":385,"rows":2,"sha256":"6c4c4a72dad92eeca2c6422bcdeaf1537b794bb1461a68b5b8e17129c06ce3b0"},"static-spawn-pilot.jsonl":{"bytes":1245,"rows":5,"sha256":"ef9cd8e24f597492bb269541cce794bf7ebb98fbee31e9cce1286bb59db77959"}}
  }
}'''
GOLDEN_B = r'''{
  "id": "B_default_empty_and_continuation",
  "input_raw_hex": ["6d096d6f6e73746572094e09313030312c310a6d096d6f6e73746572094e09313030312c312c0a","6d09626f73735f6d6f6e73746572094e09313030312c312c352c302c310a6d09626f73735f6d6f6e73746572094e09313030312c312c352c302c0a"],
  "unit_limits": {"completion_bytes":1048576,"each_jsonl_bytes":8388608,"framing_events":8192,"manifest_bytes":4194304,"nesting":64,"raw_lines":8192,"scanner_line_payload_bytes":65536,"source_file_bytes":262144,"source_total_bytes":524288,"static_declarations":4096},
  "expected": {
    "source_lines": [
      {"line":1,"raw_hex":"6d096d6f6e73746572094e09313030312c310a","schema":1,"sha256":"cce17c19ee49f2bae36e50a1b48ee19506221256aa017dc0d7bebe6436fe824a","source_index":0,"span":[0,19],"terminator":"lf"},
      {"line":2,"raw_hex":"6d096d6f6e73746572094e09313030312c312c0a","schema":1,"sha256":"7cf1bc3e007d70bf4a6b8326f2b02214c1adf9e0c932ad661f548384aadd67c3","source_index":0,"span":[19,39],"terminator":"lf"},
      {"line":1,"raw_hex":"6d09626f73735f6d6f6e73746572094e09313030312c312c352c302c310a","schema":1,"sha256":"c10cce066da3a16a27c7f25236c0681d0ab3d14c74c47f00ebad39c72cc2c380","source_index":1,"span":[0,30],"terminator":"lf"},
      {"line":2,"raw_hex":"6d09626f73735f6d6f6e73746572094e09313030312c312c352c302c0a","schema":1,"sha256":"5acc7eda8edd38b0c183fc349da659a20a3be4a1e39858895562b8f81efdcf10","source_index":1,"span":[30,59],"terminator":"lf"}
    ],
    "events": [
      {"detail":{"fields":[{"name":"w1","raw_hex":"6d","span":[0,1]},{"name":"w2","raw_hex":"6d6f6e73746572","span":[2,9]},{"name":"w3","raw_hex":"4e","span":[10,11]},{"name":"w4","raw_hex":"313030312c31","span":[12,18]}],"gaps":[],"keyword":"monster","projection_state":"supported","tabs":3,"values":{"amount":{"origin":"declared","span":[17,18],"value":1},"delay":{"origin":"default","span":null,"value":5000},"event":{"origin":"absent","span":null,"value":null},"map":{"origin":"declared","span":[0,1],"value":"6d"},"name":{"origin":"declared","span":[10,11],"value":"4e"},"sprite":{"origin":"declared","span":[12,16],"value":1001},"variance":{"origin":"default","span":null,"value":0},"x":{"origin":"default","span":null,"value":0},"xs":{"origin":"default","span":null,"value":0},"y":{"origin":"default","span":null,"value":0},"ys":{"origin":"default","span":null,"value":0}}},"event_index":0,"kind":"static","schema":1,"sha256":"cce17c19ee49f2bae36e50a1b48ee19506221256aa017dc0d7bebe6436fe824a","source_index":0,"span":[0,19]},
      {"detail":{"fields":[{"name":"w1","raw_hex":"6d","span":[19,20]},{"name":"w2","raw_hex":"6d6f6e73746572","span":[21,28]},{"name":"w3","raw_hex":"4e","span":[29,30]},{"name":"w4","raw_hex":"313030312c312c","span":[31,38]}],"gaps":[{"code":"delay_form","span":[38,38]}],"keyword":"monster","projection_state":"gap","tabs":3,"values":null},"event_index":1,"kind":"static","schema":1,"sha256":"7cf1bc3e007d70bf4a6b8326f2b02214c1adf9e0c932ad661f548384aadd67c3","source_index":0,"span":[19,39]},
      {"detail":{"fields":[{"name":"w1","raw_hex":"6d","span":[0,1]},{"name":"w2","raw_hex":"626f73735f6d6f6e73746572","span":[2,14]},{"name":"w3","raw_hex":"4e","span":[15,16]},{"name":"w4","raw_hex":"313030312c312c352c302c31","span":[17,29]}],"gaps":[],"keyword":"boss_monster","projection_state":"supported","tabs":3,"values":{"amount":{"origin":"declared","span":[22,23],"value":1},"delay":{"origin":"declared","span":[24,25],"value":5},"event":{"origin":"declared","span":[28,29],"value":"31"},"map":{"origin":"declared","span":[0,1],"value":"6d"},"name":{"origin":"declared","span":[15,16],"value":"4e"},"sprite":{"origin":"declared","span":[17,21],"value":1001},"variance":{"origin":"declared","span":[26,27],"value":0},"x":{"origin":"default","span":null,"value":0},"xs":{"origin":"default","span":null,"value":0},"y":{"origin":"default","span":null,"value":0},"ys":{"origin":"default","span":null,"value":0}}},"event_index":2,"kind":"static","schema":1,"sha256":"c10cce066da3a16a27c7f25236c0681d0ab3d14c74c47f00ebad39c72cc2c380","source_index":1,"span":[0,30]},
      {"detail":{"fields":[{"name":"w1","raw_hex":"6d","span":[30,31]},{"name":"w2","raw_hex":"626f73735f6d6f6e73746572","span":[32,44]},{"name":"w3","raw_hex":"4e","span":[45,46]},{"name":"w4","raw_hex":"313030312c312c352c302c","span":[47,58]}],"gaps":[{"code":"event_form","span":[58,58]}],"keyword":"boss_monster","projection_state":"gap","tabs":3,"values":null},"event_index":3,"kind":"static","schema":1,"sha256":"5acc7eda8edd38b0c183fc349da659a20a3be4a1e39858895562b8f81efdcf10","source_index":1,"span":[30,59]}
    ],
    "sources": [
      {"bytes":39,"certified_offset":39,"counters":{"certified_bytes":39,"framing_events":2,"opaque_blocks":0,"raw_bytes":39,"raw_lines":2,"static_declared":2,"static_gap":1,"static_supported":1,"suffix_events":0,"unknown_bytes":0},"framing":"complete","manifest_key":"rathena/npc/unit/a.txt","projection":"gapped","reconstructed_sha256":"c6fa574909a2efe57b875839bc11d6d7d14afe79c9ef5eb6428c34a9283181f3","selection_entry":{"bytes":39,"file":"npc/unit.conf","line":1,"manifest_path":"rathena/npc/unit/a.txt","phase":"npc_config","sha256":"c6fa574909a2efe57b875839bc11d6d7d14afe79c9ef5eb6428c34a9283181f3","source":"npc/unit/a.txt"},"selection_index":0,"sha256":"c6fa574909a2efe57b875839bc11d6d7d14afe79c9ef5eb6428c34a9283181f3","source_index":0,"source_path":"npc/unit/a.txt"},
      {"bytes":59,"certified_offset":59,"counters":{"certified_bytes":59,"framing_events":2,"opaque_blocks":0,"raw_bytes":59,"raw_lines":2,"static_declared":2,"static_gap":1,"static_supported":1,"suffix_events":0,"unknown_bytes":0},"framing":"complete","manifest_key":"rathena/npc/unit/b.txt","projection":"gapped","reconstructed_sha256":"fe5cc2723ce91228eaf5dc7f1918d57a73f159fc9760050c92c140b8c1b3c690","selection_entry":{"bytes":59,"file":"npc/unit.conf","line":2,"manifest_path":"rathena/npc/unit/b.txt","phase":"npc_config","sha256":"fe5cc2723ce91228eaf5dc7f1918d57a73f159fc9760050c92c140b8c1b3c690","source":"npc/unit/b.txt"},"selection_index":1,"sha256":"fe5cc2723ce91228eaf5dc7f1918d57a73f159fc9760050c92c140b8c1b3c690","source_index":1,"source_path":"npc/unit/b.txt"}
    ],
    "counters": {"certified_bytes":98,"framing_events":4,"opaque_blocks":0,"raw_bytes":98,"raw_lines":4,"static_declared":4,"static_gap":2,"static_supported":2,"suffix_events":0,"unknown_bytes":0},
    "state": "qualified",
    "exit_status": 1,
    "completion_allowed": false,
    "unscanned_selection_indices": [],
    "deferred_joins": {"map_cache":"not_performed","monster_history":"not_performed"},
    "outputs": {"source-lines.jsonl":{"bytes":838,"rows":4,"sha256":"2e47842b156312465b859d8f365248335f055a7c9b61198b4a2eb8f3a75fc035"},"static-spawn-pilot.jsonl":{"bytes":3091,"rows":4,"sha256":"cb74aeb5ccc3dbd96aaf788514d3317edccad880956bd37689b0d280213855ca"}}
  }
}'''
GOLDEN_C = r'''{
  "id": "C_detection_cursor_and_suffix_reservation",
  "input_raw_hex": ["200a2f2a78","200a6d096d6f6e73746572094e09313030312c310a"],
  "unit_limits": {"completion_bytes":1048576,"each_jsonl_bytes":8388608,"framing_events":3,"manifest_bytes":4194304,"nesting":64,"raw_lines":8192,"scanner_line_payload_bytes":65536,"source_file_bytes":262144,"source_total_bytes":524288,"static_declarations":4096},
  "expected": {
    "source_lines": [
      {"line":1,"raw_hex":"200a","schema":1,"sha256":"e16f1596201850fd4a63680b27f603cb64e67176159be3d8ed78a4403fdb1700","source_index":0,"span":[0,2],"terminator":"lf"},
      {"line":2,"raw_hex":"2f2a78","schema":1,"sha256":"e91a1c6e20081511d31e49c00fcaffa1ad55b1ae56bab299890b62415f060e4a","source_index":0,"span":[2,5],"terminator":"none"},
      {"line":1,"raw_hex":"200a","schema":1,"sha256":"e16f1596201850fd4a63680b27f603cb64e67176159be3d8ed78a4403fdb1700","source_index":1,"span":[0,2],"terminator":"lf"},
      {"line":2,"raw_hex":"6d096d6f6e73746572094e09313030312c310a","schema":1,"sha256":"cce17c19ee49f2bae36e50a1b48ee19506221256aa017dc0d7bebe6436fe824a","source_index":1,"span":[2,21],"terminator":"lf"}
    ],
    "events": [
      {"detail":null,"event_index":0,"kind":"whitespace","schema":1,"sha256":"e16f1596201850fd4a63680b27f603cb64e67176159be3d8ed78a4403fdb1700","source_index":0,"span":[0,2]},
      {"detail":{"fault_offset":5,"reason":"unterminated_comment"},"event_index":1,"kind":"suffix","schema":1,"sha256":"e91a1c6e20081511d31e49c00fcaffa1ad55b1ae56bab299890b62415f060e4a","source_index":0,"span":[2,5]},
      {"detail":{"fault_offset":0,"reason":"not_scanned"},"event_index":2,"kind":"suffix","schema":1,"sha256":"b864e65d73e59d09a42f1b9bb9d27a6677395aa85c0546408b141bc872423c2a","source_index":1,"span":[0,21]}
    ],
    "sources": [
      {"bytes":5,"certified_offset":2,"counters":{"certified_bytes":2,"framing_events":2,"opaque_blocks":0,"raw_bytes":5,"raw_lines":2,"static_declared":0,"static_gap":0,"static_supported":0,"suffix_events":1,"unknown_bytes":3},"framing":"cutoff","manifest_key":"rathena/npc/unit/a.txt","projection":"incomplete","reconstructed_sha256":"f65ee90a65fc28f0a3849d896f98ce9b74143d48163be177edaf772cbfa7f7bb","selection_entry":{"bytes":5,"file":"npc/unit.conf","line":1,"manifest_path":"rathena/npc/unit/a.txt","phase":"npc_config","sha256":"f65ee90a65fc28f0a3849d896f98ce9b74143d48163be177edaf772cbfa7f7bb","source":"npc/unit/a.txt"},"selection_index":0,"sha256":"f65ee90a65fc28f0a3849d896f98ce9b74143d48163be177edaf772cbfa7f7bb","source_index":0,"source_path":"npc/unit/a.txt"},
      {"bytes":21,"certified_offset":0,"counters":{"certified_bytes":0,"framing_events":1,"opaque_blocks":0,"raw_bytes":21,"raw_lines":2,"static_declared":0,"static_gap":0,"static_supported":0,"suffix_events":1,"unknown_bytes":21},"framing":"cutoff","manifest_key":"rathena/npc/unit/b.txt","projection":"incomplete","reconstructed_sha256":"b864e65d73e59d09a42f1b9bb9d27a6677395aa85c0546408b141bc872423c2a","selection_entry":{"bytes":21,"file":"npc/unit.conf","line":2,"manifest_path":"rathena/npc/unit/b.txt","phase":"npc_config","sha256":"b864e65d73e59d09a42f1b9bb9d27a6677395aa85c0546408b141bc872423c2a","source":"npc/unit/b.txt"},"selection_index":1,"sha256":"b864e65d73e59d09a42f1b9bb9d27a6677395aa85c0546408b141bc872423c2a","source_index":1,"source_path":"npc/unit/b.txt"}
    ],
    "counters": {"certified_bytes":2,"framing_events":3,"opaque_blocks":0,"raw_bytes":26,"raw_lines":4,"static_declared":0,"static_gap":0,"static_supported":0,"suffix_events":2,"unknown_bytes":24},
    "state": "qualified",
    "exit_status": 1,
    "completion_allowed": false,
    "unscanned_selection_indices": [],
    "deferred_joins": {"map_cache":"not_performed","monster_history":"not_performed"},
    "outputs": {"source-lines.jsonl":{"bytes":691,"rows":4,"sha256":"aa516681089b35a17c703fd6b530c5e61ff80ac58dc4d52faba99917667d9eed"},"static-spawn-pilot.jsonl":{"bytes":583,"rows":3,"sha256":"88a85c9e3d02788e132d59de7cd813af7752d82ea8439cd1b10434faf8003b3e"}}
  }
}'''
GOLDENS = [json.loads(g) for g in (GOLDEN_A, GOLDEN_B, GOLDEN_C)]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def unit_context(datas):
    """Two-entry unit selection at npc/unit/{a,b}.txt with real-byte pins."""
    sources = []
    for i, data in enumerate(datas):
        name = "ab"[i]
        sources.append({"selection_index": i, "data": data, "entry": {
            "bytes": len(data), "file": "npc/unit.conf", "line": i + 1,
            "manifest_path": f"rathena/npc/unit/{name}.txt", "phase": "npc_config",
            "sha256": sha(data), "source": f"npc/unit/{name}.txt"}})
    selection = P.render({"npc_sources": {"files": [s["entry"] for s in sources]}})
    snapshot = P.render({"files": [{"path": s["entry"]["manifest_path"]} for s in sources]})
    reader = (HERE / "server_selection.py").read_bytes()
    complete = P.render({"selection_manifest_sha256": sha(selection)})
    return {"producer": P.producer_pin(),
            "inputs": {"reader": P.pin(reader), "snapshot_manifest": P.pin(snapshot),
                       "selection_manifest": P.pin(selection),
                       "selection_complete": P.pin(complete)},
            "sources": sources, "unscanned": []}


def limits(**override):
    result = dict(P.LIMITS)
    result.update(override)
    return result


def build(*datas, **override):
    datas = list(datas) + [b""] * (2 - len(datas))
    return P.build(unit_context(datas), limits(**override))


def events_of(result, source_index=None, kind=None):
    return [e for e in result["events"]
            if (source_index is None or e["source_index"] == source_index)
            and (kind is None or e["kind"] == kind)]


def statics(result):
    return events_of(result, kind="static")


def suffix_of(result, source_index):
    found = events_of(result, source_index, "suffix")
    return found[0] if found else None


def projection(line):
    """Static detail of a one-line source0."""
    found = statics(build(line))
    assert len(found) == 1, found
    return found[0]["detail"]


def gap_of(line):
    detail = projection(line)
    assert detail["projection_state"] == "gap" and detail["values"] is None, detail
    assert len(detail["gaps"]) == 1
    return detail["gaps"][0]["code"], detail["gaps"][0]["span"]


def check_schemas(test, result):
    """Exact key sets/types on every emitted record and the manifest."""
    for r in result["lines"]:
        test.assertEqual(set(r), {"schema", "source_index", "line", "span", "terminator",
                                  "raw_hex", "sha256"})
        test.assertIn(r["terminator"], ("lf", "crlf", "none"))
    for e in result["events"]:
        test.assertEqual(set(e), {"schema", "source_index", "event_index", "span", "sha256",
                                  "kind", "detail"})
        if e["kind"] == "static":
            d = e["detail"]
            test.assertEqual(set(d), {"keyword", "tabs", "fields", "projection_state",
                                      "values", "gaps"})
            test.assertEqual([f["name"] for f in d["fields"]], ["w1", "w2", "w3", "w4"])
            if d["values"] is not None:
                test.assertEqual(set(d["values"]), set(P.VALUE_KEYS))
                for slot in d["values"].values():
                    test.assertEqual(set(slot), {"value", "origin", "span"})
                    test.assertIsNot(type(slot["value"]), bool)
        elif e["kind"] == "opaque":
            test.assertEqual(set(e["detail"]), {"header", "open", "body", "close"})
        elif e["kind"] == "suffix":
            test.assertEqual(set(e["detail"]), {"reason", "fault_offset"})
        else:
            test.assertIsNone(e["detail"])
    m = result["manifest"]
    test.assertEqual(set(m), {"schema", "task", "profile", "state", "producer", "inputs",
                              "sources", "unscanned_selection_indices", "deferred_joins",
                              "outputs", "counters", "limits"})
    test.assertEqual(set(m["producer"]), {"file", "bytes", "sha256"})
    test.assertEqual(set(m["inputs"]), {"reader", "snapshot_manifest", "selection_manifest",
                                        "selection_complete"})
    for s in m["sources"]:
        test.assertEqual(set(s), {"source_index", "selection_index", "selection_entry",
                                  "source_path", "manifest_key", "bytes", "sha256",
                                  "reconstructed_sha256", "certified_offset", "framing",
                                  "projection", "counters"})
        test.assertEqual(set(s["counters"]), set(P.COUNTER_KEYS))
        c = s["counters"]
        test.assertEqual(c["certified_bytes"] + c["unknown_bytes"], c["raw_bytes"])
        test.assertEqual(c["static_declared"], c["static_supported"] + c["static_gap"])
    test.assertEqual(m["limits"], result["limits"])


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ssp-test-")
        os.chmod(self.tmp, 0o700)
        self.saved = {n: getattr(P, n) for n in ("_os_open", "_os_read", "_os_write",
                                                 "_os_fsync", "_os_close", "_os_mkdir",
                                                 "_os_unlink")}

    def tearDown(self):
        for name, value in self.saved.items():
            setattr(P, name, value)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def out(self, name="out"):
        return os.path.join(self.tmp, name)


# --- F01 exact goldens -------------------------------------------------------------

class F01Goldens(TempDirCase):
    def run_golden(self, golden, result=None):
        datas = [bytes.fromhex(h) for h in golden["input_raw_hex"]]
        if result is None:
            result = P.build(unit_context(datas), golden["unit_limits"])
        exp = golden["expected"]
        self.assertEqual(result["lines"], exp["source_lines"])
        self.assertEqual(result["events"], exp["events"])
        m = result["manifest"]
        self.assertEqual(m["sources"], exp["sources"])
        self.assertEqual(m["counters"], exp["counters"])
        self.assertEqual(m["state"], exp["state"])
        self.assertEqual(result["complete"], exp["completion_allowed"])
        self.assertEqual(m["unscanned_selection_indices"], exp["unscanned_selection_indices"])
        self.assertEqual(m["deferred_joins"], exp["deferred_joins"])
        self.assertEqual(m["outputs"], exp["outputs"])
        return result

    def test_goldens_records_and_publication(self):
        for golden in GOLDENS:
            with self.subTest(golden["id"]):
                datas = [bytes.fromhex(h) for h in golden["input_raw_hex"]]
                target = self.out(golden["id"])
                status, result = P.execute(unit_context(datas), target, golden["unit_limits"])
                self.run_golden(golden, result)
                check_schemas(self, result)
                self.assertEqual(status, golden["expected"]["exit_status"])
                names = sorted(os.listdir(target))
                expect = sorted([P.LINES_OUT, P.EVENTS_OUT, P.MANIFEST_OUT]
                                + ([P.COMPLETE_OUT] if status == 0 else []))
                self.assertEqual(names, expect)
                self.assertEqual(stat.S_IMODE(os.lstat(target).st_mode), 0o700)
                for name in names:
                    info = os.lstat(os.path.join(target, name))
                    self.assertTrue(stat.S_ISREG(info.st_mode))
                    self.assertEqual(stat.S_IMODE(info.st_mode), 0o600)
                lines = Path(target, P.LINES_OUT).read_bytes()
                events = Path(target, P.EVENTS_OUT).read_bytes()
                outs = golden["expected"]["outputs"]
                self.assertEqual({"bytes": len(lines), "sha256": sha(lines)},
                                 {k: outs[P.LINES_OUT][k] for k in ("bytes", "sha256")})
                self.assertEqual({"bytes": len(events), "sha256": sha(events)},
                                 {k: outs[P.EVENTS_OUT][k] for k in ("bytes", "sha256")})
                manifest_bytes = Path(target, P.MANIFEST_OUT).read_bytes()
                manifest = json.loads(manifest_bytes)
                self.assertEqual(manifest_bytes, P.render(manifest))
                self.assertEqual(manifest["schema"], 1)
                self.assertEqual(manifest["task"], "T06.002.003.005.001")
                self.assertEqual(manifest["profile"], "static-spawn-raw-v1")
                self.assertEqual(manifest["limits"], golden["unit_limits"])
                # Dynamic producer binds the actual submitted producer bytes.
                producer = (HERE / "static_spawn_pilot.py").read_bytes()
                self.assertEqual(manifest["producer"], {
                    "file": "tools/renewal/static_spawn_pilot.py", "bytes": len(producer),
                    "sha256": sha(producer)})
                reader = (HERE / "server_selection.py").read_bytes()
                self.assertEqual(manifest["inputs"]["reader"],
                                 {"bytes": len(reader), "sha256": sha(reader)})
                if status == 0:
                    marker = Path(target, P.COMPLETE_OUT).read_bytes()
                    self.assertEqual(json.loads(marker), {
                        "schema": 1, "task": "T06.002.003.005.001",
                        "profile": "static-spawn-raw-v1", "state": "complete",
                        "manifest": {"bytes": len(manifest_bytes), "sha256": sha(manifest_bytes)},
                        "outputs": outs})
                    self.assertEqual(marker, P.render(json.loads(marker)))

    def test_jsonl_encoding_is_canonical(self):
        result = build(b"m\tmonster\t\xa5\xbb\t1001,1\n")
        for line in result["events_bytes"].splitlines(keepends=True):
            obj = json.loads(line)
            self.assertEqual(line, P.render(obj))
            self.assertTrue(line.endswith(b"\n"))
            line.decode("ascii")


# --- F02 basic/defaults ----------------------------------------------------------

class F02BasicDefaults(unittest.TestCase):
    def test_w1_forms(self):
        v = projection(b"prt\tmonster\tN\t1002,1\n")["values"]
        for key in ("x", "y", "xs", "ys"):
            self.assertEqual(v[key], {"value": 0, "origin": "default", "span": None})
        v = projection(b"prt,5,-6\tmonster\tN\t1002,1\n")["values"]
        self.assertEqual(v["x"], {"value": 5, "origin": "declared", "span": [4, 5]})
        self.assertEqual(v["y"], {"value": -6, "origin": "declared", "span": [6, 8]})
        self.assertEqual(v["xs"]["origin"], "default")
        v = projection(b"prt,305,233,10,10\tmonster\tN\t1002,1\n")["values"]
        self.assertEqual([v[k]["value"] for k in ("x", "y", "xs", "ys")], [305, 233, 10, 10])
        self.assertEqual(v["ys"]["span"], [15, 17])

    def test_w4_lengths_2_to_5(self):
        v = projection(b"m\tmonster\tN\t1002,3\n")["values"]
        self.assertEqual((v["delay"], v["variance"], v["event"]), (
            {"value": 5000, "origin": "default", "span": None},
            {"value": 0, "origin": "default", "span": None},
            {"value": None, "origin": "absent", "span": None}))
        v = projection(b"m\tmonster\tN\t1002,3,7\n")["values"]
        self.assertEqual(v["delay"], {"value": 7, "origin": "declared", "span": [19, 20]})
        self.assertEqual(v["variance"]["origin"], "default")
        v = projection(b"m\tmonster\tN\t1002,3,7,9\n")["values"]
        self.assertEqual(v["variance"], {"value": 9, "origin": "declared", "span": [21, 22]})
        self.assertEqual(v["event"]["origin"], "absent")
        v = projection(b"m\tmonster\tN\t1002,3,7,9,E::On\n")["values"]
        self.assertEqual(v["event"], {"value": b"E::On".hex(), "origin": "declared",
                                      "span": [23, 28]})

    def test_omitted_versus_explicit_zero(self):
        v = projection(b"m,0,0\tmonster\tN\t1002,1,5000,0\n")["values"]
        self.assertEqual(v["x"], {"value": 0, "origin": "declared", "span": [2, 3]})
        self.assertEqual(v["variance"], {"value": 0, "origin": "declared", "span": [28, 29]})
        self.assertEqual(v["delay"], {"value": 5000, "origin": "declared", "span": [23, 27]})
        self.assertEqual(v["xs"], {"value": 0, "origin": "default", "span": None})

    def test_identical_declarations_retained(self):
        line = b"prt_fild08,0,0\tmonster\tPoring\t1002,20,5000\n"
        result = build(line * 3)
        found = statics(result)
        self.assertEqual(len(found), 3)
        self.assertEqual([e["span"] for e in found],
                         [[0, len(line)], [len(line), 2 * len(line)], [2 * len(line), 3 * len(line)]])
        self.assertEqual(len({e["sha256"] for e in found}), 1)
        self.assertEqual(result["manifest"]["counters"]["static_declared"], 3)

    def test_literal_gat_and_keyword_case(self):
        d = projection(b"prt.GaT\tBoSs_MoNsTeR\tN\t1002,1\n")
        self.assertEqual(d["keyword"], "boss_monster")
        self.assertEqual(d["fields"][1]["raw_hex"], b"BoSs_MoNsTeR".hex())
        self.assertEqual(d["values"]["map"], {"value": b"prt.GaT".hex(), "origin": "declared",
                                              "span": [0, 7]})
        self.assertEqual(projection(b"m\tMONSTER\tN\t1,1\n")["keyword"], "monster")


# --- F03 context/opaque ----------------------------------------------------------

class F03ContextOpaque(unittest.TestCase):
    LOOK = b"m\tmonster\tN\t1002,1"

    def test_comment_lookalikes(self):
        r = build(b"//" + self.LOOK + b"\n/*\n" + self.LOOK + b"\n*/\n")
        self.assertEqual([e["kind"] for e in r["events"]],
                         ["line_comment", "whitespace", "block_comment", "whitespace"])
        self.assertEqual(statics(r), [])

    def test_block_close_mid_line_then_static(self):
        r = build(b"/*x*/" + self.LOOK + b"\n")
        self.assertEqual([(e["kind"], e["span"]) for e in r["events"]],
                         [("block_comment", [0, 5]), ("static", [5, 24])])
        self.assertEqual(statics(r)[0]["detail"]["fields"][0]["span"], [5, 6])

    def test_opaque_body_monster_not_counted(self):
        src = (b"-\tscript\tS\t-1,{\n\tmonster \"m\",0,0,\"--ja--\",1002,1;\n"
               + self.LOOK + b"\n\tif (1) { end; }\n}\n" + self.LOOK + b"\n")
        r = build(src)
        kinds = [e["kind"] for e in r["events"]]
        self.assertEqual(kinds, ["opaque", "whitespace", "static"])
        self.assertEqual(r["manifest"]["counters"]["static_declared"], 1)
        self.assertEqual(r["manifest"]["counters"]["opaque_blocks"], 1)
        op = r["events"][0]["detail"]
        close = src.index(b"}\n" + self.LOOK)
        self.assertEqual(op["close"]["span"], [close, close + 1])
        self.assertEqual(op["header"]["span"], [0, 14])
        self.assertEqual(op["open"]["span"], [14, 15])
        self.assertEqual(op["body"]["span"], [15, close])

    def test_braces_in_strings_comments_and_escaped_quote(self):
        body = b'{ "}" /* } */ // }\n "a\\"}" }'
        src = b"-\tscript\tS\t-1,{" + body + b"}\n"
        r = build(src)
        self.assertEqual([e["kind"] for e in r["events"]], ["opaque", "whitespace"])
        self.assertEqual(r["events"][0]["span"], [0, len(src) - 1])

    def test_high_bit_preceding_byte_rule(self):
        # 0xA5 before the backslash: not an escape, so the next quote ends the string.
        src = b'-\tscript\tS\t-1,{"\xa5\\"}' + b"\n"
        r = build(src)
        self.assertEqual(r["events"][0]["kind"], "opaque")
        self.assertEqual(r["events"][0]["detail"]["close"]["span"], [19, 20])
        # ASCII before the backslash: the quote is escaped and the brace is string text.
        src = b'-\tscript\tS\t-1,{"a\\"}' + b"\n"
        r = build(src)
        sfx = suffix_of(r, 0)
        self.assertEqual(sfx["detail"], {"reason": "string_linebreak", "fault_offset": 20})
        self.assertEqual(sfx["span"], [0, 21])

    def test_empty_body_and_case_insensitive_script(self):
        r = build(b"-\tSCRIPT\t_x9\t-1,{}")
        d = r["events"][0]["detail"]
        self.assertEqual(d["body"]["span"], [17, 17])
        self.assertEqual(d["body"]["sha256"], sha(b""))
        self.assertEqual(r["manifest"]["state"], "complete")


# --- F04 physical hazards ----------------------------------------------------------

class F04PhysicalHazards(unittest.TestCase):
    def test_terminators_and_no_normalization(self):
        src = b"a\r\nb\n\xa5\xbbc"
        r = build(src)
        self.assertEqual([(l["span"], l["terminator"], l["raw_hex"]) for l in r["lines"]],
                         [([0, 3], "crlf", "610d0a"), ([3, 5], "lf", "620a"),
                          ([5, 8], "none", "a5bb63")])
        r = build(b"a\n")
        self.assertEqual(len(r["lines"]), 1)
        r = build(b"")
        self.assertEqual((r["lines"], r["events"]), ([], []))
        self.assertEqual(r["manifest"]["sources"][0]["framing"], "complete")
        self.assertEqual(r["manifest"]["sources"][0]["projection"], "complete")

    def test_crlf_static_fields_exclude_terminator(self):
        src = b"m\tmonster\tN\t1002,1\r\nm\tmonster\t\xa5\xbb\t1002,1\r\n"
        r = build(src)
        a, b = statics(r)
        self.assertEqual(a["span"], [0, 20])
        self.assertEqual(a["detail"]["fields"][3], {"name": "w4", "span": [12, 18],
                                                    "raw_hex": b"1002,1".hex()})
        self.assertEqual(b["detail"]["values"]["name"]["value"], "a5bb")
        self.assertEqual(r["manifest"]["state"], "complete")
        self.assertEqual(b"".join(bytes.fromhex(l["raw_hex"]) for l in r["lines"]), src)

    def test_global_hazards(self):
        ok = b"m\tmonster\tN\t1002,1\n"
        cases = [(b"\xef\xbb\xbf" + ok, "bom", 0),
                 (ok + b"x\0y\n", "nul", len(ok) + 1),
                 (ok + b"x\ry\r\n", "bare_cr", len(ok) + 1),
                 (b"a\r\r\n\0", "bare_cr", 1),
                 (b"\0\r", "nul", 0)]
        for src, reason, fault in cases:
            with self.subTest(reason=reason, fault=fault):
                r = build(src, ok)
                self.assertEqual([e["kind"] for e in events_of(r, 0)], ["suffix"])
                sfx = suffix_of(r, 0)
                self.assertEqual(sfx["span"], [0, len(src)])
                self.assertEqual(sfx["detail"], {"reason": reason, "fault_offset": fault})
                self.assertEqual(b"".join(bytes.fromhex(l["raw_hex"]) for l in r["lines"]
                                          if l["source_index"] == 0), src)
                s1 = r["manifest"]["sources"][1]
                self.assertEqual((s1["framing"], s1["projection"]), ("complete", "complete"))
                self.assertEqual(r["manifest"]["state"], "qualified")


# --- F05 headers/columns ----------------------------------------------------------

class F05HeadersColumns(unittest.TestCase):
    def test_fewer_than_three_tabs(self):
        r = build(b" \nm\tmonster\tN 1002,1\nm\tmonster\tN\t1,1\n")
        self.assertEqual(suffix_of(r, 0)["detail"],
                         {"reason": "malformed_columns", "fault_offset": 2})
        self.assertEqual(suffix_of(r, 0)["span"], [2, 37])
        self.assertEqual(statics(r), [])
        r = build(b"H{/*}*/x}")
        self.assertEqual(suffix_of(r, 0)["detail"],
                         {"reason": "malformed_columns", "fault_offset": 0})

    def test_exact_keyword_versus_spacing(self):
        for w2 in (b"monster ", b" monster", b"monsters", b"boss-monster"):
            with self.subTest(w2=w2):
                r = build(b"m\t" + w2 + b"\tN\t1,1\n")
                self.assertEqual(suffix_of(r, 0)["detail"]["reason"], "unsupported_construct")

    def test_extra_tab_stays_in_w4(self):
        d = projection(b"m\tmonster\tN\t1002,1\t5\n")
        self.assertEqual(d["tabs"], 4)
        self.assertEqual(d["fields"][3]["raw_hex"], b"1002,1\t5".hex())
        self.assertEqual(d["gaps"], [{"code": "w4_form", "span": [12, 20]}])

    def test_column_width(self):
        name = b"N" * 2047
        r = build(b"m\tmonster\t" + name + b"\t1,1\n")
        self.assertEqual(len(statics(r)), 1)
        self.assertEqual(statics(r)[0]["detail"]["gaps"][0]["code"], "name_form")
        r = build(b"m\tmonster\t" + name + b"N\t1,1\n")
        self.assertEqual(suffix_of(r, 0)["detail"],
                         {"reason": "column_width", "fault_offset": 10 + 2047})
        # Ties: both w1 and w3 overlong report w1's start + 2047.
        w1 = b"m" * 2048
        r = build(w1 + b"\tmonster\t" + name + b"NN\t1,1\n")
        self.assertEqual(suffix_of(r, 0)["detail"],
                         {"reason": "column_width", "fault_offset": 2047})
        # Column width applies to every header, including unsupported ones.
        r = build(b"m\tshop\tS\t" + b"1" * 2048 + b"\n")
        self.assertEqual(suffix_of(r, 0)["detail"]["reason"], "column_width")

    def test_unsupported_headers(self):
        heads = [b"prontera,1,1,1\tscript\tX\t1,{}\n", b"function\tscript\tF\t{}\n",
                 b"-\tscript\tS\t1,{}\n", b"-\tscript\t1bad\t-1,{}\n",
                 b"-\tscript\tS::T\t-1,{}\n", b"-\tscript\t" + b"a" * 50 + b"\t-1,{}\n",
                 b"m,1,1\tshop\tS\t1,1:1\n", b"m,1,1\twarp\tW\t1,1,n,1,1\n",
                 b"m,1,1\tduplicate(S)\tD\t1\n", b"m\tmapflag\tnosave\tSavePoint\n",
                 b"- \tscript\tS\t-1,{}\n", b"x\ty\tz\tw\n"]
        for head in heads:
            with self.subTest(head=head):
                r = build(b"\n" + head + b"m\tmonster\tN\t1,1\n")
                self.assertEqual(suffix_of(r, 0)["detail"],
                                 {"reason": "unsupported_construct", "fault_offset": 1})
                self.assertEqual(statics(r), [])
        r = build(b"-\tscript\t" + b"a" * 49 + b"\t-1,{}\n")
        self.assertEqual(r["events"][0]["kind"], "opaque")

    def test_gap_versus_cutoff(self):
        r = build(b"m\tmonster\tN\t1002\nm\tmonster\tN\t1002,1\n")
        s = r["manifest"]["sources"][0]
        self.assertEqual((s["framing"], s["projection"]), ("complete", "gapped"))
        self.assertEqual((s["counters"]["static_gap"], s["counters"]["static_supported"]), (1, 1))
        r = build(b"m\tmonster\tN\nm\tmonster\tN\t1002,1\n")
        s = r["manifest"]["sources"][0]
        self.assertEqual((s["framing"], s["projection"], s["certified_offset"]),
                         ("cutoff", "incomplete", 0))


# --- F06 numeric/byte subset ------------------------------------------------------

def line(w1=b"m", w3=b"N", w4=b"1002,1", kw=b"monster"):
    return w1 + b"\t" + kw + b"\t" + w3 + b"\t" + w4 + b"\n"


class F06NumericBytes(unittest.TestCase):
    def assert_gap(self, src, code, span):
        self.assertEqual(gap_of(src), (code, list(span)))

    def test_int16_coordinates(self):
        for x in (b"32767", b"-32768", b"0", b"-1"):
            v = projection(line(w1=b"m," + x + b",1"))["values"]
            self.assertEqual(v["x"]["value"], int(x))
        for x in (b"32768", b"-32769", b"+1", b" 1", b"1 ", b"01", b"-0", b"0x1", b"1e2",
                  b"0000001", b"", b"1.5"):
            with self.subTest(x=x):
                w1 = b"m," + x + b",1"
                self.assert_gap(line(w1=w1), "map_form", (0, len(w1)))

    def test_partial_and_extra_coordinates(self):
        for w1 in (b"m,1", b"m,1,2,3", b"m,1,2,3,4,5", b"m,,1", b",1,1", b","):
            with self.subTest(w1=w1):
                self.assert_gap(line(w1=w1), "map_form", (0, len(w1)))
        # An empty w1 leaves a leading TAB, which is top-level whitespace, not a field.
        r = build(line(w1=b""))
        self.assertEqual(r["events"][0]["kind"], "whitespace")
        self.assertEqual(suffix_of(r, 0)["detail"],
                         {"reason": "malformed_columns", "fault_offset": 1})

    def test_map_token(self):
        for w1 in (b"a" * 11, b"a" * 11 + b".gat", b"x_1.GAT"):
            self.assertEqual(projection(line(w1=w1))["values"]["map"]["value"], w1.hex())
        for w1 in (b"a" * 12, b"a" * 12 + b".gat", b"prt-f", b"p.gatx", b"\xa5\xbb",
                   b"m.gat.gat"):
            with self.subTest(w1=w1):
                self.assert_gap(line(w1=w1), "map_form", (0, len(w1)))

    def test_name_bytes(self):
        v = projection(line(w3=b"\xa5" * 23))["values"]
        self.assertEqual(v["name"]["value"], "a5" * 23)
        for w3 in (b"\xa5" * 24, b"N" * 24, b"", b"Poring,10", b"\xe5\x9c\x8b" * 8):
            with self.subTest(w3=w3):
                self.assert_gap(line(w3=w3), "name_form", (10, 10 + len(w3)))

    def test_sprite(self):
        self.assertEqual(projection(line(w4=b"2147483647,1"))["values"]["sprite"]["value"],
                         2147483647)
        self.assertEqual(projection(line(w4=b"0,1"))["values"]["sprite"]["value"], 0)
        start = 12
        for tok in (b"2147483648", b"-1", b"+1002", b"01002", b"0x3E9", b"PORING", b"1002 ",
                    b"", b"9" * 24):
            with self.subTest(tok=tok):
                self.assert_gap(line(w4=tok + b",1"), "sprite_form", (start, start + len(tok)))

    def test_amount(self):
        start = 12 + 5
        for tok, value in ((b"0", 0), (b"-5", -5), (b"1000", 1000), (b"1001", 1001),
                           (b"2147483647", 2147483647), (b"-2147483648", -2147483648)):
            v = projection(line(w4=b"1002," + tok))["values"]
            self.assertEqual(v["amount"], {"value": value, "origin": "declared",
                                           "span": [start, start + len(tok)]})
        for tok in (b"2147483648", b"-2147483649", b"+1", b"-0", b"01", b" 1", b"", b"0x10",
                    b"000000000001"):
            with self.subTest(tok=tok):
                self.assert_gap(line(w4=b"1002," + tok), "amount_form", (start, start + len(tok)))

    def test_delay_variance(self):
        start = 12 + 7
        for tok in (b"-1", b"01", b"2147483648", b"", b"5s"):
            with self.subTest(tok=tok):
                self.assert_gap(line(w4=b"1002,1," + tok), "delay_form",
                                (start, start + len(tok)))
                self.assert_gap(line(w4=b"1002,1,5," + tok), "variance_form",
                                (start + 2, start + 2 + len(tok)))
        v = projection(line(w4=b"1002,1,2147483647,2147483647"))["values"]
        self.assertEqual((v["delay"]["value"], v["variance"]["value"]), (2147483647, 2147483647))

    def test_event_bytes(self):
        start = 12 + len(b"1002,1,5,0,")
        for n in (1, 76):
            tok = b"E" * n
            v = projection(line(w4=b"1002,1,5,0," + tok))["values"]
            self.assertEqual(v["event"], {"value": tok.hex(), "origin": "declared",
                                          "span": [start, start + n]})
        for n in (0, 77, 78):
            with self.subTest(n=n):
                self.assert_gap(line(w4=b"1002,1,5,0," + b"E" * n), "event_form",
                                (start, start + n))
        quoted = b'"ant_d02_i_boss::OnMobDead"'
        v = projection(line(w4=b"1002,1,5,0," + quoted))["values"]
        self.assertEqual(v["event"]["value"], quoted.hex())

    def test_fifth_token_one_is_event_not_boss(self):
        for kw in (b"monster", b"boss_monster"):
            d = projection(line(w4=b"1147,1,7200000,600000,1", kw=kw))
            self.assertEqual(d["values"]["event"]["value"], "31")
            self.assertEqual(d["values"]["event"]["origin"], "declared")
            self.assertEqual(d["keyword"], kw.decode())
            self.assertNotIn("boss", json.dumps(d["values"]))

    def test_w4_cardinality_and_first_gap_order(self):
        self.assert_gap(line(w4=b"1002"), "w4_form", (12, 16))
        self.assert_gap(line(w4=b"1002,1,5,0,E,AI"), "w4_form", (12, 27))
        # w4 six tokens beats a bad sprite; map beats name; name beats w4.
        self.assert_gap(line(w4=b"x,1,5,0,E,AI"), "w4_form", (12, 24))
        self.assert_gap(line(w1=b"m,1", w3=b""), "map_form", (0, 3))
        self.assert_gap(line(w3=b"", w4=b"1"), "name_form", (10, 10))
        self.assert_gap(line(w4=b",x"), "sprite_form", (12, 12))
        self.assert_gap(line(w4=b"1,1,,"), "delay_form", (16, 16))


# --- F07 cutoffs ------------------------------------------------------------------

HEAD = b"-\tscript\tS\t-1,{"


class F07Cutoffs(unittest.TestCase):
    def cut(self, body, reason, fault, prefix=b"\n"):
        src = prefix + HEAD + body
        later = b"m\tmonster\tN\t1002,1\n"
        r = build(src, later)
        sfx = suffix_of(r, 0)
        self.assertEqual(sfx["detail"], {"reason": reason, "fault_offset": fault})
        self.assertEqual(sfx["span"], [len(prefix), len(src)])
        self.assertEqual(sfx["sha256"], sha(src[len(prefix):]))
        self.assertEqual(statics(r)[0]["source_index"], 1)
        self.assertEqual(r["manifest"]["sources"][1]["framing"], "complete")
        self.assertEqual(r["manifest"]["sources"][0]["counters"]["unknown_bytes"],
                         len(src) - len(prefix))
        return src

    def test_unterminated_and_escape(self):
        n = len(b"\n" + HEAD)
        look = b"\nm\tmonster\tN\t1002,1\n"
        self.cut(b' "abc', "unterminated_string", n + 5)
        self.cut(b"/* x" + look, "unterminated_comment", n + 4 + len(look))
        self.cut(look + b"{ }", "unterminated_brace", n + len(look) + 3)
        self.cut(b'"a\\', "escape_boundary", n + 3)
        self.cut(b'"a\\\nb"}', "escape_boundary", n + 3)
        self.cut(b'"ab\n"}', "string_linebreak", n + 3)
        self.cut(b'"ab\r\n"}', "string_linebreak", n + 4)

    def test_top_level_unterminated_comment(self):
        r = build(b" \n/*x\nm\tmonster\tN\t1,1\n")
        self.assertEqual(suffix_of(r, 0)["detail"],
                         {"reason": "unterminated_comment", "fault_offset": 22})
        self.assertEqual(suffix_of(r, 0)["span"], [2, 22])
        self.assertEqual(statics(r), [])

    def test_nesting_64_and_65(self):
        ok = HEAD + b"{" * 63 + b"}" * 64
        r = build(ok)
        self.assertEqual([e["kind"] for e in r["events"]], ["opaque"])
        src = self.cut(b"{" * 64 + b"}" * 65, "nesting_cap", len(b"\n" + HEAD) + 63)
        self.assertEqual(src[len(b"\n" + HEAD) + 63], ord("{"))


# --- F08 caps/reservations --------------------------------------------------------

class F08Caps(unittest.TestCase):
    def test_pre_admission_fatal(self):
        with self.assertRaisesRegex(P.PilotError, "source file byte limit"):
            build(b"abcd", source_file_bytes=3)
        with self.assertRaisesRegex(P.PilotError, "total source byte limit"):
            build(b"abc", b"abc", source_total_bytes=5)
        with self.assertRaisesRegex(P.PilotError, "raw physical line limit"):
            build(b"\n\n", b"\n", raw_lines=2)
        with self.assertRaisesRegex(P.PilotError, "below 2"):
            build(b"", framing_events=1)
        self.assertEqual(len(build(b"\n\n", b"\n", raw_lines=3)["lines"]), 3)

    def test_line_width(self):
        ok = b"m\tmonster\tN\t1,1\n"
        self.assertEqual(len(statics(build(ok, scanner_line_payload_bytes=15))), 1)
        r = build(b" \n" + ok, b"\n", scanner_line_payload_bytes=14)
        self.assertEqual([(e["kind"], e["span"]) for e in events_of(r, 0)],
                         [("whitespace", [0, 2]), ("suffix", [2, 2 + len(ok)])])
        self.assertEqual(suffix_of(r, 0)["detail"],
                         {"reason": "line_width", "fault_offset": 2 + 14})
        self.assertEqual(r["manifest"]["sources"][1]["framing"], "complete")
        # Overlong row inside an opaque body: suffix from the opaque header.
        src = b"\n" + HEAD + b"\n" + b"x" * 40 + b"\n}\n"
        r = build(src, scanner_line_payload_bytes=20)
        self.assertEqual(suffix_of(r, 0)["span"], [1, len(src)])
        self.assertEqual(suffix_of(r, 0)["detail"],
                         {"reason": "line_width", "fault_offset": len(HEAD) + 2 + 20})
        # Block comment reaching an overlong row: suffix from the opener.
        src = b"/*\n" + b"x" * 40 + b"*/\n"
        r = build(src, scanner_line_payload_bytes=20)
        self.assertEqual(suffix_of(r, 0)["span"], [0, len(src)])
        self.assertEqual(suffix_of(r, 0)["detail"]["reason"], "line_width")
        # A lexical stop reached before the overlong row wins.
        src = b"\n" + HEAD + b'"a\n' + b"x" * 40 + b"\n"
        r = build(src, scanner_line_payload_bytes=20)
        self.assertEqual(suffix_of(r, 0)["detail"]["reason"], "string_linebreak")
        # CRLF terminators are not payload.
        r = build(b"m\tmonster\tN\t1,1\r\n", scanner_line_payload_bytes=15)
        self.assertEqual(r["manifest"]["state"], "complete")

    def test_golden_c_style_reservation_and_release(self):
        # Completing a file releases its reservation.
        r = build(b" \n//x\n", b"m\tmonster\tN\t1,1\n", framing_events=3)
        self.assertEqual([(e["source_index"], e["kind"]) for e in r["events"]],
                         [(0, "whitespace"), (0, "suffix"), (1, "static")])
        self.assertEqual(suffix_of(r, 0)["detail"], {"reason": "event_cap", "fault_offset": 2})
        self.assertEqual(suffix_of(r, 0)["span"], [2, 6])
        # First file denied before any ordinary event: whole-file not_scanned.
        r = build(b" \nx", b"y", framing_events=2)
        self.assertEqual([(e["kind"], e["span"], e["detail"]) for e in r["events"]],
                         [("suffix", [0, 3], {"reason": "not_scanned", "fault_offset": 0}),
                          ("suffix", [0, 1], {"reason": "malformed_columns", "fault_offset": 0})])
        # Known lexical failure keeps its reason even when capacity is exhausted.
        r = build(b" \n \n//x\n", b"/*", framing_events=3)
        self.assertEqual(suffix_of(r, 1)["detail"],
                         {"reason": "unterminated_comment", "fault_offset": 2})
        # Empty files reserve and emit nothing.
        r = build(b"", b"m\tmonster\tN\t1,1\n", framing_events=2)
        self.assertEqual([e["kind"] for e in r["events"]], ["static"])
        self.assertEqual(r["manifest"]["state"], "complete")
        for result in (r,):
            self.assertLessEqual(len(result["events"]), 2)
        self.assertFalse([e for e in build(b"a", b"b", framing_events=2)["events"]
                          if e["span"][0] == e["span"][1]])

    def test_static_cap(self):
        src = b"m\tmonster\tN\t1,1\nm\tmonster\tN\t1,2\n"
        r = build(src, static_declarations=1)
        self.assertEqual(len(statics(r)), 1)
        self.assertEqual(suffix_of(r, 0)["detail"], {"reason": "static_cap", "fault_offset": 16})
        self.assertEqual(r["manifest"]["counters"]["static_declared"], 1)
        r = build(src, b"m\tmonster\tN\t1,3\n", static_declarations=2)
        self.assertEqual(suffix_of(r, 1)["detail"], {"reason": "static_cap", "fault_offset": 0})

    def test_lowered_nesting(self):
        r = build(HEAD + b"{}}")
        self.assertEqual(r["events"][0]["kind"], "opaque")
        r = build(HEAD + b"{{}}}", nesting=2)
        self.assertEqual(suffix_of(r, 0)["detail"],
                         {"reason": "nesting_cap", "fault_offset": len(HEAD) + 1})

    def test_output_caps_fatal(self):
        src = b"m\tmonster\tN\t1,1\n"
        full = build(src)
        with self.assertRaisesRegex(P.PilotError, "static-spawn-pilot.jsonl"):
            build(src, each_jsonl_bytes=len(full["events_bytes"]) - 1)
        with self.assertRaisesRegex(P.PilotError, "manifest"):
            build(src, manifest_bytes=100)
        self.assertEqual(build(src, each_jsonl_bytes=len(full["events_bytes"]))["complete"],
                         True)


# --- F09 prerequisites -----------------------------------------------------------

def reader_module():
    module, _ = P.load_reader(str(HERE / "server_selection.py"))
    return module


def fake_selection(reader, snap_sha="ab" * 32):
    files = []
    for i in range(P.SELECTION_COUNT):
        files.append({"bytes": 1, "file": "npc/x.conf", "line": i + 1,
                      "manifest_path": f"rathena/npc/x{i}.txt", "phase": "npc_config",
                      "sha256": "00" * 32, "source": f"npc/x{i}.txt"})
    for spec in P.PILOT:
        files[spec["selection_index"]] = P._expected_entry(spec)
    return {"generator": {"tool": P.READER_TOOL, "version": "1.0.1",
                          "source_sha256": P.READER_PIN["sha256"]},
            "input": {"snapshot_manifest_sha256": snap_sha, "files": 1683, "bytes": 68752782},
            "source": copy.deepcopy(reader.SOURCE), "profile": copy.deepcopy(reader.PROFILE),
            "status": "complete", "npc_sources": {"count": 839, "files": files}}


GOOD_COMPLETE = {"generator_version": "1.0.1", "selection_manifest": "selection-manifest.json",
                 "selection_manifest_sha256": P.SELECTION_MANIFEST_PIN["sha256"]}


class F09Prerequisites(TempDirCase):
    def test_reader_is_pinned(self):
        reader = reader_module()
        self.assertTrue(callable(reader.read_snapshot))
        copy_path = os.path.join(self.tmp, "server_selection.py")
        data = (HERE / "server_selection.py").read_bytes()
        Path(copy_path).write_bytes(data + b"\n")
        with self.assertRaisesRegex(P.PilotError, "larger than"):
            P.load_reader(copy_path)
        os.unlink(copy_path)
        Path(copy_path).write_bytes(data[:-1] + b" ")
        with self.assertRaisesRegex(P.PilotError, "not the pinned"):
            P.load_reader(copy_path)
        link = os.path.join(self.tmp, "link.py")
        os.symlink(str(HERE / "server_selection.py"), link)
        with self.assertRaisesRegex(P.PilotError, "without following links"):
            P.load_reader(link)

    def test_bind_selection_good_and_mutations(self):
        reader = reader_module()
        good = fake_selection(reader)
        files = P.bind_selection(reader, "ab" * 32, good, dict(GOOD_COMPLETE))
        self.assertEqual(len(files), 839)

        def mutated(fn, complete=None):
            sel = copy.deepcopy(good)
            fn(sel)
            return P.bind_selection, (reader, "ab" * 32, sel, complete or dict(GOOD_COMPLETE))

        def dup(sel):
            sel["npc_sources"]["files"][0] = P._expected_entry(P.PILOT[0])

        def moved(sel):
            f = sel["npc_sources"]["files"]
            f[690], f[691] = f[691], f[690]

        def swap_order(sel):
            f = sel["npc_sources"]["files"]
            f[691], f[772] = f[772], f[691]

        cases = {
            "generator sha": lambda s: s["generator"].update(source_sha256="00" * 32),
            "generator extra": lambda s: s["generator"].update(extra=1),
            "version": lambda s: s["generator"].update(version="1.0.0"),
            "source": lambda s: s["source"].update(revision="x"),
            "profile bool as int": lambda s: s["profile"].update(renewal=1),
            "profile int as bool": lambda s: s["profile"].update(map_slots=True),
            "input files bool": lambda s: s["input"].update(files=True),
            "input snapshot": lambda s: s["input"].update(snapshot_manifest_sha256="cd" * 32),
            "status": lambda s: s.update(status="incomplete"),
            "count": lambda s: s["npc_sources"].update(count=838),
            "count bool": lambda s: s["npc_sources"].update(count=True),
            "length": lambda s: s["npc_sources"]["files"].pop(),
            "duplicate occurrence": dup,
            "missing occurrence": lambda s: s["npc_sources"]["files"].__setitem__(
                772, s["npc_sources"]["files"][0]),
            "moved occurrence": moved,
            "pilot order": swap_order,
            "entry line": lambda s: s["npc_sources"]["files"][691].update(line=22),
            "entry bytes bool": lambda s: s["npc_sources"]["files"][5].update(line=True),
            "entry ordinal bool": lambda s: s["npc_sources"]["files"][691].update(bytes=True),
            "entry extra key": lambda s: s["npc_sources"]["files"][3].update(x=1),
            "entry phase": lambda s: s["npc_sources"]["files"][772].update(phase="map_config"),
        }
        for label, fn in cases.items():
            with self.subTest(label):
                f, args = mutated(fn)
                with self.assertRaises(P.PilotError):
                    f(*args)
        for label, complete in {
                "wrong sha": dict(GOOD_COMPLETE, selection_manifest_sha256="00" * 32),
                "extra key": dict(GOOD_COMPLETE, extra=1),
                "version": dict(GOOD_COMPLETE, generator_version="1.0.0"),
                "missing": {k: v for k, v in GOOD_COMPLETE.items() if k != "selection_manifest"},
        }.items():
            with self.subTest(label):
                with self.assertRaises(P.PilotError):
                    P.bind_selection(reader, "ab" * 32, copy.deepcopy(good), complete)

    def test_strict_json(self):
        for bad in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}', b'{"a":-Infinity}',
                    b'\xff', b'{"a":'):
            with self.subTest(bad=bad):
                with self.assertRaises(P.PilotError):
                    P.strict_json(bad, "x")
        self.assertEqual(P.strict_json(b'{"a":[1,true]}', "x"), {"a": [1, True]})

    def test_strict_json_nested_exponent_overflow(self):
        # parse_constant alone does not see exponent overflow through parse_float.
        for number in (b"1e309", b"-1e309"):
            for body in (b'{"nested":{"value":' + number + b'}}',
                         b'{"nested":[0,{"value":' + number + b'}]}'):
                with self.subTest(body=body):
                    with self.assertRaises(P.PilotError):
                        P.strict_json(body, "authored overflow")
        finite = P.strict_json(b'{"nested":[1e3,-1.25,0,true,null]}', "finite")
        self.assertEqual(finite, {"nested": [1000.0, -1.25, 0, True, None]})
        self.assertIs(type(finite["nested"][0]), float)
        self.assertEqual(P.strict_json(b'{"nested":["1e309","-1e309"]}', "strings"),
                         {"nested": ["1e309", "-1e309"]})

    def test_bounded_reads(self):
        path = os.path.join(self.tmp, "f")
        Path(path).write_bytes(b"abc")
        self.assertEqual(P.read_pinned(path, P.pin(b"abc"), "f"), b"abc")
        with self.assertRaisesRegex(P.PilotError, "not the pinned"):
            P.read_pinned(path, P.pin(b"abd"), "f")
        with self.assertRaisesRegex(P.PilotError, "larger than"):
            P.read_pinned(path, P.pin(b"ab"), "f")
        fifo = os.path.join(self.tmp, "fifo")
        os.mkfifo(fifo)
        with self.assertRaisesRegex(P.PilotError, "not a regular file"):
            P.read_regular(fifo, 10, "fifo")
        with self.assertRaisesRegex(P.PilotError, "not a regular file"):
            P.read_regular(self.tmp, 10, "dir")

    def test_cli_has_no_bypass(self):
        script = str(HERE / "static_spawn_pilot.py")

        def cli(*args):
            return subprocess.run([sys.executable, "-I", "-B", script, *args],
                                  capture_output=True, timeout=120)

        abs_out = self.out("o")
        self.assertEqual(cli("--snapshot", "rel", "--selection-dir", "/x", "--output",
                             abs_out).returncode, 2)
        self.assertEqual(cli("--snapshot", "/x", "--selection-dir", "/x", "--output",
                             "rel").returncode, 2)
        self.assertEqual(cli("--snapshot", "/x", "--selection-dir", "/x", "--output", abs_out,
                             "--limits", "{}").returncode, 2)
        empty = self.out("empty-snapshot")
        os.mkdir(empty)
        Path(empty, "snapshot-manifest.json").write_bytes(b"{}")
        sel_dir = self.out("sel")
        os.mkdir(sel_dir)
        r = cli("--snapshot", empty, "--selection-dir", sel_dir, "--output", abs_out)
        self.assertEqual(r.returncode, 2)
        self.assertIn(b"snapshot admission failed", r.stderr)
        self.assertNotIn(self.tmp.encode(), r.stderr)
        self.assertFalse(os.path.lexists(abs_out))

    @unittest.skipUnless(FROZEN, "STATIC_SPAWN_FROZEN_ROOT not set")
    def test_real_tampered_inputs_are_fatal(self):
        script = str(HERE / "static_spawn_pilot.py")
        snap = os.path.join(FROZEN, "snapshot")
        sel = os.path.join(FROZEN, "selection")
        work_sel = self.out("sel")
        shutil.copytree(sel, work_sel)
        os.chmod(os.path.join(work_sel, "selection-complete.json"), 0o600)
        data = Path(work_sel, "selection-complete.json").read_bytes()
        Path(work_sel, "selection-complete.json").write_bytes(data.replace(b"1.0.1", b"1.0.2"))
        r = subprocess.run([sys.executable, "-I", "-B", script, "--snapshot", snap,
                            "--selection-dir", work_sel, "--output", self.out("o1")],
                           capture_output=True, timeout=600)
        self.assertEqual(r.returncode, 2)
        self.assertIn(b"selection completion", r.stderr)
        # Full snapshot admission: one non-pilot byte or one extra file is fatal.
        work_snap = self.out("snap")
        shutil.copytree(snap, work_snap)
        victim = Path(work_snap, "rathena", "conf", "atcommands.yml")
        os.chmod(victim, 0o600)
        body = bytearray(victim.read_bytes())
        body[0] ^= 1
        victim.write_bytes(bytes(body))
        r = subprocess.run([sys.executable, "-I", "-B", script, "--snapshot", work_snap,
                            "--selection-dir", sel, "--output", self.out("o2")],
                           capture_output=True, timeout=600)
        self.assertEqual(r.returncode, 2)
        self.assertIn(b"snapshot admission failed", r.stderr)
        body[0] ^= 1
        victim.write_bytes(bytes(body))
        Path(work_snap, "rathena", "npc", "extra.txt").write_bytes(b"x")
        r = subprocess.run([sys.executable, "-I", "-B", script, "--snapshot", work_snap,
                            "--selection-dir", sel, "--output", self.out("o3")],
                           capture_output=True, timeout=600)
        self.assertEqual(r.returncode, 2)
        self.assertFalse(any(os.path.lexists(self.out(n)) for n in ("o1", "o2", "o3")))


# --- F10 publication --------------------------------------------------------------

def open_fds():
    found = set()
    for fd in range(1024):
        try:
            os.fstat(fd)
        except OSError:
            continue
        found.add(fd)
    return found


class F10Publication(TempDirCase):
    SRC = b"m\tmonster\tN\t1002,1\n"

    def context(self, *datas):
        return unit_context(list(datas or (self.SRC,)) + [b""] * (2 - len(datas or (1,))))

    def execute(self, target=None):
        return P.execute(self.context(), target or self.out(), P.LIMITS)

    def test_refusals(self):
        existing = self.out("exists")
        os.mkdir(existing)
        Path(existing, "foreign").write_bytes(b"keep")
        with self.assertRaisesRegex(P.PilotError, "already exists"):
            P.output_target(existing)
        self.assertEqual(Path(existing, "foreign").read_bytes(), b"keep")
        link = self.out("link")
        os.symlink(existing, link)
        with self.assertRaisesRegex(P.PilotError, "already exists"):
            P.output_target(link)
        self.assertTrue(os.path.islink(link))
        dangling = self.out("dangling")
        os.symlink(self.out("nowhere"), dangling)
        with self.assertRaisesRegex(P.PilotError, "already exists"):
            P.output_target(dangling)
        root = self.out("input-root")
        os.mkdir(root, 0o700)
        with self.assertRaisesRegex(P.PilotError, "collides"):
            P.output_target(os.path.join(root, "out"), (root,))
        loose = self.out("loose")
        os.mkdir(loose)
        os.chmod(loose, 0o777)
        with self.assertRaisesRegex(P.PilotError, "not group/world writable"):
            P.output_target(os.path.join(loose, "out"))
        with self.assertRaisesRegex(P.PilotError, "absolute"):
            P.output_target("relative/out")
        # A collision appearing after validation is refused by the exclusive mkdir.
        target = self.out("raced")
        os.mkdir(target)
        with self.assertRaisesRegex(P.PilotError, "cannot create exclusively"):
            self.execute(target)

    def test_short_writes_complete(self):
        real = P._os_write
        calls = []

        def short(fd, data):
            calls.append(len(data))
            return real(fd, bytes(data[:7]))

        P._os_write = short
        status, result = self.execute()
        self.assertEqual(status, 0)
        self.assertGreater(len(calls), 10)
        self.assertEqual(Path(self.out(), P.EVENTS_OUT).read_bytes(), result["events_bytes"])
        self.assertTrue(os.path.exists(os.path.join(self.out(), P.COMPLETE_OUT)))

    def assert_fatal_without_completion(self, pattern, target=None):
        before = open_fds()
        with self.assertRaisesRegex(P.PilotError, pattern):
            self.execute(target)
        self.assertEqual(open_fds(), before, "owned descriptor leaked")
        target = target or self.out()
        names = set(os.listdir(target)) if os.path.isdir(target) else set()
        self.assertNotIn(P.COMPLETE_OUT, names)
        self.assertNotIn(P.MANIFEST_OUT, names)
        return names

    def test_zero_write(self):
        real = P._os_write
        P._os_write = lambda fd, data: 0 if len(data) > 1000 else real(fd, data)
        self.assert_fatal_without_completion("no progress")

    def test_write_error_closes_once(self):
        context = self.context()
        real_close = P._os_close
        bad = []

        def write(fd, data):
            raise OSError(errno.ENOSPC, "No space left on device")

        def close(fd):
            try:
                real_close(fd)
            except OSError as exc:
                bad.append(exc)
                raise

        P._os_write, P._os_close = write, close
        before = open_fds()
        with self.assertRaisesRegex(P.PilotError, "write/fsync failed"):
            P.execute(context, self.out(), P.LIMITS)
        self.assertEqual(open_fds(), before, "owned descriptor leaked")
        self.assertEqual(bad, [], "double close")
        # The owned partial stream may remain; no manifest or marker is published.
        self.assertEqual(os.listdir(self.out()), [P.LINES_OUT])

    def fail_on(self, attr, name_hint, exc=None, after_real=False):
        """Fail `attr` for the fd opened for `name_hint` (marker by default)."""
        real_open, real = P._os_open, getattr(P, attr)
        fds = set()

        def opener(path, flags, *a, **kw):
            fd = real_open(path, flags, *a, **kw)
            if os.path.basename(str(path)) == name_hint and flags & os.O_WRONLY:
                fds.add(fd)
            elif name_hint == "<dir>" and flags & os.O_DIRECTORY and path == self.out():
                fds.add(fd)
            return fd

        def failing(fd, *a):
            if fd in fds:
                fds.discard(fd)
                if after_real:
                    real(fd, *a)
                raise exc or OSError(errno.EIO, "Input/output error")
            return real(fd, *a)

        P._os_open = opener
        setattr(P, attr, failing)

    def test_fsync_failure(self):
        self.fail_on("_os_fsync", P.MANIFEST_OUT)
        names = self.assert_fatal_without_completion("write/fsync failed")
        self.assertEqual(names, {P.LINES_OUT, P.EVENTS_OUT})

    def test_close_failure_after_real_close(self):
        self.fail_on("_os_close", P.COMPLETE_OUT, after_real=True)
        names = self.assert_fatal_without_completion("close failed")
        self.assertEqual(names, {P.LINES_OUT, P.EVENTS_OUT})

    def test_marker_open_failure(self):
        real_open = P._os_open

        def opener(path, flags, *a, **kw):
            if path == P.COMPLETE_OUT and flags & os.O_WRONLY:
                raise OSError(errno.EACCES, "Permission denied")
            return real_open(path, flags, *a, **kw)

        P._os_open = opener
        self.assert_fatal_without_completion("cannot create exclusively")

    def test_readback_failure(self):
        real_read = P._os_read

        def read(fd, n):
            data = real_read(fd, n)
            if data.startswith(b'{"counters"'):
                return b"X" + data[1:]
            return data

        P._os_read = read
        self.assert_fatal_without_completion("differs from the generated bytes")

    def test_final_directory_close_failure_revokes_marker(self):
        self.fail_on("_os_close", "<dir>", after_real=True)
        names = self.assert_fatal_without_completion("output directory close failed")
        self.assertEqual(names, {P.LINES_OUT, P.EVENTS_OUT})

    def test_directory_fsync_failure_before_close(self):
        # Failure before the real close: the owned directory fd is still closed exactly once.
        self.fail_on("_os_fsync", "<dir>")
        names = self.assert_fatal_without_completion("Input/output error")
        self.assertEqual(names, {P.LINES_OUT, P.EVENTS_OUT})

    def test_foreign_marker_collision_preserved(self):
        real_open = P._os_open
        foreign = {}

        def opener(path, flags, *a, **kw):
            if path == P.COMPLETE_OUT and flags & os.O_WRONLY and not foreign:
                dest = os.path.join(self.out(), P.COMPLETE_OUT)
                Path(dest).write_bytes(b"foreign")
                foreign["ino"] = os.lstat(dest).st_ino
            return real_open(path, flags, *a, **kw)

        P._os_open = opener
        with self.assertRaisesRegex(P.PilotError, "cannot create exclusively"):
            self.execute()
        dest = os.path.join(self.out(), P.COMPLETE_OUT)
        self.assertEqual(Path(dest).read_bytes(), b"foreign")
        self.assertEqual(os.lstat(dest).st_ino, foreign["ino"])
        self.assertNotIn(P.MANIFEST_OUT, os.listdir(self.out()))

    def test_foreign_replacement_untouched_on_later_failure(self):
        real_fsync = P._os_fsync
        state = {}

        def fsync(fd):
            info = os.fstat(fd)
            if stat.S_ISDIR(info.st_mode):
                dest = os.path.join(self.out(), P.COMPLETE_OUT)
                tmp = os.path.join(self.out(), ".foreign")
                Path(tmp).write_bytes(b"foreign")
                os.rename(tmp, dest)
                state["ino"] = os.lstat(dest).st_ino
                raise OSError(errno.EIO, "Input/output error")
            return real_fsync(fd)

        P._os_fsync = fsync
        before = open_fds()
        with self.assertRaisesRegex(P.PilotError, "foreign file, left untouched"):
            self.execute()
        self.assertEqual(open_fds(), before)
        dest = os.path.join(self.out(), P.COMPLETE_OUT)
        self.assertEqual(Path(dest).read_bytes(), b"foreign")
        self.assertEqual(os.lstat(dest).st_ino, state["ino"])
        self.assertNotIn(P.MANIFEST_OUT, os.listdir(self.out()))

    def test_completion_cap_fatal(self):
        context = self.context()
        with self.assertRaisesRegex(P.PilotError, "completion record"):
            P.execute(context, self.out(), dict(P.LIMITS, completion_bytes=10))
        self.assertEqual(set(os.listdir(self.out())), {P.LINES_OUT, P.EVENTS_OUT})

    def test_input_read_close_failure(self):
        path = os.path.join(self.tmp, "f")
        Path(path).write_bytes(b"abc")
        real_close = P._os_close

        def close(fd):
            real_close(fd)
            raise OSError(errno.EIO, "Input/output error")

        P._os_close = close
        before = open_fds()
        with self.assertRaisesRegex(P.PilotError, "close failed"):
            P.read_regular(path, 10, "f")
        self.assertEqual(open_fds(), before)

    def test_qualified_has_no_marker(self):
        status, _ = P.execute(self.context(b"m\tmonster\tN\t1002\n"), self.out(), P.LIMITS)
        self.assertEqual(status, 1)
        self.assertEqual(set(os.listdir(self.out())), {P.LINES_OUT, P.EVENTS_OUT, P.MANIFEST_OUT})


class F10CloseOwnership(TempDirCase):
    """Finite synchronous owned-FD controls; no arbitrary concurrent-reuse claim."""

    SRC = b"m\tmonster\tN\t1002,1\n"

    @staticmethod
    def fd_identity(fd):
        try:
            info = os.fstat(fd)
        except OSError as exc:
            if exc.errno == errno.EBADF:
                return None
            raise
        return info.st_dev, info.st_ino

    def close_fixture_tokens(self, tokens):
        # Called only AFTER liveness assertions. This releases observed fixture
        # leaks on a failing producer without making those observations pass.
        for token in reversed(tokens):
            if token is not None and self.fd_identity(token["fd"]) == token["identity"]:
                self.saved["_os_close"](token["fd"])

    def close_case(self, role, after_real=False, reuse_foreign=False, read_error=False):
        context = unit_context([self.SRC, b""])
        label = role + ("-reuse" if reuse_foreign else "-after" if after_real else "-before")
        target = self.out(label)
        source = self.out(label + ".source")
        Path(source).write_bytes(b"source bytes")
        os.chmod(source, 0o600)
        real_open, real_close = self.saved["_os_open"], self.saved["_os_close"]
        real_read = self.saved["_os_read"]
        opened, current = [], {}
        state = {"selected": None, "injected": False, "owned_real_closes": 0,
                 "expired_close_attempts": 0, "foreign_close_attempts": 0,
                 "read_error": False, "foreign": None}
        donor = None
        if reuse_foreign:
            donor_path = self.out(label + ".donor")
            Path(donor_path).write_bytes(b"private foreign descriptor")
            os.chmod(donor_path, 0o600)
            donor_fd = real_open(donor_path, os.O_RDONLY | os.O_NOFOLLOW)
            donor = {"fd": donor_fd, "identity": self.fd_identity(donor_fd)}
        before = open_fds()

        def selected_open(path, flags):
            path = os.fspath(path)
            access = flags & os.O_ACCMODE
            if role == "source":
                return path == source and access == os.O_RDONLY
            if role == "stream-readback":
                return path == P.LINES_OUT and access == os.O_RDONLY
            if role == "marker-write":
                return path == P.COMPLETE_OUT and access == os.O_WRONLY
            if role == "marker-readback":
                return path == P.COMPLETE_OUT and access == os.O_RDONLY
            if role == "directory":
                return path == target and bool(flags & os.O_DIRECTORY)
            raise AssertionError("unknown authored close role")

        def opener(path, flags, *args, **kwargs):
            fd = real_open(path, flags, *args, **kwargs)
            token = {"fd": fd, "identity": self.fd_identity(fd)}
            opened.append(token)
            current[fd] = token  # A later legitimate open is a NEW lifetime.
            if state["selected"] is None and selected_open(path, flags):
                state["selected"] = token
            return fd

        def closer(fd):
            identity = self.fd_identity(fd)
            foreign = state["foreign"]
            if foreign is not None and fd == foreign["fd"] and identity == foreign["identity"]:
                state["foreign_close_attempts"] += 1
            token = state["selected"]
            if token is not None and fd == token["fd"] and current.get(fd) is token:
                if identity is None:
                    state["expired_close_attempts"] += 1
                elif identity == token["identity"]:
                    if not state["injected"]:
                        state["injected"] = True
                        if after_real or reuse_foreign:
                            real_close(fd)
                            state["owned_real_closes"] += 1
                            if reuse_foreign:
                                self.assertNotEqual(token["identity"], donor["identity"])
                                self.assertNotEqual(fd, donor["fd"])
                                # Exactly this test-owned number was just closed;
                                # no arbitrary concurrent descriptor is displaced.
                                os.dup2(donor["fd"], fd)
                                state["foreign"] = {"fd": fd,
                                                    "identity": self.fd_identity(fd)}
                                self.assertEqual(state["foreign"]["identity"], donor["identity"])
                        raise OSError(errno.EIO, "authored close fault")
                    real_close(fd)
                    state["owned_real_closes"] += 1
                    return
            return real_close(fd)

        def reader(fd, count):
            token = state["selected"]
            if read_error and token is not None and fd == token["fd"] \
                    and self.fd_identity(fd) == token["identity"] and not state["read_error"]:
                state["read_error"] = True
                raise OSError(errno.EIO, "authored read fault")
            return real_read(fd, count)

        P._os_open, P._os_close, P._os_read = opener, closer, reader
        error = None
        try:
            try:
                if role == "source":
                    P.read_regular(source, 64, "authored source")
                else:
                    P.execute(context, target, P.LIMITS)
            except BaseException as exc:
                error = exc  # Keep the actual traceback alive through observation.
            # Capture real liveness BEFORE assertions or fixture cleanup can
            # unwind this scope. Number-only sets cannot identify an FD swap.
            live_owned = [(token["fd"], token["identity"]) for token in opened
                          if self.fd_identity(token["fd"]) == token["identity"]]
            observed_fds = open_fds()
            foreign = state["foreign"]
            foreign_identity = None if foreign is None else self.fd_identity(foreign["fd"])
            self.assertTrue(state["injected"], "the intended close fault was not reached")
            self.assertIsInstance(error, P.PilotError)
            if read_error:
                self.assertTrue(state["read_error"], "the primary read fault was not reached")
            self.assertEqual(live_owned, [], "owned descriptors survived failure cleanup")
            if reuse_foreign:
                self.assertIsNotNone(foreign, "the different-inode reuse was not installed")
                self.assertEqual(foreign_identity, donor["identity"],
                                 "the deliberately retained foreign FD was not preserved")
            self.assertEqual(state["owned_real_closes"], 1)
            self.assertEqual(state["expired_close_attempts"], 0, "double close on expired lifetime")
            self.assertEqual(state["foreign_close_attempts"], 0, "foreign reused FD was closed")
            expected_fds = before
            if reuse_foreign:
                os.lseek(foreign["fd"], 0, os.SEEK_SET)
                self.assertEqual(real_read(foreign["fd"], 64), b"private foreign descriptor")
                # The pre-existing number-only helper observes 0..1023; the
                # per-token identities above/ here cover every selected FD.
                if foreign["fd"] < 1024:
                    expected_fds = before | {foreign["fd"]}
            self.assertEqual(observed_fds, expected_fds, "unexpected live descriptor after failure")
            self.assertFalse(os.path.lexists(os.path.join(target, P.COMPLETE_OUT)))
        finally:
            for name, value in self.saved.items():
                setattr(P, name, value)
            self.close_fixture_tokens(opened + [state["foreign"], donor])

    def test_source_read_close_before_and_after_real_close(self):
        for after in (False, True):
            with self.subTest(after_real=after):
                self.close_case("source", after_real=after)

    def test_stream_readback_close_before_and_after_real_close(self):
        for after in (False, True):
            with self.subTest(after_real=after):
                self.close_case("stream-readback", after_real=after)

    def test_marker_write_close_before_and_after_real_close(self):
        for after in (False, True):
            with self.subTest(after_real=after):
                self.close_case("marker-write", after_real=after)

    def test_marker_readback_close_before_and_after_real_close(self):
        for after in (False, True):
            with self.subTest(after_real=after):
                self.close_case("marker-readback", after_real=after)

    def test_final_directory_close_before_and_after_real_close(self):
        for after in (False, True):
            with self.subTest(after_real=after):
                self.close_case("directory", after_real=after)

    def test_source_fd_released_when_read_and_close_both_fail(self):
        # This control verifies cleanup after both faults, not diagnostic prose.
        self.close_case("source", read_error=True)

    def test_after_real_close_different_inode_reuse_is_untouched(self):
        for role in ("source", "marker-write", "directory"):
            with self.subTest(role=role):
                self.close_case(role, reuse_foreign=True)

    def test_late_private_mode_change_is_refused(self):
        for name in (P.LINES_OUT, P.COMPLETE_OUT):
            with self.subTest(name=name):
                context = unit_context([self.SRC, b""])
                target = self.out("mode-" + name)
                real_open = self.saved["_os_open"]
                opened, changed = [], []

                def opener(path, flags, *args, **kwargs):
                    fd = real_open(path, flags, *args, **kwargs)
                    token = {"fd": fd, "identity": self.fd_identity(fd)}
                    opened.append(token)
                    if path == name and (flags & os.O_ACCMODE) == os.O_RDONLY and not changed:
                        self.assertEqual(stat.S_IMODE(os.fstat(fd).st_mode), 0o600)
                        os.fchmod(fd, 0o644)
                        self.assertEqual(stat.S_IMODE(os.fstat(fd).st_mode), 0o644)
                        changed.append(token)
                    return fd

                P._os_open = opener
                before, error = open_fds(), None
                try:
                    try:
                        P.execute(context, target, P.LIMITS)
                    except BaseException as exc:
                        error = exc  # Observe liveness before clearing the traceback.
                    live_owned = [(token["fd"], token["identity"]) for token in opened
                                  if self.fd_identity(token["fd"]) == token["identity"]]
                    observed_fds = open_fds()
                    self.assertEqual(len(changed), 1, "readback mode mutation was not reached")
                    self.assertIsInstance(error, P.PilotError)
                    self.assertEqual(live_owned, [], "owned descriptors survived mode refusal")
                    self.assertEqual(observed_fds, before)
                    self.assertFalse(os.path.lexists(os.path.join(target, P.COMPLETE_OUT)))
                finally:
                    for attr, value in self.saved.items():
                        setattr(P, attr, value)
                    self.close_fixture_tokens(opened)


# --- Negative controls: each fault must fail the comparison it targets ------------

OPAQUE_CASE = b"-\tscript\tS\t-1,{\nm\tmonster\tN\t1002,1\n}\n"


class OpaqueBodyCheck(unittest.TestCase):
    def test_body_monster_is_not_static(self):
        r = build(OPAQUE_CASE)
        self.assertEqual([e["kind"] for e in r["events"]], ["opaque", "whitespace"])
        self.assertEqual(r["manifest"]["counters"]["static_declared"], 0)


class NegativeControls(unittest.TestCase):
    """Run a real check under a deliberate producer fault; it must fail, then pass again."""

    def fails_under(self, patch, case, method):
        saved = {name: getattr(P, name) for name in patch}
        for name, fn in patch.items():
            setattr(P, name, fn)
        try:
            outcome = unittest.TestResult()
            case(method).run(outcome)
        finally:
            for name, fn in saved.items():
                setattr(P, name, fn)
        self.assertFalse(outcome.wasSuccessful(), f"{case.__name__}.{method} missed the fault")
        self.assertTrue(outcome.testsRun == 1)
        baseline = unittest.TestResult()
        case(method).run(baseline)
        self.assertTrue(baseline.wasSuccessful(), f"{case.__name__}.{method} baseline failed")

    def test_crlf_normalization(self):
        real = P.physical_lines

        def normalized(data):
            return [(a, b, c, "lf" if t == "crlf" else t) for a, b, c, t in real(data)]
        self.fails_under({"physical_lines": normalized}, F04PhysicalHazards,
                         "test_terminators_and_no_normalization")
        self.fails_under({"physical_lines": normalized}, F01Goldens,
                         "test_goldens_records_and_publication")

    def test_empty_token_default_coercion(self):
        real = P._declared_token

        def coerce(data, span, kind):
            if span[0] == span[1] and kind in ("delay", "variance"):
                return 5000 if kind == "delay" else 0
            return real(data, span, kind)
        self.fails_under({"_declared_token": coerce}, F01Goldens,
                         "test_goldens_records_and_publication")
        self.fails_under({"_declared_token": coerce}, F06NumericBytes, "test_delay_variance")

    def test_event_one_as_boss(self):
        real = P._static_detail

        def boss(data, keyword, fields, tabs):
            d = real(data, keyword, fields, tabs)
            if d["values"] and d["values"]["event"]["value"] == "31":
                d["values"]["event"] = {"value": None, "origin": "absent", "span": None}
                d["values"]["boss"] = True
            return d
        self.fails_under({"_static_detail": boss}, F06NumericBytes,
                         "test_fifth_token_one_is_event_not_boss")
        self.fails_under({"_static_detail": boss}, F01Goldens,
                         "test_goldens_records_and_publication")

    def test_suffix_byte_loss(self):
        real = P.scan

        def lossy(datas, limits, rows=None):
            events, info = real(datas, limits, rows)
            for e in events:
                if e["kind"] == "suffix" and e["span"][1] - e["span"][0] > 1:
                    e["span"] = [e["span"][0], e["span"][1] - 1]
            return events, info
        self.fails_under({"scan": lossy}, F07Cutoffs, "test_unterminated_and_escape")
        self.fails_under({"scan": lossy}, F01Goldens, "test_goldens_records_and_publication")

    def test_opaque_body_counted_as_static(self):
        real = P._candidate

        def shallow(data, pos, geo, limits):
            kind, end, detail = real(data, pos, geo, limits)
            if kind == "opaque":
                end = data.find(b"\n", pos)
                return "line_comment", end, None
            return kind, end, detail
        self.fails_under({"_candidate": shallow}, OpaqueBodyCheck,
                         "test_body_monster_is_not_static")
        self.fails_under({"_candidate": shallow}, F03ContextOpaque,
                         "test_opaque_body_monster_not_counted")

    def test_deduplicated_declarations(self):
        real = P.scan

        def dedupe(datas, limits, rows=None):
            events, info = real(datas, limits, rows)
            seen, kept = set(), []
            for e in events:
                key = (e["kind"], e["sha256"])
                if e["kind"] == "static" and key in seen:
                    continue
                seen.add(key)
                kept.append(dict(e, event_index=len(kept)))
            return kept, info
        self.fails_under({"scan": dedupe}, F02BasicDefaults,
                         "test_identical_declarations_retained")

    def test_character_based_clipping(self):
        def chars(token):
            text = token.decode("utf-8", "replace")
            return 1 <= len(text) <= 23 and not P.TOKEN_FORBIDDEN.intersection(token)
        self.fails_under({"_name_ok": chars}, F06NumericBytes, "test_name_bytes")


# --- Real frozen inputs (optional) ------------------------------------------------

@unittest.skipUnless(FROZEN, "STATIC_SPAWN_FROZEN_ROOT not set")
class RealInputs(TempDirCase):
    def test_canonical_run(self):
        script = str(HERE / "static_spawn_pilot.py")
        out = self.out("canonical")
        r = subprocess.run([sys.executable, "-I", "-B", script,
                            "--snapshot", os.path.join(FROZEN, "snapshot"),
                            "--selection-dir", os.path.join(FROZEN, "selection"),
                            "--output", out], capture_output=True, timeout=600)
        self.assertEqual(r.returncode, 0, r.stderr)
        manifest_bytes = Path(out, P.MANIFEST_OUT).read_bytes()
        m = json.loads(manifest_bytes)
        marker = json.loads(Path(out, P.COMPLETE_OUT).read_bytes())
        self.assertEqual(marker["manifest"], P.pin(manifest_bytes))
        self.assertEqual(marker["outputs"], m["outputs"])
        self.assertEqual(m["unscanned_selection_indices"],
                         [i for i in range(839) if i not in (691, 772)])
        self.assertEqual(m["deferred_joins"],
                         {"map_cache": "not_performed", "monster_history": "not_performed"})
        self.assertEqual([s["selection_index"] for s in m["sources"]], [691, 772])
        self.assertEqual(m["inputs"]["snapshot_manifest"], P.SNAPSHOT_MANIFEST_PIN)
        self.assertEqual(m["inputs"]["selection_manifest"], P.SELECTION_MANIFEST_PIN)
        self.assertEqual(m["inputs"]["selection_complete"], P.SELECTION_COMPLETE_PIN)
        self.assertEqual(m["inputs"]["reader"], P.READER_PIN)
        c = m["counters"]
        self.assertEqual((c["raw_lines"], c["framing_events"], c["static_declared"],
                          c["static_supported"], c["opaque_blocks"], c["suffix_events"]),
                         (311, 354, 192, 192, 1, 0))
        lines = [json.loads(l) for l in Path(out, P.LINES_OUT).read_bytes().splitlines()]
        events = [json.loads(l) for l in Path(out, P.EVENTS_OUT).read_bytes().splitlines()]
        for si, spec in enumerate(P.PILOT):
            own = [l for l in lines if l["source_index"] == si]
            raw = b"".join(bytes.fromhex(l["raw_hex"]) for l in own)
            self.assertEqual(sha(raw), spec["sha256"])
        starts = {si: [l["span"][0] for l in lines if l["source_index"] == si] for si in (0, 1)}

        def line_no(si, offset):
            return sum(1 for s in starts[si] if s <= offset)

        st = {si: [line_no(si, e["span"][0]) for e in events
                   if e["source_index"] == si and e["kind"] == "static"] for si in (0, 1)}
        self.assertEqual(st[0], list(range(18, 111)) + list(range(115, 123))
                         + list(range(127, 136)))
        self.assertEqual(len(st[1]), 82)
        boss = [e for e in events if e["kind"] == "static"
                and e["detail"]["keyword"] == "boss_monster"]
        self.assertEqual([(e["source_index"], line_no(0, e["span"][0])) for e in boss], [(0, 122)])
        self.assertEqual(boss[0]["detail"]["values"]["event"]["value"], "31")
        self.assertEqual(boss[0]["detail"]["values"]["name"]["value"], b"Maya".hex())
        opaque = [e for e in events if e["kind"] == "opaque"]
        self.assertEqual([(line_no(0, e["span"][0]), line_no(0, e["span"][1] - 1))
                          for e in opaque], [(137, 166)])
        p94, p97 = [e["detail"]["values"] for e in events
                    if e["source_index"] == 1 and e["kind"] == "static"
                    and line_no(1, e["span"][0]) in (94, 97)]
        for v in (p94, p97):
            self.assertEqual(v["sprite"]["value"], 1002)
            self.assertEqual(v["name"]["value"], b"Poring".hex())
        self.assertEqual(p94["amount"]["value"], 20)
        self.assertEqual(p97["amount"]["value"], 2)
        self.assertEqual([p97[k]["value"] for k in ("x", "y", "xs", "ys", "delay")],
                         [305, 233, 10, 10, 15000])
        self.assertEqual(p94["x"]["origin"], "declared")
        self.assertEqual(p97["variance"], {"value": 0, "origin": "default", "span": None})


if __name__ == "__main__":
    unittest.main(verbosity=2)
