extends SceneTree
## Deterministic import of the generated repaint into unchanged native SPR slots.
## No per-sprite alignment, warping, masking to source silhouettes, or ACT edits.
const Actor = preload("res://scripts/ro_sprite_actor.gd")
const TEMPLATE_BASE := "res://tools/character-lab/assets/native-template-v1/"
var BASE := TEMPLATE_BASE
var SOURCE := BASE+"costume-slot-board.png"
const PART_NAMES := ["body","head","weapon","trail"]

func _initialize() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--output-dir="):
			BASE = argument.trim_prefix("--output-dir=").trim_suffix("/")+"/"
	SOURCE = BASE+"costume-slot-board.png"
	call_deferred("run")

func rect_array(rect: Rect2i) -> Array:
	return [rect.position.x,rect.position.y,rect.size.x,rect.size.y]

func save_image(image: Image, path: String) -> Dictionary:
	assert(image.save_png(BASE+path) == OK,"Cannot save "+path)
	return {"file":path,"width":image.get_width(),"height":image.get_height(),"sha256":FileAccess.get_sha256(BASE+path),"bounds":rect_array(image.get_used_rect())}

func visible_pixels(image: Image) -> int:
	var count := 0
	for y in image.get_height():
		for x in image.get_width():
			if image.get_pixel(x,y).a > 0:
				count += 1
	return count

func alpha_overlap(original: Image, replacement: Image) -> Dictionary:
	assert(original.get_size() == replacement.get_size())
	var intersection := 0
	var union_pixels := 0
	var original_pixels := 0
	var replacement_pixels := 0
	for y in original.get_height():
		for x in original.get_width():
			var a := original.get_pixel(x,y).a > 0
			var b := replacement.get_pixel(x,y).a > 0
			if a: original_pixels += 1
			if b: replacement_pixels += 1
			if a and b: intersection += 1
			if a or b: union_pixels += 1
	return {"alphaIoU":float(intersection)/union_pixels if union_pixels > 0 else 1.0,"alphaThreshold":0,"intersectionPixels":intersection,"unionPixels":union_pixels,"originalOpaquePixels":original_pixels,"replacementOpaquePixels":replacement_pixels,"originalBounds":rect_array(original.get_used_rect()),"replacementBounds":rect_array(replacement.get_used_rect())}

func fingerprint_actions(parts: Array) -> Dictionary:
	var hashes := {}
	for i in parts.size():
		hashes[PART_NAMES[i]] = JSON.stringify(parts[i].actions).sha256_text()
	return hashes

