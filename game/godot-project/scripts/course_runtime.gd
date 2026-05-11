extends Control

const PLAYER_1 := "player_1"
const PLAYER_2 := "player_2"

const PERFECT_SCORE := 1000
const GOOD_SCORE := 500
const OK_SCORE := 250

@export_file("*.json") var course_path: String = "res://data/sample_course.json"
@export_file("*.wav", "*.ogg", "*.mp3") var music_path: String = ""
@export var prompt_lead_seconds: float = 2.0
@export var lane_travel_pixels: float = 500.0
@export var prompt_overshoot_ratio: float = 1.3
@export var prompt_fade_seconds: float = 0.6
@export var prompt_cleanup_delay: float = 0.7
@export var perfect_window_seconds: float = 0.15
@export var good_window_seconds: float = 0.3
@export var early_late_window_seconds: float = 0.5
@export var feedback_hold_seconds: float = 0.9
@export var camera_input_enabled: bool = true
@export var camera_websocket_url: String = "ws://127.0.0.1:8765"
@export var camera_min_confidence: float = 0.55
@export var camera_reconnect_seconds: float = 2.0

@onready var audio_player: AudioStreamPlayer = $AudioPlayer
@onready var lane_1_prompt_layer: Control = %Lane1PromptLayer
@onready var lane_2_prompt_layer: Control = %Lane2PromptLayer
@onready var lane_1_panel: PanelContainer = %LanePlayer1
@onready var lane_2_panel: PanelContainer = %LanePlayer2
@onready var lane_1_score_label: Label = %Lane1ScoreLabel
@onready var lane_2_score_label: Label = %Lane2ScoreLabel
@onready var lane_1_combo_label: Label = %Lane1ComboLabel
@onready var lane_2_combo_label: Label = %Lane2ComboLabel
@onready var lane_1_feedback_label: Label = %Lane1FeedbackLabel
@onready var lane_2_feedback_label: Label = %Lane2FeedbackLabel
@onready var timeline_label: Label = $UI/Header/TimelineLabel
@onready var status_label: Label = $UI/Header/StatusLabel
@onready var camera_status_label: Label = $UI/Header/CameraStatusLabel
@onready var results_overlay: Control = %ResultsOverlay
@onready var results_title_label: Label = %ResultsTitleLabel
@onready var results_body_label: Label = %ResultsBodyLabel

var _events: Array[Dictionary] = []
var _spawn_index: int = 0
var _timeline_seconds: float = 0.0
var _song_duration_seconds: float = 0.0
var _course_end_seconds: float = 0.0
var _start_ticks_msec: int = 0
var _active_prompts: Array[Label] = []
var _player_state: Dictionary = {}
var _results_shown: bool = false
var _camera_peer: WebSocketPeer = null
var _next_camera_reconnect_msec: int = 0
var _camera_connected: bool = false
var _camera_player_status: Dictionary = {
    PLAYER_1: {"visible": false, "calibrated": false, "confidence": 0.0},
    PLAYER_2: {"visible": false, "calibrated": false, "confidence": 0.0},
}
var _paused: bool = false

func _ready() -> void:
    _player_state = {
        PLAYER_1: _make_player_state(),
        PLAYER_2: _make_player_state(),
    }

    _configure_lane_styles()
    _update_hud()
    results_overlay.visible = false

    var course: Dictionary = _load_course(course_path)
    if course.is_empty():
        status_label.text = "Unable to load course JSON"
        set_process(false)
        set_process_unhandled_input(false)
        return

    _events.clear()
    for event_data in course.get("events", []):
        if event_data is Dictionary:
            _events.append(event_data)
    _events.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
        return float(a.get("time_seconds", 0.0)) < float(b.get("time_seconds", 0.0))
    )

    var song_data: Dictionary = course.get("song", {})
    _song_duration_seconds = float(song_data.get("duration_seconds", 0.0))
    _course_end_seconds = max(_song_duration_seconds, _last_event_time() + early_late_window_seconds + prompt_cleanup_delay)

    _load_music(song_data.get("id", ""))
    if audio_player.stream != null:
        audio_player.play()
    _start_ticks_msec = Time.get_ticks_msec()

    _update_status_label()
    _connect_camera()
    set_process(true)
    set_process_unhandled_input(true)

