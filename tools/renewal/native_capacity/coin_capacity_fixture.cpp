// Host differential fixture for T10.010.002 (source only).
//
// Built by test_coin_capacity.py from a fresh private directory. The driver
// extracts, without rewriting, these bodies from the prepared native subset:
//   orig.inc    UNCHANGED pc_search_inventory, pc_generate_unique_id, pc_additem
//   patched.inc patched pc_search_inventory, pc_generate_unique_id,
//               pc_additem_plan, pc_additem, pc_ch1_coin_capacity and
//               BUILDIN_FUNC(ros_ch1_coin_capacity)
//   types.inc   mmo.hpp t_itemid, MAX_SLOTS/MAX_AMOUNT/MAX_ITEM_RDM_OPT,
//               enum item_types, bound_type, packed s_item_randomoption/item;
//               pc.hpp enum e_additem_result; itemdb isStackable bodies.
// Everything else is a transparent typed stub below: map_session_data and
// item_data carry only the fields those bodies touch; packets, logs, equip,
// rental, delete, achievements, quest info, time, item/pet DB and the script
// stack record an ordered trace. MAX_INVENTORY is frozen at 200 (packet
// 20221005: 100 base + 100 expansion) by the driver in types.inc.
// This proves nothing about full headers, linking, the parser or runtime.

#include <cstdio>
#include <cstring>
#include <cstdint>
#include <map>
#include <memory>
#include <string>
#include <vector>

#include "common/cbasetypes.hpp"
#include "types.inc"

// ---- typed dependency stubs (shared types) -------------------------------

enum e_log_pick_type { LOG_TYPE_OTHER = 1, LOG_TYPE_SCRIPT = 2 };
enum e_achievement_group { AG_GET_ITEM = 1 };
enum _sp { SP_WEIGHT = 24 };
enum e_script_cmd { SCRIPT_CMD_SUCCESS = 0, SCRIPT_CMD_FAILURE = 1 };
enum e_script_state { RUN = 0, END = 2 };

struct item_data {
	t_itemid nameid;
	uint32 value_sell;
	item_types type;
	uint32 equip;
	uint32 weight;
	struct {
		unsigned autoequip : 1;
		unsigned guid : 1;
	} flag;
	struct {
		uint16 amount;
		bool inventory;
	} stack;
	bool isStackable() const;
};


struct map_session_data {
	struct {
		struct {
			struct item items_inventory[MAX_INVENTORY];
		} u;
	} inventory;
	struct {
		uint32 char_id;
		uint32 uniqueitem_counter;
		uint16 inventory_slots;
	} status;
	struct item_data* inventory_data[MAX_INVENTORY];
	uint32 weight, max_weight;
	int16 last_addeditem_index;
};

struct s_pet_db { int32 egg; };

struct script_state {
	int32 rid;
	int32 nargs; // data positions 2..(1+nargs)
	int32 state;
	std::vector<int64> pushed;
};

static std::vector<std::string> g_trace;
static item_data g_dummy;                          // itemdb_search fallback
static std::map<t_itemid, item_data*> g_itemdb;
static std::map<std::string, std::shared_ptr<item_data>> g_names;
static std::map<int32, map_session_data*> g_players;
static bool g_pet_egg = false;
static int g_pet_create_calls = 0;
static const time_t NOW = 1000000;

static void tr(const char* fmt, long a = 0, long b = 0, long c = 0) {
	char buf[160];
	snprintf(buf, sizeof(buf), fmt, a, b, c);
	g_trace.push_back(buf);
}

#define nullpo_retr(ret, p) do { if (!(p)) return (ret); } while (0)
#define nullpo_ret(p) do { if (!(p)) return 0; } while (0)
// ARR_FIND is not in the frozen subset; this is the usual rAthena linear find.
#define ARR_FIND(__start, __end, __var, __cmp) \
	do { for ((__var) = (__start); (__var) < (__end); ++(__var)) if (__cmp) break; } while (0)
