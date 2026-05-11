# Beat Dodge Living Room Playability Gap Plan (2026-05-11)

## Purpose

This plan validates `docs/implementation_status_report_2026-05-11.md` against
`docs/multiplayer_camera_music_game_project_plan.md` and the current code, then
turns the remaining gaps into a pragmatic implementation sequence for a
two-kid living room playtest.

## Validation Summary

The implementation status report is directionally accurate: Beat Dodge is a
keyboard-playable Godot prototype with a song analyzer, course generator, and
pose-tracking camera service, but it is not yet playable from a webcam in a
living room.

Corrections and clarifications:

- Current implementation percentage should be treated as a rough planning
  estimate, not a tested delivery metric. Tests could not be run in the current
  shell because `pytest` is not installed.
- The repository structure mostly exists, including `.github/`, `courses/`,
  `songs/`, and `tools/`, but `tools/` and `.github/workflows/` currently only
  contain `.gitkeep` placeholders.
- The report correctly says there is no root `.gitignore`.
- The course implementation is internally consistent with
  `docs/schemas/course.schema.json`, but the schema is narrower than the project
  plan. It supports `dodge_left`, `dodge_right`, `jump`, and `duck`, not
  `leanLeft`, `leanRight`, `leftHandUp`, `rightHandUp`, `handsUp`, `freeze`, or
  `both` player prompts.
- The current camera schema is frame telemetry, not the movement event format
  described in the project plan. It emits `timestamp_ms`, player visibility,
  and body-center coordinates only.
- The camera service extracts landmarks needed for movement classification, but
  it does not currently classify or publish gameplay actions.
- The Godot runtime has an internal `_handle_action_input` scoring path, but
  only keyboard events call it. There is no WebSocket or UDP camera integration.
- The status report understates one packaging gap: no CI workflow exists beyond
  a `.gitkeep`, and no desktop export presets are present.
- The status report's living-room blocker assessment is correct: camera action
  detection, transport, game integration, setup UX, and launch scripts are the
  remaining critical path.

## Living Room MVP Target

The next deliverable is not the full project-plan MVP. It is a reliable local
playtest where two kids can stand in front of one webcam and finish a short
round with minimal parent intervention.

Done means:

- Player 1 and Player 2 are assigned by left/right lane.
- Each player can trigger `jump`, `duck`, `dodge_left`, and `dodge_right` from
  body movement.
- Camera input reaches Godot with less than 300 ms typical end-to-end latency.
- Keyboard fallback still works.
- The game shows whether the camera service is connected and whether each
  player is visible.
- The round can be restarted without reopening Godot.
- A parent can run setup, generate a course, start camera input, and launch the
  game from documented commands.

## Implementation Strategy

Keep the first living-room version smaller than the project plan:

- Map camera `leanLeft`/`leanRight` to the runtime's existing
  `dodge_left`/`dodge_right` prompt names instead of renaming the whole course
  format immediately.
- Defer `leftHandUp`, `rightHandUp`, `handsUp`, `freeze`, and `both` prompts
  until the basic four-action game is playable.
- Use WebSocket transport because the project plan recommends it and Godot 4
  has built-in WebSocket support.
- Add calibration as simple baseline capture first, not a full onboarding flow.
- Optimize for forgiving detection and visible feedback over strict accuracy.

## Phase 1 - Camera Movement Events

Goal: convert per-frame landmarks into stable gameplay actions.

Files likely touched:

- `services/camera-input/camera_input/detector.py`
- `services/camera-input/camera_input/players.py`
- New `services/camera-input/camera_input/movement.py`
- `services/camera-input/camera_input/cli.py`
- `docs/schemas/camera-action.schema.json`
- Camera service tests

Tasks:

1. Add a `PlayerPoseFrame` or equivalent model that keeps player ID, visibility,
   body center, and relevant landmarks together.
2. Implement baseline calibration per lane:
   - standing hip/shoulder/nose height
   - lane center
   - recent body-center history
3. Implement classifiers:
   - `jump`: hip/body center moves up relative to baseline
   - `duck`: nose/shoulder/hip height lowers relative to baseline
   - `dodge_left`: body center shifts left relative to lane baseline
   - `dodge_right`: body center shifts right relative to lane baseline
