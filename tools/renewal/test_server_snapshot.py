"""Tests for server_snapshot. Run: python3 -I -m unittest discover -s tools/renewal

Synthetic archives are built in memory. The pinned-input tests read the real
packaged archive from $RENEWAL_IMAGES_TAR, or the coordinator's default
.tools/renewal/app-unpacked path, and are skipped when it is absent.
"""

import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import server_snapshot as snap  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = (REPO / ".tools/renewal/app-unpacked/Ragnarok Offline.app/Contents/Resources"
                 "/payload/dist/images.tar.gz")
PINNED_INPUT = Path(os.environ.get("RENEWAL_IMAGES_TAR", DEFAULT_INPUT))
PINNED_FILE_SHA = {
    "academy": "b2ab5f7de7e1c36e4f58b8447a80d4cb089e8bf45aeade59953c6a70004f27fd",
    "map_index": "4fd52bc6c7b89c4a1267ee5be73dd994b8b9bedf9caf201a246a4a0cc79819ce",
    "scripts_main": "85bc6dd2e4231cd1ae0e73946ba469865396c330e7bbf5bdd5f776349ad898bf",
}
# Root's comparison sentinels for the pinned archive only (T06.001 brief).
PINNED_SENTINELS = {"conf": 96, "db": 293, "npc": 1182, "sql-files": 112}
TAG = "test/rathena:1"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def tar(entries, gz=False):
    """entries: (name, data) for files, or (name, kind[, linkname]) with kind in dir/sym/hard/fifo."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.PAX_FORMAT) as tf:
        for entry in entries:
            name, value = entry[0], entry[1]
            info = tarfile.TarInfo(name)
            if isinstance(value, bytes):
                info.size = len(value)
                tf.addfile(info, io.BytesIO(value))
                continue
            info.type = {"dir": tarfile.DIRTYPE, "sym": tarfile.SYMTYPE,
                         "hard": tarfile.LNKTYPE, "fifo": tarfile.FIFOTYPE}[value]
            if len(entry) > 2:
                info.linkname = entry[2]
            tf.addfile(info)
    data = buf.getvalue()
    return gzip.compress(data, mtime=0) if gz else data


def layers_tree(*layers):
    return snap.resolve_layers([(sha(t), t) for t in (tar(l) for l in layers)])


def image(layers, tag=TAG, extra_manifest=(), extra_members=(), config=None, tamper=None):
    """Return gzip outer archive bytes for one tagged image plus optional extras."""
    blobs = {}
    layer_bytes = [tar(l) for l in layers]
    for data in layer_bytes:
        blobs[sha(data)] = data
    config = config if config is not None else {
        "rootfs": {"type": "layers", "diff_ids": ["sha256:" + sha(d) for d in layer_bytes]}}
    config_bytes = json.dumps(config).encode()
    blobs[sha(config_bytes)] = config_bytes
    entry = {"Config": "blobs/sha256/" + sha(config_bytes), "RepoTags": [tag],
             "Layers": ["blobs/sha256/" + sha(d) for d in layer_bytes]}
    members = [("blobs/sha256/" + d, b) for d, b in sorted(blobs.items())]
    if tamper:
        members = [(n, tamper.get(n.rsplit("/", 1)[-1], b)) for n, b in members]
    manifest = json.dumps([entry, *extra_manifest]).encode()
    return tar([*members, ("manifest.json", manifest), *extra_members], gz=True)


BASE = [("rathena", "dir"), ("rathena/conf", "dir"), ("rathena/conf/a.conf", b"conf-a\n"),
        ("rathena/db", "dir"), ("rathena/db/re", "dir"), ("rathena/db/re/mob.yml", b"mob\n"),
        ("rathena/npc", "dir"), ("rathena/npc/scripts_main.conf", b"npc\n"),
        ("rathena/sql-files", "dir"), ("rathena/sql-files/main.sql", b"sql\n"),
        ("rathena/map-server", b"\x7fELF binary"), ("rathena/log", "dir"),
        ("rathena/log/x.log", b"log"), ("bin", "dir"), ("bin/sh", "sym", "busybox")]


def contents(files):
    return dict(sorted(files.items()))


class NormalizeTest(unittest.TestCase):
    def test_accepts_relative_and_dot_slash(self):
        self.assertEqual(snap.normalize_member("./rathena/db/", "t"), "rathena/db")
        self.assertEqual(snap.normalize_member("./", "t"), "")

    def test_rejects_unsafe_names(self):
        for name in ("/etc/passwd", "../x", "a/../b", "a/./b", "a//b", "a\\b", "..",
                     "a\udcff"):
            with self.subTest(name=name), self.assertRaises(snap.SnapshotError):
                snap.normalize_member(name, "t")


class OuterTest(unittest.TestCase):
    def build(self, data, expect=None):
        return snap.build_snapshot(data, TAG, expect)

    def test_end_to_end_selects_only_scope_files(self):
        files, manifest = self.build(image([BASE]))
        self.assertEqual(sorted(files), ["rathena/conf/a.conf", "rathena/db/re/mob.yml",
                                         "rathena/npc/scripts_main.conf",
                                         "rathena/sql-files/main.sql"])
        self.assertEqual(files["rathena/db/re/mob.yml"], b"mob\n")
        self.assertEqual(manifest["ignored"]["out_of_scope_file"], 2)
        self.assertEqual(manifest["ignored"]["out_of_scope_link"], 1)
        self.assertEqual(manifest["counts"]["by_dir"]["db"], {"files": 1, "bytes": 4})

    def test_rejects_unsafe_outer_member_even_unreferenced(self):
        for name in ("../evil", "/abs", "x\\y"):
            with self.subTest(name=name), self.assertRaisesRegex(snap.SnapshotError, "member"):
                self.build(image([BASE], extra_members=[(name, b"x")]))

    def test_rejects_duplicate_normalized_outer_member(self):
        with self.assertRaisesRegex(snap.SnapshotError, "duplicate"):
            self.build(image([BASE], extra_members=[("./manifest.json", b"[]")]))

    def test_rejects_blob_digest_mismatch(self):
        layer = tar(BASE)
        bad = image([BASE], tamper={sha(layer): layer[:-1024] + b"\1" * 1024})
        with self.assertRaisesRegex(snap.SnapshotError, "has SHA-256"):
            self.build(bad)

    def test_rejects_missing_and_nonregular_blob(self):
        data = tar(BASE)
        ref = "blobs/sha256/" + sha(data)
        config = json.dumps({"rootfs": {"diff_ids": ["sha256:" + sha(data)]}}).encode()
        entry = {"Config": "blobs/sha256/" + sha(config), "RepoTags": [TAG], "Layers": [ref]}
        common = [("blobs/sha256/" + sha(config), config),
                  ("manifest.json", json.dumps([entry]).encode())]
        with self.assertRaisesRegex(snap.SnapshotError, "missing member"):
            self.build(tar(common, gz=True))
        with self.assertRaisesRegex(snap.SnapshotError, "not a regular file"):
            self.build(tar(common + [(ref, "sym", "elsewhere")], gz=True))

    def test_rejects_unsupported_blob_reference(self):
        data = image([BASE])
        outer = snap.OuterArchive(data)
        with self.assertRaisesRegex(snap.SnapshotError, "unsupported blob reference"):
            outer.blob("abc/layer.tar", "layer")

    def test_rejects_ambiguous_or_missing_tag(self):
        other = {"Config": "blobs/sha256/" + "0" * 64, "RepoTags": [TAG], "Layers": []}
        with self.assertRaisesRegex(snap.SnapshotError, "2 images tagged"):
            self.build(image([BASE], extra_manifest=[other]))
        with self.assertRaisesRegex(snap.SnapshotError, "0 images tagged"):
            snap.build_snapshot(image([BASE]), "test/rathena:2", None)

    def test_rejects_diff_id_mismatch_and_pin_mismatch(self):
        with self.assertRaisesRegex(snap.SnapshotError, "diff_ids"):
            self.build(image([BASE], config={"rootfs": {"diff_ids": []}}))
        with self.assertRaisesRegex(snap.SnapshotError, "pinned image"):
            self.build(image([BASE]), expect=snap.PINNED_IMAGE)

    def test_rejects_outer_size_and_hash_pin_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "images.tar.gz"
            path.write_bytes(b"not the archive")
            with self.assertRaisesRegex(snap.SnapshotError, "bytes, pinned archive"):
                snap.read_outer(path)
            with self.assertRaisesRegex(snap.SnapshotError, "not the pinned archive"):
                snap.read_outer(path, {"bytes": 15, "sha256": "0" * 64})
            self.assertEqual(snap.read_outer(path, {"bytes": 15, "sha256": sha(b"not the archive")}),
                             b"not the archive")

    def test_input_symlink_and_fifo_are_refused_without_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "archive").write_bytes(b"data")
            (root / "link").symlink_to(root / "archive")
            os.mkfifo(root / "fifo")
            for name in ("link", "fifo"):
                with self.subTest(name), mock.patch("sys.stderr", io.StringIO()):
                    self.assertEqual(snap.main([str(root / name), str(root / "out")]), 2)
                self.assertFalse(os.path.lexists(root / "out"))
            self.assertEqual((root / "archive").read_bytes(), b"data")

    def test_rejects_duplicate_json_keys_at_any_depth(self):
        for body in (b'{"Config":"first","Config":"second"}',
                     b'{"rootfs":{"diff_ids":[],"diff_ids":["other"]}}'):
            with self.subTest(body), self.assertRaisesRegex(snap.SnapshotError, "duplicate JSON"):
                snap.load_json(body, "test metadata")

    def test_rejects_falsey_nonobject_layer_sources(self):
        original = image([BASE])
        with tarfile.open(fileobj=io.BytesIO(original), mode="r:gz") as outer:
            members = [(m.name, outer.extractfile(m).read()) for m in outer.getmembers()]
        entry = json.loads(dict(members)["manifest.json"])[0]
        digest = "sha256:" + entry["Layers"][0].rsplit("/", 1)[1]
        for value in ([], "", 0, None):
            for level in ("container", "entry"):
                changed = dict(entry)
                changed["LayerSources"] = value if level == "container" else {digest: value}
                data = tar([(name, json.dumps([changed]).encode()
                             if name == "manifest.json" else body)
                            for name, body in members], gz=True)
                with self.subTest(value=value, level=level):
                    with self.assertRaisesRegex(snap.SnapshotError, "LayerSources"):
                        self.build(data)

    def test_cli_refuses_unpinned_input_without_creating_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "images.tar.gz"
            path.write_bytes(image([BASE]))
            out = Path(tmp) / "out"
            with mock.patch("sys.stderr", io.StringIO()) as err:
                self.assertEqual(snap.main([str(path), str(out)]), 2)
            self.assertIn("pinned archive", err.getvalue())
            self.assertFalse(os.path.lexists(out))
            self.assertEqual(sorted(os.listdir(tmp)), ["images.tar.gz"])

    def test_deterministic_manifest(self):
        data = image([BASE, [("rathena/db/re/mob.yml", b"mob2\n")]])
        first = snap.render_manifest(self.build(data)[1])
        second = snap.render_manifest(self.build(data)[1])
        self.assertEqual(first, second)
        self.assertNotIn(os.path.expanduser("~").encode(), first)
        record = json.loads(first)["files"][1]
        self.assertEqual(record["path"], "rathena/db/re/mob.yml")
        self.assertEqual(record["source"]["layer"], 1)
        self.assertEqual(record["source"]["earlier_definitions"], 1)
        self.assertEqual(record["sha256"], sha(b"mob2\n"))


class LayerTest(unittest.TestCase):
    def files(self, *layers):
        return {p: n["data"] for p, n in layers_tree(*layers).selected_files().items()}

    def test_upper_layer_replaces_file(self):
        tree = layers_tree(BASE, [("rathena/npc/scripts_main.conf", b"new\n")])
        node = tree.selected_files()["rathena/npc/scripts_main.conf"]
        self.assertEqual(node["data"], b"new\n")
        self.assertEqual((node["layer"], node["earlier_definitions"]), (1, 1))

    def test_repeated_definition_in_one_layer_last_wins(self):
        tree = layers_tree([("rathena/db/x.txt", b"one"), ("rathena/db/x.txt", b"two")])
        node = tree.selected_files()["rathena/db/x.txt"]
        self.assertEqual((node["data"], node["occurrence"], node["ordinal"]), (b"two", 2, 1))

    def test_file_replaces_directory_and_directory_replaces_file(self):
        files = self.files(BASE, [("rathena/db/re", b"now a file")])
        self.assertEqual(files["rathena/db/re"], b"now a file")
        self.assertNotIn("rathena/db/re/mob.yml", files)
        files = self.files(BASE, [("rathena/conf/a.conf", "dir"),
                                  ("rathena/conf/a.conf/inner", b"inner")])
        self.assertNotIn("rathena/conf/a.conf", files)
        self.assertEqual(files["rathena/conf/a.conf/inner"], b"inner")

    def test_dir_entry_merges_with_lower_dir(self):
        files = self.files(BASE, [("rathena/db", "dir"), ("rathena/db/new.yml", b"n")])
        self.assertIn("rathena/db/re/mob.yml", files)
        self.assertIn("rathena/db/new.yml", files)

    def test_whiteout_file_and_subtree(self):
        files = self.files(BASE, [("rathena/conf/.wh.a.conf", b""),
                                  ("rathena/db/.wh.re", b"")])
        self.assertNotIn("rathena/conf/a.conf", files)
        self.assertFalse(any(p.startswith("rathena/db/") for p in files))

    def test_ancestor_whiteout_removes_whole_tree(self):
        tree = layers_tree(BASE, [(".wh.rathena", b"")])
        self.assertEqual(tree.selected_files(), {})
        tree = layers_tree(BASE, [(".wh.rathena", b""), ("rathena/npc/new.txt", b"x")])
        self.assertEqual(list(tree.selected_files()), ["rathena/npc/new.txt"])

    def test_opaque_dir_hides_lower_but_keeps_same_layer(self):
        files = self.files(BASE, [("rathena/db", "dir"), ("rathena/db/fresh.yml", b"f"),
                                  ("rathena/db/.wh..wh..opq", b"")])
        self.assertEqual([p for p in files if p.startswith("rathena/db/")],
                         ["rathena/db/fresh.yml"])
        self.assertIn("rathena/conf/a.conf", files)

    def test_whiteout_then_recreate_in_same_layer(self):
        files = self.files(BASE, [("rathena/conf/.wh.a.conf", b""),
                                  ("rathena/conf/a.conf", b"recreated")])
        self.assertEqual(files["rathena/conf/a.conf"], b"recreated")

    def test_malformed_whiteouts_reject_before_deleting_lower_data(self):
        markers = ("rathena/db/.wh.re", "rathena/db/.wh..wh..opq",
                   ".wh.rathena", ".wh..wh..opq")
        for marker in markers:
            for value in ("sym", "hard", "fifo", "dir", b"nonempty"):
                with self.subTest(marker=marker, value=value):
                    tree = layers_tree(BASE)
                    before = {p: n["data"] for p, n in tree.selected_files().items()}
                    bad = (marker, value, "never-followed") if value in ("sym", "hard") else (marker, value)
                    upper = tar([("rathena/conf/.wh.a.conf", b""), bad])
                    with self.assertRaisesRegex(snap.SnapshotError, "empty nonsparse regular"):
                        tree.apply_layer(1, sha(upper), upper)
                    self.assertEqual({p: n["data"] for p, n in tree.selected_files().items()}, before)

    def test_opaque_child_of_lower_file_is_explicitly_unsupported(self):
        with self.assertRaisesRegex(snap.SnapshotError, "non-directory"):
            layers_tree([("rathena/conf/sub", b"keep")],
                        [("rathena/conf/sub/.wh..wh..opq", b"")])

    def test_malformed_marker_names_reject_before_any_deletion(self):
        for marker in ("rathena/db/.wh.", "rathena/db/.wh..", ".wh..wh.plnk",
                       "unselected/.wh..wh.plnk"):
            with self.subTest(marker=marker):
                tree = layers_tree(BASE)
                before = {p: n["data"] for p, n in tree.selected_files().items()}
                upper = tar([("rathena/conf/.wh.a.conf", b""), (marker, b"")])
                with self.assertRaisesRegex(snap.SnapshotError, "unsupported whiteout"):
                    tree.apply_layer(1, sha(upper), upper)
                self.assertEqual({p: n["data"] for p, n in tree.selected_files().items()}, before)

    def test_rejects_selected_links_and_specials(self):
        cases = {
            "symlink": [("rathena/npc/link.txt", "sym", "/etc/passwd")],
            "hardlink": [("rathena/npc/hard.txt", "hard", "rathena/conf/a.conf")],
            "fifo": [("rathena/db/pipe", "fifo")],
            "scope dir link": [("rathena/db", "sym", "/tmp")],
            "root link": [(".wh.rathena", b""), ("rathena", "sym", "/")],
        }
        for label, upper in cases.items():
            with self.subTest(label), self.assertRaises(snap.SnapshotError):
                layers_tree(BASE, upper).selected_files()

    def test_rejects_selected_entry_below_link(self):
        with self.assertRaisesRegex(snap.SnapshotError, "never followed"):
            layers_tree(BASE, [("rathena/db/re", "sym", "/etc")],
                        [("rathena/db/re/mob.yml", b"through link")])

    def test_link_removed_later_is_fine_and_outside_links_are_counted(self):
        tree = layers_tree(BASE, [("rathena/npc/link.txt", "sym", "x")],
                           [("rathena/npc/.wh.link.txt", b"")])
        self.assertNotIn("rathena/npc/link.txt", tree.selected_files())
        tree = layers_tree(BASE, [("lib", "sym", "usr/lib")], [("lib/thing.so", b"so")])
        self.assertEqual(tree.unresolved, ["lib/thing.so"])
        self.assertEqual(tree.ignored_counts()["out_of_scope_link"], 2)

    def test_rejects_unsafe_inner_member_and_unsupported_marker(self):
        for name in ("../escape", "/abs/file", "rathena\\db\\x"):
            with self.subTest(name=name), self.assertRaises(snap.SnapshotError):
                layers_tree(BASE, [(name, b"x")])
        with self.assertRaisesRegex(snap.SnapshotError, "unsupported whiteout"):
            layers_tree(BASE, [("rathena/db/.wh..wh.plnk", b"")])


class OutputTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.files, manifest = snap.build_snapshot(image([BASE]), TAG, None)
        self.manifest = snap.render_manifest(manifest)

    def tearDown(self):
        self.tmp.cleanup()

    def test_publishes_exact_bytes_privately(self):
        out = snap.write_output(self.root / "out", self.files, self.manifest)
        for path, data in self.files.items():
            self.assertEqual((out / path).read_bytes(), data)
            self.assertEqual(stat.S_IMODE((out / path).stat().st_mode) & 0o077, 0)
        self.assertEqual((out / snap.MANIFEST_NAME).read_bytes(), self.manifest)
        self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o700)
        self.assertEqual(sorted(os.listdir(self.root)), ["out"])  # staging removed
        self.assertFalse((out / "rathena/log").exists())

    def test_refuses_existing_destinations_unchanged(self):
        (self.root / "file").write_bytes(b"keep")
        (self.root / "dir").mkdir()
        (self.root / "dir/inside").write_bytes(b"keep")
        (self.root / "emptydir").mkdir()
        os.symlink(self.root / "dir", self.root / "live")
        os.symlink(self.root / "missing", self.root / "dangling")
        for name in ("file", "dir", "emptydir", "live", "dangling"):
            with self.subTest(name), self.assertRaisesRegex(snap.SnapshotError, "already exists"):
                snap.write_output(self.root / name, self.files, self.manifest)
        self.assertEqual((self.root / "file").read_bytes(), b"keep")
        self.assertEqual(os.listdir(self.root / "dir"), ["inside"])
        self.assertEqual(os.listdir(self.root / "emptydir"), [])
        self.assertEqual(os.readlink(self.root / "dangling"), str(self.root / "missing"))
        self.assertFalse(os.path.lexists(self.root / "missing"))
        self.assertEqual(sorted(os.listdir(self.root)),
                         ["dangling", "dir", "emptydir", "file", "live"])

    def test_destination_appearing_during_publish_is_preserved(self):
        target = self.root / "out"
        real_mkdir = os.mkdir

        def racing_mkdir(path, *args, **kw):
            if os.path.basename(path) == "out":  # parent is realpath-resolved
                os.symlink(self.root / "nowhere", target)
            return real_mkdir(path, *args, **kw)

        with mock.patch("os.mkdir", racing_mkdir):
            with self.assertRaisesRegex(snap.SnapshotError, "could not publish"):
                snap.write_output(target, self.files, self.manifest)
        self.assertEqual(os.readlink(target), str(self.root / "nowhere"))
        self.assertEqual(sorted(os.listdir(self.root)), ["out"])

    def test_requires_trusted_existing_parent(self):
        with self.assertRaisesRegex(snap.SnapshotError, "does not exist"):
            snap.write_output(self.root / "missing/out", self.files, self.manifest)
        shared = self.root / "shared"
        shared.mkdir()
        os.chmod(shared, 0o777)
        with self.assertRaisesRegex(snap.SnapshotError, "not group/world"):
            snap.write_output(shared / "out", self.files, self.manifest)

    def test_rejects_case_collisions(self):
        with self.assertRaisesRegex(snap.SnapshotError, "collide"):
            snap.build_snapshot(image([[("rathena/db/Mob.yml", b"a"),
                                        ("rathena/db/mob.yml", b"b")]]), TAG, None)

    def test_rejects_aliased_directory_prefixes_and_file_directory_aliases(self):
        pairs = (("A/one.txt", "a/two.txt"), ("é/one.txt", "e\u0301/two.txt"),
                 ("A", "a/child.txt"), ("é", "e\u0301/child.txt"))
        for first, second in pairs:
            paths = {"rathena/conf/" + first: b"one", "rathena/conf/" + second: b"two"}
            with self.subTest(first=first, second=second):
                with self.assertRaisesRegex(snap.SnapshotError, "collide"):
                    snap.build_snapshot(image([list(paths.items())]), TAG, None)
                with self.assertRaisesRegex(snap.SnapshotError, "collide"):
                    snap.write_output(self.root / "out", paths, self.manifest)
                self.assertFalse(os.path.lexists(self.root / "out"))
        paths = {"rathena/conf/A/one.txt": b"one", "rathena/conf/A/two.txt": b"two"}
        snap.check_collisions(paths)  # Repeated identical directory prefixes are valid.

    def test_direct_writer_refuses_unsafe_paths_before_staging(self):
        for path in ("../escape", "rathena/conf/../../escape", "/absolute", "other/file"):
            with self.subTest(path), self.assertRaises(snap.SnapshotError):
                snap.write_output(self.root / "out", {path: b"bad"}, self.manifest)
            self.assertEqual(list(self.root.iterdir()), [])

    def test_failed_readback_leaves_no_completion_manifest(self):
        target = self.root / "out"
        with mock.patch.object(snap, "_read_back", return_value=b"corrupt"):
            with self.assertRaisesRegex(snap.SnapshotError, "incomplete output"):
                snap.write_output(target, self.files, self.manifest)
        self.assertTrue(target.is_dir())
        self.assertFalse((target / snap.MANIFEST_NAME).exists())
        self.assertFalse(list(self.root.glob(".snapshot-staging-*")))


@unittest.skipUnless(PINNED_INPUT.is_file(), f"pinned input absent: {PINNED_INPUT}")
class PinnedInputTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = snap.read_outer(PINNED_INPUT)
        cls.files, cls.manifest = snap.build_snapshot(cls.data)

    def test_sentinels_and_named_files(self):
        by_dir = {d: v["files"] for d, v in self.manifest["counts"]["by_dir"].items()}
        self.assertEqual(by_dir, PINNED_SENTINELS)
        digests = {sha(body) for body in self.files.values()}
        for label, digest in PINNED_FILE_SHA.items():
            with self.subTest(label):
                self.assertIn(digest, digests)
        self.assertEqual(self.manifest["input"]["layers"][-1]["digest"],
                         "sha256:" + snap.PINNED_IMAGE["layers"][-1])
        self.assertEqual(self.manifest["unresolved_out_of_scope"], [])

    def test_every_file_matches_direct_layer_read(self):
        """Re-read each file's recorded member and check no later exact-path entry.
        This is a pinned-input byte check, not a general ancestor/whiteout oracle.
        """
        outer = tarfile.open(fileobj=io.BytesIO(self.data), mode="r:gz")
        manifest = json.load(outer.extractfile("manifest.json"))
        entry = [e for e in manifest if snap.PINNED_TAG in e["RepoTags"]][0]
        layers = []
        for ref in entry["Layers"]:
            body = outer.extractfile(ref).read()
            self.assertEqual("blobs/sha256/" + sha(body), ref)
            tf = tarfile.open(fileobj=io.BytesIO(body), mode="r:")
            layers.append((tf, {m.name: m for m in tf.getmembers()}))
        records = self.manifest["files"]
        self.assertEqual(len(records), len(self.files))
        for record in records:
            tf, members = layers[record["source"]["layer"]]
            info = members[record["source"]["member"]]
            body = tf.extractfile(info).read()
            self.assertEqual(sha(body), record["sha256"])
            self.assertEqual(body, self.files[record["path"]])
            for later_tf, later in layers[record["source"]["layer"] + 1:]:
                self.assertNotIn(record["path"], later)
        whiteouts = [n for _, members in layers for n in members if ".wh." in n
                     and n.startswith(snap.SCOPE_ROOT)]
        self.assertEqual(whiteouts, [])

    def test_cli_publish_and_determinism(self):
        with tempfile.TemporaryDirectory() as tmp:
            outputs = []
            for name in ("a", "b"):
                with mock.patch("sys.stdout", io.StringIO()) as out:
                    self.assertEqual(snap.main([str(PINNED_INPUT), os.path.join(tmp, name)]), 0)
                outputs.append(json.loads(out.getvalue()))
            self.assertEqual(outputs[0]["manifest_sha256"], outputs[1]["manifest_sha256"])
            root = Path(tmp) / "a"
            manifest = json.loads((root / snap.MANIFEST_NAME).read_bytes())
            on_disk = sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())
            self.assertEqual(on_disk, sorted([snap.MANIFEST_NAME] +
                                             [r["path"] for r in manifest["files"]]))
            for record in manifest["files"]:
                self.assertEqual(sha((root / record["path"]).read_bytes()), record["sha256"])


if __name__ == "__main__":
    unittest.main()
