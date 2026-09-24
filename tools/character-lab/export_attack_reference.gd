extends SceneTree
## Native ACT/SPR attack export, preserving source order, timing and registration.
## .tools/Godot.app/Contents/MacOS/Godot --headless --path . --script res://tools/character-lab/export_attack_reference.gd
const Actor = preload("res://scripts/ro_sprite_actor.gd")
const OUT := "res://tools/character-lab/assets/attack/"
const FRAME_SIZE := Vector2i(192,192)
const VIEW := 6 # East, the source's right-facing direction.
const PART_NAMES := ["body","head","weapon","trail"]

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	if DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT)) != OK:
		_fail("Cannot create attack reference export directory")
		return
	var scene := Node3D.new()
	root.add_child(scene)
	var actor := Actor.new()
	scene.add_child(actor)
	actor.configure("swordsman")
	actor.weapon_visible = true
	actor.set_process(false)
	actor.direction = VIEW
	actor.set_state("attack")
	var anchor := Vector2i(Actor.ORIGIN.x, Actor.ORIGIN.y + int(actor._feet_offset))
	var action: Dictionary = actor._get_action(actor._body,"attack",VIEW)
	var count: int = action.frames.size()
	var step: float = maxf(0.024,action.delay)
	var atlas := Image.create(FRAME_SIZE.x*count,FRAME_SIZE.y,false,Image.FORMAT_RGBA8)
	var contact := Image.create(FRAME_SIZE.x*count,FRAME_SIZE.y,false,Image.FORMAT_RGBA8)
	contact.fill(Color("e0d9c9"))
	var parts: Array[Dictionary] = [actor._body, actor._head, actor._weapon, actor._trail]
	var frames: Array[Dictionary] = []
	var sources: Array[Dictionary] = []
	for part in parts:
		for extension in [".act",".spr"]:
			var source_path: String = part.source + extension
			sources.append({"path":source_path,"sha256":FileAccess.get_sha256(source_path)})
	for i in count:
		actor._clock = i * step + 0.000001
		actor._render_frame()
		var frame_image: Image = actor._sprite.texture.get_image()
		var bounds := frame_image.get_used_rect()
		if frame_image.get_size() != FRAME_SIZE or not bounds.has_area():
			_fail("Missing native attack frame %d" % i)
			return
		atlas.blit_rect(frame_image,Rect2i(Vector2i.ZERO,FRAME_SIZE),Vector2i(i*FRAME_SIZE.x,0))
		contact.blend_rect(frame_image,Rect2i(Vector2i.ZERO,FRAME_SIZE),Vector2i(i*FRAME_SIZE.x,0))
		var part_frames: Dictionary = {}
		for part_index in parts.size():
			var part: Dictionary = parts[part_index]
			var part_action: Dictionary = actor._get_action(part,"attack",VIEW)
			var part_frame_index: int = i % part_action.frames.size()
			var part_frame: Dictionary = part_action.frames[part_frame_index]
			var attachment: Vector2 = actor._attachment(action.frames[i],part_frame) if part_index == 1 else Vector2.ZERO
			part_frames[PART_NAMES[part_index]] = {"sourceFrame":part_frame_index,
				"sourceAction":Actor.CHARACTER_GROUPS.attack*8+VIEW,
				"sourceDelayMs":part_action.delay*1000,
				"eventIndex":part_frame.event,"event":_event_name(part,part_frame.event),
				"anchors":_anchors(part_frame.anchors),
				"attachmentOffset":{"x":attachment.x,"y":attachment.y},
				"layerCount":part_frame.layers.size()}
		frames.append({"x":i*FRAME_SIZE.x,"y":0,"w":FRAME_SIZE.x,"h":FRAME_SIZE.y,
			"anchorX":anchor.x,"anchorY":anchor.y,"durationMs":action.delay*1000,
			"phase":"source-frame-%d" % (i+1),"sourceFrame":i,
			"contentBounds":{"x":bounds.position.x,"y":bounds.position.y,"w":bounds.size.x,"h":bounds.size.y},
			"parts":part_frames})
	var atlas_path := OUT+"reference-attack.png"
	var contact_path := OUT+"reference-attack-contact.png"
	contact.resize(contact.get_width()*3,contact.get_height()*3,Image.INTERPOLATE_NEAREST)
	if atlas.save_png(atlas_path) != OK or contact.save_png(contact_path) != OK:
		_fail("Could not save reference attack images")
		return
	var metadata := {"name":"RO Swordsman · dagger attack","file":"attack/reference-attack.png","scale":1,
		"canvasWidth":FRAME_SIZE.x,"canvasHeight":FRAME_SIZE.y,"anchor":{"x":anchor.x,"y":anchor.y},
		"frames":frames,"width":atlas.get_width(),"height":atlas.get_height(),
		"direction":"east","sourceDirection":VIEW,"durationMs":action.delay*count*1000,
		"source":{"kind":"native-ro-act-spr","character":"male-swordsman","state":"attack",
			"actionIndex":Actor.CHARACTER_GROUPS.attack*8+VIEW,"weapon":"dagger","parts":sources,
			"provenance":"../../../../assets/reference-ro/provenance.json",
			"rights":"Original Ragnarok Online reference artwork; retained for this local study."},
		"registration":"Original 192x192 actor canvas, ACT origin 96,156; fixed neutral foot baseline 96,168. All source frames in their original order; no per-frame recentering or timing changes.",
		"composition":"Matches the local native renderer: body, anchored head, weapon, trail. Source ACT per-part anchors and event names retained in each frame.",
		"phaseLabels":"Numeric source-frame labels intentionally avoid implying that source sound events define damage timing.",
		"verification":{"frameCount":count,"atlasSha256":FileAccess.get_sha256(atlas_path),
			"contactSha256":FileAccess.get_sha256(contact_path),"transparentMargin":atlas.get_pixel(0,0).a==0}}
	var metadata_file := FileAccess.open(OUT+"reference.json",FileAccess.WRITE)
	if metadata_file == null:
		_fail("Could not write native attack metadata")
		return
	metadata_file.store_string(JSON.stringify(metadata,"\t")+"\n")
	metadata_file.close()
	var reread := Image.new()
	if reread.load_png_from_buffer(FileAccess.get_file_as_bytes(atlas_path)) != OK or reread.get_size() != atlas.get_size():
		_fail("Attack atlas PNG read-back failed")
		return
	print("Native Swordsman east dagger attack: %d source frames, %.3f ms/frame, %.3f ms total, %dx%d atlas, fixed foot anchor %d,%d" % [count,action.delay*1000,action.delay*count*1000,atlas.get_width(),atlas.get_height(),anchor.x,anchor.y])
	for frame in frames:
		print("Frame %d: %s" % [frame.sourceFrame,JSON.stringify(frame.parts)])
	quit()

func _event_name(data: Dictionary, index: int) -> String:
	return data.events[index] if index >= 0 and index < data.events.size() else ""

func _anchors(values: Array) -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	for value in values:
		result.append({"x":value.x,"y":value.y})
	return result

func _fail(message: String) -> void:
	push_error(message)
	quit(1)
