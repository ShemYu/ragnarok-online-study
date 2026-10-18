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
Selected resource winners, pixels, Chinese terminology, implementation and
native behavior remain unqualified. Later compiled-site checks are below.

Next owner root: finish exact compiled-site/resource preparation, choose a
bounded contract and terms, then obtain independent actual Claude/Grok attempts
from one committed base. Personally verify the selected source and later native
behavior before any evaluation packet. This documentation checkpoint is
reversible with git revert; it has no external-state rollback step.

## Later root compiled-site qualification

Root personally checks all66candidate English literal sites, all34contexts and
five guard-only sites against the exact repaired bundle. Every source byte span,
length and SHA matches; contexts each occur exactly once in their declared
window. Root inspects every short literal/context and verifies all seven bound
modules/windows, both JSON string tokens and their decoded equality to the
upstream raw HTML/CSS, the protected9700-byte loader repair, and all67unchanged
complement pieces. Total **184bound span checks** pass without executing stock
source or changing any bundle byte. This is a text-site denominator for the
prospective transform, not a denominator for the complete game UI.

Private data ledger60694bytes/SHA
**5154f9cbef4c3ab7274cea6d4ad50432e2f122b282638bdb60be9ec56004fa96**
is navigation-compiled-literal-ledger-1.json under the earlier preparation
directory. Root qualification receipt navigation-ledger-root-qualification-1.json
SHA**323ba8d97c54ebdea9603e504a3c28dea8a25fde0b9a44eaf3a3d62379fc967c**.
Six distinct Unknown and three Select a result sites are retained. Compiled
empty-result advice contains actual UTF-8 arrows; the upstream patch-template
escape spelling is not the compiled byte spelling. No translated output or
new implementation contract has been frozen.

Root also personally reads the exact compiled UIButton implementation and all
Find state/click sites. A narrower prospective solution for the two English
bitmap captions is to retain the **ui-button elements**, classes, disabled
attributes and handlers, remove only their bg/hover/down attributes before new
component construction, and add Chinese text with scoped120×20CSS visual states.
Missing image paths return without loading; the element preserves text children.
This avoids raster edits and native-button keyboard changes. It remains a
design choice to encode and verify in the next brief, not an installed repair.

The disabled appearance must be defined with **[disabled] CSS**: without image
callbacks initial connection does not call update, while later events can set
inline opacity0.5/cursor default. Preserve those semantics, restrict hover/press
rules to enabled controls, and test actual text fit, state changes, inert Share,
Find click/reset and absence of these six bitmap requests. Removing attributes
from an already initialized element would leave captured bitmap URIs intact,
so a live DOM-only change is not equivalent. No new keyboard accessibility claim
is made. Original exact bitmap attributes/CSS guards and final Chinese terms
still need root review/freeze before the actual provider pair.

## Final source preparation and frozen follow-up

The preceding pending-freeze statements describe earlier preparation. Root now
qualifies11additional whole-tag/attribute/CSS spans, bringing the two source
ledgers to195bound spans. Button ledger10131bytes/SHA
0d7f488fa72e6e0f5fbecc90ba391468e25c0630fce4b420e777f65c7bf0343f;
root receipt SHA2dc231a5c6734b50230ed2463a88c4d85d6c2aaef551dcd01e90f555ea977428.

[T05.009](../tasks/T05.009.md) is the separately frozen pure transform/inverse
task, with [root pre-provider evidence](2026-10-19-T05.009.md):75edits and72
unchanged pieces, independent expected13173065-byte result SHA67525a4e…4478,
exact whole inverse and9700-byte loader conservation. Root's final combined
profile qualification passes129bound checks and all metadata/source pins;
syntax-only Node check passes. Both custom controls are retained; two Chinese
text children/scoped CSS replace only their six image attributes. No bitmap
pixels are edited or certified. The earlier append adapter stays unadopted.

Production remains a small fixed-pin/75fragment module; broad metadata checks
belong to root external acceptance. No actual pair, implementation install,
rendered Chinese Navigation or user/full-language acceptance is inferred from
this contract freeze. New native/delivery/installed/rollback gates remain.
