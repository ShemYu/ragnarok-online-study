extends SceneTree
## Preserve native accessory ACT records and decode SPR bitmaps for a local PoC.
const Actor = preload("res://scripts/ro_sprite_actor.gd")
const SpriteData = preload("res://scripts/ro_sprite_data.gd")
const OUT := "res://tools/character-lab/assets/native-equipment-v1/"
const VIEW := 6

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
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path((OUT+path).get_base_dir()))
	assert(image.save_png(OUT+path) == OK, "Cannot write " + path)
	var bounds := image.get_used_rect()
	return {"file":path,"width":image.get_width(),"height":image.get_height(),"sha256":FileAccess.get_sha256(OUT+path),"bounds":[bounds.position.x,bounds.position.y,bounds.size.x,bounds.size.y]}

func run() -> void:
	var actor := Actor.new()
	root.add_child(actor)
	actor.configure("swordsman")
	actor.set_process(false)
	actor.direction = VIEW
	var output := {"schemaVersion":1,"name":"Original RO headgear modules for male Swordsman","sourceDirection":VIEW,"canvas":[192,192],"origin":[96,156],"rotationUnit":"radians","attachment":"body.anchors[0] - headgear.anchors[0]; [0,0] when either anchor is absent","partFrameSelection":"body frame modulo headgear frame count","compositionOrder":["body","head","headgear","weapon","trail"],"parts":{},"sourceFiles":{},"limits":["Native headgear and body reference artwork retained locally for technical study.","Only east-facing ready and dagger attack actions are exported; not a full equipment library.","Composite fixtures are local renderer reconstructions, not official-client captures.","Native dagger is one class-based weapon appearance; a second dagger is not invented."]}
	for kind in ["cap","hat"]:
		var base: String = OUT+"source/"+kind
		var part: Dictionary = SpriteData.load_pair(base)
		assert(not part.is_empty(), "Missing native headgear: " + kind)
		part["source"] = base
		var out_part := {"id":kind,"label":"RO Cap" if kind == "cap" else "RO Hat","viewId":14 if kind == "cap" else 16,"source":base,"actVersion":part.act_version,"sprVersion":part.spr_version,"indexedCount":part.indexed_count,"events":part.events,"textures":{},"actions":{},"sequences":{}}
		for extension in [".act",".spr"]:
			output.sourceFiles[base+extension] = FileAccess.get_sha256(base+extension)
		for state_name in ["ready","attack"]:
			var source_action: int = Actor.CHARACTER_GROUPS[state_name]*8+VIEW
			assert(source_action < part.actions.size(), "Headgear source action absent")
			var action: Dictionary = part.actions[source_action]
			var frames: Array = []
			for frame: Dictionary in action.frames:
				frames.append(plain_frame(frame))
				for layer: Dictionary in frame.layers:
					if layer.index < 0 or out_part.textures.has(str(layer.index)):
						continue
					out_part.textures[str(layer.index)] = save_image(part.textures[layer.index].get_image(),"sprites/%s/%03d.png" % [kind,layer.index])
			out_part.actions[state_name] = {"sourceAction":source_action,"delayMs":action.delay*1000,"sourceFrameCount":action.frames.size(),"frames":frames}
			var body_action: Dictionary = actor._get_action(actor._body,state_name,VIEW)
			var rendered: Array = []
			var board := Image.create(576,576,false,Image.FORMAT_RGBA8)
			for i in body_action.frames.size():
				var body_frame: Dictionary = body_action.frames[i]
				var hat_frame: Dictionary = action.frames[i % action.frames.size()]
				var image := Image.create(192,192,false,Image.FORMAT_RGBA8)
				actor._draw_part(image,actor._body,body_frame,Vector2.ZERO)
				var head_action: Dictionary = actor._get_action(actor._head,state_name,VIEW)
				var head_frame: Dictionary = head_action.frames[i % head_action.frames.size()]
				actor._draw_part(image,actor._head,head_frame,actor._attachment(body_frame,head_frame))
				var hat_attachment := actor._attachment(body_frame,hat_frame)
				actor._draw_part(image,part,hat_frame,hat_attachment)
				var weapon_action: Dictionary = actor._get_action(actor._weapon,state_name,VIEW)
				actor._draw_part(image,actor._weapon,weapon_action.frames[i % weapon_action.frames.size()],Vector2.ZERO)
				if state_name == "attack":
					var trail_action: Dictionary = actor._get_action(actor._trail,state_name,VIEW)
					actor._draw_part(image,actor._trail,trail_action.frames[i % trail_action.frames.size()],Vector2.ZERO)
				var metadata := save_image(image,"%s/%s/frame-%02d.png" % [kind,state_name,i])
				metadata["sourceFrame"] = i % action.frames.size()
				metadata["attachment"] = [hat_attachment.x,hat_attachment.y]
				rendered.append(metadata)
				board.blit_rect(image,Rect2i(0,0,192,192),Vector2i(i%3*192,int(i/3)*192))
			out_part.sequences[state_name] = {"frames":rendered,"sourceAction":source_action,"durationMs":body_action.frames.size()*body_action.delay*1000}
			if state_name == "attack":
				out_part["board"] = save_image(board,kind+"/attack/contact.png")
				board.resize(1728,1728,Image.INTERPOLATE_NEAREST)
				out_part["enlargedBoard"] = save_image(board,kind+"/attack/contact-3x.png")
		output.parts[kind] = out_part
	var file := FileAccess.open(OUT+"equipment.json",FileAccess.WRITE)
	file.store_string(JSON.stringify(output,"\t")+"\n")
	file.close()
	for kind in output.parts:
		var item: Dictionary = output.parts[kind]
		print("%s: source action %d; frames %d; delay %.1f ms; textures %s" % [kind,item.actions.attack.sourceAction,item.actions.attack.sourceFrameCount,item.actions.attack.delayMs,item.textures.keys()])
	quit()
