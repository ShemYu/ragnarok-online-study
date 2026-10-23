"""Own-source checks for the ro-solo-ch1-entry mod (T10.007).

Run: python3 -I -B tools/renewal/test_chapter1_entry.py

Two kinds of check, both on the committed files only:

- static: package layout, mod.json fields, QUEST_DB shape, UTF-8, audited
  title bytes, forbidden-command/word checks and the NPC header line;
- modeled: a small authored interpreter for the subset of rAthena script the
  real entry.txt uses, run against that file with a modeled quest log. The
  model follows the pinned rAthena 0693b8c quest_check/quest_add excerpts
  (inactive reported as 1; setquest returns success even when quest_add fails).
  It is a model: it proves nothing about the real parser, char-server
  persistence, relog or the client. Those remain Root integration gates.
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
# A long client Description sentence fragment; the NPC must not copy prose.
DESCRIPTION_FRAGMENTS = ("雖然令人難以置信", "接受守護精靈的引導", "觸碰梧桐樹後", "莎莎", "梅雪")

ABSENT, INACTIVE, ACTIVE, COMPLETE = None, 0, 1, 2  # modeled stored quest state


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


def script_lines():
    text = NPC.read_text(encoding="utf-8")
    start = text.index(",{\n") + 3
    end = text.rindex("\n}")
    return [strip_comment(l).strip() for l in text[start:end].split("\n")]


# ---------------------------------------------------------------- the model

class Character:
    """Modeled quest log of one character, per pinned quest.cpp semantics."""

    def __init__(self, level, quests=None, add_fails=False):
        self.level = level
        self.quests = dict(quests or {})
        self.add_fails = add_fails  # e.g. quest missing from the loaded DB
        self.writes = []

    def checkquest(self, qid):
        state = self.quests.get(qid)
        if state is None:
            return -1
        return 1 if state == INACTIVE else state

    def setquest(self, qid):
        self.writes.append(("setquest", qid))
        if self.add_fails or qid in self.quests:
            return  # quest_add returned -1; the script command still succeeds
        self.quests[qid] = ACTIVE


class Run:
    """Interprets the line-oriented subset of rAthena script entry.txt uses."""

    def __init__(self, char, choice, on_yield=None):
        self.char, self.choice, self.on_yield = char, choice, on_yield
        self.lines = script_lines()
        self.labels = {l[:-1]: i for i, l in enumerate(self.lines)
                       if re.fullmatch(r"[A-Za-z_]\w*:", l)}
        self.mes, self.debug, self.menus, self.yields = [], [], 0, 0
        self.closed = False

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
            self.yield_()
            return self.choice
        if name == "callsub":
            return self.execute(self.labels[arg.strip()] + 1, {})
        raise AssertionError(name)

    def yield_(self):
        self.yields += 1
        if self.on_yield:
            self.on_yield(self, self.char)

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
            self.mes.append(m.group(1))
            return None
        if line == "next;":
            self.yield_()
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
        m = re.fullmatch(r"setquest (\d+);", line)
        if m:
            self.char.setquest(int(m.group(1)))
            return None
        if line.startswith("debugmes "):
            self.debug.append(line)
            return None
        raise AssertionError(f"unmodeled statement: {line}")


def talk(level, quests=None, choice=1, on_yield=None, add_fails=False):
    char = Character(level, quests, add_fails)
    run = Run(char, choice, on_yield)
    run.execute()
    assert run.closed
    return char, run


def expected_class(a, b, c):
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
    return "preserved"


STATE_CODE = {"fresh": 0, "resume": 1, "preserved": 2, "conflict": 3}


# ---------------------------------------------------------------- A: package

class PackageTests(unittest.TestCase):
    def test_owned_files_only(self):
        found = sorted(p.relative_to(MOD).as_posix() for p in MOD.rglob("*") if p.is_file())
        self.assertEqual(found, ["db/quest_db.yml", "mod.json", "npc/entry.txt"])

    def test_mod_json(self):
        m = json.loads(MOD_JSON.read_text(encoding="utf-8"))
        self.assertEqual(m["name"], MOD.name)
        for key in ("version", "author", "description"):
            self.assertTrue(m[key].strip(), key)
        self.assertEqual(m["requires"], {"app": ">=1.6.3", "era": "renewal"})
        self.assertNotIn("client", m["requires"])

    def test_utf8_lf_no_bom(self):
        for path in (MOD_JSON, NPC, QUEST_DB):
            raw = path.read_bytes()
            raw.decode("utf-8")
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), path)
            self.assertNotIn(b"\r", raw, path)
            self.assertTrue(raw.endswith(b"\n"), path)

    def test_npc_header_line(self):
        heads = [l for l in NPC.read_text(encoding="utf-8").split("\n")
                 if l and not l.startswith("//")][:1]
        parts = heads[0].split("\t")
        self.assertEqual(parts[0], "prt_fild05,353,252,4")
        self.assertEqual(parts[1], "script")
        self.assertEqual(parts[3], "4_CH1_BRANCH,{")
        display, _, hidden = parts[2].partition("#")
        self.assertTrue(hidden.upper().startswith("ROSOLO_CH1"))
        # rAthena NAME_LENGTH is 24 including the terminator.
        self.assertLessEqual(len(parts[2].encode("utf-8")), 23)
        self.assertEqual(sum(1 for l in NPC.read_text(encoding="utf-8").split("\n")
                             if "\tscript\t" in l), 1, "exactly one NPC")

    def test_braces_balance(self):
        body = "\n".join(script_lines())
        depth = 0
        for ch in re.sub(r'"[^"]*"', "", body):
            depth += {"{": 1, "}": -1}.get(ch, 0)
            self.assertGreaterEqual(depth, 0)
        self.assertEqual(depth, 0)


# ------------------------------------------------------------ D: text and DB

class QuestDbTests(unittest.TestCase):
    def setUp(self):
        self.lines = [l for l in QUEST_DB.read_text(encoding="utf-8").split("\n")
                      if l.strip() and not l.lstrip().startswith("#")]

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

    def test_npc_text_reuses_short_log_text_only(self):
        mes = re.findall(r'"([^"]*)"', NPC.read_text(encoding="utf-8"))
        title = next(t for t in re.findall(r"「(.+?)」", "".join(mes)))
        self.assertEqual(sha(title), TITLE_SHA256[ENTRY])
        objectives = [s.split("：", 1)[1] for s in mes if s.startswith("目標：")]
        self.assertTrue(objectives)
        self.assertTrue(all(sha(o) == ENTRY_SUMMARY_SHA256 for o in objectives))
        text = NPC.read_text(encoding="utf-8")
        for fragment in DESCRIPTION_FRAGMENTS:
            self.assertNotIn(fragment, text)
        for line in script_lines():
            m = re.fullmatch(r'mes "(.*)";', line)
            if m:
                self.assertLessEqual(len(m.group(1)), 24, m.group(1))

    def test_menu_is_plain_chinese(self):
        options = re.findall(r'select\("([^"]*)"\)', NPC.read_text(encoding="utf-8"))
        self.assertEqual(len(options), 1)
        for option in options[0].split(":"):
            self.assertIsNone(re.search(r"[A-Za-z0-9_#]", option), option)


# ------------------------------------------------- C: static state discipline

class ScriptDisciplineTests(unittest.TestCase):
    def setUp(self):
        self.code = "\n".join(re.sub(r'"[^"]*"', '""', l) for l in script_lines())

    def test_only_mutation_is_one_setquest_entry(self):
        self.assertEqual(re.findall(r"\bsetquest\s+(\d+)", self.code), [str(ENTRY)])
        forbidden = ("completequest", "erasequest", "changequest", "warp", "getitem",
                     "delitem", "getexp", "Zeny", "set ", "setarray", "cleararray",
                     "callfunc", "donpcevent", "doevent", "addtimer", "sleep", "input",
                     "isbegin_quest", "getvariableofnpc", "query_sql", "atcommand",
                     "unitwarp", "jobchange", "resetlvl", "savepoint")
        for word in forbidden:
            self.assertNotIn(word, self.code, word)

    def test_only_guarded_ids(self):
        ids = set(re.findall(r"\b\d{4,}\b", NPC.read_text(encoding="utf-8")))
        self.assertLessEqual(ids, {str(i) for i in GUARDED})
        self.assertNotIn("18371", ids)
        self.assertNotIn("24069", ids)

    def test_variables_are_scope_only(self):
        assigned = re.findall(r"^\s*([^\s=]+)\s*=[^=]", self.code, re.M)
        self.assertTrue(assigned)
        for name in assigned:
            self.assertTrue(name.startswith(".@"), name)
        for prefix in (r"(?<![.\w])@\w", r"\$\w", r"#\w", r"(?<!@)\.(?!@)\w", r"'\w"):
            self.assertIsNone(re.search(prefix, self.code.replace("4_CH1", "")), prefix)

    def test_checkquest_comparisons_are_explicit(self):
        """Read into a .@ variable, compared with ==/!=, or logged; no truthiness."""
        for line in script_lines():
            plain = re.sub(r'"[^"]*"', '""', line)
            if line.startswith(("debugmes", "questinfo")):
                continue
            for m in re.finditer(r"checkquest\(\d+\)", plain):
                head, tail = plain[:m.start()], plain[m.end():]
                direct = re.fullmatch(r"\.@\w+ = ", head) and tail == ";"
                self.assertTrue(direct or re.match(r"\s*(==|!=) -?[12]\b", tail), line)
            self.assertIsNone(re.search(r"\.@\w+\s*(\)|&&|\|\|)", plain), line)
            self.assertIsNone(re.search(r"(\.@[abc]|checkquest\(\d+\))\s*(==|!=|<|>|<=|>=)\s*0\b",
                                        plain), "inactive-as-0: " + line)

    def test_setquest_after_recheck_without_yield(self):
        lines = script_lines()
        i_set = next(i for i, l in enumerate(lines) if l.startswith("setquest"))
        i_sel = next(i for i, l in enumerate(lines) if "select(" in l)
        rechecks = [i for i, l in enumerate(lines) if "callsub(L_State)" in l]
        self.assertTrue(any(i_sel < i < i_set for i in rechecks))
        self.assertTrue(any(i_sel < i < i_set and "BaseLevel < 200" in l
                            for i, l in enumerate(lines)))
        between = lines[max(i for i in rechecks if i < i_set):i_set]
        self.assertFalse(any(re.match(r"(next|select|menu|sleep|input)\b", l) for l in between))
        after = lines[i_set + 1:i_set + 3]
        self.assertTrue(any("checkquest(18368)" in l for l in after), "postcondition read-back")


# --------------------------------------------- B/C: modeled interaction runs

class ModeledInteractionTests(unittest.TestCase):
    def test_fresh_level_gate(self):
        for level, choice in itertools.product((1, 199), (1, 2)):
            char, run = talk(level, choice=choice)
            self.assertEqual((char.quests, char.writes, run.menus), ({}, [], 0), level)
        for level in (200, 201, 275):
            char, run = talk(level, choice=1)
            self.assertEqual(char.quests, {ENTRY: ACTIVE})
            self.assertEqual(char.writes, [("setquest", ENTRY)])
            self.assertEqual(run.menus, 1)

    def test_cancel_changes_nothing_and_retry_registers_once(self):
        char = Character(200)
        Run(char, choice=2).execute()
        self.assertEqual((char.quests, char.writes), ({}, []))
        Run(char, choice=1).execute()
        Run(char, choice=1).execute()  # second visit resumes
        self.assertEqual(char.quests, {ENTRY: ACTIVE})
        self.assertEqual(char.writes, [("setquest", ENTRY)])

    def test_post_menu_recheck(self):
        def drop_level(run, char):
            if run.menus:
                char.level = 199

        def appears(qid, state):
            def hook(run, char):
                if run.menus:
                    char.quests[qid] = state
            return hook

        char, run = talk(200, on_yield=drop_level)
        self.assertEqual((char.quests, char.writes), ({}, []))
        for qid, state in ((ENTRY, ACTIVE), (ENTRY, INACTIVE), (ENTRY, COMPLETE),
                           (SECOND, ACTIVE), (THIRD, COMPLETE)):
            char, run = talk(201, on_yield=appears(qid, state))
            self.assertEqual(char.writes, [], (qid, state))
            self.assertEqual(char.quests, {qid: state})

    def test_failed_registration_is_reported_and_retryable(self):
        char, run = talk(200, add_fails=True)
        self.assertEqual(char.quests, {})
        self.assertEqual(char.writes, [("setquest", ENTRY)])
        self.assertTrue(run.debug)
        self.assertNotIn("任務「天地樹的召喚(1)」已記錄。", run.mes)
        char.add_fails = False
        Run(char, choice=1).execute()
        self.assertEqual(char.quests, {ENTRY: ACTIVE})

    def test_resume_active_and_inactive_at_any_level(self):
        for state, level in itertools.product((ACTIVE, INACTIVE), (150, 199, 200, 201)):
            char, run = talk(level, {ENTRY: state})
            self.assertEqual(char.writes, [])
            self.assertEqual(char.quests, {ENTRY: state}, "inactive is not reset")
            self.assertEqual(run.menus, 0)
            self.assertIn("目標：前往梧桐村", run.mes)

    def test_every_combination(self):
        """All stored states incl. unknown, x levels x menu choice."""
        stored = (ABSENT, INACTIVE, ACTIVE, COMPLETE, 7)
        for combo in itertools.product(stored, repeat=3):
            quests = {q: s for q, s in zip(GUARDED, combo) if s is not None}
            seen = tuple(Character(0, quests).checkquest(q) for q in GUARDED)
            want = expected_class(*seen)
            probe = Run(Character(200, quests), 1)
            self.assertEqual(probe.execute(probe.labels["L_State"] + 1, {}),
                             STATE_CODE[want], combo)
            for level, choice in itertools.product((199, 200, 201), (1, 2)):
                char, run = talk(level, quests, choice)
                registers = want == "fresh" and level >= 200 and choice == 1
                self.assertEqual(char.writes, [("setquest", ENTRY)] if registers else [],
                                 (combo, level, choice))
                self.assertEqual(char.quests,
                                 {ENTRY: ACTIVE} if registers else quests, (combo, level))
                self.assertEqual(bool(run.debug), want == "conflict", combo)

    def test_characters_are_independent(self):
        one, two = Character(200), Character(200, {ENTRY: COMPLETE})
        Run(one, 1).execute()
        Run(two, 1).execute()
        self.assertEqual(one.quests, {ENTRY: ACTIVE})
        self.assertEqual(two.quests, {ENTRY: COMPLETE})
        self.assertEqual(two.writes, [])


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    unittest.main(verbosity=2)
