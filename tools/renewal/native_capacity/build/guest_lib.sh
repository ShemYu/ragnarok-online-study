# T10.010.003 guest library, sourced by guest_build.sh and by host tests.
# POSIX sh (busybox ash compatible). Every check fails closed.
#
# Paths are parameters only so host tests can point them at fixtures;
# guest_build.sh sets them to the literal production paths, ignoring inputs.

log() {
    printf '%s %s\n' "$(date -u +%H:%M:%S)" "$*" >&2
    printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" >> "$OUT/logs/steps.log"
}

die() {
    printf '%s %s\n' "$(date -u +%H:%M:%S)" "FAIL $*" >&2
    printf 'FAIL %s\n' "$*" > "$OUT/RESULT"
    exit 1
}

step() { # step <name> <cmd...>: bounded by STEP_TIMEOUT, logged; nonzero/timeout fails
    _name=$1; shift
    log "begin $_name"
    if ! timeout "$STEP_TIMEOUT" "$@" > "$OUT/logs/$_name.log" 2>&1; then
        tail -n 40 "$OUT/logs/$_name.log" >&2 || true
        die "$_name"
    fi
    log "end $_name"
}

is_uint() { case "$1" in ''|*[!0-9]*) return 1 ;; *) return 0 ;; esac; }

# check_cgroup: own kernel cgroup ID, read-only cgroup2 view, and positive
# per-ID limits equal to the plan, BEFORE any dependency install or build.
#   CG_SELF   file with this process's cgroup (production /proc/self/cgroup)
#   CG_MOUNTS mountinfo (production /proc/self/mountinfo)
#   CG_VIEW   read-only bind of the Engine's cgroup root (/run/root-cgroup-view)
# Inputs: CONTAINER_ID, EXPECT_MEMORY_MAX, EXPECT_SWAP_MAX, EXPECT_CPU_MAX
# ("<quota> <period>"), EXPECT_PIDS_MAX. Writes $OUT/cgroup.txt.
check_cgroup() {
    : "${CONTAINER_ID:?}" "${EXPECT_MEMORY_MAX:?}" "${EXPECT_SWAP_MAX:?}" "${EXPECT_CPU_MAX:?}" "${EXPECT_PIDS_MAX:?}"
    [ "$(wc -l < "$CG_SELF" | tr -d ' ')" = 1 ] || die "cgroup: not exactly one cgroup2 membership line"
    _line=$(cat "$CG_SELF")
    case "$_line" in 0::/slim/*) ;; *) die "cgroup: unexpected membership '$_line'" ;; esac
    _id=${_line#0::/slim/}
    case "$_id" in ''|*/*|*[!0-9a-f]*) die "cgroup: bad own ID '$_id'" ;; esac
    [ "$_id" = "$CONTAINER_ID" ] || die "cgroup: own ID $_id is not container $CONTAINER_ID"
    # mountinfo: id parent major:minor root mountpoint options ... - fstype source superopts
    _mi=$(awk -v mp="$CG_VIEW" '$5 == mp' "$CG_MOUNTS")
    [ -n "$_mi" ] || die "cgroup: no mount at $CG_VIEW"
    [ "$(printf '%s\n' "$_mi" | wc -l | tr -d ' ')" = 1 ] || die "cgroup: stacked mounts at $CG_VIEW"
    _opts=$(printf '%s\n' "$_mi" | awk '{print $6}')
    _fstype=$(printf '%s\n' "$_mi" | awk '{for (i = 7; i <= NF; i++) if ($i == "-") {print $(i + 1); exit}}')
    [ "$_fstype" = cgroup2 ] || die "cgroup: $CG_VIEW is '$_fstype', not cgroup2"
    case ",$_opts," in *,ro,*) ;; *) die "cgroup: $CG_VIEW is not read-only ($_opts)" ;; esac
    _dir="$CG_VIEW/$_id"
    [ -d "$_dir" ] || die "cgroup: own directory missing"
    : > "$OUT/cgroup.txt"
    for _pair in "memory.max:$EXPECT_MEMORY_MAX" "memory.swap.max:$EXPECT_SWAP_MAX" \
                 "cpu.max:$EXPECT_CPU_MAX" "pids.max:$EXPECT_PIDS_MAX"; do
        _leaf=${_pair%%:*}; _want=${_pair#*:}
        [ -r "$_dir/$_leaf" ] || die "cgroup: $_leaf unreadable"
        _got=$(cat "$_dir/$_leaf")
        printf '%s=%s\n' "$_leaf" "$_got" >> "$OUT/cgroup.txt"
        [ "$_got" = "$_want" ] || die "cgroup: $_leaf is '$_got', want '$_want'"
    done
    for _v in "$EXPECT_MEMORY_MAX" "$EXPECT_SWAP_MAX" "$EXPECT_PIDS_MAX" "${EXPECT_CPU_MAX%% *}"; do
        is_uint "$_v" && [ "$_v" -gt 0 ] || die "cgroup: expected limit '$_v' is not positive"
    done
    printf 'id=%s\nmount=%s\n' "$_id" "$_mi" >> "$OUT/cgroup.txt"
}

