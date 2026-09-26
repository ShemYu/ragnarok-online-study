extends SceneTree
## Import a generated board for ANY board made by export_slot_board.gd.
## Palette-indexed adapter + style-bible slot contract (refuses failing candidates),
## then fixture frames for every direction of the drawn view. ACT never changes.
##
## Godot --headless --path . --script res://tools/character-lab/import_slot_board.gd -- \
##   --board=<board dir> --source=<generated png> --output-dir=<new art pack dir> \
##   [--style-bible=res://tools/character-lab/style/style-bible-v1.json] [--allow-contract-failure] [--name=...]
const Actor = preload("res://scripts/ro_sprite_actor.gd")
const SpriteData = preload("res://scripts/ro_sprite_data.gd")
const Indexed = preload("res://tools/character-lab/indexed_import.gd")
const Gate = preload("res://tools/character-lab/verify_candidate.gd")
const DIRECTIONS := ["S", "SW", "W", "NW", "N", "NE", "E", "SE"]

func _initialize() -> void:
	call_deferred("run")

func option(name: String, fallback: String = "") -> String:
	for argument in OS.get_cmdline_user_args():
		if argument == "--" + name:
			return "true"
		if argument.begins_with("--%s=" % name):
			return argument.trim_prefix("--%s=" % name)
	return fallback

func fail(message: String) -> void:
	push_error(message)
	quit(1)

func record(image: Image, base: String, path: String) -> Dictionary:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path((base + path).get_base_dir()))
	if not Indexed.save_png(image, base + path):
		quit(1)
	return {"file": path, "width": image.get_width(), "height": image.get_height(), "sha256": FileAccess.get_sha256(base + path)}

