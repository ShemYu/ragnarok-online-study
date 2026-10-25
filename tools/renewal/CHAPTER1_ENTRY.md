# Chapter 1 starter branch, first edge and fruit village (T10.007, T10.009, T10.010, T10.010.001, T10.010.002)

`chapter1_entry/ro-solo-ch1-entry/` is a small rAthena mod for the retained
Ragnarok Offline v1.6.3 mod layout, version **0.3.2**. A BaseLevel 200+
character registers quest **18368** 「天地樹的召喚(1)」 at a branch on
`prt_fild05`, travels to `ygg_edge`, and a Messenger there completes 18368
and starts **18369** 「天地樹的召喚(2)」. On `ygg_fruit`, 莎莎 (Shasha)
replaces 18369 with **18370** 「天地樹的召喚(3)」, and 梅雪 (Maysel)
replaces 18370 with **18371** 「扭曲的黑暗之地」 and gives the source's native
reward. Two ordinary warps link `ygg_edge` and `ygg_fruit`, and a gate returns
to `prt_fild05`. QUEST_DB definitions for 18368–18371 let the server know the
IDs the client quest log already describes.

This is one functional room, a step toward the full Modern/Renewal game. It is
not Chapter 1: it stops at the 18371 objective (the Twisted Land of Darkness).
No transport there, no later quest, no Naviel, no party adaptation.

```
ro-solo-ch1-entry/
├── mod.json               name = folder, version 0.3.2, requires app >=1.6.3, era renewal
├── npc/entry.txt          starter branch
├── npc/first_edge.txt     Messenger + three connections (connections unchanged)
├── npc/fruit_village.txt  arrival event, Shasha, Maysel, Est, Debris (new)
└── db/quest_db.yml        QUEST_DB v3, four Id/Title rows (three unchanged, 18371 added)
```

**Native prerequisite (0.3.2).** Maysel calls the new builtin
`ros_ch1_coin_capacity()`, added by
[`native_capacity/coin_capacity.patch`](native_capacity/README.md). Stock
server binaries do not register it and cannot load `fruit_village.txt`; the
patched map server must be built, installed and parser-checked first. That is
a separate Root installation gate, not covered by any source check here.

All files are UTF-8 without BOM, LF line ends. The app assembler emits one
`npc:` line per `.txt` under the mod's `npc/` folder, so the three NPC files
are separate script files, not duplicates.

## Quest state

State is read only with default `checkquest` (HAVEQUEST). On the pinned
rAthena 0693b8c `quest_check` returns -1 absent, **1 for active and for
inactive**, 2 complete; any other value is unknown and refused. Donor
`isbegin_quest` (absent = 0) is not used. Tuples are (18368, 18369, 18370,
18371) and **every gate reads all four**, including fresh registration,
Messenger, arrival and travel. Every script that classifies uses the same
`L_State` text:

| Code | Tuple | Meaning |
| --- | --- | --- |
| 0 | (-1,-1,-1,-1) | fresh |
| 1 | (1,-1,-1,-1) | A stage: Messenger or checked arrival fallback |
| 4 | (2,1,-1,-1) | first edge done: Shasha may replace B with C |
| 6 | (2,-1,1,-1) | Shasha done: Maysel may replace C with D |
| 7 | (2,-1,-1,1) | room done: no new reward or progression |
| 5 | (2,-1,-1,-1) | genuine interrupted first edge: held, never repaired |
| 3 | any unknown value; 18368 open with a later ID; 18369 open with 18370/18371; 18370 open with 18371 | conflict: refused and logged, no write |
| 2 | everything else | other progress: preserved, no write |

Native `quest_change` replaces the source slot with an active destination; the
old ID is absent afterwards. That is the history rule for B→C and C→D, so
"B absent, C active" is the expected record, not a loss. Unknown or later
tuples are preserved, not reset or called corrupt. Durable state is the
quest log only: no permanent character, account, global or NPC variable.

## Starter branch `梧桐枝#ROSOLO_CH1`

Unchanged behaviour for the old stages, read with D:

| Class | What the NPC does |
| --- | --- |
| conflict | refuse, `debugmes`, no write |
| fresh | < 200: refuse. 200+: continue/cancel menu, recheck, `setquest 18368`, four-ID readback |
| A, B, C, D stage | title of the open quest; 200+: travel menu → `ygg_edge,212,95` |
| interrupted | hold, `debugmes`, no travel, no repair |
| other | "already answered", no write, no travel |

