"""Own-source checks for the ro-solo-ch1-entry mod (T10.007, T10.009).

Run: python3 -I -B tools/renewal/test_chapter1_entry.py

Two kinds of check, both on the committed files only:

- static: package layout, mod.json fields, QUEST_DB shape and unchanged bytes,
  UTF-8, audited title bytes, forbidden-command/word checks, NPC/warp
  declaration lines and the ordering of reads and writes;
- modeled: a small authored interpreter for the subset of rAthena script the
  real entry.txt and first_edge.txt use, run against those files with a
  modeled quest log. The model follows the pinned rAthena 0693b8c excerpts
  (inactive reported as 1; setquest and completequest return success even
  when nothing changed; close2 waits for the button and the script continues).
  Fault hooks make either write a no-op or change the log after a write or at
  any yield. Mutation controls edit a copy of the real text and confirm the
  same checks catch a missing readback or a partial tuple check.
  It is a model: it proves nothing about the real parser, char-server
  persistence, relog, map cells, arrival or the client. Those remain Root
  integration gates.
"""

import hashlib
import itertools
import json
from pathlib import Path
import re
import sys
import unittest

HERE = Path(__file__).resolve().parent
MOD = HERE / "chapter1_entry" / "ro-solo-ch1-entry"
NPC = MOD / "npc" / "entry.txt"
EDGE = MOD / "npc" / "first_edge.txt"
NPC_FILES = (NPC, EDGE)
QUEST_DB = MOD / "db" / "quest_db.yml"
MOD_JSON = MOD / "mod.json"

ENTRY, SECOND, THIRD = 18368, 18369, 18370
GUARDED = (ENTRY, SECOND, THIRD)
# UTF-8 SHA-256 of the Big5-decoded client quest-log fields, from the frozen
# T10.007 input packet (data/TC_ENTRY_ROWS.json, Root-audited rows 37/73/114).
TITLE_SHA256 = {
    ENTRY: "a71c099afc2f2439f8b1a39944fd2424a2efeb99d4f24715f470bbdaa940ba12",
    SECOND: "cdef2c43bd2100a0194eafc67036410906fb93a69571026be44c0e4619c7e46e",
    THIRD: "c110a8a52040a7ad5345cc3503b694548af8f9bb38523769bfcd9184102c6e36",
}
ENTRY_SUMMARY_SHA256 = "2bbdf105102f7663b88da765fc5c3dc112e438a11bc6a837f086c8b650f47124"
# The T10.007 quest_db.yml; T10.009 keeps the three rows byte-identical.
QUEST_DB_SHA256 = "c6bbbae1c6e902c90e36c20aa931ab92e3673b565a3855d49251fcd2724e6614"
# A long client Description sentence fragment; the NPC must not copy prose.
DESCRIPTION_FRAGMENTS = ("雖然令人難以置信", "接受守護精靈的引導", "觸碰梧桐樹後", "莎莎", "梅雪")

FIRST_DEST = ("ygg_edge", 255, 240)
REPEAT_DEST = ("ygg_edge", 212, 95)
PAYON_DEST = ("ygg_edge", 194, 97)
TOWN_DEST = ("prt_fild05", 353, 248)

# Modeled stored quest state. Any other int is stored raw and returned as-is
# by checkquest, so 0, 3 or 7 model an unknown value.
ABSENT, INACTIVE, ACTIVE, COMPLETE = None, "inactive", 1, 2
STORED = (ABSENT, INACTIVE, ACTIVE, COMPLETE, 0, 7)
UNRELATED = {1000: COMPLETE, 7128: ACTIVE, 18371: INACTIVE}


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def strip_comment(line):
    """Drop a // comment that is not inside a string literal."""
    quoted = False
    for i, ch in enumerate(line):
        if ch == '"':
            quoted = not quoted
        elif not quoted and line.startswith("//", i):
            return line[:i]
    return line


def declarations(text):
    """Top-level NPC/warp declarations: (w1, kind, name, w4, body lines)."""
    out, lines, i = [], text.split("\n"), 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line or line.startswith(("//", "\t", " ")):
            continue
        parts = line.split("\t")
        if len(parts) != 4:
            raise AssertionError(f"not a declaration: {line!r}")
        body = []
        if parts[3].endswith(",{"):
            while lines[i] != "}":
                body.append(strip_comment(lines[i]).strip())
                i += 1
            i += 1
        out.append((parts[0], parts[1], parts[2], parts[3], body))
    return out


def script_lines(path=NPC, index=0, text=None):
    text = path.read_text(encoding="utf-8") if text is None else text
    return [d for d in declarations(text) if d[1] == "script"][index][4]


def tuple_of(char):
    return tuple(char.checkquest(q) for q in GUARDED)


def validate_oninit_form(lines):
    """Only check OnInit's supported form; do not execute the bubble condition."""
    if "OnInit:" not in lines:
        return
    tail = [line for line in lines[lines.index("OnInit:") + 1:] if line]
    if (len(tail) != 2 or tail[1] != "end;" or not re.fullmatch(
            r'questinfo\(QTYPE_QUEST, QMARK_YELLOW, "[^"\n]+"\);', tail[0])):
        raise AssertionError("unsupported OnInit form")


# ---------------------------------------------------------------- the model

class Character:
    """Modeled quest log of one character, per pinned quest.cpp semantics."""

    def __init__(self, level, quests=None, add_fails=False, faults=()):
        self.level = level
        self.quests = dict(UNRELATED)
        self.quests.update(quests or {})
        self.add_fails = add_fails  # e.g. quest missing from the loaded DB
        self.faults = set(faults)  # (command, id) that silently does nothing
        self.zeny, self.exp, self.items = 12345, 678, {501: 3}
        self.writes, self.warps = [], []

    def guarded(self):
        return {q: s for q, s in self.quests.items() if q in GUARDED}

    def checkquest(self, qid):
        state = self.quests.get(qid)
        if state is None:
            return -1
        return 1 if state == INACTIVE else state

    def setquest(self, qid):
        self.writes.append(("setquest", qid))
        if self.add_fails or ("setquest", qid) in self.faults or qid in self.quests:
            return  # quest_add returned -1; the script command still succeeds
        self.quests[qid] = ACTIVE

    def completequest(self, qid):
        self.writes.append(("completequest", qid))
        if ("completequest", qid) in self.faults:
            return
        # quest_update_status only finds active or inactive records.
        if self.quests.get(qid) in (ACTIVE, INACTIVE):
            self.quests[qid] = COMPLETE


