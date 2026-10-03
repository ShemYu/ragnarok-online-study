# Completion acceptance — 2026-10-02

The selected Character Lab and game-art milestone is complete and installed locally. Wayfarer has a coherent idle/walk/ready/dagger-attack set in eight directions; Lantern Scholar proves a second character through configuration. The importer, head v3, action coverage and second-character reuse were verified together. Codex visual review passes, including the protected back-v2 drawings. User artwork approval has not been recorded.

## Open and play

Open [the local frame viewer](../../tools/character-lab/assets/completion-2026-10-02/review.html) directly in a browser. It works from a file without a server and offers character, action, direction, headgear, native-speed playback and frame stepping. Its 984 PNG frames come from the installed game appearances. [Fresh Chrome screenshot](../../logs/completion-2026-10-02/review-browser-escalated.png).

To review in the offline field without reading or writing progress, run from the repository root:

```sh
.tools/Godot.app/Contents/MacOS/Godot \
  --log-file "$PWD/logs/completion-2026-10-02/play-local-review.log" \
  --path . -- --no-save --review-job=swordsman \
  --appearance=res://tools/character-lab/appearances/wayfarer-complete.json
```

**O** cycles outfits and **H** cycles none/cap/hat. The review job changes the displayed sprites; it does not change character progression. The old accepted appearance and normal play entry remain available.

Local art/reference packs are required. The public source checkout excludes generated images, reference binaries and these visual fixtures.

## Delivered scope

| Deliverable | Acceptance |
| --- | --- |
| Wayfarer body | 67 drawings: 0–44, 54–65, 82–91; all eight directions in idle, walk, ready and dagger attack. Fifty-six are newly generated; the protected 11 front/back drawings are retained. |
| Wayfarer head v3 | Five newly generated head views, 0–4; strict original silhouette/face thresholds and native none/cap/hat attachment. |
| Back-v2 | Independent Codex review passes in the complete look. Its original files and user-pending status remain unchanged. |
| Lantern Scholar | Six new front body drawings, 82–86 + 54, and head 1; nine native front attack frames under none/cap/hat, with a distinct coat/book/bob design. Other drawings use native fallback. |
| D14 | Shared import/export behavior is configured by character specs, board layouts, recipes and fixture plans. The two characters used identical importer code hashes; saved imports still reproduce byte for byte. |
| D13 | Eleven source-independent native composition/attachment tests run in public CI. |
| Local review | Both appearances are installed, available to outfit cycling, and rendered through the game actor. A file-based viewer and save-free field entry are ready. |

Scholar is a front-attack reuse proof. Front ready frame 0 uses its new body 54; ready frames 1–5, rear attack/ready and the other actions remain native. The concept is adapted to the available male Swordsman/novice-head templates; beret and ribbon are omitted so equipment stays separate.

Wayfarer sit, pickup, hit, dead, cast, other attack groups and head 5–14 remain native. Full 94-gameplay/118-total body coverage, a complete second job, C8–C12 research and online/server work were outside this selected milestone.

## Final evidence

| Check | Actual result | Evidence |
| --- | --- | --- |
| Final strict recipe runs | Wayfarer 12 modules + Scholar 2; both PASS, zero problems, all modules reviewed-by-codex | [Wayfarer](../../logs/completion-2026-10-02/wayfarer-final/REPORT.md), [Scholar](../../logs/completion-2026-10-02/scholar-final/REPORT.md) |
| Installed packs | All 14 packs, 1,366 PNG records verified; all 105 import comparison checks true | [Final integrity QA](../../logs/completion-2026-10-02/final-preservation-installed-qa.json) |
| Installed game actor | Wayfarer: 139 checks, 624 frames, applied 67 body/5 head, no missing drawings in the four states. Scholar: 58 checks, 360 frames, 6 body/1 head with explicit fallback | [Wayfarer runtime](../../tools/character-lab/assets/completion-2026-10-02/review-wayfarer/look-review.json), [Scholar runtime](../../tools/character-lab/assets/completion-2026-10-02/review-scholar/look-review.json) |
| Visual review | All 18 actor contact sheets plus 18 selected native-size PNGs inspected; no blocking art issue | [Independent visual QA](../../logs/completion-2026-10-02/art-scope-final-visual-qa.json) |
| Reviewed versus installed art | All 1,366 imported PNGs match the initially reviewed runs; all 984 final actor PNGs match isolated review | [Run continuity](../../logs/completion-2026-10-02/final-run-visual-continuity.json), [Integrity QA](../../logs/completion-2026-10-02/final-preservation-installed-qa.json) |
| Viewer controls/paths | 5,445 Node assertions; all 984 frames, 18 contacts and both reports present | [Viewer verification](../../logs/completion-2026-10-02/review-viewer-validation.json) |
| Browser render | Fresh Chrome file-open rendered the installed art and controls; screenshot and DOM retained. Control assertions above ran in Node, not in a browser automation suite | [Screenshot](../../logs/completion-2026-10-02/review-browser-escalated.png), [DOM](../../logs/completion-2026-10-02/review-browser-escalated-dom.html) |
| Field boot | Exit 0 with --no-save, Swordsman review sprites, installed Wayfarer and cap, 30 engine frames | [Boot log](../../logs/completion-2026-10-02/main-wayfarer-no-save-boot-console.log) |
| Python recipe suite | 58 discovered: 57 passed, one optional full-reproduction test skipped. Actual full reproduction ran separately below | [Python log](../../logs/completion-2026-10-02/validation-python-local-final.log) |
| Saved reproduction | All 100/100 saved PNGs byte-identical across three packs, zero problems; historical head failure retained explicitly | [Saved report](../../logs/completion-2026-10-02/saved-reproduction-final/REPORT.md) |
| Other regressions | Appearance 48; output safety 22; slot board 21; indexed import 13; slot contract 5; synthetic native 11; modular 12; saved pipeline 197 hashes/18 native tests | [Workflow and command evidence](COMPLETION-2026-10-02.md#confirmed-local-evidence) |
| Preservation | All 1,976 protected original files, including old appearances/art, snapshots, historical evidence and four saves, unchanged | [Final integrity QA](../../logs/completion-2026-10-02/final-preservation-installed-qa.json) |
| Art provenance | All 14 selected raw candidate copies, originals, prompts and reference hashes verified | [Generation provenance](../../logs/completion-2026-10-02/generation-provenance-verification.json) |

The new recipe/source/config files passed the public path guard without staging assets; the Git index still contains only the original 140 public paths. Git diff whitespace checks pass. Native ACT bytes, source frame timing, registration and attachment records remain unchanged.

The existing Claude CLI was the main code implementer, resumed in its authorized session with its configured default model (the run reported claude-opus-5-5[1m]). Codex handled generated artwork, strict gates, runtime/visual review and acceptance. No commits, pushes, deployments or game-server actions were performed.

## Limits and remaining decisions

There is no technical blocker to using the installed local milestone. Artwork approval remains the user's decision; reviewed-by-codex never means user-accepted. Official direction-dependent draw order, hit-event timing and the other C8–C12 research items remain unverified. Native headgear, weapon, trail and environment artwork still serve as reference assets.

The field check was a headless boot, not a fresh interactive gameplay playthrough or performance benchmark. Fresh browser evidence covers the new local viewer; the older pipeline's browser parity evidence remains its historical review. Godot emits a macOS certificate-store warning in this environment, but every listed offline Godot check exited successfully.

For exact recipes, crop selections, regeneration commands and coverage boundaries, see [the completion handoff](COMPLETION-2026-10-02.md).
