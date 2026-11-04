#!/usr/bin/env python3
"""Authored controls for the 0.3.2 release gate (T10.010.005).

    python3 -I -W error tools/renewal/release_compatibility/test_release_gate.py

(Run the file directly. `python3 -I -m unittest <path>` maps the path to a
package import that does not exist here and fails before any test.)

Every packet here is SYNTHETIC: a synthetic manifest, executable, parser log,
app sources, text table and synthetic records, built fresh in a private
temporary directory. Only the tracked story source and native patch are read
from this checkout (read-only). Synthetic Description hashes are labelled
placeholders, not reference data. A synthetic pass proves gate behaviour
only; it is never a real-install admission.
"""

import copy
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
GATE_PATH = os.path.join(HERE, "release_gate.py")
_spec = importlib.util.spec_from_file_location("release_gate", GATE_PATH)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

STORY_DIR = os.path.join(REPO, "tools", "renewal", "chapter1_entry", "ro-solo-ch1-entry")
PATCH = os.path.join(REPO, "tools", "renewal", "native_capacity", "coin_capacity.patch")
RESOURCE = "System/OngoingQuestInfoList-tc-true-quest-text.lub"
QUEST_IDS = (18368, 18369, 18370, 18371)
STORY_FILES = {
    "story.mod_json": "mod.json",
    "story.quest_db": "db/quest_db.yml",
    "story.npc.entry": "npc/entry.txt",
    "story.npc.first_edge": "npc/first_edge.txt",
    "story.npc.fruit_village": "npc/fruit_village.txt",
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fake(label):
    return sha(("synthetic:" + label).encode())


def tracked_bytes():
    with open(gate.BUNDLED_MANIFEST, "rb") as fh:
        manifest = fh.read()
    paths = [os.path.join(STORY_DIR, rel) for rel in STORY_FILES.values()] + [PATCH, GATE_PATH]
    out = {gate.BUNDLED_MANIFEST: sha(manifest)}
    for p in paths:
        with open(p, "rb") as fh:
            out[p] = sha(fh.read())
    return out


class Packet:
    """Builds one complete, mutually consistent synthetic packet."""

    def __init__(self, root):
        self.root = root
        with open(gate.BUNDLED_MANIFEST, "rb") as fh:
            real = json.loads(fh.read().decode("utf-8"))
        self.files = {}
        for role, rel in STORY_FILES.items():
            with open(os.path.join(STORY_DIR, rel), "rb") as fh:
                self.files[role] = fh.read()
        with open(PATCH, "rb") as fh:
            self.files["native.patch"] = fh.read()
        self.files["text.mod_json"] = (json.dumps(real["text"]["mod_manifest"], ensure_ascii=False, indent=2) + "\n").encode()
        self.files["text.table"] = b"-- SYNTHETIC quest table; not the True table\nQuestInfoList = {}\n"
        for role in real["app"]["files"]:
            self.files[role] = ("// SYNTHETIC app source for %s\n" % role).encode()
        self.files["native.executable"] = b"\x7fELF SYNTHETIC patched map-server\n"
        self.files["native.parser_log"] = b"[Status]: SYNTHETIC isolated load of 3 release scripts and quest_db.yml, no errors\n"
        exe = self.files["native.executable"]
        stack = {"amount": None, "inventory": False, "cart": False, "storage": False, "guild_storage": False}
        abi = {"libc": "synthetic-libc", "loader": "/lib/ld-synthetic.so.1",
               "libraries": [{"soname": "libsynthetic.so.1", "sha256": fake("lib")}]}
        self.manifest = copy.deepcopy(real)
        m = self.manifest
        m["manifest_class"] = "synthetic"
        m["note"] = "SYNTHETIC manifest for authored gate controls only"
        m["text"]["table"].update(bytes=len(self.files["text.table"]), sha256=sha(self.files["text.table"]))
        for role in m["app"]["files"]:
            m["app"]["files"][role].update(bytes=len(self.files[role]), sha256=sha(self.files[role]))
        n = m["native"]
        n["executable"] = {"bytes": len(exe), "sha256": sha(exe)}
        n["stock_executable_sha256"] = fake("stock-exe")
        n["image_id"] = "sha256:" + fake("image")
        n["abi"] = copy.deepcopy(abi)
        n["effective_config_sha256"] = fake("config")
        staged = {r: sha(self.files[r]) for r in STORY_FILES}
        common = {"record_class": "synthetic", "qualified_by": "Root", "release_id": m["release_id"]}
        self.native = dict(common, **{
            "schema": gate.NATIVE_SCHEMA, "qualification_id": "SYNTHETIC-native-1",
            "qualification_kind": "isolated_runtime",
            "source": {"rathena_revision": n["source_revision"], "prepared_source_tree_sha256": n["prepared_source_tree_sha256"],
                       "patch_sha256": n["patch"]["sha256"], "app_commit": m["app"]["commit"], "app_tree": m["app"]["tree"]},
            "executable": {"path": "/synthetic/map-server", "bytes": len(exe), "sha256": sha(exe), "patched": True},
            "image": {"id": n["image_id"], "platform": "linux/arm64"},
            "packet_version": 20221005,
            "abi": copy.deepcopy(abi),
            "effective_config_sha256": n["effective_config_sha256"],
            "parser": {"method": "isolated_map_server_load", "log_sha256": sha(self.files["native.parser_log"]),
                       "loaded": True, "errors": 0, "release_warnings": 0,
                       "scripts": [{"path": STORY_FILES[r], "sha256": staged[r]} for r in
                                   ("story.npc.entry", "story.npc.first_edge", "story.npc.fruit_village", "story.quest_db")]},
            "builtin": {"name": "ros_ch1_coin_capacity", "registered": True, "arguments": 0,
                        "probe_observations": {"fits": 1, "no_fit": 0}},
            "stock_control": {"executable_sha256": n["stock_executable_sha256"], "builtin_registered": False, "release_rejected": True},
            "stack_restrictions": dict(stack),
            "max_amount": 30000,
        })
        env = {"executable_sha256": sha(exe), "image_id": n["image_id"], "effective_config_sha256": n["effective_config_sha256"]}
        self.facts = dict(common, **{
            "schema": gate.FACTS_SCHEMA, "qualification_id": "SYNTHETIC-facts-1", "environment": dict(env),
            "item": {"alias_resolutions": [{"source": "item_db", "alias": "Ch1_Root_Coin", "id": 1001972},
                                           {"source": "script_getitem", "alias": "Ch1_Root_Coin", "id": 1001972}],
                     "id": 1001972, "type": "Etc", "weight": 1, "stackable": True, "guid": False, "pet": False,
                     "stack_restrictions": dict(stack), "max_amount": 30000},
            "maps": {name: {"loaded": True} for name in m["routes"]["maps"]},
            "connections": [dict(c, loaded=True) for c in copy.deepcopy(m["routes"]["connections"])],
            "npc_imports": [{"path": STORY_FILES[r], "sha256": staged[r], "loaded": True}
                            for r in ("story.npc.entry", "story.npc.first_edge", "story.npc.fruit_village")],
            "quest_db": {"layers": [{"source": "db/re/quest_db.yml", "sha256": fake("base-quest-db"), "clear": False},
                                    {"source": "db/import/quest_db.yml", "sha256": staged["story.quest_db"], "clear": False}],
                         "rows": [{"id": r["id"], "title_sha256": r["title_sha256"], "source": "db/import/quest_db.yml"}
                                  for r in m["quests"]["rows"]]},
            "collisions": [],
        })
        tex = m["text_expectations"]
        recs = {str(q): {"title_sha256": tex["public_title_sha256"][str(q)],
                         "summary_sha256": tex["public_summary_sha256"][str(q)],
                         "description_sha256": [fake("SYNTHETIC-PLACEHOLDER-description-%d-%d" % (q, i)) for i in range(2)]}
                for q in QUEST_IDS}
        self.reference = {"schema": gate.REFERENCE_SCHEMA, "record_class": "synthetic", "qualified_by": "Root",
                          "reference_id": "SYNTHETIC-reference-1", "complete": True, "hash_basis": tex["hash_basis"],
                          "source_table": {"bytes": m["text"]["table"]["bytes"], "sha256": m["text"]["table"]["sha256"]},
                          "records": copy.deepcopy(recs)}
        self.array = ["System/OngoingQuestInfoList-earlier.lub", RESOURCE]
        self.text_effective = dict(common, **{
            "schema": gate.TEXT_EFFECTIVE_SCHEMA, "qualification_id": "SYNTHETIC-text-1",
            "environment": {"executable_sha256": sha(exe), "effective_config_sha256": n["effective_config_sha256"]},
            "generated_resource": {"path": RESOURCE, "bytes": m["text"]["table"]["bytes"], "sha256": m["text"]["table"]["sha256"]},
            "selected_server": "synthetic-local", "custom_quest_info": list(self.array),
            "decoder": {"langtype": 4}, "diagnostic_quest_ids": list(QUEST_IDS), "records": copy.deepcopy(recs)})
        self.packet_extra = {"expected": {"selected_server": "synthetic-local", "custom_quest_info": list(self.array)}}
        self.packet_class = "synthetic"
        self.raw = {}

    def write(self, drop=(), override_paths=None):
        root = self.root
        os.makedirs(os.path.join(root, "in"), exist_ok=True)
        payload = dict(self.files)
        records = {"native.qualification": self.native, "effective.facts": self.facts,
                   "text.reference": self.reference, "text.effective": self.text_effective}
        for role, rec in records.items():
            payload[role] = json.dumps(rec, ensure_ascii=False).encode()
        payload.update(self.raw)
        inputs = {}
        for i, (role, body) in enumerate(sorted(payload.items())):
            if role in drop:
                continue
            path = os.path.join(root, "in", "%02d-%s" % (i, role.replace("/", "_")))
            with open(path, "wb") as fh:
                fh.write(body)
            inputs[role] = {"path": path, "bytes": len(body), "sha256": sha(body)}
        for role, path in (override_paths or {}).items():
            inputs[role]["path"] = path
        self.manifest_path = os.path.join(root, "manifest.json")
        with open(self.manifest_path, "w", encoding="utf-8") as fh:
            json.dump(self.manifest, fh, ensure_ascii=False)
        packet = {"schema": gate.PACKET_SCHEMA, "record_class": self.packet_class,
                  "release_id": self.manifest["release_id"], "inputs": inputs}
        packet.update(copy.deepcopy(self.packet_extra))
        self.packet = packet
        self.packet_path = os.path.join(root, "packet.json")
        with open(self.packet_path, "w", encoding="utf-8") as fh:
            json.dump(packet, fh, ensure_ascii=False)
        return self.packet_path

    def rewrite_packet(self):
        with open(self.packet_path, "w", encoding="utf-8") as fh:
            json.dump(self.packet, fh, ensure_ascii=False)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="t10-010-005-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.p = Packet(self.tmp)

    def run_gate(self, mode="synthetic", **write):
        if not hasattr(self.p, "packet_path") or write:
            self.p.write(**write)
        manifest = self.p.manifest_path if mode == "synthetic" else gate.BUNDLED_MANIFEST
        return gate.evaluate(mode, manifest, self.p.packet_path)

    def refused(self, *codes, **write):
        r = self.run_gate(**write)
        self.assertEqual(r["status"], "refused", r["reasons"])
        self.assertFalse(r["admitted"])
        got = [x["code"] for x in r["reasons"]]
        for code in codes:
            self.assertIn(code, got, json.dumps(r["reasons"], ensure_ascii=False)[:2000])
        return r


class PositiveAndBoundary(Base):
    def test_complete_synthetic_packet_is_consistent_but_never_admitted(self):
        r = self.run_gate()
        self.assertEqual(r["reasons"], [])
        self.assertEqual(r["status"], "synthetic_consistent")
        self.assertFalse(r["admitted"])
        self.assertEqual(len(r["inputs"]), len(self.p.manifest["required_roles"]))
        self.assertTrue(gate.is_sha(r["gate"]["sha256"]))
        self.assertTrue(gate.is_sha(r["manifest"]["sha256"]))

    def test_cli_synthetic_exit_zero_and_real_exit_one(self):
        self.p.write()
        cmd = [sys.executable, "-I", GATE_PATH, "--synthetic", "--manifest", self.p.manifest_path, "--packet", self.p.packet_path]
        out = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout)["status"], "synthetic_consistent")
        out = subprocess.run([sys.executable, "-I", GATE_PATH, "--packet", self.p.packet_path],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        self.assertEqual(out.returncode, 1)
        self.assertFalse(json.loads(out.stdout)["admitted"])
        out = subprocess.run([sys.executable, "-I", GATE_PATH, "--manifest", self.p.manifest_path, "--packet", self.p.packet_path],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        self.assertEqual(out.returncode, 2, "real mode must not accept a substitute manifest")

    def test_real_mode_refuses_synthetic_packet(self):
        r = self.refused("manifest_unpinned", "packet_record_class", "native_record_class", "release_pin_mismatch", mode="real")
        self.assertEqual(r["mode"], "real")

    def test_real_mode_refuses_todays_inputs(self):
        # Tracked staged story + patch only: everything else is genuinely absent today.
        inputs = {}
        for role, rel in STORY_FILES.items():
            path = os.path.join(STORY_DIR, rel)
            with open(path, "rb") as fh:
                body = fh.read()
            inputs[role] = {"path": path, "bytes": len(body), "sha256": sha(body)}
        with open(PATCH, "rb") as fh:
            body = fh.read()
        inputs["native.patch"] = {"path": PATCH, "bytes": len(body), "sha256": sha(body)}
        path = os.path.join(self.tmp, "today.json")
        with open(path, "w") as fh:
            json.dump({"schema": gate.PACKET_SCHEMA, "record_class": "actual",
                       "release_id": "ro-solo-ch1-entry@0.3.2+tc-true-quest-text@0.1.0", "inputs": inputs}, fh)
        r = gate.evaluate("real", gate.BUNDLED_MANIFEST, path)
        self.assertEqual(r["status"], "refused")
        self.assertFalse(r["admitted"])
        codes = [x["code"] for x in r["reasons"]]
        self.assertIn("manifest_unpinned", codes)
        missing = {x["detail"] for x in r["reasons"] if x["code"] == "input_missing"}
        for role in ("native.executable", "native.qualification", "effective.facts", "text.reference", "text.effective", "text.table"):
            self.assertIn("role %s not supplied" % role, missing)
        # The staged tracked story and patch themselves match their release pins.
        self.assertNotIn("release_pin_mismatch", codes)
        for code in ("story_version_mismatch", "quest_row_missing", "route_exit_missing", "connection_block_changed"):
            self.assertNotIn(code, codes)

    def test_synthetic_mode_refuses_actual_class_records(self):
        self.p.native["record_class"] = "actual"
        self.refused("native_record_class")

    def test_actual_class_manifest_refused_in_synthetic_mode(self):
        self.p.manifest["manifest_class"] = "actual"
        self.refused("manifest_class")

    def test_no_writes_and_tracked_inputs_unchanged(self):
        before_tracked = tracked_bytes()
        self.p.write()
        snap = {}
        for dirpath, dirnames, filenames in os.walk(self.tmp):
            for name in dirnames + filenames:
                p = os.path.join(dirpath, name)
                st = os.lstat(p)
                snap[p] = (st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
        gate.evaluate("synthetic", self.p.manifest_path, self.p.packet_path)
        after = {}
        for dirpath, dirnames, filenames in os.walk(self.tmp):
            for name in dirnames + filenames:
                p = os.path.join(dirpath, name)
                st = os.lstat(p)
                after[p] = (st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
        self.assertEqual(snap, after)
        self.assertEqual(before_tracked, tracked_bytes())

    def test_reasons_are_bounded(self):
        self.p.facts["collisions"] = [{"kind": "quest", "key": str(i), "resolved": False} for i in range(200)]
        r = self.refused("collision_unresolved")
        self.assertEqual(len(r["reasons"]), gate.MAX_REASONS)
        self.assertGreater(r["reasons_truncated"], 0)
        self.assertTrue(all(len(x["detail"]) <= gate.MAX_DETAIL for x in r["reasons"]))


class NativeEvidence(Base):
    def test_missing_parser_evidence(self):
        self.refused("input_missing", drop=("native.qualification",))
        self.setUp()
        self.refused("input_missing", drop=("native.parser_log",))

    def test_stock_parser_evidence(self):
        self.p.native["executable"]["patched"] = False
        self.p.native["builtin"]["registered"] = False
        self.refused("native_stock_evidence", "native_builtin_unproven")

    def test_stock_executable_substituted(self):
        self.p.native["executable"]["sha256"] = self.p.manifest["native"]["stock_executable_sha256"]
        self.refused("native_stock_evidence", "native_executable_mismatch")

    def test_missing_stock_control(self):
        del self.p.native["stock_control"]
        self.refused("native_stock_control_missing")

    def test_stock_control_that_accepted_the_release(self):
        self.p.native["stock_control"]["release_rejected"] = False
        self.refused("native_stock_control_invalid")

    def test_host_fixture_or_label_is_not_qualification(self):
        self.p.native["qualification_kind"] = "host_fixture"
        self.p.native["parser"]["method"] = "string_search"
        self.refused("native_unqualified_kind", "native_parser_unqualified")

    def test_bare_boolean_builtin_without_probe(self):
        self.p.native["builtin"] = {"name": "ros_ch1_coin_capacity", "registered": True, "arguments": 0}
        self.refused("native_builtin_unproven")

    def test_unqualified_record(self):
        self.p.native["qualified_by"] = "worker"
        self.p.native["qualification_id"] = ""
        self.refused("native_unqualified")

    def test_changed_binary(self):
        self.p.files["native.executable"] += b"x"
        self.refused("release_pin_mismatch", "native_executable_mismatch")

    def test_changed_patch(self):
        self.p.files["native.patch"] += b"\n"
        self.p.native["source"]["patch_sha256"] = sha(self.p.files["native.patch"])
        self.refused("release_pin_mismatch", "native_source_mismatch")

    def test_changed_script(self):
        self.p.files["story.npc.entry"] += b"\n// changed\n"
        r = self.refused("release_pin_mismatch", "native_script_mismatch", "npc_import_not_effective")
        self.assertIn("story.npc.entry", [x["detail"] for x in r["reasons"] if x["code"] == "release_pin_mismatch"])

    def test_changed_config(self):
        self.p.native["effective_config_sha256"] = fake("other-config")
        self.refused("native_config_mismatch", "facts_environment_mismatch")

    def test_changed_abi(self):
        self.p.native["abi"]["libraries"][0]["sha256"] = fake("other-lib")
        self.refused("native_abi_mismatch")

    def test_wrong_platform_packet_image(self):
        self.p.native["image"]["platform"] = "linux/amd64"
        self.p.native["packet_version"] = 20200401
        self.p.native["image"]["id"] = "sha256:" + fake("other-image")
        self.refused("native_platform_mismatch", "native_packet_mismatch", "native_image_mismatch")

    def test_parser_log_rejection_marker(self):
        self.p.files["native.parser_log"] = b"[Error]: parse_line: expect command, missing function name or calling undeclared function\n"
        self.p.native["parser"]["log_sha256"] = sha(self.p.files["native.parser_log"])
        self.refused("native_parser_log_rejection")

    def test_parser_errors_recorded(self):
        self.p.native["parser"]["errors"] = 1
        self.refused("native_parser_failed")

    def test_wrong_source_revision(self):
        self.p.native["source"]["rathena_revision"] = "0" * 40
        self.refused("native_source_mismatch")


class StagingAndQuests(Base):
    def test_old_020_staging(self):
        mod = json.loads(self.p.files["story.mod_json"])
        mod["version"] = "0.2.0"
        self.p.files["story.mod_json"] = json.dumps(mod, ensure_ascii=False).encode()
        self.refused("story_superseded_staging", "release_pin_mismatch")

    def test_invented_requires_key(self):
        mod = json.loads(self.p.files["story.mod_json"])
        mod["requires"]["native"] = "ros_ch1_coin_capacity"
        self.p.files["story.mod_json"] = json.dumps(mod, ensure_ascii=False).encode()
        self.refused("story_requires_unsupported_key")

    def test_missing_18371_staged(self):
        text = self.p.files["story.quest_db"].decode()
        cut = text.index("  - Id: 18371")
        self.p.files["story.quest_db"] = text[:cut].encode()
        r = self.refused("quest_row_missing")
        self.assertIn("staged quest_db.yml lacks 18371", [x["detail"] for x in r["reasons"]])

    def test_missing_18371_effective(self):
        self.p.facts["quest_db"]["rows"] = [r for r in self.p.facts["quest_db"]["rows"] if r["id"] != 18371]
        r = self.refused("quest_row_not_effective")
        self.assertEqual([x["detail"] for x in r["reasons"]], ["18371"])

    def test_clear_staged(self):
        text = self.p.files["story.quest_db"].decode().replace("  Version: 3\n", "  Version: 3\n  Clear: true\n")
        self.p.files["story.quest_db"] = text.encode()
        self.refused("quest_db_clear")

    def test_clear_effective_layer(self):
        self.p.facts["quest_db"]["layers"][0]["clear"] = True
        r = self.refused("quest_db_clear")
        self.assertEqual(len(r["reasons"]), 1)

    def test_conflicting_imports(self):
        self.p.facts["collisions"] = [{"kind": "quest", "key": "18370", "resolved": False, "other_source": "another-mod"}]
        self.refused("collision_unresolved")
        self.setUp()
        self.p.facts["npc_imports"].append(dict(self.p.facts["npc_imports"][0]))
        self.refused("npc_import_not_effective")
        self.setUp()
        self.p.facts["quest_db"]["rows"].append({"id": 18369, "title_sha256": fake("other-title"), "source": "other"})
        self.refused("quest_row_effective_mismatch")

    def test_resolved_identical_collision_admitted_consistently(self):
        self.p.facts["collisions"] = [{"kind": "quest", "key": "18368", "resolved": True, "identical": True}]
        self.assertEqual(self.run_gate()["status"], "synthetic_consistent")

    def test_missing_map_effective(self):
        del self.p.facts["maps"]["ygg_fruit"]
        r = self.refused("route_map_not_loaded")
        self.assertEqual(r["reasons"][0]["detail"], "ygg_fruit")

    def test_missing_exit_staged(self):
        text = self.p.files["story.npc.first_edge"].decode()
        line = "ygg_fruit,71,114,0\twarp\tROSOLO_CH1_FRUIT_OUT\t1,1,ygg_edge,168,139\n"
        self.assertIn(line, text)
        self.p.files["story.npc.first_edge"] = text.replace(line, "").encode()
        r = self.refused("route_exit_missing", "connection_block_changed")
        self.assertIn("ROSOLO_CH1_FRUIT_OUT", [x["detail"] for x in r["reasons"] if x["code"] == "route_exit_missing"])

    def test_return_gate_destination_changed(self):
        text = self.p.files["story.npc.first_edge"].decode().replace('warp "prt_fild05",353,248;', 'warp "prt_fild05",1,1;')
        self.p.files["story.npc.first_edge"] = text.encode()
        r = self.refused("route_exit_missing", "connection_block_changed")
        self.assertIn("回程#ROSOLO_CH1_RET", [x["detail"] for x in r["reasons"] if x["code"] == "route_exit_missing"])

    def test_missing_exit_effective(self):
        self.p.facts["connections"] = [c for c in self.p.facts["connections"] if c["name"] != "ROSOLO_CH1_EDGE_IN"]
        self.refused("route_exit_not_effective")

    def test_missing_quest_db_import(self):
        self.p.facts["quest_db"]["layers"] = self.p.facts["quest_db"]["layers"][:1]
        self.refused("quest_db_import_missing")


class ItemFacts(Base):
    def test_wrong_alias(self):
        self.p.facts["item"]["alias_resolutions"][1]["id"] = 1001973
        self.refused("item_alias_wrong")

    def test_single_alias_source(self):
        self.p.facts["item"]["alias_resolutions"] = self.p.facts["item"]["alias_resolutions"][:1]
        self.refused("item_alias_unproven")

    def test_wrong_type(self):
        self.p.facts["item"]["type"] = "Usable"
        self.refused("item_type_wrong")

    def test_wrong_weight(self):
        self.p.facts["item"]["weight"] = 10
        self.refused("item_weight_wrong")

    def test_guid_and_pet(self):
        self.p.facts["item"]["guid"] = True
        self.p.facts["item"]["pet"] = True
        self.refused("item_guid_wrong", "item_pet_wrong")

    def test_not_stackable(self):
        self.p.facts["item"]["stackable"] = False
        self.refused("item_stackable_wrong")

    def test_unknown_fact(self):
        self.p.facts["item"]["pet"] = None
        self.refused("item_fact_unknown")

    def test_stack_unknown(self):
        self.p.facts["item"]["stack_restrictions"] = None
        self.refused("item_stack_unknown")

    def test_stack_contradiction_with_native(self):
        self.p.facts["item"]["stack_restrictions"] = {"amount": 5, "inventory": True, "cart": False, "storage": False, "guild_storage": False}
        self.refused("item_stack_contradiction")

    def test_stack_internally_contradictory(self):
        self.p.native["stack_restrictions"] = {"amount": None, "inventory": True, "cart": False, "storage": False, "guild_storage": False}
        self.refused("native_stack_contradiction")

    def test_max_amount_contradiction(self):
        self.p.facts["item"]["max_amount"] = 32767
        self.refused("item_stack_contradiction")

    def test_actual_stack_restriction_binds_when_consistent(self):
        stack = {"amount": 500, "inventory": True, "cart": False, "storage": False, "guild_storage": False}
        self.p.native["stack_restrictions"] = dict(stack)
        self.p.facts["item"]["stack_restrictions"] = dict(stack)
        self.assertEqual(self.run_gate()["status"], "synthetic_consistent")


class TextEvidence(Base):
    def test_changed_text_table(self):
        self.p.files["text.table"] += b"-- changed\n"
        self.refused("release_pin_mismatch", "text_resource_mismatch")

    def test_changed_text_manifest(self):
        mod = json.loads(self.p.files["text.mod_json"])
        mod["version"] = "0.1.1"
        self.p.files["text.mod_json"] = json.dumps(mod).encode()
        self.refused("text_manifest_mismatch")

    def test_changed_decoder(self):
        self.p.text_effective["decoder"] = {"langtype": 0}
        self.refused("text_decoder_mismatch")

    def test_changed_array_order(self):
        self.p.text_effective["custom_quest_info"] = list(reversed(self.p.array))
        self.refused("text_array_mismatch")

    def test_array_without_resource(self):
        self.p.packet_extra["expected"]["custom_quest_info"] = ["System/OngoingQuestInfoList-earlier.lub"]
        self.p.text_effective["custom_quest_info"] = ["System/OngoingQuestInfoList-earlier.lub"]
        self.refused("text_expectation_missing")

    def test_other_server(self):
        self.p.text_effective["selected_server"] = "another"
        self.refused("text_server_mismatch")

    def test_changed_description(self):
        self.p.text_effective["records"]["18371"]["description_sha256"][0] = fake("changed")
        r = self.refused("text_record_mismatch")
        self.assertIn("18371 description", [x["detail"] for x in r["reasons"]])

    def test_missing_18371_text(self):
        del self.p.text_effective["records"]["18371"]
        self.refused("text_record_missing")

    def test_reference_absent(self):
        self.refused("input_missing", drop=("text.reference",))

    def test_reference_without_descriptions(self):
        for rec in self.p.reference["records"].values():
            rec["description_sha256"] = []
        self.refused("text_reference_incomplete")

    def test_reference_incomplete_flag_and_wrong_source(self):
        self.p.reference["complete"] = False
        self.p.reference["source_table"]["sha256"] = fake("other-table")
        self.refused("text_reference_incomplete", "text_reference_source_mismatch")

    def test_reference_title_not_public_hash(self):
        self.p.reference["records"]["18370"]["summary_sha256"] = fake("x")
        self.refused("text_reference_summary_mismatch")

    def test_registration_tail_diagnostic_ids_do_not_count(self):
        self.p.text_effective["diagnostic_quest_ids"] = [21001, 16912]
        self.refused("text_diagnostic_scope")


class MalformedAndUnsafeInputs(Base):
    def test_non_json_evidence(self):
        self.p.raw["native.qualification"] = b"PASS"
        self.refused("evidence_malformed")

    def test_duplicate_keys_and_nan(self):
        self.p.raw["effective.facts"] = b'{"schema": "a", "schema": "b"}'
        self.p.raw["text.reference"] = b'{"complete": NaN}'
        r = self.refused("evidence_malformed")
        self.assertEqual(sum(1 for x in r["reasons"] if x["code"] == "evidence_malformed"), 2)

    def test_wrongly_typed_evidence(self):
        self.p.native["builtin"] = ["ros_ch1_coin_capacity"]
        self.p.native["parser"] = "ok"
        self.p.facts["item"] = "Ch1_Root_Coin"
        self.p.text_effective["records"] = []
        self.refused("native_builtin_unproven", "native_parser_unqualified", "item_alias_unproven", "text_record_missing")

    def test_incomplete_evidence(self):
        for key in ("abi", "image", "stack_restrictions", "max_amount"):
            del self.p.native[key]
        self.refused("native_abi_malformed", "native_image_malformed", "native_stack_unknown", "native_max_amount_unknown")

    def test_missing_file(self):
        self.p.write()
        os.unlink(self.p.packet["inputs"]["effective.facts"]["path"])
        r = gate.evaluate("synthetic", self.p.manifest_path, self.p.packet_path)
        self.assertIn("input_missing", [x["code"] for x in r["reasons"]])

    def test_symlink_input(self):
        self.p.write()
        target = self.p.packet["inputs"]["native.parser_log"]["path"]
        link = os.path.join(self.tmp, "link.log")
        os.symlink(target, link)
        self.p.packet["inputs"]["native.parser_log"]["path"] = link
        self.p.rewrite_packet()
        r = gate.evaluate("synthetic", self.p.manifest_path, self.p.packet_path)
        self.assertIn("input_symlink", [x["code"] for x in r["reasons"]])

    def test_symlinked_parent(self):
        self.p.write()
        alias = os.path.join(self.tmp, "alias")
        os.symlink(os.path.join(self.tmp, "in"), alias)
        path = self.p.packet["inputs"]["native.parser_log"]["path"]
        self.p.packet["inputs"]["native.parser_log"]["path"] = os.path.join(alias, os.path.basename(path))
        self.p.rewrite_packet()
        r = gate.evaluate("synthetic", self.p.manifest_path, self.p.packet_path)
        self.assertIn("input_symlink", [x["code"] for x in r["reasons"]])

    def test_directory_fifo_hardlink_relative_unnormalized(self):
        self.p.write()
        d = os.path.join(self.tmp, "dir")
        os.mkdir(d)
        fifo = os.path.join(self.tmp, "fifo")
        os.mkfifo(fifo)
        hard = os.path.join(self.tmp, "hard")
        os.link(self.p.packet["inputs"]["text.table"]["path"], hard)
        ins = self.p.packet["inputs"]
        ins["native.qualification"]["path"] = d
        ins["effective.facts"]["path"] = fifo
        ins["text.table"]["path"] = hard
        ins["text.reference"]["path"] = "relative/reference.json"
        ins["text.effective"]["path"] = self.tmp + "/in/../in/x.json"
        self.p.rewrite_packet()
        r = gate.evaluate("synthetic", self.p.manifest_path, self.p.packet_path)
        codes = [x["code"] for x in r["reasons"]]
        for code in ("input_not_regular", "input_hardlinked", "input_path_not_absolute", "input_path_not_normalized"):
            self.assertIn(code, codes)
        self.assertEqual(codes.count("input_not_regular"), 2)

    def test_oversized_input(self):
        self.p.raw["text.reference"] = b" " * (gate.JSON_CAP + 1)
        self.refused("input_too_large")

    def test_packet_pin_mismatch(self):
        self.p.write()
        self.p.packet["inputs"]["effective.facts"]["sha256"] = "0" * 64
        self.p.rewrite_packet()
        r = gate.evaluate("synthetic", self.p.manifest_path, self.p.packet_path)
        self.assertIn("packet_pin_mismatch", [x["code"] for x in r["reasons"]])

    def test_unknown_role_and_missing_packet(self):
        self.p.raw["private.autodiscovered"] = b"{}"
        self.refused("packet_unknown_role")
        r = gate.evaluate("synthetic", self.p.manifest_path, os.path.join(self.tmp, "absent.json"))
        self.assertEqual([x["code"] for x in r["reasons"]], ["packet_input_missing"])
        r = gate.evaluate("synthetic", self.p.manifest_path, None)
        self.assertEqual(r["status"], "refused")

    def test_malformed_packet_and_manifest(self):
        self.p.write()
        with open(self.p.packet_path, "w") as fh:
            fh.write("[]")
        r = gate.evaluate("synthetic", self.p.manifest_path, self.p.packet_path)
        self.assertEqual([x["code"] for x in r["reasons"]], ["packet_malformed"])
        with open(self.p.manifest_path, "w") as fh:
            fh.write("{")
        r = gate.evaluate("synthetic", self.p.manifest_path, self.p.packet_path)
        self.assertEqual([x["code"] for x in r["reasons"]], ["manifest_malformed"])


if __name__ == "__main__":
    unittest.main()
