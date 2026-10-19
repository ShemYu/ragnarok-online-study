"""Tests for quest_ui_zh_tw (T05.011).

    T05_011_BUNDLE=<frozen Chinese-navigation Online.js> \
        python3 -I -B tools/renewal/test_quest_ui_zh_tw.py -v

Without T05_011_BUNDLE (or when it does not exist) every actual-input test is
reported as skipped ("missing-input"), never passed. A bundle that exists but
does not match the input pin fails. T05_011_BUNDLE is only read.

The checked-in frozen profile (docs/project/fixtures/T05.011-profile.json) is
read here, never by the module, as independent external acceptance data; the
term table, interpolation lists and CSS below are authored from the frozen
task text and profile, not copied from the module. Bundle bytes stay in
memory; nothing is written and no JavaScript is parsed or executed.
"""

import ast
import hashlib
from html.parser import HTMLParser
import inspect
import json
import os
from pathlib import Path
import re
import sys
import unittest

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))
import quest_ui_zh_tw as quest  # noqa: E402

MODULE = HERE / "quest_ui_zh_tw.py"
PROFILE_PATH = REPO / "docs/project/fixtures/T05.011-profile.json"
BUNDLE = os.environ.get("T05_011_BUNDLE")

# Authored from docs/project/tasks/T05.011.md.
PROFILE_BYTES = 33878
PROFILE_SHA = "e4ceded134b743ba062ae7e383f42e71ec1e60359c0b64d728e4e5e3a73b5b71"
IN_BYTES = 13173065
IN_SHA = "67525a4ec4b834ec02c5ff33b4ca55c119f1380fa131ea329aab880359144478"
OUT_BYTES = 13174160
OUT_SHA = "9c148d9e43384a2498f9074efd1603b4eda1ff36dac53998985cfdf5eaf6fadf"

# Site id -> (English runtime text, Traditional Chinese runtime text).
LABELS = {
    "H01": ("Quest Information", "任務資訊"),
    "H02": ("Quest Information", "任務資訊"),
    "H03": ("Show Quest", "顯示任務"),
    "H04": ("Description", "任務說明"),
    "H05": ("Monster", "目標魔物"),
    "H06": ("Reward", "任務獎勵"),
    "H07": ("EXP", "基本經驗值"),
    "H08": ("JEXP", "職業經驗值"),
    "H09": ("Item", "物品"),
}
ROW_CAPTIONS = {"icon": ("Quest", "任務"), "toggle": ("Toggle", "切換")}
TAB_CAPTIONS = (("active", "進行中"), ("feature", "推薦"),
                ("inactive", "暫停中"), ("cooldown", "冷卻中"))
MISSION_INTERPOLATIONS = [
    "${DB.getQuestInfo(questID).Title}",
    "${mob_name}",
    "${_questList[questID].hunt_list[huntID].huntCount}",
    "${_questList[questID].hunt_list[huntID].maxCount}",
]
TEMPLATES = {
    "T01-mission": "`任務 [${DB.getQuestInfo(questID).Title}]：已擊倒 [${mob_name}]。"
                   "(${_questList[questID].hunt_list[huntID].huntCount}/"
                   "${_questList[questID].hunt_list[huntID].maxCount})`",
    "T02-completed": "`${mob_name} [已完成]`",
    "T03-deadline": "`截止時間 [${d.toLocaleString()}]`",
}
CLOSE_BUTTONS = (
    '<ui-button class="close-quest-container-btn" bg="basic_interface/btn_close.bmp"></ui-button>',
    '<ui-button class="quest-info-bottom-btn" bg="basic_interface/btn_close.bmp"></ui-button>',
)
INTERP = re.compile(rb"\$\{[^}]*\}")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_profile():
    raw = PROFILE_PATH.read_bytes()
    if len(raw) != PROFILE_BYTES or sha(raw) != PROFILE_SHA:
        raise AssertionError("frozen profile does not match its task pin")
    return json.loads(raw.decode("utf-8"), strict=False)


