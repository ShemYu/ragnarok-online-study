extends Node3D
## Native ACT/SPR animation in a 3D scene. World coordinates drive movement;
## the camera selects one of the source's eight drawn viewing directions.
const SpriteData = preload("res://scripts/ro_sprite_data.gd")
const CANVAS := Vector2i(192, 192)
const ORIGIN := Vector2i(96, 156)
# One navigation cell represents a GAT tile; native art is about 32 px per tile.
const PIXEL_SIZE := 0.03125
const CHARACTER_GROUPS := {"idle": 0, "walk": 1, "sit": 2, "pickup": 3, "ready": 4, "attack": 10, "hit": 6, "dead": 8, "cast": 12}
const MONSTER_GROUPS := {"idle": 0, "walk": 1, "attack": 2, "hit": 3, "dead": 4}
# Native reference headgear from the Character Lab equipment study (local assets).
const HEADGEAR_SOURCES := {"cap": "res://tools/character-lab/assets/native-equipment-v1/source/cap", "hat": "res://tools/character-lab/assets/native-equipment-v1/source/hat"}
static var _data_cache: Dictionary = {}
static var _appearance_cache: Dictionary = {}
static var _used_slot_cache: Dictionary = {}
static var _frame_cache: Dictionary = {}
static var _image_cache: Dictionary = {}
static var _feet_cache: Dictionary = {}
static var _bounds_cache: Dictionary = {}

var kind: String = "novice"
var state: String = "idle"
var direction: int = 0
var facing := Vector3(0, 0, 1)
var velocity := Vector3.ZERO
var _body: Dictionary
var _head: Dictionary = {}
var _weapon: Dictionary = {}
var _trail: Dictionary = {}
var _sprite: Sprite3D
var _shadow: MeshInstance3D
var _ring: MeshInstance3D
var _clock: float = 0.0
var _flash: float = 0.0
var _one_shot: float = 0.0
var _duration: float = 0.0
var _current_key: String = ""
var weapon_visible: bool = true
var _configured: bool = false
var _feet_offset: float = 0.0
var _rest_state: String = "idle"
# Appearance: replacement SPR drawings per part (inspection B5/B6). ACT records
# stay shared with the native data; only texture slots are substituted.
var appearance_id: String = ""
var appearance_path: String = ""
var appearance_label: String = ""
var headgear_id: String = ""
var coverage: Dictionary = {}
var _appearance: Dictionary = {}
var _native_parts: Dictionary = {}
var _headgear: Dictionary = {}
var _look_key: String = ""

func configure(actor_kind: String) -> void:
	# Job changes can replace the presentation on the same gameplay actor.
	for child in [_sprite, _shadow, _ring]:
		if is_instance_valid(child):
			remove_child(child)
			child.queue_free()
	_head = {}
	_weapon = {}
	_trail = {}
	state = "idle"
	_rest_state = "idle"
	_clock = 0.0
	_one_shot = 0.0
	_duration = 0.0
	_current_key = ""
	kind = "poring" if actor_kind == "slime" else actor_kind
	var base := "res://assets/reference-ro/"
	if kind in ["novice", "swordsman"]:
		var class_name_prefix := "swordsman" if kind == "swordsman" else "novice"
		_body = _load(base + class_name_prefix + "-male-body")
		_head = _load(base + "novice-male-head-1")
		_weapon = _load(base + class_name_prefix + "-male-dagger")
		_trail = _load(base + class_name_prefix + "-male-dagger-trail")
	elif kind == "guide":
		_body = _load(base + "swordsman-trainer")
	else:
		_body = _load(base + kind)
	if _body.is_empty():
		push_error("Missing RO actor data for " + kind)
		_configured = false
		return
	_sprite = Sprite3D.new()
	_sprite.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	_sprite.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
	_sprite.alpha_cut = SpriteBase3D.ALPHA_CUT_DISCARD
	_sprite.alpha_scissor_threshold = 0.35
	_sprite.shaded = false
	_sprite.pixel_size = PIXEL_SIZE
	# One neutral-pose foot registration is shared by every direction/action.
	# Do not recenter individual frames: the ACT data contains intentional motion.
	_feet_offset = _neutral_feet_offset()
	_native_parts = {"body": _body, "head": _head}
	_apply_look()
	_sprite.offset = Vector2(CANVAS.x / 2 - ORIGIN.x, ORIGIN.y + _feet_offset - CANVAS.y / 2)
	_sprite.position.y = 0.035
	_sprite.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(_sprite)
	_make_shadow()
	_make_ring()
	_configured = true
	_render_frame()

