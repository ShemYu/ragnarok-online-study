# T05.005 dictionary loader and detached native fixture

Worker candidate for the [frozen brief](../../docs/project/tasks/T05.005.md). It is a loader and a private fixture. It is not a package, a mod.json, client staging, an installation or a live pilot. It does not cover full Chinese UI, colours, links, templates, names, story or offline use. Nothing in this file is root verification or user acceptance.

| File | Role |
| --- | --- |
| `dictionary_loader.mjs` | Client API 1 wrapper that statically imports the unchanged `./npc_plaintext_adapter.mjs` |
| `test_dictionary_loader.mjs` | Node built-in tests using authored doubles, plus builder runs and refusals |
| `dictionary_loader_fixture.py` | Builds the private detached browser fixture and its loopback server script |
| `DICTIONARY_LOADER.md` | This runbook |

## Interface

```js
import initialize, { createInitializer, createOwnedStatus, ERROR_CODES, STATUS_TEXT, jsonMediaType } from './dictionary_loader.mjs';
const init = createInitializer({ initializeCore, moduleURL, pageURL, expected, timeoutMs,
                                 fetchImpl, digestImpl, parseImpl, statusFactory });
const handle = init(parameters, api);   // or initialize(parameters, api)
// handle: frozen { dispose(), ready: Promise<'ready'>, diagnostics() }
```

- The construction values are trusted and are validated when the factory is created. `expected` is `{bytes, sha256}`, where bytes is a positive safe integer and sha256 is 64 lowercase hex digits. `timeoutMs` is a positive integer. `moduleURL` and `pageURL` are absolute strings. The dictionary URL is always `new URL('./dict.json', moduleURL)`. It must use HTTP(S) and share the page's origin. The module URL and the target may not carry credentials, a query or a fragment. The page may carry a query or fragment.
- `initialize(parameters, api)` checks API 1 (`version === 1`, `on` and `cleanup` are functions) and the facilities it needs: URL, Uint8Array, AbortController, Promise, timers, `performance.now` and a TextDecoder that supports `{fatal:true}`. It throws a TypeError before any cleanup, subscription, status, timer or I/O work. **`parameters` is ignored**: it cannot override the URL, pin, deadline or any dependency.
- Production default: the imported core, `import.meta.url`, the actual `location.href`, the pin **19706353 bytes / `be3825ca…fc2`**, a **30000 ms** total deadline, native `fetch`, `crypto.subtle.digest('SHA-256', bytes)`, `JSON.parse` and `createOwnedStatus(document)`. The default also requires native fetch, WebCrypto, `document.body`, MutationObserver and `location`. Importing the module, or creating a factory, starts no work.
- The extra named exports are read-only helpers: the bounded code list, the Chinese labels, the media-type predicate and the owned status factory. They give the tests and the fixture something to check against. They are not a settings surface.

### Error codes

`ready` rejects with a `DictionaryLoaderError` whose `code` (and message) is one of `ERROR_CODES`:

| Code | Meaning |
| --- | --- |
| `API` | `api.cleanup` threw during registration |
| `STATUS` | The status factory threw or returned a malformed handle, or a status update threw |
| `CORE` | Core init threw, the core returned a malformed handle, or the core was not `ready` after the activation checkpoints (failed, disposed, stuck, malformed or throwing diagnostics) |
| `FETCH` | fetch threw or rejected. This covers network errors, `redirect:'error'` and abort |
| `HTTP_STATUS` | The status was not 200 |
| `REDIRECT` | `redirected !== false`, or `response.url` is not exactly the request URL |
| `MEDIA_TYPE` | The type is not `application/json`, optionally with one `charset=utf-8` parameter (case-insensitive, may be quoted) |
| `BODY` | There is no readable stream, `getReader` failed, or the single buffer could not be allocated |
| `READ` | `read()` threw or rejected, or returned something other than a result object |
| `CHUNK` | A chunk is not a plain same-realm `Uint8Array`, or it has zero length |
| `OVERSIZE` | A chunk is larger than the bytes still expected. This is checked before the copy |
| `TRUNCATED` | EOF arrived before `expected.bytes` |
| `DIGEST` | The digest threw or rejected, or the result was not a 32-byte ArrayBuffer |
| `IDENTITY` | The 64-hex SHA-256 differs from the pin |
| `DECODE` | The fatal UTF-8 decode failed |
| `PARSE` | `parseImpl` threw |
| `CONTAINER` | The parsed value is not a non-null, non-array object with an `Object.prototype` or null prototype |
| `TIMEOUT` | The total deadline passed, confirmed by the monotonic clock |
| `DISPOSED` | Reported by `ready` only: the loader was disposed before it became ready |
| `DISPOSE` | Reported by diagnostics only: a core or status disposer threw. The state stays `disposed` |

