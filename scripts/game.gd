extends Control

const MUTED := Color8(163, 170, 188)

var riffs := GameConfig.default_riffs()
var riff_keys: Array[String] = []
var selected_riff := "riff_imagem"
var game_state := "espera"
var notes: Array[Dictionary] = []
var effects: Array[Dictionary] = []
var game_time := 0.0
var pause_time := 0.0
var latency := GameConfig.DEFAULT_LATENCY
var speed_profiles := {"lento": 0.75, "padrao": 1.0, "rapido": 1.25}
var speed_profile := "padrao"
var speed_multiplier := 1.0
var score := 0
var combo := 0
var best_combo := 0
var hits := 0
var misses := 0
var metronome_enabled := true
var last_beat := -1
var riff_menu_open := false
var riff_focus := 0
var riff_scroll := 0
var mic: MicPitch
var metronome_player: AudioStreamPlayer
var beat_sound: AudioStreamWAV
var strong_sound: AudioStreamWAV
var windowed := false
var status_label: Label
var shortcuts_label: Label
var prompt_label: Label
var selected_label: Label
var signal_label: Label
var paused_label: Label
var results_label: Label
var riff_modal_shield: Control
var top_hud: Control
var center_message_container: Control
var action_buttons: Dictionary = {}

func _ready() -> void:
	get_window().title = "Mini Rocksmith"
	get_window().size = Vector2i(1920, 1080)
	get_window().mode = Window.MODE_EXCLUSIVE_FULLSCREEN
	windowed = false
	_build_ui()
	riff_keys.assign(riffs.keys())
	RiffLibrary.load_all(riffs)
	riff_keys.assign(riffs.keys())
	if not riffs.has(selected_riff) and not riff_keys.is_empty():
		selected_riff = riff_keys[0]
	riff_focus = maxi(0, riff_keys.find(selected_riff))
	mic = MicPitch.new()
	add_child(mic)
	metronome_player = AudioStreamPlayer.new()
	add_child(metronome_player)
	beat_sound = _make_click(750.0, 0.25)
	strong_sound = _make_click(1100.0, 0.42)
	set_process(true)
	_refresh_ui()

func _process(delta: float) -> void:
	if game_state == "jogando":
		game_time += delta
		_update_notes()
		_update_metronome()
	for effect in effects:
		effect["age"] = float(effect["age"]) + delta
	effects = effects.filter(func(effect: Dictionary) -> bool: return float(effect["age"]) < GameConfig.EFFECT_DURATION)
	_refresh_ui()
	queue_redraw()

