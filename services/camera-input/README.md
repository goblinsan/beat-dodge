# camera-input

Python service that captures webcam frames and emits per-frame player pose data for Beat Dodge.

## What it does

| Step | Description |
|---|---|
| Capture | Reads frames from the default webcam via OpenCV |
| Detect | Runs MediaPipe Pose on each player lane (left/right half of frame) |
| Assign | Maps detections to Player 1 (left lane) and Player 2 (right lane) |
| Emit | Prints one JSON object per frame to stdout, conforming to `docs/schemas/camera-frame.schema.json` |
| Actions | Optionally classifies movement actions and emits `docs/schemas/camera-action.schema.json` events |
| Transport | Optionally serves action events over WebSocket for the Godot runtime |
| Debug | Optional OpenCV window with skeleton overlay, player IDs, and lane boundaries |

## Setup

```bash
cd services/camera-input
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Usage

```bash
# Stream frame JSON to stdout (Ctrl-C to stop)
capture-pose

# Use a specific camera device
capture-pose --device 1

# Show debug overlay window (press q to quit)
capture-pose --debug

# Stop after a fixed number of frames
capture-pose --max-frames 100

# Emit gameplay action/status events as JSON lines
capture-pose --actions --debug

# Serve gameplay action/status events to Godot
capture-pose --websocket --debug

# Use a two-second standing calibration period
capture-pose --websocket --debug --calibration-seconds 2
```

## Output format

Each line printed to stdout is a JSON object conforming to
`docs/schemas/camera-frame.schema.json`:

```json
{
  "timestamp_ms": 1234567,
  "players": [
    {"player_id": 1, "visible": true,  "x": 0.27, "y": 0.61},
    {"player_id": 2, "visible": false, "x": 0.0,  "y": 0.0}
  ]
}
```

`x` and `y` are normalised 0–1 coordinates of each player's body centre
(hip midpoint), derived from MediaPipe pose landmarks.

With `--actions`, action events are printed when a movement is detected:

```json
{
  "timestamp_ms": 1234567,
  "players": [
    {"id": 1, "action": "jump", "confidence": 0.82}
  ]
}
```

When no action is detected, status events are emitted so the game can show
connection, visibility, and calibration state:

```json
{
  "timestamp_ms": 1234567,
  "type": "status",
  "players": [
    {"id": 1, "visible": true, "calibrated": true, "confidence": 0.91},
    {"id": 2, "visible": false, "calibrated": false, "confidence": 0.0}
  ]
}
```

## Player lane assignment

The camera frame is divided vertically at the midpoint:

```
|  Player 1  |  Player 2  |
|  (left)    |  (right)   |
```

MediaPipe Pose is run independently on each half so that two players can
be tracked simultaneously.

## Landmarks extracted

The service extracts the following landmarks for movement classification:

| Name | Use |
|---|---|
| `nose` | Head position (duck detection) |
| `left_shoulder`, `right_shoulder` | Upper-body tracking |
| `left_hip`, `right_hip` | Body centre; duck baseline |
| `left_knee`, `right_knee` | Jump / duck detection |
| `left_ankle`, `right_ankle` | Jump detection |
| `left_elbow`, `right_elbow` | Arm tracking |
| `left_wrist`, `right_wrist` | Hand tracking |

## Movement actions

The first living-room implementation supports the same four prompt names used
by the current Godot course runtime:

| Action | Camera heuristic |
|---|---|
| `jump` | Hip/body center moves upward from standing baseline |
| `duck` | Nose/shoulders/hips move downward from standing baseline |
| `dodge_left` | Body center shifts left from lane baseline |
| `dodge_right` | Body center shifts right from lane baseline |

The classifier collects a short standing baseline when the service starts.
Keep both players standing still in their lanes for the first second or two
before the round begins.

## Running tests

```bash
python -m pytest tests/ -v
```
