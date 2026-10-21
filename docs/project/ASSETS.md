# Taiwan asset acquisition — T02

Coordinator-verified 2026-10-18. Acquisition and extraction passed. T03 subsequently verified [initial browser loading and character selection](INSTALLATION.md); exhaustive retrieval, Traditional Chinese coverage and content completeness remain unverified. Trial files are ignored under `.tools/renewal/`; no game payload is in Git.

## Provenance and fingerprints

The [official Taiwan download page](https://ro.gnjoy.com.tw/download/program_download.aspx) returned [RAGNAROK_260409.exe](https://twcdn.gnjoy.com.tw/ragnarok/Client/RAGNAROK_260409.exe) through its public download action. The full HTTP GET returned 200 with the same 2026-04-09 Last-Modified as the probe. Actual size **4,065,527,496 bytes**; the first 1 MiB matched the earlier HTTP 206 probe exactly.

Installer: `.tools/renewal/downloads/RAGNAROK_260409.exe`.

SHA-256: `b2abc92e8a5f39c1df2622141f8b1825d2eac0265a204f169f22694024f8ae19`. This is an observed local fingerprint; no publisher digest was found. ETag is transport metadata, not a checksum.

Extracted client root: **`.tools/renewal/assets/tw-20260409/app`**. The complete extracted tree has **4,936 files / 4,818,782,685 bytes**, including temporary installer artwork and unused Windows programs. The JSON manifest contains a relative path, byte size and SHA-256 for every file; it is local at `.tools/renewal/evidence/T02-files.json`, SHA-256 `d4d3ecc0b497a8e6ecf94bd7732fa3da5db77f2805f9de7f2b7131254615c81f`.

| Game archive | Bytes | Observed signature/version | SHA-256 |
| --- | ---: | --- | --- |
| `app/data.grf` | 2043560050 | Event Horizon / `0x300` | `1c7d68f70714937abbd3741a6b3aea34a7ed9da63428941d5df453efacd1c0ad` |
| `app/data0.grf` | 2123919641 | Master of Magic / `0x102` | `913402ace1d3c67818b4f070650a07eb157a6d62df9e394d596d59b4c7e6678a` |
| `app/event.grf` | 5833135 | Master of Magic / `0x102` | `7fff4e0eececd10df9a9c4f83b70d78dc4dbb99c5ece64b117df7db8a2f85575` |

Header table offsets are within each file. **T03 correction:** the pinned reader interprets GRF 3.0's count directly, giving **148161**, while legacy 1.02 arithmetic gives **92065** and **43**. T02 incorrectly subtracted the legacy adjustment from the 3.0 count (148154); archive bytes/hashes are unchanged. Tables have **not** been fully decoded or reconciled, and these are not unique-world/content counts. No `rdata.grf` is present. There are **203 BGM files, 30 System files and 5 AI files**. Loose text candidates include `System/iteminfo*.lub`, `System/LuaFiles514/MsgString.lub` and `PatchClient/Lua Files/MsgStringz/StringTable_TW.lub`. Their presence does not establish readable Chinese or server-side translated dialogue. T03's [installation record](INSTALLATION.md) adds successful browser startup and character selection, not exhaustive archive coverage.

## Reproducible extraction

1. Download over HTTPS to a `.part` file with curl; retain HTTP headers, check exact size, `MZ` prefix, RAR4 signature at offset 90624, probe-prefix equality and SHA-256 before renaming the complete download. Observed curl transfer: **99.33 s**, about **40.93 MB/s**; not a general network-speed promise.
2. Run `/usr/bin/bsdtar -tf` and `-tvf` on the original SFX, inspect relative regular-file paths, then extract with `bsdtar -xf … -C <empty-output>`. The MZ stub does not prevent this host's bsdtar 3.5.3 / libarchive 3.7.4 from reading the archive. Outer extraction passed in **80.96 s**.
3. The outer archive contains `RAG_SETUP_20260409.exe` (2301704 bytes), `-1.bin` (2097708800), `-2.bin` (2100000000) and `-3.bin` (430814758). Keep the standard names together in `.tools/renewal/extract/tw-outer`. The inner setup identifies Inno Setup **6.4.2 Unicode**. Do not concatenate the data files or run the Windows executables.
4. Build the extractor from pinned source below, list the setup paths and inspect them before extracting. The first collision-strict listing correctly reported duplicate `app/Ragexe.exe`. Use `--collisions rename-all` to preserve both variants; the three GRF paths have no collision. No setup program, redistributable or installer script is executed.
5. Run the pinned `innoextract` with `--extract --test --no-extract-unknown --collisions rename-all --color=0 --progress=0 --output-dir .tools/renewal/assets/tw-20260409 .tools/renewal/extract/tw-outer/RAG_SETUP_20260409.exe`. The extraction/checksum operation exited 0 with `Done.` in **19.95 s**. Hash all extracted files and check paths, signatures and offsets. Preserve errors/inputs for diagnosis rather than treating an unsupported tool as proof of a corrupt archive.

The [extractor manual](https://constexpr.org/innoextract/innoextract.1) specifies passing the executable for multipart installers and combining extract/test to abort on checksum errors. Its normal path conversion was retained; `--dump` was not used.

## Extractor and host tooling

The stock Homebrew innoextract formula reported 1.9. Instead, the coordinator built the source of [open upstream PR #210](https://github.com/dscharrer/innoextract/pull/210), which adds 6.4.2 support. It is **unmerged**; successful compilation alone was not treated as an extraction pass.

- Source repository: `https://github.com/dscho/innoextract.git`; detached commit **`376a13e7c41cc5528b6088d0dd16ec1b323a8d37`**, private checkout `.tools/renewal/innoextract-source`. No source modifications were required.
- Configure: `cmake -S .tools/renewal/innoextract-source -B .tools/renewal/innoextract-build -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH=/opt/homebrew -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DUSE_LTO=OFF -DBUILD_TESTS=OFF`.
- Build: `cmake --build .tools/renewal/innoextract-build --parallel 8 --target innoextract`. The executable reports `innoextract 1.10-dev + 376a13e`; local SHA-256 `bdd94bfa4409fa609164e69b77436886abff260d6116f575f6843821f372dc71`.
- Homebrew added CMake 4.4.4, Boost 1.92.0, xz 5.8.4 and their installed dependencies icu4c@78 78.3, lz4 1.10.0 and zstd 1.5.7_1. Root commands/build output are in ignored evidence. No Homebrew innoextract or sevenzip binary was installed.
- Observed trial directory footprint: **13 GiB, rounded by `du -sh`**, including download, extraction layers, source and build. Homebrew dependencies are separate. This is not the running game's footprint.

## Compatibility and next gate

| Input | Acquisition | Runtime/Chinese result |
| --- | --- | --- |
| Official Taiwan April 2026 client | Downloaded, extracted, hashed; three GRF versions identified | T03 initial browser loading/character selection passed; exhaustive archive retrieval, native Taiwan priority, fonts/input, text and server dialogue pending |
| Publisher's baseline kRO client | Not locally acquired | Only a publisher-tested baseline; not a local fallback PASS |
| Optional English art pack / `official_data.grf` | Not acquired | Not needed to close this acquisition step; do not substitute it for Chinese |

T03's later [installation record](INSTALLATION.md) identifies the pinned app, actual bundled reader/runtime and verified browser startup. Next T04 supplies gameplay/persistence/offline/recovery evidence; T05 supplies the Chinese pilot. No client date or file count defines an episode. See the [acquisition review](reviews/2026-10-18-T02.md) and current [Status](STATUS.md).

Git rollback restores documentation/source records only. The T02 acquisition step changed no app or save data; T03's later installation is recorded separately. Downloads/extraction/build files remain local; preserve them while the app references them. Homebrew package state is separate from Git and must be considered separately if undoing setup.


## Later October client acquisition

[T07.007](reviews/2026-10-21-T07.007.md#fresh-outer-extraction-and-four-file-reconciliation-qualified)
separately acquires the official October2Taiwan installer,4153946520bytes/SHA
3d4202eb52b885b94b4e84b40ae5669b97d0c3649a8302f2246d0d1af0e1dc71.
Root qualifies the official native26.04RAR reader and complete checksum test,
then extracts/reconciles four outer files totaling4761139292bytes. The
inner6.4.2Unicode format and complete4976-file listing qualify. Actual inner
extract/test and independent full4976-file/115-directory manifest now pass; its
SHA is2706c3a8463be72d20e621028b6d3cc2c9c15988a8fce419733c1fe243251edd.
The [full archive pins](reviews/2026-10-21-T07.007.md#complete-inner-extraction-and-independent-manifest-qualified)
record changed data.grf and two hashes matching the recorded April pins. No loose
DATA.INI exists; lookup precedence remains open. Later header/name preparation
and the new fixed-profile paired inventory are recorded in T07.007.
The tooling list above is the historical T02record; later tools and
failed-reader recovery are in T07.007. April assets/pins and running worlds
remain in place. This new acquisition is not a playable-content qualification.


## Official patch source preparation — additive files only

[T07.007patch preparation](reviews/2026-10-21-T07.007.md#missing-map-name-witnesses-found-in-the-official-august-patch)
finds exact official CDN metadata routes through manifest-pinned installer
configuration literals. The full patch3.txt index is162117bytes/SHA
`ec7a274f282ba7b5f1b15cddbca32c06a8a1be88c5df546f84e6a05bf5eeb69b`.
Two exact August25GPFs are separately acquired/fully hashed, never installed:

| Patch index | Bytes | Local full SHA256 |
| --- | ---: | --- |
|9298|306097616|70725f6624f947c3096066cc66a07fcd2440adf94137b79561ed2d67843f9f0e|
|9303|86992|03764f614453d2b453a5ab5b552f6af9f66599a3642943566f72cbae6a501d07|

Both are legacy0x102GRF-family containers. Root independently traverses all5708
records and compares every complete field/record byte with the unchanged qualified
core. All12GAT/GND/RSWname entries for mu_fild01/ygg_edge/ygg_fruit/ygg_roots exist
in9298; that patch also supplies22previous RSW-gap name counterparts. These are
name/table witnesses, not payload/dependency/render/ordinary-play qualification.
The selected two files do not represent all59noncomment index rows after the
installer's static9296value. Patcher-marker meaning, full update/lookup order,
remaining patch contents and new reader/runtime admission remain open. Base and
patch provenance stay separate; neither existing world or its assets change.
