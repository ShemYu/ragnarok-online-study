"""Host differential check for the T10.010.002 native coin-capacity patch.

Run:
  python3 -I -B tools/renewal/native_capacity/test_coin_capacity.py \
      --native-source <prepared-subset> --clang /usr/bin/clang++

<prepared-subset> holds src/common and src/map from rAthena 0693b8c plus the
app 2c3b261 server overlays. The driver verifies the pinned hashes, copies
the three patched files into a fresh private directory, applies
coin_capacity.patch with no rejects, extracts the UNCHANGED original and the
patched function bodies verbatim, compiles them with coin_capacity_fixture.cpp
and runs the finite differential. Nine causal mutants of the patched body
must each be caught. Source only: no full headers, link, parser or runtime.
"""

import argparse
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
PATCH = HERE / "coin_capacity.patch"
FIXTURE = HERE / "coin_capacity_fixture.cpp"
MAX_INVENTORY = 200  # 100 base + 100 expansion (PACKETVER >= 20181031)

PINS = {
    "src/map/pc.cpp": (505127, "03b4d592e46e36824e4d44da6c7132edcb89e35f15f826914a2dae6d1d8a6e9b"),
    "src/map/pc.hpp": (65071, "0f57ca247570962ab357adbf257f8e1304bd95cf0219220fb4855bbba06d1a39"),
    "src/map/script.cpp": (805000, "f83b93eb11b1765d6115a5be64837be892cc11da2ec94ee3298fe8dd1fdf85db"),
    "src/map/pet.cpp": (62202, "43ee63394f4e5301e032ad006fb4c3dd87f717e0efb935ab33d4fa9758b85065"),
    "src/map/pet.hpp": (8293, "b7fe4e89627acaaade502d43b13d9b7b72b0df82d66fd65a7ef17b7886c0eeac"),
    "src/map/itemdb.cpp": (136601, "3b51a2bbcb44c5ffbdb5dc04683dd4f567c2da92f56a4bc0008aa9a93de5efe5"),
    "src/map/itemdb.hpp": (93676, "c7fb0224d54797f8271c3423cf90b1db9e7c179771423a2f1145b153c47faff0"),
    "src/common/mmo.hpp": (29705, "f4b81dc87a8f54059e07e90a314c2cef1d61e67ef488fe0093bea2805814a795"),
    "src/common/cbasetypes.hpp": (12917, "5ae18835ab3374a4ed613c613d2f65be8ea1fdd35c2194b84ce3f6d23f58a007"),
}
PATCHED = ("src/map/pc.cpp", "src/map/pc.hpp", "src/map/script.cpp")


def fail(msg):
    print("FAIL", msg)
    sys.exit(1)


def verify(src):
    for rel, (size, digest) in PINS.items():
        data = (src / rel).read_bytes()
        if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
            fail(f"pin {rel}")
    print(f"pins ok {len(PINS)}")


def body(text, signature):
    """Verbatim function text from its signature line to the matching brace."""
    start = text.find(signature)
    if start < 0 or text.find(signature, start + 1) >= 0:
        fail(f"signature not unique: {signature}")
    open_ = text.index("{", start)
    depth = 0
    for i in range(open_, len(text)):
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        if depth == 0:
            return text[start:i + 1] + "\n"
    fail(f"unbalanced: {signature}")


def block(text, pattern):
    m = re.findall(pattern, text, re.S | re.M)
    if len(m) < 1:
        fail(f"block: {pattern}")
    return m[0] + "\n"


