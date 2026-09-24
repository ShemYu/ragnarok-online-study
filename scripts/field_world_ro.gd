extends Node3D
## A local, cropped slice of the actual Prontera south field.
## World X/Z are GAT cells; north is -Z. Native terrain, UVs and props are retained.
const MapData = preload("res://scripts/ro_map_data.gd")
const ModelData = preload("res://scripts/ro_model_data.gd")
const ROOT := "res://assets/reference-ro/map-study/"
const MAP_RECT := Rect2i(-24,-24,49,49)
const ORIGIN_GAT := Vector2(172.5,371.5)
const VISUAL_CROP := Rect2i(100,295,145,105)

var navigation: AStarGrid2D
var map_data := MapData.new()
var height_origin := 0.0
var environment_metrics: Dictionary = {}
var minimap_texture: Texture2D
var _built := false
var _textures: Dictionary = {}
var _map_visual: Node3D

func build() -> void:
	if _built:
		return
	_built = true
	_textures = JSON.parse_string(FileAccess.get_file_as_string(ROOT+"texture-map.json"))
	if not map_data.load_map(ROOT+"prt_fild08.gnd",ROOT+"prt_fild08.gat",_textures):
		push_error(map_data.last_error)
		return
	# Preserve the camp spawn at Y=0 while other cells keep their actual relief.
	height_origin = map_data.height_at(_to_gat(Vector3(0,0,3)))
	_map_visual = Node3D.new()
	_map_visual.name = "NativeProntera"
	_map_visual.scale.z = -1
	add_child(_map_visual)
	environment_metrics = map_data.build_ground(_map_visual,VISUAL_CROP,ORIGIN_GAT,height_origin)
	_build_models()
	_build_navigation()
	minimap_texture = _make_minimap()

func _build_models() -> void:
	var world: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(ROOT+"world.json"))
	var loaded := 0
	var unavailable: Array[String] = []
	for entry: Dictionary in world.models:
		var p: Array = entry.position
		var gat := Vector2(float(p[0])+map_data.ground_size.x,float(p[2])+map_data.ground_size.y)
		if not Rect2(VISUAL_CROP).grow(12).has_point(gat):
			continue
		var file: String = entry.file
		if file.is_empty():
			if entry.native_path not in unavailable:
				unavailable.append(entry.native_path)
			continue
		var path := file if file.begins_with("res://") else ROOT+file
		var r: Array = entry.rotation
		var s: Array = entry.scale
		var placed := ModelData.build_model(_map_visual,path,_textures,{
			"position":Vector3(gat.x-ORIGIN_GAT.x,-float(p[1])-height_origin,gat.y-ORIGIN_GAT.y),
			"rotation":Vector3(r[0],r[1],r[2]),"scale":Vector3(s[0],s[1],s[2])})
		if placed:
			loaded += 1
	environment_metrics["models"] = loaded
	environment_metrics["unavailable_models"] = unavailable

func _build_navigation() -> void:
	navigation = AStarGrid2D.new()
	navigation.region = MAP_RECT
	navigation.cell_size = Vector2.ONE
	navigation.diagonal_mode = AStarGrid2D.DIAGONAL_MODE_ONLY_IF_NO_OBSTACLES
	navigation.default_compute_heuristic = AStarGrid2D.HEURISTIC_OCTILE
	navigation.default_estimate_heuristic = AStarGrid2D.HEURISTIC_OCTILE
	navigation.update()
	for z in range(MAP_RECT.position.y,MAP_RECT.end.y):
		for x in range(MAP_RECT.position.x,MAP_RECT.end.x):
			var gat := Vector2i(_to_gat(Vector3(x,0,z)).floor())
			navigation.set_point_solid(Vector2i(x,z),not map_data.is_walkable(gat))

func _to_gat(point: Vector3) -> Vector2:
	return ORIGIN_GAT+Vector2(point.x,-point.z)

func is_walkable(cell: Vector2i) -> bool:
	return navigation!=null and MAP_RECT.has_point(cell) and not navigation.is_point_solid(cell)

func world_to_cell(point: Vector3) -> Vector2i:
	return Vector2i(roundi(point.x),roundi(point.z))

func height_at(point: Vector3) -> float:
	return map_data.height_at(_to_gat(point))-height_origin

func ground_position(point: Vector3) -> Vector3:
	return Vector3(point.x,height_at(point),point.z)

func cell_to_world(cell: Vector2i) -> Vector3:
	return ground_position(Vector3(cell.x,0,cell.y))

func nearest_ground(point: Vector3) -> Vector3:
	var cell := world_to_cell(point)
	for radius in range(12):
		for z in range(-radius,radius+1):
			for x in range(-radius,radius+1):
				if maxi(absi(x),absi(z))!=radius:
					continue
				var candidate := cell+Vector2i(x,z)
				if is_walkable(candidate):
					return cell_to_world(candidate)
	return cell_to_world(Vector2i.ZERO)

func pick_ground(ray_origin: Vector3,ray_direction: Vector3) -> Variant:
	# Bracket the first terrain crossing, then refine it. This follows the real
	# GAT elevation rather than projecting every click onto a flat Y=0 plane.
	var last_distance := 0.0
	var was_above := ray_origin.y>height_at(ray_origin)
	for step in range(1,121):
		var distance := float(step)*1.5
		var point := ray_origin+ray_direction*distance
		var above := point.y>height_at(point)
		if was_above and not above:
			var low := last_distance
			var high := distance
			for iteration in range(13):
				var mid := (low+high)*0.5
				var sample := ray_origin+ray_direction*mid
				if sample.y>height_at(sample):
					low = mid
				else:
					high = mid
			return ground_position(ray_origin+ray_direction*((low+high)*0.5))
		last_distance = distance
		was_above = above
	return null

func _make_minimap() -> Texture2D:
	var image := Image.create(196,196,false,Image.FORMAT_RGBA8)
	var images: Dictionary = {}
	for y in image.get_height():
		for x in image.get_width():
			var position := Vector3((float(x)+0.5)/4-24.5,0,(float(y)+0.5)/4-24.5)
			var gat := _to_gat(position)
			var gnd := Vector2i((gat/2).floor())
			var tile_index: int = map_data.ground_surfaces[(gnd.x+gnd.y*map_data.ground_size.x)*3]
			var color := Color("849e61")
			if tile_index>=0:
				var tile: Dictionary = map_data.tiles[tile_index]
				var name: String = map_data.texture_names[tile.texture]
				if not images.has(name):
					var texture: Texture2D = load(_textures[name]) if _textures.has(name) else null
					images[name] = texture.get_image() if texture else null
				var source: Image = images[name]
				if source:
					var fraction := gat/2-Vector2(gnd)
					var uv: Vector2 = tile.uv[0].lerp(tile.uv[1],fraction.x).lerp(tile.uv[2].lerp(tile.uv[3],fraction.x),fraction.y)
					color = source.get_pixel(posmod(int(uv.x*source.get_width()),source.get_width()),posmod(int(uv.y*source.get_height()),source.get_height()))
			if not is_walkable(world_to_cell(position)):
				color = color.darkened(0.42)
			image.set_pixel(x,y,color)
	return ImageTexture.create_from_image(image)
