# Traditional Chinese Navigation — source preparation

Status: **source preparation only** within open T05. No new implementation task,
Claude/Grok result, Chinese rendering result or user acceptance is claimed.
Root works from coordination7cedf51 while the independent T06 reference pair
runs. No app, browser, database, save, cache, preference or network setting is
changed. [Current status](../STATUS.md) retains the full milestone boundary.

## Verified problem and prospective boundary

The expanded Navigation panel contains hardcoded English beyond seven fixed
headings. Root fully reads the supplementary inventory, checks the relevant
template/render/search/command source, and freshly matches11whole-file pins,
including that inventory, the qualified repaired bundle and proposed CLI checker.
This is a source finding; no new panel or bitmap was rendered during this work.

| Surface | Verified source behavior | Consequence for the next task |
| --- | --- | --- |
| Template | Title, All/NPC/MOB captions, search-count caption, detail placeholder, three column headers, Share tooltip, Services, MOVE, Minimize and marker tooltip | Keep dispatch values, count nodes, controls and disabled state intact while deciding the display text |
| Search/reset/selection | Rewrites Select a result, No result, No results found, Map-wide spawn, stat labels/fallbacks and spawn-entry tooltips after append | Translating a node once at append cannot cover later rewrites |
| MOB display values | JS creates10element,12race,3size and5abundance categories in English | These are finite code-generated display labels, separate from loaded monster names; abundance categories are not respawn intervals |
| Routes and help | Map Click, no-path suffix and the patched /navi description are separate sites; Mouse/Target/no-path footer text is currently CSS-hidden | Preserve route logic, identifiers and coordinates; distinguish source-reachable text from observed visible text |
| Images and loaded data | Share/Find use six Navigation bitmaps; dataset names, map artwork and caller labels have separate origins | A translated tooltip cannot prove bitmap words or arbitrary data are Chinese |

The empty-result advice specifically recommends enabling
navigation-english-tables after an English GRF override. Its recommendation
needs a Chinese-mode content decision before implementation; translating the
sentence alone does not establish that the suggested mod is appropriate. No mod
was enabled or disabled here.

The earlier private seven-slot append/replay adapter draft remains **unadopted
and partial**. The existing qualified msgid adapter covers SkillListV2/283 and
QuestV1/1317 only. No reviewed Navigation site uses that binding unchanged.
Full Traditional Chinese UI/story coverage remains required.

## Existing repair and a feasible next source task

Root reads navigation_client_repair.py's guarded repair_bundle and build paths.
Its current qualified contract changes only the Lua-loader window, copying all
outside bytes unchanged; it has no Navigation UI replacement hook. Do not
silently broaden or repin that existing helper.

A separate finite, pinned bundle transform is a feasible next candidate: take
the already qualified repaired Online.js, replace only frozen contextual
template/render/enum/help literals, and prove every other byte unchanged,
including the working transport repair. Root has **not** frozen the compiled
occurrence ledger, Chinese terms or a new task contract yet. Source-only
compiled-window and bitmap-path preparation continues before the actual pair.

New bundle bytes will need their own delivery/execution integrity and rollback
qualification. T05.008's existing original/repaired pins cannot qualify a later
localized bundle. Retain the current repaired stage and newest save; do not
restore older progress to undo a UI change.

## Evidence and next owner

Upstream patch source is2c3b2612973fb8d0ae6ad366a2b298686f2404cb;
client source is775f8847a8b09749d03c82fcb554e155401d1e02.

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| patch-navigation-client.cjs | 59483 | dd24e5fa0864d1c65977b36e6453a02a7bd48bb58fe92eb25c10bea04155c9f7 |
| navigation_client_repair.py | 42497 | 4dfa29570e7b6ac64be5bda706626a9261f1aed3decce96d796107cdae548b8d |
| Qualified repaired Online.js | 13172839 | 6ba854cb67b1306cadb905b1b89a7a1eac98cd7e5c912196e6f87df41a5c4c2f |
| Private full-text inventory | 20950 | 012a5bcade690e68c0d9a8a0ada7122afd43a572ac903259c10a06c42e76e941 |

Private inventory is
`.tools/renewal/t06-static-spawn-pair-1/navigation-full-text-inventory-1.md`,
0600. Root personally reads all of it and checks the primary source sites;
supplementary internal assistance is not credited as Claude/Grok benchmarking.
Actual compiled occurrences, selected resource winners, pixels, Chinese
terminology, implementation and native behavior remain unqualified.

Next owner root: finish exact compiled-site/resource preparation, choose a
bounded contract and terms, then obtain independent actual Claude/Grok attempts
from one committed base. Personally verify the selected source and later native
behavior before any evaluation packet. This documentation checkpoint is
reversible with git revert; it has no external-state rollback step.
