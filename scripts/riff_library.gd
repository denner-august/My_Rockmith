class_name RiffLibrary
extends RefCounted

const STRING_ALIASES := {
	"E": 0, "E grave": 0, "Mi grave": 0, "e grave": 0, "mi grave": 0, "mi_grave": 0,
	"A": 1, "Lá": 1, "La": 1, "D": 2, "Ré": 2, "Re": 2,
	"G": 3, "Sol": 3, "B": 4, "Si": 4,
	"e": 5, "E aguda": 5, "Mi aguda": 5, "mi aguda": 5, "e aguda": 5
}

static func load_all(riffs: Dictionary) -> Array[String]:
	var loaded: Array[String] = []
	var paths: Array[String] = []
	for folder in ["res://riffs", "user://riffs"]:
		var dir := DirAccess.open(folder)
		if dir == null:
			continue
		dir.list_dir_begin()
		var filename := dir.get_next()
		while not filename.is_empty():
			if not dir.current_is_dir() and filename.to_lower().ends_with(".json"):
				paths.append(folder.path_join(filename))
			filename = dir.get_next()
		dir.list_dir_end()
	paths.sort()
	for path in paths:
		var file := FileAccess.open(path, FileAccess.READ)
		if file == null:
			push_warning("Não foi possível abrir %s" % path)
			continue
		var parsed: Variant = JSON.parse_string(file.get_as_text())
		if not parsed is Dictionary:
			push_warning("JSON inválido: %s" % path)
			continue
		var data: Dictionary = parsed
		var key := str(data.get("id", path.get_file().get_basename())).strip_edges()
		var name := str(data.get("nome", path.get_file().get_basename())).strip_edges()
		var description := str(data.get("descricao", "Importado de JSON")).strip_edges()
		var bpm_value: Variant = data.get("bpm", 100)
		if not (bpm_value is int or bpm_value is float or (bpm_value is String and str(bpm_value).is_valid_int())):
			push_warning("BPM inválido em %s" % path)
			continue
		var bpm := int(bpm_value)
		var events: Variant = data.get("eventos", [])
		if key.is_empty() or name.is_empty() or bpm < 30 or bpm > 300 or not events is Array or events.is_empty() or riffs.has(key):
			push_warning("Dados de riff inválidos ou id duplicado: %s" % path)
			continue
		var normalized: Array[Dictionary] = []
		var valid := true
		for i in range(events.size()):
			var event: Variant = events[i]
			if not event is Dictionary:
				valid = false
				break
			var raw_string: Variant = event.get("corda", null)
			var string_index := -1
			if raw_string is int or raw_string is float:
				string_index = int(raw_string)
			elif raw_string is String:
				string_index = int(STRING_ALIASES.get(str(raw_string).strip_edges(), -1))
			if raw_string is float and not is_equal_approx(raw_string, roundf(raw_string)):
				valid = false
				break
			var fret_value: Variant = event.get("traste", -1)
			if not (fret_value is int or fret_value is float or (fret_value is String and str(fret_value).is_valid_int())):
				valid = false
				break
			var fret := int(fret_value)
			if fret_value is float and not is_equal_approx(fret_value, roundf(fret_value)):
				valid = false
				break
			var beat_value: Variant = event.get("pulso", i)
			if not (beat_value is int or beat_value is float or (beat_value is String and str(beat_value).is_valid_float())):
				valid = false
				break
			var beat := float(beat_value)
			if string_index < 0 or string_index > 5 or fret < 0 or fret > 24 or not is_finite(beat) or beat < 0.0:
				valid = false
				break
			normalized.append({"corda": string_index, "traste": fret, "pulso": beat})
		if not valid:
			push_warning("Notas inválidas em %s" % path)
			continue
		riffs[key] = {"nome": name, "bpm": bpm, "eventos": normalized, "descricao": description, "arquivo": path}
		loaded.append(name)
	return loaded

static func build_notes(riff: Dictionary, speed: float) -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	var seconds_per_beat := 60.0 / (float(riff["bpm"]) * speed)
	for event in riff["eventos"]:
		var string_index := int(event["corda"])
		result.append({"t": 3.0 + float(event["pulso"]) * seconds_per_beat, "corda": string_index, "traste": int(event["traste"]), "midi": GameConfig.STRING_MIDI[string_index] + int(event["traste"]), "estado": "pendente"})
	return result
