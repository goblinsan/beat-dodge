extends Control

const PLAYER_1 := "player_1"
const PLAYER_2 := "player_2"
const ROUND_SETUP := "setup"
const ROUND_COUNTDOWN := "countdown"
const ROUND_PLAYING := "playing"

const PERFECT_SCORE := 1000
const GOOD_SCORE := 500
const OK_SCORE := 250

# Forest-theme obstacle prompt dimensions (in local pixels at scale 1.0)
const PROMPT_W: float = 200.0
const PROMPT_H: float = 150.0
const LOG_PROMPT_SCALE: float = 2.65
const BRANCH_PROMPT_SCALE: float = 4.2
const ROCK_PROMPT_SCALE: float = 2.75
const HORIZON_Y_RATIO: float = 0.40
const JUMP_HIT_Y_RATIO: float = 0.88
const DUCK_HIT_Y_RATIO: float = 0.22
const DODGE_HIT_Y_RATIO: float = 0.82
const FOREGROUND_ACCELERATION_EXPONENT: float = 3.0
const AVATAR_W: float = 126.0
const AVATAR_H: float = 236.0
const AVATAR_ACTION_SECONDS: float = 0.34

@export_file("*.json") var course_path: String = "res://data/sample_course.json"
@export_file("*.wav", "*.ogg", "*.mp3") var music_path: String = ""
@export var prompt_lead_seconds: float = 2.0
@export var lane_travel_pixels: float = 500.0
@export var prompt_overshoot_ratio: float = 1.08
@export var prompt_fade_seconds: float = 0.08
@export var prompt_cleanup_delay: float = 0.24
@export var perfect_window_seconds: float = 0.15
@export var good_window_seconds: float = 0.3
@export var early_late_window_seconds: float = 0.5
@export var feedback_hold_seconds: float = 0.9
@export var pre_round_enabled: bool = true
@export var pre_round_countdown_seconds: float = 3.0
@export var pre_round_require_camera_ready: bool = true
@export var camera_input_enabled: bool = true
@export var camera_websocket_url: String = "ws://127.0.0.1:8765"
@export var camera_min_confidence: float = 0.55
@export var camera_reconnect_seconds: float = 2.0
@export var camera_input_latency_offset_seconds: float = 0.0
@export var camera_status_stale_seconds: float = 1.5

@onready var audio_player: AudioStreamPlayer = $AudioPlayer
@onready var lane_1_prompt_layer: Control = %SharedPromptLayer
@onready var lane_2_prompt_layer: Control = %SharedPromptLayer
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
@onready var ready_overlay: Control = %ReadyOverlay
@onready var ready_title_label: Label = %ReadyTitleLabel
@onready var ready_body_label: Label = %ReadyBodyLabel
@onready var results_overlay: Control = %ResultsOverlay
@onready var results_title_label: Label = %ResultsTitleLabel
@onready var results_body_label: Label = %ResultsBodyLabel

var _events: Array[Dictionary] = []
var _spawn_index: int = 0
var _timeline_seconds: float = 0.0
var _song_duration_seconds: float = 0.0
var _course_end_seconds: float = 0.0
var _start_ticks_msec: int = 0
var _active_prompts: Array[Control] = []
var _player_state: Dictionary = {}
var _results_shown: bool = false
var _round_state: String = ROUND_SETUP
var _countdown_started_msec: int = 0
var _camera_peer: WebSocketPeer = null
var _next_camera_reconnect_msec: int = 0
var _camera_connection_state: String = "disconnected"
var _last_camera_packet_msec: int = 0
var _camera_player_status: Dictionary = {
    PLAYER_1: {"visible": false, "calibrated": false, "confidence": 0.0},
    PLAYER_2: {"visible": false, "calibrated": false, "confidence": 0.0},
}
var _paused: bool = false

# Forest theme
var _forest_scroll_time: float = 0.0
var _forest_shader_mats: Array[ShaderMaterial] = []
var _tex_fallen_log: Texture2D = null
var _tex_low_branch: Texture2D = null
var _tex_rock: Texture2D = null
var _avatar_nodes: Dictionary = {}

func _ready() -> void:
    _player_state = {
        PLAYER_1: _make_player_state(),
        PLAYER_2: _make_player_state(),
    }

    _configure_lane_styles()
    _load_forest_textures()
    _build_forest_backgrounds()
    _build_player_avatars()
    _update_hud()
    results_overlay.visible = false
    ready_overlay.visible = false

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
    _timeline_seconds = 0.0

    _update_status_label()
    _update_ready_overlay()
    _connect_camera()
    set_process(true)
    set_process_unhandled_input(true)

    if not pre_round_enabled:
        _start_round()

