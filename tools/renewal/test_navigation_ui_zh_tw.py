"""Tests for navigation_ui_zh_tw (T05.009).

    T05_009_BUNDLE=<frozen repaired Online.js> \
        python3 -I -B tools/renewal/test_navigation_ui_zh_tw.py -v

Without T05_009_BUNDLE (or when it does not exist) every actual-input test is
reported as skipped ("missing-input"), never passed. A bundle that exists but
does not match the input pin fails. The checked-in frozen profile
(docs/project/fixtures/T05.009-profile.json) is read here, never by the module,
as independent external acceptance data; the term table and CSS rules below
are authored from the frozen task text, not copied from the module.

Bundle bytes stay in memory. Only the optional `node --check` syntax parse
writes them, as a 0600 file inside a 0700 directory under T05_009_WORK
(default: .tools/renewal/T05.009/test-work in this checkout), removed after
use. JavaScript is parsed, never executed; without node that check is skipped.
"""

import ast
import hashlib
from html.parser import HTMLParser
import inspect
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))
import navigation_ui_zh_tw as nav  # noqa: E402

MODULE = HERE / "navigation_ui_zh_tw.py"
PROFILE_PATH = REPO / "docs/project/fixtures/T05.009-profile.json"
BUNDLE = os.environ.get("T05_009_BUNDLE")
WORK = Path(os.environ.get("T05_009_WORK") or REPO / ".tools/renewal/T05.009/test-work")
NODE = shutil.which("node")

# Authored from docs/project/tasks/T05.009.md.
PROFILE_BYTES = 95517
PROFILE_SHA = "df4ba7abdd6a9af9499365b4e4392a6bf70e59bee77298fbfc29002dcbcc7fb9"
IN_BYTES = 13172839
IN_SHA = "6ba854cb67b1306cadb905b1b89a7a1eac98cd7e5c912196e6f87df41a5c4c2f"
OUT_BYTES = 13173065
OUT_SHA = "67525a4ec4b834ec02c5ff33b4ca55c119f1380fa131ea329aab880359144478"
LOADER = (10727952, 10737652, 10728206, 10737906,
          "ba4aa8301e73b177b2a4fe17097372090018f2d131e2bbb2cc98c28d9ff4e306")

ELEMENTS = "無 水 地 火 風 毒 聖 暗 念 不死".split()
RACES = "無形 不死 動物 植物 昆蟲 魚貝 惡魔 人形 天使 龍 玩家 首領".split()
SIZES = "小型 中型 大型".split()
ABUNDANCE = "極少 少 普通 多 極多".split()
HELP = "以座標或名稱導航。用法：/navi prontera 150/150 或 /navi 波利"

# Site id -> exact localized runtime text, from the frozen term tables.
TERMS = {
    "A01-title": "導航",
    "A02-caption-ALL": "全部", "A02-caption-NPC": "人物", "A02-caption-MOB": "魔物",
    "A03-prefix": "搜尋結果[",
    "A04-detail-initial": "請選擇結果",
    "A05-map": "地圖", "A05-coordinates": "座標", "A05-frequency": "出現量",
    "A06-share-tooltip": "此用戶端不支援分享",
    "A07-services": " 服務", "A08-move": "✣ 移動", "A09-minimize": " 縮小",
    "A10-mouse": "滑鼠：", "A10-target": "目標：",
    "A11-marker-tooltip": "路徑標記",
    "B14-no-path": " （找不到路徑）",
    "B01-short-query": "請選擇結果",
    "B05-mapwide": "全地圖出現",
    "B06-label-level": "等級", "B06-label-element": "屬性",
    "B06-label-race": "種族", "B06-label-size": "體型",
    "B07-stat-unknown-element": "未知", "B07-stat-unknown-race": "未知",
    "B07-stat-unknown-size": "未知", "B07-db-unknown-element": "未知",
    "B07-db-unknown-race": "未知", "B07-db-unknown-size": "未知",
    "B12-spawn-tooltip": " 筆出現資料",
    "B02-result-select": "請選擇結果", "B02-result-empty": "無結果",
    "B04-empty-advice": "請嘗試其他關鍵字。",
    "B03-no-results": "找不到結果",
    "B13-map-click": "地圖選點",
    "B15-navi-help": HELP,
}
TERMS.update(("B08-%d-" % i, v) for i, v in enumerate(ELEMENTS))
TERMS.update(("B09-%d-" % i, v) for i, v in enumerate(RACES))
TERMS.update(("B10-%d-" % i, v) for i, v in enumerate(SIZES))
TERMS.update(("B11-%d-" % i, v) for i, v in enumerate(ABUNDANCE))