4. Add confidence scores based on landmark visibility and movement magnitude.
5. Add temporal smoothing:
   - short rolling window of frames
   - minimum confidence threshold
   - cooldown so one movement does not fire repeatedly across many frames
6. Emit action events in this shape:

```json
{
  "timestamp_ms": 124350,
  "players": [
    {"id": 1, "action": "jump", "confidence": 0.91},
    {"id": 2, "action": "duck", "confidence": 0.87}
  ]
}
```

Acceptance criteria:

- Unit tests cover each classifier using synthetic landmarks.
- With debug mode on, the overlay shows current action and confidence per
  visible player.
- The service can still emit frame telemetry for debugging.

## Phase 2 - WebSocket Camera Service

Status: implemented in the current working tree.

Goal: make camera actions available to Godot without piping stdout.

Files likely touched:

- `services/camera-input/camera_input/cli.py`
- New `services/camera-input/camera_input/server.py`
- `services/camera-input/README.md`
- `tools/run-camera-service.sh`

Tasks:

1. Add a WebSocket server on `127.0.0.1:8765`.
2. Broadcast camera action events to connected clients.
3. Add CLI flags:
   - `--websocket`
   - `--host`
   - `--port`
   - `--calibration-seconds`
   - `--debug`
4. Keep JSON-lines stdout mode available for tests and diagnostics.
5. Add a simple heartbeat/status message when no action fires but players are
   visible or lost.

Acceptance criteria:

- `capture-pose --websocket --debug` starts the camera feed and serves action
  events.
- A small test client can connect and receive JSON action/status messages.
- Disconnecting Godot does not crash the camera service.

Implemented notes:

- `camera_input.server.serve_events` uses one producer loop and broadcasts the
  same event stream to all connected WebSocket clients.
- `capture-pose --websocket` supports `--host`, `--port`,
  `--calibration-seconds`, `--calibration-frames`, and
  `--websocket-send-interval`.
- JSON-lines stdout mode remains the default for diagnostics and tests.
- WebSocket client/reconnect tests are covered in
  `services/camera-input/tests/test_server.py`.

## Phase 3 - Godot Camera Integration

Status: implemented in the current working tree.

Goal: route camera actions into the existing scoring path.

Files likely touched:

- `game/godot-project/scripts/course_runtime.gd`
- `game/godot-project/scenes/main.tscn`
- `game/godot-project/README.md`

Tasks:

1. Add a `WebSocketPeer` client to connect to the camera service.
2. Parse incoming camera event JSON.
3. Map camera player IDs to runtime player IDs:
   - `1` -> `player_1`
   - `2` -> `player_2`
4. Map camera actions to course moves:
   - `jump` -> `jump`
   - `duck` -> `duck`
   - `leanLeft` or `dodge_left` -> `dodge_left`
   - `leanRight` or `dodge_right` -> `dodge_right`
5. Call `_handle_action_input` with `source = "camera"`.
6. Add exported settings:
   - camera input enabled
   - WebSocket URL
   - minimum camera confidence
   - optional input latency offset
7. Add camera status UI:
   - disconnected
   - connected
   - P1 visible/lost
   - P2 visible/lost

Acceptance criteria:

- Starting the camera service before the game allows body actions to score
  prompts.
- Keyboard controls still work during the same run.
- Camera disconnect shows a visible warning but does not break the round.

Implemented notes:

- `course_runtime.gd` connects to `camera_websocket_url` with `WebSocketPeer`
  and reconnects after disconnects.
- Camera action packets are parsed, confidence-filtered, mapped to runtime
  player IDs and moves, then routed into `_handle_action_input` with
  `source = "camera"`.
- Keyboard fallback remains enabled during camera play.
- Exported camera settings now include enablement, WebSocket URL, minimum
  confidence, reconnect interval, input latency offset, and stale-status
  timeout.
- The gameplay HUD shows camera connection state plus P1/P2 lost,
  calibrating, or ready status.

## Phase 4 - Minimal Kid-Friendly Play Flow

Goal: reduce friction for a living-room playtest.

Files likely touched:

- `game/godot-project/scripts/course_runtime.gd`
- `game/godot-project/scenes/main.tscn`
- `game/godot-project/data/sample_course.json`
- Optional new sample course/audio