class Run:
    """Interprets the line-oriented subset of rAthena script the mod uses."""

    def __init__(self, char, choices=1, on_yield=None, on_write=None, lines=None):
        self.char, self.on_yield, self.on_write = char, on_yield, on_write
        self.choices = list(choices) if isinstance(choices, (list, tuple)) else None
        self.choice = choices
        self.lines = script_lines() if lines is None else lines
        validate_oninit_form(self.lines)
        self.labels = {l[:-1]: i for i, l in enumerate(self.lines)
                       if re.fullmatch(r"[A-Za-z_]\w*:", l)}
        self.mes, self.debug, self.bottom = [], [], []
        self.menus = self.yields = 0
        self.window = self.closed = self.warped = False

    def expr(self, src, scope):
        def call(m):
            return self.call(m.group(1), m.group(2), scope)
        py = re.sub(r"\b(checkquest|callsub|select)\(([^()]*)\)", lambda m: repr(call(m)), src)
        py = re.sub(r"\.@(\w+)", lambda m: repr(scope.get(m.group(1), 0)), py)
        py = py.replace("BaseLevel", repr(self.char.level))
        py = py.replace("&&", " and ").replace("||", " or ")
        if re.search(r"[^\w\s().=!<>+\-'\"]", re.sub(r'"[^"]*"', "", py)):
            raise AssertionError(f"unsupported expression: {src}")
        return eval(py, {"__builtins__": {}}, {})  # noqa: S307 - authored subset

    def call(self, name, arg, scope):
        if name == "checkquest":
            if "," in arg:
                raise AssertionError("checkquest must use the default HAVEQUEST form")
            return self.char.checkquest(int(arg))
        if name == "select":
            self.menus += 1
            self.yield_("select")
            if self.choices is None:
                return self.choice
            if not self.choices:
                raise AssertionError("unexpected extra menu")
            return self.choices.pop(0)
        if name == "callsub":
            return self.execute(self.labels[arg.strip()] + 1, {})
        raise AssertionError(name)

    def yield_(self, kind):
        self.yields += 1
        if self.on_yield:
            self.on_yield(self, self.char, kind)

    def wrote(self, cmd, qid):
        if self.on_write:
            self.on_write(self, self.char, cmd, qid)

    def block_end(self, i):
        depth = 0
        for j in range(i, len(self.lines)):
            depth += self.lines[j].count("{") - self.lines[j].count("}")
            if depth == 0:
                return j
        raise AssertionError("unbalanced block")

    def execute(self, pc=0, scope=None):
        scope = {} if scope is None else scope
        while pc < len(self.lines):
            line = self.lines[pc]
            pc += 1
            if not line or line == "}" or line.endswith(":") and line[:-1] in self.labels:
                continue
            if self.warped and line != "end;":
                raise AssertionError(f"warp must be followed by end, got: {line}")
            m = re.fullmatch(r"if \((.*)\) \{", line)
            if m:
                if not self.expr(m.group(1), scope):
                    pc = self.block_end(pc - 1) + 1
                continue
            m = re.fullmatch(r"if \((.*)\) (.*;)", line)
            if m:
                if not self.expr(m.group(1), scope):
                    continue
                line = m.group(2)
            r = self.statement(line, scope)
            if r is not None:
                kind, value = r
                if kind == "goto":
                    pc = self.labels[value] + 1
                else:
                    return value
        raise AssertionError("fell off the end of the script")

    def statement(self, line, scope):
        m = re.fullmatch(r"\.@(\w+) = (.*);", line)
        if m:
            scope[m.group(1)] = self.expr(m.group(2), scope)
            return None
        m = re.fullmatch(r'mes "(.*)";', line)
        if m:
            if self.closed:
                raise AssertionError("mes after close2: dialog already closed")
            self.mes.append(m.group(1))
            self.window = True
            return None
        if line == "next;":
            if not self.window or self.closed:
                raise AssertionError("next without an open dialog")
            self.yield_("next")
            return None
        if line == "close2;":
            if not self.window or self.closed:
                raise AssertionError("close2 without a dialog would halt the script")
            self.window, self.closed = False, True
            self.yield_("close2")
            return None
        if line in ("close;", "end;"):
            self.closed = True
            return ("return", None)
        m = re.fullmatch(r"goto (\w+);", line)
        if m:
            return ("goto", m.group(1))
        m = re.fullmatch(r"return (-?\d+);", line)
        if m:
            return ("return", int(m.group(1)))
        m = re.fullmatch(r"(setquest|completequest) (\d+);", line)
        if m:
            getattr(self.char, m.group(1))(int(m.group(2)))
            self.wrote(m.group(1), int(m.group(2)))
            return None
        m = re.fullmatch(r'warp "(\w+)",(\d+),(\d+);', line)
        if m:
            self.char.warps.append((m.group(1), int(m.group(2)), int(m.group(3))))
            self.warped = True
            return None
        m = re.fullmatch(r'dispbottom "(.*)";', line)
        if m:
            self.bottom.append(m.group(1))
            return None
        if line.startswith("debugmes "):
            atom = r'(?:"[^"\n]*"|checkquest\((?:18368|18369|18370)\)|\.@[abc])'
            if not re.fullmatch(rf"debugmes {atom}(?: \+ {atom})*;", line):
                raise AssertionError("unsupported debugmes form: " + line)
            self.debug.append(line)
            return None
        raise AssertionError(f"unmodeled statement: {line}")


def talk(level, quests=None, choices=1, on_yield=None, add_fails=False, faults=(),
         on_write=None, lines=None, char=None):
    char = char or Character(level, quests, add_fails, faults)
    run = Run(char, choices, on_yield, on_write, lines)
    run.execute()
    assert run.closed
    return char, run


