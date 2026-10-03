extends SceneTree
## Isolated runtime check and visual fixtures for one appearance, through the game actor
## (scripts/ro_sprite_actor.gd): the same caches, attachment and frame selection as play.
## Writes only below --out-dir; never reads or writes player saves.
##
## Godot --headless --log-file <abs log> --path . --script res://tests/look_review_test.gd -- \
##   --out-dir=<new absolute folder> --appearance=res://tools/character-lab/appearances/<look>.json
##   [--states=idle,walk,ready,attack] [--headgear=none,cap,hat] [--job=swordsman]
##   [--require-complete]   fail unless every body and head drawing those states use is replaced
## Exit 0 pass, 1 failed checks, 2 unusable arguments or look (e.g. packs not installed).
const Actor = preload("res://scripts/ro_sprite_actor.gd")
const SpriteData = preload("res://scripts/ro_sprite_data.gd")
const DIRECTIONS := ["S", "SW", "W", "NW", "N", "NE", "E", "SE"]
var checks := 0
var failures: Array[String] = []

func _initialize() -> void:
	call_deferred("run")

func option(name: String, fallback: String = "") -> String:
	for argument in OS.get_cmdline_user_args():
		if argument == "--" + name:
			return "true"
		if argument.begins_with("--%s=" % name):
			return argument.trim_prefix("--%s=" % name)
	return fallback