static func _load(base: String) -> Dictionary:
	if not _data_cache.has(base):
		if not FileAccess.file_exists(base + ".act"):
			return {}
		var data: Dictionary = SpriteData.load_pair(base)
		if data.is_empty():
			return {}
		data["source"] = base
		_data_cache[base] = data
	return _data_cache[base]

## Load a replacement-art manifest (tools/character-lab/appearances/*.json).
## Every replacement file must match the SHA-256 recorded by its art pack.
static func load_appearance(path: String) -> Dictionary:
	if _appearance_cache.has(path):
		return _appearance_cache[path]
	var manifest: Variant = JSON.parse_string(FileAccess.get_file_as_string(path)) if FileAccess.file_exists(path) else null
	if not manifest is Dictionary or not manifest.get("parts") is Dictionary:
		push_warning("Appearance manifest unavailable: " + path)
		return {}
	var result := {"id": str(manifest.get("id", path.get_file().get_basename())), "label": str(manifest.get("label", "")), "path": path, "parts": {}}
	for part: String in manifest.parts:
		# One pack, or several packs (e.g. attack front view + back view) merged by slot.
		var entries: Array = manifest.parts[part] if manifest.parts[part] is Array else [manifest.parts[part]]
		var textures := {}
		var source := ""
		for entry: Dictionary in entries:
			var pack_path: String = entry.manifest
			var pack: Variant = JSON.parse_string(FileAccess.get_file_as_string(pack_path)) if FileAccess.file_exists(pack_path) else null
			var field: String = entry.get("field", part)
			if not pack is Dictionary or not pack.get(field) is Dictionary:
				push_warning("Appearance part unavailable: %s (%s)" % [part, pack_path])
				return {}
			var pack_source := str(pack.get("nativeSource", ""))
			if pack_source.is_empty():
				var template: Variant = JSON.parse_string(FileAccess.get_file_as_string(pack.originalTemplate)) if FileAccess.file_exists(pack.get("originalTemplate", "")) else null
				if not template is Dictionary:
					push_warning("Appearance template unavailable for " + part)
					return {}
				pack_source = template.parts[part].source
			if not source.is_empty() and source != pack_source:
				push_error("Appearance %s mixes packs for different native sources" % part)
				return {}
			source = pack_source
			for index: String in pack[field]:
				var record: Dictionary = pack[field][index]
				var file: String = pack_path.get_base_dir() + "/" + record.file
				if FileAccess.get_sha256(file) != record.sha256:
					push_error("Appearance file changed since import: " + file)
					return {}
				# Raw PNG bytes, not an imported resource: the pack's hash covers these exact bytes.
				var image := Image.new()
				if image.load_png_from_buffer(FileAccess.get_file_as_bytes(file)) != OK:
					push_error("Appearance image unreadable: " + file)
					return {}
				textures[int(index)] = ImageTexture.create_from_image(image)
		result.parts[part] = {"source": source, "textures": textures}
	_appearance_cache[path] = result
	return result

## "" restores native art. Returns false when the manifest cannot be used.
func set_appearance(path: String) -> bool:
	var look: Dictionary = {} if path.is_empty() else load_appearance(path)
	if not path.is_empty() and look.is_empty():
		return false
	_appearance = look
	appearance_id = look.get("id", "")
	appearance_path = path
	appearance_label = look.get("label", appearance_id)
	if _configured:
		_apply_look()
		_render_frame()
	return true

## "", "cap" or "hat". Headgear is its own ACT/SPR part, attached like the head.
func set_headgear(id: String) -> bool:
	if not id.is_empty() and (not HEADGEAR_SOURCES.has(id) or not FileAccess.file_exists(HEADGEAR_SOURCES[id] + ".act")):
		return false
	headgear_id = id
	if _configured:
		_apply_look()
		_render_frame()
	return true