def messenger(level=200, quests=None, **kw):
    kw.setdefault("lines", script_lines(EDGE, 0))
    return talk(level, quests, **kw)


def classify(a, b, c):
    """The brief's contract, stated independently of the script."""
    vals = (a, b, c)
    if any(v not in (-1, 1, 2) for v in vals):
        return "conflict"
    if vals == (-1, -1, -1):
        return "fresh"
    if a == 1:
        return "resume" if (b, c) == (-1, -1) else "conflict"
    if b == 1 and c != -1:
        return "conflict"
    if vals == (2, 1, -1):
        return "edge_done"
    if vals == (2, -1, -1):
        return "interrupted"
    return "preserved"


STATE_CODE = {"fresh": 0, "resume": 1, "preserved": 2, "conflict": 3,
              "edge_done": 4, "interrupted": 5}
LOGGED = ("conflict", "interrupted")


def combos():
    for combo in itertools.product(STORED, repeat=3):
        yield combo, {q: s for q, s in zip(GUARDED, combo) if s is not None}


def sentinels_ok(test, char):
    for qid, state in UNRELATED.items():
        test.assertEqual(char.quests[qid], state, qid)
    test.assertEqual((char.zeny, char.exp, char.items), (12345, 678, {501: 3}))
    test.assertTrue(all(q in GUARDED for _, q in char.writes))


# ---------------------------------------------------------------- A: package

class PackageTests(unittest.TestCase):
    def test_owned_files_only(self):
        found = sorted(p.relative_to(MOD).as_posix() for p in MOD.rglob("*") if p.is_file())
        self.assertEqual(found, ["db/quest_db.yml", "mod.json", "npc/entry.txt",
                                 "npc/first_edge.txt"])

    def test_mod_json(self):
        m = json.loads(MOD_JSON.read_text(encoding="utf-8"))
        self.assertEqual(m["name"], MOD.name)
        for key in ("version", "author", "description"):
            self.assertTrue(m[key].strip(), key)
        self.assertEqual(m["requires"], {"app": ">=1.6.3", "era": "renewal"})
        self.assertNotIn("client", m["requires"])

    def test_utf8_lf_no_bom(self):
        for path in (MOD_JSON, QUEST_DB) + NPC_FILES:
            raw = path.read_bytes()
            raw.decode("utf-8")
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), path)
            self.assertNotIn(b"\r", raw, path)
            self.assertTrue(raw.endswith(b"\n"), path)

    def test_npc_header_line(self):
        decls = declarations(NPC.read_text(encoding="utf-8"))
        self.assertEqual(len(decls), 1, "exactly one NPC in entry.txt")
        w1, kind, name, w4, _ = decls[0]
        self.assertEqual((w1, kind, w4), ("prt_fild05,353,252,4", "script", "4_CH1_BRANCH,{"))
        self.assertTrue(name.partition("#")[2].upper().startswith("ROSOLO_CH1"))
        # rAthena NAME_LENGTH is 24 including the terminator.
        self.assertLessEqual(len(name.encode("utf-8")), 23)

    def test_first_edge_declarations(self):
        """Messenger plus exactly one declaration per route, as in the brief."""
        decls = declarations(EDGE.read_text(encoding="utf-8"))
        heads = [(w1, kind, w4) for w1, kind, _, w4, _ in decls]
        self.assertEqual(heads, [
            ("ygg_edge,253,246,4", "script", "4_CH1_DELEGACY02,{"),
            ("ygg_edge,164,140,0", "warp", "1,1,ygg_fruit,73,117"),
            ("ygg_fruit,71,114,0", "warp", "1,1,ygg_edge,168,139"),
            ("ygg_edge,216,91,0", "script", "GATE_SKYBLUE,1,1,{"),
        ])
        names = [d[2] for d in decls] + [d[2] for d in declarations(NPC.read_text(encoding="utf-8"))]
        self.assertEqual(len(names), len({n.upper() for n in names}), "unique identities")
        for name in names:
            hidden = name.partition("#")[2] or name
            self.assertTrue(hidden.upper().startswith("ROSOLO_CH1"), name)
            self.assertLessEqual(len(name.encode("utf-8")), 23, name)

    def test_no_fallback_graph_or_other_npcs(self):
        text = "\n".join(strip_comment(l) for p in NPC_FILES
                         for l in p.read_text(encoding="utf-8").split("\n"))
        decls = [d for p in NPC_FILES for d in declarations(p.read_text(encoding="utf-8"))]
        self.assertEqual(len(decls), 5)
        self.assertFalse(any(d[0].startswith("ygg_fruit,73,117") for d in decls))
        for word in ("cloaknpc", "HIDDEN_WARP_NPC", "Maysel", "Est#", "Debris", "cutin",
                     "c1p1", "Lapine", "Ashridge", "strnpcinfo", "194, 97", "194,97", "payon"):
            self.assertFalse(word.lower() in text.lower(), word)

    def test_braces_balance(self):
        for path in NPC_FILES:
            for _, kind, _, _, body in declarations(path.read_text(encoding="utf-8")):
                depth = 0
                for ch in re.sub(r'"[^"]*"', "", "\n".join(body)):
                    depth += {"{": 1, "}": -1}.get(ch, 0)
                    self.assertGreaterEqual(depth, 0)
                self.assertEqual(depth, 0, path)


# ------------------------------------------------------------ D: text and DB

