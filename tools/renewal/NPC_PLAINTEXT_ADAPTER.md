# NPC plain-text dictionary core (T05.004)

Root correction1.0.1 based on selected Claude `12cd6f3b3e202a350ec1de2765dc5a911cc2ff09`, unchanged integration1f18453, under the [frozen T05.004 brief](../../docs/project/tasks/T05.004.md) (SHA256 `7f40a6ce0b5a6fb4b00aeb66ecd032ca78de6b20d95e0a8070e76b99c782648a`, common base `981ee2b7a14b5ec4eb62e77ffcce57d50357eb24`). The preserved raw candidate remains unchanged. Internal Codex preparation is attributed separately in the [root review](../../docs/project/reviews/2026-10-18-T05.004.md). Root integrated requalification is underway; no installed/full-language or user acceptance is claimed.

The packaged engine calls `NpcBox.append()` **before** `NpcBox.setText()` and `NpcMenu.append()` before `setMenu()` (source `Engine/MapEngine/NPC.js` 35–37/109–111; packaged `Online.js` 340395–340398/340454–340456). An append-only translator therefore never sees ordinary dialogue. `npc_plaintext_adapter.mjs` is a client API 1 **core** that owns each allowlisted component root, observes only that root's first `.content` node with the browser's native `MutationObserver`, and rewrites the data of plain Text rows whose logical lines are exact own keys of a caller-supplied dictionary. Everything else is left alone.

This is one necessary part of the full Traditional Chinese goal, not that goal. English fallback for misses or unsupported lines is not full-language success.

## Files

| File | Role |
| --- | --- |
| `npc_plaintext_adapter.mjs` | The core: default `initialize({ dictionaryReady }, api)`; also exports `translateText`, `createCounts` and `LIMITS` for tests |
| `test_npc_plaintext_adapter.mjs` | Node built-in tests on authored DOM, MutationObserver, component and API 1 doubles; builder runs and negatives |
| `npc_plaintext_fixture.py` | Python stdlib builder for the detached native-DOM browser fixture |
| `NPC_PLAINTEXT_ADAPTER.md` | This runbook |

Node 24.20.0 and Python 3.9.6 standard library only. No packages, network or external AI.

## Inputs read

All 18 pinned inputs were re-hashed under the coordination root before use; every size and SHA-256 matched the brief. Read as source/data: `NpcBox.js/.html`, `NpcMenu.js/.html`, `InputBox.js/.html`, `NPC.js`, `GUIComponent.js` (append/remove), `ExtensionRuntime.mjs` (scope, `on`, replay, cleanup, `appendComponent`/`removeComponent`), `PluginLoader.mjs` (asynchronous adoption of a returned `dispose`), `PluginManager.js`, the packaged `Online.js` ranges above plus its `appendComponent`/`removeComponent` call sites (324582, 324606: append emits after `onAppend`; remove emits before `onRemove` and detachment), both review documents and the dictionary/manifest as data (221007 string pairs; top-level object). Nothing stock was imported or executed. Source revision pins: client `775f8847a8b09749d03c82fcb554e155401d1e02`, upstream `2c3b2612973fb8d0ae6ad366a2b298686f2404cb`, dictionary source `485ceb2c11104a37f0dd87f5cd2ce3d527f87982`.

## Core contract

**Interface.** `initialize(parameters, api)` runs **synchronously** and returns a frozen `{ dispose, diagnostics }`. It never awaits readiness, so later plugins are not blocked.

