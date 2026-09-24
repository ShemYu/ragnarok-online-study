extends SceneTree
## A complete adventure through the normal frame loop, without injected damage,
## EXP, stats, teleporting, forced deaths, or skipped attack/respawn timers.
## Run: Godot --headless --path . --script res://tests/progression_playthrough.gd -- --qa-progression
## Commands are the same movement, target, instructor, potion and skill commands
## used by a player. Time scale accelerates the whole simulation equally.

const SCENE = preload("res://scenes/main.tscn")
const WALL_TIMEOUT_SECONDS := 120.0
const REPORT_PATH := "res://docs/v3/progression-playthrough.json"
const RUN_COMMAND := ".tools/Godot.app/Contents/MacOS/Godot --headless --path . --script res://tests/progression_playthrough.gd -- --qa-progression"
var game
var wall_started := 0
var checks := 0
var potion_uses := 0
var natural_kills := 0
var original_save_hash := ""


func _initialize() -> void:
	call_deferred("run")


func run() -> void:
	if "--qa-progression" not in OS.get_cmdline_user_args():
		push_error("Pass -- --qa-progression to keep the playthrough isolated from saved progress.")
		quit(1)
		return
	Engine.time_scale = 8.0
	Engine.max_fps = 120
	wall_started = Time.get_ticks_msec()
	game = SCENE.instantiate()
	game.save_enabled = false
	root.add_child(game)
	await process_frame
	original_save_hash = _save_hash()
	if not _check(not game.save_enabled and game.character.base_level == 1 and game.character.job_level == 1
		and game.character.job_class == "Novice" and game.kills == 0, "Adventure must start from a fresh, isolated novice"):
		return
	_log("Fresh novice; walking to the instructor")
	if not await _instructor("accept", "Begin training"):
		return
	if not _check(game.quest.active, "The normal conversation must start training"):
		return
	while int(game.quest.poring) < 3:
		if not await _fight_species("poring"):
			return
	while int(game.quest.lunatic) < 2:
		if not await _fight_species("lunatic"):
			return
	if not _check(game.quest.complete and game.kills == 5, "Five natural combat kills must complete the two-species course"):
		return
	_log("Training course completed through combat")
	var potions_before: int = game.character.inventory.red_potion
	if not await _instructor("claim", "Claim reward"):
		return
	if not _check(game.quest.claimed and game.character.inventory.red_potion == potions_before + 5,
		"Instructor reward must be claimed once after the actual course"):
		return
	if not _check(game.character.job_level == 10, "Training must unlock novice job level ten"):
		return
	var base_before: int = game.character.base_level
	var stats_before: Dictionary = game.character.stats.duplicate()
	if not await _instructor("change_job", "Become Swordsman"):
		return
	if not _check(game.character.job_class == "Swordsman" and game.character.job_level == 1
		and game.character.skill_points == 0 and game.character.skills.bash == 0,
		"Real job change must reset job progression and leave Bash to be learned"):
		return
	if not _check(game.character.base_level == base_before and game.character.stats == stats_before,
		"Job change must preserve earned base level and stats"):
		return
	_log("Swordsman reached; earning the first skill point from normal monster EXP")
	var kills_at_change: int = game.kills
	while int(game.character.job_level) < 2:
		if int(game.character.inventory.red_potion) == 0 or float(game.hp) < float(game.max_hp) * 0.35:
			if not await _instructor("heal", "Restock and heal"):
				return
		if not await _fight_species("lunatic"):
			return
		if (int(game.kills) - kills_at_change) % 3 == 0:
			_log("Swordsman training: %d natural kills since promotion" % (int(game.kills) - kills_at_change))
	if not _check(game.character.skill_points == 1 and int(game.kills) - kills_at_change == 15,
		"Thirty normal Lunatic job EXP must earn one Swordsman skill point without accelerated rewards"):
		return
	game.learn_bash()
	if not _check(game.character.skills.bash == 1 and game.character.skill_points == 0,
		"The naturally earned job point must train Bash"):
		return
	_log("Bash learned through progression; validating its actual attack")
	var landed_bash := false
	for attempt in range(4):
		if not await _instructor("heal", "Restock and heal"):
			return
		var index: int = await _find_living_target("lunatic")
		if index < 0:
			return
		var initial_hp: float = game.monsters[index].hp
		var initial_sp: float = game.sp
		var initial_kills: int = game.kills
		game.select_monster(index)
		game.queue_bash()
		if not _check(game.next_skill == "bash" and game.sp == initial_sp, "Queueing a learned Bash must preserve SP until the swing starts"):
			return
		if not await _wait(func() -> bool:
			return not game.pending_attack.is_empty() and game.pending_attack.get("skill", "") == "bash",
			90.0, "approach and start Bash"):
			return
		if not _check(is_equal_approx(float(game.sp), initial_sp - 8.0), "The actual Bash wind-up must consume exactly eight SP"):
			return
		if not _check(game.monsters[index].hp == initial_hp, "Bash must not apply damage before the animation hit point"):
			return
		if not await _wait(func() -> bool: return game.pending_attack.is_empty(), 4.0, "resolve Bash impact"):
			return
		landed_bash = float(game.monsters[index].hp) < initial_hp or int(game.kills) > initial_kills
		# A legitimate miss is possible. Stop normal auto-attacks with a real move
		# command, then try another fully resourced cast through the instructor.
		game.move_to(game.player.position)
		if landed_bash:
			break
		_log("Bash attempt %d missed normally; trying again" % (attempt + 1))
	if not _check(landed_bash, "At least one normally rolled Bash must visibly damage its target"):
		return
	if not _check(not game.dead and natural_kills >= 20 and game.kills >= 20,
		"The novice-to-Swordsman adventure must complete alive with natural combat rewards"):
		return
	if not _check(_save_hash() == original_save_hash and not game.save_enabled,
		"The full adventure must leave the player's persistent save unchanged"):
		return
	if not _write_report():
		return
	_log("Complete adventure passed")
	print("PROGRESSION_PLAYTHROUGH_PASS (%d checks; %d natural kills; %d potions; %.1fs game / %.1fs wall)" % [
		checks, natural_kills, potion_uses, float(game.time), (Time.get_ticks_msec() - wall_started) / 1000.0])
	quit()


