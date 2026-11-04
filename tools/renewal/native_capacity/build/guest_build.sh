#!/bin/sh
# T10.010.003/.004 guest build: one complete renewal Linux/arm64 map-server, built
# twice from the same prepared source and toolchain -- unpatched and with
# coin_capacity.patch -- so T10.010.004 can compare them.
#
# Runs inside ONE owned compiler container created by build_recipe.py.
# Inputs (PUT archive at /work/in before start):
#   source.tar.gz        deterministic prepared tree (prepare_source.py)
#   coin_capacity.patch  checked-in patch, applied with GNU patch -F 0
#   crash_verify.sh      the app's crash-trace verify.sh with its two
#                        hardcoded roots rewritten to owned /work/crash paths
#   apk.base, apk.lock   exact "name=version" frozen base and install delta (build mode)
#   apk-local.list, local-<i>.apk  optional authenticated-on-arrival local APKs
#                        (generated names; T10.010.004), either mode
#   guest_lib.sh         checks (also exercised by host tests)
#   inputs.env           hashes, mode, limits, expected ABI versions
#   owner.env            CONTAINER_ID (second PUT, after create)
# Output: /work/out, exported by GET archive and validated on the host.
#
# Owned state: only /work and the container's own apk installs. The stock
# runtime image's populated /rathena and any /symbols are never touched.
#
# Mirrors containers/rathena/Dockerfile at app 2c3b261 for the renewal
# map-server: same apk set, CXXFLAGS/CPPFLAGS/LIBS/LDFLAGS, configure
# --enable-packetver, crash-trace check, era check, objcopy/strip/debuglink.
set -eu
umask 022
# T10.010.004: Slim closes fd0 (OpenStdin=false). Root's actual control showed
# APK's trigger launch failing with fd0 closed and succeeding with fd0 on
# /dev/null (descriptor numbers were not traced). Keep fd0 valid for the whole
# guest; scripts and signature checking stay enabled.
exec 0< /dev/null
IN=/work/in
OUT=/work/out
mkdir -p "$OUT/logs"
. "$IN/guest_lib.sh"
. "$IN/inputs.env"
. "$IN/owner.env"
# Literal production paths (never taken from inputs).
CG_SELF=/proc/self/cgroup
CG_MOUNTS=/proc/self/mountinfo
CG_VIEW=/run/root-cgroup-view
APK=apk
APK_KEYS_DIR=/etc/apk/keys
APK_DB=/lib/apk/db/installed
STAGE=/work/closure
: "${MODE:?}" "${SOURCE_SHA256:?}" "${PATCH_SHA256:?}" "${PACKETVER:?}" "${JOBS:?}" "${STEP_TIMEOUT:?}"
: "${EXPECT_MUSL:?}" "${EXPECT_LIBSTDCXX:?}" "${EXPECT_ARCH:?}" "${CRASH_VERIFY_ORIG_SHA256:?}"
: "${CRASH_VERIFY_SHA256:?}" "${LOCK_SHA256:?}" "${BASE_SHA256:?}" "${LOCAL_LIST_SHA256:?}"

sha() { sha256sum "$1" | cut -d' ' -f1; }

# ---- 1. inputs, architecture and enforced limits: before ANY change
[ "$(sha "$IN/source.tar.gz")" = "$SOURCE_SHA256" ] || die "source sha256"
[ "$(sha "$IN/coin_capacity.patch")" = "$PATCH_SHA256" ] || die "patch sha256"
[ "$(sha "$IN/crash_verify.sh")" = "$CRASH_VERIFY_SHA256" ] || die "crash_verify sha256"
[ "$(apk --print-arch)" = "$EXPECT_ARCH" ] || die "arch $(apk --print-arch)"
check_cgroup
{
    echo "alpine=$(cat /etc/alpine-release)"
    echo "uname=$(uname -srm)"
    echo "nproc=$(nproc)"
    echo "apk=$(apk --version)"
    grep -E '^(MemTotal|MemAvailable):' /proc/meminfo
} > "$OUT/environment.txt" 2>&1
apk info -v 2>/dev/null | LC_ALL=C sort > "$OUT/apk-before.txt"
apk info 2>/dev/null | LC_ALL=C sort > "$OUT/apk-names-before.txt"
grep -qx "musl-$EXPECT_MUSL" "$OUT/apk-before.txt" || die "base musl is not $EXPECT_MUSL"
grep -qx "libstdc++-$EXPECT_LIBSTDCXX" "$OUT/apk-before.txt" || die "base libstdc++ is not $EXPECT_LIBSTDCXX"

