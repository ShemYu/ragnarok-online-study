# First-level map dependency observation (T06.003.003.005)

Root-operated driver for the [frozen brief](../../docs/project/tasks/T06.003.003.005.md). It observes the
exact literal HTTP availability and fixed magic prefix of every first-level model / ground-texture
target in the qualified .004 catalog (11134 targets, 63557 referrers, all 1296 roots and 82 gap
roots retained). This is availability evidence only: no RSM parsing, nested textures, decode, render,
playable-map, monster, story or full-content proof.

Stdlib Python only. Profile SHA `c581255b…89f5` is pinned in the driver; the profile pins the catalog,
authored controls, 16 rule sources and the four native inputs.

## Commands

```text
python3 tools/renewal/observe_map_dependencies.py --preflight \
 --input-root /canonical/repository \
 --profile docs/project/fixtures/T06.003.003.005-profile.json
python3 tools/renewal/observe_map_dependencies.py --execute \
 --input-root /canonical/repository \
 --profile docs/project/fixtures/T06.003.003.005-profile.json \
 --output /own/checkout/.tools/renewal/fresh-output \
 --root-reviewed-sha256 EXACT_DRIVER_SHA256
python3 -m unittest discover -s tools/renewal -p test_observe_map_dependencies.py
```

- `--preflight` reads only profile/authored/catalog/rule-source metadata with stable admitted reads,
  validates the whole catalog (schema/task/mode/.004 binding, expected counts, root/gap order, root
  edge ↔ job references, loader ↔ target ↔ referrer bidirectionality, filemanager agreement,
  UTF-8 per-segment reconstruction of every `http_path`, kind/role, `wire_target`) and prints one JSON
  line with counts and `native_qualification: null`. It never opens/stats native inputs, launches a
  process or creates a socket. Exit 0.
- `--execute` (root only) first requires the exact own-source SHA, then admits a fresh output under
  this checkout's `.tools/renewal` with ≥8 GiB + 4 GiB free, writes `catalog-input.json` byte-for-byte,
  prefills all 11134 records in `report.json`, full-hashes the native inputs, writes `resources/DATA.INI`
  (event.grf → data0.grf → data.grf), launches only the pinned binary as one new-session `Popen` child
  (minimal 17-variable environment, DEVNULL stdio, child umask 077), proves PGID = PID and the exact
  owned `127.0.0.1` listener, performs one health GET and at most one GET per target in catalog order,
  then terminates only the owned child and audits cleanup, native/source drift, `logs/missing-files.log`
  and the strict output tree.
- Refusals (usage, pins, metadata, output admission) exit 2 before output creation. Execute failure
  exits 1 and retains observations; failed final publication also exits 1. Output is bounded JSON with
  generic codes only; no paths, names or exception text.

## Shared functions (all used in production)

- `wire_target(http_path)` — `/` + unchanged encoded ASCII path; generic `ValueError` otherwise.
- `write_all(fd, data, write_fn=None)` — physical full write; zero/invalid/overlarge progress raises
  `OSError` without retry; EINTR retries. Used for every body, INI, catalog copy and checkpoint.
- `transfer(response, fd, *, body_cap, aggregate_left, deadline, clock=None, write_fn=None)` — exact
  precedence (framed zero, declared over cap, deadline, aggregate, body cap, ≤64 KiB read), no EOF
  lookahead at an unframed cap, `late` from the final clock. Storage errors propagate; the production
  caller counts wire bytes via a metering proxy so received bytes survive a storage failure.
- `inspect_signature(kind, prefix)` — GRSM/GRSX (6 bytes), BM (2), FFD8 (2); prefix only.

## Gap versus fatal

Per-target gaps continue: 404, other HTTP, redirect, empty/HTML 200, unsupported encoding, oversized
header, declared/unframed cap, framed truncation, read/transport error, I/O timeout and connection
setup failure (attempt consumed, no wire claim). Fatal halts retain the untouched suffix with the halt
reason: acquisition deadline (including a late final read, which stays `complete`), aggregate cap
(health bytes included), reader loss, storage/publication failure, health failure, native drift or
internal failure or uncertain HTTP-resource close. Exit 0 requires all targets attempted, valid health, postchecks, log, tree and a
proven clean exit 0 with no forced kill, listener or group residue.

