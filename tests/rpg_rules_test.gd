extends SceneTree
## Run: Godot --headless --path . --script res://tests/rpg_rules_test.gd

const Rules = preload("res://scripts/rpg_rules.gd")
var checks := 0
var failures := 0

func _initialize() -> void:
	_test_character_isolation()
	_test_stats_have_gameplay_effects()
	_test_progression_and_carry()
	_test_allocation_is_transactional()
	_test_skill_resources()
	_test_novice_and_job_identity()
	_test_combat_distribution()
	_test_combat_boundaries()
	_test_monster_profiles()
	if failures == 0:
		print("RPG_RULES_TEST_PASS (%d checks)" % checks)
	else:
		push_error("RPG_RULES_TEST_FAIL: %d of %d checks" % [failures, checks])
	quit(1 if failures else 0)


func check(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(message)


func _test_character_isolation() -> void:
	var first := Rules.default_character()
	var second := Rules.default_character()
	first.stats.str = 90
	first.inventory.red_potion = 0
	first.skills.bash = 10
	check(second.stats.str < 90 and second.inventory.red_potion > 0 and second.skills.bash == 0,
		"Fresh characters must not share nested stats, inventory or skills")
	var derived := Rules.derived_stats(second)
	check(second.hp == derived.max_hp and second.sp == derived.max_sp,
		"New characters must start within their resource limits")


func _test_stats_have_gameplay_effects() -> void:
	var character := Rules.default_character()
	var before := Rules.derived_stats(character)
	var expected: Dictionary = {"str": "attack", "agi": "flee", "vit": "max_hp",
		"int": "max_sp", "dex": "hit", "luk": "critical"}
	for stat in Rules.STAT_NAMES:
		var changed := character.duplicate(true)
		changed.stats[stat] += 20
		var after := Rules.derived_stats(changed)
		check(after[expected[stat]] > before[expected[stat]], "%s must affect %s" % [stat, expected[stat]])
		if stat in ["agi", "dex"]:
			check(after.attack_interval < before.attack_interval, "%s must improve attack cadence" % stat)
		check(after.walk_speed == before.walk_speed, "Attack speed must not accidentally change walking speed")
	character.equipped_weapon = ""
	check(Rules.derived_stats(character).attack < before.attack, "Removing a dagger must lower damage")
	character.stats.agi = Rules.STAT_CAP
	character.stats.dex = Rules.STAT_CAP
	check(Rules.derived_stats(character).attack_interval > 0.0, "High attack speed must keep a positive cycle")


func _test_progression_and_carry() -> void:
	var character := Rules.default_character()
	var starting_points: int = character.stat_points
	character.hp = 1.0
	character.sp = 0.0
	# Literal early thresholds are acceptance evidence from the published novice
	# EXP table, not a restatement of the implementation's level-up loop.
	var outcome := Rules.grant_exp(character, 9 + 16 + 7, 10 + 18 + 3)
	check(character.base_level == 3 and character.base_exp == 7, "Base EXP must carry over two level-ups")
	check(character.job_level == 3 and character.job_exp == 3, "Job EXP must carry independently")
	check(outcome.base_levels == 2 and outcome.job_levels == 2, "Level-up notifications must count every level")
	check(character.stat_points > starting_points and character.skill_points == 2,
		"Base levels grant stat points; job levels grant skill points")
	check(character.hp == Rules.derived_stats(character).max_hp and character.sp > 0,
		"Base level-up restores HP and SP")
	var before := character.duplicate(true)
	Rules.grant_exp(character, -1000, -1000)
	check(character == before, "Negative rewards cannot subtract progress or award a level")
	Rules.grant_exp(character, 0, Rules.exp_needed(3, true))
	check(character.base_level == 3 and character.job_level == 4 and character.job_exp == 3,
		"Job-only rewards must not alter base progression")
	character.base_level = Rules.BASE_LEVEL_CAP - 1
	character.job_class = "Swordsman"
	character.job_level = Rules.JOB_LEVEL_CAP - 1
	Rules.grant_exp(character, 2000000000, 2000000000)
	check(character.base_level == Rules.BASE_LEVEL_CAP and character.job_level == Rules.JOB_LEVEL_CAP,
		"Large rewards must stop at caps")
	check(character.base_exp == 0 and character.job_exp == 0, "Cap policy must discard excess EXP")
	check(Rules.exp_needed(Rules.BASE_LEVEL_CAP) == 0 and Rules.exp_needed(Rules.JOB_LEVEL_CAP, true, "Swordsman") == 0,
		"UI must be able to detect capped progression")


func _test_allocation_is_transactional() -> void:
	var character := Rules.default_character()
	var before := character.duplicate(true)
	check(not Rules.spend_stat(character, "hp") and character == before, "Unknown stats must be a no-op")
	character.stat_points = 1
	before = character.duplicate(true)
	check(not Rules.spend_stat(character, "str") and character == before, "Cannot partially spend points")
	character.stat_points = 100
	character.stats.str = Rules.STAT_CAP
	before = character.duplicate(true)
	check(not Rules.spend_stat(character, "str") and character == before, "Capped stats cannot charge points")
	character.stats.vit = 10
	var hp_before: float = character.hp
	check(Rules.spend_stat(character, "vit"), "Valid stat allocation should succeed")
	check(character.stats.vit == 11 and character.stat_points == 98, "10->11 costs two points")
	check(Rules.spend_stat(character, "vit") and character.stat_points == 95, "11->12 raises the price to three points")
	check(character.hp == hp_before, "Allocating VIT does not grant free healing")


func _test_skill_resources() -> void:
	var character := Rules.default_character()
	character.job_class = "Swordsman"
	var before := character.duplicate(true)
	check(not Rules.learn_bash(character) and character == before, "Learning without skill points must be a no-op")
	check(not Rules.try_use_bash(character).success and character == before, "An unlearned skill cannot spend SP")
	character.skill_points = 10
	check(Rules.learn_bash(character) and character.skills.bash == 1 and character.skill_points == 9,
		"Learning a skill consumes exactly one point")
	character.sp = 7.0
	before = character.duplicate(true)
	check(not Rules.try_use_bash(character).success and character == before, "Insufficient SP must reject atomically")
	character.sp = 8.0
	var cast := Rules.try_use_bash(character)
	check(cast.success and cast.cost == 8 and character.sp == 0.0 and cast.multiplier > 1.0,
		"Exact SP allows one cast and never makes SP negative")
	for _index in range(9):
		Rules.learn_bash(character)
	character.skill_points = 1
	before = character.duplicate(true)
	check(not Rules.learn_bash(character) and character == before, "Max-rank skills cannot consume points")
	check(Rules.bash_cost(5) == 8 and Rules.bash_cost(6) == 15,
		"Bash crosses the documented SP-cost boundary")


func _test_novice_and_job_identity() -> void:
	var character := Rules.default_character()
	check(character.job_class == "Novice" and character.skills.first_aid == 1 and character.skills.bash == 0,
		"Starting identity is a novice with First Aid, not a swordsman with Bash")
	character.skill_points = 10
	var before := character.duplicate(true)
	check(not Rules.learn_bash(character) and character == before, "Novice skill points cannot purchase Bash")
	check(not Rules.change_job(character) and character == before, "Job change requires novice job level ten")
	check(not Rules.try_first_aid(character).success and character == before, "Full HP does not waste First Aid SP")
	character.hp -= 2.0
	character.sp = 3.0
	var first_aid := Rules.try_first_aid(character)
	check(first_aid.success and first_aid.cost == 3 and first_aid.healed == 2.0 and character.sp == 0.0,
		"First Aid clamps a five-HP heal and spends three SP atomically")
	character.hp = 1.0
	before = character.duplicate(true)
	check(not Rules.try_first_aid(character).success and character == before, "First Aid cannot run without SP")
	Rules.grant_exp(character, 0, 100000)
	check(character.job_level == 10 and character.job_exp == 0 and Rules.exp_needed(10, true) == 0,
		"Novice job progression must stop at ten")
	before = character.duplicate(true)
	check(Rules.change_job(character), "A trained novice can become a Swordsman")
	check(character.job_class == "Swordsman" and character.job_level == 1 and character.job_exp == 0 and character.skill_points == 0,
		"Job change starts the new class at job one without inherited skill points")
	check(character.base_level == before.base_level and character.stats == before.stats and character.inventory == before.inventory,
		"Job change preserves base progression, stats and inventory")
	check(not Rules.change_job(character), "Job change cannot reset the same class repeatedly")
	Rules.grant_exp(character, 0, 30)
	check(character.job_level == 2 and character.skill_points == 1 and Rules.learn_bash(character),
		"The new Swordsman earns and spends a real job point on Bash")


func _test_combat_distribution() -> void:
	var attacker: Dictionary = {"attack": 20, "attack_min": 10, "attack_max": 20, "hit": 20, "critical": 0.0}
	var defender: Dictionary = {"defense": 2, "flee": 20}
	var rng := RandomNumberGenerator.new()
	var replay := RandomNumberGenerator.new()
	rng.seed = 112358
	replay.seed = 112358
	var hits := 0
	var values: Dictionary = {}
	for _index in range(2000):
		var result := Rules.resolve_attack(attacker, defender, rng)
		var repeated := Rules.resolve_attack(attacker, defender, replay)
		if result != repeated:
			check(false, "Injected RNG must reproduce combat exactly")
			return
		if result.hit:
			hits += 1
			values[result.damage] = true
			if result.damage < 8 or result.damage > 18:
				check(false, "Normal damage escaped the weapon/defense bounds")
				return
		elif result.damage != 0:
			check(false, "Misses must do zero damage")
			return
	check(hits > 1500 and hits < 1700, "Equal hit/flee should produce a statistical mix near 80% hits")
	check(values.size() >= 8, "Weapon damage must have a real distribution")
	check(attacker.attack == 20 and defender.defense == 2, "Resolving combat must not mutate profiles")


func _test_combat_boundaries() -> void:
	check(is_equal_approx(Rules.hit_chance({"hit": -100000}, {"flee": 100000}), 0.05), "Hit chance has a floor")
	check(is_equal_approx(Rules.hit_chance({"hit": 100000}, {"flee": -100000}), 0.95), "Hit chance has a ceiling")
	var rng := RandomNumberGenerator.new()
	rng.seed = 42
	var critical := Rules.resolve_attack({"attack": 10, "hit": -10000, "critical": 100.0}, {"flee": 10000}, rng)
	check(critical.hit and critical.critical and critical.damage == 14, "Guaranteed crits bypass the normal hit roll")
	var armored := Rules.resolve_attack({"attack": 1, "critical": 100.0}, {"defense": 100000}, rng)
	check(armored.hit and armored.damage == 1, "Connected hits have a one-damage floor")
	var stronger := Rules.resolve_attack({"attack": 10, "critical": 100.0}, {}, rng, 2.0)
	check(stronger.damage > critical.damage, "Skills must increase connected damage")


func _test_monster_profiles() -> void:
	var poring := Rules.monster_def("poring")
	var lunatic := Rules.monster_def("lunatic")
	check(not poring.aggro and not lunatic.aggro, "Starting monsters are peaceful before provocation")
	check(poring.hp == 50 and lunatic.hp == 60, "Early monsters use inspected reference HP")
	check(lunatic.walk_speed > poring.walk_speed and lunatic.attack_interval < poring.attack_interval,
		"Lunatics must feel quicker, not be a recolored Poring")
	check(lunatic.base_exp > poring.base_exp and poring.drop != lunatic.drop, "Species have different rewards")
	poring.stats.attack = 999
	check(Rules.monster_def("poring").stats.attack < 999, "Monster instances must not share combat profiles")
	check(Rules.monster_def("unknown").is_empty() and Rules.item_def("unknown").is_empty(), "Unknown database IDs are explicit")
