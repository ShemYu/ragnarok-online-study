extends Node3D
## Original hand-drawn pixel sprites rendered on a camera-facing plane.
## This node owns appearance only; the parent owns movement and combat.

const OUTLINE := Color("29313f")
const HAIR_DARK := Color("49312c")
const HAIR_MID := Color("815039")
const HAIR_LIGHT := Color("ba8050")
const SKIN_DARK := Color("b57756")
const SKIN := Color("edba83")
const SKIN_LIGHT := Color("ffe0a5")
const CLOTH_DARK := Color("9d8967")
const CLOTH := Color("e4d9b1")
const CLOTH_LIGHT := Color("fff1c8")
const VEST_DARK := Color("2b4b62")
const VEST := Color("48718a")
const VEST_LIGHT := Color("739ca8")
const LEATHER := Color("78513c")
const LEATHER_LIGHT := Color("b6814e")
const STEEL := Color("bdd9dc")
const STEEL_LIGHT := Color("efffff")

var _kind: String = "novice"
var _sprite: Sprite3D
var _selection: MeshInstance3D
var _shadow: MeshInstance3D
var _slash: MeshInstance3D
var _textures: Dictionary = {}
var _velocity := Vector3.ZERO
var _aim_direction := Vector3(0.0, 0.0, 1.0)
var _facing: String = "front"
var _flip: bool = false
var _attacking: bool = false
var _attack_clock: float = 0.0
var _clock: float = 0.0
var _walk_clock: float = 0.0
var _hit_clock: float = 0.0
var _selected: bool = false
var _configured: bool = false
var _base_height: float = 0.0


func configure(kind: String) -> void:
	_kind = kind
	if _configured:
		for child in get_children():
			child.queue_free()
	_textures.clear()
	_sprite = Sprite3D.new()
	_sprite.name = "PixelSprite"
	_sprite.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	_sprite.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
	_sprite.alpha_cut = SpriteBase3D.ALPHA_CUT_DISCARD
	_sprite.alpha_scissor_threshold = 0.45
	_sprite.shaded = false
	_sprite.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_sprite.pixel_size = 0.03125 if _kind == "novice" else 0.028
	# Offset in the billboard plane, so the feet remain at the node origin even
	# with a camera looking down. Raising the entire Sprite3D would make it float.
	_sprite.offset = Vector2(0.0, 30.0 if _kind == "novice" else 16.0)
	_base_height = 0.025
	_sprite.position.y = _base_height
	add_child(_sprite)
	_create_shadow()
	_create_selection()
	_create_slash()
	_configured = true
	_update_sprite()


func set_motion(velocity: Vector3) -> void:
	_velocity = velocity
	if velocity.length_squared() > 0.001:
		_aim_direction = Vector3(velocity.x, 0.0, velocity.z).normalized()
	_update_facing()


func _update_facing() -> void:
	var view_x: float = _aim_direction.x
	var view_z: float = _aim_direction.z
	var camera: Camera3D = get_viewport().get_camera_3d()
	if is_instance_valid(camera):
		var right: Vector3 = camera.global_basis.x
		var toward_camera: Vector3 = camera.global_basis.z
		right.y = 0.0
		toward_camera.y = 0.0
		view_x = _aim_direction.dot(right.normalized())
		view_z = _aim_direction.dot(toward_camera.normalized())
	_flip = view_x < -0.03
	if absf(view_x) > absf(view_z) * 1.4:
		_facing = "side"
	elif view_z < 0.0:
		_facing = "back"
	else:
		_facing = "front"


func set_attacking(active: bool) -> void:
	if active and not _attacking:
		_attack_clock = 0.0
	_attacking = active


func flash_hit() -> void:
	_hit_clock = 0.18


func set_selected(active: bool) -> void:
	_selected = active
	if is_instance_valid(_selection):
		_selection.visible = active


