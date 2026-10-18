# T05 navigation compatibility preparation

Coordinator base:397dfd5. This is root verification/preparation for T05.006's open console gate, not a new implementation benchmark, adopted alias or playable-navigation PASS. The preceding [actual on→off→on comparison](2026-10-18-T05.006.md#enabled-state-restored-current-console-attribution-complete) reproduces the same six missing Korean-suffix navigation requests with and without the NPC package. The Chinese dialogue package remains enabled and the newest ordinary save is protected.

## Exact archive-derived copies verified

Root personally read the extraction helper's full source and relevant native grf.rs631–682 plus the already qualified archive_catalog.py descriptor/range/zlib pattern. The native reader derives body offset+46, applies encryption only for bits2/4 and inflates non-stored bodies. Each of the six pinned records has kind1, aligned==compressed and compressed!=decoded. This finite extraction uses the prior [direct catalog-range method](2026-10-18-T05-ui-preparation.md); it does not introduce a new archive parser or use the live resolver/cache.

Root freshly hash-checked the complete2043560050-byte data.grf SHA1c7d68f70714937abbd3741a6b3aea34a7ed9da63428941d5df453efacd1c0ad, complete catalog SHA09757b373fcc6534d0f5eeb9123daef9d0fdb955e91d818ff135f44cf88ae9ad and manifest SHA95d227e8b7b46163260d6488e76d4e2da4b59020a7641bcd3f718ba8d4005b84. The same regular no-follow archive descriptor supplied the full hash and six exact compressed reads; descriptor/path identities, sizes and modification/change times were unchanged before/after. Every row's raw ASCII filename/ordinal/range/flags/sizes matched the fixed preparation. Each independent bounded zlib decode reached EOF at exactly its declared size, with no unused/unconsumed input and no flush. These strict framing checks are verifier policy, not a claim that the native reader enforces the same output-size contract.

| Taiwan basename | Ordinal | Decoded bytes | Decoded SHA256 |
| --- | ---: | ---: | --- |
| navi_map_tw.lub |7581|67328|e7c8d566b5883df68d01830f0ce4ec385fc8ac084a1a8f6944bd517d89a046dc|
| navi_link_tw.lub |23356|594363|f6526637f8cfc8755b92fad9e496f7c97439715db34a6efd430dfb870b62ff10|
| navi_linkdistance_tw.lub |49391|1556072|26cea879a399a1362a02deecf0ef3b07c7d4bfcdf01938f08f98338e5f05c193|
| navi_mob_tw.lub |74384|396243|02aeb90a6df4af8f2e4fc8adf5a88f70b5ac1c48e32373a7cba57439a776c3c7|
| navi_npcdistance_tw.lub |89731|3840599|3e896b2ba29de46f40ab36e43917359b376612ef00b3b4c0e2eb0cc81cb95471|
| navi_npc_tw.lub |132777|1025994|7b760b652d8ce5a6353811aa57d433848b056f6bdc99a3ddbb585f88bb44b528|

The six compressed reads total1786500bytes; decoded copies total7480599bytes. Every copy begins with the observed header hex1b4c75615100010404040800. This identifies a candidate Lua5.1 bytecode profile, without proving execution/export/schema/codec compatibility. Root independently read back every published file and verified exact size/hash/mode0600, fresh directory0700 and exact six payloads plus one receipt. All payloads/receipts/helper code remain ignored and private. No app/mod/settings/save/network/audio/IME mutation occurred during this extraction; no Lua execution, alias or live request was performed.

Private stateless evidence:

- `.tools/renewal/t05-package-candidates/extract-six-navigation-1.py`, SHA0428c16108a79a79cd1ca94a30e04b7bcec121d12603e9629a4fa4e050a2eaf2. A supplementary source-review helper read the same bytes; root personally reviewed/executed it with assertions enabled.
- `.tools/renewal/t05-package-candidates/navigation-payload-preparation-1/extraction.json`, SHAbfbb2e04a7da52c5f72e6b1601320f65c9f7d1a53091a804fde290616c847653. Six named files alongside it have the above identities. Do not overwrite this evidence or extract into the installed mod tree.
- Source-only retrieval note SHA99ba03c5bd1c9231a9f6bd6894046d51c0064ab04dec1b77604f7bd6cc0313d9 and Lua preparation note SHAecebb9421877c2bd2bd626ad4ce3ddce6c04bfc660a2f1729d6b29f9c927f0c9 were fully read by root. Their proposed fixture/alias design remains preparation, not executed compatibility proof. They are under the same private t05-package-candidates directory; names navigation-grf-extraction-preparation-20261019.md and navigation-lua-source-preparation-1.md.

## Remaining decision and next owner

Root must qualify the six exports/recursive shapes and actual Taiwan decoding through the exact packaged loadLuaValue conversion using the pinned local Lua5.1 WASM/codec, outside the live game. The existing renewal-item-roundtrip fixture is an execution pattern; it is hardcoded to iteminfo/tbl and cannot run unchanged for these globals. Do not import Online.js/DBManager into a verifier or silently replace the packaged serializer/Big5 path with a UTF8/platform decoder. Test a finite authored Big5 trail-backslash case as an ordering risk; no actual Taiwan-name corruption is established. Keep optional English name/server-link overlays absent in the first isolated six-chunk profile and explicitly record that boundary.

Only after actual global/shape/codec/reference evidence can root freeze an identical independent Claude/Grok repair brief. A six-file data overlay is a possibility, not an adopted implementation. Preserve raw map/link/numeric identities and require named Chinese NPC/MOB searches plus a source-checked ordinary portal route in eventual live acceptance. Quiet logs alone are insufficient. Any incompatible table or decoding result must be recorded and used to bound the repair before dispatch; do not substitute empty/English tables.

T05.006 stays in_progress with its frozen console gate open. Full UI/story/IME/all-content/offline and user acceptance remain separate. Current runtime remains enabled, normally saved/logged out at izlude202,208/base3/job7/EXP781/146/HP51/SP13/zeny0; the browser is retained at character selection. No critical issue requiring a goal change is established.
