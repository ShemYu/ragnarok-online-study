# Task board

Task owner: coordinator unless dispatched. Date: 2026-10-18. The user has authorized executing the strategy and finishing all steps after the documentation checkpoint. Task states below distinguish completed evidence from future work. See [Workflow](WORKFLOW.md) for state transitions, paired comparisons and Git control; [Status](STATUS.md) is the resume point.

## Dependency map

`T00 → T01 → T02 → T03 → T04 → T05 → T06 → T07 → {T08, T09, T10, T11} → T12 → T13`

T05 may begin a read-only compatibility assessment alongside T02; its actual in-game pilot needs T03/T04. T02 verifies acquisition/extraction only; later tasks establish runtime compatibility. T05 may create bounded encoding/compatibility diagnosis or fix children before T07; it must not wait for the later bulk localization tasks to resolve a foundation blocker. T08–T11 can run in parallel only with disjoint source and isolated runtime state. Split newly discovered gaps into numbered children before implementation. A dependency arrow is a gate, not a claim that every future task has a known workload.

If an inventory shows no work is needed in one of T08–T11, both models assess that finding and the coordinator supplies a verified no-change report. Do not invent modifications or leave an empty task blocking qualification.

| Task | Phase | Deliverable | Depends on | Status | Paired comparison / evidence |
| --- | --- | --- | --- | --- | --- |
| T00 | P0 | Documentation, feasibility, task plan and Git/verification protocol | — | `accepted` | Checkpoint `35ad527`; user gave go-ahead to follow strategy and finish all steps |
| T01 | P1 | Pinned foundation/source manifest | T00 | `ready_for_user` | [Verified manifest](FOUNDATION.md), [paired review](reviews/2026-10-18-T01.md); Claude 17/20, Grok 18/20; source audit only |
| T02 | P1 | Asset acquisition/extraction manifest; runtime compatibility pending | T01 | `ready_for_user` | [Verified acquisition](ASSETS.md), [paired review](reviews/2026-10-18-T02.md); Claude 18/20, Grok 14/20 on plans; root extracted/hashed actual files |
| T03 | P1 | Reproducible local installation with version/hash record | T02 | `ready_for_user` | [Installation](INSTALLATION.md), [paired review](reviews/2026-10-18-T03.md); Claude 14/20, Grok 17/20 on plans. Root verified headless/browser character screen and shutdown; native-window interaction open |
| T04 | P1 | Baseline play, persistence, offline and resource report | T03 | `planned` | Paired test designs; coordinator personally runs integrated scenarios |
| T05 | P1 | Traditional Chinese encoding/UI/story pilot | T04 | `planned` | Isolated text fixtures and independent diagnosis; root verifies in game |
| T06 | P2 | Full candidate content and localization inventory | T04, T05 | `planned` | Independently generated inventories or validators on the same snapshot |
| T07 | P2 | Exact episode/content contract and full-work estimate | T06 | `planned` | Paired coverage assessments; root audits evidence; user accepts scope |
| T08 | P3 | Client/launcher localization gaps resolved | T07 | `planned` | Separate candidate branches and fixture outputs; one task per gap batch |
| T09 | P3 | Server NPC/story/system localization gaps resolved | T07 | `planned` | Separate candidate branches; preserve quest logic and IDs |
| T10 | P3 | Missing/broken in-scope gameplay content resolved | T07 | `planned` | Reproducer and child task per defect; compare isolated implementations |
| T11 | P3 | Approved solo progression changes | T07, solo decision | `planned` | Paired approaches; external state isolated; decision still open |
| T12 | P4 | Coverage qualification and recovery/performance report | T08–T11 | `planned` | Independent regression plans/fixtures; root verifies final integrated build |
| T13 | P4 | Reproducible user handoff and acceptance | T12 | `planned` | Paired runbook reviews; root rehearses; user evaluates experience |

## Task acceptance contracts

### T00 — documentation baseline

