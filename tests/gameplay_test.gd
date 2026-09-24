extends RefCounted
## Integration checks run against the real scene with: Godot --headless --path . -- --qa
## Disable automatic simulation while advancing the real game commands/timers.
## Save/load uses a unique disposable fixture; the player's save is never written.

const Rules = preload("res://scripts/rpg_rules.gd")
var checks := 0
var failures := 0
var _game


func run(game) -> void:
	_game = game
	_game.set_process(false)
	var original_save_path: String = _game.save_path
	var original_save_enabled: bool = _game.save_enabled
	var original_hash := FileAccess.get_sha256(original_save_path) if FileAccess.file_exists(original_save_path) else "missing"
	_game.save_enabled = false
	await _game.get_tree().process_frame
	_test_delayed_and_cancelled_attacks()
	_test_monster_retaliation()
	_test_potions_and_first_aid()
	_test_equipment_and_allocation()
	_test_class_skill_commands()
	_test_trainer_course()
	_test_death_respawn_and_pickup()
	_test_player_death_and_return()
	_test_save_roundtrip()
	_game.save_path = original_save_path
	_game.save_enabled = original_save_enabled
	var final_hash := FileAccess.get_sha256(original_save_path) if FileAccess.file_exists(original_save_path) else "missing"
	check(original_hash == final_hash, "Integration checks must not change the player's save")
	await _game.get_tree().process_frame
	if failures == 0:
		print("GAMEPLAY_V2_TEST_PASS (%d checks)" % checks)
	else:
		push_error("GAMEPLAY_V2_TEST_FAIL: %d of %d checks" % [failures, checks])
	_game.get_tree().quit(1 if failures > 0 else 0)


