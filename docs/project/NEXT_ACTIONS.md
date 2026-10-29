# Expert re-audit — next actions

Updated 2026-10-29. **Inspection/design is authorized; game execution remains
paused.** These are planned tasks, not dispatched implementation or acceptance.
[Audit evidence](reviews/2026-10-29-T00.005.md) distinguishes confirmed findings
from missing runtime proof. The full Modern/Renewal goal is unchanged.

## What changes in the approach

Qualify the release path before adding more story slices. In parallel, make
verification reproducible and build a provisional coverage ledger now; do not
wait for every inventory to finish before exposing what is unknown. Do not
replace the exact native capacity probe with the known-incompatible stock
`checkweight` shortcut, or broaden CI to private/mutating suites indiscriminately.
No new permanent marker or transaction system is selected by this audit.

## Seven bounded tasks

All tasks use Root as coordinator. Implementation candidates follow the paired
workflow, with separate ownership and Root verification before user evaluation.
The acceptance column describes future evidence, not a result already obtained.

| ID / priority | Deliverable and dependencies | Objective verification and end-user acceptance |
| --- | --- | --- |
| **T00.006 / P0** | Public test classification and a checked-in self-isolating runner for mutation suites. Independent of game startup. | Public commands work without assets. Success and interrupted runs preserve canonical source hash/inode/mtime/ctime; mutations touch ordinary private copies only. Private inputs require explicit selection. A fresh engineer needs no ignored wrapper to reproduce the safe path. |
| **T06.005.001 / P0, parallel** | Provisional version/content ledger from already qualified T06/T07 inventories. Do not wait for final T06 completion. Record server/client/overlay revisions, expected/present/effective/loaded/exercised/verified/unknown states and evidence links; join all 82 open resource gaps. | Counts reconcile to their pinned inventories; unknown and missing categories remain visible, including unimplemented story chains. Classify actual party gates separately. User can see which ordinary content works and why the rest is pending. Presence or a sample tour never becomes full-content acceptance. |
| **T10.010.003 / P0, parallel** | Reproducible native source/overlay preparation and bounded build/export recipe. Pin full sources, ordered transforms, nine existing subset hashes, dependencies, architecture, packet configuration, ABI, resources, cancellation and cleanup. | A fresh isolated workspace reconstructs all nine hashes without old `.tools` packets; exact patch and differential qualify. The full build recipe accounts for the known slim-build limitations. Produce one complete map-server artifact, not another model-only refinement, as the next runtime experiment after resumption. |
| **T10.010.004 / P1** | Full Linux/arm64 compile/link/start and ordinary-item A/B regression, after .003. Use owned isolated state and refreshed resource bindings. | Binary starts against intended libraries/config/DB. Compare patched vs corresponding unpatched ordinary stack/new-slot, weight/full-bag, equipment, metadata/rental/GUID and save/re-entry cases. Player-visible loot/shop behavior must not lose or duplicate items. The new read-only probe changes no state. |
| **T10.010.005 / P0 design, P1 execution** | Release compatibility manifest and pre-install gate, designed alongside .003; validate using .004 outputs. Bind app/server/patch/mod/text/config identities, item 1001972's effective alias/type/weight/stack/pet facts, three route maps and quest/text rows 18368–18371. Clearly separate frozen 0.2.0 staging from current 0.3.2 source. | Stock/mismatched binaries are refused before installation; matching builtin/parser and effective data qualify. All four quest rows survive withdrawal, without `Clear`; title/summary/description checks include 18371. Use a supported external preflight if the app manifest cannot express native capabilities. No invented `requires` keys or client-side guard can replace parser compatibility. User installs one coherent tested release. |
| **T10.010.006 / P1, parallel analysis** | Inspect real EXP callbacks and quest/status/inventory save paths from .003. Define actual EXP expectations and the current uncertain-reward/manual-review procedure; validate after .004. | Normal save/re-entry and isolated restart retain earned state, repeat dialogue does not duplicate rewards, and a level-up case checks actual configured EXP behavior. Test one justified interruption boundary if safely controllable; otherwise keep it explicitly unproved. The initial no-replay alert is not described as durable quarantine or crash atomicity. |
| **T10.010.007 / P1** | Native story slice and supported normal installation, after .004–.006, refreshed ownership and current backup qualification. | Real parser/OnInit/four actors, starter/travel, Shasha/Maysel, full-bag refusal/retry, matching-stack/new-stack rewards and journal all work in isolation. Then supported install/full Apply, normal play, save/restart and withdrawal pass with the user's progress preserved. Root verifies before the user's short playtest. |

## Dependency flow

```text
Inspection/design complete; execution awaits resumption
 |
 +-- T00.006     safe, reproducible verification ----------+
 +-- T06.005.001 coverage ledger / 82-gap reconciliation --+--> full-content plan
 |
 +-- T10.010.003 exact sources + build recipe
       +-- T10.010.004 full binary + ordinary items ------+
       +-- T10.010.005 release compatibility ------------+--> T10.010.007
       +-- T10.010.006 reward/save analysis + validation -+    native -> normal play
```

Existing resource repairs can proceed alongside these lanes within their
qualified inputs. Remaining Chinese/input work follows functionality; actual
party-only completion stays later. T12/T13 still require full agreed coverage
and explicit user acceptance. This audit adds seven planned children to the
37 previously unfinished rows; the parent ledger remains 4/14 qualified.

## First experiment and stop conditions

After resumption, reconstruct the pinned full source and compile/export one
bounded matching binary. Verify loader compatibility, registration/parser and
ordinary item behavior in isolated state before loading the new story. This
tests the highest unproved delivery assumption without changing normal play.

Stop that experiment on a source/ABI/capability mismatch, unbounded build,
uncertain actor cleanup or any item-loss/duplication regression; preserve its
evidence and fix the bounded cause before advancing. Notify the user if verified
missing-content volume or an unavailable compatible/recoverable runtime means
the agreed full-game goal needs a scope or maintenance commitment decision.
No such forced goal change is established by this source audit.
