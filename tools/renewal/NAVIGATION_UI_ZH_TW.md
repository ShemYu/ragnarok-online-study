# Navigation Traditional Chinese source transform (T05.009)

Pure, fixed-input byte transform and exact inverse for the expanded
Navigation UI in one qualified repaired Ragnarok Offline 1.6.3 `Online.js`.
It turns 66 English literal sites and the two bitmap Share/Find captions into
the frozen Traditional Chinese wording. **Source qualification is not
installation, rendering, executing-page integrity or user acceptance.** Root
owns those later gates; see [Limits](#limits).

Frozen specification: [T05.009](../../docs/project/tasks/T05.009.md) and its
[profile](../../docs/project/fixtures/T05.009-profile.json) (95517 bytes,
SHA-256 `df4ba7ab…7cc7fb9`). The wording is coordinator-authored, not asserted
official glossary text.

## API

```python
import navigation_ui_zh_tw as nav

localized = nav.transform_bundle(original)  # bytes -> bytes
original = nav.restore_bundle(localized)    # bytes -> bytes
```

| | Bytes | SHA-256 |
| --- | ---: | --- |
| Accepted original input | 13172839 | `6ba854cb67b1306cadb905b1b89a7a1eac98cd7e5c912196e6f87df41a5c4c2f` |
| Returned / accepted localized | 13173065 | `67525a4ec4b834ec02c5ff33b4ca55c119f1380fa131ea329aab880359144478` |

Each function accepts exactly one `bytes` object (not `str`, `bytearray`,
`memoryview` or a `bytes` subclass) and either returns the other pinned bundle
or raises `ValueError` with a short diagnosis naming the failed check or site
id. Error wording is not a contract.

Python 3.9 standard library only; the module imports `hashlib` and nothing
else. It reads no file, environment, network or profile, starts no process,
evaluates no JavaScript, imports nothing from the T05.007 repair helper and
registers nothing. Import only builds and arithmetically checks the fixed
constants (unique ids; fragment length equals span length; nonoverlapping
ordered spans; equal complement gaps on both sides; equal tail). It embeds no
bundle: the module is about 12.6 KB.

## What each call checks

`transform_bundle(source)`, before building:

1. exact `bytes` type, 13172839 bytes, the input SHA-256;
2. each of the 75 fixed original fragments at its fixed original span, the
   spans in fixed nonoverlapping source order and in bounds (the two empty
   child-insertion fragments included).

It then copies every byte between the spans and puts each localized fragment
in place, and checks the whole result is 13173065 bytes with the localized
SHA-256 before returning it.

`restore_bundle(localized)` mirrors this: exact localized size/SHA-256, each
of the 75 localized fragments at its fixed localized span (the six empty
fragments of removed attributes included) in stable listed order, then the
whole result must equal the original size/SHA-256.

The six removed attributes become two groups of three zero-length points in
the localized bundle: Share at 7025090 and Find at 7025205. Sites are spliced
strictly in listed order, so each group is restored **bg → hover → down**.
Sorting equal points would change bytes; the result pin then refuses.

Production does not embed or recompute the 39 contexts, 72 complement pieces,
7 windows, 5 guard-only sites, 2 literal tokens, per-fragment hashes or the
profile. Those remain external acceptance, checked by the tests and root.

## The 75 edits

All offsets are zero-based half-open UTF-8 byte offsets in compiled source.
HTML and CSS sit inside JSON-escaped string tokens, so their fragments hold
literal `\"` and `\n` escapes; no raw newline is inserted.

| Kind | Count | Where |
| --- | ---: | --- |
| Text | 66 | A01–A11 initial HTML, B01–B07/B12–B14 Navigation.js, B15 `/navi` help, B07–B11 `searchNavigation` arrays/fallbacks |
| Bitmap attribute removal | 6 | ` bg`/` hover`/` down` (with their leading space) on the Share and Find `ui-button` |
| Text child insertion | 2 | `分享` at 7025280, `尋路` at 7025500, between `>` and `</ui-button>` |
| Scoped CSS rule | 1 | 67-byte `.Navigation .search-actions ui-button { width:120px; height:20px; }` at `[7033941, 7034008)` becomes the four frozen rules (base, `:not([disabled]):hover`, `:not([disabled]):active`, `[disabled]`) |

Unchanged on purpose: filter values `ALL`/`NPC`/`MOB`, the count node and
`]`, the `?` level placeholder, all classes, `disabled` attributes, handlers,
the `ui-button` custom elements (no native button, role, tabindex or key
handling), the MOVE button's `disabled`, the `.Navigation .disabled` and
action-container CSS rules, numeric thresholds and array index order, every
`addStat` `: ` join and the `navigation-english-tables` identifier elsewhere.
The 9700-byte repaired loader `[10727952, 10737652)` moves to
`[10728206, 10737906)` byte for byte. Rows are listed in `_EDITS` in the
module; ids match the profile.

## Tests

```sh
T05_009_BUNDLE=<frozen repaired Online.js> \
    python3 -I -B tools/renewal/test_navigation_ui_zh_tw.py -v
```

Without `T05_009_BUNDLE`, or if it does not exist, the actual-input class is
skipped as `missing-input`, never passed; a bundle that exists but has the
wrong pin fails. The tests read the checked-in profile (pin-checked) as
external data; the term table, arrays, help text, CSS rules and action tags
are authored from the task text, so constants are not only compared to
themselves.

| Group | Needs bundle | Checks |
| --- | --- | --- |
| `ModuleContractTests` (S01) | no | exactly two typed public functions; only `hashlib` imported; no I/O/env/process/dynamic-code names; top level only defines and checks constants; module under 32 KB; pins equal the task |
| `ProfileAgreementTests` (S02) | no | profile counts 66/6/2/1, 39/72/7/5/2; all 75 rows equal profile ids/spans/fragments/hashes in order; all 66 text sites equal the authored terms (6 `未知`, 3 `請選擇結果`); bitmap/child/CSS rows; constant check rejects bad tables |
| `AuthoredSpliceTests` | no | tiny authored splice with co-located deletions, insertion and replacement; exact inverse; reordered co-located inverse refused; fragment/overlap/order/bounds/length/type/pin refusals |
| `ActualInputTests` (S02–S05) | yes | output pin; determinism; exact inverse; all 75 edits at both spans; 72 complement pieces and full tiling of both bundles (1034 old / 1260 new edit bytes); loader; 39 contexts with window match counts; 7 windows' guards in both bundles; 5 guard sites; both tokens decode as JSON; HTML start-tag sequence identical, only Share/Find/marker attributes differ as expected; exact action tags; CSS differs only by the rule; finite arrays and dynamic lines; forward and inverse refusals; fragment and result layers refuse independently; optional `node --check` of both bundles |

The node check writes each bundle once as a 0600 file in a 0700 temporary
directory under `T05_009_WORK` (default `.tools/renewal/T05.009/test-work`),
parses it without executing, and removes it. Without `node` it is skipped.

## Limits

- Source bytes only. Nothing here renders the panel, runs the client or
  proves text fit, contrast, Find enable/reset, hover/active/disabled states
  or the `/navi` help in the game.
- Fixed input only: any other `Online.js`, including other repaired builds,
  is refused, not adapted.
- No CLI, writer, publisher, installer, cache/settings/save action. Root
  later writes and delivers the bytes through separately verified mechanisms;
  T05.008 pins do not qualify the localized bundle.
- Arbitrary loaded names, story, markers and other UI stay untranslated; this
  is not full Navigation or game localization.

## Root detached-fixture plan (pending, not run)

Plan only, after root source qualification. Root reviews a detached fixture
with the exact localized HTML/CSS and the actual pinned UIButton plus minimal
DB/Client/Targa stand-ins:

- **N01** fresh panel text, captions, tooltips and the two children; control
  identities kept; Share and MOVE disabled; none of the six bitmap requests.
- **N02** short query, empty/nonempty results, missing fields, map-wide and
  numeric coordinates, reset/hide/show paths.
- **N03** authored MOB rows covering 10 elements, 12 races, 3 sizes, 5
  abundance thresholds, unknown fallbacks and one NPC.
- **N04** 120×20 text fit; base/hover/active only when enabled; `[disabled]`
  opacity .5 and default cursor; Share inert; Find enables, clicks once,
  resets and survives hide/show.
- **N05** help text; Map Click and no-path if faithfully isolatable;
  Mouse/Target footer stays CSS-hidden.

Paths that cannot be isolated faithfully stay pending. Installed rendering,
save preservation, fresh launch, rollback, IME/story/full UI and user
evaluation remain separate root-owned gates.