func _build_ui() -> void:
	# Status e botões ocupam a faixa superior; o VBox da direita mantém os
	# perfis abaixo da fileira de ações sem sobreposição.
	var top_row := HBoxContainer.new()
	top_row.name = "TopHUD"
	top_hud = top_row
	top_row.anchor_right = 1.0
	top_row.offset_left = 18.0
	top_row.offset_top = 16.0
	top_row.offset_right = -18.0
	top_row.offset_bottom = 126.0
	top_row.add_theme_constant_override("separation", 18)
	add_child(top_row)

	var left_column := VBoxContainer.new()
	left_column.name = "AudioStatus"
	left_column.custom_minimum_size.x = 400.0
	left_column.add_theme_constant_override("separation", 9)
	top_row.add_child(left_column)
	status_label = _new_label(17, Color8(174, 207, 255))
	left_column.add_child(status_label)
	shortcuts_label = _new_label(14, Color8(139, 155, 181))
	shortcuts_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	shortcuts_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left_column.add_child(shortcuts_label)

	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	top_row.add_child(spacer)

	var toolbar := VBoxContainer.new()
	toolbar.name = "ToolbarAndSpeedProfiles"
	toolbar.custom_minimum_size.x = 650.0
	toolbar.add_theme_constant_override("separation", 7)
	top_row.add_child(toolbar)
	var action_row := HBoxContainer.new()
	action_row.add_theme_constant_override("separation", 6)
	toolbar.add_child(action_row)
	_add_action_button(action_row, "menu", "RIFFS", 78, _open_riff_menu)
	_add_action_button(action_row, "pause", "PAUSAR", 92, _on_pause_pressed)
	_add_action_button(action_row, "restart", "REINICIAR", 98, _on_restart_pressed)
	_add_action_button(action_row, "metro", "METRÔNOMO", 118, _on_metronome_pressed)
	_add_action_button(action_row, "menos", "−", 42, _on_slower_pressed)
	_add_action_button(action_row, "mais", "+", 42, _on_faster_pressed)
	var profile_row := HBoxContainer.new()
	profile_row.add_theme_constant_override("separation", 6)
	toolbar.add_child(profile_row)
	_add_action_button(profile_row, "lento", "1 LENTO", 92, func() -> void: _set_speed("lento"))
	_add_action_button(profile_row, "padrao", "2 PADRÃO", 92, func() -> void: _set_speed("padrao"))
	_add_action_button(profile_row, "rapido", "3 RÁPIDO", 92, func() -> void: _set_speed("rapido"))

	var center_messages := VBoxContainer.new()
	center_messages.name = "CenterMessages"
	center_message_container = center_messages
	center_messages.anchor_left = 0.12
	center_messages.anchor_top = 0.18
	center_messages.anchor_right = 0.88
	center_messages.anchor_bottom = 0.35
	center_messages.offset_left = 0.0
	center_messages.offset_top = 0.0
	center_messages.offset_right = 0.0
	center_messages.offset_bottom = 0.0
	center_messages.alignment = BoxContainer.ALIGNMENT_CENTER
	center_messages.add_theme_constant_override("separation", 5)
	center_messages.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(center_messages)
	prompt_label = _new_label(32, Color.WHITE)
	prompt_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	prompt_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	prompt_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	center_messages.add_child(prompt_label)
	selected_label = _new_label(22, MUTED)
	selected_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	selected_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	selected_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	center_messages.add_child(selected_label)
	signal_label = _new_label(18, GameConfig.RED)
	signal_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	signal_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	signal_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	center_messages.add_child(signal_label)
	paused_label = _new_label(34, Color8(255, 220, 100))
	paused_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	paused_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	paused_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	center_messages.add_child(paused_label)
	results_label = _new_label(28, Color.WHITE)
	results_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	results_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	results_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	center_messages.add_child(results_label)

	riff_modal_shield = Control.new()
	riff_modal_shield.name = "RiffModalInputShield"
	riff_modal_shield.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	riff_modal_shield.mouse_filter = Control.MOUSE_FILTER_STOP
	riff_modal_shield.z_index = 10
	riff_modal_shield.visible = false
	add_child(riff_modal_shield)

func _new_label(font_size: int, color: Color) -> Label:
	var label := Label.new()
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	label.clip_text = false
	return label

func _add_action_button(parent: HBoxContainer, key: String, caption: String, min_width: float, callback: Callable) -> void:
	var button := Button.new()
	button.name = key.capitalize()
	button.text = caption
	button.custom_minimum_size = Vector2(min_width, 38.0)
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	button.toggle_mode = key in ["metro", "lento", "padrao", "rapido"]
	button.pressed.connect(callback)
	parent.add_child(button)
	action_buttons[key] = button

