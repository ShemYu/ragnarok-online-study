# Traditional Chinese Captain Carocc pilot (T05.001, 0.2.0 by T05.012)

`carocc_zh_pilot.py` builds the server-script mod **tw-carocc-pilot** from the
pinned rAthena `academy.txt` packaged with Ragnarok Offline v1.6.3. Captain
Carocc in Izlude then greets a new Novice in Traditional Chinese, and one
sentence of his active-7472 revisit is Chinese too. Python 3 standard library
only. Nothing is installed and no game state is touched.

```sh
umask 077
python3 -I tools/renewal/carocc_zh_pilot.py \
  /path/to/academy.txt .tools/renewal/<new-private-dir>/candidate
CAROCC_ACADEMY=/path/to/academy.txt \
  python3 -I -m unittest discover -s tools/renewal -p test_carocc_zh_pilot.py -v
```

Without `CAROCC_ACADEMY` the six real-input tests are reported as skipped;
the synthetic and publication tests still run. A skipped run is not a
production pass. No stock script is committed.

## Version 0.2.0 (T05.012)

0.1.0 had eight authored translations. In the real active-7472 Carocc revisit
(six pages, source lines 673–699) the plain `mes` body lines already render
Chinese through the existing client dictionary, but the line holding the Hun
navigation link stayed English: the plain-text adapter skips rows that contain
`<NAVI>` markup. 0.2.0 adds that one sentence, source line **693**, as a ninth
`mes` translation. The eight 0.1.0 entries, their order and bytes are
unchanged; so is every function of the generator. The other revisit lines are
not authored here and still depend on the existing dictionary.

The link markup `<NAVI>[Hun]<INFO>izlude,122,207</INFO></NAVI>` is copied byte
for byte inside the translated literal; only the prose around it changes. The
`viewpoint 1,122,207,…` on line 695, the five `next;`, the `close;`, the cutins
and the `[Carocc]`/`[Lumin]`/ellipsis lines of that branch are unchanged, and
it still writes no quest, EXP, item, zeny or warp. Hun himself (source
824–827, which completes 7472) is not part of the copied block.

With the pinned input, the default output is exactly:

| File | Bytes | SHA-256 |
| --- | --- | --- |
| `tw-carocc-pilot/npc/carocc_zh_pilot.txt` | 16,526 | `9eedc4c3…00973aa1` |
| `tw-carocc-pilot/mod.json` | 419 | `c9e9b733…6874488d` |
| `generation-manifest.json` | 3,326 | `071da5e3…bc79d4aa` |

## What it produces

```
candidate/
├── generation-manifest.json         input/block/output hashes, translations, limits
└── tw-carocc-pilot/
    ├── mod.json                     requires app >=1.6.3, era renewal
    └── npc/carocc_zh_pilot.txt      UTF-8: provenance, copied block, controller
```

The script holds three parts:

1. A provenance and licence comment: source file, SHA-256, copied lines,
   original authors and the GPL-3.0 notice (rAthena scripts).
2. Source lines **388–798**, the Izlude Captain Carocc `script` block, under
   the internal name `Captain Carocc#t05zh`. The displayed name, map,
   coordinates, direction, sprite and 5,5 trigger are unchanged. The block's
   own OnInit (quest marker) and OnTouch are copied byte for byte.
   The duplicate definitions on lines 800–803 (`izlude_a`..`izlude_d`) are not
   copied.
3. A hidden controller `T05CaroccZHInit` whose only OnInit effect is
   `disablenpc "Captain Carocc#iz";`. The stock academy is not edited or
   unloaded, and the other-map duplicates are left alone.

Exactly nine display literals are translated. Latin names Carocc and Izlude
stay, because their official Chinese forms are not established. The speaker tag
`[Carocc]` stays.

| Line | Kind | English | Traditional Chinese |
| --- | --- | --- | --- |
| 569 | mes | Hello? | 你好？ |
| 570 | mes | Is it your first time on Izlude? | 你是第一次來到 Izlude 嗎？ |
| 572 | select | Hello? | 你好？ |
| 572 | select | Let me get on the ship! | 讓我上船吧！ |
| 572 | select | I don't know what to do. | 我不知道該做什麼。 |
| 575 | mes | You look strong and able! | 你看起來既強壯又能幹！ |
| 576 | mes | I like able people like you! | 我就喜歡像你這樣能幹的人！ |
| 577 | mes | Always be healthy and strong as you are now. | 希望你永遠都像現在這樣健康又強壯。 |
| 693 | mes | My friend `<NAVI>[Hun]<INFO>izlude,122,207</INFO></NAVI>` will be around the academy entrance. | 我的朋友 `<NAVI>[Hun]<INFO>izlude,122,207</INFO></NAVI>` 就在學院入口附近。 |

