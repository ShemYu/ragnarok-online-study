# T10.010.004 ordinary-item NPC fixtures

Source-only candidates for the
[ordinary-item A/B runbook](../../../../docs/project/runbooks/T10.010.004-ordinary-item-verification.md).
**Nothing here is parser-, placement-, item- or runtime-qualified.** Root alone
loads these in a disposable world and decides what they prove. Source review:
[2026-11-04 fixture record](../../../../docs/project/reviews/2026-11-04-T10.010.004-ordinary-fixtures.md).

| File | Server | NPC | Candidate placement |
| --- | --- | --- | --- |
| `t10_ordinary_items.txt` | unpatched **and** patched | `T10 Ordinary Items#t10oi` | `prontera,150,150` |
| `t10_coin_capacity.txt` | patched **only** | `T10 Coin Capacity#t10cc` | `prontera,151,150` |

The common file contains no reference to the patched builtin, so the unpatched
parser can load it. Never load the capacity file on the unpatched server.
Coordinates and the `4_M_MANAGER` sprite are candidates: confirm the cells are
walkable, unoccupied and on the loaded map before loading.

## What the fixtures do and do not do

- Access requires `getgmlevel() >= 99` (the player group *level*, not
  `getgroupid()`). Qualify the disposable account's group level first.
- No `OnInit`, timers, automatic grants, quest changes, persistent variables,
  deletion/reset/fill, stat/slot/weight assignments, SQL, save, warp, admin or
  privilege commands. `Weight`/`MaxWeight` are only read, in native units.
- Each menu choice runs exactly one fixed command between a `before` and an
  `after` snapshot. Script completion and the closing message are **not**
  action success. `getitem`/`getitem2`/`rentitem` return no value; on a native
  refusal they print `buildin_getitem...: Failed to add the item to player.`
  (`getitem`/`getitem2` only) and the map server prints
  `Script command '<cmd>' returned failure.`, then the script continues.

Common menu (one choice per interaction):

| # | Case marker | Command |
| --- | --- | --- |
| 1 | `read` | none (snapshot only) |
| 2 | `909x2` | `getitem 909,2;` |
| 3 | `909x3` | `getitem 909,3;` |
| 4 | `909x1` | `getitem 909,1;` — deliberate one-unit refusal probe |
| 5 | `909bound_char` | `getitembound 909,1,BOUND_CHAR;` |
| 6 | `909rent3600` | `rentitem 909,3600;` |
| 7 | `1201x2` | `getitem 1201,2;` — nonstackable: one insertion per unit, can **partially** succeed |
| 8 | `1201x1` | `getitem 1201,1;` — single-slot setup / one-unit refusal probe |
| 9 | `1201ref4_fabre` | `getitem2 1201,1,1,4,0,4002,0,0,0;` — creation metadata, not card insertion |
| 10 | `12900x2` | `getitem 12900,2;` — only meaningful if effective `UniqueId: true` |
| 11 | `12900x1` | `getitem 12900,1;` — same condition |

Capacity fixture: one confirmation, then a `before` snapshot, two
back-to-back `ros_ch1_coin_capacity()` calls, an `after` snapshot and a
`result` line with `r1`/`r2`. Nothing (no `next`/menu/yield/snapshot) lies
between the two calls; the optional intermediate snapshot is omitted so the
whole interaction stays well inside the stock command budget (below).
Returns are logged verbatim: `1` fits, `0` native capacity refusal, `-1`
unsupported actor/item/configuration. Do not read `-1` as a capacity failure
or a logged value as proof of the read-only contract.

## Script command budget (source-derived, not parser-verified)

Stock `check_cmdcount` 65535 and `check_gotocount` 2048 stay enabled; no
`freeloop`. Each snapshot emits one `sprintf` `debugmes` per row inside a
`while` loop. A conservative pinned-source count is at most 102 compiled
commands and one `goto` per row, so two 200-row snapshots plus everything else
in one interaction stay at or below 42,200 commands and 450 gotos. Rows are
never truncated. See the fixture review for the derivation. If the console
shows `script:run_script_main: infinity loop !`, the run failed: stop.

## Markers (map-server console via `debugmes`)

`debugmes` reaches native `ShowDebug` as `script debug : <rid> <oid> : <msg>`.
Actual console/file capture (and whether debug output is shown) is
**unqualified**; qualify the capture path before running a case.

```text
T10OI case=<case> phase=before run=<tick> actor_cid=<cid> actor_aid=<aid> epoch=<s> tick=<ms> weight=<W> maxweight=<MW> count=<n>
T10OI case=<case> phase=before run=<tick> row=<j> idx=<slot> id=<item> amount=<a> identify=<0|1> refine=<r> attribute=<a> cards=<c1>,<c2>,<c3>,<c4> bound=<b> expire=<unix> equip=<eqp> enchantgrade=<g>
T10OI case=<case> phase=before run=<tick> end rows=<n>
T10OI case=<case> phase=action run=<tick> cmd=<command> epoch=<s>
... phase=after ... (same shape)
T10CC case=coin_capacity phase=<before|after> ... (same shape)
T10CC case=coin_capacity phase=result run=<tick> r1=<v> r2=<v> legend=...
```

`run` is the system tick at the start of the interaction; it correlates one
interaction's lines and is not persistent. `row` is the compact list position;
`idx` is the native zero-based inventory slot. Rows iterate only below the
current `@inventorylist_count`. `getinventorylist` exposes no unique ID or
`uniqueitem_counter`; read those from the isolated saved DB after normal
logout. A complete set of `end rows=<n>` lines confirms the snapshot finished.

## Root procedure outline

1. Use the qualified disposable world/baseline from the runbook; restore it
   through the qualified DB-only backup, never by script. Confirm the exact
   intended map-server binary, parser and logged-in disposable actor.
2. Pin each fixture's bytes/hash. Load with the supported `@loadnpc <path>`
   GM command (common on both binaries; capacity on patched only), capture the
   parser output and confirm the NPC appears. Do not use `@script`, and do not
   run full app `up`/repair after the map container replacement.
3. Qualify effective items 909/1201/4002/12900/1001972 (weight, stackability,
   slots, `UniqueId`, auto-equip/scripts) before freezing expected outcomes.
4. Run one menu choice per interaction. Judge each case only from the
   before/after rows, native weights and failure lines, against the runbook
   oracle and the same case on the other binary.
5. Persistence: normal logout, isolated read-only DB snapshot (amounts,
   metadata, bound, expiry, unique IDs, counter), then login and `read` again.
   `@save` sets a save point; it is not save proof.
6. Still required outside these NPCs: real-client equip/unequip, loot
   drop/pickup, an ordinary shop purchase, slot exhaustion with qualified
   light items and exact-weight/one-unit overweight states.

Stop on a binary/parser mismatch, missing registration, unexpected NPC/world,
item loss/duplication, persistent-state change from the capacity probe or any
unexplained A/B difference, or any `infinity loop` budget error.
