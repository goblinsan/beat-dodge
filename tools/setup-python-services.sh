#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-}"

if [[ -z "$PYTHON_BIN" ]]; then
  if command -v python3.11 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3.11)"
  else
    PYTHON_BIN="$(command -v python3)"
  fi
fi

"$PYTHON_BIN" - <<'PY'
import sys

if sys.version_info < (3, 11):
    raise SystemExit("Beat Dodge services require Python 3.11 or newer.")
PY

for service in camera-input song-analyzer; do
  service_dir="$ROOT_DIR/services/$service"
  "$PYTHON_BIN" -m venv --clear "$service_dir/.venv"
  "$service_dir/.venv/bin/pip" install --upgrade pip
  "$service_dir/.venv/bin/pip" install -r "$service_dir/requirements.txt"
  "$service_dir/.venv/bin/pip" install -e "$service_dir"
done
