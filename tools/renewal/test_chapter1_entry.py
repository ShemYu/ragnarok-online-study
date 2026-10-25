"""Own-source checks for the ro-solo-ch1-entry mod (T10.007, T10.009, T10.010,
T10.010.001, T10.010.002).

Run: python3 -I -B tools/renewal/test_chapter1_entry.py

Two kinds of check, both on the committed files only:

- static: package layout, mod.json fields, QUEST_DB shape and bytes,
  UTF-8, audited title/objective bytes, forbidden-command/word checks,
  NPC/warp declaration lines and the ordering of reads, writes and yields;
- modeled: a small authored interpreter for the subset of rAthena script the
  real entry.txt, first_edge.txt and fruit_village.txt use, run against
  those files with a modeled quest log, inventory and per-character NPC
  masks. The model follows the pinned rAthena 0693b8c excerpts (inactive
  reported as 1; setquest, completequest and changequest return success
  even when nothing changed; quest_change replaces the source with an active
  destination and refuses a missing DB row, present destination or missing
  or completed source). The inventory is a finite list of native-shaped
  rows (nameid, amount, bound, expiry, unique ID, cards) with a usable-slot
  count and inaccessible indices beyond it: countitem/rentalcountitem sum
  every positive same-ID row with zero/positive expiry (script_countitem_sub);
  checkweight tests weight, then the FIRST same-ID row only, or a usable
  blank (pc_checkadditem, pc_inventoryblank); getitem only merges into a
  row with matching bound, zero expiry, unique ID and cards, else needs the
  first blank inside the usable slots (pc_additem). So the native check and
  the actual add are distinct and can disagree; ros_ch1_coin_capacity()
  (T10.010.002) is that add evaluated on a copy, or a forced 0/-1 value
  (the native body is checked by native_capacity/test_coin_capacity.py); character cloak entries invert the global
  cloak and are cleared on map change; close2 waits for the button and the
  script continues). Fault hooks make a write a no-op, change the log after
  a write, or change state or quit at any yield. Mutation controls edit a
  copy of the real text and confirm the same checks catch a missing readback,
  recheck, preflight, delivery check, legacy checkweight AND or truthy -1.
  It is a model: it proves nothing about the real parser, char-server
  persistence, relog, map cells, arrival, item/EXP delivery, rendering or
  the client. Those remain Root integration gates.
"""

import copy
import functools
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
FRUIT = MOD / "npc" / "fruit_village.txt"
INHERITED_NPC = (NPC, EDGE)
NPC_FILES = (NPC, EDGE, FRUIT)
QUEST_DB = MOD / "db" / "quest_db.yml"
MOD_JSON = MOD / "mod.json"
PROFILE = HERE.parent.parent / "docs" / "project" / "fixtures" / "T10.010-profile.json"

ENTRY, SECOND, THIRD, FOURTH = 18368, 18369, 18370, 18371
GUARDED = (ENTRY, SECOND, THIRD, FOURTH)
# UTF-8 SHA-256 of the Big5-decoded client quest-log fields: rows 37/73/114
# from the frozen T10.007 packet, row 150 (18371) from the T10.010 packet
# (reference/four-quest-records.json).
TITLE_SHA256 = {
    ENTRY: "a71c099afc2f2439f8b1a39944fd2424a2efeb99d4f24715f470bbdaa940ba12",
    SECOND: "cdef2c43bd2100a0194eafc67036410906fb93a69571026be44c0e4619c7e46e",
    THIRD: "c110a8a52040a7ad5345cc3503b694548af8f9bb38523769bfcd9184102c6e36",
    FOURTH: "e2daadf50038d2878e4bc87abfc16eb249cc5ad3fc9a549ea58677675a89c4e3",
}
SUMMARY_SHA256 = {
    ENTRY: "2bbdf105102f7663b88da765fc5c3dc112e438a11bc6a837f086c8b650f47124",
    SECOND: "7721b04586c508490b947e1598590daad3c16fb6aa2d05e32ab192bc30ce7fbe",
    THIRD: "ada64123eb02d110dbb3c39020b9fda05f2445730590960dda5f29c1eb1e5246",
    FOURTH: "72cde7aa5d58a17969e96a6307c5651206324932a89c08df9351dfc804d32121",
}
ENTRY_SUMMARY_SHA256 = SUMMARY_SHA256[ENTRY]
# T10.010 appends the 18371 row; the three inherited rows stay byte-identical.
QUEST_DB_SHA256 = "2a1b0b0ee1588240e9845b68146226e21545d09bf7b2c99217069aa37bced23f"
INHERITED_ROWS = ("  - Id: 18368\n    Title: 天地樹的召喚(1)\n"
                  "  - Id: 18369\n    Title: 天地樹的召喚(2)\n"
                  "  - Id: 18370\n    Title: 天地樹的召喚(3)\n")
# Long client Description fragments; the NPCs must not copy that prose.
DESCRIPTION_FRAGMENTS = ("雖然令人難以置信", "接受守護精靈的引導", "觸碰梧桐樹後",
                         "很快就返回去邀請", "聽了各式各樣的故事", "決定親自前往確認")

FIRST_DEST = ("ygg_edge", 255, 240)
REPEAT_DEST = ("ygg_edge", 212, 95)
PAYON_DEST = ("ygg_edge", 194, 97)
TOWN_DEST = ("prt_fild05", 353, 248)

ARRIVAL = "#ROSOLO_CH1_ARR"
SHASHA = "莎莎#ROSOLO_CH1_SHA"
MAYSEL = "梅雪#ROSOLO_CH1_MAY"
EST = "Est#ROSOLO_CH1_EST"
DEBRIS = "Debris#ROSOLO_CH1_DEB"
ACTORS = (MAYSEL, EST, DEBRIS)

# Maysel's source-bound native reward (chapter1.txt 625-626) and the item
# row it resolves to (item-1001972.yml.excerpt): ID 1001972, weight 1.
BASE_EXP, JOB_EXP = 65304744, 4000000
COIN, COIN_ID, COIN_WEIGHT, COIN_COUNT = "Ch1_Root_Coin", 1001972, 1, 10
# Modeled stack bound for the existing-stack OVERAMOUNT refusal. The real
# bound (MAX_AMOUNT / item stack) is a native/resource fact for Root.
STACK_CAP = 30000
NO_CARDS = (0, 0, 0, 0)

# Modeled stored quest state. Any other int is stored raw and returned as-is
# by checkquest, so 0, 3 or 7 model an unknown value.
ABSENT, INACTIVE, ACTIVE, COMPLETE = None, "inactive", 1, 2
STORED = (ABSENT, INACTIVE, ACTIVE, COMPLETE, 0, 7)
# Genuinely unrelated sentinels. 18371 was one before T10.010; it is now D.
UNRELATED = {1000: COMPLETE, 7128: ACTIVE, 18372: INACTIVE, 18378: ACTIVE}

STAGE_A = {ENTRY: ACTIVE}
STAGE_B = {ENTRY: COMPLETE, SECOND: ACTIVE}
STAGE_C = {ENTRY: COMPLETE, THIRD: ACTIVE}
STAGE_D = {ENTRY: COMPLETE, FOURTH: ACTIVE}
PARTIAL = {ENTRY: COMPLETE}


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


@functools.lru_cache(maxsize=None)
def file_declarations(path):
    return declarations(path.read_text(encoding="utf-8"))


def script_lines(path=NPC, index=0, text=None):
    decls = file_declarations(path) if text is None else declarations(text)
    return list([d for d in decls if d[1] == "script"][index][4])


def fruit_lines(name, text=None):
    decls = file_declarations(FRUIT) if text is None else declarations(text)
    return list(next(d[4] for d in decls if d[2] == name))


@functools.lru_cache(maxsize=None)
def quest_db_ids():
    return frozenset(int(m) for m in re.findall(r"^  - Id: (\d+)$",
                                                QUEST_DB.read_text(encoding="utf-8"), re.M))


def tuple_of(char):
    return tuple(char.checkquest(q) for q in GUARDED)


def validate_oninit_form(lines):
    """Only check OnInit's supported forms; do not execute the bubble condition."""
    if "OnInit:" not in lines:
        return
    tail = [line for line in lines[lines.index("OnInit:") + 1:] if line]
    if tail == ["cloakonnpc;", "end;"]:
        return
    if (len(tail) != 2 or tail[1] != "end;" or not re.fullmatch(
            r'questinfo\(QTYPE_QUEST, QMARK_YELLOW, "[^"\n]+"\);', tail[0])):
        raise AssertionError("unsupported OnInit form")


# ---------------------------------------------------------------- the model

class World:
    """NPC global cloak options plus the characters on the modeled server."""

    def __init__(self):
        self.cloaked = dict(initial_cloaks())
        self.chars = {}
        self.calls = []  # (command, npc, char_id) for every cloak request

    def visible(self, npc, char):
        cloaked = self.cloaked[npc]
        if npc in char.mask:  # npc_is_cloaked: membership inverts the option
            cloaked = not cloaked
        return not cloaked

    def cloak_target(self, npc, char_id, on, cmd):
        """npc_enable_target with a char_id: idempotent for the requested state."""
        if npc not in self.cloaked:
            raise AssertionError(f"cloak target not declared: {npc}")
        self.calls.append((cmd, npc, char_id))
        char = self.chars.get(char_id)
        if char is None:
            return  # native ShowError + SCRIPT_CMD_FAILURE; nothing changes
        option = self.cloaked[npc]
        if npc not in char.mask and option != on:
            char.mask.add(npc)
        elif npc in char.mask and option == on:
            char.mask.discard(npc)

    def cloak_global(self, npc, on):
        """Option change on the NPC itself: everyone's entries for it are removed."""
        self.calls.append(("global", npc, on))
        self.cloaked[npc] = on
        for char in self.chars.values():
            if char.map == "ygg_fruit":
                char.mask.discard(npc)


@functools.lru_cache(maxsize=None)
def _initial_cloaks():
    """Run every fruit_village.txt OnInit that uses the cloak form."""
    world = World.__new__(World)
    world.cloaked = {d[2]: False for d in file_declarations(FRUIT) if d[1] == "script"}
    world.chars, world.calls = {}, []
    for _, kind, name, _, body in file_declarations(FRUIT):
        if kind == "script" and "OnInit:" in body and "cloakonnpc;" in body:
            run = Run(None, lines=list(body), npc=name, world=world)
            run.execute(run.labels["OnInit"] + 1)
    return tuple(sorted(world.cloaked.items()))


def initial_cloaks():
    return _initial_cloaks()


def row(nameid=COIN_ID, amount=1, bound=0, expire=0, unique=0, card=0):
    """One native inventory row; card marks the first card slot."""
    return {"nameid": nameid, "amount": amount, "bound": bound, "expire": expire,
            "unique": unique, "card": (card, 0, 0, 0)}


