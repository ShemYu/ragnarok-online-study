extends SceneTree
## Statistics for review.html: palette cleanup before/after and the slot
## contract (size vs native) for every head candidate. Re-run after adding
## generated heads to assets/native-head-v3/candidates/.
##
## Godot --headless --path . --script res://tools/character-lab/export_review.gd
const Indexed = preload("res://tools/character-lab/indexed_import.gd")
const Contract = preload("res://tools/character-lab/slot_contract.gd")
const Gate = preload("res://tools/character-lab/verify_candidate.gd")
const A := "res://tools/character-lab/assets/"
const OUT := "res://tools/character-lab/assets/review/"
const BIBLE := "res://tools/character-lab/style/style-bible-v1.json"
const CANDIDATES := "res://tools/character-lab/assets/native-head-v3/candidates/"

func _initialize() -> void:
	call_deferred("run")

func slot_stats(image: Image, palette: Dictionary) -> Dictionary:
	var v := Indexed.validate(image, palette)
	return {"colors": Indexed.unique_colors(image), "fringe": magenta_tinted(image), "offPalette": v.offPalettePixels}

## Opaque pixels visibly tinted by the magenta key (the specks seen on the
## contact sheets): red and blue well above green. Same test as the inspection.
func magenta_tinted(image: Image) -> int:
	var count := 0
	for y in image.get_height():
		for x in image.get_width():
			var c := image.get_pixel(x, y)
			if c.a8 > 0 and c.r8 > 150 and c.b8 > 110 and c.g8 < c.r8 - 50 and c.g8 < c.b8 - 30:
				count += 1
	return count

func summary(result: Dictionary) -> Dictionary:
	var m: Dictionary = result.metrics
	return {"pass": result.pass, "failures": result.failures, "areaRatio": m.get("areaRatio", 0.0), "faceRatio": m.get("faceRatio", -1.0),
		"alphaIoU": m.get("alphaIoU", 0.0), "outlineRatio": m.get("outlineRatio", 0.0),
		"area": m.get("replacement", {}).get("area", 0), "facePixels": m.get("replacement", {}).get("facePixels", 0), "faceBox": m.get("replacement", {}).get("faceBox", [])}

func run() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT + "candidates"))
	var bible := Gate.load_bible(BIBLE)
	var palette: Dictionary = bible._palette
	var data := {"schemaVersion": 1, "generatedAt": Time.get_datetime_string_from_system(true) + "Z", "palette": {"id": palette.id, "colors": palette.colors.size()}, "rules": bible.slotRules, "nativeFace": bible.nativeFaces["head:1"], "body": [], "head": {}, "headCandidates": []}
	# 1. Palette cleanup: v2 (threshold import) vs v3 (indexed import), same generated board.
	for index in [82, 83, 84, 85, 86, 54]:
		var file := "%03d.png" % index
		var native := Image.load_from_file(A + "native-template-v1/sprites/body/" + file)
		var before := Image.load_from_file(A + "native-wayfarer-v2/costume/body/" + file)
		var after := Image.load_from_file(A + "native-wayfarer-v3/costume/body/" + file)
		var contract := Contract.check("body", native, after, bible.slotRules.body, {}, bible._skin)
		data.body.append({"slot": index, "role": "ready" if index == 54 else "attack", "native": slot_stats(native, palette), "before": slot_stats(before, palette), "after": slot_stats(after, palette),
			"images": {"native": "native-template-v1/sprites/body/" + file, "before": "native-wayfarer-v2/costume/body/" + file, "after": "native-wayfarer-v3/costume/body/" + file},
			"contract": summary(contract)})
	var native_head := Image.load_from_file(A + "native-template-v1/sprites/head/001.png")
	var face: Dictionary = bible.nativeFaces["head:1"]
	var head_v1 := Image.load_from_file(A + "native-head-v1/head/001.png")
	var head_v2 := Image.load_from_file(A + "native-head-v2/head/001.png")
	data.head = {"native": slot_stats(native_head, palette), "before": slot_stats(head_v1, palette), "after": slot_stats(head_v2, palette), "nativeArea": Contract.measure(native_head, Contract.native_skin).area,
		"images": {"native": "native-template-v1/sprites/head/001.png", "before": "native-head-v1/head/001.png", "after": "native-head-v2/head/001.png"}}
	# 2. Head candidates against the slot contract. Prompt v0.1.0 produced one head.
	data.headCandidates.append({"id": "v0.1.0 · 1", "prompt": "v0.1.0", "designReference": "Wayfarer parts kit", "image": "native-head-v2/head/001.png", "source": "native-head-v1/generated-head.png",
		"contract": summary(Contract.check("head", native_head, head_v2, bible.slotRules.head, face, bible._skin))})
	var layout: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(A + "native-head-v1/head-slot.json"))
	var r: Array = layout.imageRect
	var files := DirAccess.get_files_at(CANDIDATES) if DirAccess.dir_exists_absolute(CANDIDATES) else PackedStringArray()
	var sorted := Array(files)
	sorted.sort()
	var n := 0
	for name: String in sorted:
		if not name.to_lower().ends_with(".png"):
			continue
		var raw := Image.new()
		if raw.load_png_from_buffer(FileAccess.get_file_as_bytes(CANDIDATES + name)) != OK:
			continue
		n += 1
		var board: Image = Indexed.import_board(raw, Vector2i(int(layout.canvas[0]), int(layout.canvas[1])), palette).image
		var slot := board.get_region(Rect2i(int(r[0]), int(r[1]), int(r[2]), int(r[3])))
		var shown := "review/candidates/" + name.get_basename() + "-slot.png"
		Indexed.save_png(slot, A + shown)
		data.headCandidates.append({"id": "v0.2.0 · %d" % n, "prompt": "v0.2.0", "designReference": "V3 compact attack art", "image": shown, "source": "native-head-v3/candidates/" + name,
			"contract": summary(Contract.check("head", native_head, slot, bible.slotRules.head, face, bible._skin))})
	var file := FileAccess.open(OUT + "review.json", FileAccess.WRITE)
	file.store_string(JSON.stringify(data, "\t") + "\n")
	file.close()
	print("Review data: %d body slots, %d head candidates (%d new) -> %sreview.json" % [data.body.size(), data.headCandidates.size(), n, OUT])
	quit()