func _process(_delta: float) -> void:
    _poll_camera()
    if _paused:
        _update_status_label()
        _update_camera_status_label()
        return

    _timeline_seconds = _read_timeline_seconds()
    _spawn_due_prompts()
    _handle_missed_prompts()
    _update_prompt_positions()
    _cleanup_finished_prompts()
    _update_hud()
    _update_feedback_labels()
    _update_status_label()
    _update_camera_status_label()

    if not _results_shown and _timeline_seconds >= _course_end_seconds and _all_prompts_resolved():
        _show_results()

func _unhandled_input(event: InputEvent) -> void:
    if not (event is InputEventKey):
        return

    var key_event: InputEventKey = event
    if not key_event.pressed or key_event.echo:
        return

    var keycode := key_event.physical_keycode
    if keycode == 0:
        keycode = key_event.keycode

    if keycode == KEY_R:
        get_tree().reload_current_scene()
        get_viewport().set_input_as_handled()
        return

    if keycode == KEY_ESCAPE or keycode == KEY_P:
        _toggle_pause()
        get_viewport().set_input_as_handled()
        return

    if _results_shown or _paused:
        return

    var action_event := _normalize_keyboard_action(key_event)
    if action_event.is_empty():
        return

    _handle_action_input(action_event)
    get_viewport().set_input_as_handled()

func _configure_lane_styles() -> void:
    var lane_1_style := StyleBoxFlat.new()
    lane_1_style.bg_color = Color(0.129, 0.2, 0.349)
    lane_1_style.set_border_width_all(2)
    lane_1_style.border_color = Color(0.59, 0.76, 1.0)
    lane_1_style.set_corner_radius_all(8)
    lane_1_panel.add_theme_stylebox_override("panel", lane_1_style)

    var lane_2_style := StyleBoxFlat.new()
    lane_2_style.bg_color = Color(0.176, 0.129, 0.298)
    lane_2_style.set_border_width_all(2)
    lane_2_style.border_color = Color(0.9, 0.6, 1.0)
    lane_2_style.set_corner_radius_all(8)
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

    var parsed: Variant = JSON.parse_string(file.get_as_text())
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
    var lane_id := str(event.get("player", PLAYER_1))
    var lane_layer: Control = lane_1_prompt_layer
    if lane_id == PLAYER_2:
        lane_layer = lane_2_prompt_layer

    var prompt := Label.new()
    prompt.text = "%s  x%d" % [_display_move_name(str(event.get("move", "move"))), int(event.get("intensity", 1))]
    prompt.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
    prompt.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    prompt.position = Vector2(0.0, -30.0)
    prompt.custom_minimum_size = Vector2(0.0, 30.0)
    prompt.add_theme_color_override("font_color", Color(1.0, 0.98, 0.85))
    prompt.add_theme_color_override("font_outline_color", Color(0.05, 0.08, 0.12))
    prompt.add_theme_constant_override("outline_size", 3)
    prompt.set_meta("target_time", event_time)
    prompt.set_meta("player", lane_id)
    prompt.set_meta("move", str(event.get("move", "")))
    prompt.set_meta("resolved", false)
    lane_layer.add_child(prompt)
    _active_prompts.append(prompt)

func _normalize_keyboard_action(event: InputEventKey) -> Dictionary:
    var keycode := event.physical_keycode
    if keycode == 0:
        keycode = event.keycode

    match keycode:
        KEY_A:
            return _make_action_event(PLAYER_1, "dodge_left")
        KEY_D:
            return _make_action_event(PLAYER_1, "dodge_right")
        KEY_W:
            return _make_action_event(PLAYER_1, "jump")
        KEY_S:
            return _make_action_event(PLAYER_1, "duck")
        KEY_LEFT:
            return _make_action_event(PLAYER_2, "dodge_left")
        KEY_RIGHT:
            return _make_action_event(PLAYER_2, "dodge_right")
        KEY_UP:
            return _make_action_event(PLAYER_2, "jump")
        KEY_DOWN:
            return _make_action_event(PLAYER_2, "duck")
        _:
            return {}

func _make_action_event(player_id: String, move: String) -> Dictionary:
    return {
        "player": player_id,
        "move": move,
        "source": "keyboard",
        "time_seconds": _timeline_seconds,
    }

