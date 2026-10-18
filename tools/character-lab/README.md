# Character Lab

> Historical/deferred artwork tooling. Read the [current Renewal milestone status](../../docs/project/STATUS.md) before resuming this work; the Character Lab is not the active runtime or proof of its Chinese/content coverage.

**Public checkout:** the visual studies require the separately retained local asset pack. Source-only tests run without it; the native verification command below requires it. Asset links in this document refer to local files. See [setup and repository scope](../../docs/PUBLIC_REPOSITORY.md).

**Saved milestone: [native-art-poc v0.1.0](../../docs/character-lab/README.md).** The review, reusable workflow and restorable snapshot preserve the successful native-action artwork approach. Verify it with `python3 tools/character-lab/pipeline.py verify` from the repository root.

## Original RO action with replacement artwork

The **Head & hair** selector now independently switches between a new chestnut-haired Wayfarer head and the original RO reference. It retains the original 30×26 head slot and native ACT attachment; Cap/Hat remain separate modules. [Head artwork, prompt and import records](assets/native-head-v1/README.md) document the addition. The clothing accepted in the previous study is retained.

The current default is the **Wayfarer costume on native RO modules**: the earlier teal vest, ivory shirt and leather equipment design follows the original body poses. Separate native Cap/Hat and dagger controls demonstrate equipment attachment. A 1/32/128-character scene measures fresh composition and cached playback. [Assets, exact ImageGen prompt, modular scope and performance method](assets/native-wayfarer-v2/README.md) document this version. The previous teal repaint remains selectable.

