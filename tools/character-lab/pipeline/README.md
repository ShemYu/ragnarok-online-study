# Native-art study verification and versioning

**Local asset pack required.** This tool packages the complete local study, including reference material. It is not a public-release packager; generated snapshots stay ignored by Git. See [repository scope](../../../docs/PUBLIC_REPOSITORY.md).

The packaging recipe `native-art-poc-v0.1.0.json` names source/asset manifests, focused tests, saved browser evidence, version scope and archive contents. It does not drive artwork generation or runtime assembly yet. [The workflow design](../../../docs/character-lab/WORKFLOW.md) identifies the next extraction work.

From the repository root:

```sh
python3 tools/character-lab/pipeline.py verify
python3 tools/character-lab/pipeline.py snapshot
python3 tools/character-lab/pipeline.py verify-snapshot docs/character-lab/releases/native-art-poc-v0.1.0/manifest.json
```

`verify` checks recorded source/asset hashes and runs the 18 native tests. It reports the saved browser-review date; it does not pretend to rerun browser visual or pixel checks. `snapshot` runs verification, creates a ZIP with per-file hashes and dated evidence, checks that ZIP, and saves it under its versioned release directory. It refuses to overwrite an existing version. `verify-snapshot` validates the saved ZIP bytes, member inventory, sizes and every member's hash.

The archive contains all Character Lab browser studies, selected native ACT/SPR source pairs, the two Godot decoder/compositor scripts, `project.godot` for script context, and the character-study notes. It excludes the field-map game, Godot executable, `.import` caches, lock files and earlier release archives. Original reference assets remain local study material. Nothing is uploaded or published.

To reproduce playback, extract the archive and serve its `tools/character-lab` directory with a local HTTP server. Run its own `pipeline.py verify` to check the restored copies. For a new milestone, copy the recipe, increment `version`, select a new `releaseDirectory`, and use `--recipe` with that path. Create new art directories for new candidates and retain the previous source images/prompts.

This version records source and asset bytes independently from the art generation process. Reimporting the saved image is deterministic; asking ImageGen again may produce a different image.