func _refresh_ui() -> void:
	if status_label == null:
		return
	status_label.text = "LATÊNCIA %d ms  •  %s  •  VOL %.1f  •  %s" % [roundi(latency * 1000.0), "SOM ON" if mic.monitor_enabled else "SOM OFF", mic.volume, "OVERDRIVE" if mic.overdrive else "LIMPO"]
	shortcuts_label.text = "[M] som  [D] timbre  [T] metrônomo  [↑↓] volume  [←→] latência"
	var selected_name := str(riffs[selected_riff]["nome"])
	prompt_label.text = "Toque uma corda para testar — ESPAÇO para começar"
	selected_label.text = "Selecionado: %s" % selected_name
	signal_label.text = "Sem sinal: habilite a entrada de áudio do sistema"
	paused_label.text = "PAUSADO  •  P para continuar"
	var total := maxi(1, hits + misses)
	results_label.text = "PONTOS: %d\nAcertos: %d/%d (%d%%)  •  Melhor combo: %d\nESPAÇO para jogar novamente" % [score, hits, total, roundi(100.0 * hits / total), best_combo]
	prompt_label.visible = game_state == "espera"
	selected_label.visible = game_state == "espera"
	signal_label.visible = game_state == "espera" and mic.level < GameConfig.SILENCE_THRESHOLD
	paused_label.visible = game_state == "pausado"
	results_label.visible = game_state == "fim"
	var pause_button: Button = action_buttons["pause"]
	pause_button.text = "CONTINUAR" if game_state == "pausado" else "PAUSAR"
	var metro_button: Button = action_buttons["metro"]
	metro_button.text = "METRÔNOMO ON" if metronome_enabled else "METRÔNOMO OFF"
	metro_button.button_pressed = metronome_enabled
	for profile in ["lento", "padrao", "rapido"]:
		var button: Button = action_buttons[profile]
		button.button_pressed = speed_profile == profile
	riff_modal_shield.visible = riff_menu_open
	top_hud.visible = not riff_menu_open
	center_message_container.visible = not riff_menu_open

func _open_riff_menu() -> void:
	riff_menu_open = true
	riff_focus = maxi(0, riff_keys.find(selected_riff))
	_update_riff_scroll()
	if game_state == "jogando":
		_toggle_pause()
	_refresh_ui()
	queue_redraw()

func _on_pause_pressed() -> void:
	_toggle_pause()
	_refresh_ui()

func _on_restart_pressed() -> void:
	_start_game()
	_refresh_ui()

func _on_metronome_pressed() -> void:
	metronome_enabled = not metronome_enabled
	_refresh_ui()

func _on_slower_pressed() -> void:
	_adjust_speed(-0.05)
	_refresh_ui()

func _on_faster_pressed() -> void:
	_adjust_speed(0.05)
	_refresh_ui()

func _make_click(frequency: float, volume: float) -> AudioStreamWAV:
	var rate := 22050
	var samples := PackedByteArray()
	var length := int(rate * 0.045)
	samples.resize(length * 2)
	for i in length:
		var envelope := 1.0 - float(i) / length
		var value := int(clampf(sin(TAU * frequency * i / rate) * envelope * volume, -1.0, 1.0) * 32767.0)
		samples.encode_s16(i * 2, value)
	var wav := AudioStreamWAV.new()
	wav.format = AudioStreamWAV.FORMAT_16_BITS
	wav.mix_rate = rate
	wav.stereo = false
	wav.data = samples
	return wav

func _start_game() -> void:
	if mic == null:
		return
	notes = RiffLibrary.build_notes(riffs[selected_riff], speed_multiplier)
	game_time = 0.0
	score = 0
	combo = 0
	best_combo = 0
	hits = 0
	misses = 0
	effects.clear()
	last_beat = -1
	game_state = "jogando"

func _toggle_pause() -> void:
	if game_state == "jogando":
		game_state = "pausado"
		pause_time = game_time
	elif game_state == "pausado":
		game_state = "jogando"

func _update_notes() -> void:
	var audio_time := game_time - latency
	for note in notes:
		if note["estado"] != "pendente":
			continue
		if audio_time > float(note["t"]) + GameConfig.HIT_WINDOW:
			note["estado"] = "errou"
			misses += 1
			combo = 0
			_add_effect(note, false, "ERROU")
		elif absf(audio_time - float(note["t"])) <= GameConfig.HIT_WINDOW and GameConfig.pitch_matches(mic.midi, int(note["midi"])):
			note["estado"] = "acertou"
			hits += 1
			combo += 1
			best_combo = maxi(best_combo, combo)
			var perfect := absf(audio_time - float(note["t"])) <= 0.06
			var gain := 100 + mini(combo, 10) * 10 + (50 if perfect else 0)
			score += gain
			_add_effect(note, true, ("PERFEITO" if perfect else "BOA") + "  +" + str(gain))
	var finished := not notes.is_empty()
	for note in notes:
		if note["estado"] == "pendente":
			finished = false
			break
	if finished:
		game_state = "fim"

