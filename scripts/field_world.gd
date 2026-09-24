extends Node3D
## An original countryside study: textured surfaces, layered woodland, and a small trail camp.
## Grid coordinates are world X/Z coordinates; the walking plane is Y = 0.

const MAP_RECT := Rect2i(-14, -14, 29, 29)
# Render beyond the navigation boundary so camera orbit/zoom never exposes a cut edge.
const SCENERY_EXTENT := 90.0
const START_CLEAR := [Vector2i(0, 3), Vector2i(-4, 0), Vector2i(3, -3), Vector2i(-6, -5), Vector2i(4, 5)]

var navigation: AStarGrid2D
var _materials: Dictionary = {}
var _rng := RandomNumberGenerator.new()
var _built := false
var _static_meshes: Array[MeshInstance3D] = []
var environment_metrics: Dictionary = {}
var _main_path: Array[Vector2] = [Vector2(-45.0, -4), Vector2(-10, -4), Vector2(-6, -2.8), Vector2(-2, -0.5), Vector2(2, 0.5), Vector2(6, 0), Vector2(12, 0), Vector2(45.0, 0)]
var _branch_path: Array[Vector2] = [Vector2(0.0, 0), Vector2(0.2, 3.5), Vector2(-0.8, 7), Vector2(0.5, 11.5), Vector2(0.5, 45.0)]


func build() -> void:
	if _built:
		return
	_built = true
	_rng.seed = 7331
	_create_materials()
	navigation = AStarGrid2D.new()
	navigation.region = MAP_RECT
	navigation.cell_size = Vector2.ONE
	navigation.diagonal_mode = AStarGrid2D.DIAGONAL_MODE_ONLY_IF_NO_OBSTACLES
	navigation.default_compute_heuristic = AStarGrid2D.HEURISTIC_OCTILE
	navigation.default_estimate_heuristic = AStarGrid2D.HEURISTIC_OCTILE
	navigation.update()
	_build_ground()
	_build_river()
	_build_trees()
	_build_rocks()
	_build_fence()
	_build_grass()
	_build_flowers()
	_build_waymarker()
	_build_camp()
	_bake_static_geometry()
	# Start points remain navigable even if decorative placement is changed later.
	for cell: Vector2i in START_CLEAR:
		navigation.set_point_solid(cell, false)


func is_walkable(cell: Vector2i) -> bool:
	return navigation != null and MAP_RECT.has_point(cell) and not navigation.is_point_solid(cell)


func world_to_cell(pos: Vector3) -> Vector2i:
	return Vector2i(roundi(pos.x), roundi(pos.z))


func cell_to_world(cell: Vector2i) -> Vector3:
	return Vector3(float(cell.x), 0.0, float(cell.y))


func _create_materials() -> void:
	var ground := ShaderMaterial.new()
	ground.shader = preload("res://assets/environment/ground.gdshader")
	ground.set_shader_parameter("main_path", PackedVector2Array(_main_path))
	ground.set_shader_parameter("branch_path", PackedVector2Array(_branch_path))
	_materials["grass"] = ground
	_materials["earth"] = _surface_material(Color("695840"), 9.0, 0.45)
	_materials["path_edge"] = _material(Color("989360"))
	_materials["path"] = _surface_material(Color("b8a574"), 28.0, 0.24)
	_materials["shore"] = _surface_material(Color("948967"), 30.0, 0.25)
	var water := ShaderMaterial.new()
	water.shader = preload("res://assets/environment/water.gdshader")
	_materials["water"] = water
	_materials["water_light"] = _material(Color("8cae9d"))
	_materials["wood"] = _surface_material(Color("66513a"), 20.0, 0.55, true)
	_materials["wood_light"] = _surface_material(Color("a2895c"), 20.0, 0.24, true)
	_materials["bark"] = _surface_material(Color("66543f"), 24.0, 0.65, true)
	var leaves := ShaderMaterial.new()
	leaves.shader = preload("res://assets/environment/foliage.gdshader")
	_materials["leaf"] = leaves
	_materials["leaf_dark"] = _material(Color("475633"))
	_materials["leaf_light"] = _material(Color("81934e"))
	_materials["rock"] = _surface_material(Color("7f8175"), 19.0, 0.24)
	_materials["rock_light"] = _surface_material(Color("a5a58e"), 28.0, 0.22)
	_materials["moss"] = _surface_material(Color("697747"), 22.0, 0.32)
	_materials["plaster"] = _surface_material(Color("d1c5a4"), 30.0, 0.20)
	_materials["roof"] = _surface_material(Color("66584a"), 12.0, 0.35)
	_materials["iron"] = _material(Color("535347"))
	_materials["paper"] = _surface_material(Color("dacf9f"), 45.0, 0.08)
	_materials["ink"] = _material(Color("675a42"))
	_materials["target"] = _material(Color("976757"))
	_materials["grass_detail"] = _vertex_material()
	_materials["flowers"] = _vertex_material()


