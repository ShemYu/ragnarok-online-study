extends SceneTree
## Exact local ACT/SPR data template, for replacing art without inventing motion.
const Actor = preload("res://scripts/ro_sprite_actor.gd")
const OUT := "res://tools/character-lab/assets/native-template-v1/"
const SIZE := Vector2i(192,192)
const VIEW := 6
const PART_NAMES := ["body","head","weapon","trail"]

func _initialize() -> void:
	call_deferred("run")

func plain_frame(frame: Dictionary) -> Dictionary:
	var layers: Array = []
	for layer: Dictionary in frame.layers:
		layers.append({"x":layer.x,"y":layer.y,"index":layer.index,"mirror":layer.mirror,"color":[layer.color.r,layer.color.g,layer.color.b,layer.color.a],"scale":[layer.scale.x,layer.scale.y],"rotation":layer.rotation,"type":layer.type})
	var anchors: Array = []
	for anchor: Vector2 in frame.anchors:
		anchors.append([anchor.x,anchor.y])
	return {"layers":layers,"anchors":anchors,"event":frame.event}

func save_image(image: Image, path: String) -> Dictionary:
	var error := image.save_png(OUT+path)
	assert(error == OK,"Cannot save "+path)
	var bounds := image.get_used_rect()
	return {"file":path,"width":image.get_width(),"height":image.get_height(),"sha256":FileAccess.get_sha256(OUT+path),"bounds":[bounds.position.x,bounds.position.y,bounds.size.x,bounds.size.y]}