func _add_effect(note: Dictionary, success: bool, text: String) -> void:
	effects.append({"corda": int(note["corda"]), "ok": success, "texto": text, "age": 0.0})

func _update_metronome() -> void:
	if not metronome_enabled:
		return
	var bpm := float(riffs[selected_riff]["bpm"]) * speed_multiplier
	var beat := floori(game_time * bpm / 60.0)
	if beat > last_beat:
		metronome_player.stream = strong_sound if beat % 4 == 0 else beat_sound
		metronome_player.play()
		last_beat = beat

func _input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		_handle_key(event as InputEventKey)
	elif event is InputEventMouseButton and event.pressed and riff_menu_open:
		_handle_click((event as InputEventMouseButton).position)
		get_viewport().set_input_as_handled()

func _handle_key(event: InputEventKey) -> void:
	var key := event.keycode
	if riff_menu_open:
		if key == KEY_ESCAPE:
			riff_menu_open = false
			if game_state == "pausado":
				_toggle_pause()
			_refresh_ui()
		elif key == KEY_UP or key == KEY_LEFT:
			riff_focus = maxi(0, riff_focus - 1)
			_update_riff_scroll()
		elif key == KEY_DOWN or key == KEY_RIGHT:
			riff_focus = mini(riff_keys.size() - 1, riff_focus + 1)
			_update_riff_scroll()
		elif key == KEY_ENTER or key == KEY_KP_ENTER or key == KEY_SPACE:
			selected_riff = riff_keys[riff_focus]
			riff_menu_open = false
			_start_game()
			_refresh_ui()
		return
	match key:
		KEY_ESCAPE: get_tree().quit()
		KEY_F11:
			windowed = not windowed
			get_window().mode = Window.MODE_WINDOWED if windowed else Window.MODE_EXCLUSIVE_FULLSCREEN
		KEY_SPACE:
			if game_state == "espera" or game_state == "fim": _start_game()
		KEY_P: _toggle_pause()
		KEY_R: _start_game()
		KEY_T: metronome_enabled = not metronome_enabled
		KEY_M: mic.monitor_enabled = not mic.monitor_enabled
		KEY_D: mic.overdrive = not mic.overdrive
		KEY_UP: mic.volume = minf(1.5, mic.volume + 0.1)
		KEY_DOWN: mic.volume = maxf(0.0, mic.volume - 0.1)
		KEY_LEFT: latency = maxf(0.0, latency - 0.01)
		KEY_RIGHT: latency = minf(0.5, latency + 0.01)
		KEY_1: _set_speed("lento")
		KEY_2: _set_speed("padrao")
		KEY_3: _set_speed("rapido")
		KEY_MINUS: _adjust_speed(-0.05)
		KEY_EQUAL, KEY_KP_ADD: _adjust_speed(0.05)
	_refresh_ui()

func _set_speed(profile: String) -> void:
	speed_profile = profile
	speed_multiplier = float(speed_profiles[profile])
	if game_state == "jogando" or game_state == "pausado":
		_start_game()
	_refresh_ui()

func _update_riff_scroll() -> void:
	var size := get_viewport_rect().size
	var visible := maxi(1, int((size.y * 0.70 - 140.0) / 118.0))
	if riff_focus < riff_scroll:
		riff_scroll = riff_focus
	elif riff_focus >= riff_scroll + visible:
		riff_scroll = riff_focus - visible + 1

func _adjust_speed(amount: float) -> void:
	if speed_profile == "padrao":
		return
	speed_profiles[speed_profile] = clampf(float(speed_profiles[speed_profile]) + amount, 0.35, 2.0)
	speed_multiplier = float(speed_profiles[speed_profile])
	if game_state == "jogando" or game_state == "pausado":
		_start_game()
	_refresh_ui()

