# Beat Dodge Living Room Demo Runbook

## Setup

1. Put the webcam above or below the TV/monitor, centered between both players.
2. Give each kid a clear left or right half of the camera view.
3. Turn on enough room lighting for full-body tracking.
4. Keep chairs, tables, and toys out of the lanes.

## First-Time Install

```bash
tools/setup-python-services.sh
```

## Start Camera Input

```bash
tools/run-camera-service.sh
```

Keep both players standing still in their lanes for the first second or two so
the service can calibrate their standing baseline.

## Start The Game

Open `game/godot-project/` in Godot 4 and run the main scene.

The top camera status line should move from `connecting` to `connected`, then
show each player as `calibrating` or `ready`.

## Controls

Camera actions:

- Jump
- Duck
- Move left
- Move right

Keyboard fallback:

- Player 1: `A`, `D`, `W`, `S`
- Player 2: arrow keys

## Troubleshooting

- `Camera: connecting`: make sure `tools/run-camera-service.sh` is running.
- Player shows `lost`: move fully into the left or right lane and improve room
  lighting.
- Player stays `calibrating`: stand still for a couple of seconds.
- Actions feel late: increase Godot timing windows or lower camera confidence
  only after checking that debug overlay tracking is stable.
