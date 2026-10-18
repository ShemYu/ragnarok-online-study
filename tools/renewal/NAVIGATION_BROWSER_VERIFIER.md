# Navigation browser verifier (T05.008)

A fixed, source-only generator for a **temporary** verifier on the local game
origin `http://127.0.0.1:3338`. It produces:

- one standalone page that audits, removes and HTTP-refreshes only the six
  recognized navigation cache copies, and
- two entry pages, one per server stage, that load `Online.js` only through a
  `<script type="module">` carrying the expected SHA-256 integrity, so the
  browser itself refuses any other bytes.

**Generating the pages and passing the authored tests does not show any cache
was cleared or that the game uses the right bytes.** Root owns every browser,
cache, server and save action; see [Limits](#limits). This addresses the
unqualified Chrome rollback check of
[T05.007](../../docs/project/reviews/2026-10-19-T05.007.md#original-server-rollback-passes-chrome-rollback-remains-unverified).
It does not translate content or establish the milestone.

## Command

```sh
python3 -I -B tools/renewal/navigation_browser_verifier.py API_HTML OUTPUT
```

- `API_HTML`: the pinned production bootstrap `api.html` (5848 bytes, SHA-256
  `9a22f871…5662`) holding exactly one `import('./' + scriptFile)`. Links,
  directories, FIFOs and other specials are refused.
- `OUTPUT`: a new path whose parent exists. It must not exist, not even as a
  dangling link.

Python 3.9 standard library only. The frozen `profile.json` (2153 bytes,
SHA-256 `6629304c…fe97`) is embedded verbatim and checked at import. The
argument only locates the bootstrap bytes: no pin, path, origin, element ID or
URL can be overridden, and no environment variable is read. The authored
`navigation_browser_cache.mjs` must carry the same pins. Every input is read
and validated before `OUTPUT` is created.

Success prints one JSON line `{"files": 5, "manifest_sha256": …, "output":
<basename>, "state": "generated", "task": "T05.008"}`. A refusal or failure
exits 1 with a one-line, path-free diagnosis and no traceback. A wrong
argument count or a leading `-` exits 2 with usage. Write, fsync and file-close
failures attempt to remove only files this run created. A directory-close failure is reported with a bounded refusal and is
never retried with uncertain descriptor ownership; failed output may remain,
even if every artifact was written. Do not consume a failed output. Every
existing output, including a failed tree, is refused rather than overwritten.

## Output

```text
OUTPUT/                         0700
  T05_008-cache.html            0600  standalone cache page
  T05_008-cache.mjs             0600  navigation_browser_cache.mjs, byte for byte
  T05_008-original-entry.html   0600  bootstrap pinned to the original bundle
  T05_008-repaired-entry.html   0600  bootstrap pinned to the repaired bundle
  verification-manifest.json    0600  written last
```

The manifest is canonical JSON (`ensure_ascii=False, sort_keys=True,
indent=2`, LF). It holds schema 1, task, profile name and SHA-256, origin, the
source `api.html` size/hash, the module size/hash/SRI, both bundle pins/SRI,
and the size/hash of each of the four browser files. These files are not a
completion marker. Output is deterministic for the same inputs. Keep it
private: it stays under the ignored `.tools/` tree and is never committed.

## Entry pages

Every bootstrap byte outside the one import expression is preserved. The
tests compare the full prefix and suffix. The expression becomes an inline
expression that yields a Promise, so the bootstrap's own `.then` (preloader
removal) and `.catch` stay in force. Config.js/Config.local.js loading and
merging, `?app=` handling and normal login are untouched. So are game code,
worker URLs, language and preferences. When `loadApp` evaluates the
expression, it:

1. Creates or reuses a visible `<pre id="T05_008-entry-status">`. This is a
   fixed bottom-left overlay that ignores pointer events. It shows the JSON
   record `{task, stage, state, expected_sha256, integrity, module_url,
   reason}`, written with `textContent` only.
2. Refuses visibly (`state: failed`, Promise rejected) in any of these cases:
   a second invocation, any `scriptFile` other than `Online.js`, an origin
   other than `http://127.0.0.1:3338`, missing `crypto.getRandomValues`, a
   browser without script `integrity` support, or a resolved URL off the
   origin.
3. Builds one same-directory URL,
   `Online.js?t05_008_sha256=<expected>&t05_008_nonce=<32 hex>`. The nonce
   comes from the browser CSPRNG, so the module-map key is always new.
4. Creates one `<script type="module" crossorigin="anonymous"
   integrity="sha256-…">` and registers `load` and `error` before inserting
   it. The original page uses `sha256-gPQ3HMja…M+o=` (original bundle,
   13166284 bytes). The repaired page uses `sha256-a6hUy2ex…TC8=` (13172839
   bytes).
5. Sets `loaded` and resolves only on the script's `load` event. The `error`
   event (fetch failure or integrity mismatch) gives `failed` with reason
   `load-or-integrity-error`. A window `error` event whose `filename` is
   exactly the module URL, which means evaluation threw, gives `failed` with
   reason `evaluation-error`. A later event cannot change a settled record.
   The record never shows `loaded` before load or after a rejection.

There is no Blob URL, `eval`, `new Function` or separate fetch→hash→import.
The browser enforces integrity on the actual executed resource. Root opens
each page as `T05_008-<stage>-entry.html?app=ONLINE`, placed beside `api.html`
and `Online.js`.

## Cache page and module

`T05_008-cache.html` has the four controls `inspect-cache`,
`remove-verified-cache`, `refresh-http-original` and `refresh-http-repaired`,
all disabled until the module binds, plus the JSON report
`T05_008-cache-report`. Its one inline classic script refuses a foreign
origin. It then loads `T05_008-cache.mjs?t05_008_sha256=<authored
sha>&t05_008_nonce=…` as a module with that file's SRI, so switching candidate
files cannot silently run an old cached controller. If the module fails to
load, fails its integrity check, throws during evaluation or never binds, the
loader shows a visible failure. The page imports no game, UI or Preferences
module and contacts no external URL. It writes no storage or cookies and
sends no telemetry. Nothing runs automatically.

`navigation_browser_cache.mjs` exports a side-effect-free core,
`createVerifier(adapters)`, plus fixed pins (`ORIGIN`, `TARGETS`, `BUNDLES`,
`IDS`, `CODES`). Importing it in Node does nothing. `bindBrowser(window)` runs
only inside a document marked `data-t05008="cache"` that holds the report
element, and it uses the real browser APIs with the fixed pins. The core's
second argument is an internal test seam for tiny authored pins and
timeouts. No page or CLI input reaches it.

### Every action

- **Single flight.** The controls lock while an action runs, a click on a busy
  page is ignored, and the core itself refuses a concurrent call with `busy`.
  The report switches to `running` at once. A late result from an older
  action is never rendered over a newer one.
- **WebStorage guard.** Before and after each action, the page reads
  `localStorage` and `sessionStorage` twice. It sorts the `[key, value]`
  pairs, serializes them as JSON (unambiguous) and reports only `count` and
  `sha256` per area. An unavailable, throwing or unstable read refuses the
  action. A fresh unchanged-storage guard also runs immediately before each
  file removal and alias request, after their asynchronous preflight work.
  Changed storage stops the next mutation and is reported as `storage-changed`,
  never as success. No key, value, cookie, credential, exception message or
  stack is ever rendered. This checks WebStorage equality only. It does not cover
  cookies, IndexedDB or any filesystem file it does not read.
- **Finite outcomes.** Each report has `state`, one of `inspected`,
  `removed-verified`, `refreshed-verified`, `refused`, `failed` or
  `uncertain`. It also has `code` from the fixed `CODES` list, the fixed
  paths, counts, statuses, sizes, hashes and `lock`. Nothing says PASS.
- **Uncertainty lock.** A callback or fetch that times out leaves a pending
  token until the real callback or promise settles. While any token is
  pending, no mutation can start, and a timed-out fetch is also aborted. An
  action that issued a delete or a reload fetch and did not fully succeed
  sets `mutation_locked`. Only a later clean inspection releases it: one
  that began and ended with nothing pending, read all six as matching or
  missing, and kept storage unchanged. Inspection alone never releases the
  lock while a callback is unresolved. Nothing is retried blindly.

### Filesystem audit and removal

The page feature-detects `requestFileSystem`/`webkitRequestFileSystem` and
uses `TEMPORARY` only. It opens only the six exact profile paths, under
`data/luafiles514/lua files/navigation/`: `navi_{map,mob,npc,link,
linkdistance,npcdistance}_krpri.lub`. Every open uses `getFile(path,
{create:false})`. The page never creates a file or directory, never
enumerates, never calls `getDirectory` or `removeRecursively`, and never
touches PERSISTENT storage, IndexedDB, CacheStorage or browser-wide clearing.

`inspect-cache` classifies each target:

- `missing`: only a genuine `NotFoundError`, or a legacy FileError with code
  1 and no conflicting name.
- `match`: `isFile` true and `isDirectory` false, `fullPath` exactly
  `/<path>`, the expected `name`, `File.size`, `ArrayBuffer.byteLength`, and
  the SHA-256 all match the pin.
- `mismatch`: identity, size or content differs. Unknown content is never
  replaced or normalized.
- `failure`: a directory, `TypeMismatchError`, security or read error,
  timeout or unsupported API.

`remove-verified-cache` first re-reads and validates all six. It refuses
before the first delete unless every target is matching or missing and
storage is stable. Immediately before each present target's file-only
`entry.remove()`, the page revalidates that target, and a change stops the
run. Each callback and error is awaited. Afterwards the page independently
reopens all six and requires genuine absence plus unchanged storage before
reporting `removed-verified`. Missing targets are neither created nor
deleted, and parent directories and other files are never removed. A partial
or timed-out removal stays visible (`uncertain`/`failed`) and locks further
mutation. Removal is not atomic, and the report never pretends it is.

### Narrow HTTP refresh

The refresh is separate from removal. It requires all six filesystem copies
to be missing: a matching copy that is still present refuses the refresh. It
runs these steps in order:

1. **Preflight.** It fetches the same-directory `Online.js?t05_008_preflight=<nonce>`
   with `cache:'no-store'` and a bounded read. The body must equal the
   selected stage's exact size and SHA-256. This checks current server bytes
   only, not what any page executes. A wrong stage, redirect or error stops
   the refresh before any alias request (`bundle-stage-mismatch`, with
   `preflight.code` giving the cause).
2. **Reload.** It fetches each of the six exact aliases with
   `cache:'reload'`. The alias is the origin plus `/` plus each path segment
   URI-encoded, as in `FileManager.getHTTP` with `remoteClient: '/'`.
3. **Default.** It then makes an independent `cache:'default'` fetch of every
   alias.
4. **Absence recheck.** All six filesystem copies must still be absent.

Every fetch uses `redirect:'error'`, `credentials:'same-origin'` and an abort
signal. The fetch/read timeout is an inactivity limit per operation, not an
overall response deadline. Oversized-body cancellation is awaited with the
same settlement tracking: rejection is handled, and a timed-out cancellation
keeps mutation locked until it settles and a later clean inspection succeeds.
A response must have `redirected === false`, exactly the requested `url` and `type === 'basic'`. Bodies are read with a cap: the pinned size for
a 200, or 64 KiB for a 404. They are never exposed. In original mode every
response must be 404, and a default-phase 200 is `stale-default-response`. In
repaired mode every response must be 200 with the exact size and SHA-256.
Any failure, changed storage or reappearing filesystem target is a failure,
or `uncertain` on a timeout. A successful refresh does not show that a later
game load consumes those responses.

## Tests

```sh
T05_008_INPUT_ROOT=<frozen input root> \
    python3 -I -B tools/renewal/test_navigation_browser_verifier.py -v
node --test tools/renewal/test_navigation_browser_cache.mjs
```

Python tests (14):

- **G01 (needs the frozen input root; skipped, never passed, without it).**
  Checks the eight frozen inputs and their modes without mutating them. Runs
  production CLI generation and checks the exact five-file tree, modes,
  canonical manifest, module bytes, full unchanged bootstrap prefix/suffix and
  per-stage digest/SRI. Also checks determinism, existing-output refusal and
  `node --check` of every generated inline script and the module.
- **G02 (authored fixture bootstrap through the internal profile seam).**
  Checks generation and syntax. Refuses a wrong size, hash or marker count,
  links, directories, FIFOs, absent input, existing output (directory, file or
  dangling link) and a missing parent. Validates every input before output is
  created. Refuses module pin drift. A write, short-write or close failure
  leaves no output. Also covers usage, and the production CLI having no
  profile override.
- **G03.** Checks the embedded profile identity, SRI encoding and entry
  expression shape: one module script, listeners registered before insertion,
  and no import/eval/Blob/config/storage tokens.

Node tests (48, authored doubles plus Node WebCrypto):

- **Module.** Import has no side effects. Production pins equal the
  generator profile, and alias encoding equals FileManager's. A source scan
  finds no forbidden API.
- **Inspection.** Genuine not-found classification. All six missing, all six
  matching. One target wrong in hash, size, reported size, type, full path or
  name. A directory or `TypeMismatchError`. Genuine missing versus security
  and read errors. Unsupported API, wrong origin, and unavailable, unstable or
  changed WebStorage, with privacy checks on every report.
- **Removal.** Full removal with revalidate→remove ordering. Missing targets
  untouched. Change before delete, both before and after earlier deletes.
  Delayed callbacks. Partial removal error with no retry. Remove timeout:
  pending, locked, no unlock by inspection until settled, then unlock by
  fresh inspection. A lookup that never settles. Reappearance after removal.
  Storage changed during removal. Concurrent actions.
- **HTTP.** Original success (13 requests in order, no body exposure, fresh
  nonce). Repaired success. Wrong bundle stage before refresh. Filesystem not
  absent. Stale default 200. Wrong status or content. Redirected, foreign or
  opaque response, fetch error and oversized body. Changed storage and
  reappearing target. Fetch timeout with abort and pending. Bad mode,
  missing fetch and foreign preflight base.
- **Generated loaders,** run in `node:vm` over a minimal DOM double. One
  SRI-pinned module script per stage, with listeners before insertion, no
  early success and fresh nonces. Load error and evaluation error rejection
  with no later success. Refusal of other scripts, wrong origin, missing
  crypto or SRI support, and duplicates. The cache-page loader's authored-byte
  SRI URL, plus error, unbound and foreign-origin failures. Browser binding:
  foreign origin refused, no automatic action, controls locked while running.

The Node tests execute only the authored module and the authored generated
expressions. They never run the pinned bootstrap, game code, a browser, a
real cache or the network.

## Limits

NOT RUN by workers, and owned by root:

- Native browser SRI refusal of a mismatched bundle and correct-bundle loading
  for both entry pages.
- Native behavior of the legacy filesystem API on the actual six copies:
  read-only inspection, then backed-up removal.
- Real HTTP-cache effect of `reload`/`default`.
- OFF missing-navigation behavior and ON Chinese queries in a fresh client.
- Newest-save and re-entry checks, protected-state comparison, and removal of
  the temporary verifier files.

Mocks cannot prove any of these. Before any mutation, root must close or
navigate away every old game document and worker so they cannot repopulate
the cache. Two worktrees do not isolate browser cache or the app database.
WebStorage equality says nothing about cookies or unread filesystem files.
This verifier does not establish complete cache clearance, offline
readiness, full Chinese coverage or world readiness.

Root regression additions R01–R05 cover storage changes during the full cache
precheck, first target revalidation and bundle preflight (zero mutation),
a later storage change stopping the next alias request, rejecting cancellation
without an unhandled error, and pending cancellation remaining locked through
inspection until real settlement. The Python directory-close control requires
one bounded failure, no retry and refusal to reuse the retained failed tree.
These remain authored checks; the browser/cache/save gates above stay separate.