#define ShowError(...) tr("ShowError")

#include "isstackable.inc"

class ItemDbStub {
public:
	std::shared_ptr<item_data> searchname(const char* name) {
		auto it = g_names.find(name);
		return it == g_names.end() ? nullptr : it->second;
	}
} item_db;

#define BUILDIN_FUNC(x) int32 buildin_ ## x (struct script_state* st)
#define script_hasdata(st, i) ((i) - 2 < (st)->nargs)
#define script_pushint(st, v) ((st)->pushed.push_back((v)))

// Per-namespace stubs: unqualified calls inside the extracted bodies resolve
// here first, so both copies see identical deterministic dependencies.
#define STUBS \
	static time_t time(time_t*) { return NOW; } \
	static struct item_data* itemdb_search(t_itemid n) { auto it = g_itemdb.find(n); return it == g_itemdb.end() ? &g_dummy : it->second; } \
	static void clif_additem(map_session_data* sd, int32 i, int32 a, int32 f) { tr("clif_additem %ld %ld %ld", i, a, f); tr("packet row amount %ld", sd->inventory.u.items_inventory[i].amount); } \
	static void log_pick_pc(map_session_data*, e_log_pick_type t, int32 a, struct item* it) { tr("log_pick %ld %ld %ld", t, a, it->amount); } \
	static void clif_updatestatus(map_session_data& sd, int32 t) { tr("updatestatus %ld %ld", t, sd.weight); } \
	static bool pc_equipitem(map_session_data* sd, int32 i, int32 pos) { tr("equip %ld %ld", i, pos); sd->inventory.u.items_inventory[i].equip = pos; return true; } \
	static void clif_rental_expired(map_session_data*, int32 i, t_itemid n) { tr("rental_expired %ld %ld", i, n); } \
	static char pc_delitem(map_session_data* sd, int32 i, int32 a, int32 t, int16 r, e_log_pick_type l) { tr("delitem %ld %ld %ld", i, a, t); sd->inventory.u.items_inventory[i].amount -= a; if (sd->inventory.u.items_inventory[i].amount <= 0) memset(&sd->inventory.u.items_inventory[i], 0, sizeof(struct item)); return 0; } \
	static void clif_rental_time(map_session_data*, t_itemid n, uint32 s) { tr("rental_time %ld %ld", n, s); } \
	static void pc_inventory_rental_add(map_session_data*, uint32 s) { tr("rental_add %ld", s); } \
	static void achievement_update_objective(map_session_data*, int32 g, int32 n, uint32 v) { tr("achievement %ld %ld %ld", g, n, v); } \
	static void pc_show_questinfo(map_session_data*) { tr("questinfo"); }

namespace orig {
STUBS
#include "orig.inc"
}

static std::shared_ptr<s_pet_db> pet_db_search(int32 key, e_pet_itemtype type) {
	tr("pet_db_search %ld %ld", key, type);
	return (g_pet_egg && type == PET_EGG) ? std::make_shared<s_pet_db>() : nullptr;
}
static bool pet_create_egg(map_session_data*, t_itemid) { g_pet_create_calls++; return false; }
static map_session_data* map_id2sd(int32 id) {
	auto it = g_players.find(id);
	return it == g_players.end() ? nullptr : it->second;
}

namespace patched {
STUBS
#include "patched.inc"
}

// ---- cases ----------------------------------------------------------------

static const t_itemid COIN = 1001972;
static item_data d_coin, d_other, d_weapon, d_guid, d_auto, d_limit;
static int g_fail = 0, g_cases = 0, g_probes = 0;

struct State {
	map_session_data sd;
	struct item it;
};

