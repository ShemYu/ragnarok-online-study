# Independent item-table round-trip verifier

Coordinator verification for T04.003, independent of both converter candidates.
This directory contains authored verification source only. Private game tables,
copied upstream JS/WASM, generated candidate tables and reports stay ignored.

Prepare a new private fixture from the pinned local client Git object and modern
item table. No network or package install is used:

```sh
python3 tools/verification/renewal-item-roundtrip/prepare.py \
  --client-source .tools/renewal/client-source \
  --item-table .tools/renewal/assets/tw-20260409/app/System/iteminfo_new.lub \
  --output .tools/renewal/roundtrip-verified
python3 -m http.server 3350 --bind 127.0.0.1 \
  --directory .tools/renewal/roundtrip-verified
```

Use supported browser UI to open the loopback fixture. Supply a reviewed generated
source file, or copy it into the ignored fixture and enter its same-origin URL.
Enter its expected SHA-256, then press **Compare full tables**. No comparison runs
on page load. The original, JS and WASM hashes are checked before Lua evaluation;
the source must strictly decode as UTF-8. Only trusted reviewed source belongs in
this verifier: it executes Lua and is not a hostile-code sandbox.

The pinned Lua 5.1 runtime loads/compiles the original and generated tables in
separate states. Lua enumerates the actual `tbl`; strings become raw-byte hex,
numeric/string/boolean key types stay distinct, finite numbers retain 17 digits
and signed-zero values, and nested tables expand by value. Nil means absence;
cycles, metatables and unsupported values fail. Complete canonical strings and
each root record are compared directly; SHA-256 is supplementary. Noncyclic alias
identity is outside this value-comparison scope.

Self-checks assert known Unicode/NUL/type/sparse/zero tokens, reordered equality,
nil deletion, a detected boolean difference and rejection of cycles/nonfinite
values/table keys. For a negative control, supply `tbl={}` and confirm all 20442
original IDs are missing. Current original canonical SHA-256 is
`472f9cacc13051e3160f71de577e578adae7ffc30a2354d24ea1a1e6acd31d71`.

The unchanged upstream module imports lodash; a local adapter implements its two
used methods. No JS table/object is passed across that bridge. Source-only
verification does not prove mod staging, resource-path conversion or game
rendering; the coordinator must check those separately in the actual app.

See [implementation review](../../../docs/project/reviews/2026-10-18-T04.003.md).