def decode_token(token):
    """Decode one JSON string token after rejecting raw controls except TAB."""
    if any(b < 0x20 and b != 0x09 for b in token):
        raise AssertionError("raw control byte other than TAB in string token")
    return json.loads(token.decode("utf-8"), strict=False)


def mutate(data, pos):
    return data[:pos] + bytes([data[pos] ^ 0x01]) + data[pos + 1:]


class Tags(HTMLParser):
    """Records start tags with attributes and the text found inside each li."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.tags, self.li_text, self._li = [], [], None

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, attrs))
        if tag == "li":
            self._li = []

    def handle_endtag(self, tag):
        if tag == "li" and self._li is not None:
            self.li_text.append("".join(self._li))
            self._li = None

    def handle_data(self, data):
        if self._li is not None:
            self._li.append(data)


def parse(html):
    p = Tags()
    p.feed(html)
    p.close()
    return p


class SourceShapeTests(unittest.TestCase):
    """Checks that need no bundle."""

    def test_wrong_type_diagnostics_are_bounded(self):
        value = type("X" * 10000, (), {})()
        for fn in (quest.transform_bundle, quest.restore_bundle):
            with self.subTest(function=fn.__name__):
                with self.assertRaises(ValueError) as caught:
                    fn(value)
                self.assertLess(len(str(caught.exception)), 200)

    def test_pins_and_counts_match_task(self):
        self.assertEqual((quest.INPUT_BYTES, quest.INPUT_SHA256), (IN_BYTES, IN_SHA))
        self.assertEqual((quest.OUTPUT_BYTES, quest.OUTPUT_SHA256), (OUT_BYTES, OUT_SHA))
        self.assertEqual(quest.EDIT_COUNT, 23)
        self.assertEqual(len(quest._PLAN), 23)

    def test_module_is_pure_standard_library(self):
        tree = ast.parse(MODULE.read_text(encoding="utf-8"))
        imports = [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        self.assertEqual(imports, ["hashlib"])
        self.assertFalse([n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)])
        banned = {"open", "exec", "eval", "compile", "__import__", "getattr", "globals",
                  "os", "sys", "subprocess", "socket", "pathlib", "json", "print", "input"}
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        self.assertFalse(names & banned, names & banned)
        public = sorted(k for k, v in vars(quest).items()
                        if callable(v) and not k.startswith("_") and inspect.isfunction(v))
        self.assertEqual(public, ["restore_bundle", "transform_bundle"])
        for fn in (quest.transform_bundle, quest.restore_bundle):
            self.assertEqual(list(inspect.signature(fn).parameters), [fn.__code__.co_varnames[0]])

    def test_plan_terms_and_order_match_task(self):
        by_id = {row[0]: row for row in quest._PLAN}
        for site, (en, zh) in LABELS.items():
            self.assertEqual(by_id[site][5:], (en.encode(), zh.encode()), site)
        for branch in ("cooldown", "active", "inactive"):
            for kind, (en, zh) in ROW_CAPTIONS.items():
                self.assertEqual(by_id["R-%s-%s" % (branch, kind)][5:],
                                 (en.encode(), zh.encode()))
        for tab, zh in TAB_CAPTIONS:
            row = by_id["I-" + tab]
            self.assertEqual(row[5], b"")
            self.assertEqual(row[6], ('<span class=\\"quest-menu-caption\\">%s</span>' % zh).encode())
        for site, new in TEMPLATES.items():
            self.assertEqual(by_id[site][6], new.encode())
        starts = [row[1] for row in quest._PLAN]
        self.assertEqual(starts, sorted(starts))

    def test_templates_conserve_interpolations(self):
        by_id = {row[0]: row for row in quest._PLAN}
        for site in TEMPLATES:
            old, new = by_id[site][5:]
            self.assertEqual(INTERP.findall(old), INTERP.findall(new), site)
        self.assertEqual([m.decode() for m in INTERP.findall(by_id["T01-mission"][6])],
                         MISSION_INTERPOLATIONS)
        self.assertNotIn(b"quest_info", by_id["T01-mission"][6])

    def test_plan_matches_frozen_profile(self):
        profile = load_profile()
        rows = [(e["id"], *e["input_span"], *e["output_span"],
                 e["old_source"].encode(), e["new_source"].encode())
                for e in sorted(profile["edits"], key=lambda e: e["order"])]
        self.assertEqual([tuple(r) for r in rows], list(quest._PLAN))
        css = next(e for e in profile["edits"] if e["id"] == "C01-caption-css")
        self.assertEqual(json.loads('"%s"' % css["new_source"]), css["decoded_appended_css"])

    def test_wrong_types_refused_both_ways(self):
        for fn in (quest.transform_bundle, quest.restore_bundle):
            for bad in (None, "", "x" * 10, bytearray(b"x"), memoryview(b"x"), 0, [b"x"],
                        type("Sub", (bytes,), {})(b"x")):
                with self.assertRaises(ValueError) as cm:
                    fn(bad)
                self.assertIn("expected bytes", str(cm.exception))

    def test_wrong_sizes_refused_both_ways(self):
        for fn in (quest.transform_bundle, quest.restore_bundle):
            for bad in (b"", b"\x00" * 100):
                with self.assertRaises(ValueError) as cm:
                    fn(bad)
                self.assertLess(len(str(cm.exception)), 200)

    def test_tiny_splicer_controls(self):
        data = b"aaXbbYcc"
        sites = [("s1", 2, 3, b"X", b"11"), ("ins", 5, 5, b"", b"+"), ("s2", 5, 6, b"Y", b"")]
        want = b"aa11bb+cc"
        out = quest._splice(data, sites, len(data), sha(data), len(want), sha(want), "t")
        self.assertEqual(out, want)
        inv = [("s1", 2, 4, b"11", b"X"), ("ins", 6, 7, b"+", b""), ("s2", 7, 7, b"", b"Y")]
        self.assertEqual(quest._splice(want, inv, len(want), sha(want), len(data), sha(data), "t"),
                         data)
        bad = b"aaZbbYcc"
        with self.assertRaisesRegex(ValueError, "site s1 does not hold"):
            quest._splice(bad, sites, len(bad), sha(bad), len(want), sha(want), "t")
        with self.assertRaisesRegex(ValueError, "out of order"):
            quest._splice(data, sites[::-1], len(data), sha(data), len(want), sha(want), "t")
        with self.assertRaisesRegex(ValueError, "result does not match"):
            quest._splice(data, sites, len(data), sha(data), len(want), sha(b"other"), "t")


@unittest.skipUnless(BUNDLE and Path(BUNDLE).is_file(), "missing-input: T05_011_BUNDLE")
class ActualInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = Path(BUNDLE).read_bytes()
        if len(cls.src) != IN_BYTES or sha(cls.src) != IN_SHA:
            raise AssertionError("T05_011_BUNDLE does not match the frozen input pin")
        cls.out = quest.transform_bundle(cls.src)
        cls.profile = load_profile()

    def test_forward_matches_golden_pin(self):
        self.assertEqual(len(self.out), OUT_BYTES)
        self.assertEqual(sha(self.out), OUT_SHA)

    def test_inverse_is_exact(self):
        back = quest.restore_bundle(self.out)
        self.assertEqual(back, self.src)
        self.assertEqual(sha(back), IN_SHA)

    def test_independent_profile_splice_equals_output(self):
        # Splice built here from profile data only, not from module constants.
        edits = sorted(self.profile["edits"], key=lambda e: e["order"])
        pieces, pos = [], 0
        for e in edits:
            a, b = e["input_span"]
            self.assertEqual(self.src[a:b], e["old_source"].encode(), e["id"])
            self.assertEqual(sha(e["old_source"].encode()), e["old_sha256"])
            self.assertEqual(sha(e["new_source"].encode()), e["new_sha256"])
            pieces += [self.src[pos:a], e["new_source"].encode()]
            pos = b
        pieces.append(self.src[pos:])
        self.assertEqual(b"".join(pieces), self.out)
        for e in edits:
            c, d = e["output_span"]
            self.assertEqual(self.out[c:d], e["new_source"].encode(), e["id"])

    def test_all_24_unchanged_pieces(self):
        pieces = self.profile["unchanged_complement"]
        self.assertEqual(len(pieces), 24)
        self.assertEqual(sum(p["bytes"] for p in pieces)
                         + sum(e["old_bytes"] for e in self.profile["edits"]), IN_BYTES)
        for p in pieces:
            a, b = p["input_span"]
            c, d = p["output_span"]
            self.assertEqual(sha(self.src[a:b]), p["sha256"])
            self.assertEqual(sha(self.out[c:d]), p["sha256"])

    def test_guard_only_sites_unchanged(self):
        guards = self.profile["guard_only"]
        self.assertEqual(len(guards), 6)
        for g in guards:
            a, b = g["span"]
            self.assertEqual(self.src[a:b], g["source"].encode())
            self.assertEqual(sha(g["source"].encode()), g["sha256"])
            self.assertEqual(self.out.count(g["source"].encode()),
                             self.src.count(g["source"].encode()))

    def test_scope_windows_and_compiled_interpolations(self):
        for site in TEMPLATES:
            e = next(e for e in self.profile["edits"] if e["id"] == site)
            a, b = e["input_span"]
            c, d = e["output_span"]
            self.assertEqual(INTERP.findall(self.src[a:b]), INTERP.findall(self.out[c:d]))
            self.assertEqual(self.out[c:d], TEMPLATES[site].encode())
        self.assertNotIn(b"quest_info", self.out[7935779:7956870])
        self.assertEqual(self.out.count(b"d.toLocaleString()"), self.src.count(b"d.toLocaleString()"))
        self.assertEqual(INTERP.findall(self.src), INTERP.findall(self.out))

    def tokens(self, data, delta):
        result = {}
        for name, t in self.profile["tokens"].items():
            a, b = t["span"]
            result[name] = decode_token(data[a + delta[name][0]:b + delta[name][1]])
        return result

    def test_decoded_html_and_css(self):
        old = self.tokens(self.src, {k: (0, 0) for k in self.profile["tokens"]})
        # Token spans shift by the earlier edits' growth.
        new = self.tokens(self.out, {"helper_html": (7, 7 + 32), "html": (39, 39 + 198),
                                     "css": (237, 237 + 858)})
        for name, t in self.profile["tokens"].items():
            self.assertEqual(sha(old[name].encode()), t["decoded_sha256"], name)
        css = next(e for e in self.profile["edits"] if e["id"] == "C01-caption-css")
        self.assertEqual(new["css"], old["css"] + css["decoded_appended_css"])
        self.assertIn("pointer-events:none", css["decoded_appended_css"])

        for name in ("html", "helper_html"):
            po, pn = parse(old[name]), parse(new[name])
            added = [t for t in pn.tags if t not in po.tags]
            base = [t for t in pn.tags if t[0] != "span" or ("class", "quest-menu-caption") not in t[1]]
            self.assertEqual(base, po.tags, name)
            if name == "helper_html":
                self.assertEqual(added, [])
        self.assertEqual(new["html"].count('class="quest-menu-caption"'), 4)
        for button in CLOSE_BUTTONS:
            self.assertEqual(sum(h.count(button) for h in old.values()), 1)
            self.assertEqual(sum(h.count(button) for h in new.values()), 1)

        tabs = parse(new["html"])
        li = [dict(a) for t, a in tabs.tags if t == "li"]
        self.assertEqual([(x["id"], x["class"]) for x in li],
                         [(tab, "quest-menu-item") for tab, _ in TAB_CAPTIONS])
        self.assertEqual(tabs.li_text, [zh for _, zh in TAB_CAPTIONS])
        self.assertEqual(parse(old["html"]).li_text, ["", "", "", ""])

        for site, (en, zh) in LABELS.items():
            token = "html" if site in ("H01", "H03") else "helper_html"
            self.assertIn(zh, new[token], site)
        for en in ("Quest Information", "Show Quest", ">Description<", ">Monster<", ">Reward<",
                   ">EXP<", ">JEXP<", ">Item<"):
            self.assertNotIn(en, new["html"] + new["helper_html"])

    def test_row_branches_hidden_fallbacks(self):
        for e in self.profile["edits"]:
            if e["kind"] != "hidden_row_caption":
                continue
            c, d = e["output_span"]
            kind = "icon" if e["id"].endswith("icon") else "toggle"
            prefix = ('<span class=\\"quest-item-%s-image-text\\">' % kind).encode()
            self.assertEqual(self.out[c - len(prefix):c], prefix)
            self.assertEqual(self.out[c:d + 7], ROW_CAPTIONS[kind][1].encode() + b"</span>")

    def test_refusals_on_actual_bytes(self):
        src, out = self.src, self.out
        site = quest._PLAN[9]  # H02, inside a fixed fragment
        cases = [
            (quest.transform_bundle, src[:-1], "expected %d bytes" % IN_BYTES),
            (quest.transform_bundle, src + b"\n", "expected %d bytes" % IN_BYTES),
            (quest.transform_bundle, mutate(src, site[1]), "SHA-256"),
            (quest.transform_bundle, mutate(src, 100), "SHA-256"),
            (quest.transform_bundle, out, "expected %d bytes" % IN_BYTES),
            (quest.restore_bundle, out[:-1], "expected %d bytes" % OUT_BYTES),
            (quest.restore_bundle, out + b"\n", "expected %d bytes" % OUT_BYTES),
            (quest.restore_bundle, mutate(out, site[3]), "SHA-256"),
            (quest.restore_bundle, mutate(out, 100), "SHA-256"),
            (quest.restore_bundle, src, "expected %d bytes" % OUT_BYTES),
        ]
        for fn, data, needle in cases:
            with self.assertRaises(ValueError) as cm:
                fn(data)
            self.assertIn(needle, str(cm.exception))
            self.assertLess(len(str(cm.exception)), 200)

    def test_fragment_checks_beyond_whole_pin(self):
        # With the whole pin re-aimed at mutated bytes, the ordered fragment
        # checks still refuse before any result is built.
        fwd = [(n, a, b, o, w) for n, a, b, _, _, o, w in quest._PLAN]
        inv = [(n, c, d, w, o) for n, _, _, c, d, o, w in quest._PLAN]
        for i in range(23):
            name, a, b, c, d, old, new = quest._PLAN[i]
            if old:
                bad = mutate(self.src, a)
                with self.assertRaisesRegex(ValueError, "site %s does not hold" % name):
                    quest._splice(bad, fwd, IN_BYTES, sha(bad), OUT_BYTES, OUT_SHA, "f")
            bad = mutate(self.out, c)
            with self.assertRaisesRegex(ValueError, "site %s does not hold" % name):
                quest._splice(bad, inv, OUT_BYTES, sha(bad), IN_BYTES, IN_SHA, "r")
        # Unchanged-piece mutation passes fragments but fails the result pin.
        bad = mutate(self.src, 100)
        with self.assertRaisesRegex(ValueError, "result pin"):
            quest._splice(bad, fwd, IN_BYTES, sha(bad), OUT_BYTES, OUT_SHA, "f")


if __name__ == "__main__":
    # Adopt the paired Grok candidate's explicit incomplete-run status.
    program = unittest.main(exit=False)
    result = program.result
    if result.failures or result.errors:
        sys.exit(1)
    if result.skipped:
        sys.stderr.write("NOT A FULL PASS: skipped %d (%s)\n" % (
            len(result.skipped), "; ".join(str(reason) for _, reason in result.skipped)))
        sys.exit(2)
    sys.exit(0)
