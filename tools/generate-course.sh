#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: tools/generate-course.sh <song-file> [output-json] [generate-course args...]" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="$ROOT_DIR/services/song-analyzer/.venv/bin/python"
SONG_FILE="$1"
shift

OUTPUT_FILE="$ROOT_DIR/courses/generated/course.json"
if [[ $# -gt 0 && "$1" != --* ]]; then
  OUTPUT_FILE="$1"
  shift
fi

if [[ ! -x "$VENV_PY" ]]; then
  echo "Song analyzer virtualenv not found. Run tools/setup-python-services.sh first." >&2
  exit 1
fi

ensure_playable_song() {
  local input_file="$1"
  local ext="${input_file##*.}"
  local ext_lc
  ext_lc="$(printf '%s' "$ext" | tr '[:upper:]' '[:lower:]')"

  case "$ext_lc" in
    wav|ogg|mp3)
      printf '%s\n' "$input_file"
      return 0
      ;;
  esac

  local base_no_ext="${input_file%.*}"
  local output_file="${base_no_ext}.ogg"

  if [[ -f "$output_file" ]]; then
    printf '%s\n' "$output_file"
    return 0
  fi

  echo "Converting unsupported audio format '.$ext_lc' to OGG for Godot..." >&2
  if command -v ffmpeg >/dev/null 2>&1; then
    ffmpeg -y -i "$input_file" -vn -acodec libvorbis "$output_file" >/dev/null 2>&1
  elif command -v afconvert >/dev/null 2>&1; then
    # macOS fallback: convert to WAV if ffmpeg is unavailable.
    output_file="${base_no_ext}.wav"
    afconvert -f WAVE -d LEI16@44100 "$input_file" "$output_file" >/dev/null 2>&1
  else
    echo "Error: no audio converter found. Install ffmpeg, or use WAV/MP3/OGG input." >&2
    exit 1
  fi

  if [[ ! -f "$output_file" ]]; then
    echo "Error: audio conversion failed for '$input_file'." >&2
    exit 1
  fi

  printf '%s\n' "$output_file"
}

ANALYZE_FILE="$(ensure_playable_song "$SONG_FILE")"
SONG_ID_OVERRIDE="$(basename "$ANALYZE_FILE")"

mkdir -p "$(dirname "$OUTPUT_FILE")"
exec "$VENV_PY" -m song_analyzer.course_cli "$ANALYZE_FILE" --output "$OUTPUT_FILE" --song-id "$SONG_ID_OVERRIDE" "$@"
