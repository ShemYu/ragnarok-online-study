# T10.010.003/.004 guest library, sourced by guest_build.sh and by host tests.
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
    # Every step child gets a valid fd0 on /dev/null (T10.010.004): with fd0
    # closed, Root's actual APK trigger launch failed (fchdir ENOTDIR, child 127);
    # with fd0 on /dev/null the same reinstall and trigger succeeded.
    _name=$1; shift
    log "begin $_name"
    if ! timeout "$STEP_TIMEOUT" "$@" < /dev/null > "$OUT/logs/$_name.log" 2>&1; then
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

# ---------------------------------------------------------------- T10.010.004
# Exact-base dependency transaction with authenticated, retained package bytes.
# Production values are literal in guest_build.sh; host tests point them at
# fixtures (and a modelled APK command):
#   APK           package tool ("apk"); EXPECT_ARCH  aarch64
#   APK_KEYS_DIR  the image's unchanged stock trusted keys (/etc/apk/keys)
#   APK_DB        installed database (/lib/apk/db/installed)
#   STAGE         owned staging directory (/work/closure); IN, OUT, WANT
# Never used: --allow-untrusted, --keys-dir, --no-scripts, --force-*, --arch,
# imported keys or repository-base upgrades.

sha_of() { sha256sum "$1" | cut -d' ' -f1; }
size_of() { wc -c < "$1" | tr -d ' '; }

# check_local_list <list>: "<index> <sha256> <bytes> <name> <version> <Q1>"
# lines, indices 0..n-1 in order, unique names. Q1 is the host-derived control
# identity (apk_identity), joined to the installed database after install. Indices name generated upload files
# ($IN/local-<index>.apk); no caller string is ever used as a path.
check_local_list() {
    _n=0
    while IFS=' ' read -r _i _sha _bytes _nm _v _q1 _extra; do
        [ -z "$_extra" ] && [ "$_i" = "$_n" ] || die "local list line $_n malformed"
        case "$_q1" in Q1*=) ;; *) die "local list $_n identity digest" ;; esac
        case "${_q1#Q1}" in *[!A-Za-z0-9+/=]*) die "local list $_n identity digest" ;; esac
        [ "${#_q1}" = 30 ] || die "local list $_n identity digest length"
        case "$_sha" in *[!0-9a-f]*|'') die "local list $_n sha256" ;; esac
        [ "${#_sha}" = 64 ] || die "local list $_n sha256 length"
        is_uint "$_bytes" && [ "$_bytes" -gt 0 ] || die "local list $_n bytes"
        case "$_nm=$_v" in *[!A-Za-z0-9._+~=-]*|=*|*=|*=*=*) die "local list $_n identity" ;; esac
        _n=$((_n + 1))
    done < "$1"
    [ -z "$(cut -d' ' -f4 "$1" | LC_ALL=C sort | uniq -d)" ] || die "local list has duplicate names"
}

apk_keys_digest() { # stable listing of every stock trusted-key entry and its hash
    [ -d "$APK_KEYS_DIR" ] && [ ! -L "$APK_KEYS_DIR" ] || die "trusted keys dir missing"
    ( cd "$APK_KEYS_DIR" && find . ! -type d -exec sha256sum {} + ) | LC_ALL=C sort -k2
}

pkginfo_field() { # pkginfo_field <.PKGINFO> <key>: exactly one "key = value"
    awk -v k="$2" '$1 == k && $2 == "=" && NF == 3 { n++; v = $3 } END { if (n != 1) exit 1; print v }' "$1"
}