func _surface_material(color: Color, frequency: float, amount: float, is_wood: bool = false) -> ShaderMaterial:
	var material := ShaderMaterial.new()
	material.shader = preload("res://assets/environment/surface.gdshader")
	material.set_shader_parameter("base_color", color)
	material.set_shader_parameter("grain_scale", frequency)
	material.set_shader_parameter("grain_amount", amount)
	material.set_shader_parameter("wood", is_wood)
	return material


func _material(color: Color) -> StandardMaterial3D:
	var result := StandardMaterial3D.new()
	result.albedo_color = color
	result.roughness = 1.0
	return result


func _vertex_material() -> StandardMaterial3D:
	var result := StandardMaterial3D.new()
	result.vertex_color_use_as_albedo = true
	result.cull_mode = BaseMaterial3D.CULL_DISABLED
	result.roughness = 1.0
	return result


func _build_ground() -> void:
	_box(Vector3(0, -0.36, 0), Vector3(SCENERY_EXTENT, 0.66, SCENERY_EXTENT), "earth")
	var meadow := PlaneMesh.new()
	meadow.size = Vector2.ONE * SCENERY_EXTENT
	_instance(meadow, Vector3.ZERO, "grass")
	# Pebbles are very small dressing, never navigation obstacles.
	for idx: int in range(90):
		var x: float = _rng.randf_range(-13.5, 13.5)
		var z: float = _rng.randf_range(-13.5, 13.5)
		if x > 7.05 and x < 10.95:
			continue
		if _near_path(Vector2(x, z), 0.65):
			continue
		_sphere(Vector3(x, 0.024, z), Vector3(0.08, 0.045, 0.065) * _rng.randf_range(0.7, 1.8), "rock_light", 5, 3)


func _build_river() -> void:
	_box(Vector3(9, 0.002, 0), Vector3(3.85, 0.004, SCENERY_EXTENT), "shore")
	_box(Vector3(9, 0.003, 0), Vector3(3.25, 0.006, SCENERY_EXTENT), "water")
	for z: int in range(-14, 15):
		for x: int in range(8, 11):
			if absi(z) > 1:
				navigation.set_point_solid(Vector2i(x, z), true)
	# Quiet reed banks keep the stream tied to the meadow instead of a flat blue strip.
	for idx: int in range(24):
		var z: float = -13.5 + float(idx) * 1.15
		if absf(z) < 1.8:
			continue
		var x: float = 7.25 if idx % 2 == 0 else 10.73
		_sphere(Vector3(x, 0.025, z), Vector3(0.15, 0.09, 0.20), "rock", 6, 3)
	# The bridge spans all three passable river rows and sits close to the walk plane.
	for idx: int in range(12):
		_box(Vector3(7.2 + float(idx) * 0.33, -0.025, 0), Vector3(0.30, 0.08, 2.8), "wood_light" if idx % 3 else "wood")
	for z: float in [-1.43, 1.43]:
		for x: float in [7.25, 9.0, 10.75]:
			_box(Vector3(x, 0.36, z), Vector3(0.13, 0.72, 0.13), "wood")
		_box(Vector3(9.0, 0.62, z), Vector3(3.65, 0.12, 0.11), "wood_light")
		_box(Vector3(9.0, 0.30, z), Vector3(3.65, 0.07, 0.075), "wood")


