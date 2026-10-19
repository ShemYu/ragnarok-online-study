"""Tests for carocc_zh_pilot. Run: python3 -I -m unittest discover -s tools/renewal

Synthetic inputs are written here; no stock script is committed. The tests on
the real pinned academy.txt run only when CAROCC_ACADEMY names that file and
are reported as skipped otherwise.
"""

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import carocc_zh_pilot as pilot  # noqa: E402

ACADEMY = os.environ.get("CAROCC_ACADEMY")
PROFILE = Path(__file__).resolve().parents[2] / "docs/project/fixtures/T05.012-profile.json"

# The 0.1.0 translations, which 0.2.0 must keep byte for byte and in order.
ORIGINAL_EIGHT = (
    (569, "mes", "Hello?", "你好？"),
    (570, "mes", "Is it your first time on Izlude?", "你是第一次來到 Izlude 嗎？"),
    (572, "select", "Hello?", "你好？"),
    (572, "select", "Let me get on the ship!", "讓我上船吧！"),
    (572, "select", "I don't know what to do.", "我不知道該做什麼。"),
    (575, "mes", "You look strong and able!", "你看起來既強壯又能幹！"),
    (576, "mes", "I like able people like you!", "我就喜歡像你這樣能幹的人！"),
    (577, "mes", "Always be healthy and strong as you are now.", "希望你永遠都像現在這樣健康又強壯。"),
)
NAVI = b"<NAVI>[Hun]<INFO>izlude,122,207</INFO></NAVI>"
LINE_693_EN = b"My friend " + NAVI + b" will be around the academy entrance."
LINE_693_ZH = "我的朋友 ".encode() + NAVI + " 就在學院入口附近。".encode()

SYNTHETIC = (
    b"// synthetic, not stock\n"
    b"izlude,198,213,3\tscript\tCaptain Carocc#iz\t4_M_REINDEER,5,5,{\n"
    b"\tmes \"[Carocc]\";\n"
    b"\tmes \"Hello?\";\n"
    b"\tswitch(select(\"Hello?\", \"Bye.\")) {\n"
    b"\tcase 1:\n"
    b"\t\tmes \"Fine.\";\n"
    b"\t}\r\n"
    b"OnInit:\n"
    b"\tend;\n"
    b"}\n"
    b"\n"
    b"izlude_a,198,213,3\tduplicate(Captain Carocc#iz)\tCaptain Carocc#iz_a\t4_M_REINDEER,5,5\n"
)
SYN_TRANSLATIONS = (
    (4, "mes", "Hello?", "你好？"),
    (5, "select", "Hello?", "你好？"),
    (5, "select", "Bye.", "再見。"),
    (7, "mes", "Fine.", "很好。"),
)


def source_for(data, first=2, last=11, duplicates=(13,)):
    lines = pilot.split_lines(data)
    block = b"".join(lines[first - 1:last])
    return pilot.Source(hashlib.sha256(data).hexdigest(), len(data), first, last,
                        hashlib.sha256(block).hexdigest(), lines[first - 1].rstrip(b"\n"), duplicates)


def block_of(script):
    """The copied block of a generated script: clone header .. first closing brace line."""
    lines = pilot.split_lines(script)
    start = next(i for i, l in enumerate(lines) if b"\tscript\tCaptain Carocc#t05zh\t" in l)
    end = next(i for i in range(start, len(lines)) if lines[i] == b"}\n")
    return lines[start:end + 1], lines[end + 1:]


