#!/usr/bin/env python3
"""Provisional version/content coverage ledger (T06.005.001).

Reads only the exact metadata inputs named by an explicit pin file, resolved
against an explicit root. Nothing is discovered implicitly: no default root,
no directory walk, no raw JSONL stream and no embedded path/pointer is ever
followed. Every input is hashed before and after reading; any drift refuses.

The ledger joins all gap roots of the frozen T07.007.014 profile with the
already qualified T06/T07 inventory manifests and states, for each fact, one
state from STATES plus an explicit evidence level and version scope.
Metadata-only inputs can never yield ``loaded`` or ``verified`` facts, and no
gap root is ever closed by name/parser witnesses.

Usage::

    python3 -I -B tools/renewal/coverage_ledger.py generate \
        --inputs docs/project/fixtures/T06.005.001-inputs.json \
        --root <canonical root> --out <ledger.json> [--receipt <file>]
    python3 -I -B tools/renewal/coverage_ledger.py check \
        --inputs ... --root ... --ledger docs/project/fixtures/T06.005.001-ledger.json
    python3 -I -B tools/renewal/coverage_ledger.py validate --ledger <ledger.json>

Exit status: 0 success, 2 refusal (code printed on stderr), 64 usage.
"""

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import time

SCHEMA = "renewal-provisional-coverage-ledger-v1"
INPUTS_SCHEMA = "renewal-provisional-coverage-inputs-v1"
TOOL_VERSION = "1.1.0"

STATES = ("expected", "present", "effective", "loaded", "exercised",
          "verified", "missing", "unknown")
EVIDENCE_LEVELS = (
    "qualified_inventory_manifest",   # Root-qualified source-profile manifest summary
    "qualified_metadata_join",        # Root-qualified 82-root gap join / profile
    "prior_observed_request",         # historical runtime HTTP observation in a qualified report
    "name_witness_metadata_only",     # stored-name match in a catalog; no body/load/render
    "documented_not_admitted",        # project documentation only; not a pinned input
    "name_convention_only",           # derived from a map name pattern; classification hint
    "not_observed",                   # no admitted evidence at all
    "runtime_load_observation",       # reserved; no admitted input provides it
    "root_verified_runtime",          # reserved; no admitted input provides it
    "user_accepted",                  # reserved; no admitted input provides it
    "full_content_oracle",            # reserved; an authoritative full-content denominator
)
RESERVED_LEVELS = {"runtime_load_observation", "root_verified_runtime", "user_accepted",
                   "full_content_oracle"}
# States that need runtime-level evidence; metadata inputs cannot supply it.
PROMOTION_RULES = {
    "loaded": {"runtime_load_observation", "root_verified_runtime", "user_accepted"},
    "verified": {"root_verified_runtime", "user_accepted"},
    "effective": {"runtime_load_observation", "root_verified_runtime", "user_accepted"},
    # A full-content denominator needs an authoritative oracle, never metadata.
    "expected": {"full_content_oracle"},
    # Exercise needs an actual observation (historical request or documented play).
    "exercised": {"prior_observed_request", "documented_not_admitted",
                  "runtime_load_observation", "root_verified_runtime", "user_accepted"},
}
# Denominators no admitted input defines; they must stay unknown/null/unsourced.
DENOMINATOR_FACTS = ("maps.full_game_denominator", "monsters.full_game_denominator",
                     "story.full_chain_denominator", "instances.denominator")
# Every category must carry exactly these fact IDs (no silent removal or addition).
REQUIRED_FACTS = {
    "maps_warps": ("maps.full_game_denominator", "maps.server_cache_entries",
                   "maps.stock_configured", "maps.source_profile_retained", "maps.cache_only",
                   "maps.runtime_loaded", "maps.client_rsw_404_gap_roots",
                   "maps.gap_roots_configured", "maps.gap_roots_cache_only",
                   "maps.exercised_tour", "warps.count"),
    "monsters_spawns": ("monsters.full_game_denominator", "monsters.mob_db_raw_declarations",
                        "monsters.distinct_declared_ids", "monsters.effective_table",
                        "spawns.framing_events", "spawns.static_supported", "spawns.static_gap",
                        "spawns.opaque", "spawns.uncertified_suffix", "spawns.not_static",
                        "spawns.unparsed_suffix_bytes", "spawns.effective_population"),
    "items_skills": ("items.item_db_raw_rows", "skills.skill_db_raw_rows",
                     "items_skills.yaml_edges_skipped", "items_skills.effective",
                     "items_skills.client_tables"),
    "npcs": ("npcs.stock_selected_sources", "npcs.installed_selected_sources",
             "npcs.entities", "npcs.loaded"),
    "story_quests": ("story.full_chain_denominator", "quests.quest_db_raw_rows",
                     "story.quoted_text_occurrences", "story.chapter1_family_gap_roots",
                     "story.chains_implemented", "story.party_gates"),
    "instances": ("instances.denominator", "instances.gap_root_name_candidates",
                  "instances.party_gates"),
    "dynamic_dependencies": ("dynamic.rsw_embedded_gnd_gat", "dynamic.model_texture_dependencies",
                             "dynamic.computed_map_names", "dynamic.archive_priority",
                             "dynamic.overlay_effects"),
}
METADATA_ROLES = {"qualified_metadata_only"}
SCOPES = ("server", "client", "overlay", "cross")
CATEGORIES = ("maps_warps", "monsters_spawns", "items_skills", "npcs",
              "story_quests", "instances", "dynamic_dependencies")
MAX_INPUT_BYTES = 16 * 1024 * 1024

# Documented (not admitted) Chapter 1 family names, from
# docs/project/reviews/2026-10-22-T07.007.014.004.md (ch1_* / 1@ch1* plus these).
# Similar names such as ch1zero*/ch1fild1 are deliberately left unclassified.
CH1_DOCUMENTED_EXTRA = ("ygg_edge", "ygg_fruit", "ygg_roots", "mu_fild01")
INSTANCE_NAME = re.compile(r"^[0-9]@")

ROLE_KEYS = {
    "profile": "T07.007.014-profile.json",
    "gaps": "t06-map-gap-plans-1/gaps.json",
    "corrected": "root-metadata-2/report.json",
    "join": "actual-g-1/gap-join.json",
    "snapshot": "snapshot-manifest.json",
    "selection": "selection-manifest.json",
    "map_cache": "map-cache-manifest.json",
    "yaml": "yaml-graph-manifest.json",
    "monster": "monster-projection-manifest.json",
    "spawn": "static-spawn-references-manifest.json",
    "quoted": "quoted-manifest.json",
}


class Refusal(Exception):
    def __init__(self, code, detail):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def need(cond, code, detail):
    if not cond:
        raise Refusal(code, detail)


# --------------------------------------------------------------------- inputs