func _build_trees() -> void:
	var trees: Array[Vector3] = [
		Vector3(-12, 0, -12), Vector3(-8.8, 0, -12.8), Vector3(-5.5, 0, -12),
		Vector3(-2.2, 0, -13), Vector3(1.2, 0, -12.5), Vector3(4.8, 0, -12),
		Vector3(-13, 0, -8), Vector3(-11.8, 0, -6.5), Vector3(-13.1, 0, 0.3),
		Vector3(-12.3, 0, 3.2), Vector3(-13.0, 0, 8.5), Vector3(-10.4, 0, 12.5),
		Vector3(-7.4, 0, 13.0), Vector3(-4.6, 0, 11.7), Vector3(4.2, 0, 12.8),
		Vector3(6, 0, 10.5), Vector3(12.4, 0, 11.5), Vector3(13.2, 0, 7.4),
		Vector3(13.3, 0, 4.5), Vector3(13.0, 0, -5.0), Vector3(12.0, 0, -9),
		Vector3(13.2, 0, -12.5), Vector3(-7.5, 0, 4.3), Vector3(-8.5, 0, -8),
		Vector3(4.8, 0, -7.6)
	]
	for idx: int in range(trees.size()):
		_tree(trees[idx], _rng.randf_range(0.85, 1.2), idx)


func _tree(pos: Vector3, size: float, variant: int) -> void:
	var root := Node3D.new()
	root.position = pos
	root.scale = Vector3.ONE * size
	root.rotation.y = float(variant) * 1.71
	add_child(root)
	_cylinder(Vector3(0, 0.85, 0), 0.13, 0.24, 1.7, "bark", root)
	for angle: float in [0.0, 1.6, 3.1, 4.6]:
		_branch_between(Vector3(0, 0.28, 0), Vector3(cos(angle) * 0.48, 0.045, sin(angle) * 0.48), 0.12, 0.045, "bark", root)
	for idx: int in range(5):
		var angle: float = float(idx) * 1.27 + 0.3
		var endpoint := Vector3(cos(angle) * 0.85, 1.80 + float(idx % 2) * 0.17, sin(angle) * 0.80)
		_branch_between(Vector3(0, 1.0, 0), endpoint, 0.12, 0.045, "bark", root)
	# One mesh with broad irregular overlapping crown planes rather than round balls.
	var vertices := PackedVector3Array()
	var normals := PackedVector3Array()
	for lobe: int in range(7):
		var angle: float = float(lobe) * 2.4
		var offset := Vector3(cos(angle) * 0.61, 2.00 + float(lobe % 3) * 0.22, sin(angle) * 0.59)
		if lobe == 6:
			offset = Vector3(0.03, 2.67, 0.05)
		var extent := Vector3(0.88, 0.49, 0.82) if lobe != 6 else Vector3(0.91, 0.56, 0.80)
		_append_crown(vertices, normals, offset, extent, variant * 13 + lobe)
	var arrays: Array = []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = vertices
	arrays[Mesh.ARRAY_NORMAL] = normals
	var crown := ArrayMesh.new()
	crown.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	_instance(crown, Vector3.ZERO, "leaf", root)
	_block_disc(pos, 0.70)


func _branch_between(start: Vector3, end: Vector3, bottom: float, top: float, key: String, parent: Node3D = null) -> void:
	var branch := _cylinder((start + end) * 0.5, top, bottom, start.distance_to(end), key, parent)
	branch.quaternion = Quaternion(Vector3.UP, (end - start).normalized())


func _crown_point(theta: float, phi: float, extent: Vector3, seed_value: float) -> Vector3:
	var scallop: float = 1.0 + 0.09 * sin(theta * 7.0 + seed_value) + 0.065 * sin(theta * 11.0 + phi * 5.0 + seed_value * 2.0)
	return Vector3(cos(theta) * sin(phi) * extent.x * scallop,
		cos(phi) * extent.y * (0.93 + 0.07 * sin(theta * 5.0 + seed_value)),
		sin(theta) * sin(phi) * extent.z * scallop)


