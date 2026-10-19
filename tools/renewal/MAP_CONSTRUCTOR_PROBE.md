# Map constructor probe (T06.003.003.003)

Runs the unmodified pinned client constructors `new World(buffer)`, `new Ground(buffer)` and
`new Altitude(buffer)` on finite inputs and records the frozen common
`summarizeConstructor(kind, value)` projection. A returned constructor is an observation only.
It does not prove format validity, a complete episode, rendering or playable coverage.

Frozen task: [T06.003.003.003](../../docs/project/tasks/T06.003.003.003.md). Profile pin
`b6635a65…74cf5c`; common summary `33cdb4ce…6ddf1`; authored fixtures `fa5711ba…4cf5c`.

## Files

- `probe_map_constructors.mjs`: CLI/parent. Pins, input admission, lower-only policy, one worker at a time, RSS sampling, deadlines, settlement and output.
- `map_constructor_worker.mjs`: one `worker_threads.Worker` per job. It creates a fresh VM context and a closed `SourceTextModule` graph from the nine verified source texts plus a fixed entry that imports World, Ground and Altitude.
- `test_probe_map_constructors.mjs`: runner controls.

## Use

Node builtins only; no installation or build step.

```sh
node --experimental-vm-modules tools/renewal/probe_map_constructors.mjs \
  --input-root /canonical/repository \
  --client-source /canonical/repository/.tools/renewal/client-source \
  --profile docs/project/fixtures/T06.003.003.003-profile.json \
  --fixtures docs/project/fixtures/T06.003.003.003-authored.json \
  --output /own/checkout/.tools/renewal/fresh-output
```

Corpus mode replaces `--fixtures` with `--manifest /canonical/repository/.tools/renewal/t06-map-parse-preparation-1/combined-parser-input-1.json`.
That path must equal the input root joined with `profile.manifest.path`. Exactly one mode is required.

Lower-only overrides are `--job-timeout-ms`, `--run-timeout-ms`, `--rss-limit-bytes`,
`--max-job-json-bytes` and `--max-jobs N` (0..total). A value above the profile is refused.
Stdout is one bounded JSON summary line. Exit codes:

- `0`: complete observation with every started worker's exit positively observed. Observed constructor exceptions still count as complete.
- `1`: incomplete, with explicit accounting. Causes are timeout, resource, input, environment, worker, output or cleanup trouble, `--max-jobs` truncation, or a pin identity change after the run.
- `2`: refused before output was created. Causes are usage, profile, pins, links, policy or existing output.
- `3`: an unexpected I/O/publication failure prevented a complete artifact. Owned sampler/descriptors are cleaned; partial diagnostic output is not an accepted report.

Tests (read-only use of the canonical client source; temp state lives below this checkout's
`.tools/renewal/t06-constructor-candidate-1/test-tmp-*` and is removed afterwards):

```sh
T06_INPUT_ROOT=/canonical/repository \
  node --experimental-vm-modules --no-warnings --test tools/renewal/test_probe_map_constructors.mjs
```

## Execution and admission rules

- The profile is pinned by SHA in code. Summary, fixtures or manifest, and all nine sources are read in full under a byte bound. Every one must be a regular file on a fully link-free path (`resolve == realpath`), opened with `O_NOFOLLOW | O_NONBLOCK`. The full opened identity and size are checked before allocating or reading. Size and SHA must match, and dev/ino/size/mtime/ctime must be unchanged across lstat, open, read and relstat. Identity is checked again after the run.
- In corpus mode each body is `job.body_path` under the input root. The path must be relative with no `.`, `..`, empty or backslash segments. It gets the same regular-file, link and identity checks, and its exact bytes and full SHA are verified before the worker starts. A failure is recorded as `input_refused` and the run continues. Fixture mode opens no retained bodies.
- The closed linker accepts only the nine profile keys. Bare `Utils/…` or `Vendors/…` specifiers resolve under `src/`, and relative ones resolve against the referrer. Unknown, escaping, URL and dynamic imports are refused. The VM sets `self = globalThis`, so the BinaryReader `SEEK_*` constants become actual VM globals. Code generation from strings and wasm is disabled.
- The VM gets no `process`, `require`, `Buffer` or network API. Its only addition is a VM-defined bounded `console`. `SourceTextModule` is an execution adapter, not a security or memory sandbox.
- The body is copied into an exact-length ArrayBuffer created in the VM realm and passed straight to the constructor. There is no parser rewrite, format validation, version allowlist or `compile` call.
- The summary module runs from its verified bytes, through a `data:` import in the worker host realm, on the returned object before JSON serialization. A summary throw becomes `summary_error` and exits nonzero. The parent caps the complete serialized job row, including metadata and logs. A result that does not fit becomes `summary_limit`, with no summary written; dependency lists are never truncated and labeled complete. A cap too small for mandatory accounting refuses before output creation.
- Limits: worker `maxOldGenerationSizeMb` 512. Whole-process RSS is sampled at each worker start and then every 50 ms. VM limits are 5 s for module evaluation and 10 s for the constructor, each capped by the remaining job deadline. The job wall is 20 s, capped by the run deadline (15 min).
- A timeout, Worker error, unexpected nonzero exit or observed RSS failure stays latched; a later result cannot restore success. RSS remains enforced after a result and before worker exit. Once RSS exceeds its bound, later jobs are unattempted.
- On a result, a worker gets a 2 s natural-exit grace and is then terminated. On a timeout or RSS refusal it is terminated at once. The next job starts only after the worker's `exit` event is observed. If exit is not observed within 10 s, the runner halts as `cleanup_unverified` and does not retry or start a duplicate worker.
- Each pending job gets reserved `jobs.jsonl` space: its unattempted row plus 4096 bytes. If a full row would eat into the reserve, it is written without summary or log (`limit: max_jobs_jsonl_bytes`) and the remaining jobs become `unattempted/output_limit`. Logs are capped at 4096 bytes per job and 65536 in total. Exception messages are capped at 512 characters.

