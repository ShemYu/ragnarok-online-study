# T10.010.003 — reproducible native source and bounded map-server build

Claude candidate (blinded pair). Base `a06f1037ac6ecf308db6a963e06391ebbf586cbd`,
brief `docs/project/tasks/T10.010.003.md` (SHA-256 `7bd1791f…a5a3f8`).
Status: **candidate result, not Root verification**. Source preparation was
executed and checked on the host. The full build recipe is implemented and
tested only against a fake Engine. **No compiler container, image or binary
has been run or produced.**

## Files

| Path | Role |
| --- | --- |
| `source_manifest.json` | Repository/commit/tree pins, app semantics blob pins, ordered steps, fuzz allowlist and prepared-tree digest |
| `prepare_source.py` | `fetch` / `prepare` / `verify` / `reference` |
| `test_prepare_source.py` | 16 focused tests using synthetic `file://` repos, plus a binding check on the real manifest |
| `build/guest_build.sh` | Guest script: builds unpatched and patched renewal `map-server` in one container with one toolchain |
| `build_recipe.py` | `plan` / `execute` / `validate-export` / `image-context` / `import-check` |
| `test_build_recipe.py` | 11 tests against a fake Unix-socket Engine |

## 1. Source identity

- rAthena `0693b8c69911d5ca42269684aa036b67d67f4d3e`, tree
  `e7122969bfca08f0dd1dc65e5cc723dcd7411170`, 5049 files (5031 × 100644 and 18 × 100755).