func _handle_action_input(action_event: Dictionary) -> void:
    var player_id := str(action_event.get("player", PLAYER_1))
    var move := str(action_event.get("move", ""))
    var source := str(action_event.get("source", "keyboard"))
    var prompt := _find_closest_prompt(player_id)
    if prompt == null:
        return

    var expected_move := str(prompt.get_meta("move"))
    if expected_move != move:
        if source == "camera":
            return
        _resolve_prompt(prompt, player_id, "Miss", 0, Color(1.0, 0.45, 0.45), true)
        return

    var target_time := float(prompt.get_meta("target_time"))
    var offset := _timeline_seconds - target_time
    var absolute_offset := absf(offset)
    if absolute_offset <= perfect_window_seconds:
        _resolve_prompt(prompt, player_id, "Perfect", PERFECT_SCORE, Color(0.45, 1.0, 0.68))
    elif absolute_offset <= good_window_seconds:
        _resolve_prompt(prompt, player_id, "Good", GOOD_SCORE, Color(0.98, 0.88, 0.4))
    elif absolute_offset <= early_late_window_seconds:
        var label := "Late"
        if offset < 0.0:
            label = "Early"
        _resolve_prompt(prompt, player_id, label, OK_SCORE, Color(0.65, 0.83, 1.0))

func _find_closest_prompt(player_id: String) -> Label:
    var best_prompt: Label = null
    var best_offset := INF

    for prompt in _active_prompts:
        if not is_instance_valid(prompt):
            continue
        if bool(prompt.get_meta("resolved", false)):
            continue
        if str(prompt.get_meta("player", "")) != player_id:
            continue

        var target_time := float(prompt.get_meta("target_time"))
        var absolute_offset := absf(_timeline_seconds - target_time)
        if absolute_offset > early_late_window_seconds:
            continue
        if absolute_offset < best_offset:
            best_offset = absolute_offset
            best_prompt = prompt

    return best_prompt

func _handle_missed_prompts() -> void:
    for prompt in _active_prompts:
        if not is_instance_valid(prompt):
            continue
        if bool(prompt.get_meta("resolved", false)):
            continue

        var target_time := float(prompt.get_meta("target_time"))
        if _timeline_seconds > target_time + early_late_window_seconds:
            _resolve_prompt(
                prompt,
                str(prompt.get_meta("player", PLAYER_1)),
                "Miss",
                0,
                Color(1.0, 0.45, 0.45),
                true
            )

func _resolve_prompt(
    prompt: Label,
    player_id: String,
    judgment: String,
    points: int,
    color: Color,
    counts_as_miss: bool = false
) -> void:
    prompt.set_meta("resolved", true)
    prompt.set_meta("result_time", _timeline_seconds)
    prompt.text = "%s • %s" % [_display_move_name(str(prompt.get_meta("move", ""))), judgment]
    prompt.modulate = color

    var state: Dictionary = _player_state.get(player_id, _make_player_state())
    if counts_as_miss:
        state["combo"] = 0
        state["misses"] = int(state.get("misses", 0)) + 1
    else:
        state["combo"] = int(state.get("combo", 0)) + 1
        state["score"] = int(state.get("score", 0)) + points
        state["hits"] = int(state.get("hits", 0)) + 1
        if int(state["combo"]) > int(state.get("max_combo", 0)):
            state["max_combo"] = state["combo"]
        if points > int(state.get("best_points", -1)):
            state["best_points"] = points
            state["best_moment"] = {
                "move": str(prompt.get_meta("move", "")),
                "judgment": judgment,
                "time_seconds": float(prompt.get_meta("target_time", 0.0)),
                "points": points,
            }

    state["feedback_text"] = judgment
    if points > 0:
        state["feedback_text"] = "%s +%d" % [judgment, points]
    state["feedback_color"] = color
    state["feedback_until"] = _timeline_seconds + feedback_hold_seconds
    _player_state[player_id] = state

func _update_prompt_positions() -> void:
    for prompt in _active_prompts:
        if not is_instance_valid(prompt):
            continue

        var target_time := float(prompt.get_meta("target_time"))
        var spawn_time := target_time - prompt_lead_seconds
        var progress := 1.0
        if prompt_lead_seconds > 0.0:
            progress = clamp((_timeline_seconds - spawn_time) / prompt_lead_seconds, 0.0, prompt_overshoot_ratio)

        prompt.position.y = lerp(-30.0, lane_travel_pixels, progress)

        var fade_anchor: float = target_time
        if bool(prompt.get_meta("resolved", false)):
            fade_anchor = max(fade_anchor, float(prompt.get_meta("result_time", target_time)))
        if _timeline_seconds > fade_anchor:
            var fade: float = clamp((_timeline_seconds - fade_anchor) / max(prompt_fade_seconds, 0.01), 0.0, 1.0)
            prompt.modulate.a = 1.0 - fade