class Character:
    """Modeled quest log, inventory and NPC mask of one character."""

    _next_id = 150001

    def __init__(self, level, quests=None, add_fails=False, faults=(), world=None,
                 map="ygg_fruit", coins=0, weight=100, max_weight=1000, free_slots=10,
                 item_db=True, db_ids=None, coin_rows=(), hidden_rows=(), hidden_blanks=0,
                 stack_limit=None, capacity=None):
        self.level = level
        self.quests = dict(UNRELATED)
        self.quests.update(quests or {})
        self.add_fails = add_fails  # e.g. quest missing from the loaded DB
        self.faults = set(faults)  # (command, arg) that silently does nothing
        self.zeny, self.exp = 12345, 678
        # Usable slots: filler 501, coin rows, then blanks. Indices at or beyond
        # inventory_slots exist in the array but are not usable (MAX_INVENTORY).
        rows = [row(501, 3)] + ([row(amount=coins)] if coins else [])
        self.inv = rows + [dict(r) for r in coin_rows] + [None] * free_slots
        self.inventory_slots = len(self.inv)
        self.inv += [dict(r) for r in hidden_rows] + [None] * hidden_blanks
        self.stack_limit = stack_limit  # item DB Stack.Inventory amount, if any
        # ros_ch1_coin_capacity() override: None derives it from the add model;
        # -1 models an unsupported actor/alias/configuration (or any int forced).
        self.capacity = capacity
        self.probes = 0
        self.weight, self.max_weight = weight, max_weight
        self.start_inv, self.start_weight = copy.deepcopy(self.inv), weight
        self.start_coins = self.coins()
        self.item_db = item_db  # alias resolvable in the loaded item DB
        self.db_ids = quest_db_ids() if db_ids is None else frozenset(db_ids)
        self.writes, self.warps, self.exp_calls = [], [], []
        self.char_id = Character._next_id
        Character._next_id += 1
        self.map, self.mask = map, set()
        self.world = world or World()
        self.world.chars[self.char_id] = self

    def guarded(self):
        return {q: s for q, s in self.quests.items() if q in GUARDED}

    @property
    def items(self):
        out = {}
        for r in self.inv:
            if r:
                out[r["nameid"]] = out.get(r["nameid"], 0) + r["amount"]
        return out

    @property
    def free_slots(self):
        return self.inv[:self.inventory_slots].count(None)  # pc_inventoryblank

    def coins(self):
        """Every coin row regardless of metadata or index (for sentinels)."""
        return self.items.get(COIN_ID, 0)

    def expand(self):
        """One more usable blank slot (the player made room)."""
        self.inv.insert(self.inventory_slots, None)
        self.inventory_slots += 1

    def move(self, map_name):
        """pc_setpos: a different map clears the character's cloak entries."""
        if map_name != self.map:
            self.mask.clear()
        self.map = map_name

    def relog(self):
        self.mask.clear()  # session memory only (pc.hpp cloaked_npc)

    def checkquest(self, qid):
        state = self.quests.get(qid)
        if state is None:
            return -1
        return 1 if state == INACTIVE else state

    def setquest(self, qid):
        self.writes.append(("setquest", qid))
        if (self.add_fails or ("setquest", qid) in self.faults or qid in self.quests
                or qid not in self.db_ids):
            return  # quest_add returned -1; the script command still succeeds
        self.quests[qid] = ACTIVE

    def completequest(self, qid):
        self.writes.append(("completequest", qid))
        if ("completequest", qid) in self.faults:
            return
        # quest_update_status only finds active or inactive records.
        if self.quests.get(qid) in (ACTIVE, INACTIVE):
            self.quests[qid] = COMPLETE

    def changequest(self, old, new):
        """quest_change: refusals return -1 before any mutation."""
        self.writes.append(("changequest", old, new))
        if ("changequest", old) in self.faults or new not in self.db_ids:
            return
        if new in self.quests or old not in self.quests:
            return
        if self.quests[old] not in (ACTIVE, INACTIVE):
            return  # completed source is outside the unfinished prefix
        del self.quests[old]
        self.quests[new] = ACTIVE

    def over(self, amount, have=0):
        limit = self.stack_limit
        return amount > STACK_CAP - have or (limit is not None and amount > limit - have)

    def checkadditem(self, amount):
        """pc_checkadditem: the first same-ID row decides; metadata ignored."""
        if self.over(amount):
            return "overamount"
        for i, r in enumerate(self.inv):
            if r and r["nameid"] == COIN_ID:
                if self.over(amount, r["amount"]) or i >= self.inventory_slots:
                    return "overamount"
                return "exist"
        return "new"

    def checkweight(self, alias, amount):
        if alias != COIN or not self.item_db or amount < 1:
            return 0  # invalid item/amount: pushes 0 and reports failure
        if self.weight + COIN_WEIGHT * amount > self.max_weight:
            return 0
        result = self.checkadditem(amount)
        if result == "new":
            return 1 if self.free_slots >= 1 else 0
        return 1 if result == "exist" else 0

    def coin_capacity(self):
        """ros_ch1_coin_capacity(): read-only; 1 iff the add model would succeed.

        The native oracle is the C++ differential (native_capacity/); here the
        inherited add model is evaluated on a copy, so nothing changes."""
        self.probes += 1
        if self.capacity is not None:
            return self.capacity
        if not self.item_db:
            return -1
        trial = copy.copy(self)
        trial.inv = copy.deepcopy(self.inv)
        return 1 if Character.additem(trial, COIN_COUNT) else 0

    def countitem(self, alias, rental=False):
        """script_countitem_sub, non-expanded: all MAX_INVENTORY rows."""
        if alias != COIN:
            raise AssertionError("countitem of an unmodeled item")
        if not self.item_db:
            return 0  # invalid item: pushes 0 and reports failure
        return sum(r["amount"] for r in self.inv
                   if r and r["nameid"] == COIN_ID and r["amount"] >= 1
                   and ((r["expire"] > 0) if rental else (r["expire"] == 0)))

    def getexp(self, base, job):
        # Native rates, boosts, caps and level-ups decide the credited amount;
        # the model only records the call, it does not compute status deltas.
        self.writes.append(("getexp", base, job))
        self.exp_calls.append((base, job))

    def getitem(self, alias, amount):
        self.writes.append(("getitem", alias, amount))
        if alias != COIN or not self.item_db or ("getitem", alias) in self.faults:
            return False
        return self.additem(amount)

    def additem(self, amount):
        """pc_additem of an unbound, unexpiring, zero-unique, cardless coin.

        Any ADDITEM_* failure returns False: logged, the script continues."""
        if self.over(amount) or self.weight + COIN_WEIGHT * amount > self.max_weight:
            return False
        for i, r in enumerate(self.inv):
            if (r and r["nameid"] == COIN_ID and r["bound"] == 0 and r["expire"] == 0
                    and r["unique"] == 0 and r["card"] == NO_CARDS):
                if self.over(amount, r["amount"]) or i >= self.inventory_slots:
                    return False  # ADDITEM_OVERAMOUNT
                r["amount"] += amount
                break
        else:
            i = self.inv.index(None) if None in self.inv else -1  # pc_search_inventory(0)
            if i < 0 or i >= self.inventory_slots:
                return False  # ADDITEM_OVERITEM
            self.inv[i] = row(amount=amount)
        self.weight += COIN_WEIGHT * amount
        return True


class Quit(Exception):
    """The player closed the window or disconnected at a yield."""


class _End(Exception):
    pass


QUEST_ATOM = "|".join(str(q) for q in GUARDED)


class Run:
    """Interprets the line-oriented subset of rAthena script the mod uses."""

    def __init__(self, char, choices=1, on_yield=None, on_write=None, lines=None,
                 npc=None, world=None):
        self.char, self.on_yield, self.on_write = char, on_yield, on_write
        self.world = world or (char.world if char else None)
        self.npc = npc
        self.choices = list(choices) if isinstance(choices, (list, tuple)) else None
        self.choice = choices
        self.lines = script_lines() if lines is None else lines
        validate_oninit_form(self.lines)
        self.labels = {l[:-1]: i for i, l in enumerate(self.lines)
                       if re.fullmatch(r"[A-Za-z_]\w*:", l)}
        self.mes, self.debug, self.bottom, self.talk = [], [], [], []
        self.menus = self.yields = 0
        self.window = self.closed = self.warped = self.quit = False

    def expr(self, src, scope):
        def call(m):
            return self.call(m.group(1), m.group(2), scope)
        py = re.sub(r"\b(checkquest|callsub|select|getcharid|strcharinfo|checkweight|countitem"
                    r"|rentalcountitem|ros_ch1_coin_capacity)"
                    r"\(([^()]*)\)", lambda m: repr(call(m)), src)
        py = re.sub(r"\.@(\w+)", lambda m: repr(scope.get(m.group(1), 0)), py)
        py = py.replace("BaseLevel", repr(self.char.level) if self.char else "0")
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
            return self._exec(self.labels[arg.strip()] + 1, {})
        if name == "getcharid":
            if arg != "0":
                raise AssertionError("only getcharid(0) is modeled")
            return self.char.char_id
        if name == "strcharinfo":
            if arg != "3":
                raise AssertionError("only strcharinfo(3) is modeled")
            return self.char.map
        if name == "ros_ch1_coin_capacity":
            if arg != "":
                raise AssertionError("ros_ch1_coin_capacity takes no arguments")
            return self.char.coin_capacity()
        m = re.fullmatch(r'"(\w+)",(\d+)', arg)
        if name == "checkweight" and m:
            return self.char.checkweight(m.group(1), int(m.group(2)))
        m = re.fullmatch(r'"(\w+)"', arg)
        if name in ("countitem", "rentalcountitem") and m:
            return self.char.countitem(m.group(1), rental=name == "rentalcountitem")
        raise AssertionError(f"{name}({arg})")

    def yield_(self, kind):
        self.yields += 1
        if self.on_yield:
            self.on_yield(self, self.char, kind)

    def wrote(self, cmd, arg):
        if self.on_write:
            self.on_write(self, self.char, cmd, arg)

    def block_end(self, i):
        depth = 0
        for j in range(i, len(self.lines)):
            depth += self.lines[j].count("{") - self.lines[j].count("}")
            if depth == 0:
                return j
        raise AssertionError("unbalanced block")

    def execute(self, pc=0, scope=None):
        try:
            return self._exec(pc, scope)
        except _End:
            return None
        except Quit:
            self.quit = self.closed = True
            return None

    def _exec(self, pc=0, scope=None):
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
        m = re.fullmatch(r'select\("([^"]*)"\);', line)
        if m:
            if not self.window or self.closed:
                raise AssertionError("menu without an open dialog")
            self.call("select", m.group(1), scope)
            return None
        if line == "close2;":
            if not self.window or self.closed:
                raise AssertionError("close2 without a dialog would halt the script")
            self.window, self.closed = False, True
            self.yield_("close2")
            return None
        if line in ("close;", "end;"):
            self.closed = True
            raise _End
        m = re.fullmatch(r"goto (\w+);", line)
        if m:
            return ("goto", m.group(1))
        m = re.fullmatch(r"callsub (\w+);", line)
        if m:
            self._exec(self.labels[m.group(1)] + 1, {})
            return None
        m = re.fullmatch(r"return (-?\d+);", line)
        if m:
            return ("return", int(m.group(1)))
        if line == "return;":
            return ("return", None)
        m = re.fullmatch(r"(setquest|completequest) (\d+);", line)
        if m:
            getattr(self.char, m.group(1))(int(m.group(2)))
            self.wrote(m.group(1), int(m.group(2)))
            return None
        m = re.fullmatch(r"changequest (\d+),(\d+);", line)
        if m:
            self.char.changequest(int(m.group(1)), int(m.group(2)))
            self.wrote("changequest", int(m.group(1)))
            return None
        m = re.fullmatch(r"getexp (\d+),(\d+);", line)
        if m:
            self.char.getexp(int(m.group(1)), int(m.group(2)))
            self.wrote("getexp", int(m.group(1)))
            return None
        m = re.fullmatch(r'getitem "(\w+)",(\d+);', line)
        if m:
            self.char.getitem(m.group(1), int(m.group(2)))
            self.wrote("getitem", m.group(1))
            return None
        m = re.fullmatch(r'(cloakonnpc|cloakoffnpc) "([^"]+)",(\.@\w+);', line)
        if m:
            self.world.cloak_target(m.group(2), self.expr(m.group(3), scope),
                                    m.group(1) == "cloakonnpc", m.group(1))
            return None
        if line == "cloakonnpc;":
            if self.char is not None or self.npc is None:
                raise AssertionError("global cloak is only modeled for OnInit")
            self.world.cloak_global(self.npc, True)
            return None
        m = re.fullmatch(r'npctalk "([^"]*)","",BC_SELF;', line)
        if m:
            if self.char is None:
                raise AssertionError("BC_SELF needs an attached player")
            self.talk.append(m.group(1))
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
            atom = (rf'(?:"[^"\n]*"|checkquest\((?:{QUEST_ATOM})\)'
                    r'|\.@(?:[abcd]|coin|after))')
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


def arrive(char, lines=None, **kw):
    run = Run(char, lines=fruit_lines(ARRIVAL) if lines is None else lines, npc=ARRIVAL, **kw)
    run.execute(run.labels["OnTouch"] + 1)
    assert run.closed
    return run


def click(char, npc, lines=None, **kw):
    run = Run(char, lines=fruit_lines(npc) if lines is None else lines, npc=npc, **kw)
    run.execute()
    assert run.closed
    return run


def scene(char):
    return {npc: char.world.visible(npc, char) for npc in ACTORS}


