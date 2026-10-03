# Completion milestone — Wayfarer action slice and second-character proof (2026-10-02)

**Technical acceptance passes for the selected milestone.** The new Wayfarer art imports through 12 strict-gated recipe modules; Lantern Scholar imports through two modules using the same palette, style bible, native template and generic scripts. Isolated game-actor checks pass for both looks. Independent raw-board and actual-composite review found no blocking visual issue; the new recipe modules are `reviewed-by-codex`. Final reviewed recipes were rerun strictly and all 14 packs were installed; installed runtime checks, the save-free field boot and fresh local-viewer browser evidence pass. See [final acceptance](COMPLETION-QA-2026-10-02.md). No new artwork is accepted by the user.

This page supersedes the earlier code-only handoff. The dated inspection log and saved-art reproduction report preserve that earlier stage. Native actions, attachment anchors and timing remain unchanged.

## Delivered scope

| Item | Drawings | Release modules | Confirmed result |
| --- | --- | --- | --- |
| Wayfarer idle | body 0–4 | 1 | strict import passes |
| Wayfarer walk, five drawn views | body 5–44 | 5 | strict imports pass |
| Wayfarer ready front/back | body 55–59 / 60–65 | 2 | strict imports pass |
| Existing Wayfarer front attack + ready | body 82–86 + 54 | protected `native-wayfarer-v3` | user-accepted baseline, unchanged |
| Existing Wayfarer back attack | body 87–91 | protected `native-wayfarer-attack-back-v2` | technically passing, user acceptance pending |
| Wayfarer head v3 | head 0–4 | 4 | strict imports pass; separate none/cap/hat fixtures |
| Lantern Scholar proof | body 82–86 + 54, head 1 | 2 | strict imports and configuration reuse pass |

Wayfarer replaces **67 body drawings** (0–44, 54–65, 82–91) and **five head drawings**, covering idle, walk, ready and dagger attack across all eight directions, including native idle head turns. Fifty-six body drawings and all five heads are new. Scholar replaces six body drawings and head 1: its remaining ready frames, back view and other actions explicitly use native artwork. The optional Scholar ready-front 55–59 board was not selected or delivered.

This completes the selected art/import milestone. Sit, pickup, hit, dead, cast, unarmed/other attack groups, head 5–14, the full 94-gameplay/118-total body budget and other job templates remain outside it. C8–C12 remain open: ACT-event hit timing, direction-specific draw order, unarmed-action mapping, tick-length verification and missing-action warnings.

## Release data and fixed crops

The current export plan is [`plans/release-2026-10-02.json`](../../tools/character-lab/plans/release-2026-10-02.json). The earlier `plans/completion-2026-10-02.json` remains the original pre-generation plan; its combined idle/walk modules do not describe the selected release. Release boards and candidate art are retained locally under `tools/character-lab/assets/completion-2026-10-02/` and excluded from the public source repository.

Thirteen boards were exported afresh with the current exporter so every fixture records `bodyFrames` and `bodyDelayMs`. Each native board is byte-identical to the original generation board. Body idle/ready and Scholar body use 128-pixel cells, three columns and scale 4; walk uses 96-pixel cells, three columns and scale 5. Single heads use a centered 64×64 native canvas at scale 16. The four-head board uses a centered 128×128 canvas, two columns and scale 16.

Paths below are relative to the completion asset folder. Every recipe output/install name is the lowercase module ID; exported walk board names keep uppercase direction suffixes.

| Recipe module | Layout folder under `release-boards/` | Unchanged raw source under `candidates/` | Selected slots |
| --- | --- | --- | --- |
| `wayfarer-body-idle-all` | same ID | `wayfarer-body-idle-all-03.png` | 0–4 |
| `wayfarer-body-walk-s` | `wayfarer-body-walk-S` | `walk-s-01.png` | 5–12 |
| `wayfarer-body-walk-sw` | `wayfarer-body-walk-SW` | `wayfarer-body-walk-SW-01.png` | 13–20 |
| `wayfarer-body-walk-w` | `wayfarer-body-walk-W` | `walk-we-01.png` | 21–28 |
| `wayfarer-body-walk-nw` | `wayfarer-body-walk-NW` | `wayfarer-body-walk-NW-01.png` | 29–36 |
| `wayfarer-body-walk-n` | `wayfarer-body-walk-N` | `wayfarer-body-walk-N-01.png` | 37–44 |
| `wayfarer-body-ready-front` | same ID | `wayfarer-body-ready-front-02.png` | 55–59 |
| `wayfarer-body-ready-back` | same ID | `wayfarer-body-ready-back-02.png` | 60–65 |
| `wayfarer-head-0` | same ID; metadata selection | `wayfarer-head-other-views-05.png` | only 0 |
| `wayfarer-head-1` | same ID; single head | `wayfarer-head-slot1-02.png` | only 1 |
| `wayfarer-head-2` | same ID; single head | `wayfarer-head-2-02.png` | only 2 |
| `wayfarer-head-rear` | same ID; metadata selection | `wayfarer-head-other-views-02.png` | only 3, 4 |
| `lantern-scholar-body-front` | same ID | `lantern-scholar-body-front-01.png` | 82–86, 54 |
| `lantern-scholar-head-1` | same ID | `lantern-scholar-head-1-03.png` | only 1 |