## Behaviour (authored policy, per the brief)

1. **Cleanup comes first.** The loader creates the dictionary Promise and the ready Promise, each with an internal rejection handler. Then it calls `api.cleanup(dispose)` synchronously. If that call disposes an already-dead scope, the loader returns the disposed handle and does no further core, status, fetch or timer work. Otherwise it creates one AbortController and the deadline, and calls `initializeCore({dictionaryReady}, api)` once. A malformed core handle fails with CORE. A handle returned after a reentrant disposal is itself disposed. Then the loader creates the status (`loading`) and starts the pipeline. Repeated `dispose` calls and later adoption by the manager do nothing.
2. **One request.** `fetchImpl(url, {method:'GET', mode:'same-origin', credentials:'omit', redirect:'error', cache:'no-store', signal})`. There is no retry, no fallback URL and no nonce. The response body is acquired first, so that every early refusal can cancel it. The loader then checks for status 200, `redirected === false`, an exact `response.url`, the media type and a readable stream.
3. **One buffer.** The loader allocates exactly one `new Uint8Array(expected.bytes)`, and only after the metadata checks pass. It reads one chunk at a time and checks each chunk's type and length, and its size against the remaining space, before copying. It requires EOF at exactly `expected.bytes`. Content-Length is never read. It never uses `text()`, `json()` or `arrayBuffer()`, and keeps no chunk array.
4. **Identity before interpretation.** One digest over that same buffer, a 32-byte result and all 64 hex digits compared. Then one fatal UTF-8 decode, after which the buffer reference is dropped. Then one `parseImpl(text)`, after which the text reference is dropped. Then an O(1) container check. Nothing enumerates, clones, freezes, normalises or builds an index of the dictionary. The exact parsed object resolves the core's `dictionaryReady`, and the loader drops its own reference to it.
5. **Activation.** After the handoff, the loader allows up to **8 zero-delay `setTimeout` checkpoints** inside the same deadline. At each one it reads only `core.diagnostics().state`. `ready` means success, `loading` means continue, and anything else fails with CORE. Still `loading` after the eighth checkpoint also fails with CORE. Then comes the ready status update, `state='ready'`, and `ready` resolves to `'ready'`.
6. **One terminal authority.** The first of failure, timeout or dispose wins. It records the timing of the stage it interrupted and clears the deadline and the checkpoint timer. It signals every pending `wait()`, which is a `Promise.race` against a halt Promise. It aborts the request and starts `reader.cancel()`, or `body.cancel()` if no reader exists yet, without awaiting it. It rejects the dictionary Promise, which fails the core before handoff, and disposes the core after handoff. It updates or removes the status, then rejects `ready`. Late fetch, read, digest or activation outcomes can never revive the loader or bring back its status. A deadline timer that fires early re-arms itself. TIMEOUT is reported only once `performance.now()` has actually passed the budget.
7. **Status.** The production node is one appended `<div role="status" aria-live="polite" data-t05-dictionary-loader>` holding one native Text node, styled through CSSOM only. Its labels are `繁體中文 NPC 字典載入中…`, then `繁體中文 NPC 純文字翻譯已就緒` (shown only after the core reports ready), or `字典載入失敗（CODE）`. A failure stays visible until disposal. Disposal removes only that node. Manager-ready, verified bytes or an English fallback never produce the ready label.
8. **Diagnostics.** Each call returns a fresh frozen snapshot of primitives: `state, phase, errorCode, receivedBytes, expectedBytes, coreState, requestMs, readMs, digestMs, decodeMs, parseMs, activateMs, totalMs`. The phase is one of `init|request|read|digest|decode|parse|activate|ready`. A stage's duration is set when that stage completes, or when it fails, times out or is disposed while running, in which case it is the elapsed time so far. Stages never entered stay `null`. `totalMs` is `null` while loading. It is fixed at the moment of ready, failure or disposal-while-loading. A later disposal keeps the ready total. The snapshot never contains the dictionary, its text, a DOM node, a URL, an ID or a stack. After a successful ready, a disposal leaves the resolved `ready` Promise as history. `diagnostics().state` is the authority on the current state. Disposal after handoff follows the core's rule: already translated text is not restored.

