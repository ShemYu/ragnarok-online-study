extends RefCounted
## Config-driven import of the two saved native-template packs (D14, 2026-10-02).
## import_native_costume.gd and import_native_head.gd are thin wrappers that pass an
## importer configuration (tools/character-lab/importers/*.json) and their command-line
## options to run(). Template and layout paths, slots and crops, fixture actions and
## headgear combinations, file names and labels all come from that configuration; this
## file only holds the operations, kept step for step equal to the original importers so
## the saved costume v2/v3 and head v1/v2 packs reproduce byte for byte.
## New art (any action, view, part or character) goes through board_export.gd and
## import_slot_board.gd, which take their layout and fixture plan from the board.
const Actor = preload("res://scripts/ro_sprite_actor.gd")
const SpriteData = preload("res://scripts/ro_sprite_data.gd")
const Indexed = preload("res://tools/character-lab/indexed_import.gd")
const Gate = preload("res://tools/character-lab/verify_candidate.gd")


static func cli_options() -> Dictionary:
	var options := {}
	for argument in OS.get_cmdline_user_args():
		if not argument.begins_with("--"):
			continue
		var pair := argument.trim_prefix("--").split("=", true, 1)
		options[pair[0]] = pair[1] if pair.size() > 1 else "true"
	return options


static func load_config(path: String) -> Dictionary:
	var value: Variant = JSON.parse_string(FileAccess.get_file_as_string(path)) if FileAccess.file_exists(path) else null
	if not value is Dictionary:
		push_error("Importer configuration unusable: " + path)
		return {}
	value["_path"] = path
	return value


static func _dir(path: String) -> String:
	return path.trim_suffix("/") + "/"


static func _ints(values: Array) -> Array:
	return values.map(func(v) -> int: return int(v))


static func _rect_array(rect: Rect2i) -> Array:
	return [rect.position.x, rect.position.y, rect.size.x, rect.size.y]


static func _save(base: String, image: Image, path: String, make_dirs: bool) -> Dictionary:
	if make_dirs:
		DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path((base + path).get_base_dir()))
	if not Indexed.save_png(image, base + path):
		return {}
	return {"file": path, "width": image.get_width(), "height": image.get_height(), "sha256": FileAccess.get_sha256(base + path), "bounds": _rect_array(image.get_used_rect())}


static func _visible_pixels(image: Image) -> int:
	var count := 0
	for y in image.get_height():
		for x in image.get_width():
			if image.get_pixel(x, y).a > 0:
				count += 1
	return count


static func _alpha_overlap(original: Image, replacement: Image) -> Dictionary:
	var intersection := 0
	var union_pixels := 0
	var original_pixels := 0
	var replacement_pixels := 0
	for y in original.get_height():
		for x in original.get_width():
			var a := original.get_pixel(x, y).a > 0
			var b := replacement.get_pixel(x, y).a > 0
			if a: original_pixels += 1
			if b: replacement_pixels += 1
			if a and b: intersection += 1
			if a or b: union_pixels += 1
	return {"alphaIoU": float(intersection) / union_pixels if union_pixels > 0 else 1.0, "alphaThreshold": 0, "intersectionPixels": intersection, "unionPixels": union_pixels, "originalOpaquePixels": original_pixels, "replacementOpaquePixels": replacement_pixels, "originalBounds": _rect_array(original.get_used_rect()), "replacementBounds": _rect_array(replacement.get_used_rect())}


## The pre-palette adapter of the v0.1.0 packs: one nearest resize, then a magenta threshold key.
static func _legacy_normalize(board: Image, canvas: Vector2i, key: Dictionary) -> int:
	board.convert(Image.FORMAT_RGBA8)
	board.resize(canvas.x, canvas.y, Image.INTERPOLATE_NEAREST)
	var keyed := 0
	for y in board.get_height():
		for x in board.get_width():
			var color := board.get_pixel(x, y)
			if color.r > float(key.r) and color.b > float(key.b) and color.g < float(key.g) and color.r + color.b - 2 * color.g > float(key.sum):
				board.set_pixel(x, y, Color(0, 0, 0, 0))
				keyed += 1
	return keyed


