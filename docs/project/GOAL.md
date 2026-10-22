# Renewal solo milestone: goal and feasibility

Last reviewed: 2026-10-22. Owner: coordinating Codex agent. Current work: active execution of the documented strategy.

## User decisions

The first milestone targets the **full Modern / Renewal Ragnarok Online game** for personal play on this Mac: maps, monsters, story/quests, Traditional Chinese game UI/text and persistent progress. On2026-10-19 the user clarified that “all content” means the full game, rather than a single-map game, and deferred party-only content to the next phase. The user also requires durable documentation for stateless agents, supervised phases, task-level Claude/Grok comparisons, coordinator verification before user evaluation, and Git rollback controls.

After documentation checkpoint `35ad527`, the user instructed “follow the strategy I told you, finished all these steps” and activated the thread goal. This authorizes local execution of the task board; the earlier documentation-only boundary applied to T00. It is not evidence that the game or later acceptance gates are complete.

The user selected Renewal rather than classic/pre-renewal. T06/T07 must identify the actual version/edition, build a complete content manifest and expose missing content against the full-game goal. A version/manifest is a verification boundary, not permission to declare only the easiest shipped subset complete. The current evidence does not establish parity with the latest Taiwan or Korean service. Root will provide a concrete coverage recommendation; no new user answer is needed to continue the inventory.

Traditional Chinese means menus, item/skill/monster names and descriptions, quest log, NPC dialogue, story text and system messages. Launcher/settings localization is tracked separately so it cannot be mistaken for game localization. Font rendering, text encoding and macOS input must work as well as translations.

**Current execution order: functionality first.** The user clarified on2026-10-19 that translation may be a large job and asked to prioritize gameplay. Next verify full-world maps, monsters, combat, jobs, items, quest progression and persistence, then resolve remaining localization/input work. Existing Taiwan client tables/dictionaries and installed Chinese overlays stay in use; assess reusable resources before translating gaps. This changes work order, not the final Traditional Chinese requirement. Remaining T05 language checks do not block functional inventory/repairs. See the [priority record](reviews/2026-10-19-functionality-first.md).

**Party-only content is deferred to the next phase.** This means activities that actually require multiple players, including any adaptations needed to play them alone. T06 must still list their maps, monsters, story links and prerequisites, clearly marking the deferred activity rather than hiding missing content. Party-only completion and T11 adaptations do not block first-milestone acceptance. A party identity check alone does not establish a multi-player requirement; verify the real gate. No particular companion, entry bypass, reward or balance change is selected by this deferral. See the [decision record](reviews/2026-10-19-scope-clarification.md).

## Proposed foundation

Evaluate **Ragnarok Offline v1.6.3**, which packages rAthena, roBrowserLegacy, MariaDB and a local microVM/Electron shell. An app can be local and offline while running server components on the same Mac. This changes the earlier server-free Godot study's architecture; a public multiplayer service is not requested.

Godot and the asset factory are deferred research for this milestone. Reusing a functioning RO stack is the credible route to broad existing content. A full engine reconstruction is a separate, much larger goal. The foundation remains a candidate until the runtime, Chinese and content gates pass.

## Feasibility assessment

| Area | Current evidence | Judgment / unresolved work |
| --- | --- | --- |
| Mac hardware | M1 Max,64GB RAM; [30-minute measured session](RESOURCES.md) | Ample headroom in the measured baseline; heavy content, GPU timing and thermal behaviour unmeasured |
| Packaged local runtime | Exact signed/notarized1.6.3 installed; ordinary combat, loot, portals, save/re-entry, full relaunch and A/B recovery verified | Viable for the tested browser baseline; native window and full host/browser offline behavior remain open |
| Renewal content | Publisher documents Renewal mode and tested kRO client assets | Exact episode, quest/instance completion and Taiwan equivalence unknown |
| Traditional Chinese | Taiwan assets acquired; Chinese item/skill rendering and direct Unicode chat verified; [T05 pilot](reviews/2026-10-18-T05.md) | Narrow Carocc opening/revisit, Navigation/Quest chrome and active7472text samples now verified with save/re-entry/restart/rollback checks. Full game UI/story and real macOS IME remain open |
| Full world/story | Existing emulator content provides a head start | Asset/database presence is not proof of working AI, quests, instance logic or solo completion |
| Progress and recovery | Ordinary earned EXP, inventory/equipment/quests survive re-entry/relaunch; actual A→B→A→B recovery verified | Newest full O is archive/live-state qualified before the Carocc0.2 update; subsequent dialogue/restart/rollback/reapply checks preserve earned fields. This is not a new restore rehearsal. Git alone cannot recover external state; preserve all archives |

Conclusion: **conditionally feasible as an integration/localization project**. Full latest-official-content parity and complete Chinese story coverage have no defensible schedule yet. Missing emulator features or translations can turn them into substantial implementation work. Do not promise a complete world on the setup estimate.

## Estimates and resource budget

Initial allowances and later observations are distinguished below. Neither is a guaranteed delivery date or a full-milestone quote.

| Work/resource | Initial planning allowance | Assumptions |
| --- | --- | --- |
| Basic feasibility trial | 2–4 engineering hours after compatible assets are available | Packaged app works; no substantial runtime or encoding fix required |
| First coverage/localization inventory | 1–3 working days | Inventory/report only; not all quests tested or translated |
| Full milestone | Unestimated until inventory and a pilot establish remaining work | Count translation units, missing systems and verification workload first |
| RAM | Initial allowance6–8GB; measured app/asset/VM summed RSS median1.85GiB, maximum1.87GiB | Excludes shared Chrome; Chrome's other tabs prevent game-only attribution. Configured VM maximum4GiB is separate; [method and limits](RESOURCES.md) |
| Disk | Initial allowance20–30GB; observed ignored engineering tree13.49GiB, installed app0.51GiB, app support1.06GiB | Asset tree4.50GiB is nested in engineering tree; do not add nested rows. Downloads/source/backups make this larger than a minimal install |
| New infrastructure | No cloud host or hardware purchase expected for the trial | Existing Mac; external service/API purchases are not part of this plan |

