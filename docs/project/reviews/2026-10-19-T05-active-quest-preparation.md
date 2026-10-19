# T05 — active quest source preparation

2026-10-19 JST; root source review from coordination base8864fb5. This is supplementary preparation for the open parent [T05](2026-10-18-T05.md), not a new provider comparison, rendered-language result or task acceptance. No game input, save/settings change, stock Lua execution or network change occurred.

Root personally checked the pinned client775f8847 source and packaged Online.js SHA80f4371cc8da2bb54432e46e7e34dfaf7acc56444b28c6fbc6a99c6ba22933ea. The recorded20221005 packet profile selects modern Quest at the20180307 common UI gate, not QuestV1. UIVersionManager chooses the latest applicable common/mode date; the modern factory selects QuestHelper/QuestWindow and renewLayout. This is source-profile selection, not inspection of a newly running page.

Server packets provide quest IDs, activity/time and hunt state, including hunt mobName. Engine/MapEngine/Quest.js25–69 obtains displayed title/summary/description through DB.getQuestInfo. With loadLua enabled, DBManager693–705 loads the first successful System/OngoingQuestInfoList alias, then SystemEN/OngoingQuests.lub, then ordered customQuestInfo entries; later records can replace the same ID. Aliases4290–4302 try suffixes empty/_true/_sak/_Sakray, each .lub then .lua. With loadLua disabled, questid2display.txt is a separate route. These paths do not establish which resource currently wins.

The actual packaged loadQuestInfo312129–312230 and source5100–5240 explicitly decode Title/Summary/Description with userCharpage, Big5 in the recorded langtype4 profile. IconName/NpcSpr/NpcNavi use the decoder default. Rewards/positions remain separate fields. A caught Lua error can still lead to onEnd(true), so completion alone is not proof of readable quest data. English defaults and English UI chrome remain separate localization gaps. Prior zero-replacement decoding of11508 raw strings proves neither correct ID coverage nor rendered Chinese.

QuestCommon418–443 puts activity1 in Active unless a future end time first selects Cooldown. Titles/summaries clip at30 UTF16 units; details require their own observation. Row-body click477–485 displays QuestHelper; Toggle674–681 sends an ACTIVE_QUEST packet. QuestHelperCommon211–233 processes title/description markup and separately renders packet-origin hunt names. Root inspected these exact boundaries and the packet structure/registration; no live packet or row was inferred.

The later end-user check is ordinary Alt+U, capture an already-present Active row's title/summary, single-click its body and inspect full details without Toggle, Show Quest/preferences, display controls or item/NAVI links. If Active is empty, record the unmet precondition and keep the gate open. Do not create a quest or restore older progress merely to manufacture this sample. Prior empty Active and completed21001/21008 remain historical observations.

Private root receipt `.tools/renewal/t05-navigation-pair-1/quest-ui-root-source-check-1.json`,1431bytes/SHA4852416b3f77e8c2cb765ec74301c8aa8254c7013e5cbe57a7aeeafa47807cc3, records the five checked source hashes and packaged identity. Supplementary source note SHAc41eb1c37533b54fab02670bdcbc31e321d17164f1ff03dd2676bca610c13de5 was personally read and its material claims checked against primary source. Source line numbers count LF boundaries.

Next owner root: finish the current navigation pair/serial qualification, then choose the ordinary quest sample when the game is available. Actual active-quest rendering, full Chinese UI/story and the all-content milestone remain open; no critical goal-changing issue is established.

## Saved-state precondition and ordinary continuation source check

After T05.008, root personally reads the quest slice of the latest normal-page logout receipt, SHA91e5b7c3bbe6cfaa00810d19096cf8469ffc859a017af7cc8fe34c90cc0acf9c. Only21001/21008 are present, both state2/time0/counts0. The pinned server enum defines state2 as completed; no active sample is established and4269/7471/7472/7473 are absent. No new client observation or quest acceptance follows.