func check(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(message)


func _reset() -> void:
	_game.save_enabled = false
	_game._cancel_target()
	_game.dead = false
	_game.sitting = false
	_game.character = Rules.default_character()
	_game.quest = {"active": false, "complete": false, "claimed": false, "poring": 0, "lunatic": 0}
	_game.kills = 0
	_game.attack_timer = 0.0
	_game.attack_pose = 0.0
	_game.potion_timer = 0.0
	_game.regen_timer = 0.0
	_game.hit_stun = 0.0
	_game.death_timer = 0.0
	_game.player.configure("novice")
	_game.player.position = Vector3.ZERO
	_game._refresh_derived()
	_game.rng.seed = 7331
	_game.hud.close_panels()
	while not _game.drops.is_empty():
		_game._remove_drop(_game.drops.size() - 1)
	_game._update_floating_text(10.0)
	for mob: Dictionary in _game.monsters:
		mob.def = Rules.monster_def(mob.id)
		mob.hp = float(mob.def.hp)
		mob.max_hp = float(mob.def.max_hp)
		mob.alive = true
		mob.aggro = false
		mob.cooldown = 999.0
		mob.windup = 0.0
		mob.stun = 0.0
		mob.pose = 0.0
		mob.death_pose = 0.0
		mob.respawn = 0.0
		mob.returning = false
		mob.generation = 0
		mob.wander = 999.0
		mob.route = []
		mob.repath = 0.0
		mob.visual.position = mob.spawn
		mob.visual.visible = true
		mob.visual.set_selected(false)
		mob.visual.set_state("idle")
	_game._update_hud()


func _prepare_target(index: int = 0) -> void:
	_game.monsters[index].visual.position = _game.player.position + Vector3(0.9, 0, 0)
	# Guarantee a connecting strike independently of RNG seed or base-stat balance.
	_game.derived.critical = 1000.0
	_game.select_monster(index)


func _test_delayed_and_cancelled_attacks() -> void:
	_reset()
	_prepare_target()
	var original_hp: float = _game.monsters[0].hp
	check(original_hp == _game.monsters[0].max_hp, "Selecting a target must not deal damage")
	_game._start_attack(0)
	var hit_time: float = _game.pending_attack.remaining
	check(hit_time > 0.0 and _game.attack_timer > hit_time, "Attack command must schedule wind-up and recovery")
	check(_game.monsters[0].hp == original_hp and not _game.monsters[0].aggro, "Starting a swing cannot apply damage early")
	_game._advance_attack(hit_time * 0.99)
	check(_game.monsters[0].hp == original_hp, "Damage must wait until the actual hit point")
	_game._advance_attack(hit_time * 0.02)
	var after_hit: float = _game.monsters[0].hp
	check(after_hit < original_hp and _game.monsters[0].aggro, "The hit point must deliver damage and provoke its target")
	_game._advance_attack(2.0)
	check(_game.monsters[0].hp == after_hit and _game.pending_attack.is_empty(), "One swing cannot deliver duplicate damage")

	_reset()
	_prepare_target()
	_game._start_attack(0)
	original_hp = _game.monsters[0].hp
	_game.move_to(Vector3(0, 0, 3))
	_game._advance_attack(2.0)
	check(_game.selected_id == -1 and _game.pending_attack.is_empty(), "A movement command must cancel target and wind-up")
	check(_game.monsters[0].hp == original_hp and not _game.path.is_empty(), "Cancelled swings cannot hit while the player walks away")

	_reset()
	_prepare_target()
	_game._start_attack(0)
	original_hp = _game.monsters[0].hp
	_game.select_monster(1)
	_game._advance_attack(2.0)
	check(_game.monsters[0].hp == original_hp and _game.monsters[1].hp == _game.monsters[1].max_hp,
		"Switching targets must not redirect an old swing to the new monster")

	_reset()
	_prepare_target()
	_game._start_attack(0)
	original_hp = _game.monsters[0].hp
	_game.monsters[0].generation += 1
	_game._advance_attack(2.0)
	check(_game.monsters[0].hp == original_hp and not _game.monsters[0].aggro,
		"A stale strike must not damage another spawn generation in the same slot")

	_reset()
	_prepare_target()
	_game._start_attack(0)
	original_hp = _game.monsters[0].hp
	_game.monsters[0].visual.position += Vector3(5, 0, 0)
	_game._advance_attack(2.0)
	check(_game.monsters[0].hp == original_hp and _game.pending_attack.is_empty(), "Leaving reach before impact must avoid the hit")
	_game._cancel_target()
	_game.select_monster(_game.monsters.size())
	_game._start_attack(_game.monsters.size())
	check(_game.selected_id == -1 and _game.pending_attack.is_empty(), "Stale out-of-bounds targets must be rejected")


func _test_monster_retaliation() -> void:
	_reset()
	var mob: Dictionary = _game.monsters[0]
	mob.visual.position = Vector3(0.9, 0, 0)
	mob.aggro = true
	mob.cooldown = 0.0
	mob.def.stats.critical = 1000.0
	var original_hp: float = _game.hp
	_game._update_monsters(0.01)
	check(mob.windup > 0.0 and _game.hp == original_hp, "Monster retaliation must have a visible wind-up")
	_game._update_monsters(0.10)
	check(_game.hp == original_hp, "A monster cannot damage the player before its impact")
	_game._update_monsters(0.13)
	var after_hit: float = _game.hp
	check(after_hit < original_hp and _game.hit_stun > 0.0, "Monster impact must cause damage and hit reaction")
	_game._update_monsters(0.05)
	check(_game.hp == after_hit, "Monster wind-up must resolve only once")
	mob.pose = 0.0
	mob.cooldown = 0.0
	_game._update_monsters(0.01)
	_game.player.position += Vector3(4, 0, 0)
	_game._update_monsters(0.24)
	check(_game.hp == after_hit, "Walking out of monster reach before impact must avoid retaliation")


func _test_potions_and_first_aid() -> void:
	_reset()
	var original_count: int = _game.character.inventory.red_potion
	_game.hud.potion_requested.emit()
	check(_game.character.inventory.red_potion == original_count and _game.potion_timer == 0.0,
		"The real potion command cannot consume a potion at full HP")
	_game.hp = 1.0
	_game.hud.potion_requested.emit()
	check(_game.hp > 1.0 and _game.hp <= _game.max_hp and _game.character.inventory.red_potion == original_count - 1,
		"Potion UI command must heal within maximum HP and consume exactly one item")
	_game.hp = 1.0
	_game.use_potion()
	check(_game.hp == 1.0 and _game.character.inventory.red_potion == original_count - 1,
		"Potion cooldown prevents repeated immediate consumption")
	_game.dead = true
	_game.potion_timer = 0.0
	_game.use_potion()
	check(_game.hp == 1.0 and _game.character.inventory.red_potion == original_count - 1,
		"Potions cannot revive a knocked-out actor")

	_reset()
	_game.hp = _game.max_hp - 4.0
	_game.sp = 10.0
	_game.hud.first_aid_requested.emit()
	check(_game.hp == _game.max_hp and _game.sp == 7.0 and _game.attack_pose > 0.0,
		"First Aid UI command must charge SP, clamp healing and play its action")
	_game.hp -= 5.0
	_game.use_first_aid()
	check(_game.sp == 7.0 and _game.hp == _game.max_hp - 5.0,
		"The active cast animation must prevent duplicate First Aid casts")
	_game.attack_pose = 0.0
	_game.sp = 2.0
	_game.use_first_aid()
	check(_game.sp == 2.0 and _game.hp == _game.max_hp - 5.0, "Insufficient SP must leave First Aid resources untouched")


func _test_equipment_and_allocation() -> void:
	_reset()
	var armed_attack: int = _game.derived.attack
	_game.hud.equip_requested.emit()
	check(_game.character.equipped_weapon == "" and not _game.player.weapon_visible and _game.derived.attack < armed_attack,
		"Unequipping must update data, damage and the actual weapon overlay")
	_game.hud.equip_requested.emit()
	check(_game.character.equipped_weapon == "knife" and _game.player.weapon_visible and _game.derived.attack == armed_attack,
		"Equipping must restore both damage and the weapon overlay")
	_game.character.inventory.knife = 0
	_game.character.equipped_weapon = ""
	_game._refresh_derived()
	_game.toggle_weapon()
	check(_game.character.equipped_weapon == "" and not _game.player.weapon_visible, "A missing weapon cannot be equipped through a command")
	var attack_before: int = _game.derived.attack
	var points_before: int = _game.character.stat_points
	_game.hud.stat_requested.emit("str")
	check(_game.character.stats.str == 6 and _game.character.stat_points < points_before and _game.derived.attack > attack_before,
		"Stat UI command must spend points and refresh the combat profile immediately")


func _test_class_skill_commands() -> void:
	_reset()
	_game.character.skill_points = 10
	_game.hud.learn_bash_requested.emit()
	check(_game.character.skills.bash == 0 and _game.character.skill_points == 10, "Novice cannot learn Swordsman Bash through the HUD signal")
	_prepare_target()
	_game.queue_bash()
	check(_game.next_skill == "", "An unlearned skill cannot enter the attack queue")
	_game.character.job_class = "Swordsman"
	_game.character.skill_points = 1
	_game.hud.learn_bash_requested.emit()
	check(_game.character.skills.bash == 1 and _game.character.skill_points == 0, "A Swordsman can train Bash with a job point")
	var sp_before: float = _game.sp
	_game.hud.bash_requested.emit()
	check(_game.next_skill == "bash" and _game.sp == sp_before, "Queueing Bash must not consume SP before an attack starts")
	_game._start_attack(0)
	check(_game.sp == sp_before - 8.0 and _game.pending_attack.skill == "bash" and _game.pending_attack.multiplier > 1.0,
		"Starting Bash commits its cost once and stores the skill on that swing")
	_game._advance_attack(2.0)
	check(_game.sp == sp_before - 8.0, "Delivering Bash must not charge its cost a second time")
	_game._cancel_target()
	_game.queue_bash()
	check(_game.next_skill == "" and _game.sp == sp_before - 8.0, "Bash without a selected target must not queue or spend SP")


func _kill_target(index: int) -> void:
	_game.attack_pose = 0.0
	_game.attack_timer = 0.0
	_game.player.position = _game.monsters[index].visual.position + Vector3(0.75, 0, 0)
	_game.monsters[index].hp = 1.0
	_game.derived.critical = 1000.0
	_game.select_monster(index)
	_game._start_attack(index)
	_game._advance_attack(2.0)


func _test_trainer_course() -> void:
	_reset()
	_game.player.position = Vector3(-3, 0, 3)
	_game.hud.trainer_requested.emit()
	check(_game.hud._dialog.visible, "Talking to the nearby guide must open a real conversation")
	_game.hud._dialog_actions.get_child(0).pressed.emit()
	check(_game.quest.active and not _game.hud._dialog.visible, "Accepting the dialogue action starts the actual training quest")
	for index in [0, 1, 2, 3, 4]:
		_kill_target(index)
	check(_game.quest.poring == 3 and _game.quest.lunatic == 2 and _game.quest.complete and _game.kills == 5,
		"Combat kills must independently count both required monster species")
	var potions_before: int = _game.character.inventory.red_potion
	_game.player.position = Vector3(10, 0, 10)
	_game._dialog_action("claim")
	check(not _game.quest.claimed and _game.character.inventory.red_potion == potions_before,
		"The reward cannot be claimed remotely by a stale dialogue action")
	_game.player.position = Vector3(-3, 0, 3)
	_game.talk_to_guide()
	_game.hud._dialog_actions.get_child(0).pressed.emit()
	check(_game.quest.claimed and not _game.quest.active and _game.character.inventory.red_potion == potions_before + 5,
		"Claiming completed training awards exactly five potions and closes the quest")
	check(_game.character.job_level == 10 and _game.character.base_level > 1,
		"Training reward must carry through enough levels to unlock the first job")
	var after_reward: Dictionary = _game.character.duplicate(true)
	_game._dialog_action("claim")
	check(_game.character == after_reward, "Training rewards can only be claimed once")
	_game.talk_to_guide()
	_game.hud._dialog_actions.get_child(0).pressed.emit()
	check(_game.character.job_class == "Swordsman" and _game.character.job_level == 1 and _game.character.skill_points == 0,
		"Trainer job change must start Swordsman job progression without novice skill points")
	check(_game.character.base_level == after_reward.base_level and _game.character.stats == after_reward.stats,
		"Job change must preserve base level and allocated stats")
	check(_game.character.skills.bash == 0, "Bash must still be learned after the job change")


func _test_death_respawn_and_pickup() -> void:
	_reset()
	_game.monsters[0].def.drop_chance = 1.0
	_kill_target(0)
	var mob: Dictionary = _game.monsters[0]
	check(not mob.alive and mob.hp == 0.0 and _game.kills == 1 and _game.drops.size() == 1,
		"A lethal timed hit must kill once, award one kill and spawn its drop")
	check(_game.attack_pose > 0.0 and _game.selected_id == -1,
		"Lethal impact must clear targeting without cutting off the player's finishing animation")
	var after_kill: Dictionary = _game.character.duplicate(true)
	_game._defeat_monster(0)
	check(_game.kills == 1 and _game.character == after_kill and _game.drops.size() == 1,
		"An already-dead monster cannot award duplicate XP or loot")
	_game._update_monsters(0.4)
	check(mob.visual.visible and not mob.alive, "Monster death animation should remain visible before despawn")
	_game._update_monsters(0.5)
	check(not mob.visual.visible and not mob.alive, "Dead monsters should disappear while waiting for respawn")
	_game._update_monsters(float(mob.respawn) + 0.01)
	check(mob.alive and mob.visual.visible and mob.hp == mob.max_hp and mob.generation == 1,
		"Respawn must create a fresh target generation with full HP")
	check(mob.visual.position == mob.spawn, "Respawn must return a monster to its assigned spawn position")
	_game.attack_pose = 0.0
	_game.player.position = Vector3(12, 0, 12)
	_game.gather_nearby()
	check(_game.drops.size() == 1 and _game.character.inventory.jellopy == 0, "Gather cannot collect a distant drop")
	_game.player.position = _game.drops[0].base
	_game.hud.pickup_requested.emit()
	check(_game.drops.is_empty() and _game.character.inventory.jellopy == 1 and _game.attack_pose > 0.0,
		"Nearby pickup transfers the item once and plays a movement-blocking pickup action")
	var pickup_position: Vector3 = _game.player.position
	_game.path.append(pickup_position + Vector3(1, 0, 0))
	_game._update_player(0.1)
	check(_game.player.position == pickup_position, "Pickup action must not be overwritten by walking in the same frame")


func _test_player_death_and_return() -> void:
	_reset()
	_prepare_target()
	_game._start_attack(0)
	var mob_hp: float = _game.monsters[0].hp
	_game.monsters[0].aggro = true
	_game.monsters[0].windup = 0.2
	_game._damage_player(_game.max_hp + 10.0)
	check(_game.dead and _game.pending_attack.is_empty() and _game.selected_id == -1 and _game.hp == 0.0,
		"Player knockout must cancel pending combat and targeting")
	check(not _game.monsters[0].aggro and _game.monsters[0].windup == 0.0 and _game.monsters[0].returning,
		"Knockout clears retaliation and sends a displaced monster back to spawn")
	_game._advance_attack(2.0)
	check(_game.monsters[0].hp == mob_hp, "A dead player's cancelled swing cannot deliver damage")
	_game.toggle_rest()
	check(_game.dead and _game.hp == 0.0, "The rest shortcut must not skip the knockout return timer")
	_game._process(4.1)
	check(not _game.dead and _game.hp == _game.max_hp and _game.sp == _game.derived.max_sp,
		"The actual return timer restores HP and SP")
	check(_game.player.position == Vector3(0, 0, 3), "A knocked-out player returns to camp")


func _write_fixture(path: String, contents: Dictionary) -> void:
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify(contents))
		file.close()
	else:
		check(false, "Could not write the isolated save fixture")


