# Renewal solo milestone: goal and feasibility

Last reviewed: 2026-10-18. Owner: coordinating Codex agent. Current work: documentation only.

## User decisions

The first milestone is a personally playable, Mac-local **Modern / Renewal Ragnarok Online** build, including maps, monsters, story/quests, Traditional Chinese game UI and text, and persistent solo progress. The user requested durable documentation for stateless agents, supervised phases, task-level Claude/Grok comparisons, coordinator verification before user evaluation, and Git rollback controls.

The user selected Renewal rather than classic/pre-renewal. “All” must be evaluated against a named episode/content manifest; it does not currently identify an episode or prove parity with the latest Taiwan or Korean service. Do not silently reduce the requested story or world to a sample.

Traditional Chinese means menus, item/skill/monster names and descriptions, quest log, NPC dialogue, story text and system messages. Launcher/settings localization is tracked separately so it cannot be mistaken for game localization. Font rendering, text encoding and macOS input must work as well as translations.

Open decision: whether companions and documented changes may remove party-only progression gates. A question has been sent to the user. Preserve this as undecided until answered; documentation can proceed, gameplay changes cannot rely on presumed approval.

## Proposed foundation

Evaluate **Ragnarok Offline v1.6.3**, which packages rAthena, roBrowserLegacy, MariaDB and a local microVM/Electron shell. An app can be local and offline while running server components on the same Mac. This changes the earlier server-free Godot study's architecture; a public multiplayer service is not requested.

Godot and the asset factory are deferred research for this milestone. Reusing a functioning RO stack is the credible route to broad existing content. A full engine reconstruction is a separate, much larger goal. The foundation remains a candidate until the runtime, Chinese and content gates pass.

## Feasibility assessment

| Area | Current evidence | Judgment / unresolved work |
| --- | --- | --- |
| Mac hardware | Locally inspected M1 Max, 64 GB RAM, more than 500 GiB free | Likely sufficient; actual CPU, memory, GPU/frame time and thermal behaviour unmeasured |
| Packaged local runtime | Publisher provides Apple Silicon v1.6.3 and describes a bundled RO stack | Credible trial candidate; no installation or local gameplay verified |
| Renewal content | Publisher documents Renewal mode and tested kRO client assets | Exact episode, quest/instance completion and Taiwan equivalence unknown |
| Traditional Chinese | Official Taiwan client download exists; candidate documents an English overlay and Korean/Western decoding | Taiwan/Big5 compatibility, UI coverage and server dialogue translation unverified; primary technical risk |
| Full world/story | Existing emulator content provides a head start | Asset/database presence is not proof of working AI, quests, instance logic or solo completion |
| Progress and recovery | Publisher documents database backup/restore | Must test locally; a Git revert cannot recover a save or database |

Conclusion: **conditionally feasible as an integration/localization project**. Full latest-official-content parity and complete Chinese story coverage have no defensible schedule yet. Missing emulator features or translations can turn them into substantial implementation work. Do not promise a complete world on the setup estimate.

## Estimates and resource budget

These are planning estimates from the discussion, not measurements, guaranteed delivery dates or a full-milestone quote.

| Work/resource | Initial planning allowance | Assumptions |
| --- | --- | --- |
| Basic feasibility trial | 2–4 engineering hours after compatible assets are available | Packaged app works; no substantial runtime or encoding fix required |
| First coverage/localization inventory | 1–3 working days | Inventory/report only; not all quests tested or translated |
| Full milestone | Unestimated until inventory and a pilot establish remaining work | Count translation units, missing systems and verification workload first |
| RAM | Budget 6–8 GB for the combined app initially | Publisher's VM default ceiling is 4 GB; total host usage is not yet measured |
| Disk | Reserve 20–30 GB initially | App, approximately 4.5 GB runtime data, game assets, extraction and backup headroom; actual footprint unmeasured |
| New infrastructure | No cloud host or hardware purchase expected for the trial | Existing Mac; external service/API purchases are not part of this plan |

At the trial checkpoint, record actual elapsed engineering time and observed resources, then re-estimate. Simulated population starts disabled; benchmark optional companions separately.

## Known local starting state

- Source checkpoint before this documentation work: `c6314bbd85caa01f54fdcc38d62168e101e2c5a4`.
- Coordination branch: `ShemYu/reverse-the-Ragnarok-Online-to-play-by-myself`.
- Earlier Godot code and source-only checks exist. Reference and Character Lab asset directories in this checkout contain READMEs only.
- A bounded search of Downloads, the original project directory and Applications found no matching GRF/archive candidate. This is not a machine-wide absence claim.
- No Ragnarok Offline app or game asset download/install was performed during the source research. No local runtime, Chinese or gameplay result has been established.

## Evidence sources

Checked 2026-10-18; publisher statements are distinct from local verification.

- [Ragnarok Offline v1.6.3 release](https://github.com/Flux159/ragnarokoffline.app/releases/tag/v1.6.3). Release metadata: published 2026-10-16; Apple Silicon DMG approximately 245.5 MiB. Pinned DMG SHA-256: `2073bdf311dab09e77ea6e1dca746cd3837acbc1417f099d900c4d13bb427f19`. A future downloaded file still needs its own hash check.
- [Versioned README](https://github.com/Flux159/ragnarokoffline.app/blob/v1.6.3/README.md): architecture, Renewal mode, supplied assets, English translation and decoding settings.
- [Versioned advanced features](https://github.com/Flux159/ragnarokoffline.app/blob/v1.6.3/docs/ADVANCED_FEATURES.md): disk footprint, backup/restore and differences between client navigation tables and server-loaded content.
- [Official Taiwan RO download](https://ro.gnjoy.com.tw/download/program_download.aspx): listed client download, approximately 3.78 GB at inspection. Its availability is not proof of compatibility, translation reuse coverage or a complete story implementation.
- [rAthena quest example](https://github.com/rathena/rathena/blob/master/npc/quests/quests_prontera.txt): server-side dialogue and quest logic are separate from client UI. This unpinned example explains architecture, not the candidate's exact bundled quest coverage.
- [Hercules localization](https://docs.herc.ws/customization/localization-huld/): server dialogue translation has its own mechanism and limitations. Hercules is an alternative, not a feature supplied by the rAthena-based candidate.

Keep original source rights/provenance and the existing [source-only repository boundaries](../PUBLIC_REPOSITORY.md) intact. Do not commit downloaded assets or whole local app backups.
