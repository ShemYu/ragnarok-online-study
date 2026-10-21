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

**Metadata admission.** `check_profile` requires the exact task/policy, the six complete ordered native descriptors (name/base/path/bytes/full SHA)
(reader under `input_root`, then DATA.INI 0..4: the two 2026-08-25 GPFs, event, data0, data — an
experimental order, not publisher priority), `input_root` bases only (HOME is never looked up), the exact 22
ordered source paths (old 16 with only the prior profile path replaced, plus Ground.js and the .004
profile/manifest/worker/producer/summary), producer 48337 bytes `546ab293…ea89`, prior .005 profile 4649
bytes `c0dccf5d…7034` and the catalog pin. All 22 sources keep stable regular/single-link/no-symlink full byte/SHA
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
matching the frozen tuples. Diagnostic failure is checked before and after connect, GET, response headers, each streamed read and
each confirmed positive physical body write, plus final observations and cleanup. Received/stored prefixes
are charged before the post-operation guard; a diagnostic `Fatal` propagates through `transfer`. Requests are health,
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

- Candidate only; no live native run was performed by the worker. Root independently verifies the corrected driver and exact guarded invocation before execution.
- Python threads cannot cancel an arbitrary kernel-stalled regular-file syscall. Diagnostic writes assume
  ordinary private local storage returns; finite pauses/errors/EINTR are tested. A worker exceeding the
  shared join allowance remains incomplete, with its FDs retained and qualification false. The unchanged
  external guard remains necessary; neither the join nor guard establishes universal OS containment.
- T07 route: metadata preflight and fake I/O never touch the six native inputs or prove availability; the
  five-archive order, startup literal and cache fields are artifact observations, not source parity.
- Listener ownership is checked with `lsof` at readiness, after transport faults and before shutdown,
  not after every target; per-target liveness uses the owned `Popen.poll()`.
- Legacy route: native stdout/stderr are discarded, so startup/extraction diagnostics are not retained. Root's RSS
  guard is external and is not OS containment; the 24 MiB/64 MiB caps do not bound native inflation.
- Signature state is recorded only for complete stored 200 responses; it is a magic check, not parsing.

Rollback: `git revert` of the candidate commit. Private outputs live only under `.tools/renewal`.


## T07.007.006 repair candidate — 2026-10-21

Implementation-only repair on base `c884d8b9d15d658dce980901c1ee82d22a552879`, after unchanged selected
Claude integration `895a18f662e8fb0f0d6d9b288da80fd6cd759bb7`. This is separate from the completed
Claude/Grok comparison and is not coordinator verification or user acceptance. Dispatch
`task_abc9af01b76e` / `ctx_82057a34eab8` owns only this runbook, the driver and its tests. The source
uses the admitted root clarification (9560 bytes, SHA256
`02827bd87723f59a3f06aa87ce52c326250c7b5a57ef2f8096b677fcf28f96b6`); final-only staging is not used.

The two diagnostic workers reserve a prefix from one monotonic combined budget under a short lock,
then write outside it. Every positive physical write updates stored bytes, hash and startup framing;
unused reservation is never refunded after a fault. Startup readiness also requires no reserved write
in flight. The existing overflow assertion remains seen65/stored10. Reads are nonblocking with20ms
stop-aware polls; read/write EINTR is limited to16 consecutive interruptions. Lock acquisition has a
50ms ceiling bounded by the remaining phase/drain allowance, with a nonblocking error fallback.
One8s join allowance covers both workers, reserving its final1s for stop/join. EOF and cancellation are
reported separately. Output/source handles are removed from ownership only after the corresponding
worker is proved stopped; a later finish cannot close a stale numeric FD.

`Diagnostics.start` now creates/registers each unstarted `Thread` before the new narrow
`SystemOps.start_diagnostic_thread(thread)` hook. This hook replaces the former asynchronous factory
only on the T07 route. Existing `SystemOps.start_thread(target,name)` and all shared helper signatures,
including legacy `write_all`, remain unchanged. Root stand-ins injecting a diagnostic start failure
must use the new hook; a start-then-raise failure is explicitly tested. No generic runner is introduced.

Metadata rejects hardlinks at initial, opened and final admission, compares all six native descriptors
against fixed source values, and uses typed counts/policy/header/index relationships. The two exact
profile descriptors and all frozen input/source pins remain unchanged. Decimal startup counts longer
than10digits are retained as malformed observations with null counts, without an unbounded integer
conversion; all five association records still publish on failure. Operation failures are recorded
before response/connection/file closers; later cleanup/publication/diagnostic faults remain separate,
bounded generic codes. Listener/group observation failures do not suppress exact-child TERM/wait or
other independent cleanup observations. No group or foreign-PID signaling is added.

Verification commands use the two input roots shown above, `PYTHONDONTWRITEBYTECODE=1`, and no HOME
in the final subprocess environment. Private stdout/stderr and the machine-readable receipt are under
`.tools/renewal/t07-007-006-repair-verification-1` in this child (0700/0600). The final receipt records
exact argv, exit codes, elapsed time, output/source hashes and the OS child high-water mark; that is
not sampled combined driver/native RSS. The worker does not run root private controls/oracles or the
external scan guard and does not claim their results.

The85test methods comprise all69original selected methods plus16repair methods, with no skips.
AST comparison confirms every original test body is unchanged; only T07 fake thread-start plumbing
moves to the registered-worker hook. New finite controls cover30native-field mutations, typed policy/
counts/header/index refusals, a physical hardlink, partial reserved cap/hash evidence, six synchronized
HTTP phase stops, storage-before-close ordering, three independent cleanup-observation faults,
5000-digit startup count failure, start-then-raise and output-fchmod ownership, delayed-writer lock
access, held-open pipe cancellation,16-read/16-write EINTR exhaustion, post-write deadline, bounded
lock timeout and close-once behavior. The delayed-writer test has a2s fallback and finally release;
it observes the live FD retained before release, joins the worker, and checks ownership before deleting
its fixture. The original first-write zero/error and later-startup-write failure controls require zero GETs.

Final worker results: **85/85 tests, zero skips**, unittest14.135s / subprocess wall14.568904s.
Legacy metadata preflight exits0 in1.105906s; new311-target metadata preflight exits0 in0.211481s;
canonical legacy drift refuses exit2/`admit_size` in0.201203s. All44admitted metadata files retain
identical complete before/after identity/size/SHA receipts. The verification process observes an OS
child high-water mark of807862272bytes (not a native/combined sample). The final driver is112136bytes,
SHA256`0e691c1e93b726cf2819f473745864469d7c2c49aebe89c0b4115f2bd7722750`; tests131582bytes,
SHA256`e4ce441a78cda18fc67e0fbe027b5f37b55569e88c8f5ee9ae009dc9e57bbc09`.
Private `receipt.json` SHA256`dd9b0d5dd1606f33ee7c2e3433f1becb32b2672d7978025f7559b6248fee3221`.
All earlier failing runs concerned the implementation/fixture corrections described above; these are
final candidate results, without any claim of root control, guard or native-scan qualification.

The root coordinator is the next owner: read this candidate, personally rerun the common retained and
private controls (including the new start hook), qualify exact guarded invocation and full output, then
consider the actual311-target scan. No native/archive/body input, actual HTTP/service, app/world/save,
OS settings, build/install, sibling .007 work, publication or default-branch merge was performed.
The full Modern/Renewal goal,82world gaps and all downstream render/play/story acceptance remain open.
Rollback is a separate source revert; this repair changed no original game state.