# verify_apk <file> <sha256> <bytes> <name> <version> <tag>: recheck bytes,
# authenticate with the stock keys (real apk verify), then require the signed
# control segment's pkgname/pkgver/arch to be exactly the expected identity.
verify_apk() {
    _vf=$1; _vt=$6
    [ -f "$_vf" ] && [ ! -L "$_vf" ] || die "apk $_vt is not a regular file"
    [ "$(size_of "$_vf")" = "$3" ] || die "apk $_vt size changed"
    [ "$(sha_of "$_vf")" = "$2" ] || die "apk $_vt sha256 changed"
    step "apk-verify-$_vt" "$APK" --no-network verify "$_vf"
    grep -qw OK "$OUT/logs/apk-verify-$_vt.log" || die "apk verify $_vt reported no OK"
    tar -xzOf "$_vf" .PKGINFO > "$STAGE/$_vt.pkginfo" 2> /dev/null || die "apk $_vt has no .PKGINFO"
    _pn=$(pkginfo_field "$STAGE/$_vt.pkginfo" pkgname) || die "apk $_vt pkgname"
    _pv=$(pkginfo_field "$STAGE/$_vt.pkginfo" pkgver) || die "apk $_vt pkgver"
    _pa=$(pkginfo_field "$STAGE/$_vt.pkginfo" arch) || die "apk $_vt arch"
    [ "$_pn=$_pv" = "$4=$5" ] || die "apk $_vt identity $_pn=$_pv is not $4=$5"
    [ "$_pa" = "$EXPECT_ARCH" ] || die "apk $_vt arch $_pa"
    printf '%s %s %s %s %s OK\n' "$_vt" "$2" "$_pn" "$_pv" "$_pa" >> "$OUT/apk-verify.txt"
}