static void db_init() {
	auto mk = [](item_data& d, t_itemid n, item_types t, uint32 w) {
		memset(&d, 0, sizeof(d)); d.nameid = n; d.type = t; d.weight = w; d.value_sell = 7;
		g_itemdb[n] = &d;
	};
	memset(&g_dummy, 0, sizeof(g_dummy)); g_dummy.type = IT_ETC;
	mk(d_coin, COIN, IT_ETC, 1);
	mk(d_other, 501, IT_HEALING, 7);
	mk(d_weapon, 1201, IT_WEAPON, 50);
	mk(d_guid, 6000, IT_ETC, 1); d_guid.flag.guid = 1;
	mk(d_auto, 6001, IT_ETC, 1); d_auto.flag.autoequip = 1; d_auto.equip = 0x100;
	mk(d_limit, 6002, IT_ETC, 1); d_limit.stack.inventory = true; d_limit.stack.amount = 100;
}

// Fresh zeroed state: slots usable, a sentinel row at 0 and the rest blank.
static State base(uint16 slots = 20) {
	State s;
	memset(&s, 0, sizeof(s));
	s.sd.status.char_id = 150001;
	s.sd.status.uniqueitem_counter = 77;
	s.sd.status.inventory_slots = slots;
	s.sd.weight = 100; s.sd.max_weight = 1000;
	s.sd.last_addeditem_index = -1;
	s.sd.inventory.u.items_inventory[0].nameid = 501;
	s.sd.inventory.u.items_inventory[0].amount = 3;
	s.sd.inventory.u.items_inventory[0].identify = 1;
	s.sd.inventory_data[0] = &d_other;
	s.it.nameid = COIN; s.it.identify = 1; s.it.bound = BOUND_NONE;
	return s;
}
static struct item& row(State& s, int i, t_itemid n = COIN, int16 a = 1) {
	struct item& r = s.sd.inventory.u.items_inventory[i];
	r.nameid = n; r.amount = a; r.identify = 1;
	s.sd.inventory_data[i] = g_itemdb.count(n) ? g_itemdb[n] : &g_dummy;
	return r;
}
static void fill(State& s, int from, int to) { // occupy with unrelated rows
	for (int i = from; i < to; i++) row(s, i, 909, 1);
}

static std::string dump(const std::vector<std::string>& t) {
	std::string o; for (auto& x : t) { o += x; o += "; "; } return o;
}

enum Flags { NULL_SD = 1, NULL_IT = 2 };

// Separate restored states run the unchanged and patched pc_additem; a third
// unchanged copy is probed twice when the input is the ordinary coin x10.
static void diff(const char* name, const State& s0, int32 amount, bool fav = false,
		int flags = 0, int expect = -2) {
	g_cases++;
	State a, b, c;
	memcpy(&a, &s0, sizeof(State)); memcpy(&b, &s0, sizeof(State)); memcpy(&c, &s0, sizeof(State));
	g_trace.clear();
	int ra = orig::pc_additem((flags & NULL_SD) ? nullptr : &a.sd, (flags & NULL_IT) ? nullptr : &a.it, amount, LOG_TYPE_SCRIPT, fav);
	std::vector<std::string> ta = g_trace;
	g_trace.clear();
	int rb = patched::pc_additem((flags & NULL_SD) ? nullptr : &b.sd, (flags & NULL_IT) ? nullptr : &b.it, amount, LOG_TYPE_SCRIPT, fav);
	std::vector<std::string> tb = g_trace;
	bool ok = ra == rb && memcmp(&a, &b, sizeof(State)) == 0 && ta == tb;
	if (expect != -2 && ra != expect) ok = false;
	if (!ok) {
		g_fail++;
		printf("FAIL diff %s orig=%d patched=%d expect=%d state=%s\n  o: %s\n  p: %s\n", name, ra, rb, expect,
			memcmp(&a, &b, sizeof(State)) ? "differs" : "same", dump(ta).c_str(), dump(tb).c_str());
	}
	struct item ordinary; memset(&ordinary, 0, sizeof(ordinary));
	ordinary.nameid = COIN; ordinary.identify = 1; ordinary.bound = BOUND_NONE;
	if (!(flags) && amount == 10 && memcmp(&s0.it, &ordinary, sizeof(ordinary)) == 0
			&& g_itemdb[COIN] == &d_coin) {
		g_probes++;
		// Every named physical row must have a valid quantity. This policy is
		// separate from the unchanged general-add oracle, which still runs above.
		bool malformed = false;
		for (int i = 0; i < MAX_INVENTORY; i++)
			if (s0.sd.inventory.u.items_inventory[i].nameid != 0
					&& (s0.sd.inventory.u.items_inventory[i].amount <= 0 || s0.sd.inventory.u.items_inventory[i].amount > MAX_AMOUNT))
				malformed = true;
		int want = malformed ? -1 : (ra == 0 ? 1 : 0);
		for (int k = 0; k < 2; k++) {
			g_trace.clear();
			int p = patched::pc_ch1_coin_capacity(&c.sd, &d_coin);
			bool pok = p == want && g_trace.empty() && memcmp(&c, &s0, sizeof(State)) == 0;
			if (!pok) {
				g_fail++;
				printf("FAIL probe %s #%d probe=%d orig=%d trace=%s\n", name, k, p, ra, dump(g_trace).c_str());
			}
		}
	}
	printf("case %s -> %d\n", name, ra);
}

