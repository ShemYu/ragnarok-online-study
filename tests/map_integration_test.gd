extends SceneTree
## --headless --path . --script res://tests/map_integration_test.gd
## Use a rendered process and append -- --visual for map capture.
const Field = preload("res://scripts/field_world_ro.gd")
const Actor = preload("res://scripts/ro_sprite_actor.gd")
var checks := 0
var failures := 0

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, message: String) -> void:
	checks += 1
	if not ok:
		failures += 1
		push_error(message)

func run() -> void:
	root.size = Vector2i(1280,800)
	var scene := Node3D.new()
	root.add_child(scene)
	var field := Field.new()
	scene.add_child(field)
	field.build()
	check(field.map_data.last_error.is_empty(), "Native GND/GAT must load successfully")
	check(field.environment_metrics.missing_textures.is_empty(), "Every terrain material must resolve to a reference texture")
	check(field.environment_metrics.unavailable_models.is_empty(), "Every RSW instance in the visible crop must have its source model")
	check(field.environment_metrics.models >= 100, "The native crop contains its original model population")
	check(field.environment_metrics.surfaces > 3000, "The field uses native terrain surfaces")
	check(field.minimap_texture != null, "The minimap is sampled from the native terrain")
	check(field._map_visual.scale.z == -1, "North GAT coordinates reflect to negative world Z")
	check(field._to_gat(Vector3(2,99,-3)).is_equal_approx(Field.ORIGIN_GAT + Vector2(2,3)), "Coordinate conversion flips only the north axis")

	var spawn := field.nearest_ground(Vector3(0,0,3))
	check(absf(spawn.y) < 0.0001, "The camp spawn is vertically registered at zero")
	var start := field.world_to_cell(spawn)
	var destinations := [Vector3(-3,0,4), Vector3(-4,0,0), Vector3(3,0,-3), Vector3(-6,0,-5), Vector3(4,0,5), Vector3(3,0,-7), Vector3(-8,0,1)]
	for point: Vector3 in destinations:
		var target := field.nearest_ground(point)
		var cell := field.world_to_cell(target)
		check(field.is_walkable(cell), "Actor spawn %s must snap to a walkable native cell" % point)
		var route := field.navigation.get_id_path(start,cell)
		check(not route.is_empty(), "Actor spawn %s must be reachable from camp" % point)
		for waypoint: Vector2i in route:
			check(field.is_walkable(waypoint), "Spawn routes never cross native blocked cells")
		check(absf(target.y - gnd_height(field,target)) <= 0.16, "Actor feet remain within native GAT/GND simplification tolerance")
	var guide_cell := field.world_to_cell(field.nearest_ground(destinations[0]))
	field.navigation.set_point_solid(guide_cell,true)
	var approaches := 0
	for delta in [Vector2i.LEFT,Vector2i.RIGHT,Vector2i.UP,Vector2i.DOWN]:
		var cell: Vector2i = guide_cell + delta
		if field.is_walkable(cell) and not field.navigation.get_id_path(start,cell).is_empty():
			approaches += 1
	check(approaches > 0, "A blocking NPC still has a reachable interaction neighbor")
	field.navigation.set_point_solid(guide_cell,false)

	var walkable := 0
	var blocked := 0
	var max_visual_height_error := 0.0
	for z in range(-24,25):
		for x in range(-24,25):
			var cell := Vector2i(x,z)
			var world := Vector3(x,0,z)
			var gat := Vector2i(field._to_gat(world).floor())
			check(field.is_walkable(cell) == field.map_data.is_walkable(gat), "Navigation reflects the native GAT cell type")
			if field.is_walkable(cell):
				walkable += 1
				max_visual_height_error = maxf(max_visual_height_error,absf(field.height_at(world)-gnd_height(field,world)))
			else:
				blocked += 1
	check(walkable > 1000 and blocked > 100, "The gate slice retains substantial open ground and source collision barriers")
	check(max_visual_height_error <= 0.16, "Native GAT height must align to visible GND across the entire play area")
	check(not field.is_walkable(Vector2i(25,0)), "Navigation never escapes the cropped play boundary")

	var camera := Camera3D.new()
	scene.add_child(camera)
	camera.fov = 15
	camera.near = 1
	camera.far = 250
	camera.current = true
	await process_frame
	var picked := 0
	var max_pick_error := 0.0
	for yaw in [-90.0,-45.0,0.0,45.0,90.0]:
		for pitch in [35.0,48.0,65.0]:
			place_camera(camera,spawn,yaw,pitch,62)
			for point: Vector3 in [spawn,field.ground_position(Vector3(-4,0,0)),field.ground_position(Vector3(3,0,-3)),field.ground_position(Vector3(-6,0,-5))]:
				var screen := camera.unproject_position(point)
				var hit: Variant = field.pick_ground(camera.project_ray_origin(screen),camera.project_ray_normal(screen))
				check(hit != null, "Terrain ray must hit at supported camera angles")
				if hit != null:
					var distance: float = hit.distance_to(point)
					max_pick_error = maxf(max_pick_error,distance)
					check(distance < 0.015, "Click projection reaches the correct elevated ground point")
					picked += 1
	place_camera(camera,spawn,0,48,62)
	var player := Actor.new()
	scene.add_child(player)
	player.configure("novice")
	player.position = spawn
	player.set_process(false)
	player.direction = 0
	player._render_frame()
	check(is_equal_approx(Actor.PIXEL_SIZE,0.03125), "Native sprite scale is explicitly one world cell per32 source pixels")
	var rectangle: Rect2 = player.screen_rect(camera)
	check(rectangle.size.y > 135 and rectangle.size.y < 145, "Default novice is about140 screen pixels tall at1280x800")
	var image_bounds := player._sprite.texture.get_image().get_used_rect()
	var bottom_y: float = (Actor.ORIGIN.y + player._feet_offset - image_bounds.end.y) * Actor.PIXEL_SIZE + player._sprite.position.y
	check(absf(bottom_y-0.035) < 0.0001, "Enlargement keeps the original neutral foot registration")
	for index in 6:
		var actor := Actor.new()
		scene.add_child(actor)
		actor.configure("poring" if index < 3 else "lunatic")
		actor.position = field.nearest_ground(destinations[index+1])
		actor.set_process(false)
		var rect: Rect2 = actor.screen_rect(camera)
		check(rect.size.y > 30 and rect.size.y < 65, "Native monsters remain legible at default map zoom")
	var guide := Actor.new()
	scene.add_child(guide)
	guide.configure("guide")
	guide.position = field.nearest_ground(destinations[0])
	guide.set_process(false)
	print("Map metrics: %d walkable cells, %d blocked, %.5f maximum GAT/GND difference, %d successful ray cases (max error %.5f), novice %.1fpx" % [walkable,blocked,max_visual_height_error,picked,max_pick_error,rectangle.size.y])
	if "--visual" in OS.get_cmdline_user_args():
		await capture(scene,camera,spawn)
	print("Map integration checks: %d passed, %d failed" % [checks-failures,failures])
	quit(1 if failures else 0)