func _apply_look() -> void:
	coverage = {}
	for part: String in _native_parts:
		var native: Dictionary = _native_parts[part]
		var look := native
		var replacement: Dictionary = _appearance.get("parts", {}).get(part, {})
		# A body pack drawn for the Swordsman must not repaint the Novice body.
		if not native.is_empty() and not replacement.is_empty() and replacement.source == native.source:
			look = native.duplicate()
			var textures: Array[Texture2D] = native.textures.duplicate()
			var replaced := 0
			for index: int in replacement.textures:
				var texture: Texture2D = replacement.textures[index]
				if index < textures.size() and texture.get_size() == textures[index].get_size():
					textures[index] = texture
					replaced += 1
				else:
					push_error("Appearance %s %s slot %d does not fit the native SPR image" % [appearance_id, part, index])
			look.textures = textures
			# Distinct identity keeps the shared image cache from mixing looks.
			look.source = "%s@%s" % [native.source, appearance_id]
			coverage[part] = {"replaced": replaced, "used": _used_slots(native)}
		if part == "body":
			_body = look
		else:
			_head = look
	_headgear = {}
	if not headgear_id.is_empty() and kind in ["novice", "swordsman"]:
		_headgear = _load(HEADGEAR_SOURCES[headgear_id])
	_look_key = "%s|%s|%s" % [_body.get("source", ""), _head.get("source", ""), _headgear.get("source", "")]
	_current_key = ""

static func _used_slots(data: Dictionary) -> int:
	if not _used_slot_cache.has(data.source):
		var used := {}
		for action: Dictionary in data.actions:
			for frame: Dictionary in action.frames:
				for layer: Dictionary in frame.layers:
					if layer.index >= 0:
						used[layer.index] = true
		_used_slot_cache[data.source] = used.size()
	return _used_slot_cache[data.source]

func set_motion(value: Vector3) -> void:
	velocity = value
	if value.length_squared() > 0.001:
		facing = Vector3(value.x, 0, value.z).normalized()
	if _one_shot <= 0.0 and state not in ["sit", "dead"]:
		set_state("walk" if value.length_squared() > 0.03 else _rest_state)

func set_state(value: String) -> void:
	if value in ["idle", "ready"]:
		_rest_state = value
	if state != value:
		state = value
		_clock = 0.0
		_duration = 0.0
		_one_shot = 0.0

func play_action(value: String, duration: float = 0.0) -> void:
	set_state(value)
	_clock = 0.0
	_duration = duration
	_one_shot = duration if duration > 0 else action_length(value)

func action_length(value: String = "attack") -> float:
	if _body.is_empty():
		return 0.4
	var action: Dictionary = _get_action(_body, value, direction)
	return action.frames.size() * action.delay

func set_attacking(active: bool) -> void:
	if active and state != "attack":
		play_action("attack", 0.5)
	elif not active and state == "attack" and _one_shot <= 0:
		set_state("idle")

func flash_hit() -> void:
	_flash = 0.14
	if state not in ["attack", "dead", "cast"]:
		play_action("hit", 0.20)

func set_selected(active: bool) -> void:
	if _ring:
		_ring.visible = active

func screen_rect(camera: Camera3D) -> Rect2:
	if not _configured or not _sprite.texture:
		return Rect2()
	# Hit the visible native artwork at every zoom, including the trainer's head.
	# Cached alpha bounds exclude the large transparent composition margins.
	if not _bounds_cache.has(_current_key):
		_bounds_cache[_current_key] = _sprite.texture.get_image().get_used_rect()
	var bounds: Rect2i = _bounds_cache[_current_key]
	var center := _sprite.global_position
	var right := camera.global_basis.x * PIXEL_SIZE
	var up := camera.global_basis.y * PIXEL_SIZE
	var corner_a := Vector2(bounds.position) - Vector2(CANVAS) * 0.5
	var corner_b := Vector2(bounds.end) - Vector2(CANVAS) * 0.5
	var a := camera.unproject_position(center + right * (corner_a.x + _sprite.offset.x) + up * (-corner_a.y + _sprite.offset.y))
	var b := camera.unproject_position(center + right * (corner_b.x + _sprite.offset.x) + up * (-corner_b.y + _sprite.offset.y))
	return Rect2(a.min(b), (a-b).abs())