- **Output:** current goal, feasibility sources, phase gates, task board, stateless startup instructions, model comparison protocol, Git/backup recovery distinction and durable initial review.
- **Coordinator verification:** personally review both model proposals; check current source claims and dates; inspect the full diff; verify local links/anchors and task IDs; `git diff --check`; stage owned Markdown only and run the public-tree path guard; create a local documentation checkpoint.
- **User evaluation:** start with STATUS and identify the active phase, unknowns, next action, acceptance criteria and rollback procedure without reading chat history.
- **Do not claim:** installed app, working Chinese, complete content, a future model winner or user acceptance.

### T01 — foundation/source manifest

- **Output:** pinned app artifact URL/hash/version, server/client source revisions when obtainable, provenance, supported-platform evidence and known feature limits; no inferred episode from an installer year.
- **Coordinator verification:** independently confirm release metadata and relevant source at the pinned revision; compare each model's claims; distinguish unavailable version data from confirmed values.
- **User evaluation:** read a one-page recommendation showing what is known, untested and required for the trial.

### T02 — asset acquisition and extraction

- **Output:** local asset paths/hashes/version evidence; source and extraction steps; compatibility matrix for baseline kRO and desired Taiwan text, with missing inputs explicit. Assets remain outside Git.
- **Coordinator verification:** inspect actual supplied files and hash them; confirm expected archive entries and extraction. This closes acquisition/extraction only. Runtime compatibility stays explicitly pending until T03/T05; T02 does not depend on those later tests to supply its input files. A download link alone does not pass compatibility.
- **User evaluation:** the setup instructions identify exactly which files the app uses and what still needs testing; no account or secret is published.

### T03 — local installation

- **Output:** version-pinned, reproducible installation and a record of created app/support files, configured memory/network mode and rollback/removal procedure.
- **Coordinator verification:** verify the downloaded artifact against the recorded hash; personally launch the app; record actual app/server/client versions and startup result. Establish backup and isolated restoration procedure before changing any existing saves. T03 used the publisher's supported headless/browser mode after native window control failed across apps; this mode and its native-UI limitation are explicit in [Installation](INSTALLATION.md).
- **User evaluation:** launch the app through the documented entry point and reach the character screen without agent intervention.

### T04 — basic play, persistence and resource baseline

- **Output:** character creation, walking, fighting, loot, inventory/equipment, map travel, save/quit/relaunch, offline operation and a 30-minute resource observation. Population starts disabled; optional companions are a separate scenario.
- **Coordinator verification:** personally play the scenarios; compare saved values before/after relaunch; check offline operation after initial setup; measure total host app/VM memory, CPU, frame rate/time and disk footprint with a stated method/resolution. Rehearse backup/restore on test progress.
- **User evaluation:** a short play/relaunch script shows the same character, items and quest progress. Performance is judged from an actual scene, not a published memory ceiling.

### T05 — Traditional Chinese pilot

- **Output:** separate results for menus, CJK fonts/input, monster/item/skill names and descriptions, quest log, one server-side story/NPC exchange, system message and launcher/settings; a terminology sample and encoding diagnosis.
- **Coordinator verification:** inspect actual rendered text and macOS input in game; test save/reload of relevant text; verify source strings/identifiers and demonstrate both client text and server dialogue. A screenshot of one menu cannot close the story/localization goal.
- **Pilot disposition:** unreadable/unsupported Chinese needs a bounded T05 child diagnosis/fix or a documented foundation alternative before P1 passes. Readable Chinese with incomplete translations can advance with the exact gaps tracked for T08/T09; the pilot does not require translating the whole world first.
- **User evaluation:** read and interact with the Chinese sample in context. Mark unreadable text, wrong terminology and remaining English/Korean explicitly.

### T06 — content and localization inventory

- **Output:** manifest of expected and present maps/warps, monsters/spawns/skills/drops, items/skills, NPCs, quest chains, instances and text units. Track `expected`, `present`, `loaded`, `exercised`, `verified`, `missing` and verification method separately; define denominator before any coverage percentage.
- **Coordinator verification:** reconcile client assets, server databases and actually loaded scripts; check validator results and negative/missing cases; manually inspect entries including early and later content. Sampling tests the inventory method; it does not certify all gameplay.
- **User evaluation:** review the world/story coverage report and play representative sections; understand the exact gaps and uncertainty.

