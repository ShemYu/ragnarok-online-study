# Baseline trial — T04 in progress

Coordinator evidence, 2026-10-18. Base `022ab07`. This is an **intermediate checkpoint**, not a T04 PASS or user gameplay handoff. App/source/assets remain pinned in [Installation](INSTALLATION.md). No goal or episode boundary has changed.

Historical T04.003 checkpoint: [T04.003](reviews/2026-10-18-T04.003.md) repaired the Taiwan item-table resource names with a supported client-only UTF-8 source overlay. Root verified ordinary Magnifier **4 → 3 → 4** drop/pickup, Chinese item art, equipment, full app/VM persistence and disable/reproduce/re-enable rollback. At that checkpoint the save was Izlude **176,211**, levels 2/3, user stats preserved, Knife/Shirt equipped, Magnifier ×4, quests complete. Fresh E is pre-overlay; F includes it. Earlier C and missing-art descriptions below are historical checkpoints, superseded only within the explicitly verified repair scope. **Normal-monster EXP and full host/browser offline proof were still open at that checkpoint.** Later results retain their own scope below.

## Latest progress preservation — H

On2026-10-19 JST root re-entered the existing T04Novice at prt_fild08 170,375, base3/job7, EXP781/146, HP51/SP13, then normal character-select logout. A complete six-table read-only snapshot records online0 and all current inventory/quest/skill/registry fields. Fresh full **H** is1862904bytes, SHA256 `d5176952bcdd6e5895b5bb71ee675a37dff74d9e996666274db11c85ec44912d`; every archive payload, protected settings/mod file and selected saved row matches that boundary. Both existing overlays are included/enabled. Actual read-only restore preview was cancelled; **H has not been restored**. Earlier A→B→A→B remains the tested recovery reference, and no old archive may overwrite newer progress. [Current save/backup evidence and next installed gate](reviews/2026-10-18-T05.006.md#fresh-full-h-created-and-validated-before-installation). A later controlled app/asset/service restart preserved every selected saved field and protected file/mode/absence; actual service/assets readiness and unchanged two-mod baseline were verified before installation. This does not independently prove a guest-VM power cycle. [Cold lifecycle evidence](reviews/2026-10-18-T05.006.md#pre-install-cold-lifecycle-and-collision-check). Earlier state/location paragraphs below retain their historical scope.

## Later ordinary live save — Izlude

T05.006 subsequently used only ordinary walking to reach Carocc and verified the named Chinese/body/fallback/control samples. Current normal logout save is **izlude194,211**, base3/job7, EXP781/146, HP51/SP13, zeny0. The complete six-table comparison against H attributes exactly last_map/last_x/last_y, last_login and body_direction changes to travel/sign-in/NPC facing; every other selected field/schema/row is equal. This newer save supersedes H's field location for subsequent restart/off-on comparisons; H remains preserved and was never restored. [Actual dialogue and preservation proof](reviews/2026-10-18-T05.006.md#ordinary-live-sample-and-saved-progress). Re-entry/full relaunch/off-on gates remain next.

## Verified so far

| Check | Actual result |
| --- | --- |
| Ordinary account | Created a dedicated local test account through the documented login signup; Settings → Accounts explicitly showed **group 0**, enabled. No GM commands or database writes used for progression |
| Character creation | `T04Novice`, ordinary Novice, entered `iz_int`; default GM appearance was not used |
| Movement and portals | Click walking and the bundled keyboard control changed visible coordinates; natural cabin portal reached `iz_int 51,30`, ship exit reached **int_land**. No admin warp |
| Quest | Wounded Swordsman created quest 21001; normal Captain dialogue completed it and assigned 21008 (`最初的戰鬥`). After two natural Poring kills, Sailor accepted two Wood, granted five Magnifiers and completed 21008. Visible levels progressed to base 2 / job 3. Server dialogue remained English |
| Combat and quest loot | Supported Space attack killed natural island Porings; two `取得 木材 1 個` messages appeared. Inventory item info showed `木材`, amount 1 after the first kill, and its Chinese description. Two Wood were accepted by Sailor, confirming the second acquisition. This is a quest-granted item, not an ordinary ground pickup; that separate check later passed through ordinary Magnifier drop/pickup in T04.003 |
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

## Resource observation complete

The sampler actually exited successfully: 181 records spanning 1800.002 seconds between first/last samples. Root checked the data, grouping, CPU method, process counts and maintenance gaps. [Measured resource report](RESOURCES.md) records median/max usage, FPS limits and disk footprint. App/asset/VM summed RSS was median 1.85 GiB when all core groups were present; shared Chrome is separately labeled and cannot be treated as exclusive game cost. This mixed play/maintenance session is not a heavy-combat stress test.

Local measurement-script SHA-256: `00109327e4bec72d145775c1dde066a0aa218e0ea9a2e45f2901ecaa0d6a4986`; read-only save-query helper: `af74dcf1828d9c770f4984849ee08e1a82e5ec0c0288d46b5cac3f4baceaf5cb`. They remain ignored with raw evidence.

### Current state C before further runtime trials

Normal logout at 05:14 UTC saved `izlude 188,211`, save point `izlude 128,142`, base/job levels 2/3, EXP 152/17, zeny 0, Knife equip mask 2, shirt mask 16, item 23484 ×1, Magnifier 611 ×4 and quests 21001/21008 both state 2. This includes the one deliberately dropped test Magnifier; no pickup is claimed. Read-only SQL showed online 0. Actual Save data → Back up everything created private `T04-C-izlude.tar.gz`: **15839 bytes**, SHA-256 **`f5a8faa9568b5ee91b7576ee79a407a2552bd01a06dbaac812f53920c0c5da0e`**, mode 0600. It uses the A/B-tested backup format; restoring C itself has not yet been rehearsed.

## Issues and limits

- Missing optional import overrides did not prevent login, map loading or saving. The pinned 20221005 protocol disables the newer item-icon script feature. Keep those messages recorded rather than changing protocol merely to silence them.
- Roulette has missing/default data substituted with Apples: a **content gap**, not proof that roulette is unnecessary offline. The disabled companion recruiter emits an initialization error; companion behavior remains unverified. Carry these into T06 and applicable gap tasks.
- At 05:12 UTC root dropped exactly one of five owned test Magnifiers through ordinary inventory drag and the amount dialog in Izlude; inventory fell to four. No visible ground sprite appeared. Console at 05:12:28.950 recorded missing `data/sprite/¾ÆÀÌÅÛ/???.act` and `.spr`; inventory icon requests also used `???.bmp`. A pickup has not passed. [T04.002 diagnosis](reviews/2026-10-18-T04.002.md) confirmed literal question-mark resource names in the old table and retrievable assets under correct names. T04.003 will implement and test the compatibility overlay; the runtime defect remains open. No goal change is currently required.
- Client console reports missing UI bitmap requests and an unregistered `0x08e2` packet. Several icon/button labels are blank or English. T05 must diagnose exact effects; current samples do not certify all UI/features.
- Controlled targeting at 05:06 UTC passed: keyboard movement was disabled; right-clicking the visible Captain without dragging showed his hover name and retained position 74,101; a subsequent left-click at the same point opened the normal dialogue. The same sequence opened Sailor dialogue at 59,71. No client fix was made. This is consistent with cached picking, not a comparative proof of causation.
- Targeting the captain and moving behind scenery took extra inspection. The keyboard plugin can finish an accepted path after release; Controls → disabling Keyboard movement clears intent. The current source also disables Q/E and Space attack with that master checkbox. Root re-enabled it and observed combat. Timing/target history does **not yet prove a stuck-key defect**. Natural captain dialogue subsequently passed; ordinary ground pickup remains open.
- Some menu/target clicks coincided with extra map movement. Early screenshots also preceded map/UI initialization (including a transient 0 FPS reading). The restored location was observed before those later actions; do not mistake subsequent movement for a restore mismatch. A supplemental source audit found mouse picking cached until rendering, while GUI hover has guards against map clicks. This supports a pointer-timing hypothesis, not a proven defect. The controlled right-click → rendered observation → left-click diagnostic subsequently opened the normal Captain dialogue without movement, as recorded above.
- A loopback listener or absence of observed internet traffic does **not** prove offline operation. A calibrated restricted-network test remains required, preserving the user's general Mac networking. Neither provider's proposed offline gate was accepted unchanged.
- Native desktop-window interaction, complete Chinese dialogue, episode completeness and all-world solo progression remain unverified. No confirmed critical issue presently requires changing the goal.

## Resume actions

1. Confirm branch/HEAD/status and this task's owned files. Revalidate the existing app handle/process; the resource sampler has completed and must not be restarted. The current coordinator's execution handles are recorded locally in `.tools/renewal/evidence/T04-live-handles.json`; they are hints, not proof of liveness.
2. A/B restoration, controlled NPC targeting, natural tutorial combat, quest-item acquisition and Sailor turn-in have passed. The ordinary ship exit reached Izlude; actual game showed position 193,211. No admin move/quest completion.
3. T04.003 repair/art/ordinary pickup/equipment/relaunch/rollback passed. Keep the verified overlay enabled; finish a natural ordinary-monster EXP scenario outside tutorial mob 2401. No admin warp/spawn/quest forcing.
4. Continue T04.001 host/browser offline verification. Guest/container IPv4 restriction, real login/walk/save/re-entry and exact firewall cleanup passed; see its review for limits. Current save is Izlude 176,211 after T04.003; full inventory/quests/skills/registers match E and user stats remain intact. User explicitly requires internet connected; use bounded traffic observations and keep full network-unavailable behavior unverified. The resource report is complete within its stated scope.
5. Commit each meaningful verified checkpoint. Keep T04 `in_progress` until all required checks pass; then prepare the basic playtest. T05 Chinese pilot follows, with no reduction of the full goal.

Evidence remains ignored: `T04-observations.jsonl` and named screenshots, `T04-save-{A,B}.json`, `T04-relaunch-check.json`, `T04-after-restore-A.json`, `T04-after-restore-B.json`, backup metadata, raw logs and resource samples. The local test login is in a separate user-only ignored file; never publish it or the admin URL. See [paired review](reviews/2026-10-18-T04.md).

Git revert restores these source/docs records only. Recover game state through the preserved, tested A archive or verified automatic B archive; machine asset paths and GRFs remain separate. No existing user's progress was overwritten.

## Prontera field fog discriminator — partial T04 checkpoint

2026-10-18. Root naturally walked the existing group-0 character through Izlude's west portal (`20,98`) to **prt_fild08 367,212**. This is an actual second ordinary-map transition, not a GM warp. Ordinary-monster EXP remains pending.

The field rendered nearly solid pale green while minimap/UI and ~60 FPS remained normal. At fixed position/camera, ordinary local chat command `/fog` reported `fog off` and immediately revealed textured terrain, water, buildings and the character. A second `/fog` reported `fog on` and reproduced the green field. Private before/off/on screenshots are under `.tools/renewal/evidence/T04-field-*`. Root inspected pinned ProcessCommand.js178–185 and MapRenderer.js627–634: supported fog toggle and per-map parameters are real. The external fog table/parser needs diagnosis; no engine/asset root cause or permanent fix is claimed. Fog may be kept off as an explicit temporary playtest workaround; toggle again to restore. Do not qualify fog-on rendering or all-map compatibility from the workaround. Preserve progress and never restore older E/F just to undo natural walking.

## Ordinary field EXP and re-entry — verified T04 gate

2026-10-18. With the explicitly recorded fog-off workaround, root used the supported normal nearby-target **Space** control beside ordinary monsters on prt_fild08 (white Lunatic sprite adjacent during the attack). After ordinary combat, the live UI showed job level **3→4** and EXP **17%→33.7%**; no quest turn-in, GM/admin action, SQL write or reward injection occurred. Root then normally logged out: read-only SQL saved **base2/job4, base EXP302, job EXP27**, versus prior base2/job3, EXP152/17. Inventory and completed quests21001/21008 stayed unchanged, Magnifier4 retained, Knife/Shirt still equipped. Saved location **prt_fild08 326,209**, save point remains Izlude128,142. Do not infer an exact monster ID or per-kill formula solely from the adjacent sprite.

Normal character-select re-entry visibly restored level2/job4,33.7%,HP45/SP12 and field326,209; fog-off preference persisted and terrain rendered. Private evidence `T04-field-{ordinary-exp,ordinary-exp-reentry}.png` and `T04-field-after-combat-save.json`. The narrow SQL helper was first invoked without its required output-path argument (read-only queries ran, report write failed); rerun with the explicit evidence path succeeded. This closes the ordinary-monster EXP/persistence sample, not all-monster behavior or fog-on compatibility. [Connected-session metrics](reviews/2026-10-18-T04.004.md) are now measured; full host/browser offline behavior remains unverified under the user's keep-internet-connected constraint.

Full six-table read-only comparison after re-entry also passed: inventory, quests, skills and both character registry tables match the final overlay snapshot exactly. Character changes are the earned job/EXP/skill-point values, map/position and normal login/online state; STR15 and other assigned stats are unchanged. Fresh evidence `T04-field-full-snapshot.json`.

## Later read-only state observation

During T06.002.002's independent provider wave on2026-10-18, root resumed the existing game tab only for a read-only DOM/screenshot check. The UI shows base3/job7/EXP52.5%, HP51/SP13, basic skill6/zero skill points and open inventory/skill panels. Coordinates were196,346 in the DOM and200,346 in the immediately following screenshot; no movement/combat/chat/menu or other game input was sent by root. Attribution of the intervening inputs is not inferred. Earlier root-controlled Prontera156,60/base2/job4 and SQL EXP302/27 are historical checkpoints, not current saved-state verification.

Leave this newer progress and running tab untouched. No logout, restore, fresh runtime mutation, network/window/audio/IME-source change or new SQL read/write occurred. Full backupG predates the story overlay/newer progress; do not restore it over this state. A fresh full backup is needed before a future installed-state mutation. This observation does not requalify persistence, localization, resources or offline behavior.

Private ignored screenshot .tools/renewal/evidence/T06-readonly-newer-progress.png: **1021974bytes/SHA eba6355d82a3e9067bab986753afb473735ddb0d6a9af85b739dd0ff6ad01195**,0600. Authored Markdown only is version-controlled. Next root action remains source-only inventory and personally verifying both candidate implementations.