SCENE_B = {MAYSEL: False, EST: True, DEBRIS: True}
SCENE_C = {MAYSEL: True, EST: False, DEBRIS: True}
SCENE_DEFAULT = {MAYSEL: True, EST: False, DEBRIS: False}  # also the D stage


def classify(a, b, c, d):
    """The brief's four-ID contract, stated independently of the scripts."""
    vals = (a, b, c, d)
    if any(v not in (-1, 1, 2) for v in vals):
        return "conflict"
    if vals == (-1, -1, -1, -1):
        return "fresh"
    if a == 1:
        return "resume" if (b, c, d) == (-1, -1, -1) else "conflict"
    if b == 1 and (c != -1 or d != -1):
        return "conflict"
    if c == 1 and d != -1:
        return "conflict"
    return {(2, 1, -1, -1): "edge_done", (2, -1, -1, -1): "interrupted",
            (2, -1, 1, -1): "shasha_done", (2, -1, -1, 1): "room_done"}.get(vals, "preserved")


STATE_CODE = {"fresh": 0, "resume": 1, "preserved": 2, "conflict": 3,
              "edge_done": 4, "interrupted": 5, "shasha_done": 6, "room_done": 7}
LOGGED = ("conflict", "interrupted")
TRAVEL = ("resume", "edge_done", "shasha_done", "room_done")


def combos():
    for combo in itertools.product(STORED, repeat=4):
        yield combo, {q: s for q, s in zip(GUARDED, combo) if s is not None}


def sentinels_ok(test, char, rewarded=False):
    for qid, state in UNRELATED.items():
        test.assertEqual(char.quests[qid], state, qid)
    test.assertEqual((char.zeny, char.exp, char.items.get(501)), (12345, 678, 3))
    test.assertLessEqual(set(char.items), {501, COIN_ID})
    for write in char.writes:
        if write[0] in ("getexp", "getitem"):
            test.assertTrue(rewarded, write)
        else:
            test.assertTrue(all(q in GUARDED for q in write[1:]), write)
    if not rewarded:
        test.assertEqual((char.coins(), char.exp_calls), (char.start_coins, []))
        test.assertEqual((char.inv, char.weight), (char.start_inv, char.start_weight))


def perturb(kind_at, change):
    """Hook that applies change(char) at the n-th yield (1-based)."""
    def hook(run, char, kind):
        if run.yields == kind_at:
            change(char)
    return hook


def quit_at(n):
    def hook(run, char, kind):
        if run.yields == n:
            raise Quit
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


def replace(old, new):
    def change(char):
        char.quests.pop(old, None)
        char.quests[new] = ACTIVE
    return change


def after_write(cmd_at, change):
    def hook(run, char, cmd, arg):
        if cmd == cmd_at:
            change(char)
    return hook


# ---------------------------------------------------------------- E: package

class PackageTests(unittest.TestCase):
    def test_owned_files_only(self):
        found = sorted(p.relative_to(MOD).as_posix() for p in MOD.rglob("*") if p.is_file())
        self.assertEqual(found, ["db/quest_db.yml", "mod.json", "npc/entry.txt",
                                 "npc/first_edge.txt", "npc/fruit_village.txt"])

    def test_mod_json(self):
        m = json.loads(MOD_JSON.read_text(encoding="utf-8"))
        self.assertEqual(m["name"], MOD.name)
        self.assertEqual(m["version"], "0.3.2")
        for key in ("version", "author", "description"):
            self.assertTrue(m[key].strip(), key)
        self.assertEqual(m["requires"], {"app": ">=1.6.3", "era": "renewal"})
        self.assertNotIn("client", m["requires"])
        self.assertEqual(sorted(m), ["author", "description", "name", "requires", "version"])

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

    def test_fruit_declarations(self):
        """Arrival event plus exactly the four village actors of the brief."""
        decls = declarations(FRUIT.read_text(encoding="utf-8"))
        self.assertEqual([(w1, kind, name, w4) for w1, kind, name, w4, _ in decls], [
            ("ygg_fruit,73,117,0", "script", ARRIVAL, "HIDDEN_WARP_NPC,1,1,{"),
            ("ygg_fruit,80,122,3", "script", SHASHA, "4_CH1_DELEGACY01,{"),
            ("ygg_fruit,82,120,3", "script", MAYSEL, "4_F_MAYSEL,{"),
            ("ygg_fruit,77,117,1", "script", EST, "4_F_ESTLOVELOY,{"),
            ("ygg_fruit,77,124,4", "script", DEBRIS, "4_LGTSCIENCE,{"),
        ])

    def test_unique_bounded_identities(self):
        names = [d[2] for p in NPC_FILES for d in declarations(p.read_text(encoding="utf-8"))]
        self.assertEqual(len(names), 10)
        self.assertEqual(len(names), len({n.upper() for n in names}), "unique identities")
        for name in names:
            hidden = name.partition("#")[2] or name
            self.assertTrue(hidden.upper().startswith("ROSOLO_CH1"), name)
            self.assertLessEqual(len(name.encode("utf-8")), 23, name)

    def test_no_fallback_graph_in_inherited_files(self):
        text = "\n".join(strip_comment(l) for p in INHERITED_NPC
                         for l in p.read_text(encoding="utf-8").split("\n"))
        decls = [d for p in INHERITED_NPC for d in declarations(p.read_text(encoding="utf-8"))]
        self.assertEqual(len(decls), 5)
        self.assertFalse(any(d[0].startswith("ygg_fruit,73,117") for d in decls))
        for word in ("cloaknpc", "cloakonnpc", "cloakoffnpc", "HIDDEN_WARP_NPC", "Maysel",
                     "Est#", "Debris", "cutin", "c1p1", "Lapine", "Ashridge", "strnpcinfo",
                     "194, 97", "194,97", "payon"):
            self.assertFalse(word.lower() in text.lower(), word)

    def test_fruit_has_no_donor_or_framework_words(self):
        text = "\n".join(strip_comment(l) for l in FRUIT.read_text(encoding="utf-8").split("\n"))
        for word in ("cloaknpc(", "dummynpc", "duplicate(", "CLOAKED", "c1p1", "Lapine",
                     "Ashridge", "Naviel", "isbegin_quest", "cutin", "navigateto", "close3",
                     "Shasha#", "Maysel#", "Newt"):
            self.assertNotIn(word.lower(), text.lower(), word)

    def test_braces_balance(self):
        for path in NPC_FILES:
            for _, kind, _, _, body in declarations(path.read_text(encoding="utf-8")):
                depth = 0
                for ch in re.sub(r'"[^"]*"', "", "\n".join(body)):
                    depth += {"{": 1, "}": -1}.get(ch, 0)
                    self.assertGreaterEqual(depth, 0)
                self.assertEqual(depth, 0, path)

    def test_profile_binding(self):
        """The fixed acceptance profile names the same IDs and reward."""
        profile = json.loads(PROFILE.read_text(encoding="utf-8"))
        self.assertEqual(profile["stages"], {"A": ENTRY, "B": SECOND, "C": THIRD, "D": FOURTH})
        reward = profile["mayselNativeReward"]
        self.assertEqual((reward["baseExp"], reward["jobExp"], reward["itemAlias"],
                          reward["sourceItemID"], reward["count"]),
                         (BASE_EXP, JOB_EXP, COIN, COIN_ID, COIN_COUNT))
        self.assertEqual(profile["preservedPartial"], [2, -1, -1, -1])
        self.assertFalse(profile["sourcePassIsRuntimeAcceptance"])


# ------------------------------------------------------------ D: text and DB

class QuestDbTests(unittest.TestCase):
    def setUp(self):
        self.text = QUEST_DB.read_text(encoding="utf-8")
        self.lines = [l for l in self.text.split("\n")
                      if l.strip() and not l.lstrip().startswith("#")]

    def test_db_file_bytes(self):
        self.assertEqual(hashlib.sha256(QUEST_DB.read_bytes()).hexdigest(), QUEST_DB_SHA256)
        self.assertIn("Body:\n" + INHERITED_ROWS + "  - Id: 18371\n", self.text,
                      "three inherited rows unchanged, D appended")

    def test_header_and_sections(self):
        self.assertEqual(self.lines[:3], ["Header:", "  Type: QUEST_DB", "  Version: 3"])
        top = [l for l in self.lines if not l.startswith(" ")]
        self.assertEqual(top, ["Header:", "Body:"])
        self.assertFalse(any(re.match(r"\s*Clear:", l) for l in self.lines))

    def test_four_rows_id_title_only(self):
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
        self.assertEqual(quest_db_ids(), frozenset(GUARDED))


class TextTests(unittest.TestCase):
    def strings(self, path):
        return re.findall(r'"([^"]*)"', path.read_text(encoding="utf-8"))

    def test_npc_text_reuses_short_log_text_only(self):
        for path in NPC_FILES:
            text = path.read_text(encoding="utf-8")
            titles = re.findall(r"「(.+?)」", "".join(self.strings(path)))
            self.assertTrue(titles, path)
            self.assertTrue(all(sha(t) in TITLE_SHA256.values() for t in titles), titles)
            objectives = [s.split("：", 1)[1] for s in self.strings(path) if s.startswith("目標：")]
            self.assertTrue(all(sha(o) in SUMMARY_SHA256.values() for o in objectives), objectives)
            for fragment in DESCRIPTION_FRAGMENTS:
                self.assertNotIn(fragment, text)
            for decl in declarations(text):
                for line in decl[4]:
                    m = re.fullmatch(r'(?:mes|dispbottom|npctalk) "([^"]*)"(?:,"",BC_SELF)?;', line)
                    if m:
                        self.assertLessEqual(len(m.group(1)), 24, m.group(1))
                        if m.group(1) in ("[Est]", "[Debris]"):
                            continue  # untranslated proper names allowed by the brief
                        self.assertIsNone(re.search(r"[A-Za-z]", m.group(1)), m.group(1))
        self.assertTrue(any("目標：" in s for s in self.strings(NPC)))
        fruit = self.strings(FRUIT)
        for qid in (THIRD, FOURTH):
            self.assertTrue(any(sha(s.split("：", 1)[-1]) == SUMMARY_SHA256[qid]
                                for s in fruit if s.startswith("目標：")), qid)

    def test_menus_are_plain_chinese(self):
        options = re.findall(r'select\("([^"]*)"\)', NPC.read_text(encoding="utf-8"))
        self.assertEqual(len(options), 2, "registration menu and travel menu")
        self.assertNotIn("select(", EDGE.read_text(encoding="utf-8"))
        for menu in options:
            for option in menu.split(":"):
                self.assertIsNone(re.search(r"[A-Za-z0-9_#]", option), option)

    def test_village_prompts_are_single_option(self):
        """Source single-option prompts stay single-option; no new branches."""
        for npc, count in ((SHASHA, 1), (MAYSEL, 4)):
            menus = [l for l in fruit_lines(npc) if "select(" in l]
            self.assertEqual(len(menus), count, npc)
            for line in menus:
                m = re.fullmatch(r'select\("([^":]+)"\);', line)
                self.assertTrue(m, line)
                self.assertIsNone(re.search(r"[A-Za-z0-9_#]", m.group(1)), line)


# ------------------------------------------------- A/E: static state discipline

FORBIDDEN = ("erasequest", "changequest", "getitem", "delitem", "getexp", "Zeny", "set ",
             "setarray", "cleararray", "callfunc", "donpcevent", "doevent", "addtimer",
             "sleep", "input", "isbegin_quest", "getvariableofnpc", "query_sql",
             "atcommand", "unitwarp", "areawarp", "jobchange", "resetlvl", "savepoint",
             "cutin", "cloaknpc", "navigateto", "specialeffect", "progressbar")
FRUIT_FORBIDDEN = tuple(w for w in FORBIDDEN if w not in ("changequest", "getitem", "getexp")) + (
    "warp", "close3", "cloakonnpcself", "cloakoffnpcself", "hideonnpc", "disablenpc",
    "OnPCLoadMapEvent", "OnPCLoginEvent", "initnpctimer", "setnpctimer")


def code_of(lines):
    return "\n".join(re.sub(r'"[^"]*"', '""', l) for l in lines)


def all_bodies():
    return [d[4] for p in NPC_FILES for d in file_declarations(p) if d[1] == "script"]


