extends SceneTree
## Import a generated board for ANY board made by export_slot_board.gd or board_export.gd
## (body or head, any action groups and views). This is the generic importer (D14).
## Palette-indexed adapter + style-bible slot contract (refuses failing candidates),
## then fixture frames. ACT never changes.
##
## Godot --headless --log-file <abs log> --path . --script res://tools/character-lab/import_slot_board.gd -- \
##   --board=<board dir> --source=<generated png> --output-dir=<new art pack dir> \
##   [--style-bible=<json>; default: the board's "styleBible", else style-bible-v1] [--allow-contract-failure] [--name=...]
##   [--fixture-look=<appearance json>]   art for the OTHER parts in fixtures (e.g. the body under a new head)
##   [--fixture-headgear=none,cap,hat]    override the board's fixture headgear list
##   [--recipe=<json> --recipe-module=<id>]   provenance written by art_recipe.py (D14)
## Boards with a "fixtures" plan (board_export.gd) render every listed group x direction x
## headgear; older boards render the board's single view with the native head and weapon.
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

## "" when `path` is free (missing or an empty folder), otherwise why it is not.
static func occupied_reason(path: String) -> String:
	var folder := ProjectSettings.globalize_path(path.trim_suffix("/"))
	if FileAccess.file_exists(folder):
		return "is an existing file"
	if not DirAccess.dir_exists_absolute(folder):
		return ""
	var dir := DirAccess.open(folder)
	if dir == null:
		return "cannot be listed"
	dir.include_hidden = true
	if not dir.get_files().is_empty() or not dir.get_directories().is_empty():
		return "already contains files"
	return ""

func record(image: Image, base: String, path: String) -> Dictionary:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path((base + path).get_base_dir()))
	if not Indexed.save_png(image, base + path):
		quit(1)
	return {"file": path, "width": image.get_width(), "height": image.get_height(), "sha256": FileAccess.get_sha256(base + path)}

