# Chapter1 external source — Astra lead, root-checked preparation

2026-10-20; root. Internal Astra advisory under the user's hard-question
authorization; **no actual Claude/Grok comparison or implementation PASS**.
This preparation follows the finite [T07.005 finding](2026-10-20-T07.005.md).

Root resolves the author's repository to immutable revision
769bdf7f54473a592a800f4fee5366c620cf6cd0, enumerates its complete140-entry tree,
and independently fetches/hash-checks the material text without executing it.

| Source | Bytes | SHA256 |
| --- | ---: | --- |
| [Chapter1 script](https://raw.githubusercontent.com/hayakawakaki/rathena-script-collection/769bdf7f54473a592a800f4fee5366c620cf6cd0/Episode%20CH%201/CH1.c) | 634359 | 8ac8c8de78e54e574450f78e49d423ad8d1c494e27378db71d92ee93b033ee55 |
| [Shared helpers](https://raw.githubusercontent.com/hayakawakaki/rathena-script-collection/769bdf7f54473a592a800f4fee5366c620cf6cd0/Function.c) | 8251 | 81de538fb465b56e19b285ea4d2e117f2891622d2e8bbd5da3e323db016e559c |
| [Quest records](https://raw.githubusercontent.com/hayakawakaki/rathena-script-collection/769bdf7f54473a592a800f4fee5366c620cf6cd0/Episode%20CH%201/DB/quest.yml) | 11571 | 631ab32562ec6644cec940faac8cd3347a50a0b1846d60376cd9c6425f959deb |

Root reads the first entry/handoff: LF9and97match both official starter
coordinates. LF10–16give the level200gate; LF58starts quest18368, LF60–64allows
postponement, and LF72warps to ygg_edge255,240. Messenger253,246at LF99–114
completes18368and starts18369. Repeat entry has distinct destination branches.
This is a concrete stateful candidate, unlike generic world-sync placement.

Root also fetches old0693b8c script.cpp804967bytes/SHA
b6f4e24abdb50758b8e8bac2ab293c2a1bc8ef9a2d49672e03e7b80d065e7a80
and script_constants.hpp408599bytes/SHA
3aaa58220eba966e7cc59f9921ad70421da593cb021cbf44b2cb2e9bccbbf641.
It independently checks registrations for close3/navigation/quest/cutin/warp/
strnpcinfo and the two NPC classes/quest markers. This supplies a static
compatibility lead, not compiled or served support. The full script has custom
behavior and later helpers; it cannot be installed wholesale on this evidence.

The [README](https://raw.githubusercontent.com/hayakawakaki/rathena-script-collection/769bdf7f54473a592a800f4fee5366c620cf6cd0/README.md)
warns about mismatches and restricts redistribution. No author code is copied
into the public Git tree. Private text/metadata receipts remain in
.tools/renewal/t07-chapter1-external-lead-root-1 at0700/0600. Intended local
integration, attribution and any later publication boundary require explicit
treatment in the next plan; no legal-permission conclusion is inferred here.

Next: [T07.006 paired source/integration proposal](../tasks/T07.006.md).
Check entry/defer/re-entry/Messenger declarations, effective quest/import
collisions, client resources and regional differences. Preserve full chapter
as an outstanding integration obligation. No need to change the full-game goal
is established; no new runtime, source patch or party-rule adaptation occurs.
