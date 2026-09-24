# Public repository and local study assets

This repository records an independent, offline Ragnarok Online reverse-engineering study. The goal is to understand formats, animation composition and game development through a new local implementation. It is not the original game source, an official client, or a multiplayer server.

## What is versioned publicly

- Godot game code, native format readers, shaders, scenes and tests.
- Browser Character Lab code, export/import scripts and local snapshot tooling.
- Research notes, the v0.1.0 review, workflow design, successful body/head prompt text and the roadmap.
- Source-only CI and a check that rejects local asset packs, media, archives and common machine-local files from the Git index.

The existing provenance records state that redistribution permission for the RO reference assets has not been established. Original files, decoded images, native action manifests, mixed reference/generated artwork packs, screenshots, videos, CLI logs and full snapshots therefore stay local. The new clothing/head studies also remain in that local pack. This initial public checkpoint makes no claim that those studies are cleared original production artwork.

Historical documents describe results observed with the local pack. Links into asset folders, visual evidence directories or `docs/character-lab/releases/` refer to local-only files and will not resolve on GitHub. Public prompt copies are in [character-lab/prompts](character-lab/prompts/README.md).

## Local assets

Existing workspace users do not need to move anything. `.gitignore` excludes the files without deleting them. For a new checkout, copy your locally retained study files into the same relative locations:

| Location | Local contents | Needed for |
| --- | --- | --- |
| `assets/reference-ro/` | ACT/SPR pairs; `map-study/` GND/GAT/RSW/RSM files and textures | Godot native field and actors; sprite/template export |
| `tools/character-lab/assets/` | Native templates, replacement art, equipment packs, manifests and earlier studies | Character Lab pages, native tests and import/verification |
| `tools/character-lab/qa/` and `docs/v2/`, `docs/v3/` | Saved browser/game evidence | Historical visual review |
| `docs/character-lab/releases/` | Full local milestone archives and integrity records | Snapshot restoration |

Exact source basenames and decoded structures are documented in [RO asset research](RO_ASSET_RESEARCH.md). The native snapshot recipe at `tools/character-lab/pipeline/native-art-poc-v0.1.0.json` lists that milestone's required paths. A renamed or different client file may not match the stored fixture hashes. Source artwork and generated art packs are distinct inputs; exporting a native template does not recreate the Wayfarer drawings.

Use your own permitted local source files or the existing local checkpoint. No asset download step or artwork-generation service runs when cloning this repository. `Setup.command` only downloads the pinned Godot engine. The Character Lab snapshot covers the character study, not the field-map game assets.

With the complete local Character Lab pack restored:

```sh
python3 tools/character-lab/pipeline.py verify
python3 -m http.server 8767 --bind 127.0.0.1 --directory tools/character-lab
```

Open `http://127.0.0.1:8767/native.html`. See the root README for game controls and Godot checks.

## Tests without the asset pack

```sh
python3 tools/check_public_tree.py
node --test tools/character-lab/tests/modular-motion.test.mjs tools/character-lab/tests/modular-engine.test.mjs
```

These exercise the earlier authored-motion model, import validation and collision geometry without artwork. They do not establish native animation parity. With Godot 4.5.1 installed, the game rules can also be checked without artwork:

```sh
godot --headless --path . --script res://tests/rpg_rules_test.gd
```

On the original Mac, use `.tools/Godot.app/Contents/MacOS/Godot` in place of `godot`.

## Version boundaries

Git commits version the public source and notes. The Git tag `public-source-v0.1.0` identifies this initial public source checkpoint.

The separate `native-art-poc-v0.1.0` local snapshot freezes source **and** asset bytes, prompts, earlier experiments and visual evidence. It is not uploaded as a GitHub release asset. Keep it unchanged and increment the recipe for the next local milestone. The local packaging command intentionally includes reference material and is not a public-release packager.

Future work should keep source changes, native template identity and replacement-art versions explicit. Before adding a new asset publicly, give it a separate provenance review instead of forcing the existing ignored pack into Git.