static void group1() {
	State s = base();
	diff("g1 null actor", s, 10, false, NULL_SD, 1);
	diff("g1 null item", s, 10, false, NULL_IT, 1);
	s.it.nameid = 0; diff("g1 nameid0", s, 10, false, 0, 1);
	s = base(); diff("g1 amount0", s, 0, false, 0, 1);
	diff("g1 amount-1", s, -1, false, 0, 1);
	diff("g1 overMAX", s, MAX_AMOUNT + 1, false, 0, 5);
	diff("g1 exactly MAX new", s, MAX_AMOUNT, false, 0, 2); // overweight (30000)
	s.sd.max_weight = 100000; diff("g1 exactly MAX new fits", s, MAX_AMOUNT, false, 0, 0);
	// stack limit beats weight
	s = base(); s.it.nameid = 6002; s.sd.weight = 1000; diff("g1 stack-before-weight", s, 101, false, 0, 7);
	diff("g1 stack ok then overweight", s, 100, false, 0, 2);
	// weight beats GUID generation: counter must stay 77
	s = base(); s.it.nameid = 6000; s.sd.weight = 995; diff("g1 weight-before-GUID", s, 10, false, 0, 2);
	s = base(); s.sd.weight = 990; diff("g1 weight equality", s, 10, false, 0, 0);
	s.sd.weight = 991; diff("g1 weight over by 1", s, 10, false, 0, 2);
	// disabled stack.inventory ignores its amount
	s = base(); d_coin.stack.amount = 3; diff("g1 disabled limit ignored", s, 10, false, 0, 0);
	d_coin.stack.inventory = true; diff("g1 active limit 3 refuses", s, 10, false, 0, 7);
	d_coin.stack.amount = 10; diff("g1 active limit equal", s, 10, false, 0, 0);
	row(s, 4, COIN, 1); diff("g1 active limit total over", s, 10, false, 0, 5);
	s.sd.inventory.u.items_inventory[4].amount = 0; diff("g1 active limit zero-row", s, 10, false, 0, 0);
	d_coin.stack.inventory = false; d_coin.stack.amount = 0;
}