func _exit_tree() -> void:
    if audio_player != null:
        audio_player.stop()
        audio_player.stream = null
    if _camera_peer != null:
        _camera_peer.close()
        _camera_peer = null

func _process(delta: float) -> void:
    _poll_camera()
    _expire_stale_camera_status()
    _scroll_forest(delta)
    _update_player_avatars()

    if _round_state == ROUND_SETUP:
        _timeline_seconds = 0.0
        _update_hud()
        _update_status_label()
        _update_camera_status_label()
        _update_ready_overlay()
        if _camera_ready_for_round():
            _begin_countdown()
        return

    if _round_state == ROUND_COUNTDOWN:
        _timeline_seconds = 0.0
        _update_hud()
        _update_status_label()
        _update_camera_status_label()
        _update_ready_overlay()
        if _countdown_seconds_remaining() <= 0.0:
            _start_round()
        return

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
        _mark_input_handled()
        return

    if (keycode == KEY_SPACE or keycode == KEY_ENTER) and _round_state != ROUND_PLAYING:
        _begin_countdown()
        _mark_input_handled()
        return

    if keycode == KEY_ESCAPE or keycode == KEY_P:
        _toggle_pause()
        _mark_input_handled()
        return

    if _results_shown or _paused or _round_state != ROUND_PLAYING:
        return

    var action_event := _normalize_keyboard_action(key_event)
    if action_event.is_empty():
        return

    _handle_action_input(action_event)
    _mark_input_handled()

func _mark_input_handled() -> void:
    var viewport := get_viewport()
    if viewport != null:
        viewport.set_input_as_handled()

func _configure_lane_styles() -> void:
    var lane_1_style := StyleBoxFlat.new()
    lane_1_style.bg_color = Color(0.0, 0.0, 0.0, 0.0)
    lane_1_style.set_border_width_all(2)
    lane_1_style.border_color = Color(0.42, 0.72, 0.28, 0.85)
    lane_1_style.set_corner_radius_all(8)
    lane_1_panel.add_theme_stylebox_override("panel", lane_1_style)

    var lane_2_style := StyleBoxFlat.new()
    lane_2_style.bg_color = Color(0.0, 0.0, 0.0, 0.0)
    lane_2_style.set_border_width_all(2)
    lane_2_style.border_color = Color(0.85, 0.72, 0.28, 0.85)
    lane_2_style.set_corner_radius_all(8)
    lane_2_panel.add_theme_stylebox_override("panel", lane_2_style)

func _try_load_texture(path: String) -> Texture2D:
    var tex := ResourceLoader.load(path, "Texture2D") as Texture2D
    if tex == null:
        push_warning("ForestTheme: could not load texture: %s" % path)
    return tex

func _load_forest_textures() -> void:
    _tex_fallen_log  = _try_load_texture("res://images/fallen-log.png")
    _tex_low_branch  = _try_load_texture("res://images/low-branch.png")
    _tex_rock        = _try_load_texture("res://images/rock.png")

func _build_forest_backgrounds() -> void:
    var shader_res := ResourceLoader.load("res://shaders/forest_floor.gdshader", "Shader") as Shader
    if shader_res == null:
        push_warning("ForestTheme: forest_floor.gdshader not found — skipping background")
        return
    var floor_tex := _try_load_texture("res://images/forrest-floor.png")
    # lane_1_prompt_layer and lane_2_prompt_layer are the same node in shared mode —
    # only add one background.
    var bg := ColorRect.new()
    bg.name = "ForestBackground"
    bg.set_anchors_preset(Control.PRESET_FULL_RECT)
    bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
    var mat := ShaderMaterial.new()
    mat.shader = shader_res
    if floor_tex != null:
        mat.set_shader_parameter("floor_texture", floor_tex)
    mat.set_shader_parameter("horizon_y", HORIZON_Y_RATIO)
    bg.material = mat
    lane_1_prompt_layer.add_child(bg)
    lane_1_prompt_layer.move_child(bg, 0)
    _forest_shader_mats.append(mat)

func _scroll_forest(delta: float) -> void:
    if _forest_shader_mats.is_empty():
        return
    _forest_scroll_time += delta
    for mat in _forest_shader_mats:
        mat.set_shader_parameter("scroll_time", _forest_scroll_time)

