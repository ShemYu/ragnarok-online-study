# ui-text msgid compatibility adapter (T05.003)

Root-corrected 1.0.1 from selected raw Claude `b724e385` (unchanged integration `c4931e6`). Root verification is recorded in the [task review](../../docs/project/reviews/2026-10-18-T05.003.md); this remains a detached source/fixture tool, with no installed mod.

The packaged `ui-text` element (`UI/Elements/UIText.js`, and the identical
class in the packaged `Online.js`) looks up and observes only `msg`. Two
packaged templates write their title id as `msgid` instead, so the title never
reaches `DB.getMessage`:

| Component | Slot | Notes |
| --- | --- | --- |
| `SkillListV2` | `<ui-text class="text" msgid="283">` with English fallback text | Selected from packet version 20090601; relevant under the recorded 20221005 profile |
| `QuestV1` | `<ui-text class="title" msgid="1317">`, empty | Version-family fixture only: from 20180307 the controller selects `Quest`, not `QuestV1` |

`ui_msgid_adapter.mjs` is a client API 1 plugin that sets `msg` from the
allowlisted `msgid` on those two slots and nothing else. This is a source and
fixture qualification. Nothing is installed; the game, app, browser, saves,
settings and network are untouched.

## Files

| File | Role |
| --- | --- |
| `ui_msgid_adapter.mjs` | The adapter: default `initialize(parameters, api)`, plus `createMsgidAdapter(api)` for tests |
| `test_ui_msgid_adapter.mjs` | Node built-in tests on authored DOM, element and API 1 doubles; builder negatives |
| `ui_msgid_fixture.py` | Builds the detached browser fixture from the exact pinned `UIText.js` |
| `UI_MSGID_ADAPTER.md` | This runbook |

Node24 and Python3.9 standard library only; no packages or network. Correction regressions run authored API/boot code under Node event/element doubles, plus authored builder fault probes; the stock UIText and complete generated harness are never executed by those tests. Temporary test files stay beside the test module and are removed.

## Adapter contract

- **API gate.** `api.version === 1` is required before anything is touched;
  otherwise the initializer throws and the loader reports a failed plugin.
- **Subscriptions.** `api.on('ui:append', …, { replay: true })` and
  `api.on('ui:remove', …, { replay: false })`, plus one `api.cleanup(dispose)`.
  The initializer returns nothing, so the loader does not register a second
  cleanup.
- **Eligibility.** The descriptor's `name` must be exactly `SkillListV2` or
  `QuestV1`. Within `descriptor.root`, a `ui-text` element is eligible only if
  its `msgid` is exactly `283` or `1317` respectively, it has **no** `msg`
  attribute (an existing `msg`, even empty, wins) and all its children are text
  nodes. Empty, padded, zero-prefixed, full-width or other ids, other
  components and slots holding elements are left unchanged.
- **Action.** `element.setAttribute('msg', id)`. The registered element's own
  `attributeChangedCallback` performs the lookup and, if the message is
  non-empty, replaces its text. A missing or empty message leaves the fallback.
  The adapter imports nothing: no DB or game module, no storage, no
  preferences, no observers, timers, globals or prototype changes, and no
  callback patching after registration. Ids, other attributes, other nodes
  and controls are not touched.
- **Idempotence.** State is keyed by the component's stable `root` (the
  shadow root; every append hands over a freshly allocated descriptor) and by
  component name, then by element. A repeated append or the queued replay
  skips an element it already handled for that mount, even if foreign code
  later removed its `msg`.
- **Removal.** `ui:remove` (emitted by the client before the host is
  detached) restores and releases that component's slots for that root only.
  Two descriptors sharing a root are released separately. A later append
  applies again.
- **Disposal.** Unsubscribes, restores and releases every slot, and ignores
  any later event or queued replay. Calling it twice, or through both the
  scope and the returned handle, has no further effect.

### Conservative restoration

Removing `msg` does not restore text in this class (`attributeChangedCallback`
ignores a null value), so restoration is explicit and guarded:

1. `msg` is removed only if it still equals the value the adapter wrote.
2. Text is restored only if the lookup actually changed it, the `msgid` is
   still the source id, and the children are the very nodes, with the very
   text, the lookup left. The original fallback text node is put back when it
   is still detached and unmodified; otherwise equal text is written.
