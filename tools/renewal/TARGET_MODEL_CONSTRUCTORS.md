# Supplementary Model constructor route (T07.007.008)

Adds one exact second profile route to the existing Model parent for the four-root supplement (`mu_fild01`, `ygg_edge`, `ygg_fruit`, `ygg_roots`). It observes `new Model(buffer)` and the unchanged `summarizeModel` projection for 273 retained bodies. A returned constructor does not prove a texture fetch, instancing, compile, render, map travel or full-game coverage.

Frozen task: [T07.007.008](../../docs/project/tasks/T07.007.008.md). New profile `cc53e345…050dea` (4168 bytes); private manifest `9980ac60…edd541c` (563422 bytes). The old T06.003.003.006 route, its profile `9ad90329…b2140d`, exported APIs, CLI flags, exit codes and report schema are unchanged. See [MODEL_CONSTRUCTOR_PROBE.md](MODEL_CONSTRUCTOR_PROBE.md) for the shared execution rules.

## Changes

Owned files only: `probe_model_constructors.mjs`, `test_probe_model_constructors.mjs` and this note. The worker (11388 bytes), common summary (6452 bytes), seven modules, three rule files, both profiles and the authored fixtures are unchanged.

- **Route selection.** The profile is read in full, then its exact bytes/SHA256 select a route from `ROUTES`. Anything else is `pin_mismatch`. Each route has its own task, manifest and availability contract. A new profile with the old manifest path, the old profile with the new manifest path, or a non-canonical `--input-root` refuses with `path_refused`. The supplement route requires `--input-root` to equal the frozen execution `cwd`.
- **Worker pin.** The supplement profile pins `model_constructor_worker.mjs`. It is checked at admission, before every worker creation, and at the final recheck. A drift before creation produces an `environment_failure` row with reason `worker_pin`. That row halts later jobs as `source_drift`.
- **Descriptors.** Every manifest availability, body and ledger-profile identity must have exactly the five keys `dev,ino,size,mtime_ns,ctime_ns` as canonical decimal strings, with `size` equal to the pinned bytes. Reads use the existing `lstat`/`O_NOFOLLOW`/`fstat`/full read/`lstat` path and refuse symlinks, special files and hardlinks. Bodies also need `0600` permissions in a `0700` directory.
- **Availability contracts.** These are checked as their real schemas, never as aliases of the old root005 audit:
  - **Report** (`T07.007.006`): the three qualification flags must be exactly `true`, and `catalog_pin` must equal the admitted catalog bytes/SHA. All 311 records join the catalog by `target_index`, with `request_index = i + 2`, `wire_target = '/' + http_path`, attempted/200/wire-complete/stored-complete/null-error, a matching `model` or `bmp` signature, and `wire_bytes = stored.bytes`. Health plus two cache records make 314 requests. Totals are 7575826 wire and stored bytes; the target bodies alone total 7575328 bytes.
  - **Catalog** (`T07.007.005`): has 4 roots, no gap ordinals, and dense jobs whose single root reference joins `roots[r].edges[kind].job_id`. All 337 referrers join exactly once to a loader entry with the same `target_index` and `http_path`, and the role equals the job role. Occurrence loader indexes must be in range. The report's `catalog_refs` must match.
  - **Artifact audit**: must equal the frozen literal, typed exactly. `report_sha256` must equal the admitted report hash. Its targets, referrers, request records and wire/stored totals are cross-checked against the computed values. `guard_receipt_sha256` is the historical guard receipt, not the 5454-byte wrapper. Its null live/native/argv/game fields remain limits.
  - **Execution receipt** (`root-t07-actual-execution-gate-1`): the gate and equality flags must be `true`, `first_failure` null, `later_errors` empty, and the qualification claim null. `binding` must equal the frozen literal, including `argv[3] = driver_file`, `[bytes, sha]` pins, counts, `HOME_present`, the child `PATH` and the guard defaults.
  - **Guard result** (inside the execution receipt): schema `root005-two-group-external-guard-1`, valid. `driver_exit` is safe integer 0, `guard_action` null, `native` present, `groups_after` non-empty with every group empty. `work_seconds`, `rss_limit_bytes` and `cleanup_grace_seconds` are 1800/2147483648/8 and must agree with the binding defaults. `driver_pin` is exactly `{bytes, sha256, identity}` and must agree with the binding. Its `identity` is the historical five-integer list. Its nanosecond members exceed the safe range, so they are checked with `Number.isInteger`, not `Number.isSafeInteger`, and are never stringified or re-emitted. Decimal-string tuples are refused. The receipt is not executed, and native inputs are not reopened.
