extends RefCounted
## Static classic RSM 1.x meshes. Coordinate/registration behavior follows the
## documented RSM layout and roBrowser's Loaders/Model.js implementation.
## RSM vertices are raw client units; this loader makes one GAT cell one unit.
const RAW_SCALE := 0.2
const FLIP_Y := Basis(Vector3.RIGHT, Vector3.DOWN, Vector3.BACK)
static var _models: Dictionary = {}
static var _textures: Dictionary = {}
static var _meshes: Dictionary = {}

class Reader:
	extends RefCounted
	var bytes: PackedByteArray
	var at := 0
	var failed := false
	func _init(data: PackedByteArray):
		bytes = data
	func take(size: int) -> PackedByteArray:
		if size < 0 or at + size > bytes.size():
			failed = true
			return PackedByteArray()
		var result := bytes.slice(at, at + size)
		at += size
		return result
	func u8() -> int:
		var raw := take(1)
		return raw.decode_u8(0) if raw.size() == 1 else 0
	func u16() -> int:
		var raw := take(2)
		return raw.decode_u16(0) if raw.size() == 2 else 0
	func i32() -> int:
		var raw := take(4)
		return raw.decode_s32(0) if raw.size() == 4 else 0
	func f32() -> float:
		var raw := take(4)
		var value := raw.decode_float(0) if raw.size() == 4 else 0.0
		if not is_finite(value):
			failed = true
			return 0.0
		return value
	func v3() -> Vector3:
		return Vector3(f32(), f32(), f32())
	func string(size: int) -> String:
		# Preserve original byte-valued names; provenance supplies the decoded name.
		var raw := take(size)
		var result := ""
		for value in raw:
			if value == 0:
				break
			result += String.chr(value)
		return result
	func count(stride: int = 1, cap: int = 1000000) -> int:
		var value := i32()
		if value < 0 or value > cap or value * stride > bytes.size() - at:
			failed = true
			return 0
		return value

static func load_model(path: String) -> Dictionary:
	if _models.has(path):
		return _models[path]
	if not FileAccess.file_exists(path):
		push_error("Missing RSM: " + path)
		return {}
	var result := decode(FileAccess.get_file_as_bytes(path))
	if result.is_empty():
		push_error("Invalid or unsupported classic RSM: " + path)
		return {}
	result.source = path
	_models[path] = result
	return result

static func decode(bytes: PackedByteArray) -> Dictionary:
	var reader := Reader.new(bytes)
	if reader.string(4) != "GRSM":
		return {}
	var major := reader.u8()
	var minor := reader.u8()
	if major != 1 or minor > 6:
		return {}
	var result := {"version": Vector2i(major, minor), "animation_length": reader.i32(), "shade_type": reader.i32()}
	result.alpha = reader.u8() / 255.0 if minor >= 4 else 1.0
	reader.take(16)
	var texture_count := reader.count(40, 4096)
	var textures: Array[String] = []
	for i in texture_count:
		textures.append(reader.string(40))
	result.textures = textures
	result.root_name = reader.string(40)
	var node_count := reader.count(140, 4096)
	if node_count == 0:
		return {}
	var nodes: Array[Dictionary] = []
	for i in node_count:
		var node := {"name": reader.string(40), "parent": reader.string(40)}
		var node_textures: Array[int] = []
		for j in reader.count(4, 4096):
			var index := reader.i32()
			if index < 0 or index >= texture_count:
				reader.failed = true
			node_textures.append(index)
		node.textures = node_textures
		node.basis = Basis(reader.v3(), reader.v3(), reader.v3())
		node.offset = reader.v3()
		node.position = reader.v3()
		node.angle = reader.f32()
		node.axis = reader.v3()
		node.scale = reader.v3()
		var vertices := PackedVector3Array()
		for j in reader.count(12):
			vertices.append(reader.v3())
		node.vertices = vertices
		var uvs := PackedVector2Array()
		for j in reader.count(12 if minor >= 2 else 8):
			if minor >= 2:
				reader.take(4) # Legacy texture vertex color is not scene lighting.
			uvs.append(Vector2(reader.f32(), reader.f32()))
		node.uvs = uvs
		var faces: Array[Dictionary] = []
		for j in reader.count(24 if minor >= 2 else 20):
			var face := {"vertices": [reader.u16(), reader.u16(), reader.u16()], "uvs": [reader.u16(), reader.u16(), reader.u16()], "texture": reader.u16()}
			reader.u16()
			face.two_sided = reader.i32() != 0
			face.smooth_group = reader.i32() if minor >= 2 else -1
			for index: int in face.vertices:
				if index >= vertices.size():
					reader.failed = true
			for index: int in face.uvs:
				if index >= uvs.size():
					reader.failed = true
			if face.texture >= node_textures.size():
				reader.failed = true
			faces.append(face)
		node.faces = faces
		if minor >= 6:
			reader.take(reader.count(20) * 20)
		var rotations := reader.count(20)
		node.rotation_keys = rotations
		for j in rotations:
			reader.i32()
			var q := Quaternion(reader.f32(), reader.f32(), reader.f32(), reader.f32())
			if j == 0 and q.length_squared() > 0.000001:
				node.first_rotation = q.normalized()
		nodes.append(node)
	if minor < 6:
		reader.take(reader.count(20) * 20)
	if reader.at < bytes.size():
		reader.take(reader.count(40 if minor >= 3 else 36) * (40 if minor >= 3 else 36))
	if reader.failed:
		return {}
	result.nodes = nodes
	if not _resolve_transforms(result):
		return {}
	return result