func run() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT))
	var scene := Node3D.new()
	root.add_child(scene)
	var actor := Actor.new()
	scene.add_child(actor)
	actor.configure("swordsman")
	actor.set_process(false)
	actor.direction = VIEW
	actor.weapon_visible = true
	var source_parts: Array = [actor._body,actor._head,actor._weapon,actor._trail]
	var data: Dictionary = {
		"name":"Native Swordsman ACT/SPR template v1",
		"schemaVersion":1,
		"character":"swordsman-male",
		"direction":"east",
		"sourceDirection":VIEW,
		"canvas":[192,192],
		"origin":[96,156],
		"neutralAnchor":[96,156+int(actor._feet_offset)],
		"rotationUnit":"radians",
		"coordinates":"Native ACT pixels; positive x right, positive y down. SPR images are centered at origin + layer position + part attachment. No frame recentering.",
		"composition":{"order":PART_NAMES,"headAttachment":"body.anchors[0] - head.anchors[0], or [0,0] if either missing","otherAttachments":[0,0],"partFrameSelection":"bodyFrameIndex modulo part frame count","trailVisible":"attack only","sampling":"nearest","untransformedTopLeft":"floor(center - imageSize/2)","transformedSampling":"For destination pixel center (x+0.5,y+0.5): subtract layer center, rotate by -rotation, divide by scale, negate x when mirror, add imageSize/2, floor for nearest source pixel. Multiply layer color and source-over blend."},
		"parts":{},"sequences":{},"sourceFiles":{},
		"caveats":["Local renderer reconstruction of original Ragnarok Online ACT/SPR data, not an official client recording.","Native timing is retained. Runtime attack speed can differ; this template does not retime it.","Ready exports only pose zero; source ready ACT frames are retained in the JSON.","Attack ends at its original last pose. No synthetic recovery, tweening, interpolation, or authored keyframes.","Original reference artwork belongs to its rightsholders and is retained locally as study material. Replacement art is a separate asset set."]
	}
	for part_index in PART_NAMES.size():
		var part_name: String = PART_NAMES[part_index]
		var part: Dictionary = source_parts[part_index]
		DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT+"sprites/"+part_name))
		var out_part := {"source":part.source,"actVersion":part.act_version,"sprVersion":part.spr_version,"indexedCount":part.indexed_count,"events":part.events,"textures":{},"actions":{}}
		for extension in [".act",".spr"]:
			data.sourceFiles[part.source+extension] = FileAccess.get_sha256(part.source+extension)
		for state_name in ["ready","attack"]:
			var action: Dictionary = actor._get_action(part,state_name,VIEW)
			var frames: Array = []
			for frame: Dictionary in action.frames:
				frames.append(plain_frame(frame))
				for layer: Dictionary in frame.layers:
					var index: int = layer.index
					if index < 0 or out_part.textures.has(str(index)):
						continue
					var image: Image = part.textures[index].get_image()
					out_part.textures[str(index)] = save_image(image,"sprites/%s/%03d.png" % [part_name,index])
			out_part.actions[state_name] = {"sourceAction":Actor.CHARACTER_GROUPS[state_name]*8+VIEW,"delayMs":action.delay*1000,"sourceFrameCount":action.frames.size(),"frames":frames}
		data.parts[part_name] = out_part
	var body_board := Image.create(576,576,false,Image.FORMAT_RGBA8)
	var head_board := Image.create(576,576,false,Image.FORMAT_RGBA8)
	var composite_board := Image.create(576,576,false,Image.FORMAT_RGBA8)
	for state_name in ["ready","attack"]:
		DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT+state_name))
		actor.set_state(state_name)
		var action: Dictionary = actor._get_action(actor._body,state_name,VIEW)
		var count: int = action.frames.size() if state_name == "attack" else 1
		var frames: Array = []
		for i in count:
			actor._clock = i*maxf(0.024,action.delay)+0.000001
			actor._render_frame()
			var composite: Image = actor._sprite.texture.get_image()
			var metadata := save_image(composite,"%s/frame-%02d.png" % [state_name,i])
			metadata["sourceFrame"] = i
			metadata["durationMs"] = action.delay*1000
			var body_frame: Dictionary = action.frames[i]
			metadata["parts"] = {}
			for part_index in PART_NAMES.size():
				var part_name: String = PART_NAMES[part_index]
				var part: Dictionary = source_parts[part_index]
				var part_action: Dictionary = actor._get_action(part,state_name,VIEW)
				var part_frame: Dictionary = part_action.frames[i % part_action.frames.size()]
				var part_image := Image.create(192,192,false,Image.FORMAT_RGBA8)
				var attachment := actor._attachment(body_frame,part_frame) if part_name == "head" else Vector2.ZERO
				if part_name != "trail" or state_name == "attack":
					actor._draw_part(part_image,part,part_frame,attachment)
				metadata.parts[part_name] = save_image(part_image,"%s/%s-%02d.png" % [state_name,part_name,i])
				metadata.parts[part_name]["sourceFrame"] = i % part_action.frames.size()
				metadata.parts[part_name]["attachment"] = [attachment.x,attachment.y]
				if state_name == "attack":
					if part_name == "body":
						body_board.blit_rect(part_image,Rect2i(Vector2i.ZERO,SIZE),Vector2i(i%3*192,int(i/3)*192))
					elif part_name == "head":
						head_board.blit_rect(part_image,Rect2i(Vector2i.ZERO,SIZE),Vector2i(i%3*192,int(i/3)*192))
			if state_name == "attack":
				composite_board.blit_rect(composite,Rect2i(Vector2i.ZERO,SIZE),Vector2i(i%3*192,int(i/3)*192))
			frames.append(metadata)
		data.sequences[state_name] = {"sourceAction":Actor.CHARACTER_GROUPS[state_name]*8+VIEW,"sourceFrameCount":action.frames.size(),"exportedFrameCount":count,"frameDurationMs":action.delay*1000,"durationMs":count*action.delay*1000,"frames":frames}
	data["boards"] = {}
	for board_name in ["body","head","composite"]:
		var board: Image = {"body":body_board,"head":head_board,"composite":composite_board}[board_name]
		data.boards[board_name] = {"native":save_image(board,board_name+"-attack-board.png"),"layout":[3,3],"cellSize":[192,192],"frameOrder":[0,1,2,3,4,5,6,7,8],"registration":"All frames use original 192x192 registration, with transparent background."}
		board.resize(1728,1728,Image.INTERPOLATE_NEAREST)
		data.boards[board_name]["enlarged"] = save_image(board,board_name+"-attack-board-3x.png")
	# Replacement-art input: unique raw SPR images rather than repeated ACT poses.
	# Placement is explicit and invertible so replacement bitmaps retain their index.
	var slot_board := Image.create(288,192,false,Image.FORMAT_RGBA8)
	slot_board.fill(Color("ff00ff"))
	var slots: Array = []
	var slot_indexes := [82,83,84,85,86,54]
	for slot_index in slot_indexes.size():
		var spr_index: int = slot_indexes[slot_index]
		var raw: Image = actor._body.textures[spr_index].get_image()
		var cell := Vector2i(slot_index%3*96,int(slot_index/3)*96)
		var top_left := cell+Vector2i(floori((96-raw.get_width())/2.0),88-raw.get_height())
		slot_board.blend_rect(raw,Rect2i(Vector2i.ZERO,raw.get_size()),top_left)
		slots.append({"part":"body","index":spr_index,"cell":[cell.x,cell.y,96,96],"imageRect":[top_left.x,top_left.y,raw.get_width(),raw.get_height()],"sourceFile":"sprites/body/%03d.png" % spr_index})
	data.boards["spriteSlots"] = {"native":save_image(slot_board,"sprite-slot-board.png"),"slots":slots,"background":"#FF00FF","layout":[3,2],"cellSize":[96,96],"placement":"Raw SPR images centered horizontally in each 96x96 cell, bitmap bottom at local y=88. No rotation, mirror, scaling, or ACT composition."}
	slot_board.resize(1440,960,Image.INTERPOLATE_NEAREST)
	data.boards.spriteSlots["enlarged"] = save_image(slot_board,"sprite-slot-board-5x.png")
	var slots_file := FileAccess.open(OUT+"sprite-slots.json",FileAccess.WRITE)
	slots_file.store_string(JSON.stringify({"canvas":[288,192],"enlargedCanvas":[1440,960],"scale":5,"background":"#FF00FF","slots":slots},"\t")+"\n")
	slots_file.close()
	var file := FileAccess.open(OUT+"template.json",FileAccess.WRITE)
	file.store_string(JSON.stringify(data,"\t")+"\n")
	file.close()
	print("Exported native template. Attack frames: %d; delayMs: %s; body SPR indexes: %s; neutral anchor: %s" % [data.sequences.attack.sourceFrameCount,data.sequences.attack.frameDurationMs,data.parts.body.textures.keys(),data.neutralAnchor])
	quit()
