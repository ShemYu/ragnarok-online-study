# Model constructor probe (T06.003.003.006)

Runs the unmodified pinned client constructor `new Model(buffer)` and records the frozen common `summarizeModel(value)` projection, including declared nested texture names. A returned constructor is an observation only. It does not prove format validity, a texture fetch, rendering, or playable coverage.

Frozen task: [T06.003.003.006](../../docs/project/tasks/T06.003.003.006.md). Profile pin `9ad90329…b2140d`; common summary `ec51b8b2…e13d5c`; authored fixtures `f64315a2…876fa3`.

Preserved denominators from the pinned profile: 8194 model targets, 8166 byte-distinct jobs, 48980 model referrers, 1296 roots, 82 remaining core-gap roots, 63557 catalog referrers. Header prefix counts are observations, not a version allowlist. The two missing ground textures stay outside this probe.

## Files

- `probe_model_constructors.mjs`: CLI/parent. Pins, admission, lower-only policy, one worker at a time, RSS sampling, monotonic deadlines, settlement, and output.
- `model_constructor_worker.mjs`: one `worker_threads.Worker` per job. Fresh VM context and a closed `SourceTextModule` graph of the seven pinned modules, plus a fixed entry that imports Model only.
- `test_probe_model_constructors.mjs`: runner controls. Fixture execution only.

## Use

Node builtins only. No installation or build step.

```sh
node --experimental-vm-modules tools/renewal/probe_model_constructors.mjs \
  --input-root /canonical/repository \
  --client-source /canonical/repository/.tools/renewal/client-source \
  --profile docs/project/fixtures/T06.003.003.006-profile.json \
  --fixtures docs/project/fixtures/T06.003.003.006-authored.json \
  --output /own/checkout/.tools/renewal/fresh-output
```

Corpus mode replaces `--fixtures` with `--manifest` and the input root joined to `profile.manifest.path`. Exactly one mode is required. Unknown or duplicate flags are refused.

Lower-only overrides are `--job-timeout-ms`, `--run-timeout-ms`, `--rss-limit-bytes`, `--max-job-json-bytes`, and `--max-jobs N` (0..total). A value above the profile is refused. Stdout is one JSON line of at most 4096 bytes and does not carry paths, names, or bodies.

Exit codes:

- `0`: complete bounded observation. Every started worker's exit was observed, and normal `returned` / `constructor_exception` rows exited 0 without parent termination. Inventoried constructor exceptions still count as complete.
- `1`: incomplete, with every expected job id retained. Causes include timeout, resource refusal, input or summary failure, worker lifecycle, publication, source drift, or intentional truncation.
- `2`: refused before output was created.
- `3`: an unexpected failure outside a `Refusal`.

Tests, using the canonical client source and temp state under this checkout's `.tools/renewal/t06-model-constructor-candidate-1/`:

```sh
T06_INPUT_ROOT=/canonical/repository \
  node --experimental-vm-modules --no-warnings --test tools/renewal/test_probe_model_constructors.mjs
```

## Execution rules

- Profile, common summary, the selected fixture or manifest, seven modules, three request-rule sources, and the owned parent/worker sources are read in full before execution and checked again afterwards. Reads use `lstat`, `open` with `O_NOFOLLOW | O_NONBLOCK`, `fstat`, a full read, `close`, and `lstat` again. Symlinks, special files, extra links, traversal, and changed identity are refused. Source inputs are not chmodded.
- Fixture mode does not open retained model bodies, the availability report, or the catalog. Corpus mode checks the pinned report, catalog, and root audit, then full-hashes every admitted body before deduplicating. Only complete byte-equal bodies share a job. The representative is the first target. `model_ordinal` stays distinct from catalog `target_index`.
- The closed linker accepts only the seven profile keys. The VM sets `self = globalThis`, so `SEEK_CUR/SET/END` are 1/2/3. There is no `process`, `require`, `Buffer`, DOM, or network API in the client realm. The body is copied into an exact-length same-realm `ArrayBuffer`. `SourceTextModule` is an execution adapter, not a memory sandbox.
- `summarizeModel` runs from the verified summary bytes before JSON serialization. `SummaryLimitError` becomes `summary_limit` and does not keep a truncated summary. Constructor exceptions stay distinct from summary and worker failures.
- One worker runs at a time. A normal `returned` or `constructor_exception` result must then exit 0 without the parent calling `terminate`. Any result followed by an error or a nonzero exit stays a failed lifecycle row, with `prior_result` holding the earlier fact and no successful summary. After the 2s result-exit grace the parent may terminate that worker and waits up to 10s. Unknown cleanup halts later jobs. There are no retries.
- Output is a fresh `0700` directory below this checkout's `.tools/renewal/`. Files are created `0600`. `jobs.jsonl` reserves room for every remaining id. `report.json` is published through a private exclusive temporary file; a qualified directory has no temporary file. Publication failure exits 1 and does not claim a qualified report.

