# Reuse the native action; replace the artwork

**Public checkout:** the scripts and this workflow are versioned publicly; the artwork, template manifests and visual evidence referenced below require the local study pack. See [repository scope and setup](../PUBLIC_REPOSITORY.md). Successful generation requests are also saved as public [prompt text](prompts/README.md).

This is the working process from the Wayfarer body and head studies, recorded on 2026-09-24. The reusable idea is **a fixed action template plus independently versioned art modules**. It has been demonstrated for male Swordsman dagger action 86, direction 6 (labelled east in the exporter), with nine 96 ms frames. It is not yet a generic character-production tool.

The selected body action uses SPR indexes `[82, 83, 83, 83, 84, 85, 86, 86, 86]`: five complete body drawings, not nine separately generated poses. Head SPR index 1 is reused across all nine frames. Body/clothes, head/face/hair, headgear, weapon and trail are separate modules; shirt, vest, arms and legs are not separate runtime parts in this approach.

## Existing stages and their contracts

All paths in the table are relative to `tools/character-lab/` unless stated otherwise. The source of truth is the code and local manifests linked here, rather than a prompt's claim that its output stayed aligned.

| Stage | Existing implementation | Concrete inputs → outputs | Invariant / review |
| --- | --- | --- | --- |
| 1. Read native source | Repository `scripts/ro_sprite_data.gd` and `scripts/ro_sprite_actor.gd`; `export_native_template.gd` | Original local ACT/SPR pairs → `assets/native-template-v1/template.json`, decoded `sprites/*/*.png`, registered `attack/frame-*.png` | Retain source file hashes, ACT image indexes, duration, events, offsets, anchors, mirror, rotation and scale. Exported composites are local reconstructions, not official-client captures. |
| 2. Make fixed artwork slots | Body: `export_native_template.gd`; head: `prepare_native_head.gd` | Decoded source bitmaps → body `sprite-slots.json` + `sprite-slot-board-5x.png`; head `head-slot.json` + `head-slot-board-16x.png` | Raw SPR orientation; fixed bitmap margins and crop rectangles. Do not apply ACT mirroring to the input and then apply it again at playback. Body has six cells: five attack drawings and one extra ready drawing. |
| 3. Generate a candidate | Built-in ImageGen reference-image edit; saved prompt and provenance in each art pack | Fixed native board **as geometry reference** + `assets/modular-v1/parts-atlas-keyed.png` **as design reference** → untouched `native-wayfarer-v2/costume-slot-board.png` or `native-head-v1/generated-head.png` | Ask for the established Wayfarer design while preserving poses, scale, registration and board background. Save exact prompt, both reference roles, original output and SHA-256. Generation is not deterministic; the saved source image is the reproducible import input. |
| 4. Import body art | `import_native_costume.gd` | Source board + `native-template-v1/sprite-slots.json` → pack `costume/body/*.png`, `costume.json`, `costume/attack/*` | Resize the whole board once to 288×192 with nearest sampling; key magenta; crop exact source rectangles. No individual recentering, silhouette forcing or ACT edits. `--output-dir` selects the output art pack. |
| 5. Import head art | `import_native_head.gd` | `native-head-v1/generated-head.png` + `head-slot.json` + existing Wayfarer body and native equipment → `head/001.png`, `head.json`, 27 fixtures across none/cap/hat | Normalize whole board to 64×64; fixed crop `[17,19,30,26]`; preserve the 30×26 bitmap and original head ACT. No headgear baked into the face/hair artwork. |
| 6. Export equipment | `export_native_equipment.gd` | Native `assets/native-equipment-v1/source/{cap,hat}.{act,spr}` → `equipment.json`, decoded sprites and composite fixtures | Headgear keeps its own action and attaches using body anchor minus accessory anchor. Native source cap, hat, dagger and trail remain reference artwork. |
| 7. Assemble and play | `native-core.mjs` + `native.js` | Template + selected body/head/equipment maps → synchronized original/custom previews and cached scene frames | One native playhead; part frame selection uses the body frame modulo each part's frame count. Order for this facing is body → head → headgear → weapon → trail. Cache identity includes selected modules. |
| 8. Technical QA | `tests/native-template.test.mjs`, `tests/native-modularity.test.mjs`, `tests/native-head.test.mjs`; startup comparison in `native.js` | Source and output manifests/PNGs → test results and 72 pixel comparisons against Godot fixtures | Check file hashes, dimensions, indexes, module isolation, timing, attachment and composition. Alpha overlap and out-of-crop pixels are diagnostics; a changed costume or hair silhouette may legitimately differ. |
| 9. Visual review | `native.html`, source/contact boards, per-pack `browser-verification.json` | Same-frame original/custom comparison + actual playback + equipment switches → dated visual findings | Judge costume identity, head scale, silhouette, pixel clusters, joint continuity, headgear overlap, foot stability and perceived force. Technical pass does not approve the artwork. |
| 10. Save a version | Versioned asset directories + provenance/manifests + the release snapshot tooling documented beside this file | Source, action, art, code and evidence hashes → an identifiable, reviewable local baseline | Preserve earlier candidates. Freeze selected references and source images; record scope and user feedback separately from test status. |

