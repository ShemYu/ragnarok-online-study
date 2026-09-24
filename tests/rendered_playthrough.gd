extends RefCounted
## Rendered integration test. Launch the normal game with -- --qa-playthrough.
## The fixture seeds RNG and delays ambient wandering; every tested player
## command is sent through Input.parse_input_event, including real GUI clicks.
const OUT := "res://docs/v3/"
var game: Node
var checks := 0
var failures: Array[String] = []
var observations: Array[String] = []

func check(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failures.append(message)
		push_error("RENDERED_QA: " + message)

func run(active_game: Node) -> void:
	game = active_game
	DirAccess.make_dir_recursive_absolute(OUT)
	check(game.qa_mode and not game.save_enabled, "Playthrough must use isolated QA mode with saving disabled")
	game.get_window().size = Vector2i(1280, 800)
	game.rng.seed = 20260923
	for mob: Dictionary in game.monsters:
		mob.wander = 999.0
		mob.route = []
	await settle(0.5)
	await screenshot("field-preview.png")
	var initial_position: Vector3 = game.player.position
	var first_destination: Vector3 = game.field.nearest_ground(Vector3(1, 0, 1))
	check(game.field.is_walkable(game.field.world_to_cell(first_destination)), "Movement fixture must use a native walkable GAT cell")
	await world_click(first_destination)
	check(not game.path.is_empty() or game.player.position.distance_to(initial_position) > 0.1,
		"A ground mouse click must start navigation")
	check(await wait_for(func() -> bool: return game.path.is_empty(), 5.0), "Ground-click movement must reach its destination")
	check(game.player.position.distance_to(initial_position) > 1.0, "Native timeline must actually move the character")
	check(game.player.position.distance_to(first_destination) < 0.25, "Ground click must reach the intended elevated terrain cell")
	check(absf(game.player.position.y-game.field.height_at(game.player.position)) < 0.02, "Player feet must follow the native GAT height")

	await click_button(find_button(game.hud._hotbar, "C Status"))
	check(game.hud._status_panel.visible, "Status hotbar button must open the actual status window")
	var before_ui_position: Vector3 = game.player.position
	await click_at(game.hud._status_panel.get_global_rect().position + Vector2(35, 13))
	await settle(0.12)
	check(game.path.is_empty() and game.player.position.distance_to(before_ui_position) < 0.02,
		"Clicking an opaque status window must not issue a ground movement command")
	var strength_before: int = game.character.stats.str
	var points_before: int = game.character.stat_points
	await click_button(game.hud._stat_buttons.str)
	check(game.character.stats.str == strength_before + 1 and game.character.stat_points < points_before,
		"The STR plus button must allocate a real stat point transaction")
	await screenshot("status-preview.png")
	await click_button(find_button(game.hud._hotbar, "C Status"))
	check(not game.hud._status_panel.visible, "Status button must close its window")
	await click_button(find_button(game.hud._hotbar, "I Bag"))
	check(game.hud._inventory.visible, "Bag button must open inventory")
	await click_button(game.hud._equip_button)
	check(game.character.equipped_weapon == "" and not game.player.weapon_visible,
		"Inventory must unequip the real weapon and its sprite")
	await click_button(game.hud._equip_button)
	check(game.character.equipped_weapon == "knife" and game.player.weapon_visible,
		"Inventory must equip the real weapon and its sprite")
	await click_button(find_button(game.hud._hotbar, "I Bag"))

	var before_trainer: Vector3 = game.player.position
	var trainer_bounds: Rect2 = game.guide.screen_rect(game.camera)
	await click_at(Vector2(trainer_bounds.get_center().x, trainer_bounds.position.y + 10))
	check(await wait_for(func() -> bool: return game.hud._dialog.visible, 7.0),
		"Clicking the trainer must approach him and open his dialogue")
	check(game.player.position.distance_to(before_trainer) > 1.0 and game.player.position.distance_to(game.GUIDE_POSITION) < 1.65,
		"Trainer dialogue must follow actual world movement into conversation range")
	await screenshot("training-preview.png")
	await click_button(find_button(game.hud._dialog_actions, "Begin training"))
	check(game.quest.active and not game.hud._dialog.visible, "Begin training must accept the quest through the dialogue button")

	var target: Dictionary = game.monsters[0]
	var hp_before: float = target.hp
	var kills_before: int = game.kills
	await click_at(game.camera.unproject_position(target.visual.position + Vector3(0, 0.55, 0)))
	check(game.selected_id == 0, "Clicking a monster sprite must select the intended monster")
	check(await wait_for(func() -> bool: return not game.pending_attack.is_empty(), 6.0),
		"A selected monster must trigger an attack after native chase movement")
	check(target.hp == hp_before, "Attack selection and wind-up must not apply instant damage")
	await settle(0.08)
	check(target.hp == hp_before, "Damage must still wait for the scheduled contact time")
	check(await wait_for(func() -> bool: return target.hp < hp_before, 4.0),
		"The native attack timeline must eventually commit damage")
	await screenshot("combat-preview.png")
	check(await wait_for(func() -> bool: return not target.alive, 12.0),
		"Repeated native attacks must defeat the target without a direct damage handler")
	check(game.kills == kills_before + 1 and game.quest.poring == 1,
		"A real monster defeat must advance both kill count and the accepted training quest")
	check(game.character.base_exp > 0 and game.character.job_exp > 0,
		"A real defeat must award independent Base and Job experience")

	await click_at(game.camera.unproject_position(game.monsters[1].visual.position + Vector3(0, 0.55, 0)))
	check(game.selected_id == 1, "A second monster must be targetable")
	var cancelled_target_hp: float = game.monsters[1].hp
	check(await wait_for(func() -> bool: return not game.pending_attack.is_empty(), 7.0),
		"Cancellation scenario must reach a real attack wind-up")
	var cancel_destination: Vector3 = clear_ground_destination(game.player.position + Vector3(2, 0, 0))
	check(game.field.is_walkable(game.field.world_to_cell(cancel_destination)), "Cancellation destination must be a native walkable cell")
	await world_click(cancel_destination)
	check(game.selected_id == -1 and game.pending_attack.is_empty(),
		"A ground click must cancel targeting and any pending attack")
	await settle(0.4)
	check(game.monsters[1].hp == cancelled_target_hp, "Cancelled wind-up must not deal delayed damage after walking away")
	check(await wait_for(func() -> bool: return game.path.is_empty(), 5.0), "Cancellation movement must finish")
	await click_button(game.hud._rest_button)
	check(game.sitting and game.player.state == "sit", "Sit button must switch gameplay and native sprite pose")
	var yaw_before: float = game.camera_yaw
	await rotate_camera(Vector2(62, 0))
	await settle(0.3)
	check(absf(game.camera_yaw - yaw_before) > 0.3, "Right-drag input must rotate the camera")
	observations.append("One normal Poring was defeated using click-to-chase and scheduled attacks. No HP or damage fixture was applied.")

	game.get_window().size = Vector2i(960, 640)
	await settle(0.35)
	await click_button(find_button(game.hud._hotbar, "C Status"))
	check(game.hud._status_panel.visible, "Status must still open in a 960x640 window")
	var viewport_rect: Rect2 = game.get_viewport().get_visible_rect()
	for control in [game.hud._status_panel, game.hud._hotbar, game.hud._map_panel, game.hud._quest_panel]:
		check(viewport_rect.encloses(control.get_global_rect()), "Compact HUD window must remain within the visible viewport: " + str(control.name))
	check(game.hud._map.map_texture == game.field.minimap_texture and game.hud._map.map_texture != null,
		"Compact minimap must display the native terrain raster")
	check(is_equal_approx(game.hud._map.extent, 24.5), "Minimap marker extent must match the 49-cell native navigation region")
	check(game.hud._map_title.text.contains("Prontera"), "Minimap title must identify the current native field")
	await screenshot("compact-preview.png")
	observations.append("Compact window size: %s; UI viewport: %s." % [game.get_window().size, viewport_rect.size])
	var report := {"checks": checks, "failures": failures, "fixture": "Fresh QA character; saving disabled; RNG seed 20260923; ambient wander timers set to 999 seconds and existing ambient routes cleared. Monster combat and all player movement/attacks run on the real frame timeline.",
		"input": "Input.parse_input_event mouse clicks on native GAT-grounded world positions and actual GUI rectangles, plus right-drag motion.",
		"observations": observations, "screenshots": ["field-preview.png", "status-preview.png", "training-preview.png", "combat-preview.png", "compact-preview.png"]}
	var report_file := FileAccess.open(OUT + "rendered-playthrough.json", FileAccess.WRITE)
	report_file.store_string(JSON.stringify(report, "\t") + "\n")
	print("RENDERED_PLAYTHROUGH_%s (%d checks)" % ["PASS" if failures.is_empty() else "FAIL", checks])
	game.get_tree().quit(0 if failures.is_empty() else 1)

func settle(seconds: float) -> void:
	await game.get_tree().create_timer(seconds).timeout

func wait_for(predicate: Callable, timeout: float) -> bool:
	var deadline := Time.get_ticks_msec() + int(timeout * 1000)
	while Time.get_ticks_msec() < deadline:
		if predicate.call():
			return true
		await game.get_tree().process_frame
	return bool(predicate.call())

func screenshot(filename: String) -> void:
	await RenderingServer.frame_post_draw
	var image: Image = game.get_viewport().get_texture().get_image()
	var expected_size := Vector2i(960, 640) if filename == "compact-preview.png" else Vector2i(1280, 800)
	check(image.get_size() == expected_size, "Screenshot must have the requested native viewport size: " + filename)
	check(image.save_png(OUT + filename) == OK, "Screenshot must save: " + filename)

func world_click(point: Vector3) -> void:
	await click_at(game.camera.unproject_position(game.field.ground_position(point)))

func clear_ground_destination(preferred: Vector3) -> Vector3:
	# Pick an actual unobstructed ground click, avoiding sprites that can cover
	# a walkable terrain cell from this camera angle. Do not reposition actors.
	var candidates: Array[Vector3] = [preferred]
	for offset: Vector3 in [Vector3(0,0,3),Vector3(-3,0,0),Vector3(0,0,-3),Vector3(3,0,3),Vector3(-3,0,3)]:
		candidates.append(game.player.position+offset)
	for point: Vector3 in candidates:
		var grounded: Vector3 = game.field.nearest_ground(point)
		if grounded.distance_to(game.player.position) < 1.5:
			continue
		var screen: Vector2 = game.camera.unproject_position(grounded)
		if not Rect2(260,180,740,440).has_point(screen):
			continue
		var obstructed: bool = game.guide.screen_rect(game.camera).grow(8).has_point(screen)
		for mob: Dictionary in game.monsters:
			if mob.alive and mob.visual.screen_rect(game.camera).grow(8).has_point(screen):
				obstructed = true
		if not obstructed:
			return grounded
	check(false,"A visible walkable ground cell must be available for the cancel command")
	return game.field.nearest_ground(preferred)

func click_at(point: Vector2) -> void:
	# parse_input_event receives window coordinates. GUI rectangles and camera
	# projection use logical viewport coordinates, including after resizing.
	point = game.get_viewport().get_screen_transform() * point
	var motion := InputEventMouseMotion.new()
	motion.position = point
	motion.global_position = point
	Input.parse_input_event(motion)
	var press := InputEventMouseButton.new()
	press.position = point
	press.global_position = point
	press.button_index = MOUSE_BUTTON_LEFT
	press.button_mask = MOUSE_BUTTON_MASK_LEFT
	press.pressed = true
	Input.parse_input_event(press)
	await game.get_tree().process_frame
	var release: InputEventMouseButton = press.duplicate()
	release.button_mask = 0
	release.pressed = false
	Input.parse_input_event(release)
	# Input dispatch and deferred GUI signals finish on the next main-loop tick.
	await settle(0.06)
	await RenderingServer.frame_post_draw

func click_button(button: Button) -> void:
	if not is_instance_valid(button):
		check(false, "Expected GUI button must exist")
		return
	check(button.is_visible_in_tree() and not button.disabled, "GUI button must be visible and enabled: " + button.text)
	# Newly shown Containers sort their children on the next rendered frame.
	await RenderingServer.frame_post_draw
	await click_at(button.get_global_rect().get_center())

func find_button(node: Node, caption: String) -> Button:
	if node is Button and node.text == caption:
		return node
	for child in node.get_children():
		var found := find_button(child, caption)
		if found != null:
			return found
	return null

func rotate_camera(relative: Vector2) -> void:
	var point := game.get_viewport().get_visible_rect().size * 0.5
	point = game.get_viewport().get_screen_transform() * point
	var press := InputEventMouseButton.new()
	press.position = point
	press.global_position = point
	press.button_index = MOUSE_BUTTON_RIGHT
	press.button_mask = MOUSE_BUTTON_MASK_RIGHT
	press.pressed = true
	Input.parse_input_event(press)
	var motion := InputEventMouseMotion.new()
	motion.position = point + relative
	motion.global_position = point + relative
	motion.relative = relative
	motion.button_mask = MOUSE_BUTTON_MASK_RIGHT
	Input.parse_input_event(motion)
	await game.get_tree().process_frame
	press.pressed = false
	press.button_mask = 0
	Input.parse_input_event(press)
	await game.get_tree().process_frame
