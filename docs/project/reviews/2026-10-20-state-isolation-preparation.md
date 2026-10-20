# Separate quest-test state: source preparation

2026-10-20. Root. **Preparation only; no app/VM/database trial executed.**
The [qualified texture scan](2026-10-20-T06.003.003.008.md#actual-scan-and-independent-availability-audit-qualified)
allows the next ordinary quest/runtime-load step. Independent state preparation
can run alongside the T07.001 proposal comparison and official-baseline work.

Root reads the complete internal14348-byte note and personally checks the
critical upstream source sections, then full-hashes all17 cited files against
the clean committed upstream revision2c3b2612973fb8d0ae6ad366a2b298686f2404cb.
The source documents a disposable second VM/database beside the player's app.
Runtime support in the installed binaries and actual coexistence remain open.

Concrete source findings for the next frozen paired plan:

- Separate app home, state, runtime, Nebula home/socket/volume and Electron
  profile are required. A new character or Git worktree does not isolate a VM.
- Move all six game/API ports and the separate admin port; move rotest's port
  too if used. Advertised login/char/map ports and served client configuration
  must agree with actual one-to-one forwarding. A login page alone cannot
  identify the database reached. The development helper's free-port check
  covers fewer ports than this complete coexistence boundary.
- Startup's legacy-home migration runs before port validation. Its skip
  predicate is a pre-existing client.json in the new home, not just a directory.
  Do not use Repair: its broader stale-engine cleanup can stop legacy engines.
- A103-byte Unix-socket limit requires a new, short, explicitly owned path;
  the current long checkout path cannot hold the test world directly. Do not
  disguise a long world through a symlink.
- The development-world preparation requires built supervisor/client outputs.
  The packaged headless route may avoid another build by materializing the
  signed package into a fresh home/profile; actual support must be proved.
- Default rotest setup promotes its tester to GM. Ordinary acceptance needs a
  fresh group0 character and source-defined progression, with admin diagnostics
  labelled separately.

Primary local references: electron/main.js173–235,384–390,514–559,3840–3857,
3988–4057; stack/src/config.rs108–119; docker.rs80–100; ports.rs27–139;
cmds.rs431–507/2895–2925; tests/e2e/world.cjs16–119;
docs/AGENT_TESTING.md69–123, all at the exact upstream pin. Root inspected
migration/locking/port validation/Repair/socket selection directly. No native
or live-save access follows from these source observations.

Next: compare actual Claude/Grok plans on identical inputs, then root proves
the new engine/volume/ports/client handshake before any test login. Preserve
the newest player state and keep the existing game running. Test persistence
and any restore only in owned separate test state. Astra is reviewing the
minimum necessary preservation/isolation proof to avoid redundant recovery
work; its advisory does not establish runtime success or replace the pair.

Private note .tools/renewal/t06-006-isolation-preparation-1/DRAFT.md,
14348bytes/SHA3f6b8ac15b776c8dec1fa745f59542a8ae42fb4c5b1f37b9c0435a9f29f6ed3a.
root-source-pin-review.json records all17 committed/full source matches.
Full Modern/Renewal, eventual Traditional Chinese and later party-only scope
remain unchanged. No current game, save, network or preferences changed.