The current importer uses normalized RGB thresholds `r > 0.65`, `b > 0.6`, `g < 0.45` and `r + b - 2*g > 0.85` for the magenta key. This is a saved adapter choice, not a universal transparency rule. A future design containing magenta needs a different keyed background or a transparent-image adapter, followed by fresh review.

## Indexed style-palette adapter (2026-09-24)

Added after the [workflow inspection](INSPECTION-2026-09-24.md), items A1–A3. `--palette=<style.json>` on either importer selects `indexed_import.gd` instead of the resize-and-threshold path above. Without the flag, both importers still reproduce `native-wayfarer-v2` and `native-head-v1` byte for byte.

- **Palette only.** Every opaque output pixel is an exact entry of the style palette, with full alpha. Body and head of one character, and different characters of one style, share the same file. Manifests record `import.palette` (id, path, SHA-256) and per-slot `uniqueColors`, `offPalettePixels`, `keyTintedPixels` and `partialAlphaPixels`; the import asserts that the last three are zero.
- **Grid-independent downscale.** Each source pixel is classified first. Each target pixel then takes the majority class of its fractional source block (ties: the block center). A 1536×1024 result of a 1440×960 reference imports correctly.
- **Key unmixing.** An edge pixel is modelled as `t·magenta + (1−t)·palette color`; `t ≥ keyBlendThreshold` (0.5) becomes transparent, otherwise the palette color.

Build or rebuild a palette from accepted artwork, then review and edit it by hand. It is an asset with its own version:

```sh
.tools/Godot.app/Contents/MacOS/Godot --headless --path . --script res://tools/character-lab/build_style_palette.gd -- \
  --id=wayfarer-style-v1 --colors=48 --out=res://tools/character-lab/style/wayfarer-style-v1.json \
  --inputs=<comma-separated accepted slot PNGs>
```

The default split is variance-based median cut in Oklab plus six k-means passes. Population weighting under-served the small teal vest; the variance split gives it a three-to-four shade ramp. Automatic palettes remain a bootstrap. Hand-authored material ramps belong to the style bible (inspection A4).

Import a new pack from a saved generated board without touching earlier packs:

```sh
G=.tools/Godot.app/Contents/MacOS/Godot; A=res://tools/character-lab/assets; P=res://tools/character-lab/style/wayfarer-style-v1.json
$G --headless --path . --script res://tools/character-lab/import_native_costume.gd -- --output-dir=$A/native-wayfarer-v3/ --source=$A/native-wayfarer-v2/costume-slot-board.png --palette=$P
$G --headless --path . --script res://tools/character-lab/import_native_head.gd -- --output-dir=$A/native-head-v2/ --source=$A/native-head-v1/generated-head.png --costume=$A/native-wayfarer-v3/ --palette=$P
$G --headless --path . --script res://tests/indexed_import_test.gd
node --test tools/character-lab/tests/native-indexed.test.mjs
```

