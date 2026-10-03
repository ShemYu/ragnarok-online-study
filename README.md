# Ragnarok Online Study

Reverse-engineering Ragnarok Online's file formats, rendering and animation to learn game development and build a local, offline game. The current work includes a Godot field prototype and a browser Character Lab for applying replacement artwork to native actions.

**This public repository contains source code, tests and research notes.** Native RO files, reference images, generated artwork/video, visual fixtures and full local snapshots are excluded. A fresh clone can run the source-only checks below; the game and visual demos require separately supplied local assets. Your existing local asset folders continue to work. See [public repository scope and local asset setup](docs/PUBLIC_REPOSITORY.md).

Start with the [v0.1.0 findings](docs/character-lab/native-art-poc-v0.1.0.md), [repeatable artwork workflow](docs/character-lab/WORKFLOW.md) and [next milestones](ROADMAP.md). The [2026-10-02 completion milestone](docs/character-lab/COMPLETION-2026-10-02.md) now verifies Wayfarer idle, walk, ready and dagger attack in eight directions through the game actor: 67 body drawings and five head views, with separate native cap/hat modules. A second character, Lantern Scholar, proves the same import workflow with six body drawings and one head. The new looks are installed locally, and [final acceptance and the frame viewer](docs/character-lab/COMPLETION-QA-2026-10-02.md) are ready. Other actions retain native artwork; user artwork approval remains separate.

## Source-only checks

With Node.js 22+ and Python 3.9+:

```sh
python3 tools/check_public_tree.py
node --test tools/character-lab/tests/modular-motion.test.mjs tools/character-lab/tests/modular-engine.test.mjs tools/character-lab/tests/native-core-synthetic.test.mjs
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tools/character-lab/tests -p 'test_*.py'
```

The public CI runs these checks, including 11 synthetic native composition tests without RO assets. The native fixture tests, browser comparisons and visual performance measurements documented in the milestone require the local asset pack and are not reproduced by CI.

## Local game prototype

A standalone **Godot 4 + GDScript** learning project. The game simulation, rendering and saves run in one desktop app. Playing requires no game server, account, database service or internet connection.

Godot is the chosen engine because this project needs 3D scenery, camera-facing 2D sprites, an editable scene system and a native local executable together. The bundled runtime is pinned to **Godot 4.5.1**, rather than tracking engine updates during the study.

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
| O | Cycle outfit: native RO art / Wayfarer looks / Lantern Scholar proof (only looks whose local Character Lab packs are installed) |
| H | Cycle headgear: none / Cap / Hat (native reference headgear) |
| Esc | Close windows, then cancel the current command |

Speak to the instructor to begin a **3 Poring / 2 Lunatic** exercise. Claiming its accelerated training reward reaches Novice Job 10. Speak again to become a Swordsman, then earn a job level and spend a skill point on Bash in Status. The reward and short quest are conveniences for this local study, not a reproduction of RO's original novice tutorial.

Potions are limited; sitting and First Aid provide recovery. The instructor can heal and supply at least three potions. Monsters retaliate after being attacked, lose interest when pulled too far, return home and respawn after defeat. Death returns the player to camp after four seconds.

## What changed in revision 3

The active field now loads a **native crop of Prontera South Field (`prt_fild08`)**: original ground geometry, texture UVs, baked shading, stone gate, walls, trees and benches placed from the source map. Its 49 × 49 navigation area retains the original GAT blocked cells. Characters follow the terrain height, ground clicks account for elevation, and the minimap shows the native area.

The player and monsters are approximately **42% larger relative to the map** than in revision 2: sprite scale increased from 0.022 to 0.03125 world units per pixel. The standing Novice measures about 139 screen pixels in the default preview; zoom and camera position change that measurement.

The existing eight-direction sprites, timed combat, EXP, stats, equipment, First Aid, Bash, training quest and job change remain. The instructor and monster placement are local training content inside the authentic map crop. Battle formulas are simplified, and this is not a complete RO client. Audio, full job trees, shops, the complete field and multiplayer are not implemented.

See [map revision details and before/after images](docs/MAP_V3.md). This revision is ready for visual review; technical checks do not establish the user's approval of its appearance.

## Character Lab

Double-click **Character Lab.command**, then open the printed local browser address. The saved [native-action PoC](http://127.0.0.1:8767/native.html) applies Wayfarer clothing and a separate head to one original RO attack, with independent headgear and weapon layers. Earlier appearance, sprite-sheet, video and cutout experiments remain available. The newer [completion milestone](docs/character-lab/COMPLETION-2026-10-02.md) uses the same native construction for the four-state Wayfarer slice and a smaller Scholar proof, verified in isolated Godot actor fixtures. Candidate appearances load on the existing Swordsman once their verified packs are installed; they do not add game classes. [Usage and artwork notes](tools/character-lab/README.md) · [v0.1.0 findings, workflow and snapshot](docs/character-lab/README.md).

## Saves

Character, stats, equipment, inventory, skills, quest and kill count save automatically to `user://progress-v2.json` under Godot's application data directory. Each launch starts at camp with full HP/SP; monster positions and uncollected drops reset. The earlier `progress.json` save is preserved but not imported into the new rules.

## Learn the implementation

| File | Responsibility |
| --- | --- |
| `scenes/main.tscn` | Root game scene |
| `scripts/main.gd` | Commands, timed combat, AI, quest, interaction and persistence |
| `scripts/rpg_rules.gd` | Stats, damage, EXP, items and class/skill rules |
| `scripts/ro_sprite_data.gd` | SPR image decoding and ACT animation parsing |
| `scripts/ro_sprite_actor.gd` | Head/body/headgear/equipment composition, replacement-art appearances and camera-relative animation |
| `tools/character-lab/appearances/*.json` | Replacement-art looks: which art pack replaces which part's SPR drawings |
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
.tools/Godot.app/Contents/MacOS/Godot --path . -- --qa-playthrough --evidence-dir=<new absolute folder>
.tools/Godot.app/Contents/MacOS/Godot --headless --path . --script res://tests/progression_playthrough.gd -- --qa-progression --evidence-dir=<new absolute folder>
```

The two playthroughs write their screenshots and reports to `--evidence-dir`. The saved `docs/v3` evidence is only rewritten with `--update-saved-evidence`. In a sandbox that cannot write Godot's user data folder, add `--log-file <absolute path>` after the Godot executable on every command.

Integration QA uses a separate temporary save. See [current validation evidence](docs/QA_V3.md), [revision 2 validation history](docs/QA.md), [study notes](docs/STUDY.md), [sprite provenance and format research](docs/RO_ASSET_RESEARCH.md), [native map notes](docs/MAP_V3.md) and [previous environment notes](docs/ENVIRONMENT_V2.md). The V1 baseline is preserved in `docs/baseline-v1/`; its procedural actor and test remain historical references and are no longer used by the game.

## Sources and attribution

[Godot Engine](https://godotengine.org/) is under the [MIT license](https://godotengine.org/license/). Ragnarok Online reference sprites and map assets belong to Gravity and the relevant rightsholders. Their public source paths and SHA-256 hashes are recorded in `assets/reference-ro/provenance.json` and `assets/reference-ro/map-study/provenance.json`. They are local study references, not original or open-source project art. The earlier procedural field remains preserved as revision 2. This project is unaffiliated with Ragnarok Online's creators and publishers.

The revision 3 field preview is retained locally at `docs/v3/field-preview.png`; screenshots and media are not part of the public repository.