Root also checks the primary academy script and quest/client-state boundaries behind supplementary private note active-quest-next-source-1.md,8600bytes/SHAe8f851f38c454967597210475bb9bbe9ee9375bec1e2e9806409f18184487a1c. Pinned academy.txt,508418bytes/SHAb2ab5f7de7e1c36e4f58b8447a80d4cb089e8bf45aeade59953c6a70004f27fd, declares Carocc at izlude198,213. For a novice below level15 with the stated absent quest gates, the ordinary menu “I don't know what to do.” reaches setquest7472 at line604. The pinned untimed DB declaration, quest_add and client Active predicate predict an active row if the effective native prerequisites hold. Hun at122,207 subsequently completes7472, grants200 base EXP and starts7473, so talking to him would consume this particular sample.

This is a possible later normal story continuation, **not authorization inferred from an empty test fixture to manufacture quest state**. No travel, dialogue, quest, reward, save/settings or runtime mutation occurs in this source check. A later root-owned ordinary-story check must preserve the newest progress, establish actual novice/level/NPC/menu conditions, inspect Chinese title/summary/details before Hun, and compare the resulting saved state. Installed script/DB identity, packet delivery, winning client resource, Chinese rendering and full story remain unverified. Current T06 source work proceeds independently; the game stays at normal-page character selection.


## Ordinary Active-tab precondition inspection

After Navigation checkpoint e747286, root re-enters the same ordinary
api.html?app=ONLINE character at prt_fild08 362,212/base3/job7/HP51/SP13.
Actual Alt+U opens the modern Quest window. Root captures and visually inspects
the selected **ACTIVE** tab: it is empty. Visible chrome remains English:
Quest Information, ACTIVE, RECOMMENDED, PENDING, COOLDOWN and Show Quest.
This identifies a UI language gap but supplies no active title/summary/details
sample and does not identify the effective quest-resource winner.

Root does not use Show Quest, activity toggles, quest/item/navigation links,
travel, NPC dialogue, rewards or saved archive restoration. Alt+U closes the
Quest window. The first Option click is covered by the Navigation panel:
actual Option bounds170.296875,112,32,32 lie under Navigation120,120,390,430.
No Option menu appears, and the attempted hidden character-selection click
times out without a click. A scoped role-button lookup also returns0; its
subsequent attempted click times out without action. Root inspects actual
shadow DOM, finds ui-button.close, closes only Navigation through
#Navigation .titlebar .close, then uses the unobstructed Option menu and normal
character-selection logout. These are UI-control observations, not game defects.

Latest complete six-table receipt
8e910da48dd4b2b428feb7a12f3512bd6e499c5cf9469b5e42a07c0e9c927f46
changes only char.last_login from the final Navigation receipt b71b67ed… .
All other rows/schema/order/bytes/NULL remain exact; online0. The quest table
still contains only21001/21008, both state2, and no7472. The Active text sample
precondition is therefore **unmet**, not passed. Finite console capture shows
32warnings/0errors. Same app96858/start identity, asset97329/direct parent/
executable, Ready/all five listeners, all three clean1094file195dir runtime
manifests and21protected/3absences remain exact. Aliases/prior overlays stay ON;
internet/audio/mute/IME/window preferences are unchanged. The ordinary page
remains safely at character selection with the game server running.

Private t05-active-quest-live-1/root-Active-empty-qualified-1.json SHA
c17172f5ed3a387fa27d89b633e8ecc9446b90991af261f923604442c515e4a6;
Active-empty-1.jpg SHA3d853249808e0a5087ffac2a685a1a63c944eecfcab0fc0293dd718dbac9a891.
All files0600/directory0700. This root preparation is not a new Claude/Grok
comparison or task/user acceptance. The next bounded comparison should assess
normal beginner-story continuation and actual quest-resource attribution before
any runtime mutation or speculative localization repair. Preserve the newest
save, establish actual prerequisites and stop before consuming any chosen active
sample. Full parent T05 and the complete milestone remain open.
