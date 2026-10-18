# Navigation client repair (T05.007)

Source and artifact generator for the Taiwan navigation repair. It produces a
repaired copy of the patched Ragnarok Offline 1.6.3 `Online.js` and a separate
seven-file mod that serves the six Taiwan navigation chunks, byte for byte, at
the Korean filenames the client requests. **Generation, its tests and a
`COMPLETE.json` do not show that the repair works in the native Lua runtime,
the installed app or the game.** Root owns that verification; see
[Limits](#limits).

## Command

```sh
python3 -I -B tools/renewal/navigation_client_repair.py BUNDLE_SOURCE TAIWAN_TABLE_DIR OUTPUT
```

- `BUNDLE_SOURCE`: the pinned `Online.js` (13166284 bytes, SHA-256
  `80f4371c…33ea`).
- `TAIWAN_TABLE_DIR`: a directory holding the six pinned
  `navi_<role>_tw.lub` chunks (map, mob, npc, link, linkdistance,
  npcdistance).
- `OUTPUT`: a new path whose parent exists. It must not exist, not even as a
  dangling link.

Python 3.9 standard library only. The frozen `profile.json` (4838 bytes,
SHA-256 `70508ac9…265b`) is embedded verbatim and checked at import, so
arguments only locate bytes; no pin, offset, request or metadata can be
overridden and no environment variable is read. Success prints one JSON line
`{"files": 8, "manifest_sha256": …, "output": <basename>, "state":
"complete", "task": "T05.007"}`; any refusal or failure exits nonzero with a
one-line, path-free diagnosis on stderr and no traceback. Wrong argument count
or a leading `-` exits 2 with usage.

## Output

```text
OUTPUT/                                     0700
  Online.js                                 0600  repaired bundle (not a mod)
  repair-manifest.json                      0600
  COMPLETE.json                             0600  written last
  tw-navigation-request-compat/             0700  the only mod folder
    mod.json                                0600  278 bytes, f207ec96…c336
    data/luafiles514/lua files/navigation/  0700 at every level
      navi_{map,mob,npc,link,linkdistance,npcdistance}_krpri.lub  0600
```

Exactly ten files and six directories. Each `_krpri.lub` is its `_tw.lub`
source, streamed and hashed as opaque bytes. `mod.json` is `profile.package`
in canonical JSON (`sort_keys`, `indent=2`, `ensure_ascii=False`, LF, no BOM).
`repair-manifest.json` holds exactly `schema`, `task`, `profile`, `generator`
(the bytes/hash of the generator file that ran, no path), `inputs`
(`profile.inputs` verbatim, after verifying the bytes actually consumed),
`package` and eight sorted `files` records `{path, bytes, sha256, mode}`.
`COMPLETE.json` binds the read-back manifest. No timestamps, private paths or
payload text appear in either. Repeated runs of one generator are
byte-identical.

## The repair

The only bundle change is inside the original `loadLuaValue` function,
bytes [10727952, 10731097), SHA-256 `ea24a0af…b664`. The generator requires
the full bundle, window, prefix and suffix pins, the queue/loader/entry region
pins, a unique `loadLuaValue` signature at the pinned offset, a unique
following `mapInfo` comment, and unique callback and unmount anchors inside
the window. It inserts three pieces and changes nothing else:

1. Local helpers after the function's opening line: a table of the six exact
   `variable_name` → `file_path` pairs from `profile.requests`, the
   `navigationTransport` guard (both must match), and `navigationValue`.
2. `if (navigationTransport) result = navigationValue(ctx); else {` before the
   original `ctx.extractValue = …` line.
3. `}` before the original `lua.unmountFile(file_path);`.

The original callback, its `String.raw` serializer, the name/server-link
templates, the six request sites, the queue and everything outside the window
keep their exact bytes, so every other table (and any navigation global asked
for at another path) converts exactly as before, defects included. The tests
strip the three insertions and require the original window back.

Cause: the original serializer escapes `\` inside raw Big5 bytes and the host
decodes the whole JSON text at once, so the trail byte `5c` of 許 (`b3 5c`)
pairs with the lead byte and the escape's remainder survives as literal
`u005c`. The new transport never puts raw bytes next to escapes:

- Lua writes pure-ASCII JSON. Every string value is `"<hex of its raw
  bytes>"`. A table keyed exactly 1..n (including the empty table) is an
  array, as before; any other table is an object whose keys are `s<hex>` for a
  string key or `n<digits>` for an integer key with |k| < 1e13. Numbers are
  `%.17g` (round-trips doubles, keeps `-0`). Booleans stay booleans.
- After the name-swap and server-link templates have run (unchanged, as
  before), the global is converted inside `pcall`; the text, or `!` and a
  fixed diagnosis, reaches the host through the existing `extractValue`
  callback, so no Lua error is left on the shared state's stack.
- The host copies the callback's bytes at once (they are a view into WASM
  memory), requires printable ASCII, `JSON.parse`s, then rebuilds the value,
  decoding each string and string key **separately** with
  `userStringDecoder.decode(bytes, userCharpage)`. It never relies on the
  decoder's default charset (windows-1252). Object keys are defined with
  `Object.defineProperty`, so a key such as `__proto__` stays an own property.

