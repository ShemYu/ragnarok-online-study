extends SceneTree
## Generation board for ANY action group and drawn view (inspection B7/D14).
## Reads the ACT-driven slot inventory, lays out the raw SPR drawings that one
## view needs on a magenta board, and writes everything the generator and the
## importer need into one folder: board, layout, design reference, context
## frames and a prompt with the SIZE CONTRACT filled in.
##
## Godot --headless --path . --script res://tools/character-lab/export_slot_board.gd -- \
##   --group=attack2 --direction=2 [--job=swordsman-male] [--part=body] [--character=wayfarer]
## --direction picks the drawn view containing that direction (0 S,1 SW,2 W,3 NW,4 N,5 NE,6 E,7 SE).
const SpriteData = preload("res://scripts/ro_sprite_data.gd")
const Actor = preload("res://scripts/ro_sprite_actor.gd")
const Contract = preload("res://tools/character-lab/slot_contract.gd")
const Gate = preload("res://tools/character-lab/verify_candidate.gd")
const DIRECTIONS := ["S", "SW", "W", "NW", "N", "NE", "E", "SE"]
const SCALE := 5
const MARGIN := 8

func _initialize() -> void:
	call_deferred("run")

func option(name: String, fallback: String) -> String:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--%s=" % name):
			return argument.trim_prefix("--%s=" % name)
	return fallback

func save(image: Image, path: String) -> Dictionary:
	if image.save_png(path) != OK:
		push_error("Cannot save " + path)
		quit(1)
	return {"file": path.get_file(), "width": image.get_width(), "height": image.get_height(), "sha256": FileAccess.get_sha256(path)}

