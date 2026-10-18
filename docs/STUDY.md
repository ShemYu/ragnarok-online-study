# Study notes

> Historical Godot reconstruction notes. The active Modern / Renewal solo milestone uses the separate [project goal](project/GOAL.md), [status](project/STATUS.md) and [phase plan](project/PHASES.md). Results below do not establish the new candidate runtime's behaviour.

## Engine and reconstruction approach

**Godot 4 + GDScript** provides the scene graph, local game loop, GUI, navigation, 3D scenery and sprite billboards used here. The runtime is pinned to 4.5.1 for reproducibility. It is a new local implementation, not the original Ragnarok engine. No RO server process is part of this project.

Revision 3 combines actual SPR/ACT reference files with a native crop of Prontera South Field (`prt_fild08`). The decoders follow published binary layouts and primary loader implementations; game commands, rendering integration and local simulation are written in GDScript. We have not recovered Gravity's proprietary game source or established exact reproduction of its battle formulas.

The current target is classic PC Ragnarok presentation with a small pre-renewal-inspired rules model. The selected map is `prt_fild08`; GND/GAT terrain, baked shading, textures and RSM props come from the recorded reference files. The instructor and monster population are local training content. No exact client-era or complete-client match is claimed.

## How one click becomes an attack

1. Godot delivers the input to visible interface controls first. Unhandled clicks reach `main.gd`.
2. A monster click selects its stable index; navigation approaches its current position.
3. At melee distance, the simulation starts an attack clip and a pending strike with a hit deadline and target generation.
4. At the deadline, the target must still be selected, alive, from the same spawn generation and within reach. Moving away cancels the pending strike.
5. `rpg_rules.gd` resolves accuracy, critical chance and damage. The target reacts, retaliates, or enters death/reward/respawn states.
6. `ro_sprite_actor.gd` presents the current state. Camera position selects one of eight views; head anchors and weapon frames follow the body frame.
7. The HUD reads the resulting character, target and quest state. Saves contain progress, not render nodes or transient attack state.

The hit deadline is independent of screen refresh rate. A killing blow still finishes its visible follow-through. Equipment changes both the attack calculation and the native armed/unarmed animation group.

## Primary references

| Source | Used for | Boundary |
| --- | --- | --- |
| [Godot features](https://godotengine.org/features/) and [4.5.1 release](https://github.com/godotengine/godot-builds/releases/tag/4.5.1-stable) | Engine/tooling and verified runtime | This is the chosen version, not a latest-version claim |
| [SpriteBase3D](https://docs.godotengine.org/en/4.5/classes/class_spritebase3d.html) and [AStarGrid2D](https://docs.godotengine.org/en/4.5/classes/class_astargrid2d.html) | Billboard rendering and grid navigation | The active navigation grid follows the source map's GAT cells |
| [Ragnarok Research Lab: ACT](https://ragnarokresearchlab.github.io/file-formats/act/) and [SPR](https://ragnarokresearchlab.github.io/file-formats/spr/) | Native images, frame layers, transforms and anchors | Actual local fixtures cover a subset of format versions |
| [roBrowser Ground, World and Model loaders](https://github.com/MrAntares/roBrowserLegacy/tree/master/src/Loaders) | Native GND/GAT/RSM layouts, scene placement and texture registration | The playable field is cropped; client effects and original NPC/spawn population are incomplete |
| [Research Lab: animation systems](https://ragnarokresearchlab.github.io/rendering/animation-systems/) | ACT timing interpretation | 24 ms ticks; roBrowser uses 25 ms, documented separately |
| [Research Lab: camera](https://ragnarokresearchlab.github.io/rendering/camera-controls/) | Narrow perspective and constrained orbital controls | Its 15-degree FOV is a reported research value, not a verified constant across every RO client |
| [roBrowserLegacy](https://github.com/MrAntares/roBrowserLegacy) | Public source paths, action/direction mapping and attachment behavior | Client source license does not license reference artwork |
| [rAthena status implementation](https://github.com/rathena/rathena/blob/master/src/map/status.cpp) | Pre-renewal stat relationships | HP/SP curves, critical damage and final damage model remain simplified |
| [rAthena monster database](https://github.com/rathena/rathena/blob/master/db/pre-re/mob_db.yml) | Poring/Lunatic HP, attack, EXP, delay and common drop identities | Local drop chances, leash, AI and respawn behavior are selected for this study |
| [rAthena EXP](https://github.com/rathena/rathena/blob/master/db/pre-re/job_exp.yml) and [skills](https://github.com/rathena/rathena/blob/master/db/pre-re/skill_db.yml) | Early progression, class skill identity and SP costs | Later progression and the accelerated instructor quest are not an exact RO tutorial |
| [Official camera controls](https://renewal.playragnarok.com/gameguide/howtoplay_interface05.aspx), [movement](https://renewal.playragnarok.com/gameguide/howtoplay_gameplay01.aspx), [attacks](https://renewal.playragnarok.com/gameguide/howtoplay_gameplay02.aspx), [shortcuts](https://renewal.playragnarok.com/gameguide/howtoplay_interface03.aspx) | Interaction reference | Continuous attacks use one click here; extra laptop-friendly shortcuts are provided |

Exact asset URLs, downloaded bytes and hashes are recorded in [sprite provenance](../assets/reference-ro/provenance.json) and [map provenance](../assets/reference-ro/map-study/provenance.json). [Sprite research](RO_ASSET_RESEARCH.md) and [map research](MAP_V3_RESEARCH.md) record format evidence. [Revision 3 map notes](MAP_V3.md) describe the current crop and scale; the previous procedural field remains in `scripts/field_world.gd`.

## Further fidelity work

- Compare the native `prt_fild08` crop with a chosen client-era recording to refine camera framing, foliage, lighting and sprite scale. Terrain elevation, texture UVs, source prop placement and blocked walk cells are already integrated.
- Compare a recorded walking/combat sequence at the same camera size to tune step cadence, attack impact and hit reaction.
- Add audio, further items/jobs and more complete stats only with a concrete reference and a playable reason.
- Move authored field content and NPC definitions into editor-friendly scenes/data once the reference slice stabilizes.

The working animation, commands, rules and UI are separate modules so these improvements can be evaluated without replacing the whole engine. Automated correctness checks and rendered captures do not establish user approval of appearance or combat feel.
