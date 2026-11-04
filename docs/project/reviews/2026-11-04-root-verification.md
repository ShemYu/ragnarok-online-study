# Expert-action candidates — Root verification checkpoint

Date: 2026-11-04. Coordinator: Root. Run `run_7cfbb105cb59`.
Starting coordination revision: `39c4b66038afbebea225f113ed4f8c135a4af67f`.
All six initial supplier candidates are submitted on separate task branches
from `a06f103`. No candidate is integrated at this checkpoint. Repairs and
final paired selection remain open. The full seven-task goal is active.

## Candidate state and next owner

| Task | Claude candidate | Grok candidate | Root disposition / next action |
| --- | --- | --- | --- |
| T00.006 | Initial `c9dbef6`, cleanup repair `5df05ffaf8a2e8e122ac7ddf5cf93ee87cffcdb2` | `6bf83ba92e269bfb73f4277f0df206bf61df29bf` | Both expose stale private admission. Claude's cleanup repair is submitted, awaiting Root. Verify authored mutation success, signals and failure cleanup before selecting. No full private pass claimed. |
| T06.005.001 | Initial `a61c086`, repaired `b4a263f`, annotation follow-up `2110b15a342528cbebfc0eba78446b6a5ec41cc8` | Initial `361653e`, consistency follow-up `21ad124aab6a19a68818f231131edc8fa7abd58a` | Root verified the initial pair and Claude's first repair. Final annotation/output/provenance repairs need checks before integration. All 82 functional gaps remain open. |
| T10.010.003 | `06d6f36633881f6e765ef559063da0936b059344` | `25a25737d70b626df785b011acb64e4c6ead56a2` | Root reproduces Claude's fresh full source and host differential. Real build is held for recipe repairs and paired review; Grok source/recipe verification is next. |

Known current repair dispatches: T00 Claude `ctx_5ac1d2290afe`, T00 Grok
`ctx_d9434dd1e218`, native Claude `ctx_954c6772a7ee`. Coverage Claude's
`ctx_9a984d3c72e5` has submitted its annotation follow-up. Grok's consistency
follow-up is `ctx_9966801637fc`; additional output/provenance corrections
were sent as `msg_4f37194a2026`. Receipts establish enqueue, not adoption.
Use the next wake's exact check and current dispatch state before follow-up
or release. Reused workers share the same six worktrees; do not release a
terminal that still owns a repair. Release settled chats once no immediate
follow-up requires them.

## Coverage: actual Root checks and defects

Root personally runs Claude's six authored tests, pinned-input byte
reproduction and Ruff 0.16.9. All pass on `a61c086`, but five additional
in-memory controls expose standalone validation gaps: an `exercised` claim
with `not_observed` evidence, cache/raw-quest counts substituted for full-map
or story-chain denominators, an inflated spawn-class count, and a deleted
root hidden by stale reconciliation sidecars. Root also checks the actual
spawn lexer: `not_static` means whitespace and comments; it is not a warp
inventory. Claude's initial warp annotation is wrong.

On `b4a263f`, Root reruns seven tests and byte reproduction and personally
confirms all five controls now refuse. The ledger hash is
`fea058b4b66e71aa8d7a0b4eee6c6613ced639d5bcf4d54ddabbb8fe96a0bb94`.
The latest annotation-only `2110b15` remains pending Root's final check.
Standalone structure/internal consistency does not authenticate inputs;
pinned regeneration and byte equality are a separate gate.

For Grok `361653e`, Root runs all eight tests with explicit canonical input
and ResourceWarning as an error, including byte-identical canonical rebuild,
and Ruff. All pass. Root then exercises the actual output writer on owned
synthetic paths: a dangling `<output>.tmp` symlink creates its protected
target, and a hardlinked temporary file changes its protected target.
No real canonical input is a target. This demonstrates a write-isolation
defect requiring exclusive fresh temporary files. Additional source review
finds five unpinned documentary dependencies and annotations that lose the
producer's `not_counts_of` negation. Corrections were requested. The later
`21ad124` consistency changes do not yet establish those fixes.

Root independently reads the canonical profile and qualified gap join,
without either generator, and recomputes:

- 82 exact descriptor tuples in original order, 79 configured and three
  cache-only. Both initial public ledgers preserve every tuple, including
  non-dense root/cache ordinals.
- 26 RSW, 21 GND and 26 GAT name occurrences: 73 total on 26 distinct roots;
  56 roots without any counterpart. Names do not prove bodies/rendering.
- Before/after hashes and stat identities of all eleven canonical metadata
  inputs remain unchanged during Root's tests and controls.

Full content/story denominators, effective loading and actual party gates
remain unknown. No resource gap closes and no user acceptance is inferred.

## Native preparation passes; runtime recipe needs repair