class QuestDbTests(unittest.TestCase):
    def setUp(self):
        self.lines = [l for l in QUEST_DB.read_text(encoding="utf-8").split("\n")
                      if l.strip() and not l.lstrip().startswith("#")]

    def test_db_file_unchanged(self):
        self.assertEqual(hashlib.sha256(QUEST_DB.read_bytes()).hexdigest(), QUEST_DB_SHA256)

    def test_header_and_sections(self):
        self.assertEqual(self.lines[:3], ["Header:", "  Type: QUEST_DB", "  Version: 3"])
        top = [l for l in self.lines if not l.startswith(" ")]
        self.assertEqual(top, ["Header:", "Body:"])
        self.assertFalse(any(re.match(r"\s*Clear:", l) for l in self.lines))

    def test_three_rows_id_title_only(self):
        body = self.lines[self.lines.index("Body:") + 1:]
        rows = []
        for line in body:
            m = re.fullmatch(r"  - Id: (\d+)", line)
            if m:
                rows.append({"Id": int(m.group(1))})
                continue
            m = re.fullmatch(r"    (\w+): (.+)", line)
            self.assertTrue(m, line)
            self.assertEqual(m.group(1), "Title")
            rows[-1]["Title"] = m.group(2)
        self.assertEqual([r["Id"] for r in rows], list(GUARDED))
        for r in rows:
            self.assertEqual(sorted(r), ["Id", "Title"])
            self.assertEqual(sha(r["Title"]), TITLE_SHA256[r["Id"]], r["Id"])


class TextTests(unittest.TestCase):
    def strings(self, path):
        return re.findall(r'"([^"]*)"', path.read_text(encoding="utf-8"))

    def test_npc_text_reuses_short_log_text_only(self):
        for path in NPC_FILES:
            text = path.read_text(encoding="utf-8")
            titles = re.findall(r"「(.+?)」", "".join(self.strings(path)))
            self.assertTrue(titles, path)
            self.assertTrue(all(sha(t) in (TITLE_SHA256[ENTRY], TITLE_SHA256[SECOND])
                                for t in titles), titles)
            objectives = [s.split("：", 1)[1] for s in self.strings(path) if s.startswith("目標：")]
            self.assertTrue(all(sha(o) == ENTRY_SUMMARY_SHA256 for o in objectives))
            for fragment in DESCRIPTION_FRAGMENTS:
                self.assertNotIn(fragment, text)
            for decl in declarations(text):
                for line in decl[4]:
                    m = re.fullmatch(r'(?:mes|dispbottom) "(.*)";', line)
                    if m:
                        self.assertLessEqual(len(m.group(1)), 24, m.group(1))
                        self.assertIsNone(re.search(r"[A-Za-z]", m.group(1)), m.group(1))
        self.assertTrue(any("目標：" in s for s in self.strings(NPC)))

    def test_menus_are_plain_chinese(self):
        options = re.findall(r'select\("([^"]*)"\)', NPC.read_text(encoding="utf-8"))
        self.assertEqual(len(options), 2, "registration menu and travel menu")
        self.assertNotIn("select(", EDGE.read_text(encoding="utf-8"))
        for menu in options:
            for option in menu.split(":"):
                self.assertIsNone(re.search(r"[A-Za-z0-9_#]", option), option)


# ------------------------------------------------- C: static state discipline

FORBIDDEN = ("erasequest", "changequest", "getitem", "delitem", "getexp", "Zeny", "set ",
             "setarray", "cleararray", "callfunc", "donpcevent", "doevent", "addtimer",
             "sleep", "input", "isbegin_quest", "getvariableofnpc", "query_sql",
             "atcommand", "unitwarp", "areawarp", "jobchange", "resetlvl", "savepoint",
             "cutin", "cloaknpc", "navigateto", "specialeffect", "progressbar")


def code_of(lines):
    return "\n".join(re.sub(r'"[^"]*"', '""', l) for l in lines)