func _tex_for_move(move: String) -> Texture2D:
    match move:
        "jump":                   return _tex_fallen_log
        "duck":                   return _tex_low_branch
        "dodge_left", "dodge_right": return _tex_rock
        _:                        return null

func _build_player_avatars() -> void:
    _avatar_nodes[PLAYER_1] = _make_avatar_node(PLAYER_1, Color(0.35, 0.95, 0.45), Color(0.11, 0.38, 0.16))
    _avatar_nodes[PLAYER_2] = _make_avatar_node(PLAYER_2, Color(1.0, 0.78, 0.28), Color(0.43, 0.28, 0.06))
    for player_id in [PLAYER_1, PLAYER_2]:
        var avatar: Control = _avatar_nodes[player_id]
        lane_1_prompt_layer.add_child(avatar)
        avatar.z_index = 650

func _make_avatar_node(player_id: String, primary: Color, dark: Color) -> Control:
    var root := Control.new()
    root.name = "%sAvatar" % player_id
    root.size = Vector2(AVATAR_W, AVATAR_H)
    root.pivot_offset = Vector2(AVATAR_W * 0.5, AVATAR_H)
    root.mouse_filter = Control.MOUSE_FILTER_IGNORE

    var head := ColorRect.new()
    head.name = "Head"
    head.color = primary.lightened(0.12)
    head.position = Vector2(AVATAR_W * 0.34, AVATAR_H * 0.02)
    head.size = Vector2(AVATAR_W * 0.32, AVATAR_H * 0.14)
    head.mouse_filter = Control.MOUSE_FILTER_IGNORE
    root.add_child(head)

    var torso := ColorRect.new()
    torso.name = "Torso"
    torso.color = primary
    torso.position = Vector2(AVATAR_W * 0.28, AVATAR_H * 0.19)
    torso.size = Vector2(AVATAR_W * 0.44, AVATAR_H * 0.34)
    torso.mouse_filter = Control.MOUSE_FILTER_IGNORE
    root.add_child(torso)

    var left_arm := ColorRect.new()
    left_arm.name = "LeftArm"
    left_arm.color = dark
    left_arm.position = Vector2(AVATAR_W * 0.10, AVATAR_H * 0.20)
    left_arm.size = Vector2(AVATAR_W * 0.14, AVATAR_H * 0.34)
    left_arm.mouse_filter = Control.MOUSE_FILTER_IGNORE
    root.add_child(left_arm)

    var right_arm := ColorRect.new()
    right_arm.name = "RightArm"
    right_arm.color = dark
    right_arm.position = Vector2(AVATAR_W * 0.76, AVATAR_H * 0.20)
    right_arm.size = Vector2(AVATAR_W * 0.14, AVATAR_H * 0.34)
    right_arm.mouse_filter = Control.MOUSE_FILTER_IGNORE
    root.add_child(right_arm)

    var left_leg := ColorRect.new()
    left_leg.name = "LeftLeg"
    left_leg.color = dark
    left_leg.position = Vector2(AVATAR_W * 0.30, AVATAR_H * 0.55)
    left_leg.size = Vector2(AVATAR_W * 0.17, AVATAR_H * 0.42)
    left_leg.mouse_filter = Control.MOUSE_FILTER_IGNORE
    root.add_child(left_leg)

    var right_leg := ColorRect.new()
    right_leg.name = "RightLeg"
    right_leg.color = dark
    right_leg.position = Vector2(AVATAR_W * 0.53, AVATAR_H * 0.55)
    right_leg.size = Vector2(AVATAR_W * 0.17, AVATAR_H * 0.42)
    right_leg.mouse_filter = Control.MOUSE_FILTER_IGNORE
    root.add_child(right_leg)

    var name_label := Label.new()
    name_label.name = "NameLabel"
    name_label.text = "P1" if player_id == PLAYER_1 else "P2"
    name_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
    name_label.position = Vector2(0.0, -20.0)
    name_label.size = Vector2(AVATAR_W, 18.0)
    name_label.add_theme_font_size_override("font_size", 16)
    name_label.add_theme_color_override("font_color", Color.WHITE)
    name_label.add_theme_color_override("font_outline_color", Color.BLACK)
    name_label.add_theme_constant_override("outline_size", 3)
    name_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
    root.add_child(name_label)

    return root

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
        if not song_id.begins_with("res://"):
            candidates.append("res://audio/%s" % song_id)

    # If the source song extension is unsupported (for example .m4a),
    # try common Godot-friendly alternatives with the same base name.
    var expanded_candidates: Array[String] = []
    for candidate in candidates:
        expanded_candidates.append(candidate)
        var dot := candidate.rfind(".")
        if dot <= 0:
            continue
        var base := candidate.substr(0, dot)
        expanded_candidates.append("%s.ogg" % base)
        expanded_candidates.append("%s.mp3" % base)
        expanded_candidates.append("%s.wav" % base)

    var unique_candidates: Array[String] = []
    var seen: Dictionary = {}
    for candidate in expanded_candidates:
        if seen.has(candidate):
            continue
        seen[candidate] = true
        unique_candidates.append(candidate)

    for candidate in unique_candidates:
        var stream := _load_audio_stream_candidate(candidate)
        if stream != null:
            audio_player.stream = stream
            return

    if not unique_candidates.is_empty():
        push_warning("Audio stream not found. Try .ogg/.mp3/.wav. Checked: %s" % str(unique_candidates))