static void group2() {
	State s = base(); diff("g2 new first blank", s, 10, false, 0, 0);
	s = base(); row(s, 3, COIN, 5); diff("g2 merge", s, 10, false, 0, 0);
	s = base(); row(s, 3, COIN, MAX_AMOUNT - 9); diff("g2 full compatible", s, 10, false, 0, 5);
	s = base(); row(s, 3, COIN, MAX_AMOUNT - 10); diff("g2 exact MAX total", s, 10, false, 0, 0);
	s = base(); row(s, 2, COIN, MAX_AMOUNT).bound = BOUND_CHAR; row(s, 5, COIN, 7);
	diff("g2 earlier incompatible FULL later fit", s, 10, false, 0, 0);
	s = base(5); fill(s, 1, MAX_INVENTORY); row(s, 2, COIN, MAX_AMOUNT).bound = BOUND_ACCOUNT; row(s, 4, COIN, 7);
	diff("g2 full bag + incompatible full + compatible fit", s, 10, false, 0, 0);
	s = base(5); fill(s, 1, MAX_INVENTORY); row(s, 3, COIN, 7); diff("g2 full bag compatible fit", s, 10, false, 0, 0);
	s = base(5); fill(s, 1, MAX_INVENTORY); diff("g2 no blank", s, 10, false, 0, 4);
	s = base(5); fill(s, 1, 5); diff("g2 only inaccessible blanks", s, 10, false, 0, 4);
	s = base(5); fill(s, 1, 4); diff("g2 last usable blank", s, 10, false, 0, 0);
	s = base(MAX_INVENTORY); fill(s, 1, MAX_INVENTORY - 1); diff("g2 last physical blank", s, 10, false, 0, 0);
	s = base(0); diff("g2 zero usable slots", s, 10, false, 0, 4);
	s = base(MAX_INVENTORY); fill(s, 1, MAX_INVENTORY); s.sd.inventory.u.items_inventory[199].nameid = 0;
	s.sd.inventory.u.items_inventory[199].amount = 0; diff("g2 physical index 199 blank", s, 10, false, 0, 0);
	s = base(MAX_INVENTORY); fill(s, 1, MAX_INVENTORY); row(s, 199, COIN, 3); diff("g2 physical index 199 merge", s, 10, false, 0, 0);
	s = base(5); fill(s, 1, 5); s.sd.inventory.u.items_inventory[3].nameid = 0; s.sd.inventory.u.items_inventory[3].refine = 9;
	s.sd.inventory.u.items_inventory[3].amount = 4; diff("g2 dirty blank selected", s, 10, false, 0, 0);
	s = base(); s.it.nameid = 6002; row(s, 3, 6002, 90); diff("g2 active stack total", s, 10, false, 0, 0);
	s.sd.inventory.u.items_inventory[3].amount = 91; diff("g2 active stack total over", s, 10, false, 0, 5);
}

static void group3() {
	const char* names[] = { "bound", "card0", "card1", "card2", "card3", "unique", "rental" };
	for (int k = 0; k < 7; k++) {
		for (int blank = 0; blank < 2; blank++) {
			State s = base(5); fill(s, 1, 5);
			if (blank) s.sd.inventory.u.items_inventory[4].nameid = 0, s.sd.inventory.u.items_inventory[4].amount = 0, s.sd.inventory_data[4] = nullptr;
			struct item& r = row(s, 2, COIN, 5);
			if (k == 0) r.bound = BOUND_GUILD;
			else if (k <= 4) r.card[k - 1] = (k == 4) ? 0x10000 : 4001;
			else if (k == 5) r.unique_id = 99;
			else r.expire_time = (uint32)(NOW + 50);
			std::string n = std::string("g3 incompatible ") + names[k] + (blank ? " +blank" : " full");
			diff(n.c_str(), s, 10, false, 0, blank ? 0 : 4);
		}
	}
	State s = base(5); fill(s, 1, 5); row(s, 2, COIN, 5).expire_time = (uint32)(NOW - 5);
	diff("g3 expired rental row full", s, 10, false, 0, 4);
	s = base(); row(s, 2, COIN, MAX_AMOUNT - 5); row(s, 4, COIN, 1); diff("g3 first compatible full later fit", s, 10, false, 0, 5);
	s = base(5); row(s, 7, COIN, 1); diff("g3 compatible inaccessible earlier blank", s, 10, false, 0, 5);
	s = base(); row(s, 2, COIN, 1).bound = BOUND_PARTY; row(s, 4, COIN, MAX_AMOUNT - 1); diff("g3 incompatible then full compatible", s, 10, false, 0, 5);
}