class ScriptDisciplineTests(unittest.TestCase):
    def setUp(self):
        self.entry = script_lines(NPC, 0)
        self.msg = script_lines(EDGE, 0)
        self.ret = script_lines(EDGE, 1)
        self.bodies = (self.entry, self.msg, self.ret)

    def test_mutations_are_exactly_owned(self):
        entry, msg, ret = map(code_of, self.bodies)
        self.assertEqual(re.findall(r"\bsetquest\s+(\d+)", entry), [str(ENTRY)])
        self.assertNotIn("completequest", entry)
        self.assertEqual(re.findall(r"\bcompletequest\s+(\d+)", msg), [str(ENTRY)])
        self.assertEqual(re.findall(r"\bsetquest\s+(\d+)", msg), [str(SECOND)])
        self.assertNotIn("warp", msg)
        self.assertNotIn("quest", ret)
        self.assertEqual(re.findall(r"\bwarp\b.*", ret), ['warp "",353,248;'])
        self.assertEqual(re.findall(r'warp "ygg_edge",(\d+),(\d+);',
                                    "\n".join(self.entry)), [("255", "240"), ("212", "95")])
        for code in (entry, msg, ret):
            for word in FORBIDDEN:
                self.assertNotIn(word, code, word)
            self.assertNotRegex(code, rf"(setquest|completequest)\s+{THIRD}")

    def test_only_guarded_ids(self):
        for path in NPC_FILES:
            code = code_of(l for d in declarations(path.read_text(encoding="utf-8"))
                           for l in d[4])
            ids = set(re.findall(r"\b\d{4,}\b", code))
            self.assertLessEqual(ids, {str(i) for i in GUARDED}, path)

    def test_variables_are_scope_only(self):
        for lines in self.bodies:
            code = code_of(lines)
            for name in re.findall(r"^\s*([^\s=]+)\s*=[^=]", code, re.M):
                self.assertTrue(name.startswith(".@"), name)
            for prefix in (r"(?<![.\w])@\w", r"\$\w", r"#\w", r"(?<!@)\.(?!@)\w", r"'\w"):
                self.assertIsNone(re.search(prefix, code), prefix)

    def test_checkquest_comparisons_are_explicit(self):
        """Read into a .@ variable, compared with ==/!=, or logged; no truthiness."""
        for lines in self.bodies:
            for line in lines:
                plain = re.sub(r'"[^"]*"', '""', line)
                if line.startswith(("debugmes", "questinfo")):
                    continue
                for m in re.finditer(r"checkquest\(\d+\)", plain):
                    head, tail = plain[:m.start()], plain[m.end():]
                    direct = re.fullmatch(r"\.@\w+ = ", head) and tail == ";"
                    self.assertTrue(direct or re.match(r"\s*(==|!=) -?[12]\b", tail), line)
                # A bare variable as a whole operand is truthiness.
                self.assertIsNone(re.search(r"(\(|&&|\|\|)\s*!?\.@\w+\s*(\)|&&|\|\|)", plain), line)
                self.assertIsNone(re.search(r"(\.@[abc]|checkquest\(\d+\))\s*(==|!=|<|>|<=|>=)\s*0\b",
                                            plain), "inactive-as-0: " + line)

    def test_setquest_after_recheck_without_yield(self):
        lines = self.entry
        i_set = next(i for i, l in enumerate(lines) if l.startswith("setquest"))
        i_sel = next(i for i, l in enumerate(lines) if "select(" in l)
        rechecks = [i for i, l in enumerate(lines) if "callsub(L_State)" in l]
        self.assertTrue(any(i_sel < i < i_set for i in rechecks))
        self.assertTrue(any(i_sel < i < i_set and "BaseLevel < 200" in l
                            for i, l in enumerate(lines)))
        between = lines[max(i for i in rechecks if i < i_set):i_set]
        self.assertFalse(any(re.match(r"(next|select|menu|sleep|input|close2)\b", l) for l in between))
        after = lines[i_set + 1:i_set + 3]
        self.assertTrue(any("checkquest(18368)" in l for l in after), "postcondition read-back")

    def test_warp_rechecked_after_close2_and_ends(self):
        lines = self.entry
        i_c2 = [i for i, l in enumerate(lines) if l == "close2;"]
        self.assertEqual(len(i_c2), 1)
        for i, l in enumerate(lines):
            if l.startswith("warp "):
                tail = lines[i_c2[0] + 1:i]
                self.assertGreater(i, i_c2[0])
                self.assertTrue(any("callsub(L_State)" in t for t in tail))
                self.assertTrue(any("BaseLevel < 200" in t for t in tail))
                self.assertFalse(any(re.match(r"(next|select|close2|mes)\b", t) for t in tail))
                self.assertEqual(lines[i + 1], "end;")

    def test_messenger_writes_are_readback_guarded_without_yield(self):
        lines = self.msg
        i_next = [i for i, l in enumerate(lines) if l == "next;"]
        i_cq = next(i for i, l in enumerate(lines) if l.startswith("completequest"))
        i_sq = next(i for i, l in enumerate(lines) if l.startswith("setquest"))
        i_ok = next(i for i, l in enumerate(lines) if i > i_sq and l.startswith("mes "))
        self.assertEqual(len(i_next), 1)
        self.assertLess(i_next[0], i_cq)
        self.assertLess(i_cq, i_sq)
        window = lines[i_next[0] + 1:i_ok]
        self.assertFalse(any(re.match(r"(next|select|close2?|sleep|mes|warp|callfunc|callsub|end)\b", l)
                             for l in window), "no yield/helper between precondition and postcondition")
        for start, end in ((i_next[0], i_cq), (i_cq, i_sq), (i_sq, i_ok)):
            reads = [l for l in lines[start + 1:end] if "= checkquest(" in l]
            self.assertEqual(len(reads), 3, (start, end))
            checks = [l for l in lines[start + 1:end] if l.startswith("if (")]
            self.assertTrue(checks)
            for check in checks:
                self.assertTrue(all(v in check for v in (".@a", ".@b", ".@c")), check)


# --------------------------------------------- B/C: modeled starter runs

def perturb(kind_at, change):
    """Hook that applies change(char) at the n-th yield (1-based)."""
    def hook(run, char, kind):
        if run.yields == kind_at:
            change(char)
    return hook


def set_quest(qid, state):
    def change(char):
        if state is None:
            char.quests.pop(qid, None)
        else:
            char.quests[qid] = state
    return change


def set_level(level):
    def change(char):
        char.level = level
    return change


