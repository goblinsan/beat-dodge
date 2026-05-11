#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: tools/generate-course.sh <song-file> [output-json]" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="$ROOT_DIR/services/song-analyzer/.venv/bin/python"
SONG_FILE="$1"
OUTPUT_FILE="${2:-$ROOT_DIR/courses/generated/course.json}"

if [[ ! -x "$VENV_PY" ]]; then
  echo "Song analyzer virtualenv not found. Run tools/setup-python-services.sh first." >&2
  exit 1
fi

mkdir -p "$(dirname "$OUTPUT_FILE")"
exec "$VENV_PY" -m song_analyzer.course_cli "$SONG_FILE" --output "$OUTPUT_FILE"
