extends RefCounted
## Native decoder for the local RO reference set. No network or server dependency.
## Supported: SPR 2.0/2.1; ACT 2.0 through 2.5 (2.2 has no anchors).
## ACT coordinates stay in their original pixels, positive Y down. Layer index is
## normalized into textures (including the indexed_count offset for truecolor).
## Artwork provenance and ownership: assets/reference-ro/provenance.json.

class Reader:
	extends RefCounted
	var data: PackedByteArray
	var cursor := 0
	var failed := false
	var reason := ""

	func _init(bytes: PackedByteArray) -> void:
		data = bytes

	func require_bytes(count: int) -> bool:
		if failed:
			return false
		if count < 0 or cursor + count > data.size():
			fail("Unexpected end of file at byte %d (need %d)" % [cursor, count])
			return false
		return true

	func fail(message: String) -> void:
		if not failed:
			reason = message
		failed = true

	func skip(count: int) -> void:
		if require_bytes(count):
			cursor += count

	func bytes(count: int) -> PackedByteArray:
		if not require_bytes(count):
			return PackedByteArray()
		var result := data.slice(cursor, cursor + count)
		cursor += count
		return result

	func u8() -> int:
		if not require_bytes(1):
			return 0
		var value := data[cursor]
		cursor += 1
		return value

	func u16() -> int:
		if not require_bytes(2):
			return 0
		var value := data.decode_u16(cursor)
		cursor += 2
		return value

	func i32() -> int:
		if not require_bytes(4):
			return 0
		var value := data.decode_s32(cursor)
		cursor += 4
		return value

	func f32() -> float:
		if not require_bytes(4):
			return 0.0
		var value := data.decode_float(cursor)
		cursor += 4
		if not is_finite(value):
			fail("Non-finite float")
		return value

	func count(maximum: int) -> int:
		var value := i32()
		if value < 0 or value > maximum:
			fail("Invalid collection count %d" % value)
			return 0
		return value


static func load_pair(base_path: String) -> Dictionary:
	var spr_path := base_path + ".spr"
	var act_path := base_path + ".act"
	if not FileAccess.file_exists(spr_path) or not FileAccess.file_exists(act_path):
		push_error("RO sprite pair missing: " + base_path)
		return {}
	var sprites := _read_spr(FileAccess.get_file_as_bytes(spr_path))
	if sprites.is_empty():
		push_error("RO SPR decoding failed: " + spr_path)
		return {}
	var animation := _read_act(FileAccess.get_file_as_bytes(act_path), sprites.indexed_count, sprites.textures.size())
	if animation.is_empty():
		push_error("RO ACT decoding failed: " + act_path)
		return {}
	sprites.merge(animation)
	return sprites


static func _read_spr(bytes: PackedByteArray) -> Dictionary:
	var r := Reader.new(bytes)
	if r.bytes(2).get_string_from_ascii() != "SP":
		return _error("Invalid SPR signature")
	var minor := r.u8()
	var major := r.u8()
	var version := major * 10 + minor
	if version not in [20, 21]:
		return _error("Unsupported SPR version %d.%d" % [major, minor])
	var indexed_count := r.u16()
	var rgba_count := r.u16()
	if indexed_count + rgba_count == 0 or indexed_count + rgba_count > 8192:
		return _error("Invalid SPR image count")
	if bytes.size() < 1032:
		return _error("SPR palette missing")
	var palette := bytes.slice(bytes.size() - 1024)
	var textures: Array[Texture2D] = []
	for sprite_index in range(indexed_count + rgba_count):
		var width := r.u16()
		var height := r.u16()
		if width < 1 or height < 1 or width > 4096 or height > 4096 or width * height > 16777216:
			return _error("Invalid SPR dimensions")
		var pixels := PackedByteArray()
		pixels.resize(width * height * 4)
		if sprite_index < indexed_count:
			var indices := PackedByteArray()
			if version == 21:
				var compressed_size := r.u16()
				var compressed := Reader.new(r.bytes(compressed_size))
				while compressed.cursor < compressed.data.size() and not compressed.failed:
					var value := compressed.u8()
					if value == 0:
						var run := compressed.u8()
						# 00 00 encodes two transparent pixels; other runs include
						# the zero marker as the first pixel in their length.
						if run == 0:
							run = 2
						if indices.size() + run > width * height:
							return _error("SPR transparent run exceeds image bounds")
						for _j in range(run):
							indices.append(0)
					else:
						indices.append(value)
					if indices.size() > width * height:
						return _error("SPR decoded image exceeds dimensions")
				if compressed.failed:
					return _error(compressed.reason)
			else:
				indices = r.bytes(width * height)
			if indices.size() != width * height:
				return _error("SPR pixel count does not match dimensions")
			for p in range(indices.size()):
				var index := int(indices[p])
				var offset := p * 4
				pixels[offset] = palette[index * 4]
				pixels[offset + 1] = palette[index * 4 + 1]
				pixels[offset + 2] = palette[index * 4 + 2]
				pixels[offset + 3] = 0 if index == 0 else 255
		else:
			# Truecolor SPR storage is ABGR, bottom row first.
			var source := r.bytes(width * height * 4)
			if r.failed:
				return _error(r.reason)
			for y in range(height):
				for x in range(width):
					var src := ((height - 1 - y) * width + x) * 4
					var dst := (y * width + x) * 4
					pixels[dst] = source[src + 3]
					pixels[dst + 1] = source[src + 2]
					pixels[dst + 2] = source[src + 1]
					pixels[dst + 3] = source[src]
		if r.failed or r.cursor > bytes.size() - 1024:
			return _error("SPR frame overlaps palette or is truncated")
		var image := Image.create_from_data(width, height, false, Image.FORMAT_RGBA8, pixels)
		textures.append(ImageTexture.create_from_image(image))
	if r.cursor != bytes.size() - 1024:
		return _error("SPR image data did not end at palette")
	return {"textures": textures, "indexed_count": indexed_count, "spr_version": version}