def fruit_scripts():
    return [d for d in file_declarations(FRUIT) if d[1] == "script"]


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
            self.assertNotRegex(code, rf"(setquest|completequest)\s+({THIRD}|{FOURTH})")

    def test_fruit_mutations_are_exactly_owned(self):
        writes = {}
        for _, _, name, _, body in fruit_scripts():
            code = code_of(body)
            for word in FRUIT_FORBIDDEN:
                self.assertNotIn(word, code, (name, word))
            writes[name] = re.findall(r"^(setquest|completequest|changequest|getexp|getitem)"
                                      r"\s+(.*);$", code, re.M)
        self.assertEqual(writes, {
            ARRIVAL: [("completequest", "18368"), ("setquest", "18369")],
            SHASHA: [("changequest", "18369,18370")],
            MAYSEL: [("changequest", "18370,18371"), ("getexp", "65304744,4000000"),
                     ("getitem", '"",10')],
            EST: [], DEBRIS: []})
        self.assertEqual([l for l in fruit_lines(MAYSEL) if l.startswith("getitem")],
                         ['getitem "Ch1_Root_Coin",10;'])
        self.assertEqual(fruit_lines(EST), ["end;", "", "OnInit:", "cloakonnpc;", "end;"])

    def test_only_guarded_ids(self):
        for path in INHERITED_NPC:
            code = code_of(l for d in declarations(path.read_text(encoding="utf-8"))
                           for l in d[4])
            ids = set(re.findall(r"\b\d{4,}\b", code))
            self.assertLessEqual(ids, {str(i) for i in GUARDED}, path)
        code = code_of(l for d in fruit_scripts() for l in d[4])
        self.assertEqual(set(re.findall(r"\b\d{4,}\b", code)),
                         {str(i) for i in GUARDED} | {str(BASE_EXP), str(JOB_EXP)})

    def test_variables_are_scope_only(self):
        for lines in all_bodies():
            code = code_of(lines)
            for name in re.findall(r"^\s*([^\s=]+)\s*=[^=]", code, re.M):
                self.assertTrue(name.startswith(".@"), name)
            for prefix in (r"(?<![.\w])@\w", r"\$\w", r"#\w", r"(?<!@)\.(?!@)\w", r"'\w"):
                self.assertIsNone(re.search(prefix, code), prefix)

    def test_checkquest_comparisons_are_explicit(self):
        """Read into a .@ variable, compared with ==/!=, or logged; no truthiness."""
        for lines in all_bodies():
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
                self.assertIsNone(re.search(r"(\.@[abcd]|checkquest\(\d+\))\s*(==|!=|<|>|<=|>=)\s*0\b",
                                            plain), "inactive-as-0: " + line)

    def test_every_tuple_reader_reads_all_four(self):
        """No gate still reads only three IDs: reads come in exact A,B,C,D runs."""
        for lines in all_bodies():
            reads = [i for i, l in enumerate(lines) if re.fullmatch(r"\.@[abcd] = checkquest\(\d+\);", l)]
            self.assertEqual(len(reads) % 4, 0)
            for k in range(0, len(reads), 4):
                run = [lines[i] for i in reads[k:k + 4]]
                self.assertEqual(run, [f".@{v} = checkquest({q});" for v, q in zip("abcd", GUARDED)])
                self.assertEqual(reads[k + 3] - reads[k], 3)

    def test_state_subroutines_are_identical(self):
        def block(lines, label):
            """From the label to the next label (or the end), blank lines dropped."""
            i = lines.index(label + ":")
            j = next((k for k in range(i + 1, len(lines))
                      if re.fullmatch(r"\w+:", lines[k])), len(lines))
            return [l for l in lines[i:j] if l]
        states = [block(b, "L_State") for b in all_bodies() if "L_State:" in b]
        self.assertEqual(len(states), 4, "starter, arrival, Shasha, Maysel")
        self.assertTrue(all(s == states[0] for s in states))
        syncs = [block(b, "L_Sync") for b in all_bodies() if "L_Sync:" in b]
        self.assertEqual(len(syncs), 3, "arrival, Shasha, Maysel")
        self.assertTrue(all(s == syncs[0] for s in syncs))

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
            self.assertEqual(len(reads), 4, (start, end))
            checks = [l for l in lines[start + 1:end] if l.startswith("if (")]
            self.assertTrue(checks)
            for check in checks:
                self.assertTrue(all(v in check for v in (".@a", ".@b", ".@c", ".@d")), check)

    def test_arrival_writes_are_readback_guarded_without_yield(self):
        lines = fruit_lines(ARRIVAL)
        start = lines.index("OnTouch:")
        i_cq = lines.index("completequest 18368;")
        i_sq = lines.index("setquest 18369;")
        i_ok = lines.index("L_Present:")
        self.assertLess(start, i_cq)
        self.assertLess(i_cq, i_sq)
        window = lines[start + 1:i_ok]
        self.assertFalse(any(re.match(r"(next|select|close2?|mes|sleep|callsub|warp)\b", l)
                             for l in window), "arrival never yields or warps")
        for a, b in ((start, i_cq), (i_cq, i_sq), (i_sq, i_ok)):
            self.assertEqual(len([l for l in lines[a + 1:b] if "= checkquest(" in l]), 4)
            checks = [l for l in lines[a + 1:b] if l.startswith("if (")]
            self.assertTrue(checks)
            self.assertTrue(all(all(v in c for v in (".@a", ".@b", ".@c", ".@d")) for c in checks))

    def test_conversation_write_windows(self):
        """After the last yield: full recheck, write, full readback; no yield inside."""
        for npc, write, last in ((SHASHA, "changequest 18369,18370;", "next;"),
                                 (MAYSEL, "changequest 18370,18371;", 'select("要怎麼去黑暗之地？");')):
            lines = fruit_lines(npc)
            i_w = lines.index(write)
            i_last = max(i for i, l in enumerate(lines[:i_w]) if l == last)
            i_c2 = next(i for i in range(i_w, len(lines)) if lines[i] == "close2;")
            pre = lines[i_last + 1:i_w]
            self.assertEqual(len([l for l in pre if "= checkquest(" in l]), 4, npc)
            first_mes = next(i for i in range(i_w, len(lines)) if lines[i].startswith("mes "))
            window = lines[i_last + 1:first_mes]
            self.assertFalse(any(re.match(r"(next|select|close2?|mes|sleep|callsub|end)\b|\.@\w+ = callsub", l)
                                 for l in window), npc)
            post = lines[i_w + 1:first_mes]
            self.assertGreaterEqual(len([l for l in post if "= checkquest(" in l]), 4, npc)
            self.assertEqual([l for l in lines[i_c2 + 1:] if l][:2], ["callsub L_Sync;", "end;"], npc)
        lines = fruit_lines(MAYSEL)
        i_final = lines.index("if (.@a != 2 || .@b != -1 || .@c != 1 || .@d != -1) goto L_Changed;")
        self.assertEqual([l for l in lines[i_final + 1:i_final + 6] if l][:4], [
            ".@cap = ros_ch1_coin_capacity();",
            "if (.@cap == 0) goto L_NoRoom;",
            "if (.@cap != 1) goto L_Unsupported;",
            '.@coin = countitem("Ch1_Root_Coin");'],
            "tri-state preflight directly after the exact C check")
        self.assertEqual(sum("countitem(" in l for l in lines), 2, "two snapshots, no count gate")
        self.assertEqual(sum("L_Unsupported" in l for l in lines), 2)
        self.assertEqual(sum("ros_ch1_coin_capacity" in l for l in lines), 1)
        order = [lines.index(l) for l in (
            ".@cap = ros_ch1_coin_capacity();",
            "if (.@cap == 0) goto L_NoRoom;",
            "if (.@cap != 1) goto L_Unsupported;",
            '.@coin = countitem("Ch1_Root_Coin");', "changequest 18370,18371;",
            "if (.@a != 2 || .@b != -1 || .@c != -1 || .@d != 1) goto L_Hold;",
            "getexp 65304744,4000000;", 'getitem "Ch1_Root_Coin",10;',
            '.@after = countitem("Ch1_Root_Coin");',
            "if (.@after != .@coin + 10) goto L_RewardHold;",
            "if (.@a != 2 || .@b != -1 || .@c != -1 || .@d != 1) goto L_RewardHold;")]
        self.assertEqual(order, sorted(order))
        self.assertEqual(order[6] - order[5], 1, "rewards follow the exact D readback")
        self.assertEqual(order[7] - order[6], 1)

    def test_every_dialogue_yield_is_rechecked(self):
        for npc, code in ((SHASHA, 4), (MAYSEL, 6)):
            lines = fruit_lines(npc)
            start = lines.index("L_Intro:" if npc == SHASHA else "L_Talk:")
            stop = lines.index("close2;")
            ys = [i for i in range(start, stop)
                  if lines[i] == "next;" or lines[i].startswith("select(")]
            self.assertEqual(len(ys), 7 if npc == SHASHA else 12, npc)
            for i in ys[:-1]:
                self.assertEqual(lines[i + 1:i + 3], [".@state = callsub(L_State);",
                                                      f"if (.@state != {code}) goto L_Changed;"],
                                 (npc, i))


# --------------------------------------------- A: modeled starter runs

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

    def test_fresh_requires_d_absent(self):
        """An old three-ID test would register here; D present is preserved."""
        for d in (ACTIVE, INACTIVE, COMPLETE):
            char, run = talk(250, {FOURTH: d}, choices=[1, 1])
            self.assertEqual((char.writes, char.warps, run.menus), ([], [], 0), d)
            self.assertEqual(char.guarded(), {FOURTH: d})

    def test_cancel_changes_nothing_and_retry_registers_once(self):
        char = Character(200)
        Run(char, [2]).execute()
        self.assertEqual((char.guarded(), char.writes, char.warps), ({}, [], []))
        Run(char, [1, 2]).execute()
        Run(char, [2]).execute()  # second visit resumes; declines travel
        self.assertEqual(char.guarded(), {ENTRY: ACTIVE})
        self.assertEqual(char.writes, [("setquest", ENTRY)])
        self.assertEqual(char.warps, [])

    def test_quit_at_each_yield_writes_nothing_more(self):
        for at in (1, 2):
            char, run = talk(200, choices=[1, 1], on_yield=quit_at(at))
            self.assertTrue(run.quit)
            self.assertEqual((char.writes, char.warps), ([], []), at)
        for at in (3, 4, 5):
            char, run = talk(200, choices=[1, 1], on_yield=quit_at(at))
            self.assertEqual((char.writes, char.warps), ([("setquest", ENTRY)], []), at)

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

    def test_later_stage_repeat_travel_and_payon_never(self):
        """B, C and D stages (active or inactive) travel to 212,95 at 200+ only."""
        for later, s, level in itertools.product((SECOND, THIRD, FOURTH), (ACTIVE, INACTIVE),
                                                 (199, 200, 201)):
            for choice in (1, 2):
                quests = {ENTRY: COMPLETE, later: s}
                char, run = talk(level, quests, choices=[choice])
                self.assertEqual(char.writes, [])
                self.assertEqual(char.guarded(), quests)
                want = [REPEAT_DEST] if level >= 200 and choice == 1 else []
                self.assertEqual(char.warps, want, (later, s, level, choice))
                self.assertNotIn(PAYON_DEST, char.warps)
                self.assertEqual(run.debug, [])
                title = {SECOND: "天地樹的召喚(2)", THIRD: "天地樹的召喚(3)",
                         FOURTH: "扭曲的黑暗之地"}[later]
                self.assertIn(f"任務「{title}」仍在進行中。", run.mes)

    def test_genuine_partial_hold_versus_room_done(self):
        char, run = talk(250, PARTIAL, choices=[1, 1])
        self.assertEqual((char.writes, char.warps, run.menus), ([], [], 0))
        self.assertTrue(run.debug, "(2,-1,-1,-1) still held and logged")
        char, run = talk(250, STAGE_D, choices=[1])
        self.assertEqual((char.writes, char.warps, run.debug), ([], [REPEAT_DEST], []))

    def test_completed_only_and_active_active_hold(self):
        for quests in ({ENTRY: COMPLETE}, {ENTRY: ACTIVE, SECOND: ACTIVE},
                       {ENTRY: INACTIVE, SECOND: INACTIVE}, {ENTRY: ACTIVE, FOURTH: ACTIVE},
                       {ENTRY: COMPLETE, SECOND: ACTIVE, FOURTH: ACTIVE},
                       {ENTRY: COMPLETE, THIRD: ACTIVE, FOURTH: COMPLETE}):
            char, run = talk(250, quests, choices=[1, 1])
            self.assertEqual((char.writes, char.warps, run.menus), ([], [], 0), quests)
            self.assertEqual(char.guarded(), quests)
            self.assertTrue(run.debug, quests)

    def test_registration_yield_rechecks(self):
        """State/level changed during the registration menu (yield 2)."""
        char, run = talk(200, choices=[1, 1], on_yield=perturb(2, set_level(199)))
        self.assertEqual((char.guarded(), char.writes, char.warps), ({}, [], []))
        for qid, state in ((ENTRY, COMPLETE), (SECOND, ACTIVE), (THIRD, COMPLETE), (ENTRY, 0),
                           (FOURTH, ACTIVE), (FOURTH, 7)):
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
            "D present": set_quest(FOURTH, ACTIVE),
            "A erased": set_quest(ENTRY, None),
            "A unknown": set_quest(ENTRY, 7),
        }
        for at, (name, change) in itertools.product((3, 4, 5), changes.items()):
            char, run = talk(200, choices=[1, 1], on_yield=perturb(at, change))
            self.assertEqual(char.writes, [("setquest", ENTRY)], (at, name))
            self.assertEqual(char.warps, [], (at, name))
            if at == 5:
                self.assertTrue(run.bottom, "post-close2 refusal is visible")
        # A harmless inactive toggle keeps (1,-1,-1,-1) and still travels.
        char, run = talk(200, choices=[1, 1], on_yield=perturb(5, set_quest(ENTRY, INACTIVE)))
        self.assertEqual(char.warps, [FIRST_DEST])

    def test_repeat_travel_yields_recheck(self):
        """Yields 1 (next), 2 (travel select) and 3 (close2) on a revisit."""
        for start, at, change in itertools.product(
                (STAGE_A, STAGE_B, STAGE_C, STAGE_D), (1, 2, 3),
                (set_level(150), set_quest(FOURTH, 7), set_quest(SECOND, COMPLETE))):
            char, run = talk(200, start, choices=[1], on_yield=perturb(at, change))
            self.assertEqual((char.writes, char.warps), ([], []), (start, at))
        # Progress elsewhere during the menu (C -> D) changes the class: no travel.
        char, run = talk(200, STAGE_C, choices=[1], on_yield=perturb(2, replace(THIRD, FOURTH)))
        self.assertEqual(char.warps, [])

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
                                    (False, SECOND, ACTIVE), (False, THIRD, COMPLETE),
                                    (False, FOURTH, ACTIVE), (True, FOURTH, 0)):
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
                elif want in TRAVEL and ok:
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


