extends SceneTree
## Replace native head SPR 1; preserve all head/body/equipment ACT records.
const Actor = preload("res://scripts/ro_sprite_actor.gd")
const SpriteData = preload("res://scripts/ro_sprite_data.gd")
const BASE := "res://tools/character-lab/assets/native-head-v1/"
const TEMPLATE := "res://tools/character-lab/assets/native-template-v1/"
const COSTUME := "res://tools/character-lab/assets/native-wayfarer-v2/"
const EQUIPMENT := "res://tools/character-lab/assets/native-equipment-v1/"
const SOURCE := BASE+"generated-head.png"
const VIEW := 6

func _initialize() -> void:
	call_deferred("run")

func rect_array(rect: Rect2i) -> Array:
	return [rect.position.x,rect.position.y,rect.size.x,rect.size.y]

func save_image(image: Image, path: String) -> Dictionary:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path((BASE+path).get_base_dir()))
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
	for y in original.get_height():
		for x in original.get_width():
			var a := original.get_pixel(x,y).a > 0
			var b := replacement.get_pixel(x,y).a > 0
			if a and b: intersection += 1
			if a or b: union_pixels += 1
	return {"alphaIoU":float(intersection)/union_pixels if union_pixels > 0 else 1.0,"alphaThreshold":0,"intersectionPixels":intersection,"unionPixels":union_pixels,"originalOpaquePixels":visible_pixels(original),"replacementOpaquePixels":visible_pixels(replacement),"originalBounds":rect_array(original.get_used_rect()),"replacementBounds":rect_array(replacement.get_used_rect())}

func fingerprints(parts: Dictionary) -> Dictionary:
	var result := {}
	for name: String in parts:
		result[name] = JSON.stringify(parts[name].actions).sha256_text()
	return result

