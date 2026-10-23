# Chapter 1 starter branch mod (T10.007)

`chapter1_entry/ro-solo-ch1-entry/` is a small rAthena mod for the retained
Ragnarok Offline v1.6.3 mod layout. One NPC on `prt_fild05` lets a BaseLevel
200+ character register, cancel or resume quest **18368** 「天地樹的召喚(1)」.
It adds QUEST_DB definitions for 18368, 18369 and 18370 so the server knows the
IDs the client quest log already describes. It is one functional step toward
the full Modern/Renewal game, not Chapter 1: no route to the village, no
18368 → 18369 → 18370 transition, no rewards.

```
ro-solo-ch1-entry/
├── mod.json           name = folder, requires app >=1.6.3, era renewal
├── npc/entry.txt      the NPC; assembled as npc/mods/ro-solo-ch1-entry/entry.txt
└── db/quest_db.yml    QUEST_DB v3, three Id/Title rows; assembled into db/import/quest_db.yml
```

All three files are UTF-8 without BOM, LF line ends. No regional client is
required: the dialogue is plain UTF-8 Traditional Chinese, as in the existing
`tw-carocc-pilot` mod, and the quest log text comes from the client's own
18368 row by ID.

## The NPC

`梧桐枝#ROSOLO_CH1`, sprite `4_CH1_BRANCH`, at `prt_fild05,353,252` facing 4:
the client log target of 18368 and the A01 entry guide. Whether that cell is
walkable and reachable for an ordinary player is a Root check, not proved here.
The `ROSOLO_CH1` identity was absent from the retained 1,185-file NPC corpus
(literal search; not live memory). The 20-byte UTF-8 full name fits rAthena's
24-byte `NAME_LENGTH`.

State is read only with default `checkquest` (HAVEQUEST). On the pinned
rAthena 0693b8c `quest_check` returns -1 absent, **1 for active and for
inactive**, 2 complete. `doc/script_commands.txt` says inactive is 0; the
script follows the code and compares only against -1, 1 and 2. Any other
value is unknown.

Evaluate this table from top to bottom; the first matching row applies.

| 18368 | 18369 | 18370 | Class | What the NPC does |
| --- | --- | --- | --- | --- |
| any unknown value in any guarded ID | | | conflict | refuse, server `debugmes`, no write |
| -1 | -1 | -1 | fresh | Level < 200: refuse, no menu. 200+: continue/cancel menu |
| 1 (active or inactive) | -1 | -1 | in progress | Show title and objective; no write, any level |
| 1 | either later ID present | | conflict | refuse, server `debugmes`, no write |
| any | 1 | present | conflict | refuse, server `debugmes`, no write |
| 2 | any of -1/1/2 | any of -1/1/2 | preserved | "already answered"; no write |
| -1 | either later ID present | | preserved | same (a later script may use changequest) |

Continue path: after `select` yields to the client the script re-reads all
three quests and BaseLevel. Only if the character is still fresh and 200+ does
it run `setquest 18368` — the only write in the file, reached once per
interaction. `setquest` returns script success even when `quest_add` fails (DB
row missing, already present), so the script reads 18368 back: 1 with both
later IDs absent is success; -1 is a reported failure ("任務沒有被記錄",
`ROSOLO_CH1: setquest 18368 was not recorded` in the map-server log) and a
later visit retries cleanly; anything else is the conflict diagnostic.

Cancel, closing the dialog, refusal and every non-fresh class write nothing.
Repeating any action is idempotent: a registered character always lands in
"in progress". The script uses no `completequest`, `erasequest`, `changequest`,
warp, item, EXP or zeny command and never reads or writes 18371, 24069 or any
other quest.

Durable state is the character's quest log only. The script declares no
permanent character, account (`#`, `##`), global (`$`) or NPC (`.`) variable;
`.@` scope variables die with the dialog. With one record per character there
is no multi-write to tear and nothing to recover beyond the quest row itself.
The referenced schema keys quest rows by `char_id`; actual two-character
isolation is still an integration check below.

`OnInit` adds a yellow quest bubble while the character is 200+ and all three
IDs are absent; `setquest` refreshes bubbles. It writes nothing.

Text: the NPC uses only short original wording, the 18368 title and its
objective 「前往梧桐村」 (bytes match the audited client row). The long client
description, 18369/18370 objectives and village dialogue are not copied. The
menu shows 「回應呼喚」/「先離開」, no IDs or jargon.

## QUEST_DB rows

`Header: Type QUEST_DB, Version 3`, then `Body:` with exactly 18368, 18369 and
18370, each `Id` and audited `Title` only. No `Clear`, no `Footer`, no
targets, time limit or rewards. The file name must be `db/quest_db.yml`: the
app copies a mod's `db/` over the seeded `db/import` stubs and, when a second
mod ships the same table, merges bodies (`merge_tables`, which carries a
`Clear: true` across, so the merged table must be checked). 18369/18370 are
defined only so a later owner can use them; no script here reaches them.

## Checks run in the task worktree (source only)

```sh
python3 -I -B tools/renewal/test_chapter1_entry.py
```