func _process(delta: float) -> void:
	if not _configured:
		return
	_clock += delta
	_flash = maxf(0.0, _flash - delta)
	if _one_shot > 0:
		_one_shot -= delta
		if _one_shot <= 0 and state != "dead":
			set_state("walk" if velocity.length_squared() > 0.03 else _rest_state)
	var camera := get_viewport().get_camera_3d()
	if camera:
		var toward := camera.global_basis.z
		toward.y = 0
		var right := camera.global_basis.x
		right.y = 0
		# Source order: S, SW, W, NW, N, NE, E, SE.
		var angle := atan2(-facing.dot(right.normalized()), facing.dot(toward.normalized()))
		direction = posmod(roundi(angle / (PI / 4.0)), 8)
	_sprite.modulate = Color(1.8, 0.7, 0.65, 1) if _flash > 0 else Color.WHITE
	_render_frame()

func _get_action(data: Dictionary, requested_state: String, view: int) -> Dictionary:
	var groups: Dictionary = CHARACTER_GROUPS if kind in ["novice", "swordsman"] else MONSTER_GROUPS
	var group: int = groups.get(requested_state, 0)
	if kind == "guide":
		group = 0
	elif requested_state == "attack" and kind in ["novice", "swordsman"] and not weapon_visible:
		group = 5
	var index: int = group * 8 + view
	if index >= data.actions.size() or data.actions[index].frames.is_empty():
		index = mini(view, data.actions.size() - 1)
	return data.actions[index]

func _render_frame() -> void:
	if _body.is_empty():
		return
	var action: Dictionary = _get_action(_body, state, direction)
	var count: int = action.frames.size()
	if count == 0:
		return
	var step: float = maxf(0.024, action.delay)
	if _duration > 0 and (_one_shot > 0 or state == "dead"):
		step = _duration / count
	if state == "walk":
		step /= clampf(velocity.length() / 3.1, 0.65, 1.6)
	var frame_index: int = int(_clock / step)
	frame_index = mini(frame_index, count - 1) if state in ["dead", "hit", "pickup", "attack", "cast"] else frame_index % count
	if state in ["idle", "sit"] and kind in ["novice", "swordsman"]:
		# These three source poses encode head direction, not an idle cycle.
		frame_index = 0
	var key := "%s:%s:%s:%d:%d:%s" % [kind, _look_key, state, direction, frame_index, weapon_visible]
	if key == _current_key:
		return
	_current_key = key
	if not _frame_cache.has(key):
		var image := Image.create(CANVAS.x, CANVAS.y, false, Image.FORMAT_RGBA8)
		var body_frame: Dictionary = action.frames[frame_index]
		_draw_part(image, _body, body_frame, Vector2.ZERO)
		if not _head.is_empty():
			var head_action: Dictionary = _get_action(_head, state, direction)
			var head_frame: Dictionary = head_action.frames[frame_index % head_action.frames.size()]
			_draw_part(image, _head, head_frame, _attachment(body_frame, head_frame))
		if not _headgear.is_empty():
			# Same anchor rule as the head; drawn above it for the studied facing.
			var gear_action: Dictionary = _get_action(_headgear, state, direction)
			var gear_frame: Dictionary = gear_action.frames[frame_index % gear_action.frames.size()]
			_draw_part(image, _headgear, gear_frame, _attachment(body_frame, gear_frame))
		if weapon_visible and not _weapon.is_empty():
			var weapon_action: Dictionary = _get_action(_weapon, state, direction)
			var weapon_frame: Dictionary = weapon_action.frames[frame_index % weapon_action.frames.size()]
			_draw_part(image, _weapon, weapon_frame, Vector2.ZERO)
		if weapon_visible and not _trail.is_empty() and state == "attack":
			var trail_action: Dictionary = _get_action(_trail, state, direction)
			var trail_frame: Dictionary = trail_action.frames[frame_index % trail_action.frames.size()]
			_draw_part(image, _trail, trail_frame, Vector2.ZERO)
		_frame_cache[key] = ImageTexture.create_from_image(image)
	_sprite.texture = _frame_cache[key]