Head 0 and rear heads 3/4 are metadata-only selections of `release-boards/wayfarer-head-other-views/`. Copies of the complete native/enlarged board and complete raw candidate retain their exact bytes and 128×128 canvas. Selected crop rectangles remain head 0 `[17,18,29,27]`, head 3 `[19,83,26,26]`, head 4 `[84,82,24,28]`. No drawing is repacked, recentered or edited. Only selected slots and relevant fixture directions remain in each derived layout; complete native sequences, body frame counts and delays are preserved. Failed cells elsewhere on either raw candidate are excluded from gating/import and are not accepted.

The single head-1 crop is `[17,19,30,26]`; single head-2 is `[18,19,27,26]`. Each selected raw PNG is copied unchanged to its layout folder's `candidates/candidate.png`. `candidates/origin.json` records the original generation layout, raw candidate/native board hashes and selected fixed crops. The recipe pins the derived layout and copied PNG. An unfiltered four-slot layout cannot be used as `generatedImage.generatedOn` for a one-/two-slot selection because that option requires identical slot lists as well as identical canvas/crops.

All head fixture looks include the eight new body modules and protected front/back base appearance. Earlier head modules are included in dependency order; the final rear-head fixture therefore composes the complete selected look. Scholar head fixtures use the earlier Scholar body module. Cap, hat, dagger and trail remain separate native modules.

## Configuration reuse (D14) and public tests (D13)

`import_native_costume.gd` and `import_native_head.gd` are thin wrappers around `art_import.gd`; template/layout paths, slot crops, actions, headgear variants, fixtures and labels live in `importers/native-*.json`. The saved configurations describe the preserved single action/facing; those values are data rather than character-specific importer code. Generic `board_export.gd` / `export_boards.gd`, `import_slot_board.gd` and `slot-board-v2` recipes cover new parts, groups and views.

D14 is proven by the successful two-module Scholar recipe without character-specific script edits, plus the unchanged saved three-pack reproduction. Both characters share `style-bible-v2.json` and the same 48-color `wayfarer-style-v1` palette. The original body/front-head thresholds are preserved; rear-head rules measure the visible skin of native rear views. A failing candidate is regenerated, never repaired or passed by relaxing a threshold.

D13 is complete for this milestone: [`native-core-synthetic.test.mjs`](../../tools/character-lab/tests/native-core-synthetic.test.mjs) supplies 11 tests without RO files and runs in [public CI](../../.github/workflows/source-checks.yml). It verifies the current composition/attachment behavior; it does not resolve the C9 direction-order research.

## Reproduce and review locally

Run from the repository root with the retained local source, reference and generated-art pack present. `ART_LOG` must be an existing absolute writable folder. Every Godot call gets an explicit log file; the output folders below must be new. Existing board directories, non-empty importer outputs and installed packs are never overwritten.

```sh
ART_GODOT="$PWD/.tools/Godot.app/Contents/MacOS/Godot"
ART_LOG="$PWD/logs/completion-2026-10-02"

# Export only into absent board folders. Use a different --out for a fresh re-export.
"$ART_GODOT" --headless --log-file "$ART_LOG/reexport-next.log" --path . --script res://tools/character-lab/export_boards.gd -- --plan=res://tools/character-lab/plans/release-2026-10-02.json --out=res://tools/character-lab/assets/completion-2026-10-02/release-boards-reexport-next/

# After deriving the fixed-crop head metadata, copy raw candidates unchanged.
# Example: the selected front head uses whole-board variant 05, only SPR 0.
cp -n tools/character-lab/assets/completion-2026-10-02/candidates/wayfarer-head-other-views-05.png tools/character-lab/assets/completion-2026-10-02/release-boards/wayfarer-head-0/candidates/candidate.png
python3 tools/character-lab/art_recipe.py lock tools/character-lab/recipes/wayfarer-complete-v1.json
python3 tools/character-lab/art_recipe.py pin tools/character-lab/recipes/wayfarer-complete-v1.json --module wayfarer-head-0 --candidate=res://tools/character-lab/assets/completion-2026-10-02/release-boards/wayfarer-head-0/candidates/candidate.png
python3 tools/character-lab/art_recipe.py validate tools/character-lab/recipes/wayfarer-complete-v1.json
python3 tools/character-lab/art_recipe.py validate tools/character-lab/recipes/lantern-scholar-v1.json

# All new-art modules require strict gates; these fresh runs also request --strict explicitly.
python3 tools/character-lab/art_recipe.py run tools/character-lab/recipes/wayfarer-complete-v1.json --strict --out logs/completion-2026-10-02/wayfarer-run-next --log-dir "$ART_LOG" --timeout 90
python3 tools/character-lab/art_recipe.py run tools/character-lab/recipes/lantern-scholar-v1.json --strict --out logs/completion-2026-10-02/scholar-run-next --log-dir "$ART_LOG" --timeout 90

# Preserve the historical head-v2 failure as recorded; full --strict correctly rejects it.
python3 tools/character-lab/art_recipe.py run tools/character-lab/recipes/wayfarer-saved-art-v1.json --out logs/completion-2026-10-02/saved-reproduction-next --log-dir "$ART_LOG" --timeout 90
```