class SyntheticTests(unittest.TestCase):
    def setUp(self):
        self.source = source_for(SYNTHETIC)

    def generate(self, data=SYNTHETIC, translations=SYN_TRANSLATIONS, source=None):
        return pilot.generate(data, source or self.source, translations)

    def test_only_header_and_translated_lines_change(self):
        script, meta = self.generate()
        script.decode("utf-8")
        block, rest = block_of(script)
        src = pilot.split_lines(SYNTHETIC)[1:11]
        self.assertEqual(len(block), len(src))
        changed = [i for i, (a, b) in enumerate(zip(src, block)) if a != b]
        self.assertEqual(changed, [0, 2, 3, 5])
        self.assertEqual(block[3], '\tswitch(select("你好？", "再見。")) {\n'.encode())
        self.assertEqual(block[6], b"\t}\r\n")  # foreign line ending kept
        self.assertEqual(b"".join(rest), b"\n" + pilot.controller())
        self.assertNotIn(b"duplicate(", script)
        self.assertEqual(meta["excluded_duplicates"]["names"], ["Captain Carocc#iz_a"])

    def test_controller_is_exact(self):
        self.assertEqual(pilot.controller(),
                         b'-\tscript\tT05CaroccZHInit\t-1,{\n\tend;\nOnInit:\n'
                         b'\tdisablenpc "Captain Carocc#iz";\n\tend;\n}\n')

    def test_wrong_hash_and_size_refused(self):
        altered = SYNTHETIC.replace(b"Fine.", b"Fino.")
        with self.assertRaisesRegex(pilot.PilotError, "SHA-256"):
            self.generate(altered)
        with self.assertRaisesRegex(pilot.PilotError, "bytes, expected"):
            self.generate(SYNTHETIC + b"\n")

    def test_missing_and_ambiguous_anchors(self):
        with self.assertRaisesRegex(pilot.PilotError, "missing"):
            self.generate(translations=((7, "mes", "Okay.", "好。"),))
        ambiguous = SYNTHETIC.replace(b'"Bye."', b'"Hello?"')
        with self.assertRaisesRegex(pilot.PilotError, "ambiguous"):
            self.generate(ambiguous, source=source_for(ambiguous))
        with self.assertRaisesRegex(pilot.PilotError, "lone mes"):
            self.generate(translations=((5, "mes", "Bye.", "再見。"),))
        with self.assertRaisesRegex(pilot.PilotError, "outside the block"):
            self.generate(translations=((13, "mes", "x", "好"),))

    def test_block_boundaries_and_names(self):
        moved = pilot.Source(self.source.sha256, self.source.size, 3, 11,
                             self.source.block_sha256, self.source.header, (13,))
        with self.assertRaisesRegex(pilot.PilotError, "boundaries"):
            self.generate(source=moved)
        no_dup = pilot.Source(self.source.sha256, self.source.size, 2, 11,
                              self.source.block_sha256, self.source.header, (12,))
        with self.assertRaisesRegex(pilot.PilotError, "excluded duplicate"):
            self.generate(source=no_dup)
        taken = SYNTHETIC + b"// Captain Carocc#t05zh\n"
        with self.assertRaisesRegex(pilot.PilotError, "not be unique"):
            self.generate(taken, source=source_for(taken))
        twice = SYNTHETIC + b"izlude,1,1,3\tscript\tCaptain Carocc#iz\t4_M_REINDEER,{\n}\n"
        with self.assertRaisesRegex(pilot.PilotError, "not unique"):
            self.generate(twice, source=source_for(twice))

    def test_literal_escaping_rules(self):
        self.assertEqual(pilot.script_literal("讓我上船吧！", "select"), "讓我上船吧！".encode("utf-8"))
        for bad in ('他說"好"', "好\\n", "^ff0000好", "好\n", "好\t", "", "   ", "Hello", "好 "):
            with self.assertRaises(pilot.PilotError, msg=repr(bad)):
                pilot.script_literal(bad, "mes")
        pilot.script_literal("注意:好", "mes")
        with self.assertRaisesRegex(pilot.PilotError, "':'"):
            pilot.script_literal("注意:好", "select")

    def test_pinned_translations_are_valid_and_nine(self):
        self.assertEqual(len(pilot.TRANSLATIONS), 9)
        self.assertEqual(pilot.TRANSLATIONS[:8], ORIGINAL_EIGHT)
        kinds = [k for _, k, _, _ in pilot.TRANSLATIONS]
        self.assertEqual((kinds.count("mes"), kinds.count("select")), (6, 3))
        for _, kind, english, chinese in pilot.TRANSLATIONS:
            pilot.script_literal(chinese, kind)
            for name in ("Izlude", "Carocc"):
                self.assertEqual(name in english, name in chinese)

    def test_ninth_translation_keeps_navi_markup(self):
        line, kind, english, chinese = pilot.TRANSLATIONS[8]
        self.assertEqual((line, kind), (693, "mes"))
        self.assertEqual((english.encode(), pilot.script_literal(chinese, kind)),
                         (LINE_693_EN, LINE_693_ZH))
        # The link payload occurs exactly once in both, and nothing else is markup.
        for text in (english.encode(), chinese.encode()):
            self.assertEqual(text.count(NAVI), 1)
            rest = text.replace(NAVI, b"")
            self.assertFalse(any(c in rest for c in b"<>[]^"), rest)

    def test_navi_literal_on_synthetic_mes_line(self):
        data = SYNTHETIC.replace(b'"Fine.";', b'"Go to ' + NAVI + b' now.";')
        script, meta = self.generate(data, ((7, "mes", "Go to " + NAVI.decode() + " now.",
                                             "去 " + NAVI.decode() + " 吧。"),), source_for(data))
        block, _ = block_of(script)
        self.assertEqual(block[5], b'\t\tmes "' + "去 ".encode() + NAVI + " 吧。".encode() + b'";\n')
        self.assertEqual(meta["translations"][0]["line"], 7)


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        os.chmod(self.tmp, 0o700)
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.script, self.meta = pilot.generate(SYNTHETIC, source_for(SYNTHETIC), SYN_TRANSLATIONS)

    def staging_left(self):
        return [p for p in self.tmp.iterdir() if p.name.startswith(".staging-")]

    def test_layout_manifest_and_mod_json(self):
        out = self.tmp / "out"
        meta = pilot.write_output(out, self.script, self.meta)
        mod = out / pilot.MOD_NAME
        self.assertEqual(sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()),
                         ["generation-manifest.json", "tw-carocc-pilot/mod.json",
                          "tw-carocc-pilot/npc/carocc_zh_pilot.txt"])
        self.assertEqual((mod / pilot.SCRIPT_PATH).read_bytes(), self.script)
        manifest = json.loads((out / "generation-manifest.json").read_text("utf-8"))
        self.assertEqual(manifest["output"][pilot.SCRIPT_PATH]["sha256"],
                         hashlib.sha256(self.script).hexdigest())
        mod_json = json.loads((mod / "mod.json").read_text("utf-8"))
        self.assertEqual(mod_json["requires"], {"app": ">=1.6.3", "era": "renewal"})
        self.assertEqual(mod_json["name"], pilot.MOD_NAME)
        self.assertEqual(meta["output"]["mod.json"]["sha256"],
                         hashlib.sha256((mod / "mod.json").read_bytes()).hexdigest())
        self.assertEqual(self.staging_left(), [])

    def test_existing_destinations_refused_unchanged(self):
        file_ = self.tmp / "file"
        file_.write_bytes(b"keep")
        empty = self.tmp / "empty"
        empty.mkdir()
        dangling = self.tmp / "dangling"
        dangling.symlink_to(self.tmp / "nowhere")
        live = self.tmp / "live"
        live.symlink_to(empty)
        for dest in (file_, empty, dangling, live):
            with self.assertRaisesRegex(pilot.PilotError, "already exists"):
                pilot.write_output(dest, self.script, self.meta)
        self.assertEqual(file_.read_bytes(), b"keep")
        self.assertEqual(list(empty.iterdir()), [])
        self.assertFalse((self.tmp / "nowhere").exists())
        self.assertEqual(os.readlink(dangling), str(self.tmp / "nowhere"))
        self.assertEqual(self.staging_left(), [])

    def test_destination_appearing_after_check_is_refused_and_staging_cleaned(self):
        out = self.tmp / "out"
        real_copytree = shutil.copytree

        def racing(src, dst, **kw):
            Path(dst).symlink_to(self.tmp / "elsewhere")
            return real_copytree(src, dst, **kw)

        with mock.patch.object(pilot.shutil, "copytree", racing):
            with self.assertRaisesRegex(pilot.PilotError, "could not publish"):
                pilot.write_output(out, self.script, self.meta)
        self.assertTrue(out.is_symlink())
        self.assertFalse((self.tmp / "elsewhere").exists())
        self.assertEqual(self.staging_left(), [])

    def test_untrusted_or_missing_parent_refused(self):
        with self.assertRaisesRegex(pilot.PilotError, "does not exist"):
            pilot.write_output(self.tmp / "no" / "out", self.script, self.meta)
        real = self.tmp / "real"
        real.mkdir(mode=0o700)
        (self.tmp / "link").symlink_to(real)
        with self.assertRaisesRegex(pilot.PilotError, "not a real directory"):
            pilot.write_output(self.tmp / "link" / "out", self.script, self.meta)
        open_dir = self.tmp / "open"
        open_dir.mkdir()
        os.chmod(open_dir, 0o777)
        with self.assertRaisesRegex(pilot.PilotError, "group/world-writable"):
            pilot.write_output(open_dir / "out", self.script, self.meta)
        self.assertEqual(list(real.iterdir()) + list(open_dir.iterdir()), [])

    def test_cli_wrong_input_writes_nothing(self):
        bad = self.tmp / "academy.txt"
        bad.write_bytes(b"x" * pilot.PINNED.size)
        out = self.tmp / "out"
        with mock.patch("sys.stderr"):
            self.assertEqual(pilot.main([str(bad), str(out)]), 2)
            bad.write_bytes(b"short")
            self.assertEqual(pilot.main([str(bad), str(out)]), 2)
        self.assertFalse(out.exists())
        self.assertEqual(self.staging_left(), [])