## Coordinator corrections

The selected Claude submission is preserved unchanged as integration `258585d`.
The separately attributed root correction rejects invalid initial framing before
I/O; retains complete-wire evidence across storage failure; counts confirmed
health and partial-file storage; and reports an unknown stored-byte total as
null. HTTP close uncertainty disqualifies acquisition. An observation error
still permits termination of the owned child, without claiming clean shutdown.
Startup and final acquisition proofs check the clock after listener queries.
The missing-file audit uses observed404status independently of body transfer.
Driver postchecks compare the full identity receipt, as for the other inputs.
Partial bytes from an HTTP IncompleteRead remain in received-byte accounting.

Failed final publication always exits1 and clears in-memory qualification. One
bounded recovery publication attempts to retain that failure; a persistent
publication failure cannot guarantee a rewritten on-disk receipt. Root requires
both positive exit status and independently audited evidence before acceptance.
The11new regression methods reject the original source and pass the corrected
source; see the [root review](../../docs/project/reviews/2026-10-20-T06.003.003.005.md).

## T07.007.006 second route (four-map subset)

Candidate source for the [frozen brief](../../docs/project/tasks/T07.007.006.md). One exact second trusted
descriptor is added; the route is selected **only** by the profile's trusted byte length and full SHA-256
(`T07.007.006-profile.json`, 9680 bytes, `0615c6d9…5db5c6`) before any profile content is believed. A
same-size different-SHA profile refuses `profile_pin`; a larger one refuses `admit_limit` before allocation.
The legacy descriptor (7258 bytes, `c581255b…89f5`, producer pin 31720 bytes `12f5a315…897f`) is unchanged;
neither producer is accepted by the other route.

```text
OBSERVE_INPUT_ROOT=CANONICAL_REPO/.tools/renewal/t07-007-006-legacy-metadata-1/snapshot \
OBSERVE_NEW_INPUT_ROOT=CANONICAL_REPO \
 python3 -m unittest discover -s tools/renewal -p test_observe_map_dependencies.py
python3 tools/renewal/observe_map_dependencies.py --preflight \
 --input-root CANONICAL_REPO/.tools/renewal/t07-007-006-legacy-metadata-1/snapshot \
 --profile docs/project/fixtures/T06.003.003.005-profile.json
python3 tools/renewal/observe_map_dependencies.py --preflight \
 --input-root CANONICAL_REPO --profile docs/project/fixtures/T07.007.006-profile.json
```

Both test variables default to the canonical checkout layout and never bypass CLI pins. Old preflight
against the canonical root refuses (`admit_size`, integrated .005 producer drift) — expected evidence.

**Metadata admission.** `check_profile` requires the exact task/policy, the six ordered native names
(reader under `input_root`, then DATA.INI 0..4: the two 2026-08-25 GPFs, event, data0, data — an
experimental order, not publisher priority), `input_root` bases only (HOME is never looked up), the exact 22
ordered source paths (old 16 with only the prior profile path replaced, plus Ground.js and the .004
profile/manifest/worker/producer/summary), producer 48337 bytes `546ab293…ea89`, prior .005 profile 4649
bytes `c0dccf5d…7034` and the catalog pin. All 22 sources keep stable regular/no-symlink full byte/SHA
admission; the .005 profile, .004 profile and manifest are parsed as data, never executed.
`validate_catalog_t07` checks the exact catalog key set, schema/task `T07.007.005`/mode, `profile_sha256`,
ordered `input_pins` (report.json/jobs.jsonl/constructor_manifest), constructor task/worker/producer,
`constructor_profile_sha256`, `summary_sha256`, all three rule sources and limitations against the .005
profile; ties those sub-pins to the descriptor's source pins; binds the .004 profile and manifest
(task/counts/gaps); validates every ordered job against its manifest row (id/kind/body hash/input
bytes/header version, `outcome: returned`, `constructor_returned is True`); and compares the roots
order-sensitively with the manifest roots plus each linked job's `parse_outcome` (scope, null original
ordinal/status and `parse_status: not_run` preserved). The shared graph validator then enforces root-edge ↔
job references, loader ↔ target ↔ referrer bidirectionality, occurrence indexes, FileManager agreement,
UTF-8 HTTP reconstruction and `wire_target`; counts equal the profile's full `expected_counts`
(4 roots/12 jobs/311 targets/337 referrers/273+38 distinct names) and the census is 174 rsm2/99 rsm/38 BMP.
Manifest `body_path` strings are never followed.

