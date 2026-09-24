extends SceneTree
## ACT-driven art budget (inspection B7): which SPR drawings a replacement
## character must supply, per part, for every action group and direction.
## Reads native ACT/SPR only; writes a JSON inventory and prints a summary.
##
## Godot --headless --path . --script res://tools/character-lab/export_slot_inventory.gd -- \
##   [--job=swordsman-male] [--out=res://tools/character-lab/assets/slot-inventory/]
const SpriteData = preload("res://scripts/ro_sprite_data.gd")
const Actor = preload("res://scripts/ro_sprite_actor.gd")
const REFERENCE := "res://assets/reference-ro/"
const EQUIPMENT := "res://tools/character-lab/assets/native-equipment-v1/source/"
# Standard RO player action groups (group * 8 + direction). The game currently
# uses the subset in Actor.CHARACTER_GROUPS; the rest are listed for completeness.
const GROUPS := ["idle", "walk", "sit", "pickup", "ready", "attack1", "hit", "freeze1", "dead", "freeze2", "attack2", "attack3", "cast"]
const DIRECTIONS := ["S", "SW", "W", "NW", "N", "NE", "E", "SE"]

func _initialize() -> void:
	call_deferred("run")

func option(name: String, fallback: String) -> String:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--%s=" % name):
			return argument.trim_prefix("--%s=" % name)
	return fallback

func run() -> void:
	var job := option("job", "swordsman-male")
	var out := option("out", "res://tools/character-lab/assets/slot-inventory/").trim_suffix("/") + "/"
	var parts := {
		"body": REFERENCE + job + "-body",
		"head": REFERENCE + "novice-male-head-1",
		"weapon": REFERENCE + job + "-dagger",
		"trail": REFERENCE + job + "-dagger-trail",
		"headgear-cap": EQUIPMENT + "cap",
		"headgear-hat": EQUIPMENT + "hat",
	}
	var used_groups := {}
	for state: String in Actor.CHARACTER_GROUPS:
		used_groups[Actor.CHARACTER_GROUPS[state]] = state
	var result := {"schemaVersion": 1, "job": job, "groups": GROUPS, "directions": DIRECTIONS, "gameUsesGroups": used_groups, "parts": {}, "sourceFiles": {}}
	print("Art budget for %s (unique SPR drawings a replacement must supply)" % job)
	print("part            actions  frames  layer refs  unique slots  game-subset slots  mirrored refs  pixels")
	for part: String in parts:
		var base: String = parts[part]
		var data: Dictionary = SpriteData.load_pair(base)
		if data.is_empty():
			push_error("Missing source pair " + base)
			continue
		for extension in [".act", ".spr"]:
			result.sourceFiles[base + extension] = FileAccess.get_sha256(base + extension)
		var all := {}
		var game := {}
		var per_group := {}
		var frames := 0
		var references := 0
		var mirrored := 0
		var mirrored_only := {}
		var unmirrored := {}
		for group in GROUPS.size():
			var group_slots := {}
			var per_direction := []
			for direction in 8:
				var index := group * 8 + direction
				var slots := {}
				if index < data.actions.size():
					for frame: Dictionary in data.actions[index].frames:
						frames += 1
						for layer: Dictionary in frame.layers:
							if layer.index < 0:
								continue
							references += 1
							slots[layer.index] = true
							group_slots[layer.index] = true
							all[layer.index] = true
							if used_groups.has(group):
								game[layer.index] = true
							if layer.mirror:
								mirrored += 1
								mirrored_only[layer.index] = true
							else:
								unmirrored[layer.index] = true
				var list := slots.keys()
				list.sort()
				per_direction.append(list)
			var group_list := group_slots.keys()
			group_list.sort()
			# Directions sharing an identical drawing set are one drawn view (the
			# others mirror it); this is how RO keeps the per-character budget small.
			var views := {}
			var view_of := []
			for list: Array in per_direction:
				var key := str(list)
				if not views.has(key):
					views[key] = views.size()
				view_of.append(views[key])
			per_group[GROUPS[group]] = {"slots": group_list, "count": group_list.size(), "byDirection": per_direction, "drawnViews": views.size(), "viewOfDirection": view_of}
		for index in unmirrored:
			mirrored_only.erase(index)
		var sizes := {}
		var pixels := 0
		for index in all:
			var size: Vector2i = data.textures[index].get_size()
			sizes[str(index)] = [size.x, size.y]
			pixels += size.x * size.y
		var all_list := all.keys()
		all_list.sort()
		var game_list := game.keys()
		game_list.sort()
		var mirrored_list := mirrored_only.keys()
		mirrored_list.sort()
		result.parts[part] = {
			"source": base, "actionCount": data.actions.size(), "sprImages": data.textures.size(),
			"frames": frames, "layerReferences": references, "mirroredReferences": mirrored,
			"uniqueSlots": all_list, "uniqueSlotCount": all_list.size(),
			"gameSubsetSlots": game_list, "gameSubsetSlotCount": game_list.size(),
			"slotsOnlyDrawnMirrored": mirrored_list, "slotSizes": sizes, "slotPixels": pixels,
			"unusedSprImages": data.textures.size() - all_list.size(), "groups": per_group,
		}
		print("%-14s  %7d  %6d  %10d  %12d  %17d  %13d  %6d" % [part, data.actions.size(), frames, references, all_list.size(), game_list.size(), mirrored, pixels])
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out))
	var file := FileAccess.open(out + job + ".json", FileAccess.WRITE)
	file.store_string(JSON.stringify(result, "\t") + "\n")
	file.close()
	var body: Dictionary = result.parts.get("body", {})
	if not body.is_empty():
		print("\nbody unique slots per action group:")
		for group: String in GROUPS:
			var entry: Dictionary = body.groups[group]
			var counts := []
			for direction in 8:
				counts.append(entry.byDirection[direction].size())
			print("  %-8s %3d drawings  %d drawn views  view per direction %s  per-direction %s%s" % [group, entry.count, entry.drawnViews, entry.viewOfDirection, counts, "   (game)" if used_groups.has(GROUPS.find(group)) else ""])
	print("\nSaved " + out + job + ".json")
	quit()
