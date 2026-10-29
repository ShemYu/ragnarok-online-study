# Ragnarok Online Study — Renewal solo milestone

The current goal is the **full Modern / Renewal RO game** for personal play on this Mac, including maps, monsters, story, Traditional Chinese game UI/text and persistent progress. Party-only activities and their solo adaptations are a later phase. The proposed foundation is an existing RO emulator/client stack; its exact version, complete content coverage and full Chinese support still need verification. The content inventory must expose gaps without reducing the goal to a small sample.

**Current priority: gameplay functionality first.** Verify maps, monsters, combat, jobs, items, quests and persistence before remaining translation/input work. Existing Chinese support stays enabled; full Traditional Chinese remains in the final goal.

**Start at [current status](docs/project/STATUS.md).** Stateless agents should read [AGENTS.md](AGENTS.md), then the assigned task and evidence. Runtime and content claims require the task-specific evidence recorded there; the current pause state controls execution.

**Current handoff (2026-10-25): game execution is paused.** Basic local browser
play and saved progress are verified; full world/story/Chinese coverage remains
unfinished. The active documents show remaining work, with completed records
preserved in [History](docs/project/HISTORY.md). The current authorized work is
conservative source cleanup, archiving the retired prototypes and feature-branch
publication. On 2026-10-28 the user also authorizes a merge into local `main`;
the reviewed source is fast-forwarded locally. `origin/main` stays unchanged.

The 2026-10-29 [expert re-audit](docs/project/reviews/2026-10-29-T00.005.md)
defines [seven bounded next tasks](docs/project/NEXT_ACTIONS.md). Inspection
and design proceed; game implementation and installation remain paused.

| Planning document | Purpose |
| --- | --- |
| [Goal and feasibility](docs/project/GOAL.md) | Decisions, known facts, uncertainties, candidate sources and initial estimates |
| [Supervisory phases](docs/project/PHASES.md) | Coordinator verification and end-user acceptance at each gate |
| [Unfinished task board](docs/project/TASKS.md) | Remaining tasks, dependencies, next actions and acceptance contracts |
| [Completed work and history](docs/project/HISTORY.md) | Original task dispositions, verification evidence and dated snapshots |
| [Workflow and Git control](docs/project/WORKFLOW.md) | Paired Claude/Grok comparison, stateless handoff, branches and rollback |
| [Roadmap](ROADMAP.md) | Active direction and deferred historical work |

## Repository scope

The active tree contains Renewal integration tools, authored tests and project
records. Game assets, the local app, saves, credentials and raw runtime evidence
stay outside Git. A fresh source checkout can run the checks below; it does not
install or launch the game. See [publication scope](docs/PUBLIC_REPOSITORY.md)
and [Renewal tools](tools/renewal/README.md).

## Source-only checks

With Node.js 22+ and Python 3.9+:

```sh
python3 tools/check_public_tree.py
python3 tools/check_source.py
uvx --from ruff==0.16.9 ruff check --config ruff.toml --no-cache tools tests
node --test tests/renewal/quest_text_projection.test.mjs tests/renewal/quest_registration_tail.test.mjs
python3 -I -B tools/renewal/test_chapter1_entry.py
```

The lint command uses `uvx` to run the pinned tool in isolation; an existing
Ruff 0.16.9 installation can run the same arguments directly. CI installs that
version with pip. Lint checks Python errors and unused code; it does not format
files. One documented F401 exception preserves the exact bytes of a materializer
pinned by local replay tooling. Syntax checks parse every tracked Python and
JavaScript file without executing its source. Stage new source files to include
them in this inventory.

CI runs these checks using authored source/model fixtures. Do not replace the
explicit test list with broad discovery: some other suites automatically read
private `.tools` inputs when present. Native tests, browser/gameplay checks
and visual measurements remain separate; a green CI result does not establish
runtime or full-content acceptance.

## Retired prototypes

The user retired the Godot prototype and browser Character Lab on 2026-10-25.
Their code, launchers, tests and reports are removed from this active branch and
preserved under Git tag
[`archive/legacy-prototypes-2026-10-25`](https://github.com/ShemYu/ragnarok-online-study/tree/archive/legacy-prototypes-2026-10-25).
[Archive verification and recovery](docs/project/reviews/2026-10-25-T00.003.md)
records the exact boundary. Existing ignored assets are not deleted.

To inspect the old source without changing this checkout:

```sh
git fetch origin tag archive/legacy-prototypes-2026-10-25
git show archive/legacy-prototypes-2026-10-25:README.md
```

The tag versions source only; it does not contain private assets or saves.
