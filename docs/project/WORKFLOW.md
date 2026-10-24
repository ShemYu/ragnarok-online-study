# Task execution, model comparison and Git control

## Stateless startup

Read root [AGENTS.md](../../AGENTS.md), [Status](STATUS.md), [Goal](GOAL.md), the assigned [task](TASKS.md) and its [phase](PHASES.md). Verify branch, base commit and working-tree ownership. Read the task's linked evidence, not every historical transcript. If the task lacks acceptance criteria or inputs, ask the coordinator before mutating anything.

## Paired Claude/Grok task protocol

Every task uses an independent Claude candidate and Grok candidate. This compares performance on that task type; no blanket model winner is assumed.

From2026-10-24, the user requests a **1–3 task shadow pilot** of the new
Kimi coding harness through Orca. Run it alongside useful independent work;
do not make game progress wait for Kimi or create benchmark-only busywork.
T07.007.012.010 records trial1 and subsequent shadow use; the pilot is at most
3tasks total before its verdict. Keep the same frozen inputs, acceptance criteria and scorecard
as Claude/Grok, and verify its output before adopting it. Observe the
actual harness/model from launch evidence; inherit its configured default
unless a supported override is explicitly selected. A launch/authentication
failure is a harness-availability result, not a failed reasoning score. Keep
historical Claude/Grok comparisons unchanged. Report task-specific usefulness,
verified quality, elapsed time and coordinator rework; cost/tokens remain
`not observed` unless authoritative usage evidence exists. One trial cannot
establish a general provider winner.

1. Freeze one task brief: ID, target, exact base commit/input hashes, deliverable, allowed mutations, constraints, dependencies, timebox, acceptance checks and user-visible outcome. Use the same brief and same input set for both providers. Record launch defaults/model identities as observed; do not invent hidden model or token-cost data.
2. For documentation/research, collect isolated read-only proposals or separately owned draft files. Neither agent may read the sibling's answer before submitting. For code, use separate Orca-managed task worktrees/branches from the same commit and independent fixture outputs.
3. For a live app/database task, two Git worktrees are insufficient isolation. Compare read-only plans or rehearsals first, label the benchmark **plan-only**, select one for serial execution, and have the coordinator verify it. Compare two actual executions only when separate app state or a tested restore procedure makes that safe. Never call a plan-only winner a proven better implementer.
4. Each worker submits its result, branch/commit where applicable, checks, limitations and evidence. Orca `worker_done` settles worker ownership, not user acceptance. Follow the version-matched Orca skill for launch, mail, release and recovery.
5. The coordinator reads both, checks primary-source claims, and personally executes the relevant checks on each candidate or records the exact reason a check cannot be performed. Reject unsupported PASS claims. A blocked check stays blocked.
6. Record scores, actual elapsed time when observable, corrections/rework, candidate artifacts, scope and chosen approach in a task-linked review. Select the stronger verified candidate, combine useful elements with attribution, or reject both and redispatch. Do not reward speed over correctness.
7. Integrate only the selected change, rerun the required checks on the integrated revision, update tasks/status, and make a local checkpoint commit for that completed/verified step before advancing. This applies to research, no-change findings and gap-task children too: commit the redacted evidence even when no code changes. Only then mark `ready_for_user` and assemble a concise evaluation packet.
8. Record the user's evaluation and any issue tasks. Close/release settled workers. Update the next action before ending the coordinator turn.

For Orca worker follow-ups, process and acknowledge each delivered FIFO batch
before checking for the next one. Repeatedly reading an unacknowledged delivery
can hide later guidance behind the same first batch. A send receipt proves
enqueue only; do not infer that the worker read or adopted it. Put required
correction instructions directly in the next self-contained Dispatch when
reusing a settled worker, with its new lifecycle IDs.

While independent read-only plans run, the coordinator may perform independently verified, reversible preparation on immutable inputs or fresh isolated state. Record this explicitly; do not mutate candidate input artifacts, touch existing user progress, read a sibling answer on a worker's behalf, or claim both plans informed an action performed before submission. Read and evaluate both plans before the final verification checkpoint or user handoff. If the frozen brief promises a stricter serial order, follow it or record the deviation and its comparison limits; changing this workflow does not retroactively satisfy an earlier brief.

The planning comparison is deliberately a read-only proposal comparison, not an implementation benchmark. Re-evaluate model fit as actual tasks generate evidence.

On2026-10-23 the user asked Root to use more of the available Grok capacity
through qualified parallel tasks. Launch independent useful work together,
with explicit inputs, ownership and observable acceptance; keep the equal
Claude/Grok comparison and Root verification. Reported remaining provider
capacity is scheduling context, not a measured cost or reason to create
unnecessary work. Keep live game actions under one owner, and release settled
workers when no immediate follow-up needs them.

## Scorecard

Score each dimension 0–4, with a brief evidence-based reason; total /20. A severe factual or ownership violation prevents selection regardless of total.

| Dimension | Evidence |
| --- | --- |
| Correctness and evidence | Verified claims, calibrated uncertainty, correct scope/version/source boundaries |
| Task coverage | Requested deliverables and acceptance criteria addressed without silent omissions |
| Verification design/results | Reproducible checks, appropriate negative cases, user-visible acceptance |
| Handoff clarity | Stateless agent can identify inputs, status, artifacts, blockers and next action |
| Git/state discipline | Correct branch/ownership, bounded diff, source rollback and external-state recovery |