static void group4() {
	State s = base(); struct item& r = row(s, 3, COIN, 5);
	r.identify = 0; r.refine = 7; r.attribute = 1; r.enchantgrade = 3; r.option[0].id = 9; r.option[4].value = 2;
	r.equip = 0x10; r.equipSwitch = 0x20; r.favorite = 1; r.id = 1234;
	row(s, 6, 909, 2).refine = 4; // unrelated sentinel
	diff("g4 ignored metadata merge", s, 10, false, 0, 0);
	for (int f = 0; f < 9; f++) { // each native-ignored field independently
		State one = base(); struct item& q = row(one, 3, COIN, 5);
		switch (f) {
		case 0: q.identify = 0; break; case 1: q.refine = 1; break; case 2: q.attribute = 1; break;
		case 3: q.enchantgrade = 1; break; case 4: q.option[2].id = 1; break; case 5: q.equip = 1; break;
		case 6: q.equipSwitch = 1; break; case 7: q.favorite = 1; break; default: q.id = 9; break;
		}
		std::string n = "g4 ignored field " + std::to_string(f);
		diff(n.c_str(), one, 10, false, 0, 0);
	}
	s = base(); s.it.equip = 0x2; s.it.equipSwitch = 0x4; s.it.refine = 5; s.it.option[1].param = 3; s.it.id = 55;
	diff("g4 new copy clears equip", s, 10, true, 0, 0);
	s = base(); s.it.nameid = 501; diff("g4 merge sentinel row favorite", s, 2, true, 0, 0);
}

static void group5() {
	State s = base(); s.it.nameid = 1201; row(s, 2, 1201, 1); diff("g5 nonstackable bypasses merge", s, 1, false, 0, 0);
	s = base(); row(s, 2, COIN, 4); s.it.expire_time = (uint32)(NOW + 100); diff("g5 rental future", s, 10, false, 0, 0);
	s.it.expire_time = (uint32)NOW; diff("g5 rental equal now", s, 10, false, 0, 0);
	s.it.expire_time = (uint32)(NOW - 1); diff("g5 rental expired", s, 10, false, 0, 0);
	s = base(); s.it.nameid = 6001; diff("g5 autoequip new", s, 1, false, 0, 0);
	row(s, 5, 6001, 1); diff("g5 autoequip merge", s, 1, false, 0, 0);
}

static void group6() {
	State s = base(); s.it.nameid = 6000; d_guid.stack.inventory = true; d_guid.stack.amount = 5;
	diff("g6 guid stack early failure", s, 10, false, 0, 7);
	d_guid.stack.inventory = false;
	s = base(5); fill(s, 1, 5); s.it.nameid = 6000; diff("g6 guid destination failure", s, 10, false, 0, 4);
	s = base(); s.it.nameid = 6000; diff("g6 guid success", s, 10, false, 0, 0);
	s = base(); s.it.nameid = 6000; row(s, 3, 6000, 4).unique_id = ((uint64)150001 << 32) | 77;
	diff("g6 guid generated-ID match", s, 10, false, 0, 0);
	s = base(); s.it.nameid = 6000; s.it.unique_id = 4242; row(s, 3, 6000, 4).unique_id = 4242;
	diff("g6 guid supplied merge", s, 10, false, 0, 0);
	s = base(); s.it.nameid = 1201; diff("g6 nonguid nonstackable generation", s, 1, false, 0, 0);
	s.sd.status.uniqueitem_counter = UINT32_MAX; diff("g6 counter wrap", s, 1, false, 0, 0);
	s = base(); s.it.nameid = 6000; s.sd.status.uniqueitem_counter = UINT32_MAX; diff("g6 guid counter wrap", s, 10, false, 0, 0);
	s = base(); s.it.nameid = 1201; s.it.unique_id = 31337;
	diff("g6 nonguid nonstackable supplied", s, 1, false, 0, 0);
	s = base(5); fill(s, 1, 5); s.it.nameid = 1201; diff("g6 nonstackable no slot", s, 1, false, 0, 4);
}