func _load_audio_stream_candidate(candidate: String) -> AudioStream:
    if ResourceLoader.exists(candidate):
        var imported_stream := load(candidate)
        if imported_stream is AudioStream:
            return imported_stream

    var path := candidate
    if candidate.begins_with("res://"):
        if not FileAccess.file_exists(candidate):
            return null
        path = ProjectSettings.globalize_path(candidate)

    var ext := candidate.get_extension().to_lower()
    if ext == "ogg":
        return AudioStreamOggVorbis.load_from_file(path)
    if ext == "mp3":
        return AudioStreamMP3.load_from_file(path)
    if ext == "wav":
        return AudioStreamWAV.load_from_file(path)
    return null

func _read_timeline_seconds() -> float:
    if audio_player.playing:
        return audio_player.get_playback_position()
    if _round_state == ROUND_PLAYING:
        return float(Time.get_ticks_msec() - _start_ticks_msec) / 1000.0
    return 0.0

func _spawn_due_prompts() -> void:
    while _spawn_index < _events.size():
        var event: Dictionary = _events[_spawn_index]
        var event_time := float(event.get("time_seconds", 0.0))
        if _timeline_seconds < event_time - prompt_lead_seconds:
            break

        _spawn_prompt(event, event_time)
        _spawn_index += 1

func _spawn_prompt(event: Dictionary, event_time: float) -> void:
    var lane_layer: Control = lane_1_prompt_layer  # shared path — both players see same obstacles
    var move := str(event.get("move", ""))
    var intensity := int(event.get("intensity", 1))

    var obstacle_scale := _base_obstacle_scale(move)
    var pw: float = PROMPT_W * obstacle_scale
    var ph: float = PROMPT_H * obstacle_scale

    # Root control — sized at the base PROMPT dimensions; scaled by perspective each frame.
    var prompt := Control.new()
    prompt.custom_minimum_size = Vector2(pw, ph)
    prompt.size = Vector2(pw, ph)
    prompt.pivot_offset = Vector2(pw * 0.5, ph * 0.5)
    prompt.position = Vector2(0.0, -ph)
    prompt.mouse_filter = Control.MOUSE_FILTER_IGNORE

    # Obstacle image — anchored to fill the prompt rect.
    var img := TextureRect.new()
    img.name = "ObstacleImage"
    img.texture = _tex_for_move(move)
    img.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
    img.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
    img.set_anchors_preset(Control.PRESET_FULL_RECT)
    img.mouse_filter = Control.MOUSE_FILTER_IGNORE
    prompt.add_child(img)

    # Small action label at the bottom of the card.
    var action_label := Label.new()
    action_label.name = "ActionLabel"
    action_label.text = _display_move_name(move).to_upper()
    action_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
    action_label.vertical_alignment = VERTICAL_ALIGNMENT_BOTTOM
    action_label.anchor_left = 0.0
    action_label.anchor_right = 1.0
    action_label.anchor_top = 0.72
    action_label.anchor_bottom = 1.0
    action_label.add_theme_font_size_override("font_size", 18)
    action_label.add_theme_color_override("font_color", Color(1.0, 1.0, 1.0))
    action_label.add_theme_color_override("font_outline_color", Color(0.0, 0.0, 0.0))
    action_label.add_theme_constant_override("outline_size", 4)
    action_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
    prompt.add_child(action_label)

    # x_side: -1 = left lane for dodge_left, 1 = right lane for dodge_right, 0 = centre.
    var x_side: int = 0
    if move == "dodge_left":
        x_side = -1
    elif move == "dodge_right":
        x_side = 1

    prompt.set_meta("target_time", event_time)
    prompt.set_meta("player", "shared")
    prompt.set_meta("move", move)
    prompt.set_meta("intensity", intensity)
    prompt.set_meta("resolved", false)
    prompt.set_meta("x_side", x_side)
    prompt.set_meta("resolved_player_1", false)
    prompt.set_meta("resolved_player_2", false)
    prompt.set_meta("prompt_w", pw)
    prompt.set_meta("prompt_h", ph)
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
    var input_time_seconds := float(action_event.get("time_seconds", _timeline_seconds))
    _set_avatar_action(player_id, move)
    var prompt := _find_closest_prompt(player_id, input_time_seconds)
    if prompt == null:
        return

    var expected_move := str(prompt.get_meta("move"))
    if expected_move != move:
        if source == "camera":
            return
        _resolve_prompt(prompt, player_id, "Miss", 0, Color(1.0, 0.45, 0.45), true)
        return

    var target_time := float(prompt.get_meta("target_time"))
    var offset := input_time_seconds - target_time
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

