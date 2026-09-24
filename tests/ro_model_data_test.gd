extends SceneTree
## Godot --headless --path . --script res://tests/ro_model_data_test.gd
## Add -- --visual to save a native reference-model contact view.
const Rsm = preload("res://scripts/ro_model_data.gd")
const Actor = preload("res://scripts/ro_sprite_actor.gd")
const ASSETS := "res://assets/reference-ro/map-study/"
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
	var stage := Node3D.new()
	root.add_child(stage)
	var textures: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(ASSETS + "texture-map.json"))
	var sources := ["tree01", "tree02", "bush02", "mushroom01", "stump01", "bench01", "signpost01", "prontera-gate", "prontera-wall", "prontera-pillar", "prontera-guardpost", "prontera-banner"]
	for id: String in sources:
		var path := ASSETS + id + ".rsm"
		var data := Rsm.load_model(path)
		check(not data.is_empty(), id + " must parse as classic RSM")
		if data.is_empty():
			continue
		check(data.version == Vector2i(1, 4), id + " must retain the source version")
		var model := Rsm.build_model(stage, path, textures, {"position": Vector3(3, 2, -4), "scale": Vector3.ONE * 0.6})
		check(model != null and model.get_child_count() > 0, id + " must construct textured geometry")
		check(model.position.is_equal_approx(Vector3(3, 2, -4)), "Instance position must already use Godot world units")
		var minimum_y := INF
		var maximum_y := -INF
		for child: MeshInstance3D in model.get_children():
			var mesh: ArrayMesh = child.mesh
			var arrays := mesh.surface_get_arrays(0)
			check(arrays[Mesh.ARRAY_VERTEX].size() % 3 == 0, id + " has complete triangle groups")
			check(arrays[Mesh.ARRAY_VERTEX].size() == arrays[Mesh.ARRAY_TEX_UV].size(), id + " UVs match vertex count")
			check(child.material_override.albedo_texture != null, id + " resolves every original texture")
			minimum_y = minf(minimum_y, mesh.get_aabb().position.y)
			maximum_y = maxf(maximum_y, mesh.get_aabb().end.y)
		check(absf(minimum_y) < 0.0001, id + " rests on the zero-height foot plane")
		check(is_equal_approx(maximum_y, data.size.y), id + " preserves source height at raw / 5")
		model.queue_free()

	var tree := Rsm.load_model(ASSETS + "tree01.rsm")
	check(tree.nodes[0].vertices.size() == 70 and tree.nodes[0].faces.size() == 64,
		"Known tree fixture preserves its native vertex and triangle counts")
	check(absf(tree.size.y - 9.11126) < 0.0001, "Tree source height remains 9.11126 normalized cells")
	var bench := Rsm.load_model(ASSETS + "bench01.rsm")
	check(absf(bench.size.y - 1.884726) < 0.0001, "Embedded RSM basis scale is retained")
	var world_rotation := Rsm.build_model(stage, ASSETS + "tree01.rsm", textures,
		{"rotation": Vector3(0, 90, 0), "scale": Vector3(2, 3, 4)})
	check((world_rotation.basis * Vector3.RIGHT).is_equal_approx(Vector3(0, 0, -2)), "Raw RSW yaw is converted consistently")
	check((world_rotation.basis * Vector3.UP).is_equal_approx(Vector3(0, 3, 0)), "RSW scale remains dimensionless")
	world_rotation.queue_free()

	var leaf := Rsm.load_texture(ASSETS + "textures/leaf_10.png").get_image()
	var transparent := 0
	var opaque := 0
	var magenta_opaque := 0
	for y in leaf.get_height():
		for x in leaf.get_width():
			var pixel := leaf.get_pixel(x, y)
			if pixel.a < 0.01:
				transparent += 1
			else:
				opaque += 1
				if pixel.r > 0.99 and pixel.b > 0.99 and pixel.g < 0.01:
					magenta_opaque += 1
	check(transparent > 1000 and opaque > 1000, "Leaf texture keeps a real cutout, not an opaque square")
	check(magenta_opaque == 0, "Color-key magenta never becomes visible geometry")
	check(leaf.has_mipmaps(), "Reference model textures include filtered mip levels")

	var fixture := make_fixture()
	var valid := Rsm.decode(fixture)
	check(not valid.is_empty() and valid.size.is_equal_approx(Vector3(2, 2, 0)), "Synthetic triangle validates /5 units and Y inversion independently")
	var nested := Rsm.decode(make_fixture(true))
	check(not nested.is_empty(), "A child listed before its parent resolves")
	if not nested.is_empty():
		check(nested.nodes[0].transform.origin.is_equal_approx(Vector3(10, 5, 0)), "Parent rotation rotates child translation")
		check((nested.nodes[0].geometry_transform * Vector3.ZERO).is_equal_approx(Vector3(8, 5, 0)), "Per-node geometry offset follows the node hierarchy")
	check(Rsm.decode(fixture.slice(0, 20)).is_empty(), "Truncated model is rejected")
	var unsupported := fixture.duplicate()
	unsupported[4] = 2
	check(Rsm.decode(unsupported).is_empty(), "Unsupported RSM 2.x is rejected explicitly")
	var invalid_count := fixture.duplicate()
	invalid_count.encode_s32(31, -1)
	check(Rsm.decode(invalid_count).is_empty(), "Negative texture count is rejected")
	check(Rsm.decode(make_fixture(false, true)).is_empty(), "Out-of-range vertex index is rejected")
	check(Rsm.decode(make_fixture(true, false, true)).is_empty(), "Cyclic parent chains are rejected")
	if "--visual" in OS.get_cmdline_user_args():
		await capture(stage, textures)
	print("RSM model checks: %d passed, %d failed" % [checks - failures, failures])
	quit(1 if failures else 0)

