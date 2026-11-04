# Test classification and safe mutation-suite runner (T00.006)

Task: [T00.006](tasks/T00.006.md). Frozen base `a06f1037ac6ecf308db6a963e06391ebbf586cbd`.
The selected Claude candidate is integrated. Root's
[selection and verification scope](reviews/2026-11-04-T00.006-root.md)
supersede the historical worker results below. This is tooling verification,
not a full private-constructor or game-runtime pass.

## Safe entry points

| Purpose | Command | Inputs |
| --- | --- | --- |
| Public CI list | See [root README](../../README.md#source-only-checks) and `.github/workflows/source-checks.yml` | Tracked source only |
| Runner checks, public part | `node --test tests/renewal/run_isolated_suite.test.mjs` | Authored synthetic suite only; two private cases skip with a reason |
| Runner checks, private part | `T00_006_CORPUS=<abs canonical checkout> node --test tests/renewal/run_isolated_suite.test.mjs` | Run from a separate source checkout; explicit corpus differs from that checkout |
| List registered mutation suites | `node tools/renewal/run_isolated_suite.mjs --list` | None |
| Model-constructor suite | `node tools/renewal/run_isolated_suite.mjs --suite model-constructors --corpus <abs canonical checkout> --work-root <new absolute directory outside corpus>` | Explicit corpus; separate work root, including when invoked from the corpus checkout |

Never run `tools/renewal/test_probe_model_constructors.mjs` directly in a source checkout. Its tests rewrite the sibling `model_constructor_worker.mjs`, at about lines 311 and 1775. Restoring the same bytes still changes ctime, and the driver admits `dev/ino/size/mtime_ns/ctime_ns`. The pinned `MODEL_CONSTRUCTOR_PROBE.md` (line 43) still shows the direct command. Its bytes are frozen by the T07.007.008 baseline, so the warning is in the test header and [TARGET_MODEL_CONSTRUCTORS.md](../../tools/renewal/TARGET_MODEL_CONSTRUCTORS.md) instead.

### What the runner does

The runner is `tools/renewal/run_isolated_suite.mjs`. Its only dependencies are Node built-ins and `/bin/ps`. It does not use the historical ignored `.tools` wrapper.

1. **Selection.** Choose a registered suite with `--suite`, or an authored JSON definition with `--definition` (the authored kind is used by the focused checks). A registered private suite with no `--corpus` refuses with `private_input_required` (exit 2).
   - A corpus that is relative, absent, a symlink or a non-directory is refused.
   - A corpus missing any required pinned file refuses with `private_input_missing`. The required set is the 10 client modules/rules, manifest, 4 availability inputs, 273 bodies, ledger profile and the 9-file source closure.
   - All refusals happen before anything is copied, run or created.
2. **Protected snapshot.** Each protected path gets SHA-256 plus `type/dev/ino/size/mode/nlink/mtime_ns/ctime_ns`, before and after the run. Protected paths are the source closure in the invoking checkout and every corpus input. Optional historical world-route inputs are included when present, as are their parent directories (stat only). For this suite that makes 326 entries.
3. **Private tree.** Each closure file is copied into `<work-root>/<suite>-XXXX/tree/` by a read plus an exclusive `O_CREAT|O_EXCL|O_NOFOLLOW` write (0600 files, 0700 directories). No hardlink, symlink or clone is used.
   - A copy must be a regular file with `nlink == 1`, equal SHA and an inode different from every protected inode. Otherwise the run refuses with `copy_not_isolated`.
   - Source symlinks are refused.
   - The copied closure must match the frozen profile/baseline pins. Otherwise the run refuses with `pin_drift`.
   - The work root defaults to `<checkout>/.tools/renewal/isolated-runs`. It may not be inside the corpus, or inside the source tree outside its ignored `.tools`.
4. **Run.** The test runs unchanged as `node --experimental-vm-modules --no-warnings --test <copy>/tools/renewal/test_probe_model_constructors.mjs`.
   - Settings: `cwd` = the copy, its own process group, `PATH=/usr/bin:/bin:/usr/sbin:/sbin`, `TMPDIR` inside the run directory, and `T06_INPUT_ROOT=<corpus>`.
   - The suite's `REPO`/`HERE` therefore resolve to the copy. Every worker rewrite and every `.tools/renewal` output lands in the copy. The corpus is only read.
   - The driver's own admission and source pins are unchanged.
5. **Tracking and cleanup.** Every 100 ms the runner reads the process table. It records each descendant (by parent chain or process group) by pid plus start time, so a reused pid is not mistaken for one. It notes `mutation_observed` when the copied witness worker's ctime/inode changes.
   - SIGINT, SIGTERM or SIGHUP to the runner (or leftovers after a normal exit) trigger SIGTERM to the group and to every live recorded descendant. After `--grace-ms` (default 5000) comes SIGKILL, followed by verification that none remain.
   - **Lifecycle guarantee (repair 1).** Signal handlers are registered before the spawn. Everything from opening the suite log onward (spawn, tracker, every evidence event, the poll/witness loop) runs inside one `try`.
   - The outer `finally` always performs best-effort owned cleanup: the escalation above, or a last-resort group SIGKILL if the escalation itself throws. The protected after-snapshot and comparison then run outside any evidence write.
   - An evidence-write failure during the lifecycle fails the run closed but never skips cleanup or the comparison. A failure to publish the final evidence (`after.json`, the `finished` event, `result.json`) gives status `evidence_failed` (exit 6), never a pass (repair 2). A failed signal-event write is recorded in `evidence_errors` and cannot crash the runner from inside its signal handler.
   - Before the spawn, no owned process exists. A non-refusal error there (for example a copy I/O error) still exits as `runner_error` without an after-snapshot; the runner has written only inside its private run directory at that point.
6. **Exit codes.** 0 = passed. 1 = suite failed. 2 = refused. 3 = canonical changed. 4 = descendant cleanup failed. 5 = runner error after the spawn, with cleanup and comparison still performed. 6 = evidence publication failed. 128+signal = interrupted, with cleanup and preservation intact.
   - Precedence: 3 > 4 > 5 > 128+signal > 6 > 0 / 1. Lost evidence therefore overrides `passed`, `passed_subset` and `suite_failed`; `suite_exit` still shows the suite's own result. Higher-priority statuses keep their codes and list the loss in `evidence_errors`.
   - Status `passed_subset` (exit 0) is used only when `--exclude-test` names exact tests. It is never a full pass.
   - `result.json`, `before.json`, `after.json`, `copies.json`, `events.jsonl` and `suite.log` stay in the ignored run directory.
   - `corpus_identity_preflight` *reports* manifest-pinned identities that already differ from the live corpus. It never repairs them or relaxes admission.

## Candidate results, 2026-11-04 (actual runs)

Node `/Users/shem/.local/bin/node` v24.20.0, macOS. Canonical corpus is the read-only checkout named in the brief; its HEAD moved from `a06f103` to `39c4b66` during this work. Those two commits change only Root's STATUS/PROJECT_MAP/execution docs, so no closure file differs. Evidence is in this worktree's ignored `.tools/renewal/t00-006-claude-evidence/` and `.tools/renewal/t00-006-runner-checks/`.

| Check | Exit | Result |
| --- | --- | --- |
| Public runner checks (no corpus) | 0 | 12 tests: 10 pass, 0 fail, 2 private skipped with reason |
| `--list`; no `--corpus`; absent / empty corpus | 0; 2; 2 / 2 | `private_input_required`; `private_input_missing`, no work root created |
| Full private model suite | **1** | **56 tests: 48 pass, 8 fail.** `mutation_observed_in_copy=true`, 9/9 ordinary private copies, 326/326 protected entries unchanged, 0 leaked, 28.1s |
| Same suite, excluding exactly the 8 drift-blocked tests | 0 | `passed_subset`: 48/48 pass, copy mutation observed, 326 unchanged, 0 leaked, 28.0s |
| Private SIGINT after the copied worker was rewritten | 130 | Mutation at 2315 ms, signal at 2317 ms, 14/56 tests done. SIGTERM reached 3 live descendants (12 observed), 0 leaked, 326 unchanged |
| Private SIGTERM after the copied worker was rewritten | 143 | Mutation at 2156 ms, signal at 2204 ms. SIGTERM reached 3 live descendants (12 observed), 0 leaked, 326 unchanged |
| Independent snapshot of canonical files (Python) | — | 1407 files, identical digest `9a62ad57…f1f15c10` before (16:12:06) and after (16:14:02) the four private runs |
| Repeat on the final committed tree (header comment edit) | 1 / 0 / 0 / 0 | Full 48/56 with the same 8 failures; subset 48/48; runner checks 12/12 private and 10 pass + 2 skipped public. Snapshot files byte-identical before (16:16:45) and after (16:18:13) |
| CI list and hygiene on the final tree | 0 | Public tree 602 paths; syntax 72 Py / 45 JS; Ruff 0.16.9 passes; quest Node suites 24/24; Chapter 1 120 OK; `git diff --cached --check` clean |

### Repair 1: post-spawn failure cleanup (Root source review of `c9dbef6`)

Root found that the original lifecycle spawned the detached suite, closed the log, built the tracker and emitted `started` *before* entering its `try`. The `finally` only removed signal handlers. As a result, an evidence-write failure, or any error in the poll/witness loop, escaped as `runner_error` with no `stopOwned` and no after-snapshot. The repair moves the whole post-spawn lifecycle under an outer `finally`, as described in step 5.

| Check (repaired tree, 2026-11-04 16:43–16:45 JST, canonical HEAD `39c4b660`) | Exit | Result |
| --- | --- | --- |
| Negative control: `c9dbef6` runner plus only the fault hook, `started` write fails | — | `main` threw, the suite group was **still alive** afterwards, and no `after.json` was written. This confirms the defect |
| Injected EIO on the `started` event write (repaired) | 5 | `runner_error`. Group leader and every group member gone, 0 leaked, `after.json` written, 0 protected changes, independent re-snapshot unchanged |
| Injected error inside the poll loop, with the TERM-ignoring and escaped descendants live (copy already mutated) | 5 | SIGTERM then SIGKILL; all 3 recorded pids dead; 0 leaked; 0 protected changes |
| Injected EIO on the signal-event write, then SIGINT | 130 | `interrupted`, write failure listed in `evidence_errors`, all pids dead, 0 leaked, 0 changes |
| Runner checks, public / private | 0 / 0 | 15 tests: 13 pass + 2 skipped (public); 15/15 (private) |
| Full private suite / exact 8-test exclusion | 1 / 0 | Unchanged: 48/56, and `passed_subset` 48/48. Copy mutation observed, 326 unchanged, 0 leaked, no evidence errors |
| Independent canonical snapshot | — | 1407 files byte-identical, 16:43:17 to 16:44:35 |

Preservation is demonstrated for the cases exercised above: success, suite failure, leftovers after exit, SIGINT/SIGTERM after mutation, and injected post-spawn failures on the `started` event, inside the poll loop and on the signal-event write. It is **not** claimed for every possible failure. SIGKILL of the runner itself, host crash, power loss, an unavailable process table and pre-spawn I/O errors are outside the evidence.

The independent snapshot is `ext_snapshot.py` in the evidence directory. It covers canonical `tools/renewal/**`, `docs/project/fixtures/**`, `.tools/renewal/client-source/src/**`, the manifest, the availability inputs and the 273 bodies. For each file it records content SHA-256 plus `mode/dev/ino/nlink/size/mtime_ns/ctime_ns`.

The synthetic interruption checks run a suite that rewrites its sibling, then starts two children: one that ignores SIGTERM and one detached into its own process group. They require the runner's `mutation_observed` event and the suite's own ready file before signalling. They then prove three things: both escalation steps (SIGTERM then SIGKILL) ran, every recorded pid is dead, and the canonical identities are unchanged. A control shows that a direct same-bytes rewrite changes `ctime_ns` with an unchanged SHA, and that the snapshot detects it.

### Unresolved: the full private suite does not pass at the current canonical state

All 8 failures refuse admission with `identity_changed` rather than the asserted outcomes. Corpus files and the runner are not the cause. The supplement manifest pins the ledger profile `docs/project/fixtures/T06.003.003.006-profile.json` with `ino 19645439` and `mtime/ctime 1792464154520062553`.

The canonical file still has the same 4855 bytes and SHA `9ad90329…b2140d`. However, it was recreated on 2026-10-28 09:48:58 JST (new birth time, inode and mtime/ctime), consistent with that day's working-tree checkout. The runner's preflight finds exactly 1 of 278 pinned identities drifted.

Following the brief, the runner neither re-pins, edits nor weakens admission. Root's repair dispatch confirms the stale historical binding from both suppliers. It preserves the old manifest/profile/baseline: no re-pin of canonical private records, no change to the production driver, routes or frozen profiles, and no rerun of the old ignored producer (it pins an obsolete parent and output directory). The 8 private semantic admission failures stay visible for a separately scoped fresh-binding task. The 8 blocked tests are listed in `drift-blocked-tests.txt` and are:

- cross-route substitutions;
- positive admission;
- typed semantic drift;
- lower-only limits;
- worker nonzero/timeout/lost exits;
- storage failures;
- worker pin/reread/final drift (the line-1775 mutation test);
- actual 273-job CLI.

Consequently, no fresh actual 273-job result is claimed here.

### Repair 2: evidence publication failures can no longer pass

Root reproduced `5df05ff` with an authored same-bytes mutation suite. With `hooks.beforeEvent` throwing on `finished`, the run returned exit 0 and status `passed` even though `evidence_errors` held the injected EIO (Root evidence: `.tools/renewal/seven-task-execution-2026-11-04/t00-evidence-fault-root-1/RESULT_ROOT.json`). The source also let `after.json` and `result.json` write failures keep exit 0.

The repair classifies the run status three times: before the `finished` event, after it, and after `result.json`. A failed write adds to `evidence_errors` and reclassifies the run. If `result.json` cannot be written, the runner appends a best-effort `publication_failed` event carrying the final status and code. The stdout line and the exit code always carry the final status. The test seam `hooks.beforeWrite(name)` covers `after.json` and `result.json`; the CLI never sets it.

| Authored control (16:54–16:55 JST, canonical HEAD `0b0252ff`) | Exit | Result |
| --- | --- | --- |
| `finished` event write fails, suite passed | 6 | `evidence_failed`; `suite_exit` 0 still visible; `result.json` records `evidence_failed`; 0 leaked; canonical unchanged |
| `after.json` write fails | 6 | `evidence_failed`; `after.json` absent; the comparison still ran (`changed` = [], more than 0 entries compared); last event code 6 |
| `result.json` write fails | 6 | stdout `evidence_failed`; `result.json` absent; last event `publication_failed` with status `evidence_failed`, code 6; canonical unchanged |
| Suite failure plus `finished` and `result.json` faults | 6 | `evidence_failed` with `suite_exit` 1 visible and 2 evidence errors |
| SIGTERM during a hang, plus `finished` and `result.json` faults | 143 | `interrupted` keeps its signal code and lists 2 evidence errors; all descendants dead; 0 leaked |
| Runner checks, public / private | 0 / 0 | 20 tests: 18 pass + 2 skipped (public); 20/20 (private) |
| Full private suite / exact 8-test exclusion | 1 / 0 | Unchanged: 48/56 (8 stale-binding admission failures), and `passed_subset` 48/48. 0 evidence errors, 0 leaked, 326 unchanged |
| Independent canonical snapshot | — | 1412 files (Root's later commits added 5) byte-identical, 16:54:07 to 16:55:28 |

Not covered: stdout itself being unwritable, a failure to write `before.json`/`copies.json` (pre-spawn; exits `runner_error` with no owned processes), and the earlier limits (runner SIGKILL, host crash).

## Classification of tracked test entry points

Static classification from headers and source. Only the CI list, the runner checks and the private model suite were executed for this task. No broad discovery was run. "Writes `.tools`" means ignored private state created under the *invoking* checkout. That is harmless in a fresh worktree, but it creates directories when invoked inside the canonical checkout.

### Public, CI members

| Entry | Invocation | Notes |
| --- | --- | --- |
| `tests/renewal/quest_text_projection.test.mjs`, `tests/renewal/quest_registration_tail.test.mjs` | `node --test <both>` | Authored only |
| `tools/renewal/test_chapter1_entry.py` | `python3 -I -B <file>` | Own committed source only |
| `tools/renewal/release_compatibility/test_release_gate.py` | `python3 -I -B -W error <file>` | Synthetic packets in private temporary trees; tracked story/patch/manifest reads only; no Engine, private inputs, package install or game execution. Root's integrated113 tests preserve all644 tracked files. |

### Public authored, not in CI

These need no private input. Optional real-input groups run **only** when an explicit environment variable or argument names the input, and are otherwise skipped with a reason. They are CI candidates only after a separate verified run on the CI image.

| Entry | Invocation | Explicit optional/required input; side effects |
| --- | --- | --- |
| `tests/probe_direct_models.test.mjs` | `node --test` | none; writes `.tools` |
| `tools/renewal/test_coverage_ledger.py` | `python3 -I -B <file> -v` | Authored fixtures only; actual pinned regeneration is a separate explicit-root command |
| `tools/renewal/native_capacity/test_prepare_source.py`, `test_build_recipe.py` | `python3 -I -B <file>` | Authored Git/host-shell/fake-Engine fixtures; no installed Engine, package install or server build; actual preparation/build commands are separate |
| `tests/image_consumer_fixture.test.mjs` | `node --test` | `IMAGE_CONSUMER_SOURCE`+`IMAGE_CONSUMER_METADATA`; writes `.tools` |
| `tests/renewal/test_quest_table_inventory.py` | `python3 -m unittest` (header suggests discovery; use the file) | none |
| `tests/renewal/test_quest_negative_lifecycle_patch.py` | unittest file | `T10_NEGATIVE_LIFECYCLE_DONORS` |
| `tests/test_observe_direct_asset_delivery.py` | `python3 -I -m unittest <file>` | none; private temp tree |
| `tests/test_observe_nested_texture_delivery.py` | unittest file, `TMPDIR` in a private prefix | `T07_014_017_PROFILE`; imports the direct-delivery test as a library |
| `tests/test_two_cell_gat_candidate.py` | direct | `TWO_CELL_CASE`; writes a fixed `.tools` base (no temp fallback) |
| `tools/renewal/quest_shared_clock_patch.test.py` | unittest file | none; header says worker-authored, unrun |
| `tools/renewal/test_archive_catalog.py` | unittest file | `T06_CLIENT_INPUTS`+`T06_ARCHIVE_ROOT` |
| `tools/renewal/test_archive_inventory_october.py` | unittest file | `T07_EXTRACTED_MANIFEST`/`T07_ARCHIVE_ROOT`/`T07_OUTPUT_PARENT` |
| `tools/renewal/test_archive_inventory_patches.py` | `-p` single-file pattern | none; writes `.tools/renewal/T07.007.007` |
| `tools/renewal/test_carocc_zh_pilot.py` | unittest file | `CAROCC_ACADEMY` |
| `tools/renewal/test_decode_patch_targets.py` | `-p` single-file pattern | `PATCH_DECODER_SOURCE_ROOT`+`PATCH_DECODER_PATCH` |
| `tools/renewal/test_dictionary_loader.mjs`, `test_navigation_browser_cache.mjs`, `test_npc_plaintext_adapter.mjs` | `node --test` | none (authored doubles) |
| `tools/renewal/test_ui_msgid_adapter.mjs` | `node --test` | `T05_UITEXT_SOURCE` |
| `tools/renewal/test_map_cache_inventory.py` | unittest file | `MAP_CACHE_SNAPSHOT`+`MAP_CACHE_SELECTION` |
| `tools/renewal/test_monster_projection.py`, `test_yaml_graph_inventory.py` | unittest file | `/usr/bin/ruby` Psych required; `T06_YAML_SNAPSHOT` (yaml) |
| `tools/renewal/test_navigation_browser_verifier.py`, `test_navigation_client_repair.py`, `test_npc_plaintext_package.py` | direct `-v` | `T05_008/007/006_INPUT_ROOT`; `WORK` defaults to `.tools` |
| `tools/renewal/test_navigation_ui_zh_tw.py`, `test_quest_ui_zh_tw.py` | direct `-v` | `T05_009_BUNDLE` / `T05_011_BUNDLE`; writes `.tools` |
| `tools/renewal/test_quoted_source_inventory.py` | direct | `QUOTED_SOURCE_FROZEN_ROOT`; source tampering is in-memory/temp only |
| `tools/renewal/test_static_spawn_pilot.py`, `test_static_spawn_references.py` | direct | `STATIC_SPAWN_*FROZEN_ROOT`, `..._FULL839_MANIFEST` |
| `tools/renewal/test_tw_iteminfo_utf8.py` | direct | none |
| `tools/renewal/test_zero_sum_normal_repair.py` | direct | `RO_NORMAL_FIX_INPUT_ROOT`; writes `.tools` |
| `tools/renewal/tests/probe_remaining_compiled_core.test.mjs` | profile-named Node `--test` | none (synthetic) |

### Explicitly private (mandatory input; not public)

| Entry | Required input |
| --- | --- |
| `tests/tga_decoder_fixture.test.mjs` | `TGA_DECODER_BUNDLE` (saved Online.js) |
| `tools/renewal/test_fruit_transport_capture.py` | mandatory fresh `RO_FRUIT_TEST_ROOT` below `.tools` |
| `tools/renewal/test_quest_true_text_mod.py` | `--source <retained .lub> --workdir NEW` |
| `tools/renewal/native_capacity/test_coin_capacity.py` | `--native-source <prepared subset> --clang` |
| `tools/renewal/test_ordered_archive_stack_integration.rs` | Compiled inside the app crate (`use super::link`). Not runnable from this repo; needs `RO_STACK_INTEGRATION_TEST_ROOT` |

### Flagged: import-time private autodiscovery

These choose a private input at import time **without** explicit selection, from a conventional `.tools` file, the sibling canonical checkout or an absolute canonical path. Real-input tests then auto-enable, or tests fail, depending on the host. Do not add them to CI or to any glob. Do not "fix" this with blanket discovery. The recommended later repair, outside this task's allowed edits, is to require an explicit variable and skip with a reason otherwise.

| Entry | Default chosen without selection | Effect |
| --- | --- | --- |
| `tools/renewal/test_server_snapshot.py` | `.tools/renewal/app-unpacked/...` in the checkout | Real archive tests run whenever that file exists |
| `tools/renewal/test_server_selection.py` | `.tools/renewal/t06-candidates/integrated-2` | Pinned-input test runs whenever present |
| `tools/renewal/test_observe_map_dependencies.py` | absolute canonical `.../t07-007-006-legacy-metadata-1/snapshot` and canonical root | Reads canonical metadata; writes `.tools` |
| `tools/renewal/test_catalog_map_dependencies.mjs` | sibling `../reverse-the-Ragnarok-Online-to-play-by-myself` | Corpus tests run or skip by host layout |
| `tools/renewal/test_probe_map_constructors.mjs` | sibling canonical (`T06_INPUT_ROOT` fallback) | Needs canonical client-source; no source rewrite found |
| `tools/renewal/test_probe_model_constructors.mjs` | sibling canonical (`T06_INPUT_ROOT` fallback) | **Also rewrites its sibling worker**. Use only via the runner |
| `tools/renewal/test_catalog_model_textures.mjs` | `CANONICAL_ROOT` fallback to sibling canonical | Reads canonical metadata |
| `tools/renewal/test_observe_model_textures.py` | absolute canonical `CANONICAL_ROOT` default | Full canonical metadata-only preflight |
| `tests/model_geometry_observer.test.mjs`, `tests/tga_decode_observer.test.mjs` | the checkout's `.tools` profile if it exists, else sibling canonical | Private prefix defaults into `.tools` |

### Flagged: exported-only navigation helper

`tools/renewal/navigation_portal_patch.test.cjs` registers no `node:test` cases and has no main. It only exports `runAuthored(onlineText, workerText)`, and its header says it is not executed by the worker. `node --test` on it reports `tests 1, pass 1`, which is a file-level pass with **zero** assertions (observed on this candidate). It is not a meaningful entry point. Its meaningful use is a caller that passes the private saved `Online.js`/worker texts and inspects the returned groups. No checked-in caller exists.

## Limitations and next action

- The full private suite is blocked by the pre-existing ledger-profile identity drift above. The 48/48 subset stays labeled as a subset; it is never a 56/56 or 273-job pass. The subset and the interrupted runs prove isolation and cleanup, not fresh corpus admission or the 273 actual jobs.
- Preservation evidence covers only the exercised cases listed under Repair 1. The fault hooks (`hooks.beforeEvent`, `hooks.afterPoll`) are in-process test seams that the CLI never sets.
- Descendant tracking samples the process table every 100 ms. A process that forks, double-forks out of the group and exits its parent within one interval could be missed. The authored escaped child is caught. This is not OS containment and sets no RSS or CPU limits. SIGKILL to the runner itself cannot be cleaned up by the runner.
- Parent directories of corpus inputs are stat-compared. A concurrent writer in a canonical directory (Root actively commits there) would be reported as `canonical_changed`. That is correct to flag, but it is not attributable to the suite without inspection.
- Only one registered mutation suite exists. Classification is static apart from the commands above. CI membership is unchanged; adding the public runner checks would first need a verified Linux run (`/bin/ps -o lstart`).
- Next owner: Root. Verify the repaired runner and classify every result. A separately scoped fresh-binding task owns the 8 private admission failures and any later full run.