class StarterTests(unittest.TestCase):
    def test_fresh_level_gate(self):
        for level, choice in itertools.product((1, 199), ([1, 1], [2])):
            char, run = talk(level, choices=choice)
            self.assertEqual((char.guarded(), char.writes, char.warps, run.menus),
                             ({}, [], [], 0), level)
        for level in (200, 201, 275):
            char, run = talk(level, choices=[1, 2])
            self.assertEqual(char.guarded(), {ENTRY: ACTIVE})
            self.assertEqual(char.writes, [("setquest", ENTRY)])
            self.assertEqual(run.menus, 2)
            sentinels_ok(self, char)

    def test_cancel_changes_nothing_and_retry_registers_once(self):
        char = Character(200)
        Run(char, [2]).execute()
        self.assertEqual((char.guarded(), char.writes, char.warps), ({}, [], []))
        Run(char, [1, 2]).execute()
        Run(char, [2]).execute()  # second visit resumes; declines travel
        self.assertEqual(char.guarded(), {ENTRY: ACTIVE})
        self.assertEqual(char.writes, [("setquest", ENTRY)])
        self.assertEqual(char.warps, [])

    def test_first_registration_travels_to_first_landing(self):
        for level in (200, 201):
            char, run = talk(level, choices=[1, 1])
            self.assertEqual(char.guarded(), {ENTRY: ACTIVE})
            self.assertEqual(char.writes, [("setquest", ENTRY)])
            self.assertEqual(char.warps, [FIRST_DEST])
            self.assertEqual(run.yields, 5)  # next, select, next, select, close2
            sentinels_ok(self, char)

    def test_defer_keeps_registration_then_repeat_destination(self):
        char = Character(200)
        run = Run(char, [1, 2])
        run.execute()
        self.assertEqual(char.guarded(), {ENTRY: ACTIVE}, "defer is not cancellation")
        self.assertEqual(char.warps, [])
        self.assertIn("任務紀錄會保留著。", run.mes)
        Run(char, [1]).execute()
        self.assertEqual(char.warps, [REPEAT_DEST], "first-entry status is not durable")
        self.assertEqual(char.writes, [("setquest", ENTRY)])

    def test_resume_active_and_inactive_at_any_level(self):
        for state, level in itertools.product((ACTIVE, INACTIVE), (150, 199, 200, 201)):
            char, run = talk(level, {ENTRY: state}, choices=[1])
            self.assertEqual(char.writes, [])
            self.assertEqual(char.guarded(), {ENTRY: state}, "inactive is not reset")
            self.assertIn("目標：前往梧桐村", run.mes)
            self.assertEqual(run.menus, 1 if level >= 200 else 0)
            self.assertEqual(char.warps, [REPEAT_DEST] if level >= 200 else [])

    def test_edge_done_repeat_and_payon_never(self):
        for b, level in itertools.product((ACTIVE, INACTIVE), (199, 200, 201)):
            for choice in (1, 2):
                char, run = talk(level, {ENTRY: COMPLETE, SECOND: b}, choices=[choice])
                self.assertEqual(char.writes, [])
                self.assertEqual(char.guarded(), {ENTRY: COMPLETE, SECOND: b})
                want = [REPEAT_DEST] if level >= 200 and choice == 1 else []
                self.assertEqual(char.warps, want, (b, level, choice))
                self.assertNotIn(PAYON_DEST, char.warps)

    def test_completed_only_and_active_active_hold(self):
        for quests in ({ENTRY: COMPLETE}, {ENTRY: ACTIVE, SECOND: ACTIVE},
                       {ENTRY: INACTIVE, SECOND: INACTIVE}):
            char, run = talk(250, quests, choices=[1, 1])
            self.assertEqual((char.writes, char.warps, run.menus), ([], [], 0), quests)
            self.assertEqual(char.guarded(), quests)
            self.assertTrue(run.debug, quests)

    def test_registration_yield_rechecks(self):
        """State/level changed during the registration menu (yield 2)."""
        char, run = talk(200, choices=[1, 1], on_yield=perturb(2, set_level(199)))
        self.assertEqual((char.guarded(), char.writes, char.warps), ({}, [], []))
        for qid, state in ((ENTRY, COMPLETE), (SECOND, ACTIVE), (THIRD, COMPLETE), (ENTRY, 0)):
            char, run = talk(201, choices=[1, 1], on_yield=perturb(2, set_quest(qid, state)))
            self.assertEqual((char.writes, char.warps), ([], []), (qid, state))
            self.assertEqual(char.guarded(), {qid: state})
        # Registered meanwhile elsewhere: existing-progress path, repeat destination.
        for state in (ACTIVE, INACTIVE):
            char, run = talk(201, choices=[1, 1], on_yield=perturb(2, set_quest(ENTRY, state)))
            self.assertEqual(char.writes, [])
            self.assertEqual(char.warps, [REPEAT_DEST])

    def test_travel_yields_recheck_everything(self):
        """Yields 3 (next), 4 (travel select) and 5 (close2) after registration."""
        changes = {
            "level199": set_level(199),
            "A complete": set_quest(ENTRY, COMPLETE),
            "edge done": lambda c: c.quests.update({ENTRY: COMPLETE, SECOND: ACTIVE}),
            "B active": set_quest(SECOND, ACTIVE),
            "C present": set_quest(THIRD, INACTIVE),
            "A erased": set_quest(ENTRY, None),
            "A unknown": set_quest(ENTRY, 7),
        }
        for at, (name, change) in itertools.product((3, 4, 5), changes.items()):
            char, run = talk(200, choices=[1, 1], on_yield=perturb(at, change))
            self.assertEqual(char.writes, [("setquest", ENTRY)], (at, name))
            self.assertEqual(char.warps, [], (at, name))
            if at == 5:
                self.assertTrue(run.bottom, "post-close2 refusal is visible")
        # A harmless inactive toggle keeps (1,-1,-1) and still travels.
        char, run = talk(200, choices=[1, 1], on_yield=perturb(5, set_quest(ENTRY, INACTIVE)))
        self.assertEqual(char.warps, [FIRST_DEST])

    def test_repeat_travel_yields_recheck(self):
        """Yields 1 (next), 2 (travel select) and 3 (close2) on a revisit."""
        for start, at, change in itertools.product(
                ({ENTRY: ACTIVE}, {ENTRY: COMPLETE, SECOND: ACTIVE}), (1, 2, 3),
                (set_level(150), set_quest(THIRD, ACTIVE), set_quest(SECOND, COMPLETE))):
            char, run = talk(200, start, choices=[1], on_yield=perturb(at, change))
            self.assertEqual((char.writes, char.warps), ([], []), (start, at))

    def test_failed_registration_is_reported_and_retryable(self):
        char, run = talk(200, choices=[1], add_fails=True)
        self.assertEqual(char.guarded(), {})
        self.assertEqual(char.writes, [("setquest", ENTRY)])
        self.assertEqual(char.warps, [])
        self.assertTrue(run.debug)
        self.assertNotIn("任務「天地樹的召喚(1)」已記錄。", run.mes)
        char.add_fails = False
        Run(char, [1, 1]).execute()
        self.assertEqual(char.guarded(), {ENTRY: ACTIVE})
        self.assertEqual(char.warps, [FIRST_DEST])

    def test_registration_interference_is_a_truthful_postwrite_hold(self):
        for failed, qid, state in ((True, SECOND, ACTIVE), (True, THIRD, 7),
                                    (False, SECOND, ACTIVE), (False, THIRD, COMPLETE)):
            def hook(run, char, cmd, written, qid=qid, state=state):
                if (cmd, written) == ("setquest", ENTRY):
                    char.quests[qid] = state
            char, run = talk(200, choices=[1], add_fails=failed, on_write=hook)
            self.assertEqual(char.writes, [("setquest", ENTRY)])
            self.assertEqual(char.warps, [])
            self.assertIn("已經停止，不會再做其他變更。", run.mes)
            self.assertNotIn("這段任務仍未建立，可稍後再試。", run.mes)
            self.assertNotIn("任務「天地樹的召喚(1)」已記錄。", run.mes)
            self.assertTrue(any("no further change" in line for line in run.debug))
            self.assertFalse(any("no change made" in line for line in run.debug))

    def test_every_combination(self):
        """All stored states incl. inactive/unknown x levels x menu paths."""
        for combo, quests in combos():
            seen = tuple(Character(0, quests).checkquest(q) for q in GUARDED)
            want = classify(*seen)
            probe = Run(Character(200, quests))
            self.assertEqual(probe.execute(probe.labels["L_State"] + 1, {}),
                             STATE_CODE[want], combo)
            for level, choices in itertools.product((199, 200, 201), ([1, 1], [1, 2], [2])):
                char, run = talk(level, quests, list(choices))
                ok = level >= 200
                registers = want == "fresh" and ok and choices[0] == 1
                self.assertEqual(char.writes, [("setquest", ENTRY)] if registers else [],
                                 (combo, level, choices))
                self.assertEqual(char.guarded(),
                                 {ENTRY: ACTIVE} if registers else quests, (combo, level))
                if registers:
                    dest = [FIRST_DEST] if choices[1] == 1 else []
                elif want in ("resume", "edge_done") and ok:
                    dest = [REPEAT_DEST] if choices[0] == 1 else []
                else:
                    dest = []
                self.assertEqual(char.warps, dest, (combo, level, choices))
                self.assertEqual(bool(run.debug), want in LOGGED, combo)
                sentinels_ok(self, char)

    def test_characters_are_independent(self):
        one, two = Character(200), Character(200, {ENTRY: COMPLETE})
        Run(one, [1, 2]).execute()
        Run(two, [1, 1]).execute()
        self.assertEqual(one.guarded(), {ENTRY: ACTIVE})
        self.assertEqual(two.guarded(), {ENTRY: COMPLETE})
        self.assertEqual((two.writes, two.warps), ([], []))