`indexed_import_test.gd` uses synthetic images only. `native-indexed.test.mjs` needs the local packs; it checks palette membership and 36 frames of Node/Godot pixel parity. The viewer offers both packs as "style palette" options and includes them in its startup parity check.

## Generation gate (2026-09-25)

Size rules are a limit of the harness, not advice in a prompt. `tools/character-lab/style/style-bible-v1.json` holds the palette reference, skin palette indices and per-part slot rules (area, bounds, silhouette overlap, outline length and, for heads, the native face size). The same numbers drive three steps:

1. **Brief.** `verify_candidate.gd --brief --part=head` prints the SIZE CONTRACT section. Paste it unchanged into the generation prompt.
2. **Gate.** Check the untouched generated board before importing it: `verify_candidate.gd --part=head --source=<generated png>` prints PASS/FAIL per slot with reasons, and exits 1 on failure. `--pack=<dir>` checks an already-imported pack.
3. **Import.** `--style-bible=<json>` on either importer sets the palette and runs the same gate first. A failing candidate writes nothing, unless `--allow-contract-failure` is given for a study pack; the manifest then records the failure. Passing manifests record the contract result and bible hash.

```sh
G=.tools/Godot.app/Contents/MacOS/Godot; A=res://tools/character-lab/assets; B=res://tools/character-lab/style/style-bible-v1.json
$G --headless --path . --script res://tools/character-lab/verify_candidate.gd -- --brief --part=head
$G --headless --path . --script res://tools/character-lab/verify_candidate.gd -- --part=head --source=$A/native-head-v3/generated-head.png
$G --headless --path . --script res://tools/character-lab/import_native_head.gd -- --output-dir=$A/native-head-v3/ --costume=$A/native-wayfarer-v3/ --style-bible=$B
```

Rejected candidates are regenerated, never scaled or repaired in the importer. Scaling pixel art by one or two pixels destroys the clusters, and repairing would hide the difference from review. `tests/slot_contract_test.gd` checks the contract on synthetic heads.

At introduction, the accepted body `native-wayfarer-v3` passed every slot. Head `native-head-v2` failed: area 86% and face 25% of native (a 5×5 face against 10×11). That matched the user's in-game observation that the head looked small.

## Boards for any action and view (2026-09-26)

`export_slot_board.gd` makes a generation board for any action group and drawn view, from the ACT-driven inventory (`export_slot_inventory.gd`). `--direction` picks the view containing that direction. Each board folder under `tools/character-lab/assets/boards/<job>-<part>-<group>-<view>/` holds:

- `slot-board-5x.png`: image 1 for the generator (raw SPR drawings on magenta, same placement rule as the original template board);
- `design-reference.png`: image 2, from the character spec `tools/character-lab/characters/<id>.json` (for Wayfarer, the accepted front-view clothing);
- `prompt.txt`: filled from the character spec and the style bible, including a per-cell SIZE CONTRACT and the raw facing (front view faces screen-left toward the camera; back view faces screen-left away from it);
- `context-frames.png` (how the drawings play), `sprite-slots.json` (layout, sequences, source hashes), `HOWTO.txt` and `candidates/`.

```sh
G=.tools/Godot.app/Contents/MacOS/Godot; B=res://tools/character-lab/assets/boards/swordsman-male-body-attack2-W-NW-N-NE/
$G --headless --path . --script res://tools/character-lab/export_slot_board.gd -- --group=attack2 --direction=2
$G --headless --path . --script res://tools/character-lab/verify_candidate.gd -- --board=$B --source=<candidate>
$G --headless --path . --script res://tools/character-lab/import_slot_board.gd -- --board=$B --source=<candidate> --output-dir=res://tools/character-lab/assets/<new pack>/
```

