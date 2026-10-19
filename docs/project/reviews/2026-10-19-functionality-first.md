# Functionality first; localization remains in the goal

Date: 2026-10-19 JST. Owner: root Codex. The user twice clarified that
translation may be a large job and gameplay functionality should take priority.
This is an execution-order decision, not a provider result or acceptance.

Next work covers maps, monsters, combat, jobs, items, quest progression and
persistence across the Modern/Renewal game. Remaining Chinese UI/input checks
and bulk story translation follow functional verification/repairs. T05 stays
open with deferred work and cannot block T06/T07 or functional T10 children.
Final Chinese coverage and user acceptance remain required. Party-only
activities/adaptations stay in the later phase already recorded separately.

Reuse comes before new translation: current Taiwan client tables, existing
translation dictionaries and enabled overlays remain available. T06 must
separate client text from server story, deduplicate units, identify usable
resources and measure uncovered text. Raw quoted-occurrence counts are not
unique translatable strings or a translation effort estimate. Future resource
reuse needs version/meaning/provenance checks; no uninspected web resource is
installed or declared complete by this decision.

## Deferred input preparation and cleanup

After resume, native Chrome binding succeeds; a later window action reports
noWindowsAvailable, and one fresh rebind succeeds. Native access is therefore
intermittent, rather than permanently unavailable or fixed. Root uses one
isolated loopback scratch page with no game imports, forms, chat or network
requests from its page. The browser-tab ctrl+space path reports Meta/Space
events; it does not qualify a real source switch. Native Control_L+space
changes the selected source, but the later scratch key produces trusted ASCII
insertText without composition events. Focus/input routing remains unproven;
no real Zhuyin preedit/candidate/commit/cancel or game IME PASS follows.

The native source switch initially targets the game window before root
explicitly selects the scratch tab. No game chat is typed or sent; no NPC,
movement, reward, installed-state or SQL action is performed for this probe.
Root stops rather than expanding it after the priority change. Scratch draft
and log are cleared, the tab is closed, and the owned server session is
interrupted/reaped with exit130 and its loopback listener absent. Root's narrow
read confirms the original ABC selected input source restored. No preference
file is written. Private root-cleanup-and-deferral-1.json SHA
827edfb0e1a03db2c3605d7208c750de4fdc0a03dbefc2b4f4ea968a0e2450a3
binds the fixture/events/cleanup evidence under ignored0700/0600
.tools/renewal/t05-ime-native-capability-1/.

The read-only resumed game observation shows newer state at Izlude136,181,
base3/job7 with Chinese Quest/active7472 visible and additional earlier loot
text. This is not the old197,212handoff or a new complete SQL comparison.
App58655/asset67357still own the loopback3339/3338listeners. Newer progress is
preserved; O/ff3ec892… remain historical backup/save evidence and must not be
restored over it. Take fresh earned-state/backup admission before another
installed-state mutation. The ordinary game tab is retained running.

## Next owner and verification

Root proceeds to whole cached-map core-resource evidence and then functional
gaps/end-user scenarios. Each bounded task still receives actual independent
Claude/Grok work and root verification. The first content task must account
for every cached root, including unconfigured ones, and distinguish observed
resource chains from rendered/playable maps. No remaining translation task is
marked passed or accepted because of this deferral.

## Orca sleeping workspaces are separate from active workers

Root freshly checks the run, scoped worktree PS and both retained workers.
The run has63resources:61released and two user-retained. Both retained Grok
attempts are completed/settled, with live terminals independently observed;
their ownership is user_owned/user_takeover. Their stale fleet projection is
not used as proof of exit. No automatic close/release is authorized for them.

The repo has47worktrees, all with in-progress badges:25have no PTY and22have
attached live PTYs. PS classifies root as working and two Grok agents as done;
the other19PTYs lack agent classification. These observations establish no
CPU/token/memory cost or unused-shell claim. Saved checkouts/badges therefore
must not be counted as running AI workers. Completed agent sessions are not
needed for repair when source commits/reports are preserved; current read-only
plan workers can share this checkout without creating more child checkouts.

Private root audit summary SHA
6c51e9d5ea6534eb6eaa418678c9117b8adffb0849dc5c5811e133ca541cee7e
binds the raw read-only observations under
.tools/renewal/orca-lifecycle-audit-20261019-1/. No terminal/worktree was sent
input, launched, closed, deleted or changed by this audit.

Root checks257local Markdown paths/anchors across12changed documents, valid
new profile JSON, unchanged prior frozen T05.012 task/profile pins, reviewed
public diff, git diff --check and public-tree guard before the local checkpoint.