- **Bridge.** The parent rebuilds each expected record from the report and catalog and compares it field by field with the manifest. Each model target keeps its dense `model_ordinal` (0..272, distinct from `target_index`), `request_index`, pointers, `http_path`, referrers, complete original `availability_record` and body descriptor. All 297 `root_model_references` keep catalog job id, source row, loader index, role, root ordinal, edge kind, summary pointer and `occurrence_indexes`, for 4922 placements in total. These index occurrence summaries; no placement gets a constructor job. All 38 `carried_ground_targets` keep their complete catalog and report pairs and their 40 ground referrers. They are neither jobs nor decoded BMPs. Roots, empty subset gaps, `prior_first_level_gaps = []`, limitations and the world ledger reference must match. The ledger reference is 1296 roots, 82 gap roots and `reconciled_by_this_subset = false`. Its old profile is full-read under the input root and its counts are checked against the ledger.
- **Bodies and jobs.** All 273 bodies are full-hashed before any job is formed, including bodies that `--max-jobs` will leave unattempted. Their header prefixes must equal the report signatures. The histogram 1.4:94, 1.5:5, 2.2:6, 2.3:168 is an observation, not a parser allowlist. Grouping uses the existing byte-equality rule and yields 273 jobs (4784704 distinct bytes), which must equal the manifest jobs field by field. Every body is reread and hashed again after the run.
- **Report.** The schema is unchanged, `task` is `T07.007.008`, and targets are expanded with `constructor_outcome`. The report also carries `root_model_references`, `carried_ground_targets`, `world_gap_ledger_reference` and `availability_admission` totals. A separate `functional` block reports `all_model_constructors_returned` and the exact `open_failures`. It is false unless every job returned and the run qualified, and it is also set false whenever the report is later disqualified.
- **Fixtures.** Fixture mode under either profile reads only the authored file, summary, modules, rules and owned sources (plus the worker pin on the new route). It does not open the manifest, availability inputs, ledger profile or bodies.
- **Test seam.** `hooks.afterPinnedJson(role, value)` runs only after a complete pinned read and hash. The CLI never sets it.

## Candidate results (Claude, base 1fe89ee, code commit 4e2d15f)

Run on 2026-10-21 with `/Users/shem/.local/bin/node` v24.20.0. ROOT is the canonical checkout named in `execution_binding_expected.cwd`. Outputs are under this checkout's ignored `.tools/renewal/t07-007-008-candidate-evidence-1/`, with directories `0700` and files `0600`.

1. `node --experimental-vm-modules --no-warnings --test tools/renewal/test_probe_model_constructors.mjs` gave 48 tests, 48 pass, 0 fail, in about 25s. That is the 36 existing tests plus 12 T07 tests. The log is `tests.log`.
2. The fresh old fixture CLI (old profile, `--fixtures` authored) exited 0. It reported `complete`, 13/13 matched (9 full returned summaries, 4 expected exception names), task `T06.003.003.006`, and 15/15 final pins. `jobs.jsonl` is 32969 bytes `cd227786…5e83b`.
3. The fresh new-profile fixture CLI exited 0. It reported 13/13 matched (9/4), task `T07.007.008`, and 16/16 final pins including the worker. `jobs.jsonl` is 32970 bytes `9e3d9aee…1139`. It is one byte longer only because of a timing value.
4. The actual 273-job CLI (new profile, frozen manifest, default limits, no `--max-jobs`) exited 0 with status `complete`.
   - Outcomes: 273/273 `returned` and 0 constructor exceptions. All 273 workers exited 0, observed and not parent-terminated.
   - Checks: postcheck 273/273 bodies, 21/21 final pins. `functional.all_model_constructors_returned = true` with no open failures.
   - Measurements (not golden values): elapsed 8042ms; peak sampled RSS 125173760 bytes over 430 samples.
   - `jobs.jsonl`: 854897 bytes `9ca22761da62c06f947b31ed5762b708bf415d79696c510e5305a77d610246fe`.
   - `report.json`: 694232 bytes `b2c205534a9905252b2984a70371070e128e5e66cde1a5302ac72a6affd97cf6`.

The final pin checks in the reports recorded the parent source as 101846 bytes `38fe32b1…f8fd37` and the unchanged worker `c1eee8da…22a3f4`.

The new tests cover:

- frozen baseline literals;
- route and profile typing (strings, booleans, non-integral and unsafe values);
- historical integer tuples against decimal strings;
- new-profile fixture full rows, and fixture mode not opening corpus inputs;
- cross-route substitution;
- full-hash positive hook activation with a `--max-jobs 0` suffix;
- 95 table-driven typed refusal cases over the manifest, report, catalog, audit, execution receipt, ledger profile and profile, plus a coherent report/manifest header change that still disagrees with the body bytes;
- lower-only limits with a `--max-jobs 2` suffix control;
- authored nonzero, timeout and lost-exit workers;
- jobs EIO and report-rename storage faults;
- worker pin drift before creation, body reread and postcheck drift, and final worker drift;
- the actual 273-row comparison against the manifest.

The `--max-jobs` runs are controls, not corpus evidence.

## Limitations

- Only the four-root supplement is covered. The 1296-root world ledger and its 82 gap roots stay open, and original world ordinals stay null/unknown.
- Constructors and declarations only. Nested texture availability, image decode, `createInstance`, compile, render, travel, combat, quests, persistence and Traditional Chinese acceptance are separate gates.
- RSS is sampled, not OS containment. The guard and audit limitations of the T07.007.006 inputs carry over.
- This is a worker candidate. Root must independently rerun it, compare all rows with the withheld reference, and audit the outputs before any `ready_for_user`.
