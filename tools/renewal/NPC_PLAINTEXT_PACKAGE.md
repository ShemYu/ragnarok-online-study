# T05.006 NPC plain-text package generator

Worker candidate for the [frozen brief](../../docs/project/tasks/T05.006.md). It generates one fixed private folder package around the root-qualified loader, the unchanged NPC core and the pinned dictionary. **Generating a package does not complete T05.006.** The task completes only after root qualifies a package and runs the backed-up installed pilot below. Nothing in this file is root verification, native or live evidence, or user acceptance. Full Chinese UI and story, formatting, templates, names, real IME, and world, episode, solo and offline qualification remain open.

| File | Role |
| --- | --- |
| `npc_plaintext_package.py` | Fixed generator (Python 3.9 standard library only) |
| `test_npc_plaintext_package.py` | G01–G06 `unittest` groups |
| `NPC_PLAINTEXT_PACKAGE.md` | This runbook and the root serial plan |

## Command

```sh
python3 -I -B tools/renewal/npc_plaintext_package.py LOADER_SOURCE CORE_SOURCE DICTIONARY_SOURCE OUTPUT
```

The four positional arguments only **locate** bytes. Name, version, metadata, pins, entry text, URLs and policy are constants in the generator, copied from the frozen `package-profile.json` (1531 bytes, SHA-256 `53f3ea8b…8da`). G01 checks that the constants equal the frozen profile. There are no options. Any argument that starts with `-`, or a count other than four, exits 2 with usage text.

| Role | File | Bytes | SHA-256 |
| --- | --- | --- | --- |
| loader | `dictionary_loader.mjs` | 22648 | `5ef583b6bf7d15c285dc6c3ebde7c6e51ba1f8a9523228a2dd44a777e0a15ab4` |
| core | `npc_plaintext_adapter.mjs` | 14236 | `0dc77140f921925f7079dfdeaf6f674931f66a726f97b41bfab5f6b8e7f0089c` |
| dictionary | `dict.json` | 19706353 | `be3825ca74db764f8d9ffbea9ba8f15ac17b1fd5bde49975d4b36c59ba704fc2` |

### Path rules

- Paths may be absolute or relative to the current directory. A path is refused if it has an empty, `.` or `..` component (so `a//b`, `a/./b`, `a/../b` and a trailing `/` are refused), or if any existing component is a symbolic link. `.tools` is an ordinary name.
- Each source must be an existing regular file, reached without links. It is never opened if `lstat` shows otherwise, so a FIFO cannot block the generator.
- OUTPUT's parent must be an existing directory. OUTPUT itself must not exist in any form: file, directory, empty directory, FIFO or dangling link. OUTPUT `/` is refused.
- Overlap is refused. Two roles may not name the same path or the same file (device and inode), and OUTPUT may not lie at, inside or around a source path.

### What a run does, in order

1. Resolves and lstat-checks the paths, then reads the generator's own source. That read is bounded to 1 MiB, uses a regular descriptor and records no absolute path.
2. Opens each source once with `O_NOFOLLOW` and keeps the descriptor open for the whole run. It requires a regular descriptor whose device, inode, size, mtime, ctime and type match `lstat` of the path, and a size equal to the pin. The loader and core are read in full (capped at 1 MiB) and compared with their pinned length and SHA-256. All of this happens **before** OUTPUT is created.
3. Creates OUTPUT and the two inner directories exclusively, then sets mode 0700 explicitly so that any umask, including 0777, gives the fixed modes. Each file is created with `O_CREAT|O_EXCL|O_NOFOLLOW` and set to 0600 with `fchmod`. Each write loops until every byte is written. A write that returns 0 or an invalid count fails; a short write is resumed.
4. Copies the dictionary from its single source descriptor in 1 MiB reads, never more than the bytes still due. Each chunk is hashed and written immediately. The run fails if the source reaches EOF early, has an extra byte at the EOF probe, or has a streamed SHA different from the pin. The dictionary is never collected in memory, decoded, parsed or normalised.
5. Runs `fsync` and then `close` on every written file, then reopens it for reading and checks: same inode, regular file, mode 0600, exact size and a streamed SHA-256. The source descriptors and paths are re-checked for stable identity, and the hashes of each copy must equal its source.
6. Writes `package-manifest.json` and reads it back, then checks that the tree has exactly the fixed directories (0700) and files (0600).
7. Writes `COMPLETE.json` as `.COMPLETE.json.partial`, reads it back, hard-links it to `COMPLETE.json` (a link never replaces an existing entry), removes the partial name, reads the final name back and checks the tree again. Only after all of that does it print the success line.