func _find_closest_prompt(player_id: String, input_time_seconds: float) -> Control:
    var best_prompt: Control = null
    var best_offset := INF

    for prompt in _active_prompts:
        if not is_instance_valid(prompt):
            continue
        if bool(prompt.get_meta("resolved_" + player_id, false)):
            continue

        var target_time := float(prompt.get_meta("target_time"))
        var absolute_offset := absf(input_time_seconds - target_time)
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

        var target_time := float(prompt.get_meta("target_time"))
        if _timeline_seconds > target_time + early_late_window_seconds:
            for pid: String in [PLAYER_1, PLAYER_2]:
                if not bool(prompt.get_meta("resolved_" + pid, false)):
                    _resolve_prompt(prompt, pid, "Miss", 0, Color(1.0, 0.45, 0.45), true)

func _resolve_prompt(
    prompt: Control,
    player_id: String,
    judgment: String,
    points: int,
    color: Color,
    counts_as_miss: bool = false
) -> void:
    prompt.set_meta("resolved_" + player_id, true)
    # Mark fully resolved only once both players have dealt with this obstacle.
    var both_done := bool(prompt.get_meta("resolved_player_1", false)) \
        and bool(prompt.get_meta("resolved_player_2", false))
    if both_done:
        prompt.set_meta("resolved", true)
    prompt.set_meta("result_time", _timeline_seconds)
    _set_prompt_card_result(prompt, judgment)
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

        # Perspective scale grows at a constant rate with travel progress.
        var move := str(prompt.get_meta("move", ""))
        var persp_scale := _perspective_scale_for_progress(move, progress)
        prompt.scale = Vector2(persp_scale, persp_scale)
        prompt.z_index = int(_depth_sort_progress(progress) * 1000.0)

        # X: obstacles begin near the path centre and spread into their lane as they approach.
        var lane_w: float = prompt.get_parent().size.x
        if lane_w <= 0.0:
            lane_w = 300.0
        var horizon_center_x: float = _horizon_center_x(move, lane_w, int(prompt.get_meta("x_side", 0)))
        var hit_center_x: float = _target_center_x(move, lane_w, int(prompt.get_meta("x_side", 0)))
        var visual_center_x: float = _constant_speed_project(horizon_center_x, hit_center_x, progress)
        var pw: float = float(prompt.get_meta("prompt_w", PROMPT_W))
        var ph: float = float(prompt.get_meta("prompt_h", PROMPT_H))
        prompt.pivot_offset = Vector2(pw * 0.5, ph * 0.5)
        prompt.position.x = visual_center_x - pw * 0.5

        # Y: logs pass below the players' feet; branches grow until the camera passes under them.
        var lane_h: float = prompt.get_parent().size.y
        if lane_h <= 0.0:
            lane_h = max(lane_travel_pixels, 680.0)
        var center_y := _prompt_center_y(move, lane_h, ph, persp_scale, progress)
        prompt.position.y = center_y - ph * 0.5

        var pass_by_seconds: float = prompt_lead_seconds * maxf(prompt_overshoot_ratio - 1.0, 0.0)
        var fade_anchor: float = target_time + pass_by_seconds
        if bool(prompt.get_meta("resolved", false)):
            fade_anchor = max(fade_anchor, float(prompt.get_meta("result_time", target_time)) + pass_by_seconds)
        if _timeline_seconds > fade_anchor:
            var fade: float = clamp((_timeline_seconds - fade_anchor) / max(prompt_fade_seconds, 0.01), 0.0, 1.0)
            prompt.modulate.a = 1.0 - fade