# --------------------------------------------- A: modeled Messenger runs

EDGE_WRITES = [("completequest", ENTRY), ("setquest", SECOND)]
SUCCESS = "任務「天地樹的召喚(2)」已記錄。"


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
                self.assertEqual(tuple_of(char), (2, 1, -1, -1), combo)
                continue
            self.assertEqual(char.writes, [], combo)
            self.assertEqual(char.guarded(), quests, combo)
            self.assertNotIn(SUCCESS, run.mes)
            self.assertEqual(bool(run.debug), want in LOGGED, combo)
            sentinels_ok(self, char)

    def test_d_present_blocks_the_edge(self):
        for d in (ACTIVE, INACTIVE, COMPLETE):
            char, run = messenger(200, {ENTRY: ACTIVE, FOURTH: d})
            self.assertEqual(char.writes, [], d)
            self.assertTrue(run.debug)

    def test_completequest_noop_prevents_setquest_and_retries(self):
        char, run = messenger(200, {ENTRY: ACTIVE}, faults={("completequest", ENTRY)})
        self.assertEqual(char.writes, [("completequest", ENTRY)])
        self.assertEqual(tuple_of(char), (1, -1, -1, -1))
        self.assertTrue(run.debug)
        self.assertNotIn(SUCCESS, run.mes)
        self.assertIn("可以稍後再和我說話。", run.mes, "reported as retryable")
        char.faults.clear()
        Run(char, lines=script_lines(EDGE, 0)).execute()
        self.assertEqual(tuple_of(char), (2, 1, -1, -1))
        self.assertEqual(char.writes, [("completequest", ENTRY)] + EDGE_WRITES)

    def test_setquest_noop_leaves_protected_partial(self):
        char, run = messenger(200, {ENTRY: ACTIVE}, faults={("setquest", SECOND)})
        self.assertEqual(char.writes, EDGE_WRITES)
        self.assertEqual(tuple_of(char), (2, -1, -1, -1))
        self.assertTrue(run.debug)
        self.assertNotIn(SUCCESS, run.mes)
        self.assertIn("紀錄只更新了一半。", run.mes, "reported as an interrupted edge")
        char.faults.clear()
        for _ in range(2):  # revisits never repair: Messenger, starter, arrival, village
            Run(char, lines=script_lines(EDGE, 0)).execute()
            char.level = 250
            r = Run(char, [1, 1])
            r.execute()
            self.assertTrue(r.debug)
            arrive(char)
            for npc in (SHASHA, MAYSEL, DEBRIS, EST):
                click(char, npc)
        self.assertEqual(char.writes, EDGE_WRITES)
        self.assertEqual((tuple_of(char), char.warps), ((2, -1, -1, -1), []))

    def test_interference_after_each_write_stops(self):
        changes = (set_quest(THIRD, ACTIVE), set_quest(ENTRY, None), set_quest(ENTRY, 7),
                   set_quest(SECOND, COMPLETE), set_quest(THIRD, 0), set_quest(FOURTH, ACTIVE))
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
                   set_quest(THIRD, COMPLETE), set_quest(ENTRY, None), set_quest(ENTRY, 0),
                   set_quest(FOURTH, INACTIVE))
        for change in changes:
            char, run = messenger(200, {ENTRY: ACTIVE}, on_yield=perturb(1, change))
            self.assertEqual(char.writes, [])
            self.assertNotIn(SUCCESS, run.mes)
        # A level change is not a Messenger gate; an inactive toggle keeps the tuple.
        for change in (set_level(1), set_quest(ENTRY, INACTIVE)):
            char, run = messenger(200, {ENTRY: ACTIVE}, on_yield=perturb(1, change))
            self.assertEqual(char.writes, EDGE_WRITES)


# --------------------------------------------- B: arrival fallback

class ArrivalTests(unittest.TestCase):
    def test_admitted_fallback_is_checked_and_yieldless(self):
        for a in (ACTIVE, INACTIVE):
            char = Character(1, {ENTRY: a})
            run = arrive(char)
            self.assertEqual(char.writes, EDGE_WRITES)
            self.assertEqual(tuple_of(char), (2, 1, -1, -1))
            self.assertEqual((run.yields, run.mes, char.warps, run.debug), (0, [], [], []))
            self.assertIn(SUCCESS, run.bottom)
            self.assertEqual(scene(char), SCENE_B)
            sentinels_ok(self, char)
            before = list(char.writes)
            arrive(char)  # repeat arrival: presentation only
            self.assertEqual(char.writes, before)

    def test_completequest_noop_is_retryable(self):
        char = Character(1, STAGE_A, faults={("completequest", ENTRY)})
        run = arrive(char)
        self.assertEqual(char.writes, [("completequest", ENTRY)])
        self.assertEqual(tuple_of(char), (1, -1, -1, -1))
        self.assertTrue(run.debug)
        self.assertNotIn(SUCCESS, run.bottom)
        self.assertEqual(scene(char), SCENE_DEFAULT)
        char.faults.clear()
        arrive(char)
        self.assertEqual(tuple_of(char), (2, 1, -1, -1))

    def test_setquest_noop_is_held_not_repaired(self):
        char = Character(1, STAGE_A, faults={("setquest", SECOND)})
        run = arrive(char)
        self.assertEqual(tuple_of(char), (2, -1, -1, -1))
        self.assertTrue(run.debug)
        self.assertNotIn(SUCCESS, run.bottom)
        char.faults.clear()
        for _ in range(3):
            arrive(char)
        self.assertEqual(char.writes, EDGE_WRITES, "A-complete/B-absent never repaired")

    def test_interference_after_each_write_holds(self):
        for cmd, change in itertools.product(("completequest", "setquest"), (
                set_quest(THIRD, ACTIVE), set_quest(FOURTH, ACTIVE), set_quest(ENTRY, 7),
                set_quest(SECOND, COMPLETE))):
            char = Character(1, STAGE_A)
            run = arrive(char, on_write=after_write(cmd, change))
            self.assertTrue(any("no further change" in l for l in run.debug), (cmd,))
            self.assertNotIn(SUCCESS, run.bottom)
            self.assertLessEqual(len(char.writes), 2)

    def test_every_other_tuple_writes_nothing(self):
        for combo, quests in combos():
            seen = tuple(Character(0, quests).checkquest(q) for q in GUARDED)
            want = classify(*seen)
            char = Character(1, quests)
            run = arrive(char)
            if want == "resume":
                self.assertEqual(char.writes, EDGE_WRITES, combo)
                continue
            self.assertEqual((char.writes, run.bottom, run.debug), ([], [], []), combo)
            self.assertEqual(char.guarded(), quests)
            expect = {"edge_done": SCENE_B, "shasha_done": SCENE_C}.get(want, SCENE_DEFAULT)
            self.assertEqual(scene(char), expect, combo)
            if want not in ("edge_done", "shasha_done", "room_done"):
                self.assertEqual(char.mask, set(), "no stale visibility for other tuples")
            sentinels_ok(self, char)


# --------------------------------------------- B: Shasha 18369 -> 18370

SHASHA_WRITE = [("changequest", SECOND, THIRD)]
SHASHA_OK = "任務「天地樹的召喚(3)」已記錄。"


def shasha_char(quests=None, **kw):
    char = Character(250, STAGE_B if quests is None else quests, **kw)
    arrive(char)
    return char