func run() -> void:
	var layout: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(BASE+"head-slot.json"))
	var template: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(TEMPLATE+"template.json"))
	var costume: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(COSTUME+"costume.json"))
	var equipment: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(EQUIPMENT+"equipment.json"))
	var board := Image.load_from_file(SOURCE)
	assert(board != null,"Generated head board missing")
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
	var crop := Rect2i(int(layout.imageRect[0]),int(layout.imageRect[1]),int(layout.imageRect[2]),int(layout.imageRect[3]))
	var replacement := board.get_region(crop)
	var original := Image.load_from_file(TEMPLATE+"sprites/head/001.png")
	assert(original.get_size() == replacement.get_size(),"Changed native head SPR dimensions")
	var head_metadata := save_image(replacement,"head/001.png")
	head_metadata["sourceIndex"] = 1
	head_metadata["imageRect"] = layout.imageRect
	var diagnostic := alpha_overlap(original,replacement)
	diagnostic["visiblePixelsOutsideFixedCrop"] = visible_pixels(board)-visible_pixels(replacement)
	var output := {
		"schemaVersion":1,"name":"Wayfarer head on original RO attachment action","sourceImage":"generated-head.png","sourceImageSha256":FileAccess.get_sha256(SOURCE),"sourceImageSize":[source_size.x,source_size.y],
		"sourceDirection":VIEW,"sourceHeadIndex":1,"originalTemplate":TEMPLATE+"template.json","originalTemplateSha256":FileAccess.get_sha256(TEMPLATE+"template.json"),"costumeManifest":COSTUME+"costume.json","costumeManifestSha256":FileAccess.get_sha256(COSTUME+"costume.json"),"equipmentManifestSha256":FileAccess.get_sha256(EQUIPMENT+"equipment.json"),"slotMetadataSha256":FileAccess.get_sha256(BASE+"head-slot.json"),
		"import":{"operation":"Resize entire board to 64x64 nearest-neighbor once, remove magenta background, then fixed [17,19,30,26] crop. No individual recentering, resizing, silhouette masks, warping, or ACT edits.","nativeBoardSize":[64,64],"backgroundKey":"r > 0.65 and b > 0.6 and g < 0.45 and r+b-2*g > 0.85 (RGB normalized 0..1)","backgroundPixelsRemoved":keyed_pixels,"normalizedBoard":save_image(board,"imported-board.png")},
		"head":{"1":head_metadata},"diagnostics":{"1":diagnostic},"sequences":{},"sourceFiles":{},
		"limits":["One facing and one head image slot, reused by all nine native attack frames; not a full head direction library.","Generated replacement face and hair use the original head slot registration and ACT. A headgear module remains a separate original RO reference asset.","Wayfarer costume repaint and original dagger/trail are retained; reference composites use the local renderer, not the official client.","Geometry and timing checks do not constitute artistic approval of the head or every headgear combination."]
	}
	var actor := Actor.new()
	root.add_child(actor)
	actor.configure("swordsman")
	actor.set_process(false)
	actor.direction = VIEW
	var source_parts := {"body":actor._body,"head":actor._head,"weapon":actor._weapon,"trail":actor._trail}
	for gear in ["cap","hat"]:
		source_parts[gear] = SpriteData.load_pair(EQUIPMENT+"source/"+gear)
		assert(not source_parts[gear].is_empty(),"Native headgear missing")
		source_parts[gear]["source"] = EQUIPMENT+"source/"+gear
	var before := fingerprints(source_parts)
	var body: Dictionary = actor._body.duplicate(true)
	for index: String in costume.body:
		var metadata: Dictionary = costume.body[index]
		var image := Image.load_from_file(COSTUME+metadata.file)
		assert(image.get_size() == body.textures[int(index)].get_image().get_size())
		assert(FileAccess.get_sha256(COSTUME+metadata.file) == metadata.sha256,"Wayfarer body bitmap changed")
		body.textures[int(index)] = ImageTexture.create_from_image(image)
	var head: Dictionary = actor._head.duplicate(true)
	head.textures[1] = ImageTexture.create_from_image(replacement)
	# configure() may have cached original raw images. These fixtures must sample
	# the new textures under the same source identities and unchanged ACT records.
	Actor._image_cache.clear()
	Actor._frame_cache.clear()
	var action: Dictionary = actor._get_action(body,"attack",VIEW)
	var head_action: Dictionary = actor._get_action(head,"attack",VIEW)
	var weapon_action: Dictionary = actor._get_action(actor._weapon,"attack",VIEW)
	var trail_action: Dictionary = actor._get_action(actor._trail,"attack",VIEW)
	assert(action.frames.size() == 9)
	for gear in ["none","cap","hat"]:
		var board_image := Image.create(576,576,false,Image.FORMAT_RGBA8)
		var frames: Array = []
		for i in action.frames.size():
			var body_frame: Dictionary = action.frames[i]
			var head_frame: Dictionary = head_action.frames[i % head_action.frames.size()]
			var image := Image.create(192,192,false,Image.FORMAT_RGBA8)
			actor._draw_part(image,body,body_frame,Vector2.ZERO)
			actor._draw_part(image,head,head_frame,actor._attachment(body_frame,head_frame))
			if gear != "none":
				var gear_action: Dictionary = actor._get_action(source_parts[gear],"attack",VIEW)
				var gear_frame: Dictionary = gear_action.frames[i % gear_action.frames.size()]
				actor._draw_part(image,source_parts[gear],gear_frame,actor._attachment(body_frame,gear_frame))
			actor._draw_part(image,actor._weapon,weapon_action.frames[i % weapon_action.frames.size()],Vector2.ZERO)
			actor._draw_part(image,actor._trail,trail_action.frames[i % trail_action.frames.size()],Vector2.ZERO)
			var metadata := save_image(image,"%s/attack/frame-%02d.png" % [gear,i])
			metadata["sourceFrame"] = i
			metadata["durationMs"] = action.delay*1000
			frames.append(metadata)
			board_image.blit_rect(image,Rect2i(0,0,192,192),Vector2i(i%3*192,int(i/3)*192))
		var contact := save_image(board_image,"%s/attack/contact.png" % gear)
		board_image.resize(1728,1728,Image.INTERPOLATE_NEAREST)
		output.sequences[gear] = {"sourceAction":86,"frameDurationMs":action.delay*1000,"durationMs":action.frames.size()*action.delay*1000,"frames":frames,"contactBoard":contact,"contactBoard3x":save_image(board_image,"%s/attack/contact-3x.png" % gear)}
	var replacement_parts := source_parts.duplicate()
	replacement_parts.body = body
	replacement_parts.head = head
	var after := fingerprints(replacement_parts)
	assert(before == after,"Original ACT changed")
	assert(fingerprints(source_parts) == before,"Cached native ACT changed")
	assert(source_parts.head.textures[1] != head.textures[1],"Cached native head overwritten")
	output.sourceFiles.merge(template.sourceFiles)
	output.sourceFiles.merge(equipment.sourceFiles)
	for source_path: String in output.sourceFiles:
		assert(FileAccess.get_sha256(source_path) == output.sourceFiles[source_path],"Original source file changed")
	output["verification"] = {"originalActionsSha256":before,"afterReplacementActionsSha256":after,"allACTDataUnchanged":true,"cachedSourceACTDataUnchanged":true,"sourceBitmapsRetained":true,"allReplacementDimensionsMatchSource":true,"allSourceFileHashesMatchTemplate":true,"headAttackIndexSequence":[1,1,1,1,1,1,1,1,1],"headReadyIndexSequence":[1,1,1,1,1,1],"headgearVariants":["none","cap","hat"],"compositeFixtureCount":27,"originalHeadSha256":FileAccess.get_sha256(TEMPLATE+"sprites/head/001.png")}
	var file := FileAccess.open(BASE+"head.json",FileAccess.WRITE)
	file.store_string(JSON.stringify(output,"\t")+"\n")
	file.close()
	print("Head imported: one 30x26 bitmap, 27 native composites; six ACT records unchanged. AlphaIoU: %.6f; pixels outside fixed crop: %d" % [diagnostic.alphaIoU,diagnostic.visiblePixelsOutsideFixedCrop])
	quit()