func _neutral_feet_offset() -> float:
	if _feet_cache.has(kind):
		return _feet_cache[kind]
	var image := Image.create(CANVAS.x, CANVAS.y, false, Image.FORMAT_RGBA8)
	var neutral: Dictionary = _get_action(_body, "idle", 0).frames[0]
	_draw_part(image, _body, neutral, Vector2.ZERO)
	var bottom := image.get_used_rect().end.y
	var correction := float(bottom - ORIGIN.y)
	_feet_cache[kind] = correction
	return correction

func _attachment(parent: Dictionary, child: Dictionary) -> Vector2:
	if parent.anchors.is_empty() or child.anchors.is_empty():
		return Vector2.ZERO
	return parent.anchors[0] - child.anchors[0]

func _draw_part(canvas: Image, data: Dictionary, frame: Dictionary, attachment: Vector2) -> void:
	for layer: Dictionary in frame.layers:
		var index: int = layer.index
		if index < 0 or index >= data.textures.size():
			continue
		var image_key: String = data.source + ":" + str(index)
		if not _image_cache.has(image_key):
			_image_cache[image_key] = data.textures[index].get_image()
		var source: Image = _image_cache[image_key]
		var dimensions := Vector2(source.get_size())
		var center := Vector2(ORIGIN) + Vector2(layer.x, layer.y) + attachment
		var scaling: Vector2 = layer.scale
		if absf(scaling.x) < 0.001 or absf(scaling.y) < 0.001:
			continue
		var rotation_angle: float = layer.rotation
		var mirrored: bool = layer.mirror
		# The common untransformed layer can use Godot's native image blitter.
		if not mirrored and is_zero_approx(rotation_angle) and scaling == Vector2.ONE and layer.color == Color.WHITE:
			var top_left := Vector2i((center - dimensions * 0.5).floor())
			canvas.blend_rect(source, Rect2i(Vector2i.ZERO, source.get_size()), top_left)
			continue
		var radius := (dimensions * scaling.abs()).length() * 0.5 + 2
		var from_x := maxi(0, floori(center.x - radius))
		var to_x := mini(CANVAS.x, ceili(center.x + radius))
		var from_y := maxi(0, floori(center.y - radius))
		var to_y := mini(CANVAS.y, ceili(center.y + radius))
		for y in range(from_y, to_y):
			for x in range(from_x, to_x):
				var local := (Vector2(x + 0.5, y + 0.5) - center).rotated(-rotation_angle) / scaling
				if mirrored:
					local.x = -local.x
				local += dimensions * 0.5
				var sx := floori(local.x)
				var sy := floori(local.y)
				if sx < 0 or sy < 0 or sx >= source.get_width() or sy >= source.get_height():
					continue
				var color: Color = source.get_pixel(sx, sy) * layer.color
				if color.a > 0:
					canvas.set_pixel(x, y, canvas.get_pixel(x, y).blend(color))

func _make_shadow() -> void:
	var shadow := MeshInstance3D.new()
	_shadow = shadow
	var mesh := PlaneMesh.new()
	mesh.size = Vector2(0.90, 0.53) if kind in ["novice", "guide", "swordsman"] else Vector2(1.0, 0.58)
	shadow.mesh = mesh
	shadow.position.y = 0.022
	var texture_image := Image.create(32, 32, false, Image.FORMAT_RGBA8)
	for y in 32:
		for x in 32:
			var distance := Vector2((x - 15.5) / 15.5, (y - 15.5) / 15.5).length()
			texture_image.set_pixel(x, y, Color(0.12, 0.14, 0.13, pow(maxf(0, 1 - distance), 1.1) * 0.45))
	var material := StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.albedo_texture = ImageTexture.create_from_image(texture_image)
	shadow.material_override = material
	shadow.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(shadow)

func _make_ring() -> void:
	_ring = MeshInstance3D.new()
	var mesh := TorusMesh.new()
	mesh.inner_radius = 0.64
	mesh.outer_radius = 0.685
	mesh.rings = 32
	mesh.ring_segments = 6
	_ring.mesh = mesh
	_ring.position.y = 0.032
	_ring.scale.y = 0.1
	var material := StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.albedo_color = Color("ffe786")
	_ring.material_override = material
	_ring.visible = false
	add_child(_ring)