`import_slot_board.gd` applies the palette adapter and the slot contract (refusing failures), then writes `pack.json`, the part's PNGs and fixture frames for every direction of the view. It checks that the native ACT is unchanged. Appearance manifests accept a list of packs per part, merged by slot, e.g. `"body": [<attack front pack>, <attack back pack>]`. `tests/slot_board_test.gd` runs the whole path without generated art: a shrunken candidate is refused and writes nothing; the board's own native image imports with every silhouette pixel-exact; a merged look covers 11 body drawings.

## Reproduce the existing candidate

For review and version preservation, use the implemented snapshot entry point first:

```sh
python3 tools/character-lab/pipeline.py verify
python3 tools/character-lab/pipeline.py snapshot
python3 tools/character-lab/pipeline.py verify-snapshot docs/character-lab/releases/native-art-poc-v0.1.0/manifest.json
```

The default configuration is `tools/character-lab/pipeline/native-art-poc-v0.1.0.json`. `verify` checks source/manifest hashes and runs the 18 native Node tests; it does not regenerate artwork or Godot exports. `snapshot` writes an immutable local artifact archive and inventory below `docs/character-lab/releases/native-art-poc-v0.1.0/` and refuses to overwrite that release. The pack preserves the Character Lab (including earlier experiments), selected native ACT/SPR sources, the local Godot source decoder/actor and project file, and this study's documentation. This is an artifact version, independent of whether the repository has a Git commit or tag.