## Candidate results (Grok, base 2f8644bd)

Commands run from this checkout on 2026-10-20:

- `node --experimental-vm-modules --no-warnings --test tools/renewal/test_probe_model_constructors.mjs`: 19 tests, 0 failures, about 2.0s.
- Fresh fixture CLI: exit 0, status `complete`, 13/13 authored matches. Nine `returned` rows matched the full expected summaries. Four `constructor_exception` rows matched `Error`, `RangeError`, `RangeError`, and `TypeError` by name. All 13 workers exited 0 and were not parent-terminated. `SEEK` was `[1, 2, 3]`. Elapsed about 378ms inside the report. Peak sampled RSS was 81395712 bytes over 21 samples. No RSS guard action. Output was `jobs.jsonl` and `report.json` only, modes `0600` under a `0700` directory.

The same test file also checked existing output, profile pin, symlink, fifo, output-ancestor link, lower-only and duplicate flags, `--max-jobs 0` and `--max-jobs 2` suffixes, a real 1ms job timeout with observed termination, run-deadline and RSS suffixes, summary/output caps, source drift, closed linker, synthetic corpus admission (including a shared byte-equal pair and decimal nanosecond identity), representative/body drift, result-then-nonzero and never-exit workers, short writes, zero-progress publication, and opened-file growth. Importing the parent did not start a worker.

Cross-realm `ArrayBuffer` throws `BinaryReader() - Undefined buffer type`. A same-realm `Uint8Array` with a byte offset is read from the underlying buffer start and throws `Error` on the header. An exact same-realm copy matches the authored summary. Those are adapter hazards, not evidence of bad retained content.

## Root corrections after the raw comparison

Root independently ran both raw 8166-job corpora: all8165 returned summaries
matched and both observed the same constructor exception. See the
[comparison and repair selection](../../docs/project/reviews/2026-10-20-T06.003.003.006.md#root-score-and-repair-basis-selection).
The raw implementations scored14/20each. Grok was selected as a repair basis,
then integrated unchanged as c4b2258; these subsequent fixes are root work.

- VM timeout options use positive integer remaining budgets. An exhausted
  budget before invocation is a timeout, not an invented constructor exception.
- Parent settlement rechecks the monotonic deadline on exit, including exit0
  after a timely result. The earlier result remains visible as `prior_result`.
  The whole-run budget starts before input admission.
- Final checks fully reread/hash/identity-check every admitted input, module,
  rule and own source. `source_postchecks` records expected/checked/failures;
  source/rule identities and protected input receipts remain in the report.
- Failed initial checkpoints start no workers. `expected_job_ids`,
  `expected_target_ids` and `job_accounting` preserve all IDs and execution
  facts independently of durable JSONL rows. Accounting omits summary/log
  payloads; full successful summaries remain in JSONL. Outcome totals cover
  accounting, while `counts.records` counts written rows.
- A partial row is retried only after confirmed truncation to its prior size.
  Uncertain rollback stops JSONL writes, sets `storage.jobs_tail_uncertain`,
  and leaves whole-file bytes/SHA null with a separately labeled
  `confirmed_prefix`. Close failures prevent qualification. Exclusive report
  temporary names receive bounded cleanup without retrying an ambiguous close.
  Every final/deadline/failure publication attempt observes the report cap.

Root verification at this source checkpoint:29tests/zero failures/zero skips,
including ten added regression tests; a separate fresh production fixture CLI
exits0 with13matches. Real fixture execution and explicitly labeled synthetic
lifecycle/storage controls are distinguished in the tests. Integrated retained
corpus/root comparison is still required before task readiness. Constructor
exceptions, nine raw numeric-marker models, earlier core/ground gaps and
render/play/full-game verification remain open.

## Limitations

- This candidate did not execute corpus mode and did not read retained model bodies. Root admits and runs the 8166 jobs.
- Worker-heap exhaustion and the VM's own module/constructor timers are implemented. The lower-only CLI does not expose separate caps for them, so these specific paths were not forced. Healthy lower1000/10000ms jobs, real parent timeout, delayed exit and admission-budget exhaustion are separately checked.
- RSS is sampled. The heap limit does not contain typed arrays or native allocations.
- The client-source git revision is copied from the profile and is not checked against a git object. The seven content SHAs and three rule-source SHAs are verified.
- Cursor/tail remains `not_observable_from_unchanged_constructor`. Declared texture names are not GET counts.

## Rollback

Revert the commit that added these four files (`git revert <commit>`). Private outputs live under the ignored `.tools/renewal/t06-model-constructor-candidate-1/` directory; delete that directory to remove them. No installed app, game, database, or settings state is touched.
