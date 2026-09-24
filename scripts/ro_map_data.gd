extends RefCounted
## Reads native classic GND/GAT terrain without any networking or server state.
## One local world unit is one GAT navigation cell (five source world units).
## Binary layouts verified against roBrowser Loaders/Ground.js and Altitude.js.

var ground_size := Vector2i.ZERO
var gat_size := Vector2i.ZERO
var texture_names: Array[String] = []
var texture_sources: Dictionary = {}
var tiles: Array[Dictionary] = []
var ground_heights := PackedFloat32Array()
var ground_surfaces := PackedInt32Array()
var gat_heights := PackedFloat32Array()
var gat_types := PackedInt32Array()
var lightmap: Texture2D
var lightmap_columns: int = 1
var lightmap_rows: int = 1
var lightmap_cell_size := Vector2i(8, 8)
var last_error: String = ""
var versions: Dictionary = {}
var _materials: Dictionary = {}

const TERRAIN_SHADER := """
shader_type spatial;
render_mode unshaded, cull_disabled;
uniform sampler2D diffuse_map : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D light_map : filter_linear, repeat_disable;
uniform vec3 terrain_light = vec3(1.0);
void fragment() {
    vec4 paint = texture(diffuse_map, UV) * COLOR;
    vec4 baked = texture(light_map, UV2);
    ALBEDO = clamp(paint.rgb * terrain_light * baked.a + baked.rgb, vec3(0.0), vec3(1.0));
    ROUGHNESS = 1.0;
}
"""


func load_map(gnd_path: String, gat_path: String, textures: Dictionary = {}) -> bool:
	last_error = ""
	texture_sources = textures.duplicate()
	_materials.clear()
	texture_names.clear()
	tiles.clear()
	ground_heights.clear()
	ground_surfaces.clear()
	gat_heights.clear()
	gat_types.clear()
	if not _load_ground(gnd_path):
		return false
	if not _load_altitude(gat_path):
		return false
	if gat_size != ground_size * 2:
		return _fail("GAT dimensions must be twice GND dimensions")
	return true


func is_walkable(gat_cell: Vector2i) -> bool:
	if not Rect2i(Vector2i.ZERO, gat_size).has_point(gat_cell):
		return false
	var kind: int = gat_types[gat_cell.x + gat_cell.y * gat_size.x]
	return kind in [0, 2, 3, 4, 6]


func height_at(gat_position: Vector2) -> float:
	if gat_heights.is_empty():
		return 0.0
	var cell := Vector2i(floori(gat_position.x), floori(gat_position.y))
	cell.x = clampi(cell.x, 0, gat_size.x - 1)
	cell.y = clampi(cell.y, 0, gat_size.y - 1)
	var u: float = clampf(gat_position.x - cell.x, 0.0, 1.0)
	var v: float = clampf(gat_position.y - cell.y, 0.0, 1.0)
	var index: int = (cell.x + cell.y * gat_size.x) * 4
	# Match the terrain's 0--3 diagonal rather than bilinear interpolation.
	var a: float = gat_heights[index]
	var b: float = gat_heights[index + 1]
	var c: float = gat_heights[index + 2]
	var d: float = gat_heights[index + 3]
	return a + (b-a)*u + (d-b)*v if u >= v else a + (d-c)*u + (c-a)*v