# check_lock_file <lock> <nonempty|empty-ok>: lines "name=version", sorted, unique.
check_lock_file() {
    if [ ! -s "$1" ]; then
        [ "$2" = empty-ok ] || die "dependency list $1 empty"
        return 0
    fi
    while IFS= read -r _l; do
        case "$_l" in *[!A-Za-z0-9._+~=-]*|=*|*=|*=*=*) die "dependency line '$_l'" ;; *=*) ;; *) die "dependency line '$_l'" ;; esac
    done < "$1"
    LC_ALL=C sort -u "$1" | cmp -s - "$1" || die "dependency list $1 not sorted/unique"
}

# check_coverage <base> <delta> <want...>: every wanted name is in exactly one
# of base/delta, delta re-pins no base package, libunwind-dev is 1.8.1.
check_coverage() {
    _b=$1; _d=$2; shift 2
    cut -d= -f1 "$_b" | LC_ALL=C sort > "$OUT/names-base.txt"
    cut -d= -f1 "$_d" | LC_ALL=C sort > "$OUT/names-delta.txt"
    [ -z "$(LC_ALL=C comm -12 "$OUT/names-base.txt" "$OUT/names-delta.txt")" ] || die "delta re-pins base packages"
    for _w in "$@"; do
        grep -qx -- "$_w" "$OUT/names-base.txt" || grep -qx -- "$_w" "$OUT/names-delta.txt" || die "required $_w in neither base nor delta"
    done
    cat "$_b" "$_d" | grep -q '^libunwind-dev=1\.8\.1-' || die "libunwind-dev is not ~1.8.1"
}

# check_deps <before> <after> <delta>: the packages added by the install are
# EXACTLY the delta, and no base package was upgraded, downgraded or removed.
check_deps() {
    _before=$1; _after=$2; _lock=$3
    sed 's/=/-/' "$_lock" | LC_ALL=C sort > "$OUT/deps-locked.txt"
    LC_ALL=C comm -13 "$_before" "$_after" > "$OUT/deps-added.txt"
    LC_ALL=C comm -23 "$_before" "$_after" > "$OUT/deps-removed.txt"
    [ ! -s "$OUT/deps-removed.txt" ] || die "dependency install changed preinstalled packages: $(tr '\n' ' ' < "$OUT/deps-removed.txt")"
    cmp -s "$OUT/deps-added.txt" "$OUT/deps-locked.txt" || die "installed closure differs from the lock"
}

# lock_candidate <names-before> <names-after> <versions-after>: for each
# added package name, its exact installed "name-<digit>..." entry -> name=version.
lock_candidate() {
    LC_ALL=C comm -13 "$1" "$2" | while IFS= read -r _n; do
        # exact "name-" prefix followed by a digit; no regex built from the name
        _pv=$(awk -v n="$_n" 'index($0, n "-") == 1 && substr($0, length(n) + 2, 1) ~ /[0-9]/' "$3")
        _hits=$(printf '%s' "$_pv" | grep -c . || true)
        [ "$_hits" = 1 ] || die "lock candidate: $_n has $_hits version entries"
        printf '%s=%s\n' "$_n" "${_pv#"$_n"-}"
    done
}

# finalize: the last log line precedes the immutable checksums; nothing is
# written after SHA256SUMS except RESULT (excluded from scope, read by value).
finalize() {
    log "PASS"
    ( cd "$OUT" && find . -type f ! -name 'SHA256SUMS*' ! -name RESULT | LC_ALL=C sort | xargs sha256sum ) > "$OUT/SHA256SUMS.tmp"
    mv "$OUT/SHA256SUMS.tmp" "$OUT/SHA256SUMS"
    echo PASS > "$OUT/RESULT"
}
