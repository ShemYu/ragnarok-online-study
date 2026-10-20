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

## Limitations

- Candidate only; no live native run was performed by the worker. Root executes the selected driver.
- Listener ownership is checked with `lsof` at readiness, after transport faults and before shutdown,
  not after every target; per-target liveness uses the owned `Popen.poll()`.
- Native stdout/stderr are discarded, so startup/extraction diagnostics are not retained. Root's RSS
  guard is external and is not OS containment; the 24 MiB/64 MiB caps do not bound native inflation.
- Signature state is recorded only for complete stored 200 responses; it is a magic check, not parsing.

Rollback: `git revert` of the candidate commit. Private outputs live only under `.tools/renewal`.
