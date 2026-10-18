# Traditional Chinese Captain Carocc pilot (T05.001)

`carocc_zh_pilot.py` builds the server-script mod **tw-carocc-pilot** from the
pinned rAthena `academy.txt` packaged with Ragnarok Offline v1.6.3. Captain
Carocc in Izlude then greets a new Novice in Traditional Chinese. Python 3
standard library only. Nothing is installed and no game state is touched.

```sh
python3 -I tools/renewal/carocc_zh_pilot.py \
  /path/to/T04-source/academy.txt .tools/renewal/T05.001/candidate
CAROCC_ACADEMY=/path/to/T04-source/academy.txt \
  python3 -I -m unittest discover -s tools/renewal
```

Without `CAROCC_ACADEMY` the three real-input tests are reported as skipped;
the synthetic and publication tests still run. No stock script is committed.

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

Exactly eight display literals are translated. Latin names Carocc and Izlude
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
- Masking the eight translations and the header name back must reproduce the
  source block **byte for byte** (tabs, LF endings). Only the header and the
  six translated lines may differ, and counts of `mes`, `select(`, `next;`,
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

Not done by this tool. Copy `tw-carocc-pilot/` into the supported mods
directory, restart, and check the load log. Turning the mod off and restarting
removes the clone and the controller, so the stock English Captain Carocc#iz
is back. No SQL, quest or save change is involved.

## Limits

- Only the first-visit Novice opening, its menu and the Hello? reply are
  Chinese. Choices 2 and 3, the 4269/7471/7472 branches, the post-novice
  Pharos/Alberta menus and all other text stay English.
- Duplicates on `izlude_a`..`izlude_d` stay English and enabled.
- Not checked here: the map server loading the script, client rendering of the
  UTF-8 text, menu clipping, the quest marker of the clone, or dialogue flow.
  The coordinator verifies those in the running game.
