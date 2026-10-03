extends RefCounted
## Generation boards for any set of native SPR drawings (inspection B7/D14, 2026-10-02).
## A board spec selects drawings either by action groups seen from one raw view
## ("view" + "groups") or as an explicit slot list ("slots"). Every slot keeps its
## own raw facing and role, so one board may hold idle + walk drawings of a view,
## or the five head views. Writes, into one new folder:
##   slot-board.png / slot-board-<scale>x.png   native and enlarged edit target (magenta)
##   design-reference-<n>.png                     design images from the character spec
##   context-frames.png                           the drawings in play: body + anchored head
##   sprite-slots.json                            layout, slot facings, fixture plan, sources
##   prompt.txt, HOWTO.txt, candidates/
## Used by export_boards.gd. The older export_slot_board.gd stays as written for the
## saved attack2 back-view board.
const SpriteData = preload("res://scripts/ro_sprite_data.gd")
const Contract = preload("res://tools/character-lab/slot_contract.gd")
const Gate = preload("res://tools/character-lab/verify_candidate.gd")
const DIRECTIONS := ["S", "SW", "W", "NW", "N", "NE", "E", "SE"]
const DEFAULT_LAYOUTS := {
	"body": {"scale": 5, "minCell": 96, "margin": 8, "placement": "bottom", "columns": 3, "defaultHeadgear": ["none"]},
	"head": {"scale": 10, "minCell": 48, "margin": 6, "placement": "center", "columns": 3, "defaultHeadgear": ["none", "cap", "hat"]},
}
const CONTEXT_PREFERENCE := ["walk", "idle", "ready", "attack2"]


static func _json(path: String) -> Variant:
	return JSON.parse_string(FileAccess.get_file_as_string(path)) if FileAccess.file_exists(path) else null


static func _save(image: Image, path: String) -> Dictionary:
	if image.save_png(path) != OK:
		return {}
	return {"file": path.get_file(), "width": image.get_width(), "height": image.get_height(), "sha256": FileAccess.get_sha256(path)}


static func _write_text(path: String, text: String) -> bool:
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return false
	file.store_string(text)
	file.close()
	return true


static func _fail(message: String) -> Dictionary:
	return {"ok": false, "error": message}


## Directions that show this group with this view's drawings (the view's own and its mirrors).
static func _directions_using(entry: Dictionary, slots: Array) -> Array:
	var result := []
	for d in 8:
		for index in entry.byDirection[d]:
			if slots.has(int(index)):
				result.append(DIRECTIONS[d])
				break
	return result


## For every slot: where it is used ({group, direction, frame, mirror}) in the given groups.
static func _usage(data: Dictionary, group_names: Array, groups: Array, slots: Array) -> Dictionary:
	var usage := {}
	for index in slots:
		usage[int(index)] = []
	for name in groups:
		var gi: int = group_names.find(name)
		if gi < 0:
			continue
		for d in 8:
			var action_index := gi * 8 + d
			if action_index >= data.actions.size():
				continue
			var frames: Array = data.actions[action_index].frames
			for i in frames.size():
				for layer: Dictionary in frames[i].layers:
					if usage.has(int(layer.index)):
						usage[int(layer.index)].append({"group": name, "direction": DIRECTIONS[d], "frame": i, "frames": frames.size(), "mirror": bool(layer.mirror)})
	return usage


## Raw facing from the first group (walk, idle, ready, attack2, then the board's own) that
## shows the drawing unmirrored. Idle head-turn frames reuse neighbouring head views,
## so a union over all groups would mislabel the straight front head as three-quarter.
static func _raw_facing(uses: Array, groups: Array) -> Array:
	var order: Array = CONTEXT_PREFERENCE.duplicate()
	for name in groups:
		if not order.has(name):
			order.append(name)
	for name in order:
		var raw := []
		for use: Dictionary in uses:
			if use.group == name and not use.mirror and not raw.has(use.direction):
				raw.append(use.direction)
		if not raw.is_empty():
			return raw
	return []


static func _roles(uses: Array, groups: Array) -> Array:
	var roles := []
	for name in groups:
		var frames := []
		var count := 0
		for use: Dictionary in uses:
			if use.group == name and not use.mirror and not frames.has(int(use.frame) + 1):
				frames.append(int(use.frame) + 1)
				count = int(use.frames)
		if frames.is_empty():
			continue
		frames.sort()
		roles.append("%s frame %s of %d" % [name, ", ".join(frames.map(func(f: int) -> String: return str(f))), count])
	return roles