func _horizon_center_x(move: String, lane_w: float, x_side: int) -> float:
    return lerpf(lane_w * 0.5, _target_center_x(move, lane_w, x_side), 0.18)

func _target_center_x(move: String, lane_w: float, x_side: int) -> float:
    if move == "duck":
        return lane_w * 0.28
    var target_center_x: float = lane_w * 0.5
    if x_side == -1:
        # dodge_left → rock is on the RIGHT side of the path (player must go left)
        target_center_x = lane_w * 0.75
    elif x_side == 1:
        # dodge_right → rock is on the LEFT side of the path (player must go right)
        target_center_x = lane_w * 0.25
    return target_center_x

func _cleanup_finished_prompts() -> void:
    var remaining: Array[Control] = []
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

func _base_obstacle_scale(move: String) -> float:
    match move:
        "jump":
            return LOG_PROMPT_SCALE
        "duck":
            return BRANCH_PROMPT_SCALE
        _:
            return ROCK_PROMPT_SCALE

func _exit_perspective_scale(move: String) -> float:
    var start_scale := _start_perspective_scale()
    var hit_scale := _hit_perspective_scale(move)
    return _constant_speed_project(start_scale, hit_scale, prompt_overshoot_ratio)

func _hit_perspective_scale(move: String) -> float:
    match move:
        "jump":
            return 1.45
        "duck":
            return 3.25
        _:
            return 2.05

func _start_perspective_scale() -> float:
    return 0.035

func _perspective_scale_for_progress(move: String, progress: float) -> float:
    return _constant_speed_project(_start_perspective_scale(), _hit_perspective_scale(move), progress)

func _depth_sort_progress(progress: float) -> float:
    return clampf(_projected_progress(progress) / max(_projected_progress(prompt_overshoot_ratio), 0.01), 0.0, 1.0)

func _constant_speed_project(start_value: float, hit_value: float, progress: float) -> float:
    return start_value + (hit_value - start_value) * _projected_progress(progress)

func _projected_progress(progress: float) -> float:
    var clamped_progress := clampf(progress, 0.0, prompt_overshoot_ratio)
    return pow(clamped_progress, FOREGROUND_ACCELERATION_EXPONENT)

func _prompt_center_y(move: String, lane_h: float, _prompt_h: float, _persp_scale: float, progress: float) -> float:
    var start_y := lane_h * HORIZON_Y_RATIO
    var hit_y := lane_h * DODGE_HIT_Y_RATIO

    match move:
        "jump":
            hit_y = lane_h * JUMP_HIT_Y_RATIO
        "duck":
            hit_y = lane_h * DUCK_HIT_Y_RATIO
        "dodge_left", "dodge_right":
            hit_y = lane_h * DODGE_HIT_Y_RATIO

    return _constant_speed_project(start_y, hit_y, progress)

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

func _set_avatar_action(player_id: String, move: String) -> void:
    if not _player_state.has(player_id):
        return
    if move not in ["jump", "duck", "dodge_left", "dodge_right"]:
        return
    var state: Dictionary = _player_state[player_id]
    state["avatar_move"] = move
    state["avatar_action_until"] = _timeline_seconds + AVATAR_ACTION_SECONDS
    _player_state[player_id] = state

func _update_player_avatars() -> void:
    if _avatar_nodes.is_empty():
        return
    var lane_size := lane_1_prompt_layer.size
    if lane_size.x <= 0.0 or lane_size.y <= 0.0:
        return
    _update_player_avatar(PLAYER_1, lane_size)
    _update_player_avatar(PLAYER_2, lane_size)

func _update_player_avatar(player_id: String, lane_size: Vector2) -> void:
    var avatar: Control = _avatar_nodes.get(player_id, null)
    if avatar == null or not is_instance_valid(avatar):
        return

    var state: Dictionary = _player_state.get(player_id, _make_player_state())
    var move := ""
    if _timeline_seconds <= float(state.get("avatar_action_until", -1.0)):
        move = str(state.get("avatar_move", ""))

    var base_x := lane_size.x * (0.43 if player_id == PLAYER_1 else 0.57)
    var base_y := lane_size.y * 0.86
    var x_offset := 0.0
    var y_offset := 0.0
    var scale_y := 1.0
    var rotation := 0.0

    match move:
        "jump":
            y_offset = -72.0
            scale_y = 1.06
        "duck":
            y_offset = 36.0
            scale_y = 0.56
        "dodge_left":
            x_offset = -90.0
            rotation = -0.10
        "dodge_right":
            x_offset = 90.0
            rotation = 0.10

    avatar.position = Vector2(base_x + x_offset - AVATAR_W * 0.5, base_y + y_offset - AVATAR_H)
    avatar.scale = Vector2(1.0, scale_y)
    avatar.rotation = rotation
    avatar.modulate.a = 0.94 if move.is_empty() else 1.0