func _process(delta: float) -> void:
	if not _configured:
		return
	_clock += delta
	if _velocity.length_squared() > 0.01:
		_walk_clock += delta * clampf(_velocity.length() / 2.5, 0.65, 1.6)
	else:
		_walk_clock = 0.0
	if _attacking:
		_attack_clock += delta
	_hit_clock = maxf(0.0, _hit_clock - delta)
	# Values above one brighten the actual sprite colors without changing alpha.
	_sprite.modulate = Color(2.6, 1.65, 1.65) if _hit_clock > 0.0 else Color.WHITE
	# Retain the world-space facing while idle, and choose the correct sprite
	# relative to the current orbit camera on every frame.
	_update_facing()
	_update_sprite()
	if _selected:
		var pulse: float = 1.0 + sin(_clock * 4.5) * 0.055
		_selection.scale = Vector3(pulse, 0.1, pulse)
	var strike_time: float = fmod(_attack_clock, 0.72)
	_slash.visible = _kind == "novice" and _attacking and strike_time > 0.08 and strike_time < 0.21
	if _slash.visible:
		var sweep: float = remap(strike_time, 0.08, 0.21, -0.35, 0.35)
		_slash.rotation.y = atan2(-_aim_direction.z, _aim_direction.x) + sweep


func _update_sprite() -> void:
	var walking: bool = _velocity.length_squared() > 0.01
	var frame: int = int(_walk_clock * 9.0) % 4 if walking else 0
	var attack_frame: int = -1
	if _attacking:
		# All three poses fit the gameplay controller's 0.26-second attack window.
		attack_frame = mini(2, int(fmod(_attack_clock, 0.72) / 0.09))
	var breathe: int = 1 if sin(_clock * 2.5) > 0.6 else 0
	var key: String = "%s_%s_%d_%d_%d_%d" % [_kind, _facing, frame, attack_frame, breathe, int(walking)]
	if not _textures.has(key):
		var art: Image
		if _kind == "novice":
			art = _draw_novice(_facing, frame, attack_frame, breathe if not walking else 0)
		else:
			art = _draw_slime(frame, attack_frame, breathe, walking)
		_textures[key] = ImageTexture.create_from_image(art)
	_sprite.texture = _textures[key]
	_sprite.flip_h = _flip and _facing != "back"
	# The image foot row stays in exactly the same place during every animation.
	_sprite.position.y = _base_height


func _create_shadow() -> void:
	_shadow = MeshInstance3D.new()
	_shadow.name = "GroundShadow"
	var mesh := PlaneMesh.new()
	mesh.size = Vector2(1.2, 0.72) if _kind == "novice" else Vector2(1.25, 0.8)
	_shadow.mesh = mesh
	_shadow.position.y = 0.018
	var img := Image.create(64, 64, false, Image.FORMAT_RGBA8)
	for y in range(64):
		for x in range(64):
			var d: float = Vector2((float(x) - 31.5) / 31.0, (float(y) - 31.5) / 31.0).length()
			var opacity: float = pow(maxf(0.0, 1.0 - d), 1.3) * 0.38
			img.set_pixel(x, y, Color(0.09, 0.13, 0.15, opacity))
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.albedo_texture = ImageTexture.create_from_image(img)
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	_shadow.material_override = mat
	_shadow.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(_shadow)


func _create_selection() -> void:
	_selection = MeshInstance3D.new()
	_selection.name = "TargetRing"
	var ring := TorusMesh.new()
	ring.inner_radius = 0.49 if _kind == "novice" else 0.54
	ring.outer_radius = 0.52 if _kind == "novice" else 0.58
	ring.rings = 40
	ring.ring_segments = 6
	_selection.mesh = ring
	_selection.position.y = 0.038
	_selection.scale.y = 0.1
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.albedo_color = Color("ffd78c") if _kind == "novice" else Color("ffb78e")
	_selection.material_override = mat
	_selection.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_selection.visible = _selected
	add_child(_selection)


func _create_slash() -> void:
	_slash = MeshInstance3D.new()
	_slash.name = "SwordArc"
	var arc := ImmediateMesh.new()
	arc.surface_begin(Mesh.PRIMITIVE_TRIANGLES)
	for i in range(14):
		var angle_a: float = lerpf(-1.05, 1.05, float(i) / 14.0)
		var angle_b: float = lerpf(-1.05, 1.05, float(i + 1) / 14.0)
		var a := Vector3(cos(angle_a) * 0.8, 0.0, sin(angle_a) * 0.8)
		var b := Vector3(cos(angle_b) * 0.8, 0.0, sin(angle_b) * 0.8)
		var c := a * 1.18
		var d := b * 1.18
		for point in [a, b, c, b, d, c]:
			arc.surface_add_vertex(point)
	arc.surface_end()
	_slash.mesh = arc
	_slash.position.y = 0.75
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.albedo_color = Color(1.0, 0.95, 0.72, 0.72)
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	_slash.material_override = mat
	_slash.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_slash.visible = false
	add_child(_slash)