func _append_crown(vertices: PackedVector3Array, normals: PackedVector3Array, center: Vector3, extent: Vector3, seed_value: float) -> void:
	for ring: int in range(7):
		var phi_a: float = PI * float(ring) / 7.0
		var phi_b: float = PI * float(ring + 1) / 7.0
		for segment: int in range(24):
			var theta_a: float = TAU * float(segment) / 24.0
			var theta_b: float = TAU * float(segment + 1) / 24.0
			var corners: Array[Vector3] = [_crown_point(theta_a, phi_a, extent, seed_value), _crown_point(theta_b, phi_a, extent, seed_value), _crown_point(theta_a, phi_b, extent, seed_value), _crown_point(theta_b, phi_b, extent, seed_value)]
			for index: int in [0, 2, 1, 1, 2, 3]:
				vertices.append(center + corners[index])
				normals.append((corners[index] / extent / extent).normalized())


func _build_rocks() -> void:
	var rocks: Array[Vector3] = [Vector3(-9, 0, 7), Vector3(-8.3, 0, 7.5), Vector3(-5.5, 0, -8.8), Vector3(5.4, 0, -4.7), Vector3(5.8, 0, 7.2), Vector3(11.8, 0, -3), Vector3(-11, 0, -10)]
	for idx: int in range(rocks.size()):
		var pos: Vector3 = rocks[idx]
		var size: float = _rng.randf_range(0.52, 0.83)
		var rock := _sphere(pos + Vector3(0, size * 0.38, 0), Vector3(size, size * 0.65, size * 0.75), "rock", 8, 4)
		rock.rotation.y = _rng.randf_range(-PI, PI)
		_sphere(pos + Vector3(-size * 0.12, size * 0.73, -size * 0.08), Vector3(size * 0.64, size * 0.10, size * 0.48), "moss", 6, 3)
		_block_disc(pos, 0.65)


func _build_fence() -> void:
	for idx: int in range(6):
		var x: float = -11.0 + float(idx) * 1.35
		_box(Vector3(x, 0.52, 10.1), Vector3(0.16, 1.04, 0.16), "wood_light")
		if idx < 5:
			for y: float in [0.38, 0.76]:
				_box(Vector3(x + 0.68, y, 10.1), Vector3(1.39, 0.11, 0.12), "wood")
			navigation.set_point_solid(world_to_cell(Vector3(x + 0.68, 0, 10.1)), true)
		navigation.set_point_solid(world_to_cell(Vector3(x, 0, 10.1)), true)


func _build_waymarker() -> void:
	var origin := Vector3(2.25, 0, 3.6)
	_box(origin + Vector3(0, 0.55, 0), Vector3(0.13, 1.1, 0.14), "wood")
	var sign := _box(origin + Vector3(-0.06, 0.95, 0), Vector3(0.85, 0.29, 0.13), "wood_light")
	sign.rotation.z = -0.08
	# A simple cream trail stripe on the wooden sign.
	_box(origin + Vector3(-0.10, 0.95, 0.073), Vector3(0.44, 0.055, 0.012), "path")
	_block_disc(origin, 0.4)


func _build_grass() -> void:
	var vertices := PackedVector3Array()
	var colors := PackedColorArray()
	var grass_colors: Array[Color] = [Color("566a39"), Color("687b43"), Color("969e57"), Color("748146")]
	for idx: int in range(1100):
		var pos := Vector2(_rng.randf_range(-13.8, 13.8), _rng.randf_range(-13.8, 13.8))
		if pos.x > 7.1 and pos.x < 10.9:
			continue
		if _near_path(pos, 1.20):
			continue
		var color: Color = grass_colors[idx % grass_colors.size()]
		for blade: int in range(3):
			var angle: float = float(blade) * 2.1 + float(idx)
			var span := Vector3(cos(angle) * 0.07, 0, sin(angle) * 0.07)
			var center := Vector3(pos.x, 0.008, pos.y)
			var tip := center + Vector3(cos(angle) * 0.06, _rng.randf_range(0.10, 0.23), sin(angle) * 0.06)
			_append_triangle(vertices, colors, center - span, center + span, tip, color)
	_colored_mesh(vertices, colors, "grass_detail")


