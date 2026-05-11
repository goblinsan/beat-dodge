# camera-input

Python service that captures webcam frames and emits per-frame player pose data for Beat Dodge.

## What it does

| Step | Description |
|---|---|
| Capture | Reads frames from the default webcam via OpenCV |
| Detect | Runs MediaPipe Pose on each player lane (left/right half of frame) |
| Assign | Maps detections to Player 1 (left lane) and Player 2 (right lane) |
| Emit | Prints one JSON object per frame to stdout, conforming to `docs/schemas/camera-frame.schema.json` |
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

## Running tests

```bash
python -m pytest tests/ -v
```
