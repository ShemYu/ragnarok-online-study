extends RefCounted
## Pure local RPG rules: no scene, frame timing, input, files, or networking.
## Dictionaries returned by the factories are independent. Mutators explicitly
## accept a character Dictionary; other functions leave their arguments alone.
##
## This is an educational PRE-RENEWAL-INSPIRED model, not the official RO engine.
## Primary reference inspected 2026-09-23:
## https://github.com/rathena/rathena/blob/master/src/map/status.cpp
##   status_base_amotion_pc: AGI/DEX reduce weapon delay; status_calc_misc:
##   pre-renewal hit = level + DEX, flee = level + AGI; STR affects base ATK.
## https://github.com/rathena/rathena/blob/master/db/pre-re/mob_db.yml
##   Poring/Lunatic HP, attack range, EXP, attack delays and common drop identities.
## https://github.com/rathena/rathena/blob/master/db/pre-re/job_exp.yml
##   Early base and novice job EXP thresholds.
## https://github.com/rathena/rathena/blob/master/db/pre-re/skill_db.yml
##   Bash max level 10 and SP cost 8 (levels 1-5) / 15 (levels 6-10).
##
## Deliberate simplifications: one weapon slot; no size/element/armor multipliers;
## HP/SP curves, damage variance, critical damage and late EXP are our own balance.
## The first job path is Novice -> Swordsman at novice job level 10. First Aid
## is available to the novice; Bash is restricted to the Swordsman class.

const STAT_NAMES = ["str", "agi", "vit", "int", "dex", "luk"]
const BASE_LEVEL_CAP = 99
const JOB_LEVEL_CAP = 50
const STAT_CAP = 99
const BASH_LEVEL_CAP = 10
const MIN_HIT_CHANCE = 0.05
const MAX_HIT_CHANCE = 0.95
const BASE_EXP_EARLY = [9, 16, 25, 36, 77, 112, 153, 200, 253, 320]
const JOB_EXP_EARLY = [10, 18, 28, 40, 91, 151, 205, 268, 340]
const SWORDSMAN_JOB_EXP_EARLY = [30, 43, 58, 76, 116, 180, 220, 272, 336, 520]

## The world owns wind-up/hit/recovery state. Resolve damage once at this point
## in each animation, not immediately when selecting a target. A cancelled
## wind-up must never deliver a late hit to another target.
const ATTACK_HIT_FRACTION = 0.45
const ATTACK_ANIMATION_MAX_SECONDS = 0.72
const HIT_STOP_SECONDS = 0.10
const POTION_COOLDOWN_SECONDS = 0.75
const REGEN_TICK_SECONDS = 2.0


static func default_character() -> Dictionary:
	var character: Dictionary = {
		"base_level": 1, "base_exp": 0, "job_level": 1, "job_exp": 0, "job_class": "Novice",
		"hp": 0.0, "sp": 0.0,
		"stats": {"str": 5, "agi": 5, "vit": 5, "int": 3, "dex": 7, "luk": 1},
		"stat_points": 6, "skill_points": 0,
		"inventory": {"red_potion": 8, "jellopy": 0, "knife": 1, "clover": 0},
		"equipped_weapon": "knife", "skills": {"first_aid": 1, "bash": 0},
	}
	var derived := derived_stats(character)
	character.hp = float(derived.max_hp)
	character.sp = float(derived.max_sp)
	return character