### Stated limitations

- The deadline is logical. It cannot interrupt a synchronous `TextDecoder.decode` or `JSON.parse`, CPU starvation, or a native WebCrypto digest that is already running. The overrun is detected after the call returns: D06 shows a parse running past the deadline and then failing TIMEOUT. AbortController does not cancel the digest or the parse.
- Memory is bounded only for the buffers the application owns. The browser may already hold the current native chunk, and WebCrypto may copy its input. At peak, the buffer, the decoded string and the parsed object can overlap. No memory or latency budget is claimed. D09 has to measure them.
- There is no host injection of a dictionary, base URL or report method. The "next plugin while loading" behaviour comes from the synchronous return. Manager-ready is not dictionary readiness.
- The source review does not prove the later game's routing, proxy/static shadowing, configuration or server LRU. `no-store` does not bypass that LRU. The RemoteClient binary/checksum mismatch noted in the root review stays unexplained.

## Node tests (worker-runnable)

```sh
node --test tools/renewal/test_dictionary_loader.mjs
```

The tests run only authored doubles and tiny authored bytes, with Node's WebCrypto, TextDecoder and JSON.parse. The core integration case uses the unchanged core with a minimal MutationObserver stand-in. One case starts a child Node process to show that importing the default starts nothing, and that calling it outside a browser throws before any work. The builder cases call the Python builder into a temporary directory. Expected outcome: every group D01–D08 and D10 passes, and **D09 is reported as skipped: `NOT RUN — ROOT ONLY`**. That skip is partial evidence, not a pass. These doubles do not establish browser fetch, stream, MutationObserver or CSP behaviour.

## Fixture builder

```sh
python3 -I tools/renewal/dictionary_loader_fixture.py \
    tools/renewal/dictionary_loader.mjs tools/renewal/npc_plaintext_adapter.mjs OUTPUT \
    [--dictionary-source <frozen-root>/.tools/renewal/translation-source-preparation/source/plugin/npc-live-translate/dict.json]
```

- The builder refuses: an OUTPUT that already exists (left untouched); a symbolic link in any source, output or ancestor path component; `.` or `..` in a path; a source that is not a regular file; a loader or core larger than 1 MiB (checked before reading); a core other than **14236 bytes / `0dc77140…089c`**; a loader whose only import is not the static `./npc_plaintext_adapter.mjs`, or one with a dynamic import; and a dictionary source of the wrong size (checked before OUTPUT is created) or the wrong SHA-256, which is checked while streaming and again on the copied file. After any refusal, the builder removes only the OUTPUT directory that this run created, confirmed by dev/inode, and prints no success summary.
- OUTPUT is created with mode 0700, and every file in it with 0600. `provenance.json` records the loader's and core's source bytes, SHA-256 and mode, every copy, the exact relative import, the generator hash, the CSP, the expected groups, the fault modes, the server allowlist, and every generated file's size, hash and mode. When `--dictionary-source` is given, it also records the external pin and the copied identity. The printed summary contains no absolute paths and no dictionary content.
- The production dictionary is only streamed, hashed and copied, never decoded, parsed or enumerated. The `full/` directory holds byte-identical copies of the loader and core beside `full/dict.json`. It is **detached fixture data**, not a supported-mod or staging proof.

Layout: `index.html` (landing page) · `pages/run/index.html` (the harness page, with `<base href="../../decoy/">`, so the page directory, the document base and the module directory all differ) · `boot.js` (a classic reporter that loads before any module) · `fixture/{reporter,doubles,harness,cases}.mjs`, `fixture/style.css` · `loader/` (the loader, the core and a tiny `dict.json`) · `broken/` (the loader without its core) · `decoy/dict.json` and `pages/run/dict.json` (decoys that must never be requested) · `case/*/dict.json` (tiny pinned cases) · optional `full/` · `server.py` · `provenance.json`.