func run() -> void:
	var job := option("job", "swordsman-male")
	var part := option("part", "body")
	var group := option("group", "attack2")
	var direction := int(option("direction", "2"))
	var character_path := "res://tools/character-lab/characters/%s.json" % option("character", "wayfarer")
	var inventory_path := "res://tools/character-lab/assets/slot-inventory/%s.json" % job
	if not FileAccess.file_exists(inventory_path):
		push_error("Run export_slot_inventory.gd -- --job=%s first" % job)
		quit(1)
		return
	var inventory: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(inventory_path))
	var part_inventory: Dictionary = inventory.parts[part]
	var group_index: int = inventory.groups.find(group)
	var entry: Dictionary = part_inventory.groups[group]
	var view: int = int(entry.viewOfDirection[direction])
	var view_directions := []
	for d in 8:
		if int(entry.viewOfDirection[d]) == view:
			view_directions.append(d)
	var slots: Array = entry.byDirection[direction].map(func(v) -> int: return int(v))
	var data: Dictionary = SpriteData.load_pair(part_inventory.source)
	data["source"] = part_inventory.source
	# Which directions show each drawing unmirrored: that is the raw drawing's facing.
	var unmirrored := []
	var sequences := {}
	for d in view_directions:
		var action: Dictionary = data.actions[group_index * 8 + d]
		var sequence := []
		var mirrored := false
		for frame: Dictionary in action.frames:
			for layer: Dictionary in frame.layers:
				if layer.index >= 0:
					sequence.append(layer.index)
					mirrored = mirrored or layer.mirror
		sequences[DIRECTIONS[d]] = {"slots": sequence, "mirrored": mirrored, "delayMs": action.delay * 1000}
		if not mirrored:
			unmirrored.append(d)
	var shown: int = unmirrored[0] if not unmirrored.is_empty() else view_directions[0]
	var view_name := "-".join(view_directions.map(func(d: int) -> String: return DIRECTIONS[d]))
	var out := option("out", "res://tools/character-lab/assets/boards/%s-%s-%s-%s/" % [job, part, group, view_name]).trim_suffix("/") + "/"
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out + "sprites/" + part))
	# Layout: same rule as the accepted native-template board — 3 columns, cells at
	# least 96 px, bitmap centred horizontally with its bottom 8 px above the cell edge.
	var widest := 0
	var tallest := 0
	for index in slots:
		widest = maxi(widest, data.textures[int(index)].get_width())
		tallest = maxi(tallest, data.textures[int(index)].get_height())
	var cell := Vector2i(maxi(96, ceili((widest + 2 * MARGIN) / 8.0) * 8), maxi(96, ceili((tallest + 2 * MARGIN) / 8.0) * 8))
	var columns := mini(3, slots.size())
	var rows := ceili(slots.size() / float(columns))
	var board := Image.create(columns * cell.x, rows * cell.y, false, Image.FORMAT_RGBA8)
	board.fill(Color("ff00ff"))
	var layout_slots := []
	for i in slots.size():
		var index := int(slots[i])
		var raw: Image = data.textures[index].get_image()
		var origin := Vector2i(i % columns * cell.x, i / columns * cell.y)
		var top_left := origin + Vector2i(floori((cell.x - raw.get_width()) / 2.0), cell.y - MARGIN - raw.get_height())
		board.blend_rect(raw, Rect2i(Vector2i.ZERO, raw.get_size()), top_left)
		var sprite := save(raw, out + "sprites/%s/%03d.png" % [part, index])
		layout_slots.append({"part": part, "index": index, "cell": [origin.x, origin.y, cell.x, cell.y], "imageRect": [top_left.x, top_left.y, raw.get_width(), raw.get_height()], "sourceFile": "sprites/%s/%03d.png" % [part, index], "sourceSha256": sprite.sha256})
	var native_board := save(board, out + "slot-board.png")
	var enlarged := board.duplicate()
	enlarged.resize(board.get_width() * SCALE, board.get_height() * SCALE, Image.INTERPOLATE_NEAREST)
	var enlarged_board := save(enlarged, out + "slot-board-%dx.png" % SCALE)
	# Context: the composed frames of one unmirrored direction, so the reviewer
	# (and optionally the generator) sees how the drawings play in sequence.
	var actor := Actor.new()
	root.add_child(actor)
	actor.configure("swordsman" if job.begins_with("swordsman") else "novice")
	actor.set_process(false)
	var action: Dictionary = data.actions[group_index * 8 + shown]
	var frames := Image.create(action.frames.size() * 192, 192, false, Image.FORMAT_RGBA8)
	for i in action.frames.size():
		var canvas := Image.create(192, 192, false, Image.FORMAT_RGBA8)
		var body_frame: Dictionary = action.frames[i]
		actor._draw_part(canvas, data, body_frame, Vector2.ZERO)
		if part == "body" and not actor._head.is_empty():
			var head_action: Dictionary = actor._head.actions[group_index * 8 + shown]
			var head_frame: Dictionary = head_action.frames[i % head_action.frames.size()]
			actor._draw_part(canvas, actor._head, head_frame, actor._attachment(body_frame, head_frame))
		frames.blit_rect(canvas, Rect2i(0, 0, 192, 192), Vector2i(i * 192, 0))
	# Crop every frame to the union of the used area so the strip stays readable.
	var used := Rect2i()
	for i in action.frames.size():
		var r := frames.get_region(Rect2i(i * 192, 0, 192, 192)).get_used_rect()
		used = r if used.size == Vector2i.ZERO else used.merge(r)
	used = used.grow(6).intersection(Rect2i(0, 0, 192, 192))
	var strip := Image.create(action.frames.size() * used.size.x, used.size.y, false, Image.FORMAT_RGBA8)
	for i in action.frames.size():
		strip.blit_rect(frames, Rect2i(i * 192 + used.position.x, used.position.y, used.size.x, used.size.y), Vector2i(i * used.size.x, 0))
	strip.resize(strip.get_width() * 3, strip.get_height() * 3, Image.INTERPOLATE_NEAREST)
	var context := save(strip, out + "context-frames.png")
	# Design reference from the character spec, enlarged like the board.
	var character: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(character_path)) if FileAccess.file_exists(character_path) else {}
	var spec: Dictionary = character.get("parts", {}).get(part, {})
	var reference := {}
	if spec.has("designReference") and FileAccess.file_exists(spec.designReference):
		var design := Image.load_from_file(spec.designReference)
		if design.get_width() < 600:
			design.resize(design.get_width() * SCALE, design.get_height() * SCALE, Image.INTERPOLATE_NEAREST)
		reference = save(design, out + "design-reference.png")
		reference["from"] = spec.designReference
	var layout := {
		"schemaVersion": 1, "job": job, "part": part, "group": group, "groupIndex": group_index,
		"view": {"directions": view_directions.map(func(d: int) -> String: return DIRECTIONS[d]), "rawFacing": unmirrored.map(func(d: int) -> String: return DIRECTIONS[d]), "contextDirection": DIRECTIONS[shown]},
		"nativeSource": part_inventory.source, "sourceFiles": {part_inventory.source + ".act": FileAccess.get_sha256(part_inventory.source + ".act"), part_inventory.source + ".spr": FileAccess.get_sha256(part_inventory.source + ".spr")},
		"sequences": sequences, "canvas": [board.get_width(), board.get_height()], "enlargedCanvas": [enlarged.get_width(), enlarged.get_height()], "scale": SCALE,
		"background": "#FF00FF", "cellSize": [cell.x, cell.y], "layout": [columns, rows],
		"placement": "Raw SPR images centred horizontally in each cell, bitmap bottom %d px above the cell edge. No rotation, mirror, scaling or ACT composition." % MARGIN,
		"boards": {"native": native_board, "enlarged": enlarged_board, "context": context, "designReference": reference},
		"character": character_path, "slots": layout_slots,
	}
	var file := FileAccess.open(out + "sprite-slots.json", FileAccess.WRITE)
	file.store_string(JSON.stringify(layout, "\t") + "\n")
	file.close()
	var prompt := build_prompt(layout, character, spec)
	var prompt_file := FileAccess.open(out + "prompt.txt", FileAccess.WRITE)
	prompt_file.store_string(prompt + "\n")
	prompt_file.close()
	var howto := FileAccess.open(out + "HOWTO.txt", FileAccess.WRITE)
	howto.store_string("\n".join([
		"1. Open the image generator (ChatGPT). Attach, in this order:",
		"   Image 1: slot-board-%dx.png   (layout and size - the drawings to repaint)" % SCALE,
		"   Image 2: design-reference.png (the accepted clothing to match)" if not reference.is_empty() else "   (no design reference in the character spec)",
		"2. Paste the whole of prompt.txt.",
		"3. Save the untouched result into candidates/ in this folder (make 2-3; generation is random).",
		"4. Check:  Godot --headless --path . --script res://tools/character-lab/verify_candidate.gd -- --board=%s --source=<candidate>" % out,
		"5. Import: Godot --headless --path . --script res://tools/character-lab/import_slot_board.gd -- --board=%s --source=<candidate> --output-dir=<new pack dir>" % out,
		"context-frames.png shows how these drawings play in the animation (reference only; do not attach unless needed).", ""]))
	howto.close()
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out + "candidates"))
	print("Board %s: %d drawings %s, view %s (raw facing %s), %dx%d cells -> %s" % [group, slots.size(), slots, view_name, layout.view.rawFacing, cell.x, cell.y, out])
	quit()