3. Any later foreign `msg`, text, child or `msgid` change is preserved.

**Ownership limits.** Without an observer the adapter sees only end states. A
foreign write that removes `msg` and sets it back to the same id, or that
replaces nothing observable, is indistinguishable from the adapter's own
state and is treated as its own. Restoration is per element, not an atomic
document rollback.

## Checks

```sh
node --test tools/renewal/test_ui_msgid_adapter.mjs
T05_UITEXT_SOURCE=/path/to/client-source/src/UI/Elements/UIText.js \
  node --test tools/renewal/test_ui_msgid_adapter.mjs
```

Without `T05_UITEXT_SOURCE` one test (fresh fixture from the pinned class) is
reported as skipped. With it, the test builds a fixture into a temporary
directory and **reads** it: modes, every provenance hash, that the class
differs from the source only by the import line (CRLF kept), that the adapter
copy is byte-identical, the page CSP and `NOT RUN` start, and that every
generated import is a sibling `./*.js` file with no URL, storage or `Online.js`
reference. It never imports the generated code.

Coverage: both sites; existing ordinary and empty `msg`; empty, malformed and
unlisted ids; non-allowlisted and malformed descriptors; missing and empty
messages; element-child slots; immediate append plus queued replay; replay
only; removal and disposal before the queued replay; detach and re-append
with fresh descriptors; two descriptors on one root; foreign `msg`, text,
child, `msgid` and same-text updates; unrelated control identity; a throwing
reaction; the API gate; double disposal; and a source scan for forbidden
globals. **These are doubles.** They mirror the reviewed class and API 1
lifecycle; they do not establish real browser custom-element reactions.

## Detached browser fixture

```sh
python3 -I tools/renewal/ui_msgid_fixture.py \
  /path/to/client-source/src/UI/Elements/UIText.js .tools/renewal/T05.003/fixture
```

The builder refuses a source that is not a regular, non-link file of exactly
796 bytes with SHA-256
`8b93dde4d26829fbe5dc9ce18170dbdd7c6f236bd165ec6695556f4564531d8f`, an
`OUTPUT` that already exists (a dangling link included), or a link or missing
parent, including linked ancestor components. System aliases such as `/var` must be supplied by their physical non-link spelling. Descriptor size is checked before reading; UIText reads stop after at most797bytes, and authored adapter/generator reads are capped at1MiB. These checks do not close concurrent same-user path-replacement races. It writes a fresh `0700` directory of `0600` files, removing it again
if writing fails, and prints a summary with hashes and the output's basename
only.

| Generated file | Content |
| --- | --- |
| `UIText.js` | The pinned class; only `import DB from 'DB/DBManager.js';` (offset 173) becomes `import DB from './db-stub.js';`. 793 bytes, SHA-256 `19b6b4ae4dd247b652be04c459e56e093be065edb5fc3e7de0ba72d6e3d65997` |
| `ui_msgid_adapter.js` | Byte copy of `ui_msgid_adapter.mjs` (`.js` so any static server sends a JavaScript type) |
| `db-stub.js` | Authored `getMessage(id, default)` over an in-memory map, same missing-id semantics; records calls |
| `api-double.js` | Authored API 1 double: fresh descriptors, microtask replay from the current registry, removal before detach, scoped cleanup |
| `boot.js` | Classic script loaded first: records load errors, CSP violations, uncaught errors and unhandled rejections; fails the page after 20 s without completion |
| `harness.js` | 25 authored cases in readable DOM |
| `index.html`, `style.css` | Page; CSP `default-src 'none'; script-src 'self'; style-src 'self'` with img, font, connect, media, object, frame, child, worker and manifest all `'none'`, `base-uri`/`form-action` `'none'` |
| `provenance.json` | Source, transformed class, adapter, generator and every file's size and SHA-256; substitution offset; CSP; expected case count. No absolute paths |

No `Online.js`, client initialization, real tables, storage, WebSocket, fetch
or external resource is involved. The markup is tiny and authored in the two
template shapes, not copied.

