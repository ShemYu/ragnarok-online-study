extends SceneTree

func _initialize() -> void:
	call_deferred("run_checks")

func run_checks() -> void:
	var Actor = load("res://scripts/actor_visual.gd")
	var actor = Actor.new()
	root.add_child(actor)
	actor.configure("novice")
	var camera := Camera3D.new()
	root.add_child(camera)
	camera.position = Vector3(0, 16, 20)
	camera.look_at(Vector3.ZERO)
	camera.current = true
	await process_frame
	actor.set_motion(Vector3(0, 0, 0.05))
	assert(actor._facing == "front")
	camera.position = Vector3(20, 16, 0)
	camera.look_at(Vector3.ZERO)
	actor._update_facing()
	assert(actor._facing == "side")
	actor.set_motion(Vector3(0.05, 0, 0))
	assert(actor._facing == "front")
	camera.position = Vector3(-20, 16, 0)
	camera.look_at(Vector3.ZERO)
	actor._update_facing()
	assert(actor._facing == "back")
	var atlas := Image.create(384, 288, false, Image.FORMAT_RGBA8)
	atlas.fill(Color("c8d2bd"))
	for row in range(3):
		var facing: String = ["front", "back", "side"][row]
		for column in range(6):
			var frame: int = [0, 1, 3, 0, 0, 0][column]
			var attack: int = [-1, -1, -1, 0, 1, 2][column]
			var art: Image = actor._draw_novice(facing, frame, attack, 0)
			atlas.blend_rect(art, Rect2i(0, 0, 64, 72), Vector2i(column * 64, row * 72))
	actor._facing = "front"
	for column in range(6):
		var frame: int = [0, 1, 3, 0, 0, 0][column]
		var attack: int = [-1, -1, -1, 0, 1, 2][column]
		var art: Image = actor._draw_slime(frame, attack, 0, column > 0 and column < 3)
		atlas.blend_rect(art, Rect2i(0, 0, 64, 48), Vector2i(column * 64, 228))
	atlas.resize(1152, 864, Image.INTERPOLATE_NEAREST)
	atlas.save_png("res://assets/original/sprite-contact-sheet.png")
	actor.set_selected(true)
	actor.set_attacking(true)
	actor._process(0.12)
	assert(actor._slash.visible)
	actor.flash_hit()
	actor._process(0.02)
	assert(actor._sprite.modulate.r > 1.0)
	actor.configure("slime")
	actor._process(0.05)
	assert(not actor._slash.visible)
	print("ACTOR_VISUAL_CHECKS_PASS")
	quit()