Root uses a new empty cache and fetches the pinned public app and rAthena
commits, including the app's vendor-pin fork URL. Fresh fetch takes 7.93 s;
preparation 8.16 s; re-verification 0.47 s. The result is 5049 to 5121 files,
72 added, 29 modified, none removed, including the app's build-context
Dockerfile. Full tree SHA-256:
`b64e850bd0d0fddbcda1df619d9a2544f27e286301a0e7d69b5f827ea3d40f32`.
All nine existing source pins match. No old prepared bodies or ignored
preparation wrapper is used as a reconstruction input.

The exact patch/differential check takes 7.23 s: 133 cases, 63 probes, zero
failures, all nine causal mutants caught. Root also runs 16 preparation tests,
11 fake-Engine recipe tests and pinned Ruff; all pass. These establish source
reconstruction and their stated host/fake contracts only.

Root and an auxiliary source reviewer find real recipe defects despite those
passes. Root reproduces the first three on private host controls and inspects
the affected source paths:

1. Final `PASS` logging changes `steps.log` after hashing it, so the produced
   export fails its own validator.
2. `ln -sfn` into the stock `/rathena` directory nests a link rather than
   replacing that directory; the pinned final image excludes crash-fixture
   source. The fixture hardcodes `/rathena` and `/symbols`, with no ROOT option.
3. A zero-memory plan is accepted and emits `HostConfig.Memory = 0`. This
   synthetic plan has an invalid all-zero image ID and is never executed.
4. The guest reads parent cgroup leaves, does not assert its own effective
   limits before APK/build work, and uses `Binds` semantics that may create a
   missing source. Require own-ID/cgroup2/read-only mount checks and positive
   limits before work; do not treat an echoed request as enforcement.
5. Ambiguous create, SIGTERM and absolute request/lifecycle deadlines need
   owned cleanup qualification. Export/import checks also need declared
   UID/GID verification. Closed source verification must reject directory
   symlinks rather than silently ignoring them.

Repair requests retain the original source pins and app behavior. Equal
semantic acceptance updates go to both native suppliers. Immutable dependency
package inputs, current headroom/enforcement, full compile/link/loader/start,
ordinary-item regression and actual image import remain open. No real Engine
write, APK install, compiler container, binary or image build is performed by
these Root checks.

## Historical private admission and safe-test scope

Root personally hashes the historical constructor manifest:
563422 bytes, SHA-256
`9980ac604d77f651802fb788f5b21f57198e6063b8df4b982b670ddd8edd541c`.
Its referenced ledger profile still matches 4855 bytes and SHA-256
`9ad903297104cd6f9a03d74196d5db7a4091ee07da4d2b73b4b4f61027b2140d`.
Root compares actual identities: inode, mtime and ctime differ. Byte equality
does not restore this admission. Recreation is supported by the auxiliary
trace; checkout causation is not proven.

Claude reports full-suite 48/56 and a labeled 48/48 subset; Grok reports a
preflight `pin_mismatch` and a failed worker outcome. Root has not yet run
either isolation candidate. None is a full private-suite or actual 273-job
pass. Source review confirms an additional Claude cleanup gap: a failure
after detached spawn can bypass owned cleanup and the protected after-snapshot.
The worker submits `5df05ff` with an outer lifecycle finally and three injected
post-spawn failure controls. It reports 13 public passes/two private skips,
15 private runner checks and unchanged full-suite 48/56. These remain worker
claims pending Root's execution; they do not change the stale admission result.

Preserve historical manifest/profile/baseline/receipts. The old ignored
producer pins an obsolete parent and already-used output path; do not rerun
or edit it as a shortcut. A future current-corpus binding needs a separately
versioned metadata derivation and independent audit. Track that inventory
admission gap under T06; it is not needed to weaken T00's frozen acceptance.
T00 explicitly permits documented limits when the full private suite cannot
run. Root will qualify meaningful authored mutation success, after-mutation
SIGINT/SIGTERM, post-spawn failure cleanup and explicit stale-private refusal.
Subset results remain labeled. No assertion or production admission is relaxed.

## Astra consultation informs the later native save gate

Root uses the user-authorized Astra model for a read-only hard-path review.
Root rebinds all eleven discussed source bodies to the fresh public
reconstruction above: every body equals the historical prepared counterpart.
Root inspects the event queue, quest-triggered save, status/inventory packet
separation and char-server ACK paths. These are source facts, not native tests:

- Base/job level-up NPC events queue while Maysel's script is attached.
  Synchronous status/equipment/unequip scripts are separate paths; native
  level-up/capacity testing still must inspect actual configured scripts.
- `getexp` applies rates/bonuses/caps and may not grant the requested raw
  amount. App-side overrides show 100% base/job/quest rates, but the effective
  native merge and other settings remain unproved.
- Quest replacement may save D before EXP/items. Quest, character status
  and inventory use separate packets and SQL statement sequences, without
  a transaction spanning the reward. Final-save ACK is not proof every SQL
  write succeeded. Native acceptance requires complete stored-value readback.