**Execute (root only).** Evidence (`catalog-input.json`, `report.json`, six-digit bodies,
`native-stdout.log`, `native-stderr.log`) stays in the fresh output; the fresh 0700 `server/` is native cwd
and `SERVER_ROOT` and holds only `resources/DATA.INI` (canonical absolute archive paths) plus a justified
`logs/missing-files.log`. The 16-variable environment has `NODE_ENV=development`, zero caches, no HOME and
no `GRF_FILENAME_ENCODING`. The 25 s startup clock starts immediately before `Popen` and is checked after
`getpgid`, drainer start, the launch checkpoint and every listener/diagnostic observation. Pipes are adopted
right after `Popen`; drainer threads retain at most 16 MiB combined, preserve LF framing across chunks and
require exactly five ordered `  Valid GRF: PATH (version V, N files)` lines (two leading spaces; one stream)
matching the frozen tuples. Diagnostic failure is checked before connect, after headers and after each
transfer, and again after cleanup, so a late failure sets `diagnostic_failure`. Requests are health,
cache-stats, the 311 assets, cache-stats (≤314, cap enforced). Health requires `version` `1.0.5`; each cache
observation requires integer `index.grfCount=5`, `cache.size=0`, `cache.maxSize=0` (bool/float/string/null
refused) and records the other fields as observations. A clock check follows each final metadata parse.
Report adds `cache_before`/`cache_after`, `health.version_ok`, `totals.cache_attempts`,
`startup_archive_counts`, `diagnostics`, `server_tree`/`evidence_tree` (both required by `tree.valid`) and
`retained_postverify` (full receipt re-admission of the catalog copy, INI, every body and both diagnostic
files). Exit 0 additionally requires all of these.

**Shared corrections (both routes).** A storage `Fatal` during the health body previously left a bytes
`_prefix` in the record, so the halt checkpoint raised and skipped owned-child cleanup; the prefix is now
always removed and a non-`Fatal` halt-checkpoint error is recorded as `publication_failure` before cleanup.

**Tests.** All 42 legacy methods (16 wire/11 transfer/10 signature/3 write authored cases and the 11 root
regressions) run unchanged on the legacy snapshot. New: descriptor/route/cross-substitution refusals,
whole-catalog/.005/.004/manifest corruption, forbidden native/body/process/socket/thread/output/HOME
sentinels on the new preflight, a production-method fake scan of all 311 records with both cache
observations, 404 continuation versus fatal suffix, health/cache failures, inclusive byte/attempt/
invocation caps, late final cache/EOF, short/EINTR/zero/bool writes, connection/close/input/body drift,
failed publication, split-root placement faults, and diagnostics overflow/short/zero/error writes,
unterminated/duplicate/extra lines, source-close failure, startup version/count/order/path/stream
mismatches, delayed after-`Popen` setup and drainer start failure, each with FD/thread leak inspection
before fixture deletion. Tiny stand-in native files and pipes live only under ignored private fixtures.

## Limitations

- Candidate only; no live native run was performed by the worker. Root executes the selected driver.
- T07 route: metadata preflight and fake I/O never touch the six native inputs or prove availability; the
  five-archive order, startup literal and cache fields are artifact observations, not source parity.
- Listener ownership is checked with `lsof` at readiness, after transport faults and before shutdown,
  not after every target; per-target liveness uses the owned `Popen.poll()`.
- Legacy route: native stdout/stderr are discarded, so startup/extraction diagnostics are not retained. Root's RSS
  guard is external and is not OS containment; the 24 MiB/64 MiB caps do not bound native inflation.
- Signature state is recorded only for complete stored 200 responses; it is a magic check, not parsing.

Rollback: `git revert` of the candidate commit. Private outputs live only under `.tools/renewal`.