On **any** failure, including KeyboardInterrupt, the generator closes every descriptor it acquired. It then removes, in reverse order, only the entries this run created, matched by device and inode. If the OUTPUT root is no longer the directory this run created, nothing under it is touched and the diagnosis says so. Foreign entries inside the owned tree are kept, and so is their parent; the diagnosis says that cleanup was incomplete. A completion failure therefore leaves no usable completion marker. Power-loss atomicity, directory fsync and protection against concurrent adversarial tree changes are **not** claimed.

### Output

```text
OUTPUT/                          0700
  package-manifest.json          0600
  COMPLETE.json                  0600, finalized last
  npc-plaintext-zh-tw/           0700   <- the only folder that is a mod
    mod.json                     0600
    client/                      0700
      index.js                   0600   export { default } from './dictionary_loader.mjs';\n
      dictionary_loader.mjs      0600   exact qualified loader
      npc_plaintext_adapter.mjs  0600   exact qualified core
      dict.json                  0600   exact streamed dictionary
```

The generator writes every JSON file as `json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)` plus one LF, encoded as UTF-8 with no BOM. The files contain no timestamps, private paths or dictionary text.

- `mod.json` is exactly the profile's `mod_json`: name `npc-plaintext-zh-tw`, version 1.0.0, author `Project local integration`, a Traditional Chinese description, `"default":"off"` and `requires {app:"=1.6.3", era:"renewal"}`.
- `package-manifest.json` has exactly these keys: `schema` 1, `task` "T05.006", `profile` "npc-plaintext-package-v1", `generator` `{file,bytes,sha256}` (the executed generator source), `package`, `acquisition`, `sources` and `entry` (the profile values verbatim), `directories` (`.`, the mod folder and its `client`, each with mode 0700, in that order) and `files`. `files` holds five `{path,bytes,sha256,mode:"0600"}` records, sorted by ASCII path and relative to OUTPUT. The manifest does not list itself or the completion marker. The `entry` block declares the source-profile mapping. It is not proof of native staging.
- `COMPLETE.json` is `{schema:1, task, profile, state:"complete", files:5, manifest:{file:"package-manifest.json", bytes, sha256}}`. It binds the closed, read-back manifest. It is publication evidence, not a sign that the package works in the game.
- On success, stdout is one compact JSON line: `{"files":5,"manifest_sha256":H,"output":OUTPUT_BASENAME,"package":"npc-plaintext-zh-tw","state":"complete","task":"T05.006"}`. On failure the exit status is non-zero (1 for a refusal or failure, 2 for usage), stdout is empty, and stderr carries one line with a bounded diagnosis. That line has no traceback, input contents or private absolute path.

The only bytes that depend on the provider are `generator.bytes` and `generator.sha256`, plus the manifest and completion hashes that follow from them. Two runs of the same generator produce byte-identical trees.

## Tests

```sh
T05_006_INPUT_ROOT=<frozen input root containing frozen-inputs.json> \
  python3 -I -B tools/renewal/test_npc_plaintext_package.py -v
```

`T05_006_WORK` sets where the private scratch directories go. The default is `.tools/renewal/T05.006/test-work`, which is ignored by git and must have no symlink ancestors. Each test creates a fresh `t-*` directory and removes it afterwards. **Without `T05_006_INPUT_ROOT`, the tests that need the real inputs report as skipped and are unrun.** Those are all of G01 and the real-package G06 case. The counts are not an oracle.

