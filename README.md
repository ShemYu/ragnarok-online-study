# Ragnarok Online Study — Renewal solo milestone

The current goal is a personally playable, Mac-local **Modern / Renewal RO** build with the agreed episode's maps, monsters and story, Traditional Chinese game UI/text, persistent progress and a verified solo play path. The proposed foundation is an existing RO emulator/client stack; exact episode coverage and Chinese compatibility are still unverified.

**Start at [current status](docs/project/STATUS.md).** Stateless agents should read [AGENTS.md](AGENTS.md), then the assigned task and evidence. This pass changes documentation only; the new runtime has not been installed or tested.

| Planning document | Purpose |
| --- | --- |
| [Goal and feasibility](docs/project/GOAL.md) | Decisions, known facts, uncertainties, candidate sources and initial estimates |
| [Supervisory phases](docs/project/PHASES.md) | Coordinator verification and end-user acceptance at each gate |
| [Task board](docs/project/TASKS.md) | Dependencies, task deliverables, status and verification contracts |
| [Workflow and Git control](docs/project/WORKFLOW.md) | Paired Claude/Grok comparison, stateless handoff, branches and rollback |
| [Roadmap](ROADMAP.md) | Active direction and deferred historical work |

## Historical Godot and Character Lab study

The source below preserves the earlier work reverse-engineering RO file formats, rendering and animation to learn game development. It includes a Godot field prototype and a browser Character Lab. These are historical research, separate from the new Renewal integration candidate and its future verification.

**This public repository contains source code, tests and research notes.** Native RO files, reference images, generated artwork/video, visual fixtures and full local snapshots are excluded. A fresh clone can run the source-only checks below; the game and visual demos require separately supplied local assets. Your existing local asset folders continue to work. See [public repository scope and local asset setup](docs/PUBLIC_REPOSITORY.md).

The historical [v0.1.0 findings](docs/character-lab/native-art-poc-v0.1.0.md) and [artwork workflow](docs/character-lab/WORKFLOW.md) preserve one native attack with replacement body/clothing and head. They do not establish the new milestone's content or localization.

## Source-only checks

With Node.js 22+ and Python 3.9+:

```sh
python3 tools/check_public_tree.py
node --test tools/character-lab/tests/modular-motion.test.mjs tools/character-lab/tests/modular-engine.test.mjs
```

The public CI runs these checks. The native fixture tests, browser comparisons and visual performance measurements documented in the milestone require the local asset pack and are not reproduced by CI.

## Historical local game prototype

A standalone **Godot 4 + GDScript** learning project. The game simulation, rendering and saves run in one desktop app. Playing requires no game server, account, database service or internet connection.

Godot was chosen for this prototype's 3D scenery, camera-facing 2D sprites, editable scene system and native local executable. Its runtime is pinned to **Godot 4.5.1**. This version choice concerns the historical prototype, not the proposed Renewal app.

## Play with local assets