SIG_SEARCH = "int16 pc_search_inventory( const map_session_data* sd, t_itemid nameid) {"
SIG_UID = "uint64 pc_generate_unique_id(map_session_data *sd) {"
SIG_ADD = "enum e_additem_result pc_additem(map_session_data *sd,struct item *item,int32 amount,e_log_pick_type log_type, bool favorite) {"
SIG_PLAN = "enum e_additem_result pc_additem_plan( const map_session_data* sd, const struct item* item, int32 amount, const struct item_data* id, int16* index, bool* merge ){"
SIG_PROBE = "int32 pc_ch1_coin_capacity( const map_session_data* sd, const struct item_data* id ){"
SIG_BUILTIN = "BUILDIN_FUNC(ros_ch1_coin_capacity)\n{"
SIG_GETITEM = "BUILDIN_FUNC(getitem)\n{"
SIG_CHECKADD = "char pc_checkadditem( const map_session_data* sd, t_itemid nameid, int32 amount )\n{"

# Causal mutants of the patched pc.cpp text: (name, old, new).
MUTANTS = (
    ("extra identify comparison",
     "\t\t\t\tsd->inventory.u.items_inventory[i].expire_time == 0 &&\n\t\t\t\tsd->inventory.u.items_inventory[i].unique_id == item->unique_id &&\n\t\t\t\tmemcmp(&sd->inventory.u.items_inventory[i].card, &item->card, sizeof(item->card)) == 0 ) {\n\t\t\t\tif( amount > MAX_AMOUNT - sd->inventory.u.items_inventory[i].amount || ( id->stack.inventory && amount > id->stack.amount - sd->inventory.u.items_inventory[i].amount ) )\n\t\t\t\t\treturn ADDITEM_OVERAMOUNT;\n\t\t\t\t// If the item is in the inventory already, but the player is not allowed to use that many slots anymore\n\t\t\t\tif( i >= sd->status.inventory_slots ){\n\t\t\t\t\treturn ADDITEM_OVERAMOUNT;\n\t\t\t\t}\n\t\t\t\t*index = i;",
     "\t\t\t\tsd->inventory.u.items_inventory[i].expire_time == 0 &&\n\t\t\t\tsd->inventory.u.items_inventory[i].identify == item->identify &&\n\t\t\t\tsd->inventory.u.items_inventory[i].unique_id == item->unique_id &&\n\t\t\t\tmemcmp(&sd->inventory.u.items_inventory[i].card, &item->card, sizeof(item->card)) == 0 ) {\n\t\t\t\tif( amount > MAX_AMOUNT - sd->inventory.u.items_inventory[i].amount || ( id->stack.inventory && amount > id->stack.amount - sd->inventory.u.items_inventory[i].amount ) )\n\t\t\t\t\treturn ADDITEM_OVERAMOUNT;\n\t\t\t\t// If the item is in the inventory already, but the player is not allowed to use that many slots anymore\n\t\t\t\tif( i >= sd->status.inventory_slots ){\n\t\t\t\t\treturn ADDITEM_OVERAMOUNT;\n\t\t\t\t}\n\t\t\t\t*index = i;"),
    ("any-fit selector",
     "\t\t\t\t\treturn ADDITEM_OVERAMOUNT;\n\t\t\t\t// If the item is in the inventory already, but the player is not allowed to use that many slots anymore\n\t\t\t\tif( i >= sd->status.inventory_slots ){\n\t\t\t\t\treturn ADDITEM_OVERAMOUNT;\n\t\t\t\t}\n\t\t\t\t*index = i;",
     "\t\t\t\t\tcontinue;\n\t\t\t\t// If the item is in the inventory already, but the player is not allowed to use that many slots anymore\n\t\t\t\tif( i >= sd->status.inventory_slots ){\n\t\t\t\t\tcontinue;\n\t\t\t\t}\n\t\t\t\t*index = i;"),
    ("usable-only scan",
     "\t*merge = false;\n\n\t// Stackable | Non Rental\n\tif( itemdb_isstackable2(id) && item->expire_time == 0 ) {\n\t\tfor( i = 0; i < MAX_INVENTORY; i++ ) {",
     "\t*merge = false;\n\n\t// Stackable | Non Rental\n\tif( itemdb_isstackable2(id) && item->expire_time == 0 ) {\n\t\tfor( i = 0; i < sd->status.inventory_slots; i++ ) {"),
    ("GUID generated after plan",
     "\tif (id->flag.guid && !item->unique_id)\n\t\titem->unique_id = pc_generate_unique_id(sd);\n\n\tresult = pc_additem_plan(sd, item, amount, id, &i, &merge);\n\tif( result != ADDITEM_SUCCESS )\n\t\treturn result;\n",
     "\tresult = pc_additem_plan(sd, item, amount, id, &i, &merge);\n\tif( result != ADDITEM_SUCCESS )\n\t\treturn result;\n\tif (id->flag.guid && !item->unique_id)\n\t\titem->unique_id = pc_generate_unique_id(sd);\n"),
)