Tasks:

1. Add pause and restart controls.
2. Add a pre-round ready state:
   - wait for both players visible
   - show simple stand-left/stand-right guidance
   - start countdown
3. Add a post-round try-again action.
4. Improve prompt labels for kids:
   - "Jump"
   - "Duck"
   - "Move Left"
   - "Move Right"
5. Add stronger immediate hit/miss feedback using color and larger text.
6. Tune default timing windows if camera latency needs more forgiveness.

Acceptance criteria:

- Two kids can understand what to do from the screen without reading developer
  docs.
- A parent can restart a failed setup or round from the keyboard.
- A full sample round can be played repeatedly without restarting the editor.

## Phase 5 - Course Generation Needed For Play

Goal: generate courses that are fun and physically possible for kids.

Files likely touched:

- `services/song-analyzer/song_analyzer/course_generator.py`
- `services/song-analyzer/song_analyzer/course_cli.py`
- `docs/schemas/course.schema.json`
- Song analyzer tests
- `tools/generate-course.sh`

Tasks:

1. Add difficulty settings:
   - `easy`: every 4 beats, mostly jump/duck
   - `normal`: every 2-4 beats, includes dodge left/right
   - `hard`: every 1-2 beats, more alternation
2. Add impossible-sequence prevention:
   - no repeated jumps too close together
   - no jump immediately followed by duck without enough spacing
   - no rapid left/right spam for the same player
3. Add energy-aware density:
   - sparse prompts in low-energy windows
   - denser prompts in high-energy windows
4. Add deterministic seed support for repeatable courses.
5. Add at least one committed generated sample course using the non-copyright
   sample audio.

Acceptance criteria:

- Generated easy courses are playable by kids using camera input.
- The generator still produces schema-valid JSON.
- Both players receive roughly equal activity.

## Phase 6 - One-Command Local Demo

Goal: make the project runnable without remembering service internals.

Files likely touched:

- `tools/setup-python-services.sh`
- `tools/generate-course.sh`
- `tools/run-camera-service.sh`
- `tools/run-living-room-demo.sh`
- `README.md`
- `docs/living_room_demo_runbook.md`
- `.gitignore`
- Optional `.github/workflows/ci.yml`

Tasks:

1. Add root `.gitignore` for:
   - Python caches and virtualenvs
   - Godot generated/imported artifacts
   - local songs
   - generated courses unless intentionally sampled
2. Add setup script for both Python services.
3. Add course generation wrapper.
4. Add camera service wrapper.
5. Add a living-room demo runbook:
   - webcam placement
   - lighting guidance
   - player spacing
   - launch order
   - troubleshooting
6. Add CI that runs Python unit tests when dependencies are available.
7. Add Godot export presets later, after camera gameplay works in-editor.

Acceptance criteria:

- From a fresh clone, a parent/developer can follow one page and reach a local
  demo.
- The commands do not require editing source files.
- Local songs remain uncommitted by default.

## Recommended Build Order

1. Phase 1: movement classifiers and action event schema.
2. Phase 2: WebSocket server in the camera service.
3. Phase 3: Godot WebSocket client and action mapping.
4. Phase 4: pre-round setup, restart, and stronger feedback.
5. Phase 5: easy/normal course generation improvements.
6. Phase 6: scripts, runbook, ignore rules, and CI.

## First Implementation Slice

The first slice should be small enough to validate in one real room:

1. Add `movement.py` with calibrated `jump`, `duck`, `dodge_left`, and
   `dodge_right` detection.
2. Add tests for synthetic pose sequences.
3. Add WebSocket broadcasting behind `capture-pose --websocket`.
4. Add Godot WebSocket client that feeds `_handle_action_input`.
5. Test against `game/godot-project/data/sample_course.json`.

This slice proves the core risk: whether two kids can trigger recognizable
actions from one webcam quickly enough for the existing scoring windows.

## Deferred Until After First Living Room Playtest

- `leftHandUp`, `rightHandUp`, `handsUp`, and `freeze`.
- `both` player prompt support.
- Full main menu/song picker.
- Rich avatars, prompt icons, SFX, and celebrations.
- Desktop export presets.
- 4-player support.
- Advanced song section detection.
