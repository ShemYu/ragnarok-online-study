# Chapter 1 starter branch and first story edge (T10.007, T10.009)

`chapter1_entry/ro-solo-ch1-entry/` is a small rAthena mod for the retained
Ragnarok Offline v1.6.3 mod layout. A BaseLevel 200+ character registers
quest **18368** 「天地樹的召喚(1)」 at a branch on `prt_fild05`, travels to
`ygg_edge`, and a Messenger there completes 18368 and starts **18369**
「天地樹的召喚(2)」. Two ordinary warps link `ygg_edge` and `ygg_fruit`, and a
gate returns to `prt_fild05`. QUEST_DB definitions for 18368, 18369 and 18370
let the server know the IDs the client quest log already describes.

This is the first story edge, one functional step toward the full
Modern/Renewal game. It is not Chapter 1: no 18369 → 18370 transition, no
`ygg_fruit` arrival event or next-room NPCs, no rewards.

```
ro-solo-ch1-entry/
├── mod.json             name = folder, requires app >=1.6.3, era renewal
├── npc/entry.txt        starter branch; assembled as npc/mods/ro-solo-ch1-entry/entry.txt
├── npc/first_edge.txt   Messenger + three connections; npc/mods/ro-solo-ch1-entry/first_edge.txt
└── db/quest_db.yml      QUEST_DB v3, three Id/Title rows (unchanged since T10.007)
```

All files are UTF-8 without BOM, LF line ends. No regional client is
required: dialogue is plain UTF-8 Traditional Chinese, as in the existing
`tw-carocc-pilot` mod, and the quest log text comes from the client's own
rows by ID. The app assembler emits one `npc:` line per `.txt` under the mod's
`npc/` folder, so `first_edge.txt` is a second script file, not a duplicate.

## Quest state

State is read only with default `checkquest` (HAVEQUEST). On the pinned
rAthena 0693b8c `quest_check` returns -1 absent, **1 for active and for
inactive**, 2 complete. `doc/script_commands.txt` says inactive is 0; both
scripts follow the code and compare only against -1, 1 and 2. Any other value
is unknown and refused. Tuples below are (18368, 18369, 18370).

Durable state is the character's quest log only. No permanent character,
account (`#`, `##`), global (`$`) or NPC (`.`) variable is declared; `.@`
scope variables die with the dialog, so "registered in this invocation" is
not a stored flag. No other quest, item, EXP, zeny or skill is touched;
18370 is never written.

## Starter branch `梧桐枝#ROSOLO_CH1`

Sprite `4_CH1_BRANCH`, `prt_fild05,353,252` facing 4. First matching row:

| Tuple | Class | What the NPC does |
| --- | --- | --- |
| any unknown value | conflict | refuse, `debugmes`, no write |
| (-1,-1,-1) | fresh | < 200: refuse, no menu. 200+: continue/cancel menu |
| (1,-1,-1) | in progress | title and objective, any level; 200+: travel menu → 212,95 |
| 1 with a later ID present | conflict | refuse, `debugmes`, no write (incl. active/active) |
| (any,1,present) | conflict | refuse, `debugmes`, no write |
| (2,1,-1) | edge done | 18369 in progress; 200+: travel menu → 212,95 |
| (2,-1,-1) | interrupted | hold, `debugmes`, no write, no travel, no repair |
| other recognised | preserved | "already answered"; no write, no travel |

Fresh path: after the registration `select` yields, the script re-reads all
three IDs and BaseLevel. Only if still fresh and 200+ does it run
`setquest 18368`. If another interaction registered 18368 meanwhile, it takes
the in-progress row (repeat destination), not the new-registration one.
`setquest` returns success even when `quest_add` fails, so all three IDs are
read back once: (1,-1,-1) is success; exactly (-1,-1,-1) is a reported,
retryable registration failure. Any other tuple gets a post-write hold that
says no further changes, without claiming the log is unchanged. Cancel
before registration writes nothing.

After a verified registration in this invocation the travel menu offers
「前往天地樹」/「稍後再去」. Deferring keeps 18368; it is not cancellation.
Travelling now goes to `ygg_edge,255,240`. Any later visit uses the repeat
destination `ygg_edge,212,95`. There is no Payon branch and no 194,97 route.

Every travel path re-reads the full tuple and BaseLevel after the travel
`select`, then again after `close2` (which waits for the button and lets the
script continue). The tuple class must still equal the one that offered
travel and the level must still be 200+; otherwise no warp (a `dispbottom`
line after `close2`). `warp` is the ordinary script command for the attached
player, immediately followed by `end`. A `warp` call is not proof of arrival.

`OnInit` adds a yellow bubble while 200+ and all three IDs are absent.

## Messenger `信使#ROSOLO_CH1_MSG`

Sprite `4_CH1_DELEGACY02`, `ygg_edge,253,246` facing 4. No level gate is
added; only the exact tuple (1,-1,-1), including inactive 18368, starts the
edge. After the one `next`:

1. read all three; require (1,-1,-1), else "changed", no write;
2. `completequest 18368` once; read all three; (1,-1,-1) → reported failure,
   18369 not set, later retry is clean; anything except (2,-1,-1) → hold;
3. `setquest 18369` once; read all three; (2,-1,-1) → interrupted partial,
   reported and held; anything except (2,1,-1) → hold; (2,1,-1) → success
   text and a direction toward the fruit (`ygg_fruit,80,122` objective).

