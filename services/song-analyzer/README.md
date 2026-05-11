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

```bash
# Print JSON to stdout
analyze-song path/to/song.mp3

# Write JSON to a file
analyze-song path/to/song.mp3 --output courses/generated/my_course.json
```

## Output format

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

## Running tests

```bash
python -m pytest tests/ -v
```