func _draw_novice(facing: String, frame: int, attack: int, breathe: int) -> Image:
	var img := Image.create(64, 72, false, Image.FORMAT_RGBA8)
	var bob: int = -1 if frame == 1 or frame == 3 else 0
	var sy: int = 6 + bob
	var cx: int = 32
	var back: bool = facing == "back"
	var side: bool = facing == "side"
	var left_step: int = 0
	var right_step: int = 0
	if frame == 1:
		left_step = -2
		right_step = 2
	elif frame == 3:
		left_step = 2
		right_step = -2
	# Small, offset boots and trousers; the planted foot never leaves the baseline.
	_rect(img, cx - 8 + left_step, 48 + sy, 7, 9 - bob, OUTLINE)
	_rect(img, cx + 2 + right_step, 48 + sy, 7, 9 - bob, OUTLINE)
	_rect(img, cx - 7 + left_step, 48 + sy, 5, 6, Color("777e81"))
	_rect(img, cx + 3 + right_step, 48 + sy, 5, 6, Color("777e81"))
	_rect(img, cx - 8 + left_step, 54 + sy, 8, 7 - bob, OUTLINE)
	_rect(img, cx + 2 + right_step, 54 + sy, 9, 7 - bob, OUTLINE)
	_rect(img, cx - 7 + left_step, 54 + sy, 6, 5 - bob, LEATHER)
	_rect(img, cx + 3 + right_step, 54 + sy, 7, 5 - bob, LEATHER)
	_rect(img, cx - 7 + left_step, 55 + sy, 5, 1, LEATHER_LIGHT)
	_rect(img, cx + 3 + right_step, 55 + sy, 5, 1, LEATHER_LIGHT)
	_rect(img, cx - 8 + left_step, 60 + sy - bob, 8, 1, Color("1c2a34"))
	_rect(img, cx + 2 + right_step, 60 + sy - bob, 9, 1, Color("1c2a34"))
	# The left arm rests at the hip; its sleeve swings a pixel against the stride.
	var arm_y: int = 34 + sy + (1 if frame == 1 else 0)
	_ellipse(img, cx - 12, arm_y + 5, 5, 8, OUTLINE)
	_ellipse(img, cx - 12, arm_y + 4, 4, 6, CLOTH)
	_rect(img, cx - 15, arm_y + 2, 3, 4, CLOTH_LIGHT)
	_ellipse(img, cx - 12, arm_y + 11, 3, 4, SKIN_DARK)
	_rect(img, cx - 13, arm_y + 8, 3, 4, SKIN)
	# Cream tunic, a blue open vest, folded collar, and a belt with a brass buckle.
	_poly(img, [Vector2i(cx - 8, 29 + sy), Vector2i(cx + 8, 29 + sy), Vector2i(cx + 12, 36 + sy), Vector2i(cx + 11, 49 + sy), Vector2i(cx + 8, 52 + sy), Vector2i(cx - 9, 52 + sy), Vector2i(cx - 11, 49 + sy), Vector2i(cx - 11, 36 + sy)], OUTLINE)
	_rect(img, cx - 9, 35 + sy, 18, 15, CLOTH_DARK)
	_rect(img, cx - 7, 33 + sy, 14, 17, CLOTH)
	_rect(img, cx - 4, 34 + sy, 8, 15, CLOTH_LIGHT)
	_rect(img, cx - 8, 48 + sy, 5, 3, CLOTH)
	_rect(img, cx + 3, 48 + sy, 5, 3, CLOTH)
	_poly(img, [Vector2i(cx - 8, 30 + sy), Vector2i(cx - 2, 32 + sy), Vector2i(cx - 4, 44 + sy), Vector2i(cx - 9, 43 + sy), Vector2i(cx - 10, 35 + sy)], VEST_DARK)
	_poly(img, [Vector2i(cx + 8, 30 + sy), Vector2i(cx + 2, 32 + sy), Vector2i(cx + 4, 44 + sy), Vector2i(cx + 9, 43 + sy), Vector2i(cx + 10, 35 + sy)], VEST_DARK)
	_rect(img, cx - 8, 34 + sy, 3, 8, VEST)
	_rect(img, cx + 5, 34 + sy, 3, 8, VEST)
	_rect(img, cx - 8, 33 + sy, 2, 5, VEST_LIGHT)
	_rect(img, cx + 5, 33 + sy, 2, 3, VEST_LIGHT)
	_rect(img, cx - 9, 45 + sy, 18, 3, LEATHER)
	_rect(img, cx - 1, 45 + sy, 4, 3, Color("d5ab57"))
	_rect(img, cx, 46 + sy, 2, 1, LEATHER)
	if back:
		_rect(img, cx - 5, 33 + sy, 10, 10, VEST)
		_rect(img, cx - 2, 33 + sy, 3, 9, VEST_LIGHT)
		_line(img, Vector2i(cx - 8, 32 + sy), Vector2i(cx + 6, 44 + sy), LEATHER_LIGHT, 2)
	else:
		_poly(img, [Vector2i(cx - 6, 30 + sy), Vector2i(cx, 33 + sy), Vector2i(cx - 4, 37 + sy)], CLOTH_LIGHT)
		_poly(img, [Vector2i(cx + 6, 30 + sy), Vector2i(cx, 33 + sy), Vector2i(cx + 4, 37 + sy)], CLOTH_LIGHT)
		_rect(img, cx, 34 + sy, 1, 6, CLOTH_DARK)
		_rect(img, cx + 1, 39 + sy, 1, 1, LEATHER)
	# Sword hand has three readable attack poses: lift, extend, recover.
	var hand := Vector2i(cx + 13, 45 + sy)
	if attack == 0:
		hand = Vector2i(cx + 15, 30 + sy)
	elif attack == 1:
		if side:
			hand = Vector2i(cx + 17, 38 + sy)
		elif back:
			hand = Vector2i(cx + 13, 31 + sy)
		else:
			hand = Vector2i(cx + 11, 44 + sy)
	elif attack == 2:
		hand = Vector2i(cx + 16, 46 + sy)
	_line(img, Vector2i(cx + 9, 35 + sy), hand, OUTLINE, 7)
	_line(img, Vector2i(cx + 10, 35 + sy), hand - Vector2i(1, 2), CLOTH, 5)
	_ellipse(img, hand.x, hand.y, 3, 3, SKIN_DARK)
	_ellipse(img, hand.x - 1, hand.y - 1, 2, 2, SKIN)
	if attack == 0:
		_sword(img, hand, Vector2i(hand.x - 5, hand.y - 24))
	elif attack == 1:
		if side:
			_sword(img, hand, Vector2i(61, hand.y - 2))
		elif back:
			_sword(img, hand, Vector2i(cx + 20, 12 + sy))
		else:
			_sword(img, hand, Vector2i(cx + 15, 65))
	elif attack == 2:
		_sword(img, hand, Vector2i(60, hand.y + 11))
	else:
		_sword(img, hand, Vector2i(hand.x + 5, hand.y - 21))
	# Head silhouette is deliberately larger than the torso: an original chibi novice.
	var hy: int = sy + breathe
	_ellipse(img, cx, 20 + hy, 13, 13, OUTLINE)
	_ellipse(img, cx, 20 + hy, 12, 12, HAIR_DARK)
	_ellipse(img, cx - 11, 23 + hy, 3, 4, SKIN_DARK)
	_ellipse(img, cx + 11, 23 + hy, 3, 4, SKIN_DARK)
	_ellipse(img, cx, 23 + hy, 10, 9, SKIN_DARK)
	_ellipse(img, cx, 21 + hy, 10, 9, SKIN)
	_ellipse(img, cx - 1, 19 + hy, 8, 7, SKIN_LIGHT)
	# Irregular locks rather than a rectangular hair cap.
	var locks: Array = [Vector2i(-13, 19), Vector2i(-14, 12), Vector2i(-10, 12), Vector2i(-12, 7), Vector2i(-6, 9), Vector2i(-4, 3), Vector2i(0, 7), Vector2i(5, 4), Vector2i(7, 9), Vector2i(12, 8), Vector2i(12, 13), Vector2i(15, 15), Vector2i(12, 24), Vector2i(9, 27), Vector2i(8, 17), Vector2i(4, 19), Vector2i(3, 15), Vector2i(-2, 19), Vector2i(-2, 15), Vector2i(-7, 21), Vector2i(-8, 16), Vector2i(-11, 23)]
	var hair_points: Array = []
	for p: Vector2i in locks:
		hair_points.append(p + Vector2i(cx, hy))
	_poly(img, hair_points, HAIR_DARK)
	_poly(img, [Vector2i(cx - 10, 12 + hy), Vector2i(cx - 5, 11 + hy), Vector2i(cx - 4, 6 + hy), Vector2i(cx + 1, 11 + hy), Vector2i(cx + 5, 7 + hy), Vector2i(cx + 8, 12 + hy), Vector2i(cx + 11, 11 + hy), Vector2i(cx + 10, 17 + hy), Vector2i(cx + 7, 15 + hy), Vector2i(cx + 2, 15 + hy), Vector2i(cx - 2, 13 + hy), Vector2i(cx - 7, 17 + hy)], HAIR_MID)
	_line(img, Vector2i(cx - 6, 11 + hy), Vector2i(cx - 3, 9 + hy), HAIR_LIGHT, 2)
	_line(img, Vector2i(cx - 2, 11 + hy), Vector2i(cx + 2, 12 + hy), HAIR_LIGHT, 2)
	_rect(img, cx + 5, 12 + hy, 3, 2, HAIR_LIGHT)
	if back:
		_ellipse(img, cx, 22 + hy, 10, 9, HAIR_DARK)
		_ellipse(img, cx - 1, 21 + hy, 9, 7, HAIR_MID)
		_line(img, Vector2i(cx - 6, 20 + hy), Vector2i(cx - 3, 26 + hy), HAIR_LIGHT, 2)
		_poly(img, [Vector2i(cx - 8, 24 + hy), Vector2i(cx - 6, 31 + hy), Vector2i(cx - 3, 28 + hy), Vector2i(cx, 32 + hy), Vector2i(cx + 3, 28 + hy), Vector2i(cx + 6, 30 + hy), Vector2i(cx + 9, 23 + hy)], HAIR_DARK)
	elif side:
		_rect(img, cx + 3, 22 + hy, 3, 4, OUTLINE)
		_rect(img, cx + 4, 22 + hy, 1, 1, Color.WHITE)
		_rect(img, cx + 8, 25 + hy, 3, 2, SKIN)
		_rect(img, cx + 3, 29 + hy, 3, 1, SKIN_DARK)
		_ellipse(img, cx - 6, 24 + hy, 3, 4, SKIN_DARK)
		_rect(img, cx - 6, 22 + hy, 2, 3, SKIN)
		_rect(img, cx - 9, 17 + hy, 4, 6, HAIR_DARK)
	else:
		_rect(img, cx - 6, 22 + hy, 3, 4, OUTLINE)
		_rect(img, cx + 4, 22 + hy, 3, 4, OUTLINE)
		_rect(img, cx - 5, 22 + hy, 1, 1, Color.WHITE)
		_rect(img, cx + 5, 22 + hy, 1, 1, Color.WHITE)
		_rect(img, cx - 8, 26 + hy, 3, 1, Color("e69978"))
		_rect(img, cx + 6, 26 + hy, 3, 1, Color("e69978"))
		_rect(img, cx, 27 + hy, 1, 1, SKIN_DARK)
		_rect(img, cx - 1, 29 + hy, 3, 1, Color("a76d58"))
	return img


