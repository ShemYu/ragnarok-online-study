# Ragnarok sprite reference research

Verified on 2026-09-23. This is an offline, local study set, not a cleared art pack for redistribution.

## Public source and provenance

The [roBrowserLegacy demo configuration](https://github.com/MrAntares/roBrowserLegacy/blob/master/applications/browser-examples/demo.html) names `https://grf.robrowser.com/` as its remote asset client. Twenty small SPR/ACT files were obtained directly from that public HTTP endpoint, without a game server, login, account, or access-control bypass. Exact original client paths, download URLs, sizes, and SHA-256 hashes are recorded in [provenance.json](../assets/reference-ro/provenance.json).

Ragnarok Online art remains owned by Gravity and the relevant rightsholders. The license of an open-source client does **not** license Gravity's art. These files have not been established as authorized for redistribution; the current use is a local technical reference. They must not be represented as original project art or an open-source asset pack.

## Downloaded pairs and actual decoded structure

Each basename below has both `.spr` and `.act` in `assets/reference-ro/`. Every SPR is version 2.1 and every image in this set is indexed palette data.

| Basename | Images | ACT version | Directional clips | Purpose |
| --- | ---: | --- | ---: | --- |
| `novice-male-body` | 110 | 2.4 | 104 | Original male Novice body |
| `novice-male-head-1` | 15 | 2.4 | 104 | Original hairstyle 1 head |
| `novice-male-dagger` | 5 | 2.4 | 104 | Novice dagger weapon |
| `novice-male-dagger-trail` | 8 | 2.1 | 104 | Corresponding slash trail |
| `poring` | 49 | 2.5 | 72 | Poring, including combat/death |
| `lunatic` | 56 | 2.5 | 64 | Lunatic, including combat/death |
| `swordsman-male-body` | 118 | 2.4 | 104 | Job-change Swordsman body |
| `swordsman-male-dagger` | 5 | 2.4 | 104 | Swordsman dagger |
| `swordsman-male-dagger-trail` | 8 | 2.3 | 104 | Swordsman dagger trail |
| `swordsman-trainer` | 1 | 2.5 | 8 | Swordsman NPC used as trainer |

Counts above come from decoding the downloaded bytes in Godot 4.5.1, not from filenames alone. Clip counts include the eight views of each action.

## Action and direction interpretation

The [entity action mapping](https://github.com/MrAntares/roBrowserLegacy/blob/master/src/Renderer/Entity/EntityAction.js) identifies these groups:

| Group | Player | Monster |
| ---: | --- | --- |
| 0 | Idle | Idle |
| 1 | Walk | Walk |
| 2 | Sit | Attack |
| 3 | Pick up | Hurt |
| 4 | Combat ready | Death |
| 5 | Attack 1 | Additional species action |
| 6 | Hurt | Additional species action |
| 7 | Freeze | Additional species action |
| 8 | Death | Additional species action |
| 9 | Freeze 2 | — |
| 10 | Attack 2 | — |
| 11 | Attack 3 | — |
| 12 | Skill | — |

Clip index is `group * 8 + view`. The [walk implementation](https://github.com/MrAntares/roBrowserLegacy/blob/master/src/Renderer/Entity/EntityWalk.js) confirms view order: **S, SW, W, NW, N, NE, E, SE**. Select the view relative to the current camera, while keeping movement facing in world coordinates.

For this male Novice, a dagger uses **group 10**, an unarmed attack uses group 5, and a sword uses group 11. This comes from [WeaponAction.js](https://github.com/MrAntares/roBrowserLegacy/blob/master/src/DB/Jobs/WeaponAction.js), combined with the entity action mapping.

## Registration and playback

The [ACT specification](https://ragnarokresearchlab.github.io/file-formats/act/) defines frame layers, transforms, events and attachment anchors. Layer positions are pixel offsets from the actor origin. The first head anchor is aligned to the first body anchor: `head_displacement = body_anchor - head_anchor`. Preserve layer offsets when doing this; centering each frame independently destroys registration.

The [current renderer](https://github.com/MrAntares/roBrowserLegacy/blob/master/src/Renderer/Entity/EntityRender.js) draws the body before the head and weapon. Head uses the anchor displacement. Weapon and trail already use body-relative coordinates and are rendered without the head-style displacement. Synchronize attachments to the body's animation frame. Idle/sit's three Novice frames encode head-direction poses; continuously looping them creates unwanted head turning. Use frame 0 for a neutral idle/sit.

The downloaded body has 8 walk frames (72 ms each using Research Lab's tick conversion), and 9 dagger attack frames (96 ms each). These stored timings are a reference: gameplay attack speed and movement cadence can override them. The parser uses 24 ms per ACT tick as documented by Research Lab. roBrowser's current loader uses 25 ms; this discrepancy is recorded rather than silently treating them as identical.

## Native decoder contract

[`scripts/ro_sprite_data.gd`](../scripts/ro_sprite_data.gd) independently implements SPR decoding and ACT parsing from the documented binary structure. `load_pair(base_path)` returns textures, indexed image count, actions, events, and version metadata. `actions[*].frames[*].layers[*].index` is **already normalized** into the combined texture array; do not add `indexed_count` again. An index of `-1` means an empty layer. Rotation is radians, delay is seconds, and Y remains positive downward. Indexed palette entry 0 is transparent.

Supported parser layouts are SPR 2.0/2.1 and ACT 2.0–2.5; actual fixtures cover SPR 2.1 and ACT 2.1/2.3/2.4/2.5. Invalid signatures, unsupported versions, out-of-bounds reads, invalid transforms/counts, malformed RLE, and missing image references return an empty dictionary with an error. All ten downloaded pairs passed native headless decoding. This establishes file readability and structural alignment, not final visual or gameplay approval.

Further primary format reference: [SPR specification](https://ragnarokresearchlab.github.io/file-formats/spr/).

## In-engine actor verification

`tests/ro_sprite_test.gd` checks directional selection under three camera orientations, the known body/head attachment offset, the nine-frame dagger cycle in eight views, head-direction idle behavior, attack-duration synchronization, return to ready stance, unarmed action selection, job reconfiguration, and fixed foot registration. Run it with Godot `--headless --path . --script res://tests/ro_sprite_test.gd`; add `-- --visual` in a rendered Godot invocation to capture the floor preview.

The actor uses one fixed neutral-foot offset per sprite kind (Novice 11 px, Swordsman 12 px, trainer 13 px, Poring 6 px, Lunatic 9 px). This lifts the entire registered sprite to ground level; it never recenters individual animation frames. At 0.022 world units per pixel the standing Novice is about 2.00 world units tall. Shared decoded files, source images and composed frames are cached. The common untransformed layer uses Godot's native image blitter.

[Eight-direction Novice contact sheet](v2/novice-actions-eight-directions.png): columns S, SW, W, NW, N, NE, E, SE; rows idle, walk, ready, dagger attack, sit, death. [Native floor preview](v2/native-floor-registration.png) shows Novice, Swordsman, trainer, Poring and Lunatic in one actual Godot scene with floor depth testing. These images were inspected for head registration, whole feet, source artwork and major clipping. They are technical visual checks, not a claim of user art approval.
