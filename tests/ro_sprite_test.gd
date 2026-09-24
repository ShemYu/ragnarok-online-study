extends SceneTree
## Godot --headless --path . --script res://tests/ro_sprite_test.gd
## Add -- --visual under a rendered Godot process to save the ground preview.
const Actor = preload("res://scripts/ro_sprite_actor.gd")
const Data = preload("res://scripts/ro_sprite_data.gd")
const OUT := "res://docs/v3/"
var checks := 0
var failures := 0

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(message)

func run() -> void:
	DirAccess.make_dir_recursive_absolute(OUT)
	var scene := Node3D.new()
	root.add_child(scene)
	var actor := Actor.new()
	scene.add_child(actor)
	actor.configure("novice")
	actor.set_process(false)
	check(actor._body.textures.size() == 110 and actor._head.textures.size() == 15,
		"Reference Novice body/head image counts must match the downloaded files")
	check(actor._body.actions.size() == 104 and actor._weapon.textures.size() == 5,
		"Reference Novice needs 13 eight-view action groups and the dagger images")
	check(is_equal_approx(actor.action_length("attack"), 0.864),
		"Male Novice dagger action must be the nine-frame attack, not five-frame punch")
	check(is_equal_approx(actor.action_length("cast"), 0.576),
		"Skill presentation must use the six-frame cast group, not a freeze pose")
	var walk_body: Dictionary = actor._body.actions[8].frames[0]
	var walk_head: Dictionary = actor._head.actions[8].frames[0]
	check(actor._attachment(walk_body, walk_head) == Vector2(-1, 1),
		"Known walk pose needs the actual head/body anchor displacement")
	var baseline_offset: Vector2 = actor._sprite.offset
	check(actor._feet_offset > 0 and actor._feet_offset < 20,
		"The ACT foot pixel extent must lift the billboard above the ground origin")

	var sheet := Image.create(8 * 192, 6 * 192, false, Image.FORMAT_RGBA8)
	var states := ["idle", "walk", "ready", "attack", "sit", "dead"]
	var phases := [0.0, 0.25, 0.0, 0.52, 0.0, 1.0]
	for row in states.size():
		for view in range(8):
			actor.direction = view
			actor.set_state(states[row])
			actor._clock = phases[row] * actor.action_length(states[row])
			actor._render_frame()
			var image: Image = actor._sprite.texture.get_image()
			var bounds := image.get_used_rect()
			check(bounds.has_area(), "Novice %s view %d must render" % [states[row], view])
			check(bounds.position.x > 0 and bounds.end.x < 192 and bounds.position.y > 0 and bounds.end.y < 192,
				"Novice %s view %d must fit the common canvas" % [states[row], view])
			check(actor._sprite.offset == baseline_offset, "Pose changes must preserve the fixed foot registration")
			var cell := Rect2i(view * 192, row * 192, 192, 192)
			sheet.fill_rect(cell, Color("edf0de") if (row + view) % 2 == 0 else Color("d9e3d1"))
			sheet.fill_rect(Rect2i(cell.position.x, cell.position.y + Actor.ORIGIN.y + int(actor._feet_offset), 192, 1), Color("b2c2a3"))
			sheet.blend_rect(image, Rect2i(0, 0, 192, 192), cell.position)
	sheet.save_png(OUT + "novice-actions-eight-directions.png")
	# Exercise the whole dagger cycle, including its differently timed trail.
	for view in range(8):
		actor.direction = view
		actor.set_state("attack")
		for frame_index in range(9):
			actor._clock = frame_index * 0.096 + 0.0001
			actor._render_frame()
			var bounds: Rect2i = actor._sprite.texture.get_image().get_used_rect()
			check(bounds.has_area() and bounds.position.x > 0 and bounds.end.x < 192 and bounds.position.y > 0 and bounds.end.y < 192,
				"Every dagger attack frame and trail must fit the fixed canvas")
			check(actor._sprite.offset == baseline_offset, "Attack must not recenter each frame")

	actor.direction = 0
	actor.set_state("idle")
	actor._render_frame()
	var idle_texture = actor._sprite.texture
	actor._clock = 0.22
	actor._render_frame()
	check(actor._sprite.texture == idle_texture, "Idle must hold its head pose instead of cycling head directions")
	actor.set_state("ready")
	actor.play_action("attack", 0.9)
	actor._process(0.45)
	check(actor.state == "attack" and actor._current_key.contains(":0:4:"),
		"Attack duration must synchronize the body, head, dagger and trail at frame four")
	actor._process(0.46)
	check(actor.state == "ready", "Completed attack must return to the requested combat stance")
	actor.weapon_visible = false
	check(is_equal_approx(actor.action_length("attack"), 0.48), "Unequipping must select the unarmed animation")
	actor.weapon_visible = true
	actor.position = Vector3(2, 0, 3)
	actor.configure("swordsman")
	check(actor.position == Vector3(2, 0, 3) and actor.get_child_count() == 3,
		"Job reconfiguration must preserve location and replace its own three visual nodes")
	check(actor._body.textures.size() == 118 and actor._head.textures.size() == 15,
		"Swordsman must use the actual new body with the registered shared head")
	for actor_kind in ["poring", "lunatic", "guide"]:
		actor.configure(actor_kind)
		check(not actor._body.is_empty() and actor._sprite.texture != null, actor_kind + " must load natively")
		var foot_before: Vector2 = actor._sprite.offset
		for view in range(8):
			actor.direction = view
			actor.set_state("attack" if actor_kind != "guide" else "idle")
			actor._clock = 0.12
			actor._render_frame()
			check(actor._sprite.offset == foot_before, actor_kind + " must keep one foot offset across directions")
	actor.configure("lunatic")
	actor.direction = 0
	actor.play_action("dead", 0.75)
	actor._process(0.74)
	var death_last_frame: String = actor._current_key
	actor._process(0.02)
	check(actor._current_key == death_last_frame,
		"A retimed death clip must hold its final frame instead of rewinding to native timing")
	actor.configure("novice")
	var camera := Camera3D.new()
	scene.add_child(camera)
	camera.position = Vector3(0, 8, 10)
	camera.look_at(Vector3.ZERO)
	camera.current = true
	for camera_position in [Vector3(0, 8, 10), Vector3(10, 8, 0), Vector3(-10, 8, -10)]:
		camera.position = camera_position
		camera.look_at(Vector3.ZERO)
		var toward := camera.global_basis.z
		toward.y = 0
		var right := camera.global_basis.x
		right.y = 0
		for view in range(8):
			var angle := view * PI / 4.0
			actor.facing = toward.normalized() * cos(angle) - right.normalized() * sin(angle)
			actor._process(0)
			check(actor.direction == view, "Eight source directions must follow the rotated camera")
	if "--visual" in OS.get_cmdline_user_args():
		await _render_floor(scene, camera, actor)
	print("RO_SPRITE_TEST_%s (%d checks); native contact sheet saved" % ["PASS" if failures == 0 else "FAIL", checks])
	quit(1 if failures else 0)