def _read_pinned(root, entry):
    rel = entry.get("path")
    need(isinstance(rel, str) and rel and not rel.startswith("/")
         and ".." not in rel.split("/"), "INPUT_PATH", f"unsafe input path {rel!r}")
    path = os.path.join(root, rel)
    try:
        st = os.lstat(path)
    except OSError as error:
        raise Refusal("PIN_MISSING", f"{rel}: {error.strerror}")
    need(stat.S_ISREG(st.st_mode), "PIN_NOT_REGULAR", f"{rel} is not a regular file")
    need(st.st_size <= MAX_INPUT_BYTES, "INPUT_LIMIT", f"{rel} exceeds {MAX_INPUT_BYTES} bytes")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        chunks = []
        while True:
            chunk = os.read(fd, 1 << 20)
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        os.close(fd)
    data = b"".join(chunks)
    digest = hashlib.sha256(data).hexdigest()
    need(len(data) == entry.get("bytes") and digest == entry.get("sha256"), "PIN_DRIFT",
         f"{rel}: expected {entry.get('bytes')} B/{entry.get('sha256')}, "
         f"observed {len(data)} B/{digest}")
    return data, digest


def _role_of(rel):
    for role, suffix in ROLE_KEYS.items():
        if rel.endswith(suffix):
            return role
    raise Refusal("INPUT_ROLE", f"no ledger role for admitted input {rel}")


def load_inputs(pins_path, root):
    need(root is not None and os.path.isabs(root), "EXPLICIT_ROOT_REQUIRED",
         "--root must be an explicit absolute directory")
    need(os.path.isdir(root), "EXPLICIT_ROOT_REQUIRED", "--root is not a directory")
    with open(pins_path, "rb") as handle:
        pins = json.loads(handle.read())
    need(pins.get("schema") == INPUTS_SCHEMA, "INPUT_SHAPE", "unexpected pin schema")
    entries = pins.get("inputs")
    need(isinstance(entries, list) and entries, "INPUT_SHAPE", "pin list empty")
    seen, docs, admitted = set(), {}, []
    for entry in entries:
        rel = entry.get("path")
        need(rel not in seen, "INPUT_DUPLICATE", f"duplicate pinned input {rel}")
        seen.add(rel)
        need(entry.get("role") in METADATA_ROLES, "INPUT_ROLE",
             f"{rel}: role {entry.get('role')!r} not admitted")
        role = _role_of(rel)
        need(role not in docs, "INPUT_DUPLICATE", f"two inputs map to role {role}")
        data, digest = _read_pinned(root, entry)
        try:
            docs[role] = json.loads(data)
        except ValueError as error:
            raise Refusal("INPUT_SHAPE", f"{rel}: invalid JSON ({error})")
        admitted.append({"path": rel, "bytes": len(data), "sha256": digest,
                         "role": entry["role"], "ledger_role": role})
    missing = sorted(set(ROLE_KEYS) - set(docs))
    need(not missing, "INPUT_MISSING", f"required ledger roles absent: {missing}")
    return pins, docs, admitted


def recheck_inputs(root, admitted):
    for entry in admitted:
        _read_pinned(root, entry)


# ---------------------------------------------------------------- utilities

def fact(fid, state, value, unit, level, scope, source, note=None):
    out = {"id": fid, "state": state, "value": value, "unit": unit,
           "evidence_level": level, "scope": scope, "source": source}
    if note:
        out["note"] = note
    return out


def src(role_paths, role, pointer):
    return {"input": role_paths[role], "pointer": pointer} if role else \
        {"input": None, "pointer": pointer}


def _get(doc, pointer):
    cur = doc
    for part in pointer.strip("/").split("/"):
        if isinstance(cur, list):
            cur = cur[int(part)]
        else:
            need(isinstance(cur, dict) and part in cur, "INPUT_SHAPE",
                 f"missing field {pointer}")
            cur = cur[part]
    return cur


# ------------------------------------------------------- cross-input checks

def check_provenance(docs, sha):
    """Each manifest must name the exact pinned upstream manifests it consumed."""
    snap, sel, mc = sha["snapshot"], sha["selection"], sha["map_cache"]
    pairs = [
        ("selection", "/input/snapshot_manifest_sha256", snap),
        ("map_cache", "/inputs/snapshot/manifest_sha256", snap),
        ("map_cache", "/inputs/selection/selection-manifest.json/sha256", sel),
        ("yaml", "/input/snapshot_manifest_sha256", snap),
        ("monster", "/input/snapshot_manifest_sha256", snap),
        ("spawn", "/provenance/snapshot_manifest_sha256", snap),
        ("spawn", "/provenance/selection_manifest_sha256", sel),
        ("spawn", "/inputs/map~1map-cache-manifest.json/sha256", mc),
        ("spawn", "/inputs/monster~1monster-projection-manifest.json/sha256", sha["monster"]),
        ("quoted", "/inputs/snapshot_manifest/sha256", snap),
        ("quoted", "/inputs/selection_manifest/sha256", sel),
    ]
    for role, pointer, expected in pairs:
        value = _get_escaped(docs[role], pointer)
        need(value == expected, "PROVENANCE_MISMATCH",
             f"{role}{pointer} = {value!r}, pinned {expected}")
    revisions = {role: _get(docs[role], "/source/revision")
                 for role in ("selection", "map_cache", "yaml", "monster")}
    revisions["spawn"] = _get(docs["spawn"], "/provenance/rathena_revision")
    need(len(set(revisions.values())) == 1, "PROVENANCE_MISMATCH",
         f"server source revisions differ: {revisions}")
    profile_inputs = {(i["path"], i["bytes"], i["sha256"]) for i in docs["profile"]["inputs"]}
    join_inputs = {(i["path"], i["bytes"], i["sha256"]) for i in docs["join"]["inputs"]}
    need(profile_inputs == join_inputs, "PROVENANCE_MISMATCH",
         "gap-join inputs differ from the frozen profile inputs")
    profile_shas = {i["sha256"] for i in docs["profile"]["inputs"]}
    for role in ("gaps", "corrected"):
        need(sha[role] in profile_shas, "PROVENANCE_MISMATCH",
             f"profile does not pin admitted {role} input")
    return next(iter(revisions.values()))


def _get_escaped(doc, pointer):
    parts = [p.replace("~1", "/").replace("~0", "~") for p in pointer.strip("/").split("/")]
    cur = doc
    for part in parts:
        need(isinstance(cur, dict) and part in cur, "INPUT_SHAPE", f"missing field {pointer}")
        cur = cur[part]
    return cur


# --------------------------------------------------------------- gap roots