func _sword(img: Image, hand: Vector2i, tip: Vector2i) -> void:
	var direction: Vector2 = (Vector2(tip) - Vector2(hand)).normalized()
	var guard: Vector2i = hand + Vector2i(direction * 5.0)
	_line(img, hand, tip, OUTLINE, 5)
	_line(img, guard, tip, STEEL, 3)
	_line(img, guard + Vector2i(-1, -1), tip, STEEL_LIGHT, 1)
	var across := Vector2i(-direction.y * 4.0, direction.x * 4.0)
	_line(img, guard - across, guard + across, OUTLINE, 3)
	_line(img, guard - across, guard + across, Color("d1ac63"), 1)
	_line(img, hand, guard - Vector2i(direction * 2.0), LEATHER, 2)


func _draw_slime(frame: int, attack: int, breathe: int, walking: bool) -> Image:
	var img := Image.create(64, 48, false, Image.FORMAT_RGBA8)
	var squash: int = breathe
	if walking:
		squash = 2 if frame % 2 == 0 else -2
	if attack >= 0:
		squash = -3 if attack == 1 else 2
	var ry: int = 14 - squash
	var rx: int = 21 + squash
	var cy: int = 40 - ry
	_ellipse(img, 32, cy, rx, ry, Color("975274"))
	_ellipse(img, 32, cy - 1, rx - 1, ry - 1, Color("d77896"))
	_ellipse(img, 31, cy - 3, rx - 3, ry - 3, Color("ef9da7"))
	_ellipse(img, 30, cy - 5, rx - 6, ry - 5, Color("ffbfbb"))
	# An uneven liquid base, broad translucent-looking highlights, and tiny cheeks.
	_rect(img, 18 - squash, 36, 29 + squash * 2, 3, Color("d77896"))
	_rect(img, 22 - squash, 38, 22 + squash * 2, 2, Color("b96488"))
	_ellipse(img, 23, cy - 6, 6, 3, Color("ffddd0"))
	_rect(img, 21, cy - 8, 5, 2, Color("fff0db"))
	_rect(img, 42, cy - 3, 3, 2, Color("ffd9c6"))
	var face_y: int = cy + 3
	if _facing == "back":
		_ellipse(img, 35, cy - 1, 6, 3, Color("f7afb1"))
	else:
		var face_x: int = 5 if _facing == "side" else 0
		_rect(img, 25 + face_x, face_y, 3, 4, Color("673a58"))
		_rect(img, 37 + face_x, face_y, 3, 4, Color("673a58"))
		_rect(img, 25 + face_x, face_y, 1, 1, Color("fff4df"))
		_rect(img, 37 + face_x, face_y, 1, 1, Color("fff4df"))
		_rect(img, 21 + face_x, face_y + 5, 4, 2, Color("e98198"))
		_rect(img, 40 + face_x, face_y + 5, 4, 2, Color("e98198"))
		if attack == 1:
			_ellipse(img, 32 + face_x, face_y + 6, 2, 3, Color("8e4568"))
		else:
			_rect(img, 30 + face_x, face_y + 5, 1, 1, Color("934662"))
			_rect(img, 31 + face_x, face_y + 6, 3, 1, Color("934662"))
			_rect(img, 34 + face_x, face_y + 5, 1, 1, Color("934662"))
	return img


