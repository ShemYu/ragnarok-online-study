# T07.007.004 four-target terrain constructors

The existing parent admits one additional exact profile and runs the unmodified
World, Ground and Altitude constructors. A returned constructor is an observation.
Format validity, dependency availability, native parity, compile, render, travel,
save, story and full-game coverage stay open. This four-map subset does not
replace the full coverage ledger.

Base: `7fb7a1e458c1eebbc1b03892d4de3629b6202f13`.
The candidate commit is the commit that adds this file together with the two
runner files below. The private report records that full SHA.
Running parent: `tools/renewal/probe_map_constructors.mjs`, 44087 bytes,
SHA `ec581316ad7220956613322f598310b91d2e1d455a0949edb7539c230fc8c961`.
Running tests: `tools/renewal/test_probe_map_constructors.mjs`, 48909 bytes,
SHA `25f0722d1b46c41ad58310cd7a080fcf466fa71ea2d45c4e134b4972df74a707`.
`T07.007.004-profile.json` field `baseline_tools.parent.sha256`
(`5c916d7678fb2480e1f80e89a867dca22b7d298da9b393e5d87fa3b9f02c0350`, 36633 bytes)
is provenance for the pre-change parent.

## Owned files

- `probe_map_constructors.mjs`: second allowlist entry, manifest task/count/linkage checks, worker pin.
- `test_probe_map_constructors.mjs`: old 26-case route plus the new admission controls.
- `TARGET_MAP_CONSTRUCTORS.md`: this note.

Unchanged: `map_constructor_worker.mjs`, `map_constructor_summary.mjs`, both frozen
profiles, the authored fixture, the nine client modules and `MAP_CONSTRUCTOR_PROBE.md`.
The original profile `b6635a65db373f5240112734e1f51311851101603323fe1d5300dfaa1c74cf5c`
still admits only task `T06.003.003.003`, its original manifest and its authored
fixtures. Its report schema stays `T06-map-constructor-report-1` with task
`T06.003.003.003` and no worker field.

## New admission

Allowlist entry `f4ed366d2da83eec2aed5a25178ce826d15b43bb7a8b6c583e023c616b47e56e`
(3924 bytes) binds task `T07.007.004`, manifest
`.tools/renewal/t07-007-004-constructor-input-1/input-manifest.json`
(10338 bytes, SHA `37f038082891a626ab1251fd3bd697d73a867f9dca90ba89288f5b18e6be2161`),
counts 4 roots / 4 observed / 0 unavailable / 12 jobs / 12 edges, the same nine
source pins and summary pin, and worker
`tools/renewal/map_constructor_worker.mjs` (9132 bytes, SHA
`1a7bdf5693364800b23c2ba2a4eb052c0521527b89732e857d55ea406e0ec395`).

The worker pin is checked before each worker starts and again in the final
identity check. It is not added to the nine client-source entries. The new
report uses schema `T06-map-constructor-report-1`, task `T07.007.004`, and an
explicit `worker.verified` pin. Swapped old/new manifests are refused before
the other manifest is opened. `--max-jobs 0` writes 12 unattempted rows, exits
nonzero and opens no body.

Roots stay ordinals 0..3: `mu_fild01`, `ygg_edge`, `ygg_fruit`, `ygg_roots`.
File order is GAT, GND, RSW. `original_gap_root_ordinal` stays null. The empty
subset gap list means body metadata exists.

## Commands

Old route, canonical client source:

```sh
T06_INPUT_ROOT=/canonical/repository \
  node --experimental-vm-modules --no-warnings --test --test-concurrency=1 \
  tools/renewal/test_probe_map_constructors.mjs
```

This candidate: 33 tests, 0 failures, 0 skipped, runner `duration_ms` 4930.994.
The original 26 authored outcomes and summaries still match. The 2761-body
corpus was not repeated.

Actual twelve-job command, from this checkout:

```sh
node --experimental-vm-modules tools/renewal/probe_map_constructors.mjs \
  --input-root /canonical/repository \
  --client-source /canonical/repository/.tools/renewal/client-source \
  --profile docs/project/fixtures/T07.007.004-profile.json \
  --manifest /canonical/repository/.tools/renewal/t07-007-004-constructor-input-1/input-manifest.json \
  --output /this/checkout/.tools/renewal/T07.007.004/0700/0600/actual-12
```

An outer guard of 150 seconds sends SIGTERM, waits 15 seconds, then SIGKILL.
It did not fire. There was no retry.

## Actual observation

Exit 0. Stdout: `complete`, `returned` 12, `cleanup_verified` true.
Parent `elapsed_ms` 770. Outer wall 0.828 s. `/usr/bin/time -l`: real 0.82,
user 1.05, sys 0.06, maximum resident set size 242302976, peak memory footprint
210474248. Tool RSS samples 28, peak 241795072, over-limit samples 0.
Twelve workers started, twelve exits observed, every `exit_code` 0, parent did
not terminate them. No constructor exception, summary error, input refusal,
timeout or unattempted row.

`report.json` is 8112 bytes, SHA `ab14d22c38d8d302a0f4b31e7ac7666990558df1de3f5513a60285086cb57270`.
`jobs.jsonl` is 405226 bytes, SHA `4659343ae10a5faed7ae7a0f2d9af9db38cd5290b5f03ef1442187a1e82c41c3`,
12 records. Model and sound lists match the summary object counts.

| Job | Map | Result |
| --- | --- | --- |
| target-000 gat | mu_fild01 400×400, 800000 cells, flags 1/8/10 | returned, 86.533 ms |
| target-001 gnd | mu_fild01 200×200, 26 textures, 41429 tiles, trailing 0 | returned, 98.782 ms |
| target-002 rsw | mu_fild01 build 244, 1285 models, 188 lights, 182 effects | returned, 34.023 ms |
| target-003 gat | ygg_edge 300×300, 450000 cells, flags 1/10 | returned, 65.836 ms |
| target-004 gnd | ygg_edge 150×150, 0 textures, 0 tiles, 22500 surfaces, trailing 0 | returned, 42.439 ms |
| target-005 rsw | ygg_edge build 227, 1290 models, 164 effects | returned, 34.106 ms |
| target-006 gat | ygg_fruit 240×240, 288000 cells, flags 1/10 | returned, 54.190 ms |
| target-007 gnd | ygg_fruit 120×120, 2 textures, 14400 tiles, trailing 0 | returned, 53.778 ms |
| target-008 rsw | ygg_fruit build 227, 509 models, 85 effects | returned, 30.747 ms |
| target-009 gat | ygg_roots 400×400, 800000 cells, flags 1/8/10 plus 2 NaN | returned, 87.748 ms |
| target-010 gnd | ygg_roots 200×200, 12 textures, 65644 tiles, trailing 0 | returned, 116.385 ms |
| target-011 rsw | ygg_roots build 244, 1838 models, 749 effects | returned, 35.903 ms |

The two NaN altitude samples are `cells[416889]` and `cells[452539]`. Both are
flag slots. They are preserved in the common summary. GND 1.9 cursors report
`trailing_bytes` 0 on all four grounds. `ygg_edge` ground returned with an
empty texture list, empty tile list and lightmap count 0. No loader was changed
to alter these results.

Independent audit, before and after the run: all 12 body full hashes, all nine
source hashes, the worker, the summary, the manifest and the profile matched
their pins. Inodes were unchanged. No symlink was followed. The process group
was empty after exit.

Private artifacts, directories 0700 and files 0600:

`.tools/renewal/T07.007.004/0700/0600/actual-12/` and
`.tools/renewal/T07.007.004/0700/0600/REPORT.md`.

## Rollback

Revert the candidate commit. That restores the three owned paths. Delete this
checkout's `.tools/renewal/T07.007.004/` to remove private output. Git does not
restore game saves, databases or installed files; this run did not change them.

Next owner: root. Root reruns both candidates, compares all 12 full typed rows
and stable summaries, checks preservation and the shared controls, then scores
and integrates. This candidate's twelve returns are an observation for that
comparison, not root qualification.