def join_roots(docs, paths):
    profile, gaps, corrected, join = docs["profile"], docs["gaps"], docs["corrected"], docs["join"]
    pgaps = profile.get("gaps")
    need(isinstance(pgaps, list) and pgaps, "INPUT_SHAPE", "profile has no gaps")
    denom = profile["denominators"]
    need(len(pgaps) == denom["gap_roots"], "COUNT_MISMATCH",
         f"profile lists {len(pgaps)} gaps, denominator {denom['gap_roots']}")
    for key in ("gap_index", "root_ordinal", "map_name"):
        values = [g.get(key) for g in pgaps]
        need(None not in values, "MISSING_ROOT_ID", f"profile gap lacks {key}")
        dup = sorted({v for v in values if values.count(v) > 1}, key=str)
        need(not dup, "DUPLICATE_ROOT_ID", f"duplicate {key}: {dup}")
    need([g["gap_index"] for g in pgaps] == list(range(len(pgaps))), "MISSING_ROOT_ID",
         "profile gap_index is not the dense original order 0..n-1")

    extract = [(i, g) for i, g in enumerate(gaps["gaps"])
               if (g.get("rsw") or {}).get("outcome") == "http_404"]
    rows = corrected["rows"]
    jroots = join["roots"]
    for label, seq in (("gap extract (http_404)", extract), ("corrected metadata", rows),
                       ("gap join", jroots)):
        need(len(seq) == len(pgaps), "MISSING_ROOT_ID" if len(seq) < len(pgaps)
             else "EXTRA_ROOT_ID", f"{label} has {len(seq)} roots, profile {len(pgaps)}")

    catalogs = profile["catalogs"]
    cat_by_index = {c["catalog_index"]: c for c in catalogs}
    cand_by_name = {}
    for k, c in enumerate(docs["map_cache"]["candidates"]):
        cand_by_name.setdefault(c["name"], []).append(k)
    entry_by_key = {}
    for ci, cache in enumerate(docs["map_cache"]["caches"]):
        for ei, entry in enumerate(cache["entries"]):
            entry_by_key.setdefault((cache["path"], entry.get("ordinal")), []).append(
                (ci, ei, entry))

    out = []
    for g in pgaps:
        i = g["gap_index"]
        ex_index, ex = extract[i]
        row, jr = rows[i], jroots[i]
        name, ordinal = g["map_name"], g["root_ordinal"]
        need(g["gap_extract_pointer"] == f"/gaps/{ex_index}", "ROOT_JOIN_MISMATCH",
             f"{name}: extract pointer {g['gap_extract_pointer']} vs /gaps/{ex_index}")
        need(g["corrected_metadata_pointer"] == f"/rows/{i}", "ROOT_JOIN_MISMATCH",
             f"{name}: corrected pointer")
        for label, other in (("extract", ex), ("corrected", row)):
            need(other["name"] == name and other["ordinal"] == ordinal
                 and other["cache_ordinal"] == g["cache_ordinal"]
                 and other["cache_file"] == g["cache_file"], "ROOT_JOIN_MISMATCH",
                 f"{name}: {label} identity differs")
        need(ex["rsw"].get("request_index") == g["rsw_request_index"], "ROOT_JOIN_MISMATCH",
             f"{name}: RSW request index differs")
        need((ex["configured"] is not None) == g["configured"] == bool(row["configured"]),
             "ROOT_JOIN_MISMATCH", f"{name}: configured flag differs")
        need(row.get("observed") == "HTTP404", "ROOT_JOIN_MISMATCH",
             f"{name}: corrected observation is not HTTP404")
        need(jr["gap"] == g, "ROOT_JOIN_MISMATCH", f"{name}: gap-join root differs from profile")

        cands = cand_by_name.get(name, [])
        need(len(cands) == (1 if g["configured"] else 0), "ROOT_JOIN_MISMATCH",
             f"{name}: {len(cands)} stock selection candidates, configured={g['configured']}")
        entries = entry_by_key.get((g["cache_file"], g["cache_ordinal"]), [])
        need(len(entries) == 1 and entries[0][2].get("name") == name, "ROOT_JOIN_MISMATCH",
             f"{name}: map cache entry {g['cache_file']}#{g['cache_ordinal']} not found once")
        ci, ei, centry = entries[0]
        cand = docs["map_cache"]["candidates"][cands[0]] if cands else None

        roles = {}
        for role in ("rsw", "gnd", "gat"):
            slot = jr["terrain"][role]
            occ = slot["full_path_occurrences"]
            basename = slot["basename_only_occurrences"]
            refs = []
            for o in occ:
                cat = cat_by_index.get(o["catalog_index"])
                need(cat is not None, "ROOT_JOIN_MISMATCH", f"{name}: unknown catalog")
                refs.append({
                    "catalog_index": o["catalog_index"], "record_ordinal": o["record_ordinal"],
                    "match": o["match"], "file_candidate": o["file_candidate"],
                    "archive_file": cat["archive_file"], "patch_index": cat["patch_index"],
                    "views": sorted({m["view"] for m in cat["memberships"]}),
                })
            roles[role] = {
                "basis": slot["basis"],
                "state": "present" if occ else "missing",
                "evidence_level": "name_witness_metadata_only",
                "full_path_occurrences": len(occ),
                "basename_only_occurrences": len(basename),
                "witnesses": refs,
            }
        views = sorted({v for r in roles.values() for w in r["witnesses"] for v in w["views"]})
        tags = {
            "chapter1_family_documented": name.startswith(("ch1_", "1@ch1"))
            or name in CH1_DOCUMENTED_EXTRA,
            "instance_name_candidate": bool(INSTANCE_NAME.match(name)),
        }
        out.append({
            "gap_index": i, "root_ordinal": ordinal, "map_name": name,
            "cache_file": g["cache_file"], "cache_ordinal": g["cache_ordinal"],
            "configured": g["configured"],
            "pointers": {
                "profile": f"/gaps/{i}",
                "gap_extract": g["gap_extract_pointer"],
                "corrected_metadata": g["corrected_metadata_pointer"],
                "original_report_not_admitted": g["original_report_pointer"],
                "gap_join": f"/roots/{i}",
                "map_cache_entry": f"/caches/{ci}/entries/{ei}",
                "map_cache_candidate": f"/candidates/{cands[0]}" if cands else None,
            },
            "server": {
                "stock_selection": fact_inline("present" if g["configured"] else "missing",
                                               "qualified_inventory_manifest"),
                "map_cache_entry": fact_inline(
                    "present" if centry.get("decode") == "ok" else "unknown",
                    "qualified_inventory_manifest"),
                "source_profile_disposition": cand["disposition"] if cand else None,
                "runtime_load": fact_inline("unknown", "not_observed"),
            },
            "client": {
                "rsw_request": dict(fact_inline("missing", "prior_observed_request"),
                                    request_index=g["rsw_request_index"], observed="HTTP404"),
                "name_counterparts": roles,
                "counterpart_views": views,
                "body_render_load": fact_inline("unknown", "not_observed"),
            },
            "tags": tags,
            "story_chain": fact_inline("unknown", "not_observed"),
            "party_gate": fact_inline("unknown", "not_observed"),
            "functional_gap": "open",
        })
    return out