static func _resolve_transforms(model: Dictionary) -> bool:
	var by_name: Dictionary = {}
	for i in model.nodes.size():
		by_name[model.nodes[i].name] = i
	var visiting: Dictionary = {}
	for i in model.nodes.size():
		if not _resolve_node(model.nodes, i, by_name, visiting):
			return false
	var first := true
	var bounds := AABB()
	for node: Dictionary in model.nodes:
		var geometry: Transform3D = node.transform
		if model.nodes.size() > 1:
			geometry = geometry * Transform3D(Basis.IDENTITY, node.offset)
		geometry = geometry * Transform3D(node.basis, Vector3.ZERO)
		node.geometry_transform = geometry
		for vertex: Vector3 in node.vertices:
			var point := geometry * vertex
			if first:
				bounds = AABB(point, Vector3.ZERO)
				first = false
			else:
				bounds = bounds.expand(point)
	if first:
		return false
	model.raw_bounds = bounds
	model.registration = Vector3(bounds.get_center().x, bounds.end.y, bounds.get_center().z)
	model.size = bounds.size * RAW_SCALE
	return true

static func _resolve_node(nodes: Array, index: int, names: Dictionary, visiting: Dictionary) -> bool:
	var node: Dictionary = nodes[index]
	if node.has("transform"):
		return true
	if visiting.has(index):
		return false
	visiting[index] = true
	var parent := Transform3D.IDENTITY
	if names.has(node.parent) and node.parent != node.name:
		var parent_index: int = names[node.parent]
		if not _resolve_node(nodes, parent_index, names, visiting):
			return false
		parent = nodes[parent_index].transform
	var rotation := Basis.IDENTITY
	if node.has("first_rotation"):
		rotation = Basis(node.first_rotation)
	elif node.axis.length_squared() > 0.000001 and not is_zero_approx(node.angle):
		rotation = Basis(node.axis.normalized(), node.angle)
	node.transform = parent * Transform3D(rotation * Basis.from_scale(node.scale), node.position)
	visiting.erase(index)
	return true

static func build_model(parent: Node3D, rsm_path: String, texture_map: Dictionary, rsw_transform: Dictionary = {}) -> Node3D:
	var data := load_model(rsm_path)
	if data.is_empty():
		return null
	var model := Node3D.new()
	model.name = rsm_path.get_file().get_basename()
	parent.add_child(model)
	model.position = rsw_transform.get("position", Vector3.ZERO)
	var angles: Vector3 = rsw_transform.get("rotation", Vector3.ZERO) * PI / 180.0
	var rotation := Basis(Vector3.BACK, angles.z) * Basis(Vector3.RIGHT, angles.x) * Basis(Vector3.UP, angles.y)
	model.basis = FLIP_Y * rotation * FLIP_Y * Basis.from_scale(rsw_transform.get("scale", Vector3.ONE))
	var unshaded: bool = rsw_transform.get("unshaded", true)
	var key := rsm_path + "|" + str(texture_map.hash()) + "|" + str(unshaded)
	if not _meshes.has(key):
		_meshes[key] = _make_meshes(data, texture_map, unshaded)
	for entry: Dictionary in _meshes[key]:
		var instance := MeshInstance3D.new()
		instance.mesh = entry.mesh
		instance.material_override = entry.material
		instance.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		model.add_child(instance)
	model.set_meta("rsm_bounds", AABB(Vector3(-data.size.x * 0.5, 0, -data.size.z * 0.5), data.size))
	model.set_meta("source", rsm_path)
	return model

