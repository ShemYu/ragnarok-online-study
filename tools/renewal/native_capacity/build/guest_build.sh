#!/bin/sh
# T10.010.003 guest build: one complete renewal Linux/arm64 map-server, built
# twice from the same prepared source and toolchain -- unpatched and with
# coin_capacity.patch -- so T10.010.004 can compare them.
#
# Runs as PID 1's child inside ONE owned compiler container created by
# build_recipe.py. Inputs arrive by PUT archive at /work/in:
#   source.tar.gz        deterministic prepared tree (prepare_source.py)
#   coin_capacity.patch  checked-in patch, applied with GNU patch -F 0
#   inputs.env           sha256s, packet version, jobs, per-step timeouts,
#                        expected ABI library versions
# Output: /work/out (exported by GET archive, then validated on the host).
#
# Mirrors containers/rathena/Dockerfile at app 2c3b261 for renewal map-server:
# same apk set, CXXFLAGS/CPPFLAGS/LIBS/LDFLAGS, configure --enable-packetver,
# crash-trace verify, era check, objcopy/strip/debuglink. It differs only in
# building `make map` (not `make server` + pre-re) and in its explicit checks.
set -eu
umask 022
IN=/work/in
OUT=/work/out
mkdir -p "$OUT/logs"
exec 3>&2
log() { printf '%s %s\n' "$(date -u +%H:%M:%S)" "$*" >&3; printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" >> "$OUT/logs/steps.log"; }
die() { log "FAIL $*"; printf 'FAIL %s\n' "$*" > "$OUT/RESULT"; exit 1; }
. "$IN/inputs.env"
: "${SOURCE_SHA256:?}" "${PATCH_SHA256:?}" "${PACKETVER:?}" "${JOBS:?}" "${STEP_TIMEOUT:?}"
: "${EXPECT_MUSL:?}" "${EXPECT_LIBSTDCXX:?}" "${EXPECT_ARCH:?}"

step() { # step <name> <cmd...>: bounded, logged; nonzero or timeout is failure
    name=$1; shift
    log "begin $name"
    if ! timeout "$STEP_TIMEOUT" "$@" > "$OUT/logs/$name.log" 2>&1; then
        tail -n 40 "$OUT/logs/$name.log" >&3 || true
        die "$name"
    fi
    log "end $name"
}

# ---- identity of inputs and environment (before any change)
[ "$(sha256sum "$IN/source.tar.gz" | cut -d' ' -f1)" = "$SOURCE_SHA256" ] || die "source sha256"
[ "$(sha256sum "$IN/coin_capacity.patch" | cut -d' ' -f1)" = "$PATCH_SHA256" ] || die "patch sha256"
[ "$(apk --print-arch)" = "$EXPECT_ARCH" ] || die "arch $(apk --print-arch)"
{
    echo "alpine=$(cat /etc/alpine-release)"
    echo "uname=$(uname -srm)"
    echo "nproc=$(nproc)"
    grep -E '^(MemTotal|MemAvailable):' /proc/meminfo
    echo "cgroup=$(cat /proc/self/cgroup)"
    for f in memory.max memory.swap.max cpu.max pids.max; do
        for d in /run/root-cgroup-view /sys/fs/cgroup; do
            [ -r "$d/$f" ] && { echo "$d/$f=$(cat "$d/$f")"; break; }
        done
    done
} > "$OUT/environment.txt" 2>&1
apk info -v 2>/dev/null | sort > "$OUT/apk-before.txt"

# ---- toolchain: the Dockerfile's build set plus GNU patch (busybox patch has no -F)
step apk-add apk add --no-cache bash git make cmake gcc g++ zlib-dev mariadb-dev linux-headers \
    'libunwind-dev~1.8.1' binutils patch
apk info -v 2>/dev/null | sort > "$OUT/apk-after.txt"
grep -qx "musl-$EXPECT_MUSL" "$OUT/apk-after.txt" || die "musl is not $EXPECT_MUSL (runtime ABI)"
grep -qx "libstdc++-$EXPECT_LIBSTDCXX" "$OUT/apk-after.txt" || die "libstdc++ is not $EXPECT_LIBSTDCXX (runtime ABI)"
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
        grep -Eqi 'fuzz|offset|failed' "$OUT/logs/$v-patch.log" && die "$v patch not exact"
    fi
    if [ "$v" = unpatched ]; then
        # The Dockerfile's crash-trace check hardcodes /rathena and /symbols.
        ln -sfn "$d" /rathena
        step crash-trace-verify sh /rathena/ragnarok-crash-tests/verify.sh
        rm -f /rathena
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
    chmod 0755 "$OUT/$v/map-server"
    readelf -h "$OUT/$v/map-server" > "$OUT/$v/elf-header.txt"
    readelf -d "$OUT/$v/map-server" | grep -E 'NEEDED|RUNPATH|RPATH' > "$OUT/$v/dynamic.txt" || true
    readelf -l "$OUT/$v/map-server" | grep -A1 INTERP > "$OUT/$v/interp.txt" || true
    # musl's loader resolves the NEEDED set (no separate ldd package needed).
    "/lib/ld-musl-$EXPECT_ARCH.so.1" --list "$OUT/$v/map-server" > "$OUT/$v/ldd.txt" 2>&1 || die "$v ldd"
    ! grep -q 'not found' "$OUT/$v/ldd.txt" || die "$v unresolved library"
    ( cd "$d" && sha256sum src/map/pc.cpp src/map/pc.hpp src/map/script.cpp ) > "$OUT/$v/patched-sources.sha256"
    rm -rf "$d"
}

build_variant unpatched
build_variant patched
( cd "$OUT" && find . -type f ! -name SHA256SUMS ! -name RESULT | sort | xargs sha256sum ) > "$OUT/SHA256SUMS"
echo PASS > "$OUT/RESULT"
log "PASS"
