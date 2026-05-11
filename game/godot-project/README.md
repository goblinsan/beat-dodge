# Godot Game Foundation

This project now includes a minimal Godot 4 runtime foundation that:

- loads a course JSON file (`course_path`),
- loads/plays a song file (`music_path` or `song.id` from the course),
- advances a synchronized timeline,
- renders two player lanes, and
- spawns/moves movement prompts on those lanes.

## Open and run

1. Open `game/godot-project/` in Godot 4.
2. Run the default scene (`res://scenes/main.tscn`).

By default, it uses `res://data/sample_course.json` and `res://audio/sample_tone.wav`.
