# T04 measured resource observation

Coordinator inspected the actual completed dataset on 2026-10-18; parent T04 remains open for full host/browser offline and fog-rendering checks. Ordinary pickup and EXP/persistence later passed. Frozen runtime/source/assets are in [Installation](INSTALLATION.md). This report replaces estimates with one measured session, not a full-world minimum specification.

## Duration and method

The sampler exited successfully with **181 records / 1800.057 seconds**. Sample timestamps span **04:45:26.077082 → 05:15:26.082593 UTC**, monotonic sample span **1800.002063 seconds**. Sampling interval: approximately 10 seconds. Dataset SHA-256 `395abcbac5c2a5a95b95f006bae0e93345065988d6a7956296e56c375af17ab6`; sampler fingerprint is in [Baseline](BASELINE.md).

`ps` cumulative per-PID CPU deltas produce percentages where 100% is one CPU core. RSS is summed by executable-path group, expressed as MiB (1024² bytes). Present samples only are summarized; the first CPU sample is unavailable. This is a **mixed play/maintenance session**, including quests, combat, inventory, logout, full restart, backups and restores. It is not 30 minutes of uninterrupted combat.

## Actual results

| Group | Present samples | RSS MiB median / maximum | CPU one-core % median / maximum |
| --- | ---: | ---: | ---: |
| App Electron (3 processes) | 180 | 211.48 / 213.06 | 0.30 / 3.40 |
| Asset server | 175 | 174.30 / 205.73 | 0 / 5.90 |
| VM daemon | 179 | 26.59 / 26.73 | 0.10 / 0.60 |
| Matching Virtualization process | 179 | 1469.19 / 1500.41 | 1.80 / 81.04 |
| Transient app supervisors | 8 | 12.77 / 19.81 | 0.60 / 2.20 |
| **All shared Chrome processes (40–50)** | 181 | **12748.55 / 13732.91** | **52.70 / 141.75** |

The four core app/asset/VM groups were simultaneously present in 175 samples. Their summed RSS ranged **1540.58–1915.59 MiB**, median **1896.95 MiB (1.85 GiB)**; summed CPU median 2.30%, maximum 82.04% of one core. Transient supervisor and Chrome are excluded from that aggregate. This is summed RSS, not unique physical memory.

Chrome includes the user's other tabs and cannot be quoted as the game's RAM requirement. The Virtualization matcher also covers every matching XPC process: observed counts were only 0 or 1. Its process disappeared alongside the owned VM daemon at sampled 04:53:36/46 and returned with a new PID at 04:53:56. This supports temporal attribution to this app's VM, but is not a unique-memory or container allocation measurement. The app's configured 4096 MiB VM maximum is a ceiling, separate from measured RSS.

CPU spikes include restarts/recovery. New PIDs are charged accumulated CPU when first observed; exited processes lose their final unsampled tail, and short-lived processes can be missed. PID reuse is not detected. Do not treat maxima as steady combat demand. Sampling shows the Electron group missing at 04:53:36; the VM at 04:53:36/46; asset server at 04:53:36/46/56, 04:56:16/26 and 05:03:26. Those are observations, not exact downtime durations.

## Rendering and disk

Actual visible viewport **3440×1296, DPR 1**, configured 60 FPS cap. Named post-initialization observations in the real game showed **59.9–60 FPS** at full relaunch, restored equipment, state B, Captain quest, Wood inventory, Sailor completion and Izlude arrival. These are the client's approximately one-second render-loop averages, not a continuous frame-time trace or GPU timing. A 0 FPS capture taken during restoration/map initialization remains recorded and is not discarded as a steady-state sample. Heavy scenes and frame-time percentiles remain unmeasured. CUA's read-only page scope did not expose `requestAnimationFrame`, so no injected frame logger was used. A Chrome-internal diagnostics URL was policy-blocked; no alternate route to it was attempted.

Allocated disk measured by `du -sk` after the trial:

| Component | Allocated KiB | Approx. GiB |
| --- | ---: | ---: |
| Installed app | 536568 | 0.51 |
| App support, including VM | 1110352 | 1.06 |
| Taiwan extracted asset root | 4718352 | 4.50 |
| VM disk files (included in support) | 686416 | 0.65 |
| Entire ignored engineering trial (includes assets/downloads/source/extraction tools) | 14143924 | 13.49 |

The trial footprint is not a minimal end-user installation; do not add nested rows together. Sparse disk logical capacity differs from allocated storage. Full-content qualification may load heavier scenes and add overlays/backups.

