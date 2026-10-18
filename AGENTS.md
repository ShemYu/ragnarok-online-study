# Project handoff

## Read first

1. [Current status](docs/project/STATUS.md): active task, evidence, blockers and next action.
2. [Goal and feasibility](docs/project/GOAL.md): current user decisions and unresolved scope.
3. Your assigned row in [Tasks](docs/project/TASKS.md), its phase in [Phases](docs/project/PHASES.md), and [Workflow](docs/project/WORKFLOW.md).
4. Confirm `git status --short`, branch and HEAD before working. Stop and report an unexpected branch or another worker's edits; do not overwrite them.

## Current scope

- The first milestone is a Mac-local, solo **Modern / Renewal RO** installation with the agreed episode's maps, monsters and story, Traditional Chinese game UI and text, and persistent progress.
- The exact episode and completeness are **not verified**. The candidate is Ragnarok Offline v1.6.3, not a confirmed foundation.
- Execution is now **active**: after the documentation checkpoint, the user instructed the coordinator to follow the strategy and finish all steps. Local acquisition, installation, implementation and verification required by the task board are authorized. Keep publication/default-branch merges separate and preserve per-task isolation and rollback. The earlier documentation-only restriction applied to T00, not this execution pass.
- Earlier Godot and Character Lab code and reports are historical research. They do not prove the new milestone works. Preserve them.

## Coordination and evidence

- Use Orca for supervised Claude/Grok work. Follow the version-matched orchestration guide and dispatched lifecycle instructions.
- Compare Claude and Grok independently on each bounded task using the same frozen inputs and acceptance criteria. Record plan-only comparisons as plan-only.
- Workers own only their dispatched scope. Implementation attempts need separate branches/worktrees; two worktrees do not isolate an app's external database.
- The coordinator must personally perform the applicable verification before `ready_for_user`. A worker's PASS is a candidate result, not coordinator verification or user acceptance.
- Update the task row, status, evidence and next action at every meaningful checkpoint. A stateless worker must not need a chat transcript to resume.
- Before advancing from a completed or coordinator-verified step, commit its owned changes and redacted verification record on its task/coordination branch. Include no-change findings as Markdown evidence; never rely on an uncommitted report or chat alone.
- Never promote a sample playthrough into proof that all maps, monsters or quests work. Track coverage and remaining gaps explicitly.
- Notify the user promptly when evidence shows a critical issue may require changing the agreed goal. Explain the evidence, options and scope impact; wait for the user's decision before changing the goal. Continue independent work that preserves it.

## Git and local data

- Work on the assigned task branch, never directly on `main`. Start paired implementations from the same recorded commit.
- Make local checkpoint commits after coordinator verification. Do not push, merge to the default branch, force-push or rewrite shared history as part of this task.
- Revert verified checkpoint commits to roll source changes back. Git does not restore app databases, saves, installed files or untracked assets; use tested external-state backups.
- Keep game assets, installers, screenshots, logs, credentials and database dumps local. Commit redacted Markdown evidence and source only; follow [repository scope](docs/PUBLIC_REPOSITORY.md).
- Do not store private hardware identifiers, credentials or machine-wide environment dumps in documentation.

## Completion handoff

Return task ID, base/candidate commit, files changed, checks and actual results, limitations, evidence path, and the next owner/action. Use `accepted` only after the user's explicit evaluation. See the exact [status definitions](docs/project/WORKFLOW.md#task-status).
