extends SceneTree
## Registered input board for replacing one native SPR head bitmap.
const BASE := "res://tools/character-lab/assets/native-head-v1/"
const TEMPLATE := "res://tools/character-lab/assets/native-template-v1/"
const SIZE := Vector2i(64,64)
const CROP := Rect2i(17,19,30,26)

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(BASE))
	var source := TEMPLATE+"sprites/head/001.png"
	var head := Image.load_from_file(source)
	assert(head.get_size() == CROP.size,"Unexpected native head slot size")
	var board := Image.create(SIZE.x,SIZE.y,false,Image.FORMAT_RGBA8)
	board.fill(Color("ff00ff"))
	board.blend_rect(head,Rect2i(Vector2i.ZERO,CROP.size),CROP.position)
	assert(board.save_png(BASE+"head-slot-board.png") == OK)
	board.resize(1024,1024,Image.INTERPOLATE_NEAREST)
	assert(board.save_png(BASE+"head-slot-board-16x.png") == OK)
	var template: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(TEMPLATE+"template.json"))
	for state_name in ["ready","attack"]:
		for frame: Dictionary in template.parts.head.actions[state_name].frames:
			for layer: Dictionary in frame.layers:
				assert(int(layer.index) in [-1,1],"This direction needs another head slot")
	var metadata := {"schemaVersion":1,"part":"head","index":1,"canvas":[64,64],"enlargedCanvas":[1024,1024],"scale":16,"background":"#FF00FF","imageRect":[17,19,30,26],"cell":[0,0,64,64],"sourceFile":source,"sourceFileSha256":FileAccess.get_sha256(source),"orientation":"Raw SPR bitmap; unmirrored. Original ACT performs the mirror at playback.","placement":"Exact source bitmap centered in a fixed 64x64 canvas. Never auto-trim or recenter the generated result.","requiredSourceActions":{"ready":38,"attack":86},"uniqueHeadSlots":[1],"sourceTemplateSha256":FileAccess.get_sha256(TEMPLATE+"template.json")}
	var file := FileAccess.open(BASE+"head-slot.json",FileAccess.WRITE)
	file.store_string(JSON.stringify(metadata,"\t")+"\n")
	file.close()
	print("Head input: 64x64, crop [17,19,30,26], enlarged 16x to 1024x1024. Only SPR 1 is used.")
	quit()