class ShashaTests(unittest.TestCase):
    def test_replacement_before_final_close_and_no_reward(self):
        for b in (ACTIVE, INACTIVE):
            char = shasha_char({ENTRY: COMPLETE, SECOND: b})
            seen = []

            def at_close(run, ch, kind):
                if kind == "close2":
                    seen.append((tuple_of(ch), dict(scene(ch))))
            run = click(char, SHASHA, on_yield=at_close)
            self.assertEqual(char.writes, SHASHA_WRITE)
            self.assertEqual(tuple_of(char), (2, -1, 1, -1), "B removed, C active")
            self.assertEqual(seen, [((2, -1, 1, -1), SCENE_B)], "written before close2")
            self.assertEqual((run.yields, run.menus), (8, 1))
            self.assertIn(SHASHA_OK, run.mes)
            self.assertIn("目標：與梅雪對話", run.mes)
            self.assertEqual(scene(char), SCENE_C, "post-close presentation")
            sentinels_ok(self, char)

    def test_every_yield_rechecks(self):
        changes = (set_quest(SECOND, COMPLETE), set_quest(THIRD, ACTIVE), set_quest(FOURTH, ACTIVE),
                   set_quest(ENTRY, None), set_quest(SECOND, 7), replace(SECOND, THIRD),
                   set_quest(SECOND, None))
        for at, change in itertools.product(range(1, 8), changes):
            char = shasha_char()
            run = click(char, SHASHA, on_yield=perturb(at, change))
            self.assertEqual(char.writes, [], at)
            self.assertNotIn(SHASHA_OK, run.mes)
            self.assertIn("這次不會做任何變更。", run.mes)
        for at in range(1, 8):  # inactive toggle keeps (2,1,-1,-1)
            char = shasha_char()
            click(char, SHASHA, on_yield=perturb(at, set_quest(SECOND, INACTIVE)))
            self.assertEqual(char.writes, SHASHA_WRITE)

    def test_quit_before_write_is_not_completion(self):
        for at in range(1, 8):
            char = shasha_char()
            run = click(char, SHASHA, on_yield=quit_at(at))
            self.assertTrue(run.quit)
            self.assertEqual((char.writes, tuple_of(char)), ([], (2, 1, -1, -1)), at)
            self.assertNotIn(SHASHA_OK, run.mes)

    def test_noop_replacement_is_retryable_without_reward(self):
        char = shasha_char(faults={("changequest", SECOND)})
        run = click(char, SHASHA)
        self.assertEqual(char.writes, SHASHA_WRITE)
        self.assertEqual(tuple_of(char), (2, 1, -1, -1))
        self.assertTrue(run.debug)
        self.assertIn("可以稍後再和我說話。", run.mes)
        self.assertNotIn(SHASHA_OK, run.mes)
        self.assertEqual(scene(char), SCENE_B)
        char.faults.clear()
        click(char, SHASHA)
        self.assertEqual(tuple_of(char), (2, -1, 1, -1))
        sentinels_ok(self, char)

    def test_missing_c_definition_is_a_refused_noop(self):
        char = shasha_char(db_ids={ENTRY, SECOND, FOURTH})
        click(char, SHASHA)
        self.assertEqual(tuple_of(char), (2, 1, -1, -1))

    def test_unexpected_poststate_is_held(self):
        for change in (set_quest(FOURTH, ACTIVE), set_quest(ENTRY, None), set_quest(THIRD, 7),
                       set_quest(SECOND, ACTIVE)):
            char = shasha_char()
            run = click(char, SHASHA, on_write=after_write("changequest", change))
            self.assertTrue(any("no further change" in l for l in run.debug))
            self.assertNotIn(SHASHA_OK, run.mes)
            self.assertNotIn("可以稍後再和我說話。", run.mes)
            self.assertEqual(run.yields, 7, "held before close2/presentation")

    def test_close_interruption_recovers_on_next_interaction(self):
        char = shasha_char()
        run = click(char, SHASHA, on_yield=quit_at(8))
        self.assertTrue(run.quit)
        self.assertEqual(tuple_of(char), (2, -1, 1, -1))
        self.assertEqual(scene(char), SCENE_B, "handoff interrupted")
        run = click(char, SHASHA)
        self.assertEqual(scene(char), SCENE_C, "ordinary Shasha repeat repairs it")
        self.assertEqual(char.writes, SHASHA_WRITE, "no write replayed")
        self.assertIn("任務「天地樹的召喚(3)」仍在進行中。", run.mes)

    def test_relog_away_from_touch_cell_recovers_on_interaction(self):
        char = shasha_char()
        click(char, SHASHA)
        char.relog()
        self.assertEqual(scene(char), SCENE_DEFAULT, "native masks reset; quest log persists")
        click(char, SHASHA)
        self.assertEqual(scene(char), SCENE_C)
        self.assertEqual(char.writes, SHASHA_WRITE)

    def test_post_close_sync_checks_map(self):
        char = shasha_char()
        mark = []

        def leave(run, ch, kind):
            if kind == "close2":
                mark.append(len(ch.world.calls))
                ch.move("ygg_edge")
        click(char, SHASHA, on_yield=leave)
        self.assertEqual(tuple_of(char), (2, -1, 1, -1))
        self.assertEqual(char.world.calls[mark[0]:], [], "no cloak request off the fruit map")

    def test_c_and_d_repeats_are_read_only(self):
        for quests, text in ((STAGE_C, "梅雪就在旁邊，去和她說話吧。"),
                             (STAGE_D, "目標：前往扭曲的黑暗之地")):
            char = Character(250, quests)
            for _ in range(3):
                run = click(char, SHASHA)
                self.assertIn(text, run.mes)
            self.assertEqual(char.writes, [])
            sentinels_ok(self, char)

    def test_every_tuple_only_b_writes(self):
        for combo, quests in combos():
            seen = tuple(Character(0, quests).checkquest(q) for q in GUARDED)
            want = classify(*seen)
            char = Character(250, quests)
            run = click(char, SHASHA)
            if want == "edge_done":
                self.assertEqual(char.writes, SHASHA_WRITE, combo)
                self.assertEqual(tuple_of(char), (2, -1, 1, -1))
                continue
            self.assertEqual(char.writes, [], combo)
            self.assertEqual(char.guarded(), quests)
            self.assertEqual(bool(run.debug), want == "conflict", combo)
            if want not in ("shasha_done", "room_done"):
                self.assertEqual(char.mask, set(), combo)
            sentinels_ok(self, char)


# --------------------------------------------- C: Maysel 18370 -> 18371 and rewards

MAYSEL_WRITES = [("changequest", THIRD, FOURTH), ("getexp", BASE_EXP, JOB_EXP),
                 ("getitem", COIN, COIN_COUNT)]
MAYSEL_OK = "任務「扭曲的黑暗之地」已記錄。"


def maysel_char(quests=None, **kw):
    char = Character(250, STAGE_C if quests is None else quests, **kw)
    arrive(char)
    return char


class MayselTests(unittest.TestCase):
    def test_ordered_native_rewards_once(self):
        for c in (ACTIVE, INACTIVE):
            char = maysel_char({ENTRY: COMPLETE, THIRD: c})
            first_blank = char.inv.index(None)
            run = click(char, MAYSEL)
            self.assertEqual(char.writes, MAYSEL_WRITES)
            self.assertEqual(tuple_of(char), (2, -1, -1, 1))
            self.assertEqual(char.coins(), COIN_COUNT)
            self.assertEqual(char.inv[first_blank], row(amount=COIN_COUNT), "one new row")
            self.assertEqual(char.weight, char.start_weight + COIN_WEIGHT * COIN_COUNT)
            self.assertEqual(char.exp_calls, [(BASE_EXP, JOB_EXP)])
            self.assertEqual((run.yields, run.menus), (13, 4))
            self.assertIn(MAYSEL_OK, run.mes)
            self.assertIn("目標：前往扭曲的黑暗之地", run.mes)
            self.assertEqual(run.debug, [])
            self.assertEqual(scene(char), SCENE_DEFAULT, "D restores initial roles")
            sentinels_ok(self, char, rewarded=True)

    def test_no_repeat_reward(self):
        char = maysel_char()
        click(char, MAYSEL)
        for npc in (MAYSEL, MAYSEL, SHASHA, DEBRIS, EST):
            run = click(char, npc)
            self.assertNotIn(MAYSEL_OK, run.mes)
        arrive(char)
        talk(250, char=char, choices=[2])
        self.assertEqual(char.writes, MAYSEL_WRITES)
        self.assertEqual(char.coins(), COIN_COUNT)

    def test_every_yield_rechecks(self):
        changes = (set_quest(THIRD, COMPLETE), set_quest(FOURTH, ACTIVE), set_quest(SECOND, ACTIVE),
                   set_quest(ENTRY, None), set_quest(THIRD, 0), replace(THIRD, FOURTH),
                   set_quest(THIRD, None))
        for at, change in itertools.product(range(1, 13), changes):
            char = maysel_char()
            run = click(char, MAYSEL, on_yield=perturb(at, change))
            self.assertEqual(char.writes, [], at)
            self.assertNotIn(MAYSEL_OK, run.mes)
            sentinels_ok(self, char)

    def test_quit_before_write_grants_nothing(self):
        for at in range(1, 13):
            char = maysel_char()
            run = click(char, MAYSEL, on_yield=quit_at(at))
            self.assertTrue(run.quit)
            self.assertEqual((char.writes, tuple_of(char)), ([], (2, -1, 1, -1)), at)
            sentinels_ok(self, char)

    def test_preflight_refusals_grant_nothing_and_stay_retryable(self):
        cases = {
            "overweight": dict(weight=995, max_weight=1000),
            "no free slot": dict(free_slots=0),
            "no usable blank, blank beyond the usable slots": dict(free_slots=0, hidden_blanks=1),
            "stack limit below ten": dict(stack_limit=COIN_COUNT - 1),
        }
        for name, kw in cases.items():
            char = maysel_char(**kw)
            run = click(char, MAYSEL)
            self.assertEqual(char.writes, [], name)
            self.assertEqual(tuple_of(char), (2, -1, 1, -1), name)
            self.assertIn("整理之後再來找我吧。", run.mes, name)
            self.assertTrue(run.debug, name)
            sentinels_ok(self, char)
        char = maysel_char(free_slots=0)
        click(char, MAYSEL)
        char.expand()
        click(char, MAYSEL)
        self.assertEqual(char.writes, MAYSEL_WRITES, "retry after making room")

    def test_noop_replacement_grants_nothing(self):
        for kw in (dict(faults={("changequest", THIRD)}), dict(db_ids={ENTRY, SECOND, THIRD})):
            char = maysel_char(**kw)
            run = click(char, MAYSEL)
            self.assertEqual(char.writes, [("changequest", THIRD, FOURTH)], kw)
            self.assertEqual(tuple_of(char), (2, -1, 1, -1))
            self.assertIn("可以稍後再和我說話。", run.mes)
            sentinels_ok(self, char)

    def test_unexpected_poststate_grants_nothing(self):
        for change in (set_quest(THIRD, ACTIVE), set_quest(FOURTH, 7), set_quest(SECOND, ACTIVE),
                       set_quest(ENTRY, None)):
            char = maysel_char()
            run = click(char, MAYSEL, on_write=after_write("changequest", change))
            self.assertEqual(char.writes, [("changequest", THIRD, FOURTH)])
            self.assertTrue(any("nothing granted" in l for l in run.debug))
            sentinels_ok(self, char)

    def test_bad_delivery_is_held_not_replayed(self):
        failures = {
            "getitem refused after preflight": dict(faults={("getitem", COIN)}),
            "coin delta wrong": dict(on_write=after_write(
                "getitem", lambda c: c.inv[c.inv.index(row(amount=COIN_COUNT))].update(
                    amount=COIN_COUNT - 1))),
            "native add fails after a passed check": dict(free_slots=1, on_write=after_write(
                "getexp", lambda c: c.inv.__setitem__(c.inv.index(None), row(501, 1)))),
            "tuple changed after rewards": dict(on_write=after_write(
                "getitem", set_quest(FOURTH, 7))),
        }
        for name, kw in failures.items():
            on_write = kw.pop("on_write", None)
            char = maysel_char(**kw)
            run = click(char, MAYSEL, on_write=on_write)
            self.assertEqual(char.writes, MAYSEL_WRITES, name)
            self.assertNotIn(MAYSEL_OK, run.mes, name)
            self.assertIn("紀錄已保留，不會自動重發。", run.mes, name)
            self.assertTrue(any("held, no replay" in l for l in run.debug), name)
            self.assertEqual(run.yields, 12, "no close2/presentation on a hold")
            char.faults.clear()
            for _ in range(2):
                click(char, MAYSEL)
            self.assertEqual(char.writes, MAYSEL_WRITES, "no automatic replay or compensation")

    def test_cloak_is_not_a_gate(self):
        char = shasha_char()
        self.assertFalse(scene(char)[MAYSEL])
        run = click(char, MAYSEL)  # a hidden NPC can still be clicked natively
        self.assertEqual(char.writes, [])
        self.assertIn("先去和莎莎說話吧。", run.mes)

    def test_every_tuple_only_c_writes(self):
        for combo, quests in combos():
            seen = tuple(Character(0, quests).checkquest(q) for q in GUARDED)
            want = classify(*seen)
            char = Character(250, quests)
            run = click(char, MAYSEL)
            if want == "shasha_done":
                self.assertEqual(char.writes, MAYSEL_WRITES, combo)
                continue
            self.assertEqual(char.writes, [], combo)
            self.assertEqual(char.guarded(), quests)
            self.assertEqual(bool(run.debug), want == "conflict", combo)
            sentinels_ok(self, char)


# ------------------- T10.010.002: native ros_ch1_coin_capacity() tri-state

UNSUPPORTED = "現在無法確認金幣能否放進你的行囊。"
NO_ROOM = "整理之後再來找我吧。"
HELD = "紀錄已保留，不會自動重發。"
FUTURE, PAST = 4102444800, 1  # positive expiry; the model has no clock
CAP_LINES = ("\t.@cap = ros_ch1_coin_capacity();\n",
             "\tif (.@cap == 0) goto L_NoRoom;\n",
             "\tif (.@cap != 1) goto L_Unsupported;\n")
CAP = "".join(CAP_LINES)
# The three controlling gates 0.3.1 had; none may remain in current text.
OLD_GATES = ('\tif (countitem("Ch1_Root_Coin") != 0) goto L_HasCoin;\n',
             '\tif (rentalcountitem("Ch1_Root_Coin") != 0) goto L_HasCoin;\n',
             '\tif (checkweight("Ch1_Root_Coin",10) == 0) goto L_NoRoom;\n')