func _rect(img: Image, x: int, y: int, w: int, h: int, color: Color) -> void:
	for py in range(maxi(0, y), mini(img.get_height(), y + h)):
		for px in range(maxi(0, x), mini(img.get_width(), x + w)):
			img.set_pixel(px, py, color)


func _ellipse(img: Image, cx: int, cy: int, rx: int, ry: int, color: Color) -> void:
	if rx <= 0 or ry <= 0:
		return
	for y in range(maxi(0, cy - ry), mini(img.get_height(), cy + ry + 1)):
		for x in range(maxi(0, cx - rx), mini(img.get_width(), cx + rx + 1)):
			var dx: float = float(x - cx) / float(rx)
			var dy: float = float(y - cy) / float(ry)
			if dx * dx + dy * dy <= 1.0:
				img.set_pixel(x, y, color)


func _line(img: Image, start: Vector2i, finish: Vector2i, color: Color, width: int = 1) -> void:
	var steps: int = maxi(absi(finish.x - start.x), absi(finish.y - start.y))
	if steps == 0:
		_rect(img, start.x - width / 2, start.y - width / 2, width, width, color)
		return
	for i in range(steps + 1):
		var t: float = float(i) / float(steps)
		var p := Vector2i(Vector2(start).lerp(Vector2(finish), t).round())
		_rect(img, p.x - width / 2, p.y - width / 2, width, width, color)


func _poly(img: Image, points: Array, color: Color) -> void:
	var poly := PackedVector2Array()
	var min_x: int = img.get_width()
	var min_y: int = img.get_height()
	var max_x: int = 0
	var max_y: int = 0
	for point: Vector2i in points:
		poly.append(Vector2(point))
		min_x = mini(min_x, point.x)
		min_y = mini(min_y, point.y)
		max_x = maxi(max_x, point.x)
		max_y = maxi(max_y, point.y)
	for y in range(maxi(0, min_y), mini(img.get_height(), max_y + 1)):
		for x in range(maxi(0, min_x), mini(img.get_width(), max_x + 1)):
			if Geometry2D.is_point_in_polygon(Vector2(x, y), poly):
				img.set_pixel(x, y, color)