# These mutations distinguish unsupported named quantities from dirty blanks.
# They affect only the probe; the general-add oracle must stay unchanged.
_DOMAIN_PREDICATE = "sd->inventory.u.items_inventory[i].nameid != 0 &&"
_DOMAIN_SCAN = "\tif( sd->status.inventory_slots > MAX_INVENTORY )\n\t\treturn -1;\n\tfor( i = 0; i < MAX_INVENTORY; i++ ){"
_MERGE_NOTIFY = "\t\tsd->inventory.u.items_inventory[i].amount += amount;\n\t\tclif_additem(sd,i,amount,0);"
MUTANTS += (
    ("coin-only quantity guard", _DOMAIN_PREDICATE,
     "sd->inventory.u.items_inventory[i].nameid == id->nameid &&"),
    ("quantity guard removed", _DOMAIN_PREDICATE, "false &&"),
    ("usable-only quantity guard", _DOMAIN_SCAN,
     _DOMAIN_SCAN.replace("i < MAX_INVENTORY", "i < sd->status.inventory_slots")),
    ("blank quantities incorrectly validated", _DOMAIN_PREDICATE, "true &&"),
    ("merge notification before amount update", _MERGE_NOTIFY,
     "\t\tclif_additem(sd,i,amount,0);\n\t\tsd->inventory.u.items_inventory[i].amount += amount;"),
)


def write_common(src, gen):
    mmo = (src / "src/common/mmo.hpp").read_text()
    pch = (src / "src/map/pc.hpp").read_text()
    pet = (src / "src/map/pet.hpp").read_text()
    idb = (src / "src/map/itemdb.cpp").read_text()
    types = [f"#define MAX_INVENTORY {MAX_INVENTORY}\n",
             block(mmo, r"^typedef uint32 t_itemid;"),
             block(mmo, r"^#define MAX_SLOTS \d+"),
             block(mmo, r"^#define MAX_AMOUNT \d+"),
             block(mmo, r"^#define MAX_ITEM_RDM_OPT \d+"),
             block(mmo, r"^enum item_types \{.*?^\};"),
             block(mmo, r"^enum bound_type \{.*?^\};"),
             block(mmo, r"^// NetBSD 5 and Solaris don't like pragma pack.*?#pragma pack\( pop \)\n#endif"),
             block(pch, r"^enum e_additem_result : uint8 \{.*?^\};"),
             block(pet, r"^enum e_pet_itemtype : uint8 \{.*?\};")]
    if "struct item {" not in types[7]:
        fail("struct item block")
    (gen / "types.inc").write_text("".join(types))
    (gen / "isstackable.inc").write_text(
        body(idb, "bool item_data::isStackable() const{")
        + body(idb, "bool itemdb_isstackable2( const item_data *id )\n{"))
    (gen / "common").mkdir()
    shutil.copy(src / "src/common/cbasetypes.hpp", gen / "common" / "cbasetypes.hpp")


def write_bodies(gen, orig_pc, new_pc, new_script):
    (gen / "orig.inc").write_text(body(orig_pc, SIG_SEARCH) + body(orig_pc, SIG_UID) + body(orig_pc, SIG_ADD))
    (gen / "patched.inc").write_text(
        body(new_pc, SIG_SEARCH) + body(new_pc, SIG_UID) + body(new_pc, SIG_PLAN)
        + body(new_pc, SIG_ADD) + body(new_pc, SIG_PROBE) + body(new_script, SIG_BUILTIN))