The pipeline configuration is a working verification/packaging contract for the v0.1.0 snapshot. Rebuilding the current accepted packs from validated configuration is done by `art_recipe.py`, described [below](#reproduce-the-saved-wayfarer-packs-from-a-recipe-d14-2026-10-02). Neither automates the ImageGen step.

Run from the repository root. These commands use saved generated images and local source assets; they do not call ImageGen again. They overwrite derived files in the named packs, so verify the saved baseline first and use a new pack for a new candidate.

```sh
.tools/Godot.app/Contents/MacOS/Godot --headless --path . --script res://tools/character-lab/export_native_template.gd
.tools/Godot.app/Contents/MacOS/Godot --headless --path . --script res://tools/character-lab/export_native_equipment.gd
.tools/Godot.app/Contents/MacOS/Godot --headless --path . --script res://tools/character-lab/import_native_costume.gd -- --output-dir=res://tools/character-lab/assets/native-wayfarer-v2/
.tools/Godot.app/Contents/MacOS/Godot --headless --path . --script res://tools/character-lab/prepare_native_head.gd
.tools/Godot.app/Contents/MacOS/Godot --headless --path . --script res://tools/character-lab/import_native_head.gd
node --test tools/character-lab/tests/native-template.test.mjs tools/character-lab/tests/native-modularity.test.mjs tools/character-lab/tests/native-head.test.mjs
```

Open the repository's `Character Lab.command` launcher, then [the native comparison](http://127.0.0.1:8767/native.html). It reports browser pixel parity after loading. Step all nine frames, switch the head independently of the costume, inspect cap/hat/none, and check the weapon visibility control. Weapon removal currently hides the dagger and trail; it does **not** select a native unarmed action. Looping jumps from the original follow-through to the first frame; no synthetic recovery is added.

When measuring performance, record the selected outfit/head/equipment, actor count, browser/environment, cold nine-frame composition cost and cached scene CPU submission median/p95 separately. The present repeated-character scene shares nine cached compositions. Its figures exclude gameplay and GPU completion and do not establish performance for 128 unique outfits.

## What to extract next, and what already works

The shared playback and composition code in `native-core.mjs` already accepts texture maps and action records. It is the strongest existing reusable module. The web page already assembles body, head and headgear independently, and the costume importer can write the same body template into another art directory.

The production scripts are still adapters for this experiment. The body exporter hardcodes Swordsman, direction 6, slot indexes and board layout. The body importer hardcodes that template and source action. The head preparer/importer hardcode head slot 1, its crop, the Wayfarer body pack and three equipment combinations. Body and head use different manifest shapes and output directories. The viewer hardcodes pack paths and the reference-fixture matrix. These limitations should remain visible until a second character or action proves the abstraction.

The next small extraction is a recipe loader around these existing pieces:

1. Describe the selected source action, direction and required image slots in data. Enumerate slots from ACT rather than assuming `[82…86]`.
2. Put board layout, fixed crops, transparency rule and output module name into an import adapter configuration. Keep full-board normalization and fixed-crop semantics.
3. Resolve independent body/head/headgear/weapon/trail manifests through one assembly recipe. Keep renderer inputs unchanged initially.
4. Produce the required fixture combinations and evidence inventory from that recipe. Add new fixtures when adding a direction, action or module combination.

Start by expressing the existing successful body and head packs through that recipe, then prove a second case. A complete job editor, generic rig or large plugin system is not necessary to validate this reuse.

## Reproduce the saved Wayfarer packs from a recipe (D14, 2026-10-02)

The earlier "proposed recipe shape" sketch is replaced by a smaller, implemented contract for this saved-art milestone. `tools/character-lab/art_recipe.py` reads `tools/character-lab/recipes/wayfarer-saved-art-v1.json` and rebuilds three saved packs from their saved generated images with the existing importers. It does not generate art and does not change any appearance manifest.

| Module | Adapter (importer) | SPR slots | Saved pack reproduced | Status | Gate |
| --- | --- | --- | --- | --- | --- |
| `body-attack-front` | `native-costume-v1` (`import_native_costume.gd`) | 82–86 attack + 54 ready, layout `native-template-v1/sprite-slots.json` | `native-wayfarer-v3` | accepted | strict |
| `head-v2-historical` | `native-head-v1` (`import_native_head.gd`) | head 1, layout `native-head-v1/head-slot.json` | `native-head-v2` | historical | recorded failure |
| `body-attack-back-v2` | `slot-board-v1` (`import_slot_board.gd`) | 87–91, board `swordsman-male-body-attack2-W-NW-N-NE` | `native-wayfarer-attack-back-v2` | pending visual review | strict |

The body layout must be the six-slot template layout. A generic attack2 board has only five slots and cannot express ready slot 54, so it cannot stand in for v3.

```sh
python3 tools/character-lab/art_recipe.py validate tools/character-lab/recipes/wayfarer-saved-art-v1.json
python3 tools/character-lab/art_recipe.py run tools/character-lab/recipes/wayfarer-saved-art-v1.json --out /tmp/wayfarer-reproduction-1
# Strict gating of every module, including the historical head: must exit 1 and create nothing.
python3 tools/character-lab/art_recipe.py run tools/character-lab/recipes/wayfarer-saved-art-v1.json --out /tmp/wayfarer-strict-1 --strict
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tools/character-lab/tests -p 'test_*.py' -v
```

`--module <id>` (repeatable) limits a run; the head needs its fixture body module selected too. `--godot` or `GODOT` selects the executable (default `.tools/Godot.app/Contents/MacOS/Godot`). Prefer an output directory outside the repository; a later Godot launch may add `.import` caches to output inside it.

**Godot logs.** Every Godot call the runner makes passes an absolute `--log-file`. That keeps Godot out of its default `user://logs` rotation, which crashed with signal 11 in a sandbox that cannot write the user's application-data folder.

- The log files go in a private temporary folder under `--log-dir`, `ART_RECIPE_LOG_DIR` or the system temporary folder. That folder must exist and must not be inside the output or a protected folder.
- After the gates pass, the logs are copied to `<out>/godot-logs/`. On a refused gate they are deleted with the temporary folder, and the Godot output is printed instead.
- When running the importers or `verify_candidate.gd` by hand in such a sandbox, add `--log-file <absolute path>` after `--headless` in the same way.

**What `validate` (and the first stage of `run`) checks, writing nothing.** Exit status 2 on any failure.

- Schema: known keys only, `schemaVersion` the JSON integer 1 (not `true` or `1.0`), known adapter/status/gate values, unique module ids and outputs, a reason for every expected manifest difference. Action contracts compare JSON values with booleans kept distinct from numbers.
- Pinned SHA-256 of every input: native ACT/SPR files, template, slot layout, equipment manifest, style bible, palette (also against the bible's own palette reference) and each generated image. The native drawings fed to the size gate are pinned too: template body drawings by the hashes `template.json` records under `parts.body.textures`, the native head by `head-slot.json` (cross-checked with the template) and board drawings by their `sourceSha256`. All pinned inputs are re-hashed after the run.
- Paths: recipe paths are `res://` and must resolve, after symlinks, inside the repository. File records in saved and reproduced manifests must be relative and stay inside their own pack folder (the palette `res://` record excepted). Absolute paths, `..` and symlinks leading outside are rejected.
- Coverage: `coverage.parts.<part>` needs a positive integer `total` (and optional `gameplay` no larger than it) for every module's part. If `coverage.inventory` exists it must be valid JSON with matching `parts.<part>.uniqueSlotCount`. If the inventory file is absent, the report says the totals are declarations only.
- Geometry: the layout's slot indexes and `imageRect`s equal the recipe's, in order; every crop lies inside its cell and the canvas; every crop has the native drawing's exact size; the generated image has the declared size and the canvas aspect ratio.
- Action contract: `native-costume-v1` and `native-head-v1` still hardcode Swordsman action 86, direction 6, 96 ms frames, ready action 38 and the cap/hat variants, so the recipe must state exactly those values. Attack slots must be the drawings of the attack sequence and ready slots `[54]`. For boards, group, view directions, sequences and frame duration must match the board's layout.
- Saved packs: every file recorded in the saved manifest still has its hash. Each saved manifest is cross-checked only against the dependencies it actually records:
  - **Body v3 and head v2:** generated image, slot layout, template, palette, plus equipment and the body pack for the head. Both predate the slot contract and were imported with `--palette` only, so their manifests record no style bible. The bible pin and its strict/recorded gate are applied for the first time by the reproduction; the expected `contract` difference says so.
  - **Back-view v2:** generated image, board layout and palette, plus the style bible it was gated with.
- Labels: the output folder must keep the saved pack's name, so a reproduction cannot be relabelled as another version, such as `native-head-v3`. Only a `historical` module may use the `recorded-failure` gate.
- Output: `--out` must be new or empty, must not contain the repository, and must not be inside `assets/`, `docs/`, `scenes/`, `scripts/`, `tests/`, `.git`, `.godot`, `.tools` or the Character Lab asset, appearance, character, style, recipe, pipeline, QA or test folders.

**Gate stage.** `verify_candidate.gd` checks every selected candidate before anything is imported (it writes no files). Strict modules must PASS. A `recorded-failure` module must still FAIL. If it now passes, the recipe is stale and the run stops. `--strict` treats every module as strict, so the undersized head v2 stops the run. A failed gate exits 1, and the output directory is not created.

**Import stage.** Each module is imported into `<out>/<saved pack name>/` with `--style-bible`, so accepted modules are gated again by the importer. The historical head adds `--allow-contract-failure`, and its manifest records `contract.pass = false` instead of skipping the gate. Head fixtures render on the freshly reproduced body; the back view is imported independently. Importers record `"recipe": {"path", "sha256", "module"}`. Although `recipe` is a declared manifest difference, its content must equal exactly the validated recipe's path, the SHA-256 of the validated bytes and the module id; absent or different provenance fails. The recipe is read once; that one read is both hashed and parsed. At the end of validation the file must still have that hash, otherwise validation fails with exit 2. The recipe's bytes are then re-hashed before the gates and again before the output folder is created; a change at either point exits 2 with nothing written. They are re-hashed once more at the end, and an edit during the imports is reported as a problem. The costume importer now creates its folders only after its gate.

**Comparison and report.** For each module, every file record in the saved manifest must reappear at the same JSON path with the same file name and SHA-256, and the reproduced file must have those bytes. That covers slot drawings, normalized boards, fixture frames and contact boards. Every other manifest difference must be listed under `expectedManifestDifferences`. The recipe currently allows these:

- `recipe` everywhere;
- `contract` for the body (strict result now recorded) and the head (failing result now recorded);
- `costumeManifest` and `costumeManifestSha256` for the head (it uses the reproduced body).

The run also checks importer-reported ACT fingerprints, slot sets, source actions and frame counts and timing, and flags stray files. It re-hashes all pinned inputs after the run, and hashes the saved pack, appearance, style and source folders before and after (Godot `.import` caches are reported, not failed). `<out>/reproduction-report.json` and `<out>/REPORT.md` record the outcome, the coverage per part and the recipe's remaining decisions. Exit 0 only when everything matches.

The report only states what that run established. It lists the selected modules and names the unselected ones, which are neither imported nor counted in coverage. Each module's import is recorded as `completed`, `failed` or `skipped after … failed`. PNG counts and per-module checks appear only for modules that were compared, and inputs changed during the run are listed by name. The claims "fixtures rendered on the reproduced body" and "ACT unchanged" appear only when that module's check passed. Failure reports are written whenever the output folder already exists, that is, after the gate stage.

**Limits.** D14 remains partial. The two native adapters (`import_native_costume.gd`, `import_native_head.gd`, plus the hardcoded template and head-slot paths in `verify_candidate.gd`) remain fixed to this one Swordsman action and facing; the recipe validates against them rather than generalizing them. Other actions and views go through `slot-board-v1`. Byte equality depends on the same Godot build (4.5.1 here) re-encoding the PNGs. The report does not run a browser or the game and does not refresh saved browser evidence. Weapon, trail and headgear remain native reference modules and are not recipe modules. A second character (A1), head v3, walk boards and visual acceptance of the back view are outside this recipe.

Asset-independent tests (`tools/character-lab/tests/test_art_recipe.py`) build a miniature repository and a fake Godot. The fake Godot requires `--log-file`, simulates gates and either a successful slot-board import, a failing import or an import that alters an input.

- **Rejected configurations:** changed or missing sources, and same-size altered native drawings (template, head and board); missing template drawing hashes; geometry and aspect mismatches; a five-slot layout in place of the six-slot body; action-contract and schema errors, including boolean `schemaVersion` and indexes; relabelling and acceptance of the failing head.
- **Coverage and paths:** malformed inventory and coverage entries; symlinked inputs and saved records outside the repository or pack; `..` and absolute record paths; unsafe output and log folders.
- **Runs:** a strict head failure, a stale recorded failure or a failing accepted body exits 1 without creating the output folder, and logs stay in a removed private folder.
- **Reports:** a back-view-only run passes and reports only that module. A failed import reports nothing it did not check. An input changed mid-run is named. Absent or wrong recipe provenance (missing block, other module, hash or path) fails. A recipe edited during an import is reported, and a recipe edited after validation exits 2 before any Godot call. Empty and `.` paths, including `res://.`, are rejected as invalid configuration.
- **Comparison:** byte and manifest comparison, keeping `true` distinct from `1`. `ART_RECIPE_LOCAL=1` adds the real recipe validation and the real strict head refusal. `ART_RECIPE_FULL=1` adds a full reproduction into a temporary folder.

Independent local acceptance results and the retained output paths are in [the 2026-10-02 QA handoff](REPRODUCTION-QA-2026-10-02.md).

## New art for any action, view or character (2026-10-02)

The reproduction above rebuilds saved packs. New art uses the same runner with `slot-board-v2` modules (`artwork-import-recipe`):

1. A board plan exports the boards.
2. A character spec supplies the text and design references.
3. `lock` and `pin` record the board and candidate hashes.
4. `run` gates, imports and verifies.
5. `promote` installs the packs.
6. `coverage` lists native fallback per action and direction.

The saved costume and head importers now read their template, slots, actions, fixtures and labels from `tools/character-lab/importers/*.json`. Commands, the module table and open dependencies are in [COMPLETION-2026-10-02.md](COMPLETION-2026-10-02.md).

## Version boundaries and saved evidence

| Version boundary | Change that creates a new version | What stays independent |
| --- | --- | --- |
| Native source snapshot | Different ACT/SPR bytes or source selection | Repainting a vest does not modify or overwrite source files. Save source provenance and exact file hashes. |
| Action template | Different action/direction coverage, timing, placement semantics or extraction contract | New artwork can reference the same template and unchanged ACT. Renderer/extraction corrections need explicit evidence updates. |
| Art module | New costume, head/hair, equipment design, prompt result or import result | Body v3 can continue to use head v1 and the original action. Keep generated source, prompt, references, import settings, indexed PNGs and hashes together. |
| Assembly recipe | Different selected module versions, supported combinations or assembly configuration | Switching a head does not manufacture a new body or new source action. Record the precise dependency versions. |
| Renderer/tooling | Composition, adapter or cache behavior changes | Asset identity stays fixed unless its bytes change. Rerun parity and relevant tests before reusing old performance findings. |
| Review/evidence | A new test run, benchmark environment or visual judgment | A technical pass and user artwork acceptance are distinct facts with their own date and scope. |

A frozen artifact pack should record a stable version ID, source and dependency manifests with SHA-256, recipe selection, code revision/file hashes, exact generation provenance, import adapter version, slot contract, technical checks, visual findings and known limits. It should contain or reference every file needed to reproduce the saved result, including raw generated boards; saving only final composed PNGs loses modularity and provenance.

Keep changes narrow: a new art candidate gets a new art directory and recipe selection while the source action stays fixed. A new action gets its own coverage and fixtures. Never silently relabel older evidence as covering additional actions, directions, hats or artwork.

## Evidence and review scope

### Current scope (2026-10-02)

- **Accepted look:** `tools/character-lab/appearances/wayfarer-v3.json` uses body `native-wayfarer-v3` (SPR 82–86 + 54) and head `native-head-v2` with palette `wayfarer-style-v1`. The head fails the size contract added on 2026-09-25 and stays only until a head v3 candidate passes the strict gate; none has been generated.
- **Preview look:** `wayfarer-preview.json` adds the attack2 back view v2 (SPR 87–91). It passes the slot contract but awaits the user's visual acceptance.
- **Game integration** (inspection B5/B6, 2026-09-24): the Godot actor loads appearance manifests. **O** cycles outfits and **H** cycles headgear, and `tests/appearance_test.gd` compares game frames with the Lab fixtures.
  - Coverage is still small: body 6 of 118 drawings accepted (+5 pending), head 1 of 15.
  - Walk, idle and the other actions show native Swordsman clothing. Draw order, hit timing and unarmed-action items C8–C12 remain open.
- **Reproduction:** `art_recipe.py` (above) rebuilds these three packs from their saved generated images and writes a dated report. Such a report covers its own run only; it adds no browser or visual review.

### v0.1.0 evidence (historical, 2026-09-24 and earlier)

These records describe the first PoC packs (body v2, head v1). They are kept as history, not as evidence for the current v3/v2 look:

- [Body pack and prompt](../../tools/character-lab/assets/native-wayfarer-v2/README.md): Wayfarer clothing identity on native body poses; earlier teal-only repaint remains preserved.
- [Head pack and prompt](../../tools/character-lab/assets/native-head-v1/README.md): independent face/hair replacement; original head remains available for comparison.
- [Source template contract](../../tools/character-lab/assets/native-template-v1/README.md) and [equipment contract](../../tools/character-lab/assets/native-equipment-v1/README.md).
- [Body browser record](../../tools/character-lab/assets/native-wayfarer-v2/browser-verification.json) and [head browser record](../../tools/character-lab/assets/native-head-v1/browser-verification.json): saved observations, not live guarantees.

The user described the native-template clothing result as “way better” and said it fixed inconsistency with the first design. That is useful positive direction for this PoC. It is not blanket acceptance of every headgear combination or a complete production job. At v0.1.0 the result was a costume/head adaptation using native RO poses and reference equipment. It did not establish a wholly original asset set, full eight-direction animation or gameplay integration. Gameplay loading was added later (B5/B6, above), with the coverage limits listed there.
