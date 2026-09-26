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
	data["boardCandidates"] = board_candidates(bible)
	var file := FileAccess.open(OUT + "review.json", FileAccess.WRITE)
	file.store_string(JSON.stringify(data, "\t") + "\n")
	file.close()
	print("Review data: %d body slots, %d head candidates (%d new) -> %sreview.json" % [data.body.size(), data.headCandidates.size(), n, OUT])
	quit()


## Every board under assets/boards/ with generated candidates (any PNG below candidates/).
func board_candidates(bible: Dictionary) -> Array:
	var result := []
	var packs := {}
	for dir in DirAccess.get_directories_at(A):
		if FileAccess.file_exists(A + dir + "/pack.json"):
			var pack: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(A + dir + "/pack.json"))
			packs[str(pack.get("sourceImage", ""))] = {"dir": dir, "pack": pack}
	if not DirAccess.dir_exists_absolute(A + "boards"):
		return result
	for name in DirAccess.get_directories_at(A + "boards"):
		var board_dir := A + "boards/" + name + "/"
		var files := []
		collect_pngs(board_dir + "candidates/", files)
		if files.is_empty():
			continue
		var layout: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(board_dir + "sprite-slots.json"))
		DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT + "boards/" + name))
		var native := Image.load_from_file(board_dir + "slot-board.png")
		native.convert(Image.FORMAT_RGBA8)
		for y in native.get_height():
			for x in native.get_width():
				var c := native.get_pixel(x, y)
				if c.r8 == 255 and c.g8 == 0 and c.b8 == 255:
					native.set_pixel(x, y, Color(0, 0, 0, 0))
		Indexed.save_png(native, OUT + "boards/%s/native.png" % name)
		var entry := {"board": name, "part": layout.part, "group": layout.group, "view": layout.view.directions, "rawFacing": layout.view.rawFacing, "nativeBoard": "review/boards/%s/native.png" % name, "candidates": []}
		for path: String in files:
			var raw := Image.new()
			if raw.load_png_from_buffer(FileAccess.get_file_as_bytes(path)) != OK:
				continue
			var id := path.trim_prefix(board_dir + "candidates/").get_basename().replace("/candidate", "")
			var board: Image = Indexed.import_board(raw, Vector2i(int(layout.canvas[0]), int(layout.canvas[1])), bible._palette).image
			var shown := "review/boards/%s/%s.png" % [name, id.replace("/", "-")]
			Indexed.save_png(board, A + shown)
			var gate := Gate.gate(layout.part, bible, board, "", board_dir)
			var slots := []
			for index: String in gate.slots:
				var slot: Dictionary = gate.slots[index]
				slots.append({"index": int(index), "pass": slot.pass, "failures": slot.failures, "areaRatio": slot.metrics.get("areaRatio", 0.0), "alphaIoU": slot.metrics.get("alphaIoU", 0.0), "outlineRatio": slot.metrics.get("outlineRatio", 0.0)})
			var candidate := {"id": id, "source": path.trim_prefix(A), "sourceSize": [raw.get_width(), raw.get_height()], "image": shown, "pass": gate.pass, "slots": slots, "pack": null, "contacts": {}}
			if packs.has(path):
				var found: Dictionary = packs[path]
				candidate.pack = found.dir
				for direction: String in found.pack.fixtures:
					var cropped := "review/boards/%s/%s-%s.png" % [name, id.replace("/", "-"), direction]
					Indexed.save_png(crop_strip(Image.load_from_file(A + found.dir + "/" + found.pack.fixtures[direction].contact.file)), A + cropped)
					candidate.contacts[direction] = cropped
			entry.candidates.append(candidate)
		result.append(entry)
	return result

func collect_pngs(dir: String, into: Array) -> void:
	if not DirAccess.dir_exists_absolute(dir):
		return
	for file in DirAccess.get_files_at(dir):
		if file.to_lower().ends_with(".png"):
			into.append(dir + file)
	for sub in DirAccess.get_directories_at(dir):
		collect_pngs(dir + sub + "/", into)
	into.sort()

## A 192-px-per-frame contact strip cropped to the union of used pixels, doubled.
func crop_strip(strip: Image) -> Image:
	var count := strip.get_width() / 192
	var used := Rect2i()
	for i in count:
		var r := strip.get_region(Rect2i(i * 192, 0, 192, 192)).get_used_rect()
		used = r if used.size == Vector2i.ZERO else used.merge(r)
	used = used.grow(4).intersection(Rect2i(0, 0, 192, 192))
	var out := Image.create(count * used.size.x, used.size.y, false, Image.FORMAT_RGBA8)
	for i in count:
		out.blit_rect(strip, Rect2i(i * 192 + used.position.x, used.position.y, used.size.x, used.size.y), Vector2i(i * used.size.x, 0))
	out.resize(out.get_width() * 2, out.get_height() * 2, Image.INTERPOLATE_NEAREST)
	return out
