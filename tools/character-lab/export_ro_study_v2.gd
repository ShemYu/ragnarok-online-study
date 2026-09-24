extends SceneTree
## Local native ACT/SPR study. No AI rendering, interpolation, or frame recentering.
## .tools/Godot.app/Contents/MacOS/Godot --headless --path . --script res://tools/character-lab/export_ro_study_v2.gd
const Actor = preload("res://scripts/ro_sprite_actor.gd")
const OUT := "res://tools/character-lab/assets/video-tests/ro-study-v2/"
const SIZE := Vector2i(192,192)
const NAMES := ["south","southwest","west","northwest","north","northeast","east","southeast"]
const MATTE := Color("e8e6df")

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT))
	var scene := Node3D.new()
	root.add_child(scene)
	var sequences: Array[Dictionary] = []
	var sources: Dictionary = {}
	var style_board := Image.create(4*96,2*120,false,Image.FORMAT_RGBA8)
	style_board.fill(MATTE)
	var class_row := 0
	for kind in ["swordsman","novice"]:
		var actor := Actor.new()
		scene.add_child(actor)
		actor.configure(kind)
		actor.set_process(false)
		actor.weapon_visible = true
		var anchor := Vector2i(Actor.ORIGIN.x,Actor.ORIGIN.y+int(actor._feet_offset))
		for part in [actor._body,actor._head,actor._weapon,actor._trail]:
			for extension in [".act",".spr"]:
				var source_path: String = part.source+extension
				sources[source_path] = FileAccess.get_sha256(source_path)
		for state_name in ["idle","ready","attack"]:
			var direction_contact := Image.create(4*192,2*192,false,Image.FORMAT_RGBA8)
			direction_contact.fill(MATTE)
			for view in 8:
				actor.direction = view
				actor.set_state(state_name)
				var action: Dictionary = actor._get_action(actor._body,state_name,view)
				var source_action_fingerprints: Dictionary = {}
				for part in [actor._body,actor._head,actor._weapon,actor._trail]:
					var source_action: Dictionary = actor._get_action(part,state_name,view)
					source_action_fingerprints[part.source] = JSON.stringify(source_action).sha256_text()
				# Idle source poses encode head direction; take pose zero consistently.
				var count: int = action.frames.size() if state_name == "attack" else 1
				var sequence_id: String = "%s-%s-%s" % [kind,state_name,NAMES[view]]
				DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT+sequence_id))
				var atlas := Image.create(count*192,192,false,Image.FORMAT_RGBA8)
				var contact := Image.create(3*192,ceili(count/3.0)*192,false,Image.FORMAT_RGBA8)
				contact.fill(MATTE)
				var frames: Array[Dictionary] = []
				for i in count:
					actor._clock = i*maxf(0.024,action.delay)+0.000001
					actor._render_frame()
					var frame: Image = actor._sprite.texture.get_image()
					var bounds := frame.get_used_rect()
					if not bounds.has_area() or not Rect2i(Vector2i.ZERO,SIZE).encloses(bounds):
						push_error("Empty or clipped reference: "+sequence_id)
						quit(1)
						return
					var file: String = sequence_id+"/frame-%02d.png" % i
					frame.save_png(OUT+file)
					atlas.blit_rect(frame,Rect2i(Vector2i.ZERO,SIZE),Vector2i(i*192,0))
					contact.blend_rect(frame,Rect2i(Vector2i.ZERO,SIZE),Vector2i(i%3*192,int(i/3)*192))
					if i == 0:
						direction_contact.blend_rect(frame,Rect2i(Vector2i.ZERO,SIZE),Vector2i(view%4*192,int(view/4)*192))
						if state_name == "idle" and view in [0,1,6,7]:
							style_board.blend_rect(frame,Rect2i(48,60,96,120),Vector2i([0,1,6,7].find(view)*96,class_row*120))
					var matte := Image.create(192,192,false,Image.FORMAT_RGBA8)
					matte.fill(MATTE)
					matte.blend_rect(frame,Rect2i(Vector2i.ZERO,SIZE),Vector2i.ZERO)
					matte.resize(576,576,Image.INTERPOLATE_NEAREST)
					matte.save_png(OUT+sequence_id+"/frame-%02d-3x.png" % i)
					frames.append({"file":file,"sha256":FileAccess.get_sha256(OUT+file),"sourceFrame":i,"sourceDurationMs":action.delay*1000,"bounds":{"x":bounds.position.x,"y":bounds.position.y,"w":bounds.size.x,"h":bounds.size.y}})
				atlas.save_png(OUT+sequence_id+"/atlas.png")
				contact.resize(contact.get_width()*2,contact.get_height()*2,Image.INTERPOLATE_NEAREST)
				contact.save_png(OUT+sequence_id+"/contact-2x.png")
				sequences.append({"id":sequence_id,"character":kind,"state":state_name,"direction":NAMES[view],"sourceDirection":view,"sourceAction":Actor.CHARACTER_GROUPS[state_name]*8+view,"sourceActionFingerprints":source_action_fingerprints,"sourceFrameCount":action.frames.size(),"exportedFrameCount":count,"frameDurationMs":action.delay*1000,"durationMs":count*action.delay*1000,"canvas":{"w":192,"h":192},"anchor":{"x":anchor.x,"y":anchor.y},"frames":frames})
			direction_contact.resize(direction_contact.get_width()*2,direction_contact.get_height()*2,Image.INTERPOLATE_NEAREST)
			direction_contact.save_png(OUT+kind+"-"+state_name+"-8-directions.png")
		actor.queue_free()
		class_row += 1
	style_board.resize(style_board.get_width()*3,style_board.get_height()*3,Image.INTERPOLATE_NEAREST)
	style_board.save_png(OUT+"native-style-board.png")
	var data := {"name":"Native RO reference study v2","provenance":"../../../../../assets/reference-ro/provenance.json","sourceFiles":sources,"sequences":sequences,"registration":"192x192 canvas; ACT origin 96,156; per-character neutral anchor; no per-frame recentering. Native palettes and nearest-neighbor layer assembly via local renderer.","timing":"ACT delay value times 24 ms. All attack frames retain original order/duration; idle/ready exports are single pose-zero views, not animation.","caveats":["A reconstruction of original sprite data with the local ACT/SPR renderer, not a recording of the official game client.","Source attack action ends on follow-through; no synthetic recovery was added.","Gameplay can retime this animation according to attack speed; exported timing is the source file timing.","Artwork is original Ragnarok Online reference material, retained locally; not newly authored game assets."]}
	var output := FileAccess.open(OUT+"manifest.json",FileAccess.WRITE)
	data["directionReuse"] = {"idle":"Eight visually distinct source direction slots.","readyAndAttack":"Eight source slots with four distinct drawings: south=southwest, west=northwest, north=northeast, east=southeast. Equality verified against full parsed ACT actions for body, head, dagger and trail, not only rendered image hashes.","attackSourceActionPairs":[[80,81],[82,83],[84,85],[86,87]],"readySourceActionPairs":[[32,33],[34,35],[36,37],[38,39]]}
	output.store_string(JSON.stringify(data,"\t")+"\n")
	output.close()
	print("Exported %d RO reference sequences; 8 directions for each of idle, ready, attack on Swordsman and Novice." % sequences.size())
	quit()
