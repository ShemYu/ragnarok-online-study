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

## Astra repair candidate — T07.007.008, 2026-10-21

This is the separately dispatched repair consultation, not a new Claude/Grok
comparison or a change to their scores. Base commit:
`8427f81d0c7b2e36d05b6ec51c6cd3f72069dafd`; candidate is the commit containing
this section on `ShemYu/t07-007-008-repair-astra-a1`. Only the parent, its test
file and this note change. Root must independently verify this candidate before
integration or readiness.

The selected starting parent/test/note hashes were respectively
`38fe32b11c7fb25337be8bcff854b308603afc0dd3a4ca8b5d39cb2c06f8fd37`,
`77acbefc587cffd72aec428c65c2211c5ab99421d828b1a934058cd983f96f29`, and
`4c4da9ea34a203b8f4083e72077763e06ebc3e27d24bbd1e22ad37ac6bf314ea`.
The tested repaired parent is SHA256
`02079022287d188486c90cfb8380a22fa4f04a636c27bbca9606d569fdfb5d23`;
the tested test file is
`b4ce68123c60e8630555e36bbd94df1a3cb78dda5ffdedaa2c07726e4ded7c33`.

### Repair behavior

- The new route compares every policy and summary-limit key/value with the
  frozen semantic literals. Missing/extra keys and changed values refuse after
  genuine full pinned admission. Noncoercing integer validation and lower-only
  CLI overrides remain; JSON number spelling and historical identity typing
  are unchanged.
- Each stream has a separate observed-EOF flag and decoder-flushed flag. A
  natural zero exit alone does not settle a result. EOF may precede or follow
  exit; settlement waits for both streams and the exit. A single cleanup wait
  starts on the first termination request or observed exit, never resets, and
  bounds a missing EOF even after the worker has exited. The parent never
  terminates an already observed exited worker.
- Job/run deadlines are checked on events and final settlement. Result-to-exit
  grace also has an absolute deadline, so an overdue timer cannot accept a
  late natural exit. Cleanup expiry cannot be defeated by a delayed EOF event.
  Decoder tails flush at most once. The first failure, prior result and
  constructor-return/exception facts survive later stream, termination and
  publication failures. A separate `publication_failure` fact records a later
  jobs-write failure without overwriting the earlier execution failure.
- New-route started rows add boolean `stdout_eof_observed` and
  `stderr_eof_observed` under `cleanup`, including false values on failures.
  Unstarted rows do not invent observations. Both fields survive compact
  failure output and have explicit reservation bytes. Prior-result,
  publication and existing log-loss facts also survive compaction. The old
  route retains its existing cleanup field set. Either route marks cleanup
  unverified and accounts for the unattempted suffix when an EOF is missing.

### Tests and actual commands

All execution used `/Users/shem/.local/bin/node`, observed version `v24.20.0`.
Exact argument arrays, working directories and return codes are retained in
`.tools/renewal/astra-repair-1/cli-commands.json` and
`suite-2/command.json`; the private helper scripts retain the actual invocations:

```sh
python3 .tools/renewal/astra-repair-1/preserve.py before
python3 .tools/renewal/astra-repair-1/run-suite.py suite-1
python3 .tools/renewal/astra-repair-1/run-suite.py suite-2
python3 .tools/renewal/astra-repair-1/run-clis.py
python3 .tools/renewal/astra-repair-1/preserve.py after
git diff --check
```

The suite helper made ordinary private copies of the parent, worker, summary,
test, profiles, baseline, authored fixtures and unchanged probe documentation.
Their inode separation was asserted. The tests that deliberately rewrite worker
bytes touched only these copies. Neither canonical nor original child worker
bytes/identities were altered. The fixed Node invocation was
`--experimental-vm-modules --no-warnings --test` followed by the private copied
test path; `T06_INPUT_ROOT` selected the authorized canonical read-only input.
`TMPDIR` pointed inside this child's evidence directory and did not change
production admission. No hardlinks were used.

Final suite: **56/56 pass, zero failures/skips/cancellations**, 48099.637125ms.
All 48 original tests remain, with eight additional repair test groups. Existing
positive EventEmitter stand-ins now emit both `end` events on their authored
exit, before the parent sees exit; they no longer omit this real-worker
lifecycle requirement. Four new-route exact cleanup assertions add both true
EOF fields; all prior outcome/failure/summary assertions remain. The logging
stand-in emits duplicate EOFs and retains its once-only flushing assertions.

