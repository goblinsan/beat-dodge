# Beat Dodge

Beat Dodge is a **2-player, camera-based PC party game** where players physically dodge beat-synced obstacles generated from music.

## Product vision

Create a fast, social game loop that blends rhythm gameplay with body movement:

- **Input:** live camera tracking for two players.
- **Music intelligence:** beat and energy analysis from songs.
- **Gameplay:** spawn dodge patterns aligned to beat timing and intensity.
- **Experience:** quick setup, short rounds, and replayable party sessions.

## MVP scope

The first milestone focuses on proving the core end-to-end loop:

1. Capture player pose/position data from webcam input.
2. Analyze a song into beat events and simple difficulty signals.
3. Generate a dodge course from the analyzed song timeline.
4. Run the course inside a Godot 4 prototype scene for 2 local players.

### Planned stack

- **Game client:** Godot 4 (`game/godot-project/`)
- **Camera input service:** Python + MediaPipe + OpenCV (`services/camera-input/`)
- **Song analyzer service:** Python + librosa (`services/song-analyzer/`)

## Repository structure

```text
.github/workflows/        # CI workflow definitions
courses/generated/        # Generated course files
courses/samples/          # Hand-authored/sample course files
docs/                     # Project documentation
  schemas/                # JSON schemas for service contracts and courses
game/godot-project/       # Godot game project
services/camera-input/    # Camera tracking service
services/song-analyzer/   # Song analysis service
songs/                    # Local songs (gitignored content, keep directory)
tools/                    # Utility scripts and local helpers
```

## Schemas

Initial schemas are defined in `docs/schemas/`:

- `course.schema.json`: generated course data consumed by the game.
- `camera-frame.schema.json`: frame-level camera tracking output.
- `camera-action.schema.json`: sparse movement actions consumed by the game.

## Local development guidance

### Prerequisites

- Godot 4.x
- Python 3.11+
- Webcam supported by OpenCV

### Suggested setup flow

1. Clone the repository.
2. Run `tools/setup-python-services.sh` to create Python virtual environments
   and install service dependencies.
3. Place local test tracks under `songs/`.
4. Use `courses/samples/` for hand-authored fixtures and `courses/generated/`
   for analyzer output.
5. Run `tools/run-camera-service.sh` to serve camera action events.
6. Open `game/godot-project/` in Godot 4 and run the default scene.

### Living-room demo

After installing dependencies and Godot 4, run:

```bash
./run-living-room-demo.sh
```

This starts the camera WebSocket service, opens the Godot project, and keeps
keyboard fallback enabled.

For living-room setup details, see `docs/living_room_demo_runbook.md`.

### Notes

- Keep large media files and generated artifacts out of git unless intentionally versioned.
- Use JSON schema validation against `docs/schemas/` when adding/updating payload formats.