- A character-conditional breakpoint before the quest-save ACK could expose
  a meaningful isolated interruption boundary, but only after debugger,
  binary, database and state isolation qualify. A timed kill after dialogue
  cannot establish that boundary. Keep any unavailable boundary explicitly
  unproved, as T10.010.006 permits. No new marker/replay/transaction system is
  selected; uncertain reward requires manual review.

T10.010.004–007 still need real native and normal-game verification. The
agreed goal is unchanged; these are bounded repair/qualification gaps.

## Durable private evidence

All paths below are relative to
`.tools/renewal/seven-task-execution-2026-11-04/` and remain ignored. Commands,
actual exits/timings and input-preservation snapshots are retained there.

| Artifact | SHA-256 |
| --- | --- |
| `coverage-claude-root-1/RESULT_ROOT.json` | `ca48bf36629791e8aa20adca6973a2ba19ad42b40ce51fb49c7aaa9fc5bf4543` |
| `coverage-pair-root-1/RESULT_ROOT.json` | `0d5b7989864791b318362ebf722915600438652c6a253ab5cb2c6296bc6e516b` |
| `native-claude-root-1/RESULT_ROOT.json` | `ff4588aac590f323293c8c8e401ccb4a4a816562ed044be7738d0b7e8de136a4` |
| `native-recipe-controls-root-1/RESULT_ROOT.json` | `88d26ac6ea96daa88ef73d013bc8c169f671712ae9fc5604ad2f803cfa62a3ee` |
| `reward-source-root-1/BINDING_ROOT.json` | `2deb855ec8ffb033a517fc86735a81fdab75da4ca93aecdd02f29481383b6680` |
| `reward-source-root-1/IDENTITY_ROOT.json` | `8fcefd38f75f405f22b69b1917a38ec78abef8f0824ed1b048d3b8013caaa5b0` |

## Subsequent integrated tasks and remaining native repairs

The preceding sections describe checkpoint `232eb9fa`, before integration.
Root subsequently completes [T06.005.001](2026-11-04-T06.005.001-root.md) and
[T00.006](2026-11-04-T00.006-root.md). Both selected implementations are
rechecked after integration; all four settled coverage/T00 terminals are
released with transcript archives. Two of seven audit tasks are self-verified.

Native Grok submits `10f959c0`. Root runs 13 preparation and six planner tests
successfully. Its header's `python3 -I -m unittest <path>` fails to import
`tools`; direct explicit-file invocation passes. Actual `execute` exits 2
unconditionally: this candidate is a JSON planner, not the frozen brief's
executable lifecycle. Source review also finds unrelated manifest/staging
admission and root-link/ignored-overlay closure weaknesses. No full Grok
reconstruction or native build is claimed by Root. The candidate is not
selected; its settled terminal is released, preserving Git and transcript.

Claude's executable repair `1b0508c8` improves cgroup ordering, final log/hash
sealing, mount semantics, request bounds, ownership checks and dependency
inputs. Root personally tests its guest lock helper against an authored
preinstalled-bash fixture: it emits an added-only lock which its own host
parser refuses (`apk lock lacks ['bash']`). Source confirms build validation
also requires an incompatible full-versus-added lock. Root's fake Engine
control creates an object then raises `Cancelled` during create: recovery
does not run and no owned ID is returned. Source confirms import-check also
lacks SIGTERM handling. A narrower output-root symlink check resolves before
testing the link. No real Engine requests occur in these controls.

Repair dispatch `ctx_5f4bd33b6298` / task `task_65756ef449b9` owns these
remaining fixes. The extra root-link correction is queued as
`msg_f12d874d58f1`. This is continued work in the same Claude native workspace.
No actual compiler, package installation or image import is admitted yet.

That dispatch submits `7e5135b0b7e63db64fc433272c735e3663cd770c` with base/delta
dependency separation, cancellation-safe create/import and output-root link
checks. The worker reports 41 recipe/20 preparation tests. These are candidate
claims pending Root's next check, not an executed guest or integrated task.

| Additional private evidence under the same execution directory | SHA-256 |
| --- | --- |
| `native-repair-controls-root-2/RESULT_ROOT.json` | `847fc4421407862f354a9515e3318e01c7c39df6bdd482f80d3ca11669a863c1` |
| `native-grok-root-2/RESULT_ROOT.json` | `ace80d61f7fc198d6ad30554ed66d05c76b55a97787ef94bc34976d7b7cf6b7d` |

Next owner: suppliers repair their owned candidates; Root verifies the latest
revisions, records the final paired score/selection, integrates and commits
each qualified child before advancing. Model versions remain provider/session
reports where not independently observable; API tokens/cost are unobserved.
No initial candidate's worker PASS substitutes for Root or user acceptance.