## Output

The output directory must be a fresh path below this checkout's `.tools/renewal/`. Every existing output ancestor is checked for links before parent creation and again afterwards. The output directory must not already exist. It is created with mode 0700, and its files are created exclusively with mode 0600.

- `jobs.jsonl` has one row per expected job, in input order. Each row has `id`, `kind`, `complete_sha256`, `input_bytes`, `header_version_bytes`, `outcome`, `constructor_returned`, `elapsed_ms`, `worker_started` and `cleanup.exit_observed`. Optional fields are `exit_code`, `terminated_by_parent`, `phase_reached`, `exception{phase,name,message}`, `reason`, `summary`, `summary_json_bytes`, `limit` and `log`. Fixture `header_version_bytes` are bytes 4–5; corpus values come from the manifest.
- `report.json` uses schema `T06-map-constructor-report-1`. It records the mode, the input path, bytes and SHA, the profile and summary SHAs, the verified source pins, the effective policy, `counts.job_outcomes`, RSS observations, cleanup state and `jobs_file{path,bytes,sha256,records}`.
- In fixture mode, `roots` is `[]` and an `authored_comparison` is included.
- In corpus mode, `roots` is the full manifest roots array, deep-copied with every field. Each edge gains `parse_outcome` from its linked job, or `unavailable_from_observation` when `job_id` is null. The original `parse_status` is kept as provenance, and manifest counts and gaps appear separately under `input_manifest`.
- If the report would exceed 8 MiB, the roots are omitted with an explicit `report_limit` and the exit code is 1.

## Historical raw candidate results (2026-10-19, Claude child, base 8320de8)

- Tests: 12/12 pass, zero skips.
- Fresh fixture CLI: exit 0, 26/26 authored matches (17 returned with full dictionary equality, 9 expected constructor exceptions by name). 26 workers started and 26 exits were observed, in about 0.7 s. Peak sampled RSS was about 80 MB.
- The tests also exercise these controls: existing output, profile pin and symlink refusal, symlinked sources, lower-only caps, `--max-jobs 3` (23 unattempted rows), a real 1 ms job timeout with terminate and observed exit, run-deadline halting, RSS refusal, `summary_limit`, the closed linker, and synthetic corpus admission and edge mapping.
- Source hazards observed with the real pinned constructors:
  - A host-realm ArrayBuffer throws `Error: BinaryReader() - Undefined buffer type` (cross-realm `instanceof`).
  - A same-realm `Uint8Array` with `byteOffset` 7 is read from the start of the underlying buffer, which gives `Invalid header "AAAA"`.
  - An exact same-realm copy returns and its summary equals the authored value.
  - These are source/adapter hazards, not evidence of bad retained content.

## Root corrections and final verification

Selected raw Claude source was integrated unchanged as26ba921 after root's
independent same-input comparison with Grok. Neither raw runner qualified
unchanged. Root separately corrects opened-file bounds, output ancestors,
complete-row caps, failure precedence and publication/cleanup. Positive short
writes retry at explicit positions; zero progress refuses promptly. A transient
jobs-write failure rolls back its partial record, writes truthful failure state
with one bounded accounting attempt and leaves later jobs unattempted. A
persistent storage failure exits nonzero after cleanup; it cannot guarantee a
complete report on unwritable storage.

Final verification and provenance are recorded in the
[task review](../../docs/project/reviews/2026-10-19-T06.003.003.003.md).
Raw results above remain historical; use the review's latest integrated check
for readiness. No installed app/game/save/network state is changed by this tool.

## Limitations

- The retained corpus (2761 jobs) was not run by this candidate. Root admits and runs it.
- The `jobs.jsonl` overflow and `report.json` overflow paths, the VM-internal module and constructor timeouts, and worker heap OOM are implemented but not exercised: no lower-only cap exists for them, and the authored inputs are too small to trigger them.
- RSS is sampled, so a short spike can be missed. V8 heap limits do not bound typed arrays or native memory.
- The client-source git revision is recorded from the profile, not independently checked. The nine content SHAs are verified.

## Rollback

This adds four source files only. Revert the commit that introduced them (`git revert <commit>`).
Private outputs live under the ignored `.tools/renewal/`. Delete the owned
`t06-constructor-candidate-1/` directory to remove them. No installed, game, database or settings state is touched.