func _update_status_label() -> void:
    if _results_shown:
        status_label.text = "Round complete • Press R to try again"
        return

    if _round_state == ROUND_SETUP:
        status_label.text = "Stand in your lane • Press Space to start with keyboard"
        return

    if _round_state == ROUND_COUNTDOWN:
        status_label.text = "Starting in %d" % max(1, int(ceil(_countdown_seconds_remaining())))
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
    if _results_shown or _round_state != ROUND_PLAYING:
        return
    _paused = not _paused
    if audio_player.stream != null:
        audio_player.stream_paused = _paused

func _connect_camera() -> void:
    if not camera_input_enabled:
        return

    _camera_connection_state = "connecting"
    _camera_peer = WebSocketPeer.new()
    var err := _camera_peer.connect_to_url(camera_websocket_url)
    if err != OK:
        _camera_peer = null
        _camera_connection_state = "disconnected"
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
        _camera_connection_state = "connected"
        while _camera_peer.get_available_packet_count() > 0:
            var packet := _camera_peer.get_packet()
            _handle_camera_packet(packet.get_string_from_utf8())
    elif state == WebSocketPeer.STATE_CLOSED:
        _camera_connection_state = "disconnected"
        _camera_peer = null
        _next_camera_reconnect_msec = Time.get_ticks_msec() + int(camera_reconnect_seconds * 1000.0)

func _handle_camera_packet(packet_text: String) -> void:
    var parsed: Variant = JSON.parse_string(packet_text)
    if typeof(parsed) != TYPE_DICTIONARY:
        return

    _last_camera_packet_msec = Time.get_ticks_msec()
    var payload: Dictionary = parsed
    var players = payload.get("players", [])
    if str(payload.get("type", "")) == "status":
        _update_camera_player_status(players)
        return

    if _paused or _results_shown or _round_state != ROUND_PLAYING:
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
            "time_seconds": max(0.0, _timeline_seconds - camera_input_latency_offset_seconds),
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

    camera_status_label.text = "Camera: %s • P1 %s • P2 %s" % [
        _camera_connection_state,
        _format_camera_player_status(PLAYER_1),
        _format_camera_player_status(PLAYER_2),
    ]

func _expire_stale_camera_status() -> void:
    if not camera_input_enabled:
        return
    if _last_camera_packet_msec == 0:
        return

    var stale_after_msec := int(camera_status_stale_seconds * 1000.0)
    if Time.get_ticks_msec() - _last_camera_packet_msec <= stale_after_msec:
        return

    _camera_connection_state = "disconnected"
    if _camera_peer != null:
        _camera_peer.close()
        _camera_peer = null
        _next_camera_reconnect_msec = Time.get_ticks_msec() + int(camera_reconnect_seconds * 1000.0)
    _camera_player_status[PLAYER_1] = {"visible": false, "calibrated": false, "confidence": 0.0}
    _camera_player_status[PLAYER_2] = {"visible": false, "calibrated": false, "confidence": 0.0}

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

func _format_prompt_text(move: String, intensity: int) -> String:
    var intensity_hint := ""
    var level := clampi(intensity, 1, 5)
    for i in range(level):
        intensity_hint += "!"

    match move:
        "jump":
            return "JUMP  %s" % intensity_hint
        "duck":
            return "DUCK  %s" % intensity_hint
        "dodge_left":
            return "LEFT  %s" % intensity_hint
        "dodge_right":
            return "RIGHT  %s" % intensity_hint
        _:
            return "%s  %s" % [_display_move_name(move).to_upper(), intensity_hint]

func _prompt_icon_for_move(move: String) -> String:
    match move:
        "jump":
            return "_/\\_"
        "duck":
            return "-----"
        "dodge_left":
            return "<<|"
        "dodge_right":
            return "|>>"
        _:
            return "*"

func _set_prompt_card_result(prompt: Control, judgment: String) -> void:
    var move := str(prompt.get_meta("move", ""))
    var action_label := prompt.get_node_or_null("ActionLabel")
    if action_label is Label:
        (action_label as Label).text = "%s  %s" % [_display_move_name(move).to_upper(), judgment]