NEW_CSS = (
    ".Navigation .search-actions ui-button { width:120px; height:20px; box-sizing:border-box;"
    " display:inline-flex; align-items:center; justify-content:center; border:1px solid #9c9c9c;"
    " border-radius:2px; background:linear-gradient(#fff,#e4e4e4); color:#333; line-height:18px;"
    " white-space:nowrap; user-select:none; cursor:pointer; }\n"
    ".Navigation .search-actions ui-button:not([disabled]):hover"
    " { background:linear-gradient(#fff,#e2efff); border-color:#7d9abb; }\n"
    ".Navigation .search-actions ui-button:not([disabled]):active"
    " { background:linear-gradient(#bfd5ef,#e1edfa); border-color:#627f9f; }\n"
    ".Navigation .search-actions ui-button[disabled] { opacity:.5; cursor:default; }")
OLD_CSS = ".Navigation .search-actions ui-button { width:120px; height:20px; }"
SHARE_OUT = '<ui-button class="share-result disabled" disabled title="此用戶端不支援分享">分享</ui-button>'
FIND_OUT = '<ui-button class="find-result disabled" disabled>尋路</ui-button>'
BITMAPS = [(name, attr) for name in ("share", "find") for attr in ("bg", "hover", "down")]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def term_for(edit_id):
    for key, value in TERMS.items():
        if edit_id == key or (key.endswith("-") and edit_id.startswith(key)):
            return value
    return None


def load_profile():
    raw = PROFILE_PATH.read_bytes()
    if len(raw) != PROFILE_BYTES or sha(raw) != PROFILE_SHA:
        raise AssertionError("frozen profile does not match its task pin")
    return json.loads(raw.decode("utf-8"))


def forward_sites():
    return [(n, a, b, old, new) for n, a, b, _, _, old, new in nav._PLAN]


def inverse_sites():
    return [(n, c, d, new, old) for n, _, _, c, d, old, new in nav._PLAN]