| Group | What it exercises |
| --- | --- |
| G01 Pinned generation | The frozen manifest SHA and the profile are compared with the generator constants. The actual CLI runs twice, with absolute and with relative source paths, on the real pins. It checks the exact stdout schema, a byte-identical repeat, source size, inode, mtime and SHA unchanged afterwards, bounded 1 MiB reads and no `json.load`/`loads` while the production dictionary is copied. |
| G02 Package/evidence | Exact tree, modes, bytes, canonical JSON with key sets and order, manifest and completion bindings, and no extras. Repeated under umask 0777 and 0000. The literal default re-export (no `export *`). No bypass options, and fixture pins refused by the production CLI. |
| G03 Refusals | OUTPUT as an existing file, populated directory, empty directory, dangling link or FIFO. Missing or non-directory parent, `.`, `..`, empty and trailing-slash components, a symlinked ancestor, and `/`. A source that is a final or ancestor symlink, a directory, missing, or a FIFO (run in a subprocess with a timeout). Oversize, wrong length, wrong hash, a pin above the 1 MiB cap. The same path, the same inode through a hard link, OUTPUT at or under a source. Each refusal leaves no output, unchanged sources, no leaked descriptor and no private path in the message. |
| G04 Stream/readback | Truncated stream, an extra byte at the EOF probe, an actual append during the copy, changed same-length content, the source path replaced mid-run, and corrupted written bytes caught by read-back. Bounded read and write sizes with a small patched chunk, and no parse. None of these complete. |
| G05 Publication failures | Writes capped at 3 bytes still finish byte-exact. A zero-byte write and ENOSPC fail. `fsync` EIO is injected at each of the seven files. Close EIO after a real close. Completion `link` failure, completion read-back failure, manifest read-back read failure. A source `open` failure after earlier opens (descriptors released). KeyboardInterrupt mid-run. OUTPUT replaced by a foreign directory (preserved and reported), and a foreign file planted inside the owned tree (kept and reported). A `main()` failure prints nothing to stdout and no traceback. |
| G06 Handoff/staging profile | A **source-profile model** that executes no JS, stock code or native staging. It checks all five package files and maps the four `client/` files to `plugins/npc-plaintext-zh-tw/`. It checks that the config path `plugins/npc-plaintext-zh-tw/index` plus `.js` and the loader-relative `./npc_plaintext_adapter.mjs` and `./dict.json` resolve inside that set. It checks that `mod.json` stays at the mod root and is not staged, and that the folder name equals the manifest name. Negative cases: missing `index.js` (nothing staged), four non-default entries (export-star, no LF, import-then-export, absolute path), an extra client file, `mod.json` copied into `client/`, `default:"on"` and a renamed folder. |

The model follows the pinned sources. In mods.rs `read_manifest` and `scan`, the folder name is the identity, `default:"off"` stays off unless explicitly enabled, `requires` accepts only `app`, `era`, `mods` and `client`, and `=1.6.3` is an exact rule with a numeric prefix and suffixes dropped. In assets.rs `overlay_mods`, `client/` is copied to `plugins/<name>` only when `client/index.js` is a file, and the generated `Config.local.js` entry is `'<name>': { path: 'plugins/<name>/index', pars: {…} }`. In PluginManager.js, the entry is resolved against `document.baseURI` and `.js` is appended. In PluginLoader.mjs, the module's `default` must be a function. RemoteClient (http.rs) serves `.js`/`.mjs` as `text/javascript; charset=utf-8` and `.json` as `application/json; charset=utf-8`, and may gzip them. These observations come from reading the source, not from running it.

## Root serial plan (root only; nothing here was executed by the worker)

Root compares both submissions first: complete source, suites, CLI and negatives, every file, the canonical manifest and the completion. Root then selects one package and integrates or corrects it under the workflow. **Only that one package is deployed, serially.** Do not run two live deployments. Keep internet, audio, IME, other mods and settings as they are. Use the supported app lifecycle only; no global cache or network changes, and no GM or SQL shortcuts.

### R0 Generate and pin the selected package (source only)

```sh
git status --short && git rev-parse HEAD                    # selected, integrated commit
P=<frozen input root>
python3 -I -B tools/renewal/test_npc_plaintext_package.py -v   # with T05_006_INPUT_ROOT=$P
python3 -I -B tools/renewal/npc_plaintext_package.py \
  "$P/tools/renewal/dictionary_loader.mjs" "$P/tools/renewal/npc_plaintext_adapter.mjs" \
  "$P/.tools/renewal/translation-source-preparation/source/plugin/npc-live-translate/dict.json" \
  .tools/renewal/T05.006/root-package-1
```

Record the exit status, stdout, `COMPLETE.json`, the manifest SHA, and all five file sizes, hashes and modes. Independently recompute and compare: stream-hash every file, re-serialize both JSON files, and diff the tree against the brief. Confirm that `npc-plaintext-zh-tw/` holds only `mod.json` and `client/`, with four files in `client/`. Never edit the generated folder by hand. If it is wrong, fix the generator and regenerate into a new OUTPUT name.

### R1 Detached actual entry (before any installed mutation)

Use a fresh owned loopback origin, a fresh page and a nested or different-base page URL. Map the generated `client/` tree to `plugins/npc-plaintext-zh-tw/` and import the **actual** `index.js` default through the qualified API1/core fixture pattern. For the entry, loader, core and dictionary, record status, final URL, MIME and decoded SHA. Confirm the fixed module-relative dictionary request, then loading → actual core ready → dispose. Check the named plain hits, the unknown and formatted fallbacks (pilot-samples L01/L02/L03/D01), and that input and button identity, value, click and order are unchanged. Then inject a missing entry, a missing core and a missing dictionary. Each must give a sticky outer error or a handled failed status. Remove each injection and record that honestly. Close the owned server and page. This transport was written for the test. It is not Rust or Electron staging.