func _render_floor(scene: Node3D, camera: Camera3D, actor: Node3D) -> void:
	actor.queue_free()
	var environment := WorldEnvironment.new()
	var settings := Environment.new()
	settings.background_mode = Environment.BG_COLOR
	settings.background_color = Color("1e2d2b")
	settings.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	settings.ambient_light_color = Color.WHITE
	settings.ambient_light_energy = 1.0
	environment.environment = settings
	scene.add_child(environment)
	var floor_mesh := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(16, 10)
	floor_mesh.mesh = plane
	var material := StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.albedo_color = Color("718c65")
	floor_mesh.material_override = material
	scene.add_child(floor_mesh)
	var kinds := ["novice", "swordsman", "guide", "poring", "lunatic"]
	for i in kinds.size():
		var example := Actor.new()
		scene.add_child(example)
		example.configure(kinds[i])
		example.position = Vector3((i - 2) * 2.3, 0, 0)
		example.set_process(false)
		var label := Label3D.new()
		label.text = kinds[i].capitalize()
		label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		label.pixel_size = 0.009
		label.font_size = 28
		label.position = example.position + Vector3(0, 2.6, 0)
		scene.add_child(label)
	camera.position = Vector3(0, 7, 11)
	camera.look_at(Vector3(0, 0.8, 0))
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 14
	await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(OUT + "native-floor-registration.png")