Restore your own local study assets first, as described in [local asset setup](docs/PUBLIC_REPOSITORY.md#local-assets). `Setup.command` installs the engine only; it does not download RO files or Character Lab artwork.

On this Mac, double-click **Play.command**. Double-click **Edit.command** to open the project in Godot's editor; **F5** runs it.

On another Mac, run **Setup.command** once online, or install Godot 4.5+ and open `project.godot`. Setup downloads the official 4.5.1 release and verifies SHA-512. Windows and Linux have not been tested.

| Input | Action |
| --- | --- |
| Click ground | Walk through the navigation grid; cancel the current attack |
| Click a monster | Approach and continuously attack |
| Right-drag | Rotate camera |
| Shift + right-drag | Tilt camera |
| Wheel / Ctrl + right-drag | Zoom |
| 1 / F1 | Red Potion: heal 45–65 HP |
| 2 / Insert | Sit or stand; sitting increases HP/SP recovery |
| 3 / F2 | First Aid: heal 5 HP for 3 SP |
| 4 / F3 | Queue Bash on the selected target, after learning it as Swordsman |
| E | Gather nearby loot; drops can also be clicked |
| I / Alt+E / Ctrl+E | Inventory and weapon equipment |
| C | Stats and skills |
| T / Talk to Guide | Approach the training instructor |
| Esc | Close windows, then cancel the current command |

Speak to the instructor to begin a **3 Poring / 2 Lunatic** exercise. Claiming its accelerated training reward reaches Novice Job 10. Speak again to become a Swordsman, then earn a job level and spend a skill point on Bash in Status. The reward and short quest are conveniences for this local study, not a reproduction of RO's original novice tutorial.

Potions are limited; sitting and First Aid provide recovery. The instructor can heal and supply at least three potions. Monsters retaliate after being attacked, lose interest when pulled too far, return home and respawn after defeat. Death returns the player to camp after four seconds.

## What changed in revision 3

The active field now loads a **native crop of Prontera South Field (`prt_fild08`)**: original ground geometry, texture UVs, baked shading, stone gate, walls, trees and benches placed from the source map. Its 49 × 49 navigation area retains the original GAT blocked cells. Characters follow the terrain height, ground clicks account for elevation, and the minimap shows the native area.

The player and monsters are approximately **42% larger relative to the map** than in revision 2: sprite scale increased from 0.022 to 0.03125 world units per pixel. The standing Novice measures about 139 screen pixels in the default preview; zoom and camera position change that measurement.

The existing eight-direction sprites, timed combat, EXP, stats, equipment, First Aid, Bash, training quest and job change remain. The instructor and monster placement are local training content inside the authentic map crop. Battle formulas are simplified, and this is not a complete RO client. Audio, full job trees, shops, the complete field and multiplayer are not implemented.

See [map revision details and before/after images](docs/MAP_V3.md). This revision is ready for visual review; technical checks do not establish the user's approval of its appearance.

## Character Lab

Double-click **Character Lab.command**, then open the printed local browser address. The current [native-action PoC](http://127.0.0.1:8767/native.html) applies Wayfarer clothing and a separate head to one original RO attack, with independent headgear and weapon layers. Earlier appearance, sprite-sheet, video and cutout experiments remain available. This is a separate Character Lab study; the replacement designs are not integrated as game jobs. [Usage and artwork notes](tools/character-lab/README.md) · [v0.1.0 findings, workflow and snapshot](docs/character-lab/README.md).

## Saves

Character, stats, equipment, inventory, skills, quest and kill count save automatically to `user://progress-v2.json` under Godot's application data directory. Each launch starts at camp with full HP/SP; monster positions and uncollected drops reset. The earlier `progress.json` save is preserved but not imported into the new rules.

## Learn the implementation

| File | Responsibility |
| --- | --- |
| `scenes/main.tscn` | Root game scene |
| `scripts/main.gd` | Commands, timed combat, AI, quest, interaction and persistence |
| `scripts/rpg_rules.gd` | Stats, damage, EXP, items and class/skill rules |
| `scripts/ro_sprite_data.gd` | SPR image decoding and ACT animation parsing |
| `scripts/ro_sprite_actor.gd` | Head/body/equipment composition and camera-relative animation |
| `scripts/field_world_ro.gd` | Active native field crop, elevation, blocked cells and navigation |
| `scripts/ro_map_data.gd` | GND/GAT parsing, textured terrain and baked shading |
| `scripts/ro_model_data.gd` | Native RSM model parsing and rendering |
| `scripts/field_world.gd` | Preserved revision 2 procedural field |
| `scripts/game_hud.gd` | Status, inventory, skills, map and dialogue |
| `assets/reference-ro/map-study/` | Native field files, prop models, 49 textures and provenance |
| `assets/environment/*.gdshader` | Preserved revision 2 procedural materials |

A useful first experiment is changing `walk_speed` in `rpg_rules.gd`, then comparing walking cadence. Next, tune `ATTACK_RANGE` in `main.gd`, observe the pending-hit timer in `_start_attack()`, or change a monster definition. Gameplay timing can retime an ACT clip without altering its head/body/weapon registration.

## Checks with the local study pack

```sh
.tools/Godot.app/Contents/MacOS/Godot --headless --path . --editor --quit
.tools/Godot.app/Contents/MacOS/Godot --headless --path . --script res://tests/rpg_rules_test.gd
.tools/Godot.app/Contents/MacOS/Godot --headless --path . --script res://tests/ro_sprite_test.gd
.tools/Godot.app/Contents/MacOS/Godot --headless --path . --script res://tests/ro_map_data_test.gd
.tools/Godot.app/Contents/MacOS/Godot --headless --path . --script res://tests/ro_model_data_test.gd
.tools/Godot.app/Contents/MacOS/Godot --headless --path . --script res://tests/map_integration_test.gd
.tools/Godot.app/Contents/MacOS/Godot --headless --path . -- --qa
.tools/Godot.app/Contents/MacOS/Godot --path . -- --qa-playthrough
.tools/Godot.app/Contents/MacOS/Godot --headless --path . --script res://tests/progression_playthrough.gd -- --qa-progression
```

Integration QA uses a separate temporary save. See [current validation evidence](docs/QA_V3.md), [revision 2 validation history](docs/QA.md), [study notes](docs/STUDY.md), [sprite provenance and format research](docs/RO_ASSET_RESEARCH.md), [native map notes](docs/MAP_V3.md) and [previous environment notes](docs/ENVIRONMENT_V2.md). The V1 baseline is preserved in `docs/baseline-v1/`; its procedural actor and test remain historical references and are no longer used by the game.

## Sources and attribution

[Godot Engine](https://godotengine.org/) is under the [MIT license](https://godotengine.org/license/). Ragnarok Online reference sprites and map assets belong to Gravity and the relevant rightsholders. Their public source paths and SHA-256 hashes are recorded in `assets/reference-ro/provenance.json` and `assets/reference-ro/map-study/provenance.json`. They are local study references, not original or open-source project art. The earlier procedural field remains preserved as revision 2. This project is unaffiliated with Ragnarok Online's creators and publishers.

The revision 3 field preview is retained locally at `docs/v3/field-preview.png`; screenshots and media are not part of the public repository.