# parse_simulate <log> <out>: the solver's plan must consist only of
# "(i/n) Installing <name> (<version>)" rows. apk-tools 3.0.8 pads the
# counter to the width of n -- actual: "( 1/47) Installing jansson (2.14.1-r0)"
# -- so a counter is accepted unpadded or space-padded to exactly n's width.
# Every line that starts with "(" (after optional whitespace) or names a
# transaction action is a
# transaction row and must parse completely: counters 1..n in order with one
# constant n, a valid name and "(version)", unique names, and exactly n rows.
# Any upgrade/downgrade/reinstall/replace/purge/remove/unknown action or
# malformed row refuses before anything is fetched or installed; no
# transaction-shaped line is ever dropped silently.
parse_simulate() {
    awk -v bad="$OUT/apk-simulate.refused" '
        function refuse(why) { print why ": " $0 > bad; refused = 1 }
        # A "(" after leading whitespace is still transaction-shaped; apk never
        # indents its rows, so the strict grammar below refuses it.
        /^[[:space:]]+\(/ { refuse("indented transaction row"); next }
        /^\(/ {
            if (!match($0, /^\( *[0-9]+\/[0-9]+\) /)) { refuse("malformed counter"); next }
            head = substr($0, 2, RLENGTH - 3); rest = substr($0, RLENGTH + 1)
            split(head, c, "/"); lead = c[1]; tot = c[2]; idx = lead; sub(/^ +/, "", idx)
            if (idx !~ /^[1-9][0-9]*$/ || tot !~ /^[1-9][0-9]*$/) { refuse("bad counter"); next }
            if (length(lead) != length(idx) && length(lead) != length(tot)) { refuse("bad counter padding"); next }
            if (total == "") total = tot
            if (tot != total) { refuse("changing transaction total"); next }
            rows++
            if (idx + 0 != rows) { refuse("out-of-order counter"); next }
            if (split(rest, w, " ") != 3 || rest != w[1] " " w[2] " " w[3]) { refuse("malformed row"); next }
            if (w[1] != "Installing") { refuse("forbidden or unknown action"); next }
            if (w[2] !~ /^[A-Za-z0-9][A-Za-z0-9._+-]*$/) { refuse("bad package name"); next }
            if (w[3] !~ /^\([0-9][A-Za-z0-9._+~-]*-r[0-9]+\)$/) { refuse("bad package version"); next }
            if (w[2] in seen) { refuse("duplicate package"); next }
            seen[w[2]] = 1
            print w[2] "=" substr(w[3], 2, length(w[3]) - 2); next }
        /(Installing|Upgrading|Downgrading|Reinstalling|Replacing|Purging|Removing|Deleting)/ { refuse("uncounted transaction"); next }
        END {
            if (rows != total + 0) { $0 = rows " of " total; refuse("row count differs from the transaction total") }
            exit refused ? 3 : 0 }' "$1" > "$2.unsorted" || die "solver plan refused (changes existing packages or malformed): $(tr '\n' ' ' < "$OUT/apk-simulate.refused")"
    LC_ALL=C sort "$2.unsorted" > "$2"
    rm -f "$2.unsorted"
}

# deps_transaction <base> <local-list> <lock|""> <offline 0|1>
#   1. local inputs: size/hash recheck, stock-key signature, signed identity
#   2. solver constraints = EVERY exact frozen base pin + WANT (libunwind-dev~1.8.1)
#      + exact delta pins (build) + the authenticated local files
#   3. simulate; refuse any non-install; delta must equal the lock (build)
#   4. repository additions: fetch exact pins to generated paths, authenticate
#   5. one transaction from exactly the authenticated files, no package network,
#      scripts/triggers and signature checking left enabled
#   6. installed delta == solver delta, base unchanged, trusted keys unchanged
# Requires $OUT/apk-before.txt. Writes apk-closure.txt (name=version sha256
# bytes file source), apk-verify.txt, apk-installed-identity.txt.
deps_transaction() {
    _base=$1; _local=$2; _lock=$3; _offline=$4
    rm -rf "$STAGE"; mkdir -p "$STAGE"
    : > "$OUT/apk-verify.txt"; : > "$STAGE/local.src"; : > "$STAGE/repo.src"
    apk_keys_digest > "$OUT/apk-keys-before.txt"
    [ -s "$OUT/apk-keys-before.txt" ] || die "no stock trusted keys"
    cut -d= -f1 "$_base" | LC_ALL=C sort > "$STAGE/base.names"
    _files=""
    : > "$STAGE/local.q1"
    while IFS=' ' read -r _i _sha _bytes _nm _v _q1; do
        ! grep -qx -- "$_nm" "$STAGE/base.names" || die "local input $_nm would replace a frozen base package"
        printf '%s=%s %s\n' "$_nm" "$_v" "$_q1" >> "$STAGE/local.q1"
        verify_apk "$IN/local-$_i.apk" "$_sha" "$_bytes" "$_nm" "$_v" "local-$_i"
        printf '%s=%s %s %s local-%s.apk local\n' "$_nm" "$_v" "$_sha" "$_bytes" "$_i" >> "$STAGE/local.src"
        _files="$_files $IN/local-$_i.apk"
    done < "$_local"
    { cat "$_base"
      printf '%s\n' $WANT | sed 's/^libunwind-dev$/libunwind-dev~1.8.1/'
      if [ -n "$_lock" ]; then cat "$_lock"; fi; } > "$OUT/apk-constraints.txt"
    if [ "$_offline" = 1 ]; then
        _net="--no-network --no-cache --repositories-file /dev/null"
    else
        _net="--no-cache"
    fi
    # shellcheck disable=SC2046,SC2086  # validated name=version tokens and generated paths only
    step apk-simulate "$APK" add --simulate $_net $(cat "$OUT/apk-constraints.txt") $_files
    parse_simulate "$OUT/logs/apk-simulate.log" "$OUT/apk-simulate.delta"
    check_lock_file "$OUT/apk-simulate.delta" empty-ok
    if [ -n "$_lock" ]; then
        cmp -s "$OUT/apk-simulate.delta" "$_lock" || die "solver delta differs from the qualified lock"
    fi
    check_coverage "$_base" "$OUT/apk-simulate.delta" $WANT
    while IFS=' ' read -r _nv _rest; do  # a file loop, not a pipeline: die must end the guest
        grep -qxF -- "$_nv" "$OUT/apk-simulate.delta" || die "local input $_nv is not in the solver delta"
    done < "$STAGE/local.src"
    _k=0
    while IFS= read -r _nv; do
        if awk -v nv="$_nv" '$1 == nv { f = 1 } END { exit !f }' "$STAGE/local.src"; then continue; fi
        [ "$_offline" = 0 ] || die "offline closure lacks $_nv"
        _d="$STAGE/fetch-$_k"; mkdir "$_d"
        step "apk-fetch-$_k" "$APK" fetch --no-cache --output "$_d" "$_nv"
        [ "$(find "$_d" ! -type d | wc -l | tr -d ' ')" = 1 ] || die "fetch $_nv did not yield exactly one file"
        _ff=$(find "$_d" -type f -name '*.apk')
        [ -n "$_ff" ] && [ ! -L "$_ff" ] || die "fetch $_nv is not one regular .apk"
        mv "$_ff" "$STAGE/repo-$_k.apk"
        rmdir "$_d"
        _sha=$(sha_of "$STAGE/repo-$_k.apk"); _bytes=$(size_of "$STAGE/repo-$_k.apk")
        verify_apk "$STAGE/repo-$_k.apk" "$_sha" "$_bytes" "${_nv%%=*}" "${_nv#*=}" "repo-$_k"
        printf '%s %s %s repo-%s.apk repo\n' "$_nv" "$_sha" "$_bytes" "$_k" >> "$STAGE/repo.src"
        _files="$_files $STAGE/repo-$_k.apk"
        _k=$((_k + 1))
    done < "$OUT/apk-simulate.delta"
    cat "$STAGE/local.src" "$STAGE/repo.src" | LC_ALL=C sort > "$OUT/apk-closure.txt"
    cut -d' ' -f1 "$OUT/apk-closure.txt" | cmp -s - "$OUT/apk-simulate.delta" || die "closure differs from the solver delta"
    # shellcheck disable=SC2046,SC2086
    step apk-add "$APK" add --no-network --no-cache --repositories-file /dev/null \
        $(cat "$OUT/apk-constraints.txt") $_files
    "$APK" info -v 2> /dev/null | LC_ALL=C sort > "$OUT/apk-after.txt"
    "$APK" info 2> /dev/null | LC_ALL=C sort > "$OUT/apk-names-after.txt"
    check_deps "$OUT/apk-before.txt" "$OUT/apk-after.txt" "$OUT/apk-simulate.delta"
    apk_keys_digest > "$OUT/apk-keys-after.txt"
    cmp -s "$OUT/apk-keys-before.txt" "$OUT/apk-keys-after.txt" || die "stock trusted keys changed"
    # Installed-database records are blank-line separated; C: (identity) may precede P:/V:.
    awk 'function flush() { if ((p "=" v) in want && c != "") print p "=" v, c; p = v = c = "" }
         FILENAME == ARGV[1] { want[$1] = 1; next }
         /^$/ { flush(); next }
         /^P:/ { p = substr($0, 3) } /^V:/ { v = substr($0, 3) } /^C:/ { c = substr($0, 3) }
         END { flush() }' "$OUT/apk-simulate.delta" "$APK_DB" | LC_ALL=C sort > "$OUT/apk-installed-identity.txt"
    cut -d' ' -f1 "$OUT/apk-installed-identity.txt" | cmp -s - "$OUT/apk-simulate.delta" \
        || die "installed database identities do not cover the delta exactly once"
    # planned local inputs: the installed C: must be the host-derived control identity
    while IFS=' ' read -r _nv _q1; do
        grep -qxF -- "$_nv $_q1" "$OUT/apk-installed-identity.txt" || die "installed identity of $_nv is not its planned control identity"
    done < "$STAGE/local.q1"
}

# retain_closure <all|repo>: copy authenticated delta files into the export
# with their generated names and recheck each hash. "all" (resolve) also
# writes MANIFEST.json in the documented local-input format (usable as plan
# --apk-local for an offline build); "repo" (build) retains only fetched
# repository files -- planned local bytes are joined from the plan's upload.
retain_closure() {
    _scope=${1:-all}
    mkdir -p "$OUT/apk-closure"
    _first=1
    { printf '{"schema": "t10.010.004/apk-local/v1", "packages": ['
      while IFS=' ' read -r _nv _sha _bytes _file _src; do
          case "$_src" in local) _from="$IN/$_file" ;; repo) _from="$STAGE/$_file" ;; *) die "closure source $_src" ;; esac
          [ "$_scope" = all ] || [ "$_src" = repo ] || continue
          cp "$_from" "$OUT/apk-closure/$_file"
          [ "$(sha_of "$OUT/apk-closure/$_file")" = "$_sha" ] || die "retained $_file hash"
          [ "$_first" = 1 ] || printf ', '
          _first=0
          printf '{"file": "%s", "name": "%s", "version": "%s", "bytes": %s, "sha256": "%s"}' \
              "$_file" "${_nv%%=*}" "${_nv#*=}" "$_bytes" "$_sha"
      done < "$OUT/apk-closure.txt"
      printf ']}\n'; } > "$STAGE/MANIFEST.json"
    if [ "$_scope" = all ]; then mv "$STAGE/MANIFEST.json" "$OUT/apk-closure/MANIFEST.json"; else rm -f "$STAGE/MANIFEST.json"; fi
}

# finalize: the last log line precedes the immutable checksums; nothing is
# written after SHA256SUMS except RESULT (excluded from scope, read by value).
finalize() {
    log "PASS"
    ( cd "$OUT" && find . -type f ! -name 'SHA256SUMS*' ! -name RESULT | LC_ALL=C sort | xargs sha256sum ) > "$OUT/SHA256SUMS.tmp"
    mv "$OUT/SHA256SUMS.tmp" "$OUT/SHA256SUMS"
    echo PASS > "$OUT/RESULT"
}