def fact_inline(state, level):
    return {"state": state, "evidence_level": level}


def summarize_roots(roots, catalogs):
    per_role = {}
    for role in ("rsw", "gnd", "gat"):
        per_role[role] = {
            "occurrences": sum(r["client"]["name_counterparts"][role]["full_path_occurrences"]
                               for r in roots),
            "roots": sum(1 for r in roots
                         if r["client"]["name_counterparts"][role]["full_path_occurrences"]),
            "basename_only_occurrences": sum(
                r["client"]["name_counterparts"][role]["basename_only_occurrences"]
                for r in roots),
        }
    any_root = [r for r in roots if any(r["client"]["name_counterparts"][k]["full_path_occurrences"]
                                        for k in ("rsw", "gnd", "gat"))]
    rsw_by_catalog = {}
    for r in roots:
        for w in r["client"]["name_counterparts"]["rsw"]["witnesses"]:
            key = w["archive_file"] if w["patch_index"] is None else f"patch {w['patch_index']}"
            key += " [" + ",".join(w["views"]) + "]"
            rsw_by_catalog[key] = rsw_by_catalog.get(key, 0) + 1
    rsw_roots = per_role["rsw"]["roots"]
    return {
        "gap_roots": len(roots),
        "configured": sum(1 for r in roots if r["configured"]),
        "cache_only": sum(1 for r in roots if not r["configured"]),
        "functional_open": sum(1 for r in roots if r["functional_gap"] == "open"),
        "name_occurrences_total": sum(v["occurrences"] for v in per_role.values()),
        "roots_with_any_counterpart": len(any_root),
        "roots_without_rsw_counterpart": len(roots) - rsw_roots,
        "roots_without_any_counterpart": len(roots) - len(any_root),
        "roots_with_all_three_counterparts": sum(
            1 for r in roots if all(r["client"]["name_counterparts"][k]["full_path_occurrences"]
                                    for k in ("rsw", "gnd", "gat"))),
        "per_role": per_role,
        "rsw_witness_occurrences_by_catalog": dict(sorted(rsw_by_catalog.items())),
        "roots_with_counterpart_in_view": {
            view: sum(1 for r in roots if view in r["client"]["counterpart_views"])
            for view in sorted({m["view"] for c in catalogs for m in c["memberships"]})
        },
        "chapter1_family_documented": sum(1 for r in roots
                                          if r["tags"]["chapter1_family_documented"]),
        "instance_name_candidates": sum(1 for r in roots if r["tags"]["instance_name_candidate"]),
        "party_gate_unknown": sum(1 for r in roots if r["party_gate"]["state"] == "unknown"),
        "story_chain_unknown": sum(1 for r in roots if r["story_chain"]["state"] == "unknown"),
    }


# --------------------------------------------------------- category facts