func _instructor(action: String, expected_label: String) -> bool:
	game.talk_to_guide()
	if not await _wait(func() -> bool: return game.hud._dialog.visible, 90.0, "walk to instructor for " + action):
		return false
	var available := false
	for button in game.hud._dialog_actions.get_children():
		if button is Button and button.text == expected_label:
			available = true
	if not _check(available, "Instructor must actually offer '%s' at this point in the adventure" % expected_label):
		return false
	game._dialog_action(action)
	return true


func _find_living_target(species: String) -> int:
	if not await _wait(func() -> bool: return _nearest_alive(species) >= 0, 40.0, "wait for a natural " + species + " respawn"):
		return -1
	return _nearest_alive(species)


func _nearest_alive(species: String) -> int:
	var best := INF
	var selected := -1
	for index in game.monsters.size():
		var monster: Dictionary = game.monsters[index]
		if not monster.alive or monster.id != species:
			continue
		var distance: float = game.player.position.distance_to(monster.visual.position)
		if distance < best:
			best = distance
			selected = index
	return selected


func _fight_species(species: String) -> bool:
	var index: int = await _find_living_target(species)
	if index < 0:
		return false
	var before: int = game.kills
	game.select_monster(index)
	if not await _wait(func() -> bool: return int(game.kills) > before, 100.0, "approach and defeat " + species):
		return false
	natural_kills += int(game.kills) - before
	return _check(int(game.kills) == before + 1 and not game.monsters[index].alive,
		"An ordinary target command must finish one complete combat encounter")


func _wait(predicate: Callable, simulated_timeout: float, stage: String) -> bool:
	var started: float = game.time
	while not bool(predicate.call()):
		_keep_healthy()
		if game.dead:
			return _fail("Unexpected knockout while trying to " + stage)
		if float(game.time) - started > simulated_timeout:
			return _fail("Simulation timeout while trying to " + stage)
		if (Time.get_ticks_msec() - wall_started) / 1000.0 > WALL_TIMEOUT_SECONDS:
			return _fail("Wall-clock timeout while trying to " + stage)
		await process_frame
	return true


func _keep_healthy() -> void:
	if not game.dead and float(game.hp) < float(game.max_hp) * 0.50 and int(game.character.inventory.red_potion) > 0 and float(game.potion_timer) <= 0.0:
		var before: int = game.character.inventory.red_potion
		game.use_potion()
		potion_uses += before - int(game.character.inventory.red_potion)


func _check(condition: bool, message: String) -> bool:
	checks += 1
	if not condition:
		return _fail(message)
	return true


func _fail(message: String) -> bool:
	push_error("PROGRESSION_PLAYTHROUGH_FAIL: " + message)
	if is_instance_valid(game):
		_log("Failure state: command=%s target=%d path=%d position=%s" % [game.command, game.selected_id, game.path.size(), game.player.position])
	quit(1)
	return false


func _log(message: String) -> void:
	print("PROGRESSION %.1fs | %s | %s B%d/J%d EXP %d/%d HP %d/%d SP %d Kills %d" % [float(game.time), message,
		game.character.job_class, game.character.base_level, game.character.job_level, game.character.base_exp,
		game.character.job_exp, int(game.hp), int(game.max_hp), int(game.sp), game.kills])


func _save_hash() -> String:
	return FileAccess.get_sha256(game.save_path) if FileAccess.file_exists(game.save_path) else "missing"


func _write_report() -> bool:
	var directory := ProjectSettings.globalize_path(REPORT_PATH.get_base_dir())
	var error := DirAccess.make_dir_recursive_absolute(directory)
	if error != OK:
		return _fail("Could not create the progression evidence directory")
	var file := FileAccess.open(REPORT_PATH, FileAccess.WRITE)
	if not file:
		return _fail("Could not write the progression evidence report")
	var report: Dictionary = {
		"result": "pass",
		"recorded_utc": Time.get_datetime_string_from_system(true) + "Z",
		"engine_version": str(Engine.get_version_info().get("string", "unknown")),
		"check_count": checks,
		"natural_kills": natural_kills,
		"potion_uses": potion_uses,
		"game_seconds": snappedf(float(game.time), 0.01),
		"wall_seconds": snappedf((Time.get_ticks_msec() - wall_started) / 1000.0, 0.01),
		"character": {
			"job_class": game.character.job_class,
			"base_level": game.character.base_level,
			"job_level": game.character.job_level,
			"bash_level": game.character.skills.bash,
		},
		"save_unchanged": _save_hash() == original_save_hash and not game.save_enabled,
		"fixture": "Fresh default novice in the real main scene; --qa-progression disables loading and saving. No stat, damage, EXP, death or position injection.",
		"command": RUN_COMMAND,
		"time_scale": Engine.time_scale,
		"max_fps": Engine.max_fps,
	}
	file.store_string(JSON.stringify(report, "\t") + "\n")
	file.close()
	print("Progression evidence saved to " + REPORT_PATH)
	return true