static func _read_act(bytes: PackedByteArray, indexed_count: int, texture_count: int) -> Dictionary:
	var r := Reader.new(bytes)
	if r.bytes(2).get_string_from_ascii() != "AC":
		return _error("Invalid ACT signature")
	var minor := r.u8()
	var major := r.u8()
	var version := major * 10 + minor
	if version < 20 or version > 25:
		return _error("Unsupported ACT version %d.%d" % [major, minor])
	var action_count := r.u16()
	if action_count == 0 or action_count > 4096:
		return _error("Invalid ACT action count")
	r.skip(10)
	var actions: Array = []
	for _action_id in range(action_count):
		var frames: Array = []
		var frame_count := r.count(4096)
		if frame_count == 0:
			return _error("ACT action has no frames")
		for _frame_id in range(frame_count):
			r.skip(32)
			var layers: Array = []
			var layer_count := r.count(1024)
			for _layer_id in range(layer_count):
				var x := r.i32()
				var y := r.i32()
				var index := r.i32()
				var mirror := r.i32() != 0
				var color := Color(r.u8() / 255.0, r.u8() / 255.0, r.u8() / 255.0, r.u8() / 255.0)
				var scale_x := r.f32()
				var scale_y := r.f32() if version >= 24 else scale_x
				var rotation := deg_to_rad(float(r.i32()))
				var image_type := r.i32()
				if version >= 25:
					r.skip(8) # Stored image dimensions; decoded SPR is authoritative.
				if image_type not in [0, 1]:
					return _error("Unknown ACT layer image type")
				# Preserve -1 as the explicit hidden/empty layer sentinel.
				if index >= 0 and image_type == 1:
					index += indexed_count
				if index < -1 or index >= texture_count:
					return _error("ACT layer refers to missing SPR image")
				layers.append({"x": x, "y": y, "index": index, "mirror": mirror, "color": color, "scale": Vector2(scale_x, scale_y), "rotation": rotation, "type": image_type})
			var event := r.i32()
			var anchors: Array[Vector2] = []
			if version >= 23:
				var anchor_count := r.count(256)
				for _anchor_id in range(anchor_count):
					r.skip(4)
					var x := r.i32()
					var y := r.i32()
					anchors.append(Vector2(x, y))
					r.skip(4)
			frames.append({"layers": layers, "anchors": anchors, "event": event})
			if r.failed:
				return _error(r.reason)
		actions.append({"frames": frames, "delay": 0.15})
	var events: Array[String] = []
	if version >= 21:
		var event_count := r.count(4096)
		for _event in range(event_count):
			var name := r.bytes(40)
			var end := name.find(0)
			if end >= 0:
				name = name.slice(0, end)
			events.append(name.get_string_from_ascii())
	if version >= 22:
		for action in actions:
			var ticks := r.f32()
			if ticks <= 0.0 or ticks > 10000.0:
				return _error("Invalid ACT frame timing")
			action.delay = ticks * 0.024
	if r.failed:
		return _error(r.reason)
	if r.cursor != bytes.size():
		return _error("Trailing bytes after ACT animation data")
	return {"actions": actions, "events": events, "act_version": version}


static func _error(message: String) -> Dictionary:
	push_error("RO sprite data: " + message)
	return {}