static func facing_words(raw: Array) -> String:
	if raw.has("S") and raw.size() == 1:
		return "straight TOWARD the camera (front view)"
	if raw.has("S") or raw.has("SW"):
		return "screen-LEFT, turned TOWARD the camera (front three-quarter view)"
	if raw.has("N") and raw.size() == 1:
		return "straight AWAY from the camera (back view: only the back is visible)"
	if raw.has("NW"):
		return "screen-LEFT, turned AWAY from the camera (back three-quarter view: mostly the back and the left side)"
	if raw.has("W"):
		return "screen-LEFT in profile (side view)"
	return "the direction shown in the context frames"


static func is_back(raw: Array) -> bool:
	return raw.has("NW") or (raw.has("N") and not raw.has("S"))


static func export_board(spec: Dictionary, plan: Dictionary, out: String, actor: Node) -> Dictionary:
	var part: String = spec.get("part", "body")
	var inventory: Variant = _json(plan.inventory)
	if not inventory is Dictionary or not inventory.parts.has(part):
		return _fail("Slot inventory %s has no part %s; run export_slot_inventory.gd first" % [plan.inventory, part])
	var part_inventory: Dictionary = inventory.parts[part]
	var group_names: Array = inventory.groups
	var source: String = part_inventory.source
	var data: Dictionary = SpriteData.load_pair(source)
	if data.is_empty():
		return _fail("Native source missing: " + source)
	data["source"] = source
	var character_path: String = spec.get("character", "")
	var character: Variant = _json(character_path)
	if not character is Dictionary:
		return _fail("Character spec missing: " + character_path)
	var part_spec: Dictionary = character.get("parts", {}).get(part, {})
	var bible_path: String = spec.get("styleBible", character.get("styleBible", plan.get("styleBible", "")))
	var bible := Gate.load_bible(bible_path)
	if bible.is_empty() or not bible.slotRules.has(part):
		return _fail("Style bible unusable for %s: %s" % [part, bible_path])
	# Slot selection.
	var groups: Array = spec.get("groups", [])
	var slots: Array = []
	if spec.has("slots"):
		for index in spec.slots:
			slots.append(int(index))
		if groups.is_empty():
			groups = CONTEXT_PREFERENCE.filter(func(name: String) -> bool: return group_names.has(name))
	else:
		var view := DIRECTIONS.find(str(spec.get("view", "")))
		if view < 0 or groups.is_empty():
			return _fail("Board %s needs \"slots\" or a \"view\" (S..SE) with \"groups\"" % spec.get("id", "?"))
		for name in groups:
			if not part_inventory.groups.has(name):
				return _fail("Unknown action group " + str(name))
			for index in part_inventory.groups[name].byDirection[view]:
				if not slots.has(int(index)):
					slots.append(int(index))
	for index in spec.get("exclude", []):
		slots.erase(int(index))
	if slots.is_empty():
		return _fail("Board %s selects no drawings" % spec.get("id", "?"))
	for index in slots:
		if index < 0 or index >= data.textures.size():
			return _fail("SPR %d does not exist in %s" % [index, source])
	var usage := _usage(data, group_names, groups, slots)
	# Layout: same placement rule as the accepted boards.
	var layout_rules: Dictionary = DEFAULT_LAYOUTS.get(part, DEFAULT_LAYOUTS.body).duplicate()
	layout_rules.merge(plan.get("layouts", {}).get(part, {}), true)
	# Per-board override, e.g. {"minCell": 64, "scale": 16} for one head on the classic 64x64 head board geometry.
	layout_rules.merge(spec.get("layout", {}), true)
	var scale := int(layout_rules.scale)
	var margin := int(layout_rules.margin)
	var widest := 0
	var tallest := 0
	for index in slots:
		widest = maxi(widest, data.textures[index].get_width())
		tallest = maxi(tallest, data.textures[index].get_height())
	var min_cell := int(layout_rules.minCell)
	var cell := Vector2i(maxi(min_cell, ceili((widest + 2 * margin) / 8.0) * 8), maxi(min_cell, ceili((tallest + 2 * margin) / 8.0) * 8))
	var columns := mini(int(layout_rules.columns), slots.size())
	var rows := ceili(slots.size() / float(columns))
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out + "sprites/" + part))
	var board := Image.create(columns * cell.x, rows * cell.y, false, Image.FORMAT_RGBA8)
	board.fill(Color("ff00ff"))
	var layout_slots := []
	var natives := {}
	for i in slots.size():
		var index: int = slots[i]
		var raw: Image = data.textures[index].get_image()
		raw.convert(Image.FORMAT_RGBA8)
		natives[index] = raw
		var origin := Vector2i(i % columns * cell.x, i / columns * cell.y)
		var top_left := origin + Vector2i(floori((cell.x - raw.get_width()) / 2.0), cell.y - margin - raw.get_height())
		if layout_rules.placement == "center":
			top_left.y = origin.y + floori((cell.y - raw.get_height()) / 2.0)
		board.blend_rect(raw, Rect2i(Vector2i.ZERO, raw.get_size()), top_left)
		var sprite := _save(raw, out + "sprites/%s/%03d.png" % [part, index])
		if sprite.is_empty():
			return _fail("Cannot write " + out)
		var uses: Array = usage[index]
		layout_slots.append({"part": part, "index": index, "cell": [origin.x, origin.y, cell.x, cell.y], "imageRect": [top_left.x, top_left.y, raw.get_width(), raw.get_height()],
			"sourceFile": "sprites/%s/%03d.png" % [part, index], "sourceSha256": sprite.sha256, "rawFacing": _raw_facing(uses, groups), "roles": _roles(uses, groups)})
	var native_board := _save(board, out + "slot-board.png")
	var enlarged := board.duplicate()
	enlarged.resize(board.get_width() * scale, board.get_height() * scale, Image.INTERPOLATE_NEAREST)
	var enlarged_board := _save(enlarged, out + "slot-board-%dx.png" % scale)
	if native_board.is_empty() or enlarged_board.is_empty():
		return _fail("Cannot write the slot board images in " + out)
	# Fixture plan: every direction that shows these drawings, per group.
	var fixtures := []
	var headgear: Array = spec.get("fixtureHeadgear", layout_rules.defaultHeadgear)
	for name in groups:
		if not part_inventory.groups.has(name):
			continue
		var directions := _directions_using(part_inventory.groups[name], slots)
		if not directions.is_empty():
			fixtures.append({"group": name, "groupIndex": group_names.find(name), "directions": directions, "headgear": headgear})
	# Context: how the drawings play, always as a body with its head attached at the ACT anchor.
	var pairs := []
	if spec.has("slots"):
		for index in slots:
			for name in CONTEXT_PREFERENCE:
				var found := false
				for use: Dictionary in usage[index]:
					if use.group == name and not use.mirror:
						var pair := [name, DIRECTIONS.find(use.direction)]
						if not pairs.has(pair):
							pairs.append(pair)
						found = true
						break
				if found:
					break
	else:
		for name in groups:
			pairs.append([name, DIRECTIONS.find(str(spec.view))])
	var context := _context(pairs, group_names, data, part, actor)
	if context == null:
		return _fail("No context frames for board %s" % spec.get("id", "?"))
	var context_record := _save(context, out + "context-frames.png")
	if context_record.is_empty():
		return _fail("Cannot write " + out + "context-frames.png")
	# Design references from the character spec.
	var references := []
	var entries: Array = part_spec.get("designReferences", [])
	if entries.is_empty() and part_spec.has("designReference"):
		entries = [{"file": part_spec.designReference, "role": part_spec.get("designReferenceNote", "design reference")}]
	for k in entries.size():
		var entry: Dictionary = entries[k]
		if not FileAccess.file_exists(entry.file):
			return _fail("Design reference missing: " + str(entry.file))
		var design := Image.load_from_file(entry.file)
		if design == null:
			return _fail("Design reference unreadable: " + str(entry.file))
		if design.get_width() < 600:
			var factor := ceili(600.0 / design.get_width())
			design.resize(design.get_width() * factor, design.get_height() * factor, Image.INTERPOLATE_NEAREST)
		var record := _save(design, out + "design-reference-%d.png" % (k + 1))
		if record.is_empty():
			return _fail("Cannot write " + out + "design-reference-%d.png" % (k + 1))
		record["from"] = entry.file
		record["fromSha256"] = FileAccess.get_sha256(entry.file)
		record["role"] = entry.get("role", "")
		references.append(record)
	var view_directions := []
	var raw_all := []
	for fixture: Dictionary in fixtures:
		for name in fixture.directions:
			if not view_directions.has(name):
				view_directions.append(name)
	for slot: Dictionary in layout_slots:
		for name in slot.rawFacing:
			if not raw_all.has(name):
				raw_all.append(name)
	var group_sequences := {}
	for name in groups:
		var gi: int = group_names.find(name)
		var per := {}
		for d in 8:
			var action: Dictionary = data.actions[gi * 8 + d]
			var sequence := []
			var mirrored := false
			var relevant := false
			for frame: Dictionary in action.frames:
				for layer: Dictionary in frame.layers:
					if int(layer.index) >= 0:
						sequence.append(int(layer.index))
						mirrored = mirrored or bool(layer.mirror)
						relevant = relevant or slots.has(int(layer.index))
			if relevant:
				# Fixtures and play follow the BODY timeline (the head repeats its frames modulo),
				# so the body's frame count and delay are recorded for head boards too.
				var body_action: Dictionary = (data if part == "body" else actor._body).actions[gi * 8 + d]
				per[DIRECTIONS[d]] = {"slots": sequence, "mirrored": mirrored, "delayMs": action.delay * 1000, "frames": action.frames.size(),
					"bodyFrames": body_action.frames.size(), "bodyDelayMs": body_action.delay * 1000}
		group_sequences[name] = per
	var layout := {
		"schemaVersion": 2, "kind": "slot-board", "id": spec.get("id", out.trim_suffix("/").get_file()), "label": spec.get("label", "%s %s" % [character.get("label", ""), part]),
		"job": plan.job, "part": part, "groups": groups, "group": groups[0], "groupIndex": group_names.find(groups[0]),
		"view": {"directions": view_directions, "rawFacing": raw_all, "contextDirection": DIRECTIONS[pairs[0][1]] if not pairs.is_empty() else ""},
		"nativeSource": source, "sourceFiles": {source + ".act": FileAccess.get_sha256(source + ".act"), source + ".spr": FileAccess.get_sha256(source + ".spr")},
		"groupSequences": group_sequences, "fixtures": fixtures,
		"canvas": [board.get_width(), board.get_height()], "enlargedCanvas": [enlarged.get_width(), enlarged.get_height()], "scale": scale,
		"background": "#FF00FF", "cellSize": [cell.x, cell.y], "layout": [columns, rows],
		"placement": ("Raw SPR images centred in each cell." if layout_rules.placement == "center" else "Raw SPR images centred horizontally in each cell, bitmap bottom %d px above the cell edge." % margin) + " No rotation, mirror, scaling or ACT composition.",
		"boards": {"native": native_board, "enlarged": enlarged_board, "context": context_record, "designReferences": references},
		"character": character_path, "characterSha256": FileAccess.get_sha256(character_path), "styleBible": bible_path, "styleBibleSha256": FileAccess.get_sha256(bible_path),
		"inventory": plan.inventory, "plan": plan.get("id", ""), "slots": layout_slots,
	}
	if not _write_text(out + "sprite-slots.json", JSON.stringify(layout, "\t") + "\n"):
		return _fail("Cannot write " + out + "sprite-slots.json")
	var prompt := build_prompt(layout, character, part_spec, bible, natives)
	if not _write_text(out + "prompt.txt", prompt + "\n") or not _write_text(out + "HOWTO.txt", howto(layout, out)):
		return _fail("Cannot write prompt.txt / HOWTO.txt in " + out)
	if DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out + "candidates")) != OK:
		return _fail("Cannot create " + out + "candidates")
	return {"ok": true, "summary": "%s: %s %s SPR %s, %dx%d cells, %d design reference(s) -> %s" % [layout.id, character.get("label", "?"), part, slots, cell.x, cell.y, references.size(), out]}