func _handle_click(point: Vector2) -> void:
	var size := get_viewport_rect().size
	if riff_menu_open:
		var menu := Rect2(Vector2(size.x * 0.15, size.y * 0.15), Vector2(size.x * 0.70, size.y * 0.70))
		if not menu.has_point(point):
			riff_menu_open = false
			if game_state == "pausado":
				_toggle_pause()
			_refresh_ui()
			queue_redraw()
			return
		var top := menu.position.y + 100.0
		for i in range(riff_keys.size()):
			var visible_index := i - riff_scroll
			if visible_index < 0 or visible_index >= maxi(1, int((menu.size.y - 140.0) / 118.0)):
				continue
			var card := Rect2(menu.position.x + 24.0, top + visible_index * 118.0, menu.size.x - 48.0, 110.0)
			if card.has_point(point):
				riff_focus = i
				selected_riff = riff_keys[i]
				riff_menu_open = false
				_start_game()
				_refresh_ui()
				queue_redraw()
				return
		return

func _draw() -> void:
	var size := get_viewport_rect().size
	var scale := minf(size.x / 800.0, size.y / 520.0)
	var top := size.y * 0.38
	var target_y := size.y * 0.74
	var end_y := size.y * 0.80
	var gap := minf(size.y * 0.17, size.x * 0.8 / 6.0)
	var x0 := size.x / 2.0 - 2.5 * gap
	var radius := maxf(12.0, gap * 0.15)
	var lane_x: Array[float] = []
	for i in 6:
		lane_x.append(x0 + i * gap)
		_draw_line(Vector2(lane_x[i], top), Vector2(lane_x[i], end_y), Color8(55,55,62), maxf(1.0, 2.0 * scale))
		_draw_text(GameConfig.STRING_NAMES[i], Vector2(lane_x[i], size.y * 0.83), 24.0 * scale, GameConfig.STRING_COLORS[i], HORIZONTAL_ALIGNMENT_CENTER)
	_draw_line(Vector2(lane_x[0] - gap * 0.45, target_y), Vector2(lane_x[5] + gap * 0.45, target_y), Color.WHITE, maxf(2.0, 4.0 * scale))
	var minimum_speed := _minimum_lane_speed(radius)
	var visual_speed := maxf((target_y - top) / GameConfig.VISIBLE_SECONDS * speed_multiplier, minimum_speed)
	if game_state == "jogando" or game_state == "pausado":
		var elapsed := game_time if game_state == "jogando" else pause_time
		for note in notes:
			if note["estado"] == "acertou": continue
			var y := target_y - (float(note["t"]) - elapsed) * visual_speed
			if y < top - radius or y > end_y: continue
			var lane := int(note["corda"])
			var color: Color = Color8(110,45,45) if note["estado"] == "errou" else GameConfig.STRING_COLORS[lane]
			draw_circle(Vector2(lane_x[lane], y), radius, color)
			draw_arc(Vector2(lane_x[lane], y), radius, 0.0, TAU, 48, Color8(18,20,28), maxf(2.0, 2.0 * scale), true)
			_draw_text(str(note["traste"]), Vector2(lane_x[lane], y + 7.0 * scale), 21.0 * scale, Color.BLACK if note["estado"] != "errou" else Color.WHITE, HORIZONTAL_ALIGNMENT_CENTER)
			_draw_text(GameConfig.SOLFEGE[posmod(int(note["midi"]), 12)], Vector2(lane_x[lane] + (radius + 42.0 * scale) * (1.0 if lane < 5 else -1.0), y + 5.0 * scale), 15.0 * scale, Color8(238,241,250), HORIZONTAL_ALIGNMENT_CENTER)
		if elapsed < GameConfig.COUNTDOWN:
			_draw_text("%.1f" % (GameConfig.COUNTDOWN - elapsed), Vector2(size.x / 2.0, size.y * 0.35), 64.0 * scale, Color.WHITE, HORIZONTAL_ALIGNMENT_CENTER)
	_draw_effects(lane_x, top, end_y, target_y, radius, scale, size)
	_draw_tuner(size, scale)
	if riff_menu_open: _draw_riff_menu(size, scale)