func build_ground(parent: Node3D, crop_gat: Rect2i, origin_gat: Vector2, height_origin: float = 0.0) -> Dictionary:
	var from_cell := Vector2i(floori(crop_gat.position.x / 2.0), floori(crop_gat.position.y / 2.0))
	var to_cell := Vector2i(ceili(crop_gat.end.x / 2.0), ceili(crop_gat.end.y / 2.0))
	var region := Rect2i(from_cell, to_cell - from_cell).intersection(Rect2i(Vector2i.ZERO, ground_size))
	var batches: Dictionary = {}
	var face_count: int = 0
	for y: int in range(region.position.y, region.end.y):
		for x: int in range(region.position.x, region.end.x):
			var idx: int = x + y * ground_size.x
			var h: int = idx * 4
			var p := Vector3(x*2.0-origin_gat.x, -height_origin, y*2.0-origin_gat.y)
			var corners: Array[Vector3] = [p + Vector3(0,ground_heights[h],0), p + Vector3(2,ground_heights[h+1],0), p + Vector3(0,ground_heights[h+2],2), p + Vector3(2,ground_heights[h+3],2)]
			var colors: Array[Color] = [_ground_color(x,y), _ground_color(x+1,y), _ground_color(x,y+1), _ground_color(x+1,y+1)]
			if _append_quad(batches, ground_surfaces[idx*3], corners, colors):
				face_count += 1
			if y + 1 < ground_size.y:
				var n: int = (idx + ground_size.x)*4
				var north: Array[Vector3] = [corners[2],corners[3],p+Vector3(0,ground_heights[n],2),p+Vector3(2,ground_heights[n+1],2)]
				if _append_quad(batches, ground_surfaces[idx*3+1], north, [Color.WHITE,Color.WHITE,Color.WHITE,Color.WHITE]):
					face_count += 1
			if x + 1 < ground_size.x:
				var n: int = (idx+1)*4
				var east: Array[Vector3] = [corners[3],corners[1],p+Vector3(2,ground_heights[n+2],2),p+Vector3(2,ground_heights[n],0)]
				if _append_quad(batches, ground_surfaces[idx*3+2], east, [Color.WHITE,Color.WHITE,Color.WHITE,Color.WHITE]):
					face_count += 1
	var missing: Array[String] = []
	for texture_index: int in batches:
		var batch: Dictionary = batches[texture_index]
		var arrays: Array = []
		arrays.resize(Mesh.ARRAY_MAX)
		arrays[Mesh.ARRAY_VERTEX] = PackedVector3Array(batch.vertices)
		arrays[Mesh.ARRAY_NORMAL] = PackedVector3Array(batch.normals)
		arrays[Mesh.ARRAY_TEX_UV] = PackedVector2Array(batch.uv)
		arrays[Mesh.ARRAY_TEX_UV2] = PackedVector2Array(batch.light_uv)
		arrays[Mesh.ARRAY_COLOR] = PackedColorArray(batch.colors)
		var mesh := ArrayMesh.new()
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
		var node := MeshInstance3D.new()
		node.name = "NativeGround_%d" % texture_index
		node.mesh = mesh
		node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		node.material_override = _get_material(texture_index, missing)
		parent.add_child(node)
	return {"gnd_region":region, "surfaces":face_count, "triangles":face_count*2, "materials":batches.size(), "missing_textures":missing}


func _append_quad(batches: Dictionary, tile_index: int, corners: Array[Vector3], colors: Array[Color]) -> bool:
	if tile_index < 0 or tile_index >= tiles.size():
		return false
	var tile: Dictionary = tiles[tile_index]
	var texture_index: int = tile.texture
	if texture_index < 0 or texture_index >= texture_names.size():
		return false
	if not batches.has(texture_index):
		batches[texture_index] = {"vertices":[],"normals":[],"uv":[],"light_uv":[],"colors":[]}
	var batch: Dictionary = batches[texture_index]
	var light_index: int = tile.light
	var lx: int = light_index % lightmap_columns
	var ly: int = light_index / lightmap_columns
	var uv_min := Vector2(float(lx)+1.0/lightmap_cell_size.x, float(ly)+1.0/lightmap_cell_size.y) / Vector2(lightmap_columns,lightmap_rows)
	var uv_max := Vector2(float(lx)+1.0-1.0/lightmap_cell_size.x, float(ly)+1.0-1.0/lightmap_cell_size.y) / Vector2(lightmap_columns,lightmap_rows)
	var light_uv: Array[Vector2] = [uv_min,Vector2(uv_max.x,uv_min.y),Vector2(uv_min.x,uv_max.y),uv_max]
	var normal: Vector3 = (corners[3]-corners[0]).cross(corners[1]-corners[0]).normalized()
	for index: int in [0,1,3,3,2,0]:
		batch.vertices.append(corners[index])
		batch.normals.append(normal)
		batch.uv.append(tile.uv[index])
		batch.light_uv.append(light_uv[index])
		batch.colors.append(colors[index])
	return true