## Displayed critical is percent (e.g. 3.0 = 3%). Intervals are seconds;
## walk_speed is Godot world units per second, independent of attack speed.
static func derived_stats(character: Dictionary) -> Dictionary:
	var stats: Dictionary = character.get("stats", {})
	var base_level := clampi(int(character.get("base_level", 1)), 1, BASE_LEVEL_CAP)
	var strength := clampi(int(stats.get("str", 1)), 1, STAT_CAP)
	var agility := clampi(int(stats.get("agi", 1)), 1, STAT_CAP)
	var vitality := clampi(int(stats.get("vit", 1)), 1, STAT_CAP)
	var intelligence := clampi(int(stats.get("int", 1)), 1, STAT_CAP)
	var dexterity := clampi(int(stats.get("dex", 1)), 1, STAT_CAP)
	var luck := clampi(int(stats.get("luk", 1)), 1, STAT_CAP)
	var weapon := item_def(str(character.get("equipped_weapon", "")))
	var weapon_attack := int(weapon.get("attack", 0))
	var strength_bonus := int(strength / 10.0)
	var base_attack := strength + strength_bonus * strength_bonus + int(dexterity / 5.0) + int(luck / 5.0)
	var attack := base_attack + weapon_attack
	var attack_min := base_attack + int(round(weapon_attack * clampf(0.65 + dexterity * 0.01, 0.65, 1.0)))
	# Same proportional AGI/DEX influence as the pre-renewal reference, with our
	# practice dagger's 1.4-second base cycle. No exact class/weapon table claim.
	var attack_interval := clampf(1.4 * (1.0 - (4.0 * agility + dexterity) / 1000.0), 0.40, 1.4)
	return {
		"max_hp": int(round((50.0 + base_level * 10.0) * (1.0 + vitality / 100.0))),
		"max_sp": int(round((10.0 + base_level * 3.0) * (1.0 + intelligence / 100.0))),
		"attack": attack, "attack_min": attack_min, "attack_max": attack,
		"defense": int(vitality / 2.0), "hit": base_level + dexterity,
		"flee": base_level + agility, "critical": 1.0 + luck * 0.3,
		"critical_resist": luck * 0.2,
		"aspd": 200.0 - attack_interval / 0.02,
		"attack_interval": attack_interval, "walk_speed": 3.6,
	}


## Cost to reach the next level, not accumulated lifetime EXP. Returns 0 at cap.
## The first ten base levels and nine novice job levels use the reference data;
## beyond them our smooth training curve permits continued local progression.
static func exp_needed(level: int, job: bool = false, job_class: String = "Novice") -> int:
	level = maxi(1, level)
	if level >= (job_level_cap(job_class) if job else BASE_LEVEL_CAP):
		return 0
	var thresholds: Array = JOB_EXP_EARLY if job else BASE_EXP_EARLY
	if job and job_class == "Swordsman":
		thresholds = SWORDSMAN_JOB_EXP_EARLY
	if level <= thresholds.size():
		return int(thresholds[level - 1])
	if job:
		return int(round(520.0 * pow(level / 10.0, 2.4)))
	return int(round(320.0 * pow(level / 10.0, 2.6)))


static func job_level_cap(job_class: String = "Novice") -> int:
	return JOB_LEVEL_CAP if job_class == "Swordsman" else 10


## Mutates only progression and (on a base level-up) HP/SP. All overflow carries
## through multiple levels. EXP at a level cap is intentionally discarded.
static func grant_exp(character: Dictionary, base_amount: int, job_amount: int) -> Dictionary:
	var outcome: Dictionary = {"base_levels": 0, "job_levels": 0,
		"stat_points_gained": 0, "skill_points_gained": 0}
	character.base_exp = maxi(0, int(character.get("base_exp", 0))) + maxi(0, base_amount)
	character.job_exp = maxi(0, int(character.get("job_exp", 0))) + maxi(0, job_amount)
	var job_class := str(character.get("job_class", "Novice"))
	var job_cap := job_level_cap(job_class)
	character.base_level = clampi(int(character.get("base_level", 1)), 1, BASE_LEVEL_CAP)
	character.job_level = clampi(int(character.get("job_level", 1)), 1, job_cap)
	while character.base_level < BASE_LEVEL_CAP:
		var threshold := exp_needed(int(character.base_level))
		if character.base_exp < threshold:
			break
		character.base_exp -= threshold
		character.base_level += 1
		var points := 3 + int((int(character.base_level) - 1) / 5.0)
		character.stat_points = int(character.get("stat_points", 0)) + points
		outcome.stat_points_gained += points
		outcome.base_levels += 1
	while character.job_level < job_cap:
		var threshold := exp_needed(int(character.job_level), true, job_class)
		if character.job_exp < threshold:
			break
		character.job_exp -= threshold
		character.job_level += 1
		character.skill_points = int(character.get("skill_points", 0)) + 1
		outcome.skill_points_gained += 1
		outcome.job_levels += 1
	if character.base_level >= BASE_LEVEL_CAP:
		character.base_exp = 0
	if character.job_level >= job_cap:
		character.job_exp = 0
	if outcome.base_levels > 0:
		var derived := derived_stats(character)
		character.hp = float(derived.max_hp)
		character.sp = float(derived.max_sp)
	return outcome