- **Repository identity finding.** The brief names `rathena/rathena`. The
  app's own `config/VENDOR_PINS` pins this commit on **`Flux159/rathena`**
  (branch `ragnarokoffline`). The commit is a fork merge ("Merge pull
  request #40 from Dizzzlectic/fix/non-critical-random-options", 2026-10-15).
  `rathena/rathena.git` serves it only because GitHub shares objects across a
  fork network. `fetch` downloads it from **both** URLs into separate bare
  caches and requires the same commit and tree (`app_vendor_pin_url: true`).
  The content is identical, but upstream rAthena does not necessarily contain
  this commit on any of its branches.
- App `2c3b2612973fb8d0ae6ad366a2b298686f2404cb`, tree `8cab46745c01bc49d62b5f43b209a88910686151`.
- Fetching uses `git fetch --depth 1 <url> <sha>` with `transfer.fsckObjects`.
  Export reproduces `git checkout` (`read-tree` + `checkout-index`, with
  `core.autocrlf=false`, honouring `.gitattributes` eol rules) and includes
  no `.git` directory.

## 2. Ordered transforms (= `scripts/apply-server-mods.sh` + CI Dockerfile copy)

The app's actual build route is the same in `bootstrap.sh` and in
`.github/workflows/images.yml` (`compile`): `vendor-fetch.sh rathena` →
`apply-server-mods.sh` → `cp containers/rathena/Dockerfile Dockerfile.ragnarokmac` → build.
The manifest pins the blobs of `apply-server-mods.sh`, `apply-crash-trace.py`,
`apply-party-chat-hook.py`, the Dockerfile, `VENDOR_PINS` and `PACKETVERS`.
Any change to those semantics makes preparation fail.

| # | Step | Effect on tree |
| --- | --- | --- |
| 1 | `apply-crash-trace.py` (the app's own script, run with `python3 -I -X utf8`) | modifies `src/common/core.cpp`; adds `src/common/ragnarok_crash_trace.hpp` and 4 files in `ragnarok-crash-tests/` |
| 2 | copy `third-party/population-engine/files/**` | +65 files |
| 3 | 36 patches, byte-sorted, `-p1 --forward` | modifies 28 files |
| 4 | `apply-party-chat-hook.py` | modifies `src/map/clif.cpp` (already patched in step 3) |
| 5 | stamp `.ragnarokmac-server-mods` = sha256(cat patches) + `\n` | +1 |
| 6 | `Dockerfile.ragnarokmac` | +1 (build context) |

**Footprint:** 5049 → **5121** files: **72 added, 29 modified, 0 removed**
(full lists are in `PREPARED.json`). The historical 5049 → 5120 files and
"100 changed paths" equal this footprint minus `Dockerfile.ragnarokmac`,
which bootstrap/CI add separately. On the "112 overlay payloads": this
reconstruction reads 108 distinct app blobs as inputs (65 files, 36 patches,
4 crash-trace sources, 2 Python transforms, the Dockerfile). It also
executes or pins 3 more semantics blobs (`apply-server-mods.sh`,
`VENDOR_PINS`, `PACKETVERS`), for 111 in total. I cannot reproduce the
historical 112 from public inputs without its private packet, so that count
is **unreconciled**. The footprint above is what I actually verified.

### Patch ambiguity found and how it is handled

- Every patch applies with **offsets** (git-apply counts many offset hunks
  per patch). This is expected because the patches target a fork that has
  moved under them.
- Exactly **one hunk needs fuzz**: `0001-population-engine-hooks.patch` in
  `src/map/pc.cpp`, the include block. The fork adds
  `#include "skill_lua.hpp"` after `skill.hpp`, so the last trailing context
  line differs. With fuzz 1 the two population includes still land after
  `pet.hpp` inside the include block, which is the intended and unique
  place. Host `patch -F 0` rejects it, and `git apply` with full context
  fails it (and then cascades to 27 more patches).
- The historical "no fuzz/offset diagnostic" result came from `patch -s`,
  which suppresses those diagnostics. The app's real script uses default
  fuzz silently, and on macOS it leaves **13 `.orig` side files**, matching
  the historical 13.
- Policy: zero fuzz everywhere except the single allowlisted patch. For that
  patch, zero fuzz must fail (otherwise the allowlist is stale), fuzz 1 is
  used, and the resulting `pc.cpp` SHA-256 must equal
  `bf611356a23674233969d1eb37c32bff551b5ce94bf28517777d755975bb24b6`.
  Rejects, `.rej`/`.orig` files, an unlisted fuzz or a wrong result all fail
  closed.
- **Cross-implementation agreement.** Three routes produce the same
  prepared-tree digest **`b64e850bd0d0fddbcda1df619d9a2544f27e286301a0e7d69b5f827ea3d40f32`**
  (sha256 over sorted `exec-bit\tsha256\tpath` lines):
  1. Apple `patch` 2.0-12u11 with the allowlist.
  2. `git apply -C2` for the allowlisted patch and full context otherwise.
  3. The app's **own** `apply-server-mods.sh` (`reference` command), after
     excluding its 13 `.orig` side files.

  GNU patch was not available on the host, so GNU-specific behaviour is
  **not observed**. The digest pin makes any divergence fail.

### Safe-failure rules

- `prepare` refuses an existing output and any `<out>.staging-*` leftover.
- It builds in a sibling staging directory, writes `PREPARED.json` last and
  publishes with an atomic rename.
- On any error the staging directory is removed.
- `verify` fails on a missing marker, unexpected entries, any
  modified/added/removed file or mode change, digest drift, or a staging
  leftover.

## 3. Executed source checks (host, 2026-11-04 UTC)

Owned ignored workspace: `.tools/t10-010-003-claude-a1/` (fresh, created by
this run). No shared canonical source, old `.tools` packet or prepared
checkout was used.

| Check | Command | Result |
| --- | --- | --- |
| fresh fetch (both rAthena URLs + app) | `prepare_source.py fetch --cache C` | OK; rathena tree e7122969…, vendor-pin URL identical; app tree 8cab4674… |
| fresh preparation | `prepare_source.py prepare --cache C --out O` | OK: 5049 → 5121 files, +72/~29/−0, nine pins 9/9, digest b64e850b…; fresh fetch + prepare + verify took 18 s |
| re-verify | `prepare_source.py verify --out O` | OK, 5121 files, same digest |
| engines agree | `--patch-engine git-apply`, `reference` | same digest (discovery run) |
| patch + differential | `test_coin_capacity.py --native-source O/source --clang /usr/bin/clang++` | `pins ok 9`; patch applied with no rejects; unchanged bodies OK; `SUMMARY cases=133 probes=63 failures=0`; **9/9 causal mutants caught**; rc 0, 8 s |
| safe failures | `test_prepare_source.py` | 16/16 OK (bad revision, bad tree pin, app-semantics change, unpinned/wrong digest, wrong native pin, existing output, partial staging, dirty modify/add/remove/mode, missing marker, foreign entries, reject, unlisted fuzz, allowlisted fuzz with right/wrong result, stale allowlist, absent-patch allowlist) |
| recipe logic | `test_build_recipe.py` | 11/11 OK, fake Engine only |

Hashes: `PREPARED.json` 5665099a…e9832ce521. The deterministic
`source.tar.gz` is 23,049,381 B, sha256 `101b1526…388d84f`. The wrapper
`upload.tar` is 23,070,720 B, sha256 `3e36a6eb…a4139833`. Both are identical
across repeated plans. `coin_capacity.patch` is `9c84d846…5411d`; the patch
and oracle are unchanged.

## 4. Full build/export recipe (for Root in T10.010.004)

### Engine route (pinned slim source, nebula `2e9cf43`, `slimd/router.rs` and `archive.rs`)

- **Uses only** `GET /containers/json`, `POST /containers/create`,
  `GET /containers/{id}/json`, `PUT` and `GET /containers/{id}/archive`,
  `POST start` and `POST kill`, `GET logs` and `DELETE ?force=1`.
- **Does not use:**
  - Dockerfile build (pre-FROM ARG and stage ARG defects, directory COPY
    basename, RUN without network or limits)
  - commit or image save (both return 501)
  - `/wait`: an HTTP disconnect only stops the wait, not the container, so
    the recipe polls inspect and kills on the deadline
  - exec and pull
- PUT archive buffers the whole body in Engine memory (2 GiB cap) and does
  not decompress it, so the upload is a 23 MB wrapper tar holding
  `source.tar.gz` (the prepared tree itself is about 110 MB). PUT preserves
  modes, and GET works on stopped containers.

### Container lifecycle

- Single owner: refuse if any container labelled
  `t10.010.003.role=compiler` already exists.
- Admission token = sha256 of `PLAN.json`. The plan is consumed once
  (`EXECUTION.json`).
- Create the named, labelled container (`User 0:0`,
  `Cmd /work/in/guest_build.sh`, `RestartPolicy no`, `AutoRemove false`) →
  PUT inputs → start → poll.
- On the deadline: kill → logs → GET `/work/out` → `DELETE ?force=1` →
  confirm 404.
- The delete runs in `finally` for every path. A cleanup error is reported
  as **unresolved**, never as success.

### Toolchain and dependency inputs

- Base image must be an **immutable local image ID** (`sha256:…`), never a
  tag. Recommended base: the currently running stock
  `ragnarokmac/rathena:20221005` image ID (Alpine 3.23, runtime libraries
  already present). Its musl and libstdc++ then define the ABI. Root must
  read that ID freshly.
- The guest runs `apk add` with the Dockerfile set (`bash git make cmake gcc
  g++ zlib-dev mariadb-dev linux-headers libunwind-dev~1.8.1 binutils`) plus
  `patch` (GNU; busybox patch has no `-F`).
- After the install, the build **fails** unless musl and libstdc++ still
  equal the expected runtime versions (plan inputs, e.g. `1.2.5-r23` and
  `15.2.0-r2`, from Root's fresh check). It records `apk-before/after`,
  `toolchain.txt` and `environment.txt` (Alpine release, nproc, meminfo,
  cgroup values).

### Flags, configuration and outputs

- Flags are identical to the Dockerfile: `CXXFLAGS=-g -O2
  -fno-omit-frame-pointer -fno-optimize-sibling-calls`,
  `CPPFLAGS=-DRAGNAROK_CRASH_TRACE`, `LIBS=-lunwind`,
  `LDFLAGS=-Wl,--build-id=sha1 -rdynamic`.
- Configure with `./configure --enable-packetver=20221005` (renewal),
  then `make -j$JOBS map`.
- Crash-trace `verify.sh` runs once.
- Era check: the `npc/re` marker is present and `npc/pre-re` is absent.
- Builtin check: `ros_ch1_coin_capacity` is present only in the patched build.
- Then objcopy `--only-keep-debug` / `strip --strip-debug` / debuglink, as
  in the Dockerfile.
- The guest records the ELF header, NEEDED/RPATH, INTERP and the musl
  loader `--list` (any unresolved library fails), plus `SHA256SUMS`.

### Comparable A/B builds

The **unpatched** and **patched** builds run in the same container, with
the same toolchain, flags and prepared tree. The only difference is
`coin_capacity.patch` (GNU patch `-F 0`, dry run first, no side files
allowed).

### Resource limits (defaults, all parameters)

- `Memory = MemorySwap = 1536 MiB` (no swap), `NanoCpus = 2e9`, `-j1`.
- Per-step `timeout` 3600 s; overall deadline 4 h.
- `plan` refuses unless the fresh MemAvailable ≥ limit + 768 MiB reserve.
- `PidsLimit` is **not advertised** by the current Engine (Root, 2026-11-04),
  so it is not requested.
- An optional read-only cgroup view bind
  (`/sys/fs/cgroup/slim:/run/root-cgroup-view:ro`) follows Root's earlier
  qualified readiness probe. Enforcement is **not** assumed; Root compares
  the guest's readback with the plan.

### Export validation (`validate-export`)

The export must pass all of the following:

- safe tar extraction (regular files and directories only, no escape)
- `RESULT = PASS`
- the file set equals `SHA256SUMS` and every hash matches
- both binaries are ELF64 LE AArch64 (`e_machine` 183), mode 0755, with
  interpreter `/lib/ld-musl-aarch64.so.1`
- era markers are correct, and the builtin is present only in the patched
  binary
- both variants have identical NEEDED sets but different bytes
- musl and libstdc++ match the plan

It writes `ARTIFACTS.json` (sha256, size, Build ID, NEEDED, debug sha256).

### Import route

- `image-context` writes a context whose Dockerfile is exactly
  `FROM <image-id>` plus one literal single-file
  `COPY map-server /rathena/map-server-t10-010-<variant>`, with no ARG and
  no RUN.
- Because COPY chmod/chown cannot be assumed, `import-check` creates (and
  never starts) a container from the resulting image. It reads the
  stat-header mode and the archive bytes, requires sha256 and mode 0755,
  then deletes the container and confirms a 404.
- The image build itself goes through the Engine's build handler. Missing
  bases may be pulled and no-cache still uses the shared cache, so Root
  must use a locally present base ID and verify readback.

### Root's next executable action (T10.010.004)

```sh
# 0. fresh read-only binding: Engine, running stock image ID, musl/libstdc++,
#    MemAvailable, no foreign compiler-role containers; backup/isolation refreshed
python3 -I -B tools/renewal/native_capacity/prepare_source.py fetch   --cache $W/cache
python3 -I -B tools/renewal/native_capacity/prepare_source.py prepare --cache $W/cache --out $W/prepared
python3 -I -B tools/renewal/native_capacity/test_coin_capacity.py --native-source $W/prepared/source --clang /usr/bin/clang++
python3 -I -B tools/renewal/native_capacity/build_recipe.py plan --prepared $W/prepared --rundir $W/run1 \
    --base-image sha256:<fresh stock image id> --expect-musl <fresh> --expect-libstdcxx <fresh> \
    --mem-available-bytes <fresh>          # prints admit=<sha256 of PLAN.json>
python3 -I -B tools/renewal/native_capacity/build_recipe.py execute --plan $W/run1/PLAN.json \
    --engine-socket <socket> --admit <admit>
python3 -I -B tools/renewal/native_capacity/build_recipe.py validate-export --plan $W/run1/PLAN.json \
    --export $W/run1/export.tar --dest $W/run1/artifacts
```

## 5. Limitations and open items (not passed)

- **No real build has run.** Compile success, compile time, peak memory,
  whether 1536 MiB suffices at `-j1` for `script.cpp`/`pc.cpp` with
  `-g -O2`, and the real outputs are all unknown.
- At the earlier ~4 GiB guest snapshot, MemAvailable was about 1.30 GiB.
  At those numbers `plan` would **refuse** (it needs 2.25 GiB). Root must
  either measure enough headroom or choose an explicit smaller limit and
  accept the OOM risk. The recipe does not stop or resize user services.
- **Network:** `apk add` needs container networking. Neither an offline
  package set nor immutable apk pins exist, because Alpine carries only the
  current `-rN` of each package. The recipe records the resolved versions
  and fails on an ABI drift of musl/libstdc++, but other package versions
  (gcc, binutils, libunwind, mariadb-connector) are recorded, not pinned.
  This dependency pin is **missing**.
- Cgroup enforcement, actual PID limits, container deletion that fully
  reclaims storage, and kill-at-deadline on the real slim Engine are
  untested. The fake Engine proves only request order and logic.
- The `/sys/fs/cgroup/slim` bind source must exist in the guest. If it does
  not, create fails closed, and Root may drop the bind from the plan.
- GNU patch behaviour on the host was not observed (only Apple patch and
  `git apply`). The guest uses GNU patch `-F 0` only for `coin_capacity.patch`.
- Only renewal `map-server` is built. char/login/web and pre-re builds are
  not produced. The app image also ships `char-server`, which must match
  `mmo.hpp`, and the coin patch does not change `mmo.hpp`.
- The prepared tree deliberately excludes `.git` and the 13 `.orig` files
  that the app's own script leaves in its build context. Neither is
  compiled.
- The "112 overlay payloads" count remains unreconciled (see §2).
- Model: configured `claude-opus-5-5` (Opus 5.5) per session metadata; the
  provider-reported model is not observed. Elapsed time is about 20 min of
  wall clock from 07:03:44Z. Cost and tokens were not observed.
