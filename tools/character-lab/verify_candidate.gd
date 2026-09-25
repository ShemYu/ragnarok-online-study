extends SceneTree
## Generation gate (inspection A4): check a generated board, or already-imported
## slot bitmaps, against the style bible's slot contract before anything is imported.
##
##   --part=head|body                     which native slots
##   --source=<generated board png>       candidate straight from ImageGen
##   --pack=<art pack dir>                or: already-imported costume/body or head PNGs
##   --brief                              print the prompt SIZE CONTRACT for this part
##   --derive                             print native face numbers + skin palette candidates
##   --bible=<style bible json>           default res://tools/character-lab/style/style-bible-v1.json
## Exit code 1 when any slot fails, so scripts can stop before import.
const Indexed = preload("res://tools/character-lab/indexed_import.gd")
const Contract = preload("res://tools/character-lab/slot_contract.gd")
const TEMPLATE := "res://tools/character-lab/assets/native-template-v1/"
const HEAD_SLOT := "res://tools/character-lab/assets/native-head-v1/head-slot.json"

func _initialize() -> void:
	call_deferred("run")

func option(name: String, fallback: String = "") -> String:
	for argument in OS.get_cmdline_user_args():
		if argument == "--" + name:
			return "true"
		if argument.begins_with("--%s=" % name):
			return argument.trim_prefix("--%s=" % name)
	return fallback

static func load_bible(path: String) -> Dictionary:
	var bible: Variant = JSON.parse_string(FileAccess.get_file_as_string(path)) if FileAccess.file_exists(path) else null
	if not bible is Dictionary:
		push_error("Style bible unavailable: " + path)
		return {}
	var palette := Indexed.load_palette(bible.palette.file)
	if palette.is_empty() or palette.sha256 != bible.palette.sha256:
		push_error("Style bible palette missing or changed: " + str(bible.palette.file))
		return {}
	bible["_palette"] = palette
	bible["_skin"] = Contract.palette_skin(palette, bible.materials.skin)
	return bible

## Slot definitions: [{index, rect (in the normalized board), native (Image)}], canvas, offset, scale.
static func slots(part: String) -> Dictionary:
	if part == "head":
		var layout: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(HEAD_SLOT))
		var r: Array = layout.imageRect
		return {"canvas": Vector2i(int(layout.canvas[0]), int(layout.canvas[1])), "scale": int(layout.scale), "slots": [{"index": int(layout.index), "rect": Rect2i(int(r[0]), int(r[1]), int(r[2]), int(r[3])), "native": Image.load_from_file(TEMPLATE + "sprites/head/%03d.png" % int(layout.index)), "file": "head/%03d.png" % int(layout.index)}]}
	var sprite_slots: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(TEMPLATE + "sprite-slots.json"))
	var result := []
	for slot: Dictionary in sprite_slots.slots:
		var r: Array = slot.imageRect
		result.append({"index": int(slot.index), "rect": Rect2i(int(r[0]), int(r[1]), int(r[2]), int(r[3])), "native": Image.load_from_file(TEMPLATE + slot.sourceFile), "file": "costume/body/%03d.png" % int(slot.index)})
	return {"canvas": Vector2i(int(sprite_slots.canvas[0]), int(sprite_slots.canvas[1])), "scale": int(sprite_slots.scale), "slots": result}

## Check every slot of `part`. `board` is a normalized palette board (or null to read `pack`).
static func gate(part: String, bible: Dictionary, board: Image, pack: String) -> Dictionary:
	var definition := slots(part)
	var rules: Dictionary = bible.slotRules[part]
	var results := {}
	var passed := true
	for slot: Dictionary in definition.slots:
		var image: Image = board.get_region(slot.rect) if board else Image.load_from_file(pack.trim_suffix("/") + "/" + slot.file)
		var face: Dictionary = bible.get("nativeFaces", {}).get("%s:%d" % [part, slot.index], {})
		var result := Contract.check(part, slot.native, image, rules, face, bible._skin)
		results[str(slot.index)] = result
		passed = passed and result.pass
	return {"pass": passed, "slots": results}

func run() -> void:
	var part := option("part", "head")
	var bible_path := option("bible", "res://tools/character-lab/style/style-bible-v1.json")
	if option("derive") == "true":
		derive(part)
		return
	var bible := load_bible(bible_path)
	if bible.is_empty() or not bible.slotRules.has(part):
		push_error("No slot rules for part " + part)
		quit(1)
		return
	if option("brief") == "true":
		var definition := slots(part)
		for slot: Dictionary in definition.slots:
			var face: Dictionary = bible.get("nativeFaces", {}).get("%s:%d" % [part, slot.index], {})
			print("[%s SPR %d]" % [part, slot.index])
			print(Contract.brief(part, slot.native, bible.slotRules[part], face, slot.rect.position, definition.scale))
		quit()
		return
	var board: Image = null
	var source := option("source")
	if not source.is_empty():
		var raw := Image.load_from_file(source)
		if raw == null:
			push_error("Cannot load candidate " + source)
			quit(1)
			return
		board = Indexed.import_board(raw, slots(part).canvas, bible._palette).image
	elif option("pack").is_empty():
		push_error("Give --source=<generated board> or --pack=<imported art pack>")
		quit(1)
		return
	var result := gate(part, bible, board, option("pack"))
	for index: String in result.slots:
		var slot: Dictionary = result.slots[index]
		var m: Dictionary = slot.metrics
		print("%s SPR %s: %s  area %.0f%%  IoU %.3f  outline %.0f%%%s" % [part, index, "PASS" if slot.pass else "FAIL", m.get("areaRatio", 0) * 100, m.get("alphaIoU", 0), m.get("outlineRatio", 0) * 100, ("  face %.0f%%" % (m.faceRatio * 100)) if m.has("faceRatio") else ""])
		for failure: String in slot.failures:
			print("    - " + failure)
	print("GATE_%s %s" % [part.to_upper(), "PASS" if result.pass else "FAIL"])
	var report := option("report")
	if not report.is_empty():
		var file := FileAccess.open(report, FileAccess.WRITE)
		file.store_string(JSON.stringify(result, "\t") + "\n")
		file.close()
	quit(0 if result.pass else 1)

func derive(part: String) -> void:
	var definition := slots(part)
	for slot: Dictionary in definition.slots:
		var m := Contract.measure(slot.native, Contract.native_skin)
		print("%s:%d native area %d bbox %s edge %d face %d px box %s" % [part, slot.index, m.area, m.bbox, m.edgePixels, m.facePixels, m.faceBox])
	var palette := Indexed.load_palette(option("palette", "res://tools/character-lab/style/wayfarer-style-v1.json"))
	var candidates := []
	for i in palette.colors.size():
		if Contract.native_skin(palette.colors[i]):
			candidates.append("%d %s" % [i, (palette.colors[i] as Color).to_html(false)])
	print("skin-like palette entries (review before tagging): ", candidates)
	quit()