# --------------------------------------------- G2: modeled Messenger runs

EDGE_WRITES = [("completequest", ENTRY), ("setquest", SECOND)]
SUCCESS = "任務「天地樹的召喚(2)」已記錄。"


def after_write(cmd_at, change):
    def hook(run, char, cmd, qid):
        if cmd == cmd_at:
            change(char)
    return hook


class MessengerTests(unittest.TestCase):
    def test_admitted_edge_any_level(self):
        for a, level in itertools.product((ACTIVE, INACTIVE), (1, 150, 199, 200, 275)):
            char, run = messenger(level, {ENTRY: a})
            self.assertEqual(char.writes, EDGE_WRITES)
            self.assertEqual(char.guarded(), {ENTRY: COMPLETE, SECOND: ACTIVE})
            self.assertIn(SUCCESS, run.mes)
            self.assertEqual((char.warps, run.debug, run.menus), ([], [], 0))
            sentinels_ok(self, char)

    def test_terminal_repeat_is_read_only(self):
        char, run = messenger(200, {ENTRY: ACTIVE})
        for _ in range(3):
            before = len(char.writes)
            run = Run(char, lines=script_lines(EDGE, 0))
            run.execute()
            self.assertEqual(len(char.writes), before)
            self.assertIn("任務「天地樹的召喚(2)」仍在進行中。", run.mes)
            self.assertEqual(run.debug, [])
        self.assertEqual(char.writes, EDGE_WRITES)

    def test_every_tuple_preserved_unless_admitted(self):
        for combo, quests in combos():
            seen = tuple(Character(0, quests).checkquest(q) for q in GUARDED)
            want = classify(*seen)
            char, run = messenger(200, quests)
            if want == "resume":
                self.assertEqual(char.writes, EDGE_WRITES, combo)
                self.assertEqual(tuple_of(char), (2, 1, -1), combo)
                continue
            self.assertEqual(char.writes, [], combo)
            self.assertEqual(char.guarded(), quests, combo)
            self.assertNotIn(SUCCESS, run.mes)
            self.assertEqual(bool(run.debug), want in LOGGED, combo)
            sentinels_ok(self, char)

    def test_completequest_noop_prevents_setquest_and_retries(self):
        char, run = messenger(200, {ENTRY: ACTIVE}, faults={("completequest", ENTRY)})
        self.assertEqual(char.writes, [("completequest", ENTRY)])
        self.assertEqual(tuple_of(char), (1, -1, -1))
        self.assertTrue(run.debug)
        self.assertNotIn(SUCCESS, run.mes)
        self.assertIn("可以稍後再和我說話。", run.mes, "reported as retryable")
        char.faults.clear()
        Run(char, lines=script_lines(EDGE, 0)).execute()
        self.assertEqual(tuple_of(char), (2, 1, -1))
        self.assertEqual(char.writes, [("completequest", ENTRY)] + EDGE_WRITES)

    def test_setquest_noop_leaves_protected_partial(self):
        char, run = messenger(200, {ENTRY: ACTIVE}, faults={("setquest", SECOND)})
        self.assertEqual(char.writes, EDGE_WRITES)
        self.assertEqual(tuple_of(char), (2, -1, -1))
        self.assertTrue(run.debug)
        self.assertNotIn(SUCCESS, run.mes)
        self.assertIn("紀錄只更新了一半。", run.mes, "reported as an interrupted edge")
        char.faults.clear()
        for _ in range(2):  # revisits never repair, at the Messenger or the starter
            Run(char, lines=script_lines(EDGE, 0)).execute()
            Run(Character(0), [1]).execute()
            char.level = 250
            r = Run(char, [1, 1])
            r.execute()
            self.assertTrue(r.debug)
        self.assertEqual(char.writes, EDGE_WRITES)
        self.assertEqual((tuple_of(char), char.warps), ((2, -1, -1), []))

    def test_interference_after_each_write_stops(self):
        changes = (set_quest(THIRD, ACTIVE), set_quest(ENTRY, None), set_quest(ENTRY, 7),
                   set_quest(SECOND, COMPLETE), set_quest(THIRD, 0))
        for change in changes:
            char, run = messenger(200, {ENTRY: ACTIVE},
                                  on_write=after_write("completequest", change))
            self.assertEqual(char.writes, [("completequest", ENTRY)])
            self.assertTrue(run.debug)
            self.assertNotIn(SUCCESS, run.mes)
            char, run = messenger(200, {ENTRY: ACTIVE},
                                  on_write=after_write("setquest", change))
            self.assertEqual(char.writes, EDGE_WRITES)
            self.assertTrue(run.debug)
            self.assertNotIn(SUCCESS, run.mes)
        # Another interaction finishing the edge in between is also a hold, not success.
        char, run = messenger(200, {ENTRY: ACTIVE}, on_write=after_write(
            "completequest", set_quest(SECOND, ACTIVE)))
        self.assertEqual(char.writes, [("completequest", ENTRY)])
        self.assertNotIn(SUCCESS, run.mes)

    def test_dialogue_yield_rechecks(self):
        changes = (set_quest(ENTRY, COMPLETE), set_quest(SECOND, ACTIVE),
                   set_quest(THIRD, COMPLETE), set_quest(ENTRY, None), set_quest(ENTRY, 0))
        for change in changes:
            char, run = messenger(200, {ENTRY: ACTIVE}, on_yield=perturb(1, change))
            self.assertEqual(char.writes, [])
            self.assertNotIn(SUCCESS, run.mes)
        # A level change is not a Messenger gate; an inactive toggle keeps the tuple.
        for change in (set_level(1), set_quest(ENTRY, INACTIVE)):
            char, run = messenger(200, {ENTRY: ACTIVE}, on_yield=perturb(1, change))
            self.assertEqual(char.writes, EDGE_WRITES)