func _build_flowers() -> void:
	var vertices := PackedVector3Array()
	var colors := PackedColorArray()
	var flower_colors: Array[Color] = [Color("d9d4aa"), Color("cdb564"), Color("c29f9d"), Color("aaadc4")]
	var clusters: Array[Vector2] = [Vector2(-5.7, 3.2), Vector2(-4.2, -6.6), Vector2(3.8, 3.6), Vector2(-3.5, 7.8), Vector2(5.8, -9.7), Vector2(-10.2, -0.5), Vector2(11.8, 6.0)]
	for cluster_idx: int in range(clusters.size()):
		for idx: int in range(12):
			var origin: Vector2 = clusters[cluster_idx] + Vector2(_rng.randf_range(-0.95, 0.95), _rng.randf_range(-0.6, 0.6))
			var height: float = _rng.randf_range(0.13, 0.25)
			var center := Vector3(origin.x, height, origin.y)
			var color: Color = flower_colors[cluster_idx % flower_colors.size()]
			_append_triangle(vertices, colors, Vector3(origin.x - 0.014, 0.005, origin.y), Vector3(origin.x + 0.014, 0.005, origin.y), center, Color("527d40"))
			for petal: int in range(5):
				var angle: float = float(petal) * TAU / 5.0
				var radius: float = 0.095
				var tip := center + Vector3(cos(angle) * radius, 0.006, sin(angle) * radius)
				var side := Vector3(-sin(angle) * 0.042, 0, cos(angle) * 0.042)
				_append_triangle(vertices, colors, center, tip - side, tip + side, color)
	_colored_mesh(vertices, colors, "flowers")


func _near_path(pos: Vector2, distance: float) -> bool:
	for path: Array[Vector2] in [_main_path, _branch_path]:
		for idx: int in range(path.size() - 1):
			var nearest: Vector2 = Geometry2D.get_closest_point_to_segment(pos, path[idx], path[idx + 1])
			if pos.distance_to(nearest) < distance:
				return true
	return false


func _block_disc(pos: Vector3, radius: float) -> void:
	var base := world_to_cell(pos)
	for x: int in range(base.x - 1, base.x + 2):
		for z: int in range(base.y - 1, base.y + 2):
			var cell := Vector2i(x, z)
			if MAP_RECT.has_point(cell) and Vector2(float(x) - pos.x, float(z) - pos.z).length() < radius + 0.25:
				navigation.set_point_solid(cell, true)


func _ribbon(points: Array[Vector2], width: float, elevation: float, material_key: String) -> void:
	var vertices := PackedVector3Array()
	var normals := PackedVector3Array()
	var edges: Array[Vector2] = []
	for idx: int in range(points.size()):
		var tangent: Vector2
		if idx == 0:
			tangent = (points[1] - points[0]).normalized()
		elif idx == points.size() - 1:
			tangent = (points[idx] - points[idx - 1]).normalized()
		else:
			tangent = (points[idx + 1] - points[idx - 1]).normalized()
		var side := Vector2(-tangent.y, tangent.x) * width * 0.5
		edges.append(points[idx] - side)
		edges.append(points[idx] + side)
	for idx: int in range(points.size() - 1):
		for corner: int in [idx * 2, idx * 2 + 2, idx * 2 + 1, idx * 2 + 1, idx * 2 + 2, idx * 2 + 3]:
			vertices.append(Vector3(edges[corner].x, elevation, edges[corner].y))
			normals.append(Vector3.UP)
	var arrays: Array = []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = vertices
	arrays[Mesh.ARRAY_NORMAL] = normals
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	_instance(mesh, Vector3.ZERO, material_key)