## One row per (group, direction): native body frames with the head attached at the ACT anchor.
static func _context(pairs: Array, group_names: Array, data: Dictionary, part: String, actor: Node) -> Image:
	if pairs.is_empty():
		return null
	var body: Dictionary = data if part == "body" else actor._body
	var head: Dictionary = data if part == "head" else actor._head
	var rows := []
	var used := Rect2i()
	for pair: Array in pairs:
		var gi: int = group_names.find(pair[0])
		var action: Dictionary = body.actions[gi * 8 + int(pair[1])]
		var frames := []
		for i in action.frames.size():
			var canvas := Image.create(192, 192, false, Image.FORMAT_RGBA8)
			var body_frame: Dictionary = action.frames[i]
			actor._draw_part(canvas, body, body_frame, Vector2.ZERO)
			if not head.is_empty():
				var head_action: Dictionary = head.actions[gi * 8 + int(pair[1])]
				var head_frame: Dictionary = head_action.frames[i % head_action.frames.size()]
				actor._draw_part(canvas, head, head_frame, actor._attachment(body_frame, head_frame))
			var r := canvas.get_used_rect()
			if r.size != Vector2i.ZERO:
				used = r if used.size == Vector2i.ZERO else used.merge(r)
			frames.append(canvas)
		rows.append(frames)
	used = used.grow(6).intersection(Rect2i(0, 0, 192, 192))
	var longest := 0
	for frames: Array in rows:
		longest = maxi(longest, frames.size())
	var strip := Image.create(maxi(1, longest * used.size.x), maxi(1, rows.size() * used.size.y), false, Image.FORMAT_RGBA8)
	for r in rows.size():
		for i in rows[r].size():
			strip.blit_rect(rows[r][i], used, Vector2i(i * used.size.x, r * used.size.y))
	strip.resize(strip.get_width() * 3, strip.get_height() * 3, Image.INTERPOLATE_NEAREST)
	return strip


