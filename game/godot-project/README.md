# Godot Game Foundation

This project now includes a minimal Godot 4 runtime foundation that:

- loads a course JSON file (`course_path`),
- loads/plays a song file (`music_path` or `song.id` from the course),
- advances a synchronized timeline,
- renders two player lanes, and
- spawns/moves movement prompts on those lanes,
- supports two-player keyboard fallback (`A/W/S/D` and arrow keys),
- scores prompts with Perfect/Good/Early/Late/Miss timing windows, and
- shows per-player combos plus end-of-round results.

## Open and run

1. Open `game/godot-project/` in Godot 4.
2. Run the default scene (`res://scenes/main.tscn`).

By default, it uses `res://data/sample_course.json` and `res://audio/sample_tone.wav`.

## Camera input

The runtime connects to `ws://127.0.0.1:8765` by default and maps camera actions
to the existing prompt names:

| Camera action | Runtime move |
|---|---|
| `jump` | `jump` |
| `duck` | `duck` |
| `dodge_left` / `leanLeft` | `dodge_left` |
| `dodge_right` / `leanRight` | `dodge_right` |

Start the camera service before launching the scene:

```bash
../../tools/run-camera-service.sh
```

Keyboard controls remain enabled as fallback while camera input is connected.

Useful exported camera settings on the main scene:

| Setting | Purpose |
|---|---|
| `camera_input_enabled` | Turns camera input on/off without disabling keyboard fallback |
| `camera_websocket_url` | WebSocket endpoint, default `ws://127.0.0.1:8765` |
| `camera_min_confidence` | Ignores low-confidence camera actions |
| `camera_input_latency_offset_seconds` | Scores camera actions slightly earlier to compensate for camera/transport latency |
| `camera_status_stale_seconds` | Marks camera/player status lost when events stop arriving |