No yield, helper, timer or warp sits between step 1's read and step 3's
read. No `changequest`, `erasequest`, reset, compensation or rollback; 18369
is never added first. Revisits: (2,1,-1) is a read-only "in progress" reply;
(2,-1,-1) is refused for every automatic write, at the Messenger and the
starter, and is not taken as proof this component completed it. Active/active,
later 18370 and unknown values are preserved and logged. No `navigateto` is
used: its availability depends on the server's `PACKETVER`, which the
supplied seam does not pin.

This is a checked, non-yielding, fail-closed sequence, **not** a transaction
or crash-atomic save. Quest changes are saved by separate operations; a
partial tuple must be reviewed by Root, never overwritten or replaced by an
older save.

## Connections

Unconditional, as the reference declarations are; none reads or writes a quest:

| Identity | From | Trigger | To |
| --- | --- | --- | --- |
| `ROSOLO_CH1_EDGE_IN` warp | `ygg_edge,164,140` | 1,1 | `ygg_fruit,73,117` |
| `ROSOLO_CH1_FRUIT_OUT` warp | `ygg_fruit,71,114` | 1,1 | `ygg_edge,168,139` |
| `回程#ROSOLO_CH1_RET` `GATE_SKYBLUE` OnTouch | `ygg_edge,216,91` | 1,1 | `prt_fild05,353,248` |

Walking past the Messenger is allowed; arrival never completes or sets a
quest. The `ygg_fruit,73,117` fallback touch event, its `cloaknpc` helpers
and the Maysel/Est/Debris graph are intentionally omitted: they belong to a
later next-room task. The nine-cell client GAT metadata covers the landing,
repeat, Messenger and first-room cells only; `216,91` and
`prt_fild05,353,248` are new unqualified cells.

## Text and rights

Short original Traditional Chinese wording only, plus the audited 18368/18369
titles and the 18368 objective 「前往梧桐村」. The donor script is an inert
semantics reference whose README forbids redistribution: no donor prose,
script bodies, helpers, cutins or assets are copied. No publication right is
inferred.

## Checks run in the task worktree (source only)

```sh
python3 -I -B tools/renewal/test_chapter1_entry.py
```

Standard library only, under two seconds. Static: package files, mod.json,
UTF-8/LF, declaration lines/coordinates/triggers, unique `ROSOLO_CH1` names
under 24 bytes, unchanged DB bytes and title hashes, short text, no Latin text
or donor words, owned writes only, warps only to the three destinations,
`.@`-only variables, explicit `checkquest` comparisons, recheck before
`setquest`, recheck after `close2` before each `warp` + `end`, three
readbacks after each Messenger step and no yield inside that window.
Modeled: an authored interpreter runs the real script bodies against a
modeled quest log with no-op and interference hooks (levels 199/200/201,
cancel, defer, first/repeat destination, every yield, all 216 stored
combinations incl. inactive and unknown 0/7, both write no-ops, interference
after each write, return gate for every tuple, unrelated sentinels).
Mutation controls show the checks fail if a readback or a full-tuple check is
removed. Executed unmodeled commands fail the test; debugmes is checked
against the supported literal/checkquest/scope-variable concatenation form.
OnInit is not executed: a static check accepts only one questinfo statement
and end, rejects extra commands or missing terminators, and leaves the quoted
bubble condition's native meaning to the parser gate. The model is not the
rAthena parser and proves nothing about persistence, cells, arrival or the client.

## Root verification recipe (all UNRUN by the worker)

Use disposable state, never the installed app's database, with a tested
external backup of target `quest`/`char_reg_num` rows and the app's `mods/`,
`enabled.txt`, `disabled.txt`.

1. **Assembly.** Current import/owner checks; both `npc:` lines generated;
   no duplicate route or NPC at the five declared cells; the three unchanged
   DB rows merged without an inherited `Clear: true`; mod not refused.
2. **Parser.** Exact parser load of both changed files plus focused malformed
   controls (e.g. drop the `;` from `completequest 18368;` in a copy) with a
   causal diagnostic, reusing the qualified T10.007 isolated lifecycle; prove
   both NPCs and both warps loaded. No unchanged full cold/backup replay.
3. **Cells and routes.** Effective map/collision for `ygg_edge`/`ygg_fruit`;
   server adjacency and actual first (255,240) and repeat (212,95) arrivals;
   both warps both ways; new cells `216,91` and `prt_fild05,353,248`.
4. **Client.** Chinese quest log for 18368/18369, visible scene, Messenger
   and gate sprites/textures.
5. **Ordinary play.** A legitimately eligible level 200+ character: cancel,
   defer, first travel, Messenger edge, repeat travel and return. Do not
   bypass eligibility with level/quest edits or fixture substitution; the
   current low-level character's missing eligibility is a later gate, not a
   source defect or authorization to grant it.
6. **Persistence.** Normal earned-state save/logout/re-entry; tuple (2,1,-1)
   durable; unrelated quests, items, EXP, zeny and skills unchanged.

## Install and rollback

Not installed or ready for user evaluation. After the gates pass, install as
the enabled folder in the app's user `mods/`, then the normal rebuild/restart.

`git revert` rolls back source only; it does not restore installed
definitions, saves, settings or merged imports, and must not be deployed
automatically over earned progress.

Operational rollback keeps the mod enabled with the same DB definitions,
earned quest records and the usable exit connections from both destinations
(the two warps and the return gate). Withdraw the starter and Messenger NPCs
separately (remove their declarations; keep `first_edge.txt`'s connection
lines), rebuild and restart. Removing every NPC/portal can strand a character
on `ygg_edge` or `ygg_fruit`. Do not delete quest rows or restore an older
save. Root verifies an actual retention/withdrawal revision on isolated state
before installation; actual operational rollback is UNRUN.