// Actual builtin body with minimal script/DB stubs.
static void builtin(const char* name, int nargs, int rid, int expect_push, int expect_ret, State& s) {
	g_cases++;
	State before; memcpy(&before, &s, sizeof(State));
	g_players.clear(); g_players[150001] = &s.sd;
	script_state st; st.rid = rid; st.nargs = nargs; st.state = RUN;
	g_trace.clear();
	int ret = patched::buildin_ros_ch1_coin_capacity(&st);
	bool effects = false;
	for (auto& t : g_trace) if (t.rfind("ShowError", 0) != 0 && t.rfind("pet_db_search", 0) != 0) effects = true;
	bool ok = st.pushed.size() == 1 && st.pushed[0] == expect_push && ret == expect_ret
		&& st.state == RUN && !effects && g_pet_create_calls == 0 && memcmp(&before, &s, sizeof(State)) == 0;
	if (!ok) {
		g_fail++;
		printf("FAIL builtin %s push=%lld ret=%d trace=%s\n", name, st.pushed.empty() ? 99LL : (long long)st.pushed[0], ret, dump(g_trace).c_str());
	}
	printf("builtin %s -> %lld/%d\n", name, st.pushed.empty() ? 99LL : (long long)st.pushed[0], ret);
}

static void group7() {
	auto coin = std::make_shared<item_data>(d_coin);
	State s = base();
	g_names.clear();
	builtin("missing alias", 0, 150001, -1, 0, s);
	g_names["Ch1_Root_Coin"] = std::make_shared<item_data>(d_other);
	builtin("remapped alias", 0, 150001, -1, 0, s);
	auto bad = std::make_shared<item_data>(d_coin); bad->type = IT_USABLE; g_names["Ch1_Root_Coin"] = bad;
	builtin("wrong type", 0, 150001, -1, 0, s);
	bad = std::make_shared<item_data>(d_coin); bad->type = IT_WEAPON; g_names["Ch1_Root_Coin"] = bad;
	builtin("nonstackable", 0, 150001, -1, 0, s);
	bad = std::make_shared<item_data>(d_coin); bad->flag.guid = 1; g_names["Ch1_Root_Coin"] = bad;
	builtin("guid", 0, 150001, -1, 0, s);
	bad = std::make_shared<item_data>(d_coin); bad->weight = UINT32_MAX / 5; g_names["Ch1_Root_Coin"] = bad;
	builtin("weight arithmetic", 0, 150001, -1, 0, s);
	g_names["Ch1_Root_Coin"] = coin;
	g_pet_egg = true; builtin("pet mapping", 0, 150001, -1, 0, s);
	State full = base(5); fill(full, 1, MAX_INVENTORY);
	builtin("pet mapping full bag", 0, 150001, -1, 0, full);
	g_pet_egg = false;
	builtin("no actor", 0, 4242, -1, 0, s);
	builtin("extra args", 1, 150001, -1, 0, s);
	builtin("two extra args", 2, 150001, -1, 0, s);
	State w = base(); w.sd.weight = UINT32_MAX - 3; w.sd.max_weight = UINT32_MAX;
	builtin("weight state overflow", 0, 150001, -1, 0, w);
	State slots = base(); slots.sd.status.inventory_slots = MAX_INVENTORY + 1;
	builtin("slots over MAX", 0, 150001, -1, 0, slots);
	State bad_row = base(); row(bad_row, 3, COIN, 0);
	builtin("named row amount 0", 0, 150001, -1, 0, bad_row);
	bad_row.sd.inventory.u.items_inventory[3].amount = -2;
	builtin("named row negative", 0, 150001, -1, 0, bad_row);
	State zero = base(0);
	builtin("zero usable slots is no-fit", 0, 150001, 0, 0, zero);
	State heavy = base(); heavy.sd.weight = 1001;
	builtin("already overweight is no-fit", 0, 150001, 0, 0, heavy);
	auto light = std::make_shared<item_data>(d_coin); light->weight = 0; g_names["Ch1_Root_Coin"] = light;
	builtin("weight 0 supported", 0, 150001, 1, 0, s);
	builtin("weight 0 still refused when already overweight", 0, 150001, 0, 0, heavy);
	auto cap0 = std::make_shared<item_data>(d_coin); cap0->stack.inventory = true; g_names["Ch1_Root_Coin"] = cap0;
	builtin("active stack cap 0 is no-fit", 0, 150001, 0, 0, s);
	auto big = std::make_shared<item_data>(d_coin); big->stack.inventory = true; big->stack.amount = 60000;
	g_names["Ch1_Root_Coin"] = big;
	State nearmax = base(); row(nearmax, 3, COIN, MAX_AMOUNT - 5);
	builtin("MAX_AMOUNT kept under larger cap", 0, 150001, 0, 0, nearmax);
	g_names["Ch1_Root_Coin"] = coin;
	State inacc = base(5); fill(inacc, 1, MAX_INVENTORY); row(inacc, 150, COIN, 9);
	builtin("occupied inaccessible coin row", 0, 150001, 0, 0, inacc);
	builtin("supported fit", 0, 150001, 1, 0, s);
	builtin("supported refusal", 0, 150001, 0, 0, full);
	State mixed = base(5); fill(mixed, 1, MAX_INVENTORY); row(mixed, 2, COIN, MAX_AMOUNT).bound = BOUND_CHAR; row(mixed, 3, COIN, 4);
	builtin("supported mixed fit", 0, 150001, 1, 0, mixed);
	builtin("repeat probe unchanged", 0, 150001, 1, 0, mixed);
}