LEGACY_AND = OLD_GATES[2]
D_READBACK = "\tif (.@a != 2 || .@b != -1 || .@c != -1 || .@d != 1) goto L_Hold;\n"


def maysel_variant(*pairs):
    """Maysel's real text with (old, new) replacements, each applied once."""
    text = FRUIT.read_text(encoding="utf-8")
    start = text.index("\t" + MAYSEL + "\t")
    end = text.index("\n}\n", start)
    part = text[start:end]
    for old, new in pairs:
        if part.count(old) != 1:
            raise AssertionError("mutation target must exist once: " + old)
        part = part.replace(old, new)
    return fruit_lines(MAYSEL, text[:start] + part + text[end:])


# Profile existingCoinCases: kwargs, legacy native checkweight, native add, and
# the outcome of the 0.3.0 checkweight-only order (history). 0.3.2 follows the
# native add: rewarded exactly when the add succeeds, otherwise refused first.
EXISTING_COIN_CASES = {
    "ordinary compatible, no free slot": (dict(free_slots=0, coin_rows=[row()]), 1, True, "rewarded"),
    "ordinary compatible, spare slot": (dict(free_slots=1, coin_rows=[row()]), 1, True, "rewarded"),
    "bound only, full bag": (dict(free_slots=0, coin_rows=[row(bound=1)]), 1, False, "late_hold"),
    "card marked only, full bag": (dict(free_slots=0, coin_rows=[row(card=254)]), 1, False, "late_hold"),
    "nonzero unique ID only, full bag": (dict(free_slots=0, coin_rows=[row(unique=77)]), 1, False,
                                         "late_hold"),
    "rental only, full bag": (dict(free_slots=0, coin_rows=[row(expire=FUTURE)]), 1, False, "late_hold"),
    "expired but retained rental, full bag": (dict(free_slots=0, coin_rows=[row(expire=PAST)]), 1,
                                              False, "late_hold"),
    "mixed rental and ordinary rows, full bag": (
        dict(free_slots=0, coin_rows=[row(expire=FUTURE), row()]), 1, True, "rewarded"),
    "coin at an inaccessible index, full bag": (dict(free_slots=0, hidden_rows=[row()]), 0, False,
                                                "no_room"),
    "full compatible stack, spare slot": (dict(free_slots=1, coin_rows=[row(amount=STACK_CAP)]), 0,
                                          False, "no_room"),
    "earlier incompatible, later full compatible, spare slot": (
        dict(free_slots=1, coin_rows=[row(bound=1), row(amount=STACK_CAP)]), 1, False, "late_hold"),
    # T10.010.002: the first same-ID row is an incompatible FULL stack, so the
    # legacy checkweight refuses although a later compatible row fits.
    "earlier incompatible full, later compatible fit, full bag": (
        dict(free_slots=0, coin_rows=[row(bound=1, amount=STACK_CAP), row()]), 0, True, "no_room"),
    "earlier full rental, later compatible fit, spare slot": (
        dict(free_slots=1, coin_rows=[row(expire=FUTURE, amount=STACK_CAP), row(amount=5)]), 0, True,
        "no_room"),
}


class NativeCapacityPolicyTests(unittest.TestCase):
    def assert_refused(self, char, run, text, msg=None):
        self.assertEqual(char.writes, [], msg)
        self.assertEqual(tuple_of(char), (2, -1, 1, -1), msg)
        self.assertEqual((char.coins(), char.exp_calls), (char.start_coins, []), msg)
        self.assertIn(text, run.mes, msg)
        for other in {UNSUPPORTED, NO_ROOM} - {text}:
            self.assertNotIn(other, run.mes, msg)
        self.assertEqual(run.yields, 12, msg)

    def assert_rewarded(self, char, run, msg=None):
        self.assertEqual(char.writes, MAYSEL_WRITES, msg)
        self.assertEqual(tuple_of(char), (2, -1, -1, 1), msg)
        self.assertEqual(char.coins(), char.start_coins + COIN_COUNT, msg)
        self.assertIn(MAYSEL_OK, run.mes, msg)

    def test_no_old_gate_remains(self):
        text = FRUIT.read_text(encoding="utf-8")
        for gate in OLD_GATES:
            self.assertNotIn(gate, text)
        for word in ("checkweight", "rentalcountitem", "L_HasCoin"):
            self.assertNotIn(word, "\n".join(fruit_lines(MAYSEL)), word)
        self.assertEqual(text.count("ros_ch1_coin_capacity()"), 2, "one call, one comment")

    def test_unsupported_text_is_distinct_short_and_truthful(self):
        lines = fruit_lines(MAYSEL)
        i = lines.index("L_Unsupported:")
        mes = [l for l in lines[i:lines.index("close;", i)] if l.startswith("mes ")]
        self.assertEqual(mes, ['mes "[梅雪]";', f'mes "{UNSUPPORTED}";',
                               'mes "這次沒有發放獎勵，任務維持原狀。";'])
        text = "".join(mes)
        for word in ("裝不下", "滿", "損壞", "交易", "倉庫", "丟", "刪除", "已經有"):
            self.assertNotIn(word, text, word)
        self.assertTrue(any("capacity unconfirmed" in l for l in lines[i:i + 3]))

    def test_existing_coin_cases_follow_the_native_add(self):
        for name, (kw, check, add, _) in EXISTING_COIN_CASES.items():
            char = maysel_char(**kw)
            self.assertEqual(char.checkweight(COIN, COIN_COUNT), check, name)
            self.assertEqual(copy.deepcopy(char).additem(COIN_COUNT), add, name)
            run = click(char, MAYSEL)
            self.assertEqual(char.probes, 1, name)
            if add:
                self.assert_rewarded(char, run, name)
            else:
                self.assert_refused(char, run, NO_ROOM, name)
            sentinels_ok(self, char, rewarded=add)

    def test_compatible_and_mixed_positives_are_restored(self):
        restored = [n for n, v in EXISTING_COIN_CASES.items() if v[2]]
        self.assertEqual(len(restored), 5)
        for name in restored:
            char = maysel_char(**EXISTING_COIN_CASES[name][0])
            self.assert_rewarded(char, click(char, MAYSEL), name)

    def test_unsupported_is_refused_before_any_mutation(self):
        for kw in (dict(capacity=-1), dict(capacity=-1, coin_rows=[row()]), dict(capacity=2),
                   dict(item_db=False), dict(capacity=-1, free_slots=0)):
            char = maysel_char(**kw)
            run = click(char, MAYSEL)
            self.assert_refused(char, run, UNSUPPORTED, kw)
            self.assertTrue(any("capacity unconfirmed" in l for l in run.debug), kw)
            sentinels_ok(self, char)

    def test_zero_is_refused_before_any_mutation(self):
        for kw in (dict(capacity=0), dict(free_slots=0), dict(weight=991, max_weight=1000)):
            char = maysel_char(**kw)
            self.assert_refused(char, click(char, MAYSEL), NO_ROOM, kw)
        char = maysel_char(weight=990, max_weight=1000)
        self.assert_rewarded(char, click(char, MAYSEL), "weight equality fits")

    def test_capacity_is_read_after_the_final_yield(self):
        def put(r):
            return lambda c: c.inv.__setitem__(c.inv.index(None), dict(r))
        for at in range(1, 13):
            char = maysel_char(free_slots=0, coin_rows=[row(bound=1)])
            run = click(char, MAYSEL, on_yield=perturb(at, lambda c: c.inv.__setitem__(
                c.inv.index(row(bound=1)), row())))
            self.assert_rewarded(char, run, ("compatible row appears", at))
            char = maysel_char(free_slots=1)
            run = click(char, MAYSEL, on_yield=perturb(at, put(row(501, 1))))
            self.assert_refused(char, run, NO_ROOM, ("last blank taken", at))
            for added in (row(), row(expire=FUTURE), row(bound=1)):
                char = maysel_char(free_slots=2)
                run = click(char, MAYSEL, on_yield=perturb(at, put(added)))
                self.assertEqual(char.writes, MAYSEL_WRITES, (at, added))
                self.assertEqual(char.coins(), 1 + COIN_COUNT, (at, added))

    def test_refusal_is_retryable_once_and_d_stays_read_only(self):
        char = maysel_char(free_slots=0, coin_rows=[row(expire=FUTURE)])
        for _ in range(2):
            self.assert_refused(char, click(char, MAYSEL), NO_ROOM)
        char.inv[char.inv.index(row(expire=FUTURE))] = None  # coin expired and was removed
        click(char, MAYSEL)
        self.assertEqual(char.writes, MAYSEL_WRITES)
        probes = char.probes
        for npc in (MAYSEL, MAYSEL, SHASHA):
            run = click(char, npc)
            self.assertNotIn(UNSUPPORTED, run.mes)
        self.assertEqual(char.writes, MAYSEL_WRITES, "D repeats never reach the probe or rewards")
        self.assertEqual(char.probes, probes)

    def test_late_exp_capacity_loss_is_held_not_replayed(self):
        char = maysel_char(free_slots=0, coin_rows=[row(amount=STACK_CAP - COIN_COUNT)])
        run = click(char, MAYSEL, on_write=after_write(
            "getexp", lambda c: c.inv[c.inv.index(row(amount=STACK_CAP - COIN_COUNT))].update(
                amount=STACK_CAP - 1)))
        self.assertEqual(char.writes, MAYSEL_WRITES)
        self.assertEqual(tuple_of(char), (2, -1, -1, 1))
        self.assertIn(HELD, run.mes)
        for _ in range(2):
            click(char, MAYSEL)
        self.assertEqual(char.writes, MAYSEL_WRITES, "no replay")


# --------------------------------------------- D: presentation, exits

class PresentationTests(unittest.TestCase):
    def test_initial_roles_come_from_the_text(self):
        self.assertEqual(dict(initial_cloaks()), {ARRIVAL: False, SHASHA: False, MAYSEL: False,
                                                  EST: True, DEBRIS: True})
        char = Character(1, {})
        self.assertEqual(scene(char), SCENE_DEFAULT)

    def test_two_character_masks(self):
        world = World()
        one = Character(250, STAGE_B, world=world)
        two = Character(250, STAGE_C, world=world)
        three = Character(250, {}, world=world)
        arrive(one)
        arrive(two)
        self.assertEqual((scene(one), scene(two), scene(three)),
                         (SCENE_B, SCENE_C, SCENE_DEFAULT))
        click(one, SHASHA)
        self.assertEqual((scene(one), scene(two), scene(three)),
                         (SCENE_C, SCENE_C, SCENE_DEFAULT))
        click(two, MAYSEL)
        self.assertEqual((scene(one), scene(two)), (SCENE_C, SCENE_DEFAULT))
        self.assertFalse(any(c[0] == "global" for c in world.calls),
                         "no global toggle during attached play")
        self.assertTrue(all(c[2] in (one.char_id, two.char_id) for c in world.calls
                            if c[0] != "global"))

    def test_map_change_resets_and_arrival_restores(self):
        char = shasha_char()
        char.move("ygg_edge")
        self.assertEqual(scene(char), SCENE_DEFAULT)
        char.move("ygg_fruit")
        arrive(char)
        self.assertEqual(scene(char), SCENE_B)

    def test_sync_is_idempotent(self):
        char = maysel_char()
        for _ in range(3):
            arrive(char)
            click(char, SHASHA)
        self.assertEqual(scene(char), SCENE_C)

    def test_est_is_inert(self):
        for combo, quests in combos():
            char = Character(250, quests)
            run = click(char, EST)
            self.assertEqual((char.writes, run.mes, run.talk, run.yields), ([], [], [], 0))

    def test_debris_is_bounded_self_only_flavor(self):
        for combo, quests in combos():
            seen = tuple(Character(0, quests).checkquest(q) for q in GUARDED)
            char = Character(250, quests)
            run = click(char, DEBRIS)
            self.assertEqual((char.writes, run.mes, run.yields), ([], [], 0))
            self.assertEqual(len(run.talk), 1 if classify(*seen) == "shasha_done" else 0, combo)
            sentinels_ok(self, char)

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

    def test_warps_are_unchanged_unconditional_routes(self):
        text = EDGE.read_text(encoding="utf-8")
        for line in ("ygg_edge,164,140,0\twarp\tROSOLO_CH1_EDGE_IN\t1,1,ygg_fruit,73,117",
                     "ygg_fruit,71,114,0\twarp\tROSOLO_CH1_FRUIT_OUT\t1,1,ygg_edge,168,139",
                     "ygg_edge,216,91,0\tscript\t回程#ROSOLO_CH1_RET\tGATE_SKYBLUE,1,1,{\n\tend;\n\n"
                     "OnTouch:\n\twarp \"prt_fild05\",353,248;\n\tend;\n}"):
            self.assertIn(line, text)
        decls = declarations(text)
        warps = [(d[0], d[3]) for d in decls if d[1] == "warp"]
        self.assertEqual(len(warps), 2)
        for _, w4 in warps:
            self.assertEqual(len(w4.split(",")), 5)  # no body, no condition


