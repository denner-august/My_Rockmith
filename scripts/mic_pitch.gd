class_name MicPitch
extends Node

var capture: AudioEffectCapture
var capture_player: AudioStreamPlayer
var monitor_player: AudioStreamPlayer
var monitor_playback: AudioStreamGeneratorPlayback
var monitor_enabled := true
var overdrive := false
var volume := 0.7
var midi: Variant = null
var level := 0.0
var _ring := PackedFloat32Array()
var _write_index := 0
var _poll_clock := 0.0
var _last_output := 0.0
var _bus_name := "GuitarCapture"
var _sample_rate := 44100.0
var _pitch_history: Array[float] = []

func _ready() -> void:
	_ring.resize(GameConfig.ANALYSIS_WINDOW)
	var bus_index := AudioServer.get_bus_index(_bus_name)
	if bus_index < 0:
		AudioServer.add_bus()
		bus_index = AudioServer.get_bus_count() - 1
		AudioServer.set_bus_name(bus_index, _bus_name)
	AudioServer.set_bus_volume_db(bus_index, -80.0)
	capture = AudioEffectCapture.new()
	AudioServer.add_bus_effect(bus_index, capture)
	capture_player = AudioStreamPlayer.new()
	capture_player.stream = AudioStreamMicrophone.new()
	capture_player.bus = _bus_name
	add_child(capture_player)
	monitor_player = AudioStreamPlayer.new()
	var generator := AudioStreamGenerator.new()
	_sample_rate = AudioServer.get_mix_rate()
	generator.mix_rate = _sample_rate
	generator.buffer_length = 0.12
	monitor_player.stream = generator
	add_child(monitor_player)
	monitor_player.play()
	monitor_playback = monitor_player.get_stream_playback() as AudioStreamGeneratorPlayback
	capture_player.play()

func _process(delta: float) -> void:
	_poll_clock += delta
	if _poll_clock < 0.045:
		return
	_poll_clock = 0.0
	if capture == null:
		return
	var available := capture.get_frames_available()
	if available <= 0:
		return
	var frames := capture.get_buffer(mini(available, 4096))
	for frame in frames:
		var sample := (frame.x + frame.y) * 0.5
		_ring[_write_index] = sample
		_write_index = (_write_index + 1) % _ring.size()
	_process_monitor(frames)
	var result := _detect_pitch()
	if result[0] != null:
		_pitch_history.append(float(result[0]))
	else:
		_pitch_history.append(-1.0)
	if _pitch_history.size() > 3:
		_pitch_history.pop_front()
	var valid: Array[float] = []
	for pitch in _pitch_history:
		if pitch >= 0.0:
			valid.append(pitch)
	valid.sort()
	midi = valid[int(valid.size() / 2)] if valid.size() >= 2 else null
	level = result[1]

func _process_monitor(frames: PackedVector2Array) -> void:
	if not monitor_enabled or monitor_playback == null:
		return
	var room := monitor_playback.get_frames_available()
	var out := PackedVector2Array()
	var count := mini(room, frames.size())
	out.resize(count)
	for i in count:
		var sample := (frames[i].x + frames[i].y) * 0.5
		if overdrive:
			sample = tanh(sample * 10.0) * 0.5
		# Filtro passa-baixa simples, mantendo continuidade entre blocos.
		sample = (sample * 3.0 + _last_output * 2.0) / 5.0
		_last_output = sample
		sample = clampf(sample * volume, -1.0, 1.0)
		out[i] = Vector2(sample, sample)
	if count > 0:
		monitor_playback.push_buffer(out)

func _detect_pitch() -> Array:
	var count := _ring.size()
	var mean := 0.0
	for sample in _ring:
		mean += sample
	mean /= count
	var rms := 0.0
	for i in count:
		var centered := _ring[i] - mean
		rms += centered * centered
	rms = sqrt(rms / count)
	if rms < GameConfig.SILENCE_THRESHOLD:
		return [null, rms]
	var min_lag := int(_sample_rate / GameConfig.FMAX)
	var max_lag := mini(int(_sample_rate / GameConfig.FMIN), count - 2)
	var correlations := PackedFloat32Array()
	correlations.resize(max_lag + 1)
	for lag in range(min_lag, max_lag + 1):
		var sum := 0.0
		var limit := count - lag
		for i in range(0, limit, 4):
			var a := _ring[(i + _write_index) % count] - mean
			var b := _ring[(i + lag + _write_index) % count] - mean
			sum += a * b
		correlations[lag] = sum
	var best := 0.0
	for lag in range(min_lag, max_lag + 1):
		best = maxf(best, correlations[lag])
	if best <= 0.0:
		return [null, rms]
	var chosen := -1
	for lag in range(min_lag + 1, max_lag):
		if correlations[lag] > correlations[lag - 1] and correlations[lag] >= correlations[lag + 1] and correlations[lag] >= best * 0.85:
			chosen = lag
			break
	if chosen < 0:
		return [null, rms]
	var left := correlations[chosen - 1]
	var center := correlations[chosen]
	var right := correlations[chosen + 1]
	var denominator := left - 2.0 * center + right
	var offset := 0.0 if is_zero_approx(denominator) else 0.5 * (left - right) / denominator
	var frequency := _sample_rate / (chosen + offset)
	return [69.0 + 12.0 * log(frequency / 440.0) / log(2.0), rms]

func stop() -> void:
	if capture_player:
		capture_player.stop()
	if monitor_player:
		monitor_player.stop()