- `api.version === 1` (the number), `api.on` and `api.cleanup` functions, and a global `MutationObserver` function are required. Otherwise it throws a `TypeError` before any cleanup registration, subscription or DOM access.
- `parameters` must be a plain object whose own data property `dictionaryReady` is either a `Promise` (state `loading`) or a plain JSON object with `Object.prototype` or `null` prototype (state `ready`). Anything else — missing, `null`, string, array, `Map`, class instance, accessor-valued parameter, object with a function-valued own `then` (a thenable) — is `failed` and inert, with no subscriptions. A rejection, or a resolution to a non-plain value, moves `loading` to `failed`. Both handlers are attached at once, so no rejection is unhandled.
- `api.cleanup(dispose)` is registered **before** subscribing, so a loader that never adopts the returned handle, or adopts it after its scope was disposed, still cleans up. If the scope is already disposed, the runtime calls `dispose` immediately and the core skips subscribing. The handle exposes that same `dispose`; the loader registering it again is harmless. The core does not depend on any exact cleanup-registration count.
- Pending dictionary resolve/reject handlers are attached before that cleanup registration. An already-disposed scope therefore returns a disposed handle, attempts no later subscription, and still consumes a late rejection.
- Subscriptions: `ui:append` with `{ replay: true }` (the runtime replays its *current* registry in a microtask) and `ui:remove` with `{ replay: false }`.
- `disposed` is terminal: late resolves, rejections, replays and queued observer callbacks do nothing.
- This core never fetches, parses files, stores, caches globally, clones or iterates the dictionary. Per line it does exactly one `Object.getOwnPropertyDescriptor`; at readiness it reads one own `then`. The caller keeps the borrowed dictionary immutable while owned; the core never mutates it. A future JS wrapper/loader supplies `dictionaryReady`; a Promise-valued JSON plugin configuration is **not** claimed to be supported.

**Ownership.** Only descriptors named exactly `NpcBox` or `NpcMenu`, with an object `root` that has `querySelector` and a non-null `host`, are considered; anything else is ignored and counted. State is keyed by the stable `root` (every append hands over a fresh frozen descriptor) and captures `name` and `host`:

- One owner (one observer) per root; repeated descriptors for the same name/root/host are idempotent re-scans.
- While owned, a descriptor with another name or host on that root is ignored, and a mismatched `ui:remove` never releases the owner.
- The first `root.querySelector('.content')` is adopted. At most **8** roots are owned; a ninth is untouched until a later append arrives after capacity frees.
- `ui:remove` (emitted before the client's `onRemove` and detachment) disconnects the observer and drops the owner's root/host/content references and memo. Removed roots are inert even while still connected (`isConnected` is not an ownership test). A later fresh append starts a new generation.
- `dispose()` unsubscribes, disconnects every observer and releases every owner; calling it twice, or via both scope and handle, does nothing more.
- A content-only observer cannot see its own `.content` being replaced in the parent. On the next supported trigger (observer callback, append or readiness) the core notices that the root's first `.content` changed, **retires** the old content (disconnects, counts `stale`) and writes nothing there. Only a fresh append from the same name/host adopts the new content.
- No component setters/prototypes are patched; no body/document observer, polling, timers, event-listener changes or invented runtime APIs.

**Observation and writes.** For each owned content the core attaches `observe(content, { childList, characterData, subtree })` once ready, and scans on append, replay, readiness and every observer delivery. Before **every** write it rechecks: the core is `ready`; this owner is still the current owner of its root and not retired; the root's first `.content` is still the adopted node; the row is still a direct child of that content; the Text is still a direct child of that row; its data is still the value that was translated; and the row is still eligible. Only then is `text.data` assigned on that same node.

**Feedback and chains.** Per owner generation, a `WeakMap` remembers the data the core last wrote into each Text. If a node still holds exactly that output, it is not translated again (own observer delivery, replay, duplicates), so an output that is also a key (`A`→`B`, `B`→`C`) never chains. A distinguishably different foreign value is new input; the comparison is per whole Text, so a partial foreign edit of a multiline Text re-evaluates all of its current lines. Limits: a foreign write of the identical output string, or a revert to it, is indistinguishable and treated as the core's own; there is no memory across dispose/reinitialization or generations. The memo is weak, so replaced rows are collectable (checked under `--expose-gc`).

**No blanket restoration.** Removal and disposal never restore DOM text. Translated text may remain until the native component clears or re-renders (`NpcBox.onRemove` and `NpcMenu.onRemove` clear content natively; `NpcBox.setText` clears after Next/Close). Foreign nodes and controls are never rewritten to a snapshot.

## Eligible text and matching

- **Rows:** only direct child `div` elements of the adopted content; for `NpcMenu` the row must also have `data-index`. Every child of the row must be a Text node; any element (colour span, ITEM/NAVI link, control) or comment skips the **whole row**. Any `contenteditable` attribute on the row or an ancestor up to the component root, or `isContentEditable === true`, skips it. Bare content Text, other elements and nested rows are not walked. Rows' attributes, classes, `data-index`, listeners, buttons, inputs and every other component (including `InputBox`) are untouched.
- **Lines:** each eligible Text is evaluated on its own (adjacent Texts are never joined) and split into logical lines on CRLF, CR or LF. Delimiters, whitespace and UTF-16 units are preserved exactly; no trimming, normalization, substring or fuzzy match, language prefilter or case folding. Empty and whitespace-only lines are kept without lookup. A line matches only an **own data property** of the dictionary (inherited names such as `toString` or `constructor`, and accessors, never match; an own JSON `__proto__` key does). Exact mixed English/CJK keys match. Each miss, unsupported line or malformed mapping keeps that exact line while sibling lines translate.
- **Unsupported (kept):** a source or target containing `^RRGGBB` (six ASCII hex digits, any case), `<` or `>`, a numbered `{N}` placeholder, U+FFFD or a lone surrogate; a target that is not a string, is empty or whitespace-only, or contains CR/LF. Non-BMP characters, Chinese punctuation, quotes, `&` and `:` are ordinary text; a translated colon in a menu row is just text and never reparses options. HTML-like targets are unsupported, and nothing is ever parsed as markup: writes are only `Text.data`.

## Limits

| Bound | Value | Policy |
| --- | --- | --- |
| Active roots | 8 | Ninth untouched until a later eligible append after capacity frees |
| Direct `content.childNodes` per scan (all node types) | 256 | More: no new writes in that scan (earlier translations stay) |
| `childNodes` per row | 32 | More: whole row skipped |
| UTF-16 units per input Text | 8192 | More: whole Text skipped before line parsing |
| Logical lines per Text | 256 | 1 + delimiter count, CRLF once, trailing empty line counts; more: whole Text skipped |
| UTF-16 units per target | 8192 | Checked before any regex; more: that line kept, siblings continue |
| UTF-16 units per assembled output Text | 8192 | Checked before each concatenation; more: whole original Text kept |

Overflow never truncates, undoes earlier translations or retries endlessly (a skipped Text is re-evaluated only on a later scan trigger). These are logical bounds, not measured latency or memory guarantees.

## Diagnostics

`diagnostics()` returns a new frozen object of primitives only: `state` (`loading` | `ready` | `failed` | `disposed`), `activeRoots`, and saturating non-negative counters `hits`, `misses`, `unsupported`, `overflow`, `errors`, `stale`, `ignored`. No text, dictionary, DOM references, ids or arrays. Exact counter increments are not an acceptance criterion (re-scans recount misses); state, released roots and visible outcomes are.

## Historical raw worker checks

```sh
node --test tools/renewal/test_npc_plaintext_adapter.mjs
```

Historical result on the unchanged raw candidate: **34 tests, 34 pass, 0 fail, 0 skipped** (about 1.9 s). Root later reproduced two core and two reporter defects despite those passes. Coverage maps to the brief's groups: API gate and missing `MutationObserver` before subscribing; synchronous handle, idempotent dispose, frozen diagnostics; preexisting text plus rows added after append, duplicate append/replay with stable node identity; per-line hits/misses with CRLF/CR/LF, trailing empty and whitespace lines; adjacent Texts and own-key negatives (inherited, accessor, null-prototype, own `__proto__`); native-shape menu with omitted empty options, indexes, mousedown/OK/double-click and cancel 255; Next/Close and unrelated controls; excluded InputBox with `parseInt(value, 10) | 0` and unchanged `input.value`; whole-row skips; unsafe, nonstring and oversized mappings; pending/late/rejected/malformed dictionaries with an `unhandledRejection` probe; queued current-registry replay, immediate append, removal before replay, scope cleanup before loader adoption, removal while connected, reappend, name/host mismatch; observer data changes, row replacement, foreign elements, output-as-key, queued callbacks after remove/dispose and stale content; every numeric bound at limit and limit + 1; diagnostics content; dictionary reads and non-mutation; a lookup-time interference probe for the per-write recheck; a source scan for forbidden globals/DOM replacement; the weak memo in an `--expose-gc` child; and builder output, refusals and bounded reads.

The root correction adds targeted regressions for immediate cleanup followed by late dictionary rejection/resolve, component Element-root editable attribute presence (including `false`), and loading-content replacement requiring a fresh append. It adds a literal independent 13-group manifest and reporter tests for omitted G13, baseline success, suppressed/observed faults, and actual authored API listener/replay/synchronous and asynchronous cleanup errors. Private supplementary results remain separate from the root verification recorded in the linked review. Native fixture variants remain within the same 13 frozen groups.

A mutation sweep (scratch copies only) removed individual guards — memo, editable check, `data-index`, readiness-after-dispose, root limit, own-key lookup, host checks on append and remove, assembled-output limit, target CR/LF check, content-identity checks and the per-write recheck — and each mutation failed at least one test. **The doubles do not establish browser behaviour.** The Node MutationObserver double delivers in microtasks and drops its queue on `disconnect`, like the specification, but it is authored code.

## Detached browser fixture

```sh
python3 -I tools/renewal/npc_plaintext_fixture.py \
  tools/renewal/npc_plaintext_adapter.mjs .tools/renewal/T05.004/fixture
```

The builder takes the adapter path and a new output path. It refuses an `OUTPUT` that already exists (a dangling link included), any linked or missing component of either path (supply system aliases such as macOS `/var` by their physical `/private/var` spelling), a non-regular or non-UTF-8 source, and a source over 1 MiB: size is checked from the open descriptor before reading, and the chunked read stops after at most 1 MiB + 1 bytes even if the file grows. These checks do not close concurrent same-user path-replacement races. It writes a fresh `0700` directory of `0600` files (removed again on failure) and prints a summary with hashes and the output basename only.

| Generated file | Content |
| --- | --- |
| `npc_plaintext_adapter.js` | Byte copy of the adapter (`.js` for a JavaScript MIME type) |
| `boot.js` | Classic script loaded first: load errors, uncaught errors, unhandled rejections and **every** CSP violation (no favicon exemption) fail the page permanently; 30 s watchdog |
| `reporter.js` | Independent literal 13-group manifest; aggregate rules and explicit observed/not-observed fault-sink evidence; failures are sticky |
| `api-double.js` | Authored API 1 double: fresh frozen descriptors, microtask replay from the current registry, removal emitted before the caller detaches, scoped idempotent cleanup; listener, replay and cleanup errors go to a visible sink |
| `components.js` | Authored native-shape NpcBox/NpcMenu/InputBox stand-ins in shadow roots (written from the reviewed shapes, not copied) |
| `dictionary.js` | 41 authored entries parsed from JSON per call (no real dictionary content; long targets built with `repeat`) |
| `harness.js` | 13 baseline groups plus the six fault modes |
| `demo.js` | Interactive local demo |
| `index.html`, `style.css`, `shadow.css` | Page and styles; CSP `default-src 'none'; script-src 'self'; style-src 'self'` with img, font, connect, media, object, frame, child, worker and manifest `'none'`, `base-uri`/`form-action` `'none'`; no inline script, style or handler |
| `provenance.json` | Adapter and generator SHA-256, every generated file's size and SHA-256, CSP, group count, fault modes. No absolute paths |

The tests build a fresh fixture into a temporary directory and read it: modes, every provenance hash, adapter byte identity, CSP directives, no inline script/style/handlers, `NOT RUN` start with 13 expected groups, every import a sibling `./*.js` file, no fetch/XHR/WebSocket/storage/dynamic import/external URL/`innerHTML`, no CSS `url()`/`@import`, a small dictionary module, all six modes and 13 `group(` registrations. They import only the generated authored `reporter.js` and `api-double.js` to check aggregate rules and error sinks. `harness.js`, `components.js` and `demo.js` were only parse-checked (`node --check`), never executed.

**Page behaviour.** It starts `NOT RUN — 13 groups expected`, then runs the groups automatically and shows per-group PASS/FAIL with assertion counts, executed/passed/failed/assertion totals and a final status. The expected baseline names are a fixed literal manifest independent of `group(...)` registrations, so omission of G13 still leaves a missing expected group and fails. Baseline groups:

1. Preexisting dialogue, rows added after append, duplicate append/replay, node identity, one write per row (second native observer counts writes).
2. Multiline hit/miss/hit, mixed-CJK hits and misses, CRLF/CR/LF/trailing empty/whitespace, code-point check.
3. Adjacent Texts never joined; inherited-key negatives; own `__proto__`; null-prototype accepted; inheriting container fails.
4. Native-shape menu: omitted empty options, zero-based indexes, real `MouseEvent` mousedown selection, OK → owner/index+1, double-click, cancel 255, translated colons.
5. Next/Close and unrelated buttons/inputs: identity, values, one listener action.
6. Excluded InputBox: text submits the exact string, number submits `parseInt(value, 10) | 0` (`"0007"` → `7`) with `input.value` unchanged; Chinese/non-BMP code points. **Not an IME test.**
7. Whole-row skips for colour/ITEM/NAVI spans with metadata and working link listeners, comments, controls, `contenteditable` row and ancestor (native `isContentEditable`).
8. Unsafe/nonstring/empty/CR/LF/colour/angle/placeholder/U+FFFD/lone-surrogate mappings, oversized target, 8192 target, punctuation/non-BMP/quotes/ampersands, no elements created.
9. Pending → ready with foreign text at readiness; rejected, malformed and thenable dictionaries; removed before readiness while owned and connected; disposed before late resolve/reject; no unhandled rejection.
10. Queued current-registry replay, immediate append, removal before replay, scope cleanup before loader adoption, double dispose, name/host mismatches, removal while connected, reappend, detach/reappend.
11. Native MutationObserver: later data change, foreign Chinese kept, output-as-key, partial multiline edit, row replacement, foreign element insertion, removal, own-write settling, queued callbacks after remove/dispose, stale content replacement and mismatched adoption.
12. Component-name and row-shape negatives, malformed descriptors, all numeric bounds at limit and overflow, diagnostics shape.
13. Reporter rules (zero assertions, omitted, unexpected, duplicate, sticky failure), 13 groups, six modes, exact CSP meta, native `MutationObserver`.

**Fault modes.** Each `?mode=` adds exactly one authored local fault after the baseline groups and must remain FAIL; baseline must PASS: `api-append-error` (listener throws on a live append after the core's normal callback), `api-replay-error` (listener throws during queued replay), `api-cleanup-error` (cleanup throws on scope disposal), `zero-assertions` (an expected group records zero assertions), `unhandled-rejection`, `csp-inline` (inline script insertion blocked by CSP). An unknown mode also fails. No mode contacts any external resource. Errors after PASS (for example from the demo) turn the page FAIL.

The mode string no longer vetoes aggregate PASS by itself. Finalization records `status.dataset.fault` and a visible `fault observation` note: `observed`, `not-observed` or baseline `not-applicable`. Observed means the intended exact authored API/rejection sink error, native inline-script CSP violation, or actual zero-assertion group is present. Suppressed injection fails with the explicit `fault injection NOT OBSERVED` diagnostic and `not-observed`; that failure must never be credited as a working fault sink. Root must check both the failure and actual sink evidence in all six unmodified generated modes, then suppress an owned injection to verify this distinction. Node tests of authored error strings do not establish native CSP/unhandled-rejection delivery.

**Interactive demo.** After the run, buttons drive a demo NpcBox/NpcMenu/InputBox under the core: say lines (plain, CRLF hit/miss, coloured, ITEM, non-BMP, output-as-key), Show Next/Close, open the menu (`Yes::Buy:Unknown:Sell:`), number (`0007`) and text (`你好𠀋`) input. Click rows, OK, double-click, Cancel, Next/Close and the input OK; the log shows local callback values (owner, index, 255, submitted type and code points, `input.value`) and live diagnostics. These are local callbacks, **not packets or IME**.

## Root browser checks still pending

Not performed by this worker (no browser, listener or server was opened): serving the generated directory from a local static server, observing baseline PASS with 13/13 groups and nonzero assertions in a real browser, each of the six modes visibly FAIL, removing an owned module to see load failure, clicking every demo control and checking numeric/text/local counters and Chinese code points, and comparing against the other candidate. Root alone performs these.

## Not covered (required later work)

Coloured, link (NAVI/ITEM), template/placeholder and name text; menu rows with formatting; other UI surfaces; dictionary loading/transfer/parse cost of the 19.7 MB source; the JS wrapper that supplies `dictionaryReady`; packaging/installation as a mod; live NPC behaviour in the game; translation quality; full UI/story/content/episode coverage. None of this is reduced by this task.

## Rollback

Source rollback: `git revert` the integration/selection commit (and any later correction first, in reverse dependency order). Deleting generated fixtures under `.tools/renewal/T05.004/`, any root-started listener or browser tab is separate and manual. No installed, app, save, settings or browser state is changed by this task.