func _append_triangle(vertices: PackedVector3Array, colors: PackedColorArray, a: Vector3, b: Vector3, c: Vector3, color: Color) -> void:
	vertices.append_array(PackedVector3Array([a, b, c]))
	colors.append_array(PackedColorArray([color, color, color]))


func _colored_mesh(vertices: PackedVector3Array, colors: PackedColorArray, material_key: String) -> void:
	var arrays: Array = []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = vertices
	arrays[Mesh.ARRAY_COLOR] = colors
	var normals := PackedVector3Array()
	for idx: int in range(vertices.size()):
		normals.append(Vector3.UP)
	arrays[Mesh.ARRAY_NORMAL] = normals
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	_instance(mesh, Vector3.ZERO, material_key)


func _box(pos: Vector3, size: Vector3, material_key: String, parent: Node3D = null) -> MeshInstance3D:
	var mesh := BoxMesh.new()
	mesh.size = size
	return _instance(mesh, pos, material_key, parent)


func _sphere(pos: Vector3, size: Vector3, material_key: String, segments: int = 8, rings: int = 4, parent: Node3D = null) -> MeshInstance3D:
	var mesh := SphereMesh.new()
	mesh.radius = 1.0
	mesh.height = 2.0
	mesh.radial_segments = segments
	mesh.rings = rings
	var result := _instance(mesh, pos, material_key, parent)
	result.scale = size
	return result


func _cylinder(pos: Vector3, top: float, bottom: float, height: float, material_key: String, parent: Node3D = null) -> MeshInstance3D:
	var mesh := CylinderMesh.new()
	mesh.top_radius = top
	mesh.bottom_radius = bottom
	mesh.height = height
	mesh.radial_segments = 7
	return _instance(mesh, pos, material_key, parent)


func _instance(mesh: Mesh, pos: Vector3, material_key: String, parent: Node3D = null) -> MeshInstance3D:
	var result := MeshInstance3D.new()
	result.mesh = mesh
	result.position = pos
	result.material_override = _materials[material_key] as Material
	_static_meshes.append(result)
	if parent == null:
		add_child(result)
	else:
		parent.add_child(result)
	return result