Later inventory checkpoint on2026-10-18: the current checkout's ignored .tools/renewal tree is **15734228KiB, approximately15.01GiB**, after preserving paired catalogs, independent references and native-response evidence. This supersedes13.49GiB only for that checkout tree's later footprint; it excludes sibling worker worktrees, installed app/support and other locations. It is not a new game-only disk requirement. A separate read-only /api/health check returned200/status ok/version1.0.5, with installed app and asset-process executables present. No game input/settings/network change or new performance sampler was used; this is service liveness, not renewed gameplay/full-world performance qualification.

## Practical limit and next action

This Mac has ample headroom for the measured baseline. A different machine's minimum RAM/CPU requirement is not established by this one run. Keep the current VM setting for the Chinese pilot; the bounded item-art repair/pickup/relaunch/rollback is now verified in [T04.003](reviews/2026-10-18-T04.003.md). Repeat performance checks on the eventual integrated Chinese/content build in T12. Raw measurements/screenshots remain ignored; this redacted method, fingerprints and results are version controlled.


## Later functionality-first acquisition observations — 2026-10-21

These are isolated engineering-tool observations from [T07.007](reviews/2026-10-21-T07.007.md),
not new game minimum specifications or a full-milestone estimate. Complete source/
input/output pins and failure evidence are in that review. Downloads are capped
at16MiB/s by policy; their elapsed times do not measure the connection's maximum.

| Bounded operation | Observed elapsed | Sampled owned RSS peak | Result / limit |
| --- | ---: | ---: | --- |
| October installer transfer + local hash,4153946520bytes | 249.650152375s | not measured by this transfer receipt | Complete; publisher digest uninspected |
| Fresh outer native extraction | 30.064440791s | 10567680bytes | Four files; full independent sizes/CRC/SHA reconcile |
| Inner extract/test | 21.211300833s | 20283392bytes |4976files; independent full manifest/hash follows |
| Independent three-GRF record reference | 5.865303s | 86163456bytes |156800new records parsed;92108unchanged legacy references rebound |
| Two official GPF transfers + rehash,306184608bytes | 18.969805333s | 44777472bytes | Complete separate local files; not installed |
| Independent5708patch-name record preparation | 1.597509958s | 31342592bytes | All12target terrain-name witnesses; payload/runtime untested |

RSS is combined owned-process-group sampling at roughly0.5seconds, not unique
physical memory or an OS containment limit. Every listed guarded command exits0
with no guard action; observations do not include provider/other-app resource use.
These stages are not additive end-to-end delivery times and some independent work
runs in parallel. Exact Claude/Grok API tokens and billing remain unobserved.

At the acquisition checkpoint, before later candidate preservation, the root
checkout's ignored `.tools/renewal` allocation is48165232KiB
(approximately45.93GiB), freshly measured after the new package/patch/reference
work. This supersedes its older15.01GiBengineering-tree observation only. It
includes preserved downloads, both extraction layers, source/builds, catalogs,
references, failure evidence and retained response bodies; excludes sibling
worker checkouts and separately located installed apps/worlds. It is not the
end-user installation size. Do not add nested component rows to this total.

No new hardware/cloud purchase is identified by these bounded stages. Full
content, heavier scenes, retained final assets, patch closure and T12performance
still need verification before a full build/time/cost estimate can be defended.

Official candidate patch-suffix HEAD census later returns59/59HTTP200with known
lengths:465176988compressed bytes total (about444MiB), of which158992380remain
unacquired. At the16MiB/s policy ceiling the byte-transfer-only lower bound is
about27.7seconds for the entire suffix, before request latency/hash/retries and
all format/content checks; it is not an elapsed-time promise. [T07.007.002](tasks/T07.007.002.md)
compares the bounded acquisition/reader plan before any remaining body transfer.


The later corrected plan00e83e4is followed by complete additive acquisition:
57new GETs/158992380bytes, two existing objects reused, all59independently
rehashed/465176988bytes. Owned guard44.205241s, sampled RSS36536320bytes,
81samples/no action/exit0/empty stderr. Internal transfer/hash campaign is
43.708965625s at the16MiB/s cap; request latency is included. New disk growth
is roughly159MBplus bounded headers/receipts/logs, not another full465MBcopy.
Before launch available space is529142857728bytes;128GiBfloor passes throughout.
No new broad engineering-tree size or full-game hardware/time estimate is
claimed. [Exact source/receipt verification](reviews/2026-10-21-T07.007.md#complete-official-candidate-suffix-acquired-as-opaque-files).