func _ground_color(x: int, y: int) -> Color:
	x = clampi(x,0,ground_size.x-1)
	y = clampi(y,0,ground_size.y-1)
	var index: int = ground_surfaces[(x+y*ground_size.x)*3]
	return tiles[index].color if index >= 0 and index < tiles.size() else Color.WHITE


func _get_material(index: int, missing: Array[String]) -> Material:
	if _materials.has(index):
		return _materials[index]
	var path: String = texture_names[index]
	var source: Variant = texture_sources.get(path, texture_sources.get(path.to_lower(), null))
	var texture: Texture2D
	if source is Texture2D:
		texture = source
	elif source is String and (ResourceLoader.exists(source) or FileAccess.file_exists(source)):
		var imported: Texture2D = load(source) if ResourceLoader.exists(source) else null
		var picture := imported.get_image() if imported else Image.new()
		if not imported:
			picture.load_png_from_buffer(FileAccess.get_file_as_bytes(source))
		if picture != null and not picture.is_empty():
			picture.generate_mipmaps()
			texture = ImageTexture.create_from_image(picture)
	if texture == null:
		missing.append(path)
		var picture := Image.create(2,2,false,Image.FORMAT_RGBA8)
		picture.fill(Color("dd00dd"))
		texture = ImageTexture.create_from_image(picture)
	var shader := Shader.new()
	shader.code = TERRAIN_SHADER
	var material := ShaderMaterial.new()
	material.shader = shader
	material.set_shader_parameter("diffuse_map",texture)
	material.set_shader_parameter("light_map",lightmap)
	_materials[index] = material
	return material


func _load_ground(path: String) -> bool:
	var data := FileAccess.get_file_as_bytes(path)
	if data.size() < 26 or data.slice(0,4).get_string_from_ascii() != "GRGN":
		return _fail("Invalid GND signature or truncated header")
	var major: int = data[4]
	var minor: int = data[5]
	if major != 1 or minor < 5 or minor > 9:
		return _fail("Unsupported GND version %d.%d" % [major,minor])
	versions.gnd = "%d.%d" % [major,minor]
	ground_size = Vector2i(data.decode_u32(6),data.decode_u32(10))
	if ground_size.x < 1 or ground_size.y < 1 or ground_size.x*ground_size.y > 1048576:
		return _fail("Invalid GND dimensions")
	var source_scale: float = data.decode_float(14)
	if not is_equal_approx(source_scale,10.0):
		return _fail("Unsupported GND coordinate scale")
	var texture_count: int = data.decode_u32(18)
	var path_length: int = data.decode_u32(22)
	if texture_count > 65535 or path_length < 1 or path_length > 4096 or data.size() < 26+texture_count*path_length+16:
		return _fail("Invalid GND texture table")
	var pos: int = 26
	for _index: int in range(texture_count):
		var raw: PackedByteArray = data.slice(pos,pos+path_length)
		var end: int = raw.find(0)
		if end >= 0:
			raw = raw.slice(0,end)
		texture_names.append(raw.get_string_from_ascii().replace("\\","/"))
		pos += path_length
	var light_count: int = data.decode_u32(pos)
	lightmap_cell_size = Vector2i(data.decode_u32(pos+4),data.decode_u32(pos+8))
	var light_format: int = data.decode_u32(pos+12)
	pos += 16
	if light_count < 1 or light_count > 65536 or lightmap_cell_size.x != 8 or lightmap_cell_size.y != 8 or light_format != 1:
		return _fail("Unsupported GND lightmap layout")
	var pixels: int = lightmap_cell_size.x*lightmap_cell_size.y
	var light_bytes: int = light_count*pixels*4
	if pos+light_bytes+4 > data.size():
		return _fail("Truncated GND lightmap data")
	_make_lightmap(data.slice(pos,pos+light_bytes),light_count)
	pos += light_bytes
	var tile_count: int = data.decode_u32(pos)
	pos += 4
	if tile_count > 1048576 or pos+tile_count*40+ground_size.x*ground_size.y*28 > data.size():
		return _fail("Truncated GND tile or surface table")
	for _index: int in range(tile_count):
		var uv: Array[Vector2] = []
		for corner: int in range(4):
			uv.append(Vector2(data.decode_float(pos+corner*4),data.decode_float(pos+16+corner*4)))
		var light_index: int = data.decode_u16(pos+34)
		if light_index >= light_count:
			return _fail("GND tile references invalid lightmap")
		tiles.append({"uv":uv,"texture":data.decode_s16(pos+32),"light":light_index,"color":Color8(data[pos+38],data[pos+37],data[pos+36],255)})
		pos += 40
	var cell_count: int = ground_size.x*ground_size.y
	ground_heights.resize(cell_count*4)
	ground_surfaces.resize(cell_count*3)
	for index: int in range(cell_count):
		for corner: int in range(4):
			ground_heights[index*4+corner] = -data.decode_float(pos+corner*4)*0.2
		for side: int in range(3):
			var surface: int = data.decode_s32(pos+16+side*4)
			if surface < -1 or surface >= tile_count:
				return _fail("GND cell references invalid surface")
			ground_surfaces[index*3+side] = surface
		pos += 28
	return true