func facing_words(raw: Array) -> String:
	if raw.has("S") or raw.has("SW"):
		return "screen-LEFT, turned TOWARD the camera (front view)"
	if raw.has("W") or raw.has("NW"):
		return "screen-LEFT, turned AWAY from the camera (back view: we mostly see the back and the left side)"
	return "the direction shown in the context frames"

func build_prompt(layout: Dictionary, character: Dictionary, spec: Dictionary) -> String:
	var bible := Gate.load_bible(character.get("styleBible", "res://tools/character-lab/style/style-bible-v1.json"))
	var rules: Dictionary = bible.slotRules[layout.part]
	var n: int = layout.slots.size()
	var lines := []
	lines.append("Use case: precise-object-edit.")
	lines.append("Asset type: native Ragnarok Online %s sprite replacement board — %s action, %s view (%s)." % [layout.part, layout.group, ", ".join(layout.view.directions), character.get("label", "character")])
	lines.append("Edit target image 1: a %d-column by %d-row board of %d HEADLESS %s sprites on pure magenta, %dx%d, every logical pixel a solid %dx%d block. KEEP its exact layout, relative scale, pixel positions, all %d poses, limb angles, bare hands, feet contact, neck openings and body proportions. These are raw unmirrored SPR image slots of one animation, played left-to-right then top-to-bottom, not a storyboard to redesign. The raw drawings face %s; keep that facing." % [layout.layout[0], layout.layout[1], n, layout.part, layout.enlargedCanvas[0], layout.enlargedCanvas[1], layout.scale, layout.scale, n, facing_words(layout.view.rawFacing)])
	if not layout.boards.designReference.is_empty():
		lines.append("Design reference image 2: the ACCEPTED %s clothing already drawn on other native poses. Match it exactly — same garments, colors, buckles, pouch and boots — seen from this view. Use ONLY the clothing design; keep image 1's anatomy." % character.get("label", "character"))
	if spec.has("costume"):
		lines.append("Primary request: Dress EACH image-1 body in the SAME recognizable outfit: %s. %s" % [spec.costume, spec.get("replaces", "")])
	lines.append("Mirrored views flip asymmetric details; draw them as they appear from this raw facing, the game mirrors other directions.")
	lines.append("")
	lines.append("SIZE CONTRACT (checked automatically after generation; a candidate outside it is rejected, not repaired):")
	var area_range: Array = rules.areaRatio
	lines.append("- Every sprite keeps %d%%-%d%% of its native opaque area and its outer edges within %d logical pixels of the native sprite; hands, feet and neck opening stay where they are." % [roundi(float(area_range[0]) * 100), roundi(float(area_range[1]) * 100), int(rules.bboxTolerance)])
	for slot: Dictionary in layout.slots:
		var r: Array = slot.imageRect
		lines.append("  - cell %d (SPR %d): sprite occupies board pixels x%d-x%d, y%d-y%d." % [layout.slots.find(slot) + 1, slot.index, int(r[0]) * layout.scale, (int(r[0]) + int(r[2])) * layout.scale - 1, int(r[1]) * layout.scale, (int(r[1]) + int(r[3])) * layout.scale - 1])
	if rules.has("outlineRatioMax"):
		lines.append("- Solid clean silhouettes (outline length at most %d%% of native): no ragged fringes, no detached specks." % roundi(float(rules.outlineRatioMax) * 100))
	lines.append("")
	lines.append("Invariant: same %d complete HEADLESS drawings in the SAME cells, exactly registered. No heads, hair, headgear, weapons, text, extra sprites, shadows, guides, labels or scene." % n)
	lines.append("Pixel art: native RO body bitmap look, thin dark-brown contours, small crisp clusters, controlled subdued colors; no smoothing, no 3D, no large illustrated chibi. Keep flat pure #FF00FF background everywhere outside the sprites. Output the same board size and layout as image 1.")
	return "\n".join(lines)
