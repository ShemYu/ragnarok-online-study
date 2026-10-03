extends SceneTree
## Output-safety checks for the board exporter and the generic importer (completion QA).
## Run: Godot --headless --log-file <abs log> --path . --script res://tests/completion_safety_test.gd -- \
##        --out-dir=<new absolute folder> [--log-dir=<absolute writable folder>]
## Writes only below --out-dir. Requires the local slot inventory, native sources and the
## design references named by the completion plan.
const Actor = preload("res://scripts/ro_sprite_actor.gd")
const Boards = preload("res://tools/character-lab/board_export.gd")
const PLAN := "res://tools/character-lab/plans/completion-2026-10-02.json"
const HEAD_BOARD := "wayfarer-head-views"
var OUT := ""
var LOGS := ""
var checks := 0
var failures := 0
var calls := 0

func _initialize() -> void:
	call_deferred("run")

func option(name: String) -> String:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--%s=" % name):
			return argument.trim_prefix("--%s=" % name)
	return ""

func check(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(message)

func godot(arguments: Array) -> int:
	calls += 1
	var output := []
	var code := OS.execute(OS.get_executable_path(), ["--headless", "--log-file", LOGS.path_join("completion-safety-%02d.log" % calls), "--path", ProjectSettings.globalize_path("res://")] + arguments, output, true)
	if code != 0:
		print("\n".join(output))
	return code

func listing(folder: String) -> Array:
	var dir := DirAccess.open(folder)
	if dir == null:
		return []
	dir.include_hidden = true
	var names := Array(dir.get_files()) + Array(dir.get_directories())
	names.sort()
	return names

func run() -> void:
	OUT = option("out-dir").trim_suffix("/")
	if OUT.is_empty() or not OUT.is_absolute_path() or OUT.begins_with("res://") or DirAccess.dir_exists_absolute(OUT + "/boards"):
		push_error("Give --out-dir=<new absolute folder>")
		quit(2)
		return
	LOGS = option("log-dir").trim_suffix("/") if not option("log-dir").is_empty() else OUT + "/logs"
	DirAccess.make_dir_recursive_absolute(LOGS)
	var plan: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(PLAN))
	var spec: Dictionary = {}
	for entry: Dictionary in plan.boards:
		if entry.id == HEAD_BOARD:
			spec = entry
	check(not spec.is_empty(), "Plan has no %s board" % HEAD_BOARD)
	# 1. A partial board folder (interrupted export) is refused, not completed.
	var boards := OUT + "/boards/"
	DirAccess.make_dir_recursive_absolute(boards + HEAD_BOARD)
	var marker := FileAccess.open(boards + HEAD_BOARD + "/partial.txt", FileAccess.WRITE)
	marker.store_string("left by an interrupted export\n")
	marker.close()
	check(godot(["--script", "res://tools/character-lab/export_boards.gd", "--", "--plan=" + PLAN, "--board=" + HEAD_BOARD, "--out=" + boards]) == 1, "export_boards must refuse a partial board folder")
	check(listing(boards + HEAD_BOARD) == ["partial.txt"], "A refused export must not add files: %s" % [listing(boards + HEAD_BOARD)])
	# 2. Failed image saves and failed prompt writes are reported, never PASS.
	var actor := Actor.new()
	root.add_child(actor)
	actor.configure("swordsman")
	actor.set_process(false)
	for blocker in ["slot-board.png", "context-frames.png", "design-reference-1.png", "prompt.txt"]:
		var target := OUT + "/blocked-%s/" % blocker.get_basename()
		DirAccess.make_dir_recursive_absolute(target + blocker)  # a folder where the file must go
		var result: Dictionary = Boards.export_board(spec, plan, target, actor)
		check(not result.ok, "export_board must fail when %s cannot be written" % blocker)
		if blocker != "prompt.txt":
			check(not FileAccess.file_exists(target + "sprite-slots.json"), "No layout may be written after %s failed" % blocker)
	# 3. A clean export writes every artifact and records the body timeline for head fixtures.
	var good := boards + "fresh/"
	var exported: Dictionary = Boards.export_board(spec, plan, good, actor)
	check(exported.ok, "Clean head board export must succeed: %s" % exported.get("error", ""))
	for file in ["sprite-slots.json", "slot-board.png", "slot-board-10x.png", "context-frames.png", "design-reference-1.png", "prompt.txt", "HOWTO.txt"]:
		check(FileAccess.file_exists(good + file), "Missing board artifact " + file)
	var layout: Variant = JSON.parse_string(FileAccess.get_file_as_string(good + "sprite-slots.json"))
	if layout is Dictionary:
		var timeline_ok := true
		for group: String in layout.groupSequences:
			for direction: String in layout.groupSequences[group]:
				var sequence: Dictionary = layout.groupSequences[group][direction]
				timeline_ok = timeline_ok and sequence.has("bodyFrames") and sequence.has("bodyDelayMs")
		check(timeline_ok, "Head board must record the body frame count and delay per group/direction")
		check(not FileAccess.get_file_as_string(good + "prompt.txt").contains("HEADLESS"), "Head prompt must not ask for headless sprites")
	# 4. The importer refuses an occupied output folder before writing anything.
	var pack := OUT + "/occupied-pack/"
	DirAccess.make_dir_recursive_absolute(pack)
	var keep := FileAccess.open(pack + "keep.txt", FileAccess.WRITE)
	keep.store_string("existing pack content\n")
	keep.close()
	check(godot(["--script", "res://tools/character-lab/import_slot_board.gd", "--", "--board=" + good, "--source=" + good + "slot-board-10x.png", "--output-dir=" + pack]) == 1, "import_slot_board must refuse an occupied output folder")
	check(listing(pack) == ["keep.txt"], "A refused import must not add files: %s" % [listing(pack)])
	if failures == 0 and checks >= 15:
		print("COMPLETION_SAFETY_TEST_PASS (%d checks) -> %s" % [checks, OUT])
	else:
		push_error("COMPLETION_SAFETY_TEST_FAIL: %d of %d checks" % [failures, checks])
	quit(1 if failures or checks < 15 else 0)