Supported: raw strings of any bytes (so `b3 5c` → 許, literal `u005c`, ASCII
backslashes/quotes, C0 controls and NUL stay exact), nested dense and empty
arrays, sparse objects with string or small integer keys, booleans and finite
numbers. Refused visibly: a missing or non-table global, boolean keys,
fractional/huge/non-finite numeric keys, two keys equal once decoded (for
example `"1"` and `1`), cycles, metatables, nesting deeper than 256, non-finite
numbers, functions/userdata/threads, a non-ASCII or missing transfer, and a
non-empty string that decodes to nothing. No Unicode normalization, no
`u005c` removal, no substitute or empty table.

Failure path in production: the error is thrown into the function's own
`catch`, which logs `(<path>) error:`, calls `callback(null)` and, in
`finally`, `onEnd` once, exactly as the original branch does. Like the
original, a failed load leaves its file mounted in the Lua filesystem; only a
successful load unmounts. Closing states and mounts after a test run is the
harness's (root's) cleanup, not something this code does.

## Publication guarantees

- Inputs: no symlink path component, no `.`/`..`/empty component, regular
  files only (opened non-blocking, so a FIFO is refused without hanging), all
  seven distinct by path and by device/inode, OUTPUT neither inside nor around
  any input or the table directory.
- Each input is held on one descriptor for the run. The bundle is read whole
  under a 32 MiB bound; aliases are streamed in 1 MiB chunks. Exact size, EOF
  and SHA-256 are checked on the bytes actually consumed, and descriptor and
  path identity/metadata must be unchanged afterwards (truncation, growth,
  later or already-consumed changes all fail).
- Outputs are created `O_EXCL|O_NOFOLLOW`, set to 0600/0700 whatever the
  umask, written with `os.write` loops (short writes continue; zero or
  impossible progress fails; no buffered I/O), fsynced and closed once, then
  reopened and checked for identity, mode, size and hash. Write, fsync, close,
  read-back and completion errors all fail the run.
- `COMPLETE.json` is written beside, read back, hard-linked into place, read
  back again, and the tree is re-checked for exactly ten files.
- On failure, only entries recorded as created by this run (by device/inode)
  are removed, deepest first. A replaced OUTPUT root or foreign entries are
  left and reported; a root whose ownership could not be confirmed is left
  untouched and reported. No adversarial concurrency, retry after an
  ambiguous close, directory fsync or power-loss guarantee is offered.

## Tests

```sh
T05_007_INPUT_ROOT=<frozen input root> python3 -I -B tools/renewal/test_navigation_client_repair.py -v
```

`-I` keeps the checkout off `sys.path`, so run the file, not `-m unittest`.
G01 (frozen manifest/profile identity, real CLI twice, exact tree, unchanged
inputs, legacy bytes, request sites/helpers in place, `node --check` of the
window and of the whole repaired bundle as a module) is skipped without
`T05_007_INPUT_ROOT`. G02–G05 use small authored fixtures under
`.tools/renewal/T05.007/test-work` (override with `T05_007_WORK`): repair
shape and forbidden mechanisms, refusals, injected I/O failures (short/zero/
failing writes, every fsync, close EIO after a real close including the final
`COMPLETE.json` read-back, truncation/changes during streaming, read-back
corruption, partial descriptor acquisition, foreign root/entries, interrupt)
and this runbook's sections. JavaScript is only parsed; no Lua, WASM, browser
or game code is executed by these tests.