func _prompt_visuals_for_move(move: String) -> Dictionary:
    match move:
        "jump":
            return {
                "font_color": Color(0.65, 0.96, 1.0),
                "outline_color": Color(0.06, 0.16, 0.22),
                "shadow_color": Color(0.03, 0.12, 0.2, 0.7),
                "panel_color": Color(0.08, 0.23, 0.31, 0.92),
                "panel_border_color": Color(0.67, 0.96, 1.0, 0.95),
            }
        "duck":
            return {
                "font_color": Color(1.0, 0.9, 0.55),
                "outline_color": Color(0.23, 0.14, 0.03),
                "shadow_color": Color(0.2, 0.12, 0.02, 0.7),
                "panel_color": Color(0.34, 0.22, 0.06, 0.92),
                "panel_border_color": Color(1.0, 0.9, 0.56, 0.95),
            }
        "dodge_left":
            return {
                "font_color": Color(0.7, 1.0, 0.72),
                "outline_color": Color(0.05, 0.2, 0.08),
                "shadow_color": Color(0.04, 0.16, 0.06, 0.7),
                "panel_color": Color(0.07, 0.3, 0.14, 0.92),
                "panel_border_color": Color(0.72, 1.0, 0.74, 0.95),
            }
        "dodge_right":
            return {
                "font_color": Color(1.0, 0.76, 0.92),
                "outline_color": Color(0.24, 0.05, 0.18),
                "shadow_color": Color(0.19, 0.03, 0.14, 0.7),
                "panel_color": Color(0.34, 0.09, 0.26, 0.92),
                "panel_border_color": Color(1.0, 0.78, 0.93, 0.95),
            }
        _:
            return {
                "font_color": Color(1.0, 0.98, 0.85),
                "outline_color": Color(0.05, 0.08, 0.12),
                "shadow_color": Color(0.0, 0.0, 0.0, 0.65),
                "panel_color": Color(0.1, 0.14, 0.2, 0.92),
                "panel_border_color": Color(0.95, 0.95, 1.0, 0.95),
            }

func _camera_ready_for_round() -> bool:
    if not camera_input_enabled or not pre_round_require_camera_ready:
        return true
    return _camera_player_ready(PLAYER_1) and _camera_player_ready(PLAYER_2)

func _camera_player_ready(player_id: String) -> bool:
    var status: Dictionary = _camera_player_status.get(player_id, {})
    return bool(status.get("visible", false)) and bool(status.get("calibrated", false))

func _begin_countdown() -> void:
    if _round_state == ROUND_PLAYING:
        return
    _round_state = ROUND_COUNTDOWN
    _countdown_started_msec = Time.get_ticks_msec()
    ready_overlay.visible = true
    _update_ready_overlay()

func _start_round() -> void:
    _round_state = ROUND_PLAYING
    ready_overlay.visible = false
    _start_ticks_msec = Time.get_ticks_msec()
    _timeline_seconds = 0.0
    if audio_player.stream != null:
        audio_player.play()

func _countdown_seconds_remaining() -> float:
    if _round_state != ROUND_COUNTDOWN:
        return pre_round_countdown_seconds
    var elapsed := float(Time.get_ticks_msec() - _countdown_started_msec) / 1000.0
    return max(0.0, pre_round_countdown_seconds - elapsed)

func _update_ready_overlay() -> void:
    if _round_state == ROUND_PLAYING:
        ready_overlay.visible = false
        return

    ready_overlay.visible = true
    if _round_state == ROUND_COUNTDOWN:
        ready_title_label.text = "%d" % max(1, int(ceil(_countdown_seconds_remaining())))
        ready_body_label.text = "Get ready"
        return

    ready_title_label.text = "Stand in your lane"
    if camera_input_enabled and pre_round_require_camera_ready:
        ready_body_label.text = "Player 1 left: %s\nPlayer 2 right: %s\nPress Space to start anyway" % [
            _format_ready_player_status(PLAYER_1),
            _format_ready_player_status(PLAYER_2),
        ]
    else:
        ready_body_label.text = "Press Space to start"

func _format_ready_player_status(player_id: String) -> String:
    var status: Dictionary = _camera_player_status.get(player_id, {})
    if not bool(status.get("visible", false)):
        return "step into view"
    if not bool(status.get("calibrated", false)):
        return "stand still"
    return "ready"

func _show_results() -> void:
    _results_shown = true
    results_overlay.visible = true
    results_title_label.text = _build_results_title()
    results_body_label.text = "%s\n\n%s\n\nPress R to try again" % [
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
