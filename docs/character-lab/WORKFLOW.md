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

## Reproduce the existing candidate

For review and version preservation, use the implemented snapshot entry point first:

```sh
python3 tools/character-lab/pipeline.py verify
python3 tools/character-lab/pipeline.py snapshot
python3 tools/character-lab/pipeline.py verify-snapshot docs/character-lab/releases/native-art-poc-v0.1.0/manifest.json
```

The default configuration is `tools/character-lab/pipeline/native-art-poc-v0.1.0.json`. `verify` checks source/manifest hashes and runs the 18 native Node tests; it does not regenerate artwork or Godot exports. `snapshot` writes an immutable local artifact archive and inventory below `docs/character-lab/releases/native-art-poc-v0.1.0/` and refuses to overwrite that release. The pack preserves the Character Lab (including earlier experiments), selected native ACT/SPR sources, the local Godot source decoder/actor and project file, and this study's documentation. This is an artifact version, independent of whether the repository has a Git commit or tag.

The pipeline configuration is a working verification/packaging contract. It is separate from the proposed generic artwork recipe below; it does not automate the ImageGen step or remove the hardcoded importer assumptions.

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

## Proposed recipe shape

The following is a **design sketch, not an implemented API**. Existing JSON manifests remain the current contract. Paths are shown relative to `tools/character-lab/`; hash placeholders must be replaced from actual files. A future loader should reject missing or incompatible slot dimensions and source hashes rather than silently aligning images.

```json
{
  "schemaVersion": 1,
  "recipeId": "wayfarer-native-attack-east",
  "recipeVersion": "1.0.0",
  "source": {
    "template": "assets/native-template-v1/template.json",
    "sha256": "<exact template bytes>",
    "actionVersion": "swordsman-male-dagger-86-direction-6-v1",
    "action": "attack",
    "sourceAction": 86,
    "sourceDirection": 6
  },
  "modules": {
    "body": {
      "manifest": "assets/native-wayfarer-v2/costume.json",
      "artVersion": "native-wayfarer-v2",
      "sha256": "<manifest bytes>",
      "requiredSlots": [82, 83, 84, 85, 86]
    },
    "head": {
      "manifest": "assets/native-head-v1/head.json",
      "artVersion": "native-head-v1",
      "sha256": "<manifest bytes>",
      "requiredSlots": [1]
    },
    "headgear": {
      "manifest": "assets/native-equipment-v1/equipment.json",
      "sha256": "<manifest bytes>",
      "selected": "none",
      "reviewVariants": ["none", "cap", "hat"]
    },
    "weapon": {"from": "source.parts.weapon", "visible": true},
    "trail": {"from": "source.parts.trail", "visible": true}
  },
  "invariants": {
    "sourceActionUnchanged": true,
    "sourceSlotDimensionsUnchanged": true,
    "individualRecentering": false,
    "frameInterpolation": false
  },
  "review": {
    "technicalEvidence": "<saved verification record>",
    "visualEvidence": "<dated review record>",
    "scope": "one attack, one direction"
  }
}
```

Generation and import settings should remain separately referenced, not mixed into playback timing. An import adapter needs `generatedImage`, `generatedImageSha256`, `slotLayout`, `slotLayoutSha256`, `normalizeCanvas`, `sampling`, `backgroundKey` and `outputPart`; its output is the part's indexed texture map plus diagnostics. These are proposed field names, not options currently accepted by the scripts.

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

## Current evidence and review scope

- [Body pack and prompt](../../tools/character-lab/assets/native-wayfarer-v2/README.md): Wayfarer clothing identity on native body poses; earlier teal-only repaint remains preserved.
- [Head pack and prompt](../../tools/character-lab/assets/native-head-v1/README.md): independent face/hair replacement; original head remains available for comparison.
- [Source template contract](../../tools/character-lab/assets/native-template-v1/README.md) and [equipment contract](../../tools/character-lab/assets/native-equipment-v1/README.md).
- [Body browser record](../../tools/character-lab/assets/native-wayfarer-v2/browser-verification.json) and [head browser record](../../tools/character-lab/assets/native-head-v1/browser-verification.json): saved observations, not live guarantees.

The user described the native-template clothing result as “way better” and said it fixed inconsistency with the first design. That is useful positive direction for this PoC. It is not blanket acceptance of every headgear combination or a complete production job. The result remains a costume/head adaptation using native RO poses and reference equipment; it does not establish a wholly original asset set, full eight-direction animation, or integration into gameplay.