class Tags(HTMLParser):
    """Records the start-tag/attribute sequence and text of decoded HTML."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.tags, self.text = [], []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, attrs))

    def handle_data(self, data):
        if data.strip():
            self.text.append(data)


def parse_html(text):
    parser = Tags()
    parser.feed(text)
    parser.close()
    return parser


# ---------------------------------------------------------------------------
# S01: fixed API and purity (no bundle needed).

class ModuleContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = MODULE.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_public_api_is_exactly_two_typed_functions(self):
        public = sorted(n for n, v in vars(nav).items()
                        if callable(v) and not n.startswith("_") and inspect.isfunction(v))
        self.assertEqual(public, ["restore_bundle", "transform_bundle"])
        for fn, arg in ((nav.transform_bundle, "source"), (nav.restore_bundle, "localized")):
            sig = inspect.signature(fn)
            self.assertEqual(list(sig.parameters), [arg])
            self.assertIs(sig.parameters[arg].annotation, bytes)
            self.assertIs(sig.return_annotation, bytes)

    def test_only_hashlib_is_imported(self):
        imported = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module)
        self.assertEqual(imported, {"hashlib"})
        self.assertNotIn("navigation_client_repair", self.source)

    def test_no_io_env_process_or_dynamic_code(self):
        banned = {"open", "eval", "exec", "compile", "__import__", "input", "print",
                  "os", "sys", "subprocess", "socket", "pathlib", "importlib", "environ",
                  "getattr", "globals", "locals"}
        names = {n.id for n in ast.walk(self.tree) if isinstance(n, ast.Name)}
        attrs = {n.attr for n in ast.walk(self.tree) if isinstance(n, ast.Attribute)}
        self.assertFalse((names | attrs) & banned, (names | attrs) & banned)
        self.assertLessEqual(attrs, {"sha256", "hexdigest", "encode", "startswith", "join", "append",
                                     "__name__"})

    def test_top_level_only_defines_constants_and_checks_them(self):
        allowed = (ast.Expr, ast.Import, ast.Assign, ast.FunctionDef, ast.If, ast.Delete)
        for node in self.tree.body:
            self.assertIsInstance(node, allowed, ast.dump(node)[:80])
            if isinstance(node, ast.Expr) and not isinstance(node.value, ast.Constant):
                self.assertEqual(ast.unparse(node), "_check_constants(_PLAN, INPUT_BYTES, OUTPUT_BYTES)")

    def test_module_is_finite_and_embeds_no_bundle(self):
        self.assertLess(MODULE.stat().st_size, 32768)
        self.assertNotIn("_EDITS", vars(nav))

    def test_pins_match_the_frozen_task(self):
        self.assertEqual((nav.INPUT_BYTES, nav.INPUT_SHA256), (IN_BYTES, IN_SHA))
        self.assertEqual((nav.OUTPUT_BYTES, nav.OUTPUT_SHA256), (OUT_BYTES, OUT_SHA))
        self.assertEqual(nav.EDIT_COUNT, 75)
        self.assertEqual(len(nav._PLAN), 75)


# ---------------------------------------------------------------------------
# S02/S03 constant review against the frozen profile and authored terms.

class ProfileAgreementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = load_profile()

    def test_profile_counts(self):
        p = self.profile
        self.assertEqual(p["task"], "T05.009")
        self.assertEqual(p["input"], {**p["input"], "bytes": IN_BYTES, "sha256": IN_SHA})
        self.assertEqual((p["derived_output"]["bytes"], p["derived_output"]["sha256"]),
                         (OUT_BYTES, OUT_SHA))
        kinds = [e["kind"] for e in p["edits"]]
        self.assertEqual({k: kinds.count(k) for k in set(kinds)},
                         {"text": 66, "remove_bitmap_attribute": 6, "insert_text_child": 2,
                          "replace_scoped_css_rule": 1})
        self.assertEqual((len(p["contexts"]), len(p["unchanged_complement"]),
                          len(p["modules_and_windows"]), len(p["guard_only_sites"]),
                          len(p["literal_tokens"])), (39, 72, 7, 5, 2))

    def test_module_rows_equal_profile_edits_in_order(self):
        edits = sorted(self.profile["edits"], key=lambda e: e["order"])
        self.assertEqual([e["order"] for e in edits], list(range(75)))
        for row, e in zip(nav._PLAN, edits):
            name, a, b, c, d, old, new = row
            self.assertEqual(name, e["id"])
            self.assertEqual([a, b], e["input_span"], name)
            self.assertEqual([c, d], e["derived_output_span"], name)
            self.assertEqual((old, sha(old), len(old)),
                             (e["old_source"].encode(), e["old_sha256"], e["old_bytes"]), name)
            self.assertEqual((new, sha(new), len(new)),
                             (e["new_source"].encode(), e["new_sha256"], e["new_bytes"]), name)

    def test_authored_terms_cover_all_66_text_sites(self):
        text = [r for r, e in zip(nav._PLAN, self.profile["edits"]) if e["kind"] == "text"]
        self.assertEqual(len(text), 66)
        for name, _, _, _, _, _, new in text:
            self.assertEqual(new.decode("utf-8"), term_for(name), name)
        unknown = [r for r in text if r[6] == "未知".encode()]
        select = [r for r in text if r[6] == "請選擇結果".encode()]
        self.assertEqual((len(unknown), len(select)), (6, 3))

    def test_structural_rows(self):
        rows = {r[0]: r for r in nav._PLAN}
        for name, attr in BITMAPS:
            r = rows["A12-%s-remove-%s" % (name, attr)]
            self.assertEqual(r[5], (' %s=\\"navigation_interface3/btn_%s_%s.bmp\\"' % (
                attr, name, {"bg": "normal", "hover": "over", "down": "press"}[attr])).encode())
            self.assertEqual(r[6], b"")
            self.assertEqual(r[3], r[4])
        self.assertEqual([rows["A12-share-remove-%s" % a][3] for a in ("bg", "hover", "down")],
                         [7025090] * 3)
        self.assertEqual([rows["A12-find-remove-%s" % a][3] for a in ("bg", "hover", "down")],
                         [7025205] * 3)
        share, find = rows["A12-share-insert-child"], rows["A12-find-insert-child"]
        self.assertEqual((share[1], share[2], share[5], share[6].decode()), (7025280, 7025280, b"", "分享"))
        self.assertEqual((find[1], find[2], find[5], find[6].decode()), (7025500, 7025500, b"", "尋路"))
        css = rows["A12-action-button-css"]
        self.assertEqual((css[1], css[2]), (7033941, 7034008))
        self.assertEqual(css[5].decode(), OLD_CSS)
        self.assertEqual(json.loads('"%s"' % css[6].decode()), NEW_CSS)
        self.assertNotIn(b"\n", css[6])

    def test_constant_check_rejects_inconsistent_tables(self):
        good = nav._PLAN
        nav._check_constants(good, nav.INPUT_BYTES, nav.OUTPUT_BYTES)
        bad_len = good[:1] + ((good[1][0], good[1][1], good[1][2] + 1) + good[1][3:],) + good[2:]
        swapped = (good[1], good[0]) + good[2:]
        for plan, size in ((bad_len, nav.INPUT_BYTES), (swapped, nav.INPUT_BYTES),
                           (good, nav.INPUT_BYTES + 1), (good + (good[-1],), nav.INPUT_BYTES)):
            with self.assertRaises(RuntimeError):
                nav._check_constants(plan, size, nav.OUTPUT_BYTES)


# ---------------------------------------------------------------------------
# Authored tiny fixtures for the private splicer (cannot replace S02).

class AuthoredSpliceTests(unittest.TestCase):
    SRC = b'<b class="x" bg="a.bmp" hover="b.bmp" down="c.bmp" t="Hi"></b>|Lv.'
    OUT = b'<b class="x" t="\xe5\x97\xa8">\xe5\x88\x86</b>|\xe7\xad\x89'

    def forward(self):
        s = self.SRC
        return [("bg", 12, 23, b' bg="a.bmp"', b""),
                ("hover", 23, 37, b' hover="b.bmp"', b""),
                ("down", 37, 50, b' down="c.bmp"', b""),
                ("t", 54, 56, b"Hi", "嗨".encode()),
                ("child", 58, 58, b"", "分".encode()),
                ("lv", s.index(b"Lv."), len(s), b"Lv.", "等".encode())]

    def inverse(self):
        return [("bg", 12, 12, b"", b' bg="a.bmp"'),
                ("hover", 12, 12, b"", b' hover="b.bmp"'),
                ("down", 12, 12, b"", b' down="c.bmp"'),
                ("t", 16, 19, "嗨".encode(), b"Hi"),
                ("child", 21, 24, "分".encode(), b""),
                ("lv", 29, 32, "等".encode(), b"Lv.")]

    def run_fwd(self, data, sites=None):
        return nav._splice(data, sites or self.forward(), len(self.SRC), sha(self.SRC),
                           len(self.OUT), sha(self.OUT), "fwd")

    def run_inv(self, data, sites=None):
        return nav._splice(data, sites or self.inverse(), len(self.OUT), sha(self.OUT),
                           len(self.SRC), sha(self.SRC), "inv")

    def test_forward_and_exact_inverse(self):
        self.assertEqual(self.run_fwd(self.SRC), self.OUT)
        self.assertEqual(self.run_inv(self.OUT), self.SRC)

    def test_co_located_insertions_keep_listed_order(self):
        inv = self.inverse()
        reordered = [inv[2], inv[0], inv[1]] + inv[3:]
        # Same semantic attributes, different bytes: the result pin refuses it.
        with self.assertRaisesRegex(ValueError, "result"):
            self.run_inv(self.OUT, reordered)

    def test_refuses_fragment_order_and_bounds(self):
        fwd = self.forward()
        cases = {
            "fragment": fwd[:3] + [("t", 54, 56, b"Ho", b"X")] + fwd[4:],
            "overlap": fwd[:1] + [("hover", 22, 36, b'" hover="b.bmp', b"")] + fwd[2:],
            "order": [fwd[1], fwd[0]] + fwd[2:],
            "bounds": fwd[:-1] + [("lv", len(self.SRC) - 2, len(self.SRC) + 1, b"v.!", b"")],
            "length": fwd[:3] + [("t", 54, 57, b"Hi", b"X")] + fwd[4:],
        }
        for label, sites in cases.items():
            with self.subTest(label), self.assertRaises(ValueError):
                self.run_fwd(self.SRC, sites)

    def test_refuses_types_and_pins(self):
        class Sub(bytes):
            pass
        for bad in (self.SRC.decode(), bytearray(self.SRC), memoryview(self.SRC), Sub(self.SRC),
                    None, b"", self.SRC[:-1], self.SRC + b"!", self.OUT):
            with self.subTest(type(bad).__name__), self.assertRaises(ValueError):
                self.run_fwd(bad)

    def test_public_api_refuses_without_bundle(self):
        for fn in (nav.transform_bundle, nav.restore_bundle):
            for bad in ("", b"", bytearray(b"x"), b"x" * 100, None, 0):
                with self.subTest(fn.__name__, bad=type(bad).__name__), self.assertRaises(ValueError):
                    fn(bad)


# ---------------------------------------------------------------------------
# S02-S05 on the actual frozen production input.

def mapped(edits, point, side):
    """Map an original offset outside every edit to the localized offset."""
    shift = 0
    for e in edits:
        a, b = e["input_span"]
        if b <= point:
            shift += e["new_bytes"] - e["old_bytes"]
        elif a < point:
            raise AssertionError("point %d inside edit %s" % (point, e["id"]))
    return point + shift if side == "out" else point


class ActualInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not BUNDLE or not Path(BUNDLE).is_file():
            raise unittest.SkipTest("missing-input: set T05_009_BUNDLE to the frozen Online.js")
        cls.profile = load_profile()
        cls.edits = sorted(cls.profile["edits"], key=lambda e: e["order"])
        cls.src = Path(BUNDLE).read_bytes()
        if len(cls.src) != IN_BYTES or sha(cls.src) != IN_SHA:
            raise AssertionError("T05_009_BUNDLE does not match the frozen input pin")
        cls.out = nav.transform_bundle(cls.src)
        cls.back = nav.restore_bundle(cls.out)

    def span_out(self, span):
        return mapped(self.edits, span[0], "out"), mapped(self.edits, span[1], "out")

    # S01/S02 whole result
    def test_forward_matches_required_localized_pin(self):
        self.assertEqual((len(self.out), sha(self.out)), (OUT_BYTES, OUT_SHA))
        self.assertIs(type(self.out), bytes)

    def test_deterministic(self):
        self.assertEqual(nav.transform_bundle(self.src), self.out)
        self.assertEqual(nav.restore_bundle(self.out), self.back)

    def test_inverse_is_exact(self):
        self.assertEqual(self.back, self.src)
        self.assertEqual(sha(self.back), IN_SHA)

    # S02 every edit at both spans, plus authored terms
    def test_all_75_edits_at_both_spans(self):
        for e in self.edits:
            a, b = e["input_span"]
            c, d = e["derived_output_span"]
            self.assertEqual(self.src[a:b], e["old_source"].encode(), e["id"])
            self.assertEqual(sha(self.out[c:d]), e["new_sha256"], e["id"])
            if e["kind"] == "text":
                self.assertEqual(self.out[c:d].decode("utf-8"), term_for(e["id"]), e["id"])
                self.assertEqual(self.out[c:d].decode(), e["new_runtime_text"], e["id"])

    # S03 complement, loader and coverage
    def test_72_complement_pieces_unchanged(self):
        pieces = self.profile["unchanged_complement"]
        total = 0
        for p in pieces:
            a, b = p["input_span"]
            c, d = p["derived_output_span"]
            self.assertEqual(sha(self.src[a:b]), p["sha256"])
            self.assertEqual(self.out[c:d], self.src[a:b])
            total += b - a
        self.assertEqual(total, 13171805)
        for side, size, key in (("in", IN_BYTES, "input_span"), ("out", OUT_BYTES, "derived_output_span")):
            spans = sorted([tuple(p[key]) for p in pieces] + [tuple(e[key]) for e in self.edits])
            pos = 0
            for a, b in spans:
                self.assertEqual(a, pos, side)
                pos = b
            self.assertEqual(pos, size, side)
        self.assertEqual(sum(e["old_bytes"] for e in self.edits), 1034)
        self.assertEqual(sum(e["new_bytes"] for e in self.edits), 1260)

    def test_protected_loader_untouched(self):
        a, b, c, d, digest = LOADER
        self.assertEqual(sha(self.src[a:b]), digest)
        self.assertEqual(self.out[c:d], self.src[a:b])
        self.assertEqual(self.span_out([a, b]), (c, d))

    # 39 contexts / 7 windows / 5 guards / 2 tokens
    def test_39_contexts_in_their_windows(self):
        windows = self.profile["modules_and_windows"]
        for name, ctx in self.profile["contexts"].items():
            text = ctx["compiled_text"].encode()
            a, b = ctx["span"]
            self.assertEqual((self.src[a:b], sha(text), len(text)), (text, ctx["sha256"], ctx["bytes"]), name)
            ws, we = windows[ctx["window"]]["span"]
            self.assertTrue(ws <= a and b <= we, name)
            self.assertEqual(self.src[ws:we].count(text), ctx["expected_matches_in_window"], name)

    def test_7_windows_and_guards_in_both_bundles(self):
        for name, w in self.profile["modules_and_windows"].items():
            for data, (a, b) in ((self.src, w["span"]), (self.out, self.span_out(w["span"]))):
                seg = data[a:b]
                self.assertTrue(seg.startswith(w["start_guard"].encode()), name)
                if "end_guard" in w:
                    self.assertTrue(seg.endswith(w["end_guard"].encode()), name)
                else:
                    self.assertTrue(data[b:].startswith(w["following_guard"].encode()), name)
            self.assertEqual(sha(self.src.__getitem__(slice(*w["span"]))), w["sha256"], name)

    def test_5_guard_only_sites_unchanged(self):
        for g in self.profile["guard_only_sites"]:
            a, b = g["span"]
            c, d = self.span_out(g["span"])
            self.assertEqual(self.src[a:b], g["compiled_text"].encode(), g["id"])
            self.assertEqual(self.out[c:d], self.src[a:b], g["id"])
            self.assertEqual(sha(self.out[c:d]), g["sha256"], g["id"])

    def tokens(self, name):
        tok = self.profile["literal_tokens"][name]
        a, b = tok["token"]["span"]
        old = self.src[a:b]
        self.assertEqual((len(old), sha(old)), (tok["token"]["bytes"], tok["token"]["sha256"]))
        c, d = self.span_out([a, b])
        new = self.out[c:d]
        dec_old, dec_new = json.loads(old.decode()), json.loads(new.decode())
        self.assertEqual(sha(dec_old.encode()), tok["decoded_sha256"])
        self.assertEqual(len(dec_old.encode()), tok["decoded_bytes"])
        self.assertEqual(new.count(b"\n"), old.count(b"\n"))
        return dec_old, dec_new

    # S05 template/control validity
    def test_html_controls_preserved_with_exact_action_children(self):
        old, new = self.tokens("html_literal")
        self.assertEqual(new.count(SHARE_OUT), 1)
        self.assertEqual(new.count(FIND_OUT), 1)
        self.assertNotIn("btn_share_", new)
        self.assertNotIn("btn_find_", new)
        self.assertEqual(old.count(".bmp") - 6, new.count(".bmp"))
        for marker in ("<button", "role=", "tabindex", "onkey", "<ui-button", " disabled",
                       'class="search-count">0</span>', 'value="ALL"', 'value="NPC"', 'value="MOB"'):
            self.assertEqual(old.count(marker), new.count(marker), marker)
        self.assertIn('<button class="move-button" disabled>✣ 移動</button>', new)
        for value, caption in (("ALL", "全部"), ("NPC", "人物"), ("MOB", "魔物")):
            self.assertIn('<option value="%s">%s</option>' % (value, caption), new)
        po, pn = parse_html(old), parse_html(new)
        self.assertEqual([t for t, _ in po.tags], [t for t, _ in pn.tags])
        # Every other tag keeps its attributes, values and order exactly.
        changed = [(tag, oa, na) for (tag, oa), (_, na) in zip(po.tags, pn.tags) if oa != na]
        share = [("class", "share-result disabled"), ("disabled", None)]
        find = [("class", "find-result disabled"), ("disabled", None)]
        bitmaps = lambda name: [(a, "navigation_interface3/btn_%s_%s.bmp" % (name, f))  # noqa: E731
                                for a, f in (("bg", "normal"), ("hover", "over"), ("down", "press"))]
        self.assertEqual([(t, o) for t, o, _ in changed][:2], [
            ("ui-button", share + bitmaps("share") + [("title", "Not supported by this client")]),
            ("ui-button", find + bitmaps("find"))])
        self.assertEqual([n for _, _, n in changed][:2],
                         [share + [("title", "此用戶端不支援分享")], find])
        self.assertEqual(len(changed), 3)
        tag, oa, na = changed[2]
        self.assertEqual([(k, v) for k, v in oa if k != "title"], [(k, v) for k, v in na if k != "title"])
        self.assertEqual((dict(oa)["title"], dict(na)["title"]), ("Path marker", "路徑標記"))
        self.assertEqual(len(pn.text), len(po.text) + 2)
        self.assertNotIn("Navigation</div>", new)

    def test_css_has_only_the_scoped_rule_replaced(self):
        old, new = self.tokens("css_literal")
        self.assertEqual(old.count(OLD_CSS), 1)
        self.assertEqual(new.count(NEW_CSS), 1)
        self.assertEqual(new.replace(NEW_CSS, OLD_CSS), old)
        for rule in (".Navigation .disabled { filter:grayscale(.55); opacity:.65; }",
                     ".Navigation .search-actions { height:23px;"):
            self.assertEqual((old.count(rule), new.count(rule)), (1, 1), rule)

    def test_finite_arrays_and_dynamic_lines(self):
        q = lambda xs: ", ".join('"%s"' % x for x in xs)  # noqa: E731
        expected = [
            "const elementNames = [%s];" % q(ELEMENTS),
            "const raceNames = [%s];" % q(RACES),
            "const sizeNames = [%s];" % q(SIZES),
            'if (count <= 5) return "極少"; if (count <= 15) return "少"; if (count <= 40) return '
            '"普通"; if (count <= 80) return "多"; return "極多";',
            'race: raceNames[Number(mob[7]) & 255] || "未知",',
            'size: sizeNames[Number(mob[7]) >>> 8 & 255] || "未知",',
            'addStat("等級", result.level || "?");',
            'addStat("屬性", result.element || "未知");',
            'addStat("種族", result.race || "未知");',
            'addStat("體型", result.size || "未知");',
            'frequency.title = location.spawnCount + " 筆出現資料";',
            'textContent = results.length ? "請選擇結果" : "無結果";',
            'textContent = results.length ? "" : "請嘗試其他關鍵字。";',
            '"<div class=\\"no-results\\">找不到結果</div>";',
            'if (options.noPathFound) text += " （找不到路徑）";',
            'displayName: "地圖選點"',
            'description: "%s",' % HELP,
        ]
        for line in expected:
            self.assertEqual(self.out.count(line.encode()), 1, line)
        for gone in (b"Very Low", b"Demi-Human", b"Map-wide spawn", b"An English GRF can replace"):
            self.assertEqual(self.src.count(gone), 1, gone)
            self.assertEqual(self.out.count(gone), 0, gone)
        self.assertIn(b"navigation-english-tables", self.src)

    # S04 refusals on actual bytes
    def test_forward_refusals(self):
        a01 = self.edits[0]["input_span"][0]
        cases = {
            "str": self.src.decode("utf-8"), "bytearray": bytearray(self.src),
            "memoryview": memoryview(self.src), "empty": b"", "truncated": self.src[:-1],
            "grown": self.src + b"\n", "inside-site": self.flip(self.src, a01),
            "outside-site": self.flip(self.src, 100), "already-localized": self.out,
        }
        for label, data in cases.items():
            with self.subTest(label), self.assertRaises(ValueError):
                nav.transform_bundle(data)

    def test_inverse_refusals(self):
        c = self.edits[0]["derived_output_span"][0]
        cases = {
            "str": self.out.decode("utf-8"), "bytearray": bytearray(self.out), "empty": b"",
            "truncated": self.out[:-1], "grown": self.out + b"\n", "original": self.src,
            "new-text": self.flip(self.out, c), "complement": self.flip(self.out, OUT_BYTES - 2),
        }
        for label, data in cases.items():
            with self.subTest(label), self.assertRaises(ValueError):
                nav.restore_bundle(data)

    def test_fragment_and_result_layers_refuse_independently(self):
        # Re-pin a mutated copy so only the later layers can catch it.
        inside = self.flip(self.src, self.edits[40]["input_span"][0])
        with self.assertRaisesRegex(ValueError, "fixed fragment"):
            nav._splice(inside, forward_sites(), IN_BYTES, sha(inside), OUT_BYTES, OUT_SHA, "t")
        outside = self.flip(self.src, 10730000)
        with self.assertRaisesRegex(ValueError, "result"):
            nav._splice(outside, forward_sites(), IN_BYTES, sha(outside), OUT_BYTES, OUT_SHA, "t")
        empty_site = self.flip(self.out, 7025090)  # complement byte at the co-located point
        with self.assertRaises(ValueError):
            nav._splice(empty_site, inverse_sites(), OUT_BYTES, sha(empty_site), IN_BYTES, IN_SHA, "t")

    @staticmethod
    def flip(data, index):
        return data[:index] + bytes([data[index] ^ 0x01]) + data[index + 1:]

    # S05 optional parse-only JS syntax check
    def test_node_syntax_check_same_for_both(self):
        if not NODE:
            self.skipTest("node not found: JS syntax parse skipped")
        for level in reversed([WORK] + list(WORK.parents)):
            if not level.exists():
                level.mkdir(mode=0o700)
        os.chmod(WORK, 0o700)
        results = []
        with tempfile.TemporaryDirectory(dir=WORK) as tmp:
            os.chmod(tmp, 0o700)
            for label, data in (("original", self.src), ("localized", self.out)):
                path = Path(tmp) / ("%s.mjs" % label)
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as fh:
                    fh.write(data)
                run = subprocess.run([NODE, "--check", str(path)], capture_output=True, timeout=300)
                results.append(run.returncode)
        self.assertEqual(results, [0, 0])


if __name__ == "__main__":
    unittest.main()