Actual sampled viewport3440×1296/DPR1, visible59.9–60FPS at a60FPS cap; this is not a continuous frame-time or heavy-scene measurement. Simulated population remains disabled. Full engineering effort/API cost was not reliably metered; paired dispatch durations are task-level elapsed observations. Setup required item-table repair and further Chinese/rendering work, so the initial2–4hour assumption is not a delivery promise. T07 re-estimates from the remaining inventory.

Current cost decisions, clarified after the user's cost question on2026-10-19:

- No current step is stopped by a verified financial limit. Continue the existing RO stack; a full engine reconstruction remains deferred because it adds implementation and verification work without establishing broader playable coverage first.
- Follow the user's functionality-first order and reuse available Taiwan text/resources before bulk translation. Remaining translation is deferred work, not removed from the final goal.
- Keep independent Claude/Grok comparison on every bounded task. Size tasks around meaningful reviewable deliverables, grouping related small checks within them; do not create a new paired task for each assertion or routine command. Freeze common inputs once and repeat checks when changed source, failures or unresolved concerns justify them.
- The inspected Mac has headroom in the measured baseline; there is no identified hardware/cloud purchase needed for the current checks. This is not a heavy-scene guarantee. Exact provider billing is not observed, so no invented money total or projected saving is reported. Track observable task duration, rework and local resource use; T07 must still produce a gap-based full estimate.

The82remaining RSW resource gaps are open compatibility/content work. Buying
more compute is not an established remedy. If investigation shows a critical
issue that may force a goal change, present the evidence/options to the user
before changing scope; a long task alone does not authorize reducing coverage.

New evidence on2026-10-22: [the actual installed NPC/config snapshot and
source-selected startup closure](reviews/2026-10-22-T07.007.014.004.md#installed-server-snapshot-and-source-selected-startup-closure-qualify)
contain no Chapter1 map-family references or published entry placements. The
whole1185-file NPC tree and all mounted files are inspected; this is stronger
than the earlier checkout-only search, while still not live NPC enumeration or
a complete interpreter of computed strings. The regular-RO provenance is
confirmed. Treat full Chapter1 story implementation as an unresolved in-scope
coverage risk: asset fixes alone cannot meet it. Recommended next action is
locating/verifying reusable licensed quest implementations, then estimating a
faithful repair. Keeping the full goal can add substantial quest implementation
and verification work; a reduced interim release would change the first milestone
and requires the user's explicit decision. No reduced release, chapter exclusion,
party-only classification or revised delivery promise is selected.

Internet remains connected at the user's instruction. [Calibrated connected metrics](reviews/2026-10-18-T04.004.md) demonstrate local traffic and a guest-NAT blind spot in host per-process counters; quiet counters cannot establish full offline operation. Earlier guest-only denial/play is limited separate evidence. Do not disconnect the Mac or mark full host/browser offline proof passed.

## Historical starting state before T01–T05

- Source checkpoint before this documentation work: `c6314bbd85caa01f54fdcc38d62168e101e2c5a4`.
- Coordination branch: `ShemYu/reverse-the-Ragnarok-Online-to-play-by-myself`.
- Earlier Godot code and source-only checks exist. Reference and Character Lab asset directories in this checkout contain READMEs only.
- A bounded search of Downloads, the original project directory and Applications found no matching GRF/archive candidate. This is not a machine-wide absence claim.
- No app/asset download or runtime test had occurred at that original source-research checkpoint. Later installation/gameplay/Chinese results are described above and in [current status](STATUS.md).

## Evidence sources

Checked 2026-10-18; publisher statements are distinct from local verification.

- [Ragnarok Offline v1.6.3 release](https://github.com/Flux159/ragnarokoffline.app/releases/tag/v1.6.3). Release metadata: published 2026-10-16; Apple Silicon DMG approximately 245.5 MiB. Pinned DMG SHA-256: `2073bdf311dab09e77ea6e1dca746cd3837acbc1417f099d900c4d13bb427f19`. A future downloaded file still needs its own hash check.
- [Versioned README](https://github.com/Flux159/ragnarokoffline.app/blob/v1.6.3/README.md): architecture, Renewal mode, supplied assets, English translation and decoding settings.
- [Versioned advanced features](https://github.com/Flux159/ragnarokoffline.app/blob/v1.6.3/docs/ADVANCED_FEATURES.md): disk footprint, backup/restore and differences between client navigation tables and server-loaded content.
- [Official Taiwan RO download](https://ro.gnjoy.com.tw/download/program_download.aspx): listed client download, approximately 3.78 GB at inspection. Its availability is not proof of compatibility, translation reuse coverage or a complete story implementation.
- [rAthena quest example](https://github.com/rathena/rathena/blob/master/npc/quests/quests_prontera.txt): server-side dialogue and quest logic are separate from client UI. This unpinned example explains architecture, not the candidate's exact bundled quest coverage.
- [Hercules localization](https://docs.herc.ws/customization/localization-huld/): server dialogue translation has its own mechanism and limitations. Hercules is an alternative, not a feature supplied by the rAthena-based candidate.

Keep original source rights/provenance and the existing [source-only repository boundaries](../PUBLIC_REPOSITORY.md) intact. Do not commit downloaded assets or whole local app backups.