The public recipes already pin every selected layout/candidate. Re-exporting to another directory does not silently redirect those pins: compare native hashes and geometry, prepare the metadata selections and candidate origin records, then explicitly change/lock/pin a new recipe if using that output. The retained preparation evidence is `logs/completion-2026-10-02/release-config/`: `head-selections.json`, `candidate-map.json`, `release-artifact-validation.json`, and the exact 18 successful lock/pin/validate commands in `commands.json` / `pin-and-validate.log`.

Promotion requires a PASS run of the exact current recipe bytes. A review-status change requires a new run before promotion. The following commands install only into absent pack folders, then exercise the installed appearance without reading or writing player saves:

```sh
python3 tools/character-lab/art_recipe.py promote tools/character-lab/recipes/wayfarer-complete-v1.json --from logs/completion-2026-10-02/wayfarer-run-next
python3 tools/character-lab/art_recipe.py promote tools/character-lab/recipes/lantern-scholar-v1.json --from logs/completion-2026-10-02/scholar-run-next
python3 tools/character-lab/art_recipe.py coverage res://tools/character-lab/appearances/wayfarer-complete.json
python3 tools/character-lab/art_recipe.py coverage res://tools/character-lab/appearances/lantern-scholar-proof.json
"$ART_GODOT" --headless --log-file "$ART_LOG/wayfarer-review-next.log" --path . --script res://tests/look_review_test.gd -- --out-dir="$ART_LOG/wayfarer-review-next" --appearance=res://tools/character-lab/appearances/wayfarer-complete.json --require-complete
"$ART_GODOT" --headless --log-file "$ART_LOG/scholar-review-next.log" --path . --script res://tests/look_review_test.gd -- --out-dir="$ART_LOG/scholar-review-next" --appearance=res://tools/character-lab/appearances/lantern-scholar-proof.json --states=ready,attack --headgear=none,cap,hat
"$ART_GODOT" --log-file "$ART_LOG/play-review-next.log" --path . -- --no-save --review-job=swordsman --appearance=res://tools/character-lab/appearances/wayfarer-complete.json
```

`look_review_test.gd` renders the whole native idle timeline, including head turns; idle frame 0 must match actual play. Other states use the game actor's frame selection and appearance-aware caches. The final field/browser review is separate evidence from these isolated fixtures. The Scholar proof intentionally does not use `--require-complete`.

## Confirmed local evidence

The following reports precede final promotion. Their recipes marked the art pending review; each new-art module nevertheless required and passed its strict contract. Final reviewed-recipe run reports and installation status belong to the final acceptance handoff.

| Check | Result | Local evidence under `logs/completion-2026-10-02/` |
| --- | --- | --- |
| Wayfarer recipe | 12 modules, PASS, zero problems | `wayfarer-run-01/REPORT.md`, `reproduction-report.json` |
| Scholar recipe | 2 modules, PASS, zero problems | `scholar-run-01/REPORT.md`, `reproduction-report.json` |
| Wayfarer game actor | 139 checks, 624 frames; 67 body/5 head; no fallback for the four states | `wayfarer-isolated-review/look-review.json`, contact sheets and frames |
| Scholar game actor | 58 checks, 360 frames; 6 body/1 head; remaining ready/back drawings native | `scholar-isolated-review/look-review.json`, contact sheets and frames |
| Saved reproduction | 100/100 PNGs byte-identical, three packs | `saved-reproduction-final/REPORT.md` |
| Appearance compatibility | 48 checks | `validation-appearance-final-0307.log` |
| Output/fixture safety | 22 checks | `safety-check.log` |
| Generic slot-board regression | 21 checks | `slot-board-final/`, `slot-board-final-logs/` |
| Indexed import / slot contract | 13 / 5 checks | `validation-indexed-final-0311.log`, `validation-contract-final-0311.log` |
| Synthetic native composition | 11 tests | `validation-native-core-final-0307.log` |
| Modular motion/engine | 12 tests | `modular-regression-final.log` |
| Saved pipeline | 197 hashes, 18 native tests | `saved-pipeline-final.log`; historical browser evidence retained |
| Protected baseline | all 1,976 files unchanged | `validation-regressions-20261002T030920097932Z.json` |

The runtime reports both record `savesTouched: false`. The protected baseline includes the old accepted artwork, historical snapshots/QA and four saves. Browser evidence retained by `pipeline.py verify` is historical; that command does not rerun browser validation. The current study remains local and offline.

The Scholar concept is female while the retained native body/head templates are male; this proof adapts the coat, notebook and bob to those native silhouettes. Its beret, ribbon and pin are omitted from head art because cap/hat remain independent modules. Both the new looks and the preserved back-v2 preview await the user's artwork acceptance.