// Explicit domain boundaries exercise both the real helper and builtin.
// An early fitting coin must not hide a malformed row outside usable slots.
static void group8() {
	g_names["Ch1_Root_Coin"] = std::make_shared<item_data>(d_coin);
	for (int index : {3, 199}) {
		for (int16 quantity : {int16(0), int16(-1), int16(30001), int16(32767)}) {
			State s = base(5);
			if (index == 199) row(s, 1, COIN, 4);
			row(s, index, 501, quantity);
			std::string name = "g8 malformed noncoin " + std::to_string(index) + ":" + std::to_string(quantity);
			diff(name.c_str(), s, 10, false, 0, 0);
			builtin(name.c_str(), 0, 150001, -1, 0, s);
		}
	}
	for (int16 quantity : {int16(1), int16(30000)}) {
		State s = base(5); row(s, 1, COIN, 4); row(s, 199, 501, quantity);
		std::string name = "g8 supported noncoin boundary " + std::to_string(quantity);
		diff(name.c_str(), s, 10, false, 0, 0);
		builtin(name.c_str(), 0, 150001, 1, 0, s);
	}
	for (int16 quantity : {int16(0), int16(-1), int16(32767)}) {
		State s = base(5); struct item& blank = row(s, 1, 0, quantity);
		blank.card[0] = 4001; blank.bound = BOUND_CHAR; blank.unique_id = 123;
		blank.expire_time = NOW + 1; s.sd.inventory_data[1] = &d_other;
		std::string name = "g8 dirty blank quantity " + std::to_string(quantity);
		diff(name.c_str(), s, 10, false, 0, 0);
		builtin(name.c_str(), 0, 150001, 1, 0, s);
	}
}

int main() {
	db_init();
	group1(); group2(); group3(); group4(); group5(); group6(); group7(); group8();
	printf("SUMMARY cases=%d probes=%d failures=%d\n", g_cases, g_probes, g_fail);
	return g_fail ? 1 : 0;
}