func run() -> void:
	var board_dir := option("board").trim_suffix("/") + "/"
	var source := option("source")
	var out := option("output-dir").trim_suffix("/") + "/"
	if board_dir == "/" or source.is_empty() or out == "/":
		return fail("Usage: --board=<dir> --source=<generated png> --output-dir=<pack dir>")
	# Packs are never overwritten or mixed: the output folder must be new or empty.
	var occupied := occupied_reason(out)
	if not occupied.is_empty():
		return fail("Output %s %s; nothing was written. Import into a new folder." % [out, occupied])
	var layout_value: Variant = JSON.parse_string(FileAccess.get_file_as_string(board_dir + "sprite-slots.json")) if FileAccess.file_exists(board_dir + "sprite-slots.json") else null
	if not layout_value is Dictionary:
		return fail("Board layout missing: " + board_dir + "sprite-slots.json")
	var layout: Dictionary = layout_value
	var part: String = layout.part
	var bible_path := option("style-bible", str(layout.get("styleBible", "res://tools/character-lab/style/style-bible-v1.json")))
	var bible := Gate.load_bible(bible_path)
	if bible.is_empty():
		return fail("Style bible unusable: " + bible_path)
	var raw := Image.new()
	if not FileAccess.file_exists(source) or raw.load_png_from_buffer(FileAccess.get_file_as_bytes(source)) != OK:
		return fail("Cannot read candidate " + source)
	for path: String in layout.sourceFiles:
		if FileAccess.get_sha256(path) != layout.sourceFiles[path]:
			return fail("Native source changed since the board was exported: " + path)
	var plan_mode: bool = layout.has("fixtures")
	if plan_mode:
		# New boards also pin their character spec, style bible and native drawings.
		for key in ["character", "styleBible"]:
			if layout.has(key + "Sha256") and FileAccess.get_sha256(layout[key]) != layout[key + "Sha256"]:
				return fail("%s changed since the board was exported: %s" % [key, layout[key]])
		for slot: Dictionary in layout.slots:
			if FileAccess.get_sha256(board_dir + slot.sourceFile) != slot.sourceSha256:
				return fail("Native drawing changed since the board was exported: " + board_dir + slot.sourceFile)
	var imported: Dictionary = Indexed.import_board(raw, Vector2i(int(layout.canvas[0]), int(layout.canvas[1])), bible._palette)
	var board: Image = imported.image
	var contract := Gate.gate(part, bible, board, "", board_dir)
	for index: String in contract.slots:
		for failure: String in contract.slots[index].failures:
			print("CONTRACT %s SPR %s: %s" % [part, index, failure])
	if not contract.pass and option("allow-contract-failure") != "true":
		return fail("Candidate fails the style bible slot contract; nothing was written. Regenerate, or pass --allow-contract-failure for a study pack.")
	# Fixture inputs are resolved before anything is written.
	var fixture_actor: Node = null
	var fixture_plan: Array = []
	if plan_mode:
		fixture_plan = layout.fixtures.duplicate(true)
		var headgear_override := option("fixture-headgear")
		for fixture: Dictionary in fixture_plan:
			if not headgear_override.is_empty():
				fixture.headgear = Array(headgear_override.split(",", false))
			for gear in fixture.headgear:
				if gear != "none" and not Actor.HEADGEAR_SOURCES.has(gear):
					return fail("Unknown fixture headgear " + str(gear))
		fixture_actor = Actor.new()
		root.add_child(fixture_actor)
		fixture_actor.configure("swordsman" if str(layout.job).begins_with("swordsman") else "novice")
		fixture_actor.set_process(false)
		var look_path := option("fixture-look")
		if not look_path.is_empty() and not fixture_actor.set_appearance(look_path):
			return fail("Fixture look unusable (missing pack or changed file): " + look_path)
	# Write the pack.
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out))
	var pack := {
		"schemaVersion": 1, "kind": "slot-pack", "name": option("name", str(layout.get("label", "%s %s %s" % [part, layout.group, "-".join(layout.view.directions)]))),
		"job": layout.job, "part": part, "group": layout.group, "view": layout.view, "nativeSource": layout.nativeSource,
		"board": {"layout": board_dir + "sprite-slots.json", "sha256": FileAccess.get_sha256(board_dir + "sprite-slots.json")},
		"sourceImage": source, "sourceImageSha256": FileAccess.get_sha256(source), "sourceImageSize": [raw.get_width(), raw.get_height()],
		"import": {"adapter": Indexed.ADAPTER, "palette": {"id": bible._palette.id, "file": bible.palette.file, "sha256": bible._palette.sha256}, "stats": imported.stats, "normalizedBoard": record(board, out, "imported-board.png")},
		"contract": {"bible": bible_path, "bibleSha256": FileAccess.get_sha256(bible_path), "pass": contract.pass, "allowedFailure": not contract.pass, "slots": contract.slots},
		part: {}, "diagnostics": {}, "fixtures": {},
	}
	if not option("recipe").is_empty():
		pack["recipe"] = {"path": option("recipe"), "sha256": FileAccess.get_sha256(option("recipe")), "module": option("recipe-module")}
	if plan_mode:
		pack["schemaVersion"] = 2
		pack["groups"] = layout.groups
		pack["character"] = {"file": layout.character, "sha256": FileAccess.get_sha256(layout.character)}
		pack["fixturePlan"] = fixture_plan
		pack["fixtureLook"] = {"file": option("fixture-look"), "sha256": FileAccess.get_sha256(option("fixture-look"))} if not option("fixture-look").is_empty() else {}
	var replacements := {}
	for slot: Dictionary in layout.slots:
		var r: Array = slot.imageRect
		var image := board.get_region(Rect2i(int(r[0]), int(r[1]), int(r[2]), int(r[3])))
		var index := int(slot.index)
		pack[part][str(index)] = record(image, out, "%s/%03d.png" % [part, index])
		var diagnostics := Indexed.validate(image, bible._palette)
		diagnostics["uniqueColors"] = Indexed.unique_colors(image)
		pack.diagnostics[str(index)] = diagnostics
		if diagnostics.offPalettePixels != 0 or diagnostics.keyTintedPixels != 0 or diagnostics.partialAlphaPixels != 0:
			return fail("Indexed %s SPR %d is not clean: %s" % [part, index, diagnostics])
		replacements[index] = ImageTexture.create_from_image(image)
	if plan_mode:
		var fixture_result := render_plan(fixture_actor, layout, part, replacements, fixture_plan, out, pack)
		if not fixture_result.is_empty():
			return fail(fixture_result)
	else:
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
	print("Slot pack %s: %d drawings, contract %s, %d fixture sets -> %s" % [pack.name, replacements.size(), "PASS" if contract.pass else "FAIL (allowed)", pack.fixtures.size(), out])
	quit()