func _build_camp() -> void:
	# An obvious human landmark helps the open field feel inhabited and gives the
	# spawn a recognizable home. Every solid prop marks its navigation cells.
	for row: int in range(5):
		for col: int in range(6):
			var x: float = -5.25 + float(col) * 0.45 + float(row % 2) * 0.18
			var z: float = 2.65 + float(row) * 0.46
			if (Vector2(x, z) - Vector2(-4.0, 3.6)).length() > 1.5:
				continue
			var stone := _box(Vector3(x, 0.023, z), Vector3(_rng.randf_range(0.34, 0.42), 0.045, _rng.randf_range(0.31, 0.40)), "rock_light" if (row + col) % 3 else "rock")
			stone.rotation.y = _rng.randf_range(-0.09, 0.09)
	var board := Vector3(-4.4, 0, 3.3)
	for side: float in [-0.57, 0.57]:
		_box(board + Vector3(side, 0.73, 0), Vector3(0.14, 1.46, 0.15), "wood")
		_box(board + Vector3(side, 0.09, 0), Vector3(0.32, 0.18, 0.31), "rock")
	_box(board + Vector3(0, 1.03, 0), Vector3(1.33, 0.77, 0.12), "wood_light")
	for side: float in [-0.67, 0.67]:
		_box(board + Vector3(side, 1.03, 0.025), Vector3(0.07, 0.85, 0.15), "wood")
	for y: float in [0.61, 1.45]:
		_box(board + Vector3(0, y, 0.025), Vector3(1.4, 0.07, 0.15), "wood")
	# Roof boards and ridge make a small, readable classic village noticeboard.
	for side: float in [-1.0, 1.0]:
		var roof := _box(board + Vector3(0, 1.61, side * 0.18), Vector3(1.65, 0.075, 0.46), "roof")
		roof.rotation.x = side * -0.38
	_box(board + Vector3(0, 1.69, 0), Vector3(1.67, 0.08, 0.075), "wood")
	for idx: int in range(3):
		var sheet := board + Vector3(-0.40 + float(idx) * 0.39, 1.04 + float(idx % 2) * 0.08, 0.075)
		var paper := _box(sheet, Vector3(0.28, 0.38, 0.009), "paper")
		paper.rotation.z = -0.07 + float(idx) * 0.05
		for line: int in range(3):
			_box(sheet + Vector3(0, 0.05 - float(line) * 0.07, 0.007), Vector3(0.19 if line != 2 else 0.12, 0.012, 0.005), "ink")
		_sphere(sheet + Vector3(0, 0.14, 0.012), Vector3(0.017, 0.017, 0.008), "iron", 5, 3)
	for cell: Vector2i in [Vector2i(-5, 3), Vector2i(-4, 3)]:
		navigation.set_point_solid(cell, true)
	# Supply barrel: staves, dark hoops and a recessed lid.
	var barrel := Vector3(-5.7, 0, 4.4)
	_cylinder(barrel + Vector3(0, 0.30, 0), 0.28, 0.26, 0.6, "wood_light")
	for y: float in [0.09, 0.49]:
		_cylinder(barrel + Vector3(0, y, 0), 0.285, 0.285, 0.046, "iron")
	_cylinder(barrel + Vector3(0, 0.605, 0), 0.238, 0.238, 0.022, "wood")
	_block_disc(barrel, 0.44)
	# Straw target mounted on an A-frame, a visual promise of a training ground.
	var target := Vector3(-3.6, 0, 5.4)
	for x: float in [-0.28, 0.28]:
		_branch_between(target + Vector3(x, 0, 0.25), target + Vector3(x * 0.3, 1.02, 0), 0.05, 0.035, "wood")
		_branch_between(target + Vector3(x, 0, -0.23), target + Vector3(x * 0.3, 1.02, 0), 0.05, 0.035, "wood")
	for item: Array in [[0.43, 0.05, "wood_light"], [0.31, 0.079, "target"], [0.22, 0.084, "paper"], [0.105, 0.090, "target"]]:
		var disc := _cylinder(target + Vector3(0, 0.92, float(item[1])), float(item[0]), float(item[0]), 0.055, str(item[2]))
		disc.rotation.x = PI * 0.5
	_block_disc(target, 0.55)


func _bake_static_geometry() -> void:
	# Static scenery is combined by material. Hundreds of authored pieces become
	# a small set of surfaces while retaining their normals and vertex colors.
	var groups: Dictionary = {}
	var source_count: int = _static_meshes.size()
	var triangle_count: int = 0
	for part: MeshInstance3D in _static_meshes:
		var material: Material = part.material_override
		if not groups.has(material):
			groups[material] = SurfaceTool.new()
			(groups[material] as SurfaceTool).begin(Mesh.PRIMITIVE_TRIANGLES)
		var transform_to_field: Transform3D = global_transform.affine_inverse() * part.global_transform
		(groups[material] as SurfaceTool).append_from(part.mesh, 0, transform_to_field)
	for material: Material in groups:
		var combined: ArrayMesh = (groups[material] as SurfaceTool).commit()
		var result := MeshInstance3D.new()
		result.name = "ScenerySurface%d" % get_child_count()
		result.mesh = combined
		result.material_override = material
		add_child(result)
		var index_count: int = combined.surface_get_array_index_len(0)
		triangle_count += (index_count if index_count > 0 else combined.surface_get_array_len(0)) / 3
	for part: MeshInstance3D in _static_meshes:
		part.get_parent().remove_child(part)
		part.free()
	_static_meshes.clear()
	for child: Node in get_children():
		if child is Node3D and not child is MeshInstance3D and child.get_child_count() == 0:
			remove_child(child)
			child.free()
	environment_metrics = {"authored_meshes": source_count, "render_meshes": groups.size(), "triangles": triangle_count, "nodes": get_child_count()}