# --------------------------------------------- G3: connections

class ConnectionTests(unittest.TestCase):
    def test_return_gate_only_warps(self):
        lines = script_lines(EDGE, 1)
        for combo, quests in combos():
            char = Character(1, quests)
            run = Run(char, lines=lines)
            run.execute(run.labels["OnTouch"] + 1)
            self.assertEqual((char.writes, char.warps), ([], [TOWN_DEST]), combo)
            self.assertEqual(char.guarded(), quests)
        char = Character(1)
        Run(char, lines=lines).execute()  # clicking the gate does nothing
        self.assertEqual((char.writes, char.warps), ([], []))

    def test_warps_are_unconditional_routes(self):
        decls = declarations(EDGE.read_text(encoding="utf-8"))
        warps = [(d[0], d[3]) for d in decls if d[1] == "warp"]
        self.assertEqual(len(warps), 2)
        for _, w4 in warps:
            self.assertEqual(len(w4.split(",")), 5)  # no body, no condition


# --------------------------------------------- controls: the checks bite

class MutationControlTests(unittest.TestCase):
    """Edited copies of the real text must fail the same contract checks."""

    def mutate(self, path, old, new, index=0, count=1):
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text, "mutation target must exist")
        return script_lines(path, index, text.replace(old, new, count))

    def test_missing_completequest_readback_would_write_b(self):
        text = EDGE.read_text(encoding="utf-8")
        start = text.index("\tcompletequest 18368;\n") + len("\tcompletequest 18368;\n")
        end = text.index("\tsetquest 18369;\n")
        self.assertIn("goto L_NotCompleted;", text[start:end])
        lines = script_lines(EDGE, 0, text[:start] + text[end:])  # drop reads and checks
        char, run = messenger(200, {ENTRY: ACTIVE}, faults={("completequest", ENTRY)}, lines=lines)
        self.assertNotEqual(char.writes, [("completequest", ENTRY)], "control must differ")
        self.assertEqual(tuple_of(char), (1, 1, -1))

    def test_partial_precondition_would_admit_active_active(self):
        lines = self.mutate(EDGE, "if (.@a != 1 || .@b != -1 || .@c != -1) goto L_Other;",
                            "if (.@a != 1) goto L_Other;")
        self.assertIn("if (.@a != 1 || .@b != -1 || .@c != -1) goto L_Changed;", lines)
        lines = [l.replace(" || .@b != -1 || .@c != -1", "") for l in lines]
        char, run = messenger(200, {ENTRY: ACTIVE, SECOND: ACTIVE}, lines=lines)
        self.assertTrue(char.writes, "control must differ from the real file")

    def test_partial_final_postcondition_would_claim_success(self):
        lines = self.mutate(EDGE, "if (.@a != 2 || .@b != 1 || .@c != -1) goto L_Hold;",
                            "if (.@b != 1) goto L_Hold;")
        char, run = messenger(200, {ENTRY: ACTIVE}, lines=lines,
                              on_write=after_write("setquest", set_quest(THIRD, ACTIVE)))
        self.assertIn(SUCCESS, run.mes, "control must differ from the real file")

    def test_missing_close2_recheck_would_warp(self):
        text = NPC.read_text(encoding="utf-8")
        old = "\tif (.@state != .@want) goto L_Stale;\n\tif (BaseLevel < 200) goto L_Stale;\n"
        self.assertIn(old, text)
        lines = script_lines(NPC, 0, text.replace(old, ""))
        char, run = talk(200, choices=[1, 1], lines=lines, on_yield=perturb(5, set_level(199)))
        self.assertEqual(char.warps, [FIRST_DEST], "control must differ from the real file")

    def test_unsupported_command_fails_loudly(self):
        lines = self.mutate(EDGE, "\tcompletequest 18368;\n", "\tgetitem 501,1;\n")
        with self.assertRaises(AssertionError):
            messenger(200, {ENTRY: ACTIVE}, lines=lines)

    def test_malformed_debugmes_is_rejected(self):
        lines = script_lines()
        for invalid in ("debugmes root_unknown();", 'debugmes "unterminated"'):
            changed = [invalid if line.startswith("debugmes ") else line for line in lines]
            with self.assertRaisesRegex(AssertionError, "unsupported debugmes form"):
                talk(200, {ENTRY: COMPLETE}, lines=changed)

    def test_unsupported_oninit_command_is_rejected(self):
        for path in NPC_FILES:
            lines = script_lines(path, 0)
            index = lines.index("OnInit:") + 1
            changed = lines[:index] + ["root_unknown_command;"] + lines[index:]
            with self.assertRaisesRegex(AssertionError, "unsupported OnInit form"):
                Run(Character(200), lines=changed)

    def test_malformed_oninit_questinfo_is_rejected(self):
        for path in NPC_FILES:
            lines = script_lines(path, 0)
            changed = [line[:-1] if line.startswith("questinfo(") else line for line in lines]
            with self.assertRaisesRegex(AssertionError, "unsupported OnInit form"):
                Run(Character(200), lines=changed)


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    unittest.main(verbosity=2)
