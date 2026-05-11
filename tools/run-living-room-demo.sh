#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CAMERA_PY="$ROOT_DIR/services/camera-input/.venv/bin/python"

if [[ ! -x "$CAMERA_PY" ]]; then
  echo "Python services are not installed. Run tools/setup-python-services.sh first." >&2
  exit 1
fi

if ! command -v godot >/dev/null 2>&1; then
  echo "Godot was not found on PATH. Install Godot 4 and ensure 'godot' is available." >&2
  exit 1
fi

export MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp/beat-dodge-matplotlib}"
mkdir -p "$MPLCONFIGDIR"

cleanup() {
  if [[ -n "${CAMERA_PID:-}" ]]; then
    kill "$CAMERA_PID" >/dev/null 2>&1 || true
    wait "$CAMERA_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

"$CAMERA_PY" -m camera_input.cli --websocket --debug --calibration-seconds 2 "$@" &
CAMERA_PID=$!

sleep 2
exec godot --path "$ROOT_DIR/game/godot-project"