func run() -> void:
	for directory in ["costume/body","costume/attack","costume/ready"]:
		DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(BASE+directory))
	var layout: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(TEMPLATE_BASE+"sprite-slots.json"))
	var template: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(TEMPLATE_BASE+"template.json"))
	var board := Image.load_from_file(SOURCE)
	assert(board != null,"Generated costume board missing")
	var source_size := board.get_size()
	board.convert(Image.FORMAT_RGBA8)
	board.resize(int(layout.canvas[0]),int(layout.canvas[1]),Image.INTERPOLATE_NEAREST)
	var keyed_pixels := 0
	for y in board.get_height():
		for x in board.get_width():
			var color := board.get_pixel(x,y)
			if color.r > 0.65 and color.b > 0.6 and color.g < 0.45 and color.r+color.b-2*color.g > 0.85:
				board.set_pixel(x,y,Color(0,0,0,0))
				keyed_pixels += 1
	var result := {
		"name":"Wayfarer costume on native Swordsman action",
		"schemaVersion":1,
		"sourceImage":"costume-slot-board.png",
		"sourceImageSha256":FileAccess.get_sha256(SOURCE),
		"sourceImageSize":[source_size.x,source_size.y],
		"originalTemplate":TEMPLATE_BASE+"template.json",
		"originalTemplateSha256":FileAccess.get_sha256(TEMPLATE_BASE+"template.json"),
		"slotMetadataSha256":FileAccess.get_sha256(TEMPLATE_BASE+"sprite-slots.json"),
		"import":{"operation":"Resize entire board to 288x192 nearest-neighbor once, then fixed imageRect crops from sprite-slots.json. No individual resizing, recentering, source silhouette masks, warping, or ACT edits.","nativeBoardSize":[288,192],"backgroundKey":"r > 0.65 and b > 0.6 and g < 0.45 and r+b-2*g > 0.85 (RGB normalized 0..1)","backgroundPixelsRemoved":keyed_pixels},
		"body":{},"sequences":{},"diagnostics":{},
		"caveats":["Repaint derived from original RO body references; original head, weapon and trail remain native reference artwork.","Same bitmap dimensions and ACT data preserve the template, but generated pixels can still drift inside their slots. Per-slot alpha overlap quantifies this rather than proving artistic approval.","Reconstruction through the existing local renderer, not a capture of the official game client."]
	}
	result.import["normalizedBoard"] = save_image(board,"costume/imported-board.png")
	var replacements: Dictionary = {}
	for slot: Dictionary in layout.slots:
		var crop := Rect2i(int(slot.imageRect[0]),int(slot.imageRect[1]),int(slot.imageRect[2]),int(slot.imageRect[3]))
		var cell := Rect2i(int(slot.cell[0]),int(slot.cell[1]),int(slot.cell[2]),int(slot.cell[3]))
		var replacement := board.get_region(crop)
		var original := Image.load_from_file(TEMPLATE_BASE+slot.sourceFile)
		assert(original.get_size() == replacement.get_size(),"Changed source SPR dimensions")
		var index := int(slot.index)
		var metadata := save_image(replacement,"costume/body/%03d.png" % index)
		metadata["sourceIndex"] = index
		metadata["imageRect"] = slot.imageRect
		metadata["cell"] = slot.cell
		result.body[str(index)] = metadata
		var diagnostic := alpha_overlap(original,replacement)
		diagnostic["visiblePixelsOutsideFixedCrop"] = visible_pixels(board.get_region(cell))-visible_pixels(replacement)
		result.diagnostics[str(index)] = diagnostic
		replacements[index] = ImageTexture.create_from_image(replacement)
		print("SPR %d alphaIoU %.6f; outside fixed crop: %d pixels" % [index,diagnostic.alphaIoU,diagnostic.visiblePixelsOutsideFixedCrop])
	var scene := Node3D.new()
	root.add_child(scene)
	var actor := Actor.new()
	scene.add_child(actor)
	actor.configure("swordsman")
	actor.set_process(false)
	actor.direction = 6
	actor.weapon_visible = true
	var source_parts: Array = [actor._body,actor._head,actor._weapon,actor._trail]
	var before := fingerprint_actions(source_parts)
	var original_body: Dictionary = actor._body
	actor._body = original_body.duplicate(true)
	for index: int in replacements:
		actor._body.textures[index] = replacements[index]
	# This process owns these caches. It must not reuse native compositions made
	# while configure() established the neutral foot anchor.
	Actor._frame_cache.clear()
	Actor._image_cache.clear()
	actor._current_key = ""
	var contact := Image.create(576,576,false,Image.FORMAT_RGBA8)
	for state_name in ["ready","attack"]:
		actor.set_state(state_name)
		var action: Dictionary = actor._get_action(actor._body,state_name,6)
		var count: int = action.frames.size() if state_name == "attack" else 1
		var frames: Array = []
		for i in count:
			actor._clock = i*maxf(0.024,action.delay)+0.000001
			actor._render_frame()
			var composite: Image = actor._sprite.texture.get_image()
			var metadata := save_image(composite,"costume/%s/frame-%02d.png" % [state_name,i])
			metadata["sourceFrame"] = i
			metadata["durationMs"] = action.delay*1000
			frames.append(metadata)
			if state_name == "attack":
				contact.blit_rect(composite,Rect2i(0,0,192,192),Vector2i(i%3*192,int(i/3)*192))
		result.sequences[state_name] = {"sourceAction":Actor.CHARACTER_GROUPS[state_name]*8+6,"frameDurationMs":action.delay*1000,"durationMs":count*action.delay*1000,"frames":frames}
	result["contactBoard"] = save_image(contact,"costume/attack/contact.png")
	contact.resize(1728,1728,Image.INTERPOLATE_NEAREST)
	result["contactBoard3x"] = save_image(contact,"costume/attack/contact-3x.png")
	var after := fingerprint_actions([actor._body,actor._head,actor._weapon,actor._trail])
	assert(before == after,"Original ACT data changed during replacement import")
	assert(fingerprint_actions(source_parts) == before,"Cached source ACT data changed")
	var body_sequence: Array = []
	for frame: Dictionary in actor._get_action(actor._body,"attack",6).frames:
		body_sequence.append(frame.layers[0].index)
	assert(body_sequence == [82,83,83,83,84,85,86,86,86],"Unexpected native body sequence")
	for index: int in replacements:
		assert(original_body.textures[index] != replacements[index],"Cached original bitmap was overwritten")
	result["verification"] = {"originalActionsSha256":before,"afterReplacementActionsSha256":after,"allACTDataUnchanged":true,"cachedSourceACTDataUnchanged":true,"sourceBitmapsRetained":true,"allReplacementDimensionsMatchSource":true,"bodyAttackIndexSequence":body_sequence,"reusedIndex83Frames":[1,2,3],"reusedIndex86Frames":[6,7,8],"allSourceFileHashesMatchTemplate":true}
	for source_path: String in template.sourceFiles:
		assert(FileAccess.get_sha256(source_path) == template.sourceFiles[source_path],"Original source file changed")
	var out := FileAccess.open(BASE+"costume.json",FileAccess.WRITE)
	out.store_string(JSON.stringify(result,"\t")+"\n")
	out.close()
	print("Costume imported: six body bitmaps, nine native attack frames, ACT unchanged.")
	quit()
