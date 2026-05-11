extends Control

@export_file("*.json") var course_path: String = "res://data/sample_course.json"
@export_file("*.wav", "*.ogg", "*.mp3") var music_path: String = ""
@export var prompt_lead_seconds: float = 2.0
@export var lane_travel_pixels: float = 500.0

@onready var audio_player: AudioStreamPlayer = $AudioPlayer
@onready var lane_1_prompt_layer: Control = %Lane1PromptLayer
@onready var lane_2_prompt_layer: Control = %Lane2PromptLayer
@onready var lane_1_panel: PanelContainer = %LanePlayer1
@onready var lane_2_panel: PanelContainer = %LanePlayer2
@onready var timeline_label: Label = %TimelineLabel
@onready var status_label: Label = %StatusLabel

var _events: Array[Dictionary] = []
var _spawn_index: int = 0
var _timeline_seconds: float = 0.0
var _song_duration_seconds: float = 0.0
var _start_ticks_msec: int = 0
var _active_prompts: Array[Label] = []

func _ready() -> void:
    _configure_lane_styles()

    var course: Dictionary = _load_course(course_path)
    if course.is_empty():
        status_label.text = "Unable to load course JSON"
        set_process(false)
        return

    _events = course.get("events", [])
    _events.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
        return float(a.get("time_seconds", 0.0)) < float(b.get("time_seconds", 0.0))
    )

    var song_data: Dictionary = course.get("song", {})
    _song_duration_seconds = float(song_data.get("duration_seconds", 0.0))

    _load_music(song_data.get("id", ""))
    _start_ticks_msec = Time.get_ticks_msec()
    if audio_player.stream != null:
        audio_player.play()

    status_label.text = "Loaded %d prompts" % _events.size()
    set_process(true)

func _process(_delta: float) -> void:
    _timeline_seconds = _read_timeline_seconds()
    _spawn_due_prompts()
    _update_prompt_positions()
    _cleanup_finished_prompts()
    _update_debug_labels()

func _configure_lane_styles() -> void:
    var lane_1_style := StyleBoxFlat.new()
    lane_1_style.bg_color = Color(0.129, 0.2, 0.349)
    lane_1_style.border_width_all = 2
    lane_1_style.border_color = Color(0.59, 0.76, 1.0)
    lane_1_style.corner_radius_top_left = 8
    lane_1_style.corner_radius_top_right = 8
    lane_1_style.corner_radius_bottom_left = 8
    lane_1_style.corner_radius_bottom_right = 8
    lane_1_panel.add_theme_stylebox_override("panel", lane_1_style)

    var lane_2_style := StyleBoxFlat.new()
    lane_2_style.bg_color = Color(0.176, 0.129, 0.298)
    lane_2_style.border_width_all = 2
    lane_2_style.border_color = Color(0.9, 0.6, 1.0)
    lane_2_style.corner_radius_top_left = 8
    lane_2_style.corner_radius_top_right = 8
    lane_2_style.corner_radius_bottom_left = 8
    lane_2_style.corner_radius_bottom_right = 8
    lane_2_panel.add_theme_stylebox_override("panel", lane_2_style)

func _load_course(path: String) -> Dictionary:
    if path.is_empty():
        push_error("Course path is empty")
        return {}

    if not FileAccess.file_exists(path):
        push_error("Course file not found: %s" % path)
        return {}

    var file := FileAccess.open(path, FileAccess.READ)
    if file == null:
        push_error("Failed to open course file: %s" % path)
        return {}

    var parsed := JSON.parse_string(file.get_as_text())
    if typeof(parsed) != TYPE_DICTIONARY:
        push_error("Course JSON root must be an object: %s" % path)
        return {}

    var course: Dictionary = parsed
    if not course.has("events") or typeof(course["events"]) != TYPE_ARRAY:
        push_error("Course JSON must include an events array")
        return {}

    return course

func _load_music(song_id: String) -> void:
    var candidates: Array[String] = []
    if not music_path.is_empty():
        candidates.append(music_path)
    if not song_id.is_empty():
        candidates.append(song_id)

    for candidate in candidates:
        if ResourceLoader.exists(candidate):
            var stream := load(candidate)
            if stream is AudioStream:
                audio_player.stream = stream
                status_label.text = "Loaded audio: %s" % candidate
                return

    if not candidates.is_empty():
        push_warning("Audio stream not found for candidates: %s" % str(candidates))

func _read_timeline_seconds() -> float:
    if audio_player.playing:
        return audio_player.get_playback_position()
    return float(Time.get_ticks_msec() - _start_ticks_msec) / 1000.0

func _spawn_due_prompts() -> void:
    while _spawn_index < _events.size():
        var event: Dictionary = _events[_spawn_index]
        var event_time := float(event.get("time_seconds", 0.0))
        if _timeline_seconds < event_time - prompt_lead_seconds:
            break

        _spawn_prompt(event, event_time)
        _spawn_index += 1

func _spawn_prompt(event: Dictionary, event_time: float) -> void:
    var lane_id := str(event.get("player", "player_1"))
    var lane_layer: Control = lane_1_prompt_layer
    if lane_id == "player_2":
        lane_layer = lane_2_prompt_layer

    var prompt := Label.new()
    prompt.text = "%s  x%d" % [str(event.get("move", "move")), int(event.get("intensity", 1))]
    prompt.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
    prompt.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    prompt.position = Vector2(0.0, -30.0)
    prompt.custom_minimum_size = Vector2(0.0, 30.0)
    prompt.add_theme_color_override("font_color", Color(1.0, 0.98, 0.85))
    prompt.add_theme_color_override("font_outline_color", Color(0.05, 0.08, 0.12))
    prompt.add_theme_constant_override("outline_size", 3)
    prompt.set_meta("target_time", event_time)
    lane_layer.add_child(prompt)
    _active_prompts.append(prompt)

func _update_prompt_positions() -> void:
    for prompt in _active_prompts:
        if not is_instance_valid(prompt):
            continue

        var target_time := float(prompt.get_meta("target_time"))
        var spawn_time := target_time - prompt_lead_seconds
        var progress := 1.0
        if prompt_lead_seconds > 0.0:
            progress = clamp((_timeline_seconds - spawn_time) / prompt_lead_seconds, 0.0, 1.3)

        prompt.position.y = lerp(-30.0, lane_travel_pixels, progress)
        if _timeline_seconds > target_time:
            var fade := clamp((_timeline_seconds - target_time) / 0.6, 0.0, 1.0)
            prompt.modulate.a = 1.0 - fade

func _cleanup_finished_prompts() -> void:
    var remaining: Array[Label] = []
    for prompt in _active_prompts:
        if not is_instance_valid(prompt):
            continue

        var target_time := float(prompt.get_meta("target_time"))
        if _timeline_seconds > target_time + 0.7:
            prompt.queue_free()
        else:
            remaining.append(prompt)

    _active_prompts = remaining

func _update_debug_labels() -> void:
    timeline_label.text = "Timeline: %.2fs" % _timeline_seconds
    if _song_duration_seconds > 0.0:
        status_label.text = "Events %d/%d • Duration %.2fs" % [_spawn_index, _events.size(), _song_duration_seconds]
    else:
        status_label.text = "Events %d/%d" % [_spawn_index, _events.size()]
