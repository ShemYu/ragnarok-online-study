# Modern Quest Traditional Chinese chrome transform (T05.011)

Pure, fixed-input byte transform and exact inverse for the modern Quest
list/helper chrome in one Chinese-navigation Ragnarok Offline 1.6.3
`Online.js`. **Source qualification is not installation, rendering, native
fit, IME, game behavior or user acceptance.** Root owns those later gates; see
[Limits](#limits).

Frozen specification: [T05.011](../../docs/project/tasks/T05.011.md) and its
[profile](../../docs/project/fixtures/T05.011-profile.json) (33878 bytes,
SHA-256 `e4ceded1…e3a73b5b71`). The wording is coordinator-authored, not
asserted official glossary text.

## API

```python
import quest_ui_zh_tw as quest

localized = quest.transform_bundle(original)  # bytes -> bytes
original = quest.restore_bundle(localized)    # bytes -> bytes
```

| | Bytes | SHA-256 |
| --- | ---: | --- |
| Accepted original input | 13173065 | `67525a4ec4b834ec02c5ff33b4ca55c119f1380fa131ea329aab880359144478` |
| Returned / accepted localized | 13174160 | `9c148d9e43384a2498f9074efd1603b4eda1ff36dac53998985cfdf5eaf6fadf` |

Each function accepts exactly one `bytes` object (not `str`, `bytearray`,
`memoryview` or a `bytes` subclass) and either returns the other pinned bundle
or raises `ValueError` with a short diagnosis naming the failed check or site
id. Diagnostics omit caller-controlled type names so they remain bounded.
Error wording is not a contract. There is no best-effort output.

Python 3.9 standard library only; the module imports `hashlib` and nothing
else. It reads no file, environment, network or profile, starts no process,
evaluates no JavaScript and imports nothing from the Navigation transform
(used as a pattern reference only). Import only builds and arithmetically
checks the fixed constants (23 unique ids; fragment length equals span
length; ordered nonoverlapping spans; equal complement gaps on both sides;
equal tail). It embeds no bundle.

## What each call checks

`transform_bundle(source)`, before building:

1. exact `bytes` type, 13173065 bytes, the input SHA-256;
2. each of the 23 fixed original fragments at its fixed original span, in
   fixed nonoverlapping source order and in bounds (the five zero-length
   insertion points included).

It then copies every byte between the spans, puts each localized fragment in
place and checks the whole result is 13174160 bytes with the localized
SHA-256 before returning it.

`restore_bundle(localized)` mirrors this: exact localized size/SHA-256, each
of the 23 localized fragments at its fixed localized span, then the whole
result must equal the original size/SHA-256. The four tab captions and the CSS
append invert to deletions, so every original byte, including JSON-string
escaping, returns.

## The 23 edits

Fragments are compiled bundle source text: HTML and CSS sit inside
JSON-escaped string tokens (`\"`, `\r\n` are literal escape bytes; raw TAB
bytes stay as they are).

| Group | Sites | Change |
| --- | --- | --- |
| Shared hunt templates (QuestCommon; also reach QuestV1) | T01, T02 | `Mission [..], you killed [..]. (..)` → `任務 [..]：已擊倒 [..]。(..)`; `[Completed]` → `[已完成]` |
| Modern helper template | T03 | `Deadline [..]` → `截止時間 [..]` |
| Hidden row fallbacks, 3 modern branches | R-cooldown/active/inactive × icon/toggle | `Quest` → `任務`, `Toggle` → `切換` (still hidden) |
| Helper HTML labels | H02, H04–H09 | 任務資訊, 任務說明, 目標魔物, 任務獎勵, 基本經驗值, 職業經驗值, 物品 |
| List HTML labels | H01, H03 | 任務資訊, 顯示任務 |
| Tab captions | I-active/feature/inactive/cooldown | one `span.quest-menu-caption` child in each empty `li`: 進行中/推薦/暫停中/冷卻中 |
| Caption CSS | C01 | frozen profile CSS appended at the end of the modern Quest.css token |

Every compiled interpolation is kept byte-for-byte and in order; the Mission
title stays `${DB.getQuestInfo(questID).Title}` (no `quest_info` local) and
the deadline keeps `${d.toLocaleString()}`. Not changed: both Close bitmap
buttons (the Taiwan installation's bitmaps already read 關閉), the four
`bg_quest1..4` state selections, tab ids/classes/order/handlers/list
destinations, dynamic quest/item/monster data, and every byte outside the 23
sites.

## Tests

```sh
T05_011_BUNDLE=<frozen Online.js> python3 -I -B tools/renewal/test_quest_ui_zh_tw.py -v
```

`T05_011_BUNDLE` is only read. Without it (or if the path is not a file) the
10 actual-input tests are reported as skipped (`missing-input`) and the runner
exits 2, never a full pass; this explicit status follows the paired Grok
candidate. Exit 0 means all tests passed with no skips; failures/errors exit 1.
An existing file that does not match the input pin fails. The 9 source-shape
tests always run, including a regression for long invalid type names.

Source-shape tests: pins/count, AST purity (only `hashlib`; no file, process,
eval or environment names), term table and tab captions authored from the task
text, interpolation conservation in the three templates, plan equality with
the frozen profile, wrong-type and wrong-size refusals in both directions, and
tiny test-authored splicer controls (replace/insert/delete, inverse,
fragment, order and result-pin refusals).

Actual-input tests: golden output pin; exact inverse; an independent splice
built only from profile data equals the output; all 24 unchanged pieces by
SHA-256 in both bundles; the 6 guard-only sites; template output and global
`${...}` sequence conservation; decoded HTML/CSS tokens (raw controls other
than TAB rejected before `json.loads(strict=False)`): the original tag
sequence plus exactly four caption spans, four `li` in original id/class order
with the four captions, both Close buttons once each, no remaining English
labels, CSS equal to original plus the frozen append; hidden row fallbacks in
place; refusals of truncated, grown, inside-site, unchanged-piece and
wrong-direction bytes; and per-site fragment refusals for the 18 nonempty
forward fragments and all 23 inverse fragments, with the whole pin re-aimed
at the mutated bytes. The five empty forward insertions are covered by exact
positive site/output checks; they supply no nonempty fragment to mutate.

## Limits

- Fixed to the one pinned input; any other bundle (including a future client
  or Navigation revision) is refused and needs a new root golden and task.
- No CLI, publisher, runtime adapter or installer. Root performs installation,
  detached/native appearance (four visible labels covering the English bitmap
  letters, readable selected state, unchanged click/drag/close, text fit),
  hunt/deadline data, IME and current-save checks.
- T01/T02 change the shared hunt notification, so QuestV1 text changes too;
  no claim that all legacy Quest text remains English or is localized.
- The `:has()` selected-caption styling and caption fit are unmeasured in the
  native client.
