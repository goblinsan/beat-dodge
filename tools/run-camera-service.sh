#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="$ROOT_DIR/services/camera-input/.venv/bin/python"

if [[ ! -x "$VENV_PY" ]]; then
  echo "Camera service virtualenv not found. Run tools/setup-python-services.sh first." >&2
  exit 1
fi

exec "$VENV_PY" -m camera_input.cli --websocket --debug "$@"