func _draw_riff_menu(size: Vector2, scale: float) -> void:
	draw_rect(Rect2(Vector2.ZERO, size), Color(0.01,0.015,0.035,0.96), true)
	var menu := Rect2(Vector2(size.x * 0.15, size.y * 0.15), Vector2(size.x * 0.70, size.y * 0.70))
	draw_rect(menu, Color8(27,31,43), true, 16.0 * scale)
	draw_rect(menu, Color8(105,117,142), false, 2.0 * scale, true)
	_draw_text("BIBLIOTECA DE RIFFS", Vector2(menu.position.x + 28.0, menu.position.y + 48.0), 30.0 * scale, Color.WHITE)
	_draw_text("Escolha um exercício para começar a tocar", Vector2(menu.position.x + 28.0, menu.position.y + 78.0), 18.0 * scale, MUTED)
	var visible_count := maxi(1, int((menu.size.y - 140.0) / 118.0))
	var count := mini(visible_count, riff_keys.size() - riff_scroll)
	for i in count:
		var key_index := riff_scroll + i
		var key := riff_keys[key_index]
		var card := Rect2(menu.position.x + 24.0, menu.position.y + 100.0 + i * 118.0, menu.size.x - 48.0, 110.0)
		var selected := key == selected_riff
		var focused := key_index == riff_focus
		draw_rect(card, Color8(39,78,66) if selected else Color8(38,43,57), true, 10.0)
		draw_rect(card, Color8(92,227,160) if selected else (Color8(255,204,102) if focused else Color8(72,82,108)), false, 2.0 * scale, true)
		_draw_text(str(riffs[key]["nome"]), Vector2(card.position.x + 22.0, card.position.y + 34.0), 21.0 * scale, Color.WHITE)
		var description := "%d BPM  •  %s" % [riffs[key]["bpm"], riffs[key]["descricao"]]
		var description_lines := _wrap_menu_description(description, card.size.x - 44.0, 15.0 * scale, 2)
		for line_index in description_lines.size():
			_draw_text(description_lines[line_index], Vector2(card.position.x + 22.0, card.position.y + 64.0 + line_index * 18.0 * scale), 15.0 * scale, MUTED)
	_draw_text("Setas para navegar  •  Enter para escolher  •  Esc para fechar", Vector2(menu.get_center().x, menu.end.y - 22.0), 16.0 * scale, MUTED, HORIZONTAL_ALIGNMENT_CENTER)

func _wrap_menu_description(text: String, max_width: float, font_size: float, max_lines: int) -> Array[String]:
	var result: Array[String] = []
	var font := ThemeDB.fallback_font
	if font == null:
		var fallback: Array[String] = [text]
		return fallback
	var pixel_size := maxi(10, roundi(font_size))
	var current := ""
	var truncated := false
	for word in text.split(" ", false):
		var candidate := word if current.is_empty() else current + " " + word
		if font.get_string_size(candidate, HORIZONTAL_ALIGNMENT_LEFT, -1.0, pixel_size).x > max_width and not current.is_empty():
			result.append(current)
			current = word
			if result.size() >= max_lines:
				truncated = true
				break
		else:
			current = candidate
	if not current.is_empty() and result.size() < max_lines:
		result.append(current)
	if truncated and not result.is_empty():
		var last := result.size() - 1
		var shortened := result[last]
		while not shortened.is_empty() and font.get_string_size(shortened + "…", HORIZONTAL_ALIGNMENT_LEFT, -1.0, pixel_size).x > max_width:
			shortened = shortened.left(shortened.length() - 1).strip_edges()
		result[last] = shortened + "…"
	return result