## What it checks before writing

- Input is exactly 508,418 bytes with SHA-256 `b2ab5f7d…4f27fd`; the block's
  header, closing brace and SHA-256 (`f9d8d556…96e33`) match; the stock
  definition is unique; lines 800–803 are the expected duplicates; the clone and
  controller names do not occur in the input. Anything else is refused.
- Each English literal must occur exactly once, quoted, on its pinned line
  (missing or ambiguous anchors are refused), and `mes` anchors must be a lone
  `mes "...";` line.
- Translations are not escaped. A `"`, `\`, `^` colour code, control or line
  separator, and in `select` labels the `:` option separator, is refused, as is
  a label without Chinese characters.
- Masking the nine translations and the header name back must reproduce the
  complete 411-line source block **byte for byte** (tabs, LF endings, NAVI
  markup). Only the header and the seven translated lines (569, 570, 572,
  575–577, 693) may differ, and counts of `mes`, `select(`, `next;`,
  `close`, `case`, item/EXP/zeny/warp/quest/viewpoint/navigation/cutin tokens
  must match.
- The input file is only read. Its bytes are never recoded; only the copied
  ASCII block and the new UTF-8 literals reach the output.

## Publication, partial output and races

The output directory must not exist: a file, directory, empty directory or live
or dangling symlink is refused and left unchanged. Its parent must already
exist, be a real directory (not a symlink), be owned by you and not be group or
world writable; use an ignored path such as `.tools/renewal/T05.001/`.

Files are written to a `.staging-*` directory in that parent, then copied to
the destination, which `copytree` creates with an exclusive `mkdir`. Anything
that appears at the destination after the first check is refused, never
replaced or followed. Staging is removed on success and failure. If the copy
itself fails after the destination was created, an incomplete destination may
remain: inspect and remove it yourself before retrying. A process killed
mid-run can leave a `.staging-*` directory behind; remove it by hand. Files
inside the parent are not protected against another process running as you.
Only use output after exit 0 and after checking the manifest hashes.

## Installing and removing (root only)

Not done by this tool. The app's folder installer refuses an existing mod
with the same name. A same-name update uses supported **Remove → Add**:

1. Qualify the fresh generated output and independently preserve the old
   `tw-carocc-pilot` folder, including its script and `mod.json`. Normally
   logout/save, verify the newest earned state and a fresh full backup, then
   use General → Stop.
2. Settings → Mods → Installed: remove only `tw-carocc-pilot`. Removal moves
   its folder to Trash and forgets its choices; keep the independent old copy.
   Add the qualified output's inner folder named exactly `tw-carocc-pilot`.
   Headless Settings accepts its unquoted absolute host path in the browser
   file prompt. Choosing it installs and enables the mod.
3. Confirm the intended version and all four existing mods remain enabled.
   Use the qualified Apply & restart server → General Stop → General Start
   sequence, which rebuilds registration and relinks/stages assets. Verify the
   installed/generated script, container bind view, registration, readiness
   and actual six-page dialogue/link. Preserve the Quest/Navigation bundle,
   aliases, other overlays and newest earned progress throughout.
4. Verify normal save/re-entry, a cold start and bounded rollback/reapply.
   To roll only this change back, Remove/Add the preserved **0.1.0** folder
   and repeat the same checks; then reapply0.2.0. Disabling the whole pilot
   also removes its original eight translations, so it is not this rollback.

This procedure is still a delivery plan until root records actual completion.
Source conservation does not itself prove unchanged saved state or successful
loading. Do not restore an older save to undo a text-only update, edit stock
scripts, or copy files directly into the map container.

Source rollback is a revert of the T05.012 commit, which restores the 0.1.0
generator and tests; regenerating then gives the 0.1.0 output. Git does not
restore an installed mod, saves or the app database. Replacing an installed
0.1.0 pilot with 0.2.0 (or back) is a later root-only step that needs its own
tested external-state backup and save/re-entry checks.

## Limits

- Authored Chinese covers only the first-visit Novice opening, its menu, the
  Hello? reply and the one active-7472 NAVI sentence (line 693). All other
  literals are copied unchanged and rely on the existing client translation
  or fall back to English.
- Duplicates on `izlude_a`..`izlude_d` stay English and enabled.
- Not checked here: the map server loading the script, client rendering of the
  UTF-8 text, menu clipping, the quest marker of the clone, or dialogue flow.
  Source generation does not prove that the client renders the Chinese line
  693 or that its NAVI link still shows and targets izlude 122,207. The
  coordinator verifies those in the running game.