# ---- 2. dependencies: the Dockerfile set + GNU patch (busybox patch has no -F)
WANT="bash git make cmake gcc g++ zlib-dev mariadb-dev linux-headers libunwind-dev binutils patch"
# Dependency model (both modes): BASE = exact name=version of every package the
# stock image already has (frozen); DELTA = exact name=version of every package
# the install adds. WANT must be covered by BASE + DELTA; DELTA never re-pins a
# BASE package; the install must leave every BASE package unchanged.
# T10.010.004: every BASE pin is a solver constraint (a conflicting repository
# refuses instead of upgrading), every DELTA file is authenticated with the
# stock keys and installed offline from exactly those bytes.
: > "$OUT/empty"
lock_candidate "$OUT/empty" "$OUT/apk-names-before.txt" "$OUT/apk-before.txt" > "$OUT/apk.base.current" || die "base freeze"
# canonical name=version order (prefix pairs: alpine-baselayout-data sorts before
# alpine-baselayout=), unique -- the order build-mode compares byte for byte
check_lock_file "$OUT/apk.base.current" nonempty
if [ "$LOCAL_LIST_SHA256" = none ]; then
    : > "$OUT/apk-local.list"
else
    [ "$(sha "$IN/apk-local.list")" = "$LOCAL_LIST_SHA256" ] || die "apk-local.list sha256"
    cp "$IN/apk-local.list" "$OUT/apk-local.list"
    check_local_list "$OUT/apk-local.list"
fi
case "$MODE" in
resolve)
    # Qualification run only: resolve the exact-base closure, retain it, build nothing.
    deps_transaction "$OUT/apk.base.current" "$OUT/apk-local.list" "" 0
    grep -q '^libunwind-dev-1\.8\.1-' "$OUT/apk-after.txt" || die "libunwind-dev is not ~1.8.1"
    # Candidates for Root to review/qualify: the delta and the frozen base.
    # Exact byte equality in canonical complete-tuple order (never a set/count test).
    lock_candidate "$OUT/apk-names-before.txt" "$OUT/apk-names-after.txt" "$OUT/apk-after.txt" > "$OUT/apk.lock.candidate" || die "lock candidate"
    cmp -s "$OUT/apk.lock.candidate" "$OUT/apk-simulate.delta" || die "installed names differ from the solver delta"
    cp "$OUT/apk.base.current" "$OUT/apk.base.candidate"
    check_coverage "$OUT/apk.base.candidate" "$OUT/apk.lock.candidate" $WANT
    grep -qx "musl-$EXPECT_MUSL" "$OUT/apk-after.txt" || die "musl changed from $EXPECT_MUSL (runtime ABI)"
    grep -qx "libstdc++-$EXPECT_LIBSTDCXX" "$OUT/apk-after.txt" || die "libstdc++ changed from $EXPECT_LIBSTDCXX (runtime ABI)"
    retain_closure all
    rm -rf "$STAGE"
    finalize
    exit 0 ;;
build)
    [ "$(sha "$IN/apk.lock")" = "$LOCK_SHA256" ] || die "apk.lock sha256"
    [ "$(sha "$IN/apk.base")" = "$BASE_SHA256" ] || die "apk.base sha256"
    check_lock_file "$IN/apk.base" nonempty
    check_lock_file "$IN/apk.lock" empty-ok
    # The stock image must be exactly the qualified base, before anything changes.
    cmp -s "$OUT/apk.base.current" "$IN/apk.base" || die "image packages differ from the qualified base"
    check_coverage "$IN/apk.base" "$IN/apk.lock" $WANT
    # Complete local closure -> no package network (solver and install offline).
    OFFLINE=1
    while IFS= read -r _nv; do
        awk -v nv="$_nv" '($4 "=" $5) == nv { f = 1 } END { exit !f }' "$OUT/apk-local.list" || OFFLINE=0
    done < "$IN/apk.lock"
    echo "offline=$OFFLINE" > "$OUT/apk-mode.txt"
    # Exact base + delta pins; an unavailable/conflicting pin fails here, before compilation.
    deps_transaction "$IN/apk.base" "$OUT/apk-local.list" "$IN/apk.lock" "$OFFLINE"
    retain_closure repo
    rm -rf "$STAGE"
    grep -qx "musl-$EXPECT_MUSL" "$OUT/apk-after.txt" || die "musl changed from $EXPECT_MUSL (runtime ABI)"
    grep -qx "libstdc++-$EXPECT_LIBSTDCXX" "$OUT/apk-after.txt" || die "libstdc++ changed from $EXPECT_LIBSTDCXX (runtime ABI)" ;;