Open **[native.html](http://127.0.0.1:8767/native.html)** for the current study. It replaces the five complete body drawings referenced by original Swordsman dagger action 86, while retaining all nine source frames, 96 ms holds, layer offsets, mirroring and attachment anchors. Native and costume views share one playhead. The browser checks original, both costume variants, and native equipment output against 72 Godot-composed reference frames pixel for pixel, including the new head with both hats. The original head, weapon and trail remain reference assets. This is a costume repaint on native pose templates, not a newly invented rig or motion.

The earlier cutout experiment had exaggerated separate shoulders and elbow joins; it proved equipment controls but did not match native RO construction. ACT selects complete SPR drawings, so a new job needs replacements for the used image slots. [Template export, replacement import, source records and asset prompts](assets/native-template-v1/README.md) document this approach. Run `node --test tools/character-lab/tests/native-template.test.mjs` for focused native-template checks.

## Modular attack workshop

Open **[modular.html](http://127.0.0.1:8767/modular.html)** for the new controlled attack PoC. It renders original body/head/headgear/weapon parts on one authored timeline, with six key poses, two swords, two headgear choices, full-body versus arm-only comparison, adjustable timing, a training dummy, layer/anchor inspection, per-pose attachment edits, and JSON settings export/import. Effects start off. The earlier V3 video remains available unchanged in the comparison panel.

The new approach combines three torso drawings with joint-driven limbs, rather than using generated video frames. It proves a reusable one-direction equipment/animation structure, not finished RO-quality animation or Godot gameplay integration. [Asset prompts, provenance, scope and validation](assets/modular-v1/README.md) are saved with the new parts kit. Run `node --test tools/character-lab/tests/modular-*.test.mjs` for focused checks.

## Grok video experiment

The latest **V3** test focuses on action choreography while preserving V2's exact source art. Its shorter screen-space prompt produces a more readable overhead sword cut, but the strike is late and a white slash mark appears. Open **video.html** to compare V3, the rejected V2 motion, and original RO frames. [Motion prompt and criteria](assets/video-tests/attack-choreography-v3/README.md) document the target; [run records](assets/video-tests/README.md) preserve the actual result and the recorded terminal-newline difference in Grok's submitted prompt.

The preceding **V2** style study used a newly drawn original Wayfarer pose, official Swordsman/Thief/Archer sprite panels, and an expanded native RO frame study. The user found the art better but still far from RO, and rejected the weird motion. Its untouched **480×480, 24 fps, 25-frame / 1.041667-second** MP4 remains selectable, along with rejected V1. The page also compares original RO frames at their source timing and links the official artwork and viewed trailer. No generated-video sprite extraction or retiming has been applied. See [video-test records](assets/video-tests/README.md) for prompts, provenance and visual findings.

The earlier sprite-sheet experiment remains available for comparison. Its generated pose consistency was not accepted by the user; the new video test is intended to investigate whether temporal consistency improves.

## Attack PoC

Open **attack.html** (or “Try the attack study” from the appearance page) to see the original Wayfarer perform a single sword slash. Play once, loop, pause, step through eight poses, scrub the timeline or choose 0.5×/1×/1.5× playback. An actual native RO Swordsman dagger attack appears alongside it. The reference is normalized to the original's one-second cycle for comparison; its source atlas preserves all nine frames and original 96 ms frame timing.

The earlier sprite-sheet attack on **attack.html** is **not modular**: body, hair, clothes and sword are painted together in each pose. The Godot renderer separately composes native body/head/weapon/trail assets. The new **modular.html** workshop now demonstrates separate original parts, while this older sheet remains preserved as a visual motion experiment.

Original source: [wayfarer-attack-v1.png](assets/attack/wayfarer-attack-v1.png), generated with built-in image_gen and stored unchanged. [Prompts](assets/attack/generation-prompts.json), [provenance](assets/attack/provenance.json), and [frame/timing manifest](assets/attack/manifest.json) record the asset and processing. Browser alpha threshold96 removes faint extraction noise. Manually marked rear-boot contact points register the eight generated poses; a single scale is used throughout, without automatic bounding-box centering. Each pose can be exported as a 192×192 PNG or a JSON recipe. Registration does not fix generated changes in anatomy, costume, perspective or foot spacing; those still need visual review.

The [reference descriptor](assets/attack/reference.json) preserves native ACT frame events, anchors and source hashes. Reproduce it with `tools/character-lab/export_attack_reference.gd` using the local Godot executable. The reference ends in its source follow-through pose; no synthetic recovery frames were added.

## Appearance PoC

Double-click **Character Lab.command** in the project root, then open the printed browser address. Keep its Terminal window open; **Control-C** stops it. Python 3 is required. The server listens only on `127.0.0.1:8767` and reuses an existing Character Lab at that port.

Choose **Wayfarer** or **Lantern Scholar**, switch South/West/North/East, and try cloth or hair colors. Compare against the RO Swordsman reference at 1–4× zoom, with field, transparency-grid or plain backgrounds and an optional feet line. **Export sprite PNG** saves the selected view as a transparent **128 × 128** image; **Export recipe JSON** records the selected source frame and preview choices. Choices also persist in this browser's local storage.

This is a **static art-style proof of concept**. It has four views per design, not SPR/ACT animation, a rig, a walking/attack cycle or an integrated game job. Height normalization uses a common scale per design, targeting roughly 94 pixels beside the RO reference; the export's foot anchor is at Y = 112. Fitting that canvas and height does not prove a perfect Ragnarok style match or consistent production animation. Palette changes use color-range masks on the original AI artwork, rather than separately authored hair and clothing layers.

## Artwork and references

The two new designs were created with built-in **image_gen**, without an API key. They are original AI-generated character concepts, not recolors or edits of RO sprites. The active files are **`wayfarer-v1.png`** and **`lantern-scholar-v3.png`**, both with real alpha transparency. Wayfarer V2 was rejected because it baked a checkerboard into the image; V1 remains selected. Lantern Scholar V3 is the refined transparent version. Earlier generations remain as study history.

[Generation prompts](assets/generation-prompts.json) record the design briefs, and [manifest.json](assets/manifest.json) defines the chosen files, four source crops, anchors and palette masks. The comparison Swordsman and field grass are Ragnarok reference artwork, separate from the new designs; see [reference.json](assets/reference.json), [sprite provenance](../../assets/reference-ro/provenance.json) and [map provenance](../../assets/reference-ro/map-study/provenance.json).

The lab runs from local assets and does not call an image-generation API while browsing or exporting. Visual acceptance remains for user review.

## Validation

[Browser verification](qa/verification.json) covers all eight original views, palette changes, reference stability, desktop/narrow-screen zoom, saved selections and PNG/JSON payloads. Export also leaves a visible download link because automatic downloads were not confirmed in the in-app browser. [Asset provenance](assets/provenance.json) records selected files and hashes.

The new designs match the scale and fantasy costume vocabulary, but their frontal posing and rounded faces still differ from the more oblique RO reference. These are candidate designs for comparison, not an accepted production style.
