# User Assassin play account and page

The user explicitly requests an account/page to try the game, then chooses
the Assassin job line. This steers ongoing work; it does not replace the full
Renewal milestone or count as earned progression. Root creates a separate
local account through the app's supported account command and creates two
characters through the ordinary UI. Existing novice progress is preserved.

The new test account has a level99/job50 Assassin and a level200/job50 Shadow
Cross. The latter's class4254 is confirmed in the current client source.
Only the two new offline characters and new account are preset via supported
SQL-write controls; the app makes its automatic before-SQL backup. The test
account has local GM permissions for skills/items/travel. No original character
or installed mod/config is changed. Credentials and full backup/evidence paths
remain private; no secret is committed.

Root personally logs into both characters and sees the Yggdrasil map at73,117
with Chinese UI. Ordinary server commands grant class skills, starter equipment
and100white/50blue potions each. Saved SQL shows17/52learned skills, both exact
jobs/levels and both characters offline at the requested map/position. Gear is
in their bags: double-click it to equip. The exploratory autoequip command is
unknown and has no effect; no equipment success is invented.

Root uses normal character-select to save each, then verifies the Assassin's
settled re-entry, character identity, connection and movement readiness. An
earlier0.5s character-screen assertion is too early and fails; later offline SQL
and settled re-entry supply the acceptance, without hiding that failed snapshot.
The old novice's complete character row matches its pre-preset bytes.

The new Orca profile is labelled **RO personal play**. Its page is handed to the
user logged into the classic Assassin. Use the Inventory and SkillTree toolbar
buttons; Escape/first option returns to character selection for Shadow Cross.
Root must stop inputs to this page after handoff and keep subsequent checks
independent. Do not stop/restart normal services or install/rebuild global mods
under the user's active play session without coordinating with them.

Supported account creation takes9.668s; supported preset write8.649s. These
intentionally restart local game services and produce new service start metadata.
The previous T10.009 trial's original-world/fresh-witness comparisons describe
the state before this separate user-requested action; do not reuse their start
reference for a new actor. Existing original containers/native service remain.
Any later operational trial needs a fresh qualified reference.

Private USER_PLAY_RESULT_ROOT.json SHA
05c2e5ae3996a57facdc693fe24053953b6db2fa4e4689b92e0916032e9ab676
is recorded after Root checks. The synthetic account is for user evaluation,
not full-content, normal leveling, story or first-milestone acceptance.

## Personal play page restored after the earlier page disappeared

Root's later tab inventory no longer contains the handed-off personal page.
A listed Default page also refuses a read-only snapshot as no longer available;
the repeated inventory still lists it, so Root does not infer or force its
closure. Under the user's existing account/page request, Root opens a fresh
page in the same RO personal play profile without restarting services or
presetting/restoring accounts, characters or saves, or changing installed files.

The first password fill/Enter attempt receives an invalid-credentials dialog.
Root dismisses it and uses the previously proven focus/select/ordinary text
insertion path. Private equality checks confirm both input values before
submission. Login succeeds; Root sees both character names and the selected
level99Assassin. Ordinary Enter reaches the saved game. This demonstrates
recovery with text insertion; it does not establish why the earlier fill
failed or a general input defect.

Root personally checks the rendered character/map/Chinese UI and the live
ShemAssassin level99/job50 status, full12077HP/665SP, at69,124. No movement,
gear grant, SQL write or service action is sent during this restoration.
The new page is handed to the user and Root stops its inputs. The older
73,117 setup is a historical checkpoint, not the current saved position.

Private t10-user-assassin-reopen-root-1/READY_SNAPSHOT.json5288B/SHA
231a5591b57f2347140089a999fa592bc37acd2b26ba0f74c502a37c137654f7
and READY.png2362635B/SHA
01bed87619d27c6268677f9808009e938b8e1f6b7c6bc7f3b5e93474ff9f73e4
preserve this check. Page/profile IDs and credentials stay private. The
personal play ownership and no-restart boundary still apply.

## User finishes testing and the personal page is confirmed closed

The user explicitly says testing is finished and asks to close the game.
Root first sees ShemAssassin99/50at74,118, full12077HP/665SP. Before a logout
input, the page becomes unavailable. A fresh authoritative tab inventory
confirms that both the target page and every page in RO personal play are
absent. Root sends no logout, movement, account/preset, service or other-tab
close action and does not reopen the game. Do not claim a normal logout/save
was verified here; actual saved/offline state remains a later preflight.

Private user-assassin-play-close-root-1/TAB_LIST_ROOT.json1233B/SHA
51965005a9e4e9f204d5f9e17edb57fa54c03d9faf4c167e98230b276d92d936.
The active-play window has ended; any next installation still requires its
current-state/offline/backup checks. No formal full-content acceptance is
implied by finished testing.

## Current offline saves are verified after the test

Root refreshes the tab list: the personal profile remains absent. Supported
authenticated app reads bind the normal data root, host/local mode, Renewal,
4096MiB setting, current settings/mod list and stack status. Six read-only
Engine GETs verify the census and all five original running service IDs,
including the DB volume mount. Current supervisor and runtime VERSION pins
match the qualified copies. No personal page is reopened.

Five supported supervisor SQL reads, without --write, return naturally with
zero status. Full character, quest, inventory and skill rows are preserved
privately; small table counts are checked before the latter full reads. All
three characters are offline. The original novice remains level2/job3at
Izlude24,98. ShemAssassin remains99/50atfruit74,118, matching the last observed
page. ShemShadow remains200/50atfruit76,120. This verifies persisted current
state, not that a normal logout input was sent. There is no database write,
restore, service restart or backup in this step.

Private idle-world-baseline-root-1/BASELINE_ROOT.json4930B/SHA
f7caa801948edb0d37f8ae7a3b68125a519d7d91c1c93e1594fd598ddc64a78e
joins the full private outputs and source queries. Next take and inspect a
fresh whole-world backup before any supported VM/service change. User test
completion still does not establish full-game/content acceptance.
