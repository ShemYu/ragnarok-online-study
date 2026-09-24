# Native-action artwork PoC — v0.1.0

**Public checkout:** this is a report of the local milestone. Linked artwork, fixtures and verification records remain in the local study pack; they are not included in public Git history. See [repository scope](../PUBLIC_REPOSITORY.md) and the published [prompt text](prompts/README.md).

**Saved:** 2026-09-24 · **Status:** local learning milestone · **Review page:** [Character Lab](http://127.0.0.1:8767/native.html)

The useful result is a repeatable way to change character artwork while retaining the original Ragnarok Online action data. The Wayfarer clothing now follows complete native body poses; the head can change independently; native hats and the dagger remain separate. This provides a much closer starting point than our generated animation or cutout rig.

This milestone preserves a working experiment, not a finished original job. The artwork remains close to and derived from the RO pose templates. It is still worth saving: we have separated the art problem from the motion problem and made both reviewable.

## What changed our approach

| Study | What we learned | Decision carried forward |
| --- | --- | --- |
| [Generated attack sheet](../../tools/character-lab/assets/attack/provenance.json) | Eight independently drawn poses varied in anatomy, costume, perspective and foot spacing. Registration could not repair those differences. Body, hair and weapon were baked together. | Preserve the experiment; do not treat a generated sheet as a stable modular animation. |
| [Grok video V1–V3](../../tools/character-lab/assets/video-tests/README.md) | More references improved appearance, and explicit screen-space choreography improved V3's attack. V2 still turned and briefly detached the blade; V3 struck late and added an unrequested white crescent. The user found V3 better but lacking force. | Prompt iteration helped exploration but did not establish exact action timing or independently replaceable equipment. Keep the original clips untouched. |
| [Cutout workshop](../../tools/character-lab/assets/modular-v1/README.md) | Separate parts and authored motion made equipment controllable, but oversized shoulders, visible joins and overlapping clothes diverged from the target construction. | Do not stretch independent arms and shoulders to reproduce this RO body animation. |
| [Native template and first repaint](../../tools/character-lab/assets/native-template-v1/README.md) | Five whole-body drawings, selected by the unchanged ACT sequence, reproduced the native movement without generating motion. | Use native image slots and registration as the contract. |
| [Wayfarer clothing](../../tools/character-lab/assets/native-wayfarer-v2/README.md) and [head candidate](../../tools/character-lab/assets/native-head-v1/README.md) | The earlier teal vest, ivory shirt, belt, pouch and boots fit the native pose family. A separate chestnut-haired head follows the native head action. | Retain the clothing baseline, keep head review separate, and document the process before expanding scope. |

The user's response to the clothing was: “this is way better, and you also fix the cloth non-consistent to our first design.” This records a positive review of the clothing and direction. The newly generated head is technically checked but has not received a separate, explicit visual acceptance. Test results must not be substituted for that review.

## The native contract

RO's **SPR stores drawings**; **ACT selects and places those drawings over time**. ACT supplies image indexes, timing, offsets, mirroring, scaling, rotation, anchors and event references. It is not a skeleton that can animate an arbitrary single character picture. See the [ACT format reference](https://ragnarokresearchlab.github.io/file-formats/act/) and [ActEditor](https://github.com/Tokeiburu/ActEditor).

This PoC supports exactly the following selected template:

| Property | Preserved value |
| --- | --- |
| Character/action | Male Swordsman dagger attack, source action **86**, direction slot **6** (east in this study) |
| Timeline | **9 frames × 96 ms = 864 ms** at source file timing |
| Body sequence | **82, 83, 83, 83, 84, 85, 86, 86, 86** |
| Body artwork required | **5 distinct drawings**, not 9 separately generated images |
| Head artwork required | Slot **1**, **30 × 26** pixels, reused throughout the attack |
| Composition | **192 × 192** canvas; ACT origin **[96, 156]**; preserved per-frame placement |
| Source data | Original ACT records and original SPR files retained; replacements are separate PNG maps |
| Sequence end | Source follow-through held at the end; looping jumps to the first source frame |

Repeated image indexes remain repeated references. They cannot be collapsed into fewer timeline frames: ACT placement and other layers can still differ. No recovery frames, pose interpolation or attack-speed gameplay rules have been added. The exported ready pose is an extra asset; it does not establish a complete ready animation or additional runtime action support.

The [template manifest](../../tools/character-lab/assets/native-template-v1/template.json) is the precise source contract. The [costume manifest](../../tools/character-lab/assets/native-wayfarer-v2/costume.json) and [head manifest](../../tools/character-lab/assets/native-head-v1/head.json) map replacement artwork back to that contract.

## Modules we actually have

| Module | Replaceable unit | Current evidence and boundary |
| --- | --- | --- |
| Body + clothing | Complete body drawing for each used SPR index | Wayfarer outfit or previous repaint can replace the original body while the playhead and ACT stay unchanged. Shirt, trousers, arms and boots are **not** separate dress-up layers. |
| Head + hair | One face/hair bitmap in head slot 1 | Original RO head or Wayfarer head. Face and hair remain one module. |
| Headgear | Its own native SPR/ACT pair | Cap / Hat / None, attached using the body anchor minus accessory anchor. These are original reference assets. |
| Weapon | Separate native dagger SPR/ACT | Dagger / None. Hiding the weapon does not change to RO's unarmed action family. There is no second weapon appearance in this native study. |
| Trail | Separate native trail SPR/ACT | Visibility can be toggled without changing body motion. This remains original reference artwork. |

The selected facing uses body → head → headgear → weapon → trail draw order. Correct ordering for other directions, weapons and accessories is outside this milestone. A hat remaining attached does not guarantee that every new hair silhouette will look good beneath it.

Local visual evidence: `tools/character-lab/assets/native-head-v1/none/attack/contact-3x.png` shows the Wayfarer costume and head candidate across the nine native attack frames.

## Evidence, and what it establishes

The latest saved [head browser verification](../../tools/character-lab/assets/native-head-v1/browser-verification.json) records **18 passing tests** and **72 frames with zero differing pixels** between the browser compositor and the local Godot native-data renderer:

- 27 frames: original body, first repaint and Wayfarer clothing, each with the original head.
- 18 frames: original body/head with native Cap or Hat.
- 27 frames: Wayfarer clothing and new head with None, Cap or Hat.

The tests cover source preservation, frame timing, slot dimensions and hashes, attachments, visibility, and module isolation. Browser review exercised clothing and head swaps on a held frame, native hats, dagger removal, playback and the performance controls. The saved review reports no browser warnings or errors.

These checks establish consistent implementations of the selected local source data. They do **not** establish parity with the official RO client, acceptance of the artwork, all outfit combinations, all directions, or integration into the local game's gameplay.

Registration is measured without forcing the new art back into the old silhouette. Wayfarer body silhouettes overlap the native templates by approximately **0.926–0.962**; the head overlap is **0.8340**. All replacement bitmap dimensions match their source slots, and no visible pixels lie outside the fixed crops. Different overlap is expected when clothing or hair changes; it is a diagnostic, not a quality score.

### Performance observation

The [saved clothing benchmark](../../tools/character-lab/assets/native-wayfarer-v2/browser-verification.json) used Wayfarer clothes, the original head, native Cap and dagger. It predates the new head candidate. Each run repeated one assembled outfit at different animation phases and sampled **120 callbacks**.

| Characters | Fresh nine-pose CPU build | Cached scene CPU median | Cached scene CPU p95 |
| --- | ---: | ---: | ---: |
| 32 | 2.00 ms | 0.10 ms | 0.20 ms |
| 128 | 1.70 ms | 0.10 ms | 0.30 ms |

Nine composed frames are cached for that outfit; this is not a test of 128 unique outfits. The figures measure CPU composition/draw submission in the local browser, excluding completed GPU work, map rendering, AI, collision and gameplay. The roughly 120 animation callbacks per second reflect browser scheduling; the artwork still holds each native frame for 96 ms. Small timing differences between these two runs are measurement variation, not evidence that 128 actors are cheaper than 32.

## Reusable process to preserve

1. **Choose a small native action/facing contract.** Record its source files and hashes, used SPR indexes, dimensions, frame order, timing, transforms, attachments and draw order. Export an untouched reference sequence before changing art.
2. **Build registered artwork templates.** Export each unique raw SPR slot once, before ACT mirroring or transforms. Save fixed crop rectangles and an enlarged nearest-neighbor editing board. Keep a separate image as the costume or character identity reference.
3. **Generate artwork within those slots.** Use the native board as the placement reference and the Wayfarer kit as the design reference. Request costume or head changes, not new motion. Save the exact prompt, unchanged generated result, reference roles and hashes. The successful runs used built-in ImageGen.
4. **Import without hiding alignment problems.** Normalize the entire board once, remove the documented magenta key and crop the recorded rectangles. Do not recenter individual poses, auto-trim them, warp them, resize limbs or force the native alpha mask. Reject or review overflow instead of silently correcting it.
5. **Substitute textures by module and source index.** Reuse the same replacement PNG wherever ACT references that index. Preserve the source actions, timing and attachments; keep native references and replacement art in separate versioned folders.
6. **Produce review fixtures and check invariants.** Export all source frames, compare browser output with the local renderer, verify dimensions and source hashes, and exercise module switches on a paused frame. Confirm that a swap does not change the playhead or other modules.
7. **Review appearance and motion separately.** Inspect the full sequence and contact board, including repeated poses, exposed joints, face identity, headgear overlap and the loop boundary. Record user acceptance independently from technical checks. Measure performance only with an explicit outfit count, cache state and workload.

The existing scripts and asset packs are reproducible building blocks for this process. They are not yet a generic production importer for any job, action or direction. [Character Lab's README](../../tools/character-lab/README.md) links the preparation, import and validation commands; the [body prompt](../../tools/character-lab/assets/native-wayfarer-v2/prompt.txt) and [head prompt](../../tools/character-lab/assets/native-head-v1/prompt.txt) preserve the successful generation requests.

## Limits and next small review

Original native body templates, headgear, dagger and trail remain RO reference material; the costume and head are derivative replacement studies. Source records are preserved in the [RO provenance](../../assets/reference-ro/provenance.json), [equipment provenance](../../tools/character-lab/assets/native-equipment-v1/provenance.json), [clothing provenance](../../tools/character-lab/assets/native-wayfarer-v2/provenance.json) and [head provenance](../../tools/character-lab/assets/native-head-v1/provenance.json). Redistribution permission for the original reference assets has not been established. This local checkpoint is not a claim of fully original or release-ready character art.

The next useful review is the current head, bareheaded and under both hats, with the accepted clothing unchanged. After that, a second native action in the same facing would test whether the process generalizes beyond this attack without immediately multiplying the work across eight directions. A complete job, free combination of separate clothing pieces, additional weapon families and game integration remain future decisions.