**Page behaviour.** It starts as `NOT RUN — 25 cases expected`, runs each case
with a 3 s bound and lists `PASS`/`FAIL` per case with its assertion count,
then the totals. Every authored API-double listener/replay/cleanup exception reaches the boot failure sink and therefore per-case and aggregate failure. It shows `PASS` only if all 25 defined cases ran and passed,
each made at least one assertion, and no load, CSP or runtime error or
unhandled rejection was recorded. Anything else stays visibly `FAIL`. No CSP violation is exempt, including a favicon-shaped image request. The frozen `img-src 'none'` policy is preserved and no favicon resource is added. Root observed no favicon notes/errors in the target raw fixture; a future surface-specific favicon violation must visibly fail pending diagnosis.

Cases: real registration and upgrade; real `connectedCallback` for an existing
`msg`; both sites through the real `attributeChangedCallback`; UTF-8 Chinese
text and punctuation compared with escape-built strings plus a non-BMP
sentinel (U+2000B); missing and empty messages; existing and empty `msg`;
invalid ids; unlisted components; element-child slot; immediate plus queued
replay; replay only; removal and disposal before replay; detach and
re-append; shared root; foreign `msg`/text/child/`msgid`; an unrelated button,
checkbox and text input keeping identity, value and exactly one local listener
each; double cleanup; API gate.

### Root-owned browser step (not performed by the worker)

Module scripts need HTTP, so the root serves the private directory on
loopback, with a port and process it owns, and opens it in a separate tab:

```sh
python3 -I -m http.server --bind 127.0.0.1 --directory .tools/renewal/T05.003/fixture 8793
# open http://127.0.0.1:8793/index.html, read #status, #totals, each case, #errors and #notes
```

Stop that process afterwards. The worker opened no browser and no listener,
and did not run the generated stock class.

## Limits

- Doubles and the fixture establish binding and lifecycle only. Real table
  entries 283/1317, Chinese glyph/layout quality, the active window, packet
  version selection on the running page, installation and complete game UI
  are separate gates. `SkillListV2`'s hardcoded labels are separate slots.
- `QuestV1` is exercised as a template shape, not as the active quest window.
- Hot unload is not promised: disposal restores what it still owns, but the
  client loads plugins once per page.

## Future packaging and rollback

A supported mod would be a folder with `mod.json` and `client/index.js`
copied from `ui_msgid_adapter.mjs`; the app stages it to `plugins/<name>/`
and lists it in the generated config. That is not staged or installed here.

Source rollback is a revert of the task commit. Deleting a verified fixture
output (`.tools/renewal/T05.003/fixture`) is a separate step. No installed
state changed, so no save or settings restore is needed.

## Root corrections and verification boundary

- The existing-msg case verifies an initialized real element, nonempty lookup activity and only the correct283 ID, without assuming one initial call. Root raw browser observation was2 calls, from upgrade and connection.
- The authored API double requires an error sink; both harness runtime constructors pass the visible boot failure sink. Listener, replay and cleanup sentinel errors have authored Node regressions.
- Every CSP event is fatal, including same-origin/external favicon-shaped URLs. The frozen img-src 'none' policy is unchanged and no favicon resource/data allowance is added. Root browser negatives are recorded separately in the task review.
- Source and output path components reject links before creation; exact796-byte source size is checked on the descriptor before reading, with at most797bytes read to detect growth. A source that grows is refused.
- The adapter is byte-identical to the raw submission. The original UIText CRLF bytes still change only at the DB import. No install, real table, active-window, game or language acceptance follows.

Root verification must include the full authored Node suite, fresh builder and all25 browser cases. In isolated negative copies, inject an append listener, replay listener or cleanup exception and require visible per-case/aggregate FAIL; check favicon-shaped CSP event reporting under authored doubles and actual module/CSP failure handling in the detached browser; confirm the target surface remains free of unexpected baseline CSP errors. A future favicon issue is a visible failure pending diagnosis. The task review records actual root results; generator output alone claims no browser success.


Root integrated verification:24 authored Node tests pass with0 skipped/failed; a freshly generated fixture passes all25 real-browser cases/120 assertions. Separate append/replay/cleanup error, zero-assertion and missing-module modes remain visibly FAIL. An actual blocked inline-script control changes prior PASS to FAIL and never runs its sentinel. Common adapter checks pass20 groups plus2 additional shared-root/text-only boundaries. This qualifies the detached source/fixture tool only. Real message selection, supported installed packaging, active-window layout/remaining UI and full Traditional Chinese acceptance remain separate. See the task review for exact hashes, raw-provider comparison, timings and resource cleanup.
