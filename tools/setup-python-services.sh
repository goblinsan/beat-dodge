#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

for service in camera-input song-analyzer; do
  service_dir="$ROOT_DIR/services/$service"
  python3 -m venv "$service_dir/.venv"
  "$service_dir/.venv/bin/pip" install --upgrade pip
  "$service_dir/.venv/bin/pip" install -r "$service_dir/requirements.txt"
  "$service_dir/.venv/bin/pip" install -e "$service_dir"
done
