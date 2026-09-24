# Workflow inspection — 2026-09-24

Goal under review: a **stable workflow for creating different characters in one shared style and theme**, reusing Ragnarok Online's native modular construction (ACT selects and places SPR drawings; body, head, headgear, weapon and trail are separate parts) so actions keep native motion quality.

Baseline inspected: commit `c6314bb`, `native-art-poc-v0.1.0`. At inspection time `tools/check_public_tree.py`, all 36 Node tests and `pipeline.py verify` (197 hashes, 18 native tests) passed. The findings below are gaps between "a generated picture" and "a reusable character that plays in the game", not failures of the saved PoC.

Each item keeps its evidence so the detail is not lost, and an *Expected result* that says how to tell it is fixed. Tick the box and link the change when an item is fixed.

## What is already right — keep it

- ACT stays unchanged; replacement art only substitutes SPR image slots. This matches how RO builds characters.
- Fixed crops, no per-slot recentering, source-hash checks, browser↔Godot pixel parity, and preserved raw generated boards.
- Abandoning generated sheets, video and the cutout rig for animation was correct.

## A. Style consistency — blocks "many characters, same style"

- [~] **A1. No palette discipline.** Unique colors per sprite: native body slots 82–86 use 37–49 colors, generated Wayfarer slots use 1,347–1,691; native head slot 1 uses 19, generated head 417. RO sprites are indexed (one 256-color palette, index 0 transparent). This is the main source of style drift between characters, and it prevents palette dyes (RO's cheap clothing/hair variants) and writing back real `.spr` files.
  *Fix:* importers quantize every pixel to a fixed, versioned **style palette** (shared skin/outline/metal/leather ramps + per-character costume ramps). Record the palette hash in the manifest; fail when pixels are outside it.
  *Expected result:* Every replacement slot uses only colors from one reviewed palette (target: tens of colors per slot, like native, not ~1,500). Two different characters imported with the same palette share skin, outline and metal colors exactly. Manifests record the palette id and SHA-256, and the import fails on off-palette pixels. Recolors become palette edits, not new drawings.
- [x] **A2. Resize grid is not aligned.** The body reference board was 1440×960 (5×); ImageGen returned 1536×1024 (5.333×). `import_native_costume.gd` resizes straight to 288×192 with nearest sampling, so each output pixel is one arbitrary sample of a 5.33-pixel block → doubled/dropped pixels and noisy clusters. `import_native_head.gd` has the same issue (1024 → 64).
  *Fix:* per target pixel, classify all source pixels inside its (fractional) block against the palette and take the majority class. Deterministic, grid-independent, no single-sample noise.
  *Expected result:* Importing the same generated board at 1440×960, 1536×1024 or any other size of the same layout gives the same slot bitmaps (or near-identical ones). No isolated single-pixel speckle from sampling; outlines stay continuous.
- [x] **A3. Magenta fringe survives the key.** 1–5 pinkish opaque pixels remain in most body slots and in the head (visible at hair edges on `native-head-v1/none/attack/contact-3x.png`). The RGB threshold key misses anti-aliased blends of magenta with sprite colors.
  *Fix:* treat a pixel as `t·key + (1−t)·paletteColor`; if the best fit is mostly key, it is transparent, otherwise it becomes the palette color. Report remaining key-like pixels; fail if any survive.
  *Expected result:* Zero pink/magenta-tinted opaque pixels in any imported slot, reported as a counted diagnostic. Hair and sleeve edges read cleanly on the contact sheet at 3×.
- [ ] **A4. No machine-readable style bible.** Style lives in prose in each `prompt.txt` plus one design reference image. For the 2nd…10th character, store once and reuse in every prompt and check: palette, outline color, light direction (RO: top-left), cluster size, head:body ratio, per-character turnaround sheet.
  *Expected result:* One style file (for example `tools/character-lab/style/<style>.json`) is referenced by every prompt and import. A new character's prompt is assembled from the style file and a short character spec, not rewritten by hand. The checks in A1–A3 read their thresholds from it.

## B. Runtime integration — before custom characters reach the game

- [x] **B5. Godot frame cache ignores appearance.** `scripts/ro_sprite_actor.gd` `_render_frame()` caches by `kind:state:direction:frame:weapon`; `_draw_part()` caches images by `source:index`. Two swordsmen with different outfits would share frames. Both importers work around this by clearing `Actor._frame_cache` / `_image_cache` manually.
  *Fix:* include selected body/head/headgear/palette identity in both keys.
  *Expected result:* Two actors of the same job with different outfits or heads render their own art side by side in Godot. The importers no longer need to clear the actor caches by hand.
- [x] **B6. The game cannot load Character Lab output.** The Godot actor only loads native SPR pairs and has no headgear part. Needs a module manifest (“for part P, replace SPR indexes with these PNGs / this palette”) and a headgear layer. (ROADMAP step 5; these are the concrete missing pieces.)
  *Expected result:* The accepted Wayfarer body and head (and a headgear choice) appear on the player in the Godot field, animating with the native ACT. Swapping outfit or headgear during play changes only that module.
- [~] **B7. Slot list is hardcoded to one action/facing.** `export_native_template.gd` hardcodes `[82,83,84,85,86,54]` and direction 6.
  *Fix:* derive required slots from ACT — walk every action group × direction the job uses and collect the image indexes each part references. That set is the real per-character art budget (usually far smaller than frames × 8 because RO reuses drawings and mirrors W↔E). Measure it before committing to the workflow's scale.
  *Expected result:* A generated inventory lists, per part, every SPR index that all used actions × 8 directions reference, with sizes and a total. This gives the real number of drawings a new character needs, and the template exporter reads that list instead of a hardcoded one.

## C. RO animation faithfulness

- [ ] **C8. Damage lands before the visible hit.** Body attack action 86 has sound event `attack_sword.wav` on frame 5 of 9 (≈56%). Gameplay applies damage at `ATTACK_HIT_FRACTION = 0.45` (`rpg_rules.gd`), while the wind-up frame 4 is still shown. Compressing the clip to the attack interval (`main.gd` `_start_attack`) is fine — RO scales attack motion by ASPD — but the hit time should come from the ACT event frame.
  *Expected result:* Damage numbers and the hit reaction appear on the source's strike frame (the `attack_sword.wav` event), at any attack speed. A test asserts that hit time = event frame ÷ frame count × clip duration.
- [ ] **C9. Draw order is fixed for every direction.** `native-core.mjs` and the Godot actor use body → head → headgear → weapon → trail. In RO, weapon/shield draw behind the body for away-facing directions, headgear is ordered lower → mid → top, and garments use per-job/per-direction tables. Store an order table per direction in the template before adding a second facing.
  *Expected result:* The template stores a draw order for each direction. Away-facing directions draw the weapon behind the body. Browser and Godot use the same table, and parity fixtures cover at least one away-facing direction.
- [ ] **C10. Unarmed attack differs between tools.** Godot switches to action group 5 without a weapon (`_get_action`); the Lab only hides the dagger. RO chooses attack action 5 / 10 / 11 by job and weapon type — keep that mapping in data.
  *Expected result:* Unequipping the weapon selects the same native unarmed action in both the Lab and Godot. The choice between attack action 5, 10 and 11 comes from a job/weapon table.
- [ ] **C11. Verify tick length.** `ro_sprite_data.gd` uses 24 ms per ACT tick (4 ticks → 96 ms). roBrowser/ActEditor are believed to use 25 ms (→ 100 ms). Unconfirmed; check against their source.
  *Expected result:* Tick length is confirmed against roBrowser/ActEditor source with a cited reference. If it is 25 ms, native clips measure 100 ms per frame and saved evidence is updated.
- [ ] **C12. Missing actions fall back silently.** `_get_action()` substitutes the idle action for a missing index without warning. Report it.
  *Expected result:* Requesting a missing action logs a warning naming the job, action and direction, instead of silently showing idle.

## D. Process and CI

- [ ] **D13. Public CI tests the abandoned path.** CI runs only `modular-motion`/`modular-engine` (cutout rig). `native-core.mjs` — the code the workflow depends on — is untested publicly. Add tiny synthetic ACT/SPR-shaped fixtures for composition, attachment and draw order.
  *Expected result:* Public CI runs `native-core.mjs` tests on synthetic fixtures (no RO files) and fails on composition, attachment or draw-order regressions.
- [ ] **D14. Importers are Wayfarer-specific.** The head importer hardcodes the Wayfarer body pack and head slot; the costume importer only accepts `--output-dir`. Move this into the recipe loader proposed in [WORKFLOW.md](WORKFLOW.md), including palette/style-bible references from A1/A4.
  *Expected result:* Body and head imports run from one recipe file for any character/pack. Wayfarer v2 is reproduced byte-for-byte through the recipe, and a second character needs only a new recipe, with no script edits.
- [~] **D15. Side effects inside `assert`.** `assert(image.save_png(...) == OK)` performs the save inside the assertion; builds with asserts disabled skip the save.
  *Expected result:* No side effects inside `assert`. Failed saves report an error and exit non-zero.

## Order of work

1. A1–A3: shared palette quantizer, block-majority downscale, key unmixing; re-import Wayfarer into a **new** pack and review it visually (keep v2 untouched).
2. B7: ACT-driven required-slot inventory for all eight directions of one job.
3. B5–B6: appearance-aware caches and a replacement-texture manifest in the Godot actor.
4. Prove a **second character on the same template** with the same palette and style bible before adding a second action.

## Progress log

- 2026-09-24 — inspection recorded; work started on branch `fix/style-consistent-import`.
- 2026-09-24 — **A1–A3 adapter landed** (`tools/character-lab/indexed_import.gd`, `build_style_palette.gd`, `--palette` on both importers; see [WORKFLOW.md](WORKFLOW.md#indexed-style-palette-adapter-2026-09-24)). Legacy path still reproduces v2 body / v1 head byte for byte.
  - Result on the saved Wayfarer boards → local packs `native-wayfarer-v3` + `native-head-v2` with palette `wayfarer-style-v1` (48 colors): body slots **46–48 colors** (native 37–55, previously 1,347–1,691), head **20** (native 19, previously 417). **0** off-palette, key-tinted or partial-alpha pixels. Silhouette IoU unchanged (0.926–0.964 body, 0.820 head). 108/108 viewer frames pixel-identical to Godot, no console errors.
  - A2 confirmed: head source was 1254×1254 for a 1024 reference, and body 1536×1024 for 1440×960. Both now import through fractional block majority.
  - **Open for A1:** the ready-pose vest reads slightly duller than v2 because the automatic palette has only 3–4 teal shades. Needs visual review; the durable fix is hand-authored ramps (A4). The palette is auto-derived and not yet reviewed. A1 stays partial until a second character shares it.
  - **Visual review 2026-09-24:** the user compared v3 body / v2 head against v2 / v1 in the viewer: "good better, pass". Palette `wayfarer-style-v1` and packs `native-wayfarer-v3` + `native-head-v2` are accepted as the new Wayfarer baseline. A1 stays partial only until a second character reuses the palette (its *Expected result*).
  - D15 fixed in the two importers only (`Indexed.save_png`); exporters still save inside `assert`.
- 2026-09-24 — **B7 inventory tool landed** (`tools/character-lab/export_slot_inventory.gd`; output `tools/character-lab/assets/slot-inventory/<job>.json`, local). It walks all 13 action groups × 8 directions of each part's ACT.
  - **RO's budget structure:** idle, walk and sit have **5 drawn views** (S, SW, W, NW, N); the east side reuses them mirrored. Every other action group (pickup, ready, attacks, hit, freeze, dead, cast) has only **2 drawn views**: *front* (S, SW, E, SE) and *back* (W, NW, N, NE). Head: 5 views × 3 head-turn drawings = 15 in total.
  - **Male Swordsman, drawings to supply:** body **118** in total, **94** for the groups the game uses (idle 5 · walk 40 · sit 5 · pickup 4 · ready 12 · hit 4 · dead 2 · attack2 10 · cast 12); head 15; dagger 5; trail 8; each headgear 9. Male Novice body: 110 / 86. Walk is the largest single cost (40 drawings).
  - **Consequence:** the accepted Wayfarer body slots 82–86 are the *whole front view* of attack2, so the attack already works in S, SW, E and SE (local render: `assets/slot-inventory/wayfarer-v3-attack-front-view.png`). Wayfarer covers 6 of the 94 gameplay body drawings (5 attack + 1 ready), plus head slot 1 of 15.
  - **Workflow implication:** plan generation boards per *action group × drawn view* (e.g. "attack2 back: 87–91"), not per direction.
  - **Style-bible rule found (A4):** mirrored views flip asymmetric details. The Wayfarer hip pouch changes sides between S and E. Either design costumes to tolerate flipping (RO does) or keep key details symmetric.
  - Still open for B7: `export_native_template.gd` still hardcodes its six slots. Its *Expected result* (template exporter reads the inventory) belongs to the recipe loader work (D14).
- 2026-09-24 — **B5 + B6 landed.**
  - `ro_sprite_actor.gd` has `set_appearance(manifest)` and `set_headgear("" | "cap" | "hat")`. The frame cache key includes the look; replaced parts get a distinct `source` identity, so the image cache cannot mix looks. ACT records stay shared with the native data (identity-checked in the test).
  - Appearance manifests live in `tools/character-lab/appearances/`. `wayfarer-v3.json` points to the accepted packs, and every file is checked against the pack's SHA-256 on load. A part applies only when its native source matches the pack's template: Swordsman body art never repaints the Novice, while the shared head applies to both. The look persists across job changes and saves (`look` in the save file).
  - In game: **O** cycles the outfit and **H** cycles headgear; the message reports coverage (e.g. "body 6/118, head 1/15"). QA flags: `--appearance=<manifest>`, `--headgear=<id>`.
  - `tests/appearance_test.gd` (48 checks, local assets): a native and a Wayfarer actor render interleaved. The game actor matches the Lab fixtures pixel for pixel for none/cap/hat (27 frames), and matches native after removing the look. Existing suites unchanged: gameplay QA 71, progression playthrough 39, sprite 352, map 2614, RSM 179, rules 68.
  - Visible limit: only the covered drawings change. Walk, idle and the attack back view still show native Swordsman clothing under the Wayfarer head, until those drawings exist (see B7 budget).
  - Headgear draw order is still the single studied order (C9 open), and the game reads art packs from `tools/character-lab/assets/`. Exported builds would need those packs included.