static func _make_meshes(model: Dictionary, texture_map: Dictionary, unshaded: bool) -> Array[Dictionary]:
	var groups: Dictionary = {}
	for node: Dictionary in model.nodes:
		for face: Dictionary in node.faces:
			var texture_index: int = node.textures[face.texture]
			var key := str(texture_index) + ":" + str(face.two_sided)
			if not groups.has(key):
				groups[key] = {"vertices": PackedVector3Array(), "uvs": PackedVector2Array(), "normals": PackedVector3Array(), "texture": texture_index, "two_sided": face.two_sided}
			var group: Dictionary = groups[key]
			var points: Array[Vector3] = []
			for i in 3:
				var point: Vector3 = node.geometry_transform * node.vertices[face.vertices[i]] - model.registration
				points.append(FLIP_Y * point * RAW_SCALE)
			var normal := (points[2] - points[0]).cross(points[1] - points[0]).normalized()
			for i in [0, 1, 2]: # Y reflection converts RO/OpenGL front faces to Godot's clockwise convention.
				group.vertices.append(points[i])
				group.uvs.append(node.uvs[face.uvs[i]])
				group.normals.append(normal)
	var result: Array[Dictionary] = []
	for group: Dictionary in groups.values():
		var arrays := []
		arrays.resize(Mesh.ARRAY_MAX)
		arrays[Mesh.ARRAY_VERTEX] = group.vertices
		arrays[Mesh.ARRAY_TEX_UV] = group.uvs
		arrays[Mesh.ARRAY_NORMAL] = group.normals
		var mesh := ArrayMesh.new()
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
		var material := StandardMaterial3D.new()
		material.albedo_texture = load_texture(_texture_path(model.textures[group.texture], texture_map))
		material.albedo_color.a = model.alpha
		material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED if unshaded else BaseMaterial3D.SHADING_MODE_PER_PIXEL
		material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
		material.alpha_scissor_threshold = 0.45
		material.cull_mode = BaseMaterial3D.CULL_DISABLED if group.two_sided else BaseMaterial3D.CULL_BACK
		material.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
		material.roughness = 1.0
		result.append({"mesh": mesh, "material": material})
	return result

static func _texture_path(name: String, texture_map: Dictionary) -> String:
	var normalized := name.replace("\\", "/").to_lower()
	for key: String in texture_map:
		var candidate := key.replace("\\", "/").to_lower()
		if candidate == normalized or candidate.get_file() == normalized.get_file():
			return texture_map[key]
	push_error("No local RSM texture mapping for: " + name)
	return ""

static func load_texture(path: String) -> Texture2D:
	if _textures.has(path):
		return _textures[path]
	if path.is_empty() or not FileAccess.file_exists(path):
		return null
	var source := Image.new()
	var imported: Texture2D = load(path) if ResourceLoader.exists(path) else null
	if imported:
		source = imported.get_image()
	else:
		var error := source.load_png_from_buffer(FileAccess.get_file_as_bytes(path))
		if error != OK:
			return null
	if source == null or source.is_empty():
		return null
	source.convert(Image.FORMAT_RGBA8)
	# The BMP palette uses exact magenta transparency, not a broad hue mask.
	for y in source.get_height():
		for x in source.get_width():
			var color := source.get_pixel(x, y)
			if color.r > 0.999 and color.g < 0.001 and color.b > 0.999:
				color.a = 0.0
				source.set_pixel(x, y, color)
	# Extend edge RGB into transparent texels before linear filtering/mipmaps;
	# otherwise a correct magenta key still leaves purple leaf/roof fringes.
	source.fix_alpha_edges()
	source.generate_mipmaps()
	var texture := ImageTexture.create_from_image(source)
	_textures[path] = texture
	return texture
