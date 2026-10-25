# Completed work and historical records

Archived: 2026-10-25 JST, from coordination checkpoint `348ea6c`.
The user requested a clean unfinished-work view before commit/push. No game
state, source implementation, task acceptance or scope changes in this cleanup.

## Completed task records

The old board contains 157 rows. The active board retains 37 unfinished rows
(23 `in_progress`, 14 `planned`). The other 120 records leave the active queue:

| Original disposition | Records | Meaning retained |
| --- | ---: | --- |
| `accepted` | 1 | T00 documentation baseline explicitly accepted |
| `ready_for_user` | 89 | Scoped verification complete; explicit user acceptance still pending |
| `self_verified` | 30 | Root verified the stated source/research/tool scope; later integration may remain open |

The parent ledger remains 4/14 qualified checkpoints: T00 accepted and
T01–T03 ready for user review. T04–T07 and T10 remain unfinished; T08/T09/T11–T13
are planned, with T11 deferred to the later phase. These counts do not measure
full-game content, translation or engineering effort.

## Latest completed maintenance

T00.001 documentation cleanup is `self_verified` for the source/documentation
scope: independent Claude/Grok reviews and Root's conservation, snapshot and
link checks. [Review, corrections and publication checks](reviews/2026-10-25-T00.001.md)
and [frozen brief](tasks/T00.001.md) record the process. This is an additional
maintenance record; the157/37/120counts above refer to the original ledger.
No game task or pending user acceptance is closed by this cleanup.

## Preserved snapshots

- [Original task ledger and acceptance contracts](HISTORY-2026-10-25-TASKS.md):
  all task rows and original evidence links, including finished source tasks.
- [Detailed verification/progress history](HISTORY-2026-10-25-STATUS.md):
  previous runtime checks, failures, repairs, backups and dated decisions.
- [Earlier ASCII supervision maps and model results](HISTORY-2026-10-25-PROJECT_MAP.md).

Each snapshot records its source commit and the original full-file hash/size.
Relative links remain valid because the files stay in the same directory.
Historical instructions and worker states are snapshots, not current actions.
Dated reviews, frozen briefs/profiles and all source commits are preserved.

Use [Status](STATUS.md), [unfinished tasks](TASKS.md) and the [remaining-work map](PROJECT_MAP.md)
for the current paused handoff. A documentation/commit/push request does not
resume game implementation. Preserve current saves and the existing local
backup; source publication does not include them.