# --------------------------------------------- E: full room and controls

class RoomTests(unittest.TestCase):
    def test_ordinary_room_from_registration_to_18371(self):
        char = Character(250, map="prt_fild05")
        Run(char, [1, 1]).execute()
        self.assertEqual(char.warps, [FIRST_DEST])
        char.move("ygg_fruit")  # walked past the Messenger: arrival fallback
        arrive(char)
        self.assertEqual(scene(char), SCENE_B)
        click(char, SHASHA)
        self.assertEqual(scene(char), SCENE_C)
        click(char, DEBRIS)
        click(char, MAYSEL)
        self.assertEqual(tuple_of(char), (2, -1, -1, 1))
        self.assertEqual(char.writes, [("setquest", ENTRY)] + EDGE_WRITES + SHASHA_WRITE
                         + MAYSEL_WRITES)
        char.move("prt_fild05")
        Run(char, [1]).execute()
        self.assertEqual(char.warps, [FIRST_DEST, REPEAT_DEST])
        sentinels_ok(self, char, rewarded=True)


class MutationControlTests(unittest.TestCase):
    """Edited copies of the real text must fail the same contract checks."""

    def mutate(self, path, old, new, index=0, count=1):
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text, "mutation target must exist")
        return script_lines(path, index, text.replace(old, new, count))

    def mutate_fruit(self, npc, old, new, count=1):
        text = FRUIT.read_text(encoding="utf-8")
        start = text.index("\t" + npc + "\t")
        end = text.index("\n}\n", start)
        self.assertIn(old, text[start:end], "mutation target must exist")
        part = text[start:end].replace(old, new, count)
        return fruit_lines(npc, text[:start] + part + text[end:])

    def test_missing_completequest_readback_would_write_b(self):
        text = EDGE.read_text(encoding="utf-8")
        start = text.index("\tcompletequest 18368;\n") + len("\tcompletequest 18368;\n")
        end = text.index("\tsetquest 18369;\n")
        self.assertIn("goto L_NotCompleted;", text[start:end])
        lines = script_lines(EDGE, 0, text[:start] + text[end:])  # drop reads and checks
        char, run = messenger(200, {ENTRY: ACTIVE}, faults={("completequest", ENTRY)}, lines=lines)
        self.assertNotEqual(char.writes, [("completequest", ENTRY)], "control must differ")
        self.assertEqual(tuple_of(char), (1, 1, -1, -1))

    def test_partial_precondition_would_admit_active_active(self):
        lines = self.mutate(EDGE, "if (.@a != 1 || .@b != -1 || .@c != -1 || .@d != -1) goto L_Other;",
                            "if (.@a != 1) goto L_Other;")
        self.assertIn("if (.@a != 1 || .@b != -1 || .@c != -1 || .@d != -1) goto L_Changed;", lines)
        lines = [l.replace(" || .@b != -1 || .@c != -1 || .@d != -1", "") for l in lines]
        char, run = messenger(200, {ENTRY: ACTIVE, SECOND: ACTIVE}, lines=lines)
        self.assertTrue(char.writes, "control must differ from the real file")

    def test_three_id_messenger_would_mutate_beside_d(self):
        lines = [l.replace(" || .@d != -1", "").replace(" && .@d == -1", "")
                 for l in script_lines(EDGE, 0)]
        lines = [l for l in lines if l != ".@d = checkquest(18371);"]
        char, run = messenger(200, {ENTRY: ACTIVE, FOURTH: ACTIVE}, lines=lines)
        self.assertEqual(char.writes, EDGE_WRITES, "control must differ from the real file")

    def test_three_id_starter_would_register_beside_d(self):
        lines = self.mutate(NPC, "if (.@a == -1 && .@b == -1 && .@c == -1 && .@d == -1) return 0;",
                            "if (.@a == -1 && .@b == -1 && .@c == -1) return 0;")
        char, run = talk(250, {FOURTH: ACTIVE}, choices=[1, 1], lines=lines)
        self.assertEqual(char.writes, [("setquest", ENTRY)], "control must differ")

    def test_partial_final_postcondition_would_claim_success(self):
        lines = self.mutate(EDGE, "if (.@a != 2 || .@b != 1 || .@c != -1 || .@d != -1) goto L_Hold;",
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

    def test_partial_arrival_gate_would_write_beside_d(self):
        lines = self.mutate_fruit(
            ARRIVAL, "if (.@a != 1 || .@b != -1 || .@c != -1 || .@d != -1) goto L_Present;",
            "if (.@a != 1) goto L_Present;")
        char = Character(1, {ENTRY: ACTIVE, FOURTH: ACTIVE})
        arrive(char, lines=lines)
        self.assertTrue(char.writes, "control must differ from the real file")

    def test_missing_shasha_yield_rechecks_would_write_stale(self):
        text = FRUIT.read_text(encoding="utf-8")
        start = text.index("\t" + SHASHA + "\t")
        end = text.index("\n}\n", start)
        part = text[start:end]
        recheck = "\t.@state = callsub(L_State);\n\tif (.@state != 4) goto L_Changed;\n"
        final = "\tif (.@a != 2 || .@b != 1 || .@c != -1 || .@d != -1) goto L_Changed;\n"
        self.assertEqual(part.count(recheck), 6)
        self.assertEqual(part.count(final), 1)
        part = part.replace(recheck, "").replace(final, "")
        lines = fruit_lines(SHASHA, text[:start] + part + text[end:])
        for at in (1, 4, 7):
            real = shasha_char()
            click(real, SHASHA, on_yield=perturb(at, set_quest(SECOND, COMPLETE)))
            self.assertEqual(real.writes, [], "real file refuses")
            char = shasha_char()
            click(char, SHASHA, lines=lines, on_yield=perturb(at, set_quest(SECOND, COMPLETE)))
            self.assertEqual(char.writes, SHASHA_WRITE, "control must differ from the real file")

    def test_missing_maysel_readback_would_reward_a_noop(self):
        lines = self.mutate_fruit(
            MAYSEL, "\tif (.@a == 2 && .@b == -1 && .@c == 1 && .@d == -1) goto L_NotChanged;\n"
                    "\tif (.@a != 2 || .@b != -1 || .@c != -1 || .@d != 1) goto L_Hold;\n", "")
        char = maysel_char(faults={("changequest", THIRD)})
        click(char, MAYSEL, lines=lines)
        self.assertEqual(char.writes, MAYSEL_WRITES, "control must differ from the real file")

    def test_missing_preflight_would_change_quest_with_a_full_bag(self):
        lines = maysel_variant((CAP, ""))
        char = maysel_char(free_slots=0)
        click(char, MAYSEL, lines=lines)
        self.assertEqual(tuple_of(char), (2, -1, -1, 1), "control must differ from the real file")

    def test_retained_legacy_and_loses_a_native_positive(self):
        kw = EXISTING_COIN_CASES["earlier incompatible full, later compatible fit, full bag"][0]
        real = maysel_char(**kw)
        click(real, MAYSEL)
        self.assertEqual(real.writes, MAYSEL_WRITES, "real file rewards")
        char = maysel_char(**kw)
        run = click(char, MAYSEL, lines=maysel_variant((CAP, CAP + LEGACY_AND)))
        self.assertEqual(char.writes, [], "control must differ: legacy AND refuses")
        self.assertIn(NO_ROOM, run.mes)

    def test_truthy_minus_one_would_progress(self):
        for variant in ((CAP_LINES[2], ""),
                        (CAP_LINES[1] + CAP_LINES[2], "\tif (.@cap == 0) goto L_NoRoom;\n")):
            char = maysel_char(capacity=-1)
            click(char, MAYSEL, lines=maysel_variant(variant))
            self.assertEqual(tuple_of(char), (2, -1, -1, 1), "control must differ: -1 is truthy")
            self.assertEqual(char.exp_calls, [(BASE_EXP, JOB_EXP)])

    def test_zero_dispatch_is_causal(self):
        char = maysel_char(capacity=0)
        run = click(char, MAYSEL, lines=maysel_variant((CAP_LINES[1], "")))
        self.assertIn(UNSUPPORTED, run.mes, "without the 0 branch a full bag is misreported")

    def test_gate_after_progression_would_lose_c(self):
        lines = maysel_variant((CAP, ""), (D_READBACK, D_READBACK + CAP))
        char = maysel_char(free_slots=0)
        run = click(char, MAYSEL, lines=lines)
        self.assertIn(NO_ROOM, run.mes)
        self.assertEqual(tuple_of(char), (2, -1, -1, 1), "control must differ: C not kept")

    def test_missing_delivery_check_would_claim_success(self):
        lines = self.mutate_fruit(MAYSEL, "\tif (.@after != .@coin + 10) goto L_RewardHold;\n", "")
        char = maysel_char(faults={("getitem", COIN)})
        run = click(char, MAYSEL, lines=lines)
        self.assertIn(MAYSEL_OK, run.mes, "control must differ from the real file")

    def test_missing_map_check_would_cloak_off_map(self):
        lines = self.mutate_fruit(SHASHA, '\tif (strcharinfo(3) != "ygg_fruit") return;\n', "")
        char = shasha_char()
        mark = []

        def leave(run, ch, kind):
            if kind == "close2":
                mark.append(len(ch.world.calls))
                ch.move("ygg_edge")
        click(char, SHASHA, lines=lines, on_yield=leave)
        self.assertTrue(char.world.calls[mark[0]:], "control must differ from the real file")

    def test_unsupported_command_fails_loudly(self):
        lines = self.mutate(EDGE, "\tcompletequest 18368;\n", "\tgetitem 501,1;\n")
        with self.assertRaises(AssertionError):
            messenger(200, {ENTRY: ACTIVE}, lines=lines)
        lines = self.mutate_fruit(DEBRIS, '\tnpctalk "', '\tunitwalk 1,1;\n\tnpctalk "')
        with self.assertRaisesRegex(AssertionError, "unmodeled statement"):
            click(Character(1, STAGE_C), DEBRIS, lines=lines)

    def test_undeclared_cloak_target_fails_loudly(self):
        lines = self.mutate_fruit(SHASHA, '"Est#ROSOLO_CH1_EST"', '"Est#c1p1est01"')
        char = shasha_char()
        with self.assertRaisesRegex(AssertionError, "cloak target not declared"):
            click(char, SHASHA, lines=lines)

    def test_malformed_debugmes_is_rejected(self):
        lines = script_lines()
        for invalid in ("debugmes root_unknown();", 'debugmes "unterminated"'):
            changed = [invalid if line.startswith("debugmes ") else line for line in lines]
            with self.assertRaisesRegex(AssertionError, "unsupported debugmes form"):
                talk(200, {ENTRY: COMPLETE}, lines=changed)

    def test_unsupported_oninit_command_is_rejected(self):
        for body in all_bodies():
            if "OnInit:" not in body:
                continue
            index = body.index("OnInit:") + 1
            changed = body[:index] + ["root_unknown_command;"] + body[index:]
            with self.assertRaisesRegex(AssertionError, "unsupported OnInit form"):
                Run(Character(200), lines=changed)

    def test_malformed_oninit_questinfo_is_rejected(self):
        for body in all_bodies():
            if not any(line.startswith("questinfo(") for line in body):
                continue
            changed = [line[:-1] if line.startswith("questinfo(") else line for line in body]
            with self.assertRaisesRegex(AssertionError, "unsupported OnInit form"):
                Run(Character(200), lines=changed)


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    unittest.main(verbosity=2)