A registration verified in this invocation still lands at `ygg_edge,255,240`.
Every travel path re-reads the tuple and BaseLevel after the menu and again
after `close2`; the class must still be the one that offered travel.
D present blocks fresh registration (an old three-ID test would register).

## Messenger `信使#ROSOLO_CH1_MSG`

As in T10.009, with D read in every check: only (1,-1,-1,-1) starts the edge;
completequest/readback (2,-1,-1,-1), setquest/readback (2,1,-1,-1), no yield
in between. C/D stages get a plain reply; conflicts are logged.

## Fruit village (`npc/fruit_village.txt`)

`fruit` means `ygg_fruit`.

| Identity | Cell / facing | Sprite | Role |
| --- | --- | --- | --- |
| `#ROSOLO_CH1_ARR` | 73,117 /0, touch 1,1 | `HIDDEN_WARP_NPC` | arrival event (not a warp) |
| `莎莎#ROSOLO_CH1_SHA` | 80,122 /3 | `4_CH1_DELEGACY01` | B→C conversation |
| `梅雪#ROSOLO_CH1_MAY` | 82,120 /3 | `4_F_MAYSEL` | C→D conversation and reward |
| `Est#ROSOLO_CH1_EST` | 77,117 /1 | `4_F_ESTLOVELOY` | inert; `OnInit: cloakonnpc;` |
| `Debris#ROSOLO_CH1_DEB` | 77,124 /4 | `4_LGTSCIENCE` | `OnInit: cloakonnpc;`; one self-only line at C |

**Sprite discrepancy.** Shasha uses `4_CH1_DELEGACY01` from the pinned mechanics
reference (chapter1.txt 155). The retained client navigation row for 18369 says
`4_CH1_DELEGACY02`. The sources do not agree; the client table is not changed.
Asset and render checks belong to Root.

**Arrival.** Only (1,-1,-1,-1) runs the Messenger's checked sequence:
recheck, `completequest 18368`, readback, `setquest 18369`, readback, with no
yield. (1,-1,-1,-1) after the first write is a reported retry; (2,-1,-1,-1)
is held; anything else is a logged hold. A-complete/B-absent is never
repaired. Other tuples write nothing and only synchronise presentation.

**Shasha.** Starts only at (2,1,-1,-1). Seven dialogue yields (six `next`, one
single-option `select`), each followed by a full recheck; a change means no
write. After the last page: four reads, require (2,1,-1,-1),
`changequest 18369,18370`, four reads. Unchanged (2,1,-1,-1) is an honest
retryable failure; anything except (2,-1,1,-1) is a hold. No reward. The
replacement and its readback happen before the final `close2`; after it the
script re-reads state and map, then synchronises presentation. C/D repeats
re-synchronise and reply; they never replace or reward.

**Maysel.** Starts only at (2,-1,1,-1); B stage gets "talk to Shasha first".
Twelve yields (eight `next`, four single-option `select`), each rechecked.
Cancel at any of them writes nothing. Then, with no menu or yield:

1. four reads, require (2,-1,1,-1);
2. `.@cap = ros_ch1_coin_capacity()`, dispatched explicitly: `0` (native
   capacity refusal: weight, stack limit, full compatible stack or no usable
   blank) gives the ordinary "make room" reply; anything other than `1`
   (`-1`: unsupported actor, alias or item configuration) gives a separate
   short reply that capacity could not be confirmed, no reward was attempted
   and the quest is unchanged. Both keep C and grant nothing. Only `1`
   continues, with no new yield. See [native coin capacity](#native-coin-capacity-t10010002);
3. `countitem` before (quantity snapshot);
4. `changequest 18370,18371`, four reads; unchanged C is a retryable failure,
   anything except (2,-1,-1,1) a hold; no reward either way;
5. `getexp 65304744,4000000`, then `getitem "Ch1_Root_Coin",10`, once each;
6. `countitem` after and four reads; the coin delta must be exactly 10 and the
   tuple (2,-1,-1,1). Otherwise the reply says delivery was not confirmed,
   the record is kept and nothing is re-sent;
7. success page names 18371 and its objective, `close2`, then presentation.

`Ch1_Root_Coin` is source-bound to item 1001972, weight 1; the installed item
DB/resource identity is a Root gate. EXP uses native rules (quest rate, boosts,
caps, level-ups), so the source amounts are not raw bar deltas, and EXP is not
read back. Level-up effects are expected, not corruption.

**Not a transaction.** Quest replacement, status and inventory are saved
separately, and a failed script command logs and continues. Preflight and
readback reduce ordinary failures; they do not make a crash atomic. A D state
with uncertain delivery stays as it is for Root review: no automatic replay,
guessed compensation, rollback to C, marker or old-save restore.

### Native coin capacity (T10.010.002)

The builtin asks the same native destination decision `getitem` uses.
`pc_additem_plan` is the read-only part of `pc_additem` extracted unchanged:
it scans the whole physical inventory, and the **first** row matching ID,
bound, zero expiry, unique ID and all card bytes decides (merge, or refusal
if that stack is full or beyond the usable slots, even when a later row or
blank fits); only when no row matches does the first physical blank decide.
`pc_additem` and `pc_ch1_coin_capacity` both call it, so the probe cannot
drift from the real add. The probe performs the same early weight/stack
checks without generating unique IDs and changes nothing. A full bag with a
fitting compatible stack, and an earlier incompatible full row followed by a
fitting compatible one, are positives again.

The probe is exact only at the moment it runs. The `getexp` callbacks that
follow can still change the inventory, so the late delivery check and honest
hold stay (no reservation, compensation or replay).

History: 0.3.0 used `checkweight` (`pc_checkadditem`, first same-ID row,
metadata ignored), which passed incompatible-row bags that the add then
refused, and refused earlier-incompatible/later-compatible bags the add would
accept. The interim 0.3.1 (T10.010.001) refused **any** carried coin before
`checkweight`; that narrowed valid compatible-stack positives and is removed in
0.3.2, together with `checkweight` itself (keeping it as an extra AND would
still lose the earlier-incompatible/later-compatible positive).

**Presentation.** `L_Sync` (same text in arrival, Shasha, Maysel) runs only on
`ygg_fruit` and reads a fresh tuple, then issues character-scoped
`cloakonnpc`/`cloakoffnpc <name>,getcharid(0)`:

| Stage | Maysel | Est | Debris |
| --- | --- | --- | --- |
| B | hidden | shown | shown |
| C | shown | hidden | shown (the reference's explicitly custom C policy) |
| D | shown | hidden | hidden (initial roles) |
| other | no change | no change | no change |

It runs at arrival, at every ordinary Shasha interaction or repeat, and after
the final close of both verified transitions. Native personal masks reset on
map change and logout and never touch another player; there is no global
toggle during play (only `OnInit` sets Est/Debris cloaked). After a relog away
from the touch cell, the first ordinary Shasha interaction restores the scene.
Instant scene parity before any interaction is not claimed; there is no
login/quest-load ordering assumption, timer or map-load observer. Cloaking is
not a gate: a hidden NPC can still be clicked, so every consequential path
checks the quest log itself.

## Connections (unchanged)

| Identity | From | Trigger | To |
| --- | --- | --- | --- |
| `ROSOLO_CH1_EDGE_IN` warp | `ygg_edge,164,140` | 1,1 | `ygg_fruit,73,117` |
| `ROSOLO_CH1_FRUIT_OUT` warp | `ygg_fruit,71,114` | 1,1 | `ygg_edge,168,139` |
| `回程#ROSOLO_CH1_RET` `GATE_SKYBLUE` OnTouch | `ygg_edge,216,91` | 1,1 | `prt_fild05,353,248` |

None reads or writes a quest. The arrival trigger covers 72–74,116–118 and
does not overlap the fruit exit at 71,114.

## Text and rights

Short original Traditional Chinese wording that keeps the supported facts:
Shasha's welcome and role, the companions (Est leaves to investigate, Debris
analyses findings), Maysel's report on the parallel gates and a distorted
space, the danger of worlds colliding, and the next objective. 莎莎/梅雪 come
from the qualified Chinese rows; Est/Debris stay untranslated. Quest titles and
objectives reuse the audited client fields by hash. The donor script is an
inert reference whose README forbids redistribution: no donor prose, bodies,
helpers (`cloaknpc`, `dummynpc`), cutins or assets are copied. No publication
right is inferred.

## Checks run in the task worktree (source only)

```sh
python3 -I -B tools/renewal/test_chapter1_entry.py
```

Standard library only, about six seconds, 120 tests. The authored interpreter
runs the real NPC bodies of all three files against a modeled quest log
(quest_change/quest_add refusal rules, DB rows parsed from `quest_db.yml`),
a finite native-shaped inventory (rows with nameid/amount/bound/expiry/
unique ID/cards, usable slots and inaccessible indices; `countitem`,
a first-row `checkweight` kept for history, a metadata-matching `getitem`
and `ros_ch1_coin_capacity()` evaluated as that add on a copy or forced to
0/-1/other values, plus post-check delivery faults) and
per-character cloak masks (from the real `OnInit`). Covered: every one of
the 1296 stored four-ID combinations for the starter, Messenger, arrival,
Shasha, Maysel, Est and Debris; interference and cancel at every yield; no-op
and interfered writes; missing C/D definitions; full bag, no slot, full stack
and missing alias; the profile existing-coin cases plus two
earlier-incompatible/later-compatible cases (each now rewarded exactly when
the native add succeeds, else refused before any write; five compatible or
mixed positives restored); `-1`/other values refused before any write with
the separate reply; capacity read after the final yield; late EXP-time
capacity loss held without replay; D repeats never probe; bad post-item delivery and tuple; ordered rewards once and
no repeat; close interruption and relog recovery; map check; two characters;
C/D repeat travel versus the held partial; unchanged exits; exactly four DB
rows. Mutation controls show the checks fail without a readback, recheck,
preflight, delivery check, map check or D read, that a retained legacy
`checkweight` AND loses a native positive, that a truthy `-1` would progress,
that a missing `0` branch misreports a full bag, and that moving the probe
after the D write loses C. The native body itself is checked separately by
`native_capacity/test_coin_capacity.py` (host C++ differential, see its
README). The model is not the
rAthena parser and proves nothing about loading, cells, arrival, rendering,
EXP/item delivery, SQL persistence or the client.

## Root verification recipe (all UNRUN by the worker)

Use disposable state, never the installed app's database, with a tested
backup of target `quest`/`inventory`/`char` rows and the app's `mods/`,
`enabled.txt`, `disabled.txt`.

0. **Native patch.** Apply `native_capacity/coin_capacity.patch` to the
   installed build source, build and install the map server; prove the
   builtin registers (stock binaries fail to load the NPC).
1. **Assembly.** Three `npc:` lines; four DB rows merged without `Clear`;
   item `Ch1_Root_Coin`/1001972 present in the loaded item DB.
2. **Parser.** Load all three files plus a malformed control; prove the five
   fruit NPCs, both warps and both OnInit cloaks loaded.
3. **Cells and arrival.** OnTouch at 73,117 after the warp; actor cells.
4. **Client.** Chinese quest log for 18368–18371, DELEGACY01/02 choice, both
   new sprites, cloak/uncloak per character.
5. **Ordinary play.** A legitimately eligible 200+ character: arrival, Shasha,
   Maysel, actual EXP/coin delivery, repeats, return and repeat travel. No
   level/quest edits or fixtures. Separately confirm with the patched server: a full
   bag with a fitting compatible coin stack receives ten coins once; an
   actual no-fit refuses before quest/EXP changes; an unsupported setup shows
   the separate reply.
6. **Persistence.** Normal save/logout/re-entry with (2,-1,-1,1) durable,
   10 coins present, unrelated quests/items/zeny/skills unchanged.

## Install and withdrawal

Not installed or ready for user evaluation. After the gates pass, install as
the enabled folder in the app's user `mods/`, then the normal rebuild/restart.
`git revert` rolls back source only; it does not restore installed
definitions, saves, settings or merged imports.

Withdrawal keeps **all four** QUEST_DB definitions and **all three** exits
(both warps and the return gate) after any travel or progress. Reverting to
the old three-row 0.2.0 package is not a safe rollback for a D save: a quest
ID missing from the loaded DB is skipped on login and can later drop out of
the saved log. Withdraw the consequential actors instead (starter, Messenger,
arrival event, Shasha, Maysel; Est/Debris may go with them) by removing their
declarations, keep the connection lines and `quest_db.yml`, preserve all
progress, and rebuild through the supported path only in Root's later play
window. Do not delete quest rows, replay rewards or restore an older save.
Actual withdrawal is UNRUN.
