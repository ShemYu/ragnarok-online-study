# Workflow inspection — 2026-09-24

Goal under review: a **stable workflow for creating different characters in one shared style and theme**, reusing Ragnarok Online's native modular construction (ACT selects and places SPR drawings; body, head, headgear, weapon and trail are separate parts) so actions keep native motion quality.

Baseline inspected: commit `c6314bb`, `native-art-poc-v0.1.0`. At inspection time `tools/check_public_tree.py`, all 36 Node tests and `pipeline.py verify` (197 hashes, 18 native tests) passed. The findings below are gaps between "a generated picture" and "a reusable character that plays in the game", not failures of the saved PoC.

Each item keeps its evidence so the detail is not lost. Tick the box and link the change when an item is fixed.

## What is already right — keep it

- ACT stays unchanged; replacement art only substitutes SPR image slots. This matches how RO builds characters.
- Fixed crops, no per-slot recentering, source-hash checks, browser↔Godot pixel parity, and preserved raw generated boards.
- Abandoning generated sheets, video and the cutout rig for animation was correct.

## A. Style consistency — blocks "many characters, same style"

- [ ] **A1. No palette discipline.** Unique colors per sprite: native body slots 82–86 use 37–49 colors, generated Wayfarer slots use 1,347–1,691; native head slot 1 uses 19, generated head 417. RO sprites are indexed (one 256-color palette, index 0 transparent). This is the main source of style drift between characters, and it prevents palette dyes (RO's cheap clothing/hair variants) and writing back real `.spr` files.
  *Fix:* importers quantize every pixel to a fixed, versioned **style palette** (shared skin/outline/metal/leather ramps + per-character costume ramps). Record the palette hash in the manifest; fail when pixels are outside it.
- [ ] **A2. Resize grid is not aligned.** The body reference board was 1440×960 (5×); ImageGen returned 1536×1024 (5.333×). `import_native_costume.gd` resizes straight to 288×192 with nearest sampling, so each output pixel is one arbitrary sample of a 5.33-pixel block → doubled/dropped pixels and noisy clusters. `import_native_head.gd` has the same issue (1024 → 64).
  *Fix:* per target pixel, classify all source pixels inside its (fractional) block against the palette and take the majority class. Deterministic, grid-independent, no single-sample noise.
- [ ] **A3. Magenta fringe survives the key.** 1–5 pinkish opaque pixels remain in most body slots and in the head (visible at hair edges on `native-head-v1/none/attack/contact-3x.png`). The RGB threshold key misses anti-aliased blends of magenta with sprite colors.
  *Fix:* treat a pixel as `t·key + (1−t)·paletteColor`; if the best fit is mostly key, it is transparent, otherwise it becomes the palette color. Report remaining key-like pixels; fail if any survive.
- [ ] **A4. No machine-readable style bible.** Style lives in prose in each `prompt.txt` plus one design reference image. For the 2nd…10th character, store once and reuse in every prompt and check: palette, outline color, light direction (RO: top-left), cluster size, head:body ratio, per-character turnaround sheet.

## B. Runtime integration — before custom characters reach the game

- [ ] **B5. Godot frame cache ignores appearance.** `scripts/ro_sprite_actor.gd` `_render_frame()` caches by `kind:state:direction:frame:weapon`; `_draw_part()` caches images by `source:index`. Two swordsmen with different outfits would share frames. Both importers work around this by clearing `Actor._frame_cache` / `_image_cache` manually.
  *Fix:* include selected body/head/headgear/palette identity in both keys.
- [ ] **B6. The game cannot load Character Lab output.** The Godot actor only loads native SPR pairs and has no headgear part. Needs a module manifest (“for part P, replace SPR indexes with these PNGs / this palette”) and a headgear layer. (ROADMAP step 5; these are the concrete missing pieces.)
- [ ] **B7. Slot list is hardcoded to one action/facing.** `export_native_template.gd` hardcodes `[82,83,84,85,86,54]` and direction 6.
  *Fix:* derive required slots from ACT — walk every action group × direction the job uses and collect the image indexes each part references. That set is the real per-character art budget (usually far smaller than frames × 8 because RO reuses drawings and mirrors W↔E). Measure it before committing to the workflow's scale.

## C. RO animation faithfulness

- [ ] **C8. Damage lands before the visible hit.** Body attack action 86 has sound event `attack_sword.wav` on frame 5 of 9 (≈56%). Gameplay applies damage at `ATTACK_HIT_FRACTION = 0.45` (`rpg_rules.gd`), while the wind-up frame 4 is still shown. Compressing the clip to the attack interval (`main.gd` `_start_attack`) is fine — RO scales attack motion by ASPD — but the hit time should come from the ACT event frame.
- [ ] **C9. Draw order is fixed for every direction.** `native-core.mjs` and the Godot actor use body → head → headgear → weapon → trail. In RO, weapon/shield draw behind the body for away-facing directions, headgear is ordered lower → mid → top, and garments use per-job/per-direction tables. Store an order table per direction in the template before adding a second facing.
- [ ] **C10. Unarmed attack differs between tools.** Godot switches to action group 5 without a weapon (`_get_action`); the Lab only hides the dagger. RO chooses attack action 5 / 10 / 11 by job and weapon type — keep that mapping in data.
- [ ] **C11. Verify tick length.** `ro_sprite_data.gd` uses 24 ms per ACT tick (4 ticks → 96 ms). roBrowser/ActEditor are believed to use 25 ms (→ 100 ms). Unconfirmed; check against their source.
- [ ] **C12. Missing actions fall back silently.** `_get_action()` substitutes the idle action for a missing index without warning. Report it.

## D. Process and CI

- [ ] **D13. Public CI tests the abandoned path.** CI runs only `modular-motion`/`modular-engine` (cutout rig). `native-core.mjs` — the code the workflow depends on — is untested publicly. Add tiny synthetic ACT/SPR-shaped fixtures for composition, attachment and draw order.
- [ ] **D14. Importers are Wayfarer-specific.** The head importer hardcodes the Wayfarer body pack and head slot; the costume importer only accepts `--output-dir`. Move this into the recipe loader proposed in [WORKFLOW.md](WORKFLOW.md), including palette/style-bible references from A1/A4.
- [ ] **D15. Side effects inside `assert`.** `assert(image.save_png(...) == OK)` performs the save inside the assertion; builds with asserts disabled skip the save.

## Order of work

1. A1–A3: shared palette quantizer, block-majority downscale, key unmixing; re-import Wayfarer into a **new** pack and review it visually (keep v2 untouched).
2. B7: ACT-driven required-slot inventory for all eight directions of one job.
3. B5–B6: appearance-aware caches and a replacement-texture manifest in the Godot actor.
4. Prove a **second character on the same template** with the same palette and style bible before adding a second action.

## Progress log

- 2026-09-24 — inspection recorded; work started on branch `fix/style-consistent-import`.