static func build_prompt(layout: Dictionary, character: Dictionary, spec: Dictionary, bible: Dictionary, natives: Dictionary) -> String:
	var part: String = layout.part
	var n: int = layout.slots.size()
	var label: String = character.get("label", "character")
	var lines := []
	lines.append("Use case: precise-object-edit.")
	if part == "head":
		lines.append("Asset type: native Ragnarok Online HEAD sprite replacement board for %s: %d head view(s) of one character." % [label, n])
		lines.append("Edit target image 1: a %d-column by %d-row board of %d native HEADS (face and hair only) on pure magenta, %dx%d, drawn at %dx (each logical pixel is a %dx%d block). The importer rescales the whole board and removes the magenta itself; the layout, proportions and pixel-cluster look are what must stay. Each cell is the SAME head seen from a different camera angle (listed below). KEEP every head's exact cell position, skull size, outer outline and neck attachment. No neck, collar, shoulders or body. No hat, cap, beret, ribbon, hairband or any other headgear: headgear is a separate module drawn for the native skull." % [layout.layout[0], layout.layout[1], n, layout.enlargedCanvas[0], layout.enlargedCanvas[1], layout.scale, layout.scale, layout.scale])
	else:
		lines.append("Asset type: native Ragnarok Online body sprite replacement board for %s: %d drawings (%s)." % [label, n, ", ".join(layout.groups)])
		lines.append("Edit target image 1: a %d-column by %d-row board of %d HEADLESS body sprites on pure magenta, %dx%d, drawn at %dx (each logical pixel is a %dx%d block). The importer rescales the whole board and removes the magenta itself, so a slightly different output size or soft magenta edges are acceptable; the layout, proportions and pixel-cluster look are what must stay. KEEP its exact layout, relative scale, pixel positions, all %d poses, limb angles, bare hands, feet contact, neck openings and body proportions. These are raw unmirrored SPR image slots of one animation set, not a storyboard to redesign." % [layout.layout[0], layout.layout[1], n, layout.enlargedCanvas[0], layout.enlargedCanvas[1], layout.scale, layout.scale, layout.scale, n])
	var references: Array = layout.boards.designReferences
	for k in references.size():
		lines.append("Image %d (design reference only): %s Use it only for the design (garments, colors, hair, face style); keep image 1's anatomy, angles and pixel size." % [k + 2, references[k].role])
	if part == "head":
		if spec.has("description"):
			lines.append("Primary request: replace each native head's hair and face with this SAME head: %s" % spec.description)
		if spec.has("avoid"):
			lines.append("Avoid: %s" % spec.avoid)
	else:
		if spec.has("costume"):
			lines.append("Primary request: Dress EACH image-1 body in the SAME recognizable outfit: %s. %s" % [spec.costume, spec.get("replaces", "")])
		if spec.has("avoid"):
			lines.append("Avoid: %s" % spec.avoid)
	lines.append("")
	lines.append("CELLS (left to right, then top to bottom):")
	var back := 0
	for i in n:
		var slot: Dictionary = layout.slots[i]
		var roles: Array = slot.roles
		lines.append("- cell %d, SPR %d: %s; faces %s." % [i + 1, slot.index, "; ".join(roles) if not roles.is_empty() else "drawing", facing_words(slot.rawFacing)])
		if is_back(slot.rawFacing):
			back += 1
	if back > 0 and part == "body":
		# Learned from attack2 back view v1 -> v2 (2026-09-26): bent-forward back poses got front details.
		lines.append("BACK VIEWS: every back-facing cell, including bent-forward poses, exposes the BACK and left side. Garments are seen from behind (the back of a vest or coat covers the torso). Do not turn any torso toward the viewer and do not paint front-only details (shirt opening, chest buckle, front belt buckle, lapels) onto the back. Preserve the original back neck opening.")
	if back > 0 and part == "head":
		lines.append("REAR HEADS: back-facing cells show the back of the hair; no eyes, mouth or frontal face. Keep only the cheek/ear/nape skin the native drawing shows.")
	lines.append("Mirrored directions flip asymmetric details; draw each cell as it appears from its raw facing, the game mirrors the other directions.")
	lines.append("")
	lines.append("SIZE CONTRACT per cell (checked automatically after generation; a candidate outside it is rejected, not repaired):")
	for i in n:
		var slot: Dictionary = layout.slots[i]
		var index := int(slot.index)
		var rect: Array = slot.imageRect
		lines.append("[cell %d, SPR %d]" % [i + 1, index])
		lines.append(Contract.brief(part, natives[index], Gate.slot_rules(bible, part, index), Gate.native_face(bible, part, index, natives[index]), Vector2i(int(rect[0]), int(rect[1])), int(layout.scale)).replace("SIZE CONTRACT (checked automatically after generation; a candidate outside it is rejected, not repaired):\n", ""))
	lines.append("")
	if part == "head":
		lines.append("Invariant: the same %d heads in the SAME cells, exactly registered. No bodies, necks, headgear, weapons, text, extra sprites, shadows, guides, labels or scene." % n)
		lines.append("Pixel art: native early-2000s RO head look, dark warm brown contours, small crisp clusters, restrained shaded skin, large rounded RO face where a face is visible; no smoothing, no 3D shine, no high-resolution lineart. Keep a flat #FF00FF background everywhere outside the heads. Output the same board layout and aspect ratio as image 1.")
	else:
		lines.append("Invariant: same %d complete HEADLESS drawings in the SAME cells, exactly registered. No heads, hair, headgear, weapons, text, extra sprites, shadows, guides, labels or scene." % n)
		lines.append("Pixel art: native RO body bitmap look, thin dark-brown contours, small crisp clusters, controlled subdued colors; no smoothing, no 3D, no large illustrated chibi. Keep a flat #FF00FF background everywhere outside the sprites. Output the same board layout and aspect ratio as image 1.")
	return "\n".join(lines)


