extends SceneTree
## Reproducible native-art export; does not change any game data or renderer.
## Run from the repository root:
## .tools/Godot.app/Contents/MacOS/Godot --headless --path . --script res://tools/character-lab/export_reference.gd
const Actor = preload("res://scripts/ro_sprite_actor.gd")
const OUT := "res://tools/character-lab/assets/"
const FRAME_SIZE := Vector2i(192,192)
const DIRECTIONS := [0,2,4,6]
const NAMES := ["south","west","north","east"]
const LABELS := ["South","West","North","East"]
const CONTACT_CROP := Rect2i(48,60,96,120)
const CONTACT_SCALE := 4

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var output_path := ProjectSettings.globalize_path(OUT)
	if DirAccess.make_dir_recursive_absolute(output_path) != OK:
		_fail("Cannot create reference export directory")
		return
	var scene := Node3D.new()
	root.add_child(scene)
	var actor := Actor.new()
	scene.add_child(actor)
	actor.configure("swordsman")
	actor.weapon_visible = true
	actor.set_process(false)
	actor.set_state("idle")
	actor._clock = 0.0
	var anchor := Vector2i(Actor.ORIGIN.x,Actor.ORIGIN.y+int(actor._feet_offset))
	if anchor != Vector2i(96,168):
		_fail("Unexpected Swordsman anchor; review reference registration before exporting")
		return
	var atlas := Image.create(FRAME_SIZE.x*DIRECTIONS.size(),FRAME_SIZE.y,false,Image.FORMAT_RGBA8)
	var contact := Image.create(CONTACT_CROP.size.x*DIRECTIONS.size(),CONTACT_CROP.size.y,false,Image.FORMAT_RGBA8)
	contact.fill(Color("d7d2c5"))
	var frames: Array[Dictionary] = []
	var opaque_pixels := 0
	var transparent_pixels := 0
	for index in DIRECTIONS.size():
		actor.direction = DIRECTIONS[index]
		actor._render_frame()
		var source: Image = actor._sprite.texture.get_image()
		var bounds := source.get_used_rect()
		if source.get_size() != FRAME_SIZE or not bounds.has_area() or not CONTACT_CROP.encloses(bounds):
			_fail("Reference direction %s does not fit the fixed source canvas/contact crop" % NAMES[index])
			return
		atlas.blit_rect(source,Rect2i(Vector2i.ZERO,FRAME_SIZE),Vector2i(index*FRAME_SIZE.x,0))
		contact.blend_rect(source,CONTACT_CROP,Vector2i(index*CONTACT_CROP.size.x,0))
		frames.append({"name":NAMES[index],"label":LABELS[index],
			"x":index*FRAME_SIZE.x,"y":0,"w":FRAME_SIZE.x,"h":FRAME_SIZE.y,
			"anchorX":anchor.x,"anchorY":anchor.y,"sourceDirection":DIRECTIONS[index],
			"contentBounds":{"x":bounds.position.x,"y":bounds.position.y,"w":bounds.size.x,"h":bounds.size.y}})
		for y in FRAME_SIZE.y:
			for x in FRAME_SIZE.x:
				if source.get_pixel(x,y).a > 0:
					opaque_pixels += 1
				else:
					transparent_pixels += 1
	if opaque_pixels == 0 or transparent_pixels == 0:
		_fail("The source must contain visible art and transparent canvas margins")
		return
	contact.resize(contact.get_width()*CONTACT_SCALE,contact.get_height()*CONTACT_SCALE,Image.INTERPOLATE_NEAREST)
	var atlas_path := OUT+"ro-swordsman-reference.png"
	var contact_path := OUT+"reference-contact.png"
	if atlas.save_png(atlas_path) != OK or contact.save_png(contact_path) != OK:
		_fail("Failed to save native reference PNGs")
		return
	var metadata := {
		"file":"ro-swordsman-reference.png","width":atlas.get_width(),"height":atlas.get_height(),
		"frames":frames,"displayHeight":94,
		"source":{"kind":"native-ro-act-spr","character":"male-swordsman","state":"idle","frame":0,
			"weaponVisible":true,"provenance":"../../../assets/reference-ro/provenance.json",
			"rights":"Original Ragnarok Online reference artwork; retained for this local study."},
		"registration":"Every view preserves the same 192x192 canvas and neutral-pose foot anchor; no per-view recentering.",
		"contact":{"file":"reference-contact.png","width":contact.get_width(),"height":contact.get_height(),
			"scale":CONTACT_SCALE,"filter":"nearest","background":"#d7d2c5",
			"crop":{"x":CONTACT_CROP.position.x,"y":CONTACT_CROP.position.y,"w":CONTACT_CROP.size.x,"h":CONTACT_CROP.size.y}},
		"verification":{"opaquePixels":opaque_pixels,"transparentPixels":transparent_pixels,
			"atlasSha256":FileAccess.get_sha256(atlas_path),"contactSha256":FileAccess.get_sha256(contact_path)}
	}
	var file := FileAccess.open(OUT+"reference.json",FileAccess.WRITE)
	if file == null:
		_fail("Failed to write reference metadata")
		return
	file.store_string(JSON.stringify(metadata,"\t")+"\n")
	file.close()
	# Read-back validation catches file, dimensions, alpha, or serialization errors.
	var reread := Image.new()
	var result := reread.load_png_from_buffer(FileAccess.get_file_as_bytes(atlas_path))
	if result != OK or reread.get_size() != Vector2i(768,192) or reread.get_pixel(0,0).a != 0:
		_fail("Reference atlas read-back validation failed")
		return
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(OUT+"reference.json"))
	if not parsed is Dictionary or parsed.frames.size() != 4:
		_fail("Reference metadata read-back validation failed")
		return
	print("Exported native Swordsman reference: 768x192 RGBA; 4 views; anchor 96,168; %d opaque / %d transparent pixels; contact %d x %d." % [opaque_pixels,transparent_pixels,contact.get_width(),contact.get_height()])
	quit()

func _fail(message: String) -> void:
	push_error(message)
	quit(1)