## Fixtures for a board's plan: every group x direction x headgear, drawn body -> head ->
## headgear -> weapon -> trail (the single studied order; inspection C9 is still open).
## The imported drawings replace their slots on top of the fixture look (or native art).
## Returns "" or an error.
func render_plan(actor: Node, layout: Dictionary, part: String, replacements: Dictionary, plan: Array, out: String, pack: Dictionary) -> String:
	var base: Dictionary = actor._body if part == "body" else actor._head
	if base.is_empty() or str(base.source).get_slice("@", 0) != str(layout.nativeSource):
		return "Fixture actor has no %s for %s" % [part, layout.nativeSource]
	var native: Dictionary = SpriteData.load_pair(layout.nativeSource)
	var before := JSON.stringify(native.actions).sha256_text()
	var look: Dictionary = base.duplicate()
	var textures: Array[Texture2D] = base.textures.duplicate()
	for index: int in replacements:
		if textures[index].get_size() != replacements[index].get_size():
			return "SPR %d does not fit the native image" % index
		textures[index] = replacements[index]
	look.textures = textures
	look.source = "%s@%s" % [layout.nativeSource, out]
	if JSON.stringify(look.actions).sha256_text() != before:
		return "Fixture %s ACT differs from the native ACT" % part
	var body: Dictionary = look if part == "body" else actor._body
	var head: Dictionary = look if part == "head" else actor._head
	var attack_group: int = Actor.CHARACTER_GROUPS.attack
	var count := 0
	for fixture: Dictionary in plan:
		var gi := int(fixture.groupIndex)
		for name in fixture.directions:
			var d := DIRECTIONS.find(str(name))
			var body_action: Dictionary = body.actions[gi * 8 + d]
			for gear in fixture.headgear:
				var gear_data: Dictionary = {} if gear == "none" else Actor._load(Actor.HEADGEAR_SOURCES[gear])
				if gear != "none" and gear_data.is_empty():
					return "Native headgear %s missing" % gear
				var n: int = body_action.frames.size()
				var contact := Image.create(maxi(1, n) * 192, 192, false, Image.FORMAT_RGBA8)
				var frames := []
				for i in n:
					var canvas := Image.create(192, 192, false, Image.FORMAT_RGBA8)
					var body_frame: Dictionary = body_action.frames[i]
					actor._draw_part(canvas, body, body_frame, Vector2.ZERO)
					for data: Dictionary in [head, gear_data]:
						if data.is_empty():
							continue
						var action: Dictionary = data.actions[gi * 8 + d]
						var frame: Dictionary = action.frames[i % action.frames.size()]
						actor._draw_part(canvas, data, frame, actor._attachment(body_frame, frame))
					if fixture.get("weapon", true):
						for data: Dictionary in [actor._weapon, actor._trail if gi == attack_group else {}]:
							if data.is_empty():
								continue
							var action: Dictionary = data.actions[gi * 8 + d]
							actor._draw_part(canvas, data, action.frames[i % action.frames.size()], Vector2.ZERO)
					frames.append(record(canvas, out, "fixtures/%s/%s/%s/frame-%02d.png" % [fixture.group, name, gear, i]))
					contact.blit_rect(canvas, Rect2i(0, 0, 192, 192), Vector2i(i * 192, 0))
					count += 1
				pack.fixtures["%s/%s/%s" % [fixture.group, name, gear]] = {"group": fixture.group, "direction": name, "headgear": gear, "sourceAction": gi * 8 + d,
					"frameDurationMs": body_action.delay * 1000, "frames": frames, "contact": record(contact, out, "fixtures/%s/%s/%s/contact.png" % [fixture.group, name, gear])}
	if JSON.stringify(look.actions).sha256_text() != before:
		return "ACT data changed during import"
	pack["verification"] = {"actUnchanged": true, "actionsSha256": before, "nativeSourceHashesMatchBoard": true, "fixtureFrames": count,
		"drawOrder": ["body", "head", "headgear", "weapon", "trail"], "otherParts": "fixture look" if not str(pack.get("fixtureLook", {}).get("file", "")).is_empty() else "native"}
	return ""