func fixed(buffer: StreamPeerBuffer, text: String, length: int) -> void:
	var bytes := text.to_ascii_buffer()
	bytes.resize(length)
	buffer.put_data(bytes)

func vector(buffer: StreamPeerBuffer, value: Vector3) -> void:
	buffer.put_float(value.x)
	buffer.put_float(value.y)
	buffer.put_float(value.z)

func make_fixture(hierarchy := false, bad_index := false, cycle := false) -> PackedByteArray:
	var buffer := StreamPeerBuffer.new()
	fixed(buffer, "GRSM", 4)
	buffer.put_u8(1)
	buffer.put_u8(4)
	buffer.put_32(0)
	buffer.put_32(0)
	buffer.put_u8(255)
	fixed(buffer, "", 16)
	buffer.put_32(1)
	fixed(buffer, "fixture.png", 40)
	fixed(buffer, "root", 40)
	buffer.put_32(2 if hierarchy else 1)
	for index in (2 if hierarchy else 1):
		var is_child: bool = hierarchy and index == 0
		fixed(buffer, "child" if is_child else "root", 40)
		fixed(buffer, "root" if is_child else ("child" if cycle else ""), 40)
		buffer.put_32(1)
		buffer.put_32(0)
		vector(buffer, Vector3.RIGHT)
		vector(buffer, Vector3.UP)
		vector(buffer, Vector3.BACK)
		vector(buffer, Vector3(0, 2, 0) if is_child else Vector3.ZERO)
		vector(buffer, Vector3(5, 0, 0) if is_child else (Vector3(10, 0, 0) if hierarchy else Vector3.ZERO))
		buffer.put_float(PI / 2 if hierarchy and not is_child else 0)
		vector(buffer, Vector3.BACK)
		vector(buffer, Vector3.ONE)
		buffer.put_32(3)
		vector(buffer, Vector3.ZERO)
		vector(buffer, Vector3(10, 0, 0))
		vector(buffer, Vector3(0, -10, 0))
		buffer.put_32(3)
		for uv in [Vector2.ZERO, Vector2.RIGHT, Vector2.DOWN]:
			buffer.put_32(0)
			buffer.put_float(uv.x)
			buffer.put_float(uv.y)
		buffer.put_32(1)
		for value in [0, 1, 9 if bad_index else 2, 0, 1, 2, 0, 0]:
			buffer.put_u16(value)
		buffer.put_32(1)
		buffer.put_32(0)
		buffer.put_32(0)
	buffer.put_32(0)
	buffer.put_32(0)
	return buffer.data_array

func capture(stage: Node3D, textures: Dictionary) -> void:
	root.size = Vector2i(1280, 800)
	await process_frame
	var environment := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color("91a770")
	environment.environment = env
	stage.add_child(environment)
	var camera := Camera3D.new()
	stage.add_child(camera)
	camera.fov = 28
	camera.position = Vector3(0, 20, 25)
	camera.look_at(Vector3(0, 2, 0))
	camera.current = true
	for item in [["tree01", Vector3(-6, 0, 0), 0.65], ["tree02", Vector3(-1, 0, -3), 0.5], ["bush02", Vector3(-6, 0, 4), 0.3], ["prontera-gate", Vector3(5, 0, -2), 0.3]]:
		Rsm.build_model(stage, ASSETS + item[0] + ".rsm", textures, {"position": item[1], "scale": Vector3.ONE * item[2]})
	var actor := Actor.new()
	stage.add_child(actor)
	actor.configure("novice")
	actor.position = Vector3(2, 0, 4)
	await process_frame
	await RenderingServer.frame_post_draw
	DirAccess.make_dir_recursive_absolute("res://docs/v3")
	root.get_texture().get_image().save_png("res://docs/v3/native-model-preview.png")