def build_categories(docs, paths, roots):
    P, mc, sel, yg, mon, sp, q = (docs["profile"], docs["map_cache"], docs["selection"],
                                  docs["yaml"], docs["monster"], docs["spawn"], docs["quoted"])
    QI, QJ = "qualified_inventory_manifest", "qualified_metadata_join"
    D, N, U = "documented_not_admitted", "not_observed", "name_convention_only"
    S = lambda role, ptr: src(paths, role, ptr)  # noqa: E731

    # ---- reconciliation of manifest summaries (no raw stream is read)
    msum = mc["summary"]
    need(msum["cache_entries"] == P["denominators"]["world_roots"]
         == sum(c["catalogued_entries"] for c in mc["caches"]), "COUNT_MISMATCH",
         "map cache entries disagree with profile world roots / per-file entries")
    need(msum["candidates"] == sel["counts"]["map_candidates"] == len(mc["candidates"])
         == P["denominators"]["configured_world_roots"], "COUNT_MISMATCH",
         "stock configured map candidates disagree")
    need(sum(msum["dispositions"].values()) == msum["candidates"], "COUNT_MISMATCH",
         "map cache dispositions do not sum to candidates")
    c = sp["counters"]
    need(c["static_supported"] + c["static_gap"] + c["opaque"] + c["suffix"] + c["not_static"]
         == c["events"], "COUNT_MISMATCH", "static spawn event classes do not sum to events")
    rc = sp["raw_scope"]["raw_counters"]
    need(rc["static_declared"] == rc["static_supported"] + rc["static_gap"]
         and rc["static_supported"] == c["static_supported"]
         and rc["static_gap"] == c["static_gap"] and rc["framing_events"] == c["events"]
         and rc["suffix_events"] == c["suffix"] and rc["opaque_blocks"] == c["opaque"],
         "COUNT_MISMATCH", "static spawn raw counters disagree with publication counters")
    need(rc["raw_bytes"] - rc["certified_bytes"] == rc["unknown_bytes"], "COUNT_MISMATCH",
         "static spawn unknown bytes do not equal raw minus certified bytes")
    need(len(sp["raw_scope"]["sources"]) == sel["counts"]["npc_source_files"]
         == q["counts"]["sources"] == q["counts"]["complete_sources"]
         + q["counts"]["incomplete_sources"], "COUNT_MISMATCH", "NPC source counts disagree")
    dbs = yg["databases"]
    need(sum(d["raw_rows"] for d in dbs.values()) == yg["counts"]["raw_rows"], "COUNT_MISMATCH",
         "YAML database rows do not sum to raw rows")
    need(dbs["MOB_DB"]["raw_rows"] == mon["counts"]["raw_declarations"], "COUNT_MISMATCH",
         "MOB_DB rows disagree with monster projection declarations")
    need(c["monster_declaration_occurrences"] == c["static_supported"] == c["map_candidate_present"],
         "COUNT_MISMATCH", "supported spawn references disagree with map/monster joins")
    claims = sp["claims"]

    cats = {}
    cats["maps_warps"] = [
        fact("maps.full_game_denominator", "unknown", None, "maps", N, "cross", S(None, None),
             "No admitted input defines the full Modern/Renewal map set; installed subset is "
             "not used as the denominator."),
        fact("maps.server_cache_entries", "present", msum["cache_entries"], "map cache entries",
             QI, "server", S("map_cache", "/summary/cache_entries"),
             "Decoded OK in the source-profile model; not a runtime load."),
        fact("maps.stock_configured", "present", msum["candidates"], "configured map names", QI,
             "server", S("selection", "/counts/map_candidates")),
        fact("maps.source_profile_retained", "present", msum["dispositions"].get("retained", 0),
             "map candidates", QI, "server", S("map_cache", "/summary/dispositions/retained"),
             "Native-rule model disposition; status_meaning states these are not runtime loads."),
        fact("maps.cache_only", "present", msum["cache_entries"] - msum["candidates"],
             "cache entries without stock configuration", QI, "server", S(None, None),
             "Derived: maps.server_cache_entries minus maps.stock_configured."),
        fact("maps.runtime_loaded", "unknown", None, "maps", N, "server", S(None, None),
             "Current map-server load not admitted (map-cache not_checked list)."),
        fact("maps.client_rsw_404_gap_roots", "missing", len(roots), "gap roots", QJ, "client",
             S("corrected", "/rsw404_count"),
             "RSW HTTP404 observed in a prior qualified request run; functional gaps open."),
        fact("maps.gap_roots_configured", "present",
             sum(1 for r in roots if r["configured"]), "gap roots", QJ, "server",
             S("corrected", "/configured404")),
        fact("maps.gap_roots_cache_only", "present",
             sum(1 for r in roots if not r["configured"]), "gap roots", QJ, "server",
             S("corrected", "/cache_only404")),
        fact("maps.exercised_tour", "exercised", None, "maps", D, "cross", S(None, None),
             "Tested personal-play scenarios are documented; a sample tour is not counted "
             "as coverage and has no denominator here."),
        fact("warps.count", "unknown", None, "warp declarations", N, "server", S(None, None),
             "No admitted input inventories warps. The static-spawn not_static class is only "
             "whitespace/line_comment/block_comment (static_spawn_references.py NOT_STATIC). "
             "The pilot lexer accepts monster/boss_monster and bounded opaque scripts, then "
             "stops at the first other construct (unsupported_construct), leaving the rest of "
             "that source as uncertified suffix bytes. Warp declarations are not counted."),
    ]
    cats["monsters_spawns"] = [
        fact("monsters.full_game_denominator", "unknown", None, "monsters", N, "cross",
             S(None, None)),
        fact("monsters.mob_db_raw_declarations", "present", mon["counts"]["raw_declarations"],
             "raw MOB_DB declarations", QI, "server", S("monster", "/counts/raw_declarations"),
             "Declarations, not accepted/effective monsters."),
        fact("monsters.distinct_declared_ids", "present",
             mon["counts"]["distinct_supported_declared_ids"], "declared IDs", QI, "server",
             S("monster", "/counts/distinct_supported_declared_ids")),
        fact("monsters.effective_table", "unknown", None, "monsters", N, "server",
             S("monster", "/not_counts_of")),
        fact("spawns.framing_events", "present", c["events"], "events", QI, "server",
             S("spawn", "/counters/events")),
        fact("spawns.static_supported", "present", c["static_supported"], "events", QI, "server",
             S("spawn", "/counters/static_supported"),
             "Map and monster references resolve in source-profile manifests only."),
        fact("spawns.static_gap", "missing", c["static_gap"], "events", QI, "server",
             S("spawn", "/counters/static_gap")),
        fact("spawns.opaque", "unknown", c["opaque"], "events", QI, "server",
             S("spawn", "/counters/opaque")),
        fact("spawns.uncertified_suffix", "unknown", c["suffix"], "events", QI, "server",
             S("spawn", "/counters/suffix")),
        fact("spawns.not_static", "unknown", c["not_static"], "events", QI, "server",
             S("spawn", "/counters/not_static")),
        fact("spawns.unparsed_suffix_bytes", "unknown", rc["unknown_bytes"], "bytes", QI,
             "server", S("spawn", "/raw_scope/raw_counters/unknown_bytes")),
        fact("spawns.effective_population", "unknown", None, "spawns", N, "server",
             S("spawn", "/claims/effective_population"),
             f"Publication claim: {claims['effective_population']}."),
    ]
    cats["items_skills"] = [
        fact("items.item_db_raw_rows", "present", dbs["ITEM_DB"]["raw_rows"], "raw rows", QI,
             "server", S("yaml", "/databases/ITEM_DB/raw_rows"), yg["not_counts_of"]),
        fact("skills.skill_db_raw_rows", "present", dbs["SKILL_DB"]["raw_rows"], "raw rows", QI,
             "server", S("yaml", "/databases/SKILL_DB/raw_rows"), yg["not_counts_of"]),
        fact("items_skills.yaml_edges_skipped", "unknown", yg["counts"]["edges_skipped"],
             "import edges", QI, "server", S("yaml", "/counts/edges_skipped"),
             "Skipped by mode: " + json.dumps(yg["counts"]["skip_reasons"], sort_keys=True)),
        fact("items_skills.effective", "unknown", None, "items/skills", N, "server",
             S(None, None), "Native rapidyaml parity and row callbacks are not established."),
        fact("items_skills.client_tables", "unknown", None, "client tables", N, "client",
             S(None, None), "Client item/skill tables are not among the admitted inputs."),
    ]
    cats["npcs"] = [
        fact("npcs.stock_selected_sources", "present", sel["counts"]["npc_source_files"],
             "NPC source files", QI, "server", S("selection", "/counts/npc_source_files"),
             "Selected source files only; not NPC/entity counts."),
        fact("npcs.installed_selected_sources", "present", 841, "NPC source files", D,
             "server", S(None, None),
             "Installed startup selection documented in reviews/2026-10-22-T07.007.014.004.md; "
             "not an admitted input, differs from the stock 839."),
        fact("npcs.entities", "unknown", None, "NPC entities", N, "server", S(None, None)),
        fact("npcs.loaded", "unknown", None, "NPCs", N, "server", S(None, None)),
    ]
    cats["story_quests"] = [
        fact("story.full_chain_denominator", "unknown", None, "story chains", N, "cross",
             S(None, None), "No admitted story-chain inventory exists."),
        fact("quests.quest_db_raw_rows", "present", dbs["QUEST_DB"]["raw_rows"], "raw rows", QI,
             "server", S("yaml", "/databases/QUEST_DB/raw_rows"),
             "Quest declarations, not implemented/reachable quest chains."),
        fact("story.quoted_text_occurrences", "present", q["counts"]["occurrences"],
             "quoted byte occurrences", QI, "server", S("quoted", "/counts/occurrences"),
             f"Story reachability claim: {q['claims']['story_reachability']}."),
        fact("story.chapter1_family_gap_roots", "unknown",
             sum(1 for r in roots if r["tags"]["chapter1_family_documented"]), "gap roots", D,
             "cross", S(None, None),
             "Documented in-scope Chapter 1 implementation risk; zero literal ch1_ NPC "
             "references (review 014.004). Not proof of absence of every quest."),
        fact("story.chains_implemented", "unknown", None, "story chains", N, "server",
             S(None, None)),
        fact("story.party_gates", "unknown", None, "party gates", N, "cross", S(None, None),
             "No actual multi-player gate is classified; party-only work is later-phase and "
             "must be inventoried from real gates."),
    ]
    cats["instances"] = [
        fact("instances.denominator", "unknown", None, "instances", N, "cross", S(None, None),
             "No instance DB is admitted."),
        fact("instances.gap_root_name_candidates", "unknown",
             sum(1 for r in roots if r["tags"]["instance_name_candidate"]), "gap roots", U,
             "cross", S(None, None), "Names matching ^[0-9]@ only; gate/party status unknown."),
        fact("instances.party_gates", "unknown", None, "instances", N, "cross", S(None, None)),
    ]
    cats["dynamic_dependencies"] = [
        fact("dynamic.rsw_embedded_gnd_gat", "unknown", None, "filenames", N, "client",
             S("profile", "/policy/gnd_gat"),
             "Missing RSW bodies were not parsed; GND/GAT are same-stem candidates."),
        fact("dynamic.model_texture_dependencies", "unknown", None, "dependencies", N,
             "client", S(None, None)),
        fact("dynamic.computed_map_names", "unknown", None, "script references", D, "server",
             S(None, None), "Dynamic/computed map names are not exhaustively interpreted."),
        fact("dynamic.archive_priority", "unknown", None, "lookup order", D, "client",
             S(None, None), "Native Taiwan precedence and full patch apply order unproved."),
        fact("dynamic.overlay_effects", "unknown", None, "overlays", N, "overlay",
             S(None, None), "No overlay manifest is admitted."),
    ]
    return cats


