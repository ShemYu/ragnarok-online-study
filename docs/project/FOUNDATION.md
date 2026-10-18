# Pinned foundation trial — T01

Checked 2026-10-18 by the coordinator. This identifies a reproducible candidate for T02–T05; it does not establish working gameplay, Taiwan assets, Chinese text or complete content.

## Source and artifacts

Candidate: [Ragnarok Offline v1.6.3](https://github.com/Flux159/ragnarokoffline.app/releases/tag/v1.6.3), published 2026-10-16. The annotated tag resolves to app commit `2c3b2612973fb8d0ae6ad366a2b298686f2404cb`. The release's `target_commitish: main` is a branch name, not the source pin.

| Mac arm64 artifact | Bytes | Published SHA-256 |
| --- | ---: | --- |
| [ZIP](https://github.com/Flux159/ragnarokoffline.app/releases/download/v1.6.3/Ragnarok.Offline-1.6.3-arm64.zip) | 248405765 | `c0f8a3b80064a8e3f23ae95f30e1776e3c30a5949c60d9b94bfd094fa4297f76` |
| [DMG](https://github.com/Flux159/ragnarokoffline.app/releases/download/v1.6.3/Ragnarok.Offline-1.6.3-arm64.dmg) | 257396059 | `2073bdf311dab09e77ea6e1dca746cd3837acbc1417f099d900c4d13bb427f19` |

These are release metadata digests. T03 must hash the actual downloaded artifact and inspect its identity/signature and bundled version evidence before installation. The ZIP is the proposed acquisition for a user-local installation; neither artifact has been downloaded at this checkpoint.

The coordinator cloned the tagged source into ignored `.tools/renewal/upstream`, resolved the tag locally and read these files at that commit. No upstream script was executed.

| Component | Exact source pin | Pinned source record |
| --- | --- | --- |
| roBrowserLegacy fork | `775f8847a8b09749d03c82fcb554e155401d1e02` | `config/VENDOR_PINS` |
| rAthena fork | `0693b8c69911d5ca42269684aa036b67d67f4d3e` | `config/VENDOR_PINS` |
| ROenglishRE | `66cdfec631603fda6a90ba4bbe26ab07b5204c84` | `config/VENDOR_PINS` |
| rAthena upstream diagnostic reference | `e985006171d2eb320ee512a653f4c83aea3d81b6` | `config/VENDOR_PINS`; not the shipped fork revision |
| Rust RemoteClient | `66ba94e2b84c4092e4b9cc9d0dcc805313438f53` | `config/REMOTECLIENT_PIN` |
| docker-slim / nebula source | `ad002a656a9fecdf2e224cf7433e1b94c809cecd` | `config/DOCKER_SLIM_PIN` |
| Nebula embed kit | CI tag `v0.2.7`; minimum `0.2.7` | `.github/workflows/build.yml`, `config/NEBULA_MIN_VERSION` |

Primary source records: [vendor pins](https://github.com/Flux159/ragnarokoffline.app/blob/2c3b2612973fb8d0ae6ad366a2b298686f2404cb/config/VENDOR_PINS), [RemoteClient pin](https://github.com/Flux159/ragnarokoffline.app/blob/2c3b2612973fb8d0ae6ad366a2b298686f2404cb/config/REMOTECLIENT_PIN), [docker-slim pin](https://github.com/Flux159/ragnarokoffline.app/blob/2c3b2612973fb8d0ae6ad366a2b298686f2404cb/config/DOCKER_SLIM_PIN), [build workflow](https://github.com/Flux159/ragnarokoffline.app/blob/2c3b2612973fb8d0ae6ad366a2b298686f2404cb/.github/workflows/build.yml).

## Trial prerequisites and limits

- Packaged Mac build: Apple Silicon arm64; declared macOS minimum 13.0 in `package.json`. This avoids the separate compiler/toolchain requirements of a source build.
- The app supplies an Electron shell, a Linux microVM, rAthena, MariaDB, roBrowserLegacy and a local asset/proxy service. User-supplied `data.grf`, optional `rdata.grf` and BGM remain separate and outside Git.
- Default protocol is `20221005`; `20250402` is experimental. Client/server packet versions must match. These dates do not establish an episode cutoff.
- Publisher resource claims: VM memory defaults to one quarter of host RAM, capped at 4 GB; config uses 4 CPUs and a 16 GiB sparse data disk. Reported runtime storage is about 4.5 GB, excluding the app and client assets. Actual host memory, CPU, disk and frame performance remain T04 measurements.
- Auto-update downloading defaults on. T03 must disable it for the pinned trial and confirm the running version. Inspect normal macOS launch/signature results; do not remove platform security protections to force a pass.
- Separate worktrees share app state by default. The expected fresh-install support directory and both normal app locations were absent during the coordinator's bounded check. Recheck before installation; preserve and test recovery for any existing state discovered then.

Primary requirements: [README at the pin](https://github.com/Flux159/ragnarokoffline.app/blob/2c3b2612973fb8d0ae6ad366a2b298686f2404cb/README.md), [advanced features and storage](https://github.com/Flux159/ragnarokoffline.app/blob/2c3b2612973fb8d0ae6ad366a2b298686f2404cb/docs/ADVANCED_FEATURES.md), [protocol configuration](https://github.com/Flux159/ragnarokoffline.app/blob/2c3b2612973fb8d0ae6ad366a2b298686f2404cb/config/PACKETVERS).

## Taiwan input and unresolved checks

The [official Taiwan download page](https://ro.gnjoy.com.tw/download/program_download.aspx) advertises the April 2026 client. Its public download action returned [RAGNAROK_260409.exe](https://twcdn.gnjoy.com.tw/ragnarok/Client/RAGNAROK_260409.exe). The coordinator's HTTP HEAD returned 200, `Content-Length: 4065527496`, last modified 2026-04-09. This confirms an available input, not a downloaded, extracted or compatible asset set. T02 must record actual hashes and archive entries. Static extraction tooling is not currently available among the checked `7zz`, `7z`, `innoextract`, `unar` and `unrar` commands.

The publisher describes English tables and Korean/Western decoding. Big5/CP950, Taiwan fonts/input, server-side Chinese dialogue and full story translation remain unverified. The world-map setting `episode: 20` is a UI configuration, not proof of Episode 20 completeness. No episode scope is accepted by this manifest.

Next: T02 controlled acquisition and extraction; T03 installation; T04 baseline play and recovery; T05 Chinese pilot. Paired audit findings and coordinator corrections belong in the linked task review and [Status](STATUS.md).