The page CSP is `default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'`. img, font, media, object, frame, child, worker and manifest are all `'none'`, along with `form-action 'none'` and `base-uri 'self'`, which the nested page's decoy `<base>` needs. There is no inline script, no inline style and no favicon exemption.

## Root-only native run

Workers never start a listener or a browser. The root owns the process, port, page and teardown:

```sh
python3 -I OUTPUT/server.py 0        # binds 127.0.0.1 only and prints the page URL
```

`server.py` serves only its embedded allowlist from its own directory. It also answers a finite set of case endpoints under `/case/<name>/dict.json`. The static cases are tiny, bad-utf8, bad-json, scalar, array, null and unsafe. The generated cases are chunked, gzip, framing-short (Content-Length larger than the body), redirect (302 to the owned tiny path), stall-headers, stall-body (both finite, 8 s), delay (300 ms), wrong-mime, other-charset, status-500 and no-store-plain. Any other path returns 404. It is not a general file server, and nothing remote is contacted.

| Page | Expected |
| --- | --- |
| `/pages/run/index.html` | Groups D01–D08 and D10 pass and D09 shows `NOT RUN — ROOT ONLY`. The overall status is **INCOMPLETE** (yellow), never PASS |
| `/pages/run/index.html?full=1` (needs `full/`, fresh tab/origin) | D09 runs first, on the fresh page, then the other groups. **PASS** requires all 10 |
| `?fault=<mode>` for each of the 10 modes | The page shows FAIL, and that mode's ledger row shows **OBSERVED**, with its sink and primitive evidence |
| `?fault=<mode>&suppress=1` | The page shows FAIL, and the row shows **NOT OBSERVED** with a `missing-fault` diagnosis |
| `?fault=omitted-group&group=D10` (or another group) | The omitted group stays `not run`. The page can never pass |

What D09 records (as `window.__t05D09`, also shown in the notes):

- the diagnostics stage timings and the wall time;
- the resource entry's transferSize, encodedBodySize, decodedBodySize and duration, when available;
- `longtask` durations, when the browser supports them;
- the maximum timer lag from a 50 ms sampler;
- `performance.memory`, only when present, labelled coarse, non-standard and not a peak value.

Anything that is not available is marked `unobserved`. There is no forced GC and there are no thresholds. D09 cannot translate a production key, because the fixture never learns any key.

The ten fault modes and the evidence each needs (the mode name alone is never evidence):

| Mode | Required sink evidence |
| --- | --- |
| missing-loader | Dynamic import of `/absent/…` rejected, and a probe of that path returned 404 |
| missing-core | Import of `/broken/dictionary_loader.mjs` rejected, with the loader path returning 200 and the adjacent core 404 |
| csp-inline | A `securitypolicyviolation` event for `script-src(-elem)` with `inline`, and the inline flag never set |
| loader-reject | The loader's ready rejected with `HTTP_STATUS`, the state is failed and the Chinese failure label is shown |
| loader-timeout | The loader's ready rejected with `TIMEOUT` after a real elapsed time of at least 300 ms against the stalled endpoint |
| api-error | The API double's sink caught a listener error, after an ordinary translated append |
| cleanup-error | The API double's sink caught both a thrown cleanup and a rejected one, after an ordinary translated append |
| unhandled-rejection | The boot `unhandledrejection` sink holds the injected reason |
| zero-assertions | A real group (default D08) was recorded with 0 assertions and is failing |
| omitted-group | A real group (default D05) was never run and stays `not run` |

Negative pages leave D09 unrun. Their partial totals never count as a baseline. A same-page watchdog cannot preempt synchronous starvation, so the root's external tab teardown is still required. Stop the server and delete the fixture output when finished. Neither has any other state.

## Rollback

Source changes are reverted by reverting the candidate commit. The fixture and server are private and disposable. Stop the process, close the tab and delete OUTPUT. No installation, game, save, settings or cache state is involved.
