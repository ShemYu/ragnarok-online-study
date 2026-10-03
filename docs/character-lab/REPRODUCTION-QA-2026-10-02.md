# Saved-art reproduction acceptance — 2026-10-02 JST

**PASS for the bounded saved-art milestone.** The validated recipe rebuilds the saved Wayfarer front body v3, historical head v2 and back-view trial v2 in an isolated directory. Codex independently compared all 100 PNGs with the saved originals and found no differences. D14 remains partial: the native adapters still target the existing Swordsman action and facing.

Claude implemented the workflow in its existing configured Opus 5.5 session. Codex ran the acceptance checks, reviewed the output images and repaired findings through that same Claude session. The branch remains `fix/style-consistent-import`, HEAD `24b0806265b2f84060f35626d03b1b71f4ecb91b`; all changes are uncommitted.

## Deliverables

- [Recipe runner](../../tools/character-lab/art_recipe.py), [pinned recipe](../../tools/character-lab/recipes/wayfarer-saved-art-v1.json) and [regression tests](../../tools/character-lab/tests/test_art_recipe.py).
- [Workflow and limits](WORKFLOW.md#reproduce-the-saved-wayfarer-packs-from-a-recipe-d14-2026-10-02), updated inspection/backlog and public CI test step.
- Retained local output: `logs/overnight-2026-10-02/reproduction-accepted/REPORT.md`, `reproduction-report.json`, the three reproduced packs and their isolated Godot logs.
- Independent machine-readable evidence: `logs/overnight-2026-10-02/codex-acceptance-final.json`. This records tested source hashes, unchanged baseline files and the independent PNG comparison.

The output and local evidence remain ignored by Git. Existing native and generated assets have not been added to the public source tree.

## Acceptance results

| Check | Fresh result | Evidence below `logs/overnight-2026-10-02/` |
| --- | --- | --- |
| Recipe suite | 45 synthetic tests + 2 local checks pass | `codex-tests-accepted.log` |
| Real full reproduction | All three importers exit 0; 100/100 PNGs byte-identical; zero problems | `reproduction-accepted.console.log`, `reproduction-accepted/REPORT.md` |
| Independent comparison | Front body 19/19, head/hat fixtures 35/35, back fixtures 46/46; only declared manifest differences | `codex-acceptance-final.json` |
| Current strict head refusal | Real local test confirms exit 1 and absent output directory | `codex-tests-accepted.log`; detailed importer metrics in `head-strict-gate.log` |
| Existing Godot appearance integration | 48 checks pass | `appearance-baseline.log` |
| Existing native study | 197 source/asset hashes and 18 tests pass | `codex-saved-pipeline.log` |
| Asset-independent motion/modularity | 12 tests pass | `codex-modular-tests.log` |
| Source policy and syntax | Four Python files parse; 140 indexed paths and all four new source/document files pass path policy; `git diff --check` passes | Independently run after the final implementation |
| Protected content | All 1,976 original files unchanged; zero additions in the seven protected asset/evidence trees | `protected-before.json`, `codex-acceptance-final.json` |

The optional full-reproduction unittest was skipped because `ART_RECIPE_FULL` was unset. The full run was verified separately with retained output, so the above count is 47 passed tests, not 48.

The final report pins 34 native/source/layout/palette/generated inputs and verifies recipe provenance exactly. It also hashes 601 files in its relevant saved folders before and after; the wider Codex preservation check independently covers the 1,976-file baseline, including snapshots, prior evidence, appearance manifests and saves.

Failure regressions cover missing/changed sources, same-size native image changes, the required sixth ready slot, incompatible geometry/actions, malformed coverage, traversal and symlink escapes, invalid schema types, unsafe output/log locations, stale historical failures, missing/wrong recipe provenance and changes during validation or import. Partial and failed import reports describe only the checks they completed.

The first full attempt hit Godot's default file logger outside the writable workspace. The runner now uses explicit logs in a private temporary directory and retains them only after gates pass. The final full run succeeds under the normal sandbox; no wider save-directory access was needed.

## Visual and behavior review

Codex inspected the reproduced body contact sheet, head fixtures with none/cap/hat, and back-view fixture output. The independent byte check establishes that these preserve the saved pictures. This technical acceptance does not approve new artwork.

A fresh local browser opening of existing `native.html` reports 108 original/costume/head/equipment frames matching the native-data renderer. With body v3 and head v2 selected, changing the cap retained frame 6, SPR 85, source action 86, 96 ms duration and `attack_sword.wav`. This browser check loads existing saved packs, not the fresh reproduction directory. The generated reproduction report correctly makes no browser-validation claim.

## Repeat the accepted workflow

From the repository root, with the local study assets and Godot 4.5.1 available:

```sh
python3 -B tools/character-lab/art_recipe.py validate tools/character-lab/recipes/wayfarer-saved-art-v1.json
python3 -B tools/character-lab/art_recipe.py run tools/character-lab/recipes/wayfarer-saved-art-v1.json --out /tmp/wayfarer-reproduction-review
ART_RECIPE_LOCAL=1 python3 -B -m unittest discover -s tools/character-lab/tests -p 'test_*.py' -v
```

Use a new or empty isolated output directory. Adding `--strict` to a full run must reject the historical head and leave that directory absent. The normal historical reproduction applies the current contract, records the known failure and keeps the old pack name; it does not produce head v3.

## Remaining decisions and limits

- Head v2 still fails the current contract: area 86%, face 25%, face 5×5 against native 10×11. Head v3 has no candidate. A future replacement must pass strict gating and receive visual review.
- Back v2 passes its technical slot contract but awaits the user's artwork acceptance. The accepted appearance manifest was not changed.
- Accepted body coverage is six drawings of 118; back preview adds five pending drawings. Head coverage is one of 15. Native fallback still covers walk, idle and other actions.
- D14 does not yet remove the native importers' fixed template, action 86 and direction 6. General adapters, a second character/style proof and the D13 native-core CI fixture work remain future scope.
- No gameplay, renderer draw-order, hit timing or source tick changes were made. No new art generation, commits, pushes, deployment, publication or external game/server actions occurred. No remaining blocker prevents using this bounded local workflow.