def build_versions(docs, revision):
    snap, sel, P = docs["snapshot"], docs["selection"], docs["profile"]
    views = {}
    for cat in P["catalogs"]:
        for m in cat["memberships"]:
            views.setdefault(m["view"], []).append(cat)
    client_views = {}
    for view, cats in sorted(views.items()):
        entry = {"catalogs": len(cats),
                 "families": dict(sorted({f: sum(1 for c in cats if c["family"] == f)
                                          for f in {c["family"] for c in cats}}.items()))}
        if view == "suffix59":
            idx = sorted(c["patch_index"] for c in cats)
            entry["patch_index_min"], entry["patch_index_max"] = idx[0], idx[-1]
        else:
            entry["archives"] = [{"archive_file": c["archive_file"],
                                  "archive_sha256": c["archive_sha256"],
                                  "archive_bytes": c["archive_bytes"]}
                                 for c in sorted(cats, key=lambda c: c["archive_file"])]
        client_views[view] = entry
    return {
        "server": {
            "evidence_level": "qualified_inventory_manifest",
            "repository": sel["source"]["repository"], "revision": revision,
            "image_tag": snap["input"]["tag"],
            "snapshot_file_list_sha256": snap["output"]["file_list_sha256"],
            "snapshot_files": snap["counts"]["files"],
            "selection_profile": sel["profile"]["name"],
            "renewal": sel["profile"]["renewal"],
            "installed_binary_build": "unknown",
            "note": "Packaged image snapshot of the source profile; installed binary compile "
                    "options and live config are not admitted.",
        },
        "client": {
            "evidence_level": "qualified_metadata_join",
            "views": client_views,
            "installed_view": {"value": "april", "evidence_level": "documented_not_admitted",
                               "note": "INSTALLATION/ASSETS record the April archives as "
                                       "configured; current installed state not refreshed."},
            "episode": {"state": "unknown",
                        "note": "No client date or archive count defines an episode."},
        },
        "overlay": {
            "state": "unknown", "evidence_level": "documented_not_admitted",
            "documented": "six enabled of 17 listed mods (2026-10-25 records), including "
                          "tw-iteminfo-utf8 1.0.1, tw-carocc-pilot 0.2.0 and "
                          "npc-plaintext-zh-tw 1.0.0",
            "note": "No overlay manifest is pinned; overlay revisions are recorded separately "
                    "and must be refreshed before any runtime claim.",
        },
    }


# ---------------------------------------------------------------- validator
#
# validate_ledger checks STRUCTURE and INTERNAL CONSISTENCY only: vocabularies,
# promotion rules, required facts/denominators, root identity/order, row-derived
# totals, arithmetic identities between facts, and that every input-sourced fact
# equals its recorded source value. It cannot prove that the recorded source
# values are authentic: a coordinated edit of a fact and its recorded source
# value (or of every input) is only detected by `check`, which regenerates the
# ledger from the pinned inputs and requires byte equality.

def _rows(ledger):
    return ledger.get("gap_roots") or []


def _slot_total(roots, key):
    return sum(r["client"]["name_counterparts"][k][key] for r in roots
               for k in ("rsw", "gnd", "gat"))


# Ledger-side values recomputed from the actual rows/facts at validation time.
BINDINGS = {
    "rows": lambda L, F: len(_rows(L)),
    "rows_configured": lambda L, F: sum(1 for r in _rows(L) if r["configured"]),
    "rows_cache_only": lambda L, F: sum(1 for r in _rows(L) if not r["configured"]),
    "rows_name_occurrences": lambda L, F: _slot_total(_rows(L), "full_path_occurrences"),
    "rows_basename_only": lambda L, F: _slot_total(_rows(L), "basename_only_occurrences"),
    "rows_with_counterpart": lambda L, F: sum(
        1 for r in _rows(L) if any(r["client"]["name_counterparts"][k]["full_path_occurrences"]
                                   for k in ("rsw", "gnd", "gat"))),
    "rows_comparison_names": lambda L, F: 3 * len(_rows(L)),
    "fact_server_cache_entries": lambda L, F: F["maps.server_cache_entries"]["value"],
    "fact_stock_configured": lambda L, F: F["maps.stock_configured"]["value"],
}
# Reconciliation keys -> (binding, source role, pointer). All are mandatory.
RECONCILIATION = {
    "gap_roots_join": ("rows", "join", "/counts/gap_roots"),
    "gap_roots_profile": ("rows", "profile", "/denominators/gap_roots"),
    "gap_roots_rsw404": ("rows", "corrected", "/rsw404_count"),
    "configured": ("rows_configured", "corrected", "/configured404"),
    "configured_profile": ("rows_configured", "profile", "/denominators/configured_gap_roots"),
    "cache_only": ("rows_cache_only", "corrected", "/cache_only404"),
    "cache_only_profile": ("rows_cache_only", "profile", "/denominators/cache_only_gap_roots"),
    "name_occurrences": ("rows_name_occurrences", "join", "/counts/full_path_occurrences"),
    "roots_with_counterpart": ("rows_with_counterpart", "join", "/counts/roots_with_full_path"),
    "basename_only": ("rows_basename_only", "join", "/counts/basename_only_occurrences"),
    "comparison_names": ("rows_comparison_names", "profile", "/denominators/comparison_names"),
    "world_roots": ("fact_server_cache_entries", "profile", "/denominators/world_roots"),
    "configured_world_roots": ("fact_stock_configured", "profile",
                               "/denominators/configured_world_roots"),
}
# Facts recomputed from rows (no input pointer of their own).
ROW_DERIVED = {
    "maps.client_rsw_404_gap_roots": lambda L: len(_rows(L)),
    "maps.gap_roots_configured": lambda L: BINDINGS["rows_configured"](L, None),
    "maps.gap_roots_cache_only": lambda L: BINDINGS["rows_cache_only"](L, None),
    "story.chapter1_family_gap_roots": lambda L: sum(
        1 for r in _rows(L) if r["tags"]["chapter1_family_documented"]),
    "instances.gap_root_name_candidates": lambda L: sum(
        1 for r in _rows(L) if r["tags"]["instance_name_candidate"]),
}
# Arithmetic identities between facts.
IDENTITIES = (
    ("spawns.framing_events", ("spawns.static_supported", "spawns.static_gap", "spawns.opaque",
                               "spawns.uncertified_suffix", "spawns.not_static"), ()),
    ("maps.cache_only", ("maps.server_cache_entries",), ("maps.stock_configured",)),
)


