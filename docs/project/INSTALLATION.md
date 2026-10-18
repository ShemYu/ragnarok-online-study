# Local installation — T03

Coordinator-verified 2026-10-18: Ragnarok Offline **1.6.3** starts its local Renewal server and reaches the character-selection screen through its documented **headless app + browser** mode using the acquired Taiwan assets. Native desktop-window interaction remains unverified because computer control returned `cgWindowNotFound` for both this app and Finder. This checkpoint does not establish gameplay, complete Chinese text or full-content coverage.

## Installed artifact and state

- Release: [v1.6.3](https://github.com/Flux159/ragnarokoffline.app/releases/tag/v1.6.3), `Ragnarok.Offline-1.6.3-arm64.zip`, **248405765 bytes**. SHA-256 **`c0f8a3b80064a8e3f23ae95f30e1776e3c30a5949c60d9b94bfd094fa4297f76`**, matching the published artifact digest recorded in [Foundation](FOUNDATION.md).
- Installed app: `~/Applications/Ragnarok Offline.app`; bundle `com.chronotale.ragnarokoffline`, arm64, macOS minimum 13.0. Both unpacked and installed copies passed `codesign --verify --deep --strict` and `spctl --assess`; assessment was **accepted, Notarized Developer ID**, CHRONOTALE, INC. Gatekeeper was not changed.
- Packaged and installed runtime marker: **`2c3b261`**; full tagged source `2c3b2612973fb8d0ae6ad366a2b298686f2404cb`. Packaged `electron/main.js` and `settings-store.js` match that source byte for byte. Bundled dependency pin files match [Foundation](FOUNDATION.md); this is packaging evidence, not independent reconstruction of every embedded server binary.
- RemoteClient's supported `--capabilities` returned managed protocol 1, service `robrowser-remoteclient`, version **1.0.5**. The running installed binary SHA-256 was `ee6b328ec73a591b23b514379e1b34e876b5d860d0e1aa4d9aa15dd7173eb1c1`.
- New app data: `~/Library/Application Support/Ragnarok Offline`, containing generated `runtime/`, `state/`, `nebula/` and Electron caches. No existing installation or saves were found. The coordinator seeded configuration before first launch, preventing legacy-home migration; no user's existing progress was changed.
- GRFs remain at the absolute paths under `.tools/renewal/assets/tw-20260409/app`; moving that tree requires updating configuration. Original archives were not modified.

## Reproduce configuration and launch

1. Read [Assets](ASSETS.md), verify the exact ZIP hash and extract it with `ditto -x -k` into an empty staging directory. Check `~/Applications/Ragnarok Offline.app`, `/Applications/Ragnarok Offline.app`, the current support home, and legacy `~/Library/Application Support/RagnarokMac` / `~/Library/Application Support/com.ragnarokmac.app` before copying the app with `ditto` to `~/Applications`. If existing state is found, preserve it and establish a tested isolated restore before mutation; the fresh-install observation here is not authorization to overwrite it.
2. Before the first app process, create the support root and `state/`. In `client.json`, use `mode: "host"`, `lan: false`, empty `join_host`/`fallback_grf`, the absolute `data.grf` path as `data_grf`, `data0.grf` as `rdata_grf`, `event.grf` as `official_grf`, and `BGM` as `bgm_dir`. Set `vm_ram_mib: 4096`. Use user-only permissions for configuration and state.
3. In `state/settings.json`, set `auto_update: false`, `install_update_on_quit: false`, `open_settings_first: true`, `prerenewal: false`, `hosting_scope: "local"`, `population_enable: false`, `packetver: "20221005"`, `game_text: "client_taiwan"`, `agent_play: false`, `agent_window: false`. Keep the three archive paths explicit: the directory scanner retains only the first additional GRF.
4. Run the app's documented mode, with no other copy running:

   ```sh
   "$HOME/Applications/Ragnarok Offline.app/Contents/MacOS/Ragnarok Offline" --headless
   ```

   Wait for `headless: ready`, then open **`http://127.0.0.1:3338/`** in the browser. First boot on this host reached ready in about **36 seconds**, including VM image installation, server-image loading and database setup; not a timing guarantee. For this diagnostic character-screen check, use the public seeded GM login documented in the [pinned upstream README](https://github.com/Flux159/ragnarokoffline.app/blob/2c3b2612973fb8d0ae6ad366a2b298686f2404cb/README.md#getting-started). The coordinator observed empty character slots without creating a character or using admin gameplay commands. Use an ordinary account for T04 play; normal solo progression requires T04/T11 evidence.
5. Settings are available through the local authenticated URL in `state/headless-admin.url`; it changes each start. Keep that URL private. Stop with Ctrl-C or SIGTERM and wait for graceful completion before relaunching or copying state. Do not run desktop and headless copies together. See the pinned [headless guide](https://github.com/Flux159/ragnarokoffline.app/blob/v1.6.3/docs/HEADLESS.md); upstream labels this mode experimental.

## Actual startup checks

| Check | Coordinator result |
| --- | --- |
| Runtime/version and source configuration | App/runtime 1.6.3 / `2c3b261`; server log explicitly reports packet version **20221005** |
| Generated archive priority | `state/asset-config/DATA.INI`: **event → data0 → data**; source-supported order, native Taiwan precedence still unverified |
| Taiwan detection and browser settings | Detected `twRO` from `msgstring_tw.lub` in `data.grf`; `Config.local.js` has langtype **4**, Renewal true, packetver 20221005 and address 127.0.0.1 |
| Population | Generated `population_engine_enable: 0` |
| Server readiness | `ragnarok-stack status`: database, login, character and map services all Up; map log reports ready on 5121 |
| Network | Observed listeners **127.0.0.1 only**: game/assets 3338, admin 3339, login 6900, character 6121, map 5121 and emblem web 8888 |
| Visible acceptance | Taiwan login artwork/menu loaded; successful local login rendered the empty character-selection screen in Chrome |
| Machine allocation | Generated Nebula configuration: **4096 MiB maximum RAM, 4 vCPUs, 16 GiB sparse data disk**; these are allocation limits, not measured gameplay consumption |
| Initial disk observation | `du -sh`: trial tree about 13 GiB, installed app 524 MiB, app support 1.0 GiB; rounded allocated sizes, sparse disks have larger logical capacity |

The startup log is **not error-free**. It reports missing optional import files, a packet-version-dependent feature disabled, empty roulette defaults and a disabled companion NPC reference. Services still reached ready and character login worked. T04 must triage these messages before treating baseline play as verified; T06 must reconcile actual loaded content. No count or world-map `episode: 20` setting establishes a complete episode.

Traditional Chinese appeared in the login menu, but character-selection labels include English. Fonts/input, item and skill text, quest log and server story dialogue remain T05 checks. The Rust reader supports the actual GRF 3.0 and 1.02 families; startup exercised asset retrieval, not every archive entry. Electron's separate skin reader skips 1.x archives. No full archive or localization PASS is implied.

## Evidence and rollback

Ignored coordinator records: `.tools/renewal/evidence/T03-{artifact,packaged-source,preflight,install-preparation,grf-format-audit,runtime}.json`, signature assessment, raw headless/map logs and `T03-character-select.jpg`. Raw startup output contains a local admin sign-in URL and must not be published. Only redacted results are in Git. See [paired review](reviews/2026-10-18-T03.md).

Git rollback is `git revert <T03-checkpoint>` and affects source/documentation only. It does not uninstall the app or restore the VM/database. Keep this fresh trial state and assets until T04's application backup plus real progress-restoration rehearsal succeeds. To undo an unused fresh trial, first stop the owned app/VM cleanly, then **move** this run's app/support directory to a named recovery location; preserve it instead of deleting uncertain state. Never apply that procedure to later user progress without a tested backup. The project and Homebrew tooling are separate.

Later verified recovery supersedes that historical T03 gate: T04 demonstrated real A→B→A→B progress restoration. The fresh [T05.006 H backup](reviews/2026-10-18-T05.006.md#fresh-full-h-created-and-validated-before-installation) now preserves the newer current save and both installed overlays, with archive/member/current-row equality and read-only inspection verified; H itself has not been restored. Never apply fresh-install removal or older A–G restoration to later play merely to remove a mod.


## Verified client-only item overlay (T04.003)

The original Taiwan item assets remain pinned and unchanged. A supported local mod `tw-iteminfo-utf8` **1.0.1**, generated by [tools/renewal](../../tools/renewal/README.md), is installed/enabled in app state. Its staged UTF-8 source SHA-256 is `ec031e40f24ed7d0eeb3d65fe66678d231d436ae29f22cf3158d79a45d693aba`. Config places it before base `System/itemInfo.lub`; langtype4/protocol20221005 unchanged. Root verified complete modern Lua value equality, visible Chinese item art, ordinary pickup, equipment, full app/VM restart and supported disable/re-enable rollback. [Exact evidence and recovery steps](reviews/2026-10-18-T04.003.md). Source checkout does not include generated tables or game bytes. Full offline, Chinese/story/content completeness and user acceptance remain separate gates.

## Verified narrow server-text pilot (T05.001)

Supported mod **tw-carocc-pilot0.1.0** is installed/enabled alongside the item repair. Authored [generator/runbook](../../tools/renewal/CAROCC_ZH_PILOT.md), source checkpoint307e2bf; NPC SHA463a1dca3401a4c445ac44995b56eda2733df34d01ae23e803410e0b71d18f55. Only8 opening/menu/Hello display literals are translated; copied quest logic/IDs/rewards/other branches are byte-preserved. Root verified actual Chinese dialogue, normal re-entry, unchanged save and supported disable/re-enable rollback. [Comparison, proof and evaluation](reviews/2026-10-18-T05.001.md). Disable this mod and Apply to restore stock English; Git alone does not uninstall it. Full story/UI/IME/content remain separate requirements.


## NPC dictionary package — functional gates verified, console issue open

T05.006 now has npc-plaintext-zh-tw1.0.0 installed/enabled through the supported inner-folder picker, Apply and Stop→Start. Root verified all five installed files/four staged resources, generated registration, four actual decoded HTTP identities and the fresh real-game core-ready status. The six-table saved state still exactly matches fresh H; only the expected enabled-list addition changed among prior protected files. Both older overlays remain enabled. [Exact installed gate and limits](reviews/2026-10-18-T05.006.md#supported-installation-and-actual-servedcore-readiness). Ordinary named dialogue, persistence/full app-service relaunch and functional off/on qualification subsequently passed, with the package currently enabled and newer save preserved. Final console capture has six missing navigation-table errors; attribution/repair remains open before T05.006 readiness. No full language/story/IME/content acceptance. Disable only this package through supported Apply/rebuild/lifecycle to roll it back; never restore an older database merely to toggle it.