New tests exercise every policy/summary field at +1, -1 and string values after
full-pin admission, missing/extra keys, real owned workers with normal, hidden
stdout/stderr EOF, delayed EOF, EOF-before-exit, job/run expiry, nonzero and
unknown exits, result grace, primary exceptions, close/error/termination faults,
late cleanup events, one-time partial UTF8 flushing, compact log/failure
accounting, and suffix preservation under a jobs publication fault. Real-worker
lifecycle packets, module/SEEK values and summaries are explicit authored
stand-ins; they are not Model evidence.

The first suite attempt retained 53/54 passes and one setup failure: the private
copy omitted unchanged `MODEL_CONSTRUCTOR_PROBE.md`, causing ENOENT in its
baseline assertion. The setup was corrected before the final full suite; that
failed log remains in `suite-1/tests.log`. No assertion was weakened to pass it.

Fresh CLI results, all at unchanged profile defaults and without `--max-jobs`:

| Run | Exit / result | Preservation and cleanup |
| --- | --- | --- |
| Old authored | 0; 13/13 literal matches, nine full summaries/four exception names | 15/15 final pins; natural zero exits; original cleanup fields |
| New authored | 0; 13/13 literal matches, nine full summaries/four exception names | 16/16 final pins; all 13 natural zero exits and both observed EOFs |
| Actual supplement | 0; 273/273 returned, no open functional failures | 273/273 body postchecks, 21/21 final pins; all 273 natural zero exits, no parent termination and both observed EOFs |

The separate CLI audit checks every actual job id/hash/header/input size,
module/SEEK/dynamic-import facts, complete target expansion, roots, 297 model
references, carried ground records and world ledger against the admitted
manifest. Full summaries are retained for root's independent reference audit.
Actual CLI elapsed was 8242ms; sampled RSS peaked at125501440bytes over434
samples. These are measurements, not golden values or OS containment.

### Retained evidence and boundaries

All artifact paths below are relative to the child's ignored
`.tools/renewal/astra-repair-1/`. Final directories are0700 and files0600.
The before/after receipts compare **305 protected full hashes, identities,
modes and link counts exactly**, including all273 bodies, availability inputs,
canonical/original worker and summary, profiles, authored fixtures, modules and
rules. Their bytes are identical. One own `inputs-after.json` receipt was
initially created0644 inside the0700 evidence directory; the mode audit found
and corrected it to0600, and the helper now sets its own077umask. This was a
local permission deviation, not an outside-child output; no protected input
was changed.

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| `suite-2/tests.log` | 5274 | `fdd22206a98ea2e2b8f35282a1f1f48093ef862b5139616d45cd84f6e79f3175` |
| `inputs-before.json` and `inputs-after.json` (each) | 135105 | `fc58767487f886cb5dac091d04c316525ce272dcdc30c5575bfe21bdbf11148b` |
| `cli-commands.json` | 3609 | `0e2c485596f19623dc9afc5805fc46489b6df7d9923e46141c4c4fbf5ad3bfdd` |
| `cli-audit.json` | 1514 | `e97c1cd7a86864a57ea5c3156514bb440af5fe4533e9b7ea232d857cf810a9f2` |
| `old13/jobs.jsonl` | 32970 | `75f4159d2872f0b9383b335c12705d254cf74f20e80b967f035770a6cfa28c01` |
| `old13/report.json` | 19581 | `d487b44d2adaa39b1541941dc91ebf3a6322fd41a381cf00783b1631498df354` |
| `new13/jobs.jsonl` | 33674 | `c2dd6cc746fdb94a819b51d9cff02ffe23578a7f00583b5dc80b5be50c7a7f8e` |
| `new13/report.json` | 20399 | `c2065254369507801c9995166e645fa092b27b0b3d49abcbc31b1508745a7fbb` |
| `actual273/jobs.jsonl` | 869622 | `1199009175b2de47c4a37f4f2c5a58531490fd2ea01e0ac0bb3837ece5629f02` |
| `actual273/report.json` | 708957 | `f44a1e72cbbd9d0752d7708234e77930f10eeec65a79a140ac1a14f6339ab404` |

`artifact-manifest.json` inventories every retained evidence file with its full
hash, size and mode (excluding itself and the later completion receipt to avoid
self-reference). Original and final source hashes are separately recorded in
`source-receipt.json`. No sibling results or root withheld reference outputs
were read. No native/browser/HTTP/network/app/save/SQL/preferences/install or
upgrade work occurred. No old8166-job corpus rerun, push, default merge or
history rewrite occurred. Worker/common/profile/client sources remain unchanged.

Next owner: root coordinator, for independent full typed reference comparison,
EOF/failure controls, preservation audit and separate integration decision.
This is a worker candidate, not `ready_for_user` or user acceptance. Nested
textures, rendering, game/quest/save behavior, the82world gaps and full-game
coverage remain open.
