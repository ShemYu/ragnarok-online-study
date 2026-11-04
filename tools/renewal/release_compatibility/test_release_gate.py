#!/usr/bin/env python3
"""Authored controls for the 0.3.2 release gate (T10.010.005).

    python3 -I -B -W error tools/renewal/release_compatibility/test_release_gate.py

(Run the file directly. `python3 -I -m unittest <path>` maps the path to a
package import that does not exist here and fails before any test.)

Every packet here is SYNTHETIC. Each test builds, in its own private
temporary directory:

- a synthetic manifest whose expected pins are explicitly authored for that
  test;
- a synthetic executable, parser log, effective configuration, app sources
  and text table;
- synthetic records;
- two staged folders.

The staged story folder copies the tracked story source, and the native
patch is read from this checkout. Both are only read. No test writes inside
the checkout. Synthetic Description hashes are labelled private placeholders,
not reference data. A synthetic pass proves gate behaviour only; it is never
a real-install admission.
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
from unittest import mock

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
TEXT_FILES = {"text.mod_json": "mod.json", "text.table": RESOURCE}
RECORD_ROLES = ("native.qualification", "effective.facts", "text.reference", "text.effective")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fake(label):
    return sha(("synthetic:" + label).encode())


def tracked_snapshot():
    paths = [gate.BUNDLED_MANIFEST, PATCH, GATE_PATH] + [os.path.join(STORY_DIR, rel) for rel in STORY_FILES.values()]
    out = {}
    for p in paths:
        st = os.lstat(p)
        with open(p, "rb") as fh:
            out[p] = (sha(fh.read()), st.st_ino, st.st_mtime_ns, st.st_ctime_ns)
    return out


class Packet:
    """Builds one complete, mutually consistent synthetic packet.

    write(repin=True) authors fresh synthetic expected pins for every file
    and record. write(repin=False) keeps the expected pins from the previous
    write: that models a coherent caller change without Root re-pinning."""

    def __init__(self, root):
        self.root = root
        with open(gate.BUNDLED_MANIFEST, "rb") as fh:
            real = json.loads(fh.read().decode("utf-8"))
        self.files = {}
        for role, rel in STORY_FILES.items():
            with open(os.path.join(STORY_DIR, rel), "rb") as fh:
                self.files[role] = fh.read()
        self.files["text.mod_json"] = (json.dumps(real["text"]["mod_manifest"], ensure_ascii=False, indent=2) + "\n").encode()
        self.files["text.table"] = b"-- SYNTHETIC quest table; not the True table\nQuestInfoList = {}\n"
        with open(PATCH, "rb") as fh:
            self.files["native.patch"] = fh.read()
        for role in real["app"]["files"]:
            self.files[role] = ("// SYNTHETIC app source for %s\n" % role).encode()
        self.files["native.executable"] = b"\x7fELF SYNTHETIC patched map-server\n"
        self.files["native.parser_log"] = b"[Status]: SYNTHETIC isolated load of 3 release scripts and quest_db.yml, no errors\n"
        self.files["effective.config"] = b"# SYNTHETIC effective map-server configuration bundle\n"
        self.extra_staged = {}
        self.staged_links = {}
        self.manifest = copy.deepcopy(real)
        m = self.manifest
        m["manifest_class"] = "synthetic"
        m["note"] = "SYNTHETIC manifest for authored gate controls only; every expected pin here is authored"
        n = m["native"]
        n["stock_executable_sha256"] = fake("stock-exe")
        n["image_id"] = "sha256:" + fake("image")
        abi = {"libc": "synthetic-libc", "loader": "/lib/ld-synthetic.so.1",
               "libraries": [{"soname": "libsynthetic.so.1", "sha256": fake("lib")}]}
        n["abi"] = copy.deepcopy(abi)
        stack = {"amount": None, "inventory": False, "cart": False, "storage": False, "guild_storage": False}
        common = {"record_class": "synthetic", "release_id": m["release_id"]}
        self.native = dict(common, **{
            "schema": gate.NATIVE_SCHEMA, "qualification_id": "SYNTHETIC-native-1",
            "qualification_kind": "isolated_runtime",
            "source": {"rathena_revision": n["source_revision"], "prepared_source_tree_sha256": n["prepared_source_tree_sha256"],
                       "patch_sha256": n["patch"]["sha256"], "app_commit": m["app"]["commit"], "app_tree": m["app"]["tree"]},
            "executable": {"path": "/synthetic/map-server", "patched": True},
            "image": {"id": n["image_id"], "platform": "linux/arm64"},
            "packet_version": 20221005,
            "abi": copy.deepcopy(abi),
            "parser": {"method": "isolated_map_server_load", "loaded": True, "errors": 0, "release_warnings": 0},
            "builtin": {"name": "ros_ch1_coin_capacity", "registered": True, "arguments": 0,
                        "probe_observations": {"fits": 1, "no_fit": 0}},
            "stock_control": {"executable_sha256": n["stock_executable_sha256"], "builtin_registered": False, "release_rejected": True},
            "stack_restrictions": dict(stack),
            "max_amount": 30000,
        })
        self.facts = dict(common, **{
            "schema": gate.FACTS_SCHEMA, "qualification_id": "SYNTHETIC-facts-1",
            "item": {"alias_resolutions": [{"source": "item_db", "alias": "Ch1_Root_Coin", "id": 1001972},
                                           {"source": "script_getitem", "alias": "Ch1_Root_Coin", "id": 1001972}],
                     "id": 1001972, "type": "Etc", "weight": 1, "stackable": True, "guid": False, "pet": False,
                     "stack_restrictions": dict(stack), "max_amount": 30000},
            "maps": {name: {"loaded": True} for name in m["routes"]["maps"]},
            "connections": [dict(c, loaded=True) for c in copy.deepcopy(m["routes"]["connections"])],
            "quest_db": {"layers": [{"source": "db/re/quest_db.yml", "sha256": fake("base-quest-db"), "clear": False}],
                         "rows": [{"id": r["id"], "title_sha256": r["title_sha256"], "source": "db/import/quest_db.yml"}
                                  for r in m["quests"]["rows"]]},
            "collisions": [],
        })
        tex = m["text_expectations"]
        recs = {}
        for q in QUEST_IDS:
            desc = [fake("SYNTHETIC-PRIVATE-PLACEHOLDER-description-%d-%d" % (q, i)) for i in range(2)]
            recs[str(q)] = {"title_sha256": tex["public_title_sha256"][str(q)],
                            "summary_sha256": tex["public_summary_sha256"][str(q)],
                            "description_sha256": desc, "description_elements": len(desc)}
        self.reference = {"schema": gate.REFERENCE_SCHEMA, "record_class": "synthetic", "release_id": m["release_id"],
                          "reference_id": "SYNTHETIC-reference-1", "complete": True, "hash_basis": tex["hash_basis"],
                          "records": copy.deepcopy(recs)}
        self.array = ["System/OngoingQuestInfoList-earlier.lub", RESOURCE]
        self.text_effective = dict(common, **{
            "schema": gate.TEXT_EFFECTIVE_SCHEMA, "qualification_id": "SYNTHETIC-text-1",
            "generated_resource": {"path": RESOURCE},
            "selected_server": "synthetic-local", "custom_quest_info": list(self.array),
            "decoder": {"langtype": 4}, "diagnostic_quest_ids": list(QUEST_IDS),
            "records": {q: {k: copy.deepcopy(v[k]) for k in ("title_sha256", "summary_sha256", "description_sha256")}
                        for q, v in recs.items()}})
        self.packet_extra = {"expected": {"selected_server": "synthetic-local", "custom_quest_info": list(self.array)}}
        self.packet_class = "synthetic"
        self.raw = {}
        self.auto_subject = True
        self.roots = None
        self.written = False

    # The subject fields every record must cite are filled from the actual
    # synthetic bytes unless a test turns auto_subject off.
    def _fill_subject(self):
        exe, cfg, log = self.files["native.executable"], self.files["effective.config"], self.files["native.parser_log"]
        staged = {r: sha(self.files[r]) for r in STORY_FILES}
        table = self.files["text.table"]
        env = {"executable_sha256": sha(exe), "image_id": self.native["image"]["id"], "effective_config_sha256": sha(cfg)}
        self.native["executable"].update(bytes=len(exe), sha256=sha(exe))
        self.native["effective_config_sha256"] = sha(cfg)
        self.native["parser"]["log_sha256"] = sha(log)
        self.native["parser"]["scripts"] = [{"path": STORY_FILES[r], "sha256": staged[r]} for r in
                                            ("story.npc.entry", "story.npc.first_edge", "story.npc.fruit_village", "story.quest_db")]
        self.facts["environment"] = dict(env)
        self.facts["npc_imports"] = [{"path": STORY_FILES[r], "sha256": staged[r], "loaded": True}
                                     for r in ("story.npc.entry", "story.npc.first_edge", "story.npc.fruit_village")]
        layers = [layer for layer in self.facts["quest_db"]["layers"] if layer["source"] != "db/import/quest_db.yml"]
        layers.append({"source": "db/import/quest_db.yml", "sha256": staged["story.quest_db"], "clear": False})
        self.facts["quest_db"]["layers"] = layers
        self.reference["source_table"] = {"bytes": len(table), "sha256": sha(table)}
        self.text_effective["environment"] = {"executable_sha256": sha(exe), "effective_config_sha256": sha(cfg)}
        self.text_effective["generated_resource"].update(bytes=len(table), sha256=sha(table))

    def write(self, repin=True, drop=(), staged_drop=()):
        root = self.root
        if self.written:
            shutil.rmtree(os.path.join(root, "in"))
            shutil.rmtree(os.path.join(root, "stage"))
        os.makedirs(os.path.join(root, "in"))
        if self.auto_subject:
            self._fill_subject()
        payload = {r: self.files[r] for r in self.files if not r.startswith(("story.", "text."))}
        payload.update({"native.qualification": json.dumps(self.native, ensure_ascii=False).encode(),
                        "effective.facts": json.dumps(self.facts, ensure_ascii=False).encode(),
                        "text.reference": json.dumps(self.reference, ensure_ascii=False).encode(),
                        "text.effective": json.dumps(self.text_effective, ensure_ascii=False).encode()})
        payload.update(self.raw)
        self.roots = {"story": os.path.join(root, "stage", "ro-solo-ch1-entry"),
                      "text": os.path.join(root, "stage", "tc-true-quest-text")}
        for label, files in (("story", STORY_FILES), ("text", TEXT_FILES)):
            for role, rel in files.items():
                if role in staged_drop:
                    continue
                path = os.path.join(self.roots[label], *rel.split("/"))
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as fh:
                    fh.write(self.files[role])
            os.makedirs(self.roots[label], exist_ok=True)
        for (label, rel), body in self.extra_staged.items():
            path = os.path.join(self.roots[label], *rel.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as fh:
                fh.write(body)
        for (label, rel), target in self.staged_links.items():
            os.symlink(target, os.path.join(self.roots[label], *rel.split("/")))
        inputs = {}
        for i, (role, body) in enumerate(sorted(payload.items())):
            if role in drop:
                continue
            path = os.path.join(root, "in", "%02d-%s" % (i, role.replace("/", "_")))
            with open(path, "wb") as fh:
                fh.write(body)
            inputs[role] = {"path": path, "bytes": len(body), "sha256": sha(body)}
        m = self.manifest
        if repin:
            for label, files in (("story", STORY_FILES), ("text", TEXT_FILES)):
                for role in files:
                    m[label]["files"][role].update(bytes=len(self.files[role]), sha256=sha(self.files[role]))
            for role in m["app"]["files"]:
                m["app"]["files"][role].update(bytes=len(self.files[role]), sha256=sha(self.files[role]))
            exe = self.files["native.executable"]
            m["native"]["executable"] = {"bytes": len(exe), "sha256": sha(exe)}
            for role in gate.QUALIFIED_ROLES:
                m["qualification_pins"][role] = {"bytes": len(payload[role]), "sha256": sha(payload[role])}
        self.manifest_path = os.path.join(root, "manifest.json")
        with open(self.manifest_path, "w", encoding="utf-8") as fh:
            json.dump(m, fh, ensure_ascii=False)
        packet = {"schema": gate.PACKET_SCHEMA, "record_class": self.packet_class,
                  "release_id": m["release_id"], "roots": dict(self.roots), "inputs": inputs}
        packet.update(copy.deepcopy(self.packet_extra))
        self.packet = packet
        self.packet_path = os.path.join(root, "packet.json")
        self.rewrite_packet()
        self.written = True
        return self.packet_path

    def rewrite_packet(self):
        with open(self.packet_path, "w", encoding="utf-8") as fh:
            json.dump(self.packet, fh, ensure_ascii=False)

    def rewrite_manifest(self):
        with open(self.manifest_path, "w", encoding="utf-8") as fh:
            json.dump(self.manifest, fh, ensure_ascii=False)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="t10-010-005-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.p = Packet(self.tmp)

    def evaluate(self, mode="synthetic"):
        manifest = self.p.manifest_path if mode == "synthetic" else gate.BUNDLED_MANIFEST
        return gate.evaluate(mode, manifest, self.p.packet_path)

    def run_gate(self, mode="synthetic", **write):
        self.p.write(**write)
        return self.evaluate(mode)

    def codes(self, r):
        return [x["code"] for x in r["reasons"]]

    def assert_refused(self, r, *codes):
        self.assertEqual(r["status"], "refused", r["reasons"])
        self.assertFalse(r["admitted"])
        for code in codes:
            self.assertIn(code, self.codes(r), json.dumps(r["reasons"], ensure_ascii=False)[:2000])
        return r

    def refused(self, *codes, **write):
        return self.assert_refused(self.run_gate(**write), *codes)

    def pinned_then(self, mutate, *codes):
        """Pin a coherent baseline, mutate coherently, rewrite WITHOUT re-pinning."""
        self.assertEqual(self.run_gate()["status"], "synthetic_consistent")
        mutate()
        r = self.assert_refused(self.run_gate(repin=False), *codes)
        return r


class PositiveAndBoundary(Base):
    def test_complete_synthetic_packet_is_consistent_but_never_admitted(self):
        r = self.run_gate()
        self.assertEqual(r["reasons"], [])
        self.assertEqual(r["status"], "synthetic_consistent")
        self.assertFalse(r["admitted"])
        self.assertEqual(len(r["inputs"]), len(self.p.manifest["required_roles"]) + len(STORY_FILES) + len(TEXT_FILES))
        self.assertTrue(gate.is_sha(r["gate"]["sha256"]))

    def test_cli_exit_codes(self):
        self.p.write()
        cmd = [sys.executable, "-I", "-B", GATE_PATH, "--synthetic", "--manifest", self.p.manifest_path, "--packet", self.p.packet_path]
        out = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout)["status"], "synthetic_consistent")
        out = subprocess.run([sys.executable, "-I", "-B", GATE_PATH, "--packet", self.p.packet_path],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        self.assertEqual(out.returncode, 1)
        self.assertFalse(json.loads(out.stdout)["admitted"])
        out = subprocess.run([sys.executable, "-I", "-B", GATE_PATH, "--manifest", self.p.manifest_path, "--packet", self.p.packet_path],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        self.assertEqual(out.returncode, 2, "real mode must not accept a substitute manifest")

    def test_real_mode_refuses_complete_synthetic_packet(self):
        r = self.assert_refused(self.run_gate(mode="real"), "manifest_unpinned", "packet_record_class",
                                "native_record_class", "release_pin_mismatch")
        gaps = {x["detail"].split(" ")[0] for x in r["reasons"] if x["code"] == "manifest_unpinned"}
        for role in gate.QUALIFIED_ROLES:
            self.assertIn("qualification_pins." + role, gaps)
        self.assertIn("text.mod_json", gaps)

    def test_real_mode_refuses_todays_inputs(self):
        # Only the tracked story folder and the patch exist today; everything else is genuinely absent.
        with open(PATCH, "rb") as fh:
            body = fh.read()
        path = os.path.join(self.tmp, "today.json")
        with open(path, "w") as fh:
            json.dump({"schema": gate.PACKET_SCHEMA, "record_class": "actual",
                       "release_id": "ro-solo-ch1-entry@0.3.2+tc-true-quest-text@0.1.0",
                       "roots": {"story": STORY_DIR},
                       "inputs": {"native.patch": {"path": PATCH, "bytes": len(body), "sha256": sha(body)}}}, fh)
        r = gate.evaluate("real", gate.BUNDLED_MANIFEST, path)
        self.assert_refused(r, "manifest_unpinned", "input_missing")
        codes = self.codes(r)
        missing = {x["detail"] for x in r["reasons"] if x["code"] == "input_missing"}
        self.assertIn("staged text root not supplied", missing)
        for role in ("native.executable", "native.qualification", "effective.config", "effective.facts",
                     "text.reference", "text.effective"):
            self.assertIn("role %s not supplied" % role, missing)
        # The tracked story folder itself is exactly the bound 0.3.2 inventory and pins.
        for code in ("release_pin_mismatch", "staged_extra", "staged_missing", "staged_root_name",
                     "story_version_mismatch", "quest_row_missing", "route_exit_missing", "connection_block_changed"):
            self.assertNotIn(code, codes)

    def test_synthetic_mode_refuses_actual_class_records_and_manifest(self):
        self.p.native["record_class"] = "actual"
        self.refused("native_record_class")
        self.setUp()
        self.p.manifest["manifest_class"] = "actual"
        self.refused("manifest_class")

    def test_no_writes_and_tracked_inputs_unchanged(self):
        before = tracked_snapshot()
        self.p.write()
        def snap():
            out = {}
            for dirpath, dirnames, filenames in os.walk(self.tmp):
                for name in dirnames + filenames:
                    st = os.lstat(os.path.join(dirpath, name))
                    out[os.path.join(dirpath, name)] = (st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
            return out
        s0 = snap()
        self.evaluate()
        gate.evaluate("real", gate.BUNDLED_MANIFEST, self.p.packet_path)
        self.assertEqual(s0, snap())
        self.assertEqual(before, tracked_snapshot())

    def test_reasons_are_bounded(self):
        self.p.facts["collisions"] = [{"kind": "quest", "key": str(i), "resolved": False} for i in range(200)]
        r = self.refused("collision_unresolved")
        self.assertEqual(len(r["reasons"]), gate.MAX_REASONS)
        self.assertGreater(r["reasons_truncated"], 0)
        self.assertTrue(all(len(x["detail"]) <= gate.MAX_DETAIL for x in r["reasons"]))


class IndependentPins(Base):
    """Coherent caller changes refuse against unchanged expected pins."""

    def test_coherent_description_replacement(self):
        def mutate():
            new = fake("coherent-replacement")
            self.p.reference["records"]["18371"]["description_sha256"][1] = new
            self.p.text_effective["records"]["18371"]["description_sha256"][1] = new
        r = self.pinned_then(mutate, "release_pin_mismatch")
        self.assertEqual(sorted(x["detail"] for x in r["reasons"]), ["text.effective", "text.reference"])

    def test_coherent_description_truncation(self):
        def mutate():
            for rec in (self.p.reference["records"]["18371"], self.p.text_effective["records"]["18371"]):
                rec["description_sha256"] = rec["description_sha256"][:1]
            self.p.reference["records"]["18371"]["description_elements"] = 1
        r = self.pinned_then(mutate, "release_pin_mismatch")
        self.assertEqual(sorted(x["detail"] for x in r["reasons"]), ["text.effective", "text.reference"])

    def test_changed_qualification_record(self):
        def mutate():
            self.p.native["qualification_id"] = "SYNTHETIC-native-2"
        r = self.pinned_then(mutate, "release_pin_mismatch")
        self.assertEqual([x["detail"] for x in r["reasons"]], ["native.qualification"])

    def test_changed_subject_executable_with_coherent_records(self):
        def mutate():
            self.p.files["native.executable"] = b"\x7fELF SYNTHETIC other patched map-server\n"
        r = self.pinned_then(mutate, "release_pin_mismatch")
        details = {x["detail"] for x in r["reasons"]}
        for role in ("native.executable", "native.qualification", "effective.facts", "text.effective"):
            self.assertIn(role, details)

    def test_changed_effective_config_with_coherent_records(self):
        def mutate():
            self.p.files["effective.config"] += b"# changed\n"
        r = self.pinned_then(mutate, "release_pin_mismatch")
        self.assertIn("effective.config", [x["detail"] for x in r["reasons"]])

    def test_changed_staged_story_with_coherent_records(self):
        def mutate():
            self.p.files["story.npc.entry"] += b"\n// changed\n"
        r = self.pinned_then(mutate, "release_pin_mismatch")
        self.assertIn("story.npc.entry", [x["detail"] for x in r["reasons"]])

    def test_effective_config_not_cited(self):
        self.p.auto_subject = True
        self.p.write()
        self.p.auto_subject = False
        self.p.native["effective_config_sha256"] = fake("other-config")
        self.refused("native_config_mismatch")

    def test_effective_config_missing(self):
        self.refused("input_missing", drop=("effective.config",))

    def test_labels_and_self_hashes_do_not_qualify(self):
        # Root labels and a matching caller self-hash alone, with no manifest pin: refuse.
        self.p.write()
        self.p.native["qualified_by"] = "Root"
        for role in gate.QUALIFIED_ROLES:
            self.p.manifest["qualification_pins"][role] = {"bytes": None, "sha256": None}
        self.p.write(repin=False)
        self.p.rewrite_manifest()
        r = self.assert_refused(self.evaluate(), "manifest_unpinned")
        self.assertEqual(len([x for x in r["reasons"] if x["code"] == "manifest_unpinned"]), len(gate.QUALIFIED_ROLES))


class StagedRoots(Base):
    def test_extra_unadmitted_npc_file(self):
        self.p.extra_staged[("story", "npc/extra.txt")] = b"prontera,1,1,4\tscript\tX\t1,{ end; }\n"
        r = self.refused("staged_extra")
        self.assertIn("story npc/extra.txt", [x["detail"] for x in r["reasons"]])

    def test_era_db_override(self):
        self.p.extra_staged[("story", "db/re/quest_db.yml")] = b"Header:\n  Type: QUEST_DB\n  Version: 3\n  Clear: true\n"
        self.refused("staged_era_override", "staged_extra")

    def test_era_folder_manifest_key(self):
        mod = json.loads(self.p.files["story.mod_json"])
        mod["renewalFolder"] = "renewal"
        self.p.files["story.mod_json"] = json.dumps(mod, ensure_ascii=False).encode()
        self.p.extra_staged[("story", "renewal/npc/alt.txt")] = b"// alt\n"
        self.refused("staged_era_override", "staged_extra")

    def test_extra_text_file(self):
        self.p.extra_staged[("text", "System/OngoingQuestInfoList_True.lub")] = b"-- extra\n"
        self.refused("staged_extra")

    def test_absent_text_table(self):
        r = self.refused("staged_missing", staged_drop=("text.table",))
        self.assertIn("text " + RESOURCE, [x["detail"] for x in r["reasons"]])

    def test_absent_text_root(self):
        self.p.write()
        del self.p.packet["roots"]["text"]
        self.p.rewrite_packet()
        r = self.assert_refused(self.evaluate(), "input_missing")
        self.assertIn("staged text root not supplied", [x["detail"] for x in r["reasons"]])

    def test_changed_text_table(self):
        self.p.write()
        self.p.files["text.table"] += b"-- changed\n"
        r = self.assert_refused(self.run_gate(repin=False), "release_pin_mismatch")
        self.assertIn("text.table", [x["detail"] for x in r["reasons"]])

    def test_changed_text_manifest(self):
        mod = json.loads(self.p.files["text.mod_json"])
        mod["version"] = "0.1.1"
        self.p.files["text.mod_json"] = json.dumps(mod).encode()
        self.refused("text_manifest_mismatch")

    def test_wrong_root_parent_folder(self):
        self.p.write()
        self.p.packet["roots"]["story"] = os.path.dirname(self.p.roots["story"])
        self.p.rewrite_packet()
        self.assert_refused(self.evaluate(), "staged_root_name", "staged_extra", "staged_missing")

    def test_wrong_root_name(self):
        self.p.write()
        renamed = os.path.join(self.tmp, "stage", "ro-solo-ch1-entry-copy")
        os.rename(self.p.roots["story"], renamed)
        self.p.packet["roots"]["story"] = renamed
        self.p.rewrite_packet()
        self.assert_refused(self.evaluate(), "staged_root_name")

    def test_wrong_layout_flattened(self):
        self.p.write()
        root = self.p.roots["story"]
        os.rename(os.path.join(root, "db", "quest_db.yml"), os.path.join(root, "quest_db.yml"))
        r = self.assert_refused(self.evaluate(), "staged_missing", "staged_extra")
        self.assertIn("story db/quest_db.yml", [x["detail"] for x in r["reasons"] if x["code"] == "staged_missing"])

    def test_text_root_swapped_with_story(self):
        self.p.write()
        self.p.packet["roots"]["text"] = self.p.roots["story"]
        self.p.rewrite_packet()
        self.assert_refused(self.evaluate(), "staged_root_name", "staged_extra", "staged_missing")

    def test_symlink_and_special_files_in_staging(self):
        self.p.staged_links[("story", "npc/link.txt")] = os.path.join(STORY_DIR, "npc", "entry.txt")
        self.p.write()
        os.mkfifo(os.path.join(self.p.roots["text"], "System", "pipe"))
        r = self.assert_refused(self.evaluate(), "staged_symlink", "staged_special_file")
        self.assertIn("story npc/link.txt", [x["detail"] for x in r["reasons"] if x["code"] == "staged_symlink"])
        # An expected leaf replaced by a symlink is both a link and a missing file.
        path = os.path.join(self.p.roots["story"], "npc", "entry.txt")
        os.unlink(path)
        os.symlink(os.path.join(STORY_DIR, "npc", "entry.txt"), path)
        r = self.assert_refused(self.evaluate(), "staged_symlink", "staged_missing")
        self.assertIn("story npc/entry.txt", [x["detail"] for x in r["reasons"] if x["code"] == "staged_missing"])

    def test_symlinked_root(self):
        self.p.write()
        link = os.path.join(self.tmp, "ro-solo-ch1-entry")
        os.symlink(self.p.roots["story"], link)
        self.p.packet["roots"]["story"] = link
        self.p.rewrite_packet()
        self.assert_refused(self.evaluate(), "staged_input_symlink")

    def test_staged_file_replaced_by_directory(self):
        self.p.write()
        path = os.path.join(self.p.roots["story"], "npc", "entry.txt")
        os.unlink(path)
        os.mkdir(path)
        self.assert_refused(self.evaluate(), "staged_missing", "staged_extra")

    def test_hardlinked_staged_file(self):
        self.p.write()
        os.link(os.path.join(self.p.roots["story"], "mod.json"), os.path.join(self.tmp, "alias.json"))
        self.assert_refused(self.evaluate(), "input_hardlinked")


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
        self.p.write()
        self.p.auto_subject = False
        self.p.native["executable"]["sha256"] = self.p.manifest["native"]["stock_executable_sha256"]
        self.refused("native_stock_evidence", "native_executable_mismatch")

    def test_missing_or_accepting_stock_control(self):
        del self.p.native["stock_control"]
        self.refused("native_stock_control_missing")
        self.setUp()
        self.p.native["stock_control"]["release_rejected"] = False
        self.refused("native_stock_control_invalid")

    def test_host_fixture_or_label_is_not_qualification(self):
        self.p.native["qualification_kind"] = "host_fixture"
        self.p.native["parser"]["method"] = "string_search"
        self.refused("native_unqualified_kind", "native_parser_unqualified")

    def test_bare_boolean_builtin_without_probe(self):
        self.p.native["builtin"] = {"name": "ros_ch1_coin_capacity", "registered": True, "arguments": 0}
        self.refused("native_builtin_unproven")

    def test_numeric_booleans(self):
        self.p.native["builtin"]["arguments"] = False
        self.p.native["builtin"]["probe_observations"] = {"fits": True, "no_fit": False}
        r = self.refused("native_builtin_unproven")
        self.assertEqual(self.codes(r).count("native_builtin_unproven"), 2)
        self.setUp()
        self.p.native["parser"]["errors"] = False
        self.p.native["parser"]["release_warnings"] = False
        self.refused("native_parser_failed")
        self.setUp()
        self.p.native["packet_version"] = 20221005.0
        self.p.native["max_amount"] = True
        self.refused("native_packet_mismatch", "native_max_amount_unknown")
        self.setUp()
        self.p.facts["item"]["weight"] = True
        self.p.facts["item"]["id"] = 1001972.0
        self.p.facts["connections"][0]["from"] = ["ygg_edge", 164, 140.0]
        self.refused("item_fact_unknown", "item_alias_wrong", "route_exit_not_effective")

    def test_binary_larger_than_4_mib_streams(self):
        self.p.files["native.executable"] = b"\x7fELF" + b"\0" * (4 * 1024 * 1024 + 1)
        r = self.run_gate()
        self.assertEqual(r["status"], "synthetic_consistent", r["reasons"])
        self.assertEqual(r["inputs"]["native.executable"]["bytes"], 4 * 1024 * 1024 + 5)

    def test_large_artifacts_are_streamed_not_buffered(self):
        self.p.write()
        calls = {}
        real = gate.read_explicit

        def spy(path, cap, keep=True):
            calls[path] = (cap, keep)
            return real(path, cap, keep)
        with mock.patch.object(gate, "read_explicit", spy):
            self.assertEqual(self.evaluate()["status"], "synthetic_consistent")
        ins = self.p.packet["inputs"]
        self.assertEqual(calls[ins["native.executable"]["path"]], (gate.EXECUTABLE_CAP, False))
        self.assertEqual(calls[ins["effective.config"]["path"]], (gate.CONFIG_CAP, False))
        self.assertEqual(calls[ins["native.qualification"]["path"]], (gate.JSON_CAP, True))

    def test_binary_over_cap(self):
        self.p.write()
        with mock.patch.dict(gate.STREAMED, {"native.executable": 16}):
            self.assert_refused(self.evaluate(), "input_too_large")

    def test_changed_binary_patch_script(self):
        self.p.write()
        self.p.files["native.executable"] += b"x"
        self.p.files["native.patch"] += b"\n"
        r = self.assert_refused(self.run_gate(repin=False), "release_pin_mismatch")
        details = {x["detail"] for x in r["reasons"]}
        self.assertTrue({"native.executable", "native.patch"} <= details)
        self.setUp()
        self.p.files["native.patch"] += b"\n"
        self.p.manifest["native"]["patch"]["sha256"] = fake("unchanged-patch-pin")
        self.refused("release_pin_mismatch", "native_source_mismatch")
        self.setUp()
        self.p.write()
        self.p.auto_subject = False
        self.p.files["story.npc.entry"] += b"\n// changed\n"
        self.refused("native_script_mismatch", "npc_import_not_effective")

    def test_changed_abi_platform_packet_image(self):
        self.p.native["abi"]["libraries"][0]["sha256"] = fake("other-lib")
        self.p.native["image"]["platform"] = "linux/amd64"
        self.p.native["packet_version"] = 20200401
        self.p.native["image"]["id"] = "sha256:" + fake("other-image")
        self.refused("native_abi_mismatch", "native_platform_mismatch", "native_packet_mismatch", "native_image_mismatch")

    def test_parser_log_rejection_and_errors(self):
        self.p.files["native.parser_log"] = b"[Error]: parse_line: expect command, missing function name or calling undeclared function\n"
        self.refused("native_parser_log_rejection")
        self.setUp()
        self.p.native["parser"]["errors"] = 1
        self.refused("native_parser_failed")

    def test_wrong_source_revision(self):
        self.p.native["source"]["rathena_revision"] = "0" * 40
        self.p.native["source"]["prepared_source_tree_sha256"] = fake("tree")
        self.refused("native_source_mismatch")


class StoryAndQuests(Base):
    def test_old_020_staging(self):
        mod = json.loads(self.p.files["story.mod_json"])
        mod["version"] = "0.2.0"
        self.p.files["story.mod_json"] = json.dumps(mod, ensure_ascii=False).encode()
        self.refused("story_superseded_staging")

    def test_invented_requires_key(self):
        mod = json.loads(self.p.files["story.mod_json"])
        mod["requires"]["native"] = "ros_ch1_coin_capacity"
        self.p.files["story.mod_json"] = json.dumps(mod, ensure_ascii=False).encode()
        self.refused("story_requires_unsupported_key")

    def test_missing_18371_staged_and_effective(self):
        text = self.p.files["story.quest_db"].decode()
        self.p.files["story.quest_db"] = text[:text.index("  - Id: 18371")].encode()
        r = self.refused("quest_row_missing")
        self.assertIn("staged quest_db.yml lacks 18371", [x["detail"] for x in r["reasons"]])
        self.setUp()
        self.p.facts["quest_db"]["rows"] = [r for r in self.p.facts["quest_db"]["rows"] if r["id"] != 18371]
        r = self.refused("quest_row_not_effective")
        self.assertEqual([x["detail"] for x in r["reasons"]], ["18371"])

    def test_clear_staged_and_effective(self):
        text = self.p.files["story.quest_db"].decode().replace("  Version: 3\n", "  Version: 3\n  Clear: true\n")
        self.p.files["story.quest_db"] = text.encode()
        self.refused("quest_db_clear")
        self.setUp()
        self.p.facts["quest_db"]["layers"][0]["clear"] = True
        r = self.refused("quest_db_clear")
        self.assertEqual(len(r["reasons"]), 1)

    def test_conflicting_imports(self):
        self.p.facts["collisions"] = [{"kind": "quest", "key": "18370", "resolved": False, "other_source": "another-mod"}]
        self.refused("collision_unresolved")
        self.setUp()
        self.p.write()
        self.p.auto_subject = False
        self.p.facts["npc_imports"].append(dict(self.p.facts["npc_imports"][0]))
        self.refused("npc_import_not_effective")
        self.setUp()
        self.p.facts["quest_db"]["rows"].append({"id": 18369, "title_sha256": fake("other-title"), "source": "other"})
        self.refused("quest_row_effective_mismatch")

    def test_resolved_identical_collision_is_consistent(self):
        self.p.facts["collisions"] = [{"kind": "quest", "key": "18368", "resolved": True, "identical": True}]
        self.assertEqual(self.run_gate()["status"], "synthetic_consistent")

    def test_missing_map_and_exits(self):
        del self.p.facts["maps"]["ygg_fruit"]
        r = self.refused("route_map_not_loaded")
        self.assertEqual(r["reasons"][0]["detail"], "ygg_fruit")
        self.setUp()
        text = self.p.files["story.npc.first_edge"].decode()
        line = "ygg_fruit,71,114,0\twarp\tROSOLO_CH1_FRUIT_OUT\t1,1,ygg_edge,168,139\n"
        self.assertIn(line, text)
        self.p.files["story.npc.first_edge"] = text.replace(line, "").encode()
        r = self.refused("route_exit_missing", "connection_block_changed")
        self.assertIn("ROSOLO_CH1_FRUIT_OUT", [x["detail"] for x in r["reasons"] if x["code"] == "route_exit_missing"])
        self.setUp()
        text = self.p.files["story.npc.first_edge"].decode().replace('warp "prt_fild05",353,248;', 'warp "prt_fild05",1,1;')
        self.p.files["story.npc.first_edge"] = text.encode()
        r = self.refused("route_exit_missing", "connection_block_changed")
        self.assertIn("回程#ROSOLO_CH1_RET", [x["detail"] for x in r["reasons"] if x["code"] == "route_exit_missing"])
        self.setUp()
        self.p.facts["connections"] = [c for c in self.p.facts["connections"] if c["name"] != "ROSOLO_CH1_EDGE_IN"]
        self.refused("route_exit_not_effective")

    def test_missing_quest_db_import(self):
        self.p.write()
        self.p.auto_subject = False
        self.p.facts["quest_db"]["layers"] = self.p.facts["quest_db"]["layers"][:1]
        self.refused("quest_db_import_missing")


class ItemFacts(Base):
    def test_wrong_alias(self):
        self.p.facts["item"]["alias_resolutions"][1]["id"] = 1001973
        self.refused("item_alias_wrong")
        self.setUp()
        self.p.facts["item"]["alias_resolutions"] = self.p.facts["item"]["alias_resolutions"][:1]
        self.refused("item_alias_unproven")

    def test_wrong_type_weight_guid_pet_stackable(self):
        item = self.p.facts["item"]
        item.update(type="Usable", weight=10, guid=True, pet=True, stackable=False)
        self.refused("item_type_wrong", "item_weight_wrong", "item_guid_wrong", "item_pet_wrong", "item_stackable_wrong")

    def test_unknown_fact(self):
        self.p.facts["item"]["pet"] = None
        self.refused("item_fact_unknown")

    def test_stack_unknown_and_contradictions(self):
        self.p.facts["item"]["stack_restrictions"] = None
        self.refused("item_stack_unknown")
        self.setUp()
        self.p.facts["item"]["stack_restrictions"] = {"amount": 5, "inventory": True, "cart": False, "storage": False, "guild_storage": False}
        self.refused("item_stack_contradiction")
        self.setUp()
        self.p.native["stack_restrictions"] = {"amount": None, "inventory": True, "cart": False, "storage": False, "guild_storage": False}
        self.refused("native_stack_contradiction")
        self.setUp()
        self.p.facts["item"]["max_amount"] = 32767
        self.refused("item_stack_contradiction")

    def test_actual_stack_restriction_binds_when_consistent(self):
        stack = {"amount": 500, "inventory": True, "cart": False, "storage": False, "guild_storage": False}
        self.p.native["stack_restrictions"] = dict(stack)
        self.p.facts["item"]["stack_restrictions"] = dict(stack)
        self.assertEqual(self.run_gate()["status"], "synthetic_consistent")


class TextEvidence(Base):
    def test_changed_decoder_array_server(self):
        self.p.text_effective["decoder"] = {"langtype": 0}
        self.refused("text_decoder_mismatch")
        self.setUp()
        self.p.text_effective["decoder"] = {"langtype": 4.0}
        self.refused("text_decoder_mismatch")
        self.setUp()
        self.p.text_effective["custom_quest_info"] = list(reversed(self.p.array))
        self.refused("text_array_mismatch")
        self.setUp()
        self.p.text_effective["selected_server"] = "another"
        self.refused("text_server_mismatch")

    def test_array_without_resource(self):
        self.p.packet_extra["expected"]["custom_quest_info"] = ["System/OngoingQuestInfoList-earlier.lub"]
        self.p.text_effective["custom_quest_info"] = ["System/OngoingQuestInfoList-earlier.lub"]
        self.refused("text_expectation_missing")

    def test_effective_description_differs_from_pinned_reference(self):
        self.p.text_effective["records"]["18371"]["description_sha256"][0] = fake("changed")
        r = self.refused("text_record_mismatch")
        self.assertIn("18371 description", [x["detail"] for x in r["reasons"]])
        self.setUp()
        del self.p.text_effective["records"]["18371"]
        self.refused("text_record_missing")

    def test_reference_absent(self):
        self.refused("input_missing", drop=("text.reference",))

    def test_reference_incomplete(self):
        for rec in self.p.reference["records"].values():
            rec["description_sha256"] = []
            rec["description_elements"] = 0
        self.refused("text_reference_incomplete")
        self.setUp()
        self.p.reference["records"]["18370"]["description_elements"] = 3
        self.refused("text_reference_incomplete")
        self.setUp()
        del self.p.reference["records"]["18371"]
        self.refused("text_reference_incomplete")
        self.setUp()
        self.p.reference["complete"] = False
        self.refused("text_reference_incomplete")
        self.setUp()
        self.p.reference["records"]["18372"] = copy.deepcopy(self.p.reference["records"]["18371"])
        self.refused("text_reference_incomplete")

    def test_reference_bound_to_staged_table(self):
        self.p.write()
        self.p.auto_subject = False
        self.p.reference["source_table"]["sha256"] = fake("other-table")
        self.refused("text_reference_source_mismatch")

    def test_reference_title_summary_not_public_hash(self):
        self.p.reference["records"]["18370"]["summary_sha256"] = fake("x")
        self.p.reference["records"]["18369"]["title_sha256"] = fake("y")
        self.refused("text_reference_summary_mismatch", "text_reference_title_mismatch")

    def test_registration_tail_diagnostic_ids_do_not_count(self):
        self.p.text_effective["diagnostic_quest_ids"] = [21001, 16912]
        self.refused("text_diagnostic_scope")

    def test_resource_mismatch(self):
        self.p.text_effective["generated_resource"]["path"] = "System/OngoingQuestInfoList-other.lub"
        self.refused("text_resource_mismatch")


class MalformedAndUnsafeInputs(Base):
    def test_non_json_duplicate_nan_and_wrong_types(self):
        self.p.raw["native.qualification"] = b"PASS"
        self.refused("evidence_malformed")
        self.setUp()
        self.p.raw["effective.facts"] = b'{"schema": "a", "schema": "b"}'
        self.p.raw["text.reference"] = b'{"complete": NaN}'
        r = self.refused("evidence_malformed")
        self.assertEqual(self.codes(r).count("evidence_malformed"), 2)
        self.setUp()
        self.p.write()
        self.p.auto_subject = False
        self.p.native["builtin"] = ["ros_ch1_coin_capacity"]
        self.p.native["parser"] = "ok"
        self.p.facts["item"] = "Ch1_Root_Coin"
        self.p.text_effective["records"] = []
        self.refused("native_builtin_unproven", "native_parser_unqualified", "item_alias_unproven", "text_record_missing")

    def test_incomplete_evidence(self):
        self.p.write()
        self.p.auto_subject = False
        for key in ("abi", "image", "stack_restrictions", "max_amount"):
            del self.p.native[key]
        self.refused("native_abi_malformed", "native_image_malformed", "native_stack_unknown", "native_max_amount_unknown")

    def test_observed_mid_read_change(self):
        self.p.write()
        target = self.p.packet["inputs"]["effective.facts"]["path"]
        ino = os.lstat(target).st_ino
        real_read = os.read
        state = {"done": False}

        def read(fd, n):
            data = real_read(fd, n)
            if not state["done"] and os.fstat(fd).st_ino == ino:
                state["done"] = True
                with open(target, "ab") as fh:
                    fh.write(b" ")
            return data
        with mock.patch.object(gate.os, "read", read):
            r = self.evaluate()
        self.assertTrue(state["done"])
        self.assert_refused(r, "input_changed")
        self.assertIn("effective.facts", [x["detail"] for x in r["reasons"] if x["code"] == "input_changed"][0])

    def test_metadata_only_change_during_read(self):
        self.p.write()
        target = self.p.packet["inputs"]["native.parser_log"]["path"]
        ino = os.lstat(target).st_ino
        real_read = os.read
        state = {"done": False}

        def read(fd, n):
            data = real_read(fd, n)
            if not state["done"] and os.fstat(fd).st_ino == ino:
                state["done"] = True
                st = os.lstat(target)
                os.utime(target, ns=(st.st_atime_ns, st.st_mtime_ns + 1000000000))
            return data
        with mock.patch.object(gate.os, "read", read):
            r = self.evaluate()
        self.assert_refused(r, "input_changed")

    def test_missing_symlink_directory_fifo_hardlink_relative_unnormalized(self):
        self.p.write()
        ins = self.p.packet["inputs"]
        os.unlink(ins["effective.facts"]["path"])
        link = os.path.join(self.tmp, "link.log")
        os.symlink(ins["native.parser_log"]["path"], link)
        ins["native.parser_log"]["path"] = link
        alias = os.path.join(self.tmp, "alias")
        os.symlink(os.path.join(self.tmp, "in"), alias)
        ins["text.effective"]["path"] = os.path.join(alias, os.path.basename(ins["text.effective"]["path"]))
        d = os.path.join(self.tmp, "dir")
        os.mkdir(d)
        ins["native.qualification"]["path"] = d
        fifo = os.path.join(self.tmp, "fifo")
        os.mkfifo(fifo)
        ins["effective.config"]["path"] = fifo
        os.link(ins["native.patch"]["path"], os.path.join(self.tmp, "hard"))
        ins["text.reference"]["path"] = "relative/reference.json"
        ins["app.electron/main.js"]["path"] = self.tmp + "/in/../in/x.js"
        self.p.rewrite_packet()
        r = self.evaluate()
        codes = self.codes(r)
        for code in ("input_missing", "input_symlink", "input_not_regular", "input_hardlinked",
                     "input_path_not_absolute", "input_path_not_normalized"):
            self.assertIn(code, codes)
        self.assertEqual(codes.count("input_symlink"), 2)
        self.assertEqual(codes.count("input_not_regular"), 2)

    def test_oversized_json(self):
        self.p.raw["text.reference"] = b" " * (gate.JSON_CAP + 1)
        self.refused("input_too_large")

    def test_packet_pin_mismatch_and_numeric_boolean_pin(self):
        self.p.write()
        self.p.packet["inputs"]["effective.facts"]["sha256"] = "0" * 64
        self.p.rewrite_packet()
        self.assert_refused(self.evaluate(), "packet_pin_mismatch")
        self.p.write()
        self.p.manifest["native"]["executable"]["bytes"] = float(self.p.manifest["native"]["executable"]["bytes"])
        self.p.rewrite_manifest()
        r = self.assert_refused(self.evaluate(), "release_pin_mismatch")
        self.assertIn("native.executable", [x["detail"] for x in r["reasons"]])

    def test_unknown_role_and_missing_packet(self):
        self.p.raw["private.autodiscovered"] = b"{}"
        self.refused("packet_unknown_role")
        r = gate.evaluate("synthetic", self.p.manifest_path, os.path.join(self.tmp, "absent.json"))
        self.assertEqual(self.codes(r), ["packet_input_missing"])
        r = gate.evaluate("synthetic", self.p.manifest_path, None)
        self.assertEqual(r["status"], "refused")

    def test_malformed_packet_and_manifest(self):
        self.p.write()
        with open(self.p.packet_path, "w") as fh:
            fh.write("[]")
        r = self.evaluate()
        self.assertEqual(self.codes(r), ["packet_malformed"])
        with open(self.p.manifest_path, "w") as fh:
            fh.write("{")
        r = self.evaluate()
        self.assertEqual(self.codes(r), ["manifest_malformed"])


if __name__ == "__main__":
    unittest.main()