@unittest.skipUnless(ACADEMY, "CAROCC_ACADEMY not set: real pinned academy.txt tests skipped")
class PinnedInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = Path(ACADEMY).read_bytes()
        cls.script, cls.meta = pilot.generate(cls.data)

    def test_complete_block_comparison(self):
        src = pilot.split_lines(self.data)[387:798]
        block, rest = block_of(self.script)
        self.assertEqual(len(block), 411)
        changed = {388 + i: (a, b) for i, (a, b) in enumerate(zip(src, block)) if a != b}
        self.assertEqual(sorted(changed), [388, 569, 570, 572, 575, 576, 577, 693])
        self.assertEqual(changed[388][1],
                         b"izlude,198,213,3\tscript\tCaptain Carocc#t05zh\t4_M_REINDEER,5,5,{\n")
        expected = {
            569: '\t\t\t\t\tmes "你好？";\n',
            570: '\t\t\t\t\tmes "你是第一次來到 Izlude 嗎？";\n',
            572: '\t\t\t\t\tswitch(select("你好？", "讓我上船吧！", "我不知道該做什麼。")) {\n',
            575: '\t\t\t\t\t\tmes "你看起來既強壯又能幹！";\n',
            576: '\t\t\t\t\t\tmes "我就喜歡像你這樣能幹的人！";\n',
            577: '\t\t\t\t\t\tmes "希望你永遠都像現在這樣健康又強壯。";\n',
            693: '\t\t\t\t\tmes "我的朋友 <NAVI>[Hun]<INFO>izlude,122,207</INFO></NAVI> 就在學院入口附近。";\n',
        }
        for line, text in expected.items():
            self.assertEqual(changed[line][1], text.encode("utf-8"), line)
        # Own OnInit/OnTouch, case 2/3 and the 7473 guard: unchanged, tail and all.
        tail = b"".join(block[block.index(b"OnInit:\n"):])
        self.assertEqual(tail, b"".join(src[src.index(b"OnInit:\n"):]))
        self.assertIn(b'"Class == Job_Novice && BaseLevel <= 14 && !isbegin_quest(7472) && !isbegin_quest(7473)"', tail)
        self.assertEqual(block[199:250], src[199:250])
        self.assertTrue(all(byte < 0x80 for line in block for byte in line
                            if line not in (changed[n][1] for n in expected)))
        self.assertEqual(b"".join(rest), b"\n" + pilot.controller())
        self.assertNotIn(b"duplicate(", self.script)
        self.assertEqual(self.script.count(b"\tscript\t"), 2)

    def test_line_693_navi_sentence(self):
        src = pilot.split_lines(self.data)
        block, _ = block_of(self.script)
        self.assertEqual(src[692], b'\t\t\t\t\tmes "' + LINE_693_EN + b'";\n')
        self.assertEqual(block[693 - 388], b'\t\t\t\t\tmes "' + LINE_693_ZH + b'";\n')
        # The link payload, its map/coordinates and the matching viewpoint are unchanged.
        raw = b"".join(src[387:798])
        for token in (NAVI, b"<NAVI>", b"</NAVI>", b"<INFO>", b"<ITEM>", b"^"):
            self.assertEqual(b"".join(block).count(token), raw.count(token), token)
        self.assertEqual(block[695 - 388], src[694])
        self.assertIn(b"viewpoint 1,122,207,1,0x4d4dff;", block[695 - 388])

    def test_active_7472_branch_only_693_changes(self):
        src = pilot.split_lines(self.data)[672:699]
        block, _ = block_of(self.script)
        out = block[673 - 388:699 - 388 + 1]
        self.assertEqual(src[0], b"\t\t\t\t} else if (isbegin_quest(7472) == 1) {\n")
        self.assertEqual(out[-1], b"\t\t\t\t\tclose;\n")
        self.assertEqual([673 + i for i, (a, b) in enumerate(zip(src, out)) if a != b], [693])
        branch = b"".join(out)
        self.assertEqual((branch.count(b"next;"), branch.count(b"close;"), branch.count(b"viewpoint")),
                         (5, 1, 1))
        for token in (b"getitem", b"getexp", b"setquest", b"completequest", b"Zeny", b"warp", b"erasequest"):
            self.assertNotIn(token, branch)
        for kept in (b'"[Carocc]"', b'"[Lumin]"', b'"........."', b'cutin "nov_lumin01.bmp", 0;', b'cutin "", 255;'):
            self.assertIn(kept, branch)

    def test_mask_restores_complete_stock_block(self):
        src = pilot.split_lines(self.data)[387:798]
        block, _ = block_of(self.script)
        restored = list(block)
        restored[0] = restored[0].replace(b"\tCaptain Carocc#t05zh\t", b"\tCaptain Carocc#iz\t")
        for line, _, english, chinese in pilot.TRANSLATIONS:
            quoted = b'"' + chinese.encode() + b'"'
            self.assertEqual(restored[line - 388].count(quoted), 1, line)
            restored[line - 388] = restored[line - 388].replace(quoted, b'"' + english.encode() + b'"')
        self.assertEqual(len(restored), 411)
        self.assertEqual(restored, src)
        self.assertEqual(hashlib.sha256(b"".join(restored)).hexdigest(), pilot.PINNED.block_sha256)
        # The original eight Chinese literals are byte-identical to 0.1.0.
        for line, _, _, chinese in ORIGINAL_EIGHT:
            self.assertIn(b'"' + chinese.encode() + b'"', block[line - 388])

    def test_manifest_and_determinism(self):
        self.assertEqual(self.meta["input"]["sha256"], pilot.PINNED.sha256)
        self.assertEqual(self.meta["excluded_duplicates"]["names"],
                         [f"Captain Carocc#iz_{c}" for c in "abcd"])
        self.assertEqual(len(self.meta["translations"]), 9)
        self.assertEqual(self.meta["translations"][8],
                         {"line": 693, "kind": "mes", "en": LINE_693_EN.decode(),
                          "zh_hant": LINE_693_ZH.decode()})
        self.assertEqual(self.meta["generator_version"], "0.2.0")
        profile = json.loads(PROFILE.read_text("utf-8"))
        self.assertEqual(self.meta["limits"], [profile["limits_first"]] + profile["limits_remaining"])
        again, meta = pilot.generate(self.data)
        self.assertEqual((again, meta), (self.script, self.meta))

    def test_cli_publishes_and_leaves_input_unchanged(self):
        before = hashlib.sha256(Path(ACADEMY).read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            os.chmod(tmp, 0o700)
            out = Path(tmp) / "out"
            with mock.patch("sys.stdout"):
                self.assertEqual(pilot.main([ACADEMY, str(out)]), 0)
                with mock.patch("sys.stderr"):
                    self.assertEqual(pilot.main([ACADEMY, str(out)]), 2)
            self.assertEqual((out / pilot.MOD_NAME / pilot.SCRIPT_PATH).read_bytes(), self.script)
            files = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
            expected = json.loads(PROFILE.read_text("utf-8"))["expected_outputs"]
            self.assertEqual(files, sorted(expected))
            for name, pin in expected.items():
                data = (out / name).read_bytes()
                self.assertEqual({"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}, pin, name)
        self.assertEqual(hashlib.sha256(Path(ACADEMY).read_bytes()).hexdigest(), before)
        self.assertEqual(before, pilot.PINNED.sha256)


if __name__ == "__main__":
    unittest.main()
