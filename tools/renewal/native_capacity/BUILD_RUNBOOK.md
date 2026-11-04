# T10.010.003 — reproducible native source and bounded map-server build

Claude candidate (blinded pair). Base `a06f1037ac6ecf308db6a963e06391ebbf586cbd`,
brief `docs/project/tasks/T10.010.003.md` (SHA-256 `7bd1791f…a5a3f8`).

| Revision | Content |
| --- | --- |
| `06d6f36` | Initial candidate. Root verified the source reconstruction and did not admit build execution. |
| `1b0508c8` | Fixes Root's P1/lifecycle findings, adds owner checks and closed-tree checks |
| `7e5135b0` | Consistent base+delta dependency model, cancellation-safe create/import, output-root link check |
| repair 3 (this revision) | `import_check` preserves ownership detail when the body fails and cleanup also fails |

**Status: selected and integrated; Root verifies preparation/recipe scope.**
See [Root's selection, actual tests and remaining runtime gates](../../../docs/project/reviews/2026-11-04-T10.010.003-root.md).
Historical worker results below retain their original scope.
The subsequent [actual personal Root resource probe](../../../docs/project/reviews/2026-11-04-T10.010.004-root.md#actual-personal-probe-and-save-preservation)
passes cgroup/mount/limit readback, bounded archive/lifecycle, save preservation
and cleanup404. Its 1.20 GiB available memory refuses the unchanged 1536 MiB
compiler plus 768 MiB reserve gate. Attributed stats establish balloon-held
RAM. [Root's separate 4 GiB build VM](../../../docs/project/reviews/2026-11-04-T10.010.004-root.md#actual-build-only-vm-characterization-passes)
subsequently passes local image/ownership/cgroup/cleanup and the unchanged
headroom gate with3.61 GiB available; it is stopped. The later
[actual dependency attempt](../../../docs/project/reviews/2026-11-04-T10.010.004-root.md#actual-dependency-failure-and-next-diagnostic)
fails on an APK trigger error after selecting four base upgrades. Its owned
container is removed and VM stopped; no closure/full build is qualified.
Dependencies and compiler/export/binary qualification remain pending; do not
interpret the historical fake-only results below as current runtime coverage.
- Source preparation was executed and checked on the host.
- The implementation's host/fake-Engine checks pass. Its actual Engine path
  now runs resource probes and one failed dependency transaction; the full
  compilation/export/import paths remain unqualified.
- **No full map-server build or new game image/binary is qualified.
  T10.010.003 is self-verified for implementation; .004 remains unqualified.**

## Files (all under `tools/renewal/native_capacity/`)

| Path | Role |
| --- | --- |
| `source_manifest.json` | Repository/commit/tree pins, app semantics blob pins, ordered steps, fuzz allowlist, prepared-tree digest, crash-fixture pin, footprint file |
| `source_footprint.json` | The 101 overlay paths (72 added, 29 modified, 0 removed), each with its prepared-bytes SHA-256 |
| `prepare_source.py` | `fetch` / `prepare` / `verify` / `reference` / `reconcile` / `footprint` |
| `build/guest_build.sh` | Guest main: checks, then dependencies, then unpatched + patched renewal `map-server` |
| `build/guest_lib.sh` | Guest checks: cgroup, lock, closure, lock candidate, finalize. Sourced by the guest and by host tests |
| `build_recipe.py` | `plan` / `execute` / `validate-export` / `image-context` / `import-check` |
| `test_prepare_source.py`, `test_build_recipe.py` | 20 + 56 focused tests |

## 1. Source identity and preparation (unchanged result, verified again)

- rAthena `0693b8c69911d5ca42269684aa036b67d67f4d3e` has tree `e7122969…`
  and 5049 files.
- The app's `config/VENDOR_PINS` pins it on **`Flux159/rathena`**, while the
  brief names `rathena/rathena`. `fetch` downloads it from both URLs and
  requires the same commit and tree.
- App `2c3b2612973fb8d0ae6ad366a2b298686f2404cb` has tree `8cab4674…`.
- The ordered steps equal the app's `apply-server-mods.sh` followed by the
  CI Dockerfile copy:
  1. crash-trace script
  2. copy of the 65 population-engine files
  3. 36 patches
  4. party-chat hook
  5. stamp file
  6. `Dockerfile.ragnarokmac`

  The blobs of the semantics scripts are pinned.
- **Fuzz:** exactly one hunk needs it (`0001`, the `pc.cpp` include block;
  the fork adds `skill_lua.hpp`). It is allowlisted with zero-fuzz-must-fail
  and a pinned resulting `pc.cpp` SHA-256. Every other patch uses zero fuzz.
- Rejects, side files, unlisted fuzz and stale allowlists all fail closed.
- Prepared tree: **5121 files**, digest
  **`b64e850bd0d0fddbcda1df619d9a2544f27e286301a0e7d69b5f827ea3d40f32`**.

### Footprint reconciled against independently prepared bytes (repair)

The "112 payloads" count is no longer used as an oracle. Instead:
- `prepare` compares its full per-path footprint with `source_footprint.json`
  (path, change type and SHA-256 for all 101 paths). Any difference fails
  and names the paths.
- `reconcile` compares two complete prepared trees path by path
  (exec bit + SHA-256). The reference side ignores only `.orig` side files.

Executed on 2026-11-04, all against a fresh `prepared2`:

| Compared tree | Result |
| --- | --- |
| The app's **own** `apply-server-mods.sh` (`reference`; it leaves 13 `.orig` side files) | 5121 vs 5121 files, `differ` / `only_a` / `only_b` all empty |
| The earlier independent `prepared` run | identical |
| A `git apply -C2` engine run | identical |

### Closed tree (repair)

`tree_listing` now rejects:
- **directory symlinks**, which `os.walk` lists but never descends, so they
  previously went unseen
- symlinked files
- non-regular entries such as FIFOs
- a symlinked root

`verify` also rejects a symlinked `out`, `out/source` or marker. Focused
controls: a planted directory symlink and a FIFO each fail `verify`; after
removal, `verify` passes.

## 2. Build recipe — what the repair changed

| Root finding | Repair | Control |
| --- | --- | --- |
| P1 `logs/steps.log` changed after `SHA256SUMS` | `finalize()` logs `PASS` first, writes sums atomically (`SHA256SUMS.tmp` → mv, excluded from scope), then only `RESULT`, which is checked by value | host `sh` runs the real `finalize` and the exact host `check_sums` passes, with `steps.log` included; an export with a late log line is rejected |
| P1 cgroup readback read parent leaves; values were not enforced | `check_cgroup` runs **before** any apk/compile and requires all of: exactly `0::/slim/<id>`; id == `CONTAINER_ID` (delivered by a second PUT after create); one mount at `/run/root-cgroup-view` with fstype `cgroup2` and `ro`; `<view>/<id>/{memory.max,memory.swap.max,cpu.max,pids.max}` equal to the plan and positive. `validate-export` re-checks the values and that the id equals the created container ID | pass case; other id, wrong pids, zero memory, rw mount, non-cgroup2, missing mount, only parent leaves, host cgroup and `pids.max=max` all fail closed (the parent `memory.max=max` is never read) |
| Expected values | Taken from pinned `slim-runtime linux.rs cgroup_setup`: memory.max = Memory; swap = MemorySwap − Memory if larger, else **Memory** (so MemorySwap == Memory would allow swap equal to Memory); cpu.max = `NanoCpus/10000 100000`; pids.max = PidsLimit. The plan sets MemorySwap = Memory + 1 MiB (swap 1 MiB; the backend cannot express 0) and **requests PidsLimit**, which the pinned runtime writes | formula tests |
| Plan accepted `memory_mib<=0` | Positive bounds: memory 512–6144 MiB, cpus 1–64 and ≤ fresh `--host-cpus`, jobs 1–cpus, pids 64–4096, reserve ≥ 256 MiB, deadline 600–86400 s, step ≤ deadline, post/cleanup budgets ≥ 30 s; booleans are rejected | 17 refusal cases; no run directory is created on refusal |
| P1 `/rathena` symlink on a populated image dir; `verify.sh` absent | No `/rathena` or `/symbols` access at all. The host rewrites the pinned app `verify.sh` (SHA `d4b7295b…`) with exact anchor counts (`cd /rathena/ragnarok-crash-tests` ×1 → `/work/crash/…`, `/symbols/trace-tests` ×2 → `/work/crash/symbols/trace-tests`) and records both SHAs. The guest checks the extracted original SHA, copies the fixture into owned `/work/crash` and runs the transform; only `/work` is written | transform output contains no `/rathena`; drift is refused; guest contract has no `ln -sfn` and no `rm -f /rathena` |
| Ambiguous create left an unowned orphan | `create_owned`: a 4xx is definite (nothing of ours exists). Transport loss or a 5xx is **ambiguous**: list all, adopt only an object with the exact `/<name>` **and** role and run labels, solely to delete it, then abort. **Never retried** | lost response → recovered and deleted, creates=1; 5xx → same; lost response with foreign labels → left untouched and reported UNRESOLVED; pre-existing same name → refused before create |
| SIGTERM bypassed `finally` | SIGTERM/SIGINT raise `Cancelled` (a BaseException). The post phase kills the container, cleanup deletes it with signals ignored, the previous handlers are restored, and the CLI exits 143 | real `os.kill(SIGTERM)` during poll → kill, delete, 404, `state=finished`, handler restored |
| Deadline started after start; HTTP timeout idle-only | The build deadline is absolute **from admission**. Post (logs/export) and cleanup have separate budgets; the plan records `absolute_bound_s`. Every request has an absolute end, enforced by a timer that shuts the socket down, plus an idle timeout and a body cap (json 8 MiB, logs 64 MiB, export 1 GiB, import 256 MiB). Short Content-Length bodies are detected | drip-fed response aborted at the 2 s budget (< 30 s total); truncated export → failure, no `export.tar`, cleanup done; body-cap overflow fails |
| Cleanup refusal | A refused DELETE is recorded as `deleted=false` and raises **UNRESOLVED**, never success | refused delete → UNRESOLVED and the container remains in the fake |
| `Binds` can create a missing source | `HostConfig.Mounts` `[{Type: bind, Source: /sys/fs/cgroup/slim, Target: /run/root-cgroup-view, ReadOnly: true}]`. Pinned `mounts.rs` refuses a missing `--mount` bind source at create; `Binds` is never sent | plan test |
| Owner (follow-up) | Declared `artifact_owner` and `import_owner` = uid 0, gid 0, mode 0755. The guest runs `chown 0:0`. `safe_extract` returns tar uid/gid/mode, and `validate-export` requires the declaration. `import-check` compares bytes, tar uid/gid/mode and the stat-header mode | export with uid/gid 1000 rejected; import with 1000:1000, 0:1000, 0644 or setuid 4755 rejected; owned container deleted each time |
| Dependency pins unqualified | `--mode build` **requires** `--apk-lock`: sorted, unique `name=version-rN` lines covering the Dockerfile set + `patch`, with `libunwind-dev` 1.8.1. The guest installs exact pins; an unavailable pin fails before compilation. The installed closure must equal the lock exactly, and preinstalled packages (musl/libstdc++) must be unchanged. `--mode resolve` is a separate qualification run: it installs the unpinned set, records `apk.lock.candidate`, and builds nothing | missing, malformed, unsorted or duplicate locks, a missing package and wrong libunwind all refused; extra or changed installed package fails `check_deps`; `lock_candidate` exact-prefix parse |

### Repair 2 (Root review of `1b0508c`)

| Root finding | Repair | Control |
| --- | --- | --- |
| Preinstalled `bash`: the guest's candidate lock held only *added* names, and the host lock parser then rejected it for lacking `bash`; build compared only the added set | **One consistent model** in both guest and host. **BASE** = exact `name=version` of every package the stock image already has, frozen: the guest derives `apk.base.current` before any change and requires it to equal the qualified `apk.base` byte for byte. **DELTA** (`apk.lock`, may be empty) = exact `name=version` of every package the install adds. WANT must be covered by BASE ∪ DELTA. DELTA must not re-pin any BASE package, which also refuses base upgrades. `libunwind-dev` is 1.8.1 wherever it comes from. Base musl/libstdc++ must equal the runtime ABI. After the install, the added set must equal DELTA exactly and no BASE package may be upgraded, downgraded or removed (guest `check_deps` and host `validate-export`). Resolve mode emits both `apk.lock.candidate` and `apk.base.candidate`; `plan --mode build` needs **both** `--apk-lock` and `--apk-base` | the Root case (bash only in base) plans and validates; bash in neither, re-pinned bash, musl ABI drift and empty base are refused; all-wanted-preinstalled with an empty delta is accepted; build exports with base drift, base upgraded or base removed are rejected; guest `check_coverage`/`check_lock_file` and base freeze via `lock_candidate` are run under `sh` |
| `create_owned` caught `Exception` only; `Cancelled` (a BaseException) escaped with no ID, no recovery and no delete | `create_owned` runs inside a bounded **`Shield`**, which swaps the SIGTERM/SIGINT handlers so a signal is only recorded. A per-thread mask cannot do this, because Python runs handlers in the main thread whatever thread receives the signal. The ID is stored in a caller-owned holder as soon as it is known. A `Cancelled` raised from inside the call is treated as an ambiguous create: exact name+labels recovery, delete only, no retry, then `Cancelled` is re-raised. After the shield, a recorded signal is raised as `Cancelled`. `execute` and its `finally` read the holder. An ambiguous create with no owned object found is recorded as `orphan_unresolved` (name + run label, possible late completion) without masking the cancellation | Cancelled raised after the daemon created the object → recovered `c1`, deleted, creates = 1, handler restored. Cancelled before send → no create, no delete, orphan recorded UNRESOLVED. Real SIGTERM during a delayed create → shield lets the create finish, ID known directly, then cancelled and deleted |
| `import_check` installed no signal handling and could lose cleanup or the ID during create | Same holder + shield + exact-label recovery. SIGTERM/SIGINT handlers are installed and restored; cleanup runs with signals ignored; a refused delete is UNRESOLVED; a lost create is never retried | Cancelled after daemon create → deleted; real SIGTERM during delayed create → deleted; real SIGTERM with known ID (during HEAD) → deleted; refused delete → UNRESOLVED; dropped create → creates = 1, nothing left |
| (repair 3) `import_check`: a failure or cancellation in the body (e.g. HEAD raising `Cancelled(SIGTERM)`) combined with a refused DELETE or an unconfirmed 404 propagated only the original exception, so the owned ID, name and cleanup failure were lost | The body's exception is held, not swallowed. Cleanup always runs (signals ignored); the outcome is written to `--record` (now required on the CLI) **before** anything propagates. Unconfirmed cleanup raises `CancelledUnresolved` (a `Cancelled` subclass, CLI exit 143, prints the UNRESOLVED detail) when cancelled, otherwise `CleanupUnresolved` (a `RecipeError`). Both carry `.detail` = {container_id, name, run label, cleanup_error, primary} and `__cause__` = the original exception. Confirmed cleanup keeps the previous semantics: the original exception or `Cancelled` is re-raised unchanged. The create shield is unchanged | Cancelled + refused DELETE and Cancelled + failed 404 confirmation → `CancelledUnresolved`, cause is the same object, record holds `c1`/name/error, handler restored; RecipeError + refused DELETE → `CleanupUnresolved` with chained cause; Cancelled + confirmed cleanup → the identical `Cancelled`; CLI → exit 143 with the record written |
| (repair 4, runtime compatibility) Root's first real read-only `GET /version` failed with `AttributeError: 'NoneType' object has no attribute 'settimeout'`. For a close-framed response, Python 3.9 `getresponse()` calls `conn.close()` (`conn.sock=None`) and hands the body to the `HTTPResponse`; the read loop and the deadline timer used `conn.sock` | `UnixHTTPConnection.connect` retains its socket as `transport` for the whole request. Every idle timeout is armed on `transport` (capped at the remaining absolute budget), and the timer shuts `transport` down. CPython keeps the descriptor open while the response's makefile reference exists. The response, connection and transport are closed in `finally`. A timeout armed at the remaining budget is reported as the absolute deadline. Truncation, caps, HEAD, status and lifecycle contracts are unchanged | new `CloseFramedTests` over **real Unix-socket HTTP** with byte-scripted responses: `Connection: close` + Content-Length and EOF-framed bodies succeed; close-framed and EOF-framed drips stop at a 1 s absolute budget (< 3 s); a stall stops at the 0.3 s idle timeout; slow headers stop at the deadline; truncation, cap, HEAD with stat header, 404 status and 404 confirmation, close-framed create and holder semantics all hold; no descriptor leak over 50 calls. **On `ad87a58b` all 11 fail with Root's exact AttributeError** |
| `verify` resolved `out` before its symlink check, so a root link was accepted | The root path is checked with `is_symlink()` **before** `resolve()` | authored root-link control; real check: `prepared2-link` → `FAIL … output root is a symlink`; `prepared2` itself passes |

### Unchanged route and lifecycle

- Engine requests:
  1. census (`GET /containers/json?all=1`)
  2. create
  3. inspect, with a label check
  4. PUT `upload.tar` and PUT `owner.env` to `/work/in`
  5. start
  6. poll inspect
  7. kill (on deadline, failure or cancel)
  8. logs, then GET `/work/out`
  9. `DELETE ?force=1`, then inspect, expecting 404
- Never used: `/build`, `/wait`, commit/save, exec, pull.
- The upload is a 23,080,960 B wrapper tar holding the 23 MB deterministic
  `source.tar.gz` (SHA-256 `101b1526…388d84f`, unchanged).
- Flags, configure options, `make -j$JOBS map`, the era check, builtin
  presence, debuglink, ELF/INTERP/NEEDED checks and the musl loader
  `--list` are unchanged from the initial candidate.
- Unpatched and patched builds run in one container with one toolchain.

## 3. Checks executed on this revision (host, 2026-11-04 UTC)

| Check | Result |
| --- | --- |
| fresh `prepare` (footprint pin active) + `verify` | OK, 5121 files, `b64e850b…`; `PREPARED.json` `1f3a3c92…` |
| `reference` + `reconcile` × 3 (app script, earlier run, git-apply) | all zero differences |
| `test_coin_capacity.py` on `prepared2/source` | `pins ok 9`; clean patch; 133 cases / 63 probes / 0 failures; **9/9 mutants caught** |
| `test_prepare_source.py` | **20/20 OK** (repair 2) |
| `test_build_recipe.py` | **56/56 OK**, ×3 repeats (about 25 s each; repair 4) |
| `ruff check tools/renewal/native_capacity/` (ruff 0.16.9, repo `ruff.toml`) | All checks passed |
| `sh -n` guest scripts | OK |
| plan-only demo on the real tree (`--mode resolve`, placeholder image `sha256:0…0`, no Engine) | upload `6bee45a7…08ac`, expected cgroup `memory.max=1610612736`, `memory.swap.max=1048576`, `cpu.max=200000 100000`, `pids.max=1024`, absolute bound 14880 s; `--mode build` without a lock refused; `--memory-mib 0` refused |

Owned evidence stays in ignored `.tools/t10-010-003-claude-a1/` (`ev/`,
`ev2/`, `prepared/`, `prepared2/`, `prepared-ga/`, `ref-app/`). The
initial-candidate evidence is kept.

## 4. Root's next executable sequence (T10.010.004, after fresh bindings)

```sh
P=tools/renewal/native_capacity
python3 -I -B $P/prepare_source.py fetch   --cache $W/cache
python3 -I -B $P/prepare_source.py prepare --cache $W/cache --out $W/prepared
python3 -I -B $P/prepare_source.py reference --cache $W/cache --out $W/ref
python3 -I -B $P/prepare_source.py reconcile --out $W/prepared --against $W/ref
python3 -I -B $P/test_coin_capacity.py --native-source $W/prepared/source --clang /usr/bin/clang++
# (a) dependency qualification run -- builds nothing
python3 -I -B $P/build_recipe.py plan --mode resolve --prepared $W/prepared --rundir $W/r1 \
    --base-image sha256:<fresh stock image id> --expect-musl <fresh> --expect-libstdcxx <fresh> \
    --mem-available-bytes <fresh> --host-cpus <fresh>
python3 -I -B $P/build_recipe.py execute --plan $W/r1/PLAN.json --engine-socket <sock> --admit <admit>
python3 -I -B $P/build_recipe.py validate-export --plan $W/r1/PLAN.json --export $W/r1/export.tar --dest $W/r1/v
#     Root reviews r1/v/out/apk.lock.candidate (delta) and apk.base.candidate (frozen base)
# (b) build run with both qualified files
python3 -I -B $P/build_recipe.py plan --mode build --apk-lock <qualified delta> --apk-base <qualified base> ... --rundir $W/b1
python3 -I -B $P/build_recipe.py execute ... ; python3 -I -B $P/build_recipe.py validate-export ...
```

## 5. Remaining limitations (open, not passed)

- **No real execution.** Nothing has run on a real slim Engine or guest:
  cgroup leaf values and mount layout, the PidsLimit write, `Mounts`
  refusal, kill/delete, archive owner/mode readback, compile time and
  memory, and the binaries themselves.
- The fake Engine proves request order and logic only.
- `guest_lib.sh` was exercised under macOS `/bin/sh` (bash 3.2 in POSIX
  mode). **Busybox ash, comm, awk and cmp behaviour in Alpine is not
  observed.**
- **Dependencies.** No qualified base/delta pair exists yet. Alpine keeps only the
  current `-rN`, so a lock can stop resolving at any time, which fails
  closed before compilation. There is **no offline closure**, apk needs
  container networking, and package bytes are verified only by apk's own
  signed index.
- Swap: the backend cannot express zero swap, so 1 MiB is requested and
  verified.
- Headroom: the defaults need 1536 + 768 MiB of fresh MemAvailable. The
  earlier ~1.3 GiB snapshot would be refused. Whether 1536 MiB suffices at
  `-j1` is unknown.
- Pinned `mounts.rs` validates the bind source at **create**, but `prepare`
  at start would create it again if it vanished in between. The guest's
  cgroup2/ro check catches a plain directory.
- If create is ambiguous **and** recovery cannot list the object, the
  possible orphan is reported UNRESOLVED (name + run label) for Root. It is
  never guessed or deleted.
- Only the renewal `map-server` is built; pre-renewal builds and the other
  servers are not.
- Model: configured `claude-opus-5-5`; the provider-reported model is not
  observed. Repair wall clock was about 28 min (07:27–07:55Z); repair 2 took
  about 25 min. Cost and tokens were not observed.
- `Shield` defers signals only for the bounded create/recovery (the request
  budget plus the recovery budget). A SIGKILL, or a host crash in that
  window, still needs Root's exact name + run-label recovery.