def validate_ledger(ledger):
    """Structural and internal-consistency checks (see the note above)."""
    need(ledger.get("schema") == SCHEMA, "LEDGER_SHAPE", "unexpected ledger schema")
    admitted = ledger.get("admitted_inputs") or []
    need(admitted and all(i.get("role") in METADATA_ROLES and len(i.get("sha256", "")) == 64
                          for i in admitted), "LEDGER_SHAPE", "admitted inputs missing pins")
    metadata_only = all(i["role"] in METADATA_ROLES for i in admitted)
    admitted_paths = {i["path"] for i in admitted}
    roots = _rows(ledger)
    for key in ("gap_index", "root_ordinal", "map_name"):
        values = [r.get(key) for r in roots]
        need(None not in values, "MISSING_ROOT_ID", f"root lacks {key}")
        dup = sorted({v for v in values if values.count(v) > 1}, key=str)
        need(not dup, "DUPLICATE_ROOT_ID", f"duplicate {key}: {dup}")
    need([r["gap_index"] for r in roots] == list(range(len(roots))), "MISSING_ROOT_ID",
         "gap_index is not dense in original order")

    def check_state(where, state, level):
        need(state in STATES, "LEDGER_SHAPE", f"{where}: unknown state {state!r}")
        need(level in EVIDENCE_LEVELS, "LEDGER_SHAPE", f"{where}: unknown level {level!r}")
        need(state == "unknown" or level != "not_observed", "UNSUPPORTED_PROMOTION",
             f"{where}: state {state} claimed with evidence level not_observed")
        allowed = PROMOTION_RULES.get(state)
        need(allowed is None or level in allowed, "UNSUPPORTED_PROMOTION",
             f"{where}: state {state} needs {sorted(allowed or [])}, has {level}")
        need(not (metadata_only and level in RESERVED_LEVELS), "UNSUPPORTED_PROMOTION",
             f"{where}: reserved level {level} from metadata-only inputs")
        need(level != "name_convention_only" or state == "unknown", "UNSUPPORTED_PROMOTION",
             f"{where}: name convention cannot establish state {state}")

    facts_by_id = {}
    categories = ledger.get("categories") or {}
    need(set(categories) == set(CATEGORIES), "LEDGER_SHAPE", "category set differs")
    for cat in CATEGORIES:
        facts = categories[cat]
        need(isinstance(facts, list) and [f.get("id") for f in facts]
             == list(REQUIRED_FACTS[cat]), "LEDGER_SHAPE",
             f"category {cat} facts differ from the required fact list")
        need(any(f["state"] == "unknown" for f in facts), "LEDGER_SHAPE",
             f"category {cat} hides its unknowns")
        for f in facts:
            check_state(f"{cat}/{f['id']}", f["state"], f["evidence_level"])
            need(f["scope"] in SCOPES, "LEDGER_SHAPE", f"{f['id']}: scope {f['scope']!r}")
            facts_by_id[f["id"]] = f
    for fid in DENOMINATOR_FACTS:
        f = facts_by_id[fid]
        need(f["state"] == "unknown" and f["value"] is None
             and f["evidence_level"] == "not_observed" and f["source"]["input"] is None,
             "UNSUPPORTED_PROMOTION",
             f"{fid}: no admitted input defines this denominator; metadata, raw declarations "
             "or the installed subset cannot fill it")

    # Every numeric fact must be bound: to a recorded input value, to rows, or be documented.
    recorded = ledger.get("source_values") or {}
    bound = set()
    for fid, f in facts_by_id.items():
        value, source = f["value"], f["source"]
        if source["input"] is not None:
            need(source["input"] in admitted_paths, "UNBOUND_FACT",
                 f"{fid}: source {source['input']} is not an admitted input")
        if value is None:
            continue
        need(isinstance(value, int) and not isinstance(value, bool), "LEDGER_SHAPE",
             f"{fid}: non-integer value")
        if source["input"] is not None:
            rec = recorded.get(fid)
            need(rec is not None and rec.get("input") == source["input"]
                 and rec.get("pointer") == source["pointer"], "UNBOUND_FACT",
                 f"{fid}: no recorded source value for its input/pointer")
            need(rec["value"] == value, "COUNT_MISMATCH",
                 f"{fid}: value {value} differs from recorded source value {rec['value']}")
            bound.add(fid)
        if fid in ROW_DERIVED:
            want = ROW_DERIVED[fid](ledger)
            need(value == want, "COUNT_MISMATCH",
                 f"{fid}: value {value} differs from {want} recomputed from rows")
            bound.add(fid)
        if source["input"] is None and fid not in ROW_DERIVED:
            need(f["evidence_level"] == "documented_not_admitted"
                 or any(fid == total for total, _, _ in IDENTITIES), "UNBOUND_FACT",
                 f"{fid}: value has no input, row or identity binding")
    need(set(recorded) <= bound, "UNBOUND_FACT",
         f"recorded source values without a fact: {sorted(set(recorded) - bound)}")
    for total, plus, minus in IDENTITIES:
        got = facts_by_id[total]["value"]
        want = (sum(facts_by_id[k]["value"] for k in plus)
                - sum(facts_by_id[k]["value"] for k in minus))
        need(got == want, "COUNT_MISMATCH", f"{total} = {got}, identity gives {want}")

    for r in roots:
        where = f"root {r.get('map_name')}"
        need(r.get("functional_gap") == "open", "UNSUPPORTED_PROMOTION",
             f"{where}: functional gap closed without runtime verification")
        for part in (r["server"]["stock_selection"], r["server"]["map_cache_entry"],
                     r["server"]["runtime_load"], r["client"]["rsw_request"],
                     r["client"]["body_render_load"], r["story_chain"], r["party_gate"]):
            check_state(where, part["state"], part["evidence_level"])
        need(r["server"]["stock_selection"]["state"]
             == ("present" if r["configured"] else "missing"), "COUNT_MISMATCH",
             f"{where}: stock selection state disagrees with configured flag")
        rsw = r["client"]["rsw_request"]
        need(rsw["state"] == "missing" and rsw["evidence_level"] == "prior_observed_request"
             and rsw.get("observed") == "HTTP404", "UNSUPPORTED_PROMOTION",
             f"{where}: gap root RSW request must remain the observed HTTP404")
        for role, slot in r["client"]["name_counterparts"].items():
            check_state(f"{where}/{role}", slot["state"], slot["evidence_level"])
            need(slot["state"] == ("present" if slot["full_path_occurrences"] else "missing"),
                 "COUNT_MISMATCH", f"{where}/{role}: state disagrees with occurrences")
            need(slot["full_path_occurrences"] == len(slot["witnesses"]), "COUNT_MISMATCH",
                 f"{where}/{role}: witness list disagrees with count")
    want = summarize_roots(roots, ledger["catalog_views"])
    need(ledger.get("gap_summary") == want, "COUNT_MISMATCH",
         "gap summary does not reconcile with per-root ledger")
    rec = ledger.get("reconciliation") or {}
    need(set(rec) == set(RECONCILIATION), "UNBOUND_FACT",
         f"reconciliation keys differ: {sorted(set(rec) ^ set(RECONCILIATION))}")
    for key, (binding, _role, pointer) in RECONCILIATION.items():
        item = rec[key]
        need(item.get("binding") == binding and item.get("pointer") == pointer
             and item.get("input") in admitted_paths, "UNBOUND_FACT",
             f"reconciliation {key}: binding/source differs from the fixed specification")
        actual = BINDINGS[binding](ledger, facts_by_id)
        need(actual == item["source_value"], "COUNT_MISMATCH",
             f"reconciliation {key}: rows/facts give {actual}, source recorded "
             f"{item['source_value']}")
    return True


