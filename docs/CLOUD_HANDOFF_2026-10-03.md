# Cloud source handoff — 2026-10-03

The `handoff/cloud-2026-10-03` branch snapshots the current public source, tests,
configuration, recipes and research notes for work on a Linux cloud computer.
Its parent is the locally reviewed source checkpoint
`24b0806265b2f84060f35626d03b1b71f4ecb91b`. The original Mac working branch,
index, uncommitted files, local assets and saves are preserved. This is a source
handoff; Linux execution still needs independent verification on the destination.

The existing destination is
`https://github.com/ShemYu/ragnarok-online-study.git`, a public repository.
Its visibility and access are unchanged. No deployment, merge or asset publication
is part of this handoff.

## Clone and verify source

```sh
git clone --single-branch --branch handoff/cloud-2026-10-03 \
  https://github.com/ShemYu/ragnarok-online-study.git
cd ragnarok-online-study
git rev-parse HEAD
python3 tools/check_public_tree.py
node --test tools/character-lab/tests/modular-motion.test.mjs \
  tools/character-lab/tests/modular-engine.test.mjs \
  tools/character-lab/tests/native-core-synthetic.test.mjs
env -u ART_RECIPE_LOCAL -u ART_RECIPE_FULL PYTHONDONTWRITEBYTECODE=1 \
  python3 -m unittest discover -s tools/character-lab/tests -p 'test_*.py' -v
```

Use **Python 3.9+ and Node 22+**. These checks need no pip/npm packages, game
assets or service credentials. The source-only suite defines 23 Node tests and
58 Python tests; three Python tests are optional local/full reproductions and
are expected to skip without the Mac-local pack. Compare the clone's commit
with the exact remote SHA reported at handoff; test counts are not a substitute
for checking that commit.

## Linux engine

The destination reports Python 3.12, Node 24, Git/LFS, ffmpeg and a working
headless Godot 4.6.3. No installation is needed for its source baseline. Use
that existing engine for initial source-only smoke tests; those results do not
prove 4.5.1 PNG byte reproduction or asset-dependent game compatibility.

The project is `Willow Field — Offline RPG Study`, using GDScript and Godot's
GL Compatibility renderer. The tested Mac engine is
**Godot 4.5.1.stable.official.f62fdbde1**. `Setup.command`, `Play.command` and
`Edit.command` target macOS. Only if reproducing the pinned engine is necessary,
install the official Linux 4.5.1 binary separately.
Select the asset matching `uname -m` (`x86_64` or `arm64`):

```sh
uname -m
# Example for x86_64; use the arm64 archive on an aarch64 host.
mkdir -p .tools/godot-linux
curl -fL https://github.com/godotengine/godot-builds/releases/download/4.5.1-stable/Godot_v4.5.1-stable_linux.x86_64.zip \
  -o .tools/godot-linux/Godot_v4.5.1-stable_linux.x86_64.zip
curl -fL https://github.com/godotengine/godot-builds/releases/download/4.5.1-stable/SHA512-SUMS.txt \
  -o .tools/godot-linux/SHA512-SUMS.txt
(cd .tools/godot-linux && \
  awk '$2 == "Godot_v4.5.1-stable_linux.x86_64.zip" {print}' SHA512-SUMS.txt > verify.sha512 && \
  test -s verify.sha512 && sha512sum -c verify.sha512 && \
  unzip Godot_v4.5.1-stable_linux.x86_64.zip)
GODOT_BIN="$PWD/.tools/godot-linux/Godot_v4.5.1-stable_linux.x86_64"
chmod +x "$GODOT_BIN"
"$GODOT_BIN" --version
mkdir -p logs
QA_LOG="$(mktemp -d "$PWD/logs/linux-source.XXXXXX")"
"$GODOT_BIN" --headless --log-file "$QA_LOG/rules.log" --path . --script res://tests/rpg_rules_test.gd
"$GODOT_BIN" --headless --log-file "$QA_LOG/indexed.log" --path . --script res://tests/indexed_import_test.gd
"$GODOT_BIN" --headless --log-file "$QA_LOG/contract.log" --path . --script res://tests/slot_contract_test.gd
```

Always use explicit absolute Godot log paths in restricted workspaces. The recipe
runner accepts `--godot /absolute/executable` or an absolute `GODOT` environment
variable; a bare `GODOT=godot` does not search `PATH`. Optional local/full Python
tests currently check for the Mac executable before running and can skip on
Linux even with `GODOT` set. Explicit recipe CLI runs are a separate check.
Cross-platform byte-identical PNG reproduction has not been established.

## Asset and access boundary

There are **no Git LFS objects, submodules or package-manager dependencies** in
this checkpoint. Git cannot restore the ignored local asset pack. Existing
[public-repository scope](PUBLIC_REPOSITORY.md) remains in force: redistribution
permission for native RO references is unestablished, and mixed replacement-art
packs, native manifests, screenshots, logs and snapshots stay local. No new art
license is asserted by the synchronization; the repo has no project LICENSE file.

The complete field requires `assets/reference-ro/`, including ACT/SPR actors,
native `map-study` files, models and textures. Character Lab additionally requires
`tools/character-lab/assets/`, including native templates/equipment, protected
Wayfarer packs and the installed `completion-2026-10-02/packs/` modules. The two
completion recipes pin 12 native ACT/SPR inputs, plus their local boards and
candidates. The asset snapshot is local and is not a GitHub release or cloud copy.

Without a separately permitted asset transfer, cloud work is limited to source
and synthetic tests. Do not force-add ignored media, download native references,
run native visual fixtures or overwrite saved evidence. Do not claim the game
has migrated merely because Git clone and source-only checks succeed. Keep the
Mac-local pack intact; Git is not a backup of it.

## Next work

The [selected art milestone](character-lab/COMPLETION-QA-2026-10-02.md) and D13/D14
are complete. Wayfarer covers idle/walk/ready/dagger attack in eight directions;
Lantern Scholar remains a six-body/one-head front reuse proof. Full artwork
coverage and user artwork acceptance remain separate.

First verify the destination clone, Python/Node checks and the asset-independent
Godot tests above. Then follow the existing [C8–C12 backlog](character-lab/INSPECTION-2026-09-24.md):

1. C8: derive attack hit timing from the ACT event frame rather than fixed 0.45;
   use synthetic event fixtures and preserve native clip timing.
2. C9/C10: verify direction-specific layer order and job/weapon action mapping
   against authoritative existing format research before changing behavior.
3. C11: resolve the 24 ms versus 25 ms ACT tick question from primary source;
   preserve current behavior until that decision has evidence.
4. C12: expose missing-action fallback with a useful warning and a synthetic
   missing-action case.

Asset-dependent acceptance and additional generated artwork are blocked until
the destination has a separately authorized pack. No paid services, new
credentials, live game-server work, merge or deployment are required.