static func _write_json(path: String, value: Dictionary) -> bool:
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		push_error("Cannot write " + path)
		return false
	file.store_string(JSON.stringify(value, "\t") + "\n")
	file.close()
	return true


static func _fail(message: String) -> int:
	push_error(message)
	return 1


static func _recipe(options: Dictionary) -> Dictionary:
	var path: String = options.get("recipe", "")
	return {"path": path, "sha256": FileAccess.get_sha256(path), "module": options.get("recipe-module", "")} if not path.is_empty() else {}


static func _character(config: Dictionary, options: Dictionary) -> String:
	return options.get("character-label", config.labels.defaultCharacter)


## Entry point for both wrappers. Returns the process exit code.
static func run(tree: SceneTree, config: Dictionary, options: Dictionary) -> int:
	if config.is_empty():
		return 2
	match str(config.get("schema", "")):
		"costume-v1":
			return _run_costume(tree, config, options)
		"head-v1":
			return _run_head(tree, config, options)
	return _fail("Unknown importer schema in " + str(config.get("_path", "")))


static func _run_costume(tree: SceneTree, config: Dictionary, options: Dictionary) -> int:
	var template_base: String = config.templateDir
	var base := _dir(options.get("output-dir", config.defaultOutputDir))
	var source: String = options.get("source", base + config.defaultSource)
	var palette_path: String = options.get("palette", "")
	var bible_path: String = options.get("style-bible", "")
	var allow_failure: bool = options.has("allow-contract-failure")
	var files: Dictionary = config.files
	var direction := int(config.direction)
	var contract := {}
	var layout: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(config.layout))
	var template: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(template_base + "template.json"))
	var board := Image.load_from_file(source)
	if board == null:
		return _fail("Generated costume board missing")
	var source_size := board.get_size()
	var canvas := Vector2i(int(layout.canvas[0]), int(layout.canvas[1]))
	var bible := {}
	if not bible_path.is_empty():
		bible = Gate.load_bible(bible_path)
		if bible.is_empty():
			return _fail("Style bible unusable")
		palette_path = bible.palette.file
	var palette := {}
	var indexed_stats := {}
	var keyed_pixels := 0
	if not palette_path.is_empty():
		palette = Indexed.load_palette(palette_path)
		if palette.is_empty():
			return _fail("Style palette missing")
		var imported: Dictionary = Indexed.import_board(board, canvas, palette)
		board = imported.image
		indexed_stats = imported.stats
		keyed_pixels = board.get_width() * board.get_height() - _visible_pixels(board)
		if not bible.is_empty():
			contract = Gate.gate(config.part, bible, board, "")
			for index: String in contract.slots:
				for failure: String in contract.slots[index].failures:
					print("CONTRACT %s SPR %s: %s" % [config.part, index, failure])
			if not contract.pass and not allow_failure:
				return _fail("Candidate fails the style bible slot contract; nothing was written. Regenerate, or pass --allow-contract-failure for a study pack.")
	else:
		keyed_pixels = _legacy_normalize(board, canvas, config.legacyKey)
	var labels: Dictionary = config.labels
	var canvas_text := "%dx%d" % [canvas.x, canvas.y]
	var result := {
		"name": str(labels.name).format({"character": _character(config, options)}),
		"schemaVersion": 1,
		"sourceImage": source.trim_prefix(base) if source.begins_with(base) else source,
		"sourceImageSha256": FileAccess.get_sha256(source),
		"sourceImageSize": [source_size.x, source_size.y],
		"originalTemplate": template_base + "template.json",
		"originalTemplateSha256": FileAccess.get_sha256(template_base + "template.json"),
		"slotMetadataSha256": FileAccess.get_sha256(config.layout),
		"import": {"operation": str(labels.legacyOperation).format({"canvas": canvas_text}), "nativeBoardSize": [canvas.x, canvas.y], "backgroundKey": config.legacyKey.text, "backgroundPixelsRemoved": keyed_pixels},
		"body": {}, "sequences": {}, "diagnostics": {},
		"caveats": labels.caveats.duplicate(),
	}
	if not palette_path.is_empty():
		result.import = {"adapter": Indexed.ADAPTER, "operation": labels.indexedOperation, "nativeBoardSize": [canvas.x, canvas.y], "palette": {"id": palette.id, "file": palette_path, "sha256": palette.sha256, "colors": palette.colors.size()}, "backgroundPixelsRemoved": keyed_pixels, "stats": indexed_stats}
	if not contract.is_empty():
		result["contract"] = {"bible": bible_path, "bibleSha256": FileAccess.get_sha256(bible_path), "pass": contract.pass, "allowedFailure": not contract.pass, "slots": contract.slots}
	var recipe := _recipe(options)
	if not recipe.is_empty():
		result["recipe"] = recipe
	# Nothing is written before the contract gate above.
	for directory: String in config.outputDirs:
		DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(base + directory))
	result.import["normalizedBoard"] = _save(base, board, files.normalizedBoard, false)
	if result.import.normalizedBoard.is_empty():
		return 1
	var replacements: Dictionary = {}
	for slot: Dictionary in layout.slots:
		var crop := Rect2i(int(slot.imageRect[0]), int(slot.imageRect[1]), int(slot.imageRect[2]), int(slot.imageRect[3]))
		var cell := Rect2i(int(slot.cell[0]), int(slot.cell[1]), int(slot.cell[2]), int(slot.cell[3]))
		var replacement := board.get_region(crop)
		var original := Image.load_from_file(template_base + slot.sourceFile)
		if original.get_size() != replacement.get_size():
			return _fail("Changed source SPR dimensions")
		var index := int(slot.index)
		var metadata := _save(base, replacement, files.slot % index, false)
		if metadata.is_empty():
			return 1
		metadata["sourceIndex"] = index
		metadata["imageRect"] = slot.imageRect
		metadata["cell"] = slot.cell
		result.body[str(index)] = metadata
		var diagnostic := _alpha_overlap(original, replacement)
		diagnostic["visiblePixelsOutsideFixedCrop"] = _visible_pixels(board.get_region(cell)) - _visible_pixels(replacement)
		diagnostic["uniqueColors"] = Indexed.unique_colors(replacement)
		diagnostic["nativeUniqueColors"] = Indexed.unique_colors(original)
		if not palette_path.is_empty():
			diagnostic.merge(Indexed.validate(replacement, palette))
			if diagnostic.offPalettePixels != 0 or diagnostic.keyTintedPixels != 0 or diagnostic.partialAlphaPixels != 0:
				return _fail("Indexed slot %d is not clean" % index)
		result.diagnostics[str(index)] = diagnostic
		replacements[index] = ImageTexture.create_from_image(replacement)
		print("SPR %d alphaIoU %.6f; outside fixed crop: %d pixels; colors %d (native %d)" % [index, diagnostic.alphaIoU, diagnostic.visiblePixelsOutsideFixedCrop, diagnostic.uniqueColors, diagnostic.nativeUniqueColors])
	var scene := Node3D.new()
	tree.root.add_child(scene)
	var actor := Actor.new()
	scene.add_child(actor)
	actor.configure(config.actorKind)
	actor.set_process(false)
	actor.direction = direction
	actor.weapon_visible = true
	var source_parts: Array = [actor._body, actor._head, actor._weapon, actor._trail]
	var before := _fingerprint_list(source_parts, config.partNames)
	var original_body: Dictionary = actor._body
	actor._body = original_body.duplicate(true)
	for index: int in replacements:
		actor._body.textures[index] = replacements[index]
	# This process owns these caches. It must not reuse native compositions made
	# while configure() established the neutral foot anchor.
	Actor._frame_cache.clear()
	Actor._image_cache.clear()
	actor._current_key = ""
	var contact_rules: Dictionary = config.contact
	var cell_size := int(contact_rules.cell)
	var columns := int(contact_rules.columns)
	var contact := Image.create(int(contact_rules.size[0]), int(contact_rules.size[1]), false, Image.FORMAT_RGBA8)
	var contact_frames := 0
	for entry: Dictionary in config.states:
		var state_name: String = entry.state
		actor.set_state(state_name)
		var action: Dictionary = actor._get_action(actor._body, state_name, direction)
		var count: int = action.frames.size() if str(entry.frames) == "all" else int(entry.frames)
		var frames: Array = []
		for i in count:
			actor._clock = i * maxf(0.024, action.delay) + 0.000001
			actor._render_frame()
			var composite: Image = actor._sprite.texture.get_image()
			var metadata := _save(base, composite, files.frame % [state_name, i], false)
			if metadata.is_empty():
				return 1
			metadata["sourceFrame"] = i
			metadata["durationMs"] = action.delay * 1000
			frames.append(metadata)
			if entry.get("contact", false):
				contact.blit_rect(composite, Rect2i(0, 0, cell_size, cell_size), Vector2i(i % columns * cell_size, int(i / columns) * cell_size))
				contact_frames += 1
		result.sequences[state_name] = {"sourceAction": Actor.CHARACTER_GROUPS[state_name] * 8 + direction, "frameDurationMs": action.delay * 1000, "durationMs": count * action.delay * 1000, "frames": frames}
	result["contactBoard"] = _save(base, contact, files.contact, false)
	contact.resize(int(contact_rules.scaled[0]), int(contact_rules.scaled[1]), Image.INTERPOLATE_NEAREST)
	result["contactBoard3x"] = _save(base, contact, files.contact3x, false)
	var after := _fingerprint_list([actor._body, actor._head, actor._weapon, actor._trail], config.partNames)
	if before != after:
		return _fail("Original ACT data changed during replacement import")
	if _fingerprint_list(source_parts, config.partNames) != before:
		return _fail("Cached source ACT data changed")
	var expected: Dictionary = config.expectedSequence
	var body_sequence: Array = []
	for frame: Dictionary in actor._get_action(actor._body, expected.state, direction).frames:
		body_sequence.append(frame.layers[0].index)
	if body_sequence != _ints(expected.slots):
		return _fail("Unexpected native body sequence %s" % [body_sequence])
	for index: int in replacements:
		if original_body.textures[index] == replacements[index]:
			return _fail("Cached original bitmap was overwritten")
	result["verification"] = {"originalActionsSha256": before, "afterReplacementActionsSha256": after, "allACTDataUnchanged": true, "cachedSourceACTDataUnchanged": true, "sourceBitmapsRetained": true, "allReplacementDimensionsMatchSource": true, "bodyAttackIndexSequence": body_sequence, "allSourceFileHashesMatchTemplate": true}
	for key: String in config.get("verificationExtras", {}):
		result.verification[key] = _ints(config.verificationExtras[key])
	for source_path: String in template.sourceFiles:
		if FileAccess.get_sha256(source_path) != template.sourceFiles[source_path]:
			return _fail("Original source file changed")
	if not _write_json(base + config.manifest, result):
		return 1
	print(str(labels.done).format({"slots": replacements.size(), "frames": contact_frames}))
	return 0