21 standard-library tests, under a second. Static: exact package files,
mod.json fields, UTF-8/LF/no BOM, NPC header and name length, brace balance,
QUEST_DB shape and title hashes, short-text reuse and no copied prose, plain
menu, forbidden command/word checks, guarded IDs only, `.@`-only variables, explicit
`checkquest` comparisons, recheck between menu and `setquest`, read-back.
Modeled: an authored interpreter for the script subset the real `entry.txt`
uses runs the actual file against a modeled quest log (pinned `quest_check`
and `quest_add` behaviour): 199/200/201, cancel/retry, state changes during
the menu, failed `setquest`, active/inactive resume, every combination of
absent/inactive/active/complete/unknown for the three IDs at three levels and
both choices, two characters. The model is not the rAthena parser and proves
nothing about persistence, the client or real play.

## Root verification recipe (all UNRUN by the worker)

Use a disposable server, never the installed app's database. Keep a tested
external-state backup of the target characters' `quest` and `char_reg_num`
rows and the app state `mods/`, `enabled.txt`, `disabled.txt` before any
installed step.

1. **Assembly.** Copy `ro-solo-ch1-entry/` into the disposable state `mods/`.
   After assembly expect `npc: npc/mods/ro-solo-ch1-entry/entry.txt` in the
   generated map conf import and the three rows in the assembled
   `db/import/quest_db.yml`, with every other mod's rows kept and no inherited
   `Clear: true`. The app must not report the mod as refused.
2. **Isolated parser and definitions.** `map-server --run-once` initializes
   SQL and NPC OnInit; it is not a pure syntax check. Use a newly owned SQL
   container/data volume and one-shot map container on a fresh private network,
   no published ports or live DB mounts. Pin same-image SQL/config/import
   inputs. Replace the Renewal NPC selector with an owned selector: map config
   `npc: clear` alone is followed by the stock `npc/re/scripts_main.conf` load.
   Preserve required nonquest import stubs if mounting a whole import directory.
   Confirm no causal error/warning and positively prove the owned NPC loaded,
   e.g. an isolated audit OnInit resolves its exact name with `getnpcid`.
   Independently establish all three quest definitions. Registration of18368
   or `checkquest` for absent later IDs cannot prove18369/18370 definitions.
   A source-qualified per-file accepted count of3 over exactly the three unique
   pinned nodes, with no later import/override, is insertion inference; retain
   that distinction. On disposable attached characters later, register each
   ID through an audit-only fixture and verify per-ID success/readback and SQL
   rows. Such fixture grants are not earned story progression.
   Use separate fresh negative fixtures: remove the exact semicolon from
   `setquest 18368;` and require a causal parser diagnostic for that file; use
   a noninteger quest Id and require a causal YAML/DB refusal. Do not assume a
   particular diagnostic prefix or count log silence/exit0 as a pass. Also
   remove18368 from a separate DB fixture before the failed-registration case:
   Continue must report failure, with the native quest-add diagnostic and
   `ROSOLO_CH1` log line, leaving no saved quest row. No real parser case has
   been run for this component yet.
3. **Interaction**, fresh disposable characters, levels set with GM commands:
   199 refuses with no menu; 200 and 201 show the menu; cancel leaves no row;
   continue adds one 18368 row (`SELECT char_id, quest_id, state FROM quest
   WHERE quest_id IN (18368,18369,18370)`) and the client log shows the TC
   title/description/objective; talking again resumes; toggle 18368 inactive
   in the quest window and talk — still resume, state stays inactive.
4. **Guards.** With the character offline, insert 18368 complete, then
   separately 18369/18370 rows, into the disposable DB: the NPC must leave
   every row byte-identical. Plant 18368 active + 18369 to see the conflict
   text and `debugmes`. Confirm `char_reg_num` has no `rosolo_ch1%` key.
5. **Persistence.** Relog and restart the map and char servers; rows and
   resume behaviour persist. A second character on the same account is still
   fresh.
6. **Ordinary play.** Reach the NPC without GM warp. Reaching it by GM command
   is a fixture, not earned play. The village, transitions and rewards stay
   open work.

## Install and rollback

This component is not installed or ready for user evaluation. After the gates
above pass, the supported installation is the enabled folder in the app's user
`mods/`, followed by the normal rebuild/restart; folder name is its identity.

Source rollback uses `git revert` on the integration commit. It does not restore
or safely migrate installed definitions, saves, settings or merged imports.
Do not automatically deploy that revert to an app that has earned these quests.

For an installed operational rollback, first verify an NPC-withdrawal revision
on isolated state: keep the mod enabled with the same compatible DB definitions
and metadata, withdraw only its NPC source/directive, rebuild and restart.
Require positive NPC absence, retained definitions and unchanged earned quest
records/unrelated progress. Keep that separately verified retention revision
available before installation. Disabling/removing the entire mod would remove
its definitions and is not this progress-preserving procedure. Do not delete
quest rows or restore an older character snapshot merely to undo this NPC.
Undefined-ID behavior and any future definition migration require their own
tested recovery plan. Actual operational rollback is still UNRUN.
