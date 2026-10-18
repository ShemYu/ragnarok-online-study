# Baseline trial — T04 in progress

Coordinator evidence, 2026-10-18. Base `022ab07`. This is an **intermediate checkpoint**, not a T04 PASS or user gameplay handoff. App/source/assets remain pinned in [Installation](INSTALLATION.md). No goal or episode boundary has changed.

## Verified so far

| Check | Actual result |
| --- | --- |
| Ordinary account | Created a dedicated local test account through the documented login signup; Settings → Accounts explicitly showed **group 0**, enabled. No GM commands or database writes used for progression |
| Character creation | `T04Novice`, ordinary Novice, entered `iz_int`; default GM appearance was not used |
| Movement and portals | Click walking and the bundled keyboard control changed visible coordinates; natural cabin portal reached `iz_int 51,30`, ship exit reached **int_land**. No admin warp |
| Quest | Wounded Swordsman created quest 21001; normal Captain dialogue completed it and assigned 21008 (`最初的戰鬥`). After two natural Poring kills, Sailor accepted two Wood, granted five Magnifiers and completed 21008. Visible levels progressed to base 2 / job 3. Server dialogue remained English |
| Combat and quest loot | Supported Space attack killed natural island Porings; two `取得 木材 1 個` messages appeared. Inventory item info showed `木材`, amount 1 after the first kill, and its Chinese description. Two Wood were accepted by Sailor, confirming the second acquisition. This is a quest-granted item, not an ordinary ground pickup; that separate check remains open |
| Equipment interaction | Equipment window showed `短劍` and `棉襯衫`. Double-clicking the sword removed it; double-clicking its inventory item re-equipped it, with matching Chinese system messages. Removing the shirt created state B |
| Save and full relaunch | Logged out through the game menu; read-only SQL confirmed online 0. Gracefully stopped the entire app/VM, observed phase Stopped and no game/admin listeners, then started a new headless process and logged in again. Character, item/equipment and quest tuples matched A; visible map coordinates and quest title also returned |
| Backup A → restore A | Used actual browser Settings → Save data → Back up everything, then Restore everything; Renewal plus settings/mods selected. After changing equipment to B and preserving a separate B archive, restoring A returned all recorded character, item and quest rows **exactly** to A. The server returned Ready. Root re-entered the world, observed the restored location/quest and both equipped items. The automatic B safety copy was then restored: all three logged-out SQL groups matched B exactly, and the game showed position 74,101, the quest and no equipped shirt. Normal inventory double-click re-equipped the shirt, with Chinese confirmation |

### Saved states

Both use the same ordinary account and character. Read-only queries used the supported `ragnarok-stack sql` interface. They selected character/inventory/quest fields, never account passwords, and made no SQL writes. The comparison ignores `online` only during an active login; logged-out A and restored A matched it too.

| Field | A | B |
| --- | --- | --- |
| Base/job level; EXP; zeny | 1 / 1; 0 / 0; 0 | Same |
| Last map / position | `int_land 74,101` | Same |
| Save point | `int_land 77,101` | Same |
| Item 1201 (Knife; UI `短劍`), count / equip mask | 1 / 2 | 1 / 2 |
| Item 2301 (cotton shirt), count / equip mask | **1 / 16** | **1 / 0**, removed normally through equipment UI |
| Item 23484, count / equip mask | 1 / 0 | Same; item name/use not yet qualified |
| Quest 21001 | state 1, counters 0 | Same |

Private backups are under `.tools/renewal/backups`, user-only files in a user-only directory. Their existence/hash is not by itself a restore PASS; actual A restoration above is separate evidence.

| Archive | Bytes | SHA-256 |
| --- | ---: | --- |
| `T04-B0-fresh.tar.gz` (before test account/character) | 14949 | `9fb9fc1062806f11f02661e855c2978d6a5db30b14814f8df2bd82631f356c82` |
| `T04-A-quest.tar.gz` | 15358 | `0e47c2965ef097a76d3c648e1785d2d29b5ab12815b9d6e26f2a48943b9e4432` |
| `T04-B-equipment.tar.gz` | 15433 | `5be72a77581fe55e164b36d84ebae47cf941ca9216b959eca6542ad5afeb4849` |