func run() -> void:
	var board_dir := option("board").trim_suffix("/") + "/"
	var source := option("source")
	var out := option("output-dir").trim_suffix("/") + "/"
	var bible_path := option("style-bible", "res://tools/character-lab/style/style-bible-v1.json")
	if board_dir == "/" or source.is_empty() or out == "/":
		return fail("Usage: --board=<dir> --source=<generated png> --output-dir=<pack dir>")
	var layout: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(board_dir + "sprite-slots.json"))
	var part: String = layout.part
	var bible := Gate.load_bible(bible_path)
	if bible.is_empty():
		return fail("Style bible unusable: " + bible_path)
	var raw := Image.new()
	if not FileAccess.file_exists(source) or raw.load_png_from_buffer(FileAccess.get_file_as_bytes(source)) != OK:
		return fail("Cannot read candidate " + source)
	for path: String in layout.sourceFiles:
		if FileAccess.get_sha256(path) != layout.sourceFiles[path]:
			return fail("Native source changed since the board was exported: " + path)
	var imported: Dictionary = Indexed.import_board(raw, Vector2i(int(layout.canvas[0]), int(layout.canvas[1])), bible._palette)
	var board: Image = imported.image
	var contract := Gate.gate(part, bible, board, "", board_dir)
	for index: String in contract.slots:
		for failure: String in contract.slots[index].failures:
			print("CONTRACT %s SPR %s: %s" % [part, index, failure])
	if not contract.pass and option("allow-contract-failure") != "true":
		return fail("Candidate fails the style bible slot contract; nothing was written. Regenerate, or pass --allow-contract-failure for a study pack.")
	# Write the pack.
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out))
	var pack := {
		"schemaVersion": 1, "kind": "slot-pack", "name": option("name", "%s %s %s" % [part, layout.group, "-".join(layout.view.directions)]),
		"job": layout.job, "part": part, "group": layout.group, "view": layout.view, "nativeSource": layout.nativeSource,
		"board": {"layout": board_dir + "sprite-slots.json", "sha256": FileAccess.get_sha256(board_dir + "sprite-slots.json")},
		"sourceImage": source, "sourceImageSha256": FileAccess.get_sha256(source), "sourceImageSize": [raw.get_width(), raw.get_height()],
		"import": {"adapter": Indexed.ADAPTER, "palette": {"id": bible._palette.id, "file": bible.palette.file, "sha256": bible._palette.sha256}, "stats": imported.stats, "normalizedBoard": record(board, out, "imported-board.png")},
		"contract": {"bible": bible_path, "bibleSha256": FileAccess.get_sha256(bible_path), "pass": contract.pass, "allowedFailure": not contract.pass, "slots": contract.slots},
		part: {}, "diagnostics": {}, "fixtures": {},
	}
	var replacements := {}
	for slot: Dictionary in layout.slots:
		var r: Array = slot.imageRect
		var image := board.get_region(Rect2i(int(r[0]), int(r[1]), int(r[2]), int(r[3])))
		var index := int(slot.index)
		pack[part][str(index)] = record(image, out, "%s/%03d.png" % [part, index])
		var diagnostics := Indexed.validate(image, bible._palette)
		diagnostics["uniqueColors"] = Indexed.unique_colors(image)
		pack.diagnostics[str(index)] = diagnostics
		replacements[index] = ImageTexture.create_from_image(image)
	# Fixtures: the view's frames with the new drawings, native head and weapon, per direction.
	var actor := Actor.new()
	root.add_child(actor)
	actor.configure("swordsman" if str(layout.job).begins_with("swordsman") else "novice")
	actor.set_process(false)
	var native: Dictionary = SpriteData.load_pair(layout.nativeSource)
	native["source"] = layout.nativeSource
	var before := JSON.stringify(native.actions).sha256_text()
	var look: Dictionary = native.duplicate()
	var textures: Array[Texture2D] = native.textures.duplicate()
	for index: int in replacements:
		textures[index] = replacements[index]
	look.textures = textures
	look.source = "%s@%s" % [layout.nativeSource, out]
	var group_index := int(layout.groupIndex)
	for name: String in layout.view.directions:
		var d := DIRECTIONS.find(name)
		var action: Dictionary = look.actions[group_index * 8 + d]
		var contact := Image.create(action.frames.size() * 192, 192, false, Image.FORMAT_RGBA8)
		var frames := []
		for i in action.frames.size():
			var canvas := Image.create(192, 192, false, Image.FORMAT_RGBA8)
			var frame: Dictionary = action.frames[i]
			var others: Dictionary = {"body": actor._body, "head": actor._head, "weapon": actor._weapon}
			var body_frame: Dictionary = frame if part == "body" else others.body.actions[group_index * 8 + d].frames[i % others.body.actions[group_index * 8 + d].frames.size()]
			actor._draw_part(canvas, look if part == "body" else others.body, body_frame, Vector2.ZERO)
			for other in ["head", "weapon"]:
				var data: Dictionary = look if other == part else others[other]
				if data.is_empty():
					continue
				var other_action: Dictionary = data.actions[group_index * 8 + d]
				var other_frame: Dictionary = other_action.frames[i % other_action.frames.size()]
				actor._draw_part(canvas, data, other_frame, actor._attachment(body_frame, other_frame) if other == "head" else Vector2.ZERO)
			frames.append(record(canvas, out, "fixtures/%s/frame-%02d.png" % [name, i]))
			contact.blit_rect(canvas, Rect2i(0, 0, 192, 192), Vector2i(i * 192, 0))
		pack.fixtures[name] = {"frames": frames, "contact": record(contact, out, "fixtures/%s/contact.png" % name), "sourceAction": group_index * 8 + d}
	var after := JSON.stringify(look.actions).sha256_text()
	if before != after:
		return fail("ACT data changed during import")
	pack["verification"] = {"actUnchanged": true, "actionsSha256": before, "nativeSourceHashesMatchBoard": true}
	var file := FileAccess.open(out + "pack.json", FileAccess.WRITE)
	file.store_string(JSON.stringify(pack, "\t") + "\n")
	file.close()
	print("Slot pack %s: %d drawings, contract %s, fixtures for %s -> %s" % [pack.name, replacements.size(), "PASS" if contract.pass else "FAIL (allowed)", ", ".join(layout.view.directions), out])
	quit()