func _load_altitude(path: String) -> bool:
	var data := FileAccess.get_file_as_bytes(path)
	if data.size() < 14 or data.slice(0,4).get_string_from_ascii() != "GRAT":
		return _fail("Invalid GAT signature or truncated header")
	if data[4] != 1 or data[5] != 2:
		return _fail("Only classic GAT 1.2 is currently supported")
	versions.gat = "1.2"
	gat_size = Vector2i(data.decode_u32(6),data.decode_u32(10))
	var count: int = gat_size.x*gat_size.y
	if gat_size.x < 1 or gat_size.y < 1 or count > 4194304 or data.size() < 14+count*20:
		return _fail("Invalid GAT dimensions or truncated cell data")
	gat_heights.resize(count*4)
	gat_types.resize(count)
	for index: int in range(count):
		var pos: int = 14+index*20
		for corner: int in range(4):
			gat_heights[index*4+corner] = -data.decode_float(pos+corner*4)*0.2
		gat_types[index] = data.decode_s32(pos+16)
	return true


func _make_lightmap(bytes: PackedByteArray, count: int) -> void:
	lightmap_columns = ceili(sqrt(float(count)))
	lightmap_rows = ceili(float(count)/lightmap_columns)
	var width: int = lightmap_columns*8
	var height: int = lightmap_rows*8
	var output := PackedByteArray()
	output.resize(width*height*4)
	for index: int in range(count):
		var ox: int = (index%lightmap_columns)*8
		var oy: int = (index/lightmap_columns)*8
		for y: int in range(8):
			for x: int in range(8):
				var src: int = index*256+x+y*8
				var dst: int = ((oy+y)*width+ox+x)*4
				output[dst] = bytes[index*256+64+(x+y*8)*3]
				output[dst+1] = bytes[index*256+65+(x+y*8)*3]
				output[dst+2] = bytes[index*256+66+(x+y*8)*3]
				output[dst+3] = bytes[src]
	lightmap = ImageTexture.create_from_image(Image.create_from_data(width,height,false,Image.FORMAT_RGBA8,output))


func _fail(message: String) -> bool:
	last_error = message
	push_error("RO map: " + message)
	return false