func _cleanup_finished_prompts() -> void:
    var remaining: Array[Label] = []
    for prompt in _active_prompts:
        if not is_instance_valid(prompt):
            continue

        var target_time := float(prompt.get_meta("target_time"))
        var cleanup_at := target_time + prompt_cleanup_delay
        if bool(prompt.get_meta("resolved", false)):
            cleanup_at = max(cleanup_at, float(prompt.get_meta("result_time", target_time)) + prompt_cleanup_delay)

        if _timeline_seconds > cleanup_at:
            prompt.queue_free()
        else:
            remaining.append(prompt)

    _active_prompts = remaining

func _update_hud() -> void:
    var player_1_state: Dictionary = _player_state.get(PLAYER_1, _make_player_state())
    var player_2_state: Dictionary = _player_state.get(PLAYER_2, _make_player_state())

    lane_1_score_label.text = "Score: %d" % int(player_1_state.get("score", 0))
    lane_2_score_label.text = "Score: %d" % int(player_2_state.get("score", 0))
    lane_1_combo_label.text = "Combo: %d  •  Misses: %d" % [int(player_1_state.get("combo", 0)), int(player_1_state.get("misses", 0))]
    lane_2_combo_label.text = "Combo: %d  •  Misses: %d" % [int(player_2_state.get("combo", 0)), int(player_2_state.get("misses", 0))]
    timeline_label.text = "Timeline: %.2fs" % _timeline_seconds

func _update_feedback_labels() -> void:
    _update_feedback_label(lane_1_feedback_label, _player_state.get(PLAYER_1, {}))
    _update_feedback_label(lane_2_feedback_label, _player_state.get(PLAYER_2, {}))

func _update_feedback_label(label: Label, state: Dictionary) -> void:
    if _timeline_seconds > float(state.get("feedback_until", -1.0)):
        label.text = ""
        return

    label.text = str(state.get("feedback_text", ""))
    label.modulate = state.get("feedback_color", Color.WHITE)

func _update_status_label() -> void:
    if _results_shown:
        status_label.text = "Round complete • Press R to try again"
        return

    if _paused:
        status_label.text = "Paused • Press P or Esc to resume • Press R to restart"
        return

    status_label.text = "A/W/S/D vs Arrow Keys • P pause • R restart • Perfect ±%.0fms • Good ±%.0fms • Early/Late ±%.0fms • Events %d/%d" % [
        perfect_window_seconds * 1000.0,
        good_window_seconds * 1000.0,
        early_late_window_seconds * 1000.0,
        _spawn_index,
        _events.size(),
    ]

func _toggle_pause() -> void:
    if _results_shown:
        return
    _paused = not _paused
    if audio_player.stream != null:
        audio_player.stream_paused = _paused

func _connect_camera() -> void:
    if not camera_input_enabled:
        return

    _camera_peer = WebSocketPeer.new()
    var err := _camera_peer.connect_to_url(camera_websocket_url)
    if err != OK:
        _camera_peer = null
        _camera_connected = false
        _next_camera_reconnect_msec = Time.get_ticks_msec() + int(camera_reconnect_seconds * 1000.0)

func _poll_camera() -> void:
    if not camera_input_enabled:
        return

    if _camera_peer == null:
        if Time.get_ticks_msec() >= _next_camera_reconnect_msec:
            _connect_camera()
        return

    _camera_peer.poll()
    var state := _camera_peer.get_ready_state()
    if state == WebSocketPeer.STATE_OPEN:
        _camera_connected = true
        while _camera_peer.get_available_packet_count() > 0:
            var packet := _camera_peer.get_packet()
            _handle_camera_packet(packet.get_string_from_utf8())
    elif state == WebSocketPeer.STATE_CLOSED:
        _camera_connected = false
        _camera_peer = null
        _next_camera_reconnect_msec = Time.get_ticks_msec() + int(camera_reconnect_seconds * 1000.0)

func _handle_camera_packet(packet_text: String) -> void:
    var parsed: Variant = JSON.parse_string(packet_text)
    if typeof(parsed) != TYPE_DICTIONARY:
        return

    var payload: Dictionary = parsed
    var players = payload.get("players", [])
    if str(payload.get("type", "")) == "status":
        _update_camera_player_status(players)
        return

    if _paused or _results_shown:
        return

    for player in players:
        if not (player is Dictionary):
            continue
        var player_data: Dictionary = player
        var confidence := float(player_data.get("confidence", 0.0))
        if confidence < camera_min_confidence:
            continue

        var player_id := _camera_player_id_to_runtime(int(player_data.get("id", 0)))
        if player_id.is_empty():
            continue

        var move := _camera_action_to_move(str(player_data.get("action", "")))
        if move.is_empty():
            continue

        _handle_action_input({
            "player": player_id,
            "move": move,
            "source": "camera",
            "time_seconds": _timeline_seconds,
            "confidence": confidence,
        })