### T07 — content contract and estimate

- **Output:** supported Renewal episode/edition evidence, frozen required-content manifest, localization/solo expectations, gap tasks and effort estimate derived from measured pilot throughput and gap count. Keep Taiwan terminology and client/server revision distinctions explicit.
- **Coordinator verification:** audit the proposed boundary against T06; verify every exclusion is visible; record assumptions/ranges and unestimated work. Client date or rAthena commit alone is not episode completeness.
- **User evaluation:** explicitly accept the intended world/story and any scope changes. No silent reduction of “all.”

### T08 — client/launcher localization

- **Output:** child tasks for each missing text/UI group, consistent glossary, compatible fonts/input and versioned overlays where appropriate. Game UI and launcher coverage reported separately.
- **Coordinator verification:** compare candidate diffs and rendering; test long strings, substitutions, layout, fallback text, input and regression scenarios on the integrated version.
- **User evaluation:** judge Chinese terminology and readability in affected windows, including item/skill and quest information.

### T09 — server dialogue/story localization

- **Output:** child tasks for missing NPC/quest/system-message groups with a glossary and source mapping; preserve identifiers, control flow, variables, placeholders and quest rewards.
- **Coordinator verification:** inspect the translated script diff and exercise affected quest states; verify options, branches, variables/rewards and persistence; review consistency with client terminology. Machine translation output is a candidate, not an accepted story.
- **User evaluation:** play/read the affected story interactions and report meaning, tone or progression issues.

### T10 — gameplay/content gaps

- **Output:** one child task per missing or broken required feature/quest/instance, with a reproducible failure and bounded fix. Prioritize progression blockers.
- **Coordinator verification:** reproduce the old failure, test both candidate fixes in isolated state, test dependencies and integrated regression, and update each content manifest entry using actual evidence.
- **User evaluation:** play the corrected area or quest using a short scenario; verify the intended behaviour and report remaining friction.

### T11 — solo progression

- **Output:** after the user's decision, document necessary changes/companions, original behaviour, intended solo behaviour and affected quests/instances. If official rules must remain, incompatible solo requirements are unresolved scope, not a pass.
- **Coordinator verification:** test with one real player account; check entry requirements, companion behaviour, mechanics, rewards and save state. An admin warp or forced quest completion is not normal solo progression.
- **User evaluation:** complete the affected progression naturally and judge difficulty/pacing and documented deviations.

### T12 — full qualification

- **Output:** final required-content matrix, root verification evidence, measured resources, regression report, recoverable backup and reproducible setup/upgrade/rollback procedure.
- **Coordinator verification:** account for every required entry; test required quest-chain progression, missing-asset and dependency failures, offline play, restart, backup/restore and applicable update regression. Mark unsupported/skipped entries open. Do not infer completeness from representative scenes.
- **User evaluation:** follow a compact tour plus agreed story/endgame scenarios; inspect coverage evidence and a restore demonstration.

### T13 — handoff and user acceptance

- **Output:** play/setup/recovery guide, pinned source/runtime manifest, selected task commits, known limitations and end-user acceptance record.
- **Coordinator verification:** rehearse the guide on the qualified state; verify links, versions and backups, and ensure the task/phase ledger agrees with actual evidence.
- **User evaluation:** launch, play, resume and recover using the guide. Record explicit acceptance or create issue tasks. Only this acceptance closes milestone 1.

## New gap-task template

Before executing T08–T11 children, assign an ID (for example `T09.001`), dependency IDs, exact affected entries/files, frozen inputs/base commit, observed failure, allowed changes, independent Claude/Grok deliverables, coordinator checks, end-user scenario, external-state backup and next owner. Add its state/review link here or in a linked, task-specific Markdown record; keep this board current.
