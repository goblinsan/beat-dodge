# song-analyzer

Python service that analyses a local audio file and extracts structured data used by the Beat Dodge game.

## What it extracts

| Field | Description |
|---|---|
| `duration_seconds` | Total duration of the track |
| `bpm` | Estimated tempo |
| `beats` | List of beat timestamps (seconds) |
| `energy_windows` | 1-second slices, each with RMS energy and a normalised level (1–5) |

## Setup

```bash
cd services/song-analyzer
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Usage

### Analyse a song (raw analysis JSON)

```bash
# Print JSON to stdout
analyze-song path/to/song.mp3

# Write JSON to a file
analyze-song path/to/song.mp3 --output analysis.json
```

### Generate a Beat Dodge course

```bash
# Print course JSON to stdout
generate-course path/to/song.mp3

# Write course JSON to a file
generate-course path/to/song.mp3 --output courses/generated/my_course.json
```

## Output format

### `analyze-song`

```json
{
  "version": "1.0.0",
  "source": "song.mp3",
  "duration_seconds": 212.5,
  "bpm": 128.0,
  "beats": [0.511, 0.977, 1.443],
  "energy_windows": [
    {"start_seconds": 0.0, "end_seconds": 1.0, "energy": 0.142, "level": 2},
    {"start_seconds": 1.0, "end_seconds": 2.0, "energy": 0.201, "level": 4}
  ]
}
```

### `generate-course`

Produces a course document conforming to `docs/schemas/course.schema.json`.
Each event targets one of the two players with a kid-friendly movement prompt
at a beat-aligned timestamp.

```json
{
  "version": "1.0.0",
  "song": {
    "id": "song.mp3",
    "bpm": 128.0,
    "duration_seconds": 212.5
  },
  "events": [
    {"time_seconds": 0.511, "player": "player_1", "move": "dodge_left",  "intensity": 2},
    {"time_seconds": 0.977, "player": "player_2", "move": "dodge_right", "intensity": 3},
    {"time_seconds": 1.443, "player": "player_1", "move": "jump",        "intensity": 4}
  ]
}
```

Supported moves: `dodge_left`, `dodge_right`, `jump`, `duck`.

## Running tests

```bash
python -m pytest tests/ -v
```
