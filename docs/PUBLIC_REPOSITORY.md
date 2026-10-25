# Public source and local game data

This repository contains the source, authored tests and project records for
[the Modern/Renewal solo milestone](project/GOAL.md). The local game is playable
in tested scenarios; full content coverage remains unverified. Follow
[current status](project/STATUS.md) for the pause boundary and remaining work.
Cloning the source does not install or launch the game.

## Versioned content

- Renewal inventory, compatibility, localization and verification tools.
- Authored fixtures, source/model tests and bounded source-only CI.
- Frozen task briefs, scoped reviews, project decisions and historical evidence.

Game assets, installers, compiled binaries, native RO files, decoded media,
credentials, screenshots, raw logs, app databases, saves, backups and full local
snapshots stay outside public Git. Redistribution permission for reference
assets has not been established in the project records. Do not add them merely
because a local test or archived tool needs them.

`.gitignore` and `tools/check_public_tree.py` retain protections for local files,
including the old asset directories. The checker examines indexed paths; it is
not a secret-content scanner or a rights classifier. Review outgoing source
and documentation separately before publication. Never force-add private data.

## Local state and verification

Keep existing `.tools` inputs, app files, saves and backups where they are.
Git versions source; reverting a commit does not restore those external files.
Use the separately tested backup/recovery process before runtime changes.

[Source-only commands](../README.md#source-only-checks) need Python, Node and
the pinned linter. They do not need private game assets. Other tests may require
exact private inputs, and some auto-detect those inputs when present. Keep the
explicit CI test list; a green source check is not native/gameplay or full-world
acceptance. Installation, normal play and recovery remain separate task gates.

## Retired Godot and Character Lab projects

The user retired both prototypes from the active tree on 2026-10-25. Their
source, reports and old setup instructions remain under
[`archive/legacy-prototypes-2026-10-25`](https://github.com/ShemYu/ragnarok-online-study/tree/archive/legacy-prototypes-2026-10-25).
[The archive record](project/reviews/2026-10-25-T00.003.md) documents removal,
verification and recovery. Only tracked source files were removed; ignored
assets and local snapshots were not deleted or uploaded.

The older `public-source-v0.1.0` tag and private `native-art-poc-v0.1.0`
snapshot remain historical identities. The new archive tag is a source
checkpoint, not a game/asset package or public release. Inspect it in a separate
checkout if needed; do not replay its setup commands against current game state.