### R2 Fresh full backup BEFORE installation

Fresh installation from the UI runs `mod-enable` even though the manifest says `default:"off"` (electron/main.js `switchOnInstalled`). There is therefore no window where the package is installed but off, and no "install first, back up later". Use the supported controlled save, logout and shutdown procedure, then take a fresh full backup labelled **H or later**. It must preserve the newer saves, mods, settings, the item overlay and the existing story overlay (`tw-carocc-pilot`). Verify the actual archive exists, its hash, that it can be read, and the applicable tested recovery reference. A closed tab or a health response does not prove a flushed save. Never restore an older A–G backup over newer progress. Asset-transaction recovery is not a save backup.

### R3 Supported serial install

1. Confirm that no installed mod folder named `npc-plaintext-zh-tw` exists (there must be no collision). Record the current mods list and enabled/disabled state.
2. In Add mod from folder, select **only** `OUTPUT/npc-plaintext-zh-tw/`, never OUTPUT itself (the envelope is not a mod). Expect "Installed npc-plaintext-zh-tw." with no refusal note, and confirm that the mod is listed as on.
3. Apply and restart through the supported lifecycle, then open a fresh game page.
4. Record the actual generated registration, which should be `Config.local.js` containing `'npc-plaintext-zh-tw': { path: 'plugins/npc-plaintext-zh-tw/index', pars: {  } }`. Record the identities staged under `plugins/npc-plaintext-zh-tw/` (four files, no `mod.json`). For each of `index.js`, `dictionary_loader.mjs`, `npc_plaintext_adapter.mjs` and `dict.json`, record HTTP 200, final URL, MIME and decoded SHA, which must equal the manifest. Record the actual core readiness, including the Chinese "ready" status. **Disk hashes alone are insufficient.** A query string, no-store or a hard reload does not bypass the RemoteClient server LRU. Use the controlled process lifecycle instead. Do not infer that the binary matches the source from the app version or the unexplained checksum file.

### R4 Ordinary live sample (pilot-samples.json)

1. Check eligibility at runtime: an ordinary Novice below base 15 in Captain Carocc's initial-menu branch at izlude 198,213. If the current character is not eligible, use a vacant ordinary trial slot after R2, and keep the user's character. Never edit quest, class, level or currency.
2. Choose menu item 2 and confirm L01 reads `不過因為出了點問題，現在正在休息。`. Press Next once and confirm L02 reads `如果要去艾爾貝塔或拜拉島，請找旁邊的水手。`. Then Close. Only these previously English body lines count towards this package. The existing Chinese opening, menu and Hello lines belong to the earlier eight-literal pilot and must stay unchanged.
3. L03 must keep its source text and native `^4d4dff` formatting and is **not** counted as translated. Check menu choice, Next, Close and their order, and that no errors appear.
4. Do an ordinary save, re-entry, and a full relaunch with the earned state preserved. Detached misses and input-safety checks do not prove real IME or an unavailable live input dialog.

### R5 Off/on rollback

1. Disable **only** `npc-plaintext-zh-tw`, then use the supported Apply/rebuild/cycle and a fresh page. Expect L01 and L02 back in baseline English, the older overlays and progress kept, and no registration, init or request for the new package. An old resource URL need not return 404.
2. Re-enable it through the same lifecycle. Expect the exact served identities, readiness, translations and progress to return.
3. Close the owned fixtures and processes. Record any retained trial state.

### Rollback and recovery

- **Installed state:** disable as in R5, or remove the mod folder through the supported Remove action, then Apply. Git does not restore installed files, saves or databases. Recover progress only from the R2 backup using its tested procedure, never from an older backup and never by automatic DB restore.
- **Source:** `git revert <candidate or integrated commit>` on the coordination branch. Generated packages and reports under `.tools/` are ignored, private, and deleted by hand.

## Limits

- Only exact plain-text dictionary hits are translated, through the unchanged core. Colours, links, templates, names, UI, story coverage, real IME, offline and solo use, and every other map, NPC and quest are untested here.
- Worker evidence covers generation and a source-profile model only. No JS, browser, native staging, served HTTP, install or live game was run. The R1–R5 gates are unrun.
- Files are created through ordinary paths, with no `dirfd`-relative hardening. Concurrent adversarial changes and power loss are out of scope, as is directory fsync. On macOS the files may carry system extended attributes; these are not package content.