## Each +1 costs more every ten points: 1..10 costs 2, 11..20 costs 3, etc.
static func stat_cost(current_value: int) -> int:
	return 2 + int(maxi(0, current_value - 1) / 10.0)


## Invalid stat names, capped stats, and insufficient points leave state intact.
static func spend_stat(character: Dictionary, stat: String) -> bool:
	if stat not in STAT_NAMES:
		return false
	var stats: Dictionary = character.get("stats", {})
	if not stats.has(stat):
		return false
	var current := int(stats[stat])
	var points := int(character.get("stat_points", 0))
	var cost := stat_cost(current)
	if current < 1 or current >= STAT_CAP or points < cost:
		return false
	stats[stat] = current + 1
	character.stat_points = points - cost
	# Raising maximum HP/SP does not heal: the extra capacity is filled by rest.
	return true


static func learn_bash(character: Dictionary) -> bool:
	if str(character.get("job_class", "Novice")) != "Swordsman":
		return false
	var skills: Dictionary = character.get("skills", {})
	var level := int(skills.get("bash", 0))
	if int(character.get("skill_points", 0)) < 1 or level < 0 or level >= BASH_LEVEL_CAP:
		return false
	character.skill_points -= 1
	skills.bash = level + 1
	character.skills = skills
	return true


static func bash_cost(level: int) -> int:
	if level <= 0:
		return 0
	return 8 if level <= 5 else 15


static func bash_multiplier(level: int) -> float:
	return 1.0 + 0.3 * clampi(level, 0, BASH_LEVEL_CAP)


## Call exactly once when the world commits a skill wind-up after checking range
## and actor state. Queueing a skill or pressing a key must not consume SP.
static func try_use_bash(character: Dictionary) -> Dictionary:
	var level := int(character.get("skills", {}).get("bash", 0))
	var cost := bash_cost(level)
	if str(character.get("job_class", "Novice")) != "Swordsman" or level <= 0 or level > BASH_LEVEL_CAP or float(character.get("sp", 0.0)) < cost:
		return {"success": false, "cost": 0, "multiplier": 1.0}
	character.sp = float(character.sp) - cost
	return {"success": true, "cost": cost, "multiplier": bash_multiplier(level)}


## First Aid: 3 SP -> up to 5 HP. Full HP, no skill or insufficient SP is a
## complete no-op. Actor death/animation state and cooldowns belong to the world.
static func try_first_aid(character: Dictionary) -> Dictionary:
	var maximum := float(derived_stats(character).max_hp)
	var current := float(character.get("hp", 0.0))
	if int(character.get("skills", {}).get("first_aid", 0)) < 1 or current <= 0.0 or current >= maximum or float(character.get("sp", 0.0)) < 3.0:
		return {"success": false, "cost": 0, "healed": 0.0}
	var healed := minf(5.0, maximum - current)
	character.hp = current + healed
	character.sp = float(character.sp) - 3.0
	return {"success": true, "cost": 3, "healed": healed}


## The trainer is the world interaction; this function is the eligibility gate.
## Job change keeps base level, allocated stats, resources, equipment and items.
static func change_job(character: Dictionary) -> bool:
	if str(character.get("job_class", "Novice")) != "Novice" or int(character.get("job_level", 1)) < 10:
		return false
	character.job_class = "Swordsman"
	character.job_level = 1
	character.job_exp = 0
	character.skill_points = 0
	return true