Restoring A automatically preserved B at `state/world-backups/before-restore-everything-20261018-045612-50ac23d8.tar.gz` under app support: **15463 bytes**, SHA-256 **`33447c4e7b1dd7b72cf32a1a4ce641308c5c9ccd0e14b73109320ff86932fb74`**. Do not delete it. At 05:03–05:06 UTC the actual Save data UI restored this automatic B copy. Read-only character, inventory and quest outputs matched the original B snapshot exactly, including online 0. Root entered the world and verified position 74,101, the quest and an empty shirt slot. The shirt was then re-equipped through inventory, with `棉襯衫 裝備穿著完成` confirmation. The A → B → A → B recovery rehearsal passed for these recorded fields. Preserve both manual archives and every automatic safety archive. Reverse restoration created `before-restore-everything-20261018-050318-6e37a808.tar.gz`: 15424 bytes, SHA-256 `09c2bb5b29af229a8e4b4d704545b7f4a6be0987d9cedeafe80ba1c25c866577`.

## Tutorial loot source check

Root inspected the pinned rAthena sources (`0693b8c69911d5ca42269684aa036b67d67f4d3e`) independently after a supplemental audit. [Quest 21008](https://github.com/Flux159/rathena/blob/0693b8c69911d5ca42269684aa036b67d67f4d3e/db/re/quest_db.yml#L12643-L12648) grants Wood for G_PORING kills at 100%; [quest handling](https://github.com/Flux159/rathena/blob/0693b8c69911d5ca42269684aa036b67d67f4d3e/src/map/quest.cpp#L809-L832) adds it directly to inventory. [Mob 2401](https://github.com/Flux159/rathena/blob/0693b8c69911d5ca42269684aa036b67d67f4d3e/db/re/mob_db.yml#L57447-L57474) defines neither ordinary drops nor EXP; the constructor defaults both EXP values to zero. The absence of kill-EXP growth here is therefore not an observed defect. General autoloot settings were not inferred from this quest reward.

The actual Captain reward visibly changed the character to base/job 2/2 (5.8% base); read-only SQL recorded base EXP 52/job EXP 9, completed 21001 and active 21008. The later Sailor reward visibly changed job level to 3 and base EXP display to 17%. This is quest EXP, not normal monster EXP. Ground pickup and normal monster EXP still need their own scenario outside this tutorial mob.

## Resource observation running

An ignored Python sampler started **04:45:26 UTC**, with 10-second samples for a planned 1800 seconds / 181 points, ending about **05:15:26 UTC**. It is still live at this checkpoint; no 30-minute result is claimed. `.tools/renewal/T04-resource-sample.py` records cumulative CPU-time deltas and RSS by app Electron, asset server, VM daemon, matching host Virtualization processes and **all shared Chrome processes**. RSS sums can double-count shared pages; Chrome includes other user tabs and is not the game's exclusive memory cost. The Virtualization group also sums every matching process: the final report must verify sole ownership/counts against the app lifecycle, or label it shared/uncertain. No per-tab memory claim is available.

The trial uses a **3440×1296 visible viewport, DPR 1**. The game's graphics UI lists a **60 FPS limit**, left unchanged; its legacy resolution selector displays 800×600 while the actual viewport is larger, so do not report that selector as the measured resolution. Root enabled the supported **Esc → Graphics Settings → Basic → FPS Display**. Observed readings near 60 are approximately one-second client render-loop averages, sampled at named scenarios; they are not GPU timing or frame-time percentiles. CUA's read-only page scope did not expose `requestAnimationFrame`, so the proposed injected frame logger was not used. A Chrome-internal diagnostics URL was policy-blocked; no alternate route to that blocked page was attempted.

This is a **mixed gameplay/maintenance observation**: tutorial play, menus, logout, a full app restart, backups and restore. Preserve the timestamps and report maintenance gaps separately from active scenes. It is not a continuous heavy-combat stress test. Final CPU/memory/FPS/disk figures remain open until the actual observation finishes and is inspected.

Local measurement-script SHA-256: `00109327e4bec72d145775c1dde066a0aa218e0ea9a2e45f2901ecaa0d6a4986`; read-only save-query helper: `af74dcf1828d9c770f4984849ee08e1a82e5ec0c0288d46b5cac3f4baceaf5cb`. They remain with ignored trial tooling/evidence; this Git checkpoint preserves their fingerprints, method and results, not private execution files. Through the partial observation, matching Virtualization process counts were 0 or 1; recheck the completed series.

## Issues and limits

- Missing optional import overrides did not prevent login, map loading or saving. The pinned 20221005 protocol disables the newer item-icon script feature. Keep those messages recorded rather than changing protocol merely to silence them.
- Roulette has missing/default data substituted with Apples: a **content gap**, not proof that roulette is unnecessary offline. The disabled companion recruiter emits an initialization error; companion behavior remains unverified. Carry these into T06 and applicable gap tasks.
- At 05:12 UTC root dropped exactly one of five owned test Magnifiers through ordinary inventory drag and the amount dialog in Izlude; inventory fell to four. No visible ground sprite appeared. Console at 05:12:28.950 recorded missing `data/sprite/¾ÆÀÌÅÛ/???.act` and `.spr`; inventory icon requests also used `???.bmp`. A pickup has not passed. This concrete encoding/asset defect is T04.002; preserve it as a reproducer for paired diagnosis. No goal change is currently required.
- Client console reports missing UI bitmap requests and an unregistered `0x08e2` packet. Several icon/button labels are blank or English. T05 must diagnose exact effects; current samples do not certify all UI/features.
- Controlled targeting at 05:06 UTC passed: keyboard movement was disabled; right-clicking the visible Captain without dragging showed his hover name and retained position 74,101; a subsequent left-click at the same point opened the normal dialogue. The same sequence opened Sailor dialogue at 59,71. No client fix was made. This is consistent with cached picking, not a comparative proof of causation.
- Targeting the captain and moving behind scenery took extra inspection. The keyboard plugin can finish an accepted path after release; Controls → disabling Keyboard movement clears intent. The current source also disables Q/E and Space attack with that master checkbox. Root re-enabled it and observed combat. Timing/target history does **not yet prove a stuck-key defect**. Natural captain dialogue subsequently passed; ordinary ground pickup remains open.
- Some menu/target clicks coincided with extra map movement. Early screenshots also preceded map/UI initialization (including a transient 0 FPS reading). The restored location was observed before those later actions; do not mistake subsequent movement for a restore mismatch. A supplemental source audit found mouse picking cached until rendering, while GUI hover has guards against map clicks. This supports a pointer-timing hypothesis, not a proven defect. The controlled right-click → rendered observation → left-click diagnostic subsequently opened the normal Captain dialogue without movement, as recorded above.
- A loopback listener or absence of observed internet traffic does **not** prove offline operation. A calibrated restricted-network test remains required, preserving the user's general Mac networking. Neither provider's proposed offline gate was accepted unchanged.
- Native desktop-window interaction, complete Chinese dialogue, episode completeness and all-world solo progression remain unverified. No confirmed critical issue presently requires changing the goal.

## Resume actions

1. Confirm branch/HEAD/status and this task's owned files. Revalidate the existing app and sampler handles/processes; do not restart a live job because an observation timed out. The current coordinator's execution handles are recorded locally in `.tools/renewal/evidence/T04-live-handles.json`; they are hints, not proof of liveness.
2. A/B restoration, controlled NPC targeting, natural tutorial combat, quest-item acquisition and Sailor turn-in have passed. The ordinary ship exit reached Izlude; actual game showed position 193,211. No admin move/quest completion.
3. Diagnose the missing ground-item sprite in T04.002, then repeat ordinary pickup. A normal inventory drag dropped one of five test Magnifiers, leaving four; its sprite failed to load. Do not claim a pickup PASS or silently replace normal loot with tutorial rewards.
4. Complete a calibrated offline trial and the full timed resource/disk report. The sampler ends about 05:15:26 UTC; inspect its actual completion and samples, not just its intended duration.
5. Commit each meaningful verified checkpoint. Keep T04 `in_progress` until all required checks pass; then prepare the basic playtest. T05 Chinese pilot follows, with no reduction of the full goal.

Evidence remains ignored: `T04-observations.jsonl` and named screenshots, `T04-save-{A,B}.json`, `T04-relaunch-check.json`, `T04-after-restore-A.json`, `T04-after-restore-B.json`, backup metadata, raw logs and resource samples. The local test login is in a separate user-only ignored file; never publish it or the admin URL. See [paired review](reviews/2026-10-18-T04.md).

Git revert restores these source/docs records only. Recover game state through the preserved, tested A archive or verified automatic B archive; machine asset paths and GRFs remain separate. No existing user's progress was overwritten.
