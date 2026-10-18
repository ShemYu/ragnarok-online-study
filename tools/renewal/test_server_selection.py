"""Tests for server_selection. Run: python3 -I -m unittest discover -s tools/renewal

Synthetic snapshots are in-memory {path: bytes} trees, written to temporary
directories only for the verification and publication tests. The pinned-input
test reads the canonical T06.001 snapshot from $RENEWAL_SELECTION_SNAPSHOT, or
the default .tools/renewal/t06-candidates/integrated-2, and is skipped when absent.
"""

import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import server_selection as sel  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
PINNED_SNAPSHOT = Path(os.environ.get("RENEWAL_SELECTION_SNAPSHOT",
                                      REPO / ".tools/renewal/t06-candidates/integrated-2"))
# Exact path/hash checks named by the T06.002.001 brief (hashes from the canonical manifest).
PINNED_NPC = {
    "npc/re/jobs/novice/academy.txt":
        "b2ab5f7de7e1c36e4f58b8447a80d4cb089e8bf45aeade59953c6a70004f27fd",
    "npc/custom/population/arena.txt":
        "d6919d3fdfa2ec42a9f27f6d40894d4aa3e38a31dbbd90aeec548192e812c22c",
    "npc/custom/population/recruiter.txt":
        "4a32b6c6c36882f4a32745f31c0b950bd336cea24b6a2d73eba2dc1b79288aea",
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def tree(map_conf=b"", npc_main=b"", **extra):
    """Snapshot files below rathena/. extra keys use '__' for '/' and '_DOT_' for '.'."""
    files = {"rathena/conf/map_athena.conf": map_conf,
             "rathena/npc/re/scripts_main.conf": npc_main}
    for key, body in extra.items():
        files["rathena/" + key.replace("__", "/").replace("_DOT_", ".")] = body
    return files


def run(files):
    return sel.build_selection(files, "0" * 64)


def maps(result):
    return [m["name"] for m in result["maps"]["candidates"]]


def npcs(result):
    return [n["source"] for n in result["npc_sources"]["files"]]


def ops(result, *names):
    return [e for e in result["events"] if e["op"] in names]


class ParserRules(unittest.TestCase):
    def test_key_case_whitespace_comments_and_value_rules(self):
        conf = (b"MAP: upper\n"
                b"map:nospace\n"
                b"map:   padded   \n"
                b" map: leading_key_space\n"
                b"map : key_trailing_space\n"
                b"map: commented // trailing comment\n"
                b"// map: whole_line_comment\n"
                b"map: a//b\n"
                b"map: tab\tafter\n"
                b"map: crlf\r\n"
                b"map:\n"
                b"map: \t \n"
                b"no colon line\n"
                b"map: last_without_newline")
        result = run(tree(conf))
        self.assertEqual(maps(result), ["upper", "nospace", "padded", "commented", "a", "tab",
                                        "crlf", "last_withou"])
        unknown = {u["key"] for u in result["ignored_settings"]}
        self.assertEqual(unknown, {" map", "map "})

    def test_comment_inside_key_becomes_unknown_key(self):
        # strstr replaces the first '/' with '\n'; %[^:] keeps reading to the ':'.
        result = run(tree(b"map // note: hidden\n"))
        self.assertEqual(maps(result), [])
        self.assertEqual([u["key"] for u in result["ignored_settings"]], ["map \n/ note"])

    def test_key_width_differs_between_passes(self):
        long_key = b"k" * 31
        conf = long_key + b"x: value\n" + long_key + b": value\n"
        result = run(tree(conf, npc_main=b"q" * 40 + b": value\n"))
        self.assertEqual(len(ops(result, "ignored_key_overflow")), 1)
        keys = [(u["phase"], u["key"]) for u in result["ignored_settings"]]
        self.assertEqual(keys, [("map_config", "k" * 31), ("npc_config", "q" * 40)])

    def test_overlong_nul_and_control_input_rejected(self):
        ok = b"map: " + b"x" * (sel.LINE_MAX - 5) + b"\n"
        self.assertEqual(len(run(tree(ok))["maps"]["candidates"]), 1)
        for bad in (b"map: " + b"x" * (sel.LINE_MAX - 4) + b"\n", b"map: a\0b\n",
                    b"map: a\x0bb\n", b"// \x1b comment\n"):
            with self.assertRaises(sel.SelectionError):
                run(tree(bad))
        with self.assertRaises(sel.SelectionError):
            run(tree(b"map: caf\xc3\xa9\n"))
        # Non-ASCII in comments and unrelated values is not recorded and is allowed.
        result = run(tree(b"// caf\xc3\xa9\nmotd_txt: caf\xc3\xa9\nmap: ok\n"))
        self.assertEqual(maps(result), ["ok"])

    def test_unknown_and_sensitive_values_absent(self):
        conf = (b"userid: SECRET_USER_1\npasswd: SECRET_PASS_2\n"
                b"api_token: SECRET_TOKEN_3\nmap: m\n")
        result = run(tree(conf, npc_main=b"password: SECRET_NPC_4\n"))
        rendered = sel.render(result)
        for secret in (b"SECRET_USER_1", b"SECRET_PASS_2", b"SECRET_TOKEN_3", b"SECRET_NPC_4"):
            self.assertNotIn(secret, rendered)
        entries = {(u["key"], u["recognized_by_parser"], u["count"])
                   for u in result["ignored_settings"]}
        self.assertEqual(entries, {("userid", True, 1), ("passwd", True, 1),
                                   ("api_token", False, 1), ("password", False, 1)})
        location = [u for u in result["ignored_settings"] if u["key"] == "passwd"][0]
        self.assertEqual(location["locations"], [{"file": "conf/map_athena.conf", "line": 2}])

    def test_db_path_and_use_grf(self):
        conf = b"db_path: abcdefghijklmnop\nuse_grf: YES\nuse_grf: 7\n"
        settings = run(tree(conf))["settings"]
        self.assertEqual(settings["db_path"][0]["effective"], "abcdefghijk")
        self.assertTrue(settings["db_path"][0]["truncated"])
        self.assertEqual([v["effective"] for v in settings["use_grf"]], [1, None])
        # Only the map pass recognizes them.
        result = run(tree(npc_main=b"db_path: x\n"))
        self.assertEqual(result["settings"], {})


class ImportOrder(unittest.TestCase):
    def test_recursive_imports_at_position_relative_to_server_root(self):
        files = tree(b"map: m1\nimport: conf/sub/a.conf\nmap: m4\n",
                     conf__sub__a_DOT_conf=b"map: m2\nimport: conf/b.conf\n",
                     conf__b_DOT_conf=b"map: m3\n",
                     conf__sub__conf__b_DOT_conf=b"map: WRONG_relative_to_importer\n")
        result = run(files)
        self.assertEqual(maps(result), ["m1", "m2", "m3", "m4"])
        self.assertEqual([(v["path"], v["depth"]) for v in result["visits"]],
                         [("conf/map_athena.conf", 0), ("conf/sub/a.conf", 1),
                          ("conf/b.conf", 2), ("npc/re/scripts_main.conf", 0)])
        b = result["visits"][2]
        self.assertEqual(b["from"], {"file": "conf/sub/a.conf", "line": 2, "visit": 1})
        self.assertEqual(b["sha256"], sha(b"map: m3\n"))
        self.assertEqual(result["status"], "complete")

    def test_map_config_npcs_precede_renewal_main_without_clear(self):
        files = tree(b"npc: npc/early.txt\n", b"npc: npc/main.txt\nimport: npc/more.conf\n",
                     npc__early_DOT_txt=b"x", npc__main_DOT_txt=b"y",
                     npc__more_DOT_conf=b"npc: npc/late.txt\n", npc__late_DOT_txt=b"z")
        result = run(files)
        self.assertEqual(npcs(result), ["npc/early.txt", "npc/main.txt", "npc/late.txt"])
        self.assertEqual([n["phase"] for n in result["npc_sources"]["files"]],
                         ["map_config", "npc_config", "npc_config"])
        self.assertEqual(result["npc_sources"]["files"][0]["sha256"], sha(b"x"))

    def test_npc_pass_does_not_accept_map_keys(self):
        result = run(tree(npc_main=b"map: nope\ndelmap: all\n"))
        self.assertEqual(maps(result), [])
        self.assertEqual({u["key"] for u in result["ignored_settings"]}, {"map", "delmap"})

    def test_import_cycle_and_depth_are_refused(self):
        files = tree(b"import: conf/a.conf\n", conf__a_DOT_conf=b"import: ./conf/map_athena.conf\n")
        with self.assertRaisesRegex(sel.SelectionError, "cycle"):
            run(files)
        chain = {f"rathena/conf/c{i}.conf": f"import: conf/c{i + 1}.conf\n".encode()
                 for i in range(sel.MAX_DEPTH + 2)}
        chain.update(tree(b"import: conf/c0.conf\n"))
        with self.assertRaisesRegex(sel.SelectionError, "deeper"):
            run(chain)
        # A diamond (same file imported twice, not nested) is legitimate.
        files = tree(b"import: conf/d.conf\nimport: conf/d.conf\n", conf__d_DOT_conf=b"map: d\n")
        self.assertEqual(maps(run(files)), ["d", "d"])

    def test_missing_case_mismatch_directory_and_scope_mark_incomplete(self):
        files = tree(b"import: conf/absent.conf\nimport: CONF/x.conf\nimport: conf\n"
                     b"import: log/x.conf\n", conf__x_DOT_conf=b"map: x\n")
        result = run(files)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual([d["kind"] for d in result["diagnostics"]],
                         ["import_missing", "import_case_mismatch",
                          "unsupported_directory_import", "import_outside_snapshot_scope"])
        self.assertEqual(result["diagnostics"][1]["detail"], ["rathena/conf/x.conf"])
        self.assertEqual(maps(result), [])
        result = run({"rathena/conf/map_athena.conf": b""})
        self.assertEqual(result["diagnostics"][0]["kind"], "import_missing")
        self.assertEqual(result["status"], "incomplete")

    def test_unsafe_paths_refused(self):
        for line in (b"import: ../etc/x\n", b"import: /etc/passwd\n", b"npc: npc/../../x\n",
                     b"npc: /abs.txt\n", b"npc: npc\\x.txt\n", b"import: caf\xc3\xa9\n"):
            with self.assertRaises(sel.SelectionError, msg=line):
                run(tree(line))


class MapList(unittest.TestCase):
    def test_duplicates_clear_all_and_delete_first(self):
        conf = (b"map: x\nmap: y\nmap: x\nmap: x\n"
                b"delmap: x.GAT\n"       # normalized 'x' removes the first x only
                b"delmap: X\n"           # strcmp is case-sensitive: no match
                b"map: z\n")
        result = run(tree(conf))
        self.assertEqual(maps(result), ["y", "x", "x", "z"])
        self.assertEqual(result["maps"]["distinct_names"], ["y", "x", "z"])
        self.assertEqual(result["maps"]["candidate_count"], 4)
        self.assertEqual(ops(result, "map_delete")[0]["slot"], 0)
        self.assertEqual(len(ops(result, "map_delete_none")), 1)
        result = run(tree(b"map: a\nmap: CLEAR\nmap: b\ndelmap: All\nmap: c\nmap: clear.gat\n"))
        self.assertEqual(maps(result), ["c", "clear"])

    def test_gat_clip_and_case(self):
        conf = (b"map: Prontera.GAT\nmap: abcdefghijklmn\nmap: abcdefghijk.gat\n"
                b"map: abcdefghijklmnop\nmap: abcdefghijk.gatxyz\nmap: .gat\n")
        result = run(tree(conf))
        self.assertEqual(maps(result), ["Prontera", "abcdefghijk", "abcdefghijk",
                                        "abcdefghijk", "abcdefghijk", ""])
        flags = [m.get("flags", []) for m in result["maps"]["candidates"]]
        self.assertEqual(flags[0], ["gat_stripped"])
        self.assertEqual(flags[3], ["too_long_warning", "clipped"])
        self.assertEqual(flags[5], ["gat_stripped", "empty_name"])
        # 16+ chars: only the first 15 are examined for '.gat' (string[len-4] at len 15).
        self.assertEqual(sel.map_name(b"abcdefghijk.gatX"), (b"abcdefghijk", [
            "too_long_warning", "gat_stripped"]))

    def test_capacity(self):
        conf = b"".join(b"map: m%d\n" % i for i in range(sel.MAP_SLOTS + 2))
        result = run(tree(conf))
        self.assertEqual(result["maps"]["candidate_count"], 1499)
        self.assertEqual([r["raw"] for r in result["maps"]["rejected_capacity"]],
                         ["m1499", "m1500"])
        self.assertEqual(result["status"], "complete")
        conf += b"delmap: m0\nmap: again\n"
        self.assertEqual(maps(run(tree(conf)))[-1], "again")


class NpcList(unittest.TestCase):
    def files(self, map_conf=b"", npc_main=b""):
        return tree(map_conf, npc_main, npc__x_DOT_txt=b"X", npc__y_DOT_txt=b"Y",
                    npc__sub__z_DOT_txt=b"Z")

    def test_exact_string_dedup_and_alias(self):
        result = run(self.files(npc_main=b"npc: npc/x.txt\nnpc: ./npc/x.txt\nnpc: npc/x.txt\n"
                                         b"npc: npc/./x.txt\nnpc: npc/x.txt  \n"))
        self.assertEqual(npcs(result), ["npc/x.txt", "./npc/x.txt", "npc/./x.txt"])
        self.assertEqual(len(ops(result, "npc_duplicate")), 2)
        self.assertEqual(result["npc_sources"]["distinct_manifest_paths"], 1)
        self.assertEqual(result["npc_sources"]["same_file_aliases"],
                         [{"manifest_path": "rathena/npc/x.txt",
                           "sources": ["npc/x.txt", "./npc/x.txt", "npc/./x.txt"]}])

    def test_clear_all_and_delete_exact_original(self):
        main = (b"npc: npc/x.txt\nnpc: npc/y.txt\n"
                b"delnpc: ./npc/x.txt\n"     # different raw string: no removal
                b"delnpc: npc/x.txt\n"
                b"npc: npc/x.txt\n")         # re-added at the end
        self.assertEqual(npcs(run(self.files(npc_main=main))), ["npc/y.txt", "npc/x.txt"])
        result = run(self.files(b"npc: npc/x.txt\n", b"npc: CLEAR\nnpc: npc/y.txt\n"
                                b"delnpc: ALL\nnpc: npc/sub/z.txt\n"))
        self.assertEqual(npcs(result), ["npc/sub/z.txt"])
        self.assertEqual([e["op"] for e in ops(result, "npc_clear", "npc_delete_all")],
                         ["npc_clear", "npc_delete_all"])

    def test_missing_directory_case_and_scope_not_added(self):
        main = (b"npc: npc/absent.txt\nnpc: npc/sub\nnpc: NPC/x.txt\nnpc: npc/X.txt\n"
                b"npc: custom/x.txt\nnpc: npc/x.txt/\nnpc: npc/x.txt\n")
        result = run(self.files(npc_main=main))
        self.assertEqual(npcs(result), ["npc/x.txt"])
        self.assertEqual([(d["kind"], d["line"]) for d in result["diagnostics"]],
                         [("npc_missing", 1), ("npc_directory", 2), ("npc_case_mismatch", 3),
                          ("npc_case_mismatch", 4), ("npc_outside_snapshot_scope", 5),
                          ("npc_missing", 6)])
        self.assertEqual(result["status"], "incomplete")


def write_tree(root, files, manifest=None):
    """Write a synthetic snapshot directory and return its manifest bytes."""
    for path, body in files.items():
        target = Path(root, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    if manifest is None:
        manifest = {"files": [{"path": p, "bytes": len(b), "sha256": sha(b)}
                              for p, b in sorted(files.items())]}
    data = json.dumps(manifest, sort_keys=True).encode()
    Path(root, sel.SNAPSHOT_MANIFEST).write_bytes(data)
    return data


class SnapshotVerification(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name, "snap")
        self.files = tree(b"map: a\n", b"npc: npc/x.txt\n", npc__x_DOT_txt=b"X")
        self.manifest = write_tree(self.root, self.files)
        self.pin = sha(self.manifest)
        self.counts = {"files": 3, "bytes": sum(len(b) for b in self.files.values())}

    def tearDown(self):
        self.tmp.cleanup()

    def read(self):
        return sel.read_snapshot(self.root, self.pin, self.counts)

    def test_valid_snapshot_reads(self):
        manifest, files = self.read()
        self.assertEqual(files, self.files)
        self.assertEqual(manifest, self.manifest)

    def test_pin_and_counts_enforced(self):
        with self.assertRaisesRegex(sel.SelectionError, "pinned"):
            sel.read_snapshot(self.root, "1" * 64, self.counts)
        with self.assertRaisesRegex(sel.SelectionError, "pinned"):
            sel.read_snapshot(self.root, self.pin, {"files": 4, "bytes": 1})
        # The CLI always uses the canonical pin and cannot be pointed at this fixture.
        out = Path(self.tmp.name, "out")
        self.assertEqual(sel.main([str(self.root), str(out)]), 2)
        self.assertFalse(os.path.lexists(out))

    def test_modified_file_extra_missing_and_links_refused(self):
        Path(self.root, "rathena/npc/x.txt").write_bytes(b"Y")
        with self.assertRaisesRegex(sel.SelectionError, "differs"):
            self.read()
        Path(self.root, "rathena/npc/x.txt").write_bytes(b"X")
        Path(self.root, "rathena/.DS_Store").write_bytes(b"")
        with self.assertRaisesRegex(sel.SelectionError, "file set"):
            self.read()
        os.unlink(Path(self.root, "rathena/.DS_Store"))
        os.unlink(Path(self.root, "rathena/npc/x.txt"))
        with self.assertRaisesRegex(sel.SelectionError, "file set"):
            self.read()
        os.symlink("../conf/map_athena.conf", Path(self.root, "rathena/npc/x.txt"))
        with self.assertRaisesRegex(sel.SelectionError, "symlink"):
            self.read()
        os.unlink(Path(self.root, "rathena/npc/x.txt"))
        Path(self.root, "rathena/npc/x.txt").write_bytes(b"X")
        os.mkfifo(Path(self.root, "rathena/fifo"))
        with self.assertRaisesRegex(sel.SelectionError, "special"):
            self.read()
        os.unlink(Path(self.root, "rathena/fifo"))
        link = Path(self.tmp.name, "link")
        os.symlink(self.root, link)
        with self.assertRaisesRegex(sel.SelectionError, "link"):
            sel.read_snapshot(link, self.pin, self.counts)
        self.read()

    def test_symlinked_directory_refused(self):
        os.rename(Path(self.root, "rathena/npc"), Path(self.tmp.name, "npc"))
        os.symlink(Path(self.tmp.name, "npc"), Path(self.root, "rathena/npc"))
        with self.assertRaisesRegex(sel.SelectionError, "symlink"):
            self.read()

    def test_manifest_shape_refused(self):
        self.assertRaises(sel.SelectionError, sel.verify_manifest, b'{"files": 1}', {}, None, None)
        self.assertRaises(sel.SelectionError, sel.verify_manifest,
                          b'{"files": [], "files": []}', {}, None, None)
        dup = json.dumps({"files": [{"path": "a", "bytes": 0, "sha256": sha(b"")}] * 2}).encode()
        self.assertRaises(sel.SelectionError, sel.verify_manifest, dup, {"a": b""}, None, None)


class Publication(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.parent = Path(self.tmp.name, "private")
        self.parent.mkdir(mode=0o700)
        self.files = tree(b"map: a\nuserid: hidden_user\n", b"npc: npc/x.txt\n",
                          npc__x_DOT_txt=b"X")

    def tearDown(self):
        self.tmp.cleanup()

    def test_deterministic_and_private(self):
        first = sel.render(sel.build_selection(self.files, "a" * 64, "b" * 64))
        second = sel.render(sel.build_selection(dict(reversed(list(self.files.items()))),
                                                "a" * 64, "b" * 64))
        self.assertEqual(first, second)
        self.assertNotIn(b"hidden_user", first)
        target = sel.write_output(self.parent / "out", first)
        self.assertEqual(sorted(os.listdir(target)), [sel.OUTPUT_COMPLETE, sel.OUTPUT_MANIFEST])
        self.assertEqual(Path(target, sel.OUTPUT_MANIFEST).read_bytes(), first)
        complete = json.loads(Path(target, sel.OUTPUT_COMPLETE).read_bytes())
        self.assertEqual(complete["selection_manifest_sha256"], sha(first))
        self.assertEqual(stat.S_IMODE(os.lstat(target).st_mode) & 0o077, 0)
        for name in os.listdir(target):
            self.assertEqual(stat.S_IMODE(os.lstat(Path(target, name)).st_mode) & 0o077, 0)
        self.assertEqual(sorted(os.listdir(self.parent)), ["out"])  # staging removed

    def test_existing_destinations_preserved(self):
        data = sel.render(sel.build_selection(self.files, "a" * 64))
        existing_dir = self.parent / "dir"
        existing_dir.mkdir()
        Path(existing_dir, "keep").write_bytes(b"keep")
        existing_file = self.parent / "file"
        existing_file.write_bytes(b"keep")
        live = self.parent / "live"
        os.symlink(existing_dir, live)
        dangling = self.parent / "dangling"
        os.symlink(self.parent / "nowhere", dangling)
        for target in (existing_dir, existing_file, live, dangling):
            with self.assertRaisesRegex(sel.SelectionError, "already exists"):
                sel.write_output(target, data)
        self.assertEqual(os.listdir(existing_dir), ["keep"])
        self.assertEqual(existing_file.read_bytes(), b"keep")
        self.assertFalse(os.path.exists(self.parent / "nowhere"))
        self.assertTrue(os.path.islink(dangling))
        self.assertEqual(sorted(os.listdir(self.parent)),
                         ["dangling", "dir", "file", "live"])

    def test_untrusted_parent_refused(self):
        open_parent = Path(self.tmp.name, "open")
        open_parent.mkdir()
        os.chmod(open_parent, 0o777)
        with self.assertRaisesRegex(sel.SelectionError, "writable"):
            sel.write_output(open_parent / "out", b"{}\n")
        with self.assertRaisesRegex(sel.SelectionError, "does not exist"):
            sel.write_output(Path(self.tmp.name, "absent", "out"), b"{}\n")
        self.assertEqual(os.listdir(open_parent), [])


@unittest.skipUnless((PINNED_SNAPSHOT / sel.SNAPSHOT_MANIFEST).is_file(),
                     f"pinned snapshot absent: {PINNED_SNAPSHOT} (set RENEWAL_SELECTION_SNAPSHOT)")
class PinnedSnapshot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        manifest, files = sel.read_snapshot(PINNED_SNAPSHOT)
        cls.result = sel.build_selection(files, sha(manifest))
        cls.manifest_sha = sha(manifest)

    def test_pinned_selection(self):
        result = self.result
        self.assertEqual(self.manifest_sha, sel.PINNED_MANIFEST_SHA256)
        self.assertEqual(result["visits"][0]["path"], "conf/map_athena.conf")
        roots = [v["path"] for v in result["visits"] if v["depth"] == 0]
        self.assertEqual(roots, ["conf/map_athena.conf", "npc/re/scripts_main.conf"])
        by_source = {n["source"]: n for n in result["npc_sources"]["files"]}
        for source, digest in PINNED_NPC.items():
            self.assertEqual(by_source[source]["sha256"], digest)
            self.assertEqual(by_source[source]["manifest_path"], "rathena/" + source)
        self.assertEqual((by_source["npc/custom/population/arena.txt"]["file"],
                          by_source["npc/custom/population/arena.txt"]["line"]),
                         ("npc/scripts_custom.conf", 121))
        self.assertEqual(by_source["npc/custom/population/recruiter.txt"]["line"], 122)
        rendered = sel.render(result)
        for credential in (b'"s1"', b'"p1"'):  # stock userid/passwd values
            self.assertNotIn(credential, rendered)


if __name__ == "__main__":
    unittest.main()