Elapsed time and rework are reported alongside the score, not inferred from transcript size. If exact API cost/tokens or model version are unavailable, write `not observed`. Do not compare unrecorded costs or claim statistical superiority from one pair.

The user additionally authorizes Opus5.5with higher thinking effort when Astra
does not resolve a hard issue or produce useful progress (2026-10-21). Use that
as a bounded escalation, verify available provider/model/effort controls first,
and record the actual consultation/result separately from the frozen Claude/
Grok benchmark. The coordinator still personally verifies proposed changes.

## Critical issues and goal changes

The user requires prompt notification if a critical issue may force a goal change. Once supported by evidence, report the failed requirement, the verified facts, available options, the coordinator's recommendation and each option's effect on the agreed goal. Ask for the user's decision before changing scope; elapsed time or silence is not acceptance. Continue independent work that preserves the goal while waiting. Ordinary implementation defects that can be fixed within scope stay in the task board and do not require a fresh approval request.

Commit the critical-issue evidence and any resulting user decision. Do not silently reduce all-content coverage, replace Traditional Chinese story requirements with UI-only translation, or count admin shortcuts as normal solo progression.

## Task status

| Status | Meaning |
| --- | --- |
| `planned` | Defined; dependencies or prior phase have not cleared |
| `in_progress` | Assigned ownership and active attempt recorded |
| `candidate_submitted` | Worker supplied an answer/change; coordinator has not verified it |
| `self_verified` | Coordinator personally completed the stated checks on the current artifact |
| `ready_for_user` | Self-verification passed, limitations/rollback documented, evaluation packet available |
| `accepted` | User explicitly accepted the stated scope/version; record date/decision |
| `needs_fix` | A candidate or user review failed; link the issue and next attempt |
| `blocked` | Name the missing input and exact next action; do not call an uncertain result a pass |
| `deferred` | Explicitly outside the active milestone or moved by a recorded decision |

Task and phase acceptance are separate: mechanical internal tasks can be reviewed together at their phase gate, but each still requires coordinator verification. “Latest result” must not overwrite an older result's evidence or version.

## Git branch and checkpoint policy

- Baseline before this pass: `c6314bbd85caa01f54fdcc38d62168e101e2c5a4`. Current coordination branch: `ShemYu/reverse-the-Ragnarok-Online-to-play-by-myself`. It is not the default branch.
- Documentation-only reviews may share a checkout only while read-only or when file ownership is explicitly disjoint. All mutating implementation candidates get dedicated branches such as `task/T05-claude-a1` and `task/T05-grok-a1` from the same recorded commit.
- Create/manage Orca worktrees with the Orca CLI, loading its placement guide before doing so. Skip setup hooks for documentation-only work. Never manually repurpose another agent's active branch/worktree.
- Before edits, inspect status/HEAD; commit only owned paths. Before checkpointing, inspect the diff and staged path list, run applicable checks, and update evidence. Local commits are authorized; publishing/pushing and merging to the default branch are separate actions.
- Integrate a selected committed candidate onto the coordination branch with a traceable commit/cherry-pick, resolve conflicts explicitly, and reverify the integrated result. Retain the rejected candidate commit and review record for comparison.
- Suggested messages: `docs(P0): define Renewal milestone and verification workflow`, `task(T05): verify Traditional Chinese pilot`, `fix(T09): preserve quest variables during localization`.
- Record each checkpoint with task, parent/base commit, verification and external-state backup reference. Locate the current documentation checkpoint with `git log -1 --format='%h %s' -- AGENTS.md docs/project` instead of embedding a commit's own hash into its files.

## Rollback

For an already committed source checkpoint, inspect the branch/status and use `git revert <checkpoint-commit>` on the coordination branch. Revert dependent checkpoints in reverse dependency order and re-run relevant checks. Do not use destructive reset, force-push or deletion of unrelated work as the routine rollback method.

Git does **not** restore the installed app, application-support files, GRFs, MariaDB, saves or local evidence. Before a runtime mutation of existing progress/state, create a named app/database/settings backup, record app/server/client versions and input hashes, and prove restoration on isolated test state. A verified fresh installation with no prior state may be initialized without a nonexistent save backup; record that preflight and preserve the resulting trial state. T04 must still demonstrate backup/restore using actual test progress. If isolation is unavailable, report that limitation before touching the user's save. A backup's existence alone is not a successful restore test.

Keep assets/installers/databases/raw logs/screenshots local and ignored; commit redacted Markdown results. Do not broaden `.gitignore` or source-publication rules just to include evidence files.

## Minimal handoff record

Each task-linked review must record:

- Task/phase ID; date; owner and next owner/action.
- Baseline, candidate and integrated commit; app/server/client versions and input hashes where applicable.
- Identical brief, Claude/Grok outputs or durable references, observed provider/model information, benchmark type and score rationale.
- Coordinator's own commands/actions and actual results; failures, fixes, skipped checks and limitations.
- User evaluation steps, expected visible behaviour, known gaps, source rollback and external backup/restore reference.
- Current status, elapsed effort if observed, and the condition needed to advance.

## Verification for documentation changes

The coordinator reviews the full diff, checks local Markdown paths/anchors, checks task/dependency/status consistency and historical labels, runs `git diff --check`, and runs `python3 tools/check_public_tree.py` after staging the intended files. These checks establish documentation/source-tree hygiene, not runtime feasibility. Game tests are not required for prose-only changes; no app, generator or installer is run during P0.