func _draw_effects(lanes: Array[float], top: float, end_y: float, target_y: float, radius: float, scale: float, size: Vector2) -> void:
	for effect in effects:
		var alpha := 1.0 - float(effect["age"]) / GameConfig.EFFECT_DURATION
		var color: Color = GameConfig.GREEN if effect["ok"] else GameConfig.RED
		color.a = alpha * 0.22
		draw_rect(Rect2(lanes[int(effect["corda"])] - 35.0 * scale, top, 70.0 * scale, end_y - top), color, true)
		if effect["ok"]:
			var ring := radius * (1.0 + 1.6 * (1.0 - alpha))
			color.a = alpha
			draw_arc(Vector2(lanes[int(effect["corda"])], target_y), ring, 0.0, TAU, 48, color, 5.0 * scale, true)
	if not effects.is_empty():
		var effect: Dictionary = effects.back()
		var color: Color = GameConfig.GREEN if effect["ok"] else GameConfig.RED
		color.a = 1.0 - float(effect["age"]) / GameConfig.EFFECT_DURATION
		_draw_text(str(effect["texto"]), Vector2(size.x / 2.0, top - 18.0 * scale), 30.0 * scale, color, HORIZONTAL_ALIGNMENT_CENTER)

func _draw_tuner(size: Vector2, scale: float) -> void:
	var center := Vector2(size.x / 2.0, size.y * 0.91)
	var half := 150.0 * scale
	_draw_line(center + Vector2(-half, 0), center + Vector2(half, 0), Color8(90,90,90), 2.0 * scale)
	_draw_line(center + Vector2(0,-12.0 * scale), center + Vector2(0,12.0 * scale), Color8(160,160,160), 2.0 * scale)
	if mic.midi == null:
		_draw_text("--", center + Vector2(0,-30.0 * scale), 36.0 * scale, Color8(120,120,120), HORIZONTAL_ALIGNMENT_CENTER)
		return
	var midi_value := float(mic.midi)
	var rounded := roundi(midi_value)
	var cents := (midi_value - rounded) * 100.0
	var color := GameConfig.GREEN if absf(cents) <= GameConfig.TOLERANCE_CENTS * 0.5 else Color8(240,190,50)
	_draw_text(GameConfig.note_name(rounded), center + Vector2(0,-30.0 * scale), 36.0 * scale, color, HORIZONTAL_ALIGNMENT_CENTER)
	draw_circle(center + Vector2(clampf(cents, -50.0, 50.0) / 50.0 * half, 0), 9.0 * scale, color)
	_draw_text("%+.0f cents" % cents, center + Vector2(0,28.0 * scale), 16.0 * scale, MUTED, HORIZONTAL_ALIGNMENT_CENTER)

func _minimum_lane_speed(radius: float) -> float:
	var last_time := {}
	var shortest := INF
	var sorted_notes := notes.duplicate()
	sorted_notes.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return float(a["t"]) < float(b["t"]))
	for note in sorted_notes:
		var lane := int(note["corda"])
		if last_time.has(lane):
			var interval := float(note["t"]) - float(last_time[lane])
			if interval > 0.0:
				shortest = minf(shortest, interval)
		last_time[lane] = note["t"]
	return 0.0 if is_inf(shortest) else (2.0 * radius + 8.0) / shortest

func _draw_text(text: String, position: Vector2, size: float, color: Color, align: HorizontalAlignment = HORIZONTAL_ALIGNMENT_LEFT) -> void:
	var font := ThemeDB.fallback_font
	if font == null: return
	var font_size := maxi(10, roundi(size))
	var draw_position := position
	var text_width := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1.0, font_size).x
	if align == HORIZONTAL_ALIGNMENT_CENTER:
		draw_position.x -= text_width * 0.5
	elif align == HORIZONTAL_ALIGNMENT_RIGHT:
		draw_position.x -= text_width
	draw_string(font, draw_position, text, HORIZONTAL_ALIGNMENT_LEFT, -1.0, font_size, color)

func _draw_line(from: Vector2, to: Vector2, color: Color, width: float) -> void:
	draw_line(from, to, color, width, true)