def build_run(clang, gen, label):
    exe = gen / "fixture"
    cmd = [clang, "-std=c++17", "-O0", "-w", "-I", str(gen), str(FIXTURE), "-o", str(exe)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode:
        print(r.stderr[:4000])
        fail(f"compile {label}")
    r = subprocess.run([str(exe)], capture_output=True, text=True, timeout=15)
    return r.returncode, r.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--native-source", required=True, type=Path)
    ap.add_argument("--clang", required=True)
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    src = a.native_source.resolve()
    verify(src)
    work = Path(tempfile.mkdtemp(prefix="t10-010-002-fixture-"))
    try:
        tree = work / "tree"
        for rel in PATCHED:
            (tree / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src / rel, tree / rel)
        r = subprocess.run(["patch", "-F", "0", "-p1", "-N", "-s", "--no-backup-if-mismatch", "-r", "-",
                            "-d", str(tree), "-i", str(PATCH)], capture_output=True, text=True, timeout=120)
        if (r.returncode or list(tree.rglob("*.rej")) or list(tree.rglob("*.orig"))
                or re.search(r"fuzz|offset|failed", r.stdout + r.stderr, re.I)):
            print(r.stdout, r.stderr)
            fail("patch did not apply cleanly")
        print("patch applied with no rejects")
        orig_pc = (src / "src/map/pc.cpp").read_text()
        orig_script = (src / "src/map/script.cpp").read_text()
        new_pc = (tree / "src/map/pc.cpp").read_text()
        new_hpp = (tree / "src/map/pc.hpp").read_text()
        new_script = (tree / "src/map/script.cpp").read_text()
        # Unchanged neighbours and the frozen registration.
        for sig in (SIG_SEARCH, SIG_UID, SIG_CHECKADD):
            if body(orig_pc, sig) != body(new_pc, sig):
                fail(f"changed: {sig}")
        if body(orig_script, SIG_GETITEM) != body(new_script, SIG_GETITEM):
            fail("getitem changed")
        if new_script.count('\tBUILDIN_DEF(ros_ch1_coin_capacity,""),\n') != 1:
            fail("registration")
        for decl in ("int32 pc_ch1_coin_capacity( const map_session_data* sd, const struct item_data* id );",
                     "enum e_additem_result pc_additem_plan( const map_session_data* sd, const struct item* item, int32 amount, const struct item_data* id, int16* index, bool* merge );"):
            if new_hpp.count(decl) != 1:
                fail(f"declaration {decl}")
        if "pet_create_egg" in body(new_script, SIG_BUILTIN) or "pc_generate_unique_id" in body(new_pc, SIG_PROBE):
            fail("probe calls a creator")
        print("unchanged bodies/registration ok")

        gen = work / "real"
        gen.mkdir()
        write_common(src, gen)
        write_bodies(gen, orig_pc, new_pc, new_script)
        rc, out = build_run(a.clang, gen, "real")
        summary = [l for l in out.splitlines() if l.startswith("SUMMARY")]
        if a.verbose or rc:
            print(out[:200000])
        print("real:", summary[0] if summary else "no summary")
        if rc or not summary:
            fail("differential")

        caught = 0
        for name, old, new in MUTANTS:
            if new_pc.count(old) != 1:
                fail(f"mutant anchor: {name}")
            mgen = work / ("mut%d" % caught)
            mgen.mkdir()
            write_common(src, mgen)
            write_bodies(mgen, orig_pc, new_pc.replace(old, new), new_script)
            mrc, mout = build_run(a.clang, mgen, name)
            fails = sum(l.startswith("FAIL") for l in mout.splitlines())
            print(f"mutant {name}: rc={mrc} failures={fails}")
            if mrc == 0 or fails == 0:
                fail(f"mutant not caught: {name}")
            caught += 1
        print(f"PASS differential and {caught}/{len(MUTANTS)} causal mutants caught")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