static func howto(layout: Dictionary, out: String) -> String:
	var lines := ["Board %s (%s, SPR %s)" % [layout.id, layout.part, ", ".join(layout.slots.map(func(s: Dictionary) -> String: return str(s.index)))], "",
		"1. In the image generator attach, in this order:",
		"   Image 1: %s   (edit target: layout, size and poses)" % layout.boards.enlarged.file]
	var references: Array = layout.boards.designReferences
	for k in references.size():
		lines.append("   Image %d: %s   (%s)" % [k + 2, references[k].file, references[k].role])
	lines += ["2. Paste the whole of prompt.txt.",
		"3. Save the untouched result as candidates/<date>-v<N>/candidate.png in this folder (one folder per attempt; never overwrite).",
		"4. Gate (writes nothing; exit 1 = rejected; G is the Godot binary, L an absolute writable log folder):",
		"   $G --headless --log-file $L/gate.log --path . --script res://tools/character-lab/verify_candidate.gd -- --board=%s --source=<candidate>" % out,
		"5. Import into a NEW pack folder (refuses failing candidates and writes nothing then):",
		"   $G --headless --log-file $L/import.log --path . --script res://tools/character-lab/import_slot_board.gd -- --board=%s --source=<candidate> --output-dir=<new pack dir> [--fixture-look=<appearance json for the other parts>]" % out,
		"   or pin the candidate in a recipe and run tools/character-lab/art_recipe.py (see docs/character-lab/WORKFLOW.md).",
		"context-frames.png shows the native drawings in play (body with the head at its ACT anchor). Reference only.", ""]
	return "\n".join(lines)