func _update_camera_player_status(players) -> void:
    for player in players:
        if not (player is Dictionary):
            continue
        var player_data: Dictionary = player
        var player_id := _camera_player_id_to_runtime(int(player_data.get("id", 0)))
        if player_id.is_empty():
            continue

        _camera_player_status[player_id] = {
            "visible": bool(player_data.get("visible", false)),
            "calibrated": bool(player_data.get("calibrated", false)),
            "confidence": float(player_data.get("confidence", 0.0)),
        }

func _camera_player_id_to_runtime(player_id: int) -> String:
    if player_id == 1:
        return PLAYER_1
    if player_id == 2:
        return PLAYER_2
    return ""

func _camera_action_to_move(action: String) -> String:
    if action in ["jump", "duck", "dodge_left", "dodge_right"]:
        return action
    if action == "leanLeft":
        return "dodge_left"
    if action == "leanRight":
        return "dodge_right"
    return ""

func _update_camera_status_label() -> void:
    if not camera_input_enabled:
        camera_status_label.text = "Camera input: off"
        return

    var connection_text := "connecting"
    if _camera_connected:
        connection_text = "connected"

    camera_status_label.text = "Camera: %s • P1 %s • P2 %s" % [
        connection_text,
        _format_camera_player_status(PLAYER_1),
        _format_camera_player_status(PLAYER_2),
    ]

func _format_camera_player_status(player_id: String) -> String:
    var status: Dictionary = _camera_player_status.get(player_id, {})
    if not bool(status.get("visible", false)):
        return "lost"
    if not bool(status.get("calibrated", false)):
        return "calibrating"
    return "ready %.0f%%" % (float(status.get("confidence", 0.0)) * 100.0)

func _display_move_name(move: String) -> String:
    match move:
        "jump":
            return "Jump"
        "duck":
            return "Duck"
        "dodge_left":
            return "Move Left"
        "dodge_right":
            return "Move Right"
        _:
            return move.capitalize()

func _show_results() -> void:
    _results_shown = true
    results_overlay.visible = true
    results_title_label.text = _build_results_title()
    results_body_label.text = "%s\n\n%s" % [
        _format_player_results(PLAYER_1, "Player 1"),
        _format_player_results(PLAYER_2, "Player 2"),
    ]

func _build_results_title() -> String:
    var player_1_score := int(_player_state.get(PLAYER_1, {}).get("score", 0))
    var player_2_score := int(_player_state.get(PLAYER_2, {}).get("score", 0))
    if player_1_score == player_2_score:
        return "Results • It's a tie!"
    if player_1_score > player_2_score:
        return "Results • Player 1 wins!"
    return "Results • Player 2 wins!"

func _format_player_results(player_id: String, player_name: String) -> String:
    var state: Dictionary = _player_state.get(player_id, _make_player_state())
    var best_summary := "No scored moments"
    var best_moment: Dictionary = state.get("best_moment", {})
    if not best_moment.is_empty():
        best_summary = "%s @ %.2fs (%s, +%d)" % [
            str(best_moment.get("move", "")),
            float(best_moment.get("time_seconds", 0.0)),
            str(best_moment.get("judgment", "")),
            int(best_moment.get("points", 0)),
        ]

    return "%s\nScore: %d\nMax combo: %d\nMisses: %d\nBest moment: %s" % [
        player_name,
        int(state.get("score", 0)),
        int(state.get("max_combo", 0)),
        int(state.get("misses", 0)),
        best_summary,
    ]

func _all_prompts_resolved() -> bool:
    if _spawn_index < _events.size():
        return false

    for prompt in _active_prompts:
        if is_instance_valid(prompt) and not bool(prompt.get_meta("resolved", false)):
            return false

    return true

func _last_event_time() -> float:
    var last_event_time := 0.0
    for event in _events:
        last_event_time = max(last_event_time, float(event.get("time_seconds", 0.0)))
    return last_event_time

func _make_player_state() -> Dictionary:
    return {
        "score": 0,
        "combo": 0,
        "max_combo": 0,
        "misses": 0,
        "hits": 0,
        "best_points": -1,
        "best_moment": {},
        "feedback_text": "",
        "feedback_color": Color.WHITE,
        "feedback_until": -1.0,
    }
