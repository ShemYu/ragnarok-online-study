# Project handoff

## Read first

1. [Current status](docs/project/STATUS.md): active task, evidence, blockers and next action.
   Use the [ASCII project map](docs/project/PROJECT_MAP.md) for remaining work and [History](docs/project/HISTORY.md) for completed records. Status is authoritative for execution/pause state and the next action.
2. [Goal and feasibility](docs/project/GOAL.md): current user decisions and unresolved scope.
3. Your assigned row in [Tasks](docs/project/TASKS.md), its phase in [Phases](docs/project/PHASES.md), and [Workflow](docs/project/WORKFLOW.md).
4. Confirm `git status --short`, branch and HEAD before working. Stop and report an unexpected branch or another worker's edits; do not overwrite them.

## Current scope

- The first milestone targets the **full Modern / Renewal RO game** on this Mac: maps, monsters, story, Traditional Chinese game UI/text and persistent personal play. The user clarified on2026-10-19 that this is not a single-map game. Party-only activities and their solo adaptations belong to a later phase.
- T06/T07 must identify actual version/content coverage and gaps without reducing that full-game intent. Inventory party-only entries explicitly as later-phase work; do not require T11 for first-milestone acceptance or infer approval for companions/rule changes.
- **Current priority: functionality first** (user clarification2026-10-19). Verify maps, monsters, combat, jobs, items, quests and persistence before remaining localization/input work. Keep existing Chinese overlays enabled. T05 remains open with deferred checks; it does not block functional inventory/repairs. Reuse existing text/resources before bulk translation; full Traditional Chinese remains in the final goal.
- The exact episode and completeness are **not verified**. The candidate is Ragnarok Offline v1.6.3, not a confirmed foundation.
- Execution is **paused at the 2026-10-25 handoff**. The user currently authorizes documentation cleanup, conservative repository lint/trim and committing/pushing the current feature branch. Preserve behavior; trace references and check regressions before removing code. A default-branch merge remains unauthorized. Keep game implementation paused until the user resumes it. The earlier authorization to execute the full strategy remains the scope for resumption; it is not a completion claim. Check Status and the thread goal before acting.
- The user retired Godot and Character Lab from the active tree on 2026-10-25. Their complete source/report snapshot is preserved at Git tag `archive/legacy-prototypes-2026-10-25` (`62dde90`). Do not restore those projects into the active tree without a new reason. Preserve ignored local assets and all Renewal/project evidence; see the archive record linked in Status.

## Coordination and evidence

- Use Orca for supervised Claude/Grok/Kimi work. Follow the version-matched orchestration guide and dispatched lifecycle instructions.
- Do not run bundled docker-slim subcommand `--help` probes. This client's advertised help is unreliable: `volume create --help` created a volume named `--help`. Root removed only that new unused volume and verified absence/original-container preservation. Use pinned Engine/client source and fixed read-only API discovery instead; see the [capability/cleanup record](docs/project/reviews/2026-10-23-T10.007.md#bundled-cli-help-is-unreliable-unexpected-volume-cleaned-up).
- Compare Claude and Grok independently on each bounded task using the same frozen inputs and acceptance criteria. Record plan-only comparisons as plan-only.
- From the user's2026-10-24 clarification, test Kimi in shadow mode on1–3 suitable real tasks alongside the main work. Track used pilot slots and results in T07.007.012.010; use at most3tasks total before the pilot verdict. Keep the same frozen inputs/scorecard, no main-path dependency on Kimi, and Root verification before using its output. Track availability, verified quality, elapsed time and rework separately; cost/tokens remain not observed when unavailable. Do not create extra work just for benchmarking, backfill historical pairs or call a source plan proven implementation ability.
- From the user's2026-10-25 instruction, include Muse in3useful real tasks and report its likely strengths after all3. Track T07.007.012.011 and the [Muse record](docs/project/reviews/2026-10-25-Muse.md). Keep pilot slot, frozen inputs, actual configured/provider-reported model, quality, time, corrections and scope distinct. A repair/follow-up is the same pilot task. No extra work solely for benchmarking or unsupported provider-winner/implementation claim; Root verifies before use.
- Workers own only their dispatched scope. Implementation attempts need separate branches/worktrees; two worktrees do not isolate an app's external database.
- The coordinator must personally perform the applicable verification before `ready_for_user`. A worker's PASS is a candidate result, not coordinator verification or user acceptance.
- Update the task row, status, evidence and next action at every meaningful checkpoint. A stateless worker must not need a chat transcript to resume.
- Keep STATUS, PROJECT_MAP and TASKS focused on unfinished work. Move finished records into dated history with their original scoped status and evidence; retain frozen briefs/profiles and pending user acceptance. Follow [documentation maintenance](docs/project/WORKFLOW.md#active-documentation-and-completed-history).
- Before advancing from a completed or coordinator-verified step, commit its owned changes and redacted verification record on its task/coordination branch. Include no-change findings as Markdown evidence; never rely on an uncommitted report or chat alone.
- Never promote a sample playthrough into proof that all maps, monsters or quests work. Track coverage and remaining gaps explicitly.
- Notify the user promptly when evidence shows a critical issue may require changing the agreed goal. Explain the evidence, options and scope impact; wait for the user's decision before changing the goal. Continue independent work that preserves it.

## Git and local data

- Work on the assigned task branch, never directly on `main`. Start paired implementations from the same recorded commit.
- Make local checkpoint commits after coordinator verification. Push the feature branch when explicitly requested by the user, as authorized for this handoff. Default-branch merges, force-push and shared-history rewrites remain separate actions.
- Revert verified checkpoint commits to roll source changes back. Git does not restore app databases, saves, installed files or untracked assets; use tested external-state backups.
- Keep game assets, installers, screenshots, logs, credentials and database dumps local. Commit redacted Markdown evidence and source only; follow [repository scope](docs/PUBLIC_REPOSITORY.md).
- Do not store private hardware identifiers, credentials or machine-wide environment dumps in documentation.

## Completion handoff

Return task ID, base/candidate commit, files changed, checks and actual results, limitations, evidence path, and the next owner/action. Use `accepted` only after the user's explicit evaluation. See the exact [status definitions](docs/project/WORKFLOW.md#task-status).