func _test_save_roundtrip() -> void:
	_reset()
	var fixture := "user://qa-gameplay-%d.json" % Time.get_ticks_usec()
	_game.save_path = fixture
	_game.save_enabled = true
	_game.character.job_class = "Swordsman"
	_game.character.base_level = 7
	_game.character.base_exp = 11
	_game.character.job_level = 3
	_game.character.job_exp = 17
	_game.character.stat_points = 15
	_game.character.skill_points = 2
	_game.character.stats.str = 11
	_game.character.inventory.red_potion = 3
	_game.character.inventory.jellopy = 9
	_game.character.skills.bash = 2
	_game.quest = {"active": false, "complete": true, "claimed": true, "poring": 3, "lunatic": 2}
	_game.kills = 42
	_game._refresh_derived()
	_game.hp = 1.0
	_game.sp = 1.0
	var expected: Dictionary = _game.character.duplicate(true)
	_game._save_progress()
	check(FileAccess.file_exists(fixture) and not FileAccess.file_exists(fixture + ".tmp"),
		"Saving must atomically replace the isolated fixture and consume the temporary file")
	_game.character = Rules.default_character()
	_game.quest = {"active": false, "complete": false, "claimed": false, "poring": 0, "lunatic": 0}
	_game.kills = 0
	_game._load_progress()
	var actual: Dictionary = _game.character.duplicate(true)
	# Relaunch intentionally restores health at camp instead of saving wounds.
	expected.hp = _game.max_hp
	expected.sp = float(_game.derived.max_sp)
	check(actual == expected, "Save/load must restore class, EXP, allocated stats, points, skills and equipment")
	check(_game.quest.claimed and _game.quest.complete and _game.quest.poring == 3 and _game.quest.lunatic == 2 and _game.kills == 42,
		"Save/load must persist training progress and kill count")
	check(_game.player.weapon_visible, "Loading equipped gear must update the actual actor overlay")
	_write_fixture(fixture, {"version": 999, "character": {"base_level": 99}})
	_game._load_progress()
	check(_game.character == actual, "Unknown save formats must not partially overwrite the character")
	_write_fixture(fixture, {"version": 2, "character": {"base_level": "bad", "stats": null,
		"inventory": [], "skills": 42, "job_class": "Novice", "job_level": 999},
		"quest": {"active": "bad", "claimed": false, "poring": -9, "lunatic": -2, "complete": true}, "kills": -99})
	_game._load_progress()
	check(_game.character.stats is Dictionary and _game.character.inventory is Dictionary and _game.character.skills is Dictionary,
		"Malformed nested save values must not replace valid dictionaries")
	check(_game.character.job_level == 10 and _game.character.skills.bash == 0 and _game.kills == 0,
		"Loaded novice levels, class skills and negative counts must be sanitized")
	check(not _game.quest.complete and _game.quest.poring == 0 and _game.quest.lunatic == 0,
		"Quest completion must follow valid kill counts rather than trusting a saved flag")
	_game.save_enabled = false
	DirAccess.remove_absolute(fixture)
	if FileAccess.file_exists(fixture + ".tmp"):
		DirAccess.remove_absolute(fixture + ".tmp")
	check(not FileAccess.file_exists(fixture), "The isolated save fixture must be removed after verification")