## Normal hit roll, including sensible caps so extreme stats never hard-lock
## combat. Crits are rolled separately by resolve_attack and bypass this roll.
static func hit_chance(attacker_stats: Dictionary, defender_stats: Dictionary) -> float:
	return clampf((80.0 + float(attacker_stats.get("hit", 1)) - float(defender_stats.get("flee", 1))) / 100.0,
		MIN_HIT_CHANCE, MAX_HIT_CHANCE)


## No mutation; inject RandomNumberGenerator to reproduce combat in tests/replay.
## Misses do zero damage. Connected attacks always do at least one. Crits use
## the upper attack bound, bypass hit rolls, and deal 1.4x before flat defense.
static func resolve_attack(attacker_stats: Dictionary, defender_stats: Dictionary,
		rng: RandomNumberGenerator, skill_multiplier: float = 1.0) -> Dictionary:
	var chance := hit_chance(attacker_stats, defender_stats)
	var crit_chance := clampf((float(attacker_stats.get("critical", 0.0)) - float(defender_stats.get("critical_resist", 0.0))) / 100.0, 0.0, 1.0)
	var critical := rng.randf() < crit_chance
	if not critical and rng.randf() >= chance:
		return {"hit": false, "critical": false, "damage": 0, "hit_chance": chance}
	var attack := maxi(1, int(attacker_stats.get("attack", 1)))
	var low := maxi(1, int(attacker_stats.get("attack_min", floori(attack * 0.85))))
	var high := maxi(low, int(attacker_stats.get("attack_max", attack)))
	var rolled := high if critical else rng.randi_range(low, high)
	var damage := int(round(rolled * maxf(0.0, skill_multiplier) * (1.4 if critical else 1.0)))
	damage = maxi(1, damage - maxi(0, int(defender_stats.get("defense", 0))))
	return {"hit": true, "critical": critical, "damage": damage, "hit_chance": chance}


## Each monster owns its return dictionary; using one as a live instance will
## never change later spawns. Monster criticals are disabled in this first field.
static func monster_def(id: String) -> Dictionary:
	match id:
		"poring", "slime":
			return {
				"id": "poring", "name": "Poring", "visual": "slime", "level": 1,
				"hp": 50, "max_hp": 50, "base_exp": 2, "job_exp": 1,
				"walk_speed": 1.4, "attack_interval": 1.872, "aggro": false,
				"drop": "jellopy", "drop_chance": 0.70, "respawn_seconds": 12.0,
				"stats": {"max_hp": 50, "attack": 10, "attack_min": 7, "attack_max": 10,
					"defense": 1, "hit": 7, "flee": 2, "critical": 0.0,
					"critical_resist": 6.0, "attack_interval": 1.872, "walk_speed": 1.4},
			}
		"lunatic":
			return {
				"id": "lunatic", "name": "Lunatic", "visual": "lunatic", "level": 3,
				"hp": 60, "max_hp": 60, "base_exp": 6, "job_exp": 2,
				"walk_speed": 2.25, "attack_interval": 1.456, "aggro": false,
				"drop": "clover", "drop_chance": 0.65, "respawn_seconds": 15.0,
				"stats": {"max_hp": 60, "attack": 12, "attack_min": 9, "attack_max": 12,
					"defense": 2, "hit": 11, "flee": 6, "critical": 0.0,
					"critical_resist": 12.0, "attack_interval": 1.456, "walk_speed": 2.25},
			}
	return {}


static func item_def(id: String) -> Dictionary:
	match id:
		"red_potion":
			return {"id": id, "name": "Red Potion", "type": "consumable", "heal": 55,
				"heal_min": 45, "heal_max": 65, "description": "Restores 45-65 HP."}
		"jellopy":
			return {"id": id, "name": "Jellopy", "type": "material", "sell": 3,
				"description": "A small crystal dropped by Porings."}
		"clover":
			return {"id": id, "name": "Clover", "type": "material", "sell": 5,
				"description": "A soft field herb carried by Lunatics."}
		"knife":
			return {"id": id, "name": "Knife", "type": "weapon", "equipment": true,
				"slot": "weapon", "attack": 17, "description": "A beginner's dagger. ATK +17."}
	return {}