## Serial delivery plan (plan-only)

One later installed delivery, owned and qualified by root. Nothing here has
been run against the installed app. The bundle and the alias mod are separate
deliveries: the mod cannot replace `Online.js`, and the bundle alone does not
satisfy the six requests.

### Preservation

Before any runtime change:

1. Quit the app normally after an ordinary save. Take a fresh full backup of
   the newest save/database, `state/mods` (including `enabled.txt` /
   `disabled.txt`), mod settings and app settings; read every file back. The
   older H backup excludes the runtime and predates the current package/save,
   so it is not a substitute and must not be restored to test rollback.
2. Separately preserve the exact original runtime/client artifacts that will
   be shadowed: the served `vendor/roBrowserLegacy/dist/Web/Online.js` (expect
   the pinned 13166284 bytes / `80f4371c…33ea`) and anything else the chosen
   bundle route replaces. Record size/hash/mode.
3. Record the enabled overlay set (for example the NPC dialogue package) so it
   stays enabled and can be compared after delivery.

### Bundle delivery

The packaged app serves the client from
`<projectRoot>/vendor/roBrowserLegacy/dist/Web` (`ROBROWSER_PATH`).
`projectRoot()` in the Electron source returns `RAGNAROKMAC_ROOT` when set,
otherwise the installed `runtime` copy of the signed payload. The candidate
route is a developer root: a separate copy of the runtime tree whose
`dist/Web/Online.js` is the repaired file, selected through
`RAGNAROKMAC_ROOT`. **This is conditional and unverified**: it is source
behaviour, not shown to apply to the installed binary, and it changes how the
app is launched. Do not patch the signed app or the current materialized
`runtime` tree. If the route cannot be qualified without wider changes, stop
and report rather than choosing another override.

Confirm the actually served `Online.js` over HTTP equals the repaired
`OUTPUT/Online.js` (bytes/hash) before testing gameplay; the client caches
files by name, and `Online.js` is not part of the mod overlay fingerprint.

### Alias mod installation

Install only the inner `OUTPUT/tw-navigation-request-compat/` folder (Settings
→ Mods → Add mod from folder, or by copying the folder into the mods
directory). A fresh supported installation is enabled even though `default` is
`off`, which is why the fresh backup comes first. Its `data/` layer is served
ahead of the GRFs after an app restart, and the overlay fingerprint change
drops the client's cache. Confirm each of the six served
`data/luafiles514/lua files/navigation/navi_*_krpri.lub` responses equals its
Taiwan source.

### Root acceptance gates (not claimed here)

Fresh client entry with the six missing-file errors gone and no new error;
queries 許書生 and 骷髏頭 find their Chinese targets; 波利 unaffected; the
ordinary route izlude 20,98 → prt_fild08 367,212 works; enabled overlays and
newest progress intact through save, re-entry and full relaunch. No GM/SQL
shortcuts; IME, audio, settings and network unchanged.

### Rollback

- Alias mod: switch it off in Settings → Mods (or list it in `disabled.txt`),
  restart, confirm the six requests return to their previous behaviour; remove
  the folder only after that. Switching it back on demonstrates off/on.
- Bundle: stop using the developer root (launch without `RAGNAROKMAC_ROOT`),
  confirm the served `Online.js` is again the preserved original
  (`80f4371c…33ea`). The installed runtime was never edited, so nothing is
  restored over it.
- Keep the current saved state; the fresh backup is for recovery only, not a
  rollback step. Git reverts source only; it restores no app, save or
  installed file.

## Limits

- Not executed by the author: the repaired JavaScript (only `node --check`),
  the Lua serializer, Wasmoon/WASM, the real codec, the six stock chunks and
  any queue/task interleaving. Root runs the actual extracted loader, native
  Lua and full six-table value oracle on both submissions.
- The 88 corrupted occurrences and the full-value baseline (694399 values)
  come from root's earlier audit; this generator does not re-measure them.
- A string consisting only of a UTF-8 BOM under a UTF-8 `userCharpage` would
  decode to nothing and be refused; Big5 is unaffected.
- The serial plan above is plan-only. Developer-root delivery is unverified in
  the installed binary. Complete world, episode, story, Traditional Chinese
  and solo/offline gates remain open.