func check(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failures.append(message)
		push_error(message)

func used_slots(data: Dictionary, states: Array) -> Dictionary:
	var used := {}
	for state: String in states:
		var group: int = Actor.CHARACTER_GROUPS[state]
		for d in 8:
			for frame: Dictionary in data.actions[group * 8 + d].frames:
				for layer: Dictionary in frame.layers:
					if int(layer.index) >= 0:
						used[int(layer.index)] = true
	return used

func render(actor: Node, state: String, direction: int, frame: int) -> Image:
	actor.set_state(state)
	actor.direction = direction
	var action: Dictionary = actor._get_action(actor._body, state, direction)
	# Walk speed 3.1 keeps the native frame time; idle shows frame 0, as in play.
	actor.velocity = Vector3(3.1, 0, 0) if state == "walk" else Vector3.ZERO
	actor._clock = frame * maxf(0.024, action.delay) + 0.000001
	actor._current_key = ""
	actor._render_frame()
	return actor._sprite.texture.get_image()

## The native body-driven timeline frame `i`: body, head and headgear at the ACT anchor, weapon.
## Play pins idle to frame 0, but the native idle action also holds head-turn frames that
## use the neighbouring head views; reviewing them exercises every head drawing.
func compose(actor: Node, state: String, direction: int, i: int, heads: Dictionary) -> Image:
	var canvas := Image.create(192, 192, false, Image.FORMAT_RGBA8)
	var body_frame: Dictionary = actor._get_action(actor._body, state, direction).frames[i]
	actor._draw_part(canvas, actor._body, body_frame, Vector2.ZERO)
	for data: Dictionary in [actor._head, actor._headgear]:
		if data.is_empty():
			continue
		var action: Dictionary = actor._get_action(data, state, direction)
		var frame: Dictionary = action.frames[i % action.frames.size()]
		actor._draw_part(canvas, data, frame, actor._attachment(body_frame, frame))
		if data == actor._head:
			for layer: Dictionary in frame.layers:
				if int(layer.index) >= 0:
					heads[int(layer.index)] = true
	if actor.weapon_visible and not actor._weapon.is_empty():
		var weapon_action: Dictionary = actor._get_action(actor._weapon, state, direction)
		actor._draw_part(canvas, actor._weapon, weapon_action.frames[i % weapon_action.frames.size()], Vector2.ZERO)
	return canvas

func save(image: Image, path: String) -> String:
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	if image.save_png(path) != OK:
		failures.append("cannot write " + path)
	return FileAccess.get_sha256(path)

func run() -> void:
	var out := option("out-dir").trim_suffix("/")
	var look_path := option("appearance")
	if out.is_empty() or not out.is_absolute_path() or out.begins_with("res://") or DirAccess.dir_exists_absolute(out + "/frames") or look_path.is_empty():
		push_error("Give --out-dir=<new absolute folder> and --appearance=<res:// look>")
		quit(2)
		return
	var states: Array = Array(option("states", "idle,walk,ready,attack").split(",", false))
	var gears: Array = Array(option("headgear", "none,cap,hat").split(",", false))
	var job := option("job", "swordsman")
	var actor := Actor.new()
	root.add_child(actor)
	actor.configure(job)
	actor.set_process(false)
	actor.weapon_visible = true
	var native_actor := Actor.new()
	root.add_child(native_actor)
	native_actor.configure(job)
	native_actor.set_process(false)
	native_actor.weapon_visible = true
	var native_body: Dictionary = SpriteData.load_pair(actor._body.source)
	var native_head: Dictionary = SpriteData.load_pair(actor._head.source)
	if not actor.set_appearance(look_path):
		push_error("Look unusable (a pack is missing or changed): " + look_path)
		quit(2)
		return
	var look := Actor.load_appearance(look_path)
	# ACT records are shared, never edited: the look only swaps SPR textures.
	check(JSON.stringify(actor._body.actions) == JSON.stringify(native_body.actions), "Body ACT differs from the native ACT")
	check(JSON.stringify(actor._head.actions) == JSON.stringify(native_head.actions), "Head ACT differs from the native ACT")
	var summary := {"appearance": look_path, "appearanceSha256": FileAccess.get_sha256(look_path), "job": job, "states": states, "headgear": gears,
		"coverage": actor.coverage, "parts": {}, "frames": 0, "savesTouched": false}
	for part: String in ["body", "head"]:
		var native: Dictionary = native_body if part == "body" else native_head
		var used := used_slots(native, states)
		var replaced: Dictionary = look.get("parts", {}).get(part, {}).get("textures", {})
		var missing := []
		for index: int in used:
			if not replaced.has(index):
				missing.append(index)
		missing.sort()
		summary.parts[part] = {"usedByStates": used.size(), "replaced": used.size() - missing.size(), "nativeFallback": missing}
		if option("require-complete") == "true":
			check(missing.is_empty(), "%s drawings still native in %s: %s (clothing or head would flash)" % [part, states, missing])
	var differs := 0
	var idle_heads := {}
	for state: String in states:
		for gear: String in gears:
			check(actor.set_headgear("" if gear == "none" else gear) and native_actor.set_headgear("" if gear == "none" else gear), "Headgear %s unavailable" % gear)
			var rows := []
			for d in 8:
				var action: Dictionary = actor._get_action(actor._body, state, d)
				var count: int = action.frames.size()
				var row := []
				for i in count:
					var image: Image
					if state == "idle":
						# Frame 0 is what play shows; the rest is the native idle timeline (head turns).
						image = compose(actor, state, d, i, idle_heads)
						if i == 0:
							check(render(actor, state, d, 0).get_data() == image.get_data(), "idle %s frame 0: timeline composition differs from the game actor" % DIRECTIONS[d])
					else:
						image = render(actor, state, d, i)
					save(image, "%s/frames/%s/%s/%s/frame-%02d.png" % [out, state, DIRECTIONS[d], gear, i])
					summary.frames += 1
					row.append(image)
					var native_image := compose(native_actor, state, d, i, {}) if state == "idle" else render(native_actor, state, d, i)
					if native_image.get_data() != image.get_data():
						differs += 1
					# Cache identity includes the look: rendering again returns the same pixels.
					if i == 0:
						check(render(actor, state, d, i).get_data() == image.get_data(), "%s %s frame 0 is not stable across the frame cache" % [state, DIRECTIONS[d]])
				rows.append(row)
			var columns := 0
			for row: Array in rows:
				columns = maxi(columns, row.size())
			var sheet := Image.create(columns * 192, 8 * 192, false, Image.FORMAT_RGBA8)
			for r in rows.size():
				for c in rows[r].size():
					sheet.blit_rect(rows[r][c], Rect2i(0, 0, 192, 192), Vector2i(c * 192, r * 192))
			save(sheet, "%s/contact/%s-%s.png" % [out, state, gear])
	check(differs > 0, "The look renders exactly like native art; no replacement is visible")
	if states.has("idle"):
		# The full idle timeline must show every head drawing the native idle action uses.
		var idle_used := used_slots(native_head, ["idle"])
		var unseen := []
		for index: int in idle_used:
			if not idle_heads.has(index):
				unseen.append(index)
		unseen.sort()
		check(unseen.is_empty(), "Idle timeline did not draw head SPR %s" % [unseen])
		var seen := idle_heads.keys()
		seen.sort()
		summary["idleTimelineHeads"] = seen
	# Headgear attaches to the look's head: cap and none differ on the same frame.
	if gears.has("cap") and gears.has("none"):
		actor.set_headgear("")
		var bare := render(actor, states[0], 0, 0)
		actor.set_headgear("cap")
		check(render(actor, states[0], 0, 0).get_data() != bare.get_data(), "Cap does not change the composite")
	summary["framesDifferingFromNative"] = differs
	summary["checks"] = checks
	summary["failures"] = failures
	var file := FileAccess.open(out + "/look-review.json", FileAccess.WRITE)
	file.store_string(JSON.stringify(summary, "\t") + "\n")
	file.close()
	var lines := ["# Look review fixtures: %s" % look_path, "", "Rendered through the game actor; no browser, no player save. %d frames, %d checks, %d failures." % [summary.frames, checks, failures.size()], ""]
	for part: String in summary.parts:
		var entry: Dictionary = summary.parts[part]
		lines.append("- %s: %d of %d drawings used by %s replaced; native fallback: %s" % [part, entry.replaced, entry.usedByStates, ", ".join(states), entry.nativeFallback])
	lines.append("")
	lines.append("Contact sheets: contact/<state>-<headgear>.png (rows S, SW, W, NW, N, NE, E, SE). This is technical evidence, not visual approval.")
	var md := FileAccess.open(out + "/LOOK-REVIEW.md", FileAccess.WRITE)
	md.store_string("\n".join(lines) + "\n")
	md.close()
	print("LOOK_REVIEW_%s %d checks, %d frames -> %s" % ["PASS" if failures.is_empty() else "FAIL", checks, summary.frames, out])
	quit(0 if failures.is_empty() else 1)