# ---------------------------------------------------------------- generate

def generate(pins_path, root):
    pins, docs, admitted = load_inputs(pins_path, root)
    paths = {a["ledger_role"]: a["path"] for a in admitted}
    sha = {a["ledger_role"]: a["sha256"] for a in admitted}
    revision = check_provenance(docs, sha)
    roots = join_roots(docs, paths)
    categories = build_categories(docs, paths, roots)
    summary = summarize_roots(roots, docs["profile"]["catalogs"])
    role_of_path = {a["path"]: a["ledger_role"] for a in admitted}
    source_values = {}
    for facts in categories.values():
        for f in facts:
            if f["source"]["input"] is None or f["value"] is None:
                continue
            got = _get(docs[role_of_path[f["source"]["input"]]], f["source"]["pointer"])
            need(got == f["value"], "COUNT_MISMATCH",
                 f"{f['id']}: fact {f['value']} vs input {got} at {f['source']['pointer']}")
            source_values[f["id"]] = dict(f["source"], value=got)
    reconciliation = {}
    for key, (binding, role, pointer) in RECONCILIATION.items():
        reconciliation[key] = {"binding": binding, "input": paths[role], "pointer": pointer,
                               "source_value": _get(docs[role], pointer)}
    ledger = {
        "schema": SCHEMA, "task": "T06.005.001", "tool_version": TOOL_VERSION,
        "status": "provisional",
        "boundary": pins.get("input_boundary"),
        "pin_file_source_commit": pins.get("source_commit"),
        "admitted_inputs": [{k: a[k] for k in ("path", "bytes", "sha256", "role", "ledger_role")}
                            for a in admitted],
        "not_followed": "Embedded paths, raw JSONL streams, original 1296-root report and "
                        "archive bodies are inert pointers; none was read.",
        "states": list(STATES), "evidence_levels": list(EVIDENCE_LEVELS),
        "versions": build_versions(docs, revision),
        "catalog_views": [{"catalog_index": c["catalog_index"], "family": c["family"],
                           "archive_file": c["archive_file"],
                           "archive_sha256": c["archive_sha256"],
                           "patch_index": c["patch_index"],
                           "memberships": [{"view": m["view"]} for m in c["memberships"]]}
                          for c in docs["profile"]["catalogs"]],
        "categories": categories,
        "gap_summary": summary,
        "reconciliation": reconciliation,
        "source_values": source_values,
        "validation_boundary": "validate checks structure and internal consistency only; "
                               "input authenticity and reproducibility are proved only by "
                               "`check` against the pinned inputs.",
        "gap_roots": roots,
        "claims_not_made": [
            "full world/story coverage", "current runtime map/NPC/monster load",
            "functional closure of any gap root", "episode completeness",
            "party-only classification", "overlay state",
        ],
    }
    validate_ledger(ledger)
    recheck_inputs(root, admitted)
    return ledger


def dump(ledger):
    return (json.dumps(ledger, indent=1, sort_keys=True, ensure_ascii=True) + "\n").encode()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command")
    for name in ("generate", "check"):
        p = sub.add_parser(name)
        p.add_argument("--inputs", required=True)
        p.add_argument("--root", required=True)
        if name == "generate":
            p.add_argument("--out", required=True)
            p.add_argument("--receipt")
        else:
            p.add_argument("--ledger", required=True)
    p = sub.add_parser("validate")
    p.add_argument("--ledger", required=True)
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_usage(sys.stderr)
        return 64
    try:
        if args.command == "validate":
            with open(args.ledger, "rb") as handle:
                validate_ledger(json.loads(handle.read()))
            print("valid")
            return 0
        started = time.monotonic()
        ledger = generate(args.inputs, args.root)
        data = dump(ledger)
        if args.command == "check":
            with open(args.ledger, "rb") as handle:
                need(handle.read() == data, "LEDGER_DRIFT",
                     "regenerated ledger differs from the committed ledger")
            print("reproduced", hashlib.sha256(data).hexdigest())
            return 0
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        fd = os.open(args.out, flags, 0o644)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        if args.receipt:
            fd = os.open(args.receipt, flags, 0o600)
            with os.fdopen(fd, "w") as handle:
                json.dump({"root": args.root, "inputs": args.inputs,
                           "ledger_bytes": len(data),
                           "ledger_sha256": hashlib.sha256(data).hexdigest(),
                           "seconds": round(time.monotonic() - started, 3)}, handle, indent=1)
        print("written", len(data), hashlib.sha256(data).hexdigest())
        return 0
    except Refusal as refusal:
        print(f"refused {refusal.code}: {refusal.detail}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