static func _fingerprint_list(parts: Array, names: Array) -> Dictionary:
	var hashes := {}
	for i in parts.size():
		hashes[names[i]] = JSON.stringify(parts[i].actions).sha256_text()
	return hashes


static func _fingerprints(parts: Dictionary) -> Dictionary:
	var result := {}
	for name: String in parts:
		result[name] = JSON.stringify(parts[name].actions).sha256_text()
	return result


static func _run_head(tree: SceneTree, config: Dictionary, options: Dictionary) -> int:
	var template_dir: String = config.templateDir
	var equipment_dir: String = config.equipmentDir
	var base := _dir(options.get("output-dir", config.defaultOutputDir))
	var costume_dir := _dir(options.get("costume", config.defaultCostume))
	var source: String = options.get("source", base + config.defaultSource)
	var palette_path: String = options.get("palette", "")
	var bible_path: String = options.get("style-bible", "")
	var allow_failure: bool = options.has("allow-contract-failure")
	var files: Dictionary = config.files
	var view := int(config.direction)
	var state_name: String = config.state
	var contract := {}
	var layout: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(config.layout))
	var template: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(template_dir + "template.json"))
	var costume: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(costume_dir + "costume.json"))
	var equipment: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(equipment_dir + "equipment.json"))
	var board := Image.load_from_file(source)
	if board == null:
		return _fail("Generated head board missing")
	var source_size := board.get_size()
	var canvas := Vector2i(int(layout.canvas[0]), int(layout.canvas[1]))
	var head_index := int(layout.index)
	var keyed_pixels := 0
	var bible := {}
	if not bible_path.is_empty():
		bible = Gate.load_bible(bible_path)
		if bible.is_empty():
			return _fail("Style bible unusable")
		palette_path = bible.palette.file
	var palette := {}
	var indexed_stats := {}
	if not palette_path.is_empty():
		palette = Indexed.load_palette(palette_path)
		if palette.is_empty():
			return _fail("Style palette missing")
		var imported: Dictionary = Indexed.import_board(board, canvas, palette)
		board = imported.image
		indexed_stats = imported.stats
		keyed_pixels = board.get_width() * board.get_height() - _visible_pixels(board)
		if not bible.is_empty():
			contract = Gate.gate(config.part, bible, board, "")
			for index: String in contract.slots:
				for failure: String in contract.slots[index].failures:
					print("CONTRACT %s SPR %s: %s" % [config.part, index, failure])
			if not contract.pass and not allow_failure:
				return _fail("Candidate fails the style bible slot contract; nothing was written. Regenerate, or pass --allow-contract-failure for a study pack.")
	else:
		keyed_pixels = _legacy_normalize(board, canvas, config.legacyKey)
	var crop := Rect2i(int(layout.imageRect[0]), int(layout.imageRect[1]), int(layout.imageRect[2]), int(layout.imageRect[3]))
	var replacement := board.get_region(crop)
	var native_path: String = template_dir + (config.nativeImage % head_index)
	var original := Image.load_from_file(native_path)
	if original.get_size() != replacement.get_size():
		return _fail("Changed native head SPR dimensions")
	var head_metadata := _save(base, replacement, files.slot % head_index, true)
	if head_metadata.is_empty():
		return 1
	head_metadata["sourceIndex"] = head_index
	head_metadata["imageRect"] = layout.imageRect
	var diagnostic := _alpha_overlap(original, replacement)
	diagnostic["visiblePixelsOutsideFixedCrop"] = _visible_pixels(board) - _visible_pixels(replacement)
	diagnostic["uniqueColors"] = Indexed.unique_colors(replacement)
	diagnostic["nativeUniqueColors"] = Indexed.unique_colors(original)
	if not palette_path.is_empty():
		diagnostic.merge(Indexed.validate(replacement, palette))
		if diagnostic.offPalettePixels != 0 or diagnostic.keyTintedPixels != 0 or diagnostic.partialAlphaPixels != 0:
			return _fail("Indexed head is not clean")
	var labels: Dictionary = config.labels
	var crop_text := "[%d,%d,%d,%d]" % [crop.position.x, crop.position.y, crop.size.x, crop.size.y]
	var canvas_text := "%dx%d" % [canvas.x, canvas.y]
	var output := {
		"schemaVersion": 1, "name": str(labels.name).format({"character": _character(config, options)}), "sourceImage": source.trim_prefix(base) if source.begins_with(base) else source, "sourceImageSha256": FileAccess.get_sha256(source), "sourceImageSize": [source_size.x, source_size.y],
		"sourceDirection": view, "sourceHeadIndex": head_index, "originalTemplate": template_dir + "template.json", "originalTemplateSha256": FileAccess.get_sha256(template_dir + "template.json"), "costumeManifest": costume_dir + "costume.json", "costumeManifestSha256": FileAccess.get_sha256(costume_dir + "costume.json"), "equipmentManifestSha256": FileAccess.get_sha256(equipment_dir + "equipment.json"), "slotMetadataSha256": FileAccess.get_sha256(config.layout),
		"import": {"operation": str(labels.legacyOperation).format({"canvas": canvas_text, "crop": crop_text}), "nativeBoardSize": [canvas.x, canvas.y], "backgroundKey": config.legacyKey.text, "backgroundPixelsRemoved": keyed_pixels, "normalizedBoard": _save(base, board, files.normalizedBoard, true)},
		"head": {str(head_index): head_metadata}, "diagnostics": {str(head_index): diagnostic}, "sequences": {}, "sourceFiles": {},
		"limits": labels.limits.duplicate(),
	}
	if not palette_path.is_empty():
		output.import = {"adapter": Indexed.ADAPTER, "operation": str(labels.indexedOperation).format({"canvas": canvas_text, "crop": crop_text}), "nativeBoardSize": [canvas.x, canvas.y], "palette": {"id": palette.id, "file": palette_path, "sha256": palette.sha256, "colors": palette.colors.size()}, "backgroundPixelsRemoved": keyed_pixels, "stats": indexed_stats, "normalizedBoard": output.import.normalizedBoard}
	if not contract.is_empty():
		output["contract"] = {"bible": bible_path, "bibleSha256": FileAccess.get_sha256(bible_path), "pass": contract.pass, "allowedFailure": not contract.pass, "slots": contract.slots}
	var recipe := _recipe(options)
	if not recipe.is_empty():
		output["recipe"] = recipe
	var actor := Actor.new()
	tree.root.add_child(actor)
	actor.configure(config.actorKind)
	actor.set_process(false)
	actor.direction = view
	var source_parts := {"body": actor._body, "head": actor._head, "weapon": actor._weapon, "trail": actor._trail}
	var variants: Array = config.variants
	for gear: String in variants:
		if gear == "none":
			continue
		source_parts[gear] = SpriteData.load_pair(equipment_dir + "source/" + gear)
		if source_parts[gear].is_empty():
			return _fail("Native headgear missing")
		source_parts[gear]["source"] = equipment_dir + "source/" + gear
	var before := _fingerprints(source_parts)
	var body: Dictionary = actor._body.duplicate(true)
	for index: String in costume.body:
		var metadata: Dictionary = costume.body[index]
		var image := Image.load_from_file(costume_dir + metadata.file)
		if image.get_size() != body.textures[int(index)].get_image().get_size():
			return _fail("Costume bitmap %s does not fit its native slot" % index)
		if FileAccess.get_sha256(costume_dir + metadata.file) != metadata.sha256:
			return _fail("Wayfarer body bitmap changed")
		body.textures[int(index)] = ImageTexture.create_from_image(image)
	var head: Dictionary = actor._head.duplicate(true)
	head.textures[head_index] = ImageTexture.create_from_image(replacement)
	# configure() may have cached original raw images. These fixtures must sample
	# the new textures under the same source identities and unchanged ACT records.
	Actor._image_cache.clear()
	Actor._frame_cache.clear()
	var action: Dictionary = actor._get_action(body, state_name, view)
	var head_action: Dictionary = actor._get_action(head, state_name, view)
	var weapon_action: Dictionary = actor._get_action(actor._weapon, state_name, view)
	var trail_action: Dictionary = actor._get_action(actor._trail, state_name, view)
	if action.frames.size() != int(config.expectedFrames):
		return _fail("Unexpected native action length %d" % action.frames.size())
	var contact_rules: Dictionary = config.contact
	var cell_size := int(contact_rules.cell)
	var columns := int(contact_rules.columns)
	var source_action: int = Actor.CHARACTER_GROUPS[state_name] * 8 + view
	for gear: String in variants:
		var board_image := Image.create(int(contact_rules.size[0]), int(contact_rules.size[1]), false, Image.FORMAT_RGBA8)
		var frames: Array = []
		for i in action.frames.size():
			var body_frame: Dictionary = action.frames[i]
			var head_frame: Dictionary = head_action.frames[i % head_action.frames.size()]
			var image := Image.create(cell_size, cell_size, false, Image.FORMAT_RGBA8)
			actor._draw_part(image, body, body_frame, Vector2.ZERO)
			actor._draw_part(image, head, head_frame, actor._attachment(body_frame, head_frame))
			if gear != "none":
				var gear_action: Dictionary = actor._get_action(source_parts[gear], state_name, view)
				var gear_frame: Dictionary = gear_action.frames[i % gear_action.frames.size()]
				actor._draw_part(image, source_parts[gear], gear_frame, actor._attachment(body_frame, gear_frame))
			actor._draw_part(image, actor._weapon, weapon_action.frames[i % weapon_action.frames.size()], Vector2.ZERO)
			actor._draw_part(image, actor._trail, trail_action.frames[i % trail_action.frames.size()], Vector2.ZERO)
			var metadata := _save(base, image, files.frame % [gear, i], true)
			if metadata.is_empty():
				return 1
			metadata["sourceFrame"] = i
			metadata["durationMs"] = action.delay * 1000
			frames.append(metadata)
			board_image.blit_rect(image, Rect2i(0, 0, cell_size, cell_size), Vector2i(i % columns * cell_size, int(i / columns) * cell_size))
		var contact := _save(base, board_image, files.contact % gear, true)
		board_image.resize(int(contact_rules.scaled[0]), int(contact_rules.scaled[1]), Image.INTERPOLATE_NEAREST)
		output.sequences[gear] = {"sourceAction": source_action, "frameDurationMs": action.delay * 1000, "durationMs": action.frames.size() * action.delay * 1000, "frames": frames, "contactBoard": contact, "contactBoard3x": _save(base, board_image, files.contact3x % gear, true)}
	var replacement_parts := source_parts.duplicate()
	replacement_parts.body = body
	replacement_parts.head = head
	var after := _fingerprints(replacement_parts)
	if before != after:
		return _fail("Original ACT changed")
	if _fingerprints(source_parts) != before:
		return _fail("Cached native ACT changed")
	if source_parts.head.textures[head_index] == head.textures[head_index]:
		return _fail("Cached native head overwritten")
	output.sourceFiles.merge(template.sourceFiles)
	output.sourceFiles.merge(equipment.sourceFiles)
	for source_path: String in output.sourceFiles:
		if FileAccess.get_sha256(source_path) != output.sourceFiles[source_path]:
			return _fail("Original source file changed")
	output["verification"] = {"originalActionsSha256": before, "afterReplacementActionsSha256": after, "allACTDataUnchanged": true, "cachedSourceACTDataUnchanged": true, "sourceBitmapsRetained": true, "allReplacementDimensionsMatchSource": true, "allSourceFileHashesMatchTemplate": true, "headgearVariants": variants.duplicate(), "originalHeadSha256": FileAccess.get_sha256(native_path)}
	for key: String in config.get("verificationExtras", {}):
		var value: Variant = config.verificationExtras[key]
		output.verification[key] = _ints(value) if value is Array else int(value)
	if not _write_json(base + config.manifest, output):
		return 1
	print(str(labels.done).format({"size": "%dx%d" % [replacement.get_width(), replacement.get_height()], "fixtures": variants.size() * action.frames.size(), "iou": "%.6f" % diagnostic.alphaIoU, "outside": diagnostic.visiblePixelsOutsideFixedCrop}))
	return 0