*) die "unknown MODE $MODE" ;;
esac
{ gcc --version | head -1; g++ --version | head -1; ld --version | head -1; make --version | head -1; patch --version | head -1; } > "$OUT/toolchain.txt"

export CXXFLAGS="-g -O2 -fno-omit-frame-pointer -fno-optimize-sibling-calls"
export CPPFLAGS="-DRAGNAROK_CRASH_TRACE"
export LIBS="-lunwind"
export LDFLAGS="-Wl,--build-id=sha1 -rdynamic"

build_variant() { # build_variant <unpatched|patched>
    v=$1; d=/work/build-$v
    rm -rf "$d"; mkdir -p "$d"
    step "$v-extract" tar -xzf "$IN/source.tar.gz" -C "$d"
    if [ "$v" = patched ]; then
        step "$v-patch-check" patch -d "$d" -p1 -F 0 --dry-run -N -i "$IN/coin_capacity.patch"
        step "$v-patch" patch -d "$d" -p1 -F 0 -N --no-backup-if-mismatch -i "$IN/coin_capacity.patch"
        ! find "$d" -name '*.rej' -o -name '*.orig' | grep -q . || die "$v patch side files"
        ! grep -Eqi 'fuzz|offset|failed' "$OUT/logs/$v-patch.log" || die "$v patch not exact"
    else
        # Crash-trace fixture: the original hardcodes /rathena and /symbols.
        # Run the host-transformed copy on an owned copy of its directory.
        [ "$(sha "$d/ragnarok-crash-tests/verify.sh")" = "$CRASH_VERIFY_ORIG_SHA256" ] || die "crash verify.sh drift"
        rm -rf /work/crash; mkdir -p /work/crash
        cp -R "$d/ragnarok-crash-tests" /work/crash/ragnarok-crash-tests
        step crash-trace-verify sh "$IN/crash_verify.sh"
        mkdir -p "$OUT/crash-trace" && cp /work/crash/symbols/trace-tests/* "$OUT/crash-trace/"
    fi
    ( cd "$d" && step "$v-configure" ./configure --enable-packetver="$PACKETVER" )
    ( cd "$d" && step "$v-make-map" make -j"$JOBS" map )
    b="$d/map-server"
    [ -x "$b" ] || die "$v map-server missing"
    grep -qa "npc/re/scripts_main.conf" "$b" || die "$v is not renewal"
    ! grep -qa "npc/pre-re/scripts_main.conf" "$b" || die "$v has pre-re in it"
    if [ "$v" = patched ]; then
        grep -qa "ros_ch1_coin_capacity" "$b" || die "patched lacks the builtin"
    else
        ! grep -qa "ros_ch1_coin_capacity" "$b" || die "unpatched has the builtin"
    fi
    mkdir -p "$OUT/$v"
    objcopy --only-keep-debug "$b" "$OUT/$v/map-server.debug"
    readelf -n "$b" | sed -n 's/.*Build ID: //p' > "$OUT/$v/BUILD_ID"
    strip --strip-debug "$b"
    objcopy --add-gnu-debuglink="$OUT/$v/map-server.debug" "$b"
    cp "$b" "$OUT/$v/map-server"
    chown 0:0 "$OUT/$v/map-server"
    chmod 0755 "$OUT/$v/map-server"
    readelf -h "$OUT/$v/map-server" > "$OUT/$v/elf-header.txt"
    readelf -d "$OUT/$v/map-server" | grep -E 'NEEDED|RUNPATH|RPATH' > "$OUT/$v/dynamic.txt" || true
    # T10.010.004: keep the complete program-header report. readelf wraps each
    # header over two lines, so the old grep -A1 INTERP kept only the offset
    # and size rows and lost "[Requesting program interpreter: ...]".
    readelf -l "$OUT/$v/map-server" > "$OUT/$v/interp.txt" || die "$v readelf -l"
    # musl's loader resolves the NEEDED set (no separate ldd package needed).
    "/lib/ld-musl-$EXPECT_ARCH.so.1" --list "$OUT/$v/map-server" > "$OUT/$v/ldd.txt" 2>&1 || die "$v ldd"
    ! grep -q 'not found' "$OUT/$v/ldd.txt" || die "$v unresolved library"
    ( cd "$d" && sha256sum src/map/pc.cpp src/map/pc.hpp src/map/script.cpp ) > "$OUT/$v/patched-sources.sha256"
    rm -rf "$d"
}

build_variant unpatched
build_variant patched
rm -rf /work/crash
finalize
