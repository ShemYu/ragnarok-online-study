extends SceneTree

const MapData := preload("res://scripts/ro_map_data.gd")
var checks: int = 0
var failures: int = 0


func _initialize() -> void:
	var gnd := _ground_fixture()
	var gat := _altitude_fixture()
	_write("user://map-test.gnd",gnd)
	_write("user://map-test.gat",gat)
	var data := MapData.new()
	var picture := Image.create(4,4,false,Image.FORMAT_RGBA8)
	picture.fill(Color.GREEN)
	_check(data.load_map("user://map-test.gnd","user://map-test.gat",{"grass.bmp":ImageTexture.create_from_image(picture)}), "Fixture loads")
	_check(data.ground_size == Vector2i(2,1) and data.gat_size == Vector2i(4,2), "GND/GAT coordinate ratio")
	_check(data.texture_names == ["grass.bmp"], "Null-terminated texture name")
	_check(data.is_walkable(Vector2i(0,0)) and not data.is_walkable(Vector2i(1,0)), "Walkable and blocked cell types")
	_check(not data.is_walkable(Vector2i(-1,0)), "Bounds reject navigation")
	_check(is_equal_approx(data.height_at(Vector2(0.5,0.5)),1.0), "Negative raw heights become upward elevation")
	_check(data.tiles[0].color == Color8(100,150,200), "BGRA surface color converts to RGB")
	var root_node := Node3D.new()
	root.add_child(root_node)
	var result: Dictionary = data.build_ground(root_node,Rect2i(0,0,4,2),Vector2(2,1),1.0)
	_check(result.surfaces == 3 and result.triangles == 6, "Top faces and the shared elevation wall")
	_check(result.missing_textures.is_empty() and result.materials == 1, "Texture batch resolves without fallback")
	var mesh: ArrayMesh = root_node.get_child(0).mesh
	var vertices: PackedVector3Array = mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
	_check(vertices.has(Vector3(-2,0,-1)) and vertices.has(Vector3(2,1,1)), "Crop origin and vertical origin preserve geometry")
	var uvs: PackedVector2Array = mesh.surface_get_arrays(0)[Mesh.ARRAY_TEX_UV]
	_check(vertices[6] == Vector3(0,0,1) and uvs[6] == Vector2.ZERO, "East wall retains authored texture orientation")
	var lm := data.lightmap.get_image()
	_check(lm.get_pixel(3,3).a == 1.0 and lm.get_pixel(3,3).r == 0.0, "Separate light and shadow channels")
	root_node.free()
	# Truncation must fail rather than reading unrelated bytes as dimensions.
	_write("user://map-test-bad.gnd",gnd.slice(0,gnd.size()-1))
	var malformed := MapData.new()
	_check(not malformed.load_map("user://map-test-bad.gnd","user://map-test.gat"), "Truncated surface data rejected")
	for path: String in ["user://map-test.gnd","user://map-test.gat","user://map-test-bad.gnd"]:
		DirAccess.remove_absolute(path)
	if FileAccess.file_exists("res://assets/reference-ro/map-study/prt_fild08.gat"):
		var actual := MapData.new()
		_check(actual.load_map("res://assets/reference-ro/map-study/prt_fild08.gnd","res://assets/reference-ro/map-study/prt_fild08.gat"), "Actual Prontera South field parses")
		_check(actual.gat_size == Vector2i(400,400), "Actual native map dimensions")
		_check(actual.is_walkable(Vector2i(170,350)) and is_equal_approx(actual.height_at(Vector2(170.5,350.5)),-1.35), "Actual walkable start cell height")
	print("RO_MAP_DATA_TEST: %d checks passed, %d failed" % [checks,failures])
	quit(1 if failures else 0)


func _check(ok: bool, description: String) -> void:
	if not ok:
		push_error(description)
		failures += 1
		return
	checks += 1


func _write(path: String, bytes: PackedByteArray) -> void:
	var file := FileAccess.open(path,FileAccess.WRITE)
	file.store_buffer(bytes)


func _ground_fixture() -> PackedByteArray:
	var b := StreamPeerBuffer.new()
	b.put_data("GRGN".to_ascii_buffer())
	b.put_u8(1)
	b.put_u8(7)
	b.put_u32(2)
	b.put_u32(1)
	b.put_float(10.0)
	b.put_u32(1)
	b.put_u32(80)
	var name_bytes := "grass.bmp".to_ascii_buffer()
	name_bytes.resize(80)
	b.put_data(name_bytes)
	b.put_u32(1)
	b.put_u32(8)
	b.put_u32(8)
	b.put_u32(1)
	for index: int in range(256):
		b.put_u8(255 if index < 64 else 0)
	b.put_u32(1)
	for number: float in [0.0,1.0,0.0,1.0,0.0,0.0,1.0,1.0]:
		b.put_float(number)
	b.put_u16(0)
	b.put_u16(0)
	for number: int in [200,150,100,255]:
		b.put_u8(number)
	for cell: int in range(2):
		for _corner: int in range(4):
			b.put_float(-5.0 if cell == 0 else -10.0)
		b.put_32(0)
		b.put_32(-1)
		b.put_32(0 if cell == 0 else -1)
	return b.data_array


func _altitude_fixture() -> PackedByteArray:
	var b := StreamPeerBuffer.new()
	b.put_data("GRAT".to_ascii_buffer())
	b.put_u8(1)
	b.put_u8(2)
	b.put_u32(4)
	b.put_u32(2)
	for cell: int in range(8):
		for _corner: int in range(4):
			b.put_float(-5.0)
		b.put_u32(1 if cell == 1 else 0)
	return b.data_array