func place_camera(camera: Camera3D, focus: Vector3, yaw: float, pitch: float, distance: float) -> void:
	var horizontal := cos(deg_to_rad(pitch))*distance
	camera.position = focus+Vector3(sin(deg_to_rad(yaw))*horizontal,sin(deg_to_rad(pitch))*distance,cos(deg_to_rad(yaw))*horizontal)
	camera.look_at(focus)

func gnd_height(field: Node3D, world: Vector3) -> float:
	# Sample rendered GND triangles independently of the GAT collision height.
	var grid: Vector2 = field._to_gat(world)/2
	var cell := Vector2i(grid.floor())
	var uv := grid-Vector2(cell)
	var i: int = (cell.x+cell.y*field.map_data.ground_size.x)*4
	var heights: PackedFloat32Array = field.map_data.ground_heights
	var a := heights[i]
	var b := heights[i+1]
	var c := heights[i+2]
	var d := heights[i+3]
	var height := a+(b-a)*uv.x+(d-b)*uv.y if uv.x>=uv.y else a+(d-c)*uv.x+(c-a)*uv.y
	return height-field.height_origin

func capture(scene: Node3D, camera: Camera3D, spawn: Vector3) -> void:
	var environment := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color("91a770")
	environment.environment = env
	scene.add_child(environment)
	DirAccess.make_dir_recursive_absolute("res://docs/v3")
	place_camera(camera,spawn+Vector3(0,0,-0.7),0,48,62)
	await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://docs/v3/map-scale-default.png")
	place_camera(camera,Vector3(0,2,-7),0,60,172)
	await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://docs/v3/map-overview.png")
