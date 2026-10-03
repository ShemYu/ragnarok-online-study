extends SceneTree
## Export the generation boards listed in a board plan (D14). Each board goes to
## <out>/<board id>/; an existing board folder is never overwritten.
##
## Godot --headless --log-file <abs log> --path . --script res://tools/character-lab/export_boards.gd -- \
##   [--plan=res://tools/character-lab/plans/completion-2026-10-02.json] [--board=<id>[,<id>...]]
##   [--out=<folder; default: the plan's "output">] [--skip-existing]
const Actor = preload("res://scripts/ro_sprite_actor.gd")
const Boards = preload("res://tools/character-lab/board_export.gd")

func _initialize() -> void:
	call_deferred("run")

func option(name: String, fallback: String = "") -> String:
	for argument in OS.get_cmdline_user_args():
		if argument == "--" + name:
			return "true"
		if argument.begins_with("--%s=" % name):
			return argument.trim_prefix("--%s=" % name)
	return fallback

func run() -> void:
	var plan_path := option("plan", "res://tools/character-lab/plans/completion-2026-10-02.json")
	var plan: Variant = JSON.parse_string(FileAccess.get_file_as_string(plan_path)) if FileAccess.file_exists(plan_path) else null
	if not plan is Dictionary or not plan.get("boards") is Array:
		push_error("Board plan unusable: " + plan_path)
		quit(2)
		return
	var out_root := option("out", str(plan.get("output", ""))).trim_suffix("/") + "/"
	if out_root == "/":
		push_error("Give --out or an \"output\" folder in the plan")
		quit(2)
		return
	var wanted := option("board").split(",", false)
	var skip_existing := option("skip-existing") == "true"
	var selected := []
	for spec: Dictionary in plan.boards:
		if wanted.is_empty() or wanted.has(str(spec.get("id", ""))):
			selected.append(spec)
	if selected.is_empty():
		push_error("No board in %s matches %s" % [plan_path, wanted])
		quit(2)
		return
	var existing := []
	for spec: Dictionary in selected:
		# Any existing folder counts, including a partial one from an interrupted export.
		var folder := ProjectSettings.globalize_path(out_root + str(spec.id))
		if DirAccess.dir_exists_absolute(folder) or FileAccess.file_exists(folder):
			existing.append(str(spec.id))
	if not existing.is_empty() and not skip_existing:
		push_error("Board folders (or files) already exist and are never overwritten or completed: %s (use --skip-existing or a new --out)" % ", ".join(existing))
		quit(1)
		return
	var actor := Actor.new()
	root.add_child(actor)
	actor.configure("swordsman" if str(plan.get("job", "")).begins_with("swordsman") else "novice")
	actor.set_process(false)
	var failures := 0
	for spec: Dictionary in selected:
		if existing.has(str(spec.id)):
			print("skip %s (exists)" % spec.id)
			continue
		var result: Dictionary = Boards.export_board(spec, plan, out_root + str(spec.id) + "/", actor)
		if result.ok:
			print("board " + result.summary)
		else:
			failures += 1
			push_error("board %s: %s" % [spec.id, result.error])
	print("EXPORT_BOARDS %s: %d of %d boards" % ["PASS" if failures == 0 else "FAIL", selected.size() - existing.size() - failures, selected.size() - existing.size()])
	quit(1 if failures else 0)
